#!/usr/bin/env python3
# Compute-queue IB survey over a capture's NNNNNN-ib1.bin dumps: opcodes, SET_SH_REG / SET_UCONFIG /
# SET_CONTEXT register offsets, EVENT_WRITE types, RELEASE_MEM event/index, DMA_DATA control words.
import collections, os, re, struct, sys

d = sys.argv[1]
ops = collections.Counter(); sh = collections.Counter(); uc = collections.Counter(); ctx = collections.Counter()
ev = collections.Counter(); rel = collections.Counter(); dma = collections.Counter(); hdrflags = collections.Counter()
sizes = []
first = None
for name in sorted(os.listdir(d)):
    if not re.match(r'^\d{6}-ib1\.bin$', name):
        continue
    data = open(os.path.join(d, name), 'rb').read()
    w = struct.unpack('<%dI' % (len(data) // 4), data)
    sizes.append(len(w))
    if first is None and len(w) > 500:
        first = (name, len(w))
    i = 0
    while i < len(w):
        h = w[i]; t = h >> 30; cnt = (h >> 16) & 0x3fff
        if t != 3:
            i += (cnt + 2 if t == 0 else 1); ops['t%d' % t] += 1; continue
        op = (h >> 8) & 0xff; n = 1 if cnt == 0x3fff else cnt + 2
        p = w[i:i + n]
        ops[op] += 1
        hdrflags[h & 0xff] += 1
        if op == 0x76 and n >= 3:
            for k in range(n - 2): sh[0x2c00 + (p[1] & 0xffff) + k] += 1
        elif op == 0x79 and n >= 3:
            for k in range(n - 2): uc[0xc000 + (p[1] & 0xffff) + k] += 1
        elif op == 0x69 and n >= 3:
            for k in range(n - 2): ctx[0xa000 + (p[1] & 0xffff) + k] += 1
        elif op == 0x46 and n >= 2:
            ev[(p[1] & 0x3f, (p[1] >> 8) & 0xf, n)] += 1
        elif op == 0x49 and n >= 3:
            rel[(p[1] & 0x3f, (p[1] >> 8) & 0xf, p[2] >> 29, (p[2] >> 16) & 3)] += 1
        elif op == 0x50 and n >= 7:
            dma[(p[1], p[6] >> 26)] += 1
        i += n
print('ib1 dumps: %d, sizes min/med/max %d/%d/%d, first big: %s' % (len(sizes), min(sizes), sorted(sizes)[len(sizes)//2], max(sizes), first))
print('ops:', ' '.join('%s:%d' % (o if isinstance(o, str) else '%02x' % o, c) for o, c in ops.most_common()))
print('hdr low byte:', dict(hdrflags))
print('SH regs (%d distinct):' % len(sh), ' '.join('%x:%d' % (r, c) for r, c in sorted(sh.items())))
print('UCONFIG regs:', ' '.join('%x:%d' % (r, c) for r, c in sorted(uc.items())))
print('CTX regs:', ' '.join('%x:%d' % (r, c) for r, c in sorted(ctx.items())))
print('EVENT_WRITE (type,index,len):', dict(ev))
print('RELEASE_MEM (type,index,data_sel,dst_sel):', dict(rel))
print('DMA_DATA (control, count_hi):', dict(dma))
