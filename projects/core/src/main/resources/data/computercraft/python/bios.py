"""Python BIOS for ComputerCraft.

This is the Python counterpart to ``bios.lua``. For now it only sets up the
ROM-import path, prints a startup banner, and parks in an idle pull-event
loop. The full shell/program-launcher is a separate milestone.
"""

from cc import term
from rom.programs import shell


def _print_banner():
    term.clear()
    term.set_cursor_pos(1, 1)
    term.write("CraftOS (Python preview)")
    term.set_cursor_pos(1, 2)
    term.write("Press Ctrl+T to terminate.")
    term.set_cursor_pos(1, 3)


async def main():
    _print_banner()
    try:
        await shell.run([])
    except Exception as e:
        term.write("\n")
        term.write("Shell error: ")
        term.write(str(e))
        term.write("\n")
