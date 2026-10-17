#!/usr/bin/env python3
# Experiment 0155: for dumped graphics buffers that hold a DMA_DATA from memory, the waits before
# it: position, label page, whether a packet of the same buffer writes the label (self-wait) or
# not (cross-queue: a compute-queue label), and the DMA's source and destination.
import glob, struct, sys, collections, os
d = sys.argv[1]; shown = collections.Counter()
for f in sorted(glob.glob(d + "/ib-*-dcb-*.bin")):
    b = open(f, "rb").read(); ib = struct.unpack("<%dI" % (len(b) // 4), b[:len(b) // 4 * 4]); i = 0
    writes = set(); events = []
    while i < len(ib):
        h = ib[i]; t = h >> 30; c = (h >> 16) & 0x3fff
        n = 1 if t not in (0, 3) or c == 0x3fff else c + 2
        if t == 3 and i + n <= len(ib):
            op = (h >> 8) & 0xff
            if op == 0x37 and n >= 4 and ((ib[i+1] >> 8) & 0xf) in (1, 2, 5): writes.add((ib[i+2] & ~3) | (ib[i+3] << 32))
            elif op == 0x49 and n >= 6 and ((ib[i+2] >> 29) & 7) != 0: writes.add((ib[i+3] & ~3) | ((ib[i+4] & 0xffff) << 32))
            elif op in (0x3c, 0x93) and n >= 4 and (ib[i+1] >> 4) & 1:
                l = (ib[i+2] & ~3) | ((ib[i+3] & 0xffff) << 32); events.append((i, "wait", l, l in writes))
            elif op == 0x50 and n >= 7 and ((ib[i+1] >> 29) & 3) in (0, 3):
                events.append((i, "dma", ib[i+2] | (ib[i+3] << 32), ib[i+4] | (ib[i+5] << 32), ib[i+6] & 0x3ffffff))
            elif op in (0x15, 0x16): events.append((i, "dispatch"))
        i += n
    dmas = [e for e in events if e[1] == "dma"]
    if not dmas: continue
    key = (len(ib), tuple(e[4] for e in dmas))
    if shown[key] >= 1: continue
    shown[key] += 1
    print("== %s" % os.path.basename(f))
    for e in events:
        if e[1] == "wait": print("  %5d wait  on 0x%x %s" % (e[0], e[2], "self" if e[3] else "CROSS-QUEUE"))
        elif e[1] == "dma": print("  %5d DMA   src 0x%x dst 0x%x %d B" % (e[0], e[2], e[3], e[4]))
        else: print("  %5d dispatch" % e[0])
    if sum(shown.values()) >= 4: break
