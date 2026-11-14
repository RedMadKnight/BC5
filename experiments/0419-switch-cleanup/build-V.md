# Experiment 0419: build V, prepared on the laptop in the night of 2026-11-14/15, NOT built

Ordered by the top session (the maintainer: "kontynuuj"): tomorrow morning ONE compile and ONE acceptance of
V = build U (patch 5b185960; normal b85a756d, lean e8c3d935) + everything that could be put together safely. The box
was not touched for this (the night series holds it until 06:45).

## What is in V

| # | Part | Script (step) | Files | Can be left out alone |
|---|---|---|---|---|
| 1 | **The constant branches of the built-in library ports folded** (batch 3, round 1): the condition goes, an `else` branch goes, and after a port block that ends in `return` the rest of the function (the old stub path) goes | `mkfold0419.py` with `fold-levels.txt` | 16 files of `src/libs` | yes, per file (its level set to 0) or all (`FOLD=0`) |
| 2 | **The rest of `KYTY_BC5_PAD_TOUCH`'s code**: `ControllerTouch`, `GameController::Touch`, `ApplyTouch`, the touch fields, the read-out of touch points. PAD CODE | `mkv0419.py touchfn` | `controller.cpp`, `controller.h` | yes |
| 3 | **The fix for the GPU read fault of arm n13P4** (fault record `20261114-184017`; exp 0412 README sections 98-99, `PLAN-memory-wall.md` cure 2, the guardian's): the title's heap "FileSystem" is never lazy for the direct path, so its written pages are imported. Diagnostic to measure the price: `BC5_DIAG_LAZY_FILESYSTEM=1` keeps the old list | `mkv0419.py lazyfs` | the main unit, 10 lines | yes |
| 4 | **`KYTY_BC5_AJM_LIVE_IDS`: two variants**, the top session picks one after the night series' tA against tJ | `mkv0419.py liveids`, or not named | `ajm.cpp` | it is the variant |

Where the lazy list lives (asked): `BC5_DIRECT_LAZY_NAMES` is in no table of the build (`switch_defaults.hpp` has no
row for it). It is a **launcher word**: the second title's launchers set it (the journal of every walk prints "lazy
names: orbis_user_malloc,Wwise,SoundAlloc,FileSystem,UIStr..."). The launchers and shortcuts are the maintainer's, so
the change is made in the build where the list is read (`direct_lazy_name`): the name is taken out of whatever the
launcher gave, with one line on stderr. The journal's "lazy names:" line still prints the launcher's string.

| Variant | Patch | Tree list | Words read / can be set |
|---|---|---|---|
| V with `KYTY_BC5_AJM_LIVE_IDS` fixed on (step `liveids`) | `c4504857` | `tree-build-V-liveids-fixed-c4504857.md5` | 203 / **154** |
| V with it still a switch | `f85fb913` | `tree-build-V-liveids-switch-f85fb913.md5` | 204 / **155** |

Both: 133 patched files, 20 (19) files changed against U, about 360 lines added and 855 removed. Against U the word
lists differ by `BC5_DIAG_LAZY_FILESYSTEM` (new, a diagnostic) and, in the first variant, `KYTY_BC5_AJM_LIVE_IDS`
(gone). Words without a verdict: 0, with one to come: `KYTY_BC5_AJM_DEFER` gets its verdict from arm tJ.

## The library folds in numbers (`fold-levels.txt`, decided by `mklevels0419.sh`)

A file's level is the highest at which it passes the laptop's `-fsyntax-only -std=c++20 -Wall -Wextra -Werror`
exactly as before the change (7 everything; 5 without removing the negated blocks, whose removal leaves functions
unused; 0 untouched).

| | Files | Folds | Stub tails removed | Sites left as they are |
|---|---|---|---|---|
| level 7 | 10 (`libAudio`, `libCamera`, `libCompanion`, `libDiscMap`, `libHmd`, `libMove`, `libScreenShot`, `libUlobjmgr`, `libVoice`, `libVrTracker`) | 109 | 99 | 0 |
| level 5 | 6 (`libGameLiveStreaming`, `libInvitationDialog`, `libNp`, `libSharePlay`, `libUsbd`, `libWebBrowserDialog`) | 243 | 184 | 73 (the negated blocks: they register functions "held" while a port was off) |
| level 0 | 1 (`libNet`: its two sites do not pass the check when folded) | 0 | 0 | 2 |

352 of the 426 `if` sites are folded and 283 unreachable stub tails removed. `libAudio.cpp` is the Voice library's
port id map, not the pad's audio route (`audio.cpp` and `pad_audio_route.hpp` are not touched by V).

## Checked on the laptop

- every edit of `mkv0419.py` matches exactly once on U's tree; braces balance in every changed file;
- the 16 folded library files pass the syntax check as before, each at its level (`libNp.cpp` keeps its one old
  error, `sched_param`, a stand-in's gap);
- `ajm/test0419ajm.cpp` covers the id rule that `liveids` fixes; `test0419diag.cpp` unchanged;
- the dry run: both variants apply to a clean tree at U; `grep -c 'exp 0372'` = 5 in both patches;
- `BC5_GUARD_LAZY_BY_DATA` (the guardian's, NOT a default in V) is read by the same function `lazyfs` edits, two
  statements below the edit; its lines are unchanged and it still wins over the list when set.

## NOT checked

- Any compile of `controller.cpp`, `controller.h` (the laptop lacks pthread.h), the main unit and `ajm.cpp` with
  these edits: the box's build is their first. `touchfn` is nine cuts in pad code made blind; it is the step most
  likely to be taken back.
- Whether the fold changes behaviour: by construction it does not (the conditions were constant true), but no test
  calls these library functions; ASTRO BOT's three starts and the second title's walk are what the acceptance has.
- The price of `lazyfs` (the guardian's estimate: at most 48 MiB pinned more) and whether it cures n13P4's fault:
  both are the guardian's to measure on V.

## The round (`v0419round.sh`, from the laptop, in the slot the top session gives)

1. `v0419round.sh pad` FIRST: a joystick device and the DualSense's ALSA card in PipeWire. Without them it says so
   at once and stops: the software replug at the end cannot run without the pad (this is what cost U its replug).
2. `v0419round.sh build` (default steps `touchfn lazyfs`; for the fixed variant `build touchfn lazyfs liveids`):
   sends the kit; `p3build0419.sh` saves U's files and binaries, applies folds and steps, rebuilds normal and lean.
   A compile error names file and line; that part is left out (a level set to 0, or a step not named) and the stage
   is run again: the saved files go back first, so it stays one round.
3. `v0419round.sh accept`: the acceptance as for U (`chk0419v.sh`: ASTRO BOT 120 s x3 and the bad save, the second
   title's walk to G+240, the cutscene arm to G+320, lean), RT on.
4. `v0419round.sh replug R12`: one software replug on the private normal build (V touches pad code).
5. `v0419round.sh words`: the binaries' md5s and word lists, copies in `~/bc5-work/exp0419/bin-V/`.

The backend is not changed by V (its 121 tests ran for T). CPU tests are the laptop's, above. The driver itself has
only had `bash -n`: its stages have not been run.

## Dead code that stays after V

Each needs a compile of its own; none is in V because it sits in the hot path or belongs with a test.

| What | Why not in V |
|---|---|
| the acb CS prefix and acb inherit | woven into the submit path (named by the top session as a separate compile) |
| the R3 block's `submit_eop`, `rewind`, `drop` members and their ioctl-site code | the same |
| ADR 0013's consumer side (`hold_release`, the `hold` vectors) | it sits in the chain slot's path, read on every chain |
| the zero skip of exp 0379, the four reset switches (`m11_on`), the meshlet sampler | wide blocks of the unit, with CPU tests and seams of their own |
| the five hang-hunt words' code (unit and backend) and step f's four checks | the planner's seams with `flx0401.cpp`; a new backend archive and its tests |
| the guardian's mlock, cap, `MAP_RULE`, `PRT_BG` code and `g412::forget_step` | exp 0412's blocks and tests: its to prepare |
| the AMM PRT and extra commands (`libAmpr.cpp`) | cutting the registration alone would leave their handlers unused: all or nothing, with a compiler |
| in the libraries: 73 negated blocks (and the "held" functions they register) and `libNet`'s two sites | removing them leaves functions unused; they go together with those functions |
| the checking thread of `KYTY_BC5_ANON_SYNC` | not dead: it serves `verify`, which stays as a diagnostic |

Eight groups of dead code stay after V (the ninth row is not dead); before V there were ten, with the libraries'
branches whole and the pad's touch code.
