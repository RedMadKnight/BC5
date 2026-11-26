#!/usr/bin/env python3
# BC5 experiment 0190: offline check of the matcher in patch_0190.py (the same rules as flat_aperture_fix) on
# dumped programs. Prints the stack-push sites found per program and writes a patched copy to <out>/<name>.bin
# for disassembly (disoff.sh). Usage: aptest.py <out dir> <program.bin>...
import os
import struct
import sys

out = sys.argv[1]
os.makedirs(out, exist_ok=True)
for f in sys.argv[2:]:
    d = open(f, "rb").read()
    n = len(d) // 4
    w = list(struct.unpack("<%dI" % n, d[:4 * n]))
    end = next((i for i, x in enumerate(w) if x == 0xBF810000), n)  # s_endpgm
    sites = brevs = 0
    where = []
    k = 0
    while k + 2 < end:
        d0, d1 = w[k], w[k + 1]
        s = d1 & 0x1FF
        # v_med3_u32 (VOP3, no modifiers), src1 = literal 0x70000000, src0 = an SGPR
        if (d0 & 0xFFFFFF00) == 0xD5590000 and ((d1 >> 9) & 0x1FF) == 0xFF and w[k + 2] == 0x70000000 and s <= 105:
            at = 0
            for j in range(k - 1, max(-1, k - 1025), -1):  # s_brev_b32 s<src0>, 1 (or 4 once rewritten)
                if w[j] in (0xBE800B81 | (s << 16), 0xBE800B84 | (s << 16)):
                    at = j + 1
                    break
            if at:
                if w[at - 1] != (0xBE800B84 | (s << 16)):
                    w[at - 1] = 0xBE800B84 | (s << 16)
                    brevs += 1
                w[k + 2] = 0x10000000
                sites += 1
                where.append(hex(4 * k))
                k += 3
                continue
        k += 1
    open(os.path.join(out, os.path.basename(f)), "wb").write(struct.pack("<%dI" % n, *w))
    print(os.path.basename(f), "sites", sites, "s_brev", brevs, " ".join(where))
