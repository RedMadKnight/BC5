#!/usr/bin/env python3
# BC5 experiment 0205: pg0205.py's samples against the patch share of the frozen-view shots.
# Prints (1) per sample the tile counts per range (hole / zero / data) and the changes since the previous sample,
# (2) per shot ("HHMMSS-tsNN.png: patch x %" lines of the bench output) the patch share with the nearest sample,
# (3) per range the tile maps of the first and last full sample in the frozen view and how many tiles differ.
# usage: python3 -I ana0205.py <pages.txt> <bench output> [first HH:MM:SS of the frozen view]
import re, sys


def secs(hms):
    h, m, s = (int(x) for x in hms.split(":"))
    return h * 3600 + m * 60 + s


samples = []  # (wall s, wall str, base, counts dict, changes str)
maps = []  # (mono, base, string)
mono_wall = {}
for line in open(sys.argv[1]):
    p = line.split()
    if p[:1] == ["s"]:
        c = {"hole": int(p[5]), "zero": int(p[7]), "data": int(p[9]), "err": int(p[11])}
        samples.append((secs(p[2]), p[2], p[3], c, " ".join(p[13:])))
        mono_wall[p[1]] = secs(p[2])
    elif p[:1] == ["m"]:
        maps.append((p[1], p[2], p[3]))
shots = []
for line in open(sys.argv[2]):
    m = re.match(r"(\d\d)(\d\d)(\d\d)-(ts\d+)\.png: patch\s+([\d.]+) %", line.strip())
    if m:
        shots.append((secs("%s:%s:%s" % m.groups()[:3]), m[4], float(m[5])))
t0 = secs(sys.argv[3]) if len(sys.argv) > 3 else (shots[0][0] - 30 if shots else 0)

print("(1) samples: wall range hole zero data err | changes")
last = {}
for w, ws, base, c, ch in samples:
    key = (c["hole"], c["zero"], c["data"], c["err"])
    if last.get(base) != key or "to. 0 toz 0 tod 0 remap 0" not in ch:
        print("  %s %s %4d %4d %4d %d | %s" % (ws, base, *key, ch))
    last[base] = key
print("(2) shots: name patch | nearest sample per range (hole zero data)")
for w, name, share in shots:
    near = {}
    for sw, ws, base, c, ch in samples:
        if base not in near or abs(sw - w) < abs(near[base][0] - w):
            near[base] = (sw, c)
    print("  %s %5.1f %% | %s" % (name, share, "  ".join(
        "%s %d %d %d" % (b, v[1]["hole"], v[1]["zero"], v[1]["data"]) for b, v in sorted(near.items()))))
print("(3) tile maps in the frozen view (from %d s of the day)" % t0)
for base in sorted({b for _, b, _ in maps}):
    fr = [(mono_wall.get(mo, 0), s) for mo, b, s in maps if b == base and mono_wall.get(mo, 0) >= t0]
    if len(fr) < 2:
        print("  %s: fewer than two maps in the frozen view" % base)
        continue
    (wa, a), (wb, b) = fr[0], fr[-1]
    diff = sum(1 for x, y in zip(a, b) if x != y)
    kinds = {}
    for x, y in zip(a, b):
        if x != y:
            kinds[x + ">" + y] = kinds.get(x + ">" + y, 0) + 1
    print("  %s: %d tiles differ between %d and %d s %s" % (base, diff, wa, wb, kinds))
    for w, s in (fr[0], fr[-1]):
        print("    %d %s" % (w, s))
