#!/usr/bin/env python3
# BC5 experiment 0250: the G-buffer target's render size per journalled frame against the lake's patch level.
# Pairs every window of a jr0240.py summary (exp 0240's script; frame lines carry "rt0 113f230000 <w>x<h>") with the
# bench's frozen-view shots before and after it by wall time, and prints the size of each frame in the window. It asks
# whether patched windows run at one size, or follow a size switch (the top session's HTILE hypothesis, 2026-10-23).
# Runs on the committed summaries only.
# usage: python3 -I sz0250.py <jr.txt> <bench.txt> [<jr.txt> <bench.txt> ...]
import re, sys

args = sys.argv[1:]
for jr, bench in zip(args[::2], args[1::2]):
    shots = []
    for l in open(bench):
        m = re.match(r"\s*(\d{6})-(ts\d\d)\.png: patch\s+([\d.]+) %", l)
        if m:
            shots.append((m[1], m[2], float(m[3])))
    wins, cur = [], None
    for l in open(jr):
        m = re.match(r"== window at t ([\d.]+) \(wall (\d\d):(\d\d):(\d\d)\)", l)
        if m:
            cur = (m[1], m[2] + m[3] + m[4], [])
            wins.append(cur)
            continue
        m = re.match(r"  frame (\d+):", l)
        if m and cur:
            cur[2].append("/".join(sorted(set(re.findall(r"rt0 113f230000 (\d+x\d+)", l)))) or "-")
    print("# %s against %s: %d windows" % (jr, bench, len(wins)))
    for t, w, sizes in wins:
        prev = [s for s in shots if s[0] <= w]
        nxt = [s for s in shots if s[0] >= w]
        fmt = lambda s: "%s %4.1f %%" % (s[1], s[2]) if s else "-      "
        print("  t %-7s wall %s:%s:%s  prev %s  next %s | %s" % (
            t, w[:2], w[2:4], w[4:], fmt(prev[-1] if prev else None), fmt(nxt[0] if nxt else None), " ".join(sizes)))
