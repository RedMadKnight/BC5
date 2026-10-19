# ADR 0011 — A menu bar in the emulator window

**Status:** accepted (2026-10-19), implemented in the KytyPlus patch (`src/graphics/presentation/hostMenu.cpp`)
and the dev box's `play-any.sh` launcher; verified in experiment 0164.

## Context

- The host is KytyPlus's `kyty_emulator` built without Qt (`KYTY_BUILD_LAUNCHER=OFF`): a plain SDL2
  Wayland window that needs `--game <dir>` to start at all (`main.cpp` prints the usage without it,
  `Emulator::Run` exits without an app0 directory). The window itself is created lazily by the
  graphics subsystem's init (`agc.cpp`, `WindowInit`), together with VideoOut's present thread.
- Games are started from two desktop shortcuts whose scripts (`play-pkg.sh`, `play-astro.sh`) mount
  the image with `bc5-mount`, export the title's settings (experiments 0036–0163) and restart the
  emulator on exit code 75 ("Restart game" in the F2 menu, experiment 0047). The mount, the
  system-module pack and the per-title switches all live in those scripts; nothing of it is in the
  host.
- The host already draws an ImGui UI in the presentation pass: the F2 settings overlay
  (`settingsOverlay.cpp`, `3rdparty/imgui` 1.92.9b, `imgui_impl_vulkan`), with keyboard, mouse and
  pad input routed to ImGui while it is open, and the present thread redrawing the last frame (or a
  blank one) whenever the overlay is active or changes (`NeedsImeRefresh`). No new dependency is
  needed.
- The maintainer wants what other emulators have: a window with a menu bar that opens an image or
  a package and closes the session, usable in fullscreen (the second title runs with
  `--fullscreen`) and from the pad.

## Decision

1. **The menu bar is ImGui, drawn by the settings overlay's pass.** `hostMenu.cpp` draws
   `BeginMainMenuBar` (File / Emulation / Help), a file browser (an ImGui popup: directory listing,
   `.ffpfsc` or `.pkg` filter, Up, pad navigation through ImGui's gamepad nav) and the launcher
   page shown when no game is open. `settingsOverlay.cpp` treats "host UI active" as *settings
   window open or menu bar visible*: the same input routing (the game gets nothing while the menu
   is up) and the same redraw trigger. F1 toggles the menu bar; so does the pad's Guide (PS) button,
   which a PS5 title never receives (the console keeps it for its own home menu). F2 still opens
   the settings window; the menu's *Emulation > Settings…* does too. RenderDoc's F1 capture stays
   when the emulator runs with `--rd`.
2. **An empty window: `kyty_emulator --menu`.** Without `--game`, `Run` initialises the subsystems
   as for a game (the graphics init creates the window and the present thread), skips the mounts
   and the ELF, and runs the window loop with the menu bar and the launcher page visible. The
   present thread's "blank frame + overlay" path draws it. `--fullscreen`, the input file and
   `Fullscreen=on` apply as for a game.
3. **The host never mounts.** The scripts own `bc5-mount`, the system-module pack and the per-title
   settings, and keep owning them. The menu's actions end the process with an exit code and a
   file, like code 75 does today:
   - **76** — *open*: the chosen path was written to `$KYTY_BC5_MENU_DIR/choice.txt`
     (and to `recent.txt`, eight entries); the launcher mounts it and starts the emulator on it.
   - **77** — *close session*: the launcher unmounts and starts `--menu` again.
   - **75** — *restart* (unchanged); **0** — quit (the window closes as before).
   `KYTY_BC5_MENU_DIR` names the launcher's state directory; without it the actions that need a
   launcher are shown disabled with the reason.
4. **One launcher: `play-any.sh [path]`.** It loops over those codes. A `.pkg` goes through
   `play-pkg.sh` (`BC5_PKG=<path>`: the mount at `~/bc5-data/mnt/pkg-play`, the title's exports,
   `--fullscreen`), a `.ffpfsc` through `play-astro.sh` (`BC5_FFPFSC=<path>`, the mount under
   `~/bc5-data/mnt/<first word of the file name>`, its `fakelib/` as the system-module pack when the
   file is not ASTRO BOT's), a directory straight to `--game`. No path, or code 77, means
   `kyty_emulator --menu` with the settings of `bc5-run.env`. The two title scripts are unchanged
   except that they take the path and the mountpoint from those variables.
5. **Pause/Resume and Restart are the existing ones.** Pause is the window loop's pause (Space: the
   present thread repeats the last frame and stops taking flips, so the title waits); Restart is
   exit code 75 behind a confirmation. Both are disabled on the launcher page.

6. **One logging switch for the session** (the maintainer's addition, 2026-10-19): *Emulation >
   Logging: on/off*. It is a runtime flag, `Log::Bc5LoggingOn()` (an atomic bool in `log.cpp`,
   initial value from `BC5_LOGGING`, unset = on), not the environment variables at start: the
   direct path's `journal()` and dump writers, `LOGF` / `Log::Write` (the guest's printf too),
   every stderr trace gate and the frame profile, drop tally and dispatch journal hooks read it
   first and return when it is off, so "off" costs one relaxed load per call site and the frame
   profile keeps no counters. The menu shows the state; `BC5_LOGGING=0` in the launcher's
   environment starts a session quiet. Experiment 0162 measured the journal's own cost as
   nothing visible (42.1 against 41.3 fps): the switch is for the traces and for the
   maintainer's peace of mind, not a performance setting.

## Consequences

- A session change is a process change: the title's memory, the GPU mappings and the learned-fault
  state start clean, as with code 75 today, and nothing in the host has to tear a title down.
  The cost is the window closing and reopening between sessions (about two seconds on the box).
- The menu is usable in fullscreen (it is drawn into the swapchain image) and from the pad (ImGui
  nav: d-pad/left stick, Cross activates, Circle backs out).
- The desktop shortcut for the window is `distrobox enter ubuntu -- ~/bc5-work/play-any.sh`; the
  two title shortcuts keep working as they are.
- Open: a title's own settings still come from the scripts, keyed by the file kind; a third title
  would need its own block there (a per-title env file is the obvious next step).
