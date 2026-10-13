# 0074 — graphics pieces built but not submitted, outside the water (ADR 0008, step 2)

**Question.** Where would the host split graphics buffers, and how often? What does a piece's
full-state prefix cost to build? What happens to those waits now, without the split?

**Setup.**
- KytyPlus patch, `BC5_DIRECT_PIECES_DRY=1`:
  - At every memory wait of a game-thread `dcb` buffer that is not satisfied when reached, the
    host builds the later piece's prefix and submits nothing differently. These are the points
    where `BC5_DIRECT_PIECES` would split the buffer.
  - The prefix comes from `bc5::full_state` (experiment 0073), starting from the graphics queue's
    state before the buffer, which `piece_check()` follows.
  - The host counts the splits, prefix sizes and build time.
  - It also counts what then happens to each wait: kept for the GPU by ring order, served on the
    CPU, or given up or broken as a cycle.
- Run 317 (`run317.sh`): run 316 with `BC5_DIRECT_PIECES_DRY=1` instead of
  `BC5_DIRECT_PIECE_CHECK`, the same input script (Sky Garden from the save, 150 s). Kernel
  7.2.8-ogc5.1.
- Frame rate: `frameprof.py` over 100–148 s of runs 317, 316 (the check of 0073) and 315 (neither
  knob).

**Result.** Run 317, 14 reports (`raw/run317-pieces-dry.txt`):

| | |
|---|---|
| waits not satisfied when reached (split points) | 5,567 in ~140 s, up to 1,104 per 10 s |
| of these, kept for the GPU by ring order | 5,491 (98.6 %) |
| served on the CPU | 76 |
| given up or broken as a cycle | **0** |
| prefix | 1,260–1,261 dwords |
| build time per prefix | 0.10–0.38 ms; 597 ms in all |
| following the state (all graphics buffers) | 1.6–3.3 s CPU per 10 s |

Frame rate over 100–148 s (`raw/frameprof-100-148s.txt`):

| Run | Knob | fps | game thread in the host, mean |
|---|---|---|---|
| 315 | none | 56.0 | 12.2 ms (label waits 10.0) |
| 317 | `PIECES_DRY` | 55.0 | 6.6 ms (label waits 4.6) |
| 316 | `PIECE_CHECK=30` | 50.4 | 3.7 ms (label waits 1.8) |

The state tracking takes time that the game thread otherwise spent in label waits, so the frame
rate drops by about 2 %. The full check of 0073 costs about 10 %.

**Verdict.** Passed for its question outside the water:
- Building a piece costs a prefix of ~1,260 dwords and 0.1–0.4 ms of CPU.
- Almost every wait that is not satisfied on arrival is one that ring order already leaves to the
  GPU. None was given up or broken.
- The rule of ADR 0008 holds: split only where a wait can be neither served nor left to the GPU.
  Here that is never.

Following the state costs 16–33 % of a CPU core. It uses `std::map` per register, so flat arrays
are the obvious change before pieces are used for real.

Not yet measured: the water, where 0072's sessions had ~500 given-up waits and ~50 broken cycles
a minute. That is a new experiment. Its run has to reach the water: the maintainer plays there,
or a route is replayed.
