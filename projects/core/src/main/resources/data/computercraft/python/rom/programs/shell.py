"""ComputerCraft shell (Python).

This is an interactive command shell similar to `rom/programs/shell.lua`.
For now it supports a faithful prompt, basic line input, built-in commands,
and running ROM programs implemented as Python modules under `rom.programs`.

Disk/hdd filesystem execution is a later milestone once `cc.fs` is wired.
"""

from cc import os as ccos
from cc import fs
from cc import term


class ShellExit(Exception):
    pass


def _coerce_char(value) -> str:
    """
    Coerce a ComputerCraft `char` event argument into a 1-character Python string.
    Some platforms deliver this as an int codepoint, while others appear to deliver
    a foreign array-like value (for instance a 1-byte Java array).
    """
    if value is None:
        return ""

    if isinstance(value, str):
        return value[0:1]

    if isinstance(value, int):
        try:
            return chr(value)
        except ValueError:
            return ""

    # Try treating it as an iterable of bytes/codepoints.
    try:
        items = list(value)
    except TypeError:
        return str(value)[0:1]

    if len(items) == 0:
        return ""

    if len(items) == 1 and isinstance(items[0], int):
        try:
            return chr(items[0])
        except ValueError:
            return ""

    # If it's a byte array, decode it (best-effort).
    if all(isinstance(x, int) and 0 <= x <= 255 for x in items):
        try:
            return bytes(items).decode("utf-8", errors="ignore")[0:1]
        except Exception:
            return ""

    return str(value)[0:1]


def _prompt(cwd: str) -> str:
    if not cwd.startswith("/"):
        cwd = "/" + cwd
    return f"{cwd}> "


def _write_line(text: str) -> None:
    term.write(text)
    term.write("\n")


def _split_command(line: str) -> list[str]:
    # Minimal, Lua-like splitting: whitespace separates arguments.
    # Quoting/escaping is a later parity pass.
    return [part for part in line.strip().split() if part]


async def _read_line(cwd: str) -> str:
    """
    Very small line editor based on `char` and `key` events.
    This is intentionally minimal: it provides the baseline needed for an
    interactive shell loop.
    """
    buf: list[str] = []
    term.write(_prompt(cwd))

    while True:
        ev = await ccos.pull_event_raw()
        if not ev:
            continue

        name = ev[0]
        if name == "terminate":
            raise ShellExit()

        if name == "char" and len(ev) >= 2:
            ch = _coerce_char(ev[1])
            buf.append(ch)
            term.write(ch)
            continue

        if name == "key" and len(ev) >= 2:
            key = ev[1]
            # Backspace is 259 in GLFW; this is what MC uses for CC key events.
            if key == 259:
                if buf:
                    buf.pop()
                    x, y = term.get_cursor_pos()
                    if x > 1:
                        term.set_cursor_pos(x - 1, y)
                        term.write(" ")
                        term.set_cursor_pos(x - 1, y)
                continue
            # Enter is 257 in GLFW.
            if key == 257:
                term.write("\n")
                return "".join(buf)


async def _cmd_help(_argv: list[str]) -> None:
    _write_line("Built-in commands:")
    _write_line("  help         Show this help")
    _write_line("  clear        Clear the screen")
    _write_line("  echo ...     Print arguments")
    _write_line("  pwd          Print the current directory")
    _write_line("  cd <dir>     Change directory")
    _write_line("  ls [dir]     List directory")
    _write_line("  cat <file>   Print a file")
    _write_line("  exit         Exit the shell")
    _write_line("")
    _write_line("ROM programs:")
    _write_line("  shell        This shell")
    _write_line("")
    _write_line("Note: filesystem execution is not wired yet.")


async def _cmd_clear(_argv: list[str]) -> None:
    term.clear()
    term.set_cursor_pos(1, 1)


async def _cmd_echo(argv: list[str]) -> None:
    _write_line(" ".join(argv[1:]))


async def _cmd_exit(_argv: list[str]) -> None:
    raise ShellExit()

async def _cmd_pwd(argv: list[str], state: dict) -> None:
    _write_line(state["cwd"])


async def _cmd_cd(argv: list[str], state: dict) -> None:
    if len(argv) < 2:
        state["cwd"] = "/"
        return
    path = _resolve_path(argv[1], state["cwd"])
    if not fs.exists(path) or not fs.is_dir(path):
        _write_line(f"Not a directory: {argv[1]}")
        return
    state["cwd"] = path


async def _cmd_ls(argv: list[str], state: dict) -> None:
    path = state["cwd"] if len(argv) < 2 else _resolve_path(argv[1], state["cwd"])
    if not fs.exists(path):
        _write_line(f"No such file or directory: {argv[1] if len(argv) >= 2 else path}")
        return
    if not fs.is_dir(path):
        _write_line(path)
        return
    for name in fs.list(path):
        _write_line(name)


async def _cmd_cat(argv: list[str], state: dict) -> None:
    if len(argv) < 2:
        _write_line("Usage: cat <file>")
        return
    path = _resolve_path(argv[1], state["cwd"])
    try:
        _write_line(fs.read_all(path))
    except FileNotFoundError:
        _write_line(f"No such file: {argv[1]}")


def _resolve_path(path: str, cwd: str) -> str:
    path = str(path)
    if path.startswith("/"):
        out = path
    else:
        out = fs.combine(cwd, path)

    parts = []
    for part in out.split("/"):
        if part == "" or part == ".":
            continue
        if part == "..":
            if parts:
                parts.pop()
            continue
        parts.append(part)
    return "/" + "/".join(parts)


_BUILTINS: dict[str, callable] = {
    "help": _cmd_help,
    "clear": _cmd_clear,
    "cls": _cmd_clear,
    "echo": _cmd_echo,
    "pwd": _cmd_pwd,
    "cd": _cmd_cd,
    "ls": _cmd_ls,
    "dir": _cmd_ls,
    "cat": _cmd_cat,
    "type": _cmd_cat,
    "exit": _cmd_exit,
}


async def run(argv: list[str] | None = None) -> None:
    """
    Entry point for the ROM shell program.
    """
    state = {"cwd": "/"}

    if argv is None:
        argv = []

    try:
        while True:
            line = await _read_line(state["cwd"])
            parts = _split_command(line)
            if not parts:
                continue

            cmd = parts[0]
            try:
                builtin = _BUILTINS.get(cmd)
                if builtin is not None:
                    # Some built-ins mutate shell state.
                    if cmd in ("pwd", "cd", "ls", "dir", "cat", "type"):
                        await builtin(parts, state)
                    else:
                        await builtin(parts)
                    continue

                # Try to run a ROM program (e.g. `rom.programs.foo`).
                # If the user provided a path (or .py), try to execute it from the filesystem.
                if "/" in cmd or cmd.endswith(".py"):
                    path = _resolve_path(cmd, state["cwd"])
                    try:
                        source = fs.read_all(path)
                    except FileNotFoundError:
                        _write_line(f"{cmd}: not found")
                        continue

                    scope = {"__name__": "__main__"}
                    exec(compile(source, path, "exec"), scope, scope)
                    continue

                try:
                    mod = __import__(f"rom.programs.{cmd}", fromlist=["run"])
                except Exception:
                    _write_line(f"{cmd}: not found")
                    continue

                fn = getattr(mod, "run", None)
                if fn is None or not callable(fn):
                    _write_line(f"{cmd}: not runnable")
                    continue

                # Programs follow the same async model as BIOS/shell.
                res = fn(parts)
                if hasattr(res, "__await__"):
                    await res
            except Exception as e:
                _write_line(f"Error: {e}")
    except ShellExit:
        return

