import collections
import re
import sys

lines = open(sys.argv[1], errors="replace").read().splitlines()
t = 0.0
frames = collections.Counter()
events = []
pt = re.compile(r"^timing: t ([0-9.]+) s")
ps = re.compile(r"^timing: t ([0-9.]+) s (\S+) (\d+) dwords: sync( \(lazy\))? ([0-9.]+) ms, hints ([0-9.]+) ms")
for l in lines:
    m = pt.match(l)
    if m:
        t = float(m.group(1))
    if l.startswith("frame profile: t "):
        frames[int(float(l.split()[3]) // 5) * 5] += 1
    m = ps.match(l)
    if m and t > 50 and (float(m.group(5)) > 200 or float(m.group(6)) > 200):
        events.append(f"{t:8.3f} long sync/hints: {l[:120]}")
    if "TIMEOUT" in l or l.startswith("timeout:") or l.startswith("cpu-wait") and ("GIVEN UP" in l or "TIMEOUT" in l):
        events.append(f"{t:8.3f} {l[:150]}")
    if l.startswith("reopen") or "recover" in l[:40]:
        events.append(f"{t:8.3f} {l[:120]}")
print("frames per 5 s:", " ".join(f"{k}:{v}" for k, v in sorted(frames.items())))
for e in events[:40]:
    print(e)
