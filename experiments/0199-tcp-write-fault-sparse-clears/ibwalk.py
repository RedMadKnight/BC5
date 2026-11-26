#!/usr/bin/env python3
# Walk a raw PM4 dump from a given start dword and print every packet in [lo, hi) with its body,
# plus each DISPATCH_DIRECT/INDIRECT with the COMPUTE_PGM_LO/HI and COMPUTE_USER_DATA_0..15 in force.
# usage: ibwalk.py dump.bin start lo hi
import struct, sys

def main():
    path, start, lo, hi = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
    b = open(path, 'rb').read()
    d = struct.unpack('<%dI' % (len(b) // 4), b[: len(b) // 4 * 4])
    sh = {}
    i = start
    names = {0x10: 'NOP', 0x76: 'SET_SH_REG', 0x15: 'DISPATCH_DIRECT', 0x16: 'DISPATCH_INDIRECT', 0x69: 'SET_CONTEXT_REG',
             0x79: 'SET_UCONFIG_REG', 0x37: 'WRITE_DATA', 0x3c: 'WAIT_REG_MEM', 0x46: 'EVENT_WRITE', 0x49: 'RELEASE_MEM',
             0x50: 'DMA_DATA', 0x26: 'ACQUIRE_MEM', 0x58: 'ACQUIRE_MEM', 0x22: 'COND_EXEC', 0x63: 'LOAD_SH_REG_INDEX',
             0x2d: 'DRAW_INDEX_AUTO', 0x27: 'DRAW_INDEX_2', 0x24: 'DRAW_INDIRECT', 0x25: 'DRAW_INDEX_INDIRECT',
             0x38: 'DRAW_INDEX_INDIRECT_MULTI', 0x2c: 'DRAW_INDIRECT_MULTI', 0x11: 'SET_BASE', 0x28: 'CONTEXT_CONTROL',
             0x3f: 'INDIRECT_BUFFER', 0x33: 'INDIRECT_BUFFER_CNST', 0x2f: 'RUN_LIST', 0x5f: 'RELEASE_MEM?', 0x6e: 'SET_SH_REG_INDEX?'}
    while i < len(d) and i < hi:
        h = d[i]
        t = h >> 30
        if h == 0xffff1000:  # the one-dword NOP filler
            i += 1
            continue
        if t != 3:
            if i >= lo: print('%6d type%d %08x' % (i, t, h))
            i += 1
            continue
        n = ((h >> 16) & 0x3fff) + 1
        op = (h >> 8) & 0xff
        body = d[i + 1: i + 1 + n]
        if op == 0x76 and n >= 2:
            for j in range(n - 1):
                sh[(body[0] & 0xffff) + j] = body[1 + j]
        if i >= lo:
            show = ' '.join('%08x' % x for x in body[:20]) + (' ...' if n > 20 else '')
            extra = ''
            if op in (0x15, 0x16):
                pgm = sh.get(0x20c, 0) | (sh.get(0x20d, 0) << 32)
                ud = ' '.join('%08x' % sh.get(0x240 + k, 0) for k in range(16))
                # SET_SH_REG only: registers a LOAD_SH_REG_INDEX loads from memory are not seen here
                # (the timeout probe's "cs" is the program in force).
                extra = '\n         SET_SH_REG-tracked CS pgm 0x%x (LO %08x HI %08x) rsrc1 %08x rsrc2 %08x tg %s ud %s' % (
                    pgm << 8, sh.get(0x20c, 0), sh.get(0x20d, 0), sh.get(0x212, 0), sh.get(0x213, 0),
                    '/'.join('%x' % sh.get(r, 0) for r in (0x207, 0x208, 0x209)), ud)
            print('%6d %-22s n=%-4d %s%s' % (i, names.get(op, 'op%02x' % op), n, show, extra))
        i += 1 + n

main()
