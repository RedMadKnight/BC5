#!/usr/bin/env python3
# BC5 experiment 0287: from a draw journal (edit0194.py's "draw journal args" lines after each "draw journal buf" line),
# per writer pixel shader: the SET_BASE index-1 bases its indirect draws read their arguments through, and the offsets
# (base1 + offset = the argument address), with counts; and the address range all writers' arguments span.
# usage: python3 -I base0287.py <direct.log>
import collections, re, sys

DRAW = re.compile(r"^draw journal buf (\d+) \((\d+) dwords\) at (\d+): .*\| ps ([0-9a-f]+) ")
ARGS = re.compile(r"^draw journal args buf (\d+) at (\d+): op (\S+) base1 ([0-9a-f]+) \+0x([0-9a-f]+)")
ps_of, per = {}, collections.defaultdict(collections.Counter)
lo, hi = None, None
for l in open(sys.argv[1], errors="replace"):
    if not l.startswith("draw journal"):
        continue
    m = DRAW.match(l)
    if m:
        ps_of[(m[1], m[3])] = m[4]
        continue
    m = ARGS.match(l)
    if m and (m[1], m[2]) in ps_of:
        b, o = int(m[4], 16), int(m[5], 16)
        per[ps_of[(m[1], m[2])]][(b, o, m[3])] += 1
        a = b + o
        lo, hi = (a if lo is None else min(lo, a)), (a + 32 if hi is None else max(hi, a + 32))
print("# %s: %d writer shaders with indirect draws; argument addresses %x..%x" % (sys.argv[1], len(per), lo or 0, hi or 0))
for ps, c in sorted(per.items()):
    bases = collections.Counter(b for (b, o, op) in c.elements())
    offs = sorted({o for (b, o, op) in c})
    print("  ps %s: %d draws; op %s; base1 %s; offsets %d distinct, 0x%x..0x%x" % (
        ps, sum(c.values()), ",".join(sorted({op for (b, o, op) in c})), " ".join("%x x%d" % kv for kv in bases.most_common(3)),
        len(offs), offs[0], offs[-1]))
