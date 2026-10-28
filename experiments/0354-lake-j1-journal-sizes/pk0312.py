#!/usr/bin/env python3
# BC5 experiment 0312: pg0312.py without the family labels. Without the draw journal most depth reads have no clear render
# size, and only one clear read fell in family Y, so the labelled test had no power. Here every clear depth read with
# holes (next-best shear >= 3 x best, depth-0 share > 0 at the best size) carries a continuous label, d = inX - inY at
# its best size (how far its holes lean to X's set rather than Y's). Per 4-KiB page of the culling buffers' read beside
# it (the order-insensitive key of pg0312.py), over all pairs of these reads: the mean |d_i - d_j| among pairs whose
# keys differ minus that among pairs whose keys agree (pages where all or no pairs agree are left out). A page that
# follows the hole state scores high; the null is the top score with d shuffled over the reads. Summaries only.
# usage: python3 -I pk0312.py <capture dir> <reads json> [permutations]   (on the box, in the ubuntu distrobox)
import json, os, random, sys
import numpy as np

PAGE, NPAGE = 1024, 2048
BASE = 0x11934d3900
cdir, rjson = sys.argv[1], sys.argv[2]
nperm = int(sys.argv[3]) if len(sys.argv) > 3 else 500
rows = []
for r in json.load(open(rjson))["reads"]:
    if r["kind"] != "z":
        continue
    s = sorted(r["sizes"].values(), key=lambda v: v["shear"])
    if len(s) < 2 or s[1]["shear"] < 3 * s[0]["shear"] or s[0]["share"] <= 0:
        continue
    f = os.path.join(cdir, "%s.c%s.bin" % tuple(r["name"].split(".z")))
    if os.path.exists(f):
        rows.append((r["name"], s[0]["inX"] - s[0]["inY"], f))
print("# %d clear depth reads with holes; d = inX - inY: min %.2f, median %.2f, max %.2f" % (
    len(rows), min(r[1] for r in rows), float(np.median([r[1] for r in rows])), max(r[1] for r in rows)))
keys = []
for _, _, f in rows:
    a = np.frombuffer(open(f, "rb").read(), dtype="<u4")[:PAGE * NPAGE]
    a = np.sort(np.pad(a, (0, PAGE * NPAGE - a.size)).reshape(NPAGE, PAGE), axis=1)
    keys.append([hash(a[p].tobytes()) for p in range(NPAGE)])
pairs = [(i, j) for i in range(len(rows)) for j in range(i + 1, len(rows))]
same = np.array([[keys[i][p] == keys[j][p] for p in range(NPAGE)] for i, j in pairs])
use = [p for p in range(NPAGE) if same[:, p].any() and not same[:, p].all()]
print("  pages whose content agrees for some pairs and not others: %d" % len(use))
if not use:
    sys.exit(0)
S = same[:, use]


def score(d):
    dd = np.array([abs(d[i] - d[j]) for i, j in pairs])[:, None]
    return (dd * ~S).sum(axis=0) / (~S).sum(axis=0) - (dd * S).sum(axis=0) / S.sum(axis=0)


d = [r[1] for r in rows]
sc = score(d)
rng, null = random.Random(312), []
for _ in range(nperm):
    sh = list(d)
    rng.shuffle(sh)
    null.append(float(score(sh).max()))
null.sort()
print("  null of the top score (d shuffled, %d): median %.3f, 95th percentile %.3f, 99th %.3f" % (
    nperm, null[nperm // 2], null[int(0.95 * nperm)], null[int(0.99 * nperm)]))
for o in np.argsort(-sc)[:8]:
    p = use[o]
    print("    page %4d (+0x%06x, 0x%x): score %+.3f; keys agree in %d of %d pairs; %d distinct contents" % (
        p, p * PAGE * 4, BASE + p * PAGE * 4, sc[o], int(S[:, o].sum()), len(pairs), len({k[p] for k in keys})))
