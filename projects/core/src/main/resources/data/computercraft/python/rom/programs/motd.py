"""Print a message of the day (port of ``rom/programs/motd.lua``)."""

import random

from cc import fs
from cc import settings


def _read_lines(path: str) -> list[str]:
    try:
        raw = fs.read_all(path)
    except Exception:
        return []
    lines = str(raw).replace("\r\n", "\n").replace("\r", "\n").split("\n")
    return [l for l in (s.strip("\n") for s in lines) if l != ""]


def main():
    motd_path = settings.get("motd.path") or "/rom/motd.txt:/motd.txt"
    candidates: list[str] = []
    for p in str(motd_path).split(":"):
        p = p.strip()
        if not p:
            continue
        if fs.exists(p) and not fs.is_dir(p):
            candidates.extend(_read_lines(p))

    if not candidates:
        print("missingno")
        return
    print(random.choice(candidates))


main()
