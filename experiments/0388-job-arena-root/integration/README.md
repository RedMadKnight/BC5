# 0388, the integration of arm J and the removal of the job-arena fix (D19)

**Date.** 2026-11-01. **Branch.** `int/0388-j`, from main `4ef4f6fe`. **Request.** The maintainer: "Ramię J ma być wbudowane", then, for the wait, "dla wszystkich tytułów", "arena fix ma zniknąć z opcji i z kodu", and "Usuń A oraz B, wbuduj J. Daj mi do testów na świeżym buildzie." **Status.** Prepared on the laptop. Nothing on the box has changed, and the patch is not merged: main must match the shared builds (D19).

**Scope.** The wait J: 2000 µs at most, on by default for every title, off with `KYTY_BC5_JOB_PUSH_WAIT=0`. Exp 0359's job-arena fix goes from the menu and the code, and classes A and B of the switch inventory go. No zero skip, no 0390, no catcher of exp 0388. The shared `play-pkg.sh` gets one line, `export BC5_DIRECT_GC_HS_OFFCHIP=1`, the water fix of exp 0399 (the top session, on the maintainer's yes). `input.cfg` and the learned list stay as they are.

## What changes

Patch 0001: `716dcaf6` → `4e559f47`, 318 lines added and 2,552 removed in the patch file. `grep -c 'exp 0372'` stays 5, and `pad_audio_route.hpp` stays. No `KYTY_BC5_0388`, `ZERO_SKIP` or `APR_PARK` in it. 42 files in all: 28 host, 7 backend, 7 mount. `mkkit.py` makes the kit and the pins from a host tree of the candidate.

The wait and the fix touch `src/bc5/job_push_wait.hpp` (new, also `backend/include/bc5`), `src/bc5/job_arena_fix.hpp` (removed, also in `backend/` with its test), `kernel/semaphore.cpp`, `loader/gamePatch.cpp`/`.h`, `loader/runtimeLinker.cpp`, `presentation/hostMenu.cpp` (the "Game fixes" menu goes; the fix was its only item) and `window/hostInput.cpp`/`.h`.

**Classes A and B** (`coordination/switch-removal-20261101.md`): 110 of its 115 names are removed. None was set in the live launchers or `bc5-run.env`, read at 19:30 (`bc5-pkg.env` does not exist).

| kept | why |
|---|---|
| `BC5_DIRECT_HS_OFFCHIP`, `GC_HS_OFFCHIP`, `OFFCHIP_SECOND` | the top session: exp 0397 points at `VGT_HS_OFFCHIP_PARAM` |
| `BC5_DIRECT_TF_DEFAULT` | `hs_offchip_force()` is called only inside its block; removing it would leave HS_OFFCHIP with no effect |
| `BC5_AGC_DUMP_DIR` | it is the whole RPCSX capture tap: `backend/rpcsx-patches` and a CI job would go with it; the top session: it stays |

The tunables with no stated default fold as the code had them: `FENCE_TIMEOUT_MS` to 2 s, `MAX_BO_MIB` keeps its sysfs read and clamps, `NODE` is `/dev/dri/renderD128`, `CU_MASK` 0xffffffff. One option field goes, `FilterOptions::pfp_sync_indirect`, so the archive and the host are rebuilt together (F414). Unset behaviour should be the same but for timing and log text: the journal's t 0 may move slightly, since FIND_ALL made the first clock call; some unconditional counters and a per-call lock in the audio path are gone; two stderr lines lost fields.

**One old line stays understood.** `input.cfg` holds `JobArenaFix.PPSA03671=off`, and an unknown key is an error at start. So the parser keeps one three-line branch that reads such a line and drops it, and that file stays untouched. The next save from the menu leaves the line out. This is the only place the name remains in code, besides a comment in the new header.

**"For every title".** There is no title check. The wait is on by default everywhere and prints its state at every start. It acts only where the main executable holds the known code at `+0x3cca87b` and is large enough for the table, because the table's offsets belong to one build of one executable; reading them in any other would crash the title. Any other executable prints `OFF, not the code it knows` and runs as before. A build of the same game under another title id gets the wait. Other titles have no such table, so for them the wait does nothing either way. A form that works without a table is arm F, at about 15 % of the frames, so it was not taken.

**Differences from the tested arm, binary `1a596e50`.**

- The image base comes from `program->base_vaddr`, not a constant, and the wait is enabled only for the known code.
- A title update turns it off and says so; the bytes compared are the fix's own, already in the repository.
- The arm's trace and catchers are gone. The trace is `KYTY_BC5_JOB_PUSH_TRACE`, off by default and not compiled in lean. All arm runs had `TRACE=1`, so the integrated build is slightly lighter, not the same.

**What the removal risks.** The fix has the longer record: 514 s of the fight (F457) and every run since. The wait has 5 of 5 on the route and one pass of the fight, with a private list and changed sysctls, and why it is enough is not known. With the fix gone, if the wait fails the crash at eboot+0x3d7eca0 is back with no in-game switch. The way back is then the rollback below, or the old binary's copy.

## Tests run on the laptop

- `backend/tests/job_push_wait_test.cpp`: 26 checks pass with a Catch2 stand-in; the real Catch2 runs on the box if that tree built it.
- `test_wait.py`: 13 pass, on the final tree: text checks with mutants, then `semaphore.cpp`'s own code on a fake job table, normal and lean. The timing case failed once on a loaded laptop and passed alone.
- `test_apply.py`: `ApplyJobPushWait` on a fake image: on with no title known, the switch, other code, a small image, nothing loaded.
- `test_int.sh`: 14 pass, the swap on stand-ins: success, five stops before the lock, four restores.
- `cargo test -p bc5-mount`: 93 passed, 0 failed, 1 ignored. `clippy -D warnings` and `fmt --check` clean. On Windows, so `fuse.rs`, which needs the `fuse` feature on Linux, was not compiled.

Not done: **no changed C++ unit has been compiled whole**, neither host nor backend. The box build is the first compile of a change of 28 host files, and the backend has `-Werror`. Expect at least one round of build errors. No test on the GPU or in a run.

## Build and swap

In a slot: with `box0388.sh`, the candidate as `0001-new.patch` and `kit/` in `exp0388/s/`, run `int0388j.sh`. Before the lock it checks no emulator; normal `78f25172`, lean `7b246487`, archive `3292bdaf`; the tree's diff, index lines apart; every file's md5; exp 0372 in the candidate. Under the lock it copies the four outputs and every file to `exp0388/integration/`, writes the kit's files over the host tree, the backend source named in the build's cache and `~/src/bc5/tools`, then builds archive, backend tests if present, normal, lean and mount at nice 19. Both binaries must hold the wait and no `job-arena` string; removed names still in them are counted and printed. The tree's diff must equal the candidate. Any failure after the first write restores everything and releases the lock.

If the build fails on a compile error the script restores all, so a fix means a new kit and a new slot.

**Rollback after a good swap.**

```bash
cp -p ~/bc5-work/exp0388/integration/kyty_emulator.before-j ~/bc5-work/kytyplus-build/src/kyty_emulator
```

```bash
cp -p ~/bc5-work/exp0388/integration/kyty_emulator-lean.before-j ~/bc5-work/kytyplus-build-lean/src/kyty_emulator
```

Then `libbc5_backend.a.before-j` and `bc5-mount.before-j` the same way, and the files from `integration/tree-before`. The old binaries bring the fix back, per `input.cfg`.

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
4. The rebuilt `bc5-mount`: a real start; the audio check covers the two folded audio values.
5. Lean: the runner cannot route lean, since its second phase is gated on the journal. So D19's lean smoke, plus the start line and no access violation.
6. The audio replug check: exp 0372's `s6n0372.sh` with `replug0372.sh`, then his physical replug and a DS4.
7. ASTRO BOT start: `job push wait OFF, 2000 us at most, not the code it knows`, and it plays as before.
8. The Emulation menu has no "Game fixes".
9. His own play through the fight on the shared build.

S1 runs on the old launcher, at `VGT_HS_OFFCHIP_PARAM` 0. T and U run on the new launcher, with `GC_HS_OFFCHIP`, so they differ from S1 by that too.

Only then `int/0388-j` goes to main, so main matches the builds.

**Limits.** Why the wait is enough is not known: most waits run out the bound. The hangs of 07:41 and 07:54 are not touched by this.

## Result of the swap (2026-11-01 21:29–21:53)

**The first swap** stopped at `bc5LleAgc.cpp:4650`, a `force` left by class B, and restored all. **The second** passed at 21:32–21:34: archive, normal `7c0efa36`, lean, mount, launcher `48a4dbf9`, 0 removed names left in either binary, tree diff equal to patch `f3022900`. The rollback copies are in `exp0388/integration/`, and the first attempt's in `exp0388/integration.first/`.

**S2, the baseline** (old binary, old launcher, fix on): NO_CRASH, 34.3 flips/s. OS 44, Mesa 26.2.4, kernel 7.2.11-ogc4.1, swappiness 60. S1 and T1 stopped on the runner's own pins before any launch.

| run | wait | result | flips/s | waits / pushes |
|---|---|---|---|---|
| T4 | on | NOT_ROUTED: no gameplay gate | 39.9 | 271 / 830,000 |
| T4R | on | **CRASH_TARGET at eboot+0x3d7eca0, 116 s** | none | 223 / 370,000 |
| T5 | on | NO_CRASH | 33.7 | 306 / 630,000 |
| T6 | on | NO_CRASH | 34.1 | 314 / 628,000 |
| U2 | off | NO_CRASH | 33.2 | none |

No amdgpu line in T4R's stream. Each log has the right wait line and `HS offchip 0x1ff (programmed)`.

**J does not hold.** With the wait on and the fix gone, the crash came at its site in one of three routed runs, with the wait active. By the rule that is REFUTED. Over all route runs with J: 7 clean of 8. Controls without it: 3 clean of 10 (U2 included). So J lowers the crash and does not end it, and the 92 % of waits that run out the bound fit that, though that is not shown. This build differs from the arm in having no trace, and in `GC_HS_OFFCHIP` and the removals; one crash does not say whether any of those matter. The shared builds now have no fix, so this crash is live in play.

Not run after this, pending a decision: lean, audio replug, ASTRO BOT. Main stays unmerged.

## The fix comes back (the maintainer, 2026-11-01: "B: fix wraca")

Patch `f3022900` → `df13b062`: the job-arena fix returns exactly as it was, on by default for PPSA03671: hook, `ApplyJobArenaFix`, `KYTY_BC5_JOB_ARENA_FIX`, the "Game fixes" menu, `JobArenaFix.<TITLE>` parsing, the header in both places and its backend test, whose md5 are the integrated ones of exp 0361 (`22a78051`, `a65221ca`). J stays on, the launcher's water line and classes A and B stay. J still looks at the site first, before the fix writes there. The sections above about the fix being gone are the record of what was tried.

**With J and the fix both on.** No run has had that combination yet; T7–T9 are it.

**`input.cfg`.** The default only applies when the file has no line for the title. `JobArenaFix.PPSA03671=off` is explicit, so the restored fix would stay off in his play, and J alone would stand, as in T4R. `KYTY_BC5_JOB_ARENA_FIX=0|1` overrides the file; the route runs set it to 1, so they do not depend on the file. The start log says which it was: `job-arena fix ON for PPSA03671 (input.cfg on)`, `(not set, on for that title)`, or `OFF ... (input.cfg off)`.

The smallest way to have it on in his test: that one line to `=on`, or the line removed. He can do it himself from Emulation → Game fixes, which writes the line, and it counts from the next start. Otherwise it needs his word.

**Second swap.** `int0388j.sh` now stands for this one: pins normal `7c0efa36`, lean `f13f3fc3`, archive `75e30335`, patch `df13b062`, 12 files (8 host, 4 backend). It builds archive, normal and lean; the archive must not change, and the mount and the launcher are not touched. Copies go to `exp0388/integration2/`.

**After it.** `series0388.sh post`: T7–T9, fix on, wait on. Then ASTRO BOT start, lean smoke, the software replug check, then his build.

## Result of the second swap (2026-11-01 21:59–22:43)

Shared builds: normal `f4e1a52e`, lean `206aa65d`, archive `75e30335` unchanged, mount `a59ef623`, launcher `48a4dbf9`, patch `df13b062`. Rollback to the fixless build in `exp0388/integration2/`, to the pre-integration build in `exp0388/integration/`.

| check | result |
|---|---|
| T7, T8, T9: fix and J on, RT on, 180 s, route, env override | NO_CRASH, 33.8, 33.9, 34.2 flips/s; 318, 316, 338 waits; `HS offchip 0x1ff (programmed)`; no amdgpu line |
| Lean, 150 s, private saves | job push wait ON, job-arena fix ON and APPLIED, hook wrapping; no access violation, no amdgpu line; launcher exit 0 |
| ASTRO BOT start, 90 s, no input | `job push wait OFF ... not the code it knows`, the fix OFF; no access violation, no amdgpu line; exit 0 |
| Software replug J1, `s6n0372j.sh` and `replug0372j.sh`, RT on, 420 s | pass: three pulls, every pad stream back on the DualSense with both flags, the main mix on the dock; 0 kernel lines; live saves unchanged `b80e1812c389f309` |

`series0388.sh`'s `RULE T FAIL: 5 clean of 7` counts every T row, T4R and T4 from the fixless binary too; T7–T9 alone are 3 of 3.

Lean ran with the fix forced by the environment and the menu route only: it did not reach the fight, which the runner cannot gate on lean. J's job-table reads have the private save route, not free play.

`input.cfg`: `JobArenaFix.PPSA03671=on`, on the maintainer's word ("Tak, ustaw =on"), md5 `6de9c4c4`; the old file is `exp0388/integration2/input.cfg.before-on`.

Left: his physical replug with a DualSense and a DS4, his fight, then the merge to main by the top session. HANDOFF's findings go with the merge.

My waiting loop on the box matched its own `pgrep -f` and held the lock from 22:23 to 22:43 with nothing running.
