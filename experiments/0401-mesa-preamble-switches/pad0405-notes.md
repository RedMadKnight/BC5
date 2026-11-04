# pad0405: the scePad rows b94b3fa32, 3b404f65e (cleared 2026-11-04) and 2f9581050 in libPad.cpp (series e6)

Port agent `fwn`, tag `pad`, 2026-11-04. Files: `mkpad0405.py` (the edit), `pad0405.cpp` (the CPU test), this note.

**Input.** `src/libs/libPad.cpp` from the e6 input tree: e5's unit, md5 89a047a4f1ad39847bf76c15fa0d4c14 (`E5-FILES.txt`).
`controller.cpp` is not edited: the pad's init state is kept in libPad.cpp instead (see below).

**Provenance.** fwn0405 held b94b3fa32 and 3b404f65e on provenance. The maintainer answered on 2026-11-04: "tak,
przepisać tak JIT". So they are written the way decision 3 asks for the JIT item:
- from behaviour only, as AnyPS5's GPL-2.0-only code shows it;
- with our own names, structure and comments;
- with untyped outputs where the checks need no layout;
- citing only AnyPS5's code (path:lines and commit), and nothing from the upstream notes' sources.

The script asserts that the inserted text names no disassembly, decompiler output, IDA or module file.

2f9581050 was "missing export, later" in fwn0405. It is a decision-1 row (a firmware 13.42 run). It became small once the
init state is kept here, so it is item `queries`.

## Switch and journal lines

`KYTY_BC5_FW_PAD` is off by default and read once.
- Unset, empty or `0` means off. Nothing is registered, which is today's path: a title's import of these calls gets the
  loader's stub, which answers 0 and writes nothing.
- Any other value turns on all items, unless it names them as a comma list: `infotype`, `argchecks`, `queries`.
- Journal line, printed at libPad's registration either way: `[bc5] exp 0405: fw pad on (items: infotype argchecks queries)`
  or `[bc5] exp 0405: fw pad off`.
- Catcher, only when on: `[bc5] exp 0405: fw pad <call> past its checks -> 0, nothing written (not modelled)`, for the first
  8 such calls.

## What changed (output `src/libs/libPad.cpp`)

- **Block :339-643.** The parser, `Bc5FwPadItems`, the init flag, `Bc5FwPadInit`, and 18 functions.
- **`<atomic>` :10.**
- **scePadInit :648.** With any item on, scePadInit is registered as `Bc5FwPadInit`. It calls `Controller::PadInit` and
  records success. Off, today's `LIB_FUNC("hv1luiJrqQM", Controller::PadInit)` is kept in the `else` branch. This is the
  one input line the diff shows as moved (-1 +336).
- **Registrations :677, :680, :694**, one `if` per item.
- **Our model:**
  - "Initialised" means scePadInit was called.
  - A "known handle" is 1 to 4 (`Controller::ControllerIndexFromHandle`), which every pad call here accepts.
  - The host keeps no closed state and has no separate special-port handle.

## Item `infotype`: scePadGetInfoByPortType (row b94b3fa32): PORTED

**Source.** AnyPS5 4f41f4c37 `core/libs/prx/libScePad/Export.cpp:1014-1019`, commit b94b3fa32. The checks, in order:
1. a null output gives INVALID_ARG 0x80920001;
2. before scePadInit gives NOT_INITIALIZED 0x80920005;
3. a type other than 0 or 2 gives INVALID_ARG.

Past the checks AnyPS5 stops, because the answer would come from the pad driver. Ours returns 0 and writes nothing, which
is what the loader stub answered before. TODO(verify): the real port information.

## Item `argchecks`: twelve calls (row 3b404f65e): PORTED

**Source.** AnyPS5 4f41f4c37 Export.cpp, commit 3b404f65e:

| Lines | Call |
|---|---|
| 562-566 | ReadStateExt |
| 573-578 | GetExtensionUnitInfo |
| 589-594 | OpenExt2 |
| 636-640 | GetIdleCount |
| 642-646 | GetControllerIdleCount |
| 683-688 | GetCapability |
| 710-715 | GetVersionInfo |
| 997-1004 | GetActiveTime |
| 1006-1012 | GetDeviceId |
| 1148-1153 | GetDeviceInfo |
| 1208-1212 | SetPS4BcVibrationMode |
| 1229-1235 | ReadHistory |

The sizes are at Export.cpp:87-88.

**Before scePadInit.**
- Every call answers NOT_INITIALIZED, except GetIdleCount, which answers 0.
- ReadStateExt has no init check. It checks an unknown handle (INVALID_HANDLE 0x80920003), then a null output
  (INVALID_ARG), as our scePadReadState does.

**After scePadInit.**
- A null output gives INVALID_ARG in DeviceInfo, Capability, VersionInfo, ExtensionUnitInfo, ActiveTime and DeviceId.
- ControllerIdleCount refuses handle 0 or a null count.
- ReadHistory needs a size of exactly 0x960; it does not check a null data pointer.
- OpenExt2 needs a parameter size of 0x10 and a non-null parameter.
- ActiveTime writes 0.
- DeviceId writes -1, then refuses an unknown handle.

Past the checks every call returns 0 and writes nothing more, with the catcher line. That is today's stub answer.
TODO(verify): the real answers. The OpenExt2 handle, the history records and the device id are not modelled; AnyPS5
stops there too.

## Item `queries`: five queries (row 2f9581050, decision 1): PORTED

**Source.** AnyPS5 4f41f4c37 Export.cpp, commit 2f9581050 (BunnyFl):
- :81-85, OpenHandle;
- :899-905, ParseUniqueDataLeonardo;
- :1054-1060, GetMotionTimerUnit;
- :1067-1072, GetMotionSensorPosition;
- :1074-1079, GetSphereRadius;
- :1101-1106, GetBluetoothAddress.

The upstream note is `docs/dev/debt/libScePad.md:47` (13.42 module run natively).

**Behaviour.** The checks run in this order: before scePadInit, then a null output (INVALID_ARG), then an unknown handle
(INVALID_HANDLE). The DualSense has none of these queries, so past the checks:
- MotionTimerUnit, MotionSensorPosition and BluetoothAddress answer DEVICE_NOT_CONNECTED (0x80920007).
- MotionTimerUnit writes 0.0 before its handle check.
- SphereRadius answers INVALID_HANDLE for every handle. AnyPS5 accepts only a special-port handle, and our PadOpen gives
  port type 2 the player's standard handle, so no handle here is a special-port one.
- ParseUniqueDataLeonardo refuses a null input or output, clears 0x18 bytes of the output and answers INVALID_HANDLE.
- The `controller.cpp` dependency named in fwn0405 is gone, because the init state is kept here.

## CPU test `pad0405.cpp`

**Build.** `--gate pad0405.cpp <bin> --like src/libs/libPad.cpp`, with the private `src/libs/libPad.cpp` from
mkpad0405.py.

**Composition.** If fwn0405's units are in the same build, there is no overlap: fwn0405 does not touch libPad.cpp.

**How it runs.** Subsystems as lib0405.cpp starts them, then `Libs::InitAll`, then calls by NID. No game, GPU, window,
sound, network, fork or guest thread. Watchdog 60 s.

**NIDs.** From exp 0327's calculator (nid0401.py's algorithm), self-checked on strcmp, scePadInit, scePadOpen and
scePadReadState. 14 of the 18 are also in shadPS4's pad table. GetControllerIdleCount, GetActiveTime,
SetPS4BcVibrationMode and ParseUniqueDataLeonardo are PS5-only names and rest on the calculator alone.

**Cases.**
- Registration: 4 cases. Per item, its NIDs resolve on and do not resolve off. scePadInit is `Controller::PadInit` off
  and the wrapper on.
- `=1`: 71 cases. Registration 4, before init 19, after init 48.
- `=0` or unset: 4 cases (registration only; the calls do not exist then).
- An item list prints `mixed`.

**Expected output.** `pad0405: on 71 of 71; end` and `pad0405: off 4 of 4; end`.

**Risks.**
- Low-medium. A title that imports one of these calls now gets errors where the checks refuse, and 0 past them as before.
- One title-visible change past the checks: GetDeviceId writes -1 (today: nothing). GetActiveTime writes 0.
- With any item on, scePadInit becomes a wrapper; it answers the same.

## Laptop verification (2026-11-04)

**The script.**
- `python -I mkpad0405.py <e6 tree> <out>` prints the md5 below; a rerun gives the same md5.
- An already-edited unit is refused and nothing is written.
- The script asserts the pinned md5, anchors found once, balance, helper counts, ASCII/LF, undo giving the input back, and
  that no module-reading reference is in the inserted text.

**Syntax.** VS 18 clang++ (msvc target), with `-fsyntax-only -std=c++20 -Wall -Wextra -Werror` and fwn0405's stand-ins.
- Input and output libPad.cpp and `pad0405.cpp` are clean.
- With `-Wshadow -Wconversion -Wsign-conversion` the input and output have the same 2 warnings; the test has none.
- `pad0405.cpp` is ASCII, LF and balanced.

**Not checked.** GCC on the box, the link and the run.

## Still held

- Mouse 26d7585cf: M, about 0.5 d. Four exports and the absolute-pointer model.
- The rows fwn0405 lists stay as listed there.

## Files

| File | md5 |
|---|---|
| input `src/libs/libPad.cpp` (e5) | 89a047a4f1ad39847bf76c15fa0d4c14 |
| output `src/libs/libPad.cpp` | b9940ebe905e9ef1e31b117b531632fd |
| `mkpad0405.py` | 94ddd13d8f7e97337e20c0484672c10a |
| `pad0405.cpp` | df2412da46887c0da9f133637e351552 |
