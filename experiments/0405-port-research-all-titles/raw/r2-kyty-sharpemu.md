# r2: KytyPS5 and sharpemu compared with BC5's host, without the title gate (2026-11-04)

## 1. Question

Which fixes and features do KytyPS5 and sharpemu have in their system libraries, kernel and loader that our host lacks?

This redoes the KytyPS5 and sharpemu parts of exp 0402 (§2, §4) under the maintainer's rule of 2026-11-03 23:0x:

- A port is not judged by whether our two titles use it. The host should be complete and correct for any title.
- There are only two valid skips: "we already match (our file:line)" and "licence or provenance not acceptable".

The output ranks every candidate, gives a port spec for each item that can go into the e4 test build now, and estimates
the size of the rest. Nothing is ported here.

## 2. Setup

### Constraints

Read-only research on the laptop:

- No SSH, no box access, no git commits, and no edits to any existing file.
- Everything written is under `scratchpad/0405/`.
- No Sony material, dumps or keys were fetched or used.

### Sources compared

| Side | What | Licence |
|---|---|---|
| Ours | KytyPlus `f266548` + BC5 patch 0001, effective tree `scratchpad/e4/full/src` (short `O:` below). The `LIB_FUNC` registrations define our exports: 3,143 calls, 3,070 unique NIDs. Our linker resolves a NID in any library (`loader/runtimeLinker.cpp:1864`, FindByNid fallback). An unregistered import gets a return-0 thunk that writes no out-parameters (`runtimeLinker.cpp:143-380`). | GPL-2.0 |
| KytyPS5 | `dfec14a` (2026-11-02), `src/libs`, `src/kernel`, `src/loader`, extracted with `git archive` from `Downloads/bc5/refs/KytyPS5_KytyPS5` (short `K:`). The clone is shallow: history only from `4644c52` (2026-10-21), so older changes are marked "pre-4644c52". It holds the 182 commits since `8291cfe`; 48 of them touch libs, kernel or loader. The passes looked up each in-scope one. The GPU, memory and launcher-only commits belong to other scopes, for example `1b70938`, `ffc8137`, `72b41eb`, `ec8b75b`, `ec74662`, `69fdb03` and `906d255`. | GPL-2.0 (`LICENSE`) |
| sharpemu | `514d766`, `src/SharpEmu.Libs` (C#) plus HLE and Core, extracted from another session's clone (read-only, 715 commits). Commit messages were mined for behaviour fixes with stated reasons. | GPL-2.0-or-later (SPDX headers, `REUSE.toml`) |

### Method

- **Six read-only passes, run in parallel, one per area.**
  - KytyPS5: kernel and libKernel (KK), loader and process services (KL), audio and media (KA), system services (KS).
  - sharpemu: kernel, libc and Ult (SK), media and services (SS).
  - Shared KytyPS5 files were diffed directly with `diff --strip-trailing-cr -w`, since KytyPS5 uses CRLF. Every
    KytyPS5-only hunk was read and checked against our code.
  - sharpemu was compared per export and per fix commit.
  - Each pass wrote one part file under `work/r2/parts/`. This file merges them: 356 part rows become 318 candidates
    after 37 duplicates across parts were folded together and one pointer row was dropped.
- **Out of scope (covered by the GPU and memory agent):** the GPU side (agc, libAgcDriver, graphics, shaders, the
  VideoOut presenter, sharpemu Gpu/ and Agc/) and memory (`kernel/memory.cpp`, `memoryAddressSpace.inc`, AMM and PRT,
  direct and flexible sizing).
- **NID inventory** (`work/r2/scripts/nids2.py`, `sharp_nids.py`):
  - KytyPS5 registers 1,774 unique NIDs; 143 are not in ours. Sixteen of those are GPU (`Graphics5`), leaving 127 in
    scope.
  - sharpemu has 1,513 unique NIDs plus 15 name-only exports; 297 are not in ours, 32 of them `libSceAgc` (GPU). That
    leaves 265 in scope, including `sceNpAuthGetAuthorizedAppCode`, the only name-only export we lack.
  - The two overlap on 31 in-scope NIDs. The union is 361 NIDs that our host does not register.
  - A first line-based parse missed `LIB_FUNC` calls that span two lines and so reported 20 false "missing" sharpemu
    NIDs: the 19 NpUniversalDataSystem exports and GetAddcontEntitlementInfoList. The SS pass caught this, and the
    multi-line parser removed them.
- **Already in flight, listed as "in e4 / done" and not re-specified:**
  - KytyPS5 `dfec14a` (SaveData mount result) and `4b0282e` (sorted search).
  - KytyPS5 `09753bf`/`0a14091` (param.json memory sizing, `KYTY_BC5_MEMORY_FROM_PARAM`).
  - sharpemu `11506fc` (`BC5_DIRECT_TABLE_CATCHER`) and `b1ec286` (VideoOutGetOutputStatus).

### Provenance

| Case | Decision |
|---|---|
| sharpemu `56bf00e` "[RTC] Port core rtc helpers from PS5 3.20 libs": derived from firmware libraries. | Its Rtc helpers are skipped (rank 317). The three network-tick aliases are sourced from shadPS4 instead (GPL-2.0, rank 124). |
| sharpemu `Audio/AudioOut2Exports.cs:1196-1198`: a mask taken from header ids (also line 990, "The header does not document..."). | sharpemu's UserGetSupportedAttributes is skipped (rank 318). KytyPS5's version (rank 84) is used instead. |
| sharpemu `LibcStdioExports.cs:20` cites "the SDK fpos_t" layout. | That layout must not be copied when the libc fallbacks (rank 234) are ported. |
| KytyPS5 Hmd2 and VrTracker2 use SDK-style structs: `Sce` names and `sizeOfThis`/`reserved00` fields. | Skipped (rank 316). |
| A grep of every KytyPS5 file in scope for SDK, firmware and disassembly mentions found nothing else. | No action. |
| Our own tree: `O:libs/ngs2_pcm.h:7` says its values come from "psOff / SDK dumps". It is upstream KytyPlus `f266548` (checked in `refs/Coder787-source_KytyPlus`) and not included anywhere, together with `ngs2_vag_decoder.h` and `audio3d_impl.inc` (KA pass). | Keep these dead files out of any build. Do not reuse their values in an NGS2 port. |

### Cautions that apply to every port

- **sharpemu's error constants are not the console's.** In `OrbisGen2Result.cs`, INVALID_ARGUMENT is 0x80020003. Port
  the behaviour and map to our `KERNEL_ERROR_*` by meaning.
- **Fixes first, then test (10-31 rule).** Every item goes into the test build behind its own switch.
- **Audio rule.** Every AudioOut, AudioOut2, AudioIn, AJM and NGS2 item still needs the exp 0372 DualSense replug
  check before it ships (marked "replug" in Risk).
- **Our libc fallbacks.** Titles that ship `sce_module/libc.prx` resolve libc from it (`runtimeLinker.cpp:2384`), so our
  libc fallbacks only matter for titles without one. That is a scope note, not a skip.

### Side checks

- **KS pass note:** `libIme.cpp:268-291` registers `sceIme*` stubs under the same normalised library as the real
  `ime.cpp`. Its `InitIme_1` is never `LIB_LOAD`ed (`O:libs/libs.cpp:93-160`), so the two do not conflict.
- **Duplicate registration:** `ShareFeaturePermit` is registered twice under the same library and module
  (`O:libs/libNet.cpp:4028`, `O:libs/libShare.cpp:240`). The later `LIB_LOAD` wins (`symbolDatabase.cpp`
  `insert_or_assign`). This is harmless today.

## 3. Totals

| Class | Candidates | Effort | Estimate |
|---|---|---|---|
| e4-now | **124**: 91 led by a KytyPS5 row and 33 by a sharpemu row; 24 have both projects as sources (KytyPS5 contributes to 98 items, sharpemu to 50) | all S | about 15 agent-days with CPU tests |
| later | **129** | 65 S + 52 M + 12 L (14 rows are registration-only) | about 100 agent-days (range 80-130), see §6 |
| in e4 / done | 5 (`dfec14a`, `4b0282e`, `09753bf`/`0a14091`, `b1ec286`, `11506fc`) | - | - |
| skip: already match | 58 (each with our file:line) | - | - |
| skip: provenance | 3 (sharpemu Rtc `56bf00e`, sharpemu AudioOut2 attribute mask, KytyPS5 Hmd2/VrTracker2) | - | - |

The e4-now items by area:

| Area | e4-now | later |
|---|---|---|
| Kernel, libKernel, libc, Ult | 39 | 32 |
| Loader and process services | 9 | 14 |
| Audio and media | 27 | 39 |
| System services (SaveData, Np, Net/Http, Pad, Json, PlayGo, Psml, Usbd, VideoOut exports) | 49 | 44 |

e4-now means:

- S effort (under 1 hour);
- well sourced;
- checkable by a CPU test without the game and without the GPU;
- nothing that submits to the GPU.

One item was moved down at merge. KK05, the libc `struct tm` conversion, rests on KytyPS5's assertion that the guest
struct is 36 bytes. That is unverified, so it is now later rank 125: verify the layout first.

## 4. Ranked candidates

How to read the tables:

- **Rank:** value over cost across both projects.
  - Ranks 1-45 were ordered by hand: crashes, hangs, wrong results and data loss in functions we already have come
    first, then missing behaviour.
  - Ranks 46-124 keep each pass's own value order, grouped by area.
  - Later ranks put the named larger items first, then S before M before L, with registration-only stubs last.
- **ID:** the part-file row (`work/r2/parts/<prefix>.md`). "(+X)" means a duplicate row X from another pass was folded
  in; its source and our-side note are appended.
- **Source:** the project at its commit, then path:lines. The introducing commit is given where the history has it.
- **Ours:** `O:` paths are in the effective tree.

### Top 15 at a glance

All fifteen are S effort and e4-now. Full rows are in §4.1 and specs in §5.

| # | ID | What is wrong in ours, and the fix | Source |
|---|---|---|---|
| 1 | KK02 (+SK01) | An equeue level event (no `EV_CLEAR`) is copied into every slot of one wait, up to `num` times (`O:kernel/eventQueue.cpp:115-139`). Fix: deliver once per wait (`else break`). | K `eventQueue.cpp:120-127`; sharpemu `816ec4a` |
| 2 | KK01 | `sceKernelAddTimerEvent` treats the microseconds argument as a `timespec*` and makes a one-shot timer (`O:libs/bc5LleAgc.cpp:7920-7924`, F246). Fix: a periodic `EVFILT_TIMER` whose `data` counts expirations. | K `eventQueue.cpp:142-154, 210-234` |
| 3 | KL01 | The TLS-load stubs change RFLAGS with `sub/add rsp,0x80` (`O:loader/jit.h:107-115, 127, 157`). Every patched `fs:[0]` load can corrupt a live compare result in any title. Fix: `lea rsp,[rsp∓0x80]`. | K `loader/jit.h:61-114` |
| 4 | KL02 | The TLS patch scan skips stray 0x66 bytes and writes the call over the last byte of the previous instruction (`O:loader/runtimeLinker.cpp:1533-1563`). Fix: patch at the `64 48 8B` byte with a REX.W call, plus a size guard. | K `runtimeLinker.cpp` (KL02 row) |
| 5 | KK06 | Mutex unlock and cond signal notify after releasing the internal lock (`O:kernel/pthread.cpp:1489-1492`, 2925-2937, 3029-3070, 586-593). This is a use-after-free when the woken thread destroys the object. Fix: notify under the lock. | K `pthread.cpp:523, 1404-1413, 2765-2771` |
| 6 | KK03 (+SK11) | A statically initialised rwlock exits the emulator on Destroy and on first use by Timedrdlock/Timedwrlock. | K `4592e4c`; sharpemu |
| 7 | KK04 (+SK02) | `sceKernelRename` exits when either path is open (`O:kernel/fileSystem.cpp:1456-1457`), and directories cannot be renamed. | K; sharpemu |
| 8 | SK04 (+KK09) | `KernelOpen` exits on `O_ACCMODE` 3 and on a directory opened with write, `O_CREAT` or `O_TRUNC`. The EACCES path leaks a descriptor. | sharpemu; K |
| 9 | SK03 | `sceKernelWaitEqueue` with `out == NULL` exits (`O:kernel/eventQueue.cpp:432`). | sharpemu |
| 10 | KS03 (+SS01, KS02) | `sceSaveDataSyncSaveDataMemory` never posts its event, so a title polling `GetEventResult` waits forever (`O:libs/libSaveData.cpp:1061-1067`). The SaveData event queue also has no lock. | K; sharpemu; shadPS4 |
| 11 | KS09 (+SS02) | `SetupSaveDataMemory2` reports `existed_memory_size` ≥ 64 KiB on a first run, so a fresh title reads zeros as a save. | K; sharpemu |
| 12 | KA01 | `sceAudioOutOutputs` exits on `num` 0 and overflows a stack array when `num` > 32 (`O:libs/audio.cpp:1498-1517`). Fix: INVALID_SIZE. | K `audio.cpp:995-997` |
| 13 | KA02 | `sceAudioOutOpen` with freq 0 causes a SIGFPE. Fix: INVALID_SAMPLE_FREQ. | K `audio.cpp:870-872` |
| 14 | KA03 | `Ngs2RackDestroy` neither unlinks nor frees the rack: use-after-free and heap corruption. | K `ngs2.cpp` |
| 15 | KS01 | Http2 `SendRequestAsync` and `ReadDataAsync` never trigger the caller's equeue user event, so async HTTP/2 waits forever. | K `a06e356` |

### The largest "later" items by value

| Rank | ID | Item | Effort |
|---|---|---|---|
| 141 | KA37 (+SS07) | NGS2 renderer. Our NGS2 only zeroes its buffers (`O:libs/audio.cpp:2999-3066`), so every NGS2 title is silent. | L |
| 142 | SK24 (+KS38) | POSIX sockets on the Linux host. Our socket layer answers ENOSYS (`O:libs/network.cpp:1043-2367`). | L |
| 143 | KS39 (+SS14) | Trophy system and UDS unlock rules. | L |
| 135 | KL13 | Boot module model: start only libc at boot and the rest when the title loads them, with the title's arguments. | M, risk H |
| 126, 127 | KK19 (+KL08), KL09 | Module reference counting; re-resolving object imports when a PRX is loaded at runtime. | S each |
| 130, 131 | KK30, KK29 | FIFO mutex hand-off and `scePthreadCancel`. | M each |
| 128, 129 | SK22, SK23 | Ult condition variables and the ulthread lifecycle. | M each |
| 144, 145 | KK37 (+KL20), KL21 | Guest TSC at 1.6 GHz and the guest instruction patcher. Provenance is fine (shadPS4-derived SPDX header). The 1.6 GHz figure is uncited. | L each |


### 4.1 e4-now, ranked across both projects (ranks 1-45)

| Rank | ID | What | Source | Licence | Ours | Effort | Risk | Class | Value |
|---|---|---|---|---|---|---|---|---|---|
| 1 | KK02 (+SK01) | Equeue wait: a level event (no `EV_CLEAR`, no reset func, no pending copies) is delivered once per wait, not copied into every slot of the array (`else break;`) | [KytyPS5 dfec14a] K:kernel/eventQueue.cpp:120-127; pre-4644c52 **+ SK01** [sharpemu 514d766] `Kernel/KernelEventQueueCompatExports.cs:1920-1975` (TryReserveEvents, comment 1951); 816ec4a 2026-07-31 "Kernel: correct equeue event delivery and waiter lifetime" | GPL-2.0 + GPL-2.0+ | differs: O:kernel/eventQueue.cpp:130-139 (loop re-copies the same event until `ret >= num`) / SK01: differs: `kernel/eventQueue.cpp:100-147` (loop 115-139) | S | L | e4-now | Wrong result: a title gets N identical events per wait and may run its handler N times |
| 2 | KK01 | `sceKernelAddTimerEvent` (`57ZK+ODEXWY`): third arg is `SceKernelUseconds` by value; periodic `EVFILT_TIMER` (-7), `EV_CLEAR`, `data` = expirations since last read, deadline advanced by interval; re-adding a live timer first accounts expired periods | [KytyPS5 dfec14a] K:kernel/eventQueue.cpp:142-154, 210-234 (l.221,223), 525-539; eventQueue.h:55 (`interval_ns`); libKernel.cpp:3168; pre-4644c52 | GPL-2.0 | differs: O:libs/bc5LleAgc.cpp:7920-7924 casts the usec integer to `const KernelTimespec*` and makes a one-shot HR timer; O:kernel/eventQueue.cpp:149-155 (no periodic support) | S | L: only callers of this NID change | e4-now | Crash (deref of a small integer as a pointer) or a wrong one-shot timer for any title using kernel periodic timers. Known as F246 |
| 3 | KL01 | TLS-load stubs keep RFLAGS: `lea rsp,[rsp-0x80]`+`nop` / `lea rsp,[rsp+0x80]` in place of `sub/add rsp,0x80` in TlsRegStub and SafeCall | [KytyPS5 dfec14a] src/loader/jit.h @ dfec14a:43-117; pre-4644c52 (history not in clone) | GPL-2.0 | differs: loader/jit.h:89-161 (`sub rsp,0x80` before pushfq at 127, `add rsp,0x80` after popfq at 157-158; TlsRegStub 114-116) | S | L: byte layout of two stubs; offsets of SetFunc/SetOutputReg stay the same | e4-now | Correctness for every title whose main ELF has `mov reg,fs:[0]`: the original instruction leaves flags alone, our replacement returns with the flags of `add rsp,0x80`; any cmp/test...jcc that the compiler scheduled across a TLS load takes the wrong branch |
| 4 | KL02 | TLS patch writes the call at the `64 48 8B` instruction, not over leading 0x66 bytes; Call9 = `48 E8 rel32 48 89 C0` (REX.W so a kept 0x66 cannot make it `callw` on AMD); skip segments < 9 bytes | [KytyPS5 dfec14a] src/loader/jit.h @ dfec14a:21-41; src/loader/runtimeLinker.cpp @ dfec14a:968-1016 (comment 1007-1009); pre-4644c52 | GPL-2.0 | differs: loader/jit.h:68-87 (`E8 rel32 48 89 C0 90`); loader/runtimeLinker.cpp:1519-1567 (writes at `ptr`, i.e. over the 0x66 bytes, NOP-pads; no `size>=9` guard, `end_ptr` underflows for tiny segments) | S | M: touches every title's TLS patching; a mistake shows at boot | e4-now | Our raw byte scan also takes a 0x66 that ends the PREVIOUS instruction (e.g. `cmp al,0x66` = `3C 66`) as a prefix and overwrites it: silent code corruption before the TLS load |
| 5 | KK06 | Notify under the internal lock: mutex unlock wakes while holding `mutex->m`; cond signal/broadcast notify while holding `cond->m` ("so the selected waiter cannot exit and be freed first") | [KytyPS5 dfec14a] K:kernel/pthread.cpp:1404-1413, 506-525 (comment l.523), 2765-2771; pre-4644c52 | GPL-2.0 | differs: O:kernel/pthread.cpp:1489-1492 (`lock.unlock(); mutex->cv.notify_one();`), 2925-2937, 3029-3037, 3062-3070, 586-593 notify after releasing; a woken thread can destroy the object first (cond: `(*cond)` re-read after destroy set it to NULL) | S | L: standard pattern, a little more contention | e4-now | Rare use-after-free / null-deref crash in destroy-after-unlock patterns (POSIX allows them). Minimal change only; full FIFO rework is KK30 |
| 6 | KK03 (+SK11) | Statically initialised rwlock (`*rwlock == NULL`): `PthreadRwlockDestroy` returns OK without allocating (`4592e4c` 2026-10-29 "kernel: destroy untouched static rwlocks without allocation"); `PthreadRwlockTimedrdlock/Timedwrlock` create it on first use (pre-4644c52) | [KytyPS5 dfec14a] K:kernel/pthread.cpp:2288-2299, 2469-2501; test tests/KernelFileSystemTests.cpp:104-113 @dfec14a **+ SK11** [sharpemu 514d766] OURS `kernel/pthread.cpp:2618-2633` pattern | GPL-2.0 + GPL-2.0 (ours) | differs: O:kernel/pthread.cpp:2464, 2642, 2654 `EXIT_NOT_IMPLEMENTED(*rwlock == nullptr)` (emulator stop); Rdlock and the other entry points already create (2621-2624, 2664-2665, 2695-2696, 2730, 2769) / SK11: differs: `kernel/pthread.cpp:2635-2657` | S | L | e4-now | Emulator stop on legal calls (`SCE_PTHREAD_RWLOCK_INITIALIZER`). Same pattern still EXITs in `PthreadCondDestroy` O:2955 (KytyPS5 has it too; extend the fix) |
| 7 | KK04 (+SK02) | `sceKernelRename` of a file that is open (source or target) proceeds | [KytyPS5 dfec14a] K:kernel/fileSystem.cpp:1398-1430 (no open-file check); pre-4644c52 **+ SK02** [sharpemu 514d766] `Kernel/KernelFileExtendedExports.cs:330-380` (Directory.Move / File.Move overwrite); 1811cef 2026-10-09 "[Kernel] Allow renaming and unlinking open guest files" | GPL-2.0 + GPL-2.0+ | differs: O:kernel/fileSystem.cpp:1456-1457 `EXIT_NOT_IMPLEMENTED(g_files->GetFile(real_*) != nullptr)` / SK02: differs: `kernel/fileSystem.cpp:1444-1476` (EXITs 1456-1457, file-only 1459) | S | L: Linux renames open files; open fds keep the inode | e4-now | Emulator stop on the common "write temp, rename over open save" pattern |
| 8 | SK04 (+KK09) | KernelOpen exits on: O_ACCMODE==3 (`EXIT` 469), O_DIRECTORY with write/O_TRUNC/O_CREAT (472-473), an existing directory opened with write/O_TRUNC/O_CREAT (532-533); and leaks the descriptor slot on the O_TRUNC+O_RDONLY EACCES path (513-515, no DeleteDescriptor). sharpemu returns an error for every one of these. | [sharpemu 514d766] `Kernel/KernelMemoryCompatExports.cs:1512-1530` (dir + write/creat/trunc/append -> error), `4827-4839` (ResolveOpenAccess: 3 -> read-write); 956da76 2026-07-23 (open error mapping; reverted by 6db095e, kept for the reason) **+ KK09** [KytyPS5 dfec14a] K:kernel/fileSystem.cpp:495-498; pre-4644c52 | GPL-2.0 + GPL-2.0+ | differs: `kernel/fileSystem.cpp:433-583` / KK09: differs: O:kernel/fileSystem.cpp:513-515 returns without `DeleteDescriptor` | S | L | e4-now | crash on a bad/odd open; slot leak |
| 9 | SK03 | sceKernelWaitEqueue with `out == NULL` exits the process; sharpemu accepts NULL and just does not write the count. | [sharpemu 514d766] `Kernel/KernelEventQueueCompatExports.cs:783-976` (null checks 813, 937) | GPL-2.0+ | differs: `kernel/eventQueue.cpp:432` | S | L | e4-now | crash |
| 10 | KS03 (+SS01, KS02) | SaveDataSyncSaveDataMemory: validate, flush, queue MEMORY_SYNC_END (type 3) event unless option==1, MEMORY_NOT_READY before setup | [KytyPS5 dfec14a] K libs/libSaveData.cpp:197-202 (struct),267,1151-1182; pre-4644c52 **+ SS01** [sharpemu 514d766] SaveData/SaveDataExports.cs:1571-1609 (added in 9415395 2026-07-18; comment: guest blocks a worker on GetEventResult until SYNC_END, "what wedged Dead Cells at FLIP 0"); shadPS4 savedata.cpp:1637-1665 + save_backup.h:26 agree (type 3) **+ KS02** [KytyPS5 dfec14a] K libs/libSaveData.cpp:1027-1028,1275-1276,1191; pre-4644c52 (history not in clone) | GPL-2.0 + GPL-2.0+ | differs: O libs/libSaveData.cpp:1061-1067 (log + OK), 244-246 (no type 3) / SS01: differs: O libs/libSaveData.cpp:1061-1067 (returns OK, no event) / KS02: differs: O libs/libSaveData.cpp:940,1123,1090-1095 (no lock; Umount2 896 does lock) | S | L-M: event appears where none did | e4-now | hang: titles that wait for the sync-end event via GetEventResult poll NOT_FOUND forever |
| 11 | KS09 (+SS02) | SetupSaveDataMemory2 existed_memory_size = size of the stored memory file, 0 when none | [KytyPS5 dfec14a] K libs/libSaveData.cpp:457-483,811-825; pre-4644c52 **+ SS02** [sharpemu 514d766] SaveData/SaveDataExports.cs:1495-1551 (488b285 2026-07-16 "Implement save data memory2 exports"); shadPS4 savedata.cpp:1580-1603 (existed_size 0 = just created) | GPL-2.0 + GPL-2.0+ | differs: O libs/libSaveData.cpp:763-766 (reports g_save_data_memory.size(), >= 0x10000 always) / SS02: differs: O libs/libSaveData.cpp:757-767 reports the vector size after resize (>= 0x10000, = memory_size on a fresh title) | S | M: first title's memory-save init path | e4-now | wrong result: a fresh install looks like an existing save |
| 12 | KA01 | sceAudioOutOutputs: num 0 or > 32 returns AUDIO_OUT_ERROR_INVALID_SIZE | [KytyPS5 dfec14a] audio.cpp:995-997; pre-4644c52 (history not in clone) | GPL-2.0 | differs: audio.cpp:1498-1517 writes `params[i]` for i < num into a 32-entry stack array (stack overflow for num > 32); num 0 aborts in Audio::AudioOutOutputs (audio.cpp:1210) | S | L; replug | e4-now | crash/stack corruption to error code |
| 13 | KA02 | sceAudioOutOpen: freq 0 returns AUDIO_OUT_ERROR_INVALID_SAMPLE_FREQ | [KytyPS5 dfec14a] audio.cpp:870-872; pre-4644c52 | GPL-2.0 | differs: audio.cpp:1378-1423 accepts 0; audio.cpp:1215 then divides by freq (SIGFPE at the first output) | S | L; replug | e4-now | crash to error code |
| 14 | KA03 | Ngs2RackDestroy unlinks the rack (global racks mutex), calls the allocator free_handler, returns the context buffer | [KytyPS5 dfec14a] ngs2.cpp:1456-1528 (+ rack->buffer_info stored at 1377, g_racks_mutex 910); pre-4644c52 | GPL-2.0 | differs: audio.cpp:2958-2967 only zeroes buffer_info; the rack stays in g_racks_list, so Ngs2SystemRender (audio.cpp:3021-3060) keeps writing voice state into memory the title freed; allocator racks leak | S | M (NGS2 titles); replug | e4-now | use-after-free and heap corruption in any title that destroys a rack |
| 15 | KS01 | Http2 SendRequestAsync/ReadDataAsync never trigger the caller's kqueue user event | [KytyPS5 dfec14a] K libs/libNet.cpp:837-845,1259-1264,1266-1288,1436-1473; a06e356 2026-11-01 "net: signal the event queue when Http2 async calls complete" | GPL-2.0 | differs: O libs/libNet.cpp:1132-1152,1300-1336 (kqueue_option ignored) | S | L: only adds an event | e4-now | hang: a title that waits on its equeue for Http2 completion blocks forever |
| 16 | SS22 (+KS69) | scePadOpenExt (WFIiSfXGUq8): as scePadOpen, also accepts port type 1 | [sharpemu 514d766] Pad/PadExports.cs:91-96 + PadOpenCore 132-180 (373100a 2026-07-14) **+ KS69** [KytyPS5 dfec14a] K libs/libPad.cpp:126-135,170 | GPL-2.0 + GPL-2.0+ | missing (stub returns handle 0, which every O pad call rejects: controller.cpp:489-492) / KS69: missing | S | L | e4-now | no input at all for a title that opens its pad this way |
| 17 | KK25 | `scePthreadAttrGetinheritsched` (`lpMP8HhkBbg`) registration; drop the EXIT on values other than 0/4 | [KytyPS5 dfec14a] K:libs/libKernel.cpp:3245; K:kernel/pthread.cpp:2005-2015; `b20850a` 2026-11-02 "kernel: export scePthreadAttrGetinheritsched" | GPL-2.0 | missing registration: O:kernel/pthread.cpp:2166-2182 exists (with `EXIT` at 2178) | S | L | e4-now | Stub leaves `*inherit_sched` unwritten; a title copying attributes passes the garbage to `Setinheritsched`, which EXITs (O:kernel/pthread.cpp:2338, emulator stop) |
| 18 | KK10 | `write`/`pwrite` on a descriptor opened read-only return EBADF | [KytyPS5 dfec14a] K:kernel/fileSystem.cpp:722, 940 (`!file->opened \|\| !file->writable`); pre-4644c52 | GPL-2.0 | differs: O:kernel/fileSystem.cpp:713, 838 check only `file == nullptr`; `fwrite` on the read-only `FILE*` gives 0 and the call returns 0 | S | L | e4-now | Wrong result; a retry-until-written loop in a title spins forever |
| 19 | SK06 | Return-convention mismatches (posix NID bound to an sce function or the reverse): XhWHn6P5R7U pthread_rwlock_trywrlock -> LibKernel::PthreadRwlockTrywrlock returns 0x80020010 for EBUSY (normal flow for a trylock); VAzswvTOCzI unlink -> FileSystem::KernelUnlink returns SCE codes; P41kTWUS3EI scePthreadGetschedparam / oIRFTjoILbg scePthreadSetschedparam -> Posix:: wrappers return errno numbers; 14bOACANTBo scePthreadOnce -> Posix::pthread_once returns 22. sharpemu: dedicated posix trywrlock core (0c467e8), PosixFailure -1/errno pattern (bb3318a). | [sharpemu 514d766] `Kernel/KernelPthreadCompatExports.cs` (posix trywrlock, 0c467e8 2026-07-19 "Add missing nids"), `KernelMemoryCompatExports.cs:1684-1700` (PosixFailure; bb3318a 2026-07-20); found by NID-name join | GPL-2.0+ | differs: `libs/libKernel.cpp:2460, 3662, 2420, 2422, 3653` | S | L | e4-now | trywrlock EBUSY misread by posix callers; error paths of the others. (mprotect YQOfxL4QfeU / munmap UqDGjXA5yUM -> SCE codes too: memory agent) |
| 20 | KS10 | Pad: a stick/axis event that changes no button merges into the newest unread sample | [KytyPS5 dfec14a] K libs/controller.cpp:522-546; 39faa62 2026-10-27 "controller: merge stick and sensor events into the newest unread pad sample" | GPL-2.0 | differs: O libs/controller.cpp:859-875 (every Axis event, :963, pushes a sample; ring 64 at :104) | S | M: fewer samples from scePadRead | e4-now | input loss: a burst of axis events between two reads pushes unread button changes out of the 64-entry ring (motion/touch already merged in ours, :111-127) |
| 21 | SK07 | sceUltQueuePush drops the item and returns OK when the queue holds `num_data` items (data loss). sharpemu keeps the queue unbounded so a push never loses data (comment: hardware blocks, never blocking cannot deadlock). | [sharpemu 514d766] `Ult/UltExports.Sync.cs:518-560`; 1f4425b 2026-10-13 "[Ult] Implement libSceUlt runtime, sync objects and worker pool" | GPL-2.0+ | differs: `libs/libUlt.cpp:428-458` (drop at 441-451) | S | L | e4-now | data loss in ULT job queues |
| 22 | KS05 | Json2 JsonValueSetObject / JsonObjectAssign destroy the target before copying a source that may be the target or its descendant | [KytyPS5 dfec14a] K libs/libJson2.cpp:626-636,987-996; pre-4644c52 | GPL-2.0 | differs: O libs/libJson2.cpp:1033-1048 (Clear then copy), 911-917 (Dtor then CopyCtor) | S | L | e4-now | use-after-free on self/descendant assignment |
| 23 | KS04 | HttpCreateTemplate with NULL user agent | [KytyPS5 dfec14a] K libs/network.cpp:469; 87e815b 2026-10-23 "net: accept a NULL user agent in sceHttpCreateTemplate (Cyberpunk 2077)" | GPL-2.0 | differs: O libs/network.cpp:584 `std::string(user_agent)` | S | L | e4-now | crash (std::string from nullptr) |
| 24 | SK08 (+KK14) | Guest printf (`libs/guestPrintf.cpp`, used by the HLE snprintf eLdDw6l0-bU / vprintf GMpvxPFW924 / printf): `%s` with NULL dereferences NULL in `_strnlen_s` (host crash); `%ls`, `%S`, `%lc`, `%C` are printed as narrow (16-bit wchar strings come out as their first character). sharpemu prints "(null)" and decodes UTF-16 for %ls/%S and %lc. | [sharpemu 514d766] `Kernel/KernelMemoryCompatExports.cs:4543-4600` (%S -> %ls, %s/%ls, %lc), `5633-5700` (16-bit wide reader); 179fcbb 2026-09-19 "[Kernel] Fix printf %S to be treated as %ls..." **+ KK14** [KytyPS5 dfec14a] K:libs/guestPrintf.cpp:435-442, 703-740; needs `Common::Utf16ToUtf8(u16string_view)` (K:common/stringUtils.h:166-172; ours has a `const char16_t*` form O:common/stringUtils.h:319); pre-4644c52 | GPL-2.0 + GPL-2.0+ | differs: `libs/guestPrintf.cpp:434-440, 676-720` / KK14: differs: O:libs/guestPrintf.cpp:696-720 prints the UTF-16 bytes as `char*` (first char only for ASCII) | S | L | e4-now | crash on printf("%s", NULL) through our HLE; wrong text for wide strings |
| 25 | KA04 | AJM control job with SIDEBAND_GAPLESS: parse the gapless sideband, set state->gapless, advance the sideband pointer before RESET/INITIALIZE | [KytyPS5 dfec14a] ajm.cpp:491-560 (gapless 511-520); pre-4644c52 | GPL-2.0 | differs: ajm.cpp:677-708 ignores the flag; with INITIALIZE the 8-byte gapless struct is passed to Initialize as codec parameters | S | M (AJM path of both titles); replug | e4-now | wrong decoder init / lost gapless trim |
| 26 | KA05 | AT9 RIFF header: accept the 'data' chunk before the chunk-size check (the job may hold only a prefix of the data) | [KytyPS5 dfec14a] ajm/atrac9_decoder.h:572-579; pre-4644c52 | GPL-2.0 | differs: ajm/atrac9_decoder.h:575-578 returns PARTIAL_INPUT when the data chunk extends past the job, so a RIFF stream fed in pieces never starts | S | L-M; replug | e4-now | AT9 RIFF streams that never start |
| 27 | KS06 (+SS03) | sceNetResolverDestroy (kJlYH5uMAWI) frees the resolver slot | [KytyPS5 dfec14a] K libs/libNet.cpp:127-129, libs/network.cpp:311-319,1445-1456; pre-4644c52 **+ SS03** [sharpemu 514d766] Network/NetExports.cs:1245-1282 (02222c7 2026-06-28) | GPL-2.0 + GPL-2.0+ | missing (O network.cpp:423-447 has no destroy; RESOLVERS_MAX 32 at :369) / SS03: missing; O libs/network.cpp:369-375,423-446 has 32 resolver slots and no way to free one | S | L | e4-now | after 32 create/destroy cycles sceNetResolverCreate fails ENOSPACE (stub destroy frees nothing) |
| 28 | KS14 (+SS10) | SaveDataDelete of a mounted save -> BUSY; honours del->title_id | [KytyPS5 dfec14a] K libs/libSaveData.cpp:1034-1062; pre-4644c52 **+ SS10** [sharpemu 514d766] as cited | GPL-2.0 + GPL-2.0+ | differs: O libs/libSaveData.cpp:946-983 (removes even when mounted, own title only) / SS10: differs: O libs/libSaveData.cpp:946-983 deletes a mounted save, OK for missing | S | M | e4-now | data loss: deletes files under an open mount |
| 29 | KS17 | SaveData input checks: dir/title names must be one path component of [A-Za-z0-9_-.@] (PARAMETER), user_id<0 -> INVALID_LOGIN_USER, Mount3 create blocks 48..16384, Mount3 nulls -> PARAMETER, Search: NUL-terminated dir_name, dir_names_num w/o buffer | [KytyPS5 dfec14a] K libs/libSaveData.cpp:286-297,581-597,693-702,742-744,938-945,1037-1043; pre-4644c52 (22a9392 adds callers) | GPL-2.0 | differs: O libs/libSaveData.cpp:612-614 (EXIT on null), 497-520, 854, 949 (no name checks) | S | M: a title using another character in a dir name would now get PARAMETER (charset is KytyPS5's choice, not verified on a console) | e4-now | path traversal ("../") out of _SaveData; abort on null |
| 30 | KL03 | sceUserServiceGetUserName returns error codes instead of aborting | [KytyPS5 dfec14a] src/libs/libUserService.cpp @ dfec14a:113-132; pre-4644c52 | GPL-2.0 | differs: libs/libUserService.cpp:116-127 (`EXIT_NOT_IMPLEMENTED` on unknown user id and on size < 5; no null check) | S | L | e4-now | Crash fix: a title asking the name of user 0xFF (system), -1 or a stale id, or passing a short buffer, kills the emulator |
| 31 | SK09 | sceKernelSignalSema accepts a negative count (decrements the count; `m_count + signal_count` can also overflow); sceKernelCreateSema with sem==NULL exits. sharpemu: count<0 -> EINVAL, overflow-safe compare, NULL -> EINVAL. | [sharpemu 514d766] `Kernel/KernelSemaphoreCompatExports.cs:366-410` (379, 388), `36-60`; 864cbb0 / 2df6f5b | GPL-2.0+ | differs: `kernel/semaphore.cpp:135-150` (142), `260` | S | L | e4-now | wrong count; crash |
| 32 | KK07 | `PthreadGetprio`/`PthreadSetprio` (and `PthreadCancel`) return ESRCH for a joined thread (`thread->free`) | [KytyPS5 dfec14a] K:kernel/pthread.cpp:3410-3413, 3518-3520, 3534-3537; pre-4644c52 | GPL-2.0 | differs: O:kernel/pthread.cpp:3762-3780, 3782-3796 call `pthread_getschedparam` on a joined native handle; Setprio then `Bc5ApplyGuestPriority` (3813) on a possibly reused host TID | S | L | e4-now | Undefined behaviour; priority can land on another thread |
| 33 | KK08 | `sceFiberRun`: copy `arg_on_return` and the terminated state before publishing the fiber IDLE | [KytyPS5 dfec14a] K:libs/libKernel.cpp:2638-2650 ("Copy results before another thread can acquire and resume the fiber"); pre-4644c52 | GPL-2.0 | differs: O:libs/libKernel.cpp:3055-3064 commits IDLE (3055) then reads `returned_fiber->arg_on_return` and state | S | L | e4-now | Wrong return value / spurious `FIBER_ERROR_STATE` when another worker resumes the fiber at once (fiber job systems) |
| 34 | KA06 | sceAudioInInput writes silence into dest when no device; dest == nullptr stops and returns 0 | [KytyPS5 dfec14a] audio.cpp:743-822 (memset 806); pre-4644c52 | GPL-2.0 | differs: audio.cpp:1333-1352 never writes dest (the title reads stale/garbage "mic" data); dest null aborts (audio.cpp:1587) | S | L; replug | e4-now | garbage capture data, abort |
| 35 | KA07 | sceAudioInOpen returns errors instead of aborting: type not 0/1 -> INVALID_TYPE, index != 0 -> INVALID_PARAM, freq 0 -> INVALID_FREQ, len 0 -> INVALID_SIZE | [KytyPS5 dfec14a] audio.cpp:1047-1058 (OpenPort); pre-4644c52 | GPL-2.0 | differs: audio.cpp:1556-1557 `EXIT_NOT_IMPLEMENTED(type != 1 / index != 0)` (type 0 kills the emulator); freq 0 later divides by zero (audio.cpp:1339) | S | L; replug | e4-now | abort to error code. Only the zero guards of KytyPS5's len/freq rule; its full sets are KA22 |
| 36 | KA08 | Ngs2VoiceGetState for custom mastering/sampler racks: state_size < configured -> 0x804a8011, else zero `configured_size` bytes and fill | [KytyPS5 dfec14a] ngs2.cpp:2795-2813; a0b99a8 2026-10-29 "ngs2: accept larger custom voice state buffers" | GPL-2.0 | differs: audio.cpp:3421-3430 `EXIT_NOT_IMPLEMENTED(state_size != configured_size)` for CustomMastering (abort on a larger buffer) | S | L | e4-now | abort to correct behaviour |
| 37 | KS13 | SaveDataGetParam types 1-5 (title/subtitle/detail/user_param/mtime) and NOT_MOUNTED; SaveDataSetParam types 1-4 and NOT_MOUNTED, PARAMETER for null buf | [KytyPS5 dfec14a] K libs/libSaveData.cpp:126-139,1064-1118,1282-1333; pre-4644c52 | GPL-2.0 | differs: O libs/libSaveData.cpp:1021-1027 (zero fill), 1129-1167 (type!=0 no-op; LOGF derefs p before null check :1139-1145) | S | L | e4-now | wrong result + null deref crash |
| 38 | KS15 (+SS04) | SaveDataTransferringMount: mounts the given title's dir read-only, NOT_FOUND when absent, PARAMETER for null title_id | [KytyPS5 dfec14a] K libs/libSaveData.cpp:934-970; pre-4644c52 **+ SS04** [sharpemu 514d766] SaveData/SaveDataExports.cs:920-963 + MountSaveData 825-918 (4c8c67a 2026-07-21); shadPS4 savedata.cpp:1685-1703 (RDONLY mount with mount->titleId) | GPL-2.0 + GPL-2.0+ | differs: O libs/libSaveData.cpp:850-883 (own title, creates dir, created=1) / SS04: differs: O libs/libSaveData.cpp:850-883 uses our own title id, creates the dir and reports mount_status 1 | S | M: slot key must then include title (O saveDataMountSlots.h:17-29 keys by dir name) | e4-now | wrong result: a PS4-transfer probe always "finds" an empty save |
| 39 | KS16 | SaveDataGetMountInfo: PARAMETER for null, NOT_MOUNTED for an unknown mount point | [KytyPS5 dfec14a] K libs/libSaveData.cpp:1335-1358; pre-4644c52 | GPL-2.0 | differs: O libs/libSaveData.cpp:1169-1193 (EXIT_NOT_IMPLEMENTED on null, OK+MAX when unmounted) | S | L | e4-now | abort on null; wrong result |
| 40 | SK05 (+KK35) | Guest paths are not normalised: "." / ".." go to the host verbatim, so `/app0/../x` escapes the mount into the host folder and `/app0/../download0/f` is served from app0's host dir; mount lookup takes the first, not the longest, matching mount point. sharpemu resolves ./.. lexically, clamps at the mount root, and picks the longest prefix (UE titles address content with "../../../"). | [sharpemu 514d766] `Kernel/KernelMemoryCompatExports.cs:5176-5203` (NormalizeMountRelativePath), `5214-5245` (CombineWithinMount), `5070-5110` (longest prefix); 9ff60ab 2026-07-19 "[Kernel] Clamp guest path traversal at the mount root", e01092a 2026-07-21 **+ KK35** [KytyPS5 dfec14a] K:kernel/fileSystem.cpp:339-377; pre-4644c52 | GPL-2.0 + GPL-2.0+ | differs: `kernel/fileSystem.cpp:333-398` (no normalisation; find_if first match 339-341, 380-382) / KK35: differs: O:kernel/fileSystem.cpp:333-374 (`open("/app0", 0)` without `O_DIRECTORY` resolves to empty: ENOENT), 375-398 | S | M: any path that only worked through host ".." walking | e4-now | correctness + sandbox; UE paths |
| 41 | KK23 (+SK12) | AIO: `sceKernelAioPollRequest` (`2pOuoWoCxdk`), `...PollRequests` (`o7O4z3jwKzo`), `...WaitRequests` (`lgK+oIWkJyA`, AND=1/OR=2 modes), `...DeleteRequests` (`Ft3EtsZzAoY`); `DeleteRequest` reports ESRCH/EBUSY in `*ret` and frees the slot | [KytyPS5 dfec14a] K:libs/libKernel.cpp:2815-2823, 2926-3051, 3391-3399; tests KernelFileSystemTests.cpp:840-940 @dfec14a; pre-4644c52 **+ SK12** [sharpemu 514d766] `Kernel/KernelFileExtendedExports.cs:645-746`; fd59352 2026-10-15 "[Kernel] Implement sceKernelAioPollRequest". Overlap: KytyPS5 dfec14a `src/libs/libKernel.cpp:2941-3010` (same lineage, KytyPS5 agent) | GPL-2.0 + GPL-2.0+ | missing 4 NIDs; differs: O:libs/libKernel.cpp:3347-3390 (WaitRequest treats `*usec == 0` as infinite; DeleteRequest returns EINVAL for a bad id and marks ABORTED without freeing) / SK12: missing (ours AIO: `libs/libKernel.cpp:3223-3390`) | S | L: our submissions complete synchronously, so states are terminal | e4-now | Poll stub writes no state: a title polling for completion reads garbage or never sees it (hang). KytyPS5's `NOTIFIED` bit 0x10000 has no source: TODO(verify), leave out |
| 42 | KK21 | `sceKernelPreadv` (`yTj62I7kw4s`), `sceKernelWritev` (`kAt6VDbHmro`), `sceKernelPwritev` (`mBd4AfLP+u8`) with iovec validation (iovcnt 0..1024, total <= INT_MAX, EFAULT for null base with length), EBADF for a read-only/write-only fd, ESPIPE on sockets, append handling, position kept for p* variants | [KytyPS5 dfec14a] K:kernel/fileSystem.cpp:822-921, 977-1056; fileSystem.h:36-42 (`KernelIovec`, 16 bytes); libKernel.cpp:3095-3099; tests KernelFileSystemTests.cpp:764-838 @dfec14a; pre-4644c52 | GPL-2.0 | missing (k-only; loader stub returns 0, nothing read or written) | S (port ~180 lines + `readable` flag; borderline M) | L | e4-now | Title sees 0 bytes: EOF on reads, lost data or retry loops on writes |
| 43 | KK24 (+SK16) | posix `_umtx_op` (`04AjkP0jO9U`): `UMTX_OP_WAIT` (2) on a 64-bit word with an optional relative `timespec` in `uaddr2`, `UMTX_OP_WAKE` (3); needs `SyncOnAddress::Wait64(nanoseconds)` with a saturating deadline and `ceil` rounding of the remaining slice | [KytyPS5 dfec14a] K:libs/libKernel.cpp:2108-2138, 3347; K:kernel/syncOnAddress.cpp:50-61, 74, 285-288; syncOnAddress.h:16-17; pre-4644c52. Op numbers: FreeBSD `sys/umtx.h` (public; not re-read here) **+ SK16** [sharpemu 514d766] `Kernel/KernelSyncOnAddressCompatExports.cs:209-282`, constants 13-14; 2df6f5b 2026-10-06 "[Kernel] Add _umtx_op wait and wake". Overlap: KytyPS5 has Posix::UmtxOp (`kps5-nids.tsv` 04AjkP0jO9U, libKernel.cpp:3347) | GPL-2.0 + GPL-2.0+ | missing (k-only); O:kernel/syncOnAddress.cpp:57-77 micro-second deadlines only, `duration_cast` truncates (<1 us spin) / SK16: missing; core exists `kernel/syncOnAddress.cpp:290-315` | S | L: replace KytyPS5's EXIT on unknown ops/`uaddr != NULL` with EINVAL | e4-now | Stub returns 0 for WAIT: a guest futex lock busy-spins |
| 44 | KS27 (+SS23) | sceNetConnect/Send/Sendto/Recv/Recvfrom/Getsockopt exports | [KytyPS5 dfec14a] K libs/libNet.cpp:99-101,191-224,246,268-273; pre-4644c52 **+ SS23** [sharpemu 514d766] Network/NetExports.cs:253-355 (d0dd3fe 2026-09-30) | GPL-2.0 + GPL-2.0+ | missing exports; O network.cpp:1895,2062,2129,2133,2182,2186 exist (ENOSYS on Linux) / SS23: missing in libSceNet; implementation exists: O libs/network.cpp:2182-2230 | S | M: titles that "connected" via the stub now see an error | e4-now | today sceNetConnect returns 0 (stub) = connected, sceNetRecv 0 = peer closed |
| 45 | KS26 (+SK10) | select/sceNetSelect: open file and device descriptors are ready at once | [KytyPS5 dfec14a] K libs/network.cpp:2603-2620,2648-2654,2688-2694, kernel/fileSystem.cpp IsOpenDescriptor; a875d1b 2026-10-22 "net: report open file and device descriptors ready in select (Cyberpunk 2077 Galaxy RNG seeding)" **+ SK10** [sharpemu 514d766] OURS Windows branch `libs/network.cpp:2318-2329` | GPL-2.0 + GPL-2.0 (ours) | differs: O libs/network.cpp:2361-2364 (Linux: ENOSYS for everything), caller O libs/libKernel.cpp:2099-2103 / SK10: differs: `libs/network.cpp:2360-2363` | S | L | e4-now | OpenSSL RAND_poll selects /dev/urandom first; ours fails |

### 4.2 e4-now, the rest by area (ranks 46-124)

#### e4-now, ranks 46-65: kernel / libKernel / libc / Ult (in the part's own value order)

| Rank | ID | What | Source | Licence | Ours | Effort | Risk | Class | Value |
|---|---|---|---|---|---|---|---|---|---|
| 46 | KK11 | `stat("/")` answers a directory (`st_mode 040777`) though no mount holds "/" | [KytyPS5 dfec14a] K:kernel/fileSystem.cpp:1130-1134; `13df214` 2026-11-02 "kernel: report the guest root as a directory in stat" | GPL-2.0 | differs: O:kernel/fileSystem.cpp:950-961 resolves "/" to an empty path, ENOENT | S | L | e4-now | Wrong result for root probes |
| 47 | KK12 | posix `_write`/`write` (`FxVZqBAA7ks`, `FN4gaPmuFV8`) to fd 0-2 goes through `KernelWrite` (fd 1/2 to host stdout/stderr, fd 0 EBADF) | [KytyPS5 dfec14a] K:libs/libKernel.cpp:1363-1365; `e0c5ae0` 2026-10-24 "kernel: send _write to descriptors 0-2 through KernelWrite instead of dropping it" | GPL-2.0 | differs: O:libs/libKernel.cpp:1458-1478 returns `size` for fd 0-2 and writes nothing (`KernelWrite` O:fileSystem.cpp:690-700 already handles 1/2) | S | L: more host console output | e4-now | Guest stdout/stderr lost (diagnostics); fd 0 write reports success |
| 48 | KK13 | guest printf: negative `%.*` precision means "no precision" | [KytyPS5 dfec14a] K:libs/guestPrintf.cpp:527-537; pre-4644c52 | GPL-2.0 | differs: O:libs/guestPrintf.cpp:528 sets precision 0 (`%.*s` with -1 prints nothing) | S | L | e4-now | Wrong `snprintf` results in guest strings (paths, names) |
| 49 | KK15 | AMPR completion events on filter `EVFILT_AMPR = -25` | [KytyPS5 dfec14a] K:kernel/eventQueue.h:21, eventQueue.cpp:570, 598; pre-4644c52. Same value in AnyPS5 (cited in our comment) and KytyPlus HEAD (related-projects-review §6) | GPL-2.0 | differs: O:kernel/eventQueue.cpp:268-274 `AmprEventFilter()` returns `EVFILT_USER` (-11): an AMPR id and a user-event id that are equal collide in one (ident, filter) entry | S | M: exp 0036 saw no change at -25 on the second title; LLE modules may dispatch on the filter | e4-now | Event collision / filter mismatch; three projects agree, console value still TODO(verify). Behind a switch |
| 50 | KK16 | Host error mapping: `ENOSPC` and `EFBIG` | [KytyPS5 dfec14a] K:kernel/fileSystem.cpp:1288-1290; pre-4644c52 | GPL-2.0 | differs: O:kernel/fileSystem.cpp:1137-1148 maps both to EIO | S | L | e4-now | Disk-full reported as EIO (truncate/chmod/utimes/fsync paths) |
| 51 | KK17 | libDbgAsan shadow pages: free a shadow page only when the bytes released cover what was allocated, not by call count | [KytyPS5 dfec14a] K:libs/libDbgAsan.cpp:40-129; pre-4644c52 | GPL-2.0 | differs: O:libs/libDbgAsan.cpp:~40-118 (`count++/--`, l.72, 107-109): a range freed in two pieces drops a shadow page still in use | S | L | e4-now | Crash in ASan-instrumented (debug) titles only |
| 52 | KK18 | `fstat` of a special device (`/dev/urandom`, `/dev/random`, ours also `/dev/gc`, `/dev/dipsw`) reports `S_IFCHR 020644` | [KytyPS5 dfec14a] K:kernel/fileSystem.cpp:1201-1205; pre-4644c52 | GPL-2.0 | differs: O:kernel/fileSystem.cpp:1014, 1019-1030 reports a regular file 0100777 | S | L | e4-now | Wrong result for `S_ISCHR` checks; low value |
| 53 | KK20 (+KL07) | `sceKernelStopUnloadModule` with an unknown handle returns ESRCH | [KytyPS5 dfec14a] K:libs/libKernel.cpp:1273-1276; pre-4644c52 **+ KL07** [KytyPS5 dfec14a] src/libs/libKernel.cpp @ dfec14a:1272-1276; pre-4644c52 | GPL-2.0 | differs: O:libs/libKernel.cpp:1362-1365 returns OK / KL07: differs: libs/libKernel.cpp:1362-1365 returns OK | S | L | e4-now | Wrong result |
| 54 | KK26 | posix `pthread_attr_setstack` (`-SrbXpGR1f0`) | [KytyPS5 dfec14a] K:kernel/pthread.cpp:4272-4274; K:libs/libKernel.cpp:2179; pre-4644c52 | GPL-2.0 | missing wrapper and registration; `PthreadAttrSetstack` exists O:kernel/pthread.cpp:2411 | S | L | e4-now | Stub ignores the title's stack: a thread sized for a large own stack runs on the default one (overflow) |
| 55 | KK27 | `sceKernelGetAvailableCpumask` (`La9uyZv4Kvw`) returns 0x1FFF (CPUs 0-12) | [KytyPS5 dfec14a] K:libs/libKernel.cpp:1768-1772, 3416; corroborated AnyPS5 `27c88a8` core/libs/prx/libkernel/Pthread/src/Thread.cpp:1093, docs/dev/debt/libkernel.md:68 (titles pin within 0x1FFB); pre-4644c52 | GPL-2.0 | missing (stub returns 0, an empty mask) | S | L | e4-now | Title computes 0 workers or pins to nothing. CPU 13 availability TODO(verify) |
| 56 | KK28 | `sceKernelClearVirtualRangeName` (`mkgXxsoxWHg`): name the range "" | [KytyPS5 dfec14a] K:kernel/memory.cpp:1893-1907; libKernel.cpp:3118; pre-4644c52 | GPL-2.0 | missing; O:kernel/memory.cpp:2610-2635 has only Set (memory agent's file: coordinate) | S | L | e4-now | VirtualQuery keeps the old name; low value |
| 57 | KK36 | `O_CLOEXEC` (0x00100000) at open sets the descriptor's FD_CLOEXEC | [KytyPS5 dfec14a] K:kernel/fileSystem.cpp:471; test KernelFileSystemTests.cpp:367-394 @dfec14a; pre-4644c52 | GPL-2.0 | differs: O:kernel/fileSystem.cpp:480-483 ignores it (flag kept only via fcntl, 1375-1406) | S | L | e4-now | `F_GETFD` read-back only; low value |
| 58 | SK13 (+KK22) | Alias registrations onto functions we already have: SoZkxZkCHaw sceKernelFcntl, VW3TVZiM4-E sceKernelFtruncate, 30Rh4ixbKy4 sceKernelFdatasync, KIbJFQ0I1Cg fdatasync, NN01qLRhiqU rename, ayrtszI7GBg truncate, 3eqs37G74-s pthread_getthreadid_np. | [sharpemu 514d766] `Kernel/KernelFileExtendedExports.cs:185-191, 242-244, 274-276, 322-324, 444-446`; `Kernel/KernelPthreadCompatExports.cs:343-351, 431-435` **+ KK22** [KytyPS5 dfec14a] K:libs/libKernel.cpp:3102; pre-4644c52 | GPL-2.0 + GPL-2.0+ | missing NIDs; bodies exist: `kernel/fileSystem.cpp:1375, 1064, 1328, 1444, 1178`; `libs/libKernel.cpp:2297`; `kernel/pthread.cpp:3924` / KK22: missing registration only: O:kernel/fileSystem.cpp:1064-1105 implements it; only posix `ftruncate` (`ih4CD9-gghM`, O:libs/libKernel.cpp:2401) is registered | S | L | e4-now | each returns a value / errno today lost to the 0-stub (e.g. getthreadid 0, fcntl F_GETFL 0) |
| 59 | SK14 | Missing cTDYxTUNPhM pthread_condattr_getclock, h0qUqSuOmC8 pthread_condattr_getpshared, 3BpP850hBT4 pthread_condattr_setpshared. | [sharpemu 514d766] `Kernel/KernelPthreadCompatExports.cs:668-712, 1372-1416` | GPL-2.0+ | missing (attr struct `kernel/pthread.cpp:502-506` has clock_id) | S | L | e4-now | out-params unwritten today |
| 60 | SK15 | Missing aPcyptbOiZs sigprocmask and VkTAsrZDcJ0 sigfillset; our _sigprocmask (6xVpy0Fdq+I) returns 0 without writing `oset`. sharpemu keeps a per-thread 16-byte mask, validates `how`, writes oset. | [sharpemu 514d766] `Kernel/KernelRuntimeCompatExports.Signals.cs:13-49`; 8ddf660 2026-10-31 "[Kernel] Implement POSIX signal masks" | GPL-2.0+ | missing; differs: `libs/libKernel.cpp:476-484` | S | L | e4-now | oset read uninitialised today |
| 61 | SK17 | Missing Ult queue/pool ops: RVSq2tsm2yw sceUltQueuePop (blocking), 6Mc2Xs7pI1I sceUltQueueTryPush, PP9nZxpSKLY sceUltQueueDestroy, or55417wcDk sceUltWaitingQueueResourcePoolDestroy, dh11uAUWNyM sceUltQueueDataResourcePoolDestroy. Pop via the stub returns 0 and writes nothing (consumer processes garbage). | [sharpemu 514d766] `Ult/UltExports.Sync.cs:167-190, 499-516, 518-560, 564-620`; 1f4425b | GPL-2.0+ | missing (`libs/libUlt.cpp:67-74` state, 459-485 TryPop) | S | L | e4-now | real behaviour |
| 62 | SK18 | Missing jOsUG0BJI-Y sceUltMutexTryLock, jW+HnafeS3Y sceUltMutexDestroy; our UltMutexUnlock calls `recursive_mutex::unlock` for a non-owner (undefined behaviour). sharpemu tracks the owner: TryLock BUSY, Destroy BUSY if owned, Unlock by non-owner PERMISSION 0x80810005. | [sharpemu 514d766] `Ult/UltExports.Sync.cs:214-320`, error constants `Ult/UltExports.cs:8-12` | GPL-2.0+ | missing; differs: `libs/libUlt.cpp:39-42, 534-567` | S | L (recursion kept as is, see SK31) | e4-now | real behaviour + removes UB |
| 63 | SK19 | Missing Ult aliases: RlN-xQPtYnM sceUltUlthreadCreate, 81ag9-mItVY sceUltUlthreadRuntimeCreate, 7+pdaXR9jWw sceUltUlthreadRuntimeOptParamInitialize (same bodies as the `_sce` NIDs we have), V89UhsfEhJk / vIuen2qlRmo sceUltUlthreadOptParamInitialize (zero 128 bytes, NULL -> 0x80810001). | [sharpemu 514d766] `Ult/UltExports.cs:104-160, 216-231` (both NIDs on one method), `139-150` | GPL-2.0+ | missing; bodies `libs/libUlt.cpp:144-200, 207-262` | S | L | e4-now | a title using the non-underscore names gets no runtime / no ulthread |
| 64 | SK20 | Missing 9oiX1kyeedA bzero, jogUIsOV3-U htons (libKernel exports). | [sharpemu 514d766] `Kernel/KernelSocketCompatExports.cs:738-755, 797-806`; 4f028d0 2026-07-14 | GPL-2.0+ | missing | S | L | e4-now | bzero writes memory, htons returns a value; the stub does neither |
| 65 | SK21 | sceLibcHeapGetTraceInfo (NWtTN10cJzE) exits when `info->size != 32`, dereferences NULL, returns void. sharpemu: NULL/size mismatch -> error, else fills and returns 0. | [sharpemu 514d766] `LibcInternalExports.cs:20-52` | GPL-2.0+ | differs: `libs/libC.cpp:658-665` | S | L | e4-now | crash |

#### e4-now, ranks 66-71: loader / process services (in the part's own value order)

| Rank | ID | What | Source | Licence | Ours | Effort | Risk | Class | Value |
|---|---|---|---|---|---|---|---|---|---|
| 66 | KL04 | UserService login set consistent: GetEvent sends Login only for logged-in users; per-user getters return NOT_LOGGED_IN for the others; GetUserNumber = player+1 | [KytyPS5 dfec14a] src/libs/libUserService.cpp @ dfec14a:44-51, 75-93, 95-111, 134-148 (and the getters 150-280 using GetLoggedInPlayer); pre-4644c52 | GPL-2.0 | differs: libs/libUserService.cpp:78-92 (Login events for all of 1000..1003 while GetLoginUserIdList 94-113 reports only KYTY_BC5_LOGIN_USERS, default 1), 24-26 IsLocalUser accepts 1000..1003 (used at 135,150,171,187,202,218,234,250,266), 139 `*number = 1` | S | M: pad/user binding of the two titles (the ASTRO BOT note at 98-102); re-run the pad checks | e4-now | Today a title that follows login events opens users 1001-1003 the list says are not logged in, exactly the second-controller problem the list fix solved; GetUserNumber says 1 for every user |
| 67 | KL05 | sceSystemServiceParamGetInt id 400 = system language | [KytyPS5 dfec14a] src/libs/libSystemService.cpp @ dfec14a:34, 118-119 (comment cites title PPSA01325); pre-4644c52 | GPL-2.0 | differs: libs/libSystemService.cpp:113-131, id 400 hits `default` -> 0 | S | L | e4-now | Wrong result: a title reading id 400 gets 0 = Japanese |
| 68 | KL06 | Sysmodule keeps load state: refcounted Load, Unload of a not-loaded id -> 0x805A1001, IsLoaded -> 0x805A1001 unless loaded | [KytyPS5 dfec14a] src/libs/libSysmodule.cpp @ dfec14a:24-59, 65-118; pre-4644c52 | GPL-2.0 | differs: libs/libSysmodule.cpp:25-63 (all return 0) | S | M: a title that calls IsLoaded first now sees UNLOADED and loads; one that unloads twice gets an error | e4-now | Wrong result for IsLoaded/Unload. KytyPS5's native table (id 0x0115 -> /app0/sce_module/libSceNpCppWebApi.prx via LoadStartModule) is already covered by our boot preload (runtimeLinker.cpp:2310-2410), so the spec leaves it out |
| 69 | KL10 | Guest stack walk probes every frame with IsReadableRange, stops on non-increasing `next`, uses rsp as window base for the libc abort trace | [KytyPS5 dfec14a] src/loader/runtimeLinker.cpp @ dfec14a:544-577, 1522-1537; src/libs/libC.cpp @ dfec14a:225; pre-4644c52 | GPL-2.0 | differs: loader/runtimeLinker.cpp:716-758 (dereferences frames unchecked), 2062-2066 StackTrace(rbp) only, used at 1068 inside the exception handler; libs/libC.cpp:233 | S | L | e4-now | Diagnostics only: a bad frame chain faults inside our crash reporter, losing the report the session needs |
| 70 | KL11 | x64 trap emulation fixes: RDPID decoded properly (dest reg, TSC_AUX, 4/5-byte length); SSE4a register forms `66 0F 79` EXTRQ / `F2 0F 79` INSERTQ; CLWB (`66 0F AE /6` mem) as CLFLUSH | [KytyPS5 dfec14a] src/loader/x64InstructionEmulator.cpp @ dfec14a:585-649 (SSE4a), 651-715 (RDPID, CLWB); pre-4644c52 | GPL-2.0 | differs: loader/x64InstructionEmulator.cpp:975-981 (Linux) / 657-662 (Win) RDPID matches any `F3 0F C7 xx`, writes RAX=0, advances 3 bytes; 802-859 / 500-556 SSE4a immediate forms only; no CLWB (983-989 only `0F 08/09`) | S | L: only reached on SIGILL | e4-now | No effect on the BC-250 (Zen 2 has RDPID, SSE4a, CLWB natively); correct on other hosts, and our RDPID path is wrong where it is reached |
| 71 | KL12 (+SS06) | sceSystemServiceGetNoticeScreenSkipFlag from a `--skip-notice-screen` flag (default false) | [KytyPS5 dfec14a] src/libs/libSystemService.cpp @ dfec14a:231-241; src/main.cpp @ dfec14a:110, 232; src/common/emulatorConfig.h @ dfec14a:101, 172; emulatorConfig.cpp:236-238; pre-4644c52 **+ SS06** [sharpemu 514d766] SystemService/SystemServiceExports.cs:62-107 (eb252af 2026-07-23: titles use it as a preference store and expect a later get to see the set value) | GPL-2.0 + GPL-2.0+ | differs: libs/libSystemService.cpp:241 `*value = false` / SS06: differs: O libs/libSystemService.cpp:234-256 (Get always false, Set ignores its argument) | S | L: default unchanged | e4-now | Startup flag to skip logos/notices in titles that honour it |

#### e4-now, ranks 72-90: audio / media (in the part's own value order)

| Rank | ID | What | Source | Licence | Ours | Effort | Risk | Class | Value |
|---|---|---|---|---|---|---|---|---|---|
| 72 | KA09 | AJM AAC RAW (config 2): instance channel count is a limit; derive channels from the first raw packet (CPE -> 2) via AV_PKT_DATA_NEW_EXTRADATA; TOO_MANY_CHANNELS (0x40) when the stream exceeds the limit | [KytyPS5 dfec14a] ajm/aac_decoder.h:41-43, 97-101, 210-213, 298-316, 364, 371; ajm/decoder.h:82; pre-4644c52 | GPL-2.0 | differs: ajm/aac_decoder.h:191-210 builds the AudioSpecificConfig at open from the instance's max channels (an 8-ch instance decoding a stereo stream is configured as 7.1) | S | M (AJM decode path); replug | e4-now | wrong/failed decode of raw AAC |
| 73 | KA10 | sceAudioOut2PortSetAttributes validation: attributes null with num != 0 -> INVALID_PARAM; unknown port -> AUDIO_OUT2_ERROR_INVALID_PORT (0x80268009); duplicate attribute id or null value or PCM value_size < 8 -> INVALID_PARAM | [KytyPS5 dfec14a] libAudio2.cpp:803-848, 872-883; pre-4644c52 | GPL-2.0 | differs: libAudio2.cpp:816-841 aborts on null attributes, returns OK for unknown ports and ignores malformed PCM attributes | S | M (hot path of the second title's Wwise sink); replug | e4-now | abort to error; console-like errors |
| 74 | KA11 | AudioOut2 user handles tracked: UserCreate null -> INVALID_PARAM; UserDestroy unknown -> INVALID_PARAM, still used by a port -> AUDIO_OUT2_ERROR_BUSY (0x80268007); PortCreate with an unknown user -> INVALID_PARAM | [KytyPS5 dfec14a] libAudio2.cpp:172, 183, 235, 712-716, 735, 916-945; pre-4644c52 | GPL-2.0 | differs: libAudio2.cpp:874-888 (UserCreate aborts on null, UserDestroy always OK), PortCreate (713-797) ignores params->user_handle | S | M (PortCreate check could refuse a port a title opens with a stale handle: give it a switch); replug | e4-now | error codes; needed by KA33 |
| 75 | KA12 | AvPlayer NV12 output: fill the luma padding with 16 (0 for full range) and chroma with 128 instead of 0 | [KytyPS5 dfec14a] avPlayer.cpp:1556-1561; pre-4644c52 (comment: "PPSA02433 samples the padded columns; zero chroma would turn them green") | GPL-2.0 | differs: avPlayer.cpp:1519 memsets the whole frame to 0 | S | L (CPU copy into the guest buffer only) | e4-now | green right/bottom edge on movies whose width is below the pitch |
| 76 | KA13 | AvPlayer file-callback IO: mask AVSEEK_FORCE, overflow-safe seek arithmetic, EINVAL on bad whence, a callback returning more than asked is AVERROR(EIO), free the AVIO buffer when avio_alloc_context fails, 64 KiB AVIO buffer | [KytyPS5 dfec14a] avPlayer.cpp:607-616, 621-667; pre-4644c52 | GPL-2.0 | differs: avPlayer.cpp:581-620 (seek with AVSEEK_FORCE set returns -1; no read > len guard; 4 KiB buffer leaked on alloc failure) | S | L | e4-now | failed seeks in movies opened through file callbacks |
| 77 | KA14 | sceAjmBatchInitialize: buffer or info null -> AJM_ERROR_INVALID_PARAMETER | [KytyPS5 dfec14a] ajm.cpp:721-735; pre-4644c52 | GPL-2.0 | differs: ajm.cpp:876-890 EXIT_NOT_IMPLEMENTED | S | L | e4-now | abort to error (low) |
| 78 | KA15 | libFont: accept CFF OpenType ('OTTO') fonts for stb_truetype | [KytyPS5 dfec14a] libFont.cpp:733-742 (741); pre-4644c52 | GPL-2.0 | differs: libFont.cpp:742-749 accepts only 0x00010000/'true'; OTTO fonts fall back to the substitute font | S | L (needs stb_truetype with CFF: v1.26 per refs/Coder787-source_KytyPlus/3rdparty/stb; our 3rdparty not in the extracted tree, verify) | e4-now | correct glyphs for OTF titles |
| 79 | KA16 | AudioOut2 queue drain at an exact 48 kHz grain rate: 1/6-us ticks, one grain = num_grains*125 ticks, no 1000-us floor | [KytyPS5 dfec14a] libAudio2.cpp:277-280, 346-371, 558, 643; 7ff8aff 2026-10-27 "audio: drain the AudioOut2 queue at an exact 48 kHz grain rate" | GPL-2.0 | differs: libAudio2.cpp:353-380 uses integer microseconds (512 grains = 10666 us, 0.006 % fast) | S | L-M (exp 0188 advanced model reads the device queue, the timer is only its fallback); replug | e4-now | timing drift (low) |
| 80 | KA29 | sceAudioOutGetSystemState (R5hemoKKID8): null -> AUDIO_OUT_ERROR_INVALID_POINTER, else zero the 32-byte state, OK | [KytyPS5 dfec14a] audio.cpp:844-848, 961-972; libAudio.cpp:134; 2944d12 2026-10-21 "audio: implement sceAudioOutGetSystemState" | GPL-2.0 | missing (loader stub writes nothing) | S | L | e4-now | out-param written |
| 81 | KA30 | sceAudioInClose (Jh6WbHhnI68): free the port; invalid -> AUDIO_IN_ERROR_INVALID_HANDLE | [KytyPS5 dfec14a] audio.cpp:717-729, 1096-1103; libAudio.cpp:188; pre-4644c52 | GPL-2.0 | missing: ports never freed, the 9th open returns PORT_FULL | S | L; replug | e4-now | port leak |
| 82 | KA31 (+SS51) | sceAudioInGetSilentState (BohEAQ7DlUE): 0x1 (DEVICE_NONE) without a capture device; invalid handle -> INVALID_HANDLE | [KytyPS5 dfec14a] audio.cpp:38, 731-741, 1115-1125; libAudio.cpp:190; pre-4644c52 **+ SS51** [sharpemu 514d766] Audio/AudioInExports.cs:10-17 returns 0x80260101 only because sharp cannot open AudioIn | GPL-2.0 + GPL-2.0+ | missing (stub returns 0 = "mic present") / SS51: missing; OURS opens AudioIn ports (libs/audio.cpp:1542-1580) so needs its own answer | S | L | e4-now | titles learn there is no mic |
| 83 | KA32 | sceAudioInHqOpen (nya-R5gDYhM): open an HQ port (len 128, 48000 Hz, else INVALID_SIZE/INVALID_FREQ) | [KytyPS5 dfec14a] audio.cpp:1038-1082, 1090-1094; libAudio.cpp:187; pre-4644c52 | GPL-2.0 | missing (stub returns 0, an invalid handle) | S | L; replug | e4-now | HQ voice-chat open |
| 84 | KA33 | sceAudioOut2UserGetSupportedAttributes (iE8trxPKnAg): null -> INVALID_PARAM, unknown user -> INVALID_PARAM, context_attributes = 0, port_attributes = supported attribute bits | [KytyPS5 dfec14a] libAudio2.cpp:947-963; libAudio.cpp:162; pre-4644c52 | GPL-2.0 | missing | S | L; replug | e4-now | report bit 0 (PCM) only until KA39/KA40 land |
| 85 | KA34 | Ngs2SystemGetInfo (vU7TQ62pItw), Ngs2SystemLock (gThZqM5PYlQ), Ngs2SystemUnlock (JXRC5n0RQls) with system handle lookup | [KytyPS5 dfec14a] ngs2.cpp:179-193, 327-335, 952-972, 1182-1221, 2060, 2901-2925; pre-4644c52 | GPL-2.0 | differs: libNgs2.cpp:120-163, 243-251 return OK and write nothing; no lock taken | S | L | e4-now | title-side locking around VoiceControl; info out-params |
| 86 | KA35 | JpegEnc (o6ZgXfFdWXQ QueryMemorySize, K+rocojkr-I Create, QbrU0cUghEM Encode, j1LyMdaM+C0 Delete) on stb_image_write | [KytyPS5 dfec14a] libJpegEnc.cpp:1-240; ba0e93d 2026-10-23 "libs: implement JpegDec and JpegEnc" | GPL-2.0 (stb: public domain/MIT) | differs: libJpeg.cpp:20-46 stubs return 0 (QueryMemorySize 0, Create writes no handle, Encode writes nothing) | S | L | e4-now | screenshots/share/upload thumbnails |
| 87 | KA36 (+SS40) | sceFontGetKerning (sDuhHGNhHvE) through stb_truetype kern tables | [KytyPS5 dfec14a] libFont.cpp:85-87, 128-135, 2058-2091, 2264; pre-4644c52 **+ SS40** [sharpemu 514d766] Font/FontExports.cs:409-434 (b4584f8 2026-09-22) | GPL-2.0 + GPL-2.0+ | missing (stub writes nothing) / SS40: missing | S | L | e4-now | kerning in libFont text |
| 88 | SS34 | sceAudioOut2LoContextGetQueueLevel (Q8DZkKQ-SYc) -> ContextGetQueueLevel | [sharpemu 514d766] Audio/AudioOut2Exports.cs:615-621 (e13cb28 2026-07-23) | GPL-2.0+ | missing; O libs/libAudio2.cpp:673-712 | S | L; audio path: replug check; file elsewhere quotes "the header" (:990,:1198), these lines do not | e4-now | stub writes no level: Wwise-style renderers see garbage |
| 89 | SS35 | sceAjmBatchJobRunBufferRa (ElslOCpOIns), RunSplitBufferRa (7jdAXK+2fMo): same nine args plus a return address | [sharpemu 514d766] Audio/AjmExports.cs:572-590 (2b6bd5a 2026-07-28) | GPL-2.0+ | missing; O libs/ajm.cpp:1186-1232 | S | L; replug check | e4-now | decode jobs silently dropped today |
| 90 | SS39 | sceAvPlayerSetAvailableBW (+7xJ+lFxmkQ) -> SetAvailableBandwidth | [sharpemu 514d766] AvPlayer/AvPlayerExports.cs:884-900 (both NIDs on one method) | GPL-2.0+ | missing; O libs/avPlayer.cpp:1994-2005 | S | L | e4-now | param validation/state kept |

#### e4-now, ranks 91-124: system services (in the part's own value order)

| Rank | ID | What | Source | Licence | Ours | Effort | Risk | Class | Value |
|---|---|---|---|---|---|---|---|---|---|
| 91 | KS07 | sce_net_errno holds positive errno (result - NET_ERROR_EPERM + 1), not the 0x8041xxxx code | [KytyPS5 dfec14a] K libs/libNet.cpp:52-57 (FinishNetCall), 85-87; pre-4644c52 (22b3178 only adds a caller) | GPL-2.0 | differs: O libs/libNet.cpp:20-27 (NET_CALL stores result), 71-79 (FinishSocketCall stores net_error) | S | M: anything reading errno changes value | e4-now | titles test sce_net_errno == EWOULDBLOCK/EINPROGRESS; ours never matches |
| 92 | KS08 | PlayGoGetChunkId(list==NULL) returns the total chunk count; list!=NULL && entries==0 -> BAD_SIZE | [KytyPS5 dfec14a] K libs/libPlayGo.cpp:209-245 (224-234); pre-4644c52 | GPL-2.0 | differs: O libs/libPlayGo.cpp:236-266 (254-255: BAD_POINTER; NULL+0 -> count 0) | S | M: PlayGo flow of titles | e4-now | wrong result: a count query answers 0 chunks |
| 93 | KS11 | Psml Initialize answers NOT_TRINITY_MODE (0x8a810012) on a base PS5; Psml_mfsr2 Initialize answers NOT_AVAILABLE (0x8a8a0012), its 8 other exports NOT_INITIALIZED; Psml aliases fccGInHrj8A/94iBp3KvIuI | [KytyPS5 dfec14a] K libs/libPsml.cpp:40,120-130,494-503,505-603,614-624,641,645; NOT_TRINITY_MODE 651ef73 2026-10-29 "graphics: add experimental Pro mode and linear PSSR"; mfsr2 02b17af 2026-11-02 "libs: implement Psml_mfsr2 and the 1100 Psml exports" | GPL-2.0 | differs: O libs/libPsml.cpp:113-121 (OK always) while O libs/libKernel.cpp:1408-1417 says base PS5; mfsr2 missing | S | M: a title that used the PSSR path stops | e4-now | consistency: ours tells titles PSSR/MFSR2 exist on a base console, then dispatches nothing. Console behaviour per KytyPS5 only (unverified) |
| 94 | KS12 | NpGetAccountAge / NpGetAccountLanguage2 complete their request (signed out) instead of answering synchronously | [KytyPS5 dfec14a] K libs/network.cpp:4164-4177,4369-4407; 15452a5 2026-10-29 "np: separate PSN emulation from host networking" | GPL-2.0 | differs: O libs/network.cpp:4560-4575 (no request lookup), O libs/libNet.cpp:1430-1444 | S | L | e4-now | async request: ours returns SIGNED_OUT from the call and NpPollAsync then answers INVALID_ID (request never completed) |
| 95 | KS18 | sceSaveDataConvert (2mfSRGdshtk) synchronous checks: PARAMETER (names, memory dirs, blocks 48..16384), INVALID_LOGIN_USER, NOT_FOUND, BUSY, EXISTS, NO_NEED_CONVERT (0x809F001E), BLOCKS_FEWER_THAN_SRC (0x809F0020) | [KytyPS5 dfec14a] K libs/libSaveData.cpp:234-242,1210-1258, errno.h:661-662; 22a9392 2026-10-25 "savedata: implement sceSaveDataConvert's synchronous checks" (test tests/SaveDataMemoryTests.cpp TestConvert) | GPL-2.0 | differs: O libs/libSaveData.cpp:1218-1234 (always NOT_FOUND) | S | M: the second title calls it before Mount3 (exp 0145); KytyPS5 ends in EXIT for a real conversion -- keep our NOT_FOUND there | e4-now | wrong result for existing saves (NO_NEED_CONVERT) |
| 96 | KS20 | Stubs that answer OK and write nothing: GameLiveStreamingGetCurrentStatus2 (zeroed, user_id -1), GetSocialFeedbackMessagesCount (type 1..3, count 0), SharePlay init state + GetCurrentConnectionInfoA (zeroed, user ids -1), NpGetUserIdByAccountId (INVALID_ARGUMENT / SIGNED_OUT) | [KytyPS5 dfec14a] K libs/libNet.cpp:2783-2830 (GLS), 2850-2905 (SharePlay), libs/network.cpp:4332-4350; GLS/SharePlay pre-4644c52; UserIdByAccountId f12fc20 2026-10-31 "Stub missing SystemService / NpManager / NpWebApi2 imports (Palworld, PPSA23126)" | GPL-2.0 | differs: O libs/libGameLiveStreaming.cpp:223,268; O libs/libSharePlay.cpp:30; O libs/libNet.cpp:4162-4176; O libs/libNp.cpp:347 | S | L | e4-now | guest reads uninitialised memory (a garbage count or user id) |
| 97 | KS21 | NpCommerceDialog result carries param->user_data (result layout int32,bool,void*,reserved[32]); PARAM_INVALID for size!=128 / mode>5 / reserved!=0 | [KytyPS5 dfec14a] K libs/libNet.cpp:1563-1585,1609-1645; pre-4644c52 | GPL-2.0 | differs: O libs/libNpCommerceDialog.cpp:36-40 (no user_data field), 58-76, 109-126 | S | L | e4-now | title gets user_data NULL back |
| 98 | KS22 | NetCtlGetInfo: null info -> INVALID_ADDR, code outside 1..21 -> INVALID_CODE before NOT_CONNECTED | [KytyPS5 dfec14a] K libs/network.cpp:3947-3962; pre-4644c52 | GPL-2.0 | differs: O libs/network.cpp:4074-4084 (EXIT_NOT_IMPLEMENTED on null) | S | L | e4-now | abort on null |
| 99 | KS23 | NpAuthGetAuthorizationCodeV3/GetIdTokenV3 check req_id, param, size (INVALID_SIZE 0x80550302), client_id/secret/scope | [KytyPS5 dfec14a] K libs/libNet.cpp:1737-1755,1921-1980; 15452a5 2026-10-29 | GPL-2.0 | differs: O libs/libNet.cpp:1908-1969 (no checks) | S | L | e4-now | error codes for bad params |
| 100 | KS24 | SaveDataDialogUpdateStatus answers RUNNING once before FINISHED ("Some games require a RUNNING update before FINISHED") | [KytyPS5 dfec14a] K libs/dialog.cpp:441,450,464-477; pre-4644c52 | GPL-2.0 | differs: O libs/dialog.cpp:388-401 (message modes finish at first poll; progress bar kept running -- keep that) | S | M: second title's save dialogs (F205 history) | e4-now | titles that need to see RUNNING |
| 101 | KS25 | Pad port state: NOT_INITIALIZED before scePadInit, ALREADY_OPENED on a second open, GetHandle NO_HANDLE when not open, Close releases | [KytyPS5 dfec14a] K libs/controller.cpp:1155-1212,1230-1281; pre-4644c52 | GPL-2.0 | differs: O libs/controller.cpp:1199-1262 (stateless), O libs/libPad.cpp:278 | S | M: titles that open twice now get an error | e4-now | API contract |
| 102 | KS28 | sceNetResolverStartNtoaMultipleRecords (RCCY01Xd+58): literal IPv4 -> 1 record; NetResolverInfo 384 bytes | [KytyPS5 dfec14a] K libs/network.h:40-56, libs/network.cpp:1464-1531, libs/libNet.cpp:139-144,253; 22b3178 2026-11-01 "net: implement sceNetResolverStartNtoaMultipleRecords" | GPL-2.0 | missing | S | L | e4-now | port the literal path and our Linux answer (ENOTIMPLEMENTED as O network.cpp:1503-1505); DNS goes with KS38 |
| 103 | KS30 (+SS31) | NpEntitlementAccess GetEntitlementKey (5LiMEPuW0DQ: PARAMETER / NO_ENTITLEMENT), GetGameTrialsFlag (y7JD1gfwyfA: 0), GenerateTransactionId (IQtb-TaIjSM: "6b797479"+24 hex), NOT_INITIALIZED before Initialize | [KytyPS5 dfec14a] K libs/libNpEntitlementAccess.cpp:24-28,118,181-193,207-232,475-492; pre-4644c52 (99044c7 adds only Pft) **+ SS31** [sharpemu 514d766] Np/NpEntitlementAccessExports.cs:98-116, 223-252 (1811cef, e17fb6f) | GPL-2.0 + GPL-2.0+ | missing; O libs/libNet.cpp:1576-1588 Initialize keeps no state / SS31: missing; O constants and owned list libs/libNet.cpp:1547-1548, 1570-1574 | S | L | e4-now | stub answers "has a key" (0) and leaves the key buffer uninitialised |
| 104 | KS31 | Http: SetRedirectCallback, SetCookieRecvCallback, SetRequestStatusCallback, SetInflateGZIPEnabled (any valid id), SetChunkedTransferEnabled (request id, 0/1), HttpsLoadCert/UnloadCert (ctx id), HttpsGetSslError, HttpGetLastErrno (write 0) | [KytyPS5 dfec14a] K libs/network.cpp:415-419,3064-3200; libs/libNet.cpp:754-762; pre-4644c52 | GPL-2.0 | missing (O helpers network.cpp:260-263) | S | L | e4-now | INVALID_ID / INVALID_VALUE paths and zeroed out-params |
| 105 | KS32 | NpWebApi2: contexts tracked; GetMemoryPoolStats (Xweb+naPZ8Y) writes {pool rounded to 16 KiB,0,0}; Terminate INVALID_LIB_CONTEXT_ID / LIB_CONTEXT_NOT_FOUND | [KytyPS5 dfec14a] K libs/libNet.cpp:2084-2108,2122-2155,2435-2445; pre-4644c52 | GPL-2.0 | missing; O libs/libNet.cpp:3451-3460,3792-3798 | S | L | e4-now | stats struct otherwise garbage |
| 106 | KS33 (+SS41) | scePadIsRemoteController (fCWdlnmB1Ks): handle check, *is_remote=false | [KytyPS5 dfec14a] K libs/controller.cpp:1348-1360; pre-4644c52 **+ SS41** [sharpemu 514d766] Pad/PadExports.cs:816-839 (e17fb6f 2026-09-27) | GPL-2.0 + GPL-2.0+ | missing | S | L | e4-now | bool left uninitialised |
| 107 | KS34 | sceConvertKeycodeGetImeKeyboardType (mUuUOWI-C+0): INVALID_ADDRESS / INVALID_USER_ID, *type=0 | [KytyPS5 dfec14a] K libs/libConvertKeycode.cpp:1-37; pre-4644c52 | GPL-2.0 | missing | S | L | e4-now | out-param unwritten |
| 108 | KS35 | sceVideoOutAddBufferAttributeOption (MBlv8YWoyOk): attribute->option \| = option | [KytyPS5 dfec14a] K graphics/presentation/videoOut.cpp:1335-1340, libs/libVideoOut.cpp:19; pre-4644c52 | GPL-2.0 | missing; O graphics/presentation/videoOut.cpp:96-109 has `option` at the same offset | S | L-M: option bits now reach buffer registration (GPU-side consumer, not submitted here) | e4-now | option bits silently dropped |
| 109 | KS36 | VideoOutVrrStatus gWT7X8H0bYs: GetOutputStatus + zero 8-byte VRR range at +0x30 | [KytyPS5 dfec14a] K libs/libVideoOutVrrStatus.cpp:43-62; pre-4644c52 | GPL-2.0 | missing (O libs/libVideoOut.cpp:53-60 registers only kP2L8t3j-aM) | S | L | e4-now | status buffer unwritten; layout from KytyPS5's observation of a title |
| 110 | KS37 | NetCtl host info on Linux: getifaddrs + /proc/net/route default route, netmask, ip | [KytyPS5 dfec14a] K libs/network.cpp:3757-3811; pre-4644c52 | GPL-2.0 | differs: O libs/network.cpp:3920 (non-Windows: connected=true, no addresses) | S | L: only with --network-online | e4-now | empty IP strings on Linux |
| 111 | SS05 (+KS19) | sceUsbdHandleEventsTimeout (+wU6CGuZcWk): validate {s64 sec, s64 usec} and sleep that long | [sharpemu 514d766] Usbd/UsbdExports.cs:64-102 (acb0d4a 2026-09-22; stated: keep guest USB event threads paced instead of a hot loop) **+ KS19** [KytyPS5 dfec14a] K libs/libUsbd.cpp:13,27-34; pre-4644c52 | GPL-2.0 + GPL-2.0+ | differs: O libs/libUsbd.cpp:673-682 returns at once / KS19: differs: O libs/libUsbd.cpp:673-680 (returns at once) | S | L | e4-now | CPU: a USB event thread spins on the 4-core-ish box; sceUsbdHandleEvents (O :643-650) has the same shape (not changed by sharp) |
| 112 | SS18 | scePlayGoGetLocus writes NOT_DOWNLOADED into the bad entry before returning BAD_CHUNK_ID | [sharpemu 514d766] PlayGo/PlayGoExports.cs (16a2131 2026-07-16) | GPL-2.0+ | differs: O libs/libPlayGo.cpp:188-194 leaves it unwritten | S | L | e4-now | small: defined output on the error path |
| 113 | SS24 | sceNetCtlRegisterCallbackV6 (1NE9OWdBIww) -> same as RegisterCallback | [sharpemu 514d766] Network/NetCtlExports.cs:149-154 (373100a) | GPL-2.0+ | missing; O libs/network.cpp:4013-4033 | S | L | e4-now | stub leaves *cid unwritten (garbage id later unregistered) |
| 114 | SS25 (+KS29) | Json aliases: Array C2/D2, String C2/D2, iterator D2, iterator operator->, Value::getValue(size_t), Value::clear | [sharpemu 514d766] Json/JsonExports.cs:489-494,531-548,667-686,777-782,807-812; JsonValueExports.cs:189-198 (b307b2f 2026-10-12, df53ff5, 864cbb0) **+ KS29** [KytyPS5 dfec14a] K libs/libJson2.cpp:1063-1075,1154; pre-4644c52 | GPL-2.0 + GPL-2.0+ | missing; targets exist: O libs/libJson2.cpp:1100-1121, 799-826, 1208-1224, 740-748, 224-240 / KS29: missing (O libs/libJson2.cpp:224-240 JsonValueClear exists) | S | L | e4-now | an unregistered C2 constructor returns 0 without setting impl: later use dereferences garbage |
| 115 | SS26 | Json Array::iterator default ctor (C1/C2), copy ctor (C1/C2), operator=, operator++(int), advance(size_t) | [sharpemu 514d766] Json/JsonExports.cs:731-764, 827-850 + helpers 852-910 (b307b2f) | GPL-2.0+ | missing; O iterator model libs/libJson2.cpp:1129-1224 | S | L | e4-now | range-for and std-style loops over sce::Json::Array |
| 116 | SS27 | sceAppContentGetAddcontInfoList (xnd8BJzAxmk): writes *hitNum | [sharpemu 514d766] AppContent/AppContentExports.cs:48-68 (4d73f46); shadPS4 app_content.cpp:269-295 | GPL-2.0+ | missing | S | L | e4-now | stub leaves hitNum uninitialised: title iterates a garbage count |
| 117 | SS28 | sceNpCommerceDialogOpen2 (IXmfUaze9So) -> same state machine as Open | [sharpemu 514d766] Np/NpCommerceExports.cs:41-46 (37694df 2026-09-19) | GPL-2.0+ | missing; O libs/libNpCommerceDialog.cpp:58-77 ignores the param, so a direct alias fits | S | L | e4-now | stub leaves the dialog INITIALIZED: a title polling for FINISHED waits forever |
| 118 | SS29 | sceSaveDataUmount (BMR4F-Uek3E) = Umount2(0, mp); sceSaveDataGetProgress (ANmSWUiyyGQ) writes 1.0f | [sharpemu 514d766] SaveData/SaveDataExports.cs:263-265, 535-549 (9415395); shadPS4 savedata.cpp:1705-1708, 1096-1108 | GPL-2.0+ | missing; O libs/libSaveData.cpp:885-910 | S | L | e4-now | stub Umount never frees the slot: 17th mount -> MOUNT_FULL |
| 119 | SS30 | sceSystemServiceGetMainAppTitleId (4veE0XiIugA): TITLE_ID into a 16-byte field | [sharpemu 514d766] SystemService/SystemServiceExports.cs:109-133 (b4b9501 2026-07-16) | GPL-2.0+ | missing | S | L | e4-now | out-param |
| 120 | SS32 | sceNpAuthGetAuthorizedAppCode (IDX0S5EsEh4): same signed-out completion as GetAuthorizationCodeV3 | [sharpemu 514d766] Np/NpAuthExports.cs:154-158 + 180-217 (37694df) | GPL-2.0+ | missing; O libs/libNet.cpp:1908-1940 pattern | S | L | e4-now | error code instead of 0 (title thinks it got a code) |
| 121 | SS33 | sceNpSessionSignalingCreateContext2 (aBuX0PX-T7I) returns a positive id; RequestPrepare (r8mVMwlafF8) returns SIGNED_OUT 0x80550006 | [sharpemu 514d766] Np/NpSessionSignalingExports.cs:24-41 (e17fb6f, d0dd3fe) | GPL-2.0+ | missing (O libs/libNet.cpp:1534-1539 has Init/Term/Deactivate/Destroy) | S | L | e4-now | context id 0 may be read as failure |
| 122 | SS36 | sceAmprCommandBufferWaitOnAddress (V7GQTEeUfhw), sceAmprMeasureCommandSizeWaitOnAddress (jIlc4p5dSD0): non-_04_00 forms (compare <= 3 instead of <= 6) | [sharpemu 514d766] Ampr/AmprExports.cs:613-642, 835-869, 1748-1769 (8feea60 2026-09-25) | GPL-2.0+ | missing; _04_00 forms exist: O libs/libAmpr.cpp:3050-3066, 2743-2748, 3668, 3688 | S | L | e4-now | stub measure 0 -> undersized APR command buffers |
| 123 | SS37 | scePlayGoSetLanguageMask (LosLlHOpNqQ) stores the mask; GetLanguageMask returns it | [sharpemu 514d766] PlayGo/PlayGoExports.cs:680-702 (01ebab9 2026-06-23) | GPL-2.0+ | missing; O libs/libPlayGo.cpp:381-395 returns a constant | S | L | e4-now | round-trip of a title setting |
| 124 | SS38 | sceRtcGetCurrentAdNetworkTick (LN3Zcb72Q0c), DebugNetworkTick (Ot1DE3gif84), RawNetworkTick (HWxHOdbM-Pg) -> current tick | [sharpemu 514d766] shadPS4 rtc.cpp:390-507 (primary; sharp RtcExports.cs:163-242 is from flagged 56bf00e) | GPL-2.0+ | missing; O libs/libRtc.cpp:107-126 | S | L | e4-now | out-param tick |

### 4.3 later (ranks 125-253): the named larger items first, then S before M before L, registration-only stubs last

| Rank | ID | What | Source | Licence | Ours | Effort | Risk | Class | Value |
|---|---|---|---|---|---|---|---|---|---|
| 125 | KK05 | libc `gmtime/localtime/mktime/strftime` on a 9-int (36-byte) guest `struct tm`, converted to/from host `std::tm` | [KytyPS5 dfec14a] K:libs/libC.cpp:340-444; pre-4644c52 | GPL-2.0 | differs: O:libs/libC.cpp:367-436 passes the guest pointer as host 56-byte `std::tm`: glibc `mktime` writes `tm_gmtoff`/`tm_zone` 20 bytes past a 36-byte guest struct; `strftime` copies 56 bytes (l.429) | S | L: if the guest struct were the 56-byte FreeBSD one, KytyPS5's form only leaves gmtoff/zone unset | later (downgraded at merge: the 36-byte guest struct tm is KytyPS5's assertion, unverified; verify the layout first) | Guest memory corruption on `mktime`. Guest size 36 is KytyPS5's `static_assert` (l.352), uncited: TODO(verify) |
| 126 | KK19 (+KL08) | Module reference count: a repeated `sceKernelLoadStartModule` of a loaded module takes a reference; `sceKernelStopUnloadModule` only unloads at the last one (`Program::load_count`). `kernel/module.h` exposes both to KytyPS5's libSysmodule (K:libs/libSysmodule.cpp:50, 85; sysmodule agent) | [KytyPS5 dfec14a] K:libs/libKernel.cpp:1228-1235, 1245, 1278-1281; K:loader/runtimeLinker.h:124; K:kernel/module.h:1-24; pre-4644c52 **+ KL08** [KytyPS5 dfec14a] src/libs/libKernel.cpp @ dfec14a:1228-1233, 1245, 1278-1281; src/loader/runtimeLinker.h @ dfec14a:124; pre-4644c52 | GPL-2.0 | differs: O:libs/libKernel.cpp:1319-1325 returns the existing handle without a reference; 1360-1389 unloads on the first stop / KL08: differs: libs/libKernel.cpp:1319-1325 (returns the handle, no count), 1348-1390 (first StopUnload unloads) | S | M: loader struct change | later | Use-after-unload when two users share a module. Not e4-now: a CPU test needs a loadable module image |
| 127 | KL09 | Every LoadStartModule re-runs relocation of ALL loaded programs for still-unresolved records (rela_bits); unload re-resolves importers that pointed into the unloaded module | [KytyPS5 dfec14a] src/loader/runtimeLinker.cpp @ dfec14a:876-926, 1096-1167, 1974-1978, 2019-2055; src/loader/symbolDatabase.cpp @ dfec14a:68-75; pre-4644c52 | GPL-2.0 | differs: loader/runtimeLinker.cpp:1658-1665 RelocateProgram relocates only the new program; unresolved FUNC imports late-resolve in the stub thunk (320-344), but OBJECT imports stay `g_invalid_memory` (1360) and NOTYPE keep the ELF value (1369). Unload (1667-1683) already re-runs RelocateAll | S (ours: RelocateProgram -> RelocateAll(), our imports-only pass 2977-2982 already re-resolves) | M: rewrites GOT slots of every module while guest threads run (same values except stub -> real); needs two-PRX fixture to test | later | Data imports of an earlier module that a later-loaded PRX exports fault on first access today |
| 128 | SK22 | Missing Ult condition variables: jnKaHGkrxZ4 _sceUltConditionVariableCreate, xrmmI832R4U ..Destroy (BUSY with waiters), 5xGAHCxA8M0 ..Wait (releases the Ult mutex, re-acquires), JTw1cAVkuc0 ..Signal, byiceqcMvV0 ..SignalAll (+ RVmEia0vXMI opt-param init, stub-level). | [sharpemu 514d766] `Ult/UltExports.Sync.cs:321-470` | GPL-2.0+ | missing | M | M: needs SK18 owner tracking; recursive_mutex vs condvar | later | real behaviour |
| 129 | SK23 | Missing Ult ulthread lifecycle: kF--s3xZjco sceUltUlthreadExit, xOQ9oACobA4 ..GetSelf (PERMISSION outside an ulthread), HFd-lpjGxJA ..Yield, DsW+3FTXL0Q ..TryJoin (BUSY while running), -gxcs521SvA sceUltUlthreadRuntimeDestroy (BUSY with live ulthreads). | [sharpemu 514d766] `Ult/UltExports.cs:194-215, 301-420` | GPL-2.0+ | missing (`libs/libUlt.cpp:202-300`) | M | L | later | Exit/GetSelf return values matter to workers |
| 130 | KK30 | Mutex FIFO ownership hand-off (waiter list, owner transferred on unlock, no barging) and per-thread cond condition variables | [KytyPS5 dfec14a] K:kernel/pthread.cpp:368-384, 1275-1416, 417-439, 492-531, 2879-2960; test KernelFileSystemTests.cpp:114-271 @dfec14a; pre-4644c52 | GPL-2.0 | differs: O:kernel/pthread.cpp:1373-1495 (barging, 1 ms poll), 3081-3160 (one cv per cond, notify_all) | M | M: lock fairness and throughput change everywhere | later | Starvation of waiters under contention; thundering herd on signal |
| 131 | KK29 | `scePthreadCancel` (`qBDmpCyGssE`) registration, with ESRCH for joined threads and host cancellation disabled inside guest mutex waits | [KytyPS5 dfec14a] K:libs/libKernel.cpp:3221; K:kernel/pthread.cpp:3403-3425, 1317-1350; pre-4644c52 | GPL-2.0 | missing registration; O:kernel/pthread.cpp:3661-3677 exists (no `free` check) | M | H: host `pthread_cancel` unwinds through emulator frames at host cancellation points | later | Stub returns 0 and does not cancel: a title waiting for the cancelled thread to exit can hang |
| 132 | KS40 | SaveData memory model per slot (0..3) and user: options SET_PARAM/DOUBLE_BUFFER, 32 MiB total, LIMITATION_OVER, BUSY, MEMORY_NOT_READY, init_param, param stored/returned, range checks (no grow on read) | [KytyPS5 dfec14a] K libs/libSaveData.cpp:270-280,338-347,442-483,771-932; pre-4644c52 | GPL-2.0 | differs: O libs/libSaveData.cpp:248,693-848 (one global vector for all slots/users, grows on read) | M | M: first title's memory save file layout | later | correctness for multi-slot titles |
| 133 | KA17 | AudioOut2 destroy vs in-flight push: per-context submission copy and mutex, ContextDestroy/PortDestroy wait for a running push before closing handles | [KytyPS5 dfec14a] libAudio2.cpp:223-232, 273-275, 437-473, 595-598, 794-797; b46eeb7 2026-10-21 "audio: stop AudioOut2 contexts from stalling each other (PPSA09809)" (+ pre-4644c52) | GPL-2.0 | differs: libAudio2.cpp:403-427 releases the port mutex and then reads `state.downmix` (a per-port vector PortDestroy can free) and closes handles without waiting (799-814) | M | M; replug | later | rare use-after-free on port/context destroy during a push |
| 134 | KA18 | AudioOut2 PCM ownership: PCM copied at SetAttributes; a push consumes it, a port not fed again falls silent | [KytyPS5 dfec14a] libAudio2.cpp:437-470, 872-882; 64a554d 2026-10-27 "audio: a pushed AudioOut2 grain consumes its ports' PCM" (copy pre-4644c52) | GPL-2.0 | differs: libAudio2.cpp:550-579 (Advance copies the port's last pointer every grain, exp 0188) and 403-427 (non-advanced push replays the pointer): a port the title stops feeding repeats its last buffer | M | H (exp 0188 tuned on the second title); replug | later | stale-buffer buzz on abandoned ports |
| 135 | KL13 | Boot loads and starts only /app0/sce_module/libc.prx; every other PRX waits for the title's sceKernelLoadStartModule and gets the title's args/argp in module_start | [KytyPS5 dfec14a] src/loader/runtimeLinker.cpp @ dfec14a:1268-1281; pre-4644c52 | GPL-2.0 | differs: loader/runtimeLinker.cpp:1784-1792 PreloadAdjacentPrograms (2310-2410: every .prx/.sprx in root, sce_module, sce_modules) + StartAllModules (2128-2157) with args 0/NULL before main; LoadStartModule of a preloaded PRX then skips module_start (libKernel.cpp:1319-1325) | M | H: changes the boot of both titles (init order, module_start args) | later | Fidelity of init order and module_start arguments; our model runs PRX initialisers before main |
| 136 | KL16 | sceSystemServiceLoadExec (NID JoBqSQt1yyA): validate `/app0/` path (else SYSTEM_SERVICE_ERROR_PARAMETER), argv <= 4096 bytes, re-exec the emulator with `--guest-exec <path> args...`; guest argv passed to main | [KytyPS5 dfec14a] src/loader/loadExec.cpp @ dfec14a:44-191 (906d255 2026-10-24 "launcher: option to close the terminal after a clean exit" changed the exit); src/libs/libSystemService.cpp @ dfec14a:103-106, 588; src/main.cpp:298-301; src/loader/runtimeLinker.cpp:1286-1296; runtimeLinker.h:17-21; pre-4644c52 otherwise | GPL-2.0 | missing (unregistered -> loader stub returns 0, title believes the exec happened); argv fixed to `{"KytyEmu"}` at runtimeLinker.cpp:1796-1801 | M | M: process re-exec on the box (pid tracking of box scripts, log continuation) | later | Titles that chain executables (launcher -> game, mode switch) break today. argv[0]: KytyPS5 passes "" by default, ours "KytyEmu"; which the console uses is not verified |
| 137 | SK26 | Missing iiQjzvfWDq0 dup, wdUufa9g-D8 dup2; fcntl F_DUPFD/F_DUP2FD fail EINVAL in ours. sharpemu shares the open file (offset) between descriptors. | [sharpemu 514d766] `Kernel/KernelFileExtendedExports.cs:384-470`; 956da76 (errno on bad fd) | GPL-2.0+ | missing; `kernel/fileSystem.cpp:72-104` has no shared/refcounted File | M | M: descriptor table change | later | real behaviour |
| 138 | SK27 | Missing ku7D4q1Y9PI poll: sharpemu reports every requested POLLIN/POLLOUT as ready (regular files). | [sharpemu 514d766] `Kernel/KernelFileExtendedExports.cs:488-528` | GPL-2.0+ | missing | M | L | later | files-only version is S; sockets need SK24 |
| 139 | SK28 | Missing VHCS3rCd0PM sceKernelAddReadEvent / JxJ4tfgKlXA sceKernelDeleteReadEvent (EVFILT_READ on an fd, polled readiness). | [sharpemu 514d766] `Kernel/KernelEventQueueCompatExports.cs:498-560, 1659-1835` | GPL-2.0+ | missing | M | L | later | needs fd readiness (sockets) |
| 140 | SK29 | Missing module queries: kUpgrXIrz7Q sceKernelGetModuleInfo, QgsKEUfkqMA ..Info2, HZO7xOos4xc ..InfoInternal, IuxnUuXk6Bg sceKernelGetModuleList, ZzzC3ZGVAkc ..List2 (size-checked info structs, handle lists). | [sharpemu 514d766] `Kernel/KernelRuntimeCompatExports.cs:951-1012, 1550-1660`, `Kernel/KernelModuleRegistry.cs` | GPL-2.0+ | missing; we have `KernelGetModuleInfoFromAddr` `libs/libKernel.cpp:1739` and Program::unique_id `loader/runtimeLinker.h:117` | M | L | later | real out-params |
| 141 | KA37 (+SS07) | NGS2 renderer: sampler voices decode PCM16 and ATRAC9 waveform blocks (streamed, dataless, CANCEL, CLEAR reopen), voice ports/matrices/patches (rack-handle patch -> voice 0), submixer, reverb dry path, mastering with full-band/LFE gain mixed into the output buffer's channel count, custom racks/user FX, ParseWaveformData (ATRAC9 RIFF), CalcWaveformBlock (ATRAC9 and 16-bit PCM) | [KytyPS5 dfec14a] ngs2.cpp:394-930, 1248-1284, 1560-2062, 2064-2241, 2366-2765; pre-4644c52 base + 05694ab 2026-10-22, 8cfe1c4 10-29, bc4333e 10-29 (Isaac: zeroed PCM blocks gave no audio), 67f8276, e66a7f5, 2aa0d58, 9bf311c, 08a7d7f, 2f6dccb, b65dd18 10-30, e0621a7, 4234458 11-01 **+ SS07** [sharpemu 514d766] Ngs2/*.cs (2cd6676 2026-10-20, 2409 lines in 9 files) | GPL-2.0 + GPL-2.0+ | differs: audio.cpp:2999-3066 zeroes the render buffers and only steps voice states; ParseWaveformData/CalcWaveformBlock return fake values (3068-3099) / SS07: differs: O libs/audio.cpp:2999-3022 Ngs2SystemRender memsets the buffers and only steps voice states | L | M (new mixer; AT9 via LibAtrac9 + ours exp 0243); replug | later | every NGS2 title is silent in ours; tests/Ngs2SamplerTests.cpp in KytyPS5 |
| 142 | SK24 (+KS38) | POSIX sockets on the Linux host: socket/bind/connect/listen/accept/send/recv... return -1/ENOSYS (Windows-only backend). sharpemu has a cross-platform host-socket emulation (TcpClient/Socket) with an outbound policy; ecbb0db keeps the fd after a failed connect. | [sharpemu 514d766] `Kernel/KernelSocketCompatExports.cs` (whole file, connect 557-640); ecbb0db 2026-07-18 **+ KS38** [KytyPS5 dfec14a] K libs/network.cpp:844-2720; pre-4644c52 | GPL-2.0 + GPL-2.0+ | differs: `libs/network.cpp:1856-1858` and every `#else ENOSYS` (1783, 1890, 1923, 1948, ...) / KS38: differs: O libs/network.cpp:1043-2367 (Windows only; ENOSYS on Linux) | L | M | later | titles that probe the network get an unusual errno; an offline-friendly ECONNREFUSED/ENETUNREACH path is a cheaper first step |
| 143 | KS39 (+SS14) | Trophy system: NpTrophy2 contexts/registration with real package data (sce_sys/trophy2), unlock persistence, platinum, UDS `_UnlockTrophy` and stat rules, unlock notification overlay; NpTrophy2/UDS error codes | [KytyPS5 dfec14a] K libs/libTrophy.cpp:1-1334, common/trophies.cpp/.h (447 lines), graphics/presentation/systemOverlay; pre-4644c52 **+ SS14** [sharpemu 514d766] Np/* (5052fae 2026-10-13; message: rules follow KytyPS5's NpTrophy2/UDS code) | GPL-2.0 + GPL-2.0+ | differs: O libs/libNet.cpp:1984-2420 (fixed 1-trophy "Kyty" answers), 2422-3144 (UDS no-ops) / SS14: differs: O libs/libNet.cpp:2543-2555 PostEvent does not unlock | L | M: overlay is GPU/UI | later | trophies list/unlock correct for any title |
| 144 | KK37 (+KL20) | Guest TSC at 1.6 GHz (`--guest-tsc`): TSC reads and `sceKernelGetTscFrequency` scaled, loader rewrites guest RDTSC/RDTSCP | [KytyPS5 dfec14a] K:kernel/pthread.cpp:183-203; loader/guestInstructionPatcher.cpp (loader); `2f885e2` 2026-11-01 "kernel: add --guest-tsc to run the guest TSC at the PS5's 1.6 GHz" **+ KL20** [KytyPS5 dfec14a] 2f885e2 2026-11-01 "kernel: add --guest-tsc to run the guest TSC at the PS5's 1.6 GHz": src/loader/guestInstructionPatcher.cpp @ dfec14a:959-994, 1543-1610; src/kernel/pthread.cpp @ dfec14a:186-204; src/loader/runtimeLinker.cpp:1700-1703, 1846-1850 | GPL-2.0 (1.6 GHz claim uncited: TODO(verify)) + GPL-2.0-or-later (patcher, shadPS4 SPDX) / GPL-2.0 | differs: O:kernel/pthread.cpp:132-210, 4116-4121 host TSC (minus BC5 pause) / KL20: missing; needs KL21's patcher on Linux (ours: redZonePatcher Windows-only Xbyak, redZonePatcher.cpp:23-26) | L | H: patches guest code | later | Titles that hard-code 1.6 GHz instead of asking; brief's re-evaluated item |
| 145 | KL21 | Guest instruction patcher (replaces our redZonePatcher): native trampolines or traps for VRSQRTPS (deterministic estimate), EXTRQ/INSERTQ, RDPID, CLWB with `--amd-cpu`; cross-platform Xbyak | [KytyPS5 dfec14a] src/loader/guestInstructionPatcher.cpp/.h @ dfec14a (1815+73 lines); src/loader/runtimeLinker.cpp @ dfec14a:1694-1730, 1807-1876; x64InstructionEmulator.cpp:735-800; pre-4644c52 | GPL-2.0-or-later (shadPS4 SPDX) | differs: loader/redZonePatcher.cpp (1447 lines, red-zone part only, Windows) | L | H | later | Intel-host compatibility; no effect on the BC-250. Basis for KL20 |
| 146 | KK38 | `setenv` validates and does not touch the host environment | [KytyPS5 dfec14a] K:libs/libC.cpp:310-326; pre-4644c52 | GPL-2.0 | differs: O:libs/libC.cpp:334-352 calls host `setenv` (guest `getenv` is not HLE'd in either tree) | S | L | later | Host isolation (a guest `TZ` changes our host `localtime`) |
| 147 | KK39 | `read` with `nbytes > INT_MAX` returns EINVAL | [KytyPS5 dfec14a] K:kernel/fileSystem.cpp:648-650; pre-4644c52 | GPL-2.0 | differs: O:kernel/fileSystem.cpp:646-649 (> UINT_MAX EOPNOTSUPP; INT_MAX..UINT_MAX read) | S | L: TODO(verify) the console limit | later | Low |
| 148 | KK40 | libc `init_env` takes any `argc` (`Loader::EntryParams`) | [KytyPS5 dfec14a] K:libs/libC.cpp:260-284 | GPL-2.0 | differs: O:libs/libC.cpp:278-280 EXITs at `argc >= 3` | S | L | later | Host-built argv only; very low |
| 149 | SK25 | Missing lXT0m3P-vs4 sceKernelAioSubmitReadCommandsMultiple. sharpemu treats it as SubmitReadCommands (one id). Unverified here whether the Multiple variant returns one id per request. | [sharpemu 514d766] `Kernel/KernelFileExtendedExports.cs:547-549` | GPL-2.0+ | missing | S | M: id-array semantics unverified | later | verify id[] shape first |
| 150 | SK30 | getdirentries/getdents with a buffer < 512 bytes: ours EINVAL; sharpemu packs whole records into any buffer >= 12 bytes (Quake II). | [sharpemu 514d766] `Kernel/KernelMemoryCompatExports.cs:7192-7270`; 50198a6 2026-09-30 "[Kernel] Return packed directory entries for Quake II" | GPL-2.0+ | differs: `kernel/fileSystem.cpp:1495-1500` (512-block layout kept) | S | M: offset/basep semantics of our 512-byte block model | later | title-reported |
| 151 | SK31 | Ult mutex self-relock: ours recursive (OK); sharpemu PERMISSION 0x80810005. Console behaviour unverified. | [sharpemu 514d766] `Ult/UltExports.Sync.cs:240-262` | GPL-2.0+ | differs: `libs/libUlt.cpp:39-42, 534-550` | S | M | later | verify before changing |
| 152 | SK32 | Ult objects: ours memsets guessed sizes into guest-owned objects (runtime 4096 B, ulthread 512, pools 256/512, queue 512, mutex 256, semaphore 256); sharpemu writes none of them (and leaves sync opt params untouched "rather than risk zeroing past a stack-allocated block"). Real sizes unknown here. | [sharpemu 514d766] `Ult/UltExports.Sync.cs:121-124`; `Ult/UltExports.cs:139-150` | GPL-2.0+ | differs: `libs/libUlt.cpp:197, 245, 323, 379, 422, 522, 612` | S | M | later | possible overwrite of adjacent guest memory; the 4096 B one is the most suspect |
| 153 | SK33 | Relative guest paths (no leading "/"): sharpemu resolves them against /app0; ours ENOENT. Console cwd not verified here. | [sharpemu 514d766] `Kernel/KernelMemoryCompatExports.cs:5052-5057` | GPL-2.0+ | differs: `kernel/fileSystem.cpp:370-372` | S | M | later | verify cwd |
| 154 | SK34 | Equeue re-add of an existing (ident, filter) updates udata/deadline but not `flags` (sceKernelAddUserEventEdge after AddUserEvent keeps level mode); sharpemu replaces the registration incl. flags. | [sharpemu 514d766] `Kernel/KernelEventQueueCompatExports.cs:1150-1197` | GPL-2.0+ | differs: `kernel/eventQueue.cpp:221-226` | S | L | later | edge case |
| 155 | SK35 | sceKernelTriggerUserEvent: ours puts the argument in both `data` (0x10) and `udata` (0x18); sharpemu only udata, data 0. | [sharpemu 514d766] `Kernel/KernelEventQueueCompatExports.cs:1519-1562`; 816ec4a | GPL-2.0+ | differs: `kernel/eventQueue.cpp:261-266` | S | L | later | console value of `data` unverified |
| 156 | SK36 | Missing QyrxcdBrb0M sceKernelGetKqueueFromEqueue (sharpemu returns the equeue handle). | [sharpemu 514d766] `Kernel/KernelEventQueueCompatExports.cs:715-725` | GPL-2.0+ | missing | S | L | later | useless without kevent() |
| 157 | SK37 | clock_gettime(NULL): ours EFAULT; sharpemu EINVAL "to match Orbis runtime behavior" (no evidence given). | [sharpemu 514d766] `Kernel/KernelRuntimeCompatExports.cs` (65a4077 2026-07-11) | GPL-2.0+ | differs: `kernel/pthread.cpp:3969-3971` | S | L | later | unverified claim |
| 158 | SK38 | PTHREAD_MUTEX_ADAPTIVE_NP self-relock returns OK (idempotent) in sharpemu ("Gen5 runtime wrappers layer an adaptive lock over scePthreadMutexLock", UE boot); ours EDEADLK, as FreeBSD libthr's mutex_self_lock does. | [sharpemu 514d766] `Kernel/KernelPthreadCompatExports.cs` (90c72eb 2026-07-19 "Fixes a Mutex Issue Preventing Some UE Titles From Booting") | GPL-2.0+ | differs: `kernel/pthread.cpp:1383-1396` | S | H: hides real deadlocks | later | do not port without console evidence |
| 159 | KL14 | Symbol resolve checks every program exporting the lib+module, first that has the record wins (sets bind_self) | [KytyPS5 dfec14a] src/loader/runtimeLinker.cpp @ dfec14a:1388-1405; pre-4644c52 | GPL-2.0 | differs: loader/runtimeLinker.cpp:1898-1905 FindProgram (2999-3012) returns the first match only; the NID fallback (lambda 1860, used 1907-1911) usually finds it anyway, without bind_self | S | L | later | Corner case: two loaded programs exporting the same lib/module |
| 160 | KL15 | Fault report: guest thread name, 32 stack qwords; DebugCounters (EmulatedInstructions, GpuFaults, UnresolvedImportCalls) | [KytyPS5 dfec14a] src/loader/runtimeLinker.cpp @ dfec14a:658, 673, 682-716, 195; pre-4644c52 | GPL-2.0 | differs: loader/runtimeLinker.cpp:1003-1012 (16 qwords), 1070 numeric thread id; no counters | S | L | later | Diagnostics |
| 161 | KL19 | Configurable user: `--user-id` (default 1000, player n = id + n*0x100), `--user-name` (player 1), localized "Guest N" for others | [KytyPS5 dfec14a] src/common/emulatorConfig.h @ dfec14a:33-48; emulatorConfig.cpp:43-86; src/main.cpp:57-58, 341-350; src/libs/libUserService.cpp:65-73, 113-131; pre-4644c52 | GPL-2.0 | differs: libs/libUserService.cpp:28-29 fixed 1000..1003, 116-127 "Kyty-N" | S | M: ids feed save-data paths | later | Startup flags only |
| 162 | KL24 | param.json `attribute` -> ATTRIBUTE (default 0), `attribute3` -> ATTRIBUTE3 in the emulated param.sfo | [KytyPS5 dfec14a] src/loader/systemContent.cpp @ dfec14a:169-171; pre-4644c52 | GPL-2.0 | missing: loader/systemContent.cpp:166-173 maps no attribute keys | S | L | later | No consumer in our tree (KytyPS5 uses them for HDR permission and Trinity, videoOut.cpp:1856-1858); port with a consumer |
| 163 | KA20 | 8-channel speaker order: KytyPS5 swaps side/back for non-STD formats and drops the STD swap in SetVolume | [KytyPS5 dfec14a] audio.cpp:307-371 (SDL_8CH_MAP 334), 525-541; pre-4644c52 | GPL-2.0 | differs: audio.cpp:534-600 and 1176-1207 swap for STD formats, as shadPS4 does (refs/shadps4-emu_shadPS4 src/core/libraries/audio/audioout.cpp:52-68 @ 60c42b9) | S | M (two of three hosts disagree with KytyPS5); replug | later | verify on a 7.1 sink before porting either way |
| 164 | KA22 | sceAudioInOpen full PS5 rules: len 128 (HQ) or 128/256, freq 48000 (HQ) or 48000/16000; param 1 = S16 mono, 2 = S16 stereo, 0x10/0x11 = float mono, 0x12 = float stereo, else INVALID_PARAM | [KytyPS5 dfec14a] audio.cpp:1053-1072; pre-4644c52 | GPL-2.0 | differs: audio.cpp:1559-1569 maps param 0 -> S16 mono (as shadPS4 PS4 enum S16Mono = 0, audioin.h:21), other values -> stereo | S | M (mapping conflicts with shadPS4's PS4 enum; unverified for PS5); replug | later | verify the PS5 enum first |
| 165 | KA25 | AvPlayer aspect_ratio = sample aspect ratio only | [KytyPS5 dfec14a] avPlayer.cpp:1428-1430; pre-4644c52 | GPL-2.0 | differs: avPlayer.cpp:1383-1392 reports display aspect (w/h*SAR) | S | M (which one the API means is unverified) | later | verify before porting |
| 166 | KA26 | AvPlayer StartWorkers/StopWorkers/FailPipeline under the source mutex | [KytyPS5 dfec14a] avPlayer.cpp:1212-1262; pre-4644c52 | GPL-2.0 | differs: avPlayer.cpp:1171-1215 (flags written unlocked) | S | L | later | data race |
| 167 | KA28 | PngEnc validation: this_size checked, image address and pitch 4-aligned, popcount(filter_type) <= max_filter_number, pitch*height <= image_mem_size | [KytyPS5 dfec14a] libPngEnc.cpp:128-148, 188-262; pre-4644c52 | GPL-2.0 | differs: libPngEnc.cpp:88-99, 283-309 (exp 0329, AnyPS5-based) | S | L (which side matches the console is unverified) | later | low |
| 168 | KA38 | Ngs2VoiceQueryInfo (9eic4AmjGVI, query 0x4001 setup channels) and Ngs2VoiceGetPortInfo (WCayTgob7-o, matrix/volume/dest) | [KytyPS5 dfec14a] ngs2.cpp:2857-2899; 9bf311c and 2aa0d58 2026-10-30 | GPL-2.0 | differs: libNgs2.cpp stubs (return OK, no writes) | S | L (needs KA37 voice state; KytyPS5 aborts on other query ids) | later | after KA37 |
| 169 | KA50 | Warn once when a title asks for VP9 and FFmpeg has no VP9 decoder (AvPlayer and Videodec2) | [KytyPS5 dfec14a] avPlayer.cpp:396-405; videoDec2Decoder.cpp:97-101; pre-4644c52 | GPL-2.0 | missing (log only) | S | L | later | diagnosability |
| 170 | KA51 | libavutil >= 61 build fix: avpriv_vga16_font_get() | [KytyPS5 dfec14a] libFont.cpp:43-48, 936-940; pre-4644c52 | GPL-2.0 | missing (only matters with FFmpeg 8) | S | L | later | build compat |
| 171 | SS08 | sceAcm_ConvReverb_SharedInput zeroes its output channel buffers (convolution itself not done) | [sharpemu 514d766] Acm/AcmExports.cs @514d766 ConvReverbSharedInput (d113a37 2026-10-15; stated: stale output must not be played) | GPL-2.0+ | differs: O libs/audio.cpp:1724-1736 (advances batch only) | S | M: out-descriptor layout {u32 samples, u32 channels, .., u64 buffers@+0x10} is sharp's reading, unverified, and writes guest memory; replug check | later | stale/garbage reverb output becomes silence |
| 172 | SS15 | sceAjmModuleUnregister/sceAjmFinalize validate the context and drop registrations | [sharpemu 514d766] Audio/AjmExports.cs (4b8d455 2026-08-09) | GPL-2.0+ | differs: O libs/ajm.cpp:779-783, 813-817 no-ops | S | L; replug check | later | error-path accuracy |
| 173 | SS16 | sceFontGetHorizontalLayout/VerticalLayout take the layout pointer from rdx when rsi is 0 | [sharpemu 514d766] Font/FontExports.cs (8e1c625 2026-10-01; stated: Astro Bot assert in FontSystem.cpp) | GPL-2.0+ | differs: O libs/libFont.cpp:1408-1413 returns -1 (O already scales metrics, :1416-1429) | S | M: rdx may be garbage when a caller passes 0 on purpose | later | avoids a title assert |
| 174 | SS17 | sceAudioPropagationSystemQueryMemory: report 1 MiB CPU, 0 GPU; null out -> 0x8A700003 | [sharpemu 514d766] Audio/AudioPropagationExports.cs:20-52 (ddaf7ff) | GPL-2.0+ | differs: O libs/libAudio.cpp:36-48 reports 0 CPU bytes (descriptor already untouched, as sharp's fix wants) | S | L; replug check | later | a title allocating 0 bytes may assert |
| 175 | SS21 | AvPlayer: file URIs resolved inside app0, case-insensitive fallback, traversal rejected | [sharpemu 514d766] AvPlayer/AvPlayerExports.cs (22bbb4e 2026-07-17) | GPL-2.0+ | partly: O libs/avPlayer.cpp:646-690 handles file:// and relative paths; case-insensitive fallback not verified | S | L | later | Linux host is case-sensitive |
| 176 | SS49 | libSceVideodec v1: CreateDecoder writes a handle; Decode/Flush OK without picture; Delete | [sharpemu 514d766] Codec/CodecExports.cs:86-118 | GPL-2.0+ | missing | S | L | later | handle out-param |
| 177 | SS54 | libfmod uPLTdl3psGk (FMOD System::setOutput) override poking fmod object offsets 0x08/0x116D0/0x116D4 | [sharpemu 514d766] Audio/FmodCompatExports.cs:14-45 | GPL-2.0+ | missing | S | H: patches a title-bundled library's internals; one fmod build | later | hack |
| 178 | KS46 | Psml NID meaning differs: GHna9-DvnUk K GetMipmapBias vs O PsmlGetProgress; GJY0MvuTcs8 K ValidateContext vs O PsmlRequestCapture | [KytyPS5 dfec14a] K libs/libPsml.cpp:336-353,646-649 | GPL-2.0 | differs: O libs/libPsml.cpp:345-346 | S | L | later | verify which is right before Pro mode work |
| 179 | KS52 | sceHttpCreateRequest2 (rGNm+FjIXKk) | [KytyPS5 dfec14a] K libs/network.cpp:3504-3521 | GPL-2.0 | missing | S | M: KytyPS5 passes the path where a URL is expected; needs host+path join | later |  |
| 180 | KS53 | PlayGoOpen NOT_SUPPORT_PLAYGO when no chunk table; playgo_hack 1000 chunks | [KytyPS5 dfec14a] K libs/libPlayGo.cpp:27,57,100-103,124-126; pre-4644c52 | GPL-2.0 | differs: O libs/libPlayGo.cpp:75-83 (assumes 1 chunk, deliberate) | S | M | later |  |
| 181 | KS54 | Login/Signin dialog: selected user from Config, Signin reserved/user_id checks (INVALID_USER_ID 0x81350007) | [KytyPS5 dfec14a] K libs/dialog.cpp:147-192,285,323-341; pre-4644c52 | GPL-2.0 | differs: O libs/dialog.cpp:51,77-122,250-262 (user 1000) | S | L | later | needs a user model |
| 182 | KS56 (+SS46) | scePadGetExtControllerInformation (hGbf2QTBmqc): handle check, no write | [KytyPS5 dfec14a] K libs/libPad.cpp:137-146,180 **+ SS46** [sharpemu 514d766] Pad/PadExports.cs:296-325 | GPL-2.0 + GPL-2.0+ | missing | S | L | later | error code only |
| 183 | KS57 | NpEntitlementAccessPft eDXKe9FndlE: *state=2 | [KytyPS5 dfec14a] K libs/libNpEntitlementAccess.cpp:524-541; 99044c7 2026-10-25 "libs: provide NpEntitlementAccessPft state query used by FC27 (#1897)" | GPL-2.0 | missing | S | M: meaning unknown ("for the FC27 investigation") | later | weak evidence |
| 184 | KS58 | DirNameSearch of another title_id searches that title; only dirs with param metadata listed | [KytyPS5 dfec14a] K libs/libSaveData.cpp:615-637 | GPL-2.0 | differs: O libs/libSaveData.cpp:538-556 (other title -> no match, AnyPS5) | S | L | later |  |
| 185 | KS59 | IME text editing refactored into imeCommon (TextEditEngine shared by Ime and ImeDialog) | [KytyPS5 dfec14a] K libs/imeCommon.cpp/.h (418 lines); pre-4644c52 | GPL-2.0 | differs: O libs/ime.cpp:175-312, imeDialog.cpp:158-455 (inline); validation lines identical (O ime.cpp:352-735 vs K 235-615) | S | L | later | verify only; no behaviour difference found in the hunks read |
| 186 | KS60 | GetEventResult stops logging empty polls | [KytyPS5 dfec14a] K libs/libSaveData.cpp:1184-1188; 52c80be 2026-10-25 "savedata: stop logging empty sceSaveDataGetEventResult polls" | GPL-2.0 | differs: O libs/libSaveData.cpp:1071-1084 | S | L | later | log only |
| 187 | KS61 | M3wFXbYQtAA named NpUnregisterStateCallback (K) vs NpUnregisterStateCallbackA (O) | [KytyPS5 dfec14a] K libs/libNet.cpp:1676 | GPL-2.0 | differs: O libs/libNet.cpp:1458 | S | L | later | one name is wrong; not verified |
| 188 | SS11 | Get/SetSaveDataMemory2 and Sync before Setup -> MEMORY_NOT_READY 0x809F0012 | [sharpemu 514d766] SaveData/SaveDataExports.cs:1576-1699 (488b285); shadPS4 :1652-1655 | GPL-2.0+ | differs: O libs/libSaveData.cpp:771-848 auto-loads and succeeds | S | M: a title relying on our lenient path would now see an error | later | console-accurate error |
| 189 | SS12 | MsgDialog state guards return SCE_COMMON_DIALOG errors (NOT_INITIALIZED 0x80B80003, NOT_FINISHED 0x80B80005, BUSY 0x80B80007, NOT_RUNNING 0x80B8000B, ARG_NULL 0x80B8000D) | [sharpemu 514d766] CommonDialog/MsgDialogExports.cs (de13735 2026-07-15) | GPL-2.0+ | differs: O libs/dialog.cpp:~549-640 returns OK in those states | S | M: stricter errors | later | correctness of error paths |
| 190 | SS42 | Rtc calendar exports: CompareTick, GetDosTime, SetDosTime, TickAddMonths, TickAddYears | [sharpemu 514d766] clean-room from the public FAT date/time format and calendar rules; sharp's code is provenance-flagged (SS64); shadPS4 rtc.cpp:55-67,578-596,913-930,1070-1180 has defects (CompareTick returns 1/0, GetDosTime ORs into an uncleared out, TickAddMonths converts the destination tick) | own | missing | S | L | later | out-params; not "well sourced" from either repo |
| 191 | SS45 | sceSaveDataGetSaveDataCount, GetMountedSaveDataCount, GetAllSize, IsMounted, Delete5 | [sharpemu 514d766] SaveData/SaveDataExports.cs:267-283, 325-358, 508-533, 566-615 | GPL-2.0+ | missing | S | M: out-param positions are sharp-only (shadPS4 declares them without params); sharp Delete reads dirName at +0x08, OURS/shadPS4 at +0x10 (libSaveData.cpp:212-220) | later | unverified ABI |
| 192 | SS47 | sceNetGetMemoryPoolStats, sceSslGetMemoryPoolStats, sceHttp2GetMemoryPoolStats | [sharpemu 514d766] Network/NetExports.cs:1093-1110, SslExports.cs:58-79, Http2Exports.cs:147-169 | GPL-2.0+ | missing | S | L | later | out-params |
| 193 | SS53 | scePsmlMfsrGetDispatchMfsrPacket1000/1100 (s2psNHUIdjk, 94iBp3KvIuI) clear the packet buffer | [sharpemu 514d766] Psml/PsmlExports.cs:284-322 (96fde57) | GPL-2.0+ | missing; the 900 variant (RUNLFro+qok) is registered as Psml::PsmlDispatch (O libs/libPsml.cpp:344), so 1000/1100 could alias it | S | M: GPU packet | later | GPU-adjacent, needs a GPU check |
| 194 | KK31 | pthread keys: lock-free thread-local value array with key generations; destructors repeated until none runs | [KytyPS5 dfec14a] K:kernel/pthread.cpp:597-610, 1579-1609, 3931-3997; pre-4644c52 | GPL-2.0 | differs: O:kernel/pthread.cpp:671-698, 1658-1770, 4208-4264 (global mutex, per-key vector scanned by thread id on every get/set; one destructor pass) | M | M | later | Speed of `pthread_getspecific` (hot in engines); POSIX destructor iterations. KytyPS5 loop is unbounded (cap at 4) |
| 195 | KK32 | Fiber thread context through a native TLS key instead of C++ `thread_local` ("native lookup must stay fresh when a fiber resumes on another host thread") | [KytyPS5 dfec14a] K:libs/libKernel.cpp:2358-2425, 2612-2730; pre-4644c52 | GPL-2.0 | differs: O:libs/libKernel.cpp:2706-2713, 2840-3145 (`thread_local` + owner maps, BC5 naked-function fix kept) | M | M | later | Guards against a compiler-cached TLS address after a cross-thread resume; not observed in ours |
| 196 | KK33 | Per-thread alternate signal stack and `SA_ONSTACK` for the host fault handler ("keep fault handling off guest stacks, which GPU tracking can make read-only") | [KytyPS5 dfec14a] K:common/hostException.cpp:41-80, 325; K:kernel/pthread.cpp:1030-1035, 3228-3230; pre-4644c52 | GPL-2.0 | differs: O:common/hostException.cpp:437-450 (no `SA_ONSTACK`, comment "Fault resolution needs the normal thread stack") | M | M: handler depth on a 64 KiB stack | later | A fault on a write-protected stack page kills the process |
| 197 | KK34 | Directories as a byte stream: dirents packed at open, `read()` returns them, `lseek` on directories (EINVAL/EOVERFLOW checks), `stat`/`fstat` size = packed size, `getdirentries` under the file mutex rejecting unaligned or past-EOF offsets | [KytyPS5 dfec14a] K:kernel/fileSystem.cpp:129-173, 519-521, 648-657, 1057-1119, 1152-1156, 1223-1226, 1432-1469; test KernelFileSystemTests.cpp:1341-1442 @dfec14a; pre-4644c52 | GPL-2.0 | differs: O:kernel/fileSystem.cpp:640-642 (read EISDIR), 893-895 (lseek EISDIR), 972/1050 (size 0), 1478-1600 (repacks per call, no lock, may copy partial records) | M | M: TODO(verify) the console's `read()` on a directory | later | Rewind/seekdir of a directory stream fails; stat size 0 |
| 198 | KL17 | Add-on content: `--addcont-dir` scan of sce_sys/param.json + `--addcont LABEL[=DIR]`; AddcontMount mounts /addcontN, BUSY on duplicate label (97bef29), NOT_FOUND, MOUNT_FULL (64), PARAMETER for service_label != 0, creates /download0/pdlc; Unmount -> NOT_MOUNTED if unknown | [KytyPS5 dfec14a] src/libs/libAppContent.cpp @ dfec14a:35-47, 198-251, 266-279; src/loader/additionalContent.cpp:1-47; src/common/additionalContent.cpp:1-131; src/main.cpp:315-328; src/emulator.cpp:187. 66e21a6 2026-10-24 "addcont: add user add-ons with --addcont and a launcher list"; 97bef29 2026-10-29 "appcontent: reject duplicate mounts without transferring ownership" | GPL-2.0 | differs: libs/libAppContent.cpp:165-199 (Mount always DRM_NO_ENTITLEMENT, Unmount OK unless empty) | M | L: off without flags | later | DLC support; the NpEntitlementAccess side (10 k-only NIDs) belongs to another part |
| 199 | KL18 | sceSystemServiceGetStatus reports is_system_ui_overlaid / is_in_background_execution from the system-dialog state | [KytyPS5 dfec14a] src/libs/libSystemService.cpp @ dfec14a:184-201 (191-194); needs KytyPS5 libs/dialog.h; pre-4644c52 | GPL-2.0 | differs: libs/libSystemService.cpp:190-204 (always false) | M | L | later | Titles pause/hide UI while a system dialog shows; needs a dialog-visibility source in ours |
| 200 | KL22 | GoldHEN-style cheat JSON (`id/version/process/mods`), anchor-byte module matching, code caves, deferred apply when the matching module loads | [KytyPS5 dfec14a] src/loader/gamePatch.cpp/.h @ dfec14a; src/loader/runtimeLinker.cpp:1112-1115, 1275-1279, 1309; pre-4644c52 | GPL-2.0 | differs: loader/gamePatch.cpp:92-322 (own plan format, main program only, plus the BC5 job-arena fix) | M | L | later | User feature |
| 201 | KL23 | sceSystemServiceHideSplashScreen hides KytyPS5's boot splash overlay | [KytyPS5 dfec14a] src/libs/libSystemService.cpp @ dfec14a:97-101; src/graphics/presentation/systemOverlay.cpp; pre-4644c52 | GPL-2.0 | differs: libs/libSystemService.cpp:98-102 (OK, no splash exists) | M | L | later | Presentation side; we have no splash to hide |
| 202 | KA19 | AudioOut2 per-context port tables: max_ports <= 32 channel ports, max_object_ports <= 512, guarantee <= max_object -> else INVALID_PARAM; PORT_FULL per partition; ContextResetParam defaults 8/0/0/1/256 | [KytyPS5 dfec14a] libAudio2.cpp:174-177, 196-207, 373-384, 486-503, 523-571, 717-731; 2efd314 2026-10-27 "audio: support 512 object ports per AudioOut2 context" | GPL-2.0 | differs: libAudio2.cpp:440-454 (defaults 256/256/0/4/512/1), 471-508 (no validation), one global 256-port table (234-235) | M | M (our ResetParam defaults fail KytyPS5's validation; the commit does not say where the new defaults come from); replug | later | per-context limits, PORT_FULL |
| 203 | KA21 | AudioOut pacing: sample-exact OutputClock (remainder carried), 40 ms target latency, 200 ms stall clears the stream, primed/unprimed queue | [KytyPS5 dfec14a] audio.cpp:36-57, 373-429, 547-620; pre-4644c52 | GPL-2.0 | differs: audio.cpp:645-1019, 1209-1298 (BC5 pacing of exps 0174-0188 on SDL2/PipeWire) | M | H (box-tuned pacing); replug | later | only if our pacing shows drift again |
| 204 | KA23 | AvPlayer state machine Ready/Playing/Stopped: Pause/Resume return OPERATION_FAILED unless playing; STATE_STOP event on Stop only when playing; IsActive true while Ready | [KytyPS5 dfec14a] avPlayer.cpp:876-920, 1032-1037, 852-873; pre-4644c52 | GPL-2.0 | differs: avPlayer.cpp:836-882 (void Pause; `stopped` flag; KytyPlus natural-EOF STATE_STOP, 1687-1719) | M | M (CB4 boot-movie fix in ours) | later | API return codes |
| 205 | KA24 | AvPlayer looping: keep the original timestamp with a separate loop offset, raise LOOPING_BACK when the first looped frame is delivered, audio-clocked video via steady_clock from the first audio frame | [KytyPS5 dfec14a] avPlayer.cpp:1016-1019, 1022-1043, 1414, 975; pre-4644c52 | GPL-2.0 | differs: avPlayer.cpp:936-991, 1246, 1369 (warning at demux time; offset added to time_stamp; sync to last audio ts) | M | M | later | looped movie timing |
| 206 | KA27 | libFont: em-based scale with separate horizontal/vertical scale; glyph images sized to the glyph (vector, up to 4096 px) | [KytyPS5 dfec14a] libFont.cpp:83-84, 213, 234, 807-861, 931-950, 1402; pre-4644c52 | GPL-2.0 | differs: libFont.cpp:798-881 (pixel-height scale clamped 8-128, fixed 128x128 image arrays, FONT_BITMAP_MAX_DIM 75) | M | M (text size/metrics change in every libFont title) | later | large text clipped at 128 px in ours |
| 207 | KA39 | AudioOut2 GAIN attribute: per-channel finite gains >= 0 (value_size = channels*4), applied in the AudioOut mix | [KytyPS5 dfec14a] libAudio2.cpp:851-864, 458-460; audio_internal.h:24; audio.cpp:307-371 (gains); pre-4644c52 | GPL-2.0 | missing (attribute ignored) | M | M; replug | later | per-port volume |
| 208 | KA40 | AudioOut2 object ports (type 0x100, mono 48 kHz): mixed centred into a per-context stereo stream; AMBISONICS attribute (W, first-order L/R cardioids); attributes locked until Advance | [KytyPS5 dfec14a] libAudio2.cpp:407-435, 437-470, 523-541, 704-709, 865-881, 615-626; pre-4644c52 + 2efd314 | GPL-2.0 | missing: object ports get no device (libAudio2.cpp:756-770), their PCM is dropped | M | M; replug | later | object audio silent in ours |
| 209 | KA41 | sceAudiodec M4AAC decodes through the AJM AAC decoder (AudiodecParamM4aacEx non-delay output, result codes -4/-5, API_FAIL) | [KytyPS5 dfec14a] libAudio.cpp:635, 666-668, 734-740, 757, 898-901, 981-1002, 1052-1074, 1099-1105; ajm/decoder.h (shared base); pre-4644c52 | GPL-2.0 | differs: libAudio.cpp:1005-1037 returns zeroed PCM for every codec | M | M; replug | later | Audiodec AAC titles silent |
| 210 | KA42 | AJM Opus resampler: INSTANCE_FLAG_RESAMPLE, CONTROL_RESAMPLE/RESAMPLE_EX sideband, linear-interpolation ratio 0-4 with per-sample change, resample info sideband | [KytyPS5 dfec14a] ajm/resampler.h:1-182; ajm.cpp:426-431, 529-557, 950-985, 1000; c528324 2026-10-28 "audio: let the AJM Opus decoder write part of a packet" | GPL-2.0 | differs: ajm.cpp:547-552, 1120, 1132, 1151 report ratio 1.0 and ignore the parameters | M | M; replug | later | pitch/speed-changed voices |
| 211 | KA43 | ATRAC9 discrete multichannel config (0x30): up to 64 mono streams, per-channel superframes interleaved | [KytyPS5 dfec14a] ajm/atrac9_decoder.h:24-81, 326-371, 381-435; pre-4644c52 | GPL-2.0 | missing: ajm/atrac9_decoder.h:289-336 rejects the config | M | M (needs a DMC test vector, none without Sony data); replug | later | multichannel AT9 |
| 212 | KA44 | AudioIn real capture through SDL (configured device, async HQ reads of up to 384 frames, device-loss fallback to silence) | [KytyPS5 dfec14a] audio.cpp:622-707, 743-822; pre-4644c52 | GPL-2.0 | missing (silence only) | M | M (SDL3 code; ours is SDL2); replug | later | voice chat |
| 213 | KA45 | JpegDec (uNAUmANZMEw QueryMemorySize, JPh3Zgg0Zwc Create, 1kzQRoWEgSA Decode, Hwh11+m5KoI Delete, LSinoSQH790 ParseHeader) on stb_image | [KytyPS5 dfec14a] libJpegDec.cpp:1-402; ba0e93d 2026-10-23 | GPL-2.0 | missing | M | L | later | CPU-testable (KytyPS5 tests/JpegDecTests.cpp) but 400 lines |
| 214 | KA46 | Vdecsw library (13 NIDs: +L5ArV1tPGA CreateDecoder, 0moTubWCsTM, 5Y6nZqIZvBg, A+2M7EivuOU, aqMiF0AgUYI, ecUtPX+dBYk, fX-zOOefbbs, hIgrg5h4V6s, ihNT-uuEAr4, kMBw37oH8nI, l4sQYy5wPkc, rgtMCOpyBSc, veb-YBrOqo0) over the FFmpeg H.264 decoder | [KytyPS5 dfec14a] libVdecsw.cpp:1-459; videoDec2Decoder.h:76-152; pre-4644c52 | GPL-2.0 | missing | M | L (CPU only; the "compute queue" is bookkeeping) | later | needs KA47 |
| 215 | KA47 | Videodec2 decoder: pending-frame queue (max_pending_frames >= 2), Submit/Receive/Finalize split, InputFull/NoFrame results, last_frame flag, picture info captured at receive | [KytyPS5 dfec14a] videoDec2Decoder.cpp:124-255, 370, 407-467; videoDec2Decoder.h:17-43, 76-152; pre-4644c52 | GPL-2.0 | differs: videoDec2Decoder.cpp:116-237 (one-frame pending, AccessUnit on a full decoder) | M | M (Videodec2 movies) | later | base of KA46 |
| 216 | KA48 | libFont fallback: ship Noto Sans Regular/Bold/Italic/BoldItalic (OFL) in assets/fonts next to the binary | [KytyPS5 dfec14a] libFont.cpp:701-730; CMake; 3583331 2026-10-26 "libFont: ship Noto Sans as the fallback font" | GPL-2.0 code; fonts SIL OFL 1.1 | differs: libFont.cpp:660-722 looks for Tracy's Roboto relative to the source tree or cwd (absent in installed builds: every glyph '?') | M | L (packaging change; FetchContent downloads at configure time) | later | system font sets on installed builds |
| 217 | SS13 | Videodec2: picture-info size prefix and adjacent fields kept, EOF handled, teardown joins workers | [sharpemu 514d766] Codec/Videodec2Decoder.cs, Videodec2Exports.cs (3172d7c 2026-10-15) | GPL-2.0+ | not compared in detail: O libs/libVideoDec2.cpp:460-507 + videoDec2Decoder.h | M | M | later | movie decode robustness; unverified whether OURS has the defects |
| 218 | SS19 | AudioOut2 producer usleep shortened while the device runs short | [sharpemu 514d766] Audio/AudioOut2Exports.cs (ef73fe4 2026-10-14) | GPL-2.0+ | differs by design: O libs/libAudio2.cpp:599-665 paces on the device queue | M | H: pacing; replug check | later | anti-crackle idea only |
| 219 | SS55 | Font text-string state (sceFontText*, 11506fc Font part) | [sharpemu 514d766] Font/FontExports.Text.cs (11506fc 2026-10-31) | GPL-2.0+ | not compared (NIDs registered in OURS) | M | L | later | unverified |
| 220 | KS41 | Guest users' saves under [users]/<id>; per-user memory dir | [KytyPS5 dfec14a] K libs/libSaveData.cpp:313-336; pre-4644c52 | GPL-2.0 | differs: O libs/libSaveData.cpp:629-630 (one dir per title) | M | M: needs a user model (Config::IsGuestUserId) | later | local multiplayer saves |
| 221 | KS42 | PSN emulation option (signed-in simulation: NpGetState, NpId "Kyty", account id, reachability, NpAuth SERVICE_DOWN) | [KytyPS5 dfec14a] K libs/network.cpp:4086-4100 and callers; 15452a5 2026-10-29 | GPL-2.0 | differs: O always signed out (network.cpp:4261-4275, libNet.cpp:1410-1444) | M | M: titles go online paths | later | optional mode |
| 222 | KS43 | NpEntitlementAccess request/poll family: RequestServiceEntitlementInfoList, RequestUnifiedEntitlementInfo, RequestConsumeUnifiedEntitlement, Poll* (3 k-only), param validation, kind checks | [KytyPS5 dfec14a] K libs/libNpEntitlementAccess.cpp:111-171,234-422; pre-4644c52 | GPL-2.0 | differs/missing: O libs/libNet.cpp:1651-1714 (only the unified list) | M | L | later | completes the offline entitlement API |
| 223 | KS44 | Ces CP932 (Shift-JIS) to UTF-8: ProfileInitSJis1997Cp932, MbcsUcsContextInit, MbcsStrGetUtf8Len, MbcsStrToUtf8Str | [KytyPS5 dfec14a] K libs/libCes.cpp:160-385; pre-4644c52 | GPL-2.0 | differs: O libs/libNet.cpp:3305-3318 (CesStub returns 0 = NULL profile), 2 NIDs missing | M | L: needs iconv CP932 on Linux (SDL_iconv) | later | Japanese text conversion |
| 224 | KS50 | sceVideoOutSetFlipMaster (WkYtyOg30do) | [KytyPS5 dfec14a] K graphics/presentation/videoOut.cpp:794-830,1330-1333; pre-4644c52 | GPL-2.0 | missing | M | M: presenter | later | multi-port flip sync |
| 225 | KS51 | NpEntitlementAccess add-on list from installed add-ons (--addcont), package_type/download_status from the entry | [KytyPS5 dfec14a] K libs/libNpEntitlementAccess.cpp:155-171,424-473, loader/additionalContent.*; 66e21a6 2026-10-24 "addcont: add user add-ons with --addcont and a launcher list" | GPL-2.0 | differs: O libs/libNet.cpp:1570-1640 (fixed GTA V list only) | M | L | later | DLC; needs KytyPS5 loader/additionalContent (not in this scope) |
| 226 | KS55 | Controller host features: gyro emulation from the right stick, keyboard player cycling, device timestamps for motion | [KytyPS5 dfec14a] K libs/controller.cpp:656-830,1083-1134; pre-4644c52 | GPL-2.0 | differs: O libs/controller.cpp (own model) | M | M | later | UX |
| 227 | SS09 | sceSaveDataSaveIcon/LoadIcon persist the icon with the slot; LoadIcon NOT_FOUND when none | [sharpemu 514d766] SaveData/SaveDataExports.cs:431-505 | GPL-2.0+ | differs: O libs/libSaveData.cpp:1195-1206 (SaveIcon no-op), 1030-1045 (LoadIcon data_size 0, OK) | M | L: choose sidecar location (OURS keeps sidecars next to the dir, :320-343) | later | data loss: icon never kept; slot lists show none |
| 228 | SS20 | PlayGo installed chunk set derived from pak files on disk | [sharpemu 514d766] PlayGo/PlayGoExports.cs (3ebfc56 2026-07-19) | GPL-2.0+ | differs: O libs/libPlayGo.cpp:73-88 (all chunks of the table local) | M | L | later | partial installs only |
| 229 | SS43 | SaveData memory v1: sceSaveDataSetupSaveDataMemory (v7AAAMo0Lz4), Get (7Bt5pBC-Aco), Set (h3YURzXGSVQ) | [sharpemu 514d766] sharp aliases them to v2 (SaveDataExports.cs:617-624) - wrong: shadPS4 savedata.h:129-172 gives (userId, size, param*) and (userId, buf, size, offset) | GPL-2.0+ | missing | M | M | later | port v1 on the shadPS4 signatures over our memory store, not sharp's alias |
| 230 | SS44 | sceSaveDataMount (32HQAQdwM2o), Mount2 (0z45PIH+SNI), Mount5 (xz0YMi6BfNk) | [sharpemu 514d766] sharp routes all to the Mount3 layout (SaveDataExports.cs:254-261); shadPS4 OrbisSaveDataMount2 (savedata.cpp:206-213) has no systemBlocks, so mountMode is at +0x18 not +0x20 | GPL-2.0+ | missing | M | M: layout errors corrupt mount mode | later | Mount5 layout unknown |
| 231 | SS48 | Http2 CreateCookieBox (positive id), SetCookieBox, SetMinSslVersion; Http sceHttpsLoadCert; Ssl sceSslClose; Rudp PollCreate (positive id)/PollWait | [sharpemu 514d766] Network/Http2Exports.cs:227-330, HttpExports.cs:161-175, SslExports.cs:82-90, RudpExports.cs:24-100 | GPL-2.0+ | missing | M | L | later | ids/err codes |
| 232 | SS52 | sceVideoOutSetBufferAttribute (i6-sR91Wt-4), sceVideoOutRegisterBuffers (w3BY+tAEiQY) (PS4 v1 forms) | [sharpemu 514d766] VideoOut/VideoOutExports.cs:1319-1340, 1444-1500 | GPL-2.0+ | missing; v2 forms exist (O libs/libVideoOut.cpp:17-18) | M | M: presenter buffer registration | later | GPU-adjacent, not CPU-testable |
| 233 | KK41 | ZArchive (`.zar`) read-only mounts (EROFS on writes) | [KytyPS5 dfec14a] K:common/archive.h, kernel/fileSystem.cpp:47, 268, 359-362, 489-493; `cb8042c` 2026-10-22 (launcher) and pre-4644c52 | GPL-2.0 (3rd-party ZArchive dependency licence not checked) | missing | L | M | later | Host feature; BC5 mounts through bc5-mount FUSE, no guest-visible value |
| 234 | SK39 | libc HLE fallbacks (55 NIDs): stdio (xeYO4u7uyJ0 fopen, uodLYyUip20 fclose, lbB+UlZqVG0 fread, MpxhMh8QFro fwrite, rQFVBXp-Cxg fseek, Qazy8LmXTvw ftell, SHlt7EhOtqA fgetpos, 7PkSz+qnTto fsetpos, QMFyLoqNxIg setvbuf, KdP-nULpuGw fgets, 8Q60JLJ6Rv4 getc, AEuF3F2f8TA fgetc, LxcEU+ICu8U feof, AHxyhN96dy4 ferror, 3QIPIh-GDjw rewind, aZK8lNei-Qw fputc, QrZZdJ8XsX0 fputs, fffwELXNVFA fprintf, pDBDcY6uLSA vfprintf, gkWgn0p1AfU freopen, vZkmJmvqueY _Lockfilelock, 0x7rx8TKy2Y _Unlockfilelock, sUP1hBaouOw _Getpctype, EMutwaQ34Jo perror), allocator (gQX+4GDQjpM malloc, tIhsqj0qsFE free, 2X5agFjKxMc calloc, Y7aJ1uydPMo realloc, Ujf3KzMvRmI memalign, 2Btkg8k24Zg aligned_alloc, cVSk9y8URbc posix_memalign), string/format (5jNubw4vlAA strnlen, 8u8lPzUEq+U memchr, AV6ipCNa4Rw strcasecmp, kHg45qPC6f0 strncat, tcVi5SivF7Q sprintf, jbz9I9vkqkk vsprintf, Q2V+iqvjgC0 vsnprintf), wide (0nV21JjYCH8 wcsncpy, 6f5f-qx4ucA wcscpy_s, E8wCoUEbfzk wcsncmp, Ezzq78ZgHPs wcschr, FM5NPnLqBc8 wcscpy, Im55VJ-Bekc swprintf_s, LHMrG7e8G78 "wcsmisc" (bound to Wcslen), Slmz4HMpNGs wcsncpy_s, WkkeywLJcgU wcslen, fV2xHER+bKE wcscoll, nJz16JE1txM swprintf, oDoV9tyHTbA vswprintf_s, pNtJdE3x49E wcscmp, u0XOsuOmOzc vswprintf), C++ ABI (3GPpjQdAMTw __cxa_guard_acquire, 9rAeANT2tyE __cxa_guard_release, 2emaaluWzUw __cxa_guard_abort). | [sharpemu 514d766] `LibcStdioExports.cs`, `Kernel/KernelMemoryCompatExports.cs` (lines in s-only.tsv), `CxxAbiExports.cs:25-200`; e17fb6f (HLE memset preferred: int 45h path in LLE memset) | GPL-2.0+ | served by the title's libc.prx (method note b); memset/memcpy already HLE `libs/libC.cpp:913-914` | L | M: HLE FILE layout must never mix with LLE FILE (`DirectExecutionBackend.cs:1826-1832`) | later | only for a title without libc.prx |
| 235 | KL25 | PS5 Pro (Trinity) mode: ATTRIBUTE3 bit 22 + `--trinity` -> SystemContentIsTrinityMode used by kernel/Psml/Agc | [KytyPS5 dfec14a] 651ef73 2026-10-29 "graphics: add experimental Pro mode and linear PSSR": src/loader/systemContent.cpp @ dfec14a:608-615, 639-641 | GPL-2.0 | missing (KernelIsTrinityMode returns 0, libs/libKernel.cpp:1408) | L | M | later | GPU-coupled; loader part is 10 lines |
| 236 | KA49 (+KS48) | DualSense haptics/speaker stream for AudioOut pad/vibration ports including Bluetooth HID (Controller::DualSenseHaptics) | [KytyPS5 dfec14a] audio.cpp:465-471, 557-600 + dualSenseHaptics.cpp/dualSenseBluetooth.cpp; pre-4644c52 **+ KS48** [KytyPS5 dfec14a] K libs/dualSenseHaptics.cpp (436), dualSenseBluetooth.cpp (467); pre-4644c52 | GPL-2.0 | differs: ours routes pad ports to the controller's USB audio device (audio.cpp:342-533, exp 0372) with a rumble fallback; no Bluetooth haptics / KS48: differs: O libs/dualsense.cpp:439 ("BT framing ... not wired through"), audio.cpp pad ports | L | H (exp 0372 route); replug | later | overlaps the controller scope; listed for completeness |
| 237 | KS45 | Psml PSSR dispatch packets and Psml_mfsr2 real implementation (contexts, requirements, dispatch) | [KytyPS5 dfec14a] K libs/libPsml.cpp:120-653; 02b17af 2026-11-02, 651ef73 2026-10-29 | GPL-2.0 | differs: O libs/libPsml.cpp (bookkeeping only) | L | H: GPU | later | GPU agent's scope; only with a Pro mode |
| 238 | KS47 | Error and Signin dialogs as a host overlay (SystemDialog snapshot, visibility callback, HostClose) | [KytyPS5 dfec14a] K libs/dialog.cpp:17-91,303-369,748-825, dialog.h:70-92; pre-4644c52 | GPL-2.0 | differs: O libs/dialog.cpp:234-293,697-771 (finish at first poll, no UI) | L | M: UI/GPU | later | user-visible error dialogs |
| 239 | KS49 | PSVR2 controllers: PadVrControllerReadState (iA-DdobUen8), PadVrControllerSetTriggerEffects (v8P+9PRqg10), OpenXR input | [KytyPS5 dfec14a] K libs/padVr.cpp:1-158, libs/libPad.cpp:192-193; pre-4644c52 | GPL-2.0 | missing | L | M | later | VR titles; depends on KS70 parts we will not take |
| 240 | SK40 | Stub-equivalent (return 0, no out-param): Ac86z8q7T8A sceKernelExitSblock; Y2OqwJQ3lr8 sync (sharpemu flushes open files; our sceKernelSync uvT2iYBBnkY is a no-op too); LuLTRt0rfTw / 6gYjd50q0CE / TkASc9I-xX0 / RVmEia0vXMI Ult sync opt-param inits (sharpemu: 0x80810001 on NULL only, writes nothing). mkgXxsoxWHg sceKernelClearVirtualRangeName: memory agent. | [sharpemu 514d766] `Kernel/KernelExports.cs:209-217`, `KernelFileExtendedExports.cs:220-234`, `Ult/UltExports.Sync.cs:95-125` | GPL-2.0+ | missing; `libs/libKernel.cpp:1429-1431` | S | L | later | equivalent to loader return-0 stub; registration only |
| 241 | KL26 (+SS62) | Registration-only SystemService stubs: x1UB9bwDSOw SystemServiceDisableMusicPlayer, 9kPCz7Or+1Y sceSystemServiceReenableMusicPlayer (06ab430 2026-10-31), uaieF+glFPs SystemServiceLaunchPlayerDialog, m5CYKX20wfg SystemServiceInitializePlayerDialogParam (void, writes nothing) (f12fc20 2026-10-31 "Stub missing SystemService / NpManager / NpWebApi2 imports (Palworld, PPSA23126)") | [KytyPS5 dfec14a] src/libs/libSystemService.cpp @ dfec14a:261-268, 279-287, 600-604 **+ SS62** [sharpemu 514d766] SystemService/SystemServiceExports.cs:48-60 | GPL-2.0 + GPL-2.0+ | missing | S | L | later | equivalent to loader return-0 stub; registration only |
| 242 | SS56 | libSceAudioPropagation stubs (33): ZQXE-xS6MTE WXMhENV2NcA i687TNRF+hw d84otraxt2s wkseM3LWPuc -wsUTr31yeg PBcrVpEqUVY eEeKqFeNI3o G+QLTfyLMYk aKJZx7wCma8 3aEY9tPXGKc hhz9pITnC8k SoKPzY1-3SU tKSmk2JsMAA 5vzOS2pHMFc MNmGapXrYRs i-0aUex3zCE JZIkSbmt2BE tL2AEPejVQE 2BSFmuKtRss 0r2+9UTg1BA BbOT4vBwAjs gCmQm6dvMxw GrA9ke1QT+E x5VPqg5iyAk ile38Gl-p5M cMl3u+7QBBM 3B9IabLByyM B2KI2AachWE VlBT16890mA XKCN4gpeYsM S0JwP2AFTTE b-dYXrjSNZU | [sharpemu 514d766] Audio/AudioPropagationExports.cs:55-166 | GPL-2.0+ | missing | S | L | later | equivalent to loader return-0 stub; registration only |
| 243 | SS57 | libSceAcm stubs (5): WeZOIm8+8WI Mk1xvQXIdkk A5NXCXK5Gfc S3BPrjCfZ90 uqDIauipRbo | [sharpemu 514d766] Acm/AcmExports.cs:106-143 (4b8d455) | GPL-2.0+ | missing | S | L | later | equivalent to loader return-0 stub; registration only |
| 244 | KS62 | Net: NetResolverAbort AzqoBha7js4 | [KytyPS5 dfec14a] K libs/libNet.cpp:131-133, network.cpp:1458-1462 | GPL-2.0 | missing | S | L | later | equivalent to loader return-0 stub; registration only |
| 245 | KS63 | Http2: Http2SetResolveRetry Gcjh+CisAZM | [KytyPS5 dfec14a] K libs/libNet.cpp:1185-1187,1511; 3c77472 2026-11-02 "libs: stub sceHttp2SetResolveRetry" | GPL-2.0 | missing | S | L | later | equivalent to loader return-0 stub; registration only |
| 246 | KS64 | NpWebApi2: PushEventUnregisterCallback hOnIlcGrO6g | [KytyPS5 dfec14a] K libs/libNet.cpp:2419-2427,2466; f12fc20 2026-10-31 | GPL-2.0 | missing (DeleteFilter KJdPcOGmK58 already O libNet.cpp:3805) | S | L | later | equivalent to loader return-0 stub; registration only |
| 247 | KS66 (+SS50) | DeviceService: 84fDxStrG44, 9ddRUOV8Q5A, UNMEa+5lrUA | [KytyPS5 dfec14a] K libs/libDeviceService.cpp:13-44; 45f5323 2026-10-23 "hle: implement sceDeviceServiceGetEventState (My First Gran Turismo)" **+ SS50** [sharpemu 514d766] Stubs/GameServiceStubs.cs:157-163, 240-260 | GPL-2.0 + GPL-2.0+ | missing / SS50: missing (KytyPS5 has libDeviceService/libHmd2 - other agent) | S | L | later | equivalent to loader return-0 stub; registration only |
| 248 | KS67 (+SS61) | BluetoothHid: tul3-GzejQc, 4FUZ+c52d2k, 4Ypfo9RIwfM | [KytyPS5 dfec14a] K libs/libBluetoothHid.cpp:13-40 **+ SS61** [sharpemu 514d766] Pad/BluetoothHidExports.cs:37-75 | GPL-2.0 + GPL-2.0+ | missing | S | L | later | equivalent to loader return-0 stub; registration only |
| 249 | KS68 | VideoOutVrrStatus: LibwuIonIBw, -q-vbO859Tw | [KytyPS5 dfec14a] K libs/libVideoOutVrrStatus.cpp:20-41 | GPL-2.0 | missing | S | L | later | equivalent to loader return-0 stub; registration only |
| 250 | SS58 | libSceSaveData stubs (8): hsKd5c21sQc v-AK1AxQhS0 ZkZhskCPXFw l1NmDeDpNGU Wz-4JZfeO9g dQ2GohUHXzk eBSSNIG6hMk 52pL2GKkdjA | [sharpemu 514d766] SaveData/SaveDataExports.cs:216-248, 551-561 | GPL-2.0+ | missing | S | L | later | equivalent to loader return-0 stub; registration only (Initialize/2 only create the root dir) |
| 251 | SS59 | libSceRtc stubs (2): LlodCMDbk3o sceRtcInit, 8SljQx6pDP8 sceRtcEnd | [sharpemu 514d766] shadPS4 rtc.cpp:103-105, 686-688 | GPL-2.0+ | missing | S | L | later | equivalent to loader return-0 stub; registration only |
| 252 | SS60 | libSceVoiceQoS stubs (3): Trpt2QBZHCI FuXenJLkk-c +0lOiPZjnBI | [sharpemu 514d766] Voice/VoiceQoSExports.cs:20-50 | GPL-2.0+ | missing | S | L | later | equivalent to loader return-0 stub; registration only |
| 253 | SS63 (+KS65) | single-NID stubs: cTGkc6-TBlI sceNetTerm, BQ3tey0JmQM sceCommonDialogIsUsed, FzQS6DREDfk sceSharePlayProhibitController (INVALID_ARGUMENT only for arg > 1), UOjiprYwVNw sceTextToSpeech2Initialize, 84fDxStrG44 / 9ddRUOV8Q5A DeviceService Initialize/GetEventState, PZSoY8j0Pko scePadGetFeatureReport, yN7Jhuv8g24 sceAvPlayerVprintf, DxGyV8dtOR8 sceAudioOut2ContextBedWrite, i1393UBWu1U Json setGlobalSpecialFloatHandler (error only for null this) | [sharpemu 514d766] files as in s-only.tsv **+ KS65** [KytyPS5 dfec14a] K libs/dialog.cpp:102-106, libDialog.cpp:17 | GPL-2.0 + GPL-2.0+ | missing | S | L | later | equivalent to loader return-0 stub; registration only |

### 4.4 in e4 / done (not re-specified)

| Rank | ID | What | Source | Licence | Ours | Effort | Risk | Class | Value |
|---|---|---|---|---|---|---|---|---|---|
| 254 | KL28 | param.json memory sizing (flexible/CPU/GPU/AMM page tables) and per-module flexible charge | [KytyPS5 dfec14a] 09753bf 2026-10-27, 0a14091 2026-10-26; systemContent.cpp @ dfec14a:177-191; runtimeLinker.cpp:1639-1667, 1715-1716, 1908 | GPL-2.0 | in flight | - | - | in e4 / done | listed only |
| 255 | KS76 | SaveData mount result kept on failed mount | [KytyPS5 dfec14a] K dfec14a 2026-11-02 "Fix save mount result on failed mounts (#2079)" | GPL-2.0 | O libs/libSaveData.cpp:625 | S | - | in e4 / done |  |
| 256 | KS77 | SaveData search sorted by the requested key | [KytyPS5 dfec14a] K 4b0282e 2026-10-27 "savedata: sort directory searches by the requested key" | GPL-2.0 | O libs/libSaveData.cpp:559-582 | S | - | in e4 / done |  |
| 257 | SS87 | VideoOutGetOutputStatus before buffer registration | [sharpemu 514d766] b1ec286 | - | - | - | - | in e4 / done | brief |
| - | sharpemu 11506fc | Submit-time DCB / SET_*_REG_INDIRECT table capture | [sharpemu 514d766] src/SharpEmu.Libs/Agc/AgcExports.Submissions.cs @ 11506fc | GPL-2.0-or-later | built as BC5_DIRECT_TABLE_CATCHER | - | - | in e4 / done | GPU-side catcher, listed for completeness |

### 4.5 valid skips (already match, or provenance)

| Rank | ID | What | Source | Licence | Ours | Effort | Risk | Class | Value |
|---|---|---|---|---|---|---|---|---|---|
| 258 | KK42 | Pro/Trinity answers in `sceKernelIsProspero`-style query and `sceKernelGetOperationMode` | [KytyPS5 dfec14a] K:libs/libKernel.cpp:1324-1332 (`651ef73` 2026-10-29) | GPL-2.0 | O:libs/libKernel.cpp:1404-1415 (0), 3682-3693 (mode 2, submode 0) = KytyPS5's base-PS5 answers | - | - | skip: already match (O:libs/libKernel.cpp:1404-1415, 3682-3693) | Trinity mode itself is the GPU agent's |
| 259 | KK43 | RazorCpu stubs incl. `sceRazorCpuPushMarkerStatic`, `sceRazorCpuSync` | [KytyPS5 dfec14a] K:libs/libRazorCpu.cpp:43-48 (`bbf96a5`, `a9edfb6`) | GPL-2.0 | all six NIDs registered | - | - | skip: already match (O:libs/libRazorCpu.cpp:615-651, O:libs/libDebug.cpp:20) | - |
| 260 | KK44 | libc `strcmp`/`strncmp`/`strcpy` NIDs | [KytyPS5 dfec14a] K:libs/libC.cpp:774-777 (`8c01d8e` 2026-10-24) | GPL-2.0 | same NIDs | - | - | skip: already match (O:libs/libC.cpp:917-921) | - |
| 261 | KK45 | posix `fcntl`/`fsync`/`shutdown` | [KytyPS5 dfec14a] K:libs/libKernel.cpp:1945-1987, kernel/fileSystem.cpp:603-622 | GPL-2.0 | ours is a superset (varargs fcntl, F_GETFL/SETFL, sockets, errno on shutdown, host fsync) | - | - | skip: already match (O:libs/libKernel.cpp:2304-2383, O:kernel/fileSystem.cpp:1328-1406) | - |
| 262 | KK46 | Event flag single-thread gate; semaphore timer placement | [KytyPS5 dfec14a] K:kernel/eventFlag.cpp:123 (older TOCTOU form); K:kernel/semaphore.cpp:213-218 | GPL-2.0 | ours has the race fix; semaphore results identical | - | - | skip: already match (O:kernel/eventFlag.cpp:123-168, O:kernel/semaphore.cpp:203-220) | - |
| 263 | KL29 | Unresolved-import stub thunk (zero int/float return, first-call log) | [KytyPS5 dfec14a] src/loader/runtimeLinker.cpp @ dfec14a:129-215 | GPL-2.0 | loader/runtimeLinker.cpp:157-395 (superset: saves arg regs and AL, late-resolves by NID and patches the slot, journals first calls) | - | - | skip: already match (loader/runtimeLinker.cpp:157-395) | - |
| 264 | KL30 | sceKernelDlsym (NID then name, Func/Object/NoType, `scriptingGetMem`), GetModuleInfoFromAddr, GetModuleInfoForUnwind | [KytyPS5 dfec14a] src/libs/libKernel.cpp @ dfec14a:177-280, 1492, 1625 | GPL-2.0 | libs/libKernel.cpp:181-290 and the two GetModuleInfo* (identical apart from whitespace) | - | - | skip: already match (libs/libKernel.cpp:181-290) | - |
| 265 | KL31 | Red-zone memory-fault protection (Windows only in both) | [KytyPS5 dfec14a] src/loader/runtimeLinker.cpp @ dfec14a:1695-1699 | GPL-2.0-or-later | loader/runtimeLinker.cpp:2559-2585 + redZonePatcher.cpp | - | - | skip: already match (loader/runtimeLinker.cpp:2559-2585) | - |
| 266 | KA52 | Audio3d (7 NIDs) | [KytyPS5 dfec14a] audio3d.cpp:1-319 | GPL-2.0 | audio.cpp:1802-2106 identical (whitespace-insensitive diff of the section) | - | - | skip: already match (audio.cpp:1802-2106) | audio3d_impl.inc is dead |
| 267 | KA53 | Acm (12 NIDs) incl. c5f7644 sceAcmBatchJobPriority (return OK, nothing recorded) | [KytyPS5 dfec14a] acm.cpp:98-103; c5f7644 2026-10-25 | GPL-2.0 | audio.cpp:1617-1800 identical except JobPriority, which ours records per batch and advances 16 bytes (exp 0329, audio.cpp:1711-1722) | - | - | skip: already match (audio.cpp:1617-1800) | ours does more |
| 268 | KA54 | c528324 Opus "write part of a packet" | [KytyPS5 dfec14a] ajm.cpp:426-431 + resampler.h | GPL-2.0 | ajm/opus_decoder.h:89-197 buffers the decoded packet and hands it out across jobs for every Opus job (exp 0154); KytyPS5 does it only in the resample path (KA42) | - | - | skip: already match (ajm/opus_decoder.h:110-124) |  |
| 269 | KA55 | b46eeb7 push outside the state mutex | [KytyPS5 dfec14a] libAudio2.cpp:437-473 | GPL-2.0 | libAudio2.cpp:403-427, 637-646 already submit outside the mutexes | - | - | skip: already match (libAudio2.cpp:403-427) | residual race is KA17 |
| 270 | KA56 | 12-channel float output (7.1 + 4 heights) | [KytyPS5 dfec14a] audio.cpp:341-353; libAudio2.cpp:305-309 | GPL-2.0 | libAudio2.cpp:274-300, 305-307 BC5 downmix 12 -> 8 (heights -3 dB; KytyPS5 0 dB) | - | - | skip: already match (libAudio2.cpp:274-300) |  |
| 271 | KA57 | PngDec (5 NIDs) | [KytyPS5 dfec14a] libPngDec.cpp | GPL-2.0 | identical | - | - | skip: already match (libPngDec.cpp:1-381) |  |
| 272 | KA58 | FontFt (2 NIDs) | [KytyPS5 dfec14a] libFontFt.cpp | GPL-2.0 | identical | - | - | skip: already match (libFontFt.cpp:1-45) |  |
| 273 | KA59 | AvPlayer without file callbacks reads the guest file through Common::File | [KytyPS5 dfec14a] avPlayer.cpp:590-605, 627-635 | GPL-2.0 | avPlayer.cpp:674-682 opens the real path with avformat_open_input (and strips file://) | - | - | skip: already match (avPlayer.cpp:674-682) |  |
| 274 | KA60 | Videodec2 AvcPictureInfo moved into videoDec2Decoder (MakeAvcPictureInfo) | [KytyPS5 dfec14a] libVideoDec2.cpp:114, 542 | GPL-2.0 | libVideoDec2.cpp:114-176, 602-635 same fields and values | - | - | skip: already match (libVideoDec2.cpp:602-635) |  |
| 275 | KA61 | KytyPS5 Opus Initialize rejects > 2 channels, mapping family != 0, rate != 48000 | [KytyPS5 dfec14a] ajm/opus_decoder.h:31-65 | GPL-2.0 | ajm/opus_decoder.h:42-77, 228-273 supports mapping family 1 up to 8 channels via libopus | - | - | skip: already match (ajm/opus_decoder.h:228-273) | ours is a superset |
| 276 | KS71 | MsgDialog finishes at Open | [KytyPS5 dfec14a] K libs/dialog.cpp:646 | GPL-2.0 | O libs/dialog.cpp:580-594 (RUNNING until first poll; progress bar until close) | - | - | skip: already match (ours supersedes, dialog.cpp:580-594) |  |
| 277 | KS72 | RTC local time = UTC | [KytyPS5 dfec14a] K libs/libRtc.cpp:290-304 | GPL-2.0 | O libs/libRtc.cpp:285-318 (host zone, DST) | - | - | skip: already match (ours supersedes, libRtc.cpp:285-318) |  |
| 278 | KS73 | WebBrowserDialogGetStatus returns NONE | [KytyPS5 dfec14a] K libs/libWebBrowserDialog.cpp:13-17 | GPL-2.0 | O libs/libWebBrowserDialog.cpp:237 (state machine) | - | - | skip: already match (libWebBrowserDialog.cpp:237) |  |
| 279 | KS74 | Mount3 unknown mode -> EXIT | [KytyPS5 dfec14a] K libs/libSaveData.cpp:728-730 | GPL-2.0 | O libs/libSaveData.cpp:643-647 (PARAMETER, releases slot) | - | - | skip: already match (ours supersedes, libSaveData.cpp:643-647) |  |
| 280 | KS75 | Ssl, NetCtl and LibNetCtl tables, NpGameIntent, GameUpdate, Share (libNet + libShare.cpp), Random, Remoteplay, WebBrowserDialog (libNet), NpTrophy2 icon getters | [KytyPS5 dfec14a] K libs/libNet.cpp namespaces; libShare.cpp | GPL-2.0 | O identical (nsx diff 0 KytyPS5-only lines; libShare.cpp onlyK=0) | - | - | skip: already match (libNet.cpp:223-236,1389-1408,3326-3411,3827-4032,4038-4131; libShare.cpp) |  |
| 281 | SK41 | User-event id sign extension (int id -> uintptr_t ident, -1 -> all ones). | [sharpemu 514d766] 46a7d3a 2026-10-09 | GPL-2.0+ | `kernel/eventQueue.cpp:463, 481, 499, 527` (`static_cast<uintptr_t>(int)` sign-extends) | - | - | skip: already match (eventQueue.cpp:463) |  |
| 282 | SK42 | Equeue: delete terminates waiters; trigger arg in udata; level state kept across reads; re-add refreshes pending udata; delete drops pending copies. | [sharpemu 514d766] 816ec4a, 2df6f5b | GPL-2.0+ | `kernel/eventQueue.cpp:83-98, 104-106, 122-128, 221-226, 264-265, 306-329` | - | - | skip: already match (eventQueue.cpp:83-98) | duplicate-delivery part is SK01 |
| 283 | SK43 | Semaphore wake on signal/cancel/delete, no lost wake, cancel -> ECANCELED, delete -> EACCES, zero-count signal OK; posix sem_* errno. | [sharpemu 514d766] edb4eb8 2026-07-11, 2a4da8c 2026-07-22, 2df6f5b, b6347f9 | GPL-2.0+ | `kernel/semaphore.cpp:62-150, 323-337, 516-680` (condvar design) | - | - | skip: already match (semaphore.cpp:100-150) |  |
| 284 | SK44 | Mutex: unlock hand-off (no "free with queued waiter"), NORMAL self-relock EDEADLK, timed waits in microseconds. | [sharpemu 514d766] 73e8821 2026-07-19, f36ce40 2026-08-02, 4e6d1e0 2026-10-07 | GPL-2.0+ | `kernel/pthread.cpp:1373-1505` (owner + condvar loop, chrono us) | - | - | skip: already match (pthread.cpp:1373-1437) |  |
| 285 | SK45 | Cond vars: signals are edges (no pending credit), pthread_cond_timedwait takes an absolute timespec on the cond's clock, posix NID exported, Signalto exists. | [sharpemu 514d766] 9cdc855 2026-07-13, 1be009c 2026-07-15, c0fd6a8 2026-07-10, 2a27cfe 2026-09-22 | GPL-2.0+ | `kernel/pthread.cpp:2911-3047, 3168-3250, 4601-4607`; `libs/libKernel.cpp:3625, 2499` | - | - | skip: already match (pthread.cpp:3168) | ours uses the attr clock, sharpemu always realtime |
| 286 | SK46 | Precise usleep/nanosleep, EINTR resumed, sub-ms timed waits. | [sharpemu 514d766] ef73fe4 2026-10-14, 4e6d1e0, de4fc1e 2026-07-11, `HostTiming.cs` | GPL-2.0+ | `common/threads.cpp:138-168` (clock_nanosleep ABSTIME, EINTR loop); `kernel/pthread.cpp:617-645, 4153-4206` | - | - | skip: already match (threads.cpp:167) | sharpemu's issue was Win32 Sleep rounding |
| 287 | SK47 | clock ids incl. *_PRECISE/*_FAST/SECOND, gettimeofday tz zero-fill, clock_getres. | [sharpemu 514d766] 65a4077, 5e76554, 3a24db5 (2026-07-11), 0c467e8 | GPL-2.0+ | `kernel/pthread.cpp:311-345, 3930-3997`; `libs/libKernel.cpp:1956-1984, 2390` | - | - | skip: already match (pthread.cpp:311) | NULL tp code: SK37 |
| 288 | SK48 | getdents on a file fd is an error (not EOF); "." and ".." are listed. | [sharpemu 514d766] 007bf6f 2026-07-23 | GPL-2.0+ | `kernel/fileSystem.cpp:1498-1500`; `common/platform/sysLinuxFileIO.cpp:670-684` (readdir includes . and ..) | - | - | skip: already match (fileSystem.cpp:1498) |  |
| 289 | SK49 | Unmapped absolute guest paths denied (no host passthrough); no negative stat cache to alias case-distinct paths. | [sharpemu 514d766] e01092a 2026-07-21, f84d869 2026-07-18 | GPL-2.0+ | `kernel/fileSystem.cpp:370-372, 397, 253-288` | - | - | skip: already match (fileSystem.cpp:372) | ".." escape is SK05 |
| 290 | SK50 | Unlink of an open file allowed. | [sharpemu 514d766] 1811cef 2026-10-09 | GPL-2.0+ | `kernel/fileSystem.cpp:1427-1430` | - | - | skip: already match (fileSystem.cpp:1427) | rename is SK02 |
| 291 | SK51 | POSIX aliases titles link directly: clock_getres, pthread_once alias, getpagesize 16 KiB, mprotect/munmap/setsockopt, posix tryrdlock, pthread_yield, pthread sem exports, HR timer events, sceKernelDebugWriteCppExceptionInfo -> 0. | [sharpemu 514d766] 0c467e8 2026-07-19, 5d7d8e0, a60bfc9, 3e76003, f4e6c73 | GPL-2.0+ | `libs/libKernel.cpp:1944-1948, 2390, 2425, 2462-2467, 2475, 2484, 3507-3508, 3535-3541, 3654` | - | - | skip: already match (libKernel.cpp:2390) | trywrlock is SK06 |
| 292 | SK52 | Event flags (wait modes, single-waiter EPERM, cancel ECANCELED, delete EACCES, poll EBUSY). | [sharpemu 514d766] 5512da9, d134f9b | GPL-2.0+ | `kernel/eventFlag.cpp:326-370` | - | - | skip: already match (eventFlag.cpp:326) |  |
| 293 | SK53 | Fiber: sharpemu's fixes capture import-call continuations (engine-specific); GetSelf outside a fiber writes 0 and returns OK in both. | [sharpemu 514d766] d134f9b 2026-06-23, d0dd3fe 2026-09-30; `Fiber/FiberExports.cs:356-372` | GPL-2.0+ | `libs/libKernel.cpp:2627-3210` (real context switch; GetSelf 3114-3124) | - | - | skip: already match (libKernel.cpp:3114) |  |
| 294 | SK54 | Sync-on-address wait/wake (mismatch -> OK, zero timeout -> ETIMEDOUT, misaligned -> EINVAL); default thread affinity 0x7F; main-thread stack reported in pthread attrs. | [sharpemu 514d766] 09bd4f0, 2df6f5b | GPL-2.0+ | `kernel/syncOnAddress.cpp:88-140, 272-315`; `kernel/pthread.cpp:2061, 1118-1180` | - | - | skip: already match (syncOnAddress.cpp:272) |  |
| 295 | SS66 | SaveDataDialog open param: mode at +0x34, userData at +0x70 | [sharpemu 514d766] 4d56978 2026-10-10 | - | O libs/dialog.cpp:323-338 | - | - | skip: already match (dialog.cpp:323-338) | - |
| 296 | SS67 | Per-slot block count in mount info and search | [sharpemu 514d766] 4d56978 | - | O libs/libSaveData.cpp:345-390, 670-675, 1169-1193 | - | - | skip: already match (libSaveData.cpp:345-390) | residual: no 48-block floor; a slot without a record reports the max |
| 297 | SS68 | SetParam keeps the slot's other metadata | [sharpemu 514d766] 4d56978 | - | O .param/.blocks sidecars are separate files, libSaveData.cpp:1149-1161, 410-428 | - | - | skip: already match (libSaveData.cpp:1149-1161) | - |
| 298 | SS69 | NP reachability: signed out / UNAVAILABLE | [sharpemu 514d766] 4d56978, 9eef395 | - | O libs/network.cpp:4678-4699, 4786-4799 | - | - | skip: already match (network.cpp:4678-4699) | - |
| 299 | SS70 | sceRtcConvertLocalTimeToUtc on non-UTC hosts | [sharpemu 514d766] 341c2a0 | - | O libs/libRtc.cpp:172-182 (offset arithmetic) | - | - | skip: already match (libRtc.cpp:172-182) | - |
| 300 | SS71 | sceNetHtonl/Htons/Ntohl/Ntohs return the converted value | [sharpemu 514d766] a8be1da | - | O libs/libNet.cpp:172-186 | - | - | skip: already match (libNet.cpp:172-186) | - |
| 301 | SS72 | sceNetInetPton | [sharpemu 514d766] 7a108c6 | - | O libs/network.cpp:1508-1528 | - | - | skip: already match (network.cpp:1508-1528) | bad family: OURS EAFNOSUPPORT (BSD-like), sharp 0 |
| 302 | SS73 | Notice skip flag written as one byte | [sharpemu 514d766] 3c500d2 | - | O libs/libSystemService.cpp:234-244 (bool*) | - | - | skip: already match (libSystemService.cpp:234-244) | - |
| 303 | SS74 | New touch id per touchpad contact | [sharpemu 514d766] c60b57a | - | O libs/controller.cpp:1040-1044 | - | - | skip: already match (controller.cpp:1040-1044) | - |
| 304 | SS75 | Pad handle 0 accepted before first open (b4b9501), rejected after (ac8ffc3) | [sharpemu 514d766] sharp HEAD dropped both: PadSessionRegistry.cs:97-103 (9e19412) only knows opened handles | - | O libs/controller.cpp:489-492 rejects 0 | - | - | skip: already match (controller.cpp:489-492) | - |
| 305 | SS76 | scePlayGoGetLocus BAD_CHUNK_ID for unknown ids (enumeration terminator) | [sharpemu 514d766] b4b9501 | - | O libs/libPlayGo.cpp:188-194 | - | - | skip: already match (libPlayGo.cpp:188-194) | see SS18 |
| 306 | SS77 | AudioOut2 queue level written as u32, available queues reported | [sharpemu 514d766] e13cb28 | - | O libs/libAudio2.cpp:673-712 | - | - | skip: already match (libAudio2.cpp:673-712) | - |
| 307 | SS78 | Float PCM endpoint conversion | [sharpemu 514d766] 3585519 | - | O keeps float as float, libs/audio.cpp:558-570 | - | - | skip: already match (audio.cpp:558-570) | - |
| 308 | SS79 | AudioOut2 MasteringInit / Set3DLatency succeed | [sharpemu 514d766] 4b8d455 | - | O libs/libAudio2.cpp:1016-1052 | - | - | skip: already match (libAudio2.cpp:1048-1052) | - |
| 309 | SS80 | sceAudioOutOutputs | [sharpemu 514d766] 26c5029 | - | O libs/libAudio.cpp:125 | - | - | skip: already match (libAudio.cpp:125) | - |
| 310 | SS81 | Ajm Opus decode, Gen5 codec type 24 accepted | [sharpemu 514d766] 660df73, d3600c9 | - | O libs/ajm.cpp:134, 415-416, 603 | - | - | skip: already match (ajm.cpp:415-416) | - |
| 311 | SS82 | sceAppContentDownloadDataGetAvailableSpaceKb | [sharpemu 514d766] 2ced3af | - | O libs/libAppContent.cpp:131-163 | - | - | skip: already match (libAppContent.cpp:131-163) | - |
| 312 | SS83 | MsgDialog RUNNING state, buttonId 1, ProgressBar exports | [sharpemu 514d766] de13735 | - | O libs/dialog.cpp:~581-650, libDialog.cpp:126-128 | - | - | skip: already match (dialog.cpp:581-596) | error guards differ: SS12 |
| 313 | SS84 | RemotePlay initialised + disconnected | [sharpemu 514d766] 7b95016 | - | O libs/libNet.cpp:4088-4105 | - | - | skip: already match (libNet.cpp:4088-4100) | - |
| 314 | SS85 | UDS property object/array (19) + GetAddcontEntitlementInfoList | [sharpemu 514d766] s-only rows | - | registered, two-line LIB_FUNC: O libs/libNet.cpp:3088-3138, 1722-1723 | - | - | skip: already match (libNet.cpp:3088-3138) | inventory parser miss |
| 315 | SS86 | NpAuth (9) and Http2 (5) name-only s-only rows | [sharpemu 514d766] s-only rows | - | O libs/libNet.cpp:1972-1979, libNp.cpp:62, libNet.cpp:1358-1383 | - | - | skip: already match (libNet.cpp:1972-1979) | inventory had no NID |
| 316 | KS70 | Hmd2 (15 NIDs) and VrTracker2 (4 NIDs) | [KytyPS5 dfec14a] K libs/libHmd2.cpp:42-135, libs/hmd2.h:33-60, libs/libVrTracker2.cpp:34-122 | GPL-2.0 | missing | L | H | skip: provenance (Sce-prefixed structs with SDK-style field names -- sizeOfThis, reserved00/01, motionSensorDataValidFlags, lastValidVisionTimestamp, playAreaUpdateCounter -- not derivable from NIDs; origin not stated) |  |
| 317 | SS64 | sharp Rtc helpers from 56bf00e (CompareTick, Get/SetDosTime, TickAddMonths/Years, network ticks, Init/End) | [sharpemu 514d766] Rtc/RtcExports.cs (56bf00e 2026-07-13 "[RTC] Port core rtc helpers from PS5 3.20 libs") | GPL-2.0+ | - | - | - | skip: provenance (commit says ported from PS5 3.20 firmware libs) | use SS38/SS42/SS59 instead |
| 318 | SS65 | sceAudioOut2UserGetSupportedAttributes (iE8trxPKnAg) masks 0x1F/0x3FFF | [sharpemu 514d766] Audio/AudioOut2Exports.cs:1183-1215 | GPL-2.0+ | missing | - | - | skip: provenance (comment :1196-1198 derives the masks from attribute ids that "exist in the header") | - |

## 5. Port specs for the e4-now items (rank order)

Each block is the pass's own spec, copied verbatim. For merged items the second source's spec follows. `K:` means KytyPS5 `dfec14a`, `S` or `sharp` paths mean sharpemu `514d766` `src/SharpEmu.Libs`, and `O:` means our effective tree. Every item goes behind its own switch.

### Conventions from each part (read the one for the item's source part)

**KK (KytyPS5 dfec14a):** Common: register in the named `LIB_DEFINE` block of O:libs/libKernel.cpp (Posix 2387, FS 3430, Mem 3453, Equeue 3493, Pthread 3541, InitLibKernel_1 3695). Tests go in a new file under the base tree's `tests/` (KytyPlus `f266548` has a CMake test tree: tests/CMakeLists.txt, SyncOnAddressTests.cpp, EventQueueLifetimeTests.cpp); KytyPS5's tests/KernelFileSystemTests.cpp @dfec14a shows how to start the pthread subsystem and run guest threads from a host test (TestMutexHandoff, l.167-271). Every change behind its own switch per the fixes-first rule.

**KA (KytyPS5 dfec14a):** Common: library names below are as registered (`libSce` prefix is stripped by the linker). Every AudioOut/AudioOut2/ AudioIn/AJM/NGS2 item still needs the exp 0372 replug check before it ships. Per the 10-31 rule each fix gets a switch. CPU tests can run without SDL: with no Audio subsystem `AudioInternal::AudioOutOpen` returns 0, so AudioOut2 ports open without devices; `Libs::Audio::Audio` methods need the subsystem object but no device (SDL_AUDIODRIVER=dummy).

**KS (KytyPS5 dfec14a):** All return codes are KytyPS5's constants; insertion points are in OURS. CPU tests need no game and no GPU: a small host test binary linking the lib file (KytyPS5 has matching tests: tests/SaveDataMemoryTests.cpp, NetResolverTests.cpp, HttpUriParseTests.cpp, KernelFileSystemTests.cpp, ControllerSettingsTests.cpp, PsmlTests.cpp).

**SK (sharpemu 514d766):** Common: library "libkernel" rows go in `libs/libKernel.cpp`; posix wrappers live in `namespace Posix` and use `POSIX_CALL` / `POSIX_N_CALL` (-1 + errno) or `POSIX_PTHREAD_CALL` (errno as return) from `libs/errno.h:9-40`. Tests are host unit tests (or a small guest-free harness calling the C++ functions directly); none needs the game or the GPU.

**SS (sharpemu 514d766):** Common: insert next to the named LIB_DEFINE; S paths are `src/SharpEmu.Libs/...` @514d766. Audio-path rows (SS34, SS35) need the DualSense replug check (exp 0372 s6n0372.sh + replug0372.sh, then physical replug and a DS4) before shipping.

#### 1. KK02 (+SK01)

- **KK02** in O:kernel/eventQueue.cpp:130-134 add `else { break; }` after the pending-events pop
  (K:eventQueue.cpp:124-127). Test: add user event (no EV_CLEAR) id 5, trigger once, wait with num=8:
  `*out == 1`; a second wait returns it again (level stays).

*Second source, SK01:* **SK01 equeue one-delivery-per-wait.** `kernel/eventQueue.cpp:100-147` `GetTriggeredEvents`. Keep the loop for an
event that has `pending_events` (AMPR distinct completions, 285-295), but after delivering an event whose state came
from neither a reset nor a popped pending entry (i.e. still `triggered` and `pending_events` empty), `break` the inner
loop: each knote is reported at most once per wait. Source of the rule: sharpemu `KernelEventQueueCompatExports.cs:
1920-1975` (each queued entry delivered once, level entries re-queued, comment 1951-1953). Test: create eq; AddUserEvent
(eq, 5); TriggerUserEvent(eq, 5, 0x1234); WaitEqueue(num=4, timo=&0) -> out 1 (today 4), ev[0].udata 0x1234; a second
wait -> out 1 again (level); same with AddUserEventEdge -> second wait ETIMEDOUT; AMPR id with three triggers -> out 3.

#### 2. KK01

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

#### 3. KL01

**KL01 -- TLS stubs keep RFLAGS**
- NIDs: none (loader JIT code).
- Behaviour: the patched TLS load must leave RFLAGS as the original `mov reg,fs:[0]` does. Replace in
  `Jit::TlsRegStub::code` `48 81 EC 80 00 00 00` (sub rsp,0x80) by `48 8D 64 24 80 66 90` (lea rsp,[rsp-0x80]; nop,
  same 7 bytes) and `48 81 C4 80 00 00 00` (add rsp,0x80) by `48 8D A4 24 80 00 00 00` (lea rsp,[rsp+0x80], 8 bytes;
  ret moves one byte later, padding shrinks by one). Same two changes in `Jit::SafeCall::code` (offset /*00*/ and
  /*43*/; ret becomes /*4b*/). Call offsets (`code[9]`, `code[13]`, `code[15]`, SafeCall `code[0x22]`) are unchanged.
- Port: KytyPS5 src/loader/jit.h @ dfec14a:43-117 (TlsRegStub 43-72, SafeCall 74-117).
- Insertion: OURS loader/jit.h:89-161.
- CPU-only test: host x86-64 unit test; mmap an RWX buffer, placement-new `Jit::SafeCall`, `SetFunc` to an MS-ABI
  function returning a constant; from inline asm set CF and ZF (`stc; cmp eax,eax`), `call` the buffer, read flags
  with `pushfq/pop`; assert CF/ZF/SF/OF/PF unchanged and RAX = the constant. Same through a `TlsRegStub` whose
  SetFunc points at the SafeCall buffer (assert the chosen register gets the constant, RAX preserved). Current code
  fails the flags check.

#### 4. KL02

**KL02 -- TLS patch placement**
- NIDs: none.
- Behaviour: `Jit::Call9::code = {0x48, 0xE8, rel32, 0x48, 0x89, 0xC0}`; `SetFunc` computes rel from `&code[6]` and
  stores at `code[2]`; `SetOutputReg` writes `code[8]`. In the TLS scan of RuntimeLinker::PatchProgram: only scan
  when `size >= Jit::Call9::GetSize()`; on a match place `Call9` at `inst_ptr` (the 0x64 byte), leave the counted
  0x66 bytes untouched, drop the NOP fill, advance `ptr += prefix_count + 9 - 1`; log `inst_ptr`.
- Port: KytyPS5 src/loader/jit.h @ dfec14a:21-41; src/loader/runtimeLinker.cpp @ dfec14a:968-1016.
- Insertion: OURS loader/jit.h:68-87; loader/runtimeLinker.cpp:1519-1567.
- CPU-only test: move the scan into a free function `PatchTlsLoads(uint8_t* p, size_t n, uint64_t handler)` (or test
  through a hook); buffer `3C 66 64 48 8B 04 25 00 00 00 00 C3`: after patching byte 1 is still 0x66, bytes 2..10 are
  `48 E8 xx xx xx xx 48 89 C0`, Zydis decodes `cmp al,0x66; call; mov rax,rax; ret`. Buffer
  `66 66 66 64 48 8B 1C 25 00 00 00 00 C3` (rbx): prefixes kept, call target = handler + TlsRegStub offset(3);
  executing it on the host with a stub handler returns the expected value (a 64-bit call on AMD and Intel). A
  5-byte buffer is left untouched.

#### 5. KK06

- **KK06** O:kernel/pthread.cpp:1489-1492 → `mutex->owner = nullptr; mutex->count = 0;
  mutex->cv.notify_one();` while `lock` is held. 2925-2937, 3029-3037, 3062-3070: call
  `(*cond)->cv.notify_all()` inside the `lock_guard` block (use a local `auto* c = *cond`). 586-593
  likewise. Source: K:pthread.cpp:523 comment, 1404-1413, 2765-2771. Test (ASan build): 2 guest threads
  × 100k rounds of {heap struct with mutex+cond; waiter locks, waits flag; signaller locks, sets flag,
  unlocks, then signals; waiter returns, destroys both, frees} with no ASan report.

#### 6. KK03 (+SK11)

- **KK03** O:kernel/pthread.cpp:2464 replace the EXIT with `if (*rwlock == nullptr) return OK;`
  (K:2295-2298); in Timedrdlock (2635) and Timedwrlock (2647) add the `CreateObject(rwlock,
  Type::Rwlock)` + null check of K:2472-2479 / 2489-2496 before the EXIT. Test: K test
  TestStaticRwlockDestroy (tests @dfec14a:104-113) plus `PthreadRwlockTimedrdlock(&static_null, 1000)
  == OK` and unlock.

*Second source, SK11:* **SK11 rwlock timed static init.** `kernel/pthread.cpp:2635-2657`: add the `GetPthreadStaticObjects()->CreateObject(
rwlock, PthreadStaticObject::Type::Rwlock)` step that `PthreadRwlockRdlock` has (2621-2624) to both timed functions.
Test: `PthreadRwlock l = nullptr; PthreadRwlockTimedrdlock(&l, 1000)` -> OK, no exit; Timedwrlock from another thread
-> ETIMEDOUT.

#### 7. KK04 (+SK02)

- **KK04** delete O:kernel/fileSystem.cpp:1456-1457. Test: mount a temp dir at /savedata0, open
  "/savedata0/a" (O_CREAT|O_RDWR), create "/savedata0/b", `KernelRename(".../b", ".../a")` == OK while
  a is open; `KernelRename(".../a", ".../c")` == OK; read through the old fd still works.

*Second source, SK02:* **SK02 rename open files and directories.** `kernel/fileSystem.cpp:1444-1476`. Remove the two `EXIT_NOT_IMPLEMENTED`
(1456-1457). If `IsDirectoryExisting(real_from)` use `std::filesystem::rename` (target an existing empty dir or
absent); else the current file path. After success, under `g_files` lock, set `real_name = real_to` on every open File
whose `real_name == real_from`, and clear (`{}`) `real_name` of Files that pointed at the replaced `real_to` (their
inode stays valid on Linux; KernelFsync reopens by `real_name`, 1349). Needs a small `FileDescriptors::Rename(from,to)`
method (class at 88-104). Errors: missing source -> ENOENT (as now). Source: sharpemu `KernelFileExtendedExports.cs:
350-379` (Directory.Move / File.Move overwrite: true), reason 1811cef. Test: mount a temp dir at /temp0; open
/temp0/a (write "x"); rename /temp0/a -> /temp0/b: OK, no exit; read through the fd still works; fsync(fd) OK;
mkdir /temp0/d; rename /temp0/d -> /temp0/e: OK.

#### 8. SK04 (+KK09)

**SK04 KernelOpen without exits.** `kernel/fileSystem.cpp:433-583`: (1) 469 `default:` -> `return KERNEL_ERROR_EINVAL`
(sharpemu instead treats 3 as read-write, `KernelMemoryCompatExports.cs:4827-4839`; FreeBSD behaviour not verified
here); (2) 472-473 and 532-533 -> delete the descriptor and `return KERNEL_ERROR_EISDIR` (`libs/errno.h:208`) for a
directory opened with write access, O_TRUNC or O_CREAT (sharpemu returns its INVALID_ARGUMENT at 1521-1525; EISDIR is
the FreeBSD meaning, value already in our table); (3) 513-515 call `g_files->DeleteDescriptor(descriptor)` before
returning EACCES. Test: open a mounted dir with O_WRONLY / O_RDONLY|O_CREAT / O_DIRECTORY|O_RDWR -> error, no exit;
open(file, 3) -> EINVAL; 1000 x open(file, O_RDONLY|O_TRUNC) then a normal open returns a small fd (no slot growth).

*Second source, KK09:* - **KK09** O:kernel/fileSystem.cpp:513-514 add `g_files->DeleteDescriptor(descriptor);` (K:495-498).
  Test: 1000 × open(path, O_RDONLY|O_TRUNC) == EACCES, then a normal open returns the same lowest fd as
  before the loop.

#### 9. SK03

**SK03 WaitEqueue NULL out.** `kernel/eventQueue.cpp:432`: replace `EXIT_NOT_IMPLEMENTED(out == nullptr)` with a local
`int count` and write `*out` only when non-NULL; return codes unchanged. Source: sharpemu `KernelEventQueueCompatExports
.cs:813, 937`. Test: trigger, WaitEqueue(eq, ev, 1, nullptr, &zero) -> OK and ev[0] filled.

#### 10. KS03 (+SS01, KS02)

**KS03 SyncSaveDataMemory.** NID wiT9jeC7xPw. `int(const SaveDataMemorySync* p)` with {int32 user_id; uint32 slot_id;
uint32 option; uint8 reserved[28]}. PARAMETER if p null, slot_id>=4 or option>1; INVALID_LOGIN_USER if user_id<0;
MEMORY_NOT_READY if Setup was never called (add a flag set in O SetupSaveDataMemory2 :757); flush
(save_data_memory_store, O :714-739); if option==1 return the flush status; else queue event type 3
(MEMORY_SYNC_END) with title_id = get_title_id(), dir_name "sce_sdmemory"+(slot?slot:""), error_code = status, under
g_mount_mutex; return OK. Source K libs/libSaveData.cpp:197-202,267,309-311,1151-1182. Insert at O :244-246 (constant),
:1061-1067. Test: Setup slot 0, Sync option 0 -> GetEventResult gives type 3, error 0; Sync option 1 -> no event;
Sync without Setup -> MEMORY_NOT_READY.

*Second source, SS01:* **SS01 sceSaveDataSyncSaveDataMemory** (wiT9jeC7xPw, libSceSaveData). `int (const SaveDataMemorySync* p)` where p =
{int32 userId; uint32 slotId; uint32 option; reserved[28]} (shadPS4 savedata.cpp:199-204). Behaviour: p null ->
SAVE_DATA_ERROR_PARAMETER; flush memory (OURS already writes through on Set, so nothing to do); queue
`queue_save_data_event(3 /*SAVE_DATA_MEMORY_SYNC*/, p->userId, title_id(our TITLE_ID), dir "sce_sdmemory")`; return OK.
Add a mutex around g_save_data_events (push in queue_save_data_event, pop in GetEventResult). Source:
S SaveData/SaveDataExports.cs:1571-1609; shadPS4 savedata.cpp:1637-1665. Ours: replace libs/libSaveData.cpp:1061-1067,
add `constexpr uint32_t SAVE_DATA_EVENT_TYPE_MEMORY_SYNC_END = 3;` near :244. Test: CPU unit test calls Setup2, Set2,
Sync, then GetEventResult -> OK with type 3, user id echoed; second GetEventResult -> NOT_FOUND.

*Second source, KS02:* **KS02 SaveData event lock.** Wrap the queue_save_data_event calls in SaveDataCommit (O :940) and SaveDataBackup (O :1123)
and the empty-check/pop in SaveDataGetEventResult (O :1090-1095) in `Common::LockGuard lock(g_mount_mutex)` (K:1027,1275,1191).
Test: two threads, one Backup in a loop, one GetEventResult in a loop, under TSan/ASan; no report.

#### 11. KS09 (+SS02)

**KS09 existed_memory_size.** Record the size of memory.dat read by save_data_memory_load (O :693-716; 0 when the
file is missing) and report that at O :765 instead of g_save_data_memory.size() (K :457-483,823). Test: empty
KYTY_BC5_SAVEDATA_DIR -> Setup reports 0; after Set + new process state reload -> reports the file size.

*Second source, SS02:* **SS02 sceSaveDataSetupSaveDataMemory2** (oQySEUfgXRA). `int (const SaveDataMemorySetup2*, SaveDataMemorySetupResult*)`.
Behaviour: existed = bytes in memory.dat before this call (0 when the file is absent; if already set up in this
process, the size set up then); then grow the store to max(existed, memory_size); write result->existed_memory_size =
existed (before growing). Remove the 0x10000 pre-size of g_save_data_memory (libSaveData.cpp:248) or track a separate
`g_save_data_memory_existed`. Source: S SaveDataExports.cs:1495-1551 (result written before mutating, :1530-1545);
shadPS4 savedata.cpp:1580-1603. Ours: libs/libSaveData.cpp:693-718 (load), 741-769. Test: temp KYTY_BC5_SAVEDATA_DIR,
no file -> existed 0; Set2 then a fresh process-state (reset globals) -> existed = file size.

#### 12. KA01

**KA01 sceAudioOutOutputs** (w3PdaSTSwGE, AudioOut). `int AudioOutOutputs(AudioOutOutputParam* param, uint32_t num)`.
After the null check add `if (num == 0 || num > Audio::OUT_PORTS_MAX) return AUDIO_OUT_ERROR_INVALID_SIZE;`
(0x80260006). Port KytyPS5 audio.cpp:995-997 into ours audio.cpp:1498-1517 (before the `params[]` loop). Test: open one
port (dummy driver), call with num 0 and 33: both return 0x80260006, no abort, stack canary intact.

#### 13. KA02

**KA02 sceAudioOutOpen** (ekNvsT22rsY, AudioOut). After the port-type check add `if (freq == 0) return
AUDIO_OUT_ERROR_INVALID_SAMPLE_FREQ;` (0x80260008). Source audio.cpp:870-872; ours audio.cpp:1378-1423 (insert before 1392).
Test: AudioOutOpen(255, 0, 0, 256, 0, 1) returns 0x80260008 before g_audio is touched (works with no subsystem).

#### 14. KA03

**KA03 Ngs2RackDestroy** (lCqD7oycmIM, Ngs2). `int Ngs2RackDestroy(uintptr_t rack, Ngs2ContextBufferInfo* out)`.
Behaviour: zero `*out` if given; rack 0 or not in g_racks_list -> 0x804a8202; under ngs->mutex and a new global
`g_racks_mutex` unlink it; take its stored buffer_info and allocator; if allocator.free_handler is set return
`free_handler(&buffer_info)`, else copy buffer_info to `*out`, return OK. Source ngs2.cpp:1456-1528 without the custom
module cleanup (lines 1503-1518; ours has no modules); store `rack->buffer_info = *buffer_info` in RackCreate
(KytyPS5 1377) and take g_racks_mutex where the list is linked (KytyPS5 1381) and walked (1973, render). Ours:
add `Ngs2ContextBufferInfo buffer_info` to Ngs2RackInternal (audio.cpp:2392-2398), link at audio.cpp:2877-2878,
render walk audio.cpp:3024, replace audio.cpp:2958-2967. Test: SystemCreate in a host buffer; RackCreateWithAllocator
with host sysv_abi alloc/free handlers counting calls; RackDestroy -> free called once with the same buffer, OK;
fill the freed buffer with 0xCC, call SystemRender, buffer unchanged; second RackDestroy -> 0x804a8202.

#### 15. KS01

**KS01 Http2 async event.** Http2 lib: Http2SendRequestAsync (A+NVAFu4eCg), Http2ReadDataAsync (bGN-6zbo7ms).
Signature `int(int req_id, const void* post_data|void* data, size_t size, const Http2TriggerUserEventArgs* kq, void* option)`;
struct {KernelEqueue eq; int uniq_id; uint8_t pad[4]; void* udata; void* reserved;} static_assert 32. After the
request state is set, `if (kq) LibKernel::EventQueue::KernelTriggerUserEvent(kq->eq, kq->uniq_id, kq->udata)`;
ReadDataAsync also sets async_event=1 on the error path (K:1453-1472). Port K libs/libNet.cpp:837-845,1259-1264,
1266-1288,1436-1473 into O libs/libNet.cpp:1132-1152,1300-1336 (O eventQueue.h:72 has KernelTriggerUserEvent).
Test: create equeue, AddUserEvent(id 7), call SendRequestAsync with {eq,7,udata} -> KernelWaitEqueue returns id 7 with udata.

#### 16. SS22 (+KS69)

**SS22 scePadOpenExt** (WFIiSfXGUq8, libScePad). `int (int user_id, int type, int index, const void* param)`. As PadOpen
(controller.cpp:1220-1243) but the personal-port check accepts type 0, 1 or 2; same handle numbering; same 0x80920001
for bad args. Source: S Pad/PadExports.cs:91-96, 132-180 (typeAccepted :149-151). Ours: add next to
libs/controller.cpp:1205-1243, LIB_FUNC in libs/libPad.cpp:301-326. Test: (1000,1,0) -> 1, (1000,0,0) -> 1, (1000,3,0)
-> 0x80920001, (0xff,16,0) -> 1.

#### 17. KK25

- **KK25** register `lpMP8HhkBbg` → `LibKernel::PthreadAttrGetinheritsched` in O:Pthread block (3541);
  delete O:kernel/pthread.cpp:2175-2179 (`b20850a`). `int (const PthreadAttr*, int*)`: EINVAL for null,
  writes the stored value. Test: AttrInit, Get → 4 or 0 (whatever AttrInit stores), Set(0), Get → 0.

#### 18. KK10

- **KK10** O:kernel/fileSystem.cpp:713 and 838 → `if (file == nullptr || !file->opened ||
  !file->writable) return KERNEL_ERROR_EBADF;` (K:722, 940); the `EXIT_IF(!file->opened)` below becomes
  dead. Test: open read-only, `KernelWrite` and `KernelPwrite` == EBADF, file unchanged.

#### 19. SK06

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

#### 20. KS10

**KS10 Pad sample merge.** In GameController::AddState(index, state) (O controller.cpp:859): if s.states_num != 0 and
the newest sample `(first+num-1)%64` is unread (`!s.obtained[newest]`) and its `buttons` equal the new state's buttons,
overwrite that sample (and last_state) and return (K controller.cpp:524-535; our touch is outside the samples, so
compare buttons only). Test: feed 100 Axis events with no button change between two ReadStates -> one sample; press
a button, 100 axis events, release -> the press is still read.

#### 21. SK07

**SK07 Ult queue push never drops.** `libs/libUlt.cpp:441-451`: remove the capacity check (unbounded deque), keep the
copy; `capacity` stays informational. Source: sharpemu `Ult/UltExports.Sync.cs:518-560` (comment 518-520). Test:
data pool num_data=2, queue data_size=8; push 1,2,3; TryPop x3 -> 1,2,3 (today 3 is lost); 4th TryPop -> 0x80810008.

#### 22. KS05

**KS05 Json2 aliasing.** JsonValueSetObject (dFCphqnd+a4): build the copy of `value` first (parent = self), then
JsonValueClear(self), then attach (K:626-636). JsonObjectAssign (urOpESTBZmo): copy src into a new map, destroy self's
map, attach (K:987-996). Insert at O libs/libJson2.cpp:1033-1048 and :911-917. Test: object o with child "a" (object);
SetObject(o, o.a.object) and ObjectAssign(x, x) under ASan -> no use-after-free, contents preserved.

#### 23. KS04

**KS04 HttpCreateTemplate.** `tn.user_agent = user_agent != nullptr ? user_agent : "";` at O libs/network.cpp:584
(K network.cpp:469). Test (K tests/HttpUriParseTests.cpp TestTemplateWithoutUserAgent): Initialize, NetPoolCreate,
SslInit, HttpInit, HttpCreateTemplate(http, nullptr, 2, 1) > 0.

#### 24. SK08 (+KK14)

**SK08 guest printf.** `libs/guestPrintf.cpp`: in `case 's'` (696) if `p == nullptr` print "(null)" with width and
precision; if `FLAGS_LONG` is set, or the conversion is 'S', read `uint16_t` units up to 0 and emit UTF-8 (pair
surrogates; precision counts output characters); in `case 'c'` (676) with `FLAGS_LONG`, or 'C', take the argument as
one UTF-16 unit and emit UTF-8. Add `case 'S'`/`case 'C'`. Source: sharpemu `KernelMemoryCompatExports.cs:4543-4600`,
16-bit reader `5633-5700`, 179fcbb. Test (host, through `GetGuestSnprintfCtxFunc`): "%s" NULL -> "(null)"; "%ls"
u"abé" -> "ab\xc3\xa9"; "%S" same; "%lc" 0x41 -> "A"; "%5.1s" "xyz" -> "    x".

*Second source, KK14:* - **KK14** port K:guestPrintf.cpp:435-442 (template `_strnlen_s`) and 703-740 (`case 's'`); add the
  `u16string_view` overload of `Utf16ToUtf8` (K:common/stringUtils.h:166-172) or adapt ours (O:319).
  Test: `"%ls"` with u"hé" → "hé" (UTF-8); `"%.2ls"` with u"éé" → "é" (2 bytes).

#### 25. KA04

**KA04 AJM control job gapless** (7FZsbyVRM4U AjmBatchJobControl, Ajm). In `AjmControlInstance` (ours ajm.cpp:677-708)
before the RESET block insert KytyPS5 ajm.cpp:511-520: if `flags & AJM_FLAG_SIDEBAND_GAPLESS`: input null or shorter
than AJM_SIDEBAND_GAPLESS_SIZE -> result AJM_RESULT_INVALID_PARAMETER and return; `state->gapless.Set(input,
flags & AJM_FLAG_CONTROL_RESET)`; advance sideband_input/size by AJM_SIDEBAND_GAPLESS_SIZE. Constants exist in ours
(ajm.cpp:175, 182). Test: MP3 instance (FFmpeg MP3 decoder, CPU), control job flags SIDEBAND_GAPLESS with {total 1000,
skip 100} and sideband output GAPLESS: output echoes 1000/100; then INITIALIZE|SIDEBAND_GAPLESS on an Opus instance with
{gapless, opus init params} initializes with the init params (result OK, format 2 ch 48000).

#### 26. KA05

**KA05 AT9 RIFF data chunk.** In `AjmAt9Decoder::ParseRiffHeader` (ours ajm/atrac9_decoder.h:571-613) move the 'data'
branch (607-613) above the size check (575-578), as KytyPS5 ajm/atrac9_decoder.h:572-583. Test: synthetic RIFF/WAVE with
a 52-byte fmt chunk (0xFFFE, AT9 GUID, a 4-byte config built from LibAtrac9's public layout) and a 'data' chunk whose size
is 4096 while the job holds 200 bytes: ParseRiffHeader returns true with data_offset = payload instead of PARTIAL_INPUT.

#### 27. KS06 (+SS03)

**KS06 NetResolverDestroy.** NID kJlYH5uMAWI, Net lib. `int(int rid)`: if Network::ResolverDestroy(rid) false ->
NET_ERROR_EBADF, else OK; sets net errno on error (with KS07). Add `bool ResolverDestroy(int)` to O network.cpp:243
and implement after :447 as K network.cpp:311-319; Net:: wrapper as K :1445-1456; LibNet wrapper and LIB_FUNC in
O libs/libNet.cpp:189-219. Test: 33 x (Create, Destroy) all succeed; Destroy twice -> EBADF.

*Second source, SS03:* **SS03 sceNetResolverDestroy / sceNetResolverGetError** (kJlYH5uMAWI, J5i3hiLJMPk, libSceNet). `int Destroy(int rid)`:
valid id -> free the slot (m_resolvers[rid].used=false, name cleared), OK; else NET_ERROR_EBADF (sharp 0x80410109).
`int GetError(int rid, int* status)`: status null -> NET_ERROR_EINVAL (0x80410116); bad id -> EBADF; else *status =
resolver's last error (OURS keeps none: write 0), OK. Set the net errno as NET_CALL does. Source:
S Network/NetExports.cs:1245-1282. Ours: add Network::ResolverDestroy next to libs/network.cpp:423-446, wrappers in
libs/libNet.cpp near :114-121, LIB_FUNC in LIB_DEFINE(InitNet_1_Net) libs/libNet.cpp:189-224. Test: 40 x
(Create, Destroy) all succeed; 33 Creates without Destroy -> 33rd ENOSPACE; GetError(valid) writes 0.

#### 28. KS14 (+SS10)

**KS14 Delete busy.** In SaveDataDelete (S1GkePI17zQ, O :946): use del->title_id when non-null (validated, KS17);
if the dir is mounted (g_mount_slots.FindAvailable(dir_name)==BUSY, under g_mount_mutex) return SAVE_DATA_ERROR_BUSY
(K :1051-1056). Test: Mount3 "a", Delete "a" -> BUSY and files still there; Umount2, Delete -> OK.

#### 29. KS17

**KS17 SaveData input checks.** Add valid_path_component (K :286-297) and apply: Mount3 (O :612-614 -> PARAMETER instead
of EXIT; name check; user_id<0 -> INVALID_LOGIN_USER; on create, blocks outside 48..16384 -> PARAMETER, K :742-744 --
note our 0 means "unspecified" at O :672, keep 0 allowed or decide), TransferringMount, Delete (title and dir),
DirNameSearch (K :586-597: title_id name, NUL-terminated dir_name, dir_names_num w/o buffer, user_id), Setup/Get/Set
memory user_id. Test: Mount3 dir "../x" -> PARAMETER; Mount3(NULL) -> PARAMETER (no abort); user_id -1 -> INVALID_LOGIN_USER.

#### 30. KL03

**KL03 -- GetUserName without aborts**
- NID 1xxcMiGu2fo, `UserService::UserServiceGetUserName`, library UserService.
- Signature: `int (int user_id, char* name, size_t size)`.
- Behaviour: `name == nullptr` -> USER_SERVICE_ERROR_INVALID_ARGUMENT (0x80960005); user not logged in (KL04's check,
  or IsLocalUser if KL04 is not taken) -> USER_SERVICE_ERROR_NOT_LOGGED_IN (0x80960009); build our name "Kyty-N";
  `size <= strlen(name)` -> USER_SERVICE_ERROR_BUFFER_TOO_SHORT (0x8096000A); else copy with NUL, return OK. No writes
  on error.
- Port: KytyPS5 src/libs/libUserService.cpp @ dfec14a:113-132 (keep our name scheme; KL19 has theirs).
- Insertion: OURS libs/libUserService.cpp:116-127 (constants already in libs/errno.h:628-632).
- CPU-only test: (1000, buf, 16) -> OK "Kyty-1"; (1000, buf, 6) -> BUFFER_TOO_SHORT, buffer untouched;
  (0xFF, buf, 16) and (-1, ...) -> NOT_LOGGED_IN; (1000, nullptr, 16) -> INVALID_ARGUMENT. Today the 2nd-4th abort.

#### 31. SK09

**SK09 semaphore arguments.** `kernel/semaphore.cpp:135-150` `Signal`: `if (signal_count < 0) return
Result::InvalCount;` and compare `m_count > m_max_count - signal_count`; 260 `EXIT_NOT_IMPLEMENTED(sem == nullptr)` ->
`return KERNEL_ERROR_EINVAL`. (sharpemu also rejects a non-NULL opt with EINVAL at 54; not proposed.) Source: sharpemu
`KernelSemaphoreCompatExports.cs:379-392, 49-56`. Test: CreateSema(init 1, max 5); SignalSema(-1) -> 0x80020016 and
PollSema(1) still OK; SignalSema(INT_MAX) -> EINVAL; CreateSema(NULL,..) -> EINVAL.

#### 32. KK07

- **KK07** add `if (thread->free) return KERNEL_ERROR_ESRCH;` after the null checks in O:pthread.cpp:
  3765-3769 (Getprio), 3785-3787 (Setprio), 3664-3666 (Cancel). Source K:3410-3413, 3518-3520,
  3534-3537. Test: create, join, then Getprio/Setprio == `KERNEL_ERROR_ESRCH`.

#### 33. KK08

- **KK08** O:libs/libKernel.cpp:3055-3064: read `returned_fiber` (from `g_thread_return_fiber`),
  `arg_on_return` and the TERMINATED check into locals before `FiberCommitDeferredIdle()`; write
  `*arg_on_return` afterwards (K:2638-2650). Test: two host-created guest threads alternately
  `sceFiberRun` one fiber that returns its run argument + 1, 100k times; every run returns arg+1, OK.

#### 34. KA06

**KA06 sceAudioInInput** (LozEOU8+anM, AudioIn). `int AudioInInput(int handle, void* dest)`. Invalid handle ->
AUDIO_IN_ERROR_INVALID_HANDLE (unchanged); dest null -> return 0 without waiting (KytyPS5 stops the stream);
otherwise keep our block-time wait and `memset(dest, 0, samples_num * bytes_per_frame)` (2 for S16 mono, 4 for S16
stereo), return samples_num. Source audio.cpp:743-822 (silence 805-807, stop 808-811, return 822); ours export audio.cpp:1584-1596 (drop the
EXIT_NOT_IMPLEMENTED at 1587) and Audio::AudioInInput 1333-1352. Test: open a port, fill the buffer with 0xAA, input:
all zero, return 256; dest null returns 0.

#### 35. KA07

**KA07 sceAudioInOpen errors** (5NE8Sjc7VC8, AudioIn). Replace audio.cpp:1556-1557 with `if (type != 0 && type != 1)
return AUDIO_IN_ERROR_INVALID_TYPE; if (index != 0) return AUDIO_IN_ERROR_INVALID_PARAM;` and add `if (len == 0)
return AUDIO_IN_ERROR_INVALID_SIZE; if (freq == 0) return AUDIO_IN_ERROR_INVALID_FREQ;` (subset of KytyPS5
audio.cpp:1047-1058; codes 0x80260104/0x80260106/0x80260102/0x80260103 already in errno.h:353-365). Test: type 0 opens a
port; type 2 -> 0x80260104; index 1 -> 0x80260106; freq 0 -> 0x80260103; no abort.

#### 36. KA08

**KA08 Ngs2VoiceGetState custom racks** (-TOuuAQ-buE, Ngs2). In ours audio.cpp:3404-3465 replace the CustomMastering
case (3421-3430) with KytyPS5 ngs2.cpp:2795-2813 (a0b99a8): CustomMastering and CustomSampler read
`custom_rack_option.state_size`; `state_size < configured` -> 0x804a8011; memset `configured` bytes; mastering writes
state_flags; custom sampler writes state_flags (ours has no decode state; add Ngs2CustomSamplerVoiceState, 48 bytes,
KytyPS5 897-905, and fill flags only). Test: custom mastering rack (0x4003) with state_size 16; GetState with a 32-byte
buffer pre-filled 0xCC: OK, bytes 0-15 written, 16-31 unchanged; with 8 bytes -> 0x804a8011.

#### 37. KS13

**KS13 Get/SetParam.** GetParam (XgvSuIdnMlw, O :985): PARAMETER if param_type>5 or mount_point not NUL-terminated;
NOT_MOUNTED if g_mount_slots.Find fails; load our .param sidecar (save_data_load_param); type 0 whole struct
(size >= sizeof), 4 user_param (4 bytes), 5 mtime (8 bytes), 1..3 text field copied up to buf-1 bytes plus NUL;
*got_size = bytes written (K :126-139,1064-1118). SetParam (85zul--eGXs, O :1129): PARAMETER for null mount/buf,
type>4, size checks; NOT_MOUNTED; type 0 store whole struct; type 4 user_param; 1..3 replace that text field
(truncate to field-1, zero fill) then store (K :1282-1333); move the LOGF after the null check. Test: mount, SetParam
type 1 "abc", GetParam type 1 -> "abc", type 0 -> title "abc"; GetParam on "/savedata9" -> NOT_MOUNTED; SetParam(NULL buf) -> PARAMETER.

#### 38. KS15 (+SS04)

**KS15 TransferringMount.** WAzWTZm1H+I/RjMlsR8EXrw (O :850): PARAMETER if title_id null; mount
`_SaveData/<title_id>/<dir>`; NOT_FOUND when absent (no create); created flag 0 (K :934-970). Slot key: include the
title (e.g. key "<title>/<dir>") so another title's "data" does not collide with ours. Test: TransferringMount of a
missing dir -> NOT_FOUND and no directory created; existing -> OK, mount_result.mount_status 0.

*Second source, SS04:* **SS04 sceSaveDataTransferringMount** (WAzWTZm1H+I, RjMlsR8EXrw). Behaviour: title_id null or dir null -> PARAMETER;
path = _SaveData/<mount->title_id>/<dir>; if absent -> SAVE_DATA_ERROR_NOT_FOUND (no directory created); else mount it
read-only in a free slot (BUSY/MOUNT_FULL as Mount3), mount_status 0. Source: S SaveDataExports.cs:920-963 with
MountSaveData 825-918 (mode READ_ONLY); shadPS4 savedata.cpp:1685-1703. Ours: libs/libSaveData.cpp:850-883. Test: no dir
-> NOT_FOUND and no dir created; pre-created dir under another title id -> OK, /savedataN mounted.

#### 39. KS16

**KS16 GetMountInfo.** 65VH0Qaaz6s (O :1169): PARAMETER for null mount_point/info or non-terminated point;
NOT_MOUNTED when Find fails; else our sidecar blocks/free (K :1335-1358). Test: GetMountInfo("/savedata3") unmounted -> NOT_MOUNTED.

#### 40. SK05 (+KK35)

**SK05 guest path normalisation.** `kernel/fileSystem.cpp:333-398`. Add `static std::string NormalizeGuestPath(
std::string_view)`: split on '/', drop "" and ".", ".." pops one segment (never above root), rejoin with a leading '/'
(keep a trailing '/' for the directory form). Call it at the top of `GetRealFilename` and `GetRealDirectory` before the
mount search, and pick the matching `MountPair` with the longest `point` instead of the first (`find_if` 339-341,
380-382). Relative paths (no leading '/') unchanged (SK33). Source: sharpemu `KernelMemoryCompatExports.cs:5176-5203`
(segment walk), `5070-5110` (longest prefix), reasons 9ff60ab / e01092a. Difference to sharpemu: we normalise the whole
guest path (so `/app0/..` becomes `/`, no mount, ENOENT) instead of clamping inside the mount. Test: Mount(T, "/app0"),
Mount(D, "/download0"): "/app0/a/../b" -> T/b; "/app0/./c" -> T/c; "/app0/../etc/passwd" -> empty; "/app0/../download0/f"
-> D/f; overlapping mounts "/app0" and "/app0/sub" -> the longer wins.

#### 41. KK23 (+SK12)

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

*Second source, SK12:* **SK12 AIO poll/wait/cancel.** `libs/libKernel.cpp`, after `KernelAioDeleteRequest` (3375-3390), LIB_FUNCs next to
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

#### 42. KK21

- **KK21** `sceKernelPreadv` `yTj62I7kw4s`, `sceKernelWritev` `kAt6VDbHmro`, `sceKernelPwritev`
  `mBd4AfLP+u8`, libkernel. `int64_t (int d, const KernelIovec* iov, int iovcnt[, int64_t offset])`,
  `KernelIovec {void* iov_base; size_t iov_len;}` (16 bytes). Errors: iovcnt <0 or >1024, offset <0,
  total > INT_MAX → EINVAL; iov NULL with iovcnt>0 or base NULL with len>0 → EFAULT; d<3 / closed / not
  readable (preadv) / not writable (writev) → EBADF; socket → ESPIPE; directory → EISDIR; special on
  writev → EINVAL; returns bytes moved; p* variants restore the position; writev honours O_APPEND.
  Port K:fileSystem.h:36-42, fileSystem.cpp:822-921, 977-1056 (drop `DebugCounters`; add
  `File::readable` set in KernelOpen like K:467). Insert after O:kernel/fileSystem.cpp:878;
  register in FS block O:3430. Test: KytyPS5 TestSaveWritev (@dfec14a:764-838) + a preadv case.

#### 43. KK24 (+SK16)

- **KK24** `_umtx_op` `04AjkP0jO9U` (name per shadPS4 aerolib.inl:5665), InitLibKernel_1. `int (volatile
  void* obj, int op, uint64_t val, void* uaddr, const void* uaddr2)`; posix -1/errno. op 2: if `*(u64*)obj
  != val` return 0; else sleep until woken / changed / relative `timespec` in uaddr2 elapsed (EINVAL for
  a bad timespec, ETIMEDOUT); op 3: wake `val` waiters; other ops and `uaddr != NULL` → EINVAL (not
  EXIT). Port K:libKernel.cpp:2108-2138, syncOnAddress.cpp:50-61 (ns `MakeDeadline` with saturation),
  74 (`ceil`), 285-288, syncOnAddress.h:16-17. Insert after O:libs/libKernel.cpp:2191 and
  O:kernel/syncOnAddress.cpp:57-62, 293. Test: thread A `_umtx_op(&w, 2, 5, 0, &{0, 50ms})` → -1
  ETIMEDOUT after ≥50 ms; thread B sets w=6 and `_umtx_op(&w, 3, 1, 0, 0)` → A returns 0.

*Second source, SK16:* **SK16 _umtx_op.** `libs/libKernel.cpp` Posix namespace: `int _umtx_op(void* obj, int op, uint64_t val, void* uaddr,
void* uaddr2)`: uaddr != NULL -> -1/EINVAL (the `_umtx_time` form is not supported, as in sharpemu); op 2: uaddr2
NULL = infinite, else a relative `KernelTimespec` (tv_sec/tv_nsec range-checked -> EINVAL, converted to microseconds,
clamped to UINT32_MAX) -> `POSIX_CALL(SyncOnAddress::Wait64((volatile uint64_t*)obj, val, &us, signal poll))`; op 3:
`POSIX_CALL(SyncOnAddress::Wake(obj, (int32_t)val))`; other ops -> -1/EINVAL. Register 04AjkP0jO9U in
`InitLibKernel_1_Posix`. Source: sharpemu `KernelSyncOnAddressCompatExports.cs:209-282`. Test: thread A
_umtx_op(&w, 2, 0, 0, NULL) blocks; B sets w=1 and _umtx_op(&w, 3, 1, 0, 0) -> A returns 0; timeout 10 ms -> -1/60.

#### 44. KS27 (+SS23)

**KS27 Net socket exports.** NIDs OXXX4mUk3uk Connect, xphrZusl78E Getsockopt, beRjXBn-z+o Send, gvD1greCu0A Sendto,
9wO9XrMsNhc Recv, 304ooNZxWDY Recvfrom. Wrappers as K libNet.cpp:99-101,191-224 over our Net::Connect/Getsockopt/
Sendto/Recv/Recvfrom (O network.cpp:1895,2062,2133,2182,2186): clamp len to INT_MAX, FinishSocketCall (KS07). Check
whether our ConvertMessageFlags (O :1190) accepts the 0x20000 KytyPS5 ORs into Sendto before keeping it. LIB_FUNC in
O libNet.cpp:189-219. Test (Linux): NetSocket fails ENOSYS today, so call NetConnect(200, addr, 16) -> the
net error for EBADF (not 0) and sce_net_errno == 9; NetRecv likewise. On Windows: loopback connect/send/recv round trip.

*Second source, SS23:* **SS23 sceNetRecv / sceNetRecvfrom** (9wO9XrMsNhc, 304ooNZxWDY). `int64 Recv(int s, void* buf, uint64 len, int flags)`,
`int64 Recvfrom(int s, void* buf, uint64 len, int flags, void* addr, uint32_t* addrlen)`. Wrap Net::Recv/Recvfrom
(network.cpp:2182-2230) with an int64 variant of FinishSocketCall (libNet.cpp:70-78: negative -> map posix errno to
NET_ERROR, store in net errno, return it). Source: S Network/NetExports.cs:253-355 (flags 0x2 PEEK, 0x80 DONTWAIT
semantics). Ours: libs/libNet.cpp:80-104 + LIB_DEFINE :189-224. Test: two UDP sockets on 127.0.0.1 via NetSocket/NetBind;
host sendto; NetRecvfrom returns the bytes and the sender address; NetRecv on an empty non-blocking socket -> EAGAIN code.

#### 45. KS26 (+SK10)

**KS26 select files.** Add `bool IsOpenDescriptor(int)` to O kernel/fileSystem (GetFile(d) && opened; K a875d1b
fileSystem.cpp:413-416). In O Net::Select (network.cpp:2241) before the platform branch: for each fd in 0..nfds with a
read/write bit that is not a socket and is an open descriptor, remember it as ready; on Linux, if every requested fd is
such a file, zero the sets, set those bits and return the count; if a socket is also requested keep ENOSYS (until KS38).
Bad fd -> EBADF (K test). Test (K tests/KernelFileSystemTests.cpp TestRandomDevices): open /dev/urandom, select with read+write
bits, NULL timeout -> 2 and both bits set; after close -> -1/EBADF.

*Second source, SK10:* **SK10 select sleep idiom on Linux.** `libs/network.cpp:2360-2363` (`#else` of `Select`): before ENOSYS, if no guest fd
< nfds in the three sets is a known socket (`GetSocketBackend`), sleep the timeout (signal-polled, as `KernelUsleep`
does), zero the three sets (`GuestFdZero`) and return 0; a NULL timeout with no fds keeps today's ENOSYS. Source: our
Windows branch 2318-2329. Test: select(0, NULL, NULL, NULL, {0, 20000}) returns 0 after ~20 ms.

#### 46. KK11

- **KK11** O:kernel/fileSystem.cpp after 948: `if (std::strcmp(path, "/") == 0) { *sb = {};
  sb->st_mode = 0040777u; return OK; }` (K:1130-1134). Test: KytyPS5 tests @dfec14a:1121-1122.

#### 47. KK12

- **KK12** `_write` `FxVZqBAA7ks` and posix `write` `FN4gaPmuFV8` (both → `LibKernel::write`, O:2491,
  3666, 3738). `int64_t (int d, const void* buf, size_t nbytes)`: keep ours' `d < 0` EBADF and socket
  branch, then `return POSIX_N_CALL(FileSystem::KernelWrite(d, buf, nbytes));` for every other d (drop
  the fd 0-2 swallow at O:1474-1477). Source K:1363-1365 (`e0c5ae0`). Test: redirect host stdout to a
  pipe, write(1, "x\n", 2) == 2 and the pipe receives it; write(0, ..) == -1 errno EBADF.

#### 48. KK13

- **KK13** O:libs/guestPrintf.cpp:528 → `if (prec < 0) { flags &= ~FLAGS_PRECISION; } else {
  precision = prec; }` (K:530-535). Test: guest-printf ctx `"%.*s|"`, -1, "abc" → "abc|"; 0 → "|".

#### 49. KK15

- **KK15** O:kernel/eventQueue.h add `KERNEL_EVFILT_AMPR = -25`; O:eventQueue.cpp:272-274 return it
  when switch `KYTY_BC5_AMPR_FILTER` (default off until a box run) is set. Source K:eventQueue.h:21,
  eventQueue.cpp:570, 598. Test: add user event id 7 and AMPR event id 7 on one queue, trigger AMPR:
  wait returns one event with filter -25, the user event stays untriggered.

#### 50. KK16

- **KK16** O:kernel/fileSystem.cpp:1137-1148 add `file_too_large → EFBIG`, `no_space_on_device →
  ENOSPC` (K:1288-1290). Test: map a synthetic `std::error_code(ENOSPC, generic_category())`.

#### 51. KK17

- **KK17** O:libs/libDbgAsan.cpp: `Shadow::count` → `covered_bytes`, add `ShadowCoverage`, port
  K:libDbgAsan.cpp:40-129 into AllocShadow/FreeShadow. Test: `KernelAlloc(base, 0x100000)`, free
  `[base, base+0x40000)`; the shadow page for `base+0x7ffff` is still mapped (read it), free the rest:
  unmapped (K:139-145 has a test hook).

#### 52. KK18

- **KK18** O:kernel/fileSystem.cpp:1019 branch: `stat.st_mode = 0020644u;` (K:1202). Test: fstat of
  an open /dev/urandom → `(st_mode & 0170000) == 0020000`.

#### 53. KK20 (+KL07)

- **KK20** O:libs/libKernel.cpp:1364 `return KERNEL_ERROR_ESRCH;` (K:1275). Test: resolve `QKd0qM58Qes`,
  call with handle 0x7fff, flags 0 → `KERNEL_ERROR_ESRCH`.

*Second source, KL07:* ### KL07 -- StopUnloadModule bad handle
- NID QKd0qM58Qes, `LibKernel::KernelStopUnloadModule`, library libkernel.
- Signature: `int (KernelModule handle, size_t args, const void* argp, uint32_t flags, const KernelUnloadModuleOpt*
  opt, int* res)`.
- Behaviour: `FindProgramById(handle) == nullptr` -> return KERNEL_ERROR_ESRCH (0x80020003), `*res` untouched.
- Port: KytyPS5 src/libs/libKernel.cpp @ dfec14a:1272-1276.
- Insertion: OURS libs/libKernel.cpp:1362-1365.
- CPU-only test: call with handle 0x7fff and flags 0, opt nullptr -> ESRCH (today OK). No module needed.

#### 54. KK26

- **KK26** posix `pthread_attr_setstack` `-SrbXpGR1f0`: add in O:kernel/pthread.cpp near 4546
  `int pthread_attr_setstack(LibKernel::PthreadAttr* attr, void* addr, size_t size) { return
  POSIX_PTHREAD_CALL(LibKernel::PthreadAttrSetstack(attr, addr, size)); }` + declaration in pthread.h;
  register in O:Posix block (2387). Source K:pthread.cpp:4272-4274, libKernel.cpp:2179. Test: set a
  1 MiB host buffer, `pthread_attr_getstack` returns it; create a thread and check its rsp is inside.

#### 55. KK27

- **KK27** `sceKernelGetAvailableCpumask` `La9uyZv4Kvw`, InitLibKernel_1, `uint64_t (void)`, returns
  0x1FFF (K:1768-1772). Test: resolve and call → 0x1FFF.

#### 56. KK28

- **KK28** `sceKernelClearVirtualRangeName` `mkgXxsoxWHg`, Mem block (O:3453), `int (const void* addr,
  uint64_t len)`: same as ours' Set with name "" (O:kernel/memory.cpp:2630-2632) under
  `g_memory_operation_mutex`, returns OK (K:memory.cpp:1893-1907). Coordinate with the memory agent.
  Test: map flexible memory, Set name "x", Clear, VirtualQuery name == "".

#### 57. KK36

- **KK36** O:kernel/fileSystem.cpp after 483: `file->close_on_exec = (static_cast<uint32_t>(flags) &
  0x00100000u) != 0;` (K:471). Test: KytyPS5 TestFileDescriptorFlags (@dfec14a:367-394).

#### 58. SK13 (+KK22)

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

*Second source, KK22:* - **KK22** `sceKernelFtruncate` `VW3TVZiM4-E` → `FileSystem::KernelFtruncate` in O:FS block (3430).
  `int (int d, int64_t length)`; behaviour already at O:kernel/fileSystem.cpp:1064-1105 (EBADF,
  EINVAL for <0/socket/dir/special, EIO). Test: write 10 bytes, ftruncate 4, fstat size 4.

#### 59. SK14

**SK14 condattr getters/pshared.** `kernel/pthread.cpp`: add `int pshared = 0` to `PthreadCondattrPrivate` (502-506);
posix `pthread_condattr_getclock(const PthreadCondattr* attr, KernelClockid* clock)`: attr/*attr/clock NULL -> 22, else
`*clock = (*attr)->clock_id`, 0; `pthread_condattr_getpshared(attr, int* v)` same with `pshared`;
`pthread_condattr_setpshared(attr, int v)`: v not 0 (PRIVATE) or 1 (SHARED) -> 22, else store, 0. Register cTDYxTUNPhM /
h0qUqSuOmC8 / 3BpP850hBT4 next to EjllaAqAPZo (`libs/libKernel.cpp:3632`). Source: sharpemu `KernelPthreadCompatExports
.cs:668-712, 1372-1416`. Test: init attr, setclock(4), getclock -> 4; setpshared(2) -> 22; getpshared -> 0.

#### 60. SK15

**SK15 signal masks.** `libs/libKernel.cpp:476`: replace the body of `LibKernel::sigprocmask(int how, const void* set,
void* oset)` with: `thread_local uint8_t mask[16]`; if set != NULL and how not in 1..3 -> errno 22, -1; if oset write
the 16 current bytes first; if set: 1 = OR, 2 = AND-NOT, 3 = copy; return 0. Bind aPcyptbOiZs to the same function.
New `int sigfillset(void* set)`: NULL -> errno 14, -1; else 16 x 0xFF, 0 -> VkTAsrZDcJ0. The mask is state only (this
tree raises no guest signals). Source: sharpemu `KernelRuntimeCompatExports.Signals.cs:13-49`, 8ddf660. Test:
sigfillset(&s); sigprocmask(3, &s, NULL); sigprocmask(1, NULL, &o) -> o all ones; how 7 -> -1/22.

#### 61. SK17

**SK17 Ult queue pop/try-push/destroy, pool destroy.** `libs/libUlt.cpp`: add `std::condition_variable cv` to
`UltQueueState` (67-74) and `bool alive`; Push (428) notifies; new `UltQueuePop(void* queue, void* data)` = TryPop that
waits on `cv` until non-empty or `!alive` (-> ULT_ERROR_STATE); `UltQueueTryPush` = Push; `UltQueueDestroy(void*
queue)`: NULL -> ULT_ERROR_NULL, unknown -> ULT_ERROR_INVALID (0x80810004), else mark !alive, notify_all, erase;
`UltWaitingQueueResourcePoolDestroy` / `UltQueueDataResourcePoolDestroy(void* pool)`: NULL -> NULL error, unknown ->
INVALID, else erase from `g_ult_resource_pools` / `g_ult_queue_data_pools`. Register RVSq2tsm2yw, 6Mc2Xs7pI1I,
PP9nZxpSKLY, or55417wcDk, dh11uAUWNyM in `InitUlt_1` (710). Source: sharpemu `Ult/UltExports.Sync.cs:167-190,
499-516, 518-620`. Test: consumer thread blocks in QueuePop; producer pushes 0x55 -> consumer gets it; Destroy with a
blocked popper wakes it with an error; destroy of an unknown pool -> 0x80810004.

#### 62. SK18

**SK18 Ult mutex try-lock/destroy/owner.** `libs/libUlt.cpp:39-42`: add `std::thread::id owner` and `uint32_t depth`
to `UltMutexState`, set in Lock (534) after `lock()`, cleared when depth reaches 0 in Unlock (552); Unlock when
`owner != this_thread` -> 0x80810005 (no `unlock()` call, removes the UB); new `UltMutexTryLock(void*)`: `try_lock()`
-> OK (update owner/depth) else ULT_ERROR_BUSY (0x80810007); new `UltMutexDestroy(void*)`: NULL -> NULL error, unknown
-> ULT_ERROR_INVALID, owned -> ULT_ERROR_BUSY, else erase. Recursion stays (SK31). Register jOsUG0BJI-Y, jW+HnafeS3Y.
Source: sharpemu `Ult/UltExports.Sync.cs:214-320`, codes `Ult/UltExports.cs:8-12`. Test: A locks; B TryLock -> BUSY;
B Unlock -> 0x80810005; A Destroy while locked -> BUSY; A unlock; Destroy -> OK.

#### 63. SK19

**SK19 Ult aliases.** `libs/libUlt.cpp` `InitUlt_1` (710-733): `LIB_FUNC("RlN-xQPtYnM", UltUlthreadCreate)`,
`LIB_FUNC("81ag9-mItVY", UltUlthreadRuntimeCreate)`, `LIB_FUNC("7+pdaXR9jWw", UltUlthreadRuntimeOptParamInitialize)`;
new `int UltUlthreadOptParamInitialize(void* p, uint32_t build)`: NULL -> ULT_ERROR_NULL, else zero 128 bytes (same as
the runtime opt param, 150-163) -> V89UhsfEhJk, vIuen2qlRmo. Source: sharpemu `Ult/UltExports.cs:104-160, 216-231`
(both NIDs on one method each). Test: call the new NIDs' functions; runtime create + ulthread create + join returns the
entry's status.

#### 64. SK20

**SK20 bzero/htons.** Posix namespace: `void bzero(void* p, size_t n) { if (p && n) memset(p, 0, n); }` and
`uint16_t htons(uint16_t v) { return (v << 8) | (v >> 8); }`; register 9oiX1kyeedA, jogUIsOV3-U in
`InitLibKernel_1_Posix`. Source: sharpemu `KernelSocketCompatExports.cs:738-755, 797-806` (its bzero takes an int
length; use size_t). Test: htons(0x1234) == 0x3412; bzero of 8 bytes.

#### 65. SK21

**SK21 sceLibcHeapGetTraceInfo.** `libs/libC.cpp:658-665`: return `int`; `info == nullptr || info->size != 32` ->
`KERNEL_ERROR_EINVAL`; else fill as now and return 0. Source: sharpemu `LibcInternalExports.cs:25-52`. Test: size 16 ->
error, no exit; size 32 -> 0 and both pointers set.

#### 66. KL04

**KL04 -- UserService login set**
- NIDs (UserService): yH17Q6NWtVg UserServiceGetEvent; bwFjS+bX9mA and qbwy0Ub8b3M UserServiceGetUserNumber;
  1xxcMiGu2fo GetUserName; -sD02mFDBh4 GetGamePresets; woNpu+45RLk GetAgeLevel; rnEhHqG-4xo, ZKJtxdgvzwg,
  qWYHOFwqCxY, -3Y5GO+-i78, hD-H81EN9Vg, O6IW1-Dwm-w accessibility getters.
- Behaviour: hoist the `logged_in` count of GetLoginUserIdList (KYTY_BC5_LOGIN_USERS, 1..4, default 1) into one
  shared static; `IsLoggedIn(user_id)` = ControllerIndexFromUserId(user_id) in [0, logged_in). GetEvent: emit
  `{Login, LOCAL_USERS[i]}` for i < logged_in once each, then USER_SERVICE_ERROR_NO_EVENT (KytyPS5 additionally emits
  Logout/Login on pad disconnect/connect, 75-93 -- optional, ties to our pad-slot code). Every per-user getter uses
  IsLoggedIn -> NOT_LOGGED_IN otherwise. GetUserNumber: `*number = index + 1`.
- Port: KytyPS5 src/libs/libUserService.cpp @ dfec14a:44-51, 75-93, 134-148.
- Insertion: OURS libs/libUserService.cpp:24-30, 78-92, 94-113, 129-141 and the getters at 144-280.
- CPU-only test: env unset: GetEvent -> Login 1000, then NO_EVENT; GetUserNumber(1001) -> NOT_LOGGED_IN;
  GetLoginUserIdList -> {1000,-1,-1,-1}. With KYTY_BC5_LOGIN_USERS=2 (fresh process): two Login events,
  GetUserNumber(1001) -> 2.

#### 67. KL05

**KL05 -- language parameter 400**
- NID fZo48un7LK4, `SystemService::SystemServiceParamGetInt`, library SystemService.
- Signature: `int (int param_id, int* value)`.
- Behaviour: `case 400` shares the PARAM_ID_LANG branch (our host-input SystemLanguage, else --console-language).
- Port: KytyPS5 src/libs/libSystemService.cpp @ dfec14a:34, 118-119.
- Insertion: OURS libs/libSystemService.cpp:34 (constant) and 114-118 (case).
- CPU-only test: ParamGetInt(400,&v) == OK and v == the value of ParamGetInt(1,&w); with --console-language 1, v==1
  (today 0).

#### 68. KL06

**KL06 -- Sysmodule load state**
- NIDs (Sysmodule): g8cM39EUZ6o SysmoduleLoadModule `int(uint16_t id)`; eR2bZFAAU0Q SysmoduleUnloadModule
  `int(uint16_t)`; hHrGoGoNf+s SysmoduleLoadModuleInternalWithArg `int(uint16_t,int,int,int,int* ret)`;
  fMP5NHUOaMk SysmoduleIsLoaded `int(uint16_t)`.
- Behaviour: mutex-guarded `unordered_map<uint16_t, {uint32 refs}>`. Load: present -> ++refs, else insert refs=1;
  return 0. LoadModuleInternalWithArg: `*ret = Load(id); return *ret` (keep our EXIT_IFs on arg1-3). Unload: absent
  -> 0x805A1001 (SYSMODULE_ERROR_UNLOADED); refs==1 -> erase; else --refs; return 0. IsLoaded: present -> 0 else
  0x805A1001. Leave out KytyPS5's native-module table (0x0115) and the FATAL 0x805A10FF path: our boot preload already
  loads that PRX.
- Port: KytyPS5 src/libs/libSysmodule.cpp @ dfec14a:24-59, 65-118.
- Insertion: OURS libs/libSysmodule.cpp:18-63 (LIB_DEFINE 67-73 unchanged).
- CPU-only test: IsLoaded(0x80)==0x805A1001; Load==0; IsLoaded==0; Load==0; Unload==0; IsLoaded==0; Unload==0;
  IsLoaded==0x805A1001; Unload==0x805A1001.

#### 69. KL10

**KL10 -- stack walk hardening**
- NIDs: none.
- Behaviour: in StackwalkX86 per frame: require frame >= window start and frame <= window end - 16,
  `IsReadableRange(frame, 16)`, return address in code range; record it; stop if `frame->next <= frame`. Bounds as in
  WalkGuestStack (window 1 MiB from rsp). RuntimeLinker::StackTrace takes (rbp, rsp) and libC passes rsp.
- Port: KytyPS5 src/loader/runtimeLinker.cpp @ dfec14a:544-577, 1522-1537; src/libs/libC.cpp @ dfec14a:225.
- Insertion: OURS loader/runtimeLinker.cpp:716-758 (IsReadableRange is defined at 761: add a forward declaration as
  KytyPS5 does at 549), 2062-2066, runtimeLinker.h:186; libs/libC.cpp:233.
- CPU-only test: expose StackwalkX86 (test hook; it already takes the window and code range as parameters); mmap 2
  pages, mprotect the second PROT_NONE; frame A in page 1 with ret in range and next -> page 2: expect depth 1 and no
  signal (today SIGSEGV). Frame with next == itself: expect depth 1 (today 20 duplicates).

#### 70. KL11

**KL11 -- x64 trap emulation fixes**
- NIDs: none. Ours links Zydis on every platform (CMakeLists.txt:372).
- RDPID: decode `F3 [REX] 0F C7 /7` with mod=11 (or Zydis mnemonic RDPID); dest = rm | REX.B<<3; value = TSC_AUX from
  `rdtscp` (ECX), only if CPUID 0x80000001 EDX bit 27; write zero-extended into the 64-bit GPR; RIP += 4 (+1 with REX);
  otherwise return false. KytyPS5 x64InstructionEmulator.cpp @ dfec14a:651-661, 674-697.
- SSE4a register forms: `66 [REX] 0F 79 /r` EXTRQ xmm(reg), xmm(rm): len = rm.q0[7:0], idx = rm.q0[15:8], dest.q0 =
  ExtractBitField, dest.q1 = 0; `F2 [REX] 0F 79 /r` INSERTQ: controls from rm.q1, dest.q0 = InsertBitField(dest.q0,
  rm.q0, len, idx); RIP += 4 (+REX). KytyPS5 585-649.
- CLWB: Zydis-decode `66 0F AE /6` memory form, compute the address from the saved GPRs (keep FS/GS segment), CLFLUSH
  it, RIP += length. KytyPS5 663-672, 698-711.
- Insertion: OURS loader/x64InstructionEmulator.cpp:975-981 and 657-662 (RDPID), 802-859 and 500-556 (SSE4a), add
  CLWB next to TryEmulateCacheFlush 983-989 / 664-669 and to the TryEmulate chains 1010-1027.
- CPU-only test: build a ucontext_t (Linux) with fpregs pointing at a local `_libc_fpstate`, RIP at a byte buffer;
  `F3 0F C7 F9` -> RCX == TSC_AUX, RAX untouched, RIP+4; `F3 41 0F C7 F8` -> R8, RIP+5; `66 0F 79 C1` and
  `F2 0F 79 C1` against ExtractBitField/InsertBitField references, RIP+4; `66 0F AE 30` with RAX -> a buffer: true,
  RIP+4.

#### 71. KL12 (+SS06)

**KL12 -- notice-screen skip flag**
- NID 3RQ5aQfnstU, `SystemService::SystemServiceGetNoticeScreenSkipFlag`, library SystemService.
- Signature: `int (bool* value)`.
- Behaviour: null -> SYSTEM_SERVICE_ERROR_PARAMETER (already); `*value = Config::SkipNoticeScreen()`; OK. New bool
  `skip_notice_screen` (default false) in ConfigOptions, getter, and flag `--skip-notice-screen` in main.cpp.
- Port: KytyPS5 src/libs/libSystemService.cpp @ dfec14a:231-241; src/common/emulatorConfig.h:101, 172;
  emulatorConfig.cpp:236-238; src/main.cpp:110, 232.
- Insertion: OURS libs/libSystemService.cpp:241; common/emulatorConfig.h ConfigOptions (~66) and getters (~163-186);
  main.cpp simple-flag block 169-205.
- CPU-only test: config without the flag -> false; with it -> true; nullptr -> 0x80A10003.

*Second source, SS06:* **SS06 notice-screen skip flag** (Q3utJvma4Mo set, 3RQ5aQfnstU get, libSceSystemService). `int Set(int flag)` stores
flag != 0 (atomic); `int Get(bool* v)` writes it (one byte), PARAMETER on null. Source: S
SystemService/SystemServiceExports.cs:62-107 (eb252af). Ours: libs/libSystemService.cpp:234-256. Test: Get -> 0; Set(1);
Get -> 1; Set(0); Get -> 0.

#### 72. KA09

**KA09 AJM AAC RAW channels.** In ours ajm/aac_decoder.h: constructor takes `max_channels` (store m_max_channels, base
channels 0), Initialize resets channels and m_raw_configured and sets the sample rate from the index (KytyPS5 97-101);
remove the open-time extradata block (ours 191-210); on the first raw packet attach AV_PKT_DATA_NEW_EXTRADATA with
object type 2, the frequency index and channels = 2 if the first element is a CPE (`packet[0] >> 5 == 1`) else
clamp(max_channels, 1, 8) (KytyPS5 298-316); TOO_MANY_CHANNELS (add `AJM_RESULT_TOO_MANY_CHANNELS = 0x40`, KytyPS5
decoder.h:82) when the decoded frame has more channels than the limit (KytyPS5 210-213). Test: encode one stereo raw
AAC-LC frame with FFmpeg on the laptop (fixture), decode through an 8-channel AAC instance with config_number 2:
output 2 channels, 1024 samples, result OK; through a 1-channel instance: TOO_MANY_CHANNELS.

#### 73. KA10

**KA10 sceAudioOut2PortSetAttributes** (8XTArSPyWHk, AudioOut2). `int AudioOut2PortSetAttributes(port, attrs, num)`.
Under g_audioout2_port_mutex: attrs null with num != 0 -> INVALID_PARAM (0x80268001); port not found ->
AUDIO_OUT2_ERROR_INVALID_PORT (0x80268009, add constant); loop: ids other than 0 (PCM), 1 (GAIN), 8 (AMBISONICS) are
skipped; a repeated id -> INVALID_PARAM; value null -> INVALID_PARAM; PCM with value_size < sizeof(AudioOut2Pcm) ->
INVALID_PARAM; GAIN/AMBISONICS accepted and ignored until KA39/KA40; store the PCM pointer as today. Source
libAudio2.cpp:803-848 and 872-883 (PCM part); ours libAudio2.cpp:816-841. Test (no devices): create user, context,
port; null attrs num 1 -> 0x80268001; bogus port -> 0x80268009; two PCM entries -> 0x80268001; valid PCM -> OK.

#### 74. KA11

**KA11 AudioOut2 user handles** (xywYcRB7nbQ UserCreate, IaZXJ9M79uo UserDestroy, JK2wamZPzwM PortCreate; AudioOut2).
Keep a user list under a mutex (KytyPS5 libAudio2.cpp:235); UserCreate: null -> INVALID_PARAM, else next handle,
push (916-927); UserDestroy: not in list -> INVALID_PARAM, a used port with that user -> BUSY 0x80268007, else erase
(929-945); PortCreate: user not in list -> INVALID_PARAM (712-716) and store `port->user`. Ours libAudio2.cpp:874-888,
713-797 (AudioOut2PortParam.user_handle exists at 53). Test: PortCreate with handle 999 -> 0x80268001; UserDestroy while a
port exists -> 0x80268007; after PortDestroy -> OK; UserDestroy again -> 0x80268001.

#### 75. KA12

**KA12 AvPlayer NV12 padding** (inside o3+RWnHViSg AvPlayerGetVideoData). Replace ours avPlayer.cpp:1519 with KytyPS5
avPlayer.cpp:1556-1561: luma bytes [0, pitch*h) = 0 if `codecpar->color_range == AVCOL_RANGE_JPEG` else 16; chroma
[pitch*h, pitch*h*3/2) = 128 (keep zeroing any tail beyond that if `size` is larger). Test: factor the copy into a helper;
an NV12 AVFrame 6x4 into pitch 16: columns 6-15 of every luma row are 16, chroma padding 128; full-range frame: luma 0.

#### 76. KA13

**KA13 AvPlayer callback IO** (inside KMcEa+rHsIo AvPlayerAddSource). In FileStreamer (ours avPlayer.cpp:567-620):
Read returns AVERROR(EIO) when the callback returns more than `len` (KytyPS5 636-638; keep our AVERROR_EOF for 0); Seek
masks AVSEEK_FORCE, computes base+offset without overflow, EINVAL for unknown whence (KytyPS5 642-667; keep our clamp to
size); 64 KiB AVIO buffer and av_free on avio_alloc_context failure (607-616). Test: fake callbacks; read callback
returning len+1 -> AVERROR(EIO); Seek(100, SEEK_SET | AVSEEK_FORCE) -> 100; Seek(-1, SEEK_SET) -> negative.

#### 77. KA14

**KA14 sceAjmBatchInitialize** (MmpF1XsQiHw, Ajm). Replace ours ajm.cpp:879-880 EXIT_NOT_IMPLEMENTED with `if (buffer
== nullptr || info == nullptr) return AJM_ERROR_INVALID_PARAMETER;` (KytyPS5 ajm.cpp:724-726). Test: null buffer ->
error code, no abort.

#### 78. KA15

**KA15 libFont OTTO.** Add `(data[0]=='O' && data[1]=='T' && data[2]=='T' && data[3]=='O')` to ours libFont.cpp:747-748
(KytyPS5 libFont.cpp:741). Check our 3rdparty stb_truetype is >= 1.20 (CFF). Test: open an OFL CFF .otf from memory
(KXUpebrFk1U FontOpenFontMemory), render 'A': non-empty glyph bitmap from the font, not the fallback.

#### 79. KA16

**KA16 AudioOut2 exact drain** (aII9h5nli9U ContextPush, R7d0F1g2qsU GetQueueLevel, PE2zHMqLSHs Advance). Add
`audioout2_clock() = KernelGetProcessTime() * 6`; in audioout2_update_context_locked use `grain = num_grains * 125`
ticks and `last_update += drained * grain`; set last_update with audioout2_clock() in ContextCreate and Push. Source
7ff8aff (libAudio2.cpp:277-280, 346-371, 558, 643); ours libAudio2.cpp:353-380, 497, 632 (audioout2_grain_micros stays
for the sleep). Test: factor the drain into a pure function of (queued, last_update, now); at 512 grains, 3600 s of
ticks drains exactly 337500 grains (the old 10666-us grain gives 337521).

#### 80. KA29

**KA29 sceAudioOutGetSystemState** (R5hemoKKID8, AudioOut). `int AudioOutGetSystemState(AudioOutSystemState* s)`,
`struct {float loudness; uint8_t reserved8[4]; uint64_t reserved64[3];}` (32 bytes). Null -> AUDIO_OUT_ERROR_INVALID_POINTER
(0x80260004); else `*s = {}`; OK. Source audio.cpp:844-848, 961-972, audio.h decl, libAudio.cpp:134. Ours: struct and
function after AudioOutGetPortState (audio.cpp:1479), declare in audio.h, LIB_FUNC in libAudio.cpp:121-130. Test:
0xFF-filled struct comes back all zero; null -> 0x80260004.

#### 81. KA30

**KA30 sceAudioInClose** (Jh6WbHhnI68, AudioIn). `int AudioInClose(int handle)`: handle <= 0 or not open ->
AUDIO_IN_ERROR_INVALID_HANDLE (0x80260101); else `port = {}` under m_mutex; OK. Source audio.cpp:717-729, 1096-1103.
Ours: Audio::AudioInClose next to AudioInValid (audio.cpp:1326), export after AudioInInput (1596), LIB_FUNC in
libAudio.cpp:178-181. (KytyPS5's BUSY while an input runs needs a busy flag; optional.) Test: open 8 ports, close one,
the 9th open succeeds; closing twice -> 0x80260101.

#### 82. KA31 (+SS51)

**KA31 sceAudioInGetSilentState** (BohEAQ7DlUE, AudioIn). `int AudioInGetSilentState(int handle)`: invalid ->
0x80260101; else 0x1 (AUDIO_IN_SILENT_STATE_DEVICE_NONE, KytyPS5 audio.cpp:38) because ours has no capture device.
Source audio.cpp:731-741, 1115-1125. Insertion as KA30. Test: open port -> 1; bad handle -> 0x80260101.

#### 83. KA32

**KA32 sceAudioInHqOpen** (nya-R5gDYhM, AudioIn). Same signature as AudioInOpen; apply KA07 checks, then len != 128 ->
INVALID_SIZE, freq != 48000 -> INVALID_FREQ (KytyPS5 1053-1058 with asynchronous = true), then the AudioInOpen path
(KytyPS5 1090-1094). Insertion as KA30. Test: (len 128, 48000) returns a handle that KA06/KA30/KA31 accept; len 256 ->
0x80260102.

#### 84. KA33

**KA33 sceAudioOut2UserGetSupportedAttributes** (iE8trxPKnAg, AudioOut2). `int (AudioOut2UserHandle h, uint32_t*
ctx_attrs, uint32_t* port_attrs)`: either pointer null -> INVALID_PARAM; h not in the KA11 list -> INVALID_PARAM;
`*ctx_attrs = 0; *port_attrs = 1u << 0` (PCM; add GAIN bit 1 and AMBISONICS bit 8 only with KA39/KA40). Source
libAudio2.cpp:947-963, libAudio.cpp:162. Ours after UserDestroy (libAudio2.cpp:888), declare in audio.h, LIB_FUNC in
libAudio.cpp:139-170. Test: valid user -> 0/1; unknown -> 0x80268001.

#### 85. KA34

**KA34 Ngs2SystemGetInfo/Lock/Unlock** (vU7TQ62pItw, gThZqM5PYlQ, JXRC5n0RQls; Ngs2). Add `Ngs2FindSystem` over
g_ngs_list (KytyPS5 ngs2.cpp:965-972); Lock/Unlock: unknown handle -> 0x804a8201, else ngs->mutex.Lock()/Unlock()
(recursive Common::Mutex, so VoiceControl inside a lock is safe), OK (2901-2925). GetInfo(handle, info, size): info null
-> 0x804a8010; size != 184 -> 0x804a8011; unknown -> 0x804a8201; fill name, handle, buffer_info, uid, min grain 64, max
grain, state_flags 1, render_count, rack_count, sample_rate, num_grain_samples (1182-1221, struct 179-193). Ours: add
buffer_info, uid, render_count to Ngs2Internal (audio.cpp:2375), set them in Ngs2CreateSystemInternal, `++render_count`
in SystemRender; register in libAudio.cpp:1089-1116; delete the three stubs and their LIB_FUNCs from libNgs2.cpp
(120-163, 243, 245, 251) so only one record exists. Test: create system, GetInfo -> uid > 0, rack_count after one
RackCreate = 1, render_count increments per SystemRender; Lock on another thread blocks SystemRender until Unlock.

#### 86. KA35

**KA35 JpegEnc** (o6ZgXfFdWXQ, K+rocojkr-I, QbrU0cUghEM, j1LyMdaM+C0; JpegEnc). Copy KytyPS5 libJpegEnc.cpp:1-240
(QueryMemorySize returns the context size 8 or a create-param error; Create validates this_size 8/attribute 0 and
writes a magic-tagged handle; Encode validates format/size/sampling, converts RGBA/BGRA/YUYV/Y8 and writes the JPEG
through stb_image_write, returns the byte count or DATA_OVERFLOW 0x80650110 and fills output_info; Delete clears the
magic) as a new file and delete ours libJpeg.cpp:20-46 (same NIDs). stb_image_write.h is in KytyPlus 3rdparty/stb
(refs/Coder787-source_KytyPlus); STBIWDEF static inline keeps the instance private. Test (model: KytyPS5
tests/JpegEncTests.cpp): encode a 16x16 RGBA gradient, decode with stb_image, mean error small; jpeg_mem_size 10 ->
0x80650110; bad handle -> 0x80650104.

#### 87. KA36 (+SS40)

**KA36 sceFontGetKerning** (sDuhHGNhHvE, Font). `int FontGetKerning(FontHandle, uint32_t pre_code, uint32_t code,
FontKerning* k)`, `FontKerning {float offset_x, offset_y, position_x, position_y}` (16 bytes): k null ->
0x80460002; zero k; handle null -> 0x80460005; pre_code 0 or no stb font -> OK; glyph ids (code with bit 31 = glyph
index) out of range -> 0x80460041; offset_x = stbtt_GetGlyphKernAdvance * scale. Source libFont.cpp:85-87, 128-135,
2058-2091, 2264. Use our `stb_font_scale(font)` (libFont.cpp:803) instead of KytyPS5's em scale so it matches our
metrics. Insertion: before LIB_DEFINE(InitFont_1) (libFont.cpp:2218). Test: Roboto/Noto TTF from memory, kerning of
'A','V' is negative; pre_code 0 -> OK and zero.

*Second source, SS40:* **SS40 sceFontGetKerning** (sDuhHGNhHvE). `int (FontHandle font, uint32 pre, uint32 code, float kerning[4])`: kerning
null -> error (sharp INVALID_ARGUMENT; OURS font errors use -1 style, keep OURS convention); write 4 x 0.0f; OK. Source:
S Font/FontExports.cs:409-434. Ours: LIB_DEFINE(InitFont_1) libs/libFont.cpp:2218-. Test: zeros written.

#### 88. SS34

**SS34 sceAudioOut2LoContextGetQueueLevel** (Q8DZkKQ-SYc). LIB_FUNC to AudioOut2ContextGetQueueLevel
(libAudio2.cpp:673-712). Source: S Audio/AudioOut2Exports.cs:615-621. Ours: LIB_DEFINE(InitAudio_1_AudioOut2)
libs/libAudio.cpp:139-168. Test: unknown context -> level 0, available 4. Replug check before ship.

#### 89. SS35

**SS35 sceAjmBatchJobRunBufferRa / RunSplitBufferRa** (ElslOCpOIns, 7jdAXK+2fMo). LIB_FUNC to AjmBatchJobRun /
AjmBatchJobRunSplit (ajm.cpp:1186-1232); the 10th (stack) return-address argument is ignored by the SysV callee.
Source: S Audio/AjmExports.cs:572-590. Ours: libs/libAudio.cpp:552-553 block. Test: same batch built through RunBufferRa
and Run gives identical batch buffers. Replug check before ship.

#### 90. SS39

**SS39 sceAvPlayerSetAvailableBW** (+7xJ+lFxmkQ). LIB_FUNC to AvPlayerSetAvailableBandwidth (avPlayer.cpp:1994-2005).
Source: S AvPlayer/AvPlayerExports.cs:884-900. Ours: LIB_DEFINE(InitAudio_1_AvPlayer) libs/libAudio.cpp:588-610. Test:
null handle -> AVPLAYER_ERROR_INVALID_PARAMS; min > max -> same.

#### 91. KS07

**KS07 net errno.** Replace O NET_CALL (libNet.cpp:20-27) and FinishSocketCall (:71-79) with K FinishNetCall
(libNet.cpp:52-57): on result<0 store `result - NET_ERROR_EPERM + 1` in g_net_errno; return the result unchanged.
Test: NetResolverStartNtoa with null hostname returns NET_ERROR_EINVAL and *GetNetErrorAddr() == 22.

#### 92. KS08

**KS08 PlayGoGetChunkId.** NID per O libPlayGo.cpp LIB_DEFINE :478. After handle and out_entries checks: if
list!=NULL && entries==0 -> PLAYGO_ERROR_BAD_SIZE; ensure_chunks_loaded(); if list==NULL -> *out_entries =
g_chunks_num, OK. Source K libs/libPlayGo.cpp:224-234; insert O :254-257. Test: open, GetChunkId(h, NULL, 0, &n) ->
n == chunk count (1 with our fallback); GetChunkId(h, buf, 0, &n) -> BAD_SIZE.

#### 93. KS11

**KS11 Psml base mode.** Psml lib: PsmlInitialize (3WVD91e12ZQ, O libPsml.cpp:113-121) returns 0x8a810012
(NOT_TRINITY_MODE) when KernelIsTrinityMode is 0 (O libKernel.cpp:1408 returns 0), leaving g_initialized false
(K libPsml.cpp:40,120-130). Register aliases fccGInHrj8A -> PsmlContextInitialize and 94iBp3KvIuI -> PsmlDispatch in
O LIB_DEFINE(InitPsml_1) :329 (both then answer NOT_INITIALIZED). New `LIB_VERSION("Psml_mfsr2",1,"Psml",1,1)` block:
Initialize o+NM86gEwFE -> 0x8a8a0012 (NOT_AVAILABLE); 1ic5q-kdOsc, gMduXCLYrNg, 0GAw7SmkwII, 5z2gBlqxJ+0, m9JLPc3wOQw,
Kyy1baXgaVU, ZLL31lzzxr4, lrJwpLjKXRc -> 0x8a8a0001 (NOT_INITIALIZED) (K :358-372,494-603,614-624). No packet writing.
Test: PsmlInitialize == 0x8a810012; mfsr2 Initialize == 0x8a8a0012; mfsr2 GetDispatchPackets == 0x8a8a0001.

#### 94. KS12

**KS12 Np request completion.** NpGetAccountAge (+4DegjBqV1g, O network.cpp:4560): after arg checks, lock
g_np_request_mutex, find the request (REQUEST_NOT_FOUND), *age=0, `return np_complete_signed_out_locked(request)`.
NpGetAccountLanguage2 (3Tcz5bNCfZQ, O libNet.cpp:1430): same through a new exported helper in network.cpp (the request
table is static there); do NOT memset KytyPS5's 48-byte NpLanguageCode -- ours documents 16 bytes (O libNet.cpp:1421-1426),
write nothing when signed out. Source K network.cpp:4164-4177,4369-4407. Test: CreateAsyncRequest, GetAccountAge -> 0,
PollAsync -> OK with result SIGNED_OUT; sync request -> SIGNED_OUT.

#### 95. KS18

**KS18 SaveDataConvert.** NID 2mfSRGdshtk (O :1218, both LIB_DEFINEs). Struct {int32 user_id; int32 pad; const DirName*
src; const DirName* dst; uint64 dst_blocks; uint8 reserved[24]} -- our comment (:1214-1217) reads blocks at +0x18, same.
Order (K :1210-1258): PARAMETER (null, src invalid or "sce_sdmemory*", dst invalid, blocks outside 48..16384);
INVALID_LOGIN_USER; NOT_FOUND if src dir missing; BUSY if mounted; EXISTS if dst exists; if our .blocks sidecar exists:
equal -> 0x809F001E NO_NEED_CONVERT, smaller -> 0x809F0020 BLOCKS_FEWER_THAN_SRC; otherwise keep our current NOT_FOUND
(KytyPS5 EXITs here). Add the two constants to O errno.h next to SAVE_DATA_ERROR_PARAMSFO_TRANSFER_TITLE_ID_NOT_FOUND.
Test: K tests/SaveDataMemoryTests.cpp TestConvert sequence, last step expecting NOT_FOUND instead of abort.

#### 96. KS20

**KS20 Stub out-params.** GameLiveStreaming lK8dLBNp9OE `int(Status2* s)`: null -> 0x80A00002 INVALID_PARAM;
memset 72 bytes, user_id=-1. yeQKjHETi40 `int(int type, uint32_t* count)`: type 1..3 and count non-null else same
error; *count=0 (K libNet.cpp:2783-2830; replace O libGameLiveStreaming.cpp:223,268). SharePlay: add init flag to
O libNet.cpp:4162-4176 (ALREADY_INITIALIZED 0x810E0003, NOT_INITIALIZED 0x810E0004, heap!=NULL && size<6 KiB ->
INVALID_ARGS 0x810E0001); +MCXJlWdi+s `int(ConnectionInfoA*)` 72 bytes zeroed, host/visitor user id -1 (K :2850-2905;
replace O libSharePlay.cpp:30). NpGetUserIdByAccountId VgYczPGB5ss `int(uint64 account, int* user)`: account 0 or
user NULL -> 0x80550003; else 0x80550006 SIGNED_OUT (no PSN emulation) (K network.cpp:4332-4350; replace O libNp.cpp:347).
Test: call each with a 0xCC-filled buffer; check the written fields and codes.

#### 97. KS21

**KS21 NpCommerceDialog.** Result struct {int32 result; bool authorized; void* user_data (+8); uint8 reserved[32]} 48
bytes; Open copies param->user_data (+88 of the 128-byte param) when param->size==128; size!=128, mode>5 or
reserved!=0 -> 0x80B8000A PARAM_INVALID (result.result too); GetResult copies the stored result (K libNet.cpp:1563-1645).
Keep our RUNNING-until-UpdateStatus state machine (O :58-86). Test: Open with user_data 0x1234 -> GetResult user_data
0x1234, result 1 (cancelled).

#### 98. KS22

**KS22 NetCtlGetInfo.** At O network.cpp:4077 replace EXIT with `if (!info) return NET_CTL_ERROR_INVALID_ADDR; if (code<1||code>21) return NET_CTL_ERROR_INVALID_CODE;`
before the memset (K network.cpp:3950-3955). Test: GetInfo(1, NULL) -> 0x80412107; GetInfo(99, &i) -> 0x80412106.

#### 99. KS23

**KS23 NpAuth V3.** Structs {size_t size; int user_id; pad; const void* client_id; const char* scope} (32) and
{...; const void* client_secret; const char* scope} (40). req_id<=0, param or out NULL -> 0x80550301; size<sizeof ->
0x80550302; client_id/scope (and secret) NULL -> 0x80550301; then the existing signed-out completion (K libNet.cpp:
1737-1755,1921-1980; O libNet.cpp:1908-1969). Test: param.size=8 -> 0x80550302.

#### 100. KS24

**KS24 SaveDataDialog RUNNING poll.** In O dialog.cpp:388-401: for non-progress-bar modes, the first UpdateStatus after
Open returns RUNNING, the next FINISHED (flag reset in Open/Close/Terminate as K :441,450,464-477,531,542,557).
Test: Open(mode 1), UpdateStatus -> 2, UpdateStatus -> 3; mode 5 stays 2 until Close.

#### 101. KS25

**KS25 Pad port state.** Per player slot: Uninitialized -> PadInit -> Closed; PadOpen: Uninitialized ->
NOT_INITIALIZED (0x80920005), invalid args -> INVALID_ARG, Open -> ALREADY_OPENED (0x80920004), else Open + handle;
PadGetHandle: NOT_INITIALIZED / NO_HANDLE (0x80920008) unless open; handle checks answer NOT_INITIALIZED before init;
PadClose releases (K controller.cpp:1155-1212,1230-1281). Insert O controller.cpp:1199-1262, libPad.cpp:278. Keep our
user->slot mapping and the remote-control port. Test: Open before Init -> 0x80920005; Init, Open, Open -> 0x80920004;
Close, GetHandle -> 0x80920008.

#### 102. KS28

**KS28 MultipleRecords.** NID RCCY01Xd+58, `int(int rid, const char* host, NetResolverInfo* info, int timeout, int retry, int flags)`;
NetResolverAddr {uint32 addr; uint32 reserved[3]; int af; int reserved[3]} 32, NetResolverInfo {addrs[10]; int records;
int dns4records; int reserved[14]} 384. host/info NULL or flags & ~0x10000 -> EINVAL; bad rid -> EBADF; *info={};
literal IPv4 (flag clear) -> addrs[0], af 2, records=dns4records=1, OK; else our platform path (Windows getaddrinfo loop
filling up to 10 records, EAI_NODATA -> ENORECORD; Linux NET_ERROR_RESOLVER_ENOTIMPLEMENTED as StartNtoa). Source K
network.h:40-56, network.cpp:1464-1531; insert O network.h / network.cpp near :1446, LIB_FUNC O libNet.cpp:198.
Test (K tests/NetResolverTests.cpp): "192.168.1.2" -> 1 record, addr 0x0201a8c0.

#### 103. KS30 (+SS31)

**KS30 NpEntitlementAccess key/flag/txn.** Add `g_initialized` set by NpEntitlementAccessInitialize (O libNet.cpp:1576).
5LiMEPuW0DQ `int(uint32 label, const Label* el, Key* key)`: el/key NULL -> 0x817D0002, else 0x817D0007 (K :475-492).
y7JD1gfwyfA `int(uint32* flag)`: not init -> 0x817D0001, NULL -> 0x817D0002, *flag=0 (K :207-218). IQtb-TaIjSM
`int(TransactionId* t)` (72 bytes): not init / NULL as above; memset, snprintf "6b797479%024llx" of a counter from 1
(K :219-232). LIB_FUNC in O :1716. Test: before Initialize -> 0x817D0001; after: key -> 0x817D0007; txn -> "6b797479000...001".

*Second source, SS31:* **SS31 sceNpEntitlementAccessGetGameTrialsFlag / GetEntitlementKey** (y7JD1gfwyfA, 5LiMEPuW0DQ).
`int GetGameTrialsFlag(uint32* f)`: null -> 0x817D0002; *f = 0. `int GetEntitlementKey(uint32 service, const
NpUnifiedEntitlementLabel* label, uint8 key[16])`: label or key null -> 0x817D0002; zero key; OK when label is in
NP_ENTITLEMENT_ACCESS_ADDON_LIST (libNet.cpp:1570-1574), else 0x817D0007. Source: S Np/NpEntitlementAccessExports.cs:
98-116, 223-252. Ours: libs/libNet.cpp:1716-1724. Test: listed label -> OK + zero key; other label -> 0x817D0007.

#### 104. KS31

**KS31 Http k-only group.** Add Network::HttpValidBase(id) = HttpValid||HttpValidTemplate||HttpValidConnection||
HttpValidRequest (O network.cpp:260-263; K network.cpp:415-419). Exports (K network.cpp:3064-3200, LIB_FUNC K
libNet.cpp:754-762): h9wmFZX4i-4, Kh6bS2HQKbo, vO4B-42ef-k (int(id, cb, arg)) and i9mhafzkEi8 (int(id, en)) -> base
check; PDxS48xGQLs (int(req, en)): en not 0/1 -> HTTP_ERROR_INVALID_VALUE, non-request -> INVALID_ID; DK+GoXCNT04 /
zXqcE0fizz0 -> ctx check; JBN6N-EY+3M (int(req, int32* err, uint32* detail)) and 0onIrKx9NIE (int(req, int* err)): NULL ->
INVALID_VALUE, write 0s, then request check. Insert in O network.cpp Http namespace + LIB_DEFINE O libNet.cpp:617.
Test: each with id 12345 -> INVALID_ID; HttpGetLastErrno on a real request -> 0 and *err==0.

#### 105. KS32

**KS32 NpWebApi2 stats.** Map ctx->rounded pool size in NpWebApi2Initialize (O :3451; pool > SIZE_MAX-0x3fff ->
INVALID_ARGUMENT); Xweb+naPZ8Y `int(int ctx, Stats* s)` {size_t pool, max_inuse, cur_inuse; int32 reserved}: NULL ->
INVALID_ARGUMENT, ctx<=0 -> 0x80553403, unknown -> 0x80553404, else {pool,0,0,0}; Terminate (O :3792) same errors and
erases (K libNet.cpp:2084-2108,2122-2155,2435-2445). Test: Initialize(1, 1) -> stats.pool 0x4000; Terminate twice -> 0x80553404.

#### 106. KS33 (+SS41)

**KS33 PadIsRemoteController.** fCWdlnmB1Ks `int(int handle, bool* r)`: our handle check (as PadReadState O
controller.cpp:1359), NULL -> PAD_ERROR_INVALID_ARG, *r=false (K controller.cpp:1348-1360). LIB_FUNC O libPad.cpp:301.
Test: valid handle -> false/OK; handle 99 -> 0x80920003.

*Second source, SS41:* **SS41 scePadIsRemoteController** (fCWdlnmB1Ks). `int (int handle, uint8* out)`: ControllerIndexFromHandle < 0 ->
PAD_ERROR_INVALID_HANDLE (controller.cpp:37); out null -> 0x80920001; *out = 0; OK. Source: S Pad/PadExports.cs:816-839.
Ours: next to controller.cpp:1321-1353, LIB_FUNC libs/libPad.cpp:301-326. Test: handle 1 -> 0 written; handle 0 ->
INVALID_HANDLE.

#### 107. KS34

**KS34 ConvertKeycode.** New `LIB_VERSION("ConvertKeycode",1,"ConvertKeycode",1,0)` + mUuUOWI-C+0 `int(int32 user, uint32* type)`:
NULL -> 0x80bc0031, user<0 -> 0x80bc0010, *type=0 (K libConvertKeycode.cpp:1-37). Can live in O libs/libPad.cpp
(keyboard) with its own LIB_DEFINE called from the module's init. Test: three cases.

#### 108. KS35

**KS35 AddBufferAttributeOption.** MBlv8YWoyOk `void(VideoOutBufferAttribute2* a, uint64 option)`: a NULL -> return
(do not EXIT), else a->option |= option (K videoOut.cpp:1335-1340). Insert near O videoOut.cpp SetBufferAttribute2,
LIB_FUNC O libVideoOut.cpp:12 block. Test: SetBufferAttribute2 then Add(0x4) -> option has bit 2.

#### 109. KS36

**KS36 VrrStatus status.** gWT7X8H0bYs `int(int handle, void* status)`: NULL -> VIDEO_OUT_ERROR_INVALID_ADDRESS;
r = VideoOutGetOutputStatus(handle, status) (O videoOut.cpp:1837); on OK zero 8 bytes at +0x30 (K
libVideoOutVrrStatus.cpp:43-62). LIB_FUNC in O libVideoOut.cpp:57-60. Test needs a VideoOut driver instance for
GetOutputStatus; with the sharpemu b1ec286 change in flight (status before registration) a CPU test can open a port
without presenting. Bad handle -> GetOutputStatus's error.

#### 110. KS37

**KS37 NetCtl Linux info.** Replace the non-Windows branch of O QueryHostNetworkInfo (network.cpp:3919-3921) with K
network.cpp:3757-3811: first IFF_UP|IFF_RUNNING non-loopback AF_INET ifaddr, then /proc/net/route default route (lowest
metric, RTF_UP and not RTF_REJECT) picks interface + gateway; fill ip_address, netmask, default_route; connected = ip
non-empty. Keep our --network-online gate. Test (Linux): with the flag, GetInfo(14 IP) returns the host IP (compare with getifaddrs).

#### 111. SS05 (+KS19)

**SS05 sceUsbdHandleEventsTimeout** (+wU6CGuZcWk, libSceUsbd). `int (const struct {int64 sec; int64 usec;}* tv)`. null,
sec < 0, usec outside [0, 1e6) or overflow -> 0x80240002 (SCE_USBD_ERROR_INVALID_PARAM per sharp); else sleep
sec*1e6+usec microseconds, return OK. Source: S Usbd/UsbdExports.cs:64-102. Ours: libs/libUsbd.cpp:673-682 (LIB_FUNC
:1161). Test: {0, 5000} returns OK after >= 5 ms; {0, 1000000} -> error.

*Second source, KS19:* **KS19 Usbd poll sleep.** sceUsbdHandleEventsTimeout (+wU6CGuZcWk, O libUsbd.cpp:673): `Common::Thread::SleepMicro(16000)`
then OK (K libUsbd.cpp:27-34). Test: 10 calls take >= 150 ms.

#### 112. SS18

**SS18 scePlayGoGetLocus bad entry** (uWIYLFkkwqk). Before returning PLAYGO_ERROR_BAD_CHUNK_ID for entry i, write
out_loci[i] = PLAYGO_LOCUS_NOT_DOWNLOADED. Source: S PlayGo/PlayGoExports.cs (16a2131 hunk at former :424-430). Ours:
libs/libPlayGo.cpp:188-194. Test: ids {0, 9999} -> BAD_CHUNK_ID, loci = {LOCAL_FAST, NOT_DOWNLOADED}.

#### 113. SS24

**SS24 sceNetCtlRegisterCallbackV6** (1NE9OWdBIww, libSceNetCtl). `int (NetCtlCallback func, void* arg, int* cid)` ->
NetCtl::NetCtlRegisterCallback (network.cpp:4013-4033). Source: S Network/NetCtlExports.cs:149-154. Ours:
libs/libNet.cpp:1395-1406. Test: register -> cid written, OK; NULL func -> NET_CTL_ERROR_INVALID_ADDR.

#### 114. SS25 (+KS29)

**SS25 Json aliases** (libSceJson2). LIB_FUNC: t6AHhkWu4mY -> JsonArrayCtor; MIyMPw7YTGM -> JsonArrayDtor; eG9E9M6XvTM
-> JsonStringCtor; Ui7YFnSTCBw -> JsonStringDtor; 9niNrXsF3Bc -> JsonArrayIterDtor; iAIYn4oAWvI -> JsonArrayIterDeref;
0YqYAoO-+Uo -> JsonValueIndexUInt; FIjXN2TkuTs -> new `JsonValue* KYTY_SYSV_ABI JsonValueClearExport(JsonValue* self)`
that saves parent/rootparam, calls JsonValueClear (libJson2.cpp:224-240, which nulls them), restores them, returns
self. Source: S Json/JsonExports.cs:489-494, 531-548, 667-686, 777-782, 807-812; JsonValueExports.cs:189-198. Ours:
LIB_DEFINE(InitNet_1_Json2) libs/libJson2.cpp:1301-1391. Test: C2-construct an Array and String in a host buffer, push
values, D2-destroy (no leak under ASan); getValue(1) on [1,2,3] -> value 2; clear() on an object member -> type null,
parent kept.

*Second source, KS29:* **KS29 JsonValueClearMethod.** NID FIjXN2TkuTs, `void(void* self)`: save parent/rootparam, JsonValueClear, restore
(K libJson2.cpp:1063-1075). Insert next to O JsonValueDtor :596, LIB_FUNC in O :1301 block. Test: object value with
parent p -> after clear type null, parent p.

#### 115. SS26

**SS26 Json iterator ops**. JsonIterHandle {void* impl} (libJson2.cpp:1129-1136). TAPTWYaYf8Q/JSg1MSo7NKE `iterator()`:
self->impl = nullptr, return self. IaIvX3kgyb0/Hdc3DSIsG2I `iterator(const iterator& o)`: impl = o.impl ? new
JsonArrayIter{o.vec, o.index} registered via JsonIterRegister : nullptr. T3WReElX4BY `operator=(o)`: release own impl
(JsonIterRelease + delete), then copy as above, return self. GEylwSsiGG8 `operator++(int)`: rdi = hidden result,
rsi = this: result gets a copy at the old position, this advances (as JsonArrayIterNext); return result.
43MESLndGvQ `advance(size_t n)`: index = min(index + n, size). Source: S Json/JsonExports.cs:731-764, 827-850 and
helpers to :910 (b307b2f). Ours: after libs/libJson2.cpp:1224. Test: parse [1,2,3]; begin/end; copy begin, post-inc
the copy, deref old/new -> 1/2; advance(5) == end; destroy all copies (registry has no leaks/double frees).

#### 116. SS27

**SS27 sceAppContentGetAddcontInfoList** (xnd8BJzAxmk). `int (uint32 serviceLabel, void* list, uint32 listNum,
uint32* hitNum)`. list null or listNum 0: hitNum null -> APP_CONTENT_ERROR_PARAMETER, else *hitNum = 0; otherwise
*hitNum = 0 if non-null; OK. Source: S AppContent/AppContentExports.cs:48-68; shadPS4 app_content.cpp:269-295. Ours:
LIB_DEFINE(InitAppContent_1) libs/libAppContent.cpp:258-265. Test: hitNum preset 0xFFFFFFFF -> 0; all-null -> PARAMETER.

#### 117. SS28

**SS28 sceNpCommerceDialogOpen2** (IXmfUaze9So). LIB_FUNC to NpCommerceDialogOpen (libNpCommerceDialog.cpp:58-77).
Source: S Np/NpCommerceExports.cs:41-46. Ours: libs/libNpCommerceDialog.cpp:139-145. Test: Initialize, Open2 -> OK,
UpdateStatus -> FINISHED, GetResult -> OK.

#### 118. SS29

**SS29 sceSaveDataUmount / sceSaveDataGetProgress** (BMR4F-Uek3E, ANmSWUiyyGQ). `int Umount(const SaveDataMountPoint*)`
-> SaveDataUmount2(0, mp). `int GetProgress(float* p)`: null -> PARAMETER; *p = 1.0f (all OURS operations finish in
the call); OK. Source: S SaveDataExports.cs:263-265, 535-549; shadPS4 savedata.cpp:1705-1708, 1096-1108. Ours:
libs/libSaveData.cpp:885-910, LIB_DEFINE :1290-1316. Test: Mount3 then Umount -> slot free (17 mount/umount cycles OK).

#### 119. SS30

**SS30 sceSystemServiceGetMainAppTitleId** (4veE0XiIugA). `int (char* out /*16 bytes*/)`: null ->
SYSTEM_SERVICE_ERROR_PARAMETER; copy TITLE_ID (Loader::SystemContentParamSfoGetString as libSaveData.cpp:254-261),
at most 15 chars + NUL; OK. Source: S SystemService/SystemServiceExports.cs:109-133. Ours: LIB_DEFINE(InitSystemService_1)
libs/libSystemService.cpp:570-584. Test: with a param.sfo stub TITLE_ID "PPSA01234" -> "PPSA01234\0".

#### 120. SS32

**SS32 sceNpAuthGetAuthorizedAppCode** (IDX0S5EsEh4). `int (int reqId, const void* param, void* out)`: unknown request
-> NP_AUTH_ERROR_REQUEST_NOT_FOUND; aborted -> ABORTED; else np_auth_complete_signed_out(request) (SIGNED_OUT for sync, 0 +
result for async), no out writes (layout unknown). Source: S Np/NpAuthExports.cs:154-158, 180-217. Ours: copy of
NpAuthGetAuthorizationCodeV3 libs/libNet.cpp:1908-1940; LIB_DEFINE :1971-1980. Test: CreateRequest, call -> 0x80550006.

#### 121. SS33

**SS33 sceNpSessionSignalingCreateContext2 / RequestPrepare** (aBuX0PX-T7I, r8mVMwlafF8). CreateContext2 returns an
incrementing id starting at 1 (args ignored); RequestPrepare returns NP_ERROR_SIGNED_OUT 0x80550006. Source: S
Np/NpSessionSignalingExports.cs:24-41. Ours: libs/libNet.cpp:1534-1539. Test: two calls -> 1, 2; RequestPrepare -> error.

#### 122. SS36

**SS36 Ampr non-_04_00 wait-on-address** (V7GQTEeUfhw, jIlc4p5dSD0). LIB_FUNC V7GQTEeUfhw -> CommandBufferWaitOnAddress
(libAmpr.cpp:3050-3066), jIlc4p5dSD0 -> MeasureCommandSizeFixed32 (:2743-2748, 0x20 covers the largest record);
optional: reject compare > 3 for the new form (sharp :1748-1757). Source: S Ampr/AmprExports.cs:613-642, 835-869.
Ours: LIB_DEFINE(InitAmpr_1_Ampr) libs/libAmpr.cpp:3648-3744. Test: measure -> 0x20; append into a host command buffer
and run the CPU executor: blocks until *addr matches.

#### 123. SS37

**SS37 scePlayGoSetLanguageMask** (LosLlHOpNqQ). `int (int handle, uint64 mask)`: validate_handle; store; OK.
GetLanguageMask (libPlayGo.cpp:381-395) returns the stored mask (default PLAYGO_LANGUAGE_MASK_ALL). Source: S
PlayGo/PlayGoExports.cs:680-702. Ours: libs/libPlayGo.cpp:478-496. Test: bad handle -> BAD_HANDLE; set 0x5, get 0x5.

#### 124. SS38

**SS38 Rtc network ticks** (LN3Zcb72Q0c, Ot1DE3gif84, HWxHOdbM-Pg). LIB_FUNC each to RtcGetCurrentNetworkTick
(libRtc.cpp:122-126). Source: shadPS4 rtc.cpp:390-507. Ours: LIB_DEFINE(InitRtc_1_Rtc) libs/libRtc.cpp:566-596. Test:
each tick within 1 s of GetCurrentTick.


## 6. Size of the "later" rest

The 129 later candidates split by effort as follows:

| Effort | Rows | Estimate |
|---|---|---|
| S | 65 (14 of them registration-only: equivalent to the loader's return-0 stub, so they add no behaviour) | about 1 h each with a test: **~8 agent-days** |
| M | 52 | 0.5-1 day each: **~26-52 agent-days, central ~40** |
| L | 12 | **~55-70 agent-days** in all |

The 12 L rows:

| Rank | ID | Item | Estimate |
|---|---|---|---|
| 141 | KA37 (+SS07) | NGS2 renderer | 8-10 days |
| 142 | SK24 (+KS38) | POSIX sockets on Linux | 4-5 days |
| 143 | KS39 (+SS14) | Trophy system | 5-8 days |
| 144 | KK37 (+KL20) | Guest TSC | ~4 days; needs KL21 |
| 145 | KL21 | Guest instruction patcher | 5-8 days |
| 234 | SK39 | libc HLE fallbacks, 55 NIDs | ~5 days |
| 235 | KL25 | Trinity / Pro mode | GPU-coupled |
| 237 | KS45 | Psml PSSR | GPU, other agent |
| 238 | KS47 | Error and Signin dialog overlay | - |
| 236 | KA49 (+KS48) | DualSense Bluetooth haptics and speaker | needs the exp 0372 replug check |
| 239 | KS49 | PSVR2 controllers | - |
| 233 | KK41 | ZArchive read-only mounts | - |

**Total: about 100 agent-days (range 80-130).**

- The passes' own estimates sum to about 102-113 days before duplicates were removed. Removing them takes off about 8.
- Without the Pro/PSVR2/ZArchive/overlay items (KL25, KS45, KS47, KS49, KK41) the total is about 80.
- The e4-now set is 124 × S, about 15 agent-days including the CPU tests.

## 7. Coverage gaps and open checks

- **KytyPS5 `libs/libAmpr.cpp`: 392 KytyPS5-only lines not compared line by line.**
  - Our APR side already has the same structures: submission ids and completion wait (`O:libs/libAmpr.cpp:154-594`),
    the ForEach and WithPrefix resolvers (`:706-878`) and WaitOnAddress (`:973`). Only `V7GQTEeUfhw` is missing, and it
    is rank 122 (SS36).
  - The KytyPS5 hunks also carry AMM command execution (memory agent), guest C-string reads with EFAULT/ENAMETOOLONG,
    ENFILE on file-id exhaustion, and `InvalidateFailedResolves` for add-ons.
  - Recommended: one M pass shared with the memory agent's AMM review.
- **Not compared:**
  - KytyPS5 `src/common/` (shared utilities). Flip and VideoOut code in `graphics/presentation` is left to the GPU agent.
  - In sharpemu: the Videodec2 internals, the AvPlayer/Media FFmpeg code, the Font text-string code from `11506fc`, and
    Ime. These are marked unverified in their SS rows.
- **TODO(verify), carried from the rows (none of these has a console source):**

  | Item | Rank | What is unverified |
  |---|---|---|
  | KK05 | 125 | Guest `struct tm` size |
  | KK27 | 55 | `sceKernelGetAvailableCpumask` value 0x1FFF (AnyPS5 agrees) |
  | KK15 | 49 | AMPR event filter -25 (behind a switch; exp 0036 saw no change) |
  | KK24 (+SK16) | 43 | The FreeBSD `_umtx_op` op numbers |
  | KS11 | 93 | Psml NOT_TRINITY_MODE (KytyPS5's claim) |
  | KA22 | 164 | AudioIn param enum |
  | KA20 | 163 | 8-channel order |
  | KA19 | 202 | KytyPS5's ContextResetParam defaults |
  | KK37 | 144 | The 1.6 GHz TSC figure in `2f885e2`'s message, against our 2.0 GHz trap-path assumption |
  | KL02 | 4 | Why the call needs REX.W when the kept 0x66 bytes are real prefixes. The operand-size rules for a near CALL with 66h and REX.W are vendor-specific: cite the AMD APM Vol. 3 (CALL near) before porting. |

## 8. Files

All paths are under `scratchpad/0405/work/r2/`.

| File | Contents |
|---|---|
| `parts/KK.md`, `KL.md`, `KA.md`, `KS.md`, `SK.md`, `SS.md` | The six passes, each with its method, full table, port specs and totals. Raw diffs and helper scripts are in `parts/*-scripts/`. |
| `BRIEF.md` | The common brief the passes worked from. |
| `scripts/nids2.py` | Multi-line `LIB_FUNC` inventory. |
| `scripts/sharp_nids.py` | sharpemu `SysAbiExport` inventory. |
| `scripts/build.py` | Merge, dedupe and rank (the merge map and the hand order are in it). |
| `ours2.tsv`, `kps52.tsv`, `sharp-nids.tsv` | The inventories. |
| `k2-only.n`, `s3-only.n` | The NIDs we lack. |
| `kps5/src` | KytyPS5 `dfec14a` sources (extracted). |
| `sharp/src` | sharpemu `514d766` sources (extracted). |
