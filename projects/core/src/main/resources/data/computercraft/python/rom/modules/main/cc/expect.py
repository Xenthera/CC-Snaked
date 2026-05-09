"""Argument-checking helpers (Python port of ``cc.expect``).

Lua's ``cc.expect`` is a small library that adds typed argument checking to
Lua functions. Python already has its own type systems, but porting code
benefits from the same vocabulary, so we expose ``expect``/``field``/``range``
with similar semantics.
"""


def _type_names(types):
    types = [t for t in types if t != "nil" and t is not None]
    if not types:
        return "nil"
    if len(types) == 1:
        return str(types[0])
    return ", ".join(str(t) for t in types[:-1]) + " or " + str(types[-1])


def _matches(value, expected):
    if expected == "nil":
        return value is None
    if expected == "string":
        return isinstance(value, str)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "table":
        return isinstance(value, (dict, list, tuple))
    if expected == "function":
        return callable(value)
    return False


def expect(index, value, *types):
    """Verify ``value`` at argument position ``index`` matches one of ``types``.

    Mirrors Lua's ``cc.expect.expect``; raises ``TypeError`` if the value is
    not one of the allowed types.
    """
    for t in types:
        if _matches(value, t):
            return value
    type_names = _type_names(types)
    actual = type(value).__name__ if value is not None else "nil"
    raise TypeError("bad argument #{0} ({1} expected, got {2})".format(index, type_names, actual))


def field(table, key, *types):
    """Verify ``table[key]`` matches one of ``types``.

    Mirrors Lua's ``cc.expect.field``.
    """
    value = None
    if isinstance(table, dict):
        value = table.get(key)
    else:
        value = getattr(table, key, None)
    for t in types:
        if _matches(value, t):
            return value
    type_names = _type_names(types)
    actual = type(value).__name__ if value is not None else "nil"
    raise TypeError("bad field '{0}' ({1} expected, got {2})".format(key, type_names, actual))


def range(value, lower=None, upper=None):
    """Verify a numeric ``value`` is within an inclusive range.

    Mirrors Lua's ``cc.expect.range``.
    """
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise TypeError("bad argument (number expected)")
    if lower is not None and value < lower:
        raise ValueError("number out of range")
    if upper is not None and value > upper:
        raise ValueError("number out of range")
    return value
