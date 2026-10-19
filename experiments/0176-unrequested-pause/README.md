# 0176 — ASTRO BOT "hung" twice after ~16 minutes: an unrequested pause of the window

**Question.** The maintainer, 19:55: "something froze my game — you?" (ASTRO BOT, started 19:38 from
the window menu with the chains shortcut). The 19:01 session had ended the same way.

**Setup.** The box's process list and kernel log for 19:38–19:55; the session's host log
(`play-last.log`) and journal; the pad recording (`route-record.txt`); the desktop's idle settings
(`powerdevilrc`, `kscreenlockerrc`, the `bc5-keep-awake` inhibitor); `input-remapper`'s presets; the
window code's pause sources (`window.cpp`).

**Result.**
- Nothing else ran on the box during the session (no route run, no watcher, no sampler); the kernel
  logged no GPU error after 19:37:51 (the end of another session's run 835).
- Both sessions ran smoothly to the end (19:38: 45,992 frames, 16:16 min; 19:01: 38,175 frames,
  15:37 min) and stopped at a pause: 19:38's host log has `window: paused at 976.509 s`, `resumed at
  976.509 s`, `paused at 976.549 s` — pause, resume, pause within 40 ms — and the journal's last
  frame at the same moment (journal and process clocks differ by ~0.4 s).
- The window pauses on the Space key (including its autorepeat), on *Emulation > Pause*, and on
  SDL's application background event (resumed on the foreground event). The pause–resume–pause
  burst matches the background/foreground events or a held Space. The desktop's idle dimming,
  turning off and locking are disabled and the inhibitor is active; `input-remapper` has no
  presets; Steam is not running. The window's own log (LOGF) is silent for ASTRO BOT, so the event
  that came is not recorded.
- Changes (`window.cpp`): SDL's background/foreground events no longer pause or resume the window
  unless `KYTY_BC5_PAUSE_ON_BACKGROUND=1` (they are logged as ignored); Space toggles the pause only
  on a press, not on its repeats; every pause and resume now logs its cause ("Space key", "menu or
  script", "application background event") to the host log whatever the logging switch. Checked
  with a scripted pause/resume on the second title (20:00).

**Verdict.** The "hangs" were the window pausing itself, most likely on a burst of SDL background
events on the desktop; the window no longer pauses on those, and the next unwanted pause will name
its cause (F233). The paused banner of F231 makes any pause visible.
