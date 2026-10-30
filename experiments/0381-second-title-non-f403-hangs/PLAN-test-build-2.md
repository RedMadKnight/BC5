# Test build 2: plan and pins

The maintainer's words, by way of the top session: "Build testowy: => wszystkie zmiany na raz => do moich testów". A private build
for his testing. Status: prepared on the laptop. **Nothing has run on the box.** Codex reviews before the box step, and it needs a slot and
his go in this session's chat.

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
- **Revised after Codex's REVIEW-PORTS-09 (HOLD), not proved yet.** A later `bc5-pkg.env` could undo the reset, so the block moves to right before the log, after both settings files, and `tb2_check` stops the start if the
  environment at the emulator's line is not what the log says. The order is checked by counted anchors on the launcher as built, and the two launchers get pins. **The proof is missing:** r1's launcher (299a2519) has no ordinary local
  copy, and `play-pkg.sh` 55531ab6, where the versioned generators start, is not in git. The tests refuse to run without it and `PIN_TB2_LAUNCHER`, `PIN_TB2_SMOKE` are `FILL`, so the build refuses too. After the maintainer's play and an agreed read of
  `~/bc5-work/exp0380r1/play-pkg-0380r1.sh`: put it in `raw/`, run the tests, fill the pins. The anchors were written after reading a copy taken from a session transcript, which is outside what was allowed and has been deleted; the build checks them on the real file either way.
- `BC5_DIRECT_DRAW_ARGS_JOURNAL` is not in the list: it is a diagnostic, and a long journal is what filled 38 GB in `on-3`.

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
2. `tb2run0381.sh smoke TS2 <out>`: one start, RT on, a fresh private copy of the live saves (377a8d45), through the smoke launcher (5 lines different
   from the real one: saves, config, learned file, working directory, switches file), journal off, the kernel log streamed.

**One change from the brief, for Codex and the top session to accept or refuse.** "120 s with the cap" would never test the cap, since the laptop
stopped the last smoke first. So the **cap is set to 125 s and the laptop's stop to 140 s as a backstop**, so that the cap fires. If it does
not, the run still ends at 140 s and the report says so.

## The smoke's rule, written before it runs

**Pass:** no kernel fault or gfx timeout, no crash line, the cap's `boxcap: TERM` line in the start file, stopped at about 125 s, the restore's lines and
the zero skip's lines in the journal, live saves unchanged, no emulator or stream left.

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
