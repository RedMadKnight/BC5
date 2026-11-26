#!/usr/bin/env python3
# Experiment 0129: share of colourful (scene) pixels in the menu list area of each screenshot
# (x < 55 % of the width, y 8-70 %); menu text and bars are grey or white on black.
import sys, glob, re
from PIL import Image
for f in sorted(sys.argv[1:], key=lambda f: int(re.findall(r"-(\d+)\.png", f)[0])):
    im = Image.open(f).convert("HSV")
    w, h = im.size
    box = im.crop((0, int(h * 0.08), int(w * 0.55), int(h * 0.70))).resize((440, 248))
    px = list(box.getdata())
    n = sum(1 for H, S, V in px if S > 80 and V > 50)
    print("%s %.2f%%" % (re.findall(r"-(\d+)\.png", f)[0], 100.0 * n / len(px)))
