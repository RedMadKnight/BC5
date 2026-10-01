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

**Step (c3), run 22** (17:26, `nodraw`, `BC5_DIRECT_DROP_OPS=93`): **97 of 97 OK, no reset**, 61
frame DCBs with their `WAIT_REG_MEM` packets executed by the CP (satisfied by the same DCB's
`WRITE_DATA`/`RELEASE_MEM` labels), 8–12 ms per submit at 933 mappings. Journal: `raw/c3-direct.log`.

**Memory survey before (d), runs 23–26** (17:43–17:56, `maponly`, no submits):

- The guest's rw anonymous VMAs total 13,010 MiB (KytyPlus's direct-memory reservation is one
  merged rw anonymous VMA), 2,171 MiB resident. Mapping whole VMAs is out.
- The game maps **12,406 MiB of direct memory** up front (plus 22 MiB flexible, 100 MiB stacks,
  548 MiB code). Mapping the guest's ranges in full (`BC5_DIRECT_MAP_GUEST_RANGES=1`,
  `Bc5ForEachMappedRange` added to KytyPlus) materialised 11.2 GiB, one 7.8 GiB userptr failed and
  the box crawled: out as well (`hmm_range_fault` populates a userptr BO completely at CS time).
- Render targets: of 55 distinct CB/DB base addresses in the game's context-register tables
  (`rt.py` over the full `LOAD_CONTEXT_REG_INDEX` tables, `BC5_DIRECT_TABLES_FULL=1`), **52 were not
  resident** — the GPU writes them, the CPU never does — so the resident-run mapping would fault
  on the first draw. Fix: the **hint mapper** — before each submit the host scans the IB's
  `SET_CONTEXT_REG` packets and `LOAD_CONTEXT_REG_INDEX` tables for `CB_COLOR*_BASE/CMASK/FMASK/DCC`
  and `DB_Z/STENCIL/HTILE` bases (Mesa gfx10 offsets via the regdb) and maps a 32 MiB window from
  each (`BC5_DIRECT_HINT_MIB`), clipped to the containing rw VMA: 16 hints, +313 MiB in 30 s.

**Step (d), run 27** (17:58, `BC5_DIRECT_STAGE=all`, hint mapper on): the first DCB with draws
(#12, 3,257 dwords, 333 packets passed) **timed out** — and the machine **stayed up**: `dmesg`
shows a GPU page fault from the **SQC** (shader instruction fetch) at 0x908e86000, 8 KiB past the
last rw resident run of the executable's data, then `ring gfx_0.0.0 timeout`, `Ring gfx_0.0.0
reset succeeded`, `device wedged, but no recovery needed`; the emulator went on with the soft CP
(22 flips). A hang inside shader execution is recovered by the kernel's per-ring reset; the
`CLEAR_STATE` hangs froze the CP itself and needed the full reset that takes the box down (F28).
The faulting page is the game's shader code in an `r-x`/`r--` segment (the loader's `mprotect`
after `LoadSegment`), which the sync ignored because it took rw VMAs only. Fix: `r--`/`r-x`
anonymous guest pages are mapped read-only (`AMDGPU_GEM_USERPTR_READONLY` through the raw ioctl,
VA mapping READABLE|EXECUTABLE).

**Step (d), runs 28–33** (18:10–18:28, `BC5_DIRECT_STAGE=all`), one fault class at a time, the
machine up throughout (ring resets only, F28):

| run | change | outcome |
| --- | --- | --- |
| 28 | `KYTY_BC5_ALL_RW=1` (r-x/r-- guest pages kept CPU-writable: read-only userptrs cannot enter a libdrm BO list, see `direct.cpp`) | SQC fault gone; fault at 0x56d8bf000, CB DCC metadata of a target whose base was loaded by an earlier IB |
| 29 | context state accumulated across IBs, `LOAD_CONTEXT_REG` (flat image) parsed too | same fault: the tables of #12 were not mapped yet at scan time (sync throttled to 50 ms; the game writes them right before submitting) — also the reason for the 52 "unmapped" drops per DCB |
| 30 | sync forced on every submit | same fault: #12 sets CB0's base four times (one per pass) and the last table zeroes it; the mapper only looked at the final state |
| 31 | bases evaluated after every register-changing packet | 10 hints, CB0 windows mapped; **TCP fault** (texture fetch) at 0x538a8a000, 1.2 MiB below CB0's base, nothing resident within 32 MiB: a GPU-generated texture |
| 32 | windows 32 MiB below the bases as well; `AMDGPU_INFO_GPUVM_FAULT` read after a timeout; the faulting region (96 MiB) saved to `~/bc5-work/direct-learned.txt` and mapped from the start of every later run; `BC5_DIRECT_REOPEN=1` opens a fresh device after the kernel's ring reset and goes on | fault at 0x532832000 → learned → reopened → **91 more frame DCBs with their draws and dispatches ran on the GPU** (103 of 104 submits OK, 114 hints) |
| 33 | learned region applied from the start | 106 of 107 OK, 68 frame DCBs, one new fault (0x54218c000, TCP) learned; 3.2 GB mapped |

So the game's frames, draws included, execute on the BC-250 from inside the track-B host, with
the mapping set converging by one learned region per run. The emulator window stays black:
KytyPlus's presenter uploads the flip buffer through its own resource tracking (`InvalidateMemory`
on flip is the open item from F21), and the sampled-texture faults show that a complete map of
what a frame reads needs the game's descriptors (T#/V#), not only the CB/DB registers. Journals
of runs 32 and 33: `raw/d-run32-direct.log`, `raw/d-run33-direct.log` (table contents stripped).

**Runs 34–37** (18:35–18:43): with the two learned regions the title screen runs **fault-free**
(124 of 124 and 95 of 95 submits, 79 / 59 frame DCBs, no reopen). The presenter now drops its
cached image of the flip surface before each flip (`InvalidateMemory`, direct mode only) and the
host checksums the display buffer at `sceVideoOutSubmitEopFlip`: **all zero** (0 of 8,160 sampled
dwords non-zero, both buffers, every flip), although draws did target both display buffers
(`hint CB0 0x507410000`, `0x5093f0000`). So the window is black because nothing lands in the
flip surfaces, not because of presentation. The 52 "unmapped" drops per frame DCB were
`RELEASE_MEM` packets with `DATA_SEL` 0 (event and cache flush only, address 0): now recognised
as having no memory operand, they execute — `unmapped 0` in run 37, output unchanged. Next
suspect: the game's compute rings (264 `DISPATCH_DIRECT` per 90 s in the doorbell-ring IBs,
all still emulated by the soft CP, which runs no shaders) — composition, clears and copies of a
modern engine live there. For step (e) the filter now copies every `INDIRECT_BUFFER` target
into the scratch, filters it and rewrites the packet's address, so the ring IBs are inspected
like the DCBs; the soft CP skips their GPU-executed packets too.

**Step (e), run 38** (18:47, `BC5_DIRECT_RINGS=1`): **reset 14**, a CP stall. 32 ring slices went
through — rings of `INDIRECT_BUFFER` packets whose targets the filter copied into the scratch —
including the driver's own small compute IBs (0xfe003a200: 2 dwords, 0xfe00427a0: 55 dwords),
i.e. the first compute work on the GFX ring from the console's queues. Submit #48 (four
`INDIRECT_BUFFER`s, the last to a 1,336-dword **game** compute IB at 0x4002a55c0) timed out and
the machine went down. A survey of 152 such IBs from an earlier capture (`acbhist.py`, run 21):
`SET_SH_REG` to COMPUTE_START_X … COMPUTE_USER_DATA_15, `COMPUTE_DISPATCH_TUNNEL` (0x2e7d) and
the unresolved 0x2e80; `RELEASE_MEM` CS_DONE / BOTTOM_OF_PIPE_TS / CACHE_FLUSH_AND_INV_TS;
`EVENT_WRITE` CS_PARTIAL_FLUSH; `WAIT_REG_MEM64`; `DISPATCH_DIRECT`; and **`DMA_DATA` to and from
GDS** (control 0x46100000 = fill GDS, 0x24300000 = GDS → memory, Mesa `V_411_GDS`): the console's
compute counters live in the global data share, which our VMID does not have. Journal:
`raw/e-run38-direct.log`. Next: (e2) with GDS packets dropped by policy (`gds_drops`), nested
IBs dumped before the submit, and the piecewise mode descending into `INDIRECT_BUFFER` targets;
then a GDS BO on the BO list (`BC5_DIRECT_GDS_KIB`) so the accesses may pass.

**Step (e2), run 39** (19:51, GDS packets dropped): **reset 15**, same place — 48 submits OK,
then the ring slice whose fourth `INDIRECT_BUFFER` is the game's first compute IB (1,336
dwords, now dumped before the submit: `direct-000049-ring-ib3.raw.bin`, not committed). So GDS
is not (alone) what stalls the CP. Decoded, that IB is 225 packets: a "reset compute state"
block (`SET_SH_REG` zeros for COMPUTE_START_X … COMPUTE_USER_DATA_15, `COMPUTE_DISPATCH_TUNNEL`
0x2e7d = 0x4ff, 0x2e80 = 0), `ACQUIRE_MEM` with size 0 and `gcr_cntl` 0xc3a1 / 0x8380, `EVENT_WRITE`
CS_PARTIAL_FLUSH, `RELEASE_MEM` CS_DONE (event index 6) without data, `RELEASE_MEM` BOTTOM_OF_PIPE_TS
with the GPU clock, `WAIT_REG_MEM64` on a label the gfx queue writes (dropped by the self-wait
rule), per-dispatch `COMPUTE_PGM_LO`/`RSRC1`/`RSRC2`/`NUM_THREAD_*`/`USER_DATA_*` then
`DISPATCH_DIRECT` 192×1×1 with initiator 0x41, and `DMA_DATA` fills. Candidates for a CP stall,
none seen on the GPU before: 0x2e7d, CS_DONE/index-6 `RELEASE_MEM`, size-0 `ACQUIRE_MEM`, the
`DMA_DATA` fills. Next: the piecewise mode descending into that IB
(`BC5_DIRECT_PIECEWISE_KIND=ring BC5_DIRECT_PIECEWISE_MIN=1000`), one run names the packet.

**Step (e3), run 40** (20:14, piecewise into the compute IB): **reset 16**, and the packet is named.
The four `INDIRECT_BUFFER`s were descended; in the game's IB, nested pieces 0–17 (the compute
state reset, `ACQUIRE_MEM` size 0, `EVENT_WRITE` CS_PARTIAL_FLUSH, the dropped `WAIT_REG_MEM64`
and markers) and their probes all passed, and **nested piece 18 timed out by itself**:
`RELEASE_MEM` `c0064900 0030e62f 00010000 0 0 0 0 0` — event CS_DONE (47), **EVENT_INDEX 6**, `gcr`
0x30e, DATA_SEL 0, DST_SEL 1, address 0. The same shape with EVENT_INDEX 5 (BOTTOM_OF_PIPE_TS,
CACHE_FLUSH_TS with the same `gcr`) passes throughout steps (c)–(d), and every CS_DONE in the
console's compute IBs is data-less (survey: 120 of 120). Policy: such packets are rewritten to
BOTTOM_OF_PIPE_TS / index 5 (`cs_done_rewrites`), flush bits kept. `TODO(verify)`: why the GFX
ring's ME never completes an index-6 RELEASE_MEM without data (PAL emits CS_DONE with data only).

**Step (e4), run 41** (20:22, CS_DONE rewrite on): the machine **stayed up** through the game's
compute queues — 59 ring slices, 81 of 87 submits OK, the game's 1,336-dword compute IBs with
their dispatches executed by the CP. Three timeouts were TCP faults of compute shaders (0x53ac48000,
0x55e08a000, 0x553ba3000, learned), a fourth had no fault address (an instance of the same IB;
most likely a compute shader spinning on a label another queue writes — the kernel's ring reset
recovered it, so the host now reopens after any timeout). Flip buffers still zero; only 4 flips
in 90 s because every reopen costs 12 s.

**Run 42** (20:25, reopen after any timeout, five learned regions): 91 of 97 OK, **no page fault
at all**, three timeouts without a fault address in instances of the same compute IB that pass
at other times, each recovered by the kernel's ring reset and the host's reopen (12 s apiece;
3 flips in 90 s). A compute shader spinning on a label that the gfx queue writes later cannot
finish when both queues are serialised on one ring in doorbell order. The kernel does expose
**four compute rings** on the BC-250 (`amdgpu_query_hw_ip_info`: COMPUTE 10.0, rings 0xf,
`comp_1.0.0`…`comp_1.3.0` in `dmesg`); F6 only says RADV leaves them unused. `dispatch-min --ip
compute` is the test.

**Run 43** (20:40, `dispatch-min --submit --ip compute --ring 0`): **reset 17** — the kernel's
compute ring `comp_1.0.0` took the machine down on the buffer-fill dispatch that passes on the
GFX ring (F31). The console's queues stay serialised on the GFX ring; cross-queue waits move
to the host (IB split at the wait, CPU wait on the label, submit the rest).

**Runs 44–45** (20:46–20:48, doorbell-ring targets submitted directly as `acb` IBs, cross-queue
waits satisfied on the CPU before the submit): run 44 split each IB at such a wait and paid for
it — two **SQC faults at 0x800000400000**: between the pieces of one IB the ring runs other
processes' submissions, which leave their own compute SH state behind, and the dispatch after the
split ran with a foreign `COMPUTE_PGM_LO`. Run 45 waits up front and submits whole IBs: 150 of
156 OK, 122 compute IBs, no page fault, 19 of 25 CPU waits satisfied at once, 6 timed out (2 s),
and three timeouts without a fault address, all in instances of the game's 1,336-dword compute
IB — a compute shader that never finishes (its inputs not ready after a timed-out wait, or a
label it spins on). 3 flips in 90 s.

**Run 46** (20:51, compute IBs allowed 10 s of CPU wait): unchanged — 6 waits still time out.
The journal plus the raw dumps say why: the label a compute IB waits for at its offset 115
(e.g. 0x400202d40 in #83) is written by the **next compute IB** (#84, `RELEASE_MEM` at its end) —
a different compute queue of the game. On the console queue A blocks on its wait while queue B
runs and writes the label; the host's doorbell consumer served the queues one at a time on one
thread and blocked on A, so B never ran. The consumer must not block: a queue whose next IB has
an unsatisfied cross-queue wait keeps its read pointer, the other queues are served, and it is
retried on the next poll (deadline 10 s, then it goes anyway).

**Runs 47–48** (20:55–20:57, non-blocking doorbell consumer): a queue whose next IB has an
unsatisfied cross-queue wait keeps its read pointer and is retried on the next poll — three
deferrals of queue 2/0/0/0x21, resolved after 3–7 s (the writer queue is slow because the whole
game is). 156 of 160 submits OK, 124 compute IBs, but still three stalls without a fault address
in compute IBs and four CPU-wait timeouts; flip buffers zero, 3 flips. Remaining suspect for a
shader that never finishes: **GDS** — the compute shaders' ordered-append counters live there,
the VMID has no GDS partition and the `DMA_DATA` fills/reads of GDS are dropped by policy.
Next: a 64 KiB GDS BO on every BO list (`BC5_DIRECT_GDS_KIB=64`, kernel programs the VMID's GDS
base/size) with the GDS packets passing.

**Run 49** (21:03, `BC5_DIRECT_GDS_KIB=64`, GDS packets passing): **reset 18**, but with news. The
64 KiB GDS BO on the BO lists works: 118 compute IBs with their `DMA_DATA` fills and reads of GDS
ran (141 of 144 submits OK, no CPU-wait timeout before the end). The reset came in a **gfx** DCB
(#143, 9,891 dwords) that is packet-for-packet identical to instances that passed in runs 45–48,
except that its two GDS `DMA_DATA` (0xc6106000 fill → GDS, 0xa4306000 GDS → memory) now passed:
both carry **CP_SYNC** (bit 31), unlike the compute queues' (0x46106000 / 0x24306000). Policy:
GDS DMAs with CP_SYNC are dropped even with a GDS allocation. The logs of the run (other than
the journal) were lost with the reset. Journal: `raw/e9-run49-direct.log`.

**Run 50** (21:11, GDS allocation, sync GDS DMAs dropped): **reset 19**, the very same gfx DCB
(#143, 9,891 dwords, 141 of 144 submits OK before it, no shader stall). With the GDS partition
present something else in that DCB — or in its shaders — reaches GDS. Journal:
`raw/e10-run50-direct.log`.

Decoded, #143 has no CP-level GDS access left (its two GDS `DMA_DATA` are NOPs, no `COPY_DATA`,
no `WRITE_DATA` to GDS, no GDS UCONFIG registers), so with a GDS partition it is the DCB's
**shaders** that hang: ordered-append (`ds_ordered_count`) needs an OA allocation the console's
system provides; without any GDS partition those instructions were no-ops. The kernel offers
per compute partition 65,536 bytes of GDS, **16 OA counters and 64 GWS resources**
(`amdgpu_query_gds_info`), and `AMDGPU_GEM_DOMAIN_OA`/`_GWS` allocations succeed; on the BO list
they set the VMID's OA/GWS base and size (as RADV does for NGG streamout). Next: GDS 64 KiB +
OA 16 + GWS 64 (`BC5_DIRECT_OA=16 BC5_DIRECT_GWS=64`).

**Run 51** (21:50, GDS 64 KiB + OA 16 + GWS 64): **reset 20**, the same DCB #143 (142 of 144 OK
before it, no stall). A GDS partition of any shape makes this game's gfx shaders hang; the
partition is off for good (ADR 0005 xvii). The compute queues' GDS counters get a **64 KiB shadow
in memory** instead: the filter redirects their `DMA_DATA` (GDS→memory, fill→GDS) and
`WRITE_DATA` to shadow + GDS offset (`gds_rewrites`), so the values the game reads back are
consistent; the shaders' own GDS instructions stay no-ops as in runs 45–48.

**Run 52** (22:01, GDS shadow, no partition): back to the runs 47–48 level — 156 of 160 OK, three
compute-shader stalls, no reset; the shadow rewrites run without incident. So the gfx shaders
need *no* partition and the compute shaders need one: since the kernel programs the VMID's
GDS/OA/GWS per job from that job's BO list, the next attempt attaches the partition only to
the compute IBs' submissions.

**Run 53** (22:05, partition on the compute submissions only, shadow for gfx): **reset 22**, DCB #143
again (142 of 144 before it). The pattern across runs 45–53: #143 passes whenever the compute
shaders ran *without* a real GDS (45–48, 52) and hangs whenever they ran *with* one (49–51, 53),
whatever the gfx DCB's own partition. So it is not the partition at draw time but what the
compute queues produce with real GDS counters: non-zero object/draw counts that the DCB's
`DRAW_INDEX_INDIRECT` / `DISPATCH_INDIRECT` (22 and 88 per capture) take from memory. With zero
counters nothing was drawn (the empty flip buffers) and nothing hung; with counters that are
non-zero but not the console's (no ordered-append state) an indirect draw can ask for a
gigantic index count and keep the CP busy past the kernel's 10 s, which ends in the full reset.
Test: run 53's configuration with the indirect draws and dispatches dropped
(`BC5_DIRECT_DROP_OPS=24,25,16`).

**Run 54** (22:41, run 53's configuration + `BC5_DIRECT_DROP_OPS=24,25,16`): **confirmed** — 232 of
234 submits OK, 55 frame DCBs (the 9,891-dword ones included), 146 compute IBs on real GDS,
**no stall, no reset**, 9 flips in 90 s (three times the earlier runs). The indirect draws and
dispatches, fed by the compute queues' counters, are what kept the CP busy. Flip buffers still
zero: those draws are the scene. Next: journal every indirect argument block before the submit
(`SET_BASE` index-1 base + offset) and NOP the ones with absurd counts
(`BC5_DIRECT_INDIRECT_MAX`), then let the sane ones draw.

**Run 55** (23:20, indirect draws and dispatches back, argument survey and clamp): **232 of 234 OK,
no stall, no reset**, 9 flips. Of 40 indirect packets, 28 were NOP-ed for absurd arguments —
`DISPATCH_INDIRECT` with x = 1,938,748,700, 447,274,665, 3,483,086,075 … (`raw/e15-run55-direct.log`)
— and the 12 sane ones were 1×512 dispatches and draws with count 0. The counters the compute
queues read back from GDS are garbage: the shaders count with ordered-append, whose state the
console's system initialises; an OA allocation alone does not reproduce it. Nothing is drawn,
so the flip buffers stay zero. This is the open problem at the end of the day.

**Run 56** (23:36, `BC5_DIRECT_OA_ENBL=1`): stall-free again (231 of 234), same 28 of 40 indirect
packets dropped — and the numbers tell the story: the dropped `DISPATCH_INDIRECT` counts are
847,009,686, 687, 688 … (+1 per frame) and continue run 55's 847,009,678: GDS memory is not
cleared between processes and **the counter is never reset**. The reset is the gfx queue's
`DMA_DATA` fill → GDS with CP_SYNC — dropped since run 49 because with CP_SYNC it stalled the CP.
That also re-reads runs 49–51: the gfx-time partition was not the problem, the giant indirect
draws from the un-reset counters were (no clamp yet). Next: the partition on every submission,
the gfx queue's GDS DMAs with CP_SYNC stripped instead of dropped, the clamp kept.

**Run 57** (23:43, partition on every submission, gfx GDS DMAs without CP_SYNC): stall-free
(232 of 234) — so a partition at draw time is fine after all — but the counts still grow by one
per frame (…694 → …700). Either `ds_ordered_count` works on a GDS address the game's fills do
not cover, or the CP's fills do not land. Next: a GDS snapshot (host DMA of the 64 KiB into the
shadow, non-zero dwords journaled) after compute IBs.

**Run 58** (23:49, GDS snapshot after a compute IB): the host's DMA of GDS into the shadow copied
only **3,584 bytes** (896 dwords; the rest of the 64 KiB kept the probe pattern), the content is
non-zero everywhere in that range (0x1196f59f, 0xd93fc4db, …), and GDS[0x4], which the game's
gfx queue fills with 0 every frame, holds 0xd93fc4db — the fill never landed. Either the CP's
DMA to/from GDS does not do what the packet says on this ring, or the partition the CP sees is
3.5 KiB. A GDS self-test at init (fills at 0x100 and 0xf000, WRITE_DATA at 0x200, snapshots
before and after, dumped to files) decides.

**Run 59** (23:54, GDS self-test): the CP does write GDS — the host's `DMA_DATA` fill at 0x100 and
`WRITE_DATA` at 0x200 both landed (`gds-snapshot-000/001.bin`), a GDS read reaches ~3.7 KiB —
and the game's fills never did because of a **filter bug**: `memory_operands` treated DMA_DATA's
GDS selector (1) as a memory selector (the memory ones are 0 and 3), so every GDS fill and
read-back of the game was NOP-ed as "unmapped" before any GDS rule ran; the counters were never
reset and never read through the CP. Fixed with a test. `TODO(verify)`: why a GDS read stops at
~3.5–3.7 KiB of the 64 KiB partition.

**Run 60** (23:57, the fixed filter): the game's GDS fills land (`[0x4] = 0`, `[0xc68] = 0` after a
frame), **no indirect packet dropped** — the counts are 1 (28 `DISPATCH_INDIRECT` 1×1×1, 8
`DRAW_INDEX_INDIRECT` count 1 / 512 instances) — 232 of 234 submits, no stall. The flip buffers are
still zero, so the next question is whether any render target receives pixels: at flip the
host now also samples every CB/DB base the hint mapper saw.

**Run 61** (2026-10-01 00:01, render targets sampled at flip): the GPU **draws** — the scene's colour
target 0x519df0000 and its depth buffer 0x527430000 are fully non-zero after a frame, HTILE and
CMASK/DCC metadata partially, several targets untouched — and the flip buffers stay zero. The
pass into the flip buffer (found in the frame DCB with the surveyed tables) is a plain
`DRAW_INDEX_AUTO` of 3 vertices (a full-screen triangle) with sane state: CB0 base 0x5093f0000,
3840×2160, `CB_TARGET_MASK` 0xf, full-screen scissors, depth test off, no blend, no DCC. Why it
leaves nothing behind is the open question (the PS5's `SubmitEopFlip` semantics — a flip at the
EOP of the *next* submission, presented immediately by the host — is one candidate for the
sampling and the presentation, not for the memory being zero).

Decoded further: the stages are NGG pass-through (`VGT_SHADER_STAGES_EN`: PRIMGEN_EN,
PRIMGEN_PASSTHRU_EN), and **`VGT_PRIMITIVE_TYPE` reaches the GPU only through
`LOAD_UCONFIG_REG_INDEX` tables** (values 7, 6, 4, 1 in the survey) — never through
`SET_UCONFIG_REG_INDEX` index 1, which is how RADV and radeonsi set it on gfx10 so that the PFP
forwards the type to the GE. If the GE never learns a primitive type, no draw rasterises, the
"fully written" scene targets are clears, and the flip pass leaves nothing — consistent with
everything seen. Test: a prologue with `SET_UCONFIG_REG_INDEX` index 1 = TRILIST before every
gfx IB (`BC5_DIRECT_PROLOGUE_PRIM=4`); the flip pass's full-screen triangle is a triangle list.

**Run 62** (00:09, `BC5_DIRECT_PROLOGUE_PRIM=4`): no change — flip buffers zero, the flip-buffer CB
targets 0/1024 after every frame. The primitive-type prologue is not what the flip pass lacks.
Next: tell clears from rasterised content in the sampled targets (distinct values, min/max).

**Run 63** (00:17, distinct values per target): **no draw rasterises.** Every colour target holds
exactly one value (0x38003800, an FP16 clear colour, or 0), every depth buffer one (1.0f or
0xffffffff), and only the metadata (HTILE, CMASK, DCC) shows 2–8 values — clear patterns. The GPU
runs the game's clears and compute, the NGG pass-through geometry pipeline leaves no pixel, so
the flip pass's full-screen triangle is one of many draws that produce nothing (F33).

**Run 64, `draw-min --submit`** (00:33): phase-3 task 2 — libdrm's gfx10 memset draw (RectPosTexFast
VS, constant PS, one `DRAW_INDEX_AUTO`) through the very direct path (anonymous memory as 1:1
userptrs, policy filter, scratch, GFX ring): **16,384 of 16,384 bytes = 0x33**, the 32×32 target
fully drawn, 0.05 ms. Draws work in this model; the game's state or shaders are what differs.
The console's context-register image (`LOAD_CONTEXT_REG` from 0xfe0008000) covers
0x0–0xd6, 0xd8–0x1e7, 0x1f5–0x1f8, 0x1ff–0x29c, 0x2a0–0x2a1, 0x2a3, 0x2a5–0x2ea, 0x2f5–0x3c7:
it skips `PA_SC_TILE_STEERING_OVERRIDE` (0xd7) and a few other ranges the console's system owns;
on the BC-250 those stay whatever the context bank held, because the game's `CLEAR_STATE` is
dropped (cmd 1/2 hang). The libdrm test writes 0xd7 itself. Next: `CLEAR_STATE` rewritten to
cmd 0 (the kernel's clear state, as RADV does per IB) and the chip's tile-steering value in a
prologue.

**Run 65** (06:04, `CLEAR_STATE` → cmd 0, tile steering 0x122000 in a prologue): no change, no
hang. The targets stay single-valued. Next suspect from the SH tables: `SPI_SHADER_PGM_RSRC4_PS` =
0x3 and `RSRC4_GS` = 0x1 (narrow CU enables, loaded by table, outside the policy's CU-mask rewrite
which covers `SET_SH_REG` only); the BC-250's active CUs differ from the console's.

The CU enables are not it (RSRC3 = 0xffff everywhere; the kernel's active CUs 0–5 per SH cover
the narrow RSRC4 values). Mesa does use NGG on gfx1013 and, for NGG, programs `GE_PC_ALLOC` =
OVERSUB_EN | NUM_PC_LINES(pc_lines/4 − 1) with pc_lines = 1024 for GFX1013 (`ac_gpu_info.c`),
i.e. 0x100ff; **the game's init table loads `GE_PC_ALLOC` = 0** — another register the console's
system owns. With no position-cache lines the NGG stage cannot export primitives: clears and
compute run, draws leave nothing. Test: `BC5_DIRECT_PROLOGUE_UCONFIG=260:100ff`.

**Run 66** (06:21, `GE_PC_ALLOC` = 0x100ff in a prologue): no change. Single-register guesses are
exhausted (primitive type, `CLEAR_STATE`, tile steering, `GE_PC_ALLOC`). Next: the pass itself,
standalone — `draw-min` extended to replay the game's flip pass from the surveyed tables and the
dumped shaders, in variants (our draw + the game's context image; the game's NGG GS with our
PS; the game's pass with our target) in one run, so a bisection costs one go-ahead.

**Run 67, `draw-min --pass`** (06:40, the flip pass replayed standalone from the surveyed tables
and dumped shaders): A (libdrm control) and B (control after the game's 921 context registers)
both **draw**; C–G (the game's NGG ES program and SH/UCONFIG state, our 3840×2160 target, libdrm's
constant PS; plus `GE_PC_ALLOC`, tile steering, indexed primitive type) all end in an **SQC (data)
fault at 0x507405000 / 0x5034f5000** — the ES program runs and loads its inputs through the GS
user-data pointers (SH 0x2c8c…: 0x5034f55c0, 0x5034f5660, 0x5034ff118, 0x5074050f0), game
buffers the standalone replay did not have. So the game's context image is harmless and its NGG
stage executes; the replay now needs those buffers (the host dumps what the user-data registers
point at, `draw-min` loads them at their addresses) to see whether the pass draws when isolated.

**Runs 68–69** (06:45–06:55): the replay with the captured buffers still faults at 0x507405000 — that
page was never dumped because it is **not resident in the game**: nothing the CPU does ever
writes it, no CP packet in any captured IB targets it, and 36 draws name it in different
user-data slots, so it is most likely the driver's zero page for unused resource slots. Aliases
were ruled out by measurement (`BC5_DIRECT_RANGES_DUMP`: 68 direct ranges, 12.4 GB, no two share
a physical offset; the block is "GpuGarlicMemory" at 0x500000000), and KytyPlus's backing-store
transfers already follow the anonymous views. Next: measure instead of guess —
`SAMPLE_PIPELINESTAT` before and after every frame DCB (`BC5_DIRECT_PIPESTATS`), the deltas of IA
vertices, VS/GS invocations, clipper primitives and PS invocations show where the game's
geometry disappears.

**Run 70** (06:55, `BC5_DIRECT_PIPESTATS=1`, journal `raw/e26-run70-direct.log`): **the game's
draws do rasterise** — run 63's reading was wrong. `SAMPLE_PIPELINESTAT` before and after every
frame DCB (233 submits, no stall):

| DCB (dwords) | IA verts | IA prims | VS | clipper prims | PS invocations | CS invocations |
|---|---|---|---|---|---|---|
| 9,774 / 9,891 (the frame) | 47 | 5 | 15 | 5 | 2,073,600 or 3,326,976 | ~6.7 M |
| 2,647 | 9 | 3 | 9 | 3 | 2,073,600 or 3,326,976 | ~1.3 M |
| 798 / 1,248 | 9 | 3 | 9 | 3 | 0 | 0 / 36,864 |
| 851 | 0 | 0 | 0 | 0 | 0 | 81,920 / 122,880 |

2,073,600 is one 1920×1080 pass (or a quarter of 3840×2160), 3,326,976 adds a 1152×1088 one. A
frame is five primitives: at this point the game draws a handful of full-screen passes, and
single-valued colour targets are what such passes leave. The display buffers still sample 0/8160.

**Run 71** (07:10, `raw/e27-run71-direct.log`): KytyPlus's anonymous views (`KYTY_BC5_ANON_BACKING`)
were re-created with `mmap(MAP_FIXED)` on every protection change, which silently replaced
written pages by zero pages; they are now re-protected with `mprotect` (and unmapped to
`PROT_NONE` the same way). Same counters as run 70, same zero display buffers: not the cause.

**Run 72** (07:12–07:25, three `maponly` captures, nothing submitted): what the flip pass reads, and
why a frame takes four seconds.

- The flip pass's vertex streams: the table at 0x5034f5660 (GS user data) holds two buffer
  descriptors, 0x507406360 and 0x507406370, stride 24, three records. A probe
  (`BC5_DIRECT_PROBE_VA`, `/proc/self/pagemap`) finds the page present before submission #0 with a
  full-screen triangle, (−1,−1) (3,−1) (−1,3), w = 1, plus texture coordinates. The geometry is
  sound; the non-resident page 0x507405000 of runs 67–69 is a different slot.
- Swap: the box has a 7.4 GiB zram device, and `mincore()` reports a swapped-out page as not
  resident, so the resident-run mapper would skip data the CPU wrote. The mapper now also takes
  pagemap bit 62 (swapped; Linux `Documentation/admin-guide/mm/pagemap.rst`); the journal counts
  such pages. In these runs: 0. Not the cause, a hole closed.
- Every frame sat out **two 2 s timeouts** (runs 54–71: nine flips a minute):
  1. *The flip label.* The frame DCB ends with a `RELEASE_MEM` that writes 1 to the buffer's flip
     label (host memory handed out by `sceVideoOutGetBufferLabelAddress`; unmapped on the GPU, so
     the soft CP writes it) and, before its flip pass, waits (opcode 0x93, the 64-bit
     `WAIT_REG_MEM` this stream uses: flags, address, 64-bit reference, 64-bit mask, poll
     interval) for that label to be 0. On the console VideoOut clears it when the flip has
     happened; the host never did. Fixed: cleared at `SubmitEopFlip`, and at the wait if still set.
  2. *A two-label handshake between the compute queue and the frame DCB.* The frame's compute IB
     (1,336 dwords) runs its dispatches, writes label L1 at +1275, waits on label L2 at +1287,
     then only signals (two `RELEASE_MEM`, markers). The frame DCB waits on L1 at +115 and writes
     L2 at +1431. The host served a compute IB only when all its waits were satisfied and waited
     on the CPU before a DCB went as a whole: the compute IB could not go before the DCB (L2) and
     the DCB waited 2 s for L1, then ran **without that frame's compute results**; the compute IB
     followed afterwards. Fixed: a compute IB is split at an unsatisfied wait when everything
     after it is "light" (NOP, markers, `RELEASE_MEM`, `EVENT_WRITE[_EOP]`, `WRITE_DATA`, waits,
     `ACQUIRE_MEM`): the head goes at once, the tail when the wait is satisfied. Run 44's
     objection to splitting (foreign SH state between pieces) does not apply to a tail that
     neither sets nor uses SH state.
- With the label fix alone (no GPU, 60 s): 11 flips instead of 7; the L1 waits still time out in
  `maponly`, where no head is submitted.

So after ~9 frames a minute, each computed on stale inputs, a black display buffer is not
evidence against the pipeline: the game has barely started. Whether the flip pass writes black
or nothing is the next measurement (`BC5_DIRECT_FLIP_PREFILL`: a pattern at the sample points
after each flip — it stays if nobody writes the buffer, it turns 0 if the pass writes black).

**Verdict (2026-10-01, 00:20).** Steps (a)–(c) passed; (d) and (e) run the game's frames, draws,
dispatches and both queue types on the BC-250 stall-free (runs 54–63: 230+ of 234 submits, no
reset), with GDS counters reset and read back correctly since the DMA-selector fix. G3's image is
not reached because rasterisation produces nothing at all. Twenty-two resets, 63 runs. Next,
in order: (1) phase-3 task 2 as originally planned — a minimal triangle through `Device::submit`
(libdrm `amdgpu_test` gfx10 shaders, RADV-style state) to prove draws work in this model, then
bisect the game's state against it (NGG pass-through, `GE_CNTL`, ring sizes, CU masks, index
type bits 0x480); (2) `ORDERED_APPEND_ENBL` re-test with the fixed filter (counts of 1 are
suspicious); (3) the kernel lockup timeout (boot parameter); (4) presentation and 36/40.

**Run 73** (07:31, GPU, the wait fixes plus `BC5_DIRECT_PIPESTATS=1 BC5_DIRECT_FLIP_PREFILL=1`,
journal `raw/e28-run73-direct.log`): 325 submits, 321 OK, no machine reset (one recoverable SQC
fault at 0x507405000 with a ring reset). **No CPU wait timed out** (71 satisfied, 15 compute IBs
split at their trailing wait), 14 flips instead of 9. The prefill answers run 72's question: at
every later flip of a buffer the pattern is intact, 8160/8160 — **the flip pass writes nothing**,
not black. And the frame DCB's totals do not add up: it holds 22 draws (64 vertices), the
counters say 47 IA vertices, 5 primitives, 15 VS invocations.

The arithmetic, from the DCB's own tables (`BC5_DIRECT_TABLES_FULL` capture): the primitive type
(UCONFIG 0x242, loaded per draw through opcode 0x64 tables) is 7 (rect list) for four draws, 4
(triangle list) for one, 6 (triangle strip) for sixteen, 1 for a zero-instance point draw.
5 primitives and 15 VS invocations are five three-vertex draws; the other sixteen contribute
exactly two IA vertices each (15 + 32 = 47) and no primitive — **a three-vertex strip that
loses one vertex**. The frame enables primitive restart (`VGT_MULTI_PRIM_IB_RESET_EN` = 1 at +85,
UCONFIG 0x24b) and sets the restart index (context 0x103) to 0xffffffff at +80; a restart index
of 0 cuts vertex 0 of every auto-index strip. And the index is 0 again after the first of the
driver's internal draws:

```
+1719 CONTEXT_CONTROL 0x00000000 0x80018001   shadowing of context registers off
+1722 CLEAR_STATE 1                           push_state
+1724 LOAD_CONTEXT_REG_INDEX 0xfe0040068, 921 the driver's default state (0x103 = 0)
      ... the internal draw's own tables, DRAW_INDEX_AUTO (rect list) ...
+1758 CONTEXT_CONTROL 0x00000000 0x80018003   shadowing back on
+1783 CLEAR_STATE 2                           pop_state: the game's context registers return
```

(`PFP_CLEAR_STATE_cmd_enum`: 0 clear_state, 1 push_state, 2 pop_state, 3 push_clear_state — PAL,
`src/core/hw/gfxip/gfx9/chip/gfx9_plus_merged_f32_pfp_pm4_packets.h`.) The console's CP keeps
the context registers in shadow memory and pop_state brings them back. amdgpu sets up no CP
shadowing on gfx10; cmd 1/2 stall the CP here (F27), so the policy rewrites both to cmd 0, the
kernel's clear state. After each internal draw (four per frame DCB, two or three in the smaller
ones) the game is left with default context state plus whatever its next pass reloads: no
restart index, and every other context register a later pass relies on without reloading.

**Fix (no GPU yet):** `bc5::state_stack::Tracker` (backend, unit-tested) follows the context
registers an IB sets — `SET_CONTEXT_REG`, `LOAD_CONTEXT_REG`, `LOAD_CONTEXT_REG_INDEX` tables read
from the 1:1-mapped guest memory —, snapshots them at an unconditional push and replaces an
unconditional pop by `SET_CONTEXT_REG` packets restoring the snapshot; the main IB may grow, the
device lays out the nested copies behind the grown IB. Conditional `CLEAR_STATE`s (inside a
`COND_EXEC` range: the DCB's opening "pop if a clear was interrupted") stay with the filter.
`Device::set_state_stack`, host knob `BC5_DIRECT_STATE_STACK=1`. Dry run on real frames
(`maponly`, capture 07:47): the 9,774-dword frame DCB has 4 pushes and 4 pops, each pop restores
921 registers (the IB grows to 13,522 dwords), all 40 tables readable, the restart index tracked
as 0xffffffff. Also new: `BC5_DIRECT_DRAWSTATS=<min dwords>` — the dropped pass markers of a DCB
become `SAMPLE_PIPELINESTAT` packets (`FilterOptions::stat_sample_va`), so the counters are read
per marker-delimited section.

**Verdict update (2026-10-01, 07:30).** Correction to the verdict above and to F33: rasterisation
works (run 70: 2.07–3.33 M PS invocations per frame DCB). The frames ran at ~9 a minute and on
stale compute results because of two unresolved waits (run 72), both fixed in the host; the fixes
need a GPU run (next: run 73, with pipeline statistics and the display-buffer prefill).

**Verdict update (2026-10-01, 08:00).** Run 73: the wait fixes work (no timeouts, more frames).
The image is missing because the console CP's context-state stack (`CLEAR_STATE` push/pop around
the driver's internal draws) is not available on the BC-250 and our rewrite to the kernel's clear
state wiped the game's context registers four times per frame; its triangle strips — the flip
pass among them — then lose a vertex to a primitive-restart index of 0. The emulation is written
and dry-run; next: run 74 (per-section counters, baseline) and run 75 (`BC5_DIRECT_STATE_STACK=1`).

**Run 74** (07:53, GPU, `BC5_DIRECT_DRAWSTATS=9000`, no state stack; `raw/e29-run74-direct.log`):
the per-section counters confirm run 73's arithmetic by measurement. In the frame DCB the strip at
+779, before the first push, draws (3 IA vertices, 1 primitive, 2,073,600 PS invocations); the
rect-list draws inside the brackets draw; **every draw after the first pop counts 2 IA vertices
and no primitive** — the triangle list at +1938, the strips at +3478, +5950 … +8142 (ten of them
in one section: 20 vertices, 0 primitives) and the flip pass. 322 submits, 319 OK, no stall.

**Run 75** (07:55, GPU, the same plus `BC5_DIRECT_STATE_STACK=1`; `raw/e30-run75-direct.log`):
**the game's passes draw.** 57 IBs had pushes and pops (the frame DCB: 4 pops, 921 registers
each). Per section every draw now has all its vertices and one primitive each; the ten-draw
section makes 8,332,656 PS invocations, and **the flip pass 8,294,400 = 3840×2160**. A
zero-instance point draw at +4575 becomes 512 points, 5 past the clipper (its instance count comes
from somewhere not yet understood; harmless here). The frame DCB totals 533 primitives and
36.6–41.6 M PS invocations instead of 5 and 3.3 M. The display buffers are written from the third
flip on (8100–8160 of 8160 samples non-zero, the prefill pattern gone from the visible area; the
60 samples that keep it are the 16 padding rows). 320 submits, 316 OK, no CPU-wait timeout, no
ring timeout, no reset. The sampled sum is the same at every later flip: a static picture.

What the picture is could not be read from this run: the only screenshot (30 s) predates the
first drawn flip, and the flip target is not linear — `CB_COLOR0_INFO` 0x8824 (2:10:10:10 UNORM,
COMP_SWAP 1), `CB_COLOR0_ATTRIB3` 0x4dc6c000 (swizzle mode 27, 64KB_R_X), 3840×2160 — so a raw
dump needs de-tiling. Next: a longer run with screenshots after the first drawn flip and raw
dumps of the display buffer (`BC5_DIRECT_FLIP_DUMP`), no prefill.

**Verdict update (2026-10-01, 08:10).** F35 confirmed on the GPU: with the context-state stack
emulated the game's strips, its full-screen passes and its flip pass rasterise, and the display
buffer is written every frame. The state stack is now on by default
(`BC5_DIRECT_NO_STATE_STACK=1` turns it off). G3 needs the picture itself on screen: next run.

**Run 76** (08:48, GPU, 75 s, state stack on by default, `BC5_DIRECT_FLIP_DUMP=3`, no prefill;
`raw/e31-run76-direct.log`): 350 submits, 345 OK, 20 flips, no stall. The display buffer holds the
same picture at every drawn flip (the raw dumps of flips 3 and 15 are identical): 54 distinct
values, all grey (R = G = B, 10 bits each, alpha 3), 0…52 of 1023, 20 % exactly zero and the rest
spread evenly, every 64 KiB block with the full set — **black with grain**. The emulator window
shows it as a near-black textured surface. The game's own log says why there is no more to see
yet: it is still loading (level documents arriving one by one, its room-load thread waiting) and
its frames take ~3.3 s.

The 3.3 s: five game threads wait on event queues the game names `GpuDevice::EopEq`, registered
for `EVFILT_GRAPHICS` ident 0, and **every such wait times out** (77 in this run, five per
frame); the host fired only idents 0x40 (gfx EOP) and 0x46/0x48 (compute). Change: every gfx-queue
EOP interrupt also fires ident 0 (`TODO(verify)`: which interrupt the console maps to it; the
waiters re-check their labels as they do after the timeout). Without a GPU (`maponly`, 60 s): 38
ident-0 events delivered, 4 timeouts left instead of ~50. `BC5_GC_NO_IDENT0=1` turns it off.

**Verdict update (2026-10-01, 08:55).** The picture the game presents arrives on the BC-250's
display buffer through the direct path: the game's command buffers and shaders, untranslated, the
frame's passes and the flip pass all rasterising. What it presents during these first 20 frames
is its loading-time black with grain. G3 as "a recognisable image" needs the game to get past
loading: next, run 77 with the ident-0 events (faster frames) and a longer run.

**Run 77** (08:55, GPU, 165 s, ident-0 events; `raw/e32-run77-direct.log`): 622 submits, 616 OK,
37 flips, no machine reset; two recoverable shader faults (0x524556000 learned; 0x567ff0000 in the
run's last submission). The `GpuDevice::EopEq` waits now receive their events (4 timeouts left
instead of five per frame) — **and the frames are no faster** (KytyPlus's title bar: 0.28 fps).
The picture is the same black with grain throughout. The run's last submission is a frame DCB of
a new shape (10,440 dwords): the game is moving on, slowly.

Where a frame's 3.5 s go, as far as this run's journal tells: the forced mapping sync was 51 ms
per submission (measured afterwards without a GPU, `BC5_DIRECT_TIMING=1`), 40 ms of it the
pagemap read added in run 72 — 17 submissions a frame, most of a second. Fixed: the pagemap is
read only while the process has pages in swap (`VmSwap`), the sync is back to 11–16 ms. Submits
and fences: 12 s in the whole run; CPU waits: 3.8 s. That leaves about two thirds of the time
outside the host's submission path — the next run journals a timeline (`BC5_DIRECT_TIMING=1`:
every submission, CPU wait and flip with its time).

**Run 78** (09:08, GPU, 135 s, `BC5_DIRECT_TIMING=1`; `raw/e33-run78-direct.log`): 594 submits,
574 OK, 36 flips, the same picture, no machine reset. The timeline of a 3.0 s frame: the sync is
11 ms now, the submit and its fence ~17 ms, no CPU wait takes time — and **the host's own
submission path takes the rest**: 1,289 ms for the frame DCB, 300–440 ms for each of the
2,647/798/1,248-dword DCBs, ~23 ms for the small ones. It is the crash journal: every line was
written with open/append/`fsync`/close, the frame DCB alone journals a hundred table lines, and
each IB was dumped in three `fsync`ed files. That design dates from the runs that ended in
machine resets; it has been the frame rate's ceiling since run 54.

Change: `direct.log` is synced once per submission, right before the IB goes to the GPU (which
makes every earlier line durable); lines and IB dumps in between are written without `fsync`.
`BC5_DIRECT_JOURNAL_SYNC=1` restores the old behaviour for chasing a hang. Without a GPU
(`maponly`, 60 s): 27 flips instead of 11, a frame every 2.17 s of which 2.0 s are the
`maponly`-only label timeout.

**Run 79** (09:15, GPU, 135 s, journal synced once per submission; `raw/e34-run79-direct.log`,
reduced — table, map and per-submission sync lines left out to stay under 1 MB): **the game's
first screen is on the BC-250's display.** 2,318 submissions, 167 flips, a frame every 0.5 s
(KytyPlus's title bar: 1.9 fps) instead of every 3 s. The first 60 drawn flips are the loading-time
black; then the sampled display buffer changes from flip to flip (42 distinct contents: a
fade-in), the game's log shows its logo and title levels loaded, and the screenshot taken at 90 s
shows the publisher's "presents" card, white text on the grain, correctly de-tiled by KytyPlus's
presenter from the 64KB_R_X surface the GPU wrote. (Raw display-buffer dumps and the full-desktop screenshots stay in
`~/bc5-data/captures/kytyplus-20261001-0915/`. One crop of the emulator window at 90 s is
published at the maintainer's request as `docs/images/g3-first-screen.png`, shown in the README.)

Two submissions timed out on shader faults in regions seen for the first time (0x56801c000 at
30 s in the first DCB of the new, 10,440-dword frame shape; 0x56002a000 at 48 s in a compute IB);
the kernel reset the ring, the host learned both regions and reopened the device, the machine
stayed up. **After the second one: 114 consecutive flips and 1,354 submissions without a failure**,
to the end of the run. No CPU wait timed out after start-up (2 in the run), 5 `EopEq` timeouts.

**Verdict (2026-10-01, 09:25).** Gate G3, first two clauses: *image on screen* — yes, the game's
own frames, from its own command buffers and its own shader binaries, untranslated, on the
BC-250 through the direct path; *no GPU hang across 100 consecutive frames* — yes in run 79's last
70 seconds (114 frames), after two recoverable faults in memory the host had not seen before
(they are learned and mapped up front from the next run on). Still open for G3: the 36/40 CU
numbers (step f). What made the difference since the 00:20 verdict, in order: the context-state
stack (F35: without it every strip lost a vertex), the two wait hand-overs (F34), the ident-0
events (F36), and the host's own crash journal, which had capped the frame rate at one frame per
three seconds. Open items: the frame time (0.5 s; submit plus fence is a constant ~17 ms per
submission whatever its size), SH/UCONFIG state across pop_state, the zero-instance point draw
that became 512 points, `ORDERED_APPEND_ENBL`, the kernel lockup timeout, presentation without
the readback through KytyPlus's presenter, and step (f).

**Run 80** (09:23, GPU, 225 s, submission phases timed; `raw/e35-run80-direct.log`, reduced):
4,578 submissions, 316 flips, the machine up. **302 consecutive flips without a failed
submission** from the start (both regions learned in run 79 were mapped up front), then one
shader fault at 0x40506c000 in a DCB of a new shape (2,960 dwords) ten seconds before the end —
learned. The picture: the loading-time black, the fade-in, then the same opening card until that
new DCB; the game advances per frame, and at 1.4 frames a second its few seconds of card take
minutes.

Where the frame time goes now (`SubmitResult::prepare_ms/list_ms/cs_ms/fence_ms`):

| per submission | average |
|---|---|
| filter and scratch layout | < 0.1 ms |
| BO list creation | 0.5 ms |
| **the CS ioctl** | **27.8 ms** (14.9 ms over the first 500 submissions, 29.2 ms over the last 500) |
| fence wait | 1.2 ms (median 0.01 ms) |

127 s of the run's 223 s are spent inside `DRM_IOCTL_AMDGPU_CS`, 5 s waiting for the GPU. The GPU
finishes a frame's work in milliseconds; the kernel revalidates every userptr BO on the list for
every submission (`amdgpu_cs_parser_bos` walks the user pages of each), and the list carries the
whole mapped guest — 3 GB at the start, 5.8 GB at the end (the hint and learned windows
materialise untouched guest memory). 14–15 submissions a frame make 0.4–0.5 s.

**Verdict (2026-10-01, 09:35).** G3's image stands and repeats (runs 79, 80; 114 and 302
consecutive frames without a GPU hang). The frame rate is now bounded by userptr validation in
the CS ioctl, not by the GPU and not by the host. Options, cheapest first: (1) a short BO list
for IBs without draws or dispatches (only the BOs their packets name) — about half of a frame's
submissions; (2) smaller windows / unmapping what a frame no longer uses; (3) the guest's direct
memory backed by GEM BOs mapped at the guest's addresses instead of anonymous memory mapped as
userptr — no per-submission page walk at all, a change to ADR 0005 §1 and to KytyPlus's memory
backing, bounded by the 7.6 GB GTT. Then step (f).

**Run 81** (09:32, GPU, 135 s, option 1: `Device::set_short_lists`; `raw/e36-run81-direct.log`:
the per-submission timing lines, flips and failures only): an IB that, with its nested IBs, holds no draw and no dispatch after filtering reaches
guest memory only through its packets' operands, so its BO list carries the scratch, the shadow
and just the userptr BOs those operands lie in (the filter's `mapped` callback records them; 64
KiB before and 128 KiB plus twice the declared size after each, for tables declared with a nominal
size). The other mappings stay in the VM and are revalidated by the next submission that draws.

| | submissions | BOs on the list | CS ioctl | whole submit path |
|---|---|---|---|---|
| short list | 2,028 | 5.8 | **0.05 ms** | 1.8 ms |
| full list | 1,905 | 1,953 | 26.9 ms | 32.6 ms |

3,933 submissions, 272 flips, **none failed**, no CPU-wait timeout, the same picture (the
opening card at 90 s). A frame every 0.43 s (2.25 fps in the title bar) with 5.4 GB mapped,
against 0.70 s in run 80 with as much. What a frame costs now: seven full-list submissions at
~33 ms, fourteen mapping syncs at ~11 ms, the rest in the game. Short lists are on by default from
here (`BC5_DIRECT_NO_SHORT_LISTS=1` turns them off). Next for the frame time: the full-list
submissions (options 2 and 3 of run 80) and a sync that is forced only for submissions that draw.

**Runs 82–88, step (f): the CU mask** (09:45–10:03, GPU, 150 s each; summaries in
`raw/e37-runs82-88-cu-mask.txt`; kernel 7.2.4-ogc3.1, Mesa 26.2.2, VRAM carve-out 512 MiB,
`bc250-cu-live-manager status`: 10/10 CUs routed in each of the four shader arrays).

Two host changes first. *Lazy sync:* an IB without draws, dispatches and nested IBs whose
operands the mappings already cover gets the throttled mapping sync instead of the forced one
(0.6 ms instead of 11 ms; about half of the submissions). *The mask itself:* the game's CU masks
do not come through `SET_SH_REG` only — its register image (`LOAD_SH_REG`) and its
`LOAD_SH_REG_INDEX` tables carry `SPI_SHADER_PGM_RSRC3_PS/GS` = 0x0000ffff, `RSRC3_HS` =
0xffff0000 and `COMPUTE_STATIC_THREAD_MGMT_SE0-3` = 0xffffffff — so with a mask other than
0xffffffff the device now appends, after each such load, a `SET_SH_REG` with the loaded value
ANDed with the mask (`bc5::cu_tables`, unit-tested; `RSRC3_HS` carries `CU_EN` in bits 31:16).

All seven runs: 4,090–4,262 submissions, 283–296 flips, **no failed submission**, a flip every
0.35 s whatever the mask (the frame time is the CPU side, F38). The GPU's share is the fence wait
of the submissions that draw; medians, per mask (the same 16-bit value for every shader array):

| `BC5_DIRECT_CU_MASK` | bits per array | frame DCB (≥ 9,000 dwords) | compute IB (≥ 1,000 dwords) | fence wait per flip |
|---|---|---|---|---|
| 0x00010001 | 1 | 18.78 ms | 3.02 ms | 25.0 ms |
| 0x00ff00ff | 8 | 8.90 ms | 2.13 ms | 12.4 ms |
| 0x01ff01ff ("36") | 9 | 8.30 ms | 2.00 ms | 11.8 ms |
| 0x03ff03ff ("40") | 10 | 7.83 ms | 1.91 ms | 11.9 ms |
| 0x0fff0fff | 12 | 7.09 ms | 1.69 ms | 10.3 ms |
| 0x3fff3fff | 14 | 6.59 ms | 1.56 ms | 9.7 ms |
| 0xffffffff (the game's values) | 16 | 6.14 ms | 1.45 ms | 9.7 ms |

Readings: (1) the mask acts, on graphics and on compute, through `SET_SH_REG` and through the
loads; (2) **"36" against "40" by the bit layout assumed so far (bits 0–8 against 0–9) is 6 % on
the frame DCB and 5 % on the compute IB**; (3) **bits 10–15 are not dead**: every further pair of
bits shortens the frame DCB, and from 8 to 16 bits the medians follow 3.4 ms + 44 ms / bits within
0.1 ms — the work scales as if all sixteen bits per array were execution units. The kernel counts
10 CUs per array here and the maintainer's tool shows five WGPs of two; how sixteen mask bits map
onto them is not known (a `TODO(verify)`, Q8 in HANDOFF) — until it is, "36 for the runtime, 4
for the desktop" cannot be written as a bit mask with confidence. (4) Desktop responsiveness
cannot be told apart at this load: the GPU works ~10 ms out of every 350 ms frame in every
setting.

**Verdict (2026-10-01, 10:10).** Gate G3: image on screen — runs 79–88; no GPU hang across 100
consecutive frames — runs 81–88, seven of them with 283–296 consecutive frames and not one
failed submission; 36/40 numbers recorded — the table above, with two recorded deviations: FPS
does not move with the mask because the frame time is kernel and host work (F38), and the
36-CU mask's bit layout is an open question the numbers themselves raised. Recorded as passed
with those deviations in `docs/PHASES.md`; the maintainer's call stands above this entry.
