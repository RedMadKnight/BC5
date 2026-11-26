#!/usr/bin/env python3
"""BC5 exp 0412, stage 0 of DESIGN-device-mutex.md: the device mutex's long holds beside the frame gaps.
Input: the "lock hold" / "lock wait" lines of a run with BC5_GUARD_LOCK_STAT=1 on build g412l (each stamped with the
journal's clock at its END, in seconds) and the run's frames file (run0412n.sh: "<t s> <ms since the last flip> ...",
the same clock, t at the END of the frame). A frame with <ms> over the gap limit is a gap, the interval [t - ms, t].
Printed: per phase of the scripted run, the gaps, how many have a long hold or a long wait of the Render Thread
inside (an overlap of at least 10 ms), the share of the gaps' time that such holds cover, and the holds by thread
and largest part; and the other way round, the long holds that lie in no gap.
usage: holds0412.py <lock lines file> <frames file> [<gap ms> default 100] [<load at s> default 104]"""
import collections
import re
import sys

HOLD = re.compile(r"hold .*?: t ([\d.]+) s: (.*?) held ([\d.]+) ms:(.*)")
WAIT = re.compile(r"wait .*?: t ([\d.]+) s: (.*?) waited ([\d.]+) ms behind (.*)")
PART = re.compile(r" ([a-z ]+?) ([\d.]+)(?= [a-z]|$)")


def main():
    gap_ms = float(sys.argv[3]) if len(sys.argv) > 3 else 100.0
    load_at = float(sys.argv[4]) if len(sys.argv) > 4 else 104.0
    holds, waits = [], []
    for ln in open(sys.argv[1], errors="replace"):
        m = HOLD.search(ln)
        if m:
            t, ms = float(m.group(1)), float(m.group(3))
            parts = [(p, float(v)) for p, v in PART.findall(m.group(4).rstrip())]
            big = max(parts, key=lambda x: x[1])[0] if parts else "?"
            holds.append((t - ms / 1000, t, m.group(2), big, ms))
            continue
        m = WAIT.search(ln)
        if m:
            t, ms = float(m.group(1)), float(m.group(3))
            waits.append((t - ms / 1000, t, m.group(2), m.group(4).strip(), ms))
    frames = []
    for ln in open(sys.argv[2]):
        p = ln.split()
        if len(p) >= 2:
            frames.append((float(p[0]), float(p[1])))
    gaps = [(t - ms / 1000, t, ms) for t, ms in frames if ms > gap_ms]
    print(f"{len(frames)} frames, {len(gaps)} gaps over {gap_ms:.0f} ms ({sum(g[2] for g in gaps) / 1000:.1f} s); "
          f"{len(holds)} holds of 30 ms or more ({sum(h[4] for h in holds) / 1000:.1f} s), {len(waits)} waits of 30 ms or more "
          f"({sum(w[4] for w in waits) / 1000:.1f} s; Render Thread {sum(w[4] for w in waits if w[2] == 'Render Thread') / 1000:.1f} s)")
    ov = lambda a0, a1, b0, b1: max(0.0, min(a1, b1) - max(a0, b0))
    phases = (("menus", 0, 33), ("scene load", 33, 62), ("menu and list", 62, load_at), ("save load", load_at, load_at + 28), ("play", load_at + 28, 1e9))
    for name, lo, hi in phases:
        gs = [g for g in gaps if lo <= g[1] < hi]
        if not gs:
            print(f" -- {name}: no gap")
            continue
        with_hold = with_wait = 0
        covered = 0.0
        by = collections.Counter()
        for g0, g1, ms in gs:
            hs = [(ov(g0, g1, h[0], h[1]), h) for h in holds]
            hs = [(o, h) for o, h in hs if o >= 0.010]
            cov = min(ms / 1000, sum(o for o, _ in hs))
            covered += cov
            if hs:
                with_hold += 1
                o, h = max(hs, key=lambda x: x[0])
                by[(h[2], h[3])] += 1
            if any(ov(g0, g1, w[0], w[1]) >= 0.010 and w[2] == "Render Thread" for w in waits):
                with_wait += 1
        tot = sum(g[2] for g in gs) / 1000
        print(f" -- {name}: {len(gs)} gaps, {tot:.1f} s; with a long hold inside {with_hold} ({100 * with_hold / len(gs):.0f} %), "
              f"with a long wait of the Render Thread inside {with_wait} ({100 * with_wait / len(gs):.0f} %); the holds cover {covered:.1f} s ({100 * covered / tot:.0f} %) of the gaps' time")
        for (th, part), c in by.most_common(6):
            print(f"        {c:4d} gaps: the longest hold inside is {th}'s, mostly {part}")
    out = [h for h in holds if not any(ov(g[0], g[1], h[0], h[1]) >= 0.010 for g in gaps)]
    print(f"long holds in no gap: {len(out)} of {len(holds)} ({sum(h[4] for h in out) / 1000:.1f} s)")
    c = collections.Counter()
    for h in holds:
        c[(h[2], h[3])] += h[4]
    print("long holds by thread and largest part (s): " + ", ".join(f"{k[0]} {k[1]} {v / 1000:.1f}" for k, v in c.most_common(10)))


if __name__ == "__main__":
    main()
