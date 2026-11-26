#!/usr/bin/env python3
# BC5 experiment 0357: per GPU frame, the order of the depth pyramid's rebuild and the culling records' updates, against
# the lake's hole state. Inputs: pl0357.py's events (one line per poll with a change: monotonic time, D flag, five mip
# flags, the changed culling records), its full reads' times (b01.times.txt) and ph0357.py's labels (a state per full
# read, the two sides of the reads' hole-mask split).
#  - Cycles: the depth activity D comes in bursts, one per frame. A cycle starts at a D change after at least G s without
#    one; G is four times the median gap between D changes, at least 3 ms. Window c runs from cycle c's first D change to
#    cycle c+1's; D's last change in it ends the frame's depth writes.
#  - Per window: tp, the first pyramid change (any mip; which mips changed), and ta, the first culling-record change;
#    whether any record changes before tp and any after it. Its class: "PA" (tp < ta), "AP" (ta < tp), "P" (no record
#    change), "A" (no pyramid change), "-" (neither).
#  - A full read that starts while D is quiet shows its window's frame c; the culling records that frame's draws used
#    were written in window c-1, the feeding window. Reads that start inside D activity are left out.
#  - The test: the state x feeding-class table and its chi-square, p by shuffling the reads' states (reads 0.5 s apart
#    are farther apart than the state holds, F436: 1-7 frames); and the same for the shown window's class.
# Summaries only. usage: python3 -I cy0357.py <events.txt> <b01.times.txt> <labels json> [permutations]
#                        python3 -I cy0357.py --selftest
import bisect, collections, json, random, re, statistics, sys

CLASSES = ("PA", "AP", "P", "A", "-")


def parse(lines):
    rows = []
    for l in lines:
        f = l.split()
        if len(f) < 5:
            continue
        a = [] if f[4] == "A-" else [tuple(int(x) for x in r.split(":")) for r in f[4][1:].split(",")]
        rows.append((float(f[0]), f[2] == "D1", [c == "1" for c in f[3][1:]], a))
    rows.sort(key=lambda r: r[0])
    return rows


def windows(rows):
    dts = [r[0] for r in rows if r[1]]
    if len(dts) < 3:
        return [], 0.0
    gaps = [b - a for a, b in zip(dts, dts[1:])]
    G = max(0.003, 4 * statistics.median(gaps))
    starts = [dts[0]] + [b for a, b in zip(dts, dts[1:]) if b - a >= G]
    ws, ts = [], [r[0] for r in rows]
    for i in range(len(starts) - 1):
        s, nxt = starts[i], starts[i + 1]
        inw = rows[bisect.bisect_left(ts, s):bisect.bisect_left(ts, nxt)]
        dlast = max(r[0] for r in inw if r[1])
        ps = [r for r in inw if any(r[2])]
        as_ = [r for r in inw if r[3]]
        tp = ps[0][0] if ps else None
        ta = as_[0][0] if as_ else None
        mips = [any(r[2][k] for r in ps) for k in range(5)]
        if tp is not None and ta is not None:
            cls = "PA" if tp < ta else "AP"
        else:
            cls = "P" if tp is not None else "A" if ta is not None else "-"
        before = tp is not None and any(r[0] < tp for r in as_)
        after = tp is not None and any(r[0] >= tp for r in as_)
        ws.append({"s": s, "e": dlast, "next": nxt, "tp": tp, "ta": ta, "cls": cls, "mips": mips, "before": before,
                   "after": after, "recs": sum(len(r[3]) for r in as_)})
    return ws, G


def chi2(states, cls):
    n = len(states)
    ss, cs = sorted(set(states)), sorted(set(cls))
    if len(ss) < 2 or len(cs) < 2:
        return 0.0
    t = 0.0
    for s in ss:
        ns = states.count(s)
        for c in cs:
            nc = cls.count(c)
            e = ns * nc / n
            o = sum(1 for a, b in zip(states, cls) if a == s and b == c)
            t += (o - e) ** 2 / e
    return t


def analyse(rows, reads, labels, nperm):
    ws, G = windows(rows)
    print("# %d polls with a change; %d windows (cycles) at G %.1f ms" % (len(rows), len(ws), 1000 * G))
    if len(ws) < 5:
        print("  too few cycles")
        return None
    per = sorted(w["next"] - w["s"] for w in ws)
    dl = sorted(w["e"] - w["s"] for w in ws)
    print("  cycle period: median %.1f ms, quartiles %.1f / %.1f; depth activity per cycle: median %.1f ms" % (
        1000 * per[len(per) // 2], 1000 * per[len(per) // 4], 1000 * per[3 * len(per) // 4], 1000 * dl[len(dl) // 2]))
    cc = collections.Counter(w["cls"] for w in ws)
    print("  classes over all cycles: %s" % ", ".join("%s %d" % (c, cc[c]) for c in CLASSES))
    both = collections.Counter((w["before"], w["after"]) for w in ws if w["tp"] is not None and w["ta"] is not None)
    print("  cycles with both: records changed before the pyramid %d, after %d, both before and after %d" % (
        both[(True, False)], both[(False, True)], both[(True, True)]))
    mc = collections.Counter(tuple(w["mips"]) for w in ws if w["tp"] is not None)
    print("  pyramid mips changed per rebuilding cycle: %s" % ", ".join("%s %d" % ("".join("1" if x else "0" for x in k), v) for k, v in mc.most_common(4)))
    for c in ("PA", "AP"):
        g = [w for w in ws if w["cls"] == c]
        if g:
            print("  %s cycles: pyramid at +%.1f ms and records at +%.1f ms after the depth activity's end (medians); %d records changed (median)" % (
                c, 1000 * statistics.median(w["tp"] - w["e"] for w in g), 1000 * statistics.median(w["ta"] - w["e"] for w in g),
                statistics.median(w["recs"] for w in g)))
    starts = [w["s"] for w in ws]
    pts = []
    for name, t in reads:
        if name not in labels:
            continue
        c = bisect.bisect_right(starts, t) - 1
        if c < 1 or c >= len(ws) or t <= ws[c]["e"] + 0.0005:
            continue
        pts.append((name, labels[name], ws[c - 1]["cls"], ws[c]["cls"]))
    print("  full reads with a state and a quiet start: %d of %d" % (len(pts), len(reads)))
    res = {}
    for k, what in ((2, "feeding window (c-1)"), (3, "shown window (c)")):
        st = [p[1] for p in pts]
        cl = [p[k] for p in pts]
        tab = collections.Counter(zip(st, cl))
        obs = chi2(st, cl)
        rng, hit = random.Random(357), 0
        sh = list(st)
        for _ in range(nperm):
            rng.shuffle(sh)
            hit += chi2(sh, cl) >= obs - 1e-12
        p = (hit + 1) / (nperm + 1)
        print("  state x class of the %s: %s; chi2 %.2f, p %.4f (%d)" % (what, "  ".join(
            "%s: %s" % (s, " ".join("%s %d" % (c, tab[(s, c)]) for c in CLASSES if any(tab[(x, c)] for x in set(st))))
            for s in sorted(set(st))), obs, p, nperm))
        res[what] = p
    return res


def selftest():
    rng = random.Random(1)

    def synth(planted):
        rows, t, state, frames = [], 0.0, "X", []
        for n in range(1800):
            if rng.random() < 0.4:
                state = "Y" if state == "X" else "X"
            frames.append((t, state))
            t += rng.uniform(0.031, 0.037)
        reads = []
        for n, (s, state) in enumerate(frames[:-1]):
            nxt_state = frames[n + 1][1]
            for k in range(9):
                rows.append((s + 0.001 * k, True, [False] * 5, []))
            e = s + 0.008
            first = (nxt_state == "X") if planted else (rng.random() < 0.5)
            ta, tp = (e + 0.002, e + 0.006) if first else (e + 0.006, e + 0.002)
            rows.append((tp, False, [True, True, True, True, True], []))
            rows.append((ta, False, [False] * 5, [(1, 3), (1, 4)]))
        rows.sort(key=lambda r: r[0])
        labels = {}
        for k in range(110):
            n = 10 + k * 15
            s, state = frames[n]
            name = "b01.z%d" % k
            reads.append((name, s + 0.02))
            labels[name] = state
        return rows, reads, labels

    print("# selftest 1: X frames fed by windows where the records change before the pyramid (AP), Y by PA; expect p ~0.0002 for the feeding window")
    r1 = analyse(*synth(True), 2000)
    print("# selftest 2: the order independent of the state; expect p well above 0.05")
    r2 = analyse(*synth(False), 2000)
    print("  -> planted p %.4f, null p %.4f" % (r1["feeding window (c-1)"], r2["feeding window (c-1)"]))


if sys.argv[1:2] == ["--selftest"]:
    selftest()
    sys.exit(0)
evp, tlp, lp = sys.argv[1:4]
nperm = int(sys.argv[4]) if len(sys.argv) > 4 else 2000
rows = parse(open(evp))
reads = []
for l in open(tlp):
    m = re.match(r"(\S+) wall ([\d.]+) mono ([\d.]+)", l)
    if m:
        reads.append(("b01.%s" % m[1], float(m[3])))
labels = json.load(open(lp))["labels"]
analyse(rows, reads, labels, nperm)
