# 0264 — The BVH compaction on the second title's play route: ~3 % fewer flips and ~0.7 ms more GPU per frame, no fault, no visible difference in the route's reflections

**Question.** With the BVH compaction 0x909974400 running, the maintainer's play on 2026-10-22 ran at half its usual
frame rate (F268). On the lake bench the compaction cost no GPU time (F304, F306). On today's build — with the tiler
scratch pool (F311), the compute-state prefix (F321) and the SaveData sidecar fix (F319) — what does it cost on the
scripted play route? Does it fault there, and does it make the reflections more complete? (The box supervisor's
design, for the maintainer's compaction test.)

**Setup.**
- `ab0264.sh` (here): the TCP session's `catch0260.sh` with two arms, screenshots and a journal extract added.
  - Build: the shared normal build (md5 ce2e5d7a, built 15:26 with F319's SaveData fix) through `play-pkg.sh` with its
    defaults: `BC5_DIRECT_FLAT_APERTURE=1 BC5_DIRECT_AMM_PRT=1 BC5_DIRECT_CS_PREFIX=1`, TF ring, held tail, tiler
    pool, `PLAY_CAPTURE=1`. Each run's `/proc/<pid>/exe` matched the md5.
  - Arm A: the launcher's `BC5_DIRECT_SKIP_PGM=909974400` (the compaction skipped). Arm B: `BC5_DIRECT_SKIP_PGM=1`
    (nothing skipped). Both checked in the emulator's environment.
  - Interleaved A1, B1, A2, B2, 300 s each, 2026-10-24 15:35–15:56, on the box supervisor's grant. The maintainer
    confirmed the B runs in this session: "Tak, zgoda na biegi B z SKIP_PGM=1 w eksperymencie 0264."
  - Route: S6N's route (exp 0203's `o2-continue.cmd`, Continue at 85 s), from exp 0196's `saves-before-152617`, put
    in and taken back by exp 0196's `ab-restore.sh`.
  - Live saves: the PPSA03671 checksum was db52cb5f327c3de5 before the chain and after it. This is the state after
    the top session moved F319's stray `.blocks` sidecars out at 15:19.
  - The chain would have stopped at the first kernel amdgpu line (checked every second), TIMEOUT, crash or save
    mismatch.
  - spectacle screenshots at t 120/180/240/290 s per run. They stay on the box (`~/bc5-work/exp0264/raw/*-shots/`);
    only findings are written here.
- Laptop side: `stream0264.sh` (exp 0260's `stream0260.sh`, the lock line changed) streamed the kernel log and the
  journal's key lines throughout (`raw/kernel-stream.txt`, `raw/journal-stream.txt`).
- Statistics: exp 0211's `frameprof.py` over each run's frame-profile lines.
- Raw: `raw/frame-stats.txt`, `raw/run-summaries.txt`, `raw/skip-timelines.txt`, `raw/kernel-stream.txt`,
  `raw/journal-stream.txt`.

**Result.**
- **No fault, all four runs passed.** No crash line, no kernel amdgpu line (the laptop stream has only periodic MLD
  lines and one perf-rate notice), no TIMEOUT, and no give-up: every hold-tail summary reads "GIVEN UP 0". The saves
  came back identical after each run, and the chain's checksum matched. In B the compaction ran: no `skip pgm` line,
  where A logs the skip counter's 1st dispatch at t 41–42 s and its 4,097th at t 101–103 s.
- **The compaction costs a few per cent here, not half.** From `raw/frame-stats.txt`:

  | Run | Arm | Load t 0–100: flips/s | t 100–300: flips/s, GPU ms per frame median / p90, gaps > 0.4 s | t 150–300: flips/s, GPU median |
  |---|---|---|---|---|
  | A1 | skipped | 35.0 | 41.0, 14.3 / 15.8, 2 | 42.7, 14.5 |
  | B1 | running | 35.5 | 40.3, 14.9 / 16.5, 2 | 41.6, 15.1 |
  | A2 | skipped | 35.3 | 41.1, 14.4 / 15.9, 3 | 42.2, 14.6 |
  | B2 | running | 35.4 | 39.8, 15.1 / 16.9, 3 | 40.9, 15.4 |

  In t 100–300 B averages 40.1 flips/s against A's 41.0, about 2–3 % fewer. The GPU time per frame is about 0.6–0.8 ms
  higher at the median (4–5 %) and in the p90, in both pairs. The load is the same in both arms. The long gaps are
  as many: 2–3 over 0.4 s per run, none over 2 s.
- **The route's scene limits both comparisons.** After the Continue cutscene (t 120) the route stands from t ~150 s at
  the outpost's "Parry" tutorial prompt, waiting for input: a fixed combat scene, not moving play. The box was under
  heavy memory pressure in every run, alike in both arms: MemAvailable fell from ~13.3 GB to ~0.6 GB, with
  156–418 k pages swapped in and 6–9 s of PSI memory "full" per run. The tiler pool held 3 buffers for 11,264
  requests in every run.
- **Reflections: no visible difference in this scene.** At the same seconds, the wet ground, the vehicle and the
  lights show the same reflections in A and B; a gamma-raised crop of t 240 s was inspected. The whole-frame mean
  absolute difference between runs is as large within an arm as between arms: A1–A2 10.3, B1–B2 7.7, A1–B1 6.6,
  A2–B2 10.5 grey levels. Pose and rain differ from run to run. The scene has no mirror-like surface, so it cannot
  show what the compaction's trees add, unlike the lake or the creek of the 0211 screenshots.

**Verdict.**
- On today's build the BVH compaction runs on the play route without a fault in two runs. It costs about 3 % of the
  frame rate and about 0.7 ms of GPU per frame: a measurable cost, small next to F268's halving. Under the same
  heavy memory pressure in both arms it adds no long stalls. F268's halving is still not reproduced, on the bench or
  on this route. Today's build differs from the 2026-10-22 one in the tiler pool, which removed the per-flip
  allocation that stalled under memory pressure (F308, F311), the held tail, the compute-state prefix and the APR
  read-ahead. Which of these closed the gap is not shown.
- Whether the compaction makes the reflections visibly more complete is not shown here: the route's scene has no
  surface that would show it.
- Next, the maintainer's own play with `BC5_DIRECT_SKIP_PGM=1` (his "test 3"), through scenes with water, would
  answer both points: whether play still halves, and whether the reflections look complete. If it plays well, the
  launcher default could drop the compaction skip (his call).
