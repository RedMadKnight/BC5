# 0388 — The root of the job-arena crash, so the workaround can go

**Date.** 2026-10-31. **Branch.** `exp/0388-job-arena-root`, base main `5b22f70`. **Status.** Candidates written; nothing run on the box.

**Question.** Why does the title's main thread reach a worker-only job (F444–F454) on this host, and can a host fix make the crash go with `JobArenaFix` off?

**Lead, not shown.** Exp 0360 ruled out host throughput (F461–F463, F470, F471). The title sizes its job system as N = min(max(cpus, 7) − 2, 8), giving 5 workers per entry here. Exp 0358's "7, as on the console" had no source. The host's default thread affinity is `0x7f` (`kernel/pthread.cpp`, `PthreadAttrInit`), seven CPUs, while KytyPS5 8c01d8e and AnyPS5 27c88a8 give `0x1fff`, thirteen. Neither reference is a console measurement. That the title's count comes from the mask is still to be read.

## Switches of the private build

All default off; off leaves the host as it was. `patch0388.py` applies them to private copies of four units; the pure parts are `backend/include/bc5/cpu_model.hpp`.

| switch | does |
|---|---|
| `KYTY_BC5_0388_CPU_MASK` | the default thread affinity: unset, empty or `0` keep `0x7f`, `1` is `0x1fff`, `0x<hex>` a mask inside it |
| `KYTY_BC5_0388_CURRENT_CPU=1` | `sceKernelGetCurrentCpu` returns the real CPU inside the thread's mask, not 0 |
| `KYTY_BC5_0388_APPLY_AFFINITY=1` | a guest mask narrower than the model's is applied to the host thread |
| `KYTY_BC5_0388_PUSH_SPIN_US=<0..500>` | after a main-thread signal of `JobLoaderSema`, a bounded spin so a worker can go first |
| `KYTY_BC5_0388_TRACE=1` | catcher: logs the first 400 affinity reads and sets, and each host mask applied |

**Tests so far.** The pure parts: 65 checks, 0 failed, on the laptop with clang 22 and a small stand-in for Catch2's macros, not Catch2 itself. `patch0388.py` applied to a tree of `f266548` + main's patch; the patched units have not been compiled.

**Box scripts.** `box0388.sh claim|build|release`, with `build0388.py`, `patch0388.py`, `units.sha256` and `backend/include/bc5/cpu_model.hpp` beside it on the box. `test_box0388.sh` tests the claim and release in a temporary HOME with a stand-in `pgrep`: 14 of 14. The `build` step has had `bash -n` only.
