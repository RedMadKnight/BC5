# 0076 — graphics pieces built but not submitted, in the water (ADR 0008, step 2 continued)

**Question.** In the water, how often would the host really split a graphics buffer? These are
waits that are neither satisfied, nor left to the GPU by ring order, nor served within the
limit. What does that cost, and what do those waits cost today without the split?

**Setup.**
- The maintainer's play session of 2026-10-14 08:59–09:02, started from the shortcut. Journal
  in `captures/play-20261014-0859`, private.
- `bc5-run.env` had `BC5_DIRECT_PIECES_DRY=1` (experiment 0074; tracker on flat arrays, 0075).
  Ring order waits were on; nothing was submitted differently.
- The session reached the water of the Sky Garden level at about t = 140 s of the journal. It
  ended at 175 s.
- The water is identified by the main graphics buffer's waits at dwords 11,000–22,000 and by
  the broken cycles, as in HANDOFF F64.
- Raw: `raw/play-0859-pieces-dry.txt` (17 reports, one per 10 s), `raw/frameprof.txt`,
  `raw/waits.txt` (labels masked).

**Result.**

| | before the water (0–140 s) | in the water (last 3 reports, ~30 s) |
|---|---|---|
| frame rate | 46.7 fps | 43.3 fps (140–175 s) |
| waits not satisfied on arrival, per 10 s | 350–810 | 621–829 |
| of these, given up or broken (real split points), per 10 s | 0–1 | **82, 283, 139** |
| real split points per frame | ~0 | ~0.4 |
| prefix | 1,260–1,261 dwords | 1,261 dwords |
| prefix build, longest | 0.18–0.73 ms | 0.28–0.68 ms |

The unsatisfied waits of the whole session (`raw/waits.txt`):
- 365 were broken as cycles after 0.1–0.3 ms;
- 163 were given up at the 8 ms limit, about 1.3 s of the game thread waiting in vain;
- the most frequent offsets are 21,807, 20,841, 11,379, 22,185 and 11,456 in buffers of about
  25,200 dwords.

In 140–175 s the game thread spent a mean of 6.4 ms per frame in label waits (p90 13.7 ms).

**Verdict.** Passed for its question:
- In the water, a split at a wait that can be neither served nor left to the GPU comes about 0.4
  times a frame, 80–280 per 10 s.
- Each split costs a prefix of ~1,260 dwords and under 1 ms to build.
- Outside the water there are almost none.

The given-up waits cost the game thread about 1 ms a frame on average. The broken cycles leave
the fluid a frame late (F64). Both are what pieces would remove.

ADR 0008 step 2 is done. Step 3 (`BC5_DIRECT_PIECES_FULL=1`, pieces on the GPU) runs first
outside the water, and only with the maintainer present.
