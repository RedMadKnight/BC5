#!/usr/bin/env python3
# BC5 experiment 0244: summarise cap0244.py's captures against the screenshots of the same run. For each capture
# (<dir>/capNN.desc.txt and its .bin files) the first frozen-view shot after it gives the patch mask (exp 0197:
# luma > 47 and blue - red > 38 in x 300..1900, y 400..680 of the 1920x1080 shot). Each captured image in
# ADDR_SW_64KB_R_X (sw 27) with 2-, 4- or 8-byte elements is de-swizzled as exps 0237/0240 (Mesa addrlib pattern for
# 16 pipes from swz0244-<bytes>.json; block width/height 2^ceil(n/2) x 2^floor(n/2) elements, n = 16 - log2(bytes);
# pitch = width aligned to the block width) at the size its T# gives; the G-buffer target at the width with the least
# block-row shear (exp 0238). Channel 0 is read as 16_FLOAT (formats 13, 29, 71) or 32_FLOAT (22). Per image: the
# share of the window's most common value in patch and in other pixels, their phi, and the mean |step| of
# log(1 + |value|) across the mask's edges over the window's. Other images: md5 only, and whether it changed between
# captures. Runs on the box in the ubuntu distrobox (numpy, PIL), on the title's data; prints summaries only.
# usage: python3 -I ana0244.py <capture dir> <run dir> <bench.txt> <dir of swz0244-*.json>
import collections, glob, hashlib, json, os, re, sys
import numpy as np
from PIL import Image

cdir, rdir, bench, sdir = sys.argv[1:5]
share = {}
for l in open(bench):
    m = re.match(r"\s*(\d{6})-(ts\d\d)\.png: patch\s+([\d.]+) %", l)
    if m:
        share[m[1]] = (m[2], float(m[3]))
pats = {b: json.load(open(os.path.join(sdir, "swz0244-%d.json" % b)))["patterns"]["4"] for b in (2, 4, 8)}
X0, X1, Y0, Y1 = 300, 1900, 400, 680
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


def deswz(raw_bytes, bpe, w, h, chan_dtype):
    nb = 16 - (bpe.bit_length() - 1)
    bw, bh = 1 << ((nb + 1) // 2), 1 << (nb - (nb + 1) // 2)
    pat = pats[bpe]
    fx, fy = coord_offset(pat, "x", w), coord_offset(pat, "y", h)
    pitch = -(-w // bw)
    blk = (np.arange(h) // bh)[:, None] * pitch + (np.arange(w) // bw)[None, :]
    addr = blk * 65536 + (fx[None, :] ^ fy[:, None])
    vals = np.frombuffer(raw_bytes[: len(raw_bytes) // bpe * bpe], dtype=np.uint8)
    elem = addr // bpe
    ok = elem < len(vals) // bpe
    e = np.minimum(elem, len(vals) // bpe - 1)
    ch = np.frombuffer(raw_bytes[: (len(raw_bytes) // bpe) * bpe], dtype=chan_dtype)
    per = bpe // np.dtype(chan_dtype).itemsize
    out = ch[e * per].astype(np.float64)
    out[~ok] = np.nan
    return out


def lg(a):
    return np.log1p(np.abs(np.nan_to_num(a, nan=0.0, posinf=0.0, neginf=0.0)))


def shear(img, bh):
    d = np.abs(np.diff(lg(img), axis=0))
    at = np.arange(d.shape[0]) % bh == bh - 1
    return float(d[at].mean() / max(d[~at].mean(), 1e-12))


def compare(img, pm):
    h, w = img.shape
    r = img[(np.arange(1080) * h // 1080)][:, (np.arange(1920) * w // 1920)]
    vals = collections.Counter(np.round(r[win], 5).tolist())
    top, topn = vals.most_common(1)[0]
    fa, pa = (np.round(r, 5) == top)[win], pm[win]
    phi = float(np.corrcoef(fa.astype(float), pa.astype(float))[0, 1]) if pa.any() and (~pa).any() and fa.any() and (~fa).any() else float("nan")
    step = np.abs(np.diff(lg(r), axis=1))
    edge = (pm[:, 1:] != pm[:, :-1]) & win[:, 1:]
    er = float(step[edge].mean() / step[win[:, 1:]].mean()) if edge.any() else float("nan")
    return "mode %.5g (%.3f of the window): in patch %.3f, other %.3f, phi %+.3f; edge step x%.2f" % (
        top, topn / win.sum(), fa[pa].mean() if pa.any() else float("nan"), fa[~pa].mean(), phi, er)


DT = {13: (2, np.float16), 29: (4, np.float16), 71: (8, np.float16), 22: (4, np.float32)}
prev_md5 = {}
for desc in sorted(glob.glob(os.path.join(cdir, "cap*.desc.txt"))):
    lines = open(desc).read().splitlines()
    t = re.search(r"capture at (\d\d):(\d\d):(\d\d)", lines[0])
    hms = "%s%s%s" % t.groups()
    nxt = min((k for k in share if k >= hms), default=None)
    shot = glob.glob(os.path.join(rdir, "shots", "%s-%s.png" % (nxt, share[nxt][0]))) if nxt else []
    pm = None
    if shot:
        a = np.asarray(Image.open(shot[0]).convert("RGB")).astype(np.float64)
        pm = (a.mean(axis=2) > 47) & (a[:, :, 2] - a[:, :, 0] > 38) & win
    pfx = desc[:-len(".desc.txt")]
    print("== %s at %s:%s:%s; next shot %s (%s) patch %s" % (
        os.path.basename(pfx), *t.groups(), nxt, share[nxt][0] if nxt else "-", "%.1f %%" % share[nxt][1] if nxt else "-"))
    for l in lines[1:]:
        m = re.match(r"(\S+?): (?:table 0x[0-9a-f]+ \(([^)]*)\): )?T# base 0x([0-9a-f]+) (\d+)x(\d+) fmt (\d+) levels (\d+) sw (\d+)", l)
        name = l.split(":")[0]
        fname = "%s.%s.bin" % (pfx, "gbuffer" if name == "gbuffer" else re.sub(r"\+0x", "_", name))
        if not m or not os.path.exists(fname):
            print("  %s: %s" % (name, l.split(": ", 1)[1] if ": " in l else l))
            continue
        data = open(fname, "rb").read()
        md5 = hashlib.md5(data).hexdigest()[:8]
        changed = "" if name not in prev_md5 else (" (changed since the last capture)" if prev_md5[name] != md5 else " (same as the last capture)")
        prev_md5[name] = md5
        w, h, fmt, sw = int(m[4]), int(m[5]), int(m[6]), int(m[8])
        head = "  %s: 0x%s %dx%d fmt %d sw %d%s md5 %s%s" % (name, m[3], w, h, fmt, sw, " [%s]" % m[2] if m[2] else "", md5, changed)
        if sw == 27 and fmt in DT and pm is not None:
            bpe, dt = DT[fmt]
            nb = 16 - (bpe.bit_length() - 1)
            bh = 1 << (nb - (nb + 1) // 2)
            if name == "gbuffer":
                cand = sorted((shear(deswz(data, bpe, ww, ww * 9 // 16, dt), bh), ww) for ww in range(2304, 3329, 256))
                (sh, w), h = cand[0], cand[0][1] * 9 // 16
                head += "; width by shear %dx%d (%.2f)" % (w, h, sh)
            img = deswz(data, bpe, w, h, dt)
            print(head + "\n    " + compare(img, pm))
        else:
            print(head)
