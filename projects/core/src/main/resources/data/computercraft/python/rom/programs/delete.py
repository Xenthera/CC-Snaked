"""Delete files or directories (port of ``rom/programs/delete.lua``).

Alias ``rm`` maps to this program (set up in ``rom/startup.py``).
"""


def main():
    if len(arg) < 2:
        program_name = arg[0] if arg else "delete"
        print("Usage: " + program_name + " <paths>")
        return

    for v in arg[1:]:
        files = fs.find(shell.resolve(v))
        if files:
            for f in files:
                if fs.is_read_only(f):
                    printError("Cannot delete read-only file /" + f)
                elif fs.is_drive_root(f):
                    printError("Cannot delete mount /" + f)
                else:
                    try:
                        fs.delete(f)
                    except Exception as e:
                        printError(str(e))
        else:
            printError(v + ": No matching files")


main()
