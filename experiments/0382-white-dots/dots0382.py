#!/usr/bin/env python3
# BC5 experiment 0382: how many isolated bright points ("white dots", "sparkles") a run's screenshots hold, and what
# kind they are, in numbers (the shots themselves are never copied off the box or committed). A dot pixel is bright
# (luma >= T, default 0.70), much brighter than its surroundings (luma minus the mean of the 7x7 box around it,
# excluding its own 3x3, >= D, default 0.25), with at most two bright pixels in that ring, and the brightest pixel of
# its 3x3 (ties: the first in scan order), so a dot of 1-3 pixels counts once. Large bright areas and their edges (sky,
# white walls, the lab's washed-out floor of F362) do not count: their surroundings are bright too. Per shot: the dot
# count, the dots per megapixel, their count in a 3 x 3 grid of the frame, the mean luma, how many of the shot's dots
# sit within 2 pixels of a dot of the previous shot ("kept"), and how much of the view changed since the previous shot
# (the share of pixels whose luma moved by more than 0.04: "change"). Then the median over the shots that are not
# dark (mean luma < 0.03) and not identical to the previous shot. Runs on the box in the ubuntu distrobox (numpy,
# PIL), or on a synthetic self-test (--selftest). The shots are the 1920x1080 window after the title's upscale, which
# dims a dot of one render pixel; and no shot of the dots exists yet to calibrate on (the scenes' ordinary brights
# reach p99 luma 0.68-0.96 in exp 0299/0303/0305's extracts). So every shot is also counted on a grid, T in 0.55 /
# 0.70 / 0.85 and D in 0.15 / 0.25 / 0.40, with the grid's medians at the end: an arm comparison that holds on most of
# the grid does not hang on one threshold.
# Frames are told apart by the SHA-256 of their decoded RGB pixels (Codex review REVIEW-03, R2: mean luma plus dot
# count took different frames for repeats). ROI=x0,y0,x1,y1 in the environment counts inside a fixed scene region only.
# What kind of dot (no description of the dots exists, the top session 2026-10-30): per dot its colour (neutral when
# (max - min) / max of its RGB is at most 0.15: white or grey; else tinted), its size (pixels of its 5x5 above half
# way from the ring to the peak) and its contrast; per phase a reading from the numbers, with the thresholds printed:
#   - in a still view (median change <= 0.02), dots that move from shot to shot (median kept share < 0.25) are
#     per-frame noise (sparkles from sampling noise the denoiser lets through), dots that stay (>= 0.6) are tied to
#     the scene or to a stuck buffer;
#   - at the phase's largest view change (the run's camera nudge), dots that keep their screen position (kept share
#     >= 0.6 while change >= 0.15) are stuck to the screen (a buffer that is not reprojected), not to the world.
# --compare <dir A> <dir B>: the share of B's dots within 2 pixels of any dot of A (A -> C: the dots that RT off
# keeps are scene brights, not RT's), and the change from A's last used shot to B's first.
# --transient <dir>: A2 of 2026-10-30 showed the idle camera drifting, so no pair of shots is still, and the scene's
# lamps dominate a sheet ranked by contrast. Each shot is aligned to its neighbours (phase correlation), and a dot
# with no dot within 3 pixels of it in the shot before or after is "alone": a dot of one frame is, a lamp is not.
# A moving person or leaf can be too, so the alone dots' sheet (SHEET) has to be looked at.
# SHEET=<png> in the environment writes a contact sheet of the phase's 48 highest-contrast dots (21x21 crops, x6) to
# that path: the title's imagery, so it stays on the box beside the shots, never committed; viewing it on the laptop
# needs the top session's leave and is deleted there afterwards.
# usage: [ROI=x0,y0,x1,y1] [SHEET=<png>] python3 dots0382.py <shots dir> [T] [D]
#        [ROI=...] python3 dots0382.py --compare <dir A> <dir B> [T] [D]  |  python3 dots0382.py --selftest
#        [ROI=...] [SHEET=<png>] python3 dots0382.py --transient <dir> [T] [D]
import glob, os, sys, hashlib
import numpy as np

STILL, MOVES, STAYS, NUDGE, NEUTRAL, CHANGE = 0.02, 0.25, 0.60, 0.15, 0.15, 0.04


def luma(a):
    return 0.2126 * a[:, :, 0] + 0.7152 * a[:, :, 1] + 0.0722 * a[:, :, 2]


def box_sum(y, r):
    # sum over the (2r+1)^2 box around each pixel, edges padded by reflection
    p = np.pad(y, r + 1, mode="reflect")
    c = p.cumsum(0).cumsum(1)
    n = 2 * r + 1
    s = c[n:, n:] - c[:-n, n:] - c[n:, :-n] + c[:-n, :-n]
    return s[: y.shape[0], : y.shape[1]]


def ring_mean(y):
    return (box_sum(y, 3) - box_sum(y, 1)) / (49 - 9)


def dots(y, t=0.80, d=0.30, ring=None):
    ring = ring_mean(y) if ring is None else ring
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


def near(cur, prev, r=2):
    # how many of cur's points lie within r pixels (Chebyshev) of any of prev's
    if len(cur) == 0 or prev is None or len(prev) == 0:
        return 0
    occ = set()
    for yy, xx in prev:
        for a in range(-r, r + 1):
            for b in range(-r, r + 1):
                occ.add((int(yy) + a, int(xx) + b))
    return sum(1 for yy, xx in cur if (int(yy), int(xx)) in occ)


kept = near


def view_shift(a, b):
    # the displacement (dy, dx) that moves b onto a (phase correlation): the camera's drift between two shots
    r = np.fft.rfft2(a - a.mean()) * np.conj(np.fft.rfft2(b - b.mean()))
    r = np.fft.irfft2(r / np.maximum(np.abs(r), 1e-9), s=a.shape)
    yy, xx = (int(v) for v in np.unravel_index(int(np.argmax(r)), r.shape))
    return (yy - a.shape[0] if yy > a.shape[0] // 2 else yy, xx - a.shape[1] if xx > a.shape[1] // 2 else xx)


def transient(rows, r=3):
    # per shot, its dots with no dot within r pixels in the shot before or after it, with the views aligned, and the
    # shifts: a dot of one frame is alone, a lamp is not (a dot only tested against one neighbour at the phase's ends)
    out = []
    for i, cur in enumerate(rows):
        occ, shifts = set(), []
        for j in (i - 1, i + 1):
            if 0 <= j < len(rows):
                dy, dx = view_shift(cur["y"], rows[j]["y"])
                shifts.append((dy, dx))
                for yy, xx in rows[j]["pts"]:
                    for a in range(-r, r + 1):
                        for b in range(-r, r + 1):
                            occ.add((int(yy) + dy + a, int(xx) + dx + b))
        alone = [(p, k) for p, k in zip(cur["pts"], cur["kinds"]) if (int(p[0]), int(p[1])) not in occ]
        out.append({"alone": alone, "shifts": shifts})
    return out


def kinds(rgb, y, ring, pts):
    # per dot: neutral (1) or tinted (0), size in pixels, contrast to its ring
    out = []
    h, w = y.shape
    for yy, xx in pts:
        c = rgb[yy, xx]
        mx, mn = float(c.max()), float(c.min())
        half = (ring[yy, xx] + y[yy, xx]) / 2
        win = y[max(0, yy - 2): yy + 3, max(0, xx - 2): xx + 3]
        out.append((1 if mx > 0 and (mx - mn) / mx <= NEUTRAL else 0, int((win >= half).sum()), float(y[yy, xx] - ring[yy, xx])))
    return out


def measure(y, t, d, prev_pts, rgb=None, prev_y=None):
    ring = ring_mean(y)
    pts = dots(y, t, d, ring)
    h, w = y.shape
    grid = [0] * 9
    for yy, xx in pts:
        grid[min(2, yy * 3 // h) * 3 + min(2, xx * 3 // w)] += 1
    kd = kinds(rgb if rgb is not None else np.repeat(y[:, :, None], 3, 2), y, ring, pts)
    change = float((np.abs(y - prev_y) > CHANGE).mean()) if prev_y is not None and prev_y.shape == y.shape else None
    return {"n": len(pts), "per_mpix": len(pts) / (h * w / 1e6), "grid": grid, "mean": float(y.mean()),
            "kept": kept(pts, prev_pts), "pts": pts, "size": "%dx%d" % (w, h), "kinds": kd, "change": change, "ring": ring}


def reading(use):
    # the phase's reading from the used shots (thresholds printed with it)
    if not use:
        return "no used shot"
    n = float(np.median([r["n"] for r in use]))
    if n < 3:
        return "few or no dots (median %.0f)" % n
    pairs = [r for r in use if r["change"] is not None and r["n"] >= 3 and r["prev_used"]]
    still = [r for r in pairs if r["change"] <= STILL]
    words = []
    if still:
        share = float(np.median([r["kept"] / r["n"] for r in still]))
        if share < MOVES:
            words.append("in a still view (%d pairs, change <= %.2f) the dots move from shot to shot (median kept share %.2f < %.2f): per-frame noise" % (len(still), STILL, share, MOVES))
        elif share >= STAYS:
            words.append("in a still view (%d pairs, change <= %.2f) the dots stay (median kept share %.2f >= %.2f): tied to the scene or to a stuck buffer" % (len(still), STILL, share, STAYS))
        else:
            words.append("in a still view (%d pairs) mixed: median kept share %.2f" % (len(still), share))
    else:
        words.append("no still pair (every change > %.2f): no flicker reading" % STILL)
    big = max(pairs, key=lambda r: r["change"]) if pairs else None
    if big is not None and big["change"] >= NUDGE:
        share = big["kept"] / big["n"]
        words.append("at the largest view change (%s, change %.2f) %d of %d dots kept their screen position (%.2f): %s" % (
            big["name"], big["change"], big["kept"], big["n"], share,
            "stuck to the screen" if share >= STAYS else ("they moved with the view" if share < MOVES else "mixed")))
    kd = [k for r in use for k in r["kinds"]]
    if kd:
        words.append("%.0f%% neutral (white or grey), median size %.0f px, median contrast %.2f" % (
            100.0 * sum(k[0] for k in kd) / len(kd), float(np.median([k[1] for k in kd])), float(np.median([k[2] for k in kd]))))
    return "; ".join(words)


def selftest():
    rng = np.random.default_rng(382)
    h, w = 270, 480
    base = np.clip(0.25 + 0.05 * rng.standard_normal((h, w)), 0, 1)
    img = base.copy()
    pos = [(20, 30), (100, 200), (200, 400), (150, 50)]
    for yy, xx in pos:          # four 1-pixel dots
        img[yy, xx] = 1.0
    img[60:62, 300:302] = 0.98  # one 2x2 dot: counts once
    img[240, 30] = 0.75         # one dim dot (an upscaled 1-px dot): counted at T 0.70, not at 0.85
    img[180:260, 100:220] = 0.95  # a bright area: no dots inside it
    img[180:260, 100:220] += 0.02 * rng.standard_normal((80, 120))
    img = np.clip(img, 0, 1)
    r = measure(img, 0.70, 0.25, None)
    assert r["n"] == 6, r["n"]
    assert measure(img, 0.85, 0.25, None)["n"] == 5
    r2 = measure(img, 0.70, 0.25, r["pts"], prev_y=img)
    assert r2["kept"] == 6 and r2["change"] == 0.0, (r2["kept"], r2["change"])
    assert sorted(k[1] for k in r2["kinds"]) == [1, 1, 1, 1, 1, 4], r2["kinds"]  # five 1-px dots, one 2x2
    moved = base.copy()
    for yy, xx in pos:
        moved[yy + 10, xx + 10] = 1.0
    r3 = measure(np.clip(moved, 0, 1), 0.70, 0.25, r["pts"])
    assert r3["n"] == 4 and r3["kept"] == 0, (r3["n"], r3["kept"])
    # colour: a white dot is neutral, a red-orange one tinted
    rgb = np.repeat(base[:, :, None], 3, 2)
    rgb[50, 50] = (1.0, 1.0, 1.0)
    rgb[50, 150] = (1.0, 0.8, 0.3)
    y = luma(rgb)
    rk = measure(y, 0.70, 0.25, None, rgb=rgb)
    assert rk["n"] == 2 and sorted(k[0] for k in rk["kinds"]) == [0, 1], rk["kinds"]
    # readings: dots that move in a still view, dots that stay, dots stuck to the screen across a pan
    def phase(frames):
        use, prev, prev_y = [], None, None
        for i, f in enumerate(frames):
            m = measure(f, 0.70, 0.25, prev, prev_y=prev_y)
            m["name"], m["prev_used"] = "s%d" % i, prev is not None
            use.append(m)
            prev, prev_y = m["pts"], f
        return reading(use)
    def with_dots(bg, pts):
        f = bg.copy()
        for yy, xx in pts:
            f[yy, xx] = 1.0
        return f
    still_bg = np.clip(0.25 + 0.05 * rng.standard_normal((h, w)), 0, 1)
    rand = lambda: [(int(a), int(b)) for a, b in zip(rng.integers(10, h - 10, 12), rng.integers(10, w - 10, 12))]
    fixed = rand()
    assert "per-frame noise" in phase([with_dots(still_bg, rand()) for _ in range(4)])
    assert "dots stay" in phase([with_dots(still_bg, fixed) for _ in range(4)])
    panned = np.roll(still_bg, 40, axis=1)
    rd = phase([with_dots(still_bg, fixed), with_dots(still_bg, fixed), with_dots(panned, fixed)])
    assert "stuck to the screen" in rd, rd
    rd = phase([with_dots(still_bg, fixed), with_dots(panned, [(a, (b + 40) % w) for a, b in fixed])])
    assert "moved with the view" in rd, rd
    print("selftest ok: 6 dots at T 0.70 (four 1-px, one 2x2, one dim), 5 at T 0.85, none in the bright area or on its edges;"
          " kept 6 when unchanged, 0 when moved; sizes 1 and 4; neutral vs tinted; readings: per-frame noise, stay,"
          " stuck to the screen, moved with the view")


def load(d, roi):
    # the shots of a directory as (name, digest, rgb, luma), the ROI cut out
    from PIL import Image
    out = []
    for f in sorted(glob.glob(os.path.join(d, "*.png"))):
        try:
            pixels = np.asarray(Image.open(f).convert("RGB"))
            digest = hashlib.sha256(pixels.tobytes()).digest()
            a = pixels.astype(np.float64) / 255.0
        except OSError as e:
            print("  %s: unreadable (%s)" % (os.path.basename(f), e))
            continue
        if roi is not None:  # the fixed scene region (no HUD or menu), in the shot's pixels
            a = a[roi[1]:roi[3], roi[0]:roi[2]]
        out.append((os.path.basename(f), digest, a, luma(a)))
    return out


def phase_rows(shots, t, d, grid_td=None, verbose=True):
    rows, prev, prev_y = [], None, None
    for name, digest, a, y in shots:
        r = measure(y, t, d, prev, rgb=a, prev_y=prev_y)
        r["name"], r["digest"], r["y"], r["rgb"] = name, digest, y, a
        if grid_td is not None:
            r["gridn"] = [len(dots(y, gt, gd, r["ring"])) for gt, gd in grid_td]
        dark = r["mean"] < 0.03
        same = bool(rows) and digest == rows[-1]["digest"]
        r["use"] = not dark and not same
        r["prev_used"] = bool(rows) and rows[-1]["use"]
        if verbose:
            nn = sum(k[0] for k in r["kinds"])
            print("  %s %s: dots %d (%.1f per Mpix), kept %d of them from the previous shot; luma mean %.3f; grid %s; neutral %d, tinted %d, size median %s; change %s%s" % (
                r["name"], r["size"], r["n"], r["per_mpix"], r["kept"], r["mean"], " ".join(str(g) for g in r["grid"]),
                nn, r["n"] - nn, "%.0f" % float(np.median([k[1] for k in r["kinds"]])) if r["kinds"] else "-",
                "-" if r["change"] is None else "%.3f" % r["change"], " dark" if dark else (" same as before" if same else "")))
            if grid_td is not None:
                print("    grid T/D: %s" % " ".join("%.2f/%.2f:%d" % (gt, gd, n) for (gt, gd), n in zip(grid_td, r["gridn"])))
        rows.append(r)
        prev, prev_y = r["pts"], y
    return rows


def sheet(use, path, k=48, half=10, zoom=6):
    from PIL import Image
    cand = []
    for r in use:
        for (yy, xx), kd in zip(r["pts"], r["kinds"]):
            cand.append((kd[2], r, int(yy), int(xx)))
    cand.sort(key=lambda c: -c[0])
    cand = cand[:k]
    if not cand:
        return 0
    tile, cols = (2 * half + 1) * zoom, 8
    rows_n = (len(cand) + cols - 1) // cols
    out = np.zeros((rows_n * (tile + 2), cols * (tile + 2), 3), dtype=np.uint8)
    for i, (_, r, yy, xx) in enumerate(cand):
        a = np.pad(r["rgb"], ((half, half), (half, half), (0, 0)))
        crop = a[yy: yy + 2 * half + 1, xx: xx + 2 * half + 1]
        crop = np.repeat(np.repeat((crop * 255).astype(np.uint8), zoom, 0), zoom, 1)
        oy, ox = (i // cols) * (tile + 2), (i % cols) * (tile + 2)
        out[oy: oy + tile, ox: ox + tile] = crop
    Image.fromarray(out).save(path)
    return len(cand)


def main():
    if sys.argv[1:2] == ["--selftest"]:
        selftest()
        return
    cmp = sys.argv[1:2] == ["--compare"]
    alone = sys.argv[1:2] == ["--transient"]
    args = sys.argv[2:] if cmp or alone else sys.argv[1:]
    dirs = args[:2] if cmp else args[:1]
    rest = args[len(dirs):]
    t = float(rest[0]) if len(rest) > 0 else 0.70
    d = float(rest[1]) if len(rest) > 1 else 0.25
    # ROI=x0,y0,x1,y1 (environment, shot pixels, x1/y1 exclusive): count inside that region only (Codex review REVIEW-03, R3/R5)
    roi = tuple(int(v) for v in os.environ["ROI"].split(",")) if os.environ.get("ROI") else None
    assert roi is None or (len(roi) == 4 and roi[0] < roi[2] and roi[1] < roi[3]), "ROI is x0,y0,x1,y1"
    roi_s = ",".join(map(str, roi)) if roi else "whole shot"
    if alone:
        use = [r for r in phase_rows(load(dirs[0], roi), t, d, verbose=False) if r["use"]]
        res = transient(use)
        for r, a in zip(use, res):
            print("  %s: dots %d, alone %d (neutral %d, size <= 3: %d); view shifts %s" % (r["name"], r["n"], len(a["alone"]),
                  sum(k[0] for _, k in a["alone"]), sum(1 for _, k in a["alone"] if k[1] <= 3), " ".join("%+d,%+d" % s for s in a["shifts"])))
        counts = [len(a["alone"]) for a in res] or [0]
        print("# transient %s: %d used; alone per shot median %.0f, max %d of median %.0f dots; T %.2f D %.2f; ROI %s" % (
            dirs[0], len(use), float(np.median(counts)), max(counts), float(np.median([r["n"] for r in use])) if use else 0, t, d, roi_s))
        if os.environ.get("SHEET") and use:
            small = [[(p, k) for p, k in a["alone"] if not os.environ.get("SHEET_SMALL") or k[1] <= 3] for a in res]  # SHEET_SMALL=1: size <= 3 only
            only = [{"pts": [p for p, _ in s], "kinds": [k for _, k in s], "rgb": r["rgb"]} for r, s in zip(use, small)]
            print("# sheet: %d alone dots in %s (private: the title's imagery)" % (sheet(only, os.environ["SHEET"]), os.environ["SHEET"]))
        return
    if cmp:
        ua = [r for r in phase_rows(load(dirs[0], roi), t, d, verbose=False) if r["use"]]
        ub = [r for r in phase_rows(load(dirs[1], roi), t, d, verbose=False) if r["use"]]
        if not ua or not ub:
            print("# compare %s -> %s: no used shot in %s" % (dirs[0], dirs[1], dirs[0] if not ua else dirs[1]))
            return
        union = [p for r in ua for p in r["pts"]]
        shares = []
        for r in ub:
            at = near(r["pts"], union)
            shares.append(at / r["n"] if r["n"] else None)
            print("  %s: dots %d, %d of them within 2 px of a dot of %s" % (r["name"], r["n"], at, os.path.basename(dirs[0].rstrip("/"))))
        ch = float((np.abs(ub[0]["y"] - ua[-1]["y"]) > CHANGE).mean()) if ub[0]["y"].shape == ua[-1]["y"].shape else float("nan")
        s = [v for v in shares if v is not None]
        print("# compare %s (%d used, %d dots) -> %s (%d used): median share of B's dots at A's dots %s; change from A's last to B's first %.3f; T %.2f D %.2f; ROI %s" % (
            dirs[0], len(ua), len(union), dirs[1], len(ub), "%.2f" % float(np.median(s)) if s else "-", ch, t, d, roi_s))
        return
    grid_td = [(gt, gd) for gt in (0.55, 0.70, 0.85) for gd in (0.15, 0.25, 0.40)]
    rows = phase_rows(load(dirs[0], roi), t, d, grid_td)
    use = [r for r in rows if r["use"]]
    print("# %s: %d shots, %d used, %d distinct frames; T %.2f D %.2f; ROI %s" % (
        dirs[0], len(rows), len(use), len(set(r["digest"] for r in rows)), t, d, roi_s))
    if use:
        med = lambda k: float(np.median([r[k] for r in use]))
        ch = [r["change"] for r in use if r["change"] is not None]
        print("# median over the used shots: dots %.0f (%.1f per Mpix), kept %.0f; max dots %d; change %s" % (
            med("n"), med("per_mpix"), med("kept"), max(r["n"] for r in use), "%.3f" % float(np.median(ch)) if ch else "-"))
        print("# median over the used shots, grid T/D: %s" % " ".join(
            "%.2f/%.2f:%.0f" % (gt, gd, float(np.median([r["gridn"][i] for r in use]))) for i, (gt, gd) in enumerate(grid_td)))
    print("# reading: %s" % reading(use))
    if os.environ.get("SHEET") and use:
        print("# sheet: %d dots in %s (private: the title's imagery)" % (sheet(use, os.environ["SHEET"]), os.environ["SHEET"]))


if __name__ == "__main__":
    main()
