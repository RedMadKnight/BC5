# 0431 — way 2 for every title (handover from exp 0428)

**Status: done (verdict below, 2026-11-17).** The plan below is the handover from the exp 0428 session, whose context was
too long for another build-test-swap cycle (the top session's instruction).

## Question

The maintainer, 2026-11-16 (via the top session): "Droga 2 (wiele ringów compute) w drugiej grze => ma być w dowolnej
grze". Does way 2 run ASTRO BOT (and any title) cleanly, so its five switches can move from the second title's rows to
the defaults of every title?

## Where things stand

- **Shared builds since 2026-11-16 16:55:** patch `a8717e53` (on main), normal `dae7bf0b`, lean `819f3b05`. Way 2 is on
  for PPSA03671 only. `src/bc5/switch_defaults.hpp` (`554e0139`) has five `kTitleDefaults` rows for `BC5_T2`:
  `BC5_DIRECT_ACB_RINGS=4`, `BC5_DIRECT_ACB_QUEUE_STATE=1`, `BC5_DIRECT_ACB_MEC_INDIRECT=1`,
  `BC5_DIRECT_ACB_STATE_NO_WALK=1`, `BC5_DIRECT_ACB_SPLIT_LATE=3`. The unit `bc5LleAgc.cpp` is `0cda79b5` (exp 0428's
  `mk0428.py` on 700fd4c2's `3e847e03`).
- **Nothing forces one ring for ASTRO BOT** (read on the box, 2026-11-16 evening):
  - `~/bc5-work/bc5-run.env` holds no ring word;
  - `BC5_DIRECT_RINGS=1` is only in the stale `bc5-run-noshadow.env` and `bc5-run-test293.env`;
  - `play-astro-compute.sh` exports `BC5_DIRECT_COMPUTE_RING=0 BC5_DIRECT_CROSS_RING_WAITS=all`;
  - patch `a8717e53` reads neither `BC5_DIRECT_RINGS` nor `BC5_DIRECT_CROSS_RING_WAITS` (0 hits), and
    `BC5_DIRECT_COMPUTE_RING` is in `kIgnored` (removed at start). All inert.
  - ASTRO BOT runs one GFX ring today only because the rows are PPSA03671's.
  - Nothing was edited; the shared launchers are the maintainer's.

## Plan (the top session's order)

1. **The change** (`mkswap0431.py`, from exp 0428's `mkswap0428b.py`): in `switch_defaults.hpp`, move the five rows from
   `kTitleDefaults` (`BC5_T2`) to `kSoft`, which is applied with `setenv(name, value, 0)` for every title, so
   `NAME=0` still turns each off. The unit stays `0cda79b5`.
   - Check that `kSoft` comes before the title rows in `Apply()`. It does (`switch_defaults.hpp`: `kSoft`, then
     `ApplyTitle`).
   - A title row would not override a soft value set first, since both use overwrite 0.
2. **Private build first**, the exp 0428 way: `box0428.sh`'s relink of one unit cannot carry a header change, because
   `switch_defaults.hpp` is compiled into other objects. So either:
   - rebuild a private copy of the tree (exp 0424's `b0424.sh` pattern: tree copy without `.git`, configure and build
     normal and lean in `~/bc5-work/exp0431/build-*`); or
   - test with the five words in the environment on the shared builds. This is simpler and enough for the test: the
     words are read with `std::getenv`, lean too.
3. **Tests:**
   - **ASTRO BOT, normal shared build `dae7bf0b`** with the five words in the environment: a few minutes of its route
     (exp 0413's `start0413g.sh` drives ASTRO BOT; check that its input copy does not touch JobArenaFix, which is a
     second-title word). Read the `[bc5] exp 0428 (tag w428c)` counters line:
     - acbs on compute rings;
     - "acbs kept on gfx" by reason;
     - the queue→ring map;
     - splits (polled first: kept / satisfied / cycle / timeout);
     - aq424 parts with no tracked queue.

     ASTRO BOT's water used cross-queue waits in October (ADR 0009 amendments: its picture broke into blocks on two
     rings until exp 0134). Watch for broken pictures: compare a screenshot with a one-ring run, if the runner can
     take one.
   - **ASTRO BOT, lean `819f3b05`** with the words: the same route, by time; PASS and kernel lines.
   - **The second title, lean**, as a smoke after the swap, JobArenaFix off: `start0428l.sh` (exp 0428), which reads the
     shared `input.cfg`. exp 0413's `start0413l.sh` forces JobArenaFix on.
   - Stream the kernel log and `live0428.sh` to the laptop for every run (exp 0430's README explains why).
4. **The swap:**
   - Make `int0431.sh` / `undo0431.sh` from exp 0428's `int0428b.sh` / `undo0428b.sh`, with the base unit path written
     out by hand (exp 0428's first try of int0428b failed on a blanket rename and undid itself).
   - Pins: `PIN_OLD=a8717e53`, `NORMAL_OLD=dae7bf0b`, `LEAN_OLD=819f3b05`, `U1_OLD=0cda79b5` (unchanged),
     `U2_OLD=554e0139`.
   - The words: none gained or lost, since the five words are already in both binaries. Check that instead.
   - Test the undo on stand-ins with a real-format pins file (`test_undo0428b.sh`, adapted).
   - Then the lean smoke of both titles, and patch 0001 (`grep -c 'exp 0372'` = 5) on the branch for the top session to
     merge.

## Box

exp 0430 (session `local_0f8d7c32-5a0d-4c82-a91b-680e4487bdaf`, the hang hunt) has priority. Take short slots through
BOX-QUEUE / BOX-LOCK, and never run while the maintainer plays. Every run: way 2 on, JobArenaFix off for the second
title, no fuse or watchdog that kills the game.

## Setup (the exp 0431 session, 2026-11-16 evening)

Branch `exp/0431-way2-every-title` (worktree `bc5-0431`), from main `f42cbde2`.

- `mkswap0431.py`: in `src/bc5/switch_defaults.hpp` it cuts the five PPSA03671 way-2 rows (with their two comments) out
  of `kTitleDefaults` and adds them, with a new comment, to the end of `kSoft`. `Apply()` runs `kSoft` before
  `ApplyTitle`, both with `setenv(name, value, 0)`, so `NAME=0` in the environment still turns each one off. Run on the
  header rebuilt from patch `a8717e53` (md5 `554e0139`, the box tree's `U2`), it gives `40ac1ac2`: 2 edits, brace
  balance 0, 11 lines added and 10 removed. The unit `bc5LleAgc.cpp` (`0cda79b5`) is not touched.
- `int0431.sh` / `undo0431.sh` / `test_undo0431.sh`: exp 0428's `int0428b.sh` / `undo0428b.sh` / `test_undo0428b.sh`
  adapted. The pins are `PIN_OLD=a8717e53`, `NORMAL_OLD=dae7bf0b`, `LEAN_OLD=819f3b05`, `U1=0cda79b5` (unchanged),
  `U2_OLD=554e0139`, `U2_NEW=40ac1ac2`. There is no base unit to copy (no unit change). The checks:
  - no word gained or lost in either binary, and all five words still present;
  - no `{BC5_T2, "BC5_DIRECT_ACB` row left in the new patch, five kSoft ACB rows;
  - exp 0372 = 5, the pad_audio_route header, the same file list.
  `int0431.sh` runs in the chain's lock line when `CHAIN_LOCKLINE` holds it.
- The undo's stand-in test (pins file in `int0431.sh`'s real format, LESSONS R10 0425/undo) passed 9 of 9 on the
  laptop (Git Bash) and 9 of 9 on the box. A mutant that sources the pins over the source path (the 0425 bug) fails
  5 of 9, so the test catches it.
- `astro0431.sh`: ASTRO BOT on a shared build, with way 2's five words in the environment (`W`) or no words (`D`, the build's own defaults:
  way 2 after the swap). The top session dropped the one-ring arm: the maintainer forbade one-ring comparisons. Before the
  swap only `W` runs: normal for the counters, lean. It runs one chain under one BOX-LOCK line, and each run goes through exp 0428's `start0428l.sh` (astro kind,
  md5 `2af5fa46`; private wd `exp0413/n/wda`). The details:
  - the saves are a named snapshot of ASTRO BOT's saves, made once (`~/bc5-work/exp0431/saves-named`, LESSONS R45),
    and the private copy is reset from it before each run;
  - the route is timed, as in `tools/scripts/astro-route.sh`: a cross at 40 and 65 s, then walking and jumping;
  - `KYTY_BC5_FPS_COUNTER=1` is set in both arms;
  - spectacle takes screenshots at 60/90/120/150/180 s, for the black-block and water check (ADR 0009, exps 0132/0134);
  - an evtest pad watch counts real pad keys (it marked a run VOID until the maintainer's correction after a431W1);
  - the chain stops at a kernel line, crash text, a non-PASS, a pad key or `~/bc5-work/exp0431/STOP`.

## Result

### a431W1: ASTRO BOT, normal `dae7bf0b`, way 2's five words in the environment (2026-11-16 21:40:55, top's GO)

The box was freshly rebooted (21:39:13, after the maintainer's play ended in a hang). Kernel 7.3.3-ogc1.1.fc45. The
named save snapshot sum is `8898850cc13a23a6`.

- **A GPU fault at 196 s (21:44:14):**
  - a gfxhub page fault: a TCP write permission fault (`PERMISSION_FAULTS 0x7`, `RW 1`) at `0x314a4d000`, from
    threads DrawThread and bc5-ring;
  - then ring timeouts on `gfx_0.0.0`, `comp_1.0.1` (twice) and `comp_1.2.0`;
  - every reset succeeded and the box stayed up;
  - devcoredumps `~/bc5-data/captures/devcoredump/20261116-214417-devcd1.txt`, `-214419-devcd2.txt`,
    `-214421-devcd3.txt` (not committed);
  - the runner ended the emulator, so no exp 0412 fault record was written.
- **The pad watch** saw two real cross presses at 21:43:58 and 21:43:59, 16 s before the fault. The runner marked the
  run VOID. The maintainer overruled that (relayed by the top session): "moje wciśnięcia na padzie nic nie zmieniają -
  błąd wystąpił a Ty go złapałeś i o to chodziło". The run counts: a caught fault is data whatever the pad did. Since
  then the runner only counts pad keys.
- **Up to the fault:** five screenshots with a clean picture (the galaxy map, then the flight into a level at 180 s;
  no water in view yet), and about 60 flips/s (`fps counter`, the title's cap).
- **The last w428c counters (190.6 s):**
  - every acb ran on a compute ring (0 kept on gfx); four guest queues on four rings;
  - `mec-indirect` moved 313,429 acbs;
  - aq424 gave state to 28,536 parts, with 0 parts with no tracked queue;
  - two-ring dcb waits: 0 not served; 89 heads split (60 after 8 ms, 29 on a cycle); 18,466 kept by the poll.
- The chain stopped there, by its rule (R55). a431W2 (lean) did not run. Nothing was rebuilt; the shared builds are
  unchanged.

Raw: `raw/astro-W.out`, `raw/a431W1.txt` (end line, kernel lines, w428c and fps lines), `raw/kern-stream-a431W1.txt`
(the kernel log streamed to the laptop since the boot).

### a431W1 offline: the devcoredumps and the log (top's question: a cross-ring wait dropped as met?)

Read on 2026-11-16 at 22:00, with no emulator running (`ibscan.py`, a type-3 PM4 walk of a dumped IB).

- **No per-wait record in the log.** The shared normal build prints only the 10-s w428c counters, and the exp 0430
  catcher's "met DROPPED" lines are not in this build. Correction (22:15): a journal WAS written
  (`~/bc5-data/captures/play-20261116-2140/gc/direct.log`, 5.2 MB, `BC5_DIRECT_JOURNAL=min`). The first search used the
  directory name without its dash. The journal is to be read in the next slot, not during exp 0430's chain (R55).
- **The counters' last step (180.6 → 190.6 s, the flight into a level, 5-15 s before the fault):**
  - dcb waits on two rings: 3 more kept for the GPU and 2 more satisfied on the CPU (14 → 16);
  - 5 more head splits, all by the 8 ms timeout (55 → 60);
  - nothing else in the run changed after 80 s;
  - the counters cover dcb waits only; acb waits (exp 0430's case) are not counted.
- **devcd1, `gfx_0.0.0`:**
  - the hung IB is `0x100c00000000`, 890,432 dw; `CP_IB1_BUFSZ` leaves 697,920, so the CP had fetched about 192.5 k dw;
  - around that point there are repeated small blocks: a 0x11 packet, `PFP_SYNC_ME`, a 0x25 packet, `SET_SH_REG` and
    draws;
  - the IB holds **no** `WAIT_REG_MEM`/`WAIT_REG_MEM64` at all, and does not name the fault page `0x314a4d000`.
- **devcd2, `comp_1.0.1`:** the hung IB (`0x104800000000`, 56 dw) begins with a `WAIT_REG_MEM64` on
  `0x4_00202f80 == 1` (a wait kept for the GPU), then three `RELEASE_MEM` and an `EVENT_WRITE`. It waited for a
  producer, which is consistent with the GFX ring being stuck first.
- **devcd3, `comp_1.2.0`:** the hung IB (`0x106700000000`, 440 dw) is 8 `SET_SH_REG` and one NOP: a state prefix
  (aq424), no dispatch.

So the first failure is the GFX ring's TCP write fault. The two compute timeouts follow it: one waits on a label, one
is a state prefix.

### a431X1: ASTRO BOT on exp 0430's build 4 (the cross-queue wait fix), way 2's five words (22:35:55, top's GO)

- **The setup:**
  - build 4 is `~/bc5-work/exp0430/kyty_emulator`, md5 `85a77956`, a normal build with exp 0430's F2 and G on;
  - extra words `BC5_0430_DJ=1 BC5_0430_ARGS=1 BC5_0430_WAVES_MS=900 BC5_0430_SNAP=1 BC5_0430_F2=1 BC5_0430_G=1
    BC5_DIRECT_TIMEOUT_PROBE=1` (exp 0430's list; `BC5_0430_TABLES` unset);
  - `start0431.sh`: after a kernel line the emulator may run up to 30 s and end by itself (exp 0430's catchers);
  - the same snapshot and route as W1.
- **PASS:** 200 s, 0 kernel lines, 0 crash lines. There were 2 real pad keys (they are only counted).
- **The picture:** five screenshots, all clean. The route reached a level this time (the flight at 120 s, the level's
  start area at 180 s), not just the galaxy map. No water was in view.
- **The flips:** 44.4/s on average, against W1's 58.2/s. That is not comparable: different scenes (X1 spent more time
  inside the level), and exp 0430's catchers and waits are on.
- **exp 0430's counters (`ho430`, 180.6 s):**
  - waits seen 44,957; writes registered 4,975,007; writes dropped by the host 8,273;
  - F2 waited 3,638 times (10.5 s in all), 1,254 refused as a cycle, bound reached 0;
  - unsatisfied waits given up: 1,198, cycle 0.
- **The journal** `~/bc5-data/captures/play-20261116-2235/gc/direct.log` has 12 "DROPPED" lines. W1's journal
  (`play-20261116-2140`) has 0, but the shared build's journal level `min` may not write them.
- **The w428c counters at 190.6 s:** all acbs on compute rings; dcb waits on two rings: 1,449 **not served** and
  1,597 heads split (1,560 after 8 ms), against 0 and 89 in W1.

Raw: `raw/astro-X.out`, `raw/a431X1.txt`.

### a431Y1, a431Y2: ASTRO BOT on exp 0430's build 5, way 2 (2026-11-16 23:59 to 2026-11-17 00:06, exp 0430's slot, the night plan)

The setup was the same as X1, except for these words: `BC5_0430_F3=1 BC5_0430_F2=1 BC5_0430_G=0
BC5_DIRECT_TIMEOUT_PROBE=1` and no other exp 0430 catcher. Build 5 is md5 `a90ec52f`. There were 0 pad keys.

| run | build | kernel lines | flips/s (mean) | dcb two-ring waits NOT served | timeout splits | heads split |
|---|---|---|---|---|---|---|
| a431W1 | shared `dae7bf0b` | fault at 196 s | 58.2 | 0 | 60 | 89 |
| a431X1 | build 4, catchers on | 0 | 44.4 | 1,449 | 1,560 | 1,597 |
| a431Y1 | build 5 | 0 | 57.4 | 0 | 49 | 79 |
| a431Y2 | build 5 | 0 | 58.8 | 0 | 62 | 90 |

Both build 5 runs PASSed (200 s, no crash text). The wait counters and the flips are back at the shared build's level.
Two clean runs do not rule out a rare fault (R13). Raw: `raw/astro-Y.out`, `raw/a431Y.txt`.

### The shared swap `int0431.sh` (2026-11-17 07:37-07:39, on top of exp 0430's swap; top's night plan)

The kit was rebased on exp 0430's shared builds:
- `PIN_OLD=a7c1653d`, `NORMAL_OLD=bf3f5f00`, `LEAN_OLD=0fb7bed5`;
- `U1=b8afba59` (unchanged by 0431), `U2_OLD=554e0139`, `U2_NEW=40ac1ac2`; archive `1423af83`;
- all six were read on the box before the swap and all matched;
- the undo's stand-in test passed 9 of 9 again on the box.

- **Try 1 (07:37, `raw/int0431-try1.out`)** stopped on its own check "five kSoft ACB rows" and undid itself (every md5
  back). The check's pattern also counted the older `kDefaults` row `BC5_DIRECT_ACB_STATE_RESTORE` (6 rows). The edit was
  right. The check now names the five rows (5 on the saved patch). The try's copies are kept as
  `~/bc5-work/exp0431/swap.try1-0737`.
- **Try 2 (07:38-07:39, `raw/int0431.out`):**
  - patch `a7c1653d` → `9e7c4514` (25 lines differ, exp 0372 lines 5, the pad_audio_route header in);
  - normal `6044be08` (8 warnings), lean `d239d4bf` (9 warnings), 4 build steps each;
  - the archive is unchanged;
  - no word was gained or lost in either binary, and all five words are present;
  - lean holds no "exp 0428" text; normal holds the w428c line.
- Undo: `bash ~/bc5-work/exp0431/undo0431.sh`, then `~/bc5-work/exp0430/undo0430.sh` further back. Way 2 is off for a run
  with `BC5_DIRECT_ACB_RINGS=0`, with no build.
- `backend/kytyplus-patches/0001-bc5-lle-agc.patch` on this branch is the box's new patch `9e7c4514` (main was
  `a7c1653d`; merged into the branch first).
- The smoke (`smoke0431.sh`) did not start: exp 0429 claimed the box at 07:40:04, 15 s after the swap released it. It
  is queued in BOX-QUEUE for right after exp 0429.

### The smoke of the swapped shared builds (`smoke0431.sh`, 2026-11-17 07:52-08:09; no way-2 word anywhere, so way 2 came from the defaults)

| run | build | what | result |
|---|---|---|---|
| a431S1 | lean `d239d4bf` | ASTRO BOT 200 s, timed route | PASS, 0 kernel lines, 0 crash lines, 0 pad keys |
| l431S2 | lean `d239d4bf` | the second title 300 s (`lean0428.sh`: RT on, JobArenaFix off in its config) | PASS, 0 kernel lines, 0 crash lines |
| a431S3 | normal `6044be08` | ASTRO BOT 480 s, the route's walk for the whole run | PASS, 0 kernel lines, 0 crash lines, 0 pad keys |

- **a431S3's w428c line (480.6 s)** shows way 2 on with no word in the environment, so `kSoft` applies to ASTRO BOT:
  - acbs kept on gfx: none; queues 26/32/38/40 on rings 3/1/0/2;
  - mec-indirect moved 721,319 acbs;
  - aq424 gave state to 81,614 parts, with 0 parts with no tracked queue;
  - dcb waits on two rings: 0 not served, 103 heads split (56 after 8 ms, 47 on a cycle).
  - Flips: 59.5/s on average over 475 s, the title's cap.
- **The picture:** the screenshots of S1 and S3 are clean, but they all show the galaxy map. Without a person's presses
  the timed route does not enter a level (W1 and X1 got into levels only after real presses). So the long run says
  nothing about the water. The water check is still open: it needs a route into a level with water, or the
  maintainer's play.
- The chain ended at 08:09:24. The laptop monitor missed its lines (its ssh `tail` showed nothing), so exp 0429 got the
  word at 08:22, about 13 min late.

Raw: `raw/smoke0431.out`, `raw/smoke0431-detail.txt`.

## Verdict

**Way 2 is the default for every title in the shared builds** since 2026-11-17 07:39. The shared builds are patch
`9e7c4514` (normal `6044be08`, lean `d239d4bf`, archive `1423af83`), on top of exp 0430's cross-queue wait fix
(`a7c1653d`).

What the record shows:
- ASTRO BOT ran way 2 with no word set (kSoft): 3 of 3 smoke runs PASS, about 15 min in all, with no kernel line;
- the second title's lean smoke PASSed;
- on exp 0430's fix build, way-2 ASTRO BOT also ran 3 of 3 clean (X1, Y1, Y2);
- the one fault (W1, shared `dae7bf0b`, before exp 0430's fix) was a GFX-ring TCP write fault. Its cause was not
  proven: the build had no per-wait records.

Limits:
- 6 clean ASTRO BOT runs and one route (mostly the galaxy map, plus two short level entries). Rare faults are not
  ruled out (R13);
- ASTRO BOT's water (the October two-ring black blocks, exps 0132/0134) was never in view;
- the maintainer's own plays are the next evidence.

Rollback:
- `BC5_DIRECT_ACB_RINGS=0` in the environment turns way 2 off for a run, with no build;
- `bash ~/bc5-work/exp0431/undo0431.sh` goes back to patch `a7c1653d` (normal `bf3f5f00`, lean `0fb7bed5`).

Not done here: `CLAUDE.md` and the HANDOFF row (the top session's, on main).
