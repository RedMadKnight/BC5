#!/usr/bin/env python3
# Experiment 0157: the layer-crop dumps taken at the fence completion of each UI buffer
# (rt-...-t<sec>-buf<N>-done.ppm + -alpha.pgm): per buffer, in submission order, the share of transparent
# pixels (alpha < 128), the pixels changed since the previous dump, the buffer's draw count and the shot
# that follows (flagged or not). Usage: donedump.py <gc dir> <T0 epoch> <flagged shots,...>
import sys, glob, re, os, collections
from PIL import Image, ImageChops
d, T0 = sys.argv[1], float(sys.argv[2])
flag = set(int(x) for x in sys.argv[3].split(",")) if len(sys.argv) > 3 and sys.argv[3] else set()
wall = {}; ndraws = collections.Counter(); size = {}
for line in open(os.path.join(d, "direct.log"), errors="replace"):
    m = re.match(r"^bake draw buf (\d+) at \d+: t ([\d.]+) wall ([\d.]+)", line)
    if m: wall.setdefault(int(m.group(1)), float(m.group(3)) - T0); continue
    m = re.match(r"^draw journal buf (\d+) \((\d+) dwords\)", line)
    if m: ndraws[int(m.group(1))] += 1; size.setdefault(int(m.group(1)), int(m.group(2)))
fs = glob.glob(os.path.join(d, "rt-*-buf*-done.ppm"))
fs.sort(key=lambda f: int(re.findall(r"-buf(\d+)-done", f)[0]))
print("%d completion dumps" % len(fs))
prev = None
for f in fs:
    b = int(re.findall(r"-buf(\d+)-done", f)[0]); t = float(re.findall(r"-t([\d.]+)-buf", f)[0])
    im = Image.open(f).convert("RGB"); a = Image.open(f + "-alpha.pgm").convert("L")
    n = float(im.size[0] * im.size[1]); tr = 100.0 * sum(a.histogram()[:128]) / n
    w = wall.get(b, 0); k = int(w // 2) + 1; fl = [s for s in (k, k + 1) if s in flag]
    ch = ""
    if prev is not None:
        diff = ImageChops.lighter(ImageChops.difference(im, prev[0]).convert("L"), ImageChops.difference(a, prev[1])).point(lambda v: 255 if v > 8 else 0)
        box = diff.getbbox(); ch = "changed %7d px %s" % (diff.histogram()[255], box) if box else "unchanged"
    print("buf %3d t %7.2f +%7.2f s%-3d %-14s %5s dw %2d draws | transparent %6.2f %% | %s" % (b, t, w, k, ("FLAGGED " + ",".join(map(str, fl))) if fl else "", size.get(b), ndraws.get(b, 0), tr, ch))
    prev = (im, a)
