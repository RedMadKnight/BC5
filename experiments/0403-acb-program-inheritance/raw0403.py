# Lists PM4 packets of a dumped IB: offset, opcode, body (first N dwords). Structure only.
import struct, sys
d = open(sys.argv[1], 'rb').read(); ib = struct.unpack('<%dI' % (len(d)//4), d[:len(d)//4*4])
lo, hi = int(sys.argv[2]), int(sys.argv[3]); i = 0
while i < len(ib):
    h = ib[i]; t = h >> 30; n = 1
    if t in (0, 3):
        c = (h >> 16) & 0x3fff; n = 1 if c == 0x3fff else c + 2
    if lo <= i <= hi:
        op = (h >> 8) & 0xff
        print('%5d t%d op 0x%02x len %3d | %s' % (i, t, op, n, ' '.join('%08x' % x for x in ib[i+1:i+min(n, 12)])))
    i += n
