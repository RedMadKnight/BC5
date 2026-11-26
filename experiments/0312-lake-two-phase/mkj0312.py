#!/usr/bin/env python3
# BC5 experiment 0312, run J1: a synthetic capture for the J1 analysis path (rdj0312.py, then pqj0312.py), to be run on
# the box in the ubuntu distrobox before the run, as exp 0295's mk0295.py. Two bursts of 8 x (culling read "cK", depth
# read "zK") and a G-buffer read, in buf0312.py's file layout, and a frames JSON in fr0312.py's form: reads paired into
# frames (z0-z1, z2-z3, ...), every frame at 3072 wide, the state alternating X, Y per frame. A depth read of an X frame
# has 0 at a fixed 20 % of its elements (set A), of a Y frame at another (set B), elsewhere values in 0.1..1; page 1767
# of the culling read holds content A or B by the frame's state, page 1776 a random one of three, the rest fixed.
# Expect from rdj0312.py: two families, every depth read X or Y by its frame; from pqj0312.py: page 1767 p ~0.03 at
# 8 frames (the smallest p a 4/4 split allows is 2/70 = 1/35: the table is symmetric in X and Y), 1776 not.
# usage: python3 -I mkj0312.py <out dir>   (writes <out dir>/cap and <out dir>/frames.json; ~0.4 GB)
import json, os, sys
import numpy as np

out = sys.argv[1]
cap = os.path.join(out, "cap")
os.makedirs(cap, mode=0o700, exist_ok=True)
rng = np.random.default_rng(312)
NZ, NC = 0x1860000 // 4, (8 << 20) // 4
setA, setB = rng.random(NZ) < 0.2, rng.random(NZ) < 0.2
base = rng.integers(0, 1 << 32, NC, dtype=np.uint32)
pA, pB = rng.integers(0, 1 << 32, 1024, dtype=np.uint32), rng.integers(0, 1 << 32, 1024, dtype=np.uint32)
p1776 = [rng.integers(0, 1 << 32, 1024, dtype=np.uint32) for _ in range(3)]
sizes, frame_of = {}, {}
wall = 1792960000.0
for b in (1, 2):
    rows = []
    for k in range(8):
        j = (b - 1) * 4 + k // 2
        st = "XY"[j % 2]
        z = rng.uniform(0.1, 1.0, NZ).astype(np.float32)
        z[setA if st == "X" else setB] = 0
        c = base.copy()
        c[1767 * 1024:1768 * 1024] = rng.permutation(pA if st == "X" else pB)
        c[1776 * 1024:1777 * 1024] = p1776[int(rng.integers(3))]
        for nm, d in (("c%d" % k, c), ("z%d" % k, z)):
            open(os.path.join(cap, "b%02d.%s.bin" % (b, nm)), "wb").write(d.tobytes())
            rows.append("%s wall %.4f mono %.4f start %.1f read 10.0 write 0.0 bytes %d" % (nm, wall, wall - 1792950000, 30.0 * k, d.nbytes))
            wall += 0.015
        sizes["b%02d.z%d" % (b, k)], frame_of["b%02d.z%d" % (b, k)] = 3072, j
    g = rng.uniform(0, 1, NZ).astype(np.float32)
    open(os.path.join(cap, "b%02d.g.bin" % b), "wb").write(g.tobytes())
    rows.append("g wall %.4f mono %.4f start 250.0 read 10.0 write 0.0 bytes %d" % (wall, wall - 1792950000, g.nbytes))
    open(os.path.join(cap, "b%02d.times.txt" % b), "w").write("\n".join(rows) + "\n")
    wall += 4
json.dump({"field": "vp", "lag_ms": 0, "agree": 1.0, "clear_matched": 0, "frames": 8, "sizes": sizes, "frame_of": frame_of},
          open(os.path.join(out, "frames.json"), "w"))
print("# synthetic capture: 2 bursts, 16 depth reads in 8 frames, in %s" % cap)
