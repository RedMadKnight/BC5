# 0168 — Audio pacing with the submission chains across ioctls (`BC5_DIRECT_CHAIN=2`)

**Question.** The maintainer's pad test of `BC5_DIRECT_CHAIN=2` (2026-10-19, ~11:15, the "BC5
emulator (chains)" desktop entry): "with chains the sound chases the picture and is distorted (sped
up at moments); the picture also has freezes and sudden catch-ups"; without chains the sound runs
naturally. Does the audio thread's push rate (`KYTY_BC5_AUDIO_TRACE=1`: frames pushed per second of
wall time, the time held on the SDL queue, forced clears) change with `=2` on the 200 s gameplay
route of experiment 0165?

**Setup.**
- Box and route as experiment 0165 (`input799.cmd`: start screen, slot 1, Continue; night-scene
  gameplay from about +153 s; `play-pkg-log.sh` settings; `drive0163.sh`; 200 s). Both runs with
  `KYTY_BC5_AUDIO_TRACE=1 KYTY_BC5_VIDEOOUT_TRACE=1`.
- Run 811: chains off, the binary of 10:58 (origin/main ff45ba2's host: experiment 0166's pause
  fix, on the union with experiment 0165's chain code).
- Run 0165a: `BC5_DIRECT_CHAIN=2`, the binary of 11:50 (the same plus experiment 0167's stall
  watchdog, built by that session; `chains: mode 2` in its journal, 218,934 chains in 200 s). Named
  outside the run-number series because run 810, meant to be this run, was overwritten by
  experiment 0167's `run810.sh` before it started and ran with chains off (its trace matches 811).
- `audio.py` (in `experiments/0165-chains-cross-ioctl/`): per port, the rate's mean/min/max, the
  seconds outside 0.97–1.03, the held time, the clears, the SDL queue depth, over a window.

**Result.**
- **The push rate does not change with the chains.** Port 0 (the main 8-channel 48 kHz port),
  gameplay t 155–200 s: run 811 rate mean 1.000, min 1.000, max 1.001, held 1000 ms a second, 0
  clears, SDL queue 42 ms; run 0165a rate mean 1.000, min 0.999, max 1.001, held 1000 ms, 0 clears,
  42 ms. Over t 20–200 s the only seconds outside 0.97–1.03 are the save load (t 40–55 s: the rate
  drops to 0.001 for one second and recovers over ~8 s in both runs, 0.6–0.96; one second at 1.039
  in 0165a right after it). Port 2 (the second port) likewise 1.000 in both.
- **Frame rate.** Run 811 (off): 21.4 flips/s mean, median 23.8, min 1.8, max 31.7, `Render Thread`
  91 %. Run 0165a (`=2`): 30.8 mean, median 33.5, min 11.2, max 41.5, `Render Thread` 80 %, 1,106
  kernel submissions a second. Both below experiment 0165's 33 / 45 of the morning (803 / 805, the
  09:55 binary, a freshly booted box; the box had since run the maintainer's session and the
  0166/0167 runs, and the 11:50 binary carries 0167's watchdog). The picture's stalls are in both
  runs (the minimum flips of a second: 1.8 off, 11.2 on), as the top session reports for its own
  runs without chains (experiments 0166/0167).
- Kernel log: the F208 fault bursts in both (9 `page fault` lines in the last 40), no reset, no
  timeout; no failed submission.
- Raw: `raw/trace-{811,0165a}-sampled.txt` (every 5th audio and VideoOut trace line),
  `cpu-*.txt`, `kernel-*-after.txt`, `drive*.log`, `journal-0165a-excerpt.txt`.

**Verdict.** Not reproduced: on the scripted route the audio thread pushes at the DAC's rate with
`=2` exactly as without (F211's measurement repeated with the chains on), with the thread held on
the SDL queue the whole second and no forced clear; the chains do not change the audio pacing the
trace can see at one-second resolution. What the maintainer heard is therefore not a sustained rate
change; it is either inside the picture's stalls (present in both runs, and the subject of
experiments 0166/0167), or in the input the route does not exercise (the pad, the menus, the
maintainer's path through the scene), or shorter than a second (a burst the per-second trace
averages out). Next: the audio PCM dump of experiment 0166 and `KYTY_BC5_AUDIO_TRACE=1` during the
maintainer's own play with the chains on, from the desktop entry, with the stall watchdog of 0167
to tie a distortion to a stall. The knob stays off by default (experiment 0165's standing).
