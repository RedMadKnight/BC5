# 0386 — The fight test with the job-arena fix on and off, on the merged build

**Question.** On the merged shared build, does the fix still stop F454's crash, and does the crash still repeat without it? The maintainer asked for this after the merge: "chcę => sprawdź po scaleniu wszystkich aktualnie testowanych zmianach".

**Status (2026-10-31).** Finished: 18:20–18:39 CET, verdict Ambiguous by the rule. The maintainer played during the series, so it is no clean scripted result. See Result.

## Setup

- Binary: the shared normal build, md5 `78f251729b06001d67d642ff06773758`, from `fab8660`. No new code.
- RT on in every run. Launcher `play-pkg.sh` 55531ab6 through a private derived copy, `bc5-run.env` cb8ad5fc.
- The only difference between arms: `KYTY_BC5_JOB_ARENA_FIX=1` or `0` in the emulator's environment. Both the environment dump and the title's own log line `job-arena fix ON|OFF for PPSA03671` must show it.
- Route: F464's, unchanged. Exp 0358's save copy `saves-live-47aefd45`, copied into the private `exp0386/run/wd`; `exp0360/fight1450-menu.cmd`; the gameplay part `exp0360/fight1450-play.cmd` appended on run0360.sh's journal gate.
- Order: ON, OFF, ON, OFF, ON, OFF, tags J1N J1F J2N J2F J3N J3F, 180 s each.

## Rule, fixed before the runs

- **Confirmed:** all 3 ON runs reach 180 s with no crash, and at least 2 of 3 OFF runs end with an access violation reading 0xc at eboot+0x3d7eca0 (history: 8 of 9).
- **Regression:** a crash at that site with the fix ON. The series stops; no analysis on the box.
- **Ambiguous:** an ON crash elsewhere, or 0 or 1 OFF crashes at the site. No conclusion about the fix. An ON crash elsewhere may also touch the 22:52 crash (eboot+0x3a05f35); that is not assumed.
- A run that does not reach the Continue load and gameplay does not count. It gets one replacement in the whole series (tag with R).

"At the site" means the log has `Access violation: Read [000000000000000c]` and either `off=0000000003d7eca0, module=eboot.bin` or `kyty_exception_handler: 0000000903d7eca0`. `check0386.py` decides each run: NO_CRASH, CRASH_TARGET, CRASH_OTHER, NOT_ROUTED, INVALID or KERNEL. NO_CRASH also needs every `d19gates.py` gate.

## Stops

Any of these ends the series with no retry: a kernel amdgpu line, a GPU reset, a devcoredump; a foreign lock, a foreign emulator, a running build or compression job; launcher, binary or another pinned input off its pin; `/var/home` at 80 %; INVALID; a classifier refusal.

## Pins

All measured on 2026-10-31 by the reads of REVIEW-PORTS-30 and 31, with nothing left as FILL. `ROUTE_SAVES` is 9347496fbaf30f25, the copy `exp0358/saves-live-47aefd45` summed in C from inside it. The same read gave exp 0358's 47aefd4567e6d346 from the same files in pl_PL.UTF-8 with the names rewritten to `PPSA03671/`, so this is that copy; a sum depends on its locale and its path form.

## Commands, in order

Series, one command, on the laptop, from this directory. It calls `go0386.sh` once per run:

```bash
bash series0386.sh
```

One run alone: `bash go0386.sh <tag> <on|off> <deadline epoch>`.

For each run `go0386.sh` does: claim over stdin; send the six files and compare sha256; start the kernel stream; start the run; poll. No step is retried.

## Time

180 s run, about 45 s around it, about 4 min per run, about 24 min in all. The series deadline is 35 min and is enforced: no run starts with under 430 s left, each run has a box-side limit that ends 60 s before the deadline, and the runner a cap of 280 s under it. The kernel stream ends when the run's lock line goes.

## Lock and ownership

- `box0386.sh claim` uses d19box.sh's claim: the line appears by a hard link, which cannot replace an existing lock. A foreign line is never overwritten. One token per run, no second claimant.
- The lock is checked before the launch and at every poll. A lost lock stops the run; a foreign line stays.
- Only processes with this run's token (`D19_OWNER`) in their environment are signalled. A foreign emulator stops the run and is left alone.
- The run frees only its own lock, on every exit. If its processes do not end, the lock stays and says so.

## What REVIEW-PORTS-32 changed

- **Write roots.** `paths_safe` checks every directory this experiment writes before the first mkdir, and again after the claim, before the launch and at start. A link, a file, or a path that really lies elsewhere stops the run before anything is written. The wd's own read-only asset links are not write targets.
- **Settings.** `play-pkg.sh` reads `bc5-pkg.env` after the private exports, so that file could undo them. The derived launcher now sources `prestart0386.sh` after that load and before every emulator start, the F2 restart too. It compares the private paths, the arm, the guards, the binary, log, arguments and HOME with `run/prestart.want`, requires this run's exact lock line, and refuses every forbidden name. A mismatch exits 97 with no emulator started. The manifest after the launch stays as the full check of every other name: an unknown option in `bc5-pkg.env` that is not on these lists is only caught there.
- **Common gates.** All `d19gates.py` gates apply to every class. Only what an intended crash or an unrouted run cannot show is left out: the runner's status for that outcome, the cap and duration, the crash text, progress, flips and the second fdinfo read. A crash with a failed kernel or devcoredump read (`-reads.txt`), a TIMEOUT, a new or forbidden stub, or a missing file is INVALID and stops the series.
- **Clean release.** `lock released` is written only after no process of the token remains, the queue line reads back and the exact line is gone. `go0386.sh` also reads the lock back. Anything else keeps the lock where needed, says so, and stops.
- **Kernel stream.** It now runs for the whole run, not under the 60 s ssh cap, and ends with the lock. The box's own dmesg read at every poll and at the end decides; the laptop copy is for a machine-down. A dropped stream is not noticed by the run. That is deliberate.
- **Disk.** Read at every poll; 80 % or an unreadable value stops the run. Not a hard cap: between 5 s polls the journal can still grow, by far less than the free 20 %.
- **Deadline.** 35 min is the end of everything. The outer limit ends 60 s before it, its hard kill included; a run needs 430 s left and keeps 150 s for its own kill, reap, check and release; the laptop stops polling at deadline minus 60 s.

## Writes

`~/bc5-work/exp0386` (scripts, private wd, evidence), `~/bc5-data/captures/play-*` (the launcher's journal), BOX-LOCK and BOX-QUEUE. `play-pkg-mount.log` stays shared, as in the launcher (known, not changed). Nothing else shared. Runs use the private copy of the named snapshot `saves-live-47aefd45`; live saves are not a gate (the maintainer, 2026-10-31). The private saves are cleared only inside `exp0386`, after a containment check.

## Recovery

- ssh lost during a run: the box finishes by itself and frees its lock. `go0386.sh` exits 3 and prints the read and the release.
- `box0386.sh` killed outright (no trap ran): `ssh bc250 'bash -s -- release <token>' < box0386.sh` stops this token's processes and frees only its lock. The lock line holds the token.
- Failed runs keep all evidence. Nothing is deleted.

## Tests

`bash test0386.sh`: the real scripts on a stand-in tree under a `d19-test-` path, with the pinned launcher text. Stand-ins replace ssh, scp, /proc, the kernel log, pgrep and setsid. `bash test_prestart.sh`: the real derivation, settings load, start checks and restart loop on the pinned launcher text, and the real claim against Windows junctions, with no HOME or PATH change. `bash test_route.sh`: the route sum. Not shown by them: anything on the box, the real `own_pids` over /proc, `setsid`, and a symlink BOX-LOCK or wd on Windows.

Last full run: 76 of 78. Both failures came on a loaded laptop and passed when run again alone: one `go0386.sh` over the test's 300 s limit, one INVALID from the stand-in log's old mtime. That log is now touched while the stand-in runs; the full set was not repeated after this.

## Result

Series 2026-10-31 18:20–18:39 CET, tags K1N … K3F (the J tags were lost to a stop on the `input.cfg` pin and to tag reuse), K4N afterwards. `raw-series.out`, `raw-k4n.out`.

| Arm | Run | Class |
|---|---|---|
| ON | K1N | NO_CRASH, 180 s |
| ON | K2N | NO_CRASH, 180 s |
| ON | K3N | NOT_ROUTED |
| ON | K4N | NOT_ROUTED (a timing budget under 430 s) |
| OFF | K1F | CRASH_TARGET, eboot+0x3d7eca0 |
| OFF | K2F | NOT_ROUTED |
| OFF | K2FR | CRASH_TARGET |
| OFF | K3F | CRASH_TARGET |

The checker's line: on 2 of 3 without a crash, off 3 of 3 crashed at the site, `RULE AMBIGUOUS`. The rule needs 3 of 3 ON runs through.

**The input was mixed.** The maintainer told us afterwards: "Jakby co, to pomagałem/grałem w teście walki. Za każdym razem oprócz jednego - gra się wywaliła." He also could not tell the 180 s stop from a crash on screen: "Nie wiem gdzie był crash a gdzie zamknięcie." The classes above come from the logs. His pad input ran over the scripted route, so which runs it touched is not known, and it may be why two ON runs and K2F were not routed.

## Verdict

Ambiguous by the rule fixed before the runs: no conclusion about the fix from this series. The ON runs showed no crash at the site where they were routed, and OFF crashed at the site in each routed run, which agrees with the fix doing its job but does not prove it. `JobArenaFix` was turned off on the maintainer's word for his play ("Job arena fix wyłącz"), not because of this series. The clean scripted measure with no person on the pad is exp 0388 (F792: 9 of 9 crashes without the spin).
