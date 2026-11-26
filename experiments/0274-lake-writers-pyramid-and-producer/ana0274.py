#!/usr/bin/env python3
# BC5 experiment 0274 (exp 0271's ana0271.py, unchanged but for its name): the night lake's depth buffer and G-buffer in the patch cells, clean against patched reads of one
# run (capl0274.sh: depth memory 0x1129ec0000 + 0x2940000, G-buffer 0x113f230000 + 0x1860000, every STEP s).
# De-swizzle as exps 0237/0248/0251: Mesa addrlib patterns at 16 pipes and 4-byte elements, ADDR_SW_64KB_Z_X for the
# depth buffer (swz0248-z4.json) and ADDR_SW_64KB_R_X for the G-buffer (swz0244-4.json), 64-KiB blocks of 128x128
# elements; a read's frame size is the 16:9 render size (2048..3328, the sizes the journal shows, F309/F310) with the
# least block-row shear in the G-buffer, and a read is complete when that shear is <= 2 and the depth image's is <= 3
# (reads that catch a frame mid-update are left out of the grouped summary).
# The cell mask: pixels of the lake window (x 300..1900, y 400..680 of the 1920x1080 shot) that are patch in at least
# half of the run's patched shots (exp 0197's metric >= 8 %; exp 0248's colour rule). Images are resampled to 1920x1080
# by nearest pixel. Depth words outside 0..1 (other sizes' stencil bytes, F310) are left out.
# Per read and per (size, state) group of complete reads it prints, inside the cells and in the rest of the window:
# the depth median, the share of depth 0 (cleared, reverse-Z far), the G-buffer's cleared share (>= 9000), and the depth
# step across the cell edges over the window's mean step. Prints summaries only; no image is written.
# Runs on the box in the ubuntu distrobox (numpy, PIL), on the title's data.
# usage: python3 -I ana0274.py <capture dir> <run dir> <bench.txt> <swz0248-z4.json> <swz0244-4.json>
import collections, json, os, re, statistics, sys
import numpy as np
from PIL import Image

cdir, rdir, bench, zsw, rsw = sys.argv[1:6]
pz, pr = json.load(open(zsw))["patterns"]["4"], json.load(open(rsw))["patterns"]["4"]
SIZES = [(w, w * 9 // 16) for w in (2048, 2304, 2560, 2816, 3072, 3328)]
X0, X1, Y0, Y1 = 300, 1900, 400, 680
win = np.zeros((1080, 1920), bool)
win[Y0:Y1, X0:X1] = True
shots = []
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
cells = (np.mean(masks, axis=0) >= 0.5) & win if masks else np.zeros_like(win)
rest = win & ~cells
edge = (cells[:, 1:] != cells[:, :-1]) & win[:, 1:]


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


def shear(img):
    good = np.isfinite(img) & (np.abs(img) < 1e30)
    l = np.log1p(np.abs(np.where(good, img, 0.0)))
    d = np.abs(np.diff(l, axis=0))
    at = np.arange(d.shape[0]) % 128 == 127
    return float(d[at].mean() / max(d[~at].mean(), 1e-12))


def state_of(hms):
    prev = [s for s in shots if s[0] <= hms]
    nxt = [s for s in shots if s[0] >= hms]
    p, n = (prev[-1] if prev else None), (nxt[0] if nxt else None)
    if p and n and p[2] < 5 and n[2] < 5:
        return "clean"
    if p and n and p[2] >= 8 and n[2] >= 8:
        return "patched"
    return "mixed"


caps = {}
for l in open(os.path.join(cdir, "caps.txt")):
    m = re.match(r"(cap\d+) at (\d\d):(\d\d):(\d\d)", l)
    if m:
        caps[m[1]] = "%s%s%s" % m.groups()[1:]
print("# %s: %d reads; %d patched shots give the cell mask: %.3f of the lake window (%d pixels)" % (
    cdir, len(caps), len(masks), cells[win].mean(), int(cells.sum())))
groups = collections.defaultdict(list)
for cap, hms in sorted(caps.items()):
    zf, gf = os.path.join(cdir, cap + ".1129ec0000.bin"), os.path.join(cdir, cap + ".113f230000.bin")
    if not (os.path.exists(zf) and os.path.exists(gf)):
        print("== %s: files missing" % cap)
        continue
    zr = np.frombuffer(open(zf, "rb").read(), dtype="<f4").astype(np.float64)
    gr = np.frombuffer(open(gf, "rb").read(), dtype="<f4").astype(np.float64)
    cand = sorted((shear(image(gr, pr, w, h)), w, h) for w, h in SIZES)
    gsh, w, h = cand[0]
    z, g = image(zr, pz, w, h), image(gr, pr, w, h)
    zsh = shear(z)
    ys, xs = np.arange(1080) * h // 1080, np.arange(1920) * w // 1920
    zz, gg = z[ys][:, xs], g[ys][:, xs]
    with np.errstate(invalid="ignore"):
        ok = np.isfinite(zz) & (zz >= 0) & (zz <= 1)
    st = state_of(hms)
    complete = gsh <= 2 and zsh <= 3
    r = {}
    for name, m in (("cells", cells), ("rest", rest)):
        v = zz[m & ok]
        r[name] = (float(np.median(v)) if v.size else float("nan"), float((v == 0).mean()) if v.size else float("nan"),
                   float((np.nan_to_num(gg[m]) >= 9000).mean()))
    step = np.abs(np.diff(np.where(ok, zz, 0.0), axis=1))
    ok2 = ok[:, 1:] & ok[:, :-1]
    er = float(step[edge & ok2].mean() / max(step[win[:, 1:] & ok2].mean(), 1e-12)) if (edge & ok2).any() else float("nan")
    print("== %s at %s:%s:%s %-7s size %dx%d (G-buffer shear %.2f, next %d at %.2f; depth shear %.2f)%s" % (
        cap, hms[:2], hms[2:4], hms[4:], st, w, h, gsh, cand[1][1], cand[1][0], zsh, "" if complete else " INCOMPLETE"))
    print("   cells: depth median %.6g, depth 0 %.3f, G-buffer cleared %.3f | rest: depth median %.6g, depth 0 %.3f, G-buffer cleared %.3f | edge step x%.2f" % (
        *r["cells"], *r["rest"], er))
    if complete:
        groups[(w, st)].append((r, er))
print("# complete reads by (size, state): medians over reads")
for (w, st), rows in sorted(groups.items()):
    med = lambda f: statistics.median(f(x) for x in rows)
    print("  %d %-7s %2d reads | cells: depth %.6g, depth-0 %.3f, cleared %.3f | rest: depth %.6g, depth-0 %.3f, cleared %.3f | edge x%.2f" % (
        w, st, len(rows), med(lambda x: x[0]["cells"][0]), med(lambda x: x[0]["cells"][1]), med(lambda x: x[0]["cells"][2]),
        med(lambda x: x[0]["rest"][0]), med(lambda x: x[0]["rest"][1]), med(lambda x: x[0]["rest"][2]), med(lambda x: x[1])))
