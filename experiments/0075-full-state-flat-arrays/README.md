# 0075 — the full-state tracker on flat arrays

**Question.** In experiment 0074, following the graphics queue's full state cost 1.6–3.3 s of
CPU per 10 s, with a `std::map` per register space. Do flat arrays over each space's range bring
that down far enough to keep the tracker on during play?

**Setup.**
- `bc5::full_state::Tracker` keeps each register space as a value array and a "set" byte array.
  Sizes come from Mesa `src/amd/common/sid.h` (sparse clone at `0866ae7`):
  - config 0x8000–0xB000;
  - SH 0xB000–0xC000;
  - context 0x28000–0x30000;
  - UCONFIG 0x30000–0x40000.

  Offsets past a space's range go to a map. The prefix and all comparisons are unchanged.
- Unit tests: 48 cases, all pass.
- Run 318 (`run318.sh`, otherwise the same as run 317: `BC5_DIRECT_PIECES_DRY=1`, Sky Garden from
  the save, 150 s).

**Result.** From `raw/run318-pieces-dry.txt` and `raw/frameprof-100-148s.txt`:

| | run 317 (`std::map`) | run 318 (flat arrays) |
|---|---|---|
| CPU for following the state, per 10 s | 1,650–3,266 ms | **126–335 ms** |
| split points (waits not satisfied on arrival) | 5,567 | 11,064 |
| kept for the GPU / served on the CPU / given up | 5,491 / 76 / 0 | 9,787 / 1,253 / **24** |
| prefix build, in all; longest | 597 ms; 0.38 ms | 556 ms; 1.0 ms |
| frame rate 100–148 s | 55.0 fps | 59.9 fps |

The input script is open loop, so the two runs did not play the same scenes. The frame rates
are not a like-for-like comparison. In run 318 the game ran at the display rate in that window.

**Verdict.** Passed:
- Following the state now costs 1–3 % of a core, about ten times less than with `std::map`.
- The tracker can stay on in play sessions.

Run 318 also had the first 24 waits that were given up at a split point, outside the water.
These are where ADR 0008 would really split. The water is still to be measured (step 2
continued).
