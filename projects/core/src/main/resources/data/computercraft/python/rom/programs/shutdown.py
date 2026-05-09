"""Shut down the computer (port of ``rom/programs/shutdown.lua``).

Callable from the BIOS (clean exit path) as well as from the shell: uses explicit
``cc.*`` imports so :func:`main` does not rely on shell-injected globals.
"""

from cc import os as ccos
from cc import term


async def main(*_args):
    try:
        if term.is_color():
            term.set_text_color(0x10)  # yellow
    except Exception:
        pass
    term.write("Goodbye")
    term.write_wrapped("\n")
    try:
        term.set_text_color(0x1)  # white
    except Exception:
        pass

    await ccos.sleep(1)
    ccos.shutdown()
