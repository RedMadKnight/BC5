#!/usr/bin/env python3
"""BC5 experiment 0400: lake_probe's regaudit lines against the register database. Prints each register where the chip read something else
than the stream set in most audits, with its name, and the system registers' values. Read on the laptop.
usage: audit0400.py <tag>.audit.txt <regdb gfx10.json>"""
import json
import sys

BASE = {1: 0x28000, 2: 0xb000, 3: 0x30000}
SPACE = {1: "context", 2: "sh", 3: "uconfig"}


def names(path):
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    return {m["map"]["at"]: m["name"] for m in d["register_mappings"] if "map" in m and "at" in m["map"]}


def rows(text):
    for line in text.splitlines():
        w = line.split()
        if len(w) == 6:
            yield int(w[0]), int(w[2]), int(w[3], 16), None if w[4] == "-" else int(w[4], 16), int(w[5], 16)


def main():
    with open(sys.argv[1], encoding="utf-8") as f:
        text = f.read()
    db = names(sys.argv[2])
    seen = {}
    audits = set()
    for n, space, off, stream, chip in rows(text):
        audits.add(n)
        seen.setdefault((space, off), []).append((n, stream, chip))
    same = sum(all(s == c for _, s, c in v if s is not None) and any(s is not None for _, s, _ in v) for v in seen.values())
    print(f"# {len(audits)} audits, {len(seen)} registers, {same} always equal")
    for (space, off), v in sorted(seen.items()):
        name = db.get(BASE[space] + off * 4, "?")
        if all(s is None for _, s, _ in v):
            print(f"unset {SPACE[space]} 0x{off:x} {name}: chip {' '.join(sorted({hex(c) for _, _, c in v}))}")
            continue
        bad = [(s, c) for _, s, c in v if s is not None and s != c]
        if bad:
            print(f"differs {SPACE[space]} 0x{off:x} {name}: {len(bad)} of {len(v)}, stream {' '.join(sorted({hex(s) for s, _ in bad})[:3])} chip {' '.join(sorted({hex(c) for _, c in bad})[:3])}")


if __name__ == "__main__":
    main()
