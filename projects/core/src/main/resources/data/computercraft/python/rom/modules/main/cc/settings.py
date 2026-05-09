"""ComputerCraft ``settings`` API (Python).

Mirrors Lua's ``settings`` ROM API where practical: :func:`define`, :func:`get`,
:func:`set`, :func:`unset`, and persistence via :func:`load` / :func:`save`.

On-disk format uses **JSON** (Lua uses ``textutils.serialize``) so the Python
guest can round-trip without a Lua serializer.
"""

from __future__ import annotations

import json

_definitions: dict[str, dict] = {}
_values: dict[str, object] = {}


def define(name: str, options: dict | None = None) -> None:
    """Register a setting name and its metadata (default, type, description)."""
    options = options or {}
    _definitions[str(name)] = {
        "default": options.get("default"),
        "type": options.get("type"),
        "description": options.get("description"),
    }


def get(name: str):
    """Return the current value, or the registered default, or ``None``."""
    key = str(name)
    if key in _values:
        return _values[key]
    meta = _definitions.get(key)
    if meta is not None:
        return meta.get("default")
    return None


def set(name: str, value) -> None:
    """Set a runtime value (same role as Lua ``settings.set``)."""
    _values[str(name)] = value


def unset(name: str) -> None:
    """Remove a runtime override (same role as Lua ``settings.unset``)."""
    _values.pop(str(name), None)


def load(path: str | None = None) -> bool:
    """Load settings from disk (Lua default path ``.settings``)."""
    from cc import fs

    p = ".settings" if path is None else str(path)
    try:
        raw = fs.read_all(p)
    except (FileNotFoundError, OSError):
        return False
    except BaseException:
        return False
    try:
        text = str(raw).strip()
        if not text:
            return False
        data = json.loads(text)
        if not isinstance(data, dict):
            return False
        for k, v in data.items():
            if not isinstance(k, str):
                continue
            if isinstance(v, (bool, int, float, str)) or v is None:
                _values[k] = v
            elif isinstance(v, (dict, list)):
                _values[k] = json.loads(json.dumps(v))
    except BaseException:
        return False
    return True


def save(path: str | None = None) -> bool:
    """Persist current overrides (Lua default ``.settings``)."""
    from cc import fs

    p = ".settings" if path is None else str(path)
    try:
        fs.write_all(p, json.dumps(_values, separators=(",", ":"), sort_keys=True))
        return True
    except BaseException:
        return False


def _install_bios_defaults() -> None:
    """Install the same ``settings.define`` keys as ``lua/bios.lua``."""

    define(
        "shell.allow_startup",
        {
            "default": True,
            "description": "Run startup files when the computer turns on.",
            "type": "boolean",
        },
    )
    define(
        "shell.allow_disk_startup",
        {
            "default": True,
            "description": "Run startup files from disk drives when the computer turns on.",
            "type": "boolean",
        },
    )
    define(
        "shell.autocomplete",
        {
            "default": True,
            "description": "Autocomplete program and arguments in the shell.",
            "type": "boolean",
        },
    )
    define(
        "python.tracebacks",
        {
            "default": False,
            "description": "Print full Python tracebacks for program errors in the shell.",
            "type": "boolean",
        },
    )
    define(
        "edit.autocomplete",
        {
            "default": True,
            "description": "Autocomplete API and function names in the editor.",
            "type": "boolean",
        },
    )
    define(
        "lua.autocomplete",
        {
            "default": True,
            "description": "Autocomplete API and function names in the Lua REPL.",
            "type": "boolean",
        },
    )
    define(
        "edit.default_extension",
        {
            "default": "py",
            "description": 'The file extension the editor will use if none is given. Set to "" to disable.',
            "type": "string",
        },
    )
    define(
        "paint.default_extension",
        {
            "default": "nfp",
            "description": 'The file extension the paint program will use if none is given. Set to "" to disable.',
            "type": "string",
        },
    )
    define(
        "list.show_hidden",
        {
            "default": False,
            "description": 'Whether the list program show  hidden files (those starting with ".").',
            "type": "boolean",
        },
    )
    define(
        "motd.enable",
        {
            "default": True,
            "description": "Display a random message when the computer starts up.",
            "type": "boolean",
        },
    )
    define(
        "motd.path",
        {
            "default": "/rom/motd.txt:/motd.txt",
            "description": 'The path to load random messages from. Should be a colon (":") separated string of file paths.',
            "type": "string",
        },
    )
    define(
        "lua.warn_against_use_of_local",
        {
            "default": True,
            "description": "Print a message when input in the Lua REPL starts with the word 'local'. Local variables defined in the Lua REPL are be inaccessible on the next input.",
            "type": "boolean",
        },
    )
    define(
        "lua.function_args",
        {
            "default": True,
            "description": "Show function arguments when printing functions.",
            "type": "boolean",
        },
    )
    define(
        "lua.function_source",
        {
            "default": False,
            "description": "Show where a function was defined when printing functions.",
            "type": "boolean",
        },
    )
    define(
        "bios.strict_globals",
        {
            "default": False,
            "description": "Prevents assigning variables into a program's environment. Make sure you use the local keyword or assign to _G explicitly.",
            "type": "boolean",
        },
    )
    define(
        "shell.autocomplete_hidden",
        {
            "default": False,
            "description": 'Autocomplete hidden files and folders (those starting with ".").',
            "type": "boolean",
        },
    )
    define(
        "bios.use_multishell",
        {
            "default": True,
            "description": 'Allow running multiple programs at once, through the use of the "fg" and "bg" programs.',
            "type": "boolean",
        },
    )


_install_bios_defaults()
