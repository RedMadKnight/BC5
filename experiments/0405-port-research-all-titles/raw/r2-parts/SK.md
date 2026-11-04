# SK -- sharpemu 514d766 vs OURS, kernel/libc side (pthread, equeue, sema, sync, file, runtime, sockets, libc, Ult, Fiber)

## 1. Method

Read-only. Pass 1: every `s-only.tsv` row in libc (55), libKernel (34) and libSceUlt (26) (no Fiber rows exist): read the
sharpemu body at `$R/sharp/src` (= 514d766), then searched OURS (`e4/full/src`, KytyPlus f266548 + patch 0001) for the
NID and for an implementation it could alias. Pass 2: `git log HEAD -- src/SharpEmu.Libs/Kernel Ult Fiber
LibcStdioExports.cs LibcInternalExports.cs CxxAbiExports.cs HostTiming.cs SharpEmu.HLE/FileSystem` (141 commits); read
every commit whose message states a reason (46a7d3a, ef73fe4, 4e6d1e0, 50198a6, 2a27cfe, 3e76003, 498d402, 816ec4a,
f36ce40, 007bf6f, 956da76 [reverted by 6db095e, reason kept], 2a4da8c, bb3318a, 90c72eb, 73e8821, ecbb0db, 1be009c,
9cdc855, 63b440e, c03ca32, 9ff60ab, e01092a, f84d869, 5e76554, 3a24db5, 65a4077, edb4eb8, c0fd6a8, de4fc1e, 0c467e8,
2df6f5b, 1811cef, fd59352, d0dd3fe, b6347f9, 8ddf660, 179fcbb, 1f4425b [Ult rewrite], d134f9b, e17fb6f) and opened the
matching function in OURS. Also joined `ours-nids.tsv` with `sharp-nids.tsv` to find NIDs whose posix/sce return
convention differs from the function we bound (SK06). Findings in OURS that sharpemu does not fix but that I hit while
checking are marked "found while checking".
Two cautions for porters: (a) sharpemu's `OrbisGen2Result` values are NOT the console's 0x80020000+errno codes
(INVALID_ARGUMENT = 0x80020003, MEMORY_FAULT = 0x80020101, `SharpEmu.HLE/OrbisGen2Result.cs:21-80`): port behaviour,
map to our `KERNEL_ERROR_*` by meaning, never copy the numbers. (b) In OURS the 55 libc NIDs are served by the title's
own `sce_module/libc.prx` (`loader/runtimeLinker.cpp:2384` loads it; `Resolve` falls back to program exports and then to
FindByNid, 1864-1900); sharpemu also prefers that LLE libc (`SharpEmu.Core/Cpu/Native/DirectExecutionBackend.cs:
1900-1945`), its libc HLE is a fallback. Licence of every sharpemu source cited: GPL-2.0-or-later (SPDX headers);
no provenance problem found in the cited code or comments.

## 2. Table (ranked: correctness fixes to what we have, then missing functions with behaviour, then stubs; skips last)

| ID | What | Source (sharpemu path @ 514d766:lines; commit) | Licence | Ours | Effort | Risk | Class | Value note |
|---|---|---|---|---|---|---|---|---|
| SK01 | Level-triggered equeue events are delivered N times in ONE wait: `GetTriggeredEvents` loops `while (event.triggered)` and, for a non-EV_CLEAR event (sceKernelAddUserEvent), fills every slot of `ev[]` with the same event. sharpemu delivers each queued event once per wait and re-queues level events for the next wait. | `Kernel/KernelEventQueueCompatExports.cs:1920-1975` (TryReserveEvents, comment 1951); 816ec4a 2026-07-31 "Kernel: correct equeue event delivery and waiter lifetime" | GPL-2.0+ | differs: `kernel/eventQueue.cpp:100-147` (loop 115-139) | S | L: AMPR pending_events path must keep delivering distinct pending entries | e4-now | wrong result: a title waiting with num>1 processes one trigger num times |
| SK02 | sceKernelRename/rename of a path that is open exits the process (`EXIT_NOT_IMPLEMENTED(GetFile(real_from/real_to) != nullptr)`); directories cannot be renamed (ENOENT). sharpemu renames open files and directories. | `Kernel/KernelFileExtendedExports.cs:330-380` (Directory.Move / File.Move overwrite); 1811cef 2026-10-09 "[Kernel] Allow renaming and unlinking open guest files" | GPL-2.0+ | differs: `kernel/fileSystem.cpp:1444-1476` (EXITs 1456-1457, file-only 1459) | S | M: save-data writers (temp file + rename) | e4-now | crash on a common save pattern (rename over a file another handle still has open) |
| SK03 | sceKernelWaitEqueue with `out == NULL` exits the process; sharpemu accepts NULL and just does not write the count. | `Kernel/KernelEventQueueCompatExports.cs:783-976` (null checks 813, 937) | GPL-2.0+ | differs: `kernel/eventQueue.cpp:432` | S | L | e4-now | crash |
| SK04 | KernelOpen exits on: O_ACCMODE==3 (`EXIT` 469), O_DIRECTORY with write/O_TRUNC/O_CREAT (472-473), an existing directory opened with write/O_TRUNC/O_CREAT (532-533); and leaks the descriptor slot on the O_TRUNC+O_RDONLY EACCES path (513-515, no DeleteDescriptor). sharpemu returns an error for every one of these. | `Kernel/KernelMemoryCompatExports.cs:1512-1530` (dir + write/creat/trunc/append -> error), `4827-4839` (ResolveOpenAccess: 3 -> read-write); 956da76 2026-07-23 (open error mapping; reverted by 6db095e, kept for the reason) | GPL-2.0+ | differs: `kernel/fileSystem.cpp:433-583` | S | L | e4-now | crash on a bad/odd open; slot leak |
| SK05 | Guest paths are not normalised: "." / ".." go to the host verbatim, so `/app0/../x` escapes the mount into the host folder and `/app0/../download0/f` is served from app0's host dir; mount lookup takes the first, not the longest, matching mount point. sharpemu resolves ./.. lexically, clamps at the mount root, and picks the longest prefix (UE titles address content with "../../../"). | `Kernel/KernelMemoryCompatExports.cs:5176-5203` (NormalizeMountRelativePath), `5214-5245` (CombineWithinMount), `5070-5110` (longest prefix); 9ff60ab 2026-07-19 "[Kernel] Clamp guest path traversal at the mount root", e01092a 2026-07-21 | GPL-2.0+ | differs: `kernel/fileSystem.cpp:333-398` (no normalisation; find_if first match 339-341, 380-382) | S | M: any path that only worked through host ".." walking | e4-now | correctness + sandbox; UE paths |
| SK06 | Return-convention mismatches (posix NID bound to an sce function or the reverse): XhWHn6P5R7U pthread_rwlock_trywrlock -> LibKernel::PthreadRwlockTrywrlock returns 0x80020010 for EBUSY (normal flow for a trylock); VAzswvTOCzI unlink -> FileSystem::KernelUnlink returns SCE codes; P41kTWUS3EI scePthreadGetschedparam / oIRFTjoILbg scePthreadSetschedparam -> Posix:: wrappers return errno numbers; 14bOACANTBo scePthreadOnce -> Posix::pthread_once returns 22. sharpemu: dedicated posix trywrlock core (0c467e8), PosixFailure -1/errno pattern (bb3318a). | `Kernel/KernelPthreadCompatExports.cs` (posix trywrlock, 0c467e8 2026-07-19 "Add missing nids"), `KernelMemoryCompatExports.cs:1684-1700` (PosixFailure; bb3318a 2026-07-20); found by NID-name join | GPL-2.0+ | differs: `libs/libKernel.cpp:2460, 3662, 2420, 2422, 3653` | S | L | e4-now | trywrlock EBUSY misread by posix callers; error paths of the others. (mprotect YQOfxL4QfeU / munmap UqDGjXA5yUM -> SCE codes too: memory agent) |
| SK07 | sceUltQueuePush drops the item and returns OK when the queue holds `num_data` items (data loss). sharpemu keeps the queue unbounded so a push never loses data (comment: hardware blocks, never blocking cannot deadlock). | `Ult/UltExports.Sync.cs:518-560`; 1f4425b 2026-10-13 "[Ult] Implement libSceUlt runtime, sync objects and worker pool" | GPL-2.0+ | differs: `libs/libUlt.cpp:428-458` (drop at 441-451) | S | L | e4-now | data loss in ULT job queues |
| SK08 | Guest printf (`libs/guestPrintf.cpp`, used by the HLE snprintf eLdDw6l0-bU / vprintf GMpvxPFW924 / printf): `%s` with NULL dereferences NULL in `_strnlen_s` (host crash); `%ls`, `%S`, `%lc`, `%C` are printed as narrow (16-bit wchar strings come out as their first character). sharpemu prints "(null)" and decodes UTF-16 for %ls/%S and %lc. | `Kernel/KernelMemoryCompatExports.cs:4543-4600` (%S -> %ls, %s/%ls, %lc), `5633-5700` (16-bit wide reader); 179fcbb 2026-09-19 "[Kernel] Fix printf %S to be treated as %ls..." | GPL-2.0+ | differs: `libs/guestPrintf.cpp:434-440, 676-720` | S | L | e4-now | crash on printf("%s", NULL) through our HLE; wrong text for wide strings |
| SK09 | sceKernelSignalSema accepts a negative count (decrements the count; `m_count + signal_count` can also overflow); sceKernelCreateSema with sem==NULL exits. sharpemu: count<0 -> EINVAL, overflow-safe compare, NULL -> EINVAL. | `Kernel/KernelSemaphoreCompatExports.cs:366-410` (379, 388), `36-60`; 864cbb0 / 2df6f5b | GPL-2.0+ | differs: `kernel/semaphore.cpp:135-150` (142), `260` | S | L | e4-now | wrong count; crash |
| SK10 | select() on the Linux host returns -1/ENOSYS even for the sleep idiom `select(0,NULL,NULL,NULL,&tv)`; our Windows branch already sleeps and returns 0. (found while checking; sharpemu's select returns nfds at once, `KernelFileExtendedExports.cs:530-539`, not a model) | OURS Windows branch `libs/network.cpp:2318-2329` | GPL-2.0 (ours) | differs: `libs/network.cpp:2360-2363` | S | L | e4-now | a title that paces with select spins or fails |
| SK11 | scePthreadRwlockTimedrdlock/Timedwrlock skip the static-initialiser path that Rdlock/Wrlock/Try* use, so a PTHREAD_RWLOCK_INITIALIZER lock exits the process (`EXIT_NOT_IMPLEMENTED(*rwlock == nullptr)`). (found while checking; same fix as our exp 0336 for tryrdlock) | OURS `kernel/pthread.cpp:2618-2633` pattern | GPL-2.0 (ours) | differs: `kernel/pthread.cpp:2635-2657` | S | L | e4-now | crash |
| SK12 | Missing AIO NIDs 2pOuoWoCxdk sceKernelAioPollRequest, o7O4z3jwKzo sceKernelAioPollRequests, lgK+oIWkJyA sceKernelAioWaitRequests, fR521KIGgb8 sceKernelAioCancelRequest: the loader stub returns 0 and leaves `state` unwritten, so a poller reads garbage. sharpemu writes the completed state. | `Kernel/KernelFileExtendedExports.cs:645-746`; fd59352 2026-10-15 "[Kernel] Implement sceKernelAioPollRequest". Overlap: KytyPS5 dfec14a `src/libs/libKernel.cpp:2941-3010` (same lineage, KytyPS5 agent) | GPL-2.0+ | missing (ours AIO: `libs/libKernel.cpp:3223-3390`) | S | L | e4-now | real out-param behaviour; dedupe with the KytyPS5 row |
| SK13 | Alias registrations onto functions we already have: SoZkxZkCHaw sceKernelFcntl, VW3TVZiM4-E sceKernelFtruncate, 30Rh4ixbKy4 sceKernelFdatasync, KIbJFQ0I1Cg fdatasync, NN01qLRhiqU rename, ayrtszI7GBg truncate, 3eqs37G74-s pthread_getthreadid_np. | `Kernel/KernelFileExtendedExports.cs:185-191, 242-244, 274-276, 322-324, 444-446`; `Kernel/KernelPthreadCompatExports.cs:343-351, 431-435` | GPL-2.0+ | missing NIDs; bodies exist: `kernel/fileSystem.cpp:1375, 1064, 1328, 1444, 1178`; `libs/libKernel.cpp:2297`; `kernel/pthread.cpp:3924` | S | L | e4-now | each returns a value / errno today lost to the 0-stub (e.g. getthreadid 0, fcntl F_GETFL 0) |
| SK14 | Missing cTDYxTUNPhM pthread_condattr_getclock, h0qUqSuOmC8 pthread_condattr_getpshared, 3BpP850hBT4 pthread_condattr_setpshared. | `Kernel/KernelPthreadCompatExports.cs:668-712, 1372-1416` | GPL-2.0+ | missing (attr struct `kernel/pthread.cpp:502-506` has clock_id) | S | L | e4-now | out-params unwritten today |
| SK15 | Missing aPcyptbOiZs sigprocmask and VkTAsrZDcJ0 sigfillset; our _sigprocmask (6xVpy0Fdq+I) returns 0 without writing `oset`. sharpemu keeps a per-thread 16-byte mask, validates `how`, writes oset. | `Kernel/KernelRuntimeCompatExports.Signals.cs:13-49`; 8ddf660 2026-10-31 "[Kernel] Implement POSIX signal masks" | GPL-2.0+ | missing; differs: `libs/libKernel.cpp:476-484` | S | L | e4-now | oset read uninitialised today |
| SK16 | Missing 04AjkP0jO9U _umtx_op (UMTX_OP_WAIT=2 on a 64-bit word with relative timespec, UMTX_OP_WAKE=3, others EINVAL), -1/errno. | `Kernel/KernelSyncOnAddressCompatExports.cs:209-282`, constants 13-14; 2df6f5b 2026-10-06 "[Kernel] Add _umtx_op wait and wake". Overlap: KytyPS5 has Posix::UmtxOp (`kps5-nids.tsv` 04AjkP0jO9U, libKernel.cpp:3347) | GPL-2.0+ | missing; core exists `kernel/syncOnAddress.cpp:290-315` | S | L | e4-now | futex-style waits would return 0 at once (spin) |
| SK17 | Missing Ult queue/pool ops: RVSq2tsm2yw sceUltQueuePop (blocking), 6Mc2Xs7pI1I sceUltQueueTryPush, PP9nZxpSKLY sceUltQueueDestroy, or55417wcDk sceUltWaitingQueueResourcePoolDestroy, dh11uAUWNyM sceUltQueueDataResourcePoolDestroy. Pop via the stub returns 0 and writes nothing (consumer processes garbage). | `Ult/UltExports.Sync.cs:167-190, 499-516, 518-560, 564-620`; 1f4425b | GPL-2.0+ | missing (`libs/libUlt.cpp:67-74` state, 459-485 TryPop) | S | L | e4-now | real behaviour |
| SK18 | Missing jOsUG0BJI-Y sceUltMutexTryLock, jW+HnafeS3Y sceUltMutexDestroy; our UltMutexUnlock calls `recursive_mutex::unlock` for a non-owner (undefined behaviour). sharpemu tracks the owner: TryLock BUSY, Destroy BUSY if owned, Unlock by non-owner PERMISSION 0x80810005. | `Ult/UltExports.Sync.cs:214-320`, error constants `Ult/UltExports.cs:8-12` | GPL-2.0+ | missing; differs: `libs/libUlt.cpp:39-42, 534-567` | S | L (recursion kept as is, see SK31) | e4-now | real behaviour + removes UB |
| SK19 | Missing Ult aliases: RlN-xQPtYnM sceUltUlthreadCreate, 81ag9-mItVY sceUltUlthreadRuntimeCreate, 7+pdaXR9jWw sceUltUlthreadRuntimeOptParamInitialize (same bodies as the `_sce` NIDs we have), V89UhsfEhJk / vIuen2qlRmo sceUltUlthreadOptParamInitialize (zero 128 bytes, NULL -> 0x80810001). | `Ult/UltExports.cs:104-160, 216-231` (both NIDs on one method), `139-150` | GPL-2.0+ | missing; bodies `libs/libUlt.cpp:144-200, 207-262` | S | L | e4-now | a title using the non-underscore names gets no runtime / no ulthread |
| SK20 | Missing 9oiX1kyeedA bzero, jogUIsOV3-U htons (libKernel exports). | `Kernel/KernelSocketCompatExports.cs:738-755, 797-806`; 4f028d0 2026-07-14 | GPL-2.0+ | missing | S | L | e4-now | bzero writes memory, htons returns a value; the stub does neither |
| SK21 | sceLibcHeapGetTraceInfo (NWtTN10cJzE) exits when `info->size != 32`, dereferences NULL, returns void. sharpemu: NULL/size mismatch -> error, else fills and returns 0. | `LibcInternalExports.cs:20-52` | GPL-2.0+ | differs: `libs/libC.cpp:658-665` | S | L | e4-now | crash |
| SK22 | Missing Ult condition variables: jnKaHGkrxZ4 _sceUltConditionVariableCreate, xrmmI832R4U ..Destroy (BUSY with waiters), 5xGAHCxA8M0 ..Wait (releases the Ult mutex, re-acquires), JTw1cAVkuc0 ..Signal, byiceqcMvV0 ..SignalAll (+ RVmEia0vXMI opt-param init, stub-level). | `Ult/UltExports.Sync.cs:321-470` | GPL-2.0+ | missing | M | M: needs SK18 owner tracking; recursive_mutex vs condvar | later | real behaviour |
| SK23 | Missing Ult ulthread lifecycle: kF--s3xZjco sceUltUlthreadExit, xOQ9oACobA4 ..GetSelf (PERMISSION outside an ulthread), HFd-lpjGxJA ..Yield, DsW+3FTXL0Q ..TryJoin (BUSY while running), -gxcs521SvA sceUltUlthreadRuntimeDestroy (BUSY with live ulthreads). | `Ult/UltExports.cs:194-215, 301-420` | GPL-2.0+ | missing (`libs/libUlt.cpp:202-300`) | M | L | later | Exit/GetSelf return values matter to workers |
| SK24 | POSIX sockets on the Linux host: socket/bind/connect/listen/accept/send/recv... return -1/ENOSYS (Windows-only backend). sharpemu has a cross-platform host-socket emulation (TcpClient/Socket) with an outbound policy; ecbb0db keeps the fd after a failed connect. | `Kernel/KernelSocketCompatExports.cs` (whole file, connect 557-640); ecbb0db 2026-07-18 | GPL-2.0+ | differs: `libs/network.cpp:1856-1858` and every `#else ENOSYS` (1783, 1890, 1923, 1948, ...) | L | M | later | titles that probe the network get an unusual errno; an offline-friendly ECONNREFUSED/ENETUNREACH path is a cheaper first step |
| SK25 | Missing lXT0m3P-vs4 sceKernelAioSubmitReadCommandsMultiple. sharpemu treats it as SubmitReadCommands (one id). Unverified here whether the Multiple variant returns one id per request. | `Kernel/KernelFileExtendedExports.cs:547-549` | GPL-2.0+ | missing | S | M: id-array semantics unverified | later | verify id[] shape first |
| SK26 | Missing iiQjzvfWDq0 dup, wdUufa9g-D8 dup2; fcntl F_DUPFD/F_DUP2FD fail EINVAL in ours. sharpemu shares the open file (offset) between descriptors. | `Kernel/KernelFileExtendedExports.cs:384-470`; 956da76 (errno on bad fd) | GPL-2.0+ | missing; `kernel/fileSystem.cpp:72-104` has no shared/refcounted File | M | M: descriptor table change | later | real behaviour |
| SK27 | Missing ku7D4q1Y9PI poll: sharpemu reports every requested POLLIN/POLLOUT as ready (regular files). | `Kernel/KernelFileExtendedExports.cs:488-528` | GPL-2.0+ | missing | M | L | later | files-only version is S; sockets need SK24 |
| SK28 | Missing VHCS3rCd0PM sceKernelAddReadEvent / JxJ4tfgKlXA sceKernelDeleteReadEvent (EVFILT_READ on an fd, polled readiness). | `Kernel/KernelEventQueueCompatExports.cs:498-560, 1659-1835` | GPL-2.0+ | missing | M | L | later | needs fd readiness (sockets) |
| SK29 | Missing module queries: kUpgrXIrz7Q sceKernelGetModuleInfo, QgsKEUfkqMA ..Info2, HZO7xOos4xc ..InfoInternal, IuxnUuXk6Bg sceKernelGetModuleList, ZzzC3ZGVAkc ..List2 (size-checked info structs, handle lists). | `Kernel/KernelRuntimeCompatExports.cs:951-1012, 1550-1660`, `Kernel/KernelModuleRegistry.cs` | GPL-2.0+ | missing; we have `KernelGetModuleInfoFromAddr` `libs/libKernel.cpp:1739` and Program::unique_id `loader/runtimeLinker.h:117` | M | L | later | real out-params |
| SK30 | getdirentries/getdents with a buffer < 512 bytes: ours EINVAL; sharpemu packs whole records into any buffer >= 12 bytes (Quake II). | `Kernel/KernelMemoryCompatExports.cs:7192-7270`; 50198a6 2026-09-30 "[Kernel] Return packed directory entries for Quake II" | GPL-2.0+ | differs: `kernel/fileSystem.cpp:1495-1500` (512-block layout kept) | S | M: offset/basep semantics of our 512-byte block model | later | title-reported |
| SK31 | Ult mutex self-relock: ours recursive (OK); sharpemu PERMISSION 0x80810005. Console behaviour unverified. | `Ult/UltExports.Sync.cs:240-262` | GPL-2.0+ | differs: `libs/libUlt.cpp:39-42, 534-550` | S | M | later | verify before changing |
| SK32 | Ult objects: ours memsets guessed sizes into guest-owned objects (runtime 4096 B, ulthread 512, pools 256/512, queue 512, mutex 256, semaphore 256); sharpemu writes none of them (and leaves sync opt params untouched "rather than risk zeroing past a stack-allocated block"). Real sizes unknown here. | `Ult/UltExports.Sync.cs:121-124`; `Ult/UltExports.cs:139-150` | GPL-2.0+ | differs: `libs/libUlt.cpp:197, 245, 323, 379, 422, 522, 612` | S | M | later | possible overwrite of adjacent guest memory; the 4096 B one is the most suspect |
| SK33 | Relative guest paths (no leading "/"): sharpemu resolves them against /app0; ours ENOENT. Console cwd not verified here. | `Kernel/KernelMemoryCompatExports.cs:5052-5057` | GPL-2.0+ | differs: `kernel/fileSystem.cpp:370-372` | S | M | later | verify cwd |
| SK34 | Equeue re-add of an existing (ident, filter) updates udata/deadline but not `flags` (sceKernelAddUserEventEdge after AddUserEvent keeps level mode); sharpemu replaces the registration incl. flags. | `Kernel/KernelEventQueueCompatExports.cs:1150-1197` | GPL-2.0+ | differs: `kernel/eventQueue.cpp:221-226` | S | L | later | edge case |
| SK35 | sceKernelTriggerUserEvent: ours puts the argument in both `data` (0x10) and `udata` (0x18); sharpemu only udata, data 0. | `Kernel/KernelEventQueueCompatExports.cs:1519-1562`; 816ec4a | GPL-2.0+ | differs: `kernel/eventQueue.cpp:261-266` | S | L | later | console value of `data` unverified |
| SK36 | Missing QyrxcdBrb0M sceKernelGetKqueueFromEqueue (sharpemu returns the equeue handle). | `Kernel/KernelEventQueueCompatExports.cs:715-725` | GPL-2.0+ | missing | S | L | later | useless without kevent() |
| SK37 | clock_gettime(NULL): ours EFAULT; sharpemu EINVAL "to match Orbis runtime behavior" (no evidence given). | `Kernel/KernelRuntimeCompatExports.cs` (65a4077 2026-07-11) | GPL-2.0+ | differs: `kernel/pthread.cpp:3969-3971` | S | L | later | unverified claim |
| SK38 | PTHREAD_MUTEX_ADAPTIVE_NP self-relock returns OK (idempotent) in sharpemu ("Gen5 runtime wrappers layer an adaptive lock over scePthreadMutexLock", UE boot); ours EDEADLK, as FreeBSD libthr's mutex_self_lock does. | `Kernel/KernelPthreadCompatExports.cs` (90c72eb 2026-07-19 "Fixes a Mutex Issue Preventing Some UE Titles From Booting") | GPL-2.0+ | differs: `kernel/pthread.cpp:1383-1396` | S | H: hides real deadlocks | later | do not port without console evidence |
| SK39 | libc HLE fallbacks (55 NIDs): stdio (xeYO4u7uyJ0 fopen, uodLYyUip20 fclose, lbB+UlZqVG0 fread, MpxhMh8QFro fwrite, rQFVBXp-Cxg fseek, Qazy8LmXTvw ftell, SHlt7EhOtqA fgetpos, 7PkSz+qnTto fsetpos, QMFyLoqNxIg setvbuf, KdP-nULpuGw fgets, 8Q60JLJ6Rv4 getc, AEuF3F2f8TA fgetc, LxcEU+ICu8U feof, AHxyhN96dy4 ferror, 3QIPIh-GDjw rewind, aZK8lNei-Qw fputc, QrZZdJ8XsX0 fputs, fffwELXNVFA fprintf, pDBDcY6uLSA vfprintf, gkWgn0p1AfU freopen, vZkmJmvqueY _Lockfilelock, 0x7rx8TKy2Y _Unlockfilelock, sUP1hBaouOw _Getpctype, EMutwaQ34Jo perror), allocator (gQX+4GDQjpM malloc, tIhsqj0qsFE free, 2X5agFjKxMc calloc, Y7aJ1uydPMo realloc, Ujf3KzMvRmI memalign, 2Btkg8k24Zg aligned_alloc, cVSk9y8URbc posix_memalign), string/format (5jNubw4vlAA strnlen, 8u8lPzUEq+U memchr, AV6ipCNa4Rw strcasecmp, kHg45qPC6f0 strncat, tcVi5SivF7Q sprintf, jbz9I9vkqkk vsprintf, Q2V+iqvjgC0 vsnprintf), wide (0nV21JjYCH8 wcsncpy, 6f5f-qx4ucA wcscpy_s, E8wCoUEbfzk wcsncmp, Ezzq78ZgHPs wcschr, FM5NPnLqBc8 wcscpy, Im55VJ-Bekc swprintf_s, LHMrG7e8G78 "wcsmisc" (bound to Wcslen), Slmz4HMpNGs wcsncpy_s, WkkeywLJcgU wcslen, fV2xHER+bKE wcscoll, nJz16JE1txM swprintf, oDoV9tyHTbA vswprintf_s, pNtJdE3x49E wcscmp, u0XOsuOmOzc vswprintf), C++ ABI (3GPpjQdAMTw __cxa_guard_acquire, 9rAeANT2tyE __cxa_guard_release, 2emaaluWzUw __cxa_guard_abort). | `LibcStdioExports.cs`, `Kernel/KernelMemoryCompatExports.cs` (lines in s-only.tsv), `CxxAbiExports.cs:25-200`; e17fb6f (HLE memset preferred: int 45h path in LLE memset) | GPL-2.0+ | served by the title's libc.prx (method note b); memset/memcpy already HLE `libs/libC.cpp:913-914` | L | M: HLE FILE layout must never mix with LLE FILE (`DirectExecutionBackend.cs:1826-1832`) | later | only for a title without libc.prx |
| SK40 | Stub-equivalent (return 0, no out-param): Ac86z8q7T8A sceKernelExitSblock; Y2OqwJQ3lr8 sync (sharpemu flushes open files; our sceKernelSync uvT2iYBBnkY is a no-op too); LuLTRt0rfTw / 6gYjd50q0CE / TkASc9I-xX0 / RVmEia0vXMI Ult sync opt-param inits (sharpemu: 0x80810001 on NULL only, writes nothing). mkgXxsoxWHg sceKernelClearVirtualRangeName: memory agent. | `Kernel/KernelExports.cs:209-217`, `KernelFileExtendedExports.cs:220-234`, `Ult/UltExports.Sync.cs:95-125` | GPL-2.0+ | missing; `libs/libKernel.cpp:1429-1431` | S | L | later | equivalent to loader return-0 stub; registration only |
| SK41 | User-event id sign extension (int id -> uintptr_t ident, -1 -> all ones). | 46a7d3a 2026-10-09 | GPL-2.0+ | `kernel/eventQueue.cpp:463, 481, 499, 527` (`static_cast<uintptr_t>(int)` sign-extends) | - | - | skip: already match (eventQueue.cpp:463) | |
| SK42 | Equeue: delete terminates waiters; trigger arg in udata; level state kept across reads; re-add refreshes pending udata; delete drops pending copies. | 816ec4a, 2df6f5b | GPL-2.0+ | `kernel/eventQueue.cpp:83-98, 104-106, 122-128, 221-226, 264-265, 306-329` | - | - | skip: already match (eventQueue.cpp:83-98) | duplicate-delivery part is SK01 |
| SK43 | Semaphore wake on signal/cancel/delete, no lost wake, cancel -> ECANCELED, delete -> EACCES, zero-count signal OK; posix sem_* errno. | edb4eb8 2026-07-11, 2a4da8c 2026-07-22, 2df6f5b, b6347f9 | GPL-2.0+ | `kernel/semaphore.cpp:62-150, 323-337, 516-680` (condvar design) | - | - | skip: already match (semaphore.cpp:100-150) | |
| SK44 | Mutex: unlock hand-off (no "free with queued waiter"), NORMAL self-relock EDEADLK, timed waits in microseconds. | 73e8821 2026-07-19, f36ce40 2026-08-02, 4e6d1e0 2026-10-07 | GPL-2.0+ | `kernel/pthread.cpp:1373-1505` (owner + condvar loop, chrono us) | - | - | skip: already match (pthread.cpp:1373-1437) | |
| SK45 | Cond vars: signals are edges (no pending credit), pthread_cond_timedwait takes an absolute timespec on the cond's clock, posix NID exported, Signalto exists. | 9cdc855 2026-07-13, 1be009c 2026-07-15, c0fd6a8 2026-07-10, 2a27cfe 2026-09-22 | GPL-2.0+ | `kernel/pthread.cpp:2911-3047, 3168-3250, 4601-4607`; `libs/libKernel.cpp:3625, 2499` | - | - | skip: already match (pthread.cpp:3168) | ours uses the attr clock, sharpemu always realtime |
| SK46 | Precise usleep/nanosleep, EINTR resumed, sub-ms timed waits. | ef73fe4 2026-10-14, 4e6d1e0, de4fc1e 2026-07-11, `HostTiming.cs` | GPL-2.0+ | `common/threads.cpp:138-168` (clock_nanosleep ABSTIME, EINTR loop); `kernel/pthread.cpp:617-645, 4153-4206` | - | - | skip: already match (threads.cpp:167) | sharpemu's issue was Win32 Sleep rounding |
| SK47 | clock ids incl. *_PRECISE/*_FAST/SECOND, gettimeofday tz zero-fill, clock_getres. | 65a4077, 5e76554, 3a24db5 (2026-07-11), 0c467e8 | GPL-2.0+ | `kernel/pthread.cpp:311-345, 3930-3997`; `libs/libKernel.cpp:1956-1984, 2390` | - | - | skip: already match (pthread.cpp:311) | NULL tp code: SK37 |
| SK48 | getdents on a file fd is an error (not EOF); "." and ".." are listed. | 007bf6f 2026-07-23 | GPL-2.0+ | `kernel/fileSystem.cpp:1498-1500`; `common/platform/sysLinuxFileIO.cpp:670-684` (readdir includes . and ..) | - | - | skip: already match (fileSystem.cpp:1498) | |
| SK49 | Unmapped absolute guest paths denied (no host passthrough); no negative stat cache to alias case-distinct paths. | e01092a 2026-07-21, f84d869 2026-07-18 | GPL-2.0+ | `kernel/fileSystem.cpp:370-372, 397, 253-288` | - | - | skip: already match (fileSystem.cpp:372) | ".." escape is SK05 |
| SK50 | Unlink of an open file allowed. | 1811cef 2026-10-09 | GPL-2.0+ | `kernel/fileSystem.cpp:1427-1430` | - | - | skip: already match (fileSystem.cpp:1427) | rename is SK02 |
| SK51 | POSIX aliases titles link directly: clock_getres, pthread_once alias, getpagesize 16 KiB, mprotect/munmap/setsockopt, posix tryrdlock, pthread_yield, pthread sem exports, HR timer events, sceKernelDebugWriteCppExceptionInfo -> 0. | 0c467e8 2026-07-19, 5d7d8e0, a60bfc9, 3e76003, f4e6c73 | GPL-2.0+ | `libs/libKernel.cpp:1944-1948, 2390, 2425, 2462-2467, 2475, 2484, 3507-3508, 3535-3541, 3654` | - | - | skip: already match (libKernel.cpp:2390) | trywrlock is SK06 |
| SK52 | Event flags (wait modes, single-waiter EPERM, cancel ECANCELED, delete EACCES, poll EBUSY). | 5512da9, d134f9b | GPL-2.0+ | `kernel/eventFlag.cpp:326-370` | - | - | skip: already match (eventFlag.cpp:326) | |
| SK53 | Fiber: sharpemu's fixes capture import-call continuations (engine-specific); GetSelf outside a fiber writes 0 and returns OK in both. | d134f9b 2026-06-23, d0dd3fe 2026-09-30; `Fiber/FiberExports.cs:356-372` | GPL-2.0+ | `libs/libKernel.cpp:2627-3210` (real context switch; GetSelf 3114-3124) | - | - | skip: already match (libKernel.cpp:3114) | |
| SK54 | Sync-on-address wait/wake (mismatch -> OK, zero timeout -> ETIMEDOUT, misaligned -> EINVAL); default thread affinity 0x7F; main-thread stack reported in pthread attrs. | 09bd4f0, 2df6f5b | GPL-2.0+ | `kernel/syncOnAddress.cpp:88-140, 272-315`; `kernel/pthread.cpp:2061, 1118-1180` | - | - | skip: already match (syncOnAddress.cpp:272) | |

GPU / memory items met on the way (not rowed here): 498d402 GPU interrupt kevents one per trigger (GPU agent); 46a7d3a
oversized reservation at the hint and mkgXxsoxWHg (memory agent); posix mprotect/munmap NIDs bound to SCE-code functions
(`libs/libKernel.cpp:2466-2467`, memory agent).

## 3. Port specs for the e4-now rows

Common: library "libkernel" rows go in `libs/libKernel.cpp`; posix wrappers live in `namespace Posix` and use
`POSIX_CALL` / `POSIX_N_CALL` (-1 + errno) or `POSIX_PTHREAD_CALL` (errno as return) from `libs/errno.h:9-40`. Tests are
host unit tests (or a small guest-free harness calling the C++ functions directly); none needs the game or the GPU.

**SK01 equeue one-delivery-per-wait.** `kernel/eventQueue.cpp:100-147` `GetTriggeredEvents`. Keep the loop for an
event that has `pending_events` (AMPR distinct completions, 285-295), but after delivering an event whose state came
from neither a reset nor a popped pending entry (i.e. still `triggered` and `pending_events` empty), `break` the inner
loop: each knote is reported at most once per wait. Source of the rule: sharpemu `KernelEventQueueCompatExports.cs:
1920-1975` (each queued entry delivered once, level entries re-queued, comment 1951-1953). Test: create eq; AddUserEvent
(eq, 5); TriggerUserEvent(eq, 5, 0x1234); WaitEqueue(num=4, timo=&0) -> out 1 (today 4), ev[0].udata 0x1234; a second
wait -> out 1 again (level); same with AddUserEventEdge -> second wait ETIMEDOUT; AMPR id with three triggers -> out 3.

**SK02 rename open files and directories.** `kernel/fileSystem.cpp:1444-1476`. Remove the two `EXIT_NOT_IMPLEMENTED`
(1456-1457). If `IsDirectoryExisting(real_from)` use `std::filesystem::rename` (target an existing empty dir or
absent); else the current file path. After success, under `g_files` lock, set `real_name = real_to` on every open File
whose `real_name == real_from`, and clear (`{}`) `real_name` of Files that pointed at the replaced `real_to` (their
inode stays valid on Linux; KernelFsync reopens by `real_name`, 1349). Needs a small `FileDescriptors::Rename(from,to)`
method (class at 88-104). Errors: missing source -> ENOENT (as now). Source: sharpemu `KernelFileExtendedExports.cs:
350-379` (Directory.Move / File.Move overwrite: true), reason 1811cef. Test: mount a temp dir at /temp0; open
/temp0/a (write "x"); rename /temp0/a -> /temp0/b: OK, no exit; read through the fd still works; fsync(fd) OK;
mkdir /temp0/d; rename /temp0/d -> /temp0/e: OK.

**SK03 WaitEqueue NULL out.** `kernel/eventQueue.cpp:432`: replace `EXIT_NOT_IMPLEMENTED(out == nullptr)` with a local
`int count` and write `*out` only when non-NULL; return codes unchanged. Source: sharpemu `KernelEventQueueCompatExports
.cs:813, 937`. Test: trigger, WaitEqueue(eq, ev, 1, nullptr, &zero) -> OK and ev[0] filled.

**SK04 KernelOpen without exits.** `kernel/fileSystem.cpp:433-583`: (1) 469 `default:` -> `return KERNEL_ERROR_EINVAL`
(sharpemu instead treats 3 as read-write, `KernelMemoryCompatExports.cs:4827-4839`; FreeBSD behaviour not verified
here); (2) 472-473 and 532-533 -> delete the descriptor and `return KERNEL_ERROR_EISDIR` (`libs/errno.h:208`) for a
directory opened with write access, O_TRUNC or O_CREAT (sharpemu returns its INVALID_ARGUMENT at 1521-1525; EISDIR is
the FreeBSD meaning, value already in our table); (3) 513-515 call `g_files->DeleteDescriptor(descriptor)` before
returning EACCES. Test: open a mounted dir with O_WRONLY / O_RDONLY|O_CREAT / O_DIRECTORY|O_RDWR -> error, no exit;
open(file, 3) -> EINVAL; 1000 x open(file, O_RDONLY|O_TRUNC) then a normal open returns a small fd (no slot growth).

**SK05 guest path normalisation.** `kernel/fileSystem.cpp:333-398`. Add `static std::string NormalizeGuestPath(
std::string_view)`: split on '/', drop "" and ".", ".." pops one segment (never above root), rejoin with a leading '/'
(keep a trailing '/' for the directory form). Call it at the top of `GetRealFilename` and `GetRealDirectory` before the
mount search, and pick the matching `MountPair` with the longest `point` instead of the first (`find_if` 339-341,
380-382). Relative paths (no leading '/') unchanged (SK33). Source: sharpemu `KernelMemoryCompatExports.cs:5176-5203`
(segment walk), `5070-5110` (longest prefix), reasons 9ff60ab / e01092a. Difference to sharpemu: we normalise the whole
guest path (so `/app0/..` becomes `/`, no mount, ENOENT) instead of clamping inside the mount. Test: Mount(T, "/app0"),
Mount(D, "/download0"): "/app0/a/../b" -> T/b; "/app0/./c" -> T/c; "/app0/../etc/passwd" -> empty; "/app0/../download0/f"
-> D/f; overlapping mounts "/app0" and "/app0/sub" -> the longer wins.

**SK06 return-convention fixes.** `libs/libKernel.cpp`: (a) add `int pthread_rwlock_trywrlock(PthreadRwlock*)` =
`POSIX_PTHREAD_CALL(LibKernel::PthreadRwlockTrywrlock(...))` in `kernel/pthread.cpp` Posix namespace (next to tryrdlock
4680) and bind XhWHn6P5R7U to it (2460); (b) add posix `int unlink(const char*)` = `POSIX_CALL(FileSystem::
KernelUnlink(path))` and bind VAzswvTOCzI to it (3662); (c) bind P41kTWUS3EI / oIRFTjoILbg to new sce functions that
return the `LibKernel::PthreadAttrGet/Setsched*` codes unchanged (the bodies of `Posix::pthread_get/setschedparam`,
`kernel/pthread.cpp:4387-4413`, minus `KernelToPosix`; NULL -> `KERNEL_ERROR_EINVAL`) (2420, 2422); (d) bind
14bOACANTBo to an sce `PthreadOnce` returning `KERNEL_ERROR_EINVAL` where `Posix::pthread_once` returns 22 (3653).
Source: sharpemu posix trywrlock core (0c467e8 message: "pthread_rwlock_tryrdlock/trywrlock get a dedicated
non-blocking core"), bb3318a PosixFailure (`KernelMemoryCompatExports.cs:1684-1700`), our exp 0336/0338 pattern
(`libs/libKernel.cpp:2486-2504`). Test: held write lock in thread A; thread B pthread_rwlock_trywrlock -> 16 (EBUSY),
not 0x80020010; unlink("/temp0/missing") -> -1, errno ENOENT; scePthreadGetschedparam(NULL, ..) -> 0x80020016.

**SK07 Ult queue push never drops.** `libs/libUlt.cpp:441-451`: remove the capacity check (unbounded deque), keep the
copy; `capacity` stays informational. Source: sharpemu `Ult/UltExports.Sync.cs:518-560` (comment 518-520). Test:
data pool num_data=2, queue data_size=8; push 1,2,3; TryPop x3 -> 1,2,3 (today 3 is lost); 4th TryPop -> 0x80810008.

**SK08 guest printf.** `libs/guestPrintf.cpp`: in `case 's'` (696) if `p == nullptr` print "(null)" with width and
precision; if `FLAGS_LONG` is set, or the conversion is 'S', read `uint16_t` units up to 0 and emit UTF-8 (pair
surrogates; precision counts output characters); in `case 'c'` (676) with `FLAGS_LONG`, or 'C', take the argument as
one UTF-16 unit and emit UTF-8. Add `case 'S'`/`case 'C'`. Source: sharpemu `KernelMemoryCompatExports.cs:4543-4600`,
16-bit reader `5633-5700`, 179fcbb. Test (host, through `GetGuestSnprintfCtxFunc`): "%s" NULL -> "(null)"; "%ls"
u"abé" -> "ab\xc3\xa9"; "%S" same; "%lc" 0x41 -> "A"; "%5.1s" "xyz" -> "    x".

**SK09 semaphore arguments.** `kernel/semaphore.cpp:135-150` `Signal`: `if (signal_count < 0) return
Result::InvalCount;` and compare `m_count > m_max_count - signal_count`; 260 `EXIT_NOT_IMPLEMENTED(sem == nullptr)` ->
`return KERNEL_ERROR_EINVAL`. (sharpemu also rejects a non-NULL opt with EINVAL at 54; not proposed.) Source: sharpemu
`KernelSemaphoreCompatExports.cs:379-392, 49-56`. Test: CreateSema(init 1, max 5); SignalSema(-1) -> 0x80020016 and
PollSema(1) still OK; SignalSema(INT_MAX) -> EINVAL; CreateSema(NULL,..) -> EINVAL.

**SK10 select sleep idiom on Linux.** `libs/network.cpp:2360-2363` (`#else` of `Select`): before ENOSYS, if no guest fd
< nfds in the three sets is a known socket (`GetSocketBackend`), sleep the timeout (signal-polled, as `KernelUsleep`
does), zero the three sets (`GuestFdZero`) and return 0; a NULL timeout with no fds keeps today's ENOSYS. Source: our
Windows branch 2318-2329. Test: select(0, NULL, NULL, NULL, {0, 20000}) returns 0 after ~20 ms.

**SK11 rwlock timed static init.** `kernel/pthread.cpp:2635-2657`: add the `GetPthreadStaticObjects()->CreateObject(
rwlock, PthreadStaticObject::Type::Rwlock)` step that `PthreadRwlockRdlock` has (2621-2624) to both timed functions.
Test: `PthreadRwlock l = nullptr; PthreadRwlockTimedrdlock(&l, 1000)` -> OK, no exit; Timedwrlock from another thread
-> ETIMEDOUT.

**SK12 AIO poll/wait/cancel.** `libs/libKernel.cpp`, after `KernelAioDeleteRequest` (3375-3390), LIB_FUNCs next to
3742-3746: `int KernelAioPollRequest(int32_t id, int32_t* state)`: NULL -> EFAULT, invalid id -> EINVAL, else `*state =
g_kernel_aio_state[id]`, OK. `int KernelAioPollRequests(int32_t* ids, int32_t num, int32_t* states)`: NULL -> EFAULT,
num <1 or > KERNEL_AIO_MAX_REQUESTS -> EINVAL, else per id. `int KernelAioWaitRequests(int32_t* ids, int32_t num,
int32_t* states, uint32_t mode, uint32_t* usec)`: mode must be 1 (AND) or 2 (OR) -> else EINVAL; submits complete
synchronously in ours, so this is PollRequests plus the `KernelAioWaitRequest` loop (3347-3373) per id.
`int KernelAioCancelRequest(int32_t id, int32_t* state)`: write the current state when `state` != NULL, OK. Source:
sharpemu `KernelFileExtendedExports.cs:645-746` (mode check 657-660, state writes 669-729); KytyPS5 dfec14a
`src/libs/libKernel.cpp:2941-3010` is a drop-in alternative of the same lineage (coordinate with the KytyPS5 agent).
Test: submit a read of a temp file, PollRequest -> state 3 (COMPLETED); PollRequests of two ids; WaitRequests mode 3
-> EINVAL; Cancel -> state 3.

**SK13 aliases.** In `InitLibKernel_1_FS` (3430-3451): `LIB_FUNC("SoZkxZkCHaw", FileSystem::KernelFcntl)`,
`LIB_FUNC("VW3TVZiM4-E", FileSystem::KernelFtruncate)`, `LIB_FUNC("30Rh4ixbKy4", FileSystem::KernelFsync)`. In
`InitLibKernel_1_Posix` (2387-2504): `LIB_FUNC("KIbJFQ0I1Cg", fsync)` (posix fsync 2297), new
`int rename(const char*, const char*) { return POSIX_CALL(FileSystem::KernelRename(a, b)); }` and
`int truncate(const char*, int64_t) { return POSIX_CALL(FileSystem::KernelTruncate(p, l)); }` bound to NN01qLRhiqU /
ayrtszI7GBg. In `InitLibKernel_1_Pthread`: `LIB_FUNC("3eqs37G74-s", LibKernel::PthreadGetthreadid)`. sceKernelFcntl
is variadic; the third int arrives in rdx as `KernelFcntl(int,int,int)` reads it. Source: sharpemu
`KernelFileExtendedExports.cs:185-191, 242-244, 274-276, 322-324, 444-446`, `KernelPthreadCompatExports.cs:343-351`.
Test: truncate("/temp0/f", 3) -> size 3; rename of a missing path -> -1/ENOENT; sceKernelFcntl(fd, F_GETFL) returns
the access mode; pthread_getthreadid_np() equals scePthreadGetthreadid().

**SK14 condattr getters/pshared.** `kernel/pthread.cpp`: add `int pshared = 0` to `PthreadCondattrPrivate` (502-506);
posix `pthread_condattr_getclock(const PthreadCondattr* attr, KernelClockid* clock)`: attr/*attr/clock NULL -> 22, else
`*clock = (*attr)->clock_id`, 0; `pthread_condattr_getpshared(attr, int* v)` same with `pshared`;
`pthread_condattr_setpshared(attr, int v)`: v not 0 (PRIVATE) or 1 (SHARED) -> 22, else store, 0. Register cTDYxTUNPhM /
h0qUqSuOmC8 / 3BpP850hBT4 next to EjllaAqAPZo (`libs/libKernel.cpp:3632`). Source: sharpemu `KernelPthreadCompatExports
.cs:668-712, 1372-1416`. Test: init attr, setclock(4), getclock -> 4; setpshared(2) -> 22; getpshared -> 0.

**SK15 signal masks.** `libs/libKernel.cpp:476`: replace the body of `LibKernel::sigprocmask(int how, const void* set,
void* oset)` with: `thread_local uint8_t mask[16]`; if set != NULL and how not in 1..3 -> errno 22, -1; if oset write
the 16 current bytes first; if set: 1 = OR, 2 = AND-NOT, 3 = copy; return 0. Bind aPcyptbOiZs to the same function.
New `int sigfillset(void* set)`: NULL -> errno 14, -1; else 16 x 0xFF, 0 -> VkTAsrZDcJ0. The mask is state only (this
tree raises no guest signals). Source: sharpemu `KernelRuntimeCompatExports.Signals.cs:13-49`, 8ddf660. Test:
sigfillset(&s); sigprocmask(3, &s, NULL); sigprocmask(1, NULL, &o) -> o all ones; how 7 -> -1/22.

**SK16 _umtx_op.** `libs/libKernel.cpp` Posix namespace: `int _umtx_op(void* obj, int op, uint64_t val, void* uaddr,
void* uaddr2)`: uaddr != NULL -> -1/EINVAL (the `_umtx_time` form is not supported, as in sharpemu); op 2: uaddr2
NULL = infinite, else a relative `KernelTimespec` (tv_sec/tv_nsec range-checked -> EINVAL, converted to microseconds,
clamped to UINT32_MAX) -> `POSIX_CALL(SyncOnAddress::Wait64((volatile uint64_t*)obj, val, &us, signal poll))`; op 3:
`POSIX_CALL(SyncOnAddress::Wake(obj, (int32_t)val))`; other ops -> -1/EINVAL. Register 04AjkP0jO9U in
`InitLibKernel_1_Posix`. Source: sharpemu `KernelSyncOnAddressCompatExports.cs:209-282`. Test: thread A
_umtx_op(&w, 2, 0, 0, NULL) blocks; B sets w=1 and _umtx_op(&w, 3, 1, 0, 0) -> A returns 0; timeout 10 ms -> -1/60.

**SK17 Ult queue pop/try-push/destroy, pool destroy.** `libs/libUlt.cpp`: add `std::condition_variable cv` to
`UltQueueState` (67-74) and `bool alive`; Push (428) notifies; new `UltQueuePop(void* queue, void* data)` = TryPop that
waits on `cv` until non-empty or `!alive` (-> ULT_ERROR_STATE); `UltQueueTryPush` = Push; `UltQueueDestroy(void*
queue)`: NULL -> ULT_ERROR_NULL, unknown -> ULT_ERROR_INVALID (0x80810004), else mark !alive, notify_all, erase;
`UltWaitingQueueResourcePoolDestroy` / `UltQueueDataResourcePoolDestroy(void* pool)`: NULL -> NULL error, unknown ->
INVALID, else erase from `g_ult_resource_pools` / `g_ult_queue_data_pools`. Register RVSq2tsm2yw, 6Mc2Xs7pI1I,
PP9nZxpSKLY, or55417wcDk, dh11uAUWNyM in `InitUlt_1` (710). Source: sharpemu `Ult/UltExports.Sync.cs:167-190,
499-516, 518-620`. Test: consumer thread blocks in QueuePop; producer pushes 0x55 -> consumer gets it; Destroy with a
blocked popper wakes it with an error; destroy of an unknown pool -> 0x80810004.

**SK18 Ult mutex try-lock/destroy/owner.** `libs/libUlt.cpp:39-42`: add `std::thread::id owner` and `uint32_t depth`
to `UltMutexState`, set in Lock (534) after `lock()`, cleared when depth reaches 0 in Unlock (552); Unlock when
`owner != this_thread` -> 0x80810005 (no `unlock()` call, removes the UB); new `UltMutexTryLock(void*)`: `try_lock()`
-> OK (update owner/depth) else ULT_ERROR_BUSY (0x80810007); new `UltMutexDestroy(void*)`: NULL -> NULL error, unknown
-> ULT_ERROR_INVALID, owned -> ULT_ERROR_BUSY, else erase. Recursion stays (SK31). Register jOsUG0BJI-Y, jW+HnafeS3Y.
Source: sharpemu `Ult/UltExports.Sync.cs:214-320`, codes `Ult/UltExports.cs:8-12`. Test: A locks; B TryLock -> BUSY;
B Unlock -> 0x80810005; A Destroy while locked -> BUSY; A unlock; Destroy -> OK.

**SK19 Ult aliases.** `libs/libUlt.cpp` `InitUlt_1` (710-733): `LIB_FUNC("RlN-xQPtYnM", UltUlthreadCreate)`,
`LIB_FUNC("81ag9-mItVY", UltUlthreadRuntimeCreate)`, `LIB_FUNC("7+pdaXR9jWw", UltUlthreadRuntimeOptParamInitialize)`;
new `int UltUlthreadOptParamInitialize(void* p, uint32_t build)`: NULL -> ULT_ERROR_NULL, else zero 128 bytes (same as
the runtime opt param, 150-163) -> V89UhsfEhJk, vIuen2qlRmo. Source: sharpemu `Ult/UltExports.cs:104-160, 216-231`
(both NIDs on one method each). Test: call the new NIDs' functions; runtime create + ulthread create + join returns the
entry's status.

**SK20 bzero/htons.** Posix namespace: `void bzero(void* p, size_t n) { if (p && n) memset(p, 0, n); }` and
`uint16_t htons(uint16_t v) { return (v << 8) | (v >> 8); }`; register 9oiX1kyeedA, jogUIsOV3-U in
`InitLibKernel_1_Posix`. Source: sharpemu `KernelSocketCompatExports.cs:738-755, 797-806` (its bzero takes an int
length; use size_t). Test: htons(0x1234) == 0x3412; bzero of 8 bytes.

**SK21 sceLibcHeapGetTraceInfo.** `libs/libC.cpp:658-665`: return `int`; `info == nullptr || info->size != 32` ->
`KERNEL_ERROR_EINVAL`; else fill as now and return 0. Source: sharpemu `LibcInternalExports.cs:25-52`. Test: size 16 ->
error, no exit; size 32 -> 0 and both pointers set.

## 4. Totals

- Rows: 54. e4-now 21 (SK01-SK21); later 19 (SK22-SK40); skip: already match 14 (SK41-SK54); skip: provenance 0;
  in e4 / done 0.
- e4-now size: 21 S, about 2-3 days including the host tests.
- later size: 11 S (SK25, SK30-SK38, SK40) + 6 M (SK22, SK23, SK26-SK29) + 2 L (SK24, SK39) ~ 1.5 + 3 + 6 ~ 10-11 days.
- Overlaps to dedupe at merge: SK12 and SK16 (KytyPS5 has AIO poll/wait and _umtx_op; VW3TVZiM4-E in SK13 too).
