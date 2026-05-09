"""Print a file's contents (Python-side extension; no direct Lua equivalent).

Lua's CraftOS doesn't ship a ``cat``; users open files with ``edit``. We add
this small helper because the previous Python preview supported viewing
files at the prompt and it is a familiar Unix-style command. It is kept
deliberately small so it can be removed later if a ``more``/``edit`` port
takes over its role.
"""


def main():
    if len(arg) < 2:
        program_name = arg[0] if arg else "cat"
        print("Usage: " + program_name + " <file>")
        return

    path = shell.resolve(arg[1])
    if not fs.exists(path):
        printError("No such file: " + arg[1])
        return
    if fs.is_dir(path):
        printError("Is a directory: " + arg[1])
        return

    # Use ``fs.read_all`` (host ``fsReadAll``) like ``Shell._execute_program`` — ``fs.open``
    # + ``PythonFileHandle`` has been unreliable under GraalPy for guest programs.
    try:
        data = fs.read_all(path)
    except FileNotFoundError:
        printError("No such file: " + arg[1])
        return
    except Exception as e:
        printError(str(e))
        return
    print(str(data))


main()
