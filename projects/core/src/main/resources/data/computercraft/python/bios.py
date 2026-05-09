"""Python BIOS for ComputerCraft.

This is not a line-for-line port of ``bios.lua``. Lua's BIOS (~750 lines) defines
globals (``sleep``, ``write``, ``print``, ``read``, …), loads ``rom/apis``,
registers settings, and boots the shell. In Python those concerns are split across
the host bridge (``cc.*``), import machinery, and ``rom/programs/shell.py``.

Lifecycle behavior we align with Lua where we can:

- Show a short startup banner (Lua goes straight to APIs/settings/shell).
- Run ``rom/programs/shell.py`` until it stops.
- On a **clean** shell exit (``exit`` → :meth:`shell.should_exit`), run
  ``rom/programs/shutdown.py`` — same role as Lua's ``os.run({}, "rom/programs/shutdown.lua")``
  after the shell returns — then finish (host tears down the VM).
- On shell crash, print an error and **start another shell** (restart resilience;
  stock Lua BIOS does not loop the shell).

Remaining BIOS gaps: ``parallel.waitForAny`` with ``rednet``, ``multishell``, API auto-loading.
"""

import cc.settings  # noqa: F401 — registers defaults like Lua ``bios.lua``
from cc import settings as ccsettings

ccsettings.load()

def _install_timeout_trace() -> None:
    # Mimic Lua VM's "Too long without yielding" interrupt handler.
    #
    # We cannot inject an interrupt into the Python VM at the bytecode level yet, so we use a trace hook to poll
    # the host timeout flag on each executed line and raise from *inside* guest code. This means program-level code
    # (shell, REPL, etc.) can catch and continue, matching CraftOS behaviour.
    import sys

    def _poll() -> None:
        # Ctrl+T/shutdown requests are delivered as a host flag too, so tight loops can be stopped.
        if cct.consumeUserInterrupt():
            from cc import os as ccos

            raise ccos.Terminated("Terminated")
        if cct.timeoutIsSoftAborted():
            raise RuntimeError("Too long without yielding")

    def _trace(frame, event, arg):
        # "line" only fires when the line number changes, which means a one-line tight loop like
        # `for i in range(...): pass` may never poll. Enable opcode events and poll there too.
        if event == "call":
            try:
                frame.f_trace_opcodes = True
            except Exception:
                pass
            return _trace
        if event == "line" or event == "opcode":
            _poll()
        return _trace

    sys.settrace(_trace)


_install_timeout_trace()

from cc import shell as ccshell
from cc import term


def _print_banner() -> None:
    term.clear()
    term.set_cursor_pos(1, 1)
    # Leave banner printing to the shell header (which prints os.version()) so we don't duplicate
    # the version line on startup.


def _should_use_multishell() -> bool:
    """Mirror Lua bios: multishell when ``term.is_color()`` and setting is on."""
    try:
        if not term.is_color():
            return False
    except Exception:
        return False
    try:
        return bool(ccsettings.get("bios.use_multishell"))
    except Exception:
        return False


async def main() -> None:
    """Entry point invoked by ``PythonMachine``."""
    _print_banner()

    use_multishell = _should_use_multishell()

    while True:
        shell = ccshell.Shell()
        ccshell.set_current(shell)

        try:
            if use_multishell:
                # Lua selects ``rom/programs/advanced/multishell.lua`` here on
                # advanced terminals when the setting is enabled.
                from rom.programs.advanced import multishell as multishell_program

                await multishell_program.main()
            else:
                from rom.programs import shell as shell_program

                await shell_program.run([])
        except BaseException as e:
            # Ctrl+T should stop the current program and return to the UI,
            # not crash the computer. Multishell/shell should generally catch
            # this themselves, but handle it here as a final safety net.
            try:
                from cc import os as ccos

                if ccos.is_terminated(e):
                    continue
            except Exception:
                pass
            term.write("\nShell error: " + str(e) + "\n")

        if shell.should_exit() or use_multishell:
            try:
                from rom.programs import shutdown as shutdown_program

                await shutdown_program.main()
            except BaseException as e:
                term.write("\nShutdown error: " + str(e) + "\n")
            return
