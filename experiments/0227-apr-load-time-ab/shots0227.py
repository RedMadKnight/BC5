#!/usr/bin/env python3
# BC5 experiment 0227: scores each run's screenshots (shots/<tag>/, run0227.sh's spectacle loop, active window, one about
# every 4.4 s) by the share of pixels brighter than 16/255, on the box (the images are private and stay there).
# "presents" (ASTRO BOT's first logo, "Sony Interactive Entertainment presents") is the first shot at least 1 % lit that
# follows a shot under 0.5 % lit (the game's black window); times are from the launcher's start, at each shot's start
# and end (the logo appeared at most one shot interval earlier). usage: shots0227.py <exp dir> <tag> ...
import os, re, sys

from PIL import Image

E, tags = sys.argv[1], sys.argv[2:]
for tag in tags:
    launch = None
    for line in open(f"{E}/raw/{tag}-start.txt", encoding="latin-1"):
        m = re.search(r"launch at uptime ([0-9.]+)", line)
        if m:
            launch = float(m.group(1))
    rows = []
    for line in open(f"{E}/shots/{tag}/index.txt", encoding="latin-1"):
        name, u0, u1 = line.split()
        path = f"{E}/shots/{tag}/{name}"
        lit = None
        if os.path.exists(path):
            im = Image.open(path).convert("L")
            h = im.histogram()
            lit = 100.0 * sum(h[17:]) / max(sum(h), 1)
        rows.append((float(u0) - launch, float(u1) - launch, lit))
    seen_dark, presents = False, None
    for a, b, lit in rows:
        if lit is None:
            continue
        if lit < 0.5:
            seen_dark = True
        elif seen_dark and lit >= 1.0:
            presents = (a, b, lit)
            break
    print(f"{tag}: " + " ".join("-" if lit is None else f"{a:.0f}:{lit:.0f}%" for a, b, lit in rows))
    if presents:
        print(f"{tag}: presents in the shot taken {presents[0]:.1f}-{presents[1]:.1f} s after the launch ({presents[2]:.0f} % lit)")
    else:
        print(f"{tag}: presents not seen in the shots")
