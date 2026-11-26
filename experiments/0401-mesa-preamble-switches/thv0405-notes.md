# thv0405: Hmd, VrTracker and Move ported before they are loaded (series e7, dead-table batch 2, hardware group)

Port agent `thv`, 2026-11-04. Exp 0405 decision 4 ("=> B => B"): each table that is compiled but never loaded by
`Libs::InitAll` is ported first (AnyPS5's code for the NIDs our table registers), then loaded behind its own switch by the
loader agent `tl3` (libs.cpp, not edited here). This agent edits three units and nothing else; it owns them entirely.

Files: `mkthv0405.py` (the edit), `thv0405.cpp` (the CPU test), this note.

Inputs: the e7 input tree (= e6's sources). None of the three is an e5 or e6 unit, so each is the base tree's file (KytyPlus
f266548 + patch 0001). All three are LF with a UTF-8 BOM and tab indentation; libVrTracker.cpp has two blank lines after
every line, and the anchors match that byte for byte (inserted code is written one line per line). The md5s are pinned in
one dict (`PINNED`) at the top of the script.

**No host device is ever opened.** There is no PS VR headset, tracker, camera or Move controller on the host; every port
answers as AnyPS5 does for a console with none attached (its "not connected" / "no device" answers, argument checks,
init/term state and handle rules). Nothing is submitted to the GPU.

## Switches and journal lines

Each switch is off by default and read once (a function-local static); unset, empty or `0` is off, any other value is on
(env_flag.hpp's rule). The line goes to stderr when the table's `LIB_DEFINE` runs (or at the first call).

| Switch | Init (`LIB_DEFINE`) | stderr line when on (off: `[bc5] exp 0405: <word> port off`) |
|---|---|---|
| `KYTY_BC5_LOAD_HMD` | `Libs::LibHmd::InitHmd_1` | `[bc5] exp 0405: hmd port on (items: Initialize Initialize315 Terminate Open Close GetDeviceInformation GetDeviceInformationByHandle InternalGetDeviceStatus GetFieldOfView Get2DEyeOffset GetInertialSensorData GetAssyError; 120 held, not registered)` |
| `KYTY_BC5_LOAD_VRTRACKER` | `Libs::LibVrTracker::InitVrTracker_1` | `[bc5] exp 0405: vrtracker port on (items: QueryMemory Init Term RegisterDevice RegisterDevice2 RegisterDeviceInternal UnregisterDevice Recalibrate SetDurationUntilStatusNotTracking GpuWaitAndCpuProcess; 29 held, not registered)` |
| `KYTY_BC5_LOAD_MOVE` | `Libs::LibMove::InitMove_1` | `[bc5] exp 0405: move port on (items: Init Term Open Close GetDeviceInfo GetExtensionPortInfo ReadStateLatest ReadStateRecent SetVibration SetLightSphere ResetLightSphere)` |

Two catcher lines, each printed at most once and only when on:
- `[bc5] exp 0405: vrtracker Init with a 144-byte parameter: AnyPS5 has no answer; today's 0 kept, the tracker marked initialized for the ported calls`
- `[bc5] exp 0405: move Open for a user other than the initial user: AnyPS5 has no answer; today's 0 kept, no handle opened`

Off is exactly today's path: each edited stub runs `PRINT_NAME()`, then `if (switch) return port(...)`, then today's
`return OK; // STUBBED`. The edited stubs declare their real parameters, which the off path ignores (SysV registers, ABI
unchanged).

**Held stubs are not registered while the switch is on** (the coordinator's rule, as tbn's `InitNpManager_1`): each
`LIB_DEFINE` reads its switch once into `bc5_on` and wraps every run of consecutive held `LIB_FUNC` lines in
`if (!bc5_on) { ... }`, so a title's call to a held NID shows exp 0327's "stubbed import called" line; off, every NID is
registered as today, in today's order. No NID is added to or removed from any table. With the switch on: Hmd registers 17
of 137, VrTracker 10 of 39, Move 11 of 11. No table registers nothing.

## Verdicts

| Table | NIDs | ported | already match | held | why held |
|---|---|---|---|---|---|
| Hmd | 137 | 12 | 5 | 120 | AnyPS5 does not implement them (it throws) |
| VrTracker | 39 | 10 (Init's 144-byte parameter held) | 0 | 29 | AnyPS5 does not implement them (it throws) |
| Move | 11 | 11 (Open for another user held) | 0 | 0 | |
| **total** | **187** | **33** | **5** | **149** | |

The sweep's "6 const" for Hmd: InternalGetDeviceStatus has logic (a null check, then a write) and is ported; the other five
already match.

Sources: AnyPS5 (github.com/boykopovar/AnyPS5) @ 4f41f4c375f5abb487dbd184fbc150f31994d762, GPL-2.0-only, and shadPS4
@ 60c42b925c3d1e00008621b8587819999260ec31, GPL-2.0-or-later. Each is ported in adapted form, with our own names and
structure, and each inserted block cites its files and lines. The three units are headed GPL-2.0-or-later (from shadPS4);
each block says that the combined file is GPL-2.0 with AnyPS5's part GPL-2.0-only.

**Provenance.**
- Decision 1: Move's note (`docs/dev/debt/libSceMove.md:5-7`, boykopovar 8a1bd363e, Adnan Khan fb7763279) says "The
  native module confirms" the init errors, the answer 1 with nothing written, INVALID_HANDLE 0x80EE0004, the order init,
  then arguments, then handle, and the SDK rule of ReadStateRecent: a reading of the console module, with no address, no
  disassembly listing and no SDK header named. Taken as another person's description (decision 1), as tbv took DiscMap's
  "The supplied module confirms". Every code also stands on shadPS4 `move_error.h:8-16`.
- Decision 3 (IDA-sourced rows ported from behaviour only): Move's signatures "follow Orbital" (AnyPS5 commit 14b52daf5)
  and Hmd's device/field-of-view/assembly-error/sensor signatures are "recovered from native register use"
  (`libSceHmd.md:16`, boykopovar's "restore ... signatures" commits 7b97d7552, fe0540a4e). Our parameter lists are
  shadPS4's (`move.cpp:15-121`, `hmd.cpp:19-216`, which give the same shapes), with our own parameter names; no IDA type
  name, no Orbital or IDA reference is in any inserted line (checked by grep), and the comments cite AnyPS5's behaviour and
  shadPS4 only. VrTracker's 144-byte layout ("argument slots are recovered", `libSceVrTracker.md:5`) is not used.
- Hmd's and VrTracker's answers follow shadPS4 with no headset (notes `libSceHmd.md:11`, `libSceVrTracker.md:13`: PS4
  behaviour, not measured on a PS5): TODO(verify) on a PS5. Hmd's VR2D answers: the console answers 0 to the same four
  queries in libSceHmd2 (note `:12`, a console measurement in AnyPS5's libSceHmd2 note).
- Nothing from SDK headers, decrypted firmware or a title's libc is used. No Sony material.

## Hmd (`libHmd.cpp`, `KYTY_BC5_LOAD_HMD`): 12 ported, 5 already match, 120 held

**Source.** AnyPS5 `core/libs/prx/libSceHmd/Export.cpp:22-29, 81-130, 324-329, 384-386, 408-414, 436-440, 552-559,
827-832` and `Hmd.hpp:11-51` (commits 0c4dace39 "add a disconnected-headset HLE stub", fe6aba89a, a569d075e, a64445911);
shadPS4 `src/core/libraries/hmd/hmd.cpp:19-216, 418-426, 518-536, 568-572`, `hmd.h:15-60`, `hmd_error.h:6-27`,
`system/userservice.h:22-23`.

Ported (output: includes `:15-20`, block `:27-155`, wrappers `:157-228`, `:429-436`, `:787-802`, registration `:880-1031`):
- `sceHmdInitialize` (K4KnH0QkT2c), `sceHmdInitialize315` (s-J66ar9g50) `(param)`: ALREADY_INITIALIZED 0x81110001 when
  initialized; PARAMETER_NULL 0x81110008 for null; UNSUPPORTED_FEATURE 0x81110016 when the parameter's first 8 bytes (a
  pointer) are non-zero (AnyPS5's answer; shadPS4 initializes distortion with it instead; TODO(verify)); else 0.
- `sceHmdTerminate` (z-RMILqP6tE): 0, or NOT_INITIALIZED 0x81110002.
- `sceHmdOpen` (d2g5Ij7EUzo) `(user, type, index, param)`: NOT_INITIALIZED; PARAMETER_INVALID 0x81110009 for type or
  index != 0, a non-null param, user -1 or 0xFF; else DEVICE_DISCONNECTED 0x81110004 (no handle is ever issued).
- `sceHmdClose` (6biw1XHTSqQ), `GetDeviceInformationByHandle` (1pxQfif1rkE), `Get2DEyeOffset` (BWY-qKM5hxE),
  `GetInertialSensorData` (rU3HK9Q0r8o): HANDLE_INVALID 0x81110003 once initialized, else NOT_INITIALIZED; nothing written.
- `sceHmdGetFieldOfView` (NPQwYFqi0bs): PARAMETER_NULL for a null output first, then as above.
- `sceHmdGetAssyError` (Yx+CuF11D3Q): PARAMETER_NULL, then DEVICE_DISCONNECTED once initialized, else NOT_INITIALIZED.
- `sceHmdGetDeviceInformation` (thDt9upZlp8): PARAMETER_NULL, NOT_INITIALIZED, else 32 bytes written: status 2 (not
  detected) at +0, user -1 at +4, 24 zero bytes; 0.
- `sceHmdInternalGetDeviceStatus` (PPCqsD8B5uM): PARAMETER_NULL, else 2 written (32 bits), 0, initialized or not.

Already match (today's 0; input `libHmd.cpp:365-383`, `:415-418`): InternalMmapIsConnect (1PNiQR-7L6k, AnyPS5 `:128-130`,
shadPS4 `hmd.cpp:568-572`), InternalIsCommonDlgMiniAppVr2d (GwFVF2KkIT4), InternalIsCommonDlgVr2d (LWQpWHOSUvk),
InternalIsGameVr2d (YiIVBPLxmfE), InternalIsMiniAppVr2d (LMlWs+oKHTg) (false; AnyPS5 `:384-386, 408-414, 552-554`).
They stay registered both ways.

Held (120, AnyPS5 throws for every one; sweep kind pending): the 3dAudio, AnotherScreen, CrashReport, Dfu, Debug, Led,
Mmap, SeparateMode, SocialScreen, VirtualDisplay, Vr2dData and other Internal calls, SetVr2dEnable (fJVZYeqFttM) and the
19 unknown NIDs (`libSceHmd.md:30-54`). Size: no behaviour to port. shadPS4-only candidate (not ported, the brief keeps a
stub where AnyPS5 has no behaviour): aTg7K0466r8 (`hmd.cpp:794-809`, NOT_INITIALIZED / HANDLE_INVALID /
DEVICE_DISCONNECTED, about 10 lines). AnyPS5's constant answers for distortion and reprojection sizes, aligns and command
queries (Export.cpp:341-343, 370-372, 393-401, ...) belong to NIDs our table does not register: later work on unregistered
exports.

**Test cases** (16 per mode): registration 17; held 120 absent (on) / present and 0 (off); before Initialize: six calls
NOT_INITIALIZED, GetDeviceInformation null/out, GetFieldOfView null/out, GetAssyError null/out, InternalGetDeviceStatus
null/out (2 written); Initialize/Initialize315 with null and with the first field set; Initialize, again, 315, first field
set; Open's six cases; the five handle calls HANDLE_INVALID; GetFieldOfView after init; GetDeviceInformation's 32 bytes
and the bytes after them untouched; GetAssyError DEVICE_DISCONNECTED; Terminate, again, query, Initialize315, Open,
Terminate; the 5 matching calls give 0. Off: 0 everywhere, nothing written.

## VrTracker (`libVrTracker.cpp`, `KYTY_BC5_LOAD_VRTRACKER`): 10 ported, 29 held

**Source.** AnyPS5 `core/libs/prx/libSceVrTracker/Export.cpp:32-70, 94-109, 126-128, 133-170, 187-190, 211-226` and
`include/Api.hpp:65-124` (commits 107a17bd7, 733ca2c66, 764c4c8dd, b18230158, a9e23bcc0; note `:13`); shadPS4
`src/core/libraries/vr_tracker/vr_tracker.cpp:31-204, 257-265, 273-316, 334-346, 444-476`, `vr_tracker.h:16-41, 146-201`,
`vr_tracker_error.h:6-26`, `video_core/amdgpu/liverpool.h:36-37` (7 compute pipes a title may name, the eighth reserved
by system software; 8 queues per pipe).

Ported (output: includes `:38-45`, block `:66-339`, wrappers `:341-710`, registration `:958-1100`):
- `QueryMemory` (K7yhYrsIBPc) `(param, result)`: ARGUMENT_INVALID 0x81260806 for a null param or result, size != 0x40,
  profile not 0/100, or calibration modes out of range (headset manual only; pad, Move, gun manual or automatic); else the
  six u32 at result +4..+0x1B: onion 0x400000 (0x800000 with automatic Move calibration), 0x10000, garlic 0x3000000,
  0x10000, work 0x1000000, 0x10000; 0. The result's size field and the rest are not written. No init needed.
- `Init` (QkRl7pART9M) `(param)`: ALREADY_INITIALIZED 0x81260802 first; ARGUMENT_INVALID for null, size != 0x80, a null
  block, a size or alignment other than QueryMemory's, pipe >= 7 or queue >= 8, or bad calibration; else 0. The blocks are
  not looked up (as AnyPS5; shadPS4 asserts on them).
  - **Held path:** a 144-byte parameter: AnyPS5 throws. Today's 0 is kept and the tracker counts as initialized, so the
    ported calls answer as after an init (a host choice, catcher line, TODO(verify)).
  - **Adapted:** AnyPS5 compares pipe and queue signed (`std::int32_t` constants), so a negative pipe passes; its note
    says the checks follow shadPS4, whose unsigned compare refuses it. shadPS4's is taken. TODO(verify).
- `Term` (IBv4P3q1pQ0): 0, or NOT_INIT 0x81260801; registered handles are kept (AnyPS5, shadPS4).
- `RegisterDevice` (sIh8GwcevaQ), `RegisterDevice2` (24kDA+A0Ox0) `(type, handle)`, `RegisterDeviceInternal`
  (ufexf4aNiwg) `(type, handle, option, variant)`: NOT_INIT; ARGUMENT_INVALID for type outside 0-3 (negative included) or
  option > 4; DEVICE_ALREADY_REGISTERED 0x81260804 when the type has a handle; else the handle is kept, 0. The handle is
  not validated (no device exists to validate against; AnyPS5 and shadPS4 do not either).
- `UnregisterDevice` (Q8skQqEwn5c) `(handle)`: NOT_INIT; ARGUMENT_INVALID for a negative or unknown handle; else 0.
- `Recalibrate` (EUCaQtXXYNI) `(param)`: NOT_INIT; ARGUMENT_INVALID (null, size != 0x20, type > 3);
  DEVICE_NOT_REGISTERED 0x81260803 for the headset (always: none attached) or a type with no handle; else 0.
- `SetDurationUntilStatusNotTracking` (qBjnR0HtMYI) `(type, frames)`: NOT_INIT; ARGUMENT_INVALID for type outside 0-3; 0.
- `GpuWaitAndCpuProcess` (ARhgpXvwoR0): NOT_EXECUTE_GPU_SUBMIT 0x81260815 once initialized (no camera frame, no GPU
  submission), else NOT_INIT.

Held (29, AnyPS5 throws): CpuProcess, GetPlayAreaWarningInfo, GetResult, GetTime, GpuSubmit, GpuWait,
NotifyEndOfCpuProcess, ResetAll, ResetOrientationRelative, SaveInternalBuffers, SetExtendedMode, SetLEDBrightness,
SetRestingMode, UpdateMotionSensorData, SetDeviceRejection, CpuPopMarker, CpuPushMarker, GetLiveCaptureId,
StartLiveCapture, StopLiveCapture and the 9 unknown NIDs (exp 0405 C row 19d0401c5, "match": they are registered off,
not on). Size: no AnyPS5 behaviour. shadPS4-only candidates (not ported): GetTime (NOT_INIT, ARGUMENT_INVALID for null,
the process time; `vr_tracker.cpp:222-232`, 8 lines), GpuSubmit (NOT_INIT, else ARGUMENT_INVALID; `:234-242`, 4 lines),
GpuWait (NOT_INIT, ARGUMENT_INVALID for null or size != 32, NOT_EXECUTE_GPU_SUBMIT; `:244-255`, 7 lines): about 0.1 d.

**Test cases** (16 per mode): registration 10; held 29 absent / present and 0; QueryMemory before Init (fields, size
field and tail untouched); profile 100 with automatic calibration (onion 0x800000); 8 bad queries; 8 calls before Init
NOT_INIT; 14 bad Inits (null, size 0x7C, each block, onion size, pipe 7, queue 8, pipe -1, automatic headset) then still
NOT_INIT; Init, again, 144-byte, null; GpuWaitAndCpuProcess; registration of devices (duplicates, option 5/4, type 4/-1);
Recalibrate (null, size 0x1C, type 4, headset, registered types); headset registered but still NOT_REGISTERED; Unregister;
SetDuration; Term, again, calls after Term, QueryMemory after Term; the 144-byte Init held path then ALREADY_INITIALIZED,
handles kept over Term, GpuWait, Term. Off: 0 everywhere, nothing written.

## Move (`libMove.cpp`, `KYTY_BC5_LOAD_MOVE`): 11 ported

**Source.** AnyPS5 `core/libs/prx/libSceMove/Export.cpp:14-125` (commits 14b52daf5, 808d67e71, c47878994, 8a1bd363e,
fb7763279; note `:5-7`, decision 1 above); shadPS4 `src/core/libraries/move/move.cpp:15-121` (codes, handle numbers
0x30B0100 then every 0x100, parameter lists) and `move_error.h:8-16`.

Ported (output: includes `:15-24`, block `:31-211`, wrappers `:213-299`, registration `:303-316`):
- `Init` (j1ITE-EoJmE): ALREADY_INIT 0x80EE0002, else 0. `Term` (tsZi60H4ypY): NOT_INIT 0x80EE0001, else 0; every open
  handle is closed, the handle numbers go on counting (AnyPS5 never resets them).
- `Open` (HzC60MfjJxU) `(user, type, index)`: NOT_INIT; ALREADY_OPENED 0x80EE0007 for a type and index already open; else
  a new handle. Only the initial user is ported: 1000, our UserService's `GetInitialUser` (`libs/libUserService.cpp:161-169`;
  AnyPS5 compares with its own 0x10000000). **Held path:** another user (AnyPS5 throws): today's 0, no handle, catcher
  line, TODO(verify). Not ported: the console's eight-slot limit 0x80EE0005 (note `:6` describes it; AnyPS5 does not
  implement it and the order of its check is not given).
- `Close` (XX6wlxpHyeo): NOT_INIT; 0 for an open handle, else INVALID_HANDLE 0x80EE0004.
- `GetDeviceInfo` (GWXTyxs4QbE), `GetExtensionPortInfo` (y5h7f8H1Jnk), `ReadStateLatest` (ttU+JOhShl4) `(handle, out)`,
  `ReadStateRecent` (f2bcpK6kJfg) `(handle, time, out, count)`: NOT_INIT, then INVALID_ARG 0x80EE0003 (a null out;
  ReadStateRecent: a negative time, a null count, or a null out from SDK 0x04000000 on), then INVALID_HANDLE, else 1 (no
  controller connected), nothing written.
- `SetVibration` (IFQwtT2CeY0), `SetLightSphere` (T8KYHPs1JE8): NOT_INIT, INVALID_HANDLE, else 1. `ResetLightSphere`
  (zuxWAg3HAac): NOT_INIT, INVALID_HANDLE, else 0 (AnyPS5 omits the controller ioctl, note `:5`; shadPS4 `move.cpp:102`).
- The SDK version is our `sceKernelGetCompiledSdkVersion`'s reading (`libs/bc5LleAgc.cpp`, exp 0336), through
  `Loader::Bc5ProcParam()` declared locally as bc5LleAgc.cpp does; AnyPS5 reads the low 32 bits at process parameter
  +0x10. TODO(verify): the SDK field (the same choice as tbv's ScreenShot).

**Test cases** (12 per mode): registration 11; 11 calls before Init NOT_INIT (GetDeviceInfo(null) too: init first);
Init twice; Open's handles and ALREADY_OPENED; the five queries give 1, nothing written; six INVALID_ARG cases (the null
out of ReadStateRecent at SDK 0x0A000000, no program loaded); a handle never issued: arguments checked before the handle;
SetVibration / SetLightSphere / ResetLightSphere and their bad handle; Close twice, numbering continues; user 1001 (held:
0, no handle); Term, calls after Term; Init again, closed handle, next number, Close, Term. Off: 0 everywhere, nothing
written.

## Split state and live registrations (the brief's checks)

- **Hmd:** no live function of libSceHmd (no live key `[Hmd_v1]...` in `scratchpad\e6\tld\tables.json`; `libSceHmd` occurs
  only in libHmd.cpp under `src/`). The port's only state is its own init flag. libSceHmd2 is another library (not ours).
- **VrTracker:** no live function of libSceVrTracker. The registered device handles come from Pad, Move and Hmd, but the
  port only stores them (no validation), so no dependency on another table's state can occur.
- **Move:** no live function of libSceMove. The one live dependency is the initial user, a constant in libUserService.cpp
  (1000); the port uses the same value (cited). Controller state (libs/controller.cpp) is never read: Move is a separate
  device class with none attached.
- **Live registrations:** `scratchpad\e7\thv\overlap.py` lists the NIDs of the three `LIB_DEFINE`s and greps every quoted
  11-character NID in every `.cpp`, `.h` and `.inc` of the input tree: 187 NIDs (Hmd 137, VrTracker 39, Move 11), none
  twice, **0 registrations elsewhere**, for the input units and for the output units. tld's tables.json agrees (each table
  `same_key 0, nid_other_key 0, nid_any 0`). No port adds a registration.

## Risks

- **New error answers where today's stubs gave 0.** A title that probes for a headset (Hmd), initializes a tracker
  (VrTracker) or opens a Move controller now gets "not connected" answers: Hmd's Open DEVICE_DISCONNECTED and its handle
  calls HANDLE_INVALID; Move's 1 (no controller) and handle errors; VrTracker's NOT_EXECUTE_GPU_SUBMIT. Each is the
  upstream answer for a console with nothing attached; a title that treated today's 0 as "connected" and then read the
  unwritten outputs now sees the truth.
- **Held NIDs unregistered when on:** a title that imports any of the 149 held NIDs and calls it reaches exp 0327's
  stubbed-import path instead of today's 0 (the coordinator's rule; the point is to see such calls).
- **Hmd Initialize's UNSUPPORTED_FEATURE** for a non-null first field is AnyPS5's (no source named); shadPS4 accepts it.
  TODO(verify). GetDeviceInformation writes 32 bytes (AnyPS5 and shadPS4 agree); the note's `:16` "device information
  occupies 64 bytes" (register recovery) may mean a larger PS5 record; TODO(verify).
- **VrTracker's 144-byte Init** answers 0 and marks the tracker initialized (host choice). The pipe/queue sign rule follows
  shadPS4, not AnyPS5's code.
- **Move:** only user 1000 opens handles (another user gets today's 0 and no handle); the SDK field is our kernel's reading.
- The edited stubs now declare parameters; the off path ignores them.

## Verified on the laptop

- `mkthv0405.py <e7 input tree> <out>` prints the three output md5s below. Run on its own output it refuses ("the unit has
  the edit already").
- Built-in checks per unit: the pinned md5; every anchor once; the block after its table's `LIB_VERSION` and before the
  `LIB_DEFINE`; the balance of braces, parentheses and brackets per block, per edit and per unit; helper-use counts; the
  same NIDs in the same order in the `LIB_DEFINE` before and after, held exactly as planned (Hmd 120 in 5 runs, VrTracker
  29 in 5 runs, Move none); ASCII inserts; LF and the BOM kept; undoing the edits gives the input back byte for byte.
- `diff` input/output: besides inserted lines, only the stub signature lines that now take parameters (Hmd 11, VrTracker
  8, Move 9) and the held `LIB_FUNC` lines (re-indented one tab inside their `if (!bc5_on)` block: Hmd 120, VrTracker 29)
  change. The only non-ASCII bytes in the outputs are the inputs' BOMs. No "Orbital", "IDA", "db_types" or "disassembl"
  in any output or deliverable.
- **Syntax:** Visual Studio's clang++ 22 (msvc target), `-fsyntax-only -std=c++20 -Wall -Wextra -Werror`, the stand-in
  `cmake_config.h`/POSIX headers (`scratchpad/lib0405chk/stub`), `scratchpad/e6/tbn/sched_standin.h`, fmt from
  Inori_GPCS4, magic_enum from InoriRus_Kyty: the three outputs, the three inputs and `thv0405.cpp` (plus
  `-Wno-deprecated-declarations`) are clean.
- **Stand-in run** (`scratchpad/e7/thv/run`, not a deliverable). `driver.cpp` compiles `thv0405.cpp` itself with its
  `main` renamed (its `Init()` starts the emulator's subsystems, which do not link on the laptop) and runs the same
  registration and the same three Case functions. It links the three output units, the input tree's real
  `symbolDatabase.cpp`, fmt, tbc's log/timer/thread stand-ins, and a `Loader::Bc5ProcParam` stand-in (0, as the real one
  answers with no program loaded). lld's `/force:unresolved` covers only symbols of `thv0405.cpp`'s own `Init()`/`main`
  (subsystems, `Config::Load`, `Bc5SetLogging`, `PthreadInitSelfForMainThread`, `RuntimeLinker`), none called; the
  units themselves leave nothing unresolved.
  - All `=1`: **on 44 of 44**, exit 0; the three "port on" lines and both catcher lines on stderr.
  - All `=0`: **off 44 of 44**. Unset: off 44 of 44. A mix (hmd `on`, vrtracker `0`, move `yes`): mixed 44 of 44. The
    argument `on` with a mix: exit 2. Nothing is written to the run directory.
  - **Negative control:** the same driver linked with the three unedited input units: off 44 of 44 (every off
    expectation is today's code's answer), on 4 of 44 (40 cases catch the missing ports and the held registrations).
- **Not checked:** the box's Linux compile and link; the test's `Init()` (the emulator's subsystems); the real
  `Bc5ProcParam` with a program loaded (the SDK <= 0x03FFFFFF branch of ReadStateRecent is not reached by the test). The
  box build is the first real run.

## Files

| File | md5 |
|---|---|
| `mkthv0405.py` | 18ba03002b3a2b10ede34349f59d528d |
| `thv0405.cpp` | 0ec7021c1723a03d7d2d1bca98bca2dd |
| in `src/libs/libHmd.cpp` | 905036478f8f9336090248a532d0469f |
| in `src/libs/libVrTracker.cpp` | ee30491baadb582db2df7a08cadc4ae9 |
| in `src/libs/libMove.cpp` | 90b0765d8d601d7e7189e0b5064d180f |
| out `src/libs/libHmd.cpp` | 67f2cac30c96faa6bff2009152ceab64 |
| out `src/libs/libVrTracker.cpp` | aba154d965d03dec3fe0cb39eb4bef30 |
| out `src/libs/libMove.cpp` | ba3db48e387fd600764eed1b4c17da46 |
| read only: `src/libs/libUserService.cpp` (the initial user 1000) | e7 input tree, not edited |

## Case counts

All three switches on: 44 cases (hmd 16, vrtracker 16, move 12), ending `thv0405: on 44 of 44; end`. All off or unset: the
same 44 cases with today's answers, ending `thv0405: off 44 of 44; end`. A mix runs each table's cases by its own switch
and ends `mixed 44 of 44`. Build: `build0401.py ... src/libs/libHmd.cpp=<out>/src/libs/libHmd.cpp
src/libs/libVrTracker.cpp=<out>/src/libs/libVrTracker.cpp src/libs/libMove.cpp=<out>/src/libs/libMove.cpp --gate
thv0405.cpp <bin> --like src/libs/libHmd.cpp`.
