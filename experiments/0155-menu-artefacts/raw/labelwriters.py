#!/usr/bin/env python3
# Experiment 0155: for the labels that graphics buffers wait on right before their DMA copies
# (WAIT_REG_MEM/64 with mem_space), who writes them in the dumped buffers: RELEASE_MEM (0x49),
# EVENT_WRITE_EOP (0x47), WRITE_DATA (0x37) to memory, COPY_DATA (0x40), ATOMIC_MEM (0x1e), per kind.
import glob, struct, sys, collections, os
d = sys.argv[1]
waits = collections.Counter(); writers = collections.Counter(); wdetail = {}
def pk(d):
    b = open(d, "rb").read(); return struct.unpack("<%dI" % (len(b) // 4), b[:len(b) // 4 * 4])
files = sorted(glob.glob(d + "/ib-*.bin"))
for f in files:
    kind = os.path.basename(f).split("-")[2]; ib = pk(f); i = 0
    while i < len(ib):
        h = ib[i]; t = h >> 30; c = (h >> 16) & 0x3fff
        n = 1 if t not in (0, 3) or c == 0x3fff else c + 2
        if t == 3 and i + n <= len(ib):
            op = (h >> 8) & 0xff
            if op in (0x3c, 0x93) and n >= 4 and (ib[i + 1] >> 4) & 1:
                label = (ib[i + 2] & ~3) | ((ib[i + 3] & 0xffff) << 32)
                if op == 0x93 and n >= 8: ref = ib[4 + i] | (ib[5 + i] << 32); mask = ib[6 + i] | (ib[7 + i] << 32)
                else: ref = ib[i + 4]; mask = ib[i + 5] if n > 5 else 0
                waits[(kind, label >> 12 << 12, ib[i + 1] & 7)] += 1
                wdetail.setdefault((kind, label >> 12 << 12), (hex(label), hex(ref), hex(mask), os.path.basename(f), i))
            elif op == 0x49 and n >= 6 and ((ib[i + 2] >> 29) & 7) != 0:
                a = (ib[i + 3] & ~3) | ((ib[i + 4] & 0xffff) << 32); writers[(kind, "RELEASE_MEM", a >> 12 << 12)] += 1
            elif op == 0x47 and n >= 4 and ((ib[i + 3] >> 29) & 7) != 0:
                a = (ib[i + 2] & ~3) | ((ib[i + 3] & 0xffff) << 32); writers[(kind, "EVENT_WRITE_EOP", a >> 12 << 12)] += 1
            elif op == 0x37 and n >= 4 and ((ib[i + 1] >> 8) & 0xf) in (1, 2, 5):
                a = (ib[i + 2] & ~3) | (ib[i + 3] << 32); writers[(kind, "WRITE_DATA", a >> 12 << 12)] += 1
            elif op == 0x40 and n >= 6 and ((ib[i + 1] >> 8) & 0xf) in (1, 2, 5):
                a = (ib[i + 4] & ~3) | (ib[i + 5] << 32); writers[(kind, "COPY_DATA", a >> 12 << 12)] += 1
            elif op == 0x1e and n >= 4:
                a = (ib[i + 2] & ~3) | (ib[i + 3] << 32); writers[(kind, "ATOMIC_MEM", a >> 12 << 12)] += 1
        i += n
print("-- wait label pages (kind, page, function): waits; GPU writers to that page by kind/op")
for k, v in waits.most_common(30):
    w = {(wk[0], wk[1]): wv for wk, wv in writers.items() if wk[2] == k[1]}
    print("  %s %s fn %d: %5d waits; writers %s; first %s" % (k[0], hex(k[1]), k[2], v, w if w else "NONE", wdetail[(k[0], k[1])]))
