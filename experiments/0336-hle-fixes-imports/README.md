# 0336 — exp 0335's HLE fixes in a private build, and what the second title really imports and calls

*Number claimed by the cloud supervisor, 2026-10-26 22:08. The maintainer's words after exp 0335: "B, a następnie
przebieg w celu weryfikacji co gra naprawdę wywołuje".*

**Question.**
1. Do exp 0335's fixes build and run? They are:
   - posix `chmod` through `KernelChmod`;
   - a posix wrapper for `pthread_rwlock_tryrdlock`;
   - `GetCompiledSdkVersion` from the process parameter.
2. Which implementation does each of the title's imports get?
3. Which of the audited functions does the title call?

**Setup.**
- **`patch0336.py`** changes four shared-tree files, each md5-checked. `kernel/pthread.cpp` is CRLF: it is edited as LF
  and written back as CRLF (`raw/patch_0336.diff`). The changes:
  - `libs/libKernel.cpp`:
    - posix `chmod` (`z0dtnPxYgtg`) is `POSIX_CALL(FileSystem::KernelChmod)`;
    - `SFxTMOfuCkE` goes to the new posix wrapper;
    - counting entries (template `Diag0336<F, K>`, each calling the same function as before) for `sceKernelChmod`,
      `scePthreadRwlockTryrdlock` and the six posix NIDs that "libkernel" registers with sce functions.
  - `kernel/pthread.cpp`:
    - `PthreadRwlockTryrdlock` and `PthreadRwlockTrywrlock` create a statically initialised lock on first use, as
      `PthreadRwlockRdlock` does, instead of `EXIT_NOT_IMPLEMENTED`;
    - `Posix::pthread_rwlock_tryrdlock` (`POSIX_PTHREAD_CALL`).
  - `libs/bc5LleAgc.cpp`: `sceKernelGetCompiledSdkVersion` takes the high half of the u64 at +0x10 of the program's
    process parameter (or its low half when the high is 0), within [0x01000000, 0x20000000), else the old 0x0A000000.
    The layout is TODO(verify). The header it read is journaled.
  - `loader/runtimeLinker.cpp`: `BC5_IMPORT_LOG=<file>` (off by default) journals:
    - every import `RuntimeLinker::Resolve` resolves, once per program and name, with the requested library and
      module, the path (`hle`: the exact host registration; `module`: a loaded module's export; `nid-fallback`: by NID
      alone, first registration wins; `unresolved`: a stub) and the implementation's `dbg_name`;
    - the helpers `Loader::Bc5DiagCall`, a call count journaled at 1, 2, 4, 8, … calls.
- **Built** (`run0336.sh build`, `build0336.py`, 22:16–22:17): the four units plus a link from the shared normal
  objects (4a146894) give `~/bc5-work/exp0336/kyty_emulator` **0aa094fe**. All 9 warnings are in older code
  (`raw/build.out`).
- **Run R1** (`s6n0336.sh`, exp 0333's chain):
  - the S6N route from exp 0196's route saves, with RT off, in a private working directory with its own `_SaveData`
    and learned file;
  - 600 s, with `BC5_IMPORT_LOG=raw/R1-imports.txt`;
  - the live saves (5383c9deb3c38e9e) compared only;
  - the kernel stream in the session (`stream0336.sh`).

**Result (R1, 22:18:02–22:28:15).**
- **Pass:**
  - 600 s at 38.8 flips/s, with no crash line, kernel GPU line, TIMEOUT or devcoredump;
  - 5,806 RT-off drop lines; the private learned file unchanged;
  - the live saves unchanged;
  - the launcher and bc5-mount gone after it.
- **The process parameter** (`R1-imports-summary.txt`, "procparam"): size 0x60, magic 0x4942524f ("ORBI"), 5
  entries, and the u64 at +0x10 = 0x0900004011590001.
  - `GetCompiledSdkVersion` therefore returned **0x09000040** instead of 0x0A000000. libSceAgcDriver.sprx called it
    twice at start, and the run behaved as before.
  - The title's `sce_sys/param.json` has `sdkVersion` "0x0000000000000000", so it confirms neither half. The layout
    stays TODO(verify).
- **1,935 imports from 7 programs**
  (`raw/R1-imports.txt.gz`, `raw/R1-imports-summary.txt`):

  | path | imports |
  |---|---|
  | hle (exact host registration) | 880 |
  | module (a loaded module's export) | 897 |
  | nid-fallback (by NID alone, first registration) | 148 |
  | unresolved (stub) | 10 |

  - **The 10 stubs** are eboot.bin's ten unnamed NpCppWebApi NIDs (F393, F401). None of them has code in exp 0335's
    dead blocks.
  - **Most fallbacks are only a name difference:**
    - the title asks for `libSceLibcInternal`, `libSceJson2`, `libSceCoredump`, `libSceSsl` or
      `libSceLibcInternalExt`;
    - the host registers `libc`, `Json2`, `Coredump`, `Ssl` or `LibcInternal`;
    - 81 of them resolve to the loaded libc.prx's exports.
  - **The fallbacks that change behaviour:** 16 imports from `libScePosix` (eboot.bin and libcohtml.Prospero.prx)
    resolve to registrations that libkernel holds **with sce functions**:
    - `close` → `FileSystem::KernelClose`; `open` → `KernelOpen`; `write` → `KernelWrite`;
    - `usleep` → `KernelUsleep`;
    - `pthread_cond_destroy`, `pthread_rwlock_rdlock`, `pthread_rwlock_unlock` and `pthread_yield` → the sce ones.

    On success these behave as the posix calls. On an error they return an SCE code (0x8002xxxx, negative) instead
    of -1, and set no errno. Posix-style implementations exist for most of them and are registered under other NIDs:
    - `LibKernel::open`, `close` and `write` (libKernel.cpp:1458–1484) are registered under `6c3rCVE-fTU`,
      `NNtFaKJbPt0` and `FxVZqBAA7ks`;
    - `Posix::pthread_rwlock_rdlock` and `unlock` (pthread.cpp:4652–4662) are not registered for those NIDs.
- **The audited NIDs (exp 0335):**

  | function | imported by, library | called in 600 s |
  |---|---|---|
  | `sceKernelGetCompiledSdkVersion` | libSceAgcDriver.sprx, libkernel | 2 (now 0x09000040) |
  | posix `pthread_attr_getschedparam` (`FXPWHNk8Of0`) | eboot.bin, **libkernel** → the sce function | 4–7, at t ≈ 2.7 s |
  | posix `pthread_rwlock_tryrdlock` (`SFxTMOfuCkE`) | libcohtml.Prospero.prx, libScePosix → the new wrapper | 0 |
  | `pthread_rwlock_wrlock` (`sIlRvQqsN2Y`) | libc.prx, libkernel → the sce function; libcohtml, libScePosix → the posix wrapper | 0 through libkernel |
  | `sceKernelChmod`, `scePthreadRwlockTryrdlock` | libc.prx, libkernel | 0 |
  | `pthread_self`, `pthread_cond_signal`, `pthread_attr_setstacksize` | eboot.bin and libcohtml, libScePosix → the posix wrappers | counted only through libkernel: 0 |
  | `__error` | five programs, libkernel → `get_error_addr` (the same errno as libc's) | — |
  | posix `chmod`, `ShareFeaturePermit` | not imported | — |

**Verdict.**
- **Exp 0335's three fixes build and run on the bench route, but the route does not exercise two of them.**
  - Posix `chmod` is not imported at all.
  - The posix `pthread_rwlock_tryrdlock` and the `Try*lock` static-lock change were not called in 600 s.
  - `GetCompiledSdkVersion` is called. It now answers 0x09000040 from the program's own process parameter, with no
    visible change on this route.
- **What the title really reaches of the audit's duplicates:**
  - one posix function on an sce implementation: `pthread_attr_getschedparam` from libkernel, a few calls at start;
  - the larger, new finding: **16 posix imports from libScePosix that the NID fallback gives to sce file and pthread
    functions**, among them `open`, `close`, `write` and `pthread_rwlock_rdlock`/`unlock`, which run all the time.
- The fix for most of these is the maintainer's "odnośniki": register the posix NIDs on the posix wrappers the tree
  already has (`LibKernel::open/close/write`, `Posix::pthread_rwlock_rdlock/unlock`). The rest (`usleep`,
  `pthread_cond_destroy`, `pthread_yield`) need thin `POSIX_CALL` wrappers.
- Every change to the shared builds is an integration (D19) on the maintainer's yes. The diagnostic import log can
  stay as an off-by-default switch.
