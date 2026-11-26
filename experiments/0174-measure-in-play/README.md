# 0174 — Measuring the maintainer's own play with logging off

**Question.** The maintainer, after playing the second title with and without the submission
chains (2026-10-19, 17:27 and 17:30): "in both versions the sound and the picture slow down and
speed up, so the chains are not responsible". Those sessions ran with the logging switch off
(*Emulation > Logging*), so only their first ~25 s of journal exist. What happens in the slow and
fast stretches of real play?

**Setup.**
- `KYTY_BC5_MEASURE=1` (new, `audio.cpp`): the audio push-rate line (`KYTY_BC5_AUDIO_TRACE`, exp
  0162) stays on with the logging switch off; the frame-time counter (`KYTY_BC5_FPS_COUNTER`, exp
  0172) ignores the switch anyway.
- Both pkg launchers on the box (`play-pkg.sh`, `play-pkg-log.sh`; backups `*.bak-0174`) export
  the two counters and `KYTY_BC5_MEASURE=1`, and start `cpu-sampler.sh` (exp 0162) writing
  `~/bc5-work/cpu-last.txt`: per second the CPU % of every emulator thread over 5 %, the load
  average and free memory. One line a second each.
- Check (17:43, the start screen with `BC5_LOGGING=0`): 71 frame-counter lines, 65 audio lines and
  the CPU file in 75 s.

**Result.** See experiment 0175: the 17:58 session's counters (23.4 frames a second, the audio at 75–94 % during the load, 1.000 in gameplay).
