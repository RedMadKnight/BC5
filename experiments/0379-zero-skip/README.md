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

### The maintainer's two plays with the test shortcut (2026-10-29 12:00–12:12)

Read afterwards from the box, reads only (`test0379t/raw/play/`, `test0379t/raw/play-lists/`,
`test0379t/raw/play-launcher-and-zero-lines.txt`; the comparison `test0379t/cmp0379t.py` → `raw/cmp-S1-vs-P1.txt`).

**Play 1, SCAN, 12:00:01–12:08:31** (8.5 min, exit 0). Its first log line: `mode: SCAN`. Three scans (240, 360, 480 s):

| heap | zero in all 3 scans | listed (≥ 8 MiB) | bench S1 listed | in both | bench only | play only |
|---|---|---|---|---|---|---|
| RenderGpuWcLarge | 1,098 MiB | 934 MiB in 48 runs | 1,218 MiB | 934 MiB | 284 MiB (27 runs) | 0 |
| CommitIABufferAllocator | 288 MiB | 284 MiB in 4 runs | 1,380 MiB | 276 MiB | **1,104 MiB** (3 runs) | 8 MiB |
| total | | **1,218 MiB** | 2,598 MiB | 1,210 MiB | 1,388 MiB | 8 MiB |

- In free play the title fills most of CommitIABufferAllocator: 288 MiB of it stays zero, against 1,384 MiB on the bench.
  A 1,020 MiB run at +0x6ac00000 and runs of 62 and 22 MiB that are zero on the bench hold data in this play.
  RenderGpuWcLarge loses 284 MiB in 27 runs, the largest 68 MiB at +0x98400000.
- So **1,388 MiB that was zero on the bench is written in the maintainer's play**. A list from the bench would have put those chunks
  under the canary: as many canary hits, and that much of the GPU's data lost until each hit. The list from the maintainer's own play
  avoids them. The play list is almost a subset of the bench list (8 MiB outside it).
- The maintainer's memory record (`mem-20261029-120000.txt`) is F505 again: GTT 12,338–12,429 MiB, MemAvailable 322–485 MiB after
  the load, bc5-mount reads 5.7–10.2 GB a minute, PSI io "full" 7.7–13.4 %, swap 0.8–0.9 GB.

**Play 2, SKIP, 12:09:44 until the hang at 12:12:06** (2.4 min). Its first log line names
`zero-list-20261029-120000.txt`. The skip placed RenderGpuWcLarge 934 MiB (48 runs) and CommitIABufferAllocator 284 MiB
(4 runs) behind a 52-slice canary (104 MiB). Within two minutes hints took back 183 chunks (366 MiB), no CPU writes, and
**one canary hit: run 37, file 0x1cb400000 + 24 MiB** (RenderGpuWcLarge +0x74800000), before the hang. That run was zero
in all three scans of play 1. On the bench (S1), 30 MiB around it at +0x74400000 was zero in six scans and B1 skipped it
without a hit, so which runs get hit varies between sessions. 828 MiB were still skipped at the last report.

| at ~2 min after the start | GTT used | MemAvailable | mount reads (the minute before) | PSI io full60 |
|---|---|---|---|---|
| play 1 (SCAN), 12:02:01 | 12,054 MiB | 485 MiB | 10,173 MiB | 13.4 % |
| play 2 (SKIP), 12:11:44 | 11,471 MiB | 1,079 MiB | 8,578 MiB | 13.8 % |

- At the same point of the load, SKIP has 583 MiB less GTT and 0.6 GB more MemAvailable. That fits 828 MiB skipped
  minus the 104 MiB canary. The mount reads are those of a load in both (8.1–10.2 GB/min). Two samples tell nothing
  about the steady state.
- The hang at 12:12:06 is exp 0380's to read. Exp 0380 found no sign that the skip played a part (F554, on exp 0380's
  branch).

**Recommendation.** A longer SKIP play (20 minutes or more, on the same list) is worth doing, with these expectations:
- It is the only way to see whether ~0.7 GB more page cache cuts F505's re-reads. The bench cannot show it (F543), and
  play 2 ended in the load.
- The gain in free play is ~0.7 GB, not the bench's 1.9 GB: the maintainer's list is 1.2 GB, and hints take back ~0.4 GB of it.
- The risk is the canary's, not a fault: expect a few hits (one in 2.4 minutes here) and a possible short glitch at each.
  `zero skip: canary hit` lines in the journal count them.
- For a next test shortcut (with 0380's rebase fix): one slice per run costs 104 MiB here, and sharing slices between
  runs would save most of it. A list made from a longer SCAN play, or the intersection of several plays, would carry
  fewer hits than this 3-scan list.

### The maintainer's 36-minute play on "test 0380 wb", without the skip (2026-10-29 16:25:52–17:02:29)

Read afterwards from the box, reads only, under a reads-only lock line. The files are exp 0380wb's
`play/mem-20261029-162552.txt` (the launcher's once-a-minute record) and the play log's fps counter lines
(`test0379t/wb/raw/`: the memory record, the counter and switch lines, and the per-minute join
`fpsmem-20261029-162552.txt` made by `test0379t/wb/fpsmem0379wb.py`).

- **Build:** exp 0380's c3c8660b, with `BC5_DIRECT_ARGS_WB=first` and FORCE_START. No zero skip, no copy, no rebase.
  RT on. It ran until the maintainer closed it (exit 0), with no hang. The only error lines are two `shared map at
  0x0+0x10000: -22`. The maintainer found it very unstable.
- **Overall:** 30.8 flips/s. After the first 240 s it was 32.2 flips/s. Of the seconds after 240 s, 12 % ran under 15
  flips/s and 27 % under 25. There were 137 gaps of 500 ms or more (37 of 800 ms or more), and the longest gap was 2.9 s.

**Memory.** After the load (16:30–17:02):

| measure | this play |
|---|---|
| GTT used | 12,666–12,729 MiB, still rising slowly |
| MemAvailable | 188–374 MiB |
| zram swap | 1.0–1.7 GB |
| PSI mem "full" (60 s) | 1.5–23.6 % |
| PSI io "full" (60 s) | 2.6–23.2 % |
| bc5-mount reads | 1.2–9.6 GB a minute |

- The emulator's RSS fell from 7.2 GB at the load to 0.3–1.2 GB, and bc5-mount's from 0.7 GB to 0.15 GB at the peaks.
  So the kernel was reclaiming both processes' own pages, not only the page cache. (What RSS counts for the pinned
  memfd pages is TODO(verify).)

**The frame rate follows the reads.** These are per-minute figures over the 32 minutes from 16:30 on:

| per-minute correlation with flips/s | r |
|---|---|
| bc5-mount reads in the minute | **−0.84** |
| PSI mem full60 | −0.77 |
| PSI io full60 | −0.45 |
| swap used | −0.17 |
| MemAvailable | +0.15 |

- The 9 minutes with reads under 3 GB averaged **41.2 flips/s**; the 12 minutes with 5.5 GB or more averaged **24.9**.
- The bad stretches are 16:38–16:43 (17.7–29.6 flips/s; reads 5.1–9.2 GB/min; PSI mem 9–15 %), 16:48–16:49 and
  16:59–17:02 (18.9–29.2 flips/s; reads 5.8–9.6 GB/min; PSI mem 13–24 %, the highest of the session).
- The good stretches, 16:31–16:34 and 16:50–16:57 (35–48 flips/s), are the minutes with reads at 1.2–2.8 GB/min.
- MemAvailable hardly correlates. It sits at its floor (0.2–0.3 GB) the whole time, so it shows that the box is full,
  not how badly.

**Against F505 and the 0379t plays.** At the same minute after the start, this session pins about 300 MiB more GTT than
play 1 of the 0379t shortcut (12,639 against 12,342 MiB at ~4 min). Over 36 minutes it reaches the deepest pressure
recorded so far:

| | F505 (23:32–23:36) | 0379t play 1, SCAN (12:00–12:08) | 0379t play 2, SKIP (12:09–12:12, load only) | this play (16:30–17:02) |
|---|---|---|---|---|
| GTT used | 11,967–12,402 MiB | 12,338–12,429 MiB | 11,471 MiB at 2 min | 12,666–12,729 MiB |
| MemAvailable | 536–724 MiB | 322–485 MiB | 1,079 MiB at 2 min | 188–374 MiB |
| swap | 592–929 MiB | 0.8–0.9 GB | 0.57 GB | 1.0–1.7 GB |
| PSI mem full60 | — | 0.2–1.8 % | 0.06 % | up to 23.6 % |
| mount reads | 3.0–4.4 GB/min | 5.7–10.2 GB/min | 8.2–8.6 GB/min (load) | 1.2–9.6 GB/min |

- PSI mem "full" is new: up to 24 % of the time, every task waited on memory. That is reclaim stalls, on top of F505's
  I/O stalls.
- The ~300 MiB more GTT than play 1 has no cause recorded. ARGS_WB adds no BO, so it is likely the scene or the
  session; this is not checked.

**The frame rate against the 0379t plays.** These are the same per-minute joins, from the fps counter lines read under
a second reads-only lock: `test0379t/raw/play/play-*-fps.txt` and `fpsmem-*.txt`.

| minute after the start | 1 | 2 | 3 | 4–8 |
|---|---|---|---|---|
| play 1, SCAN | 21.5 | 15.2 | 21.2 | 20.6–31.5 (reads 5.7–7.7 GB/min) |
| play 2, SKIP | 16.7 | 21.9 | 17.4 (to the hang) | — |
| this play | 19.5 | 15.6 | 16.1 | 27.9–43.1 (reads 1.8–6.7 GB/min) |

- **The loads look alike.** In the first three minutes all three plays run at 15–22 flips/s, with reads of 8–13 GB a
  minute and gaps of up to 1.5–2 s. The skip's 0.6 GB more MemAvailable at minute 2 shows no frame-rate difference
  there. That is expected: the load reads data the title has not read yet, so more page cache cannot help it.
- **Play 1's steady minutes fit this play's relation.** Its reads stayed at 5.7–7.7 GB a minute and it ran 20–31
  flips/s, close to this play's 24.9-flips/s average for minutes with reads of 5.5 GB or more.
- **No steady-state minute with the skip exists yet.** Play 2 hung at 2.4 min, still in the load. So the question F632
  asked, whether ~0.7 GB more cache lowers the steady reads, is still open.

**Should the skip go into the next test build with ARGS_WB?** Yes. The reasons:

- The two do not touch each other. ARGS_WB is in the backend archive (`backend/src/direct.cpp`). The skip is in the
  host's `bc5LleAgc.cpp`. The 0379t build already linked the skip with an exp 0380 archive by an archive swap (459d34cd,
  smoke run passed), and that method carries over.
- The session above is what the skip is for. Its frame rate falls when the box re-reads (r = −0.84) and stalls on
  reclaim (PSI mem up to 24 %), with MemAvailable at 0.2–0.3 GB. Play 2 showed that the 1.2 GB list frees ~0.6 GB at
  the load (F631), roughly two to three times this session's MemAvailable.
- Whether that cuts the re-reads and the reclaim stalls in a 30-minute play is still unmeasured. This would be the
  measurement.

What to set up, and what to watch:

- Start it in SKIP mode directly, on `zero-list-20261029-120000.txt`. A SCAN start would spend one play without the
  skip. The launcher checks each heap's size, so a title update falls back to a full import.
- It does not blur ARGS_WB's question, whether a sub-class B hang still comes. The skip never stalls the GPU and
  carries no new submission, and exp 0380 found no part for it in the 12:12 hang (F554). A hang's devcoredump and the
  journal's `zero skip:` lines still show what the skip held at that moment.
- Expect a few canary hits, each a possible one-frame glitch. Their count goes in the record.
- Add PSI mem "full" and the per-minute flips/s to the play's own summary, so the comparison with this session is
  direct.

**What else would cut pinned memory (F402's levers, and what is left of them).** F353 puts ~90 % of the ~12 GB pinned in
the eager list. Of that, RenderGpuWcLarge is 2.7 GB, CommitIABufferAllocator 2.7 GB and the AMM pool 3.1 GB in
18,661 small pages. In order of what each could give:

1. **The zero skip on the play list, ~0.6–0.7 GB in play** (this experiment).
2. **The zero scan on the other eager heaps and on the AMM pool: not measured; the AMM pool (3.1 GB) could be the largest.**
   About 1.5 GB of the eager list lies outside the two render heaps and the AMM pool (F353: ~10.1 of 11.2 GB imported is
   eager, 8.6 GB of it in those three). Its zero share is unknown, and so is the AMM pool's.
   - Measuring the heaps is cheap: one SCAN play with `BC5_DIRECT_ZERO_NAMES` set to every eager heap name, with no
     new code.
   - The AMM pool's small pages need a per-view list. Today's list is per named heap. That would be new code, and its
     own experiment.
3. **Narrower learned windows: up to ~0.7 GB, and only outside the eager heaps.**
   - Inside the two render heaps the windows change nothing, because those heaps are imported in full (Design).
   - F353's 61 windows cover 3.9 GB, and F402 puts 3.2 GB of that inside the render heaps. The rest, ≤ 0.7 GB, is the
     only part a narrower window (for example 16 MiB around the fault instead of 96) could free. These counts are from
     exp 0288 and exp 0333, and the learned file has changed since (F473). Which heaps hold that remainder today is
     TODO(verify), from one breakdown run (`BC5_DIRECT_BREAKDOWN_AT`, F353).
   - The risk is a fault where a window used to cover the address: F473 shows how the learned list grows one hang at a
     time.
4. **Shared canary slices, ~0.1 GB.** Today each skipped run gets its own 2 MiB slice, 104 MiB for this list. One
   slice per heap would do if a hit is attributed by a second step instead of by slice. This is a code change in the
   skip.
5. **Not pinned, but the same page cache:**
   - the normal build's journal and logs: the lean build swapped about 10× less (F353);
   - bc5-mount's ~0.7 GB RSS (`MALLOC_ARENA_MAX=2` is in already);
   - the reads' amplification (F396: about 3× what the emulator is served). F505 shows the re-reads outlive F398's fix.

   Using the lean build in the play shortcut is a launcher choice, not code.
- **Not a lever:** making the render heaps lazy brings back F96's faults and freezes (Design). Lowering
  `KYTY_GUEST_MEMORY_MB` saves nothing (F353).

### Why GTT grows in play, the next levers, and a 20-minute bench test (2026-10-29 evening, laptop only)

Findings: F630–F632 are the two test-shortcut plays' section. They were first numbered F563–F565, which exp 0380's
branch also uses, and were renumbered on 2026-10-30. Findings: F620–F622 are the 36-minute play section above. They were first numbered F582–F584, which exp 0380's
branch also uses, and were renumbered on 2026-10-29 evening. F623–F626 are this section's.

This section was written at the top session's request. It uses the existing records: exp 0380's 21:33 play
`PLAY-2133-mem.txt` (on exp 0380's branch), this experiment's plays and bench runs, and main's patch 0001. No box access.

**1. Where the 1.3 GB comes from.**

- **Most of it is the load.** In the 21:33 play GTT went from 11,437 MB at 1 min to 12,149 MB at 2 min. Those
  712 MB are the load still running, since 11.4 GB is reached within ~160 s (F353, and A1 here). After the load it grew
  only 553 MB in 19 minutes, to 12,702 MB.
- **The growth after the load comes in steps, never down.** The steps were +119, +88, +39, +82 and +113 MB, at 21:39,
  21:40, 21:43, 21:45 and 21:50, with flat minutes between. Two other plays grew less: the 16:25 play +344 MB in 34 min
  (12,385 → 12,729), and the 12:00 SCAN play +375 MB in 6 min (12,054 → 12,429). F353 had +0.5 GB in 29 min with
  RT off.
- **On the bench it is flat.** A1 (shared build) and B1 (skip) reached 11,992 and 10,080 MiB at 180 s and stayed there to
  421 s, at the same frame. So the growth follows the play's movement through the game world, not time. That does not
  rule out a host leak, since a leak can depend on streaming as well (Codex review, REVIEW-02). The device-wide GTT
  cannot tell apart live data, data the title freed but the host retains, and other clients.

**What the code allows** (patch 0001, `bc5LleAgc.cpp` `direct_sync_one`; `memory.cpp` `PhysicalMemory::Alloc`,
`ReleaseDirectMemoryInternal`):

- **No duplicate imports.** A chunk is imported only when `direct_covered_end` finds no BO covering its memfd offset,
  so a memfd chunk is pinned once however many views (aliases) map it.
- **No duplicate or stale GPU mappings.** Each rebuild computes the wanted (view × BO) set and unmaps every mapping no
  view asks for ("drop what no view asks for any more"). A1's end state is stable: 19,396 views and 19,431 mappings.
- **But nothing is ever released.** `S.bos` only grows. The merge replaces BOs with one covering the same range, and
  the old ones are freed in the same sync, so the extra is at most the 256 MiB merge budget for a moment.
  - When the title releases direct memory, `ReleaseDirectMemoryInternal` unmaps the GPU and CPU aliases and frees the
    physical block. The imported BO stays, and the memfd is never punched: the patch has no `FALLOC_FL_PUNCH_HOLE` and
    no `MADV_REMOVE`.
  - So pinned memory is a high-water mark: every memfd chunk that ever held data, or was forced by a hint or a learned
    window, stays pinned to the end.
- **Freed memory is reused before new memory is touched.** The physical allocator is first-fit from the bottom of the
  search range (`m_free.upper_bound(search_start)`). A freed and re-allocated block lands on chunks that are already
  pinned, so churn costs nothing new. The high-water mark rises only when the title's allocations reach chunks never
  written before.
- **Part of GTT is not the direct path's at all.** On the bench, A1's journal shows 11,338 MiB pinned by the direct
  path against 11,992 MiB of GTT used. The other ~650 MiB belongs to other clients: the emulator's Vulkan side (RADV),
  the compositor and the rest of the desktop. Its growth in play is not measured; `mem_info_gtt_used` counts the whole
  device.

**Answer:** the code shows no duplicate import or mapping. The growth after the load is the title filling more of its own direct-memory
reservation as new areas stream in. The host keeps all of it pinned for good. It never gives back a chunk the title has
freed and not reused, and it never punches the memfd.

- How much of the 12.7 GB is "freed by the title but still pinned" is not recorded. First-fit reuse suggests it is
  small. TODO(verify): a diagnostic would compare, at one moment, the imported chunks against `m_physical`'s
  allocated blocks.
- How the growth splits between the direct path and the Vulkan side is not recorded either. The test below records
  it.

**2. The next levers beyond the zero skip, ranked by expected gain over risk.**

| # | lever | expected gain | risk | cost to try |
|---|---|---|---|---|
| 1 | Zero scan of the other eager heaps (~1.5 GB) and the AMM pool (3.1 GB in 18,661 small pages); skip what stays zero | unknown; the pool could be the largest, by size | as the skip: canary hits, no faults | heaps: one SCAN play with every eager name, no code; pool: a per-view list (new code) |
| 2 | Find what the non-direct ~0.65 GB GTT is (RADV allocations: display buffers, the tiler pool's 96 MiB, F311) | part of 0.65 GB, unknown | low; measurement first | the per-client sampler below |
| 3 | Less page-cache churn from the normal build's journal and logs (the lean build swapped ~10× less, F353) | not pinned, but it eases the reclaim that F620 ties to the slow minutes | none for correctness; exp 0380 loses the journal it reads | a launcher choice (the maintainer's) |
| 4 | Release imports the title has freed: free the BO and punch the memfd for fully freed chunks | the "freed but pinned" share, likely small (first-fit) | medium-high: needs a BO split (merged BOs span up to 256 MiB+), a drain before the free, and a race with the title's next allocation; exp 0333's phase R had the same problems | code; a diagnostic first to size it |
| 5 | Narrower learned windows outside the eager heaps (F622) | ≤ ~0.7 GB | a fault where a window used to cover (F473) | code + a breakdown run |
| 6 | Shared canary slices | ~0.1 GB | low | code in the skip |

- **Not levers:** lazy render heaps (F96's faults); a smaller `KYTY_GUEST_MEMORY_MB` (F353); the box's swap and VM
  settings (the maintainer's, root).

**3. Proposed bench test (G1/G2): 20 minutes per arm, with the GTT split by client.**

- **Question:** over 20 minutes, does GTT grow on a standing route? If it does, that growth is the host's, since
  the title loads nothing new there. And how much of GTT is the direct path's against the Vulkan side, with and without
  the skip?
- **Route:** the S6N route as in A1/B1. That means exp 0203's `o2-continue.cmd`, exp 0196's route saves in a private
  save copy, a private wd, and the live saves only compared. RT on, 1,200 s per arm.
  - The runner itself does not drop the page cache, although the Setup above says each arm starts empty. Here
    `sync` and `drop_caches` are an explicit pre-step of each arm, logged to `gtt/raw/<tag>-dropcaches.txt`, and only
    with a passwordless `sudo -n` (Codex review, REVIEW-02).
- **Arms:**
  - Both arms run the same private binary, e1cc0c92: G1 with the zero skip off, G2 with `BC5_DIRECT_ZERO_SKIP` on the
    maintainer's 1.2-GB list (`exp0379t/play-lists/zero-list-20261029-120000.txt`). So one factor differs (Codex
    review, REVIEW-02).
  - At 120 s the runner also writes every `drm-` key of every fd with the fd's target (`<tag>-fdinfo-full.txt`). That
    tells the direct path's client from RADV's, and shows whether the imported udmabuf counts. A missing key is NA.
  - No leak fix is in either arm, because the code shows no leak to fix. G1's minute-by-minute GTT is the leak test.
- **Scripts:**
  - `gtt/s6n0379m.sh` (made by `gtt/mk-s6n0379m.pl` from `raw/s6n0379.sh`): the cap is raised to 1,500 s and the
    sampler swapped.
  - `gtt/sample0379m.sh`: `raw/sample0379.sh` plus one `c<client>=<GTT>/<resident>` field per DRM client of the
    emulator, from fdinfo. A missing field prints `?` (unknown), never 0. TODO(verify) the key names on 7.2.9, and that
    the udmabuf imports count in their client's `drm-total-gtt`. Both are checked on the box's real fdinfo at the run's
    pin step.
  - The first version (2e99306) had a literal newline inside the awk program's `printf`. Awk failed on it, the
    sampler's `2> /dev/null` hid the failure, and the run would have recorded no client field at all. My earlier dry
    run had used a hand-typed copy of the program, not the script's text. Codex review (REVIEW-02) found it.
    `gtt/test_sample0379m.py` now runs the script's own `fd=` pipeline through Git Bash on stand-in fdinfo files: two
    fds of one client, the older key, a client with no GTT field, and a non-DRM fd. It passes; the 2e99306 text fails
    it.
  - At the pin step on 2026-10-30 the box's 7.2.9 fdinfo turned out to print both `drm-memory-gtt` and
    `drm-total-gtt`, plus `drm-shared-gtt` (the dma-buf shared part).
    - So the sampler now prefers total and falls back to memory, and records `c<id>=<total>/<resident>/<shared>`
      (sampler md5 39ceea8d).
    - The script's own pipeline ran on plasma-keyboard's real fds (the compositor's fdinfo was not readable) and gave
      `c23=30/92/0`, with total 30,736 KiB against resident 94,384 KiB. So total and resident differ on this kernel, and
      both are kept.
  - `gtt/stream0379m.sh`: the kernel stream into `gtt/raw/`.
- **What it records:** per 10 s, GTT used per client, MemAvailable, swap, PSI mem/io full, mount reads, and the
  emulator's RSS. From the journal, the direct path's pinned total (`*-pinned-every20.txt`), the canary hits and the
  take-backs. Also flips/s, kernel lines and the live-save checksum.
- **Pass, and what each outcome means:**
  - G1's GTT within ±32 MiB of its 180-s value through 1,200 s means no host growth while standing (it does not rule
    out growth tied to streaming). More than that,
    with the direct client's GTT flat, puts the growth on the Vulkan side. If the direct client grows, it is the
    host's import path.
  - G2 should hold its skip for 20 minutes: canary hits counted, and its GTT difference to G1 measured at 180 s and at
    1,200 s.
  - Both must pass with flips/s within ~1 of each other, 0 kernel lines, and the saves unchanged.
- **What it cannot show:** the minute-16 pressure of the plays. The S6N route stands still, so its steady reads are
  21–25 MiB/min (F543) and its GTT plateaus at 180 s. For that, a moving route is needed, such as exp 0360's
  pad-record replay from the 47aefd45 save copy. Its length and coverage need checking first. Otherwise, a longer
  SKIP play by the maintainer.
- **Box time:** about 50 min. That is 2 × (1,200 s + ~3 min of setup and checks) plus ~5 min of reads before (pins,
  the list's md5, copying the three scripts).

### G1/G2 result (2026-10-30 00:01–00:42, the top session's GO)

**Setup as proposed, with Codex review (REVIEW-02)'s changes:**
- Both arms ran the same private binary, e1cc0c92: G1 with the skip off, G2 with `BC5_DIRECT_ZERO_SKIP` on the
  maintainer's list (7a4f972c, copied to `exp0379/zero-list-G2.txt`).
- S6N route, RT on, 1,200 s per arm, `gtt/s6n0379m.sh` (c88305c1) with `gtt/sample0379m.sh` (39ceea8d).
- Before each arm, `sync` and `drop_caches` ran as a logged pre-step (`gtt/raw/G?-dropcaches.txt`). `sudo -n tee` is
  passwordless for that file only.
- Pins: shared normal 58c4a627, `play-pkg.sh` 55531ab6, learned file a7cc8581 (109 windows), kernel 7.2.9-ogc3.1,
  live saves 377a8d456a9b4cb1.

**Both arms passed** (`gtt/raw/G?-summary.txt`). Each ran 37.6 flips/s (44,954 and 44,940 flips), with 0 crash,
TIMEOUT or compute-ring lines and 0 devcoredumps. The laptop's kernel streams hold only IPv6 MLD lines, no amdgpu
line. The live saves were unchanged after each arm.

**GTT does not grow on the standing route** (`gtt/ana0379g.py` → per minute):

| | G1, skip off | G2, skip on | G1 − G2 |
|---|---|---|---|
| GTT used at 3 min | 12,049 MiB | 11,333 MiB | 716 MiB |
| GTT used at 20 min | 12,049 MiB | 11,333 MiB | 716 MiB |
| direct client (fds 48/49) total / shared GTT | 11,694 / 11,602 MiB | 10,978 / 10,886 MiB | 716 / 716 |
| RADV client (fds 12/13) total GTT | 117 MiB (179 resident; 313 MiB VRAM) | 117 MiB | 0 |
| rest of the device (desktop) | ~238 MiB | ~238 MiB | 0 |
| direct path's journal, pinned at the end | 11,328 MiB | 10,508 MiB | 820 |
| MemAvailable, minutes 4–20 | 544–573 MiB | 1,227–1,294 MiB | −0.71 GB |
| PSI mem / io full, minutes 4–20 | 0.00–0.01 % / 0.04–0.21 % | 0.00–0.01 % / 0.05–0.16 % | — |
| mount reads, minutes 4–20 | 0–33 MiB a minute | 0–34 MiB a minute | — |

- **No growth while standing.** Over 17 minutes, from minute 3 to minute 20, neither arm's GTT changed by one MiB, and
  neither did any client's. That fits F623/F624: nothing in the host grows by itself. It does not test growth that
  depends on streaming, because this route streams nothing after the load.
- **Clients told apart.** The direct path is the client on fds 48/49. Nearly all of its GTT (99 %) is shared: the
  udmabuf imports count in its `drm-total-gtt` and its `drm-shared-gtt`. This answers the TODO(verify) in F626.
  RADV's client (fds 12/13) holds only 117 MiB of GTT. The ~650 MiB outside the direct path's pinned total that F623
  named is therefore:
  - ~366 MiB of the direct client's own (the gap between its fdinfo total and the journal's pinned total);
  - ~117 MiB RADV;
  - ~238 MiB the rest of the device.
- **The skip held 0.72 GB for 20 minutes.** G2's journal (`gtt/raw/G2-zero.txt`):
  - 1,218 MiB was placed. 824 MiB was still skipped from the first minutes to the end.
  - Hints took back 193 chunks (386 MiB) and CPU writes none.
  - There was one canary hit: run 49, CommitIABufferAllocator, file 0x230a00000 + 8 MiB, the same 8-MiB size as
    NC1's.
  - 824 MiB minus the 104-MiB canary is 720 MiB, the measured gap of 716 MiB.
- **What it does not show:** the plays' minute-16 pressure. Both arms stand at PSI ≈ 0 with reads of 0–34 MiB a
  minute, as F543 predicted. Whether the 0.7 GB eases that pressure still needs a moving route or a long SKIP play.

### Proposed moving-route bench G3/G4 (2026-10-30, laptop only, not run)

**The fight route doesn't fit.** The top session named exp 0360's fight route as a candidate, but it holds only 5.3 s of
the maintainer's gameplay inputs (his 14:50 record, F464), after which the character stands. A time-based pad replay
also loses his path within about a minute (F446: at 52 s). And the box keeps only the latest start's record
(`~/bc5-work/route-record.txt`), not the save it started from. So no recorded route streams for 20 minutes.

**A synthetic walk instead.**
- `gtt/mk-walk0379.py` writes `gtt/walk0379.cmd`:
  - exp 0203's `o2-continue.cmd` menu on the S6N route save, then a 30-s load;
  - then 70 cycles to 1,273 s: the left stick fully forward for 15 s, a right-stick camera turn of 1.2 s, and a 0.3-s
    pause;
  - the turn goes right for four cycles, then left for four, so the path sweeps instead of circling;
  - no button after the menu.
- The stick syntax is exp 0061's `route.cmd` and exp 0180's `record-run.sh` (`stick l 128 0 <ms>`).
- Whether the walk leaves the S6N area and streams is the open part. It may meet walls, enemies or a death reload, all
  of which still stream.

**Runner.** `gtt/s6n0379m.sh` takes `BC5_0379_ROUTE=<input script>` in place of `o2-continue.cmd` (`gtt/mk-s6n0379m.pl`,
one more anchor). Everything else is G1/G2's:
- the same binary e1cc0c92, skip off (G3) and on (G4);
- RT on, 1,200 s per arm, drop_caches logged before each;
- the per-client fdinfo sampler every 10 s;
- flips per 10 s, the kernel stream, and a stop at any amdgpu line.

**Gate.** G4 runs only if G3 streams. After minute 4, G3's mount reads must stay above ~200 MiB a minute in most
minutes, against G1's 0–33, and PSI mem or io "full" must be above 0. Otherwise G3 is reported and G4 is not run.

### G3/G4 result (2026-10-30 00:50–00:53): G3 hung the GPU about 2 minutes in, before the walk began; G4 not run

The run had the top session's GO. G3 was e1cc0c92 with the zero skip OFF, RT on, the walk route
(`gtt/walk0379.cmd`), and the runner `gtt/s6n0379m.sh` (02f9133d).
- Pins were unchanged: shared normal 58c4a627, `play-pkg.sh` 55531ab6, the list 7a4f972c, live saves
  377a8d456a9b4cb1.
- `drop_caches` ran as the logged pre-step at 00:50:35.

**What is recorded.** These are raw facts only; exp 0380 classifies the hang against F403's classes.

- **Timeline.**
  - The last fps counter line in the private `play-last.log` is t 114.1 s, at 33–44 flips/s from t 109 to 114:
    gameplay after the Continue load.
  - The gfx ring stalled about 3 s later.
  - The first walk input was due at t ≈ 118.2 s (85 s + 3.2 s of menu presses + the 30-s load wait). So at the hang
    the title had received only the S6N route's own inputs. G1 and G2 ran that same start without a hang.
- **Kernel** (`gtt/raw/G3-kernel-stream.txt`):
  - At 00:52:38 "Dumping IP State", then a devcoredump was created.
  - `ring gfx_0.0.0 timeout, signaled seq=8353704, emitted seq=8353706`, in process kyty_emulator, thread `bc5-ring`.
  - `Ring gfx_0.0.0 reset failed`, then "GPU reset begin!".
  - bc5-gpu-watch then synced and crashed the kernel for a reboot (SysRq s, c).
  - The box was back at 00:53:11 (boot b30ad76b), with bc5-gpu-watch and bc5-gpu-stall-sampler active again.
- **Stall sampler event** (private: `~/bc5-data/captures/gpu-stall/event-20261030-005238-gfx_0.0.0/`):
  - "stall clock 1.92 s on gfx_0.0.0", five register samples, no wave scan.
  - In every sample: `CP_PFP_INSTR_PNTR` 0xea0–0xea1, `CP_ME_INSTR_PNTR` 0x779–0x77b, `CP_IB1_BUFSZ` 0x1ae8.
  - The launched compute state was program 0x11d02a1600, dim [1599230800 1279809090 988715737], threads [64 1 1],
    initiator 0x41, on gfx ME0 pipe0 queue0.
  - `stalls.log` holds no line for this event.
- **Memory** at the last sample, 9 s before the stall (`gtt/raw/G3-mem.txt`): GTT used 10,644 MiB and MemAvailable
  2,015 MiB, with the load still growing. The direct client held 10,417 MiB of GTT and RADV 117.
- **Private captures, not committed:**
  - `~/bc5-data/captures/devcoredump/20261030-005238-devcd1.txt`;
  - four pstore records of 00:53:24 in `~/bc5-data/captures/pstore/`.
- **Saves:** the live saves were 377a8d456a9b4cb1 after the reboot, unchanged.

**Consequences for G3/G4.**
- The gate was never reached, and G4 (skip on) was not run.
- The walk route is untested: no walk input was ever sent.
- The skip played no part, since it was off.

### G3b, the G3 repeat (2026-10-30 00:56–01:17): passed, but the walk did not stream; G4b not run

This run was the top session's second GO, on the same pins, scripts and arm as G3: e1cc0c92 with the skip off, RT on,
the walk route, and drop_caches logged before the run.
- **Clean pass.** It ran 39.2 flips/s against G1's 37.6, with 0 crash, TIMEOUT or amdgpu lines and 0 devcoredumps. The
  live saves were unchanged. One kernel line not from the GPU: 00:58:56 "clocksource: Watchdog remote CPU 2 read
  timed out".
- **The gate failed.** From minute 4 to minute 20, mount reads were 0–33 MiB a minute and PSI mem/io "full" was about
  0. GTT was flat at 12,005 MiB from minute 3 (the direct client 11,689, RADV 117). That is G1's standing picture
  (`gtt/raw/G3b-mem.txt`).
- **The input script ran to its end.** `in-G3b.cmd.done` reads 144, written at 01:16, for the script's 147 non-wait
  commands. So the stick inputs were sent. Whether the character moved is not recorded: no screenshot was taken, and
  viewing one needs the maintainer's leave. The higher frame rate suggests the view changed.
- **Not checked** (any of these fits): the S6N spot is enclosed; the forward stick does not move the character there
  (a menu, a cutscene or another control state); or walking there loads nothing new.
- **This walk does not reach the plays' pressure.** A streaming bench needs a route checked by eye first (a few
  screenshots across the walk), or another start point.
- G3's hang (F633) did not recur on the same start in G3b.

### Route diagnosis D1 and D2 (2026-10-30 01:19–01:27, the top session's leave for private screenshots)

**D1** (01:19:30–01:23:47): e1cc0c92 with the skip off, RT on, the S6N start with the walk, 240 s, and full-screen shots
at 105, 120, 150 and 210 s.
- The shots were taken on the box into `~/bc5-data/captures/exp0379/shots/` (private). Three were viewed on the
  laptop and then deleted there. None is in the repo.
- D1 passed: 32.5 flips/s, 0 kernel lines, saves unchanged.
- **Diagnosis:** the S6N save does not start in free movement.
  - After the Continue load the title plays an in-engine cutscene, still running at 150 s, where stick input does
    nothing.
  - At 210 s the gameplay is a scripted fight in an enclosed yard, with a combat tutorial prompt on screen.
  - The walk cannot leave either, so nothing new streams. This explains G3b (F634) and the bench's flat reads
    (F543, F627).

**D2** (01:25:43–01:27:16): the same arm and walk, started from a private copy of the maintainer's current live saves
(`exp0379/saves-live-377a8d45`, sum 377a8d456a9b4cb1, copied into the wd as the route saves are). The menu was cross,
cross (slot 1), cross, and there was a slot-list shot at 89 s. **It hung before the menu, so no shot was taken.**
These are raw facts; the classification is exp 0380's.
- **Page faults:** from 01:26:41.588 the kernel logged repeated gfxhub page faults (ring 24, vmid 7) in kyty_emulator,
  thread `bc5-ring`.
  - The addresses were 0x8608c654000, 0x8608c659000, 0x8608c65a000 and so on.
  - UTCL2 client TCP, `GCVM_L2_PROTECTION_FAULT_STATUS` 0x00701031, PERMISSION_FAULTS 0x3, MAPPING_ERROR 0, RW 0.
- **Timeout:** at 01:26:43.6 `ring gfx_0.0.0 timeout` (signaled 2325648, emitted 2325650), then "Ring gfx_0.0.0 reset
  succeeded" and "device wedged, but no recovery needed".
  - bc5-gpu-watch armed and then disarmed, with no reboot.
  - The runner's verdict: "HANG: kernel amdgpu line at 61 s, ring reset succeeded".
  - At the time: 1,148 flips in 52.4 s, 24,801 views, and 10,130 MiB pinned. The input script's first key was due at
    85 s.
- **Stall event** (private, `gpu-stall/event-20261030-012643-gfx_0.0.0`; one `stalls.log` line, dur 2.04 s):
  - sample 1: PFP 0xea1, ME 0xe15, `CP_IB1_BUFSZ` 0x38f8;
  - compute program 0x909977100, dim [697 1 1], threads [64 1 1], initiator 0x61.
- **Devcoredump:** `20261030-012643-devcd1.txt` (private).
- **Stopped by me:** I sent TERM to the emulator at 01:26:51 (stop at any amdgpu line). The live saves were unchanged.
- **Not run:** a slot-4 repeat (the top session's hint: his current progress is in slot 4) and G3/G4. Both wait for
  the top session.

### D3 and D4, and the night's start-up event rate (2026-10-30 01:30–01:37)

These ran under the top session's GO for D3 (slot 4, with shots), with one retry allowed after a GPU event before the
menu. The arm, pins and drop_caches pre-step were as before. Both runs started from the live-save copy.

**D3** (`gtt/walk0379d3.cmd`, the slot-4 keys from 85 s): it passed, with no kernel line. The menu keys came too early
for this save set, so the save never loaded.
- At 88.5 s the title's "Continue game" menu was still loading at about 5 fps.
- The down and cross presses were dropped, and the menu was still up at 125 s and 210 s.
- Three shots were viewed and deleted from the laptop; they stay private on the box.

**D4** (`gtt/walk0379d4.cmd`: cross at 85 s, Continue at 100 s) hung at t 61 s, before its first key, exactly as D2 did.
These are raw facts; the classification is exp 0380's.
- gfxhub page faults from 01:36:38.387: TCP, a read, PERMISSION_FAULTS 0x3, status 0x00701031.
  - Pages 0x8608c654000–0x8608c65b000; D2 had the same pages plus 0x8608c65d000.
- At 01:36:40.408 `ring gfx_0.0.0 timeout` (signaled 2574054, emitted 2574056), this time in thread `Render Thread`.
  - The ring reset succeeded, and bc5-gpu-watch disarmed.
- Stall event `gpu-stall/event-20261030-013640-gfx_0.0.0` (private): the same compute program 0x909977100 as D2, dim
  [697 1 1], PFP 0xea1, ME 0xe15, `CP_IB1_BUFSZ` 0x38f8. Devcoredump `20261030-013640-devcd2.txt` (private).
- At the hang: 1,145 flips in 52.9 s, 24,744 views and 10,124 MiB pinned. D2 had 1,148, 24,801 and 10,130.
- I stopped the emulator at 01:36:47. The live saves were unchanged.

**The night's start-up event rate** (all starts on e1cc0c92, skip off, RT on, page cache dropped before each):

| start saves | starts | GPU event before the menu (< 85 s) | GPU event after the load |
|---|---|---|---|
| exp 0196's S6N route saves | 5 (G1, G2, G3, G3b, D1) | 0 | 1 (G3 at ~117 s, F633: ring reset failed, reboot) |
| a copy of the live saves 377a8d45 | 3 (D2, D3, D4) | 2 (D2, D4: same pages, program and dims, both at t 61 s) | 0 |

- Before the menu, the title has only read the saves for its menu. The two starts differ only in the save directory
  copied into the private wd.
- Whether the save set matters, or the two events and D3's clean start are chance, is not decided by 3 starts.
- **G3/G4 were stopped for the night** under the top session's rule: a second pre-menu event. The walk route from the
  live saves (`walk0379s4.cmd`, `menu-continue.cmd`) is prepared and untested.
