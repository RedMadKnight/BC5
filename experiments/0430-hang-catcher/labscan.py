import os
import struct
import sys

T = {0x12004b4fc8: 'fc8', 0x12004b3c38: 'c38'}
for fn in sys.argv[1:]:
    d = open(fn, 'rb').read()
    ib = struct.unpack('<%dI' % (len(d) // 4), d)
    q = 0
    print('==', os.path.basename(fn), len(ib))
    while q < len(ib):
        h = ib[q]
        t = h >> 30
        n = 1
        if t in (0, 3):
            c = (h >> 16) & 0x3fff
            n = 1 if c == 0x3fff else c + 2
        op = (h >> 8) & 0xff
        if t == 3 and q + n <= len(ib):
            body = ib[q + 1:q + n]
            for k in range(len(body) - 1):
                a = (body[k] & ~3) | ((body[k + 1] & 0xffff) << 32)
                if a in T:
                    print('  at', q, 'op %02x' % op, 'len', n, T[a], ' '.join('%08x' % x for x in body[:8]))
                    break
        q += n
