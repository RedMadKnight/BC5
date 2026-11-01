# 0393 — What the dispatch breadcrumbs cost per frame, on the same route

**Date.** Planned 2026-11-01. **Box.** Not yet run; this README is the plan until the Result section is filled in.
**Asked by.** The maintainer's yes of 2026-11-01 to the same-route cost test.

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

Not run yet.

## Verdict

Not run yet.
