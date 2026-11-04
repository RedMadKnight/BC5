// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0401 series e5, port group "svc": a CPU test of mksvc0405.py's three units, without a game, a GPU, a
// window, a sound device or a network. It calls the host's own functions, linked from the emulator's objects with the
// private libSaveData.cpp.o, libNet.cpp.o and libPad.cpp.o, and the libraries' own registrations (InitSaveData_1,
// InitNet_1_Http, InitNet_1_Http2, InitPad_1) into a SymbolDatabase for the functions the units keep static. Five
// switches, each check expecting the setting of its own switch (or item, for the two comma-list switches):
//   KYTY_BC5_SAVEDATA_MEMORY_FIXES (sync, lock, existed), KYTY_BC5_SAVEDATA_DELETE_BUSY, KYTY_BC5_SAVEDATA_ALIASES,
//   KYTY_BC5_HTTP2_FIXES (async, ssl, agent), KYTY_BC5_PAD_OPEN_EXT.
// "on" needs at least one of them on, "off" none. 21 checks in every setting:
//   Memory (7): 1 Sync before any Setup: MEMORY_NOT_READY with "sync" on, OK off (today), no event, no file either way.
//     2 Sync's argument checks (null, slot 4, option 2: PARAMETER; user -1: INVALID_LOGIN_USER) on; OK off; no event.
//     3 Setup on a run with no memory file: existed_memory_size 0 with "existed" on, 0x10000 (the memory's size) off; it
//     writes no file. 4 Sync after Setup: OK; with "sync" on the file is written (0x10000 bytes) and the poll returns
//     one type-3 event (user 1, error 0, title UNKNOWN, dir sce_sdmemory), then NOT_FOUND; off no file and no event.
//     5 Sync with option 1: OK, no event. 6 slot 1: MEMORY_NOT_READY before its Setup (on), then an event naming
//     sce_sdmemory1; off OK and no event. 7 Set writes the file (0x10000 bytes, both settings); Setup then reports
//     0x10000; with the file made 0x12340 bytes long by the test, Setup reports 0x12340 with "existed" on, 0x10000 off.
//   Queue (2): 8 with "lock" on, 3000 backups on one thread against polls on another: every polled event intact, at
//     least one polled; off, one backup polled on one thread (today's queue; the race is not run without the lock).
//     9 Terminate clears the queue (both).
//   Delete (2): 10 a mounted save: BUSY and kept with KYTY_BC5_SAVEDATA_DELETE_BUSY on, deleted (OK) off. 11 after
//     Umount2 the delete is OK and the save is gone (both).
//   Aliases (2): 12 ZkZhskCPXFw and l1NmDeDpNGU at SaveDataInitialize3 in both SaveData tables (on), absent (off).
//     13 on: both called through their records return OK; off: SaveDataInitialize3 returns OK.
//   Http (5): 14 "ssl": SslEnable/DisableOption on a context id: 0 on, INVALID_ID off; a bogus id INVALID_ID both.
//     15 "async": SendRequestAsync with {equeue, 7, udata}: returns 0; a zero-timeout wait on the equeue gives user
//     event 7 with that udata on, none (ETIMEDOUT) off; WaitAsync: event 0, result TIMEOUT. 16 ReadDataAsync on that
//     failed request with {equeue, 8, udata}: event 8 on, none off; WaitAsync: event 1, result TIMEOUT. 17 a null
//     kqueue_option and an unknown request trigger nothing (both). 18 "agent": sceHttpCreateTemplate's record is the
//     wrapper on (a NULL and a named user agent both make a template), today's Network::Http::HttpCreateTemplate off
//     (only the named one is called: today's NULL builds a std::string from NULL, which aborts).
//   Pad (3): 19 WFIiSfXGUq8 registered on, absent off (xk0AcarP3V4 at Controller::PadOpen both). 20 on, through the
//     record: (1000,1,0) 1, (1000,0,0) 1, (1000,2,0) 1, (1001,1,0) 2, (1003,1,0) 4, (255,16,0) 1 and 0x80920001 for
//     (1000,3,0), (255,1,0), (1000,1,1), (999,1,0), (1004,1,0); off: scePadOpen (1000,0,0) 1, (255,16,0) 1.
//     21 scePadOpen is unchanged: (1000,1,0) 0x80920001, (1001,0,0) 2 (both).
// SaveData safety: the test refuses to start when KYTY_BC5_SAVEDATA_DIR is set (any value) or when it cannot make a
// fresh directory svc0405-work-<pid> under the current one; it checks that directory (a real directory, not a link,
// directly under the current directory) before any SaveData call, enters it, and sets KYTY_BC5_SAVEDATA_DIR to its
// absolute <work>/_SaveData; the unit's other saves (Mount3, Delete) are relative to the current directory, so every
// file the test makes is under <work>; it checks the memory file at that absolute path, and removes only <work> at
// the end. No param.sfo is loaded, so the title is UNKNOWN. It refuses e4's three SaveData switches on (they change the
// queue and Terminate) and KYTY_BC5_SAVE_TRACE set.
// A watchdog ends a hang after 120 s with a FAIL line naming the step (exit 3). Each check prints one line; the run ends
// with exactly "svc0405: on|off 21 of 21; end" and exit 0, or a count line and exit 1. Exit 2 for a wrong argument or
// environment.
// Build (box, build0401.py): --gate svc0405.cpp <out> --like src/libs/libSaveData.cpp, linked with every emulator object
// but main.cpp.o and the three private units in place of the shared ones. Linked with the shared libSaveData.cpp.o it
// still links but checks 1-7 fail (no sync, no existed); with the shared libPad/libNet ones the "on" checks fail.
// Runtime state: Common, Threads, FileSystem (the mount table), Config (printf direction Silent) and Log (InitPad_1
// turns its PRINT_NAME on, which asks the Log for its direction), Network (sceHttpCreateTemplate's g_net), as
// emulator.cpp starts them. Logging off (Log::Bc5SetLogging(false)).
// usage: KYTY_BC5_SAVEDATA_MEMORY_FIXES=1 KYTY_BC5_SAVEDATA_DELETE_BUSY=1 KYTY_BC5_SAVEDATA_ALIASES=1 \
//          KYTY_BC5_HTTP2_FIXES=1 KYTY_BC5_PAD_OPEN_EXT=1 ./svc0405 on
//        (all =0, or all unset) ./svc0405 off        (one switch, or a comma list, at a time also works with "on")
// Run it from a directory on the NVMe (e.g. ~/bc5-work/exp0401e5/run-...). Each run also prints the units' stderr lines
// "[bc5] exp 0405: ... on (items: ...)|off" and e4's "[bc5] exp 0401: savedata ... off" lines.

#include "common/abi.h"
#include "common/commonSubsystem.h"
#include "common/emulatorConfig.h"
#include "common/logging/log.h"
#include "common/singleton.h"
#include "common/subsystems.h"
#include "common/threads.h"
#include "kernel/eventQueue.h"
#include "kernel/fileSystem.h"
#include "libs/controller.h"
#include "libs/errno.h"
#include "libs/network.h"
#include "loader/symbolDatabase.h"

#include <atomic>
#include <chrono>
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <string>
#include <system_error>
#include <thread>
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

struct SaveDataIcon {
	void*   buf;
	size_t  buf_size;
	size_t  data_size;
	uint8_t reserved[32];
};

struct SaveDataMemoryData {
	void*   buf;
	size_t  buf_size;
	int64_t offset;
	uint8_t reserved[40];
};

struct SaveDataMemorySetup2 {
	uint32_t             option;
	int32_t              user_id;
	size_t               memory_size;
	size_t               icon_memory_size;
	const SaveDataParam* init_param;
	const SaveDataIcon*  init_icon;
	uint32_t             slot_id;
	uint8_t              reserved[20];
};

struct SaveDataMemorySetupResult {
	size_t  existed_memory_size;
	uint8_t reserved[16];
};

struct SaveDataMemorySet2 {
	int32_t                   user_id;
	uint8_t                   padding[4];
	const SaveDataMemoryData* data;
	const SaveDataParam*      param;
	const SaveDataIcon*       icon;
	uint32_t                  data_num;
	uint32_t                  slot_id;
	uint8_t                   reserved[24];
};

struct SaveDataDelete {
	int32_t                   user_id;
	int32_t                   pad;
	const SceSaveDataTitleId* title_id;
	const SceSaveDataDirName* dir_name;
	uint32_t                  unused;
	uint8_t                   reserved[32];
	int32_t                   pad2;
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

// The functions SaveDataMount3, SaveDataDelete and SaveDataBackup below hide the structures of the same names, as in
// the unit; these aliases name the structures.
using Mount3Param = SaveDataMount3;
using DeleteParam = SaveDataDelete;
using BackupParam = SaveDataBackup;

int KYTY_SYSV_ABI SaveDataInitialize3(const void* init);
int KYTY_SYSV_ABI SaveDataTerminate();
int KYTY_SYSV_ABI SaveDataMount3(const SaveDataMount3* mount, SaveDataMountResult* mount_result);
int KYTY_SYSV_ABI SaveDataUmount2(uint32_t mode, const SaveDataMountPoint* mount_point);
int KYTY_SYSV_ABI SaveDataDelete(const SaveDataDelete* del);
int KYTY_SYSV_ABI SaveDataSetupSaveDataMemory2(const SaveDataMemorySetup2* setup_param, SaveDataMemorySetupResult* result);
int KYTY_SYSV_ABI SaveDataSetSaveDataMemory2(const SaveDataMemorySet2* set_param);
int KYTY_SYSV_ABI SaveDataSyncSaveDataMemory(const void* sync_param);
int KYTY_SYSV_ABI SaveDataGetEventResult(const void* event_param, SaveDataEvent* event);
int KYTY_SYSV_ABI SaveDataBackup(const SaveDataBackup* backup);

} // namespace Libs::SaveData

namespace Libs {
void InitSaveData_1(Loader::SymbolDatabase* s); // the unit's LIB_DEFINE(InitSaveData_1)
void InitPad_1(Loader::SymbolDatabase* s);      // libPad.cpp's LIB_DEFINE(InitPad_1)
namespace LibHttp {
void InitNet_1_Http(Loader::SymbolDatabase* s); // libNet.cpp's LIB_DEFINE(InitNet_1_Http)
} // namespace LibHttp
namespace LibHttp2 {
void InitNet_1_Http2(Loader::SymbolDatabase* s); // libNet.cpp's LIB_DEFINE(InitNet_1_Http2)
} // namespace LibHttp2
} // namespace Libs

namespace svc0405 {

namespace SD = Libs::SaveData;
namespace EQ = Libs::LibKernel::EventQueue;

static_assert(sizeof(SD::SaveDataMemorySetup2) == 64);
static_assert(sizeof(SD::SaveDataMemorySet2) == 64);
static_assert(sizeof(SD::SaveDataEvent) == 104);
static_assert(sizeof(SD::Mount3Param) == 80);
static_assert(sizeof(SD::SaveDataMountResult) == 64);

constexpr int kChecks          = 21;
constexpr int kWatchdogSeconds = 120;

constexpr int kPadInvalidArg = -2137915391; /* 0x80920001, controller.cpp PadOpen */
constexpr int kHttp2InvalidId = -2122641152; /* 0x817B1100, libNet.cpp */
constexpr int kHttp2Timeout   = -2122641304; /* 0x817B1068, libNet.cpp */

constexpr uint32_t kModeCreate2 = 32u; // the unit's create2: makes the save when it is missing

// KytyPS5 dfec14a SaveDataMemorySync, as the unit takes it (passed as const void*).
struct MemorySync {
	int32_t  user_id;
	uint32_t slot_id;
	uint32_t option;
	uint8_t  reserved[28];
};
static_assert(sizeof(MemorySync) == 40);

// KytyPS5 a06e356 Http2TriggerUserEventArgs, as the unit takes it.
struct TriggerArgs {
	EQ::KernelEqueue eq;
	int              uniq_id;
	uint8_t          padding[4];
	void*            udata;
	void*            reserved;
};
static_assert(sizeof(TriggerArgs) == 32);

struct Http2AsyncResult { // libNet.cpp's
	int     event_type;
	int     req_id;
	int     result;
	uint8_t padding[4];
	void*   reserved;
};

using InitFn          = KYTY_SYSV_ABI int (*)(const void* init);
using Http2InitFn     = KYTY_SYSV_ABI int (*)(int, int, size_t, int);
using Http2TmplFn     = KYTY_SYSV_ABI int (*)(int, const char*, int, int);
using Http2RequestFn  = KYTY_SYSV_ABI int (*)(int, const char*, const char*, uint64_t);
using Http2SendAsync  = KYTY_SYSV_ABI int (*)(int, const void*, size_t, void*, void*);
using Http2ReadAsync  = KYTY_SYSV_ABI int (*)(int, void*, size_t, void*, void*);
using Http2WaitFn     = KYTY_SYSV_ABI int (*)(int, Http2AsyncResult*, uint32_t*, void*);
using Http2SslFn      = KYTY_SYSV_ABI int (*)(int, uint32_t);
using HttpTemplateFn  = KYTY_SYSV_ABI int (*)(int, const char*, int, int);
using PadOpenFn       = KYTY_SYSV_ABI int (*)(int, int, int, const void*);

static int                      g_checks = 0;
static int                      g_passed = 0;
static std::atomic<const char*> g_step {"setup"};
static std::atomic<bool>        g_finished {false};

static std::string Fmt(const char* format, ...) __attribute__((format(printf, 1, 2)));
static std::string Fmt(const char* format, ...) {
	char    buf[1024];
	va_list args;
	va_start(args, format);
	std::vsnprintf(buf, sizeof(buf), format, args);
	va_end(args);
	return buf;
}

static void Check(bool ok, const char* what, const std::string& detail) {
	g_checks++;
	if (ok) {
		g_passed++;
		std::printf("svc0405: ok %d %s\n", g_checks, what);
	} else {
		std::printf("svc0405: FAIL %d %s: %s\n", g_checks, what, detail.c_str());
	}
	std::fflush(stdout);
}

static std::string Hex(int rc) {
	return Fmt("0x%08x", static_cast<unsigned>(rc));
}

static void Watchdog() {
	const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(kWatchdogSeconds);
	while (std::chrono::steady_clock::now() < deadline) {
		if (g_finished.load()) {
			return;
		}
		std::this_thread::sleep_for(std::chrono::milliseconds(100));
	}
	std::printf("svc0405: FAIL watchdog: \"%s\" did not finish within %d s\n", g_step.load(), kWatchdogSeconds);
	std::fflush(stdout);
	std::_Exit(3);
}

// ---- the switches, read as the units read them ------------------------------------------------------------------------

static bool SwitchOn(const char* name) {
	const char* e = std::getenv(name);
	return e != nullptr && e[0] != '\0' && std::strcmp(e, "0") != 0;
}

// A comma-list switch: 0 off; the named items; every item for a value that names none.
static uint32_t Items(const char* name, const char* const* items, int count) {
	const char* e = std::getenv(name);
	if (e == nullptr || e[0] == '\0' || std::strcmp(e, "0") == 0) {
		return 0;
	}
	uint32_t    got = 0;
	const char* p   = e;
	for (;;) {
		const char*  comma = std::strchr(p, ',');
		const size_t n     = comma != nullptr ? static_cast<size_t>(comma - p) : std::strlen(p);
		for (int i = 0; i < count; i++) {
			if (n == std::strlen(items[i]) && std::strncmp(p, items[i], n) == 0) {
				got |= 1u << static_cast<unsigned>(i);
			}
		}
		if (comma == nullptr) {
			break;
		}
		p = comma + 1;
	}
	return got != 0 ? got : (1u << static_cast<unsigned>(count)) - 1u;
}

struct Settings {
	bool sync    = false;
	bool lock    = false;
	bool existed = false;
	bool del     = false;
	bool aliases = false;
	bool async   = false;
	bool ssl     = false;
	bool agent   = false;
	bool pad     = false;
};

// ---- SaveData helpers ---------------------------------------------------------------------------------------------------

static std::filesystem::path g_memory_file; // <work>/_SaveData/UNKNOWN/sce_sdmemory/memory.dat

static SD::SceSaveDataDirName Name(const char* s) {
	SD::SceSaveDataDirName n {};
	std::snprintf(n.data, sizeof(n.data), "%s", s);
	return n;
}

static int Sync(int32_t user, uint32_t slot, uint32_t option) {
	MemorySync p {};
	p.user_id = user;
	p.slot_id = slot;
	p.option  = option;
	return SD::SaveDataSyncSaveDataMemory(&p);
}

static int Setup(uint32_t slot, size_t size, size_t* existed) {
	SD::SaveDataMemorySetup2      p {};
	SD::SaveDataMemorySetupResult r {};
	r.existed_memory_size = 0xdeadbeef;
	p.user_id             = 1;
	p.memory_size         = size;
	p.slot_id             = slot;
	const int rc          = SD::SaveDataSetupSaveDataMemory2(&p, &r);
	*existed              = r.existed_memory_size;
	return rc;
}

static int Poll(SD::SaveDataEvent* e) {
	*e = {};
	return SD::SaveDataGetEventResult(nullptr, e);
}

static bool IsEvent(const SD::SaveDataEvent& e, uint32_t type, int32_t user, const char* dir) {
	return e.type == type && e.user_id == user && std::strncmp(e.dir_name.data, dir, sizeof(e.dir_name.data)) == 0;
}

static std::string Ev(const SD::SaveDataEvent& e) {
	char dir[33]   = {};
	char title[11] = {};
	std::memcpy(dir, e.dir_name.data, sizeof(e.dir_name.data));
	std::memcpy(title, e.title_id.data, sizeof(e.title_id.data));
	return Fmt("type %u user %d error %s title \"%s\" dir \"%s\"", e.type, e.user_id, Hex(e.error_code).c_str(), title, dir);
}

// The poll's next answer: "none" for NOT_FOUND, the event otherwise.
static std::string Next(SD::SaveDataEvent* e, int* rc) {
	*rc = Poll(e);
	return *rc == SD::SAVE_DATA_ERROR_NOT_FOUND ? std::string("none") : (*rc == OK ? Ev(*e) : "rc " + Hex(*rc));
}

static long long FileSize() { // -1: no memory file
	std::error_code ec;
	const auto      size = std::filesystem::file_size(g_memory_file, ec);
	return ec ? -1 : static_cast<long long>(size);
}

static int Backup(const char* dir, int32_t user) {
	const SD::SceSaveDataDirName name = Name(dir);
	SD::BackupParam              b {};
	b.user_id  = user;
	b.dir_name = &name;
	return SD::SaveDataBackup(&b);
}

static int Drain() { // events left in the poll queue
	SD::SaveDataEvent e {};
	int               n = 0;
	while (Poll(&e) == OK) {
		n++;
	}
	return n;
}

// ---- 1-7: memory ----------------------------------------------------------------------------------------------------------

static void MemoryChecks(const Settings& s) {
	SD::SaveDataEvent e {};
	int               prc = 0;

	g_step = "memory: sync before setup";
	{
		const int         rc   = Sync(1, 0, 0);
		const std::string next = Next(&e, &prc);
		const long long   size = FileSize();
		const int         want = s.sync ? SD::SAVE_DATA_ERROR_MEMORY_NOT_READY : OK;
		Check(rc == want && prc == SD::SAVE_DATA_ERROR_NOT_FOUND && size == -1,
		      s.sync ? "a sync before any setup is MEMORY_NOT_READY (sync on)" : "a sync before any setup is OK (sync off, today)",
		      Fmt("rc %s (want %s), next event %s, memory file %lld bytes (want none)", Hex(rc).c_str(), Hex(want).c_str(),
		          next.c_str(), size));
	}

	g_step = "memory: sync's argument checks";
	{
		const int       null_rc   = SD::SaveDataSyncSaveDataMemory(nullptr);
		const int       slot_rc   = Sync(1, 4, 0);
		const int       option_rc = Sync(1, 0, 2);
		const int       user_rc   = Sync(-1, 0, 0);
		const int       drained   = Drain();
		const long long size      = FileSize();
		const int  par = s.sync ? SD::SAVE_DATA_ERROR_PARAMETER : OK;
		const int  usr = s.sync ? SD::SAVE_DATA_ERROR_INVALID_LOGIN_USER : OK;
		const bool ok  = null_rc == par && slot_rc == par && option_rc == par && user_rc == usr && drained == 0 && size == -1;
		Check(ok, s.sync ? "sync's arguments are checked (sync on)" : "sync's arguments are not checked (sync off, today)",
		      Fmt("null %s, slot 4 %s, option 2 %s (want %s), user -1 %s (want %s), events %d, memory file %lld", Hex(null_rc).c_str(),
		          Hex(slot_rc).c_str(), Hex(option_rc).c_str(), Hex(par).c_str(), Hex(user_rc).c_str(), Hex(usr).c_str(), drained,
		          size));
	}

	g_step = "memory: setup on a run with no memory file";
	{
		size_t          existed = 0;
		const int       rc      = Setup(0, 0x8000, &existed);
		const long long size    = FileSize();
		const size_t    want    = s.existed ? 0 : 0x10000;
		Check(rc == OK && existed == want && size == -1,
		      s.existed ? "a first setup reports existed 0 (existed on)" : "a first setup reports the memory's size (existed off, today)",
		      Fmt("rc %s, existed 0x%zx (want 0x%zx), memory file %lld (want none)", Hex(rc).c_str(), existed, want, size));
	}

	g_step = "memory: sync after setup";
	{
		const int         rc    = Sync(1, 0, 0);
		const std::string next  = Next(&e, &prc);
		const bool        event = prc == OK && IsEvent(e, 3, 1, "sce_sdmemory") && e.error_code == OK &&
		                   std::strncmp(e.title_id.data, "UNKNOWN", sizeof(e.title_id.data)) == 0;
		const std::string after = Next(&e, &prc);
		const bool        none  = prc == SD::SAVE_DATA_ERROR_NOT_FOUND;
		const long long   size  = FileSize();
		const bool        ok    = s.sync ? (rc == OK && event && none && size == 0x10000)
		                                 : (rc == OK && next == "none" && size == -1);
		Check(ok,
		      s.sync ? "a sync after setup writes the memory and queues MEMORY_SYNC_END (sync on)"
		             : "a sync after setup writes nothing and queues nothing (sync off, today)",
		      Fmt("rc %s, first poll %s, second poll %s, memory file %lld bytes", Hex(rc).c_str(), next.c_str(), after.c_str(),
		          size));
	}

	g_step = "memory: sync with option 1";
	{
		const int         rc   = Sync(1, 0, 1);
		const std::string next = Next(&e, &prc);
		Check(rc == OK && prc == SD::SAVE_DATA_ERROR_NOT_FOUND, "a sync with option 1 queues no event (both)",
		      Fmt("rc %s, next event %s", Hex(rc).c_str(), next.c_str()));
	}

	g_step = "memory: slot 1";
	{
		const int         before = Sync(1, 1, 0);
		size_t            existed = 0;
		const int         setup  = Setup(1, 0x8000, &existed);
		const int         rc     = Sync(1, 1, 0);
		const std::string next   = Next(&e, &prc);
		const bool        event  = prc == OK && IsEvent(e, 3, 1, "sce_sdmemory1");
		const int         left   = Drain();
		const bool        ok     = s.sync ? (before == SD::SAVE_DATA_ERROR_MEMORY_NOT_READY && setup == OK && rc == OK && event &&
		                                     left == 0)
		                                  : (before == OK && setup == OK && rc == OK && next == "none" && left == 0);
		Check(ok,
		      s.sync ? "slot 1 is not ready before its setup, then its event names sce_sdmemory1 (sync on)"
		             : "slot 1 syncs OK with no event (sync off, today)",
		      Fmt("sync before setup %s, setup %s, sync %s, poll %s, events left %d", Hex(before).c_str(), Hex(setup).c_str(),
		          Hex(rc).c_str(), next.c_str(), left));
	}

	g_step = "memory: existed after a set";
	{
		uint8_t                bytes[16];
		SD::SaveDataMemoryData data {};
		SD::SaveDataMemorySet2 set {};
		std::memset(bytes, 0x5a, sizeof(bytes));
		data.buf      = bytes;
		data.buf_size = sizeof(bytes);
		data.offset   = 0x20;
		set.user_id   = 1;
		set.data      = &data;
		set.data_num  = 1;
		const int       set_rc  = SD::SaveDataSetSaveDataMemory2(&set);
		const long long written = FileSize();
		size_t          existed1 = 0, existed2 = 0;
		const int       setup1   = Setup(0, 0x8000, &existed1);
		std::error_code ec;
		std::filesystem::resize_file(g_memory_file, 0x12340, ec); // the run's own file, inside <work>
		const int    setup2 = Setup(0, 0x8000, &existed2);
		const size_t want2  = s.existed ? 0x12340 : 0x10000;
		Check(set_rc == OK && written == 0x10000 && setup1 == OK && existed1 == 0x10000 && !ec && setup2 == OK &&
		          existed2 == want2,
		      s.existed ? "setup reports the stored file's size (existed on)" : "setup reports the memory's size (existed off, today)",
		      Fmt("set %s, file %lld bytes (want 0x10000) at %s, setup %s existed 0x%zx (want 0x10000), file made 0x12340 (%s), "
		          "setup %s existed 0x%zx (want 0x%zx)",
		          Hex(set_rc).c_str(), written, g_memory_file.string().c_str(), Hex(setup1).c_str(), existed1,
		          ec ? ec.message().c_str() : "ok", Hex(setup2).c_str(), existed2, want2));
	}
}

// ---- 8-9: the poll queue ----------------------------------------------------------------------------------------------------

static void QueueChecks(const Settings& s) {
	g_step = "queue: backups against polls";
	if (s.lock) {
		constexpr int     kBackups = 3000;
		std::atomic<bool> done {false};
		std::atomic<int>  backup_errors {0};
		std::thread       producer([&] {
            for (int i = 0; i < kBackups; i++) {
                if (Backup("race", 2) != OK) {
                    backup_errors++;
                }
            }
            done = true;
        });
		int polled = 0, bad = 0;
		for (;;) {
			SD::SaveDataEvent e {};
			const int         rc = Poll(&e);
			if (rc == OK) {
				polled++;
				bad += IsEvent(e, 2, 2, "race") ? 0 : 1;
			} else if (rc != SD::SAVE_DATA_ERROR_NOT_FOUND) {
				bad++;
			} else if (done.load()) {
				break;
			}
		}
		producer.join();
		const int left = Drain();
		Check(backup_errors == 0 && bad == 0 && polled + left >= 1 && left <= 20,
		      "3000 backups against polls on two threads: every event intact (lock on)",
		      Fmt("backup errors %d, events polled %d, broken %d, left %d (the queue keeps 20)", backup_errors.load(), polled,
		          bad, left));
	} else {
		const int         b  = Backup("single", 2);
		SD::SaveDataEvent e {};
		int               rc = 0;
		const std::string next = Next(&e, &rc);
		const int         left = Drain();
		Check(b == OK && rc == OK && IsEvent(e, 2, 2, "single") && left == 0,
		      "a backup's event is polled on one thread (lock off, today; the race is not run without the lock)",
		      Fmt("backup %s, poll %s, left %d", Hex(b).c_str(), next.c_str(), left));
	}

	g_step = "queue: terminate clears it";
	{
		const int b1 = Backup("t1", 3);
		const int b2 = Backup("t2", 3);
		const int t  = SD::SaveDataTerminate();
		const int i  = SD::SaveDataInitialize3(nullptr);
		const int left = Drain();
		Check(b1 == OK && b2 == OK && t == OK && i == OK && left == 0, "Terminate clears the poll queue (both)",
		      Fmt("backups %s %s, terminate %s, initialize %s, events left %d", Hex(b1).c_str(), Hex(b2).c_str(), Hex(t).c_str(),
		          Hex(i).c_str(), left));
	}
}

// ---- 10-11: delete -------------------------------------------------------------------------------------------------------

static void DeleteChecks(const Settings& s) {
	const SD::SceSaveDataDirName name = Name("busy1");
	const std::string            dir  = "_SaveData/UNKNOWN/busy1";
	SD::DeleteParam              del {};
	del.user_id  = 1;
	del.dir_name = &name;

	g_step = "delete: a mounted save";
	SD::SaveDataMountResult r {};
	{
		SD::Mount3Param m {};
		m.user_id    = 1;
		m.dir_name   = &name;
		m.mount_mode = kModeCreate2;
		const int mount = SD::SaveDataMount3(&m, &r);
		std::error_code ec;
		std::filesystem::create_directories(dir + "/data", ec); // a file in the save, as a title writes it
		std::FILE* f = std::fopen((dir + "/data/slot.bin").c_str(), "wb");
		if (f != nullptr) {
			std::fputs("svc0405", f);
			std::fclose(f);
		}
		const bool made    = std::filesystem::exists(dir + "/data/slot.bin", ec);
		const int  rc      = SD::SaveDataDelete(&del);
		const bool kept    = std::filesystem::exists(dir + "/data/slot.bin", ec);
		const int  want    = s.del ? SD::SAVE_DATA_ERROR_BUSY : OK;
		Check(mount == OK && made && rc == want && kept == s.del,
		      s.del ? "deleting a mounted save is BUSY and keeps it (delete busy on)"
		            : "deleting a mounted save removes it (delete busy off, today)",
		      Fmt("mount %s at \"%.16s\", file made %s, delete %s (want %s), file %s", Hex(mount).c_str(), r.mount_point.data,
		          made ? "yes" : "no", Hex(rc).c_str(), Hex(want).c_str(), kept ? "kept" : "gone"));
	}

	g_step = "delete: after the unmount";
	{
		const int       u  = SD::SaveDataUmount2(0, &r.mount_point);
		const int       rc = SD::SaveDataDelete(&del);
		std::error_code ec;
		const bool      gone = !std::filesystem::exists(dir, ec);
		Check(u == OK && rc == OK && gone, "after Umount2 the delete is OK and the save is gone (both)",
		      Fmt("umount %s, delete %s, directory %s", Hex(u).c_str(), Hex(rc).c_str(), gone ? "gone" : "still there"));
	}
}

// ---- 12-13: the Initialize aliases ------------------------------------------------------------------------------------------

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

static void AliasChecks(const Settings& s) {
	g_step = "aliases: the registration";
	Loader::SymbolDatabase db;
	Libs::InitSaveData_1(&db);
	const uint64_t init3   = reinterpret_cast<uint64_t>(&SD::SaveDataInitialize3);
	const bool     control = db.FindByNid("TywrFKCoLGY", Loader::SymbolType::Func) != nullptr;
	int            found = 0, right = 0;
	const char*    nids[2] = {"ZkZhskCPXFw", "l1NmDeDpNGU"};
	for (const char* nid: nids) {
		for (const char* library: {"SaveData", "SaveData_native"}) {
			const Loader::SymbolRecord* rec = db.Find(Key(library, nid));
			found += rec != nullptr ? 1 : 0;
			right += rec != nullptr && rec->vaddr == init3 ? 1 : 0;
		}
	}
	Check(control && (s.aliases ? (found == 4 && right == 4) : found == 0),
	      s.aliases ? "Initialize and Initialize2 are Initialize3 in both tables (aliases on)"
	                : "Initialize and Initialize2 are not registered (aliases off, today)",
	      Fmt("Initialize3 %s; aliases found %d of 4, %d at SaveDataInitialize3", control ? "registered" : "missing", found,
	          right));

	g_step = "aliases: the calls";
	if (s.aliases) {
		int rcs[2] = {-1, -1};
		for (int k = 0; k < 2; k++) {
			const Loader::SymbolRecord* rec = db.Find(Key("SaveData", nids[k]));
			rcs[k]                          = rec != nullptr ? reinterpret_cast<InitFn>(rec->vaddr)(nullptr) : -1;
		}
		Check(rcs[0] == OK && rcs[1] == OK, "Initialize and Initialize2 return OK through their records (aliases on)",
		      Fmt("Initialize %s, Initialize2 %s", Hex(rcs[0]).c_str(), Hex(rcs[1]).c_str()));
	} else {
		const int rc = SD::SaveDataInitialize3(nullptr);
		Check(rc == OK, "Initialize3 returns OK (aliases off, today)", "rc " + Hex(rc));
	}
}

// ---- 14-18: Http and Http2 ------------------------------------------------------------------------------------------------

template <typename F>
static F Fn(const Loader::SymbolDatabase& db, const char* nid) {
	const Loader::SymbolRecord* rec = db.FindByNid(nid, Loader::SymbolType::Func);
	return rec != nullptr ? reinterpret_cast<F>(rec->vaddr) : nullptr;
}

// The user events a zero-timeout wait finds: "none" for ETIMEDOUT, else "<id>/<udata>" each.
static std::string Waited(EQ::KernelEqueue eq, int* count, EQ::KernelEvent* first) {
	EQ::KernelEvent         ev[4] {};
	int                     out  = -1;
	Libs::LibKernel::KernelUseconds zero = 0;
	const int               rc   = EQ::KernelWaitEqueue(eq, ev, 4, &out, &zero);
	*count                         = rc == OK ? out : 0;
	*first                         = ev[0];
	if (rc == Libs::LibKernel::KERNEL_ERROR_ETIMEDOUT) {
		return "none";
	}
	if (rc != OK) {
		return "rc " + Hex(rc);
	}
	std::string s;
	for (int k = 0; k < out && k < 4; k++) {
		s += Fmt("%sid %llu filter %d udata %p", k == 0 ? "" : ", ", static_cast<unsigned long long>(ev[k].ident),
		         ev[k].filter, ev[k].udata);
	}
	return s;
}

static void HttpChecks(const Settings& s) {
	g_step = "http2: the registration";
	Loader::SymbolDatabase db;
	Libs::LibHttp2::InitNet_1_Http2(&db);
	const auto init    = Fn<Http2InitFn>(db, "3JCe3lCbQ8A");
	const auto tmpl    = Fn<Http2TmplFn>(db, "+wCt7fCijgk");
	const auto request = Fn<Http2RequestFn>(db, "mmyOCxQMVYQ");
	const auto send_async    = Fn<Http2SendAsync>(db, "A+NVAFu4eCg");
	const auto read_async    = Fn<Http2ReadAsync>(db, "bGN-6zbo7ms");
	const auto wait_async    = Fn<Http2WaitFn>(db, "MOp-AUhdfi8");
	const auto enable  = Fn<Http2SslFn>(db, "EWcwMpbr5F8");
	const auto disable = Fn<Http2SslFn>(db, "B37SruheQ5Y");
	if (init == nullptr || tmpl == nullptr || request == nullptr || send_async == nullptr || read_async == nullptr || wait_async == nullptr ||
	    enable == nullptr || disable == nullptr) {
		for (int k = 0; k < 4; k++) {
			Check(false, "http2", "InitNet_1_Http2 did not register the calls this test takes");
		}
	} else {
		// 14. A context's SSL options; this is the run's first Http2 call, so no template or request has the context's id.
		g_step = "http2: ssl options on a context";
		{
			const int ctx   = init(0, 0, 0x10000, 1);
			const int en    = enable(ctx, 0x1u);
			const int dis   = disable(ctx, 0x1u);
			const int bogus = enable(ctx + 1000, 0x1u);
			const int want  = s.ssl ? 0 : kHttp2InvalidId;
			Check(ctx > 0 && en == want && dis == want && bogus == kHttp2InvalidId,
			      s.ssl ? "SSL options are accepted on a context (ssl on)" : "SSL options on a context are INVALID_ID (ssl off, today)",
			      Fmt("context %d, enable %s, disable %s (want %s), a bogus id %s", ctx, Hex(en).c_str(), Hex(dis).c_str(),
			          Hex(want).c_str(), Hex(bogus).c_str()));

			EQ::KernelEqueue eq       = EQ::KERNEL_EQUEUE_INVALID;
			const int        made     = EQ::KernelCreateEqueue(&eq, "svc0405");
			const int        add7     = EQ::KernelAddUserEventEdge(eq, 7);
			const int        add8     = EQ::KernelAddUserEventEdge(eq, 8);
			const int        t        = tmpl(ctx, "svc0405", 2, 0);
			const int        r        = request(t, "GET", "https://example.invalid/svc0405", 0); // never contacted
			int              tag7 = 0, tag8 = 0;
			EQ::KernelEvent  first {};
			int              count = 0;

			// 15. SendRequestAsync.
			g_step = "http2: SendRequestAsync's event";
			{
				TriggerArgs       args {eq, 7, {}, &tag7, nullptr};
				const int         rc     = send_async(r, nullptr, 0, &args, nullptr);
				const std::string got    = Waited(eq, &count, &first);
				Http2AsyncResult  result {};
				const int         w      = wait_async(r, &result, nullptr, nullptr);
				const bool        event  = count == 1 && first.ident == 7 && first.filter == EQ::KERNEL_EVFILT_USER &&
				                   first.udata == &tag7;
				const bool        setup  = made == OK && add7 == OK && add8 == OK && t > 0 && r > 0;
				Check(setup && rc == 0 && (s.async ? event : got == "none") && w == 0 && result.event_type == 0 &&
				          result.result == kHttp2Timeout,
				      s.async ? "SendRequestAsync triggers the caller's user event (async on)"
				              : "SendRequestAsync triggers no event (async off, today)",
				      Fmt("equeue %s, user events %s %s, template %d, request %d; send %s, wait on the equeue: %s; WaitAsync %s "
				          "event %d result %s",
				          Hex(made).c_str(), Hex(add7).c_str(), Hex(add8).c_str(), t, r, Hex(rc).c_str(), got.c_str(),
				          Hex(w).c_str(), result.event_type, Hex(result.result).c_str()));
			}

			// 16. ReadDataAsync on the failed request.
			g_step = "http2: ReadDataAsync's event";
			{
				char              buf[16] = {};
				TriggerArgs       args {eq, 8, {}, &tag8, nullptr};
				const int         rc     = read_async(r, buf, sizeof(buf), &args, nullptr);
				const std::string got    = Waited(eq, &count, &first);
				Http2AsyncResult  result {};
				const int         w      = wait_async(r, &result, nullptr, nullptr);
				const bool        event  = count == 1 && first.ident == 8 && first.filter == EQ::KERNEL_EVFILT_USER &&
				                   first.udata == &tag8;
				Check(rc == 0 && (s.async ? event : got == "none") && w == 0 && result.event_type == 1 &&
				          result.result == kHttp2Timeout,
				      s.async ? "ReadDataAsync on a failed request triggers the caller's user event (async on)"
				              : "ReadDataAsync triggers no event (async off, today)",
				      Fmt("read %s, wait on the equeue: %s; WaitAsync %s event %d result %s", Hex(rc).c_str(), got.c_str(),
				          Hex(w).c_str(), result.event_type, Hex(result.result).c_str()));
			}

			// 17. No option, and an unknown request.
			g_step = "http2: no option and an unknown request";
			{
				char              buf[16] = {};
				TriggerArgs       args {eq, 7, {}, &tag7, nullptr};
				const int         s1      = send_async(r, nullptr, 0, nullptr, nullptr);
				const int         r1      = read_async(r, buf, sizeof(buf), nullptr, nullptr);
				const int         s2      = send_async(r + 1000, nullptr, 0, &args, nullptr);
				const int         r2      = read_async(r + 1000, buf, sizeof(buf), &args, nullptr);
				const std::string got     = Waited(eq, &count, &first);
				Check(s1 == 0 && r1 == 0 && s2 == kHttp2InvalidId && r2 == kHttp2InvalidId && got == "none",
				      "a null option and an unknown request trigger nothing (both)",
				      Fmt("send %s, read %s, unknown send %s, unknown read %s, wait on the equeue: %s", Hex(s1).c_str(),
				          Hex(r1).c_str(), Hex(s2).c_str(), Hex(r2).c_str(), got.c_str()));
			}
			(void)EQ::KernelDeleteEqueue(eq);
		}
	}

	// 18. sceHttpCreateTemplate and a NULL user agent.
	g_step = "http: CreateTemplate's user agent";
	{
		Loader::SymbolDatabase hdb;
		Libs::LibHttp::InitNet_1_Http(&hdb);
		const Loader::SymbolRecord* rec    = hdb.FindByNid("0gYjPTR-6cY", Loader::SymbolType::Func);
		const uint64_t              today  = reinterpret_cast<uint64_t>(&Libs::Network::Http::HttpCreateTemplate);
		const int                   pool   = Libs::Network::Net::NetPoolCreate("svc0405", 0x4000, 0);
		const int                   ssl    = Libs::Network::Ssl::SslInit(0x4000);
		const int                   ctx    = Libs::Network::Http::HttpInit(pool, ssl, 0x4000);
		const bool                  ready  = rec != nullptr && pool >= 0 && ssl >= 0 && ctx >= 0;
		const auto                  create = rec != nullptr ? reinterpret_cast<HttpTemplateFn>(rec->vaddr) : nullptr;
		const int                   named  = ready ? create(ctx, "svc0405", 2, 0) : -1;
		int                         null   = -1;
		if (s.agent && ready && rec->vaddr != today) {
			null = create(ctx, nullptr, 2, 0);
		}
		Check(ready && named > 0 && (s.agent ? (rec->vaddr != today && null > 0) : rec->vaddr == today),
		      s.agent ? "sceHttpCreateTemplate takes a NULL user agent (agent on)"
		              : "sceHttpCreateTemplate is today's function (agent off; its NULL user agent is not called)",
		      Fmt("record %s (%s), pool %d, ssl %d, http %d; named user agent %s, NULL user agent %s",
		          rec != nullptr ? "found" : "missing", rec != nullptr && rec->vaddr == today ? "today's function" : "a wrapper",
		          pool, ssl, ctx, Hex(named).c_str(), s.agent ? Hex(null).c_str() : "not called"));
	}
}

// ---- 19-21: scePadOpenExt ---------------------------------------------------------------------------------------------------

static void PadChecks(const Settings& s) {
	g_step = "pad: the registration";
	Loader::SymbolDatabase db;
	Libs::InitPad_1(&db); // turns libPad.cpp's PRINT_NAME on for this thread: the Log subsystem answers Silent
	const Loader::SymbolRecord* open    = db.FindByNid("xk0AcarP3V4", Loader::SymbolType::Func);
	const Loader::SymbolRecord* ext     = db.FindByNid("WFIiSfXGUq8", Loader::SymbolType::Func);
	const uint64_t              padopen = reinterpret_cast<uint64_t>(&Libs::Controller::PadOpen);
	const bool                  control = open != nullptr && open->vaddr == padopen;
	Check(control && (s.pad ? (ext != nullptr && ext->vaddr != padopen) : ext == nullptr),
	      s.pad ? "scePadOpenExt is registered (pad open ext on)" : "scePadOpenExt is not registered (pad open ext off, today)",
	      Fmt("scePadOpen %s, scePadOpenExt %s", control ? "at Controller::PadOpen" : "missing or elsewhere",
	          ext == nullptr ? "absent" : (ext->vaddr == padopen ? "at Controller::PadOpen" : "registered")));

	g_step = "pad: the opens";
	struct Case {
		int user, type, index, want;
	};
	std::string bad;
	int         n = 0;
	if (s.pad && ext != nullptr) {
		const auto f       = reinterpret_cast<PadOpenFn>(ext->vaddr);
		const Case cases[] = {{1000, 1, 0, 1}, {1000, 0, 0, 1}, {1000, 2, 0, 1}, {1001, 1, 0, 2}, {1003, 1, 0, 4},
		                      {255, 16, 0, 1}, {1000, 3, 0, kPadInvalidArg}, {255, 1, 0, kPadInvalidArg},
		                      {1000, 1, 1, kPadInvalidArg}, {999, 1, 0, kPadInvalidArg}, {1004, 1, 0, kPadInvalidArg}};
		for (const Case& c: cases) {
			const int got = f(c.user, c.type, c.index, nullptr);
			n++;
			if (got != c.want) {
				bad += Fmt(" (%d,%d,%d) %s want %s;", c.user, c.type, c.index, Hex(got).c_str(), Hex(c.want).c_str());
			}
		}
		Check(n == 11 && bad.empty(), "scePadOpenExt opens as scePadOpen, port type 1 too (pad open ext on)",
		      Fmt("%d cases:%s", n, bad.c_str()));
	} else {
		const Case cases[] = {{1000, 0, 0, 1}, {255, 16, 0, 1}};
		for (const Case& c: cases) {
			const int got = Libs::Controller::PadOpen(c.user, c.type, c.index, nullptr);
			n++;
			if (got != c.want) {
				bad += Fmt(" (%d,%d,%d) %s want %s;", c.user, c.type, c.index, Hex(got).c_str(), Hex(c.want).c_str());
			}
		}
		Check(!s.pad && n == 2 && bad.empty(), "scePadOpen opens the standard and remote ports (pad open ext off, today)",
		      Fmt("%d cases:%s%s", n, bad.c_str(), s.pad ? " (switch on but no record)" : ""));
	}

	g_step = "pad: scePadOpen unchanged";
	{
		const int t1 = Libs::Controller::PadOpen(1000, 1, 0, nullptr);
		const int t0 = Libs::Controller::PadOpen(1001, 0, 0, nullptr);
		Check(t1 == kPadInvalidArg && t0 == 2, "scePadOpen still refuses port type 1 and opens player 2's pad (both)",
		      Fmt("(1000,1,0) %s want %s, (1001,0,0) %s want 2", Hex(t1).c_str(), Hex(kPadInvalidArg).c_str(), Hex(t0).c_str()));
	}
}

} // namespace svc0405

int main(int argc, char* argv[]) {
	using namespace svc0405;
	if (argc != 2 || (std::strcmp(argv[1], "on") != 0 && std::strcmp(argv[1], "off") != 0)) {
		std::printf("usage: svc0405 on|off (on: at least one of the five switches on; off: none)\n");
		return 2;
	}
	const bool        on        = std::strcmp(argv[1], "on") == 0;
	const char* const names[5]  = {"KYTY_BC5_SAVEDATA_MEMORY_FIXES", "KYTY_BC5_SAVEDATA_DELETE_BUSY",
	                               "KYTY_BC5_SAVEDATA_ALIASES", "KYTY_BC5_HTTP2_FIXES", "KYTY_BC5_PAD_OPEN_EXT"};
	const char* const sdm[3]    = {"sync", "lock", "existed"};
	const char* const http[3]   = {"async", "ssl", "agent"};
	const uint32_t    memory    = Items(names[0], sdm, 3);
	const uint32_t    http2     = Items(names[3], http, 3);
	Settings          s;
	s.sync    = (memory & 1u) != 0;
	s.lock    = (memory & 2u) != 0;
	s.existed = (memory & 4u) != 0;
	s.del     = SwitchOn(names[1]);
	s.aliases = SwitchOn(names[2]);
	s.async   = (http2 & 1u) != 0;
	s.ssl     = (http2 & 2u) != 0;
	s.agent   = (http2 & 4u) != 0;
	s.pad     = SwitchOn(names[4]);
	const bool any = memory != 0 || s.del || s.aliases || http2 != 0 || s.pad;
	std::printf("svc0405: switches");
	for (const char* n: names) {
		const char* v = std::getenv(n);
		std::printf(" %s=%s", n, v != nullptr ? (v[0] != '\0' ? v : "(empty)") : "(unset)");
	}
	std::printf("; items: sync %d lock %d existed %d delete %d aliases %d async %d ssl %d agent %d openext %d\n", s.sync,
	            s.lock, s.existed, s.del, s.aliases, s.async, s.ssl, s.agent, s.pad);
	if (on != any) {
		std::printf("svc0405: the argument says %s but %s of the five switches is on\n", argv[1], any ? "one" : "none");
		return 2;
	}
	for (const char* e4: {"KYTY_BC5_SAVEDATA_FIXES", "KYTY_BC5_SAVEDATA_EVENT_CB", "KYTY_BC5_SAVEDATA_SORT"}) {
		if (SwitchOn(e4)) {
			std::printf("svc0405: %s is on; unset it (e4's sav0401 tests it; it changes the queue and Terminate)\n", e4);
			return 2;
		}
	}
	if (std::getenv("KYTY_BC5_SAVEDATA_DIR") != nullptr) {
		std::printf("svc0405: KYTY_BC5_SAVEDATA_DIR is set; unset it (this test sets it to its own fresh directory and "
		            "must never come near a real save)\n");
		return 2;
	}
	if (std::getenv("KYTY_BC5_SAVE_TRACE") != nullptr) {
		std::printf("svc0405: unset KYTY_BC5_SAVE_TRACE\n");
		return 2;
	}
	std::fflush(stdout);
	::Log::Bc5SetLogging(false); // LOGF stays silent from the first subsystem on
	std::thread(Watchdog).detach();

	// The fresh directory, checked before anything is written into it or through it.
	std::error_code             ec;
	const std::filesystem::path home = std::filesystem::canonical(std::filesystem::current_path(ec), ec);
	const std::filesystem::path work = home / ("svc0405-work-" + std::to_string(::getpid()));
	if (ec || home.empty() || std::filesystem::exists(std::filesystem::symlink_status(work, ec)) ||
	    !std::filesystem::create_directory(work, ec)) {
		std::printf("svc0405: cannot make a fresh %s\n", work.string().c_str());
		return 2;
	}
	const auto status = std::filesystem::symlink_status(work, ec);
	if (ec || !std::filesystem::is_directory(status) || std::filesystem::is_symlink(status) ||
	    std::filesystem::canonical(work, ec) != work || work.parent_path() != home) {
		std::printf("svc0405: %s is not a plain directory under %s\n", work.string().c_str(), home.string().c_str());
		return 2;
	}
	std::filesystem::current_path(work, ec);
	if (ec || std::filesystem::canonical(std::filesystem::current_path(ec), ec) != work) {
		std::printf("svc0405: cannot enter %s\n", work.string().c_str());
		return 2;
	}
	const std::filesystem::path saves = work / "_SaveData";
	if (::setenv("KYTY_BC5_SAVEDATA_DIR", saves.string().c_str(), 1) != 0) {
		std::printf("svc0405: cannot set KYTY_BC5_SAVEDATA_DIR\n");
		return 2;
	}
	g_memory_file = saves / "UNKNOWN" / "sce_sdmemory" / "memory.dat";
	std::printf("svc0405: work directory %s; memory file %s\n", work.string().c_str(), g_memory_file.string().c_str());
	std::fflush(stdout);

	// The subsystems, as emulator.cpp starts them: Common and Threads (the mount table's constructor checks for the main
	// thread), FileSystem (Mount3), Config (printf direction Silent) and Log (InitPad_1 turns PRINT_NAME on), Network.
	auto& slist   = *Common::SubsystemsList::Instance();
	auto* core    = Common::CommonSubsystem::Instance();
	auto* threads = Common::ThreadsSubsystem::Instance();
	auto* fs      = Libs::LibKernel::FileSystem::FileSystemSubsystem::Instance();
	auto* config  = Config::ConfigSubsystem::Instance();
	slist.SetArgs(argc, argv);
	slist.Add(core, {});
	slist.Add(threads, {core});
	slist.Add(fs, {core, threads});
	slist.Add(config, {core});
	if (!slist.InitAll(false)) {
		std::printf("svc0405: subsystem %s failed: %s\n", slist.GetFailName(), slist.GetFailMsg());
		return 1;
	}
	Config::ConfigOptions options;
	options.printf_direction = Config::OutputDirection::Silent;
	Config::Load(options);
	auto* log     = Log::LogSubsystem::Instance();
	auto* network = Libs::Network::NetworkSubsystem::Instance();
	slist.Add(log, {core, config});
	slist.Add(network, {core, log});
	if (!slist.InitAll(false)) {
		std::printf("svc0405: subsystem %s failed: %s\n", slist.GetFailName(), slist.GetFailMsg());
		return 1;
	}

	MemoryChecks(s);
	QueueChecks(s);
	DeleteChecks(s);
	AliasChecks(s);
	HttpChecks(s);
	PadChecks(s);

	g_step = "clean-up";
	std::filesystem::current_path(home, ec);
	std::filesystem::remove_all(work, ec); // only the directory this run made
	g_finished = true;

	if (g_checks != kChecks || g_passed != g_checks) {
		std::printf("svc0405: %s %d of %d passed, %d expected\n", argv[1], g_passed, g_checks, kChecks);
		std::fflush(stdout);
		std::_Exit(1);
	}
	std::printf("svc0405: %s %d of %d; end\n", argv[1], g_passed, g_checks);
	std::fflush(stdout);
	std::_Exit(0); // no static destructors
}
