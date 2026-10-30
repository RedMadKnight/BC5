# Test build 2: plan and pins

The maintainer's words, by way of the top session: "Build testowy: => wszystkie zmiany na raz => do moich testów". A private build
for his testing. Status: prepared on the laptop. **Nothing has run on the box.** Codex reviews before the box step, and it needs a slot and
his go in this session's chat.

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
2. `tb2run0381.sh smoke TS2 <out>`: one start, RT on, a fresh private copy of the live saves (377a8d45), through the smoke launcher (4 lines different
   from the real one: saves, config, learned file, working directory), journal off, the kernel log streamed.

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

## A question for the top session

"Wszystkie zmiany" as listed does **not** include main's other backend changes. The shared archive bb50b2e0 is older than main: main has `direct.cpp`,
`indirect_check.cpp` and exp 0380's `zero_skip` work (about 1,700 lines against test build 1's backend) that are not in this build. The Catch2 run at main
tests a tree that is not the archive linked here, as in test build 1. Taking them means a private archive, a bigger change, and a new review. I have
left them out, per the list.

## Rollback

Nothing shared changes. Delete `~/bc5-work/exp0381/tb2`, `in-tb2` and `backend-build-tb2`; he goes on with 4c686b5b or his usual launcher.
