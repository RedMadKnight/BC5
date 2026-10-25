#!/usr/bin/env python3
# BC5 experiment 0307: are the night lake's visible patches two complementary halves of one cell grid? Exp 0282 (F342):
# the depth holes switch between two fixed, disjoint pixel sets X and Y; exp 0304's viewed shots show the patches as a
# checkerboard of cells on the water plane. If the water renderer updates half its cells per frame and fills the other
# half from history, a failing fill leaves one half or the other empty, and the shots of one frozen view should fall
# into two families of patch masks that are disjoint and together cover the patched water.
# Per shot (exp 0190's shots.sh / bench0307.sh's frozen-view series, 1920x1080), the patch mask of exp 0283's
# rd0283.py: mean channel > 47 and blue - red > 38, inside the lake window x 300..1900, y 400..680. Then:
#  - per shot, the patch share of the window;
#  - families of patched shots (share >= 0.03): a shot joins the first family whose first shot it matches with
#    phi >= 0.6, as cross0282.py; each family's union mask;
#  - for each pair of families: the pixels they share (as a share of the smaller), phi between their unions, and what
#    their union covers of the window;
#  - the shots' family sequence in time order, and for consecutive patched shots whether they are the same family;
#  - a null for "disjoint": the overlap two random masks of the same shares would have (the product of the shares).
# Summaries only. Runs on the box in the ubuntu distrobox (numpy, PIL), on the run's shots; nothing is copied.
# usage: python3 -I cm0307.py <shots dir> [glob, default *-ts*.png]
import glob, os, sys
import numpy as np
from PIL import Image

X0, X1, Y0, Y1 = 300, 1900, 400, 680
files = sorted(glob.glob(os.path.join(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "*-ts*.png")))


def patch_mask(path):
    a = np.asarray(Image.open(path).convert("RGB")).astype(np.float64)[Y0:Y1, X0:X1]
    return (a.mean(axis=2) > 47) & (a[:, :, 2] - a[:, :, 0] > 38)


def phi(a, b):
    x, y = a.ravel().astype(float), b.ravel().astype(float)
    if x.std() == 0 or y.std() == 0:
        return float("nan")
    return float(np.corrcoef(x, y)[0, 1])


shots = [(os.path.basename(f), patch_mask(f)) for f in files]
print("# %s: %d shots; lake window %dx%d" % (sys.argv[1], len(shots), X1 - X0, Y1 - Y0))
fam_of, groups = {}, []
for i, (n, m) in enumerate(shots):
    if m.mean() < 0.03:
        continue
    for g in groups:
        if phi(m, shots[g[0]][1]) >= 0.6:
            g.append(i)
            break
    else:
        groups.append([i])
groups.sort(key=lambda g: -len(g))
names = ["A", "B"] + ["F%d" % k for k in range(3, 3 + len(groups))]
unions = []
for k, g in enumerate(groups):
    for i in g:
        fam_of[i] = names[k]
    u = np.zeros_like(shots[0][1])
    for i in g:
        u |= shots[i][1]
    unions.append(u)
seq = []
for i, (n, m) in enumerate(shots):
    seq.append(fam_of.get(i, "."))
    print("  %s: patch share %.3f, family %s" % (n, m.mean(), fam_of.get(i, "- (clean)")))
print("# families of patched shots (share >= 0.03), a shot joining the first family it matches with phi >= 0.6")
for k, g in enumerate(groups):
    sh = np.mean([shots[i][1].mean() for i in g])
    within = [phi(shots[i][1], shots[g[0]][1]) for i in g[1:]]
    print("  %s: %d shots, mean share %.3f, union %.3f of the window, phi with its first shot %s" % (
        names[k], len(g), sh, unions[k].mean(), ("%.2f-%.2f" % (min(within), max(within))) if within else "-"))
print("# pairs of families: shared pixels (share of the smaller union), the null of two random masks of these shares, phi of the unions, union coverage")
for a in range(len(groups)):
    for b in range(a + 1, len(groups)):
        ua, ub = unions[a], unions[b]
        both = (ua & ub).sum() / max(min(ua.sum(), ub.sum()), 1)
        null = max(ua.mean(), ub.mean())
        print("  %s-%s: shared %.3f of the smaller (random masks: ~%.3f), phi %+.3f, together %.3f of the window" % (
            names[a], names[b], both, null, phi(ua, ub), (ua | ub).mean()))
print("# family sequence in time order (. clean): %s" % "".join(seq))
pairs = [(seq[i], seq[i + 1]) for i in range(len(seq) - 1) if seq[i] != "." and seq[i + 1] != "."]
print("  consecutive patched shots: same family %d, different %d" % (sum(1 for a, b in pairs if a == b), sum(1 for a, b in pairs if a != b)))
