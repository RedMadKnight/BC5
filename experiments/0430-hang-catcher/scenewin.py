#!/usr/bin/env python3
"""BC5 exp 0430: per-window flips/s of one scene run against its sampler (MemAvailable, PSI memory, CPU of the busiest
threads). usage: scenewin.py <raw dir> <tag> <G s> [window s]
<tag>-fps.txt: t flips span longest_gap_ms per line; <tag>-sampler.txt: exp 0412's sampler0412b.sh lines."""
import re
import sys

raw, tag, g = sys.argv[1], sys.argv[2], float(sys.argv[3])
W = float(sys.argv[4]) if len(sys.argv) > 4 else 60.0
fp = []
for l in open(f"{raw}/{tag}-fps.txt"):
    p = l.split()
    if len(p) >= 4:
        fp.append((float(p[0]), int(p[1]), float(p[2]), float(p[3])))
sm = []
for l in open(f"{raw}/{tag}-sampler.txt", errors="replace"):
    if l.startswith("#"):
        continue
    p = [x.strip() for x in l.split("|")]
    if len(p) < 4:
        continue
    try:
        t = float(p[0]); av = int(p[1].split()[0]); psi = float(p[2].split()[0].split("/")[0])
    except (ValueError, IndexError):
        continue
    top = p[-1]
    sm.append((t, av, psi, top))


def rate(a, b):
    s = [x for x in fp if a <= x[0] < b]
    if not s:
        return None
    return sum(x[1] for x in s) / sum(x[2] for x in s), sum(1 for x in s if x[3] > 100), max(x[3] for x in s)


tot = rate(g, 1e9)
print(f"{tag}: gameplay from G {g:.0f} s: {tot[0]:.1f} flips/s, {tot[1]} s with a gap over 100 ms, longest {tot[2]:.0f} ms")
a = g
while True:
    r = rate(a, a + W)
    if r is None:
        break
    v = [x for x in sm if a <= x[0] < a + W]
    mem = f"avail min {min(x[1] for x in v)} psi mem max {max(x[2] for x in v):.2f}" if v else "no sampler"
    print(f"  G+{a - g:4.0f}: {r[0]:5.1f} flips/s, gaps>100 {r[1]:2d}, longest {r[2]:6.0f} ms | {mem}")
    a += W
