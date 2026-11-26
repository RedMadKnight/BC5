#!/usr/bin/env python3
# BC5 exp 0439 (step 5, the maintainer's "rainbow patches"): finds blocks of a screenshot that look like a rainbow: in a
# 32x32 block (of the game area, the overlays' corners left out) at least NMIN strongly coloured pixels (saturation over
# 0.5, lightness over LMIN: the patches seen on 11-25 are dark streaks) of at least HUES_MIN distinct 30-degree hue bins
# (each with 10 % of them), mean saturation SAT_MIN; a torch or a robe is one hue and does not count. Prints per
# shot the number of such blocks and the strongest ones (x, y, saturation, hue bins), and writes a crop of the first one.
#   rainbow439.py <shot.png> [...]
import colorsys
import sys

from PIL import Image

SAT_MIN, HUES_MIN, B, LMIN, NMIN = 0.5, 3, 32, 0.06, 8  # NMIN: coloured pixels of the 256 sampled (3 %)
for f in sys.argv[1:]:
    im = Image.open(f).convert('RGB')
    W, H = im.size
    small = im.resize((W // 2, H // 2))
    px = small.load()
    w, h = small.size
    hits = []
    for by in range(0, h - B, B):
        for bx in range(0, w - B, B):
            if (by < 60 and (bx < 120 or bx > w - 220)) or (by > h - 120 and bx > w - 220):
                continue  # MangoHud corners and the notification area
            bins = [0] * 12
            sat = 0.0
            n = 0
            for y in range(by, by + B, 2):
                for x in range(bx, bx + B, 2):
                    r, g, b = px[x, y]
                    hh, ll, ss = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
                    if ss > 0.5 and LMIN < ll < 0.9:
                        bins[int(hh * 12) % 12] += 1
                        sat += ss
                        n += 1
            if n < NMIN:
                continue
            hues = sum(1 for c in bins if c >= max(2, 0.10 * n))
            if sat / n >= SAT_MIN and hues >= HUES_MIN:
                hits.append((hues, sat / n, bx * 2, by * 2))
    hits.sort(reverse=True)
    print('%s: %d rainbow-like blocks%s' % (f, len(hits), (': ' + ', '.join('(%d,%d) sat %.2f hues %d' % (x, y, s, k) for k, s, x, y in hits[:4])) if hits else ''))
    if hits:
        _, _, x, y = hits[0]
        im.crop((max(0, x - 96), max(0, y - 96), min(W, x + 160), min(H, y + 160))).resize((512, 512), Image.NEAREST).save(f + '.rainbow.png')
