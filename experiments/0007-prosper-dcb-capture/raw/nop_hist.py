#!/usr/bin/env python3
# BC5 experiment 0007: histogram of type-3 NOP packets in raw DCB dumps.
# Usage: nop_hist.py <capture>/dcb
# Prints the header bits 2..7 ("r" field) and the most common first payload dword.
import collections, os, struct, sys

r_field = collections.Counter()
p0 = collections.Counter()
for root, _, files in os.walk(sys.argv[1]):
    for name in files:
        d = open(os.path.join(root, name), "rb").read()
        w = struct.unpack("<%dI" % (len(d) // 4), d[: len(d) // 4 * 4])
        i = 0
        while i < len(w):
            h = w[i]
            t = h >> 30
            if t == 3:
                n = ((h >> 16) & 0x3FFF) + 2
                if (h >> 8) & 0xFF == 0x10:
                    r_field[(h & 0xFF) >> 2] += 1
                    p0[w[i + 1] if i + 1 < len(w) else -1] += 1
                i += n
            elif t == 2:
                i += 1
            else:
                i += ((h >> 16) & 0x3FFF) + 2
print("NOP r field (header bits 2..7):")
for k, v in sorted(r_field.items()):
    print("  0x%02x %8d" % (k, v))
zero = p0[0]
print("NOP payload[0] == 0: %d of %d" % (zero, sum(p0.values())))
