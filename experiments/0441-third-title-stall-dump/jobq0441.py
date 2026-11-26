#!/usr/bin/env python3
"""Experiment 0441: the title's job system at the stall, read from a dump (private output).

  jobq0441.py <dump> <job-system address> <group address>

Prints the job system's queues (lock word, list head and tail at offsets found in eboot+0xe246a0: one 0x28-byte record
per queue from +0x970, the list head at +0x10 of the record), the two cursor lists, and the waited group with the
groups linked behind it (flags, job count, cursor, queue index, link fields, first job's state and function).
Needs ana0440.py beside it (the 0440 tools).
"""
import struct
import sys

sys.path.insert(0, ".")
from ana0440 import Mem, Syms, parse_modules  # noqa: E402


def main():
    dump, js, g = sys.argv[1], int(sys.argv[2], 0), int(sys.argv[3], 0)
    m = Mem(dump)
    sy = Syms(m, parse_modules(dump))
    print("job system header: " + " ".join("%#x" % x for x in struct.unpack("<6Q", m.read(js, 48))))
    for k in range(4):
        q = js + 0x970 + 0x28 * k
        lock, pad, a, head, tail, e = struct.unpack("<IIQQQQ", m.read(q, 0x28))
        print("queue %d at %#x: lock %d, +8 %#x, head (+0x10) %#x, +0x18 %#x, +0x20 %#x" % (k, q, lock, a, head, tail, e))
    print("cursor lists: [js+0x9e0] %#x, [js+0x9e8] %#x" % (m.q(js + 0x9E0), m.q(js + 0x9E8)))

    def group(addr, tag):
        d = m.read(addr, 0x20)
        if not d or len(d) < 0x20:
            print("  %s %#x: not in the dump" % (tag, addr))
            return None
        fl, cnt, cur, qi, nxt, x = struct.unpack("<IIIIQQ", d)
        e = m.read(addr + 0x20, 0x18)
        st, pad, fn, arg = struct.unpack("<IIQQ", e)
        print("  %s %#x: flags %#x count %d cursor %d queue %d link +0x10 %#x link +0x18 %#x; first job state %d function %s" % (
            tag, addr, fl, cnt, cur, qi, nxt, x, st, sy.name(fn) if fn and m.map_at(fn) else "%#x" % fn))
        return nxt

    n = group(g, "waited group")
    for _ in range(6):
        if not n:
            break
        nxt = group(n, "link target read as a group")
        group(n - 0x10, "link target - 0x10 read as a group")
        n = nxt


if __name__ == "__main__":
    main()
