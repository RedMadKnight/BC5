#!/usr/bin/env python3
# BC5 experiment 0238: per frozen-view shot of a lake-bench run (exp 0235's IMGS=1 dumps), the water's vertex-stage
# slot-4 image (0x113cb40000, 16_FLOAT, ADDR_SW_64KB_R_X) against the shot's patchwork.
# De-swizzle as exp 0237's deswz0237.py: Mesa addrlib's pattern for 16 pipes (swz0237.json, the pipe count exp 0237
# found), block 256 x 128 elements, pitch = width aligned to 256, offset fx(x) ^ fy(y). The frame's render width is not
# in the dump (the journal's descriptor can be 15 s old), so each 16:9 width from 2304 to 3328 is tried and the one with
# the least block-row shear is used (mean |step| of log depth across the 128-row block boundaries over that between
# other rows; ~1 at the right width, exp 0237: 0.94 against 13-18).
# Against the shot's screenshot: exp 0197's patch mask (luma > 47 and blue - red > 38 in x 300..1900, y 400..680) and the
# image resampled to 1920x1080 (nearest). Per shot: the share of the window at the far value (>= 9000), that share in
# patch and in other pixels, their phi correlation, and the mean |step| of log depth across the mask's edges over the
# window's mean |step|. Classes as img0235.py: clean < 5 %, patched >= 8 %. Then the class means.
# Runs on the box in the ubuntu distrobox (numpy, PIL), on the title's data; prints summaries only.
# usage: python3 -I sum0238.py <run dir> <bench.txt> <swz0237.json>
import glob, json, os, re, sys
import numpy as np
from PIL import Image

rd, bench, swz = sys.argv[1:4]
pat = json.load(open(swz))["patterns"]["4"]
X0, X1, Y0, Y1 = 300, 1900, 400, 680


def coord_offset(key, n):
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


def image(raw, w, h):
    fx, fy = coord_offset("x", w), coord_offset("y", h)
    pitch = -(-w // 256)
    blk = (np.arange(h) // 128)[:, None] * pitch + (np.arange(w) // 256)[None, :]
    idx = (blk * 65536 + (fx[None, :] ^ fy[:, None])) >> 1
    return np.where(idx < raw.size, raw[np.minimum(idx, raw.size - 1)], np.nan)


def logd(img):
    return np.log1p(np.clip(np.nan_to_num(img, nan=0.0), 0, None))


def shear(img):
    d = np.abs(np.diff(logd(img), axis=0))
    at = np.arange(d.shape[0]) % 128 == 127
    return float(d[at].mean() / max(d[~at].mean(), 1e-9))


share = {}
for l in open(bench):
    m = re.match(r"\s*(\d{6})-(ts\d\d)\.png: patch\s+([\d.]+) %", l)
    if m:
        share[m[2]] = (m[1], float(m[3]))
cls = {ts: ("clean" if p < 5 else "patched" if p >= 8 else "mid") for ts, (_, p) in share.items()}
win = np.zeros((1080, 1920), bool)
win[Y0:Y1, X0:X1] = True
rows = []
print("# %s: per shot: class, patch %%, width (block-row shear; next best), far share in the window, far share in patch / "
      "other pixels, phi(far, patch), step at mask edges / window step" % rd)
for ts in sorted(share):
    g = os.path.join(rd, "dumps", ts + ".img.gs4.bin")
    shot = glob.glob(os.path.join(rd, "shots", "%s-%s.png" % (share[ts][0], ts)))
    if not os.path.exists(g) or not shot:
        print("%s %-7s %5.1f %%  (no dump or shot)" % (ts, cls[ts], share[ts][1]))
        continue
    raw = np.frombuffer(open(g, "rb").read(), dtype="<f2").astype(np.float32)
    cand = sorted((shear(image(raw, w, w * 9 // 16)), w) for w in range(2304, 3329, 256))
    (sh, w), (sh2, w2) = cand[0], cand[1]
    h = w * 9 // 16
    img = image(raw, w, h)
    xs, ys = np.arange(1920) * w // 1920, np.arange(1080) * h // 1080
    r = img[ys][:, xs]
    l = logd(r)
    a = np.asarray(Image.open(shot[0]).convert("RGB")).astype(np.float64)
    pm = (a.mean(axis=2) > 47) & (a[:, :, 2] - a[:, :, 0] > 38) & win
    far = np.nan_to_num(r, nan=0.0) >= 9000
    fa, pa = far[win], pm[win]
    phi = float(np.corrcoef(fa.astype(float), pa.astype(float))[0, 1]) if pa.any() and (~pa).any() and fa.any() else float("nan")
    step = np.abs(np.diff(l, axis=1))
    edge = (pm[:, 1:] != pm[:, :-1]) & win[:, 1:]
    er = float(step[edge].mean() / step[win[:, 1:]].mean()) if edge.any() else float("nan")
    fp = float(fa[pa].mean()) if pa.any() else float("nan")
    fo = float(fa[~pa].mean())
    rows.append((cls[ts], share[ts][1], float(fa.mean()), fp, fo, phi, er))
    print("%s %-7s %5.1f %%  %dx%d (%.2f; %d %.2f)  far %.3f  in patch %.3f other %.3f  phi %+.3f  edge step x%.2f" % (
        ts, cls[ts], share[ts][1], w, h, sh, w2, sh2, fa.mean(), fp, fo, phi, er))
print("# class means: shots, patch %, far share in the window, far in patch / other, phi, edge step ratio")
for c in ("clean", "mid", "patched"):
    rs = [x for x in rows if x[0] == c]
    if rs:
        m = np.nanmean(np.array([x[1:] for x in rs]), axis=0)
        print("  %-7s %2d shots  patch %5.1f %%  far %.3f  in patch %.3f other %.3f  phi %+.3f  edge step x%.2f" % (
            (c, len(rs)) + tuple(m)))
