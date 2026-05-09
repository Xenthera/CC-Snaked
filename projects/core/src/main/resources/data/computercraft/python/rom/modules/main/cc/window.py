"""ComputerCraft ``window`` API for Python.

Direct port of ``rom/apis/window.lua``: a terminal redirect occupying a smaller
area of an existing terminal. Each window stores its content in three per-line
strings (``text``, ``fg``, ``bg``) and replays them onto the parent via
``parent.blit`` when redrawn.

Used by :mod:`rom.programs.advanced.multishell` to give each tab its own
terminal canvas.
"""

from cc import term as _term

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


def _parse_colour(colour):
    if not isinstance(colour, int):
        raise TypeError("Colour must be a number")
    if colour < 1 or colour > 0xFFFF:
        raise ValueError("Colour out of range")
    if colour in _HEX:
        return colour
    # Round to nearest power of two below.
    n = int(colour)
    while n & (n - 1):
        n &= n - 1
    return n


class Window:
    """Window terminal redirect (matches Lua ``window.create`` return value)."""

    def __init__(self, parent, x, y, width, height, start_visible=True):
        self._parent = parent
        self._x = int(x)
        self._y = int(y)
        self._width = int(width)
        self._height = int(height)
        self._visible = start_visible is not False

        self._cursor_x = 1
        self._cursor_y = 1
        self._cursor_blink = False
        self._text_colour = 1  # white
        self._bg_colour = 32768  # black

        self._build_empty_lines()

        self._lines = []
        for _ in range(self._height):
            self._lines.append(
                [self._empty_text, self._empty_lines[self._text_colour], self._empty_lines[self._bg_colour]]
            )

        if self._visible:
            self.redraw()

    # -- helpers --
    def _build_empty_lines(self):
        self._empty_text = " " * self._width
        self._empty_lines = {}
        for code in _HEX:
            self._empty_lines[code] = _HEX[code] * self._width

    def _redraw_line(self, n):
        line = self._lines[n - 1]
        self._parent.set_cursor_pos(self._x, self._y + n - 1)
        self._parent.blit(line[0], line[1], line[2])

    def _redraw(self):
        for n in range(1, self._height + 1):
            self._redraw_line(n)

    def _update_cursor_pos(self):
        cx, cy = self._cursor_x, self._cursor_y
        if 1 <= cx <= self._width and 1 <= cy <= self._height:
            self._parent.set_cursor_pos(self._x + cx - 1, self._y + cy - 1)
        else:
            self._parent.set_cursor_pos(0, 0)

    def _update_cursor_blink(self):
        self._parent.set_cursor_blink(self._cursor_blink)

    def _update_cursor_color(self):
        self._parent.set_text_color(self._text_colour)

    def _internal_blit(self, text, text_colour, bg_colour):
        n_start = self._cursor_x
        n_end = n_start + len(text) - 1
        if 1 <= self._cursor_y <= self._height:
            if n_start <= self._width and n_end >= 1:
                line = self._lines[self._cursor_y - 1]
                if n_start == 1 and n_end == self._width:
                    line[0] = text
                    line[1] = text_colour
                    line[2] = bg_colour
                else:
                    if n_start < 1:
                        clip_start = 1 - n_start  # 0-based start in the source string
                        clip_end = self._width - n_start + 1
                        ct = text[clip_start:clip_end]
                        cf = text_colour[clip_start:clip_end]
                        cb = bg_colour[clip_start:clip_end]
                        write_start = 1
                    elif n_end > self._width:
                        clip_end = self._width - n_start + 1
                        ct = text[:clip_end]
                        cf = text_colour[:clip_end]
                        cb = bg_colour[:clip_end]
                        write_start = n_start
                    else:
                        ct = text
                        cf = text_colour
                        cb = bg_colour
                        write_start = n_start

                    end = write_start + len(ct) - 1
                    old_t, old_f, old_b = line[0], line[1], line[2]
                    if write_start > 1:
                        new_t = old_t[: write_start - 1] + ct
                        new_f = old_f[: write_start - 1] + cf
                        new_b = old_b[: write_start - 1] + cb
                    else:
                        new_t = ct
                        new_f = cf
                        new_b = cb
                    if end < self._width:
                        new_t = new_t + old_t[end:]
                        new_f = new_f + old_f[end:]
                        new_b = new_b + old_b[end:]
                    line[0] = new_t
                    line[1] = new_f
                    line[2] = new_b

                if self._visible:
                    self._redraw_line(self._cursor_y)

        self._cursor_x = n_end + 1
        if self._visible:
            self._update_cursor_color()
            self._update_cursor_pos()

    # -- public API (Lua-style camelCase + snake_case) --
    def write(self, text):
        s = str(text)
        if not s:
            return
        fg = _HEX[self._text_colour] * len(s)
        bg = _HEX[self._bg_colour] * len(s)
        self._internal_blit(s, fg, bg)

    def write_wrapped(self, text):
        """Word-wrap variant of :meth:`write`, mirroring Lua's bios ``write``.

        Used by ``cc.term.write_wrapped`` (and therefore ``print``) when the
        current redirect is a Window. The native redirect delegates to the
        host ``cct.write``, which already wraps; we replicate that here for
        parity.
        """
        s = str(text)

        def _newline():
            cy = self._cursor_y
            if cy < self._height:
                self._cursor_x = 1
                self._cursor_y = cy + 1
            else:
                self._cursor_x = 1
                self.scroll(1)
            if self._visible:
                self._update_cursor_pos()

        i = 0
        n = len(s)
        w = self._width
        while i < n:
            # Whitespace run.
            j = i
            while j < n and s[j] in (" ", "\t"):
                j += 1
            if j > i:
                self.write(s[i:j])
                i = j
                if i >= n:
                    break

            # Newline.
            if s[i] == "\n":
                _newline()
                i += 1
                continue

            # Word.
            j = i
            while j < n and s[j] not in (" ", "\t", "\n"):
                j += 1
            word = s[i:j]
            i = j

            if len(word) > w:
                # Multi-line word: wrap at width.
                while word:
                    if self._cursor_x > w:
                        _newline()
                    avail = w - self._cursor_x + 1
                    chunk = word[:avail]
                    self.write(chunk)
                    word = word[avail:]
            else:
                if self._cursor_x + len(word) - 1 > w:
                    _newline()
                self.write(word)

    def blit(self, text, text_colour, bg_colour):
        text = str(text)
        text_colour = str(text_colour).lower()
        bg_colour = str(bg_colour).lower()
        if len(text_colour) != len(text) or len(bg_colour) != len(text):
            raise ValueError("Arguments must be the same length")
        self._internal_blit(text, text_colour, bg_colour)

    def clear(self):
        empty_text = self._empty_text
        empty_fg = self._empty_lines[self._text_colour]
        empty_bg = self._empty_lines[self._bg_colour]
        for y in range(self._height):
            self._lines[y][0] = empty_text
            self._lines[y][1] = empty_fg
            self._lines[y][2] = empty_bg
        if self._visible:
            self._redraw()
            self._update_cursor_color()
            self._update_cursor_pos()

    def clear_line(self):
        cy = self._cursor_y
        if 1 <= cy <= self._height:
            line = self._lines[cy - 1]
            line[0] = self._empty_text
            line[1] = self._empty_lines[self._text_colour]
            line[2] = self._empty_lines[self._bg_colour]
            if self._visible:
                self._redraw_line(cy)
                self._update_cursor_color()
                self._update_cursor_pos()

    def get_cursor_pos(self):
        return self._cursor_x, self._cursor_y

    def set_cursor_pos(self, x, y):
        self._cursor_x = int(x)
        self._cursor_y = int(y)
        if self._visible:
            self._update_cursor_pos()

    def set_cursor_blink(self, blink):
        self._cursor_blink = bool(blink)
        if self._visible:
            self._update_cursor_blink()

    def get_cursor_blink(self):
        return self._cursor_blink

    def is_color(self):
        return self._parent.is_color()

    is_colour = is_color

    def get_text_color(self):
        return self._text_colour

    get_text_colour = get_text_color

    def set_text_color(self, colour):
        self._text_colour = _parse_colour(colour)
        if self._visible:
            self._update_cursor_color()

    set_text_colour = set_text_color

    def get_background_color(self):
        return self._bg_colour

    get_background_colour = get_background_color

    def set_background_color(self, colour):
        self._bg_colour = _parse_colour(colour)

    set_background_colour = set_background_color

    def scroll(self, n):
        n = int(n)
        if n == 0:
            return
        new_lines = []
        empty_text = self._empty_text
        empty_fg = self._empty_lines[self._text_colour]
        empty_bg = self._empty_lines[self._bg_colour]
        for new_y in range(1, self._height + 1):
            y = new_y + n
            if 1 <= y <= self._height:
                new_lines.append(self._lines[y - 1])
            else:
                new_lines.append([empty_text, empty_fg, empty_bg])
        self._lines = new_lines
        if self._visible:
            self._redraw()
            self._update_cursor_color()
            self._update_cursor_pos()

    def get_size(self):
        return self._width, self._height

    def get_line(self, y):
        y = int(y)
        if y < 1 or y > self._height:
            raise IndexError("Line is out of range.")
        line = self._lines[y - 1]
        return line[0], line[1], line[2]

    def set_visible(self, visible):
        visible = bool(visible)
        if self._visible != visible:
            self._visible = visible
            if visible:
                self.redraw()

    def is_visible(self):
        return self._visible

    def redraw(self):
        if self._visible:
            self._redraw()
            self._update_cursor_blink()
            self._update_cursor_color()
            self._update_cursor_pos()

    def restore_cursor(self):
        if self._visible:
            self._update_cursor_blink()
            self._update_cursor_color()
            self._update_cursor_pos()

    def get_position(self):
        return self._x, self._y

    def reposition(self, new_x, new_y, new_width=None, new_height=None, new_parent=None):
        self._x = int(new_x)
        self._y = int(new_y)
        if new_parent is not None:
            self._parent = new_parent
        if new_width is not None and new_height is not None:
            new_width = int(new_width)
            new_height = int(new_height)
            old_width = self._width
            old_height = self._height
            old_lines = self._lines
            self._width = new_width
            self._height = new_height
            self._build_empty_lines()
            new_lines = []
            empty_text = self._empty_text
            empty_fg = self._empty_lines[self._text_colour]
            empty_bg = self._empty_lines[self._bg_colour]
            for y in range(1, new_height + 1):
                if y > old_height:
                    new_lines.append([empty_text, empty_fg, empty_bg])
                else:
                    old_line = old_lines[y - 1]
                    if new_width == old_width:
                        new_lines.append(old_line)
                    elif new_width < old_width:
                        new_lines.append([
                            old_line[0][:new_width],
                            old_line[1][:new_width],
                            old_line[2][:new_width],
                        ])
                    else:
                        pad_t = empty_text[old_width:new_width]
                        pad_f = empty_fg[old_width:new_width]
                        pad_b = empty_bg[old_width:new_width]
                        new_lines.append([
                            old_line[0] + pad_t,
                            old_line[1] + pad_f,
                            old_line[2] + pad_b,
                        ])
            self._lines = new_lines
        if self._visible:
            self.redraw()


def create(parent, x, y, width, height, start_visible=True):
    """Create a new window. Mirrors Lua ``window.create``."""
    if parent is None:
        parent = _term.current()
    return Window(parent, x, y, width, height, start_visible)
