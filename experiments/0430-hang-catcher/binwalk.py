import sys, struct
d = open(sys.argv[1], "rb").read(); d = list(struct.unpack("<%dI" % (len(d)//4), d))
p = 0; sh = {}
while p < len(d):
    h = d[p]; t = h >> 30
    if t == 3:
        c = (h >> 16) & 0x3fff; ln = 1 if c == 0x3fff else c + 2; op = (h >> 8) & 0xff
    else:
        ln = 1; op = -1
    b = d[p+1:p+ln]
    if op in (0x76, 0x9b) and b:
        o = b[0] & 0xffff
        for k, v in enumerate(b[1:]): sh[o + k] = v
    if op not in (0x10, -1, 0x76):
        extra = ""
        if op in (0x15, 0x16):
            pg = (sh.get(0x20c, 0) | (sh.get(0x20d, 0) & 0xff) << 32) << 8
            extra = " pgm 0x%x ud0-7 %s" % (pg, " ".join("%08x" % sh.get(0x240 + k, 0) for k in range(8)))
        print("%5d op %02x len %3d: %s%s" % (p, op & 0xff, ln, " ".join("%08x" % x for x in d[p:p+min(ln, 8)]), extra))
    elif op == 0x76:
        print("%5d SET_SH_REG 0x%03x x%d: %s" % (p, b[0] & 0xffff, ln - 2, " ".join("%08x" % x for x in b[1:9])))
    p += ln
