#!/usr/bin/env python3
# Experiment 0157: the raw packets of dumped graphics buffers (ib-<n>-dcb-<dwords>.bin): per buffer, the
# draws (DRAW_INDEX_OFFSET_2 0x35 and others) with the blend state as the packets set it before each
# draw: CB_BLEND0_CONTROL (ctx 0x1e0) and CB_COLOR_CONTROL (0x202) through SET_CONTEXT_REG (0x69),
# SET_CONTEXT_REG_INDEX (0x6a), LOAD_CONTEXT_REG(_INDEX) (0x61/0x9f: counted, not read), and WRITE_DATA
# with DST_SEL 0 (register, mm address in dword 2; dropped by the host): every register target it names
# is listed. Also the type-1 packets and the packet-type histogram, to compare two buffers.
# Usage: ibstate.py <ib.bin> [<ib.bin> ...] | ibstate.py --summary <dir>
import sys, struct, glob, os, collections
NAMES = {0x10: "NOP", 0x11: "SET_BASE", 0x12: "CLEAR_STATE", 0x13: "INDEX_BUFFER_SIZE", 0x15: "DISPATCH_DIRECT", 0x16: "DISPATCH_INDIRECT", 0x24: "DRAW_INDIRECT", 0x26: "INDEX_BASE",
         0x28: "CONTEXT_CONTROL", 0x2a: "INDEX_TYPE", 0x2d: "DRAW_INDEX_2", 0x2f: "NUM_INSTANCES", 0x35: "DRAW_INDEX_OFFSET_2", 0x37: "WRITE_DATA", 0x3c: "WAIT_REG_MEM", 0x3f: "INDIRECT_BUFFER",
         0x40: "COPY_DATA", 0x42: "PFP_SYNC_ME", 0x43: "SURFACE_SYNC", 0x46: "EVENT_WRITE", 0x47: "EVENT_WRITE_EOP", 0x49: "RELEASE_MEM", 0x50: "DMA_DATA", 0x58: "ACQUIRE_MEM", 0x5e: "LOAD_UCONFIG_REG",
         0x5f: "LOAD_SH_REG", 0x61: "LOAD_CONTEXT_REG", 0x63: "LOAD_SH_REG_INDEX", 0x64: "LOAD_UCONFIG_REG_INDEX", 0x68: "SET_CONFIG_REG", 0x69: "SET_CONTEXT_REG", 0x6a: "SET_CONTEXT_REG_INDEX",
         0x76: "SET_SH_REG", 0x79: "SET_UCONFIG_REG", 0x7a: "SET_UCONFIG_REG_INDEX", 0x93: "WAIT_REG_MEM64", 0x9b: "SET_SH_REG_INDEX", 0x9f: "LOAD_CONTEXT_REG_INDEX", 0x2c: "DRAW_INDIRECT_MULTI"}
WATCH = {0x1e0: "CB_BLEND0_CONTROL", 0x202: "CB_COLOR_CONTROL", 0x8e: "CB_TARGET_MASK", 0x8f: "CB_SHADER_MASK", 0x1c5: "SPI_SHADER_COL_FORMAT", 0x1d5: "SX_MRT0_BLEND_OPT", 0x31c: "CB_COLOR0_INFO", 0x0: "DB_RENDER_CONTROL", 0x3: "DB_DEPTH_CONTROL?", 0x200: "DB_DEPTH_CONTROL", 0x10c: "DB_STENCILREFMASK"}


def packets(ib):
    i = 0
    while i < len(ib):
        h = ib[i]; t = h >> 30; c = (h >> 16) & 0x3fff
        n = 1 if t not in (0, 3) or c == 0x3fff else c + 2
        if i + n > len(ib): break
        yield i, t, (h >> 8) & 0xff if t == 3 else -1, ib[i:i + n]
        i += n


def analyse(path, verbose=True):
    b = open(path, "rb").read(); ib = struct.unpack("<%dI" % (len(b) // 4), b[:len(b) // 4 * 4])
    hist = collections.Counter(); wd_regs = collections.Counter(); draws = []; type1 = 0; loads = 0; loadlist = []
    st = {}; last_set = {}
    for i, t, op, p in packets(ib):
        if t == 1: type1 += 1; continue
        if t == 0: hist["type0"] += 1; continue
        if t != 3: continue
        hist[NAMES.get(op, hex(op))] += 1
        if op in (0x69, 0x6a) and len(p) >= 3:
            off = p[1] & 0xffff
            for k in range(len(p) - 2):
                st[off + k] = p[2 + k]; last_set[off + k] = i
        elif op == 0x37 and len(p) >= 4 and ((p[1] >> 8) & 0xf) == 0:
            mm = p[2]
            for k in range(len(p) - 3): wd_regs[hex(mm + k)] += 1
            # a register write the host drops: note it as a 'shadow' change if it hits a watched context register
            for k in range(len(p) - 3):
                ctx = mm + k - 0xa000
                if ctx in WATCH: st[("wd", ctx)] = (p[3 + k], i)
        elif op in (0x61, 0x9f, 0x5f, 0x63, 0x5e, 0x64):
            loads += 1
            base = (p[1] & ~3) | ((p[2] & 0xffff) << 32)
            if op in (0x61, 0x5f, 0x5e):
                for k in range(3, len(p) - 1, 2):
                    off, n = p[k] & 0xffff, p[k + 1] & 0x3fff
                    loadlist.append((i, NAMES[op], "%010x" % (base + off * 4), off, n, op == 0x61 and off <= 0x1e0 < off + n))
            else:
                pairs = (p[3] >> 31) != 0; n = p[4] & 0x3fff; off = p[3] & 0xffff
                loadlist.append((i, NAMES[op], "%010x" % base, "pairs" if pairs else off, n, (op == 0x9f and not pairs and off <= 0x1e0 < off + n) or (op == 0x9f and pairs)))
        elif op in (0x35, 0x2d, 0x24, 0x2c, 0x15, 0x16):
            draws.append((i, op, tuple(p[1:4]), st.get(0x1e0), st.get(0x202), st.get(0x8e), st.get(0x1d5), dict((k, v) for k, v in st.items() if isinstance(k, tuple))))
    analyse.loadlist = loadlist
    return ib, hist, wd_regs, draws, type1, loads


if sys.argv[1] == "--summary":
    fs = sorted(glob.glob(os.path.join(sys.argv[2], "ib-*-dcb-*.bin")))
    print("%d buffers" % len(fs))
    sig = collections.Counter()
    for f in fs:
        ib, hist, wd, draws, t1, loads = analyse(f, False)
        n35 = sum(1 for d in draws if d[1] == 0x35)
        blend_seq = tuple("%08x" % (d[3] or 0) for d in draws if d[1] == 0x35)
        key = (len(ib), n35, hist.get("WRITE_DATA", 0), len(wd), t1, loads, len(set(blend_seq)))
        sig[key] += 1
        print("%s: %5d dwords, %2d draws(0x35), WRITE_DATA %3d (reg targets %2d: %s), type1 %d, LOAD_* %d, blend values %s" % (os.path.basename(f), len(ib), n35, hist.get("WRITE_DATA", 0), len(wd), " ".join(sorted(wd)[:6]), t1, loads, sorted(set(blend_seq))))
    sys.exit(0)
for f in sys.argv[1:]:
    ib, hist, wd, draws, t1, loads = analyse(f)
    print("== %s: %d dwords; type1 %d; LOAD_* %d; packets: %s" % (os.path.basename(f), len(ib), t1, loads, dict(hist.most_common(14))))
    print("   WRITE_DATA register targets: %s" % dict(wd.most_common(10)))
    ll = analyse.loadlist
    print("   LOAD_* packets: %d; context ones that may cover CB_BLEND0_CONTROL (ctx 0x1e0) or are pair tables: %s" % (len(ll), [(i, n, a, o, c) for i, n, a, o, c, hit in ll if hit][:12]))
    print("   LOAD_* list (first 20): %s" % [(i, n[-9:], a[-6:], o, c) for i, n, a, o, c, hit in ll[:20]])
    for i, op, pk, bl, cc, mask, mrt0, wds in draws:
        print("   at %5d %-20s %s | blend0 %s cc %s mask %s mrt0opt %s %s" % (i, NAMES.get(op, hex(op)), " ".join("%08x" % x for x in pk), "%08x" % bl if bl is not None else "-", "%08x" % cc if cc is not None else "-",
              "%08x" % mask if mask is not None else "-", "%08x" % mrt0 if mrt0 is not None else "-", ("WD:" + str(wds)) if wds else ""))
