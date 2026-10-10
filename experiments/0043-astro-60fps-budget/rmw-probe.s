// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0043: a read-modify-write variant of the buffer-clear compute program of ADR 0004,
// to compare the read bandwidth of memory kinds. Same interface: s[0:3] the V# of the buffer,
// s4..s7 the value, s8 tgid.x, v0 the thread id in the group. Each thread loads its 16-byte record,
// ORs the value into it and stores it back (the check of dispatch-min then holds: the buffer starts
// at 0 and ends at the value).
// Build: llvm-mc -arch=amdgcn -mcpu=gfx1013 -filetype=obj -o rmw.o rmw-probe.s
//        llvm-objcopy -O binary --only-section=.text rmw.o rmw.bin
// Run:   dispatch-min --submit --console --shader-file rmw.bin --bytes N --dst KIND --repeat R
v_lshl_add_u32 v4, s8, 6, v0
buffer_load_format_xyzw v[0:3], v4, s[0:3], 0 idxen
s_waitcnt vmcnt(0)
v_or_b32 v0, s4, v0
v_or_b32 v1, s5, v1
v_or_b32 v2, s6, v2
v_or_b32 v3, s7, v3
buffer_store_format_xyzw v[0:3], v4, s[0:3], 0 idxen
s_endpgm
