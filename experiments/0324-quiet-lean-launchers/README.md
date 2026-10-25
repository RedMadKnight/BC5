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

**Result.** Pending: applied on the box after exp 0323's verification (it edits `play-pkg.sh` again).
