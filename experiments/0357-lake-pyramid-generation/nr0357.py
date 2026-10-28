#!/usr/bin/env python3
# BC5 experiment 0357: frames without a pyramid rebuild. cyp0357.py's cycles (from one pyramid change to the next, after
# >= 5 ms without one) that last more than 1.5 x the median mean a frame whose pyramid was not rebuilt; this counts them
# and sets each full read's state (ph0357.py's labels with the floor) against whether the cycle before its frame's was
# such a long one. Summaries only.
# usage: python3 -I nr0357.py <events.txt> <b01.times.txt> <labels json>
import bisect, collections, json, re, statistics, sys

rows = []
for l in open(sys.argv[1]):
    f = l.split()
    rows.append((float(f[0]), "1" in f[3][1:]))
pts = [t for t, p in rows if p]
st = [t for i, t in enumerate(pts) if i == 0 or t - pts[i - 1] >= 0.005]
per = [b - a for a, b in zip(st, st[1:])]
med = statistics.median(per)
longc = [p for p in per if p > 1.5 * med]
print("# %d cycles, median %.1f ms; longer than 1.5 x the median: %d (%.1f %%): %s ms" % (
    len(per), 1000 * med, len(longc), 100 * len(longc) / len(per), sorted(round(1000 * p) for p in longc)[:30]))
lab = json.load(open(sys.argv[3]))["labels"]
c = collections.Counter()
for l in open(sys.argv[2]):
    m = re.match(r"(\S+) wall ([\d.]+) mono ([\d.]+)", l)
    if not m or "b01." + m[1] not in lab:
        continue
    k = bisect.bisect_right(st, float(m[3])) - 1
    if k < 1 or k >= len(st):
        continue
    c[(lab["b01." + m[1]], st[k] - st[k - 1] > 1.5 * med)] += 1
print("  state x (the cycle before the read's was a long one): %s" % ", ".join("%s %s: %d" % (s, "after a long cycle" if f else "normal", n) for (s, f), n in sorted(c.items())))
