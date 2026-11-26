#!/usr/bin/env python3
# BC5 experiment 0210: per-session frame statistics from the direct journal's "frame profile" lines (one per flip).
# Reads the lines on stdin (LC_ALL=C grep -a '^frame profile: t ' direct.log | frameprof.py <name> [window s]).
# Per session: flips, span, flips/s per window (min/median/max), flip gaps over 0.1/0.4/2 s and the longest, the GPU
# time per frame ("GPU busy X ms", median/p90/max), the game thread's time outside the host per frame (count over
# 0.1 s and 1 s), and a timeline per window: flips/s, GPU busy per second, outside-host per second, inside-host per
# second -- a slow window with GPU busy near 1000 ms/s is GPU-bound, one with a large outside share is the title's own
# wait (or memory pressure stalling its thread).
import re
import statistics
import sys

name = sys.argv[1]
win = float(sys.argv[2]) if len(sys.argv) > 2 else 20.0
pat_t = re.compile(r"^frame profile: t ([0-9.]+) s, ([0-9.]+) ms since the last flip; game thread inside the host ([0-9.]+) ms")
pat_out = re.compile(r"outside ([0-9.]+)")
pat_gpu = re.compile(r"GPU busy ([0-9.]+) ms")
rows = []
for line in sys.stdin:
    m = pat_t.match(line)
    if not m:
        continue
    o = pat_out.search(line)
    g = pat_gpu.search(line)
    rows.append((float(m.group(1)), float(m.group(2)), float(m.group(3)), float(o.group(1)) if o else 0.0, float(g.group(1)) if g else 0.0))
if not rows:
    print(name, "no frame profile lines")
    sys.exit(0)
t0, t1 = rows[0][0], rows[-1][0]
gaps = [r[1] for r in rows]
gpu = sorted(r[4] for r in rows)
outs = [r[3] for r in rows]
nwin = int((t1 - t0) // win) + 1
wf = [0] * nwin
wg = [0.0] * nwin
wo = [0.0] * nwin
wi = [0.0] * nwin
for t, gap, ins, out, g in rows:
    k = int((t - t0) // win)
    wf[k] += 1
    wg[k] += g
    wo[k] += out
    wi[k] += ins
full = [f / win for f in wf[:-1]] or [wf[0] / max(win, 1e-9)]
print("%s: %d flips over %.0f s (t %.0f-%.0f), %.1f flips/s mean; per %.0f s: min %.1f median %.1f max %.1f" % (
    name, len(rows), t1 - t0, t0, t1, len(rows) / max(t1 - t0, 1e-9), win, min(full), statistics.median(full), max(full)))
print("  flip gaps: >0.1 s %d, >0.4 s %d, >2 s %d, longest %.0f ms" % (
    sum(g > 100 for g in gaps), sum(g > 400 for g in gaps), sum(g > 2000 for g in gaps), max(gaps)))
print("  GPU busy per frame: median %.1f ms, p90 %.1f, max %.1f; outside-host per frame: >0.1 s %d, >1 s %d, max %.0f ms" % (
    statistics.median(gpu), gpu[int(0.9 * (len(gpu) - 1))], gpu[-1], sum(o > 100 for o in outs), sum(o > 1000 for o in outs), max(outs)))
print("  timeline (window start t: flips/s | GPU busy ms/s | outside ms/s | inside ms/s):")
line = []
for k in range(nwin):
    span = win if k < nwin - 1 else max(t1 - (t0 + k * win), 1e-9)
    line.append("%4.0f: %4.1f|%4.0f|%4.0f|%3.0f" % (t0 + k * win, wf[k] / span, wg[k] / span, wo[k] / span, wi[k] / span))
for i in range(0, len(line), 4):
    print("   " + "   ".join(line[i:i + 4]))
