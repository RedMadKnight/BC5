#!/usr/bin/env python3
# BC5 exp 0439 (tag sr439b): the reader of the frame-dump catcher's captures (mksr439b.py writes them on the box; copy the
# capture directories off first). Names the op that most likely makes the NaN/Inf, in frame order:
#   - every surface with NaN/Inf at the end of frame F (index.tsv F_nan + F_inf), and its F+1 count (growth = feedback);
#   - its writers: the draws that bind it as a colour target ('w'), else the ops whose V#s reach it ('v': a compute
#     UAV or a texture, read or write unknown from the descriptor alone);
#   - a writer whose OTHER surfaces were all NaN-free at the end of F is a source candidate (it made NaN from clean
#     inputs); the earliest such op in frame order ranks first, ties by the smaller NaN fraction (closest to onset);
#   - surfaces that hold NaN in F and more in F+1 and are referenced as both 'w' and 'v' are listed as feedback buffers.
# The end-of-frame census cannot see a NaN that a later op of the same frame overwrote; DCC-compressed targets (dcc 1)
# are counted on their raw bytes and marked as such.
# Usage: python sr439read.py CAPTURE_DIR [CAPTURE_DIR_5S_LATER]
import csv
import os
import sys
from collections import Counter, defaultdict


def load(d):
    surf = {}
    with open(os.path.join(d, 'index.tsv'), newline='') as f:
        for r in csv.DictReader(f, delimiter='\t'):
            for k in ('id', 'bytes', 'w', 'h', 'd', 'dcc', 'first_op', 'cb_writes', 'refs', 'F_elems', 'F_nan', 'F_inf', 'F_ok', 'F1_elems', 'F1_nan', 'F1_inf', 'F1_ok'):
                r[k] = int(r[k])
            surf[r['id']] = r
    ops = []
    with open(os.path.join(d, 'ops.tsv'), newline='') as f:
        for r in csv.DictReader(f, delimiter='\t'):
            refs = []
            for x in r['refs'].split(',') if r['refs'] else []:
                sid, role = x.split(':')
                refs.append((int(sid), role))
            ops.append({'seq': int(r['seq']), 'submit': int(r['submit']), 'ring': int(r['ring']), 'kind': r['kind'], 'pgm': r['pgm'], 'cb_mode': int(r['cb_mode']), 'refs': refs})
    clears = []
    p = os.path.join(d, 'clears.tsv')
    if os.path.exists(p):
        with open(p, newline='') as f:
            clears = list(csv.DictReader(f, delimiter='\t'))
    return surf, ops, clears


# GFX10_FORMAT float formats (gfx10-rsrc.json enum GFX10_FORMAT): 16, 16_16, 16x4, 32, 32 clamp, 32x2, 32x3, 32x4, 11-11-10, 10-11-11
FLOATS = {'13', '29', '71', '22', '140', '64', '74', '77', '43', '36'}


def bad(s, slot='F'):
    return s[slot + '_nan'] + s[slot + '_inf']


def describe(s):
    frac = bad(s) / s['F_elems'] if s['F_elems'] else 0.0
    return '%s #%d %s %dx%dx%d %s%s NaN/Inf F %d (%.4f%%) F+1 %d%s' % (s['role'], s['id'], s['base'], s['w'], s['h'], s['d'], s['kind'], ' DCC-raw' if s['dcc'] else '',
                                                               bad(s), 100 * frac, bad(s, 'F1'), '' if s['F_ok'] else ' (unreadable at census)')


def report(d):
    surf, ops, clears = load(d)
    print('== %s: %d surfaces, %d ops, %d clears' % (d, len(surf), len(ops), len(clears)))
    # census v2: a compressed surface's bytes are not pixels and a raw buffer is not floats: both out of the ranking
    nanset = {i for i, s in surf.items() if bad(s) > 0 and not s['dcc'] and s['kind'] != 'other' and s['role'] != 'buffer'}  # buffers out: interleaved vertex data and integer/raw buffers cannot be counted per byte (run 2346)
    skipped = sum(1 for s in surf.values() if bad(s) > 0) - len(nanset)
    if skipped:
        print('(%d NaN-counted surfaces left out: compressed, or raw)' % skipped)
    print('surfaces with NaN/Inf at the end of F: %d' % len(nanset))
    for i in sorted(nanset, key=lambda i: surf[i]['first_op']):
        print('   ', describe(surf[i]), 'first op', surf[i]['first_op'])
    cands = []
    for o in ops:
        outs = [sid for sid, role in o['refs'] if role == 'w' and sid in nanset]
        if not outs and o['kind'] == 'c':
            outs = [sid for sid, role in o['refs'] if sid in nanset]
        for x in outs:
            others = [sid for sid, _ in o['refs'] if sid != x]
            dirty = [sid for sid in others if sid in nanset]
            if not dirty:
                s = surf[x]
                frac = bad(s) / s['F_elems'] if s['F_elems'] else 1.0
                cands.append((o['seq'], frac, o, x))
    cands.sort(key=lambda c: (c[0], c[1]))
    print('source candidates (an op whose other surfaces were clean; earliest first):')
    for seq, frac, o, x in cands[:15]:
        print('    op %d (%s, ring %d, submit %d, program %s, CB mode %d) -> %s' % (seq, 'draw' if o['kind'] == 'd' else 'dispatch', o['ring'], o['submit'], o['pgm'], o['cb_mode'], describe(surf[x])))
    if not cands:
        print('    none: every NaN surface is touched by ops that also touch another NaN surface (a cycle: see the feedback list)')
    roles = defaultdict(set)
    for o in ops:
        for sid, role in o['refs']:
            roles[sid].add(role)
    fb = [i for i in nanset if bad(surf[i], 'F1') > bad(surf[i]) and len(roles[i]) > 1]
    print('feedback buffers (NaN growing F -> F+1, both written and bound as a V#): %d' % len(fb))
    for i in fb:
        print('   ', describe(surf[i]))
    kinds = Counter(c['what'].split(' 0x')[0].split(' on target')[0] for c in clears)
    print('clears:', ', '.join('%s x%d' % kv for kv in kinds.most_common()))
    dcc_report(surf, ops)
    return surf


def dcc_report(surf, ops):
    """exp 0439 (tag dk439): every DCC colour target with its DCC_CONTROL, DCC_BASE and key histogram at the end of F,
    and every image that reads the same base: its V# compression bit, metadata address (word6 [31:24] and word7, the
    address >> 8) and whether that address is the target's DCC_BASE. Captures from before dk439 have no such columns."""
    any_s = next(iter(surf.values()), None)
    if any_s is None or 'dcc_base' not in any_s:
        print('DCC targets: this capture has no dk439 columns')
        return
    cbs = [s for s in surf.values() if s['role'] == 'cb' and s['dcc'] and int(s['dcc_base'], 16) != 0]
    print('DCC colour targets: %d' % len(cbs))
    for s in cbs:
        ctl = int(s['dcc_control'], 16)
        n = int(s['keys_n'])
        print('    %s: DCC_CONTROL 0x%08x (max uncompressed %d, max compressed %d, independent 64B %d, 128B %d), DCC_BASE %s, keys %d: 0xff %s, 0x00 %s, other %s (most %s x%s)' % (
            describe(s), ctl, (ctl >> 2) & 3, (ctl >> 5) & 3, (ctl >> 9) & 1, (ctl >> 20) & 1, s['dcc_base'], n, s['keys_ff'], s['keys_00'], s['keys_other'], s['keys_top'], s['keys_top_n']))
        for t in surf.values():
            if t['role'] == 'image' and t['base'] == s['base']:
                w6, w7 = int(t['word6'], 16), int(t['word7'], 16)
                meta = ((w7 << 8) | (w6 >> 24)) << 8
                print('        read as %s: COMPRESSION_EN %d, word6 0x%08x, metadata 0x%x (%s)' % (describe(t), (w6 >> 21) & 1, w6, meta,
                      'the target\'s DCC_BASE' if meta == int(s['dcc_base'], 16) else 'NOT the target\'s DCC_BASE'))


def main():
    a = report(sys.argv[1])
    if len(sys.argv) > 2:
        b = report(sys.argv[2])
        by_base = {s['base']: s for s in b.values()}
        print('== growth over 5 s (same base address):')
        for s in sorted(a.values(), key=lambda s: -bad(s)):
            t = by_base.get(s['base'])
            if t is not None and (bad(s) or bad(t)):
                print('    %s: %d -> %d' % (describe(s), bad(s), bad(t)))


if __name__ == '__main__':
    main()
