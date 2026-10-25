#!/usr/bin/env python3
# BC5 experiment 0289: does the writers' pyramid show the holes of the depth read next to it, or those of the other hole
# state? fb0289.py found mip 0 (decoded with addrlib's ADDR_SW_4KB_S pattern) correlated with the depth's per-texel
# hole share (r +0.61, the depth image stretched over 128 x 64) and against its depth (reverse-Z: the pyramid grows with
# distance), the same at every lag, since the depth reads of a burst seldom change. If the pyramid feeds the next
# frame's culling (TODO(verify) hypothesis, F350), a pyramid built while the holes were X would precede a Y frame: the
# pyramid next to a Y read would then show X's holes. Here each clear depth read (rd0289.py's JSON) is labelled X or Y
# by its family (rd0289.py's family lists of clear reads: X the family with the most of the shots' cell mask, Y the
# next; their sets overlap in W289a, so an 80 %-in-the-set rule called every Y read X too), every
# labelled read's hole share per pyramid texel is averaged per family (the depth image stretched over 128 x 64), and
# each pyramid read pK whose depth read zK is labelled is set against both family maps: Pearson r of mip 0 with the X
# map and with the Y map, tabulated by zK's label. Same decoding as fb0289.py. Summaries only. Runs on the box in the
# ubuntu distrobox (numpy), on the title's data.
# usage: python3 -I fam0289.py <capture dir> <reads json> <swz0248-z4.json> <swz4k-addrlib.json>
import collections, glob, json, os, re, statistics, sys
import numpy as np

cdir, rjson, zsw, psw = sys.argv[1:5]
pz = json.load(open(zsw))["patterns"]["4"]
pp = json.load(open(psw))["pattern"]
PBASE, MIP0 = 0x11d0880000, (0x11d0886000, 128, 64)
data = json.load(open(rjson))
reads = {r["name"]: r for r in data["reads"]}
fam = {}
for f in data["families"][:2]:
    for n in f["reads"]:
        fam[n] = f["name"]


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


def mip0(path):
    raw = np.frombuffer(open(path, "rb").read(), dtype="<f4").astype(np.float64)
    base, w, h = MIP0
    return deswizzle(raw[(base - PBASE) // 4:], pp, w, h, 32, 32, 4096, 12)


def holemap(path, w):
    h = w * 9 // 16
    raw = np.frombuffer(open(path, "rb").read(), dtype="<f4").astype(np.float64)
    z = deswizzle(raw, pz, w, h, 128, 128, 65536, 16)
    with np.errstate(invalid="ignore"):
        ok = np.isfinite(z) & (z >= 0) & (z <= 1)
    ys, xs = np.arange(h) * 64 // h, np.arange(w) * 128 // w
    key = (ys[:, None] * 128 + xs[None, :])[ok]
    cnt = np.bincount(key, minlength=8192).astype(float)
    zero = np.bincount(key, weights=(z[ok] == 0).astype(float), minlength=8192)
    with np.errstate(invalid="ignore", divide="ignore"):
        return (zero / cnt).reshape(64, 128)


def label(r):
    return fam.get(r["name"]) if r else None


def corr(a, b):
    m = np.isfinite(a) & np.isfinite(b)
    if m.sum() < 10 or a[m].std() == 0 or b[m].std() == 0:
        return float("nan")
    return float(np.corrcoef(a[m], b[m])[0, 1])


maps, pairs = collections.defaultdict(list), []
for tf in sorted(glob.glob(os.path.join(cdir, "b*.times.txt"))):
    b = os.path.basename(tf).split(".")[0]
    names = [l.split()[0] for l in open(tf) if l.strip()]
    for n in names:
        if not re.fullmatch(r"z\d+", n):
            continue
        r = reads.get("%s.%s" % (b, n))
        lab = label(r)
        if lab is None:
            continue
        hm = holemap(os.path.join(cdir, "%s.%s.bin" % (b, n)), r["best"])
        maps[lab].append(hm)
        k = n[1:]
        if "p" + k in names:
            pairs.append((b, k, lab, hm))
print("# %s: labelled depth reads X %d, Y %d; pyramid reads next to a labelled depth read %d" % (
    cdir, len(maps["X"]), len(maps["Y"]), len(pairs)))
if maps["X"] and maps["Y"]:
    mx, my = np.nanmean(maps["X"], axis=0), np.nanmean(maps["Y"], axis=0)
    print("  the two family maps against each other: r %+.3f" % corr(mx, my))
    tab = collections.defaultdict(list)
    for b, k, lab, hm in pairs:
        m0 = mip0(os.path.join(cdir, "%s.p%s.bin" % (b, k)))
        rx, ry, ro = corr(m0, mx), corr(m0, my), corr(m0, hm)
        tab[lab].append((rx, ry, ro))
        print("  %s p%s next to a %s read: r with the X map %+.3f, with the Y map %+.3f, with its own read %+.3f" % (b, k, lab, rx, ry, ro))
    for lab in ("X", "Y"):
        if tab[lab]:
            print("# next to %s reads (%d): median r with the X map %+.3f, with the Y map %+.3f, with the read itself %+.3f" % (
                lab, len(tab[lab]), statistics.median(t[0] for t in tab[lab]), statistics.median(t[1] for t in tab[lab]),
                statistics.median(t[2] for t in tab[lab])))
