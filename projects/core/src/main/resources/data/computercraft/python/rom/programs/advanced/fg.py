"""Foreground a program in a new multishell tab. Port of ``advanced/fg.lua``.

Programs run with a Shell-built env that includes ``shell``, ``multishell``
and ``printError`` as globals (see :meth:`cc.shell.Shell._make_program_env`),
so we mirror the Lua program almost line for line.
"""


async def main(*args):
    if not hasattr(shell, "open_tab"):  # type: ignore[name-defined]  # noqa: F821
        printError("Requires multishell")  # type: ignore[name-defined]  # noqa: F821
        return

    parts = list(args) if args else ["shell"]
    n_task = shell.open_tab(*parts)  # type: ignore[name-defined]  # noqa: F821
    if n_task is not None:
        shell.switch_tab(n_task)  # type: ignore[name-defined]  # noqa: F821
