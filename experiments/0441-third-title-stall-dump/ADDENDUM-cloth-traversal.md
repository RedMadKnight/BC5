# 0441 addendum — the cloth traversal programs and the flat apertures (offline, 2026-11-22)

The README beside this file is frozen with its verdict. This addendum records an offline reading done afterwards
for exp 0439, whose run past frame 273 hung in a compute buffer the title marks "CS Cloth". Nothing here ran on the
box. Inputs, all private and never in git: the first dump's program area (exp 0440, `ymd1`), exp 0439's capture of
the hang (the compute buffer and umr's wave dump, laptop `Documents/bc5-private/t3-hang-20261122-0012/`), and
llvm-mc's listings of two programs (`shdis0441.py`). Tools: `shdis0441.py`, `shscan0441.py` here.

**What hung.** The buffer holds 47 dispatches of six programs. umr saved 40 waves, all of two programs
(0x8000143400 and 0x8000175900, four dispatches). 15 of them have `SQ_WAVE_STATUS` bit 23 (FATAL_HALT) and
`SQ_WAVE_TRAPSTS` bit 8 (the memory violation; bit names as cited in HANDOFF F249), with their program counters 27
to 53 dwords behind the third store of a push group (one at the loop's head). The other 25 have neither bit and
all stand on one `s_barrier` per program, waiting for their thread group. So this is not an endless walk: it is
F249's case of the second title in another title. An earlier note of this experiment's author to the other
sessions called these waves "looping"; that was wrong.

**The loop's shape.** Each of the two programs has six push groups in three pairs. The loop read in full (about
110 dwords) holds one group. It intersects the current node with `image_bvh_intersect_ray`, takes the nearest hit child as the
next node and pushes the other hit children; when a node is a leaf or nothing is hit it pops. It leaves when the
node is the end mark (−1) and the stack counter equals its base value, and it runs while the mask of active lanes
is not empty.

**The stack discipline.** The stack pointer is one packed 32-bit counter per lane (two 16-bit halves); its base
value is held in a scalar register. There is no base register supplied by the hardware in the address:

- push: `flat_store_dword` (offset 0, no scalar address) to a 64-bit address whose low half is the minimum of the
  counter's two 16-bit halves (`v_min_u32` with a sub-dword source selection) and whose high half is
  `v_med3_u32(sN, 0x70000000, counter)`, with `sN` = 0x80000000 made by `s_brev_b32 sN, 1`. A counter with its top
  bit set gives 0x8000'0000'0000'00xx, the console's LDS aperture; a small counter gives 0x7000'0000'…, the
  console's private aperture. Three stores per group, each two instructions after its clamp (three in one small
  program).
- pop: `ds_read_b32` for the LDS part, `scratch_load_dword` for the private part. No program stores through
  scratch.

On this box the apertures are 0x2000 (shared) and 0x1000 (private) (F249, from the waves' own registers and the
kernel's `SH_MEM_BASES` setup cited there), so every push address is in neither, exactly as F249 describes. The
halted lanes' counters are at or near their base value.

**Scope in this title** (`shscan0441.py` over the first dump's program area; the full list is in the sessions'
shared notes, not in git). The area begins with the title's shader objects, each with its register pairs, which
name 595 programs: 291 compute, 225 pixel, 78 through the ES register, 1 hull; 10 more programs are named by no
object. All 605 were walked instruction by instruction to their last `s_endpgm` with no loss of sync.

- Seven programs have flat-segment instructions, all compute, all stores, every one of them the push above:
  0x8000118900, 0x8000143400, 0x8000169200, 0x8000175900 (18 pushes in 6 groups, 6 `s_brev_b32 sN, 1`, 6 scratch
  loads, 6 intersections each) and 0x800035e100, 0x8000387500, 0x80003b1600 (3 pushes in 1 group, 1 `s_brev_b32`,
  1 scratch load, 1 intersection each).
- No program has a flat load, a scratch store, or a flat access whose high half is not that clamp. No pixel,
  ES-register or hull program has a flat or scratch instruction or an intersection.
- Three more compute programs use the intersection instruction with no flat or scratch access (0x800015c900,
  0x80001b8b00, 0x80002d3700; 12, 10 and 4 intersections).
- The literal 0x80000000 appears in other programs only where there is no flat access at all.

**What follows.** The second title's rewrite of F249 (the literal to 0x10000000, the `s_brev_b32` operand to 4)
matches this title's seven programs by the same instruction pattern; in the four large programs the registers of
the six `s_brev_b32 sN, 1` are reused by other instructions later, so the rule has to key on the instruction, not
on the register. Building and testing it is exp 0439's. Not read here: which title function builds the cloth
BVH, and the BVH buffers themselves (the capture did not keep them).
