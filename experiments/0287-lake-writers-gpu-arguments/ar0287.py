#!/usr/bin/env python3
# BC5 experiment 0287: the depth writers' GPU-written indirect arguments, as capa0287.py read them from memory next to
# each depth read, against the read's hole state. Inputs: the capture directory (bNN.times.txt; bNN.aK.bin argument
# reads, their ranges listed in the times line), rd0287.py's read summary (JSON), and the run's journal for which
# writer draws through which argument address ("draw journal args buf N at P: op OP base1 B +0xO" after its "draw journal
# buf N ... at P: ... | ps PS" line; DRAW_INDIRECT 0x24 {vertex count, instance count, start vertex, start instance},
# DRAW_INDEX_INDIRECT 0x25 {index count, instance count, ...}, Mesa radv_cs_emit_indirect_draw_packet as edit0194.py
# cites).
# A depth read's state: at its best size when that is clear (rd0283.py: next-best shear >= 3 x best), by the share of
# the shots' cell mask at depth 0 as exp 0283's st0283.py: X-like >= 0.5, Y-like <= 0.3 with depth 0 on >= 0.15 of the
# lake window, none < 0.03, mixed otherwise; unclear sizes are left out. Each depth read zK is paired with the argument
# read aK taken just before it.
# Prints: the argument records (address, the writers drawing through it, how many draws); per record, how many
# distinct values its first two dwords take over all argument reads and how often they change between consecutive
# argument reads of a burst (25-30 ms apart); then X reads against Y reads: per record, exact separators (no shared
# value, >= 3 reads of each state, repeating values) and near separators (at most 4 values, mapped right in >= 90 %),
# with a permutation test (100 free shuffles of the states and every rotation along the reads' time order); and per
# writer the summed vertex counts in X and Y reads. Argument values in hex. Runs on the box (stdlib only).
# usage: python3 -I ar0287.py <capture dir> <reads json> <direct.log>
import collections, glob, json, os, random, re, statistics, struct, sys

cdir, rjson, log = sys.argv[1:4]
random.seed(287)
DRAW = re.compile(r"^draw journal buf (\d+) \((\d+) dwords\) at (\d+): .*\| ps ([0-9a-f]+) ")
ARGS = re.compile(r"^draw journal args buf (\d+) at (\d+): op (\S+) base1 ([0-9a-f]+) \+0x([0-9a-f]+)")
ps_of, rec = {}, collections.defaultdict(collections.Counter)
for l in open(log, errors="replace"):
    if not l.startswith("draw journal"):
        continue
    m = DRAW.match(l)
    if m:
        ps_of[(m[1], m[3])] = m[4]
        continue
    m = ARGS.match(l)
    if m and (m[1], m[2]) in ps_of:
        rec[int(m[4], 16) + int(m[5], 16)][(ps_of[(m[1], m[2])], m[3])] += 1
reads = {r["name"]: r for r in json.load(open(rjson))["reads"]}


def klass(r):
    if r is None or not r["clear"]:
        return "?"
    e = r["sizes"][str(r["best"])]
    if e["share"] < 0.03:
        return "0"
    if e["cells"] >= 0.5:
        return "X"
    if e["cells"] <= 0.3 and e["share"] >= 0.15:
        return "Y"
    return "m"


areads = []  # (burst, name, wall, {address: (dw0, dw1, dw2, dw3)})
for tf in sorted(glob.glob(os.path.join(cdir, "b*.times.txt"))):
    b = os.path.basename(tf).split(".")[0]
    for l in open(tf):
        m = re.match(r"(a\S+) wall ([\d.]+) .* ranges (.*)$", l)
        if not m or not os.path.exists(os.path.join(cdir, "%s.%s.bin" % (b, m[1]))):
            continue
        data = open(os.path.join(cdir, "%s.%s.bin" % (b, m[1])), "rb").read()
        vals, pos = {}, 0
        for part in m[3].split():
            a, n = (int(x, 16) for x in part.split(":"))
            for addr in rec:
                if a <= addr and addr + 16 <= a + n:
                    vals[addr] = struct.unpack_from("<4I", data, pos + addr - a)
            pos += n
        areads.append((b, m[1], float(m[2]), vals))
print("# %s: %d argument records from the journal, %d argument reads" % (cdir, len(rec), len(areads)))
for addr in sorted(rec):
    who = rec[addr]
    print("  %x: %s" % (addr, ", ".join("ps %s op %s x%d" % (ps, op, n) for (ps, op), n in who.most_common(3))))
# how the records change
print("# per record: distinct (count, instances) values over all reads; changes between consecutive reads of a burst")
for addr in sorted(rec):
    seq = [(b, v[addr][:2]) for b, n, w, v in areads if addr in v]
    ch = sum(1 for (b1, x), (b2, y) in zip(seq, seq[1:]) if b1 == b2 and x != y)
    pairs = sum(1 for (b1, _), (b2, _) in zip(seq, seq[1:]) if b1 == b2)
    dv = collections.Counter(x for _, x in seq)
    print("  %x: %d distinct (%s); changed in %d of %d consecutive pairs" % (
        addr, len(dv), " ".join("%x/%x x%d" % (k[0], k[1], c) for k, c in dv.most_common(4)), ch, pairs))
# X against Y
labelled = []  # (wall, state, values) for each depth read with a clear state, with the argument read just before it
for b, n, w, v in areads:
    if n == "aE":
        continue
    s = klass(reads.get("%s.z%s" % (b, n[1:])))
    if s in ("X", "Y"):
        labelled.append((w, s, v))
labelled.sort(key=lambda x: x[0])
states = [s for _, s, _ in labelled]
print("# X/Y: %d X reads and %d Y reads with their argument read just before" % (states.count("X"), states.count("Y")))
cols = {addr: [v.get(addr, (None,))[:2] for _, _, v in labelled] for addr in rec}


def seps(st):
    n, rows = 0, []
    for addr, vals in cols.items():
        a = [x for x, s in zip(vals, st) if s == "X" and x[0] is not None]
        b = [x for x, s in zip(vals, st) if s == "Y" and x[0] is not None]
        if len(a) < 3 or len(b) < 3 or len(set(a + b)) < 2:
            continue
        if not set(a) & set(b):
            if len(set(a)) + len(set(b)) <= (len(a) + len(b)) / 2:
                n += 1
                rows.append(("SEP", addr, a, b))
        elif len(set(a + b)) <= 4:
            right = sum(max(a.count(x), b.count(x)) for x in set(a + b))
            if right >= 0.9 * (len(a) + len(b)):
                rows.append(("NEAR %.2f" % (right / (len(a) + len(b))), addr, a, b))
    return n, rows


if states.count("X") >= 3 and states.count("Y") >= 3:
    n_real, rows = seps(states)
    shuf = []
    for _ in range(100):
        p = states[:]
        random.shuffle(p)
        shuf.append(seps(p)[0])
    rot = [seps(states[r:] + states[:r])[0] for r in range(1, len(states))]
    print("  exact separators %d (shuffles: median %s, max %d, share >= real %.2f; rotations: median %s, max %d, share >= real %.2f)" % (
        n_real, statistics.median(shuf), max(shuf), sum(x >= n_real for x in shuf) / len(shuf), statistics.median(rot),
        max(rot), sum(x >= n_real for x in rot) / len(rot)))
    for kind, addr, a, b in rows[:40]:
        print("  %s %x | X: %s | Y: %s" % (kind, addr, "; ".join("%x/%x x%d" % (k[0], k[1], c) for k, c in collections.Counter(a).most_common(3)),
                                           "; ".join("%x/%x x%d" % (k[0], k[1], c) for k, c in collections.Counter(b).most_common(3))))
    print("# per writer: the summed vertex (index) counts of its records, X reads | Y reads (sorted)")
    by_ps = collections.defaultdict(list)
    for addr, who in rec.items():
        for (ps, op), _ in who.items():
            by_ps[ps].append(addr)
    for ps, addrs in sorted(by_ps.items()):
        sx = sorted(sum(v.get(a, (0,))[0] for a in addrs) for _, s, v in labelled if s == "X")
        sy = sorted(sum(v.get(a, (0,))[0] for a in addrs) for _, s, v in labelled if s == "Y")
        print("  ps %s (%d records): X %s | Y %s" % (ps, len(addrs), " ".join("%d" % x for x in sx[:30]), " ".join("%d" % x for x in sy[:30])))
else:
    print("  too few reads of a state")
