# Review round 6 (Claude, top session): parts A and B. Do this after part C.

Results:
- AMM (review 5): accepted for a box build.
- Part A: the tests pass (68 + 6 + 15 + 10).
- Part B: the tests pass (8/8, run from ~/bc5-agent).

Fix:
1. **A: install writes straight into <dest>.** The spec asked for `<dest>.partial` with a rename at the end. Today a
   failed run leaves a half-filled <dest> that looks installed apart from the json. Either write the whole tree under
   `<dest>.partial` and rename it at the end, or make sure `.bc5-install.json` is written LAST and the launcher
   treats a dir without it as not installed. B already checks for the json, so the second way is enough. Then
   document it in NOTES.md.
2. **A: --verify hashes the bytes in memory, not the files on disk.** After writing, re-read each written file from
   disk (with POSIX_FADV_DONTNEED afterwards) and compare its sha256 with the image's.
3. **A: per-file temp names use with_extension("partial").** That replaces the extension (a.bin → a.partial). Use
   `<name>.bc5part` (append, do not replace).
4. **A: std::process::exit(2) inside the library function.** Return an error type instead, and map it to exit code 2
   in main.rs.
5. **B: the title scripts do not honour BC5_GAME_DIR.** play-any.sh passes it to ~/bc5-work/play-pkg.sh and
   play-astro.sh, but only the 0401 copy (task2/play-pkg-0401-dir.sh) handles it. Write the same three small changes
   into play-pkg.sh and play-astro.sh as edit scripts (mkdirlaunch.py): skip the package check, use the dir as the
   game root, skip mount and unmount. The two files are in task2/ (copies from the box).
6. **B: for .ffpfsc games the system-module pack comes from `$mnt/fakelib`.** With an installed game it must be
   `$inst_dir/fakelib`.
7. **Adoption: the second title is already unpacked** in ~/bc5-data/games/PPSA03671, by hand, with no
   .bc5-install.json. Add `bc5-mount install --adopt <image> <dir>`: verify an existing tree against the image
   (sizes, plus sha256 with --verify) and write the json, without copying.

## Part C (added after part C was committed, 9a20b0b)

What works: mkmenu.py edits the original file, the rerun exits 1, and the menu item and exit code 78 are there.

Fix:
8. **TITLE_ID from the file name is wrong.** For game.pkg it gives "game", so the game installs to
   ~/bc5-data/games/game and part B never finds it, because B looks under the TITLE_ID. Take the title id from
   `bc5-mount inspect <image>` (the "title id:" line), as part B does. Put that lookup in ONE shell function and use it
   from both B and C.
9. **"[installed]" marks every recent entry.** It is true whenever installed.txt merely exists, and it is checked
   every frame. Read installed.txt once, when the menu opens (or cache it with its mtime), and mark a recent entry
   only if ITS image path is listed.
10. **installed.txt is overwritten with a single line, and with the dest dir.** Make it one line per installed game,
    `<image path>\t<install dir>`, always regenerated in full by list_installed_games (from the .bc5-install.json
    files, whose "image" field holds the image path). Do not append or overwrite by hand.
11. **No progress window.** The spec asked for `kdialog --progressbar`, fed from install's progress lines (the
    "files done/total, GiB" lines on stderr), with `qdbus` to update it. Today the user sees nothing for ~40 min.
    Add it, and on failure show `kdialog --error` with the last 20 log lines. When kdialog is missing (as in tests),
    fall back to the log only.
12. **The item is enabled while a game is running.** Enable "Install game..." only on the launcher page, like
    Open/Close (use the same `launcher` flag the other items use), and only when MenuDir() is set.
13. **action.txt stays behind.** Delete it after reading it in the code-78 branch.
14. Add launcher tests for 8, 10 and 13 to task2/tests (BC5_DRY=1, a fake bc5-mount that prints a "title id:" line).
