# 0247 — The bench's long flip gaps do not depend on the BVH compaction: they vary from run to run, and the worst kind is the host's kyty-gpu thread spinning while the GPU idles

**Question.** In exp 0246 (F304) only the run with nothing skipped (B: the BVH compaction 0x909974400 and the
reflection traversals both on) had a series of long flip gaps: 13 over 0.3 s, against 2 with the compaction skipped
(A) and 1 with the traversals skipped (C). All of them were game-thread time outside the host. What is the title's
thread waiting for in those gaps, and does it come with the compaction?

**Setup.**
- Lake bench of exp 0246 (`bench0247.sh` = `bench0246.sh` with only the number changed: the maintainer's lake save
  from a private copy, the outpost scene, then a frozen Photo Mode view; `SECS=300`, `LOADWAIT=90`). Shared build as
  in exp 0246, `KYTY_BC5_AT9_VIBRATION` at its default.
- Every run: `BC5_DIRECT_FLAT_APERTURE=1 BC5_DIRECT_AMM_PRT=1 BC5_DIRECT_TIMEOUT_PROBE=1 BC5_DIRECT_WAIT_TRACE=1
  KYTY_BC5_AMM_TRACE=1`, TF ring on (`raw/*-env.txt`). Alongside ran `hoststate0247.py` (here): exp 0215's read-only
  /proc sampler (the TCP session's), every 0.1 s, plus one line per period naming the six title threads with the
  most CPU. It started with each run and ended with its emulator.
- Runs, 2026-10-23 20:40–21:12, granted by the top session. The maintainer confirmed the B runs in this session
  ("Ok, działaj"), extending his yes for exp 0246:
  - E47A1 and E47A2: A, `SKIP_PGM=909974400`;
  - E47B1 and E47B2: B, `SKIP_PGM=1`;
  - E47S: A again, with `stackwatch0247.py` (here). It would take an `eu-stack` of the emulator whenever the host's
    kyty-gpu thread ran more than 240 of the last 300 ms after t 150 s (at most 30, at least 0.5 s apart). This run
    is not used for timing.
- `runarm0247.sh` (here) streamed the kernel log (`raw/kernel-*.txt`) and would have stopped a run at its first
  fault. `xarm0247.sh` (here) pulled the journal and emulator-log lines. `ana0247.py` (here) lines each flip gap over
  0.3 s up with the sampler (per-thread CPU and R/S/D state samples), the traced label waits and the AMM trace,
  using the log's "bc5 clock" line.
- Raw: `raw/stalls.txt` (every gap of the four timing runs and a 120-s baseline), `raw/frame-stats.txt`,
  `raw/E47A1-sampler-185-210.txt` (the sampler rows of E47A1's worst stretch), `raw/stacks-E47S.txt`,
  `raw/bench-*.txt`, `raw/kernel-*.txt`, `raw/*-env.txt`. The full sampler files, journals and emulator logs stay on
  the box and the laptop.

**Result.**
- **No run faulted:** 0 kernel fault lines, 0 ring or fence timeouts in all five.
- **The gaps vary from run to run, not with the setting.**

  | Run | Setting | Flip gaps > 0.3 s (in the frozen view) | Frozen view t 180–240 / 240–290: flips/s, GPU ms per frame (median) |
  |---|---|---|---|
  | E47A1 | A | 13 (11) | 26.0, 27.1 / 27.8, 26.5 |
  | E47A2 | A | 4 (1) | 28.8, 27.5 / 29.2, 27.0 |
  | E47B1 | B | 1 (0) | 28.9, 27.1 / 29.2, 27.0 |
  | E47B2 | B | 1 (1) | 28.8, 27.4 / 29.3, 27.2 |
  | E47S | A, stack watcher | 2 (0) | not used |

  With exp 0246 (E46A 2, E46C 1, E46B 13), seven runs give 1–13 gaps. The two series of 13 came once with the
  compaction on (E46B) and once with it skipped (E47A1). The frozen view runs at 28.8–29.3 flips/s and 27.0–27.5 ms
  of GPU per frame in every run, except E47A1's stretch with the series.
- **The series in E47A1 has one shape.** In 10 of its 13 gaps (0.33–0.68 s each, all ten in t 188–205 and
  t 285–297), three things hold at once (`raw/stalls.txt`, `raw/E47A1-sampler-185-210.txt`):
  - the title's Render Thread runs 79–97 % of the gap, almost all samples R: spinning, outside the host;
  - the host's kyty-gpu thread runs 77–95 % (KytyPlus's `GpuState::ThreadRun`, its own guest command processor:
    `src/graphics/guest_gpu/graphicsRun.cpp` in the patch). Its average over E47A1's frozen view is 173 ms/s,
    against 113–114 in the other runs;
  - the GPU is busy ~35 ms in the 0.68-s gap at t 195.6, and the host's game-thread time in label waits is 2.3 ms.

  Meanwhile game-main mostly sleeps (S), the traced label waits run at their usual rate, and there is no AMM or APR
  activity (`-` in the trace column). The other gaps in all runs are short loading stalls at t 33 and t 82–92, with
  game-main and the asset threads busy.
- **The stack watcher caught nothing.** E47S had no kyty-gpu stretch over its threshold (0 samples), so what
  kyty-gpu does then is not named.

**Verdict.**
- Exp 0246's "B alone stalls" was run-to-run variance. Over seven bench runs the number of long flip gaps does not
  follow the compaction or the traversals, and frame rate and GPU time per frame do not differ between the settings.
  This corrects F304's third point. Its first two stand: the compaction is a load-time burst, and neither path adds
  GPU time on the bench.
- The worst gaps on the bench are a host matter, intermittent and independent of the setting. KytyPlus's old guest
  command processor (kyty-gpu) works flat out for 0.4–0.7 s while the title's Render Thread spins on something the
  host thread provides, and the GPU idles. Next: catch one with the stack watcher (it now exists, and fires only on
  such a stretch), in whatever runs come, to name the host code.
- F268's halving in play is therefore not reproduced on the bench in any form. Neither GPU work nor a
  setting-dependent wait shows up in the outpost scene or the frozen lake view. Whether the compaction still halves
  play on today's build is a play test: a session with nothing skipped against exp 0218's 37.5 flips/s. It is also
  the way to complete reflections, since the default skip leaves them partial (F277, F304). That run removes the
  skip, so it is the maintainer's call.
- Limits: one route; the frozen view is not play; one to two runs per setting; WAIT_TRACE and the AMM trace on in
  every run.
