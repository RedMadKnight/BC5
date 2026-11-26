#!/usr/bin/env python3
# Experiment 0197: a time series of the draw-journal windows from a wall-clock time on: per window, one frame's
# worth of draws (a draw keyed by its buffer's size and offset, the view being frozen), and per pixel shader of
# the G-buffer pass the summed meshlet counts (first argument of each single indirect draw). Shaders whose sum
# changes most across the windows are listed first.
# usage: python3 ts0197.py <direct.log> <HH:MM:SS> [top]
import collections, datetime, re, sys

WIN = re.compile(r"^draw journal window from buf (\d+): t ([\d.]+) wall (\d+)\.")
DRAW = re.compile(r"^draw journal buf (\d+) \((\d+) dwords\) at (\d+): (\S+).*?\| rt0 (\S+) .*?\| ps (\S+) es")
ARGS = re.compile(r"^draw journal args buf (\d+) at (\d+): op (\S+) .*? \| \[([0-9a-f]+) ([0-9a-f]+)")
h, m, s = map(int, sys.argv[2].split(":")); t0 = h * 3600 + m * 60 + s
top = int(sys.argv[3]) if len(sys.argv) > 3 else 12
wins = []
cur = None
for line in open(sys.argv[1], errors="replace"):
    mm = WIN.match(line)
    if mm:
        w = datetime.datetime.fromtimestamp(int(mm[3]))
        cur = None
        if w.hour * 3600 + w.minute * 60 + w.second >= t0:
            cur = dict(wall=w.strftime("%H:%M:%S"), keyps={}, keyof={}, val={})
            wins.append(cur)
        continue
    if cur is None: continue
    mm = DRAW.match(line)
    if mm:
        k = (int(mm[2]), int(mm[3])); cur["keyps"][k] = (mm[6], mm[5]); cur["keyof"][(mm[1], mm[3])] = k
        continue
    mm = ARGS.match(line)
    if mm and (mm[1], mm[2]) in cur["keyof"]:
        cur["val"][cur["keyof"][(mm[1], mm[2])]] = int(mm[4], 16)
series = collections.defaultdict(list)
for w in wins:
    sums = collections.Counter()
    for k, (ps, rt) in w["keyps"].items():
        if k in w["val"]: sums[(ps, rt)] += w["val"][k]
    w["sums"] = sums
keys = set(k for w in wins for k in w["sums"])
def spread(k):
    v = [w["sums"].get(k, 0) for w in wins]
    return max(v) - min(v)
ranked = sorted(keys, key=lambda k: -spread(k))[:top]
print("window   " + " ".join(f"{ps[-6:]}" for ps, rt in ranked))
for w in wins:
    print(f"{w['wall']} " + " ".join(f"{w['sums'].get(k, 0):6d}" for k in ranked))
print("targets: " + " ".join(f"{ps[-6:]}={rt}" for ps, rt in ranked))
