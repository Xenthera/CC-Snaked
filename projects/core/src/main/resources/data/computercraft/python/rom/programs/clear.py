"""Clear the screen and/or palette (port of ``rom/programs/clear.lua``)."""


def _print_usage():
    program_name = arg[0] if arg else "clear"
    print("Usages:")
    print(program_name)
    print(program_name + " screen")
    print(program_name + " palette")
    print(program_name + " all")


def _clear():
    term.clear()
    term.set_cursor_pos(1, 1)


def main():
    command = arg[1] if len(arg) >= 2 else "screen"
    if command == "screen":
        _clear()
    elif command == "palette":
        # Palette reset is not wired through the Python bridge yet.
        pass
    elif command == "all":
        _clear()
    else:
        _print_usage()


main()
