"""Internal helper used by ``edit`` to run a buffer in a multishell tab.

Direct port of ``rom/modules/main/cc/internal/edit_runner.lua``: launches the
program, prints any errors, and prompts the user to close the tab.

This is an internal module and should not be used by external programs.
"""

from __future__ import annotations

import inspect
import traceback

from cc import os as ccos
from cc import term as ccterm


# Pending edit runs keyed by an integer token. ``edit`` populates this map
# before launching a multishell tab, then the tab's bootstrap calls
# :func:`pop_request` to pull its job out and pass it back to :func:`run`.
_pending: dict[int, tuple[str, str, str]] = {}
_next_token = 1


def submit_request(title, path, contents) -> int:
    """Stash a buffer for a soon-to-be-launched runner tab.

    Returns a token the runner program can pass to :func:`pop_request`.
    """
    global _next_token
    token = _next_token
    _next_token += 1
    _pending[token] = (str(title), str(path), str(contents))
    return token


def pop_request(token):
    """Remove and return ``(title, path, contents)`` for ``token``."""
    return _pending.pop(int(token), None)


async def run(title, path, contents):
    """Compile and execute ``contents`` as a Python program in the current tab."""
    # Set the tab title (Lua: ``multishell.setTitle(multishell.getCurrent(), title)``).
    try:
        from cc import multishell as _ccmultishell

        if _ccmultishell.is_active():
            cur = _ccmultishell.get_current()
            if cur is not None:
                _ccmultishell.set_title(cur, title)
    except Exception:
        pass

    current = ccterm.current()

    # Build a program env. We reuse :meth:`Shell._make_program_env` indirectly
    # by spinning up a child Shell so ``shell``/``multishell`` etc. are
    # available in the running buffer just like Lua's ``edit_runner`` injects
    # ``_ENV``.
    from cc import shell as _ccshell
    from cc.shell import Shell as _Shell

    prev_shell = _ccshell._current
    proc_shell = _Shell()
    _ccshell.set_current(proc_shell)

    try:
        from cc.shell import _isolate_program
        from cc.shell import _run_program_source as _run_source

        async def _run_buffer():
            # Yield once before running user code so edit->run can't hit the
            # watchdog during compilation/large top-level work.
            await ccos.sleep(0)

            env = proc_shell._make_program_env("/" + str(path), [str(path)])

            await _run_source(str(contents), str(path), env, [str(path)])

            fn = env.get("main")
            if fn is not None and inspect.iscoroutinefunction(fn):
                await fn()

        exc = await _isolate_program(_run_buffer)
        if exc is None:
            pass
        elif isinstance(exc, SyntaxError):
            _print_error("".join(traceback.format_exception_only(type(exc), exc)).rstrip())
        elif ccos.is_terminated(exc):
            return
        else:
            _print_error(
                "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)).rstrip()
            )
    finally:
        _ccshell.set_current(prev_shell)

    # Restore the tab redirect; user code may have redirected internally.
    ccterm.redirect(current)
    try:
        if ccterm.is_color():
            ccterm.set_text_color(0x10)  # yellow
        else:
            ccterm.set_text_color(0x1)  # white
    except Exception:
        pass
    try:
        ccterm.set_background_color(0x8000)  # black
    except Exception:
        pass
    try:
        ccterm.set_cursor_blink(False)
    except Exception:
        pass

    # Lua wraps "Press any key to continue." across multiple lines; we keep
    # it single-line which is what virtually all CC terminal sizes can fit.
    message = "Press any key to continue."
    try:
        _, y = ccterm.get_cursor_pos()
        w, h = ccterm.get_size()
        start_y = h
        if y >= start_y:
            ccterm.scroll(y - start_y + 1)
        ccterm.set_text_color(0x1)
        ccterm.set_background_color(0x8000)
        ccterm.set_cursor_pos(1, start_y)
        ccterm.write(message[: max(0, w)])
    except Exception:
        pass

    try:
        await ccos.pull_event("key")
    except ccos.Terminated:
        return
    except Exception:
        pass


def _print_error(message):
    try:
        if ccterm.is_color():
            prev = ccterm.get_text_color()
            ccterm.set_text_color(0x4000)
            ccterm.write_wrapped(str(message) + "\n")
            ccterm.set_text_color(prev)
            return
    except Exception:
        pass
    try:
        ccterm.write_wrapped(str(message) + "\n")
    except Exception:
        pass
