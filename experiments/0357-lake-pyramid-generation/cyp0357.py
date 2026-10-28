#!/usr/bin/env python3
# BC5 experiment 0357, written after run P1's first look (cy0357.py's depth-gap cycles cut each 34 ms frame in two): the
# frames of pl0357.py's poll log cut at the pyramid's rebuild. P1's log shows, about every 34 ms: all five pyramid mips
# change in one poll; then the culling records change in clusters for 1-6 ms; then the depth writes begin (D), with a
# 100-record change at that moment; a second short D burst follows ~10 ms later. Some frames' record changes go on
# after the depth writes began.
#  - A cycle runs from a pyramid change (any mip, after >= 5 ms without one) to the next. tP its start, tD the first D
#    change after tP. Record changes in the cycle: "before" (tP <= t < tD - 0.5 ms), "at" (|t - tD| <= 0.5 ms), "late"
#    (t > tD + 1 ms, while the draws run); "late" cycles have at least one late record change.
#  - A full read shows the frame of the latest cycle whose first D change came before the read began. If the read
#    began less than 1 ms after a D change, it is left out (the depth may be mid-write).
#  - States: ph0357.py's labels with a hole-share floor: "0" (no holes), "A"/"B" (the two hole states).
#  - Tests: holes (A or B) against no holes, and A against B, each x late/on-time of the shown cycle; chi-square, p by
#    shuffling the reads' states (reads 0.5 s apart). Also the medians of tD - tP, of the late changes' delay after tD,
#    and the share of late cycles overall.
# Summaries only. usage: python3 -I cyp0357.py <events.txt> <b01.times.txt> <labels json> [permutations]
#                        python3 -I cyp0357.py --selftest
import bisect, collections, json, random, re, statistics, sys


def parse(lines):
    rows = []
    for l in lines:
        f = l.split()
        if len(f) < 5:
            continue
        rows.append((float(f[0]), f[2] == "D1", "1" in f[3][1:], 0 if f[4] == "A-" else len(f[4][1:].split(","))))
    rows.sort(key=lambda r: r[0])
    return rows


def cycles(rows):
    pts = [r[0] for r in rows if r[2]]
    starts = [t for i, t in enumerate(pts) if i == 0 or t - pts[i - 1] >= 0.005]
    ts = [r[0] for r in rows]
    cs = []
    for s, nxt in zip(starts, starts[1:]):
        inw = rows[bisect.bisect_left(ts, s):bisect.bisect_left(ts, nxt)]
        ds = [r[0] for r in inw if r[1]]
        if not ds:
            cs.append({"s": s, "next": nxt, "d": None, "dlast": None, "before": 0, "at": 0, "late": 0, "lated": []})
            continue
        td = ds[0]
        c = {"s": s, "next": nxt, "d": td, "dlast": ds[-1], "before": 0, "at": 0, "late": 0, "lated": []}
        for t, _, _, na in inw:
            if not na:
                continue
            if abs(t - td) <= 0.0005:
                c["at"] += na
            elif t > td + 0.001:
                c["late"] += na
                c["lated"].append(t - td)
            elif t < td - 0.0005:
                c["before"] += na
        cs.append(c)
    return cs


def chi2(a, b):
    n = len(a)
    sa, sb = sorted(set(a)), sorted(set(b))
    if len(sa) < 2 or len(sb) < 2:
        return 0.0
    t = 0.0
    for x in sa:
        for y in sb:
            e = a.count(x) * b.count(y) / n
            o = sum(1 for p, q in zip(a, b) if p == x and q == y)
            t += (o - e) ** 2 / e
    return t


def test(pairs, nperm, what):
    st = [p[0] for p in pairs]
    fl = [p[1] for p in pairs]
    tab = collections.Counter(pairs)
    obs = chi2(st, fl)
    rng, hit, sh = random.Random(357), 0, list(st)
    for _ in range(nperm):
        rng.shuffle(sh)
        hit += chi2(sh, fl) >= obs - 1e-12
    print("  %s: %s; chi2 %.2f, p %.4f (%d)" % (what, "  ".join(
        "%s: late %d on-time %d" % (s, tab[(s, "late")], tab[(s, "on-time")]) for s in sorted(set(st))), obs, (hit + 1) / (nperm + 1), nperm))
    return (hit + 1) / (nperm + 1)


def analyse(rows, reads, labels, nperm):
    cs = cycles(rows)
    ok = [c for c in cs if c["d"] is not None]
    print("# %d cycles cut at the pyramid's rebuild, %d with depth writes" % (len(cs), len(ok)))
    if len(ok) < 5:
        print("  too few cycles")
        return None
    per = sorted(c["next"] - c["s"] for c in cs)
    print("  cycle period: median %.1f ms, quartiles %.1f / %.1f; depth writes start %.1f ms after the rebuild (median)" % (
        1000 * per[len(per) // 2], 1000 * per[len(per) // 4], 1000 * per[3 * len(per) // 4], 1000 * statistics.median(c["d"] - c["s"] for c in ok)))
    late = [c for c in ok if c["late"]]
    print("  late cycles (culling records change > 1 ms after the depth writes began): %d of %d (%.0f %%); their first late change %.1f ms after the start (median); records: before %.0f, at %.0f, late %.0f (medians over late cycles)" % (
        len(late), len(ok), 100 * len(late) / len(ok), 1000 * statistics.median(min(c["lated"]) for c in late) if late else float("nan"),
        statistics.median(c["before"] for c in late) if late else float("nan"), statistics.median(c["at"] for c in late) if late else float("nan"),
        statistics.median(c["late"] for c in late) if late else float("nan")))
    ds = [c["d"] for c in ok]
    pairs = []
    for name, t in reads:
        if name not in labels:
            continue
        k = bisect.bisect_right(ds, t) - 1
        if k < 0:
            continue
        c = ok[k]
        drows = [r[0] for r in rows if r[1] and c["d"] <= r[0] <= t]
        if drows and t - drows[-1] < 0.001:
            continue
        pairs.append((labels[name], "late" if c["late"] else "on-time"))
    print("  full reads placed: %d of %d; states %s" % (len(pairs), len(reads), dict(collections.Counter(p[0] for p in pairs))))
    res = {}
    hp = [("holes" if s in "AB" else "none", f) for s, f in pairs]
    res["holes"] = test(hp, nperm, "holes vs none x late/on-time")
    ab = [(s, f) for s, f in pairs if s in "AB"]
    if len({s for s, _ in ab}) == 2:
        res["ab"] = test(ab, nperm, "A vs B x late/on-time")
    return res


def selftest():
    rng = random.Random(2)

    def synth(planted):
        rows, t, labels, reads, frames = [], 0.0, {}, [], []
        state = "0"
        for n in range(1700):
            if rng.random() < 0.3:
                state = rng.choice("0AB")
            late = (state != "0") if planted else rng.random() < 0.4
            rows.append((t, False, True, 0))
            rows.append((t + 0.002, False, False, 40))
            td = t + 0.004
            rows.append((td, True, False, 100))
            rows.append((td + 0.0001, True, False, 0))
            if late:
                rows.append((td + 0.003, False, False, 30))
            rows.append((td + 0.010, True, False, 0))
            frames.append((td + 0.012, state))
            t += rng.uniform(0.032, 0.036)
        rows.sort(key=lambda r: r[0])
        for k in range(115):
            tr, state = frames[10 + k * 14]
            nm = "b01.z%d" % k
            reads.append((nm, tr))
            labels[nm] = state
        return rows, reads, labels

    print("# selftest 1: late culling changes in frames with holes only; expect holes-vs-none p ~0.0005")
    r1 = analyse(*synth(True), 2000)
    print("# selftest 2: late changes independent of the state; expect p well above 0.05")
    r2 = analyse(*synth(False), 2000)
    print("  -> planted p %.4f, null p %.4f" % (r1["holes"], r2["holes"]))


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
analyse(rows, reads, json.load(open(lp))["labels"], nperm)
