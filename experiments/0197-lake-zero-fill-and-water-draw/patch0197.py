#!/usr/bin/env python3
# Experiment 0197: the share of "flat patch" pixels in the frozen near-lake view of the exp 0194 bench
# (1920x1080 screenshot). Flat patches are lighter and bluer than the lake around them: in the calibration shots
# (exp 0194 runs L5, L6, L8, L10, L12) patch pixels have luma ~54 and blue-minus-red ~44, the water ~36 and ~30,
# rain sparkle is bright but white. Counted inside the window x 300..1900, y 400..680, where the near lake lies.
# usage: python3 patch0197.py <png> [...]
import sys
import numpy as np
from PIL import Image

X0, X1, Y0, Y1 = 300, 1900, 400, 680
for f in sys.argv[1:]:
    a = np.asarray(Image.open(f).convert("RGB")).astype(np.float64)[Y0:Y1, X0:X1]
    luma = a.mean(axis=2)
    blue = a[:, :, 2] - a[:, :, 0]
    patch = (luma > 47) & (blue > 38)
    print(f"{f}: patch {patch.mean() * 100:5.1f} %")
