#!/usr/bin/env python3
# BC5 exp 0439 (tag sr439c): the pass census's reader (laptop; numpy, and PIL for the shot classifier; run without -I).
#   python sr439cread.py BAD_DIR GOOD_DIR [--shots SHOT_DIR]
#   python sr439cread.py --one DIR                 (one capture: its passes and kinds)
#   python sr439cread.py --classify SHOT.png ...   (black / good from a screenshot)
# A capture dir is <dump>/sr439c-<time>-a<n>-A (frame B, when the plan split the frame, is read with it from -B).
# What it prints:
#   - each capture's plan and skips (meta.txt);
#   - the pair: incarnations matched by (surface, k-th incarnation of that surface, the pass's programs); for each its
#     kind in the window tiles: nan (any NaN/Inf), zero (> 99 % zero elements), dark (> 95 % dark), same (every tile's
#     hash equals the surface's previous incarnation in this capture), content; a DCC target's kind from its keys too;
#   - the FIRST pass in frame order whose output kind differs between bad and good, its programs, ring, submit, piece,
#     and each of its inputs' path: the last writer before it in the frame (pass, ring, piece), or "no writer in this
#     frame" (written by the CPU or in an earlier frame; a label-gated DMA copy is not recorded as an op in v1);
#   - the grid: per incarnation of a plain (non-DCC) target, the 8x8-block edge ratio of its window tiles (the mean
#     jump between neighbouring 256-byte blocks over the mean spread inside them; a heuristic, the tile's inner layout
#     is not decoded) and the first incarnation where it stands out (over 3x the median of all incarnations).
# The shot classifier: the share of robe-yellow pixels in the character's box (classify(); the game area is
# 320..1600 x 172..892 of the box's 1920x1080 shots), calibrated on the 11-23 hold slot's shots.
import os
import struct
import sys
from collections import defaultdict

import numpy as np


def tsv(path):
    rows = []
    with open(path) as f:
        hdr = f.readline().rstrip('\n').split('\t')
        for line in f:
            rows.append(dict(zip(hdr, line.rstrip('\n').split('\t'))))
    return rows


class Capture:
    def __init__(self, d):
        self.dirs = [d] + ([d[:-2] + '-B'] if d.endswith('-A') and os.path.isdir(d[:-2] + '-B') else [])
        self.meta = ''.join(open(os.path.join(x, 'meta.txt')).read() for x in self.dirs if os.path.exists(os.path.join(x, 'meta.txt')))
        self.surf = {int(r['id']): r for r in tsv(os.path.join(d, 'surf.tsv'))}
        self.ops = []
        self.inc = []
        self.tiles = defaultdict(list)
        for fi, x in enumerate(self.dirs):
            ops = tsv(os.path.join(x, 'ops.tsv'))
            for o in ops:
                o['frame'] = fi
            self.ops += ops
            base = len(self.inc)
            for r in tsv(os.path.join(x, 'inc.tsv')):
                r['frame'] = fi
                r['dir'] = x
                r['gid'] = base + int(r['inc'])
                self.inc.append(r)
            for t in tsv(os.path.join(x, 'tiles.tsv')):
                self.tiles[base + int(t['inc'])].append(t)
        self.by_seq = {(o['frame'], int(o['seq'])): o for o in self.ops}
        # frame order: frame, submit, piece (the order the passes ran on their ring, and submits in host order)
        self.inc.sort(key=lambda r: (r['frame'], int(r['submit']), int(r['piece']), int(r['inc'])))
        self.prev = {}
        last = {}
        for r in self.inc:
            if r['placed'] != '1':
                continue
            s = int(r['surf'])
            self.prev[r['gid']] = last.get(s)
            last[s] = r['gid']

    def skey(self, s):
        x = self.surf[s]
        return (x['base'], x['fmt'], x['role'])

    def pgms(self, r):
        ops = [o for o in self.ops if o['frame'] == r['frame'] and int(r['op0']) <= int(o['seq']) < int(r['op1'])]
        # op seq numbers are the recorder's, op0/op1 index the same list
        return tuple(o['pgm'] for o in ops)

    def kind(self, r):
        el, z, dk, nan = int(r['w_elems']), int(r['w_zero']), int(r['w_dark']), int(r['w_nan']) + int(r['w_inf'])
        if el == 0:
            el, z, dk, nan = int(r['elems']), int(r['zero']), int(r['dark']), int(r['nan']) + int(r['inf'])
        k = 'content'
        if int(r['keys']) > 0:
            k = 'dcc'  # its bytes are not pixels; the keys tell what kind of content
            n = int(r['keys'])
            if n and int(r['keys_ff']) == n:
                k = 'dcc-plain'
            elif n and int(r['keys_00']) > 0.99 * n:
                k = 'dcc-cleared'
        elif el == 0:
            k = 'none'
        elif nan:
            k = 'nan'
        elif z > 0.99 * el:
            k = 'zero'
        elif dk > 0.95 * el:
            k = 'dark'
        p = self.prev.get(r['gid'])
        if p is not None and k not in ('none',):
            a = [t['hash'] for t in self.tiles[r['gid']]]
            b = [t['hash'] for t in self.tiles[p]]
            if a and a == b:
                k = 'same'
        return k

    def writers_before(self, r):
        # every surface's last writer (an earlier placed pass writing it: its incarnations) before r in frame order
        out = {}
        for x in self.inc:
            if x is r:
                break
            if x['placed'] == '1':
                out[int(x['surf'])] = x
        return out

    def inputs(self, r):
        ins = set()
        for o in self.ops:
            if o['frame'] == r['frame'] and int(r['op0']) <= int(o['seq']) < int(r['op1']):
                for ref in filter(None, o['refs'].split(',')):
                    s, t = ref.split(':')
                    if t == 'v':
                        ins.add(int(s))
        return sorted(ins)


def match(bad, good):
    def seqs(c):
        m = defaultdict(list)
        for r in c.inc:
            if r['placed'] == '1':
                m[c.skey(int(r['surf']))].append(r)
        return m
    gb, gg = seqs(bad), seqs(good)
    pairs = []
    for key, lb in gb.items():
        lg = gg.get(key, [])
        for k, rb in enumerate(lb):
            rg = lg[k] if k < len(lg) else None
            if rg is not None and bad.pgms(rb) != good.pgms(rg):
                rg = None
            pairs.append((rb, rg))
    order = {id(r): i for i, r in enumerate(bad.inc)}
    pairs.sort(key=lambda p: order[id(p[0])])
    return pairs


def decode(raw, kind):
    a = np.frombuffer(raw, dtype=np.uint8)
    if kind == 'f32':
        return a.view(np.float32)
    if kind == 'f16':
        return a.view(np.float16).astype(np.float32)
    if kind == 'u8x4':
        return a[0::4].astype(np.float32)
    if kind == 'u10x3':
        return (a.view(np.uint32) & 0x3ff).astype(np.float32)
    if kind in ('r10g11b11f', 'r11g11b10f'):
        return (a.view(np.uint32) & 0x7ff).astype(np.float32)
    return a.astype(np.float32)


def grid_ratio(c, r):
    s = c.surf[int(r['surf'])]
    if int(r['keys']) > 0 or s['role'] not in ('cb', 'image'):
        return None
    path = os.path.join(r['dir'], 'tiles.bin')
    if not os.path.exists(path):
        return None
    vals = []
    with open(path, 'rb') as f:
        for t in c.tiles[r['gid']]:
            fo = int(t['file_off'])
            if fo < 0:
                continue
            f.seek(fo)
            v = decode(f.read(int(t['len'])), s['kind'])
            v = v[np.isfinite(v)]
            n = (v.size // 64) * 64
            if n < 128:
                continue
            blocks = v[:n].reshape(-1, 64) if s['kind'] in ('f32', 'u10x3', 'r10g11b11f', 'r11g11b10f', 'u8x4') else v[:n].reshape(-1, 64)
            means, spread = blocks.mean(axis=1), blocks.std(axis=1).mean()
            jump = np.abs(np.diff(means)).mean()
            if spread > 0:
                vals.append(jump / spread)
    return float(np.median(vals)) if vals else None


def classify(png):
    # robe-yellow: hue 45-55 deg, saturation >= 0.4, value 0.25-0.9 (the lantern's glow is more orange and brighter), in
    # x 0.05-0.65, y 0.30-0.98 of the game area. Calibrated 11-23 on the hold slot's 30 shots labelled by eye (15 good,
    # 12 black, 3 half-dark left out): good >= 0.0023, black <= 0.00028; threshold 0.0008.
    from PIL import Image
    a = np.asarray(Image.open(png).convert('HSV')).astype(np.float32)
    g = a[172:892, 320:1600]
    h, w = g.shape[:2]
    box = g[int(0.30 * h):int(0.98 * h), int(0.05 * w):int(0.65 * w)]
    H, S, V = box[..., 0] * 360 / 255, box[..., 1] / 255, box[..., 2] / 255
    y = float(((H >= 45) & (H <= 55) & (S >= 0.4) & (V >= 0.25) & (V <= 0.9)).mean())
    return ('black' if y < 0.0008 else 'good'), y


def rt_offset32(x, y):
    # The byte offset of element (x, y) inside a 64 KiB render-target block, 4 bytes per element: KytyPlus
    # src/graphics/guest_gpu/tile.cpp Gen5RenderTargetOffsetInBlock<uint32_t> (GPL-2.0, refs/Coder787-source_KytyPlus
    # 3eee96a); the block XOR of a 2D render target is 0 at 4 bytes (TileGetBlockXor: the block origin's offset, whose
    # bits all fall below the masks); blocks row-major over the 128-aligned width (TODO(verify): the picture shows it).
    o = np.zeros(np.broadcast(x, y).shape, dtype=np.uint32)
    o ^= (y << 4) & 0x0070
    o ^= (y << 5) & 0x0f00
    o ^= (y << 9) & 0x1000
    o ^= (y << 8) & 0x4000
    o ^= (x << 2) & 0x000c
    o ^= (x << 5) & 0x0380
    o ^= (x << 4) & 0x0400
    o ^= (x << 6) & 0x0800
    o ^= (x << 9) & 0xa000
    return o


def display_png(d):
    # <frame dir>/display.raw (+ display.txt) -> display.png (the frame's own picture, 2_10_10_10 decoded to 8 bits)
    from PIL import Image
    info = open(os.path.join(d, 'display.txt')).read().split()
    w, h = int(info[1]), int(info[3])
    raw = np.fromfile(os.path.join(d, 'display.raw'), dtype=np.uint32)
    tx = (w + 127) // 128
    y, x = np.mgrid[0:h, 0:w].astype(np.uint32)
    addr = (((y >> 7) * tx + (x >> 7)).astype(np.uint64) * 65536 + rt_offset32(x & 127, y & 127)) // 4
    px = raw[np.minimum(addr, raw.size - 1)]
    rgb = np.stack([(px >> s) & 0x3ff for s in (0, 10, 20)], axis=-1).astype(np.float32)
    img = Image.fromarray(np.clip(rgb / 1023.0 * 255.0, 0, 255).astype(np.uint8))
    out = os.path.join(d, 'display.png')
    img.save(out)
    return out


def classify_display(d):
    # the robe-yellow count on the frame's own picture (a convenience: the picture is the label)
    from PIL import Image
    png = os.path.join(d, 'display.png')
    if not os.path.exists(png):
        display_png(d)
    a = np.asarray(Image.open(png).convert('HSV')).astype(np.float32)
    h, w = a.shape[:2]
    box = a[int(0.30 * h):int(0.98 * h), int(0.05 * w):int(0.65 * w)]
    H, S, V = box[..., 0] * 360 / 255, box[..., 1] / 255, box[..., 2] / 255
    return float(((H >= 45) & (H <= 55) & (S >= 0.4) & (V >= 0.25) & (V <= 0.9)).mean())


def show_one(c, name):
    print('==', name)
    print(c.meta.strip())
    kinds = defaultdict(int)
    for r in c.inc:
        if r['placed'] == '1':
            kinds[c.kind(r)] += 1
    print('kinds:', dict(kinds))


def main(argv):
    if argv[:1] == ['--classify']:
        for p in argv[1:]:
            k, y = classify(p)
            print('%s: %s (yellow %.3f)' % (p, k, y))
        return
    if argv[:1] == ['--lead']:
        # --lead BASE PIECE DIR...: per frame dir (A or B, whichever copied the pass), the target's incarnation at the
        # pass nearest PIECE, its window state, and each of the pass's inputs: its last state before the pass and its path
        base, piece = argv[1], int(argv[2])
        for d in argv[3:]:
            c = Capture(d)
            c.dirs = [d]
            hit = None
            for r in c.inc:
                s = c.surf.get(int(r['surf']))
                if s is None or s['base'] != base or r['placed'] != '1':
                    continue
                if hit is None or abs(int(r['piece']) - piece) < abs(int(hit['piece']) - piece):
                    hit = r
            if hit is None or abs(int(hit['piece']) - piece) > 4:
                print('%s: the pass is not in this frame' % d)
                continue
            el = int(hit['w_elems']) or 1
            lab = ''
            if os.path.exists(os.path.join(d, 'display.raw')):
                lab = ' picture %s (robe-yellow %.4f)' % (display_png(d), classify_display(d))
            print('%s: piece %s target dark %.2f zero %.2f%s' % (d, hit['piece'], int(hit['w_dark']) / el, int(hit['w_zero']) / el, lab))
            wr = c.writers_before(hit)
            for i in c.inputs(hit):
                x = c.surf[i]
                w = wr.get(i)
                if w is None:
                    print('    in %5d %-6s %5sx%-5s %-10s %s: no writer earlier in this frame' % (i, x['role'], x['w'], x['h'], x['kind'], x['base']))
                    continue
                e = int(w['w_elems']) or int(w['elems']) or 1
                wk = 'w_' if int(w['w_elems']) else ''
                print('    in %5d %-6s %5sx%-5s %-10s %s: last written ring %s sub %s piece %s: %s dark %.2f zero %.2f nan %d keys %s/%s/%s' % (
                    i, x['role'], x['w'], x['h'], x['kind'], x['base'], w['ring'], w['submit'], w['piece'], c.kind(w),
                    int(w[wk + 'dark']) / e, int(w[wk + 'zero']) / e, int(w[wk + 'nan']) + int(w[wk + 'inf']), w['keys_ff'], w['keys_00'], w['keys_other']))
        return
    if argv[:1] == ['--display']:
        for d in argv[1:]:
            print('%s: %s, robe-yellow %.4f' % (d, display_png(d), classify_display(d)))
        return
    if argv[:1] == ['--one']:
        c = Capture(argv[1])
        show_one(c, argv[1])
        for r in c.inc:
            if r['placed'] == '1':
                s = c.surf[int(r['surf'])]
                print('  inc %s ring %s sub %s piece %s surf %s %s %sx%s %s: %s' % (r['inc'], r['ring'], r['submit'], r['piece'], r['surf'], s['role'], s['w'], s['h'], s['kind'], c.kind(r)))
        return
    bad, good = Capture(argv[0]), Capture(argv[1])
    show_one(bad, 'BAD ' + argv[0])
    show_one(good, 'GOOD ' + argv[1])
    pairs = match(bad, good)
    matched = [p for p in pairs if p[1] is not None]
    print('pairs: %d incarnations of the bad frame, %d matched in the good one' % (len(pairs), len(matched)))
    first = None
    for rb, rg in matched:
        kb, kg = bad.kind(rb), good.kind(rg)
        if kb != kg:
            first = (rb, rg, kb, kg)
            break
    if first is None:
        print('no matched pass differs in kind (window tiles); the difference is in content only, or in unmatched passes')
    else:
        rb, rg, kb, kg = first
        s = bad.surf[int(rb['surf'])]
        print('FIRST pass differing in kind: bad %s / good %s' % (kb, kg))
        print('  output surface %s %s %sx%s %s (base %s, dcc %s)' % (rb['surf'], s['role'], s['w'], s['h'], s['kind'], s['base'], s['dcc']))
        print('  ring %s, submit %s, piece %s (where %s: 0 a piece end, 1 the root, 2 a flattened job end)' % (rb['ring'], rb['submit'], rb['piece'], rb['where']))
        print('  programs:', ' '.join(sorted(set(bad.pgms(rb)))))
        wr = bad.writers_before(rb)
        for i in bad.inputs(rb):
            x = bad.surf[i]
            w = wr.get(i)
            path = 'no writer in this frame (CPU-written or an earlier frame)' if w is None else 'written by the pass at ring %s submit %s piece %s (%s)' % (w['ring'], w['submit'], w['piece'], bad.kind(w))
            print('  input %s %s %sx%s %s: %s' % (i, x['role'], x['w'], x['h'], x['kind'], path))
    # the grid
    ratios = []
    for r in bad.inc:
        if r['placed'] == '1':
            g = grid_ratio(bad, r)
            if g is not None:
                ratios.append((r, g))
    if ratios:
        med = float(np.median([g for _, g in ratios]))
        hit = next(((r, g) for r, g in ratios if g > 3 * med), None)
        print('grid: %d plain incarnations measured, median edge ratio %.2f' % (len(ratios), med))
        if hit:
            r, g = hit
            s = bad.surf[int(r['surf'])]
            print('  first standing out: inc %s surf %s %s %sx%s %s ratio %.2f (ring %s submit %s piece %s)' % (r['inc'], r['surf'], s['role'], s['w'], s['h'], s['kind'], g, r['ring'], r['submit'], r['piece']))


if __name__ == '__main__':
    main(sys.argv[1:])
