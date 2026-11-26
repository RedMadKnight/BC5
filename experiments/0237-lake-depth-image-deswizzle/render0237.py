#!/usr/bin/env python3
# BC5 experiment 0237: render the de-swizzled slot-4 image at given (pipes log2, width, height) as greyscale PNGs
# (log depth, far = black), for viewing on the box side only. Uses deswz0237.py from the same directory.
# usage: python3 -I render0237.py <gs4.bin> <swz0237.json> <out dir> <p:w:h> [...]
import os, sys
import numpy as np
from PIL import Image
here = os.path.dirname(os.path.abspath(sys.argv[0]))
src = open(os.path.join(here, "deswz0237.py")).read().split("print(\"# %s: %d values")[0]
sys.argv = [sys.argv[0], sys.argv[1], sys.argv[2], "", sys.argv[3]] + sys.argv[4:]
exec(compile(src, "deswz0237.py", "exec"))
for spec in sys.argv[5:]:
    p, w, h = map(int, spec.split(":"))
    img = image(p, w, h)
    ld = np.log1p(np.clip(np.nan_to_num(img, nan=0.0), 0, None))
    g = (255 * (1 - ld / max(ld.max(), 1e-6))).astype(np.uint8)
    Image.fromarray(g).save(os.path.join(sys.argv[4], "render-p%d-%dx%d.png" % (p, w, h)))
    print("rendered pipes 2^%d %dx%d" % (p, w, h))
