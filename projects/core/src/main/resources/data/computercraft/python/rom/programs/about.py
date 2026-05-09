"""About this CraftOS build (port of ``rom/programs/about.lua``)."""


def main():
    try:
        if term.is_color():
            term.set_text_color(0x10)  # yellow
    except Exception:
        pass
    print("CraftOS 1.9 (Python preview)")
    try:
        term.set_text_color(0x1)  # white
    except Exception:
        pass


main()
