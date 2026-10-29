#!/usr/bin/env python3
# BC5 experiment 0380: list the packets of a devcoredump's hung IB in a dword range: offset, opcode, length and
# only the structural fields (register offsets, addresses, counts; no payload data).
# usage: python3 span0380.py <devcoredump.txt> <from> <to>
import sys
lines = open(sys.argv[1], errors="replace").read().split("\n")
lo, hi = int(sys.argv[2]), int(sys.argv[3])
start = next(i for i, l in enumerate(lines) if l.startswith("IB #0 "))
n = int(lines[start].split()[3])
ib = [int(x, 16) for x in lines[start + 1:start + 1 + n]]
i = 0
while i < len(ib):
    h = ib[i]; t = h >> 30; ln = 1
    if t in (0, 3):
        c = (h >> 16) & 0x3fff
        ln = 1 if c == 0x3fff else c + 2
    op = (h >> 8) & 0xff
    if lo <= i < hi and t == 3:
        pk = ib[i:i + ln]; f = ""
        if op in (0x76, 0x79, 0x69, 0x9b): f = f"reg 0x{pk[1] & 0xffff:x} n {ln - 2}"
        if op == 0x63 and ln >= 5: f = f"LOAD_SH_REG_INDEX? addr 0x{(pk[1] & ~3) | ((pk[2] & 0xffff) << 32):x} w1 0x{pk[1] & 3:x} reg 0x{pk[3] & 0xffff:x} hi16 0x{pk[3] >> 16:x} n {pk[4]}"
        if op == 0x9f: f = "w " + " ".join(f"0x{x:x}" for x in pk[1:])
        if op == 0x11: f = f"index {pk[1] & 0xf} 0x{(pk[2] & ~3) | ((pk[3] & 0xffff) << 32):x}"
        if op == 0x16: f = f"offset 0x{pk[1]:x} init 0x{pk[2]:x}"
        if op == 0x15: f = f"dims {pk[1]} {pk[2]} {pk[3]} init 0x{pk[4]:x}"
        if op == 0x45: f = f"fn{pk[1] & 7} poll 0x{(pk[2] & ~3) | ((pk[3] & 0xffff) << 32):x} ref 0x{pk[4]:x} write 0x{(pk[6]) | ((pk[7] & 0xffff) << 32):x} data {pk[8]}"
        if op == 0x22: f = f"addr 0x{(pk[1]) | ((pk[2] & 0xffff) << 32):x} count {pk[4] & 0x3fff}"
        if op == 0x46: f = f"event {pk[1] & 0x3f}"
        if op == 0x37: f = f"ctl 0x{pk[1]:x} addr 0x{pk[2] | ((pk[3] & 0xffff) << 32):x}"
        if op == 0x50: f = f"ctl 0x{pk[1]:x} src 0x{pk[2] | (pk[3] << 32):x} dst 0x{pk[4] | (pk[5] << 32):x} n 0x{pk[6] & 0x1fffff:x}"
        print(f"{i:6d} op {op:02x} len {ln:3d} {f}")
    i += ln
