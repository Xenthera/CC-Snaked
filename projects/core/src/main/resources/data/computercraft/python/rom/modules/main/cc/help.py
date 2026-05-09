"""Minimal ``help`` stub matching Lua's global ``help`` table surface.

Stock ROM exposes ``help.setPath``. Full topic indexing is still ROM/program work.
"""

_help_path = "/rom/help"


def set_path(path: str) -> None:
    global _help_path
    _help_path = str(path)


setPath = set_path


def get_path() -> str:
    return _help_path


getPath = get_path
