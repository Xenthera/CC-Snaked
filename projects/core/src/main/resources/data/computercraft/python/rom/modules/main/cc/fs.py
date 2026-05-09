"""ComputerCraft ``fs`` module for Python.

Mirrors the relevant subset of Lua's ``fs`` API. Function names use Lua's
camelCase form for direct parity with ports (``fs.makeDir``, ``fs.isDir``);
snake_case aliases are also exported so idiomatic Python is also possible.
"""


class FsError(Exception):
    pass


def list(path):
    """List directory entries. Missing paths or host errors yield ``[]`` (never propagate Java exceptions)."""
    try:
        data = str(cct.fsList(str(path)))
    except BaseException:
        return []
    if data == "":
        return []
    return data.split("\n")


def exists(path):
    return bool(cct.fsExists(str(path)))


def is_dir(path):
    return bool(cct.fsIsDir(str(path)))


isDir = is_dir


def read_all(path):
    data = cct.fsReadAll(str(path))
    if data is None:
        raise FileNotFoundError(str(path))
    return str(data)


def open(path, mode="r"):
    res = cct.fsOpen(str(path), str(mode))
    if res is None:
        return None, "Failed to open file"

    # GraalPy may expose Java Object[] as a polyglot foreign object. Some of
    # those are indexable but not iterable/sized, so avoid len()/tuple().
    try:
        handle = res[0]
    except Exception:
        return None, "Failed to open file"

    err = None
    try:
        err = res[1]
    except Exception:
        err = None

    if handle is None:
        return None, (str(err) if err else "Failed to open file")
    return handle, None


def write_all(path, content):
    """Replace a file with the given text. Uses the host bridge so GraalPy string coercion is reliable."""
    cct.fsWriteText(str(path), str(content))


def make_dir(path):
    cct.fsMakeDir(str(path))


makeDir = make_dir


def delete(path):
    cct.fsDelete(str(path))


def move(path, dest):
    cct.fsMove(str(path), str(dest))


def copy(path, dest):
    cct.fsCopy(str(path), str(dest))


def get_size(path):
    return int(cct.fsGetSize(str(path)))


getSize = get_size


def is_read_only(path):
    return bool(cct.fsIsReadOnly(str(path)))


isReadOnly = is_read_only


def get_drive(path):
    return cct.fsGetDrive(str(path))


getDrive = get_drive


def get_free_space(path):
    return cct.fsGetFreeSpace(str(path))


getFreeSpace = get_free_space


def get_capacity(path):
    return cct.fsGetCapacity(str(path))


getCapacity = get_capacity


def combine(*parts):
    parts = [str(p) for p in parts if p is not None and str(p) != ""]
    if not parts:
        return ""
    out = parts[0]
    for part in parts[1:]:
        out = cct.fsCombine(str(out), str(part))
    return str(out)


def _next_slash(s: str, start: int) -> int:
    for i in range(start, len(s)):
        if s[i] in "/\\":
            return i
    return -1


def complete(s_path, s_location, include_files=True, include_dirs=True):
    """Path completion matching Lua ``rom/apis/fs.lua`` ``fs.complete``."""

    s_path = str(s_path)
    s_dir = str(s_location)

    include_hidden_opt = None
    if isinstance(include_files, dict):
        opts = include_files
        include_dirs = opts.get("include_dirs")
        include_hidden_opt = opts.get("include_hidden")
        include_files = opts.get("include_files")
    else:
        include_hidden_opt = None

    b_include_hidden = True if include_hidden_opt is None else (include_hidden_opt is not False)
    b_include_files = include_files is not False
    b_include_dirs = include_dirs is not False

    n_start = 0
    if len(s_path) > 0 and s_path[0] in "/\\":
        s_dir = ""
        n_start = 1

    while True:
        n_slash = _next_slash(s_path, n_start)
        if n_slash >= 0:
            s_part = s_path[n_start:n_slash]
            s_dir = combine(s_dir, s_part)
            n_start = n_slash + 1
        else:
            s_name = s_path[n_start:]
            break

    if not is_dir(s_dir):
        return []

    t_results = []
    if b_include_dirs and s_path == "":
        t_results.append(".")
    if s_dir != "":
        if s_path == "":
            t_results.append(".." if b_include_dirs else "../")
        elif s_path == ".":
            t_results.append("." if b_include_dirs else "./")

    try:
        t_files = list(s_dir)
    except Exception:
        return []

    for s_file in t_files:
        if len(s_file) < len(s_name):
            continue
        if s_file[: len(s_name)] != s_name:
            continue
        show_hidden = b_include_hidden or not s_file.startswith(".") or (len(s_name) > 0 and s_name[0] == ".")
        if not show_hidden:
            continue
        full = combine(s_dir, s_file)
        b_is_dir = is_dir(full)
        s_result = s_file[len(s_name) :]
        if b_is_dir:
            t_results.append(s_result + "/")
            if b_include_dirs and len(s_result) > 0:
                t_results.append(s_result)
        else:
            if b_include_files and len(s_result) > 0:
                t_results.append(s_result)
    return t_results


def get_name(path):
    return str(cct.fsGetName(str(path)))


getName = get_name


def get_dir(path):
    return str(cct.fsGetDir(str(path)))


getDir = get_dir


def attributes(path):
    return cct.fsAttributes(str(path))


def find(path):
    """Return all paths matching the given path/wildcard pattern.

    Without wildcards this is just ``[path]`` if it exists, ``[]`` otherwise.
    Mirrors the simple cases of Lua's ``fs.find``; full wildcard expansion is
    deferred until host support is wired.
    """
    p = str(path)
    if "*" in p or "?" in p:
        # Wildcard support is not wired yet; return nothing rather than crash.
        return []
    return [p] if exists(p) else []


def is_drive_root(path):
    """Whether ``path`` is the root of a mounted drive.

    Lua's ``fs.isDriveRoot`` does the same check; the host doesn't currently
    expose it directly, so we approximate with ``getDrive``.
    """
    return bool(get_drive(str(path))) and combine(str(path), "") in ("", "/")


isDriveRoot = is_drive_root
