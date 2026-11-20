#!/usr/bin/env python3
"""exp 0438: the order of a waiter's waits against a writer's releases, from two dumped IBs (ib-timeout-*.bin).

Usage: pair0438.py WAITER.bin WRITER.bin
For each 64/32-bit memory wait of WAITER: label, function, reference; then every packet of WRITER that writes the label
(RELEASE_MEM 0x49, EVENT_WRITE_EOP 0x47, WRITE_DATA 0x37, ATOMIC_MEM 0x1e, COPY_DATA 0x40, DMA_DATA 0x50 by address),
with its dword offset, DATA_SEL and value. Then every wait of WRITER on a label WAITER writes, with its offset: a writer
wait that comes BEFORE the writer's release of the waiter's label is a true cycle; one that comes AFTER it is not.
Only top-level packets (IB2s are not followed). Reads the files only.
"""
import struct
import sys


def packets(path):
    b = open(path, 'rb').read()
    d = struct.unpack('<%dI' % (len(b) // 4), b[: len(b) // 4 * 4])
    i = 0
    while i < len(d):
        h = d[i]
        t = h >> 30
        ln = 1
        if t in (0, 3):
            c = (h >> 16) & 0x3FFF
            ln = 1 if c == 0x3FFF else c + 2
        if t == 3 and i + ln <= len(d):
            yield i, (h >> 8) & 0xFF, d[i:i + ln]
        i += ln


def addr(lo, hi):
    return (lo & ~3) | ((hi & 0xFFFF) << 32)


def writes(path):
    out = []  # (off, op, label, sel, value)
    for i, op, p in packets(path):
        if op == 0x49 and len(p) >= 8:
            sel = (p[2] >> 29) & 7
            out.append((i, op, addr(p[3], p[4]), sel, p[5] | (p[6] << 32)))
        elif op == 0x47 and len(p) >= 6:
            sel = (p[3] >> 29) & 7
            out.append((i, op, addr(p[2], p[3]), sel, p[4] | (p[5] << 32) if len(p) > 5 else p[4]))
        elif op == 0x37 and len(p) >= 5:
            dst = (p[1] >> 8) & 0xF
            if dst in (1, 2, 5):
                v = p[4] | ((p[5] << 32) if len(p) > 5 else 0)
                out.append((i, op, addr(p[2], p[3]), 'dst%d' % dst, v))
        elif op == 0x1e and len(p) >= 4:
            out.append((i, op, addr(p[2], p[3]), 'atomic%d' % (p[1] & 0x7F), p[4] if len(p) > 4 else 0))
        elif op == 0x40 and len(p) >= 6:
            out.append((i, op, addr(p[4], p[5]), 'copy', 0))
        elif op == 0x50 and len(p) >= 7:
            out.append((i, op, addr(p[4], p[5]), 'dma', 0))
    return out


def waits(path):
    out = []  # (off, op, label, fn, ref, engine)
    for i, op, p in packets(path):
        if op in (0x3C, 0x93) and len(p) >= 6 and ((p[1] >> 4) & 1):
            ref = p[4] | (p[5] << 32) if op == 0x93 else p[4]
            out.append((i, op, addr(p[2], p[3]), p[1] & 7, ref, 'pfp' if (p[1] >> 8) & 1 else 'me'))
    return out


def main():
    a, b = sys.argv[1], sys.argv[2]
    wa, wb = waits(a), waits(b)
    xa, xb = writes(a), writes(b)
    print('waiter %s: %d waits, %d writes; writer %s: %d waits, %d writes' % (a, len(wa), len(xa), b, len(wb), len(xb)))
    for off, op, lab, fn, ref, eng in wa:
        rel = [x for x in xb if x[2] == lab]
        print('waiter wait @%d op %02x 0x%x fn %d ref 0x%x %s: writer writes it at %s' % (
            off, op, lab, fn, ref, eng, ', '.join('@%d op %02x sel %s val 0x%x' % (x[0], x[1], x[3], x[4]) for x in rel) or 'NOWHERE'))
    labs_a = {x[2] for x in xa}
    for off, op, lab, fn, ref, eng in wb:
        if lab in labs_a:
            mine = [x for x in xa if x[2] == lab]
            print('writer wait @%d op %02x 0x%x fn %d ref 0x%x %s on a label the waiter writes (at %s)' % (
                off, op, lab, fn, ref, eng, ', '.join('@%d sel %s val 0x%x' % (x[0], x[3], x[4]) for x in mine)))


main()
