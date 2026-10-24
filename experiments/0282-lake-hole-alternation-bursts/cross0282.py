#!/usr/bin/env python3
# BC5 experiment 0282: the depth-0 sets of the given reads compared across bursts. ana0282.py compares reads within a
# burst only; in the frozen view the same cells should recur if the pattern switches between a few fixed sets. For
# each read given as <burst>.<read>:<width> (reads whose size ana0282.py found clearly, at the size it found): the
# depth-0 set of the lake window (x 300..1900, y 400..680 of 1920x1080, nearest-pixel resampling, depth words outside
# 0..1 left out) and its share; then phi between every two reads, and a grouping: each read joins the first group
# whose first read it matches with phi >= 0.6. Same de-swizzle as ana0282.py (Z_X at 16 pipes, swz0248-z4.json).
# Prints summaries only. Runs on the box in the ubuntu distrobox (numpy), on the title's data.
# usage: python3 -I cross0282.py <capture dir> <swz0248-z4.json> <burst>.<read>:<width> [...]
import json, os, sys
import numpy as np

cdir, zsw = sys.argv[1:3]
pz = json.load(open(zsw))["patterns"]["4"]
win = np.zeros((1080, 1920), bool)
win[400:680, 300:1900] = True


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


def image(raw, p, w, h):
    fx, fy = coord_offset(p, "x", w), coord_offset(p, "y", h)
    pitch = -(-w // 128)
    blk = (np.arange(h) // 128)[:, None] * pitch + (np.arange(w) // 128)[None, :]
    idx = (blk * 65536 + (fx[None, :] ^ fy[:, None])) >> 2
    return raw[np.minimum(idx, raw.size - 1)]


sets = []
for arg in sys.argv[3:]:
    name, w = arg.split(":")
    w = int(w)
    h = w * 9 // 16
    b, z = name.split(".")
    raw = np.frombuffer(open(os.path.join(cdir, "%s.%s.bin" % (b, z)), "rb").read(), dtype="<f4").astype(np.float64)
    ys, xs = np.arange(1080) * h // 1080, np.arange(1920) * w // 1920
    zz = image(raw, pz, w, h)[ys][:, xs]
    with np.errstate(invalid="ignore"):
        ok = np.isfinite(zz) & (zz >= 0) & (zz <= 1) & win
    sets.append((name, w, (zz == 0) & ok, ok))
    print("%s %d: depth 0 %.3f of %d window pixels" % (name, w, float(((zz == 0) & ok)[ok].mean()), int(ok.sum())))


def phi(a, b, m):
    x, y = a[m].astype(float), b[m].astype(float)
    return float(np.corrcoef(x, y)[0, 1]) if x.std() > 0 and y.std() > 0 else float("nan")


groups = []
for i, (n, w, d, ok) in enumerate(sets):
    for g in groups:
        j = g[0]
        if phi(d, sets[j][2], ok & sets[j][3]) >= 0.6:
            g.append(i)
            break
    else:
        groups.append([i])
print("# groups (each read joins the first group whose first read it matches with phi >= 0.6)")
for k, g in enumerate(groups):
    print("  group %d: %s" % (k, " ".join(sets[i][0] for i in g)))
print("# phi between groups' first reads, and the share of pixels both have at depth 0 over each one's share")
for a in range(len(groups)):
    for c in range(a + 1, len(groups)):
        i, j = groups[a][0], groups[c][0]
        m = sets[i][3] & sets[j][3]
        both = float((sets[i][2] & sets[j][2] & m).sum())
        print("  group %d vs %d (%s, %s): phi %+.3f; both %.3f of the first's, %.3f of the second's; union %.3f of the window" % (
            a, c, sets[i][0], sets[j][0], phi(sets[i][2], sets[j][2], m), both / max((sets[i][2] & m).sum(), 1),
            both / max((sets[j][2] & m).sum(), 1), float(((sets[i][2] | sets[j][2]) & m)[m].mean())))
print("# within each group: min and median phi against the group's first read")
for k, g in enumerate(groups):
    if len(g) > 1:
        ps = [phi(sets[i][2], sets[g[0]][2], sets[i][3] & sets[g[0]][3]) for i in g[1:]]
        print("  group %d: %d reads, phi min %+.3f, median %+.3f" % (k, len(g), min(ps), float(np.median(ps))))
