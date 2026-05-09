"""Minimal full-screen text editor (port of ``rom/programs/edit.lua``).

Line-oriented buffer, arrow navigation, Tab inserts spaces, Enter splits/joins
lines. Ctrl+S saves (when writable), Ctrl+Q quits (prompts if there are unsaved
changes). No syntax highlighting or menus yet.
"""

from __future__ import annotations

import io
import keyword
import tokenize

from cc import os as ccos
from cc import settings as ccsettings
from cc.line_reader import read_line
from cc.internal import menu as _menu


def _coerce_char(value):
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


def _mkdir_chain(dir_path: str) -> None:
    if not dir_path or fs.exists(dir_path):
        return
    parent = fs.get_dir(dir_path)
    if parent:
        _mkdir_chain(parent)
    fs.make_dir(dir_path)


async def main(*_args) -> None:
    if len(arg) < 2:
        pname = arg[0] if arg else "edit"
        print("Usage: " + pname + " <path>")
        return

    s_path = shell.resolve(arg[1])
    read_only = fs.is_read_only(s_path)
    if fs.exists(s_path) and fs.is_dir(s_path):
        printError("Cannot edit a directory.")
        return

    if not fs.exists(s_path) and "." not in fs.get_name(s_path):
        ext = ccsettings.get("edit.default_extension")
        if ext not in (None, "") and isinstance(ext, str):
            s_path = s_path + "." + ext

    w, th = term.get_size()
    edit_h = max(1, th - 1)

    space_check = s_path if fs.exists(s_path) else (fs.get_dir(s_path) or ".")
    status_ok = True
    if read_only:
        status_msg = "File is read only"
        status_ok = False
    elif fs.exists(space_check) and fs.get_free_space(space_check) < 1024:
        status_msg = "Disk is low on space"
        status_ok = False
    else:
        msg = "Press Ctrl or click here to access menu" if term.is_color() else "Press Ctrl to access menu"
        if len(msg) > w - 5:
            msg = "Press Ctrl for menu"
        status_msg = msg

    lines: list[str]
    if fs.exists(s_path) and not fs.is_dir(s_path):
        raw = fs.read_all(s_path)
        lines = str(raw).replace("\r\n", "\n").replace("\r", "\n").split("\n")
    else:
        lines = [""]

    dirty = False
    cy = 0
    cx = 0
    first_line = 0
    col_off = 0

    # --- Syntax highlighting (match edit.lua categories/colours, Python-specific) ---
    is_colour = False
    try:
        is_colour = term.is_color()
    except Exception:
        is_colour = False

    # CC colour indices -> hex digits for blit strings:
    # white=0, yellow=4, magenta=2, green=d, red=e, black=f.
    _FG_TEXT = "0"
    _FG_KEYWORD = "4"
    _FG_STRING = "e"
    _FG_COMMENT = "d"
    _FG_NUMBER = "2"
    _BG_DEFAULT = "f"

    line_colours: list[str] = [""] * len(lines)

    def _rehighlight_all() -> None:
        """Compute per-line colour strings, using Python's tokenizer.

        This mirrors edit.lua's approach: tokenise source, then colour based on token type.
        """
        nonlocal line_colours
        if not is_colour:
            return

        # Start with everything as plain text colour.
        cols = [list(_FG_TEXT * len(line)) for line in lines]

        def paint(srow: int, scol: int, erow: int, ecol: int, fg: str) -> None:
            # Token positions are 1-based lines, 0-based columns.
            srow -= 1
            erow -= 1
            if srow < 0:
                srow = 0
                scol = 0
            if erow >= len(cols):
                erow = len(cols) - 1
                ecol = len(cols[erow]) if erow >= 0 else 0
            if srow > erow or srow >= len(cols) or erow < 0:
                return

            if srow == erow:
                row = cols[srow]
                for i in range(max(0, scol), min(ecol, len(row))):
                    row[i] = fg
                return

            # First row
            row = cols[srow]
            for i in range(max(0, scol), len(row)):
                row[i] = fg
            # Middle rows
            for r in range(srow + 1, erow):
                row = cols[r]
                for i in range(0, len(row)):
                    row[i] = fg
            # Last row
            row = cols[erow]
            for i in range(0, min(ecol, len(row))):
                row[i] = fg

        text = "\n".join(lines)
        try:
            for tok in tokenize.generate_tokens(io.StringIO(text).readline):
                ttype, tstr, (srow, scol), (erow, ecol), _ = tok
                if ttype == tokenize.STRING:
                    paint(srow, scol, erow, ecol, _FG_STRING)
                elif ttype == tokenize.COMMENT:
                    paint(srow, scol, erow, ecol, _FG_COMMENT)
                elif ttype == tokenize.NUMBER:
                    paint(srow, scol, erow, ecol, _FG_NUMBER)
                elif ttype == tokenize.NAME and keyword.iskeyword(tstr):
                    paint(srow, scol, erow, ecol, _FG_KEYWORD)
        except Exception:
            # If tokenization fails (incomplete strings, etc.), keep whatever we have: plain text.
            pass

        line_colours = ["".join(row) for row in cols]

    _rehighlight_all()

    def clamp_scroll() -> None:
        nonlocal first_line, col_off
        if cy < first_line:
            first_line = cy
        if cy >= first_line + edit_h:
            first_line = cy - edit_h + 1
        if cx < col_off:
            col_off = cx
        if cx >= col_off + w:
            col_off = cx - w + 1

    current_menu = None
    menu_items: list[str] = []
    if not read_only:
        menu_items.append("Save")
    # Present but not functional until tab support exists (per request).
    menu_items.append("Run")
    menu_items.append("Exit")

    def _set_status(text: str, ok: bool = True) -> None:
        nonlocal status_msg, status_ok
        status_msg = str(text)
        status_ok = bool(ok)

    def set_cursor(new_cx: int, new_cy: int) -> None:
        nonlocal cx, cy
        cy = max(0, min(int(new_cy), len(lines) - 1))
        cx = max(0, min(int(new_cx), len(lines[cy])))
        redraw()

    def redraw() -> None:
        nonlocal w, th, edit_h
        w, th = term.get_size()
        edit_h = max(1, th - 1)
        clamp_scroll()
        for row in range(1, edit_h + 1):
            term.set_cursor_pos(1, row)
            term.clear_line()
            idx = first_line + row - 1
            if idx < len(lines):
                # Avoid writing the last column to prevent wrapping into the status bar.
                vis_w = max(0, w - 1)
                piece = lines[idx][col_off : col_off + vis_w]
                if is_colour and piece:
                    cols = (line_colours[idx] or "")[col_off : col_off + vis_w]
                    if len(cols) < len(piece):
                        cols = cols + (_FG_TEXT * (len(piece) - len(cols)))
                    term.blit(piece, cols[: len(piece)], _BG_DEFAULT * len(piece))
                else:
                    term.write(piece)

        # --- Status/menu bar (last line), matching Lua edit.lua layout ---
        term.set_cursor_pos(1, th)
        term.clear_line()
        if current_menu is not None:
            _menu.draw(current_menu)
        else:
            try:
                if term.is_color():
                    term.set_text_color(0x10 if status_ok else 0x4000)
            except Exception:
                pass
            msg = status_msg
            # Avoid writing the last column to prevent wrapping into the next row.
            term.write(msg[: max(0, w - 1)])
            try:
                term.set_text_color(0x1)
            except Exception:
                pass

        # Line numbers on the right ("Ln <y>")
        ln = f"Ln {cy + 1}"
        term.set_cursor_pos(w - len(ln) + 1, th)
        try:
            term.set_text_color(0x10)  # yellow
        except Exception:
            pass
        term.write("Ln ")
        try:
            term.set_text_color(0x1)  # white
        except Exception:
            pass
        term.write(str(cy + 1))

        term.set_cursor_blink(current_menu is None)

        sy = cy - first_line + 1
        sx = cx - col_off + 1
        term.set_cursor_pos(min(max(1, sx), w), min(max(1, sy), edit_h))

    term.set_cursor_blink(True)
    term.clear()
    redraw()

    async def try_save() -> bool:
        nonlocal dirty
        if read_only:
            _set_status("Access denied", False)
            return False
        try:
            parent = fs.get_dir(s_path)
            if parent:
                _mkdir_chain(parent)
            # Lua writes each line with a trailing newline.
            fs.write_all(s_path, "\n".join(lines) + "\n")
            dirty = False
            _set_status("Saved to " + s_path, True)
            return True
        except Exception as e:
            _set_status("Error saving: " + str(e), False)
            return False

    async def confirm(msg: str) -> bool:
        term.write_wrapped("\n")
        line = await read_line(msg + " [y/N]: ", [])
        return line.strip().lower().startswith("y")

    async def run_buffer() -> None:
        # Mirrors ``edit.lua``'s ``Run`` menu: launch a new multishell tab whose
        # program is ``cc.internal.edit_runner`` driving the current buffer.
        try:
            from cc import multishell as _ccmultishell
            from cc.internal import edit_runner as _runner
        except Exception:
            _set_status("Error starting Task", False)
            return

        if not _ccmultishell.is_active():
            _set_status("Run requires multishell", False)
            return

        title = fs.get_name(s_path)
        contents = "\n".join(lines)
        token = _runner.submit_request(title, s_path, contents)

        try:
            tab_id = _ccmultishell.launch({}, "rom/programs/edit_runner.py", str(token))
            if tab_id is None:
                _runner.pop_request(token)
                _set_status("Error starting Task", False)
                return
            _ccmultishell.set_focus(tab_id)
            _ccmultishell.set_title(tab_id, title)
        except Exception as e:
            _runner.pop_request(token)
            _set_status("Error starting Task: " + str(e), False)

    running = True
    while running:
        ev = await ccos.pull_event_raw()
        if not ev:
            continue
        et = ev[0]

        if et == "term_resize":
            redraw()
            continue

        if current_menu is not None:
            res = _menu.handle_event(current_menu, et, *ev[1:])
            if res is False:
                current_menu = None
                redraw()
                continue
            if isinstance(res, str):
                choice = res
                current_menu = None
                redraw()
                if choice == "Save":
                    await try_save()
                elif choice == "Run":
                    await run_buffer()
                elif choice == "Exit":
                    running = False
                redraw()
                continue

        if et == "char" and len(ev) >= 2:
            ch = _coerce_char(ev[1])
            oc = ord(ch) if ch else -1
            # Ctrl+S save, Ctrl+Q quit (ASCII controls).
            if oc == 19:
                await try_save()
                redraw()
                continue
            if oc == 17:
                if dirty:
                    term.write_wrapped("\n")
                    if read_only:
                        if not await confirm("Discard changes?"):
                            redraw()
                            continue
                    else:
                        if await confirm("Save before quitting?"):
                            await try_save()
                running = False
                break
            if oc < 32 and oc not in (-1, 9):
                redraw()
                continue
            if oc == 9:
                ins = "    "
            else:
                ins = ch
            line = lines[cy]
            lines[cy] = line[:cx] + ins + line[cx:]
            cx += len(ins)
            dirty = True
            _rehighlight_all()
            redraw()
            continue

        if et == "paste" and len(ev) >= 2:
            ins = str(ev[1]).replace("\r\n", "\n").replace("\r", "\n")
            parts = ins.split("\n")
            start_line = cy
            line = lines[cy]
            lines[cy] = line[:cx] + parts[0] + line[cx:]
            cx += len(parts[0])
            for extra in parts[1:]:
                cy += 1
                lines.insert(cy, extra)
                line_colours.insert(cy, "")
                cx = len(extra)
            dirty = True
            _rehighlight_all()
            redraw()
            continue

        if et == "key" and len(ev) >= 2:
            key = ev[1]
            # Ctrl opens menu (Lua: keys.leftCtrl/rightCtrl)
            if key == 341 or key == 345:
                current_menu = _menu.create(menu_items)
                redraw()
                continue

            if key == 257 or key == 335:
                # Newline with indentation (Lua edit.lua preserves leading spaces).
                line = lines[cy]
                rest = line[cx:]
                left = line[:cx]
                indent = 0
                for ch in left:
                    if ch == " ":
                        indent += 1
                    else:
                        break
                lines[cy] = left
                cy += 1
                lines.insert(cy, (" " * indent) + rest)
                cx = indent
                dirty = True
                line_colours.insert(cy, "")
                _rehighlight_all()
                redraw()
                continue
            if key == 259:
                if cx > 0:
                    line = lines[cy]
                    # If at the start of indentation, delete 4 spaces at once.
                    if cx >= 4 and line[cx - 4 : cx] == "    " and line[:cx].strip() == "":
                        lines[cy] = line[: cx - 4] + line[cx:]
                        cx -= 4
                        dirty = True
                        _rehighlight_all()
                        redraw()
                        continue
                    lines[cy] = line[: cx - 1] + line[cx:]
                    cx -= 1
                    dirty = True
                    _rehighlight_all()
                elif cy > 0:
                    prev = lines[cy - 1]
                    cur = lines.pop(cy)
                    del line_colours[cy]
                    cy -= 1
                    cx = len(prev)
                    lines[cy] = prev + cur
                    dirty = True
                    _rehighlight_all()
                redraw()
                continue
            if key == 261:
                line = lines[cy]
                if cx < len(line):
                    lines[cy] = line[:cx] + line[cx + 1 :]
                    dirty = True
                    _rehighlight_all()
                elif cy < len(lines) - 1:
                    nxt = lines.pop(cy + 1)
                    del line_colours[cy + 1]
                    lines[cy] = line + nxt
                    dirty = True
                    _rehighlight_all()
                redraw()
                continue
            if key == 263:
                if cx > 0:
                    cx -= 1
                elif cy > 0:
                    cy -= 1
                    cx = len(lines[cy])
                redraw()
                continue
            if key == 262:
                line = lines[cy]
                if cx < len(line):
                    cx += 1
                elif cy < len(lines) - 1:
                    cy += 1
                    cx = 0
                redraw()
                continue
            if key == 265 and cy > 0:
                cy -= 1
                cx = min(cx, len(lines[cy]))
                redraw()
                continue
            if key == 264 and cy < len(lines) - 1:
                cy += 1
                cx = min(cx, len(lines[cy]))
                redraw()
                continue
            if key == 268:
                cx = 0
                redraw()
                continue
            if key == 269:
                cx = len(lines[cy])
                redraw()
                continue
            if key == 266 and first_line > 0:
                first_line = max(0, first_line - edit_h)
                redraw()
                continue
            if key == 267 and first_line + edit_h < len(lines):
                first_line = min(len(lines) - 1, first_line + edit_h)
                redraw()
                continue

        if et == "mouse_click" and len(ev) >= 4:
            button = ev[1]
            mx = int(ev[2])
            my = int(ev[3])
            if button == 1:
                # Click on bottom row opens menu.
                if my == th:
                    current_menu = _menu.create(menu_items)
                    redraw()
                    continue
                # Click in editor area moves cursor.
                new_cy = first_line + (my - 1)
                new_cy = max(0, min(new_cy, len(lines) - 1))
                new_cx = col_off + (mx - 1)
                new_cx = max(0, min(new_cx, len(lines[new_cy])))
                set_cursor(new_cx, new_cy)
            continue

        if et == "mouse_scroll" and len(ev) >= 2:
            direction = int(ev[1])
            # Lua: -1 up, 1 down.
            if direction == -1:
                if first_line > 0:
                    first_line -= 1
                    redraw()
            elif direction == 1:
                max_scroll = max(0, len(lines) - edit_h)
                if first_line < max_scroll:
                    first_line += 1
                    redraw()
            continue

    # Cleanup (match Lua edit.lua)
    term.clear()
    term.set_cursor_blink(False)
    term.set_cursor_pos(1, 1)
