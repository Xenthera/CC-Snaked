"""Multishell tab manager (port of ``rom/programs/advanced/multishell.lua``).

Direct port of Lua's ``multishell`` program: maintains a list of processes, each
running in its own coroutine and rendered through a :class:`cc.window.Window`
covering the screen (or screen minus the menu bar). Mirrors the Lua program's
event routing (keyboard/paste/terminate go to the focused tab; mouse events
on row 1 toggle tab focus when the menu is visible; everything else is
broadcast to every tab).

The :data:`multishell` instance exported here is the same object that Lua's
program adds to each tab's environment; ``rom.programs.shell`` and individual
programs pick it up via ``cc.multishell.get_current_module()``.
"""

from __future__ import annotations

import inspect

from cc import os as ccos
from cc import term as ccterm
from cc import window as ccwindow
from cc import fs as ccfs


_NATIVE_TEXT_FG = 1            # white
_NATIVE_TEXT_BG = 32768        # black
_MENU_MAIN_FG = 16             # yellow on colour, white on mono
_MENU_MAIN_BG = 32768          # black
_MENU_OTHER_FG = 32768         # black
_MENU_OTHER_BG = 128           # gray


class _Process:
    """One multishell tab.

    The Lua original keeps ``co`` (a coroutine), ``window``, ``terminal`` (the
    redirect used while resuming), ``sTitle``, ``sFilter`` and ``bInteracted``.
    We mirror those fields directly.
    """

    __slots__ = (
        "title",
        "window",
        "terminal",
        "filter",
        "interacted",
        "coro",
        "dead",
        "result",
    )

    def __init__(self, title, window, coro):
        self.title = title
        self.window = window
        self.terminal = window
        self.filter = None
        self.interacted = False
        self.coro = coro
        self.dead = False
        self.result = None


class _Multishell:
    """Internal class implementing the multishell event loop and API table.

    A single instance is created when the program runs; ``cc.multishell``
    publishes a thin module-level facade onto whichever instance is current.
    """

    def __init__(self):
        self._parent = ccterm.current()
        self._w, self._h = self._parent.get_size()
        self._processes: list[_Process] = []
        self._current_process: int | None = None
        self._running_process: int | None = None
        self._show_menu = False
        self._windows_resized = False
        self._scroll_pos = 1
        self._scroll_right = False
        self._is_colour = False
        try:
            self._is_colour = self._parent.is_color()
        except Exception:
            self._is_colour = False
        if self._is_colour:
            self._menu_main_fg = 16  # yellow
            self._menu_main_bg = 32768  # black
            self._menu_other_fg = 32768  # black
            self._menu_other_bg = 128  # gray
        else:
            self._menu_main_fg = 1  # white
            self._menu_main_bg = 32768  # black
            self._menu_other_fg = 32768  # black
            self._menu_other_bg = 128  # gray

    # ---- internal helpers (mirrors Lua locals) ----

    def _select_process(self, n):
        if self._current_process != n:
            if self._current_process is not None:
                old = self._processes[self._current_process - 1]
                old.window.set_visible(False)
            self._current_process = n
            if n is not None:
                new = self._processes[n - 1]
                new.window.set_visible(True)

    def _set_process_title(self, n, title):
        self._processes[n - 1].title = title

    def _resume_process(self, n_process, event_name=None, *args):
        process = self._processes[n_process - 1]
        if process.dead:
            return
        # Filter logic (Lua: only resume when the filter matches or the event is
        # ``terminate``). ``event_name=None`` means we're starting/refreshing
        # the coroutine and should always send.
        if (
            event_name is not None
            and process.filter is not None
            and process.filter != event_name
            and event_name != "terminate"
        ):
            return
        previous = self._running_process
        self._running_process = n_process
        prev_term = ccterm.redirect(process.terminal)
        errored = False
        try:
            payload = (event_name, *args) if event_name is not None else None
            try:
                if payload is None:
                    result = process.coro.send(None)
                else:
                    result = process.coro.send(payload)
                process.filter = result if isinstance(result, str) else None
            except StopIteration as e:
                process.dead = True
                process.result = e.value
            except BaseException as e:
                process.dead = True
                process.result = e
                errored = True
                _print_error_to_window(process.terminal, str(e))
        finally:
            # The process may have redirected term internally; capture its
            # current redirect (Lua: ``tProcess.terminal = term.current()``)
            # so subsequent events go through the same target. Then restore
            # the multishell-level redirect.
            process.terminal = ccterm.current()
            ccterm.redirect(prev_term)
            self._running_process = previous

        # Lua: ``tProcess.bInteracted`` is set after char/key/key_up/paste/terminate.
        if event_name in ("char", "key", "key_up", "paste", "terminate"):
            process.interacted = True
        if errored:
            process.interacted = True
            process.title = "exited"

    def _launch_process(self, focus, env, program_path, *args):
        n = len(self._processes) + 1
        title = ccfs.get_name(str(program_path))
        if self._show_menu:
            window = ccwindow.create(self._parent, 1, 2, self._w, self._h - 1, False)
        else:
            window = ccwindow.create(self._parent, 1, 1, self._w, self._h, False)

        coro = _build_process_coro(self, n, env, program_path, list(args))
        process = _Process(title, window, coro)
        self._processes.append(process)
        if focus:
            self._select_process(n)
        self._resume_process(n)
        return n

    def _cull_process(self, n_process):
        process = self._processes[n_process - 1]
        if process.dead:
            if self._current_process == n_process:
                self._select_process(None)
            del self._processes[n_process - 1]
            if self._current_process is None:
                if n_process > 1:
                    self._select_process(n_process - 1)
                elif self._processes:
                    self._select_process(1)
            elif self._current_process > n_process:
                self._current_process -= 1
            if self._scroll_pos != 1:
                self._scroll_pos -= 1
            return True
        return False

    def _cull_processes(self):
        culled = False
        for n in range(len(self._processes), 0, -1):
            culled = self._cull_process(n) or culled
        return culled

    def _redraw_menu(self):
        if not self._show_menu:
            return
        parent = self._parent
        parent.set_cursor_pos(1, 1)
        parent.set_background_color(self._menu_other_bg)
        parent.clear_line()
        n_chars = 0
        n_size = parent.get_size()[0]
        if self._scroll_pos != 1:
            parent.set_text_color(self._menu_other_fg)
            parent.set_background_color(self._menu_other_bg)
            parent.write("<")
            n_chars = 1
        for n in range(self._scroll_pos, len(self._processes) + 1):
            if n == self._current_process:
                parent.set_text_color(self._menu_main_fg)
                parent.set_background_color(self._menu_main_bg)
            else:
                parent.set_text_color(self._menu_other_fg)
                parent.set_background_color(self._menu_other_bg)
            title = self._processes[n - 1].title
            parent.write(" " + title + " ")
            n_chars += len(title) + 2
        if n_chars > n_size:
            parent.set_text_color(self._menu_other_fg)
            parent.set_background_color(self._menu_other_bg)
            parent.set_cursor_pos(n_size, 1)
            parent.write(">")
            self._scroll_right = True
        else:
            self._scroll_right = False

        if self._current_process is not None:
            self._processes[self._current_process - 1].window.restore_cursor()

    def _resize_windows(self):
        if self._show_menu:
            window_y = 2
            window_height = self._h - 1
        else:
            window_y = 1
            window_height = self._h
        for proc in self._processes:
            cx, cy = proc.window.get_cursor_pos()
            if cy > window_height:
                proc.window.scroll(cy - window_height)
                proc.window.set_cursor_pos(cx, window_height)
            proc.window.reposition(1, window_y, self._w, window_height)
        self._windows_resized = True

    def _set_menu_visible(self, visible):
        if self._show_menu != visible:
            self._show_menu = visible
            self._resize_windows()
            self._redraw_menu()

    # ---- public API (Lua multishell.*) ----

    def get_focus(self):
        return self._current_process

    getFocus = get_focus

    def set_focus(self, n):
        n = int(n)
        if 1 <= n <= len(self._processes):
            self._select_process(n)
            self._redraw_menu()
            return True
        return False

    setFocus = set_focus

    def get_title(self, n):
        n = int(n)
        if 1 <= n <= len(self._processes):
            return self._processes[n - 1].title
        return None

    getTitle = get_title

    def set_title(self, n, title):
        n = int(n)
        if 1 <= n <= len(self._processes):
            self._set_process_title(n, str(title))
            self._redraw_menu()

    setTitle = set_title

    def get_current(self):
        return self._running_process

    getCurrent = get_current

    def launch(self, env, program_path, *args):
        prev_term = ccterm.current()
        self._set_menu_visible(len(self._processes) + 1 >= 2)
        result = self._launch_process(False, env or {}, str(program_path), *args)
        self._redraw_menu()
        ccterm.redirect(prev_term)
        return result

    def get_count(self):
        return len(self._processes)

    getCount = get_count

    # ---- main loop (Lua: while #tProcesses > 0) ----

    async def run(self):
        # Lua's bios runs ``parallel.waitForAny`` over multishell + rednet.run;
        # we have no parallel runner yet, so just run the multishell body.
        self._parent.clear()
        self._set_menu_visible(False)

        # Boot the initial shell tab using the same env Lua sets up.
        from cc import shell as _ccshell  # local import to avoid cycles

        shell_env = {
            "shell": _ccshell,
            "multishell": _module_facade,
        }
        self._launch_process(True, shell_env, "rom/programs/shell.py")

        while self._processes:
            try:
                event = await ccos.pull_event_raw()
            except ccos.Terminated:
                # Ctrl+T/user interrupt may be delivered via the BIOS trace hook
                # rather than as a normal "terminate" event. Treat it like Lua:
                # terminate the currently focused process, but keep multishell alive.
                if self._current_process is not None:
                    self._resume_process(self._current_process, "terminate")
                    if self._cull_process(self._current_process or 1):
                        self._set_menu_visible(len(self._processes) >= 2)
                        self._redraw_menu()
                    continue
                break
            if not event:
                continue
            name = event[0]
            args = event[1:]

            if name == "term_resize":
                self._w, self._h = self._parent.get_size()
                self._resize_windows()
                self._redraw_menu()
            elif name in ("char", "key", "key_up", "paste", "terminate", "file_transfer"):
                if self._current_process is not None:
                    self._resume_process(self._current_process, name, *args)
                    if self._cull_process(self._current_process or 1):
                        self._set_menu_visible(len(self._processes) >= 2)
                        self._redraw_menu()
            elif name == "mouse_click":
                button = args[0] if len(args) > 0 else 1
                x = args[1] if len(args) > 1 else 1
                y = args[2] if len(args) > 2 else 1
                if self._show_menu and y == 1:
                    if x == 1 and self._scroll_pos != 1:
                        self._scroll_pos -= 1
                        self._redraw_menu()
                    elif self._scroll_right and x == self._parent.get_size()[0]:
                        self._scroll_pos += 1
                        self._redraw_menu()
                    else:
                        tab_start = 1
                        if self._scroll_pos != 1:
                            tab_start = 2
                        for n in range(self._scroll_pos, len(self._processes) + 1):
                            tab_end = tab_start + len(self._processes[n - 1].title) + 1
                            if tab_start <= x <= tab_end:
                                self._select_process(n)
                                self._redraw_menu()
                                break
                            tab_start = tab_end + 1
                else:
                    if self._current_process is not None:
                        new_y = (y - 1) if self._show_menu else y
                        self._resume_process(self._current_process, name, button, x, new_y)
                        if self._cull_process(self._current_process or 1):
                            self._set_menu_visible(len(self._processes) >= 2)
                            self._redraw_menu()
            elif name in ("mouse_drag", "mouse_up", "mouse_scroll"):
                p1 = args[0] if len(args) > 0 else 0
                x = args[1] if len(args) > 1 else 1
                y = args[2] if len(args) > 2 else 1
                if self._show_menu and name == "mouse_scroll" and y == 1:
                    if p1 == -1 and self._scroll_pos != 1:
                        self._scroll_pos -= 1
                        self._redraw_menu()
                    elif self._scroll_right and p1 == 1:
                        self._scroll_pos += 1
                        self._redraw_menu()
                elif not (self._show_menu and y == 1):
                    if self._current_process is not None:
                        new_y = (y - 1) if self._show_menu else y
                        self._resume_process(self._current_process, name, p1, x, new_y)
                        if self._cull_process(self._current_process or 1):
                            self._set_menu_visible(len(self._processes) >= 2)
                            self._redraw_menu()
            else:
                # Other event: broadcast to every process.
                limit = len(self._processes)
                for n in range(1, limit + 1):
                    if n - 1 < len(self._processes):
                        self._resume_process(n, name, *args)
                if self._cull_processes():
                    self._set_menu_visible(len(self._processes) >= 2)
                    self._redraw_menu()

            if self._windows_resized:
                limit = len(self._processes)
                for n in range(1, limit + 1):
                    if n - 1 < len(self._processes):
                        self._resume_process(n, "term_resize")
                self._windows_resized = False
                if self._cull_processes():
                    self._set_menu_visible(len(self._processes) >= 2)
                    self._redraw_menu()

        # Lua: term.redirect(parentTerm) — restore the native redirect.
        ccterm.redirect(self._parent)


# Module-level multishell facade used by other ROM code (mirrors the Lua
# pattern of ``multishell`` being a global injected into each tab).
class _MultishellFacade:
    """Small wrapper that delegates to the active :class:`_Multishell`.

    When no multishell is running (i.e. mono-shell boot), all methods return
    ``None`` / ``False`` so callers can probe ``multishell`` safely.
    """

    def _impl(self):
        return _current_multishell

    def get_focus(self):
        impl = self._impl()
        return impl.get_focus() if impl else None

    getFocus = get_focus

    def set_focus(self, n):
        impl = self._impl()
        return impl.set_focus(n) if impl else False

    setFocus = set_focus

    def get_title(self, n):
        impl = self._impl()
        return impl.get_title(n) if impl else None

    getTitle = get_title

    def set_title(self, n, title):
        impl = self._impl()
        if impl:
            impl.set_title(n, title)

    setTitle = set_title

    def get_current(self):
        impl = self._impl()
        return impl.get_current() if impl else None

    getCurrent = get_current

    def launch(self, env, program_path, *args):
        impl = self._impl()
        if impl is None:
            return None
        return impl.launch(env, program_path, *args)

    def get_count(self):
        impl = self._impl()
        return impl.get_count() if impl else 0

    getCount = get_count


_current_multishell: _Multishell | None = None
_module_facade = _MultishellFacade()


def _print_error_to_window(window, message):
    try:
        prev_fg = window.get_text_color()
    except Exception:
        prev_fg = 1
    try:
        if window.is_color():
            window.set_text_color(0x4000)
    except Exception:
        pass
    try:
        window.write_wrapped(str(message) + "\n")
    except Exception:
        try:
            window.write(str(message))
        except Exception:
            pass
    try:
        window.set_text_color(prev_fg)
    except Exception:
        pass


def _build_process_coro(multishell, n_process, env, program_path, args):
    """Construct the coroutine object that backs a :class:`_Process`.

    Lua wraps this in a ``coroutine.create`` whose body calls ``os.run`` and
    then ``os.pullEvent("char")`` if the program never interacted with the
    user. Python uses an ``async`` function whose ``__await__`` yields the
    same way.
    """

    async def _coro():
        from cc import shell as _ccshell
        from cc.shell import Shell as _Shell

        prev_shell = _ccshell._current
        proc_shell = _Shell()
        _ccshell.set_current(proc_shell)
        try:
            try:
                # multishell.launch takes a *path* (Lua's os.run), not a shell
                # command. Bypass resolveProgram and run the file directly.
                path = str(program_path).lstrip("/\\")
                argv0 = ccfs.get_name(path)
                ok = await proc_shell._execute_program(100, path, [argv0, *[str(a) for a in args]])
                if not ok:
                    raise RuntimeError("No such program")
            except BaseException as e:
                # Mirror Lua semantics: if a program errors, it's considered
                # interacted with (so we don't show the continue prompt).
                try:
                    multishell._processes[n_process - 1].interacted = True
                except Exception:
                    pass
                _print_error_to_window(ccterm.current(), str(e))
            # Lua's "Press any key to continue" if the program never
            # interacted (i.e. did not call e.g. setCursorBlink/print/...).
            if not multishell._processes[n_process - 1].interacted:
                try:
                    ccterm.set_cursor_blink(False)
                except Exception:
                    pass
                try:
                    ccterm.write("Press any key to continue")
                except Exception:
                    pass
                try:
                    await ccos.pull_event("char")
                except Exception:
                    pass
        finally:
            _ccshell.set_current(prev_shell)

    coro_obj = _coro()
    return coro_obj


async def main(*_args):
    """Program entry point. Mirrors Lua's multishell boot sequence."""
    global _current_multishell
    impl = _Multishell()
    _current_multishell = impl
    try:
        await impl.run()
    finally:
        _current_multishell = None
