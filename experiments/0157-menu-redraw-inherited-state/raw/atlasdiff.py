#!/usr/bin/env python3
# Experiment 0156: the periodic render-target dumps of one surface (rt-<va>-...-t<sec>.ppm) as a timeline:
# per dump, the pixels changed since the previous dump, the bounding box of the change, and in the changed
# region the share of mid-tones (16..239) and of saturated colour (RGBA8 dumps), which separates glyph
# coverage (0 / 255 with thin edges) from picture fragments.
# Usage: atlasdiff.py <capture gc dir> <va hex> [<T0 epoch> <t->wall offset> <flagged shots,...>]
import sys, glob, re, os
from PIL import Image, ImageChops
d, va = sys.argv[1], sys.argv[2]
T0 = float(sys.argv[3]) if len(sys.argv) > 3 else None
off = float(sys.argv[4]) if len(sys.argv) > 4 else 0.0
flagged = [int(x) for x in sys.argv[5].split(",")] if len(sys.argv) > 5 and sys.argv[5] else []
fs = sorted(glob.glob(os.path.join(d, "rt-%s-*-t*.ppm" % va)), key=lambda f: float(re.findall(r"-t([\d.]+)\.ppm", f)[0]))
print("%d dumps of %s" % (len(fs), va))
prev = None
for f in fs:
    t = float(re.findall(r"-t([\d.]+)\.ppm", f)[0])
    im = Image.open(f).convert("RGB")
    shot = ""
    if T0 is not None:
        k = int((t + off) // 2)  # the screenshot taken just before or at this dump
        marks = [s for s in flagged if k <= s <= k + 1]
        shot = "shot s%d%s" % (k, " FLAGGED s%s" % ",".join(map(str, marks)) if marks else "")
    if prev is None:
        hist = im.convert("L").histogram()
        mid = sum(hist[16:240]) / float(sum(hist))
        print("t %7.2f %-22s first dump: %dx%d, non-black %.1f %%, mid-tones %.1f %%" % (t, shot, im.size[0], im.size[1], 100.0 * (1 - hist[0] / float(sum(hist))), 100.0 * mid))
    else:
        diff = ImageChops.difference(im, prev).convert("L").point(lambda v: 255 if v > 8 else 0)
        box = diff.getbbox()
        n = diff.histogram()[255]
        if box:
            reg = im.crop(box); hist = reg.convert("L").histogram(); tot = float(sum(hist))
            mid = sum(hist[16:240]) / tot
            hsv = reg.convert("HSV"); px = list(hsv.getdata()); col = sum(1 for H, S, V in px if S > 80 and V > 50) / float(len(px))
            print("t %7.2f %-22s changed %6d px in box %s (%dx%d): mid-tones %.1f %%, saturated %.1f %%" % (t, shot, n, box, box[2] - box[0], box[3] - box[1], 100 * mid, 100 * col))
        else:
            print("t %7.2f %-22s unchanged" % (t, shot))
    prev = im
