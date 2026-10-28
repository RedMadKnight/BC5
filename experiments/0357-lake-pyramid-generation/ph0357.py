#!/usr/bin/env python3
# BC5 experiment 0357: a hole state for each full depth read of pl0357.py, as exp 0354's ph0354.py split frames. Per depth
# read with a frame size (fr0354.py via rdj0354.py's JSON) whose shear there is at most 3: its depth-0 mask in the lake
# window at that size (rd0312.py's de-swizzle, ADDR_SW_64KB_Z_X at 16 pipes, swz0248-z4.json), over the pixels valid in
# every such read; phi between every two reads; the leading eigenvector of the centred phi matrix splits the reads into
# two states, A and B (in J1: phi +0.55 within, -0.24 between, F436). Writes <out json> {"labels": {read: "A"|"B"},
# "within": [..], "between": ..} and prints the split. Summaries only.
# With FLOOR (added after run P1, most of whose reads had few or no holes, so the split separated holes from none): reads
# whose depth-0 share over the common pixels is below FLOOR get "0", and only the rest are split into A and B.
# usage: python3 -I ph0357.py <capture dir> <rdj json> <swz0248-z4.json> <out json> [FLOOR]   (on the box, in the distrobox)
import json, os, sys
import numpy as np

cdir, rjson, zsw, out = sys.argv[1:5]
floor = float(sys.argv[5]) if len(sys.argv) > 5 else None
X0, X1, Y0, Y1 = 300, 1900, 400, 680
pz = json.load(open(zsw))["patterns"]["4"]


def coord_offset(p, key, n):  # rd0312.py's
    v = np.arange(n, dtype=np.int64)
    off = np.zeros(n, dtype=np.int64)
    for i, b in enumerate(p):
        m = b[key]
        if m:
            par = np.zeros(n, dtype=np.int64)
            for k in range(16):
                if m >> k & 1:
                    par ^= (v >> k) & 1
            off |= par << i
    return off


IDX = {}


def window_of(raw, w):  # rd0312.py's image() and window(), the lake window only
    h = w * 9 // 16
    if w not in IDX:
        fx, fy = coord_offset(pz, "x", w), coord_offset(pz, "y", h)
        pitch = -(-w // 128)
        ys, xs = np.arange(Y0, Y1) * h // 1080, np.arange(X0, X1) * w // 1920
        blk = (ys // 128)[:, None] * pitch + (xs // 128)[None, :]
        IDX[w] = (blk * 65536 + (fx[xs][None, :] ^ fy[ys][:, None])) >> 2
    return raw[np.minimum(IDX[w], raw.size - 1)]


rj = json.load(open(rjson))
reads = [r for r in rj["reads"] if r["kind"] == "z" and r.get("frame") and r["sizes"][str(r["frame"])]["shear"] <= 3]
masks, oks, names = [], [], []
for r in reads:
    b, k = r["name"].split(".z")
    raw = np.frombuffer(open(os.path.join(cdir, "%s.z%s.bin" % (b, k)), "rb").read(), dtype="<f4").astype(np.float64)
    with np.errstate(invalid="ignore"):
        z = window_of(raw, r["frame"])
        ok = np.isfinite(z) & (z >= 0) & (z <= 1)
    masks.append((z == 0) & ok)
    oks.append(ok)
    names.append(r["name"])
n = len(names)
if n < 4:
    print("# %d sized depth reads: too few" % n)
    json.dump({"labels": {}}, open(out, "w"))
    sys.exit(0)
common = np.logical_and.reduce(oks)
M = np.array([m[common] for m in masks], dtype=np.float64)
share = M.mean(axis=1)
none = [nm for nm, sh in zip(names, share) if floor is not None and sh < floor]
keep = np.array([floor is None or sh >= floor for sh in share])
print("# floor %s: %d reads below it (no holes), %d split" % (floor, len(none), int(keep.sum())))
M, names, share = M[keep], [nm for nm, k in zip(names, keep) if k], share[keep]
n = len(names)
Z = (M - M.mean(axis=1, keepdims=True)) / np.maximum(M.std(axis=1, keepdims=True), 1e-9)
PHI = Z @ Z.T / M.shape[1]
C = PHI - PHI.mean(axis=0, keepdims=True) - PHI.mean(axis=1, keepdims=True) + PHI.mean()
w, v = np.linalg.eigh(C)
side = v[:, -1] > 0
a, b2 = np.where(side)[0], np.where(~side)[0]


def mean_in(i):
    return float(PHI[np.ix_(i, i)][np.triu_indices(len(i), 1)].mean()) if len(i) > 1 else float("nan")


within = [mean_in(a), mean_in(b2)]
between = float(PHI[np.ix_(a, b2)].mean()) if len(a) and len(b2) else float("nan")
print("# %d sized depth reads of %d; %d common valid pixels; hole share min %.3f, median %.3f, max %.3f" % (
    n, sum(1 for r in rj["reads"] if r["kind"] == "z"), int(common.sum()), share.min(), float(np.median(share)), share.max()))
print("  split: A %d, B %d reads; mean phi within %.3f and %.3f, between %.3f (eigenvalue share %.2f)" % (
    len(a), len(b2), within[0], within[1], between, w[-1] / max(w[w > 0].sum(), 1e-9)))
print("  states in read order: %s" % "".join("A" if s else "B" for s in side))
lab = {nm: ("A" if s else "B") for nm, s in zip(names, side)}
lab.update({nm: "0" for nm in none})
json.dump({"labels": lab, "within": within, "between": between, "floor": floor},
          open(out, "w"), indent=0)
