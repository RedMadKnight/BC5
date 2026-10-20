#!/usr/bin/env python3
# BC5 (experiment 0186): what the title read about flips and vblanks, in 10-s windows, next to its
# clock voice's speed. From the "fs"/"vs" lines of KYTY_BC5_FLIP_STATUS_TRACE and the AJM index.
# Per window: flip-status reads, displayed flips (count delta), how far the latest flipArg runs ahead
# of the displayed count, mean pending and gc-queue counts, vblank steps between the title's reads
# (distribution), and the clock voice speed over the window.
# usage: fs_analyze.py <log> <ajm-index.txt> <from s>
import sys, collections
log, idx, t0 = sys.argv[1], sys.argv[2], float(sys.argv[3])
W = 10.0
win = collections.defaultdict(lambda: {"fs": 0, "pend": 0, "gq": 0, "c0": None, "c1": None, "arg_minus_c": [], "vb": collections.Counter(), "ptd": []})
last_vb = None; last_c = None; last_pt = None
for line in open(log, errors="replace"):
    if line.startswith("fs "):
        p = line.split(); t = float(p[1])
        if t < t0: continue
        w = win[int(t // W)]
        c, pt, arg, gq, pend = int(p[3]), int(p[5]), int(p[7]), int(p[9]), int(p[11])
        w["fs"] += 1; w["pend"] += pend; w["gq"] += gq
        if w["c0"] is None: w["c0"] = c
        w["c1"] = c
        w["arg_minus_c"].append(arg - c)
        if last_c is not None and c != last_c and last_pt is not None:
            w["ptd"].append((pt - last_pt) / 1000.0)
        last_c, last_pt = c, pt
    elif line.startswith("vs "):
        p = line.split(); t = float(p[1])
        if t < t0: continue
        c = int(p[3])
        if last_vb is not None:
            win[int(t // W)]["vb"][c - last_vb] += 1
        last_vb = c
# the clock voice: complete passes of 479352 samples
speed = {}
prev = {}; s0 = {}; seg0 = {}
for l in open(idx):
    q = l.split()
    if len(q) < 5: continue
    t = float(q[0]); i = q[1]; s = int(q[4])
    if i in prev and s < prev[i]:
        if prev[i] - s0[i] == 479352:
            sp = 479352 / 48000 / (t - seg0[i])
            for k in range(int(seg0[i] // W), int(t // W) + 1):
                speed[k] = sp
        seg0[i] = t; s0[i] = s
    if i not in prev:
        seg0[i] = t; s0[i] = s
    prev[i] = s
for k in sorted(win):
    w = win[k]
    if not w["fs"]: continue
    am = w["arg_minus_c"]; amc = collections.Counter(am)
    ptd = w["ptd"]
    print("%4d s: clock %.2fx | %3d reads, %3d shown, arg-count %s, pend %.2f, gq %.2f | vblank steps %s | shown-to-shown ms mean %.1f max %.0f" % (
        k * W, speed.get(k, float("nan")), w["fs"], (w["c1"] - w["c0"]), dict(amc.most_common(3)), w["pend"] / w["fs"], w["gq"] / w["fs"],
        dict(sorted(w["vb"].items())), sum(ptd) / len(ptd) if ptd else 0, max(ptd) if ptd else 0))
