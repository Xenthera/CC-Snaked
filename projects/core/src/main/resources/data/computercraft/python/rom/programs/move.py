"""Move files or directories (port of ``rom/programs/move.lua``).

Alias ``mv`` maps to this program (set up in ``rom/startup.py``).
"""


def _sanity_checks(source, dest):
    if fs.exists(dest):
        printError("Destination exists")
        return False
    if fs.is_read_only(dest):
        printError("Destination is read-only")
        return False
    if fs.is_drive_root(source):
        printError("Cannot move mount /" + source)
        return False
    if fs.is_read_only(source):
        printError("Cannot move read-only file /" + source)
        return False
    return True


def main():
    if len(arg) < 3:
        program_name = arg[0] if arg else "move"
        print("Usage: " + program_name + " <source> <destination>")
        return

    source = shell.resolve(arg[1])
    dest = shell.resolve(arg[2])
    files = fs.find(source)

    if not files:
        printError("No matching files")
        return

    for f in files:
        if fs.is_dir(dest):
            target = fs.combine(dest, fs.get_name(f))
            if _sanity_checks(f, target):
                try:
                    fs.move(f, target)
                except Exception as e:
                    printError(str(e))
        elif len(files) == 1:
            if _sanity_checks(f, dest):
                try:
                    fs.move(f, dest)
                except Exception as e:
                    printError(str(e))
        else:
            printError("Cannot overwrite file multiple times")
            return


main()
