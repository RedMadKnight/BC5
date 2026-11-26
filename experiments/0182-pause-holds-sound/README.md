# 0182 — A pause stops the title's sound too; chains by default for the second title; the remaining roughness is in the title's own sound

**Question.** The maintainer, 2026-10-20 afternoon, after the recording of exp 0181 and a session
with the chains shortcut:
- "on this recording it sounds bad";
- "I played the version with chains now and it is much better";
- "desync and the delays/speed-ups start only after a while, not straight away";
- "pausing the game and resuming causes terrible lags of picture and sound after unpausing".

**Setup.**
- **Code.** `KernelClocksPaused()` is added next to the window's pause clocks of exp 0166
  (`pthread.cpp`/`.h`). `QueueSdlAudio` (`audio.cpp`) waits while the window is paused, with its SDL
  device paused, and resumes both at Resume. The controller's ports are written by the same thread
  after the main one and are not held themselves.
- **`pause-run.sh`** (here): the opening of exp 0180, paused by the input script at t ≈ 225 s (the
  night part) for 15 s of wall time, then resumed. Normal build, audio trace.
- **The maintainer's chains session** (14:47–14:54, normal build with `BC5_DIRECT_CHAIN=2`, 410 s):
  its direct-path journal (`~/bc5-data/captures/play-20261020-1447`). Its stderr log was overwritten
  by a later run.
- **`clicks.py`** (here): discontinuities per second (second difference far above its local level)
  in the title's own sound (the dump of exp 0181, run c4) and in the two lossless recordings
  (c4: normal build; f1: lean build, the one sent to the maintainer), over the same 60 s of the
  opening.
- **Launcher** (`play-pkg.sh`, here): `BC5_DIRECT_CHAIN=${BC5_DIRECT_CHAIN:-2}` for the second title.

**Result.**
- **Before the fix the title's sound did not pause.** Exp 0166 stops the title's clocks during a
  pause, but its audio thread is paced by the device, which kept asking. The title's audio engine
  kept mixing, and its audio clock (which the cutscenes' picture follows) ran ahead by the length of
  the pause. After Resume the picture raced to catch up.
- **With the fix** (run opPause1): `window: paused at 225.558 s` and `resumed at 225.558 s` (process
  time stands still during the pause). The audio second spanning the 15-s pause carried 1.024 s of
  sound (96 calls), not ~16 s. No slow second, no clear on t 150–300.
- **The chains session**: 48–52 flips/s up to t ≈ 190 s, 30–40 after (night part and gameplay). Its
  three longest frames (1.1 s at t 319, 3.75 s at t 372, 0.6 s at t 384) were spent 97–99 % outside
  the host with only 9–11 GPU jobs, the shape of a pause in a wall-clock journal. The maintainer
  reports pausing in that session, so "after a while" matches "after the first pause".
- **The clicks are in the title's own sound.** Over the same 60 s, the dump has 415 and the
  recordings 457 (lean) and 549 (normal), and the worst seconds coincide (the dump's 55–56 s = the
  recordings' 205–208 s). The output path adds at most a few; how many of them are real transients
  of the scene (claws, gunfire, fire) is not known.
- The submission chains raise the second title's frame rate (F224). The title runs its audio logic
  per game frame, so more frames give smoother sound. The lean shortcut ran without them.
- **The lean build with chains, and the pause test with chains:** see `raw/runs-summary.txt`.

**Verdict.**
- A pause now holds the title's sound with its clocks, as the console stops the whole title
  (F240).
- The submission chains are the second title's default in both builds.
- The roughness heard in the recording is made inside the emulated title's audio before the host
  hands it on. TODO(verify) where: the AJM decoders (ATRAC9, Opus), the title's audio engine at low
  frame rates, or both. The maintainer's description (what sounds bad, and when in the recording)
  decides the next experiment.
