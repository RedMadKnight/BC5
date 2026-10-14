# Minimal PM4 listing of a raw dumped buffer (little-endian dwords): offset, opcode name, body.
import struct, sys
names = {}
for t in ("pm4-opcodes.tsv", "extra-opcodes.tsv"):
    for line in open(sys.path[0] + "/" + t):
        if line.startswith("#") or "\t" not in line: continue
        a, b = line.rstrip("\n").split("\t")[:2]
        names[int(a, 16)] = b
d = open(sys.argv[1], "rb").read(); ib = struct.unpack("<%dI" % (len(d) // 4), d)
i = 0
while i < len(ib):
    h = ib[i]; t = h >> 30; c = (h >> 16) & 0x3fff
    n = 1 if t not in (0, 3) or c == 0x3fff else c + 2
    if t == 3:
        op = (h >> 8) & 0xff
        print("%4d %-28s %s" % (i, names.get(op, "0x%02x" % op), " ".join("%08x" % x for x in ib[i + 1:i + n][:12])))
    else:
        print("%4d type%d %08x" % (i, t, h))
    i += n
