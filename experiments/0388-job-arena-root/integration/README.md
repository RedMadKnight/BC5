# 0388, the integration of arm J (D19)

**Date.** 2026-11-01. **Branch.** `int/0388-j`, from main `4ef4f6fe`. **Request.** The maintainer: "Ramię J ma być wbudowane". **Status.** Prepared on the laptop. Nothing on the box has changed, and the patch is not merged: main must match the shared builds (D19).

**Scope.** Only the wait J: 2000 µs at most, on by default for PPSA03671, off with `KYTY_BC5_JOB_PUSH_WAIT=0`. No zero skip, no 0390, no catcher of exp 0388. `input.cfg`, `play-pkg.sh`, the learned list and the archive stay as they are.

## What changes

Patch 0001: `716dcaf6` → `d07739b7`, +248 lines. Its only removed lines are index lines and hunk headers. `grep -c 'exp 0372'` stays 5, and `pad_audio_route.hpp` stays. No `KYTY_BC5_0388`, `ZERO_SKIP` or `APR_PARK` in it.

| file | change |
|---|---|
| `src/bc5/job_push_wait.hpp`, new, also `backend/include/bc5` | constants, the off rule, the look at the job table |
| `src/kernel/semaphore.cpp` | `m_bc5_job` by name, `Bc5JobPushWait` after the signal in `KernelSignalSema`, the trace |
| `src/loader/gamePatch.cpp`, `.h` | `ApplyJobPushWait`: title, known code, the switch |
| `src/loader/runtimeLinker.cpp` | one call, before `ApplyJobArenaFix` |
| `backend/tests/job_push_wait_test.cpp`, `backend/CMakeLists.txt` | the test |

The archive is not rebuilt, since the backend gets only a header and a test.

**Differences from the tested arm, binary `1a596e50`.**

- The image base comes from `program->base_vaddr`, not a constant, and the wait is enabled only for the title. In the arm it needed only the switch, and another title with a semaphore of that name would have read unmapped memory.
- It runs only if the code at the fix's site is the known one, read before the fix writes there. A title update turns it off and says so; no new title bytes enter the repository.
- The arm's trace and catchers are gone. The trace is `KYTY_BC5_JOB_PUSH_TRACE`, off by default and not compiled in lean. All arm runs had `TRACE=1`, so the integrated build is slightly lighter, not the same.

**With `JobArenaFix` on.** They are independent. The wait looks for the same open jobs and spins as before; the fix wraps the owner's help call, so the crash cannot come whether the wait runs or not, and the wait is then only a small cost, about 0.4 % of the main thread by the 180 s arm. No J run has had the fix on, so this is from the code. The shared `input.cfg` has `JobArenaFix.PPSA03671=off`, and without that line the fix is on by default: both remain as they are.

## Tests run on the laptop

- `backend/tests/job_push_wait_test.cpp`: 21 checks pass with a Catch2 stand-in; the real Catch2 was not run.
- `test_wait.py`: 13 pass. Text checks with three mutants, then `semaphore.cpp`'s own code built with stand-ins and run on a fake job table, normal and lean: off until enabled, another semaphore, the bound (2,022 and 2,000 µs), nothing to do, a job closing at 300 µs. Lean holds no trace.
- `test_apply.py`: `ApplyJobPushWait` from `gamePatch.cpp` on a fake image: on by default, the switch, another build, another title, nothing loaded.
- `test_int.sh`: 11 pass, `int0388j.sh` on stand-ins: success, four stops before the lock, and two restores.
- `git apply --check` of the new patch on the tree's base commit passes.

Not done: `semaphore.cpp`, `gamePatch.cpp` and `runtimeLinker.cpp` compiled whole with the real headers on Linux. That is the build itself. No test on the GPU or in a run.

## Build and swap

In a slot, under the lock: with `mkhost.py`, `job_push_wait.hpp`, `box0388.sh` and the new patch as `0001-new.patch` in `exp0388/s/`, run `int0388j.sh`. It checks, in this order: no emulator; normal `78f25172`, lean `7b246487`, archive `3292bdaf`; the tree's diff is `716dcaf6`; the four files' md5; the kit; exp 0372 in the candidate. Then it claims the lock, and copies both binaries and the four files to `exp0388/integration/`, reading the copies back. Then it edits `~/src/KytyPlus`, checks each file's md5 against the laptop's, and runs `ninja kyty_emulator` at nice 19, normal then lean. At the end the tree's diff must equal the candidate byte for byte. Any failure after the edit restores both binaries and the files and releases the lock.

**Rollback after a good swap.**

```bash
cp -p ~/bc5-work/exp0388/integration/kyty_emulator.before-j ~/bc5-work/kytyplus-build/src/kyty_emulator
```

```bash
cp -p ~/bc5-work/exp0388/integration/kyty_emulator-lean.before-j ~/bc5-work/kytyplus-build-lean/src/kyty_emulator
```

Then the four files from `integration/tree-before`, and remove `src/bc5/job_push_wait.hpp`.

## Checks after the swap, W1 first

1. The start line in the normal log: `job push wait ON, 2000 us at most`. Lean prints it too.
2. The F454 route, RT on, shared normal, 180 s: three runs as `input.cfg` stands (fix off): NO_CRASH, no amdgpu line.
3. One run with `KYTY_BC5_JOB_PUSH_WAIT=0` and the fix off: the line says OFF. The crash is expected, 7 of 9 in the controls, and no crash there is not a failure of J.
4. One run with `KYTY_BC5_JOB_ARENA_FIX=1`: both on, the combination no run has had.
5. One run on lean, fix off.
6. The audio replug check: exp 0372's `s6n0372.sh` with `replug0372.sh`, then his physical replug and a DS4.
7. ASTRO BOT start: no wait line, as the title is not the fix's.

Only then `int/0388-j` goes to main, so main matches the builds. Runner for 2–5: exp 0388's `run0388.sh` uses the private binary and arms by tag, so it needs a small derivation for the shared build; not written yet.

**Limits.** J has 5 of 5 on the route and one pass of the fight in play, which differed in its list and sysctls. Why the wait is enough is not known: most waits run out the bound. The hangs of 07:41 and 07:54 are not touched by this.
