# 0166 — "Sped-up sound, picture frozen then racing": the window's pause left the title's clocks running; now they stop with it

**Question.** The maintainer, after trying the new emulator window (2026-10-19 10:20): "the sound,
when there is any, is strongly sped up; the picture either races or nothing happens, then it
catches up very fast; the menu works". Yesterday's report of speed changes (exp 0162) was a
different, milder thing. Where does the fast sound come from?

**Setup.**
- The maintainer's session (host log `play-pkg-last.log` of 10:20, the direct journal
  `play-20261019-1020`, the audio trace was on): the save loaded, then a 380 s gap without a
  flip (t 15 → 395 s), audio pushes stopping at t 34 s and 59 s, play from 395 s on.
- Run 806: the same route by script, audio trace: the push rate 1.000 throughout.
- Run 807: `KYTY_BC5_AUDIO_DUMP=<dir>` (new): the main port's PCM before and after the SDL
  conversion, 40 s of gameplay and 30 s of menu, converted to WAV (`raw2wav.py`) and sent to the
  maintainer: "the WAV sounds right". PipeWire's view of the stream (run 808, `pw-dump`,
  `pw-top`): F32LE 8 ch 48 kHz, quantum 256, no errors, onto the stereo USB headset sink.
- The pause (ADR 0011 §5, Space / Emulation > Pause) stops the present thread taking flips, so
  the title blocks on its next flip — but `KernelGetProcessTime`, `KernelReadTsc` and the
  monotonic `clock_gettime` clocks kept running (`pthread.cpp`), so on resume the title saw the
  whole pause as elapsed time.
- Fix: `KernelPauseClocks(bool)` in `pthread.cpp`, called from the window's `SetPause`: the
  ticks of every pause are taken off the process time, the process-time counter, `KernelReadTsc`
  and the monotonic/uptime clock ids (the realtime clocks and the CPU-time clocks go on), as the
  console's suspend does for a suspended process (TODO(verify): the console's exact clock
  semantics across suspend; shadPS4 and KytyPlus both derive process time from a TSC epoch).
  Scripted test support: `pause` / `resume` lines in `KYTY_BC5_INPUT_CMD`.
- Run 809: gameplay from the save, `pause` at +145 s (process time 145.323 s), `resume` 45 s
  later, 100 s more of play; audio and VideoOut traces.

**Result.**
- The maintainer's session: 380 s without flips while the audio thread first went on (menu
  music at rate 1.000 to t 34 s, the loaded scene's port from 45 to 59 s) and then stopped;
  after the resume at t 395 s the frames ran at 33 ms and the audio trace printed nothing more
  (`play-pkg-last.log`). The sped-up sound is the title's catch-up for the pause it never knew
  about; the host's audio output itself is right (806–808).
- Run 809 with the fix: the window reported "paused at 145.323 s" and "resumed at 145.323 s" —
  the process time did not move during the 45 s; no audio push and no flip during the pause;
  the first second after resume: 94 pushes (a normal second, not 45 s' worth), rate 1.000 from
  then on, 41–45 flips/s before and after (`run809-stderr.log` excerpts here).

**Verdict.** The "strongly sped up sound and racing picture" of the window test was the pause:
the title's clocks ran through it and the title caught up on resume. The clocks now stop with the
pause (F219). The milder speed changes of exp 0162 (variable 30–42 fps) are unchanged by this.
