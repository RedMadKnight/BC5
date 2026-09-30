# 0016 — Phase 3 step (b): first live submissions from the track-B host (in progress)

**Question.** ADR 0005 step (b): does the BC-250 accept the state preamble IB that Sony's
`libSceAgc` builds, submitted from inside the track-B host through the BC5 direct path (1:1
userptr mappings, policy filter, scratch IB, GFX ring)?

**Setup.** BC-250 dev box, 2026-09-30 11:50–13:40. KytyPlus `f266548` + patch `0001` with
`BC5_GC_MODE=direct`, `KYTY_BC5_ANON_BACKING=1`, `BC5_DIRECT_STAGE=preamble`, the backend built
with clang in the `ubuntu` distrobox and linked into `kyty_emulator`. Every attempt: maintainer's
go-ahead, Steam and the indexer stopped, keep-awake on, `dmesg` baseline; from attempt 2 on, a
crash journal (`direct.log` with `fsync`, raw + filtered IB files) in the capture directory.
Standalone replays with `dispatch-min --ib-file` (fedora distrobox, own 4 KiB command BO).

**Result.** Five attempts, five machine resets (no kernel message survives; the BC-250 goes down
with the GPU reset, F6). What the journal established:

| # | direct-mode configuration | outcome |
| --- | --- | --- |
| 1 | header IBs, full BO list (198 userptr BOs), game's `CONTEXT_CONTROL` | reset; journal lost (no `fsync` yet, capture dir never reached the disk) |
| 2 | + `CONTEXT_CONTROL` rewritten to RADV's, memory-operand check, `LOAD_*`/`COND_EXEC`/`WRITE_DATA` dropped | submit #0 (`CONTEXT_CONTROL`, 3 dwords) **OK 5.3 ms**; submit #1 (150 dwords: NOPs + 2 × `CONTEXT_CONTROL`) **fence timeout 2 s** → reset |
| 3 | + scratch IB padded to 8 dwords | same: #0 OK, #1 timeout → reset |
| 4 | + `BC5_DIRECT_NO_BOLIST=1` (scratch BO only) | same: #0 OK (0.04 ms), #1 timeout → reset |
| 5 | + private amdgpu device (`amdgpu_device_initialize2`, no libdrm dedup with the host's RADV), scratch at a high GPU VA, fixed mapping sync (946 mappings, 0 failures) | same: #0 OK, #1 timeout → reset |

Standalone replays of the exact filtered IB of submit #1 (`A-exact`, 146 packets: 144 one-dword
NOPs `0xffff1000` and `CONTEXT_CONTROL 0x80000000/0x80000000` at packets 8 and 139), of 152 NOPs,
of `CONTEXT_CONTROL` first + NOPs and of `CONTEXT_CONTROL` at packet 8: **all four pass**
(`~/bc5-work/replay/replay.log`). `BC5_DIRECT_STAGE=maponly` (mappings only, no submit) runs the
game for 90 s without incident (892–946 mappings, 1.7–2.2 GB).

So far excluded as the cause: the IB content, the userptr BO list, sharing RADV's VM/VA space,
IB alignment, low-VA collisions. Not yet excluded: the host process itself (the ubuntu
distrobox's libdrm, the submitting thread being a guest thread, concurrent RADV work in the same
process, the 1 MiB scratch BO vs `dispatch-min`'s 4 KiB command BO, coherence of the scratch
mapping written from the host process).

**Standalone bisection** (`backend/experiments/direct-selftest`, the `bc5::direct::Device` path
without any host, fedora container, `--journal` with `fsync`), three more resets:

| # | Device configuration | journal |
| --- | --- | --- |
| 6 | private device, scratch at the kernel-half "high" VA | (output lost) reset |
| 7 | private device, scratch at 16 TiB | `8 nops OK 0.04 ms`, `152 nops TIMEOUT` |
| 8 | `--dedup --legacy-va` (= `dispatch-min`'s device and VA), 1 MiB scratch | `8 nops OK 0.05 ms`, `152 nops TIMEOUT` |
| 9 | same, page-sized (4 KiB) scratch | reset (same pattern) |

`dispatch-min --ib-file` replays of 152 NOPs and of `A-exact` pass every time, as **single**
submissions. `userptr-min` runs three submissions per process, but each fills 64 MiB between them.
The pattern that fits every observation: the first small IB makes the CP fetch one or two 32-byte
chunks of the scratch — the NOPs plus the zero dwords behind them — into the GPU L2; the CPU then
rewrites the same buffer (CPU-side coherence does not invalidate GL2); the next submit fetches the
stale lines, reaches the zeros, executes them as type-0 packets and hangs. Fix: the scratch IB is
mapped `MTYPE_UC` for the GPU (every fetch goes to memory).

**Next.** `direct-selftest` with the uncached scratch (fedora, then ubuntu, then with a userptr
mapping), then `BC5_DIRECT_SELFTEST=1` in the host, then step (b) proper. Each run needs the
maintainer's go-ahead; each hang costs a manual power cycle.

**Verdict.** Open. Step (b) is not passed; nine resets bought a precise negative result (the
console's preamble, filtered, is not what hangs the GPU), a crash journal that survives, and a
mechanism that explains all nine.
