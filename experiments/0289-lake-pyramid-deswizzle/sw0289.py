#!/usr/bin/env python3
# BC5 experiment 0289: at the night lake's hole switches, the writers' pyramid before and after. fb0289.py: mip 0
# (addrlib's ADDR_SW_4KB_S pattern) is a far-is-high depth pyramid in which the holes show as far. If it feeds the next
# frame's culling (TODO(verify) hypothesis, F350), the pyramid read before a switch should match the holes after it
# better than a pyramid built from the same frame would. A switch: two depth reads of one burst with a clear, equal size
# (rd0289.py's JSON) whose depth-0 sets in the lake window (x 300..1900, y 400..680 of 1920x1080, nearest pixel) have
# phi < 0.8, one or two reads apart. For each, with Pk / Pj the pyramid reads taken just before the depth reads zk / zj
# and Hk / Hj their hole shares per pyramid texel (the depth image stretched over 128 x 64), over the texels that cover
# the lake window: r(Pk, Hk), r(Pk, Hj), r(Pj, Hk), r(Pj, Hj), and r(Pj - Pk, Hj - Hk). "Same frame" predicts r(Pj, Hj) >
# r(Pj, Hk) and the pyramid change following the hole change; "feedback" predicts r(Pk, Hj) above r(Pk, Hk). Same
# decoding as fb0289.py. Summaries only. Runs on the box in the ubuntu distrobox (numpy), on the title's data.
# usage: python3 -I sw0289.py <capture dir> <reads json> <swz0248-z4.json> <swz4k-addrlib.json>
import glob, json, os, re, statistics, sys
import numpy as np

cdir, rjson, zsw, psw = sys.argv[1:5]
pz = json.load(open(zsw))["patterns"]["4"]
pp = json.load(open(psw))["pattern"]
PBASE, MIP0 = 0x11d0880000, (0x11d0886000, 128, 64)
reads = {r["name"]: r for r in json.load(open(rjson))["reads"]}
TX0, TX1, TY0, TY1 = 300 * 128 // 1920, 1900 * 128 // 1920, 400 * 64 // 1080, 680 * 64 // 1080  # texels over the window


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
    return deswizzle(raw[(base - PBASE) // 4:], pp, w, h, 32, 32, 4096, 12)[TY0:TY1, TX0:TX1]


def depth(path, w):
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
        hole = (zero / cnt).reshape(64, 128)[TY0:TY1, TX0:TX1]
    wy, wx = np.arange(400, 680) * h // 1080, np.arange(300, 1900) * w // 1920
    zw, okw = z[wy][:, wx], ok[wy][:, wx]
    return hole, (zw == 0) & okw, okw


def corr(a, b, m=None):
    m = np.isfinite(a) & np.isfinite(b) if m is None else m
    if m.sum() < 10 or a[m].std() == 0 or b[m].std() == 0:
        return float("nan")
    return float(np.corrcoef(a[m], b[m])[0, 1])


events = []
for tf in sorted(glob.glob(os.path.join(cdir, "b*.times.txt"))):
    b = os.path.basename(tf).split(".")[0]
    names = {l.split()[0] for l in open(tf) if l.strip()}
    zs = sorted(int(n[1:]) for n in names if re.fullmatch(r"z\d+", n))
    cache = {}
    for k in zs:
        r = reads.get("%s.z%d" % (b, k))
        if r and r["clear"] and "p%d" % k in names:
            cache[k] = (r["best"], depth(os.path.join(cdir, "%s.z%d.bin" % (b, k)), r["best"]), mip0(os.path.join(cdir, "%s.p%d.bin" % (b, k))))
    for k in sorted(cache):
        for j in (k + 1, k + 2):
            if j not in cache or cache[j][0] != cache[k][0]:
                continue
            (hk, dk, okk), pk = cache[k][1], cache[k][2]
            (hj, dj, okj), pj = cache[j][1], cache[j][2]
            m = okk & okj
            phi = corr(dk.astype(float), dj.astype(float), m)
            if not phi < 0.8:
                continue
            ev = (corr(pk, hk), corr(pk, hj), corr(pj, hk), corr(pj, hj), corr(pj - pk, hj - hk))
            events.append(ev)
            print("  %s z%d->z%d (size %d): holes phi %+.3f | r(Pk,Hk) %+.3f r(Pk,Hj) %+.3f r(Pj,Hk) %+.3f r(Pj,Hj) %+.3f |"
                  " r(dP,dH) %+.3f" % (b, k, j, cache[k][0], phi, *ev))
            break
print("# %s: %d hole switches (texels over the lake window: x %d..%d, y %d..%d of 128 x 64)" % (cdir, len(events), TX0, TX1, TY0, TY1))
if events:
    med = [statistics.median(e[i] for e in events if e[i] == e[i]) if any(e[i] == e[i] for e in events) else float("nan") for i in range(5)]
    print("  medians: r(Pk,Hk) %+.3f r(Pk,Hj) %+.3f r(Pj,Hk) %+.3f r(Pj,Hj) %+.3f r(dP,dH) %+.3f" % tuple(med))
