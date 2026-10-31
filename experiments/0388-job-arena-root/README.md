# 0388 — The root of the job-arena crash, so the workaround can go

**Date.** 2026-10-31. **Branch.** `exp/0388-job-arena-root`, base main `5b22f70`. **Status.** Finished 2026-10-31: the workaround is still needed. See the result at the end.

**Question.** Why does the title's main thread reach a worker-only job (F444–F454) on this host, and can a host fix make the crash go with `JobArenaFix` off?

**The root, read from the code (2026-10-31, the title's own files on the box, nothing kept beyond offsets and names).**

- The job system's count comes from the import at +0x5f20280, slot 0x980b430, NID `dt3C+gjXHKk`, `std::__sce_v2::_Thrd_hardware_concurrency()` (name from the public table in `ps5rs/data/nids.csv`, 5cfb032).
- The title's own `libc.prx` exports it at +0xca580: it returns a global at +0x1978d4. The init at +0xca5c0 fills that global with the population count of the mask from `scePthreadAttrGet` + `scePthreadAttrGetaffinity` on the calling thread.
- So the title's CPU count **is** the host's default thread mask: `0x7f` gives 7, and +0x3cc9117–+0x3cc9223 turns that into 5 workers per entry. Exp 0358's "7, as on the console" came from the host.
- The formula is N = cpus < 7 ? 4 : min(cpus − 2, 8). Thirteen CPUs would give 8 workers.
- The crash job's class is the title's "any thread" mask (read from +0xb064040 at +0x466306c, before the push at +0x46630aa), so the owner's help at +0x3cca7dd takes it by the title's own rules. Its arena lookup at +0x466212d–+0x4662171 gives null on a thread with no worker slots. Who gets the job first is a race between the owner and the workers, and the host gives the title 5 workers.

**Lead still to show.** That more workers end the crash. The mask `0x1fff` comes from KytyPS5 8c01d8e and AnyPS5 27c88a8, neither a console measurement (TODO(verify)).

## Switches of the private build

All default off; off leaves the host as it was. `patch0388.py` applies them to private copies of four units; the pure parts are `backend/include/bc5/cpu_model.hpp`.

| switch | does |
|---|---|
| `KYTY_BC5_0388_CPU_MASK` | the default thread affinity: unset, empty or `0` keep `0x7f`, `1` is `0x1fff`, `0x<hex>` a mask inside it |
| `KYTY_BC5_0388_CURRENT_CPU=1` | `sceKernelGetCurrentCpu` returns the real CPU inside the thread's mask, not 0 |
| `KYTY_BC5_0388_APPLY_AFFINITY=1` | a guest mask narrower than the model's is applied to the host thread |
| `KYTY_BC5_0388_PUSH_SPIN_US=<0..500>` | after a main-thread signal of `JobLoaderSema`, a bounded spin so a worker can go first |
| `KYTY_BC5_0388_TRACE=1` | catcher: logs the first 400 affinity reads, attribute reads and sets, and each host mask applied |

**Tests so far.** The pure parts: 65 checks, 0 failed, on the laptop with clang 22 and a small stand-in for Catch2's macros, not Catch2 itself. `patch0388.py` applied to a tree of `f266548` + main's patch; the patched units have not been compiled.

**Box scripts.** `box0388.sh claim|build|release`, with `build0388.py`, `patch0388.py`, `units.sha256` and `backend/include/bc5/cpu_model.hpp` beside it on the box. `test_box0388.sh` tests the claim and release in a temporary HOME with a stand-in `pgrep`: 14 of 14. The `build` step has had `bash -n` only.

## Test layout, fixed before the runs

- **Build.** Private binary md5 `8801066653a7ce491b9be3f753ec3b30`, `~/bc5-work/exp0388/kyty_emulator`: three patched units linked with the shared normal build's objects (78f25172). The shared binary was unchanged by the build.
- **Runner.** `mk0388run.py` derives `run0388.sh`, `go0388.sh`, `series0388.sh`, `s6n0388.sh`, `check0388.py` and the rest from exp 0386's reviewed runner. Same F464 fight route, same named save copy `saves-live-47aefd45` (private copy per run), same gates, one atomic claim per run, RT on, 180 s.
- **All arms:** `JobArenaFix` off (`KYTY_BC5_JOB_ARENA_FIX=0`), `TRACE=1`, the same binary. The shared `input.cfg` is not changed.

| arm | tags | switches beyond those |
|---|---|---|
| C, control | C1 C2 C3 | none: mask `0x7f`, 5 workers |
| A | A1 A2 A3 | `CPU_MASK=1` |
| B | B1 B2 B3 | `CPU_MASK=1 CURRENT_CPU=1 APPLY_AFFINITY=1` |

Order C1 A1 B1 C2 A2 B2 C3 A3 B3, about 4 min each, 36 min, deadline 52 min. One replacement for a run that does not reach the fight. Arm D (`PUSH_SPIN_US=200`) runs only if A and B both fail.

**Exposure.** `<tag>-jobs.txt` counts the `Job ` threads at 70 s, and the trace shows the mask read. An A or B run with the job count of the control has not tested the candidate and does not count.

**Rule (`check0388.py rule`).**

- Control: at least 2 of 3 crash at eboot+0x3d7eca0, or no conclusion on any arm.
- HOLDS: 3 of 3 NO_CRASH that reached the fight, none at the site, none elsewhere.
- REFUTED: any crash at the site.
- OPEN: anything else. A crash elsewhere is reported on its own and is not a pass.
- A pass here says the crash did not come in 180 s on this route; it is not yet the maintainer's fight, and exp 0359's fix stays until that play.

**Stops.** The first kernel amdgpu line, GPU reset or devcoredump ends the series with no retry. No one touches the pad during the series: exp 0386's runs had mixed input.

## Result (2026-10-31 21:36–22:07, F790–F794)

Runner tests before the runs: 43 of the stand-in checks passed, 0 failed, and they found one real fault (the manifest demanded the shared binary), fixed before the first run. The suite hit its 590 s cap, so its kernel, ssh, signal, recovery, gate, release, storage, rule and series groups did not run on the derived scripts. `check0388.py rule` was tried by hand on sample rows.

Pins at the start: `input.cfg` a5259c60 (JobArenaFix off) and the learned file 5b92521f differ from exp 0386's pins and were re-measured. The route copy is 9347496fbaf30f25.

| arm | runs | at the site | no crash | `Job ` threads |
|---|---|---|---|---|
| C, control, mask `0x7f` | C1 C2 C3 | 3 | 0 | 15 |
| A, mask `0x1fff` | A1 A2 A3 | 3 | 0 | 24 |
| B, A + real CPU + applied affinity | B1 B2 B3 | 3 | 0 | 24 |
| D, spin 200 µs | D1 D2 D3 | 1 (D2) | 2 (D1, D3, 180 s) | 15 |

All 12 reached the fight and all crashes read 0xc at eboot+0x3d7eca0, 110–119 s in, about 10 s after the gameplay inputs. There was no amdgpu kernel line, GPU reset or devcoredump; the only kernel lines were IPv6 MLD. Rule output for C, A and B: control 3 of 3, A REFUTED, B REFUTED. The rule's code does not read D; by the fixed rule D is also REFUTED, since a run crashed at the site.

- **F790.** The title's CPU count is the population count of the host's thread mask, read by the title's `libc.prx` (the root section above). Exp 0358's "7, as on the console" came from the host. Shown in the runs: the mask was read as `0x1fff`, and the job threads rose from 15 to 24, so N rose from 5 to 8.
- **F791.** The worker count is not the crash's cause: 8 workers crash 6 of 6, at the same time as 5 workers. CURRENT_CPU and APPLY_AFFINITY do not change that. Whether `0x1fff` is right for other reasons is still open, as neither source is a console measurement.
- **F792.** With no pad input from a person the crash came 9 of 9 without the spin. The automated route is a fast repro: under 2 min, about 10 s after the inputs.
- **F793.** The 200 µs spin after the owner's push changed the outcome: 1 of 3 crashed against 9 of 9 without it. D differs from C only by this switch. Three runs are few and D has no counter of its own, so the spin's effect is shown only by this difference. Exp 0358's "a spin cannot" does not hold here. This contradicts what I expected before the runs.
- **F794.** The time between the owner's push and its help is the lever, not the number of workers. That fits a worker that needs more time to take the job than the owner does. It is not proven, and the spin is not a fix: it still crashed, and 180 s is not the maintainer's fight.

**Verdict.** No candidate holds; `JobArenaFix` stays. Next: the host's wake-to-run time for a worker after the owner's signal, with a counter on the spin, 500 µs, and a longer window.

## Second cycle, fixed before its build (the maintainer's yes, after water)

**Question.** Does giving a worker time, or waiting until one has really taken the job, end the crash, and how long does a worker need?

**New in the build.**

| switch | does |
|---|---|
| `KYTY_BC5_0388_PUSH_UNTIL_TAKEN_US=<0..500>` | candidate: after a main-thread signal of `JobLoaderSema`, spin until a waiter has returned from the semaphore, at most this long |
| `KYTY_BC5_0388_TRACE=1` | adds two catchers: the time from a signal to a wait's return in five bands, and the count of push spins and how many were taken in time |

`PUSH_SPIN_US` keeps its meaning. The binary's md5 goes into `pins0388.env` (`NORMAL`, FILL until then) after `box0388.sh build`.

**Arms.** All with `JobArenaFix` off, `TRACE=1`, RT on, 180 s, the same route and named save copy, one binary.

| arm | tags | switch |
|---|---|---|
| G, control | G1–G3 | none |
| E | E1–E5 | `PUSH_SPIN_US=500` |
| F | F1–F5 | `PUSH_UNTIL_TAKEN_US=500` |

Order G1 E1 F1 E2 F2 G2 E3 F3 E4 F4 G3 E5 F5, about 4 min each, about 52 min, deadline 75 min.

**Exposure.** An E or F run needs `push spin` lines in its log, or it has not tested the candidate and does not count.

**Rule.** Control at least 2 of 3 at the site, or no conclusion. HOLDS: 5 of 5 NO_CRASH that reached the fight. REFUTED: any crash at the site. OPEN: anything else. A hold is still a 180 s result on this route, and a spin is a host-side workaround until the wake-time bands say why the worker is late. `JobArenaFix` goes only after the maintainer's own fight.

**Local tests so far.** `patch0388.py` applies (5 edits on `semaphore.cpp`), the scripts parse, `check0388.py rule` tried on sample rows, `test_box0388.sh` 14 of 14. The patched units are not compiled until the slot.
