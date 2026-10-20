# 0185 — The longer the second title runs, the faster its clock: a sawtooth in the night scenes, calm only at a steady frame rate

**Question.** The maintainer, 2026-10-20 evening, after playing with the 30-fps cap of exp 0184:
"the longer I played, the more picture and sound sped up together". What accumulates?

**Setup.**
- The second title's silent clock voice (exp 0184, F242), as a measure of how fast the title runs
  its clock. It is a 10-s recording looped all game long; its decoding (`KYTY_BC5_AJM_DUMP`) is
  spread evenly through each pass, so passes per second = playback speed. Every pass counted is
  complete (479,352 samples).
- **`long-run.sh`** (here): slot 1's night gameplay for 13 minutes, normal build, 30-fps cap.
  `long-cmd.txt` drives it: the first prompts, then 45 rounds of attacks, a parry and walking. The
  saves are restored around the run.
- **`idle-run.sh`** (here): the same scene, no input after loading (the game waits at its first
  prompt).
- **Runs:**

  | run | script | cap | timestamp scale | length |
  |---|---|---|---|---|
  | L1 | long-run | 30 fps | 1.00 | 13 min |
  | L2 | idle-run | 30 fps | 1.00 | 13 min |
  | L3 | idle-run | 20 fps (`KYTY_BC5_MIN_FLIP_RATE=2`) | 1.00 | 7 min |
  | L4 | idle-run | 30 fps | 0.70 (`RenderScale.PPSA03671`, the file restored after) | 7 min |

- Raw: `raw/long-runs.txt` (every pass with its speed, flips per minute, L1's decoder load per
  minute).

**Result.**
- **Menus: 1.00× in every run, at any frame rate.**
- **The host's clocks stay exact.** The vblank counter the title reads advances 60.00 a second
  (L1, every minute), and the title's audio is pushed at 1.000 with the output thread held ~999 ms a
  second and no clears for all 13 minutes. The TSC, process time and process-time counter all come
  from one measured TSC frequency (`pthread.cpp`), so they cannot drift apart.
- **L1 (fighting):** the clock voice runs 1.0× in the first minute, 1.38–1.52× at minutes 1–8, and
  2.5–2.9× at minutes 9–13, at 24–30 flips/s. The decoder load explodes with the scripted
  fighting: up to 3,010 decoder instances and 365,000 decode jobs a minute.
- **L2 (idle) shows the same without any fighting, as a sawtooth.**
  - After loading: 1.3×, rising slowly to 1.8×.
  - Then a jump to 2.6×, rising to 2.86×.
  - Then 0.2× for about 140 s, then 1.3× again.
  - Period about 6 minutes, at a steady 27–28 flips/s (but with frames alternating between two and
    three vblanks).
- **L3 (20 fps, every frame three vblanks):** a constant 0.85× for five minutes, no rise, no
  sawtooth.
- **L4 (timestamps × 0.7):** 1.00× for the first 80 s after loading, then the same rise (1.28–1.69×)
  and jump (2.5–2.66×). The title chose a higher resolution, so 24 flips/s.

**Verdict.** The title's clock drifts in the night scenes whenever frame times vary (two or three
vblanks a frame). It rises over minutes, jumps, collapses and repeats. At a constant frame time it
is calm (0.85× at 20 fps). The host's clocks do not drift, so the drift is computed by the title
from what it reads (F243).
- **Ruled out:** GPU timestamps (no proportional change at 0.7), fighting load (also idle), the
  vblank and flip counters (exact), the pause (none in these runs).
- **TODO(verify):** which of the title's inputs the clock follows: flip status times, frame pacing
  through flip events, or audio-output state calls. The next step is to sample the title's audio
  threads' stacks (gdb) during a rise, and to count the host calls they make.
