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

**Result** (2026-10-26, run by the cloud supervisor on the maintainer's GO: "Masz GO, decyzja A").
- **Setup:**
  - built 07:30: `exp0330/kyty_emulator` a86787f1 from the shared normal build 4a146894's objects; the patch output is
    29664e3c as designed; 4 compiler warnings, none in the 0330 edits (`raw/build.out`);
  - the chain ran 07:35–08:06 with `play-pkg.sh` c0357628, derived launcher 0608cd5e (`raw/play-pkg-0330.diff`);
  - the box's settings are in `raw/box-settings.txt` (swappiness 60, zram 7.6 GB zstd);
  - arm A's lazy list was `orbis_user_malloc`;
  - the live saves read b1cd637738395a19 before and after every arm (`raw/s6n-saves.txt`). They differ from STATE's
    20bc4707 because the maintainer played at 23:58 on 10-25.
- **No GPU trouble:** the kernel stream (`raw/kernel-stream.txt`) holds no GPU line over the whole chain. The journal
  stream holds no TIMEOUT and no fault.

| arm | verdict | flips/s | pinned MiB | MemAvailable after 3 min, median (min) | swap used, start → end | pswpout | pgmajfault | pgsteal file / anon | refaults file / anon | PSI memory full |
|---|---|---|---|---|---|---|---|---|---|---|
| A | pass, 600 s | 36.8 | 11,474 | 675 (650) MiB | 504 → 627 MiB | 80,227 | 59,033 | 11.52 M / 90.4 k | 1.19 M / 57.6 k | 5.75 s |
| B | pass, 600 s | 36.4 | 11,430 | 670 (634) MiB | 548 → 554 MiB | 2,954 | 3,334 | 9.35 M / 4.1 k | 708 k / 2.2 k | 3.13 s |
| C | pass, 600 s | 36.2 | 11,232 | 720 (706) MiB | 553 → 557 MiB | 1,188 | 850 | 8.98 M / 1.4 k | 705 k / 302 | 3.26 s |
| D | **did not start**: exit 65 at 6 s | — | (7,010 at the stop) | — | — | — | — | — | — | — |

The counters are deltas over the run from `raw/<arm>-mem.txt`, in pages; PSI is the "full" time. Arm A's zero scan at
550 s read 11,378 MiB in 2.3 s (`raw/A-zeroscan.txt`). The per-name import table is `raw/A-breakdown.txt` (no data walk).
The heaps with the most all-zero memory:

| heap | imported MiB | in all-zero 2 MiB chunks | in all-zero 4 KiB pages |
|---|---|---|---|
| RenderGpuWcLarge | 2,758 | 1,422 | 1,786 |
| CommitIABufferAllocator | 2,736 | 1,376 | 1,489 |
| DynamicHeap | 328 | 212 | 230 |
| AMM | 2,276 | 184 | 340 |
| Physics | 192 | 166 | 174 |
| RenderGpuRwLarge | 414 | 76 | 129 |
| InitAllocator | 412 | 2 | 150 |
| total | 11,378 | 3,672 | 4,691 |

B and C read the same within 12 MiB of all-zero chunks per heap (`raw/B-zeroscan.txt`, `raw/C-zeroscan.txt`). C's
scan lacks the four lazy names.

Readings:
1. **The eager import pins 3.7 GB that is all zero after nine minutes of play.** That is a third of the 11.4 GB pinned.
   2.8 GB of it lies in RenderGpuWcLarge and CommitIABufferAllocator, half of each heap in whole 2 MiB chunks.
   - A page still zero then was most likely written by neither the CPU nor the GPU on this route.
   - It does not show that a longer session or another place in the game leaves it untouched.
2. **B's switch costs no frame rate** (36.4 against 36.8 flips/s). This chain does not show its effect on swap
   traffic, because of the order:
   - A ran first and pushed the cold system out to zram (swap 504 → 627 MiB);
   - B and C started with that already swapped;
   - C, without the switch, swapped as little as B (1,188 and 2,954 pages out).

   A fair test alternates the arms after a warm-up run.
3. **Reclaim takes file pages, not the title's anonymous ones.** In every arm 9–11.5 M file pages were stolen against
   1.4–90 k anonymous ones. 0.7–1.2 M file pages, 2.7–4.5 GiB, were read again within ten minutes.
   - The page cache thrashes: the files the title streams do not fit in the ~0.7 GB left. These are bc5-mount's
     image and the files it serves.
   - So `vm.swappiness` is not the lever. Whether the image's pages and the FUSE files' pages are cached twice is not
     known: TODO(verify).
4. **C's four CPU-only heaps lazy** (Wwise, SoundAlloc, FileSystem, UIStringAlloc) pinned 242 MiB less than A. There
   was no learned fault, no TIMEOUT and no hang, and the frame rate was unchanged (36.2/s). MemAvailable's median rose
   by only ~45 MiB. Where the rest went was not read; the page cache taking it is the likely reading.
5. **D does not start.** With `KYTY_GUEST_MEMORY_MB=12288` the title stopped 3 s after its start:
   `condition (g_tls_main_program == nullptr) is true in runtimeLinker.cpp:1470` (`raw/D-play.log`). So the title
   does not size its pools smaller with less guest memory; the main program's load fails first. Why it fails was not
   read further.

**Verdict.**
- **The memory to win is in the eager import, not in the box.** About 3.7 GB of the pinned 11.4 GB is untouched on
  this route. The next experiment is a narrower import of RenderGpuWcLarge and CommitIABufferAllocator:
  - first it checks over a longer session (the maintainer's play, the zero scan at the end) that the zero parts stay
    zero;
  - then it leaves them to the fault path with learning (F96's method).
- **The four CPU-only names are a candidate for the launchers' lazy list:** −242 MiB pinned, no fault, same frame rate.
  The integration is D19's: the maintainer's yes.
- **`BC5_DIRECT_JOURNAL_DONTNEED=1` is harmless, but not shown to help.** It needs the alternating test before it is
  proposed as a default.
- **`KYTY_GUEST_MEMORY_MB` stays at 13,824.**
- **The box's reclaim is a page-cache thrash.** That points the box's settings and bc5-mount's caching at the file
  side, not at swap.

**Addendum (2026-10-26, after the integration, F394).** On the maintainer's yes ("Zaczynaj od A"), `int0330.sh` added
arm C's four names to the lazy list of the second title's three launchers at 08:20. One line goes in after each
launcher's env-file loop, where arm C's hook was:
`export BC5_DIRECT_LAZY_NAMES="${BC5_DIRECT_LAZY_NAMES:+$BC5_DIRECT_LAZY_NAMES,}Wwise,SoundAlloc,FileSystem,UIStringAlloc"`.
- **The launchers:**
  - `play-pkg.sh` c0357628 → b10eac6d;
  - `play-pkg-log.sh` e1b361a1 → 5080d2ce;
  - `play-pkg-quiet.sh` 2b23073d → 48fa60ba.
- **What stays as it was:** `bc5-run.env` keeps `orbis_user_malloc`, so ASTRO BOT's `play-astro.sh` is unchanged.
- **Both shortcuts take it.** They reach `play-pkg.sh` through `play-any.sh`. The lean build reads the list with
  `getenv` as the normal one does; the experiment ran the normal build's objects only.
- **Checks:** each launcher parses, its diff is the one added line (`raw/int-*.diff`), and its first lines, sourced in
  a subshell, give `orbis_user_malloc,Wwise,SoundAlloc,FileSystem,UIStringAlloc` (`raw/int.out`). The script was first
  run on copies, including its restore path.
- **Undo:** `~/bc5-work/exp0330/integration/*.before-0330`; the command is the last line of `raw/int.out`.
- **Not run:** the integrated launchers in play. The maintainer's play tests them.

**Addendum (2026-10-26 09:07, the maintainer's test shortcut).** At his choice ("a"), `setup0330t.sh` set up "BC5
emulator (test 0330: pamięć)" on his desktop, as exp 0328's test shortcut was.
- **What it runs:** the private binary a86787f1 through `exp0330/play-pkg-0330t.sh` (73845711). That is today's
  `play-pkg.sh` b10eac6d with the integrated lazy list, plus two changes (`raw/play-pkg-0330t.diff`):
  - one log per start in `exp0330/play/`;
  - after the lazy-list line, `BC5_DIRECT_BREAKDOWN_AT=1800 BC5_DIRECT_BREAKDOWN_NODATA=1 BC5_DIRECT_ZEROSCAN_AT=1810
    BC5_DIRECT_JOURNAL_DONTNEED=1`.
- **His session:** his own saves (b1cd637738395a19 at the setup) and his `input.cfg` (RT off).
- **The question:** does the 2.8 GB of all-zero chunks in RenderGpuWcLarge and CommitIABufferAllocator stay zero after
  30 minutes of his play? The answer decides the narrower import.
- **Undo:** `rm` of the shortcut and the copy (`raw/setup0330t.out`).

**Addendum (2026-10-26 10:15, the maintainer's first session on the test shortcut, F395).** He played 09:58–10:09:36
(~11.5 min, RT off) and reported a picture freeze near the end. The evidence is in `raw/maintainer-test/`.
- **The freeze:**
  - the kernel logged `ring gfx_0.0.0 timeout` at 10:08:45 (`kernel.txt`), and the reset succeeded. The box stayed up,
    in the boot of 00:03;
  - the devcoredump is `~/bc5-data/captures/devcoredump/20261026-100846-devcd1.txt`;
  - in the journal, an acb/dcb pair timed out on the host after 2,030 ms, near t ≈ 642 s (`probe.txt`): #775996 (acb,
    9,153 dwords) and #776001 (dcb, 2,908 dwords). The acb's first packet is the wait on 0x12004b4fc8 == 0, read as met;
  - the last flip was at t 658.9 s; he closed the emulator at 10:09:36 (exit 0);
  - the lazy list in force was arm C's (`journal-lines.txt`).
- **His session ran under far heavier memory pressure than the bench** (`vmstat-delta.txt`, from arm C's last sample to
  10:12):

  | | his session (~11.5 min) | arms A–C (10 min each) |
  |---|---|---|
  | PSI memory "full" | 25.9 s | 3.1–5.8 s |
  | file pages reclaimed | 44.5 M | 9.0–11.5 M |
  | file pages refaulted | 5.5 M | 0.7–1.2 M |
  | pages swapped out | 169 k | 1.2–80 k |
  | major faults | 127 k | 0.9–59 k |

  Free play streams far more than S6N's route.
- **The zero scan did not run:** it was set for 1800 s.
- **A lead for the thrash, not measured yet.** bc5-mount can hold the title's data three times:
  1. the image's pages in the page cache (plain reads, no `O_DIRECT` or `fadvise` in `tools/bc5-mount/src`);
  2. its decoded-block cache of 1,024 MiB (`pfsc.rs`, exp 0121, chosen when the game left 3.7 GB free);
  3. the served files' pages, which stay cached (`FOPEN_KEEP_CACHE`, `fuse.rs:287`).

  Which process reads those tens of GiB is not known. The mount log has no statistics.
- His saves changed in the session (a24ec483cee31821), as play does.
