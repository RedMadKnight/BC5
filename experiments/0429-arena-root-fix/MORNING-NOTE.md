# Exp 0429: morning note (2026-11-17, written 05:5x, offline, from the records in README.md)

## The JobArenaFix removal: ready, not swapped
The hook, the "Game fixes" menu, the switch, the `KYTY_BC5_JOB_ARENA_FIX` word, the input.cfg key (an old line is
accepted silently and not written back) and `src/bc5/job_arena_fix.hpp` are gone. That holds in builds 1–6, normal and
lean, and each build is checked for none of those words. The only shared file still naming it is `~/bc5-work/input.cfg`,
line 3 (`JobArenaFix.PPSA03671=off`). No shared swap was done tonight. The swap (the int0428 way, with an undo tested on
stand-ins) waits for the maintainer.

## What the crashes had that the clean controls did not

| run | build | route, save | switches | guest CPU mask, Hi workers | crash |
|---|---|---|---|---|---|
| h429X1 | 1 (shared units, no 0430 fix) | long route, slot 4, named snapshot, RT on | PRIO_ORDER, AFFINITY=1, C2 300 µs | default 0x7f (5 per entry), **pinned** to host cores | G+10 |
| h429M4 | 3 (0430 build 5) | same | GUEST_CPUS=1 | default **0xffff**, pinned guest i → host i | G+393 (walk) |
| h429Z1 | 4 (0430 build 6) | same | GUEST_CPUS=1, PRIO_ORDER=2 | default **0xffff**, **8 Hi workers**, pinned | G+10 |
| h429C1, C3, C4 | 4, 6, 6 | same | none | default 0x7f, 5 per entry, **not pinned** | none to G+600 |
| h429S1–S3 | 6 | same | FAST_MUTEX=2 | 0x7f, not pinned | none to G+600 |
| w428L1 (exp 0428) | way 2 + C1, shared-like | fight route (to G+120) | none of 0429's | 0x7f, not pinned | G+120 |

- **Same for all of them:** the route, the save (slot 4, the named snapshot), RT on, no pad key, and no second emulator,
  because the chains run one at a time under BOX-LOCK. Background load was not recorded per run; all ran at night
  without a desktop user. Flips/s do not separate the groups: the crashes ran at 39.0, 39.9 and 47.0, the controls at
  39.9, 40.4 and 47.1.
- **The one difference that lines up:** every crash in exp 0429 ran with the guest CPU mask changed by an arm
  (pinning, or a wider default mask so the title makes more workers). No unpinned run with the 0x7f mask crashed here,
  3 C and 3 S. Exp 0388 arm A (default 0x1fff, not pinned, 8 workers per entry) crashed 3 of 3 (F791).
- **The build doesn't explain it:** the crashes came on builds 1, 3 and 4, and the clean runs on 4 and 6.
- **Counts only (R13):** 3 against 6, so this is a lead, not a measured rate. Without an arm the crash still comes:
  w428L1 at G+120, and exp 0430's h430Y1 on its build 6 at G+187.

## Proposed morning A/B
- **Both arms get `KYTY_BC5_0429_GUEST_CPUS=1`, as a stressor, not a fix.** It is the condition under which the
  control has crashed (M4, Z1; arm A 3 of 3 in exp 0388).
  - C' = `GUEST_CPUS=1`.
  - S' = `GUEST_CPUS=1` + `FAST_MUTEX=2`.
  - Build 6, the long route (M4 crashed only at G+393), alternating C' S' C' S'.
- **Why this fits the candidate:** more workers per entry means more threads scanning under the per-entry guest
  mutex. The host's inner `std::mutex` is exactly what S replaces. If C' keeps crashing and S' does not, the two are
  separated. If S' crashes too, S is out.
- **The fallback (from 0388) needs a new switch.** A wider mask without pinning would separate "more workers" from
  "pinning", but build 6 has no switch for it, so it would need a small build.
- **What it costs:** about 12 min a run, 4 runs, about 50 min of box time. No build is needed.
- **The chain is ready on the laptop (05:5x).** C' is the existing arm M. S' is a new arm T (`GUEST_CPUS=1` +
  `FAST_MUTEX=2`), added to `chain0429.sh` and `mkrun0429.py`. The updated `chain0429.sh` still has to be copied to
  `~/bc5-work/exp0429` in the next slot (no box access tonight). Run it with
  `CHAIN_SET=rep7 REP_TAGS="h429M5 h429T1 h429M6 h429T2"`.
