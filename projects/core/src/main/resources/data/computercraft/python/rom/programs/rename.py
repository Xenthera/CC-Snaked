"""Rename a single file or directory (port of ``rom/programs/rename.lua``)."""


def main():
    if len(arg) < 3:
        program_name = arg[0] if arg else "rename"
        print("Usage: " + program_name + " <source> <destination>")
        return

    source = shell.resolve(arg[1])
    dest = shell.resolve(arg[2])

    if not fs.exists(source):
        printError("No matching files")
        return
    if fs.is_drive_root(source):
        printError("Can't rename mounts")
        return
    if fs.is_read_only(source):
        printError("Source is read-only")
        return
    if fs.exists(dest):
        printError("Destination exists")
        return
    if fs.is_read_only(dest):
        printError("Destination is read-only")
        return

    try:
        fs.move(source, dest)
    except Exception as e:
        printError(str(e))


main()
