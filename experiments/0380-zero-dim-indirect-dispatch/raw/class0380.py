#!/usr/bin/env python3
# BC5 experiment 0380: for each amdgpu devcoredump given, find the hung IB's position of the PFP and the ME (by
# matching the newest-first CP header histories against the IB's packet headers, F527) and print, structure only:
# the dispatches just before the ME, whether the last DISPATCH_INDIRECT is the first indirect dispatch after an
# INDEX_BASE (and what lies between), and how many indirect dispatches in the whole IB are "first after INDEX_BASE".
# No IB payload is printed beyond packet offsets, opcodes, SET_BASE / INDEX_BASE addresses and INDEX_BUFFER_SIZE.
# usage: python3 class0380.py <devcoredump.txt>...
import re
import sys


def load(path):
    lines = open(path, errors="replace").read().split("\n")
    regs = {}
    hist = {"PFP": [], "ME": []}
    for l in lines:
        m = re.match(r"mm(\w+)\s+0x([0-9a-f]+)", l)
        if not m:
            continue
        name, v = m.group(1), int(m.group(2), 16)
        if name == "CP_PFP_HEADER_DUMP" and len(hist["PFP"]) < 8:
            hist["PFP"].append(v)
        elif name == "CP_ME_HEADER_DUMP" and len(hist["ME"]) < 8:
            hist["ME"].append(v)
        elif name not in regs:
            regs[name] = v
    try:
        s = next(i for i, l in enumerate(lines) if l.startswith("IB #0 "))
    except StopIteration:
        return regs, hist, None
    n = int(lines[s].split()[3])
    ib = [int(x, 16) for x in lines[s + 1:s + 1 + n] if re.fullmatch(r"0x[0-9a-f]+", x.strip())]
    return regs, hist, ib


def packets(ib):
    out = []
    i = 0
    while i < len(ib):
        h = ib[i]
        t = h >> 30
        ln = 1
        if t in (0, 3):
            c = (h >> 16) & 0x3fff
            ln = 1 if c == 0x3fff else c + 2
        out.append((i, h, ln))
        i += ln
    return out


def locate(pk, hist):
    """Packet index of the newest history entry: the oldest..newest headers match consecutive packets."""
    want = list(reversed(hist))
    hs = [h for _, h, _ in pk]
    hits = [k + len(want) - 1 for k in range(len(hs) - len(want) + 1) if hs[k:k + len(want)] == want]
    return hits


def main():
    for path in sys.argv[1:]:
        regs, hist, ib = load(path)
        print(f"== {path.split('/')[-1]}: GRBM_STATUS 0x{regs.get('GRBM_STATUS', 0):x} STALLED_STAT2 "
              f"0x{regs.get('CP_STALLED_STAT2', 0):x} PFP 0x{regs.get('CP_PFP_INSTR_PNTR', 0):x} "
              f"ME 0x{regs.get('CP_ME_INSTR_PNTR', 0):x}")
        if ib is None:
            print("   no IB #0 in the dump")
            continue
        pk = packets(ib)
        print(f"   IB {len(ib)} dwords, {len(pk)} packets; IB1 fetched "
              f"{regs.get('CP_IB1_CMD_BUFSZ', 0) - regs.get('CP_IB1_BUFSZ', 0)} dwords")
        pfp = locate(pk, hist["PFP"])
        print(f"   PFP history matches at packet(s) {[pk[k][0] for k in pfp]} (dword offsets of the newest)")
        # the pattern over the whole IB
        last_ib = None
        first_after = 0
        indirect = 0
        rows = []
        idx_size = None
        since_index_base = None
        for k, (off, h, ln) in enumerate(pk):
            if h >> 30 != 3:
                continue
            op = (h >> 8) & 0xff
            if op == 0x26:
                last_ib = (off, (ib[off + 1] & ~1) | ((ib[off + 2] & 0xffff) << 32))
                since_index_base = []
            elif op == 0x13 and since_index_base is not None:
                idx_size = ib[off + 1]
            elif op in (0x15, 0x16):
                if op == 0x16:
                    indirect += 1
                    first = since_index_base is not None and not any(o == 0x16 for o in since_index_base)
                    if first:
                        first_after += 1
                    rows.append((off, "INDIRECT", first, last_ib, idx_size))
                else:
                    rows.append((off, "DIRECT", None, last_ib, idx_size))
                if since_index_base is not None:
                    since_index_base.append(op)
            elif op in (0x2d, 0x27, 0x28, 0x2a, 0x35, 0x36, 0x38, 0x24, 0x25, 0x2c, 0x3d) and since_index_base is not None:
                since_index_base.append(op)  # draws: the next indirect dispatch is not "first after INDEX_BASE"
                since_index_base.append(0x16)
        print(f"   indirect dispatches {indirect}, first after an INDEX_BASE {first_after}")
        if pfp:
            p_off = pk[pfp[-1]][0]
            before = [r for r in rows if r[0] <= p_off][-4:]
            for off, kind, first, lib, isz in before:
                tag = "" if kind == "DIRECT" else ("FIRST after INDEX_BASE" if first else "not first")
                ibs = f"INDEX_BASE @{lib[0]} 0x{lib[1]:x}, size 0x{isz:x}" if lib and isz is not None else (
                    f"INDEX_BASE @{lib[0]} 0x{lib[1]:x}" if lib else "no INDEX_BASE before")
                print(f"   before the PFP: {off:6d} DISPATCH_{kind} {tag} | {ibs}")


main()
