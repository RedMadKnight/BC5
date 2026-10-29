#!/usr/bin/env bash
# BC5 exp 0376: walk the PM4 packet headers of the 09:48 timed-out dcb #183691 (the host's ib-timeout dump, private on
# the box) and print, for dwords 1200-2000 and around every dispatch, the type-3 opcode and offset only, plus the event
# type of EVENT_WRITE (its low 6 bits; VGT_EVENT_TYPE, Mesa src/amd/common/sid.h, CS_PARTIAL_FLUSH = 7) and the
# dispatch dims of DISPATCH_DIRECT. No payload leaves the box beyond those numbers. Read only, no GPU work.
# Opcodes: PM4 type-3 header bits 15:8 (Mesa pkt3.json / extra-opcodes.tsv in tools/bc5-agc/regdb).
# usage: ssh bc250 'bash -s' < walk0376.sh > raw/dcb-walk.txt
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator runs: not read"; exit 1; }
F=$HOME/bc5-data/captures/play-20261029-0944/gc/ib-timeout-00183691-dcb-11115.bin
python3 - "$F" <<'PY'
import struct, sys
d = open(sys.argv[1], 'rb').read()
w = struct.unpack('<%dI' % (len(d) // 4), d)
names = {0x10: 'NOP', 0x11: 'SET_BASE', 0x12: 'CLEAR_STATE', 0x15: 'DISPATCH_DIRECT', 0x16: 'DISPATCH_INDIRECT',
         0x22: 'COND_EXEC', 0x26: 'INDEX_BASE', 0x37: 'WRITE_DATA', 0x3c: 'WAIT_REG_MEM', 0x42: 'PFP_SYNC_ME',
         0x45: 'COND_WRITE', 0x46: 'EVENT_WRITE', 0x49: 'RELEASE_MEM', 0x50: 'DMA_DATA', 0x58: 'ACQUIRE_MEM',
         0x76: 'SET_SH_REG', 0x69: 'SET_CONTEXT_REG', 0x79: 'SET_UCONFIG_REG', 0x93: 'WAIT_REG_MEM64'}
i, n, out, hist = 0, len(w), [], {}
while i < n:
    h = w[i]; t = h >> 30
    if t == 3:
        cnt = (h >> 16) & 0x3fff; op = (h >> 8) & 0xff; ln = cnt + 2
        hist[op] = hist.get(op, 0) + 1
        ex = ''
        if op == 0x46 and i + 1 < n: ex = ' event_type %d' % (w[i + 1] & 0x3f)
        if op == 0x15 and i + 3 < n: ex = ' dims %d x %d x %d' % (w[i + 1], w[i + 2], w[i + 3])
        out.append((i, op, ln, ex))
        i += ln
    elif t == 2:
        i += 1
    else:
        i += ((h >> 16) & 0x3fff) + 2
print('dwords %d, type-3 packets %d' % (n, len(out)))
print('opcode histogram: ' + ' '.join('%02x:%d' % (k, hist[k]) for k in sorted(hist)))
for i, op, ln, ex in out:
    if 1200 <= i <= 2000 or op in (0x15, 0x16, 0x46, 0x58, 0x3c, 0x93):
        print('%6d op %02x %-18s len %d%s' % (i, op, names.get(op, ''), ln, ex))
PY
