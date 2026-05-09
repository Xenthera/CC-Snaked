"""Stub ``cc.peripheral`` module.

Peripheral access is not yet wired through the Python host bridge. This
module preserves the import path but raises a clear error when called.
"""


def _unavailable(*_args, **_kwargs):
    raise NotImplementedError("cc.peripheral is not wired yet")


wrap = _unavailable
call = _unavailable
get_names = _unavailable
getNames = _unavailable
is_present = _unavailable
isPresent = _unavailable
get_type = _unavailable
getType = _unavailable
