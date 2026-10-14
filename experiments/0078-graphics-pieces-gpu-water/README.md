# 0078 — graphics pieces on the GPU, in the water (ADR 0008, step 4)

**Question.** In the water, do graphics pieces behind the full-state prefix (experiment 0077)
remove the given-up waits and broken cycles? Do they keep the fluid on time, without faults or
hangs? What do they do to the frame rate?

**Setup.**
- The maintainer's play session of 2026-10-14 09:21–09:24, from the shortcut. Journal in
  `captures/play-20261014-0921`, private.
- `bc5-run.env` had `BC5_DIRECT_PIECES_FULL=1` and `BC5_DIRECT_PIECES_DRY=1` (backup
  `bc5-run.env.before-0078`), otherwise as in experiment 0076.
- The session reached the water of the Sky Garden level at about t = 140 s. It ended at 157 s.
- Comparison: experiment 0076, the same route without pieces (session 08:59).
- The maintainer judged the picture.
- Raw (labels masked):
  - `raw/play-0921-pieces.txt`: the first 100 `piece:` lines and the 10-s reports;
  - `raw/frameprof-waits.txt`;
  - `raw/frameprof-by-part.txt`: frame profile per part of the level, both sessions.

**Result.** In the water:

| | 0076, no pieces (140–175 s) | 0078, pieces (140–157 s) |
|---|---|---|
| waits given up or cycles broken, per 10 s | 82–283 | **1** (one cycle in the session) |
| pieces on the GPU | 0 | 205 in the last report (~10 s) |
| the wait after the head went | | satisfied in 204 of 205 |
| that wait, first 100 pieces | | 1–4 ms: 22, 4–8 ms: 78 |
| split points | dwords 11,000–22,000 | dwords 11,306–12,314 (11,306, 11,456, 11,454 most often) |
| fps | 43.3 | 43.4 |
| frame time mean / p90 | 22.9 / 28.6 ms | 22.8 / **24.7 ms** |
| game thread in the host mean / p90 | 9.9 / 17.1 ms | 10.0 / **10.9 ms** |
| label waits mean / p90 | 6.4 / 13.7 ms | 6.0 / **6.7 ms** |
| GPU busy per frame | 12.8 ms | 13.7 ms |
| GPU faults, hangs | | none |

- The maintainer saw normal water and no fluid delay.
- The one stop of experiment 0077 (run 321) did not occur.

By part of the level (`raw/frameprof-by-part.txt`):

| part | fps | GPU busy per frame | label waits |
|---|---|---|---|
| first part, 60–100 s | 34.9 (0076: 36.8) | 15.8 ms (15.4) | 7.5 ms |
| 100–140 s | 45.0 | 13.2 ms | 6.2 ms |
| the water, 140–157 s | 43.4 (0076: 43.3) | 13.7 ms (12.8) | 6.0 ms |

**Verdict.** Passed: ADR 0008 works in the water.
1. The given-up waits and broken cycles of the water are gone: 1 instead of 82–283 per 10 s.
   The head piece's label writes reach the GPU, so the compute queue's fluid tail can run and
   the main buffer's wait is satisfied. The fluid is no longer a frame late, as the maintainer
   confirmed.
2. The mean frame rate does not change. The game thread now waits 1–8 ms for work that really
   has to finish, where it used to give up at 8 ms. The spikes are gone: p90 frame time
   28.6 → 24.7 ms, game thread in the host p90 17.1 → 10.9 ms, label waits p90 13.7 → 6.7 ms.
   The water plays more evenly.
3. The water is not the slow part of the level. Its frames are lighter on the GPU (12.8–13.7 ms
   busy against 15.4–15.8 ms in the first part), which explains the maintainer's observation
   of more frames in and near the water. What limits the level elsewhere is GPU time and the
   two-buffer flip pipeline (F131), not the cross-queue waits.

Next:
- Keep `BC5_DIRECT_PIECES_FULL=1` in the play settings and watch longer sessions for the host
  stop of run 321 (the stack watcher is ready).
- Then make pieces the default and retire the 8 ms limit and the cycle break to fallbacks, as
  ADR 0008 says.
