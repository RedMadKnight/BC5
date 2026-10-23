#!/usr/bin/env python3
# List the dispatches of a PM4 buffer dump (the host's ib-timeout-*.bin): offset, op, dims or indirect offset,
# the program (COMPUTE_PGM_LO/HI set by SET_SH_REG in the buffer), user data 0-15 and SET_BASE 1.
# Only what SET_SH_REG writes inside the buffer is seen; LOAD_SH_REG_INDEX tables are noted, not followed.
# usage: ibdisp.py <dump.bin>
import struct
import sys

d = open(sys.argv[1], "rb").read()
w = struct.unpack("<%dI" % (len(d) // 4), d)
sh = {}
base1 = 0
loads = 0
i = 0
while i < len(w):
    h = w[i]
    t = h >> 30
    c = (h >> 16) & 0x3FFF
    n = 1 if c == 0x3FFF else c + 2
    if t == 3:
        op = (h >> 8) & 0xFF
        p = w[i + 1:i + n]
        if op == 0x76 and len(p) >= 2:  # SET_SH_REG
            r = p[0] & 0xFFFF
            for k, v in enumerate(p[1:]):
                sh[r + k] = v
        elif op == 0x11 and len(p) >= 3 and (p[0] & 0xF) == 1:  # SET_BASE 1
            base1 = (p[1] & ~3) | ((p[2] & 0xFFFF) << 32)
        elif op == 0x63:  # LOAD_SH_REG_INDEX
            loads += 1
        elif op in (0x15, 0x16):
            pgm = (sh.get(0x20C, 0) << 8) | ((sh.get(0x20D, 0) & 0xFF) << 40)
            ud = " ".join("%08x" % sh.get(0x240 + k, 0) for k in range(16))
            arg = ("dims %d %d %d" % (p[0], p[1], p[2])) if op == 0x15 else ("indirect +0x%x (base1 0x%x)" % (p[0], base1))
            print("%6d op %02x pgm 0x%010x %-34s loads %d ud %s" % (i, op, pgm, arg, loads, ud))
    elif t != 0:
        n = 1
    i += n
