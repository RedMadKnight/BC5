#!/usr/bin/env python3
# BC5 experiment 0251: the night lake's depth memory (0x1129ec0000 .. 0x112c800000, capl0251.sh) read by address.
# F309: the depth base is the same at every render size, and each size's HTILE lies right after its depth data, its
# stencil right after the HTILE. Byte offsets from the base (64-KiB blocks; HTILE ends from the journalled stencil
# bases (0x112b420000 for 3072, exp 0245) and the fill dispatches' sizes (HTILE + stencil, run W251a); the stencil ends
# are computed as 8-bit 64KB_Z_X blocks of 256x256, TODO(verify) for 3840):
#   size        depth data      HTILE                    stencil
#   2048x1152   0 .. 0x900000   0x900000 .. 0x930000     0x930000 .. 0xbb0000
#   3072x1728   0 .. 0x1500000  0x1500000 .. 0x1560000   0x1560000 .. 0x1aa0000
#   3328x1872   0 .. 0x1860000  0x1860000 .. 0x18e0000   0x18e0000 .. 0x1f60000
#   3840x2160   0 .. 0x1fe0000  0x1fe0000 .. 0x2080000   0x2080000 .. 0x28f0000
# Per read it prints:
#  - which size's depth data reads as a coherent picture (block-row shear of the ADDR_SW_64KB_Z_X de-swizzle at each
#    size, exps 0237/0248; least = the size drawn last);
#  - for each HTILE range, its words: zero, depth-like (a finite float in (0, 1]), outside 0..1 or not finite, and the
#    three most common values. The top session's aliasing hypothesis: a 3328 HTILE that is not re-initialised holds the
#    3840x2160 pass's depth (depth-like words); a cleared one holds HTILE words;
#  - where the words outside 0..1 lie: per range above, and the 64-KiB blocks with most of them.
# The next frozen-view shot's patch level (bench.txt, exp 0197's metric) labels each read.
# Runs on the box in the ubuntu distrobox (numpy), on the title's data; prints summaries only.
# usage: python3 -I ana0251.py <capture dir> <bench.txt> <swz0248-z4.json>
import collections, json, os, re, sys
import numpy as np

cdir, bench, zsw = sys.argv[1:4]
pz = json.load(open(zsw))["patterns"]["4"]
share = {}
for l in open(bench):
    m = re.match(r"\s*(\d{6})-(ts\d\d)\.png: patch\s+([\d.]+) %", l)
    if m:
        share[m[1]] = (m[2], float(m[3]))
SIZES = [(2048, 1152), (3072, 1728), (3328, 1872), (3840, 2160)]
DATA = {w: (-(-w // 128)) * (-(-h // 128)) * 65536 for w, h in SIZES}
HTILE = {2048: (0x900000, 0x930000), 3072: (0x1500000, 0x1560000), 3328: (0x1860000, 0x18e0000), 3840: (0x1fe0000, 0x2080000)}
STENCIL = {2048: (0x930000, 0xbb0000), 3072: (0x1560000, 0x1aa0000), 3328: (0x18e0000, 0x1f60000), 3840: (0x2080000, 0x28f0000)}
assert all(DATA[w] == HTILE[w][0] for w in DATA), DATA


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


def image(raw, w, h):
    fx, fy = coord_offset(pz, "x", w), coord_offset(pz, "y", h)
    pitch = -(-w // 128)
    blk = (np.arange(h) // 128)[:, None] * pitch + (np.arange(w) // 128)[None, :]
    idx = (blk * 65536 + (fx[None, :] ^ fy[:, None])) >> 2
    return raw[np.minimum(idx, raw.size - 1)]


def shear(img):
    good = np.isfinite(img) & (np.abs(img) <= 1)
    l = np.where(good, img, 0.0)
    d = np.abs(np.diff(l, axis=0))
    at = np.arange(d.shape[0]) % 128 == 127
    return float(d[at].mean() / max(d[~at].mean(), 1e-12))


def classes(u, f):
    # depth-like: a float in [1e-6, 1] (the lake's reverse-Z depths are 1e-4..2e-2); small: a non-zero word below 1e-6
    # as a float (denormals: HTILE words such as 0x0024009f read that way).
    with np.errstate(invalid="ignore"):
        zero = u == 0
        depth = np.isfinite(f) & (f >= 1e-6) & (f <= 1)
        junk = ~np.isfinite(f) | (np.abs(f) > 1)
        small = ~zero & ~depth & ~junk
    return zero, depth, junk, small


caps = {}
for l in open(os.path.join(cdir, "caps.txt")):
    m = re.match(r"(cap\d+) at (\d\d):(\d\d):(\d\d)", l)
    if m:
        caps[m[1]] = "%s%s%s" % m.groups()[1:]
print("# %s: depth memory 0x1129ec0000 + 0x2940000, %d reads" % (cdir, len(caps)))
for cap, hms in sorted(caps.items()):
    fn = os.path.join(cdir, cap + ".1129ec0000.bin")
    if not os.path.exists(fn):
        print("== %s: file missing" % cap)
        continue
    b = open(fn, "rb").read()
    u = np.frombuffer(b, dtype="<u4")
    f = u.view("<f4").astype(np.float64)
    nxt = min((k for k in share if k >= hms), default=None)
    prv = max((k for k in share if k <= hms), default=None)
    lab = lambda k: "%s %.1f %%" % share[k] if k else "-"
    sh = {w: shear(image(f, w, h)) for w, h in SIZES}
    print("== %s at %s:%s:%s; shots before %s, after %s; %d bytes; depth shear %s" % (
        cap, hms[:2], hms[2:4], hms[4:], lab(prv), lab(nxt), len(b), ", ".join("%d %.2f" % (w, s) for w, s in sh.items())))
    zero, depth, junk, small = classes(u, f)
    for w, _ in SIZES:
        a, e = HTILE[w][0] // 4, HTILE[w][1] // 4
        top = collections.Counter(u[a:e].tolist()).most_common(3)
        print("   HTILE %4d (+%07x..%07x): zero %.3f, depth-like %.3f, small (HTILE-like) %.3f, outside 0..1 %.3f; most common %s" % (
            w, HTILE[w][0], HTILE[w][1], zero[a:e].mean(), depth[a:e].mean(), small[a:e].mean(), junk[a:e].mean(),
            ", ".join("%08x x%d" % t for t in top)))
    nj = int(junk.sum())
    regs = [("3328 depth data outside the ranges below", 0, DATA[3328])]
    for w in (2048, 3072):
        regs += [("%d HTILE" % w, *HTILE[w]), ("%d stencil" % w, *STENCIL[w])]
    regs += [("3328 HTILE", *HTILE[3328]), ("3328 stencil", *STENCIL[3328]), ("3840 HTILE", *HTILE[3840]),
             ("3840 stencil", *STENCIL[3840]), ("rest of the pool", STENCIL[3840][1], len(b))]
    inside = np.zeros(u.size, bool)
    out = []
    for name, a, e in regs[1:]:
        s = junk[a // 4:e // 4].sum()
        inside[a // 4:e // 4] = True
        out.append("%s %d (%.3f of its words)" % (name, s, junk[a // 4:e // 4].mean()))
    rest = junk[:DATA[3328] // 4] & ~inside[:DATA[3328] // 4]
    print("   words outside 0..1: %d (%.4f of the pool); in the 3328 depth data outside the smaller sizes' HTILE/stencil %d; %s" % (
        nj, nj / u.size, int(rest.sum()), "; ".join(out)))
    per_blk = junk[:(u.size // 16384) * 16384].reshape(-1, 16384).sum(axis=1)
    hot = np.argsort(per_blk)[::-1][:6]
    print("   blocks with most of them (64-KiB block: offset, words): %s" % ", ".join(
        "+%07x %d" % (k * 65536, per_blk[k]) for k in hot if per_blk[k] > 0))
