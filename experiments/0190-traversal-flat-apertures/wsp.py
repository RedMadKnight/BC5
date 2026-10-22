#!/usr/bin/env python3
# Stack depth (entries above base 0xff84, from the packed stack VGPR hi16) over all lanes, per dump.
import sys, os; sys.path.insert(0, "/home/kjaniszewski/bc5-work/exp0190")
from wparse import parse
from collections import Counter
VAR = {0x11d049aa00: 38, 0x11d04a6000: 38, 0x11d040e200: 8, 0x11d040c900: 8, 0x11d04bb900: 129}
SIZE = {0x11d049aa00: 0xab48, 0x11d04a6000: 0xa9a0, 0x11d040e200: 0x6b54, 0x11d040c900: 0x1438, 0x11d04bb900: 0xa2e4}
for f in sys.argv[1:]:
    ws = parse(f); depth = Counter(); prog = Counter()
    for w in ws:
        p = next((b for b in VAR if b <= w["pc"] < b + SIZE[b]), None)
        if p is None: continue
        prog[p] += 1; r = VAR[p]
        for l in range(32):
            hi = w["vgpr"][r][l] >> 16
            depth[((hi - 0xff84) & 0xffff) // 4] += 1
    if prog: print(os.path.basename(f), {hex(k): v for k, v in prog.items()}, "depth histogram:", dict(sorted(depth.items())))
