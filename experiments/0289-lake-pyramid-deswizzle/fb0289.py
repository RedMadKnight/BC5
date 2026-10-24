#!/usr/bin/env python3
# BC5 experiment 0289: the night lake writers' 32_FLOAT image pyramid against the depth image read next to it. Exp 0287
# (F350): in the frozen view the writers' GPU-written indirect arguments change in steps, with the depth memory and the
# pyramid, and both observed hole switches fell on such steps. If an occlusion pass culls against a pyramid built from
# the depth (the hypothesis, TODO(verify)), the pyramid should look like a reduction of a depth image, and of which
# one (this frame's, or an earlier frame's) tells whether the holes feed back.
# Inputs: a capture directory of capa0287.py-style bursts with pyramid reads (bNN.pK.bin: 0x11d0880000 + 0x20000) and
# depth reads (bNN.zK.bin: 0x1129ec0000 + 0x1860000), the read summary JSON (rd0287.py: each depth read's best size and
# whether it is clear), the depth image's pattern (swz0248-z4.json: ADDR_SW_64KB_Z_X, 16 pipes) and one or more
# patterns for the pyramid: gen0289.py's swz4k-addrlib.json (ADDR_SW_4KB_S at 4-byte elements from Mesa's addrlib,
# GFX10_SW_4K_S_PATINFO[2]) and, as a cross-check, cand0289.py's guesses. Each pattern is scored by how smooth its decoded mip 0 is (total variation: the mean
# absolute difference of neighbouring texels over the median absolute value, median over the reads; a wrong pattern
# scrambles every 32 x 32 block), and the comparison below is printed for every candidate, the smoothest first.
# Pyramid: five single-level 32_FLOAT images, 128x64 at 0x11d0886000 down to 8x4 at 0x11d0892000 (exp 0274; width and
# height from the image descriptors' words 1-2, as exp 0212's desc0212.py decodes them). A 4-KiB block of 4-byte
# elements is 32x32 elements (TODO(verify): Gfx10Lib::ComputeBlockDimension), blocks in rows of ceil(width / 32).
# Per pyramid read: each level's value statistics and how many texels are 0. Then mip 0 against the depth reads of the
# same burst at the same index and at the indexes before and after (lag in reads), for two footprints:
#   "stretch": the depth image's w x h stretched over the 128 x 64 texels;
#   "pow2":    32 x 32 depth pixels per texel from the top-left corner (a 4096 x 2048 pyramid whose level 5 is 128 x 64);
# and per texel the depth's minimum and maximum over its footprint (values 0..1 only) and the share of depth-0 pixels:
# Pearson r of mip 0 with each, over the texels inside the image. Prints summaries only (statistics and r values).
# Runs on the box in the ubuntu distrobox (numpy), on the title's data.
# usage: python3 -I fb0289.py <capture dir> <reads json> <swz0248-z4.json> <swz4k json> [more candidate jsons]
import collections, glob, json, os, re, statistics, sys
import numpy as np

cdir, rjson, zsw = sys.argv[1:4]
pz = json.load(open(zsw))["patterns"]["4"]
cands = [(os.path.basename(f).replace("swz4k-", "").replace(".json", ""), json.load(open(f))["pattern"]) for f in sys.argv[4:]]
PBASE = 0x11d0880000
MIPS = [(0x11d0886000, 128, 64), (0x11d088e000, 64, 32), (0x11d0890000, 32, 16), (0x11d0891000, 16, 8), (0x11d0892000, 8, 4)]
reads = {r["name"]: r for r in json.load(open(rjson))["reads"]}


def coord_offset(p, key, n, nbits):
    v = np.arange(n, dtype=np.int64)
    off = np.zeros(n, dtype=np.int64)
    for i, b in enumerate(p[:nbits]):
        m = b[key]
        if m:
            par = np.zeros(n, dtype=np.int64)
            for k in range(16):
                if m >> k & 1:
                    par ^= (v >> k) & 1
            off |= par << i
    return off


def deswizzle(raw, p, w, h, bw, bh, bbytes, nbits):
    fx, fy = coord_offset(p, "x", w, nbits), coord_offset(p, "y", h, nbits)
    pitch = -(-w // bw)
    blk = (np.arange(h) // bh)[:, None] * pitch + (np.arange(w) // bw)[None, :]
    idx = (blk * bbytes + (fx[None, :] ^ fy[:, None])) >> 2
    return raw[np.minimum(idx, raw.size - 1)]


def pyramid(path, pp):
    raw = np.frombuffer(open(path, "rb").read(), dtype="<f4").astype(np.float64)
    out = []
    for base, w, h in MIPS:
        sub = raw[(base - PBASE) // 4:]
        out.append(deswizzle(sub, pp, w, h, 32, 32, 4096, 12))
    return out


def tv(img):
    good = np.isfinite(img)
    v = np.where(good, img, np.nan)
    d = np.concatenate([np.abs(np.diff(v, axis=0)).ravel(), np.abs(np.diff(v, axis=1)).ravel()])
    d = d[np.isfinite(d)]
    scale = np.nanmedian(np.abs(v))
    return float(d.mean() / scale) if d.size and scale > 0 else float("nan")


def depth(path, w):
    h = w * 9 // 16
    raw = np.frombuffer(open(path, "rb").read(), dtype="<f4").astype(np.float64)
    return deswizzle(raw, pz, w, h, 128, 128, 65536, 16)


def cells(z, how):
    h, w = z.shape
    with np.errstate(invalid="ignore"):
        ok = np.isfinite(z) & (z >= 0) & (z <= 1)
    if how == "stretch":
        ys, xs = np.arange(h) * 64 // h, np.arange(w) * 128 // w
    else:
        ys, xs = np.arange(h) // 32, np.arange(w) // 32
    cy, cx = np.broadcast_to(ys[:, None], z.shape), np.broadcast_to(xs[None, :], z.shape)
    inside = (cy < 64) & (cx < 128)
    key = (cy * 128 + cx)[inside & ok]
    val = z[inside & ok]
    mn = np.full(128 * 64, np.nan)
    mx = np.full(128 * 64, np.nan)
    np.fmin.at(mn, key, val)
    np.fmax.at(mx, key, val)
    cnt = np.bincount(key, minlength=128 * 64).astype(float)
    zero = np.bincount(key, weights=(val == 0).astype(float), minlength=128 * 64)
    with np.errstate(invalid="ignore", divide="ignore"):
        hole = zero / cnt
    return mn.reshape(64, 128), mx.reshape(64, 128), hole.reshape(64, 128)


def r(a, b):
    m = np.isfinite(a) & np.isfinite(b)
    if m.sum() < 10 or a[m].std() == 0 or b[m].std() == 0:
        return float("nan")
    return float(np.corrcoef(a[m], b[m])[0, 1])


print("# %s; candidates: %s" % (cdir, " ".join(n for n, _ in cands)))
bursts = []
for tf in sorted(glob.glob(os.path.join(cdir, "b*.times.txt"))):
    b = os.path.basename(tf).split(".")[0]
    names = [l.split()[0] for l in open(tf) if l.strip()]
    pk = sorted(int(n[1:]) for n in names if re.fullmatch(r"p\d+", n))
    zk = sorted(int(n[1:]) for n in names if re.fullmatch(r"z\d+", n))
    bursts.append((b, pk, zk))
score = {}
for name, pp in cands:
    v = [tv(pyramid(os.path.join(cdir, "%s.p%d.bin" % (b, k)), pp)[0]) for b, pk, _ in bursts for k in pk]
    v = [x for x in v if x == x]
    score[name] = statistics.median(v) if v else float("nan")
print("# smoothness of mip 0 by candidate (median total variation over the pyramid reads; lower is smoother): %s" % (
    ", ".join("%s %.3f" % (n, score[n]) for n in sorted(score, key=lambda n: score[n]))))
zcache = {}
for name, pp in sorted(cands, key=lambda c: score[c[0]]):
    rows = collections.defaultdict(list)
    print("== candidate %s" % name)
    for b, pk, zk in bursts:
        for k in zk:
            rd = reads.get("%s.z%d" % (b, k))
            if (b, k) not in zcache and rd and rd["clear"] and os.path.exists(os.path.join(cdir, "%s.z%d.bin" % (b, k))):
                z = depth(os.path.join(cdir, "%s.z%d.bin" % (b, k)), rd["best"])
                zcache[(b, k)] = {how: cells(z, how) for how in ("stretch", "pow2")}
        for k in pk:
            mips = pyramid(os.path.join(cdir, "%s.p%d.bin" % (b, k)), pp)
            m0 = mips[0]
            if name == min(score, key=lambda n: score[n]):
                print("  %s p%d: mip0 min %.4g median %.4g max %.4g, %d of %d texels 0, tv %.3f; mip1..4 medians %s" % (
                    b, k, np.nanmin(m0), np.nanmedian(m0), np.nanmax(m0), int((m0 == 0).sum()), m0.size, tv(m0),
                    " ".join("%.4g" % np.nanmedian(x) for x in mips[1:])))
            for kz in zk:
                if (b, kz) not in zcache:
                    continue
                for how, (mn, mx, hole) in zcache[(b, kz)].items():
                    for nm, ref in (("min", mn), ("max", mx), ("hole", hole)):
                        rows[(how, nm, kz - k)].append(r(m0, ref))
    print("  mip 0 against the depth reads of its burst: median Pearson r over read pairs, by footprint, per-texel value"
          " and lag in reads (depth read index minus pyramid read index; negative = an earlier depth read)")
    for how in ("stretch", "pow2"):
        for nm in ("min", "max", "hole"):
            cellsr = []
            for lag in range(-7, 8):
                v = [x for x in rows.get((how, nm, lag), []) if x == x]
                if v:
                    cellsr.append("%+d: %+.3f (%d)" % (lag, statistics.median(v), len(v)))
            print("  %-7s %-4s %s" % (how, nm, " | ".join(cellsr)))
