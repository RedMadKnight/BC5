# tbd0405: InvitationDialog, WebBrowserDialog, SharePlay and GameLiveStreaming, ported before they are loaded (series e7)

Port agent `tbd`, 2026-11-04. Exp 0405 decision 4 ("=> B => B"): the tables that are compiled but never loaded by
`Libs::InitAll` are ported first, then loaded, each behind its own switch. These are four of batch 2's CPU-only library
tables. The loader agent `tl2` edits `libs.cpp` so a table loads when its switch is on. This agent edits only the four
units below, which it owns entirely, and no header. Remoteplay, the fifth table of this agent's brief, gets no switch and
no edit (see the end).

Files: `mktbd0405.py` (the edit, one script for all four units), `tbd0405.cpp` (the CPU test, all four tables), this note.

Inputs: the e7 input tree (e6's sources). None of the four is in `E5-FILES.txt` or among e6's units, so all four are the
base tree's files (KytyPlus f266548 + patch 0001). All are LF with a UTF-8 BOM. The script pins their md5s in one dict
(`PINNED`, at its top).

Two follow-ups from the top session (2026-11-04, after the first version) are in:
1. With a table's switch on, its held stubs are not registered, so their imports stay unresolved as today (exp 0327's
   `[bc5] stubbed import called` line keeps showing for them). With the switch off, every NID is registered as today.
2. Remoteplay has no load switch for now; `libRemotePlay.cpp` stays as its input.

## Switches and journal lines

Every switch defaults to off and is read once (a function-local static), by env_flag.hpp's rule: unset, empty or `0` is
off, any other value is on. No switch has items. The names are shared with `tl2`. The line goes to stderr when the
table's `LIB_DEFINE` runs (or at the first call), so it appears whenever `libs.cpp` loads the table.

| Switch | Table (`LIB_DEFINE`) | stderr line, on (off: `[bc5] exp 0405: <word> port off`) |
|---|---|---|
| `KYTY_BC5_LOAD_INVITATIONDIALOG` | `Libs::LibInvitationDialog::InitInvitationDialog_1` | `[bc5] exp 0405: invitationdialog port on (items: Initialize Terminate Open Close GetResult; OpenA GetResultA held, not registered)` |
| `KYTY_BC5_LOAD_WEBBROWSERDIALOG` | `Libs::LibWebBrowserDialog::InitWebBrowserDialog_1` | `... webbrowserdialog port on (items: Open OpenForPredeterminedContent Close UpdateStatus GetResult SetCookie ResetCookie; NOT_INITIALIZED held: split state; GetEvent Navigate SetZoom F2BE held, not registered)` |
| `KYTY_BC5_LOAD_SHAREPLAY` | `Libs::LibSharePlay::InitSharePlay_1` | `... shareplay port on (items: GetCurrentConnectionInfo GetCurrentConnectionInfoA; NOT_INITIALIZED held: split state; 20 held, not registered)` |
| `KYTY_BC5_LOAD_GAMELIVESTREAMING` | `Libs::LibGameLiveStreaming::InitGameLiveStreaming_1` | `... gamelivestreaming port on (items: GetCurrentStatus2 GetProgramInfo ScreenInitializeSeparateModeParameter and 10 argument checks; NOT_INITIALIZED held: split state; 7 match; 25 held, not registered)` |

Catcher lines (InvitationDialog only, switch on, each at most once):
`[bc5] exp 0405: invitationdialog <Open|Close|GetResult>: AnyPS5 has no answer for <case>; today's answer kept`.

Off is exactly today's path:
- Each edited function runs `PRINT_NAME()`, then `if (switch) return port(...)`, then today's code. Where AnyPS5 throws
  for some inputs, the form is `if (switch) { if (port(..., &answer)) return answer; }`.
- Stubs that are ported now declare real parameters, which the off path ignores.
- Each held stub's `LIB_FUNC` line is wrapped in `if (!switch) { ... }`: registered when off, as today, and left out
  when on. The `LIB_FUNC` text itself is unchanged.

## Size of each table

| Table | NIDs | ported | already match | held (not registered when on) | live NIDs, same library (libNet.cpp) |
|---|---|---|---|---|---|
| InvitationDialog | 9 | 5 | 2 | 2 | 0 |
| WebBrowserDialog | 12 | 7 | 1 | 4 | 2 (Initialize, Terminate) |
| SharePlay | 22 | 2 | 0 | 20 | 2 (Initialize, Terminate) |
| GameLiveStreaming | 45 | 13 | 7 | 25 | 2 (Initialize, Terminate) |
| **total** | 88 | 27 | 10 | 51 | 6 |

Every held NID is an AnyPS5 placeholder that throws (`NotImplemented_nid_no_patch`), or is absent from AnyPS5: 50 are
pending and 1 is absent (sceSharePlayNotifyOpenQuickMenu). No row is held for provenance.

The held logic inside ported functions is small:
- the NOT_INITIALIZED checks of the three split libraries, one line each;
- InvitationDialog's NOT_SYSTEM_INITIALIZED and BUSY, two lines.

By exp 0405's rule the held work is about 0 days: there is no upstream behaviour to port.

## InvitationDialog (9 NIDs): 5 PORTED, 2 already match, 2 HELD

Locations in the output `libInvitationDialog.cpp`:
- block `:71-243`;
- gates `:247` (Close), `:267` (GetResult), `:310` (Initialize), `:323` (Open), `:349` (Terminate);
- registration `:374-409`: the switch line `:375`, and the two held lines wrapped at `:384` and `:398`;
- includes `:38-42`.

**Source:** AnyPS5 4f41f4c37 (GPL-2.0-only), `core/libs/prx/libSceInvitationDialog/Export.cpp:15-114`; note
`docs/dev/debt/libSceInvitationDialog.md:6,13,17`. Note :6, quoted: GetResult answers "as shadPS4 reports when its window
is dismissed ... Not measured on a console". The param and result layouts are shadPS4's (GPL-2.0-or-later) 60c42b9,
`src/core/libraries/invitation_dialog/invitation_dialog.h:31-34,46-52,155-163`.

| Function | Ours (input) | Verdict | What changed |
|---|---|---|---|
| Initialize | `:116` status 1, OK | ported | ALREADY_INITIALIZED (0x80B80004) unless none; clears the callback argument |
| Terminate | `:146` status 0, OK | ported | NOT_INITIALIZED (0x80B80003) while none; clears the callback argument |
| Open | `:126` status 2 (running), OK | ported | ARG_NULL (0x80B8000D); finished at once (3), keeps the callback argument |
| Close | `:65` finished if not none, OK | ported | NOT_INITIALIZED while none; else today's (AnyPS5 throws) |
| GetResult | `:77` stub | ported | NOT_INITIALIZED, NOT_FINISHED (0x80B80005), ARG_NULL; then 0, callback argument, error 0, USER_CANCELED (1), recipient count 0 |
| GetStatus | `:107` returns the status | already match (`libInvitationDialog.cpp:107-110`) | not edited |
| UpdateStatus | `:156` running becomes finished, returns the status | already match (`:156-162`) for the states AnyPS5 reaches (0, 1, 3); running (2) is reached only by today's kept Open paths, which it still finishes | not edited |
| OpenA, GetResultA | `:136`, `:92` | held, not registered when on | AnyPS5 placeholders (note :11: layouts and behaviour unverified) |

- **Kept (AnyPS5 throws, so it has no answer; catcher line).** Today's answer runs in these cases:
  - Open from a status that is neither initialized nor finished (shadPS4 answers INVALID_STATE, the Signin family
    NOT_INITIALIZED: note :13);
  - Open with a size other than 144, or a mode other than 1/2;
  - Close of a dialog that is not none. That is every Close after Initialize (shadPS4 NOT_RUNNING, the Signin family 0);
  - GetResult with a non-zero reserved byte.
- **Held inside Initialize:**
  - NOT_SYSTEM_INITIALIZED: our `sceCommonDialogInitialize` (`libs/dialog.cpp:31-35`) keeps no state, and that file
    cannot be edited here;
  - BUSY: AnyPS5's note :17 says only this library takes the common dialog system, so it never answers BUSY.
- **Not ported:** AnyPS5's opt-in notice on Open (`ANYPS5_PSN_DIALOGS`, host UI). Exp 0405 R1 classed its rows
  d6f82110b and 1bbf054ce as internal / test.
- **Not used:** note :12 confirms the layout from the module's disassembly at named addresses; the layout is taken from
  shadPS4 instead. The reserved-byte check's only source is that disassembly, and AnyPS5 throws there anyway.
- **TODO(verify):** the status is a plain int, as in today's code. A title that drives this dialog from two threads.

**Tests:** on 23 cases, off 13 cases (counts include registration, split and held).

## WebBrowserDialog (12 NIDs): 7 PORTED, 1 already matches, 4 HELD

Locations in the output `libWebBrowserDialog.cpp`:
- block `:72-290`;
- gates `:294` (Close), `:326` (GetResult), `:366` (Open), `:379` (OpenForPredeterminedContent), `:394` (ResetCookie),
  `:412` (SetCookie), `:443` (UpdateStatus);
- registration `:473-521` (switch line `:474`; four held lines wrapped).

**Source:** AnyPS5 4f41f4c37, `core/libs/prx/libSceWebBrowserDialog/Export.cpp:34-154`; layouts
`core/libs/prx/libSceCommonDialog/CommonDialog.hpp:207-234` and `include/Api.hpp:6-16`; note
`docs/dev/debt/libSceWebBrowserDialog.md:6-7`.
- SetCookie / ResetCookie are a decision-1 item.
  - Note :7, quoted: "Both calls check their parameters in the same order and with the same codes as the PS5 13.60
    module".
  - Commit e70813c39 says "(PS5 12.00 module)"; d6f2d6501 relabels it 13.60 ("the decrypted modules").
  - It is a module reading with no addresses. It is accepted under decision 1, as the brief accepts GameLiveStreaming's
    13.42/13.60 readings.
- GetResult's buffer checks and the 2096-byte extended result, and the 424-byte allow list: AnyPS5 names no source. They
  come from fd6372e4f and f80c7e047, both "restore"/"validate" commits by boykopovar. Ported, with TODO(verify).

| Function | Ours (input) | Verdict | What changed (on) |
|---|---|---|---|
| Open | `:131` status 2 (running), OK | ported | ARG_NULL for null; finished at once (3), marked open |
| OpenForPredeterminedContent | `:141` status 2, OK | ported | allow list: ARG_NULL / PARAMETER (0x80B8000A) for size, no address, a 0 or 256+ character address, a reserved byte; then ARG_NULL for a null param; finished, marked open |
| Close | `:65` finished if not none, OK | ported | clears the mark; NOT_RUNNING (0x80B8000B) unless running |
| UpdateStatus | `:196` running becomes finished | ported | returns the status; a finished dialog loses the open mark |
| GetResult | `:92` stub | ported | ARG_NULL; PARAMETER (reserved 16-255; extended size 2096, reserved 2060-2063 and 2076-2095); NOT_FINISHED; then USER_CANCELED (1) at 0 |
| SetCookie | `:166` stub | ported | INVALID_STATE (0x80B80006) while marked open, ARG_NULL, PARAMETER (size 280, address 1-0x7FF, cookie 1-0xFFF, reserved); then 0 (no cookie store) |
| ResetCookie | `:151` stub | ported | ARG_NULL, INVALID_STATE, PARAMETER (size 264, reserved); then 0 |
| GetStatus | `:107` returns the status | already match (`libWebBrowserDialog.cpp:107-110`) | not edited |
| GetEvent, Navigate, SetZoom, Func_F2BE042771625F8C | `:77`, `:116`, `:181`, `:208` | held, not registered when on | AnyPS5 placeholders (note :10, :14) |

- **Not ported:** Open's BUSY for a running dialog. Nothing sets running while the switch is on. AnyPS5's value
  0x80B80007 is shadPS4's RESULT_NONE (`src/core/libraries/system/commondialog.h:34` @ 60c42b9); shadPS4's BUSY is
  0x80B80008. TODO(verify).
- **Also not ported:** the opt-in host notice (R1 rows a15c4bd90 and 3ee33308f: internal / test).
- Exp 0405 R1 row ae8929455 (`8r4EJ3FiX4w`) says "match", nothing to port. That NID is held here.

**Tests:** on 21 cases, off 14 cases.

## SharePlay (22 NIDs): 2 PORTED, 20 HELD

Locations in the output `libSharePlay.cpp`: block `:26-79`; gates `:88`, `:96`; registration `:199-263` (switch line
`:200`; 20 held lines wrapped).

**Source:** AnyPS5 4f41f4c37, `core/libs/prx/libSceSharePlay/Export.cpp:34-42,56-64`; layouts
`core/libs/SceTypes.hpp:1496-1515`; note `docs/dev/debt/libSceSharePlay.md:13-14`.
- Note :13, quoted: "the native module confirms a 72-byte result, initial zero fields and both user IDs -1" (decision 1).
- The 56-byte non-A layout is shadPS4's (note :14).
- Commit 0d2eeb87e: "KytyPS5 and fpPS4 agree on the layout and the error code".

What changed and what is held:
- **Ported:** GetCurrentConnectionInfo (input `:25`) and GetCurrentConnectionInfoA (`:30`), both stubs today. Now:
  - a null info gives INVALID_ARGS (0x810E0001);
  - otherwise every field is zero, both user ids are -1 (at 48/52, or at 64/68), and the call returns 0.
- **Held, not registered when on:** CrashDaemon, GetCurrentInfo, GetEvent, NotifyDialogOpen, NotifyForceCloseForCdlg,
  ResumeScreenForCdlg, ServerLock, ServerUnLock, SetMode, SetProhibition, SetProhibitionModeWithAppId,
  Start/StopStandby, Start/StopStreaming and the four `Func_*`. All are AnyPS5 placeholders (note :5-6, :19).
  NotifyOpenQuickMenu is held too; it is absent from AnyPS5.
- **Not this brief:** AnyPS5's `sceSharePlayProhibitController` (logic) and `zOdmo1vWHIc` (R1 3ade9e527). Neither is in
  our table.

**Tests:** on 5 cases, off 4 cases.

## GameLiveStreaming (45 NIDs): 13 PORTED, 7 already match, 25 HELD

Locations in the output `libGameLiveStreaming.cpp`: block `:64-198`; 13 gates (`:279` to `:811`, one per ported
function); registration `:917-1106` (switch line `:918`; 25 held lines wrapped).

**Source:** AnyPS5 4f41f4c37, `core/libs/prx/libSceGameLiveStreaming/Export.cpp:14-38,59-85,135-222,234-239`; layouts
`include/Api.hpp:9-61`; note `docs/dev/debt/libSceGameLiveStreaming.md`. Each row is a decision-1 item (accepted):
- :7 GetCurrentStatus2: "the supplied module confirms the 72-byte layout and inactive status (user -1, remaining bytes
  zero)". The layout is shadPS4's (`gamelivestreaming.h:22-31` @ 60c42b9).
- :8 GetProgramInfo: "the PS5 13.60 module clears the 0x134C-byte program info ... and returns 0x80A00002 for a null
  pointer". The two disassembled titles in that note only describe how titles use the answer; nothing is taken from
  them.
- :17 ScreenInitializeSeparateModeParameter: "read from its disassembly and run natively on x86-64 (not a console)".
- :12 the setting, feedback and message calls: "a report on #9524 that ran each function of the firmware 13.42 module
  with the service call stubbed".

| Ported (input line) | On |
|---|---|
| GetCurrentStatus2 `:223` | null 0x80A00002; 72 bytes zero, user id -1 |
| GetProgramInfo `:238` | null 0x80A00002; 0x134C bytes zero |
| ScreenInitializeSeparateModeParameter `:418` | null 0x80A00002; 68 bytes zero (no Initialize needed) |
| GetSocialFeedbackMessagesCount `:268`, GetSocialFeedbackMessages `:253` | null or type outside 1-3: 0x80A00002; else count / acquired 0 |
| SetMetadata `:568`, SetPresetSocialFeedbackCommandsDescription `:598`, SetInvitationSessionId `:523`, PostSocialMessage `:343` | null or longer than 240 / 720 / 45 / 360 characters: 0x80A00002 |
| SetSpoilerTag `:628`, SetPresetSocialFeedbackCommands `:583` | null, more than 16 / 5, or a non-zero tail byte (224-byte tags from 193, 228-byte commands from 197): 0x80A00002 |
| ClearSocialFeedbackMessages `:133` | type outside 1-3: 0x80A00002 |
| SetCameraFrameSetting `:478` | null or a non-zero byte at 9-39: 0x80A00002 (TODO(verify): the setting's size, note :12) |

- **Already match** for an initialized library (they return 0 and store nothing, as our stubs do; not edited, always
  registered):
  - PermitLiveStreaming `:313`, SetMaxBitrate `:553`, EnableSocialFeedback `:178`, PermitServerSideRecording `:328`,
    ClearSpoilerTag `:148`, ClearPresetSocialFeedbackCommands `:118`, EnableLiveStreaming `:163`.
  - EnableLiveStreaming is the brief's "still throws upstream" row: AnyPS5 throws before Initialize (note :5), and that
    path is held.
  - Its signature follows Orbital's IDA `db_types.json` and fpPS4 (note :5). Decision 3 ports such a row from behaviour
    only. The behaviour is "return 0", which our stub already gives, so there is no code and no IDA trace.
- **Held, not registered when on** (AnyPS5 placeholders, note :16-41):
  - StartDebugBroadcast, StopDebugBroadcast, ApplySocialFeedbackMessageFilter, CheckCallback;
  - GetCurrentBroadcastScreenLayout, LaunchLiveViewer, LaunchLiveViewerA, RegisterCallback, UnregisterCallback;
  - GetCurrentStatus (note :23: it "still throws"; the note reads it from the module at an address);
  - Screen{Initialize,Terminate,CloseSeparateMode,ConfigureSeparateMode,OpenSeparateMode,SetMode};
  - Set{Default,}ServiceProviderPermission, SetGuardAreas, SetLinkCommentPreset, SetStandbyScreenResource;
  - Start/StopGenerateStandbyScreenResource, Start/StopSocialFeedbackMessageFiltering.

**Tests:** on 17 cases, off 5 cases.

## Split state (tld0405-notes.md risk 2)

The live functions of the same libraries are in `libNet.cpp` (e7 input md5 `35773d6e769b85be74012a86c0f02e89`):

| Library | Live NIDs | libNet.cpp | What they keep |
|---|---|---|---|
| WebBrowserDialog | jqb7HntFQFc Initialize, ocHtyBwHfys Terminate | `:4240-4261` | nothing: return 0 |
| SharePlay | isruqthpYcw Initialize, UaLjloJinow Terminate | `:4288-4313` | nothing: log the heap, return 0 |
| GameLiveStreaming | kvYEw2lBndk Initialize, 9yK6Fk8mKOQ Terminate | `:4263-4286` | nothing: log the heap size, return 0 |

- AnyPS5's ports read an initialized flag that its own Initialize/Terminate set. Here those two are live, keep no
  state, and are in a file this agent may not edit. So no ported function can tell "before Initialize" from "after".
- **Decision per function:** the NOT_INITIALIZED answer is held everywhere (WebBrowserDialog 0x80B80003, SharePlay
  0x810E0004, GameLiveStreaming 0x80A00004). Every other answer is given as for an initialized library, which is what a
  title that calls Initialize first gets from AnyPS5.
  - WebBrowserDialog reads status 0 as initialized: Close gives NOT_RUNNING, GetResult NOT_FINISHED, and the cookie
    calls check their arguments.
  - WebBrowserDialog's GetStatus/UpdateStatus give 0 there, where AnyPS5 gives 1 (held).
  - After the live Terminate, WebBrowserDialog's status here keeps its value (AnyPS5: 0). The open mark stays until
    UpdateStatus or Close clears it.
  - SharePlay and GameLiveStreaming: the ported functions keep no state, so nothing else depends on the live side.
- InvitationDialog has no live functions. Its only outside state is the common dialog system (`libs/dialog.cpp:31`),
  which keeps none; see InvitationDialog.
- **No NID of these tables is registered by a live table, before or after the edit.**
  - The script changes no `LIB_FUNC` text: all 88 lines are the same; the 51 held ones are only wrapped.
  - A scan of every quoted NID in every `.cpp`, `.h` and `.inc` of the input tree, outside these files, finds none of
    the 88 (scratch `e7\tbd\overlap.py`).
  - The scratch `e6\tld\tables.json` agrees: `same_key` 0 and `nid_any` 0 for all four tables.
  - With the switch on, a held NID is therefore unresolved: `Find` and the NID-only fallback `FindByNid` find nothing,
    and the runtime linker's thunk answers as today.
  - The test checks all of this at run time.

## Remoteplay: no switch, no edit (the top session's follow-up 2)

`libRemotePlay.cpp` stays as its input (abfde0e8bb446bc6870aa5df08cfb5fa). `tl2` drops its loader row. The finding,
for when it is reconsidered:
- AnyPS5 4f41f4c37 implements none of its 39 NIDs. 38 throw (`NotImplemented_nid_no_patch`; note
  `docs/dev/debt/libSceRemoteplay.md`: "declared without parameters, signature unknown"). sceRemoteplayChangeEnterKey is
  not in AnyPS5.
- The only logic AnyPS5 has (Initialize, Terminate, GetConnectionStatus) is the live table's in our tree
  (`libNet.cpp:4198-4238`).
- Loading the table would change nothing for a title. Today these imports are unresolved. The runtime linker binds each
  to a thunk that tries a late resolve by NID and otherwise returns 0 and writes nothing (`loader/runtimeLinker.cpp:320-382`).
  Our stubs answer the same.
- Loading it would only hide exp 0327's `[bc5] stubbed import #...` and `[bc5] stubbed import called: <NID>` lines for
  those 39 NIDs. Those lines tell us which unimplemented calls a title uses.
- The same reasoning is why held stubs are no longer registered when a table is on (follow-up 1).

## Exp 0405 R1 rows (`raw\r1-verdicts\D2.tsv`) for these libraries

| Row | Class | Here |
|---|---|---|
| ae8929455 WebBrowserDialog, 70d9e562a Remoteplay | shared, match | `8r4EJ3FiX4w` held (not registered when on); `HV7jZe1frbM` untouched |
| a15c4bd90, d6f82110b, 3ee33308f, 1bbf054ce | internal / test | the opt-in host notice: not ported |
| 3ade9e527 SharePlay, 86fd8f677 Remoteplay, 77914b91e | new-export / internal | placeholders for NIDs we do not register: not this brief |

## Verified on the laptop

- `mktbd0405.py <e7 input tree> <out>` prints the four output md5s below. Run twice, it gives the same bytes. It writes
  nothing when it refuses, in two cases:
  - its own output ("the unit has the edit already");
  - an input with one byte added ("not the pinned input").
- Built-in checks:
  - every anchor occurs once, in the input and in the output; the block's own anchors lie before and after it;
  - each edit keeps the brace/parenthesis/bracket balance, and each held wrap keeps its `LIB_FUNC` text;
  - the helper-use counts are right;
  - undoing the edits gives the input back byte for byte;
  - the inserted text is ASCII; the files stay LF and keep their BOM.
- Besides the blocks, the only changes are:
  - the include lines;
  - the edited signature lines (2 + 5 + 2 + 13);
  - the gate lines after each edited `PRINT_NAME();`;
  - one line after each `LIB_DEFINE`;
  - the 2 + 4 + 20 + 25 held `LIB_FUNC` lines, each wrapped.
- **Syntax:** clean for the four inputs, the four outputs and `tbd0405.cpp`, with no extra flag. Script: scratch
  `e7\tbd\chk.sh`. Setup:
  - Visual Studio's clang++ 22 (MSVC target), `-fsyntax-only -std=c++20 -Wall -Wextra -Werror`;
  - the stand-in `cmake_config.h` and POSIX stubs (`scratchpad\lib0405chk\stub`);
  - fmt from Inori_GPCS4, magic_enum from InoriRus_Kyty.
- **Stand-in run** (scratch `e7\tbd\run`, `build.sh`, `standin.cpp`):
  - What it links: the real test, the four real output units and the real `loader/symbolDatabase.cpp`, built with
    `-Wall -Wextra -Werror`.
  - `standin.cpp` supplies the log/timer/thread symbols that `PRINT_NAME` references (never reached). It also has copies
    of `libNet.cpp`'s live tables with the real keys and NIDs: functions that return 0 and keep no state, as the real
    ones do.
  - All four `=1`, argument `on`: **66 of 66**, exit 0. The four `on` lines and four catcher lines appear on stderr. The
    held NIDs are absent (2/4/20/25), and each table registers the rest (7/8/2/20).
  - All `=0`, argument `off`: **36 of 36**, with all 9/12/22/45 NIDs registered. All unset: **36 of 36**, off.
  - Mixed:
    - `INVITATIONDIALOG=` (empty), `WEBBROWSERDIALOG=yes`, `SHAREPLAY` unset, `GAMELIVESTREAMING=1`: **mixed 55 of 55**;
    - `1/0/1/0`, argument `mixed`: **47 of 47**.
  - A wrong argument (`off` with `SHAREPLAY=1`) exits 2.
  - Each run was in a fresh directory and left nothing but its own output files.
- **Negative control:** the same test linked with the four unedited input units (today's code).
  - Switches on: 19 of 66 passed, 47 FAILs, exit 1. Among the failures: the held NIDs, which today's tables register.
  - Switches off: **36 of 36**, exit 0. Every off expectation is therefore today's answer, checked against today's code
    itself.
- **Not checked:**
  - the box's Linux compile (gcc or clang) and link with every emulator object;
  - the real `libNet.cpp` under the test (the stand-in copies its tables);
  - `tl2`'s loading.

  The box build is the first real run.

## Risks

- A title that relied on today's OK now gets AnyPS5's errors:
  - InvitationDialog: Close, Terminate and GetResult before Initialize; a second Initialize;
  - WebBrowserDialog: Close (always NOT_RUNNING while on, because Open finishes at once); GetResult before an Open; the
    cookie calls while a dialog is marked open;
  - GameLiveStreaming: argument errors.
- Status 3 right after Open (InvitationDialog, WebBrowserDialog), where today's code gives 2 until the first update. A
  title that waits for "running" before polling would see "finished" at once, as with AnyPS5.
- The split state above: before the live Initialize, or after the live Terminate, these libraries answer as if
  initialized.
- GetProgramInfo clears 0x134C bytes of the caller's buffer, as the module reading says. A title that passes a smaller
  buffer would have it overrun (note :8: "The buffer size is not shown"). TODO(verify).
- AnyPS5 names no source for WebBrowserDialog's GetResult and allow-list layouts. TODO(verify).
- With a switch on, the held NIDs go through the unresolved-import thunk, as today. If a later edit registers any of
  them elsewhere, `FindByNid` would find that one instead. Today none is registered anywhere.
- tl2: four switch names (no `KYTY_BC5_LOAD_REMOTEPLAY`). No NID is shared with a live table.

## Files

| File | md5 |
|---|---|
| `mktbd0405.py` | `d9abbabd1895383c7d4d62b218fa3c2b` |
| `tbd0405.cpp` | `433cf8731f0d6fa93ebb1581b7e0aa2c` |
| input `src/libs/libInvitationDialog.cpp` (base tree) | `204a5daeebb100a131c034edb8e58e87` |
| output `src/libs/libInvitationDialog.cpp` | `35e232795b2e575fdfe452583b95657e` |
| input `src/libs/libWebBrowserDialog.cpp` (base tree) | `af36a12a0bc234f83e5c85a76d4b283d` |
| output `src/libs/libWebBrowserDialog.cpp` | `e12c7de053bc57dbdfcb869e53cce49a` |
| input `src/libs/libSharePlay.cpp` (base tree) | `d6ecb7874b00ee29d9275d78d8087191` |
| output `src/libs/libSharePlay.cpp` | `6fc65c51edeae57fccabb96ec3084451` |
| input `src/libs/libGameLiveStreaming.cpp` (base tree) | `59e46b5d8452101a0f57257703cfa3a4` |
| output `src/libs/libGameLiveStreaming.cpp` | `4c1af2f3ba313347d93d4c1549a5137e` |
| `src/libs/libRemotePlay.cpp` (not edited) | `abfde0e8bb446bc6870aa5df08cfb5fa` |

## Case counts

- All four switches on: 66 cases (invitationdialog 23, webbrowserdialog 21, shareplay 5, gamelivestreaming 17), ending
  `tbd0405: on 66 of 66; end`.
- All off or unset: 36 cases (13, 14, 4, 5), ending `tbd0405: off 36 of 36; end`.
- Switches not alike: each table follows its own switch, ending `tbd0405: mixed N of N; end`.

Box row for `box0401.sh` (as tbc/tbn): `tbd0405.cpp src/libs/libGameLiveStreaming.cpp
KYTY_BC5_LOAD_INVITATIONDIALOG,KYTY_BC5_LOAD_WEBBROWSERDIALOG,KYTY_BC5_LOAD_SHAREPLAY,KYTY_BC5_LOAD_GAMELIVESTREAMING tbd0405`.
