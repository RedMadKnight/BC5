#!/usr/bin/env python3
# BC5 experiment 0274: the 32_FLOAT image pyramid the night lake's depth writers read in their vertex stage (exp 0253's
# raw/W251a.wr.txt: GS user data 16/24 tables, mips 128x64, 64x32, 32x16, 16x8, 8x4 at 0x11d0886000, 0x11d088e000,
# 0x11d0890000, 0x11d0891000, 0x11d0892000), read with the depth memory and the G-buffer (capl0274.sh), clean against
# patched reads of one run. Mip 0 fills exactly the 32 KiB up to mip 1's base, so it is taken as linear, row-major,
# 128 texels wide (TODO(verify): the T#'s SW_MODE is not decoded here). Per read:
#  - the frame size and completeness by block-row shear of the G-buffer and depth images (ana0274.py's method) and the
#    hole mask: lake-window pixels whose depth is 0 and G-buffer cleared (exp 0271, F333);
#  - per mip: finite share, zero share, min / median / max;
#  - the hole mask taken to the pyramid's grid as the hole fraction per texel, assuming one texel per 32x32 render
#    pixels (TODO(verify): the pyramid's scale), and its correlation with mip 0 and with mip 0 minus the median of the
#    clean complete reads' mip 0 (texel by texel).
# A strong correlation would tie the pyramid's values to where nothing drew; near zero means no tie, or a wrong layout or
# scale. Prints summaries only. Runs on the box in the ubuntu distrobox (numpy).
# usage: python3 -I pyr0274.py <capture dir> <bench.txt> <swz0248-z4.json> <swz0244-4.json>
import json, os, re, statistics, sys
import numpy as np

cdir, bench, zsw, rsw = sys.argv[1:5]
pz, pr = json.load(open(zsw))["patterns"]["4"], json.load(open(rsw))["patterns"]["4"]
REGION = 0x11d0880000
MIPS = [(0x11d0886000, 128, 64), (0x11d088e000, 64, 32), (0x11d0890000, 32, 16), (0x11d0891000, 16, 8), (0x11d0892000, 8, 4)]
SIZES = [(w, w * 9 // 16) for w in (2048, 2304, 2560, 2816, 3072, 3328)]
shots = []
for l in open(bench):
    m = re.match(r"\s*(\d{6})-(ts\d\d)\.png: patch\s+([\d.]+) %", l)
    if m:
        shots.append((m[1], float(m[3])))


def state_of(hms):
    prev = [s for s in shots if s[0] <= hms]
    nxt = [s for s in shots if s[0] >= hms]
    p, n = (prev[-1] if prev else None), (nxt[0] if nxt else None)
    if p and n and p[1] < 5 and n[1] < 5:
        return "clean"
    if p and n and p[1] >= 8 and n[1] >= 8:
        return "patched"
    return "mixed"


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


def shear(img):
    good = np.isfinite(img) & (np.abs(img) < 1e30)
    l = np.log1p(np.abs(np.where(good, img, 0.0)))
    d = np.abs(np.diff(l, axis=0))
    at = np.arange(d.shape[0]) % 128 == 127
    return float(d[at].mean() / max(d[~at].mean(), 1e-12))


def corr(a, b):
    ok = np.isfinite(a) & np.isfinite(b)
    if ok.sum() < 10 or a[ok].std() == 0 or b[ok].std() == 0:
        return float("nan")
    return float(np.corrcoef(a[ok], b[ok])[0, 1])


caps = {}
for l in open(os.path.join(cdir, "caps.txt")):
    m = re.match(r"(cap\d+) at (\d\d):(\d\d):(\d\d)", l)
    if m:
        caps[m[1]] = "%s%s%s" % m.groups()[1:]
reads = []
for cap, hms in sorted(caps.items()):
    files = [os.path.join(cdir, "%s.%x.bin" % (cap, a)) for a in (0x1129ec0000, 0x113f230000, REGION)]
    if not all(os.path.exists(f) for f in files):
        continue
    zr, gr = (np.frombuffer(open(f, "rb").read(), dtype="<f4").astype(np.float64) for f in files[:2])
    pyr = np.frombuffer(open(files[2], "rb").read(), dtype="<f4").astype(np.float64)
    gsh, w, h = sorted((shear(image(gr, pr, w, h)), w, h) for w, h in SIZES)[0]
    z, g = image(zr, pz, w, h), image(gr, pr, w, h)
    complete = gsh <= 2 and shear(z) <= 3
    with np.errstate(invalid="ignore"):
        hole = (z == 0) & (np.nan_to_num(g) >= 9000)
    # the lake window (x 300..1900, y 400..680 of 1920x1080) at this render size
    x0, x1, y0, y1 = 300 * w // 1920, 1900 * w // 1920, 400 * h // 1080, 680 * h // 1080
    win = np.zeros((h, w), bool)
    win[y0:y1, x0:x1] = True
    hole &= win
    th, tw = -(-h // 32), -(-w // 32)
    frac = np.full((64, 128), np.nan)
    hp = np.zeros((th * 32, tw * 32), bool)
    hp[:h, :w] = hole
    wp = np.zeros((th * 32, tw * 32), bool)
    wp[:h, :w] = win
    fr = hp.reshape(th, 32, tw, 32).mean(axis=(1, 3))
    wf = wp.reshape(th, 32, tw, 32).mean(axis=(1, 3))
    frac[:min(th, 64), :min(tw, 128)] = np.where(wf > 0.5, fr, np.nan)[:64, :128]
    mips = [pyr[(b - REGION) // 4:(b - REGION) // 4 + mw * mh].reshape(mh, mw) for b, mw, mh in MIPS]
    reads.append({"cap": cap, "hms": hms, "state": state_of(hms), "w": w, "complete": complete, "mips": mips, "frac": frac,
                  "hole": float(hole[win].mean())})
clean0 = [r["mips"][0] for r in reads if r["complete"] and r["state"] == "clean"]
ref = np.median(np.stack(clean0), axis=0) if clean0 else None
print("# %s: %d reads with all three regions; %d complete clean reads give the reference mip 0" % (cdir, len(reads), len(clean0)))
for r in reads:
    parts = []
    for k, m in enumerate(r["mips"]):
        f = np.isfinite(m)
        v = m[f]
        parts.append("mip%d fin %.2f zero %.2f %s" % (k, f.mean(), float((v == 0).mean()) if v.size else float("nan"),
                                                      "%.4g/%.4g/%.4g" % (v.min(), np.median(v), v.max()) if v.size else "-"))
    c1 = corr(r["frac"].ravel(), r["mips"][0].ravel())
    c2 = corr(r["frac"].ravel(), (r["mips"][0] - ref).ravel()) if ref is not None else float("nan")
    diff = float(np.nanmean(np.abs(r["mips"][0] - ref))) if ref is not None else float("nan")
    print("== %s %s %-7s %d%s hole %.3f | %s | corr(hole, mip0) %+.3f, corr(hole, mip0 - clean) %+.3f, mean |mip0 - clean| %.4g" % (
        r["cap"], r["hms"], r["state"], r["w"], "" if r["complete"] else " INCOMPLETE", r["hole"], "; ".join(parts), c1, c2, diff))
by = {}
for r in reads:
    if r["complete"]:
        by.setdefault(r["state"], []).append(r)
print("# complete reads by state: median of mean |mip0 - clean reference| and of the two correlations")
for st, rs in sorted(by.items()):
    d = [float(np.nanmean(np.abs(x["mips"][0] - ref))) for x in rs] if ref is not None else []
    c = [corr(x["frac"].ravel(), (x["mips"][0] - ref).ravel()) for x in rs] if ref is not None else []
    print("  %-7s %2d reads | |mip0 - clean| %s | corr(hole, mip0 - clean) %s" % (
        st, len(rs), "%.4g" % statistics.median(d) if d else "-", "%+.3f" % statistics.median([x for x in c if x == x]) if any(x == x for x in c) else "-"))
