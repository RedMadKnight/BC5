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
- **Run N1** (`s6n0338.sh`, exp 0336's chain):
  - the S6N route with RT off, 600 s, the normal candidate, `BC5_IMPORT_LOG`;
  - a private working directory, `_SaveData` and learned file;
  - the live saves (5383c9deb3c38e9e) compared only;
  - the kernel stream in the session (`stream0338.sh`).
- **`compare0338.py`** lists the imports whose path or implementation differs between exp 0336 R1's log and N1's.
- **`int0338.sh`** is the integration script (D19), for the maintainer's yes.
  - Guards: the five files' md5s, both shared binaries' md5s, a passed N1.
  - It backs up the five files and both binaries.
  - It makes a diff from the tree's files and the private build's copies, which keeps CRLF. It runs `git apply --check`,
    then `git apply`, and checks that each file then equals the copy the private binaries were built from.
  - It builds both shared builds (`cmake --build … -j8`, nice 10) and writes the candidate patch 0001.
