#!/usr/bin/env python3
# BC5 experiment 0289 (exp 0287's rd0287.py, unchanged; exp 0283's rd0283.py skipping the argument and pyramid reads): the depth read bursts of capa0287.py, read by read and size by size, against the two hole sets of
# exp 0282 (F342). Per read (bNN.zK depth reads, bNN.g G-buffer read), in the lake window (x 300..1900, y 400..680 of the
# 1920x1080 shot, nearest-pixel resampling; depth words outside 0..1, other sizes' stencil bytes (F310), left out):
#  - at each 16:9 render size (2048..3328, F309/F310): the block-row shear (as exps 0271/0274/0282), the share of depth-0
#    pixels (G-buffer: cleared, >= 9000), the share of them in the shots' cell mask, and how they lie in the two
#    families below ("inX": the share of the read's depth-0 pixels in family X's set; "inY" likewise; phi with each);
#  - the read's best size (least shear) and how clearly (next-best shear over best).
# The families are built from the clear reads (next-best >= 3 x best) at their best size, as exp 0282's cross0282.py:
# each read joins the first group whose first read it matches with phi >= 0.6; groups whose first reads lie one inside
# the other (>= 90 % of the smaller set's pixels in the larger) form one family; a family's set is the union of its
# clear reads' depth-0 pixels. X is the family with the larger share of the shots' cell mask, Y the next.
# Then xy0283.py matches the reads to the journal's frames and takes each read at its frame's size.
# Writes <out json> (summaries only: shares, shears, phi; no image) and prints a summary. Runs on the box in the ubuntu
# distrobox (numpy, PIL), on the title's data. De-swizzle as exps 0271/0274/0282: Mesa addrlib patterns at 16 pipes,
# ADDR_SW_64KB_Z_X for the depth (swz0248-z4.json), ADDR_SW_64KB_R_X for the G-buffer (swz0244-4.json).
# usage: python3 -I rd0283.py <capture dir> <run dir> <bench.txt> <swz0248-z4.json> <swz0244-4.json> <out json>
import glob, json, os, re, sys
import numpy as np
from PIL import Image

cdir, rdir, bench, zsw, rsw, out = sys.argv[1:7]
pz, pr = json.load(open(zsw))["patterns"]["4"], json.load(open(rsw))["patterns"]["4"]
WIDTHS = (2048, 2304, 2560, 2816, 3072, 3328)
X0, X1, Y0, Y1 = 300, 1900, 400, 680
win = np.zeros((1080, 1920), bool)
win[Y0:Y1, X0:X1] = True
shots = []
if os.path.exists(bench):
    for l in open(bench):
        m = re.match(r"\s*(\d{6})-(ts\d\d)\.png: patch\s+([\d.]+) %", l)
        if m:
            shots.append((m[1], m[2], float(m[3])))


def patch_mask(path):
    a = np.asarray(Image.open(path).convert("RGB")).astype(np.float64)
    return (a.mean(axis=2) > 47) & (a[:, :, 2] - a[:, :, 0] > 38) & win


pat = [s for s in shots if s[2] >= 8]
masks = [patch_mask(os.path.join(rdir, "shots", "%s-%s.png" % (s[0], s[1]))) for s in pat
         if os.path.exists(os.path.join(rdir, "shots", "%s-%s.png" % (s[0], s[1])))]
cells = ((np.mean(masks, axis=0) >= 0.5) & win if masks else np.zeros_like(win))[Y0:Y1, X0:X1]


def coord_offset(p, key, n):
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


def image(raw, p, w, h):
    if (id(p), w, h) not in IDX:  # word index of each element, per pattern and size
        fx, fy = coord_offset(p, "x", w), coord_offset(p, "y", h)
        pitch = -(-w // 128)
        blk = (np.arange(h) // 128)[:, None] * pitch + (np.arange(w) // 128)[None, :]
        IDX[(id(p), w, h)] = (blk * 65536 + (fx[None, :] ^ fy[:, None])) >> 2
    return raw[np.minimum(IDX[(id(p), w, h)], raw.size - 1)]


def shear(img):
    good = np.isfinite(img) & (np.abs(img) < 1e30)
    l = np.log1p(np.abs(np.where(good, img, 0.0)))
    d = np.abs(np.diff(l, axis=0))
    at = np.arange(d.shape[0]) % 128 == 127
    return float(d[at].mean() / max(d[~at].mean(), 1e-12))


def window(img, w, h):  # the lake window of the 1920x1080 shot, nearest pixel
    ys, xs = np.arange(Y0, Y1) * h // 1080, np.arange(X0, X1) * w // 1920
    return img[ys][:, xs]


def phi(a, b, m):
    x, y = a[m].astype(float), b[m].astype(float)
    return float(np.corrcoef(x, y)[0, 1]) if x.size > 1 and x.std() > 0 and y.std() > 0 else float("nan")


reads = []
for tf in sorted(glob.glob(os.path.join(cdir, "b*.times.txt"))):
    b = os.path.basename(tf).split(".")[0]
    for l in open(tf):
        m = re.match(r"(\S+) wall ([\d.]+) mono ([\d.]+) start ([\d.]+) read ([\d.]+)", l)
        if not m or m[1][0] not in "zg" or not os.path.exists(os.path.join(cdir, "%s.%s.bin" % (b, m[1]))):
            continue  # exp 0287: the argument reads (aK) are ar0287.py's
        raw = np.frombuffer(open(os.path.join(cdir, "%s.%s.bin" % (b, m[1])), "rb").read(), dtype="<f4").astype(np.float64)
        g = m[1] == "g"
        r = {"name": "%s.%s" % (b, m[1]), "burst": b, "kind": "g" if g else "z", "wall": float(m[2]), "mono": float(m[3]),
             "start_ms": float(m[4]), "read_ms": float(m[5]), "sizes": {}}
        sets = {}
        for w in WIDTHS:
            h = w * 9 // 16
            img = image(raw, pr if g else pz, w, h)
            sh = shear(img)
            z = window(img, w, h)
            with np.errstate(invalid="ignore"):
                ok = np.isfinite(z) if g else np.isfinite(z) & (z >= 0) & (z <= 1)
            s = (np.nan_to_num(z) >= 9000) & ok if g else (z == 0) & ok
            sets[w] = (s, ok)
            r["sizes"][str(w)] = {"shear": round(sh, 3), "share": round(float(s[ok].mean()) if ok.any() else float("nan"), 4),
                                  "cells": round(float(s[ok & cells].mean()) if (ok & cells).any() else float("nan"), 4)}
        cand = sorted((r["sizes"][str(w)]["shear"], w) for w in WIDTHS)
        r["best"], r["ratio"] = cand[0][1], round(cand[1][0] / max(cand[0][0], 1e-9), 2)
        r["clear"] = r["ratio"] >= 3
        reads.append((r, sets))
# families from the clear depth reads at their best size
clear = [(r, sets[r["best"]]) for r, sets in reads if r["clear"] and r["kind"] == "z" and r["sizes"][str(r["best"])]["share"] > 0.03]
groups = []
for i, (r, (s, ok)) in enumerate(clear):
    for g in groups:
        s0, ok0 = clear[g[0]][1]
        if phi(s, s0, ok & ok0) >= 0.6:
            g.append(i)
            break
    else:
        groups.append([i])
fam = list(range(len(groups)))
for a in range(len(groups)):
    for c in range(len(groups)):
        if a == c:
            continue
        sa, oka = clear[groups[a][0]][1]
        sc, okc = clear[groups[c][0]][1]
        m = oka & okc
        both = (sa & sc & m).sum()
        if both >= 0.9 * min((sa & m).sum(), (sc & m).sum()) > 0:
            fa, fc = fam[a], fam[c]
            fam = [fa if f == fc else f for f in fam]
families = {}
for gi, g in enumerate(groups):
    families.setdefault(fam[gi], []).extend(g)
fsets = []
for f, members in families.items():
    u = np.zeros_like(cells)
    for i in members:
        u |= clear[i][1][0]
    fsets.append((float(u[cells].mean()) if cells.any() else 0.0, f, members, u))
fsets.sort(key=lambda x: -x[0])
names = ["X", "Y"] + ["F%d" % k for k in range(3, 3 + len(fsets))]  # exp 0287: W287b had more than nine families
print("# %s: %d reads (%d clear depth reads with holes); cell mask from %d patched shots, %.3f of the lake window" % (
    cdir, len(reads), len(clear), len(masks), float(cells.mean())))
for k, (cs, f, members, u) in enumerate(fsets[:9]):
    print("  family %s: %d clear reads (%s), set %.3f of the window, %.3f of the cell mask" % (
        names[k], len(members), " ".join(clear[i][0]["name"] for i in members), float(u.mean()), cs))
if len(fsets) >= 2:
    ux, uy = fsets[0][3], fsets[1][3]
    print("  X and Y: %.4f of the window in both; X has %.3f of its pixels in Y, Y %.3f in X" % (
        float((ux & uy).mean()), float((ux & uy).sum() / max(ux.sum(), 1)), float((ux & uy).sum() / max(uy.sum(), 1))))
refs = [(names[k], fsets[k][3]) for k in range(min(2, len(fsets)))]
for r, sets in reads:
    for w in WIDTHS:
        s, ok = sets[w]
        e = r["sizes"][str(w)]
        for nm, u in refs:
            e["in" + nm] = round(float((s & u & ok).sum() / max((s & ok).sum(), 1)), 4)
            e["phi" + nm] = round(phi(s, u, ok), 4)
    b = r["sizes"][str(r["best"])]
    print("  %-7s wall %.4f +%6.1f ms read %4.1f: best %d (x%.2f)%s; share %.3f cells %.3f%s" % (
        r["name"], r["wall"], r["start_ms"], r["read_ms"], r["best"], r["ratio"], "" if r["clear"] else " unclear", b["share"],
        b["cells"], "".join(" in%s %.3f" % (nm, b.get("in" + nm, float("nan"))) for nm, _ in refs)))
json.dump({"capture": cdir, "families": [{"name": names[k], "reads": [clear[i][0]["name"] for i in fsets[k][2]],
                                          "share": round(float(fsets[k][3].mean()), 4), "cells": round(fsets[k][0], 4)}
                                         for k in range(len(fsets))],
           "reads": [r for r, _ in reads]}, open(out, "w"), indent=0)
