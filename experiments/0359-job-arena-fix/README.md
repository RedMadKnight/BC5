# 0359 — The job-arena fix: a temporary, switchable game-code workaround for the null-arena crash

**Date.** 2026-10-28. **Branch.** `exp/0300-rt-dispatch-sync`. **Box.** RT on for every run (the standing rule).

**Question.** Exp 0358 (F444–F454) read the second title's crash at the fight (eboot.bin+0x3d7eca0, five of five plays
that reached the fight) down to a race the host loses: at frame end the title's main thread — the owner of its job
system — pushes jobs and waits at once; while waiting it runs pending jobs itself, and one kind of job looks its
frame arena up by the thread's worker slots, which the owner never has, so the lookup yields null. The workers would
take that job first on the console; here the box's cores are saturated at the fight (F453/F454) and the owner gets
there first. Three host-side candidates were measured and did not reach it (the targeted semaphore wake, the host
threads at nice +5; a spin cannot, the workers were busy, not asleep). The maintainer's decision (14:5x): a patch as an
emulator option, temporary, while the throughput work (HANDOFF Q24) proceeds in another session so the patch can go.
Can the owner's help call be wrapped in the title's own override window, switchable per title from the Emulation
menu, with the title's bytes checked exactly before anything is written, and does the maintainer's fight then pass?

## Design

- **What the title does for an inline run.** Its override window (+0x3ccadc9–+0x3ccae5b): a 0x38-byte stack arena
  (the block, its size, 16 bytes of constants from image+0x77f9c30, a zero, 16 zero bytes, a pointer image+0x7555574)
  stored into image+0xb064018, the special index N (image+0xb064020) into the thread's worker slot (tcb−0x104),
  `call [job+0x80]`, then the arena slot 0 and the index −1 again. The job's arena lookup (+0x466212d) honours
  index N by taking image+0xb064018. The owner's help loop (+0x3cca600) makes the same `call [r15+0x80]` at
  +0x3cca87b without the window — the one inline path without it.
- **The patch.** The 7-byte `call [r15+0x80]` at +0x3cca87b becomes `call [rip+disp32]` (6 bytes) + `nop` through an
  8-byte slot at +0x3cca4c8 (eight `int3` of padding after a `__stack_chk_fail` stub, 8-aligned, within rip reach),
  which holds the address of a host hook with the guest's SysV calling convention. The hook reads the job's block
  function at +0x80, and if the current thread's worker index is −1 (the owner; a registered worker keeps its own)
  builds the stack arena as the title does, sets the slot and the index, calls the function with the same four
  arguments, and restores both. Nothing else of the title's code or data changes. The pure parts (the offsets, the
  expected bytes, the encoding, the arena layout, the "wrap only an unregistered thread" rule) are in
  `backend/include/bc5/job_arena_fix.hpp` with Catch2 `[job_arena_fix]` (`backend/tests/job_arena_fix_test.cpp`);
  the host side is `GamePatch::ApplyJobArenaFix()` in `loader/gamePatch.cpp` (KytyPlus's game-patch unit, whose plan
  mechanism is byte-for-byte writes without hooks), called from `RuntimeLinker::Execute` right after the game-patch
  plan and before the modules start.
- **The checks.** TITLE_ID must be PPSA03671 (`SystemContentParamSfoGetString`); the 7 bytes at the site and the 8 at
  the slot must be the expected ones; the slot must be within rip reach. Otherwise a log line says why and nothing is
  written. The expected bytes are the two instruction encodings (`41 ff 97 80 00 00 00`, eight `cc`): the minimal
  check, no other title bytes in the repo.
- **The switch.** `input.cfg`: `JobArenaFix.<TITLE_ID>=on|off`, read, saved and kept for other titles like
  `RayTracing.<TITLE_ID>` (exp 0273) and `MangoHud.<TITLE_ID>` (exp 0301); not set means ON for PPSA03671 and off for
  any other title. `KYTY_BC5_JOB_ARENA_FIX=0|1` overrides the file (for the bench). The Emulation menu gains a
  "Game fixes" submenu with "Job-arena fix (temporary, next start)": a checkbox saved per title through the menu's
  own `SaveTitleSwitch`; the code is patched at load, so a change takes effect at the next start (the item says so,
  and its tooltip says what it is and that it is to be removed). A line at start says ON/OFF and whether it was
  applied; the hook prints its first call and every thousandth (how many were wrapped).
- **Labels.** Code, menu and README call it a temporary game-code workaround, to be removed once the host's
  throughput at the fight is fixed (HANDOFF Q24).

## Setup

Box: `raw/build0359.sh` + `raw/build0359.py` + `raw/patch0359.pl` (0358's private-build pattern): the backend copied
beside the script is configured and built privately and its Catch2 tests run first; then four host units
(`loader/gamePatch.cpp`, `loader/runtimeLinker.cpp`, `graphics/presentation/window/hostInput.cpp`,
`graphics/presentation/hostMenu.cpp`) and two headers are copied into a private tree with the backend header,
patched, compiled with the shared normal build's compdb commands and relinked with the shared archive (header-only
fix: the archive is unchanged). Nothing shared written (D19). Smoke: `~/bc5-work/exp0358/repro0358.sh` with the
0359 binary (the Continue route from the private copy of the live saves, RT on, 200 s). The shortcut: "BC5 emulator
(test 0359)" (`raw/mktest0359.pl`, `raw/shortcut0359.sh`: the integrated launcher with a log and a pad record per
start in `~/bc5-work/exp0359/play/`), the test 0358 shortcut moved to the desktop's trash (`raw/trash0358.sh`).

**The maintainer's play (2026-10-28 15:38:47–15:47:26; top session; "Poprawka zadziała").** Shortcut "BC5 emulator
(test 0359)", build 89b95e4e, RT on, the fix not set in `input.cfg`, so ON for PPSA03671. Laptop streams in
`raw/maintainer-test/`.
- The start log: `game fix (temporary, exp 0359): job-arena fix ON for PPSA03671`, then `job-arena fix APPLIED: site
  +0x3cca87b -> slot +0x3cca4c8 -> host hook`.
- **He played through the fight that crashed six of six earlier plays and on, 514 s in all**, and closed the game
  himself (exit 0). There was no access violation and no amdgpu kernel line.
- The hook wrapped 36,000+ owner calls (thread index −1 → the window).
- 15,437 flips over 514 s = 30.0 flips/s (per-second median 30.9, 10th percentile 20.4).
- The live saves changed by his play (47aefd4567e6d346 → 41a5a36fffb4f8d4).

Verdict for the play: the fix holds where the crash was certain. It stays a temporary game-code workaround (HANDOFF Q24).
