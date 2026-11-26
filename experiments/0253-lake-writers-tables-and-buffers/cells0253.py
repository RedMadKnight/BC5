#!/usr/bin/env python3
# BC5 experiment 0253: the depth-only writers' per-draw records as cells, compared between runs and window states.
# rec0253.py: each writer draw carries an inline V# at GS user data 0-3 (STRIDE 16, NUM_RECORDS = user data 2) whose
# first 64 dwords the journal holds ("bake table gs ud0"), i.e. its first 16 records. A record's dwords 2 and 3 are
# integral floats in a few tens (grid coordinates, as read here) and dword 0 a small flag word (1, 0x2040, 0x2050).
# Only draws with at most 16 records are used, so each is seen whole. A cell is (writer shader, dword 0, dword 2,
# dword 3) with the floats as written; dword 1 varies more and is left out unless FULL=1.
# For each journal (run tag = file argument order) and window state it collects the cells per frame (frames split at
# the full-screen water draw) and prints: cells per frame (median), distinct cells, and the overlaps between the
# (run, state) groups: cells every frame of one group has that no frame of the other has.
# Prints counts only.
# usage: python3 -I cells0253.py <tag>=<direct.log>:<bench.txt> [...]
import collections, os, re, statistics, struct, sys, time

WRITERS = tuple(os.environ.get("WRITERS", "11d1d88300,11d1dd6400,11d090d900,11d0a98300").lower().split(","))  # pixel-shader prefixes
FULL = os.environ.get("FULL") == "1"  # also key on dword 1
WIN = re.compile(r"^draw journal window from buf (\d+): t ([\d.]+) wall (\d+)\.(\d+)")
DRAW = re.compile(r"^draw journal buf (\d+) \((\d+) dwords\) at (\d+):.*\| ps (\S+) ")
UD = re.compile(r"^bake ud gs buf (\d+) at (\d+):((?: [0-9a-f]{8})+)")
TAB = re.compile(r"^bake table gs ud0 ([0-9a-f]+):((?: [0-9a-f]{8})+)")


def f32(h):
    return struct.unpack("<f", struct.pack("<I", int(h, 16)))[0]


groups = collections.defaultdict(list)      # (tag, state) -> list of frame cell sets
for arg in sys.argv[1:]:
    tag, rest = arg.split("=", 1)
    path, bench = rest.split(":", 1)
    shots = []
    for l in open(bench):
        m = re.match(r"\s*(\d{6})-(ts\d\d)\.png: patch\s+([\d.]+) %", l)
        if m:
            shots.append((m[1], float(m[3])))

    def state_of(hms):
        prev = [s for s in shots if s[0] <= hms] if hms else []
        nxt = [s for s in shots if s[0] >= hms] if hms else []
        p, n = (prev[-1] if prev else None), (nxt[0] if nxt else None)
        if p and n and p[1] < 5 and n[1] < 5:
            return "clean"
        if p and n and p[1] >= 8 and n[1] >= 8:
            return "patched"
        return "mixed"

    hms, cur, frame, fstate = None, None, None, None
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
                if frame is not None:
                    groups[(tag, fstate)].append(frame)
                frame, fstate = set(), state_of(hms)
            elif any(ps.startswith(w) for w in WRITERS) and frame is not None:
                cur = {"ps": ps, "n": None}
            continue
        if cur is None:
            continue
        m = UD.match(line)
        if m:
            ud = [int(x, 16) for x in m[3].split()]
            cur["n"] = ud[2] if ud[1] == 0x00100011 else None
            continue
        m = TAB.match(line)
        if m and cur["n"] is not None and cur["n"] <= 16:
            d = m[2].split()
            for q in range(cur["n"]):
                frame.add((cur["ps"], d[4 * q], f32(d[4 * q + 2]), f32(d[4 * q + 3])) + ((d[4 * q + 1],) if FULL else ()))
            cur = None

print("# cells per frame and distinct cells, per run and window state (writer draws with <= 16 records)")
for k, frames in sorted(groups.items()):
    allc = set().union(*frames) if frames else set()
    every = set.intersection(*frames) if frames else set()
    per_ps = collections.Counter(c[0] for c in allc)
    print("  %-14s %3d frames: %s cells/frame (median), %d distinct, %d in every frame; distinct by writer %s" % (
        "%s %s" % k, len(frames), statistics.median(len(f) for f in frames) if frames else "-", len(allc), len(every),
        ", ".join("%s %d" % kv for kv in sorted(per_ps.items()))))
keys = sorted(groups)
print("# cells in every frame of A and in no frame of B (A -> B)")
for a in keys:
    for b in keys:
        if a == b or not groups[a] or not groups[b]:
            continue
        ea = set.intersection(*groups[a])
        ub = set().union(*groups[b])
        miss = ea - ub
        by = collections.Counter(c[0] for c in miss)
        print("  %-14s -> %-14s %3d of %3d (%s)" % ("%s %s" % a, "%s %s" % b, len(miss), len(ea), ", ".join("%s %d" % kv for kv in sorted(by.items())) or "-"))
