# 0388, the integration of arm J and the removal of the job-arena fix (D19)

**Date.** 2026-11-01. **Branch.** `int/0388-j`, from main `4ef4f6fe`. **Request.** The maintainer: "Ramię J ma być wbudowane", then, for the wait, "dla wszystkich tytułów", and "arena fix ma zniknąć z opcji i z kodu". **Status.** Prepared on the laptop. Nothing on the box has changed, and the patch is not merged: main must match the shared builds (D19).

**Scope.** The wait J: 2000 µs at most, on by default for every title, off with `KYTY_BC5_JOB_PUSH_WAIT=0`. Exp 0359's job-arena fix goes from the menu and the code. No zero skip, no 0390, no catcher of exp 0388. `input.cfg`, `play-pkg.sh`, the learned list and the archive stay as they are.

## What changes

Patch 0001: `716dcaf6` → `e5bb3acd`, 123 lines added and 383 removed. `grep -c 'exp 0372'` stays 5, and `pad_audio_route.hpp` stays. No `KYTY_BC5_0388`, `ZERO_SKIP` or `APR_PARK` in it.

| file | change |
|---|---|
| `src/bc5/job_push_wait.hpp`, new, also `backend/include/bc5` | constants, the known code, the look at the job table |
| `src/bc5/job_arena_fix.hpp`, also in `backend/` with its test | removed |
| `src/kernel/semaphore.cpp` | `m_bc5_job` by name, `Bc5JobPushWait` after the signal in `KernelSignalSema`, the trace |
| `src/loader/gamePatch.cpp`, `.h` | the hook and `ApplyJobArenaFix` out, `ApplyJobPushWait` in |
| `src/loader/runtimeLinker.cpp` | one call; the fix's call, its switch and `bc5_tls_main_tcb` out |
| `src/graphics/presentation/hostMenu.cpp` | the "Game fixes" menu out; the fix was its only item |
| `src/graphics/presentation/window/hostInput.cpp`, `.h` | the switch and `KYTY_BC5_JOB_ARENA_FIX` out |
| `backend/tests/job_push_wait_test.cpp`, `backend/CMakeLists.txt` | the new test in, the fix's test out |

The archive is not rebuilt, since the backend changes only by a header and tests.

**One old line stays understood.** `input.cfg` holds `JobArenaFix.PPSA03671=off`, and an unknown key is an error at start. So the parser keeps one three-line branch that reads such a line and drops it, and that file stays untouched. The next save from the menu leaves the line out. This is the only place the name remains in code, besides a comment in the new header.

**"For every title".** There is no title check. The wait is on by default everywhere and prints its state at every start. It acts only where the main executable holds the known code at `+0x3cca87b` and is large enough for the table, because the table's offsets belong to one build of one executable; reading them in any other would crash the title. Any other executable prints `OFF, not the code it knows` and runs as before. A build of the same game under another title id gets the wait. Other titles have no such table, so for them the wait does nothing either way. A form that works without a table is arm F, at about 15 % of the frames, so it was not taken.

**Differences from the tested arm, binary `1a596e50`.**

- The image base comes from `program->base_vaddr`, not a constant, and the wait is enabled only for the known code.
- A title update turns it off and says so; the bytes compared are the fix's own, already in the repository.
- The arm's trace and catchers are gone. The trace is `KYTY_BC5_JOB_PUSH_TRACE`, off by default and not compiled in lean. All arm runs had `TRACE=1`, so the integrated build is slightly lighter, not the same.

**What the removal risks.** The fix has the longer record: 514 s of the fight (F457) and every run since. The wait has 5 of 5 on the route and one pass of the fight, with a private list and changed sysctls, and why it is enough is not known. With the fix gone, if the wait fails the crash at eboot+0x3d7eca0 is back with no in-game switch. The way back is then the rollback below, or the old binary's copy.

## Tests run on the laptop

- `backend/tests/job_push_wait_test.cpp`: 26 checks pass with a Catch2 stand-in; the real Catch2 was not run.
- `test_wait.py`: 13 pass. Text checks with three mutants, then `semaphore.cpp`'s own code built with stand-ins and run on a fake job table, normal and lean: off until enabled, another semaphore, the bound (2,000 µs), nothing to do, a job closing at 300 µs. Lean holds no trace. The timing case can fail on a loaded laptop; it failed once while another suite ran and passed alone.
- `test_apply.py`: `ApplyJobPushWait` from `gamePatch.cpp` on a fake image: on with no title known, the switch, other code, an image too small, nothing loaded.
- `test_int.sh`: `int0388j.sh` on stand-ins: success, four stops before the lock, and two restores.

Not done: the changed units compiled whole with the real headers on Linux. That is the build. No test on the GPU or in a run. The menu and parser edits are checked only by the swap script's stand-ins and by grep.

## Build and swap

In a slot, under the lock: with `mkhost.py`, `job_push_wait.hpp`, `box0388.sh` and the new patch as `0001-new.patch` in `exp0388/s/`, run `int0388j.sh`. It checks, in this order: no emulator; normal `78f25172`, lean `7b246487`, archive `3292bdaf`; the tree's diff is `716dcaf6`; the seven files' md5 and the old header; the kit; exp 0372 in the candidate. Then it claims the lock, and copies both binaries, the seven files and the old header to `exp0388/integration/`, reading the binaries back. Then it edits `~/src/KytyPlus`, checks each file's md5 against the laptop's, and runs `ninja kyty_emulator` at nice 19, normal then lean. Both binaries must hold the wait and no `job-arena` string, and the tree's diff must equal the candidate byte for byte. Any failure after the edit restores both binaries and the files and releases the lock.

**Rollback after a good swap.**

```bash
cp -p ~/bc5-work/exp0388/integration/kyty_emulator.before-j ~/bc5-work/kytyplus-build/src/kyty_emulator
```

```bash
cp -p ~/bc5-work/exp0388/integration/kyty_emulator-lean.before-j ~/bc5-work/kytyplus-build-lean/src/kyty_emulator
```

Then the files from `integration/tree-before`, and remove `src/bc5/job_push_wait.hpp`. The old binaries bring the fix back, per `input.cfg`.

## The route runner

`route/`, made by `mkroute.py` from exp 0388's reviewed runner, with its stand-in suite by `mkroutetest.py`. It works in `exp0388r` and runs the shared normal binary, pinned by its first eight digits.

| tag | when | binary | expected |
|---|---|---|---|
| `S1` | before the swap: `series0388.sh baseline` | old `78f25172`, fix on | NO_CRASH, the first baseline after the reboot |
| `T1`–`T3` | after: `series0388.sh post` | new | `job push wait ON`, NO_CRASH, no amdgpu line |
| `U1` | after, the same series | new, `KYTY_BC5_JOB_PUSH_WAIT=0` | `OFF`; the crash is expected, 7 of 9 in the controls; no crash is no failure of J |

`S1` has the fix on because with it off a crash ends the baseline early and says nothing about the new system. It records the OS, Mesa and kernel versions in `<tag>-box-settings.txt`.

Before the run: `pins0388.env` holds the values read on 2026-11-01 for `input.cfg` and the learned list. A pin that no longer fits stops the run before the launch, so re-read them at the slot. `NEW=FILL` stops every T and U run until the swap's md5 is filled in.

## Checks after the swap, W1 first

1. `series0388.sh baseline` before the swap.
2. The start line in the normal log: `job push wait ON, 2000 us at most`. Lean prints it too.
3. `series0388.sh post`: T1–T3 and U1.
4. Lean: the runner cannot route lean, since its second phase is gated on the journal. So D19's lean smoke, plus the start line and no access violation.
5. The audio replug check: exp 0372's `s6n0372.sh` with `replug0372.sh`, then his physical replug and a DS4.
6. ASTRO BOT start: `job push wait OFF, 2000 us at most, not the code it knows`, and it plays as before.
7. The Emulation menu has no "Game fixes".
8. His own play through the fight on the shared build.

Only then `int/0388-j` goes to main, so main matches the builds.

**Limits.** Why the wait is enough is not known: most waits run out the bound. The hangs of 07:41 and 07:54 are not touched by this.
