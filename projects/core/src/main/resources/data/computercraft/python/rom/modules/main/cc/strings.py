"""String helpers (Python port of ``cc.strings``).

This is a small subset of the Lua module, focused on the helpers used by
shell, help, and other ROM programs.
"""


def wrap(text, width=None):
    """Wrap ``text`` into a list of lines, each at most ``width`` characters.

    Mirrors ``cc.strings.wrap``: words are separated by spaces; lines are not
    padded. ``width`` defaults to a value chosen by the caller; we use 50 if
    unset to match a typical CC computer width.
    """
    if width is None:
        width = 50
    width = int(width)
    if width <= 0:
        return [text]

    lines = []
    for paragraph in str(text).split("\n"):
        words = paragraph.split(" ")
        line = ""
        for word in words:
            if line == "":
                candidate = word
            else:
                candidate = line + " " + word
            if len(candidate) <= width:
                line = candidate
            else:
                if line != "":
                    lines.append(line)
                # If a single word exceeds width, hard-break it.
                while len(word) > width:
                    lines.append(word[:width])
                    word = word[width:]
                line = word
        lines.append(line)
    return lines


def ensure_width(line, width):
    """Pad or truncate ``line`` to exactly ``width`` characters.

    Mirrors ``cc.strings.ensure_width``.
    """
    width = int(width)
    if width <= 0:
        return ""
    s = str(line)
    if len(s) > width:
        return s[:width]
    return s + (" " * (width - len(s)))


def split(text, separator):
    """Split ``text`` on ``separator``; mirrors ``cc.strings.split``."""
    return str(text).split(str(separator))
