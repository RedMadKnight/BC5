#!/usr/bin/env python3
# BC5 experiment 0369: does the night lake's hole state follow the frame's flip parity? Exp 0354's run J1: F436's
# time-ordered A/B split (raw/J1.ph.txt) over the frames whose first depth read was sized (ra0365.py's selection from
# raw/J1.rdj2.json: kind z, a journal frame, shear at that frame's width <= 3, the earliest read per frame_j). Each
# frame_j is the j-th full-screen water draw of the draw journal ("bake draw buf N at 222: t T", the N-th line). From
# the journal's "timing: t T s flip F/B" lines: the flips before that water draw, the display buffer index B of the
# latest one, and the time since it. Cross-tables of the A/B side against B, against the parity of the flip count and of
# the water-draw count, and, for consecutive journal frames, whether a side change goes with a flip-gap change.
# usage: python3 -I fl0369.py <exp 0354 raw dir> <direct.log of J1>   (prints a summary only)
import bisect, collections, json, os, re, sys

raw, log = sys.argv[1], sys.argv[2]
d = json.load(open(os.path.join(raw, "J1.rdj2.json")))
frames = {}
for r in d["reads"]:
    if r["kind"] != "z" or not r.get("frame") or r.get("frame_j") is None or r["sizes"][str(r["frame"])]["shear"] > 3:
        continue
    frames.setdefault(r["frame_j"], []).append(r)
fj = sorted(frames)
split = re.search(r"split by time \(frames in order, A/B\): ([AB]+)", open(os.path.join(raw, "J1.ph.txt")).read())[1]
assert len(split) == len(fj)
water, flips = [], []
for l in open(log, errors="replace"):
    m = re.match(r"^bake draw buf (\d+) at 222: t ([0-9.]+)", l)
    if m:
        water.append(float(m[2]))
        continue
    m = re.match(r"^timing: t ([0-9.]+) s flip (\d+)/(\d+)", l)
    if m:
        flips.append((float(m[1]), int(m[2]), int(m[3])))
ft = [f[0] for f in flips]
print("# %d sized frames; %d water draws in the journal; %d flip lines" % (len(fj), len(water), len(flips)))
tab = collections.Counter()
rows = []
for j, s in zip(fj, split):
    if j >= len(water):
        continue
    t = water[j]
    i = bisect.bisect_right(ft, t) - 1
    if i < 0:
        continue
    rows.append((j, s, flips[i][2], i, j, (t - ft[i]) * 1000, (ft[i] - ft[i - 1]) * 1000 if i > 0 else None))
for name, k in (("display buffer index of the latest flip", 2), ("flip count parity", 3), ("water-draw count parity", 4)):
    c = collections.Counter((s, v % 2 if k != 2 else v) for _, s, *rest in rows for v in [rest[k - 2]])
    print("# side by %s: %s" % (name, dict(sorted(c.items()))))
same = collections.Counter()
for a, b in zip(rows, rows[1:]):
    if b[0] == a[0] + 1:
        same[("side kept" if a[1] == b[1] else "side changed", "buffer kept" if a[2] == b[2] else "buffer changed", "flips between %d" % (b[3] - a[3]))] += 1
print("# consecutive journal frames:")
for k, v in sorted(same.items()):
    print("   %s: %d" % (", ".join(k), v))
