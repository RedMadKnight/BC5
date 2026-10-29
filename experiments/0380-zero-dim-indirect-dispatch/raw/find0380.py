#!/usr/bin/env python3
# BC5 experiment 0380: where in a devcoredump's hung IB do given dword values occur? Prints the offset, the enclosing
# packet's offset/opcode and the dword's index in it (structure only, no other payload).
# usage: python3 find0380.py <devcoredump.txt> <hex value>...
import sys
lines = open(sys.argv[1], errors="replace").read().split("\n")
want = {int(v, 16) for v in sys.argv[2:]}
s = next(i for i, l in enumerate(lines) if l.startswith("IB #0 "))
n = int(lines[s].split()[3])
ib = [int(x, 16) for x in lines[s + 1:s + 1 + n]]
i = 0
while i < len(ib):
    h = ib[i]; t = h >> 30; ln = 1
    if t in (0, 3):
        c = (h >> 16) & 0x3fff
        ln = 1 if c == 0x3fff else c + 2
    for k in range(i, min(i + ln, len(ib))):
        if ib[k] in want:
            print(f"value 0x{ib[k]:x} at {k}: packet at {i} op 0x{(h >> 8) & 0xff:02x} len {ln} dword {k - i}"
                  + (f" (SET_SH_REG reg 0x{ib[i + 1] & 0xffff:x} + {k - i - 2})" if (h >> 8) & 0xff == 0x76 and k - i >= 2 else ""))
    i += ln
