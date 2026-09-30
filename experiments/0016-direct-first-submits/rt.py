#!/usr/bin/env python3
# Render-target / depth base addresses from the journaled LOAD_CONTEXT_REG_INDEX tables versus
# the resident userptr mappings of the same journal. Register offsets: Mesa gfx10 (bc5-agc
# regdb): CB_COLOR0_BASE mm 0xa318 (+0xf per target), CB_COLOR0_BASE_EXT 0xa390 (+1),
# CMASK 0xa31f/EXT 0xa398, FMASK 0xa321/EXT 0xa3a0, DCC 0xa325/EXT 0xa3a8, DB_Z_READ_BASE 0xa012,
# DB_STENCIL_READ_BASE 0xa013, DB_Z_WRITE_BASE 0xa014, DB_STENCIL_WRITE_BASE 0xa015,
# DB_HTILE_DATA_BASE 0xa005, *_HI 0xa01a..0xa01e.
import re, sys, collections

log = open(sys.argv[1], errors='replace').read()
maps = [(int(a, 16), int(a, 16) + int(b, 16)) for a, b in re.findall(r'^map 0x([0-9a-f]+) \+0x([0-9a-f]+) \.\.\. ok', log, re.M)]
def resident(addr):
    return any(a <= addr < b for a, b in maps)

regs = {}
for i in range(8):
    regs[0x318 + i * 0xf] = ('CB%d_BASE' % i, 0x390 + i)
    regs[0x31f + i * 0xf] = ('CB%d_CMASK' % i, 0x398 + i)
    regs[0x321 + i * 0xf] = ('CB%d_FMASK' % i, 0x3a0 + i)
    regs[0x325 + i * 0xf] = ('CB%d_DCC' % i, 0x3a8 + i)
regs[0x12] = ('DB_Z_READ', 0x1a); regs[0x13] = ('DB_STENCIL_READ', 0x1b)
regs[0x14] = ('DB_Z_WRITE', 0x1c); regs[0x15] = ('DB_STENCIL_WRITE', 0x1d)
regs[0x05] = ('DB_HTILE', 0x1e)

found = collections.Counter()
for m in re.finditer(r'^  load op 9f at \d+: addr 0x([0-9a-f]+) idx \d fmt 1 regoff 0x[0-9a-f]+ n (\d+):((?: [0-9a-f]{8})+)', log, re.M):
    words = [int(w, 16) for w in m.group(3).split()]
    table = {}
    for k in range(0, len(words) - 1, 2):
        table[words[k] & 0xffff] = words[k + 1]
    for off, (name, ext_off) in regs.items():
        if off in table and table[off] != 0:
            addr = (table[off] << 8) | ((table.get(ext_off, 0) & 0xff) << 40)
            found[(name, addr)] += 1
print('tables parsed; distinct RT/depth addresses: %d; resident mappings: %d' % (len(found), len(maps)))
res = nonres = 0
for (name, addr), c in sorted(found.items()):
    r = resident(addr)
    res += r; nonres += (not r)
    print('%-18s 0x%012x x%-3d %s' % (name, addr, c, 'resident' if r else 'NOT RESIDENT'))
print('resident %d, not resident %d' % (res, nonres))
