"""ComputerCraft shell API (Python).

Lua exposes ``shell`` from ``rom/programs/shell.lua`` (API table + execution).
Python centralizes the same responsibilities in :class:`Shell` and in the
``rom/programs/shell.py`` driver so additional language front-ends can mirror this layout:

- Lua ``shell.execute`` / ``shell.run`` ↔ :meth:`Shell.execute` / :meth:`Shell.run`
  (tokenise → resolve → run; program stack updated once per ``execute``, not per hashbang step).
- Lua ``executeProgram`` ↔ :meth:`Shell._execute_program` (hashbang recursion; Python loads
  program text via ``fs.read_all`` for reliable GraalPy I/O).
- Lua ``parentShell`` inheritance ↔ :meth:`Shell.__init__(parent)` for nested shells / future multishell.

CamelCase aliases (``resolveProgram``, ``setDir``, …) match Lua exports.
"""

from cc import fs
from cc import os as ccos
from cc import settings

_current = None


async def _isolate_program(thunk):
    """Lua ``pcall`` analogue for async code: await ``thunk()`` and return ``None``, or the caught exception.

    Never raises — callers decide whether to treat ``cc.os.Terminated`` as a clean stop or re-raise other errors.
    """
    try:
        await thunk()
        return None
    except BaseException as exc:
        return exc


def set_current(shell) -> None:
    global _current
    _current = shell


def _require_current():
    if _current is None:
        raise RuntimeError("shell API unavailable (no current shell)")
    return _current


def tokenise(*parts) -> list:
    """Split a command line into words. Matches Lua's ``shell.lua`` tokenise."""
    s_line = " ".join(str(x) for x in parts)
    words = []
    quoted = False
    for match in (s_line + "\"").split("\""):
        if quoted:
            if match != "":
                words.append(match)
        else:
            for w in match.split():
                words.append(w)
        quoted = not quoted
    return words


class _StrictGlobals(dict):
    """Reject assignments to keys not present at environment creation (Lua strict globals)."""

    __slots__ = ("_allowed_keys",)

    def __init__(self, seed: dict):
        super().__init__(seed)
        self._allowed_keys = frozenset(seed.keys())

    def __setitem__(self, key, value):
        if key not in self._allowed_keys:
            raise RuntimeError("Attempt to create global " + str(key))
        super().__setitem__(key, value)


class Shell:
    def __init__(self, parent=None):
        """Create a shell.

        When ``parent`` is another :class:`Shell` (nested tab / subshell), copy cwd,
        path, aliases, and completion registry like Lua's ``parentShell`` locals.
        """
        self._parent = parent
        self._exit = False
        if parent is not None:
            self._dir = parent._dir
            self._path = parent._path
            self._aliases = dict(parent._aliases)
            self._completion_info = parent._completion_info
        else:
            self._dir = ""  # root
            self._path = ".:/rom/programs"
            self._aliases = {}
            self._completion_info = {}
        self._program_stack: list = []

    # ---- lifecycle ----
    def exit(self) -> None:
        self._exit = True

    def should_exit(self) -> bool:
        return self._exit

    # ---- working directory ----
    def dir(self) -> str:
        return self._dir

    def set_dir(self, directory: str) -> None:
        """Set cwd (Lua ``shell.setDir``).

        The argument is a **full** directory path, typically from ``shell.resolve``
        (see ``rom/programs/cd.lua``). It is *not* a segment joined onto the previous
        cwd — that differs from ``shell.resolve`` for relative paths.
        """
        directory = str(directory)
        if directory == "":
            self._dir = ""
            return
        if not fs.is_dir(directory):
            raise RuntimeError("Not a directory")
        self._dir = fs.combine(directory, "")

    setDir = set_dir

    # ---- path + aliases ----
    def path(self) -> str:
        return self._path

    def set_path(self, path: str) -> None:
        self._path = str(path)

    setPath = set_path

    def set_alias(self, command: str, program: str) -> None:
        self._aliases[str(command)] = str(program)

    setAlias = set_alias

    def clear_alias(self, command: str) -> None:
        self._aliases.pop(str(command), None)

    clearAlias = clear_alias

    def aliases(self) -> dict:
        return dict(self._aliases)

    # ---- resolve ----
    def resolve(self, path: str) -> str:
        path = str(path)
        if path.startswith(("/", "\\")):
            return fs.combine("", path.lstrip("/\\"))
        return fs.combine(self._dir, path)

    def resolve_program(self, command: str):
        command = str(command)

        if command in self._aliases:
            command = self._aliases[command]

        def with_ext(p):
            if p.endswith(".py"):
                return p
            return p + ".py"

        if "/" in command or "\\" in command:
            p = self.resolve(command)
            p = p.lstrip("/\\")
            if fs.exists(p) and not fs.is_dir(p):
                return p
            pe = with_ext(p)
            if fs.exists(pe) and not fs.is_dir(pe):
                return pe
            return None

        for entry in self._path.split(":"):
            entry = entry or "."
            base = self.resolve(entry)
            base = base.lstrip("/\\")
            p = fs.combine(base, command)
            if fs.exists(p) and not fs.is_dir(p):
                return p
            pe = with_ext(p)
            if fs.exists(pe) and not fs.is_dir(pe):
                return pe

        return None

    resolveProgram = resolve_program

    # ---- program enumeration ----
    def programs(self, include_hidden: bool = False) -> list:
        """List program names reachable from the current path.

        Mirrors ``shell.programs`` in Lua. ``.py`` extensions are stripped.
        """
        seen = set()
        for entry in self._path.split(":"):
            entry = entry or "."
            base = self.resolve(entry)
            base = base.lstrip("/\\")
            try:
                names = fs.list(base)
            except BaseException:
                continue
            for name in names:
                full = fs.combine(base, name)
                if fs.is_dir(full):
                    continue
                clean = name
                if clean.endswith(".py"):
                    clean = clean[:-3]
                if clean.startswith(".") and not include_hidden:
                    continue
                if clean == "__init__":
                    continue
                seen.add(clean)
        return sorted(seen)

    # ---- program stack ----
    def get_running_program(self):
        if not self._program_stack:
            return None
        return self._program_stack[-1]

    getRunningProgram = get_running_program

    # ---- completion registry ----
    def set_completion_function(self, program, function):
        self._completion_info[str(program)] = {"fnComplete": function}

    setCompletionFunction = set_completion_function

    def get_completion_info(self):
        return self._completion_info

    getCompletionInfo = get_completion_info

    def complete_program(self, line: str) -> list:
        """Complete a program name (matches Lua ``completeProgram``)."""
        line = str(line)
        include_hidden = settings.get("shell.autocomplete_hidden")
        if include_hidden is None:
            include_hidden = False

        if line and ("/" in line or "\\" in line):
            return fs.complete(
                line,
                self.dir(),
                {
                    "include_files": True,
                    "include_dirs": False,
                    "include_hidden": include_hidden,
                },
            )

        results = []
        seen = {}

        for alias in self._aliases:
            if len(alias) > len(line) and alias.startswith(line):
                s_result = alias[len(line) :]
                if s_result not in seen:
                    seen[s_result] = True
                    results.append(s_result)

        for s_result in fs.complete(
            line,
            self.dir(),
            {
                "include_files": False,
                "include_dirs": False,
                "include_hidden": include_hidden,
            },
        ):
            if s_result not in seen:
                seen[s_result] = True
                results.append(s_result)

        for s_program in self.programs():
            if len(s_program) > len(line) and s_program.startswith(line):
                s_result = s_program[len(line) :]
                if s_result not in seen:
                    seen[s_result] = True
                    results.append(s_result)

        results.sort()
        return results

    completeProgram = complete_program

    def complete(self, line: str):
        """Complete a shell command line (matches Lua ``shell.complete``)."""
        line = str(line)
        if not line:
            return None
        words = tokenise(line)
        if not words:
            return None
        index = len(words)
        if line.endswith(" "):
            index += 1
        if index == 1:
            s_bit = words[0] if words else ""
            s_path = self.resolve_program(s_bit)
            if s_path is not None and s_path in self._completion_info:
                return [" "]
            t_results = self.complete_program(s_bit)
            out = []
            for s_result in t_results:
                combined = self.resolve_program(s_bit + s_result)
                if combined is not None and combined in self._completion_info:
                    out.append(s_result + " ")
                else:
                    out.append(s_result)
            return out
        if index > 1:
            s_path = self.resolve_program(words[0])
            if s_path is None:
                return None
            info = self._completion_info.get(s_path)
            if info is None:
                return None
            fn = info.get("fnComplete")
            if fn is None:
                return None
            part = "" if line.endswith(" ") else words[-1]
            previous = words[: index - 1]
            try:
                return fn(self, index - 1, part, previous)
            except Exception:
                return None
        return None

    # ---- execution ----
    async def execute(self, command, *args) -> bool:
        """Run a program by name. Returns True on success.

        Matches Lua ``shell.execute``: resolve filesystem path, push ``tProgramStack``
        once for this invocation (not once per hashbang recursion).
        """
        command = str(command)
        args = tuple(str(a) for a in args)

        path = self.resolve_program(command)
        if path is not None:
            path = str(path)
        if path:
            self._program_stack.append(path)
            try:
                return await self._execute_program(100, path, [command, *args])
            finally:
                if self._program_stack:
                    self._program_stack.pop()

        # Fallback: attempt to import a ROM program module. This keeps the shell
        # usable even if the ROM mount is temporarily out of sync, as long as the
        # ROM importer can load `rom.programs.*`.
        try:
            mod = __import__(f"rom.programs.{command}", fromlist=["main"])
        except Exception:
            return False

        fn = getattr(mod, "main", None)
        if fn is None:
            return False

        import inspect

        async def _rom_run():
            res = fn(*args)
            if inspect.isawaitable(res):
                await res

        exc = await _isolate_program(_rom_run)
        if exc is None:
            return True
        if ccos.is_terminated(exc):
            return True
        raise exc

    def _make_program_env(self, path: str, args: list) -> dict:
        return _shell_make_program_env(self, path, args)

    async def _execute_program(self, remaining_recursion, path, args) -> bool:
        # Load source via ``fs.read_all`` (host ``fsReadAll`` + ``ReadHandle`` in Java), not ``fs.open`` +
        # ``PythonFileHandle.readLine``. Guest handle interop has been unreliable under GraalPy even when
        # ``fs.exists`` is true; reading the file in one JVM call avoids that path entirely.
        try:
            full = fs.read_all(path)
        except (FileNotFoundError, OSError):
            return False
        except Exception:
            return False

        full = str(full).replace("\r\n", "\n").replace("\r", "\n")
        if "\n" in full:
            first_line, _remainder = full.split("\n", 1)
        else:
            first_line = full
        first = first_line.lstrip("\ufeff")

        if first.startswith("#!"):
            remaining_recursion -= 1
            if remaining_recursion == 0:
                return False

            words = tokenise(first[2:].strip())
            if not words:
                return False
            # `#!/usr/bin/env python` → interpreter is words[1], optional extra flags follow.
            if words[0].strip().endswith("env") and len(words) >= 2:
                interp_name = words[1].strip()
                interp_extra = words[2:]
            else:
                interp_name = words[0].strip()
                interp_extra = words[1:]
            interp_path = self.resolve_program(interp_name)
            if not interp_path:
                return False
            interp_path = str(interp_path)
            # Lua: ``#!/… shell`` with no further hashbang tokens cannot target shell.lua
            # or it loops; same for ``rom/programs/shell.py``.
            norm = interp_path.replace("\\", "/").lstrip("/")
            if norm == "rom/programs/shell.py" and len(interp_extra) == 0:
                return False
            new_args = list(interp_extra) + ["/" + path] + list(args[1:])
            return await self._execute_program(remaining_recursion, interp_path, [interp_name, *new_args])

        source = full
        env = self._make_program_env(path, args)

        import inspect

        async def _run_file_program():
            await _run_program_source(source, "/" + path, env, args)
            fn = env.get("main")
            if fn is not None and inspect.iscoroutinefunction(fn):
                await fn(*args[1:])

        exc = await _isolate_program(_run_file_program)
        if exc is None:
            return True
        if ccos.is_terminated(exc):
            return True
        raise exc

    async def run(self, *parts) -> bool:
        words = tokenise(*parts)
        if not words:
            return False
        return await self.execute(words[0], *words[1:])

    # ---- multishell integration (mirrors ``shell.openTab`` / ``shell.switchTab``) ----

    def open_tab(self, *parts):
        """Open a new multishell tab running ``parts``. Returns the tab id (or None)."""
        from cc import multishell as _ms

        if not _ms.is_active():
            return None
        words = tokenise(*parts)
        if not words:
            return None
        command = words[0]
        path = self.resolve_program(command)
        if path is None:
            try:
                from cc import term as _ccterm

                if _ccterm.is_color():
                    prev = _ccterm.get_text_color()
                    _ccterm.set_text_color(0x4000)
                    _ccterm.write_wrapped("No such program\n")
                    _ccterm.set_text_color(prev)
                else:
                    _ccterm.write_wrapped("No such program\n")
            except Exception:
                pass
            return None
        env = self._make_program_env(path, [command])
        env["multishell"] = _ms
        norm = path.replace("\\", "/").lstrip("/")
        if norm == "rom/programs/shell.py":
            return _ms.launch(env, path, *words[1:])
        return _ms.launch(env, "rom/programs/shell.py", command, *words[1:])

    openTab = open_tab

    def switch_tab(self, tab_id):
        from cc import multishell as _ms

        if _ms.is_active():
            _ms.set_focus(int(tab_id))

    switchTab = switch_tab


async def _run_program_source(source: str, filename: str, env: dict, args: list) -> None:
    """Execute a ROM program's source code inside an async wrapper.

    Lua parity: in CraftOS, *all* program code runs inside a resumable coroutine
    (via `os.run`/multishell). Python cannot `await` at top-level unless we run
    inside an `async def`, so we always wrap the entire program body in an async
    function and await it. This makes `await os.pull_event()`/`await sleep(0)`
    universally legal and consolidates behavior across shell execution and
    edit-runner execution.
    """
    import inspect

    def _wrap_async(src: str) -> str:
        indented = "\n".join(("    " + line) for line in src.splitlines())
        if indented and not indented.endswith("\n"):
            indented += "\n"
        body = indented or "    pass\n"
        # Export locals back into globals so top-level defs still end up in the
        # program environment (approximate module-scope semantics).
        export = (
            "    globals().update({k: v for (k, v) in locals().items() if not k.startswith('__')})\n"
        )
        return "async def __cct_main__():\n" + body + export + "\n__cct_main__()\n"

    # Prefer normal module execution (keeps true module/global semantics). Only
    # fall back to async-wrapping when the program uses `await` at top level.
    try:
        exec(compile(source, filename, "exec"), env, env)
        return
    except SyntaxError as e:
        msg = str(getattr(e, "msg", "") or e)
        text = str(getattr(e, "text", "") or "")
        if not (("await" in msg and "outside" in msg) or ("await" in text)):
            raise

    wrapped = _wrap_async(source)
    maybe = eval(compile(wrapped, filename, "exec"), env, env)
    if inspect.isawaitable(maybe):
        await maybe
    return


# --- Remaining Shell methods (continued) ---


def _shell_make_program_env(shell: "Shell", path: str, args: list) -> dict:
    """Build the execution environment for a program (mirrors Lua's createShellEnv)."""
    import builtins as _builtins

    from cc import help as cchelp
    from cc import http as cchttp
    from cc import os as ccos_env
    from cc import term as ccterm
    from cc import multishell as ccmultishell

    async def _sleep(seconds=0):
        await ccos_env.sleep(seconds or 0)

    def _print(*parts, sep=" ", end="\n"):
        text = sep.join(str(p) for p in parts) + end
        ccterm.write_wrapped(text)

    def _print_error(*parts, sep=" "):
        text = sep.join(str(p) for p in parts) + "\n"
        try:
            if ccterm.is_color():
                prev = ccterm.get_text_color()
                ccterm.set_text_color(0x4000)  # red
                ccterm.write_wrapped(text)
                ccterm.set_text_color(prev)
                return
        except Exception:
            pass
        ccterm.write_wrapped(text)

    def _write(text):
        ccterm.write_wrapped(str(text))

    seed = {
        "__name__": "__main__",
        "__builtins__": _builtins,
        "shell": shell,
        "arg": list(args),
        "print": _print,
        "printError": _print_error,
        "print_error": _print_error,
        "write": _write,
        "sleep": _sleep,
        "term": ccterm,
        "fs": fs,
        "http": cchttp,
        "os": ccos_env,
        "help": cchelp,
        # multishell is exposed exactly like Lua: a global; all calls are
        # safe no-ops when no multishell is running.
        "multishell": ccmultishell,
    }
    if settings.get("bios.strict_globals"):
        return _StrictGlobals(seed)
    return dict(seed)


# ---- Module-level facade matching Lua's `shell.*` ----

def exit() -> None:
    _require_current().exit()


def dir() -> str:
    return _require_current().dir()


def set_dir(directory: str) -> None:
    _require_current().set_dir(directory)


setDir = set_dir


def path() -> str:
    return _require_current().path()


def set_path(path_value: str) -> None:
    _require_current().set_path(path_value)


setPath = set_path


def set_alias(command: str, program: str) -> None:
    _require_current().set_alias(command, program)


setAlias = set_alias


def clear_alias(command: str) -> None:
    _require_current().clear_alias(command)


clearAlias = clear_alias


def aliases() -> dict:
    return _require_current().aliases()


def resolve(path_value: str) -> str:
    return _require_current().resolve(path_value)


def resolve_program(command: str):
    return _require_current().resolve_program(command)


resolveProgram = resolve_program


def programs(include_hidden: bool = False) -> list:
    return _require_current().programs(include_hidden)


def get_running_program():
    return _require_current().get_running_program()


getRunningProgram = get_running_program


def set_completion_function(program, function):
    _require_current().set_completion_function(program, function)


setCompletionFunction = set_completion_function


def get_completion_info():
    return _require_current().get_completion_info()


getCompletionInfo = get_completion_info


def complete(line: str):
    return _require_current().complete(line)


def complete_program(line: str) -> list:
    return _require_current().complete_program(line)


completeProgram = complete_program


async def execute(command: str, *args) -> bool:
    return await _require_current().execute(command, *args)


async def run(*parts) -> bool:
    return await _require_current().run(*parts)


def open_tab(*parts):
    return _require_current().open_tab(*parts)


openTab = open_tab


def switch_tab(tab_id):
    _require_current().switch_tab(tab_id)


switchTab = switch_tab
