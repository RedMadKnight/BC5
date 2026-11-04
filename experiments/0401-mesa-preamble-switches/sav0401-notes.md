# Series e4: SaveData lifecycle fixes (exp 0402 Top 10 item 9), notes for the build

Written 2026-11-03 on the laptop (the first port, `KYTY_BC5_SAVEDATA_FIXES`) and extended 2026-11-04, also on the laptop, with no box access. The extension follows the maintainer's new rule: a port is judged for any title, not for ours only. Under that rule the first port's two "not applicable" verdicts (the event callback) and its "deliberate difference" verdicts (three sort key definitions) were reopened.

Item 9 of exp 0402's survey (Top 10 row 9, §2 SaveData row) names four upstream commits. Each was checked against the tree the shared builds came from: KytyPlus `f266548` + patch 0001, `src/libs/libSaveData.cpp` md5 `d6e9c37fa099d576ce4c495dab850271`, 1,320 lines. Unless a path says otherwise, line numbers below are in that file.

Sources read (all read only, none copied into the repo):
- AnyPS5 (github.com/boykopovar/AnyPS5, GPL-2.0-only), another session's clone at `4f41f4c375f5abb487dbd184fbc150f31994d762`: `core/libs/prx/libSceSaveData.native/Export.cpp`, `core/libs/tests/GuestSaveDataEventCallback.cpp`, `docs/dev/debt/libSceSaveData.native.md`, and the commits `0d0abe09c19c85d61ac3f2227876a0c83037d6c8` and `bc6b4d76f90dab36a47bc06789c11aa4d81bbeca`.
- KytyPS5 (github.com/KytyPS5/KytyPS5, GPL-2.0, as KytyPlus), `refs/KytyPS5_KytyPS5`: `src/libs/libSaveData.cpp` at `dfec14aa8c59f8ea2bc4d87eba9854fc370161c6`, and commit `4b0282e3430ec64b5012d1c5c5a90f495f05df76` with its test `tests/SaveDataMemoryTests.cpp`.
- shadPS4 (GPL-2.0), `refs/shadps4-emu_shadPS4` at `60c42b925c3d1e00008621b8587819999260ec31`: `src/core/libraries/save_data/savedata.cpp` and `save_instance.cpp`.

## Verdicts

| Commit | What it fixes upstream | Verdict | Evidence |
|---|---|---|---|
| AnyPS5 `0d0abe09c` (`core/libs/prx/libSceSaveData.native/Export.cpp`) | The event-callback delivery thread starts at the first successful `sceSaveDataRegisterEventCallback` of an initialization, not in `sceSaveDataInitialize3`; the final terminate joins it only if one was started | **Ported, with the callback feature it fixes**, behind `KYTY_BC5_SAVEDATA_EVENT_CB` (first verdict: not applicable) | "The event callback" below |
| AnyPS5 `bc6b4d76f` (same file) | `sceSaveDataRegisterEventCallback` checks the initialization count and stores the callback under `g_slots_mutex`, atomically with the final `sceSaveDataTerminate` | **Ported**, same switch (first verdict: not applicable) | Same |
| KytyPS5 `4b0282e` (`src/libs/libSaveData.cpp`) | `DirNameSearch` sorts by the requested key; ties go by name; descending reverses both | **Order: already fixed** (F217, run on the box in F319/F324). **Key definitions: the mtime key ported** behind `KYTY_BC5_SAVEDATA_SORT`; **free blocks and the missing blocks record kept**: ours is the better-sourced behaviour (first verdict: all three deliberate) | 559-582 for the order; "The sort keys" below |
| KytyPS5 `dfec14a` (same path) | `SaveDataMount3` clears the caller's result only on its way to a successful mount, so a refused mount leaves it as it was | **Missing → ported** behind `KYTY_BC5_SAVEDATA_FIXES` (unchanged since the first port) | 625 `*mount_result = {};` comes before every refusal: BUSY 637, MOUNT_FULL 640, PARAMETER 646, NOT_FOUND 650, EXISTS 654, NO_PERMISSION 666. The mount itself is at 677. |

### The event callback (AnyPS5 0d0abe09c, bc6b4d76f)

**Why the first verdict changed.** It found the callback path unreachable for our titles:
- our host exports neither `sceSaveDataRegisterEventCallback` (NID `hsKd5c21sQc`) nor `sceSaveDataUnregisterEventCallback` (`v-AK1AxQhS0`);
- the second title's stub list (exp 0327, `raw/S1-stub-list-resolved.txt`) does not import them;
- the title polls `SaveDataGetEventResult` instead (F188, F189).

All of that still holds. Under the new rule it is not enough. A title that imports the register NID today gets the loader's return-0 stub: OK, and never a callback. A title that waits on that callback for a backup's completion would wait forever. The two AnyPS5 fixes need the feature they fix, so the feature was ported with them.

The NIDs come from exp 0327's calculator (`nid0401.py`'s, self-checked on `strcmp` and three registered SaveData NIDs). It gives `hsKd5c21sQc` and `v-AK1AxQhS0`, as the first notes had.

**What was ported** (AnyPS5 `Export.cpp` @ 4f41f4c37):
- the delivery thread and its state, 69-163: `EventDelivery`, `EventWorker`, `EventCallbacks` (a recursive "calling" lock, a mutex, a condition variable, the callback and userdata, the pending deliveries, the worker, the thread now delivering), `DeliverEvents`, `StartEventDelivery`, `DetachEventDelivery`, `JoinEventDelivery`, `InEventCallback`, `DeliverEvent`;
- `sceSaveDataRegisterEventCallback`, 1871-1886. It takes the calling lock, then the slot lock, and only then checks the count (NOT_INITIALIZED at 0, bc6b4d76f) and the callback (PARAMETER for null). It starts the delivery thread if none runs (0d0abe09c), then stores the callback and userdata;
- `sceSaveDataUnregisterEventCallback`, 2019-2027: it clears the callback, the userdata and the pending deliveries, under the calling lock. It always returns OK;
- `sceSaveDataInitialize3`'s count (1059-1064), and `sceSaveDataTerminate`'s BUSY from inside a callback and its stop of the delivery thread (1398-1419). The final terminate detaches the worker under the slot lock and joins it outside it, only when one was started.

**Fitted to our event model:**
- *One choke point for events.* `queue_save_data_event` (263-281) queues every event this file makes: type 1 (`Umount2` with `BACKUP_ASYNC`, 903-905), type 2 (`Backup`, 1123-1124) and type 4 (`Commit` with `BACKUP_ASYNC`, 939-941). With the switch on it still puts each event in the poll queue first, then hands it to the callback registered at that moment, as AnyPS5's backups do. A polling title sees every event exactly as before, callback or not.
- *Commit events too.* AnyPS5 queues nothing on a commit (its `sceSaveDataCommit` returns OK), so its callback sees types 1 and 2 only. Ours also sees type 4, because this file makes that event.
- *The poll queue gets a lock* (`g_bc5_save_data_events_mutex`), taken by the queueing, by `GetEventResult` and by `Terminate`'s clearing. The first port flagged the deque as unlocked. With the switch on, the delivery thread's callbacks add one more thread that queues and polls, so the lock is needed. With the switch off the queue is today's, unlocked.
- *`g_mount_mutex` stands for AnyPS5's `g_slots_mutex`.* It is the lock `Terminate` and `Umount2` already hold. It is a recursive `Common::Mutex`, so a callback that calls back into SaveData does not deadlock on it. The lock order is calling, then `g_mount_mutex`, then either the callbacks' mutex or the queue's lock (never both).
- *The count* (`g_bc5_initializations`) is kept under `g_mount_mutex` and counted only with the switch on.
- *`Terminate` keeps this file's rules*: BUSY while any save is mounted (AnyPS5: only for the last initialization); OK when nothing was initialized (AnyPS5: NOT_INITIALIZED); the poll queue cleared on every successful call. It adds AnyPS5's BUSY from inside a callback, and the stop and join of the delivery thread at the count's 0. A polling title therefore gets today's return codes.
- *The thread is a guest thread*: `LibKernel::PthreadCreate` with the default attributes, as AnyPS5's `scePthreadCreate`. The title's callback runs on a guest stack, on a thread with the state guest code expects. `avPlayer.cpp` starts its workers, which call guest code, the same way (1162-1170) and joins them with `LibKernel::PthreadJoin` (1197-1205). The delivering thread is told by its host thread id; AnyPS5 compares Pthreads.
- *No exceptions in this build.* A thread that cannot start makes the registration return `SAVE_DATA_ERROR_INTERNAL`. A join that fails prints a stderr line and keeps the worker allocated (the thread may still use it). AnyPS5 throws `std::runtime_error` in both cases.
- *Registration.* Both NIDs go into both SaveData tables (`InitSaveData_1` and `InitSaveDataNative_1`), as this file registers every SaveData NID in both.

**Off**: neither NID is registered (a title that imports them gets the loader's stub, as today), and none of the block runs. The poll queue, `Initialize3` and `Terminate` are today's.

### The sort keys (KytyPS5 4b0282e)

The order (sort by name, then stably by the key, reversed for descending) was already right (F217). The first notes listed three key definitions in which ours differs from KytyPS5. Ours came from AnyPS5 `7f596df` and is still AnyPS5's at `4f41f4c37`. Each one, with the three implementations side by side:

| Key | Ours (`d6e9c37f`) | KytyPS5 (`4b0282e`, lines at `dfec14a`) | shadPS4 (`60c42b9`) | AnyPS5 (`4f41f4c37`) | Verdict |
|---|---|---|---|---|---|
| Free blocks | The save's blocks less its files, each file rounded up to a 32 KiB block (`save_data_search_info`, 385-390) | Its total blocks (`read_save_blocks`, 650), because its search infos and GetMountInfo report free = total ("Host-directory saves report their allocation as free space", 685-686; 1355) | Total less the directory's size in 32 KiB blocks (`map_free_size`, savedata.cpp 841; sort 858-859; infos 892) | Blocks less the files, rounded per file (`search_info`, 863-871) | **Kept** |
| Mtime | The param's mtime the title set, else the newest of the directory and its top-level files (`save_data_load_param` 394-408, `save_data_dir_mtime` 430-447) | The newest write time of the regular files in the save, recursively, whatever the param says (`newest_save_time` 411-431, `load_save_param` 433-440; the sort 651-653, the search's params 673, GetParam 1084) | The save's `param.sfo` write time (`FromSFO` 517-525, sort 861-862); `param.sfo` is written when the save is made and at every unmount (save_instance.cpp 195-201, 219) | The param's mtime, which every SetParam but type MTIME stamps with the current time (1247-1249), else the directory's write time (`load_param` 352-372) | **Ported** (KytyPS5's) |
| No blocks record | The maximum, 16384 (`save_data_blocks`, 345-357) | 0 for the sort (639: "A save whose metadata cannot be read sorts as 0"); its search then fails BROKEN when infos are asked (681-684), and so does GetMountInfo (1349-1352) | The maximum when `SAVEDATA_BLOCKS` is missing (`GetMaxBlockFromSFO`, save_instance.cpp 60-67) | The maximum (`save_blocks`, 834-841) | **Kept** |

None of the four cites a console measurement for any of these definitions. AnyPS5's debt list says its sort keys follow shadPS4 (`docs/dev/debt/libSceSaveData.native.md`, line 20).

**Free blocks, kept.**
- Three of the four sort by the save's real free blocks, which is what the key's name says.
- KytyPS5's choice follows from its own simplification: its infos and GetMountInfo report the total as free. Its sort is consistent with that.
- Porting its key alone would make our order disagree with the free blocks our own search infos and GetMountInfo report.

**Mtime, ported.**
- All three upstreams leave out the mtime a title puts in its SaveDataParam. KytyPS5 overwrites it with the files' time; shadPS4 reports the `param.sfo` write time and never stores the title's; AnyPS5 stamps the time of the SetParam.
- Ours alone keeps the title's value and sorts by it. A title that sets a stale or zero mtime, or never sets one, gets a list that does not follow its saves' writes.
- KytyPS5's definition was taken because it is a read-side rule only (no SetParam change). Fitted to this file it also covers the other two: our param record is rewritten at every SetParam (AnyPS5's moment), and the files' times follow the writes (shadPS4's `param.sfo` is rewritten at unmount).

**No blocks record, kept.**
- shadPS4 and AnyPS5 both report the maximum.
- In KytyPS5 every save it makes has its record, so a missing one means a broken save, and its search reports it BROKEN.
- Here a save without a record is not broken. It is a save made before F217 added the record, or one made with blocks 0, and this file reports it as the maximum in the search infos and in GetMountInfo. Sorting it as 0 would contradict those.

**What `KYTY_BC5_SAVEDATA_SORT` changes** is the mtime that `save_data_load_param` returns: the newest write time of the save's regular files, recursively (KytyPS5 `newest_save_time`). That one function feeds the search's mtime order, the params the search returns and `GetParam` (type 0), as `load_save_param` feeds all three in KytyPS5.
- *Fitted to this file:* KytyPS5 keeps the param and the blocks record inside the save (`sce_sys/param.bin`, `sce_sys/blocks.bin`), where they count among its files. This file keeps them beside the save (`<dir>.param`, `<dir>.blocks`), so the two records are counted from there.
- *A save with no file and no record* keeps this file's rule (run 573): it gets the directory's time, not 0 (01/01/1970 in a slot list).
- **Off**: today's (the title's mtime, else the directory's).

## What was ported

`mksav0401.py <tree root in> <out dir>` edits `src/libs/libSaveData.cpp` and prints `<md5>  <relpath>`.
- *Anchors.* It has 15, each asserted to occur exactly once.
- *Refusal.* It refuses a tree that has any part of the edit already. It checks for the three switch names, `bc5_savedata_`, `series e4`, both NIDs, `Bc5Event`, `g_bc5_initializations`, `g_bc5_save_data_events_mutex`, `bc5_save_data_events_lock` and `bc5_newest_save_time`.
- *Input asserts.* Exactly two `*mount_result = {};` lines (Mount3's and TransferringMount's). One queue push, one queue read and one queue clearing.
- *Output asserts.* The uses of each switch function: fixes 4, event callback 7, sort 3. Three uses of the queue's lock helper.

Each switch is a function-local static, read once with `std::getenv` (so the lean build has it too). It is on when set, non-empty and not `0`, and prints one stderr line at the first read. `InitSaveData_1` reads all three first, so every run prints:
- `[bc5] exp 0401: savedata fixes on|off`
- `[bc5] exp 0401: savedata event callback on|off`
- `[bc5] exp 0401: savedata sort on|off`

**`KYTY_BC5_SAVEDATA_FIXES`** is unchanged in behaviour since the first port: the switch and its comment block before `mount_save_data`, Mount3's clearing wrapped for off, the success-path clearing for on. Only its comment's last lines changed: they now point to the two new blocks instead of calling those commits not ported.

**`KYTY_BC5_SAVEDATA_EVENT_CB`:**
- *Includes.* `#include "kernel/pthread.h"`, plus `<condition_variable>`, `<memory>`, `<thread>` and `<utility>` under a comment line.
- *The block* before `queue_save_data_event`: the comment (exp 0401 series e4, AnyPS5 path, commit and lines, GPL-2.0-only with the authors' copyright kept, both fixes with their hashes, the fitting), the switch, the delivery state and thread, `bc5_terminate`, and `SaveDataRegisterEventCallback` / `SaveDataUnregisterEventCallback`. It ends with an end marker.
- *`queue_save_data_event`.* A lock line before the push, and after it an `if` that, with the switch on, unlocks and delivers.
- *`SaveDataGetEventResult`.* A lock line before the poll.
- *`SaveDataInitialize3`.* The count, with the switch on.
- *`SaveDataTerminate`.* With the switch on, `return bc5_terminate();` first.
- *Both tables.* With the switch on, the two NIDs.

**`KYTY_BC5_SAVEDATA_SORT`:**
- *The block* before `save_data_load_param`: the comment (KytyPS5 path, commits and lines, GPL-2.0 as KytyPlus with the authors' copyright kept, the two keys kept and why), the switch, and `bc5_newest_save_time`. It ends with an end marker.
- *`save_data_load_param`.* With the switch on, the mtime is set to that time before today's `if (param.mtime == 0)` fallback.

**Off is today's path.** A scratch script took the output and removed:
- the three blocks;
- the five include lines and their comment;
- the seven switch-guarded `if` blocks;
- the two lock lines (an empty `unique_lock` when off);
- the three registration reads (they only print).

It also unwrapped the fixes switch's off clearing. The result equals the input byte for byte. The script is `C:\Users\kjani\AppData\Local\Temp\claude\7e70d624f1bff3f5\19eb012d-ed8a-4416-af2a-d3b1f4ce12f0\scratchpad\offpath_sav.py` (scratch, not a deliverable).

**md5s.**

| | md5 |
|---|---|
| Input `src/libs/libSaveData.cpp` | `d6e9c37fa099d576ce4c495dab850271` |
| Output `src/libs/libSaveData.cpp` (three switches) | `04f4c5bb05179b80fd7cf1e41832cdd9` |
| Superseded: the first port's output (fixes only) | `0723d4bae6a070f51ed5360e4e35a4f8` |
| `mksav0401.py` | `3d0351984a50e6c891fe1678d9278ae2` |
| `sav0401.cpp` | see "md5s of the deliverables" at the end |

**Includes.** The unit already includes `<cstdlib>`, `<cstring>`, `<cstdio>`, `<deque>`, `<mutex>`, `<filesystem>` and `<sys/stat.h>`. The new quoted include carries its directory (`kernel/pthread.h`, as `avPlayer.cpp` includes it), so a private copy still compiles with the shared command and no extra file.

## The test, `sav0401.cpp`

One program for all three switches. It reads the three switches as the unit does: `on` needs exactly one of them on, `off` none. Each check expects the setting of its own switch.
- *Refusals (exit 2).* A mismatch between the argument and the switches; `KYTY_BC5_SAVEDATA_DIR` set, even empty (the box unsets it, and the test must never come near a real save); `KYTY_BC5_SAVE_TRACE` set.
- *Where it works.* Only in `./sav0401-work-<pid>`, a fresh directory it makes under the current one and removes at the end. With no param.sfo loaded, the saves go to `_SaveData/UNKNOWN` there.
- *Watchdog.* It ends a hang after 240 s with `sav0401: FAIL watchdog: "<step>" did not finish within 240 s` (exit 3). The box's own timeout per run is 300 s.

**Search (9 checks).** KytyPS5's `TestSearchSortKeys` saves (alpha, bravo, charlie; blocks 96, 48, 48; user params 2, 3, 1; title mtimes +1, +3, +2 h). Their `.param` records' file times are set to now +1, +3, +2 h, as that test sets its `sce_sys/param.bin`.
1. The five orders that test expects (checks 1-5): the same in both settings, since the files' and the titles' times agree there.
2. Check 6: alpha without its `.blocks` record sorts last (kept rule), in both settings.
3. Check 7 (SORT): alpha's record is moved to +5 h. By mtime, descending: `alpha bravo charlie` with the switch on, `bravo charlie alpha` off.
4. Check 8 (SORT): the mtime the search reports for alpha is its record's file time on, the title's +1 h off.
5. Check 9: a save with no file and no record reports its directory's time (not 0), in both settings.

**Mount result (9 checks, FIXES).** As in the first port: a created mount's result; BUSY over the mounted save; the unmount through the BUSY call's result; an opened mount's result; then NOT_FOUND, EXISTS, PARAMETER, NO_PERMISSION and MOUNT_FULL over a result filled with 0xab (untouched on, cleared off).

**Events (EVENT_CB): 2 checks off, 15 on**, after AnyPS5's `GuestSaveDataEventCallback.cpp` cases, written anew for our functions.

*Both settings:*
1. The unit's registration. `InitSaveData_1` runs into a fresh `SymbolDatabase`. On: both NIDs are found by NID and by both tables' import keys, at the two functions' addresses. Off: absent. A control lookup of `j8xKtiFj0SY` shows the registration ran.
2. Polling as today: a backup's event, then a `BACKUP_ASYNC` commit's (a plain commit queues none), then NOT_FOUND.

*On only:*
3. Register before `Initialize3` is NOT_INITIALIZED; unregister then is OK; a null callback is PARAMETER. None of it starts a thread.
4. A backup reaches the callback within 5 s: once, with its userdata, on a thread other than the caller's. The poll returns the same event byte for byte.
5. A `BACKUP_ASYNC` commit (type 4) reaches it on the same delivery thread, and the poll.
6. A `BACKUP_ASYNC` unmount (type 1, queued under `g_mount_mutex`) reaches it on the same thread, and the poll.
7. A replacing registration takes the next event, on the same thread.
8. After unregister, no callback runs within 300 ms, and the poll still has the event.
9. An unregister from inside the callback drops the delivery still pending: a second backup is queued while the first one's callback runs.
10. A registration after unregister reuses the delivery thread.
11. A terminate from inside the callback is BUSY.
12. The final terminate joins the delivery thread. A `thread_local` destructor the callbacks set up has run when `Terminate` returns.
13. That terminate dropped the registration. Register is NOT_INITIALIZED; after a new `Initialize3` a backup reaches no callback until one registers again, on a new thread, and its terminate joins that one.
14. Re-registration races. Two threads re-register (A, B, every fifth time unregister, 2,000 times each) while one thread backs up 300 times and one polls 3,000 times. Every call carries its own callback's userdata; none comes after the final unregister; a fence callback then gets its event. All of it runs on one delivery thread.
15. Registration racing the final terminate (bc6b4d76f's case), 100 times. Even iterations hold the delivery thread in a callback and start the registration 10 ms before the terminate. Odd ones start both at once. Each time: terminate OK, registration OK or NOT_INITIALIZED; after a new `Initialize3` a fence callback gets its backup and the raced callback is never called.

On Linux, checks 3, 4, 7, 10 and 12-15 also count `/proc/self/task`: no thread before the first registration, one after it, none after the final terminate. This is 0d0abe09c's own check.

**End line.** `sav0401: on|off N of N; end`, exit 0, with N = 20 (9 + 9 + 2), or 33 (9 + 9 + 15) with `KYTY_BC5_SAVEDATA_EVENT_CB` on. A failed check prints `sav0401: FAIL <check>: <detail>` and the run exits 1.

**Runtime state.** Every run starts Common, Threads (the test's main thread) and FileSystem, as before. Logging is switched off before the first subsystem. With `KYTY_BC5_SAVEDATA_EVENT_CB` on the delivery thread is a real guest thread, so the run also starts what one needs, in emulator.cpp's order:
- Config, with its printf direction set to Silent;
- Log (Silent, so `PRINT_NAME`, which `PthreadCreate` turns on for its caller, never asks the Timer);
- Timer, Memory (the guest stack) and Pthread;
- the `RuntimeLinker` singleton, made on the main thread: a guest thread's end calls `DeleteTlss` on it, and its constructor insists on the main thread.

The program ends with `_Exit` after the end line, because the Pthread subsystem's helper thread may still run during static destruction.

**Linked with the shared, unedited object, it does not link**: the two new functions are missing. Checked on the laptop. Only mksav0401.py's output links.

**Build on the box,** as before (`npgate0401.cpp`'s way):
1. **Private unit.** Take the compdb command for `src/CMakeFiles/kyty_emulator.dir/libs/libSaveData.cpp.o`, cleaned as `build0401.py` cleans it. Use `-c <out dir>/src/libs/libSaveData.cpp` and `-o libSaveData.cpp.o`.
2. **Test object.** The same command with `-c sav0401.cpp -o sav0401.o`. It needs only the tree's headers: `common/abi.h`, `common/commonSubsystem.h`, `common/emulatorConfig.h`, `common/logging/log.h`, `common/singleton.h`, `common/subsystems.h`, `common/threads.h`, `kernel/fileSystem.h`, `kernel/memory.h`, `kernel/pthread.h`, `libs/errno.h`, `loader/runtimeLinker.h`, `loader/symbolDatabase.h` and `loader/timer.h`.
3. **Link.** Take the `src/kyty_emulator` link command and drop `main.cpp.o`. Put the private `libSaveData.cpp.o` in place of the shared one and add `sav0401.o`. Use `-o sav0401`, and rewrite `-Wl,-Map=` and `--dependency-file=` as `build0401.py` does.
4. **Run** from a fresh directory on the NVMe, with `KYTY_BC5_SAVEDATA_DIR` and `KYTY_BC5_SAVE_TRACE` unset and one switch at a time, the other two unset:
   - each of `KYTY_BC5_SAVEDATA_FIXES`, `KYTY_BC5_SAVEDATA_SORT` and `KYTY_BC5_SAVEDATA_EVENT_CB` set to `1` with `on`;
   - the same switch `0`, and unset, with `off`.
   - Expected end lines: `on 20 of 20` (FIXES, SORT), `on 33 of 33` (EVENT_CB), `off 20 of 20` (all off runs).
   - Each run also prints the three `[bc5] exp 0401: savedata …` lines on stderr. Every run prints one stdout line from the host's `mkdir` for the NO_PERMISSION check: `mkdir(./_SaveData/UNKNOWN/blocked, 1ff) failed: The named file exists`.

**What `box0401.sh` needs for this** (not edited here; outside this task's three files):
- `E4_EDITS`'s `sav` row: output md5 `04f4c5bb05179b80fd7cf1e41832cdd9` in place of `0723d4ba…`.
- `E4_GATES` runs `sav0401` for `KYTY_BC5_SAVEDATA_FIXES` only. Two more runs are needed, for `KYTY_BC5_SAVEDATA_EVENT_CB` and `KYTY_BC5_SAVEDATA_SORT`. The run directories and output files are named by the end-marker name (`run-sav0401-<g>`, `sav0401-<g>.out`), so a second and third `sav0401` row would overwrite the first one's. They need distinct names.
- The end-marker regex already accepts any N.
- `E4_STRS` should add `KYTY_BC5_SAVEDATA_EVENT_CB`, `exp 0401: savedata event callback`, `KYTY_BC5_SAVEDATA_SORT` and `exp 0401: savedata sort`.
- `test0401.py`'s fake box (line 442, `sav0401: on 3 of 3; end`) is a stand-in and needs nothing.

## Verified on the laptop

**The script.** The commands used Python 3.14 (`python mksav0401.py`, without `-I`; see the laptop pitfalls note).
- `python mksav0401.py <tree> <scratch>/sav3-out` printed `04f4c5bb05179b80fd7cf1e41832cdd9  src/libs/libSaveData.cpp`.
- Run again on its own output, it stopped with "libSaveData.cpp has the edit already" and wrote nothing.
- The input has no part of the edit: each refusal mark was grepped in it (`g_bc5_` alone is not a mark: the input has `g_bc5_save_trace`).

**The diff.** 14 hunks, +343 / −1 lines (1,320 → 1,662):
- the include, and the system includes;
- the event callback block;
- the queue's lock and delivery;
- the sort block, and `save_data_load_param`'s line;
- the fixes block;
- `Initialize3`, `Terminate`, Mount3's two clearings;
- the poll's lock;
- the two tables, and the three registration reads.

**Balance.** Brackets balance from input to output: braces 194 → 255, parentheses 606 → 761, square brackets 54 → 61. This uses the first port's lexer with UTF-8 reading, because the input itself has 9 non-ASCII bytes in comments; its counts differ from the first notes' 195/650/55, which came from another counting.

**Off path.** The reconstruction above is byte-identical to the input.

**Syntax check.** clang++ 22.1.3 from Visual Studio 18 (target x86_64-pc-windows-msvc): `-fsyntax-only -std=c++20 -Wall -Wextra -D_CRT_SECURE_NO_WARNINGS -D_SILENCE_ALL_CXX17_DEPRECATION_WARNINGS`, the stand-in `cmake_config.h`, and fmt 8.1.1 from `refs/Inori_GPCS4` as a system include.
- Output unit: 0 errors, 0 warnings.
- `sav0401.cpp`: 0 errors, and one warning from the stand-in `unistd.h` (Windows' `getpid` deprecation), as in the first port.

**Stand-in run.** This is not the box's objects or compiler.
- *What was built.* The output unit and `sav0401.cpp` were compiled for Windows (`-O1 -DFMT_HEADER_ONLY -DFMT_CONSTEVAL=`) and linked with the tree's real `common/subsystems.cpp` and a scratch stand-in. The stand-in is the first port's, plus:
  - a `SymbolDatabase` after the tree's (`GenerateName`'s format, `Add`, `Find`, `FindByNid`);
  - no-op Config, Log, Timer, Memory and Pthread subsystems, and an empty `RuntimeLinker`;
  - `LibKernel::PthreadCreate` / `PthreadJoin` as a `std::thread` and its join.
- *Normal runs.*
  - Unset and `off`, `FIXES=0`, `SORT=0`, `EVENT_CB=0` and `EVENT_CB=` (empty) with `off`: each `off 20 of 20; end`.
  - `FIXES=1` and `SORT=1` with `on`: each `on 20 of 20; end`.
  - `EVENT_CB=1` with `on`: `on 33 of 33; end`, in about 8.5 s.
  - Each run printed the three stderr lines once, and the work directory was gone after every run.
- *Refusals, each exit 2:*
  - `on` with no switch, or with two;
  - `off` with one switch on;
  - `KYTY_BC5_SAVEDATA_DIR` empty, or `/x`;
  - `KYTY_BC5_SAVE_TRACE` set;
  - a wrong argument.
- *Mutants.* Five mutants of the output unit, one replacement each, built and run in their switch's on setting; each was caught:
  - registration reading the count before its locks (bc6b4d76f reverted): check 15 fails at iteration 0, a held one, every time;
  - the final terminate not stopping or joining the thread: checks 12-15 fail;
  - commit events not delivered: check 5 fails;
  - unregister keeping the pending deliveries: check 9 fails. A first version of the test, without check 9 and with both race threads always starting together, missed this one, and the race needed 4 iterations for the bc6b4d76f revert. Both were tightened;
  - the sort block not counting the records beside the save: checks 5, 7 and 8 fail.
- *Not covered on the laptop.* The stand-in has no `/proc/self/task`, so the thread-count parts (0d0abe09c's "no thread before the first registration") were not exercised. Its threads are not guest threads: the real `PthreadCreate`, `RunThread`, the guest stack and `CleanupThread` run only on the box.
- *Files* (scratch only, not deliverables):
  - the stand-in: `C:\Users\kjani\AppData\Local\Temp\claude\7e70d624f1bff3f5\19eb012d-ed8a-4416-af2a-d3b1f4ce12f0\scratchpad\standin2\standin2.cpp`;
  - the mutation script: `C:\Users\kjani\AppData\Local\Temp\claude\7e70d624f1bff3f5\19eb012d-ed8a-4416-af2a-d3b1f4ce12f0\scratchpad\standin2\mutate.py`;
  - the unit's diff: `C:\Users\kjani\AppData\Local\Temp\claude\7e70d624f1bff3f5\19eb012d-ed8a-4416-af2a-d3b1f4ce12f0\scratchpad\sav3.diff`.

## Doubts

- **Not yet compiled or run on the box.** GCC is not involved (the box compiles with clang), but the box's clang and headers may still warn where Windows' did not.
- **The event-callback run is the first exp 0401 test that starts Memory and Pthread.** That means a guest address space, a guest stack and a real guest thread. A failure there shows as `subsystem … failed` or an `EXIT` line, not as a SaveData FAIL.
- **Nothing in the callback feature is measured on a console.** AnyPS5's debt list names what is unknown: which thread delivers, its priority and affinity, when it runs relative to the call, whether unregistering drops undelivered completions, and what a terminate from inside the callback does.
  - Here, as in AnyPS5: the default guest attributes (priority 700, nice 0 on the box), unregister drops them, BUSY.
  - Ours also delivers commit events (type 4), which AnyPS5 has no source for either.
  - PS4's signatures are assumed for PS5 (`void (*)(const SaveDataEvent*, void*)` and a userdata pointer), after shadPS4 #5226 as AnyPS5 cites it. shadPS4 at `60c42b9` only stubs both calls (savedata.cpp 1317-1320, 1720-1723).
- **Events this host does not make** never reach a callback. There is no `sceSaveDataUmountWithBackup` and no `sceSaveDataConvert` (AnyPS5's type 5). Exp 0145's native `2mfSRGdshtk` promises a type-5 event, but it answers NOT_FOUND and queues none.
- **With the switch on, `Terminate` still returns OK when nothing was initialized**, and BUSY whenever a save is mounted. AnyPS5 returns NOT_INITIALIZED and BUSY only for the last initialization. Kept so that polling titles see today's codes; a title that relies on AnyPS5's codes would differ.
- **The poll lock costs one uncontended mutex per poll with the switch on.** The second title polls about 7,000 times a second (F188). The cost is not measured. With the switch off the old unlocked race remains: `Commit` and `Backup` queue without `g_mount_mutex`.
- **Not checked: the failure paths.** The `PthreadCreate` failure path (registration INTERNAL) and the failed-join path were not run.
- **SORT moves `GetParam`'s mtime (type 0) too.** It is the same function, as in KytyPS5. A title that sets an mtime and reads it back gets the files' time with the switch on.
- **SORT walks each save's files recursively on every search and every `GetParam`.** KytyPS5 does the same. The second title's saves are small; a title with large saves and frequent searches would pay a directory walk each time.
- **The block size.** AnyPS5 moved from 32 KiB (`7f596df`, Export.cpp 363) to 64 KiB (`4f41f4c37`, 797, after SharpEmu). shadPS4 keeps 32 KiB (savedata.cpp 48). Ours keeps 32 KiB. That changes the free-blocks values, not the key's definition, and none of the sources is measured. Not ported.
- **Kept from the first port:**
  - No console measurement behind dfec14a.
  - No expected effect on the second title.
  - `SaveDataTransferringMount` still clears before BUSY and MOUNT_FULL.
  - With the switch on, a refused mount keeps even uninitialised caller bytes.
  - `SetParam`/`GetParam` handle `param_type` 0 only.
  - Other titles' stub lists (ASTRO BOT or any other) were still not read. Under the new rule the ports stand on the upstream behaviour, not on a title's imports.

## md5s of the deliverables

| File | md5 |
|---|---|
| `mksav0401.py` | `3d0351984a50e6c891fe1678d9278ae2` |
| `sav0401.cpp` | `de99f1a1dd5431fec3e189374795e66f` |
| Output `src/libs/libSaveData.cpp` | `04f4c5bb05179b80fd7cf1e41832cdd9` |
