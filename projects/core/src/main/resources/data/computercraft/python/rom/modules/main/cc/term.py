"""ComputerCraft ``term`` module for Python.

Mirrors Lua's ``term`` API, including the redirect stack:

- :func:`native` returns the host (real) terminal.
- :func:`current` returns the active redirect target.
- :func:`redirect` swaps the current redirect, returning the previous one.

Module-level functions dispatch through :func:`current`, so any object that
implements the ``term.Redirect`` shape (e.g. :class:`cc.window.Window`) can be
used as a target. This is the same model Lua uses (see ``rom/apis/term.lua``)
and is required for ``window``/``multishell`` to function.
"""

# Hex digits used for blit foreground/background colour strings, indexed by
# Lua-style power-of-two colour codes.
_HEX = {
    1: "0",       # white
    2: "1",       # orange
    4: "2",       # magenta
    8: "3",       # lightBlue
    16: "4",      # yellow
    32: "5",      # lime
    64: "6",      # pink
    128: "7",     # gray
    256: "8",     # lightGray
    512: "9",     # cyan
    1024: "a",    # purple
    2048: "b",    # blue
    4096: "c",    # brown
    8192: "d",    # green
    16384: "e",   # red
    32768: "f",   # black
}


def colour_to_blit(colour):
    """Return the hex digit Lua's ``term.blit`` uses for the given colour."""
    return _HEX.get(int(colour), "0")


toBlit = colour_to_blit


class _NativeRedirect:
    """Terminal redirect backed directly by the host bridge (``cct``).

    This is the equivalent of Lua's ``term.native()`` table.
    """

    def write(self, text):
        s = str(text)
        try:
            fn = getattr(cct, "termWrite")
        except Exception:
            fn = None
        if fn is None:
            cct.write(s)
        else:
            fn(s)

    def write_wrapped(self, text):
        cct.write(str(text))

    def blit(self, text, text_color, background_color):
        cct.termBlit(str(text), str(text_color), str(background_color))

    def get_size(self):
        return cct.termGetWidth(), cct.termGetHeight()

    def get_cursor_pos(self):
        return cct.termGetCursorX(), cct.termGetCursorY()

    def set_cursor_pos(self, x, y):
        cct.termSetCursorPos(int(x), int(y))

    def get_cursor_blink(self):
        return cct.termGetCursorBlink()

    def set_cursor_blink(self, blink):
        cct.termSetCursorBlink(bool(blink))

    def scroll(self, lines):
        cct.termScroll(int(lines))

    def clear(self):
        cct.termClear()

    def clear_line(self):
        cct.termClearLine()

    def is_color(self):
        return cct.termIsColor()

    is_colour = is_color

    def get_text_color(self):
        return cct.termGetTextColor()

    get_text_colour = get_text_color

    def set_text_color(self, colour):
        cct.termSetTextColor(int(colour))

    set_text_colour = set_text_color

    def get_background_color(self):
        return cct.termGetBackgroundColor()

    get_background_colour = get_background_color

    def set_background_color(self, colour):
        cct.termSetBackgroundColor(int(colour))

    set_background_colour = set_background_color


_native = _NativeRedirect()
_current = _native


def native():
    """Return the host-backed terminal redirect (Lua ``term.native``)."""
    return _native


def current():
    """Return the active terminal redirect (Lua ``term.current``)."""
    return _current


def redirect(target):
    """Switch the active redirect to ``target``, returning the previous one.

    Mirrors Lua ``term.redirect``: ``previous = term.redirect(new)``.
    """
    global _current
    if target is None:
        target = _native
    prev = _current
    _current = target
    return prev


def write(text):
    _current.write(text)


def write_wrapped(text):
    _current.write_wrapped(text)


def blit(text, text_color, background_color):
    _current.blit(text, text_color, background_color)


def get_size():
    return _current.get_size()


def get_cursor_pos():
    return _current.get_cursor_pos()


def set_cursor_pos(x, y):
    _current.set_cursor_pos(x, y)


def get_cursor_blink():
    return _current.get_cursor_blink()


def set_cursor_blink(blink):
    _current.set_cursor_blink(blink)


def scroll(lines):
    _current.scroll(lines)


def clear():
    _current.clear()


def clear_line():
    _current.clear_line()


def is_color():
    return _current.is_color()


is_colour = is_color


def get_text_color():
    return _current.get_text_color()


get_text_colour = get_text_color


def set_text_color(colour):
    _current.set_text_color(colour)


set_text_colour = set_text_color


def get_background_color():
    return _current.get_background_color()


get_background_colour = get_background_color


def set_background_color(colour):
    _current.set_background_color(colour)


set_background_colour = set_background_color
