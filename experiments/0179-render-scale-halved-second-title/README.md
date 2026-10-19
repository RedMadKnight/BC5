# 0179 — The second title's halved frame rate was its timestamp scale of 1.70, saved from the Video tab; the lean build measured

**Question.** Exp 0178 left the box running the second title 1.5–2× slower since about 17:57, for
any build, and proposed a reboot as the test. The maintainer rebooted at 22:44. Did that restore
it? If not, what persists across a reboot? Then the question of exp 0177: is the lean build faster?

**Setup.**
- After the reboot: kernel 7.2.9-ogc3.1 (it was 7.2.4-ogc3.1: the reboot also brought in a pending
  update), host Mesa 26.2.4, the container's Mesa 26.0.8. All 40 CUs were active and routed, and
  the governor was running.
- `lean-check.sh` (here; it now passes `LC_ENV` to the launcher) and `flip-rates.sh` (exp 0178).
  Runs ld11 (normal) and ld12 (lean).
- **Files that survive a reboot.** `~/bc5-work/input.cfg`, the host's input and video settings
  (F2 menu, `KYTY_BC5_INPUT_CONFIG`), was saved at 18:00:03. It holds `RenderScale.<TITLE_ID>`, the
  GPU timestamp scale per title (experiments 0046, 0047, 0115). The Video tab's presets for "the
  game's 3D view" are 1.0, 1.25, 1.7 and 3.0, named 4K UHD, 1800p class, 1440p class and Full HD.
  They were measured on ASTRO BOT.
- **Run ld13.** The second title's entry was set from 1.70 to 1.00, with the file backed up first
  (`input.cfg.bak-0178`).
- **Normal against lean.** At scale 1.00: ld14 and ld16 (normal), ld15 and ld17 (lean). Then
  ld18–ld21, alternating, with Mesa's overlay layer logging the presents per second to a file, no
  display (`VK_INSTANCE_LAYERS=VK_LAYER_MESA_overlay`, `VK_LAYER_MESA_OVERLAY_CONFIG=no_display,fps,
  frame_timing,fps_sampling_period=1000,output_file=…`). The lean build has no counter of its own,
  and the layer measures both builds the same way.
- Raw: `raw/runs-2026-10-19-evening.txt` (per-run summaries, journal flip rates, the settings diff),
  `raw/ovl-*.csv`.

**Result.**
- **The reboot changed nothing.** ld11 ran the intro at 19.9 and the start screen at 26.0.
- **The scale did it.**

  | run | `RenderScale.PPSA03671` | intro, flips/s (t 20–33) | start screen, flips/s (t 55–82) |
  |---|---|---|---|
  | ld11 (after the reboot) | 1.70 | 19.9 | 26.0 |
  | ld13 | 1.00 | 27.9 | 45.9 (journal 46.2) |
  | ld14, ld16 | 1.00 | 28.2, 28.3 | 46.6, 46.0 |

  The 17:54 session's start screen (32.3) is consistent with the preset chosen live during it.
  The 17:58 session started with 1.70 already in the file. The saves of ASTRO BOT (`PPSA21567`)
  and of `UNKNOWN` were also at 1.70 (exp 0105 for ASTRO BOT). TODO(verify) the mechanism inside
  the title: the drops land on whole divisors of 60 Hz (30 → 20, about 50 → 25), as a frame pacer
  that reads the scaled GPU time and waits for one more vblank would produce.
- **The GPU clock reading was a red herring.** `gpu_metrics` average gfxclk reads 1065–1069 MHz at
  full speed, as it did when slow. It says nothing about the clock under the governor's SMU method
  (exp 0043, 0126). F235's clock lead and exp 0178's wave-dump lead are both withdrawn.
- **Lean against normal** (overlay layer, presents per second):

  | run | build | intro | start screen | lowest second on the start screen |
  |---|---|---|---|---|
  | ld18 | normal | 29.6 | 46.7 | 41 |
  | ld19 | lean | 29.6 | 47.8 | 42 |
  | ld20 | normal | 29.8 | 45.9 | 39 |
  | ld21 | lean | 29.7 | 47.0 | 41 |

  The overlay's series matches the normal build's own frame counter second by second (ld18: 46.7
  both). The lean build is about 1 flip/s faster on the start screen (+2 %) in both pairs. The
  intro is at the title's cap of 30 in both builds.
- **Video tab warning.** For any title other than ASTRO BOT, the tab now says the steps were
  measured on ASTRO BOT. It says a title that paces its frames by the GPU time runs slower above
  1.0 (the second title at half rate at 1.7), and to keep 1.0 unless measured
  (`settingsOverlay.cpp`). It compiles in both builds; the tab itself has not been opened since.
- **The setting.** `input.cfg` keeps `RenderScale.PPSA03671=1.00`; the maintainer's file of 18:00
  is at `input.cfg.bak-0178`.

**Verdict.** The box was never slow. One save of the Video tab at about 17:57 set the second
title's timestamp scale to 1.70, a preset meant for ASTRO BOT's resolution, and the title then
paced itself at half rate (F237). At 1.00 it is back at 28–30 in the intro and 46–47 on the start
screen. Every measurement of the second title from 18:00 to 22:50 ran at 1.70: exp 0175's A/Bs,
0177, 0178 and the maintainer's evening sessions. Their differences still hold, but not their
absolute rates. The lean build is about 2 % faster than the normal one on the start screen
(F236).
