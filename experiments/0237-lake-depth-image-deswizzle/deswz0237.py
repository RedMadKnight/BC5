#!/usr/bin/env python3
# BC5 experiment 0237: de-swizzle the night lake water's vertex-stage slot-4 image (exp 0235's kept dump, 16_FLOAT,
# ADDR_SW_64KB_R_X) and compare it with the patchwork of the screenshot taken right after the dump.
# Addressing (Mesa addrlib @ ab2374a, gfx10addrlib.cpp:4751-4845, ComputeSurfaceAddrFromCoordMacroTiled): address =
# block index * 64 KiB + (in-block offset from the swizzle pattern ^ pipe/bank xor); block index = (y / 128) * pitch in
# blocks + x / 256 for 2-byte elements (block 256 x 128 elements, res0205.py's layout); pitch = width aligned to 256.
# The pattern (swz0237.json, from gen0237.py) gives each address bit as an XOR of x/y/z coordinate bits, so the in-block
# offset is fx(x) ^ fy(y) (z = 0 for one slice). The pipe/bank xor is 0: the image base 0x113cb40000 is 64-KiB aligned
# and gfx10 T#s carry the tile swizzle in the base address bits.
# The pipe count of the chip (GB_ADDR_CONFIG) is not known here, nor which render size the frame had (the journal said
# 2816x1584 for I3 ts00), so every pipe count 0-6 (log2) is tried with each size; a wrong one scrambles 256-byte
# pieces, so the smoothest image (least mean |step| of log depth between neighbours) is the right one.
# Then, against the screenshot: exp 0197's patch mask (luma > 47 and blue - red > 38 in x 300..1900, y 400..680) and the
# de-swizzled image resampled to 1920x1080 (nearest), in both vertical orientations (the water's viewport has a negative
# height): (1) the high-pass of log depth (minus its 31-px box mean) in patch and in other pixels, and their correlation
# with the mask; (2) the mean log-depth step across the mask's edges against the window's mean step.
# Writes greyscale PNGs of the best candidate (log depth) and of a mask overlay to <out dir>, which stays on the box.
# Runs in the box's ubuntu distrobox (numpy, PIL), on the title's data; prints summaries only.
# usage: python3 -I deswz0237.py <gs4.bin> <swz0237.json> <screenshot.png> <out dir>
import json, math, os, sys
import numpy as np
from PIL import Image

gs4, swz, shot, out = sys.argv[1:5]
raw = np.frombuffer(open(gs4, "rb").read(), dtype="<f2").astype(np.float32)
pat = json.load(open(swz))["patterns"]
SIZES = [(2816, 1584), (3072, 1728), (3328, 1872), (2560, 1440)]


def coord_offset(bits, key, n):
    v = np.arange(n, dtype=np.int64)
    off = np.zeros(n, dtype=np.int64)
    for i, b in enumerate(bits):
        m = b[key]
        if m:
            par = np.zeros(n, dtype=np.int64)
            for k in range(16):
                if m >> k & 1:
                    par ^= (v >> k) & 1
            off |= par << i
    return off


def image(p, w, h):
    bits = pat[str(p)]
    fx, fy = coord_offset(bits, "x", w), coord_offset(bits, "y", h)
    pitch = -(-w // 256)
    x, y = np.arange(w), np.arange(h)
    blk = (y // 128)[:, None] * pitch + (x // 256)[None, :]
    idx = (blk * 65536 + (fx[None, :] ^ fy[:, None])) >> 1
    ok = idx < raw.size
    img = np.where(ok, raw[np.minimum(idx, raw.size - 1)], np.nan)
    return img


def rough(img):
    l = np.log1p(np.clip(img, 0, None))
    return float(np.nanmean(np.abs(np.diff(l, axis=1))) + np.nanmean(np.abs(np.diff(l, axis=0))))


def shear(img):
    # a wrong pitch shifts every 128-row block row against the one above: the mean |step| of log depth across those
    # boundaries over the mean |step| between other rows is ~1 at the right width and well above it at a wrong one
    l = np.log1p(np.clip(np.nan_to_num(img, nan=0.0), 0, None))
    d = np.abs(np.diff(l, axis=0))
    at = np.arange(d.shape[0]) % 128 == 127
    return float(d[at].mean() / max(d[~at].mean(), 1e-9))


print("# %s: width by block-row shear at pipes 2^4 (16:9 sizes): %s" % (gs4, ", ".join(
    "%d %.2f" % (w, shear(image(4, w, w * 9 // 16))) for w in range(2304, 3841, 256) if (w // 256) * 256 * w * 9 // 16 * 2 <= raw.size * 2 * 1.2)))
print("# %s: %d values; candidates (pipes log2, size): roughness = mean |step| of log(1+depth), x plus y" % (gs4, raw.size))
res = []
for (w, h) in SIZES:
    for p in range(7):
        r = rough(image(p, w, h))
        res.append((r, p, w, h))
        print("  pipes 2^%d %dx%d: %.4f" % (p, w, h, r))
res.sort()
r, p, w, h = res[0]
print("best: pipes 2^%d at %dx%d (roughness %.4f; next %.4f at pipes 2^%d %dx%d)" % (p, w, h, r, res[1][0], res[1][1], res[1][2], res[1][3]))
if len(sys.argv) > 5:  # p:w:h chosen by eye (render0237.py): the size whose render has no block-row shear
    p, w, h = map(int, sys.argv[5].split(":"))
    print("compared at: pipes 2^%d %dx%d (given)" % (p, w, h))
img = image(p, w, h)
ld = np.log1p(np.clip(np.nan_to_num(img, nan=0.0), 0, None))
os.makedirs(out, exist_ok=True)
g = (255 * (1 - ld / max(ld.max(), 1e-6))).astype(np.uint8)
Image.fromarray(g).save(os.path.join(out, "depth-best.png"))
print("depth range %.4g..%.4g, zero share %.3f; rows with depth >= 9000 (far) top/bottom quarter: %.2f / %.2f" % (
    np.nanmin(img), np.nanmax(img), float(np.mean(img == 0)),
    float(np.mean(img[: h // 4] >= 9000)), float(np.mean(img[-h // 4:] >= 9000))))

# against the screenshot
a = np.asarray(Image.open(shot).convert("RGB")).astype(np.float64)
X0, X1, Y0, Y1 = 300, 1900, 400, 680
luma = a.mean(axis=2)
blue = a[:, :, 2] - a[:, :, 0]
mask = (luma > 47) & (blue > 38)
win = np.zeros(mask.shape, bool)
win[Y0:Y1, X0:X1] = True
pm = mask & win
print("screenshot %s: patch share in the window %.3f" % (os.path.basename(shot), pm[win].mean()))
xs = (np.arange(1920) * w // 1920)
ys = (np.arange(1080) * h // 1080)


def boxmean(m, k):
    c = np.cumsum(np.cumsum(np.pad(m, ((1, 0), (1, 0))), axis=0), axis=1)
    H, W = m.shape
    r = k // 2
    y0, y1 = np.clip(np.arange(H) - r, 0, H), np.clip(np.arange(H) + r + 1, 0, H)
    x0, x1 = np.clip(np.arange(W) - r, 0, W), np.clip(np.arange(W) + r + 1, 0, W)
    s = c[y1][:, x1] - c[y0][:, x1] - c[y1][:, x0] + c[y0][:, x0]
    return s / ((y1 - y0)[:, None] * (x1 - x0)[None, :])


for flip in (False, True):
    d = ld[::-1] if flip else ld
    r = d[ys][:, xs]
    hp = r - boxmean(r, 31)
    inw = win
    mp, mo = hp[pm].mean(), hp[inw & ~mask].mean()
    corr = float(np.corrcoef(hp[inw], pm[inw].astype(float))[0, 1])
    step = np.abs(np.diff(r, axis=1))
    edge = (pm[:, 1:] != pm[:, :-1]) & inw[:, 1:]
    print("  %s: high-pass of log depth: patch %+.4f, other %+.4f, correlation with the mask %+.3f; "
          "x-step at mask edges %.4f vs window %.4f (%d edge pixels)" % (
              "flipped" if flip else "as stored", mp, mo, corr, step[edge].mean(), step[inw[:, 1:]].mean(), int(edge.sum())))
    # the image's own cells hold the far value: do the screenshot's patch pixels coincide with them?
    raw2 = (img[::-1] if flip else img)[ys][:, xs]
    far = np.nan_to_num(raw2, nan=0.0) >= 9000
    fa, pa = far[inw], pm[inw]
    phi = float(np.corrcoef(fa.astype(float), pa.astype(float))[0, 1])
    print("  %s: far value (>= 9000) in patch pixels %.3f, in other window pixels %.3f; phi(far, patch) %+.3f; "
          "patch pixels that are far %.3f of all far %.3f" % (
              "flipped" if flip else "as stored", fa[pa].mean(), fa[~pa].mean(), phi, (fa & pa).sum() / max(1, pa.sum()),
              (fa & pa).sum() / max(1, fa.sum())))
    if not flip:
        ov = (255 * (1 - r / max(r.max(), 1e-6))).astype(np.uint8)
        e2 = np.zeros_like(pm)
        e2[:, 1:] |= pm[:, 1:] != pm[:, :-1]
        e2[1:, :] |= pm[1:, :] != pm[:-1, :]
        ov = np.stack([np.where(e2 & win, 255, ov), ov, ov], axis=2).astype(np.uint8)
        Image.fromarray(ov).save(os.path.join(out, "depth-vs-mask.png"))
