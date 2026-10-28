#!/usr/bin/env python3
# BC5 experiment 0362: the passes that bind the night lake's depth image as a texture, from the shared build's draw
# journal with BC5_DIRECT_DRAW_JOURNAL_FIND=1129ec00 (the depth image's T# base dword, 0x1129ec0000 >> 8), _ACB=1 and
# _PS=11d01d7100 (patch 0001, experiments 0092/0156/0157):
#   "draw journal find: <draw|dispatch> <ps|cs> ud<k> (<value>) <direct|table> <addr> | rt0 <rt> | ps <ps> cs <cs> | pkt.."
#   "find ud cs <cs> t <journal s>: <user data>"   (after a dispatch's hit)
#   "draw journal buf N (..) at P: .. | rt0 .. | .. | ps 11d01d7100.." and "bake draw buf N at P: t T wall S.MS" (the
#   full-screen water draw, one per frame, fr0354.py's frames)
# The journal's lines come in submission order. A segment is the lines between two consecutive full-screen water draws.
# Per program (draw: PS and colour target 0; dispatch: CS), with the user-data slot and where the value sat: the
# segments it appears in, its hits per segment (median), its position in the segment (the median share of the
# segment's hits before it), and for dispatches the median journal time after the segment's full-screen draw.
# Prints the table; writes <out json>. Summaries only.
# usage: python3 -I fi0362.py <direct.log> <out json>
import json, re, statistics, sys

FIND = re.compile(r"draw journal find: (draw|dispatch) (ps|cs) ud(\d+) \(([0-9a-f]+)\) (direct|table) ([0-9a-f]+) \| rt0 ([0-9a-f]+) \| ps ([0-9a-f]+) cs ([0-9a-f]+)")
UDCS = re.compile(r"find ud cs ([0-9a-f]+) t ([\d.]+):")
DRAW = re.compile(r"draw journal buf (\d+) \(\d+ dwords\) at (\d+):.*?\| ps ([0-9a-f]+)")
BAKE = re.compile(r"bake draw buf (\d+) at (\d+): t ([\d.]+) wall (\d+)\.(\d+)")

log, out = sys.argv[1:3]
segs = []  # each: {"t": fs draw time, "hits": [...]}
pend = {}
cur = None
last_dispatch = None
nfind = 0
for l in open(log, errors="replace"):
    m = FIND.search(l)
    if m:
        nfind += 1
        h = {"kind": m[1], "ud": int(m[3]), "where": m[5], "rt0": m[7], "ps": m[8], "cs": m[9]}
        h["prog"] = ("cs " + m[9]) if m[1] == "dispatch" else ("ps %s rt0 %s" % (m[8], m[7]))
        if cur is not None:
            cur["hits"].append(h)
        last_dispatch = h if m[1] == "dispatch" else None
        continue
    m = UDCS.search(l)
    if m:
        if last_dispatch is not None and last_dispatch["cs"] == m[1]:
            last_dispatch["t"] = float(m[2])
        last_dispatch = None
        continue
    m = DRAW.search(l)
    if m:
        if m[3].startswith("11d01d7100"):
            pend[(m[1], m[2])] = True
        continue
    m = BAKE.search(l)
    if m and pend.pop((m[1], m[2]), None):
        cur = {"t": float(m[3]), "hits": []}
        segs.append(cur)
print("# %d find lines, %d full-screen water draws (segments)" % (nfind, len(segs)))
if len(segs) > 2:
    segs = segs[:-1]  # the last segment is cut by the journal's end
    gaps = sorted(b["t"] - a["t"] for a, b in zip(segs, segs[1:]))
    print("  segment length: median %.1f ms; hits per segment: median %d, max %d" % (
        1000 * gaps[len(gaps) // 2], statistics.median(len(s["hits"]) for s in segs), max(len(s["hits"]) for s in segs)))
progs = {}
for s in segs:
    n = len(s["hits"])
    seen = {}
    for i, h in enumerate(s["hits"]):
        key = "%s ud%d %s" % (h["prog"], h["ud"], h["where"])
        p = progs.setdefault(key, {"kind": h["kind"], "segs": 0, "per": [], "pos": [], "dt": []})
        seen[key] = seen.get(key, 0) + 1
        p["pos"].append(i / max(n, 1))
        if "t" in h:
            p["dt"].append(1000 * (h["t"] - s["t"]))
    for key, k in seen.items():
        progs[key]["segs"] += 1
        progs[key]["per"].append(k)
rows = []
for key, p in sorted(progs.items(), key=lambda kv: statistics.median(kv[1]["pos"])):
    r = {"prog": key, "kind": p["kind"], "segments": p["segs"], "per_segment": statistics.median(p["per"]),
         "position": round(statistics.median(p["pos"]), 3), "dt_ms": round(statistics.median(p["dt"]), 1) if p["dt"] else None}
    rows.append(r)
    print("  %-62s in %4d of %d segments, x%-4g at %.2f%s" % (key, r["segments"], len(segs), r["per_segment"], r["position"],
          "" if r["dt_ms"] is None else ", %+.1f ms after the full-screen draw" % r["dt_ms"]))
json.dump({"segments": len(segs), "finds": nfind, "programs": rows}, open(out, "w"), indent=0)
