#!/usr/bin/env python3
"""BC5 exp 0418: do the titles' shaders ask for a trap handler? Read-only, on the box, numbers only.

On the console the system installs the title's trap handler (exp 0418 result 2: 0x80888123 names its code and data);
under amdgpu's graphics VMIDs there is none (gfx_v10_0.c:5175-5192 enables traps for the KFD's VMIDs only). This counts,
in the captured command buffers (exp 0401's static audit's set: ibdump-*/ib-*.bin and play-*/gc/ib-timeout-*.bin under
~/bc5-data/captures), every SET_SH_REG that writes a shader's RSRC2 and how many of those values have TRAP_PRESENT
(bit 6) or any EXCP_EN bit set, per stage. Register offsets and masks: Linux v7.2 gc_10_1_0_offset.h /
gc_10_1_0_sh_mask.h (SH offset = mm + 0x1260 - 0x2c00 for BASE_IDX 0). LOAD_SH_REG(_INDEX) ranges that cover an RSRC2
are counted too: their values are in memory and not read here.
usage (on the box): cd ~/bc5-data/captures && python3 -I <kit>/trap0418.py
"""
import collections
import glob
import struct
import sys

# stage: (SH offset, EXCP_EN mask)
RSRC2 = {
    "PS": (0x00B, 0x01FF0000),
    "VS": (0x04B, 0x003FE000),
    "GS": (0x08B, 0x0000FF80),
    "ES": (0x0CB, 0x0001FF00),
    "HS": (0x10B, 0x0003FE00),
    "LS": (0x14B, 0x01FF0000),
    "CS": (0x213, 0x7F006000),  # COMPUTE_PGM_RSRC2: EXCP_EN 24-30 and EXCP_EN_MSB 13-14
}
TRAP_PRESENT = 0x40
BY_OFF = {off: (st, m) for st, (off, m) in RSRC2.items()}
SET_SH = (0x76, 0x77)          # SET_SH_REG, SET_SH_REG_INDEX
LOAD_SH = (0x5F, 0x63)         # LOAD_SH_REG, LOAD_SH_REG_INDEX


def walk(w):
    i, n = 0, len(w)
    while i < n:
        h = w[i]
        t = h >> 30
        if t == 3:
            if h == 0xFFFF1000:
                i += 1
                continue
            c = (h >> 16) & 0x3FFF
            yield (h >> 8) & 0xFF, w[i + 1:i + 2 + c]
            i += c + 2
        elif t == 2 or h == 0:
            i += 1
        else:
            return


def main():
    files = glob.glob("ibdump-*/ib-*.bin") + glob.glob("play-*/gc/ib-timeout-*.bin")
    files = [f for f in files if not f.endswith(".tfring.bin")]
    if not files:
        print("trap0418: no captured buffers here (run it from ~/bc5-data/captures)")
        return 1
    sets = collections.Counter()
    trap = collections.Counter()
    excp = collections.Counter()
    values = collections.defaultdict(collections.Counter)
    loads = collections.Counter()
    bad = 0
    for f in sorted(files):
        try:
            b = open(f, "rb").read()
        except OSError:
            bad += 1
            continue
        w = struct.unpack("<%dI" % (len(b) // 4), b[: len(b) // 4 * 4])
        for op, body in walk(w):
            if op in SET_SH and len(body) >= 2:
                base = body[0] & 0xFFFF
                for k, v in enumerate(body[1:]):
                    hit = BY_OFF.get(base + k)
                    if hit is None:
                        continue
                    st, m = hit
                    sets[st] += 1
                    values[st][v & (TRAP_PRESENT | m)] += 1
                    if v & TRAP_PRESENT:
                        trap[st] += 1
                    if v & m:
                        excp[st] += 1
            elif op in LOAD_SH and len(body) >= 3:
                # LOAD_SH_REG: addr lo, addr hi, then (offset, count) pairs; _INDEX: index/addr, then offset, count
                pairs = body[2:]
                for j in range(0, len(pairs) - 1, 2):
                    lo, cnt = pairs[j] & 0xFFFF, pairs[j + 1] & 0x3FFF
                    for o, (st, _) in BY_OFF.items():
                        if lo <= o < lo + cnt:
                            loads[st] += 1
    print(f"trap0418: {len(files)} buffers ({bad} unreadable)")
    for st in RSRC2:
        tv = ", ".join(f"0x{k:08x}x{n}" for k, n in values[st].most_common(4))
        print(f"  {st}: RSRC2 sets {sets[st]}, TRAP_PRESENT {trap[st]}, EXCP_EN {excp[st]}; loads covering it {loads[st]}; trap/excp bits seen: {tv or '-'}")
    total = sum(trap.values()) + sum(excp.values())
    print("trap0418: " + ("NO set RSRC2 asks for a trap handler or an exception" if total == 0 else f"{total} set RSRC2 values ask for a trap handler or an exception"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
