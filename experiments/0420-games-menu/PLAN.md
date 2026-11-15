# Experiment 0420: open, install and uninstall games from the emulator's menu (plan, 2026-11-15)

The maintainer, through the top session: "Masz zrobić w menu opcję otwarcia gry z listy zainstalowanych gier. Drugi
tytuł ma być oznaczony jako zainstalowany. Kolejne zainstalowane tytuły będą pojawiać się na liście. Musi być też
możliwość odinstalowania tytułu ze zwolnieniem miejsca po nim. Build zwykły i lean mają mieć możliwość otwierania gier
z paczek jak AstroBot, otwierania zainstalowanych gier z wszystkich obsługiwanych przez nas dotychczas formatów,
instalacji gier i odinstalowania gier. Menu ma być proste". Private work until his "tak"; the shared launcher, the
shared builds and his shortcuts change only then.

## What is there today (read on 2026-11-15)

- The menu (`hostMenu.cpp`, patch 0001 since exp 0409): File has "Open game image…" (.ffpfsc), "Open package (.pkg)…",
  "Install game…" (exit 78 with `action.txt` = install), "Recent ▸" with an "[installed]" mark read from
  `installed.txt`, "Close session", "Quit". Exit codes: 75 restart, 76 open `choice.txt`, 77 close, 78 install.
- `bc5-mount install` unpacks both formats (`.ffpfsc` and `.pkg`, chosen by the file's magic) into a directory and
  `write_install_json` writes `.bc5-install.json`; `adopt` writes the record for a directory unpacked before. No
  uninstall.
- The shared `play-any.sh` (92c090c5) knows no install: exit 78 is taken as 77, and a directory goes straight to
  `--game` without the second title's launcher, so the second title cannot be started from the desktop today. The
  launcher that knows installs is only `exp0409/play-any-0409.sh`.
- On the box: `~/bc5-data/games/PPSA03671/` is the second title, installed (196 GB, with `.bc5-install.json`; its
  source image is not on the box); `~/bc5-data/games/` also holds ASTRO BOT's `.ffpfsc` as a plain file.

## The menu (patch 0001, `hostMenu.cpp` only)

File ▸
- **Open game…**: one browser for `.ffpfsc`, `.pkg` and a folder that is a game (it holds `sce_sys/param.json`; such a
  folder is opened, not entered). Replaces the two "Open" items.
- **Installed games ▸**: every `~/bc5-data/games/<dir>/` that holds `.bc5-install.json`, read from the folder each time
  the menu opens (not from `recent.txt`); the label is the game's name from `sce_sys/param.json` and its TITLE_ID. A
  click opens the folder (exit 76): the launcher starts it through the title's own script with its settings. The
  second title is on the list at once (its folder has the record).
- **Install game…**: the browser for `.ffpfsc` and `.pkg`; exit 78 with `action.txt` = install. The launcher installs to
  `~/bc5-data/games/<TITLE_ID>` in the background, writes `install-progress.txt`, and opens the menu again at once;
  the menu shows "Installing <name>: N %" in its status line and puts the game on the list when the record appears.
- **Uninstall game ▸**: the same list; a click opens a confirmation window with the name, the TITLE_ID, the size on
  disk (the record's `total_bytes`) and, when the source image is not at the recorded path, "the image this was
  installed from is not at <path>: a new install needs the image again". "Uninstall" writes `action.txt` = uninstall
  and exits 78; the launcher runs `bc5-mount uninstall` and opens the menu again with the result in the status line.
- **Recent ▸**, **Quit**. Nothing else in File: "Close session" moves to Emulation (it only acts while a game runs).

The same code is in the normal and the lean build: it reads `KYTY_BC5_MENU_DIR` (configuration, kept in lean by W).

## bc5-mount (`tools/bc5-mount`)

- **`uninstall <dir> [--games <root>] [--dry-run]`** (new): removes only a directory that (a) is not a symbolic link,
  (b) resolves to a direct child of the games root (default `~/bc5-data/games`), (c) is on the same file system as
  the root, (d) holds a `.bc5-install.json` that parses and names an image, a file count and a byte count. It refuses
  anything else with exit 2 and a reason. It removes the tree without following links (std's `remove_dir_all`), prints
  the bytes freed, and never reads or touches the source image or a save directory (saves are not under the games
  root). Tests on synthetic installs: a valid install removed; refused: a link to a valid install, a path outside the
  root, the root itself, a nested path, a folder without a record, a broken record, `..` in the path; a link inside an
  install is removed as a link and its target stays.
- **The two review fixes in `install.rs`**: the file descriptor leaked by `into_raw_fd` in the `posix_fadvise` block
  (keep the `File` and pass `as_raw_fd`), and `statvfs("")` for a destination without a directory part (an empty
  parent means `.`). Also: `write_install_json` does not escape quotes or backslashes in paths (a name with a quote
  would break the record that uninstall reads): escaped now, with a test.
- `cargo fmt --check`, `cargo clippy -- -D warnings`, `cargo test` on the laptop; CI (Linux) is the top session's read.

## The launcher (`play-any.sh`, the one shared launcher; a private copy until his "tak")

From the shared 92c090c5 (with the lean session's three lines) and the install logic of `play-any-0409.sh`:
- exit 78 reads `action.txt`: install (background `bc5-mount install --verify` to `~/bc5-data/games/<TITLE_ID>`,
  progress file, the menu again at once; the title id from `bc5-mount inspect`), uninstall (`bc5-mount uninstall`,
  the result for the menu's status line);
- a folder with a record starts through its title's script: the second title through `play-pkg.sh` with
  `BC5_GAME_DIR`, ASTRO BOT and other titles through `play-astro.sh` with a directory (a small addition there:
  `BC5_GAME_DIR` instead of a mount);
- `.ffpfsc` and `.pkg` open as today; `installed.txt` is written from the records for the Recent marks.
- Tests on stand-ins (a fake emulator returning exit codes in turn, a fake `bc5-mount`), extending exp 0409's 8:
  open each format, installed start for both title kinds, install, uninstall (allowed and refused), a missing image,
  the lean session's path with `BC5_LEAN=1`. The old launcher is kept as `.before`; `play-any-0409.sh` is then not
  needed.

## Rounds

One compile: `hostMenu.cpp` only, on the private tree of build W (both builds). bc5-mount is built on the laptop and
once on the box (its binary goes next to the private launcher). Acceptance on the box: the menu in both builds; the
second title from "Installed games" (start only, to the title screen); ASTRO BOT from its `.ffpfsc`; one install and
one uninstall of a SYNTHETIC image (a small `.ffpfsc` made by the test fixtures, installed under a test games root),
never of the second title's folder; the lean session with `BC5_LEAN=1`. Then his "tak" for the shared launcher, the
shared builds and the two shortcuts.
