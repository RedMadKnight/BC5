# 0317 — DualSense stick clicks (L3/R3) in the second title

**Question.** The maintainer reports (2026-10-25) that neither stick click (L3, R3) of the DualSense does anything
in the second title on today's shared builds (normal 226bcb82, lean 71ef2194; `hostInput.cpp` md5 47f83afb). He
adds that he may have mixed up the buttons. Does the host drop the clicks, or does the pad or the title?

**Setup.**
- Offline, on the laptop: KytyPlus `f266548` (`refs/Coder787-source_KytyPlus`, `git archive`) with main's patch
  0001 as of `ffd0e49`, applied with `git apply --include='src/*'`. That tree has F367's MangoHud lines. The same
  patch at `d670067` (2026-10-22) was applied likewise, for comparison. KytyPlus's SDL2 is a submodule link there,
  so SDL's code is cited from the box's SDL 2.33.0 (read 2026-10-22 in experiment 0193) and from the SDL 2.23.2
  that `refs/InoriRus_Kyty` vendors.
- Box (with the top session's GO, after the maintainer's play):
  - `reads.sh` (R1, read-only): `input.cfg`, the input lines of `bc5-run.env`, the newest play logs' "pad button …
    is disabled" lines, and the pad recorder's `hold l3`/`hold r3` counts.
  - `probe.sh 45` (T1, attended, no game, no GPU): experiment 0193's `padprobe` (built on the emulator's own SDL)
    listens for 45 s while the maintainer presses L3 ×3, R3 ×3, Cross and the touchpad. Its lock line is removed
    on exit.

**Result (offline part, 2026-10-25).**
- **SDL gets the clicks as ordinary game-controller buttons.** In both HIDAPI PS5 report paths, report byte 1 bit
  0x40 becomes `SDL_CONTROLLER_BUTTON_LEFTSTICK` (7) and bit 0x80 becomes `RIGHTSTICK` (8). Sources: SDL 2.23.2
  `src/joystick/hidapi/SDL_hidapi_ps5.c:859–860` (simple report) and `:957–958` (full report); the box's 2.33.0
  has the same decode right after `START` (~`:1222–1223`). The generated HIDAPI mapping on the box was
  `leftstick:b7,rightstick:b8` (experiment 0193 `raw/probe-caps.txt`), an identity mapping. This is unlike the
  touchpad's `b15`, a button the host had no case for (F252). KytyPlus's own `dualsense.cpp:330–331` reads the
  same bits.
- **The host maps and forwards them, and this path has not changed since 2026-10-22.** `window.cpp:89–90` maps
  LEFTSTICK/RIGHTSTICK to `PAD_BUTTON_L3` 0x2 / `R3` 0x4. The PS5 layout in AnyPS5
  `core/libs/prx/libScePad/include/PadInputTypes.hpp:32–33` has the same values. Then `window.cpp:407` drops a
  button only for a `Pad:leftstick=none` / `Pad:rightstick=none` line, and `:408` calls `ControllerButton`.
  The recorder writes `hold l3` there. `GameController::Button` sets the bit in the slot, and `pad_fill_data`
  copies `buttons` unchanged. `window.cpp`, `controller.h` and `libPad.cpp` are byte-identical to the 10-22 tree.
  `controller.cpp` changed only in rumble and `hostInput.cpp` only in the per-title RayTracing/MangoHud lines. On
  10-22 the recorder logged 13 and 4 `hold l3` in two second-title sessions (09:33, 09:56; no `hold r3` in
  either). So L3 reached the host then.
- **Nothing later clears 0x2/0x4 under the maintainer's configuration.** The top session read `input.cfg` at 16:10:
  its only bindings are `Cross=X` and `R2=Keypad 9`; it has no `Pad:` line and no `L3=`/`R3=` line. The only
  writers of the slot's bits are `GameController::Button` and `Axis`, which touches L2/R2 only. The only callers
  that can release L3/R3 are:
  - the host input stream: the release of Left/Right Shift (L3) or Left/Right Ctrl (R3) in the built-in keyboard
    layout, and the overlay's release-all, which releases only controls the host stream itself holds;
  - the scripted-input helpers, active only with `KYTY_BC5_AUTOPRESS`/`KYTY_BC5_INPUT_CMD`.

  Pad-axis bindings act only on bound axes, and there are none. The settings overlay swallows pad buttons only
  while it or the PS-button menu bar is open; then every button is dead, not only L3/R3. It always takes Guide
  (PS). The binding capture acts only inside the open overlay. The recorder only writes lines.
- **What is left:** the pad's own stick clicks (T1 decides), or the title not using L3/R3 where they were
  pressed (the maintainer's own doubt). If the normal build's recorder shows `hold l3`/`hold r3` during
  today's play, the host side is closed: `pad_fill_data` hands the slot's bits to the game unchanged.

**Result (box, read by the top session).**
- `~/bc5-work/input.cfg` (read 16:10): no `Pad:leftstick`/`Pad:rightstick` line, no `L3=`/`R3=` line; the only bindings
  are `Cross=X` and `R2=Keypad 9`, plus the RayTracing and RenderScale lines.
- The maintainer's session of 2026-10-25 16:10–16:33 on the normal shared build (226bcb82) recorded `hold l3` 56 times
  and `hold r3` 35 times (`KYTY_BC5_INPUT_RECORD`; the file is kept on the box as
  `~/bc5-work/exp0315/route-record-try2.txt`, not copied here).
- T1 (the padprobe) and the rest of `reads.sh` were not needed and were not run.

**Verdict.** Closed on the host side. Both stick clicks reach the host's pad slot from the DualSense: 56 L3 and 35 R3
presses were recorded where `ControllerButton` sets the bits, and `pad_fill_data` hands those bits to the game unchanged.
Nothing in the host drops or clears them under the maintainer's configuration. That the title showed no reaction is the
title's context (where and when it uses L3/R3), as the maintainer suspected himself. No fix and no patch change.
