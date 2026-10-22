#!/usr/bin/env python3
# Scan a raw PM4 IB dump for values that point near a fault address: 64-bit pointer pairs,
# V# bases (dword0 + dword1[15:0]) and T# bases ((dword0 | dword1[7:0] << 32) << 8).
# Prints the hit with the enclosing type-3 packet (opcode, start) and the last SH register
# writes of COMPUTE_PGM_LO/HI and the graphics PGM_LO registers seen before it.
import struct, sys

def load(path):
    b = open(path, 'rb').read()
    return list(struct.unpack('<%dI' % (len(b) // 4), b[: len(b) // 4 * 4]))

def packets(d):
    i = 0
    out = []
    while i < len(d):
        h = d[i]
        t = h >> 30
        if h == 0xffff1000:  # the one-dword NOP filler
            i += 1
            continue
        if t == 3:
            n = ((h >> 16) & 0x3fff) + 1
            out.append((i, (h >> 8) & 0xff, n, h))
            i += 1 + n
        elif t == 2:
            i += 1
        else:
            out.append((i, -1, 0, h))
            i += 1
    return out

def main():
    path = sys.argv[1]
    faults = [int(x, 16) for x in sys.argv[2].split(',')]
    win = int(sys.argv[3], 16) if len(sys.argv) > 3 else 0x4000000
    d = load(path)
    pk = packets(d)
    owner = {}
    for (s, op, n, h) in pk:
        for k in range(s, min(s + 1 + n, len(d))):
            owner[k] = (s, op, n)
    sh = {}
    hits = []
    shpos = {}
    for (s, op, n, h) in pk:
        if op == 0x76 and n >= 2:  # SET_SH_REG
            base = d[s + 1] & 0xffff
            for j in range(n - 1):
                shpos.setdefault(s, {})[base + j] = d[s + 2 + j]
    def near(v):
        for f in faults:
            if abs(v - f) <= win:
                return f
        return None
    for i in range(len(d) - 1):
        lo, hi = d[i], d[i + 1]
        cands = []
        p64 = lo | (hi << 32)
        if near(p64) is not None: cands.append(('ptr64', p64))
        vb = lo | ((hi & 0xffff) << 32)
        if vb != p64 and near(vb) is not None: cands.append(('V#', vb))
        tb = (lo | ((hi & 0xff) << 32)) << 8
        if near(tb) is not None: cands.append(('T#', tb))
        for kind, v in cands:
            o = owner.get(i, (None, None, None))
            hits.append((i, kind, v, o))
    # context: last COMPUTE_PGM_LO (0x20c) / SPI_SHADER_PGM_LO_PS (0x8) / _ES(0xc8)/ _GS(0x88)/ _HS(0x108) written before each hit
    pgm_regs = {0x20c: 'CS', 0x8: 'PS', 0x88: 'GS', 0xc8: 'ES', 0x108: 'HS', 0x148: 'LS'}
    for (i, kind, v, o) in hits:
        last = {}
        for (s, regs) in shpos.items():
            if s > i: continue
            for r, val in regs.items():
                if r in pgm_regs:
                    if pgm_regs[r] not in last or last[pgm_regs[r]][0] < s:
                        last[pgm_regs[r]] = (s, val)
        ctx = ' '.join('%s@%d=0x%x' % (k, s, val) for k, (s, val) in sorted(last.items()))
        s, op, n = o
        reg = ''
        if op == 0x76 and s is not None:
            reg = ' reg 0x%x' % ((d[s + 1] & 0xffff) + (i - s - 2))
        print('dw %6d %-5s 0x%012x  pkt op 0x%s at %s len %s%s | %s' % (i, kind, v, ('%02x' % op) if op is not None and op >= 0 else '??', s, n, reg, ctx))
    print('packets %d, hits %d' % (len(pk), len(hits)))

main()
