#!/usr/bin/env python3
# BC5 experiment 0380: walk the hung IB of an amdgpu devcoredump ("IB #0 <va> <n> dw", one dword a line) and print
# packet structure only: offsets, opcodes, SET_BASE / COMPUTE_PGM values, DISPATCH_* and the host check's
# COND_WRITE poll addresses (the dispatch's argument address). No IB payload beyond those fields is printed.
# usage: python3 walk0380.py <devcoredump.txt> [pgm_hex] [fetched_dwords]
import sys
path = sys.argv[1]
want = int(sys.argv[2], 16) if len(sys.argv) > 2 else None
lines = open(path, errors="replace").read().split("\n")
start = next(i for i, l in enumerate(lines) if l.startswith("IB #0 "))
_, _, va, n, _ = lines[start].split()
n = int(n)
ib = [int(x, 16) for x in lines[start + 1:start + 1 + n]]
print(f"IB va {va} {len(ib)} dwords")
NAMES = {0x10: "NOP", 0x11: "SET_BASE", 0x15: "DISPATCH_DIRECT", 0x16: "DISPATCH_INDIRECT", 0x22: "COND_EXEC",
         0x37: "WRITE_DATA", 0x3c: "WAIT_REG_MEM", 0x42: "PFP_SYNC_ME", 0x45: "COND_WRITE", 0x46: "EVENT_WRITE",
         0x49: "RELEASE_MEM", 0x50: "DMA_DATA", 0x58: "ACQUIRE_MEM", 0x76: "SET_SH_REG", 0x79: "SET_UCONFIG_REG"}
i = 0; base = 0; pgm_lo = pgm_hi = 0; conds = []
out = []
while i < len(ib):
    h = ib[i]; t = h >> 30
    ln = 1
    if t in (0, 3):
        c = (h >> 16) & 0x3fff
        ln = 1 if c == 0x3fff else c + 2
    op = (h >> 8) & 0xff
    pk = ib[i:i + ln]
    if t == 3:
        if op == 0x11 and ln >= 4 and (pk[1] & 0xf) == 1:
            base = (pk[2] & ~3) | ((pk[3] & 0xffff) << 32)
        if op == 0x76 and ln >= 3:
            reg = pk[1] & 0xffff
            for k, v in enumerate(pk[2:]):
                r = reg + k
                if r == 0x20c: pgm_lo = v      # COMPUTE_PGM_LO (byte 0xb830: (0xb830-0xb000)/4 = 0x20c)
                if r == 0x20d: pgm_hi = v
        if op == 0x45 and ln == 9:
            conds.append((pk[1] & 7, (pk[2] & ~3) | ((pk[3] & 0xffff) << 32), pk[4]))
        if op in (0x15, 0x16):
            pgm = ((pgm_hi & 0xff) << 40) | (pgm_lo << 8)
            if op == 0x16:
                desc = f"args at base 0x{base:x} + 0x{pk[1]:x} = 0x{base + pk[1]:x}, initiator 0x{pk[2]:x}"
            else:
                desc = f"dims {pk[1]} x {pk[2]} x {pk[3]}, initiator 0x{pk[4]:x}"
            cw = "; ".join(f"fn{f} 0x{a:x} ref 0x{r:x}" for f, a, r in conds)
            line = f"{i:6d} {NAMES.get(op, hex(op))} program 0x{pgm:x} {desc}" + (f" | check: {cw}" if cw else "")
            if want is None or pgm == want:
                out.append(line)
            conds = []
    i += ln
print("\n".join(out))
