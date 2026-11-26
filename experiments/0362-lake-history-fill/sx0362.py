#!/usr/bin/env python3
# BC5 experiment 0362, written after seeing run H1: the block-row shear of fz0362.py's "flat" and "no-structure"
# snapshots at the two widths sn0362.py did not try, 3328 (h 1872) and 3840 (h 2160), next to 2560, to see whether the
# depth memory holds another pass's image at another size at those times (F309: a 3840 x 2160 depth pass shares the
# base). Up to N snapshots per class. Prints summaries only.
# usage: python3 -I sx0362.py <snap dir> <reads json> <swz0248-z4.json> [N]   (on the box, in the distrobox)
import json, os, sys
import numpy as np

sdir, rjson, zsw = sys.argv[1:4]
N = int(sys.argv[4]) if len(sys.argv) > 4 else 12
pz = json.load(open(zsw))["patterns"]["4"]
S_OFF, S_LEN = 0x300000, 0x700000


def coord_offset(p, key, n):  # rd0312.py's
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


ROWS = {}


def shear(raw, w, h):  # sn0362.py's, over the block rows whole inside the snapshot
    if w not in ROWS:
        pitch = -(-w // 128)
        row = pitch * 65536
        lo, hi = -(-S_OFF // row), min((S_OFF + S_LEN) // row - 1, (h - 1) // 128)
        ys, xs = np.arange(lo * 128, (hi + 1) * 128), np.arange(0, w, 4)
        fx, fy = coord_offset(pz, "x", w), coord_offset(pz, "y", h)
        blk = (ys // 128)[:, None] * pitch + (xs // 128)[None, :]
        ROWS[w] = (ys, ((blk * 65536 + (fx[xs][None, :] ^ fy[ys][:, None])) >> 2) - S_OFF // 4)
    ys, li = ROWS[w]
    img = raw[np.clip(li, 0, raw.size - 1)]
    good = np.isfinite(img) & (np.abs(img) < 1e30)
    l = np.log1p(np.abs(np.where(good, img, 0.0)))
    d = np.abs(np.diff(l, axis=0))
    at = ys[:-1] % 128 == 127
    den = d[~at].mean()
    return float(d[at].mean() / den) if den > 0 else float("nan"), int(at.sum())


reads = json.load(open(rjson))["reads"]
for r in reads:
    v = sorted((x, int(w)) for w, x in r["shear"].items() if x == x)
    r["cls"] = "flat" if v and v[0][0] <= 0.05 else ("final" if r["clear"] and not r["torn"] and r["best"] in (2048, 2304, 2560) else
                                                     ("no-structure" if not r["clear"] else "other"))
for c in ("flat", "no-structure", "final"):
    rs = [r for r in reads if r["cls"] == c and not r["torn"]][:N]
    rows = []
    for r in rs:
        raw = np.frombuffer(open(os.path.join(sdir, r["name"] + ".bin"), "rb").read(), dtype="<f4").astype(np.float64)
        rows.append([shear(raw, w, h)[0] for w, h in ((2560, 1440), (2816, 1584), (3328, 1872), (3840, 2160))])
    if rows:
        a = np.array(rows)
        print("%-12s %2d untorn: shear median at 2560 %.2f, 2816 %.2f, 3328 %.2f, 3840 %.2f; snapshots with 3840 < 0.5 x min(2560..3328): %d, 3328 < 0.5 x others: %d" % (
            c, len(rows), *np.nanmedian(a, axis=0),
            int(np.sum(a[:, 3] < 0.5 * np.nanmin(a[:, :3], axis=1))), int(np.sum(a[:, 2] < 0.5 * np.nanmin(a[:, [0, 1, 3]], axis=1)))))
print("boundaries inside the snapshot: %s" % {w: int((ROWS[w][0][:-1] % 128 == 127).sum()) for w in ROWS})
