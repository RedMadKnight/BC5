import struct, sys
d = open(sys.argv[1], 'rb').read(); ib = struct.unpack('<%dI' % (len(d)//4), d[:len(d)//4*4])
# packet starts
starts = {}; i = 0
while i < len(ib):
    h = ib[i]; t = h >> 30; n = 1
    if t in (0, 3):
        c = (h >> 16) & 0x3fff; n = 1 if c == 0x3fff else c + 2
    starts[i] = ((h >> 8) & 0xff, n); i += n
pk = sorted(starts)
import bisect
for want in sys.argv[2:]:
    w = int(want, 16)
    for j, v in enumerate(ib):
        if (v & 0xffffff00) == (w & 0xffffff00):
            p = pk[bisect.bisect_right(pk, j) - 1]
            print(want, 'dw', j, 'in pkt', p, 'op 0x%02x len %d' % starts[p], '%08x' % v)
