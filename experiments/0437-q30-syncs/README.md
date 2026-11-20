# 0437 — Q30: the host's long submission syncs and the in-play dips

**Question.** What makes the host's submission syncs last up to 0.85 s (HANDOFF Q30), what in the sync drives the
second title's brief frame-rate dips in play, and what is the simplest fix to put into the next test build?

**Setup.** Offline, on the laptop, 2026-11-20, no box access. Sources:

- exp 0430's full `direct.log` journals copied to the laptop on 2026-11-18 (outside the repo,
  `Downloads/bc5/data-0430/`; md5 in `raw/sources.md5`): eight route/scene runs h430H4, H5, I1, I2, J2, M1, M2, M3
  (1,000-1,610 s each) and the maintainer's 57-minute play of 2026-11-18 (`play-f18`, 3,156 s, F858/F859), all on
  exp 0432's build 5 code (the d432 line names it: unmap-nowait ON, anon-thread ON, views-kept off, maps-fast ON);
- exp 0432's README (Result 3's per-job records, Result 7) and the patch `0001` `bb04219b` on main (exp 0436 in it);
- readers: `frames0437.py` (the game thread's "frame profile" lines), `split0437.py` (the "timing split over 128
  submissions" lines, all submitting threads). Outputs in `raw/`.

The candidate was written against a KytyPlus `f266548` tree with `0001` `bb04219b` applied (on the laptop, the three
touched files converted to LF as on the box) and tested on the laptop with `test_vg437.sh` (VS clang 22).

## Result

### 1. The 0.85 s sync is the first submission of the process, at start-up, not in play

The d432 counter "sync+hints longest" is set in the first 0.8-1.4 s of every run, before the first frame line, and
never exceeded afterwards (`raw/longest-per-run.txt`):

| run | longest (ms), set by | longest at the end of the run | runtime |
|---|---|---|---|
| h430H4 | 853.3 at t 0.9 s | 853.3 | 1,421 s |
| h430H5 | 841.5 at t 0.8 s | 841.5 | 1,001 s |
| h430I1 | 847.2 at t 0.8 s | 847.2 | 1,603 s |
| h430I2 | 844.9 at t 0.8 s | 844.9 | 1,601 s |
| h430J2 | 1,365.2 at t 1.4 s | 1,365.2 | 1,602 s |
| h430M1 | 829.9 at t 0.8 s | 829.9 | 1,601 s |
| h430M2 | 826.0 at t 0.8 s | 826.0 | 1,601 s |
| h430M3 | 1,394.0 at t 1.4 s | 1,394.0 | 1,602 s |
| play-f18 | 822.0 at t 0.8 s | 822.0 | 3,156 s |

9 of 9 runs. At t 0.8 s the counter reads "over 20 ms 1": that one submission. The first "timing split" line of each
run carries it: e.g. h430H4 "direct sync 1571.0 (... scan 1557.8 ...)", play-f18 "direct sync 1501.5 (... scan
1489.4 ...)". The scan's time is `ls415_import` (`bc5LleAgc.cpp`, `direct_sync_one` step 1, `g_dev->import_memfd`):
the first sync imports the eager heaps that exist at that moment, 3,952 MiB at t 1 s by the lazy-release line of
u436sS4 (exp 0436 raw). exp 0432 Result 3 had already named the same two jobs as frame 0 (+0.0 and +0.9 s) of every
run; this confirms it on nine more runs, including his play. It happens before the title's first frame, so the
player cannot see it as a stutter, and it is not what the dips are. Q30's headline number is a start-up cost
(the gameplay import), with no in-play counterpart of that size.

### 2. What the in-play syncs are made of

Game thread, from t 130 s on (`raw/frames0437-out.txt`; "sync" of the frame profile line):

| | h430H4 (scene) | h430M1 (scene) | play-f18 (his play) |
|---|---|---|---|
| frames | 58,673 | 62,109 | 113,009 |
| frames with sync 20-50 ms | 458 (12.5 s) | 546 (15.3 s) | 563 (17.6 s) |
| frames with sync 50-100 ms | 1 | 1 | 1,065 (66.8 s) |
| frames with sync over 100 ms | 0 | 0 | 10 (1.2 s, longest 175.7 ms) |
| frame periods 50-100 ms, of them with sync over 20 ms | 208, 150 | 320, 259 | 4,317, 1,343 |
| frame periods over 100 ms, of them with sync over 20 ms | 4, 2 | 5, 3 | 372, 209 |

So the scripted scenes hardly show it; his free play does: about a third of his 50-100 ms frames and over half of
his 100 ms+ frames have more than 20 ms of sync on the game thread.

All submitting threads, the 128-submission windows from t 130 s (`raw/split0437-out.txt`), seconds:

| part | h430H4 | h430M1 | play-f18 |
|---|---|---|---|
| views (the direct view list) | 10.9 | 25.3 | **128.1** |
| maps (want / drop / add) | 5.9 | 13.5 | 74.5 (36.3 / 13.9 / 17.2) |
| probe | 27.7 | 38.3 | 117.5 |
| anonymous sync | 11.3 | 12.5 | 61.8 |
| hints / learned | 18.3 / 3.4 | 25.2 / 8.2 | 41.1 / 44.7 |
| scan / merge | 4.3 / 2.6 | 7.0 / 3.5 | 29.9 / 18.9 |
| windows with sync+hints over 50 ms | 12 (0.7 s) | 79 (4.7 s) | **3,548 (285.0 s)** |
| - led by views | 0 | 26 (1.7 s) | **1,909 (153.9 s)** |
| - led by the anonymous sync | 9 | 36 | 1,124 (94.0 s) |
| - led by the probe | 0 | 14 | 420 (27.1 s) |

In his play the largest part of the long syncs is the direct view list: 1,909 of the 3,548 long windows, 154 s.
The d432 line at the end of play-f18: "view builds 89692" (3,688 at t 121 s), so **86,004 rebuilds in 3,035 s of
play, 28 a second**, each over the whole range table (29,172 views at t 553 s; `raw/play-f18-layout-gen.txt`),
under the device mutex, on whichever thread submits next. Sync+hints of all submissions: 561.5 s of the 3,156 s
run (`raw/play-f18-d432-lines.txt`).

### 3. Why the view list is rebuilt 28 times a second

Source lines (patch `bb04219b`, `src/libs/bc5LleAgc.cpp` and `src/kernel/memory.cpp`):

- `direct_views` rebuilds the kind-0 list when `Bc5MappedRangesGeneration()` has moved (exp 0037), and
  `direct_sync_one` lets a submission past its 50 ms gate when it has moved:
  `if (!force && now - S.sync_ns < 50'000'000ull && ranges_gen == S.ranges_gen) return;`
- That generation is `VirtualRanges::m_gen`, bumped by every editing call of the range table (`Add`, `Remove`,
  `ReleaseReserved`, `ConsumeReserved`, `ConsumeReservedSpan`, `Rename`, `Protect`, `SetMemoryType`) for a range of
  any type: flexible, pooled, stack, code, reserved, and protection or memory-type changes.
- The kind-0 list (`direct_views_build`) keeps type 0 (Direct) ranges only, and only their start, size, offset and
  name (the name gives the lazy/eager class). Protection and memory type are not in it, and direct ranges never merge
  (`SameMergeKey`).

So any edit of a non-direct range, and any protection change that leaves a direct range whole, rebuilds a list that
comes out the same. How often: at t 553 s of play-f18 the layout generation (counted when a sync sees a new
signature) was 8,950 against 23,221 view builds at t 552.8 s (`learned_apply took 33.6 ms on bc5-ring (layout gen
8950)`), so roughly 60 % of the builds up to then gave an unchanged list. One reading, and the layout counter can
miss a change between two syncs, so this is an upper bound on the share, not a measure; the test build counts it
exactly (below).

### 4. The candidate: vg437, the direct view list keyed on the direct ranges only

`mkvg437.py` (applies to a tree with `0001` `bb04219b`; every replacement must match exactly once), `vg437.diff`
(the result, 3 files, +86 -3 lines; `git apply --check` passes on the three files of that tree):

- `memory.cpp`: `VirtualRanges::DirectGeneration()` and `m_gen_direct`. Each of the 8 editing calls gets a guard
  right after its existing bump: it copies the direct ranges (start, size, offset, name) of the edit's window (the
  span and every range overlapping it) and, on leaving the call under the same lock, compares them with the window's
  direct ranges after the edit; the direct generation moves only if they differ. Exact comparison, no hash. An edit
  cannot change a direct range outside that window (direct ranges never merge). `Bc5DirectRangesGeneration()` in
  `memory.h`.
- `bc5LleAgc.cpp`: `direct_views` (kind 0 only) and `direct_sync_one`'s gate (kind 0 only) read
  `Bc5DirectRangesGeneration()` instead of `Bc5MappedRangesGeneration()`; the private-region list (kind 1) keeps the old
  generation. With exp 0415's stage S2 (off), kind 0 stores the direct generation read before its build.
- Switch `BC5_DIRECT_VIEWS_GEN`, read in normal and lean: "0" = off, the shared behaviour exactly (both readers take
  the old generation; the guard only counts); unset or anything else = on, in this test build, as exp 0436 did, so
  the arm is the binary (LESSONS R66). One stderr line names the state.
- Normal build only: one journal line beside exp 0432's 10 s line, "exp 0437 (tag vg437): t ... views-gen ON/off;
  range table generation N, direct generation M, view builds K": N against M is the share of edits that no longer
  rebuild; K against the shared runs is the effect.

What it does not change: the anonymous sync, the probe, the maps rebuild of a real direct change, the start-up import.
No learned window, no recovery path, no ring change. Whether it moves the dips is for the box: the share of skipped
rebuilds is measured there, not here.

Laptop test (`test_vg437.sh <tree> 200`): the class and its helpers are cut from the patched `memory.cpp` into a
harness with stand-ins for KytyPlus' mutex and constants and the tree's own `map_records.hpp` and `env_rule.hpp`;
800,000 random edits of all 8 kinds (half on whole existing ranges, all 8 range types, 6 names), oracle: the direct
generation moves if and only if the table's list of direct (start, size, offset, name) changed.
Result: "800000 edits, direct generation moved 36563, stayed 763437, mismatches 0". Mutation check: with the guard
taken out of `Protect` alone the same test reports 255 mismatches in 80,000 edits. Not compiled: the full
`bc5LleAgc.cpp` and `memory.cpp` units (their 4 small edits in `bc5LleAgc.cpp` use only names declared above them:
`bc5::env_on` line 725, `journal`/`timing_now` 537-538, `g_views_builds`, `kernel/memory.h`); the box build is the
first compile of the whole unit.

## Verdict

Cause found for Q30's number, a lead with a candidate for the dips.

- The 0.82-1.39 s "longest sync" of every run is the first submission's import of the eager heaps at start-up
  (9 of 9 runs, set at t 0.8-1.4 s and never exceeded). It is not an in-play stutter. In play the longest single
  frame sync seen is 176 ms (play-f18), 52 ms in the scenes.
- In his free play, sync+hints over 50 ms per 128 submissions summed to 285 s in 3,035 s; the largest part is the
  direct view list, rebuilt 28 times a second on every edit of any guest range, then the anonymous sync and the probe.
- Candidate vg437 (above) removes the rebuilds that cannot change the list. Next: the top session puts it into the
  next test build with exp 0436's result (`BC5_DIRECT_VIEWS_GEN=0` as the control arm), in his scene and in free play.
- Not done, next on the list if vg437 holds: the anonymous sync's remaining walks on the submit thread (94 s of led
  windows in play-f18) and the probe (117.5 s in all).
