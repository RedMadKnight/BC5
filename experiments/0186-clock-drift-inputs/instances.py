#!/usr/bin/env python3
# BC5 (experiment 0186): decoder instances that start or end in a time window, from the AJM index
# (time, instance, written bytes, frames, total decoded samples): first and last job, jobs, bytes,
# mono 16-bit seconds decoded per second of its life, and how often its sample counter wrapped.
# usage: instances.py <ajm-index.txt> <from s> <to s>
import sys
idx, a, b = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
inst = {}
for l in open(idx):
    q = l.split()
    if len(q) < 5: continue
    t = float(q[0]); i = q[1]; w = int(q[2]); s = int(q[4])
    v = inst.setdefault(i, {"t0": t, "t1": t, "jobs": 0, "bytes": 0, "wraps": 0, "last": s})
    v["t1"] = t; v["jobs"] += 1; v["bytes"] += w
    if s < v["last"]: v["wraps"] += 1
    v["last"] = s
for i, v in sorted(inst.items(), key=lambda kv: kv[1]["t0"]):
    if v["t0"] > b or v["t1"] < a: continue
    if not (a <= v["t0"] <= b or a <= v["t1"] <= b): continue
    life = max(v["t1"] - v["t0"], 1e-3)
    print("%s: %8.2f-%8.2f s (%6.1f s), %6d jobs, %9d bytes, %.2f mono s/s, %d wraps" % (
        i, v["t0"], v["t1"], life, v["jobs"], v["bytes"], v["bytes"] / 2 / 48000 / life, v["wraps"]))
