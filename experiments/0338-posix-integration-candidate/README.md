# 0338 — the integration candidate: exp 0336's fixes and the posix NIDs on the posix entry points, in private builds

*Number claimed by the cloud supervisor, 2026-10-26 22:54. The maintainer's choice: "a) Integracja do wspólnych buildów
(D19): poprawki z 0336 oraz przepięcie tych 16 funkcji posix na istniejące wrappery. Najpierw prywatny build i przebieg
testowy, potem Twoje „tak" na wymianę wspólnych binarek".*

**Question.**
- Do exp 0336's fixes, with the posix NIDs moved to the tree's posix entry points, build in both shared configurations
  (normal and lean)?
- Do the title's 16 libScePosix imports (F408) then resolve exactly, to posix code?
- Does the bench route still pass?

**Setup.**
- **`patch0338.py`** edits five shared-tree files, each md5-checked; `raw/patch_0338.diff` is the result.
  `kernel/pthread.cpp` is CRLF: it is edited as LF and written back as CRLF.
- **Exp 0336's fixes**, without its counting entries:
  - posix `chmod` (`z0dtnPxYgtg`) is `POSIX_CALL(FileSystem::KernelChmod)`;
  - posix `pthread_rwlock_tryrdlock` (`SFxTMOfuCkE`) goes to a new posix wrapper;
  - `PthreadRwlockTryrdlock` and `PthreadRwlockTrywrlock` create a statically initialised lock on first use;
  - `sceKernelGetCompiledSdkVersion` reads the process parameter (TODO(verify) the layout);
  - `BC5_IMPORT_LOG=<file>` stays as an off-by-default diagnostic.
- **The Posix block** (library "Posix", which libScePosix imports match after the linker drops "libSce") registers the
  twelve NIDs the 16 imports name, on posix code the tree already has:

  | NID | name | implementation (was, through the NID fallback) |
  |---|---|---|
  | `wuCroIGjt2g` | open | `LibKernel::open` (`FileSystem::KernelOpen`) |
  | `bY-PO6JhzhQ` | close | `LibKernel::close` (`FileSystem::KernelClose`) |
  | `FN4gaPmuFV8` | write | `LibKernel::write` (`FileSystem::KernelWrite`) |
  | `Oy6IpwgtYOk` | lseek | `Posix::lseek` (the same) |
  | `mqQMh1zPPT8` | fstat | `Posix::fstat` (the same) |
  | `HoLVWNanBBc` | getpid | `LibKernel::getpid` (the same) |
  | `QcteRwbsnV0` | usleep | `LibKernel::KernelUsleep` (the same; it returns 0 always) |
  | `6XG4B33N09g` | sched_yield | new `Posix::sched_yield`, int 0 (the void `PthreadYield`) |
  | `RXXqi4CtF8w` | pthread_cond_destroy | new `Posix::pthread_cond_destroy` (`PthreadCondDestroy`) |
  | `27bAgiJmOh0` | pthread_cond_timedwait | `Posix::pthread_cond_timedwait` (the same) |
  | `iGjsr1WAtI0` | pthread_rwlock_rdlock | `Posix::pthread_rwlock_rdlock` (`PthreadRwlockRdlock`) |
  | `EgmLo6EWgso` | pthread_rwlock_unlock | `Posix::pthread_rwlock_unlock` (`PthreadRwlockUnlock`) |

  The names come from the tree's NID algorithm (`kernel_symbol_to_nid`, libKernel.cpp:156).
- **The libkernel block's posix NIDs move to the same entry points.** These are the NIDs whose names are posix but
  whose registration was an sce function: the seven above, plus `pthread_attr_setstacksize`, `pthread_rwlock_wrlock`
  and `pthread_cond_signal`. So one posix NID has one implementation in every library, and the NID fallback and
  `sceKernelDlsym` give the same one. `pthread_self` and `usleep` behave the same either way and stay.
- **`LibKernel::write` returns -1/EBADF for a negative descriptor**, as `close` and `read` do. It stopped the emulator
  (`EXIT_NOT_IMPLEMENTED`), and the posix `write` NID now comes to it.
- **Not changed:**
  - `-quPa4SEJUw` and `FXPWHNk8Of0` are `scePthreadAttrGetstack` and `scePthreadAttrGetschedparam`. These are sce names,
    so libkernel's sce registrations of them are right. This corrects exps 0335 and 0336 (their addenda, F407, F408).
    The Posix block's posix-wrapper registrations of these two stay: nothing imports them from libScePosix.
  - `ShareFeaturePermit`'s two versions and the 35 dead blocks (F407).
- **Built** (`run0338.sh build`, `build0338.py`, 22:57–22:59), four units each, with the private sources first on the
  include path for the patched `pthread.h` (declarations added only). Each links from a shared build's other objects:

  | binary | from | md5 |
  |---|---|---|
  | `~/bc5-work/exp0338/kyty_emulator` | the shared normal objects (4a146894) | **8e5eea47** |
  | `~/bc5-work/exp0338/lean/kyty_emulator` | the shared lean objects (c28cdd3c) | **d445c67e** |

  The warnings (9 and 12) are all in older code (`raw/build-normal.out`, `raw/build-lean.out`).
- **Runs N1 and L1** (`s6n0338.sh`, exp 0336's chain), on the maintainer's "Najpierw prywatny build i przebieg testowy":
  - the S6N route with RT off and `BC5_IMPORT_LOG`;
  - N1: the normal candidate, 600 s; L1: the lean candidate, 240 s. The lean build keeps no GPU journal, so L1 has no
    flips and no RT-off drop lines; its RT-off check is the configuration and `KYTY_BC5_RT=0`;
  - a private working directory, `_SaveData` and learned file, each run starting from fresh route saves;
  - the live saves (5383c9deb3c38e9e) compared only;
  - the kernel stream in the session (`stream0338.sh`).
- **`compare0338.py`** lists the imports whose path or implementation differs between exp 0336 R1's log and N1's.
- **`int0338.sh`** is the integration script (D19), for the maintainer's yes.
  - Guards: the five files' md5s, both shared binaries' md5s, a passed N1.
  - It backs up the five files and both binaries.
  - It makes a diff from the tree's files and the private build's copies, which keeps CRLF. It runs `git apply --check`,
    then `git apply`, and checks that each file then equals the copy the private binaries were built from.
  - It builds both shared builds (`cmake --build … -j8`, nice 10) and writes the candidate patch 0001.

**Result.**
- **N1 (23:00:58–23:11:15) passes:**
  - 600 s at **38.0 flips/s** (median 40.3 per 10 s); exp 0336 R1 ran 38.8 (41.4), and S6N runs since exp 0330 range
    35.3–38.8;
  - no crash line, kernel GPU line, TIMEOUT or devcoredump; the kernel stream holds only network notices;
  - 5,721 RT-off drop lines; the private learned file unchanged;
  - the live saves unchanged; the launcher and bc5-mount gone after it.
- **L1 (23:12:46–23:16:58) passes:**
  - 240 s with no crash line, kernel GPU line or devcoredump;
  - GTT at 11.9 GiB at the end, as in every full start;
  - the live saves unchanged; the launcher and bc5-mount gone after it.
- **The imports** (`raw/N1-vs-R1-imports.txt`, `compare0338.py`): the same 1,935 imports from 7 programs.

  | path | exp 0336 R1 | N1 | L1 |
  |---|---|---|---|
  | hle (exact host registration) | 880 | **896** | 896 |
  | module | 897 | 897 | 897 |
  | nid-fallback | 148 | **132** | 132 |
  | unresolved (stub) | 10 | 10 | 10 |

  24 imports changed:
  - **The 16 libScePosix imports** (eboot.bin 4, libcohtml.Prospero.prx 12) now resolve exactly ("hle"), each to the
    implementation in the Setup table. Before, they went through the NID fallback.
  - **Five libkernel imports moved from sce functions to the posix entry points:**
    - libc.prx's `pthread_rwlock_rdlock`, `_unlock` and `_wrlock`;
    - libSceAgcDriver.sprx's `open` and `close`.
  - **Three show only that exp 0336's counting entries are gone:** `sceKernelChmod`, `scePthreadRwlockTryrdlock` and
    `scePthreadAttrGetschedparam`, the same sce function as before.
  - L1's imports equal N1's, path for path.
- `GetCompiledSdkVersion` gives 0x09000040 from the process parameter, as in exp 0336.

**Verdict.**
- **The candidate builds in both shared configurations and passes the bench route in both.**
  - Every posix import of the title now resolves exactly to a posix implementation. The 132 remaining fallbacks are
    library-name differences (F408).
  - No behaviour on the route changed that the bench can see. The changes are in error paths (-1/errno instead of SCE
    codes, `sched_yield`'s return value) and in `close` and `write` on sockets and the standard descriptors. The route
    does not reach them.
- **Not tested:** ASTRO BOT and the other launchers' titles. They use the same shared builds, so their posix imports
  change the same way.
- **Next:** the integration (`int0338.sh`: both shared builds, the candidate patch 0001), on the maintainer's yes (D19).
  Exp 0337's language setting is not in this candidate.

**Addendum (2026-10-27, after the integration, F410).** On the maintainer's "Tak" to running `int0338.sh` (BOX-QUEUE
206), 06:35–06:38 (`raw/int.out`, `raw/integration/`):
- **Guards:** the five tree files and both shared binaries had their expected md5s, and N1 and L1 had passed.
- **The diff** (382 lines) was made from the tree's files and the private build's copies, so it kept
  `kernel/pthread.cpp`'s CRLF (4,758 → 4,784 CRs). `git apply --check` and `git apply` succeeded, and each file then
  equalled the copy the private binaries were built from.
- **Both shared builds were rebuilt** (`cmake --build … -j8`, nice 10). The normal build compiled 44 units, the
  `pthread.h` dependents among them. There were no errors; the warnings are in older code.

  | build | before | after |
  |---|---|---|
  | normal (`kytyplus-build`) | 4a146894 | **21e8bd22** |
  | lean (`kytyplus-build-lean`) | c28cdd3c | **379a92b8** |

  These are not the private binaries' md5s: the shared builds recompiled every dependent unit, where the private
  builds linked the shared objects.
- **Patch 0001 on main** is the tree's diff against f266548 after the integration: 58,501 lines, md5 a20fcc2d, 96
  files. Against main's previous copy, only the five integrated files differ.
- **The undo:** copy back the two binaries and five files from `~/bc5-work/exp0338/integration/`, then rebuild both.
- The launchers and the test shortcut are unchanged. Not run yet: a session on the integrated builds.
