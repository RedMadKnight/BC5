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

**Step (b1), run 14** (15:13, same configuration, revalidating sync): **72 of 72 submits OK, no
`EFAULT`, no retry, no reset**, 22 flips, 952 mappings (2.3 GB) at the end. Pass 1 unmapped exactly
one range during the run (`unmap 0x334f30000 +0x420000 (no longer rw anonymous)`, the guest
thread-stack region) before it could reach a BO list. 12 ms per submit at 950 BOs. `dmesg`: nothing.
Journal: `raw/b1-run14-direct.log`.

**Step (b2), run 15** (15:21, `BC5_DIRECT_STAGE=preamble`, no `BC5_DIRECT_DROP_OPS`): **72 of 72
OK, no reset**, 21 flips, 965 mappings. The console's 150-dword preamble now runs with only the
policy's own drops: per submit 12 packets pass — `COND_EXEC`, 3 × `LOAD_CONTEXT_REG` (0x61, one of
19 dwords), 3 × `LOAD_SH_REG` (0x5f, one of 45), 3 × `LOAD_UCONFIG_REG` (0x5e, one of 31),
2 × `WRITE_DATA` — 2 are rewritten (`CONTEXT_CONTROL` → RADV's) and 2 dropped (`PREAMBLE_CNTL`
0x4a, first and last packet). So the AMD gfx10 CP on the BC-250 executes Sony's register-shadow
loads (`LOAD_*_REG` from the game's own tables in guest memory, mapped 1:1) without complaint.
2.5 ms per submit at 198 BOs, 12 ms at 965. `dmesg`: nothing. Journal: `raw/b2-direct.log`.

**Step (c1), run 16** (15:28, `BC5_DIRECT_STAGE=nodraw`, `BC5_DIRECT_DROP_OPS=3c,93,1e`: waits
and atomics left to the soft CP, draws NOP-ed by the filter, compute rings off): **machine reset
10 (the 10th of the day)** after 15 submits. The first three frame DCBs of the game ran on the
GFX ring and signalled their fences — #11 (96 dwords), #12 (3,257 dwords: 324 packets passed,
76 rewritten, 200 dropped, 52 for unmapped operands), #13 (851 dwords) — and #14 (798 dwords:
100 passed, 18 rewritten, 42 dropped) **timed out** after 2.03 s; the kernel's own GPU timeout
then took the machine down. Journal: `raw/c1-direct.log`.

What ran on the GPU in #14 (decoded locally from the journal's `.raw`/`.ib` pair): 17 ×
`LOAD_CONTEXT_REG_INDEX`, 8 × `LOAD_SH_REG_INDEX`, 7 × `LOAD_UCONFIG_REG_INDEX`, 17 × `EVENT_WRITE`
(events 7, 16, 44, 46, 56), 12 × `RELEASE_MEM` (events 4, 20, 40, 45), 9 × `ACQUIRE_MEM`,
8 × `WRITE_DATA`, 7 × `COND_EXEC`, 7 × `CLEAR_STATE`, 6 × `CONTEXT_CONTROL` (rewritten), 2 ×
`SET_BASE`, `SET_UCONFIG_REG_INDEX`, `INDEX_BASE`, `INDEX_BUFFER_SIZE`, 10 × `NUM_INSTANCES`.
Every memory operand was inside a mapping. With addresses masked, every packet signature of #14
also occurs in #12 or #13 except one `ACQUIRE_MEM` (`gcr_cntl` 0x380 instead of 0xc320/0xc3e1).
Two things the filter does not see:

1. **`LOAD_*_REG_INDEX` tables.** The registers a LOAD writes live in guest memory, not in the IB,
   so the register policy (which covers `SET_*` only) never sees them. #12/#13 loaded tables at
   0x908e5f… (eboot data, static) and 0xfe0040068 (driver area); #14 additionally loaded eight
   tables from fresh per-frame heap addresses (0x506e01500…0x506dfe608) whose contents are
   unknown. A privileged or non-existent register written through the CP's LOAD path is the kind
   of thing that halts the ME without a fault — which matches a fence timeout with no page
   fault.
2. **`WRITE_DATA` with `DST_SEL` 0 (register)** to mm 0xc343 (`SQ_THREAD_TRACE_USERDATA_3`, the
   marker register the policy already drops for `SET_UCONFIG_REG`) passed the filter, which only
   checked memory destinations. Now dropped (`FilterStats::reg_write_drops`, mirrored in
   `bc5-agc`).

Changes before the next attempt: the host journals every LOAD table (address, format, count,
first 16 dwords) before the submit; the soft CP skips the memory side effects of packets the GPU
executed (`SubmitResult::executed_offsets`); compute rings gated behind `BC5_DIRECT_RINGS`.

**Step (c1a), run 17** (15:44, `nodraw`, `BC5_DIRECT_DROP_OPS=3c,93,1e,63,64,9f`): **reset 11**,
same place — #11, #12, #13 OK, **#14 timeout** (798 dwords at 0x506802500, byte-identical
structure, only addresses differ between runs). So the LOAD tables are not (alone) what hangs the
CP; the remaining GPU-executed set of #14 is `EVENT_WRITE`, `RELEASE_MEM`, `ACQUIRE_MEM`,
memory `WRITE_DATA`, `COND_EXEC`, `CLEAR_STATE`, `CONTEXT_CONTROL`, `SET_BASE`, `SET_UCONFIG_REG_INDEX`,
`INDEX_BASE`, `INDEX_BUFFER_SIZE`, `NUM_INSTANCES` — all of which #12/#13 also executed. The
journaled tables (`raw/c1a-direct.log`, contents not committed) show what the LOAD path carries:
the driver's context-register shadow (921 dwords of offset/value pairs at 0xfe0040068), an SH
shadow (174), a UCONFIG shadow (57), and per-object tables in the game's heap and data segment.
One table (0x908e5ffc0, 10 pairs) straddled two adjacent 64 KiB mappings and was wrongly treated
as unmapped: the coverage check now merges adjacent mappings.

**Piecewise, run 18** (16:32, `BC5_DIRECT_PIECEWISE=14`, otherwise as c1a): **reset 12**, but with
the answer narrowed to one submission. Submit #14 went to the GPU as 26 pieces
(`raw/piecewise-direct.log`): pieces 0–24 all signalled their fences in 4.5 ms each — among them
`EVENT_WRITE` 7/16/46/44/56, `COND_EXEC` + `CLEAR_STATE cmd 2`, `NUM_INSTANCES`,
`SET_UCONFIG_REG_INDEX` (VGT_INDEX_TYPE = 0x480, index 2), `INDEX_BASE` 0, `INDEX_BUFFER_SIZE`
0xffffffff, two `SET_BASE` (index 1, address 0; one with the compute shader-type header bit), the
full-range `ACQUIRE_MEM` (`gcr_cntl` 0xc3e1) and two `RELEASE_MEM` (BOTTOM_OF_PIPE_TS with the GPU
clock, CACHE_FLUSH_TS with data 1) — and **piece 25, a policy-dropped `SET_UCONFIG_REG`, i.e. an
IB of nothing but NOPs, timed out**. So no packet of #14 hangs the CP by itself: one of the
pieces leaves the CP in a state in which the *next* submission (the kernel's CONTEXT_CONTROL +
INDIRECT_BUFFER + fence framing around eight NOPs) never completes. The arming piece is one of
the 15 real ones above.

**Piecewise with probes, run 19** (16:44): **reset 13**, and the pattern moved: pieces 0–5 and
their NOP probes OK, then piece 6 (a dropped LOAD, NOP-only) timed out — in run 18 the same
stream ran to piece 25. The one real packet executed before both hangs is piece 5: `COND_EXEC`
on 0xfe0040060 whose flag read **0x3 (non-zero, so not skipped)** followed by **`CLEAR_STATE cmd 2`**.
After it the CP stops between 5 ms and ~100 ms later, on a submission of pure NOPs. That also
explains #12/#13: their `CLEAR_STATE` packets sit under the same `COND_EXEC`, and the flag is
raised by `ATOMIC_MEM` packets the soft CP executes only after the fence — zero for the first
DCBs, non-zero by #14 — so #12/#13 skipped their `CLEAR_STATE`s. AMD's drivers emit `CLEAR_STATE`
with cmd 0 (RADV, radeonsi, PAL `PM4_PFP_CLEAR_STATE.cmd`); the console driver uses 1 and 2, whose
meaning on AMD's PFP firmware is unknown (`TODO(verify)`). Journal: `raw/probe-direct.log`.

**Step (c1b), run 20** (17:05, `nodraw`, `BC5_DIRECT_DROP_OPS=3c,93,1e,63,64,9f,12`): **95 of 95
submits OK, no reset**, 59 frame DCBs (up to 3,257 dwords, 176 packets passed each) on the GFX
ring for 90 s of game time, 923 mappings, 12–18 ms per submit. `CLEAR_STATE` confirmed (F27).
Journal: `raw/c1b-direct.log`. Flips 9 (21 in b2): the soft CP's `WAIT_REG_MEM64` 2 s timeouts
(9 here, 19 in b2) pace the game in both modes — a pre-existing soft-CP item, not a direct-mode
regression.

**Step (c2), run 21** (17:12, `nodraw`, `BC5_DIRECT_DROP_OPS=3c,93`: `LOAD_*_INDEX` and `ATOMIC_MEM`
back on the GPU, `CLEAR_STATE` dropped by policy): **98 of 98 OK, no reset**, 62 frame DCBs (one
of 9,774 dwords: 560 packets passed, 259 rewritten, 757 dropped of which 228 for unmapped
operands), 976 mappings. The console's register-shadow loads (context 921 dwords, SH, UCONFIG
and the per-object tables) and its atomics run on the BC-250's CP. Journal: `raw/c2-direct.log`.

Waits, classified per DCB (`waits.py`, c2 and b2 captures): every `WAIT_REG_MEM` (0x3c; 732 /
1,599) targets a label written earlier **in the same DCB** by `WRITE_DATA`/`RELEASE_MEM`, so the
GPU satisfies it itself; `WAIT_REG_MEM64` (0x93) splits into 70 / 154 such "self" waits, 20 / 44
on guest memory written elsewhere (0x400202d40…, the very addresses the soft CP's 2 s timeouts
name) and 10 / 22 on the host heap (KytyPlus's flip labels, unmapped, NOP-ed by the filter). A
wait nobody satisfies is a 10 s kernel reset, so 0x93 stays on the soft CP until the filter can
pass "self" waits only.

**Next.** (c3) `nodraw` with `BC5_DIRECT_DROP_OPS=93` (`WAIT_REG_MEM` on the GPU); then (d) draws.
