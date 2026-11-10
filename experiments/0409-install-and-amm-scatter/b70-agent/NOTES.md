# BC5 Task 2: install command and launcher

## What changed

### Part A: `bc5-mount install` (committed separately)
- New `install <image> <dest>` subcommand in `task2/tools/bc5-mount`
- Walks image file tree, streams files (1 MiB buffer) to `<dest>`
- Atomic writes via `<dest>.bc5part` → rename (per-file, not `.partial` which replaces extension)
- Refuses if dest exists (exit 2), unless `--resume`
- `--verify` compares sha256 of each written file re-read from disk (with POSIX_FADV_DONTNEED after fsync)
- Progress on stderr every 5s
- `posix_fadvise(POSIX_FADV_DONTNEED)` after fsync
- 6 new tests, all 31 tests pass
- **Important**: `.bc5-install.json` is written LAST (by main.rs, after all files are written and verified). The launcher treats a directory without `.bc5-install.json` as not installed, so a partial install (failed mid-way) is safely ignored.

### Part B: `play-any.sh` prefers installed games (this commit)
- `play-any.sh` now checks for `~/bc5-data/games/<TITLE_ID>/.bc5-install.json`
- If installed: runs with `BC5_GAME_DIR=<dir>` (no mount, no RAM cache)
- If not installed: mounts as before (FUSE, block cache)
- TITLE_ID extracted from `bc5-mount inspect` output (`title id:` line)
- `BC5_DRY=1` prints what would be run without executing
- Menu writes `installed.txt` (one path per line) for the host menu to read
- `list_installed_games` lists installed games (TITLE_ID + path)
- `installed_game_dir` returns the installed directory or empty string

### Part C: "Install game..." in the emulator's menu (not yet done)
- Design: host exits with code 78 + choice.txt, launcher does install
- `play-any.sh` on code 78: run `bc5-mount install --verify`
- Progress via `kdialog --progressbar` (KDE) or log file fallback
- `mkmenu.py` edit script for `hostMenu.cpp`
- Tests: `BC5_DRY=1` with fake files

## How to run install

```bash
# Install a game image
bc5-mount install /path/to/game.ffpfsc ~/bc5-data/games/PPSA21567 --verify

# Resume a failed install
bc5-mount install /path/to/game.ffpfsc ~/bc5-data/games/PPSA21567 --resume

# Install a package
bc5-mount install /path/to/game.pkg ~/bc5-data/games/PPSA21567 --verify
```

## How to run play-any.sh

```bash
# Run from installed game (if .bc5-install.json exists)
play-any.sh /path/to/game.ffpfsc

# Dry-run (print what would be run)
BC5_DRY=1 play-any.sh /path/to/game.ffpfsc

# Run from directory (no install needed)
BC5_GAME_DIR=~/bc5-data/games/PPSA21567 play-any.sh
```

## Open risks

1. **TITLE_ID extraction**: `bc5-mount inspect` output parsing is fragile. If the output format changes, TITLE_ID extraction breaks. Consider adding a `--title-id` flag to `bc5-mount inspect`.
2. **Concurrent installs**: If two instances of `play-any.sh` try to install the same game, they could conflict. Consider adding a lock file.
3. **Partial installs**: If an install fails mid-way, the destination directory may contain partial files. The `.partial` → rename pattern handles individual files, but the directory itself may be in an inconsistent state. Consider adding a `.bc5-install-partial` marker directory.
4. **Free space check**: The `statvfs` call may fail on some filesystems. The current fallback assumes enough space, which could lead to disk-full errors during install.
5. **BC5_DRY=1**: The dry-run mode only prints what would be run. It does not validate that the image exists or that the destination is writable.
