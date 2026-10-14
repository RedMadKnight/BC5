# 0106 — after the pacing fix: timestamp scale, the menu's limit, the way past Initial Setup

**Question.** Three things were left by experiment 0105:
- Does the GPU timestamp scale matter now?
- What limits the menu at 37 fps?
- Is there a menu past Initial Setup to compare the black background with (experiment 0104)?
- Where does the 170 MHz come from?

**Setup.** Unattended, the play shortcut's settings plus `BC5_DIRECT_REMEMBER_UNMAPPED=1` and
`BC5_DIRECT_PACE_FIX=11d0288100:100/170`, a fresh save, 2026-10-15 00:29–00:36:

| run | what |
|---|---|
| 392 | intro, `BC5_DIRECT_TS_SCALE=1.2` (the play settings) |
| 393 | intro, `BC5_DIRECT_TS_SCALE=1.7` (`bc5-run.env.pkg-noflipdefer-ts17`) |
| 394 | cross at 80 s (screen-reader dialog), then one circle at 95 s (`input394.cmd`); never a second cross |

Both 392 and 393 journal 30 graphics buffers from 32 s. The first 393 shared run 392's capture
directory (same minute) and was repeated. Run 391 (0105) supplies the menu profile.
`constscan.sh` searches the title's executable and modules for the constant in its common
encodings; it reads private files, stdout only.

**Result.**
1. **The timestamp scale changes nothing in the intro.**

   | | 1.2 (run 392) | 1.7 (run 393) |
   |---|---|---|
   | fps, 28–38 s | 53.6 | 49.4 |
   | frame, median | 17.1 ms | 17.1 ms |

   The render targets are the same in both: scene 2560×1440, output 3840×2160, radiance 1280×720.
   The play settings keep 1.2.
2. **The menu is limited by the title's CPU work now** (run 391, 95–120 s).
   - Frame: 26.9 ms mean, 25.4 ms median (37.2 fps).
   - GPU busy 12.7 ms; the largest buffers take 1.2–2.1 ms each.
   - Game thread inside the host 7.1 ms (prepare 3.0, CS 2.6), at the flip 1.4 ms.
   - **Outside the host 18.4 ms**: the title's own code on its render thread.
3. **There is no way back from Initial Setup** (run 394). The circle changes nothing; the screen
   still shows only "Enable screen reader" and "Select" as button hints. With a fresh state, the
   only way on is New Game, which run 326 showed can take the machine down with these settings.
   The main menu stays out of reach for an unattended comparison.
4. **No literal 170 MHz.** The executable (192 MB) and its modules hold no 170,000,000 as a 32- or
   64-bit integer, nor 1.7e8 or 1/1.7e8 as a float or double. They hold the float 1.7 six times, in
   the executable only. The title derives the clock from something else: a ratio, or a value it
   reads. Open.

**Verdict.**
- The timestamp scale stays at 1.2.
- The intro now runs at the title's 60 Hz pace (median 17.1 ms).
- The menu is CPU-bound in the title's own render-thread code (18 ms a frame). That is the next
  place to look, with the stack sampler (`pc-sampler.sh`).
- The black Initial Setup background cannot be compared with a later menu without New Game. With
  the text now complete, it looks like the design of this first-run screen.
