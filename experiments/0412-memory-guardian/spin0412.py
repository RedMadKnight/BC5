#!/usr/bin/env python3
"""BC5 exp 0412 (README section 25): is the guest's code in the long frames a tight loop? The guest-code samples of
one thread (perf cpu-clock, user space) inside the frames over <ms> of the play phase and outside them: how many
distinct addresses hold half and 90 % of the samples, and the heaviest addresses with the pages they lie in.
A wait loop shows as a handful of addresses with most of the samples; real work spreads over thousands.
usage: spin0412.py <prefix> <thread name> [<ms> default 100] [<load at s> default 104]"""
import collections
import gzip
import re
import statistics
import sys

GAP = re.compile(r"gap \(exp 0412, tag gp412\): t ([\d.]+) s mono ([\d.]+): ([\d.]+) ms")
CL = re.compile(r"^\s*(\d+)\s+([\d.]+):\s+([0-9a-f]+)\s+(.*?)\s+\(([^()]*(?:\([^()]*\))?[^()]*)\)\s*$")


def main():
    p, name = sys.argv[1], sys.argv[2]
    lim = float(sys.argv[3]) if len(sys.argv) > 3 else 100.0
    load_at = float(sys.argv[4]) if len(sys.argv) > 4 else 104.0
    gaps = [(float(m.group(1)), float(m.group(2)), float(m.group(3))) for m in (GAP.search(ln) for ln in open(p + "-gaps.txt", errors="replace")) if m]
    off = statistics.median(g[1] - g[0] for g in gaps)
    P0 = load_at + 28 + off
    iv = sorted((mono - ms / 1000, mono) for t, mono, ms in gaps if ms > lim and mono >= P0)
    log = open(p + ".log").read()
    m = re.search(r"threads (.*?) = ([\d,]+),", log)
    tl = m.group(2).split(",")
    tid = tl[0] if name.startswith("Render") else tl[1]
    inside, outside = collections.Counter(), collections.Counter()
    with gzip.open(p + "-clock.txt.gz", "rt", errors="replace") as f:
        for ln in f:
            m = CL.match(ln)
            if not m or m.group(1) != tid:
                continue
            t = float(m.group(2))
            if t < P0 or m.group(4).strip() != "[unknown]" or "kyty_emulator" in m.group(5) or ".so" in m.group(5):
                continue
            (inside if any(a <= t <= b for a, b in iv) else outside)[m.group(3)] += 1
    for label, c in (("inside frames over %.0f ms" % lim, inside), ("in the other frames", outside)):
        n = sum(c.values())
        if n == 0:
            continue
        acc, half, ninety = 0, None, None
        for k, (a, v) in enumerate(c.most_common(), 1):
            acc += v
            if half is None and acc >= n / 2:
                half = k
            if ninety is None and acc >= 0.9 * n:
                ninety = k
        print(f"{name}, guest code {label}: {n} samples at {len(c)} addresses; half of them at {half} addresses, 90 % at {ninety}")
        pages = collections.Counter()
        for a, v in c.items():
            pages[a[:-3]] += v
        print("   heaviest addresses: " + ", ".join(f"{a} {100 * v / n:.1f} %" for a, v in c.most_common(8)))
        print("   heaviest 4 KiB pages: " + ", ".join(f"{a}xxx {100 * v / n:.1f} %" for a, v in pages.most_common(5)))


if __name__ == "__main__":
    main()
