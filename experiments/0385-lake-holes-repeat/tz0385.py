#!/usr/bin/env python3
# BC5 experiment 0385: exp 0369's tz0369.py with 0369 -> 0385 (mkkit0385.py). Older comments below keep their wording.
# BC5 experiment 0385, run K2: are the night lake's holes whole 8x8 depth tiles (the HTILE that decompress #2 reads says
# "cleared" where a writer drew: the metadata reading) or cell-shaped (no writer drew there: the coverage reading)? And do
# the frame's compressed writes, before the decompress, touch the hole tiles at all?
# Input: a pl0385.py capture (exp 0365's pl0365.py: per frame a mid snapshot sM at ~+9 ms and a final sF after the last
# burst, 7 MiB of the depth image at +0x300000) and sn0385.py's reads json (each snapshot's clear size).
# Per frame with an untorn sF at a clear size in USE_W, at full render resolution over the lake window (exp 0365's
# X0..X1, Y0..Y1 of 1920x1080, scaled to the render size, cut to whole 8x8 tiles):
#   - the swizzle check: the share of aligned 8x8 tiles whose 64 dwords lie in one 256-byte block (64KB_Z_X at 32 bpp
#     keeps a tile in one block: expected 1.000);
#   - holes (depth 0): the share of tiles with a hole that are mixed (some hole, some not), on the true tile grid and on
#     one shifted by (4, 4). Tile-aligned holes: few mixed on the true grid, many on the shifted one. Cell-shaped holes:
#     about the same on both;
#   - with the previous frame's final (consecutive, same width) and this frame's untorn sM: the dwords that changed
#     between the previous final and sM, by offset within their 256-byte block (the top offsets and the share at
#     offsets 0..7, uniform 0.125), and the changed share in tiles that are all hole in this frame's final against tiles
#     with no hole.
# --selftest plants tile-aligned holes, diagonal-cell holes, and mid-frame writes at offsets 0..5 of drawn tiles only.
# usage: python3 -I tz0385.py <snapshot dir> <reads json> <swizzle json>   (on the box, after sn0385.py reads)
#        python3 -I tz0385.py --selftest <swizzle json>
import json, os, sys, types
import numpy as np

S = types.ModuleType("sn0385")  # sn0385.py's definitions (exp 0365's sn0365.py), without its command dispatch
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "sn0385.py")).read()
exec(compile(src[:src.index('\nif sys.argv[1:2] == ["--selftest"]:\n    selftest()')], "sn0385.py", "exec"), S.__dict__)


GRIDS = {}


def grid(sw, w):
    if w not in GRIDS:
        h = w * 9 // 16
        x0, x1 = (S.X0 * w // 1920) // 8 * 8, (S.X1 * w // 1920) // 8 * 8
        y0, y1 = (S.Y0 * h // 1080) // 8 * 8, (S.Y1 * h // 1080) // 8 * 8
        GRIDS[w] = sw.local(w, np.arange(y0, y1), np.arange(x0, x1))
    return GRIDS[w]


def tiles(a, shift=0):
    a = a[shift:, shift:]
    hh, ww = a.shape[0] // 8 * 8, a.shape[1] // 8 * 8
    return a[:hh, :ww].reshape(hh // 8, 8, ww // 8, 8).swapaxes(1, 2).reshape(hh // 8, ww // 8, 64)


def frame_stats(li, zf, zm=None, pf=None):
    ok = (li >= 0) & (li < zf.size)
    lic = np.clip(li, 0, zf.size - 1)
    f = zf[lic]
    hole = (f == 0) & ok
    r = {}
    t = tiles(lic)
    r["one_block"] = float(((t // 64).min(axis=2) == (t // 64).max(axis=2)).mean())
    for name, sh in (("true", 0), ("shifted", 4)):
        th, tk = tiles(hole, sh), tiles(ok, sh)
        full = tk.all(axis=2)
        n = th[full].sum(axis=1)
        anyh = n > 0
        r["mixed_" + name] = float(((n > 0) & (n < 64)).sum() / max(anyh.sum(), 1))
    r["hole_share"] = float(hole[ok].mean())
    if zm is not None and pf is not None:
        ch = (zm.view(np.uint32)[lic] != pf.view(np.uint32)[lic]) & ok
        off = lic % 64
        hist = np.bincount(off[ch], minlength=64)
        r["changed"] = float(ch[ok].mean())
        r["hist"] = hist.tolist()
        th, tc, tk = tiles(hole), tiles(ch), tiles(ok)
        full = tk.all(axis=2)
        allh = full & th.all(axis=2)
        noh = full & ~th.any(axis=2)
        r["changed_in_hole_tiles"] = float(tc[allh].mean()) if allh.any() else float("nan")
        r["changed_in_drawn_tiles"] = float(tc[noh].mean()) if noh.any() else float("nan")
    return r


def summary(rows):
    def med(k):
        v = [r[k] for r in rows if k in r and r[k] == r[k]]
        return "%.3f (n %d)" % (float(np.median(v)), len(v)) if v else "-"
    print("# %d finals; one 256-byte block per 8x8 tile: %s; hole share %s" % (len(rows), med("one_block"), med("hole_share")))
    print("# tiles with a hole that are mixed: true grid %s, grid shifted by (4, 4) %s" % (med("mixed_true"), med("mixed_shifted")))
    h = np.sum([r["hist"] for r in rows if "hist" in r], axis=0) if any("hist" in r for r in rows) else None
    if h is not None and h.sum():
        top = np.argsort(h)[::-1][:8]
        print("# mid against the previous final: changed %s; in tiles all hole in this final %s, in tiles with no hole %s" % (
            med("changed"), med("changed_in_hole_tiles"), med("changed_in_drawn_tiles")))
        print("# changed dwords by offset in their 256-byte block: share at offsets 0..7 %.3f (uniform 0.125); top offsets %s" % (
            h[:8].sum() / h.sum(), ", ".join("%d:%.3f" % (o, h[o] / h.sum()) for o in top)))


def run(sdir, rjson, zsw):
    sw = S.Swz(zsw)
    reads = {r["name"]: r for r in json.load(open(rjson))["reads"]}
    by = {}
    for s in S.snaps_of(sdir):
        by.setdefault((s["cap"], s["f"]), {})[s["s"]] = s
    rows, prev = [], {}
    for (cap, k) in sorted(by):
        sF = by[(cap, k)].get("F")
        if sF is None or sF["torn"] or not reads[sF["name"]]["clear"] or reads[sF["name"]]["best"] not in S.USE_W:
            continue
        w = int(reads[sF["name"]]["best"])
        li = grid(sw, w)
        zf = S.load(sdir, sF["name"]).astype(np.float32)
        sM = by[(cap, k)].get("M")
        pv = prev.get((cap, k - 1))
        zm = S.load(sdir, sM["name"]).astype(np.float32) if sM is not None and not sM["torn"] and pv is not None and pv[0] == w else None
        r = frame_stats(li, zf, zm, pv[1] if zm is not None else None)
        r.update(frame="%s.f%d" % (cap, k), w=w)
        rows.append(r)
        prev[(cap, k)] = (w, zf)
        print("  %s w %d holes %.3f mixed true %.3f shifted %.3f one-block %.3f%s" % (r["frame"], w, r["hole_share"], r["mixed_true"], r["mixed_shifted"], r["one_block"],
              " | changed %.3f hole tiles %.3f drawn tiles %.3f off0-7 %.3f" % (r["changed"], r["changed_in_hole_tiles"], r["changed_in_drawn_tiles"],
                                                                            sum(r["hist"][:8]) / max(sum(r["hist"]), 1)) if "hist" in r else ""))
    summary(rows)


def selftest(zsw):
    sw = S.Swz(zsw)
    w = 2560
    li = grid(sw, w)
    n = S.S_LEN // 4
    rng = np.random.default_rng(1)
    hh, ww = li.shape
    yy, xx = np.mgrid[0:hh, 0:ww]
    cells = (((xx + 2 * yy) // 37 + (yy // 23)) % 2) == 0  # diagonal cell shapes, not tile-aligned
    tilemask = np.kron(rng.random((hh // 8 + 1, ww // 8 + 1)) < 0.3, np.ones((8, 8), bool))[:hh, :ww]
    out = {}
    for name, m in (("tile-aligned", tilemask), ("cells", cells)):
        prevf = np.zeros(n, np.float32)
        prevf[li[li < n]] = rng.uniform(0.2, 0.9, size=(li < n).sum()).astype(np.float32)
        zf = prevf.copy()
        zf[li[(li < n)]] = rng.uniform(0.2, 0.9, size=(li < n).sum()).astype(np.float32)
        zf[li[m & (li < n)]] = 0
        zm = prevf.copy()
        drawn_tiles = ~tiles(m).any(axis=2)
        t = tiles(li)
        sel = t[drawn_tiles][:, :]
        blocks = np.unique(sel // 64)
        for o in range(6):
            idx = blocks * 64 + o
            idx = idx[idx < n]
            zm[idx] = 1.5
        out[name] = frame_stats(li, zf, zm, prevf)
    a, c = out["tile-aligned"], out["cells"]
    print("# selftest: one block %.3f; tile-aligned mixed true %.3f shifted %.3f; cells mixed true %.3f shifted %.3f; changed in hole tiles %.3f, drawn %.3f, off0-7 %.3f" % (
        a["one_block"], a["mixed_true"], a["mixed_shifted"], c["mixed_true"], c["mixed_shifted"], c["changed_in_hole_tiles"], c["changed_in_drawn_tiles"],
        sum(c["hist"][:8]) / max(sum(c["hist"]), 1)))
    ok = a["one_block"] > 0.99 and a["mixed_true"] < 0.05 and a["mixed_shifted"] > 0.5 and abs(c["mixed_true"] - c["mixed_shifted"]) < 0.15 and c["changed_in_hole_tiles"] < 0.01 \
        and sum(c["hist"][:8]) / max(sum(c["hist"]), 1) > 0.99
    print("# selftest %s" % ("passed" if ok else "FAILED"))
    return ok


if sys.argv[1:2] == ["--selftest"]:
    sys.exit(0 if selftest(sys.argv[2]) else 1)
run(*sys.argv[1:4])
