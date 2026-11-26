#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""BC5 experiment 0438: read-only, on the box: the code in the title's main module that addresses one data location
(RIP-relative), to find who writes a state word the Render Thread spins on. Private output only (hard rule 1).
Usage: python3 -I xref438.py EBOOT TARGET_OFFSET [OUT_DIR]
  EBOOT          the title's eboot.bin (a SELF as KytyPlus's loader reads it, or a plain ELF; gipbytes438.py's rules: a
                 compressed or differing segment is refused).
  TARGET_OFFSET  the location's offset in the module (hex), e.g. the state word's.
  OUT_DIR        default ~/bc5-data/private/exp0438-xref (mode 700).
It reads the module's executable load segments (p_flags & 1), and for every 4-byte little-endian displacement d at
position j whose RIP-relative target j + 4 + k + d (k = 0, 1, 2 or 4 immediate bytes after it) is TARGET, records j.
For each, the 64 bytes before and 16 after go to <out>/cand-<vaddr>.bin; xref438-dis.sh decodes them with the host's
objdump and keeps only the instructions that end at that target (loads, stores, atomics are told apart there).
"""
import os
import struct
import sys

path, target = sys.argv[1], int(sys.argv[2], 16)
out = sys.argv[3] if len(sys.argv) > 3 else os.path.expanduser('~/bc5-data/private/exp0438-xref')
SELF_MAGICS = (bytes.fromhex('4f153d1d'), bytes.fromhex('5414f5ee'))


def loads(f):
    h = f.read(32)
    self_segs, ehdr_pos = None, 0
    if h[:4] in SELF_MAGICS:
        n, = struct.unpack_from('<H', h, 24)
        self_segs = [struct.unpack('<QQQQ', f.read(32)) for _ in range(n)]
        ehdr_pos = 32 + 32 * n
    f.seek(ehdr_pos)
    e = f.read(64)
    assert e[:4] == b'\x7fELF' and e[4] == 2, 'not an ELF inside'
    phoff, = struct.unpack_from('<Q', e, 0x20)
    phentsize, phnum = struct.unpack_from('<HH', e, 0x36)
    f.seek(ehdr_pos + phoff)
    phs = [struct.unpack_from('<IIQQQQQQ', f.read(phentsize), 0) for _ in range(phnum)]
    res = []
    for i, (pt, fl, off, va, pa, fs, ms, al) in enumerate(phs):
        if pt != 1 or not fl & 1:
            continue
        pos = off
        if self_segs is not None:
            pos = None
            for typ, soff, csz, dsz in self_segs:
                if typ & 0x800 and ((typ >> 20) & 0xfff) == i:
                    pos = soff if csz == dsz == fs else None
                    break
        if pos is None:
            print(f'segment {i}: compressed or not stored plainly: refused')
            continue
        res.append((va, fs, pos))
    return res


os.makedirs(out, mode=0o700, exist_ok=True)
os.chmod(out, 0o700)
hits = []
with open(path, 'rb') as f:
    for va, fs, pos in loads(f):
        f.seek(pos)
        code = f.read(fs)
        want = {target - va - 4 - k: k for k in (0, 1, 2, 4)}  # value(j) + j at a hit, by immediate size k
        try:
            import numpy as np
            C = 1 << 22
            for c0 in range(0, len(code) - 3, C):
                seg = np.frombuffer(code[c0:c0 + C + 3], dtype=np.uint8).astype(np.int64)
                n = len(seg) - 3
                v = seg[:n] | (seg[1:n + 1] << 8) | (seg[2:n + 2] << 16) | (seg[3:n + 3] << 24)
                v = np.where(v >= 2**31, v - 2**32, v) + np.arange(c0, c0 + n, dtype=np.int64)
                for w, k in want.items():
                    for jj in np.nonzero(v == w)[0]:
                        hits.append((va + c0 + int(jj), k))
        except ImportError:
            for al in range(4):
                for idx_, (d,) in enumerate(struct.iter_unpack('<i', code[al:al + ((len(code) - al) // 4) * 4])):
                    jj = al + 4 * idx_
                    k = want.get(d + jj)
                    if k is not None:
                        hits.append((va + jj, k))
        hits.sort()
        print(f'segment va {va:#x} size {fs:#x}: scanned')
        with open(os.path.join(out, 'index.txt'), 'w') as idx:
            idx.write(f'target {target:#x}; candidates {len(hits)}\n')
            for v, k in hits:
                a = max(va, v - 64)
                b = min(va + fs, v + 4 + k + 16)
                fn = os.path.join(out, f'cand-{v:x}.bin')
                with open(fn, 'wb') as g:
                    g.write(code[a - va:b - va])
                os.chmod(fn, 0o600)
                idx.write(f'{v:#x} imm {k} window {a:#x}-{b:#x}\n')
print(f'{len(hits)} candidates -> {out}')
