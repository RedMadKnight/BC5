#!/usr/bin/env python3
"""BC5 exp 0412 (README section 28): one line of numbers per run of the fast2 / fast3 ABBA.
From <dir>/<tag>-frames.txt (journal t, ms since the last flip), <tag>-holds.txt (lock hold lines of 30 ms or more,
the lazy release's and the return-aware release's lines), <tag>-guard.txt (the ledger's lines) and <tag>-summary.txt:
flips/s in the scene load, the save load and the play phase; the play phase's length, its frames over 100 ms (count
and seconds) and over 50 ms; the holds of 30 ms and of 100 ms or more in play (count, seconds); pinned at 140 s and
at the last ledger line; the release's cut / returned / exempt MiB at the end.
usage: abq0412.py <dir> <tag> [<tag> ...]   (load at 104 s)"""
import os
import re
import sys


def main():
    d, tags = sys.argv[1], sys.argv[2:]
    P0 = 132.0
    for tag in tags:
        fr = [(float(a), float(b)) for a, b, *_ in (ln.split() for ln in open(os.path.join(d, tag + "-frames.txt")) if ln.strip())]
        end = fr[-1][0]
        fps = lambda lo, hi: sum(1 for t, _ in fr if lo <= t < hi) / max(1e-9, min(hi, end) - lo) if end > lo else 0.0
        pf = [ms for t, ms in fr if t >= P0]
        over100 = [ms for ms in pf if ms > 100]
        over50 = [ms for ms in pf if ms > 50]
        holds = []
        cut = back = exempt = None
        for ln in open(os.path.join(d, tag + "-holds.txt"), errors="replace"):
            m = re.search(r"lock hold \(exp 0412, tag lk412\): t ([\d.]+) s: (.*?) held ([\d.]+) ms", ln)
            if m and float(m.group(1)) >= P0:
                holds.append(float(m.group(3)))
            m = re.search(r"cut ([\d.]+) MiB in \d+ BOs .*?back ([\d.]+) MiB", ln)
            if m:
                cut, back = float(m.group(1)), float(m.group(2))
            m = re.search(r"return-aware release .*?: cut ([\d.]+) MiB in all, returned ([\d.]+) MiB, exempt now ([\d.]+) MiB", ln)
            if m:
                cut, back, exempt = float(m.group(1)), float(m.group(2)), float(m.group(3))
        pins = {}
        for ln in open(os.path.join(d, tag + "-guard.txt"), errors="replace"):
            m = re.match(r"guard: t (\d+) s: pinned direct ([\d.]+) MiB.*?orphans ([\d.]+);.*?avail (\d+) ", ln)
            if m:
                pins[int(m.group(1))] = (float(m.group(2)), float(m.group(3)), int(m.group(4)))
        last = max(pins) if pins else 0
        p140 = pins.get(140, (0, 0, 0))
        pl = pins.get(last, (0, 0, 0))
        summ = open(os.path.join(d, tag + "-summary.txt")).read()
        killed = "WATCHDOG" in summ
        print(f"{tag}: ended at {end:.0f} s{' (watchdog)' if killed else ''}; flips/s scene {fps(33, 62):.1f}, save load {fps(104, 132):.1f}, play {fps(132, end):.1f}; "
              f"play {len(pf)} frames in {sum(pf) / 1000:.1f} s: over 100 ms {len(over100)} = {sum(over100) / 1000:.1f} s, over 50 ms {len(over50)} = {sum(over50) / 1000:.1f} s, longest {max(pf) if pf else 0:.0f} ms; "
              f"holds in play: 30 ms+ {len(holds)} = {sum(holds) / 1000:.1f} s, 100 ms+ {sum(1 for h in holds if h >= 100)} = {sum(h for h in holds if h >= 100) / 1000:.1f} s; "
              f"pinned at 140 s {p140[0]:.0f} MiB (orphans {p140[1]:.0f}, available {p140[2]}), at {last} s {pl[0]:.0f} MiB (orphans {pl[1]:.0f}, available {pl[2]}); "
              f"release: cut {cut}, returned {back}, exempt now {exempt} MiB")


if __name__ == "__main__":
    main()
