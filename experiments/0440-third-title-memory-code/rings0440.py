#!/usr/bin/env python3
"""Experiment 0440: the registered queues' rings in a dump: what was written and what was consumed (private output).

  rings0440.py <dump> [--all]

Reads the emulator log's "queue reg: a b c 0xID ring 0xS-0xE doorbell ... rptr 0xR (0xN)" lines and, for each queue,
prints from the dumped memory: the INDIRECT_BUFFER entries in its ring (count, the last three targets with their
sizes and the entry's dword position), the dword at its read-pointer address, and the two doorbell-page words that
could be its write pointer (0xfe0200000 + 4*ID and + 8*ID; which one it is, the reader decides from the values).
Without --all only queues with more than the three start-up entries are printed in full.
"""
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ana0440 import Mem  # noqa: E402


def main():
    dump = sys.argv[1]
    show_all = "--all" in sys.argv
    mem = Mem(dump)
    regs = []
    for line in open(os.path.join(dump, "play-last.log"), errors="replace"):
        m = re.search(r"queue reg: (\d+) (\d+) (\d+) (0x[0-9a-f]+) ring (0x[0-9a-f]+)-(0x[0-9a-f]+) doorbell (\S+) rptr (0x[0-9a-f]+)", line)
        if m:
            regs.append((int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4), 16), int(m.group(5), 16),
                         int(m.group(6), 16), m.group(7), int(m.group(8), 16)))
    print("%d registered queues" % len(regs))
    for a, b, c, qid, rs, re_, db, rp in regs:
        raw = mem.read(rs, re_ - rs)
        if not raw:
            print("queue %d/%d/%d id %#x: ring %#x not in the dump" % (a, b, c, qid, rs))
            continue
        dw = struct.unpack("<%dI" % (len(raw) // 4), raw)
        ent = []
        i = 0
        while i + 3 < len(dw):
            h = dw[i]
            if h >> 30 == 3 and (h >> 8) & 0xFF in (0x3F, 0x33) and ((h >> 16) & 0x3FFF) == 2:
                ent.append((i, dw[i + 1] | ((dw[i + 2] & 0xFFFF) << 32), dw[i + 3] & 0xFFFFF))
                i += 4
            else:
                i += 1
        rptr = mem.read(rp, 8)
        rv = struct.unpack("<II", rptr) if rptr and len(rptr) == 8 else (None, None)
        d4 = mem.read(0xFE0200000 + 4 * qid, 4)
        d8 = mem.read(0xFE0200000 + 8 * qid, 8)
        line = "queue %d/%d/%d id %#x: %d ring entries (ring %d dwords), read-pointer words %s, doorbell page [4*id] %s [8*id] %s" % (
            a, b, c, qid, len(ent), len(dw), "%s %s" % tuple("-" if x is None else "%#x" % x for x in rv),
            "-" if not d4 else "%#x" % struct.unpack("<I", d4)[0], "-" if not d8 else "%#x %#x" % struct.unpack("<II", d8))
        if show_all or len(ent) > 3:
            print(line)
            for pos, tgt, n in ent[-3:]:
                print("      entry at ring dword %d -> %#x, %d dwords" % (pos, tgt, n))
        else:
            print(line + "  (start-up entries only)")


if __name__ == "__main__":
    main()
