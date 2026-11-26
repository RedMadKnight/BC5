#!/usr/bin/env python3
# BC5 exp 0439 (step 5): the "rainbow patches" seen on 11-25 (RP t90s) are streaks of saturated blue-violet, magenta, red
# and green over dark ground. This counts, per shot, the pixels of the game area (the overlay corners left out) with
# saturation > 0.4, lightness 0.1-0.9 and hue 235-330 degrees (violet to magenta: nothing in the title's night village
# has that colour), on a 2x subsample; and writes the count per 1,000 pixels with the bounding box of the largest cluster.
#   violet439.py <shot.png> [...]
import colorsys
import sys

from PIL import Image

for f in sys.argv[1:]:
    im = Image.open(f).convert('RGB')
    W, H = im.size
    s = im.resize((W // 2, H // 2))
    px = s.load()
    w, h = s.size
    n = tot = 0
    cols = {}
    for y in range(0, h):
        for x in range(0, w):
            if (y < 60 and (x < 120 or x > w - 220)) or (y > h - 120 and x > w - 220):
                continue
            tot += 1
            r, g, b = px[x, y]
            hh, ll, ss = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
            if ss > 0.4 and 0.1 < ll < 0.9 and 235 <= hh * 360 <= 330:
                n += 1
                cols[(x // 40, y // 40)] = cols.get((x // 40, y // 40), 0) + 1
    top = sorted(cols.items(), key=lambda kv: -kv[1])[:3]
    print('%s: violet-magenta %.2f per 1000 px (%d)%s' % (f, 1000.0 * n / tot, n, ('; densest 80x80 cells at ' + ', '.join('(%d,%d) %d' % (k[0] * 80, k[1] * 80, v) for k, v in top)) if top else ''))
