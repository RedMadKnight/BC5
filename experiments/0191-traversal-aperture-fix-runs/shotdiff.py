#!/usr/bin/env python3
# BC5 experiment 0191: compare two screenshots of the idle night scene taken at the same second of two runs.
# Prints the mean absolute difference (0-255, luma) over the whole frame and over a 4x4 grid of regions, and the
# share of pixels that differ by more than 24, and writes an amplified difference image (x4) next to <out>.
# The screenshots stay on the box (they are the title's imagery); only these numbers are committed.
# usage: shotdiff.py <a.png> <b.png> <out.png>    (run with the ubuntu distrobox's python3 + PIL)
import sys

from PIL import Image, ImageChops

a = Image.open(sys.argv[1]).convert("L")
b = Image.open(sys.argv[2]).convert("L")
d = ImageChops.difference(a, b)
w, h = d.size
px = d.load()


def stats(x0, y0, x1, y1):
    s = n = big = 0
    for y in range(y0, y1, 2):
        for x in range(x0, x1, 2):
            v = px[x, y]
            s += v
            n += 1
            big += v > 24
    return s / n, 100.0 * big / n


m, big = stats(0, 0, w, h)
print("%s vs %s: mean |diff| %.2f, %.2f %% of pixels > 24" % (sys.argv[1].split("/")[-3], sys.argv[2].split("/")[-3], m, big))
for gy in range(4):
    row = []
    for gx in range(4):
        rm, rb = stats(gx * w // 4, gy * h // 4, (gx + 1) * w // 4, (gy + 1) * h // 4)
        row.append("%5.2f/%5.1f%%" % (rm, rb))
    print("  row %d (top to bottom): %s" % (gy, "  ".join(row)))
d.point(lambda v: min(255, 4 * v)).save(sys.argv[3])
