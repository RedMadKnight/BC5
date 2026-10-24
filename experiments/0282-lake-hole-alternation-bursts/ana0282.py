#!/usr/bin/env python3
# BC5 experiment 0282: does the night lake's hole pattern alternate from frame to frame? Exp 0274 (F341) found the
# depth-0 and G-buffer-cleared pixel sets of one read pair (taken a few frames apart) coincident, half-overlapping or
# disjoint from run to run. capb0282.sh takes bursts of K back-to-back depth reads (burst0282.py, start and read time
# of each) and one G-buffer read. Per burst and read, in the lake window (x 300..1900, y 400..680 of the 1920x1080 shot,
# nearest-pixel resampling; depth words outside 0..1, other sizes' stencil bytes (F310), are left out):
#  - the read's render size: the 16:9 size (2048..3328, F309/F310) with the least block-row shear of the depth image
#    itself, and the next best; a read is complete when that shear is <= 3 (the G-buffer read's size by its own shear,
#    as exps 0271/0274, is printed as a check);
#  - the share of depth-0 pixels (cleared, reverse-Z far) in the window, in the shot cell mask and in the rest, and per
#    band of 70 shot rows (a read goes through memory block row by block row, so a frame change during a read shows as
#    bands that differ);
#  - for every pair of complete reads of a burst: the lag between their starts (ms), the share of the first read's
#    depth-0 pixels that are depth 0 in the second, phi between the two sets, and phi per band;
#  - every depth read against the burst's G-buffer read: phi of depth 0 against G-buffer cleared (>= 9000).
# A pattern that stays put gives phi near +1 at every lag; one that alternates between complementary cells each frame
# gives negative phi at odd frame lags and positive phi at even ones; one that is new each frame gives phi near 0.
# The cell mask and the burst's state (clean/patched/mixed) come from the run's shots as in exp 0274's ana0274.py (exp
# 0197's metric, patched >= 8 %, clean < 5 %). De-swizzle as exps 0271/0274: Mesa addrlib patterns at 16 pipes and
# 4-byte elements, ADDR_SW_64KB_Z_X for the depth (swz0248-z4.json), ADDR_SW_64KB_R_X for the G-buffer (swz0244-4.json).
# Prints summaries only; no image is written. Runs on the box in the ubuntu distrobox (numpy, PIL), on the title's data.
# usage: python3 -I ana0282.py <capture dir> <run dir> <bench.txt> <swz0248-z4.json> <swz0244-4.json>
import collections, itertools, json, os, re, statistics, sys
import numpy as np
from PIL import Image

cdir, rdir, bench, zsw, rsw = sys.argv[1:6]
pz, pr = json.load(open(zsw))["patterns"]["4"], json.load(open(rsw))["patterns"]["4"]
SIZES = [(w, w * 9 // 16) for w in (2048, 2304, 2560, 2816, 3072, 3328)]
X0, X1, Y0, Y1 = 300, 1900, 400, 680
BANDS = [(y, y + 70) for y in range(Y0, Y1, 70)]
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
cells = (np.mean(masks, axis=0) >= 0.5) & win if masks else np.zeros_like(win)
rest = win & ~cells


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
    if (id(p), w, h) not in IDX:  # word index of each element, per pattern and size (each read is decoded at six sizes)
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


def state_of(hms):
    prev = [s for s in shots if s[0] <= hms]
    nxt = [s for s in shots if s[0] >= hms]
    p, n = (prev[-1] if prev else None), (nxt[0] if nxt else None)
    if p and n and p[2] < 5 and n[2] < 5:
        return "clean"
    if p and n and p[2] >= 8 and n[2] >= 8:
        return "patched"
    return "mixed"


def load(f):
    return np.frombuffer(open(f, "rb").read(), dtype="<f4").astype(np.float64)


def screen(img, w, h):
    ys, xs = np.arange(1080) * h // 1080, np.arange(1920) * w // 1920
    return img[ys][:, xs]


def phi(a, b, m):
    x, y = a[m].astype(float), b[m].astype(float)
    return float(np.corrcoef(x, y)[0, 1]) if x.size > 1 and x.std() > 0 and y.std() > 0 else float("nan")


def share(a, m):
    return float(a[m].mean()) if m.any() else float("nan")


bursts = []
for l in open(os.path.join(cdir, "caps.txt")):
    m = re.match(r"(b\d+) at (\d\d):(\d\d):(\d\d)", l)
    if m:
        bursts.append((m[1], "%s%s%s" % m.groups()[1:]))
print("# %s: %d bursts; %d patched shots give the cell mask: %.3f of the lake window (%d pixels)" % (
    cdir, len(bursts), len(masks), cells[win].mean(), int(cells.sum())))
lags = collections.defaultdict(list)
for b, hms in bursts:
    st = state_of(hms)
    times = {}
    tf = os.path.join(cdir, b + ".times.txt")
    for l in open(tf) if os.path.exists(tf) else []:
        m = re.match(r"(\S+) start ([\d.]+) read ([\d.]+) write ([\d.]+)", l)
        if m:
            times[m[1]] = (float(m[2]), float(m[3]), float(m[4]))
    print("== %s at %s:%s:%s %s" % (b, hms[:2], hms[2:4], hms[4:], st))
    gf = os.path.join(cdir, b + ".g.bin")
    gc = None
    if os.path.exists(gf):
        gr = load(gf)
        gcand = sorted((shear(image(gr, pr, w, h)), w, h) for w, h in SIZES)
        gsh, gw, gh = gcand[0]
        gc = np.nan_to_num(screen(image(gr, pr, gw, gh), gw, gh)) >= 9000
        print("   g   start %6.1f read %5.1f ms: size %dx%d (shear %.2f, next %d at %.2f); cleared %.3f of the window" % (
            *times.get("g", (float("nan"),) * 3)[:2], gw, gh, gsh, gcand[1][1], gcand[1][0], share(gc, win)))
    reads = []
    for k in itertools.count():
        zf = os.path.join(cdir, "%s.z%d.bin" % (b, k))
        if not os.path.exists(zf):
            break
        zr = load(zf)
        cand = sorted((shear(image(zr, pz, w, h)), w, h) for w, h in SIZES)
        zsh, w, h = cand[0]
        zz = screen(image(zr, pz, w, h), w, h)
        with np.errstate(invalid="ignore"):
            ok = np.isfinite(zz) & (zz >= 0) & (zz <= 1) & win
        d0 = (zz == 0) & ok
        t = times.get("z%d" % k, (float("nan"),) * 3)
        complete = zsh <= 3
        bands = " ".join("%.3f" % share(d0, ok & (np.arange(1080)[:, None] >= y0) & (np.arange(1080)[:, None] < y1))
                         for y0, y1 in BANDS)
        gphi = phi(d0, gc, ok) if gc is not None else float("nan")
        print("   z%d  start %6.1f read %5.1f ms: size %dx%d (shear %.2f, next %d at %.2f)%s; depth 0 %.3f (cells %.3f, rest %.3f; bands %s); phi with G-buffer cleared %+.3f" % (
            k, t[0], t[1], w, h, zsh, cand[1][1], cand[1][0], "" if complete else " INCOMPLETE", share(d0, ok),
            share(d0, ok & cells), share(d0, ok & rest), bands, gphi))
        reads.append((k, t[0], w, complete, d0, ok))
    for (i, ti, wi, ci, di, oki), (j, tj, wj, cj, dj, okj) in itertools.combinations(reads, 2):
        if not (ci and cj):
            continue
        m = oki & okj
        p = phi(di, dj, m)
        kept = float((di & dj & m).sum() / max((di & m).sum(), 1))
        bp = " ".join("%+.2f" % phi(di, dj, m & (np.arange(1080)[:, None] >= y0) & (np.arange(1080)[:, None] < y1))
                      for y0, y1 in BANDS)
        print("   pair z%d-z%d lag %6.1f ms sizes %d/%d: of z%d's depth-0 pixels %.3f are depth 0 in z%d; phi %+.3f (bands %s)" % (
            i, j, tj - ti, wi, wj, i, kept, j, p, bp))
        lags[st].append((tj - ti, p, wi == wj))
print("# pairs by state and lag (ms): number of pairs, median phi, range; same-size pairs only in brackets")
for st in sorted(lags):
    rows = lags[st]
    for lo, hi in ((0, 25), (25, 50), (50, 75), (75, 100), (100, 150), (150, 1e9)):
        sel = [p for lag, p, _ in rows if lo <= lag < hi and p == p]
        same = [p for lag, p, s in rows if lo <= lag < hi and p == p and s]
        if sel:
            print("  %-7s lag %3d..%-4s %3d pairs, phi median %+.3f, %+.3f..%+.3f [%d same-size, median %s]" % (
                st, lo, "" if hi > 1e8 else "%d" % hi, len(sel), statistics.median(sel), min(sel), max(sel), len(same),
                "%+.3f" % statistics.median(same) if same else "-"))
