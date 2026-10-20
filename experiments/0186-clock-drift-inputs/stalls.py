#!/usr/bin/env python3
# BC5 (experiment 0186): long frames (the title's vblank step between two of its reads >= N) after a
# start time, with the clock voice's pass speed around each, from the "vs" lines of
# KYTY_BC5_FLIP_STATUS_TRACE and the AJM index.
# usage: stalls.py <log> <ajm-index.txt> <from s> [min vblank step, default 8]
import sys, bisect
log, idx, t0 = sys.argv[1], sys.argv[2], float(sys.argv[3])
mn = int(sys.argv[4]) if len(sys.argv) > 4 else 8
passes = []  # (start, end, speed)
prev = {}; s0 = {}; seg0 = {}
for l in open(idx):
    q = l.split()
    if len(q) < 5: continue
    t = float(q[0]); i = q[1]; s = int(q[4])
    if i in prev and s < prev[i]:
        if prev[i] - s0[i] == 479352:
            passes.append((seg0[i], t, 479352 / 48000 / (t - seg0[i])))
        seg0[i] = t; s0[i] = s
    if i not in prev:
        seg0[i] = t; s0[i] = s
    prev[i] = s
passes.sort()
ends = [p[1] for p in passes]


def speed_at(t):
    k = bisect.bisect_left(ends, t)
    return passes[k][2] if k < len(passes) and passes[k][0] <= t else float("nan")


last = None; n = 0
for line in open(log, errors="replace"):
    if not line.startswith("vs "): continue
    p = line.split(); t = float(p[1]); c = int(p[3])
    if last is not None and t >= t0 and c - last[1] >= mn:
        n += 1
        print("%8.2f s: %3d vblanks (%.0f ms) between reads | clock before %.2fx, after %.2fx" % (
            t, c - last[1], (c - last[1]) * 1000 / 60, speed_at(last[0] - 4), speed_at(t + 4)))
    last = (t, c)
print("%d long frames" % n)
