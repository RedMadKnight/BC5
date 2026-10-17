#!/usr/bin/env python3
# Experiment 0155: in dumped command buffers (ib-<submission>-<kind>-<dwords>.bin), the order of
# memory waits (WAIT_REG_MEM 0x3c / WAIT_REG_MEM64 0x93 with mem_space) and DMA_DATA (0x50) copies
# from memory (SRC_SEL 0/3): is a DMA source ever behind a wait in the same buffer, and which
# destinations repeat? Prints per kind: buffers, waits, DMAs, DMAs behind a wait; then the
# destinations (MiB) of DMAs behind a wait, and a few examples.
import glob, struct, sys, collections, os
d = sys.argv[1]
stats = collections.Counter(); behind = collections.Counter(); ex = []
dst_all = collections.Counter(); src_pages = collections.Counter()
for f in sorted(glob.glob(d + "/ib-*.bin")):
    name = os.path.basename(f); parts = name[:-4].split("-"); sub, kind = int(parts[1]), parts[2]
    b = open(f, "rb").read(); ib = struct.unpack("<%dI" % (len(b) // 4), b[:len(b) // 4 * 4])
    stats[(kind, "buffers")] += 1
    i = 0; waits = []
    while i < len(ib):
        h = ib[i]; t = h >> 30; c = (h >> 16) & 0x3fff
        n = 1 if t not in (0, 3) or c == 0x3fff else c + 2
        if t == 3 and i + n <= len(ib):
            op = (h >> 8) & 0xff
            if op in (0x3c, 0x93) and n >= 4 and (ib[i + 1] >> 4) & 1:
                label = (ib[i + 2] & ~3) | ((ib[i + 3] & 0xffff) << 32)
                waits.append((i, label, ib[i + 1] & 7)); stats[(kind, "mem waits")] += 1
            elif op == 0x50 and n >= 7:
                ctl, slo, shi, dlo, dhi, cmd = ib[i + 1:i + 7]
                src_sel = (ctl >> 29) & 3; dst_sel = (ctl >> 20) & 3
                if src_sel in (0, 3):
                    src = slo | (shi << 32); dst = dlo | (dhi << 32); cnt = cmd & 0x3ffffff
                    stats[(kind, "DMA from memory")] += 1
                    dst_all[(kind, hex(dst >> 20), cnt)] += 1
                    if waits:
                        stats[(kind, "DMA behind a wait")] += 1
                        behind[(kind, hex(dst >> 20), cnt)] += 1
                        if len(ex) < 12: ex.append((name, "wait at %d on 0x%x fn %d" % waits[-1], "dma at %d src 0x%x dst 0x%x %d B" % (i, src, dst, cnt)))
        i += n
for k in sorted(stats): print("%-6s %-20s %d" % (k[0], k[1], stats[k]))
print("-- DMA destinations (kind, MiB, bytes): all / behind a wait")
for k, v in dst_all.most_common(25): print("  %s %s %7d B: %5d / %5d" % (k[0], k[1], k[2], v, behind.get(k, 0)))
print("-- examples of DMA behind a wait")
for e in ex: print("  ", e)
