# 0409 — game install (bc5-mount install, menu), the AMM scatter fix, and the B70 coding agent

Number claimed on 2026-11-09 by the top session: the repo (branch `exp/0409-install-amm-scatter`, worktree `bc5-0409`) and the box
(`~/bc5-work/exp0409`). The lock line was taken and released the same day; no emulator ran.

## Question

1. Can the host give the second title a fixed AMM budget lower than 13,824 MiB without dying on "AMM virtual-memory unmap is
   unsupported"? (exp 0401, 11-03 18:14: the AMM auto pool held 212 MiB free but in pieces, and a 64 MiB auto map needs one
   contiguous range.)
2. Can games be installed (unpacked into a plain directory) instead of mounted with bc5-mount, from the emulator's menu?

## What was built, and by whom

The code was written by a local model: Qwen3.6-35B-A3B through Qwen Code on the B70 server (`b70-agent/`: the task files
`TASK.md`, `TASK2.md` and six review rounds `REVIEW1.md`–`REVIEW6.md`). The top session reviewed each round and made the last
fixes itself, because the B70 network was about to go away.

| Part | Files | Where it ended |
|---|---|---|
| AMM scatter (`KYTY_BC5_AMM_SCATTER` = unset/empty/`0` off, `journal`, `rescue`, `first`) | `b70-agent/work/mkpool0401.py` (edit script), `pool0401_impl.inc` (the helpers), `pool0401.cpp` (CPU test) | patched `libAmpr.cpp` 41d5da78 from e8's x-amm unit 0a1762f6; test passes |
| `bc5-mount install` / `adopt` | `tools/bc5-mount/src/install.rs`, `main.rs`, `lib.rs`, `tests/install.rs` | release build c7904e99; `cargo test` 68 + 6 + 15 + 10 pass on the box |
| Menu: File > Install game... (exit code 78) | `b70-agent/host/mkmenu.py` (edit script for `hostMenu.cpp`) | patched `hostMenu.cpp` 53c61393 from d3810c9f |
| Launcher that prefers installed games | `b70-agent/play-any.sh`, `play-pkg.sh`, `play-astro.sh` (the title scripts honour `BC5_GAME_DIR`) | `tests/play-any-test.sh` 8 of 8 on B70 |

The binary is e8's (dc7fb4e0) with two more private units, linked by `box/link0409.py`: **092cd87a24696f28d28437cd5023ca0b**
(`~/bc5-work/exp0409/bin/kyty_emulator`). Every other private object is e8's. The shared objects and archive were only read.

## Defects the review found (all fixed unless marked)

- Round 1: the scattered map put every piece at one address; the last piece was not trimmed; gathered pieces stayed on the free
  list; the borrow asked for the whole amount every time; the test checked a copy of the logic. Fixed in rounds 2–4.
- Round 4: the edit script took the old script's output as its input; `journal` mode scattered like `rescue`. Fixed.
- Round 5: after a successful scattered map the code fell through to the original map path (a second map of the same VA);
  `getenv` on every map. Fixed.
- Rounds 6 and C: TITLE_ID taken from the file name (game.pkg → "game"); `[installed]` on every recent entry; a bare
  `msgbox` instead of a progress bar; the menu item enabled while a game ran; `action.txt` left behind; `process::exit(2)` in a
  library function; `.partial` names that replaced the extension; verify hashing memory instead of the disk. Fixed by the agent.
- Top session, 11-09: `installed.txt` was written as a bare directory and appended to; now one function regenerates it as
  `image<TAB>dir` per game. The progress box is now closed on success, with a pop-up. The hook definitions did not compile
  on the box (`KernelUnmapVirtualRange` does not exist: it is `KernelMunmap(uint64_t, size_t)`; `bc5_watch_surface` was used
  before its declaration; `KERNEL_ERROR_EAGAIN` needs `LibKernel::`). Fixed in the HOOKS block of `mkpool0401.py`
  (original kept on the box as `mkpool0401.py.orig`).
- Not done: a real progress bar (`kdialog --progressbar` fed from install's lines): the agent used a `msgbox`. The
  `<dest>.partial` directory for the whole tree was not done either: an unfinished install is recognised by the missing
  `.bc5-install.json`, which is written last (review item 1, second option).

## State on the box

- Three new shortcuts beside the old ones: `BC5 emulator (e10 unpacked)`, `(e10 mem 12800)` and `(e10 menu)`. The first two set
  `KYTY_BC5_AMM_SCATTER=rescue` and use `play-pkg-0409.sh`; the second also uses e8's `run-mem12800.env`. The menu shortcut uses
  `play-any-0409.sh`. All three carry the e8 shortcut's words (no zero skip, quiet journal, no catchers).
- The second title's directory `~/bc5-data/games/PPSA03671` (309 files, 196,702,588,158 bytes, unpacked by hand on 11-08) got
  its install record by `bc5-mount adopt` against the NAS copy of the package: file count and sizes match; the bytes on disk
  were not hashed (no `--verify`). Its top directory had to be made user-writable (`chmod u+w`) to take the record.
- Old shortcuts that pointed at the removed package were moved to `~/bc5-work/trash-20261108/pulpit` on 11-08.

## Not verified

- **Nothing was started.** The emulator was linked, not run. The scatter path has only the CPU test (`pool0401`: 8 groups, all
  PASS, plus the byte-equality check of the inlined helpers) and has never run inside the emulator. `rescue` acts only where the
  original returned EAGAIN, which was fatal, so it cannot make that case worse; `first` is untested and is not set anywhere.
- The menu item, the exit code 78 and the launcher's install branch have not been used with a real image.
- The kit's gate programs and stand-in tests were not run for this binary (the link driver skips them).
- The lower memory budgets (11,776 and 12,288 MiB) died at startup in the title's TLS setup (11-06); this change does not touch
  that. 12,800 MiB is the value to try first.

## Next

Play the three shortcuts with the box idle and read `~/bc5-work/exp0409/play-last.log` and the journal: look for
`[bc5] exp 0401 pool:` lines and for the old "AMM virtual-memory unmap" fatal at 12,800 MiB.

## Verdict

None written (noted 2026-11-13). This README ends at its plan ("Next"). The runs made on this build are recorded elsewhere: exp 0401 (the 12,800 MiB tally: 5 of 5 runs died at 159-195 s without `KYTY_BC5_AMM_SCATTER`; with `rescue` 4 of 7 reached G+600 and 3 exited 133) and exp 0412 sections 57 and 59, which read them; see `docs/HANDOFF.md` F826.
