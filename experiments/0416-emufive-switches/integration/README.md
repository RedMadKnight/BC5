# Integration of 2026-11-13: exp 0416 + exp 0415 + exp 0412 (mr412) into patch 0001 and the shared builds

**Order.** The maintainer to the top session, 2026-11-13 about 00:50 box time: "jest zgoda na scalenie wszystkiego i
twoje testy". The top session named this session integrator: one branch on main `c7847986`, one private build, the
checks, then the swap of both shared builds. Branch `int/0416-all-into-shared`. This file is the record; the three
experiments' own READMEs are not changed by it.

## What went in (patch 0001: 01abfc0c -> 4651d1d3, 17 files against 01abfc0c)

| From | What | Default |
|---|---|---|
| exp 0416 (a099e662) | Codex's owned-EOP fix; set-buffer's map flavour opt-in (`KYTY_BC5_AMM_SETBUFFER_MAP=1`) behind exp 0413's guard; A2/C1/C2/C3 as code defaults (`kFixes`); `KYTY_BC5_EVENT_COALESCE_SAME`, `KYTY_BC5_SEMA_TARGETED_WAKE` | the two switches OFF; `BC5_R3_SUBMIT_EOP_EVENT` not in any table |
| exp 0415 (L4, `kit/0415-l4-cumulative.diff`, 16 files) | `KYTY_BC5_APR_POSIX` (`apr_posix.hpp`); the counters of `KYTY_BC5_LOAD_STAT` (hold-by-part among them); L3's `KYTY_BC5_WINDOW_FAST`, `KYTY_BC5_VMA_FAST`, `KYTY_BC5_NAMES_FAST`; S1 `KYTY_BC5_MAP_RECORDS`; `KYTY_BC5_FRAME_STAT` | `KYTY_BC5_APR_POSIX=direct` ON as a row of `kFixes` (`=0` gives the old read path; applied also with `KYTY_BC5_SWITCH_DEFAULTS=0`); everything else OFF |
| exp 0412 (tag mr412, `memfast/mkrule0412.py`, `maprule0412.inc`) | `BC5_GUARD_MAP_RULE`, `BC5_GUARD_PRT_BG`, `BC5_GUARD_LEARN_LOG` | all OFF, in no table and no launcher |

**Standing warning (exp 0412 sections 53, 54):** `BC5_GUARD_MAP_RULE=1` reaches the memory wall in the menu, and
`MAP_RULE=1` with `PRT_BG=1` hung the GPU once and rebooted the box. Neither may be set in any launcher or shortcut.

The launcher `play-pkg.sh` (157021e3) is not changed. The backend archive (75e30335) is not rebuilt.

## The fold, step by step (md5 of each unit, first 8 hex)

The fold was made in a scratch clone of KytyPlus f266548: tree S7 = patch 01abfc0c; exp 0416's tree (a099e662) and
exp 0415's tree (S7 + `0415-l4-cumulative.diff`, all 16 files equal to its `tree-l4-all.md5`) were merged three-way
with `git merge`; no conflict. Then two scripts of this directory.

| Unit | Shared (01abfc0c) | + exp 0416 | + exp 0415 L4 (0415 alone) | + this directory's scripts |
|---|---|---|---|---|
| `src/libs/bc5LleAgc.cpp` | 8f6e92b3 | 777eb681 | f82fb38f (f9d26f9b) | **a81efd2c** (`mkrule0416.py`: mr412) |
| `src/libs/libAmpr.cpp` | ddf52b7b | 9a526e31 | 2852bb41 (84793cee) | **a2d09d32** (`mkdef0416.py ampr`: one comment line) |
| `src/bc5/switch_defaults.hpp` | 852f4d03 | 4f704194 | — | **2f1316c6** (`mkdef0416.py defaults`: the APR row) |
| `src/kernel/semaphore.cpp` | 3aa9c8b4 | 81049581 | **63c448cb** (the same: 0415 built on 0416's edit and adds three lines) | — |
| `src/graphics/host_gpu/renderer/sync.cpp` | 06c1349c | 2d97421c | **2d97421c** (the same) | — |
| the other 12 files of exp 0415 | | | as `tree-l4-all.md5` | — |

All 125 patched files with their sums: `tree9.md5`.

**The one adaptation.** `mkrule0412.py` was written for exp 0412's private unit. Its catcher printed `DView::prot`,
a field only exp 0412's private step pr412 adds; that step is not part of this integration. `mkrule0416.py` runs
`mkrule0412.py`'s own `main()` with four textual changes, each asserted once: the input check asks only that tag
mr412 is absent; the catcher has no `prot` variable and no `prot = v.prot`; the would-learn line has no `prot 0x..`
field; `DView::prot` is not required. The eleven anchors, the undo check and the order checks are the author's.

**Confirmed by the authors (2026-11-13):** exp 0415's session compared the folded `bc5LleAgc.cpp` and `libAmpr.cpp`
with its own edits (each of its lines present as often as in its unit, none changed) and the 14 identical files;
exp 0412's session read the mr412 part of the diff line by line (15 conversions and 15 arguments in the would-learn
line; nothing else needs a private 0412 step; with the three switches unset one constant test per call site).

## Checks

Kernel 7.2.15-ogc1.1.fc45 (the replug runner's line; CLAUDE.md still says 7.2.11-ogc4.1). Raw logs stay on the box under
`~/bc5-work/exp0413/n/raw` (tags below), the chain's own output in `~/bc5-work/exp0413/n/chk0416c.out`.

### CPU tests (`cpu0416.sh`, g++ in the ubuntu container, against the private tree's headers)

| Test | Result |
|---|---|
| exp 0416 semaphore (`mktest0416.py` on the folded unit), switch unset and `=1` | PASS, PASS |
| exp 0416 set-buffer, forced a4 = -1 (`mktest0416sb.py` on the folded unit): guard on/off x map opt-in off/on | PASS x4 |
| exp 0416 `test0416fault.py` (on Linux, with the own-process check) | 24 checks PASS |
| exp 0412 `maprule0412.cpp` | 15281 of 15281 |
| exp 0415 `test0415` off / on | 70 of 70 / 32 of 32 |
| exp 0415 `test0415apr` | 33 of 33 |
| exp 0415 `test0415sync`, `test0415rec` | 15 of 15, 10 of 10 |

The same semaphore, set-buffer, catcher and maprule tests also pass on the laptop (VS clang++ 22).
`mktest0416.py` got stand-ins for exp 0415's two counter calls in the semaphore unit.

### Private build (patch 4651d1d3: normal fa34047cb3dc1f1cd0880b68f56c2078, lean a569bb99549dfeb115522ebee50fff1a)

`chk0416c.sh`, 01:05-01:31, every run with 0 kernel lines and 0 crash lines:

| Tag | What | Result |
|---|---|---|
| a9pp0 | ASTRO BOT 120 s, nothing set | PASS; the lines "pending cap 64" and "exp 0415: APR reads by pread ..., straight into the guest" are there |
| a9pd0 | ASTRO BOT 120 s, `KYTY_BC5_SWITCH_DEFAULTS=0` | PASS; the same two lines (the code defaults stay on without the table) |
| r9papr | second title, RT on, no zero skip, to G+240, the code default (APR direct) | clean; 24.9 flips/s over 354 s, 75 s with a gap over 100 ms, longest 911 ms; lowest available memory 338 MiB |
| r9pold | the same with `KYTY_BC5_APR_POSIX=0` | clean; 25.2 flips/s over 356 s, 74 s, longest 710 ms; lowest available 323 MiB |
| l9p | lean, 120 s | PASS |
| R7 | software replug (exp 0391's harness with Codex's R45 change), mode pulls | CLASS PASS, 3 pulls (raw: `../../0413-np-session-v2-shared/integration/replug/raw/R7-*`) |

R6, the first replug try, was INVALID before any emulator started: the harness derives a private launcher from
`play-pkg.sh` by three edits for the unpacked game, and the launcher 157021e3 (installed 2026-11-12) already has
those lines. `s6n0391.sh` now skips the three edits when the launcher has them and expects 11 marked diff lines
instead of 18 (checked by a dry run of that part on the laptop, then R7).

The catcher `fault0416.py` ran beside the four second-title runs for the first time on the box: it ended on SIGTERM
with "child terminated, status -15" each time (so `sudo` passes the signal on to `dmesg`) and saw no page fault.

### The swap and the shared binaries

**The swap** (`int0416.sh`, 01:45:08-01:50:45, lock released): the shared tree's diff 01abfc0c -> 4651d1d3 (125
patched files match `tree9.md5`), archive 75e30335 unchanged.

| | Before | After |
|---|---|---|
| shared normal `~/bc5-work/kytyplus-build/src/kyty_emulator` | ce0e3b928b6d1d1d47fc035c13e8cee3 | **fe0933c0ad7c0d9a86194bc0a7598a06** |
| shared lean `~/bc5-work/kytyplus-build-lean/src/kyty_emulator` | 35ec3341be46ffd7013db8ffa9a4b2f5 | **711d6c0d33d171bcb4749903bd607aa2** |

The shared binaries are not byte-identical to the private ones (as in exp 0413's swaps: the build directory differs).
Rollback: both binaries from `~/bc5-work/exp0413/swap/*.before-0416`, the tree by reversing `0001-new9.patch` and
applying `0001-new7.patch` (both in `~/bc5-work/exp0413/p/kit`), then a rebuild.

**On the shared binaries** (`MODE=post chk0416c.sh`, 01:51-02:14; 0 kernel lines and 0 crash lines in every run):

| Tag | What | Result |
|---|---|---|
| a9sp0 | ASTRO BOT 120 s, nothing set | PASS |
| a9sd0 | ASTRO BOT 120 s, `KYTY_BC5_SWITCH_DEFAULTS=0` | PASS |
| r9sapr | second title to G+240, the code default (APR direct) | clean; 25.5 flips/s over 353 s, 75 s with a gap over 100 ms, longest 808 ms; lowest available 368 MiB |
| r9sold | the same with `KYTY_BC5_APR_POSIX=0` | **ended at 169 s by the test's memory watchdog** (available 294 MiB, five samples under its 300 MiB line; PSI full 6 %); no kernel line, no crash line |
| r9sold2 | r9sold repeated once | clean to G+240; 23.6 flips/s over 356 s, 97 s with a gap over 100 ms, longest 1,418 ms; lowest available 258 MiB, PSI full up to 24 % |
| l9s | the SHARED lean binary, 120 s | PASS (its first start) |
| R8 | software replug on the SHARED normal build (pins fe0933c0, launcher 157021e3), mode pulls | CLASS PASS, 3 pulls (raw: `../../0413-np-session-v2-shared/integration/replug/raw/R8-*`) |

**The read counters** (`KYTY_BC5_LOAD_STAT`, the last cumulative line, field `apr_read` = reads, summed ns, longest ns,
bytes asked; `apr_fallback` is 0 in all):

| Run | `KYTY_BC5_APR_POSIX` | Reads | Summed read time | Mean per read | Bytes asked |
|---|---|---|---|---|---|
| r9papr (private) | direct (default) | 183,378 | 301.2 s | 1.64 ms | 30.34 GB |
| r9pold (private) | 0 | 156,295 | 465.3 s | 2.98 ms | 20.60 GB |
| r9sapr (shared) | direct (default) | 178,195 | 264.1 s | 1.48 ms | 23.97 GB |
| r9sold (shared, 169 s) | 0 | 133,683 | 352.9 s | 2.64 ms | 15.11 GB |
| r9sold2 (shared) | 0 | 171,052 | 636.2 s | 3.72 ms | 22.92 GB |

So the default takes the new path (its line in the log, a mean read about half as long) and `=0` takes the old one
(no line). The route's own times did not move in these runs: start to the save list 93-94 s, load 101-104 s, G at
117-119 s in all five. exp 0415 measured its 7.3 s and 4.2 s on series of 10 and 8 runs; these single runs do not
repeat that measurement and do not contradict it.

**Memory with the old read path.** The three `=0` runs had the lowest available memory of the night (323, 294 with
the kill, 258 MiB) against 338 and 368 MiB with the default. Five runs, one route: an observation, not a measured
effect. The kill is the test's own watchdog (300 MiB), which the maintainer's shortcuts do not use.

## Not verified

- **No play by the maintainer on the new shared builds yet**, and no run longer than G+240. The first real start of
  `play-pkg.sh` 157021e3 through his shortcut is still to come (the checks use derived private launchers).
- **The three exp 0412 switches were not run at all** (all OFF everywhere; ON is known to be unsafe, see the warning).
  Their code compiled and the unit's CPU test passes; "one constant test per call site when unset" is the author's
  reading, and the clean runs agree with it.
- **exp 0415's L3 fast paths, `KYTY_BC5_MAP_RECORDS`, `KYTY_BC5_FRAME_STAT`** were not switched on here (exp 0415 ran
  them in its own L4 build); `KYTY_BC5_LOAD_STAT` was on in the five second-title runs.
- **exp 0416's two switches** (`EVENT_COALESCE_SAME`, `SEMA_TARGETED_WAKE`) were not switched on in this build (they
  ran in a099e662's); they stay experimental, no speed claim.
- **The set-buffer guard with a real a4 = -1 call**: only the CPU test with stand-ins covers it in this patch.
- **The physical replug** with a DualSense and a DS4 (the maintainer's).
- **Kernel.** The box runs 7.2.15-ogc1.1.fc45 (read from the replug runner's output, also yesterday's R5), not the
  7.2.11-ogc4.1 that CLAUDE.md records; exp 0416's README repeated the stale version. Mesa and libdrm were not re-read.
- Codex's short round on this diff comes after the fact (the top session posts the request).
