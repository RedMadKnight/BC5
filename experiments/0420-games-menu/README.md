# Experiment 0420: open, install and uninstall games from the emulator's menu

## Question

The maintainer (2026-11-15, through the top session): the menu gets a list of installed games with the second title on
it, installs games and uninstalls them (freeing their space), opens packages, images and installed games of every
format we support, in the normal and the lean build, and stays simple. The plan is `PLAN.md`.

## Setup

Private only: the shared launcher (`~/bc5-work/play-any.sh` 92c090c5), the shared builds and the desktop shortcuts are
not changed; that waits for the maintainer's "tak".

| Part | Where | What |
|---|---|---|
| bc5-mount `uninstall` | `tools/bc5-mount/src/uninstall.rs`, tests `tools/bc5-mount/tests/uninstall.rs` | removes only a directory directly under the games root that is not a link, is on the root's file system and holds a valid `.bc5-install.json`; refuses anything else with exit 2; never touches the source image or a save directory |
| review fixes in `install.rs` | `tools/bc5-mount/src/install.rs` | the descriptor leaked by `into_raw_fd` in the `posix_fadvise` block; `statvfs("")` for a destination without a directory part; paths in `.bc5-install.json` escaped (a quote broke the record) |
| the menu | `mkmenu0420.py` (patch 0001, `hostMenu.cpp`), `games_list.hpp` (to `src/bc5/`), CPU test `test0420games.cpp` | File: Open game..., Installed games, Install game..., Uninstall game, Recent, Quit; the launcher page the same; the uninstall confirmation |
| one launcher | `play-any.sh` (from the shared 92c090c5 with its lean-session lines, and exp 0409's install logic), tests `test-play-any.sh` | open, install in the background with progress, uninstall through bc5-mount, an installed folder through its title's script |
| ASTRO BOT's script | `play-astro.sh` (from the shared 48238ccd) | takes `BC5_GAME_DIR` (an installed folder, no mount), as `play-pkg.sh` already does |
| the round on the box | `round0420.sh`, `look0420.sh` | build and tests of bc5-mount, the launcher's tests, the menu on the private tree, the menu started and photographed |

## Result (2026-11-15 08:42 to 08:47, the box, CPU only; raw `raw/round-box.out`)

- **bc5-mount** on the laptop: `cargo fmt --check`, `cargo clippy --all-targets -- -D warnings` (Windows, and the
  Linux target without the `fuse` feature), `cargo test` all pass. On the box (the ubuntu distrobox, Linux): `cargo
  test` passes, the uninstall tests 17 of 17 (the three that need symbolic links run there only), the release build
  `be372d39` at `~/bc5-work/exp0420/bc5-tools/release/bc5-mount` (the box's cargo has no fmt and no clippy).
- **The launcher's tests**: 14 of 14 on the laptop and on the box (stand-ins for the emulator, bc5-mount and the
  title scripts): each format opened, an installed title through its own script (the second title through
  `play-pkg.sh`, any other through `play-astro.sh`, both with `BC5_GAME_DIR`), install in the background with its
  result line, install refused for an installed title and for an image without a title id, uninstall through
  bc5-mount, uninstall refused outside the games root and while an install runs, exit 78 without an action, the
  lean build.
- **The menu** on the private tree at build W (`hostMenu.cpp` 0f324fa4, then with the name fix below): compiled at
  the first attempt in both builds with no warning in `hostMenu.cpp`; normal `10e3ef15`, lean `98ba9468`.
- **Seen on the box** (the empty window started through the private launcher, 25 s each, a screenshot each, not
  committed): the launcher page shows Open game..., Install game..., the installed list with the second title, its
  TITLE_ID and 196.7 GB, and Recent. The first look showed the name as question marks: the first `titleName` of
  `param.json` is not in ASCII and the menu's font has no other glyphs. Fixed in `games_list.hpp` (the first ASCII
  `titleName`, else the TITLE_ID; tested), rebuilt (one more compile of `hostMenu.cpp`, 10 s), and the second look
  shows the name. The lean build's look: the Plasma shell was stopped for the window and was active again after it.
  0 kernel lines.
- **NOT tried on the box**: a real install and a real uninstall through the menu (only on stand-ins and in
  bc5-mount's own tests, which install a synthetic image and uninstall it); starting a game from the installed list
  (the launcher's tests show it calls `play-pkg.sh` with `BC5_GAME_DIR`, which is how the second title is played
  from its folder today); the File menu opened by hand. The second title's folder was not touched.

## What the maintainer will see (for his "tak")

The launcher page (the window with no game):
- **Open game...**: one file browser for `.ffpfsc` images, `.pkg` packages and game folders (a folder that holds
  `sce_sys/param.json` is shown as "(game folder)" and opened, not entered).
- **Install game...**: the same browser for `.ffpfsc` and `.pkg`; the install runs in the background into
  `~/bc5-data/games/<TITLE_ID>`, the page shows "Installing <TITLE_ID>: n/m files, x/y GiB, ..." while it runs and
  "Installed <TITLE_ID> at ..." (or the failure) when it ends; the game then shows on the list.
- **Installed games**: every installed game, as "Name (TITLE_ID) size"; a click starts it with its title's settings.
  The second title is on it now.
- **Recent**: as before.

The menu bar's File menu: **Open game...**, **Installed games ▸**, **Install game...**, **Uninstall game ▸**,
**Recent ▸**, **Quit**. Uninstall opens a confirmation: the name and TITLE_ID, the folder, "Frees: <size>", "The
game's folder is deleted. Its saves are kept", and, when the image it was installed from is no longer at its path,
a warning that playing it again needs that image again (the second title's case: its image is not on the box).
"Close session" is now in the Emulation menu. Install and Uninstall are offered on the launcher page only (not
while a game runs).

## Verdict

Built and checked privately; ready for the maintainer's look. What a swap would change, on his "tak": the shared
launcher `play-any.sh` (one launcher; `play-any-0409.sh` no longer needed; the old one kept as `.before`),
`play-astro.sh` (`BC5_GAME_DIR`), the shared bc5-mount binary (`~/bc5-work/bc5-tools-ubuntu`, the menu's uninstall
and the fixed install), and the menu in both shared builds with the next patch swap. The desktop shortcuts stay as
they are (both call `play-any.sh`).

## Addendum, 2026-11-15: the lean session's race (Codex 10:07 UTC in codex-to-claude.md; LESSONS R56)

Not seen on the box; found in the code. `play-any.sh` called `lean-session.sh stop $$` before its pgrep check, and
`stop` replaced the state with the units active right then, so a second lean click during a lean play wrote an empty
state (the shell was stopped already) before pgrep refused it; the first play's watcher then restored nothing and the
Plasma shell did not come back. The shared `play-any.sh` 92c090c5 probably has the same order (not read: the box was
in the n15 series).

- `play-any.sh`: the lean stop comes after every check that can refuse the start (pgrep, the emulator, the settings
  file); a stop that finds a live lean session (exit 3) refuses the start.
- `../0412-memory-guardian/lean-session.sh`: one owner, the directory `lean-session.state.owner` with "pid starttime",
  made by an atomic rename; a stop while the owner lives changes nothing and exits 3; a dead owner (or a reused pid)
  is taken over and the units it noted are kept (old state plus what is active now); the watcher takes the claim
  when the launcher is gone, ends without a restore when a later stop took the session over, and the restore
  releases the claim (a restore by hand while the owner lives keeps it).
- Tests on stand-ins, on the laptop (a temporary HOME; stand-in systemctl, pgrep and setsid): `test-lean-race.sh`
  14 of 14, five runs in a row ((a) A runs, B refused, A's end restores the shell once; (b) two stops at once: one
  owner, the state not empty, one restore; (c) a dead owner taken over with its noted unit; (c2) a restore by hand),
  4 of 14 on the old two scripts; `test-lean-session.sh` 11 of 11; `test-play-any.sh` 14 of 14; `bash -n` on each.
- Deployment (the shared `~/bc5-work/play-any.sh` and `~/bc5-work/lean-session.sh`) only on the maintainer's word and
  not while a lean session is active.
- The shared launcher (the guardian read it from the code: 92c090c5 has the same order, stop at line 29 and `pgrep -x
  kyty_emulator` at line 42; the box was not read): `fix-lean-race.sh`, a proposal for the maintainer's word. Dry by
  default; `apply` only on the exact 92c090c5, refuses while an emulator runs or a lean session is active (a live
  owner, or a state not restored yet), moves the three lines after `mkdir -p "$KYTY_BC5_MENU_DIR"` (3 lines out, 8
  in; the result `1cd59817` on the reference copy `box/play-any.sh.box`), puts the one-owner `lean-session.sh` in
  place, and keeps both old files as `*.before-race`; `undo` puts them back. On stand-ins: `test-lean-race.sh` with
  `LAUNCHER=` the changed shared launcher 14 of 14; with the unchanged shared launcher and the old lean-session.sh
  (`LEAN=`) 4 of 14, A's end not restoring the shell (the defect reproduced).
