#!/usr/bin/env python3
# BC5 experiment 0205: which parts of a streamed texture are resident. From a texture's image descriptor (format, size,
# levels, swizzle mode) it computes the gfx10 mip layout, then marks each 4-KiB / 64-KiB block of each mip as data,
# mapped-but-zero or hole, from either a pg0205.py tile map ("m" line) or a KYTY_BC5_AMM_TRACE play log, and prints
# one character per block, row by row (block rows top to bottom), per mip.
#
# Layout (Mesa src/amd/addrlib @ ab2374a, 2D thin surfaces, one slice):
# - block size: 4 KiB for ADDR_SW_4KB_* (mode 4-7), 64 KiB for ADDR_SW_64KB_* (8-11, 24-27)
#   (inc/addrtypes.h:231-254 for the mode numbers)
# - block dimensions in elements: n = log2(block bytes) - log2(element bytes); width 2^((n+1)/2), height 2^(n - that)
#   (core/addrlib2.cpp:1698-1709, ComputeThinBlockDimension, 1xAA)
# - mip tail: the first mip whose size fits (block width / 2) x (block height) with at most maxMipsInTail levels to
#   the end; maxMipsInTail = 1 + 2^(log2 block - 9) up to 2 KiB blocks, else log2 block - 4
#   (core/addrlib2.cpp:1798-1844 GetMipTailDim; gfx10/gfx10addrlib.cpp:2139-2152 GetMaxNumMipsInTail; gfx10addrlib.h:529-541)
# - order in memory: the tail block first (offset 0), then the mips from the smallest non-tail one up to mip 0
#   (gfx10/gfx10addrlib.cpp:3964-3989); each mip's pitch and height are aligned to the block dimensions
#   (gfx10addrlib.cpp:3941-3944)
# - blocks of a mip in row-major order: block index = (y / block height) * pitch in blocks + x / block width
#   (gfx10/gfx10addrlib.cpp:4795-4797, 4835-4844)
# Element size: BC1/BC4 8 bytes per 4x4 block; other formats bytes per texel (given with --bpe).
#
# usage: python3 -I res0205.py <base hex> <width> <height> <levels> <sw mode> <bpe bytes> <element w,h in texels>
#            (--tiles <pages.txt> [<sample index>] | --amm <play log> | --selftest)
#        e.g. BC4 2048x2048, 8 levels, 4KB_S:  res0205.py 8492504000 2048 2048 8 5 8 4,4 --amm play-pkg.log
import bisect, re, sys


def layout(width, height, levels, sw, bpe, ew, eh):
    blk = 4096 if 4 <= sw <= 7 or sw == 23 else 65536
    lb = blk.bit_length() - 1
    n = lb - (bpe.bit_length() - 1)
    bw = 1 << ((n + 1) // 2)
    bh = 1 << (n - (n + 1) // 2)
    tw, th = bw >> 1, bh
    maxtail = (1 + (1 << (lb - 9))) if lb <= 11 else lb - 4
    w0, h0 = -(-width // ew), -(-height // eh)  # mip 0 in elements
    mips, first_tail = [], levels
    for i in range(levels):
        w, h = max(1, w0 >> i), max(1, h0 >> i)
        if w <= tw and h <= th and levels - i <= maxtail:
            first_tail = i
            break
        p, q = -(-w // bw) * bw, -(-h // bh) * bh
        mips.append({"mip": i, "w": w, "h": h, "pitch": p, "height": q, "size": p * q * bpe})
    off = blk if first_tail < levels else 0
    for m in reversed(mips):
        m["offset"] = off
        off += m["size"]
    return {"block": blk, "bw": bw, "bh": bh, "mips": mips, "first_tail": first_tail, "size": off}


def blocks_state(L, base, state_at):
    out = []
    for m in L["mips"]:
        pb, rows = m["pitch"] // L["bw"], m["height"] // L["bh"]
        grid = []
        for yb in range(rows):
            grid.append("".join(state_at(base + m["offset"] + (yb * pb + xb) * L["block"]) for xb in range(pb)))
        out.append((m, grid))
    return out


def from_tiles(path, base, index):
    maps = [l.split() for l in open(path) if l.startswith("m ")]
    for _, mono, b, s in ([maps[int(index)]] if index is not None else []) or maps[::-1]:
        if int(b, 16) <= base < int(b, 16) + len(s) * 0x4000:
            rb = int(b, 16)
            ch = {"d": "#", "z": "z", ".": ".", "e": "e"}
            return lambda a: ch[s[(a - rb) // 0x4000]] if rb <= a < rb + len(s) * 0x4000 else "?"
    sys.exit("no tile map covers 0x%x" % base)


def from_amm(path):
    maps, reads = {}, []
    for n, line in enumerate(open(path, errors="replace")):
        if "amm trace:" not in line:
            continue
        if "map auto va" in line or "map direct va" in line:
            g = re.search(r"va 0x([0-9a-f]+) size 0x([0-9a-f]+)", line)
            maps[int(g[1], 16)] = (int(g[2], 16), n)
        elif "amm trace: unmap va" in line:
            g = re.search(r"va 0x([0-9a-f]+) size 0x([0-9a-f]+)", line)
            va, sz = int(g[1], 16), int(g[2], 16)
            for k in [k for k in maps if va <= k < va + sz]:
                maps.pop(k)
        elif "read file" in line or "read into the AMM window" in line:
            g = re.search(r"size 0x([0-9a-f]+) -> 0x([0-9a-f]+)", line)
            if g:
                reads.append((int(g[2], 16), int(g[1], 16), n))
    ms = sorted((va, sz, n) for va, (sz, n) in maps.items())
    starts = [m[0] for m in ms]
    reads.sort()
    rstarts = [r[0] for r in reads]

    def state(a):
        i = bisect.bisect_right(starts, a) - 1
        if i < 0 or a >= ms[i][0] + ms[i][1]:
            return "."
        n = ms[i][2]
        j = bisect.bisect_left(rstarts, a - (256 << 20))
        while j < len(reads) and reads[j][0] <= a:
            if a < reads[j][0] + reads[j][1] and reads[j][2] > n:
                return "#"
            j += 1
        return "z"
    return state


def selftest():
    # BC4 2048x2048, 8 levels, 4KB_S (exp 0201 X2's pixel-stage texture): elements 512x512 of 8 bytes, block 32x16
    # elements (128x64 texels); tail from mip 5 (16x16 elements fit 16x16, 3 levels to the end <= 8); mips 4..0 at
    # 4, 12, 44, 172, 684 KiB; total 684 KiB + 2 MiB.
    L = layout(2048, 2048, 8, 5, 8, 4, 4)
    assert (L["bw"], L["bh"], L["first_tail"]) == (32, 16, 5), L
    assert [m["offset"] >> 10 for m in L["mips"]] == [684, 172, 44, 12, 4], [m["offset"] for m in L["mips"]]
    assert L["size"] == (684 << 10) + (2 << 20)
    # R16F 512x512, 7 levels, 4KB_S: block 64x32 texels, tail from mip 4, mips 3..0 at 4, 12, 44, 172 KiB, end 684 KiB.
    L = layout(512, 512, 7, 5, 2, 1, 1)
    assert (L["bw"], L["bh"], L["first_tail"]) == (64, 32, 4), L
    assert [m["offset"] >> 10 for m in L["mips"]] == [172, 44, 12, 4] and L["size"] == 684 << 10
    # R16F 2048x2048, 1 level, 64KB_R_X: one mip of 8 MiB at offset 0 (no tail with a single level that does not fit).
    L = layout(2048, 2048, 1, 27, 2, 1, 1)
    assert L["first_tail"] == 1 and L["mips"][0]["offset"] == 0 and L["size"] == 8 << 20, L
    # The block walk: a fake state that is "#" only in mip 0's first block row.
    L = layout(2048, 2048, 8, 5, 8, 4, 4)
    m0 = L["mips"][0]
    row = m0["pitch"] // L["bw"] * L["block"]
    g = blocks_state(L, 0, lambda a: "#" if m0["offset"] <= a < m0["offset"] + row else ".")
    assert g[0][1][0] == "#" * 16 and set(g[0][1][1]) == {"."} and len(g[0][1]) == 32
    print("selftest ok")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
        sys.exit(0)
    base = int(sys.argv[1], 16)
    w, h, lv, sw, bpe = (int(x) for x in sys.argv[2:7])
    ew, eh = (int(x) for x in sys.argv[7].split(","))
    L = layout(w, h, lv, sw, bpe, ew, eh)
    if sys.argv[8] == "--tiles":
        st = from_tiles(sys.argv[9], base, sys.argv[10] if len(sys.argv) > 10 else None)
    else:
        st = from_amm(sys.argv[9])
    print("texture 0x%x %dx%d %d levels sw %d: block %d B = %dx%d elements, tail from mip %d, %d bytes" % (
        base, w, h, lv, sw, L["block"], L["bw"], L["bh"], L["first_tail"], L["size"]))
    for m, grid in blocks_state(L, base, st):
        flat = "".join(grid)
        print("mip %d (%dx%d elements) at +0x%x: %d of %d blocks with data, %d mapped zero" % (
            m["mip"], m["w"], m["h"], m["offset"], flat.count("#"), len(flat), flat.count("z")))
        for r in grid:
            print("  " + r)
