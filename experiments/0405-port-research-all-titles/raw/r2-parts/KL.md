# KL: KytyPS5 @ dfec14a vs OURS -- loader and process-level services

## 1. Method

Diffed (`diff --strip-trailing-cr -w $R/kps5/src/<f> OURS/<f>`) and read every KytyPS5-only hunk of:
loader/runtimeLinker.cpp/.h, systemContent.cpp/.h, x64InstructionEmulator.cpp/.h, gamePatch.cpp/.h, elf.cpp,
jit.h, symbolDatabase.cpp/.h, timer.cpp/.h; libs/libs.cpp, libSysmodule.cpp, libAppContent.cpp,
libSystemService.cpp, systemService.h, libUserService.cpp. Read the KytyPS5-only files loader/loadExec.cpp,
loader/guestInstructionPatcher.cpp/.h, loader/additionalContent.cpp/.h (and common/additionalContent.cpp, which they
use). For sceKernelLoadStartModule / StopUnloadModule / Dlsym / GetModuleInfo* I also compared the matching
functions in libs/libKernel.cpp (Dlsym and both GetModuleInfo* are byte-identical apart from whitespace; this may
overlap the libKernel part). Introducing commits come from `git log -S` / `git log -- <file>` on the shallow clone;
commits in range: 2f885e2 (guest TSC), f12fc20 and 06ab430 (SystemService stubs), 97bef29 (addcont duplicate
mounts), 66e21a6 (addcont), 651ef73 (Trinity), 09753bf/0a14091 (memory sizing, already in e4), 906d255 (loadExec
exit code). Everything else is "pre-4644c52 (history not in clone)".
Noise, no rows: timer.h/.cpp (subsystem macro vs Lifecycle struct), symbolDatabase (fmt/magic_enum vs
Common helpers; the extra `vaddr` filter of FindByNid serves KL09 only), elf.cpp (ours has an extra PS5 SELF variant
that KytyPS5 lacks), systemContent icon-path type, PLGO/PLGX constants (same values), `CoreAccess::Unknown` returns
false in KytyPS5 vs EXIT in ours (both end in termination), Context abstraction / macOS paths in the x64 emulator.
Handed to the GPU part, no row: KytyPS5's exception handler skips faulting SRT-walker loads (bdf48dc,
`X64InstructionEmulator::SkipLoad`, runtimeLinker.cpp@dfec14a:676-679) -- shader recompiler side.
Our host is AMD Zen 2 (BC-250); x64-emulation and "AMD CPU" items only fire on hosts that lack those instructions,
which the value notes say, but they stay candidates under the 11-03 rule.

## 2. Table (ranked by value over cost)

| ID | What | Source | Licence | Ours | Effort | Risk | Class | Value note |
|---|---|---|---|---|---|---|---|---|
| KL01 | TLS-load stubs keep RFLAGS: `lea rsp,[rsp-0x80]`+`nop` / `lea rsp,[rsp+0x80]` in place of `sub/add rsp,0x80` in TlsRegStub and SafeCall | src/loader/jit.h @ dfec14a:43-117; pre-4644c52 (history not in clone) | GPL-2.0 | differs: loader/jit.h:89-161 (`sub rsp,0x80` before pushfq at 127, `add rsp,0x80` after popfq at 157-158; TlsRegStub 114-116) | S | L: byte layout of two stubs; offsets of SetFunc/SetOutputReg stay the same | e4-now | Correctness for every title whose main ELF has `mov reg,fs:[0]`: the original instruction leaves flags alone, our replacement returns with the flags of `add rsp,0x80`; any cmp/test...jcc that the compiler scheduled across a TLS load takes the wrong branch |
| KL02 | TLS patch writes the call at the `64 48 8B` instruction, not over leading 0x66 bytes; Call9 = `48 E8 rel32 48 89 C0` (REX.W so a kept 0x66 cannot make it `callw` on AMD); skip segments < 9 bytes | src/loader/jit.h @ dfec14a:21-41; src/loader/runtimeLinker.cpp @ dfec14a:968-1016 (comment 1007-1009); pre-4644c52 | GPL-2.0 | differs: loader/jit.h:68-87 (`E8 rel32 48 89 C0 90`); loader/runtimeLinker.cpp:1519-1567 (writes at `ptr`, i.e. over the 0x66 bytes, NOP-pads; no `size>=9` guard, `end_ptr` underflows for tiny segments) | S | M: touches every title's TLS patching; a mistake shows at boot | e4-now | Our raw byte scan also takes a 0x66 that ends the PREVIOUS instruction (e.g. `cmp al,0x66` = `3C 66`) as a prefix and overwrites it: silent code corruption before the TLS load |
| KL03 | sceUserServiceGetUserName returns error codes instead of aborting | src/libs/libUserService.cpp @ dfec14a:113-132; pre-4644c52 | GPL-2.0 | differs: libs/libUserService.cpp:116-127 (`EXIT_NOT_IMPLEMENTED` on unknown user id and on size < 5; no null check) | S | L | e4-now | Crash fix: a title asking the name of user 0xFF (system), -1 or a stale id, or passing a short buffer, kills the emulator |
| KL04 | UserService login set consistent: GetEvent sends Login only for logged-in users; per-user getters return NOT_LOGGED_IN for the others; GetUserNumber = player+1 | src/libs/libUserService.cpp @ dfec14a:44-51, 75-93, 95-111, 134-148 (and the getters 150-280 using GetLoggedInPlayer); pre-4644c52 | GPL-2.0 | differs: libs/libUserService.cpp:78-92 (Login events for all of 1000..1003 while GetLoginUserIdList 94-113 reports only KYTY_BC5_LOGIN_USERS, default 1), 24-26 IsLocalUser accepts 1000..1003 (used at 135,150,171,187,202,218,234,250,266), 139 `*number = 1` | S | M: pad/user binding of the two titles (the ASTRO BOT note at 98-102); re-run the pad checks | e4-now | Today a title that follows login events opens users 1001-1003 the list says are not logged in, exactly the second-controller problem the list fix solved; GetUserNumber says 1 for every user |
| KL05 | sceSystemServiceParamGetInt id 400 = system language | src/libs/libSystemService.cpp @ dfec14a:34, 118-119 (comment cites title PPSA01325); pre-4644c52 | GPL-2.0 | differs: libs/libSystemService.cpp:113-131, id 400 hits `default` -> 0 | S | L | e4-now | Wrong result: a title reading id 400 gets 0 = Japanese |
| KL06 | Sysmodule keeps load state: refcounted Load, Unload of a not-loaded id -> 0x805A1001, IsLoaded -> 0x805A1001 unless loaded | src/libs/libSysmodule.cpp @ dfec14a:24-59, 65-118; pre-4644c52 | GPL-2.0 | differs: libs/libSysmodule.cpp:25-63 (all return 0) | S | M: a title that calls IsLoaded first now sees UNLOADED and loads; one that unloads twice gets an error | e4-now | Wrong result for IsLoaded/Unload. KytyPS5's native table (id 0x0115 -> /app0/sce_module/libSceNpCppWebApi.prx via LoadStartModule) is already covered by our boot preload (runtimeLinker.cpp:2310-2410), so the spec leaves it out |
| KL07 | sceKernelStopUnloadModule on an unknown handle returns KERNEL_ERROR_ESRCH | src/libs/libKernel.cpp @ dfec14a:1272-1276; pre-4644c52 | GPL-2.0 | differs: libs/libKernel.cpp:1362-1365 returns OK | S | L | e4-now | Wrong result; may overlap the libKernel part |
| KL08 | Module load refcount: second LoadStartModule of a loaded PRX increments `load_count`, StopUnload only decrements while > 1 | src/libs/libKernel.cpp @ dfec14a:1228-1233, 1245, 1278-1281; src/loader/runtimeLinker.h @ dfec14a:124; pre-4644c52 | GPL-2.0 | differs: libs/libKernel.cpp:1319-1325 (returns the handle, no count), 1348-1390 (first StopUnload unloads) | S | M: a module still in use by another loader of it is no longer torn down; test needs a PRX fixture, so not e4-now | later | Data/crash fix for titles that load the same PRX from two places and unload one (module_stop + unmap under the other user) |
| KL09 | Every LoadStartModule re-runs relocation of ALL loaded programs for still-unresolved records (rela_bits); unload re-resolves importers that pointed into the unloaded module | src/loader/runtimeLinker.cpp @ dfec14a:876-926, 1096-1167, 1974-1978, 2019-2055; src/loader/symbolDatabase.cpp @ dfec14a:68-75; pre-4644c52 | GPL-2.0 | differs: loader/runtimeLinker.cpp:1658-1665 RelocateProgram relocates only the new program; unresolved FUNC imports late-resolve in the stub thunk (320-344), but OBJECT imports stay `g_invalid_memory` (1360) and NOTYPE keep the ELF value (1369). Unload (1667-1683) already re-runs RelocateAll | S (ours: RelocateProgram -> RelocateAll(), our imports-only pass 2977-2982 already re-resolves) | M: rewrites GOT slots of every module while guest threads run (same values except stub -> real); needs two-PRX fixture to test | later | Data imports of an earlier module that a later-loaded PRX exports fault on first access today |
| KL10 | Guest stack walk probes every frame with IsReadableRange, stops on non-increasing `next`, uses rsp as window base for the libc abort trace | src/loader/runtimeLinker.cpp @ dfec14a:544-577, 1522-1537; src/libs/libC.cpp @ dfec14a:225; pre-4644c52 | GPL-2.0 | differs: loader/runtimeLinker.cpp:716-758 (dereferences frames unchecked), 2062-2066 StackTrace(rbp) only, used at 1068 inside the exception handler; libs/libC.cpp:233 | S | L | e4-now | Diagnostics only: a bad frame chain faults inside our crash reporter, losing the report the session needs |
| KL11 | x64 trap emulation fixes: RDPID decoded properly (dest reg, TSC_AUX, 4/5-byte length); SSE4a register forms `66 0F 79` EXTRQ / `F2 0F 79` INSERTQ; CLWB (`66 0F AE /6` mem) as CLFLUSH | src/loader/x64InstructionEmulator.cpp @ dfec14a:585-649 (SSE4a), 651-715 (RDPID, CLWB); pre-4644c52 | GPL-2.0 | differs: loader/x64InstructionEmulator.cpp:975-981 (Linux) / 657-662 (Win) RDPID matches any `F3 0F C7 xx`, writes RAX=0, advances 3 bytes; 802-859 / 500-556 SSE4a immediate forms only; no CLWB (983-989 only `0F 08/09`) | S | L: only reached on SIGILL | e4-now | No effect on the BC-250 (Zen 2 has RDPID, SSE4a, CLWB natively); correct on other hosts, and our RDPID path is wrong where it is reached |
| KL12 | sceSystemServiceGetNoticeScreenSkipFlag from a `--skip-notice-screen` flag (default false) | src/libs/libSystemService.cpp @ dfec14a:231-241; src/main.cpp @ dfec14a:110, 232; src/common/emulatorConfig.h @ dfec14a:101, 172; emulatorConfig.cpp:236-238; pre-4644c52 | GPL-2.0 | differs: libs/libSystemService.cpp:241 `*value = false` | S | L: default unchanged | e4-now | Startup flag to skip logos/notices in titles that honour it |
| KL13 | Boot loads and starts only /app0/sce_module/libc.prx; every other PRX waits for the title's sceKernelLoadStartModule and gets the title's args/argp in module_start | src/loader/runtimeLinker.cpp @ dfec14a:1268-1281; pre-4644c52 | GPL-2.0 | differs: loader/runtimeLinker.cpp:1784-1792 PreloadAdjacentPrograms (2310-2410: every .prx/.sprx in root, sce_module, sce_modules) + StartAllModules (2128-2157) with args 0/NULL before main; LoadStartModule of a preloaded PRX then skips module_start (libKernel.cpp:1319-1325) | M | H: changes the boot of both titles (init order, module_start args) | later | Fidelity of init order and module_start arguments; our model runs PRX initialisers before main |
| KL14 | Symbol resolve checks every program exporting the lib+module, first that has the record wins (sets bind_self) | src/loader/runtimeLinker.cpp @ dfec14a:1388-1405; pre-4644c52 | GPL-2.0 | differs: loader/runtimeLinker.cpp:1898-1905 FindProgram (2999-3012) returns the first match only; the NID fallback (lambda 1860, used 1907-1911) usually finds it anyway, without bind_self | S | L | later | Corner case: two loaded programs exporting the same lib/module |
| KL15 | Fault report: guest thread name, 32 stack qwords; DebugCounters (EmulatedInstructions, GpuFaults, UnresolvedImportCalls) | src/loader/runtimeLinker.cpp @ dfec14a:658, 673, 682-716, 195; pre-4644c52 | GPL-2.0 | differs: loader/runtimeLinker.cpp:1003-1012 (16 qwords), 1070 numeric thread id; no counters | S | L | later | Diagnostics |
| KL16 | sceSystemServiceLoadExec (NID JoBqSQt1yyA): validate `/app0/` path (else SYSTEM_SERVICE_ERROR_PARAMETER), argv <= 4096 bytes, re-exec the emulator with `--guest-exec <path> args...`; guest argv passed to main | src/loader/loadExec.cpp @ dfec14a:44-191 (906d255 2026-10-24 "launcher: option to close the terminal after a clean exit" changed the exit); src/libs/libSystemService.cpp @ dfec14a:103-106, 588; src/main.cpp:298-301; src/loader/runtimeLinker.cpp:1286-1296; runtimeLinker.h:17-21; pre-4644c52 otherwise | GPL-2.0 | missing (unregistered -> loader stub returns 0, title believes the exec happened); argv fixed to `{"KytyEmu"}` at runtimeLinker.cpp:1796-1801 | M | M: process re-exec on the box (pid tracking of box scripts, log continuation) | later | Titles that chain executables (launcher -> game, mode switch) break today. argv[0]: KytyPS5 passes "" by default, ours "KytyEmu"; which the console uses is not verified |
| KL17 | Add-on content: `--addcont-dir` scan of sce_sys/param.json + `--addcont LABEL[=DIR]`; AddcontMount mounts /addcontN, BUSY on duplicate label (97bef29), NOT_FOUND, MOUNT_FULL (64), PARAMETER for service_label != 0, creates /download0/pdlc; Unmount -> NOT_MOUNTED if unknown | src/libs/libAppContent.cpp @ dfec14a:35-47, 198-251, 266-279; src/loader/additionalContent.cpp:1-47; src/common/additionalContent.cpp:1-131; src/main.cpp:315-328; src/emulator.cpp:187. 66e21a6 2026-10-24 "addcont: add user add-ons with --addcont and a launcher list"; 97bef29 2026-10-29 "appcontent: reject duplicate mounts without transferring ownership" | GPL-2.0 | differs: libs/libAppContent.cpp:165-199 (Mount always DRM_NO_ENTITLEMENT, Unmount OK unless empty) | M | L: off without flags | later | DLC support; the NpEntitlementAccess side (10 k-only NIDs) belongs to another part |
| KL18 | sceSystemServiceGetStatus reports is_system_ui_overlaid / is_in_background_execution from the system-dialog state | src/libs/libSystemService.cpp @ dfec14a:184-201 (191-194); needs KytyPS5 libs/dialog.h; pre-4644c52 | GPL-2.0 | differs: libs/libSystemService.cpp:190-204 (always false) | M | L | later | Titles pause/hide UI while a system dialog shows; needs a dialog-visibility source in ours |
| KL19 | Configurable user: `--user-id` (default 1000, player n = id + n*0x100), `--user-name` (player 1), localized "Guest N" for others | src/common/emulatorConfig.h @ dfec14a:33-48; emulatorConfig.cpp:43-86; src/main.cpp:57-58, 341-350; src/libs/libUserService.cpp:65-73, 113-131; pre-4644c52 | GPL-2.0 | differs: libs/libUserService.cpp:28-29 fixed 1000..1003, 116-127 "Kyty-N" | S | M: ids feed save-data paths | later | Startup flags only |
| KL20 | Guest TSC at 1.6 GHz (`--guest-tsc`): sceKernelReadTsc/GetTscFrequency scaled, guest RDTSC/RDTSCP rewritten to `host*mult>>32` via the instruction patcher (BMI2 sequence keeps RFLAGS) | 2f885e2 2026-11-01 "kernel: add --guest-tsc to run the guest TSC at the PS5's 1.6 GHz": src/loader/guestInstructionPatcher.cpp @ dfec14a:959-994, 1543-1610; src/kernel/pthread.cpp @ dfec14a:186-204; src/loader/runtimeLinker.cpp:1700-1703, 1846-1850 | GPL-2.0-or-later (patcher, shadPS4 SPDX) / GPL-2.0 | missing; needs KL21's patcher on Linux (ours: redZonePatcher Windows-only Xbyak, redZonePatcher.cpp:23-26) | L | H: rewrites guest code | later | Titles that hard-code the console TSC rate instead of asking for it. Provenance: the 1.6 GHz figure is the commit's own claim (no SDK citation); our trap path assumes 2.0 GHz (x64InstructionEmulator.cpp:882-888); not verified which is right |
| KL21 | Guest instruction patcher (replaces our redZonePatcher): native trampolines or traps for VRSQRTPS (deterministic estimate), EXTRQ/INSERTQ, RDPID, CLWB with `--amd-cpu`; cross-platform Xbyak | src/loader/guestInstructionPatcher.cpp/.h @ dfec14a (1815+73 lines); src/loader/runtimeLinker.cpp @ dfec14a:1694-1730, 1807-1876; x64InstructionEmulator.cpp:735-800; pre-4644c52 | GPL-2.0-or-later (shadPS4 SPDX) | differs: loader/redZonePatcher.cpp (1447 lines, red-zone part only, Windows) | L | H | later | Intel-host compatibility; no effect on the BC-250. Basis for KL20 |
| KL22 | GoldHEN-style cheat JSON (`id/version/process/mods`), anchor-byte module matching, code caves, deferred apply when the matching module loads | src/loader/gamePatch.cpp/.h @ dfec14a; src/loader/runtimeLinker.cpp:1112-1115, 1275-1279, 1309; pre-4644c52 | GPL-2.0 | differs: loader/gamePatch.cpp:92-322 (own plan format, main program only, plus the BC5 job-arena fix) | M | L | later | User feature |
| KL23 | sceSystemServiceHideSplashScreen hides KytyPS5's boot splash overlay | src/libs/libSystemService.cpp @ dfec14a:97-101; src/graphics/presentation/systemOverlay.cpp; pre-4644c52 | GPL-2.0 | differs: libs/libSystemService.cpp:98-102 (OK, no splash exists) | M | L | later | Presentation side; we have no splash to hide |
| KL24 | param.json `attribute` -> ATTRIBUTE (default 0), `attribute3` -> ATTRIBUTE3 in the emulated param.sfo | src/loader/systemContent.cpp @ dfec14a:169-171; pre-4644c52 | GPL-2.0 | missing: loader/systemContent.cpp:166-173 maps no attribute keys | S | L | later | No consumer in our tree (KytyPS5 uses them for HDR permission and Trinity, videoOut.cpp:1856-1858); port with a consumer |
| KL25 | PS5 Pro (Trinity) mode: ATTRIBUTE3 bit 22 + `--trinity` -> SystemContentIsTrinityMode used by kernel/Psml/Agc | 651ef73 2026-10-29 "graphics: add experimental Pro mode and linear PSSR": src/loader/systemContent.cpp @ dfec14a:608-615, 639-641 | GPL-2.0 | missing (KernelIsTrinityMode returns 0, libs/libKernel.cpp:1408) | L | M | later | GPU-coupled; loader part is 10 lines |
| KL26 | Registration-only SystemService stubs: x1UB9bwDSOw SystemServiceDisableMusicPlayer, 9kPCz7Or+1Y sceSystemServiceReenableMusicPlayer (06ab430 2026-10-31), uaieF+glFPs SystemServiceLaunchPlayerDialog, m5CYKX20wfg SystemServiceInitializePlayerDialogParam (void, writes nothing) (f12fc20 2026-10-31 "Stub missing SystemService / NpManager / NpWebApi2 imports (Palworld, PPSA23126)") | src/libs/libSystemService.cpp @ dfec14a:261-268, 279-287, 600-604 | GPL-2.0 | missing | S | L | later | equivalent to loader return-0 stub; registration only |
| KL27 | libs.cpp init list: KytyPS5 registers JpegDec, ConvertKeycode, DeviceService, BluetoothHid, Hmd2, Vdecsw, VrTracker2, VideoOutVrrStatus, Ces (k-only NIDs 5/1/3/3/15/13/4/3/2); Usbd, RazorCpu, WebBrowserDialog, JpegEnc NIDs we already register elsewhere | src/libs/libs.cpp @ dfec14a:25-113, 116-164 (JpegDec/Enc: ba0e93d 2026-10-23) | GPL-2.0 | differs: libs/libs.cpp:94-135 | n/a | n/a | later | Pointer row: the libraries belong to the per-library parts; not counted in KL's effort sum |
| KL28 | param.json memory sizing (flexible/CPU/GPU/AMM page tables) and per-module flexible charge | 09753bf 2026-10-27, 0a14091 2026-10-26; systemContent.cpp @ dfec14a:177-191; runtimeLinker.cpp:1639-1667, 1715-1716, 1908 | GPL-2.0 | in flight | - | - | in e4 / done | listed only |
| KL29 | Unresolved-import stub thunk (zero int/float return, first-call log) | src/loader/runtimeLinker.cpp @ dfec14a:129-215 | GPL-2.0 | loader/runtimeLinker.cpp:157-395 (superset: saves arg regs and AL, late-resolves by NID and patches the slot, journals first calls) | - | - | skip: already match (loader/runtimeLinker.cpp:157-395) | - |
| KL30 | sceKernelDlsym (NID then name, Func/Object/NoType, `scriptingGetMem`), GetModuleInfoFromAddr, GetModuleInfoForUnwind | src/libs/libKernel.cpp @ dfec14a:177-280, 1492, 1625 | GPL-2.0 | libs/libKernel.cpp:181-290 and the two GetModuleInfo* (identical apart from whitespace) | - | - | skip: already match (libs/libKernel.cpp:181-290) | - |
| KL31 | Red-zone memory-fault protection (Windows only in both) | src/loader/runtimeLinker.cpp @ dfec14a:1695-1699 | GPL-2.0-or-later | loader/runtimeLinker.cpp:2559-2585 + redZonePatcher.cpp | - | - | skip: already match (loader/runtimeLinker.cpp:2559-2585) | - |

## 3. Port specs for the e4-now rows

### KL01 -- TLS stubs keep RFLAGS
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

### KL02 -- TLS patch placement
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

### KL03 -- GetUserName without aborts
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

### KL04 -- UserService login set
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

### KL05 -- language parameter 400
- NID fZo48un7LK4, `SystemService::SystemServiceParamGetInt`, library SystemService.
- Signature: `int (int param_id, int* value)`.
- Behaviour: `case 400` shares the PARAM_ID_LANG branch (our host-input SystemLanguage, else --console-language).
- Port: KytyPS5 src/libs/libSystemService.cpp @ dfec14a:34, 118-119.
- Insertion: OURS libs/libSystemService.cpp:34 (constant) and 114-118 (case).
- CPU-only test: ParamGetInt(400,&v) == OK and v == the value of ParamGetInt(1,&w); with --console-language 1, v==1
  (today 0).

### KL06 -- Sysmodule load state
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

### KL07 -- StopUnloadModule bad handle
- NID QKd0qM58Qes, `LibKernel::KernelStopUnloadModule`, library libkernel.
- Signature: `int (KernelModule handle, size_t args, const void* argp, uint32_t flags, const KernelUnloadModuleOpt*
  opt, int* res)`.
- Behaviour: `FindProgramById(handle) == nullptr` -> return KERNEL_ERROR_ESRCH (0x80020003), `*res` untouched.
- Port: KytyPS5 src/libs/libKernel.cpp @ dfec14a:1272-1276.
- Insertion: OURS libs/libKernel.cpp:1362-1365.
- CPU-only test: call with handle 0x7fff and flags 0, opt nullptr -> ESRCH (today OK). No module needed.

### KL10 -- stack walk hardening
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

### KL11 -- x64 trap emulation fixes
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

### KL12 -- notice-screen skip flag
- NID 3RQ5aQfnstU, `SystemService::SystemServiceGetNoticeScreenSkipFlag`, library SystemService.
- Signature: `int (bool* value)`.
- Behaviour: null -> SYSTEM_SERVICE_ERROR_PARAMETER (already); `*value = Config::SkipNoticeScreen()`; OK. New bool
  `skip_notice_screen` (default false) in ConfigOptions, getter, and flag `--skip-notice-screen` in main.cpp.
- Port: KytyPS5 src/libs/libSystemService.cpp @ dfec14a:231-241; src/common/emulatorConfig.h:101, 172;
  emulatorConfig.cpp:236-238; src/main.cpp:110, 232.
- Insertion: OURS libs/libSystemService.cpp:241; common/emulatorConfig.h ConfigOptions (~66) and getters (~163-186);
  main.cpp simple-flag block 169-205.
- CPU-only test: config without the flag -> false; with it -> true; nullptr -> 0x80A10003.

## 4. Totals

31 rows: e4-now 10 (KL01-KL07, KL10, KL11, KL12); later 17 (KL08, KL09, KL13-KL27); in e4 / done 1 (KL28);
skip: already match 3 (KL29-KL31); skip: provenance 0 (guestInstructionPatcher carries a shadPS4
GPL-2.0-or-later SPDX header -- acceptable).
e4-now effort: 10 x S (about 1-1.5 days with tests).
later effort (KL27 is a pointer, not counted): 7 S (KL08, KL09, KL14, KL15, KL19, KL24, KL26) + 6 M (KL13, KL16,
KL17, KL18, KL22, KL23) + 3 L (KL20, KL21, KL25) ~ 1 + 5-6 + 9-12 days ~ 15-19 days.
