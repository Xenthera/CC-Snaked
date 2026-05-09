"""Show help (placeholder port of ``rom/programs/help.lua``).

The Lua implementation reads markdown topics from ``/rom/help`` and renders
them with paged output and section navigation. We don't have ``cc.help`` or
markdown rendering wired yet, so this version prints a short summary of
available shell commands.

Full help-topic rendering is on the roadmap; this stub remains useful while
that work is planned.
"""


def main():
    topic = arg[1] if len(arg) >= 2 else "intro"

    if topic in ("intro", "help"):
        print("CraftOS (Python preview) shell help")
        print("")
        print("Built-in commands (resolve via shell.run -> rom/programs/*):")
        print("  cd <path>        Change directory")
        print("  list [path]      List directory (alias: ls, dir)")
        print("  mkdir <path>     Create directory")
        print("  delete <path>    Delete a file/dir (alias: rm)")
        print("  copy <a> <b>     Copy a file/dir (alias: cp)")
        print("  move <a> <b>     Move a file/dir (alias: mv)")
        print("  rename <a> <b>   Rename a file/dir")
        print("  type <path>      Print the type of a path")
        print("  cat <file>       Print a file's contents (Python-side extension)")
        print("  clear            Clear the screen")
        print("  exit             Exit the shell")
        print("  reboot           Reboot the computer")
        print("  shutdown         Power off the computer")
        print("  programs [all]   List available programs")
        print("  alias [a] [p]    Manage aliases")
        print("  help [topic]     Show help (this screen)")
        print("")
        print("Note: full markdown help topics aren't yet ported.")
        return

    print("No help available")


main()
