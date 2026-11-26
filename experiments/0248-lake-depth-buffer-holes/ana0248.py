#!/usr/bin/env python3
# BC5 experiment 0248: compare the night lake's depth buffer with the G-buffer target read at the same moment
# (capl0248.sh) and with the next frozen-view shot.
# De-swizzle as exps 0237/0240: Mesa addrlib patterns for 16 pipes and 4-byte elements, ADDR_SW_64KB_Z_X for the depth
# buffer (swz0248-z4.json, gen0248.py) and ADDR_SW_64KB_R_X for the G-buffer (exp 0244's swz0244-4.json); 64-KiB blocks
# of 128x128 elements; the render width (16:9, one 128-element block pitch of 1920..3328) is the one with the least
# block-row shear, taken from the G-buffer and applied to both (the two targets share the frame's size).
# Per capture, in the lake window of exp 0197's patch mask (x 300..1900, y 400..680 of the 1920x1080 shot; images
# resampled by nearest pixel):
#  - the G-buffer's holes: pixels at its cleared far value (>= 9000), as exps 0237-0240;
#  - the depth buffer's values in hole pixels and in the other window pixels (median and 10th/90th percentiles), and
#    the share of each that holds the window's most common depth value;
#  - the depth buffer against the shot's patch mask: phi of "depth equals the window's most common value" with the
#    mask, and the mean |step| of depth across the mask's edges over the window's.
# Writes one greyscale render of the depth buffer (the capture named by RENDER=capNN) to <out dir>.
# Runs on the box in the ubuntu distrobox (numpy, PIL), on the title's data; prints summaries only.
# usage: [RENDER=capNN] python3 -I ana0248.py <capture dir> <run dir> <bench.txt> <swz0248-z4.json> <swz0244-4.json> <out dir>
import collections, glob, json, os, re, sys
import numpy as np
from PIL import Image

cdir, rdir, bench, zsw, rsw, out = sys.argv[1:7]
share = {}
for l in open(bench):
    m = re.match(r"\s*(\d{6})-(ts\d\d)\.png: patch\s+([\d.]+) %", l)
    if m:
        share[m[1]] = (m[2], float(m[3]))
pz, pr = json.load(open(zsw))["patterns"]["4"], json.load(open(rsw))["patterns"]["4"]
X0, X1, Y0, Y1 = 300, 1900, 400, 680
# The title scales its render size per frame (the journal's rt0 is 3328x1872 in some frames and 2048x1152 in others), so
# every 64-KiB block pitch from 1920 to 3328 is a candidate; WMIN=2304 with a 256 step was the first pass.
WMIN = int(os.environ.get("WMIN", "1920"))
win = np.zeros((1080, 1920), bool)
win[Y0:Y1, X0:X1] = True


def coord_offset(pat, key, n):
    v = np.arange(n, dtype=np.int64)
    off = np.zeros(n, dtype=np.int64)
    for i, b in enumerate(pat):
        m = b[key]
        if m:
            par = np.zeros(n, dtype=np.int64)
            for k in range(16):
                if m >> k & 1:
                    par ^= (v >> k) & 1
            off |= par << i
    return off


def image(raw, pat, w, h):
    fx, fy = coord_offset(pat, "x", w), coord_offset(pat, "y", h)
    pitch = -(-w // 128)
    blk = (np.arange(h) // 128)[:, None] * pitch + (np.arange(w) // 128)[None, :]
    idx = (blk * 65536 + (fx[None, :] ^ fy[:, None])) >> 2
    return np.where(idx < raw.size, raw[np.minimum(idx, raw.size - 1)], np.nan)


def shear(img):
    l = np.log1p(np.abs(np.nan_to_num(img, nan=0.0, posinf=0.0, neginf=0.0)))
    d = np.abs(np.diff(l, axis=0))
    at = np.arange(d.shape[0]) % 128 == 127
    return float(d[at].mean() / max(d[~at].mean(), 1e-12))


def pct(a):
    if a.size == 0:
        return "-"
    q = np.nanpercentile(a, [10, 50, 90])
    return "%.6g / %.6g / %.6g" % tuple(q)


caps = {}
for l in open(os.path.join(cdir, "caps.txt")):
    m = re.match(r"(cap\d+) at (\d\d):(\d\d):(\d\d)", l)
    if m:
        caps[m[1]] = "%s%s%s" % m.groups()[1:]
print("# %s: depth 0x1129ec0000 (64KB_Z_X) and G-buffer 0x113f230000 (64KB_R_X), %d captures" % (cdir, len(caps)))
for cap, hms in sorted(caps.items()):
    zf, gf = os.path.join(cdir, cap + ".1129ec0000.bin"), os.path.join(cdir, cap + ".113f230000.bin")
    if not (os.path.exists(zf) and os.path.exists(gf)):
        print("== %s: files missing" % cap)
        continue
    zr = np.frombuffer(open(zf, "rb").read(), dtype="<f4").astype(np.float64)
    gr = np.frombuffer(open(gf, "rb").read(), dtype="<f4").astype(np.float64)
    cand = sorted((shear(image(gr, pr, w, w * 9 // 16)), w) for w in range(WMIN, 3329, 128))
    (sh, w), h = cand[0], cand[0][1] * 9 // 16
    zsh = shear(image(zr, pz, w, h))
    z, g = image(zr, pz, w, h), image(gr, pr, w, h)
    ys, xs = np.arange(1080) * h // 1080, np.arange(1920) * w // 1920
    zz, gg = z[ys][:, xs], g[ys][:, xs]
    nxt = min((k for k in share if k >= hms), default=None)
    shot = glob.glob(os.path.join(rdir, "shots", "%s-%s.png" % (nxt, share[nxt][0]))) if nxt else []
    print("== %s at %s:%s:%s; next shot %s %s; size %dx%d (G-buffer shear %.2f, next best %d at %.2f; depth shear %.2f); depth range %.6g..%.6g" % (
        cap, hms[:2], hms[2:4], hms[4:], share[nxt][0] if nxt else "-", "%.1f %%" % share[nxt][1] if nxt else "-",
        w, h, sh, cand[1][1], cand[1][0], zsh, np.nanmin(z), np.nanmax(z)))
    # Values outside 0..1 cannot be Z_32_FLOAT depth: raw words of compressed tiles (HTILE), read without decompression.
    junk = ~np.isfinite(z) | (np.abs(z) > 1)
    print("   depth words outside 0..1 (compressed tiles?): %.4f of the image" % junk.mean())
    hole = (np.nan_to_num(gg) >= 9000) & win
    other = win & ~hole
    print("   G-buffer holes: %.3f of the window; depth in holes (p10/p50/p90) %s; in the other window pixels %s" % (
        hole[win].mean(), pct(zz[hole]), pct(zz[other])))
    vals = collections.Counter(np.round(zz[win], 7).tolist())
    top, topn = vals.most_common(1)[0]
    is_top = np.round(zz, 7) == top
    print("   the window's most common depth %.7g (%.3f of the window): in holes %.3f, in other pixels %.3f" % (
        top, topn / win.sum(), is_top[hole].mean() if hole.any() else float("nan"), is_top[other].mean()))
    if shot:
        a = np.asarray(Image.open(shot[0]).convert("RGB")).astype(np.float64)
        pm = (a.mean(axis=2) > 47) & (a[:, :, 2] - a[:, :, 0] > 38) & win
        fa, pa = is_top[win], pm[win]
        phi = float(np.corrcoef(fa.astype(float), pa.astype(float))[0, 1]) if pa.any() and (~pa).any() and fa.any() and (~fa).any() else float("nan")
        step = np.abs(np.diff(np.nan_to_num(zz), axis=1))
        edge = (pm[:, 1:] != pm[:, :-1]) & win[:, 1:]
        er = float(step[edge].mean() / max(step[win[:, 1:]].mean(), 1e-12)) if edge.any() else float("nan")
        print("   against the shot's patch mask (%.3f of the window): most common depth in patch %.3f, other %.3f, phi %+.3f; depth step at the mask edges x%.2f" % (
            pa.mean(), fa[pa].mean() if pa.any() else float("nan"), fa[~pa].mean(), phi, er))
        ha = hole[win]
        hphi = float(np.corrcoef(ha.astype(float), pa.astype(float))[0, 1]) if pa.any() and (~pa).any() and ha.any() and (~ha).any() else float("nan")
        ok = np.abs(np.where(np.isfinite(zz), zz, 2.0)) <= 1
        jk = ~ok
        print("   G-buffer holes against the mask: phi %+.3f (holes in patch %.3f, in other %.3f); depth in patch %s, other %s; words outside 0..1 in patch %.3f, other %.3f" % (
            hphi, ha[pa].mean() if pa.any() else float("nan"), ha[~pa].mean(), pct(zz[pm & ok]), pct(zz[win & ~pm & ok]),
            jk[pm].mean() if pm.any() else float("nan"), jk[win & ~pm].mean()))
    if os.environ.get("RENDER") == cap:
        os.makedirs(out, exist_ok=True)
        # Words outside 0..1 are set to 0 first; H1's kept render (cap4) was made before this and is stretched by them.
        zn = np.where(junk, 0.0, np.nan_to_num(z))
        lo, hi = np.percentile(zn, 1), np.percentile(zn, 99)
        img = (255 * np.clip((zn - lo) / max(hi - lo, 1e-12), 0, 1)).astype(np.uint8)
        Image.fromarray(img).save(os.path.join(out, "%s-depth.png" % cap))
        print("   render: %s" % os.path.join(out, "%s-depth.png" % cap))
