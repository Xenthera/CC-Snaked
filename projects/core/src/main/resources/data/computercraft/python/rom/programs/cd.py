"""Change directory (port of ``rom/programs/cd.lua``)."""


def main():
    if len(arg) < 2:
        program_name = arg[0] if arg else "cd"
        print("Usage: " + program_name + " <path>")
        return

    new_dir = shell.resolve(arg[1])
    if fs.is_dir(new_dir):
        shell.set_dir(new_dir)
    else:
        print("Not a directory")


main()
