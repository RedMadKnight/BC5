#!/usr/bin/env python3
# BC5 experiment 0253: what the night lake's depth-only writers read, from a draw journal filtered on them
# (BC5_DIRECT_DRAW_JOURNAL with _PS=...; exps 0248/0251 runs H1, W251a, W251b). Patch 0001's journal prints, after each
# matched draw's "draw journal buf N (D dwords) at P: ... | ps <ps> ..." line, "bake ud ps|gs buf N at P: <32 dwords>"
# (SPI_SHADER_USER_DATA_PS_0.. sh 0x0c, _GS_0.. sh 0x8c) and, for each user-data pair that is a readable guest
# address, "bake table ps|gs udK <addr>: <64 dwords>"; edit0194.py adds "draw journal args buf N at P: ... | [args]"
# and "draw journal window from buf N: t T wall S.MS".
# Descriptors are decoded as exp 0212's desc0212.py does (Mesa src/amd/registers/gfx10-rsrc.json @ 0866ae7):
#   buffer V#: base = dword0 | (dword1 & 0xffff) << 32, STRIDE dword1 [16,29], NUM_RECORDS dword2, FORMAT dword3
#              [12,18], TYPE dword3 [30,31] = 0;
#   image T#:  base = (dword0 | (dword1 & 0xff) << 32) << 8, FORMAT dword1 [20,28], TYPE dword3 [28,31] in 8..13.
# Per writer pixel shader it prints:
#  (1) the user-data slots and their values: constant over all draws, or how many distinct values;
#  (2) per table (stage, user-data slot): how many distinct table addresses, the descriptors found in it (each distinct
#      one once, with its draw count), and its other dwords: constant, or varying (distinct values over the draws);
#  (3) for every varying table dword, its values split by window state (clean: shots before and after under 5 %;
#      patched: both 8 % or more, exp 0197's metric): distinct count and range as float and as integer, so a per-draw
#      constant (a cell's position, size or LOD) that differs between the states shows.
# Prints summaries only (counts, ranges, descriptor fields), never whole tables.
# usage: python3 -I wr0253.py <direct.log> <bench.txt> [writer pixel shaders, default the four of exp 0245]
import collections, re, struct, sys, time

path, bench = sys.argv[1], sys.argv[2]
WRITERS = (sys.argv[3] if len(sys.argv) > 3 else "11d1d88300,11d1dd6400,11d090d900,11d0a98300").lower().split(",")
shots = []
for l in open(bench):
    m = re.match(r"\s*(\d{6})-(ts\d\d)\.png: patch\s+([\d.]+) %", l)
    if m:
        shots.append((m[1], m[2], float(m[3])))
WIN = re.compile(r"^draw journal window from buf (\d+): t ([\d.]+) wall (\d+)\.(\d+)")
DRAW = re.compile(r"^draw journal buf (\d+) \((\d+) dwords\) at (\d+):.*\| ps (\S+) ")
UD = re.compile(r"^bake ud (ps|gs) buf (\d+) at (\d+):((?: [0-9a-f]{8})+)")
TAB = re.compile(r"^bake table (ps|gs) ud(\d+) ([0-9a-f]+):((?: [0-9a-f]{8})+)")


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


draws, cur, hms = [], None, None
for line in open(path, errors="replace"):
    m = WIN.match(line)
    if m:
        hms = time.strftime("%H%M%S", time.localtime(int(m[3])))
        continue
    m = DRAW.match(line)
    if m:
        cur = None
        if any(m[4].lower().startswith(w) for w in WRITERS):
            cur = {"ps": m[4].lower(), "state": state_of(hms), "ud": {}, "tab": {}}
            draws.append(cur)
        continue
    if cur is None:
        continue
    m = UD.match(line)
    if m:
        cur["ud"][m[1]] = [int(x, 16) for x in m[4].split()]
        continue
    m = TAB.match(line)
    if m:
        cur["tab"][(m[1], int(m[2]))] = (m[3], [int(x, 16) for x in m[4].split()])


def descriptors(d):
    out, k = {}, 0
    while k + 3 < len(d):
        d0, d1, d2, d3 = d[k:k + 4]
        typ = d3 >> 28
        if 8 <= typ <= 13 and (d1 >> 20) & 0x1ff and k % 8 == 0 and k + 7 < len(d):
            base = (d0 | (d1 & 0xff) << 32) << 8
            w, h = ((d2 & 0xfff) << 2 | d1 >> 30) + 1, ((d2 >> 14) & 0x3fff) + 1
            out[k] = "image 0x%x %dx%d fmt %d" % (base, w, h, (d1 >> 20) & 0x1ff)
            k += 8
            continue
        base = d0 | (d1 & 0xffff) << 32
        if (d3 >> 30) == 0 and (d3 >> 12) & 0x7f and 0x1000000000 <= base < 0x9000000000 and d2:
            out[k] = "buffer 0x%x stride %d records %d fmt %d" % (base, (d1 >> 16) & 0x3fff, d2, (d3 >> 12) & 0x7f)
            k += 4
            continue
        k += 1
    return out


def f32(v):
    return struct.unpack("<f", struct.pack("<I", v))[0]


def rng(vals):
    fl = [f32(v) for v in vals]
    fl = [x for x in fl if x == x and abs(x) < 1e30]
    fs = "float %.6g..%.6g" % (min(fl), max(fl)) if fl else "float -"
    return "%d distinct; %s; int %d..%d" % (len(set(vals)), fs, min(vals), max(vals))


print("# %s: %d writer draws (%s)" % (path, len(draws), ", ".join("%s %d" % kv for kv in sorted(collections.Counter(d["state"] for d in draws).items()))))
for ps in WRITERS:
    mine = [d for d in draws if d["ps"] == ps]
    if not mine:
        continue
    print("== ps %s: %d draws (%s)" % (ps, len(mine), ", ".join("%s %d" % kv for kv in sorted(collections.Counter(d["state"] for d in mine).items()))))
    for st in ("gs", "ps"):
        rows = [d["ud"][st] for d in mine if st in d["ud"]]
        if not rows:
            continue
        cols = list(zip(*rows))
        desc = ["%d:%s" % (k, "%08x" % c[0] if len(set(c)) == 1 else "<%d values>" % len(set(c))) for k, c in enumerate(cols) if any(c)]
        print("  (1) %s user data: %s" % (st, " ".join(desc)))
    keys = sorted({k for d in mine for k in d["tab"]})
    for key in keys:
        rows = [(d["state"], d["tab"][key]) for d in mine if key in d["tab"]]
        addrs = collections.Counter(a for _, (a, _) in rows)
        print("  (2) table %s ud%d: %d draws, %d distinct addresses" % (key[0], key[1], len(rows), len(addrs)))
        dc = collections.Counter()
        for _, (_, d) in rows:
            for k, s in descriptors(d).items():
                dc[(k, s)] += 1
        for (k, s), n in sorted(dc.items()):
            print("      dword %2d: %s (%d draws)" % (k, s, n))
        covered = {k + j for (k, s) in dc for j in range(8 if s.startswith("image") else 4)}
        cols = list(zip(*[d for _, (_, d) in rows]))
        const = [k for k, c in enumerate(cols) if len(set(c)) == 1 and k not in covered]
        vary = [k for k, c in enumerate(cols) if len(set(c)) > 1 and k not in covered]
        print("      other dwords: %d constant, %d varying (%s)" % (len(const), len(vary), " ".join(map(str, vary)) or "-"))
        for k in vary:
            by = collections.defaultdict(list)
            for stt, (_, d) in rows:
                by[stt].append(d[k])
            print("    (3) dword %2d: %s" % (k, " | ".join("%s %s" % (stt, rng(v)) for stt, v in sorted(by.items()))))
