#!/usr/bin/env python3
# BC5 experiment 0251: the per-frame HTILE/stencil fill against each frame's render size and the lake's patch level.
# W251a's _FIND hits show the fill: CS 0x11d0288a00 (exp 0094's copy kernel) dispatched with user data 0 = the low dword
# of a size's DB_HTILE_DATA_BASE (F309) and one 1-KiB group per KiB of that size's HTILE + stencil. This script walks
# the journal in order: "draw journal window from buf N: t T wall S.MS" (edit0194.py), "frame profile: t" / "timing: t"
# lines, the full-screen water draw's "draw journal buf ... | rt0 113f230000 WxH ... | ps 11d01d7100" line (one per
# frame) and the "draw journal find: dispatch cs ud0 (VALUE) direct ... cs 11d0288a00 | pkt c0031500 GROUPS ..." lines.
# Per frame (from one full-screen water draw to the next) it prints the frame's size and the fills seen before its
# full-screen draw, flags a frame whose own size's HTILE was not filled since the previous frame, and labels each
# window with the shots around it (bench.txt, exp 0197's metric).
# usage: python3 -I clr0251.py <direct.log> <bench.txt>
import collections, re, sys, time

path, bench = sys.argv[1], sys.argv[2]
# DB_HTILE_DATA_BASE low dword per size: the depth base 0x1129ec0000 plus that size's 64-KiB blocks of depth (F309;
# 2304/2560/2816 confirmed by W251a's bake-db lines).
HT = {"%08x" % ((0x1129ec0000 + (-(-w // 128)) * (-(-(w * 9 // 16) // 128)) * 65536) & 0xffffffff): str(w)
      for w in (1536, 1792, 2048, 2304, 2560, 2816, 3072, 3328, 3584, 3840)}
shots = []
for l in open(bench):
    m = re.match(r"\s*(\d{6})-(ts\d\d)\.png: patch\s+([\d.]+) %", l)
    if m:
        shots.append((m[1], m[2], float(m[3])))
WIN = re.compile(r"^draw journal window from buf (\d+): t ([\d.]+) wall (\d+)\.(\d+)")
FS = re.compile(r"^draw journal buf \d+ \(\d+ dwords\) at \d+:.*\| rt0 113f230000 (\d+)x(\d+) .*\| ps 11d01d7100 ")
FILL = re.compile(r"^draw journal find: dispatch cs ud0 \(([0-9a-f]+)\) direct \S+ \|.*cs 11d0288a00 \| pkt c0031500 ([0-9a-f]+)")
T = re.compile(r"\bt (\d+\.\d+)")
t, win, fills, frames = 0.0, None, [], []
for line in open(path, errors="replace"):
    if line.startswith("timing: t ") or line.startswith("frame profile: t "):
        m = T.search(line)
        if m:
            t = float(m[1])
        continue
    m = WIN.match(line)
    if m:
        hms = time.strftime("%H%M%S", time.localtime(int(m[3])))
        if win is None or win[1] != hms:
            win = (float(m[2]), hms)
        continue
    m = FILL.match(line)
    if m:
        fills.append((HT.get(m[1], m[1]), int(m[2], 16)))
        continue
    m = FS.match(line)
    if m and win is not None:
        frames.append({"t": t, "win": win, "size": m[1], "fills": fills})
        fills = []


def around(hms):
    prev = [s for s in shots if s[0] <= hms]
    nxt = [s for s in shots if s[0] >= hms]
    return (prev[-1] if prev else None), (nxt[0] if nxt else None)


def state(p, n):
    if p and n and p[2] < 5 and n[2] < 5:
        return "clean"
    if p and n and p[2] >= 8 and n[2] >= 8:
        return "patched"
    return "mixed"


print("# %s: %d frames with a full-screen water draw in the journal windows" % (path, len(frames)))
by_state = collections.defaultdict(collections.Counter)
cur = None
for k, f in enumerate(frames):
    if f["win"] != cur:
        cur = f["win"]
        p, n = around(cur[1])
        st = state(p, n)
        print("  window t %.1f wall %s:%s:%s prev %s next %s -> %s" % (cur[0], cur[1][:2], cur[1][2:4], cur[1][4:],
              p and "%s %.1f %%" % (p[1], p[2]), n and "%s %.1f %%" % (n[1], n[2]), st))
    own = f["size"][:4]
    filled = [s for s, g in f["fills"]]
    first = k == 0 or frames[k - 1]["win"] != f["win"]
    flag = "" if own in filled or first else "   <- no fill of its own size since the previous frame"
    by_state[st]["frames"] += 1
    by_state[st]["size " + f["size"]] += 1
    if not first:
        by_state[st]["own fill" if own in filled else "no own fill"] += 1
    by_state[st]["switch" if k and not first and frames[k - 1]["size"] != f["size"] else "same"] += 1
    print("    t %.3f %s fills %s%s" % (f["t"], f["size"] + "x" + "", " ".join("%s(%d)" % x for x in f["fills"]) or "-", flag))
print("per window state:")
for st, c in by_state.items():
    print("  %s: %s" % (st, ", ".join("%s %d" % kv for kv in sorted(c.items()))))
