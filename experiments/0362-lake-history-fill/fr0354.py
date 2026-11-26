#!/usr/bin/env python3
# BC5 experiment 0354: exp 0312's fr0312.py with one fix: the title's full-screen water draw has a flipped viewport
# ("vp 2816x-1584 at 0,1584" in run J1's journal), so the viewport height may carry a sign; only the width is used.
# BC5 experiment 0312, run J1: each depth read's render size from the shared build's draw journal. In P1 three quarters
# of the depth reads had no clear size (rd0312.py's shear test), so the hole labels failed. Exp 0283's xy0283.py took
# the size from the private binary's "bake db" lines; the shared build has none, but journals with
# BC5_DIRECT_DRAW_JOURNAL=<t>:<n> and _PS=11d01d7100 (patch 0001, experiment 0156's filters), per full-screen water draw:
#   "draw journal buf N (D dwords) at P: <dwords> | rt0 ADDR WxH info .. mask .. | vp WxH at X,Y | ps PS es .. gs .. cs .."
#   "bake draw buf N at P: t T wall S.MS | win .."   (journal time from the emulator's start; wall clock, ms)
# rt0 is CB_COLOR0_ATTRIB2's mip-0 size, vp the viewport (2 x scale). A frame is one such draw: its start is the bake
# line's wall clock (same buf and offset), its sizes rt0 W and vp W.
# Matching (xy0283.py's rule): a read at wall time r shows frame j, the latest frame that started at least L ms before r
# (a window's last frame: within 1.5 median frame intervals). For each size field and L in -250..250 ms (5 ms steps):
# the share of rd0312.py's clear depth reads (next-best shear >= 3 x best) whose best size equals their frame's W. The
# field and lag with the largest share win (among lags matching at least 60 % as many clear reads as the best-matching
# lag; ties: the middle one). Every read then gets its frame (index, t, W) when W is one of rd0312.py's sizes.
# Writes <out json> {"field", "lag_ms", "agree", "clear_matched", "frames", "sizes": {read: W}, "frame_of": {read: j}}
# and prints the table. Summaries only. Pure Python (runs on the box or the laptop).
# usage: python3 -I fr0312.py <direct.log> <reads json> <out json>   |   python3 -I fr0312.py --selftest
import bisect, json, random, re, statistics, sys

WIDTHS = (2048, 2304, 2560, 2816, 3072, 3328)
DRAW = re.compile(r"draw journal buf (\d+) \(\d+ dwords\) at (\d+):.*?\| rt0 [0-9a-f]+ (\d+)x(\d+) .*?\| vp (\d+)x(-?\d+) at .*?\| ps ([0-9a-f]+)")
BAKE = re.compile(r"bake draw buf (\d+) at (\d+): t ([\d.]+) wall (\d+)\.(\d+)")
FIELDS = ("rt0", "vp")


def frames_of(lines):
    draws, frames = {}, []
    for l in lines:
        m = DRAW.search(l)
        if m:
            if m[7].startswith("11d01d7100"):
                draws[(m[1], m[2])] = {"rt0": int(m[3]), "vp": int(m[5])}
            continue
        m = BAKE.search(l)
        if m and (m[1], m[2]) in draws:
            d = draws.pop((m[1], m[2]))
            frames.append({"wall": int(m[4]) + int(m[5]) / 1000, "t": float(m[3]), "rt0": d["rt0"], "vp": d["vp"]})
    frames.sort(key=lambda f: f["wall"])
    return frames


def match(frames, reads, lag_ms):
    starts = [f["wall"] for f in frames]
    gaps = [b - a for a, b in zip(starts, starts[1:])]
    med = statistics.median(gaps) if gaps else 0.1
    out = {}
    for r in reads:
        t = r["wall"] - lag_ms / 1000
        j = bisect.bisect_right(starts, t) - 1
        if j < 0 or (j == len(starts) - 1 and t - starts[j] > 1.5 * med):
            continue
        out[r["name"]] = j
    return out


def fit(frames, reads):
    clear = [r for r in reads if r["kind"] == "z" and r.get("clear")]
    table = []
    for fld in FIELDS:
        rows = []
        for lag in range(-250, 255, 5):
            m = match(frames, clear, lag)
            ok = sum(1 for r in clear if r["name"] in m and frames[m[r["name"]]][fld] == r["best"])
            rows.append((lag, len(m), ok))
        most = max(n for _, n, _ in rows)
        good = [(ok / n if n else 0.0, lag, n, ok) for lag, n, ok in rows if n >= 0.6 * most and n > 0]
        top = max(g[0] for g in good) if good else 0.0
        best = [g for g in good if g[0] == top]
        table.append((top, fld, best[len(best) // 2], rows))
    table.sort(key=lambda x: -x[0])
    return table, len(clear)


def run(frames, reads):
    print("# %d full-screen water draws journalled%s" % (len(frames), "" if not frames else ", wall %.3f-%.3f, t %.1f-%.1f s" % (
        frames[0]["wall"], frames[-1]["wall"], frames[0]["t"], frames[-1]["t"])))
    if len(frames) < 2:
        return None
    gaps = sorted(b["wall"] - a["wall"] for a, b in zip(frames, frames[1:]))
    print("  frame interval: median %.1f ms, quartiles %.1f / %.1f ms, max %.1f ms" % (
        1000 * gaps[len(gaps) // 2], 1000 * gaps[len(gaps) // 4], 1000 * gaps[3 * len(gaps) // 4], 1000 * gaps[-1]))
    for fld in FIELDS:
        ws = {}
        for f in frames:
            ws[f[fld]] = ws.get(f[fld], 0) + 1
        print("  %s widths: %s" % (fld, ", ".join("%d x%d%s" % (w, n, "" if w in WIDTHS else " (not a bench size)") for w, n in sorted(ws.items()))))
    zs = [r for r in reads if r["kind"] == "z"]
    inwin = sum(1 for r in zs if frames[0]["wall"] <= r["wall"] <= frames[-1]["wall"] + 0.5)
    print("  depth reads inside the journal's window: %d of %d" % (inwin, len(zs)))
    table, nclear = fit(frames, reads)
    for top, fld, (share, lag, n, ok), rows in table:
        print("  field %-3s: best lag %+4d ms, %d of %d matched clear reads at their frame's size (%.2f); clear reads %d" % (
            fld, lag, ok, n, share, nclear))
    top, fld, (share, lag, n, ok), rows = table[0]
    print("  lag scan for %s (lag: matched, agreeing): %s" % (fld, " ".join("%+d:%d/%d" % (l, nn, o) for l, nn, o in rows[::5])))
    m = match(frames, reads, lag)
    sizes = {k: frames[j][fld] for k, j in m.items() if frames[j][fld] in WIDTHS}
    print("  reads given a frame: %d of %d (%d depth), with a bench size: %d" % (
        len(m), len(reads), sum(1 for r in zs if r["name"] in m), len(sizes)))
    per = {}
    for r in zs:
        if r["name"] in m:
            per.setdefault(m[r["name"]], []).append(r["name"])
    print("  frames with depth reads: %d; depth reads per frame: %s" % (len(per), dict(sorted(
        {k: sum(1 for v in per.values() if len(v) == k) for k in {len(v) for v in per.values()}}.items()))))
    return {"field": fld, "lag_ms": lag, "agree": round(share, 4), "clear_matched": n, "frames": len(frames),
            "sizes": sizes, "frame_of": m, "frame_t": {k: frames[j]["t"] for k, j in m.items()}}


if sys.argv[1:2] == ["--selftest"]:
    rng = random.Random(312)
    lines, t, wall, frames_true = [], 205.0, 1792953000.0, []
    for k in range(600):
        w = WIDTHS[(k // 7) % len(WIDTHS)]
        wall += rng.uniform(0.08, 0.12)
        t += 0.1
        frames_true.append((wall, w))
        lines.append("draw journal buf %d (900 dwords) at %d: c0003000 | rt0 0123456700 3328x1872 info 00000000 mask 0000000f | vp %dx%d at 0,0 | ps 11d01d7100 es 0000000000 gs 0000000000 cs 0000000000" % (k, 40 + k, w, w * 9 // 16))
        lines.append("bake draw buf %d at %d: t %.3f wall %d.%03d | win 0,0-3328,1872" % (k, 40 + k, t, int(wall), int(round((wall % 1) * 1000)) % 1000))
        lines.append("draw journal buf %d (900 dwords) at %d: c0003000 | rt0 0123456700 2048x1152 info 0 mask 0 | vp 2048x1152 at 0,0 | ps 11d0375600 es 0 gs 0 cs 0" % (k, 10 + k))
    reads = []
    starts = [f[0] for f in frames_true]
    for i in range(300):
        rw = rng.uniform(starts[5], starts[-5])
        j = bisect.bisect_right(starts, rw - 0.040) - 1
        clear = rng.random() < 0.3
        reads.append({"name": "b%02d.z%d" % (i // 8 + 1, i % 8), "kind": "z", "wall": rw, "clear": clear,
                      "best": frames_true[j][1] if clear else rng.choice(WIDTHS)})
    print("# selftest: 600 frames 80-120 ms apart, vp width changing every 7 frames, rt0 fixed; reads 40 ms after their frame")
    print("# expect field vp, lag ~ +40 ms (the band where the true frame is kept), agreement ~1.00; rt0 low")
    res = run(frames_of(lines), reads)
    print("  -> field %s, lag %+d ms, agree %.2f" % (res["field"], res["lag_ms"], res["agree"]))
    sys.exit(0)
log, rjson, out = sys.argv[1:4]
rj = json.load(open(rjson))
res = run(frames_of(open(log, errors="replace")), rj["reads"])
if res:
    json.dump(res, open(out, "w"), indent=0)
