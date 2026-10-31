# 0388 — The root of the job-arena crash, so the workaround can go

**Date.** 2026-10-31. **Branch.** `exp/0388-job-arena-root`, base main `5b22f70`. **Status.** Root read, private build `88010666` made; the runs below are fixed before they start.

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
