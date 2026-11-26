// SPDX-License-Identifier: GPL-2.0-only
// BC5's own fill shader for libSceAgc's CbMemsetExclusive export (nid_6nths4DHNrs, see
// src/reimpl/agc_cb.cpp agcCbFillMemory): writes a 16-byte pattern over [dst, dst + size).
// Written from the export's interface alone; it is not a copy of the original module's shader.
//
// Target: RDNA gfx10 (the BC-250 is gfx1013), wave64, 256 threads per group.
// Assembled on the box (no AMDGPU assembler on the laptop) with
//   llvm-mc -triple=amdgcn-amd-amdpal -mcpu=gfx1013 -mattr=+wavefrontsize64 -filetype=obj fill16.s
// and llvm-objcopy -O binary --only-section=.text; the dwords are kFillShaderWords in
// src/reimpl/agc_fill_shader.cpp (Ubuntu LLVM 21.1.8, 2026-11-20).
//
// Interface (set up by agcCbFillMemory and the header of agc_fill_shader.cpp):
//   s[0:3]  buffer descriptor of the destination: base = dst, stride 16, num_records = size / 16
//           (so a store past the end is dropped by the buffer range check)
//   s[4:7]  the 16 pattern bytes
//   s8      number of 64 KiB blocks, (size + 0xFFFF) / 0x10000
//   s9      work-group id x (COMPUTE_PGM_RSRC2.TGID_X_EN, right after the 9 user SGPRs)
//   v0      thread id x in the group (TIDIG_COMP_CNT = 0)
// Dispatch: 16 x 1 x 1 groups of 256 threads = 4096 threads, i.e. one 16-byte record per thread
// for each 64 KiB block. Thread t of group g writes record 4096 * k + 256 * g + t of block k.
// A size that is not a multiple of 16 leaves its last size % 16 bytes untouched (num_records
// counts whole records only), as the export's interface implies.

    s_cmp_eq_u32    s8, 0               // nothing to write
    s_cbranch_scc1  .Ldone
    s_lshl_b32      s10, s9, 8          // first record of this group: group id * 256
    v_add_nc_u32    v1, s10, v0         // record index of this thread in block 0
    v_mov_b32       v2, s4              // pattern dwords 0..3
    v_mov_b32       v3, s5
    v_mov_b32       v4, s6
    v_mov_b32       v5, s7
    s_mov_b32       s11, s8             // blocks left
.Lloop:
    buffer_store_dwordx4 v[2:5], v1, s[0:3], 0 idxen
    v_add_nc_u32    v1, 0x1000, v1      // same thread, next 64 KiB block (4096 records on)
    s_sub_u32       s11, s11, 1
    s_cmp_lg_u32    s11, 0
    s_cbranch_scc1  .Lloop
.Ldone:
    s_endpgm
