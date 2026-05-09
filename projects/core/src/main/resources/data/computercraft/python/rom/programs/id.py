"""Show this computer's id (placeholder port of ``rom/programs/id.lua``).

The Lua original calls ``os.getComputerID()``/``os.getComputerLabel()`` and
also probes disk drives. We don't have these wired through the Python host
bridge yet; this stub keeps the program path in place.
"""


def main():
    printError("id: not implemented yet (computer id/label not exposed to Python)")


main()
