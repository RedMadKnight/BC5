# 0193 — The DualSense touchpad press never reached the game

**Question.** The second title asks for a touchpad press, and pressing the DualSense touchpad (also on
each half) does nothing. The host's pad recorder logged no `touchpad` line in the maintainer's session
of 2026-10-22 09:33. Where is the press lost: in SDL, in the host's input layer or in the game? And
does the title need touch positions as well as the button bit?

**Setup.**
- BC-250 dev box, 2026-10-22 09:40–10:05. USB DualSense driven by `hid-playstation`. The kernel gives it
  separate evdev devices for the pad, the motion sensors and the touchpad (`raw/proc-input-devices.txt`;
  the touchpad is `mouse1 event7`, so KDE uses it as a pointer, F77). Steam is not running. The
  launch environment is `bc5-run.env` with `SDL_JOYSTICK_DISABLE_UDEV=1`, and `~/bc5-work/input.cfg`
  has no touchpad line.
- Host: KytyPlus `f266548` with patch 0001, shared build of 2026-10-21 23:46:14
  (`~/bc5-work/kytyplus-build/src/kyty_emulator`). It links KytyPlus's own SDL 2.33.0
  (`3rdparty/SDL2`, `libSDL2.a`, HIDAPI and libudev on).
- `padprobe.c` is built against that same `libSDL2.a` in the `ubuntu` distrobox:
  ```bash
  gcc -O1 -Wall -o padprobe padprobe.c -I$HOME/src/KytyPlus/3rdparty/SDL2/include \
    -I$HOME/bc5-work/kytyplus-build/src/3rdparty/SDL2/include-config-release/SDL2 -D_REENTRANT \
    $HOME/bc5-work/kytyplus-build/src/3rdparty/SDL2/libSDL2.a -lm -ldl -lpthread
  distrobox enter ubuntu -- env SDL_JOYSTICK_DISABLE_UDEV=1 ./padprobe 0                       # as launched
  distrobox enter ubuntu -- env SDL_JOYSTICK_DISABLE_UDEV=1 SDL_JOYSTICK_HIDAPI=0 ./padprobe 0  # evdev, for contrast
  distrobox enter ubuntu -- env SDL_JOYSTICK_DISABLE_UDEV=1 ./padprobe 30   # listen 30 s for presses (needs a hand on the pad)
  ```
  It lists each joystick with its SDL driver (GUID byte 14 `h` = HIDAPI), mapping, buttons, touchpads
  and sensors. With a time given, it also prints button, touchpad-finger and raw joystick events.
- Code read: `src/graphics/presentation/window/window.cpp` (`ControllerButtonToPadButton`,
  `GameEventController`), `src/graphics/presentation/window/hostInput.cpp` (`Pad:` sources),
  `src/libs/controller.cpp` (`DualSenseInputCallback`, `ControllerButton` → `Bc5RecButton`, the
  subsystem init) and SDL's `src/joystick/hidapi/SDL_hidapi_ps5.c`, `src/joystick/SDL_gamecontroller.c`,
  `src/hidapi/SDL_hidapi.c` (all in the KytyPlus `f266548` tree).
- The fix was built without touching the shared binary. `edit0193.py` applies the source change to
  `~/src/KytyPlus` (originals in `~/bc5-work/exp0193/orig/`). `build0193.py` compiles `window.cpp`
  and `controller.cpp` with the shared build's own flags (`ninja -t compdb -x`) and links
  `~/bc5-work/exp0193/kyty_emulator` (2026-10-22 09:58:06, synced) from the shared build's other
  objects. `splice0193.py` puts the three files' diff into patch 0001; the result was checked with
  `git apply --cached --check` on a scratch index of `f266548`.
- No GPU run. The title was not started by this experiment.

**Result.**
- **The press reaches SDL as a button of its own, and the host drops it.** As launched, SDL opens the
  pad through **HIDAPI** (`/dev/hidraw2`, guid `…6800`, `raw/probe-caps.txt`).
  `SDL_JOYSTICK_DISABLE_UDEV` only switches the evdev joystick backend to its fallback scan.
  HIDAPI keeps libudev unless `SDL_HIDAPI_JOYSTICK_DISABLE_UDEV` is set or a sandbox is detected
  (`SDL_hidapi.c:1082–1093`), and the hidraw node is mode 0666. Under HIDAPI the pad has the
  `touchpad` button (20), `misc1` (the mic button), one touchpad with two fingers, and both sensors.
  The touchpad click is bit 0x02 of report byte 2, joystick button 15 (`SDL_hidapi_ps5.c:1230`; bit 0x04, button 16, is the mic),
  which the generated PS5 mapping names `touchpad:b15` (`SDL_gamecontroller.c:635`). The host's
  `ControllerButtonToPadButton` (`window.cpp:81–99` before the change) maps BACK, which on a DualSense
  is the Create button (`SDL_hidapi_ps5.c:1220`, bit 0x10), to `PAD_BUTTON_TOUCH_PAD`. It has no
  case for `SDL_CONTROLLER_BUTTON_TOUCHPAD`, so it returns 0, and `GameEventController` forwards
  nothing. The host-input stream (`HostInputGamepadButton`) would carry it only with a
  `TouchPad=Pad:touchpad` line, which `input.cfg` does not have. The recorder writes a button after
  the mapping (`ControllerButton` → `Bc5RecButton`), so its 0 `touchpad` lines fit a press that SDL
  delivered and the host threw away. The session at 09:56 (shared build) also recorded 0
  (`raw/route-record-summary.txt`, read at 10:01; that file overwrote the 09:33 recording, whose
  counts are quoted there). That session had the prompt on screen ("You gained a Level! Press" and
  the touchpad icon) at 09:59:51, and its recording runs to 09:59:59. The screenshot stays on the box
  only: `~/bc5-work/exp0192/shots/095951-teraz-4.png`, from capture `~/bc5-data/captures/play-20261022-0956`.
- **The native DualSense path is not in play.** `DualSenseInputCallback`, which maps the touchpad,
  is registered only when `Config::DualSenseEnabled()` is set (off by default), and its `Open`
  works on Windows only (F214). So on the box all input goes through SDL.
- **Through evdev the button is not there at all.** With `SDL_JOYSTICK_HIDAPI=0` SDL opens
  `/dev/input/event5` (13 buttons, no `touchpad`, no `misc1`, no touchpad surface). There the click
  only exists on the kernel's separate Touchpad device, which the desktop uses as a mouse.
- **Workaround with the current binary:** the Create button already reaches the game as the
  touchpad button (BACK → `PAD_BUTTON_TOUCH_PAD`). A `TouchPad=Pad:touchpad` line in `input.cfg`
  would also work.
- **The change (patch 0001, `raw/change-0193.diff`).**
  - `ControllerButtonToPadButton` maps `SDL_CONTROLLER_BUTTON_TOUCHPAD` → `PAD_BUTTON_TOUCH_PAD`.
    This is on by default: it is the press the game asked for, and it was dropped. `Pad:touchpad=none`
    in the input configuration drops it again, through the existing `HostInputPadButtonDisabled` check.
    Create keeps its old mapping.
  - Opt-in `KYTY_BC5_PAD_TOUCH=1` forwards SDL's controller-touchpad finger events
    (`ControllerTouch`). The pad data then carries up to two touch points: `touch_num`, x/y scaled
    into the 1920 × 943 that the host reports in `scePadGetControllerInformation`, and an id
    (1..127) that changes with each new contact (`TODO(verify)` the console's range and numbering).
    The touch points are taken as the latest sample at read time, as the motion data is. Without the
    variable the pad data is byte for byte what it was (`touch_num` 0, ids 1 and 2).
    `KYTY_BC5_INPUT_TRACE=1` prints each finger down/up.
  - The two units compile with the shared build's flags. The only warning comes from an existing
    `stringUtils.h` deprecation (`raw/build-0193.txt`), and the separate binary links.
- **Touch positions: not decided.** No reading on the box can tell whether the title checks a half or
  a finger position besides the button bit, because a field read by the guest cannot be traced.
  The maintainer pressed both halves because nothing happened, not because the prompt asked for a
  half. The test is a press in the title with the new binary
  (`BC5_EMU=~/bc5-work/exp0193/kyty_emulator`, which `play-pkg.sh` honours). If that does not clear
  the prompt, repeat it with `KYTY_BC5_PAD_TOUCH=1`.
- Found on the way: the DualSense touchpad is also KDE's pointer. Every press is a click at the
  pointer as well, and a click on the window's close button ends the emulator (F77). This change
  does not address that.

**Verdict.** Passed for the cause. The press is delivered by SDL's HIDAPI driver as
`SDL_CONTROLLER_BUTTON_TOUCHPAD` and dropped by the host's button table. This is our bug, not the
pad, SDL, the launch environment or the game. The fix is built (separate binary, the shared one
untouched) and in patch 0001, but not yet confirmed in the title. That confirmation, and whether the
title needs the touch positions (`KYTY_BC5_PAD_TOUCH=1`), is the maintainer's press in the game.
Replacing the shared binary, which a rebuild of `~/bc5-work/kytyplus-build` would do with only these
three files changed since 23:46, is the maintainer's call while other sessions are testing.
