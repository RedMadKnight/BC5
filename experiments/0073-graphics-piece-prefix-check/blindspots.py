# Opcodes in dumped graphics buffers that the full-state tracker does not model, and register
# writes by other packets (WRITE_DATA / COPY_DATA with a register destination).
import glob, struct, sys, collections
known = {0x68,0x69,0x76,0x9b,0x79,0x7a,0x61,0x5f,0x5e,0x9f,0x63,0x64,0x12,0x11,0x26,0x13,0x2a,0x2f,0x28,0x3f}
ops = collections.Counter(); regw = collections.Counter()
files = sorted(glob.glob(sys.argv[1] + "/ib-*-dcb-*.bin"))
for f in files:
    d = open(f, "rb").read(); ib = struct.unpack("<%dI" % (len(d)//4), d[:len(d)//4*4])
    i = 0
    while i < len(ib):
        h = ib[i]; t = h >> 30; c = (h >> 16) & 0x3fff
        ln = 1 if t not in (0, 3) or c == 0x3fff else c + 2
        if t == 3 and c != 0x3fff and i + ln <= len(ib):
            op = (h >> 8) & 0xff
            if op not in known: ops[op] += 1
            if op == 0x37 and ln >= 4 and ((ib[i+1] >> 8) & 0xf) == 0: regw["WRITE_DATA->reg 0x%x" % (ib[i+2] & 0x3ffff)] += 1
            if op == 0x40 and ln >= 6 and ((ib[i+1] >> 8) & 0xf) == 0: regw["COPY_DATA->reg 0x%x" % (ib[i+4] & 0x3ffff)] += 1
            if op == 0x50 and ln >= 7 and ((ib[i+1] >> 20) & 3) == 0 and (ib[i+6] >> 27) & 1: regw["DMA_DATA->reg (DAS)"] += 1
            if op == 0x77: regw["SET_SH_REG_OFFSET"] += 1
        i += ln
print(len(files), "files")
for op, n in sorted(ops.items(), key=lambda x: -x[1]): print("op 0x%02x %d" % (op, n))
for k, n in regw.most_common(): print(k, n)
