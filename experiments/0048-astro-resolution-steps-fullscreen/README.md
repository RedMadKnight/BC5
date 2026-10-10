# 0048 — ASTRO BOT's four resolution steps, presets with the usual names, and fullscreen

**Question.** The maintainer asked for the usual resolutions in the F2 menu instead of the title's
odd sizes, and for a fullscreen mode without a window at the display's current resolution. Does
the title have steps between the four seen so far, and does fullscreen work while it runs?

**Setup.** As in 0047. Runs 174–176 with `BC5_DIRECT_TS_SCALE` 1.3, 1.4 and 2.5 (the main 3D
view's sizes from 240 s, `steps.awk` logic as in 0047; 420 s each). New in the host (patch 0001):

- `WindowSetFullscreen` / `WindowIsFullscreen` (`window.cpp`, `window.h`): borderless desktop
  fullscreen (`SDL_WINDOW_FULLSCREEN_DESKTOP`, the display's own resolution). Another thread
  leaves a request and wakes the event loop with an `SDL_USEREVENT`; the main thread applies it
  (`ProcessEvent`). F11 toggles it.
- `Fullscreen=on|off` in the input configuration, applied at start (before the window exists it
  becomes the window's flags) and on Apply/Save; written back by Save.
- The F2 menu's *Video* tab: a fullscreen box, and the four presets named after the usual
  resolution each step is nearest to, with what the title draws.

Run 177: 70 s with `Fullscreen=on` and `RenderScale=1.25` in the input file and the menu open.
2026-10-10 22:00–22:55. Raw output in `raw/`.

**Result.**

1. **The title has exactly four steps** (runs 166–176):

   | Timestamp scale | Main 3D view | GPU busy (380–418 s) |
   |---|---|---|
   | 1.0 | 3840×2160 | 17.0 ms |
   | 1.2, 1.3 | 3328×1872 | 15.1, 14.5 ms |
   | 1.4 | 3328×1872 and 2432×1368 alternating | 14.5 ms |
   | 1.5, 2.0 | 2432×1368 | 11.7, 10.8 ms |
   | 2.5, 3.0 | 1920×1080 | 8.9 ms |

   No 2560×1440 or 2880×1620; nothing below 1920×1080. The presets: "4K UHD – 2160p" (1.0),
   "1800p class" (1.25, draws 3328×1872), "1440p class" (1.7, draws 2432×1368), "Full HD – 1080p"
   (3.0). All at 59–60 fps but the first (57).
2. **Fullscreen works:** run 177's window covers the 1920×1080 display without a frame or the
   panel, the game and the menu scaled to it (screenshot to the maintainer only); no failed
   submission.

**Verdict.** Passed for the presets and for fullscreen from the file; F11 and the menu's box
switch the same request at run time and await the maintainer's hands.
