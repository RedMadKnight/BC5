#!/usr/bin/env python3
# BC5 experiment 0271: per pixel, does the depth buffer hold its cleared value (0, reverse-Z far) where the G-buffer holds
# its cleared value (>= 9000)? ana0271.py's grouped medians showed both shares near 0.3-0.4 of the lake window outside the
# cell mask in patched reads and 0 in clean ones. For each read given (complete reads; size from ana0271.py's output), in
# the lake window (x 300..1900, y 400..680 of 1920x1080, nearest-pixel resampling): the share of depth-0 pixels, of
# G-buffer-cleared pixels, of both, and phi between the two; depth words outside 0..1 (stencil bytes, F310) are left out.
# Same de-swizzle as ana0271.py (Z_X / R_X patterns at 16 pipes, 64-KiB blocks of 128x128 elements).
# Prints summaries only. Runs on the box in the ubuntu distrobox (numpy).
# usage: python3 -I coin0271.py <capture dir> <swz0248-z4.json> <swz0244-4.json> <cap>:<width> [...]
import json, os, sys
import numpy as np

cdir, zsw, rsw = sys.argv[1:4]
pz, pr = json.load(open(zsw))["patterns"]["4"], json.load(open(rsw))["patterns"]["4"]
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


for arg in sys.argv[4:]:
    cap, w = arg.split(":")
    w = int(w)
    h = w * 9 // 16
    zr = np.frombuffer(open(os.path.join(cdir, cap + ".1129ec0000.bin"), "rb").read(), dtype="<f4").astype(np.float64)
    gr = np.frombuffer(open(os.path.join(cdir, cap + ".113f230000.bin"), "rb").read(), dtype="<f4").astype(np.float64)
    ys, xs = np.arange(1080) * h // 1080, np.arange(1920) * w // 1920
    zz, gg = image(zr, pz, w, h)[ys][:, xs], image(gr, pr, w, h)[ys][:, xs]
    with np.errstate(invalid="ignore"):
        ok = np.isfinite(zz) & (zz >= 0) & (zz <= 1) & win
    d0 = (zz == 0) & ok
    gc = (np.nan_to_num(gg) >= 9000) & ok
    a, b = d0[ok].astype(float), gc[ok].astype(float)
    phi = float(np.corrcoef(a, b)[0, 1]) if a.std() > 0 and b.std() > 0 else float("nan")
    print("%s %dx%d: window pixels %d; depth 0 %.3f, G-buffer cleared %.3f, both %.3f; of the cleared pixels %.3f have depth 0; phi %+.3f" % (
        cap, w, h, int(ok.sum()), a.mean(), b.mean(), (d0 & gc)[ok].mean(), (d0 & gc).sum() / max(gc.sum(), 1), phi))
