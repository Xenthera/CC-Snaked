"""ComputerCraft ``os`` module for Python.

Mirrors the most-used parts of Lua's ``os`` API. Names are snake_case to be
idiomatic Python; the underlying semantics (event filtering, timer ticks,
``terminate`` translating into an exception) match the Lua side so that
behavior is consistent across language runtimes.

The host runtime (``cct``) is bound at module-import time by ``PythonMachine``.
"""


class Terminated(Exception):
    """Raised by :func:`pull_event` when a ``terminate`` event is dispatched."""


def is_terminated(exc):
    """True if ``exc`` is a Ctrl+T / ``terminate`` stop (including Graal duplicate types)."""
    if isinstance(exc, Terminated):
        return True
    try:
        if type(exc).__name__ == "Terminated":
            return True
    except Exception:
        pass
    try:
        s = str(exc)
    except Exception:
        return False
    return s in ("Terminated", "Terminated: Terminated")


class _AwaitEvent:
    # The host scheduler advances the BIOS coroutine by sending event tuples back
    # in. Yielding the desired filter (or ``None``) lets the host decide whether
    # to resume us on a particular event.
    def __init__(self, filter=None):
        self._filter = filter

    def __await__(self):
        return (yield self._filter)


def _as_event_tuple(value):
    if value is None:
        return ()
    try:
        return tuple(value)
    except TypeError:
        return (value,)


async def pull_event_raw(filter=None):
    """Yield until the host dispatches an event, optionally filtered by name."""
    return _as_event_tuple(await _AwaitEvent(filter))


async def pull_event(filter=None):
    """Like :func:`pull_event_raw` but raises :class:`Terminated` on ``terminate``."""
    event = _as_event_tuple(await _AwaitEvent(filter))
    if event and event[0] == "terminate":
        raise Terminated("Terminated")
    return event


def start_timer(seconds):
    """Start a timer; the host fires a ``timer`` event with the returned id."""
    return cct.osStartTimer(float(seconds))


def cancel_timer(token):
    cct.osCancelTimer(int(token))


def shutdown():
    cct.osShutdown()


def reboot():
    cct.osReboot()


def version():
    """CraftOS version string. Matches Lua ``bios.lua`` / ``os.version()``."""
    return "CraftOS 1.9 (Python)"


async def sleep(seconds):
    """Block the calling coroutine for at least ``seconds`` seconds.

    Uses :func:`pull_event` with a ``timer`` filter (same idea as Lua ``os.sleep`` calling
    ``os.pullEvent``), so ``terminate`` raises :class:`Terminated` instead of spinning.
    """
    token = start_timer(float(seconds or 0))
    while True:
        event = _as_event_tuple(await pull_event("timer"))
        if len(event) >= 2 and event[1] == token:
            return


def queue_event(name, *args):
    """Queue an event for :func:`pull_event` / :func:`pull_event_raw` (Lua ``os.queueEvent``)."""
    cct.osQueueEvent(str(name), *args)
