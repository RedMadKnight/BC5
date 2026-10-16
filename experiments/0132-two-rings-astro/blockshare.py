#!/usr/bin/env python3
# Experiment 0132: near-black pixels on ASTRO BOT title screen models (robots and the pad), in the
# region x 33-55 %, y 50-62 % of a full-screen screenshot of the windowed game.
import sys, re
from PIL import Image
for f in sorted(sys.argv[1:], key=lambda f: int(re.findall(r"-(\d+)\.png", f)[0])):
    im = Image.open(f).convert("L")
    w, h = im.size
    box = im.crop((int(w * 0.33), int(h * 0.50), int(w * 0.55), int(h * 0.62)))
    px = list(box.getdata())
    n = sum(1 for v in px if v < 20)
    print("%s %.1f%%" % (re.findall(r"-(\d+)\.png", f)[0], 100.0 * n / len(px)))
