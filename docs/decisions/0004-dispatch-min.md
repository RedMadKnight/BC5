# 0004 — `dispatch-min`: the first native dispatch (phase 2 preparation)

**Status.** Accepted, 2026-09-29. Implements docs/PHASES.md phase 2, task 2, under decision D9
(HANDOFF §7): code, tests and documentation may be written before gate G1; **running it with
`--submit` needs the maintainer's explicit go-ahead each time** (hard rule 5, `CLAUDE.md`).

**Context.** Phase 2 has to show that a shader binary can be loaded into memory and executed through
`amdgpu` without RADV (HANDOFF F4, F5). The plan named libdrm `tests/amdgpu`; in libdrm 2.4.134 (the
version on the dev box, HANDOFF F13) that directory only keeps `amdgpu_stress.c` — the functional
dispatch tests live in IGT (igt-gpu-tools). IGT is MIT-licensed, so its data can be used here with
attribution.

Sources (`IGT` = gitlab.freedesktop.org/drm/igt-gpu-tools @ `9d4b6ef` (2026-09-29)):

| What | Where |
| --- | --- |
| gfx10 buffer-clear compute shader, 9 dwords, with its disassembly | IGT `lib/amdgpu/amd_shaders.c:295-309` (`bufferclear_cs_shader_gfx10`) |
| default compute state for `version == 10` | IGT `lib/amdgpu/compute_utils/amd_dispatch_helpers.c:16-72` (`amdgpu_dispatch_init`) |
| CU masks via `SET_SH_REG_INDEX` (0x9B) | same file `:75-100` (`amdgpu_dispatch_write_cumask`) |
| `COMPUTE_PGM_LO/HI`, `RSRC1 = 0x000C0041`, `RSRC2 = 0x00000090`, `NUM_THREAD_X/Y/Z = 64/1/1`, `RSRC3 = 0` | same file `:103-185` (`amdgpu_dispatch_write2hw`) |
| user data: V# of the destination in `USER_DATA_0..3` (word3 `0x1104bfac` for gfx10), clear value in `USER_DATA_4..7`, `COMPUTE_RESOURCE_LIMITS = 0`, `DISPATCH_DIRECT` = `DIM_X 0x10, DIM_Y 1, DIM_Z 1, DISPATCH_INITIATOR 1` (field order per Mesa `src/amd/vulkan/radv_cmd_buffer.c:15305-15309` @ `0866ae7`), NOP padding to 8 dwords with `0xffff1000` | IGT `lib/amdgpu/compute_utils/amd_dispatch.c:142-181` (`amdgpu_memset_dispatch_test`) |
| PM4 header encoding, `PACKET3_COMPUTE` = header \| bit 1 | IGT `lib/amdgpu/amd_PM4.h:48-52`; `docs/formats/agc.md` §2 |
| SH register offsets (relative to 0x2c00) | Mesa `gfx10.json` via `tools/bc5-agc` (HANDOFF F7), e.g. `COMPUTE_PGM_LO` = mm 0x2e0c → 0x20c |

**Decision.**

1. `backend/` gets a small, dependency-free **PM4 builder** (`bc5::Pm4Builder`) and a function that
   builds the complete memset indirect buffer for given GPU virtual addresses
   (`bc5::build_memset_ib`), reproducing the IGT sequence for gfx10 packet by packet. Unit tests pin
   the result dword for dword.
2. `backend/experiments/dispatch-min` is a CLI with three modes:
   - `--dump-ib <file>` (default path for development): builds the IB for placeholder addresses and
     writes it as raw little-endian dwords. Needs no GPU; the output is checked with
     `bc5-agc report` (zero unknown opcodes, every register write named) — our C++ encoder and our
     Rust decoder cross-check each other.
   - `--info` (only with `BC5_WITH_AMDGPU=ON`): opens the render node and prints what the kernel
     reports (family, chip, active CU count, GFX rings). Read-only ioctls, nothing is submitted.
   - `--submit` (only with `BC5_WITH_AMDGPU=ON`, **off by default**): allocates the shader, the
     destination and the command BO, uploads the shader, builds the IB with the real addresses,
     submits it on the **GFX ring** (the gfx1013 compute queue is disabled by RADV, HANDOFF F6),
     waits on the fence with a finite timeout, and checks every byte of the destination.
3. Deviations from IGT, each recorded here: the destination size is a parameter (default 16 KiB)
   and the dispatch is (size / 1 KiB)×1×1 thread groups, so groups × 64 threads × 16 bytes cover the
   whole buffer (IGT's test dispatches 16×1×1 and checks 16 KiB; its V# `num_records` is 0x400).
   *Amended 2026-09-30:* the first version read IGT's `0x10` as the initiator and wrote the group
   count into `DIM_Y`; experiment 0008 showed every run writing exactly 16 KiB. Fixed with the
   field order sourced above.
   *Amended 2026-09-30 (experiment 0013):* `MemsetParams` gained `rsrc1`, `rsrc2` and `vsharp_word3`
   with IGT defaults; `--console` selects the values Sony's library uses for the same program
   (`RSRC1 0x402c0041`, V# word 3 `0x0004bfac`), `--shader-file` loads captured program bytes,
   `--value`/`--groups` the fill pattern and size. The fence wait uses a 2 s timeout instead
   of infinite, so a hang is reported instead of waited on (the kernel's own GPU reset may still take
   the machine down, HANDOFF F6).
4. No test, CI job or script runs `--submit`. CI builds the `ON` variant and runs `--dump-ib` only.

**Consequences.** Phase 2 task 2 is ready to run the moment the maintainer confirms the machine is
idle; tasks 3–4 (a captured shader, userptr mapping for Q1) reuse the builder and the BO plumbing.
The PM4 builder is the seed of the phase-3 IB writer.
