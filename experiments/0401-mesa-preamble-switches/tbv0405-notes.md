# tbv0405: Voice, ScreenShot, DiscMap, ulobjmgr, CompanionHttpd, CompanionUtil and VideoRecording ported before they are loaded (series e7)

Port agent `tbv`, 2026-11-04. Exp 0405 decision 4 ("=> B => B"), dead-table batch 2: each table that is compiled but never
loaded by `Libs::InitAll` is ported first (AnyPS5's code for the NIDs our table registers), then loaded behind its own
switch by the loader agent `tl2` (libs.cpp, not edited here). This agent edits six units and nothing else; it owns them
entirely.

Files: `mktbv0405.py` (the edit), `tbv0405.cpp` (the CPU test), this note.

Inputs: the e7 input tree (= e6's sources). None of the six is an e5 or e6 unit, so each is the base tree's file (KytyPlus
f266548 + patch 0001). All are LF with a UTF-8 BOM. libCompanion.cpp has a blank line after every line; libDiscMap.cpp,
libUlobjmgr.cpp and libVideoRecording.cpp have two. The anchors match that spacing byte for byte, and the inserted code is
written one line per line. The md5s are pinned in one dict (`PINNED`) at the top of the script.

## Switches and journal lines

Each switch is off by default and read once (a function-local static). Unset, empty or `0` is off; any other value is on
(env_flag.hpp's rule). None has items. The line goes to stderr when the table's `LIB_DEFINE` runs (or at the first call).

| Switch | Init (`LIB_DEFINE`) | stderr line when on (off: `[bc5] exp 0405: <word> port off`) |
|---|---|---|
| `KYTY_BC5_LOAD_VOICE` | `Libs::LibVoice::InitVoice_1` | `[bc5] exp 0405: voice port on (items: VADSetVersion GetResourceInfo-check; 8 held, split state with libAudio.cpp)` |
| `KYTY_BC5_LOAD_SCREENSHOT` | `Libs::LibScreenShot::InitScreenShot_1` | `[bc5] exp 0405: screenshot port on (items: Disable Enable IsDisabled SetOverlayImage SetOverlayImageWithOrigin)` |
| `KYTY_BC5_LOAD_DISCMAP` | `Libs::LibDiscMap::InitDiscMap_1` | `[bc5] exp 0405: discmap port on (items: IsRequestOnHDD ioKMruft1ek)` |
| `KYTY_BC5_LOAD_ULOBJMGR` | `Libs::LibUlobjmgr::InitUlobjmgr_1` | `[bc5] exp 0405: ulobjmgr port on (items: RegisterObject UnregisterObject)` |
| `KYTY_BC5_LOAD_COMPANIONHTTPD` | `Libs::CompanionHttpd::InitCompanionHttpd_1` | `[bc5] exp 0405: companionhttpd port on (items: OptParamInitialize Initialize Terminate RegisterRequestCallback UnregisterRequestCallback Start Stop GetEvent)` |
| `KYTY_BC5_LOAD_COMPANIONUTIL` | `Libs::CompanionUtil::InitCompanionUtil_1` | `[bc5] exp 0405: companionutil port on (items: GetEvent)` |
| `KYTY_BC5_LOAD_VIDEORECORDING` | `Libs::LibVideoRecording::InitVideoRecording_1` | `[bc5] exp 0405: videorecording port on (items: none; SetInfo held)` |

Three catcher lines, each printed at most once and only when on (CompanionHttpd):
- `[bc5] exp 0405: companionhttpd Terminate of a started server: AnyPS5 has no answer; stopped and terminated, 0`
- `[bc5] exp 0405: companionhttpd UnregisterRequestCallback with no callback: AnyPS5 has no answer; today's 0 kept`
- `[bc5] exp 0405: companionhttpd Initialize2: AnyPS5 has no answer; today's 0 kept, the library marked initialized for the ported calls`

Off is exactly today's path: each edited stub runs `PRINT_NAME()`, then `if (switch) return port(...)` (or, for the two
check-only ports, `if (switch) { check; return the error }`), then today's `return`. The edited stubs declare their real
parameters, which the off path ignores. No NID is added to or removed from any table.

## Verdicts

| Table | NIDs | ported | already match | held | why held |
|---|---|---|---|---|---|
| Voice | 14 | 2 (VADSetVersion; GetResourceInfo's check only) | 4 | 8 (+ GetResourceInfo's limits) | split state with libAudio.cpp |
| ScreenShot | 14 | 5 | 2 | 7 | AnyPS5 does not implement them |
| DiscMap | 5 | 2 | 0 | 3 | AnyPS5 does not implement them |
| ulobjmgr | 4 | 2 | 0 | 2 | AnyPS5 does not implement them |
| CompanionHttpd | 17 | 8 | 3 | 6 | AnyPS5 does not implement them |
| CompanionUtil | 5 | 1 | 4 | 0 | |
| VideoRecording | 1 | 0 | 0 | 1 | provenance: the note names no run |
| **total** | **60** | **20** | **13** | **27** | |

Common sources: AnyPS5 (github.com/boykopovar/AnyPS5) @ 4f41f4c375f5abb487dbd184fbc150f31994d762, GPL-2.0-only, and
shadPS4 @ 60c42b9, GPL-2.0-or-later. Each is ported in adapted form, with our own names and structure, and each inserted
block cites its files and lines. The six units are headed GPL-2.0-or-later (from shadPS4); each block says that the
combined file is GPL-2.0 with AnyPS5's part GPL-2.0-only. No IDA type name, no Orbital and no IDA reference is in any
inserted line.

## Voice (`libVoice.cpp`, `KYTY_BC5_LOAD_VOICE`): 2 ported, 4 already match, 8 held

**Split state (the coordinator's question).** libSceVoice's other 16 calls are the live table `InitAudio_1_Voice` in
`libs/libAudio.cpp:495-512` (input md5 45ca1ece07c4394d8700f7a57d9f0fbb, read only), same namespace `Libs::LibVoice` and
the same key (`Voice` = `libSceVoice` once "libSce" is dropped, `loader/symbolDatabase.cpp:10-22`). The 14 NIDs here and the
16 there are disjoint. What the live side keeps, all `static` in libAudio.cpp:
- `g_voice_ports` (`:256`): 256 slots, ids handed out round-robin from 1 to 254 (`alloc_voice_port`, `:260-288`);
  `g_voice_started` (`:258`). No initialized flag, no initialization mode, no mute flag.
- `VoiceInit` (`:298-306`) never fails, ignores its parameter and version, and resets the ports. No live call ever
  answers "not initialized"; `CreatePort` before `Init` gives a port (`:313-327`).

What each AnyPS5 function (`core/libs/prx/libSceVoice/Export.cpp`) needs, and the verdict:
- **The initialized flag** (every call but VADSetVersion and VADAdjustment). The state "not initialized" cannot be seen
  in our build: the live side has no such state and answers every call as initialized. So the library counts as
  initialized here. This is what lets GetResourceInfo's check and the three "all" calls be decided.
- **The port table** (GetMuteFlag, SetMuteFlag, PausePort, ResumePort, ResetPort, SetBitRate, UpdatePort): port
  existence (PORT_NOT_FOUND 0x804E0807) lives in libAudio.cpp's static `g_voice_ports`, which libVoice.cpp cannot read
  without a header or libAudio.cpp edit (both forbidden here). Also, AnyPS5's range check (`> 127` gives 0x804E0804)
  would refuse the live table's own ports from its 128th creation on (ids run to 254). SetBitRate and UpdatePort also
  change the bitrate and volume that the live GetBitRate and GetVolume report (`:459-493`). The initial mute comes from
  CreatePort's parameter, which the live CreatePort drops. **Held, all seven.**
- **The initialization mode** (GetResourceInfo's four limits, AnyPS5 `:379-392`): the mode is sceVoiceInit's parameter,
  which the live VoiceInit drops. **Held**; the null check before it is ported.
- **InitHQ** (AnyPS5 `:443-445` runs sceVoiceInit): it is the live Init's twin and would have to reset the live port
  table; its first check (0x804E0802 when initialized) needs the flag the live side does not keep. **Held.**

Ported (output `libVoice.cpp:24-71` block, wrappers `:78-87` and `:144-150`, registration `:155`):
- `sceVoiceVADSetVersion` (wFeAxEeEi-8), AnyPS5 `:491-493`: versions 0 and 1 give 0, any other INVALID_ARGUMENT
  0x804E0805. Note `docs/dev/debt/libSceVoice.md:14`: the rule follows shadPS4; shadPS4 60c42b9
  `src/core/libraries/voice/voice.cpp:556-563` and `voice_error.h:9` give the same. Not measured on a PS5.
- `sceVoiceGetResourceInfo` (Z6QV6j7igvE), check only, AnyPS5 `:374-378`: a null info gives 0x804E0805 (before and
  after the live Init, the library counting as initialized). A non-null info keeps today's 0 with nothing written.

Already match (today's 0, libVoice.cpp input `:40-43`, `:55-58`, `:70-73`, `:80-83`):
- `PausePortAll`, `ResumePortAll` (AnyPS5 `:543-555`): their only other answer is "not initialized" (see above).
- `SetMuteFlagAll` (`:495-501`): 0; the flag it sets is read only by GetMuteFlag, which is held.
- `VADAdjustment` (`:475-480`): it stores two floats nothing reads and sets no return value (note `:11`, BunnyFl's
  firmware 13.42 run under an emulator, decision 1); our 0 is what a caller that reads the register would see from a
  well-defined host.

**Decision 3 rows (the coordinator's correction).** Note `:17`: SetMuteFlagAll, SetBitRate and UpdatePort have
signatures from Orbital's IDA `db_types.json` and behaviour from VitaSDK. Under the correction they are portable from
behaviour. Their verdicts here come from split state, not provenance: SetBitRate and UpdatePort are held (above),
SetMuteFlagAll already matches. Nothing of them is in the code.

**Size of the hold.** AnyPS5 body lines: GetMuteFlag 11, SetMuteFlag 10, PausePort 10, ResumePort 10, ResetPort 10,
SetBitRate 16, UpdatePort 22, InitHQ 3 (+ sceVoiceInit's 11), GetResourceInfo's limits 15: about 118 lines, 0.8 d by the
rule. They cannot be done in libVoice.cpp: they need the live port table, so they belong in libAudio.cpp (or a header that
shares its state), with a decision on the id range (console 0-127, live 1-254), an initialized flag and the mode in
VoiceInit, and the mute flag in CreatePort.

**Test cases** (12 per mode): registration (14 here, 16 live, disjoint both ways); in tl2's order the 16 live NIDs resolve
to libAudio.cpp and the 14 to this table, by `Find` and by `FindByNid`; VADSetVersion 0/1 and 2/-1/100; GetResourceInfo
null and non-null, before and after the live sceVoiceInit (and End); GetMuteFlag(1, out) leaves out untouched; the 12
held or matching calls give 0. Off: 0 everywhere, nothing written.

## ScreenShot (`libScreenShot.cpp`, `KYTY_BC5_LOAD_SCREENSHOT`): 5 ported, 2 already match, 7 held

No live table registers libSceScreenShot (0 live NIDs; the overlap scan below).

**Source.** AnyPS5 `core/libs/prx/libSceScreenShot/Export.cpp:12-86`, commit f2bdca611. Its message says the checks are
"as the PS5 module does" and "in the module's order": a reading of the PS5 module, with no run, no disassembly and no
address named. It is taken under decision 1, as batch 1 took Ime's ForTestFunction (tbc0405-notes.md I2). Note
`docs/dev/debt/libSceScreenShot.md:5-7`. shadPS4 60c42b9 `screenshot.cpp` only stubs these.
**Provenance call for the maintainer:** turn `KYTY_BC5_LOAD_SCREENSHOT` off to drop them.

Ported (output block `:33-156`, wrappers `:168-232`, includes `:14-25`, registration `:248`):
- `Disable` / `Enable` (tIYf0W5VTi8, 2xxUtuC-RzE): set and clear one process-wide flag, 0.
- `IsDisabled(id, out)` (-SV-oTNGFQk): ERROR_ARGUMENT 0x80BE0001 for id -1 or a null out; else writes the flag (1 or 0,
  32 bits), 0. AnyPS5's ERROR_ARGUMENT for a non-null unmapped out is its host-safety fallback (note `:7`, exp 0405 row
  494cf2788 "internal") and is not ported.
- `SetOverlayImage(path, x, y)` and `SetOverlayImageWithOrigin(path, x, y, origin)` (ahHhOf+QNkQ, 73WQ4Jj0nJI), in this
  order: origin 1-9; a non-null path, x 0-1919, y 0-1079 (0-3839, 0-2159 for SDK 3.50 or later); a path under 1024
  bytes (each else 0x80BE0001); a file our kernel opens that is not a directory (else ERROR_OVERLAY_FILE 0x80BE0003); 1
  byte to 2 MiB, 8 MiB for SDK 3.50 or later (else ERROR_OVERLAY_SIZE 0x80BE000E); then 0, the image not kept.
  - The file goes through our kernel: `LibKernel::FileSystem::KernelOpen(path, 0, 0)`, `KernelFstat`, `KernelClose`
    (`kernel/fileSystem.h:42-50`, a public header, unchanged), as AnyPS5 goes through its sceKernelOpen.
  - The SDK version is the one our `sceKernelGetCompiledSdkVersion` gives (`libs/bc5LleAgc.cpp:9983-10007`, exp 0336:
    the u64 at process parameter +0x10, its high half, else its low half, within 0x01000000-0x1FFFFFFF; else
    0x0A000000), through `Loader::Bc5ProcParam()` (`loader/runtimeLinker.cpp:2069-2071`), declared locally as
    bc5LleAgc.cpp does (`:70-72`). AnyPS5 reads the low 32 bits at +0x10. TODO(verify): the SDK field.

Already match: `EnableNotification`, `DisableNotification` (input `:35-38`, `:45-48`; AnyPS5 `:80-86`, note `:5`).

Held (AnyPS5 throws, note `:11-12`): `Capture`, `GetAppInfo`, `GetDrcParam`, `IsVshScreenCaptureDisabled`, `SetParam`,
`SetDrcParam`, and `ScreenShotDummy` AS45QoYHjc4 (AnyPS5 has it under libSceHttp2 as an unknown, not implemented). Size: no
behaviour to port.

**Test cases** (19 per mode): registration 14; IsDisabled at start, with -1, with null; Disable then IsDisabled(7); Enable
then IsDisabled(0); the notifications; files made under `./tbv0405-app0` mounted at `/app0` (16 bytes, 0 bytes, 8 MiB,
8 MiB + 1, a directory, a missing file); the kernel opens the test file; (0, 0) and (3839, 2159); null; x -1, x 3840,
y -1, y 2160; a 1024-byte and a 1023-byte path; missing and directory; 0 bytes, 8 MiB, 8 MiB + 1; WithOrigin origin 0,
10, null; origin 1 and 9; origin 5 with x 3840, missing, 8 MiB + 1; no descriptor left open (the next open gets the same
descriptor); the 7 held give 0. Off: 0 everywhere, nothing written.

## DiscMap (`libDiscMap.cpp`, `KYTY_BC5_LOAD_DISCMAP`): 2 ported, 3 held

**Source.** AnyPS5 `core/libs/prx/libSceDiscMap/Export.cpp:8-33` (commits 716d81186, 31935cc85). Note
`docs/dev/debt/libSceDiscMap.md:5`: "the confirmed no-bitmap path", NO_BITMAP_INFO "before validating any argument", and
"The supplied module confirms" the argument widths (a module reading, decision 1). 716d81186's message: "as shadPS4 and
fpPS4 do". shadPS4 60c42b9 `src/core/libraries/disc_map/disc_map.cpp:16-18, 28-31` and `disc_map_codes.h:9` give the same,
so the answer stands on shadPS4 alone too.

Ported (output block `:63-93`, wrappers `:110-121` and `:144-156`, registration `:184`):
`sceDiscMapIsRequestOnHDD` (lbQKqsERhtE) and `ioKMruft1ek` (our `Func_8A828CAEE7EDD5E9`) return NO_BITMAP_INFO
0x81100004, read no argument and write nothing.

Held (AnyPS5 throws, note `:9`, `:13`): `GetPackageSize` (fl1eoDnwQ4s), fJgP+wqifno, 5+vOlukvkfg. Exp 0405 row 141f7c407
("declare 2 callable exports") said "match": our OK stubs stay. shadPS4-only candidates if the top wants them (not
ported: the brief keeps a stub where AnyPS5 has no behaviour): GetPackageSize and 5+vOlukvkfg give NO_BITMAP_INFO
(`disc_map.cpp:12-14`, `:33-35`); fJgP+wqifno writes three 32-bit zeros and gives 0 (`:20-26`). About 8 lines.

**Test cases** (6 per mode): registration 5; IsRequestOnHDD with arguments (result untouched) and all null; ioKMruft1ek
with outputs (untouched) and all null; the 3 held give 0. Off: 0, nothing written.

## ulobjmgr (`libUlobjmgr.cpp`, `KYTY_BC5_LOAD_ULOBJMGR`): 2 ported, 2 held

**Source.** AnyPS5 `core/libs/prx/ulobjmgr/Export.cpp:10-33`, which follows shadPS4 60c42b9
`src/core/libraries/ulobjmgr/ulobjmgr.cpp:12-25` (note `docs/dev/debt/ulobjmgr.md:5, :9`: PS4 behaviour, not measured on a
PS5). TODO(verify): the PS5 signature and the raw errno answers.

Ported (output block `:63-107`, wrappers `:109-139`, registration `:180`):
- `_sceUlobjmgrRegisterObject(object, kind, id_out)` (BG26hBGiNlw): a zero object, a zero kind or a null id_out gives the
  raw EINVAL 22; otherwise id 0 is written, 0. No object is registered.
- `_sceUlobjmgrUnregisterObject(id)` (Smf+fUNblPc): id 0x4000 or more gives 22, else 0.
- Not ported: AnyPS5's EFAULT 14 for an unwritable id_out (exp 0405 row 13f30a223, "partial"): its host-safety
  fallback; we have no guest-memory probe here.

Held (AnyPS5 throws, note `:13`): HZ9Q2c+4BU4, SweJO7t3pkk. shadPS4-only candidates: HZ9Q2c+4BU4 gives 0 (today's answer),
SweJO7t3pkk gives 22 for a zero argument (`ulobjmgr.cpp:27-36`).

**Test cases** (6 per mode): registration 4; Register OK (id 0 written); zero object, zero kind, null id (22 each, id
untouched); Unregister 0 and 0x3fff; 0x4000 and 0xffffffff; the 2 held give 0. Off: 0, nothing written.

## CompanionHttpd (`libCompanion.cpp`, `KYTY_BC5_LOAD_COMPANIONHTTPD`): 8 ported, 3 already match, 6 held

**Source.** AnyPS5 `core/libs/prx/libSceCompanionHttpd/Export.cpp:9-109` (commit 346cafdb8: "keep the server state with
no companion device") and note `docs/dev/debt/libSceCompanionHttpd.md:5, :11` (not measured on a console). Error codes:
shadPS4 60c42b9 `src/core/libraries/companion/companion_error.h:12-21`, with ALREADY_REGISTERED 0x80E4000C (the header's
0x80E4000 is one digit short, note `:11`).

Ported (output block `:48-244`, wrappers `:266-441`, registration `:446`): `OptParamInitialize` (clears 0x60 bytes;
INVALID_PARAM 0x80E40004 for null), `Initialize` (INVALID_PARAM, ALREADY_INITIALIZED 0x80E40007), `Terminate`
(NOT_INITIALIZED 0x80E40006), `RegisterRequestCallback` (INVALID_PARAM, NOT_INITIALIZED, ALREADY_REGISTERED; kept, never
called), `UnregisterRequestCallback` (NOT_INITIALIZED), `Start` (ALREADY_STARTED 0x80E4000A), `Stop` (NOT_STARTED
0x80E4000B), `GetEvent` (INVALID_PARAM for null first, NOT_INITIALIZED, else NO_EVENT 0x80E40008, nothing written).
- The 0x60-byte block: titles fill +0x08, +0x10 and +0x58 after OptParamInitialize (note `:5`), so 0x60 is the least the
  behaviour forces. The console's defaults are unknown: zeros. TODO(verify).

Adapted where AnyPS5 throws (each TODO(verify), with its catcher line):
- Terminate of a started server: stops it and terminates, 0.
- UnregisterRequestCallback with none: today's 0, nothing changes.

Already match: `AddHeader`, `SetStatus`, `SetBody` (input `:40`, `:140`, `:150`): 0, arguments untouched (AnyPS5
`:111-121`; exp 0405 row b6b9998f7; shadPS4 `companion_httpd.cpp:12-15, 69-78`). Nothing of row b6b9998f7's source
(module bytes) is used.

Held (AnyPS5 throws, note `:7`; today's 0): `Get2ndScreenStatus`, `GetUserId`, `Initialize2`,
`RegisterRequestBodyReceptionCallback`, `RegisterRequestCallback2`, `UnregisterRequestBodyReceptionCallback`. Size: no
behaviour to port.

**Split state inside this table.** Initialize2 is held, but the ported Start, Stop, Terminate, Register and GetEvent check
the initialized flag. A title that initializes through Initialize2 would then get NOT_INITIALIZED where it gets 0 today.
So, with the switch on, the held Initialize2 keeps today's 0 and also marks the library initialized (a host choice,
TODO(verify), with its catcher line). RegisterRequestCallback2 stays a plain stub: Unregister with no callback answers 0
anyway. No live table registers libSceCompanionHttpd.

**Test cases** (19 per mode): registration 17; before Initialize: GetEvent (NOT_INITIALIZED, untouched) and null
(INVALID_PARAM first), Start/Stop/Terminate/Unregister, Register and Register(null); OptParamInitialize null and a 0x70
buffer (0x60 cleared, the rest untouched); Initialize null, twice; GetEvent NO_EVENT; Register twice; Start twice; Stop
twice; Unregister twice; Terminate twice; Initialize, Start, Terminate while started, Start; Initialize2, Start, Stop,
Terminate, Terminate; AddHeader/SetStatus/SetBody leave the response untouched; 5 held give 0. The request callback exits
the test if it is ever called. Off: 0 everywhere, nothing written.

## CompanionUtil (`libCompanion.cpp`, `KYTY_BC5_LOAD_COMPANIONUTIL`): 1 ported, 4 already match

`sceCompanionUtilGetEvent` (cE5Msy11WhU) returns NO_EVENT 0x80AD0008, reads and writes nothing. **Source: shadPS4**
60c42b9 `src/core/libraries/companion/companion_util.cpp:31-36`, `companion_error.h:27`. AnyPS5
`core/libs/prx/libSceCompanionUtil/Export.cpp:9-11` gives the same value, but its note
(`docs/dev/debt/libSceCompanionUtil.md:9`) names a disassembly with an address ("export cE5Msy11WhU at 0x100") as its
source, so that row is not used; the value stands on shadPS4. (The top's memory records the maintainer's later Pad rule,
rows from a disassembly with addresses rewritten from behaviour; either way the answer is the same.)

Output block `:495-520`, wrapper `:522-529`, registration `:578`.

Already match: GetRemoteOskEvent, Initialize, OptParamInitialize, Terminate (input `:271-305`): 0 in AnyPS5 `:13-27` and
shadPS4 `:38-56`.

**Test cases** (4 per mode): registration 5; GetEvent with a buffer (untouched) and null; the 4 give 0.

## VideoRecording (`libVideoRecording.cpp`, `KYTY_BC5_LOAD_VIDEORECORDING`): 1 held

`sceVideoRecordingSetInfo` (Fc8qxlKINYQ) is held (today's 0). AnyPS5 `core/libs/prx/libSceVideoRecordingP/Export.cpp:193-205`
(commit cf717cd80, "restore info selectors and unopened errors") answers by selector: 0x8002/0x8003 give 0x80A80003 for
a null or short value, else 0x80A80002; 0xa004/0xa006 give 0x80A80006; any other 0x80A80003. Its note
(`docs/dev/debt/libSceVideoRecordingP.md:5`, quoted): "support native validation and errors before a recording context
exists". That names no run, no measurement and no reading. Exp 0405 #33's firmware 13.40 measurement inside a retail title
is the note's `:20, :22` (commit a344e526e): Open, QueryMemSize, GetStatus, Start, Stop, Close, none of which this table
registers; a344e526e does not touch SetInfo. The brief: port with TODO(verify) if the note names a run, hold otherwise.
**Held.** Size: 13 lines, 0.1 d. The unit gets only the switch and its line (output block `:62-85`, registration `:107`).

**Test cases** (2 per mode): registration 1; SetInfo 0x8002, 0xa004, 0: 0 each, both ways.

## Live registrations (the brief's recheck)

`scratchpad/e7/tbv/overlap.py` lists every NID in the seven tables' `LIB_FUNC` lines and greps every quoted 11-character
NID in every `.cpp`, `.h` and `.inc` of the input tree. Input units: 60 NIDs (Voice 14, ScreenShot 14, DiscMap 5,
ulobjmgr 4, CompanionHttpd 17, CompanionUtil 5, VideoRecording 1), none twice, **0 registrations elsewhere**. Output units:
the same 60, 0 elsewhere. No port adds or removes a registration.

## Exp 0405 R1 rows for these libraries (`raw\r1-verdicts\*.tsv`)

| Row | Class | Here |
|---|---|---|
| B 141f7c407 DiscMap (2 exports) | shared match | held: AnyPS5 throws; our OK stubs stay |
| B 13f30a223 ulobjmgr (EFAULT) | shared partial | EINVAL and id 0 ported; EFAULT not (host safety) |
| B d34a43407 ulobjmgr (2 exports) | shared match | held |
| C 648fba4f7, 85647ec86, e50128d91 Voice | excl.-provenance / partial / missing | GetPortInfo, ReadFromOPort, GetPortAttr: the live table's (libAudio.cpp), not this table's |
| C 7d1bb9c3d, 02bd033cc Voice (13.42 run) | excl.-provenance (decision 1) | VADAdjustment here already matches; VADPVTAdjustment, QAEnableRecording, DeviceInCustomerData, GetMemorySize are registered by no table: later work |
| C 8c1a7f338, a344e526e VideoRecording | new-export | not in our table (later work on unregistered exports, exp 0405 #33) |
| D2 494cf2788 ScreenShot | internal | not ported (host safety) |
| D2 b6b9998f7 CompanionHttpd | excl.-provenance | our stubs already return 0 |

## Risks

- **New error answers where today's stubs gave 0**, each the AnyPS5 or shadPS4 answer: DiscMap's NO_BITMAP_INFO (a caller
  such as a bundled Fios2 now learns there is no bitmap); CompanionHttpd's state errors and NO_EVENT (a title that took 0
  from GetEvent as "an event arrived" and read the unwritten event now sees none); CompanionUtil's NO_EVENT; ScreenShot's
  argument, file and size errors; Voice's VADSetVersion and GetResourceInfo(null); ulobjmgr's raw 22.
- **ScreenShot opens the title's file through our kernel.** A path our mounts do not serve gives 0x80BE0003 where it gave
  0. The SDK-version field is our kernel's reading, not AnyPS5's (TODO(verify)); the SDK < 3.50 limits are not reached by
  the test (no program is loaded, so the version is 0x0A000000).
- **IsDisabled writes 4 bytes** to the title's pointer; what the id selects on a console is unknown (note `:7`).
- **Initialize2's coupling** is a host choice (TODO(verify)).
- **Voice stays mostly stubbed**: the 8 held calls answer 0 for any port, as today, and GetResourceInfo writes no limits.
  A title that uses voice chat sees no change from today except the two ported answers.
- The edited stubs now declare parameters; the off path ignores them (ABI unchanged: SysV argument registers).

## Verified on the laptop

- `mktbv0405.py <e7 input tree> <out>` prints the six output md5s below. Run on its own output it refuses ("the unit has
  the edit already").
- Built-in checks per unit: the pinned md5; every anchor once; each block inside its own namespace (after its table's
  `LIB_VERSION`, before the next); the balance of braces, parentheses and brackets per block, per edit and per unit;
  helper-use counts; ASCII inserts; LF and the BOM kept; undoing the edits gives the input back byte for byte.
- `diff` input/output: besides inserted lines, only the 14 signature lines of the stubs that now take parameters change
  (Voice 2, ScreenShot 3, DiscMap 2, ulobjmgr 2, Companion 5, VideoRecording 0); every other input line is kept. The
  only non-ASCII bytes in the outputs are the inputs' BOMs.
- **Syntax:** Visual Studio's clang++ 22 (msvc target), `-fsyntax-only -std=c++20 -Wall -Wextra -Werror`, the stand-in
  `cmake_config.h`/POSIX headers (`scratchpad/lib0405chk/stub`), `scratchpad/e6/tbn/sched_standin.h` (MSVC has no
  `<sched.h>`), fmt from Inori_GPCS4, magic_enum from InoriRus_Kyty: the six outputs, the six inputs and `tbv0405.cpp`
  (plus `-Wno-deprecated-declarations` for Windows' POSIX names) are clean.
- **Stand-in run** (`scratchpad/e7/tbv/run`, not a deliverable). `driver.cpp` compiles `tbv0405.cpp` itself with its
  `main` renamed (its `Init()` starts the emulator's subsystems, which do not link on the laptop) and runs the same
  registration and the same seven Case functions. It links the six output units, the input tree's real
  `symbolDatabase.cpp` and `libAudio.cpp` (the live Voice table), fmt, tbc's log/timer/thread stand-ins, a `Common::Mutex`
  stand-in, and stand-ins for `KernelOpen`/`KernelFstat`/`KernelClose`/`Mount` (host files, descriptors from 3, the lowest
  free one, as kernel/fileSystem.cpp does) and `Bc5ProcParam` (0). lld's `/force:unresolved` covers only symbols of the
  renamed main and of libAudio.cpp's other tables (`link.txt`), none of them called.
  - All `=1`: **on 68 of 68**, exit 0; the seven "port on" lines and the three catcher lines on stderr; the directory left
    holding only the run's own output.
  - All `=0`: **off 68 of 68**. Unset: off 68 of 68. A mix (screenshot `1`, companionutil `on`, voice `0`): mixed 68 of
    68. The argument `on` with a mix: exit 2.
  - **Negative control:** the same driver linked with the six unedited input units: off 68 of 68 (every off expectation
    is today's code's answer), on 29 of 68 (39 cases catch the missing ports).
- **Not checked:** the box's Linux compile and link; the test's `Init()` (the emulator's subsystems) and the real
  `kernel/fileSystem.cpp` under the ScreenShot cases (the stand-in imitates them); the real `Bc5ProcParam` with a
  program loaded. The box build is the first real run.

## Files

| File | md5 |
|---|---|
| `mktbv0405.py` | a34256f1509679d34576ba83156ff8a1 |
| `tbv0405.cpp` | 2f802c927bc0795d144a2c8d64d37efc |
| in `src/libs/libVoice.cpp` | 5f63709dbf1028ceaf7784d6a070f64e |
| in `src/libs/libScreenShot.cpp` | cb913d120daa27f0d35702edeee71b19 |
| in `src/libs/libDiscMap.cpp` | e4d975b8a55da8aed19281d7c6d17b33 |
| in `src/libs/libUlobjmgr.cpp` | b85eafd0de28af091302a8aeeeb323c1 |
| in `src/libs/libCompanion.cpp` | cf8ad7a647a84ba04964eb0adfe2ab02 |
| in `src/libs/libVideoRecording.cpp` | e8f90a3574dcae417df52f1802515f4d |
| out `src/libs/libVoice.cpp` | c186ab1e0900c37e8966fe0a71f14f53 |
| out `src/libs/libScreenShot.cpp` | 7bb296c3b00e8d8c9aab448c9f0846d1 |
| out `src/libs/libDiscMap.cpp` | f6e31686ccc82f74bcbb67c347b2701b |
| out `src/libs/libUlobjmgr.cpp` | aa1959cb68ba3fea4346779edda2308e |
| out `src/libs/libCompanion.cpp` | 8e61ea093cdcfc73aac6e11d85021735 |
| out `src/libs/libVideoRecording.cpp` | afdd0f1764b8cc993d18ff5f30b4917e |
| read only: `src/libs/libAudio.cpp` (the live Voice table) | 45ca1ece07c4394d8700f7a57d9f0fbb |

## Case counts

All seven switches on: 68 cases (voice 12, screenshot 19, discmap 6, ulobjmgr 6, companionhttpd 19, companionutil 4,
videorecording 2), ending `tbv0405: on 68 of 68; end`. All off or unset: the same 68 cases with today's answers, ending
`tbv0405: off 68 of 68; end`. A mix runs each table's cases by its own switch and ends `mixed 68 of 68`.
