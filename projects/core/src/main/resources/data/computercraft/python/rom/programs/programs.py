"""List installed programs (port of ``rom/programs/programs.lua``)."""


def main():
    include_hidden = len(arg) > 1 and arg[1] == "all"
    progs = shell.programs(include_hidden)
    for p in progs:
        print(p)


main()
