# 0211 — What the reflections cost: the traversal against the BVH compaction, in a fixed lake view

**Question.** In the maintainer's long play with the reflections on (exp 0210, F268) the second title ran at half its
usual frame rate (18.5 against 38–42 flips/s). With `BC5_DIRECT_SKIP_PGM=1` two kinds of work came back at once: the
six compiled reflection-traversal variants (patched by `BC5_DIRECT_FLAT_APERTURE`) and the BVH neighbour-link
compaction 0x909974400 with the per-frame tree work that consumes it. Which of the two costs the frame time, and how
much per frame in the same view?

**Background (from exp 0210, moved here with its script).** `trend.py` (here) over the journals of session 1846
(reflections on) and the maintainer's session 1430 (same shared build and `BC5_DIRECT_AMM_PRT=1`, reflections
skipped), per minute (`raw/trend.txt`): the cost does not accumulate with playing time. Flips/s in 1846 (27, 13, 27,
19, 12, 11, 9, 12, 24, 29, 24, 13, 17, 19, 12) follow the count of frames whose GPU busy exceeds 50 ms (31–55 a minute
in the slow minutes, 9–25 in the good ones; 1–7 a minute in 1430), i.e. what the scene in view asks of the
reflection passes. Pinned memory (9.5 → 11.5 GiB) and host mappings (~23–24 k) rise in the first 3–4 minutes and
then hold, the same in 1430 (9.6 → 11.5 GiB, 21–24 k): not memory. The maintainer's "worse the longer I played" was
where he went.

**Setup.**
- The water session's lake bench (`~/bc5-work/exp0205/bench0205.sh`, the maintainer's lake save copy, a frozen Photo
  Mode view of the near lake that keeps rendering), on the shared build, with three settings over the launcher's
  defaults: A `BC5_DIRECT_FLAT_APERTURE=1 BC5_DIRECT_AMM_PRT=1 BC5_DIRECT_SKIP_PGM=909974400` (traversals on, the
  compaction skipped); B the same with `BC5_DIRECT_SKIP_PGM=1` (nothing skipped); C the launcher's skips with
  `BC5_DIRECT_AMM_PRT=1` (reflections off), repeated as R11D. The same frozen view in all of them.
- Measures: per-flip journal statistics (exp 0210's `frameprof.py`): flips/s, GPU busy per frame, flip gaps; B − A
  is the compaction's share, A − C the traversal's.
- Run on 2026-10-22 under the top session's box grants (19:16 and 20:25), each run holding `BOX-LOCK`;
  `bench0211.sh` (here) is the water session's `bench0205.sh` with only the lock text and the output directory
  changed (its consent); `BC5_EMU` in `ENVX` puts the shared build (`~/bc5-work/kytyplus-build/src/kyty_emulator`)
  in place of exp 0194's binary. The bench resets its private lake-save copy before each run; the live saves were
  not touched. Kernel log: the TCP session's stream for R11C–R11B, my own laptop-side stream for R11D
  (`raw/R11D-kernel-stream.txt`), and each run's own dmesg summary (`raw/run-summaries.txt`).
- Raw: `raw/arm-stats.txt` (whole runs), `raw/arm-frozen.txt` (the frozen-view windows), `raw/R11B-kernel.txt` (the
  TCP session's copy of R11B's kernel lines, 19:26–19:31), `raw/run-summaries.txt`, `raw/trend.txt` (exp 0210's
  sessions, see Background). Screenshots stay on the box (`~/bc5-work/exp0194/r-R11*/shots/`).

| Run | Settings over the launcher (shared build, AMM_PRT=1 in all) | View reached | Kernel / journal | Result |
|---|---|---|---|---|
| R11C | launcher skips | no: the load came late, the Photo Mode keys landed in the menu, a town rooftop | 0 faults, 0 timeouts | not a baseline |
| R11A | `FLAT_APERTURE=1`, `SKIP_PGM=909974400` (traversals on, compaction skipped) | yes, frozen lake view | 0 faults, 0 timeouts | measured |
| R11B | `FLAT_APERTURE=1`, `SKIP_PGM=1` (nothing skipped) | no: faulted during the load | 10 fault lines, 2 ring timeouts/resets; 2 fence timeouts | stopped, emulator ended at 19:30:03 |
| R11D | launcher skips, `LOADWAIT=90` (R11C repeated) | yes, frozen lake view (camera at another angle) | 0 faults, 0 timeouts | measured |

**Result.**
- **In the frozen lake view the traversals cost almost nothing.** Frame statistics over the frozen-view windows
  (`raw/arm-frozen.txt`): R11A (traversals on, compaction skipped), t 170–279 s: 26.0 flips/s (per 20 s 23.0–28.5),
  GPU busy per frame median 27.2 ms (p90 29.7), 12 flip gaps over 0.4 s, none over 0.56 s. R11D (reflections off),
  t 215–280 s: 28.0 flips/s (26.4–28.8), GPU busy median 27.9 ms (p90 30.0), 2 gaps over 0.4 s. R11A ran with no
  traversal variant skipped and no fault or timeout.
- **With the compaction running as well (R11B) the GPU faulted before the view was reached.** At 19:28:30 TCP write
  faults (ring 40, vmid 7, status 0x00741051: page not present, write) hit heap pages from 0x1208a7c000, then the gfx
  and compute rings timed out at 19:28:32 and were reset (both succeeded, the machine stayed up); the journal has the
  graphics buffer #118195 (31,651 dwords) and the compute buffer #118205 timed out, and the host saved a learned
  region 0x1206000000+0x6000000. R11A, identical except that the compaction 0x909974400 was skipped, ran 279 s clean.
  The TCP session records R11B as the second case of its non-AMM write class (the first, L7 at 0x1765833000, came
  with the compaction skipped: the class has more than one source).
- **Caveat on the view.** Photo Mode shows "Visual Effects: Stop" and the frame cost there (≈ 27–28 ms of GPU per
  frame in both arms) may not be the one of play; the reflections' share in play (exp 0210: 18.5 against 39 flips/s)
  is not reproduced by a frozen view. One run per arm.

**Verdict.**
- The traversal itself (all six variants with the aperture fix) is not shown to be the reflections' cost: in the
  same frozen lake view it adds nothing measurable to the frame (26.0 vs 28.0 flips/s, the same GPU time per frame).
- The compaction path is the one tied to the faults: with it running the GPU wrote unmapped heap pages and the rings
  were reset within ~2.5 minutes, where the same run without it was clean. In exp 0210 both ran; the play slowdown
  there may come from the compaction's per-frame BVH work rather than from the traversal — not shown here.
- Next: a play (not a frozen view) with only the compaction skipped (`FLAT_APERTURE=1`,
  `SKIP_PGM=909974400`, AMM_PRT) against exp 0210's numbers — that separates the two costs where they appeared. The
  compaction's heap writes belong to the TCP session's fault class.
