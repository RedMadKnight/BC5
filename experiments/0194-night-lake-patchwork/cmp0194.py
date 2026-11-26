#!/usr/bin/env python3
# Experiment 0194: compare the draws of two sets of draw-journal windows (by wall-clock range): which
# (packet, pixel shader, colour target, size) combinations appear in set A and not in set B, with counts per window.
# usage: python3 cmp0194.py <direct.log> <A from HH:MM:SS> <A to> <B from> <B to>
import collections, datetime, re, sys

WIN = re.compile(r"^draw journal window from buf (\d+): t ([\d.]+) wall (\d+)\.")
DRAW = re.compile(r"^draw journal buf (\d+) \((\d+) dwords\) at (\d+): (\S+).*?\| rt0 (\S+) (\d+)x(\d+) info (\S+) mask (\S+) \| vp .*? \| ps (\S+) es (\S+) gs (\S+) cs (\S+)")
ARGS = re.compile(r"^draw journal args buf (\d+) at (\d+): .*?\| (\[.*)$")
def sec(s):
    h, m, x = map(int, s.split(":")); return h * 3600 + m * 60 + x
ra, rb = (sec(sys.argv[2]), sec(sys.argv[3])), (sec(sys.argv[4]), sec(sys.argv[5]))
sets = {"A": collections.Counter(), "B": collections.Counter()}
nwin = {"A": 0, "B": 0}
args = {"A": collections.defaultdict(list), "B": collections.defaultdict(list)}
cur, key_of = None, {}
for line in open(sys.argv[1], errors="replace"):
    m = WIN.match(line)
    if m:
        w = datetime.datetime.fromtimestamp(int(m[3])); s = w.hour * 3600 + w.minute * 60 + w.second
        cur = "A" if ra[0] <= s <= ra[1] else "B" if rb[0] <= s <= rb[1] else None
        if cur: nwin[cur] += 1
        continue
    if cur is None: continue
    m = DRAW.match(line)
    if m:
        op = (int(m[4], 16) >> 8) & 0xff
        k = (f"{op:02x}", m[10], m[5], f"{m[6]}x{m[7]}", m[8], m[11] if op not in (0x15, 0x16) else m[13])
        sets[cur][k] += 1; key_of[(m[1], m[3])] = k
        continue
    m = ARGS.match(line)
    if m and (m[1], m[2]) in key_of:
        args[cur][key_of[(m[1], m[2])]].append(m[3][:60])
print(f"windows: A {nwin['A']}, B {nwin['B']}")
print("only or more in A (per window A vs B):")
for k, c in sorted(sets["A"].items(), key=lambda x: -x[1]):
    a, b = c / max(1, nwin["A"]), sets["B"][k] / max(1, nwin["B"])
    if a > b + 0.5:
        ex = args["A"][k][:3]
        print(f"  op {k[0]} ps {k[1]} rt0 {k[2]} {k[3]} info {k[4]} es/cs {k[5]}: {a:.1f} vs {b:.1f}  {' '.join(ex)}")
