"""List loaded APIs (placeholder port of ``rom/programs/apis.lua``).

The Lua original lists APIs loaded via ``os.loadAPI``. The Python runtime
uses module imports instead, so the concept doesn't translate directly.
"""


def main():
    printError("apis: not implemented (Python uses module imports, not os.loadAPI)")


main()
