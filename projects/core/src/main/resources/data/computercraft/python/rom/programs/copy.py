"""Copy files or directories (port of ``rom/programs/copy.lua``).

Alias ``cp`` maps to this program (set up in ``rom/startup.py``).
"""


def main():
    if len(arg) < 3:
        program_name = arg[0] if arg else "copy"
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
            try:
                fs.copy(f, fs.combine(dest, fs.get_name(f)))
            except Exception as e:
                printError(str(e))
        elif len(files) == 1:
            if fs.exists(dest):
                printError("Destination exists")
            elif fs.is_read_only(dest):
                printError("Destination is read-only")
            else:
                try:
                    fs.copy(f, dest)
                except Exception as e:
                    printError(str(e))
        else:
            printError("Cannot overwrite file multiple times")
            return


main()
