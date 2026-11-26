#!/usr/bin/env python3
# For every dcb dump: classify WAIT_REG_MEM (0x3c) and WAIT_REG_MEM64 (0x93) targets as
# "self" (written earlier in the same DCB by WRITE_DATA/RELEASE_MEM/ATOMIC_MEM), "guest"
# (guest window, written elsewhere) or "host" (outside the guest window, e.g. KytyPlus heap).
import collections, os, re, struct, sys

d = sys.argv[1]
cls = collections.Counter()
examples = collections.defaultdict(set)
for name in sorted(os.listdir(d)):
    if not re.match(r'^\d{6}-dcb\.bin$', name):
        continue
    data = open(os.path.join(d, name), 'rb').read()
    w = struct.unpack('<%dI' % (len(data) // 4), data)
    written = set()
    i = 0
    while i < len(w):
        h = w[i]; t = h >> 30; cnt = (h >> 16) & 0x3fff
        if t != 3:
            i += (cnt + 2 if t == 0 else 1); continue
        op = (h >> 8) & 0xff; n = 1 if cnt == 0x3fff else cnt + 2
        p = w[i:i + n]
        if op == 0x37 and n >= 4 and ((p[1] >> 8) & 0xf) in (1, 2, 5):
            written.add((p[2] & ~3) | ((p[3] & 0xffff) << 32))
        elif op == 0x49 and n >= 6:
            written.add((p[3] & ~3) | ((p[4] & 0xffff) << 32))
        elif op == 0x1e and n >= 4:
            written.add((p[2] & ~3) | ((p[3] & 0xffff) << 32))
        elif op in (0x3c, 0x93) and n >= 4:
            mem = (p[1] >> 4) & 1
            a = (p[2] & ~3) | ((p[3] & 0xffff) << 32)
            fn = p[1] & 7
            if not mem:
                k = 'reg'
            elif a in written:
                k = 'self'
            elif 0x40000 <= a <= 0xfbffffffff:
                k = 'guest'
            else:
                k = 'host'
            cls[(op, k, fn)] += 1
            if len(examples[(op, k)]) < 4:
                examples[(op, k)].add(hex(a))
        i += n
for (op, k, fn), c in sorted(cls.items()):
    print('op %02x %-5s fn %d: %5d   e.g. %s' % (op, k, fn, c, ' '.join(sorted(examples[(op, k)]))))
