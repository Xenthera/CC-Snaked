"""Interactive Python REPL (CraftOS ``python`` program).

Uses the same incremental compilation strategy as :mod:`code` / :mod:`codeop`
(:class:`code.InteractiveConsole`): primary prompt ``>>> `` and continuation
``... `` until :func:`codeop.CommandCompiler` produces a complete interactive
command (``symbol="single"``). Executed with :func:`exec`, matching native REPL
behaviour for blocks, indentation, and expression display.

Lua ``lua.lua`` only offers single-line input; Python intentionally diverges here.
"""

from __future__ import annotations

import traceback

import codeop
import ast
import inspect

from cc.line_reader import read_line


PS1 = ">>> "
PS2 = "... "


def _compile_repl_command(source: str, filename: str):
    """Call :func:`codeop.compile_command` with only kwargs the host supports.

    GraalPy (and older CPython ``codeop``) only implements ``(source, filename, symbol)``.
    CPython 3.13+ adds ``flags`` / ``dont_inherit`` / ``optimize``. Passing unsupported
    keywords breaks the REPL with :class:`TypeError`.
    """
    cc = codeop.compile_command
    try:
        sig = inspect.signature(cc)
    except (TypeError, ValueError):
        return cc(source, filename, "single")

    kw = {"filename": filename, "symbol": "single"}
    if "flags" in sig.parameters:
        kw["flags"] = getattr(ast, "PyCF_ALLOW_TOP_LEVEL_AWAIT", 0x2000)
    if "dont_inherit" in sig.parameters:
        kw["dont_inherit"] = True
    if "optimize" in sig.parameters:
        kw["optimize"] = -1
    try:
        return cc(source, **kw)
    except TypeError:
        return cc(source, filename, "single")


class _Exit:
    """Callable singleton so ``exit`` matches Lua's prompt behaviour."""

    _stop: list

    def __init__(self, stop: list) -> None:
        self._stop = stop

    def __repr__(self) -> str:
        return "Call exit() to exit."

    def __call__(self) -> None:
        self._stop[0] = True


async def main() -> None:
    if len(arg) >= 2:
        print("This is an interactive Python prompt.")
        print("To run a program, use its name from the shell.")
        return

    stop = [False]
    repl_env: dict = {
        "__builtins__": __builtins__,
        "exit": _Exit(stop),
        "shell": shell,
        "fs": fs,
        "term": term,
        "os": os,
        "help": help,
        "print": print,
        "printError": printError,
    }

    # Mirror lua.lua: implicitly print expression results in the REPL.
    # Python does this via sys.displayhook in "single" compilation mode.
    import sys

    _old_displayhook = getattr(sys, "displayhook", None)

    def _cc_displayhook(value) -> None:
        # `None` is not printed (matches CPython and lua.lua's "no results").
        if value is None:
            return
        try:
            sys.last_value = value
        except Exception:
            pass

        # Keep it simple and stable: repr() for now.
        text = repr(value)
        try:
            if term.is_color():
                prev = term.get_text_color()
                # Lua's pretty printer tends to render numbers in magenta/pink-ish tones.
                term.set_text_color(0x4)  # magenta
                term.write_wrapped(text)
                term.write_wrapped("\n")
                term.set_text_color(prev)
                return
        except Exception:
            pass

        term.write_wrapped(text)
        term.write_wrapped("\n")

    sys.displayhook = _cc_displayhook

    try:
        if term.is_color():
            term.set_text_color(0x10)
    except Exception:
        pass
    # Mirror Lua's `lua` REPL banner: concise and no extra hints.
    print("Interactive Python prompt.")
    print("Call exit() to exit.")
    try:
        term.set_text_color(0x1)
    except Exception:
        pass

    history: list[str] = []
    chunk_idx = 1
    buffer: list[str] = []

    while not stop[0]:
        prompt = PS2 if buffer else PS1
        line = await read_line(prompt, history)

        # Ignore an empty first line (matches skipping a blank primary prompt).
        if not buffer and not line.strip():
            continue

        buffer.append(line)
        source = "\n".join(buffer)
        filename = f"<python[{chunk_idx}]>"

        try:
            code = _compile_repl_command(source, filename)
        except (OverflowError, SyntaxError, ValueError) as e:
            printError("".join(traceback.format_exception_only(type(e), e)).rstrip())
            buffer.clear()
            continue

        if code is None:
            continue

        if source.strip() and (not history or history[-1] != source):
            history.append(source)

        buffer.clear()
        chunk_idx += 1

        try:
            # When top-level await is used, evaluating the code object produces an
            # awaitable. For normal statements, this returns None.
            maybe_awaitable = eval(code, repl_env, repl_env)
            if inspect.isawaitable(maybe_awaitable):
                await maybe_awaitable
        except BaseException as e:
            # Mirror Lua REPL: print just the error message for common control-flow interruptions.
            msg = ""
            try:
                msg = str(e.args[0]) if getattr(e, "args", None) else str(e)
            except Exception:
                msg = "Unknown error"

            if msg in ("Too long without yielding", "Terminated"):
                printError(msg)
            else:
                printError(traceback.format_exc().rstrip())

    # Restore host displayhook on exit.
    try:
        if _old_displayhook is not None:
            sys.displayhook = _old_displayhook
    except Exception:
        pass
