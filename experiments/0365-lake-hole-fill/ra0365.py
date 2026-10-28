#!/usr/bin/env python3
# BC5 experiment 0365, step 2: F436's two-state split (exp 0354, run J1) against the depth reads' clarity, from exp
# 0354's committed raw files only (the reads themselves were deleted, so the split's phi cannot be recomputed on clear
# reads). ph0354.py took, per frame, the first depth read whose block-row shear at the frame's journal width was at most
# 3; its time-ordered A/B split is printed in raw/J1.ph.txt. Each read's per-width summaries are in raw/J1.rdj2.json
# (rd0312.py/rdj0354.py: "clear" = next-best shear >= 3 x the best; at each width the depth-0 share in the lake window,
# and phi with rdj0354.py's X and Y families). Here, per side of the split, the frames whose read was clear and those
# whose read was not: counts, median hole share, median phi with X and Y, the shear at the frame's width and the best
# shear at any other width. If the split followed clarity, the two sides would differ in it; if the unclear reads held
# no hole information, their phi with X and Y would be near 0 on both sides.
# usage: python3 -I ra0365.py <exp 0354 raw dir>
import collections, json, os, re, statistics, sys

raw = sys.argv[1]
d = json.load(open(os.path.join(raw, "J1.rdj2.json")))
frames = {}
for r in d["reads"]:
    if r["kind"] != "z" or not r.get("frame") or r.get("frame_j") is None or r["sizes"][str(r["frame"])]["shear"] > 3:
        continue
    frames.setdefault(r["frame_j"], []).append(r)
first = [sorted(frames[j], key=lambda r: r["wall"])[0] for j in sorted(frames)]
split = re.search(r"split by time \(frames in order, A/B\): ([AB]+)", open(os.path.join(raw, "J1.ph.txt")).read())[1]
assert len(split) == len(first), (len(split), len(first))
g = collections.defaultdict(list)
for r, s in zip(first, split):
    z = r["sizes"][str(r["frame"])]
    other = min(v["shear"] for w, v in r["sizes"].items() if w != str(r["frame"]))
    g[(s, "clear" if r["clear"] else "unclear")].append((z["share"], z["phiX"], z["phiY"], z["shear"], other))
print("# exp 0354 J1: %d frames in ph0354.py's split; %d of %d depth reads clear" % (
    len(first), sum(1 for r in d["reads"] if r["kind"] == "z" and r["clear"]), sum(1 for r in d["reads"] if r["kind"] == "z")))
for k in sorted(g):
    v = g[k]
    m = [statistics.median(x[i] for x in v) for i in range(5)]
    print("  side %s, %-7s reads: %2d frames; hole share %.3f; phi with X %+.2f, with Y %+.2f; shear at the frame's width %.2f, best elsewhere %.2f" % (
        k[0], k[1], len(v), *m))
