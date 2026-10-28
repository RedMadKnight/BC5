#!/usr/bin/env python3
# BC5 experiment 0369: exp 0362's run H1, its poll log (raw/H1.events.txt.gz: "<mono> <wall> D<0|1> P<0|1>") against its
# draw journal's full-screen water draws ("bake draw buf N at 222: t T wall W", the submit time on the CPU, ms). For each
# pyramid change (a frame start: a P change 1 ms or more after the previous one) and each depth-sample burst (D changes
# with gaps under 0.5 ms), the time since the latest water-draw submit before it, and since the frame start.
# usage: python3 -I al0369.py <H1.events.txt.gz> <direct.log>   (prints a summary only)
import bisect, gzip, re, statistics, sys

ev = [l.split() for l in gzip.open(sys.argv[1], "rt")]
water = sorted(float(m[2]) for m in (re.search(r"bake draw buf \d+ at 222: t ([0-9.]+) wall ([0-9.]+)", l) for l in open(sys.argv[2], errors="replace")) if m)
P, D = [], []
last_p = -1.0
for mono, wall, d, p in ev:
    w = float(wall)
    if p == "P1":
        if w - last_p >= 0.001:
            P.append(w)
        last_p = w
    if d == "D1":
        D.append(w)
bursts = []
for w in D:
    if bursts and w - bursts[-1][1] < 0.0005:
        bursts[-1][1] = w
    else:
        bursts.append([w, w])


def since_water(t):
    i = bisect.bisect_right(water, t) - 1
    return (t - water[i]) * 1000 if i >= 0 else None


def since_p(t):
    i = bisect.bisect_right(P, t) - 1
    return (t - P[i]) * 1000 if i >= 0 else None


def q(v):
    v = sorted(x for x in v if x is not None)
    return "n %d, 10 %% %.1f, median %.1f, 90 %% %.1f ms" % (len(v), v[len(v) // 10], statistics.median(v), v[9 * len(v) // 10]) if v else "none"


gaps = [(b - a) * 1000 for a, b in zip(water, water[1:])]
print("# water-draw submits: %d, spacing %s" % (len(water), q(gaps)))
print("# frame starts (P): %d; since the latest water submit: %s" % (len(P), q([since_water(t) for t in P])))
for k, (lo, hi) in enumerate(((0, 7.5), (7.5, 12), (15, 22))):
    sel = [b for b in bursts if since_p(b[0]) is not None and lo <= since_p(b[0]) < hi]
    print("# bursts starting %.1f-%.1f ms after the frame start: %s; since the latest water submit: %s" % (
        lo, hi, q([since_p(b[0]) for b in sel]), q([since_water(b[0]) for b in sel])))
