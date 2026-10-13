# 0068 — a clean repeat of 0067, and the level load with large imports

**Question.** Experiment 0067's live run (296) shared the machine with an `rpm-ostree` transaction
on a full disk. What does the filter's fast path give in a clean run?

**Setup.** Run 297 (2026-10-13 14:05):
- the build of 0067, with udmabuf at 1024 MiB (0066);
- the settings of run 282 and the scene of 0061;
- the disk at 88% after the maintainer's clean-up;
- `rpm-ostree` idle.

The level's load left no long frame, so the window is set from the frame rate: the galaxy map at
60 fps until t≈130 s, then 44–47. Window 205–285 s. Raw data is in `raw/run297.txt`.

**Result.**

| | run 295 (0066) | run 297 |
|---|---|---|
| fps | 45.9 | **46.5** |
| frame, mean | 21.8 ms | 21.5 ms |
| filter | 1.72 ms | 1.42 ms |
| prepare | 3.0 ms | 2.7 ms |
| game thread inside the host | 5.1 ms | 4.9 ms |
| timeouts, waits given up | 0, 0 | 0, 0 |

Also observed: the level loaded in about 18 s with no frame over 120 ms. The runs with 64 MiB
imports had several frames of 0.3–2 s during the load.

**Verdict.** The fast path gives +1.3% in the later level, as measured offline. ASTRO BOT's later
level runs at 46.5 fps, from 34.9 at the start of experiment 0061.
