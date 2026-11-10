# tbn0405: the NpCommon, NpManager and NpTrophy tables of libNp.cpp, ported before they are loaded (series e6)

Port agent `tbn`, 2026-11-04. Exp 0405 decision 4 ("=> B => B"): the 32 tables that are compiled but never loaded by
`Libs::InitAll` are ported first, then loaded, each behind its own switch. These are batch 1's three CPU-only Np tables.
Agent `tld` edits `libs.cpp` so a table loads, before the live tables, when its switch is on; this agent edits only
`src/libs/libNp.cpp`, and in it only the namespaces `NpCommon`, `NpManager`, `NpTrophy` (plus the includes they need).

Files: `mktbn0405.py` (the edit), `tbn0405.cpp` (the CPU test), this note.

Input: `src/libs/libNp.cpp` of the e6 input tree. It is not in `E5-FILES.txt`, so it is the base tree's file (KytyPlus
f266548 + patch 0001), md5 `a2c5facee2708bed1556383b0f5bbdca`, 54,344 bytes, LF. The script pins that md5.

Output md5: `24e778261495abcd5a069396f14b28b4`.

## Switches and journal lines

Every switch defaults to off and is read once (a function-local static). Unset, empty or `0` is off; any other value is on.
Each switch is on/off only and has no item list. The names are shared with `tld`. The line goes to stderr when the
table's `LIB_DEFINE` runs, so it appears whenever `libs.cpp` loads the table.

| Switch | Table (`LIB_DEFINE`) | stderr line (on / off) |
|---|---|---|
| `KYTY_BC5_LOAD_NPCOMMON` | `Libs::NpCommon::InitNpCommon_1` | `[bc5] exp 0405: npcommon port on (items: ids mutex cond thread clock sdkversion callout)` / `... npcommon port off` |
| `KYTY_BC5_LOAD_NPMANAGER` | `Libs::NpManager::InitNpManager_1` | `[bc5] exp 0405: npmanager port on (items: account presence plus request timeout wait callback)` / `... off` |
| `KYTY_BC5_LOAD_NPTROPHY` | `Libs::NpTrophy::InitNpTrophy_1` | `[bc5] exp 0405: nptrophy port on (items: context handle register unlock info icon setinfo dbg)` / `... off` |

There are two catchers, printed only when on:
- `[bc5] exp 0405: npcommon sceNpCalloutTermCtx from the context's own callout: refused, context kept`
- `[bc5] exp 0405: nptrophy <call>: AnyPS5 has no answer ...; today's 0 kept, nothing written`, at most once for each of the
  two calls.

Off is exactly today's path. Each edited stub runs `PRINT_NAME()`, then `if (switch) return port(...)`, then today's
`return`. The stubs now declare real parameters, which the off path ignores. `InitNpManager_1` registers the two shared
NIDs only when off (see NpManager).

## Size of each table

| Table | NIDs | ported | already match | held | live elsewhere (not registered when on) | AnyPS5 implemented, NIDs we register nowhere |
|---|---|---|---|---|---|---|
| NpCommon | 28 | 28 | 0 | 0 | 0 | 261 of 401 unregistered (49 const, 212 logic, ~1169 body lines) |
| NpManager | 27 | 20 | 1 | 4 | 2 | 27 of 499 unregistered (10 const, 17 logic, ~108 lines) |
| NpTrophy | 87 | 23 | 0 | 64 | 0 | 0 of 24 unregistered |

The overlap scan (`scratchpad/e6/tbn/overlap.py`) covers every quoted NID in every `.cpp`, `.h` and `.inc` of the input
tree. Only NpManager's `mjjTXh+NHWY` and `cRILAEvn+9M` are also registered elsewhere: by `libNet.cpp:1587,1589`, in the
live `InitNet_1_NpManager` under the same library key (`libSceNpManager` → `NpManager`).

The last column comes from exp 0405's `r1-anyps5-missing.tsv` (AnyPS5 4f41f4c37). It is later work, not part of this
brief.

## NpCommon (28 NIDs): all 28 PORTED

The block is at output `libNp.cpp:89-487`. The 28 stubs follow it, and the registration line is `:715`. The includes are
at `:15-34`.

**From AnyPS5 4f41f4c37 (GPL-2.0-only), `core/libs/prx/libSceNpCommon/Export.cpp`:**
- `:40-81`: `sceNpCmpOnlineId` (0 / 0x80550609 / 0x80550003), `sceNpCmpNpIdInOrder` (order -1/0/1 by online id, then
  opt, then reserved), `sceNpGetPlatformType` (the tag at `opt[4..7]`: ps3 1, psp2 2, ps4 3, none 0, else 0x80550004),
  and `sceNpIntIsValidOnlineId` (3-16 characters, the first alphanumeric, the rest alphanumeric, `_` or `-`).
- `:83-157`: the wrappers `sceNpMutex*`, `sceNpLwMutex*`, `sceNpCond*` and `sceNpJoinThread`, calling
  `LibKernel::Pthread*`.
  - Flag bit 0 makes the mutex recursive (type 2).
  - EBUSY from a try-lock becomes 0x8055800F; ETIMEDOUT from a timed wait becomes 0x8055800B.
  - A timed wait of 0 waits without a limit.
- `:159-165`: `sceNpGetSystemClockUsec`, monotonic clock 4. A null output gives 0x80550003 (commit 0a520ced9, exp 0405
  row "shared missing"; ours was `libNp.cpp:170`, which wrote nothing).
- Provenance: debt `libSceNpCommon.md:36-38` names shadPS4 a808e76 and says none of these is measured on a console.

**`sceNpGetSdkVersion` (AnyPS5 `:167-175`, commit 30933ef0c), a decision-1 item:**
- It clears 8 bytes, then writes the system software version as `major.minor`.
- Upstream note (debt `:39`), quoted: "as firmware 13.42's `libSceNpCommon.sprx` does ([read from its disassembly and an
  emulator run](https://github.com/boykopovar/AnyPS5/pull/13684#issuecomment-6537744884), not measured on a console)".
  That is a firmware run, accepted by decision 1.
- The version is our kernel's own answer, 0x0A600000 (`libs/bc5LleAgc.cpp` GetProsperoSystemSwVersion), so the output is
  `"10.60"`. AnyPS5's kernel answers 1.00.
- A null buffer is left alone; the firmware writes without a check. This is host safety.

**From shadPS4 60c42b9 (GPL-2.0-or-later), `src/core/libraries/np/np_common.cpp`** (seven functions):
- `:95-117`: `sceNpCmpNpId` (online id, opt, reserved; 0x80550609).
- `:276-318`: `sceNpCreateThread`.
- `:405-555` and `:46-93`: `sceNpCalloutInitCtx/TermCtx/StartOnCtx/StartOnCtx64/StopOnCtx` and the worker.
- The context layout (0x28 bytes) and the entry layout (0x20 bytes) are from `:23-30` and `np_common.h:25-39`.
- The callout error codes are from `np_error.h:683-687`.
- Why not AnyPS5: its code for these seven (Runtime.cpp, commit 736ee67ca) says "The behaviour follows
  libSceNpCommon.sprx from firmware 12.00, read from disassembly". That is a disassembly source, so it is not used.

**Taken from AnyPS5 as host-side choices:**
- 702d85e0b: the queue is searched before an entry is written, so restarting a queued callout returns 0x80558006 and
  leaves the queue alone. shadPS4 writes the entry first.
- 22d478c78 (exp 0405 class "internal"): `TermCtx` from the context's own callout is refused with the catcher line;
  AnyPS5 throws.
- `sceNpCreateThread` applies an explicit FIFO priority whenever a priority is given, as AnyPS5's debt `:50` does. shadPS4
  does this only when the compiled SDK version is at least 0x2500000. TODO(verify) for titles built with an older SDK.
- A null callout context gives 0x80550003 (host safety; unsourced).

**Test cases:**
- On: 57 cases. Compares; platform tags; online-id rules; the clock (null, and moving forward); the SDK string; a mutex
  (held try-lock gives BUSY); a recursive lightweight mutex; a 20 ms timed wait giving TIMEDOUT; a guest thread
  (create/join, value 42); callouts (before init, init twice, a 10 ms callout runs once, a 10 s one is stopped, duplicate,
  stop twice, term, after term, null context).
- Off: 12 cases, each giving 0 with nothing written.

**Risks:**
- A title that relied on `CmpNpId` or `CmpOnlineId` always answering "equal" (0) now sees NOT_MATCH.
- The callout worker is a real guest thread now, where before the stub did nothing.
- The SDK string comes from our kernel (TODO(verify): what a title expects).

## NpManager (27 NIDs): 20 PORTED, 1 already matches, 4 HELD, 2 left to the live table

The block is at output `libNp.cpp:751-901`. The registration line is `:1100`, and the shared NIDs are at `:1124-1127`.

**Ported, from AnyPS5 4f41f4c37 `core/libs/prx/libSceNpManager/Export.cpp`:**
- `:302-327`: `CheckNpAvailabilityA`, `GetAccountDateOfBirthA`, `GetAccountLanguageA`, `GetGamePresenceStatus/A` (status 0,
  offline), `GetParentalControlInfoA`.
- `:412-416`: `IsPlusMember` (false).
- `:809-864`:
  - the PS4 forms `GetAccountCountry`, `GetAccountDateOfBirth`, `GetAccountLanguage` and `GetParentalControlInfo` (null
    gives 0x80550003, else USER_NOT_FOUND 0x80550007);
  - `GetUserIdByOnlineId`, `CheckPlus` and `GetAccountId` (SIGNED_OUT 0x80550006);
  - `SetGamePresenceOnline`, and `SetGamePresenceOnlineA` (commit 72ccb10bd, exp 0405 R1 #16 "shared missing").
- `:921-927`: `WaitAsync`. `:993-1007`: `SetTimeout` (minimums of 1 s and 10 s). `:1060-1063`: `GetUserIdByAccountId`.
  `:1085-1087`: `CheckCallbackForLib`.
- Provenance: debt `libSceNpManager.md:167,174-175,183-189,195,197` names shadPS4 for the signatures and checks, and
  nothing is measured on a console. Debt `:174` also cites orbital's IDA `db_types.json` for `SetTimeout`'s signature,
  next to shadPS4 and SharpProspero. The six-argument form is shadPS4's, and no IDA type name is used.

**Adapted to our request model** (`libs/network.cpp`, the live table):
- A request id is one of network.cpp's requests.
- The A forms complete the request signed out through `NpCheckNpReachability`. A synchronous request gives 0x80550006; an
  asynchronous one gives 0, and its poll then gives 0x80550006.
- Whether a request is live (for `SetTimeout`, `WaitAsync` and `SetGamePresenceOnline`) is asked of `NpPollAsync`, which
  changes nothing.
- Differences from AnyPS5: a request id < 0 gives 0x80550003, where AnyPS5 gives 0x80550014; and the request is completed
  instead of being left live.
- The signed-out code is 0x80550006, as network.cpp and AnyPS5 use. The file's `NP_NOT_SIGNED_IN` (0x80550005) stays on
  the off path; its TODO(verify) at `:22` still stands.

**Already matches:** `sceNpUnregisterPlusEventCallback`, input `:337`, returns 0, as AnyPS5 `:1056` does. It is not edited.

**HELD** (input `:322, :327, :372, :377`): `RegisterGamePresenceCallbackA`, `UnregisterGamePresenceCallbackA`,
`RegisterStateCallbackForToolkit`, `UnregisterStateCallbackForToolkit`. In AnyPS5 these are throwing placeholders
(`PendingExports.cpp:733, 753, 757`, `AdditionalExports.cpp:804`), so there is no behaviour to port. Today's 0 is kept.

**Shared NIDs, live only** (coordinator, from tld0405-notes risk 1):
- The NIDs are `mjjTXh+NHWY` (sceNpUnregisterStateCallback, input `:362`) and `cRILAEvn+9M`
  (sceNpUnregisterNpReachabilityStateCallback, `:367`).
- With the switch on, `InitNpManager_1` does not register them. Both the exact key (`Find`) and the NID-only fallback
  (`FindByNid`) then reach the live `libNet.cpp` functions.
- With the switch off, they are registered as today; the table is not loaded when off.

**Split state** (tld risk 2): `sceNpUnregisterPlusEventCallback` (xViqJdDgKl0) stays in this table and answers exactly as
AnyPS5 does: 0, with no registration made through it. Its live partner `sceNpRegisterPlusEventCallback` (GImICnh+boA,
`network.cpp:4456`) keeps no callback either, so the pair shares no state. This table has no other register/unregister
pair split from a live one. The GamePresenceA and Toolkit pairs are both here and held; the live
`sceNpRegisterGamePresenceCallback` (uFJpaKNBAj4) is the non-A form.

**Test cases:**
- On: 51 cases, covering every ported call (invalid user, null, unknown request, live request, outputs untouched or
  written), the 3 held or unchanged calls, the shared NIDs left out, and a second database loaded as `libs.cpp` does
  (switched table, then `InitNet_1_NpManager`). In that database both shared NIDs resolve to the live function by
  `FindByNid` and by `Find`, and `GImICnh+boA` stays live.
- Off: 15 cases (today's 0 or 0x80550005, outputs untouched, both shared NIDs registered by the dead table as today).

**Risks:**
- A title that read today's OK as "available" now sees "signed out" or "user not found", which is the AnyPS5 answer.
- tld's test expected npmanager "2 moved" (`tld0405-notes.md:112`). With this edit, those 2 are not registered by
  `InitNpManager_1` when on, so that count changes to 0 moved, 25 new. tld's numbers need updating.

## NpTrophy (87 NIDs): 23 PORTED, 64 HELD

The block is at output `libNp.cpp:1350-1832`. The registration line is `:2340`.

**Ported, from AnyPS5 4f41f4c37 `core/libs/prx/libSceNpTrophy/Export.cpp`:**
- `:59-182` and `:190-381`: contexts (one per user and service label), handles, abort, `RegisterContext`,
  `GetTrophyUnlockState`, `UnlockTrophy`, the three icons, and the three info calls.
  - The TRP reader is at `:85-111`: the magic 0xdca24d00, the entry count at 0x10, 0x40-byte entries holding a name,
    offset and size; entries past the file are refused.
  - The trophy count is the number of consecutive `TROPnnn.PNG` entries in `/app0/sce_sys/trophy/trophyNN.trp`, found
    through our mount table (`FileSystem::GetRealFilename`).
  - Structure sizes and fields: AnyPS5 `include/Api.hpp:5-74`; shadPS4 60c42b9 `np_trophy.h:36-121`.
- Provenance: debt `libSceNpTrophy.md:9`, "None of it is checked on a console". Debt `:10`, AbortHandle "measured on a
  PS4 Pro (firmware 10.71)": an aborted handle gives 0x80551607 before the other checks. Debt `:32-34` covers the details.
- **Changed from AnyPS5:**
  - Unlocks are kept in memory only, for the run. AnyPS5 writes `_trophy/trophyNN.<user>` in its working directory. Our
    tree has no trophy store, and the title's save data is never touched.
  - AnyPS5 throws for `GetGroupInfo` of an existing group and for `GetTrophyInfo` in a package with groups. Here those
    keep today's 0, write nothing, and print the catcher line.
- `:494-511`: `NumInfoGetTotal`, `GroupArrayGetNum`, `SetInfoGetTrophyNum` and `SetInfoGetTrophyFlagArray` (which
  returns the set-bit count), from commits 34b21b0b3 and 85ff6817f. These are decision-1 items.
  - Upstream note (debt `:28`), quoted: "read only their arguments in firmware 13.42 ([disassembly, the first four also
    run natively]...)". Those runs are accepted by decision 1.
  - A null argument gives 0 here (host safety); the module faults.
- `:573, 602, 606, 730, 734`: `SystemDbgCtl`, `SystemGetDbgParam`, `SystemGetDbgParamInt`, `SystemSetDbgParam`,
  `SystemSetDbgParamInt` give 0x80551692 and do nothing else. This is a decision-1 item.
  - Upstream note (debt `:5`), quoted: "which is all firmware 13.42's module does ... ([run in an
    emulator](https://github.com/boykopovar/AnyPS5/pull/9874#issuecomment-6401358829))".

**HELD:**
- `ConfigHasGroupFeature` (input `:681`): its only source is the disassembly (the fifth function of debt `:28`, with no
  run). This is the brief's provenance rule. Today's 0 is kept.
- 62 stubs whose AnyPS5 export is a throwing placeholder with no prototype (debt `:13-19`, `:34-38`):
  - CaptureScreenshot; ConfigGet* ×8; Int* ×11; ShowTrophyList;
  - System* ×37: AbortHandle, Build*IconUri ×4, CheckNetSyncTitles, CheckRecoveryRequired, CloseStorage,
    Create/DestroyContext/Handle, DebugLock/UnlockTrophy, DestroyTrophyConfig, Get* ×17, IsServerAvailable,
    NetSyncTitle(s), OpenStorage, PerformRecovery, Remove* ×3;
  - the four `Func_*` (registration lines `:1069-1154`).
- `SystemGetTrophyTitleIds` (`:1137`): absent from AnyPS5.
- Today's answers are kept for all 64.

**Test cases:**
- On: 57 cases.
  - The test builds three packages under `./tbn0405-app0` mounted at `/app0`: trophy00 (3 trophies), trophy01 (not a
    package), trophy03 (a group). There is no trophy02.
  - It covers create, duplicate and null; register with options, bad context and bad handle, then OK and again; unlock
    state before and after; unlock (null, OK, again, past the end).
  - Icons: size, small buffer, bytes, locked, bad id, group -1, missing group icon.
  - Game, group and trophy info with values (3 trophies, 1 unlocked, 33 %) and size checks; INVALID_TRP,
    CONF_NOT_INSTALLED, and the two no-answer paths.
  - Abort semantics; destroy twice; the four helpers; the five dbg calls; and 2 held calls unchanged.
- Off: 7 cases (today's 0 or 0x80550005, nothing written).

**Risks:**
- `RegisterContext` used to give 0x80550005; it now gives 0, or 0x80551626 when the title has no PS4 trophy package. A
  PS5 title's trophies live elsewhere, and how a title reacts to these answers is unknown.
- Unlocks do not survive a restart, so a title could unlock again in a new run (AnyPS5 persists them).

## Exp 0405 R1 rows (`raw\r1-verdicts\D1.tsv`) for these libraries

| Row | Class | Note (quoted) | Here |
|---|---|---|---|
| 0a520ced9 NpCommon | shared missing | "Ours writes no time ... Null check itself is a host-safety choice." | ported |
| 30933ef0c NpCommon | excluded-provenance | "Read from 13.42 disassembly (#13684). Ours: stub returning OK ..." | ported (decision 1: debt :39 names an emulator run) |
| 79624b828, c9e6fe5d1, 38bd414be, 89d38cf33, 949680de9, 5ea3d73de, 4dc74fc96 NpCommon | excluded-provenance | "Runtime.cpp follows 13.60 libSceNpCommon.sprx disassembly (debt :39)." / "See 79624b828." | held: NpCommId/TitleId, RefObject, MemoryStream, TitleSecret, Time, allocator: not in our table, none ported |
| e8a765b48 NpCommon | excluded-provenance | "13.60 disassembly (debt :46)." | held (StreamReader/Writer, not in our table) |
| 2087b15d4 NpCommon | excluded-provenance | "sceNpJsonParse* follow 13.42 disassembly plus CPU-emulator runs (debt :62)." | not in our table. A decision-1 candidate (emulator runs) for the later work on unregistered exports |
| 9b48ab521, 4b94c6905 NpCommon | excluded-provenance | "Strings.cpp follows 13.60 disassembly (debt :39)." / "See 9b48ab521." | held (ParseJid, XmlEscape; not in our table) |
| 22d478c78 NpCommon | internal | "AnyPS5 callout worker safety; ours has no callout worker" | taken (a host choice; ours has a worker now) |
| 72ccb10bd NpManager | shared missing | "C0gNCiRIi4U absent from the loaded NpManager table ... shadPS4-sourced." | ported |
| 85ff6817f, 34b21b0b3 NpTrophy | excluded-provenance | "13.42 disassembly (debt :22). Ours: OK stub ..." / "See 85ff6817f." | the four helpers ported (decision 1: run natively); ConfigHasGroupFeature held |

The other D1 rows for these libraries are new-export, internal or test/doc rows, and no code here depends on them.
Of the 12 NpCommon excluded-provenance rows, one is ported (30933ef0c). The other 11 concern code outside our table's 28
NIDs.

## Verified on the laptop

- `mktbn0405.py <e6 input tree> <out>` prints `src/libs/libNp.cpp 24e778261495abcd5a069396f14b28b4`.
- It refuses its own output ("the unit has the edit already").
- Built-in checks: every anchor occurs once and lies inside its own namespace; each edit keeps the balance; the switch-use
  counts are right; the five other tables are byte-identical; undoing the edits gives the input back byte for byte; the
  inserted text is ASCII; the file stays LF.
- **Syntax:** Visual Studio's clang++ (clang 22, MSVC target) with `-fsyntax-only -std=c++20 -Wall -Wextra -Werror`, the
  stand-in `cmake_config.h` and POSIX headers of `scratchpad/lib0405chk/stub`, and fmt from Inori_GPCS4. The input is
  clean. The output and `tbn0405.cpp` are clean once a stand-in `struct sched_param` is added (`-include
  scratchpad/e6/tbn/sched_standin.h`): MSVC has no `<sched.h>`, while the box's Linux has it. The test also needs
  `-Wno-deprecated-declarations` for Windows' POSIX names.
- **Stand-in run** (`scratchpad/e6/tbn/run/driver.cpp`, not a deliverable). The output unit was compiled in one TU with
  laptop stand-ins for the kernel's pthread calls, the clock, the mount table, network.cpp's request model and
  `SymbolDatabase::Add`, and its stubs were called directly.
  - on: 49 of 49, covering registration (140 NIDs, both shared ones absent), compares, the SDK string, mutexes, a timed
    wait, a thread, the callouts, the NpManager answers, and a trophy package end to end.
  - off: 6 of 6 (142 NIDs, today's answers).
- **Not checked:** the box's Linux compile and link; the real kernel and network.cpp under the test (the stand-ins
  imitate them); running `tbn0405.cpp` itself. The box build is the first real run.

## Files

| File | md5 |
|---|---|
| `mktbn0405.py` | `62cfb2351d5c1246f6c328b05f591215` |
| `tbn0405.cpp` | `cc524e63e1becf7ecbe65b5b15b8f324` |
| input `src/libs/libNp.cpp` (base tree) | `a2c5facee2708bed1556383b0f5bbdca` |
| output `src/libs/libNp.cpp` | `24e778261495abcd5a069396f14b28b4` |

## Case counts

All three switches on: 165 cases (npcommon 57, npmanager 51, nptrophy 57), ending `tbn0405: on 165 of 165; end`.
All off or unset: 34 cases (12, 15, 7), ending `tbn0405: off 34 of 34; end`. Mixed switches are refused (exit 2).

2026-11-04 (series e7, agent tbt, at the top session's request; found by tbp):
- **The fix.** 65 `Rc(name, call(...), want, more[, info])` statements checked a call's outputs in the call's own argument
  list, and C++ leaves the argument evaluation order unspecified. Each such call is now its own statement inside a block:
  `{ const int call_rc = call(...); Rc(name, call_rc, want, more[, info]); }`. Nothing else changed.
- **Verified** with scratch `e7/tbt/tbnfix/fix_tbn.py` and `undo_check.py`:
  - putting each call back gives the old file, whitespace aside;
  - the 194 case-name sites are the same list in the same order, so the case counts stay 165 on and 34 off;
  - VS clang++ `-fsyntax-only -std=c++20 -Wall -Wextra -Werror` is clean.
- **md5:** `cc524e63e1becf7ecbe65b5b15b8f324` before, `3eeaf1fe800442bcf66b0fa0a0a34338` now.
- **Left alone:** the three `a(...) | b(...)` expressions without output checks (LwMutexUnlock x2, CondInit, CondDestroy)
  call two independent functions; their order does not change any result.
