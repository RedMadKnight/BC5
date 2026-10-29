#!/usr/bin/env python3
# BC5 experiment 0380: for each devcoredump, the packets of the hung IB inside the fetched part (CP_IB1_CMD_BUFSZ -
# CP_IB1_BUFSZ dwords), structure only: every SET_BASE / INDEX_BASE / INDEX_BUFFER_SIZE / dispatch / EVENT_WRITE and
# draw, with the CP header histories (newest first) for placing the PFP and the ME by eye.
# usage: python3 near0380.py <devcoredump.txt>...
import re
import sys

DRAWS = {0x24, 0x25, 0x27, 0x28, 0x2a, 0x2c, 0x2d, 0x35, 0x36, 0x38, 0x3d}
for path in sys.argv[1:]:
    lines = open(path, errors="replace").read().split("\n")
    regs, hist = {}, {"CP_PFP_HEADER_DUMP": [], "CP_ME_HEADER_DUMP": []}
    for l in lines:
        m = re.match(r"mm(\w+)\s+0x([0-9a-f]+)", l)
        if m:
            k, v = m.group(1), int(m.group(2), 16)
            if k in hist:
                if len(hist[k]) < 8:
                    hist[k].append(v)
            elif k not in regs:
                regs[k] = v
    s = next(i for i, l in enumerate(lines) if l.startswith("IB #0 "))
    n = int(lines[s].split()[3])
    ib = [int(x, 16) for x in lines[s + 1:s + 1 + n]]
    fetched = regs.get("CP_IB1_CMD_BUFSZ", 0) - regs.get("CP_IB1_BUFSZ", 0)
    print(f"== {path.split('/')[-1]}: fetched {fetched} of {len(ib)} dwords")
    print("   PFP history (newest first): " + " ".join(f"{h:08x}" for h in hist["CP_PFP_HEADER_DUMP"]))
    print("   ME  history (newest first): " + " ".join(f"{h:08x}" for h in hist["CP_ME_HEADER_DUMP"]))
    i = 0
    first_indirect_after_ib = False
    while i < min(len(ib), fetched + 64):
        h = ib[i]
        t = h >> 30
        ln = 1
        if t in (0, 3):
            c = (h >> 16) & 0x3fff
            ln = 1 if c == 0x3fff else c + 2
        op = (h >> 8) & 0xff
        if t == 3:
            f = None
            if op == 0x11:
                f = f"SET_BASE {ib[i + 1] & 0xf} 0x{(ib[i + 2] & ~3) | ((ib[i + 3] & 0xffff) << 32):x}"
            elif op == 0x26:
                f = f"INDEX_BASE 0x{(ib[i + 1] & ~1) | ((ib[i + 2] & 0xffff) << 32):x}"
                first_indirect_after_ib = True
            elif op == 0x13:
                f = f"INDEX_BUFFER_SIZE 0x{ib[i + 1]:x}"
            elif op == 0x16:
                f = f"DISPATCH_INDIRECT off 0x{ib[i + 1]:x} init 0x{ib[i + 2]:x}" + (
                    "  <- first after INDEX_BASE" if first_indirect_after_ib else "")
                first_indirect_after_ib = False
            elif op == 0x15:
                f = f"DISPATCH_DIRECT {ib[i + 1]} {ib[i + 2]} {ib[i + 3]}"
            elif op == 0x46:
                f = f"EVENT_WRITE {ib[i + 1] & 0x3f}"
            elif op in DRAWS:
                f = f"draw op {op:02x}"
                first_indirect_after_ib = False
            if f:
                mark = "   (past the fetch)" if i >= fetched else ""
                print(f"   {i:6d} {f}{mark}")
        i += ln
