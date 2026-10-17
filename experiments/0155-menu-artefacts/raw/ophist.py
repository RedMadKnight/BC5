#!/usr/bin/env python3
# Experiment 0155: per buffer kind, the type-3 opcode histogram of dumped buffers; the registers
# that WRITE_DATA with DST_SEL 0 (register) targets; and the packet sequence of one buffer of a
# given size around a dword position.
import glob, struct, sys, collections, os
d = sys.argv[1]; want_size = int(sys.argv[2]) if len(sys.argv) > 2 else 0; around = int(sys.argv[3]) if len(sys.argv) > 3 else 0
ops = collections.Counter(); wd0 = collections.Counter(); shown = False
NAMES = {0x10:"NOP",0x11:"SET_BASE",0x13:"INDEX_BUFFER_SIZE",0x15:"DISPATCH_DIRECT",0x16:"DISPATCH_INDIRECT",0x1e:"ATOMIC_MEM",0x22:"COND_EXEC",0x23:"PRED_EXEC",0x24:"DRAW_INDIRECT",0x25:"DRAW_INDEX_INDIRECT",0x26:"INDEX_BASE",0x27:"DRAW_INDEX_2?",0x28:"CONTEXT_CONTROL",0x2a:"INDEX_TYPE",0x2c:"DRAW_INDEX_AUTO",0x2d:"DRAW_INDEX_2",0x2f:"NUM_INSTANCES",0x33:"INDIRECT_BUFFER_CNST",0x35:"DRAW_INDEX_OFFSET_2",0x37:"WRITE_DATA",0x38:"DRAW_INDIRECT_MULTI",0x3c:"WAIT_REG_MEM",0x3f:"INDIRECT_BUFFER",0x40:"COPY_DATA",0x42:"PFP_SYNC_ME",0x43:"SURFACE_SYNC",0x46:"EVENT_WRITE",0x47:"EVENT_WRITE_EOP",0x49:"RELEASE_MEM",0x4a:"PREAMBLE_CNTL",0x50:"DMA_DATA",0x58:"ACQUIRE_MEM",0x5e:"LOAD_UCONFIG_REG",0x5f:"LOAD_SH_REG",0x61:"LOAD_CONTEXT_REG",0x63:"LOAD_SH_REG_INDEX",0x64:"LOAD_UCONFIG_REG_INDEX",0x68:"SET_CONFIG_REG",0x69:"SET_CONTEXT_REG",0x6a:"SET_CONTEXT_REG_INDEX",0x76:"SET_SH_REG",0x77:"SET_SH_REG_OFFSET",0x79:"SET_UCONFIG_REG",0x7a:"SET_UCONFIG_REG_INDEX",0x80:"LOAD_CONST_RAM?",0x9b:"SET_SH_REG_INDEX",0x9f:"LOAD_CONTEXT_REG_INDEX",0x93:"WAIT_REG_MEM64",0x12:"CLEAR_STATE",0x88:"SET_SH_REG_INDEX?",0x7f:"SET_CONTEXT_REG_INDEX?"}
for f in sorted(glob.glob(d + "/ib-*.bin")):
    kind = os.path.basename(f).split("-")[2]; b = open(f, "rb").read(); ib = struct.unpack("<%dI" % (len(b) // 4), b[:len(b) // 4 * 4])
    i = 0; seq = []
    while i < len(ib):
        h = ib[i]; t = h >> 30; c = (h >> 16) & 0x3fff
        n = 1 if t not in (0, 3) or c == 0x3fff else c + 2
        if t == 3 and i + n <= len(ib):
            op = (h >> 8) & 0xff; ops[(kind, op)] += 1
            if op == 0x37 and n >= 4 and ((ib[i+1] >> 8) & 0xf) == 0: wd0[(kind, hex(ib[i+2]), n - 4)] += 1
            if want_size and len(ib) == want_size and kind == "dcb" and not shown and abs(i - around) <= 400:
                extra = ""
                if op == 0x69 and n >= 3: extra = "ctx 0x%x..+%d" % (ib[i+1] & 0xffff, n - 3)
                if op == 0x76 and n >= 3: extra = "sh 0x%x..+%d" % (ib[i+1] & 0xffff, n - 3)
                if op == 0x79 and n >= 3: extra = "uc 0x%x..+%d" % (ib[i+1] & 0xffff, n - 3)
                if op in (0x3c, 0x93): extra = "fn %d mem %d addr 0x%x" % (ib[i+1] & 7, (ib[i+1] >> 4) & 1, (ib[i+2] & ~3) | ((ib[i+3] & 0xffff) << 32))
                if op == 0x37: extra = "dst_sel %d addr 0x%x" % ((ib[i+1] >> 8) & 0xf, ib[i+2] | (ib[i+3] << 32))
                if op == 0x50: extra = "src 0x%x dst 0x%x %d B" % (ib[i+2] | (ib[i+3] << 32), ib[i+4] | (ib[i+5] << 32), ib[i+6] & 0x3ffffff)
                if op == 0x49: extra = "ev %d data_sel %d addr 0x%x" % (ib[i+1] & 0x3f, ib[i+2] >> 29, (ib[i+3] & ~3) | ((ib[i+4] & 0xffff) << 32))
                if op == 0x46: extra = "ev %d" % (ib[i+1] & 0x3f)
                seq.append("%5d %-22s len %-3d %s" % (i, NAMES.get(op, hex(op)), n, extra))
        elif t == 0 and want_size and len(ib) == want_size and kind == "dcb" and not shown and abs(i - around) <= 400:
            seq.append("%5d type0 len %d" % (i, n))
        i += n
    if seq and not shown:
        print("-- sequence of", os.path.basename(f), "around", around); print("\n".join(seq)); shown = True
print("-- opcodes per kind")
for (k, op), v in sorted(ops.items(), key=lambda x: (x[0][0], -x[1])): print("  %-4s %-24s %8d" % (k, NAMES.get(op, hex(op)), v))
print("-- WRITE_DATA DST_SEL 0 (register) targets: (kind, reg offset?, dwords)")
for k, v in wd0.most_common(12): print("  ", k, v)
