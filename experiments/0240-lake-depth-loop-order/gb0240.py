#!/usr/bin/env python3
# BC5 experiment 0240: the night lake's G-buffer target 0x113f230000 (colour target 0 of the G-buffer and both water
# draws; read as 32_FLOAT by the linear-depth pass, exp 0239), dumped in a frozen view, against the screenshot taken
# right after the dump.
# De-swizzle as exp 0237's deswz0237.py, for 4-byte elements: Mesa addrlib's ADDR_SW_64KB_R_X pattern for 16 pipes
# (swz0240-4.json from gen0240.py), block 128 x 128 elements, pitch = width aligned to 128, offset fx(x) ^ fy(y). The
# frame's width is the 16:9 width from 2304 to 3328 with the least block-row shear (exp 0238's test, at 128-row block
# boundaries).
# Prints the value statistics of the window that exp 0197's patch mask uses (x 300..1900, y 400..680 of the 1920x1080
# screenshot, the image resampled by nearest pixel): the most common values and their shares, and, against the patch
# mask, the share of the window's most common value in patch and in other pixels, their phi, and the mean |step| of
# log(1 + |value|) across the mask's edges over the window's mean. Writes one greyscale render (log |value|) to
# <out dir>. Runs in the box's ubuntu distrobox (numpy, PIL), on the title's data; prints summaries only.
# usage: python3 -I gb0240.py <dump.bin> <swz0240-4.json> <screenshot.png> <out dir> [render name]
import collections, json, os, sys
import numpy as np
from PIL import Image

dump, swz, shot, out = sys.argv[1:5]
name = sys.argv[5] if len(sys.argv) > 5 else None
raw = np.frombuffer(open(dump, "rb").read(), dtype="<f4").astype(np.float64)
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


def image(w, h):
    fx, fy = coord_offset("x", w), coord_offset("y", h)
    pitch = -(-w // 128)
    blk = (np.arange(h) // 128)[:, None] * pitch + (np.arange(w) // 128)[None, :]
    idx = (blk * 65536 + (fx[None, :] ^ fy[:, None])) >> 2
    return np.where(idx < raw.size, raw[np.minimum(idx, raw.size - 1)], np.nan)


def lg(img):
    return np.log1p(np.abs(np.nan_to_num(img, nan=0.0, posinf=0.0, neginf=0.0)))


def shear(img):
    d = np.abs(np.diff(lg(img), axis=0))
    at = np.arange(d.shape[0]) % 128 == 127
    return float(d[at].mean() / max(d[~at].mean(), 1e-12))


cand = sorted((shear(image(w, w * 9 // 16)), w) for w in range(2304, 3329, 256))
(sh, w), (sh2, w2) = cand[0], cand[1]
h = w * 9 // 16
img = image(w, h)
print("# %s: %d floats; width by block-row shear: %dx%d (%.2f; next %d %.2f); finite %.4f, range %.6g..%.6g" % (
    dump, raw.size, w, h, sh, w2, sh2, float(np.isfinite(img).mean()), float(np.nanmin(img)), float(np.nanmax(img))))
xs, ys = np.arange(1920) * w // 1920, np.arange(1080) * h // 1080
r = img[ys][:, xs]
win = np.zeros((1080, 1920), bool)
win[Y0:Y1, X0:X1] = True
vals = collections.Counter(np.round(r[win], 6).tolist())
print("  window: %d pixels, %d distinct values; most common: %s" % (
    int(win.sum()), len(vals), ", ".join("%.6g (%.3f)" % (v, c / win.sum()) for v, c in vals.most_common(5))))
a = np.asarray(Image.open(shot).convert("RGB")).astype(np.float64)
pm = (a.mean(axis=2) > 47) & (a[:, :, 2] - a[:, :, 0] > 38) & win
top = vals.most_common(1)[0][0]
m = np.round(r, 6) == top
fa, pa = m[win], pm[win]
phi = float(np.corrcoef(fa.astype(float), pa.astype(float))[0, 1]) if pa.any() and (~pa).any() and fa.any() and (~fa).any() else float("nan")
l = lg(r)
step = np.abs(np.diff(l, axis=1))
edge = (pm[:, 1:] != pm[:, :-1]) & win[:, 1:]
er = float(step[edge].mean() / step[win[:, 1:]].mean()) if edge.any() else float("nan")
print("  screenshot %s: patch share %.3f; most common value %.6g in patch %.3f, other %.3f, phi %+.3f; "
      "step at the mask edges / window x%.2f" % (os.path.basename(shot), pa.mean(), top,
                                                  fa[pa].mean() if pa.any() else float("nan"), fa[~pa].mean(), phi, er))
if name:
    os.makedirs(out, exist_ok=True)
    g = lg(img)
    g = (255 * (1 - g / max(g.max(), 1e-9))).astype(np.uint8)
    Image.fromarray(g).save(os.path.join(out, name))
    print("  render: %s" % os.path.join(out, name))
