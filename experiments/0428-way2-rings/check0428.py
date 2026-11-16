#!/usr/bin/env python3
"""BC5 experiment 0428: the rule, fixed before the runs (README "Rule").
    check0428.py rule <rows file> <set>
Rows (written by chain0428.sh): <tag> <CLASS> pad <n> fps <flips/s or -> gaps <s over 100 ms or -> exposure ...
The arm is the tag's fifth character: C control (BC5_DIRECT_ACB_RINGS=0, BC5_DIRECT_ACB_QUEUE_STATE=0), Q way 2
(BC5_DIRECT_ACB_RINGS=4, BC5_DIRECT_ACB_QUEUE_STATE=1). A replacement run (tag ending in R) counts for its arm.

smoke: PASS if the one Q run is NO_CRASH; anything else is FAIL (the class says why).
series: COMPLETE only with 4 C and 4 Q rows of class NO_CRASH.
  - Q FAILS if any Q row has a class other than NO_CRASH or NOT_ROUTED (KERNEL, CRASH_OTHER, WALL, TARGET, SETUP, OTHER).
  - Otherwise "not slower" HOLDS if the median of Q's flips/s >= the median of C's - 0.5, else Q is SLOWER.
  - Descriptive only beyond that (R13): 4 runs per arm say nothing about rare events, and the medians are not a cost estimate."""
import statistics, sys


def rows(path):
    out = []
    for line in open(path, encoding="utf-8", errors="replace"):
        f = line.split()
        if len(f) < 8 or f[2] != "pad" or f[4] != "fps":
            continue
        fps = None if f[5] == "-" else float(f[5])
        out.append({"tag": f[0], "arm": f[0][4], "cls": f[1], "pad": int(f[3]), "fps": fps, "gaps": f[7]})
    return out


def main():
    if len(sys.argv) != 4 or sys.argv[1] != "rule":
        print(__doc__)
        return 2
    rs, st = rows(sys.argv[2]), sys.argv[3]
    for r in rs:
        print("row %-9s arm %s %-12s fps %s gaps %s" % (r["tag"], r["arm"], r["cls"], r["fps"], r["gaps"]))
    if st == "smoke":
        q = [r for r in rs if r["arm"] == "Q"]
        if len(q) != 1:
            print("RULE smoke: OPEN (%d Q rows)" % len(q))
            return 0
        print("RULE smoke: %s (class %s)" % ("PASS" if q[0]["cls"] == "NO_CRASH" else "FAIL", q[0]["cls"]))
        return 0
    bad = [r for r in rs if r["arm"] == "Q" and r["cls"] not in ("NO_CRASH", "NOT_ROUTED")]
    if bad:
        print("RULE series: Q FAILS (%s)" % ", ".join("%s %s" % (r["tag"], r["cls"]) for r in bad))
        return 0
    c = [r["fps"] for r in rs if r["arm"] == "C" and r["cls"] == "NO_CRASH" and r["fps"] is not None]
    q = [r["fps"] for r in rs if r["arm"] == "Q" and r["cls"] == "NO_CRASH" and r["fps"] is not None]
    if len(c) < 4 or len(q) < 4:
        print("RULE series: OPEN (%d C and %d Q clean rows with fps; 4 each needed)" % (len(c), len(q)))
        return 0
    mc, mq = statistics.median(c), statistics.median(q)
    print("RULE series: COMPLETE; median flips/s C %.2f, Q %.2f (Q - C = %+.2f); not slower %s" % (mc, mq, mq - mc, "HOLDS" if mq >= mc - 0.5 else "FAILS: Q is SLOWER"))
    print("(descriptive, R13: 4 runs per arm; no claim about rare events)")
    return 0


sys.exit(main())
