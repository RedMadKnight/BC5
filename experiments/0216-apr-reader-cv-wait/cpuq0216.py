#!/usr/bin/env python3
# BC5 experiment 0216: per sampling interval, the CPU (ms) of the APR workers (bc5-apr-qN) and of each queue's readers
# (bc5-apr-rN, summed), from cpu0214.sh / cpu0216.sh files; the longest-run thread of each name. usage: cpuq0216.py <cpu file> ...
import sys, collections
for path in sys.argv[1:]:
    s = []; cur_t = None; cur = {}
    for line in open(path):
        f = line.split()
        if not f or f[0] != "t": continue
        t = float(f[1])
        if cur_t is not None and t != cur_t: s.append((cur_t, cur)); cur = {}
        cur_t = t
        v = int(f[3])
        if f[2] not in cur or v > cur[f[2]]: cur[f[2]] = v
    s.append((cur_t, cur))
    print("==", path)
    tot = collections.Counter()
    for (t0, a), (t1, b) in zip(s, s[1:]):
        g = collections.Counter()
        for n, v in b.items():
            if n in a:
                key = n[:10] if n.startswith("bc5-apr-r") else n
                g[key] += (v - a[n]) / 1e6
        tot.update(g)
        print(f"{t1 - s[0][0]:5.0f} " + " ".join(f"{k}:{g[k]:7.1f}" for k in sorted(g)))
    print("total s:", {k: round(v / 1e3, 2) for k, v in sorted(tot.items())})
