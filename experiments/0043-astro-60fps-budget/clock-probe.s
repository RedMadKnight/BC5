// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0043: the shader clock under load, from inside a shader. Interface as the
// buffer-clear program of ADR 0004 (s[0:3] V#, s8 tgid.x, v0 thread id). Each thread reads the
// core clock counter (s_memtime) and the constant-rate counter (s_memrealtime), runs an ALU loop,
// reads both again and stores (memtime delta, realtime delta, group id, loop result). The clock is
// memtime delta / realtime delta x the realtime rate (the kernel's gpu_counter_freq).
// Build: llvm-mc -arch=amdgcn -mcpu=gfx1013 -filetype=obj -o clock.o clock-probe.s
//        llvm-objcopy -O binary --only-section=.text clock.o clock.bin
// Run:   dispatch-min --submit --console --shader-file clock.bin --bytes 16384 --repeat R --print 4
v_lshl_add_u32 v4, s8, 6, v0
v_mov_b32 v5, v4
s_memtime s[10:11]
s_memrealtime s[12:13]
s_waitcnt lgkmcnt(0)
s_movk_i32 s9, 0x4000
loop:
v_mul_lo_u32 v5, v5, v5
v_add_nc_u32 v5, v5, v4
v_mul_lo_u32 v5, v5, v5
v_add_nc_u32 v5, v5, v4
s_addk_i32 s9, -1
s_cmpk_lg_u32 s9, 0
s_cbranch_scc1 loop
s_memtime s[14:15]
s_memrealtime s[16:17]
s_waitcnt lgkmcnt(0)
s_sub_u32 s14, s14, s10
s_sub_u32 s16, s16, s12
v_mov_b32 v0, s14
v_mov_b32 v1, s16
v_mov_b32 v2, s8
v_mov_b32 v3, v5
buffer_store_format_xyzw v[0:3], v4, s[0:3], 0 idxen
s_endpgm
