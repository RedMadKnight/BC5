#!/usr/bin/env python3
# BC5 experiment 0295 (exp 0293's cnt0293.py, plus the frames' period): do the night lake writers' argument steps (F350, F352) follow the changing group counts of the
# compute passes that bind the argument buffers (F355)? CS 0x11d0375600 is dispatched with CPU-set group counts that
# change between frames in the frozen view (DISPATCH_DIRECT 97-102 or 1105-1111 groups). Inputs: the run's draw journal
# (exp 0283's switches plus _FIND on the argument bases' low dwords, as exp 0292's W292a; within a journal window every
# dispatch whose user data or first-level table holds one of them is journalled, "draw journal find: dispatch ... cs
# C | pkt c0031500 X Y Z" followed by "find ud cs C t T: ..." with the journal time) and a capa0287.py-style capture
# (argument reads aK just before each depth read; their ranges in the times lines).
# Per frame (the draws up to a full-screen draw 0x11d01d7100 within one window, timed by its "bake draw" line), the
# group counts (X*Y*Z) of each candidate pass's dispatches since the previous full-screen draw. The journal time is
# turned into wall clock by the median offset of the "bake draw" lines (wall - t). Then for each pair of consecutive
# argument reads of a burst: whether any argument record changed, and whether any candidate pass's per-frame counts
# changed between the frames the two reads show (the latest frame whose full-screen draw came at least L ms before each
# read; L = 50 ms, exps 0283/0287 found 45-60). Prints per window the frames' count signatures (letters per pass), the
# table "arguments changed" against "counts changed" per pass, and the reads with no frame in a window. Summaries only.
# Exp 0295: also the period of the frames, from the full-screen draws' journal times within each window (F357 inferred
# about 120 ms from runs of identical depth reads and did not measure it).
# Runs on the box (stdlib only), on the title's data.
# usage: python3 -I cnt0295.py <direct.log> <capture dir> [L ms]
import collections, glob, os, re, statistics, struct, sys

log, cdir = sys.argv[1], sys.argv[2]
L = float(sys.argv[3]) / 1000 if len(sys.argv) > 3 else 0.05
FS = "11d01d7100"
CANDS = ["11d0375600", "11d0376b00", "11d0415700", "11d04f0c00", "11d0288a00"]
RE_WIN = re.compile(r"^draw journal window from buf (\d+): t ([\d.]+) wall (\d+)\.(\d+)")
RE_DRAW = re.compile(r"^draw journal buf (\d+) \((\d+) dwords\) at (\d+): .*\| ps ([0-9a-f]+) ")
RE_BAKE = re.compile(r"^bake draw buf (\d+) at (\d+): t ([\d.]+) wall (\d+)\.(\d+)")
RE_FD = re.compile(r"^draw journal find: dispatch cs .* cs ([0-9a-f]+) \| pkt ([0-9a-f]+) ([0-9a-f]+) ([0-9a-f]+) ([0-9a-f]+)")
RE_FU = re.compile(r"^find ud cs ([0-9a-f]+) t ([\d.]+):")
RE_ARGS = re.compile(r"^draw journal args buf \d+ at \d+: op \S+ base1 ([0-9a-f]+) \+0x([0-9a-f]+)")
win, pend_draw, fs_draws, offsets, pend_disp, disps, recs = -1, {}, [], [], None, [], set()
for l in open(log, errors="replace"):
    if not (l.startswith("draw journal") or l.startswith("bake draw") or l.startswith("find ud cs")):
        continue
    m = RE_WIN.match(l)
    if m:
        win += 1
        continue
    m = RE_DRAW.match(l)
    if m:
        if m[4].lower() == FS:
            pend_draw[(m[1], m[3])] = win
        continue
    m = RE_BAKE.match(l)
    if m:
        t, w = float(m[3]), int(m[4]) + int(m[5]) / 1000
        offsets.append(w - t)
        if (m[1], m[2]) in pend_draw:
            fs_draws.append((pend_draw.pop((m[1], m[2])), t, w))
        continue
    m = RE_FD.match(l)
    if m:
        x, y, z = (int(v, 16) for v in m.groups()[2:5])
        pend_disp = (m[1], x * y * z if m[2].lower() == "c0031500" else -1, win)
        continue
    m = RE_FU.match(l)
    if m and pend_disp and m[1] == pend_disp[0]:
        disps.append((pend_disp[0], pend_disp[1], pend_disp[2], float(m[2])))
        pend_disp = None
        continue
    m = RE_ARGS.match(l)
    if m:
        recs.add(int(m[1], 16) + int(m[2], 16))
off = statistics.median(offsets) if offsets else 0.0
fs_draws.sort(key=lambda x: x[1])
print("# %s: %d windows, %d full-screen draws, %d candidate-pass dispatch hits, %d argument records; wall - t = %.3f s" % (
    log, win + 1, len(fs_draws), sum(1 for d in disps if d[0] in CANDS), len(recs), off))
# frames: per window, the dispatches since the previous full-screen draw of that window
frames = []
for i, (w_, t, wall) in enumerate(fs_draws):
    prev = fs_draws[i - 1][1] if i > 0 and fs_draws[i - 1][0] == w_ else None
    sig = {}
    for c in CANDS:
        sig[c] = tuple(sorted(g for cs, g, dw, dt in disps if cs == c and dw == w_ and dt <= t and (prev is None or dt > prev)))
    frames.append({"win": w_, "t": t, "wall": wall, "sig": sig, "first": prev is None})
letters = {c: {} for c in CANDS}
print("# per window: frame signatures, one letter per distinct tuple of group counts, per pass (%s)" % " / ".join(CANDS))
for w_ in sorted({f["win"] for f in frames}):
    fr = [f for f in frames if f["win"] == w_]
    cols = []
    for c in CANDS:
        s = ""
        for f in fr:
            key = f["sig"][c]
            if key not in letters[c]:
                letters[c][key] = "abcdefghijklmnopqrstuvwxyz"[len(letters[c]) % 26]
            s += letters[c][key]
        cols.append(s)
    print("  w%02d: %s" % (w_, " | ".join(cols)))
# exp 0295: the frames' period, between consecutive full-screen draws of one window (journal time, as submitted)
gaps = sorted((f["t"] - g["t"]) * 1000 for g, f in zip(frames, frames[1:]) if f["win"] == g["win"])
if gaps:
    q = lambda p: gaps[min(len(gaps) - 1, int(p * len(gaps)))]
    print("# frame period (ms) over %d consecutive full-screen draws of one window: median %.1f, quartiles %.1f-%.1f, range %.1f-%.1f" % (
        len(gaps), q(0.5), q(0.25), q(0.75), gaps[0], gaps[-1]))
for c in CANDS:
    if letters[c]:
        print("  %s: %s" % (c, "; ".join("%s=%s" % (v, ",".join(map(str, k)) or "-") for k, v in sorted(letters[c].items(), key=lambda kv: kv[1])[:12])))
# argument reads
areads = []
for tf in sorted(glob.glob(os.path.join(cdir, "b*.times.txt"))):
    b = os.path.basename(tf).split(".")[0]
    for l in open(tf):
        m = re.match(r"(a\d+) wall ([\d.]+) .* ranges (.*)$", l)
        if not m:
            continue
        data = open(os.path.join(cdir, "%s.%s.bin" % (b, m[1])), "rb").read()
        vals, pos = {}, 0
        for part in m[3].split():
            a, n = (int(x, 16) for x in part.split(":"))
            for r in recs:
                if a <= r and r + 16 <= a + n:
                    vals[r] = struct.unpack_from("<4I", data, pos + r - a)
            pos += n
        areads.append((b, int(m[1][1:]), float(m[2]), vals))
areads.sort(key=lambda x: (x[0], x[1]))


def frame_at(wall):
    j = None
    for i, f in enumerate(frames):
        if f["wall"] <= wall - L:
            j = i
    if j is None or wall - L - frames[j]["wall"] > 0.25:
        return None
    return j


tab = {c: collections.Counter() for c in CANDS}
none = 0
for (b1, k1, w1, v1), (b2, k2, w2, v2) in zip(areads, areads[1:]):
    if b1 != b2 or k2 != k1 + 1:
        continue
    j1, j2 = frame_at(w1), frame_at(w2)
    if j1 is None or j2 is None or frames[j1]["win"] != frames[j2]["win"]:
        none += 1
        continue
    achanged = any(v1.get(r) != v2.get(r) for r in recs if r in v1 and r in v2)
    for c in CANDS:
        cchanged = any(frames[j]["sig"][c] != frames[j + 1]["sig"][c] for j in range(j1, j2))
        tab[c][(achanged, cchanged)] += 1
print("# consecutive argument reads matched to frames of one window (L %.0f ms); %d pairs had no frame" % (L * 1000, none))
for c in CANDS:
    t = tab[c]
    print("  %s: arguments changed and counts changed %d; arguments only %d; counts only %d; neither %d" % (
        c, t[(True, True)], t[(True, False)], t[(False, True)], t[(False, False)]))
# Are the argument steps just new frames? For several lags L, each pair of consecutive argument reads against whether
# a full-screen draw (a new frame of the window) falls between the frames the two reads show.
print("# arguments changed against a new frame between the two reads' frames, by lag L (ms)")
for lag in (0, 25, 50, 75, 100):
    L = lag / 1000
    t2 = collections.Counter()
    for (b1, k1, w1, v1), (b2, k2, w2, v2) in zip(areads, areads[1:]):
        if b1 != b2 or k2 != k1 + 1:
            continue
        j1, j2 = frame_at(w1), frame_at(w2)
        if j1 is None or j2 is None or frames[j1]["win"] != frames[j2]["win"]:
            continue
        achanged = any(v1.get(r) != v2.get(r) for r in recs if r in v1 and r in v2)
        t2[(achanged, j2 > j1)] += 1
    print("  L %3d: changed with a new frame %d; changed within one frame %d; new frame, unchanged %d; neither %d" % (
        lag, t2[(True, True)], t2[(True, False)], t2[(False, True)], t2[(False, False)]))
