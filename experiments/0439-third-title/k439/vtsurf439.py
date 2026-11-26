#!/usr/bin/env python3
# BC5 exp 0439 (tag vt439): which surface of a dumped frame (sr439b capture dir) first carries the rainbow colours. For
# every surface file whose format can be decoded as colour (index.tsv kind: u8x4, u10x3, r11g11b10f, f16 with 4 or 2
# channels by bytes per pixel), a sample of up to 200,000 pixels is decoded and counted for saturated violet-to-magenta
# (violet439.py's rule after a simple tone map for float formats: v / (1 + v)), independent of the tiling (a count needs
# no pixel order). Prints the surfaces in first-op order with their counts per 10,000 sampled pixels.
#   vtsurf439.py <capture dir> [--min N]
import colorsys
import csv
import os
import struct
import sys

d = sys.argv[1]
mn = float(sys.argv[sys.argv.index('--min') + 1]) if '--min' in sys.argv else 0.0
rows = list(csv.DictReader(open(os.path.join(d, 'index.tsv')), delimiter='\t'))
out = []


def half(h):
    return struct.unpack('<e', struct.pack('<H', h))[0]


def f11(v, mbits):
    e = v >> mbits
    m = v & ((1 << mbits) - 1)
    if e == 0:
        return m / (1 << mbits) * 2 ** -14
    if e == 31:
        return float('nan')
    return (1 + m / (1 << mbits)) * 2 ** (e - 15)


for r in rows:
    f = r.get('file', '-')
    if f in ('-', '') or not os.path.exists(os.path.join(d, f)):
        continue
    w, h = int(r['w']), int(r['h'])
    if w * h == 0:
        continue
    data = open(os.path.join(d, f), 'rb').read()
    bpp = len(data) // (w * h) if w * h else 0
    kind = r['kind']
    step = max(1, (w * h) // 200000)
    n = v = 0
    for i in range(0, w * h, step):
        o = i * bpp
        if o + bpp > len(data):
            break
        try:
            if kind == 'u8x4' and bpp >= 4:
                R, G, B = data[o] / 255, data[o + 1] / 255, data[o + 2] / 255
            elif kind == 'u10x3' and bpp >= 4:
                u = int.from_bytes(data[o:o + 4], 'little')
                R, G, B = (u & 1023) / 1023, ((u >> 10) & 1023) / 1023, ((u >> 20) & 1023) / 1023
            elif kind == 'r11g11b10f' and bpp >= 4:
                u = int.from_bytes(data[o:o + 4], 'little')
                R, G, B = f11(u & 0x7ff, 6), f11((u >> 11) & 0x7ff, 6), f11((u >> 22) & 0x3ff, 5)
                R, G, B = (x / (1 + x) if x == x and x >= 0 else 0 for x in (R, G, B))
            elif kind == 'f16' and bpp >= 6:
                R, G, B = (half(int.from_bytes(data[o + 2 * k:o + 2 * k + 2], 'little')) for k in range(3))
                R, G, B = (x / (1 + x) if x == x and x >= 0 and x != float('inf') else 0 for x in (R, G, B))
            else:
                break
        except (OverflowError, ValueError):
            continue
        n += 1
        hh, ll, ss = colorsys.rgb_to_hls(R, G, B)
        if ss > 0.4 and 0.1 < ll < 0.9 and 235 <= hh * 360 <= 330:
            v += 1
    if n:
        out.append((int(r['first_op']), r['id'], r['base'], kind, w, h, bpp, 10000.0 * v / n, n))
out.sort()
for fo, i, b, k, w, h, bpp, c, n in out:
    if c >= mn:
        print('first op %6d  #%s %s %s %dx%d %d B/px: violet %.1f per 10k (%d sampled)' % (fo, i, b, k, w, h, bpp, c, n))
