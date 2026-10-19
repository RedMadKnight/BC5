# 0175 — The maintainer's slow-downs and speed-ups in real play; a GPU watcher that froze the GPU; a save that hangs on load; a paused window that looked hung

**Question.** The maintainer, evening of 2026-10-19: "with and without the chains the sound and
the picture slow down and speed up, and the game hangs" — "collect logs from several sessions, and
find when I first said the sound broke, after it had been the one thing that worked". Then
"ASTRO BOT hung".

**Setup.**
- The conversation transcripts (this session and the F208 session's), the maintainer's messages
  about sound, by time (local time, CEST).
- The maintainer's sessions 17:47–18:03 with the measurements of exp 0174 (frame counter, audio
  push rate, per-thread CPU) — only the last one (17:58) kept its logs; the launchers overwrite
  `play-pkg-last.log` and `cpu-last.txt` at each start.
- `vmstat-sampler.sh` (here): the kernel's memory-pressure counters once a second.
- Route runs 830 (walking added after the load, `INPUT=input-walk.cmd`), 831–833 (standing; 833
  with `BC5_DIRECT_CHAIN=2`); `startscreen.sh` (here) for 90-s start-screen A/Bs (journal on/off ×
  timeout probe on/off; the launchers now take `BC5_NO_TIMEOUT_PROBE=1`).
- The root GPU watcher of exp 0160 (`/usr/local/bin/bc5-gpu-hang-watch`, re-armed in a loop from
  14:18): it reads the fence info every 50 ms and, when the gfx ring's fence stalls for 0.6 s,
  dumps the waves with `umr -O halt_waves`.
- The ASTRO BOT session of 19:01–19:17 (host log, journal).

**Result.**
- **When the sound broke.** 10:30 "the sound is strongly sped up" — the window's pause (F219, fixed
  by 11:00). 11:39 "without chains the sound runs naturally". 13:07 (F208 session) "worse again —
  the sound speeds up and slows down". 13:28 "much better … but again delays/speed-ups of the
  sound". 15:01 "the delays/speed-ups are there all the time". 17:41 "with and without the chains".
  So the break falls between 11:39 and 13:07.
- **The 17:58 session** (243 s with counters): 23.4 frames a second on average, no second above 30;
  during the load (t 51–82 s) the title's audio thread pushed 75–94 % of real time (its SDL queue
  ran empty); in gameplay the audio rate was 1.000 and the frames 13–27 a second with gaps up to
  260 ms. In the route runs the audio rate follows the frame rate at the load (16 frames a second →
  68 %): the title's audio is produced in step with its frame loop when that loop is slow, so the
  sound slows down with the picture rather than on its own. (TODO(verify) the mechanism inside the
  title's audio engine.)
- **Memory** is not short in these runs: the per-second sampler of run 830 shows almost no direct
  reclaim or compaction stalls and no swapping during play; MemAvailable stays at ~1.1–1.4 GB. Over
  the box's 9 hours of runs the kernel had swapped ~40 GB through zram, mostly between sessions.
  Giving the title more than its 13.5 GB would only cut into that last gigabyte.
- **The watcher froze the GPU in play.** It dumped (halting the waves) 46 times today, including in
  the maintainer's sessions (17:53–17:54, 17:57, 17:58, 18:02, 18:03 — the picture stands for the
  dump, then the title catches up) and in my runs; in runs 830–831 every dump was followed about
  1 s later by a kernel ring timeout and reset (831: dumps 18:32:07, :22, :38, :54, 18:33:13, :29,
  :45; timeouts 18:32:08, :23, :39, :55, 18:33:14, :30, :46). The loop was stopped at 18:40; the F208
  session recorded the warning (exp 0160).
- **A save that hangs.** Slot 1's autosave was rewritten at 18:00–18:02 during the maintainer's
  session. Every route run that loads it hangs 6–20 s after the load, with chains or without, with
  the watcher stopped (832, 833): kernel gfx and compute ring timeouts with no page fault around
  the first one. Runs 815–828 loaded the older save and never hung. The save directory is backed
  up on the box (`save-backup-0175/`) and handed to the F208 session as a reproduction.
- **The start screen** runs at 25–26 frames a second in all four journal/probe variants (t 55–82 s);
  neither the journal nor the timeout probe changes it.
- **ASTRO BOT did not hang.** 16 minutes at 38–55 frames a second (18–30 ms, no frame over 100 ms in
  the last 8 minutes), then `window: paused at 937.748 s` and exit 24 s later: the window was paused
  (Space, or *Emulation > Pause* from the PS-button menu) and a paused window showed nothing but the
  frozen picture. It now shows a banner ("PAUSED — Space, or Emulation > Resume …",
  `paused-banner.jpg`): the overlay pass also runs while paused (`swapchain.cpp`,
  `settingsOverlay.cpp`), without taking input.

**Verdict.** The slow-downs the maintainer hears and sees are frame-rate drops of the title (the
audio follows its frame loop), worst at loads; the watcher's dumps added freezes of their own and
turned stalls into ring resets (stopped, F229). The hangs at the end of today's sessions belong to
the place the game reached (a reproducible hang on loading slot 1, F230, for F208's work). A paused
window now says it is paused (F231).
