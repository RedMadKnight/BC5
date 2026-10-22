#!/usr/bin/env python3
# usage: wsum2.py dump base cur sec nxt stk act link [nwaves]
import sys; sys.path.insert(0, "/home/kjaniszewski/bc5-work/exp0190")
from wparse import parse
from collections import Counter
f, base = sys.argv[1], int(sys.argv[2], 16)
cur, sec, nxt, stk, act, link = map(int, sys.argv[3:9]); nw = int(sys.argv[9]) if len(sys.argv) > 9 else 999
ws = parse(f)
print("PCs:", {hex(k): v for k, v in Counter(w["pc"] - base for w in ws).items()})
tot = Counter(); links = Counter()
for w in ws:
    s = w["sgpr"]; v = w["vgpr"]; a = s.get(act, 0)
    lanes = [i for i in range(32) if a >> i & 1]
    links[(s[link], s[link + 1], s[link + 2])] += 1
    c = Counter((v[cur][i], v[sec][i], v[stk][i] >> 16) for i in lanes)
    tot.update(c)
    if nw > 0:
        nw -= 1
        print("%s pc+%x exec %08x act %08x link %08x %08x %08x : %s" % (w["id"], w["pc"] - base, w["exec"], a, s[link], s[link+1], s[link+2],
              "; ".join("%dx cur %x sec %x sp %04x" % (n, x, y, z) for (x, y, z), n in c.most_common(4))))
print("lane states over all waves:", [("cur %x sec %x sp %04x" % k, n) for k, n in tot.most_common(12)])
print("link V#s:", [(" ".join("%08x" % x for x in k), n) for k, n in links.most_common(6)])
