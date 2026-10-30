#!/usr/bin/env python3
# BC5 experiment 0380 (F590, F591): read the launched COMPUTE_DIM triples of the B-class hangs several ways: hex,
# little-endian u16 pairs, f32, f16, and as RDNA (gfx10) SOP1 / SOP2 / VOP2 instruction words. The field layout is
# the AMD "RDNA 1.0 Instruction Set Architecture" reference guide's (SOP1: 0x17d << 23, sdst 22:16, op 15:8, ssrc0
# 7:0; SOP2: 0b10 << 30, op 29:23, sdst 22:16, ssrc1 15:8, ssrc0 7:0; VOP2: bit 31 = 0, op 30:25, vdst 24:17, vsrc1
# 16:9, src0 8:0). TODO(verify) the decodes with llvm-mc -mcpu=gfx1013 on the box.
import struct

TRIPLES = [
    ("12:12 (0x11d0289c00)", [65536, 196610, 2752552]),
    ("14:04 (0x11d02a4a00)", [481, 0x4000008A, 480]),
    ("C1/W1 bench (0x11d0323c00)", [3204318058, 2165211406, 100939574]),
]
for name, t in TRIPLES:
    raw = b"".join(struct.pack("<I", x) for x in t)
    print(name, " ".join(f"{x:08x}" for x in t))
    print("  u16", struct.unpack("<6H", raw))
    print("  f32", struct.unpack("<3f", raw))
    print("  f16", struct.unpack("<6e", raw))
    for x in t:
        if x >> 23 == 0x17D:
            print(f"  {x:08x} SOP1 op {(x >> 8) & 0xff} sdst {(x >> 16) & 0x7f} ssrc0 {x & 0xff}")
        elif x >> 30 == 2:
            print(f"  {x:08x} SOP2 op {(x >> 23) & 0x7f} sdst {(x >> 16) & 0x7f} ssrc1 {(x >> 8) & 0xff} ssrc0 {x & 0xff}")
        elif x >> 31 == 0:
            print(f"  {x:08x} VOP2 op {(x >> 25) & 0x3f} vdst {(x >> 17) & 0xff} vsrc1 {(x >> 9) & 0xff} src0 {x & 0x1ff}")
