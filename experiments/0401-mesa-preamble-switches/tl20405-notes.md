# tl2: loading batch 2's dead tables (exp 0405, series e7 of exp 0401)

Tag `tl2`. Unit: `src/libs/libs.cpp` only. Files: `mktl20405.py` (the edit), `tl20405.cpp` (the CPU test), this note.

The maintainer's decision 4 of exp 0405 (2026-11-04, "=> B => B"): the 32 tables that KytyPlus compiles but `Libs::InitAll`
never loads are ported first, then loaded, each behind its own switch. Series e6 (tag `tld`, `mktld0405.py`) loaded
batch 1's six tables through the `Bc5Tables` block in libs.cpp. This unit adds batch 2's seventeen CPU-only library
tables to that block. Series e7's port agents port their functions, in the tables' own units, in parallel.

No upstream code is inserted. The block loads this tree's own tables (KytyPlus, GPL-2.0), so there is no project, commit
or licence to cite. No hardware or console fact is stated.

## Verdicts

All seventeen are wired: 17 loaded behind switches, 0 held. There are no per-function verdicts, because this unit only
loads tables and ports no function. Each switch is default off and read once: it is a bit of e6's function-local static
in `Bc5Tables::On`, which is unchanged. Each follows env_flag.hpp's rule: a switch is on when it is set, non-empty and not
"0".

The init functions were checked in the e7 input tree (e6's output). All are in `Libs::`. Every key is
`<name>_v1` / `<name>_v1.1`, from each table's `LIB_VERSION(l, 1, m, 1, 1)`.

| # | Switch | Item | Init function, file:line (e7 input) | Key name | Records |
|---|---|---|---|---|---|
| 7 | `KYTY_BC5_LOAD_NPTUS` | nptus | `NpTus::InitNpTus_1`, libNp.cpp:3146 | NpTus | 142 |
| 8 | `KYTY_BC5_LOAD_NPPARTY` | npparty | `NpParty::InitNpParty_1`, libNp.cpp:1301 | NpParty | 26 |
| 9 | `KYTY_BC5_LOAD_NPPARTNER` | nppartner | `NpPartner::InitNpPartner_1`, libNp.cpp:1158 | NpPartner001 | 4 |
| 10 | `KYTY_BC5_LOAD_NPAUTH` | npauth | `NpAuth::InitNpAuth_1`, libNp.cpp:76 | NpAuth | 5 |
| 11 | `KYTY_BC5_LOAD_NPSNSFACEBOOK` | npsnsfacebook | `NpSnsFacebookDialog::InitNpSnsFacebookDialog_1`, libNp.cpp:1341 | NpSnsFacebookDialog | 1 |
| 12 | `KYTY_BC5_LOAD_VOICE` | voice | `LibVoice::InitVoice_1`, libVoice.cpp:92 | Voice | 14 |
| 13 | `KYTY_BC5_LOAD_SCREENSHOT` | screenshot | `LibScreenShot::InitScreenShot_1`, libScreenShot.cpp:93 | ScreenShot | 14 |
| 14 | `KYTY_BC5_LOAD_DISCMAP` | discmap | `LibDiscMap::InitDiscMap_1`, libDiscMap.cpp:135 | DiscMap | 5 |
| 15 | `KYTY_BC5_LOAD_ULOBJMGR` | ulobjmgr | `LibUlobjmgr::InitUlobjmgr_1`, libUlobjmgr.cpp:120 | ulobjmgr | 4 |
| 16 | `KYTY_BC5_LOAD_COMPANIONHTTPD` | companionhttpd | `CompanionHttpd::InitCompanionHttpd_1`, libCompanion.cpp:211 | CompanionHttpd | 17 |
| 17 | `KYTY_BC5_LOAD_COMPANIONUTIL` | companionutil | `CompanionUtil::InitCompanionUtil_1`, libCompanion.cpp:312 | CompanionUtil | 5 |
| 18 | `KYTY_BC5_LOAD_INVITATIONDIALOG` | invitationdialog | `LibInvitationDialog::InitInvitationDialog_1`, libInvitationDialog.cpp:170 | InvitationDialog | 9 |
| 19 | `KYTY_BC5_LOAD_WEBBROWSERDIALOG` | webbrowserdialog | `LibWebBrowserDialog::InitWebBrowserDialog_1`, libWebBrowserDialog.cpp:225 | WebBrowserDialog | 12 |
| 20 | `KYTY_BC5_LOAD_SHAREPLAY` | shareplay | `LibSharePlay::InitSharePlay_1`, libSharePlay.cpp:132 | SharePlay | 22 |
| 21 | `KYTY_BC5_LOAD_GAMELIVESTREAMING` | gamelivestreaming | `LibGameLiveStreaming::InitGameLiveStreaming_1`, libGameLiveStreaming.cpp:735 | GameLiveStreaming | 45 |
| 22 | `KYTY_BC5_LOAD_REMOTEPLAY` | remoteplay | `LibRemotePlay::InitRemotePlay_1`, libRemotePlay.cpp:217 | Remoteplay | 39 |
| 23 | `KYTY_BC5_LOAD_VIDEORECORDING` | videorecording | `LibVideoRecording::InitVideoRecording_1`, libVideoRecording.cpp:75 | VideoRecording | 1 |

- `#` is the row's index in `TABLES` (1-based). Batch 1's six are rows 1-6.
- The record counts are for the input tree, 365 in total. The ports may change them; the test counts them at run time.
- Live namespaces with similar names stay as they are: `LibVoice::InitAudio_1_Voice` (libAudio.cpp), and libNet.cpp's
  `LibWebBrowserDialog`/`LibGameLiveStreaming`/`LibSharePlay` `InitPlatform_1_*` and `LibRemoteplay` (a lower-case p).
  No other declaration of the seventeen names exists in the tree.
- The emulator's `file(GLOB kyty_emulator_src ... libs/*.cpp)` (src/CMakeLists.txt:191) already compiles every unit
  named here, so the new references link.

**Journal line.** It is e6's code, unchanged, and is printed once at the first InitAll. It lists only the items that are
on, in `TABLES` order (batch 1's first):
- `[bc5] exp 0405: tables on (items: nptus,npparty,...,videorecording)`;
- or `[bc5] exp 0405: tables off`.

With all seventeen unset, the line and InitAll's record list are e6's byte for byte (checked below).

## What changed

Input `src/libs/libs.cpp` (md5 903fa699db7c20b2b3f288ab572bce8d, 370 lines, LF) becomes the output (md5
aa8f39d19b563da518b14502941c7386, 466 lines, LF). There are three insertions; no input line changes.

- **Output :138-163:** a comment that names batch 2, its order, the rule and the guard.
- **Output :164-214:** the seventeen `LIB_DEFINE` declarations, each in its own namespace, after batch 1's.
- **Output :232-249:** one comment line, then the seventeen rows of `TABLES`, after batch 1's `nptrophy` row.
- **Output :253:** `static_assert(TABLE_COUNT == 23)`. e6's `<= 32` assert stays, and `1u << i` covers 23 bits.

`Table`, `On()`, `LoadSwitched()` and `InitAll` stay byte for byte; the script asserts this. InitAll still starts with
`Bc5Tables::LoadSwitched(s);` (output :293), then today's 42 `LIB_LOAD`s (:294-335).

**Load order.** Batch 1's six load first, then batch 2's seventeen in the order above, then every live table. The
reasons are in tld0405-notes.md ("Load order"): `Add` uses `insert_or_assign`, so the newest record wins for `Find`, and
`FindByNid` returns the first record.

## Test: tl20405.cpp

It follows tld0405.cpp's design. Build: `--gate tl20405.cpp <out> --like src/libs/libs.cpp`. It is linked with every
emulator object except main.cpp.o, with series e7's private units in place, the ports of these tables among them.

**Runs.** Each run uses a fresh directory, with batch 1's six switches unset:
- `tl20405 on` with all seventeen `=1`;
- `tl20405 off` with all seventeen `=0`;
- `tl20405 off` with all seventeen unset;
- `tl20405 mixed` is accepted for other mixes.

The test refuses a mismatched argument, or any of batch 1's six that is on, with a usage line and exit 2. Batch 1's six
set to "0" or empty are off, and the test accepts them. A watchdog runs for 120 s, then prints a FAIL line and exits 3.
The test exits 0 only after `tl20405: on|off|mixed 20 of 20; end`.

**Databases built:**
- InitAll's database, twice;
- each of the 23 switched tables' own databases (its init function into a fresh `SymbolDatabase`);
- today's InitAll, a copy of the input libs.cpp:198-239, call for call.

Records are listed through `DbgDump` into `./tl20405-dump/` and parsed back through `GenerateName`, as tld does. Every
count comes from these lists at run time, so the test does not depend on the port agents' edits.

**Cases (20 on, 20 off):**
1. **The switches' line.** `./tl20405-stderr.txt` must hold exactly one `[bc5] exp 0405: tables` line over two InitAll
   calls, and it must be the expected one.
2. **InitAll's record list:**
   - off: it equals today's list, record for record (address and name);
   - on: it is the switched tables' own lists in load order, then today's.
3. **Read once.** All 23 switches are flipped, then restored before the own databases are built. The second InitAll
   must give the same list.
4. **Cases 4-20, one per table.** Each line prints the table's NIDs and key shape, then:
   - on: new, kept live, and NID-only lookups that move;
   - off: keys not registered, and NIDs that resolve to nothing.

   `FindByNid` is checked against the first record with that NID in the expected list.

   **Guard (on and off), which FAILs the case:**
   - a key of the table that today's InitAll registers (`Find` in today's database);
   - a NID+type of the table that today's InitAll registers under any key (`FindByNid`);
   - a key or NID+type that another switched table registers (the other sixteen, or batch 1's six).

   So kept live and moved must both be 0.

**Expected values.** Today's off path is this: e6's `LoadSwitched` loads nothing when every switch is off, and the line
is `tables off`. Neither changed, which is asserted by the script and shown by the identical tld runs below.

### Laptop stand-in run (scratch `scratchpad/e7/tl2/standin`)

The build uses VS 18 clang++ 22 (msvc target) and lld. It links:
- the real `tl20405.cpp` and the real output libs.cpp;
- the real `symbolDatabase.cpp`;
- the e7 input's real units of all 23 tables: libNp, libZlib, libJpeg and libIme (e6's ports), and libVoice,
  libScreenShot, libDiscMap, libUlobjmgr, libCompanion, libInvitationDialog, libWebBrowserDialog, libSharePlay,
  libGameLiveStreaming, libRemotePlay and libVideoRecording;
- zlib's C files (refs/Coder787-source_KytyPlus/3rdparty/zlib) and fmt;
- `standin.cpp`, a copy of tld's fake live tables, with the same live Ime and NpManager keys and a Zlib NID under another
  key;
- `standin_np.cpp`, which supplies never-called bodies for the ports' callees: libKernel pthreads, the clock and
  `GetRealFilename`, network.cpp's NpManager, and `Ime::GetHostSnapshot`.

| Run | Result |
|---|---|
| All seventeen `=1` | `on 20 of 20; end`. 425 records: the switched 365 first (nptus 142 ... videorecording 1), then today's 60. Every table: all new, 0 kept live, 0 moved, guard 0. |
| All `=0` / unset | `off 20 of 20; end` (60 records, equal to today's) |
| nptus=1, voice=yes, discmap= (empty), videorecording=0, remoteplay=1 | `mixed 20 of 20; end` (line `items: nptus,voice,remoteplay`) |
| Batch 1's ime=0 and zlib= (empty), seventeen unset | `off 20 of 20; end` |
| A mismatched argument; batch 1's ime=1 | exit 2 (usage) |

**Negative controls** (each `FAIL` with exit 1):
- **e6's unedited libs.cpp:** `on 1 of 20 passed`. Cases 1, 2 and 4-20 FAIL; only "read once" passes. `mixed 15 of 20
  passed`. The `off` runs pass, as they should, because e6 equals off.
- **`-DTL2_NEG_SHARED`:** a live table that registers one NpTus key, plus one NpAuth NID under another key. Cases nptus
  and npauth FAIL (guard: live key / live NID) in on, off, unset and mixed (`18 of 20 passed`).
- **A copy of libDiscMap.cpp that also registers VideoRecording's NID `Fc8qxlKINYQ`:** cases discmap and videorecording
  FAIL (guard: another switched table), in all four modes (`18 of 20`).

**e6's tld0405.cpp, unchanged** (md5 02ae1902c6ae557e9c9be06e4fb2fc95), built twice in the same stand-in: once with this
output and once with e6's libs.cpp. Only its six switches were set:

| Run | This libs.cpp | e6's libs.cpp |
|---|---|---|
| Six `=1` | `on 9 of 9; end` | `on 9 of 9; end` |
| Six `=0` / unset | `off 9 of 9; end` | `off 9 of 9; end` |
| ime=1, nptrophy=yes, zlib= | `mixed 9 of 9; end` | `mixed 9 of 9; end` |

For every run, the two builds gave:
- byte-identical stdout;
- a byte-identical `tld0405-stderr.txt` (`tables on (items: zlib,jpeg,ime,npcommon,npmanager,nptrophy)`, `tables off`,
  `tables on (items: ime,nptrophy)`);
- identical record-name lists for `initall`, `initall-again` and `today` (250 / 60 / 60 / 188 records).

**Syntax.** VS clang++ 22 with `-fsyntax-only -std=c++20 -Wall -Wextra -Werror`, also with
`-Wshadow -Wconversion -Wsign-conversion`. It used the stand-in `cmake_config.h`, fmt from refs/Inori_GPCS4 and magic_enum
from refs/InoriRus_Kyty. The input libs.cpp, the output and tl20405.cpp are clean. A negative control (an unused variable
put into the output) is caught.

**Script checks:**
- It applies to the e7 input tree and prints `src/libs/libs.cpp aa8f39d19b563da518b14502941c7386`.
- It refuses its own output (mark `tag "tl2"`), a changed input (md5), and the base tree's pre-e6 libs.cpp (md5).
- Deleting output lines 138-214, 232-249 and 253 gives back md5 903fa699 (independently of the script's own undo check).
- `diff` shows only insertions.
- Braces, parentheses and brackets balance (0, 0, 0).
- The file is ASCII, with no CR.

## Recheck: shared keys and NIDs (e7 input tree)

This used tld's static map (`scratchpad/e6/tld/tables.py`). The tl2 copy in `scratchpad/e7/tl2/tables.py` only drops
the call `Bc5Tables::LoadSwitched`, which the original cannot resolve.

**Live set:** 1996 records, 1981 keys and 110 init functions. There are still 32 dead roots.

**For the seventeen:**
- 0 keys are shared with a live table;
- 0 NID+types are shared with a live table under any key;
- 0 keys or NIDs are shared between any two dead tables (1225 dead records).

So risk 1 of tld0405-notes.md (NID-only lookups moving to a switched table) does not arise for batch 2. The test's guard
keeps it that way: it fails on the box if a port adds such a registration.

## Split state (risk 2)

Six of the seventeen tables have live records with the same library key. These are live functions of the same library,
served by another implementation:

| Table | Live records, same library | Live table |
|---|---|---|
| voice | 16 | `LibVoice::InitAudio_1_Voice` (libAudio.cpp) |
| npauth | 8 | `LibNpAuth::InitNet_1_NpAuth` (libNet.cpp) |
| remoteplay | 3 | `LibRemoteplay::InitPlatform_1_Remoteplay` (libNet.cpp) |
| gamelivestreaming | 2 | `LibGameLiveStreaming::InitPlatform_1_GameLiveStreaming` (libNet.cpp) |
| shareplay | 2 | `LibSharePlay::InitPlatform_1_SharePlay` (libNet.cpp) |
| webbrowserdialog | 2 | `LibWebBrowserDialog::InitPlatform_1_WebBrowserDialog` (libNet.cpp) |

The other eleven have 0. Because no key is shared, the live functions keep every key they have, with the switch on or
off. With a switch on, a title's imports of one library are therefore served by two units. One example is
`sceGameLiveStreamingInitialize` (live) beside the switched table's other functions.

Whether a ported function depends on state the live side sets is a question for the port agents' notes. This unit adds no
state: the loader only calls the init functions, which register functions.

## Risks

1. **Port agents' registrations.** If a port adds a key or NID that a live table or another switched table registers,
   tl20405 FAILs on the box (the guard). The fix belongs in that port, not here.
2. **Twice-called init functions.** The test calls each switched init a second time for its own list; batch 1's six are
   called once, for the guard. The tbn/tbc convention prints the port line once, at `LIB_DEFINE`. If a port adds state to
   an init function, that state must be idempotent (tld risk 3).
3. **Copy of today's InitAll in the test** (tld risk 4). If a later series changes InitAll's calls, case 2 fails by design.
4. **The order between the batches** with both on (batch 1, then batch 2) is asserted by the script, not run by a test.
   tld0405 runs with batch 2 off, and tl20405 runs with batch 1 off. No key or NID is shared between the batches (static
   map, plus the guard), so the order cannot change any lookup today.
5. **`static_assert(TABLE_COUNT == 23)`.** A later batch must update it, on purpose.
6. **DbgDump's file I/O** needs a writable fresh directory (tld risk 5).

## Not checked / held

- **Not checked on the laptop:** GCC or Linux clang on the box, the real link with every emulator object, the real live
  tables, and the port agents' versions of the seventeen units (they work in parallel). The stand-in used the e7 input's
  units. The box build is the first real compile and run.
- **Held:** nothing of the seventeen. The other nine dead tables are not in this batch, as the brief says. They are Camera
  76, Usbd 65, Hmd 137, Ngs2 40, Move 11, RazorCpu 34, VrTracker 39, GnmDriver 251 and RageEngine 15 records: 668 in total
  (tld0405-notes.md, the same counts in the e7 input).

## Files

| File | md5 |
|---|---|
| input `src/libs/libs.cpp` (e7 input = e6 output, LF) | 903fa699db7c20b2b3f288ab572bce8d |
| output `src/libs/libs.cpp` | aa8f39d19b563da518b14502941c7386 |
| `mktl20405.py` | f2b12e1dea693e9f39a28842cb8d76d2 |
| `tl20405.cpp` | 93a3acbc2a657f7b287b1de6c29ff5f8 |
| read only: `tld0405.cpp` (e6, run unchanged) | 02ae1902c6ae557e9c9be06e4fb2fc95 |
| read only: `src/loader/symbolDatabase.cpp` / `.h` | 2782bc19962a8e92db1ad35c7fc440e6 / b0e0ccdaab9d96c1d7e9fe93dfd64102 |
| read only, e7 input: libNp.cpp, libVoice, libScreenShot, libDiscMap, libUlobjmgr, libCompanion | 24e778261495abcd5a069396f14b28b4, 5f63709dbf1028ceaf7784d6a070f64e, cb913d120daa27f0d35702edeee71b19, e4d975b8a55da8aed19281d7c6d17b33, b85eafd0de28af091302a8aeeeb323c1, cf8ad7a647a84ba04964eb0adfe2ab02 |
| read only, e7 input: libInvitationDialog, libWebBrowserDialog, libSharePlay, libGameLiveStreaming, libRemotePlay, libVideoRecording | 204a5daeebb100a131c034edb8e58e87, af36a12a0bc234f83e5c85a76d4b283d, d6ecb7874b00ee29d9275d78d8087191, 59e46b5d8452101a0f57257703cfa3a4, abfde0e8bb446bc6870aa5df08cfb5fa, e8f90a3574dcae417df52f1802515f4d |
