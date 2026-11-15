#!/usr/bin/env python3
"""BC5 exp 0425: the rule fixed before the runs (README, "Rule"). Reads chain0425.sh's rows:
    <tag> <CLASS> pad <n> fix-off <n> pass-through <n> catcher-on <n> C1-on <n> C1-set-ok <n> C1-hi-ok <n> C2-on <n>
    C2-lines <n> C3-on <n> crash-type-taken <n>
usage: check0425.py rule <rows>"""
import sys

# arm letter: (name, planned runs, exposure counts that must all be above 0)
ARMS = {"C": ("control", 3, ()),
        "L": ("P1 PlayGo locus slow", 4, ("P1-on", "P1-calls")), "F": ("P2 PlayGo prefetch 500 ms", 4, ("P2-on", "P2-calls")),
        "K": ("P3 PlayGo call cost 200 us", 4, ("P3-on", "pg-calls")),
        "S": ("C1 wake slice 200 us", 4, ("C1-hi-ok",)), "Y": ("C2 handoff 300 us", 4, ("C2-lines",)),
        "D": ("C3 direct wake", 4, ("C3-on",))}


def parse(path):
    rows = []
    for line in open(path, encoding="utf-8"):
        f = line.split()
        if len(f) < 2 or not f[0].startswith("f425"):
            continue
        kv = {f[i]: f[i + 1] for i in range(2, len(f) - 1, 2)}
        rows.append((f[0], f[1], kv))
    return rows


def num(kv, k):
    try:
        return int(kv.get(k, ""))
    except ValueError:
        return -1  # missing or unreadable: unknown, never 0 (R19)


def rule(path):
    rows = parse(path)
    by = {a: [r for r in rows if r[0][4] == a and r[1] != "NOT_ROUTED"] for a in ARMS}
    # every counted run must show the fix off and the catcher armed (the pass-through hook), or the run tested nothing
    bad = [r[0] for r in rows if r[1] in ("TARGET", "NO_CRASH") and (num(r[2], "fix-off") < 1 or num(r[2], "pass-through") < 1
                                                                       or num(r[2], "catcher-on") < 1)]
    for t in bad:
        print(f"{t}: NO TEST, the fix-off / pass-through / catcher lines are missing")
    ctl = [r for r in by["C"] if r[0] not in bad]
    site = sum(r[1] == "TARGET" for r in ctl)
    print(f"control: {site} of {len(ctl)} at the site (want at least 2 of 3)")
    if site < 2:
        print("RULE NO CONCLUSION: the control did not crash at least 2 of 3 times")
        return 0
    for a, (name, want, expo) in ARMS.items():
        if a == "C":
            continue
        rs = [r for r in by[a] if r[0] not in bad]
        if not rs and not any(r[0][4] == a for r in rows):
            continue  # an arm of the other set
        clean = [r for r in rs if r[1] == "NO_CRASH"]
        hit = sum(r[1] == "TARGET" for r in rs)
        other = [r for r in rs if r[1] not in ("NO_CRASH", "TARGET")]
        exposed = [r for r in rs if all(num(r[2], k) > 0 for k in expo)]
        if hit:
            v = "REFUTED"
        elif len(exposed) < len(rs) or not rs:
            v = "NO TEST"  # a run without the candidate's own line tested nothing
        elif len(clean) == want and not other:
            v = "HOLDS"
        else:
            v = "OPEN"
        print(f"RULE arm {a} ({name}) {v}: {len(clean)} clean, {hit} at the site, {len(other)} other, {len(exposed)} exposed, of {len(rs)} (want {want})")
    print("catcher (descriptive, R11): crash-type jobs the owner took per run: " +
          " ".join(f"{r[0]}={r[2].get('crash-type-taken', '?')}" for r in rows))
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "rule":
        sys.exit(__doc__)
    sys.exit(rule(sys.argv[2]))
