#!/usr/bin/env python3
# BC5 experiment 0262: the night lake's full-screen water draw (PS 0x11d01d7100), clean against patched frames of one
# run, dword by dword. Reads a journal filtered on that draw (patch 0001: "draw journal buf N ... | ps 11d01d7100 ...",
# then "bake ud ps|gs buf N at P: <32 dwords>" (SPI_SHADER_USER_DATA_PS_0.. sh 0x0c, _GS_0.. sh 0x8c; on gfx10 the
# vertex stage's user data are the GS registers) and "bake table ps|gs udK <addr>: <64 dwords>"; patch0245.py's
# "bake db buf N at P: ..." line; edit0194.py's window lines). Window state from the bench's shots (exp 0197's metric).
# For each dword (user data, every table's 64 dwords keyed by stage and user-data slot, and the depth-state fields of
# the bake-db line) it counts the distinct values in clean and in patched frames and how many values of one state
# never occur in the other. A dword whose patched values are all absent from the clean frames, with both sets stable,
# is a constant that separates the states. Prints counts, and for separating dwords their ranges as float and integer.
# usage: python3 -I fs0262.py <direct.log> <bench.txt>
import collections, re, struct, sys, time

path, bench = sys.argv[1], sys.argv[2]
FS = "11d01d7100"
shots = []
for l in open(bench):
    m = re.match(r"\s*(\d{6})-(ts\d\d)\.png: patch\s+([\d.]+) %", l)
    if m:
        shots.append((m[1], float(m[3])))
WIN = re.compile(r"^draw journal window from buf (\d+): t ([\d.]+) wall (\d+)\.(\d+)")
DRAW = re.compile(r"^draw journal buf (\d+) \((\d+) dwords\) at (\d+):((?: [0-9a-f]{8})*) \|.*\| ps (\S+) ")
UD = re.compile(r"^bake ud (ps|gs) buf (\d+) at (\d+):((?: [0-9a-f]{8})+)")
TAB = re.compile(r"^bake table (ps|gs) ud(\d+) ([0-9a-f]+):((?: [0-9a-f]{8})+)")
DB = re.compile(r"^bake db buf (\d+) at (\d+): (.*)$")


def state_of(hms):
    if hms is None:
        return "unknown"
    prev = [s for s in shots if s[0] <= hms]
    nxt = [s for s in shots if s[0] >= hms]
    p, n = (prev[-1] if prev else None), (nxt[0] if nxt else None)
    if p and n and p[1] < 5 and n[1] < 5:
        return "clean"
    if p and n and p[1] >= 8 and n[1] >= 8:
        return "patched"
    return "mixed"


vals = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))  # key -> state -> Counter
hms, cur, n_state = None, None, collections.Counter()
for line in open(path, errors="replace"):
    m = WIN.match(line)
    if m:
        hms = time.strftime("%H%M%S", time.localtime(int(m[3])))
        continue
    m = DRAW.match(line)
    if m:
        cur = None
        if m[5].lower() == FS:
            cur = state_of(hms)
            n_state[cur] += 1
            words = m[4].split()
            for k, w in enumerate(words):
                vals[("packet", k)][cur][w] += 1
        continue
    if cur is None:
        continue
    m = UD.match(line)
    if m:
        for k, w in enumerate(m[4].split()):
            vals[("ud " + m[1], k)][cur][w] += 1
        continue
    m = TAB.match(line)
    if m:
        vals[("table %s ud%s" % (m[1], m[2]), "address")][cur][m[3]] += 1
        for k, w in enumerate(m[4].split()):
            vals[("table %s ud%s" % (m[1], m[2]), k)][cur][w] += 1
        continue
    m = DB.match(line)
    if m:
        for f in re.findall(r"(\w+) ([0-9a-f]{8,10})\b", m[3]):
            vals[("db", f[0])][cur][f[1]] += 1


def f32(h):
    try:
        return struct.unpack("<f", struct.pack("<I", int(h, 16) & 0xffffffff))[0]
    except (ValueError, struct.error):
        return float("nan")


print("# %s: full-screen draws by state: %s" % (path, ", ".join("%s %d" % kv for kv in sorted(n_state.items()))))
const_same, varying, separating = 0, [], []
for key in sorted(vals, key=lambda k: (k[0], str(k[1]))):
    c, p = vals[key].get("clean", collections.Counter()), vals[key].get("patched", collections.Counter())
    if not c or not p:
        continue
    sc, sp = set(c), set(p)
    if len(sc) == 1 and sc == sp:
        const_same += 1
        continue
    only_p, only_c = sp - sc, sc - sp
    varying.append((key, len(sc), len(sp), len(only_p), len(only_c)))
    if sp and not (sp & sc):
        separating.append((key, sc, sp))
print("dwords constant and equal in clean and patched frames: %d" % const_same)
print("dwords that vary (clean distinct, patched distinct, patched-only values, clean-only values):")
for key, a, b, op, oc in varying:
    print("  %-22s %-8s clean %4d patched %4d | patched-only %4d clean-only %4d" % (key[0], key[1], a, b, op, oc))
print("dwords whose patched values never occur in clean frames: %d" % len(separating))
for key, sc, sp in separating:
    fc = sorted(f32(x) for x in sc)
    fp = sorted(f32(x) for x in sp)
    print("  %-22s %-8s clean %d values (float %.6g..%.6g) | patched %d values (float %.6g..%.6g)" % (
        key[0], key[1], len(sc), fc[0], fc[-1], len(sp), fp[0], fp[-1]))
