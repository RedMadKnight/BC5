#!/usr/bin/env python3
# Experiment 0157: the periodic dumps of the UI layer's list area (rt-<va>-...-t<sec>.ppm with -alpha.pgm):
# per dump, the pixels changed since the previous dump and their box, and over the whole window the share
# of transparent pixels (alpha < 128) and of saturated colour; the same two inside the changed box.
# Usage: layerdiff.py <capture gc dir> <va hex or 'any'> <T0 epoch> <t->wall offset> <flagged shots,...>
import sys, glob, re, os
from PIL import Image, ImageChops
d, va = sys.argv[1], sys.argv[2]
T0, off = float(sys.argv[3]), float(sys.argv[4])
flagged = [int(x) for x in sys.argv[5].split(",")] if len(sys.argv) > 5 and sys.argv[5] else []
pat = "rt-*-t*.ppm" if va == "any" else "rt-%s-*-t*.ppm" % va
fs = sorted(glob.glob(os.path.join(d, pat)), key=lambda f: float(re.findall(r"-t([\d.]+)\.ppm", f)[0]))
print("%d dumps" % len(fs))


def stats(rgb, a, box=None):
    if box is not None:
        rgb = rgb.crop(box); a = a.crop(box) if a is not None else None
    px = rgb.convert("HSV").getdata(); n = float(len(px))
    sat = sum(1 for H, S, V in px if S > 80 and V > 50) / n
    tr = (sum(a.histogram()[:128]) / n) if a is not None else -1.0
    return 100 * sat, 100 * tr


prev = None
for f in fs:
    t = float(re.findall(r"-t([\d.]+)\.ppm", f)[0])
    im = Image.open(f).convert("RGB")
    af = f + "-alpha.pgm"
    a = Image.open(af).convert("L") if os.path.exists(af) else None
    k = int((t + off) // 2)
    marks = [s for s in flagged if k <= s <= k + 1]
    shot = "shot s%d%s" % (k, " FLAGGED s%s" % ",".join(map(str, marks)) if marks else "")
    sat, tr = stats(im, a)
    line = "t %7.2f %-22s whole: saturated %5.2f %% transparent %5.2f %%" % (t, shot, sat, tr)
    if prev is not None:
        diff = ImageChops.difference(im, prev[0]).convert("L").point(lambda v: 255 if v > 8 else 0)
        if a is not None and prev[1] is not None:
            diff = ImageChops.lighter(diff, ImageChops.difference(a, prev[1]).point(lambda v: 255 if v > 8 else 0))
        box = diff.getbbox()
        if box:
            bs, bt = stats(im, a, box)
            line += " | changed %7d px box %s: saturated %5.2f %% transparent %5.2f %%" % (diff.histogram()[255], box, bs, bt)
        else:
            line += " | unchanged"
    print(line)
    prev = (im, a)
