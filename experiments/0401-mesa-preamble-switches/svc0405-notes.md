# svc0405: SaveData memory, Http2 async events and scePadOpenExt (exp 0401 series e5, port group "svc")

Written 2026-11-04 on the laptop, with no box access and no git writes. Inputs are the e5 input tree (KytyPlus f266548 + patch 0001 + e4's private units) and exp 0405's specs (README top-32 rows 19-22; `raw/r2-kyty-sharpemu.md` §4.1 rows 10, 11, 15, 16, 23, 28, 29 and §5; `raw/r1-anyps5.md` rows 15 and 18).

Deliverables, all new: `mksvc0405.py` (the edit), `svc0405.cpp` (the CPU test) and this file.

## Switches and journal lines

Each switch is read once, defaults off, and prints one stderr line at its library's registration. Off (unset, empty or `0`) takes today's path: the old code is kept and branched on the switch. A comma-list switch with a value that names none of its items (for example `1`) turns all of its items on.

| Switch | Items | Unit | Line |
|---|---|---|---|
| `KYTY_BC5_SAVEDATA_MEMORY_FIXES` | `sync`, `lock`, `existed` | libSaveData.cpp | `[bc5] exp 0405: savedata memory fixes on (items: sync lock existed)` / `... off` |
| `KYTY_BC5_SAVEDATA_DELETE_BUSY` | (delete) | libSaveData.cpp | `[bc5] exp 0405: savedata delete busy on (items: delete)` / `... off` |
| `KYTY_BC5_SAVEDATA_ALIASES` | (initialize) | libSaveData.cpp | `[bc5] exp 0405: savedata aliases on (items: initialize)` / `... off` |
| `KYTY_BC5_HTTP2_FIXES` | `async`, `ssl`, `agent` | libNet.cpp | `[bc5] exp 0405: http2 fixes on (items: async ssl agent)` / `... off` |
| `KYTY_BC5_PAD_OPEN_EXT` | (openext) | libPad.cpp | `[bc5] exp 0405: pad open ext on (items: openext)` / `... off` |

The items are listed with spaces, not commas, inside the parentheses.

## Items

### 1. R2 KS03 + SS01 + KS02: sync never posts MEMORY_SYNC_END; the queue has no lock (top-32 row 19)

**Verdict: ported**, as items `sync` and `lock`.

**Sources.**
- KytyPS5 dfec14a (GPL-2.0) `src/libs/libSaveData.cpp`:
  - 197-202, the `SaveDataMemorySync` layout;
  - 267, the value MEMORY_SYNC_END = 3;
  - 1151-1182, `SaveDataSyncSaveDataMemory`;
  - 1027-1028, 1191 and 1275-1276, the queue taken under a lock.
- sharpemu (GPL-2.0-or-later) `SharpEmu.Libs/SaveData/SaveDataExports.cs`, read at 514d766 (added in 9415395): line 78 and lines 1571-1609.
- shadPS4 60c42b9 (GPL-2.0-or-later) `src/core/libraries/save_data/savedata.cpp:1637-1665` and `save_backup.h:26`.

**Changes** (output libSaveData.cpp):
- The switch block, constants and per-slot state: 269-394.
- `sync`, the call: 1545-1596. It checks its arguments:
  - PARAMETER for a null argument, slot ≥ 4 or option > 1;
  - INVALID_LOGIN_USER for a user below 0;
  - MEMORY_NOT_READY for a slot that no `SetupSaveDataMemory2` set up (the setup is recorded at 1234-1236).

  It then writes the memory file through `save_data_memory_store`. That function now returns whether it wrote (1180, 1189, 1196, 1199); its old caller ignores the value. Unless option is 1, the call queues a type-3 event with the user, the title, `sce_sdmemory` or `sce_sdmemory<N>`, and the write's status as the error code.
- `lock`: e4's queue lock is also taken with this item on (471-474), and so is today's `Terminate` clearing (930). e4's delivery to a callback is now gated on the event-callback switch itself (646), so `lock` alone never runs e4's callback code.

**Fitted to this file.**
- This file keeps one memory store for every slot, so "set up" is tracked per slot 0-3, as KytyPS5 and shadPS4 track it.
- KytyPS5's BUSY for a memory directory mounted through Mount3 is not taken: this file never mounts that directory.

**Risks.**
- A title that calls Sync and polls for any other event now also sees a type-3 event. The console does the same, per all three sources.
- Sync now rewrites `memory.dat`, which today only Set does. After a Setup with no Set, the file is the zero-filled memory. shadPS4 and sharpemu create that file at Setup already.

### 2. R2 KS09 + SS02: existed_memory_size (top-32 row 20)

**Verdict: ported**, as item `existed`.

**Sources.**
- KytyPS5 dfec14a `libs/libSaveData.cpp:457-483` (`load_memory`) and 811-825.
- sharpemu `SaveDataExports.cs:1495-1551` at 514d766 (added in 488b285); the file's length is read at 1525-1526.
- shadPS4 `savedata.cpp:1580-1603`, where 0 means "just created".

**Change.** `existed_memory_size` is the size of `memory.dat` before the call, 0 when there is none (output 1202-1209 and 1227-1244). Today it is the memory's size, which is at least 0x10000. With the item off the file is not even looked at.

**Risk.** A title on a later run that never called Set before also sees 0, and initialises its memory again. That is better than reading zeros as a save.

### 3. R2 KS01: Http2 async calls never trigger the caller's equeue (top-32 row 21)

**Verdict: ported**, as item `async`.

**Source.** KytyPS5 a06e356 "net: signal the event queue when Http2 async calls complete" (GPL-2.0), as at dfec14a `src/libs/libNet.cpp`:
- 837-845, the argument;
- 1259-1264, the trigger;
- 1266-1288, `SendRequestAsync`;
- 1436-1473, `ReadDataAsync`.

**Changes** (output libNet.cpp):
- The argument struct and the trigger: 753-773. The trigger is the kernel's existing `LibKernel::EventQueue::KernelTriggerUserEvent`; `eventQueue.cpp` is not touched.
- `kqueue_option` is now named in both calls (1260, 1430).
- The trigger runs after `SendRequestAsync` (1279), after `ReadDataAsync`'s failed-send path (1449), and at its end (1465).

**TODO(verify).** The argument layout `{equeue, int id, pad, udata, reserved}` (32 bytes) is KytyPS5's. No console source is cited for it.

### 4. R2 SS22 + KS69: scePadOpenExt missing (top-32 row 22)

**Verdict: ported**, as switch `KYTY_BC5_PAD_OPEN_EXT`.

**Source.** sharpemu `Pad/PadExports.cs:91-96` and `PadOpenCore` 132-180, read at 514d766 (added in 373100a). There, the Ext call also accepts port type 1 (`typeAccepted`, line 149).

KytyPS5 dfec14a `libs/libPad.cpp:126-135, 170` (KS69) registers the NID to a stub that returns 0, which is exactly the bug. Only the NID agrees with it.

The NID `WFIiSfXGUq8` was checked with exp 0327's calculator (nid0401.py's algorithm).

**How our open path works.** `Controller::PadOpen` (controller.cpp 1220-1243) validates the arguments with `PadOpenArgsAreValid` and returns handle = player slot + 1. The loader's stub returns 0, and `ControllerIndexFromHandle` rejects 0 (controller.cpp 489-492). controller.cpp is not needed, and not edited.

**Change** (output libPad.cpp 301-345):
- `Bc5PadOpenExt` maps port type 1 to 0 and calls `Controller::PadOpen`, so it keeps the same handles, checks and 0x80920001 errors. The system user with type 1 stays invalid.
- It is registered only with the switch on.

**TODO(verify).** What port type 1 is on the console.

### 5. Extras

- **R1 #15 Initialize aliases: ported** (`KYTY_BC5_SAVEDATA_ALIASES`).
  - `ZkZhskCPXFw` (sceSaveDataInitialize) and `l1NmDeDpNGU` (Initialize2) are registered to `SaveDataInitialize3` in both SaveData tables (output 1789-1792 and 1833-1836).
  - Sources: AnyPS5 bc6a5e4ea `core/libs/prx/libSceSaveData.native/Export.cpp:1817, 2070` (GPL-2.0-only) and shadPS4 60c42b9 `savedata.cpp:1194-1210, 1817-1819`.
  - The NIDs were checked with the calculator.
- **R2 KS14 + SS10, delete of a mounted save: ported** (`KYTY_BC5_SAVEDATA_DELETE_BUSY`), from KytyPS5 dfec14a `:1051-1056`.
  - The delete returns BUSY. The mount lock is held to the end of the delete (output 1439-1444, and the `Bc5MountLockIf` helper in the top block).
  - **Not taken:** KytyPS5's use of `del->title_id`, which needs KS17's name checks.
- **R2 KS04, HttpCreateTemplate with a NULL user agent: ported** as item `agent` of `KYTY_BC5_HTTP2_FIXES`, although the call is Http, not Http2.
  - Source: KytyPS5 87e815b, dfec14a `src/libs/network.cpp:469`.
  - network.cpp is not this group's file. So a wrapper in libNet.cpp (output 690-696) passes "" for NULL and is registered in place of `Http::HttpCreateTemplate` with the item on (701-705).
- **R1 #18, Http2 SSL options on a context: ported** as item `ssl`, from AnyPS5 754aad4e9 `core/libs/prx/libSceHttp2/Export.cpp:79-90, 303-315`.
  - `SslEnableOption` and `SslDisableOption` accept an id that is a context's and not a template's or request's (output 1054-1097). Today that is INVALID_ID.
  - The flags are kept per context. No transport reads them.
  - **Not done:** templates inheriting a context's flags. It is unverified and has no observable effect here.
  - **Risk:** this file numbers contexts, templates and requests separately. A context id that equals a template or request id still goes to that object, as today.
- **R2 KS17, SaveData input checks: held** for time. It touches many calls (Mount3, TransferringMount, Delete, Search, the memory calls) and changes which names a title may use. Its character set is KytyPS5's choice and is not verified on a console. It needs its own switch and test.

## The CPU test (svc0405.cpp)

There are **21 checks in every setting**; the file header lists them.

| Checks | Area |
|---|---|
| 1-7 | memory |
| 8-9 | queue |
| 10-11 | delete |
| 12-13 | aliases |
| 14-18 | Http and Http2 |
| 19-21 | pad |

**Run lines.**
- `on` needs at least one of the five switches on; `off` needs none.
- Each check expects the setting of its own switch or item. All `=1` and `on`, all `=0` and `off`, and unset and `off` all work. So does one switch, or one item list, at a time.
- The end line is `svc0405: on|off 21 of 21; end`, with exit 0.
- A watchdog stops the run at 120 s (exit 3). Exit 2 means a wrong argument or environment.

**Where the off case is not run.**
- The concurrent backup and poll race (check 8) runs only with `lock` on. Without the lock it is a data race on a `std::deque`. On the laptop stand-in, the unedited unit crashed there.
- `agent` off does not call today's `HttpCreateTemplate` with NULL, which aborts (`std::string` from NULL). Off checks only that today's function is registered and works with a named agent.

**No network.** The Http2 request's URL (`https://example.invalid/...`) is never contacted, because this host has no Http2 transport. `SendRequestAsync` fails with TIMEOUT at once, and the event fires on that path.

### How the test stays away from real saves

1. It refuses to start (exit 2) in three cases:
   - `KYTY_BC5_SAVEDATA_DIR` is set to any value, including an empty one;
   - `KYTY_BC5_SAVE_TRACE` is set;
   - any of e4's three SaveData switches is on.
2. It makes a **fresh** `svc0405-work-<pid>` directly under the canonical current directory, and refuses if that path already exists. Before any SaveData call it checks that the new path:
   - is a real directory, not a link;
   - is its own canonical path;
   - sits directly under the current directory.
3. It enters that directory and checks that it did. It then sets `KYTY_BC5_SAVEDATA_DIR` to the absolute `<work>/_SaveData`.
   - The memory file then goes to `<work>/_SaveData/UNKNOWN/sce_sdmemory/memory.dat`. The test checks exactly that absolute path; it is printed at the start.
   - Mount3 and Delete use the relative `_SaveData`, so they also land in `<work>`.
   - No param.sfo is loaded, so the title is `UNKNOWN`.
4. At the end it removes only `<work>`.

So even if it is run from `~/bc5-work`, nothing outside `~/bc5-work/svc0405-work-<pid>` is written, and `~/bc5-work/_SaveData` is never named.

## Verified on the laptop

**Script.** Python 3.14 (`python mksvc0405.py`, without `-I`).
- Run on the e5 input tree, it printed the three output md5s below. The three inputs matched their pinned md5s.
- Run again on its own output, it was refused (exit 1, "has the edit already") and wrote nothing.
- With every replacement undone in reverse order (scratch `revert.py`), each output is byte-identical to its input.
- Braces, parentheses and brackets balance before and after the edit, outside comments and literals.
- The inserted text is ASCII. The non-ASCII byte counts are unchanged: 9, 21 and 9.

**Syntax.** clang++ from Visual Studio 18 (x86_64-pc-windows-msvc), `-fsyntax-only -std=c++20 -Wall -Wextra -Werror`, with the stand-in `cmake_config.h` and fmt from `refs/Inori_GPCS4`.
- libSaveData.cpp and libPad.cpp: clean.
- libNet.cpp: clean apart from two `-Wmissing-field-initializers` errors. These are in today's `Http2CreateTemplate` and `Http2CreateRequestWithURL` aggregate initialisations, and the input file has the same errors. It is clean with `-Wno-missing-field-initializers`.
- svc0405.cpp: clean. The only flag added was `-Wno-deprecated-declarations`, for Windows' `getpid`, with a stand-in `unistd.h` that declares `setenv`.

**Stand-in run, SaveData part only.** This is a scratch copy of the test with checks 14-21 cut, so 13 checks. It was built with the real output `libSaveData.cpp`, e4's `standin2.cpp`, the real `subsystems.cpp`, and Windows stand-ins for `setenv` and `rename`.
- *Why a `rename` stand-in.* Windows' `rename` will not replace an existing file. Without the stand-in, check 5 failed with INTERNAL on the second write. That is a laptop artifact: the box's Linux `rename` replaces the file.
- *Runs that passed.* Each printed its own lines, and each left no work directory:
  - all `=1` with `on`: 13 of 13;
  - unset with `off`: 13 of 13;
  - all `=0` with `off`: 13 of 13;
  - `MEMORY_FIXES=sync`, `=existed,bogus`, `=lock`, and `=foo` with `DELETE_BUSY=` empty, each with `on`: 13 of 13.
- *Refusals.* Each of these exited 2, and nothing was written:
  - `KYTY_BC5_SAVEDATA_DIR` set to `/x`, or set empty;
  - `on` with no switch, or `off` with one;
  - `KYTY_BC5_SAVEDATA_EVENT_CB=1`;
  - `KYTY_BC5_SAVE_TRACE` set;
  - a wrong argument.
- *The unedited input unit.* It passes `off` 13 of 13. With `on` it fails checks 1-4, 6 and 7, then crashes in check 8 (exit 139): the race on the unlocked queue, which is what KS02 is about.
- *e4's sav0401 with this output unit.* Built the same way, it passed `off` 20/20, `FIXES=1` 20/20, `SORT=1` 20/20 and `EVENT_CB=1` 33/33. e4's three switches keep their behaviour.

**Not checked on the laptop.**
- Checks 14-21: Http2, sceHttpCreateTemplate and the pad. They need the real `eventQueue.cpp`, `network.cpp`, `controller.cpp` and libNet's whole unit; there was no time for a stand-in.
- The box's Linux compile, and the real `Log`, `Config` and `Network` subsystems.

## Risks and doubts

- None of these behaviours is measured on a console. Each follows upstream emulators, which agree with each other where two or more are cited.
- The box build may add warnings that Windows clang did not show.
- With `lock` on, `queue_save_data_event` from `Umount2` takes the queue lock under `g_mount_mutex`. That is the same order as e4's event callback. The queue lock is a leaf: nothing is taken while it is held.
- With delete busy on, `Delete` now holds `g_mount_mutex` while it removes the files.

## Build and run notes for the top session

- **Build:** `build0401.py ... src/libs/libSaveData.cpp=<out>/src/libs/libSaveData.cpp src/libs/libNet.cpp=<out>/src/libs/libNet.cpp src/libs/libPad.cpp=<out>/src/libs/libPad.cpp --gate svc0405.cpp <dir>/svc0405 --like src/libs/libSaveData.cpp`.
- **Gate rows:** `svc0405 on` with all five switches `=1`, and `svc0405 off` with all five `=0` and with all unset. Use distinct run-directory names per row, as e4 had to (sav0401-notes).
- **E4_STRS** (or its e5 successor) can add the five switch names and the five `exp 0405:` line prefixes above.
- **Keep e4's sav0401 rows.** They link with this libSaveData.cpp. Its switches must stay unset in the svc0405 rows, or svc0405 refuses to run.

## Files

| File | md5 |
|---|---|
| input src/libs/libSaveData.cpp (e4's private unit) | 04f4c5bb05179b80fd7cf1e41832cdd9 |
| input src/libs/libNet.cpp (base) | f7a26ceb10a4cf669c33ed592eb1e89d |
| input src/libs/libPad.cpp (base) | dbe268d7dff6134db45ad4328aace716 |
| output src/libs/libSaveData.cpp | 0e0c5d409286893e9956df9aeba845f5 |
| output src/libs/libNet.cpp | 35773d6e769b85be74012a86c0f02e89 |
| output src/libs/libPad.cpp | 89a047a4f1ad39847bf76c15fa0d4c14 |
| mksvc0405.py | f16a54ec0298d7582ca88fd4bd590096 |
| svc0405.cpp | 909a68d98fbfe8a35208b551cd245627 |
| svc0405-notes.md | (this file) |
