#!/usr/bin/env python3
"""Per screenshot: share of pixels brighter than a threshold, overall and per horizontal band
(8 bands) and per vertical band (8 bands); prints the shots sorted by time with the band maxima,
so a strip of 3D scene behind a menu stands out. Usage: shotlit.py DIR [threshold]"""
import os
import re
import sys

from PIL import Image

d = sys.argv[1]
thr = int(sys.argv[2]) if len(sys.argv) > 2 else 24
rows = []
for name in os.listdir(d):
    m = re.match(r"s(\d+)\.png$", name)
    if not m:
        continue
    im = Image.open(os.path.join(d, name)).convert("L").resize((240, 135))
    px = im.load()
    w, h = im.size
    lit = [[1 if px[x, y] > thr else 0 for x in range(w)] for y in range(h)]
    total = sum(map(sum, lit)) / (w * h) * 100
    hb = [sum(sum(lit[y]) for y in range(k * h // 8, (k + 1) * h // 8)) / (w * (h // 8)) * 100 for k in range(8)]
    vb = [sum(lit[y][x] for y in range(h) for x in range(k * w // 8, (k + 1) * w // 8)) / (h * (w // 8)) * 100 for k in range(8)]
    rows.append((int(m.group(1)), total, hb, vb))
rows.sort()
for t, total, hb, vb in rows:
    print(f"t {t:3d}: {total:5.1f}% | rows " + " ".join(f"{v:4.0f}" for v in hb) + " | cols " + " ".join(f"{v:4.0f}" for v in vb))
