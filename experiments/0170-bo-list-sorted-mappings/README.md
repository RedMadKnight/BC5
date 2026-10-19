# 0170 — The submitting thread walked all ~17,000 GPU mappings for every submission; the backend now keeps them sorted and counts them per BO

**Question.** After exp 0169 the second title's render thread still spent 8–12 ms of each frame
in the host. Of the direct path's "prepare" (4.9 ms a frame without chains, 2.6 ms with them),
only 1.3 ms were the timed phases (filter, trackers, nested copies, copy); where does the rest go?

**Setup.**
- Run 820 (`BC5_DIRECT_CHAIN=2`, the gameplay route of `route.sh`, exp 0169) with `eu-sampler.sh`
  sampling the render, game and ring threads every 0.15 s (140 samples), histogrammed by the
  innermost host function (`stackhist.py`, here).
- The per-frame prepare split from the frame profile (`prepare = filter + tracker + cu + nested +
  copy`; the remainder is the BO list).
- Change (`backend/src/direct.cpp`): `shared_maps` is kept sorted by address (`map_shared` inserts
  at its place, `unmap_shared` finds by binary search, `free_shared` removes in one pass); each
  imported BO counts its mappings. The full BO list (submissions with draws) takes the BOs with a
  non-zero count instead of walking every mapping and searching the list built so far; the short
  BO list (submissions without draws) finds the mappings around each operand by binary search —
  valid because the direct mapper never maps two pieces over the same addresses, which is checked
  once per change of the list (with the old walk as the fallback); `sorted_mappings` merges the few
  userptrs into the already sorted list instead of sorting ~17,000 entries at each change.
- Runs 821 (chains) and 822 (no chains) with the change, against 820 and 818 (exp 0169), same
  route, `stallcmp.sh`.

**Result.**
- Run 820's render thread: 78 of 140 samples in the direct path — `Device::submit` 25,
  `SubmitEopFlip` (the drain before a flip) 22, `Device::sorted_mappings` 17 (the full sort at each
  change of the list), the chain logic 19; the title's own code ~37.
- The untimed part of prepare: 3.59 ms a frame without chains (run 818), 1.34 ms with them (820).

| | 818: no chains, old | 822: no chains, new | 820: chains, old | 821: chains, new |
|---|---|---|---|---|
| flips per second | 33.1 | 40.9 | 46.2 | 49.2 |
| mean frame | 30.6 ms | 24.5 ms | 21.8 ms | 20.4 ms |
| host per frame | 12.1 ms | 8.2 ms | 8.5 ms | 6.9 ms |
| of it prepare | 4.9 ms | 1.4 ms | 2.6 ms | 1.3 ms |
| frames over 70 ms | 6 | 6 | 3 | 5 |
| audio rate | 0.999–1.001 | 0.999–1.001 | 0.999–1.001 | 0.999–1.001 |

  Run 821 had one 1.0 s frame at t 143 s with the GPU busy for 1,001 ms in 10 jobs and the host
  idle (3.9 ms): the GPU-side stall of F208, not the host. No ring reset in either run.
- The backend's unit tests do not cover this file (it needs `amdgpu`); the box's backend build
  (`backend-ubuntu`) has no test targets. The six direct-path tools of that build compiled and linked.

**Verdict.** The BO list cost the submitting thread 2–3.5 ms a frame walking every mapping; with the
mappings sorted and counted per BO it is gone (F225). Without chains the second title now runs at
41 frames a second (was 33), with chains at 49. What remains of the host's frame: the CS ioctls
(1.8 ms with chains, 4.4 without) and the drain before each flip (the console queues the flip behind
the GPU work; the host waits for it — next).
