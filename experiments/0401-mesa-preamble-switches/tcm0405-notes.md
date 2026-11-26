# tcm0405: the Camera table of libCamera.cpp, ported before it is loaded (series e7, hardware group)

Port agent `tcm`, 2026-11-04. Exp 0405 decision 4 ("=> B => B"), dead-table batch 2, hardware group: the Camera table,
`Libs::LibCamera::InitCamera_1` of `src/libs/libCamera.cpp` (76 NIDs, all `return OK; // STUBBED`). The loader agent `tl3`
edits `libs.cpp` so the table loads when its switch is on; this agent edits only `libCamera.cpp` (owned entirely).

Files: `mktcm0405.py` (the edit), `tcm0405.cpp` (the CPU test), this note. Scratch: `...scratchpad\e7\tcm\`.

Input: `src/libs/libCamera.cpp` of the e7 input tree, a base-tree file (not in `E5-FILES.txt`, not an e6 unit), md5
`810fada1b7e1d223502ace667b71eb14`, 12,675 bytes, LF, starts with a UTF-8 BOM (kept as it is). Output md5
`b8544da15dc5ade0a1bab10883847cb2`, 41,606 bytes, LF, the BOM kept; every inserted byte is ASCII.

## Switch and journal line

`KYTY_BC5_LOAD_CAMERA` (item word `camera`), shared with `tl3`. Default off, read once (a function-local static),
env_flag.hpp's rule (on = set, non-empty and not `0`). One stderr line when `InitCamera_1` runs:

- on: `[bc5] exp 0405: camera port on (items: isattached open-close start-stop frame config attributes device-queries audio)`
- off: `[bc5] exp 0405: camera port off`

Off is exactly today's path: each ported stub runs `PRINT_NAME()`, then `if (Bc5TcmOn()) return port(...)`, then today's
`return OK`; `InitCamera_1` registers all 76 NIDs in today's order. On, the 22 held NIDs are **not registered** (the top
session's rule for every dead table, 2026-11-04 evening: exp 0327's "stubbed import called" line still shows for them);
the other 54 are registered. The table registers 54 NIDs when on (not nothing).

## Verdicts: 50 ported, 4 already match, 22 held (76)

Source for every ported row: AnyPS5 4f41f4c375f5abb487dbd184fbc150f31994d762 (GPL-2.0-only),
`core/libs/prx/libSceCamera/`. Its debt note `docs/dev/debt/libSceCamera.md` (all 101 lines read) names shadPS4's camera
library **without a configured camera** as the source of every ported row (`:18-25`) and says "Not measured on a console"
for each (TODO(verify)). No row cites an IDA database, SDK headers, decrypted firmware, a disassembly or a title's
libc.prx: no decision-2/3 row. Values cross-checked in shadPS4 60c42b9 (GPL-2.0-or-later, the local checkout; AnyPS5's
note links shadPS4 commits 9a8ae44, 396c2a0 and 0614ce3, which the shallow local clone does not have): errors
`src/core/libraries/camera/camera_error.h:8-31` (PS4 values; AnyPS5 uses the same for the PS5, `include/Camera.hpp:5-10`),
system user 0xFF `src/core/libraries/system/userservice.h:22`, defaults `camera_config.cpp:28-37, 122, 156-157, 191, 265,
281, 304-305`, layouts `camera.h:42-46, 63-74, 89-158` (= AnyPS5 `include/Api.hpp:5-97`). Our own names; structures only as
far as the answers read or write them (the frame data view knows only its size word and the two status words at byte 232).

The model is a console with **no camera attached**. Nothing opens, maps or reads a host device; no frame exists.

| Group (output lines) | Exports | Behaviour on (AnyPS5 file:lines) |
|---|---|---|
| attached `:195-197`, stub `:762` | IsAttached | index 0 -> 0 (not attached), other -> 0x802E0000 PARAM (Export.cpp:11-14) |
| handles `:174-221`, stubs | Open, Close, CloseByHandle | Open(user 0xFF, type 0, index 0) hands out 1, 2, 3...; never reused; other args PARAM; parameter not read. Close: <1 PARAM, unknown NOT_OPEN 0x802E0004 (Handles.cpp:14-16, 26-57) |
| start/stop `:222-246` | Start, StartByHandle, Stop, StopByHandle | size 24 / handle checks, NOT_OPEN; Start: format levels >0xF or both 0 -> FORMAT_UNKNOWN 0x802E0007, else NOT_CONNECTED 0x802E0010; StartByHandle 0; Stop 0 (Handles.cpp:18-22, 59-78) |
| frames `:248-270` | GetFrameData, IsValidFrameData | GetFrameData writes both status words 0xFFFFFFFF, then PARAM (handle <1, size >584) or NOT_OPEN; IsValid: checks, NOT_OPEN, then status[0]==1 && status[1]==1 (Handles.cpp:80-92) |
| config `:272-326` | GetConfig, SetConfig, SetConfigInternal, GetDeviceConfig, GetDeviceConfigWithoutHandle | size 104 + open handle; GetConfig: type 1, both outputs YUV422 + 3 scaled Y8, resolution 0, 60 fps; Set*: NOT_CONNECTED; GetDeviceConfig: cleared, size 104; WithoutHandle: any handle open, all cleared incl. size (Config.cpp:7-57) |
| device/audio `:328-373` | GetDeviceInfo, GetProductInfo, GetRegistryInfo, GetMmapConnectedCount, GetCalibDataFromDevice, GetCalibrationData, AudioOpen, AudioGetData, AudioGetData2 | queries: null PARAM, nothing open NOT_INIT 0x802E0002, else NOT_CONNECTED; DeviceInfo also reserved/size 16/revision 1; mmap count: NOT_OPEN with nothing open, else 0; calibration: size 12, format 0, function <=1, then NOT_CONNECTED; AudioOpen FATAL 0x802E00FF; audio data: null PARAM else 0, nothing written (Device.cpp:7-52, Export.cpp:214-216, 238-240) |
| settings `:375-488` | GetAttribute, GetAutoExposureGain, GetAutoWhiteBalance, GetDefectivePixelCancellation, GetLensCorrection, GetContrast, GetSaturation, GetSharpness, GetHue, GetExposureGain, GetWhiteBalance, GetGamma | handle, channel 1 or 2, output, no option, open handle; defaults: flags 0, contrast 32, saturation 64, sharpness 1, hue 1, exposure {0,20,100,0}, balance {0,768,768,512}, gamma {0,4}; GetAttribute fills all 112 bytes (exposure 83, gain 100); GetAutoExposureGain clears an 8-byte target (Attributes.cpp:8-125) |
| settings, setters | SetAttribute and the 13 Set* (AutoExposureGain, AutoWhiteBalance, DefectivePixelCancellation[Internal], LensCorrection[Internal], Contrast, Saturation, Sharpness, Hue, ExposureGain, WhiteBalance, Gamma) | channel 1..3, the per-call checks (enable <=1, Internal <=2, sharpness <=10, AE target in {0,2,4,6,8,0x10,0x12,0x14,0x16,0x20} with size 8, value pointers non-null, no option), NOT_OPEN, then NOT_CONNECTED; nothing stored (Attributes.cpp:28-32, 34-45, 127-182) |

Stubs: output `:491-1021` (e.g. AudioGetData `:501`, GetAttribute `:556`, GetFrameData `:667`, Open `:783`,
SetWhiteBalance `:981`, StopByHandle `:1013`); the 50 stubs got real parameter lists (48 lines changed; AudioOpen and
GetCalibDataFromDevice have none) and one branch each. Block `:31-489`, includes `:15-24`, `LIB_DEFINE` `:1023`, its switch
line `:1024`, the 22 held lines `:1025-1095`.

Our deviations from AnyPS5, both host safety: Open answers 0x802E0014 (shadPS4 MAX_HANDLE, `camera_error.h:26`;
TODO(verify)) where AnyPS5 throws once 2^31 handles were handed out; clearing a configuration also clears its padding.

- **Already match (4):** AudioClose (input `:25-28`, output `:496`), AudioReset (`:45-48` / `:525`), DeviceOpen
  (`:65-68` / `:551`), SetAttributeInternal (`:250-253` / `:814`): AnyPS5 `Export.cpp:175-177, 351-353, 282-284, 86-88`
  answer 0 and do nothing = today's `return OK`. Not edited; registered in both modes.
- **Held (22), not registered when on, today's stub when off:** AccGetData, ChangeAppModuleState, GetCalibData,
  GetDeviceID, GetDeviceIDWithoutOpen, GetRegister, GetVrCaptureInfo, InitializeRegistryCalibData, IsConfigChangeDone,
  OpenByModuleId, RemoveAppModuleFocus, SetAppModuleFocus, SetCalibData, SetDebugStop, SetForceActivate, SetProcessFocus,
  SetProcessFocusByHandle, SetRegister, SetTrackerMode, SetUacModeInternal, SetVideoSync, SetVideoSyncInternal. AnyPS5 has
  throwing placeholders (debt `:29-91`: "signature and behavior are unverified"); brief rule for pending rows. For the
  top session: shadPS4 60c42b9 marks 21 of them `(STUBBED)` returning 0 (= today's answer); its GetCalibData
  (`camera_calibration.cpp:10-41`) copies calibration tables "dumped" from a device: not a usable source.

## Split-state check

- **No live function in libSceCamera.** `e6\tld\tables.json` for `InitCamera_1`: 76 records, key
  `[Camera_v1][Camera_v1.1][Func]`, `same_key 0`, `nid_other_key 0`, `nid_any 0`. Grep of the whole e7 input tree: none of
  the 76 NIDs occurs outside `libCamera.cpp`, and no other file mentions `libSceCamera`, `LibCamera` or `InitCamera`
  (libs.cpp does not load it yet; that is tl3's edit). So the handle table is this file's own state; nothing to share.
- **Other libraries:** Open compares the user id with the constant 0xFF; no UserService state is read. Nothing else is
  read from another library. (GameLiveStreaming's `SetCameraFrameSetting`, `libGameLiveStreaming.cpp:478`, is another
  dead table's stub and reads no camera state.)
- **After the edit:** the LIB_FUNC count stays 76 (asserted), no registration is added; on, 22 fewer. No NID of this table
  is registered by a live table (none was; the edit adds none).
- tld risk 3 (an init called twice): the init only reads the switch (idempotent); the test registers twice and sees one line.

## Test: tcm0405.cpp

Registers the table into one database and again into a second (stderr in `./tcm0405-stderr.txt`), then calls by NID.
No subsystem, no device. Each call whose outputs a case checks is its own statement (argument order, tbp's lesson).

| | on (`tcm0405: on 169 of 169; end`) | off (`tcm0405: off 79 of 79; end`) |
|---|---|---|
| journal | 1 (the on line, once) | 1 (the off line, once) |
| registration | 2 (22 held absent; 54 present) | 2 (22 held present; 54 present) |
| already match | 4 | 4 |
| ported | 162: every one of the 50 at least once, valid and refused arguments, open/close/reuse, nothing-open vs open vs all-closed answers, outputs written or untouched | 50: each answers today's 0 with arguments the port would answer differently, nothing written |
| held | (absent) | 22: each today's 0 |

## Verified on the laptop

- `mktcm0405.py <e7 input tree> <out>` prints `src/libs/libCamera.cpp b8544da15dc5ade0a1bab10883847cb2`, twice the same; it
  refuses its own output (marker) and a changed input (md5). Built-in checks: every anchor once and inside its place, each
  edit balanced, the three lists cover the 76 LIB_FUNC lines exactly (50 + 4 + 22), the held and matching stubs are
  today's stubs before and after, switch use and switch-name counts, LIB_FUNC count unchanged, undo gives the input back
  byte for byte, inserted text ASCII, LF. `diff` shows only insertions plus the 48 parameter lists and the 22 held
  LIB_FUNC lines (each wrapped in `if (!bc5_tcm_on) { ... }`).
- Syntax (VS clang++ 22, msvc target, `-fsyntax-only -std=c++20 -Wall -Wextra -Werror`, stand-ins
  `scratchpad/lib0405chk/stub`, `e6/tbn/sched_standin.h`, fmt from Inori_GPCS4): input and output libCamera.cpp clean, the
  output also with `-Wshadow -Wconversion -Wsign-conversion` (0 warnings); tcm0405.cpp clean (needs
  `-Wno-deprecated-declarations` for Windows' POSIX names), also with `-Wformat=2 -Wshadow`.
- Stand-in run (`scratchpad/e7/tcm/standin/build.sh`): the real tcm0405.cpp, the real symbolDatabase.cpp, the output
  libCamera.cpp with log/timer/File stand-ins: `=1` on 169 of 169; `=0`, unset and empty: off 79 of 79; `=1` with the
  argument `off`: exit 2. Negative control with the unedited input (`build.sh neg`): on stops at Open (no handle; exit 2
  after 8 of 39 cases passed); off 78 of 79, only the journal case failing, so the off expectations are today's.
- **Not checked:** the box's Linux compile, the real link with every emulator object, running tcm0405 on the box.

## Risks

- A title that probes the camera now sees "not attached" (as today, IsAttached(0) = 0) but Open now succeeds with a real
  handle (today 0, an invalid handle) and Start then reports NOT_CONNECTED; GetFrameData reports NOT_OPEN and writes
  "no frame" into both status words. That is AnyPS5's (and shadPS4's no-camera) model; console behaviour unmeasured.
- StartByHandle answers 0 where Start answers NOT_CONNECTED (AnyPS5 debt `:19`: which the console does is unknown).
- Error values are shadPS4's PS4 values (TODO(verify) on the PS5); the defaults are shadPS4's, not read from a device.
- On, the 22 held NIDs fall to the loader's unresolved-import path (exp 0327 line) instead of answering 0.
- The ported stubs declare real parameters now; the off path ignores them.

## Sizes held

22 AnyPS5 placeholders, 0 logic lines upstream (the sweep's 4-line throwing bodies); by exp 0405's rule 0.0 days. Not
part of this table: AnyPS5 also has `sceCamera2*`, ForEve, IsVrCaptureEnable and other inventory placeholders (debt
`:5-14, :31-101`) that no table of the tree registers; none has behaviour.

## Files

| File | md5 |
|---|---|
| `mktcm0405.py` | `b9f2c4e0e9c2866b50ddfc8c0013b91b` |
| `tcm0405.cpp` | `e792f26440effc0fb812b0f5158259cd` |
| input `src/libs/libCamera.cpp` (e7 input tree = base tree) | `810fada1b7e1d223502ace667b71eb14` |
| output `src/libs/libCamera.cpp` | `b8544da15dc5ade0a1bab10883847cb2` |
