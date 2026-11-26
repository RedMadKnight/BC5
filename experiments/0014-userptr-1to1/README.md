# 0014 — 1:1 mapping: a userptr BO at GPU VA == CPU VA on the BC-250 (phase 2, task 4; Q1)

**Question.** HANDOFF Q1: can anonymous CPU memory be handed to `amdgpu` as a userptr BO and mapped
at a GPU virtual address equal to the CPU pointer, so that a game's pointers are valid on both sides
without copies? What does it cost?

**Setup.** BC-250 dev box, 2026-09-30 11:16–11:30, kernel `7.2.4-ogc3.1.fc44`, libdrm_amdgpu
2.4.134, D8 memory split (512 MiB VRAM carve-out, GTT 7,966,146,560 bytes). New tool
`backend/experiments/userptr-min` (built with `BC5_WITH_AMDGPU=ON` in the `fedora` distrobox):
`mmap(MAP_ANONYMOUS | MAP_POPULATE)` N MiB → `amdgpu_create_bo_from_user_mem` →
`amdgpu_bo_va_op(MAP)` at the CPU address (or at a libdrm-chosen address with `--any-va`) → the
ADR 0004 memset dispatch (console `RSRC1`/V# values, experiment 0013) with the destination VA = that
address, GFX ring → every dword verified on the CPU through the original pointer. `--submit` run
with the maintainer's go-ahead, box otherwise idle, `dmesg` checked. Log:
[`raw/runs.log`](raw/runs.log).

**Result.**

| Case | userptr BO | map | GPU fill (submit → fence) | CPU verify | correct |
| --- | --- | --- | --- | --- | --- |
| 64 MiB, GPU VA == CPU VA (0x7ff1e7800000) | 1.73 ms | 0.28 ms | 0.65 / 0.56 / 0.58 ms (104–119 GB/s) | 29–33 ms | 3/3 runs, 0 dwords differ |
| 64 MiB, any VA (0x100000000), control | 2.03 ms | 0.28 ms | 0.62 / 0.57 ms | 31–32 ms | 2/2 |
| 512 MiB, GPU VA == CPU VA (0x7fea93000000) | 15.74 ms | 114 ms | 57.6 ms first, then 3.58 ms (150 GB/s) | 269–278 ms | 2/2 |

The kernel reports a user VA range of 0x10000..0x800000000000 (47 bits), so every canonical user
pointer of the emulator process is a legal GPU VA. `amdgpu_bo_va_op` accepted the CPU address
directly; no libdrm VA-range bookkeeping was needed for the 1:1 case. The first fill of the 512 MiB
mapping is slow (57 ms: page-table population on first touch); later fills run at memory speed. No
`dmesg` output, no reset.

**Verdict.** **Q1 answered: yes.** On the BC-250, `AMDGPU_GEM_USERPTR` + a chosen GPU VA maps
game-owned CPU memory 1:1 with zero copies; the GPU writes it at 100–150 GB/s and the CPU reads it
back through the same pointer. Costs: ~2 ms per 64 MiB to create the userptr BO, ~0.3 ms to map
(114 ms for 512 MiB), one slow first touch per mapping. This is the memory model for BC5's direct
mode: a game's allocations become userptr BOs mapped at their own addresses. Not measured:
GPU→CPU coherence under concurrent access, and what happens to a mapping when the game
`munmap`s or `madvise`s the range (the `AMDGPU_GEM_USERPTR_REGISTER` MMU notifier path).
With experiment 0013 this closes phase 2's gate G2 (captured shader native and bit-exact;
userptr verdict recorded), with the recorded deviation that the shader reference is a CPU model
rather than Kyty's recompiler.
