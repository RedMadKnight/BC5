# 0288 — the emulator's memory on the box: what the second title pins, touches and could do with less of

*Number assigned by the top session 2026-10-24 (the maintainer's request: "zlecić badanie pamięci emulatora"). Branch `worktree-exp-0288-emulator-memory`, own worktree.*

**Question.** During the maintainer's 29-minute second-title session of 2026-10-24 22:35 (exp 0276,
`play-20261024-2235`) the box ran out of memory: MemTotal 15.2 GB, MemAvailable ~1 GB, zram swap 1.3 GB,
PSI memory "full" avg300 13.6 % at the end, and the frame rate fell towards the end. The emulator had
11.31 of 13 GiB of GTT pinned through memfd/udmabuf ("94 BOs, 12030.0 MiB pinned"), an RSS of 4.59 GB
(Pss_Shmem 4.39 GB), 9,775 memfd mappings over 25.6 GiB; `bc5-mount` held 792 MB. Four questions, by payoff:

1. Of each heap imported in full (`BC5_DIRECT_EAGER_NAMES`, D15, F96), how much does the title touch over a
   play route, and which heaps could be imported lazily or in parts without the late-mapping faults that
   made eager import necessary (F88 (4), F96)?
2. Does the title allocate less than the 13,824 MiB of `KYTY_GUEST_MEMORY_MB`, so the figure could be lowered?
3. Can `bc5-mount`'s RAM cache be capped without slower loads (F287, F289, ADR 0014)?
4. How much does the lean build save in a long session (F236: RSS equal at the start screen)?

**Setup** *(draft, before the box work; every box step waits for the top session's GO and runs under
this experiment's lock line, read-only unless stated)*.

- Offline first: the GPU journal of the 22:35 session and its play log (`~/bc5-work/exp0276/play-2235.log`),
  copied read-only, through `mem-timeline.awk` (pinned MiB per memfd per minute, BOs, GPU mappings, map/unmap
  counts, hint and learned imports, frames) and the launcher files (`play-pkg.sh`, `bc5-run.env`).
- What the host can say per heap: the direct path imports a heap's chunks either where the CPU wrote them
  (`SEEK_DATA` over the memfd, ADR 0006) or in full for the eager names; `BC5_DIRECT_BREAKDOWN=1` journals
  per heap name "reserved / with data / imported" at every 512 MiB of growth (and on `-ENOMEM`), at
  25–80 s per pass on the game thread (patch 0001, `direct_breakdown_one`). What the GPU alone touches
  inside an eagerly imported heap is not visible after the fact: pinning allocates the pages. It needs a
  run with that heap lazy and the fault learning on (F96's method), which is a run of its own.
- Memory sizes known from the repo: the second title's heaps at fixed addresses 0x1000000000–0x1202400000
  (F88), `CommitIABufferAllocator` 2,736 MiB, `RenderAlloc` 70, `Physics` 192, `Decal Job Scheduler` 12,
  `VisualEffectInstanceHeap` 24, `DynamicHeap` 328 (exp 0042); the eager list of exp 0042 (17 names) gave
  9.7 GiB imported at 250 s; the AMM pool is the 3 GiB the title gives plus the host's direct memory (F206).
  `bc5-mount`: the `.ffpfsc` decode cache defaults to 1,024 MiB (`pfsc.rs`, exp 0121: 3.7 GB free with 1,024,
  2.7 with 2,048), the package path's inner cache to 32 MiB plus the on-disk cache (`BC5_MOUNT_DISK_CACHE`,
  exp 0112); `BC5_MOUNT_CACHE_MIB` sets either. The host's own Vulkan buffers: `KYTY_BC5_CACHE_MIB=96,16,16,16`
  (F47). The lean build: RSS 3.7 GB at the start screen, as the normal build (F236).

**Result.**

*Step 1, offline, from the 22:35 session's journal (449.9 MB; the memory lines copied read-only on the top session's
GO at 23:48, `run-timeline.sh` → `raw/mem-timeline-2235.txt`) and its play log:*

| minute | frames/s | direct memfd pinned | GPU mappings | AMM maps + / − | hint imports | learned windows asked |
|---|---|---|---|---|---|---|
| 0 | 30.8 | 9,666 MiB (7,498 at t 0.0, 8,056 at 6 s) | 11,496 | 16,334 / 4,838 | 84 × 702 MiB | 102 × 3,884 MiB |
| 1 | 36.6 | 10,968 | 19,009 | 14,506 / 6,993 | 55 × 256 | 352 passes, 48 |
| 3 | 27.8 | 11,512 | 20,726 | 4,681 / 4,466 | 26 × 140 | 110 |
| 10 | 34.6 | 11,832 | 21,825 | 3,940 / 4,398 | 59 × 126 | 52 |
| 20 | 14.2 | 11,880 | 20,855 | 3,554 / 4,438 | 72 × 42 | 8 |
| 27 | 36.5 | 12,030 (the peak, t 1,661 s) | 18,147 | 2,625 / 3,515 | 60 × 22 | 88 |

- The private memfd (code, stacks) stays at 276 MiB. So the 12 GB of GTT is the direct memfd: 7.5 GB imported at
  t 0.0 (the eager heaps plus the learned windows applied at start), 9.7 GB after the first minute, 11.5 GB from
  minute 3, then +0.5 GB in 25 minutes — a plateau, not a leak. The frame rate's dips (minutes 3–4, 13–14, 20, 23–24,
  28) do not follow the pinned size.
- **The learned-fault windows are 3.9 GB of it.** `direct-learned-pkg.txt` holds 107 windows of 96 MiB (`learned_add`:
  64 MiB-aligned, 32 MiB before the fault); 46 lie at junk addresses (bits above 40 set, or 0x0) and import nothing, the
  61 real ones in the title's heap span (0x11xx–0x12xx) and the AMM window (0x80xx–0x81xx) asked 3,884 MiB in the first
  minute: memory outside the eager heaps that the GPU once faulted on, imported whole at 96 MiB a fault.
- The "scratch" zero buffer under holes is one 2 MiB BO (`scratch_bo`) mapped 1,975 times over the session
  (8,096 MiB of GPU VA, no RAM). The learned pass itself (`learned_apply`) ran 10,028 times over 5 ms, 83 s in all
  (max 633 ms), and the direct syncs took 180 s of the 1,742-s session on the game thread (`timing split`, 13,616
  reports) — a cost, not memory, noted for another experiment.
- The slowdown is the title's thread: by 5-minute block the frame went 31.3 → 34.4 → 35.7 → 30.6 → **38.9** → 32.0 ms
  with the game thread *outside* the host 17.8 → 21.7 → 22.3 → 18.0 → **24.7** → 18.4 ms, while GPU busy stayed
  14.5–15.1 ms and label waits 0.4–0.5 ms. The title's CPU heap (`orbis_user_malloc`, lazy, not pinned) is the
  swappable part of the memfd; with 12 GB pinned and ~1 GB available its pages are what zram (1.3 GB) held.
- **`bc5-mount` (784 MB RSS + 183 MB in swap on the idle box, mount up since 19:04)** is not a cache: the package
  path's block cache is 32 MiB (`pkg/inner.rs`) plus the on-disk cache (`BC5_MOUNT_DISK_CACHE`, 196 GB `.data` +
  6 MB `.map`). Its `smaps` shows 57 anonymous mappings, 782 MB in all, eight of them 64 MiB regions filled to 62–65 MB:
  glibc's per-thread malloc arenas (8 FUSE read workers, `MAX_WORKERS`), kept after the decode buffers
  (`vec![0u8; uncomp]` per block) were freed. The candidate is a launcher line, `MALLOC_ARENA_MAX=<n>` for the mount
  process (no code), to be measured against the same loads.
- The emulator's own anonymous memory was 0.19 GB (the top session's smaps at 23:30), so the lean build (no journal,
  no traces) can save at most that plus the journal's page cache: this session's journal grew to 450 MB and its log to
  22 MB in 29 minutes, written through the page cache of a box with ~1 GB available.
- Idle box at 23:48 (no emulator): MemAvailable 12.8 GB, swap 724 MB used (zram 680 MB data, 219 MB compressed), GTT
  used 185 MiB, PSI memory full avg300 0.94 %.

*Run M1 (01:15–01:22, private binary 405f12a7, RT off, 420 s, `raw/M1-*`): passed every check (0 kernel, crash or
TIMEOUT lines, saves `c0ee58b92c0cadc2` before and after, 42 memory samples) and repeated the 22:35 picture on the
scripted route: pinned 9,658 MiB in the first minute, 11,436 MiB from t 161 s and flat; MemAvailable 500–575 MiB from
the third minute on with GTT at 12,134 MiB; the emulator's RSS 5.8 GB at the load (Pss_Shmem 5.6 GB) falling to 1.4 GB
as the kernel reclaimed its CPU-side memfd pages (141 MB of it into zram, zram 651 → 985 MB); bc5-mount 731 MB + 212 MB
swapped. No table: the breakdown fired at 240.1 s as designed, and its SEEK_DATA/SEEK_HOLE walk over 22,000 views and
12 GB of pinned pages held the game thread for the remaining 180 s (3 frames in the fifth minute). Hence
`BC5_DIRECT_BREAKDOWN_NODATA=1` (patch0288.py): the "with data" column skipped; for the eager heaps it equals "imported"
by construction (udmabuf allocates what it pins). N1 did not start: the remount step looked for the mount on the host,
where the launcher's distrobox mount is not visible, and stopped; the mount was alive throughout (the top session,
01:24). The step now works inside the distrobox: fusermount, wait for the process to leave, never a kill, and the
launcher's normal mount put back at the end.*

*Run M2 (01:47–01:52, private binary 08675be8 with `BC5_DIRECT_BREAKDOWN_AT=240 BC5_DIRECT_BREAKDOWN_NODATA=1`, RT off,
300 s, `raw/M2-*`): passed every check (0 kernel, crash or TIMEOUT lines, saves `c0ee58b92c0cadc2` before and after,
30 memory samples). Both tables came at t 240.2 and 240.9 s in under a second each (`raw/M2-breakdown.txt`), with
the frame rate unchanged across them (43.2 fps in minute 3, 42.0 in minute 4). GTT 12,128 of 13,312 MiB at the table.*

**Q1/Q2 — what the title reserves and what the host pins, per heap** (direct memfd, MiB; "imported" = pinned in GTT;
eager heaps are pinned whole by `BC5_DIRECT_EAGER_NAMES`, the others where the CPU wrote or a hint or learned window asked):

| heap | reserved | imported | note |
|---|---|---|---|
| RenderGpuWcLarge | 2,758 | 2,758 | eager |
| CommitIABufferAllocator | 2,736 | 2,736 | eager (F88's faults) |
| AMM (653 views) + AMM pages under 1 MiB (18,661 views) | 2,207 + 923 | 2,207 + 923 | eager; the pool is the "3 GiB the title gave" (F206) |
| RenderGpuRwLarge (4 views) | 414 | 414 | eager |
| DynamicHeap | 328 | 328 | eager |
| Physics | 192 | 192 | eager |
| RenderGpuWcSmall / ComponentHeap / RenderAlloc / DynamicHeap Small / RenderGpuRwSmall / ComponentHeap Small / VisualEffectInstanceHeap / MaterialHeap / DDLHeap / Decal Job Scheduler / Physics query allocator | 110 / 104 / 70 / 54 / 36 / 36 / 24 / 20 / 16 / 12 / 7 | the same | eager, 489 in all |
| InitAllocator | 652 | 412 | not eager |
| AssetHeap Large | 816 | 314 | not eager |
| AssetHeap Small | 350 | 214 | not eager |
| Wwise | 220 | 168 | not eager |
| FileSystem, Job thread scratch (15 views), SoundAlloc, UI, UIStringAlloc, SceAgcDriver, Amm Ring | 52 / 15 / 4 / 2 / 2 / 1.8 / 1 | 48 / 11 / 4 / 2 / 2 / 1.8 / 1 | |
| **total, direct memfd** (19,358 views, may alias) | **12,162** | **11,224** (11,416 in 90 BOs) | of 13,824 offered |
| private memfd: eboot.bin 228, libcohtml 26, four libraries 8, 59 thread stacks 85 (lazy) | 347 | 262 (276 in 11 BOs) | |

- **Q2:** the title reserves 12,162 MiB of the 13,824 MiB of direct memory it is offered. Reserved is not resident:
  the memfd is sparse, and its resident size is what is pinned plus what the CPU wrote — `Shmem` in the samples sits at
  11,766 MiB at steady state, within 350 MiB of the 11,416 MiB pinned plus the 276 MiB private memfd. So neither the
  1,662 MiB the title never reserves nor the 938 MiB it reserves but the host never imports costs RAM today, and
  lowering `KYTY_GUEST_MEMORY_MB` saves memory only if the title then sizes its pools smaller (the AMM pool, the asset
  heaps) — a run of its own (start at 12,288 and compare this table), not a setting to change blind.
- **Q1:** the eager list pins 10,047 MiB (the table's eager rows), 90 % of the pinned total; two heaps and the AMM pool
  are 8,624 of it. What the GPU touches inside them is not in this table (the pages are allocated by the pinning) —
  that needs a run with one heap lazy and the fault learning on (F96's method), one heap at a time, starting with the
  largest two. The non-eager heaps add 1,178 MiB through the learned windows and CPU data; the 96 MiB learned windows
  are the host's own granularity (`learned_add`), and a smaller window for new faults is a one-line knob.

*Runs N1 and L1 (01:59–02:10, shared normal build 893f8ab4 and shared lean build fa8d15f5, RT off, 300 s each, same
route, `raw/N1-*`, `raw/L1-*`): both passed every check (0 kernel, crash or TIMEOUT lines, saves `c0ee58b92c0cadc2`
before and after, 30 samples each). N1 ran on a package mount made fresh with `MALLOC_ARENA_MAX=2`, unmounted after
the run; L1 on the launcher's normal mount, made fresh right after (default arenas), which stays in place.*

**Q3 — bc5-mount's memory** (the package path; MiB, after 300 s of the same route from a fresh mount):

| mount | RSS at the end | swapped | peak RSS |
|---|---|---|---|
| default arenas (L1's, the launcher's normal mount) | 824 | 27 | 840 |
| `MALLOC_ARENA_MAX=2` (N1's) | 695 | 57 | 743 |
| the launcher's mount of 19:04 after the 29-min session, idle (23:48) | 784 | 183 | |

- The arena cap takes ~100 MiB (12 %) off, not the 700. So most of the 700–850 MB is not glibc's per-thread
  retention but memory the process holds for real after the loads — and the package path's block cache is only 32 MiB.
  Candidates are the layout tables and the on-disk cache's index for a 196 GB decoded image (`pkg/naps.rs`,
  `pkg/diskcache.rs`) and the per-request buffers of the 8 read workers; which one needs a heap profile of the mount
  process (a counting allocator or `heaptrack`), an experiment of its own. A launcher line `MALLOC_ARENA_MAX=2` for the
  mount is worth 100 MiB and nothing was slower (N1 loaded and ran like M2), but it is not the lever.

**Q4 — the lean build in the same 300 s** (the emulator's `smaps_rollup`, meminfo and vmstat every 10 s; both runs RT off,
same route, GTT 12,164 / 12,173 MiB pinned at the end):

| | normal build (N1) | lean build (L1) |
|---|---|---|
| emulator RSS at the end (peak) | 1,695 (6,352) | 5,447 (6,444) |
| of which Pss_Shmem (CPU-mapped memfd pages) | 1,547 | 5,182 |
| emulator anonymous | 132 | 244 |
| emulator pages in swap | 147 | 8 |
| pages swapped out during the run (`pswpout`) | 79,058 (309 MiB) | 7,718 (30 MiB) |
| major faults during the run (`pgmajfault`) | 45,709 | 3,004 |
| zram data, start → end | 522 → 657 | 522 → 544 |
| MemAvailable at the end | 689 | 456 |
| the run's journal + log written | 98 MB + 0.19 MB | 0.06 MB log, no journal |

- The pinned memory is the same in both builds (the heaps are the title's). The difference is what the kernel does
  with the rest: in the normal build the journal and the play log go through the page cache (98 MB in five minutes
  here, 450 MB in the maintainer's 29 minutes), and the kernel paid for it by reclaiming the title's CPU-side memfd
  pages — 309 MiB swapped out to zram and 45,700 major faults in five minutes, the emulator's mapped pages falling from
  6.3 to 1.7 GB. In the lean build the title's pages stayed resident (5.4 GB mapped at the end, 30 MiB swapped, 3,000
  major faults) and MemAvailable was 230 MiB lower for it. So the lean build saves the title about 45,000 major faults
  and 300 MiB of swap traffic per five minutes of play on this route, which is where the late-session slowdown of the
  22:35 session (the game thread outside the host 17.8 → 24.7 ms a frame, GPU flat) most plausibly came from. The
  emulator's own anonymous memory is 130–250 MB in both: nothing to gain there.

*Step 2 ran 01:06–02:10 on the top session's GOs (the private build, M1, M2, N1, L1; the box released each time).
Conditions: ray tracing off in every run
(`KYTY_BC5_RT=0`, S6N's route took the machine down at 17:47 with RT on and nobody can power-cycle before ~07:00; the
heaps are allocated either way, so the memory questions measure the same); the live saves' checksum
`c0ee58b92c0cadc2` snapshotted at the start, required at the end, restored only to that snapshot; the launcher's normal
mount back after the `MALLOC_ARENA_MAX=2` test.*

**Verdict.** Measured on the box, four runs, all clean; the shared builds and launchers unchanged.

1. **The 12 GB is the eager import, and it is a plateau, not a leak.** 11.4 GB is pinned within three minutes of
   every run (161 s on the scripted route) and grows 0.5 GB over the next 25 minutes. 90 % of it is the eager list:
   RenderGpuWcLarge 2,758 MiB, CommitIABufferAllocator 2,736 and the 3.1 GB AMM pool are 8.6 GB alone (Q1). How much
   of those three the GPU touches cannot be read from a running title; it needs one run per heap with that heap lazy
   and the fault learning on (F96's method). That is the next experiment, and the only one that can move the big number.
2. **The learned-fault windows cost 3.9 GB** of the pinned memory at every start: 61 windows of 96 MiB around old
   faults outside the eager heaps (the file holds 107 entries, 46 at junk addresses). A smaller window for new faults
   is a one-line knob in `learned_add`; shrinking the existing ones needs their fault addresses, which the file does
   not keep. Worth a run with a rebuilt file (delete it, play the route, see what returns and at what size).
3. **`KYTY_GUEST_MEMORY_MB` is not a lever by itself (Q2):** the title reserves 12,162 of 13,824 MiB, the memfd is
   sparse, and `Shmem` equals the pinned size, so the unreserved and the reserved-but-unimported parts are not resident.
   Lowering it helps only if the title then sizes its pools smaller, which a run at 12,288 would show.
4. **bc5-mount's 700–850 MB is mostly real (Q3):** `MALLOC_ARENA_MAX=2` saves ~100 MiB with no slower loads; the rest
   needs a heap profile of the mount process before anything is changed.
5. **The lean build keeps the title's pages resident (Q4):** same pinned memory, but 309 MiB swapped out and 45,700
   major faults in the normal build's five minutes against 30 MiB and 3,000 in the lean build's, the difference being
   the journal and log the normal build writes through the page cache (450 MB in the maintainer's 29 minutes). For
   long hand sessions the lean shortcut is the memory-friendly one as things stand, and `PLAY_CAPTURE` is the switch
   that costs.

Nothing here enters the shared builds or launchers. Candidate lines, all off by default and for the maintainer's yes:
`MALLOC_ARENA_MAX=2` on the launcher's mount command (~100 MiB); the lean shortcut, or `PLAY_CAPTURE` off, for long play;
`BC5_DIRECT_BREAKDOWN_AT` / `BC5_DIRECT_BREAKDOWN_NODATA` (`raw/patch_0288.diff`, a diagnostic) for the per-heap table in
future runs. Not verified: anything about ray tracing on (every run here had it off), and the GPU-touched fraction of
the eager heaps.
