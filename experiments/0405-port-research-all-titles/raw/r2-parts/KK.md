# KK — KytyPS5 `dfec14a` vs OURS: kernel and libKernel / libc side

Path shorthands: **K:** = KytyPS5 source at `dfec14a` (`$R/kps5/src/...`, GPL-2.0); **O:** = OURS
(KytyPlus `f266548` + BC5 patch 0001, `.../scratchpad/e4/full/src/...`). "pre-4644c52" = introducing
commit not in the shallow clone (history starts at `4644c52`, 2026-10-21).

## 1. Method

Diffed (`diff --strip-trailing-cr -w K: O:`) kernel/pthread.cpp/.h, eventQueue.cpp/.h, eventFlag.cpp,
semaphore.cpp, syncOnAddress.cpp/.h, fileSystem.cpp/.h and libs/libKernel.cpp, libC.cpp, errno.h,
guestPrintf.cpp, libDbgAsan.cpp, libRazorCpu.cpp, libUlt.cpp (no diff); read K:kernel/module.h
(KytyPS5 only). Diffs kept in `parts/KK-scripts/*.diff`. Every KytyPS5-only hunk was read and checked
against our code (file:line below). History: `git log dfec14a -- <file>` and `log -S`; the commits that
touch scope after 4644c52 are `e0c5ae0` (_write fd 0-2), `4592e4c` (static rwlock destroy), `13df214`
(stat "/"), `b20850a` (Getinheritsched), `2f885e2` (guest TSC), `8c01d8e` (strcmp NIDs), `bbf96a5`/
`a9edfb6` (RazorCpu), `a875d1b` (IsOpenDescriptor, net side), `22a9392` (SaveData error codes in errno.h:
SaveData agent's scope, not rowed). Everything else is pre-4644c52. The 14 scoped k-only.tsv NIDs (13
"Fiber" + 1 Posix) are all rowed; RazorCpu has no k-only rows (all six NIDs registered by us). NID
names checked against shadPS4 `60c42b9` `src/core/aerolib/aerolib.inl` (names only) where present;
`La9uyZv4Kvw` and `-SrbXpGR1f0` are named from KytyPS5 only. Memory items (memory.cpp) are noted only
where a k-only row requires it (KK28). Pure noise not rowed: logging, `std::rotl` vs our `sha1_rol`,
subsystem-macro vs `Initialize()` lifecycle, `EAPIVERSION`/`ESDKVERSION` rename (same value). Prior BC5
review `docs/ports/related-projects-review.md` §2/§6 had already flagged KK01, KK02 and KK15 (F246);
re-evaluated here under the 11-03 rule.

## 2. Table (ranked by value over cost)

| ID | What | Source | Licence | Ours | Effort | Risk | Class | Value note |
|---|---|---|---|---|---|---|---|---|
| KK01 | `sceKernelAddTimerEvent` (`57ZK+ODEXWY`): third arg is `SceKernelUseconds` by value; periodic `EVFILT_TIMER` (-7), `EV_CLEAR`, `data` = expirations since last read, deadline advanced by interval; re-adding a live timer first accounts expired periods | K:kernel/eventQueue.cpp:142-154, 210-234 (l.221,223), 525-539; eventQueue.h:55 (`interval_ns`); libKernel.cpp:3168; pre-4644c52 | GPL-2.0 | differs: O:libs/bc5LleAgc.cpp:7920-7924 casts the usec integer to `const KernelTimespec*` and makes a one-shot HR timer; O:kernel/eventQueue.cpp:149-155 (no periodic support) | S | L: only callers of this NID change | e4-now | Crash (deref of a small integer as a pointer) or a wrong one-shot timer for any title using kernel periodic timers. Known as F246 |
| KK02 | Equeue wait: a level event (no `EV_CLEAR`, no reset func, no pending copies) is delivered once per wait, not copied into every slot of the array (`else break;`) | K:kernel/eventQueue.cpp:120-127; pre-4644c52 | GPL-2.0 | differs: O:kernel/eventQueue.cpp:130-139 (loop re-copies the same event until `ret >= num`) | S | L | e4-now | Wrong result: a title gets N identical events per wait and may run its handler N times |
| KK03 | Statically initialised rwlock (`*rwlock == NULL`): `PthreadRwlockDestroy` returns OK without allocating (`4592e4c` 2026-10-29 "kernel: destroy untouched static rwlocks without allocation"); `PthreadRwlockTimedrdlock/Timedwrlock` create it on first use (pre-4644c52) | K:kernel/pthread.cpp:2288-2299, 2469-2501; test tests/KernelFileSystemTests.cpp:104-113 @dfec14a | GPL-2.0 | differs: O:kernel/pthread.cpp:2464, 2642, 2654 `EXIT_NOT_IMPLEMENTED(*rwlock == nullptr)` (emulator stop); Rdlock and the other entry points already create (2621-2624, 2664-2665, 2695-2696, 2730, 2769) | S | L | e4-now | Emulator stop on legal calls (`SCE_PTHREAD_RWLOCK_INITIALIZER`). Same pattern still EXITs in `PthreadCondDestroy` O:2955 (KytyPS5 has it too; extend the fix) |
| KK04 | `sceKernelRename` of a file that is open (source or target) proceeds | K:kernel/fileSystem.cpp:1398-1430 (no open-file check); pre-4644c52 | GPL-2.0 | differs: O:kernel/fileSystem.cpp:1456-1457 `EXIT_NOT_IMPLEMENTED(g_files->GetFile(real_*) != nullptr)` | S | L: Linux renames open files; open fds keep the inode | e4-now | Emulator stop on the common "write temp, rename over open save" pattern |
| KK05 | libc `gmtime/localtime/mktime/strftime` on a 9-int (36-byte) guest `struct tm`, converted to/from host `std::tm` | K:libs/libC.cpp:340-444; pre-4644c52 | GPL-2.0 | differs: O:libs/libC.cpp:367-436 passes the guest pointer as host 56-byte `std::tm`: glibc `mktime` writes `tm_gmtoff`/`tm_zone` 20 bytes past a 36-byte guest struct; `strftime` copies 56 bytes (l.429) | S | L: if the guest struct were the 56-byte FreeBSD one, KytyPS5's form only leaves gmtoff/zone unset | e4-now | Guest memory corruption on `mktime`. Guest size 36 is KytyPS5's `static_assert` (l.352), uncited: TODO(verify) |
| KK06 | Notify under the internal lock: mutex unlock wakes while holding `mutex->m`; cond signal/broadcast notify while holding `cond->m` ("so the selected waiter cannot exit and be freed first") | K:kernel/pthread.cpp:1404-1413, 506-525 (comment l.523), 2765-2771; pre-4644c52 | GPL-2.0 | differs: O:kernel/pthread.cpp:1489-1492 (`lock.unlock(); mutex->cv.notify_one();`), 2925-2937, 3029-3037, 3062-3070, 586-593 notify after releasing; a woken thread can destroy the object first (cond: `(*cond)` re-read after destroy set it to NULL) | S | L: standard pattern, a little more contention | e4-now | Rare use-after-free / null-deref crash in destroy-after-unlock patterns (POSIX allows them). Minimal change only; full FIFO rework is KK30 |
| KK07 | `PthreadGetprio`/`PthreadSetprio` (and `PthreadCancel`) return ESRCH for a joined thread (`thread->free`) | K:kernel/pthread.cpp:3410-3413, 3518-3520, 3534-3537; pre-4644c52 | GPL-2.0 | differs: O:kernel/pthread.cpp:3762-3780, 3782-3796 call `pthread_getschedparam` on a joined native handle; Setprio then `Bc5ApplyGuestPriority` (3813) on a possibly reused host TID | S | L | e4-now | Undefined behaviour; priority can land on another thread |
| KK08 | `sceFiberRun`: copy `arg_on_return` and the terminated state before publishing the fiber IDLE | K:libs/libKernel.cpp:2638-2650 ("Copy results before another thread can acquire and resume the fiber"); pre-4644c52 | GPL-2.0 | differs: O:libs/libKernel.cpp:3055-3064 commits IDLE (3055) then reads `returned_fiber->arg_on_return` and state | S | L | e4-now | Wrong return value / spurious `FIBER_ERROR_STATE` when another worker resumes the fiber at once (fiber job systems) |
| KK09 | `open(O_RDONLY\|O_TRUNC)` frees the descriptor it allocated before returning EACCES | K:kernel/fileSystem.cpp:495-498; pre-4644c52 | GPL-2.0 | differs: O:kernel/fileSystem.cpp:513-515 returns without `DeleteDescriptor` | S | L | e4-now | Descriptor leak per failing call |
| KK10 | `write`/`pwrite` on a descriptor opened read-only return EBADF | K:kernel/fileSystem.cpp:722, 940 (`!file->opened \|\| !file->writable`); pre-4644c52 | GPL-2.0 | differs: O:kernel/fileSystem.cpp:713, 838 check only `file == nullptr`; `fwrite` on the read-only `FILE*` gives 0 and the call returns 0 | S | L | e4-now | Wrong result; a retry-until-written loop in a title spins forever |
| KK11 | `stat("/")` answers a directory (`st_mode 040777`) though no mount holds "/" | K:kernel/fileSystem.cpp:1130-1134; `13df214` 2026-11-02 "kernel: report the guest root as a directory in stat" | GPL-2.0 | differs: O:kernel/fileSystem.cpp:950-961 resolves "/" to an empty path, ENOENT | S | L | e4-now | Wrong result for root probes |
| KK12 | posix `_write`/`write` (`FxVZqBAA7ks`, `FN4gaPmuFV8`) to fd 0-2 goes through `KernelWrite` (fd 1/2 to host stdout/stderr, fd 0 EBADF) | K:libs/libKernel.cpp:1363-1365; `e0c5ae0` 2026-10-24 "kernel: send _write to descriptors 0-2 through KernelWrite instead of dropping it" | GPL-2.0 | differs: O:libs/libKernel.cpp:1458-1478 returns `size` for fd 0-2 and writes nothing (`KernelWrite` O:fileSystem.cpp:690-700 already handles 1/2) | S | L: more host console output | e4-now | Guest stdout/stderr lost (diagnostics); fd 0 write reports success |
| KK13 | guest printf: negative `%.*` precision means "no precision" | K:libs/guestPrintf.cpp:527-537; pre-4644c52 | GPL-2.0 | differs: O:libs/guestPrintf.cpp:528 sets precision 0 (`%.*s` with -1 prints nothing) | S | L | e4-now | Wrong `snprintf` results in guest strings (paths, names) |
| KK14 | guest printf `%ls`: UTF-16 guest `wchar_t` converted to UTF-8, precision cannot split a code point | K:libs/guestPrintf.cpp:435-442, 703-740; needs `Common::Utf16ToUtf8(u16string_view)` (K:common/stringUtils.h:166-172; ours has a `const char16_t*` form O:common/stringUtils.h:319); pre-4644c52 | GPL-2.0 | differs: O:libs/guestPrintf.cpp:696-720 prints the UTF-16 bytes as `char*` (first char only for ASCII) | S | L | e4-now | Wrong output for `%ls`. 16-bit guest `wchar_t` is KytyPS5's statement: TODO(verify) |
| KK15 | AMPR completion events on filter `EVFILT_AMPR = -25` | K:kernel/eventQueue.h:21, eventQueue.cpp:570, 598; pre-4644c52. Same value in AnyPS5 (cited in our comment) and KytyPlus HEAD (related-projects-review §6) | GPL-2.0 | differs: O:kernel/eventQueue.cpp:268-274 `AmprEventFilter()` returns `EVFILT_USER` (-11): an AMPR id and a user-event id that are equal collide in one (ident, filter) entry | S | M: exp 0036 saw no change at -25 on the second title; LLE modules may dispatch on the filter | e4-now | Event collision / filter mismatch; three projects agree, console value still TODO(verify). Behind a switch |
| KK16 | Host error mapping: `ENOSPC` and `EFBIG` | K:kernel/fileSystem.cpp:1288-1290; pre-4644c52 | GPL-2.0 | differs: O:kernel/fileSystem.cpp:1137-1148 maps both to EIO | S | L | e4-now | Disk-full reported as EIO (truncate/chmod/utimes/fsync paths) |
| KK17 | libDbgAsan shadow pages: free a shadow page only when the bytes released cover what was allocated, not by call count | K:libs/libDbgAsan.cpp:40-129; pre-4644c52 | GPL-2.0 | differs: O:libs/libDbgAsan.cpp:~40-118 (`count++/--`, l.72, 107-109): a range freed in two pieces drops a shadow page still in use | S | L | e4-now | Crash in ASan-instrumented (debug) titles only |
| KK18 | `fstat` of a special device (`/dev/urandom`, `/dev/random`, ours also `/dev/gc`, `/dev/dipsw`) reports `S_IFCHR 020644` | K:kernel/fileSystem.cpp:1201-1205; pre-4644c52 | GPL-2.0 | differs: O:kernel/fileSystem.cpp:1014, 1019-1030 reports a regular file 0100777 | S | L | e4-now | Wrong result for `S_ISCHR` checks; low value |
| KK19 | Module reference count: a repeated `sceKernelLoadStartModule` of a loaded module takes a reference; `sceKernelStopUnloadModule` only unloads at the last one (`Program::load_count`). `kernel/module.h` exposes both to KytyPS5's libSysmodule (K:libs/libSysmodule.cpp:50, 85; sysmodule agent) | K:libs/libKernel.cpp:1228-1235, 1245, 1278-1281; K:loader/runtimeLinker.h:124; K:kernel/module.h:1-24; pre-4644c52 | GPL-2.0 | differs: O:libs/libKernel.cpp:1319-1325 returns the existing handle without a reference; 1360-1389 unloads on the first stop | S | M: loader struct change | later | Use-after-unload when two users share a module. Not e4-now: a CPU test needs a loadable module image |
| KK20 | `sceKernelStopUnloadModule` with an unknown handle returns ESRCH | K:libs/libKernel.cpp:1273-1276; pre-4644c52 | GPL-2.0 | differs: O:libs/libKernel.cpp:1362-1365 returns OK | S | L | e4-now | Wrong result |
| KK21 | `sceKernelPreadv` (`yTj62I7kw4s`), `sceKernelWritev` (`kAt6VDbHmro`), `sceKernelPwritev` (`mBd4AfLP+u8`) with iovec validation (iovcnt 0..1024, total <= INT_MAX, EFAULT for null base with length), EBADF for a read-only/write-only fd, ESPIPE on sockets, append handling, position kept for p* variants | K:kernel/fileSystem.cpp:822-921, 977-1056; fileSystem.h:36-42 (`KernelIovec`, 16 bytes); libKernel.cpp:3095-3099; tests KernelFileSystemTests.cpp:764-838 @dfec14a; pre-4644c52 | GPL-2.0 | missing (k-only; loader stub returns 0, nothing read or written) | S (port ~180 lines + `readable` flag; borderline M) | L | e4-now | Title sees 0 bytes: EOF on reads, lost data or retry loops on writes |
| KK22 | `sceKernelFtruncate` (`VW3TVZiM4-E`) registration | K:libs/libKernel.cpp:3102; pre-4644c52 | GPL-2.0 | missing registration only: O:kernel/fileSystem.cpp:1064-1105 implements it; only posix `ftruncate` (`ih4CD9-gghM`, O:libs/libKernel.cpp:2401) is registered | S | L | e4-now | Stub returns 0 without truncating: a rewritten save keeps a stale tail (data corruption) |
| KK23 | AIO: `sceKernelAioPollRequest` (`2pOuoWoCxdk`), `...PollRequests` (`o7O4z3jwKzo`), `...WaitRequests` (`lgK+oIWkJyA`, AND=1/OR=2 modes), `...DeleteRequests` (`Ft3EtsZzAoY`); `DeleteRequest` reports ESRCH/EBUSY in `*ret` and frees the slot | K:libs/libKernel.cpp:2815-2823, 2926-3051, 3391-3399; tests KernelFileSystemTests.cpp:840-940 @dfec14a; pre-4644c52 | GPL-2.0 | missing 4 NIDs; differs: O:libs/libKernel.cpp:3347-3390 (WaitRequest treats `*usec == 0` as infinite; DeleteRequest returns EINVAL for a bad id and marks ABORTED without freeing) | S | L: our submissions complete synchronously, so states are terminal | e4-now | Poll stub writes no state: a title polling for completion reads garbage or never sees it (hang). KytyPS5's `NOTIFIED` bit 0x10000 has no source: TODO(verify), leave out |
| KK24 | posix `_umtx_op` (`04AjkP0jO9U`): `UMTX_OP_WAIT` (2) on a 64-bit word with an optional relative `timespec` in `uaddr2`, `UMTX_OP_WAKE` (3); needs `SyncOnAddress::Wait64(nanoseconds)` with a saturating deadline and `ceil` rounding of the remaining slice | K:libs/libKernel.cpp:2108-2138, 3347; K:kernel/syncOnAddress.cpp:50-61, 74, 285-288; syncOnAddress.h:16-17; pre-4644c52. Op numbers: FreeBSD `sys/umtx.h` (public; not re-read here) | GPL-2.0 | missing (k-only); O:kernel/syncOnAddress.cpp:57-77 micro-second deadlines only, `duration_cast` truncates (<1 us spin) | S | L: replace KytyPS5's EXIT on unknown ops/`uaddr != NULL` with EINVAL | e4-now | Stub returns 0 for WAIT: a guest futex lock busy-spins |
| KK25 | `scePthreadAttrGetinheritsched` (`lpMP8HhkBbg`) registration; drop the EXIT on values other than 0/4 | K:libs/libKernel.cpp:3245; K:kernel/pthread.cpp:2005-2015; `b20850a` 2026-11-02 "kernel: export scePthreadAttrGetinheritsched" | GPL-2.0 | missing registration: O:kernel/pthread.cpp:2166-2182 exists (with `EXIT` at 2178) | S | L | e4-now | Stub leaves `*inherit_sched` unwritten; a title copying attributes passes the garbage to `Setinheritsched`, which EXITs (O:kernel/pthread.cpp:2338, emulator stop) |
| KK26 | posix `pthread_attr_setstack` (`-SrbXpGR1f0`) | K:kernel/pthread.cpp:4272-4274; K:libs/libKernel.cpp:2179; pre-4644c52 | GPL-2.0 | missing wrapper and registration; `PthreadAttrSetstack` exists O:kernel/pthread.cpp:2411 | S | L | e4-now | Stub ignores the title's stack: a thread sized for a large own stack runs on the default one (overflow) |
| KK27 | `sceKernelGetAvailableCpumask` (`La9uyZv4Kvw`) returns 0x1FFF (CPUs 0-12) | K:libs/libKernel.cpp:1768-1772, 3416; corroborated AnyPS5 `27c88a8` core/libs/prx/libkernel/Pthread/src/Thread.cpp:1093, docs/dev/debt/libkernel.md:68 (titles pin within 0x1FFB); pre-4644c52 | GPL-2.0 | missing (stub returns 0, an empty mask) | S | L | e4-now | Title computes 0 workers or pins to nothing. CPU 13 availability TODO(verify) |
| KK28 | `sceKernelClearVirtualRangeName` (`mkgXxsoxWHg`): name the range "" | K:kernel/memory.cpp:1893-1907; libKernel.cpp:3118; pre-4644c52 | GPL-2.0 | missing; O:kernel/memory.cpp:2610-2635 has only Set (memory agent's file: coordinate) | S | L | e4-now | VirtualQuery keeps the old name; low value |
| KK29 | `scePthreadCancel` (`qBDmpCyGssE`) registration, with ESRCH for joined threads and host cancellation disabled inside guest mutex waits | K:libs/libKernel.cpp:3221; K:kernel/pthread.cpp:3403-3425, 1317-1350; pre-4644c52 | GPL-2.0 | missing registration; O:kernel/pthread.cpp:3661-3677 exists (no `free` check) | M | H: host `pthread_cancel` unwinds through emulator frames at host cancellation points | later | Stub returns 0 and does not cancel: a title waiting for the cancelled thread to exit can hang |
| KK30 | Mutex FIFO ownership hand-off (waiter list, owner transferred on unlock, no barging) and per-thread cond condition variables | K:kernel/pthread.cpp:368-384, 1275-1416, 417-439, 492-531, 2879-2960; test KernelFileSystemTests.cpp:114-271 @dfec14a; pre-4644c52 | GPL-2.0 | differs: O:kernel/pthread.cpp:1373-1495 (barging, 1 ms poll), 3081-3160 (one cv per cond, notify_all) | M | M: lock fairness and throughput change everywhere | later | Starvation of waiters under contention; thundering herd on signal |
| KK31 | pthread keys: lock-free thread-local value array with key generations; destructors repeated until none runs | K:kernel/pthread.cpp:597-610, 1579-1609, 3931-3997; pre-4644c52 | GPL-2.0 | differs: O:kernel/pthread.cpp:671-698, 1658-1770, 4208-4264 (global mutex, per-key vector scanned by thread id on every get/set; one destructor pass) | M | M | later | Speed of `pthread_getspecific` (hot in engines); POSIX destructor iterations. KytyPS5 loop is unbounded (cap at 4) |
| KK32 | Fiber thread context through a native TLS key instead of C++ `thread_local` ("native lookup must stay fresh when a fiber resumes on another host thread") | K:libs/libKernel.cpp:2358-2425, 2612-2730; pre-4644c52 | GPL-2.0 | differs: O:libs/libKernel.cpp:2706-2713, 2840-3145 (`thread_local` + owner maps, BC5 naked-function fix kept) | M | M | later | Guards against a compiler-cached TLS address after a cross-thread resume; not observed in ours |
| KK33 | Per-thread alternate signal stack and `SA_ONSTACK` for the host fault handler ("keep fault handling off guest stacks, which GPU tracking can make read-only") | K:common/hostException.cpp:41-80, 325; K:kernel/pthread.cpp:1030-1035, 3228-3230; pre-4644c52 | GPL-2.0 | differs: O:common/hostException.cpp:437-450 (no `SA_ONSTACK`, comment "Fault resolution needs the normal thread stack") | M | M: handler depth on a 64 KiB stack | later | A fault on a write-protected stack page kills the process |
| KK34 | Directories as a byte stream: dirents packed at open, `read()` returns them, `lseek` on directories (EINVAL/EOVERFLOW checks), `stat`/`fstat` size = packed size, `getdirentries` under the file mutex rejecting unaligned or past-EOF offsets | K:kernel/fileSystem.cpp:129-173, 519-521, 648-657, 1057-1119, 1152-1156, 1223-1226, 1432-1469; test KernelFileSystemTests.cpp:1341-1442 @dfec14a; pre-4644c52 | GPL-2.0 | differs: O:kernel/fileSystem.cpp:640-642 (read EISDIR), 893-895 (lseek EISDIR), 972/1050 (size 0), 1478-1600 (repacks per call, no lock, may copy partial records) | M | M: TODO(verify) the console's `read()` on a directory | later | Rewind/seekdir of a directory stream fails; stat size 0 |
| KK35 | Path resolution: collapse `//`, match the whole guest path so a mount root works with or without a trailing slash | K:kernel/fileSystem.cpp:339-377; pre-4644c52 | GPL-2.0 | differs: O:kernel/fileSystem.cpp:333-374 (`open("/app0", 0)` without `O_DIRECTORY` resolves to empty: ENOENT), 375-398 | S | M: central path code, BC5 folded-lookup cache | later | Edge-case ENOENT |
| KK36 | `O_CLOEXEC` (0x00100000) at open sets the descriptor's FD_CLOEXEC | K:kernel/fileSystem.cpp:471; test KernelFileSystemTests.cpp:367-394 @dfec14a; pre-4644c52 | GPL-2.0 | differs: O:kernel/fileSystem.cpp:480-483 ignores it (flag kept only via fcntl, 1375-1406) | S | L | e4-now | `F_GETFD` read-back only; low value |
| KK37 | Guest TSC at 1.6 GHz (`--guest-tsc`): TSC reads and `sceKernelGetTscFrequency` scaled, loader rewrites guest RDTSC/RDTSCP | K:kernel/pthread.cpp:183-203; loader/guestInstructionPatcher.cpp (loader); `2f885e2` 2026-11-01 "kernel: add --guest-tsc to run the guest TSC at the PS5's 1.6 GHz" | GPL-2.0 (1.6 GHz claim uncited: TODO(verify)) | differs: O:kernel/pthread.cpp:132-210, 4116-4121 host TSC (minus BC5 pause) | L | H: patches guest code | later | Titles that hard-code 1.6 GHz instead of asking; brief's re-evaluated item |
| KK38 | `setenv` validates and does not touch the host environment | K:libs/libC.cpp:310-326; pre-4644c52 | GPL-2.0 | differs: O:libs/libC.cpp:334-352 calls host `setenv` (guest `getenv` is not HLE'd in either tree) | S | L | later | Host isolation (a guest `TZ` changes our host `localtime`) |
| KK39 | `read` with `nbytes > INT_MAX` returns EINVAL | K:kernel/fileSystem.cpp:648-650; pre-4644c52 | GPL-2.0 | differs: O:kernel/fileSystem.cpp:646-649 (> UINT_MAX EOPNOTSUPP; INT_MAX..UINT_MAX read) | S | L: TODO(verify) the console limit | later | Low |
| KK40 | libc `init_env` takes any `argc` (`Loader::EntryParams`) | K:libs/libC.cpp:260-284 | GPL-2.0 | differs: O:libs/libC.cpp:278-280 EXITs at `argc >= 3` | S | L | later | Host-built argv only; very low |
| KK41 | ZArchive (`.zar`) read-only mounts (EROFS on writes) | K:common/archive.h, kernel/fileSystem.cpp:47, 268, 359-362, 489-493; `cb8042c` 2026-10-22 (launcher) and pre-4644c52 | GPL-2.0 (3rd-party ZArchive dependency licence not checked) | missing | L | M | later | Host feature; BC5 mounts through bc5-mount FUSE, no guest-visible value |
| KK42 | Pro/Trinity answers in `sceKernelIsProspero`-style query and `sceKernelGetOperationMode` | K:libs/libKernel.cpp:1324-1332 (`651ef73` 2026-10-29) | GPL-2.0 | O:libs/libKernel.cpp:1404-1415 (0), 3682-3693 (mode 2, submode 0) = KytyPS5's base-PS5 answers | - | - | skip: already match (O:libs/libKernel.cpp:1404-1415, 3682-3693) | Trinity mode itself is the GPU agent's |
| KK43 | RazorCpu stubs incl. `sceRazorCpuPushMarkerStatic`, `sceRazorCpuSync` | K:libs/libRazorCpu.cpp:43-48 (`bbf96a5`, `a9edfb6`) | GPL-2.0 | all six NIDs registered | - | - | skip: already match (O:libs/libRazorCpu.cpp:615-651, O:libs/libDebug.cpp:20) | - |
| KK44 | libc `strcmp`/`strncmp`/`strcpy` NIDs | K:libs/libC.cpp:774-777 (`8c01d8e` 2026-10-24) | GPL-2.0 | same NIDs | - | - | skip: already match (O:libs/libC.cpp:917-921) | - |
| KK45 | posix `fcntl`/`fsync`/`shutdown` | K:libs/libKernel.cpp:1945-1987, kernel/fileSystem.cpp:603-622 | GPL-2.0 | ours is a superset (varargs fcntl, F_GETFL/SETFL, sockets, errno on shutdown, host fsync) | - | - | skip: already match (O:libs/libKernel.cpp:2304-2383, O:kernel/fileSystem.cpp:1328-1406) | - |
| KK46 | Event flag single-thread gate; semaphore timer placement | K:kernel/eventFlag.cpp:123 (older TOCTOU form); K:kernel/semaphore.cpp:213-218 | GPL-2.0 | ours has the race fix; semaphore results identical | - | - | skip: already match (O:kernel/eventFlag.cpp:123-168, O:kernel/semaphore.cpp:203-220) | - |

## 3. Port specs for the e4-now rows

Common: register in the named `LIB_DEFINE` block of O:libs/libKernel.cpp (Posix 2387, FS 3430, Mem 3453,
Equeue 3493, Pthread 3541, InitLibKernel_1 3695). Tests go in a new file under the base tree's `tests/`
(KytyPlus `f266548` has a CMake test tree: tests/CMakeLists.txt, SyncOnAddressTests.cpp,
EventQueueLifetimeTests.cpp); KytyPS5's tests/KernelFileSystemTests.cpp @dfec14a shows how to start
the pthread subsystem and run guest threads from a host test (TestMutexHandoff, l.167-271). Every
change behind its own switch per the fixes-first rule.

- **KK01** `sceKernelAddTimerEvent`, `57ZK+ODEXWY`, libkernel. `int (KernelEqueue eq, int id,
  KernelUseconds usec, void* udata)`. Adds/updates (ident=id, filter `EVFILT_TIMER` -7) with
  `flags = EV_ADD|EV_CLEAR`, `deadline = now + usec*1000`, `interval_ns = usec*1000`, `data` = number
  of expirations since the last delivery (reset by EV_CLEAR on delivery). Port K:eventQueue.h:55
  (`interval_ns` field), eventQueue.cpp:142-154 (TriggerExpiredTimers counts periods for TIMER and no
  longer skips triggered events), 210-234 (AddEvent: `TriggerExpiredTimers` before re-arm, copy
  `interval_ns`), 525-539. Insert after O:kernel/eventQueue.cpp:528; replace O:libs/bc5LleAgc.cpp:
  7920-7924 body with `EQ::KernelAddTimerEvent(eq, id, usec, udata)` (keep the registration at 7981).
  Test: create equeue, add timer 1000 us, sleep 3.5 ms, wait: one event, filter -7, data 3; wait again
  with timeout 0 after 0.2 ms: none; re-add same id: no duplicate entry.
- **KK02** in O:kernel/eventQueue.cpp:130-134 add `else { break; }` after the pending-events pop
  (K:eventQueue.cpp:124-127). Test: add user event (no EV_CLEAR) id 5, trigger once, wait with num=8:
  `*out == 1`; a second wait returns it again (level stays).
- **KK03** O:kernel/pthread.cpp:2464 replace the EXIT with `if (*rwlock == nullptr) return OK;`
  (K:2295-2298); in Timedrdlock (2635) and Timedwrlock (2647) add the `CreateObject(rwlock,
  Type::Rwlock)` + null check of K:2472-2479 / 2489-2496 before the EXIT. Test: K test
  TestStaticRwlockDestroy (tests @dfec14a:104-113) plus `PthreadRwlockTimedrdlock(&static_null, 1000)
  == OK` and unlock.
- **KK04** delete O:kernel/fileSystem.cpp:1456-1457. Test: mount a temp dir at /savedata0, open
  "/savedata0/a" (O_CREAT|O_RDWR), create "/savedata0/b", `KernelRename(".../b", ".../a")` == OK while
  a is open; `KernelRename(".../a", ".../c")` == OK; read through the old fd still works.
- **KK05** libc `gmtime`/`localtime`/`mktime`/`strftime` (NIDs as registered today in O:libs/libC.cpp;
  only the signatures change to `GuestTm*`). Port K:libs/libC.cpp:340-444 over O:367-436 (keep ours'
  null checks). Test: 36-byte `GuestTm` followed by 32 canary bytes in one buffer; `libc_mktime` returns
  the expected epoch for 2026-11-04 12:00 and the canary is intact; `strftime("%Y-%m-%d")` matches.
- **KK06** O:kernel/pthread.cpp:1489-1492 → `mutex->owner = nullptr; mutex->count = 0;
  mutex->cv.notify_one();` while `lock` is held. 2925-2937, 3029-3037, 3062-3070: call
  `(*cond)->cv.notify_all()` inside the `lock_guard` block (use a local `auto* c = *cond`). 586-593
  likewise. Source: K:pthread.cpp:523 comment, 1404-1413, 2765-2771. Test (ASan build): 2 guest threads
  × 100k rounds of {heap struct with mutex+cond; waiter locks, waits flag; signaller locks, sets flag,
  unlocks, then signals; waiter returns, destroys both, frees} with no ASan report.
- **KK07** add `if (thread->free) return KERNEL_ERROR_ESRCH;` after the null checks in O:pthread.cpp:
  3765-3769 (Getprio), 3785-3787 (Setprio), 3664-3666 (Cancel). Source K:3410-3413, 3518-3520,
  3534-3537. Test: create, join, then Getprio/Setprio == `KERNEL_ERROR_ESRCH`.
- **KK08** O:libs/libKernel.cpp:3055-3064: read `returned_fiber` (from `g_thread_return_fiber`),
  `arg_on_return` and the TERMINATED check into locals before `FiberCommitDeferredIdle()`; write
  `*arg_on_return` afterwards (K:2638-2650). Test: two host-created guest threads alternately
  `sceFiberRun` one fiber that returns its run argument + 1, 100k times; every run returns arg+1, OK.
- **KK09** O:kernel/fileSystem.cpp:513-514 add `g_files->DeleteDescriptor(descriptor);` (K:495-498).
  Test: 1000 × open(path, O_RDONLY|O_TRUNC) == EACCES, then a normal open returns the same lowest fd as
  before the loop.
- **KK10** O:kernel/fileSystem.cpp:713 and 838 → `if (file == nullptr || !file->opened ||
  !file->writable) return KERNEL_ERROR_EBADF;` (K:722, 940); the `EXIT_IF(!file->opened)` below becomes
  dead. Test: open read-only, `KernelWrite` and `KernelPwrite` == EBADF, file unchanged.
- **KK11** O:kernel/fileSystem.cpp after 948: `if (std::strcmp(path, "/") == 0) { *sb = {};
  sb->st_mode = 0040777u; return OK; }` (K:1130-1134). Test: KytyPS5 tests @dfec14a:1121-1122.
- **KK12** `_write` `FxVZqBAA7ks` and posix `write` `FN4gaPmuFV8` (both → `LibKernel::write`, O:2491,
  3666, 3738). `int64_t (int d, const void* buf, size_t nbytes)`: keep ours' `d < 0` EBADF and socket
  branch, then `return POSIX_N_CALL(FileSystem::KernelWrite(d, buf, nbytes));` for every other d (drop
  the fd 0-2 swallow at O:1474-1477). Source K:1363-1365 (`e0c5ae0`). Test: redirect host stdout to a
  pipe, write(1, "x\n", 2) == 2 and the pipe receives it; write(0, ..) == -1 errno EBADF.
- **KK13** O:libs/guestPrintf.cpp:528 → `if (prec < 0) { flags &= ~FLAGS_PRECISION; } else {
  precision = prec; }` (K:530-535). Test: guest-printf ctx `"%.*s|"`, -1, "abc" → "abc|"; 0 → "|".
- **KK14** port K:guestPrintf.cpp:435-442 (template `_strnlen_s`) and 703-740 (`case 's'`); add the
  `u16string_view` overload of `Utf16ToUtf8` (K:common/stringUtils.h:166-172) or adapt ours (O:319).
  Test: `"%ls"` with u"hé" → "hé" (UTF-8); `"%.2ls"` with u"éé" → "é" (2 bytes).
- **KK15** O:kernel/eventQueue.h add `KERNEL_EVFILT_AMPR = -25`; O:eventQueue.cpp:272-274 return it
  when switch `KYTY_BC5_AMPR_FILTER` (default off until a box run) is set. Source K:eventQueue.h:21,
  eventQueue.cpp:570, 598. Test: add user event id 7 and AMPR event id 7 on one queue, trigger AMPR:
  wait returns one event with filter -25, the user event stays untriggered.
- **KK16** O:kernel/fileSystem.cpp:1137-1148 add `file_too_large → EFBIG`, `no_space_on_device →
  ENOSPC` (K:1288-1290). Test: map a synthetic `std::error_code(ENOSPC, generic_category())`.
- **KK17** O:libs/libDbgAsan.cpp: `Shadow::count` → `covered_bytes`, add `ShadowCoverage`, port
  K:libDbgAsan.cpp:40-129 into AllocShadow/FreeShadow. Test: `KernelAlloc(base, 0x100000)`, free
  `[base, base+0x40000)`; the shadow page for `base+0x7ffff` is still mapped (read it), free the rest:
  unmapped (K:139-145 has a test hook).
- **KK18** O:kernel/fileSystem.cpp:1019 branch: `stat.st_mode = 0020644u;` (K:1202). Test: fstat of
  an open /dev/urandom → `(st_mode & 0170000) == 0020000`.
- **KK20** O:libs/libKernel.cpp:1364 `return KERNEL_ERROR_ESRCH;` (K:1275). Test: resolve `QKd0qM58Qes`,
  call with handle 0x7fff, flags 0 → `KERNEL_ERROR_ESRCH`.
- **KK21** `sceKernelPreadv` `yTj62I7kw4s`, `sceKernelWritev` `kAt6VDbHmro`, `sceKernelPwritev`
  `mBd4AfLP+u8`, libkernel. `int64_t (int d, const KernelIovec* iov, int iovcnt[, int64_t offset])`,
  `KernelIovec {void* iov_base; size_t iov_len;}` (16 bytes). Errors: iovcnt <0 or >1024, offset <0,
  total > INT_MAX → EINVAL; iov NULL with iovcnt>0 or base NULL with len>0 → EFAULT; d<3 / closed / not
  readable (preadv) / not writable (writev) → EBADF; socket → ESPIPE; directory → EISDIR; special on
  writev → EINVAL; returns bytes moved; p* variants restore the position; writev honours O_APPEND.
  Port K:fileSystem.h:36-42, fileSystem.cpp:822-921, 977-1056 (drop `DebugCounters`; add
  `File::readable` set in KernelOpen like K:467). Insert after O:kernel/fileSystem.cpp:878;
  register in FS block O:3430. Test: KytyPS5 TestSaveWritev (@dfec14a:764-838) + a preadv case.
- **KK22** `sceKernelFtruncate` `VW3TVZiM4-E` → `FileSystem::KernelFtruncate` in O:FS block (3430).
  `int (int d, int64_t length)`; behaviour already at O:kernel/fileSystem.cpp:1064-1105 (EBADF,
  EINVAL for <0/socket/dir/special, EIO). Test: write 10 bytes, ftruncate 4, fstat size 4.
- **KK23** `sceKernelAioPollRequest` `2pOuoWoCxdk` `int (int32_t id, int32_t* state)`;
  `sceKernelAioPollRequests` `o7O4z3jwKzo` `int (int32_t* ids, int32_t num, int32_t* states)`;
  `sceKernelAioWaitRequests` `lgK+oIWkJyA` `int (int32_t* ids, int32_t num, int32_t* states,
  uint32_t mode, uint32_t* usec)`; `sceKernelAioDeleteRequests` `Ft3EtsZzAoY` `int (int32_t* ids,
  int32_t num, int32_t* rets)`. EFAULT for null arrays, EINVAL for num ∉ 1..128 or (num≠1 and mode ∉
  {1 AND, 2 OR}); per id: invalid or deleted → `KERNEL_ERROR_ESRCH` in the state slot; Delete of an
  unfinished request → EBUSY in `*ret`, finished → OK and slot freed (0). Wait: `usec == NULL` infinite,
  `*usec == 0` poll, remaining time written back, ETIMEDOUT. Port K:libKernel.cpp:2926-3051 without the
  `NOTIFIED` bit (or behind its own switch); replace O:3347-3390. Register in InitLibKernel_1 (O:3742
  area). Test: KytyPS5 TestAioBatches (@dfec14a:840-940) minus the 0x10000 expectations.
- **KK24** `_umtx_op` `04AjkP0jO9U` (name per shadPS4 aerolib.inl:5665), InitLibKernel_1. `int (volatile
  void* obj, int op, uint64_t val, void* uaddr, const void* uaddr2)`; posix -1/errno. op 2: if `*(u64*)obj
  != val` return 0; else sleep until woken / changed / relative `timespec` in uaddr2 elapsed (EINVAL for
  a bad timespec, ETIMEDOUT); op 3: wake `val` waiters; other ops and `uaddr != NULL` → EINVAL (not
  EXIT). Port K:libKernel.cpp:2108-2138, syncOnAddress.cpp:50-61 (ns `MakeDeadline` with saturation),
  74 (`ceil`), 285-288, syncOnAddress.h:16-17. Insert after O:libs/libKernel.cpp:2191 and
  O:kernel/syncOnAddress.cpp:57-62, 293. Test: thread A `_umtx_op(&w, 2, 5, 0, &{0, 50ms})` → -1
  ETIMEDOUT after ≥50 ms; thread B sets w=6 and `_umtx_op(&w, 3, 1, 0, 0)` → A returns 0.
- **KK25** register `lpMP8HhkBbg` → `LibKernel::PthreadAttrGetinheritsched` in O:Pthread block (3541);
  delete O:kernel/pthread.cpp:2175-2179 (`b20850a`). `int (const PthreadAttr*, int*)`: EINVAL for null,
  writes the stored value. Test: AttrInit, Get → 4 or 0 (whatever AttrInit stores), Set(0), Get → 0.
- **KK26** posix `pthread_attr_setstack` `-SrbXpGR1f0`: add in O:kernel/pthread.cpp near 4546
  `int pthread_attr_setstack(LibKernel::PthreadAttr* attr, void* addr, size_t size) { return
  POSIX_PTHREAD_CALL(LibKernel::PthreadAttrSetstack(attr, addr, size)); }` + declaration in pthread.h;
  register in O:Posix block (2387). Source K:pthread.cpp:4272-4274, libKernel.cpp:2179. Test: set a
  1 MiB host buffer, `pthread_attr_getstack` returns it; create a thread and check its rsp is inside.
- **KK27** `sceKernelGetAvailableCpumask` `La9uyZv4Kvw`, InitLibKernel_1, `uint64_t (void)`, returns
  0x1FFF (K:1768-1772). Test: resolve and call → 0x1FFF.
- **KK28** `sceKernelClearVirtualRangeName` `mkgXxsoxWHg`, Mem block (O:3453), `int (const void* addr,
  uint64_t len)`: same as ours' Set with name "" (O:kernel/memory.cpp:2630-2632) under
  `g_memory_operation_mutex`, returns OK (K:memory.cpp:1893-1907). Coordinate with the memory agent.
  Test: map flexible memory, Set name "x", Clear, VirtualQuery name == "".
- **KK36** O:kernel/fileSystem.cpp after 483: `file->close_on_exec = (static_cast<uint32_t>(flags) &
  0x00100000u) != 0;` (K:471). Test: KytyPS5 TestFileDescriptorFlags (@dfec14a:367-394).

## 4. Totals

| Class | Rows |
|---|---|
| e4-now | 28 (KK01-18, KK20-28, KK36) |
| later | 13 (KK19, KK29-35, KK37-41) |
| skip: already match | 5 (KK42-46) |
| skip: provenance | 0 |
| in e4 / done | 0 (none of the in-flight items fall in this scope) |

e4-now: 28 × S, about 3-4 days including the tests. later: 5 S (KK19, KK35, KK38, KK39, KK40) + 6 M
(KK29-KK34) + 2 L (KK37, KK41) ≈ 5 × 0.5 h + 6 × 1 day + 2 × 3 days ≈ 12-13 days; without KK41 (no
value for BC5) ≈ 9-10 days.
