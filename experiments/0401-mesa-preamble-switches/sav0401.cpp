// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0401 series e4: a CPU test of src/libs/libSaveData.cpp as mksav0401.py leaves it, without the game, for
// its three switches: KYTY_BC5_SAVEDATA_FIXES (KytyPS5 dfec14a), KYTY_BC5_SAVEDATA_EVENT_CB (AnyPS5's event callback with
// its fixes 0d0abe09c and bc6b4d76f) and KYTY_BC5_SAVEDATA_SORT (KytyPS5 4b0282e's mtime key). It calls the host's own
// SaveData functions, linked from the emulator's objects, in a fresh directory it makes under the current one (the saves
// go to _SaveData/UNKNOWN there: no param.sfo is loaded). It reads the three switches as the unit does: "on" needs exactly
// one of them on, "off" none of them, and each check expects the setting of its own switch.
//   Search, 9 checks. Three saves made through SaveDataMount3 and SaveDataSetParam, as KytyPS5 4b0282e's
//     TestSearchSortKeys makes them: alpha, bravo, charlie with blocks 96, 48, 48, user params 2, 3, 1, title mtimes
//     +1 h, +3 h, +2 h, and their param records' file times now +1 h, +3 h, +2 h (KytyPS5 sets its sce_sys/param.bin;
//     here the record is <dir>.param). 1-5: the name, user param, blocks, free blocks and mtime orders that test expects,
//     the same in both settings. 6: alpha without its .blocks record sorts last (this file reports the maximum, as
//     shadPS4 and AnyPS5 do; KytyPS5 sorts it first), both settings. 7 (SORT): alpha's record made the newest (+5 h):
//     by mtime, descending, alpha first with the switch on (the files' time), last off (the title's). 8 (SORT): the
//     mtime the search reports for alpha: its record's file time on, the title's off. 9: a save with no file and no
//     record reports its directory's time, not 0, in both settings.
//   Mount result, 9 checks (KytyPS5 dfec14a, FIXES). A refused SaveDataMount3 (BUSY over the mounted save, NOT_FOUND,
//     EXISTS, PARAMETER, NO_PERMISSION, MOUNT_FULL) leaves the caller's result byte for byte as it was with the switch on,
//     and clears it with the switch off (today). A successful mount clears it and writes the point, 0 required blocks
//     and the status in both settings. With the switch on, the result of the BUSY call still names the mounted save, so
//     SaveDataUmount2 through it unmounts it; off it names nothing (NOT_FOUND), as today.
//   Events (EVENT_CB), 2 checks off, 15 on, after AnyPS5's tests/GuestSaveDataEventCallback.cpp @ 4f41f4c37
//     (GPL-2.0-only; written anew for this host's functions). Both settings: 1. the unit's registration (InitSaveData_1
//     into a SymbolDatabase): hsKd5c21sQc and v-AK1AxQhS0 at the two functions in both SaveData tables on, absent off;
//     2. polling as today: a backup's and a BACKUP_ASYNC commit's events, then NOT_FOUND. On only: 3. register before
//     Initialize3 is NOT_INITIALIZED, unregister then is OK, a null callback is PARAMETER, and none of it starts a thread;
//     4. a backup reaches the callback on the delivery thread (not the caller's) within 5 s, once, with the userdata,
//     and the poll returns the same event; 5. a BACKUP_ASYNC commit (type 4) and 6. a BACKUP_ASYNC unmount (type 1,
//     queued under the mount lock) reach it on the same thread and the poll; 7. a replacing registration takes the next
//     event on the same thread; 8. after unregister no callback runs and the poll still has the event; 9. an
//     unregister from inside the callback drops the delivery still pending (a second backup queued meanwhile);
//     10. a registration after unregister reuses the thread; 11. a terminate from inside the callback is BUSY;
//     12. the final terminate joins the delivery thread (its thread_local destructor has run when Terminate returns);
//     13. that terminate dropped the registration: register is NOT_INITIALIZED, and after a new Initialize3 events
//     reach no callback until one registers again; 14. two threads re-registering (A, B, unregister) against a backup
//     thread and a poll thread: each call has its own callback's userdata, none comes after the unregister, then a
//     fence callback gets its event; 15. registration racing the final terminate on two threads (bc6b4d76f's case),
//     100 times: every other time at once, every other time with the delivery thread held in a callback and the
//     registration started 10 ms before the terminate (a registration that read the count before its locks then
//     outlives the terminate every time); terminate OK, registration OK or NOT_INITIALIZED, the raced callback never
//     called. On Linux the checks also count /proc/self/task: no thread before the first registration, one after
//     it, none after the final terminate (0d0abe09c).
// A watchdog ends a hang after 240 s with a FAIL line naming the step (exit 3). Exit 0 only after the end line
// "sav0401: on|off N of N; end": N = 20, or 33 with KYTY_BC5_SAVEDATA_EVENT_CB on. A failed check prints a FAIL line and
// exits 1. Exit 2 for wrong usage, a switch setting that does not match the argument, KYTY_BC5_SAVEDATA_DIR set (set or
// empty: the box unsets it, and this test must never come near a real save) or KYTY_BC5_SAVE_TRACE set.
// Linked with the shared (unedited) libSaveData.cpp.o, the link fails (no SaveDataRegisterEventCallback): only the
// private object (mksav0401.py's output) links.
// Build (box): the compile command of src/libs/libSaveData.cpp (compdb entry
// src/CMakeFiles/kyty_emulator.dir/libs/libSaveData.cpp.o), cleaned as build0401.py cleans it, with -c sav0401.cpp and
// -o sav0401.o; it needs only the tree's own headers. Link: the src/kyty_emulator link command with every emulator object
// but main.cpp.o, the private libSaveData.cpp.o in place of the shared one, plus sav0401.o, -o sav0401, -Wl,-Map= and
// --dependency-file= rewritten as build0401.py does.
// Runtime state: Common, Threads (this thread is the main thread) and FileSystem in every run, as before; with
// KYTY_BC5_SAVEDATA_EVENT_CB on also Config (its printf direction set to Silent), Log, Timer, Memory and Pthread, as
// emulator.cpp starts them, and the RuntimeLinker singleton made on the main thread (the delivery thread is a guest
// thread, LibKernel::PthreadCreate: its stack comes from Memory, and its end asks the RuntimeLinker to drop its TLS).
// Logging stays off (Log::Bc5SetLogging(false)).
// usage, one switch at a time, the others unset:  KYTY_BC5_SAVEDATA_EVENT_CB=1 ./sav0401 on
//   KYTY_BC5_SAVEDATA_EVENT_CB=0 ./sav0401 off   ./sav0401 off   (and the same for _FIXES and _SORT)
// Run it from a directory on the NVMe (e.g. ~/bc5-work/exp0401e4/run-...). Each run also prints the unit's three lines
// "[bc5] exp 0401: savedata fixes|event callback|sort on|off" on stderr.

#include "common/abi.h"
#include "common/commonSubsystem.h"
#include "common/emulatorConfig.h"
#include "common/logging/log.h"
#include "common/singleton.h"
#include "common/subsystems.h"
#include "common/threads.h"
#include "kernel/fileSystem.h"
#include "kernel/memory.h"
#include "kernel/pthread.h"
#include "libs/errno.h"
#include "loader/runtimeLinker.h"
#include "loader/symbolDatabase.h"
#include "loader/timer.h"

#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <mutex>
#include <string>
#include <system_error>
#include <thread>
#include <vector>
#include <sys/stat.h>
#include <unistd.h>

// The structures of src/libs/libSaveData.cpp that the calls below take, copied token for token: the functions are the
// unit's, so the namespace, the names and the layout must be its own.
namespace Libs::SaveData {

struct SceSaveDataDirName {
	char data[32];
};

struct SceSaveDataTitleId {
	char data[10];
	char padding[6];
};

struct SaveDataParam;

enum class SaveDataSortKey : uint32_t {
	DirName    = 0,
	UserParam  = 1,
	Blocks     = 2,
	Mtime      = 3,
	FreeBlocks = 5,
};

enum class SaveDataSortOrder : uint32_t {
	Ascent  = 0,
	Descent = 1,
};

struct SaveDataDirNameSearchCond {
	int32_t                   user_id;
	int32_t                   pad;
	const SceSaveDataTitleId* title_id;
	const SceSaveDataDirName* dir_name;
	SaveDataSortKey           key;
	SaveDataSortOrder         order;
	uint8_t                   reserved[32];
};

struct SaveDataSearchInfo {
	uint64_t blocks;
	uint64_t free_blocks;
	uint8_t  reserved[32];
};

struct SaveDataDirNameSearchResult {
	uint32_t            hit_num;
	int32_t             pad;
	SceSaveDataDirName* dir_names;
	uint32_t            dir_names_num;
	uint32_t            set_num;
	SaveDataParam*      params;
	SaveDataSearchInfo* infos;
	uint8_t             reserved[12];
	int32_t             pad2;
};

struct SaveDataMountPoint {
	char data[16];
};

struct SaveDataMount3 {
	int                       user_id;
	int                       pad;
	const SceSaveDataDirName* dir_name;
	uint64_t                  blocks;
	uint64_t                  system_blocks;
	uint32_t                  mount_mode;
	int                       pad2;
	int32_t                   resource;
	uint8_t                   reserved[32];
};

struct SaveDataMountResult {
	SaveDataMountPoint mount_point;
	uint64_t           required_blocks;
	uint32_t           unused;
	uint32_t           mount_status;
	uint8_t            reserved[28];
	int                pad;
};

struct SaveDataParam {
	char     title[128];
	char     sub_title[128];
	char     detail[1024];
	uint32_t user_param;
	int      pad;
	int64_t  mtime;
	uint8_t  reserved[32];
};

struct SaveDataCommitParam {
	int32_t  resource;
	uint32_t commit_mode;
	uint8_t  reserved[32];
};

struct SaveDataEvent {
	uint32_t           type;
	int32_t            error_code;
	int32_t            user_id;
	uint8_t            padding[4];
	SceSaveDataTitleId title_id;
	SceSaveDataDirName dir_name;
	uint8_t            reserved[40];
};

struct SaveDataBackup {
	int32_t                   user_id;
	int32_t                   pad;
	const SceSaveDataTitleId* title_id;
	const SceSaveDataDirName* dir_name;
	const void*               fingerprint;
	uint8_t                   reserved[32];
};

// The functions SaveDataMount3 and SaveDataBackup below hide the structures of the same names, as in the unit; these
// aliases name the structures.
using Mount3Param = SaveDataMount3;
using BackupParam = SaveDataBackup;

// mksav0401.py's event callback block (KYTY_BC5_SAVEDATA_EVENT_CB).
using SaveDataEventCallback = KYTY_SYSV_ABI void (*)(const SaveDataEvent* event, void* userdata);

int KYTY_SYSV_ABI SaveDataDirNameSearch(const SaveDataDirNameSearchCond* cond, SaveDataDirNameSearchResult* result);
int KYTY_SYSV_ABI SaveDataMount3(const SaveDataMount3* mount, SaveDataMountResult* mount_result);
int KYTY_SYSV_ABI SaveDataUmount2(uint32_t mode, const SaveDataMountPoint* mount_point);
int KYTY_SYSV_ABI SaveDataSetParam(const SaveDataMountPoint* mount_point, uint32_t param_type, const void* param_buf,
                                   size_t param_buf_size);
int KYTY_SYSV_ABI SaveDataInitialize3(const void* init);
int KYTY_SYSV_ABI SaveDataTerminate();
int KYTY_SYSV_ABI SaveDataCommit(const SaveDataCommitParam* param);
int KYTY_SYSV_ABI SaveDataGetEventResult(const void* event_param, SaveDataEvent* event);
int KYTY_SYSV_ABI SaveDataBackup(const SaveDataBackup* backup);
int KYTY_SYSV_ABI SaveDataRegisterEventCallback(SaveDataEventCallback callback, void* userdata);
int KYTY_SYSV_ABI SaveDataUnregisterEventCallback();

} // namespace Libs::SaveData

namespace Libs {
void InitSaveData_1(Loader::SymbolDatabase* s); // the unit's LIB_DEFINE(InitSaveData_1)
} // namespace Libs

namespace sav0401 {

using Libs::SaveData::BackupParam;
using Libs::SaveData::Mount3Param;
using Libs::SaveData::SaveDataCommitParam;
using Libs::SaveData::SaveDataDirNameSearchCond;
using Libs::SaveData::SaveDataDirNameSearchResult;
using Libs::SaveData::SaveDataEvent;
using Libs::SaveData::SaveDataEventCallback;
using Libs::SaveData::SaveDataMountResult;
using Libs::SaveData::SaveDataParam;
using Libs::SaveData::SaveDataSortKey;
using Libs::SaveData::SaveDataSortOrder;
using Libs::SaveData::SceSaveDataDirName;

static_assert(sizeof(SaveDataMountResult) == 64);
static_assert(sizeof(Mount3Param) == 80);
static_assert(sizeof(SaveDataParam) == 1328);
static_assert(sizeof(SaveDataEvent) == 104);
static_assert(sizeof(BackupParam) == 64);

constexpr int  kSearchChecks    = 9;
constexpr int  kMountChecks     = 9;
constexpr int  kEventChecksOff  = 2;
constexpr int  kEventChecksOn   = 15;
constexpr int  kWatchdogSeconds = 240;
constexpr char kTitleRoot[]     = "_SaveData/UNKNOWN"; // get_title_id() without a param.sfo

constexpr uint32_t kModeOpen    = 1u;  // the unit's open: (mode & 3) without 4 or 32
constexpr uint32_t kModeCreate  = 4u;  // the unit's create: EXISTS over a save that is there
constexpr uint32_t kModeCreate2 = 32u; // the unit's create2: makes the save when it is missing

constexpr uint32_t kUmountBackupAsync = 1u << 16u; // the unit's SAVE_DATA_UMOUNT_MODE_BACKUP_ASYNC
constexpr uint32_t kCommitBackupAsync = 1u;        // the unit's SAVE_DATA_COMMIT_MODE_BACKUP_ASYNC

static int                      g_checks   = 0;
static int                      g_passed   = 0;
static bool                     g_setup_ok = true;
static std::atomic<const char*> g_step {"setup"};
static std::atomic<bool>        g_finished {false};

static void Check(bool ok, const char* what, const std::string& detail) {
	g_checks++;
	if (ok) {
		g_passed++;
	} else {
		std::printf("sav0401: FAIL %s: %s\n", what, detail.c_str());
		std::fflush(stdout);
	}
}

static void Setup(bool ok, const char* what) {
	if (!ok) {
		g_setup_ok = false;
		std::printf("sav0401: FAIL setup: %s\n", what);
		std::fflush(stdout);
	}
}

static std::string Fmt(const char* format, ...) __attribute__((format(printf, 1, 2)));
static std::string Fmt(const char* format, ...) {
	char    buf[768];
	va_list args;
	va_start(args, format);
	std::vsnprintf(buf, sizeof(buf), format, args);
	va_end(args);
	return buf;
}

static bool SwitchOn(const char* name) { // the unit's reading
	const char* e = std::getenv(name);
	return e != nullptr && e[0] != '\0' && std::strcmp(e, "0") != 0;
}

static void Watchdog() {
	const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(kWatchdogSeconds);
	while (std::chrono::steady_clock::now() < deadline) {
		if (g_finished.load()) {
			return;
		}
		std::this_thread::sleep_for(std::chrono::milliseconds(100));
	}
	std::printf("sav0401: FAIL watchdog: \"%s\" did not finish within %d s\n", g_step.load(), kWatchdogSeconds);
	std::fflush(stdout);
	std::_Exit(3);
}

static std::string Hex(int rc) {
	char buf[16];
	std::snprintf(buf, sizeof(buf), "0x%08x", static_cast<unsigned>(rc));
	return buf;
}

static SceSaveDataDirName Name(const char* s) {
	SceSaveDataDirName n {};
	std::snprintf(n.data, sizeof(n.data), "%s", s);
	return n;
}

static std::string Root(const char* dir) {
	return std::string(kTitleRoot) + "/" + dir;
}

static int Mount(const char* dir, uint32_t mode, uint64_t blocks, SaveDataMountResult* r) {
	const SceSaveDataDirName name = Name(dir);
	Mount3Param              m {};
	m.user_id    = 1;
	m.dir_name   = &name;
	m.blocks     = blocks;
	m.mount_mode = mode;
	return Libs::SaveData::SaveDataMount3(&m, r);
}

static int Umount(const SaveDataMountResult& r) {
	return Libs::SaveData::SaveDataUmount2(0, &r.mount_point);
}

static bool Same(const SaveDataMountResult& a, const SaveDataMountResult& b) {
	return std::memcmp(&a, &b, sizeof(a)) == 0;
}

static bool IsZero(const SaveDataMountResult& r) {
	const SaveDataMountResult zero {};
	return Same(r, zero);
}

// What a successful mount leaves: a cleared result with the point, 0 required blocks and the status.
static SaveDataMountResult Mounted(const char* point, uint32_t status) {
	SaveDataMountResult r {};
	std::snprintf(r.mount_point.data, sizeof(r.mount_point.data), "%s", point);
	r.required_blocks = 0;
	r.mount_status    = status;
	return r;
}

// For a FAIL line: the result against a reference (the bytes before the call, or what a mount should leave).
static std::string Describe(const SaveDataMountResult& r, const SaveDataMountResult& ref, const char* same_as_ref) {
	if (Same(r, ref)) {
		return same_as_ref;
	}
	if (IsZero(r)) {
		return "cleared";
	}
	char point[17] = {};
	std::memcpy(point, r.mount_point.data, sizeof(r.mount_point.data));
	return std::string("other (point \"") + point + "\", status " + std::to_string(r.mount_status) + ")";
}

// A refused mount over a result filled with 0xab: the code, then the result untouched (on) or cleared (off).
static void Refused(bool on, const char* what, const char* dir, uint32_t mode, int want_rc) {
	SaveDataMountResult r;
	std::memset(&r, 0xab, sizeof(r));
	const SaveDataMountResult before = r;
	const int                 rc     = Mount(dir, mode, 0, &r);
	const bool                kept   = on ? Same(r, before) : IsZero(r);
	Check(rc == want_rc && kept, what,
	      "rc " + Hex(rc) + " (want " + Hex(want_rc) + "), result " + Describe(r, before, "untouched") + " (want " +
	          (on ? "untouched" : "cleared") + ")");
}

// ---- search (KytyPS5 4b0282e; KYTY_BC5_SAVEDATA_SORT for the mtime) ---------------------------------------------------

static int64_t FileTime(const std::string& path) {
	struct stat st {};
	return ::stat(path.c_str(), &st) == 0 ? static_cast<int64_t>(st.st_mtime) : -1;
}

static bool SetFileTime(const std::string& path, int hours_ahead) {
	std::error_code ec;
	std::filesystem::last_write_time(
	    path, std::filesystem::file_time_type::clock::now() + std::chrono::hours(hours_ahead), ec);
	return !ec;
}

// A search with up to 3 names (and their params when asked) for the key and order, by an optional name pattern.
static int SearchInto(SaveDataSortKey key, SaveDataSortOrder order, const char* pattern, SceSaveDataDirName* found,
                      SaveDataParam* params, SaveDataDirNameSearchResult* result) {
	const SceSaveDataDirName  name = Name(pattern != nullptr ? pattern : "");
	SaveDataDirNameSearchCond cond {};
	cond.user_id          = 1;
	cond.dir_name         = pattern != nullptr ? &name : nullptr;
	cond.key              = key;
	cond.order            = order;
	*result               = {};
	result->dir_names     = found;
	result->dir_names_num = 3;
	result->params        = params;
	return Libs::SaveData::SaveDataDirNameSearch(&cond, result);
}

static std::string Search(SaveDataSortKey key, SaveDataSortOrder order) {
	SceSaveDataDirName          found[3] {};
	SaveDataDirNameSearchResult result {};
	const int                   rc = SearchInto(key, order, nullptr, found, nullptr, &result);
	if (rc != OK || result.hit_num != 3 || result.set_num != 3) {
		return "rc " + Hex(rc) + " hits " + std::to_string(result.hit_num) + " set " + std::to_string(result.set_num);
	}
	return std::string(found[0].data) + " " + found[1].data + " " + found[2].data;
}

static void Order(SaveDataSortKey key, SaveDataSortOrder order, const char* what, const char* want) {
	const std::string got = Search(key, order);
	Check(got == want, what, "got \"" + got + "\", want \"" + want + "\"");
}

static void SearchChecks(bool sort_on) {
	g_step = "search";
	// KytyPS5 4b0282e, tests/SaveDataMemoryTests.cpp TestSearchSortKeys: the same three saves and orders.
	const char*        names[3]       = {"alpha", "bravo", "charlie"};
	constexpr uint64_t blocks[3]      = {96, 48, 48};
	constexpr uint32_t user_params[3] = {2, 3, 1};
	constexpr int      hours_ahead[3] = {1, 3, 2};
	constexpr int64_t  base_mtime     = 1800000000; // seconds since the epoch; any non-zero time is taken as set
	for (int i = 0; i < 3; i++) {
		SaveDataMountResult r {};
		Setup(Mount(names[i], kModeCreate, blocks[i], &r) == OK, "create a search save");
		SaveDataParam param {};
		param.user_param = user_params[i];
		param.mtime      = base_mtime + hours_ahead[i] * 3600;
		Setup(Libs::SaveData::SaveDataSetParam(&r.mount_point, 0, &param, sizeof(param)) == OK, "set its param");
		Setup(Umount(r) == OK, "unmount it");
	}
	std::error_code ec;
	Setup(std::filesystem::is_directory(Root("alpha"), ec),
	      "the saves are not under _SaveData/UNKNOWN (a param.sfo with a TITLE_ID loaded?)");
	// KytyPS5's test then moves each save's sce_sys/param.bin to now + its hours; this file keeps that record beside the
	// save, as <dir>.param.
	for (int i = 0; i < 3; i++) {
		Setup(SetFileTime(Root(names[i]) + ".param", hours_ahead[i]), "set a param record's file time");
	}

	Order(SaveDataSortKey::DirName, SaveDataSortOrder::Descent, "search by name, descending", "charlie bravo alpha");
	Order(SaveDataSortKey::UserParam, SaveDataSortOrder::Ascent, "search by user param", "charlie alpha bravo");
	Order(SaveDataSortKey::Blocks, SaveDataSortOrder::Ascent, "search by blocks (ties by name)", "bravo charlie alpha");
	Order(SaveDataSortKey::FreeBlocks, SaveDataSortOrder::Descent, "search by free blocks, descending",
	      "alpha charlie bravo");
	Order(SaveDataSortKey::Mtime, SaveDataSortOrder::Descent, "search by mtime, descending", "bravo charlie alpha");
	const bool removed = std::filesystem::remove(Root("alpha") + ".blocks", ec);
	Setup(removed, "remove alpha's .blocks record");
	Order(SaveDataSortKey::Blocks, SaveDataSortOrder::Ascent, "search by blocks, alpha without a record (the maximum)",
	      "bravo charlie alpha");

	// 7. alpha's record becomes the newest file (+5 h); the titles' mtimes stay +1 h, +3 h, +2 h.
	Setup(SetFileTime(Root("alpha") + ".param", 5), "move alpha's param record to +5 h");
	Order(SaveDataSortKey::Mtime, SaveDataSortOrder::Descent,
	      sort_on ? "search by mtime, the files' time (KYTY_BC5_SAVEDATA_SORT on)"
	              : "search by mtime, the title's time (KYTY_BC5_SAVEDATA_SORT off)",
	      sort_on ? "alpha bravo charlie" : "bravo charlie alpha");

	// 8. The mtime the search reports for alpha.
	{
		SceSaveDataDirName          found[3] {};
		SaveDataParam               params[3] {};
		SaveDataDirNameSearchResult result {};
		const int     rc   = SearchInto(SaveDataSortKey::DirName, SaveDataSortOrder::Ascent, nullptr, found, params, &result);
		const int64_t file = FileTime(Root("alpha") + ".param");
		const int64_t want = sort_on ? file : base_mtime + 3600;
		Check(rc == OK && result.set_num == 3 && std::strcmp(found[0].data, "alpha") == 0 && params[0].mtime == want &&
		          want > 0,
		      sort_on ? "the mtime the search reports: the files' (KYTY_BC5_SAVEDATA_SORT on)"
		              : "the mtime the search reports: the title's (KYTY_BC5_SAVEDATA_SORT off)",
		      Fmt("rc %s, set %u, first \"%s\", mtime %lld, want %lld (the record's file time %lld, the title's %lld)",
		          Hex(rc).c_str(), result.set_num, found[0].data, static_cast<long long>(params[0].mtime),
		          static_cast<long long>(want), static_cast<long long>(file), static_cast<long long>(base_mtime + 3600)));
	}

	// 9. A save with no file and no record (blocks 0 keeps none, no SetParam): its directory's time, not 0.
	{
		SaveDataMountResult r {};
		Setup(Mount("delta", kModeCreate2, 0, &r) == OK, "create the empty save");
		Setup(Umount(r) == OK, "unmount the empty save");
		SceSaveDataDirName          found[3] {};
		SaveDataParam               params[3] {};
		SaveDataDirNameSearchResult result {};
		const int     rc   = SearchInto(SaveDataSortKey::DirName, SaveDataSortOrder::Ascent, "delta", found, params, &result);
		const int64_t want = FileTime(Root("delta"));
		Check(rc == OK && result.hit_num == 1 && result.set_num == 1 && params[0].mtime == want && want > 0,
		      "a save with no file and no record reports its directory's time",
		      Fmt("rc %s, hits %u, mtime %lld, want %lld", Hex(rc).c_str(), result.hit_num,
		          static_cast<long long>(params[0].mtime), static_cast<long long>(want)));
	}
}

// ---- mount result (KytyPS5 dfec14a, KYTY_BC5_SAVEDATA_FIXES) ---------------------------------------------------------

static void MountChecks(bool on) {
	g_step = "mount result";
	// 1. A successful create clears the result (0xab before) and writes the point and status 1, in both settings.
	SaveDataMountResult r;
	std::memset(&r, 0xab, sizeof(r));
	int rc = Mount("slot", kModeCreate, 48, &r);
	Check(rc == OK && Same(r, Mounted("/savedata0", 1)), "a created mount's result",
	      "rc " + Hex(rc) + ", result " + Describe(r, Mounted("/savedata0", 1), "as wanted") +
	          " (want /savedata0, status 1, the rest 0)");

	// 2. BUSY over the mounted save, the result still holding that mount (KytyPS5 dfec14a's own case, mode 32 there too).
	SaveDataMountResult r2 = r;
	rc                     = Mount("slot", kModeCreate2, 48, &r2);
	Check(rc == Libs::SaveData::SAVE_DATA_ERROR_BUSY && (on ? Same(r2, r) : IsZero(r2)), "BUSY over the mounted save",
	      "rc " + Hex(rc) + " (want " + Hex(Libs::SaveData::SAVE_DATA_ERROR_BUSY) + "), result " +
	          Describe(r2, r, "untouched") + " (want " + (on ? "untouched" : "cleared") + ")");

	// 3. Unmounting through the BUSY call's result: on, it names the save; off, it names nothing (NOT_FOUND) and the
	// save stays mounted until the first result unmounts it. A failed on run unmounts it the same way, so the checks
	// after this one still start with every slot free.
	rc            = Umount(r2);
	const int rc2 = rc == OK ? OK : Umount(r);
	if (on) {
		Check(rc == OK, "unmount through the BUSY call's result",
		      "rc " + Hex(rc) + " (want 0); through the first result then " + Hex(rc2));
	} else {
		Check(rc == Libs::SaveData::SAVE_DATA_ERROR_NOT_FOUND && rc2 == OK, "unmount through the BUSY call's result",
		      "rc " + Hex(rc) + " (want NOT_FOUND), then through the first result " + Hex(rc2) + " (want 0)");
	}

	// 4. A successful open of the existing save: cleared, the point, status 0.
	std::memset(&r, 0xab, sizeof(r));
	rc = Mount("slot", kModeOpen, 0, &r);
	Check(rc == OK && Same(r, Mounted("/savedata0", 0)), "an opened mount's result",
	      "rc " + Hex(rc) + ", result " + Describe(r, Mounted("/savedata0", 0), "as wanted") +
	          " (want /savedata0, status 0, the rest 0)");
	Setup(rc != OK || Umount(r) == OK, "unmount the opened save");

	// 5-8. Refused before anything is mounted.
	Refused(on, "NOT_FOUND (open of a missing save)", "missing", kModeOpen, Libs::SaveData::SAVE_DATA_ERROR_NOT_FOUND);
	Refused(on, "EXISTS (create over a save)", "slot", kModeCreate, Libs::SaveData::SAVE_DATA_ERROR_EXISTS);
	Refused(on, "PARAMETER (no mode bit)", "slot", 0u, Libs::SaveData::SAVE_DATA_ERROR_PARAMETER);
	{
		std::ofstream blocker(Root("blocked")); // a file where the save directory would go
		Setup(blocker.good(), "make the file that blocks the save directory");
	}
	Refused(on, "NO_PERMISSION (the directory cannot be made)", "blocked", kModeCreate2,
	        Libs::SaveData::SAVE_DATA_ERROR_NO_PERMISSION);

	// 9. MOUNT_FULL with all 16 slots taken.
	SaveDataMountResult full[16] {};
	int                 mounted = 0;
	for (int i = 0; i < 16; i++) {
		char dir[16];
		std::snprintf(dir, sizeof(dir), "full%02d", i);
		if (Mount(dir, kModeCreate2, 0, &full[i]) == OK) {
			mounted++;
		}
	}
	Setup(mounted == 16, "fill the 16 mount slots");
	Refused(on, "MOUNT_FULL (16 slots taken)", "full16", kModeCreate2, Libs::SaveData::SAVE_DATA_ERROR_MOUNT_FULL);
	int unmounted = 0;
	for (int i = 0; i < mounted; i++) {
		if (Umount(full[i]) == OK) {
			unmounted++;
		}
	}
	Setup(unmounted == mounted, "unmount the 16");
}

// ---- events (AnyPS5 0d0abe09c, bc6b4d76f; KYTY_BC5_SAVEDATA_EVENT_CB) -------------------------------------------------

enum Callback : int { kFirst = 1, kSecond, kTerminating, kStale, kFence, kHolding, kA, kB, kUnregistering };

struct Call {
	int             callback   = 0;
	SaveDataEvent   event      = {};
	void*           userdata   = nullptr;
	std::thread::id thread     = {};
	int             terminated = 0; // what SaveDataTerminate returned inside the terminating callback
};

static std::mutex              g_calls_mutex;
static std::condition_variable g_calls_changed;
static std::vector<Call>       g_calls;
static std::atomic<int>        g_thread_exits {0};

static std::mutex              g_hold_mutex;
static std::condition_variable g_hold_changed;
static bool                    g_holding  = false;
static bool                    g_released = false;

struct ExitMark {
	ExitMark() = default;
	~ExitMark() { g_thread_exits.fetch_add(1); }
	ExitMark(const ExitMark&)            = delete;
	ExitMark& operator=(const ExitMark&) = delete;
};

static void Record(int callback, const SaveDataEvent* event, void* userdata, int terminated) {
	thread_local ExitMark mark; // its destructor runs when the delivering thread ends: the final terminate joins it
	Call                  call;
	call.callback   = callback;
	call.event      = event != nullptr ? *event : SaveDataEvent {};
	call.userdata   = userdata;
	call.thread     = std::this_thread::get_id();
	call.terminated = terminated;
	std::lock_guard lock(g_calls_mutex);
	g_calls.push_back(call);
	g_calls_changed.notify_all();
}

static KYTY_SYSV_ABI void First(const SaveDataEvent* event, void* userdata) {
	Record(kFirst, event, userdata, 0);
}
static KYTY_SYSV_ABI void Second(const SaveDataEvent* event, void* userdata) {
	Record(kSecond, event, userdata, 0);
}
static KYTY_SYSV_ABI void Terminating(const SaveDataEvent* event, void* userdata) {
	const int rc = Libs::SaveData::SaveDataTerminate();
	Record(kTerminating, event, userdata, rc);
}
static KYTY_SYSV_ABI void Stale(const SaveDataEvent* event, void* userdata) {
	Record(kStale, event, userdata, 0);
}
static KYTY_SYSV_ABI void Fence(const SaveDataEvent* event, void* userdata) {
	Record(kFence, event, userdata, 0);
}
static KYTY_SYSV_ABI void CallbackA(const SaveDataEvent* event, void* userdata) {
	Record(kA, event, userdata, 0);
}
static KYTY_SYSV_ABI void CallbackB(const SaveDataEvent* event, void* userdata) {
	Record(kB, event, userdata, 0);
}
// Holds the delivery thread in a callback until released (at most 10 s, so it can never hold it for good).
static KYTY_SYSV_ABI void Holding(const SaveDataEvent* event, void* userdata) {
	Record(kHolding, event, userdata, 0);
	std::unique_lock lock(g_hold_mutex);
	g_holding = true;
	g_hold_changed.notify_all();
	g_hold_changed.wait_for(lock, std::chrono::seconds(10), [] { return g_released; });
}

// Unregisters from inside the callback once the test has queued a second event (at most 5 s), so that event is
// pending when the unregister runs.
static std::atomic<bool> g_unregistering_entered {false};
static std::atomic<bool> g_second_queued {false};
static KYTY_SYSV_ABI void Unregistering(const SaveDataEvent* event, void* userdata) {
	g_unregistering_entered = true;
	const auto deadline     = std::chrono::steady_clock::now() + std::chrono::seconds(5);
	while (!g_second_queued.load() && std::chrono::steady_clock::now() < deadline) {
		std::this_thread::sleep_for(std::chrono::milliseconds(1));
	}
	const int rc = Libs::SaveData::SaveDataUnregisterEventCallback();
	Record(kUnregistering, event, userdata, rc);
}

static size_t CallCount() {
	std::lock_guard lock(g_calls_mutex);
	return g_calls.size();
}

static bool CallAt(size_t index, Call* call) {
	std::lock_guard lock(g_calls_mutex);
	if (index >= g_calls.size()) {
		return false;
	}
	*call = g_calls[index];
	return true;
}

static size_t CallsOf(int callback, size_t from) {
	std::lock_guard lock(g_calls_mutex);
	size_t          n = 0;
	for (size_t i = from; i < g_calls.size(); i++) {
		n += g_calls[i].callback == callback ? 1u : 0u;
	}
	return n;
}

static bool WaitForCalls(size_t count) {
	std::unique_lock lock(g_calls_mutex);
	return g_calls_changed.wait_for(lock, std::chrono::seconds(5), [&] { return g_calls.size() >= count; });
}

static bool WaitForCallback(int callback, size_t from) {
	std::unique_lock lock(g_calls_mutex);
	return g_calls_changed.wait_for(lock, std::chrono::seconds(5), [&] {
		for (size_t i = from; i < g_calls.size(); i++) {
			if (g_calls[i].callback == callback) {
				return true;
			}
		}
		return false;
	});
}

// No more calls than count after a while.
static bool QuietAt(size_t count, int ms) {
	std::this_thread::sleep_for(std::chrono::milliseconds(ms));
	return CallCount() == count;
}

// The process's threads (Linux: /proc/self/task); -1 where there is no task list (the laptop stand-in only).
static long TaskCount() {
#ifdef __linux__
	std::error_code ec;
	long            n = 0;
	for (auto it = std::filesystem::directory_iterator("/proc/self/task", ec);
	     !ec && it != std::filesystem::directory_iterator(); it.increment(ec)) {
		n++;
	}
	return ec ? -1 : n;
#else
	return -1;
#endif
}

static bool ThreadsAre(long base, long delivery_threads) {
	return base < 0 || TaskCount() == base + delivery_threads;
}

static bool WaitForThreads(long base, long delivery_threads) {
	if (base < 0) {
		return true;
	}
	const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(5);
	while (TaskCount() != base + delivery_threads) {
		if (std::chrono::steady_clock::now() > deadline) {
			return false;
		}
		std::this_thread::sleep_for(std::chrono::milliseconds(1));
	}
	return true;
}

static std::string Threads(long base) {
	return base < 0 ? std::string("not counted") : std::to_string(TaskCount() - base);
}

static int Init() {
	return Libs::SaveData::SaveDataInitialize3(nullptr);
}
static int Term() {
	return Libs::SaveData::SaveDataTerminate();
}
static int Reg(SaveDataEventCallback callback, void* userdata) {
	return Libs::SaveData::SaveDataRegisterEventCallback(callback, userdata);
}
static int Unreg() {
	return Libs::SaveData::SaveDataUnregisterEventCallback();
}
static int Backup(const char* dir) {
	const SceSaveDataDirName name = Name(dir);
	BackupParam              b {};
	b.user_id  = 1;
	b.dir_name = &name;
	return Libs::SaveData::SaveDataBackup(&b);
}
static int Commit(uint32_t mode) {
	SaveDataCommitParam p {};
	p.commit_mode = mode;
	return Libs::SaveData::SaveDataCommit(&p);
}
static int Poll(SaveDataEvent* event) {
	return Libs::SaveData::SaveDataGetEventResult(nullptr, event);
}
static int Drain() {
	SaveDataEvent e {};
	int           n = 0;
	while (Poll(&e) == OK) {
		n++;
	}
	return n;
}
static bool IsEvent(const SaveDataEvent& e, uint32_t type, const char* dir) {
	return e.type == type && std::strncmp(e.dir_name.data, dir, sizeof(e.dir_name.data)) == 0;
}
static bool SameEvent(const SaveDataEvent& a, const SaveDataEvent& b) {
	return std::memcmp(&a, &b, sizeof(a)) == 0;
}
static std::string Ev(const SaveDataEvent& e) {
	char dir[33] = {};
	std::memcpy(dir, e.dir_name.data, sizeof(e.dir_name.data));
	return Fmt("type %u dir \"%s\" user %d", e.type, dir, e.user_id);
}
static std::string Desc(const Call& c, std::thread::id delivery) {
	return Fmt("callback %d, %s, %s userdata, %s", c.callback, Ev(c.event).c_str(), c.userdata != nullptr ? "a" : "no",
	           c.thread == delivery ? "the delivery thread" : "another thread");
}

static Loader::SymbolResolve Key(const char* library, const char* nid) { // a title's import key for that table
	Loader::SymbolResolve r {};
	r.name                 = nid;
	r.library              = library;
	r.library_version      = 1;
	r.module               = library;
	r.module_version_major = 1;
	r.module_version_minor = 1;
	r.type                 = Loader::SymbolType::Func;
	return r;
}

// 14. Two threads re-register (A, B, now and then unregister) while one backs up and one polls.
static void RegisterRaces(long base) {
	g_step = "events: re-registration races";
	int               tag_a = 0, tag_b = 0, tag_fence = 0;
	const int         i     = Init();
	const int         r0    = Reg(CallbackA, &tag_a);
	const size_t      start = CallCount();
	std::atomic<bool> go {false};
	std::atomic<int>  bad_reg {0}, bad_backup {0}, bad_poll {0};
	auto              registrar = [&](int phase) {
		while (!go.load()) {
			std::this_thread::yield();
		}
		for (int k = 0; k < 2000; k++) {
			const int n  = k + phase;
			const int rc = (n % 5 == 4) ? Unreg() : ((n % 2) != 0 ? Reg(CallbackA, &tag_a) : Reg(CallbackB, &tag_b));
			if (rc != OK) {
				bad_reg++;
			}
		}
	};
	std::thread r1(registrar, 0);
	std::thread r2(registrar, 1);
	std::thread producer([&] {
		while (!go.load()) {
			std::this_thread::yield();
		}
		for (int k = 0; k < 300; k++) {
			if (Backup("raced") != OK) {
				bad_backup++;
			}
		}
	});
	std::thread poller([&] {
		while (!go.load()) {
			std::this_thread::yield();
		}
		SaveDataEvent e {};
		for (int k = 0; k < 3000; k++) {
			const int rc = Poll(&e);
			if (rc != OK && rc != Libs::SaveData::SAVE_DATA_ERROR_NOT_FOUND) {
				bad_poll++;
			}
		}
	});
	go = true;
	r1.join();
	r2.join();
	producer.join();
	poller.join();
	const int    u      = Unreg(); // waits for a callback in progress; none of A or B may come after it
	const size_t after  = CallCount();
	const int    rf     = Reg(Fence, &tag_fence);
	const int    bf     = Backup("fence");
	const bool   fenced = WaitForCallback(kFence, after);
	int          a = 0, b = 0, mismatched = 0, late = 0, other = 0;
	bool         one_thread = true;
	{
		std::lock_guard lock(g_calls_mutex);
		for (size_t k = start; k < g_calls.size(); k++) {
			const Call& c = g_calls[k];
			one_thread    = one_thread && c.thread == g_calls[start].thread;
			if (c.callback == kA || c.callback == kB) {
				(c.callback == kA ? a : b)++;
				mismatched += c.userdata != (c.callback == kA ? static_cast<void*>(&tag_a) : static_cast<void*>(&tag_b)) ? 1 : 0;
				late += k >= after ? 1 : 0;
			} else if (c.callback != kFence) {
				other++;
			}
		}
	}
	const int  u2     = Unreg();
	(void)Drain();
	const int  exits  = g_thread_exits.load();
	const int  t      = Term();
	const bool joined = g_thread_exits.load() == exits + 1;
	const bool gone   = WaitForThreads(base, 0);
	Check(i == OK && r0 == OK && bad_reg == 0 && bad_backup == 0 && bad_poll == 0 && u == OK && rf == OK && bf == OK &&
	          fenced && mismatched == 0 && late == 0 && other == 0 && one_thread && u2 == OK && t == OK && joined && gone,
	      "re-registrations on two threads racing backups and polls",
	      Fmt("init %s, register %s; failed registrations %d, backups %d, polls %d; unregister %s; calls A %d, B %d, with "
	          "the other's userdata %d, after the unregister %d, other %d, %s; fence register %s, backup %s, delivered %s; "
	          "terminate %s, joined %s, threads %s",
	          Hex(i).c_str(), Hex(r0).c_str(), bad_reg.load(), bad_backup.load(), bad_poll.load(), Hex(u).c_str(), a, b,
	          mismatched, late, other, one_thread ? "one thread" : "more than one thread", Hex(rf).c_str(),
	          Hex(bf).c_str(), fenced ? "yes" : "no", Hex(t).c_str(), joined ? "yes" : "no", Threads(base).c_str()));
}

// 15. A registration racing the final terminate on two threads (AnyPS5 bc6b4d76f's case). Every other time both start at
// once; every other time the delivery thread is held in a callback and the registration starts 10 ms before the
// terminate, so it waits for the calling lock across the whole terminate (a registration that read the count before
// taking its locks would then register after the terminate, every time).
static void TerminateRaces(long base) {
	g_step = "events: registration racing the final terminate";
	constexpr int kIterations = 100;
	int           tag_hold = 0, tag_stale = 0, tag_fence = 0;
	const size_t  start      = CallCount();
	int           ran        = 0;
	int           registered = 0, not_initialized = 0;
	std::string   failure;
	for (; ran < kIterations; ran++) {
		const bool hold = ran % 2 == 0;
		if (Init() != OK) {
			failure = "Initialize3 failed";
			break;
		}
		if (hold) {
			{
				std::lock_guard lock(g_hold_mutex);
				g_holding  = false;
				g_released = false;
			}
			if (Reg(Holding, &tag_hold) != OK || Backup("held") != OK) {
				failure = "the holding callback's registration or backup failed";
				break;
			}
			std::unique_lock lock(g_hold_mutex);
			if (!g_hold_changed.wait_for(lock, std::chrono::seconds(5), [] { return g_holding; })) {
				failure = "the holding callback did not run within 5 s";
				break;
			}
		}
		std::atomic<bool> go_register {false};
		std::atomic<bool> go_terminate {false};
		int               reg  = 0;
		int               term = 0;
		std::thread       registering([&] {
			while (!go_register.load()) {
				std::this_thread::yield();
			}
			reg = Reg(Stale, &tag_stale);
		});
		std::thread       terminating([&] {
			while (!go_terminate.load()) {
				std::this_thread::yield();
			}
			term = Term();
		});
		go_register = true;
		if (hold) { // the registration first: it waits for the calling lock the held callback keeps
			std::this_thread::sleep_for(std::chrono::milliseconds(10));
		}
		go_terminate = true;
		if (hold) {
			std::this_thread::sleep_for(std::chrono::milliseconds(20));
			{
				std::lock_guard lock(g_hold_mutex);
				g_released = true;
			}
			g_hold_changed.notify_all();
		}
		registering.join();
		terminating.join();
		if (term != OK || (reg != OK && reg != Libs::SaveData::SAVE_DATA_ERROR_NOT_INITIALIZED)) {
			failure = Fmt("iteration %d: the racing terminate %s, the racing registration %s", ran, Hex(term).c_str(),
			              Hex(reg).c_str());
			break;
		}
		(reg == OK ? registered : not_initialized)++;
		if (Init() != OK || Backup("raced") != OK) {
			failure = Fmt("iteration %d: Initialize3 or the backup after the race failed", ran);
			break;
		}
		const size_t before = CallCount();
		if (Reg(Fence, &tag_fence) != OK || Backup("fenced") != OK || !WaitForCallback(kFence, before)) {
			failure = Fmt("iteration %d: the fence callback did not get its backup within 5 s", ran);
			break;
		}
		if (CallsOf(kStale, start) != 0) {
			failure = Fmt("iteration %d: the callback registered beside the final terminate was called", ran);
			break;
		}
		(void)Unreg();
		(void)Drain();
		if (Term() != OK) {
			failure = Fmt("iteration %d: the iteration's own terminate failed", ran);
			break;
		}
	}
	if (!failure.empty()) { // leave nothing held, registered or initialized behind
		{
			std::lock_guard lock(g_hold_mutex);
			g_released = true;
		}
		g_hold_changed.notify_all();
		(void)Unreg();
		(void)Drain();
		(void)Term();
		(void)Term();
	}
	const size_t stale = CallsOf(kStale, start);
	const bool   gone  = WaitForThreads(base, 0);
	Check(failure.empty() && ran == kIterations && stale == 0 && gone,
	      "registrations racing the final terminate (bc6b4d76f), every other one held and registering first",
	      Fmt("%d of %d iterations%s%s; registration OK %d, NOT_INITIALIZED %d; the raced callback called %zu times; "
	          "delivery threads left %s",
	          ran, kIterations, failure.empty() ? "" : ": ", failure.c_str(), registered, not_initialized, stale,
	          Threads(base).c_str()));
}

static void EventChecks(bool on) {
	// 1. The unit's registration of the two exports.
	g_step = "events: the registration";
	{
		Loader::SymbolDatabase db;
		Libs::InitSaveData_1(&db);
		const bool control = db.FindByNid("j8xKtiFj0SY", Loader::SymbolType::Func) != nullptr; // GetEventResult
		struct Export {
			const char* nid;
			uint64_t    address;
		};
		const Export exports[] = {
		    {"hsKd5c21sQc", reinterpret_cast<uint64_t>(&Libs::SaveData::SaveDataRegisterEventCallback)},
		    {"v-AK1AxQhS0", reinterpret_cast<uint64_t>(&Libs::SaveData::SaveDataUnregisterEventCallback)},
		};
		int found = 0, right = 0, by_nid = 0;
		for (const Export& e: exports) {
			by_nid += db.FindByNid(e.nid, Loader::SymbolType::Func) != nullptr ? 1 : 0;
			for (const char* library: {"SaveData", "SaveData_native"}) {
				const Loader::SymbolRecord* rec = db.Find(Key(library, e.nid));
				found += rec != nullptr ? 1 : 0;
				right += rec != nullptr && rec->vaddr == e.address ? 1 : 0;
			}
		}
		const std::string detail = Fmt("GetEventResult %s; by NID %d of 2; by the two tables' import keys %d of 4, %d at "
		                               "the unit's functions",
		                               control ? "registered" : "missing (InitSaveData_1 did not run as expected)",
		                               by_nid, found, right);
		if (on) {
			Check(control && by_nid == 2 && found == 4 && right == 4,
			      "the event callback exports are registered in both tables (KYTY_BC5_SAVEDATA_EVENT_CB on)", detail);
		} else {
			Check(control && by_nid == 0 && found == 0,
			      "the event callback exports are not registered (KYTY_BC5_SAVEDATA_EVENT_CB off)", detail);
		}
	}

	// 2. Polling, the same in both settings: a backup's event, a BACKUP_ASYNC commit's (a plain one queues none).
	g_step = "events: polling";
	{
		const int     i  = Init();
		const int     b  = Backup("polled");
		const int     c0 = Commit(0);
		const int     c1 = Commit(kCommitBackupAsync);
		SaveDataEvent e1 {}, e2 {}, e3 {};
		const int     p1 = Poll(&e1);
		const int     p2 = Poll(&e2);
		const int     p3 = Poll(&e3);
		const int     t  = Term();
		Check(i == OK && b == OK && c0 == OK && c1 == OK && p1 == OK && IsEvent(e1, 2, "polled") && e1.user_id == 1 &&
		          p2 == OK && e2.type == 4 && p3 == Libs::SaveData::SAVE_DATA_ERROR_NOT_FOUND && t == OK,
		      "polling: a backup's and a commit's events, then none",
		      Fmt("init %s, backup %s, commits %s %s; polls %s (%s), %s (%s), %s; terminate %s", Hex(i).c_str(),
		          Hex(b).c_str(), Hex(c0).c_str(), Hex(c1).c_str(), Hex(p1).c_str(), Ev(e1).c_str(), Hex(p2).c_str(),
		          Ev(e2).c_str(), Hex(p3).c_str(), Hex(t).c_str()));
	}
	if (!on) {
		return;
	}

	const auto      main_thread = std::this_thread::get_id();
	const long      base        = TaskCount();
	std::thread::id delivery {};
	int             tag_first = 0, tag_second = 0, tag_term = 0;
	SaveDataEvent   polled {};
	Call            c;

	// 3. The registration's rules, and no thread before a registration succeeds (0d0abe09c).
	g_step = "events: the registration's rules";
	{
		const int  r1   = Reg(First, &tag_first);
		const int  u1   = Unreg();
		const int  i    = Init();
		const int  r2   = Reg(nullptr, &tag_first);
		const bool none = ThreadsAre(base, 0);
		Check(r1 == Libs::SaveData::SAVE_DATA_ERROR_NOT_INITIALIZED && u1 == OK && i == OK &&
		          r2 == Libs::SaveData::SAVE_DATA_ERROR_PARAMETER && none,
		      "register before Initialize3 is NOT_INITIALIZED, a null callback PARAMETER, and no thread starts",
		      Fmt("register %s (want NOT_INITIALIZED), unregister %s, init %s, null register %s (want PARAMETER), "
		          "delivery threads %s (want 0)",
		          Hex(r1).c_str(), Hex(u1).c_str(), Hex(i).c_str(), Hex(r2).c_str(), Threads(base).c_str()));
	}

	// 4. A backup reaches the callback on the delivery thread, once, and the poll returns the same event.
	g_step = "events: a backup's delivery";
	{
		const size_t before = CallCount();
		const int    r      = Reg(First, &tag_first);
		const bool   one    = ThreadsAre(base, 1);
		const int    b      = Backup("backed");
		const bool   came   = WaitForCalls(before + 1);
		const bool   once   = QuietAt(before + 1, 100);
		const bool   got    = CallAt(before, &c);
		const int    p      = Poll(&polled);
		delivery            = c.thread;
		Check(r == OK && one && b == OK && came && once && got && c.callback == kFirst && c.userdata == &tag_first &&
		          IsEvent(c.event, 2, "backed") && c.event.user_id == 1 && c.thread != main_thread && p == OK &&
		          SameEvent(polled, c.event),
		      "a backup reaches the callback on the delivery thread within 5 s, and the poll",
		      Fmt("register %s, delivery threads %s (want 1), backup %s, delivered %s, calls %zu (want 1): %s, %s; "
		          "poll %s (%s)",
		          Hex(r).c_str(), Threads(base).c_str(), Hex(b).c_str(), came ? "yes" : "no", CallCount() - before,
		          got ? Desc(c, delivery).c_str() : "none", c.thread != main_thread ? "not the caller's" : "the caller's",
		          Hex(p).c_str(), Ev(polled).c_str()));
	}

	// 5. A BACKUP_ASYNC commit (type 4) on the same thread and in the poll; a plain commit queues nothing.
	g_step = "events: a commit's delivery";
	{
		const size_t  before = CallCount();
		const int     c0     = Commit(0);
		const int     c1     = Commit(kCommitBackupAsync);
		const bool    came   = WaitForCalls(before + 1);
		const bool    once   = QuietAt(before + 1, 100);
		const bool    got    = CallAt(before, &c);
		const int     p      = Poll(&polled);
		SaveDataEvent none {};
		const int     p2 = Poll(&none);
		Check(c0 == OK && c1 == OK && came && once && got && c.callback == kFirst && c.event.type == 4 &&
		          c.thread == delivery && p == OK && polled.type == 4 && p2 == Libs::SaveData::SAVE_DATA_ERROR_NOT_FOUND,
		      "a commit's BACKUP_ASYNC event reaches the callback on the same thread, and the poll",
		      Fmt("commits %s %s, delivered %s, calls %zu (want 1): %s; polls %s (%s), %s", Hex(c0).c_str(),
		          Hex(c1).c_str(), came ? "yes" : "no", CallCount() - before, got ? Desc(c, delivery).c_str() : "none",
		          Hex(p).c_str(), Ev(polled).c_str(), Hex(p2).c_str()));
	}

	// 6. A BACKUP_ASYNC unmount (type 1, queued under the mount lock).
	g_step = "events: an unmount's delivery";
	{
		SaveDataMountResult m {};
		const int           mr     = Mount("cbmount", kModeCreate2, 0, &m);
		const size_t        before = CallCount();
		const int           u      = Libs::SaveData::SaveDataUmount2(kUmountBackupAsync, &m.mount_point);
		const bool          came   = WaitForCalls(before + 1);
		const bool          once   = QuietAt(before + 1, 100);
		const bool          got    = CallAt(before, &c);
		const int           p      = Poll(&polled);
		Check(mr == OK && u == OK && came && once && got && c.callback == kFirst && c.event.type == 1 &&
		          c.thread == delivery && p == OK && polled.type == 1,
		      "an unmount's BACKUP_ASYNC event reaches the callback on the same thread, and the poll",
		      Fmt("mount %s, unmount %s, delivered %s, calls %zu (want 1): %s; poll %s (%s)", Hex(mr).c_str(),
		          Hex(u).c_str(), came ? "yes" : "no", CallCount() - before, got ? Desc(c, delivery).c_str() : "none",
		          Hex(p).c_str(), Ev(polled).c_str()));
	}

	// 7. A replacing registration takes the next event, on the same thread.
	g_step = "events: a replacing registration";
	{
		const size_t before  = CallCount();
		const int    r       = Reg(Second, &tag_second);
		const bool   one     = ThreadsAre(base, 1);
		const int    b       = Backup("replaced");
		const bool   came    = WaitForCalls(before + 1);
		const bool   once    = QuietAt(before + 1, 100);
		const bool   got     = CallAt(before, &c);
		const int    drained = Drain();
		Check(r == OK && one && b == OK && came && once && got && c.callback == kSecond && c.userdata == &tag_second &&
		          IsEvent(c.event, 2, "replaced") && c.thread == delivery && drained == 1,
		      "a replacing registration takes the next event on the same thread",
		      Fmt("register %s, delivery threads %s (want 1), backup %s, delivered %s, calls %zu (want 1): %s; polled %d",
		          Hex(r).c_str(), Threads(base).c_str(), Hex(b).c_str(), came ? "yes" : "no", CallCount() - before,
		          got ? Desc(c, delivery).c_str() : "none", drained));
	}

	// 8. After unregister no callback runs; the poll still has the event.
	g_step = "events: unregister";
	{
		const int    u      = Unreg();
		const size_t before = CallCount();
		const int    b      = Backup("unwatched");
		const bool   quiet  = QuietAt(before, 300);
		const int    p      = Poll(&polled);
		Check(u == OK && b == OK && quiet && p == OK && IsEvent(polled, 2, "unwatched"),
		      "after unregister no callback runs, and the poll still has the event",
		      Fmt("unregister %s, backup %s, calls %zu (want 0), poll %s (%s)", Hex(u).c_str(), Hex(b).c_str(),
		          CallCount() - before, Hex(p).c_str(), Ev(polled).c_str()));
	}

	// 9. An unregister from inside the callback drops the delivery still pending (AnyPS5: unregistering drops the
	// completions not yet delivered): the second backup is queued while the first one's callback runs.
	g_step = "events: an unregister from inside the callback";
	{
		int          tag_unreg = 0;
		const size_t before    = CallCount();
		g_unregistering_entered = false;
		g_second_queued         = false;
		const int  r       = Reg(Unregistering, &tag_unreg);
		const int  b1      = Backup("pending1");
		const auto waiting = std::chrono::steady_clock::now() + std::chrono::seconds(5);
		while (!g_unregistering_entered.load() && std::chrono::steady_clock::now() < waiting) {
			std::this_thread::sleep_for(std::chrono::milliseconds(1));
		}
		const bool entered = g_unregistering_entered.load();
		const int  b2      = Backup("pending2"); // the callback is still registered: this one is now pending
		g_second_queued    = true;
		const bool came    = WaitForCalls(before + 1);
		const bool quiet   = QuietAt(before + 1, 300);
		const bool got     = CallAt(before, &c);
		const int  drained = Drain();
		Check(r == OK && b1 == OK && entered && b2 == OK && came && quiet && got && c.callback == kUnregistering &&
		          c.terminated == OK && IsEvent(c.event, 2, "pending1") && c.thread == delivery && drained == 2,
		      "an unregister from inside the callback drops the delivery still pending",
		      Fmt("register %s, backups %s %s, callback entered %s, calls %zu (want 1, none for pending2): %s, its "
		          "unregister %s; polled %d (want 2)",
		          Hex(r).c_str(), Hex(b1).c_str(), Hex(b2).c_str(), entered ? "yes" : "no", CallCount() - before,
		          got ? Desc(c, delivery).c_str() : "none", Hex(got ? c.terminated : 0).c_str(), drained));
	}

	// 10. A registration after unregister reuses the delivery thread.
	g_step = "events: a registration after unregister";
	{
		const size_t before  = CallCount();
		const int    r       = Reg(First, &tag_first);
		const bool   one     = ThreadsAre(base, 1);
		const int    b       = Backup("rewatched");
		const bool   came    = WaitForCalls(before + 1);
		const bool   got     = CallAt(before, &c);
		const int    drained = Drain();
		Check(r == OK && one && b == OK && came && got && c.callback == kFirst && IsEvent(c.event, 2, "rewatched") &&
		          c.thread == delivery && drained == 1,
		      "a registration after unregister uses the same delivery thread",
		      Fmt("register %s, delivery threads %s (want 1), backup %s, delivered %s: %s; polled %d", Hex(r).c_str(),
		          Threads(base).c_str(), Hex(b).c_str(), came ? "yes" : "no", got ? Desc(c, delivery).c_str() : "none",
		          drained));
	}

	// 11. A terminate from inside the callback is BUSY.
	g_step = "events: a terminate from inside the callback";
	{
		const size_t before  = CallCount();
		const int    r       = Reg(Terminating, &tag_term);
		const int    b       = Backup("terminating");
		const bool   came    = WaitForCalls(before + 1);
		const bool   got     = CallAt(before, &c);
		const int    drained = Drain();
		const int    u       = Unreg();
		Check(r == OK && b == OK && came && got && c.callback == kTerminating &&
		          c.terminated == Libs::SaveData::SAVE_DATA_ERROR_BUSY && drained == 1 && u == OK,
		      "a terminate from inside the callback is BUSY",
		      Fmt("register %s, backup %s, delivered %s, terminate inside %s (want BUSY %s), polled %d, unregister %s",
		          Hex(r).c_str(), Hex(b).c_str(), came ? "yes" : "no", Hex(got ? c.terminated : 0).c_str(),
		          Hex(Libs::SaveData::SAVE_DATA_ERROR_BUSY).c_str(), drained, Hex(u).c_str()));
	}

	// 12. The final terminate joins the delivery thread.
	g_step = "events: the final terminate";
	{
		const int  exits  = g_thread_exits.load();
		const int  t      = Term();
		const bool joined = g_thread_exits.load() == exits + 1;
		const bool gone   = WaitForThreads(base, 0);
		Check(t == OK && joined && gone, "the final terminate joins the delivery thread",
		      Fmt("terminate %s, the delivery thread %s when it returned, delivery threads %s after 5 s at most",
		          Hex(t).c_str(), joined ? "had ended" : "had not ended", Threads(base).c_str()));
	}

	// 13. That terminate dropped the registration; after a new Initialize3 events reach a callback only once one
	// registers again, on a new delivery thread.
	g_step = "events: initialize again";
	{
		const int    r1      = Reg(First, &tag_first);
		const int    i       = Init();
		const size_t before  = CallCount();
		const int    b1      = Backup("restarted");
		const bool   quiet   = QuietAt(before, 300);
		const int    p       = Poll(&polled);
		const bool   none    = ThreadsAre(base, 0);
		const int    r2      = Reg(First, &tag_first);
		const bool   one     = ThreadsAre(base, 1);
		const int    b2      = Backup("redelivered");
		const bool   came    = WaitForCalls(before + 1);
		const bool   got     = CallAt(before, &c);
		const int    drained = Drain();
		const int    u       = Unreg();
		const int    exits   = g_thread_exits.load();
		const int    t       = Term();
		const bool   joined  = g_thread_exits.load() == exits + 1;
		const bool   gone    = WaitForThreads(base, 0);
		Check(r1 == Libs::SaveData::SAVE_DATA_ERROR_NOT_INITIALIZED && i == OK && b1 == OK && quiet && p == OK &&
		          IsEvent(polled, 2, "restarted") && none && r2 == OK && one && b2 == OK && came && got &&
		          c.callback == kFirst && IsEvent(c.event, 2, "redelivered") && c.thread != main_thread &&
		          drained == 1 && u == OK && t == OK && joined && gone,
		      "the final terminate dropped the registration; after Initialize3 only a new registration delivers",
		      Fmt("register after terminate %s (want NOT_INITIALIZED), init %s, backup %s, calls before registering %s, "
		          "poll %s (%s), threads before %s; register %s, backup %s, delivered %s: %s; terminate %s, joined %s, "
		          "delivery threads %s",
		          Hex(r1).c_str(), Hex(i).c_str(), Hex(b1).c_str(), quiet ? "none" : "some", Hex(p).c_str(),
		          Ev(polled).c_str(), none ? "none" : "some", Hex(r2).c_str(), Hex(b2).c_str(), came ? "yes" : "no",
		          got ? Desc(c, c.thread).c_str() : "none", Hex(t).c_str(), joined ? "yes" : "no",
		          Threads(base).c_str()));
	}

	RegisterRaces(base);  // 14
	TerminateRaces(base); // 15
}

} // namespace sav0401

int main(int argc, char* argv[]) {
	using namespace sav0401;
	if (argc != 2 || (std::strcmp(argv[1], "on") != 0 && std::strcmp(argv[1], "off") != 0)) {
		std::printf("usage: sav0401 on|off (on: exactly one of KYTY_BC5_SAVEDATA_FIXES, KYTY_BC5_SAVEDATA_EVENT_CB, "
		            "KYTY_BC5_SAVEDATA_SORT on; off: none)\n");
		return 2;
	}
	const bool  on       = std::strcmp(argv[1], "on") == 0;
	const char* names[3] = {"KYTY_BC5_SAVEDATA_FIXES", "KYTY_BC5_SAVEDATA_EVENT_CB", "KYTY_BC5_SAVEDATA_SORT"};
	const bool  fixes    = SwitchOn(names[0]);
	const bool  event_cb = SwitchOn(names[1]);
	const bool  sort     = SwitchOn(names[2]);
	const int   n_on     = (fixes ? 1 : 0) + (event_cb ? 1 : 0) + (sort ? 1 : 0);
	std::printf("sav0401: switches");
	for (const char* n: names) {
		const char* v = std::getenv(n);
		std::printf(" %s=%s", n, v != nullptr ? (v[0] != '\0' ? v : "(empty)") : "(unset)");
	}
	std::printf("\n");
	if ((on && n_on != 1) || (!on && n_on != 0)) {
		std::printf("sav0401: the argument says %s but %d of the three switches are on (on needs exactly one, off none)\n",
		            argv[1], n_on);
		return 2;
	}
	if (std::getenv("KYTY_BC5_SAVEDATA_DIR") != nullptr) {
		std::printf("sav0401: KYTY_BC5_SAVEDATA_DIR is set; unset it (this test must never come near a real save)\n");
		return 2;
	}
	if (std::getenv("KYTY_BC5_SAVE_TRACE") != nullptr) {
		std::printf("sav0401: unset KYTY_BC5_SAVE_TRACE (its trace needs the log subsystem, which most runs of this test do "
		            "not start)\n");
		return 2;
	}
	std::fflush(stdout);
	::Log::Bc5SetLogging(false); // LOGF stays silent from the first subsystem on
	std::thread(Watchdog).detach();

	// The subsystems the calls need: Common and Threads as main.cpp starts them (the mount table's constructor checks
	// for the main thread), then FileSystem (its mount table). With the event callback on, also what a guest thread
	// needs, as emulator.cpp starts it: Config (printf direction Silent), Log, Timer, Memory (the guest stack) and
	// Pthread, and the RuntimeLinker singleton, made here on the main thread (a guest thread's end asks it to drop its TLS).
	auto& slist   = *Common::SubsystemsList::Instance();
	auto* core    = Common::CommonSubsystem::Instance();
	auto* threads = Common::ThreadsSubsystem::Instance();
	auto* fs      = Libs::LibKernel::FileSystem::FileSystemSubsystem::Instance();
	auto* config  = Config::ConfigSubsystem::Instance();
	slist.SetArgs(argc, argv);
	slist.Add(core, {});
	slist.Add(threads, {core});
	slist.Add(fs, {core, threads});
	if (event_cb) {
		slist.Add(config, {core});
	}
	if (!slist.InitAll(false)) {
		std::printf("sav0401: subsystem %s failed: %s\n", slist.GetFailName(), slist.GetFailMsg());
		return 1;
	}
	if (event_cb) {
		Config::ConfigOptions options;
		options.printf_direction = Config::OutputDirection::Silent;
		Config::Load(options);
		auto* log     = Log::LogSubsystem::Instance();
		auto* timer   = Loader::Timer::TimerSubsystem::Instance();
		auto* memory  = Libs::LibKernel::Memory::MemorySubsystem::Instance();
		auto* pthread = Libs::LibKernel::PthreadSubsystem::Instance();
		slist.Add(log, {core, config});
		slist.Add(timer, {core, log});
		slist.Add(memory, {core, log});
		slist.Add(pthread, {core, log, timer});
		if (!slist.InitAll(false)) {
			std::printf("sav0401: subsystem %s failed: %s\n", slist.GetFailName(), slist.GetFailMsg());
			return 1;
		}
		(void)Common::Singleton<Loader::RuntimeLinker>::Instance();
#ifdef __linux__
		Setup(TaskCount() > 0, "read /proc/self/task");
#endif
	}

	std::error_code             ec;
	const std::filesystem::path home = std::filesystem::current_path(ec);
	const std::filesystem::path work = home / ("sav0401-work-" + std::to_string(::getpid()));
	if (ec || std::filesystem::exists(work, ec) || !std::filesystem::create_directory(work, ec)) {
		std::printf("sav0401: cannot make a fresh %s\n", work.string().c_str());
		return 1;
	}
	std::filesystem::current_path(work, ec);
	if (ec) {
		std::printf("sav0401: cannot enter %s\n", work.string().c_str());
		return 1;
	}

	SearchChecks(sort);
	MountChecks(fixes);
	EventChecks(event_cb);

	g_step = "clean-up";
	std::filesystem::current_path(home, ec);
	std::filesystem::remove_all(work, ec); // only the directory this run made
	g_finished = true;

	const int expected = kSearchChecks + kMountChecks + (event_cb ? kEventChecksOn : kEventChecksOff);
	if (!g_setup_ok || g_checks != expected || g_passed != g_checks) {
		std::printf("sav0401: %s %d of %d passed, %d expected%s\n", argv[1], g_passed, g_checks, expected,
		            g_setup_ok ? "" : ", setup failed");
		std::fflush(stdout);
		std::_Exit(1);
	}
	std::printf("sav0401: %s %d of %d; end\n", argv[1], g_passed, g_checks);
	std::fflush(stdout);
	std::_Exit(0); // no static destructors: the Pthread subsystem's helper thread may still run
}
