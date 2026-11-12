# E1: what the GPU does at a page without backing (exp 0412; plan of 2026-11-13, nothing run)

`DESIGN-memory-architecture.md` section 7 asks it; options B and R2 (`DESIGN-learned-windows.md`) wait for it.
This is raw GPU submission (CLAUDE.md hard rule 5): it runs only in a slot of its own, with no emulator, the kernel
log streamed to the laptop, and the maintainer's word for the submission.

## The tool

`e1-probe`, a standalone program beside `backend/experiments/dispatch-min` (same build, `BC5_WITH_AMDGPU`), nothing
of the emulator. One GPU context, the GFX ring, one compute dispatch per job, each job waited for with a 3 s fence
timeout. It does nothing without `--submit --case N`; one case per process.

Programs, both from IGT `lib/amdgpu/amd_shaders.c` (MIT, igt-gpu-tools @ 9d4b6ef, the commit the backend already
cites): the gfx10 buffer-clear program that `dispatch-min` uses (16 bytes a thread written to a V# buffer), and the
buffer-copy program of the same file (a V# source, a V# destination). **The copy program is not in our tree yet and
I have not read that file: whether it holds a gfx10 copy program, and its bytes and packet sequence, is read on the
box (`~/src/igt-gpu-tools`) and taken verbatim with line numbers, not typed from memory** (hard rule 4;
TODO(verify)). Until it is in, cases 1 and 2 cannot be built; if IGT has no gfx10 copy program, the read cases need
another public source and the plan comes back for a decision.

Memory the tool makes: `real` (a 64 KiB GTT BO, mapped read-write), `zero` (a 64 KiB GTT BO, cleared, mapped
**readable only**: `AMDGPU_VM_PAGE_READABLE` without `WRITEABLE`), `prt` (a 2 MiB VA range from libdrm's allocator
mapped with `AMDGPU_VM_PAGE_PRT` and no BO, as `Device::map_prt_window` does), `out` (a 64 KiB GTT BO for the copy's
destination, filled with 0xA5 first so that a copy that did not run is visible).

## Cases, least dangerous first; each in its own process

| case | job | the expected result | kernel lines that are the expected result | lines that mean stop |
|---|---|---|---|---|
| 0 control | clear `real` with 0x22222222; copy `real` to `out` | both buffers read back as written; fence under 50 ms | none | any amdgpu line |
| 1 PRT read | copy `prt` to `out` | `out` all zero (F162's "reads 0"); fence under 50 ms | none | any amdgpu line |
| 2 read-only read | copy `zero` to `out` | `out` all zero | none | any amdgpu line |
| 3 PRT write | clear `prt` with 0x22222222; then case 0's two jobs | fence under 50 ms; the follow-up jobs run; `real` and `out` intact | none (F257: the write is dropped) | any amdgpu line |
| 4 read-only write | clear `zero` with 0x22222222; then case 0's two jobs if the context still works | **unknown: this is the question.** Either (a) the write is dropped with a page-fault line and the job ends, or (b) the job hangs: fence timeout, ring reset (F53's 14 s) | `[gfxhub] page fault`, the `GCVM_L2_PROTECTION_FAULT_STATUS` line, `ring gfx_0.0.0 timeout`, `Starting gfx_0.0.0 ring reset`, `reset succeeded` / the context marked guilty | `reset failed`, `GPU reset begin`, `MODE1`, `VRAM is lost` (then `bc5-gpu-watch` reboots the box by design) |

Cases 3 and 4 are the two that can cost a reset, so they run last and a reboot loses no other result. Case 4 is run
once. After any stop line nothing more is run.

## Recorded per case

- the tool's own lines: every VA and size, the return code of every `amdgpu_bo_va_op_raw`, the CS ioctl's return, the
  fence wait's return and time, the first 64 bytes and a count of non-zero bytes of `out`, `real` and `zero` after
  the job (read through their CPU mappings);
- `AMDGPU_INFO_GPUVM_FAULT` before and after (address, status, vmhub), with the status left undecoded beside the
  kernel's own line;
- the kernel log from the start of the process to 20 s after it (the stream on the laptop and `sudo dmesg` on the
  box); `/sys/class/devcoredump` if one appears (the saver copies it);
- kernel, Mesa and libdrm versions, `mem_info_vram_total`, uptime, whether Plasma's shell runs.

## What each outcome decides

- 1 and 2 read zero silently: a never-written page can be given to the GPU with no memory behind it, as far as
  reads go (option B's floor; R2 is sound for reads).
- 3 silent: R2 drops a stray write without a sign. That is the console's behaviour for the AMM window (F257) and is
  exactly why R2 must never sit under a view the import policy left out.
- 4 (a), a named fault and a living context: a read-only cover is a **write detector** that costs one dropped write:
  option B gets its net and the zero skip's defect (section 48) has a sound replacement.
- 4 (b), a hang and a reset: no cheap detector exists on this kernel; B needs complete knowledge of write targets
  and stays high-risk; the catcher for "does the GPU write there" remains a 14 s event.

## Before the slot

1. The copy program from IGT (a read of `~/src/igt-gpu-tools` on the box) and `e1-probe`'s source; `--dump-ib` of
   both jobs compared on the laptop against `dispatch-min --dump-ib` for the clear (the same builder) and against
   IGT's own packet sequence for the copy.
2. Build in the `ubuntu` container beside the backend's experiments; `--case 0` is the first submission.
3. Guard: no emulator, lock taken, his desktop saved (he is told the box may reboot), `sync` before cases 3 and 4.
