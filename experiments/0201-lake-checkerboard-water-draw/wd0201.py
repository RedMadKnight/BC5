#!/usr/bin/env python3
# Experiment 0201: the water candidate's multi-draws per draw-journal window. For each window (wall time) and each
# DRAW_INDEX_INDIRECT_MULTI / DRAW_INDIRECT_MULTI of the given pixel shader: the packet's count, the count read
# from memory when the packet takes it from there, how many sub-draws exp 0194's edit read, how many of them have
# a zero index or instance count, and the largest index count. Compared with the patch share of the screenshots,
# this tells whether missing water cells are sub-draws whose count went to zero.
# usage: python3 wd0201.py <direct.log> <pixel shader hex> [HH:MM:SS]
import datetime, re, sys

WIN = re.compile(r"^draw journal window from buf (\d+): t ([\d.]+) wall (\d+)\.")
DRAW = re.compile(r"^draw journal buf (\d+) \((\d+) dwords\) at (\d+): (\S+).*?\| ps (\S+) es")
ARGS = re.compile(r"^draw journal args buf (\d+) at (\d+): op (\S+) base1 (\S+) \+0x(\S+) count (\d+) \(dw4 (\S+), count addr (\S+) = (-?\d+)\) stride (\d+) \| max count (\d+) max inst (\d+), (\d+) zero")
ps = sys.argv[2].lower().removeprefix("0x")
t0 = 0
if len(sys.argv) > 3:
    h, m, s = map(int, sys.argv[3].split(":")); t0 = h * 3600 + m * 60 + s
cur, mine = None, set()
rows = []
for line in open(sys.argv[1], errors="replace"):
    mm = WIN.match(line)
    if mm:
        w = datetime.datetime.fromtimestamp(int(mm[3]))
        cur = w.strftime("%H:%M:%S") if w.hour * 3600 + w.minute * 60 + w.second >= t0 else None
        mine = set()
        continue
    if cur is None: continue
    mm = DRAW.match(line)
    if mm and mm[5] == ps:
        mine.add((mm[1], mm[3]))
        continue
    mm = ARGS.match(line)
    if mm and (mm[1], mm[2]) in mine and mm[3] in ("38", "2c"):
        rows.append((cur, mm[1], mm[2], mm[3], int(mm[6]), int(mm[9]), int(mm[11]), int(mm[13])))
last = None
for wall, buf, off, op, count, cmem, maxc, zero in rows:
    if wall != last: print(f"== window {wall}"); last = wall
    print(f"  buf {buf} at {off} op {op}: count {count} (memory {cmem}), {zero} zero sub-draws, max index count {maxc}")
