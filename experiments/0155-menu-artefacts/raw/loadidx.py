#!/usr/bin/env python3
# Experiment 0155: the LOAD_*_REG_INDEX packets (0x9f context, 0x63 sh, 0x64 uconfig) of dumped
# graphics buffers: dword 1 bit 0 (index: 0 = address, 1 = offset from a SET_BASE), the address
# range, data format (dword 3 bit 31: pairs) and count; plus SET_BASE base indices.
import glob, struct, sys, collections, os
d = sys.argv[1]
stat = collections.Counter(); bases = collections.Counter(); ex = {}
for f in sorted(glob.glob(d + "/ib-*-dcb-*.bin"))[:4000]:
    b = open(f, "rb").read(); ib = struct.unpack("<%dI" % (len(b) // 4), b[:len(b) // 4 * 4]); i = 0
    while i < len(ib):
        h = ib[i]; t = h >> 30; c = (h >> 16) & 0x3fff
        n = 1 if t not in (0, 3) or c == 0x3fff else c + 2
        if t == 3 and i + n <= len(ib):
            op = (h >> 8) & 0xff
            if op in (0x9f, 0x63, 0x64) and n >= 5:
                idx = ib[i+1] & 1; addr = (ib[i+1] & ~3) | (ib[i+2] << 32); pairs = ib[i+3] >> 31; cnt = ib[i+4] & 0x3fff
                key = (hex(op), "index %d" % idx, "pairs %d" % pairs, "addr>>32 0x%x" % (addr >> 32), "reg 0x%x" % (ib[i+3] & 0xffff) if not pairs else "pairs", "n %d" % cnt)
                stat[key] += 1; ex.setdefault(key, (os.path.basename(f), i, hex(addr), hex(ib[i+1]), hex(ib[i+2]), hex(ib[i+3]), hex(ib[i+4])))
            elif op == 0x11 and n >= 4:
                bases[(ib[i+1] & 0xf, hex((ib[i+2] | (ib[i+3] << 32)) >> 32))] += 1
        i += n
for k, v in stat.most_common(30): print("%7d %s  e.g. %s" % (v, k, ex[k]))
print("-- SET_BASE (index, addr>>32):", bases.most_common(8))
