#!/usr/bin/env python3
# BC5 exp 0381: walk a TITLE IB dumped by the host's timeout probe (ib-timeout-*.bin, little-endian dwords before the
# host's filter) and print every draw and dispatch with the graphics/compute state the IB itself sets before it.
# Structure and register values only (packet offsets, opcodes, register names and values, counts); no other payload.
# State loaded from memory (LOAD_*_REG_INDEX) is not visible here and is marked as such.
# Register offsets from tools/bc5-agc/regdb/gfx10.json (Mesa, MIT), opcodes from regdb/pm4-opcodes.tsv.
# usage: python3 walk0381.py <ib-timeout-...-N.bin> [tail]   (tail: also print the packet list of the last 400 dwords)
import struct
import sys

OPS = {0x10: "NOP", 0x11: "SET_BASE", 0x13: "INDEX_BUFFER_SIZE", 0x15: "DISPATCH_DIRECT", 0x16: "DISPATCH_INDIRECT",
       0x22: "COND_EXEC", 0x24: "DRAW_INDIRECT", 0x25: "DRAW_INDEX_INDIRECT", 0x26: "INDEX_BASE", 0x27: "DRAW_INDEX_2",
       0x28: "CONTEXT_CONTROL", 0x2c: "DRAW_INDIRECT_MULTI", 0x2d: "DRAW_INDEX_AUTO", 0x2e: "DRAW_INDEX_IMMD",
       0x2f: "NUM_INSTANCES", 0x30: "DRAW_INDEX_MULTI_AUTO", 0x34: "STRMOUT_BUFFER_UPDATE", 0x35: "DRAW_INDEX_OFFSET_2",
       0x37: "WRITE_DATA", 0x38: "DRAW_INDEX_INDIRECT_MULTI", 0x3c: "WAIT_REG_MEM", 0x3f: "INDIRECT_BUFFER",
       0x40: "COPY_DATA", 0x42: "PFP_SYNC_ME", 0x45: "COND_WRITE", 0x46: "EVENT_WRITE", 0x49: "RELEASE_MEM",
       0x50: "DMA_DATA", 0x58: "ACQUIRE_MEM", 0x5e: "LOAD_UCONFIG_REG", 0x5f: "LOAD_SH_REG", 0x61: "LOAD_CONTEXT_REG",
       0x63: "LOAD_SH_REG_INDEX", 0x64: "LOAD_UCONFIG_REG_INDEX", 0x69: "SET_CONTEXT_REG", 0x12: "CLEAR_STATE",
       0x76: "SET_SH_REG", 0x79: "SET_UCONFIG_REG", 0x7a: "SET_UCONFIG_REG_INDEX", 0x93: "WAIT_REG_MEM64",
       0x9b: "SET_SH_REG_INDEX", 0x9f: "LOAD_CONTEXT_REG_INDEX"}
DRAWS = {0x24, 0x25, 0x27, 0x2c, 0x2d, 0x2e, 0x30, 0x35, 0x38}
DISPATCH = {0x15, 0x16}
CTX = {0x2d5: "VGT_SHADER_STAGES_EN", 0x2d6: "VGT_LS_HS_CONFIG", 0x2db: "VGT_TF_PARAM", 0x290: "VGT_GS_MODE",
       0x291: "VGT_GS_ONCHIP_CNTL", 0x29b: "VGT_GS_OUT_PRIM_TYPE", 0x2a6: "VGT_DRAW_PAYLOAD_CNTL",
       0x2e5: "VGT_STRMOUT_CONFIG", 0x2e6: "VGT_STRMOUT_BUFFER_CONFIG", 0x1ff: "GE_MAX_OUTPUT_PER_SUBGROUP"}
SH = {0x8: "PGM_LO_PS", 0x9: "PGM_HI_PS", 0x48: "PGM_LO_VS", 0x49: "PGM_HI_VS", 0x88: "PGM_LO_GS", 0x89: "PGM_HI_GS",
      0xc8: "PGM_LO_ES", 0x108: "PGM_LO_HS", 0x109: "PGM_HI_HS", 0x148: "PGM_LO_LS",
      0x204: "COMPUTE_START_X", 0x205: "COMPUTE_START_Y", 0x206: "COMPUTE_START_Z", 0x20c: "COMPUTE_PGM_LO",
      0x20d: "COMPUTE_PGM_HI"}
for i in range(16):
    SH[0x240 + i] = "CUD%d" % i
UC = {0x242: "VGT_PRIMITIVE_TYPE", 0x243: "VGT_INDEX_TYPE", 0x24d: "VGT_NUM_INSTANCES", 0x24e: "VGT_TF_RING_SIZE",
      0x24f: "VGT_HS_OFFCHIP_PARAM", 0x250: "VGT_TF_MEMORY_BASE", 0x25b: "GE_CNTL", 0x261: "VGT_TF_MEMORY_BASE_HI",
      0x240: "VGT_ESGS_RING_SIZE", 0x241: "VGT_GSVS_RING_SIZE"}

data = open(sys.argv[1], "rb").read()
ib = list(struct.unpack("<%dI" % (len(data) // 4), data[: len(data) // 4 * 4]))
tail = len(sys.argv) > 2 and sys.argv[2] == "tail"
st = {}
loads = []
counts = {}
rows = []
i = 0
while i < len(ib):
    h = ib[i]
    t = h >> 30
    ln = 1
    if t in (0, 3):
        c = (h >> 16) & 0x3fff
        ln = 1 if c == 0x3fff else c + 2
    op = (h >> 8) & 0xff
    pk = ib[i:i + ln]
    if t == 3:
        counts[op] = counts.get(op, 0) + 1
        if op in (0x69, 0x76, 0x79, 0x7a, 0x9b) and ln >= 3:
            base = pk[1] & 0xffff
            names = {0x69: CTX, 0x76: SH, 0x9b: SH, 0x79: UC, 0x7a: UC}[op]
            for k, v in enumerate(pk[2:]):
                if base + k in names:
                    st[names[base + k]] = v
        elif op == 0x2f and ln >= 2:
            st["NUM_INSTANCES(pkt)"] = pk[1]
        elif op in (0x63, 0x9f, 0x64, 0x5e, 0x5f, 0x61) and ln >= 5:
            loads.append(i)
            st["last_load"] = "%s@%d" % (OPS.get(op, hex(op)), i)
        elif op == 0x26 and ln >= 3:
            st["INDEX_BASE"] = (pk[1] & ~1) | ((pk[2] & 0xffff) << 32)
        elif op == 0x13 and ln >= 2:
            st["INDEX_BUFFER_SIZE"] = pk[1]
        elif op == 0x11 and ln >= 4:
            st["SET_BASE%d" % (pk[1] & 0xf)] = (pk[2] & ~3) | ((pk[3] & 0xffff) << 32)
        if op in DRAWS or op in DISPATCH or op in (0x34, 0x46, 0x49, 0x50) or (tail and i >= len(ib) - 400):
            f = ""
            if op == 0x27 and ln >= 5:
                f = "max_size %d addr 0x%x count %d" % (pk[1], pk[2] | ((pk[3] & 0xffff) << 32), pk[4])
            elif op == 0x2d and ln >= 3:
                f = "count %d init 0x%x" % (pk[1], pk[2])
            elif op == 0x35 and ln >= 4:
                f = "max_size %d offset %d count %d" % (pk[1], pk[2], pk[3])
            elif op in (0x24, 0x25) and ln >= 4:
                f = "data_offset 0x%x" % pk[1]
            elif op in (0x2c, 0x38) and ln >= 6:
                f = "data_offset 0x%x count %d (indirect count %s) stride %d" % (pk[1], pk[4], "on" if pk[3] >> 30 & 1 else "off", pk[6] if ln > 6 else -1)
            elif op == 0x15 and ln >= 5:
                f = "dims %d %d %d init 0x%x" % (pk[1], pk[2], pk[3], pk[4])
            elif op == 0x16 and ln >= 3:
                f = "offset 0x%x init 0x%x" % (pk[1], pk[2])
            elif op in (0x46, 0x49) and ln >= 2:
                f = "event %d" % (pk[1] & 0x3f)
            elif op == 0x50 and ln >= 7:
                f = "ctl 0x%x src 0x%x dst 0x%x n 0x%x" % (pk[1], pk[2] | (pk[3] << 32), pk[4] | (pk[5] << 32), pk[6] & 0x1fffff)
            elif op == 0x34 and ln >= 2:
                f = "ctl 0x%x" % pk[1]
            row = "%6d %-26s %s" % (i, OPS.get(op, "op 0x%02x" % op), f)
            if op in DRAWS:
                keys = ("VGT_SHADER_STAGES_EN", "VGT_PRIMITIVE_TYPE", "VGT_TF_PARAM", "VGT_GS_MODE", "VGT_STRMOUT_CONFIG",
                        "PGM_LO_HS", "PGM_LO_GS", "PGM_LO_ES", "PGM_LO_LS", "PGM_LO_VS", "PGM_LO_PS", "VGT_NUM_INSTANCES",
                        "NUM_INSTANCES(pkt)", "INDEX_BASE", "INDEX_BUFFER_SIZE", "SET_BASE1", "last_load")
                row += " | " + " ".join("%s=%s" % (k, hex(st[k]) if isinstance(st[k], int) else st[k]) for k in keys if k in st)
            if op in DISPATCH:
                keys = ["COMPUTE_PGM_LO", "COMPUTE_PGM_HI", "COMPUTE_START_X", "COMPUTE_START_Y", "COMPUTE_START_Z", "SET_BASE1",
                        "last_load"] + ["CUD%d" % k for k in range(16)]
                row += " | " + " ".join("%s=%s" % (k, hex(st[k]) if isinstance(st[k], int) else st[k]) for k in keys if k in st)
            rows.append(row)
    i += ln

print("%s: %d dwords; packets by opcode: %s" % (sys.argv[1].split("/")[-1], len(ib),
      " ".join("%s:%d" % (OPS.get(k, "0x%02x" % k), v) for k, v in sorted(counts.items(), key=lambda x: -x[1]))))
print("LOAD_*_REG(_INDEX) packets (state from memory, not visible here): %d" % len(loads))
print("UCONFIG state at the end: " + " ".join("%s=0x%x" % (v, st[v]) for v in UC.values() if v in st))
for r in rows:
    print(r)
