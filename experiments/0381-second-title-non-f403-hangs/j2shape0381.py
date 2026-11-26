#!/usr/bin/env python3
# BC5 exp 0381: where 0x909977100 runs: each run's time, buffer size, first offset and previous dispatch, and the dcbs
# of 14,000-16,000 dwords. usage: python3 j2shape0381.py direct.log
import re
import sys

pat = re.compile(r"^\s+(\S+) dispatch op \w+ at (\d+): pgm 0x([0-9a-f]+) ud0-3 (\w+)")
tim = re.compile(r"^timing: t ([0-9.]+) s (acb|dcb) (\d+) dwords")
last = (0.0, "?", 0)
prev = None
inrun = False
runs = 0
big = []
for line in open(sys.argv[1], errors="replace"):
    t = tim.match(line)
    if t:
        last = (float(t.group(1)), t.group(2), int(t.group(3)))
        if t.group(2) == "dcb" and 14000 <= last[2] <= 16000:
            big.append(last)
        continue
    m = pat.match(line)
    if not m:
        continue
    k, at, pgm = m.group(1), int(m.group(2)), m.group(3)
    if pgm == "909977100":
        if not inrun:
            runs += 1
            if runs <= 14:
                print("run t %.2f in %s %d dwords at %d; previous %s pgm 0x%s at %d" % (last[0], last[1], last[2], at, prev[0], prev[1], prev[2]))
        inrun = True
    else:
        inrun = False
    prev = (k, pgm, at)
print("runs", runs, "dcbs 14-16k dwords", len(big), [("%.1f" % a, c) for a, b, c in big[:12]])
