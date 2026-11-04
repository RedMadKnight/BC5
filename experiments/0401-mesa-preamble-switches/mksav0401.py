#!/usr/bin/env python3
"""BC5 experiment 0401, series e4 (exp 0402 Top 10 item 9, SaveData lifecycle): three switches in src/libs/libSaveData.cpp of
main's tree (KytyPlus f266548 + patch 0001; md5 d6e9c37fa099d576ce4c495dab850271), each read once (on when set, non-empty and
not "0", F767's reading), each with one stderr line at the library's registration, default off; off is today's path.
  KYTY_BC5_SAVEDATA_FIXES: KytyPS5 dfec14a "Fix save mount result on failed mounts" (github.com/KytyPS5/KytyPS5,
    src/libs/libSaveData.cpp, GPL-2.0, as KytyPlus): SaveDataMount3 clears the caller's SaveDataMountResult only on its way
    to a successful mount, so a mount it refuses leaves the result as it was. Line "[bc5] exp 0401: savedata fixes on|off".
  KYTY_BC5_SAVEDATA_EVENT_CB: AnyPS5's event callback (github.com/boykopovar/AnyPS5,
    core/libs/prx/libSceSaveData.native/Export.cpp @ 4f41f4c37, GPL-2.0-only) with its fixes 0d0abe09c (the delivery
    thread starts at the first registration) and bc6b4d76f (registration atomic with the final terminate): exports
    hsKd5c21sQc sceSaveDataRegisterEventCallback and v-AK1AxQhS0 sceSaveDataUnregisterEventCallback, a delivery thread
    (LibKernel::PthreadCreate), Initialize3's count; every queued event still goes to the poll queue, which gets a lock.
    Off: the NIDs unregistered and nothing of it runs. Line "[bc5] exp 0401: savedata event callback on|off".
  KYTY_BC5_SAVEDATA_SORT: KytyPS5 4b0282e's mtime key (newest_save_time/load_save_param, src/libs/libSaveData.cpp @ dfec14a):
    a save's mtime is its files' newest write time (here with the <dir>.param and <dir>.blocks records beside it), for the
    search's order and params and for GetParam. The other two key definitions that differ (free blocks, a save without a
    blocks record) are kept as they are (sav0401-notes.md). Line "[bc5] exp 0401: savedata sort on|off".
Edits src/libs/libSaveData.cpp only. Each anchor must occur exactly once; a tree that has any of the edit already is refused.
Prints "<md5>  <relpath>" for the output.
usage: mksav0401.py <tree root in> <out dir>"""
import hashlib
import os
import sys

REL = "src/libs/libSaveData.cpp"
MARKS = (b"KYTY_BC5_SAVEDATA_FIXES", b"KYTY_BC5_SAVEDATA_EVENT_CB", b"KYTY_BC5_SAVEDATA_SORT", b"bc5_savedata_",
         b"series e4", b"hsKd5c21sQc", b"v-AK1AxQhS0", b"Bc5Event", b"g_bc5_initializations",
         b"g_bc5_save_data_events_mutex", b"bc5_save_data_events_lock", b"bc5_newest_save_time")
MARK_FN = b"bc5_savedata_fixes_on"
CB_FN = b"bc5_savedata_event_cb_on"
SORT_FN = b"bc5_savedata_sort_on"

# =============================== KYTY_BC5_SAVEDATA_FIXES (KytyPS5 dfec14a) ===============================================

# ---- the switch and the comment block, just before mount_save_data -----------------------------------------------
SWITCH_ANCHOR = b"static int mount_save_data(int slot, std::string_view dir_name, const std::string& directory,\n"
SWITCH = b"""// ---- experiment 0401 series e4: SaveData fixes (exp 0402 Top 10 item 9), switch KYTY_BC5_SAVEDATA_FIXES ----
// Ported from KytyPS5 (github.com/KytyPS5/KytyPS5, GPL-2.0, as KytyPlus; the ported lines keep its authors' copyright),
// src/libs/libSaveData.cpp at dfec14a (dfec14aa8c59f8ea2bc4d87eba9854fc370161c6, "Fix save mount result on failed
// mounts", #2079): SaveDataMount3 clears the caller's SaveDataMountResult only on its way to a successful mount, so a
// mount it refuses (BUSY, MOUNT_FULL, PARAMETER, NOT_FOUND, EXISTS, NO_PERMISSION) leaves the result as it was, e.g. the
// mount point of the save already mounted there. AnyPS5 (boykopovar/AnyPS5, GPL-2.0-only) also writes it on success only
// (core/libs/prx/libSceSaveData.native/Export.cpp @ 4f41f4c37, mount3). Neither cites a console measurement.
// On: KYTY_BC5_SAVEDATA_FIXES set, non-empty and not "0", read once. Off: today's path (the result cleared before any
// check). One stderr line either way, at the first read (the library's registration, InitSaveData_1).
// The other commits of item 9 have blocks and switches of their own (reasons in
// experiments/0401-mesa-preamble-switches/sav0401-notes.md): AnyPS5 0d0abe09c and bc6b4d76f with the event callback
// (KYTY_BC5_SAVEDATA_EVENT_CB, before queue_save_data_event) and KytyPS5 4b0282e's mtime key (KYTY_BC5_SAVEDATA_SORT,
// before save_data_load_param).
static bool bc5_savedata_fixes_on() {
\tstatic const bool on = [] {
\t\tconst char* e = std::getenv("KYTY_BC5_SAVEDATA_FIXES");
\t\tconst bool  v = e != nullptr && e[0] != '\\0' && std::strcmp(e, "0") != 0;
\t\tstd::fprintf(stderr, "[bc5] exp 0401: savedata fixes %s\\n", v ? "on" : "off");
\t\treturn v;
\t}();
\treturn on;
}

"""

# ---- SaveDataMount3: the clearing before the checks stays for the switch off ---------------------------------------
HEAD_OLD = b"""\t     mount->mount_mode, mount->resource);

\t*mount_result = {};

\tCommon::LockGuard lock(g_mount_mutex);
"""
HEAD_NEW = b"""\t     mount->mount_mode, mount->resource);

\tif (!bc5_savedata_fixes_on()) { // experiment 0401 series e4: off, today's clearing before the checks
\t\t*mount_result = {};
\t}

\tCommon::LockGuard lock(g_mount_mutex);
"""

# ---- SaveDataMount3: on, the clearing moves to the success path (KytyPS5 dfec14a) ----------------------------------
TAIL_OLD = b"\treturn mount_save_data(slot, dir_name, mount_dir, created ? 1u : 0u, mount_result);\n"
TAIL_NEW = (b"\tif (bc5_savedata_fixes_on()) { // experiment 0401 series e4 (KytyPS5 dfec14a): cleared only on the way to a mount\n"
            b"\t\t*mount_result = {};\n"
            b"\t}\n" + TAIL_OLD)

# ---- the stderr lines at registration (the first one is the fixes switch's, as in the first port) --------------------
REG_OLD = b"LIB_DEFINE(InitSaveData_1) {\n"
REG_NEW = REG_OLD + (
    b"\t(void)SaveData::bc5_savedata_fixes_on(); // experiment 0401 series e4: the switch's stderr line, read once\n"
    b"\t(void)SaveData::bc5_savedata_event_cb_on(); // experiment 0401 series e4: the event callback switch's line\n"
    b"\t(void)SaveData::bc5_savedata_sort_on(); // experiment 0401 series e4: the sort switch's line\n")

# =============================== KYTY_BC5_SAVEDATA_EVENT_CB (AnyPS5 0d0abe09c, bc6b4d76f) ================================

INC_OLD = b'#include "kernel/fileSystem.h"\n'
INC_NEW = INC_OLD + b'#include "kernel/pthread.h" // experiment 0401 series e4: the event callback\'s delivery thread\n'

SYSINC_OLD = b"#include <vector>\n\nnamespace Libs {\n"
SYSINC_NEW = b"""#include <vector>
// experiment 0401 series e4 (KYTY_BC5_SAVEDATA_EVENT_CB): the event callback's delivery thread and its state
#include <condition_variable>
#include <memory>
#include <thread>
#include <utility>

namespace Libs {
"""

# ---- the switch, the delivery thread and the two exports, just before queue_save_data_event ------------------------
CB_ANCHOR = b"static void queue_save_data_event(uint32_t type, int32_t user_id,\n"
CB_BLOCK = b"""// ---- experiment 0401 series e4: SaveData event callback (exp 0402 Top 10 item 9), switch KYTY_BC5_SAVEDATA_EVENT_CB ----
// Ported from AnyPS5 (github.com/boykopovar/AnyPS5, GPL-2.0-only; the ported lines keep its authors' copyright),
// core/libs/prx/libSceSaveData.native/Export.cpp @ 4f41f4c37 (4f41f4c375f5abb487dbd184fbc150f31994d762): the delivery
// thread and its state (EventDelivery, EventWorker, EventCallbacks, DeliverEvents, StartEventDelivery,
// DetachEventDelivery, JoinEventDelivery, InEventCallback, DeliverEvent: 69-163), sceSaveDataRegisterEventCallback
// (1871-1886), sceSaveDataUnregisterEventCallback (2019-2027), and the initialization count of sceSaveDataInitialize3
// (1059-1064) and sceSaveDataTerminate (1398-1419). That state has AnyPS5's two fixes: 0d0abe09c
// (0d0abe09c19c85d61ac3f2227876a0c83037d6c8: the delivery thread starts at the first successful registration of an
// initialization, not in Initialize3; a replacing registration, one from inside a callback and one after an unregister
// reuse it; the final terminate joins it outside the lock, and only when one was started) and bc6b4d76f
// (bc6b4d76f90dab36a47bc06789c11aa4d81bbeca: registration takes the calling lock, then the slot lock the final terminate
// holds, and only under both checks the count and stores the callback, so no registration outlives that terminate).
// NIDs hsKd5c21sQc (sceSaveDataRegisterEventCallback) and v-AK1AxQhS0 (sceSaveDataUnregisterEventCallback), from exp
// 0327's calculator (nid0401.py's). Nothing here is measured on a console: AnyPS5's docs/dev/debt/libSceSaveData.native.md
// says it follows shadPS4 #5226 and assumes PS4's signatures for PS5.
// Fitted to this file:
//  - Every event queue_save_data_event queues (type 1 Umount2 BACKUP_ASYNC, 2 Backup, 4 Commit BACKUP_ASYNC) still goes
//    to the queue SaveDataGetEventResult polls, then to the callback registered at that moment, as AnyPS5's backups do
//    (its types 1 and 2; it queues nothing on a commit). A polling title sees every event as before.
//  - The poll queue gets a lock of its own, taken by the queueing, the poll and Terminate (it had none: the delivery
//    thread's callbacks may queue and poll from one more thread).
//  - g_mount_mutex stands for AnyPS5's g_slots_mutex (it is recursive here). The count is kept under it and counts only
//    with the switch on. Terminate keeps this file's rules (BUSY while any save is mounted; OK when nothing was
//    initialized; the poll queue cleared) and adds AnyPS5's BUSY from inside a callback and the delivery thread's stop.
//  - The thread is a guest thread of this host (LibKernel::PthreadCreate, as AnyPS5's scePthreadCreate), so the title's
//    callback runs on a guest stack and thread. The delivering thread is told by its host thread id (AnyPS5: Pthread).
//  - This host builds without exceptions: a thread that cannot start makes the registration SAVE_DATA_ERROR_INTERNAL, and
//    a join that fails leaves the worker allocated and prints a line (AnyPS5 throws std::runtime_error for both).
// On: KYTY_BC5_SAVEDATA_EVENT_CB set, non-empty and not "0", read once; both NIDs are registered in both SaveData tables.
// Off: neither is registered (a title that imports them gets the loader's stub, as today) and none of this runs: the poll
// queue, Initialize3 and Terminate are today's. One stderr line either way, at the library's registration.
static bool bc5_savedata_event_cb_on() {
\tstatic const bool on = [] {
\t\tconst char* e = std::getenv("KYTY_BC5_SAVEDATA_EVENT_CB");
\t\tconst bool  v = e != nullptr && e[0] != '\\0' && std::strcmp(e, "0") != 0;
\t\tstd::fprintf(stderr, "[bc5] exp 0401: savedata event callback %s\\n", v ? "on" : "off");
\t\treturn v;
\t}();
\treturn on;
}

using SaveDataEventCallback = KYTY_SYSV_ABI void (*)(const SaveDataEvent* event, void* userdata);

struct Bc5EventDelivery {
\tSaveDataEvent         event;
\tSaveDataEventCallback callback;
\tvoid*                 userdata;
};

struct Bc5EventWorker {
\tLibKernel::Pthread thread   = nullptr;
\tbool               stopping = false;
};

struct Bc5EventCallbacks {
\tstd::recursive_mutex         calling;
\tstd::mutex                   mutex;
\tstd::condition_variable      wake;
\tSaveDataEventCallback        callback = nullptr;
\tvoid*                        userdata = nullptr;
\tstd::deque<Bc5EventDelivery> pending;
\tBc5EventWorker*              worker = nullptr;
\tstd::thread::id              delivering; // the thread in a callback now, none otherwise
};

static std::mutex g_bc5_save_data_events_mutex; // g_save_data_events, with the switch on
static int        g_bc5_initializations = 0;   // under g_mount_mutex, counted with the switch on

static Bc5EventCallbacks& bc5_event_callbacks() {
\tstatic auto* callbacks = new Bc5EventCallbacks; // never destroyed, as AnyPS5's
\treturn *callbacks;
}

// The poll queue's lock: taken with the switch on, an empty lock (today's unlocked queue) with it off.
static std::unique_lock<std::mutex> bc5_save_data_events_lock() {
\treturn bc5_savedata_event_cb_on() ? std::unique_lock<std::mutex>(g_bc5_save_data_events_mutex)
\t                                  : std::unique_lock<std::mutex>();
}

static KYTY_SYSV_ABI void* bc5_deliver_events(void* argument) {
\tauto& callbacks = bc5_event_callbacks();
\tauto* worker    = static_cast<Bc5EventWorker*>(argument);
\tfor (;;) {
\t\t{
\t\t\tstd::unique_lock lock(callbacks.mutex);
\t\t\tcallbacks.wake.wait(lock, [&] { return worker->stopping || !callbacks.pending.empty(); });
\t\t\tif (worker->stopping) {
\t\t\t\treturn nullptr;
\t\t\t}
\t\t}
\t\tstd::lock_guard  calling(callbacks.calling);
\t\tBc5EventDelivery delivery {};
\t\t{
\t\t\tstd::lock_guard lock(callbacks.mutex);
\t\t\tif (worker->stopping) {
\t\t\t\treturn nullptr;
\t\t\t}
\t\t\tif (callbacks.pending.empty()) {
\t\t\t\tcontinue;
\t\t\t}
\t\t\tdelivery = callbacks.pending.front();
\t\t\tcallbacks.pending.pop_front();
\t\t\tcallbacks.delivering = std::this_thread::get_id();
\t\t}
\t\tdelivery.callback(&delivery.event, delivery.userdata);
\t\tstd::lock_guard lock(callbacks.mutex);
\t\tcallbacks.delivering = {};
\t}
}

static bool bc5_start_event_delivery() {
\tauto&           callbacks = bc5_event_callbacks();
\tauto            worker    = std::make_unique<Bc5EventWorker>();
\tstd::lock_guard lock(callbacks.mutex);
\tif (callbacks.worker != nullptr) {
\t\treturn true;
\t}
\tif (LibKernel::PthreadCreate(&worker->thread, nullptr, bc5_deliver_events, worker.get(),
\t                            "SceSaveDataEventCallback") != OK) {
\t\treturn false;
\t}
\tcallbacks.worker = worker.release();
\treturn true;
}

static Bc5EventWorker* bc5_detach_event_delivery() {
\tauto&           callbacks = bc5_event_callbacks();
\tstd::lock_guard lock(callbacks.mutex);
\tcallbacks.callback = nullptr;
\tcallbacks.userdata = nullptr;
\tcallbacks.pending.clear();
\tauto* worker = std::exchange(callbacks.worker, nullptr);
\tif (worker != nullptr) {
\t\tworker->stopping = true;
\t}
\treturn worker;
}

static void bc5_join_event_delivery(Bc5EventWorker* worker) {
\tbc5_event_callbacks().wake.notify_all();
\tconst int rc = LibKernel::PthreadJoin(worker->thread, nullptr);
\tif (rc != OK) {
\t\tstd::fprintf(stderr, "[bc5] exp 0401: the savedata event thread did not join (%d); its worker is kept\\n", rc);
\t\treturn;
\t}
\tdelete worker;
}

static bool bc5_in_event_callback() {
\tauto&           callbacks = bc5_event_callbacks();
\tstd::lock_guard lock(callbacks.mutex);
\treturn callbacks.delivering == std::this_thread::get_id();
}

static void bc5_deliver_event(const SaveDataEvent& event) {
\tauto& callbacks = bc5_event_callbacks();
\t{
\t\tstd::lock_guard lock(callbacks.mutex);
\t\tif (callbacks.callback == nullptr || callbacks.worker == nullptr) {
\t\t\treturn;
\t\t}
\t\tcallbacks.pending.push_back({event, callbacks.callback, callbacks.userdata});
\t}
\tcallbacks.wake.notify_all();
}

// SaveDataTerminate with the switch on: AnyPS5's sceSaveDataTerminate on this file's rules.
static int bc5_terminate() {
\tif (bc5_in_event_callback()) {
\t\treturn SAVE_DATA_ERROR_BUSY;
\t}
\tBc5EventWorker* stopped = nullptr;
\t{
\t\tCommon::LockGuard lock(g_mount_mutex);
\t\tif (!g_mount_slots.Empty()) {
\t\t\treturn SAVE_DATA_ERROR_BUSY;
\t\t}
\t\t{
\t\t\tstd::lock_guard events(g_bc5_save_data_events_mutex);
\t\t\tg_save_data_events.clear();
\t\t}
\t\tif (g_bc5_initializations > 0 && --g_bc5_initializations == 0) {
\t\t\tstopped = bc5_detach_event_delivery();
\t\t}
\t}
\tif (stopped != nullptr) {
\t\tbc5_join_event_delivery(stopped);
\t}
\treturn OK;
}

int KYTY_SYSV_ABI SaveDataRegisterEventCallback(SaveDataEventCallback callback, void* userdata) {
\tPRINT_NAME();

\tLOGF("\\t callback = 0x%016" PRIx64 "\\n"
\t     "\\t userdata = 0x%016" PRIx64 "\\n",
\t     reinterpret_cast<uint64_t>(callback), reinterpret_cast<uint64_t>(userdata));

\tauto&                                 callbacks = bc5_event_callbacks();
\tstd::lock_guard<std::recursive_mutex> calling(callbacks.calling);
\tCommon::LockGuard                     slots(g_mount_mutex);
\tif (g_bc5_initializations == 0) {
\t\treturn SAVE_DATA_ERROR_NOT_INITIALIZED;
\t}
\tif (callback == nullptr) {
\t\treturn SAVE_DATA_ERROR_PARAMETER;
\t}
\tif (!bc5_start_event_delivery()) {
\t\treturn SAVE_DATA_ERROR_INTERNAL;
\t}
\tstd::lock_guard lock(callbacks.mutex);
\tcallbacks.callback = callback;
\tcallbacks.userdata = userdata;
\treturn OK;
}

int KYTY_SYSV_ABI SaveDataUnregisterEventCallback() {
\tPRINT_NAME();

\tauto&                                 callbacks = bc5_event_callbacks();
\tstd::lock_guard<std::recursive_mutex> calling(callbacks.calling);
\tstd::lock_guard                       lock(callbacks.mutex);
\tcallbacks.callback = nullptr;
\tcallbacks.userdata = nullptr;
\tcallbacks.pending.clear();
\treturn OK;
}
// ---- end of experiment 0401 series e4's event callback block ----

"""

# ---- queue_save_data_event: on, the queue under its lock, then the event to the callback ---------------------------
QUEUE_OLD = b"""\tg_save_data_events.push_back(event);
\tif (g_save_data_events.size() > 20) {
\t\tg_save_data_events.pop_front();
\t}
}
"""
QUEUE_NEW = b"""\tstd::unique_lock<std::mutex> bc5_events_lock = bc5_save_data_events_lock(); // experiment 0401 series e4: on, locked
\tg_save_data_events.push_back(event);
\tif (g_save_data_events.size() > 20) {
\t\tg_save_data_events.pop_front();
\t}
\tif (bc5_events_lock.owns_lock()) { // experiment 0401 series e4 (switch on): then to the registered callback
\t\tbc5_events_lock.unlock();
\t\tbc5_deliver_event(event);
\t}
}
"""

# ---- SaveDataInitialize3: on, the count the registration checks (AnyPS5 sceSaveDataInitialize3) --------------------
INIT_OLD = b"""\t// EXIT_NOT_IMPLEMENTED(init != nullptr);

\treturn OK;
}
"""
INIT_NEW = b"""\t// EXIT_NOT_IMPLEMENTED(init != nullptr);
\tif (bc5_savedata_event_cb_on()) { // experiment 0401 series e4 (AnyPS5 sceSaveDataInitialize3): the count
\t\tCommon::LockGuard lock(g_mount_mutex);
\t\tg_bc5_initializations++;
\t}

\treturn OK;
}
"""

# ---- SaveDataTerminate: on, the count and the delivery thread's stop -------------------------------------------------
TERM_OLD = b"""int KYTY_SYSV_ABI SaveDataTerminate() {
\tPRINT_NAME();

\tCommon::LockGuard lock(g_mount_mutex);
"""
TERM_NEW = b"""int KYTY_SYSV_ABI SaveDataTerminate() {
\tPRINT_NAME();

\tif (bc5_savedata_event_cb_on()) { // experiment 0401 series e4: with the count and the delivery thread's stop
\t\treturn bc5_terminate();
\t}
\tCommon::LockGuard lock(g_mount_mutex);
"""

# ---- SaveDataGetEventResult: on, the poll under the queue's lock ---------------------------------------------------
POLL_OLD = b"""\tif (g_save_data_events.empty()) {
\t\treturn SAVE_DATA_ERROR_NOT_FOUND;
\t}
"""
POLL_NEW = (b"\tstd::unique_lock<std::mutex> bc5_events_lock = bc5_save_data_events_lock(); // experiment 0401 series e4: on, locked\n"
            + POLL_OLD)

# ---- the two exports, on only, in both tables (this file registers every SaveData NID in both) ---------------------
NATIVE_OLD = b"""\tLIB_FUNC("yKDy8S5yLA0", ::Libs::SaveData::SaveDataTerminate);
}

} // namespace LibSaveDataNative
"""
NATIVE_NEW = b"""\tLIB_FUNC("yKDy8S5yLA0", ::Libs::SaveData::SaveDataTerminate);
\tif (::Libs::SaveData::bc5_savedata_event_cb_on()) { // experiment 0401 series e4: AnyPS5's event callback exports
\t\tLIB_FUNC("hsKd5c21sQc", ::Libs::SaveData::SaveDataRegisterEventCallback);
\t\tLIB_FUNC("v-AK1AxQhS0", ::Libs::SaveData::SaveDataUnregisterEventCallback);
\t}
}

} // namespace LibSaveDataNative
"""
TABLE_OLD = b"""\tLIB_FUNC("yKDy8S5yLA0", SaveData::SaveDataTerminate);

\tLibSaveDataNative::InitSaveDataNative_1(s);
"""
TABLE_NEW = b"""\tLIB_FUNC("yKDy8S5yLA0", SaveData::SaveDataTerminate);
\tif (SaveData::bc5_savedata_event_cb_on()) { // experiment 0401 series e4: AnyPS5's event callback exports
\t\tLIB_FUNC("hsKd5c21sQc", SaveData::SaveDataRegisterEventCallback);
\t\tLIB_FUNC("v-AK1AxQhS0", SaveData::SaveDataUnregisterEventCallback);
\t}

\tLibSaveDataNative::InitSaveDataNative_1(s);
"""

# =============================== KYTY_BC5_SAVEDATA_SORT (KytyPS5 4b0282e's mtime key) ====================================

SORT_ANCHOR = b"// The param the title set, or zeros; an mtime of 0 becomes the directory's time (run 573).\n"
SORT_BLOCK = b"""// ---- experiment 0401 series e4: SaveData sort keys (exp 0402 Top 10 item 9), switch KYTY_BC5_SAVEDATA_SORT ----
// Ported from KytyPS5 (github.com/KytyPS5/KytyPS5, GPL-2.0, as KytyPlus; the ported lines keep its authors' copyright),
// src/libs/libSaveData.cpp @ dfec14a (dfec14aa8c59f8ea2bc4d87eba9854fc370161c6), newest_save_time and load_save_param
// (411-440): the mtime its search sorts by since 4b0282e (4b0282e3430ec64b5012d1c5c5a90f495f05df76, "savedata: sort
// directory searches by the requested key") and that its search and GetParam report. A save's mtime is the newest write
// time of its files, whatever the title put in the param's mtime. shadPS4 (param.sfo's write time) and AnyPS5 @ 4f41f4c37
// (the time of the last SetParam) do not take the title's mtime either; this file did.
// Fitted to this file: KytyPS5 keeps the param and the blocks record inside the save (sce_sys/param.bin,
// sce_sys/blocks.bin), where they count among its files; this file keeps them beside it (<dir>.param, <dir>.blocks), so
// they count from there. A save with no file at all keeps this file's rule (run 573: the directory's time), not 0.
// Of the three key definitions in which this file differs from KytyPS5 4b0282e only this one is ported. Kept as they are
// (reasons in experiments/0401-mesa-preamble-switches/sav0401-notes.md): free blocks (here the save's blocks less its
// files, as shadPS4 and AnyPS5 sort and report them; KytyPS5 reports its total as free and sorts by it) and a save without
// a blocks record (here the maximum, as shadPS4 and AnyPS5; KytyPS5 sorts it as 0 and its search and GetMountInfo report
// it BROKEN).
// On: KYTY_BC5_SAVEDATA_SORT set, non-empty and not "0", read once; save_data_load_param takes the files' time (the
// search's mtime order and the params it returns, and GetParam). Off: today's (the title's mtime, else the directory's).
// One stderr line either way, at the library's registration.
static bool bc5_savedata_sort_on() {
\tstatic const bool on = [] {
\t\tconst char* e = std::getenv("KYTY_BC5_SAVEDATA_SORT");
\t\tconst bool  v = e != nullptr && e[0] != '\\0' && std::strcmp(e, "0") != 0;
\t\tstd::fprintf(stderr, "[bc5] exp 0401: savedata sort %s\\n", v ? "on" : "off");
\t\treturn v;
\t}();
\treturn on;
}

// KytyPS5 newest_save_time: the newest write time, in seconds, of the regular files in the save, 0 if it has none; here
// with the save's two records beside it.
static int64_t bc5_newest_save_time(const std::string& directory) {
\tint64_t     newest = 0;
\tstruct stat st {};
\tfor (const std::string& record: {save_data_param_path(directory), save_data_blocks_path(directory)}) {
\t\tstd::error_code record_ec;
\t\tif (std::filesystem::is_regular_file(record, record_ec) && ::stat(record.c_str(), &st) == 0) {
\t\t\tnewest = std::max<int64_t>(newest, st.st_mtime);
\t\t}
\t}
\tstd::error_code ec;
\tfor (auto it = std::filesystem::recursive_directory_iterator(
\t         directory, std::filesystem::directory_options::skip_permission_denied, ec);
\t     !ec && it != std::filesystem::recursive_directory_iterator(); it.increment(ec)) {
\t\tstd::error_code file_ec;
\t\tif (it->is_regular_file(file_ec) && ::stat(it->path().string().c_str(), &st) == 0) {
\t\t\tnewest = std::max<int64_t>(newest, st.st_mtime);
\t\t}
\t}
\treturn newest;
}
// ---- end of experiment 0401 series e4's sort block ----

"""

LOAD_OLD = b"""\tif (param.mtime == 0) {
\t\tparam.mtime = save_data_dir_mtime(directory);
\t}
\treturn param;
}
"""
LOAD_NEW = (b"\tif (bc5_savedata_sort_on()) { // experiment 0401 series e4 (KytyPS5 load_save_param): the files' newest time\n"
            b"\t\tparam.mtime = bc5_newest_save_time(directory);\n"
            b"\t}\n" + LOAD_OLD)


def once(s, anchor, new, what):
    assert s.count(anchor) == 1, (what, anchor[:70], s.count(anchor))
    return s.replace(anchor, new)


def edit(s):
    for m in MARKS:
        assert m not in s, ("libSaveData.cpp has the edit already", m)
    # the two clearings of the result the fixes are about: Mount3's (moved) and TransferringMount's (left as it is)
    assert s.count(b"\t*mount_result = {};\n") == 2, ("the result clearings", s.count(b"\t*mount_result = {};\n"))
    # the poll queue: filled in queue_save_data_event only, read in GetEventResult only, cleared in Terminate only
    assert s.count(b"g_save_data_events.push_back(") == 1 and s.count(b"g_save_data_events.front()") == 1, "the queue"
    assert s.count(b"g_save_data_events.clear()") == 1, "the queue's clearing"
    # KYTY_BC5_SAVEDATA_FIXES (the first port, unchanged in behaviour)
    s = once(s, SWITCH_ANCHOR, SWITCH + SWITCH_ANCHOR, "the switch before mount_save_data")
    s = once(s, HEAD_OLD, HEAD_NEW, "SaveDataMount3's clearing")
    s = once(s, TAIL_OLD, TAIL_NEW, "SaveDataMount3's return")
    s = once(s, REG_OLD, REG_NEW, "InitSaveData_1")
    # KYTY_BC5_SAVEDATA_EVENT_CB
    s = once(s, INC_OLD, INC_NEW, "the include of kernel/fileSystem.h")
    s = once(s, SYSINC_OLD, SYSINC_NEW, "the last system include")
    s = once(s, CB_ANCHOR, CB_BLOCK + CB_ANCHOR, "the event callback block before queue_save_data_event")
    s = once(s, QUEUE_OLD, QUEUE_NEW, "queue_save_data_event's push")
    s = once(s, INIT_OLD, INIT_NEW, "SaveDataInitialize3")
    s = once(s, TERM_OLD, TERM_NEW, "SaveDataTerminate")
    s = once(s, POLL_OLD, POLL_NEW, "SaveDataGetEventResult's poll")
    s = once(s, NATIVE_OLD, NATIVE_NEW, "InitSaveDataNative_1's end")
    s = once(s, TABLE_OLD, TABLE_NEW, "InitSaveData_1's end")
    # KYTY_BC5_SAVEDATA_SORT
    s = once(s, SORT_ANCHOR, SORT_BLOCK + SORT_ANCHOR, "the sort block before save_data_load_param")
    s = once(s, LOAD_OLD, LOAD_NEW, "save_data_load_param's mtime")
    # each switch function: its definition and its uses
    assert s.count(MARK_FN) == 4, ("uses of the fixes switch", s.count(MARK_FN))
    assert s.count(CB_FN) == 7, ("uses of the event callback switch", s.count(CB_FN))
    assert s.count(SORT_FN) == 3, ("uses of the sort switch", s.count(SORT_FN))
    assert s.count(b"bc5_save_data_events_lock()") == 3, "the queue's lock: its definition, the push, the poll"
    return s


def main():
    assert len(sys.argv) == 3, __doc__
    root, out = sys.argv[1], sys.argv[2]
    with open(os.path.join(root, REL), "rb") as f:
        s = f.read()
    o = edit(s)
    p = os.path.join(out, REL)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as f:
        f.write(o)
    print(f"{hashlib.md5(o).hexdigest()}  {REL}")


if __name__ == "__main__":
    main()
