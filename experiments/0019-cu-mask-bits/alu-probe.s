// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0019: an ALU-bound variant of the buffer-clear compute program of ADR 0004, to
// tell how much execution capacity each CU-mask bit is worth. Same interface: s[0:3] the V# of
// the destination, s4..s7 the value, s8 tgid.x (COMPUTE_PGM_RSRC2: 8 user SGPRs, TGID_X), v0 the
// thread id in the group. Every thread runs 4,096 iterations of an integer loop, then stores.
// Build: llvm-mc -arch=amdgcn -mcpu=gfx1013 -filetype=obj -o alu.o alu-probe.s
//        llvm-objcopy -O binary --only-section=.text alu.o alu.bin     (20 dwords)
// Run:   dispatch-min --submit --console --shader-file alu.bin --bytes N --cu-mask HEX --repeat R
v_lshl_add_u32 v4, s8, 6, v0
s_movk_i32 s9, 0x1000
v_mov_b32 v5, v4
loop:
v_mul_lo_u32 v5, v5, v5
v_add_nc_u32 v5, v5, v4
v_mul_lo_u32 v5, v5, v5
v_add_nc_u32 v5, v5, v4
s_addk_i32 s9, -1
s_cmpk_lg_u32 s9, 0
s_cbranch_scc1 loop
v_mov_b32 v0, s4
v_mov_b32 v1, s5
v_mov_b32 v2, s6
v_mov_b32 v3, s7
buffer_store_format_xyzw v[0:3], v4, s[0:3], 0 idxen
s_endpgm
