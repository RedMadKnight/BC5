# 0183 — The second title's looped sounds play 1.3–2× too fast: per frame in the cutscene, by another mechanism in the night scenes

**Question.** The maintainer, 2026-10-20 evening:
- "the crackle is there almost all the time once it first appears";
- "sound and picture are both sped up almost equally; sometimes the sound runs ahead, then they
  line up, but it stays sped up";
- "A [the title's own sound, exp 0182] crackles and is sped up too".

So the fault is in the sound the emulated title makes, before the host's output path. Which sounds,
and why?

**Setup.**
- **`KYTY_BC5_AJM_DUMP=<dir>`** (new, `ajm.cpp`, diagnostic, absent from the lean build) writes what
  each AJM split-decode job hands the title, per decoder instance (`ajm-<inst>.raw`). It also writes
  an index with one line per job: process time, instance, bytes, frames, the decoder's sample count.
  The decoder's sample count restarts when a stream restarts.
- **`KYTY_BC5_MIN_FLIP_RATE=<0..2>`** (new, `videoOut.cpp`) is the least flip rate in force: 1 = a
  flip every second vblank, at most 30 frames a second with 60-Hz vblanks. Off by default.
- **Runs:**
  - opAjm: the opening with `KYTY_BC5_AJM_TRACE`;
  - opVo: the opening with `KYTY_BC5_VIDEOOUT_TRACE`;
  - c5: the opening with the AJM dump and the title's mix dump (t 150–300 s), uncapped;
  - c6: as c5 with `KYTY_BC5_MIN_FLIP_RATE=1`;
  - g1 (`gameplay-run.sh`): slot 1's night gameplay, uncapped, AJM dump.
- **Scripts:** `clicks_raw.py` (discontinuities in a decoded stream), `chunk_overlap.py` (whether a
  stream's restarts replay the same audio), `speed_factor.py` (time-compressed envelope against the
  mix; inconclusive here, the loops are quiet under the effects), `voice_speed.py`.

**Result.**
- **Codecs.** The title's sound is Opus at 48 kHz: mono instances (0x60001, 0x6000b, …) and 4-channel
  multistream (0x60002). Its sound effects get a new instance each. Every ATRAC9 instance is the
  controller's haptics (layout 7, decoded as silence). The decoders hand over exactly what they
  decode: 1.995 bytes per mono sample and 7.999 per 4-channel sample (s16).
- **The decoded streams are clean.** 0 discontinuities in 223 s of 0x6000b and in 139 s of 0x60001;
  0.1 a second in the 4-channel stream. The title's mix has ~7 a second (exp 0182).
- **The looped sounds play too fast.**
  - 0x60001 (menus) and 0x6000b (the cutscene) are each one 10-s sound on a loop: every restart
    replays the same audio (`chunk_overlap.py`: offset 0.00 s, correlation 1.00), 479,352 samples
    each.
  - Decoding inside a loop pass is spread evenly, so it follows playback.
  - Before the cutscene, 0x60001 restarts every 10.0 s (1.00×). In the cutscene, 0x6000b restarts
    every 4.8–6.8 s (1.5–2.1×).
- **In the cutscene's daytime part, the speed is the frame rate divided by 30** (c5):

  | t, s | loop speed | flips/s | speed × 30 / flips/s |
  |---|---|---|---|
  | 151.8–158.3 | 1.54 | 45.4 | 1.02 |
  | 170.9–177.0 | 1.63 | 49.0 | 1.00 |
  | 182.9–188.7 | 1.74 | 51.1 | 1.02 |
  | 200.2–205.9 | 1.75 | 50.5 | 1.04 |

  The title advances these sounds, and the cutscene with them, by a fixed 1/30 s per presented
  frame. At ~48 flips/s the cutscene ran ~1.6 times too fast.
- **Capped at 30 frames a second** (c6), 0x6000b plays at 1.00× for the first 30 s of the
  cutscene. The cutscene lasts longer: the loop played to 310.6 s against 275.9 s.
- **A second mechanism.**
  - From t ≈ 176 s in c6 (the night part), the loop runs at 1.35–1.84× at 24–37 flips/s.
  - In slot 1's night gameplay (g1), a looped sound runs at 1.30–1.65× at a steady 28–29 flips/s,
    rising steadily over two minutes (1.30 at 126 s, 1.65 at 236 s).
  - This matches "after a while".
- **The game's pacing.** It sets the flip rate once (`VideoOutSetFlipRate(1, 0)`, every vblank),
  registers only a flip event, flips in mode 1, and reads the vblank and flip status once a frame.
  No call it makes asks the host for 30 frames a second.

**Verdict.** The crackle and the speed-up are the title's own looped sounds and cutscene running too
fast (F241). In the daytime cutscene the cause is frame rate: the title steps 1/30 s per frame,
and a 30-fps cap restores 1.00×. A second cause makes the night scenes' sounds run 1.3–1.8× fast at
~30 frames a second, rising over time. TODO(verify): what drives it (the title's time measurement,
its audio sync, or a Wwise parameter fed from timing). How the console holds such a cutscene to
30 is not established either.
