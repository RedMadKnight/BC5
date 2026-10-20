# 0184 — 30 frames a second by default for the second title; the "loop" is the title's silent clock voice

**Question.** The maintainer, 2026-10-20 evening: "Yes, turn on the 30-frame cap for the second game
on both shortcuts, and keep looking for the cause in the night scenes" (exp 0183, F241).

**Setup.**
- **Launcher** (`play-pkg.sh`, here):
  `export KYTY_BC5_MIN_FLIP_RATE=${KYTY_BC5_MIN_FLIP_RATE:-1}`, so at most 30 flips a second for the
  second title on both shortcuts; `KYTY_BC5_MIN_FLIP_RATE=0` lifts it.
- **Video trace** (`videoOut.cpp`, `KYTY_BC5_VIDEOOUT_TRACE`): the per-second line now also gives
  how far the vblank and flip counters the title last read advanced, and over how much of their own
  process time.
- **Runs:**
  - g2: slot 1's night gameplay, capped, with the AJM dump and the video trace;
  - c7: the opening, capped, AJM dump, video trace and the direct-path frame profile.
- **`same_loop.py`** (here): whether two AJM loop streams are the same recording.

**Result.**
- **Night gameplay, capped (g2):** the 10-s loop plays at 0.94–1.00×, against 1.30–1.65× in the
  same scene uncapped (g1, exp 0183). That is flips/s ÷ 30, at 28–29 flips/s. The vblank counter
  the title reads advances 60 a second of process time, and the flip counter 28–29.
- **The menu loop (0x60001), the cutscene loop (0x6000b) and the gameplay loop (0x60009) are one
  recording:** correlation 1.00, each against the other. It is practically silent: −61 dBFS rms,
  −57 dBFS peak, constant. So it is not a sound the maintainer hears but a quiet voice that plays all
  game long. Its playback speed shows how fast the title runs the clock its cutscenes follow
  (exp 0153: the cutscene's picture follows the play position of one Wwise voice). TODO(verify) that
  this is that voice.
- **The opening, capped:**
  - c6 (exp 0183): 1.00× in the daytime part;
  - c7: 1.06× and 0.74× around t 161–184 s;
  - both runs: 1.35–1.45× in the night part (t 184–248 s), while frames come every 32.8 ms (30 a
    second) and the GPU works ~25 ms a frame;
  - c7 also has 0.27–0.35× at t 248–314 s (the slow-motion prompts) and 2.5–3.5× in its first 15 s.
- **The GPU-time model of exp 0183 does not fit.** A per-frame step of max(1/30 s, GPU time) would
  give 1.0× in the night part (25 ms of GPU work a frame).

**Verdict.**
- With the 30-frame cap the second title's clock runs at real time in the daytime cutscene and in
  night gameplay (F242).
- In the night part of the opening it still runs ~1.4× (reproducible), next to slow-motion stretches
  at ~0.3×. Whether that is the cutscene's own time effects or another fault is open; the
  maintainer's ear on the capped build decides.
- The audible crackle is not this voice. It is the scenes' sounds advanced by a clock that ran fast.
