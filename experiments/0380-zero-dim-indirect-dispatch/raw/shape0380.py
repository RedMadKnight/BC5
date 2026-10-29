#!/usr/bin/env python3
# BC5 experiment 0380 (F601): counts over private dcb dumps, CPU only, prints counts and offsets (no dump content).
# Per dcb file:
# - cc_at: offsets of CONTEXT_CONTROL 0x80000000 packets (one per host prefix);
# - prefix: dword 0 is CONTEXT_CONTROL 0xC0012800 0x80000000 0x80000000, then CLEAR_STATE 0xC0001200;
#   the prefix ends after its first SET_UCONFIG_REG 0x261 (VGT_TF_MEMORY_BASE_HI, tf_ring_prefix) in the first 4096 dwords;
# - in the title part: SET_BASE index 1 (0x11) positions, COND_EXEC (0x22, len 5) ranges, GFX-form
#   DISPATCH_INDIRECT (0x16, len 3), INDEX_BASE (0x26), draws;
# - shape B: the first GFX-form DISPATCH_INDIRECT of the title part comes before any SET_BASE index 1 of its own.
# usage: python3 shape0380.py <file>...   (prints one line per file, then totals)
import struct, sys

DRAWS = {0x15, 0x16, 0x24, 0x25, 0x27, 0x2c, 0x2d, 0x35, 0x38}
DRAWS.discard(0x16)  # a dispatch is not a draw


def packets(d, start=0):
    i = start
    while i < len(d):
        h = d[i]
        t = h >> 30
        n = 1
        if t in (0, 3):
            c = (h >> 16) & 0x3fff
            n = 1 if c == 0x3fff else c + 2
        if i + n > len(d):
            return
        yield i, h, t, (h >> 8) & 0xff, n
        i += n


tot = dict(files=0, prefixed=0, drawing=0, shape=0, sb1=0, sb1_in_cond=0, di=0, di_unbased=0, cond=0)
for p in sys.argv[1:]:
    b = open(p, "rb").read()
    d = struct.unpack("<%dI" % (len(b) // 4), b[: len(b) // 4 * 4])
    tot["files"] += 1
    pref = len(d) >= 5 and d[0] == 0xC0012800 and d[1] == 0x80000000 and d[2] == 0x80000000 and d[3] == 0xC0001200
    start = 0
    if pref:
        for i, h, t, op, n in packets(d):
            if i > 4096:
                break
            if t == 3 and op == 0x79 and n >= 3 and (d[i + 1] & 0xffff) == 0x261:
                start = i + n  # the first one: tf_ring_prefix's last packet
                break
    conds, sb1, di, draw, ib = [], [], [], False, []
    for i, h, t, op, n in packets(d, start):
        if t != 3:
            continue
        if op == 0x22 and n == 5:
            conds.append((i + n, i + n + (d[i + 4] & 0x3fff)))
        elif op == 0x11 and n >= 4 and (d[i + 1] & 0xf) == 1:
            sb1.append(i)
        elif op == 0x16 and n == 3:
            di.append(i)
        elif op == 0x26:
            ib.append(i)
        elif op in DRAWS:
            draw = True
    in_cond = sum(1 for s in sb1 if any(a <= s < e for a, e in conds))
    shape = bool(di) and (not sb1 or di[0] < sb1[0])
    unbased = sum(1 for x in di if not any(s < x for s in sb1))
    tot["prefixed"] += pref
    tot["drawing"] += draw
    tot["shape"] += shape
    tot["sb1"] += len(sb1)
    tot["sb1_in_cond"] += in_cond
    tot["di"] += len(di)
    tot["di_unbased"] += unbased
    tot["cond"] += len(conds)
    cc = [i for i, h, t, op, n in packets(d) if t == 3 and op == 0x28 and n == 3 and d[i + 1] == 0x80000000]
    print("cc_at=%s " % ",".join(map(str, cc[:6])), end="")
    print("%s dw=%d prefix=%d title_at=%d draws=%d cond=%d sb1=%d sb1_in_cond=%d di=%d first_di=%s first_sb1=%s shapeB=%d"
          % (p.rsplit("/", 1)[-1], len(d), pref, start, draw, len(conds), len(sb1), in_cond, len(di),
             di[0] if di else "-", sb1[0] if sb1 else "-", shape))
print("TOTAL " + " ".join("%s=%d" % kv for kv in tot.items()))
