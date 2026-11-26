; dc439 VS (legacy VS, wave64, no inputs): v0 = vertex id; s0 = width as float, s1 = height as float (user SGPRs 0, 1).
; RECTLIST corners: id 0 -> (0, 0), id 1 -> (w, 0), id 2 -> (0, h); position in screen pixels (viewport transform off).
v_and_b32 v1, 1, v0
v_and_b32 v2, 2, v0
v_mov_b32 v3, s0
v_mov_b32 v4, s1
v_mov_b32 v5, 0
v_cmp_ne_u32 vcc, 0, v1
v_cndmask_b32 v6, 0, v3, vcc
v_cmp_ne_u32 vcc, 0, v2
v_cndmask_b32 v7, 0, v4, vcc
v_mov_b32 v8, 1.0
exp pos0 v6, v7, v5, v8 done
s_endpgm
