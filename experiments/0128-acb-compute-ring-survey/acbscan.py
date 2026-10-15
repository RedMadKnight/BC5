#!/usr/bin/env python3
# ADR 0009 step 1: what in dumped compute buffers (ib-*-acb-*.bin) a compute ring would refuse.
# Mirrors bc5::policy::is_graphics_only / compute_ring_refusal (top-level buffers only).
import glob, struct, sys, collections

GFX_ONLY = {0x12: "CLEAR_STATE", 0x13: "INDEX_BUFFER_SIZE", 0x26: "INDEX_BASE", 0x28: "CONTEXT_CONTROL",
            0x2a: "INDEX_TYPE", 0x2f: "NUM_INSTANCES", 0x42: "PFP_SYNC_ME", 0x61: "LOAD_CONTEXT_REG",
            0x69: "SET_CONTEXT_REG", 0x9f: "LOAD_CONTEXT_REG_INDEX", 0x24: "DRAW_INDIRECT",
            0x25: "DRAW_INDEX_INDIRECT", 0x27: "DRAW_INDEX_2", 0x2c: "DRAW_INDIRECT_MULTI",
            0x2d: "DRAW_INDEX_AUTO", 0x35: "DRAW_INDEX_OFFSET_2", 0x38: "DRAW_INDEX_INDIRECT_MULTI"}

files = []
for d in sys.argv[1:]:
    files += sorted(glob.glob(d + "/ib-*-acb-*.bin"))
refused = collections.Counter()
ops = collections.Counter()
inits = collections.Counter()
forms = collections.Counter()
bad_files = 0
for f in files:
    b = open(f, "rb").read()
    w = struct.unpack("<%dI" % (len(b) // 4), b[: len(b) // 4 * 4])
    i = 0
    why = None
    while i < len(w):
        h = w[i]
        t = h >> 30
        n = 1
        if t in (0, 3):
            c = (h >> 16) & 0x3fff
            n = 1 if c == 0x3fff else c + 2
        if i + n > len(w):
            break
        if t == 3:
            op = (h >> 8) & 0xff
            ops[op] += 1
            if op in GFX_ONLY:
                refused[GFX_ONLY[op]] += 1
                why = why or GFX_ONLY[op]
            init = None
            if op == 0x15 and n >= 5:
                init = w[i + 4]
                forms["DISPATCH_DIRECT"] += 1
            if op == 0x16:
                forms["DISPATCH_INDIRECT len %d" % n] += 1
                if n == 3:
                    refused["DISPATCH_INDIRECT gfx form"] += 1
                    why = why or "gfx-form indirect"
                if n >= 4:
                    init = w[i + 3]
            if init is not None:
                inits[init] += 1
                if init & 2 and not init & 0x20:
                    refused["PARTIAL_TG_EN"] += 1
                    why = why or "partial tg"
        i += n
    if why:
        bad_files += 1
print("buffers %d, refused %d" % (len(files), bad_files))
print("refusals:", dict(refused))
print("dispatch forms:", dict(forms))
print("initiators:", {hex(k): v for k, v in inits.most_common()})
print("opcodes:", {hex(k): v for k, v in sorted(ops.items())})
