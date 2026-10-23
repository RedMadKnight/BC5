#!/usr/bin/env python3
# exp 0234 probe 2: per water draw (PS 0x11d01ff900), the pointer at user-data dwords 28-29 of each stage, in journal order
# usage: python3 -I ptr0234b.py <direct.log>   (on the box)
import collections, re, sys
DRAW = re.compile(r"^draw journal buf (\d+) \(\d+ dwords\) at (\d+):.*\| ps (\S+) ")
UD = re.compile(r"^bake ud (ps|gs|es|vs) buf (\d+) at (\d+): (.*)$")
owner, rows, n = {}, [], 0
for line in open(sys.argv[1], errors="replace"):
    n += 1
    m = DRAW.match(line)
    if m:
        if m[3].lower() == "11d01ff900":
            owner[(m[1], m[2])] = (n, m[1], m[2])
        continue
    m = UD.match(line)
    if not m or (m[2], m[3]) not in owner:
        continue
    d = [int(x, 16) for x in re.findall(r"\b[0-9a-f]{8}\b", m[4])]
    if len(d) > 29:
        rows.append((owner[(m[2], m[3])], m[1], d[28] | (d[29] & 0xffff) << 32, len(d)))
print("%d ud rows; dword counts %s" % (len(rows), sorted(collections.Counter(r[3] for r in rows).items())))
for (ln, buf, at), st, p, nd in rows[:48]:
    print("  line %8d buf %s at %s %s ptr 0x%x" % (ln, buf, at, st, p))
ps = sorted({r[2] for r in rows if r[1] == "ps"})
print("ps pointers: %d distinct, min 0x%x max 0x%x" % (len(ps), ps[0], ps[-1]))
hi = collections.Counter(p >> 16 for p in ps)
print("ps pointer 64-KiB pages:", ", ".join("0x%x:%d" % (k << 16, v) for k, v in sorted(hi.items())))
