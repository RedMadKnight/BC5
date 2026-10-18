#!/usr/bin/env python3
# Experiment 0157: where the UI layer's list area is transparent in one dump: row bands (y profile in
# 20-px bands with the share of alpha<128 pixels) and the bounding boxes of the transparent runs per band.
# Usage: holes.py <alpha.pgm> [<alpha.pgm> ...]
import sys
from PIL import Image
for f in sys.argv[1:]:
    a = Image.open(f).convert("L"); w, h = a.size
    px = a.load()
    print("==", f.split("/")[-1], "%dx%d" % (w, h))
    band = 20
    for y0 in range(0, h, band):
        n = 0; xs = []
        for y in range(y0, min(h, y0 + band), 4):
            for x in range(0, w, 2):
                if px[x, y] < 128: n += 1; xs.append(x)
        tot = (min(h, y0 + band) - y0 + 3) // 4 * ((w + 1) // 2)
        if n:
            xs.sort(); runs = []; s = xs[0]; p = xs[0]
            for x in xs[1:]:
                if x > p + 16: runs.append((s, p)); s = x
                p = x
            runs.append((s, p))
            print("  y %4d-%4d: transparent %5.1f %%  x-runs: %s" % (y0 + 172, min(h, y0 + band) + 172, 100.0 * n / tot, " ".join("%d-%d" % r for r in runs[:12])))
