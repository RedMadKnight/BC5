# 0047 — a resolution choice in the F2 menu, and a restart from it

**Question.** The maintainer asked for a resolution choice (HD, Full HD and so on) in the game
window's F2 menu, with a way to restart the game after changing it, and whether a lower
resolution makes the GPU work less. The title registers 3840×2160 output buffers and asks the
system for no video mode (HANDOFF F67, F100), so a resolution cannot be handed to it; its own
dynamic resolution can be steered through the GPU timestamps it reads (experiment 0046). What
does it settle at for which scale, and does that work from the menu?

**Setup.** As in 0046. New in the host (patch 0001):

- The timestamp scale is a live setting: `Libs::Bc5Gc::Direct::SetTimestampScale` /
  `GetTimestampScale` (`bc5LleAgc.cpp`); `BC5_DIRECT_TS_SCALE` gives the value at start.
- `RenderScale=<k>` (0.5–4) in the input configuration file (`hostInput.cpp`), applied when the
  file is loaded and on Apply/Save, and written back by Save.
- The size of the main 3D view (a colour target and a depth buffer of the same size, at least
  640 wide) is followed all the time (`GetMainPass`).
- F2 menu, new tab *Video* (`settingsOverlay.cpp`): the 3D view's size and the scale now, four
  presets and a slider (live), Save, and *Restart game* behind an "I have saved" box: the
  emulator exits with code 75 and the launchers (`play-astro.sh`, `play-pkg.sh` on the dev box)
  start it again with the mount and the settings kept.

Runs 171 (scale 2.0 from an input file with `RenderScale=2.0`), 172 (`BC5_DIRECT_TS_SCALE=3.0`) and
173 (70 s with the menu open, `KYTY_BC5_SETTINGS_OPEN=1`), 2026-10-10 21:34–21:51; runs 166–170
from 0046. Raw output in `raw/`.

**Result.**

| Scale | Run | Main 3D view from 240 s | GPU busy (380–418 s) | fps |
|---|---|---|---|---|
| 1.0 | 166 / 163 | 3840×2160 | 17.0 ms | 57 |
| 1.2 | 170 | 3328×1872 | 15.1 ms | 59.2 |
| 1.5 | 169 | 2432×1368 | 11.7 ms | 59.9 |
| 2.0 (from the file) | 171 | 2432×1368 | 10.8 ms | 59.9 |
| 3.0 | 172 | 1920×1080 | 8.9 ms | 60.0 |

- The title's steps are 3840×2160, 3328×1872, 2432×1368 and 1920×1080; it went no lower than
  1920×1080 here or with the GPU slowed to a fifth (run 168), so HD (720p) is out of reach.
- A lower resolution does make the GPU work less: half the GPU time at 1080p. Above 60 fps there
  is nothing to gain, the title paces itself to 60; the room is for heavier scenes.
- `RenderScale` from the input file reached the GPU path (run 171). The menu opens with the new
  *Video* tab beside *Pad* (run 173, screenshot to the maintainer only); the tab's controls and
  the restart are for the maintainer to try.
- No failed submission in runs 171–173.

**Verdict.** Passed for the mechanism and the presets (4K 1.0, about 1872p 1.2, about 1368p 1.5,
1080p 3.0); the menu's use and the restart await the maintainer.
