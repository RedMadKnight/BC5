#!/usr/bin/env python3
# BC5 experiment 0051: when a run reaches its steady 3D scene: the start of the first 5 s window
# after 45 s (the end of the intro) with at least 80 frames, and the longest stretch without a frame
# before it. Usage: to3d.py direct.log...
import collections
import sys

for path in sys.argv[1:]:
    frames = []
    for l in open(path, errors="replace"):
        if l.startswith("frame profile: t "):
            frames.append(float(l.split()[3]))
    buckets = collections.Counter(int(t // 5) * 5 for t in frames)
    start = next((b for b in sorted(buckets) if b >= 45 and buckets[b] >= 80), None)
    gap = 0.0
    for a, b in zip(frames, frames[1:]):
        if start is not None and a < start:
            gap = max(gap, b - a)
    print(f"{path.split('/')[-3]}: steady 3D from {start} s, longest gap before it {gap:.1f} s")
