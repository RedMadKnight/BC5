#!/usr/bin/env python3
# BC5 experiment 0210: does the cost grow with playing time? Per minute of a session, from the direct journal on stdin
# (LC_ALL=C grep -a '^frame profile: t \|^direct: [0-9]* views\|^submit #' direct.log | trend.py <name>):
# flips/s, frames whose GPU busy exceeds 50 ms (count, max), frames with the game thread outside the host > 0.1 s,
# the host's pinned memory and mapping count at the end of the minute ("direct:" lines carry no time, so they are
# placed at the last frame-profile time seen before them).
import re
import sys

name = sys.argv[1]
pf = re.compile(r"^frame profile: t ([0-9.]+) s, ([0-9.]+) ms since.*?outside ([0-9.]+).*?GPU busy ([0-9.]+) ms")
pd = re.compile(r"^direct: ([0-9]+) views; .*\(([0-9]+), ([0-9.]+) MiB pinned\); maps .*\(([0-9]+)\)")
ps = re.compile(r"mappings ([0-9]+)")
t = 0.0
mins = {}
for line in sys.stdin:
    m = pf.match(line)
    if m:
        t = float(m.group(1))
        k = int(t // 60)
        d = mins.setdefault(k, {"n": 0, "g50": 0, "gmax": 0.0, "out": 0, "pin": None, "maps": None})
        d["n"] += 1
        g = float(m.group(4))
        d["g50"] += g > 50
        d["gmax"] = max(d["gmax"], g)
        d["out"] += float(m.group(3)) > 100
        continue
    m = pd.match(line)
    if m:
        d = mins.setdefault(int(t // 60), {"n": 0, "g50": 0, "gmax": 0.0, "out": 0, "pin": None, "maps": None})
        d["pin"] = float(m.group(3)) / 1024.0
        continue
    if line.startswith("submit #"):
        m = ps.search(line)
        if m:
            d = mins.setdefault(int(t // 60), {"n": 0, "g50": 0, "gmax": 0.0, "out": 0, "pin": None, "maps": None})
            d["maps"] = int(m.group(1))
print("%s, per minute: flips/s | frames GPU>50 ms (max ms) | frames outside>0.1 s | pinned GiB | mappings" % name)
for k in sorted(mins):
    d = mins[k]
    print("  min %2d: %5.1f | %3d (%6.0f) | %3d | %s | %s" % (k, d["n"] / 60.0, d["g50"], d["gmax"], d["out"],
          "%.2f" % d["pin"] if d["pin"] is not None else "-", d["maps"] if d["maps"] is not None else "-"))
