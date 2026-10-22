#!/usr/bin/env python3
# Per dump: waves, FATAL_HALT/TRAPSTS, the PC range per 4-KiB page (program guess), state at sp.
import sys, os; sys.path.insert(0, "/home/kjaniszewski/bc5-work/exp0190")
from wparse import parse
from collections import Counter
for f in sys.argv[1:]:
    ws = parse(f)
    if not ws: print(os.path.basename(f), "0 waves"); continue
    fh = Counter(w.get("STATUS", 0) >> 23 & 1 for w in ws); ts = Counter("%08x" % w.get("TRAPSTS", 0) for w in ws)
    pcs = sorted(set(w["pc"] for w in ws))
    print("%s %d waves FATAL_HALT=%s TRAPSTS=%s PC %x..%x (%d distinct)" % (os.path.basename(f), len(ws), dict(fh), dict(ts), pcs[0], pcs[-1], len(pcs)))
