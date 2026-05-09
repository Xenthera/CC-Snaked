"""Python equivalent of ``rom/startup.lua``.

Configures PATH, aliases, per-program completion, then runs ROM autorun, MOTD,
and user startup — matching the Lua control flow as closely as the Python
runtime allows (optional PATH segments use ``fs.is_dir`` where Lua uses globals
like ``turtle`` / ``pocket`` / ``commands``).
"""

from cc.shell import completion as _completion


async def run(shell):
    """Configure the active shell and run post-init scripts (like ``startup.lua``)."""
    from cc import fs as _fs
    from cc import settings as _settings
    from cc import term

    # ---- Path (``lua/rom/startup.lua``) ----
    s_path = ".:/rom/programs:/rom/programs/http"
    if term.is_color():
        s_path += ":/rom/programs/advanced"
    if _fs.is_dir("rom/programs/turtle"):
        s_path += ":/rom/programs/turtle"
    else:
        s_path += ":/rom/programs/rednet:/rom/programs/fun"
        if term.is_color():
            s_path += ":/rom/programs/fun/advanced"
    if _fs.is_dir("rom/programs/pocket"):
        s_path += ":/rom/programs/pocket"
    if _fs.is_dir("rom/programs/command"):
        s_path += ":/rom/programs/command"
    shell.set_path(s_path)

    try:
        from cc import help as cch

        if hasattr(cch, "set_path"):
            cch.set_path("/rom/help")
        elif hasattr(cch, "setPath"):
            cch.setPath("/rom/help")
    except Exception:
        pass

    # ---- Aliases ----
    shell.set_alias("ls", "list")
    shell.set_alias("dir", "list")
    shell.set_alias("cp", "copy")
    shell.set_alias("mv", "move")
    shell.set_alias("rm", "delete")
    shell.set_alias("clr", "clear")
    shell.set_alias("rs", "redstone")
    shell.set_alias("sh", "shell")
    if term.is_color():
        shell.set_alias("background", "bg")
        shell.set_alias("foreground", "fg")
    shell.set_alias("more", "cat")

    # ---- Completion functions ----
    shell.set_completion_function("rom/programs/alias.py", _completion.build(None, _completion.program))
    shell.set_completion_function("rom/programs/cd.py", _completion.build(_completion.dir))
    shell.set_completion_function(
        "rom/programs/clear.py",
        _completion.build([_completion.choice, ["screen", "palette", "all"]]),
    )
    shell.set_completion_function(
        "rom/programs/copy.py",
        _completion.build([_completion.dirOrFile, True], _completion.dirOrFile),
    )
    shell.set_completion_function(
        "rom/programs/delete.py",
        _completion.build({"many": True}, _completion.dirOrFile),
    )
    shell.set_completion_function("rom/programs/drive.py", _completion.build(_completion.dir))
    shell.set_completion_function("rom/programs/edit.py", _completion.build(_completion.file))
    shell.set_completion_function("rom/programs/eject.py", _completion.build(_completion.peripheral))
    shell.set_completion_function(
        "rom/programs/gps.py",
        _completion.build([_completion.choice, ["host", "host ", "locate"]]),
    )
    shell.set_completion_function("rom/programs/help.py", _completion.build(_completion.help))
    shell.set_completion_function("rom/programs/id.py", _completion.build(_completion.peripheral))
    shell.set_completion_function(
        "rom/programs/label.py",
        _completion.build(
            [_completion.choice, ["get", "get ", "set ", "clear", "clear "]],
            _completion.peripheral,
        ),
    )
    shell.set_completion_function("rom/programs/list.py", _completion.build(_completion.dir))
    shell.set_completion_function(
        "rom/programs/mkdir.py",
        _completion.build({"many": True}, _completion.dir),
    )

    def _mon1(shell, text, previous):
        a = _completion.peripheral(shell, text, previous, True) or []
        b = _completion.choice(shell, text, previous, ["scale"], True) or []
        return a + b

    def _mon2(shell, text, previous):
        if previous is not None and len(previous) >= 2 and previous[1] == "scale":
            return _completion.peripheral(shell, text, previous, True)
        return _completion.program_with_args(shell, text, previous, 3)

    shell.set_completion_function("rom/programs/monitor.py", _completion.build(_mon1, _mon2))
    shell.set_completion_function(
        "rom/programs/move.py",
        _completion.build([_completion.dirOrFile, True], _completion.dirOrFile),
    )
    shell.set_completion_function(
        "rom/programs/redstone.py",
        _completion.build(
            [_completion.choice, ["probe", "set ", "pulse "]],
            _completion.side,
        ),
    )
    shell.set_completion_function(
        "rom/programs/rename.py",
        _completion.build([_completion.dirOrFile, True], _completion.dirOrFile),
    )
    shell.set_completion_function(
        "rom/programs/shell.py",
        _completion.build([_completion.program_with_args, 2], {"many": True}),
    )
    shell.set_completion_function("rom/programs/type.py", _completion.build(_completion.dirOrFile))
    shell.set_completion_function("rom/programs/set.py", _completion.build([_completion.setting, True]))
    shell.set_completion_function("rom/programs/cat.py", _completion.build(_completion.file))

    # ---- ROM autorun ----
    if _fs.exists("rom/autorun") and _fs.is_dir("rom/autorun"):
        try:
            for s_file in _fs.list("rom/autorun"):
                if s_file.startswith("."):
                    continue
                s_path = _fs.combine("rom/autorun", s_file)
                if not _fs.is_dir(s_path):
                    await shell.run(s_path)
        except BaseException:
            pass

    # ---- MOTD ----
    if _settings.get("motd.enable"):
        try:
            await shell.run("motd")
        except BaseException:
            pass

    # ---- User startup at computer root (simplified ``findStartups("/")``) ----
    if _settings.get("shell.allow_startup"):
        try:
            base = shell.resolve("startup")
            if _fs.exists(base) and not _fs.is_dir(base):
                await shell.run(base)
            elif _fs.is_dir(base):
                for v in _fs.list(base):
                    p = _fs.combine(base, v)
                    if not _fs.is_dir(p):
                        await shell.run(p)
        except BaseException:
            pass
