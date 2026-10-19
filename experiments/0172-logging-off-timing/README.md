# 0172 — The second title with all logging off, timing only: 43.5 frames a second without chains, 49.4 with them

**Question.** The maintainer: "run chains and no chains once more with logging switched off — only
measure the times". What do the frame rates look like without the direct journal and with the
session's logging switch off (ADR 0011 §6, `BC5_LOGGING=0`)?

**Setup.**
- `KYTY_BC5_FPS_COUNTER=1` (new, `videoOut.cpp`): a measurement that ignores the logging switch —
  once a second one stderr line with the flips submitted, the longest interval between two flips
  and how many intervals were over 40 and 70 ms. The other traces (audio, VideoOut) obey the
  switch and print nothing with it off.
- `play-pkg-quiet.sh` (box, regenerated from `play-pkg-log.sh`): the same settings, but no
  `BC5_DIRECT_TIMING`/`BC5_DIRECT_FRAME_PROFILE` and `BC5_LOGGING=0` — no journal, no guest printf,
  no host traces.
- `route.sh` (here) takes `LAUNCHER=play-pkg-quiet.sh`; `fpscmp.sh` (here) reads the counter's
  lines for the gameplay window t 130–230 s.
- Runs 825 (no chains) and 826 (`BC5_DIRECT_CHAIN=2`), the 17:01 binary (F221–F225), the
  scripted gameplay route of exp 0169. The capture directories stay empty (no journal).

**Result.**

| | 825, no chains | 826, chains | (822 / 821 with the journal, exp 0170) |
|---|---|---|---|
| flips per second, mean | 43.5 | 49.4 | 40.9 / 49.2 |
| slowest / fastest second | 30.6 / 48.7 | 42.0 / 53.5 | |
| frames in 100 s | 4,313 | 4,942 | |
| intervals over 40 ms | 69 | 31 | |
| intervals over 70 ms | 5 | 3 | 6 / 5 |
| longest interval | 328.5 ms | 134.4 ms | |

**Verdict.** With logging off the second title runs at 43.5 frames a second without the chains
(2.6 more than with the journal) and 49.4 with them (the journal cost nothing measurable there). The
chains are worth 6 frames a second and halve the frames over 40 ms; neither run had a GPU timeout
(F227).
