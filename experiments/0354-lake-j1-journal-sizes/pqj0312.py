#!/usr/bin/env python3
# BC5 experiment 0312, run J1: do the culling buffers' few-content pages follow the hole state, frame by frame? Inputs:
# buf0312.py's reads (bNN.cK.bin, the 8 MiB from 0x11934d3900 just before the depth read bNN.zK) and rdj0312.py's JSON
# (each depth read's frame from fr0312.py and its state at the frame's size: X, Y, or other). Per page, a read's
# content is the order-insensitive key of pg0312.py. The unit is the journal frame (reads 30 ms apart see the same
# frame two or three times; counting reads would overstate the evidence): a frame is X or Y when its depth reads agree,
# and has a page content when its culling reads agree. Per page, over the frames with both: the 2 x k table (state x
# content) and its chi-square; the p value by shuffling the frames' states (the same shuffles for every page).
#  - Pages named in advance from P1: 1767 (1768 held the same sequence) and 1776; each with its own p.
#  - The scan: every page with 2..8 contents over the frames; the top scores against the null of the scan's largest.
# The hole state holds for 1-8+ frames and P1's page states for 1-4 reads, so neighbouring frames are not independent:
# a run-length check prints how often each sequence changes, for reading the p values. Summaries only.
# usage: python3 -I pqj0312.py <capture dir> <rdj json> [permutations]   |   python3 -I pqj0312.py --selftest
#   (numpy for the reads, on the box in the ubuntu distrobox; the selftest is pure Python)
import json, os, random, sys

PAGE, NPAGE = 1024, 2048
BASE = 0x11934d3900
NAMED = (1767, 1768, 1776)


def chi2(states, contents):
    ks = sorted(set(contents))
    if len(ks) < 2:
        return 0.0
    n = len(states)
    nx = sum(1 for s in states if s == "X")
    if nx in (0, n):
        return 0.0
    tot = 0.0
    for k in ks:
        ck = [s for s, c in zip(states, contents) if c == k]
        for st, ns in (("X", nx), ("Y", n - nx)):
            e = len(ck) * ns / n
            o = sum(1 for s in ck if s == st)
            tot += (o - e) ** 2 / e
    return tot


def runs(seq):
    return sum(1 for a, b in zip(seq, seq[1:]) if a != b)


def analyse(frames, nperm):
    """frames: list of (frame index, state, {page: content id})"""
    st = [f[1] for f in frames]
    print("# %d frames with an X or Y state and agreeing culling reads (X %d, Y %d); state changes between them: %d" % (
        len(frames), st.count("X"), st.count("Y"), runs(st)))
    if len(frames) < 6 or st.count("X") < 2 or st.count("Y") < 2:
        print("  too few frames of both states")
        return
    pages = sorted({p for f in frames for p in f[2]})
    cont = {p: [f[2].get(p) for f in frames] for p in pages}
    scan = [p for p in pages if None not in cont[p] and 2 <= len(set(cont[p])) <= 8]
    print("  pages with 2..8 contents over these frames: %d" % len(scan))
    obs = {p: chi2(st, cont[p]) for p in set(scan) | {p for p in NAMED if p in cont and None not in cont[p]}}
    rng = random.Random(312)
    null_max, null_named = [], {p: 0 for p in NAMED if p in obs}
    for _ in range(nperm):
        sh = list(st)
        rng.shuffle(sh)
        if scan:
            null_max.append(max(chi2(sh, cont[p]) for p in scan))
        for p in null_named:
            null_named[p] += chi2(sh, cont[p]) >= obs[p] - 1e-12
    for p in NAMED:
        if p not in obs:
            print("  page %d: not in every frame's reads" % p)
            continue
        ks = sorted(set(cont[p]))
        tab = " ".join("c%d: X %d Y %d" % (k, sum(1 for s, c in zip(st, cont[p]) if c == k and s == "X"),
                                           sum(1 for s, c in zip(st, cont[p]) if c == k and s == "Y")) for k in ks)
        print("  page %4d (named; +0x%06x, 0x%x): %d contents, changes %d; %s; chi2 %.2f, p %.4f (%d)" % (
            p, p * PAGE * 4, BASE + p * PAGE * 4, len(ks), runs(cont[p]), tab, obs[p], (null_named[p] + 1) / (nperm + 1), nperm))
    if scan:
        null_max.sort()
        print("  scan null of the largest chi2 (states shuffled, %d): median %.2f, 95th percentile %.2f" % (
            nperm, null_max[nperm // 2], null_max[int(0.95 * nperm)]))
        for p in sorted(scan, key=lambda q: -obs[q])[:8]:
            print("    page %4d (+0x%06x, 0x%x): chi2 %.2f, %d contents, changes %d%s" % (
                p, p * PAGE * 4, BASE + p * PAGE * 4, obs[p], len(set(cont[p])), runs(cont[p]),
                "  <- above the 95th percentile" if obs[p] > null_max[int(0.95 * nperm)] else ""))


def page_keys(f, wanted=None):
    import numpy as np  # here, so that the selftest runs without numpy
    a = np.frombuffer(open(f, "rb").read(), dtype="<u4")[:PAGE * NPAGE]
    a = np.sort(np.pad(a, (0, PAGE * NPAGE - a.size)).reshape(NPAGE, PAGE), axis=1)
    return {p: hash(a[p].tobytes()) for p in (range(NPAGE) if wanted is None else wanted)}


if sys.argv[1:2] == ["--selftest"]:
    rng = random.Random(312)
    frames, s = [], "X"
    for j in range(120):
        if rng.random() < 0.25:
            s = "Y" if s == "X" else "X"
        c = {1767: 0 if s == "X" else 1, 1776: rng.randrange(3), 500: rng.randrange(2)}
        if rng.random() < 0.1:
            c[1767] = 1 - c[1767]
        frames.append((j, s, c))
    print("# selftest: 120 frames, page 1767 follows the state in ~90 % of frames, 1776 and 500 random")
    print("# expect 1767 p ~0.0005 and on top of the scan above the 95th percentile; 1776 p well above 0.05")
    analyse(frames, 2000)
    sys.exit(0)
cdir, rjson = sys.argv[1], sys.argv[2]
nperm = int(sys.argv[3]) if len(sys.argv) > 3 else 2000
rj = json.load(open(rjson))
zs = {r["name"]: r for r in rj["reads"] if r["kind"] == "z"}
byframe = {}
for name, r in zs.items():
    f = os.path.join(cdir, "%s.c%s.bin" % tuple(name.split(".z")))
    if r.get("frame_j") is None or not os.path.exists(f):
        continue
    byframe.setdefault(r["frame_j"], []).append((r["state"], f))
print("# %d depth reads with a frame, %d frames" % (sum(len(v) for v in byframe.values()), len(byframe)))
frames, dropped = [], {"mixed state": 0, "no X/Y": 0, "culling reads differ": 0}
allkeys = {}
for j in sorted(byframe):
    sts = {s for s, _ in byframe[j]}
    if not sts <= {"X", "Y"} or not sts:
        if sts & {"X", "Y"}:
            dropped["mixed state"] += 1
        else:
            dropped["no X/Y"] += 1
        continue
    if len(sts) > 1:
        dropped["mixed state"] += 1
        continue
    ks = [page_keys(f) for _, f in byframe[j]]
    agree = {p: ks[0][p] for p in range(NPAGE) if all(k[p] == ks[0][p] for k in ks)}
    if not agree:
        dropped["culling reads differ"] += 1
        continue
    for p, k in agree.items():
        allkeys.setdefault(p, {}).setdefault(k, len(allkeys[p]))
    frames.append((j, sts.pop(), {p: allkeys[p][k] for p, k in agree.items()}))
print("  frames left out: %s" % ", ".join("%s %d" % kv for kv in dropped.items()))
analyse(frames, nperm)
