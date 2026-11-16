# 0431 — way 2 for every title (handover from exp 0428)

**Status: handover, nothing built or run under this number yet.** Written by the exp 0428 session, whose context was
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
