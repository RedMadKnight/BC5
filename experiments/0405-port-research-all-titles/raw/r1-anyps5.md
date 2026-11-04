# r1 — AnyPS5 HLE libraries against our host, without the title gate (2026-11-04)

**Question.** The maintainer's rule from 2026-11-03 23:0x is that the host should be complete and correct for any title. A port
may be skipped only when "we already match (file:line)" or when "licence/provenance not acceptable". Under that rule, which
AnyPS5 exports and fixes should our host take? This redoes the library part of exp 0402 without the title gate.

**Inputs**
- AnyPS5 `boykopovar/AnyPS5` at `4f41f4c375f5abb487dbd184fbc150f31994d762`. The licence is GPL-2.0-only (`LICENSE`, README).
  - Clone (read only):
    `C:\Users\kjani\AppData\Local\Temp\claude\C--Users-kjani-Downloads-bc5\43cd6eac-dc2c-49c1-b603-e5283be4d569\scratchpad\src\AnyPS5`.
  - Diffs were read through private object stores under `_work\` that borrow the clone's objects. The clone itself was not
    written.
- Ours: the e4 tree, which is KytyPlus `f266548` with patch 0001:
  `...\scratchpad\e4\full\src`.
- Port points:
  - `7ba97f4` for every library, the end of Codex's review (`Documents/ChatGPT/BC5/audit/upstream-review/ANYPS5.md`).
  - `27c88a8` for NpCppWebApi (exp 0328). PORT-NP later took `daf4eb35`.

**How**
1. **Exports.** `r1-anyps5-inventory.py` counts AnyPS5 exports. It uses the exp 0402 NID calculator, self-checked on three
   pairs. It differs from 0402 in four ways:
   - only C-linkage, non-static definitions count, so 0402's internal helpers such as SaveData `DeliverEvents` drop out;
   - `_nid_disambig<N>` is stripped;
   - `APS5_ASM_FUNCTION` exports and `extern "C"` data are added;
   - each export carries its file:line and a kind:
     - *pending*: the `NotImplemented_nid_no_patch` stub;
     - *const*: no call, at most 3 statements;
     - *logic*: everything else.
2. **Our registrations.** `r1-anyps5-loaded.py` resolves which `LIB_FUNC`/`LIB_OBJECT` registrations `Libs::InitAll` actually
   reaches (`libs/libs.cpp:93-136`).
3. **Tables.** `r1-anyps5-report.py` writes the tables and `r1-anyps5-missing.tsv`.
4. **Commits.** The 966 non-merge commits after the port points that touch the non-GPU libraries we host (1,030 rows, one
   per library and commit) were split across five read-only sub-agents. Their per-commit verdicts are in `_work\verdicts\{A,B,C,D1,D2}.tsv`. I spot-checked the
   file:line claims used below against the e4 tree.
5. **Not compared:** 505 Agc, AgcDriver and GnmDriverForNeoMode commits (see §5).

## 0. Headline

- **114 AnyPS5 modules map to libraries we host.** They have 13,507 exports, of which 7,350 are implemented.
- **5,553 of the implemented exports are not exported by our host at run time.**
  - 1,500 of them are libc, which titles ship as their own `libc.prx`.
  - 267 are GPU-side: Agc, AgcDriver and GnmDriverForNeoMode.
  - That leaves **3,786**: 1,007 constant answers, 14 data objects, and 2,765 with logic (about 20,200 body lines). A rough
    port estimate is ~140 working days at 150 ported body lines or 200 constant answers per day, tests included.
- **32 KytyPlus tables are compiled but never loaded.** `InitAll` never calls them, so 1,223 of our 3,070 registered NIDs
  are dead at run time.
  - The tables: NpCommon, NpManager (libNp.cpp), NpTus, NpTrophy, NpParty, NpPartner, NpAuth, NpSnsFacebookDialog, Camera,
    Usbd, Hmd, Ime, Ngs2 (libNgs2.cpp), Voice, Move, Zlib, Jpeg, ScreenShot, RemotePlay, GameLiveStreaming, SharePlay,
    WebBrowserDialog, InvitationDialog, VideoRecording, DiscMap, ulobjmgr, CompanionHttpd/Util, RazorCpu, VrTracker,
    GnmDriver and RageEngine.
  - 1,081 of the dead NIDs belong to libraries AnyPS5 implements, and 618 of those AnyPS5 implements.
  - Exp 0402 counted these as present. The D1 sub-agent found the libNp.cpp case; the reachability scan found the rest.
- **Commit review: 1,030 rows** (966 distinct commits).
  - 117 rows touch behaviour we share: **30 match, 79 missing, 8 partial**.
  - 302 only add exports (the inventory covers them), 10 are in e4 (other port), and 120 are excluded on provenance.
  - 481 are platform-only, AnyPS5-internal, or tests/docs/build.
- **e4-now set: 18 items** (§2), all S effort, sourced, testable on the CPU and not submitting to the GPU.

## 1. Ranked candidates

Value is correctness for any title: host aborts and memory errors first, then calls every title makes, then completeness.

- **Licence.** Every AnyPS5 code source is GPL-2.0-only. Fact sources named in the notes are console measurements cited by
  AnyPS5, FreeBSD, shadPS4 (GPL-2.0), fpPS4 and prosper; only facts are taken from them.
- **Paths.** AnyPS5 paths are under `core/libs/prx/` at `4f41f4c37`. Our paths are under `e4/full/src/`.

| # | Candidate | AnyPS5 path:line, commit | Ours | Eff. | Risk (what could break) | When |
|---|---|---|---|---|---|---|
| 1 | Json2: assignment and `set()` read a source they own after clearing the destination (`v = v["a"]`, self `set`, `obj = obj`). Use-after-free. | `libSceJson2/Export.cpp:1299-1320, 1371`; fa8239009, f8e4d8acb, e237f1bfe, 3e03f8df7 | `libs/libJson2.cpp:242, 650, 911, 1012, 1033, 1050` | S | low: copy-before-clear only | **e4-now** |
| 2 | Ult: `UltUlthreadCreate` publishes the handle before `PthreadCreate` stores the thread. `Join` takes no claim, so a double join or self-join calls `PthreadJoin` twice. | `libSceUlt/Export.cpp:135-185, 881-912`; ffe469199 | `libs/libUlt.cpp:237-252, 260` | S | med: lock held across PthreadCreate | **e4-now** |
| 3 | UserService values measured on PS5 13.60 (details below). | `libSceUserService/Export.cpp:159, 163, 238`; debt `libSceUserService.md:54, 57, 58` | `libs/libUserService.cpp:117, 200-206, 270` | S | low | **e4-now** |
| 4 | SystemService parameters measured on PS5 13.40/13.60 (details below). | `libSceSystemService/Export.cpp:45-49, 549-578`; debt `libSceSystemService.md:69, 74` | `libs/libSystemService.cpp:123-129, 156` | S | med: params 7 and 1000 change answers (own switch) | **e4-now** |
| 5 | The 32 unloaded KytyPlus tables (§0). Decide per table whether to load it as is or port AnyPS5's code first. Many stubs return OK without writing their outputs, e.g. `libNp.cpp:170`. | n/a | `libs/libs.cpp:93-136` | L | high if loaded blind | later (decision first) |
| 6 | `mprotect`/`sceKernelMprotect`/mtype protect over a gap: the console returns 0 and changes only the mapped parts (fw 13.60 measurement). Ours EXITs and kills the process. | `libkernel/DirectMemory/DirectMemory.cpp:1484`; 748b35835 | `kernel/memory.cpp:3960, 3995` | M | med: per-range host protect | later |
| 7 | `scePthreadCondSignalto`: a handle that is not a thread gives ESRCH, a thread that is not waiting gives EPERM (13.60, debt `libkernel.md:345`). Ours returns 0. | `libkernel/Pthread/src/Cond.cpp:258-268`; 0a5c3be28 | `kernel/pthread.cpp:3048` | S | low | **e4-now** |
| 8 | Semaphores (details below). | `libkernel/Semaphore/src/Semaphore.cpp:25-34, 55`; 58295ef07; debt `libkernel.md:5, 91` | `kernel/semaphore.cpp:136-150, 262, 314` | S | low | **e4-now** |
| 9 | POSIX `unlink` (`VAzswvTOCzI`) is registered to `FileSystem::KernelUnlink`, so it returns SCE codes instead of -1 with errno (pattern R34). Found on the way. | `libkernel/File/src/Stdio.cpp:1227` | `libs/libKernel.cpp:3662` | S | low | **e4-now** |
| 10 | The ten SessionManager V2 NpCppWebApi exports (0402 §1, not yet ported). | `libSceNpCppWebApi/Export.cpp:1792-2316`; present since 8cd400aa4 | unregistered | S | low | **e4-now** |
| 11 | Thread lifecycle (details below). | `libkernel/Pthread/src/Thread.cpp:1230-1260, 1298-1312, 1398-1402, 1460`; 1c0cc4c7c, 2118c9913 | `kernel/pthread.cpp:3618, 3632, 3883, 1648` | M | med: the reap path must be split first | later |
| 12 | Directories report `st_blksize` 0x10000; titles size getdents buffers from it (PS4 Pro 10.71 measurement). Ours reports 512. | `libkernel/File/src/NativeStat.cpp:224`, `ArchivedFile.cpp:38`; da7581eec | `kernel/fileSystem.cpp:973, 1051` | S | low | **e4-now** |
| 13 | ENAMETOOLONG for a path of 1024 bytes or more, or a component over 255 (FreeBSD MAXPATHLEN). Ours checks only chmod, truncate and utimes, and mkdir rejects any path over 255. | `libc/src/General.cpp:386-388`; 2de34f87b | `kernel/fileSystem.cpp:941, 1111, 1615` | S | low | **e4-now** |
| 14 | New guest threads start with x87 control word 0x037f (FreeBSD thread start). Ours inherit the creator's word: glibc `pthread_create` copies the FP environment. This corrects 0402's "no-op". | `libkernel/Pthread/src/Thread.cpp:65, 891`; 8b626e307 | `kernel/pthread.cpp:3485` | S | low | **e4-now** |
| 15 | `sceSaveDataInitialize2` and `sceSaveDataInitialize` as aliases of Initialize3 (shadPS4, fpPS4). | `libSceSaveData.native/Export.cpp:1817`; bc6a5e4ea | `libs/libSaveData.cpp:1260, 1291` (Initialize3 only) | S | low | **e4-now** |
| 16 | `sceNpSetGamePresenceOnlineA` signed-out answer (shadPS4). The NID exists only in the dead libNp.cpp table. | `libSceNpManager/Export.cpp:83, 862`; 72ccb10bd | `libs/libNet.cpp:1447` (loaded table lacks it) | S | low | **e4-now** |
| 17 | Videodec2 HEVC aliases to the generic decoder calls (shadPS4). | `libSceVideodec2/Export.cpp:528-534`; 28f157cc6 | `libs/libVideoDec2.cpp:659-660` | S | low | **e4-now** |
| 18 | `sceHttp2SslEnable/DisableOption` accept a context id. Ours returns 0x817B1100. | `libSceHttp2/Export.cpp:79-90, 152-166, 303-315`; 754aad4e9 | `libs/libNet.cpp:686, 731, 947, 963` | S | low | **e4-now** |
| 19 | libSceNet IPv6 data objects (RFC 4291 values). | `libSceNet/Export.cpp:818-825, 2700`; 0918719f6 | `libs/libNet.cpp:190-191` | S | low | **e4-now** |
| 20 | `sceVideoOutRegisterBuffers2` over a live set must return SLOT_OCCUPIED 0x80290010. Ours checks the set first and returns INVALID_INDEX (EVO Player measurement). | `libSceVideoOut/src/Buffer.cpp:42-46`; a8661988e | `graphics/presentation/videoOut.cpp:1495-1502` | S | low; needs a DriverState test without a window | **e4-now** |
| 21 | AvPlayer frame `aspect_ratio` should be the sample aspect ratio, not width/height×SAR (shadPS4). | `libSceAvPlayer/src/Source.cpp:1090`; 5fdc6dbd4 | `libs/avPlayer.cpp:1383, 1532` | S | med: movie quad size in titles | **e4-now** |
| 22 | EFAULT family, 17 commits (details below). | e.g. `libkernel/System/src/Process.cpp:658`, `File/src/Stdio.cpp:1298`; 9e915f9b6, 2f29bda46, … (see `A.tsv`) | e.g. `libs/libKernel.cpp:1930`, `libs/bc5LleAgc.cpp:7838` | M | med: must not trip our GPU write-watch | later |
| 23 | Pad: 47 missing exports, e.g. `scePadGetControllerType`, `GetInfo`, `GetCapability`, `IsDS4Connected`, `ReadStateExt`, `OpenExt`, `GetDeviceInfo`. | `libScePad/Export.cpp` (TSV) | missing | M | low | later |
| 24 | Rtc: 25 missing, all pure CPU (Convert/Format/Parse, TickAddMonths/Years, Init/End, CompareTick, DOS time). | `libSceRtc/Export.cpp` (TSV) | missing | M | low | later (good next batch) |
| 25 | SystemService: 138 missing. 25 of them are "the host has no such feature" answers (4a815a8bf, 81fd4e5dd, a2e9ffd89, 2cfa852a4). | `libSceSystemService/Export.cpp` | `libs/libSystemService.cpp:570-584` (12 registered) | M | low | later |
| 26 | NpCppWebApi: the remaining 943 (615 NOT_SIGNED_IN constants and 338 parameter/factory bodies). | `libSceNpCppWebApi/Export.cpp` | `libs/libNpCppWebApi.cpp` | L | low | later |
| 27 | Json2: 128 missing, plus the `Value::s_null*` data objects (770baa122, 24fd96dcc). The identity rule's source is unclear. | `libSceJson2/Export.cpp:2667-2671` and TSV | `libs/libJson2.cpp:685, 705` | L | low | later |
| 28 | libkernel: 332 missing (aio, mmap variants, cpuset, sysctl names, `_umtx_op`, sockets). | TSV | missing | L | med | later |
| 29 | Deleted semaphore: poll, signal or delete gives ESRCH on the console (prosper console oracle). Ours is a use-after-free. | debt `libkernel.md:91` | `kernel/semaphore.cpp` (handle freed) | M | med: needs handle validation | later |
| 30 | Guest main stack ends at 0x7eeffc000 (13.60 payload). Ours is placed anywhere. | `libkernel/Pthread/src/Thread.cpp:235`; 51e5eae15 | `kernel/pthread.cpp:1150-1162` | M | med: fixed mapping collisions | later |
| 31 | No socket backend on Linux: `Net::Socket`, `Bind`, `Connect`, `Sendto` and the rest return ENOSYS. Every socket fix (14fe94351, 255fa04a1, 0c3ae3436, the socket EFAULT rows, GetSockInfo 1aa5b3089) waits on it. | `libkernel/Socket/src/Udp.cpp`, `libSceNet` | `libs/network.cpp:1855` (13 sites) | L | med | later |
| 32 | SaveData: a null mount point aborts; an unterminated 16-byte one is read with strlen. The error code (PARAMETER) is AnyPS5's assumption. | `libSceSaveData.native/Export.cpp:451`; 6f7f6dc1b | `libs/libSaveData.cpp:897, 1133, 1173, 1197` | S | low | later (code unmeasured) |
| 33 | VideoRecording parameter checks, measured on fw 13.40 inside a retail title. Our table (`InitVideoRecording_1`) is not loaded, and the layout's source is unstated. | `libSceVideoRecordingP/Export.cpp:28-60, 68-211`; a344e526e | `libs/libVideoRecording.cpp` (dead) | S–M | low | later |
| 34 | PlayGo validation of `RequestOptionalChunk`, `GetRequiredDisc`, `RequestNextChunk`, `SetInstallSpeed2`. Sourced from pgo_stub and rps5e, whose licences are unchecked; the module pack's PlayGo wins at run time (D18). | `libScePlayGo/Export.cpp:175-348`; 2412d8887 | `libs/libPlayGo.cpp:99, 112, 131` | S | low | later |
| 35 | Provenance call: values from firmware 13.42 modules run natively or under an emulator (not a console). | `libSceRtc/Export.cpp:578`, `libSceRudp/Export.cpp:269`, `libSceNet/Export.cpp:2547`; 4dd4ec5ff, 11f42d025, ce093095f | `libs/libRtc.cpp:348`, `libs/libRudp.cpp:44`, `libs/network.cpp:1446` | S | low | later (maintainer's call) |
| 36 | Smaller libkernel items, sources unclear or host choices: app0 sandbox alias (6591d3721), O_CREAT through a trailing slash gives ENOENT (7b0f1b680), equeue bound (c170bba42), CA_LIST path (b4935f7ba), ESRCH on a released handle (2118c9913). | see `A.tsv` | `kernel/fileSystem.cpp:433`, `kernel/eventQueue.cpp:290` | S | low | later |
| 37 | AudioOut: reopen default-sink ports after SDL stops the device. Not CPU-testable; needs the exp 0372 replug check. | `libSceAudioOut/src/AudioOut.cpp:201`; b87075aad | `libs/audio.cpp:645` | S | med | later |
| 38 | Voice: input voice activity (attr 1001) reports true with no mic, and `ReadFromOPort` accepts null. Unsourced. | `libSceVoice/Export.cpp:324, 331`; e50128d91, 85647ec86 | `libs/libAudio.cpp:395, 449` | S | low | later |
| 39 | Groups of missing exports (all later; sizes in §3):<br>• Font/FontFt 95<br>• CesCs 264<br>• Ult 58<br>• Http/Ssl/NetCtl/Rudp 153<br>• Audio3d/AudioPropagation/VoiceQoS/AudioIn 68<br>• AudioOut 35 (`Lo*`, `Ex*`, `Sys*`)<br>• VideoOut 25<br>• SaveData 24<br>• Http2 22<br>• AppContent 19<br>• ContentSearch/Export/Delete 30<br>• NpEntitlementAccess/SessionSignaling/WebApi2/Commerce/GameIntent 57<br>• LibcInternal 84<br>• Ampr: 30 not in flight | TSV | missing | M–L each | low–med | later |
| 40 | Ngs2 looped-PCM parsing. Our renderer is silent anyway, and the source (prosper's reading of the module) needs a provenance call. | `libSceNgs2.native/src/Atrac9.cpp:385`; 9d1a9c82e, 403956973 | `libs/audio.cpp:3068` | M | low | later |
| 41 | SaveData host-volume policy (opt-in NO_SPACE_FS, free blocks bounded by the host, failed `.blocks` write). Unmeasured. | `libSceSaveData.native/Export.cpp:863, 1116, 1135`; 438555495, 10fe6196e, 0c110bdf8 | `libs/libSaveData.cpp:359, 385, 658` | S | low–med | later |
| 42 | Needs infrastructure first: HTTP/2 transport (9624b77bc, bd68b64dd, 58f325624, eb9aa573a, d847910c6); AvPlayer HTTP sources (b81104eb5); Usbd over libusb (dbb27b9ef, 9f3799cfa; table dead). | `libSceHttp2/Transport.cpp`, `libSceAvPlayer/src/HttpStream.cpp`, `libSceUsbd/Export.cpp` | `libs/libNet.cpp:1111`, `libs/avPlayer.cpp:651`, `libs/libUsbd.cpp:643` | L | med | later |
| 43 | NpTus 136 + 16 commits, NpTrophy 24, NpParty 15, NpCommon 289 (incl. 0a520ced9, 86652a422). | `libSceNpTus/Export.cpp` etc. | dead `libs/libNp.cpp` tables | M–L | low | later (after #5) |
| 44 | libkernel_sys: 167 missing. This is the system-process module; titles link libkernel. | TSV | missing | L | low | later |
| 45 | GPU: Agc 111, AgcDriver 70, GnmDriverForNeoMode 86 missing, and 505 commits not compared. Ours runs the module pack's LLE Agc (Q14, D18). | `libSceAgc*` | `libs/bc5LleAgc.cpp`, `libs/libGraphicsDriver.cpp` | L | high: GPU | later (GPU) |
| 46 | libc: 1,500 missing. Moot while titles ship `libc.prx`. No libc commit after `7ba97f4` touches the 54 libc NIDs we register. | `libc/` | `libs/libC.cpp` | L | low | later |

Details for the longer rows:

- **#3 UserService**
  - `GetAgeLevel` without restrictions returns 0xFFFFFFFF; ours returns 9.
  - A user who is not logged in gets 0x80960009 before the null check.
  - `GetUserName` of an unknown user returns 0x80960105; ours EXITs.
  - `ZoomFollowFocus` defaults to 1; ours returns 0.
- **#4 SystemService**
  - `ParamGetInt` answers only parameters 1–5, 100–111, 200–213, 300 and 400. Every other parameter, and a null pointer,
    returns 0x80A10003 without writing. Ours answers 0 for unknown parameters and answers 7 and 1000.
  - `ParamGetString`: an unknown parameter, a buffer under 65 bytes or a null buffer returns 0x80A10003. On success the name
    is NUL-padded to the whole buffer. Ours EXITs on an unknown parameter.
- **#8 Semaphores** (fw 13.60 payload measurements):
  - attributes 0x100–0x102 are accepted;
  - a signal of 0 or less returns EINVAL;
  - a poll of 0 or above the maximum returns EINVAL.
  - Ours rejects attr > 2, accepts a signal of 0, and lowers the count on a negative signal.
- **#11 Thread lifecycle**
  - Detaching a joined thread gives ESRCH (measured, debt `libkernel.md:246`).
  - Detaching twice gives EINVAL, and so does joining a detached thread.
  - A second concurrent join gives EOPNOTSUPP.
  - Ours sets `detached` on a freed pool slot and joins a reaped `pthread_t`.
- **#22 EFAULT family**
  - The host never validates non-null guest pointers. AnyPS5 uses one guest copy-out helper (`libc/src/General.cpp:823`,
    `process_vm_writev`).
  - Real defects found in the same calls:
    - `sceKernelWriteThrottlingStatus` writes nothing.
    - `sceKernelGetAppInfo` memsets 0x98 bytes where the console struct is 0x58.
    - `KernelStat` answers EINVAL where EFAULT is expected.

**Already in e4 (other port).** These are in flight elsewhere and are not redone here:
- 45a8b80a5 (rwlock).
- dd0bc0b78 (AMM PRT writers).
- c34ab0258, 11f217b14 and 42beeaa46 (AudioOut2).
- e60402001 (`VideoOutGetOutputStatus` HDR flags).
- 0d0abe09c, bc6b4d76f and 629477b80 (SaveData events).
- Ampr: 26 of the 56 missing exports (PRT, MultiMap/Remap/ModifyProtect with their measure functions, WaitOnAddress/Counter).

**We already match (30 rows), our file:line:**

| Area | Commit | Ours |
|---|---|---|
| Semaphores | a58084520 | `kernel/semaphore.cpp:175` |
| | 2132238f4 | `:192` |
| | 3a831bd61 | `:188` |
| | 0a353f80e | `:161` |
| Memory | 06b7a58b1 | `kernel/memory.cpp:3115` |
| | 287f43e00 | `:2622` |
| libkernel | 4e913b744 | `kernel/pthread.cpp:3981` |
| | 91311f1bf and 7a4fa3865 | `libs/libKernel.cpp:2064`; one descriptor table for libkernel and sceNet |
| Ampr | 0f4ca0e8e | `libs/libAmpr.cpp:2897` |
| Font | 1d20721e1 | `libs/libFont.cpp:1039` |
| VideoOut | 36d205ebf | `graphics/presentation/videoOut.cpp:478` |
| AudioOut | ccaac6602 | `libs/audio.cpp:652` |
| Pad | e11a4735a | `libs/controller.cpp:1231` |
| | 10194ae5d | `:1349` |
| Audiodec | 095d23ea9 | `libs/libAudio.cpp:921` |
| AvPlayer | ba526365d | `libs/avPlayer.cpp:1387` |
| | 290345261 | `:1451` |
| NpCppWebApi | 4d0cd9a53 | `libs/libNpCppWebApi.cpp:603` |
| | 0f998c157 | `:150` (PORT-NP) |
| UserService | 936ae1098 | `libs/libUserService.cpp:150` |
| SaveData | 2606c3353 | `libs/libSaveData.cpp:662` |
| PlayGo | a8a5caa2a | `libs/libPlayGo.cpp:108` |

Six more matches exist only in tables that are never loaded, so at run time they do not count:

| Area | Commit | Ours |
|---|---|---|
| DiscMap | 141f7c407 | `libs/libDiscMap.cpp:144` |
| ulobjmgr | d34a43407 | `libs/libUlobjmgr.cpp:129` |
| Camera | a5113a249 | `libs/libCamera.cpp:65` |
| VrTracker | 19d0401c5 | `libs/libVrTracker.cpp:720` |
| WebBrowserDialog | ae8929455 | `libs/libWebBrowserDialog.cpp:261` |
| RemotePlay | 70d9e562a | `libs/libRemotePlay.cpp:256` |

## 2. The e4-now set: port specs

Common to all items:
- Each item goes behind its own switch (the "fixes first" rule).
- Port the behaviour, not AnyPS5's code style. A ported body keeps a `// Ported from AnyPS5 <path> @4f41f4c37 (GPL-2.0-only)`
  line.
- The NIDs below were recomputed with the calculator.

1. **Json2 aliasing-safe assignment** (fa8239009, f8e4d8acb, e237f1bfe, 3e03f8df7)
   - NIDs:
     - `Value::operator=` `4zrm6VrgIAw`
     - `set(Value)` `XL8+BUqjB1w`
     - `set(String)` `6l3Bv2gysNc`
     - `set(const char*)` `n6FC+l9DU70`
     - `set(Array)` `195ad-jAsTU`
     - `set(Object)` `dFCphqnd+a4`
     - `Object::operator=` `urOpESTBZmo`
   - Behaviour: deep-copy the source into a temporary (a JsonValue or std::string) first, then clear the destination and move
     the temporary in. dst == src stays a no-op.
   - Follow: `libSceJson2/Export.cpp:1299-1320, 1371`. Take only the snapshot-before-clear idea. Skip AnyPS5's
     reference-module allocator details and e237f1bfe's "missing headers" part, which are reference-sourced.
   - Ours: `libs/libJson2.cpp:242` (JsonValueCopy), `:650` (SetString), `:911` (Object=), `:1012` (SetArrayCopy), `:1033`
     (SetObject), `:1050` (SetCString).
   - Test (under ASan):
     - `{"a":{"b":1}}`, then `v = v["a"]`, gives `{"b":1}`.
     - Self-set of an array or object leaves it unchanged.
     - `set(v.c_str())` on the value's own string keeps the text.
     - `obj = obj` changes nothing.
2. **Ult publication and join ownership** (ffe469199)
   - NIDs: `_sceUltUlthreadCreate` `znI3q8S7KQ4`, `sceUltUlthreadJoin` `gCeAI57LGgI`.
   - Create, inside one `g_ult_mutex` section:
     - an unknown runtime or an already registered handle gives STATE 0x80810006;
     - otherwise memset the handle (512 bytes), insert the state, and call `PthreadCreate` before unlocking;
     - if `PthreadCreate` fails, erase the entry and return AGAIN 0x80810008.
   - Join:
     - a null handle gives NULL 0x80810001;
     - under the lock, a missing entry, a join already in progress, or the caller being that ulthread gives STATE (needs a
       thread_local "current ulthread" set in `UltUlthreadRun`); otherwise set `joining` and unlock;
     - then `PthreadJoin`: on failure clear `joining` and return STATE; on success store the status and erase the entry if
       it still maps to this state.
   - Follow: `libSceUlt/Export.cpp:135-185, 881-912`.
   - Source: a host-lifecycle race visible in our code (`libs/libUlt.cpp:237-252`). The STATE answer to the losing joiner
     is AnyPS5's choice and unmeasured.
   - Test:
     - Two joiners on one sleeping ulthread: exactly one gets 0 and the status, the other gets STATE.
     - A self-join gives STATE.
     - Create followed at once by a join from another thread never sees a null thread.
3. **UserService measured values**
   - Sources: debt `libSceUserService.md:54, 57, 58` (PS5 13.60). AnyPS5 `libSceUserService/Export.cpp:163, 238, 159`.
   - `sceUserServiceGetAgeLevel` `woNpu+45RLk`:
     - a user who is not logged in gets 0x80960009, checked before the null output;
     - a null output then gives 0x80960005;
     - otherwise write 0xFFFFFFFF (unrestricted). Ours writes 9 (`libs/libUserService.cpp:206`).
   - `sceUserServiceGetUserName` `1xxcMiGu2fo`:
     - an unknown user gives 0x80960105 instead of EXIT (`:117`);
     - a null name gives 0x80960005.
     - Keep our short-buffer behaviour, apart from turning the EXIT at `:118` into an error. AnyPS5's BUFFER_TOO_SHORT rule
       is unmeasured.
   - `sceUserServiceGetAccessibilityZoomFollowFocus` `O6IW1-Dwm-w`:
     - default 1 (ours 0 at `:270`);
     - the login check comes before the null check.
   - Test: a table of (logged-in or not) × (null or valid output).
4. **SystemService parameters**
   - Sources: debt `libSceSystemService.md:74` (PS5 13.40, ptrace inside a retail title) and `:69` (PS5 13.60 payload).
   - `sceSystemServiceParamGetInt` `fZo48un7LK4`:
     - a null value gives 0x80A10003;
     - keep our answers for 1–5;
     - 400 answers the language, as 1 does;
     - 100–111, 200–213 and 300 answer from AnyPS5's measured table (`Export.cpp:45-49`);
     - anything else gives 0x80A10003 without writing.
     - Parameters 7 and 1000, which ours answers today, go behind a second switch.
   - `sceSystemServiceParamGetString` `SsC-m-S9JTA`:
     - only parameter 6 (system name) answers;
     - a null buffer or a size under 65 gives 0x80A10003;
     - on success, NUL-pad the whole buffer;
     - an unknown parameter gives 0x80A10003 instead of EXIT (`libs/libSystemService.cpp:156`).
   - Follow: `Export.cpp:549-578`.
   - Test: parameters 0, 6, 7, 999, 1000, 2048, 100, 300 and 400; a null pointer; buffers of 64 and 65 bytes.
5. **`scePthreadCondSignalto`** `o69RpYO-Mu0` (0a5c3be28)
   - Order of checks:
     - a null cond or thread gives EINVAL;
     - a handle that is not a live pool thread gives ESRCH 0x80020003;
     - a thread not waiting on this cond gives EPERM 0x80020001;
     - otherwise wake that thread and return 0. Ours already wakes only the target.
   - Follow: `libkernel/Pthread/src/Cond.cpp:258-268`. Source: debt `libkernel.md:345` (13.60). Ours: `kernel/pthread.cpp:3048`.
   - Test: the three cases.
6. **Semaphores**
   - NIDs: `sceKernelCreateSema` `188x57JYp0g`, `sceKernelSignalSema` `4czppHBiriw`, `sceKernelPollSema` `12wOHk8ywb0`.
   - Create: accept when `(attr & ~0x103) == 0 && (attr & 3) != 3`, i.e. 0, 1, 2, 0x100, 0x101 or 0x102. Keep the queue order
     from `attr & 3`.
   - Signal: a count ≤ 0 gives EINVAL 0x80020016.
   - Poll: a need of 0 or above the maximum gives EINVAL. Check ours at `kernel/semaphore.cpp:314`.
   - Follow: `libkernel/Semaphore/src/Semaphore.cpp:25-34`.
   - Source: prosper `tests/data/console_oracle/kernel.golden.tsv` L10-23 @3ea5cb9, cited at debt `libkernel.md:5, 91`.
   - Ours: `kernel/semaphore.cpp:262` (attr), `:136-150` (signal).
   - Test: attributes 0x100, 0x101 and 0x102 create and work; 3, 0x103, 0x104 and 0x200 give EINVAL; signal 0 and −1 give
     EINVAL; poll 0 gives EINVAL.
7. **POSIX `unlink`** `VAzswvTOCzI`
   - Add `Posix::unlink` returning `POSIX_CALL(LibKernel::FileSystem::KernelUnlink(path))`, like `Posix::mkdir`
     (`libs/libKernel.cpp:1999`), and register it at `:3662` instead of `FileSystem::KernelUnlink`.
   - Source: POSIX/FreeBSD `unlink(2)`. AnyPS5 `libkernel/File/src/Stdio.cpp:1227`.
   - Test: unlinking a missing file gives −1 and errno ENOENT, not 0x80020002.
8. **NpCppWebApi SessionManager V2**
   - Port the ten exports exactly as in 0402 README §1: nine return 0x80552907, and `initialize` uses
     `InitializeParameterWithBody`.
   - NIDs: `eVU3cXIJz0w`, `BY1jyWLZrcA`, `JiY4sfHkV34`, `LbhH9NeB93I`, `XuVY56j7GM0`, `fIzsqjyD5oY`, `sRn6qePT54Q`,
     `-0Vv7HKZaBM`, `yl3T9brJay4`, `xjVhrq2KPJA`.
   - Follow: `libSceNpCppWebApi/Export.cpp:1792-2316`.
   - Gate (R32): resolve each NID through the real `SymbolDatabase` after `InitAll`.
9. **Directory `st_blksize`** (da7581eec)
   - NIDs: `sceKernelStat` `eV9wAD2riIA`, `sceKernelFstat` `kBwCPsYX-m4`, `stat` `E6ao34wPw+U`, `fstat` `mqQMh1zPPT8`.
   - Directories report 0x10000; files are unchanged.
   - Follow: `libkernel/File/src/NativeStat.cpp:224`. Source: the commit's PS4 Pro 10.71 measurement (not a PS5).
   - Ours: `kernel/fileSystem.cpp:973, 1051`.
   - Test: `stat("/app0")` gives 0x10000.
10. **ENAMETOOLONG** (2de34f87b)
    - Applies to `sceKernelStat`, `sceKernelUnlink` `AUXVxWeJU-A`, `sceKernelMkdir` `1-LFLmRFxxM`, `sceKernelRmdir`
      `naInUjYt3so` and `sceKernelRename` `52NcYU9+lEo`.
    - A path of 1024 bytes or more, or a component over 255 bytes, gives 0x8002003F.
    - Drop mkdir's whole-path > 255 check (`kernel/fileSystem.cpp:1615`). Reuse only the length part of `CheckGuestPath`
      (`:1111`).
    - Source: FreeBSD MAXPATHLEN/NAME_MAX. Follow `libc/src/General.cpp:386-388`.
    - Test: paths of 1024 and 1100 bytes fail; a 300-byte path with short components works.
11. **x87 control word** (8b626e307)
    - Execute `fldcw` with 0x037f at the start of `RunThread` (`kernel/pthread.cpp:3485`), before guest code.
    - Follow: `libkernel/Pthread/src/Thread.cpp:65, 891`. Source: the FreeBSD 11 thread start state; not console-measured.
    - Test: the creator sets 0x027f, and the child reads 0x037f with `fnstcw`.
12. **SaveData Initialize aliases** (bc6a5e4ea)
    - Register `l1NmDeDpNGU` (Initialize2) and `ZkZhskCPXFw` (Initialize) to `SaveDataInitialize3` in both tables
      (`libs/libSaveData.cpp:1260, 1291`).
    - Sources: shadPS4 `savedata.cpp` L1228-1238 @0614ce32 and fpPS4 `ps4_libscesavedata.pas` L291-304 (debt
      `libSceSaveData.native.md:23`).
    - Test: resolve both NIDs in both modules; each returns 0.
13. **`sceNpSetGamePresenceOnlineA`** `C0gNCiRIi4U` (72ccb10bd)
    - Signature `(int reqId, int userId, uint32 presence)`.
    - userId −1 or reqId 0 gives 0x80550003; an unknown request gives 0x80550014; a live request goes through the signed-out
      completion and gives 0x80550006.
    - Add it next to `NpCheckNpReachability` in `libs/network.cpp`, and register it in the loaded table (`libs/libNet.cpp:1447`).
    - Follow: `libSceNpManager/Export.cpp:83, 862`. Source: shadPS4 2183807e59 `np_manager.cpp` L1092-1119.
14. **Videodec2 HEVC aliases** (28f157cc6)
    - Register `pu4kxXkYz3E` (CreateHevcDecoder) to `CreateDecoder` and `krChT8KBUDU` (QueryHevcDecoderMemoryInfo) to
      `QueryDecoderMemoryInfo`, forwarding the arguments unchanged (`libs/libVideoDec2.cpp:659-660`).
    - Source: shadPS4 `videodec2.cpp:327-339`. Follow: `libSceVideodec2/Export.cpp:528-534`.
15. **Http2 SSL options on a context** (754aad4e9)
    - NIDs: `sceHttp2SslEnableOption` `EWcwMpbr5F8`, `sceHttp2SslDisableOption` `B37SruheQ5Y`.
    - Accept a context id (store the flags in `Http2Context`, `libs/libNet.cpp:686`). A bogus id keeps 0x817B1100.
    - Templates made afterwards copy the context's flags (`:763`). This inheritance is unverified, so put it behind the same
      switch.
    - Source: prosper `hle_http2.cpp` L461-478; a title sets these on its context (AnyPS5 #13715).
16. **libSceNet IPv6 data objects** (0918719f6): add `LIB_OBJECT`s next to `ZRAJo-A-ukc` (`libs/libNet.cpp:190`):

    | NID | Name | Value |
    |---|---|---|
    | `GAtITrgxKDE` | `sce_net_in6addr_any` | `::` |
    | `P3AeWBvPrkg` | loopback | `::1` |
    | `PgNI+j4zxzM` | nodelocal_allnodes | `ff01::1` |
    | `84MgU4MMTLQ` | linklocal_allnodes | `ff02::1` |
    | `2uSWyOKYc1M` | linklocal_allrouters | `ff02::2` |
    | `XCuA-GqjA-k` | `in6addr_loopback` | `::1` |

    - Skip `sce_net_dummy`, whose source is unclear.
    - Values: RFC 4291. Test: compare the bytes.
17. **VideoOut SLOT_OCCUPIED** `rKBUtgRrtbk` (a8661988e)
    - Under `ctx->mutex`, run the slot loop (`graphics/presentation/videoOut.cpp:1498-1502`) before the set check (`:1495`).
      An occupied slot gives 0x80290010 and changes nothing.
    - Follow: `libSceVideoOut/src/Buffer.cpp:42-46`. Source: the EVO Player measurement in debt `libSceVideoOut.md`.
    - Nothing here submits to the GPU. The test needs a DriverState that runs without a window.
18. **AvPlayer frame SAR** (5fdc6dbd4)
    - Applies to `o3+RWnHViSg` and `JdksQu8pNdQ`, at `libs/avPlayer.cpp:1532`.
    - The frame's `aspect_ratio` is `av_q2d(frame SAR)` when num and den are above 0, else 1.0. Stream info keeps
      width/height×SAR.
    - Follow: `libSceAvPlayer/src/Source.cpp:1090` as of 5fdc6dbd4. Do not take the stream-SAR fallback from the excluded
      0b41d81e2. Check shadPS4's no-SAR value first.
    - Test: decode a generated H.264 clip with SAR 1:1; the frame reports 1.0.

## 3. Per library

These are AnyPS5 modules that map to a library we host, by name or by an alias checked through NID overlap
(`r1-anyps5-report.py` ALIAS).

Column definitions:
- **live**: AnyPS5 NIDs our host exports at run time.
- **dead**: NIDs registered only in a table InitAll never loads.
- **Impl. missing**: implemented in AnyPS5 and not exported live by us; the number in brackets is how many of those sit in
  dead tables.
- **c / d / l**: constant / data / logic.
- **Later size**: logic lines ÷ 150 plus constants ÷ 200, in days.

Every row is in `r1-anyps5-missing.tsv`.

| AnyPS5 module | Exports | Impl. | Live | Dead | Impl. missing (dead) | c / d / l | Logic lines | Later size | Note |
|---|---|---|---|---|---|---|---|---|---|
| libc | 1558 | 1554 | 54 | 0 | **1500** (0) | 79 / 0 / 1421 | 8782 | L ~58.9 d | titles ship libc.prx |
| libSceNpCppWebApi | 1362 | 1074 | 137 | 0 | **953** (0) | 615 / 0 / 338 | 1180 | L ~10.9 d | incl. the 10 SessionManager V2 (0402 §1) |
| libkernel | 770 | 725 | 393 | 0 | **332** (0) | 16 / 0 / 316 | 3900 | L ~26.1 d |  |
| libSceNpCommon | 429 | 289 | 0 | 28 | **289** (28) | 49 / 0 / 240 | 1400 | L ~9.6 d |  |
| libSceCesCs | 287 | 269 | 5 | 0 | **264** (0) | 2 / 0 / 262 | 937 | L ~6.3 d |  |
| libkernel_sys | 829 | 171 | 13 | 0 | **167** (0) | 38 / 0 / 129 | 1120 | L ~7.7 d | system-process module |
| libSceSystemService | 618 | 150 | 12 | 0 | **138** (0) | 49 / 0 / 89 | 353 | L ~2.6 d |  |
| libSceNpTus | 142 | 136 | 0 | 142 | **136** (136) | 0 / 0 / 136 | 784 | L ~5.2 d |  |
| libSceJson2 | 219 | 218 | 90 | 0 | **128** (0) | 13 / 4 / 111 | 437 | L ~3.0 d |  |
| libSceAgc | 240 | 235 | 124 | 0 | **111** (0) | 41 / 0 / 70 | 425 | L ~3.0 d | GPU |
| libSceGnmDriverForNeoMode | 139 | 86 | 0 | 134 | **86** (86) | 53 / 0 / 33 | 320 | L ~2.4 d | GPU |
| libSceLibcInternal | 992 | 89 | 5 | 0 | **84** (0) | 3 / 3 / 78 | 578 | L ~3.9 d |  |
| libSceFont | 240 | 153 | 70 | 0 | **83** (0) | 2 / 0 / 81 | 635 | L ~4.2 d |  |
| libSceNet | 239 | 99 | 28 | 0 | **71** (0) | 4 / 7 / 60 | 980 | L ~6.6 d |  |
| libSceAgcDriver | 146 | 95 | 26 | 0 | **70** (0) | 53 / 0 / 17 | 85 | M ~0.8 d | GPU |
| libSceUsbd | 61 | 61 | 0 | 61 | **61** (61) | 0 / 0 / 61 | 524 | L ~3.5 d |  |
| libSceUlt | 94 | 81 | 23 | 0 | **58** (0) | 0 / 0 / 58 | 842 | L ~5.6 d |  |
| libSceAmpr | 150 | 147 | 92 | 0 | **56** (0) | 2 / 0 / 54 | 190 | L ~1.3 d | 26 of them in e4 (other port) |
| libSceHttp | 123 | 94 | 38 | 0 | **56** (0) | 13 / 0 / 43 | 537 | L ~3.6 d |  |
| libSceCamera | 125 | 54 | 0 | 76 | **54** (54) | 10 / 0 / 44 | 190 | L ~1.3 d |  |
| libSceNpManager | 553 | 77 | 29 | 25 | **48** (21) | 23 / 0 / 25 | 159 | L ~1.2 d |  |
| libScePad | 214 | 69 | 22 | 0 | **47** (0) | 5 / 0 / 42 | 274 | L ~1.9 d |  |
| libSceAudioOut | 192 | 70 | 35 | 0 | **35** (0) | 6 / 0 / 29 | 197 | L ~1.3 d |  |
| libSceSsl | 55 | 38 | 4 | 0 | **34** (0) | 3 / 0 / 31 | 433 | L ~2.9 d |  |
| libSceRazorCpu | 42 | 34 | 1 | 34 | **33** (32) | 24 / 0 / 9 | 64 | M ~0.5 d |  |
| libSceHmd | 187 | 32 | 0 | 137 | **32** (17) | 15 / 0 / 17 | 81 | M ~0.6 d |  |
| libSceNetCtl | 105 | 42 | 10 | 0 | **32** (0) | 11 / 0 / 21 | 77 | M ~0.6 d |  |
| libSceRudp | 35 | 34 | 3 | 0 | **31** (0) | 0 / 0 / 31 | 525 | L ~3.5 d |  |
| libSceAudio3d | 32 | 32 | 7 | 0 | **25** (0) | 0 / 0 / 25 | 320 | L ~2.1 d |  |
| libSceRtc | 52 | 51 | 26 | 0 | **25** (0) | 3 / 0 / 22 | 168 | L ~1.1 d |  |
| libSceVideoOut | 266 | 62 | 40 | 0 | **25** (0) | 0 / 0 / 25 | 195 | L ~1.3 d |  |
| libSceNpTrophy | 110 | 24 | 0 | 86 | **24** (24) | 7 / 0 / 17 | 197 | L ~1.3 d |  |
| libSceSaveData.native | 119 | 52 | 29 | 0 | **24** (0) | 11 / 0 / 13 | 97 | M ~0.7 d |  |
| libSceNgs2.native | 63 | 49 | 26 | 37 | **23** (23) | 0 / 0 / 23 | 361 | L ~2.4 d |  |
| libSceHttp2 | 71 | 48 | 29 | 1 | **22** (0) | 1 / 0 / 21 | 176 | L ~1.2 d |  |
| libSceGameLiveStreaming | 47 | 22 | 2 | 45 | **20** (20) | 0 / 0 / 20 | 124 | M ~0.8 d |  |
| libSceVoice | 36 | 35 | 16 | 14 | **20** (14) | 1 / 0 / 19 | 183 | L ~1.2 d |  |
| libSceAppContent | 40 | 27 | 8 | 0 | **19** (0) | 0 / 0 / 19 | 128 | M ~0.9 d |  |
| libSceAudioPropagation | 41 | 24 | 6 | 0 | **18** (0) | 0 / 0 / 18 | 199 | L ~1.3 d |  |
| libSceContentSearch | 29 | 19 | 1 | 0 | **18** (0) | 8 / 0 / 10 | 67 | M ~0.5 d |  |
| libSceNpEntitlementAccess | 25 | 25 | 8 | 0 | **17** (0) | 10 / 0 / 7 | 45 | M ~0.3 d |  |
| libSceNpParty | 26 | 15 | 0 | 26 | **15** (15) | 2 / 0 / 13 | 48 | M ~0.3 d |  |
| libSceNpSessionSignaling | 31 | 18 | 4 | 0 | **14** (0) | 0 / 0 / 14 | 100 | M ~0.7 d |  |
| libScePsml_debug | 31 | 25 | 14 | 0 | **13** (0) | 10 / 0 / 3 | 25 | M ~0.2 d |  |
| libSceVoiceQoS | 25 | 14 | 1 | 0 | **13** (0) | 0 / 0 / 13 | 102 | M ~0.7 d |  |
| libSceAudioIn | 48 | 14 | 2 | 0 | **12** (0) | 3 / 0 / 9 | 51 | M ~0.4 d |  |
| libSceFontFt | 21 | 14 | 2 | 0 | **12** (0) | 0 / 0 / 12 | 36 | M ~0.2 d |  |
| libSceNpWebApi2 | 45 | 34 | 22 | 0 | **12** (0) | 4 / 0 / 8 | 50 | M ~0.4 d |  |
| libSceCompanionHttpd | 17 | 11 | 0 | 17 | **11** (11) | 3 / 0 / 8 | 65 | M ~0.4 d |  |
| libSceMove | 21 | 11 | 0 | 11 | **11** (11) | 0 / 0 / 11 | 62 | M ~0.4 d |  |
| libSceVideoRecordingP | 27 | 11 | 0 | 1 | **11** (1) | 8 / 0 / 3 | 26 | M ~0.2 d |  |
| libSceUserService | 617 | 27 | 17 | 0 | **10** (0) | 4 / 0 / 6 | 41 | M ~0.3 d |  |
| libSceVrTracker | 39 | 10 | 0 | 39 | **10** (10) | 0 / 0 / 10 | 77 | M ~0.5 d |  |
| libSceContentExport | 22 | 10 | 1 | 0 | **9** (0) | 0 / 0 / 9 | 56 | M ~0.4 d |  |
| libSceAjm.native | 52 | 40 | 32 | 0 | **8** (0) | 1 / 0 / 7 | 124 | M ~0.8 d |  |
| libSceWebBrowserDialog | 14 | 10 | 2 | 12 | **8** (8) | 0 / 0 / 8 | 78 | M ~0.5 d |  |
| libSceInvitationDialog | 9 | 7 | 0 | 9 | **7** (7) | 0 / 0 / 7 | 68 | M ~0.5 d |  |
| libSceNpCommerce | 12 | 12 | 5 | 0 | **7** (0) | 4 / 0 / 3 | 19 | S ~0.1 d |  |
| libSceNpGameIntent | 26 | 11 | 4 | 0 | **7** (0) | 2 / 0 / 5 | 33 | M ~0.2 d |  |
| libSceNpSnsFacebookDialog | 7 | 7 | 0 | 1 | **7** (1) | 0 / 0 / 7 | 38 | M ~0.3 d |  |
| libSceScreenShot | 13 | 7 | 0 | 13 | **7** (7) | 4 / 0 / 3 | 13 | S ~0.1 d |  |
| libSceNpAuth | 14 | 14 | 8 | 5 | **6** (5) | 0 / 0 / 6 | 35 | M ~0.2 d |  |
| libSceTextToSpeech2 | 14 | 8 | 2 | 0 | **6** (0) | 6 / 0 / 0 | 0 | S ~<0.1 d |  |
| libSceCompanionUtil | 5 | 5 | 0 | 5 | **5** (5) | 5 / 0 / 0 | 0 | S ~<0.1 d |  |
| libSceImeDialog | 14 | 13 | 8 | 0 | **5** (0) | 1 / 0 / 4 | 21 | S ~0.1 d |  |
| libScePlayGo | 24 | 23 | 18 | 0 | **5** (0) | 2 / 0 / 3 | 19 | S ~0.1 d |  |
| libSceZlib | 5 | 5 | 0 | 5 | **5** (5) | 0 / 0 / 5 | 68 | M ~0.5 d |  |
| libSceJpegEnc | 4 | 4 | 0 | 4 | **4** (4) | 0 / 0 / 4 | 44 | M ~0.3 d |  |
| libSceMouse | 29 | 8 | 4 | 0 | **4** (0) | 0 / 0 / 4 | 12 | S ~<0.1 d |  |
| libScePlayerInvitationDialog | 7 | 7 | 3 | 0 | **4** (0) | 0 / 0 / 4 | 28 | M ~0.2 d |  |
| libSceSysmodule | 21 | 10 | 7 | 0 | **4** (0) | 0 / 0 / 4 | 80 | M ~0.5 d |  |
| libSceVideodec2 | 29 | 15 | 11 | 0 | **4** (0) | 0 / 0 / 4 | 14 | S ~<0.1 d |  |
| libSceContentDelete | 8 | 4 | 1 | 0 | **3** (0) | 0 / 0 / 3 | 17 | S ~0.1 d |  |
| libSceDiscMap | 6 | 3 | 0 | 5 | **3** (2) | 0 / 0 / 3 | 25 | M ~0.2 d |  |
| libSceIme | 64 | 16 | 13 | 39 | **3** (3) | 1 / 0 / 2 | 17 | S ~0.1 d |  |
| libSceNpPartner001 | 4 | 3 | 0 | 4 | **3** (3) | 0 / 0 / 3 | 17 | S ~0.1 d |  |
| libSceRegMgr | 74 | 3 | 1 | 0 | **3** (0) | 0 / 0 / 3 | 9 | S ~<0.1 d |  |
| libSceSharePlay | 25 | 5 | 2 | 21 | **3** (2) | 0 / 0 / 3 | 24 | M ~0.2 d |  |
| libSceErrorDialog | 8 | 8 | 6 | 0 | **2** (0) | 2 / 0 / 0 | 0 | S ~<0.1 d |  |
| libSceKeyboard | 28 | 8 | 6 | 0 | **2** (0) | 0 / 0 / 2 | 6 | S ~<0.1 d |  |
| ulobjmgr | 4 | 2 | 0 | 4 | **2** (2) | 0 / 0 / 2 | 6 | S ~<0.1 d |  |
| libSceAudiodec.native | 16 | 1 | 0 | 0 | **1** (0) | 0 / 0 / 1 | 8 | S ~<0.1 d |  |
| libSceCommonDialog | 28 | 2 | 1 | 0 | **1** (0) | 0 / 0 / 1 | 3 | S ~<0.1 d |  |
| libSceFiber | 16 | 16 | 15 | 0 | **1** (0) | 0 / 0 / 1 | 6 | S ~<0.1 d |  |
| libSceSystemGesture | 24 | 23 | 22 | 0 | **1** (0) | 1 / 0 / 0 | 0 | S ~<0.1 d |  |

**Nothing implemented and missing** (live/dead), in 29 modules:

| Module | Live / dead | Module | Live / dead |
|---|---|---|---|
| Acm | 12/0 | NpUniversalDataSystem | 41/0 |
| AddressSanitizer | 8/0 | PlayGoDialog | 7/0 |
| AgcVsh | 84/0 | PngDec | 5/0 |
| Ajm | 0/0 | PngEnc | 4/0 |
| Audiodec | 6/0 | Psml | 0/0 |
| AvPlayer | 28/0 | Random | 1/0 |
| AvPlayer.native | 0/0 | Remoteplay | 3/38 |
| Font.native | 0/0 | SaveData | 0/0 |
| GameUpdate | 7/0 | SaveDataDialog | 0/0 |
| LoginDialog | 7/0 | SaveDataDialog.native | 10/0 |
| MsgDialog | 9/0 | Share | 17/0 |
| MsgDialog.native | 10/0 | Share.native | 0/0 |
| Ngs2 | 0/2 | SigninDialog | 7/0 |
| NpTrophy2 | 18/0 | VideoRecording | 0/0 |
| | | VideoRecording.native | 0/0 |

**Totals**

| Scope | Hosted modules | Exports | Impl. | Live | Dead | Impl. missing | of which dead | Const | Data | Logic | Logic lines |
|---|---|---|---|---|---|---|---|---|---|---|---|
| All | 114 | 13,507 | 7,350 | 1,930 | 1,081 | 5,553 | 618 | 1,233 | 14 | 4,306 | 29,840 |
| Without libc and GPU | | | | | | 3,786 | 532 | 1,007 | 14 | 2,765 | 20,228 |

Later-rest estimate, without libc and GPU: about 140 working days. Taking out the 18 e4-now items and the 26 Ampr exports in
flight changes it by less than a day.

**Outside this scope.** 292 AnyPS5 modules we do not host at all have 24,425 exports, 3,815 of them implemented
(`_work\nothosted.tsv`). Most implemented ones are in NKWebKit 1,300, LibreSsl3 416, Hmd2 273, VrTracker2 178, LibreSsl 167,
GLSlimVSH 139, Fios2 106, FreeType 96 and NpScoreRanking 51. These are new-library ports, a separate decision.

## 4. Commit review summary

Commits after the port points, one row per (library, commit), by group:

| Group | Libraries | Rows |
|---|---|---|
| A | libkernel, libkernel_sys | 203 |
| B | libc, LibcInternal, Ult, Rtc, Sysmodule, Ampr, CesCs, Font, … | 212 |
| C | VideoOut, AudioOut, Pad, Ngs2, AvPlayer, Videodec2, Ime, Voice, … | 273 |
| D1 | Json2, Np*, Net, Http, Http2, Ssl, NetCtl, Rudp | 229 |
| D2 | SystemService, UserService, SaveData, AppContent, PlayGo, dialogs, … | 113 |

Rows by class:

| Class | Rows | Note |
|---|---|---|
| new-export | 302 | the inventory covers them |
| internal | 232 | AnyPS5's own relinker, tables, host input/volume features and IME |
| test-doc-build | 177 | |
| excluded-provenance | 120 | |
| platform | 72 | Windows, macOS, WebAssembly |
| in-e4 | 10 | |
| shared | 117 | 30 match, 79 missing, 8 partial |

**Provenance**
- **Excluded as in 0402.** Values sourced from an SDK reference or from disassembly or decompilation of firmware modules.
  Examples: the GamePresets null-pointer order, the NpCppWebApi bundled-module addresses (08fa66176, 705487269, fcf9754a2,
  c207cb884, f21a6b321), Acm's job layout and RazorCpu.
- **Excluded by B, needs confirmation.** Values read from titles' own `libc.prx`: d0725a852, 1c8ac1874 and abbd3bd22.
- **Open for the maintainer.** Should values from firmware 13.42 modules *run* natively or under an emulator (BunnyFl's
  runs, the ngs2 oracle, prosper's module reading) count as measurements or be excluded like disassembly?
  - They need a dumped module, and the sub-agents differed on them.
  - I kept them out of e4-now: candidates #35 and #40, and about 20 rows marked excluded in `C.tsv`.
- **Accepted.** Console measurements by AnyPS5's authors (payloads, ptrace in retail titles, hw-oracle), prosper's console
  oracle data, FreeBSD, shadPS4, fpPS4 and RFCs.

## 5. Limits

- **GPU libraries.** The 505 Agc, AgcDriver and GnmDriverForNeoMode commits were not compared. Ours runs the module pack's
  LLE Agc; the GPU-side facts are in 0402 §3.
- **Export classifier.** "Implemented" is a static body classifier. A *logic* body may still throw for some inputs. A small
  number of C-linkage helper names may be counted as exports (e.g. `DirectMemoryAliased`); they hash to NIDs no title imports.
- **C++ data exports.** Mangled-name objects (`_ZTI*`/`_ZTV*`, `numpunct::id`) are not in the TSV; only `extern "C"` data is.
- **"Live" scan.** It follows `LIB_LOAD`/`Init*(s)` calls by last name component, an over-approximation when two namespaces
  share a name.
- **Loader resolution.** A NID registered under a different library name than the title imports is counted as present. R32
  applies before any claim.
- **Unverified on the box.** Nothing here was run on the box or built. The sub-agents' verdicts were spot-checked, not
  re-derived one by one.

## Files

All under `...\scratchpad\0405\`:

| File | Contents |
|---|---|
| `r1-anyps5.md` | this report |
| `r1-anyps5-missing.tsv` | 11,577 rows. Columns: library, nid, name, AnyPS5 file:line, implemented yes/no, kind, body lines, our unloaded table |
| `r1-anyps5-inventory.py` | AnyPS5 export inventory |
| `r1-anyps5-loaded.py` | which of our registrations InitAll reaches |
| `r1-anyps5-report.py` | tables and TSV; `--commits` regenerates `_work\commits\` |
| `_work\verdicts\{A,B,C,D1,D2}.tsv` | per-commit verdicts |
| `_work\BRIEF.txt` | the sub-agents' brief |
| `_work\groups\*.txt` | commit lists |
| `_work\libtable.tsv` | per-library numbers |
| `_work\nothosted.tsv` | modules we do not host |
| `_work\inv.json`, `_work\loaded.json` | raw data |
| `_work\aps5.git`, `_work\git-*.git` | private object stores that borrow the clone's objects (~26 MB of fetched blobs; safe to delete) |
| `_work\shared_missing.txt` | the 87 shared missing/partial rows in one list |
