#!/usr/bin/env python3
# BC5 experiment 0253: the depth-only writers' inline buffer descriptors, per draw position in the frame, by window
# state. wr0253.py showed that the writers' GS user data hold V#s inline, four dwords each (user data 0-3, 4-7, 8-11,
# 12-15, 16-19): dword 0 = base low, dword 1 = 0x00100011 (base high 0x11, STRIDE 16), dword 2 = NUM_RECORDS, dword 3 =
# format word (Mesa gfx10-rsrc.json @ 0866ae7: SQ_BUF_RSRC_WORD1 BASE_ADDRESS_HI [0,15], STRIDE [16,29]; WORD2
# NUM_RECORDS). This script reads the same journal lines as wr0253.py ("draw journal buf ... | ps", "bake ud gs",
# "bake table gs udK") and prints, per writer and per position of the draw among that writer's draws in its frame
# (frames split at the full-screen water draw, PS 0x11d01d7100):
#  - the NUM_RECORDS of each inline V# (clean / patched / mixed: distinct values and counts);
#  - for the per-draw record buffer at user data 0-3, its first 16 records (the journalled 64 dwords): how many
#    distinct records each state shows, and how many of the patched ones never appear in clean frames.
# Prints summaries only.
# usage: python3 -I rec0253.py <direct.log> <bench.txt> [writer pixel shaders]
import collections, re, sys, time

path, bench = sys.argv[1], sys.argv[2]
WRITERS = (sys.argv[3] if len(sys.argv) > 3 else "11d1d88300,11d1dd6400,11d090d900,11d0a98300").lower().split(",")
shots = []
for l in open(bench):
    m = re.match(r"\s*(\d{6})-(ts\d\d)\.png: patch\s+([\d.]+) %", l)
    if m:
        shots.append((m[1], m[2], float(m[3])))
WIN = re.compile(r"^draw journal window from buf (\d+): t ([\d.]+) wall (\d+)\.(\d+)")
DRAW = re.compile(r"^draw journal buf (\d+) \((\d+) dwords\) at (\d+):.*\| ps (\S+) ")
UD = re.compile(r"^bake ud gs buf (\d+) at (\d+):((?: [0-9a-f]{8})+)")
TAB = re.compile(r"^bake table gs ud0 ([0-9a-f]+):((?: [0-9a-f]{8})+)")


def state_of(hms):
    if hms is None:
        return "unknown"
    prev = [s for s in shots if s[0] <= hms]
    nxt = [s for s in shots if s[0] >= hms]
    p, n = (prev[-1] if prev else None), (nxt[0] if nxt else None)
    if p and n and p[2] < 5 and n[2] < 5:
        return "clean"
    if p and n and p[2] >= 8 and n[2] >= 8:
        return "patched"
    return "mixed"


hms, cur, pos = None, None, collections.Counter()
recs = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))   # (ps, k) -> slot -> Counter
rec0 = collections.defaultdict(lambda: collections.defaultdict(set))                   # (ps, k) -> state -> records
for line in open(path, errors="replace"):
    m = WIN.match(line)
    if m:
        hms = time.strftime("%H%M%S", time.localtime(int(m[3])))
        continue
    m = DRAW.match(line)
    if m:
        ps = m[4].lower()
        cur = None
        if ps == "11d01d7100":
            pos = collections.Counter()
        elif any(ps.startswith(w) for w in WRITERS):
            cur = {"ps": ps, "k": pos[ps], "state": state_of(hms)}
            pos[ps] += 1
        continue
    if cur is None:
        continue
    m = UD.match(line)
    if m:
        ud = [int(x, 16) for x in m[3].split()]
        for s in range(0, 20, 4):
            if ud[s + 1] == 0x00100011:
                recs[(cur["ps"], cur["k"])][s][(cur["state"], ud[s + 2])] += 1
        continue
    m = TAB.match(line)
    if m:
        d = m[2].split()
        for q in range(0, len(d) - 3, 4):
            rec0[(cur["ps"], cur["k"])][cur["state"]].add(" ".join(d[q:q + 4]))

print("# %s" % path)
for (ps, k) in sorted(recs):
    parts = []
    for s, c in sorted(recs[(ps, k)].items()):
        by = collections.defaultdict(list)
        for (st, n), cnt in c.items():
            by[st].append("%d x%d" % (n, cnt))
        parts.append("ud%d records %s" % (s, "; ".join("%s %s" % (st, ",".join(sorted(v))) for st, v in sorted(by.items()))))
    r = rec0[(ps, k)]
    cl, pa = r.get("clean", set()), r.get("patched", set())
    print("  %s #%d: %s | ud0 records: clean %d distinct, patched %d distinct, patched-only %d" % (
        ps, k, " | ".join(parts), len(cl), len(pa), len(pa - cl)))
