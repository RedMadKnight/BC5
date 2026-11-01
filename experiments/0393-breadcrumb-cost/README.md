# 0393 — What the dispatch breadcrumbs cost per frame, on the same route

**Date.** 2026-11-01 10:46–11:48. **Box.** On the top session's GO (read, build and series under one GO, ahead of RR5 and
0391, deadline 12:11:52). One lock line per step, `tcp exp0393 | token … |`, with claim and done lines in
`~/bc5-work/BOX-QUEUE`. **Asked by.** The maintainer's yes of 2026-11-01 to the same-route cost test.

**Question.** Exp 0277 added a breadcrumb in front of and behind each dispatch, with the instruction "Measure its cost
per frame in the first run". That was never done: F351 says the cost was not measured, and exps 0277, 0279 and 0281 ran
RT off, with different routes in the arms. On today's setup, with RT on and on one route:

1. What do level 1 and level 2 cost per frame, in GPU busy, host time and flip interval?
2. Do they still behave: every sampled breadcrumb reached and done, no ring timeout, no refused submission? Today's
   frames are larger (dcbs of ~250,000 dwords), one ring carries the compute buffers (exp 0342), and the rebuild now
   runs ahead of exp 0349's IB split.
3. So can they stay in a private catcher build without changing what they catch, and at what level?

## Setup

- **Binary.** One private binary for all arms, `~/bc5-work/exp0393/kyty_emulator`. `run0393.sh build` applies
  `patch0277.py` unchanged through `patch0393.py` to the tree's unit (29b3d8c6, main at 5b22f700, result 1ed25bdf; all 18
  anchors unique, checked on the laptop) and links it from the shared normal build's objects, as exps 0277 and 0281. The
  shared binary's md5 is read before and after. Switch `BC5_DIRECT_BREADCRUMBS`: unset off, `1` level 1, `2` level 2.
- **Arms.** O off, L level 1, T level 2, one letter per run tag. Order `O1 L1 T1 O2 L2 T2 O3 L3`, mixed against drift,
  420 s each, about 60 min with restarts, deadline 85 min (`series0393.sh`).
- **Route.** The S6N route as exps 0350–0378, RT on: exp 0196's `saves-before-152617` copied into a private working
  directory for each run, `exp0203/o2-continue.cmd`, the input configuration with `RayTracing.PPSA03671=on`. Exp 0378's
  run on this route had a plateau of 403–413 flips per 10 s from 160 s to 590 s (its `raw/B1-flips-per-10s.txt`).
- **No play.** Nobody touches the pad during the series. The input script is timed, a pad would change the scene, and
  each run ends with a timed stop, which on the screen looks like a crash.
- **Runner.** `mk0393.py` makes `run0393.sh`, `go0393.sh`, `s6n0393.sh` and `prestart0393.sh` from exp 0388's kit
  (0e87a5d2) by literal edits: atomic claim by hard link, one token per step, a private launcher copy (own log, working
  directory, save directory, learned file), a start check after the launcher's last settings load, pins checked under
  the lock (`pins0393.env`, values from `read0393.sh`), no live-save gate. The launcher's anchors are checked again on the
  box at each run.
- **Stops.** The first kernel amdgpu line, devcoredump, TIMEOUT line, crash or failed gate ends the series, no retry. An
  arm is proved twice: by the emulator's environment and by the journal (no breadcrumb line in O; the level line and
  health lines in L and T).
- **Tests.** `test0393.sh`, laptop only, stand-ins for ssh, scp and the box's reads, with the real launcher text and
  the real unit from patch 0001. The first full pass gave 33 of 35. Both failures were faults of the stand-ins (a fake
  binary that was not executable, a fake clock not reset between series runs). LESSONS R45/R48 then showed that the kit
  had inherited exp 0388's reads of the live saves; `mk0393.py` removed them, and a run now records its private copy's
  sum in `<tag>-copy.txt`. After both fixes `bash test0393.sh arms`, `build` and `series` gave 11/11, 9/9 and 3/3. The
  `proof` and `stops` groups passed on the first pass and were not repeated. `ana0393.py` was tried on synthetic frames
  with known differences.
- **What is kept.** Summaries, flip tables, breadcrumb health lines and the kernel stream go to `raw/` through
  `fetch0393.sh`. The frame profile lines (numbers only, ~5 MB a run) stay out of the repo. Journals and play logs stay on
  the box.

## Reading rule

Written before any run. The window is 200–400 s of journal time, inside the plateau.

- The primary numbers are means per frame from the `frame profile` lines: GPU busy, game thread inside the host,
  prepare, its copy part, and the flip interval. Flips/s alone is not enough: on exp 0378's plateau a flip came every
  ~24.5 ms with ~19 ms of GPU busy, which may be a pace and not a limit, so a real cost could leave flips/s flat.
- A difference counts as **resolved** only if it is larger than the spread of the three O runs. Otherwise it is
  reported as "below X ms", with X that spread. Run-to-run spread on this setup is not known yet; the three O runs
  measure it.
- A level is **cheap enough for a catcher build** if its resolved extra GPU busy plus host time stays under 2 % of the O
  flip interval (~0.5 ms a frame) and no flip-interval change is resolved. That is a judgement for a private build
  only. Whether anything goes into a shared build is the maintainer's decision.

## Result

All eight runs passed, 2026-11-01 10:48–11:48, on the top session's GO, in order and with no retry. The private binary is
md5 bf927e14, linked from shared normal 78f25172. Boot d9cca008 throughout, kernel 7.2.9-ogc3.1. In every arm: swappiness
150, page-cluster 0, and `VGT_HS_OFFCHIP_PARAM` latched at 0x1ff since exp 0392's T1 (the top session's statement, not
read here; `raw/*-box-settings.txt`). There was no amdgpu line in any kernel stream, no devcoredump, no TIMEOUT line and
no crash. Environment and journal proved each arm.

### Cost per frame

Window 200–400 s of journal time, ms per frame on the game thread (`raw/ana.txt`; `python -I ana0393.py <frames> raw`).
"Outside" is the flip interval minus the host time and the flip: the guest's own work plus anything the host does there
without a timer.

| Run | Flips/s | Flip interval | GPU busy | Inside the host | At the flip | Outside | Label waits | Prepare | cs |
|---|---|---|---|---|---|---|---|---|---|
| O1 | 38.66 | 25.86 | 19.55 | 10.20 | 5.73 | 9.94 | 5.43 | 2.70 | 1.24 |
| O2 | 39.01 | 25.64 | 19.53 | 9.98 | 5.72 | 9.93 | 5.18 | 2.73 | 1.24 |
| O3 | 39.04 | 25.62 | 19.56 | 9.94 | 5.69 | 9.99 | 5.18 | 2.73 | 1.19 |
| L1 | 37.83 | 26.43 | 19.54 | 9.92 | 5.52 | 10.99 | 4.80 | 2.86 | 1.38 |
| L2 | 37.78 | 26.46 | 19.80 | 9.95 | 5.57 | 10.95 | 4.86 | 2.86 | 1.35 |
| L3 | 38.55 | 25.94 | 19.50 | 9.68 | 5.45 | 10.82 | 4.71 | 2.79 | 1.37 |
| T1 | 37.32 | 26.79 | 20.16 | 10.01 | 5.55 | 11.24 | 4.85 | 2.88 | 1.37 |
| T2 | 36.88 | 27.12 | 20.28 | 10.24 | 5.53 | 11.35 | 5.04 | 2.98 | 1.33 |

| Mean difference from off | Flip interval | GPU busy | Inside the host | At the flip | Outside | Label waits | Prepare | cs |
|---|---|---|---|---|---|---|---|---|
| Spread of the off runs | 0.25 | 0.03 | 0.26 | 0.04 | 0.06 | 0.25 | 0.03 | 0.05 |
| Level 1 | **+0.57** (+2.2 %) | +0.07 | −0.19, not resolved | −0.20 | **+0.97** | −0.47 | +0.12 | +0.14 |
| Level 2 | **+1.25** (+4.9 %) | +0.68 | +0.08, not resolved | −0.18 | **+1.34** | −0.32 | +0.21 | +0.12 |

- **The cost is resolved at both levels.** Off averages 25.71 ms, level 1 26.28 ms, level 2 26.96 ms, about 38.9, 38.1 and
  37.1 flips/s. Each level run minus the off run before it gives +0.57, +0.82, +0.32 ms (level 1) and +0.93, +1.48 ms
  (level 2). The slowest off run (25.86) and the fastest level 1 run (25.94) nearly touch, so the size at level 1 is known
  only roughly. Three runs against three, and two for level 2. L3 sits closest to off; nothing in its files says why.
- **Most of it lands outside the host, not on the GPU.** At level 1 GPU busy moves +0.07 ms, about 1,320 breadcrumbs a
  frame at 50,000 a second. At level 2 it moves +0.68 ms; level 2 differs only by the COPY_DATA of the indirect counts,
  so those take about 0.6 ms. The interval's growth is in "outside", +0.97 and +1.34 ms, partly paid back by shorter label
  waits.
- **Why "outside" grows is not shown.** The frame profile times only the game thread, and the ring thread carries about
  26 of the ~33 jobs of a frame, so most of the rebuild's host time is in no column here. One candidate is that those
  jobs reach the GPU later and the guest waits longer in its own code. That was not measured.
- **Long frames.** Frames over 40 ms in the window: off 349–368, level 1 374–423, level 2 428–441 of about 7,600.
- **Whole-run means do not see it.** The summary lines give 29.3 ms between flips for both O1 and L1, because the load is
  in the mean. The window was needed.
- **Only comparable inside this series.** Exp 0378 had ~40.8 flips/s on this route with another build and other box
  settings; off here is ~38.9. The first 10-s bin of the plateau (160 s) is low in every run and is outside the window.
- **The pad was not observed.** The top session said the maintainer was away for about 40 min from the GO, so the last
  runs (T2, O3, L3, from about 11:26) may have had him nearby. O3 matches O2 within 0.02 ms, so the numbers show no sign of
  input, but that is not proof.

### Behaviour

- **Every sample reached and done.** All 42 health lines of each of the five breadcrumb runs read 4096 of 4096 reached and
  done, over about 21 million breadcrumbs a run, with RT on, one ring and today's frames (`raw/*-bc.txt`).
- **No COND_EXEC overflow line** in any run.
- **IB split.** It held at both levels: 1–2 jobs a run were cut (none in T1), with 0 fallback cuts and 0 refused. The
  largest was 1,671,120 dwords at level 2 from the title's 641,508 (`raw/T2-0341.txt`). O1's largest cut job was 1,225,448.
- **Memory.** Mean available memory in the window was 601 MiB off (590–623), 523 MiB at level 1 and 553 MiB at level 2.
  That fits the 64 MiB the slots and the host table take, within the spread (`raw/*-mem.txt`).

## Verdict

**Exp 0277's instruction is now fulfilled: level 1 costs about 0.6 ms a frame (+2.2 %) and level 2 about 1.25 ms
(+4.9 %) on the S6N route with RT on.** Breadcrumbs behaved at both levels on today's setup through five runs of 7 min,
with every sample reached and done and no kernel line.

By the reading rule written before the runs, **neither level is "cheap enough"**. Level 1 meets the first test (GPU busy
plus the resolved host parts come to 0.33 ms, under 0.51 ms) and fails the second, because its flip-interval change is
resolved. Level 2 fails both (1.01 ms). So breadcrumbs stay off by default. Level 1 is the level to use when a hang is
being chased, knowing the run is about 2 % slower; level 2 only when the indirect counts themselves are the question.
Patch 0001 stays as it is; anything for a shared build is the maintainer's decision.

Open: where the ~1 ms outside the host goes, since the ring thread is not timed.
