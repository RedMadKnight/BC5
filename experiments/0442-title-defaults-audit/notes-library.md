# Audit: the twenty library words of `kTitleDefaults` (TITLE2 only)

Read-only, worktree `~\Downloads\bc5\wt0442`. "P:n" = line n of
`backend/kytyplus-patches/0001-bc5-lle-agc.patch`. The rows are P:6175-6195, the comment is P:6145-6147.

## 0. The exp 0413 "the first title ends at 5-6 s" result: what it was, and that it was explained and fixed

**What was seen** (`experiments/0413-np-session-v2-shared/README.md:178-191`):
- a1t1 (defaults table on, 56 rows): "CRASH at 5 s: a write to address 0 at guest 0x90000048f".
- a3t1 (`KYTY_BC5_SWITCH_DEFAULTS=0`): PASS 120 s.
- b1-b9, c1-c6 (rows set to 0 in groups): "the same crash ... whenever four or more of A15, A16, A17, A21, A22 are on. It
  passes with any two of them off (c3-c6, b5) and does not depend on the other rows" (README:181).
- d1 (the five rows off): PASS 120 s. Consequence: the five rows (the 20 words) left the table, launcher-only
  (README:185-191), "The cause in the first title is not found".

**The same README then refutes the "four or more" reading.**
- The bisect turned rows off by adding `NAME=0` words to the starting environment
  (`integration/bisect.sh:6-7`), so every "off" also grew the environment.
- e1env/e3env/e4dum (README:205-209): the table on plus 20 dummy variables PASSES. "d1 delivered 'five rows off' as 20
  `NAME=0` words ... what e4dum showed to be enough by themselves to pass" (README:285-289).
- h1t1 (README:283): with the five rows already out of the table, the first title still crashes at 5 s, same address.
- The count of dummy variables alone decides it, not monotonically: "n = 2, 4, 6: crash; 8 ... 24: PASS; 29: crash"
  (README:367). Disjoint row groups g1 and g3 each remove the crash. "No single row is the cause" (README:432).

**The cause, found the same day** (README:537-580, HANDOFF F816 at `docs/HANDOFF.md:799`):
- `CommandBufferSetBuffer` in `src/libs/libAmpr.cpp` chose its "map flavour" when `a3 != va && a4 == -1`.
- The first title passes three arguments, so `a4` was whatever was left in `r8`. When that was -1, the host mapped zeroed
  direct memory, fixed, over a live page of the title's heap at 0x300a80000.
- What host code ran just before (the `getenv` readers, their loop length, the extra rows) decided the leftover. That is
  why the outcome moved with the number of words, the environment size and every diagnostic build.

**The fix:**
- `KYTY_BC5_AMM_SETBUFFER_GUARD`, on in code (P:60718-60730, `+++ b/src/libs/libAmpr.cpp` from P:58688). Since exp
  0419 its option is removed (`kIgnored`, P:6127). The map flavour is opt-in since exp 0416
  (`KYTY_BC5_AMM_SETBUFFER_MAP`, P:60744-60750).
- Proof (README:603-611): with the guard on, starts at n = 0-16 pass 17 of 17, and the guard line shows
  `a4 0xffffffff` in the starts that used to crash. Guard off: 3 of 3 crash at 5-6 s. Final build check f1n/f3n0
  (README:641-643).

**Conclusion.**
- The 5-6 s end was a host AMM bug, fixed since 2026-11-12. None of the twenty words caused it.
- The patch comment (P:6146) and exp 0419's copies of the claim are stale: `experiments/0419-switch-cleanup/README.md:60`
  and `switch-inventory-summary.md:30` ("cause not found").
- A different the first title "ends at 5 s" (F833/F835, eboot+0x29c385, the transferring-mount save) is also unrelated to these
  words. It was fixed in exp 0422, and arm sm1 of exp 0417 ran with `SAVEDATA_MEMORY_FIXES=existed` and changed
  nothing (`experiments/0417-shared-followups/README.md:449-461`).

**Runs of the first title with the twenty on:**
- exp 0413 e1env and e3env (pre-guard binary a76f86ab, all 20 as environment words): PASS 90 s (README:205,207).
- The crashing a1/b*/c*/h1 runs also had them on; F816 explains those crashes.
- **Not found:** any first-title run with all twenty on after the guard was in (01abfc0c and later).
- In the later first-title logs (exp 0433 s433sc/s433sn, `experiments/0433-ports-pack1/raw/swap/s433sn-play.log:22-47`) all
  twenty print "off": "audioout checks off", "tables on (items: nptus,...,move)" without zlib..nptrophy, "ult off" and so on.
- The second title's run s433su prints all twenty "on". It also prints "38 title defaults, 3 taken, 35 already set in the
  environment" (s433su-play.log:15): `tools/scripts/launchers/play-pkg.sh:72-80` still sets the twenty itself.

**Third title** (TITLE3, `experiments/0439-third-title/README.md:7`):
- It starts through play-any.sh and play-t1.sh, which set none of the twenty, and the table is TITLE2 only.
- No run of it with any of the twenty on was found. (grep of exps 0439-0441 and HANDOFF F890-F894: no hit.)

**Overlap with kDefaults/kFixes** (P:5993-6109):
- None of the twenty is in kDefaults, kFixes or kSoft under its own name or another.
- Related, but separate words that are already on for every title:
  - `KYTY_BC5_SAVEDATA_FIXES`, `_EVENT_CB`, `_SORT` (A4);
  - `KYTY_BC5_AUDIO_FIXES` (A5);
  - `KYTY_BC5_FW_AUDIO` (A19);
  - `KYTY_BC5_FW_NET` (A18, which includes SystemService param400).
- The `BC5_R3_*` words are the memory-call group A13 (`mem on (...)`), not these.
- Precedent: the other 19 `LOAD_*` tables of batch 2 (nptus..move) became "built in" for every title in exp 0419
  candidate G. The maintainer's word, 2026-11-13: ports of system libraries are built in, but
  run only when a game calls them (`experiments/0419-switch-cleanup/ports-analysis.md:3`, `candidate-G-plan.md:16`). First-title logs
  show those tables on. Batch 1 (these six) was kept per title only because of the 0413 claim.

**Side note:**
- The comment at P:6142-6143 says `KYTY_BC5_SWITCH_DEFAULTS=0` skips the title table.
- But `KYTY_BC5_SWITCH_DEFAULTS` is in `kIgnored` (P:6131: "removed with this change"), which strips it from the
  environment at start.
- Whether the title table still honours it was not traced.

---

The common origin for all twenty:
- exp 0401 series e5/e6, the ports of exp 0405 "port research for any title" (top-32 rows 16-22 and R1/R2 extras).
- Audit `experiments/0413-np-session-v2-shared/audit-unintegrated.md:34-41`, rows A15, A16, A17, A21, A22, all
  "integrate (default on)".
- Tested only on the second title: exp 0401 night arms tsvc/tlib/tao/t6pad/t6tbl, r5/r6 15-min routes and the a5/a6
  replug (`experiments/0401-mesa-preamble-switches/README.md:262-278, 375-389`).
- Each word prints one stderr line at its library's registration, on or off.

## A15: SaveData memory, Http2, Pad open-ext

### 1. KYTY_BC5_SAVEDATA_MEMORY_FIXES
- **Read:** `+++ b/src/libs/libSaveData.cpp` (P:77409), at P:78700. Items are used at P:80152 (`sync`), P:78833 (`lock`)
  and P:79666 (`existed`).
- **On:**
  - `sync`: `sceSaveDataSyncSaveDataMemory` posts MEMORY_SYNC_END.
  - `lock`: the save-data event queue is taken under a lock.
  - `existed`: `existed_memory_size` is memory.dat's size before the call, 0 when there is none.
- **Off:** no sync-end event, no lock, and `existed` answers the store's size (at least 64 KiB) on a first run.
- **Origin:** exp 0405 top-32 rows 19-20, R2 KS03/SS01/KS02 and KS09/SS02 (KytyPS5 dfec14a, sharpemu, shadPS4):
  "a title polling GetEventResult waits forever" (`experiments/0405-port-research-all-titles/README.md:115-116`).
  Notes: `experiments/0401-mesa-preamble-switches/svc0405-notes.md:23-65`.
- **First-title evidence:**
  - exp 0413 e1env/e3env PASS 90 s with it on.
  - exp 0417 sm1, `=existed` only: the first title's save path is the same as without it (0417 README:453-461).
  - The first title does use save-data memory: a BackgroundTaskW thread reads `sce_sdmemory/memory.dat`, 0413 README:510-512.
  - So this word acts on the first title's path.
- **Scope:** only inside the SaveData memory and event-queue functions.
- **Risk:** low-medium. `existed`: a title that never called Set before now sees 0 and initialises again (svc notes:64).
  `lock`: a leaf lock under `g_mount_mutex` (svc notes:202).
- **Kind:** a fix restoring console behaviour, from emulator sources, not measured on a console (svc notes:200).
  No title data.

### 2. KYTY_BC5_SAVEDATA_DELETE_BUSY
- **Read:** libSaveData.cpp, P:78719. The use is at P:80045, and the mount mutex is held for the scope, P:78740.
- **On:** `SaveDataDelete` of a mounted save returns BUSY, holding `g_mount_mutex` while it removes files.
- **Off:** deletes it.
- **Origin:** R2 KS14 + SS10, KytyPS5 dfec14a `libSaveData.cpp:1051-1056` (svc notes:108-110).
- **First-title evidence:** exp 0413 e1env/e3env only. Not found: a call log showing the first title calls Delete.
- **Scope:** only inside `sceSaveDataDelete`.
- **Risk:** low.
- **Kind:** a fix. No title data.

### 3. KYTY_BC5_SAVEDATA_ALIASES
- **Read:** libSaveData.cpp, P:78729.
- **On:** NIDs `ZkZhskCPXFw` (sceSaveDataInitialize) and `l1NmDeDpNGU` (Initialize2) are registered to
  `SaveDataInitialize3` in both SaveData tables.
- **Off:** they are not registered, so a title importing them gets the loader stub.
- **Origin:** R1 #15, AnyPS5 bc6a5e4ea and shadPS4 (svc notes:104-107).
- **First-title evidence:** exp 0413 e1env/e3env.
- **Scope:** only a title that imports those two NIDs. Not found: whether the first title imports them. No "stubbed import" line for
  SaveData appears in the s433sn log, which suggests no.
- **Risk:** very low.
- **Kind:** a port (missing exports). No title data.

### 4. KYTY_BC5_HTTP2_FIXES
- **Read:** `+++ b/src/libs/libNet.cpp` (P:69336), at P:69414. Items: `agent` P:69439, `async` P:69463, `ssl` P:69493.
- **On:**
  - `async`: Http2 SendRequestAsync/ReadDataAsync trigger the caller's equeue user event.
  - `ssl`: SSL enable/disable accepts a context id.
  - `agent`: a wrapper replaces `Http::HttpCreateTemplate` and passes "" for a NULL user agent.
- **Off:** no trigger (a hang for a waiting title), INVALID_ID, and NULL passed on.
- **Origin:** exp 0405 top-32 row 21 (R2 KS01, KytyPS5 a06e356) plus R2 KS04 and R1 #18 (svc notes:67-120).
- **First-title evidence:** exp 0413 e1env/e3env.
- **Scope:** Http2 functions, and the Http `CreateTemplate` registration (`agent`). The first title imports Http_v1: one NID is a
  "stubbed import" (s433sn-play.log). Not found: whether it calls CreateTemplate. No network on the box.
- **Risk:** low.
- **Kind:** a fix. The argument layout is TODO(verify) (svc notes:82). No title data.

### 5. KYTY_BC5_PAD_OPEN_EXT
- **Read:** `+++ b/src/libs/libPad.cpp` (P:75657), at P:75798. Registered at P:76134-76136.
- **On:** NID `WFIiSfXGUq8` (scePadOpenExt) is registered to `Bc5PadOpenExt`, which maps port type 1 to 0 and calls
  `Controller::PadOpen`.
- **Off:** not registered: the stub returns handle 0, which every pad call rejects (no input).
- **Origin:** exp 0405 top-32 row 22, R2 SS22 + KS69, sharpemu 373100a (svc notes:84-100).
- **First-title evidence:** exp 0413 e1env/e3env.
- **Scope:** only a title that imports scePadOpenExt. The first title has pad input today with it off, so it opens with scePadOpen.
- **Risk:** very low.
- **Kind:** a port (missing export). Port type 1 is TODO(verify). No title data.

## A16: Json2, Ult, UserService, SystemService

### 6. KYTY_BC5_JSON2_FIXES
- **Read:** `+++ b/src/libs/libJson2.cpp` (P:67268), at P:67336. Uses at P:67493-67668, line at P:67921.
- **On:** assignment and set calls copy the source before clearing the destination. Covers `v = v["a"]`, `obj = obj`,
  `set(getString())` and the like.
- **Off:** use-after-free, or emptied objects.
- **Origin:** R1 #1 + R2 KS05, AnyPS5 4f41f4c37 and KytyPS5 dfec14a (`lib0405-notes.md:25-35`).
- **First-title evidence:** exp 0413 e1env/e3env.
- **Scope:** only inside libSceJson2 functions. Not found: whether the first title imports Json2.
- **Risk:** low: a memory-safety fix.
- **Kind:** a fix. No title data.

### 7. KYTY_BC5_ULT_FIXES
- **Read:** `+++ b/src/libs/libUlt.cpp` (P:81422), at P:81496. Uses at P:81438, P:81610-81641.
- **On:**
  - `join`: the ulthread handle is published only after the thread is stored, and Join claims ownership.
  - `queue`: the queue grows past num_data instead of silently dropping the item, with a catcher line.
- **Off:** today's race and drop.
- **Origin:** R1 #2 (AnyPS5 ffe469199) and R2 SK07 (sharpemu) (lib notes:59-90).
- **First-title evidence:** exp 0413 e1env/e3env.
- **Scope:** only inside libSceUlt. Not found: whether the first title uses Ult.
- **Risk:** low-medium. "Growth" instead of a blocking push is not console-verified (lib notes:190).
- **Kind:** a fix. The losing joiner's STATE answer is AnyPS5's choice, TODO(verify). No title data.

### 8. KYTY_BC5_USERSERVICE_VALUES
- **Read:** `+++ b/src/libs/libUserService.cpp` (P:84350), at P:84420. Uses at P:84516-84613.
- **On:**
  - `name`: GetUserName gives errors for null, unknown or short buffers instead of an EXIT or a null write.
  - `login`: seven getters check the login before the null output.
  - `age`: AgeLevel is 0xFFFFFFFF.
  - `zoom`: the accessibility values.
- **Off:** today's answers. AgeLevel 9.
- **Origin:** R1 #3 + R2 KL03. AnyPS5's debt note cites console measurements on PS5 13.60 (lib notes:94-118).
- **First-title evidence:** exp 0413 e1env/e3env.
- **Scope:** only inside UserService getters. First-title almost certainly calls UserService (every title does), so the `age`
  and `login` answers would differ on its path.
- **Risk:** low. "A title that read 9 as an age level now reads 0xFFFFFFFF ('no restriction'), as on a console"
  (lib notes:118).
- **Kind:** a fix restoring measured console values. No title data.

### 9. KYTY_BC5_SYSTEMSERVICE_VALUES
- **Read:** `+++ b/src/libs/libSystemService.cpp` (P:80949), at P:81060. Uses at P:81216 (`int`), P:81244 (`table`),
  P:81260 (`string`).
- **On:**
  - `int`: ParamGetInt refuses ids outside 1-5, 100-111, 200-213, 300, 400 with 0x80A10003, writing nothing.
  - `table`: 100-111, 200-213 and 300 answer one 13.40 console's settings values (P:81005-81007, P:81028-81029).
  - `string`: ParamGetString answers only id 6.
- **Off:** unknown ids answer 0, and ParamGetString of another id EXITs.
- **Origin:** R1 #4, AnyPS5 debt note (a ptrace sweep on PS5 13.40) (lib notes:120-143).
- **First-title evidence:** exp 0413 e1env/e3env. The first title asks ParamGetInt(1) (s433sn-play.log:173, "bc5 system param 1 -> 1"),
  which is unaffected.
- **Scope:** only inside SystemService Param calls, but every title calls these.
- **Risk:** medium (the notes' own rating, lib notes:142-143). A title relying on 0 for an unknown id now gets an error.
  The table values' meaning is unknown.
- **Kind:** a fix, but `table` carries console settings data, one console's values. That is not title data.

### 10. KYTY_BC5_SYSTEMSERVICE_PARAMS_7_1000
- **Read:** libSystemService.cpp, P:81076. The use is through `Bc5SysParamRefused`, P:81216.
- **On:** ParamGetInt 7 (game parental level) and 1000 (enter button assignment) return 0x80A10003.
- **Off:** 0 and 1 (cross) (P:81013-81015).
- **Origin:** the same 13.40 measurement, kept as its own switch because "titles read these today".
- **First-title evidence:** exp 0413 e1env/e3env only.
- **Scope:** SystemService ParamGetInt. Any title reading the enter-button parameter is affected.
- **Risk:** the highest of the twenty for an untested title: a title that reads 1000 and does not handle an error.
  Not found: whether the first title reads 7 or 1000. Its short run shows only 1, but logs of longer runs were not checked.
- **Kind:** a console-measured behaviour fix. No title data.

## A17: AudioOut, AudioIn, Ngs2

### 11. KYTY_BC5_AUDIOOUT_CHECKS
- **Read:** `+++ b/src/libs/audio.cpp` (P:36018), at P:36198. Uses at P:37098 (ka02), P:37110 (ka01).
- **On:**
  - ka01: sceAudioOutOutputs with num 0 or > 32 returns INVALID_SIZE.
  - ka02: AudioOutOpen with freq 0 returns INVALID_SAMPLE_FREQ.
- **Off:** an EXIT, or a stack overflow; and a later SIGFPE.
- **Origin:** exp 0405 top-32 rows 16-17, R2 KA01/KA02, KytyPS5 dfec14a (`ao0405-notes.md:31-46`).
- **First-title evidence:** exp 0413 e1env/e3env. First-title logs print "audioout checks off".
- **Scope:** only on argument values that today kill the process. Valid calls take the same path.
- **Risk:** very low.
- **Kind:** a fix (error codes instead of a crash). No title data.

### 12. KYTY_BC5_AUDIOIN_CHECKS
- **Read:** audio.cpp, P:36204. Uses at P:37084, P:37123, P:37149.
- **On:**
  - ka06: sceAudioInInput writes silence, and a null dest returns 0.
  - ka07: AudioInOpen returns errors for a bad type, index, len or freq, and type 0 opens a port.
- **Off:** dest is never written (stale data), a null dest exits, and type != 1 exits.
- **Origin:** R2 KA06/KA07, KytyPS5 (ao notes:62-73).
- **First-title evidence:** exp 0413 e1env/e3env. The first title imports 4 AudioIn NIDs that are "stubbed imports"
  (s433sn-play.log, `nya-R5gDYhM`, `BohEAQ7DlUE`, `Jh6WbHhnI68`, `X+4jdIS75P0`). Those are not the ported functions,
  so not found whether the first title reaches ka06/ka07 at all.
- **Scope:** only inside AudioIn.
- **Risk:** low ("titles that read AudioIn now get silence instead of a stale buffer", ao notes:145).
- **Kind:** a fix. No title data.

### 13. KYTY_BC5_NGS2_RACK_FIX
- **Read:** audio.cpp, P:36210. Uses at P:37822, P:37851 (destroy), P:37861 (render walk), P:37896 (ka08).
- **On:**
  - ka03: Ngs2RackDestroy unlinks the rack and gives its buffer back through the allocator. RackCreate links under
    `g_bc5_racks_mutex`, and **`Ngs2SystemRender` walks the racks under that mutex**.
  - ka08: custom-rack voice-state size handling.
- **Off:** the renderer keeps writing into freed rack memory, and a size mismatch exits.
- **Origin:** exp 0405 top-32 row 18 (R2 KA03, risk "medium; replug") and KA08 (ao notes:48-80).
- **First-title evidence:** exp 0413 e1env/e3env. Replug a5/a6 PASS was on the second title only.
- **Scope:** NOT only on the destroy path. With ka03 on, every Ngs2SystemRender call of any Ngs2 title takes a new mutex,
  so it touches the audio render path of any title using Ngs2. Not found: whether the first title uses Ngs2.
- **Risk:**
  - low-medium: the free handler, which is title code, is now called from RackDestroy;
  - a second destroy returns an error;
  - the lock order is system then racks (ao notes:139-147);
  - the error codes are TODO(verify).
- **Kind:** a fix (use-after-free). No title data.

## A21: firmware pad

### 14. KYTY_BC5_FW_PAD
- **Read:** libPad.cpp, P:75894. Registrations at P:76131-76135 and P:76155-76178.
- **On:**
  - **scePadInit (`hv1luiJrqQM`) is registered to `Bc5FwPadInit`**, which calls `Controller::PadInit` and records the
    init state.
  - 18 more NIDs are registered: GetInfoByPortType; twelve calls with argument checks (ReadStateExt, GetDeviceInfo,
    GetCapability, ReadHistory, OpenExt2 and others); five queries.
  - Past their checks they return 0 and write nothing.
- **Off:** the 18 NIDs are the loader stub (0, nothing written), and scePadInit is the plain one.
- **Origin:** exp 0405 rows b94b3fa32, 3b404f65e and 2f9581050: AnyPS5 4f41f4c37, rewritten "from behaviour only" on the
  maintainer's word yes, rewritten the way the JIT item was (`pad0405-notes.md:1-30, 44-100`).
- **First-title evidence:** exp 0413 e1env/e3env. The pad replug on e6 was the second title only.
- **Scope:** the scePadInit swap is on every pad title's path (first-title included), though it only adds a flag. The other 18
  change answers only for titles that import them. A call made before scePadInit now returns NOT_INITIALIZED.
- **Risk:** low-medium. A title that calls GetDeviceInfo, GetCapability or similar before Init, or with a type other than
  0 or 2, gets an error instead of 0. Not found: which of the 18 first title imports. None appears among its "stubbed import"
  lines in s433sn, which suggests none.
- **Kind:** a firmware-behaviour port (argument checks). No title data.

## A22: dead tables, batch 1 (the six LOAD_* words)

How a LOAD_* word works:
- The table is in `+++ b/src/libs/libs.cpp` (P:86127): `Bc5Tables::TABLES[]` at P:86318. Batch-1 rows are at
  P:86319-86324, read at P:86357, line printed at P:86367, `LoadSwitched` runs first in InitAll at P:86389.
- **It does not load a firmware or system module from disk.** It registers HLE tables that are host C++ in this patch,
  ported in adapted form from AnyPS5 (GPL-2.0) and KytyPS5: "No upstream code: this block only loads this tree's own
  tables" (P:86186).
- So it needs no Sony material in the repo, and no module file on the box.
- Each library's unit also reads the same word for its ported branches.
- **The host table wins over a guest module's exports** (`ports-analysis.md:13-17`, citing `runtimeLinker.cpp:2126`). So
  with the word on, a title importing that library gets the host's ported answers instead of a stub. It would get them
  even instead of a module the title shipped itself.
- A title that does not import the library is unaffected, except for more records in the symbol database and one stderr
  line. The 9 NIDs that collided under FindByNid (7 Ime, 2 NpManager) are no longer registered by these tables
  (0401 README:363-366; `thb0405-notes.md:71-104`).
- Origin for all six: exp 0405 decision 4 ("each table's functions are ported first, then the table is loaded"),
  0401 e6 tags tbc/tbn/tld/thb. CPU tests 108/26, 165/34, 9/9 (0401 README:355-357). t6tbl arm clean (0401 README:381),
  second title only.

### 15. KYTY_BC5_LOAD_ZLIB
- **Read:** P:86319 (libs.cpp) and `+++ b/src/libs/libZlib.cpp` (P:85887) at P:85938. Uses at P:86075-86102.
- **On:** libSceZlib v1 is registered with ported Initialize, Finalize, Inflate, WaitForDone and GetResult.
- **Off:** the table is not loaded (stubs: OK, nothing written).
- **First-title evidence:** exp 0413 e1env/e3env only. No first title "stubbed import" line for Zlib.
- **Scope:** only importers of libSceZlib.
- **Risk:** low.
- **Kind:** a library port (HLE table). No title data.

### 16. KYTY_BC5_LOAD_JPEG
- **Read:** P:86320 and `+++ b/src/libs/libJpeg.cpp` (P:66998) at P:67083. Uses at P:67222-67252.
- **On:** libSceJpegEnc is registered with Create, Delete, QueryMemorySize and Encode's argument checks. The encode
  itself is held.
- **Off:** not loaded.
- **First-title evidence:** exp 0413 only.
- **Scope:** only importers.
- **Risk:** low.
- **Kind:** a library port. No title data.

### 17. KYTY_BC5_LOAD_IME
- **Read:** P:86321 and `+++ b/src/libs/libIme.cpp` (P:66226) at P:66304. Uses at P:66364-66373, held stubs at P:66455.
- **On:**
  - The dead libSceIme v1 table is registered, with items `panel` and `test`.
  - Its 7 NIDs that the live Ime table (`Ime::InitPlatform_1_Ime`) also has are not registered.
  - 39 held stubs are unregistered (thb).
- **Off:** not loaded.
- **First-title evidence:** exp 0413 only.
- **Scope:** only importers of libSceIme keys that the live table lacks.
- **Risk:** low.
- **Kind:** a library port. No title data.

### 18. KYTY_BC5_LOAD_NPCOMMON
- **Read:** P:86322 and `+++ b/src/libs/libNp.cpp` (P:70024) at P:70093. Uses at P:70469+.
- **On:** 28 NpCommon NIDs are ported: ids, mutex, cond, thread, clock, sdkversion, callout (`tbn0405-notes.md:51`).
- **Off:** not loaded.
- **First-title evidence:** exp 0413 only.
- **Scope:** only importers. NpCommon is a common PSN library, so the first title may import it. Not found: its import list.
- **Risk:** low-medium: `callout` and `thread` are ported behaviour.
- **Kind:** a library port. No title data.

### 19. KYTY_BC5_LOAD_NPMANAGER
- **Read:** P:86323 and libNp.cpp at P:70757. Uses at P:70883+.
- **On:** 20 NpManager NIDs are ported, 4 held, and 2 left to the live table (tbn notes:108).
- **Off:** not loaded.
- **First-title evidence:** exp 0413 only.
- **Scope:** only importers, and the live NpManager table keeps its keys.
- **Risk:** low-medium.
- **Kind:** a library port. No title data.

### 20. KYTY_BC5_LOAD_NPTROPHY
- **Read:** P:86324 and libNp.cpp at P:71579. Uses at P:72038+.
- **On:** 23 NpTrophy NIDs are ported (context, handle, register, unlock, info, icon, setinfo, dbg), and 64 held stubs are
  unregistered.
- **Off:** not loaded.
- **First-title evidence:** exp 0413 only.
- **Scope:** only importers. Trophy titles, first-title likely among them, would take a different path at start (register
  context).
- **Risk:** medium for an untested title, because trophy registration runs early at start.
- **Kind:** a library port. No title data.

---

## Summary table

| # | Word | Kind | Only inside its library? | First-title run with it on |
|---|---|---|---|---|
| 1 | SAVEDATA_MEMORY_FIXES | fix | yes (SaveData memory and events); the first title uses it | 0413 e1env/e3env; 0417 sm1 (existed) |
| 2 | SAVEDATA_DELETE_BUSY | fix | yes | 0413 e1env/e3env |
| 3 | SAVEDATA_ALIASES | port (2 NIDs) | yes | 0413 |
| 4 | HTTP2_FIXES | fix | yes (Http2, plus the Http CreateTemplate registration) | 0413 |
| 5 | PAD_OPEN_EXT | port (1 NID) | yes | 0413 |
| 6 | JSON2_FIXES | fix | yes | 0413 |
| 7 | ULT_FIXES | fix | yes | 0413 |
| 8 | USERSERVICE_VALUES | console-measured fix | yes, but every title calls it | 0413 |
| 9 | SYSTEMSERVICE_VALUES | console-measured fix, plus one console's settings values | yes, but every title calls it | 0413 |
| 10 | SYSTEMSERVICE_PARAMS_7_1000 | console-measured fix | yes, but enter-button reads are common | 0413 |
| 11 | AUDIOOUT_CHECKS | fix | only on today's crash arguments | 0413 |
| 12 | AUDIOIN_CHECKS | fix | yes | 0413 |
| 13 | NGS2_RACK_FIX | fix | no: a mutex on every Ngs2SystemRender | 0413 |
| 14 | FW_PAD | firmware-behaviour port | no: scePadInit swapped for all pad titles (adds a flag) | 0413 |
| 15-20 | LOAD_ZLIB/JPEG/IME/NPCOMMON/NPMANAGER/NPTROPHY | library port (host HLE tables, no Sony files) | yes, importers only | 0413 |

"0413" means e1env/e3env, 90-s starts on a pre-guard binary, plus the crashing runs that F816 explains. No first-title run with
the twenty on after the AMM set-buffer guard was found. No run of the third title with any of them on was found.
