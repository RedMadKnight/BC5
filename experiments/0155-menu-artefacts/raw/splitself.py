#!/usr/bin/env python3
# Experiment 0155: in dumped graphics buffers, a "self-wait" is a WAIT_REG_MEM[64] on a label that
# a WRITE_DATA/RELEASE_MEM/EVENT_WRITE_EOP earlier in the same buffer writes. A "cross-queue wait"
# is one whose label no earlier packet of the buffer writes. For every cross-queue wait C: how many
# self-waits after C have ALL their writers before C (a split at C would leave them without a
# writer in the tail), and which packets lie between the writer and the wait.
import glob, struct, sys, collections, os
d = sys.argv[1]
tot = collections.Counter(); ex = []
for f in sorted(glob.glob(d + "/ib-*-dcb-*.bin")):
    b = open(f, "rb").read(); ib = struct.unpack("<%dI" % (len(b) // 4), b[:len(b) // 4 * 4]); i = 0
    writes = collections.defaultdict(list); waits = []  # label -> [positions], waits: (pos, label)
    while i < len(ib):
        h = ib[i]; t = h >> 30; c = (h >> 16) & 0x3fff
        n = 1 if t not in (0, 3) or c == 0x3fff else c + 2
        if t == 3 and i + n <= len(ib):
            op = (h >> 8) & 0xff
            if op == 0x37 and n >= 4 and ((ib[i+1] >> 8) & 0xf) in (1, 2, 5): writes[(ib[i+2] & ~3) | (ib[i+3] << 32)].append(i)
            elif op == 0x49 and n >= 6 and ((ib[i+2] >> 29) & 7) != 0: writes[(ib[i+3] & ~3) | ((ib[i+4] & 0xffff) << 32)].append(i)
            elif op == 0x47 and n >= 4 and ((ib[i+3] >> 29) & 7) != 0: writes[(ib[i+2] & ~3) | ((ib[i+3] & 0xffff) << 32)].append(i)
            elif op in (0x3c, 0x93) and n >= 4 and (ib[i+1] >> 4) & 1: waits.append((i, (ib[i+2] & ~3) | ((ib[i+3] & 0xffff) << 32)))
        i += n
    tot["buffers"] += 1
    cross = [(p, l) for p, l in waits if not any(w < p for w in writes.get(l, []))]
    selfw = [(p, l) for p, l in waits if any(w < p for w in writes.get(l, []))]
    tot["cross-queue waits"] += len(cross); tot["self-waits"] += len(selfw)
    for cp, cl in cross:
        for sp, sl in selfw:
            if sp > cp and all(w < cp for w in writes[sl]):
                tot["self-waits orphaned by a split at a cross-queue wait"] += 1
                if len(ex) < 8: ex.append((os.path.basename(f), "cross wait at %d on 0x%x" % (cp, cl), "self-wait at %d on 0x%x, writers at %s" % (sp, sl, writes[sl])))
        if cross: tot["buffers with a cross-queue wait"] += 0
    if cross: tot["buffers with cross-queue waits"] += 1
for k, v in sorted(tot.items()): print("%8d %s" % (v, k))
for e in ex: print("  ", e)
