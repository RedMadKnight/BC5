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

## Addendum, 2026-11-15: the shared swap to W with the games menu, prepared (the maintainer's "tak", via the top)

Prepared on the laptop only; each box step waits for the top's GO after the night series. Driver: `round0420w.sh`
(race, pad, replug, kit, swapdry, swap, smoke, undo).

- **The patch** (the laptop's replay; the kit is in the session's scratchpad, not committed: 3.9 MB): f266548 from a
  local clone + main's patch 0001 gives `27b6416f` exactly (B); exp 0419's W tree (`tree-build-W-ten.md5`, 133 of 133
  files) over it, then `mkmenu0420.py` (`hostMenu.cpp` `0f324fa4`, as on the box) and `games_list.hpp` (`24776450`,
  with the name fix): **`0001-W-menu.patch` `101555c7`**, 134 patched files listed in `tree-W-menu.md5` (`e7f6224a`);
  `grep -c 'exp 0372'` = 5 and `src/bc5/pad_audio_route.hpp` is in it. W over B: 56 files.
- **Audio and pad code**: W changes `audio.cpp` (9 lines: reads of `KYTY_BC5_PAD_PW_PROPS`, `KYTY_BC5_NO_PAD_AUDIO`,
  `KYTY_BC5_PAD_RUMBLE_FALLBACK` through exp 0419's reading rule), `controller.cpp`/`.h` (86 + 4 lines, V's touch
  code cut), `hostInput.cpp`, `libAudio.cpp`, `libAudio2.cpp` against B, and against V `audio.cpp`, `controller.cpp`,
  `hostInput.cpp`, `libAudio2.cpp` (exp 0419's lean rewrite; build-W.md said "no pad or audio code", which holds for
  what the code does in the normal build, not for the files). So the software replug runs on W first (step b, on the
  private W+menu normal build `10e3ef15`). Replug results so far: V's R12 passed (3 pulls of 3, private normal
  `c25e4d2b`); none for W.
- **`swap0420w.sh`** (dry, apply, undo): the shared tree B -> W+menu (checked against the list), the backend source
  files the private W source differs in and the archive rebuilt (it must equal the private one), both emulators
  rebuilt in place, then `play-any.sh` (`fc7a1395`, with the race order), `lean-session.sh` (`189885ea`),
  `play-astro.sh` (`e943bd8f`), the shared bc5-mount (`be372d39`); every replaced file kept under
  `~/bc5-work/exp0420/before-W` and read back; a failure restores and checks the restore (the lock is kept if it does
  not read back); `undo` puts everything back from the copies. Refuses while an emulator, a launcher or a lean session
  runs. Not touched: `play-pkg.sh`, `bc5-run.env`, the shortcuts, the saves; no launcher of the kit names
  `BC5_GUARD_MAP_RULE`, `BC5_GUARD_PRT_BG` or the learned windows (checked). `test-swap0420w.sh` (stand-ins: a
  small git tree, two small patches, stand-in distrobox and ninja): 13 of 13 (dry, apply, a second apply refused,
  undo, a failed lean build restored, refusals for a lean state, a changed launcher, a patch without the route).
- **`smoke0420w.sh`** (step d): the menu normal and lean through the shared `play-any.sh` (a screenshot each; lean:
  the shell active again, the state empty); the second title from the installed list as the menu's click does it
  (`play-any.sh <folder>`, so its script runs with `BC5_GAME_DIR`), 120 s, with a private copy of the shared
  `play-pkg.sh` whose working and save directories are exp 0413's private `wd`, reset from exp 0412's named snapshot:
  the live saves are not used. No install, no uninstall.
- `raw/swapW-dry-laptop.txt`: the patch's size and the two launcher diffs as the laptop sees them.
- After the swap, on main: patch 0001 becomes `101555c7` (only if the swap's checks pass), and `backend/` gets the
  private W backend source files the swap copied (D19: main matches what the shared builds are built from).
- **Step (a) done, 2026-11-15 12:18** (the top's GO after n15; the maintainer's "Yes, after it"): `round0420w.sh race`
  (`install-race0420.sh`, one lock line, released): the shared `play-any.sh` 92c090c5 -> **1cd59817**, `lean-session.sh`
  88ea3fa7 -> **189885ea**; `.before-race` copies read back (92c090c5, 88ea3fa7); no emulator, launcher or lean state
  at the time; `bash -n` both; `lean-session.sh dry` sees the shell active. Undo: `bash
  ~/bc5-work/exp0420/race-107e307a/fix-lean-race.sh undo`. Raw: `raw/race-install-20261115-1218.out`. Steps (b)-(d)
  are on hold (the guardian's longer pauses on W).
- **Steps (c) and (d) done, 2026-11-15 12:47 to 13:00** (the top's GO; the maintainer: "Wymaga to Twojego jednego
  „tak“ => tak" and "Yes, install"). Step (b), the replug, was not run: the top read W's normal build as V's
  (`env_rule.hpp`, the defaults' diff) and V's R12 covers the touch cut; from the code W's normal `audio.cpp` differs
  only when `KYTY_BC5_NO_PAD_AUDIO` is set to "0" (now off, before on), which no launcher sets.
  - Dry run (`raw/swapW-dry.out`): only the expected files; the backend source `direct.hpp` a9fcb26b -> e96e5c73,
    `direct.cpp` 51279eae -> aeec4c09 (the laptop's copy of W's backend file is the same); the lean order of the
    race fix kept; no line with `ulimit` removed (neither old launcher had one; `play-pkg.sh` is not touched).
  - The swap (`raw/swapW-apply.out`, 12:47:37 to 12:53:28, one lock line, released): tree 101555c7 (134 of 134
    files), archive **9aab722c** (= the private one), normal **bab1ce79**, lean **c4aca9af**: not byte-identical to
    the private builds (10e3ef15 / 98ba9468; other build directories, as in exp 0413's swaps); the BC5 word lists of
    the shared and the private binaries are the same (normal 616 words, lean 490), the sizes differ by about 47 KB;
    `play-any.sh` **fc7a1395**, `play-astro.sh` **e943bd8f**, `lean-session.sh` 189885ea, bc5-mount **be372d39**.
    Copies: `~/bc5-work/exp0420/before-W`. Undo: `bash ~/bc5-work/exp0420/swapW/swap0420w.sh undo`.
  - Smoke (`raw/swapW-smoke.out`, `raw/swapW-smoke-d2.out`; screenshots seen, not committed): the start page in
    both builds with Open game, Install game, "Installed games: Marvel's Wolverine (PPSA03671) 196.7 GB" and
    Recent; lean: the shell stopped for the window and active again, the state done. The second title from the
    list's path (`play-any.sh ~/bc5-data/games/PPSA03671`, as the menu's click), normal and lean: the emulator from
    the shared build, `--game` the installed folder, alive at 90 and 120 s, the title screen ("press X") at 40 and
    42 fps, then quit; saves: a private copy of exp 0412's named snapshot, no pad key. 0 kernel lines. The first d2
    attempt stopped before starting (the check of the private launcher's save paths caught a word name; fixed).
    The lean run's line "state file NOT-EMPTY" was read while the watcher was still restoring: a minute later the
    state was done, no owner left, the shell active.
- **Recent without missing paths** (the maintainer, 2026-11-15 13:05, directly: "recent nie może być elementów, które
  nie istnieją"; the start page listed `~/bc5-data/pkg/game.pkg`, which is gone): `mkmenu0420.py`'s 26th edit,
  `LoadRecent` drops a path that does not exist and writes `recent.txt` without it (an uninstalled game's folder too).
  `hostMenu.cpp` 0f324fa4 -> a6314317, patch 0001 101555c7 -> **ba617454** (`tree-W-menu-r.md5`), `exp 0372` = 5.
  `swap0420r.sh` (dry, private, apply, undo): the private build first as the compile check, then the shared tree's
  one file and both shared emulators, copies under `~/bc5-work/exp0420/before-R`. Waiting for a box slot.
- `CLAUDE-md-0420.diff`: the proposed CLAUDE.md lines for the shared W (hashes, record, undo, kernel 7.3.3-ogc1.1,
  launchers); not applied: CLAUDE.md changes on the maintainer's own word.
  **Done 2026-11-15 13:04 to 13:05** (the top's GO): private normal f965b9ec, lean e19e2e3c (0 warnings in
  `hostMenu.cpp`); shared tree **ba617454**, normal **fd3d0ed2**, lean **480656cc** (were bab1ce79 / c4aca9af); the
  lock released at 13:05:36. Undo: `bash ~/bc5-work/exp0420/swapR/swap0420r.sh undo`. Not looked at on the screen
  yet (the change only reads the file system when the list is read).
- **The lean session's second race** (Codex 2026-11-15 10:37 and 15:40 UTC, LESSONS R56 second occurrence; the top
  confirmed both in 189885ea): (1) the watcher read the owner, a stop took the dead launcher's session over, then the
  watcher wrote its pid into the new claim and restored during the new play; (2) a failed restore released the claim
  and the watcher's retry ran unclaimed. `../0412-memory-guardian/lean-session.sh` **1f1be812**: every read and
  write of the owner and the state and every unit start or stop run under one `flock` (command form with `-o`, so
  the watcher never inherits the lock), the owner's token ("pid starttime") is checked again right before each; the
  watcher takes the claim inside the lock and keeps it through its retries (a stop meanwhile is refused, exit 3),
  releasing it after a successful restore or when it gives up; a restore by hand while another live process owns
  the session is refused (exit 3) instead of starting the shell during a play; without flock a stop refuses (the
  play runs with the desktop) and a restore runs unlocked. `LEAN_TEST_BARRIER=<dir>` points (stop-before-lock,
  watch-gone, handover-locked, watch-owned, watch-retry) let the tests force each interleaving.
  Tests on the laptop, stand-ins only (systemctl, pgrep, setsid, `flock-standin.sh`: mkdir mutex):
  `test-lean-race.sh` 29 of 29 (`raw/test-lean-race-locked.out`; (d), (d2), (e), (e2) new, (c2) changed to the
  refusal), `test-lean-session.sh` 11 of 11 (`raw/test-lean-session-locked.out`; restores by hand now name the
  owner, the watcher takes the launcher's start time). The old 189885ea under the same test: 16 of 29
  (`raw/test-lean-race-old-189885ea.out`; it has no barrier points, so its (d)/(e) failures are not forced
  interleavings, only a record that it does not behave as the new checks require).
  `swap-lean-lock.sh` (dry, apply, undo) changes only the shared helper (189885ea -> 1f1be812), keeps it as
  `lean-session.sh.before-lock` (`.before-race` stays), checks that flock works on the box, refuses while an emulator
  runs or a lean session is active; its stand-in run is `raw/test-swap-lean-lock.out`. **Not installed**: the top
  picks the moment and puts it to the maintainer; `tools/scripts/launchers/lean-session.sh` on main stays 189885ea
  until then.
