#!/usr/bin/env python3
# BC5 exp 0381: every dcb that opens (first dispatch below dword 64) with 0x909977100: its time, size and tracker ud0,
# the previous dispatch line and the previous acb lines in journal order. usage: python3 j2job0381.py direct.log
import re
import sys

pat = re.compile(r"^\s+(\S+) dispatch op \w+ at (\d+): pgm 0x([0-9a-f]+) ud0-3 (\w+)")
tim = re.compile(r"^timing: t ([0-9.]+) s (acb|dcb) (\d+) dwords")
prev = None
last_acb_t = None
last = None
n = 0
for line in open(sys.argv[1], errors="replace"):
    t = tim.match(line)
    if t:
        last = (float(t.group(1)), t.group(2), int(t.group(3)))
        if t.group(2) == "acb":
            last_acb_t = float(t.group(1))
        continue
    m = pat.match(line)
    if not m:
        continue
    k, at, pgm, ud0 = m.group(1), int(m.group(2)), m.group(3), int(m.group(4), 16)
    if k == "dcb" and at < 64 and pgm == "909977100" and (prev is None or prev[0] != "dcb" or prev[3] >= at):
        n += 1
        print("t %.3f %s %d dwords at %d ud0 %s; previous %s pgm 0x%s at %d ud0 %s; last acb timing line t %s" % (last[0], last[1], last[2], at, hex(ud0), prev[0], prev[1], prev[3], hex(prev[2]), last_acb_t))
    prev = (k, pgm, ud0, at)
print("openers", n)
