"""Manage shell aliases (port of ``rom/programs/alias.lua``)."""


def main():
    if len(arg) > 3:
        program_name = arg[0] if arg else "alias"
        print("Usage: " + program_name + " <alias> <program>")
        return

    alias = arg[1] if len(arg) >= 2 else None
    program = arg[2] if len(arg) >= 3 else None

    if alias and program:
        shell.set_alias(alias, program)
    elif alias:
        shell.clear_alias(alias)
    else:
        items = []
        for k, v in shell.aliases().items():
            items.append(k + ":" + v)
        items.sort()
        for line in items:
            print(line)


main()
