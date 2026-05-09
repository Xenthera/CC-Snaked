"""List directory contents (port of ``rom/programs/list.lua``).

Aliases ``ls``/``dir`` map to this program (set up in ``rom/startup.py``).
"""


def main():
    target = shell.dir() if len(arg) < 2 else shell.resolve(arg[1])
    target = target.lstrip("/\\")

    if not fs.is_dir(target):
        printError("Not a directory")
        return

    items = fs.list(target)
    files = []
    dirs = []
    for item in items:
        if item.startswith("."):
            continue
        full = fs.combine(target, item)
        if fs.is_dir(full):
            dirs.append(item)
        else:
            files.append(item)
    dirs.sort()
    files.sort()

    try:
        if term.is_color():
            prev = term.get_text_color()
            term.set_text_color(0x2000)  # green
            for d in dirs:
                print(d)
            term.set_text_color(prev)
            for f in files:
                print(f)
            return
    except Exception:
        pass

    for d in dirs:
        print(d)
    for f in files:
        print(f)


main()
