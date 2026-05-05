"""ComputerCraft ``fs`` module for Python (minimal).

This exposes a small subset of Lua's `fs` API sufficient to support a basic shell.
"""


def list(path):
    return [str(x) for x in cct.fsList(str(path))]


def exists(path):
    return bool(cct.fsExists(str(path)))


def is_dir(path):
    return bool(cct.fsIsDir(str(path)))


def read_all(path):
    data = cct.fsReadAll(str(path))
    if data is None:
        raise FileNotFoundError(str(path))
    return str(data)


def combine(*parts):
    parts = [str(p) for p in parts if p is not None and str(p) != ""]
    if not parts:
        return ""
    out = parts[0]
    for part in parts[1:]:
        if out.endswith("/"):
            out = out + part.lstrip("/")
        else:
            out = out + "/" + part.lstrip("/")
    # Cheap normalization.
    while "//" in out:
        out = out.replace("//", "/")
    return out
