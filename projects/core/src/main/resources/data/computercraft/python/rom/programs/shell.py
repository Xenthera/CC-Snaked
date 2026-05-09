"""Interactive shell driver — layout tracks ``rom/programs/shell.lua``.

Lua tail structure:

1. **Argv mode** — ``shell.lua`` with CLI args runs ``shell.run(...)`` and exits.
   Startup is *not* run first (default PATH still includes ``rom/programs``).

2. **Interactive** — coloured ``print(os.version())``, then ``shell.run("/rom/startup.lua")``
   only when ``parentShell == nil``, then ``while not bExit`` with ``read()`` + ``shell.run(line)``.

Python maps (1)/(2) onto :func:`run`: argv branch first; interactive prints
:func:`cc.os.version`, runs ``rom/startup.py`` only for a top-level shell
(``shell._parent is None``), then the async prompt loop (standing in for ``read()``).

Program implementations live under ``rom/programs/``; API semantics live in
``cc.shell.Shell`` (parallel to Lua's ``shell`` API table).
"""

from cc import os as ccos
from cc import settings as ccsettings
from cc import shell as ccshell
from cc import term
import traceback


class ShellExit(Exception):
    pass


def _coerce_char(value) -> str:
    """Coerce a ComputerCraft ``char`` event arg into a 1-character string."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value[0:1]
    if isinstance(value, int):
        try:
            return chr(value)
        except ValueError:
            return ""
    try:
        items = list(value)
    except TypeError:
        return str(value)[0:1]
    if not items:
        return ""
    if len(items) == 1 and isinstance(items[0], int):
        try:
            return chr(items[0])
        except ValueError:
            return ""
    if all(isinstance(x, int) and 0 <= x <= 255 for x in items):
        try:
            return bytes(items).decode("utf-8", errors="ignore")[0:1]
        except Exception:
            return ""
    return str(value)[0:1]


def _prompt(cwd: str) -> str:
    return (cwd if cwd != "" else "") + "> "


def _write_line(text: str) -> None:
    term.write_wrapped(text)
    term.write_wrapped("\n")

def _write_traceback() -> None:
    term.write_wrapped(traceback.format_exc().rstrip())
    term.write_wrapped("\n")


def _shell_header() -> None:
    """Same role as Lua ``shell.lua`` coloured ``print(os.version())`` before the prompt."""
    try:
        term.set_background_color(0x8000)
        term.set_text_color(0x10)
        term.write(ccos.version())
        term.write_wrapped("\n")
        term.set_text_color(0x1)
    except Exception:
        _write_line(ccos.version())


def _error_message(e) -> str:
    msg = ""
    try:
        if getattr(e, "args", None):
            msg = str(e.args[0])
        else:
            msg = str(e)
    except Exception:
        msg = "Unknown error"
    if "LuaException:" in msg:
        msg = msg.split("LuaException:", 1)[1].strip()
    if "\n" in msg:
        msg = msg.split("\n", 1)[0].strip()
    return msg or "Unknown error"


async def _read_line(shell: ccshell.Shell, history: list) -> str:
    """Line editor matching Lua ``bios.lua`` ``read()`` completion semantics.

    The prompt uses :meth:`cc.shell.Shell.dir` on each redraw so it stays aligned with
    ``shell.dir() .. "> "`` (see Lua ``shell.lua`` ``show_prompt``).

    Completions are **suffix strings** shown as ghost text after the cursor when the
    cursor is at the **end** of the line (same as ``nPos == #sLine`` in Lua).
    **Tab** and **Right** (at end) accept the current ghost suffix; **Up/Down** cycle
    ghost candidates when completions are active (same precedence as Lua over history).
    """

    buf: list = []
    cursor = 0
    hist_idx = None
    completions = None  # Optional[list[str]] — ghost suffix list from shell.complete
    comp_idx = 0

    term.set_cursor_blink(True)
    prompt = _prompt(shell.dir())
    start_x, start_y = term.get_cursor_pos()
    term.write(prompt)
    last_drawn = len(prompt)

    def line_str() -> str:
        return "".join(buf)

    def recomplete() -> None:
        """Mirror Lua ``recomplete``: only when cursor at line end and autocomplete on."""
        nonlocal completions, comp_idx
        if not ccsettings.get("shell.autocomplete"):
            completions = None
            return
        if cursor != len(buf):
            completions = None
            return
        try:
            suf = ccshell.complete(line_str())
        except BaseException:
            completions = None
            return
        if suf:
            lst = list(suf)
            if lst:
                completions = lst
                comp_idx = 0
            else:
                completions = None
        else:
            completions = None

    def redraw() -> None:
        nonlocal prompt
        nonlocal last_drawn
        prompt = _prompt(shell.dir())
        term.set_cursor_pos(start_x, start_y)
        # Don't use clear_line(): it clears the whole row, including anything before our prompt.
        term.write(" " * max(0, last_drawn))
        term.set_cursor_pos(start_x, start_y)
        # Lua shell renders the prompt in yellow (on colour terminals).
        try:
            old_fg = term.get_text_color()
            if term.is_color():
                term.set_text_color(0x10)  # yellow
            term.write(prompt)
            if term.is_color():
                term.set_text_color(0x1)  # white
        except BaseException:
            term.write(prompt)
        text = line_str()
        term.write(text)

        ghost = ""
        if completions is not None and cursor == len(buf) and len(completions) > 0:
            ghost = completions[comp_idx % len(completions)]

        if ghost:
            try:
                old_fg = term.get_text_color()
                old_bg = term.get_background_color()
                if term.is_color():
                    term.set_text_color(1)
                    term.set_background_color(128)
                term.write(ghost)
                term.set_text_color(old_fg)
                term.set_background_color(old_bg)
            except BaseException:
                term.write(ghost)

        last_drawn = len(prompt) + len(text) + (len(ghost) if ghost else 0)
        cx = start_x + len(prompt) + cursor
        term.set_cursor_pos(cx, start_y)

    def accept_completion() -> None:
        nonlocal cursor, completions, comp_idx
        if not completions:
            return
        suf = completions[comp_idx % len(completions)]
        buf.extend(list(suf))
        cursor = len(buf)
        completions = None
        comp_idx = 0
        recomplete()

    recomplete()
    redraw()

    while True:
        ev = await ccos.pull_event_raw()
        if not ev:
            continue

        name = ev[0]
        if name == "terminate":
            term.set_cursor_blink(False)
            raise ShellExit()

        if name == "char" and len(ev) >= 2:
            ch = _coerce_char(ev[1])
            buf[cursor:cursor] = [ch]
            cursor += 1
            hist_idx = None
            recomplete()
            redraw()
            continue

        if name == "paste" and len(ev) >= 2:
            text = str(ev[1])
            buf[cursor:cursor] = list(text)
            cursor += len(text)
            hist_idx = None
            recomplete()
            redraw()
            continue

        if name == "file_transfer":
            completions = None
            redraw()
            continue

        if name == "term_resize":
            redraw()
            continue

        if name == "key" and len(ev) >= 2:
            key = ev[1]
            if key == 258:  # tab — accept ghost suffix (Lua ``acceptCompletion``)
                accept_completion()
                redraw()
                continue
            if key == 263:  # left
                if cursor > 0:
                    cursor -= 1
                    recomplete()
                    redraw()
                continue
            if key == 262:  # right — accept completion when at end (Lua), else move
                if cursor == len(buf) and completions:
                    accept_completion()
                    redraw()
                elif cursor < len(buf):
                    cursor += 1
                    recomplete()
                    redraw()
                continue
            if key == 268:  # home
                if cursor > 0:
                    cursor = 0
                    recomplete()
                    redraw()
                continue
            if key == 269:  # end
                if cursor < len(buf):
                    cursor = len(buf)
                    recomplete()
                    redraw()
                continue
            if key == 261:  # delete
                if cursor < len(buf):
                    del buf[cursor]
                    hist_idx = None
                    recomplete()
                    redraw()
                continue
            if key == 259:  # backspace
                if cursor > 0:
                    cursor -= 1
                    del buf[cursor]
                    hist_idx = None
                    recomplete()
                    redraw()
                continue
            if key == 265:  # up — completion cycle takes precedence over history (Lua)
                if completions:
                    comp_idx = (comp_idx - 1) % len(completions)
                    redraw()
                    continue
                if history:
                    if hist_idx is None:
                        hist_idx = len(history) - 1
                    else:
                        hist_idx = max(0, hist_idx - 1)
                    buf[:] = list(history[hist_idx])
                    cursor = len(buf)
                    recomplete()
                    redraw()
                continue
            if key == 264:  # down
                if completions:
                    comp_idx = (comp_idx + 1) % len(completions)
                    redraw()
                    continue
                if history and hist_idx is not None:
                    if hist_idx >= len(history) - 1:
                        hist_idx = None
                        new_val = ""
                    else:
                        hist_idx += 1
                        new_val = history[hist_idx]
                    buf[:] = list(new_val)
                    cursor = len(buf)
                    recomplete()
                    redraw()
                continue
            if key == 257 or key == 335:  # enter / numPadEnter (``keys.lua``)
                completions = None
                redraw()  # repaint line without ghost before newline (bios.lua sequence)
                term.write_wrapped("\n")
                term.set_cursor_blink(False)
                return line_str()


async def run(argv=None) -> None:
    """Entry point for the ROM shell program (see module docstring vs Lua ``shell.lua``)."""
    shell = ccshell._current
    if shell is None:
        shell = ccshell.Shell()
        ccshell.set_current(shell)

    if argv is None:
        argv = []

    # multishell: set this tab's title to "shell" (Lua: ``multishell.setTitle(multishell.getCurrent(), "shell")``).
    try:
        from cc import multishell as _ccmultishell

        if _ccmultishell.is_active():
            current_id = _ccmultishell.get_current()
            if current_id is not None:
                _ccmultishell.set_title(current_id, "shell")
    except Exception:
        pass

    # --- Argv mode (Lua: ``if #tArgs > 0 then shell.run(...) end``) — no startup yet ---
    if argv:
        try:
            ok = await shell.run(*argv)
            if not ok:
                _write_line("No such program")
        except BaseException as e:
            if ccos.is_terminated(e):
                return
            if ccsettings.get("python.tracebacks"):
                _write_traceback()
            else:
                _write_line(_error_message(e))
        return

    # --- Interactive mode ---
    _shell_header()

    # Lua: ``if parentShell == nil then shell.run("/rom/startup.lua") end``
    if getattr(shell, "_parent", None) is None:
        try:
            from rom import startup as _startup

            await _startup.run(shell)
        except Exception as e:
            _write_line("startup error: " + _error_message(e))

    history: list = []

    try:
        while True:
            line = await _read_line(shell, history)
            if not line.strip():
                continue
            if not history or history[-1] != line:
                history.append(line)
            # Lua: ``multishell.setTitle(getCurrent(), tWords[1])`` while running, then back to "shell".
            _ms_title = None
            try:
                from cc import multishell as _ccmultishell

                if _ccmultishell.is_active():
                    current_id = _ccmultishell.get_current()
                    if current_id is not None:
                        words = ccshell.tokenise(line)
                        if words:
                            _ms_title = current_id
                            _ccmultishell.set_title(current_id, words[0])
            except Exception:
                _ms_title = None
            try:
                ok = await shell.run(line)
                if not ok:
                    _write_line("No such program")
            except ShellExit:
                raise
            except BaseException as e:
                try:
                    if ccos.is_terminated(e):
                        continue
                except Exception:
                    pass
                if ccsettings.get("python.tracebacks"):
                    _write_traceback()
                else:
                    _write_line(_error_message(e))
            finally:
                if _ms_title is not None:
                    try:
                        from cc import multishell as _ccmultishell

                        _ccmultishell.set_title(_ms_title, "shell")
                    except Exception:
                        pass

            if shell.should_exit():
                return
    except ShellExit:
        return


async def main(*args) -> None:
    """Entry point invoked when shell.py is launched through ``Shell.execute``.

    The bios calls ``run([])`` directly; multishell-launched tabs go through
    ``shell.execute`` which only awaits a coroutine named ``main``. This
    delegates straight into :func:`run` so both pathways behave identically.
    """
    await run(list(args))
