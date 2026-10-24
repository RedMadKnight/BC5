#!/usr/bin/env python3
# BC5 experiment 0279: where in a timed-out graphics buffer the GFX CP's fetcher stood, from a devcoredump's CP_IB1
# registers. The IB the CP ran is the host's copy (the probe's ib-timeout dump) with exp 0052's GPU check inserted by the
# backend (backend/src/indirect_check.cpp, GFX ring, SET_BASE known): 44 dwords in front of each 3-dword DISPATCH_INDIRECT
# (WRITE_DATA 5 + 3 x COND_WRITE 9 + WRITE_DATA 5 + PFP_SYNC_ME 2 + COND_EXEC 5) and 35 in front of each 5-dword
# DRAW_INDIRECT / DRAW_INDEX_INDIRECT (2 counts), 2 (PFP_SYNC_ME) without a base; dropped packets (the probe's DROPPED
# marks) are NOPs of the same size and get no check. The model's total is compared with CP_IB1_CMD_BUFSZ; the fetched
# count (CMD_BUFSZ - IB1_BUFSZ) is mapped back to the title's offset. Prints the expanded size and the packets around it.
# usage: model0279.py <ib-timeout-*.bin> <probe lines (the journal's "timeout probe:" lines)> <cmd_bufsz> <ib1_bufsz>
import re, struct, sys

dump, probe_path, cmd, left = sys.argv[1], sys.argv[2], int(sys.argv[3], 0), int(sys.argv[4], 0)
d = open(dump, 'rb').read()
w = struct.unpack('<%dI' % (len(d) // 4), d)
marks, prog, grid = {}, {}, {}
for l in open(probe_path, encoding='utf-8', errors='replace'):
    m = re.match(r'timeout probe: (?:dispatch op \w\w|op \w\w|wait op \w\w|write op \w\w) at (\d+):.*?( ran| DROPPED)', l)
    if m:
        marks[int(m.group(1))] = m.group(2).strip()
    m = re.match(r'timeout probe: dispatch op \w\w at (\d+): program (?:not set in this buffer, )?(0x[0-9a-f]+), groups (\S+ x \S+ x \S+|\?)', l)
    if m:
        prog[int(m.group(1))], grid[int(m.group(1))] = m.group(2), m.group(3)
rows, q, base, out = [], 0, 0, 0
while q < len(w):
    h = w[q]
    n = 1
    if h >> 30 in (3, 0):
        c = (h >> 16) & 0x3fff
        n = 1 if c == 0x3fff else c + 2
    op = (h >> 8) & 0xff if h >> 30 == 3 else None
    if op == 0x11 and n >= 4 and (w[q + 1] & 0xf) == 1:
        base = (w[q + 2] & ~3) | ((w[q + 3] & 0xffff) << 32)
    ins = 0
    if marks.get(q) != 'DROPPED':
        if op == 0x16 and n == 3:
            ins = 44 if base else 2
        elif op in (0x24, 0x25) and n == 5:
            ins = 35 if base else 2
    rows.append((q, n, op, out))
    out += ins + n
    q += n
fetched = cmd - left
print(f'modelled size {out} dwords, CP_IB1_CMD_BUFSZ {cmd} (difference {cmd - out}); fetched {fetched}')
k = max(i for i, r in enumerate(rows) if r[3] <= fetched)
print(f'the fetcher stood at title offset {rows[k][0]} (op {rows[k][2]:#x})' if rows[k][2] is not None else f'title offset {rows[k][0]}')
for q, n, op, at in rows[max(0, k - 12):k + 4]:
    if op in (0x15, 0x16):
        print(f'{q:6d}  expanded {at:6d}  op {op:02x}  program {prog.get(q, "?")}  groups {grid.get(q, "?")}  {marks.get(q, "")}')
