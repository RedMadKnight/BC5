# 0190 — The reflection traversal does not loop: its stack pushes address the console's FLAT apertures, take a memory violation, and the waves are halted

**Question.** Every compiled variant of the second title's ray-traced-reflection traversal "hangs in
the same BVH stack loop" (F113–F116, F184, F232, F234, F248): 0x11d049aa00 on the start screen,
0x11d04a6000 at PC 0x11d04a7cfc, 0x11d040e200 when the compaction 0x909974400 runs, 0x11d04bb900 once
the night scene's tessellated surfaces are drawn (`BC5_DIRECT_GC_TF_RING=1`). Most of the stuck waves
sit with EXEC = 0 on an `s_cbranch_execz`. The trees they walk have no cycle (F185). What is the loop's
exit condition, and why is it never met?

**Setup.**
- Offline, on the BC-250 dev box, 2026-10-21 22:57–23:40; no GPU run (the box was in use by another
  session until 23:18, and every run that lets the traversal execute removes a skip: the maintainer's
  call). Box: kernel 7.2.9-ogc3.1; the `ubuntu` distrobox's `llvm-mc` for disassembly.
- Data (private, on the box, never committed): the shader dumps of exp 0189
  (`~/bc5-data/captures/exp0189-shaders/`, 380 programs; 0x11d040c900 from
  `~/bc5-data/captures/shaders-0159/`); the `umr -O halt_waves -wa` dumps of exp 0189 (R6, S1, S3:
  `~/bc5-work/exp0189/waves-*.txt`) and the 63 root hang-watcher dumps of 2026-10-14..19
  (`/var/tmp/bc5-hang-*.txt`, the stalls of F173–F234). Offset listings and the patched copies:
  `~/bc5-work/exp0190/` (private).
- Scripts (here): `disoff.sh` (offset listing: `disf.sh` of exp 0160 with `llvm-mc --show-encoding`
  sizes, undecodable dwords placed by the warning column; checked: the listing's `s_endpgm` falls on
  the dword a raw scan finds, for all six programs), `wparse.py` (parser for umr's wave dumps),
  `wsum2.py` (per-lane traversal state), `wtable.py` (per dump: waves, `FATAL_HALT`, `TRAPSTS`, PCs),
  `wsp.py` (stack depths), `wcmp.py` (two dumps of the same stall compared), `aptest.py` (the fix's
  matcher, offline), `patch_0190.py` (the fix, a host knob).
- Register fields: Mesa's gfx10 register JSON in `tools/bc5-agc/regdb/gfx10.json` (commit 9ad5bf2 here):
  `SQ_WAVE_STATUS` (0x408) `HALT` bit 13, `FATAL_HALT` bit 23; `SQ_WAVE_TRAPSTS` (0x40c) `EXCP` bits
  0–8, `XNACK_ERROR` bit 28, `DP_RATE` bits 29–31. EXCP bit 8 is the memory violation, a non-maskable
  exception: Linux `drivers/gpu/drm/amd/amdkfd/cwsr_trap_handler_gfx10.asm` (commit 62498e7):
  `SQ_WAVE_TRAPSTS_MEM_VIOL_MASK = 0x100`, "memory_violation, illegal_instruction and xnack_error
  exceptions always cause the wave to enter the trap handler".
- Apertures under amdgpu (upstream Linux; the box's kernel agrees at run time, see Result):
  `drivers/gpu/drm/amd/amdgpu/gmc_v10_0.c` (commit 5597314),
  `gmc_v10_0_early_init`: `shared_aperture_start = 0x2000000000000000ULL`,
  `private_aperture_start = 0x1000000000000000ULL` (4 GiB each); `gfx_v10_0.c` (commit a04c0c7), the
  `SH_MEM_BASES` loop over the GFX hub's VMIDs: `PRIVATE_BASE = private_aperture_start >> 48`,
  `SHARED_BASE = shared_aperture_start >> 48` (the KFD compute VMIDs get 0x6000 instead).

**Result.**
- **The exit logic** (0x11d04bb900 +0x1028–0x1ac0; the same structure at other offsets in every
  variant). The walk of an object tree is per lane: `image_bvh_intersect_ray` on the current node; for a
  box node the nearest hit child becomes the next node and the other hit children are pushed on a
  per-lane stack; a leaf child (node type 0–3) indexes the 8-byte records of the link V# (the tree's own
  memory, stride 8, record count from the tree header +0x60), a list walked record by record until a
  record's second dword is negative; a lane whose next node is −1 pops. The stack pointer is one VGPR of
  two 16-bit halves: the high half a scratch offset starting at 0xff84 (−124, the empty stack), the low
  half an LDS address, stepping by 4 and by 0x80 (32 lanes × 4 bytes) per entry; the first 31 entries
  live in LDS, the next in scratch, and pushes stop at 76. A lane leaves the loop when it must pop at
  an empty stack; the loop runs while any lane remains. There is no iteration bound, but every step
  consumes a node or a record, so on an acyclic tree (F185) the walk ends — if the pops return what was
  pushed.
- **The push and the pop take different paths.** The pop reads the slot directly: `ds_read_b32` (LDS)
  or `scratch_load_dword`. The push is a `flat_store_dword` to a 64-bit address whose high dword is the
  median of two constants and the stack pointer — `s_brev_b32 sN, 1` (0x80000000) and the literal
  0x70000000 of a `v_med3_u32` — giving 0x80000000 for LDS entries (pointer's high half negative) and
  0x70000000 for scratch entries, i.e. the console's apertures: LDS at 0x8000'0000'0000'0000, private
  at 0x7000'0000'0000'0000. The same idiom, six pushes in two copies of the walk, is in all six
  traversal variants: 0x11d049aa00, 0x11d04a6000, 0x11d040e200, 0x11d040c900, 0x11d04bb900 and
  0x11d0488a00 (a sixth, not yet seen running). They are the only programs with FLAT (not `global_`/
  `scratch_`) memory instructions among the 380 dumped in exp 0189 (`raw/flat-scan.txt`).
- **The box's apertures are 0x2000… (LDS) and 0x1000… (private).** That is what amdgpu programs (Setup),
  and what the traversals themselves read: elsewhere they load `src_shared_base` / `src_private_base`
  and pack them into a VGPR lane, which holds 0x10002000 in every wave of R6, S3 and two dumps of
  2026-10-16 (`raw/apertures.txt`; the console would give 0x70008000). So on the host every push
  addresses 0x8000'0000'0000'00xx, inside neither aperture. R6's waves show the last push: value 0x380
  to (lane × 4, 0x80000000), LDS slot 0 through the console's aperture.
- **The stuck waves are halted by a memory violation, not looping.**
  - Every wave of every traversal stall ever dumped has `SQ_WAVE_STATUS.FATAL_HALT` = 1 and
    `SQ_WAVE_TRAPSTS` = 0x40000100 (EXCP bit 8): 10,272 waves in 54 dumps, the six variants and exp
    0137's copy (`raw/dumps-table.txt`).
    The only waves without `FATAL_HALT` (2 in the 15:49:44 dump of 2026-10-16) have no EXCP bit 8 — the
    dump's own halt (`HALT`, bit 13) does not set it. Exp 0189's committed R6 summary shows the same
    STATUS values (0x0081xxxx: bit 23 set).
  - Two dumps of the same stall a second apart (five pairs) are identical in every wave's PC, SGPRs
    and VGPRs (`raw/paired-dumps.txt`); successive stalls (16 s apart, after a ring reset) are new waves.
  - The lanes stopped early, all in the same place: R6 (0x11d04bb900), all 1,447 live lanes at node
    0x35 with one stack entry; S3 (0x11d04a6000), all 6,617 at node 0x35 with five; across all dumps
    the stack holds 0–6 entries at the halt (16–18 in the four waves of 0x11d040c900),
    `raw/lane-states.txt`, `raw/stack-depths.txt`. Each wave was halted within its first iterations,
    after its first push(es); EXEC = 0 on the `s_cbranch_execz` is where a halted wave stopped between
    iterations, not a spin.
  - The kernel logs no VM fault at these stalls (exp 0189 R1–R8: no fault record), so the address is
    refused before translation; which unit flags a FLAT address outside both apertures and the 48-bit
    VA range is TODO(verify) (no public AMD document found on it).
- **This explains the earlier observations.** F186: with every ray query missing nothing is pushed, so
  nothing hangs. F234/F248: the stall comes when the walks first reach a box with two hit children —
  with the compaction's per-frame trees, or once the tessellated surfaces exist; with neither, the
  variants that ran (run 834) never pushed. F185: the trees are acyclic — they were never the cause.
  Exp 0137: the loop-bounded copy "still looped" (run 563, dump 15:20:45 of 2026-10-16, PCs in the code
  area 0xfe000013c8–1d78): those waves are `FATAL_HALT` with EXCP bit 8 too — no bound helps a wave
  that is halted. The machine-wide picture (SPI and CP busy, GE idle, F248; a ring reset recovers) is
  a dispatch whose halted waves never end.
- **A fix, built offline, not yet run.** `patch_0190.py` adds `BC5_DIRECT_FLAT_APERTURE=1` (or a comma
  list of program addresses): at a program's first dispatch the host finds each `v_med3_u32 vD, sN,
  0x70000000, vY` with its `s_brev_b32 sN, 1` up to 1,024 dwords before, and rewrites, in the title's
  code in place, the literal to 0x10000000 and the operand to 4 (`s_brev_b32 sN, 4` = 0x20000000):
  the same median with the host's apertures (LDS still the larger). Encodings from
  `llvm-mc -triple=amdgcn -mcpu=gfx1013 -show-encoding`. Offline: the matcher finds exactly the six
  pushes in each of the six variants and nothing in the other 375 programs; the patched 0x11d04bb900
  disassembles to `s_brev_b32 s38, 4` / `v_med3_u32 v19, s38, 0x10000000, v129` (`raw/flat-scan.txt`);
  the patch applies twice idempotently to the box's source and the patched `bc5LleAgc.cpp` compiles with
  the build's own command (clang from the expanded compile database, into a scratch object; four
  warnings, all in pre-existing code). It is not in the box's binary and has not run.
- Outside this question: the watcher's other stalls are memory violations too. 09:51:37 on 2026-10-14
  (227 waves at 0x11d0376fa4) and 16:54:38 on 2026-10-19 (766 waves at 0x11d0288844) add
  `XNACK_ERROR` (bit 28), a translation-side violation; 13:38:11/13:38:25 on 2026-10-16 (822 waves at
  0x5007cf940, a program outside the exp 0189 dumps) have EXCP bit 8 alone. Not examined here.

**Verdict.**
- **The traversal does not loop.** Its waves are halted by the hardware after a memory violation, and
  the dispatch never completes. The cause is the per-lane BVH stack's push: the title's code builds the
  push address with the console's fixed FLAT aperture bases (LDS 0x8000…, private 0x7000…), while
  amdgpu gives graphics contexts 0x2000… and 0x1000…, so the first push of any wave whose rays hit a box
  with two or more children leaves both apertures. All six compiled variants share it, which is why the
  stall moved from variant to variant as skips were added (F173, F232, F234, F248) and why it needs the
  compaction's trees or the tessellated surfaces to show. Not a bad tree, not the GPU's system state.
- **Next (the maintainer's call): one watched run with `BC5_DIRECT_FLAT_APERTURE=1`** after rebuilding
  the box's binary with `patch_0190.py` (synced, D16): first with the traversal skips removed and the
  compaction 0x909974400 still skipped (`BC5_DIRECT_SKIP_PGM=909974400`, TF ring on), the journal-stall
  wave dump armed (F229: dedicated run only); then with no skips. Expected: no stall, and the
  reflections drawn. If a stall remains, its waves' `TRAPSTS` tells whether it is still a violation.
