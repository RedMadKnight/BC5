# 0330 — the second title's host memory: what can come off, and does it keep the frame rate?

*Number assigned by the top session 2026-10-25 (the maintainer: "Zajmij się optymalizacją pamięci").*

**Question.** In the maintainer's test of 2026-10-25 22:33 (exp 0328, F392) the second five-minute run went under
memory pressure:
- MemAvailable fell to ~480–520 MB;
- swap went 547 → 796 MB;
- GTT reached 12.37 GiB;
- the emulator's RSS fell from 5.2 to 1.6 GB as its pages went out;
- picture and sound stalled in turn.

The box has 15.2 GB with a 512 MiB VRAM carve-out (D8), and GTT is limited to 13 GiB (D12). Which parts of the
host's memory can come off, so that MemAvailable stays well above 1 GB in long play on the normal build, and does any
of it cost frame rate?

**Known before this experiment** (exp 0288 / F353 unless stated).
- **About 12 GB is pinned for the GPU**: the direct memfd imported through udmabuf. It plateaus at 11.4 GB within
  ~160 s, then +0.5 GB over 29 min.
  - The host imports a 2 MiB chunk where the CPU has written (SEEK_DATA), in full for the names in
    `BC5_DIRECT_EAGER_NAMES`, and where a render-target hint or a learned fault window asks.
  - An imported chunk stays pinned for the session (`direct_sync_one`, ADR 0006; `bc5LleAgc.cpp` 5bccbb80).
- **The eager list is 17 names, 10,047 MiB.** RenderGpuWcLarge (2,758), CommitIABufferAllocator (2,736) and the AMM
  pool (2,207 + 923) are 8.6 GB of it.
  - Eager import exists because the GPU's first touch of a GPU-only page faulted, and a fault is a 14-s freeze
    (F88 (4), F96).
  - How much of those heaps the GPU touches cannot be read from a running title: pinning allocates the pages.
- **The non-eager heaps add 1,178 MiB.** These are pages the CPU wrote, plus the learned and hint windows.
  - They include heaps the GPU most likely never reads: Wwise 168 MiB, FileSystem 48, SoundAlloc 4, UIStringAlloc 2.
  - These are pinned only because the CPU wrote them.
- **The learned windows are 96 MiB each** (`learned_add`; 61 real ones), and pin wherever they fall outside the eager
  heaps. They carry the zero buffer (F208) where the guest has no range.
- **The normal build's journal reclaims the title's pages.** It writes ~200 MB per 10 min (exps 0281, 0319) through
  the page cache. In five minutes that cost 309 MiB swapped out and 45,700 major faults, against 30 MiB and 3,000 in
  the lean build (exp 0288 Q4).
- **bc5-mount holds 700–850 MB.** `MALLOC_ARENA_MAX=2` took ~100 MiB off and is in the launchers; the rest needs a
  heap profile.
- **Today's setup:** normal 5dd77a82 / lean 47e4a31a, `play-pkg.sh` c0357628. The test binary was
  exp0328/kyty_emulator fcb50e58. The shared tree's `bc5LleAgc.cpp` is 5bccbb80.

**Setup** (prepared offline 2026-10-25; not built, not run).
- **`patch0330.py`** makes `patch_0330.diff` (169 lines, 9 hunks) against 5bccbb80 (out md5 29664e3c). It has three
  switches, all diagnostic (`BC5_DIAG_ENV`) and off by default:
  1. **`BC5_DIRECT_JOURNAL_DONTNEED=1`**: every 8 MiB the journal writes, the writeback of the new part is started
     (`sync_file_range`, not waited for) and the part started the time before leaves the page cache
     (`posix_fadvise` DONTNEED). It applies to both journal paths.
  2. **`BC5_DIRECT_BREAKDOWN_AT=<s>`**: the per-name import table, once at that journal time.
     `BC5_DIRECT_BREAKDOWN_NODATA=1` leaves out its SEEK_DATA walk, which held the game thread for minutes in exp
     0288's run M1. Each row now also prints the name's address span, so that the learned and hint imports in the
     journal can be put to heaps.
  3. **`BC5_DIRECT_ZEROSCAN_AT=<s>`**: once, a background thread at nice 19 reads every imported chunk (pread from
     the memfd).
     - It counts per name the 2 MiB chunks and 4 KiB pages that are all zero.
     - A page still all zero after minutes of play was most likely written by neither CPU nor GPU. So the count bounds
       what a narrower import could leave out, the number exp 0288 could not get without making a heap lazy and risking
       faults.
     - It is read only.

  The diff applies to 5bccbb80, and braces and brackets balance as before. Not compiled yet: the private build is
  `run0330.sh build` (one unit, from the shared normal objects).
- **`s6n0330.sh <live-saves sum> [secs] [arms]`** is exp 0319's chain.
  - **Isolation:** a private working directory, saves and log; an RT-off input configuration; the live saves compared
    only.
  - **The derived launcher** from `play-pkg.sh` adds three hooks after its env-file loop: the input configuration,
    the lazy list and the guest memory size. A later plain assignment of either variable also takes the hook's value;
    continuation lines are left alone. The derived launcher must parse, and every arm's values must show in the
    emulator's environment.
  - **Per run:** sample0330.sh every 10 s; the breakdown and zero-scan tables; the learned and hint import lines;
    flips/s; RT-off drop lines; crash and kernel lines; devcoredumps.
  - **The box's settings,** read only at the start: `vm.swappiness`, vfs_cache_pressure, watermark_scale_factor,
    min_free_kbytes, zram size and algorithm.
- **`sample0330.sh`** is exp 0288's sampler plus the reclaim split: Active/Inactive(file), and pgsteal_file/anon and
  workingset refaults. Is reclaim taking the page cache or the title's pages?

**Arms** (one run each, 600 s, S6N's route, RT off, in this order):

| arm | change against A | what it should show |
|---|---|---|
| A | the private binary with the breakdown at 540 s (no data walk) and the zero scan at 550 s | the base: MemAvailable, swap traffic, major faults, flips/s; the per-heap import table with spans; the all-zero part of each heap; what the learned and hint windows add |
| B | + `BC5_DIRECT_JOURNAL_DONTNEED=1` | the journal's page cache gone. Expected: pswpout and pgmajfault near the lean build's, the title's RSS kept, flips/s unchanged |
| C | + Wwise, SoundAlloc, FileSystem, UIStringAlloc appended to A's `BC5_DIRECT_LAZY_NAMES` | ~222 MiB less pinned if the GPU never reads them. A GPU fault there would show as a hang and a learned window |
| D | + `KYTY_GUEST_MEMORY_MB=12288` (from 13,824) | exp 0288 Q2: does the title size its pools smaller (the AMM pool, the asset heaps) and pin less, or start and run the same? |

**Readings and what follows.**
- **MemAvailable** is the median after minute 3. Pinned is GTT used and the journal's pinned line. Swap traffic is
  pswpout and pgmajfault over the run. The reclaim split is pgsteal file against anon. Also flips/s, and the
  emulator's RSS and Pss_Shmem at the end.
- **If B holds the frame rate and cuts the swap traffic,** its switch is a candidate for the normal build's default
  (D19: the maintainer's yes, through the supervisor).
- **If C pins less with no fault,** the four names go into the launchers' lazy list.
- **If D pins less and runs,** `KYTY_GUEST_MEMORY_MB` gets a run of its own over a longer route.
- **Arm A's zero scan** says whether a narrower eager import is worth designing, and for which heap: an all-zero part
  of the big three, and where in each heap it lies. That design, and shrinking the learned windows (their fault
  addresses are not kept), come after these readings. No arm here makes an eager heap lazy.
- **Not in reach of this experiment:**
  - `vm.swappiness` and the zram setup are the maintainer's to change. The run records them, and the reclaim split
    says whether they matter.
  - bc5-mount's ~700 MB needs a heap profile.

**Plan.** Box time is about 50 minutes in one batch: the private build (~2 min, CPU only) and 4 × ~11 min of runs.
1. Build, on the box supervisor's GO.
2. The four runs, on the box supervisor's GO and the maintainer's approval in the tcp session, with `stream0330.sh`
   on the laptop. It streams the kernel log and the journal's probe, TIMEOUT, breakdown and zero-scan lines while the
   chain's lock line is there.

Exp 0329 (bvh) also needs box time, so the runs go in one chain.

**Result.** Pending.
