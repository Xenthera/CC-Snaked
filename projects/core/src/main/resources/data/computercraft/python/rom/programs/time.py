"""Show the in-game time (placeholder port of ``rom/programs/time.lua``).

Requires ``os.time``/``os.day`` and ``textutils.formatTime`` from Lua, none
of which are wired through the Python host bridge yet.
"""


def main():
    printError("time: not implemented yet (os.time/os.day not exposed to Python)")


main()
