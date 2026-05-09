"""Create directories (port of ``rom/programs/mkdir.lua``)."""


def main():
    if len(arg) < 2:
        program_name = arg[0] if arg else "mkdir"
        print("Usage: " + program_name + " <paths>")
        return

    for v in arg[1:]:
        new_dir = shell.resolve(v)
        if fs.exists(new_dir) and not fs.is_dir(new_dir):
            printError(v + ": Destination exists")
        elif fs.is_read_only(new_dir):
            printError(v + ": Access denied")
        else:
            try:
                fs.make_dir(new_dir)
            except Exception as e:
                printError(v + ": " + str(e))


main()
