#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""BC5 experiment 0438: read-only, on the box: the bytes around the Render Thread's hot guest ips (gip438.py's list),
from the title's own executable files, into a private directory outside every git checkout. Nothing here is committed;
the bytes and their disassembly stay private (hard rule 1); the experiment's README describes behaviour only.
Usage: python3 -I gipbytes438.py HOT_IPS.txt MAPS.txt TITLE_ID [GAME_DIR]
  HOT_IPS.txt  "base offset samples" per line (hex, hex, dec), gip438.py's output.
  MAPS.txt     a /proc/<pid>/maps snapshot of a run (prof0438's -maps-<n>.txt): the guest's KytyPrivateMemory regions.
  GAME_DIR     the title's directory holding eboot.bin; without it, the one directory under ~/bc5-data whose path holds
               TITLE_ID and which holds an eboot.bin (more or none: stop).
For each module base in HOT_IPS, the module file is the ELF in GAME_DIR (eboot.bin, then sce_module/*.prx|*.sprx) whose
first loadable segment, page-rounded, has the size of the first maps region at that base (an exact match is
required, or nothing is read for that base). A guest offset is turned into a file offset through that file's program
headers (p_vaddr .. p_vaddr + p_filesz). For each ip, 256 bytes from ip - 128 (windows merged when they overlap).
Output: ~/bc5-data/private/exp0438-hotcode/ (mode 700): <base>+<start>.bin per window, index.txt (base, file, file
offsets, the ips in each window and their samples), and the matching evidence. Only opens files for reading.
"""
import os
import struct
import sys

hot_p, maps_p, title = sys.argv[1], sys.argv[2], sys.argv[3]
game = sys.argv[4] if len(sys.argv) > 4 else None
out = os.path.expanduser('~/bc5-data/private/exp0438-hotcode')
home = os.path.expanduser('~')
assert os.path.normpath(out).startswith(os.path.normpath(os.path.join(home, 'bc5-data')) + os.sep)


def stop(msg):
    print('gipbytes438 STOP:', msg)
    sys.exit(1)


if game is None:
    cands = []
    for root, dirs, files in os.walk(os.path.join(home, 'bc5-data'), followlinks=False):
        parts = os.path.normpath(root).split(os.sep)
        depth = os.path.normpath(root)[len(os.path.normpath(home)):].count(os.sep)
        if depth > 6:
            dirs[:] = []
            continue
        if 'private' in parts or 'captures' in parts or 'saves' in parts:
            dirs[:] = []
            continue
        if title in root and 'eboot.bin' in files:
            cands.append(root)
    if len(cands) != 1:
        stop(f'game directory not found uniquely under ~/bc5-data: {cands} (give GAME_DIR)')
    game = cands[0]
print('game directory:', game)

hot = []
for ln in open(hot_p):
    p = ln.split()
    if len(p) == 3:
        hot.append((int(p[0], 16), int(p[1], 16), int(p[2])))
regions = {}
for ln in open(maps_p):
    p = ln.split()
    if len(p) >= 6 and 'KytyPrivateMemory' in ln:
        a, b = (int(x, 16) for x in p[0].split('-'))
        regions.setdefault(a & ~0xfffffff, []).append((a, b, p[1]))
for k in regions:
    regions[k].sort()


def elf_loads(path):
    with open(path, 'rb') as f:
        h = f.read(64)
        if len(h) < 64 or h[:4] != b'\x7fELF' or h[4] != 2:
            return None
        phoff, = struct.unpack_from('<Q', h, 0x20)
        phentsize, phnum = struct.unpack_from('<HH', h, 0x36)
        f.seek(phoff)
        segs = []
        for _ in range(phnum):
            e = f.read(phentsize)
            ptype, flags, off, vaddr, paddr, filesz, memsz, align = struct.unpack_from('<IIQQQQQQ', e, 0)
            segs.append((ptype, flags, off, vaddr, filesz, memsz))
        return segs


files = []
for name in ['eboot.bin']:
    p = os.path.join(game, name)
    if os.path.isfile(p):
        files.append(p)
md = os.path.join(game, 'sce_module')
if os.path.isdir(md):
    for n in sorted(os.listdir(md)):
        if n.endswith(('.prx', '.sprx', '.elf')):
            files.append(os.path.join(md, n))
os.makedirs(out, mode=0o700, exist_ok=True)
os.chmod(out, 0o700)
idx = open(os.path.join(out, 'index.txt'), 'w')
pg = lambda x: (x + 0xfff) & ~0xfff
for base in sorted({h[0] for h in hot}):
    regs = regions.get(base)
    if not regs:
        print(f'base {base:x}: no maps region')
        continue
    want = regs[0][1] - regs[0][0]
    match = None
    for p in files:
        segs = elf_loads(p)
        if not segs:
            continue
        loads = [s for s in segs if s[0] == 1 or (s[0] & 0xff000000) == 0x61000000]
        if not loads:
            continue
        first = min(loads, key=lambda s: s[3])
        if first[3] == 0 and pg(first[5]) == want:
            if match is not None:
                stop(f'base {base:x}: two files match ({match[0]}, {p})')
            match = (p, loads)
    msg = f'base {base:x}: first region {regs[0][0]:x}-{regs[0][1]:x} ({want:#x}); file ' + (match[0] if match else 'NONE')
    print(msg)
    idx.write(msg + '\n')
    if match is None:
        continue
    path, loads = match
    for s in loads:
        idx.write(f'  segment type {s[0]:#x} flags {s[1]:#x} file {s[2]:#x} vaddr {s[3]:#x} filesz {s[4]:#x} memsz {s[5]:#x}\n')
    ips = sorted((o, n) for b, o, n in hot if b == base)
    wins = []
    for o, n in ips:
        a, b = max(0, o - 128), o + 128
        if wins and a <= wins[-1][1]:
            wins[-1][1] = max(wins[-1][1], b)
            wins[-1][2].append((o, n))
        else:
            wins.append([a, b, [(o, n)]])
    with open(path, 'rb') as f:
        for a, b, members in wins:
            seg = next((s for s in loads if s[3] <= a and b <= s[3] + s[4]), None)
            if seg is None:
                idx.write(f'  window {a:#x}-{b:#x}: not inside one segment\'s file bytes\n')
                continue
            fo = seg[2] + (a - seg[3])
            f.seek(fo)
            data = f.read(b - a)
            fn = os.path.join(out, f'{base:x}+{a:x}.bin')
            with open(fn, 'wb') as g:
                g.write(data)
            os.chmod(fn, 0o600)
            idx.write(f'  window {a:#x}-{b:#x} file offset {fo:#x} {len(data)} bytes; ips ' + ' '.join(f'{o:#x}:{n}' for o, n in members) + '\n')
idx.close()
os.chmod(os.path.join(out, 'index.txt'), 0o600)
print('written to', out)
