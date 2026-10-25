#!/usr/bin/env python3
# BC5 experiment 0309: which of the night lake's depth writers reads a ping-pong pair, a history buffer swapped every
# frame? Exp 0307 (F372): the visible patches are one half of a checkerboard of water cells per frame, the halves
# swapping between the two states. Within a run the writers are issued identically in both states (F318-F323, F359),
# and the holes are pixels nothing drew that frame (F299, F333). So the half that is missing is decided GPU-side, from
# data the writers read. A renderer that draws half its cells per frame and fills the other half from the previous
# frame reads its history through a descriptor or pointer whose value alternates between two buffers frame to frame.
# Input: a journal of exp 0251's private binary with _EVERY windows and _PS on the full-screen draw 0x11d01d7100 and the
# depth writers (exp 0283's W283a/W283b), parsed with xy0285.py's line formats and frame rules: a frame is the draws up
# to its full-screen draw within one window; writer draws are keyed by shader and their order from the frame's end
# ("@-1" = that shader's last draw in the frame). Every user-data and table dword of every key (the "bake ud" and
# "bake table" lines: the PS and GS user data and the first 32 dwords of each table they point at) is followed over the
# consecutive frames of each window. A dword scores the share of its triplets (frames f, f+1, f+2 of one window, the
# key present in all three) with v(f) = v(f+2) != v(f+1): 1.0 for a value swapped every frame, about 0 for a constant,
# a counter or a ring of many slots (the per-frame constant pool rotates through ~27 blocks, F293).
# Prints the dwords that score >= MIN (default 0.8) over >= 6 triplets, with their two commonest values and their
# difference; then per key the number of such dwords. Values are descriptors and addresses (counts and offsets only in
# the repo). Runs on the box (stdlib only), on the title's data; read-only.
# usage: python3 -I pp0309.py <direct.log> [MIN]
import collections, re, sys

log = sys.argv[1]
MIN = float(sys.argv[2]) if len(sys.argv) > 2 else 0.8
FS = "11d01d7100"
H = lambda s: [int(x, 16) for x in s.split()]
RE_WIN = re.compile(r"^draw journal window from buf (\d+): t ([\d.]+) wall (\d+)\.(\d+)")
RE_DRAW = re.compile(r"^draw journal buf (\d+) \((\d+) dwords\) at (\d+): ([0-9a-f ]*)\| rt0 .*\| ps ([0-9a-f]+) ")
RE_BAKE = re.compile(r"^bake draw buf (\d+) at (\d+): t ([\d.]+) wall (\d+)\.(\d+)")
RE_UD = re.compile(r"^bake ud (ps|gs) buf (\d+) at (\d+):((?: [0-9a-f]{8})+)")
RE_TAB = re.compile(r"^bake table (ps|gs) ud(\d+) ([0-9a-f]+):((?: [0-9a-f]{8})+)")
draws, by_key, last, win = [], {}, None, -1
for line in open(log, errors="replace"):
    if not line.startswith(("draw journal", "bake ")):
        continue
    m = RE_WIN.match(line)
    if m:
        win += 1
        draws.append({"window": win})
        continue
    m = RE_DRAW.match(line)
    if m:
        d = {"key": (int(m[1]), int(m[3])), "win": win, "ps": m[5].lower(), "ud": {}, "tab": {}}
        draws.append(d)
        by_key[d["key"]] = d
        last = d
        continue
    m = RE_BAKE.match(line)
    if m and (int(m[1]), int(m[2])) in by_key:
        by_key[(int(m[1]), int(m[2]))]["wall"] = int(m[4]) + int(m[5]) / 1000
        continue
    m = RE_UD.match(line)
    if m and (int(m[2]), int(m[3])) in by_key:
        by_key[(int(m[2]), int(m[3]))]["ud"][m[1]] = H(m[4])
        continue
    m = RE_TAB.match(line)
    if m and last is not None:
        last["tab"]["%s%s" % (m[1], m[2])] = H(m[4])
frames, cur = [], []
for d in draws:
    if "window" in d:
        cur = []
        continue
    cur.append(d)
    if d["ps"] == FS and "wall" in d:
        frames.append({"win": d["win"], "fs": d, "writers": cur[:-1]})
        cur = []


def dwords(f):
    out = {}
    for st, u in f["fs"]["ud"].items():
        for i, v in enumerate(u):
            out[("fs", "ud " + st, i)] = v
    for t, u in f["fs"]["tab"].items():
        for i, v in enumerate(u):
            out[("fs", "table " + t, i)] = v
    back = collections.Counter()
    for d in reversed(f["writers"]):
        back[d["ps"]] += 1
        k = "%s@-%d" % (d["ps"], back[d["ps"]])
        for st, u in d["ud"].items():
            for i, v in enumerate(u):
                out[(k, "ud " + st, i)] = v
        for t, u in d["tab"].items():
            for i, v in enumerate(u):
                out[(k, "table " + t, i)] = v
    return out


vals = [dwords(f) for f in frames]
print("# %s: %d windows, %d frames, %d writer draws" % (log, win + 1, len(frames), sum(len(f["writers"]) for f in frames)))
hit, tot, seen = collections.Counter(), collections.Counter(), collections.defaultdict(collections.Counter)
for j in range(len(frames) - 2):
    if not (frames[j]["win"] == frames[j + 1]["win"] == frames[j + 2]["win"]):
        continue
    a, b, c = vals[j], vals[j + 1], vals[j + 2]
    for k in a.keys() & b.keys() & c.keys():
        tot[k] += 1
        if a[k] == c[k] and a[k] != b[k]:
            hit[k] += 1
for v in vals:
    for k, x in v.items():
        seen[k][x] += 1
cands = sorted(((hit[k] / tot[k], tot[k], k) for k in tot if tot[k] >= 6 and hit[k] / tot[k] >= MIN), key=lambda x: (-x[0], x[2]))
print("# dwords alternating with period 2 (score >= %.2f over >= 6 triplets): %d of %d followed" % (MIN, len(cands), len(tot)))
for sc, n, k in cands[:60]:
    (v1, c1), (v2, c2) = (seen[k].most_common(2) + [(0, 0)])[:2]
    print("  %-22s %-12s dw%-2d score %.2f over %d triplets; values %08x x%d / %08x x%d (difference %+x), %d distinct" % (
        k[0], k[1], k[2], sc, n, v1, c1, v2, c2, v2 - v1, len(seen[k])))
per = collections.Counter(k[0] for _, _, k in cands)
print("# per key: alternating dwords %s" % ", ".join("%s %d" % kv for kv in per.most_common(20)))
