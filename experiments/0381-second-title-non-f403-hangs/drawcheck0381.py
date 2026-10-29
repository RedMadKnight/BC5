#!/usr/bin/env python3
# BC5 exp 0381: in a devcoredump's hung IB (IB #0, the host's filtered IB), list every DRAW_INDIRECT /
# DRAW_INDEX_INDIRECT with the CP check the host put before it (experiment 0057: WRITE_DATA flag = 1, COND_WRITE
# count > limit ? flag = 0 per checked dword, WRITE_DATA confirm, PFP_SYNC_ME, COND_EXEC flag over the draw;
# bc5/indirect_check.hpp). Prints offsets, the COND_WRITEs' poll addresses and references, the COND_EXEC's address and
# count, the draw's data offset and the SET_BASE 1 in effect. Structure only, no payload.
# usage: python3 drawcheck0381.py <devcoredump.txt>
import sys

lines = open(sys.argv[1], errors="replace").read().split("\n")
start = next(i for i, l in enumerate(lines) if l.startswith("IB #0 "))
n = int(lines[start].split()[3])
ib = [int(x, 16) for x in lines[start + 1:start + 1 + n]]
pk = []
i = 0
while i < len(ib):
    h = ib[i]
    t = h >> 30
    ln = 1
    if t in (0, 3):
        c = (h >> 16) & 0x3fff
        ln = 1 if c == 0x3fff else c + 2
    pk.append((i, t, (h >> 8) & 0xff, ib[i:i + ln]))
    i += ln
base1 = 0
draws = checked = 0
for k, (at, t, op, p) in enumerate(pk):
    if t != 3:
        continue
    if op == 0x11 and len(p) >= 4 and (p[1] & 0xf) == 1:
        base1 = (p[2] & ~3) | ((p[3] & 0xffff) << 32)
    if op in (0x24, 0x25) and len(p) == 5:
        draws += 1
        prev = [q for q in pk[max(0, k - 8):k] if q[1] == 3]
        cw = [q for q in prev if q[2] == 0x45]
        ce = [q for q in prev if q[2] == 0x22]
        desc = []
        for q in cw:
            a = (q[3][2] & ~3) | ((q[3][3] & 0xffff) << 32)
            desc.append("COND_WRITE fn %d poll 0x%x ref %d" % (q[3][1] & 7, a, q[3][4]))
        for q in ce:
            desc.append("COND_EXEC 0x%x count %d" % (q[3][1] | ((q[3][2] & 0xffff) << 32), q[3][4] & 0x3fff))
        if cw and ce:
            checked += 1
        print("%6d op 0x%02x data_offset 0x%x base1 0x%x args 0x%x | %s" % (
            at, op, p[1], base1, base1 + p[1], "; ".join(desc) or "NO CHECK"))
print("draws %d, with a COND_WRITE + COND_EXEC check in the 8 packets before: %d" % (draws, checked))
