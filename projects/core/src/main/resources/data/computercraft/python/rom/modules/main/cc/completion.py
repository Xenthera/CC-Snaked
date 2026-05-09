"""User-facing completion helpers (Python port of ``cc.completion``).

These are the building blocks Lua's read() uses to offer interactive
completion; we expose the same surface so ports of completion-aware programs
keep working.
"""


def _starts_with(text, value):
    return value.startswith(text)


def choice(text, choices, add_space=False):
    """Complete ``text`` against an explicit list of options.

    Mirrors ``cc.completion.choice``.
    """
    out = []
    for c in choices or ():
        c_str = str(c)
        if _starts_with(text, c_str) and len(c_str) > len(text):
            suffix = c_str[len(text):]
            if add_space:
                suffix += " "
            out.append(suffix)
    return out
