#!/usr/bin/env python3
"""BC5 experiment 0401 series e5, port group "svc" (exp 0405's top-32 rows 19-22 and four extras): SaveData memory sync,
the SaveData queue lock, existed_memory_size, a busy delete and the Initialize aliases in src/libs/libSaveData.cpp; the
Http2 async user event, Http2 SSL options on a context and a NULL user agent for HttpCreateTemplate in src/libs/libNet.cpp;
scePadOpenExt in src/libs/libPad.cpp. Every item is behind a switch, default off; off is today's path (the old code kept,
branched on the switch). Switches, each read once, each with one stderr line "[bc5] exp 0405: <group> on (items: ...)" or
"... off" at its library's registration; "on" when set, non-empty and not "0"; a value naming items (comma list) turns on
only those, any other value all of them:
  KYTY_BC5_SAVEDATA_MEMORY_FIXES  items sync (R2 KS03+SS01), lock (R2 KS02), existed (R2 KS09+SS02)   libSaveData.cpp
  KYTY_BC5_SAVEDATA_DELETE_BUSY   item delete (R2 KS14+SS10)                                          libSaveData.cpp
  KYTY_BC5_SAVEDATA_ALIASES       item initialize (R1 #15: Initialize and Initialize2)                libSaveData.cpp
  KYTY_BC5_HTTP2_FIXES            items async (R2 KS01), ssl (R1 #18), agent (R2 KS04)                libNet.cpp
  KYTY_BC5_PAD_OPEN_EXT           item openext (R2 SS22+KS69)                                         libPad.cpp
Sources, licences and the reasons per item: the comment blocks below and svc0405-notes.md.
Inputs: the e5 input tree (KytyPlus f266548 + patch 0001 + e4's private units); each input's md5 is pinned and asserted.
libSaveData.cpp is e4's private unit 04f4c5bb (mksav0401.py's output): its three switches keep their behaviour.
Each anchor must occur exactly once; an input that has any of the edit already is refused; anchors are written with LF
and converted to the file's line ending; the inserted text is ASCII. Prints "<rel> <md5>" for each output.
usage: mksvc0405.py <tree root in> <out dir>"""
import hashlib
import os
import sys

SAV = "src/libs/libSaveData.cpp"
NET = "src/libs/libNet.cpp"
PAD = "src/libs/libPad.cpp"
IN_MD5 = {
    SAV: "04f4c5bb05179b80fd7cf1e41832cdd9",  # e4's private unit (mksav0401.py's output)
    NET: "f7a26ceb10a4cf669c33ed592eb1e89d",  # the base tree's
    PAD: "dbe268d7dff6134db45ad4328aace716",  # the base tree's
}
COMMON_MARKS = (b"series e5", b"exp 0405", b"KYTY_BC5_SAVEDATA_MEMORY_FIXES", b"KYTY_BC5_SAVEDATA_DELETE_BUSY",
                b"KYTY_BC5_SAVEDATA_ALIASES", b"KYTY_BC5_HTTP2_FIXES", b"KYTY_BC5_PAD_OPEN_EXT")


def T(text):
    """C++ text written with a visible tab ("»") for each tab, as ASCII bytes with LF line ends."""
    out = text.replace("»", "\t").encode("ascii")
    assert b"\r" not in out
    return out


# ======================================================================================================================
# src/libs/libSaveData.cpp
# ======================================================================================================================

SAV_MARKS = (b"bc5_savedata_memory_fix", b"bc5_savedata_delete_busy_on", b"bc5_savedata_aliases_on",
             b"Bc5SaveDataMemorySync", b"bc5_sync_save_data_memory", b"g_bc5_memory_set_up", b"Bc5MountLockIf",
             b"bc5_save_data_memory_file_size", b"l1NmDeDpNGU", b"ZkZhskCPXFw", b"MEMORY_SYNC_END")

# ---- the switches and the shared state, before e4's event callback block (which uses the "lock" item) ---------------
SAV_TOP_ANCHOR = T("// ---- experiment 0401 series e4: SaveData event callback (exp 0402 Top 10 item 9), switch "
                   "KYTY_BC5_SAVEDATA_EVENT_CB ----\n")
SAV_TOP = T(r"""// ---- experiment 0401 series e5: SaveData memory, queue lock, busy delete, Initialize aliases (exp 0405) ----------
// KYTY_BC5_SAVEDATA_MEMORY_FIXES (exp 0405 top-32 rows 19 and 20). Items, comma-separated; a value naming none of them (any
// value set, non-empty and not "0") turns all three on:
//  - "sync" (R2 KS03 + SS01): sceSaveDataSyncSaveDataMemory (wiT9jeC7xPw) checks its argument (PARAMETER for a null one,
//    a slot of 4 or more or an option over 1; INVALID_LOGIN_USER for a negative user), answers MEMORY_NOT_READY for a
//    slot that no SetupSaveDataMemory2 set up, writes the memory file and, unless option is 1, queues the MEMORY_SYNC_END
//    event (type 3) that a title polling SaveDataGetEventResult waits for; option 1 returns the write's status only.
//    Today it returns OK and queues nothing, so such a title polls NOT_FOUND forever (sharpemu's comment: what wedged
//    Dead Cells at FLIP 0). Ported from KytyPS5 (github.com/KytyPS5/KytyPS5, GPL-2.0, as KytyPlus; the ported lines keep
//    its authors' copyright) dfec14a src/libs/libSaveData.cpp:197-202 (SaveDataMemorySync), 267 (MEMORY_SYNC_END = 3),
//    1151-1182 (SaveDataSyncSaveDataMemory); sharpemu (GPL-2.0-or-later) SharpEmu.Libs/SaveData/SaveDataExports.cs:78,
//    1571-1609 at 514d766 (added in 9415395) and shadPS4 60c42b9 src/core/libraries/save_data/savedata.cpp:1637-1665 with
//    save_backup.h:26
//    (GPL-2.0-or-later, SAVE_DATA_MEMORY_SYNC = 3) agree on the event. Fitted to this file: its memory is one store for
//    every slot (sce_sdmemory/memory.dat), so "set up" is kept per slot 0-3 as KytyPS5 and shadPS4 keep it, the write is
//    save_data_memory_store, and the event names the slot's directory ("sce_sdmemory", "sce_sdmemory1", ...) as KytyPS5
//    does. KytyPS5's BUSY for a memory directory mounted through Mount3 is not taken (this file never mounts it).
//  - "lock" (R2 KS02; KytyPS5 dfec14a libs/libSaveData.cpp:1027-1028, 1191, 1275-1276 take its mount mutex there): the
//    poll queue g_save_data_events is queued, polled and cleared under a lock also with KYTY_BC5_SAVEDATA_EVENT_CB off; the
//    lock is e4's g_bc5_save_data_events_mutex (a leaf lock: nothing is taken under it).
//  - "existed" (R2 KS09 + SS02): SetupSaveDataMemory2's existed_memory_size is the size of the stored memory file before
//    the call, 0 when there is none. Today it is the memory's size, at least 64 KiB, so a title on its first run reads
//    zeros as a save. KytyPS5 dfec14a libs/libSaveData.cpp:457-483 (load_memory), 811-825; sharpemu
//    SaveDataExports.cs:1495-1551 at 514d766, added in 488b285 (the backing file's length before the call); shadPS4
//    savedata.cpp:1580-1603 (0 is "just created").
// KYTY_BC5_SAVEDATA_DELETE_BUSY (R2 KS14 + SS10; KytyPS5 dfec14a libs/libSaveData.cpp:1051-1056): SaveDataDelete of a save
//   that is mounted is BUSY and deletes nothing; the mount lock is held to the end of the delete. Today it removes the
//   files under the open mount. KytyPS5's use of del->title_id is not taken (it needs KS17's name checks, held).
// KYTY_BC5_SAVEDATA_ALIASES (R1 #15): sceSaveDataInitialize (ZkZhskCPXFw) and sceSaveDataInitialize2 (l1NmDeDpNGU) are
//   SaveDataInitialize3 in both SaveData tables: AnyPS5 bc6a5e4ea core/libs/prx/libSceSaveData.native/Export.cpp:1817,
//   2070 (GPL-2.0-only), shadPS4 60c42b9 savedata.cpp:1194-1210, 1817-1819 (all three initialize alike). NIDs from exp
//   0327's calculator (nid0401.py's), which gives these two for those names.
// Nothing here is measured on a console. Off (unset, empty or "0"): today's path, the old code kept. One stderr line per
// switch, at the library's registration (InitSaveData_1).
static constexpr uint32_t BC5_SDM_FIX_SYNC    = 1u; // "sync"
static constexpr uint32_t BC5_SDM_FIX_LOCK    = 2u; // "lock"
static constexpr uint32_t BC5_SDM_FIX_EXISTED = 4u; // "existed"
static constexpr uint32_t BC5_SDM_FIX_ALL     = BC5_SDM_FIX_SYNC | BC5_SDM_FIX_LOCK | BC5_SDM_FIX_EXISTED;

static constexpr uint32_t BC5_SAVE_DATA_EVENT_TYPE_MEMORY_SYNC_END = 3u; // KytyPS5 dfec14a :267, shadPS4 save_backup.h:26
static constexpr uint32_t BC5_SAVE_DATA_MEMORY_SLOTS               = 4u; // KytyPS5 dfec14a :1154 (slot_id >= 4)

static uint32_t bc5_savedata_memory_fixes_parse(const char* e) {
»if (e == nullptr || e[0] == '\0' || std::strcmp(e, "0") == 0) {
»»return 0;
»}
»uint32_t    items = 0;
»const char* p     = e;
»for (;;) {
»»const char*  comma = std::strchr(p, ',');
»»const size_t n     = comma != nullptr ? static_cast<size_t>(comma - p) : std::strlen(p);
»»if (n == 4 && std::strncmp(p, "sync", n) == 0) {
»»»items |= BC5_SDM_FIX_SYNC;
»»} else if (n == 4 && std::strncmp(p, "lock", n) == 0) {
»»»items |= BC5_SDM_FIX_LOCK;
»»} else if (n == 7 && std::strncmp(p, "existed", n) == 0) {
»»»items |= BC5_SDM_FIX_EXISTED;
»»}
»»if (comma == nullptr) {
»»»break;
»»}
»»p = comma + 1;
»}
»return items != 0 ? items : BC5_SDM_FIX_ALL;
}

// The items of KYTY_BC5_SAVEDATA_MEMORY_FIXES that are on (0: off), read once.
static uint32_t bc5_savedata_memory_fixes() {
»static const uint32_t items = [] {
»»const uint32_t v = bc5_savedata_memory_fixes_parse(std::getenv("KYTY_BC5_SAVEDATA_MEMORY_FIXES"));
»»if (v == 0) {
»»»std::fprintf(stderr, "[bc5] exp 0405: savedata memory fixes off\n");
»»} else {
»»»std::fprintf(stderr, "[bc5] exp 0405: savedata memory fixes on (items:%s%s%s)\n",
»»»             (v & BC5_SDM_FIX_SYNC) != 0 ? " sync" : "", (v & BC5_SDM_FIX_LOCK) != 0 ? " lock" : "",
»»»             (v & BC5_SDM_FIX_EXISTED) != 0 ? " existed" : "");
»»}
»»return v;
»}();
»return items;
}

static bool bc5_savedata_memory_fix(uint32_t item) {
»return (bc5_savedata_memory_fixes() & item) != 0;
}

static bool bc5_savedata_delete_busy_on() {
»static const bool on = [] {
»»const char* e = std::getenv("KYTY_BC5_SAVEDATA_DELETE_BUSY");
»»const bool  v = e != nullptr && e[0] != '\0' && std::strcmp(e, "0") != 0;
»»std::fprintf(stderr, "[bc5] exp 0405: savedata delete busy %s\n", v ? "on (items: delete)" : "off");
»»return v;
»}();
»return on;
}

static bool bc5_savedata_aliases_on() {
»static const bool on = [] {
»»const char* e = std::getenv("KYTY_BC5_SAVEDATA_ALIASES");
»»const bool  v = e != nullptr && e[0] != '\0' && std::strcmp(e, "0") != 0;
»»std::fprintf(stderr, "[bc5] exp 0405: savedata aliases %s\n", v ? "on (items: initialize)" : "off");
»»return v;
»}();
»return on;
}

// "sync": the memory slots a SetupSaveDataMemory2 set up, under g_save_data_memory_mutex; kept with the item on only.
static bool g_bc5_memory_set_up[BC5_SAVE_DATA_MEMORY_SLOTS] = {};

// KYTY_BC5_SAVEDATA_DELETE_BUSY: g_mount_mutex held for the scope when the switch is on, not taken when it is off.
struct Bc5MountLockIf {
»explicit Bc5MountLockIf(bool on): held(on) {
»»if (held) {
»»»g_mount_mutex.Lock();
»»}
»}
»~Bc5MountLockIf() {
»»if (held) {
»»»g_mount_mutex.Unlock();
»»}
»}
»Bc5MountLockIf(const Bc5MountLockIf&)            = delete;
»Bc5MountLockIf& operator=(const Bc5MountLockIf&) = delete;
»const bool      held;
};
// ---- end of experiment 0401 series e5's switches ----

""")

# ---- "lock": e4's poll queue lock, also taken with the item on --------------------------------------------------------
SAV_LOCK_OLD = T(r"""static std::unique_lock<std::mutex> bc5_save_data_events_lock() {
»return bc5_savedata_event_cb_on() ? std::unique_lock<std::mutex>(g_bc5_save_data_events_mutex)
»                                  : std::unique_lock<std::mutex>();
}
""")
SAV_LOCK_NEW = T(r"""static std::unique_lock<std::mutex> bc5_save_data_events_lock() {
»// experiment 0401 series e5 (KYTY_BC5_SAVEDATA_MEMORY_FIXES "lock", KytyPS5 dfec14a KS02): also with the item on
»return (bc5_savedata_event_cb_on() || bc5_savedata_memory_fix(BC5_SDM_FIX_LOCK))
»           ? std::unique_lock<std::mutex>(g_bc5_save_data_events_mutex)
»           : std::unique_lock<std::mutex>();
}
""")

# ---- queue_save_data_event: the delivery to a callback stays e4's (event callback on only) ---------------------------
SAV_DELIVER_OLD = T("»if (bc5_events_lock.owns_lock()) { // experiment 0401 series e4 (switch on): then to the registered "
                    "callback\n")
SAV_DELIVER_NEW = T("»if (bc5_events_lock.owns_lock() && bc5_savedata_event_cb_on()) { // experiment 0401 series e4 (switch "
                    "on): then to the registered callback (series e5: not for the \"lock\" item alone)\n")

# ---- SaveDataTerminate, today's path: the clearing under the "lock" item's lock --------------------------------------
SAV_TERM_OLD = T("»}\n»g_save_data_events.clear();\n")
SAV_TERM_NEW = T("»}\n"
                 "»std::unique_lock<std::mutex> bc5_events_lock = bc5_save_data_events_lock(); // experiment 0401 series "
                 "e5: \"lock\" (off: none)\n"
                 "»g_save_data_events.clear();\n")

# ---- save_data_memory_store says whether it wrote (the sync's status); its callers so far ignore it -----------------
SAV_STORE_HEAD_OLD = T("static void save_data_memory_store() {\n")
SAV_STORE_HEAD_NEW = T("static bool save_data_memory_store() { // experiment 0401 series e5: true when written (\"sync\"'s "
                       "status)\n")
SAV_STORE_FAIL1_OLD = T(r"""»»LOGF("\t save data memory: cannot write %s\n", tmp.c_str());
»»return;
""")
SAV_STORE_FAIL1_NEW = T(r"""»»LOGF("\t save data memory: cannot write %s\n", tmp.c_str());
»»return false; // experiment 0401 series e5
""")
SAV_STORE_FAIL2_OLD = T(r"""»»std::remove(tmp.c_str());
»»return;
""")
SAV_STORE_FAIL2_NEW = T(r"""»»std::remove(tmp.c_str());
»»return false; // experiment 0401 series e5
""")
SAV_STORE_END_OLD = T(r"""»LOGF("\t save data memory: %zu bytes written to %s\n", written, path.c_str());
}
""")
SAV_STORE_END_NEW = T(r"""»LOGF("\t save data memory: %zu bytes written to %s\n", written, path.c_str());
»return true; // experiment 0401 series e5
}
""")

# ---- "existed": the stored file's size, before SetupSaveDataMemory2 ----------------------------------------------------
SAV_SETUP_ANCHOR = T("int KYTY_SYSV_ABI SaveDataSetupSaveDataMemory2(const SaveDataMemorySetup2* setup_param,\n")
SAV_SETUP_BLOCK = T(r"""// experiment 0401 series e5 (KYTY_BC5_SAVEDATA_MEMORY_FIXES "existed", R2 KS09 + SS02): the size of the stored memory
// file, 0 when there is none (KytyPS5 dfec14a load_memory, libs/libSaveData.cpp:457-483; sharpemu 514d766, added in
// 488b285, SaveDataExports.cs:1525-1526, the backing file's length before the call).
static size_t bc5_save_data_memory_file_size() {
»std::error_code ec;
»const auto      size = std::filesystem::file_size(save_data_memory_dir() + "/memory.dat", ec);
»return ec ? 0 : static_cast<size_t>(size);
}

""")
SAV_SETUP_OLD = T(r"""»std::lock_guard lock(g_save_data_memory_mutex);
»save_data_memory_load();
»if (setup_param->memory_size > g_save_data_memory.size()) {
»»g_save_data_memory.resize(setup_param->memory_size);
»}

»if (result != nullptr) {
»»*result                     = {};
»»result->existed_memory_size = g_save_data_memory.size();
»}
""")
SAV_SETUP_NEW = T(r"""»std::lock_guard lock(g_save_data_memory_mutex);
»// experiment 0401 series e5 ("existed"): the stored file's size before this call; off: not read
»const size_t bc5_existed = bc5_savedata_memory_fix(BC5_SDM_FIX_EXISTED) ? bc5_save_data_memory_file_size() : 0;
»save_data_memory_load();
»if (setup_param->memory_size > g_save_data_memory.size()) {
»»g_save_data_memory.resize(setup_param->memory_size);
»}
»if (bc5_savedata_memory_fix(BC5_SDM_FIX_SYNC) && setup_param->slot_id < BC5_SAVE_DATA_MEMORY_SLOTS) {
»»g_bc5_memory_set_up[setup_param->slot_id] = true; // experiment 0401 series e5 ("sync"): this slot is ready
»}

»if (result != nullptr) {
»»*result                     = {};
»»result->existed_memory_size = g_save_data_memory.size();
»»if (bc5_savedata_memory_fix(BC5_SDM_FIX_EXISTED)) { // experiment 0401 series e5 (KytyPS5 dfec14a :823, sharpemu 488b285)
»»»result->existed_memory_size = bc5_existed;
»»}
»}
""")

# ---- "sync": SaveDataSyncSaveDataMemory --------------------------------------------------------------------------------
SAV_SYNC_OLD = T(r"""int KYTY_SYSV_ABI SaveDataSyncSaveDataMemory(const void* sync_param) {
»PRINT_NAME();

»LOGF("\t sync_param = 0x%016" PRIx64 "\n", reinterpret_cast<uint64_t>(sync_param));

»return OK;
}
""")
SAV_SYNC_NEW = T(r"""// experiment 0401 series e5 (KYTY_BC5_SAVEDATA_MEMORY_FIXES "sync", R2 KS03 + SS01): KytyPS5 dfec14a
// libs/libSaveData.cpp:197-202 (the argument) and 1151-1182 (the call), fitted to this file's one memory store.
struct Bc5SaveDataMemorySync {
»int32_t  user_id;
»uint32_t slot_id;
»uint32_t option;
»uint8_t  reserved[28];
};
static_assert(sizeof(Bc5SaveDataMemorySync) == 40);

static int bc5_sync_save_data_memory(const Bc5SaveDataMemorySync* sync_param) {
»if (sync_param == nullptr || sync_param->slot_id >= BC5_SAVE_DATA_MEMORY_SLOTS || sync_param->option > 1) {
»»return SAVE_DATA_ERROR_PARAMETER;
»}
»if (sync_param->user_id < 0) {
»»return SAVE_DATA_ERROR_INVALID_LOGIN_USER;
»}
»bool written = false;
»{
»»std::lock_guard lock(g_save_data_memory_mutex);
»»if (!g_bc5_memory_set_up[sync_param->slot_id]) {
»»»return SAVE_DATA_ERROR_MEMORY_NOT_READY;
»»}
»»written = save_data_memory_store();
»}
»const int status = written ? OK : SAVE_DATA_ERROR_INTERNAL;
»LOGF("\t user_id = %" PRId32 ", slot_id = %" PRIu32 ", option = %" PRIu32 ": memory %s\n", sync_param->user_id,
»     sync_param->slot_id, sync_param->option, written ? "written" : "not written");
»if (sync_param->option == 1) {
»»return status;
»}
»SceSaveDataTitleId title {};
»SceSaveDataDirName directory {};
»std::snprintf(title.data, sizeof(title.data), "%s", get_title_id().c_str());
»std::snprintf(directory.data, sizeof(directory.data), "sce_sdmemory%s",
»              sync_param->slot_id == 0 ? "" : std::to_string(sync_param->slot_id).c_str());
»queue_save_data_event(BC5_SAVE_DATA_EVENT_TYPE_MEMORY_SYNC_END, sync_param->user_id, &title, &directory, status);
»return OK;
}

int KYTY_SYSV_ABI SaveDataSyncSaveDataMemory(const void* sync_param) {
»PRINT_NAME();

»LOGF("\t sync_param = 0x%016" PRIx64 "\n", reinterpret_cast<uint64_t>(sync_param));

»if (bc5_savedata_memory_fix(BC5_SDM_FIX_SYNC)) { // experiment 0401 series e5: the checks, the write and the event
»»return bc5_sync_save_data_memory(static_cast<const Bc5SaveDataMemorySync*>(sync_param));
»}
»return OK;
}
""")

# ---- KYTY_BC5_SAVEDATA_DELETE_BUSY: SaveDataDelete -------------------------------------------------------------------
SAV_DELETE_OLD = T(r"""»std::string dir =
»    std::string(SAVE_DATA_DIR) + "/" + get_title_id() + "/" + std::string(del->dir_name->data);
""")
SAV_DELETE_NEW = SAV_DELETE_OLD + T(r"""»// experiment 0401 series e5 (KYTY_BC5_SAVEDATA_DELETE_BUSY, KytyPS5 dfec14a :1051-1056): a mounted save is BUSY; the
»// mount lock is held to the end of the delete, so that no mount comes in between. Off: no lock, today's delete.
»Bc5MountLockIf bc5_mount_lock(bc5_savedata_delete_busy_on());
»if (bc5_mount_lock.held && g_mount_slots.FindAvailable(del->dir_name->data) == SaveDataMountSlots::BUSY) {
»»return SAVE_DATA_ERROR_BUSY;
»}
""")

# ---- KYTY_BC5_SAVEDATA_ALIASES: both tables ----------------------------------------------------------------------------
SAV_NATIVE_OLD = T("»LIB_FUNC(\"TywrFKCoLGY\", ::Libs::SaveData::SaveDataInitialize3);\n")
SAV_NATIVE_NEW = SAV_NATIVE_OLD + T(r"""»if (::Libs::SaveData::bc5_savedata_aliases_on()) { // experiment 0401 series e5 (AnyPS5 bc6a5e4ea, R1 #15)
»»LIB_FUNC("ZkZhskCPXFw", ::Libs::SaveData::SaveDataInitialize3); // sceSaveDataInitialize
»»LIB_FUNC("l1NmDeDpNGU", ::Libs::SaveData::SaveDataInitialize3); // sceSaveDataInitialize2
»}
""")
SAV_TABLE_OLD = T("»LIB_FUNC(\"TywrFKCoLGY\", SaveData::SaveDataInitialize3);\n")
SAV_TABLE_NEW = SAV_TABLE_OLD + T(r"""»if (SaveData::bc5_savedata_aliases_on()) { // experiment 0401 series e5 (AnyPS5 bc6a5e4ea, R1 #15)
»»LIB_FUNC("ZkZhskCPXFw", SaveData::SaveDataInitialize3); // sceSaveDataInitialize
»»LIB_FUNC("l1NmDeDpNGU", SaveData::SaveDataInitialize3); // sceSaveDataInitialize2
»}
""")

# ---- the stderr lines at registration -----------------------------------------------------------------------------------
SAV_REG_OLD = T("»(void)SaveData::bc5_savedata_sort_on(); // experiment 0401 series e4: the sort switch's line\n")
SAV_REG_NEW = SAV_REG_OLD + T(
    "»(void)SaveData::bc5_savedata_memory_fixes(); // experiment 0401 series e5: the memory fixes switch's line\n"
    "»(void)SaveData::bc5_savedata_delete_busy_on(); // experiment 0401 series e5: the delete busy switch's line\n")


def edit_sav(s, eol):
    for m in COMMON_MARKS + SAV_MARKS:
        assert m not in s, ("libSaveData.cpp has the edit already", m)
    # e4's three switches are there (this is its private unit), and each keeps its uses
    e4 = {b"bc5_savedata_fixes_on": 4, b"bc5_savedata_event_cb_on": 7, b"bc5_savedata_sort_on": 3}
    for fn, n in e4.items():
        assert s.count(fn) == n, ("e4's switch uses", fn, s.count(fn), n)
    assert s.count(b"bc5_save_data_events_lock()") == 3, "e4's queue lock: its definition, the push, the poll"
    assert s.count(b"save_data_memory_store()") == 2, "save_data_memory_store: its definition and SetSaveDataMemory2's call"
    s = once(s, SAV_TOP_ANCHOR, SAV_TOP + SAV_TOP_ANCHOR, "the switches before e4's event callback block", eol)
    s = once(s, SAV_LOCK_OLD, SAV_LOCK_NEW, "e4's queue lock", eol)
    s = once(s, SAV_DELIVER_OLD, SAV_DELIVER_NEW, "queue_save_data_event's delivery", eol)
    s = once(s, SAV_TERM_OLD, SAV_TERM_NEW, "SaveDataTerminate's clearing", eol)
    s = once(s, SAV_STORE_HEAD_OLD, SAV_STORE_HEAD_NEW, "save_data_memory_store's head", eol)
    s = once(s, SAV_STORE_FAIL1_OLD, SAV_STORE_FAIL1_NEW, "save_data_memory_store's first failure", eol)
    s = once(s, SAV_STORE_FAIL2_OLD, SAV_STORE_FAIL2_NEW, "save_data_memory_store's second failure", eol)
    s = once(s, SAV_STORE_END_OLD, SAV_STORE_END_NEW, "save_data_memory_store's end", eol)
    s = once(s, SAV_SETUP_ANCHOR, SAV_SETUP_BLOCK + SAV_SETUP_ANCHOR, "the existed helper before Setup2", eol)
    s = once(s, SAV_SETUP_OLD, SAV_SETUP_NEW, "SetupSaveDataMemory2's result", eol)
    s = once(s, SAV_SYNC_OLD, SAV_SYNC_NEW, "SaveDataSyncSaveDataMemory", eol)
    s = once(s, SAV_DELETE_OLD, SAV_DELETE_NEW, "SaveDataDelete's directory", eol)
    s = once(s, SAV_NATIVE_OLD, SAV_NATIVE_NEW, "the native table's Initialize3", eol)
    s = once(s, SAV_TABLE_OLD, SAV_TABLE_NEW, "the SaveData table's Initialize3", eol)
    s = once(s, SAV_REG_OLD, SAV_REG_NEW, "InitSaveData_1's switch lines", eol)
    # each new function before its first use, and the uses counted
    assert s.index(b"static uint32_t bc5_savedata_memory_fixes()") < s.index(b"bc5_save_data_events_lock() {")
    assert s.index(b"static bool save_data_memory_store()") < s.index(b"written = save_data_memory_store();")
    assert s.count(b"bc5_savedata_memory_fix(BC5_SDM_FIX_") == 5, s.count(b"bc5_savedata_memory_fix(BC5_SDM_FIX_")
    assert s.count(b"bc5_savedata_delete_busy_on()") == 3, "delete busy: definition, the delete, the registration"
    assert s.count(b"bc5_savedata_aliases_on()") == 3, "aliases: definition, two tables"
    assert s.count(b"bc5_save_data_events_lock()") == 4, "e4's queue lock: + Terminate's"
    for fn, n in e4.items():
        assert s.count(fn) == n + (1 if fn == b"bc5_savedata_event_cb_on" else 0), ("e4's switch uses after", fn)
    return s


# ======================================================================================================================
# src/libs/libNet.cpp
# ======================================================================================================================

NET_MARKS = (b"bc5_http2_fix", b"Bc5Http2TriggerUserEventArgs", b"bc5_http2_trigger_user_event",
             b"Bc5HttpCreateTemplate", b"g_bc5_http2_context_ssl_options", b"kernel/eventQueue.h")

NET_INC_OLD = T("#include \"common/logging/log.h\"\n")
NET_INC_NEW = NET_INC_OLD + T("#include \"kernel/eventQueue.h\" // experiment 0401 series e5: Http2's user event (KS01)\n")
NET_SYSINC_OLD = T("#include <cctype>\n")
NET_SYSINC_NEW = NET_SYSINC_OLD + T("#include <cstdio>  // experiment 0401 series e5: the switch's stderr line\n"
                                    "#include <cstdlib> // experiment 0401 series e5: std::getenv\n")

NET_SWITCH_ANCHOR = T("namespace LibHttp {\n\nLIB_VERSION(\"Http\", 1, \"Http\", 1, 1);\n")
NET_SWITCH = T(r"""// ---- experiment 0401 series e5: Http and Http2 fixes (exp 0405 top-32 row 21 and two extras), switch KYTY_BC5_HTTP2_FIXES ----
// Items, comma-separated; a value naming none of them (any value set, non-empty and not "0") turns all three on:
//  - "async" (R2 KS01): sceHttp2SendRequestAsync (A+NVAFu4eCg) and sceHttp2ReadDataAsync (bGN-6zbo7ms) trigger the
//    caller's equeue user event (its kqueue_option {equeue, id, udata}) when the call completes, as KytyPS5 a06e356
//    ("net: signal the event queue when Http2 async calls complete", github.com/KytyPS5/KytyPS5, GPL-2.0, as KytyPlus;
//    the ported lines keep its authors' copyright) does at dfec14a src/libs/libNet.cpp:837-845, 1259-1288, 1436-1473.
//    Today the option is ignored, and a title that waits on its equeue for the completion waits forever. The calls
//    complete at once here (no transport: SendRequestAsync fails with TIMEOUT), so the event is triggered before they
//    return, on the kernel's own user-event trigger (LibKernel::EventQueue::KernelTriggerUserEvent).
//  - "ssl" (R1 #18): sceHttp2SslEnableOption (EWcwMpbr5F8) and sceHttp2SslDisableOption (B37SruheQ5Y) accept a context id
//    (AnyPS5 754aad4e9 core/libs/prx/libSceHttp2/Export.cpp:79-90, 303-315, GPL-2.0-only; a title sets them on its
//    context, AnyPS5 #13715). Today a context id that is no template's or request's is INVALID_ID. The flags are kept
//    per context; no transport reads them. Templates made later do not inherit them (AnyPS5 copies a context's
//    settings, held: unverified).
//  - "agent" (R2 KS04): sceHttpCreateTemplate (0gYjPTR-6cY) with a NULL user agent makes a template with an empty one
//    (KytyPS5 87e815b "net: accept a NULL user agent in sceHttpCreateTemplate (Cyberpunk 2077)", dfec14a
//    src/libs/network.cpp:469). Today Network::HttpCreateTemplate builds a std::string from the NULL pointer. Done here
//    by a wrapper registered in its place (network.cpp is not this group's file).
// Nothing here is measured on a console. Off (unset, empty or "0"): today's path, the old code kept. One stderr line, at
// the first read (InitNet_1_Http, at the library's registration).
static constexpr uint32_t BC5_HTTP2_FIX_ASYNC = 1u; // "async"
static constexpr uint32_t BC5_HTTP2_FIX_SSL   = 2u; // "ssl"
static constexpr uint32_t BC5_HTTP2_FIX_AGENT = 4u; // "agent"
static constexpr uint32_t BC5_HTTP2_FIX_ALL   = BC5_HTTP2_FIX_ASYNC | BC5_HTTP2_FIX_SSL | BC5_HTTP2_FIX_AGENT;

static uint32_t bc5_http2_fixes_parse(const char* e) {
»if (e == nullptr || e[0] == '\0' || std::strcmp(e, "0") == 0) {
»»return 0;
»}
»uint32_t    items = 0;
»const char* p     = e;
»for (;;) {
»»const char*  comma = std::strchr(p, ',');
»»const size_t n     = comma != nullptr ? static_cast<size_t>(comma - p) : std::strlen(p);
»»if (n == 5 && std::strncmp(p, "async", n) == 0) {
»»»items |= BC5_HTTP2_FIX_ASYNC;
»»} else if (n == 3 && std::strncmp(p, "ssl", n) == 0) {
»»»items |= BC5_HTTP2_FIX_SSL;
»»} else if (n == 5 && std::strncmp(p, "agent", n) == 0) {
»»»items |= BC5_HTTP2_FIX_AGENT;
»»}
»»if (comma == nullptr) {
»»»break;
»»}
»»p = comma + 1;
»}
»return items != 0 ? items : BC5_HTTP2_FIX_ALL;
}

// The items of KYTY_BC5_HTTP2_FIXES that are on (0: off), read once.
static uint32_t bc5_http2_fixes() {
»static const uint32_t items = [] {
»»const uint32_t v = bc5_http2_fixes_parse(std::getenv("KYTY_BC5_HTTP2_FIXES"));
»»if (v == 0) {
»»»std::fprintf(stderr, "[bc5] exp 0405: http2 fixes off\n");
»»} else {
»»»std::fprintf(stderr, "[bc5] exp 0405: http2 fixes on (items:%s%s%s)\n",
»»»             (v & BC5_HTTP2_FIX_ASYNC) != 0 ? " async" : "", (v & BC5_HTTP2_FIX_SSL) != 0 ? " ssl" : "",
»»»             (v & BC5_HTTP2_FIX_AGENT) != 0 ? " agent" : "");
»»}
»»return v;
»}();
»return items;
}

static bool bc5_http2_fix(uint32_t item) {
»return (bc5_http2_fixes() & item) != 0;
}
// ---- end of experiment 0401 series e5's switch ----

""")

# ---- "agent": the wrapper and its registration -------------------------------------------------------------------------
NET_HTTPDEF_ANCHOR = T("LIB_DEFINE(InitNet_1_Http) {\n")
NET_HTTP_WRAPPER = T(r"""// experiment 0401 series e5 (KYTY_BC5_HTTP2_FIXES "agent", KytyPS5 87e815b, dfec14a src/libs/network.cpp:469): a NULL
// user agent is an empty one; everything else is today's Network::Http::HttpCreateTemplate.
static int KYTY_SYSV_ABI Bc5HttpCreateTemplate(int http_ctx_id, const char* user_agent, int http_ver,
                                               int is_auto_proxy_conf) {
»return Http::HttpCreateTemplate(http_ctx_id, user_agent != nullptr ? user_agent : "", http_ver, is_auto_proxy_conf);
}

""")
NET_HTTPREG_OLD = T("»LIB_FUNC(\"0gYjPTR-6cY\", Http::HttpCreateTemplate);\n")
NET_HTTPREG_NEW = T(r"""»if (bc5_http2_fix(BC5_HTTP2_FIX_AGENT)) { // experiment 0401 series e5 (KytyPS5 87e815b, R2 KS04)
»»LIB_FUNC("0gYjPTR-6cY", Bc5HttpCreateTemplate);
»} else {
»»LIB_FUNC("0gYjPTR-6cY", Http::HttpCreateTemplate);
»}
""")

# ---- "async": the argument and the trigger ------------------------------------------------------------------------------
NET_H2CONST_ANCHOR = T("constexpr int HTTP2_ERROR_NULL_POINTER = -2122640859; /* 0x817B1225 */\n")
NET_H2ASYNC = T(r"""
// experiment 0401 series e5 (KYTY_BC5_HTTP2_FIXES "async", R2 KS01): the kqueue_option of the two async calls, KytyPS5
// a06e356's Http2TriggerUserEventArgs (dfec14a src/libs/libNet.cpp:837-845); TODO(verify): the layout is KytyPS5's, no
// console source cited. The equeue is this host's handle (KernelCreateEqueue's), as the title got it.
struct Bc5Http2TriggerUserEventArgs {
»LibKernel::EventQueue::KernelEqueue eq;
»int                                 uniq_id;
»uint8_t                             padding[4];
»void*                               udata;
»void*                               reserved;
};
static_assert(sizeof(Bc5Http2TriggerUserEventArgs) == 32);

// KytyPS5 a06e356 Http2TriggerUserEvent (dfec14a src/libs/libNet.cpp:1259-1264): the caller's user event, if it gave one.
static void bc5_http2_trigger_user_event(const void* kqueue_option) {
»if (kqueue_option == nullptr || !bc5_http2_fix(BC5_HTTP2_FIX_ASYNC)) {
»»return;
»}
»const auto* args   = static_cast<const Bc5Http2TriggerUserEventArgs*>(kqueue_option);
»const int   result = LibKernel::EventQueue::KernelTriggerUserEvent(args->eq, args->uniq_id, args->udata);
»LOGF("\t user event: eq = 0x%016" PRIx64 ", id = %d -> 0x%08x\n", static_cast<uint64_t>(args->eq), args->uniq_id,
»     static_cast<unsigned>(result));
}
""")

NET_SEND_SIG_OLD = T("""static int KYTY_SYSV_ABI Http2SendRequestAsync(int req_id, const void* post_data, size_t size,
                                               void* /*kqueue_option*/, void* /*option*/) {
""")
NET_SEND_SIG_NEW = T("""static int KYTY_SYSV_ABI Http2SendRequestAsync(int req_id, const void* post_data, size_t size,
                                               void* kqueue_option, void* /*option*/) { // e5: kqueue_option named
""")
NET_SEND_END_OLD = T(r"""»request->second.async_event  = 0;

»return 0;
}
""")
NET_SEND_END_NEW = T(r"""»request->second.async_event  = 0;
»bc5_http2_trigger_user_event(kqueue_option); // experiment 0401 series e5 ("async"; off: nothing)

»return 0;
}
""")
NET_READ_SIG_OLD = T("""static int KYTY_SYSV_ABI Http2ReadDataAsync(int req_id, void* data, size_t size,
                                            void* /*kqueue_option*/, void* /*option*/) {
""")
NET_READ_SIG_NEW = T("""static int KYTY_SYSV_ABI Http2ReadDataAsync(int req_id, void* data, size_t size,
                                            void* kqueue_option, void* /*option*/) { // e5: kqueue_option named
""")
NET_READ_ERR_OLD = T(r"""»»request->second.async_result = send_result;
»»request->second.async_event  = 1;
»»return 0;
""")
NET_READ_ERR_NEW = T(r"""»»request->second.async_result = send_result;
»»request->second.async_event  = 1;
»»bc5_http2_trigger_user_event(kqueue_option); // experiment 0401 series e5 ("async"; off: nothing)
»»return 0;
""")
NET_READ_END_OLD = T(r"""»request->second.async_result = static_cast<int>(to_copy);
»request->second.async_event  = 1;

»return 0;
""")
NET_READ_END_NEW = T(r"""»request->second.async_result = static_cast<int>(to_copy);
»request->second.async_event  = 1;
»bc5_http2_trigger_user_event(kqueue_option); // experiment 0401 series e5 ("async"; off: nothing)

»return 0;
""")

# ---- "ssl": a context's flags --------------------------------------------------------------------------------------------
NET_SSL_ANCHOR = T("static int KYTY_SYSV_ABI Http2SslEnableOption(int id, uint32_t ssl_flags) {\n")
NET_SSL_BLOCK = T(r"""// experiment 0401 series e5 (KYTY_BC5_HTTP2_FIXES "ssl", AnyPS5 754aad4e9, R1 #18): the SSL flags of a context, for an
// id that is a context's and no template's or request's (today's lookup goes first); nullptr with the item off or for an
// id that is no context's. Kept per context, read by nothing yet (no transport).
static std::map<int, uint32_t> g_bc5_http2_context_ssl_options;

static uint32_t* bc5_http2_context_ssl_options(int id) {
»if (!bc5_http2_fix(BC5_HTTP2_FIX_SSL) || g_http2_contexts.find(id) == g_http2_contexts.end()) {
»»return nullptr;
»}
»return &g_bc5_http2_context_ssl_options[id];
}

""")
NET_SSL_EN_OLD = T(r"""»auto* options = GetHttp2Options(id);
»if (options == nullptr) {
»»return HTTP2_ERROR_INVALID_ID;
»}

»options->ssl_options |= ssl_flags;
""")
NET_SSL_EN_NEW = T(r"""»auto* options = GetHttp2Options(id);
»if (uint32_t* bc5_context = options == nullptr ? bc5_http2_context_ssl_options(id) : nullptr; bc5_context != nullptr) {
»»*bc5_context |= ssl_flags; // experiment 0401 series e5 ("ssl"): a context's
»»return 0;
»}
»if (options == nullptr) {
»»return HTTP2_ERROR_INVALID_ID;
»}

»options->ssl_options |= ssl_flags;
""")
NET_SSL_DIS_OLD = T(r"""»auto* options = GetHttp2Options(id);
»if (options == nullptr) {
»»return HTTP2_ERROR_INVALID_ID;
»}

»options->ssl_options &= ~ssl_flags;
""")
NET_SSL_DIS_NEW = T(r"""»auto* options = GetHttp2Options(id);
»if (uint32_t* bc5_context = options == nullptr ? bc5_http2_context_ssl_options(id) : nullptr; bc5_context != nullptr) {
»»*bc5_context &= ~ssl_flags; // experiment 0401 series e5 ("ssl"): a context's
»»return 0;
»}
»if (options == nullptr) {
»»return HTTP2_ERROR_INVALID_ID;
»}

»options->ssl_options &= ~ssl_flags;
""")


def edit_net(s, eol):
    for m in COMMON_MARKS + NET_MARKS:
        assert m not in s, ("libNet.cpp has the edit already", m)
    assert b"#include <cstdio>" not in s and b"#include <cstdlib>" not in s, "libNet.cpp includes them already: look again"
    assert s.count(b"/*kqueue_option*/") == 2, "the two async calls"
    s = once(s, NET_INC_OLD, NET_INC_NEW, "the include of common/logging/log.h", eol)
    s = once(s, NET_SYSINC_OLD, NET_SYSINC_NEW, "the include of <cctype>", eol)
    s = once(s, NET_SWITCH_ANCHOR, NET_SWITCH + NET_SWITCH_ANCHOR, "the switch before namespace LibHttp", eol)
    s = once(s, NET_HTTPDEF_ANCHOR, NET_HTTP_WRAPPER + NET_HTTPDEF_ANCHOR, "the wrapper before InitNet_1_Http", eol)
    s = once(s, NET_HTTPREG_OLD, NET_HTTPREG_NEW, "HttpCreateTemplate's registration", eol)
    s = once(s, NET_H2CONST_ANCHOR, NET_H2CONST_ANCHOR + NET_H2ASYNC, "the Http2 error constants", eol)
    s = once(s, NET_SEND_SIG_OLD, NET_SEND_SIG_NEW, "Http2SendRequestAsync's signature", eol)
    s = once(s, NET_SEND_END_OLD, NET_SEND_END_NEW, "Http2SendRequestAsync's end", eol)
    s = once(s, NET_READ_SIG_OLD, NET_READ_SIG_NEW, "Http2ReadDataAsync's signature", eol)
    s = once(s, NET_READ_ERR_OLD, NET_READ_ERR_NEW, "Http2ReadDataAsync's failed send", eol)
    s = once(s, NET_READ_END_OLD, NET_READ_END_NEW, "Http2ReadDataAsync's end", eol)
    s = once(s, NET_SSL_ANCHOR, NET_SSL_BLOCK + NET_SSL_ANCHOR, "the context flags before Http2SslEnableOption", eol)
    s = once(s, NET_SSL_EN_OLD, NET_SSL_EN_NEW, "Http2SslEnableOption", eol)
    s = once(s, NET_SSL_DIS_OLD, NET_SSL_DIS_NEW, "Http2SslDisableOption", eol)
    assert s.index(b"static uint32_t bc5_http2_fixes()") < s.index(b"bc5_http2_fix(BC5_HTTP2_FIX_AGENT)")
    assert s.index(b"static std::map<int, Http2Context>  g_http2_contexts;") < s.index(b"g_bc5_http2_context_ssl_options;")
    assert s.count(b"bc5_http2_trigger_user_event(kqueue_option);") == 3
    assert s.count(b"bc5_http2_context_ssl_options(id)") == 2
    assert s.count(b"bc5_http2_fix(BC5_HTTP2_FIX_") == 3
    return s


# ======================================================================================================================
# src/libs/libPad.cpp
# ======================================================================================================================

PAD_MARKS = (b"WFIiSfXGUq8", b"Bc5PadOpenExt", b"PadOpenExt")

PAD_ANCHOR = T("LIB_DEFINE(InitPad_1) {\n")
PAD_BLOCK = T(r"""// ---- experiment 0401 series e5: scePadOpenExt (exp 0405 top-32 row 22, R2 SS22 + KS69), switch KYTY_BC5_PAD_OPEN_EXT ----
// scePadOpenExt (WFIiSfXGUq8; the NID from exp 0327's calculator, nid0401.py's, and sharpemu's and KytyPS5's tables) was
// not registered, so a title that opens its pad this way got the loader's stub, handle 0, which every pad call rejects
// (Controller::ControllerIndexFromHandle): no input at all. As sharpemu (GPL-2.0-or-later; added in 373100a, read at
// 514d766) SharpEmu.Libs/Pad/PadExports.cs:91-96 and PadOpenCore 132-180: scePadOpen's checks, handles and errors, and a
// personal port also of type 1 (typeAccepted: 0, 1 or 2 for the Ext call; the system user's remote port as before). Here
// port type 1 goes to Controller::PadOpen as the standard port 0, so its handle is the player's (1000 + N - 1 -> N).
// KytyPS5 dfec14a src/libs/libPad.cpp:126-135, 170 (KS69, GPL-2.0) registers the NID to a stub that returns 0, the
// handle this item is about; only its NID is taken from there. TODO(verify): what port type 1 is on the console (no
// public source names it); sharpemu also lets types 1 and 2 be opened more than once, which this host's PadOpen never
// refuses anyway. On: KYTY_BC5_PAD_OPEN_EXT set, non-empty and not "0", read once at the registration, one stderr line
// either way. Off: the NID is not registered (today's stub).
static bool Bc5PadOpenExtOn() {
»static const bool on = [] {
»»const char* e = std::getenv("KYTY_BC5_PAD_OPEN_EXT");
»»const bool  v = e != nullptr && e[0] != '\0' && std::strcmp(e, "0") != 0;
»»std::fprintf(stderr, "[bc5] exp 0405: pad open ext %s\n", v ? "on (items: openext)" : "off");
»»return v;
»}();
»return on;
}

static int KYTY_SYSV_ABI Bc5PadOpenExt(int user_id, int type, int index, const void* param) {
»PRINT_NAME();

»LOGF("\t user_id = %d\n"
»     "\t type    = %d\n"
»     "\t index   = %d\n"
»     "\t param   = 0x%016" PRIx64 "\n",
»     user_id, type, index, reinterpret_cast<uint64_t>(param));

»constexpr int port_type_ext      = 1; // sharpemu PadOpenCore: a personal port type the Ext call accepts too
»constexpr int port_type_standard = 0;
»return Controller::PadOpen(user_id, type == port_type_ext ? port_type_standard : type, index, param);
}
// ---- end of experiment 0401 series e5's block ----

""")
PAD_REG_OLD = T("»LIB_FUNC(\"xk0AcarP3V4\", Controller::PadOpen);\n")
PAD_REG_NEW = PAD_REG_OLD + T(r"""»if (Bc5PadOpenExtOn()) { // experiment 0401 series e5 (sharpemu 373100a, R2 SS22): scePadOpenExt
»»LIB_FUNC("WFIiSfXGUq8", Bc5PadOpenExt);
»}
""")


def edit_pad(s, eol):
    for m in COMMON_MARKS + PAD_MARKS:
        assert m not in s, ("libPad.cpp has the edit already", m)
    s = once(s, PAD_ANCHOR, PAD_BLOCK + PAD_ANCHOR, "InitPad_1", eol)
    s = once(s, PAD_REG_OLD, PAD_REG_NEW, "scePadOpen's registration", eol)
    assert s.count(b"Bc5PadOpenExtOn()") == 2 and s.count(b"Bc5PadOpenExt)") == 1
    return s


# ======================================================================================================================

def eol_of(s):
    crlf, lf = s.count(b"\r\n"), s.count(b"\n")
    assert crlf == 0 or crlf == lf, ("mixed line endings", crlf, lf)
    return b"\r\n" if crlf else b"\n"


def once(s, old, new, what, eol):
    old, new = old.replace(b"\n", eol), new.replace(b"\n", eol)
    assert s.count(old) == 1, (what, old[:90], s.count(old))
    return s.replace(old, new)


def balance(s):
    """Braces, parentheses and brackets outside comments, strings and character literals (C++, no raw strings)."""
    counts = {b"{": 0, b"}": 0, b"(": 0, b")": 0, b"[": 0, b"]": 0}
    i, n = 0, len(s)
    while i < n:
        c = s[i:i + 1]
        if s.startswith(b"//", i):
            i = s.find(b"\n", i)
            i = n if i < 0 else i
            continue
        if s.startswith(b"/*", i):
            i = s.find(b"*/", i + 2) + 2
            assert i >= 2, "an unterminated comment"
            continue
        if c in (b'"', b"'"):
            j = i + 1
            while s[j:j + 1] != c:
                j += 2 if s[j:j + 1] == b"\\" else 1
                assert j < n, "an unterminated literal"
            i = j + 1
            continue
        if c in counts:
            counts[c] += 1
        i += 1
    return counts[b"{"] - counts[b"}"], counts[b"("] - counts[b")"], counts[b"["] - counts[b"]"]


FILES = ((SAV, edit_sav), (NET, edit_net), (PAD, edit_pad))


def main():
    assert len(sys.argv) == 3, __doc__
    root, out = sys.argv[1], sys.argv[2]
    outputs = []
    for rel, fn in FILES:  # every input is checked and edited before anything is written
        with open(os.path.join(root, rel), "rb") as f:
            s = f.read()
        got = hashlib.md5(s).hexdigest()
        for m in COMMON_MARKS:
            assert m not in s, (rel, "has the edit already", m)
        assert got == IN_MD5[rel], (rel, "is not the pinned input", got, IN_MD5[rel])
        eol = eol_of(s)
        o = fn(s, eol)
        assert eol_of(o) == eol
        assert balance(o) == balance(s), (rel, "brackets", balance(s), balance(o))
        outputs.append((rel, o))
    for rel, o in outputs:
        p = os.path.join(out, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(o)
        print(f"{rel} {hashlib.md5(o).hexdigest()}")


if __name__ == "__main__":
    main()
