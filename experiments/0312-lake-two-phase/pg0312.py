#!/usr/bin/env python3
# BC5 experiment 0312: which pages of the night lake's culling buffers carry the hole state? buf0312.py reads the 8 MiB
# from 0x11934d3900 ("cK", beside each depth read "zK"); rd0312.py labels the depth reads with their hole family (X, Y,
# ...). A per-cell visibility record or a visible-cell list would be rewritten every frame (F357) but hold the same
# content within one state and a different content in the other, possibly in another order. So per 4-KiB page (1024
# dwords) and read: an order-insensitive content key (the page's sorted dwords) and an order-sensitive one. Over all
# pairs of labelled reads (X or Y; within and across bursts): per page, the share of pairs whose keys differ among
# same-state pairs and among X-Y pairs; the page's state score is the difference. A page that is constant scores 0, a
# page rewritten with new values every frame scores ~0 (differs in both), a page that follows the state scores ~1.
# Prints the pages that change at all, the top pages by score (offset from 0x11934d3900, rates, distinct contents), and
# the null of the top score with the labels shuffled. Summaries only. Runs on the box in the ubuntu distrobox (numpy).
# --selftest: synthetic reads, page 100 holding one of two cell lists by state (shuffled order), page 200 new every
# read, the rest constant: expect page 100 on top at ~1 and page 200 at ~0.
# usage: python3 -I pg0312.py <capture dir> <reads json> [permutations]   |   python3 -I pg0312.py --selftest
import glob, json, os, random, sys
import numpy as np

PAGE, NPAGE = 1024, 2048
BASE = 0x11934d3900


def keys(raw):
    a = np.frombuffer(raw, dtype="<u4")[:PAGE * NPAGE]
    a = np.pad(a, (0, PAGE * NPAGE - a.size)).reshape(NPAGE, PAGE)
    s = np.sort(a, axis=1)
    return [hash(s[p].tobytes()) for p in range(NPAGE)], [hash(a[p].tobytes()) for p in range(NPAGE)]


def analyse(reads, nperm):
    """reads: list of (name, burst, state, (sorted keys, raw keys))."""
    lab = [r for r in reads if r[2] in ("X", "Y")]
    print("# %d reads, %d labelled (X %d, Y %d)" % (len(reads), len(lab), sum(1 for r in lab if r[2] == "X"), sum(1 for r in lab if r[2] == "Y")))
    changing = [p for p in range(NPAGE) if len({r[3][1][p] for r in reads}) > 1]
    print("  pages that change at all over the reads: %d of %d" % (len(changing), NPAGE))
    if len(lab) < 3 or len({r[2] for r in lab}) < 2:
        print("  too few labelled reads of both states")
        return
    pairs = [(i, j) for i in range(len(lab)) for j in range(i + 1, len(lab))]
    diff = np.array([[lab[i][3][0][p] != lab[j][3][0][p] for p in changing] for i, j in pairs], dtype=float)

    def score(states):
        same = np.array([states[i] == states[j] for i, j in pairs])
        if same.all() or not same.any():
            return None
        return diff[~same].mean(axis=0) - diff[same].mean(axis=0), diff[same].mean(axis=0), diff[~same].mean(axis=0), int(same.sum()), int((~same).sum())

    st = [r[2] for r in lab]
    sc, rs, rd, ns, nd = score(st)
    rng, null = random.Random(312), []
    for _ in range(nperm):
        sh = list(st)
        rng.shuffle(sh)
        v = score(sh)
        if v is not None:
            null.append(float(v[0].max()))
    null.sort()
    order = np.argsort(-sc)[:12]
    print("  pairs: %d same-state, %d X-Y; null of the top score (labels shuffled, %d): median %.2f, 95th percentile %.2f" % (
        ns, nd, len(null), null[len(null) // 2], null[int(0.95 * len(null))]))
    for o in order:
        p = changing[o]
        print("    page %4d (+0x%06x, 0x%x): score %+.2f; differs in %.2f of same-state pairs, %.2f of X-Y pairs; %d distinct contents" % (
            p, p * PAGE * 4, BASE + p * PAGE * 4, sc[o], rs[o], rd[o], len({r[3][0][p] for r in reads})))


if sys.argv[1:2] == ["--selftest"]:
    rng = np.random.default_rng(312)
    base = rng.integers(0, 1 << 32, size=PAGE * NPAGE, dtype=np.uint32)
    cellsX, cellsY = rng.integers(0, 65536, PAGE, dtype=np.uint32), rng.integers(0, 65536, PAGE, dtype=np.uint32)
    reads = []
    for b in range(4):
        for k in range(5):
            st = "XY"[(b + k // 3) % 2]
            a = base.copy()
            a[100 * PAGE:101 * PAGE] = rng.permutation(cellsX if st == "X" else cellsY)
            a[200 * PAGE:201 * PAGE] = rng.integers(0, 1 << 32, PAGE, dtype=np.uint32)
            reads.append(("b%02d.z%d" % (b + 1, k), "b%02d" % (b + 1), st, keys(a.tobytes())))
    print("# selftest: expect page 100 on top at score ~1, page 200 at ~0, 2 pages changing")
    analyse(reads, 200)
    sys.exit(0)
cdir, rjson = sys.argv[1], sys.argv[2]
nperm = int(sys.argv[3]) if len(sys.argv) > 3 else 500
rj = json.load(open(rjson))
fam = {n: f["name"] for f in rj["families"] for n in f["reads"]}
reads = []
for tf in sorted(glob.glob(os.path.join(cdir, "b*.times.txt"))):
    b = os.path.basename(tf).split(".")[0]
    for l in open(tf):
        if l.startswith("c") and " error " not in l:
            k = l.split()[0][1:]
            f = os.path.join(cdir, "%s.c%s.bin" % (b, k))
            if os.path.exists(f):
                reads.append(("%s.z%s" % (b, k), b, fam.get("%s.z%s" % (b, k), "-"), keys(open(f, "rb").read())))
analyse(reads, nperm)
