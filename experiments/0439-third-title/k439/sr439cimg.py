#!/usr/bin/env python3
# BC5 exp 0439 (tag sr439c): one pass output's copied window as a picture (laptop; numpy + PIL, run without -I).
#   python sr439cimg.py FRAME_DIR INC [OUT.png]       one incarnation
#   python sr439cimg.py FRAME_DIR --surface BASE OUT  every incarnation of a surface, side by side, in frame order
# The window tiles (tiles.bin, 64 KiB each, their surface offsets in tiles.tsv) are placed by tile index (row-major
# blocks over the 128-aligned... block width, as the display surface's picture showed) and detiled inside the block with
# KytyPlus src/graphics/guest_gpu/tile.cpp Gen5RenderTargetOffsetInBlock (GPL-2.0; refs/Coder787-source_KytyPlus
# 3eee96a), for 1, 2, 4, 8 and 16 bytes per element. A surface in a texture (non-render-target) swizzle comes out
# scrambled inside each block: the block grid and its per-block level still show where it is dark. Values: the first
# channel per format (f16/f32 floats, unorm scaled), shown as the 1st..99th percentile of the picture.
import os
import sys

import numpy as np


def tsv(p):
    with open(p) as f:
        h = f.readline().rstrip('\n').split('\t')
        return [dict(zip(h, l.rstrip('\n').split('\t'))) for l in f]


def rt_offset(x, y, bpe):
    o = np.zeros(np.broadcast(x, y).shape, dtype=np.uint32)
    if bpe == 1:
        for v, s, m in ((y, 2, 0x0008), (y, 4, 0x0010), (y, 3, 0x00a0), (y, 5, 0x0f00), (y, 6, 0x1000), (y, 7, 0x4000)):
            o ^= (v << s) & m
        o ^= x & 0x0007
        for s, m in ((3, 0x0040), (5, 0x0300), (4, 0x0400), (6, 0x0800), (7, 0x2000), (8, 0x8000)):
            o ^= (x << s) & m
    elif bpe == 2:
        for s, m in ((4, 0x0070), (5, 0x0f00), (8, 0x5000)):
            o ^= (y << s) & m
        for s, m in ((1, 0x000e), (4, 0x0480), (5, 0x0300), (6, 0x0800), (7, 0x2000), (8, 0x8000)):
            o ^= (x << s) & m
    elif bpe == 4:
        for s, m in ((4, 0x0070), (5, 0x0f00), (9, 0x1000), (8, 0x4000)):
            o ^= (y << s) & m
        for s, m in ((2, 0x000c), (5, 0x0380), (4, 0x0400), (6, 0x0800), (9, 0xa000)):
            o ^= (x << s) & m
    elif bpe == 8:
        for s, m in ((4, 0x0010), (6, 0x0080), (5, 0x0f00), (10, 0x5000)):
            o ^= (y << s) & m
        for s, m in ((3, 0x0008), (4, 0x0460), (5, 0x0300), (6, 0x0800), (10, 0x2000), (9, 0x8000)):
            o ^= (x << s) & m
    elif bpe == 16:
        for s, m in ((4, 0x0410), (5, 0x0340), (6, 0x0800), (11, 0xa000)):
            o ^= (x << s) & m
        for s, m in ((5, 0x0f20), (6, 0x0080), (10, 0x1000), (11, 0x4000)):
            o ^= (y << s) & m
    return o


def block_dims(bpe):
    bits = 16 - int(np.log2(bpe))
    return 1 << ((bits + 1) // 2), 1 << (bits // 2)


def decode(raw, kind, bpe):
    a = np.frombuffer(raw, dtype=np.uint8)
    if kind == 'f32':
        return a.view(np.float32)[::max(1, bpe // 4)].astype(np.float32)
    if kind == 'f16':
        return a.view(np.float16)[::max(1, bpe // 2)].astype(np.float32)
    if kind == 'u8x4':
        return a[0::4].astype(np.float32)
    if kind == 'u10x3':
        return (a.view(np.uint32) & 0x3ff).astype(np.float32)
    if kind in ('r10g11b11f', 'r11g11b10f'):
        return (a.view(np.uint32) & 0x7ff).astype(np.float32)
    if bpe == 2:
        return a.view(np.uint16).astype(np.float32)
    if bpe >= 4:
        return a.view(np.uint32)[::bpe // 4].astype(np.float32)
    return a.astype(np.float32)


def picture(d, inc):
    surf = {int(r['id']): r for r in tsv(os.path.join(d, 'surf.tsv'))}
    r = next(x for x in tsv(os.path.join(d, 'inc.tsv')) if int(x['inc']) == inc)
    s = surf[int(r['surf'])]
    bpe, w, h, tx = int(s['bpe']), int(s['w']), int(s['h']), int(s['tx'])
    if not (bpe and int(s['tiled'])):
        return None, s, r
    bw, bh = block_dims(bpe)
    ty = int(s['ty'])
    img = np.full((ty * bh, tx * bw), np.nan, dtype=np.float32)
    yy, xx = np.mgrid[0:bh, 0:bw].astype(np.uint32)
    idx = (rt_offset(xx, yy, bpe) // bpe).astype(np.int64)
    with open(os.path.join(d, 'tiles.bin'), 'rb') as f:
        for t in tsv(os.path.join(d, 'tiles.tsv')):
            if int(t['inc']) != inc or int(t['file_off']) < 0 or int(t['len']) != 65536:
                continue
            f.seek(int(t['file_off']))
            v = decode(f.read(65536), s['kind'], bpe)
            if v.size < bw * bh:
                continue
            k = int(t['off']) // 65536
            by, bx = k // tx, k % tx
            if by >= ty:
                continue
            img[by * bh:(by + 1) * bh, bx * bw:(bx + 1) * bw] = v[idx]
    return img[:h, :w], s, r


def to_png(img, out, size=None):
    from PIL import Image
    v = img[np.isfinite(img)]
    lo, hi = (np.percentile(v, 1), np.percentile(v, 99)) if v.size else (0, 1)
    if hi <= lo:
        hi = lo + 1
    g = np.clip((np.nan_to_num(img, nan=lo) - lo) / (hi - lo), 0, 1)
    g[~np.isfinite(img)] = 0.15
    im = Image.fromarray((g * 255).astype(np.uint8))
    if size:
        im = im.resize(size)
    im.save(out)


def main(a):
    d = a[0]
    if a[1] == '--surface':
        from PIL import Image, ImageDraw
        base, out = a[2], a[3]
        surf = {int(r['id']): r for r in tsv(os.path.join(d, 'surf.tsv'))}
        incs = [r for r in tsv(os.path.join(d, 'inc.tsv')) if r['placed'] == '1' and surf[int(r['surf'])]['base'] == base]
        cells = []
        for r in incs:
            img, s, _ = picture(d, int(r['inc']))
            if img is not None:
                p = out + '.tmp.png'
                to_png(img, p, (384, 216))
                cells.append((Image.open(p).convert('RGB'), 'p%s %s %s' % (r['piece'], s['role'], s['fmt'])))
        m = Image.new('RGB', (384 * min(4, len(cells)), 216 * ((len(cells) + 3) // 4)))
        dr = ImageDraw.Draw(m)
        for i, (c, t) in enumerate(cells):
            m.paste(c, ((i % 4) * 384, (i // 4) * 216))
            dr.text(((i % 4) * 384 + 3, (i // 4) * 216 + 3), t, fill=(255, 255, 0))
        m.save(out)
        os.remove(out + '.tmp.png') if os.path.exists(out + '.tmp.png') else None
        print(out, len(cells))
        return
    img, s, r = picture(d, int(a[1]))
    out = a[2] if len(a) > 2 else os.path.join(d, 'inc%s.png' % a[1])
    to_png(img, out)
    print(out, s['base'], s['role'], s['kind'], s['w'], s['h'])


if __name__ == '__main__':
    main(sys.argv[1:])
