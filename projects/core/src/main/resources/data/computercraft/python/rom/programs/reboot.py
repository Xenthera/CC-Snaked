"""Reboot the computer (port of ``rom/programs/reboot.lua``).

Convention: programs that need to ``await`` define ``async def main`` and the
shell awaits it. Synchronous programs may simply use top-level code or define
a non-async ``main`` and call it themselves.
"""


async def main(*_args):
    try:
        if term.is_color():
            term.set_text_color(0x10)  # yellow
    except Exception:
        pass
    print("Goodbye")
    try:
        term.set_text_color(0x1)  # white
    except Exception:
        pass

    await sleep(1)
    os.reboot()
