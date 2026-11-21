#!/usr/bin/env python3
"""Experiment 0440: what the dumped frame's command buffer chain holds past the host's cut (private output).

  ahead0440.py <dump> <head-address> <head-dwords> <pm4-policy.tsv> [first-segment]

Walks the chain (INDIRECT_BUFFER with the chain bit replaces the buffer; a call is followed one level and
counted), and for the segments from first-segment on (default 4) prints:
  - type-3 opcodes with their count and the verdict of backend/policy/pm4-policy.tsv (pass, drop, rewrite,
    or the default for an opcode the table does not list);
  - every address a packet writes (WRITE_DATA to memory, RELEASE_MEM with data, COPY_DATA to memory, DMA_DATA,
    ATOMIC_MEM, MEM_SEMAPHORE) classified by the dump's maps: title view, host mapping, or not mapped;
  - every WAIT_REG_MEM on memory: whether an earlier packet of the chain writes the waited address, the wait's
    function, reference and mask, and the value in the dump;
  - COND_EXEC guards and LOAD_*_REG_INDEX tables whose address is not in a mapped title view.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ana0440 import Mem  # noqa: E402


def policy(path):
    ops, default = {}, "drop"
    for line in open(path):
        if line.startswith("#") or not line.strip():
            continue
        p = line.rstrip("\n").split("\t")
        if p[0] == "op" and len(p) >= 3:
            try:
                ops[int(p[1], 16)] = (p[2], p[3] if len(p) > 3 else "")
            except ValueError:
                pass
        elif p[0] == "default-op":
            default = p[1]
    return ops, default


def main():
    dump, head, ndw, tsv = sys.argv[1], int(sys.argv[2], 0), int(sys.argv[3], 0), sys.argv[4]
    first = int(sys.argv[5]) if len(sys.argv) > 5 else 4
    mem = Mem(dump)
    ops, default = policy(tsv)

    def where(a):
        m = mem.map_at(a)
        if not m:
            return "NOT MAPPED"
        if "---" in m[2]:
            return "NOT MAPPED (reserved, no access)"
        if a >= 0x7f0000000000 or m[4].startswith("/") and "memfd:Kyty" not in m[4]:
            return "HOST mapping %s %s" % (m[2], m[4] or "anon")
        return "title view %#x %s" % (m[0], m[4].replace("/memfd:", "").replace(" (deleted)", ""))

    seg = 0
    addr, n = head, ndw
    hist = {}
    writes = {}      # address -> (segment, packet address, kind, value)
    wr_order = []
    waits, conds, tables, calls, odd = [], [], [], [], []
    seen = set()
    total = 0
    while True:
        if addr in seen:
            print("CYCLE at %#x" % addr)
            break
        seen.add(addr)
        d = mem.read(addr, n * 4)
        if not d or len(d) < n * 4:
            print("segment %d at %#x: not in the dump" % (seg, addr))
            break
        dw = struct.unpack("<%dI" % n, d)
        total += n
        i = 0
        nxt = None
        while i < n:
            h = dw[i]
            t = h >> 30
            if h == 0xFFFF1000 or t == 2 or h == 0:
                i += 1
                continue
            if t != 3:
                if seg >= first:
                    odd.append((seg, addr + 4 * i, "type-%d header %08x" % (t, h)))
                i += 1 + ((((h >> 16) & 0x3FFF) + 1) if t == 0 else 0)
                continue
            cnt = ((h >> 16) & 0x3FFF) + 1
            op = (h >> 8) & 0xFF
            b = dw[i + 1:i + 1 + cnt]
            pa = addr + 4 * i
            if i + 1 + cnt > n:
                odd.append((seg, pa, "packet %08x overruns its segment" % h))
            if seg >= first:
                hist[op] = hist.get(op, 0) + 1

            def a64(k):
                return b[k] | (b[k + 1] << 32) if k + 1 < len(b) else 0

            w = None
            if op == 0x37 and cnt >= 3:  # WRITE_DATA: control, address lo, hi, data
                if (b[0] >> 8) & 0xF != 0:
                    w = (a64(1) & ~3, "WRITE_DATA dst_sel %d" % ((b[0] >> 8) & 0xF), b[3] if cnt > 3 else 0)
            elif op == 0x49 and cnt >= 6:  # RELEASE_MEM: event, control, address lo, hi, data lo, hi, int ctx
                if (b[1] >> 29) != 0:
                    w = (a64(2) & ~3, "RELEASE_MEM event %#x data_sel %d int_sel %d" % (b[0] & 0x3F, b[1] >> 29, (b[1] >> 24) & 7), b[4])
                elif (b[1] >> 24) & 7 and seg >= first:
                    odd.append((seg, pa, "RELEASE_MEM interrupt only: int_sel %d ctx %#x" % ((b[1] >> 24) & 7, b[6] if cnt > 6 else 0)))
            elif op == 0x40 and cnt >= 5:  # COPY_DATA: control, src lo, hi, dst lo, hi
                if (b[0] >> 8) & 0xF in (1, 2, 5):
                    w = (a64(3) & ~3, "COPY_DATA src_sel %d dst_sel %d" % (b[0] & 0xF, (b[0] >> 8) & 0xF), 0)
            elif op == 0x50 and cnt >= 6:  # DMA_DATA: control, src lo, hi, dst lo, hi, count
                if (b[0] >> 20) & 3 in (0, 3) and (b[5] & 0x3FFFFFF):
                    w = (a64(3), "DMA_DATA %d bytes" % (b[5] & 0x3FFFFFF), 0)
            elif op == 0x1E and cnt >= 3:
                w = (a64(1) & ~3, "ATOMIC_MEM", 0)
            elif op == 0x39 and cnt >= 2:
                w = (a64(0) & ~3, "MEM_SEMAPHORE", 0)
            if w:
                writes.setdefault(w[0] & ~7, (seg, pa, w[1], w[2]))
                if seg >= first:
                    wr_order.append((seg, pa, w[0], w[1], w[2]))
            if op == 0x3C and cnt >= 5 and seg >= first:  # WAIT_REG_MEM: control, address lo, hi, ref, mask, poll
                if (b[0] >> 4) & 3:
                    a = a64(1) & ~3
                    waits.append((seg, pa, a, b[0], b[3], b[4], writes.get(a & ~7)))
            if op == 0x22 and cnt >= 4 and seg >= first:
                conds.append((seg, pa, a64(0) & ~3, b[3] & 0x3FFF))
            if op in (0x9F, 0x63, 0x64, 0x5E) and cnt >= 2 and seg >= first:
                tables.append((seg, pa, op, a64(0) & ~3))
            if op in (0x3F, 0x33) and cnt >= 3:
                tgt, sz = b[0] | ((b[1] & 0xFFFF) << 32), b[2] & 0xFFFFF
                if (b[2] >> 20) & 1:
                    nxt = (tgt, sz)
                    break
                calls.append((seg, pa, tgt, sz))
            i += 1 + cnt
        if nxt is None:
            print("chain ends in segment %d at %#x (%d dwords); %d dwords in all" % (seg, addr, n, total))
            tail = dw[max(0, n - 8):]
            print("  its last packets end with the dwords' opcodes: " + " ".join("%02x" % ((x >> 8) & 0xFF) if x >> 30 == 3 else "." for x in tail))
            break
        seg += 1
        addr, n = nxt

    print("\n== opcodes in segments %d..%d, by the policy table's verdict" % (first, seg))
    for op in sorted(hist, key=lambda o: (ops.get(o, (default + " (default)", ""))[0], o)):
        v, note = ops.get(op, (default + " (DEFAULT: not in the table)", ""))
        print("  0x%02x x%-5d %-8s %s" % (op, hist[op], v, note[:90]))
    print("\n== calls (INDIRECT_BUFFER without the chain bit): %d" % len(calls))
    for c in calls[:10]:
        print("  segment %d at %#x -> %#x, %d dwords" % c)
    print("\n== addresses written in segments %d.., by place" % first)
    by = {}
    for s, pa, a, kind, val in wr_order:
        by.setdefault(where(a), []).append((s, pa, a, kind, val))
    for k in sorted(by):
        v = by[k]
        print("  %s: %d writes" % (k, len(v)))
        if "title view" not in k:
            for s, pa, a, kind, val in v[:12]:
                print("      segment %d at %#x: %s -> %#x value %#x" % (s, pa, kind, a, val))
    print("\n== WAIT_REG_MEM on memory in segments %d..: %d" % (first, len(waits)))
    ext = [w for w in waits if w[6] is None]
    print("  writer earlier in this chain: %d; no writer in this chain: %d" % (len(waits) - len(ext), len(ext)))
    for s, pa, a, ctl, ref, mask, _ in ext:
        cur = mem.q(a)
        print("      segment %d at %#x: waits on %#x function %d engine-bit %d ref %#x mask %#x; value in the dump %s; %s" % (
            s, pa, a, ctl & 7, (ctl >> 8) & 1, ref, mask, "-" if cur is None else "%#x" % (cur & 0xFFFFFFFF), where(a)))
    kinds = {}
    for s, pa, a, ctl, ref, mask, wtr in waits:
        if wtr:
            kinds[wtr[2].split(" data_sel")[0]] = kinds.get(wtr[2].split(" data_sel")[0], 0) + 1
    print("  writers of the others, by packet: %s" % kinds)
    print("\n== COND_EXEC guards in segments %d..: %d" % (first, len(conds)))
    for s, pa, a, cnt in conds[:12]:
        cur = mem.q(a)
        print("      segment %d at %#x: guard %#x (%s) value %s, %d dwords" % (s, pa, a, where(a), "-" if cur is None else "%#x" % (cur & 0xFFFFFFFF), cnt))
    bad = [(s, pa, op, a) for s, pa, op, a in tables if "title view" not in where(a)]
    print("\n== LOAD_*_REG tables: %d, of them not in a title view: %d" % (len(tables), len(bad)))
    for s, pa, op, a in bad[:10]:
        print("      segment %d at %#x: op 0x%02x table %#x %s" % (s, pa, op, a, where(a)))
    print("\n== other: %d" % len(odd))
    for s, pa, text in odd[:20]:
        print("      segment %d at %#x: %s" % (s, pa, text))


if __name__ == "__main__":
    main()
