#!/usr/bin/env python3
# Experiment 0197: per pixel shader, the draws and the meshlet counts (first argument of each single indirect
# draw, as exp 0194's edit journals them) in the draw-journal windows that start at or after a wall-clock time
# (the frozen Photo Mode view). The view is frozen, so every frame is the same; a draw is keyed by its buffer's
# size and offset and counted once (the last value seen), which gives one frame's worth per key.
# usage: python3 ps0197.py <direct.log> <HH:MM:SS> [top]
import collections, datetime, re, sys

WIN = re.compile(r"^draw journal window from buf (\d+): t ([\d.]+) wall (\d+)\.")
DRAW = re.compile(r"^draw journal buf (\d+) \((\d+) dwords\) at (\d+): (\S+).*?\| rt0 (\S+) (\d+)x(\d+) info (\S+) .*?\| ps (\S+) es (\S+)")
ARGS = re.compile(r"^draw journal args buf (\d+) at (\d+): op (\S+) .*? \| \[([0-9a-f]+) ([0-9a-f]+)")
h, m, s = map(int, sys.argv[2].split(":")); t0 = h * 3600 + m * 60 + s
top = int(sys.argv[3]) if len(sys.argv) > 3 else 25
on, keyinfo, draws, val = False, {}, {}, {}
for line in open(sys.argv[1], errors="replace"):
    mm = WIN.match(line)
    if mm:
        w = datetime.datetime.fromtimestamp(int(mm[3])); on = w.hour * 3600 + w.minute * 60 + w.second >= t0
        continue
    if not on: continue
    mm = DRAW.match(line)
    if mm:
        op = (int(mm[4], 16) >> 8) & 0xff
        k = (int(mm[2]), int(mm[3]))
        draws[k] = (f"{op:02x}", mm[9], mm[5], f"{mm[6]}x{mm[7]}")
        keyinfo[(mm[1], mm[3])] = k
        continue
    mm = ARGS.match(line)
    if mm and (mm[1], mm[2]) in keyinfo:
        val[keyinfo[(mm[1], mm[2])]] = int(mm[4], 16)
per = collections.defaultdict(lambda: [0, 0, 0])
for k, (op, ps, rt, sz) in draws.items():
    e = per[(ps, rt, op)]; e[0] += 1
    if k in val: e[1] += 1; e[2] += val[k]
print(f"{len(draws)} distinct draws (buffer size, offset) after {sys.argv[2]}")
for (ps, rt, op), (n, ni, sm) in sorted(per.items(), key=lambda x: -x[1][2])[:top]:
    print(f"  ps {ps} rt0 {rt} op {op}: {n} draws, {ni} indirect, meshlets {sm}")
