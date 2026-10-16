# 0131 — ASTRO BOT on the compute ring: title screen and galaxy map unchanged at 60 fps, the water not reached

**Question.** Does ASTRO BOT run with the compute ring settings of experiment 0129
(`BC5_DIRECT_COMPUTE_RING=0`, `BC5_DIRECT_CROSS_RING_WAITS=all`)?
- Its play settings differ from the second title's:
  - GDS for every job (`GDS_ALL`);
  - deferred flips;
  - graphics pieces (`PIECES_FULL`).
- The water level is the case that matters: its graphics and compute buffers wait on each other
  (ADR 0008).

**Setup.**
- BC-250 dev box, 2026-10-16 07:20–07:34, maintainer present, hang watcher on, no pad input.
- **Runs 542 / 543** (`exp0131.sh`): the start with the play settings (`bc5-run.env`), 70 s,
  no input. Job timestamps from 40 to 55 s.
- **Runs 544 / 545** (`exp0131w.sh`): run 410's scripted route toward the Sky Garden water
  (`input318.cmd`), 200 s. Job timestamps from 140 to 155 s, screenshots at 100, 140 and 170 s.
- The second run of each pair has the compute ring.
- Raw: `raw/runs-542-545.txt`.

**Result.**

| run | where | ring | fps | game thread in host | rings busy at once | timeouts / faults |
|---|---|---|---|---|---|---|
| 542 | title screen | one | 58.6 / 59.4 | 6.4 ms | — | 0 / 0 |
| 543 | title screen | compute ring, `all` | 58.3 / 59.7 | 6.4 ms | 6.2 % | 0 / 0 |
| 544 | route, galaxy map | one | 59.0 / 59.8 / 59.8 / 57.6 | 6.7 ms | — | 0 / 0 |
| 545 | route, galaxy map | compute ring, `all` | 57.5 / 59.4 / 59.5 / 57.6 | 7.2 ms | 8.7 % | 0 / 0 |

- **The route ended on the galaxy map**, in front of a planet. It did not get into the Sky
  Garden: the scripted presses no longer match the save. No graphics piece was split (0 in both
  runs), as expected outside the water.
- **Compute is a small part here:** 11 % of the GPU time on the compute ring, against about half
  on the second title's start screen.
- **Waits given up** (the 8 ms limit): 1 against 5 on the title screen, 3 against 6 on the route.

**Verdict.**
- ASTRO BOT runs on the compute ring with GDS on both rings: no fault, no reset, and the 60 fps
  cap is held.
- There is nothing to gain where it was measured: it is capped and compute is light.
- **The water is untested.** It needs a route that reaches it, or the maintainer driving.
  - Until it passes, ASTRO BOT's shortcut keeps one ring.
  - The second title's shortcut has the compute ring since 2026-10-16 (maintainer's yes).
