"""Minimal plain line reader (no completion ghost).

Used by :program:`rom/programs/python` REPL and similar tools. Mirrors the subset
of ``bios.lua`` ``read()`` handling needed for interactive prompts without pulling
in shell completion.
"""

from cc import os as ccos
from cc import term


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


async def read_line(prompt: str, history: list) -> str:
    """Blocking async line read with history (↑/↓). Enter / numpad enter submit."""
    buf = []
    cursor = 0
    hist_idx = None

    term.set_cursor_blink(True)
    start_x, start_y = term.get_cursor_pos()
    term.write(prompt)
    last_drawn = len(prompt)

    def redraw():
        nonlocal last_drawn
        term.set_cursor_pos(start_x, start_y)
        # Do not use clear_line(): it clears the whole row, including anything to the left of our prompt.
        # Lua's bios.read() instead overwrites just the input area.
        term.write(" " * max(0, last_drawn))
        term.set_cursor_pos(start_x, start_y)
        term.write(prompt)
        text = "".join(buf)
        term.write(text)
        last_drawn = len(prompt) + len(text)
        cx = start_x + len(prompt) + cursor
        term.set_cursor_pos(cx, start_y)

    redraw()

    while True:
        ev = await ccos.pull_event_raw()
        if not ev:
            continue
        name = ev[0]

        if name == "char" and len(ev) >= 2:
            buf[cursor:cursor] = [_coerce_char(ev[1])]
            cursor += 1
            hist_idx = None
            redraw()
            continue

        if name == "paste" and len(ev) >= 2:
            text = str(ev[1])
            buf[cursor:cursor] = list(text)
            cursor += len(text)
            hist_idx = None
            redraw()
            continue

        if name == "term_resize":
            redraw()
            continue

        if name == "key" and len(ev) >= 2:
            key = ev[1]
            if key == 257 or key == 335:
                term.write_wrapped("\n")
                term.set_cursor_blink(False)
                return "".join(buf)
            if key == 263 and cursor > 0:
                cursor -= 1
                redraw()
                continue
            if key == 262 and cursor < len(buf):
                cursor += 1
                redraw()
                continue
            if key == 268:
                cursor = 0
                redraw()
                continue
            if key == 269:
                cursor = len(buf)
                redraw()
                continue
            if key == 261 and cursor < len(buf):
                del buf[cursor]
                redraw()
                continue
            if key == 259 and cursor > 0:
                cursor -= 1
                del buf[cursor]
                redraw()
                continue
            if key == 265 and history:
                if hist_idx is None:
                    hist_idx = len(history) - 1
                else:
                    hist_idx = max(0, hist_idx - 1)
                buf[:] = list(history[hist_idx])
                cursor = len(buf)
                redraw()
                continue
            if key == 264 and history and hist_idx is not None:
                if hist_idx >= len(history) - 1:
                    hist_idx = None
                    buf[:] = []
                else:
                    hist_idx += 1
                    buf[:] = list(history[hist_idx])
                cursor = len(buf)
                redraw()
                continue
