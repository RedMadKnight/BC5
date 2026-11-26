#!/usr/bin/env python3
# BC5 experiment 0311: the night lake water's per-cell ping-pong grid (grid0311.py's gA/gB reads: 65,536 records of 8
# bytes, taken as 256 x 256 in record order) against the hole state of the depth read taken next to them (rd0311.py's
# families: X, Y, F3...). The record's meaning is unknown, so the analysis is per bit (64 per record):
#  - per read: which of the two grids changed since the previous read of the burst (bytes differing), and the share of
#    records that are not all zero;
#  - per bit, over all reads: its set share, and its parity contrast (set share on cells with (row + column) even minus
#    odd: a checkerboard of cells gives +-1, a field without one ~0);
#  - per bit and grid, X reads against Y reads: the set shares, and the share of cells whose majority value differs
#    between the X reads and the Y reads (complementary halves give ~0.5 on a checkerboard bit, 0 on others);
#  - the 12 bits with the largest X/Y cell difference.
# Summaries only (bit positions, shares). Runs on the box in the ubuntu distrobox (numpy), on the title's data.
# --selftest builds a synthetic capture in memory: bit 3 a checkerboard whose phase follows the read's state.
# usage: python3 -I gan0311.py <capture dir> <reads json>      |      python3 -I gan0311.py --selftest
import glob, json, os, sys
import numpy as np

N, W = 65536, 256
par = ((np.arange(N) // W + np.arange(N) % W) & 1).astype(bool)


def bits(raw):
    a = np.frombuffer(raw, dtype=np.uint8)[:N * 8].reshape(N, 8)
    return np.unpackbits(a, axis=1, bitorder="little").astype(bool)  # N x 64: bit k of byte k // 8


def analyse(reads, label):
    """reads: list of (name, burst, k, gA bytes, gB bytes); label: {name: family}."""
    print("# %d reads with both grids; labelled: %s" % (len(reads), ", ".join("%s %d" % (f, sum(1 for r in reads if label.get(r[0]) == f))
                                                                          for f in sorted(set(label.values())))))
    prev = {}
    for name, b, k, ga, gb in reads:
        p = prev.get(b)
        ch = ""
        if p is not None:
            da = int((np.frombuffer(ga, np.uint8) != np.frombuffer(p[0], np.uint8)).sum())
            db = int((np.frombuffer(gb, np.uint8) != np.frombuffer(p[1], np.uint8)).sum())
            ch = "; bytes changed since the previous read: A %d, B %d" % (da, db)
        nzA = float((np.frombuffer(ga, np.uint8).reshape(N, 8) != 0).any(axis=1).mean())
        nzB = float((np.frombuffer(gb, np.uint8).reshape(N, 8) != 0).any(axis=1).mean())
        print("  %s (%s): non-zero records A %.3f, B %.3f%s" % (name, label.get(name, "-"), nzA, nzB, ch))
        prev[b] = (ga, gb)
    for g, gi in (("A", 3), ("B", 4)):
        allb = np.stack([bits(r[gi]) for r in reads])  # R x N x 64
        share = allb.mean(axis=(0, 1))
        pc = allb[:, par, :].mean(axis=(0, 1)) - allb[:, ~par, :].mean(axis=(0, 1))
        X = [i for i, r in enumerate(reads) if label.get(r[0]) == "X"]
        Y = [i for i, r in enumerate(reads) if label.get(r[0]) == "Y"]
        print("# grid %s: bits with a parity contrast |c| >= 0.2: %s" % (g, ", ".join("b%d %+.2f (set %.2f)" % (k, pc[k], share[k]) for k in range(64) if abs(pc[k]) >= 0.2) or "none"))
        if X and Y:
            mx, my = allb[X].mean(axis=0) >= 0.5, allb[Y].mean(axis=0) >= 0.5  # N x 64 majority maps
            diff = (mx != my).mean(axis=0)
            order = np.argsort(-diff)[:12]
            print("# grid %s, X reads (%d) against Y reads (%d): bits by the share of cells whose majority value differs" % (g, len(X), len(Y)))
            for k in order:
                print("    b%-2d: cells differing %.3f; set share X %.3f, Y %.3f; parity contrast X %+.2f, Y %+.2f" % (
                    k, diff[k], allb[X][:, :, k].mean(), allb[Y][:, :, k].mean(),
                    allb[X][:, par, k].mean() - allb[X][:, ~par, k].mean(), allb[Y][:, par, k].mean() - allb[Y][:, ~par, k].mean()))
        else:
            print("# grid %s: X and Y reads not both present" % g)


if sys.argv[1:2] == ["--selftest"]:
    rng = np.random.default_rng(311)
    reads, label = [], {}
    for b in range(4):
        st = "XY"[b % 2]
        for k in range(4):
            recs = rng.integers(0, 256, size=(N, 8), dtype=np.uint8)
            recs[:, 0] &= 0xf7
            recs[:, 0] |= ((par ^ (st == "Y")).astype(np.uint8) << 3)
            name = "b%02d.z%d" % (b + 1, k)
            reads.append((name, "b%02d" % (b + 1), k, recs.tobytes(), rng.integers(0, 256, size=N * 8, dtype=np.uint8).tobytes()))
            label[name] = st
    print("# selftest: grid A bit 3 is a checkerboard whose phase follows the state; expect b3 on top, cells differing ~1.0,"
          " parity contrast +1 / -1; grid B random")
    analyse(reads, label)
    sys.exit(0)
cdir, rjson = sys.argv[1], sys.argv[2]
rj = json.load(open(rjson))
label = {n: f["name"] for f in rj["families"] for n in f["reads"]}
reads = []
for tf in sorted(glob.glob(os.path.join(cdir, "b*.times.txt"))):
    b = os.path.basename(tf).split(".")[0]
    lines = {l.split()[0]: l for l in open(tf) if l.strip()}
    k = 0
    while "z%d" % k in lines:
        fa, fb = (os.path.join(cdir, "%s.g%s%d.bin" % (b, g, k)) for g in "AB")
        if os.path.exists(fa) and os.path.exists(fb):
            reads.append(("%s.z%d" % (b, k), b, k, open(fa, "rb").read(), open(fb, "rb").read()))
        k += 1
analyse(reads, label)
