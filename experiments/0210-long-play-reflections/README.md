# 0210 — The maintainer's long play with the reflections on and the AMM PRT fix: 15 minutes without a hang, with heavy stutter

**Question.** In play with the second title's ray-traced reflections running (`BC5_DIRECT_FLAT_APERTURE=1`, nothing
skipped, F249/F250) the GPU hung twice on 2026-10-22 morning (F251: the machine went down at 07:49, an
instruction-fetch fault at 08:16). Since then the TCP session found the AMM-window fix `BC5_DIRECT_AMM_PRT=1` (F257,
F260). Does a long play with the reflections on and that fix stay up, and how does it run?

**Setup.**
- BC-250 dev box, 2026-10-22 18:46:01–19:00:51, the maintainer playing; the box granted by the top session (box
  supervisor), `BOX-LOCK` held for the run, the TCP session streaming the kernel log; no `umr` wave dumps (F229).
- The shared build `~/bc5-work/kytyplus-build/src/kyty_emulator` (built 2026-10-22 10:22 from the shared tree, which
  carries both switches), started by `start.sh` (here) on the box display:
  `play-any.sh ~/bc5-data/pkg/game.pkg` with `BC5_DIRECT_FLAT_APERTURE=1 BC5_DIRECT_SKIP_PGM=1 BC5_DIRECT_AMM_PRT=1`
  over `play-pkg.sh`'s defaults (TF ring on). `BC5_DIRECT_SKIP_PGM=1` is a dummy: no program is skipped, so every
  traversal variant and the compaction 0x909974400 run. The environment was checked in the running process. No
  compute-state prefix (it exists only in exp 0195's binary; plan agreed with the compute session).
- Saves: the live `~/bc5-work/_SaveData/PPSA03671` copied to `~/bc5-work/exp0210/saves-before-184600` and not
  restored afterwards (the progress is the maintainer's). `stop.sh` released the lock.
- Capture `~/bc5-data/captures/play-20261022-1846` (journal 156 MB), emulator log `~/bc5-work/play-pkg-last.log`.
  Raw: `raw/play-summary.txt`.

**Result.**
- **No hang, no fault, no machine-down.** The title ran 886 s and the maintainer quit it normally (exit 0); the boot
  is the same before and after (16:37:49). The journal has the six `flat aperture` lines (0x11d049aa00, 0x11d040e200,
  0x11d0488a00, 0x11d04bb900, 0x11d040c900, 0x11d04a6000: each patched at its first dispatch), no `skip pgm` line,
  0 fence timeouts, no `timeout: fault`; the kernel log has no amdgpu line in the run.
- **Heavy stutter.** Twelve GPU jobs took 0.37–4.23 s (t 106: 1.58 s; t 123: 0.89 s; t 155.8: 4.23 s; then 0.37–0.54 s
  at t 214, 266, 302, 306); 20 flips came more than 0.4 s apart, the longest 5.47 s (t 242.6) and 4.30 s (t 155.8);
  the mean per minute was 10.0–31.9 flips/s (minutes 0–14: 29.6, 15.0, 31.9, 21.6, 15.0, 13.1, 10.0, 13.1, 24.6, 31.8,
  26.4, 16.7, 19.8, 21.0, 28.3).
- **The reflections roughly halve the frame rate and multiply the long stalls.** `frameprof.py` (here) over the
  journal's per-flip "frame profile" lines (`raw/frame-stats.txt`), against the maintainer's own sessions of the same
  day with the reflections skipped (the launcher's list), in the same night levels:

  | Session | Setup | Flips/s (mean; per 20 s median, min) | Flip gaps > 0.4 s / > 2 s, longest | GPU busy per frame median / p90 | Outside-host > 0.1 s / > 1 s |
  |---|---|---|---|---|---|
  | 1846 (this run, 879 s) | reflections on, AMM_PRT, shared build | 18.5; 17.6, 3.9 | 219 / 6, 7.05 s | 15.7 / 32.5 ms | 637 / 30 |
  | 1430 (1,151 s) | skips, AMM_PRT, shared build (ended in the 14:50 machine-down) | 39.4; 40.1, 22.9 | 12 / 1, 2.68 s | 11.4 / 16.1 ms | 85 / 3 |
  | 1136 (1,038 s) | skips, CS prefix (exp 0195 build) | 41.8; 44.5, 23.1 | 16 / 4, 9.01 s | 13.8 / 15.7 ms | 32 / 8 |
  | 1345 (674 s) | skips, CS prefix, arm B of exp 0198 | 38.3; 39.5, 21.1 | 21 / 2, 10.0 s | 13.4 / 15.4 ms | 79 / 7 |

  The closest comparison, 1430, differs only in the reflections (same build, AMM_PRT on): the flip rate falls from
  39 to 18.5 a second, the GPU time per frame doubles in its upper tail, long flip gaps are 18 times as frequent,
  and the game thread waits outside the host far more often (637 frames over 0.1 s against 85). In this run's slow
  20-s windows (6.6–11 flips/s, t 322–462 s) the host's per-second GPU busy sum stays at 220–400 ms and the outside
  time at 600–690 ms: the title waits for something the host's game-thread GPU accounting does not show (work on
  the ring thread, or its own polling of GPU results). Multi-second stretches also occur with the reflections
  skipped (F254, F256, F266) and the box plays under memory pressure (F256), but at a much lower rate. The idle
  night runs of exp 0191 showed no such cost (F1/F2 vs B0): the expense appears where the camera sees reflective
  surfaces in play.
- Earlier the same day the same reflection settings without AMM_PRT hung at t ≈ 287 s (07:44, machine down) and
  t ≈ 470 s (08:16, instruction fetch at 0x80'0000005000); this session passed both times and ran to 886 s.

**Verdict.**
- With `BC5_DIRECT_AMM_PRT=1` the reflections-on play stayed up for 15 minutes — the first such session without a
  hang; one session is not proof (the earlier hangs came at 5–8 minutes).
- The play slows down heavily ("Bardzo mocno spowalniała", the maintainer): about half the frame rate of his sessions
  with the reflections skipped (18.5 against 38–42 flips/s), with long stalls 10–18 times as often. That is the cost
  of the reflection passes now running on this host, not of the aperture fix itself (two constants) nor of AMM_PRT
  (session 1430 had it at 39 flips/s). On the console these passes fit a 30-fps frame; why they cost this much here
  is open — candidates: walks that run very long on incomplete per-frame trees (F104's leaf lists filled by builder
  dispatches the host drops), the deep-stack scratch path, and the compaction's BVH work the skips also removed.
- The launchers keep the skips. Next: separate the traversal from the compaction (a play with only 0x909974400
  skipped), then time the traversal dispatches themselves.
