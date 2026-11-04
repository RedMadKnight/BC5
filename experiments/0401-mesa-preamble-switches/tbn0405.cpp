// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0405 (series e6 of experiment 0401), tag tbn: the CPU test of mktbn0405.py's ports in src/libs/libNp.cpp
// (the NpCommon, NpManager and NpTrophy tables, exp 0405 decision 4), behind KYTY_BC5_LOAD_NPCOMMON, KYTY_BC5_LOAD_NPMANAGER
// and KYTY_BC5_LOAD_NPTROPHY. It starts the subsystems a guest thread needs (as lib0405.cpp / sav0401.cpp do) plus the file
// system, makes the main thread a guest thread, registers the three tables into its own SymbolDatabase by calling their
// LIB_DEFINEs (as libs.cpp does when a switch is on; with a switch off the init still runs here, to call today's stubs),
// takes each function by NID and calls it as a title would.
//   on:  the ported answers (AnyPS5 4f41f4c37 / shadPS4 60c42b9, see tbn0405-notes.md), the outputs written, real mutexes,
//        conditions, a guest thread and a callout context; trophy packages built here under ./tbn0405-app0 mounted at
//        /app0; the two NpManager NIDs the live table shares are not registered by InitNpManager_1, and loaded before the
//        live table (InitNet_1_NpManager) they resolve to the live functions by FindByNid and by Find.
//   off: today's answers (0, or 0x80550005 where today's stub says "not signed in") with every output left as it was, and
//        InitNpManager_1 registering all 27 NIDs as today.
// The three switches must agree (all on, or all off/unset); the mode is checked against an optional argument "on"/"off".
// No game, GPU, window, sound device or network. Prints one line per case and finally "tbn0405: on|off N of N; end";
// exit 0 only then. A watchdog ends a hang after 150 s with a FAIL line. Run it in a fresh directory: it writes
// ./tbn0405-app0 and removes it at the end.
// Build: build0401.py ... src/libs/libNp.cpp=<out>/src/libs/libNp.cpp --gate tbn0405.cpp <bin> --like src/libs/libNp.cpp

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
#include "libs/libs.h"
#include "libs/network.h"
#include "loader/runtimeLinker.h"
#include "loader/symbolDatabase.h"
#include "loader/timer.h"

#include <atomic>
#include <chrono>
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <string>
#include <thread>
#include <utility>
#include <vector>

#include <unistd.h>

namespace Libs {
namespace NpCommon {
LIB_DEFINE(InitNpCommon_1);
} // namespace NpCommon
namespace NpManager {
LIB_DEFINE(InitNpManager_1);
} // namespace NpManager
namespace NpTrophy {
LIB_DEFINE(InitNpTrophy_1);
} // namespace NpTrophy
namespace LibNpManager {
LIB_DEFINE(InitNet_1_NpManager); // the live NpManager table, libNet.cpp
} // namespace LibNpManager
} // namespace Libs

namespace tbn0405 {

template <typename... A>
using IFn = int (KYTY_SYSV_ABI*)(A...);

constexpr int kWatchdogSeconds = 150;

std::atomic<int>         g_cases {0};
std::atomic<int>         g_passed {0};
std::atomic<const char*> g_case {"start"};
bool                     g_on = false;

std::string Fmt(const char* format, ...) __attribute__((format(printf, 1, 2)));
std::string Fmt(const char* format, ...) {
	char    buf[1024];
	va_list args;
	va_start(args, format);
	std::vsnprintf(buf, sizeof(buf), format, args);
	va_end(args);
	return buf;
}

void Report(const std::string& name, bool ok, const std::string& info) {
	g_cases++;
	if (ok) {
		g_passed++;
	}
	std::printf("tbn0405: case %d %s: %s (%s)\n", g_cases.load(), name.c_str(), ok ? "ok" : "FAIL", info.c_str());
	std::fflush(stdout);
}

// A case that compares a return value and, optionally, more conditions.
void Rc(const std::string& name, int got, int want, bool more = true, const std::string& info = "") {
	Report(name, got == want && more, Fmt("0x%08x, want 0x%08x%s%s", static_cast<unsigned>(got), static_cast<unsigned>(want),
	                                      info.empty() ? "" : "; ", info.c_str()));
}

[[noreturn]] void SetupFail(const std::string& what) {
	std::printf("tbn0405: FAIL setup: %s\n", what.c_str());
	std::fflush(stdout);
	std::_Exit(2);
}

void Watchdog() {
	std::this_thread::sleep_for(std::chrono::seconds(kWatchdogSeconds));
	std::printf("tbn0405: FAIL watchdog: case \"%s\" still running after %d s (a hang); %d of %d cases passed before it\n",
	            g_case.load(), kWatchdogSeconds, g_passed.load(), g_cases.load());
	std::fflush(stdout);
	std::_Exit(3);
}

bool SwitchOn(const char* name) {
	const char* e = std::getenv(name);
	return e != nullptr && e[0] != '\0' && std::strcmp(e, "0") != 0;
}

// ---- lookups ----------------------------------------------------------------------------------------------------------
Loader::SymbolDatabase* g_db = nullptr;

template <typename F>
F Fn(const char* nid) {
	const auto* r = g_db->FindByNid(nid, Loader::SymbolType::Func);
	if (r == nullptr || r->vaddr == 0) {
		SetupFail(Fmt("%s is not registered", nid));
	}
	return reinterpret_cast<F>(r->vaddr);
}

Loader::SymbolResolve NpManagerKey(const char* nid) { // the key a title's import of libSceNpManager looks up
	Loader::SymbolResolve r {};
	r.name                 = nid;
	r.library              = "libSceNpManager";
	r.library_version      = 1;
	r.module               = "libSceNpManager";
	r.module_version_major = 1;
	r.module_version_minor = 1;
	r.type                 = Loader::SymbolType::Func;
	return r;
}

// ---- guest structures -------------------------------------------------------------------------------------------------
struct OnlineId {
	char data[16];
	char term;
	char dummy[3];
};
struct NpId {
	OnlineId handle;
	uint8_t  opt[8];
	uint8_t  reserved[8];
};
static_assert(sizeof(NpId) == 36);

OnlineId MakeOnlineId(const char* s) {
	OnlineId id {};
	std::strncpy(id.data, s, sizeof(id.data));
	return id;
}

NpId MakeNpId(const char* s, uint32_t tag = 0) {
	NpId id {};
	id.handle = MakeOnlineId(s);
	std::memcpy(id.opt + 4, &tag, sizeof(tag));
	return id;
}

uint32_t Get32(const void* p, size_t off) {
	uint32_t v = 0;
	std::memcpy(&v, static_cast<const uint8_t*>(p) + off, sizeof(v));
	return v;
}

// =====================================================================================================================
// NpCommon
// =====================================================================================================================
std::atomic<int> g_thread_ran {0};
std::atomic<int> g_callouts {0};

KYTY_SYSV_ABI void* ThreadEntry(void* arg) {
	static_cast<std::atomic<int>*>(arg)->store(1);
	return reinterpret_cast<void*>(static_cast<uintptr_t>(42));
}

KYTY_SYSV_ABI void CalloutHandler(void* arg) {
	static_cast<std::atomic<int>*>(arg)->fetch_add(1);
}

void CaseNpCommon() {
	g_case = "npcommon";
	using Ctx                  = uint8_t[0x28];
	const auto cmp_online      = Fn<IFn<const OnlineId*, const OnlineId*>>("dj+O5aD2a0Q");
	const auto cmp_npid        = Fn<IFn<const NpId*, const NpId*>>("i8UmXTSq7N4");
	const auto cmp_order       = Fn<IFn<const NpId*, const NpId*, int32_t*>>("TcwEFnakiSc");
	const auto platform        = Fn<IFn<const NpId*>>("sXVQUIGmk2U");
	const auto valid_online    = Fn<IFn<const OnlineId*>>("hkeX9iuCwlI");
	const auto clock_usec      = Fn<IFn<int64_t*>>("PVVsRmMkO1g");
	const auto sdk_version     = Fn<IFn<char*>>("Pglk7zFj0DI");
	const auto mutex_init      = Fn<IFn<void**, const char*, uint64_t>>("uEwag-0YZPc");
	const auto mutex_lock      = Fn<IFn<void**>>("r9Bet+s6fKc");
	const auto mutex_trylock   = Fn<IFn<void**>>("DuslmoqQ+nk");
	const auto mutex_unlock    = Fn<IFn<void**>>("oZyb9ktuCpA");
	const auto mutex_destroy   = Fn<IFn<void**>>("lQ11BpMM4LU");
	const auto lw_init         = Fn<IFn<void**, const char*, uint64_t>>("1CiXI-MyEKs");
	const auto lw_lock         = Fn<IFn<void**>>("18j+qk6dRwk");
	const auto lw_trylock      = Fn<IFn<void**>>("hp0kVgu5Fxw");
	const auto lw_unlock       = Fn<IFn<void**>>("CQG2oyx1-nM");
	const auto lw_destroy      = Fn<IFn<void**>>("4zxevggtYrQ");
	const auto cond_init       = Fn<IFn<void**, const char*, uint64_t>>("q2tsVO3lM4A");
	const auto cond_timedwait  = Fn<IFn<void**, void**, uint32_t>>("ss2xO9IJxKQ");
	const auto cond_signal     = Fn<IFn<void**>>("uMJFOA62mVU");
	const auto cond_destroy    = Fn<IFn<void**>>("1a+iY5YUJcI");
	const auto create_thread   = Fn<IFn<void**, KYTY_SYSV_ABI void* (*)(void*), void*, int, uint64_t, uint64_t, const char*>>(
        "fhJ5uKzcn0w");
	const auto join_thread     = Fn<IFn<void*, void**>>("EjMsfO3GCIA");
	const auto callout_init    = Fn<IFn<void*, const char*, uint64_t, int, uint64_t>>("9+m5nRdJ-wQ");
	const auto callout_term    = Fn<IFn<void*>>("AqJ4xkWsV+I");
	const auto callout_start   = Fn<IFn<void*, void*, uint32_t, KYTY_SYSV_ABI void (*)(void*), void*>>("fClnlkZmA6k");
	const auto callout_start64 = Fn<IFn<void*, void*, int64_t, KYTY_SYSV_ABI void (*)(void*), void*>>("lpr66Gby8dQ");
	const auto callout_stop    = Fn<IFn<void*, void*, int32_t*>>("in19gH7G040");

	constexpr int kInvalid  = static_cast<int>(0x80550003u);
	constexpr int kNotMatch = static_cast<int>(0x80550609u);
	const auto    a         = MakeOnlineId("alpha");
	const auto    a2        = MakeOnlineId("alpha");
	const auto    b         = MakeOnlineId("bravo");
	const auto    na        = MakeNpId("alpha");
	const auto    nb        = MakeNpId("bravo");
	auto          na_opt    = MakeNpId("alpha");
	na_opt.opt[0]           = 1;

	if (!g_on) {
		// Today: every stub answers 0 and writes nothing.
		Rc("npcommon off: CmpOnlineId of two different ids", cmp_online(&a, &b), 0);
		Rc("npcommon off: CmpNpId of two different NpIds", cmp_npid(&na, &nb), 0);
		int32_t order = 77;
		Rc("npcommon off: CmpNpIdInOrder writes nothing", cmp_order(&na, &nb, &order), 0, order == 77);
		Rc("npcommon off: GetPlatformType(null)", platform(nullptr), 0);
		Rc("npcommon off: IntIsValidOnlineId(\"alpha\")", valid_online(&a), 0);
		int64_t usec = -7;
		Rc("npcommon off: GetSystemClockUsec writes nothing", clock_usec(&usec), 0, usec == -7);
		char ver[8];
		std::memset(ver, 0x7F, sizeof(ver));
		Rc("npcommon off: GetSdkVersion writes nothing", sdk_version(ver), 0, ver[0] == 0x7F && ver[7] == 0x7F);
		void* m = nullptr;
		Rc("npcommon off: MutexInit creates nothing", mutex_init(&m, "tbn", 0), 0, m == nullptr);
		Rc("npcommon off: MutexTryLock", mutex_trylock(&m), 0);
		void* t = nullptr;
		Rc("npcommon off: CreateThread starts nothing", create_thread(&t, ThreadEntry, &g_thread_ran, 0, 0x10000, 0, "tbn"), 0,
		   t == nullptr && g_thread_ran.load() == 0);
		alignas(8) Ctx ctx {};
		Rc("npcommon off: CalloutInitCtx writes nothing", callout_init(ctx, "tbn", 0x10000, 0, 0), 0, Get32(ctx, 0x18) == 0);
		alignas(8) uint8_t e[0x20] {};
		Rc("npcommon off: CalloutStartOnCtx", callout_start(ctx, e, 1, CalloutHandler, &g_callouts), 0, g_callouts.load() == 0);
		return;
	}

	Rc("npcommon: CmpOnlineId equal", cmp_online(&a, &a2), 0);
	Rc("npcommon: CmpOnlineId different", cmp_online(&a, &b), kNotMatch);
	Rc("npcommon: CmpOnlineId(null)", cmp_online(nullptr, &b), kInvalid);
	Rc("npcommon: CmpNpId equal", cmp_npid(&na, &na), 0);
	Rc("npcommon: CmpNpId option byte differs", cmp_npid(&na, &na_opt), kNotMatch);
	Rc("npcommon: CmpNpId(null)", cmp_npid(&na, nullptr), kInvalid);
	int32_t order = 77;
	Rc("npcommon: CmpNpIdInOrder alpha < bravo", cmp_order(&na, &nb, &order), 0, order == -1, Fmt("order %d", order));
	Rc("npcommon: CmpNpIdInOrder bravo > alpha", cmp_order(&nb, &na, &order), 0, order == 1, Fmt("order %d", order));
	Rc("npcommon: CmpNpIdInOrder equal", cmp_order(&na, &na, &order), 0, order == 0, Fmt("order %d", order));
	Rc("npcommon: CmpNpIdInOrder option byte", cmp_order(&na, &na_opt, &order), 0, order == -1, Fmt("order %d", order));
	Rc("npcommon: CmpNpIdInOrder(null order)", cmp_order(&na, &nb, nullptr), kInvalid);
	const auto p_none = MakeNpId("alpha", 0);
	const auto p_ps4  = MakeNpId("alpha", 0x00347370u);
	const auto p_ps3  = MakeNpId("alpha", 0x00337370u);
	const auto p_bad  = MakeNpId("alpha", 0x00000078u);
	Rc("npcommon: GetPlatformType none", platform(&p_none), 0);
	Rc("npcommon: GetPlatformType ps4", platform(&p_ps4), 3);
	Rc("npcommon: GetPlatformType ps3", platform(&p_ps3), 1);
	Rc("npcommon: GetPlatformType unknown tag", platform(&p_bad), static_cast<int>(0x80550004u));
	Rc("npcommon: GetPlatformType(null)", platform(nullptr), kInvalid);
	const auto v_ok    = MakeOnlineId("a-b_c9");
	const auto v_short = MakeOnlineId("ab");
	const auto v_lead  = MakeOnlineId("_abc");
	const auto v_char  = MakeOnlineId("abc.d");
	const auto v_16    = MakeOnlineId("abcdefghijklmnop");
	auto       v_term  = MakeOnlineId("abcdefghijklmnop");
	v_term.term        = 'q';
	Rc("npcommon: IntIsValidOnlineId a-b_c9", valid_online(&v_ok), 1);
	Rc("npcommon: IntIsValidOnlineId ab (short)", valid_online(&v_short), 0);
	Rc("npcommon: IntIsValidOnlineId _abc (lead)", valid_online(&v_lead), 0);
	Rc("npcommon: IntIsValidOnlineId abc.d", valid_online(&v_char), 0);
	Rc("npcommon: IntIsValidOnlineId 16 characters", valid_online(&v_16), 1);
	Rc("npcommon: IntIsValidOnlineId no terminator", valid_online(&v_term), 0);
	Rc("npcommon: IntIsValidOnlineId(null)", valid_online(nullptr), 0);

	int64_t u1 = -7;
	int64_t u2 = -7;
	Rc("npcommon: GetSystemClockUsec(null)", clock_usec(nullptr), kInvalid);
	const int r1 = clock_usec(&u1);
	std::this_thread::sleep_for(std::chrono::milliseconds(20));
	const int r2 = clock_usec(&u2);
	Rc("npcommon: GetSystemClockUsec moves forward", r1 | r2, 0, u1 > 0 && u2 - u1 >= 15000 && u2 - u1 < 5000000,
	   Fmt("%lld then %lld", static_cast<long long>(u1), static_cast<long long>(u2)));
	char ver[8];
	std::memset(ver, 0x7F, sizeof(ver));
	Rc("npcommon: GetSdkVersion", sdk_version(ver), 0,
	   std::memcmp(ver, "10.60\0\0\0", 8) == 0, Fmt("\"%.7s\"", ver));
	Rc("npcommon: GetSdkVersion(null)", sdk_version(nullptr), 0);

	void* m = nullptr;
	Rc("npcommon: MutexInit", mutex_init(&m, "tbn", 0), 0, m != nullptr);
	Rc("npcommon: MutexLock", mutex_lock(&m), 0);
	Rc("npcommon: MutexTryLock of a held mutex", mutex_trylock(&m), static_cast<int>(0x8055800Fu));
	Rc("npcommon: MutexUnlock", mutex_unlock(&m), 0);
	Rc("npcommon: MutexTryLock of a free mutex", mutex_trylock(&m), 0);
	Rc("npcommon: MutexUnlock again", mutex_unlock(&m), 0);
	Rc("npcommon: MutexDestroy", mutex_destroy(&m), 0);
	void* rm = nullptr;
	Rc("npcommon: LwMutexInit recursive", lw_init(&rm, "tbn-r", 1), 0, rm != nullptr);
	Rc("npcommon: LwMutexLock", lw_lock(&rm), 0);
	Rc("npcommon: LwMutexTryLock again (recursive)", lw_trylock(&rm), 0);
	Rc("npcommon: LwMutexUnlock x2", lw_unlock(&rm) | lw_unlock(&rm), 0);
	Rc("npcommon: LwMutexDestroy", lw_destroy(&rm), 0);

	void* cm = nullptr;
	void* c  = nullptr;
	Rc("npcommon: CondInit", mutex_init(&cm, "tbn-c", 0) | cond_init(&c, "tbn-c", 0), 0, c != nullptr);
	mutex_lock(&cm);
	const auto w0 = std::chrono::steady_clock::now();
	const int  rw = cond_timedwait(&c, &cm, 20000);
	const auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now() - w0).count();
	mutex_unlock(&cm);
	Rc("npcommon: CondTimedwait 20 ms times out", rw, static_cast<int>(0x8055800Bu), ms >= 10 && ms < 5000,
	   Fmt("%lld ms", static_cast<long long>(ms)));
	Rc("npcommon: CondSignal", cond_signal(&c), 0);
	Rc("npcommon: CondDestroy", cond_destroy(&c) | mutex_destroy(&cm), 0);

	void* t = nullptr;
	Rc("npcommon: CreateThread", create_thread(&t, ThreadEntry, &g_thread_ran, 0, 0x10000, 0, "tbn-thread"), 0, t != nullptr);
	void* ret = nullptr;
	Rc("npcommon: JoinThread", t != nullptr ? join_thread(t, &ret) : -1, 0,
	   g_thread_ran.load() == 1 && reinterpret_cast<uintptr_t>(ret) == 42, Fmt("ran %d, value %p", g_thread_ran.load(), ret));

	alignas(8) Ctx ctx {};
	alignas(8) uint8_t e1[0x20] {};
	alignas(8) uint8_t e2[0x20] {};
	Rc("npcommon: CalloutStartOnCtx before init", callout_start(ctx, e1, 1000, CalloutHandler, &g_callouts),
	   static_cast<int>(0x80558001u));
	Rc("npcommon: CalloutInitCtx", callout_init(ctx, "tbn-callout", 0x10000, 0, 0), 0, Get32(ctx, 0x18) == 1);
	Rc("npcommon: CalloutInitCtx again", callout_init(ctx, "tbn-callout", 0x10000, 0, 0), static_cast<int>(0x80558002u));
	Rc("npcommon: CalloutStartOnCtx64 10 s", callout_start64(ctx, e2, 10000000, CalloutHandler, &g_callouts), 0);
	Rc("npcommon: CalloutStartOnCtx 10 ms", callout_start(ctx, e1, 10000, CalloutHandler, &g_callouts), 0);
	Rc("npcommon: CalloutStartOnCtx64 of a queued callout", callout_start64(ctx, e2, 1, CalloutHandler, &g_callouts),
	   static_cast<int>(0x80558006u));
	const auto c0 = std::chrono::steady_clock::now();
	while (g_callouts.load() == 0 && std::chrono::steady_clock::now() - c0 < std::chrono::seconds(3)) {
		std::this_thread::sleep_for(std::chrono::milliseconds(2));
	}
	std::this_thread::sleep_for(std::chrono::milliseconds(50));
	Report("npcommon: the 10 ms callout ran once, the 10 s one not", g_callouts.load() == 1, Fmt("%d calls", g_callouts.load()));
	int32_t removed = 7;
	Rc("npcommon: CalloutStopOnCtx of the queued one", callout_stop(ctx, e2, &removed), 0, removed == 1, Fmt("removed %d", removed));
	Rc("npcommon: CalloutStopOnCtx again", callout_stop(ctx, e2, &removed), 0, removed == 0, Fmt("removed %d", removed));
	Rc("npcommon: CalloutTermCtx", callout_term(ctx), 0, Get32(ctx, 0x18) == 0);
	Rc("npcommon: CalloutStopOnCtx after term", callout_stop(ctx, e2, &removed), static_cast<int>(0x80558001u));
	Rc("npcommon: CalloutInitCtx(null)", callout_init(nullptr, "x", 0x10000, 0, 0), kInvalid);
}

// =====================================================================================================================
// NpManager
// =====================================================================================================================
void CaseNpManager() {
	g_case = "npmanager";
	const auto avail_a       = Fn<IFn<int, int>>("8Z2Jc5GvGDI");
	const auto check_plus    = Fn<IFn<int, const void*, void*>>("r6MyYJkryz8");
	const auto lang          = Fn<IFn<int, const void*, void*>>("KZ1Mj9yEGYc");
	const auto lang_a        = Fn<IFn<int, int, void*>>("TPMbgIxvog0");
	const auto parental      = Fn<IFn<int, const void*, int8_t*, void*>>("ilwLM4zOmu4");
	const auto parental_a    = Fn<IFn<int, int, int8_t*, void*>>("m9L3O6yst-U");
	const auto set_timeout   = Fn<IFn<int, int32_t, uint32_t, uint32_t, uint32_t, uint32_t>>("-QglDeRr8D8");
	const auto wait_async    = Fn<IFn<int, int*>>("jyi5p9XWUSs");
	const auto country       = Fn<IFn<const void*, void*>>("Ghz9iWDUtC4");
	const auto birth         = Fn<IFn<const void*, void*>>("8VBTeRf1ZwI");
	const auto birth_a       = Fn<IFn<int, void*>>("q3M7XzBKC3s");
	const auto presence      = Fn<IFn<const void*, uint32_t*>>("IPb1hd1wAGc");
	const auto presence_a    = Fn<IFn<int, uint32_t*>>("oPO9U42YpgI");
	const auto set_online    = Fn<IFn<int, const void*, uint32_t>>("KO+11cgC7N0");
	const auto set_online_a  = Fn<IFn<int, int, uint32_t>>("C0gNCiRIi4U");
	const auto plus_member   = Fn<IFn<int, bool*>>("Ybu6AxV6S0o");
	const auto unreg_plus    = Fn<IFn<>>("xViqJdDgKl0");
	const auto account_id    = Fn<IFn<const void*, uint64_t*>>("a8R9-75u4iM");
	const auto user_by_acc   = Fn<IFn<uint64_t, int*>>("VgYczPGB5ss");
	const auto user_by_oid   = Fn<IFn<const void*, int*>>("F6E4ycq9Dbg");
	const auto callback_lib  = Fn<IFn<>>("JELHf4xPufo");
	const auto reg_pres_a    = Fn<IFn<>>("KswxLxk4c1Y");
	const auto reg_toolkit   = Fn<IFn<>>("0c7HbXRKUt4");

	constexpr int kInvalid    = static_cast<int>(0x80550003u);
	constexpr int kSignedOut  = static_cast<int>(0x80550006u);
	constexpr int kNoUser     = static_cast<int>(0x80550007u);
	constexpr int kNoRequest  = static_cast<int>(0x80550014u);
	constexpr int kTodayNotIn = static_cast<int>(0x80550005u);
	const auto    oid         = MakeOnlineId("alpha");
	uint8_t       buf[16];
	std::memset(buf, 0x5A, sizeof(buf));
	auto untouched = [&] {
		for (const uint8_t v: buf) {
			if (v != 0x5A) {
				return false;
			}
		}
		return true;
	};
	const auto* shared1 = g_db->FindByNid("mjjTXh+NHWY", Loader::SymbolType::Func);
	const auto* shared2 = g_db->FindByNid("cRILAEvn+9M", Loader::SymbolType::Func);

	if (!g_on) {
		Report("npmanager off: InitNpManager_1 registers the two shared NIDs as today",
		       shared1 != nullptr && shared2 != nullptr && shared1->dbg_name == "NpManager::sceNpUnregisterStateCallback" &&
		           shared2->dbg_name == "NpManager::sceNpUnregisterNpReachabilityStateCallback",
		       Fmt("%s, %s", shared1 != nullptr ? shared1->dbg_name.c_str() : "none",
		           shared2 != nullptr ? shared2->dbg_name.c_str() : "none"));
		Rc("npmanager off: CheckNpAvailabilityA", avail_a(1, -1), 0);
		Rc("npmanager off: CheckPlus", check_plus(0, nullptr, nullptr), 0);
		Rc("npmanager off: GetAccountLanguage", lang(1, &oid, buf), 0, untouched());
		Rc("npmanager off: GetAccountLanguageA", lang_a(1, 1, buf), 0, untouched());
		int8_t age = 9;
		Rc("npmanager off: GetParentalControlInfoA", parental_a(1, 1, &age, buf), 0, age == 9 && untouched());
		int r = 5;
		Rc("npmanager off: WaitAsync", wait_async(999, &r), 0, r == 5);
		Rc("npmanager off: SetTimeout", set_timeout(0, 0, 0, 0, 0, 0), 0);
		uint32_t st = 7;
		Rc("npmanager off: GetGamePresenceStatus", presence(&oid, &st), 0, st == 7);
		Rc("npmanager off: SetGamePresenceOnline", set_online(0, nullptr, 1), kTodayNotIn);
		Rc("npmanager off: SetGamePresenceOnlineA", set_online_a(1, 1, 1), kTodayNotIn);
		bool member = true;
		Rc("npmanager off: IsPlusMember", plus_member(1, &member), kTodayNotIn, member);
		uint64_t acc = 3;
		Rc("npmanager off: GetAccountId", account_id(&oid, &acc), 0, acc == 3);
		Rc("npmanager off: CheckCallbackForLib", callback_lib(), 0);
		Rc("npmanager off: UnregisterPlusEventCallback", unreg_plus(), 0);
		return;
	}

	// The two NIDs the live table registers: not registered here; loaded before the live table they resolve to it.
	Report("npmanager: InitNpManager_1 leaves out the two shared NIDs", shared1 == nullptr && shared2 == nullptr,
	       Fmt("%s, %s", shared1 != nullptr ? shared1->dbg_name.c_str() : "none", shared2 != nullptr ? shared2->dbg_name.c_str() : "none"));
	{
		Loader::SymbolDatabase db2;
		Libs::NpManager::InitNpManager_1(&db2);       // the switched table first, as libs.cpp loads it
		Libs::LibNpManager::InitNet_1_NpManager(&db2); // then the live table
		for (const auto& [nid, live]: {std::pair<const char*, const char*> {"mjjTXh+NHWY", "NpManager::NpUnregisterStateCallback"},
		                               {"cRILAEvn+9M", "NpManager::NpUnregisterNpReachabilityStateCallback"}}) {
			const auto* by_nid = db2.FindByNid(nid, Loader::SymbolType::Func);
			const auto* by_key = db2.Find(NpManagerKey(nid));
			Report(Fmt("npmanager: %s resolves to the live function", nid),
			       by_nid != nullptr && by_key != nullptr && by_nid->dbg_name == live && by_key->vaddr == by_nid->vaddr,
			       Fmt("%s: by NID %s, by key %s", nid, by_nid != nullptr ? by_nid->dbg_name.c_str() : "none",
			           by_key != nullptr ? by_key->dbg_name.c_str() : "none"));
		}
		const auto* plus = db2.FindByNid("GImICnh+boA", Loader::SymbolType::Func); // sceNpRegisterPlusEventCallback, live
		Report("npmanager: RegisterPlusEventCallback stays live", plus != nullptr && plus->dbg_name.find("NpRegisterPlusEventCallback") != std::string::npos,
		       plus != nullptr ? plus->dbg_name : "none");
	}

	const int req = Libs::Network::NpManager::NpCreateRequest(); // network.cpp's request model
	if (req <= 0) {
		SetupFail(Fmt("NpCreateRequest gave 0x%08x", static_cast<unsigned>(req)));
	}
	Rc("npmanager: CheckNpAvailabilityA invalid user", avail_a(req, -1), kInvalid);
	Rc("npmanager: CheckNpAvailabilityA unknown request", avail_a(999, 1), kNoRequest);
	Rc("npmanager: CheckNpAvailabilityA live request", avail_a(req, 1), kSignedOut);
	Rc("npmanager: CheckPlus request 0", check_plus(0, buf, buf), kInvalid);
	Rc("npmanager: CheckPlus", check_plus(req, buf, buf), kSignedOut, untouched());
	Rc("npmanager: GetAccountLanguage(null online id)", lang(req, nullptr, buf), kInvalid);
	Rc("npmanager: GetAccountLanguage", lang(req, &oid, buf), kNoUser, untouched());
	const int req2 = Libs::Network::NpManager::NpCreateRequest();
	Rc("npmanager: GetAccountLanguageA(null)", lang_a(req2, 1, nullptr), kInvalid);
	Rc("npmanager: GetAccountLanguageA", lang_a(req2, 1, buf), kSignedOut, untouched());
	int8_t age = 9;
	Rc("npmanager: GetParentalControlInfo", parental(req, &oid, &age, buf), kNoUser, age == 9 && untouched());
	Rc("npmanager: GetParentalControlInfo(null age)", parental(req, &oid, nullptr, buf), kInvalid);
	const int req3 = Libs::Network::NpManager::NpCreateRequest();
	Rc("npmanager: GetParentalControlInfoA invalid user", parental_a(req3, -1, &age, buf), kInvalid);
	Rc("npmanager: GetParentalControlInfoA", parental_a(req3, 1, &age, buf), kSignedOut, age == 9 && untouched());
	Rc("npmanager: SetTimeout all zero", set_timeout(req, 0, 0, 0, 0, 0), kInvalid);
	Rc("npmanager: SetTimeout resolve below 1 s", set_timeout(req, 1, 999999, 0, 0, 0), kInvalid);
	Rc("npmanager: SetTimeout request 0", set_timeout(0, 1, 0, 0, 0, 0), kInvalid);
	Rc("npmanager: SetTimeout unknown request", set_timeout(999, 1, 1000000, 10000000, 10000000, 10000000), kNoRequest);
	Rc("npmanager: SetTimeout", set_timeout(req, 1, 1000000, 10000000, 10000000, 10000000), 0);
	int r = 5;
	Rc("npmanager: WaitAsync(null)", wait_async(req, nullptr), kInvalid);
	Rc("npmanager: WaitAsync unknown request", wait_async(999, &r), kNoRequest, r == 5);
	Rc("npmanager: WaitAsync", wait_async(req, &r), 0, r == kSignedOut, Fmt("result 0x%08x", static_cast<unsigned>(r)));
	Rc("npmanager: GetAccountCountry", country(&oid, buf), kNoUser, untouched());
	Rc("npmanager: GetAccountCountry(null)", country(&oid, nullptr), kInvalid);
	Rc("npmanager: GetAccountDateOfBirth", birth(&oid, buf), kNoUser, untouched());
	Rc("npmanager: GetAccountDateOfBirthA", birth_a(1, buf), kSignedOut, untouched());
	Rc("npmanager: GetAccountDateOfBirthA invalid user", birth_a(-1, buf), kInvalid);
	uint32_t st = 7;
	Rc("npmanager: GetGamePresenceStatus", presence(&oid, &st), 0, st == 0);
	Rc("npmanager: GetGamePresenceStatus(null)", presence(nullptr, &st), kInvalid);
	st = 7;
	Rc("npmanager: GetGamePresenceStatusA", presence_a(1, &st), 0, st == 0);
	Rc("npmanager: GetGamePresenceStatusA invalid user", presence_a(-1, &st), kInvalid);
	Rc("npmanager: SetGamePresenceOnline request 0", set_online(0, &oid, 1), kInvalid);
	Rc("npmanager: SetGamePresenceOnline unknown request", set_online(999, &oid, 1), kNoRequest);
	Rc("npmanager: SetGamePresenceOnline", set_online(req, &oid, 1), kSignedOut);
	const int req4 = Libs::Network::NpManager::NpCreateRequest();
	Rc("npmanager: SetGamePresenceOnlineA invalid user", set_online_a(req4, -1, 1), kInvalid);
	Rc("npmanager: SetGamePresenceOnlineA", set_online_a(req4, 1, 1), kSignedOut);
	bool member = true;
	Rc("npmanager: IsPlusMember", plus_member(1, &member), 0, !member);
	Rc("npmanager: IsPlusMember(null)", plus_member(1, nullptr), kInvalid);
	uint64_t acc = 3;
	Rc("npmanager: GetAccountId", account_id(&oid, &acc), kSignedOut, acc == 3);
	Rc("npmanager: GetAccountId(null)", account_id(nullptr, &acc), kInvalid);
	int user = 4;
	Rc("npmanager: GetUserIdByAccountId", user_by_acc(5, &user), kSignedOut, user == 4);
	Rc("npmanager: GetUserIdByAccountId(0)", user_by_acc(0, &user), kInvalid);
	Rc("npmanager: GetUserIdByOnlineId", user_by_oid(&oid, &user), kSignedOut, user == 4);
	Rc("npmanager: GetUserIdByOnlineId(null)", user_by_oid(nullptr, &user), kInvalid);
	Rc("npmanager: CheckCallbackForLib", callback_lib(), 0);
	Rc("npmanager: UnregisterPlusEventCallback (already as AnyPS5)", unreg_plus(), 0);
	Rc("npmanager: RegisterGamePresenceCallbackA (held, today's 0)", reg_pres_a(), 0);
	Rc("npmanager: RegisterStateCallbackForToolkit (held, today's 0)", reg_toolkit(), 0);
	for (const int id: {req, req2, req3, req4}) {
		Libs::Network::NpManager::NpDeleteRequest(id);
	}
}

// =====================================================================================================================
// NpTrophy
// =====================================================================================================================
const char* kApp0 = "tbn0405-app0";

void MakeTrp(const std::filesystem::path& path, const std::vector<std::pair<std::string, std::string>>& files) {
	std::vector<uint8_t> out(0x60 + 0x40 * files.size(), 0);
	auto                 be32 = [&](size_t at, uint32_t v) {
        for (size_t i = 0; i < 4; i++) {
            out[at + i] = static_cast<uint8_t>(v >> (24 - 8 * i));
        }
	};
	be32(0, 0xdca24d00u);
	be32(0x10, static_cast<uint32_t>(files.size()));
	be32(0x14, 0x40);
	for (size_t i = 0; i < files.size(); i++) {
		const size_t at = 0x60 + 0x40 * i;
		std::memcpy(out.data() + at, files[i].first.c_str(), files[i].first.size());
		const uint64_t offset = out.size();
		be32(at + 32, static_cast<uint32_t>(offset >> 32));
		be32(at + 36, static_cast<uint32_t>(offset));
		be32(at + 40, 0);
		be32(at + 44, static_cast<uint32_t>(files[i].second.size()));
		out.insert(out.end(), files[i].second.begin(), files[i].second.end());
	}
	std::ofstream f(path, std::ios::binary | std::ios::trunc);
	f.write(reinterpret_cast<const char*>(out.data()), static_cast<std::streamsize>(out.size()));
	if (!f) {
		SetupFail("cannot write " + path.string());
	}
}

void MakeTrophyPackages() {
	const auto dir = std::filesystem::path(kApp0) / "sce_sys" / "trophy";
	std::filesystem::create_directories(dir);
	MakeTrp(dir / "trophy00.trp",
	        {{"ICON0.PNG", "ICON"}, {"TROP000.PNG", "T000"}, {"TROP001.PNG", "T001"}, {"TROP002.PNG", "T002"}});
	{
		std::ofstream f(dir / "trophy01.trp", std::ios::binary | std::ios::trunc); // not a trophy package
		const std::string zeros(0x80, '\0');
		f.write(zeros.data(), static_cast<std::streamsize>(zeros.size()));
	}
	MakeTrp(dir / "trophy03.trp", {{"ICON0.PNG", "ICON"}, {"TROP000.PNG", "T000"}, {"GR000.PNG", "G000"}});
	Libs::LibKernel::FileSystem::Mount(std::filesystem::absolute(kApp0), "/app0");
}

void CaseNpTrophy() {
	g_case = "nptrophy";
	const auto create_ctx   = Fn<IFn<int*, int, uint32_t, uint64_t>>("XbkjbobZlCY");
	const auto destroy_ctx  = Fn<IFn<int>>("E1Wrwd07Lr8");
	const auto create_h     = Fn<IFn<int*>>("q7U6tEAQf7c");
	const auto destroy_h    = Fn<IFn<int>>("GNcF4oidY0Y");
	const auto abort_h      = Fn<IFn<int>>("aTnHs7W-9Uk");
	const auto register_ctx = Fn<IFn<int, int, uint64_t>>("TJCAxto9SEU");
	const auto unlock_state = Fn<IFn<int, int, uint32_t*, uint32_t*>>("LHuSmO3SLd8");
	const auto unlock       = Fn<IFn<int, int, int, int*>>("28xmRUFao68");
	const auto game_icon    = Fn<IFn<int, int, void*, uint64_t*>>("HLwz1fRIycA");
	const auto group_icon   = Fn<IFn<int, int, int, void*, uint64_t*>>("w4uMPmErD4I");
	const auto trophy_icon  = Fn<IFn<int, int, int, void*, uint64_t*>>("eBL+l6HG9xk");
	const auto game_info    = Fn<IFn<int, int, void*, void*>>("YYP3f2W09og");
	const auto group_info   = Fn<IFn<int, int, int, void*, void*>>("wTUwGfspKic");
	const auto trophy_info  = Fn<IFn<int, int, int, void*, void*>>("qqUVGDgQBm0");
	const auto num_total    = Fn<IFn<const uint32_t*>>("hvdThnVvwdY");
	const auto group_num    = Fn<IFn<const uint32_t*>>("Ht6MNTl-je4");
	const auto set_num      = Fn<IFn<const uint8_t*>>("BSoSgiMVHnY");
	const auto set_flags    = Fn<IFn<const uint8_t*, uint8_t*>>("ITUmvpBPaG0");
	const auto has_group    = Fn<IFn<const uint8_t*>>("iqYfxC12sak");
	const auto show_list    = Fn<IFn<>>("d9jpdPz5f-8");
	const char* const dbg_nids[] = {"8aLlLHKP+No", "WdCUUJLQodM", "4QYFwC7tn4U", "nytN-3-pdvI", "JsRnDKRzvRw"};

	const uint32_t num_info[4]  = {1, 2, 3, 4};
	const uint32_t group_arr[4] = {0x0000F0F0u, 0xFFFFFFFFu, 0, 0};
	uint8_t        set_info[64] = {};
	for (size_t i = 0; i < 16; i++) {
		set_info[i]      = static_cast<uint8_t>(i == 0 ? 0x01 : 0);
		set_info[16 + i] = static_cast<uint8_t>(i == 0 ? 0x02 : 0);
		set_info[32 + i] = static_cast<uint8_t>(i == 1 ? 0x80 : 0);
		set_info[48 + i] = static_cast<uint8_t>(i == 0 ? 0x01 : 0);
	}
	uint8_t flags16[16];
	std::memset(flags16, 0x5A, sizeof(flags16));

	if (!g_on) {
		int ctx = -5;
		Rc("nptrophy off: CreateContext writes nothing", create_ctx(&ctx, 1000, 0, 0), 0, ctx == -5);
		int h = -5;
		Rc("nptrophy off: CreateHandle writes nothing", create_h(&h), 0, h == -5);
		Rc("nptrophy off: RegisterContext", register_ctx(1, 1, 0), static_cast<int>(0x80550005u));
		int plat = 9;
		Rc("nptrophy off: UnlockTrophy", unlock(1, 1, 0, &plat), static_cast<int>(0x80550005u), plat == 9);
		Rc("nptrophy off: NumInfoGetTotal", num_total(num_info), 0);
		Rc("nptrophy off: SetInfoGetTrophyFlagArray writes nothing", set_flags(set_info, flags16), 0, flags16[0] == 0x5A);
		Rc("nptrophy off: SystemDbgCtl", Fn<IFn<>>(dbg_nids[0])(), 0);
		return;
	}

	constexpr int kInvalid = static_cast<int>(0x80551604u);
	MakeTrophyPackages();
	int ctx = -5;
	Rc("nptrophy: CreateContext(null)", create_ctx(nullptr, 1000, 0, 0), kInvalid);
	Rc("nptrophy: CreateContext options 1", create_ctx(&ctx, 1000, 0, 1), kInvalid, ctx == -5);
	Rc("nptrophy: CreateContext", create_ctx(&ctx, 1000, 0, 0), 0, ctx > 0);
	int dup = -5;
	Rc("nptrophy: CreateContext same user and label", create_ctx(&dup, 1000, 0, 0), static_cast<int>(0x80551613u), dup == -5);
	int h = -5;
	Rc("nptrophy: CreateHandle(null)", create_h(nullptr), kInvalid);
	Rc("nptrophy: CreateHandle", create_h(&h), 0, h > 0);
	uint32_t flags[4] = {7, 7, 7, 7};
	uint32_t count    = 99;
	Rc("nptrophy: GetTrophyUnlockState before RegisterContext", unlock_state(ctx, h, flags, &count), static_cast<int>(0x8055160Fu));
	Rc("nptrophy: RegisterContext options 1", register_ctx(ctx, h, 1), kInvalid);
	Rc("nptrophy: RegisterContext context -1", register_ctx(-1, h, 0), static_cast<int>(0x80551609u));
	Rc("nptrophy: RegisterContext unknown handle", register_ctx(ctx, 999, 0), static_cast<int>(0x80551608u));
	Rc("nptrophy: RegisterContext", register_ctx(ctx, h, 0), 0);
	Rc("nptrophy: RegisterContext again", register_ctx(ctx, h, 0), static_cast<int>(0x80551610u));
	Rc("nptrophy: GetTrophyUnlockState", unlock_state(ctx, h, flags, &count), 0,
	   flags[0] == 0 && flags[1] == 0 && flags[2] == 0 && flags[3] == 0 && count == 3, Fmt("count %u", count));
	int plat = 9;
	Rc("nptrophy: UnlockTrophy(null)", unlock(ctx, h, 1, nullptr), kInvalid);
	Rc("nptrophy: UnlockTrophy 1", unlock(ctx, h, 1, &plat), 0, plat == -1);
	Rc("nptrophy: UnlockTrophy 1 again", unlock(ctx, h, 1, &plat), static_cast<int>(0x8055160Cu));
	Rc("nptrophy: UnlockTrophy 3 (past the icons)", unlock(ctx, h, 3, &plat), static_cast<int>(0x8055160Au));
	Rc("nptrophy: GetTrophyUnlockState after", unlock_state(ctx, h, flags, &count), 0, flags[0] == 2u && count == 3,
	   Fmt("bits 0x%x", flags[0]));
	uint64_t size = 0;
	Rc("nptrophy: GetGameIcon size", game_icon(ctx, h, nullptr, &size), 0, size == 4);
	char     icon[8] = {};
	uint64_t small   = 3;
	Rc("nptrophy: GetGameIcon small buffer", game_icon(ctx, h, icon, &small), static_cast<int>(0x80551605u));
	size = sizeof(icon);
	Rc("nptrophy: GetGameIcon", game_icon(ctx, h, icon, &size), 0, size == 4 && std::memcmp(icon, "ICON", 4) == 0);
	size = sizeof(icon);
	Rc("nptrophy: GetTrophyIcon of a locked trophy", trophy_icon(ctx, h, 0, icon, &size), static_cast<int>(0x8055161Au));
	Rc("nptrophy: GetTrophyIcon 1", trophy_icon(ctx, h, 1, icon, &size), 0, std::memcmp(icon, "T001", 4) == 0);
	Rc("nptrophy: GetTrophyIcon 5", trophy_icon(ctx, h, 5, icon, &size), static_cast<int>(0x8055160Au));
	Rc("nptrophy: GetGroupIcon -1", group_icon(ctx, h, -1, icon, &size), static_cast<int>(0x8055160Bu));
	Rc("nptrophy: GetGroupIcon 0 (no group)", group_icon(ctx, h, 0, icon, &size), static_cast<int>(0x80551614u));

	alignas(8) uint8_t gdetails[0x4a0];
	alignas(8) uint8_t gdata[0x28];
	std::memset(gdetails, 0x5A, sizeof(gdetails));
	std::memset(gdata, 0x5A, sizeof(gdata));
	uint64_t sz = 0x4a0;
	std::memcpy(gdetails, &sz, 8);
	sz = 0x20;
	std::memcpy(gdata, &sz, 8);
	Rc("nptrophy: GetGameInfo", game_info(ctx, h, gdetails, gdata), 0,
	   Get32(gdetails, 8) == 0 && Get32(gdetails, 0xC) == 3 && gdetails[0x20] == 0 && Get32(gdata, 8) == 1 && Get32(gdata, 0x1C) == 33,
	   Fmt("groups %u trophies %u unlocked %u progress %u", Get32(gdetails, 8), Get32(gdetails, 0xC), Get32(gdata, 8),
	       Get32(gdata, 0x1C)));
	Rc("nptrophy: GetGameInfo both null", game_info(ctx, h, nullptr, nullptr), kInvalid);
	sz = 0x28;
	std::memcpy(gdata, &sz, 8);
	Rc("nptrophy: GetGameInfo wrong data size", game_info(ctx, h, nullptr, gdata), kInvalid);
	Rc("nptrophy: GetGroupInfo base game", group_info(ctx, h, -1, nullptr, gdata), 0,
	   Get32(gdata, 8) == 0xFFFFFFFFu && Get32(gdata, 0xC) == 1 && Get32(gdata, 0x20) == 33);
	Rc("nptrophy: GetGroupInfo 5", group_info(ctx, h, 5, nullptr, gdata), static_cast<int>(0x8055160Bu));
	alignas(8) uint8_t tdata[0x18];
	std::memset(tdata, 0x5A, sizeof(tdata));
	sz = 0x18;
	std::memcpy(tdata, &sz, 8);
	Rc("nptrophy: GetTrophyInfo 1", trophy_info(ctx, h, 1, nullptr, tdata), 0, Get32(tdata, 8) == 1 && tdata[0xC] == 1);
	Rc("nptrophy: GetTrophyInfo 2", trophy_info(ctx, h, 2, nullptr, tdata), 0, Get32(tdata, 8) == 2 && tdata[0xC] == 0);

	int c1 = 0;
	int c2 = 0;
	int c3 = 0;
	create_ctx(&c1, 1000, 1, 0);
	create_ctx(&c2, 1000, 2, 0);
	create_ctx(&c3, 1000, 3, 0);
	Rc("nptrophy: RegisterContext not a trophy package", register_ctx(c1, h, 0), static_cast<int>(0x80551616u));
	Rc("nptrophy: RegisterContext no package", register_ctx(c2, h, 0), static_cast<int>(0x80551626u));
	Rc("nptrophy: RegisterContext with a group", register_ctx(c3, h, 0), 0);
	std::memset(gdata + 8, 0x5A, sizeof(gdata) - 8);
	Rc("nptrophy: GetGroupInfo of a group (no answer: 0, nothing written)", group_info(c3, h, 0, nullptr, gdata), 0,
	   gdata[8] == 0x5A);
	std::memset(tdata + 8, 0x5A, sizeof(tdata) - 8);
	Rc("nptrophy: GetTrophyInfo with groups (no answer: 0, nothing written)", trophy_info(c3, h, 0, nullptr, tdata), 0,
	   tdata[8] == 0x5A);

	Rc("nptrophy: AbortHandle", abort_h(h), 0);
	Rc("nptrophy: GetTrophyUnlockState through an aborted handle", unlock_state(ctx, h, flags, &count), static_cast<int>(0x80551607u));
	Rc("nptrophy: AbortHandle again", abort_h(h), 0);
	Rc("nptrophy: AbortHandle unknown", abort_h(999), static_cast<int>(0x80551608u));
	Rc("nptrophy: DestroyHandle", destroy_h(h), 0);
	Rc("nptrophy: DestroyHandle again", destroy_h(h), static_cast<int>(0x80551608u));
	Rc("nptrophy: DestroyContext", destroy_ctx(ctx) | destroy_ctx(c1) | destroy_ctx(c2) | destroy_ctx(c3), 0);
	Rc("nptrophy: DestroyContext again", destroy_ctx(ctx), static_cast<int>(0x80551609u));

	Rc("nptrophy: NumInfoGetTotal", num_total(num_info), 10);
	Rc("nptrophy: GroupArrayGetNum", group_num(group_arr), 8);
	Rc("nptrophy: SetInfoGetTrophyNum", set_num(set_info), 4);
	Rc("nptrophy: SetInfoGetTrophyFlagArray", set_flags(set_info, flags16), 3,
	   flags16[0] == 0x03 && flags16[1] == 0x80 && flags16[2] == 0 && flags16[15] == 0);
	for (const char* nid: dbg_nids) {
		Rc(Fmt("nptrophy: SystemDbg export %s", nid), Fn<IFn<>>(nid)(), static_cast<int>(0x80551692u));
	}
	Rc("nptrophy: ConfigHasGroupFeature (held, today's 0)", has_group(nullptr), 0);
	Rc("nptrophy: ShowTrophyList (unchanged)", show_list(), 0);
}

// ---- the subsystems a guest thread needs, as lib0405.cpp starts them, plus the file system ----------------------------
void Init(int argc, char** argv) {
	g_case        = "init: subsystems";
	auto& slist   = *Common::SubsystemsList::Instance();
	auto* core    = Common::CommonSubsystem::Instance();
	auto* threads = Common::ThreadsSubsystem::Instance();
	auto* config  = Config::ConfigSubsystem::Instance();
	slist.SetArgs(argc, argv);
	slist.Add(core, {});
	slist.Add(threads, {core});
	slist.Add(config, {core});
	if (!slist.InitAll(false)) {
		SetupFail(Fmt("subsystem %s: %s", slist.GetFailName(), slist.GetFailMsg()));
	}
	Config::ConfigOptions options;
	options.printf_direction = Config::OutputDirection::Silent;
	Config::Load(options);
	auto* log     = Log::LogSubsystem::Instance();
	auto* timer   = Loader::Timer::TimerSubsystem::Instance();
	auto* memory  = Libs::LibKernel::Memory::MemorySubsystem::Instance();
	auto* pthread = Libs::LibKernel::PthreadSubsystem::Instance();
	auto* fs      = Libs::LibKernel::FileSystem::FileSystemSubsystem::Instance();
	slist.Add(log, {core, config});
	slist.Add(timer, {core, log});
	slist.Add(memory, {core, log});
	slist.Add(pthread, {core, log, timer});
	slist.Add(fs, {core, log});
	if (!slist.InitAll(false)) {
		SetupFail(Fmt("subsystem %s: %s", slist.GetFailName(), slist.GetFailMsg()));
	}
	(void)Common::Singleton<Loader::RuntimeLinker>::Instance();
	Libs::LibKernel::PthreadInitSelfForMainThread(); // the main thread becomes a guest thread (as the runtime linker does)
}

} // namespace tbn0405

int main(int argc, char** argv) {
	using namespace tbn0405;
	const bool  npc  = SwitchOn("KYTY_BC5_LOAD_NPCOMMON");
	const bool  npm  = SwitchOn("KYTY_BC5_LOAD_NPMANAGER");
	const bool  npt  = SwitchOn("KYTY_BC5_LOAD_NPTROPHY");
	const char* mode = npc && npm && npt ? "on" : (!npc && !npm && !npt ? "off" : "mixed");
	if (std::strcmp(mode, "mixed") == 0 || argc > 2 || (argc == 2 && std::strcmp(argv[1], mode) != 0)) {
		std::printf("tbn0405: the switches must agree and match the argument: npcommon %d, npmanager %d, nptrophy %d (%s), argument "
		            "%s\n",
		            npc, npm, npt, mode, argc == 2 ? argv[1] : (argc > 2 ? "too many" : "none"));
		return 2;
	}
	g_on = npc;
	std::printf("tbn0405: switches npcommon %d, npmanager %d, nptrophy %d: %s\n", npc, npm, npt, mode);
	std::fflush(stdout);
	unsetenv("KYTY_BC5_APP0_OVERRIDE"); // /app0 is this test's mount only
	::Log::Bc5SetLogging(false);        // the units' LOGF lines stay off stdout
	std::thread(Watchdog).detach();

	char  arg0[] = "tbn0405";
	char* args[] = {arg0, nullptr};
	Init(1, args);

	g_case = "init: registration";
	static Loader::SymbolDatabase db;
	Libs::NpCommon::InitNpCommon_1(&db); // each prints its "[bc5] exp 0405: <table> port on|off" line on stderr
	Libs::NpManager::InitNpManager_1(&db);
	Libs::NpTrophy::InitNpTrophy_1(&db);
	g_db = &db;

	CaseNpCommon();
	CaseNpManager();
	CaseNpTrophy();

	std::error_code ec;
	std::filesystem::remove_all(kApp0, ec);
	const int n = g_cases.load();
	const int p = g_passed.load();
	if (p != n) {
		std::printf("tbn0405: %s %d of %d passed; FAIL\n", mode, p, n);
		std::fflush(stdout);
		std::_Exit(1);
	}
	std::printf("tbn0405: %s %d of %d; end\n", mode, p, n);
	std::fflush(stdout);
	std::_Exit(0); // no static destructors: the Pthread subsystem's helper thread may still run
}
