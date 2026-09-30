# 0013 — A compute program captured from ASTRO BOT runs natively on the BC-250 (phase 2, task 3)

**Question.** Phase 2 task 3: take a compute shader out of a capture and run it through `amdgpu`
with the parameters the console used, comparing the result against a reference. What do the
captured dispatch records say about how Sony's library drives the same hardware that IGT drives?

**Setup.** BC-250 dev box, 2026-09-30 11:06–11:25.
- Capture: the soft CP of experiment 0012 extended with a dispatch recorder (KytyPlus patch
  `0001`): it shadows the compute SH registers and, at every `DISPATCH_DIRECT/INDIRECT`, writes a
  record (dims, `RSRC1..3`, `NUM_THREAD_*`, `COMPUTE_STATIC_THREAD_MGMT_*`, `USER_DATA_0..15`) and
  the program bytes read from the shader VA (up to `s_code_end`, or `s_endpgm` + zero padding).
  Run `kytyplus-20260930-1106` (150 s): **2,213 dispatches, 20 distinct programs** (236 B–62 KB;
  [`raw/captured-compute-programs.txt`](raw/captured-compute-programs.txt)). Programs and records
  stay in `~/bc5-data` (game-derived); only the inventory is committed.
- Disassembly: `llvm-mc --disassemble -triple=amdgcn-amd-amdhsa -mcpu=gfx1013` (LLVM 21.1.8) decodes
  every program as gfx1013 (`s_inst_prefetch`, `image_load … dim:SQ_RSRC_IMG_2D`, `ds_*`,
  `v_cmpx_*_e32`, `s_code_end`).
- Native run: `backend/experiments/dispatch-min` gained `--shader-file`, `--console`, `--rsrc1/2`,
  `--vsharp3`, `--value`, `--groups` (unit test pins the new dwords; ctest 8/8). Built with
  `BC5_WITH_AMDGPU=ON` in the `fedora` distrobox; `--submit` with the maintainer's go-ahead
  ("tak, działaj"), box otherwise idle, `dmesg` checked ([`raw/native-runs.log`](raw/native-runs.log)).

**Result.**

1. **The most-used program is the IGT buffer-clear shader, byte for byte.** Program `0x908e86a00`
   (1,503 of 2,213 dispatches, gfx ring and compute rings) is the nine dwords
   `d7460004 04010c08 7e000204 7e020205 7e040206 7e060207 e01c2000 80000004 bf810000` — identical
   to `kBufferClearCsGfx10` (IGT `amd_shaders.c:295-309`). Sony's `libSceAgc` uses it for buffer
   fills: user data 0..3 = a V#, 4..7 = the 16-byte fill pattern (0, `fffffff0`, `ffffffff`,
   `3c000000 00000000 …`), dims 512–12,288 groups of 64 threads, plus 3-D variants (6×4×8) and
   other V# formats (word 3 `0x91b00fac`, `0xc8200000`, `0x91800924`…).
2. **Console parameters differ from IGT's in two places** (every one of the 1,503 records):
   `COMPUTE_PGM_RSRC1 = 0x402c0041` (IGT `0x000c0041`: bit 30 = `WGP_MODE`, bits 21–23 set) and
   V# word 3 `= 0x0004bfac` (IGT `0x1104bfac`: `RESOURCE_LEVEL`, bit 24, and bit 28 clear).
   `RSRC2 = 0x90` and `NUM_THREAD = 64×1×1` match. `COMPUTE_STATIC_THREAD_MGMT_*` are 0 on the
   gfx-ring dispatches of this program (the masks of experiment 0012 are written by the compute-ring
   preambles).
3. **Native runs, all bit-exact against the CPU reference** (every dword of the destination equals
   the fill value): the built-in program (16 KiB); the built-in program with console parameters;
   the **captured program** with IGT parameters; the captured program with console parameters at a
   console size, 12,288 groups = 12 MiB, value `0xfffffff0`; and 4,096 groups with `0x3c000000`.
   No `dmesg` output, no reset.

**Verdict.** Phase 2 task 3 done for the first captured program: a compute shader taken from a
console-format capture of ASTRO BOT executes on the BC-250 through `amdgpu`, with the exact
`RSRC1`/V# values Sony's library used, and produces bit-identical output to the reference.
Deviation from the task text: the reference is the program's semantics checked on the CPU (a
16-byte fill), not Kyty's recompiler, because the program is nine instructions whose meaning is
documented (IGT) and because KytyPlus's recompiler path is not exercised by the track-B setup. The
finding that Sony's fill program *is* IGT's makes this the cheapest possible cross-check; the other
19 programs (real game shaders with images, LDS and barriers) need their input buffers captured
before they can be replayed, which is the next step. Gate G2 still needs task 4 (userptr, Q1).
