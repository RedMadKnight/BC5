#!/usr/bin/env python3
# BC5 exp 0439 (tag vz439): reads the decoder's slot dumps (vz-<k>-w.nv12 / -r.nv12) and prints, per dump, the
# "line noise" of each plane: the mean absolute difference between neighbouring rows against neighbouring columns
# (a film frame is smooth both ways; fine horizontal-line noise raises the row figure far above the column figure).
# The same figures for a screenshot (a .png argument, its luma and its chroma after RGB -> YCbCr). Writes a PNG of each
# dump beside it. PIL only (no numpy). Private data: run on private paths only.
#   vz439read.py <width> <height> <pitch> <dump.nv12 | shot.png> [...]
import sys

from PIL import Image, ImageChops, ImageStat

w, h, pitch = (int(x) for x in sys.argv[1:4])


def noise(p):
    a, b = p.crop((0, 1, p.width, p.height)), p.crop((0, 0, p.width, p.height - 1))
    rows = ImageStat.Stat(ImageChops.difference(a, b)).mean[0]
    a, b = p.crop((1, 0, p.width, p.height)), p.crop((0, 0, p.width - 1, p.height))
    cols = ImageStat.Stat(ImageChops.difference(a, b)).mean[0]
    return rows, cols


for f in sys.argv[4:]:
    if f.endswith('.png'):
        im = Image.open(f).convert('RGB')
        y, cb, cr = im.convert('YCbCr').split()
        print("%s (shot %dx%d): Y rows %.2f cols %.2f | Cb rows %.2f cols %.2f | Cr rows %.2f cols %.2f" % ((f, im.width, im.height) + noise(y) + noise(cb) + noise(cr)))
        continue
    b = open(f, 'rb').read()
    ch = (h + 1) // 2
    if len(b) < pitch * (h + ch):
        print(f, "short:", len(b))
        continue
    y = Image.frombytes('L', (pitch, h), b[:pitch * h]).crop((0, 0, w, h))
    uv = Image.frombytes('LA', (pitch // 2, ch), b[pitch * h:pitch * (h + ch)]).crop((0, 0, w // 2, ch))
    u, v = uv.split()
    pad = b[pitch * h:pitch * (h + ch)]
    padbad = sum(1 for r in range(ch) for c in pad[r * pitch + w:(r + 1) * pitch] if c != 128)
    print("%s: Y rows %.2f cols %.2f | U rows %.2f cols %.2f | V rows %.2f cols %.2f | U mean %.1f V mean %.1f | chroma pad bytes not 128: %d"
          % ((f,) + noise(y) + noise(u) + noise(v) + (ImageStat.Stat(u).mean[0], ImageStat.Stat(v).mean[0], padbad)))
    rgb = Image.merge('YCbCr', (y, u.resize((w, h)), v.resize((w, h)))).convert('RGB')
    rgb.save(f + '.png')
