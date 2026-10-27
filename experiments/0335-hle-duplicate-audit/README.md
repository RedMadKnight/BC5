# 0335 — are the host functions the second title uses implemented twice, once in KytyPlus and once by BC5?

*Number claimed by the cloud supervisor, 2026-10-26 22:03. The maintainer asked: "Sprawdź czy implementację funkcji z
których gra korzysta a które niedawno doszły - nie są przez nas inaczej zaimplementowane już w emulatorze. Być może
cześć funkcjonalności z emulatora/hosta trzeba przepisać jako odnośniki do implementacji funkcji lub na odwrót." An
offline read of the shared tree; no build, no run.*

**Question.** The tree registers every HLE function with `LIB_FUNC(nid, function)`. Patch 0001 has added such
registrations in many experiments, most recently 0327–0329 (the title's missing imports). Three questions:
- Does any NID now have two implementations?
- Which one does the title get?
- Does any recent addition duplicate host code that already does the same work under another NID?

**Setup.**
- **The tree:** `~/src/KytyPlus` (f266548 plus the uncommitted patch: 96 files, 19 of them new; `raw/tree-git-status.txt`).
  `src/`, `include/` and `CMakeLists.txt` were copied into the session over ssh, read only. Patch 0001 is main's copy
  (`backend/kytyplus-patches/0001-bc5-lle-agc.patch`, which matches the shared builds, D19).
- **`regs0335.py`** parses every `LIB_FUNC` and `LIB_OBJECT`, with its file, line and `LIB_DEFINE` block.
  - The library comes from the `LIB_VERSION` or `LIB_NAME` in scope, or from a `LIB_USING`.
  - The load order follows `LIB_LOAD(…)` and direct `Ns::InitX(s)` calls from `Libs::InitAll` (libs.cpp:93, called by
    emulator.cpp:252). That is the order of `SymbolDatabase::Add`.
  - Blocks that nothing calls are dead.
  - It found all 3,131 registrations that a grep finds (`raw/regs.jsonl.gz`).
  - Its library labels are textual. `#if`/`#else` branches with braces mislabel some blocks: the pthread block at
    libKernel.cpp:3518 is in `namespace Libs`, so its library is "libkernel" (line 61), not the "Coredump" the parser
    gives it. The labels quoted below were checked in the code by hand.
- **`report0335.py`** makes the tables (`raw/report.txt`). The patch's own registrations are its `+` lines.
- **How a duplicate resolves** (`src/loader/symbolDatabase.cpp`, `runtimeLinker.cpp`):
  - `SymbolDatabase::Add` keys a record by NID + library + version + module + type, with `insert_or_assign`. So
    `Find` (the exact match, `RuntimeLinker::Resolve` :1880) returns the **last** registration of the same full name.
  - `FindByNid` and `FindByName` walk the list from the start, so they return the **first** registration with that
    NID, in any library. The linker's "PS5 NID fallback" (:1849, used when the exact match and the loaded modules'
    exports both fail) and `sceKernelDlsym` (libKernel.cpp:181) use them.
  - So two implementations of one NID can each be reached, depending on the path.

**Result.**
- **3,131 registrations.**
  - 1,899 are reached from `InitAll`.
  - 1,232 sit in 35 `LIB_DEFINE` blocks that nothing calls, so they never enter the symbol database.
  - Patch 0001 added 303 (file, NID) registrations, the most in NpCppWebApi (137), SaveData (54), bc5LleAgc (33),
    Json2 (28), libKernel (24) and libNet (20).
- **The patch's additions do not collide with the host.**
  - No NID the patch registers is registered elsewhere with a different function.
  - Its 26 SaveData_native NIDs are aliases of the same `SaveData::` functions (libSaveData.cpp:1256 against :1290),
    as libc and LibcInternal share `abort`, `cxa_atexit`, `cxa_finalize` and `std_execute_once`.
- **The recent posix entry points already call the host's implementation:**
  - exp 0329's `sleep` → `LibKernel::KernelSleep`;
  - `fsync` → `POSIX_CALL(FileSystem::KernelFsync)`;
  - `rmdir` → `POSIX_CALL(FileSystem::KernelRmdir)`;
  - `shutdown` → `Net::Shutdown`;
  - `fcntl` → `FileSystem::KernelFcntl`.

  BC5's own libkernel functions (bc5LleAgc.cpp:9101) call the host's too:
  - `Mmap` → `Mem::KernelMapNamedFlexibleMemory`;
  - `ReleaseFlexibleMemory` → `Mem::KernelMunmap`;
  - `AllocateToolMemory` → `Mem::KernelAllocate…DirectMemory`;
  - `Kevent` → `Gen5Driver::GraphicsDriverAdd/DeleteEqEvent`;
  - `AddTimerEvent` → `EQ::KernelAddHRTimerEvent`.

  BC5's `GetAppInfo` zero-fills, as the host's `sysGetAppInfo` does (syscallExtended.cpp:362).
- **Where two implementations differ** (all upstream KytyPlus unless marked):
  1. **posix `chmod`** (`z0dtnPxYgtg`, libKernel.cpp:3194) does nothing and returns OK. The sce `KernelChmod`
     (`fgIsQ10xYVA`, added by exp 0327) changes the file. The posix entry should be
     `POSIX_CALL(FileSystem::KernelChmod(…))`, as `rmdir` is.
  2. **posix `pthread_rwlock_tryrdlock`** (`SFxTMOfuCkE`, the Posix block, libKernel.cpp:2454) points straight at
     the sce `PthreadRwlockTryrdlock` (pthread.cpp:2659).
     - That function returns SCE codes (`KERNEL_ERROR_EINVAL`) where a posix caller expects errno numbers.
     - It stops the emulator on a statically initialised lock (`EXIT_NOT_IMPLEMENTED(*rwlock == nullptr)`).
     - Exp 0327 added the sce NID `XD3mDeybCnk` to the same function. The posix NID still has no posix wrapper.
  3. **posix NIDs registered under "libkernel" with sce functions:** `pthread_self`, `pthread_getstack`,
     `pthread_attr_setstacksize`, `pthread_attr_getschedparam`, `pthread_rwlock_wrlock` and `pthread_cond_signal`
     (libKernel.cpp:3530–3601).
     - The Posix block registers the same NIDs with posix wrappers (:2410–2460).
     - An import from "libkernel" gets the sce function, with SCE codes and the static-init stop. An import from
       Posix gets the wrapper.
     - The NID fallback and `sceKernelDlsym` get the libkernel one, which comes first.
  4. **`ShareFeaturePermit`** (`YBiIdcDPrxs`) has two versions in the same library "Share":
     - libNet.cpp:4012 returns 0 always (its block also registers `ShareInitialize` and `ShareTerminate`);
     - libShare.cpp:201 checks the flags.

     `Find` gets libShare.cpp's (registered last), and the NID fallback gets libNet.cpp's.
  5. **`GetCompiledSdkVersion`** (patch, bc5LleAgc.cpp) returns the constant 0x0A000000. Its own `TODO(bc5)` says to
     read the eboot's process parameter, which the host already serves (`KernelGetProcParam`, `959qrazPIrg`).
  6. **Same behaviour, written twice:**
     - two identical `clock_gettime` bodies (libKernel.cpp:1883 and :1945);
     - `__error` from libc (`LibC::libc_error`) and from libkernel (`get_error_addr`), both returning
       `Posix::GetErrorAddr()`.
- **Dead blocks that duplicate live libraries** (`raw/report.txt`):
  - libNp.cpp, touched by the patch, defines NpManager (27 NIDs), NpAuth, NpCommon, NpTrophy (87), NpTus (142),
    NpParty and others. Nothing calls them; the live NP libraries are libNet.cpp's `LibNp*`. For example, libNet.cpp's
    `NpGetAccountLanguage2` is live, and libNp.cpp's `sceNpGetAccountLanguage` is dead.
  - Ime (41 NIDs found only there), Ngs2, Voice, RazorCpu, Random, SharePlay, GameLiveStreaming, WebBrowserDialog and
    SigninDialog each have a dead block beside a live one.
  - A NID found only in a dead block never resolves: the title would get a stub although code exists.
- **Not answered here: which of these the title imports.** The launchers run with `--printf-direction Silent`, so the
  linker's "PS5 NID fallback" lines are not logged. Exp 0327 kept only the 197 imports that ended as stubs. None of the
  NIDs in items 1–5 is among them, so each resolved to one of the implementations above, or to a loaded module's
  export.

**Verdict.**
- The functions BC5 added recently are written as calls into the host's implementations, not as second copies. The
  one exception is `GetCompiledSdkVersion`'s constant, which should read the host's process parameter.
- The duplicates with different behaviour are upstream: posix `chmod`, posix `pthread_rwlock_tryrdlock`, the posix
  NIDs under "libkernel", and `ShareFeaturePermit`. Each should become one implementation, with the other entry
  calling it.
- The 35 dead blocks should be wired in or deleted. Which way depends on whether the title imports their NIDs.
- **Next:** a diagnostic that writes, once per start, every import the linker resolves (library, NID, path: exact,
  module, NID fallback or stub, and the implementation's `dbg_name`). One RT-off run would then show which of items
  1–5 and which dead-block NIDs the title really reaches. Every fix after that is an integration (D19) and needs the
  maintainer's yes.

**Addendum (2026-10-26, exp 0338: two NID names corrected).** Item 3's list of "posix pthread NIDs under libkernel"
named two NIDs wrongly. The tree's NID algorithm (`kernel_symbol_to_nid`, libKernel.cpp:156) gives:
- `-quPa4SEJUw` is `scePthreadAttrGetstack` (posix `pthread_attr_getstack` is `vQm4fDEsWi8`);
- `FXPWHNk8Of0` is `scePthreadAttrGetschedparam` (posix `pthread_attr_getschedparam` is `qlk9pSLsUmM`).

So libkernel's sce registrations of these two are right. The wrong ones are the Posix block's (:2460 and :2435), which
give these sce NIDs posix wrappers. Four posix NIDs sit under "libkernel" with sce functions: `pthread_self`,
`pthread_attr_setstacksize`, `pthread_rwlock_wrlock` and `pthread_cond_signal`.
