# tbv0405: Voice (with the live table's port calls), ScreenShot, DiscMap, ulobjmgr, CompanionHttpd and CompanionUtil ported before they are loaded (series e7)

Port agent `tbv`, 2026-11-04. This covers exp 0405 decision 4 ("=> B => B"), dead-table batch 2. Each table that is
compiled but never loaded by `Libs::InitAll` is ported first: AnyPS5's code for the NIDs our table registers. Then it is
loaded behind its own switch by the loader agent `tl2` (libs.cpp, not edited here).

This version takes in the top session's three follow-ups:
1. **Held stubs.** They are not registered while a table's switch is on, so a title's call shows exp 0327's
   `[bc5] stubbed import called` line (`loader/runtimeLinker.cpp:362`; that stub returns 0). With the switch off they are
   registered as today.
2. **Voice port calls.** The eight Voice calls held for split state are implemented in libAudio.cpp, together with
   SetMuteFlagAll (see Voice), behind `KYTY_BC5_VOICE_PORTS`, with an explicit id map.
3. **VideoRecording.** It is dropped: `libVideoRecording.cpp` stays as its input, and tl2 drops its loader row.

Files: `mktbv0405.py` (one script, six units), `tbv0405.cpp` (the CPU test), and this note. The units are the e7 input
tree's (= e6's sources). All six are base-tree files, LF. The five dead-table units have a UTF-8 BOM; libAudio.cpp has
none. The md5s are pinned in one dict (`PINNED`).

## Switches and journal lines

Each switch is off by default and read once. Unset, empty or `0` is off; any other value is on.

| Switch | Where | stderr line when on (off: `[bc5] exp 0405: <word> port off`) |
|---|---|---|
| `KYTY_BC5_LOAD_VOICE` | `Libs::LibVoice::InitVoice_1` (libVoice.cpp) | `[bc5] exp 0405: voice port on (items: VADSetVersion GetResourceInfo-check; 8 held, not registered)` |
| `KYTY_BC5_VOICE_PORTS` | the live `Libs::LibVoice::InitAudio_1_Voice` (libAudio.cpp) | `[bc5] exp 0405: voiceports port on (items: GetMuteFlag SetMuteFlag SetMuteFlagAll PausePort ResumePort ResetPort SetBitRate UpdatePort InitHQ; console ids 0-127 = live slots 1-128)` |
| `KYTY_BC5_LOAD_SCREENSHOT` | `Libs::LibScreenShot::InitScreenShot_1` | `[bc5] exp 0405: screenshot port on (items: Disable Enable IsDisabled SetOverlayImage SetOverlayImageWithOrigin)` |
| `KYTY_BC5_LOAD_DISCMAP` | `Libs::LibDiscMap::InitDiscMap_1` | `[bc5] exp 0405: discmap port on (items: IsRequestOnHDD ioKMruft1ek)` |
| `KYTY_BC5_LOAD_ULOBJMGR` | `Libs::LibUlobjmgr::InitUlobjmgr_1` | `[bc5] exp 0405: ulobjmgr port on (items: RegisterObject UnregisterObject)` |
| `KYTY_BC5_LOAD_COMPANIONHTTPD` | `Libs::CompanionHttpd::InitCompanionHttpd_1` | `[bc5] exp 0405: companionhttpd port on (items: OptParamInitialize Initialize Terminate RegisterRequestCallback UnregisterRequestCallback Start Stop GetEvent; Initialize2 adapted; 5 held, not registered)` |
| `KYTY_BC5_LOAD_COMPANIONUTIL` | `Libs::CompanionUtil::InitCompanionUtil_1` | `[bc5] exp 0405: companionutil port on (items: GetEvent)` |

- `KYTY_BC5_VOICE_PORTS` is printed by libAudio.cpp. libVoice.cpp reads the same variable silently, with the same rule.
- Catcher lines, printed once each, only when their switch is on:
  - companionhttpd: Terminate of a started server; Unregister with no callback; Initialize2.
  - voiceports: ResetPort of a device port while started; SetBitRate on a port that is not a voice port or with a rate
    outside the list; UpdatePort with a null parameter, another port type, or such a rate.

**Off is exactly today's path.**
- Each edited stub runs `PRINT_NAME()`, then `if (switch) return port(...)`, then today's `return`.
- Each dead table registers every NID as today.
- libAudio.cpp's live functions are unchanged. Each added line there sits behind `Bc5VoicePortsOn()`, and only one input
  line is rewritten: alloc's wrap test gains `|| (Bc5VoicePortsOn() && …)`.

## Verdicts

| Table | NIDs | ported | adapted | already match | held: not registered when on |
|---|---|---|---|---|---|
| Voice (dead) | 14 | 2 (VADSetVersion; GetResourceInfo's check) | | 3 (PausePortAll, ResumePortAll, VADAdjustment) + SetMuteFlagAll while voiceports is off | 8 held here; with voiceports on, the live table's |
| Voice (live, voiceports) | +9 | 9 (the 8 + SetMuteFlagAll) | | | |
| ScreenShot | 14 | 5 | | 2 | 7 |
| DiscMap | 5 | 2 | | 0 | 3 |
| ulobjmgr | 4 | 2 | | 0 | 2 |
| CompanionHttpd | 17 | 8 | 1 (Initialize2) | 3 | 5 |
| CompanionUtil | 5 | 1 | | 4 | 0 |
| **total** | **59** | **20 dead + 9 live** | **1** | **12 (+1)** | **17 (+8 Voice)** |

Sources: AnyPS5 (github.com/boykopovar/AnyPS5) @ 4f41f4c375f5abb487dbd184fbc150f31994d762, GPL-2.0-only, and shadPS4 @
60c42b9, GPL-2.0-or-later. Each is ported in adapted form, with our own names and structure, and each inserted block cites
its files and lines. No IDA type name, Orbital or IDA reference appears in any inserted line.

## Voice: the dead table (`libVoice.cpp`, `KYTY_BC5_LOAD_VOICE`) and the live port calls (`libAudio.cpp`, `KYTY_BC5_VOICE_PORTS`)

**Split state.** libSceVoice's other 16 calls are the live table `InitAudio_1_Voice`.
- It is at libAudio.cpp input `:495-512`, with the same key `Voice` (`libSceVoice` once "libSce" is dropped).
- It keeps its port table static: `g_voice_ports` `:256`, 256 slots, handed out round-robin 1-254 by `alloc_voice_port`
  `:260-288`, and `g_voice_started` `:258`.
- It keeps no initialized flag: `VoiceInit` `:298-306` never fails, and no live call answers "not initialized".
- So the library counts as initialized everywhere: NOT_INITIALIZED (0x804E0801) is never given.

**Dead table, ported (output `libVoice.cpp:24-84` block, registration `:167-204`):**
- `sceVoiceVADSetVersion`: versions 0 and 1 give 0, anything else 0x804E0805. Source: AnyPS5 `Export.cpp:491-493`; note
  `docs/dev/debt/libSceVoice.md:14`; shadPS4 `voice.cpp:556-563` gives the same.
- `sceVoiceGetResourceInfo`, the null check only: a null info gives 0x804E0805. AnyPS5 `:374-378`. The four limits depend
  on the initialization mode, which the live `VoiceInit` drops, so they are still held: a non-null info gets today's 0.

**Dead table, registration** (each line wrapped in its condition, `bc5_on` = LOAD_VOICE, `bc5_ports` = VOICE_PORTS):

| NIDs | Registered by the dead table when |
|---|---|
| GetResourceInfo, PausePortAll, ResumePortAll, VADAdjustment, VADSetVersion | always |
| SetMuteFlagAll | `!bc5_ports` |
| GetMuteFlag, SetMuteFlag, PausePort, ResumePort, ResetPort, SetBitRate, UpdatePort, InitHQ | `!bc5_on && !bc5_ports` |

- The live table registers those nine NIDs only while `KYTY_BC5_VOICE_PORTS` is on. So no NID is ever registered twice.
- The test's case 1 checks all 30 NIDs in every switch combination it runs.

**Live port calls (output `libAudio.cpp`).** Map block `:261-312`, calls block `:570-755`, registration `:774-784`.
Edits: includes `:10-13`; alloc `:322-323` and `:342-346`; `get_voice_port` `:353-360`; `VoiceInit`/`VoiceEnd` reset
`:369-371`, `:445-447`.

From AnyPS5 `core/libs/prx/libSceVoice/Export.cpp`:

| Call | AnyPS5 lines |
|---|---|
| SetMuteFlag | `:351-360` |
| GetMuteFlag | `:362-372` |
| ResetPort | `:403-412` |
| PausePort | `:414-423` |
| ResumePort | `:425-434` |
| InitHQ (it runs sceVoiceInit) | `:443-445` |
| SetMuteFlagAll | `:495-501` |
| SetBitRate | `:503-518` |
| UpdatePort | `:520-541` |
| the voice bitrates 3850, 4650, 5700, 7300, 11800, 12200, 14400, 16000, 22533 | `:82-95` (commit 09fb692fa; the public VitaSDK and RPCS3 voice headers list the same rates) |

Notes `:5, :14, :17`: not measured on a PS5.

- **The id map (top's request).** While on, a console id c (0-127) names live slot c + 1 (1-128).
  - CreatePort hands out 0-127, the first one 0, and refuses a 129th port with 0x804E0808. The wrap test stops the
    round-robin at slot 128.
  - Every live call that takes an id looks it up through `get_voice_port`, which applies the map: Connect, Disconnect,
    Delete, GetPortInfo, GetBitRate, SetVolume, GetVolume.
  - The nine port calls return INVALID_PORT 0x804E0804 above 127 and PORT_NOT_FOUND 0x804E0807 for a free slot.
  - Off, ids are today's 1-254. Slots 129-254 stay unused while on.
  - Source for the console's 0-127: AnyPS5 `:109` (the free ids 0-127) and the `> 127` checks (`:218`), with note
    `:16`, which says the bound was observed in runs (decision 1). shadPS4 uses 64 ports instead.
- **Mute flags** are kept in a per-slot array next to the live table. CreatePort's mute parameter sets a port's flag
  (while on), as do SetMuteFlag and UpdatePort. SetMuteFlagAll makes every port read as muted without changing the port
  flags. Init and End clear them.
- **Bitrate and volume** are the live port's own fields, so the live GetBitRate and GetVolume report what SetBitRate and
  UpdatePort set.
- **InitHQ** is the live VoiceInit.
- **Adapted where AnyPS5 throws** (today's 0, nothing changed, catcher line, each TODO(verify)):
  - SetBitRate on a non-voice port or with a rate outside the list;
  - UpdatePort with a null parameter, another port type, or such a rate;
  - ResetPort of a device port while started.
- **Decision 3:** SetMuteFlagAll, SetBitRate and UpdatePort have IDA-sourced signatures (note `:17`). They are ported
  from behaviour only: our own names (`Bc5VoicePorts*`) and argument names, and comments that cite AnyPS5's behaviour.
- **SetMuteFlagAll is the ninth.** The coordinator named eight calls. SetMuteFlagAll had to move too: GetMuteFlag (now
  live) reads its flag, which the dead table cannot set.
- **No lock:** the live table's calls take none either.

**Dead GetResourceInfo's limits** stay held (about 15 AnyPS5 lines). To port them, the live VoiceInit would have to keep
its app-type parameter, which it drops today. This is a candidate for the same switch.

**Test cases.**
- voice: 11 per mode.
  - Registration of all 30 NIDs against the expected table: none twice, the held ones absent when on.
  - Each NID resolves (Find and FindByNid, tl2's order) to the table that registered it, or to nothing.
  - VADSetVersion 0/1 and 2/-1/100.
  - GetResourceInfo null and non-null, before and after the live Init and End.
  - The registered dead stubs give 0.
- voiceports: 29 on, 7 off.
  - On:
    - registration of the nine;
    - CreatePort ×128 gives 0-127 in order; the 129th is refused;
    - GetMuteFlag at 0 and 127, beyond at 128, 254 and 0xffffffff, and with null;
    - the live GetPortInfo, GetBitRate, SetVolume and GetVolume through the map, and beyond it;
    - SetMuteFlag, and SetMuteFlagAll on and off;
    - Pause, Resume and Reset, also beyond the range and while started;
    - SetBitRate, and UpdatePort with NaN volume, plus their adapted cases;
    - DeletePort, then the four PORT_NOT_FOUND answers;
    - a new port reusing id 127;
    - InitHQ resetting the ports and flags, a new port id 0, End.
  - Off: the live table as today. Ids 1 and 254 are the ends, 0 and 255 are beyond, the 255th CreatePort is refused, and
    the nine are not registered.

## ScreenShot (`libScreenShot.cpp`): 5 ported, 2 already match, 7 held

- **Source:** AnyPS5 `libSceScreenShot/Export.cpp:12-86`, commit f2bdca611. Its checks are "as the PS5 module does",
  "in the module's order": a module reading, decision 1. Note `libSceScreenShot.md:5-7`.
- **Ported** (output block `:33-157`): Disable, Enable, IsDisabled (0x80BE0001 for id -1 or a null out),
  SetOverlayImage, SetOverlayImageWithOrigin.
  - The overlay checks run in this order:
    1. origin 1-9;
    2. path non-null, x 0-1919/3839, y 0-1079/2159;
    3. path shorter than 1024 bytes;
    4. a file our kernel opens that is not a directory (else 0x80BE0003);
    5. size 1 byte to 2/8 MiB (else 0x80BE000E).
  - The larger limits apply from SDK 3.50 on. The SDK version is the one our kernel's `sceKernelGetCompiledSdkVersion`
    gives (exp 0336) via `Loader::Bc5ProcParam()`: TODO(verify).
- **Already match:** Enable/DisableNotification.
- **Held** (registration `:248-281`, not registered when on): Dummy (AS45QoYHjc4), Capture, GetAppInfo, GetDrcParam,
  IsVshScreenCaptureDisabled, SetParam, SetDrcParam. AnyPS5 does not implement them.
- **Tests:** 19 per mode, as before; the last case checks that the 7 held are absent when on, or registered and give 0
  when off.
- **Provenance call:** turn the switch off to drop the module-reading rows.

## DiscMap (`libDiscMap.cpp`): 2 ported, 3 held

- **Ported:** `sceDiscMapIsRequestOnHDD` and ioKMruft1ek return NO_BITMAP_INFO 0x81100004 without reading or writing.
  Sources: AnyPS5 `libSceDiscMap/Export.cpp:8-33` (716d81186, 31935cc85) and note `:5` (a module reading, decision 1);
  shadPS4 `disc_map.cpp:16-18, 28-31`.
- **Held**, not registered when on: GetPackageSize, fJgP+wqifno, 5+vOlukvkfg (registration `:182-218`).
- **shadPS4-only candidates** if the top wants them: GetPackageSize and 5+vOlukvkfg give NO_BITMAP_INFO
  (`disc_map.cpp:12-14, 33-35`); fJgP+wqifno writes three 32-bit zeros and gives 0 (`:20-26`).
- **Tests:** 6 per mode.

## ulobjmgr (`libUlobjmgr.cpp`): 2 ported, 2 held

- **Ported:** RegisterObject (raw EINVAL 22 for a zero object, a zero kind or a null id; else id 0 written) and
  UnregisterObject (22 from 0x4000). Sources: AnyPS5 `ulobjmgr/Export.cpp:10-33` and shadPS4 `ulobjmgr.cpp:12-25`.
  TODO(verify): the PS5 signature.
- **Held**, not registered when on: HZ9Q2c+4BU4, SweJO7t3pkk (registration `:178-209`).
- **Tests:** 6 per mode.

## CompanionHttpd (`libCompanion.cpp`): 8 ported, 1 adapted, 3 already match, 5 held

- **Ported:** the server state. Source: AnyPS5 `libSceCompanionHttpd/Export.cpp:9-109` (346cafdb8) and note `:5, :11`.
  Error codes from shadPS4 `companion_error.h:12-21`, with ALREADY_REGISTERED 0x80E4000C.
  - OptParamInitialize clears 0x60 bytes.
  - Initialize, Terminate, RegisterRequestCallback, UnregisterRequestCallback, Start, Stop, GetEvent (NO_EVENT).
  - Two adapted answers (TODO(verify), catcher): Terminate while started, and Unregister with no callback.
- **Initialize2: adapted, and registered both ways.** It is not a plain held stub. It keeps today's 0 and, while on,
  marks the library initialized. If it were unregistered, the import stub's 0 would leave the ported Start answering
  NOT_INITIALIZED to a title that initialized through it. This is a host choice; the catcher line shows any call.
  **For the top:** say if you want it unregistered like the other held ones.
- **Held**, not registered when on: Get2ndScreenStatus, GetUserId, RegisterRequestBodyReceptionCallback,
  RegisterRequestCallback2, UnregisterRequestBodyReceptionCallback (registration `:447-488`).
- **Tests:** 19 per mode. On, the table registers 12 of 17.

## CompanionUtil (`libCompanion.cpp`): 1 ported, 4 already match

- **Ported:** GetEvent gives NO_EVENT 0x80AD0008 and reads and writes nothing. Source: shadPS4 `companion_util.cpp:31-36`.
  AnyPS5 gives the same, but its note names a disassembly address, so it is not cited as the source.
- **Already match:** the other four (0).
- Nothing is held. **Tests:** 4 per mode.

## VideoRecording: dropped (top's follow-up 3)

`libVideoRecording.cpp` is not edited (input md5 e8f90a3574dcae417df52f1802515f4d stays). Its one call, SetInfo, is held:
AnyPS5's note `libSceVideoRecordingP.md:5` names no run. The table would register nothing when on, so tl2 drops its row.

## Live registrations

- `scratchpad/e7/tbv/overlap.py`: the 59 NIDs of the five dead units are registered nowhere else in the input tree
  (0 hits).
- In the output, libAudio.cpp registers the nine Voice NIDs at `:775-783`, inside `if (Bc5VoicePortsOn())`. The dead table
  skips them in that state, so none is registered twice (test case 1).

## Risks

- **New error answers where today's stubs gave 0**, each the AnyPS5 or shadPS4 answer: ScreenShot, DiscMap, ulobjmgr,
  Companion, Voice.
- **Held stubs no longer registered when on.** A title's call gets the import stub's 0 plus the 0327 line: the same
  value as today.
- **VOICE_PORTS changes the live ids** a title sees (0-127, not 1-254) and caps ports at 128, as the console does. A
  title that kept more than 128 voice ports open would now be refused.
- **The live voice table has no lock** (as before). The new per-slot mute state is unguarded too.
- **ScreenShot:** the SDK field (TODO(verify)), and kernel file access.
- **Initialize2's coupling** is a host choice.

## Verified on the laptop

- `mktbv0405.py <e7 input tree> <out>` prints the six md5s below. A unit that already has the edit is refused (tested
  with the edited libAudio.cpp beside four inputs: refused, nothing written).
- Built-in checks: pinned md5s; anchors once; each block inside its own namespace (after its `LIB_VERSION`, before its
  `LIB_DEFINE`); balance per block, per edit and per unit; helper counts; ASCII; LF and BOM as they were; undo gives the
  input back byte for byte.
- `diff` input/output, changed input lines only:

  | Unit | Changed lines | What |
  |---|---|---|
  | libVoice.cpp | 11 | 2 signatures + 9 wrapped `LIB_FUNC` lines |
  | libScreenShot.cpp | 10 | 3 + 7 |
  | libDiscMap.cpp | 5 | 2 + 3 |
  | libUlobjmgr.cpp | 4 | 2 + 2 |
  | libCompanion.cpp | 10 | 5 + 5 |
  | libAudio.cpp | 1 | the wrap test |

  Everything else is insertion. The only non-ASCII bytes are the inputs' BOMs.
- **Syntax:** VS clang++ 22, `-fsyntax-only -std=c++20 -Wall -Wextra -Werror` (stand-ins as before). The six outputs, the
  six inputs and `tbv0405.cpp` are clean.
- **Stand-in run** (`scratchpad/e7/tbv/run`). It compiles `tbv0405.cpp` itself with `main` renamed and runs the same
  registration and cases. It links the six output units (libAudio.cpp included, so the live table and its nine calls are
  real), `symbolDatabase.cpp`, fmt, and stand-ins for log/timer/thread/Mutex, `KernelOpen`/`Fstat`/`Close`/`Mount` and
  `Bc5ProcParam`.

  | Switches | Result |
  |---|---|
  | all seven `=1` | on 94 of 94, exit 0, the 7 on-lines and 6 catchers on stderr |
  | all `=0` | off 72 of 72 |
  | unset | off 72 of 72 |
  | voiceports only | mixed 94 of 94 |
  | voice only | mixed 72 of 72 |
  | voice=1, voiceports=0, screenshot, companionutil | mixed 72 of 72 |

  Each run left only its own output files behind.
- **Negative control:** the same test linked with the six unedited inputs: off 72 of 72 (every off expectation, the live
  table's 1-254 ends included, is today's code), on 21 of 94.
- **Not checked:** the box's Linux compile and link; the test's subsystem `Init()`; the real `fileSystem.cpp` under the
  ScreenShot cases.

## Files

| File | md5 |
|---|---|
| `mktbv0405.py` | 47b00f8d2fd099cff13dfdd5d51cfb5c |
| `tbv0405.cpp` | 5afd8c6b285c3fad5f97524b5d94126b |
| in `src/libs/libVoice.cpp` | 5f63709dbf1028ceaf7784d6a070f64e |
| in `src/libs/libScreenShot.cpp` | cb913d120daa27f0d35702edeee71b19 |
| in `src/libs/libDiscMap.cpp` | e4d975b8a55da8aed19281d7c6d17b33 |
| in `src/libs/libUlobjmgr.cpp` | b85eafd0de28af091302a8aeeeb323c1 |
| in `src/libs/libCompanion.cpp` | cf8ad7a647a84ba04964eb0adfe2ab02 |
| in `src/libs/libAudio.cpp` | 45ca1ece07c4394d8700f7a57d9f0fbb |
| out `src/libs/libVoice.cpp` | 35b06392f978247489feed9205e21bc7 |
| out `src/libs/libScreenShot.cpp` | 7b7ac871d0d963598109dad8bceef7f6 |
| out `src/libs/libDiscMap.cpp` | 1f965bcda04aeb3cc96ef1a05043595b |
| out `src/libs/libUlobjmgr.cpp` | d8c73e108a19961fd3b347024faa5a95 |
| out `src/libs/libCompanion.cpp` | 2c093c67a7d8efa5aad925d0b4a4fd28 |
| out `src/libs/libAudio.cpp` | a7025bf5ff622645915c4596e095b122 |
| not edited: `src/libs/libVideoRecording.cpp` | e8f90a3574dcae417df52f1802515f4d |

## Case counts

| Mode | Cases | voice | voiceports | screenshot | discmap | ulobjmgr | companionhttpd | companionutil | Last line |
|---|---|---|---|---|---|---|---|---|---|
| All seven on | 94 | 11 | 29 | 19 | 6 | 6 | 19 | 4 | `tbv0405: on 94 of 94; end` |
| All off or unset | 72 | 11 | 7 | 19 | 6 | 6 | 19 | 4 | `tbv0405: off 72 of 72; end` |

A mix ends `mixed N of N`: 94 with voiceports on, 72 with it off.
