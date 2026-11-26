# tld0405: loading the dead tables (exp 0405, series e6 of exp 0401)

Tag `tld`. Unit: `src/libs/libs.cpp` only. Files: `mktld0405.py` (the edit), `tld0405.cpp` (the CPU test), this note.

The maintainer's decision 4 of exp 0405 (2026-11-04, "=> B => B"): the 32 tables that KytyPlus compiles but `Libs::InitAll`
never loads are ported first, then loaded, each behind its own switch. Batch 1 is the six CPU-only tables. Tags `tbc`
(libZlib.cpp, libJpeg.cpp, libIme.cpp) and `tbn` (libNp.cpp) port their functions. This unit only does the loading.

No upstream code is inserted. The block loads this tree's own tables, so there is no project, commit or licence to cite
beyond KytyPlus (GPL-2.0).

## Verdicts

All six are wired. Each switch is default off, read once, and uses env_flag.hpp's rule: a switch is on when it is set,
non-empty and not "0".

| Switch | Item | Init function (input tree, checked) | Table's key | NIDs | Keys shared with a live table |
|---|---|---|---|---|---|
| `KYTY_BC5_LOAD_ZLIB` | zlib | `Libs::LibZlib::InitZlib_1`, libZlib.cpp:47 | `Zlib_v1` / `Zlib_v1.1` | 5 | 0 |
| `KYTY_BC5_LOAD_JPEG` | jpeg | `Libs::LibJpeg::InitJpeg_1`, libJpeg.cpp:42 | `JpegEnc_v1` / `JpegEnc_v1.1` | 4 | 0 |
| `KYTY_BC5_LOAD_IME` | ime | `Libs::LibIme::InitIme_1`, libIme.cpp:262 | `Ime_v1` / `Ime_v1.1` | 48 | 7 (live `Ime::InitPlatform_1_Ime`, ime.cpp:1004) |
| `KYTY_BC5_LOAD_NPCOMMON` | npcommon | `Libs::NpCommon::InitNpCommon_1`, libNp.cpp:211 | `NpCommon_v1` / `NpCommon_v1.1` | 28 | 0 |
| `KYTY_BC5_LOAD_NPMANAGER` | npmanager | `Libs::NpManager::InitNpManager_1`, libNp.cpp:383 | `NpManager_v1` / `NpManager_v1.1` | 27 | 2 (live `LibNpManager::InitNet_1_NpManager`, libNet.cpp:1577) |
| `KYTY_BC5_LOAD_NPTROPHY` | nptrophy | `Libs::NpTrophy::InitNpTrophy_1`, libNp.cpp:1067 | `NpTrophy_v1` / `NpTrophy_v1.1` | 87 | 0 |

- Each table's key comes from its `LIB_VERSION("libSceX", 1, "libSceX", 1, 1)`.
- `LibIme` is a different namespace from libs.cpp's own `Ime`. The live `Ime::InitPlatform_1_Ime` stays as it is.
- The NID counts are from the input tree. The tbc and tbn ports may add NIDs. The test lists each table at run time, so it
  needs no change for that.

Journal line, once, at the first InitAll:
- `[bc5] exp 0405: tables on (items: zlib,jpeg,ime,npcommon,npmanager,nptrophy)`, which lists only the items that are on;
- or `[bc5] exp 0405: tables off`.

## What changed

Input `src/libs/libs.cpp` (md5 309aecf7c85a5b47217060bb87ec6512, LF) becomes the output (md5
903fa699db7c20b2b3f288ab572bce8d, 370 lines). Every change is an insertion; no input line changes.

- **Output :7-11:** `<cstdint> <cstdio> <cstdlib> <cstring> <string>`.
- **Output :99-194:** the block. It has:
  - the six `LIB_DEFINE` declarations in their own namespaces;
  - `Bc5Tables::TABLES` (switch, item, init), in load order;
  - `On()`, which reads the switches once, as a function-local static, and prints the line;
  - `LoadSwitched(s)`.
- **Output :197:** the first statement of `InitAll` is `Bc5Tables::LoadSwitched(s);`. Today's 42 `LIB_LOAD`s follow
  unchanged, in today's order.
- **With every switch off:** InitAll reads six variables, prints the off line, and then makes exactly today's calls.

**Load order.** The switched tables load first, before every live table. This is confirmed in `src/loader/symbolDatabase.cpp`
(base tree, md5 2782bc19962a8e92db1ad35c7fc440e6):
- **Record name.** `GenerateName` (:16-22) builds `nid[library_vN][module_vM.m][Type]`, with "libSce" removed from both
  names. A collision for `Find` is therefore the same NID, library name and version, module name and version, and type.
- **Add.** `Add` (:24-39) appends every record to `m_symbols` and does `m_map.insert_or_assign(name, index)`. The newest
  record wins for `Find` (:56-66). A live table loaded later therefore keeps its function for a shared key.
- **FindByNid.** `FindByNid` (:68-79) matches only the NID and the type, in any library. It returns the **first** record in
  `m_symbols`. See risk 1.

## Test: tld0405.cpp

It is built like npgate0401.cpp: `--gate tld0405.cpp <out> --like src/libs/libs.cpp`, linked with every emulator object
except main.cpp.o, with the e6 private units in place.

**Runs.** Each run uses a fresh directory:
- `tld0405 on` with all six switches `=1`;
- `tld0405 off` with all six `=0`;
- `tld0405 off` with all six unset;
- `tld0405 mixed` is accepted for other mixes.

Watchdog 120 s, then a FAIL line and exit 3. It exits 0 only after `tld0405: on|off|mixed 9 of 9; end`.

**Listing records.** The header has no way to list a database's records, so the test calls `SymbolDatabase::DbgDump` into
`./tld0405-dump/` and reads the file back. Every name must give itself back through `SymbolDatabase::GenerateName`.

**Databases built:**
- InitAll's database, twice (the second time with every switch flipped);
- each table's own database: its init function into a fresh `SymbolDatabase`;
- today's InitAll: a copy, call for call, of the input libs.cpp:93-136.

**Cases (9 on, 9 off):**
1. **The switches' line.** stderr goes to `./tld0405-stderr.txt` during both InitAll calls. It must hold exactly one
   `[bc5] exp 0405: tables` line, the expected one. Every `[bc5]` line is echoed as info.
2. **InitAll's record list** (address and name, in order):
   - off: it equals today's InitAll's list, record for record;
   - on: it is the switched tables' own lists in load order, then today's list.
3. **Read once.** Every switch is flipped (on to "0", off to "1") before a second InitAll. The record list must be the same.
4. **Cases 4-9, one per table.** Each line prints NIDs, new, kept live (overridden by live), and the NID-only lookups that
   move. Each key is checked with `Find`:
   - On: a key today's InitAll also registers gives today's function (address and debug name), counted "kept live". Any
     other key gives the table's own function, counted "new".
   - Off: a key today's InitAll also registers gives today's function. Any other key gives nothing.

   Each NID is checked with `FindByNid` against the first record with that NID in the expected list:
   - Off: no NID that only the switched table has resolves.
   - On: the NIDs whose NID-only lookup now reaches the switched table instead of today's function are counted, not
     failed (risk 1).

### Laptop stand-in run

This was a scratch build in `scratchpad/e6/tld/standin`. It used Windows clang++ 22 and lld, and linked:
- the real `tld0405.cpp`;
- the real output `libs.cpp`;
- the real `symbolDatabase.cpp`;
- the input `libZlib.cpp`, `libJpeg.cpp`, `libIme.cpp` and `libNp.cpp`;
- fmt's `format.cc`;
- `standin.cpp`, which replaces today's live tables with fake ones. These keep the real Ime (13) and NpManager (4) keys,
  one Zlib NID under another library, and a duplicate live key. It also stands in for `Common::File` (with the same CRLF
  output), the log and timer, and `setenv`.

| Run | Result |
|---|---|
| All `=1` | `on 9 of 9; end`, exit 0. zlib 5 new, 1 NID-only lookup moved. ime 41 new, 7 kept live, 7 moved. npmanager 25 new, 2 kept live, 2 moved. |
| All `=0` | `off 9 of 9; end` |
| Unset | `off 9 of 9; end` |
| `ime=1`, `nptrophy=yes`, `zlib=` (empty) | `mixed 9 of 9; end` |
| A mismatched argument | exit 2 |

**Negative controls:**
- The **unedited input** libs.cpp with the switches on: cases 1, 2 and 4-9 FAIL (`on 1 of 9 passed; FAIL`, exit 1).
- A variant that loads the tables **last**: case 2 FAILs, ime's 7 and npmanager's 2 shared keys FAIL "kept live", and
  zlib's NID check FAILs (`on 5 of 9 passed; FAIL`, exit 1).

**Syntax** (VS 18 clang++ 22, msvc target, `-fsyntax-only -std=c++20 -Wall -Wextra -Werror`; stand-in `cmake_config.h`;
fmt from refs/Inori_GPCS4; magic_enum from refs/InoriRus_Kyty):
- The input libs.cpp, the output and tld0405.cpp are clean, also with `-Wshadow -Wconversion -Wsign-conversion`.
- A negative control (an unused variable put into the output) is caught.

**Script checks:**
- The script applies to the e6 input tree.
- It refuses its own output (marker) and a changed input (md5).
- Undoing its edits gives the input back byte for byte.
- `diff` shows only insertions.
- Braces, parentheses and brackets balance.

## Risks

1. **The NID-only lookups reach the switched table for shared NIDs.** The loader falls back to `FindByNid` when a title's
   import key is not registered:
   - `RuntimeLinker::Resolve`'s `resolve_by_nid`, runtimeLinker.cpp:2091-2111 (e5 unit, md5 aba94c24ad35a1c944ad3bd5843b13ef);
   - `ResolveLoadedSymbolByNid`, :2181-2207, the late resolve of a stubbed import (:320-335).

   `FindByNid` returns the first record with that NID, and the switched tables are now first. So with `ime` on, an Ime
   import under any key other than `Ime_v1/Ime_v1.1` binds the 7 shared NIDs to LibIme's functions instead of ime.cpp's.
   The 7 are ImeOpen, ImeClose, ImeSetText, ImeSetCaret, ImeParamInit, ImeGetPanelSize and ImeSetTextGeometry. With
   `npmanager` on, the same happens for NpUnregisterStateCallback and NpUnregisterNpReachabilityStateCallback.

   An exact-key import keeps the live function. There is no NID-only overlap in any of the 32 tables beyond these 9 (table
   below), so this is the whole exposure for batch 1. The test prints it per table.

   One load order cannot make the live function win both lookups. A fix would be one of these, all outside this brief:
   - load each live table that shares keys both before and after the switched tables (this calls a live init twice);
   - give the header a "contains" query;
   - accept it.

   The top session should decide.
2. **Split state between a live library and a switched table of the same library.** With `ime` on, LibIme's 41 new
   functions run beside ime.cpp's 13 live ones. Examples are sceImeKeyboardUpdate and sceImeConfirmCandidate, which act
   on an IME the live ImeOpen opened. With `npmanager` on, the title's `sceNpRegisterPlusEventCallback` (GImICnh+boA,
   live, libNet.cpp:1591) and `sceNpUnregisterPlusEventCallback` (xViqJdDgKl0, switched, libNp.cpp:402) land in two
   implementations. tbc's and tbn's ports must share or ignore that state. This is for their notes and the e6 review.
3. **Twice-called init functions.** The test calls each switched init function a second time (for its own list) and runs
   today's live inits three times in total. In the input tree the six bodies are only `LIB_FUNC`. If a port adds state to
   an init function, that state must be idempotent.
4. **Copy of today's InitAll in the test.** If a later series changes InitAll, the copy drifts and case 2 fails (by
   design: that is the check).
5. **DbgDump's file I/O.** The test needs a writable fresh directory. If `Common::File::Create` fails, `Write` hits its
   `EXIT_IF` and the run ends without the end line.

## Not checked / held

- **Not checked on the laptop:** GCC on the box, the real link with every emulator object, and the real live tables. The
  box build is the first real compile and run.
- **The other 26 tables (decision 4, later batches):** not wired here, as the brief asks. Sizes from the input tree are
  below.

## The 32 dead tables (input tree, static)

**How this was counted.** A static parse of every `LIB_DEFINE` under `src/` (scratch script `scratchpad/e6/tld/tables.py`).
It covers:
- namespaces;
- each body's `LIB_VERSION` / `LIB_NAME` / `LIB_USING` lookup, with the key built as `GenerateName` does;
- libKernel's `AddLibkernelUnityFunc`;
- calls between init functions;
- reachability from `Libs::InitAll`.

**What it found:**
- **Live:** 110 init functions and 1969 records (1959 distinct keys), counting every conditional registration, so this is
  a superset.
- **Dead roots:** 32, which matches the brief's 32.
- **Shared keys and NIDs:** no two dead tables share a key or a NID. Beyond batch 1's 9 shared keys, no dead table
  registers any NID+type that a live table registers, under any key.
- **Not counted:** three more defined but never-loaded functions have empty bodies and are not among the 32:
  `LibRandom::InitRandom_1` (libRandom.cpp:68), `LibSigninDialog::InitSigninDialog_1` (libSigninDialog.cpp:20) and
  `LibSystemGesture::InitSystemGesture_1` (libSystemGesture.cpp:20).

**Column meanings:**
- **Live NIDs in the same library:** live records whose library and module key equals the table's. These are the
  split-state candidates of risk 2.
- **Shared keys:** collide for `Find`.
- **Shared NIDs:** NID+type collisions under any key.

### Batch 1 (wired here)

| Table | Init function | File:line | NIDs | Live NIDs in the same library | Shared keys | Shared NIDs |
|---|---|---|---|---|---|---|
| Zlib | `LibZlib::InitZlib_1` | libZlib.cpp:47 | 5 | 0 | 0 | 0 |
| JpegEnc | `LibJpeg::InitJpeg_1` | libJpeg.cpp:42 | 4 | 0 | 0 | 0 |
| Ime | `LibIme::InitIme_1` | libIme.cpp:262 | 48 | 13 | 7 | 7 |
| NpCommon | `NpCommon::InitNpCommon_1` | libNp.cpp:211 | 28 | 0 | 0 | 0 |
| NpManager | `NpManager::InitNpManager_1` | libNp.cpp:383 | 27 | 29 | 2 | 2 |
| NpTrophy | `NpTrophy::InitNpTrophy_1` | libNp.cpp:1067 | 87 | 0 | 0 | 0 |

### The remaining 26 (not wired)

| Table | Init function | File:line | NIDs | Live NIDs in the same library | Shared keys | Shared NIDs |
|---|---|---|---|---|---|---|
| NpTus | `NpTus::InitNpTus_1` | libNp.cpp:1873 | 142 | 0 | 0 | 0 |
| NpParty | `NpParty::InitNpParty_1` | libNp.cpp:582 | 26 | 0 | 0 | 0 |
| NpPartner001 | `NpPartner::InitNpPartner_1` | libNp.cpp:439 | 4 | 0 | 0 | 0 |
| NpAuth | `NpAuth::InitNpAuth_1` | libNp.cpp:57 | 5 | 8 | 0 | 0 |
| NpSnsFacebookDialog | `NpSnsFacebookDialog::InitNpSnsFacebookDialog_1` | libNp.cpp:622 | 1 | 0 | 0 | 0 |
| Camera | `LibCamera::InitCamera_1` | libCamera.cpp:402 | 76 | 0 | 0 | 0 |
| Usbd | `LibUsbd::InitUsbd_1` | libUsbd.cpp:1035 | 65 | 0 | 0 | 0 |
| Hmd | `LibHmd::InitHmd_1` | libHmd.cpp:707 | 137 | 0 | 0 | 0 |
| Ngs2 (libNgs2.cpp) | `LibNgs2::InitNgs2_1` | libNgs2.cpp:222 | 40 | 26 | 0 | 0 |
| Voice | `LibVoice::InitVoice_1` | libVoice.cpp:92 | 14 | 16 | 0 | 0 |
| Move | `LibMove::InitMove_1` | libMove.cpp:77 | 11 | 0 | 0 | 0 |
| ScreenShot | `LibScreenShot::InitScreenShot_1` | libScreenShot.cpp:93 | 14 | 0 | 0 | 0 |
| RemotePlay | `LibRemotePlay::InitRemotePlay_1` | libRemotePlay.cpp:217 | 39 | 3 | 0 | 0 |
| GameLiveStreaming | `LibGameLiveStreaming::InitGameLiveStreaming_1` | libGameLiveStreaming.cpp:735 | 45 | 2 | 0 | 0 |
| SharePlay | `LibSharePlay::InitSharePlay_1` | libSharePlay.cpp:132 | 22 | 2 | 0 | 0 |
| WebBrowserDialog | `LibWebBrowserDialog::InitWebBrowserDialog_1` | libWebBrowserDialog.cpp:225 | 12 | 2 | 0 | 0 |
| InvitationDialog | `LibInvitationDialog::InitInvitationDialog_1` | libInvitationDialog.cpp:170 | 9 | 0 | 0 | 0 |
| VideoRecording | `LibVideoRecording::InitVideoRecording_1` | libVideoRecording.cpp:75 | 1 | 0 | 0 | 0 |
| DiscMap | `LibDiscMap::InitDiscMap_1` | libDiscMap.cpp:135 | 5 | 0 | 0 | 0 |
| ulobjmgr | `LibUlobjmgr::InitUlobjmgr_1` | libUlobjmgr.cpp:120 | 4 | 0 | 0 | 0 |
| CompanionHttpd | `CompanionHttpd::InitCompanionHttpd_1` | libCompanion.cpp:211 | 17 | 0 | 0 | 0 |
| CompanionUtil | `CompanionUtil::InitCompanionUtil_1` | libCompanion.cpp:312 | 5 | 0 | 0 | 0 |
| RazorCpu | `LibRazorCpu::InitRazorCpu_1` | libRazorCpu.cpp:570 | 34 | 1 | 0 | 0 |
| VrTracker | `LibVrTracker::InitVrTracker_1` | libVrTracker.cpp:645 | 39 | 0 | 0 | 0 |
| GnmDriver | `LibGnmDriver::InitGnmDriver_1` | libGnmDriver.cpp:3294 | 251 | 0 | 0 | 0 |
| RageEngine | `RageEngine::InitRageEngine_1` | libRageEngine.cpp:203 | 15 (module v1.0) | 0 | 0 | 0 |

**Totals:** the remaining 26 have 1033 NIDs; batch 1 has 199; all 32 have 1232.

**Notes on the remaining 26:**
- All init functions are in `Libs::`. Every key is `<name>_v1` / `<name>_v1.1`, except RageEngine (v1.0) and RemotePlay
  (`Remoteplay`).
- Every one of the 26 bodies is plain `LIB_FUNC`, with no other statement.
- Since no NID is shared, risk 1 does not arise for any of them. Risk 2 does arise wherever the "live NIDs in the same
  library" column is not 0.

## Files

| File | md5 |
|---|---|
| input `src/libs/libs.cpp` (base tree, LF) | 309aecf7c85a5b47217060bb87ec6512 |
| output `src/libs/libs.cpp` | 903fa699db7c20b2b3f288ab572bce8d |
| `mktld0405.py` | 5557b2ba4a65cb9e9c6b0bd2f84d4f7d |
| `tld0405.cpp` | 02ae1902c6ae557e9c9be06e4fb2fc95 |
| read only: `src/loader/symbolDatabase.cpp` / `.h` | 2782bc19962a8e92db1ad35c7fc440e6 / b0e0ccdaab9d96c1d7e9fe93dfd64102 |
| read only: `libZlib.cpp`, `libJpeg.cpp`, `libIme.cpp`, `libNp.cpp` (input tree) | f5d3aafebca0d202082365ee609f15b6, a85a83b8d541f5e10c14d739ff56457f, a572240f789088264b6e13850978b739, a2c5facee2708bed1556383b0f5bbdca |
