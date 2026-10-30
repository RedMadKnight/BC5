#!/usr/bin/env python3
# BC5 exp 0381 (Codex review REVIEW-06): the head of a devcoredump's hung IB (IB #0, the host's EMITTED IB) up to and
# including its first few DISPATCH_INDIRECTs: every packet's offset and opcode, the SH registers 0x200-0x24f a
# SET_SH_REG writes there with their values (the program, start and user-data registers), LOAD_SH_REG(_INDEX) table
# addresses, formats and counts, CONTEXT_CONTROL / CLEAR_STATE (the host's full-state prefix). Structure and those
# register values only.
# usage: python3 head0381.py <devcoredump.txt> [dispatches=3]
import sys

lines = open(sys.argv[1], errors="replace").read().split("\n")
stop_after = int(sys.argv[2]) if len(sys.argv) > 2 else 3
start = next(i for i, l in enumerate(lines) if l.startswith("IB #0 "))
n = int(lines[start].split()[3])
ib = [int(x, 16) for x in lines[start + 1:start + 1 + n]]
NAMES = {0x28: "CONTEXT_CONTROL", 0x6a: "CLEAR_STATE", 0x76: "SET_SH_REG", 0x9b: "SET_SH_REG_INDEX", 0x63: "LOAD_SH_REG_INDEX",
         0x5f: "LOAD_SH_REG", 0x16: "DISPATCH_INDIRECT", 0x15: "DISPATCH_DIRECT", 0x11: "SET_BASE", 0x58: "ACQUIRE_MEM",
         0x69: "SET_CONTEXT_REG", 0x79: "SET_UCONFIG_REG", 0x10: "NOP", 0x42: "PFP_SYNC_ME", 0x45: "COND_WRITE",
         0x22: "COND_EXEC", 0x37: "WRITE_DATA"}
print("IB #0: %d dwords" % n)
i = seen = 0
while i < len(ib) and seen < stop_after:
    h = ib[i]
    t = h >> 30
    ln = 1
    if t in (0, 3):
        c = (h >> 16) & 0x3fff
        ln = 1 if c == 0x3fff else c + 2
    op = (h >> 8) & 0xff
    p = ib[i:i + ln]
    f = ""
    if t == 3 and op in (0x76, 0x9b) and ln >= 3:
        r0 = p[1] & 0xffff
        regs = ["0x%x=0x%x" % (r0 + k, v) for k, v in enumerate(p[2:]) if 0x200 <= r0 + k < 0x250]
        f = "reg 0x%x n %d %s" % (r0, ln - 2, " ".join(regs))
    elif t == 3 and op in (0x63, 0x5f) and ln >= 5:
        f = "addr 0x%x reg/fmt 0x%x n %d" % ((p[1] & ~3) | ((p[2] & 0xffff) << 32), p[3], p[4] & 0x3fff)
    elif t == 3 and op == 0x16 and ln >= 3:
        f = "offset 0x%x init 0x%x" % (p[1], p[2])
        seen += 1
    elif t == 3 and op == 0x11 and ln >= 4:
        f = "index %d 0x%x" % (p[1] & 0xf, (p[2] & ~3) | ((p[3] & 0xffff) << 32))
    if t == 3 and (op in NAMES or f):
        print("%6d %-18s len %d %s" % (i, NAMES.get(op, "op 0x%02x" % op), ln, f))
    elif t == 3:
        print("%6d op 0x%02x len %d" % (i, op, ln))
    i += ln
