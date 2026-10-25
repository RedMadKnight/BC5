#!/usr/bin/env python3
# BC5 experiment 0299: how washed out a run's screenshots are, in numbers (the shots themselves are never copied or
# committed). Per shot (exp 0190's shots.sh, the 1920x1080 window): the mean luma (Rec. 709 weights on the 8-bit
# gamma-coded channels / 255), its 50th/90th/99th percentiles, the share of pixels with luma >= 0.90 ("white"), the share
# with all three channels >= 240 ("clipped"), the mean chroma (max - min channel / 255; washed-out white is low chroma
# at high luma), and the mean luma of a 3 x 3 grid of the frame. A shot whose mean luma is under 0.03 is marked
# "dark" (loading screen or black). Then the medians over the shots that are not dark and not identical to the previous
# one's numbers. Runs on the box in the ubuntu distrobox (numpy, PIL).
# usage: python3 -I wh0299.py <shots dir>
import glob, os, sys
import numpy as np
from PIL import Image

rows = []
for f in sorted(glob.glob(os.path.join(sys.argv[1], "*.png"))):
    try:
        a = np.asarray(Image.open(f).convert("RGB")).astype(np.float64) / 255.0
    except OSError as e:
        print("  %s: unreadable (%s)" % (os.path.basename(f), e))
        continue
    y = 0.2126 * a[:, :, 0] + 0.7152 * a[:, :, 1] + 0.0722 * a[:, :, 2]
    h, w = y.shape
    grid = [float(y[i * h // 3:(i + 1) * h // 3, j * w // 3:(j + 1) * w // 3].mean()) for i in range(3) for j in range(3)]
    r = {"name": os.path.basename(f), "mean": float(y.mean()), "p50": float(np.percentile(y, 50)), "p90": float(np.percentile(y, 90)),
         "p99": float(np.percentile(y, 99)), "white": float((y >= 0.90).mean()), "clipped": float((a.min(axis=2) >= 240 / 255).mean()),
         "chroma": float((a.max(axis=2) - a.min(axis=2)).mean()), "grid": grid, "size": "%dx%d" % (w, h)}
    rows.append(r)
print("# %s: %d shots" % (sys.argv[1], len(rows)))
prev = None
use = []
for r in rows:
    dark = r["mean"] < 0.03
    same = prev is not None and all(abs(r[k] - prev[k]) < 1e-9 for k in ("mean", "white", "chroma"))
    print("  %s %s: luma mean %.3f p50 %.3f p90 %.3f p99 %.3f; white %.3f clipped %.3f; chroma %.3f; grid %s%s" % (
        r["name"], r["size"], r["mean"], r["p50"], r["p90"], r["p99"], r["white"], r["clipped"], r["chroma"],
        " ".join("%.2f" % g for g in r["grid"]), " dark" if dark else (" same as before" if same else "")))
    if not dark and not same:
        use.append(r)
    prev = r
if use:
    med = lambda k: float(np.median([r[k] for r in use]))
    print("# median over %d shots (not dark, not repeated): luma mean %.3f p90 %.3f p99 %.3f; white %.3f clipped %.3f; chroma %.3f" % (
        len(use), med("mean"), med("p90"), med("p99"), med("white"), med("clipped"), med("chroma")))
