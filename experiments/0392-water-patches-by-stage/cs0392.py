#!/usr/bin/env python3
"""BC5 experiment 0392: does anything in what the water's draws are told differ between clean and hole frames? On the box. The entries
are the title's, so only places and counts leave it, never a value.
Reads lake_probe's <out>.inputs, each entry split into its parts (draw, registers, programs, user data of HS, GS, PS, constants of each), and
the frames' states from zp0392.py's table. For the four draws of a frame, per dword position: how many values it takes in clean and in hole
frames, and how many of the hole frames hold a value no clean frame holds. A position separates if SEP of the hole frames do and it isn't a
position that changes every frame in both states (a counter or a pointer: DISTINCT of each state's frames have their own value).
usage: cs0392.py <zpass.dat.inputs> <zpass.dat.meta> <tag>.frames.tsv.gz"""
import gzip
import struct
import sys

MAGIC, REGS, PROGRAMS, USER_DATA = 0x57415452, 11, 4, 32
SEP, DISTINCT, MIN_FRAMES = 0.9, 0.5, 10


def parts(words):
    """{part name: words} of one entry, or None if it doesn't parse."""
    if len(words) < 3 or words[0] != MAGIC or words[1] != len(words):
        return None
    at, out = 3 + words[2], {"draw": words[3:3 + words[2]]}
    out["regs"] = words[at:at + REGS + PROGRAMS]
    at += REGS + PROGRAMS
    for s in ("hs", "gs", "ps"):
        out["ud_" + s] = words[at:at + USER_DATA]
        at += USER_DATA
    for s in ("hs", "gs", "ps"):
        if at >= len(words):
            return None
        n = words[at]
        out["c_" + s] = words[at + 1:at + 1 + n]
        at += 1 + n
    return out if at == len(words) else None


def read_entries(raw, meta):
    """{job: [parts of each draw, in order]}."""
    out = {}
    bad = 0
    for line in meta.splitlines():
        w = line.split()
        if len(w) != 7 or w[6] != "i":
            continue
        at = int(w[0]) * 4
        if at + 8 > len(raw):
            bad += 1
            continue
        magic, n = struct.unpack_from("<II", raw, at)
        if magic != MAGIC or at + n * 4 > len(raw) or n < 3:
            bad += 1
            continue
        p = parts(list(struct.unpack_from(f"<{n}I", raw, at)))
        if p is None:
            bad += 1
        else:
            out.setdefault(w[1], []).append(p)
    return out, bad


def separators(entries, state):
    """[(draw, part, dword, hole frames with their own value, values in clean, values in hole)], and how many positions were read."""
    table, read = {}, 0
    for job, draws in entries.items():
        s = state.get(job)
        if s not in ("clean", "hole"):
            continue
        for d, p in enumerate(draws):
            for part, words in p.items():
                for k, v in enumerate(words):
                    table.setdefault((d, part, k), {"clean": [], "hole": []})[s].append(v)
    out = []
    for (d, part, k), v in sorted(table.items()):
        c, h = v["clean"], v["hole"]
        if len(c) < MIN_FRAMES or len(h) < MIN_FRAMES:
            continue
        read += 1
        seen = set(c)
        own = sum(x not in seen for x in h) / len(h)
        if own < SEP:
            continue
        if len(set(c)) >= DISTINCT * len(c) and len(set(h)) >= DISTINCT * len(h):
            continue
        out.append((d, part, k, own, len(seen), len(set(h))))
    return out, read


def summarise(raw, meta, tsv):
    lines = tsv.splitlines()
    state = {}
    if lines:
        head = lines[0].split("\t")
        j, s = head.index("job"), head.index("state")
        for line in lines[1:]:
            w = line.split("\t")
            state[w[j]] = w[s]
    entries, bad = read_entries(raw, meta)
    n = {k: sum(state.get(j) == k for j in entries) for k in ("clean", "hole")}
    out = [f"# {len(entries)} frames of entries, {bad} unreadable; clean {n['clean']}, hole {n['hole']}"]
    if n["clean"] < MIN_FRAMES or n["hole"] < MIN_FRAMES:
        out.append("# NO TEST: too few clean or hole frames")
        return "\n".join(out) + "\n"
    rows, read = separators(entries, state)
    out.append(f"# {read} positions read, {len(rows)} separate the states")
    for d, part, k, own, a, b in rows:
        out.append(f"separates draw {d} {part} dword {k}: {own:.3f} of hole frames hold a value no clean frame holds; values clean {a}, hole {b}")
    return "\n".join(out) + "\n"


def main():
    a = sys.argv[1:]
    with open(a[0], "rb") as f:
        raw = f.read()
    with open(a[1], encoding="utf-8", errors="replace") as f:
        meta = f.read()
    with gzip.open(a[2], "rt") as f:
        tsv = f.read()
    sys.stdout.write(summarise(raw, meta, tsv))


if __name__ == "__main__":
    main()
