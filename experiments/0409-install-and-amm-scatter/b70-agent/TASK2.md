# Task 2: an "install" command for bc5-mount, and a launcher that prefers installed games

Do this AFTER Task 1 (REVIEW5.md) is committed. Work only in ~/bc5-agent/task2. No network: build with
`cargo build --offline` (all crates are already fetched). No sudo. No game files: test only with the synthetic
fixtures the crate already generates (src/fixture, src/bin/bc5-fixture.rs).

## Background
`bc5-mount` (Rust, task2/tools/bc5-mount) reads PS5 packages (.pkg) and .ffpfsc images: inspect, verify, ls, cat, and
mount (FUSE). Today a game is played through a FUSE mount, which costs RAM (a block cache) and CPU (Kraken decode on
every read). We now "install" instead: unpack once into a plain directory and point the emulator at it.

## Part A: `bc5-mount install <image> <dest dir>`
- Walk the image's file tree and write every file under <dest dir> with the same relative paths, sizes and
  directory structure as `mount` shows (including sce_sys for packages).
- Stream each file: no whole-file buffering. Read large blocks.
- Write to `<dest>.partial` first. When every file is written and checked, rename it to `<dest>`. A refused or
  failed run leaves no half-finished `<dest>`.
- Refuse if `<dest>` already exists (exit 2), unless `--resume` is given. Resume skips files whose size already
  matches and redoes the rest.
- Check free space before starting: sum of the logical file sizes plus 1 GiB. Refuse with a clear message if short.
- `--verify`: after writing, compare each written file's sha256 with the image's (reuse what `verify` computes).
  Write `<dest>/.bc5-install.json` with the image path, image size, file count, total bytes, sha256 list and date.
- Progress on stderr every 5 s: files done/total, GiB done/total, MB/s.
- Use posix_fadvise(POSIX_FADV_SEQUENTIAL) on the image while reading, and POSIX_FADV_DONTNEED on written ranges
  after fsync of each file, so the install does not fill the page cache.
- Tests (cargo test --offline): build a fixture image with nested dirs, empty files, one large file (> 64 MiB,
  sparse is fine) and compressed and stored blocks. Install it, compare the trees and contents with `cat`, then test
  the refuse, resume and verify paths.

## Part B: `play-any.sh` prefers an installed game
- task2/play-any.sh is today's launcher. It takes a .pkg (second title, through play-pkg.sh) or an .ffpfsc (ASTRO
  BOT, through play-astro.sh).
- task2/play-pkg-0401-dir.sh shows how the second title already runs from a directory: BC5_GAME_DIR=<dir> skips the
  mount.
- Change play-any.sh so that, for a chosen image, if `~/bc5-data/games/<TITLE_ID>/.bc5-install.json` exists (TITLE_ID
  from `bc5-mount inspect`), it runs from that directory (BC5_GAME_DIR=...) and otherwise mounts as today.
- The game picker should also list installed games with no image present.
- Keep a dry-run mode, `BC5_DRY=1`, that only prints what it would run. Test it with fake files (bash tests in
  task2/tests/).

## Deliverables
- The code changes in task2/tools/bc5-mount, with passing `cargo test --offline -p bc5-mount`.
- task2/play-any.sh changed, plus task2/tests/play-any-test.sh passing.
- task2/NOTES.md: what changed, how to run install, and the open risks.
- Commit after each part passes.

## Part C: "Install game..." in the emulator's menu (the maintainer's wish)
Design rule (ADR 0011): the host NEVER mounts or installs itself. Menu actions end the emulator with an exit code
plus a file, and the launcher (play-any.sh) does the work, then restarts the emulator with --menu.
- task2/host/hostMenu.cpp (md5 d3810c9f, from the box tree ~/src/KytyPlus) is the ImGui menu bar. Today it uses
  EXIT_CODE_OPEN 76 (path in $KYTY_BC5_MENU_DIR/choice.txt) and EXIT_CODE_CLOSE 77.
- Add to the File menu, after "Open package (.pkg)...":
  - "Install game..." opens the same file browser (filter .pkg and .ffpfsc). On selection, write the path to
    choice.txt, write "install" to $KYTY_BC5_MENU_DIR/action.txt, and exit with a new code 78
    (EXIT_CODE_INSTALL). Enable it only on the launcher page (no game running), like the other session items.
  - Under "Recent", mark entries that are installed with " [installed]" (the launcher writes
    $KYTY_BC5_MENU_DIR/installed.txt, one path per line).
- play-any.sh: on code 78, run `bc5-mount install --verify <image> ~/bc5-data/games/<TITLE_ID>` with a visible
  progress window. Use `kdialog --progressbar` (KDE is on the box) fed from install's progress lines; fall back to a
  log file. Then write installed.txt and start --menu again. On failure, show a kdialog error with the last log lines.
- Deliver the change as an edit script, task2/host/mkmenu.py <in hostMenu.cpp> <out dir>, in the same style as
  work/mkpool0401.py: each anchor matched exactly once, the rerun refused with exit 1.
- Check that the edited file at least compiles with `g++ -std=c++20 -fsyntax-only`. Missing ImGui/KytyPlus headers
  are acceptable; report the first real errors.
- Test the play-any.sh code-78 path with BC5_DRY=1 and fake files.
- Commit when it passes.
