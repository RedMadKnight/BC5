# Test build 2: plan and pins

The maintainer's words, by way of the top session: "Build testowy: => wszystkie zmiany na raz => do moich testów". A private build
for his testing. Status: prepared on the laptop. **Nothing has run on the box.** Codex reviews before the box step, and it needs a slot and
his go in this session's chat.

## The rebased candidate on fab8660 (REVIEW-PORTS-26, not yet run)

Codex's review decision through the top session: an isolated local integration of bbe9921 on main fab8660, branch `exp/0381-tb2-rebased`, CPU tests only. It adds no go for the box. The shared builds are normal 78f25172, lean 7b246487, archive 3292bdaf (the top session's values).

**What the new base changes for the private unit** (`abi0381tb2.py`, reads git only). Backend headers the unit reaches: `acb_restore.hpp` and `zero_skip.hpp` are the private copies and equal main's, `full_state.hpp` gains only `#include "bc5/env_flag.hpp"`, the others are unchanged, and it does not reach `indirect_check.hpp`, whose `Stats` changed. So the layouts are the ones test build 1 linked. Only the box's link proves the symbols.
The tree unit moved from e7cc2f60 to 29b3d8c6 by four lines, all F767, and those lines are the one thing main has that the private unit lacks: it reads `PIECES_NO_CLEAR`, `INDEX_BASE_DUP` and `NO_CARRY` by presence, so `=0` would turn them on. `PIECES_NO_CLEAR` is forced to 1 anyway, and the launchers now reset the other two, never accepted, so the old reading cannot be reached. The unit stays c743bb76, the text test build 1 ran.
The archive must not hold `BC5_DIRECT_REBASE_DISPATCH`: the build now stops if it does. The launcher pins change with the switches block.

**The saves (his word, 2026-10-31, by way of the top session): they need no protection, they are only copied for repeatable tests.** So nothing compares the live saves any more, before or after a run:
- `snapshot0381tb2.sh` makes one named snapshot, `exp0381/saves-sample/PPSA03671`, from the live saves once, under the series' lock line, with no emulator, and renames only a whole copy. If it is there it stays, and the sample only changes by renaming it aside.
- Each start resets its private copy from that snapshot, proves the copy equals it and writes the sample's sum, in the C locale, into `<tag>-start.txt`. It does not read the live saves. It still refuses a link in the snapshot, before it deletes anything.

**Filled at run time:** `PIN_PLAY_PKG` and `PIN_LIBC` (`~/bc5-work/play-pkg.sh`, `~/src/KytyPlus/src/libs/libC.cpp`) come from the cycle's own read into `<out-dir>/pins-read.env`, with no commit, and the build's compare still proves every other pin against the box.

**The lock (REVIEW-PORTS-28).** `lock0381tb2.inc` is D19's claim (a hard link that cannot replace a lock, reviewed in REVIEW-PORTS-21). One token, kept in `<out-dir>/token`, gives one exact line, `top exp 0381 | test build 2 | token <t>`, from the claim to the release. Nothing rewrites it. The claim comes before anything on the box moves, and the line is checked before the rename, the extraction, each build step, the snapshot's writes, each write of the starter, each emulator start and each queue line. A foreign line, alone or next to ours, stops the step and is never touched. An empty lock is free to claim and is never ownership. Only our exact line is cleared, in success, failure and rollback alike.

**One cycle, on one slot (the process agreed by the top session and Codex, 2026-10-31). Nothing here has run.** The owner is this session: pin read, build, snapshot, smoke, recovery and report, with no go per step; Codex reviews afterwards. The top session gives the slot. The conditions are no human at the box, no game and an empty lock. One GPU job, RT on, private paths, no change to shared files, main or launchers. Any stop gives back only our line.

```bash
TB2_MAIN=fab8660 TB2_NP=fab8660 bash tb2run0381.sh all TS2 <out-dir> pins0381tb2r.env
```
About 10 minutes in all.
   - Pin read: under its own claim and release, md5s and the canonical home only, about 20 s. A file missing stops the cycle.
   - Build: claim, the tree crosses, CPU only, limit 900 s. A failure records itself and gives back the line.
   - Snapshot: only after a passed build, limit 300 s, under the same line.
   - Smoke: only after the snapshot, one start, cap 125 s, the laptop's backstop 140 s. The first kernel line (page fault, ring timeout on any ring, GPU reset) stops it. Pass and fail as below; the starter gives back the line.
   - On any stop `release` gives back the line if it is still ours. A lost line is reported, not cleared.

**Audio, exp 0372.** tb2 changes no audio code: `audio.cpp` and `pad_audio_route.hpp` come from the shared objects, and neither private unit touches them. The build still stops unless the shared tree holds 5 `exp 0372` lines and the header (`PIN_0372_LINES`); D19 reported 5 too. The software replug check (`s6n0372.sh` + `replug0372.sh`) is not part of this plan: both name exp 0372's binary, so running them on tb2 needs an adapted script and its own go. The physical check stays his: with tb2 running, pull and replug the DualSense, confirm the sound stays on the TV and the haptics on the pad, then the same with a DS4. D19's audio_ok is the executor's report and does not replace it.

**Backup.** Nothing shared is written. The live saves are read once, for the snapshot, and never written. `in-tb2` is renamed aside by date, under the line, at each build.

**Rollback**, part of the cycle:
```bash
bash tb2run0381.sh recover <out-dir>
```
`recover0381tb2.sh` renames only, to `*.rolledback-<stamp>`: `exp0381/tb2`, `backend-build-tb2`, `in-tb2` and the snapshot. It deletes nothing and signals nothing. It needs the series' exact line; an empty lock is claimed first under a new token, and any other line stops it. Before each rename it wants our line, no emulator, no ninja or cmake, no cap, and each target exactly itself under the canonical home, with no link and no mount inside. Live saves, `wd` and shared files are not on its list. A target it refuses stays, and that needs a read, not a looser check. There is no shortcut to remove; the top session asks him about one only after a pass. Test build 1 (4c686b5b) stays. A hard hang recovers through the watchdog; a line left by a dead run is cleared only by `recover` or `release` with its token. `BOX-QUEUE` is a record and stays.

**Not shown by these tests:** the box's `ln`, `mv -T` and ssh, its compile and link, `readlink`, `find` and `-ef` on Bazzite, and anything at run time. The restore has run under the new archive's code nowhere; that is what the smoke is for.

## Decided since: the rebuilt shared base

The top session's answer: "all changes" means all of them, and he has chosen to merge NP/libc and rebuild the shared builds. So tb2 goes on the new
shared objects and archive, with the recorder, crash frames, `NO_CLEAR`, zero skip and the restore on top. It waits for the merge and the rebuild. **The
rest of this file is the fallback,** if the rebuild is refused; cap 125 s and backstop 140 s are accepted for both.

**What changes with the new base** (read from the repo, against 49f1116, the commit before main's backend moved; not built yet):

| | Fallback | Rebased |
|---|---|---|
| Shared objects, archive | 58c4a627, bb50b2e0 | **new, pins unfilled** (`pins0381tb2r.env`; the scripts refuse to run until they are filled from the rebuild) |
| Private units | four | **two**, as in test build 1: `bc5LleAgc.cpp` c743bb76 and `runtimeLinker.cpp` 5f2bc982 |
| `libC.cpp`, `libNpCppWebApi.cpp` | private, proved by the src tree | from the shared objects, proved by their md5 in the shared tree |

**Does the unit need adapting? By reading, no.** Its backend includes are `direct.hpp`, `full_state.hpp`, `zero_skip.hpp` and `acb_restore.hpp`. `direct.hpp` and
`full_state.hpp` are unchanged since that commit, main's `zero_skip.hpp` is r1's (782ca0e9), `acb_restore.hpp` is pinned, and the unit does not include
`indirect_check.hpp`, which did change. Only a compile proves this, and the build stops if it fails. A rebuild that touches `bc5LleAgc.cpp`'s tree unit does not
reach this unit, which comes from r1 + the restore: anything added to the host unit by the merge would be **missing** from tb2, so `PIN_TREE_UNIT` is
checked and a change there stops the build for a new look.

**What else the new base brings in.** The archive moves to main's backend: the restore's `final_value` no change, plus exp 0380's eight switches and the draw-args journal,
`BC5_DIRECT_GPU_CHECK_ZERO`, `FORCE_START_000`, `GPU_CHECK_YZ`, `REBASE_DISPATCH`, `ARGS_COPY`, `ARGS_WB`, `ARGS_FLUSH`, `ARGS_FLUSH_DRAWS` and `DRAW_ARGS_JOURNAL`. All are off
unless set, so **the code comes in and its behaviour does not, as far as reading shows.** r1's launcher unsets the first six; `ARGS_FLUSH`, `ARGS_FLUSH_DRAWS` and `DRAW_ARGS_JOURNAL`
it neither sets nor unsets. The archive's other changes (213 lines in `direct.cpp`, 164 in `indirect_check.cpp`) have run in exp 0380's private builds, but **not under the restore**,
and this is the first time they meet it.

**The maintainer's answer (2026-10-30, in this session):** refuted switches are not compiled; the others can be turned on and off. So:
- `BC5_DIRECT_REBASE_DISPATCH` (refuted by the 14:04 hang, F565) goes from the backend: branch `fix/drop-rebase`, which must reach main before the shared rebuild, or the rebuilt
  archive still holds it. The archive pin is read after the rebuild, so an archive without the removal would not stop the build: check `strings` for the name at the pin read.
- `ARGS_COPY`'s old flag-area slot, which hung in C1 and W1, stays in the source: it is not a switch, the runtime cannot reach it (`Device::open` turns the copy off when the low slot fails),
  and the copy's unit tests run through it.
- The other seven go through `tb2/switches.env`, read at every start (`switches0381tb2.inc`, `switches0381tb2.env`). All are commented out in the file as shipped, and a rebuild keeps his file.
- **Revised after Codex's REVIEW-PORTS-08 (HOLD).** The first loader added switches but cleared none, and r1's launcher does not unset `ARGS_FLUSH`, `ARGS_FLUSH_DRAWS` or `DRAW_ARGS_JOURNAL`: an inherited
  `ARGS_FLUSH=all` with the whole file commented stayed on while the log said none. Now, after the launcher's env file, all seven and `DRAW_ARGS_JOURNAL` are unset first, and only then is the file read.
  The file is read as data, never sourced or evaluated. A line counts only as a name with one of its documented values; any other line is ignored and logged by number. The last valid line for a name wins.
  The log's first line is built from the environment after the block, so it states the effective values. The restore, recorder and crash settings are not touched. The smoke launcher's input is `/dev/null`, so a smoke
  runs with all of them off. The build stops if anything after the block loads the env file or names a switch. Rollback: revert this revision and 2db9e86; nothing else depends on them.
- **Revised after Codex's REVIEW-PORTS-09 (HOLD).** A later `bc5-pkg.env` could undo the reset, so the block moves to right before the log, after both settings files, and `tb2_check` stops the start if the environment
  at the emulator's line is not what the log says. `BC5_DIRECT_REBASE_DISPATCH` joins the reset, since the fallback archive still holds it. The order is checked by counted anchors on the launcher as built, and the two launchers are pinned (values below).
  `raw/play-pkg-0380r1.sh` is the box's file, 299a2519, read by the top session after the maintainer's play; the anchors were written before that from a copy taken out of a session transcript, which was outside what was allowed and is deleted, and they were then checked
  against this file. `~/bc5-work/bc5-pkg.env` does not exist on the box today; the launcher reads it if it appears. The log's lines after the first still list the two files' raw contents, so a switch in them shows there although it is off: the first line is the effective state.
- **Revised after Codex's REVIEW-PORTS-11 (HOLD) and REVIEW-CLAUDE-02 §A.** r1's exports stand before the `bc5-pkg.env` loop, so that file could move the smoke's saves, config and learned file or turn the restore off, and the log's first line was r1's literal text.
  Now `force0381tb2.inc`, right after the loop and before the launcher's `mkdir`, sets the restore, crash frames, recorder, `NO_CLEAR` and the zero list again, in both launchers. In the smoke launcher it also sets its three private paths and seven RT guards
  (`COMPUTE_RING`, `CROSS_RING_WAITS`, `GPU_CHECK`, `GPU_CHECK_PRODUCT`, `SHADOW_LABELS`, `HOST_INDIRECT`, `SOFT_WAIT_MS`). `tb2_check`, before every start and restart, wants each of these exactly, the nine switches and the logged settings unchanged, and in the smoke the three paths and the working
  directory to be themselves, not links elsewhere (`KYTY_BC5_SAVEDATA_DIR` only covers `memory.dat`; other saves go under `_SaveData` in the working directory, so the directory counts). Otherwise the emulator does not start and the log says why. The log's first line now gives the
  switches, then the list's md5 and the settings read from the environment. **The player's launcher keeps r1's rule on purpose:** `bc5-pkg.env` may move its paths and guards, since it runs on the live saves; the log shows where they went. The restore, crash frames, recorder, `NO_CLEAR` and the zero list are not movable there either.
  Launcher pins: see the pins files. Runtime pins stay for the final D19 and a fresh read; `start0381tb2.sh`'s save pin 377a8d45 is older than the 2026-10-30 play and will stop the smoke.
- **Revised after Codex's REVIEW-PORTS-12 (HOLD).** The starter deleted and copied under `wd/_SaveData` before any check, and the launcher never looked at that tree: a junction there passed. `pathcheck0381tb2.inc` now walks every write target from the canonical home (the only alias allowed)
  and refuses a link at any part, a link anywhere in the trees, and a private path that is its live twin (`-ef`, for mounts and hard links). The starter runs it first, before the live-save pin, again right before `rm`, and after the copy, and checks the status of `rm` and both `cp`. The launcher runs it before its `mkdir` and in `tb2_check` before every start and restart.
  If `~/bc5-work` itself is a link on the box, the smoke stops there: that needs a read, not a looser check. `wd` itself is a directory of `setup0381j.sh`'s links to the title's files (read on the box, 2026-10-31, after the first cycle stopped there), so only its save directories must hold no link. The check is not atomic with the write that follows it. It needs the box's `readlink -f`, `find` and `-ef`, only exercised here in Git Bash. The save pin 377a8d45 stays stale and stops the starter after the first check.
- **His standing rule (2026-10-31, by way of the top session):** every candidate fix and catcher goes into one test build at once, each with an on/off switch, and only then is it tested. So `DRAW_ARGS_JOURNAL`, left out earlier because a long journal filled 38 GB in `on-3`, is now in the file, off, with that warning, and so are `DISPATCH_JOURNAL` and `CHAIN_BREAK_AT=<dwords>`, both already compiled in the unit. The smoke runs with all of them off.

**What this costs.** With the new base, a difference between 4c686b5b and tb2 is no longer only three small changes: the whole archive moves too. The fallback's list below stops being exact.
The smoke rule below stands unchanged for both. The difference list, the overlap and the pins are re-read after the rebuild.

## What goes in

`~/bc5-work/exp0381/tb2/bin/kyty_emulator`, linked from the shared objects (58c4a627) and the shared archive (bb50b2e0), with four private
units:

| Unit | Source | Pin |
|---|---|---|
| `bc5LleAgc.cpp` | r1's unit + the restore (`mkpatch0381.py`), the same text as test build 1; reproduced on the laptop | c743bb76 |
| its header `acb_restore.hpp` | main d6fa368: the `final_value` fix | d01f31c6 (test build 1: c8b4cddc) |
| `runtimeLinker.cpp` | r1's, crash frames | 5f2bc982 |
| `libC.cpp` | exp 0383's patch on f266548: PORT-LIBC | patch 00a296da, src tree 7fab373a |
| `libNpCppWebApi.cpp` | the same: PORT-NP | the same |

Launcher `tb2/play-pkg-0381tb2.sh`: r1's (299a2519) with its paths moved and `BC5_DIRECT_ACB_STATE_RESTORE=1`, as in test build 1. It uses
the live saves when played. No shortcut; the top session will ask him, under the name test 0381 all. The F761 shadow is not in it: it is
not runtime code.

## Exactly what differs from 4c686b5b

1. **`libC.cpp`:** the three NID registrations (PORT-LIBC). The title's calls to those three names change target.
2. **`libNpCppWebApi.cpp`:** self-aliasing in `String::append` and the two vector `pushBack`s (PORT-NP).
3. **`acb_restore.hpp`:** `final_value` walks CHAIN and joins conditions. It only feeds a journal line under `BC5_DIRECT_DISPATCH_JOURNAL`, which the
   launcher does not set. So in play this changes no behaviour, though the object differs.
4. **Paths:** the launcher's directory and its log's first line.

Nothing else: the same restore code, recorder, crash frames, `NO_CLEAR`, zero skip and list, shared objects and archive.

## Overlap with the NP and libc hunks

**None in `bc5LleAgc.cpp`.** Patch 00a296da differs from 9420cfa0 (65f13dd) in hunks of `src/libs/libC.cpp` and `src/libs/libNpCppWebApi.cpp`
only, +30/-8 lines. Exp 0383's run confirmed that the patched tree differs from the shared tree in those two files alone, and the build
rechecks this. `mkpatch0381.py` touches `bc5LleAgc.cpp` only. Exp 0372's pieces stay: 5 lines and `pad_audio_route.hpp`, on both patches
(read here), rechecked in the tree by the build.

## Inputs, pinned

`pins0381tb2.env`, checked before anything is built; any mismatch stops the build. Commits: main d6fa368 (backend tree 909f6832), fix/port-np-libc
4968372 (patch 00a296da, run2 verdict Supported at 58a3e0d), exp 0383's Linux evidence `raw/run2-*`. Shared pins compared before and after.

## The steps, on the box

1. `tb2run0381.sh build <out>`: the tree crosses, then guard, claim, build. Catch2 at main (clang), the patched tree proved, four units compiled with
   the shared commands, link, launchers. Writes only under `~/bc5-work/exp0381/tb2`, `in-tb2` and `backend-build-tb2`. About 3 minutes, CPU only.
2. `tb2run0381.sh smoke TS2 <out>`: one start, RT on, a private copy reset from the named snapshot (see the top of this file), through the smoke launcher (7 lines different
   from the real one: saves, config, learned file, working directory, switches file, and the private paths, directory and guards it forces), journal off, the kernel log streamed.

**One change from the brief, for Codex and the top session to accept or refuse.** "120 s with the cap" would never test the cap, since the laptop
stopped the last smoke first. So the **cap is set to 125 s and the laptop's stop to 140 s as a backstop**, so that the cap fires. If it does
not, the run still ends at 140 s and the report says so.

## Catchers: terms for the next request (no go yet)

The smoke runs with all three off. Switching one on is a separate request and a separate go; his standing rule puts them in the build, not in a run. They work in this candidate only because it links the normal objects: in the lean build `BC5_DIAG_ENV` is a null pointer and `CHAIN_BREAK_AT` is absent, so nothing here carries over to a lean binary.

| Arm | Risk | Terms to settle before a go |
|---|---|---|
| all off | the smoke's own | none beyond the smoke |
| `DRAW_ARGS_JOURNAL=1` or `DISPATCH_JOURNAL=1` | a long journal took 38 GB in `on-3` and writes through the page cache, so it can fill the disk and change the timing | one journal per run, a time limit, free space read before and watched during, where the journal lives and who removes it; journals stay private |
| `CHAIN_BREAK_AT=12673` | forces a fault's position: 3 of 3 starts faulted without the restore (F685) | restore on in every start, a start count, the box's reset and reboot path accepted, devcoredumps stay private |

Each arm keeps the series' lock line, one run tag, `recover0381tb2.sh` as the undo and the kernel log streamed. Off in the file is the rollback of a switch; `recover` undoes the build.

## Result, 2026-10-31

Built at 18:51 from bc1fe7f3 (binary 86318679, shared pins unchanged, sample f93851b7b0e0dc7a). The first smoke stopped at the path check, before the emulator: `wd` holds its links by design. After that fix, with no rebuild (`tb2run0381.sh again`, launchers fb93a9b9 and a28f78c1), TS3 passed: one start, RT on, all switches off, stopped by the cap at 126 s, 0 faults, 0 timeouts, 0 resets, restore lines 31, zero skip lines 29, no ib-timeout file, 28 flips a second at the end. It shows a clean 2-minute start on that sample, nothing about F443 in play, audio or the catchers.

## The smoke's rule, written before it runs

**Pass:** no kernel fault or gfx timeout, no crash line, the cap's `boxcap: TERM` line in the start file, stopped at about 125 s, the restore's lines and
the zero skip's lines in the journal, the sample named in the start file, no emulator or stream left.

**Fail, or stop and report:** any fault, timeout or crash; the laptop's backstop firing (the cap did not work); a pin or a shared file changing. No
second start without a new go.

What it shows: the combination starts and runs for two minutes, and the cap works once. What it does not show: F443 in play (journal off, so the
exposed position is unknown); the NP and libc paths (nothing shows the title calling them, and exp 0383's binary was not run either); the recorder and
crash frames (no event); that the cap survives a dropped ssh (not tested).

## Risks carried, plainly

- **The restore depends on the tracker, and F761 and F764 are not fixed.** A CHAIN's dead tail, a condition taken as always, or a table past 4,096
  entries can give a wrong value in a prefix. Test build 1 had this too, and the CS prefix has since exp 0195. No CHAIN is shown in the title's streams;
  exposure is unknown. Codex's position stands that this is not a basis for default-on in shared builds.
- **`libC.cpp` changes three names the title may call.** That is the point of it, but it is the one change here that can alter behaviour without any
  event. If he sees something new, this is the first place to look.
- Three independent changes are in one binary, as he asked. If a new fault appears, the binary alone will not say which change did it. Test build 1 (4c686b5b)
  stays on the box for comparison.

## The fallback's limit

On the fallback, main's other backend changes are not in the build: the shared archive bb50b2e0 is older than main. The Catch2 run at main tests a tree that is not
the archive linked here, as in test build 1.

## Rollback

Nothing shared changes. Delete `~/bc5-work/exp0381/tb2`, `in-tb2` and `backend-build-tb2`; he goes on with 4c686b5b or his usual launcher.
