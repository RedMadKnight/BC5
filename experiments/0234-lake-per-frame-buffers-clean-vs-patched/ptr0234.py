#!/usr/bin/env python3
# exp 0234 probe: in the draw journal, which user-data dwords of the water draws point into the two per-frame buffers
# usage: python3 -I ptr0234.py <direct.log>   (on the box; prints pointers and the first user-data line prefix per stage)
import collections, re, sys
pss = ["11d01ff900", "11d01d7100"]
R = [(0x11e04c0000, 0x20000), (0x11e0c2b000, 0x2000)]
DRAW = re.compile(r"^draw journal buf (\d+) \(\d+ dwords\) at (\d+):.*\| ps (\S+) ")
UD = re.compile(r"^bake ud (ps|gs|es|vs) buf (\d+) at (\d+): (.*)$")
owner, hits, nud, sample = {}, collections.Counter(), collections.Counter(), {}
for line in open(sys.argv[1], errors="replace"):
    m = DRAW.match(line)
    if m:
        if m[3].lower() in pss:
            owner[(m[1], m[2])] = m[3].lower()
        continue
    m = UD.match(line)
    if not m or (m[2], m[3]) not in owner:
        continue
    ps = owner[(m[2], m[3])]
    nud[(ps, m[1])] += 1
    if (ps, m[1]) not in sample:
        sample[(ps, m[1])] = m[4][:200]
    d = [int(x, 16) for x in re.findall(r"\b[0-9a-f]{8}\b", m[4])]
    for k in range(len(d) - 1):
        for lo_hi in ((d[k] | (d[k + 1] & 0xffff) << 32),):
            for b, s in R:
                if b <= lo_hi < b + s:
                    hits[(ps, m[1], k, hex(b), hex(lo_hi - b))] += 1
print("ud lines per shader/stage:", dict(nud))
for k, v in sorted(hits.items()):
    print("  %s %s dword %d -> %s + %s: %d draws" % (k[0], k[1], k[2], k[3], k[4], v))
print("first ud line per shader/stage (prefix):")
for k, v in sample.items():
    print("  %s %s: %s" % (k[0], k[1], v))
