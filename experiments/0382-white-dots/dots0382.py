#!/usr/bin/env python3
# BC5 experiment 0382: how many isolated bright points ("white dots", "sparkles") a run's screenshots hold, in numbers
# (the shots themselves are never copied off the box or committed). A dot pixel is bright (luma >= T, default 0.80),
# much brighter than its surroundings (luma minus the mean of the 7x7 box around it, excluding its own 3x3, >= D,
# default 0.30), with at most two bright pixels in that ring, and the brightest pixel of its 3x3 (ties: the first in
# scan order), so a dot of 1-3 pixels counts once. Large bright areas and their edges (sky, white walls, the lab's
# washed-out floor of F362) do not count: their surroundings are bright too. Per shot: the dot count, the dots per megapixel, their count in a 3 x 3 grid of the frame, the mean
# luma, and how many of the shot's dots sit within 2 pixels of a dot of the previous shot ("kept": dots tied to the
# scene or to a stuck history stay; per-frame noise moves). Then the median over the shots that are not dark (mean
# luma < 0.03) and not identical to the previous shot. Runs on the box in the ubuntu distrobox (numpy, PIL), or on a
# synthetic self-test (--selftest).
# usage: python3 dots0382.py <shots dir> [T] [D]  |  python3 dots0382.py --selftest
import glob, os, sys
import numpy as np


def luma(a):
    return 0.2126 * a[:, :, 0] + 0.7152 * a[:, :, 1] + 0.0722 * a[:, :, 2]


def box_sum(y, r):
    # sum over the (2r+1)^2 box around each pixel, edges padded by reflection
    p = np.pad(y, r + 1, mode="reflect")
    c = p.cumsum(0).cumsum(1)
    n = 2 * r + 1
    s = c[n:, n:] - c[:-n, n:] - c[n:, :-n] + c[:-n, :-n]
    return s[: y.shape[0], : y.shape[1]]


def dots(y, t=0.80, d=0.30):
    s7 = box_sum(y, 3)
    s3 = box_sum(y, 1)
    ring = (s7 - s3) / (49 - 9)
    bright = (y >= t).astype(np.float64)
    ring_bright = box_sum(bright, 3) - box_sum(bright, 1)  # bright pixels in the ring: few for a dot, many on an edge
    cand = (y >= t) & (y - ring >= d) & (ring_bright <= 2.5)
    # 3x3 local maximum (first in scan order on ties)
    p = np.pad(y, 1, mode="constant", constant_values=-1.0)
    h, w = y.shape
    is_max = np.ones_like(cand)
    k = 0
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dy == 0 and dx == 0:
                k = 1
                continue
            nb = p[1 + dy: 1 + dy + h, 1 + dx: 1 + dx + w]
            is_max &= (y > nb) if k == 0 else (y >= nb)
    return np.argwhere(cand & is_max)


def kept(cur, prev, r=2):
    if len(cur) == 0 or prev is None or len(prev) == 0:
        return 0
    occ = set()
    for yy, xx in prev:
        for a in range(-r, r + 1):
            for b in range(-r, r + 1):
                occ.add((int(yy) + a, int(xx) + b))
    return sum(1 for yy, xx in cur if (int(yy), int(xx)) in occ)


def measure(y, t, d, prev_pts):
    pts = dots(y, t, d)
    h, w = y.shape
    grid = [0] * 9
    for yy, xx in pts:
        grid[min(2, yy * 3 // h) * 3 + min(2, xx * 3 // w)] += 1
    return {"n": len(pts), "per_mpix": len(pts) / (h * w / 1e6), "grid": grid, "mean": float(y.mean()),
            "kept": kept(pts, prev_pts), "pts": pts, "size": "%dx%d" % (w, h)}


def selftest():
    rng = np.random.default_rng(382)
    h, w = 270, 480
    base = np.clip(0.25 + 0.05 * rng.standard_normal((h, w)), 0, 1)
    img = base.copy()
    pos = [(20, 30), (100, 200), (200, 400), (150, 50)]
    for yy, xx in pos:          # four 1-pixel dots
        img[yy, xx] = 1.0
    img[60:62, 300:302] = 0.98  # one 2x2 dot: counts once
    img[180:260, 100:220] = 0.95  # a bright area: no dots inside it
    img[180:260, 100:220] += 0.02 * rng.standard_normal((80, 120))
    img = np.clip(img, 0, 1)
    r = measure(img, 0.80, 0.30, None)
    assert r["n"] == 5, r["n"]
    r2 = measure(img, 0.80, 0.30, r["pts"])
    assert r2["kept"] == 5, r2["kept"]
    moved = base.copy()
    for yy, xx in pos:
        moved[yy + 10, xx + 10] = 1.0
    r3 = measure(np.clip(moved, 0, 1), 0.80, 0.30, r["pts"])
    assert r3["n"] == 4 and r3["kept"] == 0, (r3["n"], r3["kept"])
    print("selftest ok: 5 dots found (four 1-px, one 2x2), none in the bright area; kept 5 when unchanged, 0 when moved")


def main():
    if sys.argv[1:2] == ["--selftest"]:
        selftest()
        return
    from PIL import Image
    t = float(sys.argv[2]) if len(sys.argv) > 2 else 0.80
    d = float(sys.argv[3]) if len(sys.argv) > 3 else 0.30
    rows, prev = [], None
    for f in sorted(glob.glob(os.path.join(sys.argv[1], "*.png"))):
        try:
            a = np.asarray(Image.open(f).convert("RGB")).astype(np.float64) / 255.0
        except OSError as e:
            print("  %s: unreadable (%s)" % (os.path.basename(f), e))
            continue
        r = measure(luma(a), t, d, prev)
        r["name"] = os.path.basename(f)
        dark = r["mean"] < 0.03
        same = rows and abs(r["mean"] - rows[-1]["mean"]) < 1e-12 and r["n"] == rows[-1]["n"]
        r["use"] = not dark and not same
        print("  %s %s: dots %d (%.1f per Mpix), kept %d of them from the previous shot; luma mean %.3f; grid %s%s" % (
            r["name"], r["size"], r["n"], r["per_mpix"], r["kept"], r["mean"], " ".join(str(g) for g in r["grid"]),
            " dark" if dark else (" same as before" if same else "")))
        rows.append(r)
        prev = r["pts"]
    use = [r for r in rows if r["use"]]
    print("# %s: %d shots, %d used; T %.2f D %.2f" % (sys.argv[1], len(rows), len(use), t, d))
    if use:
        med = lambda k: float(np.median([r[k] for r in use]))
        print("# median over the used shots: dots %.0f (%.1f per Mpix), kept %.0f; max dots %d" % (
            med("n"), med("per_mpix"), med("kept"), max(r["n"] for r in use)))


if __name__ == "__main__":
    main()
