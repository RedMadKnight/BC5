#!/usr/bin/env python3
# Experiment 0194: for a session of play-water.sh (draw-journal windows every few seconds, screenshots every 5 s),
# list each journal window with its wall time, the nearest screenshot, and its indirect draws: how many, the
# largest vertex and instance counts, and how many the CP check (exp 0057 limits) would skip.
# usage: python3 am0194.py <direct.log> <shots dir>
import datetime, os, re, sys

WIN = re.compile(r"^draw journal window from buf (\d+): t ([\d.]+) wall (\d+)\.(\d+)")
ARGS = re.compile(r"^draw journal args buf (\d+) at (\d+): op (\S+) .*?max count (\d+) max inst (\d+), (\d+) zero, (\d+) over the CP limits")
DRAW = re.compile(r"^draw journal buf (\d+) ")
shots = []
for f in sorted(os.listdir(sys.argv[2])):
    m = re.match(r"(\d\d)(\d\d)(\d\d)\.png$", f)
    if m:
        shots.append((int(m[1]) * 3600 + int(m[2]) * 60 + int(m[3]), f))
wins, cur = [], None
for line in open(sys.argv[1], errors="replace"):
    m = WIN.match(line)
    if m:
        wall = datetime.datetime.fromtimestamp(int(m[3]))
        cur = dict(buf=int(m[1]), t=float(m[2]), wall=wall, draws=0, ind=0, maxv=0, maxi=0, skip=0, zero=0)
        wins.append(cur)
        continue
    if cur is None:
        continue
    if DRAW.match(line):
        cur["draws"] += 1
        continue
    m = ARGS.match(line)
    if m:
        cur["ind"] += 1
        cur["maxv"] = max(cur["maxv"], int(m[4]))
        cur["maxi"] = max(cur["maxi"], int(m[5]))
        cur["zero"] += int(m[6])
        cur["skip"] += int(m[7])
for w in wins:
    s = w["wall"].hour * 3600 + w["wall"].minute * 60 + w["wall"].second
    near = min(shots, key=lambda x: abs(x[0] - s))[1] if shots else "-"
    print(f"buf {w['buf']:6d} t {w['t']:8.3f} {w['wall']:%H:%M:%S} shot {near}: {w['draws']:5d} draws, {w['ind']:4d} indirect, "
          f"max count {w['maxv']}, max inst {w['maxi']}, {w['zero']} zero, {w['skip']} over the CP limits")
