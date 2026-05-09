"""Module-level facade for ``multishell``.

Mirrors the Lua behavior of ``multishell`` being a global injected into each
tab's environment. When :mod:`rom.programs.advanced.multishell` is running,
this module forwards calls to the active :class:`_Multishell` instance; when
multishell is not running (mono-shell boot), the facade returns safe null
results so callers can probe ``multishell`` without crashing.
"""

from __future__ import annotations


def _impl():
    try:
        from rom.programs.advanced import multishell as _ms_program
    except Exception:
        return None
    return _ms_program._current_multishell


def is_active() -> bool:
    """Return True if a multishell program is currently running."""
    return _impl() is not None


def get_focus():
    impl = _impl()
    return impl.get_focus() if impl else None


getFocus = get_focus


def set_focus(n):
    impl = _impl()
    return impl.set_focus(n) if impl else False


setFocus = set_focus


def get_title(n):
    impl = _impl()
    return impl.get_title(n) if impl else None


getTitle = get_title


def set_title(n, title):
    impl = _impl()
    if impl:
        impl.set_title(n, title)


setTitle = set_title


def get_current():
    impl = _impl()
    return impl.get_current() if impl else None


getCurrent = get_current


def launch(env, program_path, *args):
    impl = _impl()
    if impl is None:
        return None
    return impl.launch(env, program_path, *args)


def get_count():
    impl = _impl()
    return impl.get_count() if impl else 0


getCount = get_count
