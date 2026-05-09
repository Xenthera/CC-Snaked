"""Print a path's type (port of ``rom/programs/type.lua``).

Note: in ``startup.py`` the alias ``cat`` is also bound to this program for
ease of use, but the Lua original simply reports ``file``/``directory``/``no
such path``. We keep that exact behavior here.
"""


def main():
    if len(arg) < 2:
        program_name = arg[0] if arg else "type"
        print("Usage: " + program_name + " <path>")
        return

    path = shell.resolve(arg[1])
    if fs.exists(path):
        if fs.is_dir(path):
            print("directory")
        else:
            print("file")
    else:
        print("No such path")


main()
