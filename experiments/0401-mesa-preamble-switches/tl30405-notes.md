# tl3: loading batch 2's hardware tables (exp 0405, series e7 of exp 0401)

Tag `tl3`. Unit: `src/libs/libs.cpp` only. Files: `mktl30405.py` (the edit), `tl30405.cpp` (the CPU test), this note.

The maintainer's decision 4 of exp 0405 (2026-11-04, "=> B => B"): the 32 tables that KytyPlus compiles but `Libs::InitAll`
never loads are ported first, then loaded, each behind its own switch. Series e6 (`tld`) put batch 1's six into the
`Bc5Tables` block of libs.cpp; `tl2` added batch 2's library tables (second version: fourteen). This unit adds batch 2's
hardware group, five tables, after every earlier row. Their functions are ported by the port agents tcm, thv and tus in
the tables' own units, in parallel.

No upstream code is inserted: the block loads this tree's own tables (KytyPlus, GPL-2.0), so there is no project, commit
or licence to cite. No hardware or console fact is stated. Loading only registers functions: nothing here opens a
device (camera, USB, HMD); what a loaded function does is the port agents' code.

## Verdicts

All five are wired: 5 loaded behind switches, 0 held. There are no per-function verdicts: this unit loads tables and
ports no function. Each switch is default off and read once (a bit of e6's function-local static in `Bc5Tables::On`,
unchanged) and follows env_flag.hpp's rule (on = set, non-empty and not "0").

Init functions, checked in the e7 input tree (`e6tree`); all in `Libs::`; every `LIB_VERSION` is `("libSce<X>", 1,
"libSce<X>", 1, 1)`, so every key is `<nid>[<X>_v1][<X>_v1.1][Func]`:

| # | Switch | Item | Init function, file:line (e7 input) | Key name | Records (input) |
|---|---|---|---|---|---|
| 21 | `KYTY_BC5_LOAD_CAMERA` | camera | `LibCamera::InitCamera_1`, libCamera.cpp:402 | Camera | 76 |
| 22 | `KYTY_BC5_LOAD_USBD` | usbd | `LibUsbd::InitUsbd_1`, libUsbd.cpp:1035 | Usbd | 65 |
| 23 | `KYTY_BC5_LOAD_HMD` | hmd | `LibHmd::InitHmd_1`, libHmd.cpp:707 | Hmd | 137 |
| 24 | `KYTY_BC5_LOAD_VRTRACKER` | vrtracker | `LibVrTracker::InitVrTracker_1`, libVrTracker.cpp:645 | VrTracker | 39 |
| 25 | `KYTY_BC5_LOAD_MOVE` | move | `LibMove::InitMove_1`, libMove.cpp:77 | Move | 11 |

- `#` is the row's index in `TABLES` (1-based): batch 1 is 1-6, tl2's rows 7-20. 25 of the 32 bits of `On()` are used.
- Records: 328 in the input. With a switch on, the ports register only their ported functions (series e7's rule: held
  stubs are not registered), so the loaded counts will be lower; the test counts at run time.
- No other declaration of the five namespaces or init functions exists in the tree (grep of `src/`), and no other
  `LIB_VERSION`/`LIB_NAME` names these libraries. `src/CMakeLists.txt:191` globs `libs/*.cpp`, so the five units are
  already compiled and the new references link.

**Journal line.** e6's code, unchanged, printed once at the first InitAll; it lists the items that are on, in `TABLES`
order, these five last: `[bc5] exp 0405: tables on (items: ...,camera,usbd,hmd,vrtracker,move)` or
`[bc5] exp 0405: tables off`. With the five unset, the line and InitAll's record list are the input's byte for byte
(the earlier rows keep their bits; checked below with tld0405 and tl20405).

## What changed

Input `src/libs/libs.cpp` = tl2's second output (md5 3ba4e3cd08d88a6d063d34a5e9cd813b, 454 lines, LF) becomes the output
(md5 0728ab027534903ab50cbda93945b9dd, 492 lines, LF):
- **Output :206-237** (inserted): a comment (the five, the order, the rule, the guard), then the five `LIB_DEFINE`
  declarations, each in its own namespace, after tl2's last (`} // namespace LibGameLiveStreaming`).
- **Output :270-275** (inserted): one comment line and the five rows, after tl2's `gamelivestreaming` row.
- **Output :279** (the one replaced line): `static_assert(TABLE_COUNT == 20); ...(tl2)...` becomes
  `static_assert(TABLE_COUNT == 25); // BC5 experiment 0405 (tl3): batch 1's 6, batch 2's 14, its hardware group's 5`.
  A second assert could not be added beside tl2's (20 and 25 contradict). e6's `<= 32` assert stays.

`Table`, `On()`, `LoadSwitched()`, `InitAll` and every earlier row stay byte for byte (asserted); InitAll still starts
with `Bc5Tables::LoadSwitched(s);` (output :319), then today's 42 `LIB_LOAD`s.

**Anchors that do not name a batch-2 row** (the coordinator's change of 2026-11-04): the declarations go right before the
blank line before `namespace Bc5Tables {`, the rows right before `TABLES`' closing `};` (followed by the `TABLE_COUNT`
definition), and the count line is found by pattern (`static_assert(TABLE_COUNT == N);`, N checked against the input's
row count, raised by 5). The script asserts that the declaration anchor follows a declaration, that the rows anchor follows
the input's last row, that batch 1's six are the first rows, and that every row's declaration is present. So it applies to
any tl2 output; only `PINNED` changes. Checked: re-pinned in scratch to tl2's first output (aa8f39d1..., 23 rows) it gives
md5 1e606509cbee3f672eecaa42d4e3d388 with `TABLE_COUNT == 28` (that version's test would also need tl2's three rows back
in `kEarlier`).

**Load order.** Batch 1, then tl2's fourteen, then these five, then every live table (tld0405-notes.md "Load order":
`Add` uses `insert_or_assign`, so the newest record wins for `Find`; `FindByNid` returns the first record).

## Test: tl30405.cpp

tl20405.cpp's design for the five. Build: `--gate tl30405.cpp <out> --like src/libs/libs.cpp`, linked with every emulator
object except main.cpp.o, series e7's private units in place (the ports of these tables among them).

**Runs** (fresh directory each): `tl30405 on` (all five `=1`), `tl30405 off` (all `=0`, or all unset), `tl30405 mixed`
(other mixes). Every earlier switch must be off: the 20 earlier rows of `TABLES` (`kEarlier`) and tl2's three retired
switches (`KYTY_BC5_LOAD_NPAUTH`, now read by libNet.cpp's live NpAuth table, `_REMOTEPLAY`, `_VIDEORECORDING`), so today's
InitAll is the same in every run. Otherwise, or with a mismatched argument: a usage line, exit 2. "0" or empty counts as
off. Watchdog 120 s (FAIL line, exit 3). Exit 0 only after `tl30405: on|off|mixed 8 of 8; end`.

**Databases:** InitAll's, twice; each of the five tables' own (its init into a fresh `SymbolDatabase`); each of the 20
earlier tables' own (for the guard); today's InitAll (a copy of the input's 42 calls; my scratch check asserts the copy
equals the input's InitAll call for call and `kEarlier` equals the input's rows). Records are listed through `DbgDump`
into `./tl30405-dump/` and parsed back through `GenerateName`, as tld does.

**Cases (8 on, 8 off):**
1. **The switches' line:** exactly one `[bc5] exp 0405: tables` line over two InitAll calls, the expected one.
2. **InitAll's record list:** off: equal to today's, record for record (address and name); on: the five tables' own
   lists (those on) in load order, then today's.
3. **Read once:** all 25 switches of `TABLES` flipped, then restored before the own databases are built; the second
   InitAll must give the same list.
4. **Cases 4-8, one per table** (camera, usbd, hmd, vrtracker, move): its NIDs and key shape, then on: new, kept live,
   NID-only lookups moved; off: keys not registered, NIDs that resolve to nothing. **Guard (on and off), FAILs the case:**
   a key or NID+type of the table that today's InitAll registers (`Find` / `FindByNid` in today's database), or that
   another switched table registers (the other four, or any of the 20 earlier). A table that registers nothing FAILs too
   (a port that holds every function of a table, with its switch on: drop the row, as tl2 did for remoteplay).

**Expected values.** Today's off path: `LoadSwitched` loads nothing for an off bit, and the line is `tables off` when all
are off (e6's code, unchanged, asserted). With the five off the earlier rows' bits and items are the input's.

### Laptop stand-in run (scratch `scratchpad/e7/tl3/standin`)

VS 18 clang++ 22 (msvc target) and lld. A copy of tl2's stand-in: the real `tl30405.cpp`, the real output libs.cpp, the
real `symbolDatabase.cpp`, the e7 input's real units of all 25 switched tables (tl2's prebuilt objects plus libCamera,
libUsbd, libHmd, libVrTracker, libMove), zlib and fmt, tld's fake live tables (`standin.cpp`) and `standin_np.cpp`.

| Run | Result |
|---|---|
| All five `=1` | `on 8 of 8; end`. 388 records: the switched 328 first (camera 76, usbd 65, hmd 137, vrtracker 39, move 11), then today's 60. Every table: all new, 0 kept live, 0 moved, guard 0. |
| All `=0` / unset | `off 8 of 8; end` (60 records, equal to today's) |
| camera=1, usbd= (empty), hmd=yes, vrtracker=0 | `mixed 8 of 8; end` (line `items: camera,hmd`) |
| ime=0, zlib= (empty), gamelivestreaming=0, remoteplay= (empty); five unset | `off 8 of 8; end` |
| A mismatched argument; nptus=1; npauth=1 | exit 2 (usage) |

**Negative controls** (each `FAIL`, exit 1):
- **tl2's output (the unedited input) as libs.cpp:** `on 1 of 8 passed` (cases 1, 2 and 4-8 FAIL; read once passes),
  `mixed 4 of 8 passed`; `off` passes, as it should (the input equals off).
- **`-DTL3_NEG_SHARED`** (stand-in): a live table that registers one Camera key (`QhjrPkRPUZQ`) and one Move NID
  (`j1ITE-EoJmE`) under another key. Cases camera and move FAIL (guard: live key / live NID) in on, off (=0), unset and
  mixed (`6 of 8 passed`).
- **A copy of libMove.cpp that also registers Usbd's NID `0ktE1PhzGFU`:** cases usbd and move FAIL (guard: another
  switched table), in all four modes (`6 of 8 passed`).

**tld0405.cpp and tl20405.cpp, unchanged** (snapshots, md5 below), each built twice in the same stand-in: with this
output and with the input (tl2's second output). Only their own switches set:

| Run | This output | The input (tl2's) |
|---|---|---|
| tld0405: six `=1` / `=0` / unset / ime=1, nptrophy=yes, zlib= | `on 9 of 9` / `off 9 of 9` / `off 9 of 9` / `mixed 9 of 9` | the same |
| tl20405: fourteen `=1` / `=0` / unset / nptus=1, voice=yes, discmap=, gamelivestreaming=0 | `on 17 of 17` / `off 17 of 17` / `off 17 of 17` / `mixed 17 of 17` | the same |

For all eight run pairs the two builds gave byte-identical stdout, a byte-identical `*-stderr.txt` (`tables on (items:
zlib,jpeg,ime,npcommon,npmanager,nptrophy)`, `tables off`, `tables on (items: ime,nptrophy)`; `tables on (items:
nptus,...,gamelivestreaming)`, `tables off`, `tables on (items: nptus,voice)`), and the same record names in every dump
(addresses differ by build): tld `initall` 250 / 60 / 60 / 188, tl20405 `initall` 380 / 60 / 60 / 216, `today` 60.
Script: `scratchpad/e7/tl3/standin/run_earlier.sh`.

**Syntax.** VS clang++ 22, `-fsyntax-only -std=c++20 -Wall -Wextra -Werror -Wshadow -Wconversion -Wsign-conversion`
(stand-in `cmake_config.h`, fmt from refs/Inori_GPCS4, magic_enum from refs/InoriRus_Kyty): the input libs.cpp, the output
and tl30405.cpp are clean; the stand-in build compiles tl30405.cpp with `-Wall -Wextra -Werror`.

**Script checks:**
- Applies to the e7 input chain (tl2's output) and prints `src/libs/libs.cpp 0728ab027534903ab50cbda93945b9dd`; the same
  output twice.
- Refuses its own output (mark `tag "tl3"`, also through the re-pinned copy), a changed input (md5), e6's libs.cpp (md5;
  and `edit_unit` itself refuses it: one `static_assert(TABLE_COUNT`, no tl2 rows) and tl2's first output (md5).
- An independent undo (a line diff: two insertions and one replaced line; drop the inserted lines, put the count line
  back) gives md5 3ba4e3cd back; the script's own undo asserts the same.
- Outside the `Bc5Tables` block the output is the input's byte for byte (asserted).
- Braces, parentheses and brackets balance (0, 0, 0); ASCII; no CR. No inserted line is over 120 columns.

## Recheck: shared keys and NIDs (e7 input tree)

tl2's static map (`scratchpad/e7/tl2/tables3.py`), copied as `scratchpad/e7/tl3/tables_tl3.py` with a tail for the five:
live set 1996 records, 1981 keys, 110 init functions; 32 dead roots, 1225 dead records. For each of the five: 0 keys and
0 NID+types shared with a live table (under any key), 0 keys and 0 NID+types shared with any other dead table (all 31,
not only the loaded ones). So no NID-only lookup moves (tld risk 1 does not arise), and the test's guard keeps it so: it
fails on the box if a port adds such a registration.

## Split state (risk 2)

None. No live table registers any key with these five libraries' names (`[Camera_v1]`, `[Usbd_v1]`, `[Hmd_v1]`,
`[VrTracker_v1]`, `[Move_v1]`; the static map's "live same library" is empty for all five), and no other unit declares
their namespaces. So no live function of these libraries exists whose state a port could depend on; with a switch on, a
title's imports of the library are served by the one unit. (Other live libraries that may touch the same devices, such
as libPad for a Move controller, are separate libraries with separate keys; not this unit's question.) This unit adds no
state.

## Risks

1. **Port agents' registrations.** A port that adds a key or NID a live table or another switched table registers makes
   tl30405 FAIL on the box (the guard); the fix belongs in that port.
2. **A table with every function held** registers nothing with its switch on (series e7's rule): its case FAILs by design;
   the row should then go (as tl2 dropped remoteplay). The sweep has logic rows for all five (camera 44 logic + 10 const,
   usbd 61, hmd 11 + 6 const, vrtracker 10, move 11), so this is not expected.
3. **Init functions called more than once** (InitAll twice and the own list): a port that adds state to an init must keep
   it idempotent (tld risk 3). A port that reads its switch each time instead of once FAILs case 3.
4. **Copies in the test**: today's InitAll (tld risk 4) and `kEarlier` (tl2's rows). If tl2's rows change again, `kEarlier`
   and its declarations change with them (and `PINNED` in the script); nothing else.
5. **Order between batches with several on** is asserted by the script (append only), not run: tld0405 runs with batch 2
   and these off, tl20405 with batch 1 and these off, tl30405 with all earlier off. No key or NID is shared (static map
   and guards), so the order cannot change a lookup today.
6. **`static_assert(TABLE_COUNT == 25)`**: a later batch must raise it on purpose; 7 bits are left.
7. **DbgDump's file I/O** needs a writable fresh directory (tld risk 5).

## Not checked / held

- **Not checked on the laptop:** GCC or Linux clang on the box, the real link with every emulator object, the real live
  tables, and the port agents' versions of the five units (they work in parallel; the stand-in used the e7 input's). The
  box build is the first real compile and run.
- **Held:** nothing of the five. Still dead and not in this round: Ngs2 40, RazorCpu 34, GnmDriver 251, RageEngine 15
  records (340), plus tl2's dropped remoteplay 39 and videorecording 1 (npauth moved into libNet.cpp's live table).

## Files

| File | md5 |
|---|---|
| input `src/libs/libs.cpp` (tl2's second output, LF) | 3ba4e3cd08d88a6d063d34a5e9cd813b |
| output `src/libs/libs.cpp` | 0728ab027534903ab50cbda93945b9dd |
| `mktl30405.py` | 13dc8e64092495ea3970547c7fe8d101 |
| `tl30405.cpp` | c5c4c7820d2899352b2d3fbe7936fd09 |
| read only: `tld0405.cpp` / `tl20405.cpp` (tl2's second version), run unchanged | 02ae1902c6ae557e9c9be06e4fb2fc95 / 4c2ea887630220fc03ef7a685b30b99d |
| read only: `src/loader/symbolDatabase.cpp` / `.h` | 2782bc19962a8e92db1ad35c7fc440e6 / b0e0ccdaab9d96c1d7e9fe93dfd64102 |
| read only, e7 input: libCamera, libUsbd, libHmd, libVrTracker, libMove | 810fada1b7e1d223502ace667b71eb14, f15039f248f156341d68cb3cb58a2b0f, 905036478f8f9336090248a532d0469f, ee30491baadb582db2df7a08cadc4ae9, 90b0765d8d601d7e7189e0b5064d180f |
| scratch (not deliverables): `scratchpad/e7/tl3/` `check_tl3.py`, `tables_tl3.py`, `standin/` (`build.sh`, `run.sh`, `build_all.sh`, `run_earlier.sh`, `mk_standin_tl3.py`, `mk_neg_move.py`) | |
