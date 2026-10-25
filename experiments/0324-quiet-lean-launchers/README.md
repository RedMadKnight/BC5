# 0324 — The lean shortcut writes nothing: logs only with BC5_LOGS=1

**Question.** The maintainer, 2026-10-25, before a gameplay recording on the lean build: "pozbądź się wszystkich
dzienników i wpisów dodatkowych i skryptów obok, abym na wersji lean grał naprawdę bez żadnego logowania, aby
sprawdzić prawdziwą wydajność emulatora (żadnych zrzutów - nic)", then "uwzględnij też skrypty na maszynie, aby nic
nie pisały - możesz zrobić im włączenie na parametr". What does the lean path still write, and can all of it be
switched off by default, with one switch to bring it back?

**Setup.** Offline, on copies of the box's scripts (2026-10-25 ~19:50: `play-any.sh` d89ac237, `play-pkg.sh` 7d14f7e5
after exp 0323, `play-astro.sh` e78af6cd, `compress-old-captures.sh` 9cecc62e).

What the lean path already leaves out (exp 0177): the lean binary has no tracing, journal, counters, input recorder
or samplers, and the launchers unset `KYTY_BC5_INPUT_RECORD` and `PLAY_CAPTURE`, skip the timeout probe, and set no
`BC5_GC_DUMP_DIR`.

What it still wrote, per run:
- the play log (`play-pkg-lean-last.log`, `play-lean-last.log`, `play-menu-lean-last.log`): a settings header, the
  emulator's stdout/stderr (little with `--printf-direction Silent`), the pad-volume lines, the restart and exit
  lines;
- `play-dir-last.log` for a directory game;
- the package and image mount logs (`play-pkg-mount.log`, `play-mount.log`): bc5-mount's output and the unmount
  failures;
- `compress-old-captures.sh` (the nightly timer): one "box busy, skipped" line when it fires during play.

**The change** (`quiet0324.pl`, anchored literal edits, backups `*.before-0324`):
- With `BC5_LEAN=1`, every one of those logs goes to `/dev/null` unless `BC5_LOGS=1`.
- The normal shortcut is unchanged.
- The compression timer writes nothing while the box is busy.

Not touched:
- the maintainer's saves, the menu's `choice.txt` and the input configuration (the emulator's own files);
- GPU coredumps: the maintainer's udev rule copies one only when the GPU hangs, so it costs nothing during play.

Dry run on the copies:
- all four files parse;
- the log targets are as intended in the three modes (normal; lean; lean + `BC5_LOGS=1`);
- a second run is refused.

**Result (applied 2026-10-25 ~20:30, after exp 0323's verification; the box free; backups in
`~/bc5-work/exp0324/integration/*.before-0324`).**
- md5s, the same as the dry run's:
  - `play-any.sh` d89ac237 → 4da8ce07;
  - `play-pkg.sh` 7d14f7e5 → c0357628;
  - `play-astro.sh` e78af6cd → 48238ccd;
  - `compress-old-captures.sh` 9cecc62e → 069eafeb.
- All four parse. Each launcher names its old log path only in the variable that holds it.
- The desktop shortcut "BC5 emulator (RT, diagnostyka 0302)" (exp 0302's diagnostics build) was moved to
  `~/bc5-work/trash-20261025/` (the maintainer's cleanup approval). "BC5 emulator" and "BC5 emulator (lean)" remain.
- Not run with an emulator here: the edit changes only where the logs go. The lean start itself was checked by
  exp 0323 just before.

**Verdict.** With the lean shortcut nothing is logged. `BC5_LEAN=1 BC5_LOGS=1` (e.g. `distrobox enter ubuntu -- env
BC5_LEAN=1 BC5_LOGS=1 ~/bc5-work/play-any.sh`) brings the lean logs back. The normal shortcut logs as before.
