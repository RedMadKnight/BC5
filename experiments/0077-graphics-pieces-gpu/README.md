# 0077 — graphics pieces on the GPU, outside the water (ADR 0008, step 3)

**Question.** Does a graphics buffer split at a wait, with the rest behind the full-state
prefix, run on the GPU without the fault of runs 44 and 123, and without hanging the machine?

**Setup.**
- KytyPlus patch with `BC5_DIRECT_PIECES_FULL=1` (commit f95e9e4).
- A game-thread `dcb` buffer is split only at a wait that meets all three conditions:
  - it is not satisfied on arrival;
  - ring order does not leave it to the GPU;
  - it is not served within the 8 ms limit, or it is a broken cycle.
- The split works as follows:
  - the head goes to the GPU;
  - the wait is tried again for up to 8 ms;
  - the rest follows behind the `bc5::full_state` prefix of ~1,260 dwords.
- `BC5_DIRECT_PIECES_DRY=1` kept its counts.
- Runs 321 and 322 (`run321.sh`, `run322.sh`), 2026-10-14 09:08 and 09:12, with the maintainer
  present:
  - the same input script as runs 315–318, 150 s, from the title to the galaxy map;
  - the root hang watcher (`bc5-gpu-hang-watch`, experiment 0058) running;
  - a screenshot every 10 s;
  - in run 322, also `stackwatch.sh`: thread stacks if the journal stops growing.
- Kernel 7.2.8-ogc5.1.
- Raw (labels masked): `raw/run-0908.txt` (run 321), `raw/run-0912.txt` (run 322).

**Result.**

| | run 321 | run 322 |
|---|---|---|
| pieces on the GPU (`piece:` lines) | 7, at 13–44 s | 13, at 1–49 s |
| split points | all at dword 115 of buffers of 10,000–44,000 dwords, the frame's first cross-queue wait | |
| the wait after the head went | 5 of 6 satisfied (0.0–7.7 ms), 1 not | 12 of 13 satisfied, 1 not |
| GPU faults, timeouts, ring stalls | none (dmesg, hang watcher silent) | none |
| picture | clean (save menu, galaxy map) | clean (galaxy map, 59 fps) |
| end of the run | the game stopped at 49 s at the save menu; the frame counter stood still until the 150 s limit | ran to the 150 s limit |

Run 321's stop:
- The journal ends at t = 48.9 s, in the middle of a line.
- The last piece was at 43.9 s, 5 s earlier, and the frames went on in between.
- There was no GPU error, and the hang watcher saw no stall. It was the host or the game that
  stopped, not the GPU.
- Run 322, identical, did not stop. Its stack watcher fired once at 50 s while the game was
  running: a false alarm, as the journal pauses during loads.

The cause of run 321's stop is unknown.

**Verdict.** Passed for its question outside the water:
- 20 graphics pieces ran on the GPU behind the full-state prefix with no fault and no hang. The
  same kind of split faulted in run 123 when it replayed only its own buffer's state.
- Run 321's host-side stop is open: not reproduced in run 322, and not tied to a piece in time.
  If it comes back, the stack watcher captures it.

Next is step 4: the water, with the maintainer present. That means `BC5_DIRECT_PIECES_FULL=1`
in a play session: are there fewer given-up waits and broken cycles, and is the fluid still a
frame late?
