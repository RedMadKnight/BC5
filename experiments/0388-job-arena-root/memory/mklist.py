#!/usr/bin/env python3
"""BC5 exp 0388, memory cycle: the zero list for a moving play, from the existing scans only.
Keeps what was zero in both the maintainer's play scan and the bench scan, minus every run a canary has hit.
usage: mklist.py <play list> <bench list> <out>"""
import sys

# Every canary hit recorded so far, as (offset from the heap's start, size). The heaps sat at file 0x156c00000 and
# 0x226200000: runs 22 (F542) and 37 in RenderGpuWcLarge, run 49 (F629) in CommitIABufferAllocator.
HITS = {"RenderGpuWcLarge": [(0x57a00000, 0x1200000), (0x74800000, 0x1800000)], "CommitIABufferAllocator": [(0xa800000, 0x800000)]}


def read(path):
    heaps, order = {}, []
    for line in open(path, encoding="utf-8"):
        w = line.split()
        if not w or w[0].startswith("#"):
            continue
        if w[0] == "heap":
            heaps[w[1]] = {"size": int(w[2], 16), "scans": int(w[3]), "runs": []}
            order.append(w[1])
        elif w[0] == "zero":
            heaps[w[1]]["runs"].append((int(w[2], 16), int(w[3], 16)))
        else:
            raise SystemExit(f"unknown line: {line!r}")
    return heaps, order


def cut(runs, a, b):
    """The parts of runs inside [a, b)."""
    return [(max(o, a), min(o + n, b) - max(o, a)) for o, n in runs if max(o, a) < min(o + n, b)]


def main():
    play, order = read(sys.argv[1])
    bench, _ = read(sys.argv[2])
    out = ["# bc5 zero list v1 (experiment 0379): chunks all-zero in every scan, offsets from the heap's start"]
    total = dropped = 0
    for name in order:
        p, b = play[name], bench[name]
        assert p["size"] == b["size"], name
        both = []
        for o, n in p["runs"]:
            for bo, bn in b["runs"]:
                both += cut([(o, n)], bo, bo + bn)
        both.sort()
        kept = [r for r in both if not any(r[0] < a + l and a < r[0] + r[1] for a, l in HITS[name])]
        kept = [r for r in kept if r[1] >= 0x800000]
        dropped += sum(n for _, n in p["runs"]) - sum(n for _, n in kept)
        total += sum(n for _, n in kept)
        out.append(f"heap {name} {p['size']:#x} {min(p['scans'], b['scans'])}")
        out += [f"zero {name} {o:#x} {n:#x}" for o, n in kept]
    open(sys.argv[3], "w", encoding="utf-8", newline="\n").write("\n".join(out) + "\n")
    print(f"listed {total / 1048576:.0f} MiB, left out {dropped / 1048576:.0f} MiB of the play list")


main()
