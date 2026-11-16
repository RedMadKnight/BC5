# 0428 — way 2: the title's acbs on compute rings, with each guest queue's own state

## Question

Can the second title run its asynchronous compute buffers on kernel compute rings (ADR 0009) with each guest queue's
compute state carried as on the console, cleanly and not slower than the shared builds (patch 700fd4c2)?

Background:
- the maintainer's consent for way 2 through deployment, with priority ("dla drogi nr 2 - jest całkowita moja zgoda, aż
  do pełnego wdrożenia - zadanie ma pierwszeństwo i priorytet"), and to keep looking if it fails or is slower ("ma
  szukać rozwiązania aż do skutku"), both relayed by the top session on 2026-11-16;
- exp 0427: hardware compute queues keep `COMPUTE_USER_DATA`, but a libdrm compute ring index is not a fixed hardware
  queue. The scheduler re-picks one of 7 when the index is idle. So the state has to come from each guest queue's own
  tracker, not from the ring;
- today's shared builds run every acb on the GFX ring. `BC5_DIRECT_COMPUTE_RING` was removed (F412, F415): the 10-26
  machine-down was a `comp_1.2.0` timeout whose reset never came. Build W (exp 0419) removed the October cross-ring
  waits and ADR 0013's held tail with it.

Stale statements, noted here; the top session fixes CLAUDE.md on main:
- ADR 0009's status header ("the second title's `play-pkg.sh` runs its compute buffers on compute ring 0");
- CLAUDE.md's "the direct path uses compute ring 0 for the second title".

Both are stale since 10-27: the patch's `kIgnored` holds `BC5_DIRECT_COMPUTE_RING`, `compute_ring_env()` defaults to
the GFX ring, and F412/F415 record the change.

F412 found that one ring costs no fps with RT off. So this experiment measures RT on, and says plainly if way 2's
overlap gains nothing there. By the maintainer's words, that would be a reason to keep looking for a working form, not
to deploy a slower one.

## Setup

**Private test build.** The relink pattern of exps 0425/0388:
- `mk0428.py` edits the shared tree's `src/libs/bc5LleAgc.cpp` (patch 700fd4c2, md5 `3e847e03`) into `4af9d11d`;
- `build0428.py` compiles it with the shared normal build's command and relinks with the shared objects;
- `box0428.sh` does claim, build and release under one BOX-LOCK line.

Built 2026-11-16 12:04: private normal `64fa2359`. The shared normal `1be1cc1d` was unchanged before and after. There
were 7 warnings, all on old lines (as exp 0424), none in the new code.

The edits, each behind a switch read with `std::getenv` (so lean reads them too); counters are normal-only:
1. `BC5_DIRECT_ACB_RINGS=<0..4>` (tag w428). 0 is today's one GFX ring. With n ≥ 1 the ring thread's acbs go to compute
   rings, each guest queue on its own libdrm ring index (modulo n). `bc5::policy::compute_ring_refusal` still keeps a
   buffer on the GFX ring; those are counted by reason.
2. Cross-ring waits stay for the GPU when the label's last pending write is on another ring: ADR 0009 waits step 3,
   "all", the F178 setting.
3. The game thread's dcb wait on two rings, in exp 0132's form without the held tail:
   - the head is split off and submitted;
   - the wait is kept for the GPU once its writer is on a ring, or satisfied on the CPU, within 8 ms;
   - otherwise the existing path and its limit apply.
4. `BC5_DIRECT_ACB_QUEUE_STATE` (tag aq424, exp 0424's edits unchanged): every acb part that dispatches gets its own
   guest queue's tracked SH 0x204–0x3ff (without `COMPUTE_VMID`) in front, from that queue's tracker at submit time. A
   queue with nothing tracked yet gets nothing, and that is counted.
5. One stderr line every 10 s (tag w428c), normal only: jobs per ring, acbs kept on GFX by reason, the queue→ring map,
   the two-ring wait counts, and aq424's parts with state and with no tracked queue.

**Runs.** `run0428f.sh` is derived by `mkrun0428.py` from exp 0425's `run0425f.sh` (md5 `0591b743`):
- the second title, F464's route from exp 0425's named snapshot (read only), slot 4;
- the 14:50 record's gameplay at G (the fight), G+120 s;
- RT on, `ulimit -c 0`;
- JobArenaFix as the shared `input.cfg` has it;
- everything written goes to `~/bc5-work/exp0428/n`.

`chain0428.sh` runs one set per start under one BOX-LOCK line. It stops at a kernel GPU line, a real pad key, any class
but NO_CRASH/NOT_ROUTED, a second NOT_ROUTED, or a STOP file.

Arms, on the same binary:
- **C**: `BC5_DIRECT_ACB_RINGS=0 BC5_DIRECT_ACB_QUEUE_STATE=0`, the shared behaviour;
- **Q**: `BC5_DIRECT_ACB_RINGS=4 BC5_DIRECT_ACB_QUEUE_STATE=1`, way 2.

Sets:
- **smoke**: `w428Q1` alone first. A compute-ring hang whose reset does not succeed ends the track for the day and goes
  to the top session.
- **series**: `w428C1 w428Q2 w428Q3 w428C2 w428C3 w428Q4 w428Q5 w428C4`.

## Rule (fixed before the runs; `check0428.py`)

- **smoke** passes if the one Q run is NO_CRASH.
- **series** is complete only with 4 C and 4 Q rows of class NO_CRASH.
  - Q fails if any Q row has another class (KERNEL, CRASH_OTHER, WALL, TARGET, SETUP, OTHER).
  - Otherwise "not slower" holds if the median of Q's flips/s ≥ the median of C's − 0.5.
- Beyond that, everything is descriptive (R13): 4 runs per arm say nothing about rare events, and the medians are not a
  cost estimate.
- Deployment also needs ASTRO BOT clean on Q (a separate set, not yet written) and the lean build (its own compile).

## Result

(pending)

## Verdict

(pending)
