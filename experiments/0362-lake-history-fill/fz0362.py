#!/usr/bin/env python3
# BC5 experiment 0362, written after seeing run H1: sn0362.py's s0/s1/s2 did not fall where planned. In H1 the lake's
# depth memory has a per-pixel image at the frame's width only after the frame's last D burst (~+18.7 ms): before it the
# snapshots have no block-row structure at any width (shear ~1.0), and at +1 ms most hold a near-constant image
# ("flat"). So this script takes as a frame's final depth only snapshots with their own clear size (sn0362.py reads:
# next-best shear >= 3 x the best, the best > 0.05, untorn, width 2048-2560):
#   s1 or s2 taken >= 17 ms after the frame's start -> that frame's final; s0 (at +1 ms) -> the previous frame's final.
# Per final: the lake window's depth-0 share; the states as ph0357.py (FLOOR, leading eigenvector) over the finals;
# X, Y and O as in sn0362.py. Pairs of finals of consecutive frames (g, g+1, one capture), and pairs of two snapshots
# of the same frame's final (s2 of g and s0 of g+1): per region the share of pixels bitwise equal and of depth 0 in
# each, at the same width only. Per snapshot class (flat, structure-less, final): the share of exact zeros, the most
# common value and its share. Prints summaries only.
# usage: python3 -I fz0362.py <snap dir> <reads json> <swz0248-z4.json> [FLOOR]   (on the box, in the distrobox)
import collections, json, os, sys
import numpy as np

sdir, rjson, zsw = sys.argv[1:4]
floor = float(sys.argv[4]) if len(sys.argv) > 4 else 0.03
X0, X1, Y0, Y1 = 300, 1900, 400, 680
S_OFF = 0x300000
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


def window(raw, w):
    if w not in IDX:
        h = w * 9 // 16
        fx, fy = coord_offset(pz, "x", w), coord_offset(pz, "y", h)
        pitch = -(-w // 128)
        ys, xs = np.arange(Y0, Y1) * h // 1080, np.arange(X0, X1) * w // 1920
        blk = (ys // 128)[:, None] * pitch + (xs // 128)[None, :]
        IDX[w] = ((blk * 65536 + (fx[xs][None, :] ^ fy[ys][:, None])) >> 2) - S_OFF // 4
    li = IDX[w]
    inside = (li >= 0) & (li < raw.size)
    z = raw[np.clip(li, 0, raw.size - 1)]
    with np.errstate(invalid="ignore"):
        ok = inside & np.isfinite(z) & (z >= 0) & (z <= 1)
    return z, ok


def load(name):
    return np.frombuffer(open(os.path.join(sdir, name + ".bin"), "rb").read(), dtype="<f4")


reads = json.load(open(rjson))["reads"]
cls = {}
for r in reads:
    v = sorted((x, int(w)) for w, x in r["shear"].items() if x == x)
    if v and v[0][0] <= 0.05:
        cls[r["name"]] = "flat"
    elif r["clear"] and not r["torn"] and r["best"] in (2048, 2304, 2560):
        cls[r["name"]] = "final"
    elif r["clear"]:
        cls[r["name"]] = "clear-other"
    else:
        cls[r["name"]] = "no-structure"
    r["cls"] = cls[r["name"]]
# value statistics per class (every 16th word)
print("# snapshot classes and their values (every 16th word):")
for c in ("flat", "no-structure", "final", "clear-other"):
    rs = [r for r in reads if r["cls"] == c]
    if not rs:
        continue
    zs, tops, since = [], collections.Counter(), []
    for r in rs:
        a = load(r["name"])[::16]
        zs.append(float((a == 0).mean()))
        u, n = np.unique(a.view("<u4"), return_counts=True)
        k = int(np.argmax(n))
        tops["%08x %.2f" % (u[k], n[k] / a.size)] += 1
        since.append(r["since"])
    print("  %-12s %3d (torn %d): since %.1f-%.1f ms (median %.1f); zeros median %.3f (%.3f-%.3f); commonest word (share): %s" % (
        c, len(rs), sum(r["torn"] for r in rs), min(since), max(since), float(np.median(since)), float(np.median(zs)), min(zs), max(zs),
        ", ".join("%s x%d" % kv for kv in tops.most_common(4))))
# finals: which frame's final each one is
fin = {}
for r in reads:
    if r["cls"] != "final":
        continue
    cap, f, s = r["name"].split(".")
    f, s = int(f[1:]), int(s[1:])
    if s == 0:
        g = f - 1
    elif r["since"] >= 17:
        g = f
    else:
        continue
    fin.setdefault((cap, g), []).append(r)
print("# finals: %d snapshots for %d frames (%s)" % (sum(len(v) for v in fin.values()), len(fin),
      ", ".join("%s.f%d:%s" % (k[0], k[1], "+".join("s%s@%d/%d" % (r["name"][-1], round(r["since"]), r["best"]) for r in v)) for k, v in sorted(fin.items()))))
data = {}
for k, v in fin.items():
    r = v[-1]
    z, ok = window(load(r["name"]).astype(np.float64), r["best"])
    data[k] = (z, ok, r["best"], r["name"])
keys = sorted(data)
common = np.logical_and.reduce([data[k][1] for k in keys])
M = np.array([((data[k][0] == 0) & data[k][1])[common] for k in keys], dtype=np.float64)
share = M.mean(axis=1)
print("# window pixels valid in every final: %.3f; depth-0 share per final: %s" % (common.mean(), " ".join("%.3f" % s for s in share)))
state = {k: "0" for k, s in zip(keys, share) if s < floor}
hz = [i for i, s in enumerate(share) if s >= floor]
X = Y = np.zeros(common.shape, bool)
if len(hz) >= 2:
    Mh = M[hz]
    Z = (Mh - Mh.mean(axis=1, keepdims=True)) / np.maximum(Mh.std(axis=1, keepdims=True), 1e-9)
    PHI = Z @ Z.T / Mh.shape[1]
    C = PHI - PHI.mean(axis=0, keepdims=True) - PHI.mean(axis=1, keepdims=True) + PHI.mean()
    _, vec = np.linalg.eigh(C)
    side = vec[:, -1] > 0
    a, b = [i for i, s in enumerate(side) if s], [i for i, s in enumerate(side) if not s]
    for i, s in zip(hz, side):
        state[keys[i]] = "A" if s else "B"
    wa = PHI[np.ix_(a, a)][np.triu_indices(len(a), 1)].mean() if len(a) > 1 else float("nan")
    wb = PHI[np.ix_(b, b)][np.triu_indices(len(b), 1)].mean() if len(b) > 1 else float("nan")
    bt = PHI[np.ix_(a, b)].mean() if a and b else float("nan")
    X, Y = np.zeros(common.shape, bool), np.zeros(common.shape, bool)
    if a:
        X[common] = Mh[a].mean(axis=0) >= 0.5
    if b:
        Y[common] = Mh[b].mean(axis=0) >= 0.5
    print("# states: %d below the floor %.2f, %d with holes: A %d, B %d; phi within %.2f / %.2f, between %.2f; X %.3f, Y %.3f of the window, both %.4f" % (
        len(keys) - len(hz), floor, len(hz), len(a), len(b), wa, wb, bt, X.mean(), Y.mean(), (X & Y).mean()))
O = ~(X | Y)
print("# finals in order: %s" % " ".join("%s.f%d:%s%s" % (k[0], k[1], state[k], "" if data[k][2] == 2560 else "(%d)" % data[k][2]) for k in keys))


def cmp(p, q):
    zp, op, wp, _ = p
    zq, oq, wq, _ = q
    if wp != wq:
        return "widths %d/%d" % (wp, wq)
    out = []
    for nm, R in (("X", X), ("Y", Y), ("O", O), ("lake", X | Y)):
        m = R & op & oq
        if m.sum() == 0:
            continue
        out.append("%s eq %.3f z0 %.2f>%.2f" % (nm, float((zp == zq)[m].mean()), float((zp == 0)[m].mean()), float((zq == 0)[m].mean())))
    return "; ".join(out)


print("# the same frame's final seen twice (s2 of g, then s0 of g+1):")
for k, v in sorted(fin.items()):
    if len(v) >= 2:
        a2 = [r for r in v if r["name"].endswith("s0")]
        b2 = [r for r in v if not r["name"].endswith("s0")]
        if a2 and b2:
            p = window(load(b2[0]["name"]).astype(np.float64), b2[0]["best"]) + (b2[0]["best"], "")
            q = window(load(a2[0]["name"]).astype(np.float64), a2[0]["best"]) + (a2[0]["best"], "")
            print("  %s.f%d %s -> %s: %s" % (k[0], k[1], b2[0]["name"], a2[0]["name"], cmp(p, q)))
print("# consecutive frames' finals (g -> g+1):")
for k in keys:
    k2 = (k[0], k[1] + 1)
    if k2 in data:
        print("  %s.f%d %s -> f%d %s: %s" % (k[0], k[1], state[k], k2[1], state[k2], cmp(data[k], data[k2])))
