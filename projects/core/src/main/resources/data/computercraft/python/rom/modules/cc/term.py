"""ComputerCraft ``term`` module for Python.

Thin Pythonic facade over the host ``cct`` bridge. Cursor positions are
1-based and colour codes are the power-of-two values used by Lua's
``colors`` table, matching :class:`dan200.computercraft.core.apis.TermMethods`.
"""


def write(text):
    cct.write(str(text))


def get_size():
    return cct.termGetWidth(), cct.termGetHeight()


def get_cursor_pos():
    return cct.termGetCursorX(), cct.termGetCursorY()


def set_cursor_pos(x, y):
    cct.termSetCursorPos(int(x), int(y))


def get_cursor_blink():
    return cct.termGetCursorBlink()


def set_cursor_blink(blink):
    cct.termSetCursorBlink(bool(blink))


def scroll(lines):
    cct.termScroll(int(lines))


def clear():
    cct.termClear()


def clear_line():
    cct.termClearLine()


def is_color():
    return cct.termIsColor()


is_colour = is_color


def get_text_color():
    return cct.termGetTextColor()


get_text_colour = get_text_color


def set_text_color(colour):
    cct.termSetTextColor(int(colour))


set_text_colour = set_text_color


def get_background_color():
    return cct.termGetBackgroundColor()


get_background_colour = get_background_color


def set_background_color(colour):
    cct.termSetBackgroundColor(int(colour))


set_background_colour = set_background_color
