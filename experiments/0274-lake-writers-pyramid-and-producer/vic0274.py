#!/usr/bin/env python3
# BC5 experiment 0274: do the night lake writers' vertex-stage inputs change between reads, and differently with ray
# tracing on and off? The RT session's reading (2026-10-24): the second BVH tree family (dropped by KYTY_BC5_RT=0,
# which cleared the lake in the maintainer's test 0280) is not known to write these images, but a stray store of theirs
# (F339) could hit them. For each region read by capl0274.sh (the pyramid region 0x11d0880000 and the images at
# 0x1162e60000, 0x848789c000, 0x119975c000), across the reads of one or more runs:
#  - per read: its 32-bit words' md5 (first 12 hex digits), and the number of words that differ from the reference read;
#  - the reference is the first read of the first run given (e.g. the RT-off run);
#  - for each differing read, the differing words' offset span and the 64-KiB blocks they fall in (up to 6), so a change
#    confined to a few blocks (a stray write) can be told from a whole-image update (a legitimate per-frame pass).
# Prints summaries only.
# usage: python3 -I vic0274.py <run tag>=<capture dir> [...]
import hashlib, os, re, sys
import numpy as np

REGIONS = [0x11d0880000, 0x1162e60000, 0x848789c000, 0x119975c000]
runs = [a.split("=", 1) for a in sys.argv[1:]]
ref = {}
for tag, cdir in runs:
    caps = sorted(m[1] for m in (re.match(r"(cap\d+) at ", l) for l in open(os.path.join(cdir, "caps.txt"))) if m)
    print("# %s: %s, %d reads" % (tag, cdir, len(caps)))
    for reg in REGIONS:
        rows = []
        for cap in caps:
            f = os.path.join(cdir, "%s.%x.bin" % (cap, reg))
            if not os.path.exists(f):
                continue
            b = open(f, "rb").read()
            w = np.frombuffer(b[: len(b) // 4 * 4], dtype="<u4")
            if reg not in ref:
                ref[reg] = (tag, cap, w)
            r = ref[reg][2]
            n = min(r.size, w.size)
            d = np.nonzero(r[:n] != w[:n])[0]
            blocks = sorted(set((d * 4 // 65536).tolist()))
            rows.append("%s md5 %s diff %d words%s" % (cap, hashlib.md5(b).hexdigest()[:12], d.size,
                        "" if d.size == 0 else " span +%x..+%x, %d blocks %s" % (d[0] * 4, d[-1] * 4, len(blocks),
                                                                                ",".join("+%x" % (k * 65536) for k in blocks[:6]))))
        print("  region %x (reference %s %s):" % (reg, ref[reg][0], ref[reg][1]))
        for r in rows:
            print("    " + r)
