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

**Confirmation** (run 10, 14:40, fedora, scratch mapped `MTYPE_UC`): the very sequence that hung
nine times passes — `8 nops OK seq 1`, `152 nops OK seq 2`, four `cc at 8 and 139` OK, the recorded
`A-exact` (150 dwords) OK; 30–50 µs each. Runs 11–12 (ubuntu container; ubuntu with a 256 MiB
1:1 userptr mapping in the BO list): see `raw/selftest.log`.

**Step (b1)** (run 13, 14:53, ubuntu, in the host: `BC5_DIRECT_STAGE=preamble`,
`BC5_DIRECT_DROP_OPS=5e,5f,61,63,64,9f,22,37`, full BO list, 45 s + kill lag = 90 s of game time,
22 flips): **no reset**. 72 submits of the console's submit-header IBs (3-dword `CONTEXT_CONTROL`,
the 150-dword preamble with 14 packets NOP-ed, the 2-dword trailer) through the GFX ring:

| submits | outcome | per submit |
| --- | --- | --- |
| #0–#29 | OK, fence signalled | 2.3 ms at 198 mappings → 11.4 ms at 902 mappings (userptr validation of every BO in the list) |
| #30–#71 | `FAILED rc -14` (`EFAULT` from `amdgpu_cs_submit`), no fence, GPU untouched | 0.1 ms |

The break is exactly after a 4-mapping batch (902 → 906) that followed a guest thread start
(`ProductNextLoad_ATQT`, stack at 0x335338000) and a 16 KiB flexible-memory map. `EFAULT` from
the CS ioctl is `amdgpu_ttm_tt_get_user_pages` (`vma_lookup` / `hmm_range_fault`) failing for one
userptr BO on the list: its pages are no longer inside an rw anonymous VMA. The host's mapping
sync was purely additive — it walked `/proc/self/maps` for new resident rw-anonymous runs and
never removed a mapping — while KytyPlus's `KernelMunmap` → `UnmapBacking`/`ReleaseFree`
(`src/kernel/memory.cpp`) replaces or drops the VMA under it. One stale BO fails the whole
submission, every time, until it is removed. `dmesg`: nothing (the kernel rejects the CS before
the ring).

Fix (host, `bc5LleAgc.cpp` `sync_mappings`): pass 1 revalidates every mapping against the current
rw-anonymous VMA list and unmaps the ones that fell out (`unmap … (no longer rw anonymous)` in
`direct.log`); pass 2 adds the new runs as before; `EFAULT` at submit forces an immediate resync and
one retry (`(retried)` in the journal) instead of counting as a failure. Not a GPU hang in any
form: the mode is not wedged by `EFAULT`.

**Next.** Step (b1) again with the revalidating sync, then (b2) the full preamble.

**Verdict (interim).** The mechanism is confirmed (F25) and the first 30 console-built IBs ran on the
BC-250's GFX ring from inside the track-B host without a reset. Step (b) is not yet passed: the
submission stopped at the first stale userptr mapping (F26). Nine resets bought a precise negative
result (the console's preamble, filtered, is not what hangs the GPU), a crash journal that
survives, and the rule that any CPU-rewritten IB must be mapped uncached for the GPU.
