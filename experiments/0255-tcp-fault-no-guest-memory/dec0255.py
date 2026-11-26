#!/usr/bin/env python3
# BC5 experiment 0255: exp 0260's probe decode, offline, over timeout-probe dumps (ib-timeout-*.bin: the buffer as the
# host handed it to its filter, so dropped waits are still in it; which waits went to the GPU is not in the dump).
# For each dump: every WAIT_REG_MEM (0x3C) / WAIT_REG_MEM64 (0x93) with its label (or register), function, reference,
# mask and engine; every label write (RELEASE_MEM 0x49, EVENT_WRITE_EOP 0x47, WRITE_DATA 0x37 to memory) with its
# address, data select and value; every dispatch (0x15 / 0x16) with its size or indirect offset and the program set in
# the buffer before it (SET_SH_REG over COMPUTE_PGM_LO/HI, SH 0x20c/0x20d; one set by a LOAD_SH_REG_INDEX table is
# shown as "table"); COND_EXEC (0x22) and INDIRECT_BUFFER (0x3f). Fields as bc5LleAgc.cpp's wait_satisfied() and
# register_label_writes() read them; MEM_SPACE bits 5:4 and PFP bit 8: Mesa src/amd/common/sid.h @ 0866ae7, 90-95.
# Given two dumps of one timeout (a graphics and a compute buffer), the cross references: each wait of one on a label
# the other writes, with the write's offset relative to the writer's own waits and whether its value meets the wait.
# Only offsets, addresses, register values and counts are printed.
# usage: dec0255.py <dump.bin> [<dump.bin>]
import struct, sys

FN = {0: 'always', 1: '<', 2: '<=', 3: '==', 4: '!=', 5: '>=', 6: '>', 7: '?'}


def meets(fn, v, ref, mask):
    vm, rm = v & mask, ref & mask
    return {0: True, 1: vm < rm, 2: vm <= rm, 3: vm == rm, 4: vm != rm, 5: vm >= rm, 6: vm > rm}.get(fn, False)


def walk(ib):
    n, q = len(ib), 0
    while q < n:
        h = ib[q]
        t = h >> 30
        ln = 1
        if t in (0, 3):
            c = (h >> 16) & 0x3fff
            ln = 1 if c == 0x3fff else c + 2
        if q + ln > n:
            break
        yield q, t, (h >> 8) & 0xff, ib[q:q + ln]
        q += ln


def decode(path):
    raw = open(path, 'rb').read()
    ib = list(struct.unpack('<%dI' % (len(raw) // 4), raw[:len(raw) // 4 * 4]))
    waits, writes, disp, other = [], [], [], []
    pgm_lo = pgm_hi = None
    for q, t, op, p in walk(ib):
        if t != 3:
            continue
        ln = len(p)
        if (op == 0x3c and ln >= 7) or (op == 0x93 and ln >= 9):
            is64 = op == 0x93
            mem = ((p[1] >> 4) & 3) != 0
            a = (p[2] & ~3) | ((p[3] & 0xffff) << 32)
            ref = (p[4] | (p[5] << 32)) if is64 else p[4]
            mask = (p[6] | (p[7] << 32)) if is64 else p[5]
            waits.append(dict(q=q, op=op, mem=mem, a=a if mem else p[2], fn=p[1] & 7, ref=ref, mask=mask, pfp=(p[1] >> 8) & 1))
        elif (op == 0x49 and ln >= 8) or (op == 0x47 and ln >= 6) or (op == 0x37 and ln >= 5):
            lo = 3 if op == 0x49 else 2
            sel = p[2] >> 29 if op == 0x49 else (p[3] >> 29 if op == 0x47 else (p[1] >> 8) & 0xf)
            if op == 0x37 and sel not in (1, 2, 5):
                continue
            dk = 5 if op == 0x49 else 4
            two = ln >= 6 if op == 0x37 else sel != 1
            v = p[dk] | ((p[dk + 1] << 32) if two else 0)
            a = (p[lo] & ~3) | ((p[lo + 1] & 0xffff) << 32)
            writes.append(dict(q=q, op=op, a=a, sel=sel, v=v, ln=ln))
        elif op == 0x76 and ln >= 3:  # SET_SH_REG: first register p[1] & 0xffff, values from p[2]
            first = p[1] & 0xffff
            for k in range(ln - 2):
                if first + k == 0x20c:
                    pgm_lo = p[2 + k]
                if first + k == 0x20d:
                    pgm_hi = p[2 + k]
        elif op == 0x63 and ln >= 5:  # LOAD_SH_REG_INDEX (as bc5LleAgc.cpp's cs_inherit_at reads it): the table is in memory
            pairs, cnt = (p[3] >> 31) != 0, p[4] & 0x3fff
            if pairs or (0x20c - (p[3] & 0xffff)) % (1 << 32) < cnt:
                pgm_lo, pgm_hi = 'from a LOAD_SH_REG_INDEX table (in memory)', None
        elif op in (0x15, 0x16):
            if isinstance(pgm_lo, int):
                prog = '0x%x' % ((pgm_lo | ((pgm_hi or 0) & 0xff) << 32) << 8)
            else:
                prog = pgm_lo or 'not set in this buffer'
            size = ('%u x %u x %u' % (p[1], p[2], p[3])) if op == 0x15 and ln >= 4 else ('indirect +0x%x' % p[1] if ln >= 2 else '?')
            disp.append(dict(q=q, op=op, prog=prog, size=size))
        elif op in (0x22, 0x3f):
            other.append(dict(q=q, op=op, w=p[1:5]))
    return ib, waits, writes, disp, other


def show(path, ib, waits, writes, disp, other):
    print('== %s: %u dwords; %u waits, %u label writes, %u dispatches, %u COND_EXEC/IB' % (path.split('/')[-1], len(ib), len(waits), len(writes), len(disp), len(other)))
    for w in waits:
        print('  wait op %02x at %u: %s 0x%x function %s reference 0x%x mask 0x%x %s' % (w['op'], w['q'], 'label' if w['mem'] else 'register', w['a'], FN[w['fn']], w['ref'], w['mask'], 'pfp' if w['pfp'] else 'me'))
    for w in writes:
        print('  write op %02x at %u: 0x%x select %u value 0x%x (packet %u dwords)' % (w['op'], w['q'], w['a'], w['sel'], w['v'], w['ln']))
    for d in disp[:60]:
        print('  dispatch op %02x at %u: %s, program %s' % (d['op'], d['q'], d['size'], d['prog']))
    if len(disp) > 60:
        print('  ... %u dispatches more' % (len(disp) - 60))
    for o in other:
        print('  op %02x at %u: %s' % (o['op'], o['q'], ' '.join('%08x' % x for x in o['w'])))


def cross(na, a, nb, b):
    _, wa, _, _, _ = a
    _, _, xb, _, _ = b
    wb_waits = b[1]
    for w in wa:
        if not w['mem']:
            continue
        for x in xb:
            if x['a'] != w['a']:
                continue
            before = sum(1 for y in wb_waits if y['q'] < x['q'])
            print('  %s waits at %u on 0x%x (%s 0x%x): %s writes it at %u (select %u value 0x%x, %s), after %u of its own %u waits' % (
                na, w['q'], w['a'], FN[w['fn']], w['ref'], nb, x['q'], x['sel'], x['v'], 'meets' if meets(w['fn'], x['v'], w['ref'], w['mask']) else 'does NOT meet', before, len(wb_waits)))


def main():
    paths = sys.argv[1:]
    res = [decode(p) for p in paths]
    for p, r in zip(paths, res):
        show(p, *r)
    if len(paths) == 2:
        na, nb = (p.split('/')[-1] for p in paths)
        print('== cross references')
        cross(na, res[0], nb, res[1])
        cross(nb, res[1], na, res[0])


if __name__ == '__main__':
    main()
