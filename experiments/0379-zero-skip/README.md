# 0379 — Leave the second title's known-zero render-heap chunks unpinned, behind a canary (RT on)

**Date.** 2026-10-29. **Box.** A private build and three runs of the S6N route with RT on (arms S, A, B), after
exp 0378, with the top session's GO. **Number.** Claimed in `experiments/0379-zero-skip` and `~/bc5-work/exp0379`.

**Question.** With RT on, the second title pins ~12.4 GiB of GTT and the box runs out of page cache: bc5-mount re-reads
3–4 GB a minute and PSI I/O "full" is 9–24 % (F505). Can the host leave the all-zero 2 MiB chunks of the two big render
heaps (RenderGpuWcLarge, CommitIABufferAllocator) unpinned, with no GPU fault, hang, frame-rate loss or visible change,
so that GTT used falls and the mount reads less?

## Design (written before the code)

### What pins those chunks today

Read from main's patch 0001 (9420cfa0), `src/libs/bc5LleAgc.cpp` (blob 8d2f498):

- The two heaps are in `BC5_DIRECT_EAGER_NAMES`, so `direct_sync_one` imports every 2 MiB chunk of them
  (`if (v.eager)`), data or not. udmabuf pins, and so allocates, every page (ADR 0006).
- The learned windows (`learned_add`, 96 MiB around one fault) and the hint windows (CB/DB bases ±32 MiB,
  `hint_targets`) add chunks to `S.forced`. Inside an eager heap they change nothing: the heap is imported in full anyway.
- So F402's split (738 MiB zero and unforced, 1,878 MiB zero inside learned windows) is a statement about which zero
  chunks are *protected by evidence* of GPU use, not about what pins them. Everything zero in those heaps is pinned
  because the heaps are eager.
- The learned windows inside these heaps date from before the heaps were eager (F96: "17 of the 18 regions learned so
  far lie in those two heaps"), when a lazy heap faulted on GPU-only memory. They record that the GPU once touched
  *something* within 64 MiB, not which chunks.

### The two levers exp 0371 names, and why neither is taken as stated

- **Narrower learned windows** saves nothing while the heaps are eager (above). It only matters for lazy heaps.
- **Lazy unforced ranges** (make the heaps non-eager) would go back to F96's state: render targets and GPU-written
  buffers that no CPU writes, outside the learned and hint windows, would fault. A fault that stalls is the 14-s
  freeze and the reopen (F88 (4)), which has taken the machine down (F207). A fault that does not stall is never
  learned (F208) and the GPU's writes are lost silently.
- Exp 0333's phase R (release after a scan) needs a BO split, a remap and a hole punch mid-session, with a lost-write
  race between the re-read and the punch. It is the most invasive.

### The lever chosen: a zero list from an earlier run, skipped at import, with a canary under the skipped chunks

1. **Arm S writes a zero list.** A diagnostic `BC5_DIRECT_ZEROSCAN_AT=<s>[,<s>...]` with
   `BC5_DIRECT_ZEROSCAN_OUT=<file>` reads every chunk of the named eager heaps (`BC5_DIRECT_ZERO_NAMES`, default
   `RenderGpuWcLarge,CommitIABufferAllocator`) on a background thread at each time and keeps the chunks that were
   all-zero in **every** scan so far. After each scan it rewrites the file: per heap its name and total size, then the
   zero runs of at least `BC5_DIRECT_ZERO_MIN_MIB` (default 8) as offsets from the heap's start. The scan only reads
   (pread of pinned shmem pages: no page cache, no allocation).
2. **Arm B skips those chunks.** `BC5_DIRECT_ZERO_SKIP=<file>` (off when unset; set only by this experiment's
   launcher) loads the list. When a named heap appears with the same total size, its listed chunks are left out of the
   eager import. They are never pinned, so their shmem pages are never allocated.
3. **What still imports a skipped chunk** (it leaves the skip set for the rest of the session):
   - a CPU write: each full sync (one follows every `st_blocks` change) checks each skipped run with `SEEK_DATA`, as
     ADR 0006 does for non-eager views;
   - a hint window (a CB/DB base ±32 MiB): `direct_force` from the hint path takes a skipped chunk back before the IB is
     submitted (F474: the forced sync imports before the job);
   - the canary (below);
   - a device reopen: the skip is switched off and everything is imported as before.
   A chunk that only a learned window forces stays skipped: the learned window is older evidence than the zero list
   (see above), and the canary covers it.
4. **The canary.** Each skipped run gets its own 2 MiB slice of one private memfd BO (one BO, so every CS lists one
   more BO, not one per run). Every chunk of the run is mapped onto that slice at every guest VA that maps it, so a
   GPU access to a skipped chunk never faults:
   - a read gets zeros, which is what the chunk holds (it was zero in every scan and the CPU has not written it);
   - a write lands in the slice. Every 50 ms, on the sync path, the host checks one run's slice for a non-zero byte
     (round robin; cache lines flushed first, TODO(verify) that the CPU sees the GPU's udmabuf writes without it). A
     hit takes the whole run back: it is imported at the next sync, its slice mappings are released, a
     `zero skip: canary hit` line is journalled.
   - The cost of a hit: the GPU's data written to the slice is lost (the real chunk reads zero), and until the check,
     reads of the run's other chunks see that data. That is a possible one-frame glitch, never a fault or a stall.
5. **What it cannot see.** A GPU write of zeros, or data written and cleared between two checks, leaves no trace in the
   slice. Arm S's intersection over several scans is the defence against the second (a chunk that ever held data in a
   scan is not listed).

### Expected gain and risk

- F402 (RT off, bench): 2,814 MiB zero in the two heaps, minus the hint windows (~200 MiB) → up to ~2.6 GB less pinned
  if the list matches. RT on uses ~120 MiB more of CommitIABufferAllocator (exp 0333's list item 5). Runs shorter than
  8 MiB are kept pinned, so the real figure is lower.
- Every new code path is the host's only. Nothing is released mid-session, nothing is punched, no BO is split. A wrong
  list costs a canary hit (a run back, a possible glitch), not a fault.
- The scan and the skip only run with their switches set; the shared builds are untouched (D19).

### Pass criteria (arm B against arm A)

- GTT used lower and bc5-mount reads per minute lower, over the same steady window;
- flips/s not lower (within run-to-run noise, ~1 flip/s per F394/F402);
- no new hang, no kernel amdgpu line, no TIMEOUT, no new learned fault;
- canary hits and hint takebacks counted; no crash line; the live-save checksum unchanged.

## Setup

**Code.**
- `backend/include/bc5/zero_skip.hpp` (and its copy `src/bc5/zero_skip.hpp`, md5 782ca0e9): the list format, the
  scan's intersection (`ZeroMask`), the skip set (`SkipSet`), `all_zero`. 5 Catch2 cases in
  `backend/tests/zero_skip_test.cpp`.
- `patch0379-bc5LleAgc.diff` (md5 6f0c7c16; 348 lines) on the tree's `src/libs/bc5LleAgc.cpp` (e7cc2f60, patch 0001's
  file, git blob 8d2f498) gives e62113a5. It is made by `raw/splice0379.py` from `raw/zskip_block.cpp` and seven anchors:
  - the scan and skip block before `direct_sync_one`;
  - in `direct_sync_one`: the placement, the scan tick and the canary-hit check before the fast path; the take-back
    (CPU writes, canary hits) at the start of the full path; the skip in the eager loop and the forced loop; the canary
    release before a real mapping is added; the canary mapping after a rebuild;
  - in `direct_force`: a hint takes a skipped chunk back; `map_window` marks its call as a learned window's;
  - in the reopen path: `zskip_disable`.
- Switches (all off unless set; the shared builds do not have them):

  | switch | what |
  |---|---|
  | `BC5_DIRECT_ZEROSCAN_AT=<s>,…` | scan times (journal t); a diagnostic (`BC5_DIAG_ENV`, absent from the lean build) |
  | `BC5_DIRECT_ZEROSCAN_OUT=<file>` | where each scan rewrites the list |
  | `BC5_DIRECT_ZERO_NAMES=<n>,…` | heaps scanned (default `RenderGpuWcLarge,CommitIABufferAllocator`) |
  | `BC5_DIRECT_ZERO_MIN_MIB=<n>` | shortest listed run (default 8) |
  | `BC5_DIRECT_ZERO_SKIP=<file>` | skip the list's chunks, canary under them |

**Laptop checks (2026-10-29).**
- `backend` configured with MSVC 14.51 + Ninja, `-DBC5_BUILD_TESTS=ON` (Catch2 3.7.1 from `build-win/_deps`):
  `bc5_backend_tests` 96/96 cases, 33,730 assertions; `[zero_skip]` 5/5 (54 assertions). One expected count in the
  parser test was wrong on the first try (7 bad lines, not 8) and was corrected.
- `raw/harness0379.cpp`: `zskip_block.cpp` with stand-ins for the host, `clang++ -fsyntax-only -std=c++20 -Wall -Wextra
  -Wformat=2 -Wshadow -Werror`: clean.
- `git -c core.autocrlf=false apply` of the diff on the extracted file gives e62113a5; `bash -n` on every script.

**Box build** (`raw/build0379.sh`, 2026-10-29 11:00–11:01; the experiment in `~/bc5-work/exp0379/in/`):
- pins checked: shared normal 58c4a627, archive bb50b2e0, tree unit e7cc2f60, diff, header;
- the backend's Catch2 tests: 96 cases pass (33,729 assertions; one fewer than on Windows, a platform-dependent
  case), `[zero_skip]` 5/5;
- the patched unit compiled with the shared compdb command and relinked: **e1cc0c92**, rc 0, 5 warnings, all in
  older code (`stringUtils.h`, and four in `bc5LleAgc.cpp` outside the new block);
- the shared binary, archive and tree unit unchanged after the build.

**Runs.** `raw/s6n0379.sh` (made from exp 0372's `s6n0372.sh` by `raw/mk-s6n0379.pl`): the S6N route (exp 0203's
`o2-continue.cmd` on exp 0196's route saves, a private wd and save copy), **RT on**, 420 s, the shared `play-pkg.sh`
(55531ab6) with exp 0372's four private paths, a private copy of the learned file. Before each run `sync` and
`drop_caches` (the sudoers entry), so each arm starts with an empty page cache. `raw/sample0379.sh` samples every 10 s
(MemAvailable, swap, Shmem, Cached, GTT used, PSI memory/io full totals, bc5-mount `read_bytes` and RSS, refaults).
`raw/stream0379.sh` streams the kernel log to the laptop. `raw/ana0379.py` makes the table over one window.

| arm | binary | switches |
|---|---|---|
| S1 | private e1cc0c92 | scans at 150, 200, 250, 300, 350, 400 s, list to `~/bc5-work/exp0379/zero-list-S.txt` |
| A1 | shared normal 58c4a627 | — |
| B1 | private e1cc0c92 | `BC5_DIRECT_ZERO_SKIP` = S1's list |

## Result

Box state (`raw/*-box-settings.txt`): kernel 7.2.9-ogc3.1, 15,192 MiB RAM, GTT 13,312 MiB, zram 7.4 GiB (zstd),
swappiness 60; `play-pkg.sh` 55531ab6, bc5-mount 43277724, the shared learned file a7cc8581 (109 windows). The box was
idle between runs (BOX-QUEUE: exp 0378 done at 10:5x; this experiment's lock 10:59–11:25).

### Every run passed (`raw/*-summary.txt`, `*-verdict.txt`, `*-kernel-stream.txt`)

| arm | time | flips over 420 s | flips/s | pinned at the end | kernel amdgpu lines | TIMEOUT | devcoredumps | learned file |
|---|---|---|---|---|---|---|---|---|
| S1 | 11:02–11:09 | 14,796 | 35.2 | 11,324 MiB in 90 BOs | 0 | 0 | 0 | unchanged |
| A1 | 11:09–11:17 | 14,843 | 35.4 | 11,338 MiB in 93 BOs | 0 | 0 | 0 | unchanged |
| B1 | 11:17–11:24 | 14,854 | 35.4 | **9,306 MiB in 121 BOs** | 0 | 0 | 0 | unchanged |

- No crash line in any run. The live saves read 1e451f8fefd534f3 before and after every run (`raw/s6n-saves.txt`).
- Frame profiles (`raw/*-0358.txt`): GPU busy 20.47 / 20.35 / 20.60 ms a frame, host prepare 2.46 / 2.49 / 2.39 ms,
  28.4 / 28.3 / 28.3 ms between flips (S1 / A1 / B1).

### Arm S1: the zero list with RT on (`raw/S1-zero.txt`, `raw/S1-zero-list.txt`)

| heap | span | zero at 150 s | zero in all 6 scans | listed (runs ≥ 8 MiB) |
|---|---|---|---|---|
| RenderGpuWcLarge | 2,758 MiB | 1,430 MiB | 1,378 MiB | 1,218 MiB in 52 runs |
| CommitIABufferAllocator | 2,736 MiB | 1,424 MiB | 1,384 MiB | 1,380 MiB in 3 runs |

- The intersection stopped changing after the second scan (200 s): scans 2–6 gave the same 1,378 + 1,384 MiB.
  Per scan, 1,396–1,410 MiB of RenderGpuWcLarge were zero, so ~20–30 MiB moves between zero and data there; in
  CommitIABufferAllocator nothing moved after 200 s. That matches F402 (RT off, bench) within 60 MiB per heap.
- A scan took 0.46–0.66 s (RenderGpuWcLarge) and 0.91–1.15 s (CommitIABufferAllocator) on its nice-19 thread. S1's
  frame rate (35.2) is within 0.2 flips/s of A1's.

### B1 against A1 (`raw/ana0379.py`, window 180–410 s; then 60–410 s, which includes the load)

| arm | GTT used MiB | MemAvailable MiB (min) | swap used MiB | Shmem MiB | Cached MiB | mount reads MiB/min | PSI mem full % | PSI io full % | refaults /min | major faults /min | flips/s |
|---|---|---|---|---|---|---|---|---|---|---|---|
| S1 | 11,992 | 637 (600) | 609 | 11,721 | 12,392 | 23 | 0.08 | 0.14 | 419 | 263 | 39.1 |
| A1 | 11,992 | 480 (457) | 397 | 11,832 | 12,412 | 25 | 0.03 | 0.19 | 2,357 | 389 | 38.9 |
| **B1** | **10,080** | **2,490 (2,480)** | 532 | 9,869 | 12,327 | **21** | 0.09 | 0.14 | **491** | **38** | 39.1 |

| 60–410 s | GTT used MiB | MemAvailable MiB (min) | mount reads MiB/min | PSI io full % | refaults /min | major faults /min | flips/s |
|---|---|---|---|---|---|---|---|
| S1 | 11,992 | 639 (570) | 1,525 | 2.83 | 25,956 | 3,080 | 36.5 |
| A1 | 11,992 | 503 (407) | 1,515 | 2.77 | 46,200 | 494 | 36.7 |
| B1 | 10,080 | 2,495 (2,457) | 1,303 | 2.26 | 128,001 | 590 | 36.7 |

- **GTT used fell by 1,912 MiB** and **MemAvailable rose by ~2.0 GB** (480 → 2,490 MiB). The page cache outside shmem
  (Cached − Shmem) was 580 MiB in A1 and 2,458 MiB in B1.
- **bc5-mount read 14 % less** over 60–410 s (1,303 against 1,515 MiB a minute) and 16 % less in the steady window
  (21 against 25). In the steady window, major faults fell from 389 to 38 a minute and file refaults from 2,357 to 491.
- During the load (60–180 s) B1 had more file refaults (the 60–410 rate is 128 k against 46 k a minute) at the same
  major-fault rate. With 2 GB more page cache the kernel keeps and recycles more file pages while the title streams;
  this was not looked at further.
- **No frame-rate cost:** 35.4 flips/s over the whole run in both arms, 39.1 against 38.9 in the steady window.
- **The bench does not show F505's thrash.** The S6N route stands after Continue, and its mount reads in the steady
  window are 21–25 MiB a minute in every arm, against 3–4 GB a minute in the maintainer's play (F505). PSI io "full"
  is 0.14–0.19 %. So the bench shows the memory freed, not the slowdown it should cure.

### What the skip did (`raw/B1-zero.txt`)

- Placed: RenderGpuWcLarge at file 0x156c00000 (1,218 MiB in 52 runs) and CommitIABufferAllocator at 0x226200000
  (1,380 MiB in 3 runs); one canary BO of 55 slices (110 MiB pinned); 1,299 canary mappings at the start.
- Taken back in 420 s: **279 chunks by hints** (558 MiB; 144 of them in the first minute), **2 chunks by CPU writes**,
  and **one run by a canary hit**: run 22, file 0x1ae600000 + 18 MiB in RenderGpuWcLarge, between the first and second
  minute reports (journal t ≈ 60–120 s, the load and the Continue). Its 18 MiB went back to a real import.
- 2,018 MiB stayed skipped from the second minute to the end; with the 110 MiB canary that is 1,908 MiB, the GTT
  difference within 4 MiB.
- 28 more BOs than A1 (121 against 93: the skipped runs cut the eager imports) and ~1,000 canary mappings, with no
  measurable host cost (prepare 2.39 against 2.49 ms a frame).

## Verdict

- **Pass on the bench route with RT on.** The zero skip pins 1.9 GB less (GTT used 10,080 against 11,992 MiB),
  leaves MemAvailable at 2.5 GB instead of 0.5 GB, cuts the mount's reads by 14–16 % and major faults by 10× in the
  steady window, at the same frame rate, with no kernel GPU line, TIMEOUT, devcoredump, new learned fault or crash,
  and the live saves unchanged.
- **One canary hit is a real event, not noise.** The GPU wrote non-zero data into 18 MiB of RenderGpuWcLarge that was
  zero in all six S1 scans, during the load. The canary caught it and the run was imported, as designed; whatever the
  GPU wrote there before the check (up to ~2.75 s: 55 slices at 50 ms) was lost. The logs cannot show whether that
  was visible. A list made on one route will meet more such writes in free play.
- **What the bench cannot answer.** F505's thrash happens in the maintainer's free play, which moves through the world; the bench
  stands still and its mount reads 21–25 MiB a minute in every arm. Whether 2 GB more page cache removes the 3–4 GB a
  minute of re-reads, and how many canary hits a list from the bench meets in free play, needs a run in that play.
- **Not integrated.** The host diff (`patch0379-bc5LleAgc.diff`) and the header go into patch 0001 and the shared
  builds only on the maintainer's yes (D19), with `BC5_DIRECT_ZERO_SKIP` and a list file in `play-pkg.sh`. Before
  that, two improvements are cheap: one canary slice per run is 110 MiB (a slice shared by several small runs would
  cost less), and the list could be the intersection of several sessions, the maintainer's free play included
  (one S run with the scan switches in the maintainer's play).

## Findings (for HANDOFF)

- **F540** — With RT on, 2.6 GB of the two eager render heaps stays all-zero through six scans of the S6N route.
- **F541** — Skipping those chunks behind a canary pins 1.9 GB less at the same frame rate.
- **F542** — What took chunks back: hints 558 MiB, CPU writes 4 MiB, one canary hit of 18 MiB during the load.
- **F543** — The bench route does not reproduce F505's re-reads, so the gain in free play is not measured.

## Follow-up: the maintainer's test shortcut (0379 + 0380), 2026-10-29 11:30–11:55

*Added after the verdict, at the top session's request, on the maintainer's yes ("Tak, przygotuj") to a test shortcut for
two of the maintainer's play sessions with RT on. The result and verdict above are unchanged; this section records the
build, the launcher and the smoke run. Files in `test0379t/`.*

**Build** (`test0379t/build0379t.sh` + `build0379t.py`, box 11:43–11:44, into `~/bc5-work/exp0379t/`):
- a private backend archive from main's backend + this experiment's header and test + exp 0380's backend change
  (`origin/exp/0380-zero-dim-dispatch` ed68b12; `test0379t/0380-backend-ed68b12.diff`, md5 c14097de, on the merge base
  0c13576, whose backend equals main's). The two changes do not overlap: 0380 changes `direct.cpp`,
  `indirect_check.{hpp,cpp}` and their test; this experiment adds `zero_skip.hpp` and its test. The host includes neither
  `indirect_check.hpp` nor a changed `direct.hpp`, so the shared host objects link against the private archive unchanged;
- configured as the shared archive (clang, Release, `BC5_WITH_AMDGPU=ON`): **584dca77**, 0 warnings;
- the merged backend's Catch2 tests 98/98 (MSVC on the laptop as well: 98/98), `[zero_skip]` 5/5, `[indirect_check]` 10/10;
- the emulator: the shared normal objects (58c4a627) + `bc5LleAgc.cpp` with `patch0379-bc5LleAgc.diff` (e62113a5) +
  the private archive: **459d34cd**, 5 warnings (the same older ones as e1cc0c92). Strings: the exp 0380 switch lines,
  `BC5_DIRECT_FORCE_START_000`, the zero-skip and zero-scan lines;
- the shared binary, the shared archive (bb50b2e0), `~/src/KytyPlus` and `play-pkg.sh` (55531ab6) unchanged afterwards.

**Launcher** `~/bc5-work/exp0379t/play-pkg-0379t.sh` (**b3cddc1d**), made from `play-pkg.sh` 55531ab6 by
`test0379t/mkplay0379t.pl` (nine anchors, each found once; diff in `test0379t/raw/play-pkg-0379t.diff`):
- the private emulator; `BC5_LEAN`/`BC5_LOGS` cleared; `BC5_DIRECT_FORCE_START_000=1` always; `BC5_DIRECT_GPU_CHECK_ZERO`
  unset;
- the mode per start: **SCAN** while `~/bc5-work/exp0379t/play-lists/` holds no `zero-list-*.txt` (scans every 120 s
  from 240 s to 7,200 s into `scan-<start>.txt`; at the end, a list with at least 3 scans becomes
  `zero-list-<start>.txt`); otherwise **SKIP** on the newest `zero-list-*.txt`, with the canary and the take-back;
- one log and one mount log per start in `~/bc5-work/exp0379t/play/`, the first line
  `== exp 0379t mode: SCAN|SKIP <list>; BC5_DIRECT_FORCE_START_000=1; binary <md5>`;
- `play-sample0379t.sh` (e094a3f5; exp 0371's sampler) writes `play/mem-<start>.txt` once a minute (MemAvailable,
  swap, GTT, the emulator's and the mount's RSS, mount reads per minute, PSI memory/io full avg60, load). It is started
  after the mount and killed by the launcher's EXIT trap, and ends by itself when the launcher is gone.

**Shortcut** "**BC5 emulator (test 0379+0380)**" in `~/Pulpit` (`test0379t/shortcut0379t.sh`, as exp 0372's):
`distrobox enter ubuntu -- ~/bc5-work/exp0379t/play-pkg-0379t.sh`. RT on comes from the shared `input.cfg`.

**Smoke run T1** (`test0379t/s6n0379t.sh`, made from `raw/s6n0379.sh` by `mk-s6n0379t.pl`; the test launcher with the
four private paths of the S6N bench, the route saves copy, RT on, 300 s, scans at 120/180/240 s through
`BC5_0379T_SCAN_AT`; 11:45–11:50; `test0379t/raw/`):
- **pass**: 34.2 flips/s (a 300-s run, so more of it is the load than in the 420-s arms), 0 crash lines, 0 kernel amdgpu
  lines (stream and dmesg), 0 TIMEOUT, 0 devcoredumps, the learned file unchanged, live saves 1e451f8fefd534f3 before
  and after;
- the log's first line says `SCAN`; exp 0380's switch line is there, and its periodic line at the end: FORCE_START_AT_000
  set on 6,748,739 of 9,940,597 indirect dispatches (the rest had it already);
- the three scans found RenderGpuWcLarge 1,366 MiB and CommitIABufferAllocator 1,382 MiB zero in all of them
  (S1: 1,378 and 1,384); the launcher kept the 3-scan list as `zero-list-…`;
- the sampler wrote one line a minute (GTT 11,973 MiB and MemAvailable 492–590 MiB after the load; mount reads 5.4 GB a
  minute during the load, 20–38 MiB after it);
- afterwards the list, the memory record and the mount log were moved out of `play-lists/` and `play/` into
  `~/bc5-work/exp0379t/raw/` (as `T1-zero-list.txt`, `T1-play-mem.txt`, `T1-play-mount.log`): both directories are empty,
  so the maintainer's first start runs SCAN.

**For the maintainer.**
1. First play with the test shortcut: SCAN. Play as usual. A list is kept only when the session runs at least ~8 minutes
   (three scans, at 240, 360 and 480 s).
2. Second play with the same shortcut: SKIP on the first play's list. Compare `play/mem-*.txt` of the two plays: GTT,
   MemAvailable and mount reads per minute.
3. Logs: `~/bc5-work/exp0379t/play/play-<start>.log` (mode in the first line); the journal's `zero skip:` and
   `zero scan` lines are in `~/bc5-data/captures/play-<date>/gc/direct.log`.

**Undo:** delete `~/Pulpit/BC5 emulator (test 0379+0380).desktop`; `~/bc5-work/exp0379t/` can then be removed. Nothing
shared was changed, so nothing else needs undoing. To run SCAN again, move the files out of
`~/bc5-work/exp0379t/play-lists/`.
