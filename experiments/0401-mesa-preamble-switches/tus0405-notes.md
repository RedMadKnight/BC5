# tus0405: the Usbd table of libUsbd.cpp, ported with the libusb transport behind an allow-list (series e7, hardware group)

Port agent `tus`, 2026-11-04. Exp 0405 decision 4 ("=> B => B"): the tables that are compiled but never loaded by
`Libs::InitAll` are ported first, then loaded, each behind its own switch. Agent `tl3` edits `libs.cpp` so that the table
loads when its switch is on. This agent edits only `src/libs/libUsbd.cpp`, which it owns entirely.

**History.** The first version ported only the no-device answers and held the libusb transport.

**Approval of libusb.** The top session asked the maintainer: "Usbd ... wymaga nowej zależności, biblioteki libusb na
hoście ... Dodać libusb?" His answer was "Tak". The coordinator relayed this, together with the top session's scope and
rules. This version follows those rules:
- libusb-1.0 (LGPL-2.1) is loaded at run time, behind `KYTY_BC5_LOAD_USBD`, with off exactly today's path.
- An allow-list by VID:PID, empty by default. With it empty, libusb is not even loaded and every call answers as with no
  device.
- HID (class 3), audio (class 1) and Sony's DualShock 4 / DualSense / DualSense Edge are never passed through, even when
  listed.
- libusb is loaded with dlopen/dlsym and our own declarations, so no compile or link command changes.
- AnyPS5's transport is ported on top, reachable only for allow-listed devices.
- The CPU tests need no USB and no libusb.

Files: `mktus0405.py` (the edit), `tus0405.cpp` (the CPU test), this note.

Input: `src/libs/libUsbd.cpp` of the e7 input tree, a base-tree file (KytyPlus f266548 + patch 0001, not changed by e4-e6):
md5 `f15039f248f156341d68cb3cb58a2b0f`, 11,429 bytes, LF, UTF-8 BOM. The script pins it in `PINS`.

Output md5: `eefb0de517c01962086049b816ada621` (90,664 bytes, LF, BOM kept). No other agent edits this file, so nothing
needs chaining.

## Switches, the allow-list, journal lines

| Variable | Read | Meaning |
|---|---|---|
| `KYTY_BC5_LOAD_USBD` (item `usbd`, shared with tl3) | once, `Bc5UsbOn` (output `:110`); `InitUsbd_1` (`:2976`) reads it first | unset, empty or `0`: off (today's path, all 65 registered, nothing below runs); anything else: on |
| `KYTY_BC5_USBD_ALLOW` | once, `Bc5UsbAllowList` (`:186`), by `InitUsbd_1` when the switch is on; never when off | the devices the host transport may reach |

**Allow-list format.** `vvvv:pppp[,vvvv:pppp...]`: four hex digits each, either case.
- Blanks around an entry are ignored, an empty entry (`,,`) is skipped, and duplicates are dropped.
- **One malformed entry refuses the whole list.**
- Sony's controller ids are dropped with a line: `054c:05c4`, `054c:09cc`, `054c:0ba0` (DualShock 4 and its dongle),
  `054c:0ce6` (DualSense) and `054c:0df2` (DualSense Edge).
- An empty result means no host access at all: libusb is not loaded and no device call is made.

Journal lines (stderr):
- `[bc5] exp 0405: usbd port on (items: devicelist transfer fill iso cancel events checks, host transport for KYTY_BC5_USBD_ALLOW devices; held: 4 unnamed)`
  / `[bc5] exp 0405: usbd port off`
- One allow-list line (on only):
  - `... usbd allow-list KYTY_BC5_USBD_ALLOW empty: no host USB access, libusb not loaded`
  - `... usbd allow-list KYTY_BC5_USBD_ALLOW refused, bad entry "<entry>" (want vvvv:pppp[,vvvv:pppp...]): no host USB access, libusb not loaded`
  - `... usbd allow-list: 1234:5678 ... (a device with a HID or audio class is still refused)`
  - plus `... usbd allow-list: 054c:0ce6 dropped (a Sony DualShock 4 or DualSense id, never passed through)` per dropped id.
- At the first `sceUsbdInit` with a non-empty list, one of:
  - `... usbd libusb-1.0.so.0 loaded (dlopen)`;
  - `... usbd libusb-1.0.so.0 not loaded (<dlerror>): no host USB access`;
  - `... usbd libusb-1.0.so.0 has no <symbol>` (then no host access).
- Per refused listed device, once:
  - `... usbd device vvvv:pppp refused: an interface of class HID or audio`;
  - `... refused: its device class is HID or audio`;
  - `... refused: a configuration that cannot be read`;
  - `... refused: it has no configuration to check`;
  - `... refused: a Sony DualShock 4 or DualSense id`.
- Catcher lines, once per function and case: `... usbd <function>: AnyPS5 has no answer for <case>; today's answer kept`,
  and the host-safety one for FreeTransfer.

## How the host is reached

- **Loading.** libusb is loaded once, at the first `sceUsbdInit` (AnyPS5 makes its context there), only when the
  allow-list is non-empty: `dlopen("libusb-1.0.so.0", RTLD_NOW | RTLD_LOCAL)` and `dlsym` of 34 functions (`Bc5UsbLibrary`,
  `:412`).
  - KytyPlus already uses dlopen (`graphics/presentation/renderDoc.cpp:277`, `IO/Decompressor.hpp:192`) and links
    `${CMAKE_DL_LIBS}` (`src/CMakeLists.txt:385,663`). The compile and link commands do not change, and no -dev package
    is needed.
  - On Windows the loader returns "not built for this platform" (the laptop syntax check only).
  - A missing library or symbol gives no host access, the same as AnyPS5 when `libusb_init_context` fails.
- **Our declarations** (`:238-406`): the descriptor structs, `libusb_transfer`, `timeval`, the error codes, speeds,
  transfer flags, class codes, the GET_DESCRIPTOR request, and the 34 prototypes.
  - They follow libusb's public header `libusb.h` (github.com/libusb/libusb, LGPL-2.1-or-later), with our own type names.
  - `static_assert`s pin the x86-64 layouts that AnyPS5 `Export.cpp:38-44` pins.
  - libusb.h's inline `libusb_get_descriptor` / `libusb_get_string_descriptor` are rebuilt as the same control request
    (IN, GET_DESCRIPTOR, `type << 8 | index`, 1000 ms).
  - No local copy of `libusb.h` was available: **TODO(verify)** the declarations against the container's libusb 1.0.x.
- **The gate** (`Bc5UsbAdmit`, `:621`). A device reaches the title only if all of these hold:
  - its id is listed and is not one of Sony's controllers;
  - its device class is not HID or audio;
  - it has at least one configuration;
  - no alternate setting of any interface of any configuration is HID or audio;
  - all its descriptors can be read.
- **Where the gate is applied.** `sceUsbdGetDeviceList` returns our own list of only the admitted devices, each with one
  reference. `sceUsbdOpenDeviceWithVidPid` returns null at once for an unlisted id, and opens the first device with that id
  only if the gate admits it.
- **Why nothing else can reach a device.** Every other call works only on devices or handles the title got from those two
  (AnyPS5's known-device/handle rule; anything else has no answer). So no call can open, claim or detach a refused device.
- **What the gate reads.** It reads each device's cached device descriptor, to learn its id, and the configuration
  descriptors of listed devices only. TODO(verify) on the box that libusb's Linux backend reads these from sysfs/usbfs
  caches, not from the device.
- **Sources of the Sony ids:**
  - SDL `src/joystick/usb_ids.h:40,60-63` (zlib), vendored in github.com/InoriRus/Kyty @ 4733b7e
    (`source/3rdparty/sdl2/sdl2/...`);
  - RPCS3 `rpcs3/Input/ds4_pad_handler.cpp:11-13` and `dualsense_pad_handler.cpp:28-29` (GPL-2.0), in
    github.com/RPCSX/rpcsx @ e8ae148 (DualSense Edge 0df2);
  - our own `libs/dualsense.h:27-28`.
  - The Linux `hid-ids.h` was not available offline.

## Size

| Table | NIDs | ported | already match | held (not registered on) | live elsewhere |
|---|---|---|---|---|---|
| Usbd | 65 | 61 | 0 | 4 (absent in AnyPS5) | 0 |

- All 524 AnyPS5 body lines are ported, plus its helpers (state, known checks, completion, packet size, string request).
  The output block is `:76-1701`.
- The 12 functions that matched with no device are now ported too: Init/Exit make and end the context; the device calls
  reach the host.

## Source and provenance

**AnyPS5** (github.com/boykopovar/AnyPS5, GPL-2.0-only) @ 4f41f4c375f5abb487dbd184fbc150f31994d762:
- `core/libs/prx/libSceUsbd/Export.cpp` (md5 a7a9f124…, `:24-853`) and `include/Api.hpp:18-45` (md5 94d51da2…).
- Every port function carries its AnyPS5 line range. The behaviour, the order of the checks and the constants are AnyPS5's.
  The form is our own (`Bc5Usb*`).

**Debt note** `docs/dev/debt/libSceUsbd.md` (md5 6d97a277…, read in full):
- `:5`: the pass-through, and FreeBSD 11.4 libusb's layouts equal to libusb's.
- `:6`: the `0x80240000 - code` mapping "following shadPS4". Null arguments return `0x80240002`.
- `:7`: transfers, kernel drivers and host access; "When the host has no USB access, initialization keeps the empty device
  list and event handling waits for its timeout". The transfer layout, argument lists, codes and iso are unverified on PS5.
- `:11-15`: every functional row is "not measured on a console", following FreeBSD 11.4.
- The only measurements are AnyPS5's checks with an Xbox 360 controller on Windows.

**shadPS4** (github.com/shadps4-emu/shadPS4, GPL-2.0-or-later) @ 60c42b9:
- `src/core/libraries/usbd/usbd.cpp:16-24`: the code mapping.
- `usbd.h:30-35`: the types are libusb's own. `usbd.h:42-49`: speeds.
- `usbd.h:52-163`: the argument lists.

**Exp 0405 R1** (`raw\r1-verdicts\C.tsv`): rows 9f3799cfa and dbb27b9ef ("needs host libusb pass-through first"); that is
now ported.

**Decisions 1-3.** No row of this module names a firmware run, a module reading, a title's libc.prx, SDK headers, a
disassembly or an IDA database. AnyPS5's "refactor(sdk)" commit f38d29fd0 only moves its own structs. Nothing is held
for provenance.

**TODO(verify):**
- the transfer layout, timeval, codes and event semantics on a console (as upstream);
- our libusb declarations against the container's `libusb.h`;
- that descriptor reads do no device I/O.

## Per function (61 ported, 4 held)

Switch `KYTY_BC5_LOAD_USBD` for all ported rows. Each is listed as AnyPS5 `Export.cpp` line, then output line.
- With no allow-list (no context), every answer is the first version's: an empty list; nothing known, so a non-null device
  or handle has no answer and today's 0 runs.
- With a context, each call is AnyPS5's over libusb, for admitted devices and their handles.

| Group | Functions (AnyPS5 :line → output :line) |
|---|---|
| context and list | Init :268→:2540, Exit :279→:1982, GetDeviceList :299→:2342, FreeDeviceList :316→:2122 |
| transfer object | AllocTransfer :338→:1708, FreeTransfer :347→:2142, FillInterruptTransfer :357→:2062, FillBulkTransfer :369→:2002, FillIsoTransfer :381→:2082, FillControlSetup :394→:2022, FillControlTransfer :406→:2042, ControlTransferGetData :418→:1886, ControlTransferGetSetup :423→:1906, SetIsoPacketLengths :428→:2776, GetIsoPacketBuffer :433→:2380 |
| transfers | BulkTransfer :441→:1746, InterruptTransfer :448→:2558, CancelTransfer :455→:1766, SubmitTransfer :619→:2796, ControlTransfer :513→:1866 |
| devices | RefDevice :587→:2676, UnrefDevice :656→:2874, GetDeviceDescriptor :555→:2322, GetActiveConfigDescriptor :518→:2162, GetConfigDescriptor :537→:2202, GetConfigDescriptorByValue :682→:2222, FreeConfigDescriptor :468→:2102, GetBusNumber :532→:2182, GetDeviceAddress :550→:2302, GetDeviceSpeed :715→:2360, GetMaxPacketSize :729→:2420, GetMaxIsoPacketSize :720→:2400, Open :573→:2638, OpenDeviceWithVidPid :789→:2658 |
| handles | Close :503→:1846, GetDevice :710→:2282, GetConfiguration :695→:2242, SetConfiguration :614→:2736, CheckConnected :484→:1786, ClaimInterface :491→:1806, ReleaseInterface :597→:2696, SetInterfaceAltSetting :809→:2756, ClearHalt :665→:1826, ResetDevice :609→:2716, KernelDriverActive :568→:2578, DetachKernelDriver :673→:1926, AttachKernelDriver :477→:1726, GetDescriptor :703→:2262, GetStringDescriptor :560→:2440, GetStringDescriptorAscii :734→:2460 |
| events | EventHandlingOk :464→:1964, EventHandlerActive :678→:1946, LockEvents :785→:2598, TryLockEvents :825→:2816, UnlockEvents :842→:2834, LockEventWaiters :781→:2618, UnlockEventWaiters :838→:2854, WaitForEvent :846→:2894, HandleEvents :766→:2480, HandleEventsLocked :774→:2500, HandleEventsTimeout :328→:2520 |
| **held**, not registered on | `Func_65F6EF33E38FFF50` (ZfbvM+OP-1A) :2914, `Func_97F056BAD90AADE7` (l-BWutkKrec) :2929, `Func_C55104A33B35B264` (xVEEozs1smQ) :2944, `Func_D56B43060720B1E0` (1WtDBgcgseA) :2959: absent in AnyPS5, no behaviour |

**Where this differs from AnyPS5, on purpose:**
- **No answer instead of a throw.** In these cases today's answer runs after a catcher line:
  - a device or handle never handed out, or already released or closed;
  - a null transfer, buffer, device or `transferred` output;
  - a second lock in one thread, or an unlock or wait without the lock;
  - a timeout over INT_MAX seconds;
  - transfer flags other than 1 and 8;
  - the last Exit with transfers in flight (the count is then not decremented, so nothing changes);
  - an alternate setting with transfers in flight;
  - a halt error other than NOT_FOUND.
- **The gate.** Lists hold only admitted devices, and OpenDeviceWithVidPid is refused before enumerating for an unlisted
  id. AnyPS5 passes every host device through.
- **Our own lists.** A device list is our own array holding a reference per admitted device. libusb's list is freed at
  once. AnyPS5 hands out libusb's list; the reference counts it shows the title are the same.
- **Host safety, TODO(verify).**
  - FreeTransfer frees only a transfer AllocTransfer handed out, and only once.
  - Bulk/Interrupt write `*transferred = 0` only after the handle is known open (AnyPS5 writes it just before throwing).

## Split state and dependencies

- **No live Usbd functions.**
  - tld's `e6\tld\tables.json`: 65 records, `same_key` 0, `nid_any` 0.
  - My scan (`e7/tus/overlap.py`, 489 files of the e7 tree outside `libUsbd.cpp`): 0 of the 65 NIDs, and no Usbd name.
  - The same scan finds 0 in the batch-2 outputs of tl2, tbd, tbp, tbv and tbt.
  - tl3's `libs.cpp` only lists `InitUsbd_1` under `KYTY_BC5_LOAD_USBD`.
- **No NID added:** the output registers the same 65 lines in the same order, with 4 fewer when on.
- **Nothing shared with other libraries.** The pad (libPad, `dualsense*.cpp`) and audio paths reach the DualSense through
  their own code. This port never lists, opens or claims a HID or audio device or a Sony controller id, so it cannot take an
  interface from them.

## Test (`tus0405.cpp`)

- **Setup.** The test registers `InitUsbd_1` into its own `SymbolDatabase` and calls each function by NID with the exact
  import key (`libSceUsbd` v1, module 1.1).
- **The loader hook.** It sets the port's hook `Libs::LibUsbd::bc5_usb_symbols_for_test` (output `:409`; nothing in the
  emulator sets it), so the port never calls dlopen.
  - In the parent and the no-host children, the hook is a counter that must stay at 0.
  - In the child `fake`, the hook is a fake libusb table.
- **Child runs.** The allow-list is read once per process, so each list runs in a child process of the same binary. The
  child is started with `std::system`, the path is `/proc/self/exe` on Linux, and `KYTY_BC5_USBD_ALLOW` is set for the
  child only. The parent unsets it for itself.
- No game, GPU, window, sound, network, host USB or libusb. Watchdog 120 s.

**On: 42 cases**, ending `tus0405: on 42 of 42; end`:
- **The first version's 36 cases, adjusted:**
  - registration: 61 present, 4 held absent, 61 records;
  - "no allow-list": the 12 former matches;
  - the device and handle calls: 24 cases (now with ClearHalt and GetMaxIsoPacketSize);
  - the event cases (5), held (1), and HandleEvents last.
- **Child `bad` (1 case, 8 checks):** `1234:5678,12345:678` is refused whole. No symbol lookup, an empty list,
  OpenDeviceWithVidPid null, Init/Exit 0.
- **Child `sony` (1 case):** five Sony ids, all dropped. The same checks.
- **Child `fake` (12 cases, 154 checks).** The list `" 1234:5678, 1234:0003,1234:0001,ABCD:ef01,1234:0007,054c:0ce6,054C:05C4,,"`
  is checked over seven fake devices: vendor-class, HID interface, audio interface, unreadable configuration, HID device
  class, DualSense id, unlisted id. The checks:
  - **Loading.** The 34 symbols are looked up once, at the first Init; one context is made.
  - **The device list.** Only 1234:5678 is listed, the others keep no reference, and the gate's configuration reads are all
    freed.
  - **Device queries.** Descriptor, bus 3, address 7, speed (5 answered 4), packet sizes 64/512/NOT_FOUND, iso 3072 at high
    speed and 0x1400 at full. A refused device gets no answer and nothing is written.
  - **Configuration descriptors.** Active, by index (index 1 gives NOT_FOUND and writes null), by value. Each is freed once;
    a second free has no answer.
  - **References.** RefDevice and UnrefDevice work for the admitted device only.
  - **Handle calls.** Open, GetDevice, Get/SetConfiguration, CheckConnected (NO_DEVICE when gone), claim and release, the
    alternate setting (claimed / not claimed / 40), kernel driver active / detach / attach, ClearHalt (0, NOT_FOUND→OTHER,
    pipe→no answer), reset.
  - **Control and descriptors.** ControlTransfer as given. GetDescriptor uses IN, GET_DESCRIPTOR, 0x0100, 1000 ms.
    GetStringDescriptor uses 0x0302/0x0409 with the length cut to 65535. GetStringDescriptorAscii gives "Hi!" (dropping
    '<', '>' and a control character) and "Hi" for length 3.
  - **Bulk and interrupt.** 8 transferred / TIMEOUT with 0.
  - **Submitted transfers:**
    - submit makes a host copy with every field;
    - a second submit is BUSY and its copy is freed;
    - free while in flight has no answer;
    - cancel, then HandleEventsTimeout completes it: the title's callback runs once with status 3 and its length;
    - cancel after completion gives NOT_FOUND;
    - flags 2 get no answer; flags 1 submit;
    - HandleEvents with no timeout returns after the completion;
    - an iso transfer with 2 packets of 32 gets its results copied back;
    - host transfers allocated equal those freed.
  - **Close and open by id.** Close works once. OpenDeviceWithVidPid opens 1234:5678 and refuses the HID 1234:0003 without
    opening it. Unlisted ids (054c:0ce6, 9999:9999) cause no enumeration at all.
  - **Free and Exit.** FreeDeviceList unrefs. The first Exit keeps the context; the last closes the open-by-id handle and
    calls libusb_exit once. GetDeviceList is empty afterwards, with no enumeration.
  - **Refused devices.** The six refused devices were never opened, claimed or detached, every reference is released, and
    no handle is left open.
- **Never loaded (1):** after all of the parent's calls, the counting hook was asked for 0 symbols.

**Off: 40 cases**, ending `tus0405: off 40 of 40; end`. Unset gives the same.
- The first version's off cases, with registration of all 65.
- Child `offlisted`, with the switch off and `KYTY_BC5_USBD_ALLOW=1234:5678`: the list is not read, no symbol lookup,
  today's answers, nothing written.
- Never loaded.
- **Off expectations from today's code:** every input stub is `PRINT_NAME(); return OK; // STUBBED` (65 of 65, checked by
  the script; `OK` is 0, `libs/errno.h:6`).

An argument that disagrees with the switch exits 2. A child exits 0 only when all its cases pass.

## Verified on the laptop

- **The script.** `mktus0405.py <e7 input tree> <out>` prints `src/libs/libUsbd.cpp eefb0de517c01962086049b816ada621`.
  - It refuses its own output and an input with another md5.
  - Its built-in checks pass: anchors once each, balance kept, 61 + 4 = 65 names with today's bodies, `Bc5UsbOn()` used 67
    times, held stubs unchanged, every ported stub keeps today's return, registration lines identical, undo gives the
    input back byte for byte, ASCII and LF.
- **Syntax:** VS clang++ (clang 22, MSVC target) `-fsyntax-only -std=c++20 -Wall -Wextra -Werror`, with tbt's setup
  (`e7/tus/chk.sh`).
  - The output and the test are clean.
  - The Linux-only branches were checked too, on copies with `_WIN32` switched off: dlopen/dlsym/dlerror in the port;
    `sys/wait.h`, `setenv`/`unsetenv` and `read_symlink` in the test.
  - Those copies used scratch stand-in declarations (`e7/tus/linuxbranch/inc`); both are clean.
- **Stand-in run** (`e7/tus/standin/build.sh`): the real test, the real output (both `-Wall -Wextra -Werror`), the e7 tree's
  `symbolDatabase.cpp`, fmt, and logging/timer/file stand-ins.
  - `KYTY_BC5_LOAD_USBD=1`: `tus0405: on 42 of 42; end`, exit 0, with the children's lines `[child bad] 1 of 1`,
    `[child sony] 1 of 1` and `[child fake] 12 of 12`.
  - `=0` and unset: `tus0405: off 40 of 40; end`, exit 0.
  - The journal lines are as listed above.
- **Negative run** (`e7/tus/neg`): a copy of the output with four faults:
  1. the gate lets HID and audio interfaces pass;
  2. Sony ids are kept in the list;
  3. libusb is loaded even with an empty list;
  4. the title's callback never runs.

  The result is `on 38 of 42 passed; FAIL`, exit 1. Fault 3 fails "never loaded" and the bad and sony children (34
  lookups). Faults 1 and 4 fail fake cases 2-5 and 9-12 (HID 1234:0003 listed and opened by id, configs, references,
  callbacks). Fault 2 alone would also fail the sony child (its list would then be non-empty and libusb would load); in
  this run fault 3 already does.
- **Not checked:**
  - the box's Linux compile and link;
  - the real `dlopen` of the container's libusb-1.0.so.0;
  - our declarations against the real libusb.h;
  - any real USB device.

## What the box needs

- **For the CPU test and the shared builds:** nothing new. The test injects its own symbols and never loads libusb. The
  emulator loads libusb only when `KYTY_BC5_USBD_ALLOW` is non-empty and the switch is on, and no compile or link command
  changes.
- **For a real device later:**
  1. `libusb-1.0.so.0` must exist in the `ubuntu` container. That is the runtime package `libusb-1.0-0`, often already
     installed; no -dev package is needed. A read-only check:
     `distrobox enter ubuntu -- sh -c 'ldconfig -p | grep libusb-1.0.so.0'`. If it is missing, installing it is a box write
     the maintainer must approve.
  2. Read-write access to `/dev/bus/usb/BBB/DDD` for the maintainer's user (a udev rule on the Bazzite host: also a box
     write).
  3. An allow-list naming a non-HID, non-audio device. HID game devices (pads, wheels) are refused by design, so the
     pass-through is for vendor-class devices only.

## Risks

- **Titles see different answers on.**
  - An empty list (or an allow-listed device) instead of garbage.
  - Event calls wait for their timeouts, and HandleEvents with no device never returns (as upstream).
  - 0x802400xx codes for null arguments.
- **No answer = today's 0** for the impossible cases (catcher lines).
- **The gate's strictness.** Any device with a HID or audio interface anywhere is refused, even when listed, which rules
  out most game peripherals. That is the top session's rule; a narrower one (refusing only the interfaces) would need a
  decision.
- **The callback thread.** The title's transfer callback runs on the thread that calls the event functions, a guest thread,
  as on FreeBSD libusb.
- **Exit while another thread handles events:** upstream's race (libusb_exit under a running handler) is unchanged.
- **Declarations:** our libusb declarations follow the public header but were not compiled against it here. TODO(verify).
- **Return types:** eight stubs return 64 bits (seven pointers and the list count). Off they return 0 in the whole rax.

## Files

| File | md5 |
|---|---|
| `mktus0405.py` | `6a98f3e8dcd0f80f4950378b7572dd72` |
| `tus0405.cpp` | `017432e975475484df0cdfb4930438b0` |
| input `src/libs/libUsbd.cpp` (base tree, e7 input tree) | `f15039f248f156341d68cb3cb58a2b0f` |
| output `src/libs/libUsbd.cpp` | `eefb0de517c01962086049b816ada621` |

The first version (no-device only, output `355c75224c97ad053a599cc60afc30b7`) is kept in scratch `e7/tus/v1/`.
