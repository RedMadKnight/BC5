#!/usr/bin/env python3
# BC5 experiment 0043: the GPU's busy and idle time per frame from a direct-path journal
# (BC5_DIRECT_TIMING=1, BC5_DIRECT_FRAME_PROFILE=1). Jobs run in order on the one GFX ring, so a
# job starts when it was queued to the kernel or when the previous one finished, whichever is
# later, and ends when its fence was seen ("timing: #N done at t D s, ... fence F ms": queued at
# D - F). Usage: gpu-timeline.py direct.log T0 T1  -> per-frame lines and a summary.
import re
import statistics
import sys

path, t0, t1 = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
done_re = re.compile(r"^timing: #(\d+) done at t ([0-9.]+) s, ([0-9.]+) ms after the sync and hints; device: prepare ([0-9.]+) list ([0-9.]+) cs ([0-9.]+) fence ([0-9.]+) ms")
kind_re = re.compile(r"^submit #(\d+) (\S+) (\d+) dwords")
flip_re = re.compile(r"^frame profile: t ([0-9.]+) s")

kinds = {}
jobs = []   # (queued, done, n)
flips = []
with open(path, errors="replace") as f:
    for line in f:
        m = kind_re.match(line)
        if m:
            kinds[int(m.group(1))] = (m.group(2), int(m.group(3)))
            continue
        m = done_re.match(line)
        if m:
            d = float(m.group(2))
            if t0 - 1 <= d <= t1 + 1:
                fence = float(m.group(7)) / 1e3
                jobs.append((d - fence, d, int(m.group(1))))
            continue
        m = flip_re.match(line)
        if m:
            t = float(m.group(1))
            if t0 <= t <= t1:
                flips.append(t)

jobs.sort(key=lambda j: j[1])
# GPU intervals: start = max(queued, previous end)
iv = []
prev_end = 0.0
for q, d, n in jobs:
    s = max(q, prev_end)
    if d > s:
        iv.append((s, d, n))
    prev_end = max(prev_end, d)

by_kind = {}


def per_frame(a, b):
    busy = 0.0
    gaps = []
    last = a
    first_kind_after_gap = []
    for s, e, n in iv:
        if e <= a or s >= b:
            continue
        s2, e2 = max(s, a), min(e, b)
        if s2 > last:
            gaps.append((s2 - last, n))
        busy += e2 - s2
        k = kinds.get(n, ("?", 0))[0]
        by_kind[k] = by_kind.get(k, 0.0) + (e2 - s2)
        last = max(last, e2)
    if b > last:
        gaps.append((b - last, None))
    return busy, gaps

rows = []
for a, b in zip(flips, flips[1:]):
    busy, gaps = per_frame(a, b)
    rows.append((b - a, busy, sum(g for g, _ in gaps), max((g for g, _ in gaps), default=0.0), gaps))

if not rows:
    print("no frames in the window")
    sys.exit(0)
fr = [r[0] * 1e3 for r in rows]
bu = [r[1] * 1e3 for r in rows]
idl = [r[2] * 1e3 for r in rows]
mx = [r[3] * 1e3 for r in rows]
print(f"{len(rows)} frames in {t0}-{t1} s, {len(jobs)} jobs")
for name, v in (("frame", fr), ("gpu busy", bu), ("gpu idle", idl), ("longest idle gap", mx)):
    q = statistics.quantiles(v, n=10)
    print(f"  {name:17s} median {statistics.median(v):6.2f} ms   p10 {q[0]:6.2f}   p90 {q[-1]:6.2f}")
# What the long gaps wait for: the kind of the job that starts after each gap of 1 ms or more.
after = {}
for _, _, _, _, gaps in rows:
    for g, n in gaps:
        if g >= 1e-3:
            k = kinds.get(n, ("(frame end)", 0))[0] if n is not None else "(frame end)"
            after.setdefault(k, []).append(g * 1e3)
print("  GPU busy per frame by job kind:")
for k, v in sorted(by_kind.items(), key=lambda kv: -kv[1]):
    print(f"    {k:12s} {v * 1e3 / len(rows):6.2f} ms")
print("  idle gaps of 1 ms or more, by the job that ends them:")
for k, v in sorted(after.items(), key=lambda kv: -sum(kv[1])):
    print(f"    {k:12s} {len(v):6d} gaps, {sum(v) / len(rows):5.2f} ms per frame, median {statistics.median(v):5.2f} ms")
