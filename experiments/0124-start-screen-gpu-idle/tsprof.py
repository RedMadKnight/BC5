#!/usr/bin/env python3
"""GPU time per buffer from the title's own timestamps (BC5_DIRECT_TS_LOG journal lines
"ts: #n kind dwords done t: addr=value ..."). All timestamp values (100 MHz GPU realtime) are put on
one time line; the gap before each value is charged to the buffer (kind + size) that wrote it.
Gaps over 50 ms are idle and dropped. Prints the buffers by total GPU time per frame.
Usage: tsprof.py direct.log frames_in_window"""
import collections
import re
import sys

path, frames = sys.argv[1], float(sys.argv[2])
events = []  # (value, key)
pat = re.compile(r"^ts: #(\d+) (\w+) (\d+) dwords done ([0-9.]+):(.*)$")
for line in open(path, errors="replace"):
    m = pat.match(line)
    if not m:
        continue
    key = f"{m.group(2)} {m.group(3)}"
    for kv in m.group(5).split():
        a, _, v = kv.partition("=")
        try:
            v = int(v)
        except ValueError:
            continue
        if v == 0 or v > 1 << 50:
            continue
        events.append((v, key))
events.sort()
tot = collections.Counter()
cnt = collections.Counter()
span = 0
for (v0, _), (v1, k1) in zip(events, events[1:]):
    d = v1 - v0
    if d <= 0 or d > 5_000_000:  # > 50 ms: idle
        continue
    tot[k1] += d
    span += d
    cnt[k1] += 1
print(f"{len(events)} timestamps, {span / 1e5:.1f} ms of GPU time charged, {frames:.0f} frames")
print(f"per frame: {span / 1e5 / frames:.2f} ms")
for k, d in tot.most_common(20):
    print(f"  {k:>14}: {d / 1e5 / frames:6.2f} ms/frame  ({cnt[k] / frames:5.1f} gaps/frame)")
