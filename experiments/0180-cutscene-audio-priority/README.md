# 0180 — Sound in the second title's opening cutscene: the console's blocking output instead of dropping, and the title's thread priorities

**Question.** The maintainer, 2026-10-20 morning, after playing the opening on the lean build:
"in all videos and in-game cutscenes the sound must always run at its natural speed, and the
picture should adapt to the sound", "even on the lean version the sound sped up and slowed down",
"especially in the second part of the in-game cutscene". In an early version only the sound and
subtitles played, with no picture, and the sound was natural then. Where does the sound depart
from real time, and what would the console do?

**Setup.**
- The second title's opening after New Game, by script (`opening-run.sh`, here): start screen →
  slot list → the empty slot 3 → challenge level. The saves are put back to
  `~/bc5-work/save-backup-0180-0953` before and after every run, and checked with `diff -r`.
  Normal build, 330 s, with the frame counter and the audio trace (`KYTY_BC5_AUDIO_TRACE`, once a
  second per port: the title's push rate, the time its audio thread was held, the host's queue
  clears, the SDL queue level).
- The cutscene runs from t ≈ 150 s: the daytime forest, then from t ≈ 195 s the night jungle with
  the L2/R2 prompts, the maintainer's "second part". It ends at the "Leap Attack" prompt (t ≈ 300 s).
- `audio-thread-sampler.py` (here): every 10 ms between two process times, each sound-path
  thread's state, wchan, run-queue delay and CPU time from `/proc`. `ats-summary.py` summarises it.
- `KYTY_BC5_THREAD_TRACE=1` (new) prints each guest thread's priority. `pw-top -b` and `pw-dump`
  give PipeWire's per-node error counts and the stream's latency attributes.
- Code (`backend/kytyplus-patches/0001-bc5-lle-agc.patch`):
  - `pthread.cpp`: guest priorities applied on Linux. Up to 299 → nice −15; 733 and above → nice
    +5; the rest 0. This goes through `SDL_LinuxSetThreadPriority`, which falls back to
    RealtimeKit1. `KYTY_BC5_GUEST_PRIORITY=0` turns it off.
  - `audio.cpp`: SDL's `PulseMainloop` thread gets nice −15 (`KYTY_BC5_AUDIO_PRIORITY=0` turns it
    off). The output hold drops the queue only after `KYTY_BC5_AUDIO_HOLD_MS` (default 1000)
    without progress, instead of after 100 ms.

**Result.**
- **The title paces its sound as on the console.** Its audio output thread (`AK::AudioOutThread`)
  spends ~1000 ms of every second held in the host's output call, waiting for the device. Its push
  rate is 1.000 in nearly every second, also when the picture runs at 6–15 flips/s. The host's hold
  is the console's blocking `sceAudioOutOutput`.
- **The glitches are short consumer stalls at the scene loads, then a drop.** In about half the
  runs, at t ≈ 168–175 or 230–238 s (the night part), the device side took 0.69–0.96 s of sound in
  one second. The host's hold then waited over 100 ms and cleared the queue, dropping ~42 ms of
  sound already counted as played by the title's audio clock: an audible jump. At the same moments
  the game thread spent 230–571 ms in the direct path's lazy mapping sync. The host's APR workers
  were blocked on page reads (`folio_wait_bit_common`) while the title streamed the next scene.
- **Not CPU starvation.** In a glitch window (run S3, t 230–236) no sound thread waited more than
  3 ms for a CPU in any 10-ms sample, and none was in D state.
- **Not a PipeWire underrun.** PipeWire counted 0 errors on the stream and on the output device
  (a USB headset) in a run that glitched.
- **The graph runs at a 256-frame quantum.** SDL asks for the title's 256 frames, and
  `pipewire-pulse` derives the stream's request size as a third of its buffer. Asking for 1024
  frames still gave a 256-frame request (`pulse.attr.minreq` 8192 bytes for 8 × f32) and still
  glitched. That change is withdrawn.
- **The title's thread priorities** (`raw/thread-priorities-pr1.txt`): 256 for the audio output and
  decode threads, 300 for main and render, 450 for the physics solvers and the audio mixer, 500 for
  `Job Hi`, 600 for `Job Lo`, 750 for `Job Bk`. The host ignored them on Linux; only its Windows
  build mapped them. With the top band raised and `PulseMainloop` at −15, 2 of 7 runs glitched (8
  bad seconds); without, 2 of 3 (7 bad seconds). Too few runs to call it, but the frame rate is
  unchanged (37–39 flips/s on t 150–300 in all variants), and the console runs those threads above
  the workers too.
- **The hold of 1 s removes the jumps** (`raw/runs-summary.txt`):

  | output hold | runs | runs with a slow second | slow seconds | queue clears (jumps) |
  |---|---|---|---|---|
  | drop after 100 ms (before) | 12 | 5 | 19 | 9 |
  | drop after 1000 ms (now) | 7 (H1–H7) | 2 | 2 (0.93, 0.96) | 0 |

  The two slow seconds left are short stalls of the sound server's side, held. The title's audio
  clock waited and nothing was skipped. The frame rate on t 150–300 was 37.9–41.0 flips/s against
  36.0–39.1 before. ASTRO BOT (`astro-check.sh`, 100 s from its start): 0 slow seconds, 0 clears,
  57.2 flips/s.
- **A recording for the maintainer** (`record-run.sh`): the default output's monitor through
  `pw-record` (the mix the headset gets), on the lean build. It runs from the second title's start
  through the opening and into walking. It was sent in the chat and not committed (game audio).

**Verdict.** The sound of the second title's cutscenes no longer jumps. The host held the title's
audio thread like the console's blocking output, but dropped its queue after 100 ms. That turned
short stalls of the sound server's side, at the scene loads, into skips of sound the title had
already counted as played (F238). It now holds up to 1 s, so the cutscene's picture, which follows
the title's audio clock, waits with the sound. The stalls themselves are rarer but still occur
(2 short ones in 7 runs). TODO(verify) their origin between SDL's PulseAudio client,
`pipewire-pulse` and the device: PipeWire counts no error, and no thread of ours is starved or
blocked. SDL's native PipeWire backend would remove `pipewire-pulse` from the path; it needs
`libpipewire-0.3-dev` in the build container. The title's thread priorities are now applied on
Linux, the top band only; that is console-faithful, and no measurable effect on frames or sound
was found. The picture's own stalls in the night part (8–14 s per run with a frame gap over
150 ms, the direct path's lazy mapping sync during the scene loads) remain, a separate matter.
