#!/usr/bin/env python3
# BC5 exp 0381: J2's clean-start checks over a direct.log: the restore lines, the F679 order (a dcb opening with
# 0x909977100 right after an acb) and the flip-free timing line of that buffer. Register values and counts only.
# usage: python3 j2check0381.py direct.log
import re
import sys

pat = re.compile(r"^\s+(\S+) dispatch op \w+ at (\d+): pgm 0x([0-9a-f]+) ud0-3 (\w+)")
prev = None
n = rl = 0
first = last = None
miss = []
order = []
tmax = 0.0
for line in open(sys.argv[1], errors="replace"):
    if line.startswith("acb state restore"):
        rl += 1
        first = first or line.strip()
        last = line.strip()
        if "left as they are: (no change)" not in line:
            miss.append(line.strip()[-160:])
        continue
    t = re.match(r"timing: t ([0-9.]+) s", line)
    if t:
        tmax = max(tmax, float(t.group(1)))
    m = pat.match(line)
    if not m:
        continue
    n += 1
    k, at, pgm, ud0 = m.group(1), int(m.group(2)), m.group(3), int(m.group(4), 16)
    if k == "dcb" and at < 64 and prev and prev[0].startswith("acb"):
        order.append((pgm, at, hex(ud0), prev[1], hex(prev[2]), tmax))
    prev = (k, pgm, ud0)
print("dispatch lines %d, journal t max %.1f s, restore lines %d" % (n, tmax, rl))
print("first:", (first or "none")[:230])
print("last: ", (last or "none")[:230])
print("missing-register lines:", len(miss), *miss[:6], sep="\n  ")
print("dcbs opening right after an acb:", len(order))
for o in order[:20]:
    print("  pgm 0x%s at %d tracker ud0 %s; acb pgm 0x%s ud0 %s; t %.2f" % o)
