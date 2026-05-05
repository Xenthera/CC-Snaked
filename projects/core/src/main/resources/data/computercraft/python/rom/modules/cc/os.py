"""ComputerCraft ``os`` module for Python.

Mirrors the most-used parts of Lua's ``os`` API. Names are snake_case to be
idiomatic Python; the underlying semantics (event filtering, timer ticks,
``terminate`` translating into an exception) match the Lua side so that
behavior is consistent across language runtimes.

The host runtime (``cct``) is bound at module-import time by ``PythonMachine``.
"""


class Terminated(Exception):
    """Raised by :func:`pull_event` when a ``terminate`` event is dispatched."""


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


async def sleep(seconds):
    """Block the calling coroutine for at least ``seconds`` seconds."""
    token = start_timer(float(seconds or 0))
    while True:
        event = _as_event_tuple(await _AwaitEvent("timer"))
        if len(event) >= 2 and event[1] == token:
            return


def queue_event(name, *args):
    # TODO(python-runtime): wire through to OSAPI.queueEvent once we have a
    # non-Lua-bound entry point. The Lua-bound overload needs an IArguments
    # wrapper which we deliberately don't expose to the host bridge yet.
    raise NotImplementedError("os.queue_event is not wired yet")
