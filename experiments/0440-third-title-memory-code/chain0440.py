#!/usr/bin/env python3
"""Experiment 0440: the dumped frame's chain as one flat buffer, and its render-target state (private output).

  chain0440.py flat <dump> <head> <dwords> <out.bin> [first-segment]
        the chained segments laid out one after another without their chain packets (as a host that follows
        the chain iteratively would run them), for an offline check with tools/bc5-agc
  chain0440.py ctx <dump> <head> <dwords>
        context registers as the chain sets them (LOAD_CONTEXT_REG_INDEX pair tables read from the dump,
        SET_CONTEXT_REG packets), and at every draw: CB_COLOR_CONTROL's mode, the colour targets with their
        base, DCC enable and DCC_CONTROL, DB_RENDER_CONTROL and the depth target.

Register addresses: Mesa src/amd/registers/gfx10.json (commit 0866ae7085c1; read on the box 2026-11-21):
DB_RENDER_CONTROL 0x28000, CB_TARGET_MASK 0x28238, CB_COLOR_CONTROL 0x28808, CB_COLOR0_BASE 0x28C60,
CB_COLOR0_INFO 0x28C70, CB_COLOR0_DCC_CONTROL 0x28C78, CB_COLOR0_DCC_BASE 0x28C94, CB_COLOR1_INFO 0x28CAC (so
0x3C per target). Context offsets below are (address - 0x28000) / 4.
TODO(verify): the field positions used here (CB_COLOR_CONTROL MODE in bits 6:4 with the mode names below,
CB_COLORn_INFO DCC_ENABLE in bit 28) are from memory of Mesa's sid.h, not read from the file.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ana0440 import Mem  # noqa: E402

DB_RENDER_CONTROL, CB_COLOR_CONTROL, CB_TARGET_MASK = 0x000, 0x202, 0x08E
CB0_BASE, CB0_INFO, CB0_DCC_CONTROL, CB0_DCC_BASE, CB_STEP = 0x318, 0x31C, 0x31E, 0x325, 15
CB_MODES = {0: "DISABLE", 1: "NORMAL", 2: "ELIMINATE_FAST_CLEAR", 3: "RESOLVE", 4: "DECOMPRESS", 5: "FMASK_DECOMPRESS",
            6: "DCC_DECOMPRESS"}


def segments(mem, head, ndw):
    seg, addr, n, seen = 0, head, ndw, set()
    while addr not in seen:
        seen.add(addr)
        d = mem.read(addr, n * 4)
        if not d or len(d) < n * 4:
            return
        dw = struct.unpack("<%dI" % n, d)
        nxt, cut = None, n
        i = 0
        while i < n:
            h = dw[i]
            if h >> 30 != 3 or h == 0xFFFF1000:
                i += 1
                continue
            cnt = ((h >> 16) & 0x3FFF) + 1
            if (h >> 8) & 0xFF == 0x3F and cnt >= 3 and (dw[i + 3] >> 20) & 1:
                nxt, cut = (dw[i + 1] | ((dw[i + 2] & 0xFFFF) << 32), dw[i + 3] & 0xFFFFF), i
                break
            i += 1 + cnt
        yield seg, addr, dw[:cut]
        if nxt is None:
            return
        seg += 1
        addr, n = nxt


def packets(dw):
    i = 0
    while i < len(dw):
        h = dw[i]
        if h >> 30 != 3 or h == 0xFFFF1000:
            i += 1
            continue
        cnt = ((h >> 16) & 0x3FFF) + 1
        yield i, (h >> 8) & 0xFF, dw[i + 1:i + 1 + cnt]
        i += 1 + cnt


def main():
    cmd, dump, head, ndw = sys.argv[1], sys.argv[2], int(sys.argv[3], 0), int(sys.argv[4], 0)
    mem = Mem(dump)
    if cmd == "flat":
        first = int(sys.argv[6]) if len(sys.argv) > 6 else 0
        total = 0
        with open(sys.argv[5], "wb") as f:
            for seg, addr, dw in segments(mem, head, ndw):
                if seg >= first:
                    f.write(struct.pack("<%dI" % len(dw), *dw))
                    total += len(dw)
        print("%d dwords written" % total)
        return
    ctx = {}
    draws = []
    tables = unread = pairs_n = 0
    offs = {}
    for seg, addr, dw in segments(mem, head, ndw):
        for i, op, b in packets(dw):
            if op == 0x9F and len(b) >= 4:  # LOAD_CONTEXT_REG_INDEX: address lo, hi, format, count
                a, n = (b[0] & ~3) | (b[1] << 32), b[3] & 0x3FFF
                tables += 1
                if not b[2] & 0x80000000:
                    unread += 1
                    continue
                d = mem.read(a, n * 8)
                if not d or len(d) < n * 8:
                    unread += 1
                    continue
                for k in range(n):
                    o, v = struct.unpack_from("<II", d, k * 8)
                    ctx[o & 0xFFFF] = v
                    offs[o & 0xFFFF] = offs.get(o & 0xFFFF, 0) + 1
                    pairs_n += 1
            elif op == 0x69 and len(b) >= 2:  # SET_CONTEXT_REG: offset, values
                for k, v in enumerate(b[1:]):
                    ctx[(b[0] & 0xFFFF) + k] = v
            elif op in (0x2D, 0x27, 0x35):
                draws.append((seg, addr + 4 * i, dict(ctx)))
    print("LOAD_CONTEXT_REG_INDEX tables %d (not readable as pairs: %d), %d pairs; distinct offsets %d" % (tables, unread, pairs_n, len(offs)))
    print("offsets seen for the registers read here: " + ", ".join("%#x x%d" % (o, offs.get(o, 0)) for o in (DB_RENDER_CONTROL, CB_COLOR_CONTROL, CB_TARGET_MASK, CB0_BASE, CB0_INFO, CB0_DCC_CONTROL, CB0_DCC_BASE)))
    modes, dbrc, targets = {}, {}, {}
    for seg, pa, c in draws:
        m = (c.get(CB_COLOR_CONTROL, 0) >> 4) & 7 if CB_COLOR_CONTROL in c else -1
        modes[m] = modes.get(m, 0) + 1
        dbrc[c.get(DB_RENDER_CONTROL, -1)] = dbrc.get(c.get(DB_RENDER_CONTROL, -1), 0) + 1
        mask = c.get(CB_TARGET_MASK, 0)
        for t in range(8):
            if (mask >> (4 * t)) & 0xF and (CB0_BASE + CB_STEP * t) in c:
                key = (t, c[CB0_BASE + CB_STEP * t], c.get(CB0_INFO + CB_STEP * t, 0), c.get(CB0_DCC_CONTROL + CB_STEP * t, 0),
                       c.get(CB0_DCC_BASE + CB_STEP * t, 0))
                targets.setdefault(key, []).append(seg)
    print("draws: %d" % len(draws))
    print("CB_COLOR_CONTROL mode at the draws: " + ", ".join("%s x%d" % (CB_MODES.get(m, "not set" if m < 0 else str(m)), n) for m, n in sorted(modes.items())))
    print("DB_RENDER_CONTROL at the draws: " + ", ".join("%s x%d" % ("not set" if v < 0 else "%#x" % v, n) for v, n in sorted(dbrc.items())))
    print("colour targets written by draws (slot, base << 8, DCC enable, DCC_CONTROL, DCC base << 8, segments):")
    for (t, base, info, dccc, dccb), segs in sorted(targets.items(), key=lambda x: x[1][0]):
        print("  MRT%d base %#x info %#010x DCC %s control %#x dcc_base %#x  draws %d in segments %s" % (
            t, base << 8, info, "ON" if info >> 28 & 1 else "off", dccc, dccb << 8, len(segs), sorted(set(segs))))


if __name__ == "__main__":
    main()
