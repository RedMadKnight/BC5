// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0405 (series e7 of experiment 0401), tag "tbd": the CPU test of mktbd0405.py's edits of
// src/libs/libInvitationDialog.cpp, libWebBrowserDialog.cpp, libSharePlay.cpp and libGameLiveStreaming.cpp (notes
// tbd0405-notes.md): four of the tables that are compiled but never loaded, ported first (exp 0405 decision 4), each
// behind its own switch:
//   KYTY_BC5_LOAD_INVITATIONDIALOG, KYTY_BC5_LOAD_WEBBROWSERDIALOG, KYTY_BC5_LOAD_SHAREPLAY,
//   KYTY_BC5_LOAD_GAMELIVESTREAMING (no items). (Remoteplay has no switch: nothing to port.)
// No game, no GPU, no window, no sound device, no network, no USB. The test registers the four tables and then
// libNet.cpp's three live tables of the same libraries (Initialize/Terminate of WebBrowserDialog, SharePlay and
// GameLiveStreaming) into its own SymbolDatabase, takes every function by its exact key (NID, library, versions) as a
// title's import resolves it, and calls it as a title would. Each output starts as a sentinel and is checked as written
// or left as it was. Each table's cases follow its own switch; off, every case is today's answer, computed from today's
// code line by line.
// Cases (one line each; tbd0405-notes.md has the reasons):
//   every table: registration (the 9/12/22/45 NIDs by their exact keys when off; on, all but the held ones, the same
//     records as the table alone), the split (the live NIDs are not this table's and resolve, by Find and by FindByNid,
//     to the live functions), the held stubs (on: not registered, by Find or FindByNid; off: registered, 0 each).
//   invitationdialog on: the state machine (none/initialized/finished), ALREADY_INITIALIZED, NOT_INITIALIZED,
//     NOT_FINISHED, ARG_NULL, the result fields, the four kept answers (AnyPS5 has none).
//   webbrowserdialog on: the live Initialize (status stays 0: split state), Close (NOT_RUNNING), GetResult's checks and
//     answer, the cookie checks and the open mark, Open and OpenForPredeterminedContent's allow-list checks.
//   shareplay on: both connection infos (null, the fields written, the bytes after left alone).
//   gamelivestreaming on: Status2, ProgramInfo, the separate-mode parameter, the feedback queries, the four string
//     limits, spoiler tags, preset commands, the camera setting, the 7 calls that already match.
// Build (build0401.py, series e7): --gate tbd0405.cpp <out> --like src/libs/libGameLiveStreaming.cpp, with the four
// private units from mktbd0405.py in place of the shared ones, linked with every emulator object but main.cpp.o.
// usage: run in a fresh directory, with the four switches set alike: all =1 -> "tbd0405 on"; all =0, or all unset ->
// "tbd0405 off". With the switches not alike each table's cases follow its own switch and the last line says "mixed".
// The argument may be left out. Prints "tbd0405: on|off|mixed N of N; end" and exits 0 only then. A watchdog ends a hang
// after 60 s with a FAIL line.

#include "common/abi.h"
#include "libs/errno.h"
#include "libs/libs.h"
#include "loader/symbolDatabase.h"

#include <atomic>
#include <chrono>
#include <cstdarg>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <thread>
#include <vector>

namespace Libs::LibInvitationDialog {
LIB_DEFINE(InitInvitationDialog_1);
} // namespace Libs::LibInvitationDialog
namespace Libs::LibWebBrowserDialog {
LIB_DEFINE(InitWebBrowserDialog_1);
LIB_DEFINE(InitPlatform_1_WebBrowserDialog); // libNet.cpp, live
} // namespace Libs::LibWebBrowserDialog
namespace Libs::LibSharePlay {
LIB_DEFINE(InitSharePlay_1);
LIB_DEFINE(InitPlatform_1_SharePlay); // libNet.cpp, live
} // namespace Libs::LibSharePlay
namespace Libs::LibGameLiveStreaming {
LIB_DEFINE(InitGameLiveStreaming_1);
LIB_DEFINE(InitPlatform_1_GameLiveStreaming); // libNet.cpp, live
} // namespace Libs::LibGameLiveStreaming

namespace tbd0405 {

constexpr int      kWatchdogSeconds = 60;
constexpr uint8_t  kS8              = 0xA5; // a byte the call has not written
constexpr uint32_t kS32             = 0xA5A5A5A5u;
constexpr uint64_t kS64             = 0xA5A5A5A5A5A5A5A5ull;

std::atomic<int>         g_cases {0};
std::atomic<int>         g_passed {0};
std::atomic<const char*> g_case {"start"};

std::string Fmt(const char* format, ...) __attribute__((format(printf, 1, 2)));
std::string Fmt(const char* format, ...) {
	char    buf[1024];
	va_list args;
	va_start(args, format);
	std::vsnprintf(buf, sizeof(buf), format, args);
	va_end(args);
	return buf;
}

void Check(const char* name, bool ok, const std::string& info) {
	g_cases++;
	if (ok) {
		g_passed++;
	}
	std::printf("tbd0405: case %d %s: %s (%s)\n", g_cases.load(), name, ok ? "ok" : "FAIL", info.c_str());
	std::fflush(stdout);
}

void Check(const std::string& name, bool ok, const std::string& info) {
	Check(name.c_str(), ok, info);
}

[[noreturn]] void SetupFail(const std::string& what) {
	std::printf("tbd0405: FAIL setup: %s\n", what.c_str());
	std::fflush(stdout);
	std::_Exit(2);
}

void Watchdog() {
	std::this_thread::sleep_for(std::chrono::seconds(kWatchdogSeconds));
	std::printf("tbd0405: FAIL watchdog: case \"%s\" still running after %d s (a hang); %d of %d cases passed before it\n",
	            g_case.load(), kWatchdogSeconds, g_passed.load(), g_cases.load());
	std::fflush(stdout);
	std::_Exit(3);
}

// ---- the switches, read as the units read them ----------------------------------------------------------------------
bool EnvOn(const char* name) {
	const char* e = std::getenv(name);
	return e != nullptr && e[0] != '\0' && !(e[0] == '0' && e[1] == '\0');
}

bool g_inv = false;
bool g_wbd = false;
bool g_shp = false;
bool g_gls = false;

// ---- registration and lookup ----------------------------------------------------------------------------------------
Loader::SymbolDatabase g_all;  // the four tables, then libNet.cpp's three live tables (the order of Libs::InitAll with them on)
Loader::SymbolDatabase g_dead; // the four tables alone
Loader::SymbolDatabase g_live; // libNet.cpp's three alone

const Loader::SymbolRecord* Exact(const Loader::SymbolDatabase& db, const char* nid, const char* lib) {
	Loader::SymbolResolve sr {};
	sr.name                 = nid;
	sr.library              = lib;
	sr.library_version      = 1;
	sr.module               = lib;
	sr.module_version_major = 1;
	sr.module_version_minor = 1;
	sr.type                 = Loader::SymbolType::Func;
	return db.Find(sr);
}

uint64_t Addr(const Loader::SymbolDatabase& db, const char* nid, const char* lib) {
	const auto* r = Exact(db, nid, lib);
	return r != nullptr ? r->vaddr : 0;
}

template <typename F>
F Fn(const char* nid, const char* lib) {
	const uint64_t a = Addr(g_all, nid, lib);
	if (a == 0) {
		SetupFail(Fmt("%s (%s) is not registered", nid, lib));
	}
	return reinterpret_cast<F>(a);
}

std::string Hex(int r) {
	return Fmt("0x%08x", static_cast<uint32_t>(r));
}

bool AllBytes(const void* p, size_t n, uint8_t v) {
	const auto* b = static_cast<const uint8_t*>(p);
	for (size_t i = 0; i < n; i++) {
		if (b[i] != v) {
			return false;
		}
	}
	return true;
}

int32_t I32(const void* p, size_t at) {
	int32_t v = 0;
	std::memcpy(&v, static_cast<const uint8_t*>(p) + at, sizeof(v));
	return v;
}

using NoArg  = int(KYTY_SYSV_ABI*)();
using PtrArg = int(KYTY_SYSV_ABI*)(void*);
using CPtr   = int(KYTY_SYSV_ABI*)(const void*);
using CPtr2  = int(KYTY_SYSV_ABI*)(const void*, const void*);
using IntArg = int(KYTY_SYSV_ABI*)(int);
using Text   = int(KYTY_SYSV_ABI*)(const char*);
using Count  = int(KYTY_SYSV_ABI*)(int, uint32_t*);
using Msgs   = int(KYTY_SYSV_ABI*)(int, size_t, void*, size_t*);
using Entr   = int(KYTY_SYSV_ABI*)(size_t, const void*);

bool IsIn(const std::vector<const char*>& list, const char* nid) {
	for (const char* n: list) {
		if (std::strcmp(n, nid) == 0) {
			return true;
		}
	}
	return false;
}

// The table's NIDs by their exact keys in the full database, each the same record the table alone registers (on: all
// but the held ones, which the next case checks); the live NIDs of the same library (libNet.cpp) not in the table, the
// table's not in the live set, and both lookups of a live NID (Find, and the loader's NID-only fallback FindByNid) giving
// the live function.
void Registration(const char* word, const char* lib, bool on, const std::vector<const char*>& nids,
                  const std::vector<const char*>& held, const std::vector<const char*>& live) {
	int    same   = 0;
	size_t expect = 0;
	for (const char* n: nids) {
		if (on && IsIn(held, n)) {
			continue;
		}
		expect++;
		const uint64_t a = Addr(g_all, n, lib);
		same += (a != 0 && a == Addr(g_dead, n, lib)) ? 1 : 0;
	}
	Check(on ? Fmt("%s registration: %zu NIDs by their exact keys (all but the %zu held)", word, expect, held.size())
	         : Fmt("%s registration: all %zu NIDs by their exact keys", word, expect),
	      same == static_cast<int>(expect), Fmt("%d of %zu", same, expect));
	int apart = 0;
	for (const char* n: nids) {
		apart += g_live.FindByNid(n, Loader::SymbolType::Func) == nullptr ? 1 : 0;
	}
	int live_ok = 0;
	for (const char* n: live) {
		const uint64_t lv = Addr(g_live, n, lib);
		const auto*    fb = g_all.FindByNid(n, Loader::SymbolType::Func);
		live_ok += (lv != 0 && g_dead.FindByNid(n, Loader::SymbolType::Func) == nullptr && Addr(g_all, n, lib) == lv &&
		            fb != nullptr && fb->vaddr == lv)
		               ? 1
		               : 0;
	}
	Check(Fmt("%s split: the %zu live NIDs (libNet.cpp) are not this table's, Find and FindByNid give the live functions; "
	          "no NID of this table is live",
	          word, live.size()),
	      live_ok == static_cast<int>(live.size()) && apart == static_cast<int>(nids.size()),
	      Fmt("live %d of %zu, table NIDs not live %d of %zu", live_ok, live.size(), apart, nids.size()));
}

// The held stubs. On: not registered (neither Find nor the NID-only fallback FindByNid finds them, in this table or a live
// one), so a title's import of them stays unresolved, as today, and keeps exp 0327's journal line. Off: registered as
// today, each answering 0 (call=false: present only, when the table's own cases have called them).
void Held(const char* word, const char* lib, bool on, const std::vector<const char*>& held, bool call = true) {
	if (on) {
		int absent = 0;
		for (const char* n: held) {
			absent += (Exact(g_all, n, lib) == nullptr && g_all.FindByNid(n, Loader::SymbolType::Func) == nullptr) ? 1 : 0;
		}
		Check(Fmt("%s the %zu held stubs are not registered (Find and FindByNid find none)", word, held.size()),
		      absent == static_cast<int>(held.size()), Fmt("%d of %zu absent", absent, held.size()));
		return;
	}
	int         zero = 0;
	std::string wrong;
	for (const char* n: held) {
		if (Addr(g_all, n, lib) == 0) {
			wrong += Fmt(" %s=missing", n);
			continue;
		}
		const int v = call ? Fn<NoArg>(n, lib)() : 0;
		if (v == 0) {
			zero++;
		} else {
			wrong += Fmt(" %s=%s", n, Hex(v).c_str());
		}
	}
	Check(Fmt("%s the %zu held stubs are registered as today%s", word, held.size(), call ? ", 0 each" : ""),
	      zero == static_cast<int>(held.size()), Fmt("%d of %zu%s", zero, held.size(), wrong.c_str()));
}

// =====================================================================================================================
// InvitationDialog
// =====================================================================================================================
constexpr int kInvNotInit     = static_cast<int>(0x80B80003u);
constexpr int kInvAlready     = static_cast<int>(0x80B80004u);
constexpr int kInvNotFinished = static_cast<int>(0x80B80005u);
constexpr int kInvArgNull     = static_cast<int>(0x80B8000Du);

struct InvParam { // shadPS4's layout: the common base (48 bytes), size, mode, user, callback argument, data, reserved
	uint8_t     base[48];
	uint32_t    size;
	int32_t     mode;
	int32_t     user_id;
	uint32_t    padding;
	void*       callback_arg;
	const void* data;
	uint8_t     reserved[64];
};
struct InvResult {
	void*     callback_arg;
	int32_t   error_code;
	int32_t   result;
	uint32_t* recipients;
	uint8_t   reserved[32];
};
struct InvRecipients {
	uint32_t count;
	uint8_t  online_ids[16 * 20];
};
static_assert(sizeof(InvParam) == 144 && sizeof(InvResult) == 0x38 && sizeof(InvRecipients) == 324);

void CaseInvitationDialog() {
	g_case                = "invitationdialog";
	const char* lib       = "libSceInvitationDialog";
	const bool  on        = g_inv;
	const char* w         = on ? "invitationdialog" : "invitationdialog off:";
	const std::vector<const char*> nids = {"WWtCL5lzi7Y", "8XKR6wa64iQ", "WuuUhuKOxwQ", "EiF92YDNHRA", "XvA5KS56wcs",
	                                       "0zU0G+wiVLA", "sAxbHhAWMXM", "B6HVJtDYxEE", "9+g9iOq+7kg"};
	const std::vector<const char*> held = {"WuuUhuKOxwQ", "sAxbHhAWMXM"}; // GetResultA, OpenA
	Registration(w, lib, on, nids, held, {});

	auto close    = Fn<NoArg>("WWtCL5lzi7Y", lib);
	auto get      = Fn<PtrArg>("8XKR6wa64iQ", lib);
	auto status   = Fn<NoArg>("EiF92YDNHRA", lib);
	auto init     = Fn<NoArg>("XvA5KS56wcs", lib);
	auto open     = Fn<CPtr>("0zU0G+wiVLA", lib);
	auto term     = Fn<NoArg>("B6HVJtDYxEE", lib);
	auto update   = Fn<NoArg>("9+g9iOq+7kg", lib);
	void* const a = reinterpret_cast<void*>(uintptr_t {0x1234});
	void* const b = reinterpret_cast<void*>(uintptr_t {0x5678});

	InvParam      p {};
	InvResult     res {};
	InvRecipients list {};
	const auto    param = [&](int32_t mode, void* cb) {
        std::memset(&p, 0, sizeof(p));
        p.size         = sizeof(InvParam);
        p.mode         = mode;
        p.user_id      = 1;
        p.callback_arg = cb;
	};
	const auto fresh = [&](bool with_list) { // a result the call has not written, reserved bytes zero
		std::memset(&res, kS8, sizeof(res));
		std::memset(res.reserved, 0, sizeof(res.reserved));
		std::memset(&list, kS8, sizeof(list));
		res.recipients = with_list ? &list.count : nullptr;
	};
	const auto untouched = [&] {
		return reinterpret_cast<uintptr_t>(res.callback_arg) == static_cast<uintptr_t>(kS64) &&
		       static_cast<uint32_t>(res.error_code) == kS32 && static_cast<uint32_t>(res.result) == kS32 &&
		       list.count == kS32;
	};
	const auto fields = [&] {
		return Fmt("callback %p, error %d, result %d, count 0x%x", res.callback_arg, res.error_code, res.result, list.count);
	};

	if (on) {
		int r = close();
		Check("invitationdialog Close before Initialize: NOT_INITIALIZED, status 0", r == kInvNotInit && status() == 0, Hex(r));
		r = term();
		Check("invitationdialog Terminate before Initialize: NOT_INITIALIZED", r == kInvNotInit && status() == 0, Hex(r));
		fresh(true);
		r = get(&res);
		Check("invitationdialog GetResult before Initialize: NOT_INITIALIZED, nothing written", r == kInvNotInit && untouched(),
		      Hex(r));
		r = init();
		Check("invitationdialog Initialize: 0; GetStatus 1, UpdateStatus 1", r == 0 && status() == 1 && update() == 1, Hex(r));
		r = init();
		Check("invitationdialog Initialize again: ALREADY_INITIALIZED, status 1", r == kInvAlready && status() == 1, Hex(r));
		fresh(true);
		r          = get(&res);
		const int n = get(nullptr);
		Check("invitationdialog GetResult while initialized: NOT_FINISHED, also for a null result (the status first)",
		      r == kInvNotFinished && n == kInvNotFinished && untouched(), Hex(r) + " " + Hex(n));
		r = open(nullptr);
		Check("invitationdialog Open(null): ARG_NULL, status 1", r == kInvArgNull && status() == 1, Hex(r));
		param(1, a);
		r = open(&p);
		Check("invitationdialog Open (send): 0, finished at once: GetStatus 3, UpdateStatus 3",
		      r == 0 && status() == 3 && update() == 3, Hex(r));
		r = get(nullptr);
		Check("invitationdialog GetResult(null) when finished: ARG_NULL", r == kInvArgNull, Hex(r));
		fresh(true);
		res.reserved[5] = 1;
		r               = get(&res);
		Check("invitationdialog GetResult with a reserved byte set: AnyPS5 has no answer, today's 0 kept, nothing written",
		      r == 0 && untouched() && res.reserved[5] == 1, Hex(r) + ", " + fields());
		fresh(true);
		r = get(&res);
		Check("invitationdialog GetResult: 0, the Open's callback argument, error 0, USER_CANCELED, count 0, rest untouched",
		      r == 0 && res.callback_arg == a && res.error_code == 0 && res.result == 1 && list.count == 0 &&
		          res.recipients == &list.count && AllBytes(list.online_ids, sizeof(list.online_ids), kS8) &&
		          AllBytes(res.reserved, sizeof(res.reserved), 0),
		      Hex(r) + ", " + fields());
		fresh(false);
		r = get(&res);
		Check("invitationdialog GetResult without a recipient list: 0, the same fields",
		      r == 0 && res.callback_arg == a && res.error_code == 0 && res.result == 1 && res.recipients == nullptr,
		      Hex(r) + ", " + fields());
		param(2, b);
		r = open(&p);
		fresh(false);
		int r2 = get(&res);
		Check("invitationdialog Open (receive) from finished: 0, status 3; GetResult gives its callback argument",
		      r == 0 && status() == 3 && r2 == 0 && res.callback_arg == b, Hex(r) + " " + Hex(r2) + ", " + fields());
		p.size = 100;
		r      = open(&p);
		Check("invitationdialog Open with size 100: AnyPS5 has no answer, today's kept: 0, running (2)", r == 0 && status() == 2,
		      Hex(r));
		r = update();
		Check("invitationdialog UpdateStatus of the running dialog: 3 (today's, unchanged), GetStatus 3",
		      r == 3 && status() == 3, Fmt("%d", r));
		fresh(false);
		r = get(&res);
		Check("invitationdialog GetResult after it: 0 with the last ported Open's callback argument",
		      r == 0 && res.callback_arg == b && res.result == 1, Hex(r) + ", " + fields());
		param(3, a);
		r  = open(&p);
		r2 = status();
		const int c = close();
		Check("invitationdialog Open with mode 3: today's 0 and running; Close of it: AnyPS5 has no answer, today's 0, finished",
		      r == 0 && r2 == 2 && c == 0 && status() == 3, Hex(r) + " " + Hex(c));
		r                = term();
		r2               = status();
		const int again  = term();
		fresh(false);
		const int g = get(&res);
		Check("invitationdialog Terminate: 0, status 0; again: NOT_INITIALIZED; GetResult: NOT_INITIALIZED",
		      r == 0 && r2 == 0 && again == kInvNotInit && g == kInvNotInit && untouched(),
		      Hex(r) + " " + Hex(again) + " " + Hex(g));
		param(1, a);
		r = open(&p);
		Check("invitationdialog Open before Initialize: AnyPS5 has no answer, today's kept: 0, running", r == 0 && status() == 2,
		      Hex(r));
		r  = close();
		r2 = term();
		Check("invitationdialog Close of it: today's 0 (finished); Terminate: 0, status 0", r == 0 && r2 == 0 && status() == 0,
		      Hex(r) + " " + Hex(r2));
	} else {
		int r = close();
		Check("invitationdialog off: Close before Initialize: 0, status 0", r == 0 && status() == 0, Hex(r));
		r = term();
		Check("invitationdialog off: Terminate before Initialize: 0, status 0", r == 0 && status() == 0, Hex(r));
		fresh(true);
		r           = get(&res);
		const int n = get(nullptr);
		Check("invitationdialog off: GetResult: 0, nothing written; GetResult(null): 0", r == 0 && n == 0 && untouched(),
		      Hex(r) + " " + Hex(n));
		r        = init();
		int r2   = init();
		Check("invitationdialog off: Initialize twice: 0, 0; GetStatus 1, UpdateStatus 1",
		      r == 0 && r2 == 0 && status() == 1 && update() == 1, Hex(r) + " " + Hex(r2));
		r = open(nullptr);
		Check("invitationdialog off: Open(null): 0, running (2)", r == 0 && status() == 2, Hex(r));
		r = update();
		Check("invitationdialog off: UpdateStatus: 3, GetStatus 3", r == 3 && status() == 3, Fmt("%d", r));
		fresh(true);
		r = get(&res);
		Check("invitationdialog off: GetResult when finished: 0, nothing written", r == 0 && untouched(),
		      Hex(r) + ", " + fields());
		r = close();
		Check("invitationdialog off: Close: 0, status 3", r == 0 && status() == 3, Hex(r));
		r = term();
		Check("invitationdialog off: Terminate: 0, status 0", r == 0 && status() == 0, Hex(r));
		// the held two, registered when off: today's OpenA (running), UpdateStatus (finished), GetResultA, Terminate
		auto open_a = Fn<NoArg>("sAxbHhAWMXM", lib);
		auto get_a  = Fn<NoArg>("WuuUhuKOxwQ", lib);
		r           = open_a();
		r2          = status();
		const int u = update();
		const int g = get_a();
		const int t = term();
		Check("invitationdialog off: held OpenA: 0, running; UpdateStatus 3; held GetResultA: 0; Terminate: 0, status 0",
		      r == 0 && r2 == 2 && u == 3 && g == 0 && t == 0 && status() == 0,
		      Hex(r) + " " + Fmt("%d %d ", r2, u) + Hex(g) + " " + Hex(t));
	}
	Held(w, lib, on, held, false); // off: called above
}

// =====================================================================================================================
// WebBrowserDialog
// =====================================================================================================================
constexpr int kWNotFinished  = static_cast<int>(0x80B80005u);
constexpr int kWInvalidState = static_cast<int>(0x80B80006u);
constexpr int kWParameter    = static_cast<int>(0x80B8000Au);
constexpr int kWNotRunning   = static_cast<int>(0x80B8000Bu);
constexpr int kWArgNull      = static_cast<int>(0x80B8000Du);

struct WCookie {
	uint64_t    size; // 280
	const char* address;
	const char* cookie;
	uint8_t     reserved[256];
};
struct WReset {
	uint64_t size; // 264
	uint8_t  reserved[256];
};
struct WAllow {
	uint64_t    size; // 424
	const char* addresses[20];
	uint8_t     reserved[256];
};
static_assert(sizeof(WCookie) == 280 && sizeof(WReset) == 264 && sizeof(WAllow) == 424);

alignas(8) uint8_t g_wresult[256];
alignas(8) uint8_t g_wext[2096 + 16];
alignas(8) uint8_t g_wext_copy[2096 + 16];
char g_long[0x1001 + 16];

const char* Chars(size_t n) { // n 'a's, then the terminator
	std::memset(g_long, 'a', n);
	g_long[n] = '\0';
	return g_long;
}

void CaseWebBrowserDialog() {
	g_case          = "webbrowserdialog";
	const char* lib = "libSceWebBrowserDialog";
	const bool  on  = g_wbd;
	const char* w   = on ? "webbrowserdialog" : "webbrowserdialog off:";
	const std::vector<const char*> nids = {"PSK+Eik919Q", "Wit4LjeoeX4", "vCaW0fgVQmc", "CFTG6a8TjOU",
	                                       "uYELOMVnmNQ", "FraP7debcdg", "O7dIZQrwVFY", "Cya+jvTtPqg",
	                                       "TZnDVkP91Rg", "RLhKBOoNyXY", "h1dR-t5ISgg", "8r4EJ3FiX4w"};
	const std::vector<const char*> held = {"Wit4LjeoeX4", "uYELOMVnmNQ", "RLhKBOoNyXY", "8r4EJ3FiX4w"};
	const std::vector<const char*> live = {"jqb7HntFQFc", "ocHtyBwHfys"};
	Registration(w, lib, on, nids, held, live);

	auto close     = Fn<NoArg>("PSK+Eik919Q", lib);
	auto get       = Fn<PtrArg>("vCaW0fgVQmc", lib);
	auto status    = Fn<NoArg>("CFTG6a8TjOU", lib);
	auto open      = Fn<CPtr>("FraP7debcdg", lib);
	auto opd       = Fn<CPtr2>("O7dIZQrwVFY", lib);
	auto reset     = Fn<CPtr>("Cya+jvTtPqg", lib);
	auto set       = Fn<CPtr>("TZnDVkP91Rg", lib);
	auto update    = Fn<NoArg>("h1dR-t5ISgg", lib);
	auto live_init = Fn<NoArg>("jqb7HntFQFc", lib);
	auto live_term = Fn<NoArg>("ocHtyBwHfys", lib);

	const uint8_t dummy_param[64] = {};
	WCookie       ck {};
	WReset        rs {};
	WAllow        al {};
	const auto    cookie = [&] {
        std::memset(&ck, 0, sizeof(ck));
        ck.size    = sizeof(WCookie);
        ck.address = "https://example.invalid/";
        ck.cookie  = "name=value";
	};
	const auto reset_param = [&] {
		std::memset(&rs, 0, sizeof(rs));
		rs.size = sizeof(WReset);
	};
	const auto allow = [&] {
		std::memset(&al, 0, sizeof(al));
		al.size         = sizeof(WAllow);
		al.addresses[0] = "https://example.invalid/";
	};
	const auto fresh = [&](const uint8_t* extended) { // result field and padding sentinel, reserved zero
		std::memset(g_wresult, 0, sizeof(g_wresult));
		std::memset(g_wresult, kS8, 8);
		std::memcpy(g_wresult + 8, &extended, sizeof(extended));
	};
	const auto result_untouched = [&] { return AllBytes(g_wresult, 8, kS8); };
	const auto ext_fresh        = [&] {
        std::memset(g_wext, 0, sizeof(g_wext));
        const uint64_t size = 2096;
        std::memcpy(g_wext, &size, sizeof(size));
        std::memset(g_wext + 12, 'c', 2048);       // the content
        std::memset(g_wext + 2064, 0x11, 12);      // the extended content pointer and its capacity (not checked)
        std::memset(g_wext + 2096, kS8, 16);       // past the end
        std::memcpy(g_wext_copy, g_wext, sizeof(g_wext));
	};

	int r = live_init();
	Check(Fmt("%s the live Initialize (libNet.cpp): 0; GetStatus 0 (split state: it keeps no state)", w),
	      r == 0 && status() == 0, Hex(r));
	if (on) {
		r = close();
		Check("webbrowserdialog Close with nothing open: NOT_RUNNING, status 0", r == kWNotRunning && status() == 0, Hex(r));
		r = get(nullptr);
		Check("webbrowserdialog GetResult(null): ARG_NULL", r == kWArgNull, Hex(r));
		fresh(nullptr);
		g_wresult[100] = 1;
		r              = get(g_wresult);
		Check("webbrowserdialog GetResult with reserved byte 100 set: PARAMETER, nothing written",
		      r == kWParameter && result_untouched(), Hex(r));
		fresh(nullptr);
		r = get(g_wresult);
		Check("webbrowserdialog GetResult with nothing finished: NOT_FINISHED, nothing written",
		      r == kWNotFinished && result_untouched(), Hex(r));

		// the cookie calls, nothing open
		int v[12];
		v[0] = set(nullptr);
		cookie();
		v[1] = set(&ck);
		ck.size--;
		v[2] = set(&ck);
		cookie();
		ck.address = "";
		v[3]       = set(&ck);
		cookie();
		ck.address = Chars(0x7FF);
		v[4]       = set(&ck);
		ck.address = Chars(0x800);
		v[5]       = set(&ck);
		cookie();
		ck.cookie = nullptr;
		v[6]      = set(&ck);
		ck.cookie = Chars(0xFFF);
		v[7]      = set(&ck);
		ck.cookie = Chars(0x1000);
		v[8]      = set(&ck);
		cookie();
		ck.reserved[255] = 1;
		v[9]             = set(&ck);
		Check("webbrowserdialog SetCookie: null ARG_NULL; valid 0; size 279, empty address PARAMETER; address 0x7FF 0, "
		      "0x800 PARAMETER; null cookie PARAMETER; cookie 0xFFF 0, 0x1000 PARAMETER; reserved byte PARAMETER",
		      v[0] == kWArgNull && v[1] == 0 && v[2] == kWParameter && v[3] == kWParameter && v[4] == 0 &&
		          v[5] == kWParameter && v[6] == kWParameter && v[7] == 0 && v[8] == kWParameter && v[9] == kWParameter,
		      Hex(v[0]) + " " + Hex(v[1]) + " " + Hex(v[2]) + " " + Hex(v[3]) + " " + Hex(v[4]) + " " + Hex(v[5]) + " " +
		          Hex(v[6]) + " " + Hex(v[7]) + " " + Hex(v[8]) + " " + Hex(v[9]));
		v[0] = reset(nullptr);
		reset_param();
		v[1] = reset(&rs);
		rs.size--;
		v[2] = reset(&rs);
		reset_param();
		rs.reserved[0] = 1;
		v[3]           = reset(&rs);
		Check("webbrowserdialog ResetCookie: null ARG_NULL; valid 0; size 263 PARAMETER; reserved byte PARAMETER",
		      v[0] == kWArgNull && v[1] == 0 && v[2] == kWParameter && v[3] == kWParameter,
		      Hex(v[0]) + " " + Hex(v[1]) + " " + Hex(v[2]) + " " + Hex(v[3]));

		r = open(nullptr);
		Check("webbrowserdialog Open(null): ARG_NULL, status 0", r == kWArgNull && status() == 0, Hex(r));
		r = open(dummy_param);
		Check("webbrowserdialog Open: 0, finished at once (GetStatus 3)", r == 0 && status() == 3, Hex(r));
		cookie();
		reset_param();
		v[0] = set(&ck);
		v[1] = set(nullptr);
		v[2] = reset(nullptr);
		v[3] = reset(&rs);
		Check("webbrowserdialog while marked open: SetCookie INVALID_STATE (also for null: the mark first); ResetCookie(null) "
		      "ARG_NULL (null first), ResetCookie INVALID_STATE",
		      v[0] == kWInvalidState && v[1] == kWInvalidState && v[2] == kWArgNull && v[3] == kWInvalidState,
		      Hex(v[0]) + " " + Hex(v[1]) + " " + Hex(v[2]) + " " + Hex(v[3]));
		r    = update();
		v[0] = set(&ck);
		v[1] = reset(&rs);
		Check("webbrowserdialog UpdateStatus: 3, and the mark is cleared: SetCookie 0, ResetCookie 0",
		      r == 3 && v[0] == 0 && v[1] == 0, Fmt("%d ", r) + Hex(v[0]) + " " + Hex(v[1]));
		fresh(nullptr);
		r = get(g_wresult);
		Check("webbrowserdialog GetResult: 0, USER_CANCELED (1) at 0; the padding, pointer and reserved bytes untouched",
		      r == 0 && I32(g_wresult, 0) == 1 && AllBytes(g_wresult + 4, 4, kS8) && AllBytes(g_wresult + 8, 248, 0),
		      Hex(r) + Fmt(", result %d", I32(g_wresult, 0)));
		ext_fresh();
		fresh(g_wext);
		r = get(g_wresult);
		Check("webbrowserdialog GetResult with an extended result (2096, reserved zero): 0, USER_CANCELED, extended untouched",
		      r == 0 && I32(g_wresult, 0) == 1 && std::memcmp(g_wext, g_wext_copy, sizeof(g_wext)) == 0, Hex(r));
		ext_fresh();
		g_wext[0] = 0x2F; // 2095
		fresh(g_wext);
		v[0] = get(g_wresult);
		const bool u0 = result_untouched();
		ext_fresh();
		g_wext[2061] = 1;
		fresh(g_wext);
		v[1] = get(g_wresult);
		ext_fresh();
		g_wext[2095] = 1;
		fresh(g_wext);
		v[2] = get(g_wresult);
		const bool u2 = result_untouched();
		ext_fresh();
		g_wext[2075] = 0x22; // the capacity: not a reserved byte
		g_wext[11]   = 0x33; // the type
		fresh(g_wext);
		v[3] = get(g_wresult);
		Check("webbrowserdialog GetResult extended size 2095 / byte 2061 / byte 2095: PARAMETER, nothing written; type and "
		      "capacity bytes set: 0",
		      v[0] == kWParameter && v[1] == kWParameter && v[2] == kWParameter && u0 && u2 && v[3] == 0,
		      Hex(v[0]) + " " + Hex(v[1]) + " " + Hex(v[2]) + " " + Hex(v[3]));
		r            = open(dummy_param);
		const int c  = close();
		const int sc = set(&ck);
		Check("webbrowserdialog Open then Close: 0, NOT_RUNNING (finished, not running), status 3; Close cleared the mark",
		      r == 0 && c == kWNotRunning && status() == 3 && sc == 0, Hex(r) + " " + Hex(c) + " " + Hex(sc));

		// OpenForPredeterminedContent's allow list
		v[0] = opd(dummy_param, nullptr);
		allow();
		al.size = 423;
		v[1]    = opd(dummy_param, &al);
		allow();
		al.addresses[0] = nullptr;
		v[2]            = opd(dummy_param, &al);
		allow();
		al.addresses[3] = "";
		v[3]            = opd(dummy_param, &al);
		allow();
		al.addresses[3] = Chars(256);
		v[4]            = opd(dummy_param, &al);
		allow();
		al.reserved[0] = 1;
		v[5]           = opd(dummy_param, &al);
		allow();
		al.addresses[19] = Chars(255);
		v[6]             = opd(nullptr, &al);
		const int sc0    = set(&ck);
		Check("webbrowserdialog OpenForPredeterminedContent: no list ARG_NULL; size 423, no address, empty address, 256 "
		      "characters, reserved byte PARAMETER; a valid list with a null param ARG_NULL; nothing marked open",
		      v[0] == kWArgNull && v[1] == kWParameter && v[2] == kWParameter && v[3] == kWParameter &&
		          v[4] == kWParameter && v[5] == kWParameter && v[6] == kWArgNull && sc0 == 0,
		      Hex(v[0]) + " " + Hex(v[1]) + " " + Hex(v[2]) + " " + Hex(v[3]) + " " + Hex(v[4]) + " " + Hex(v[5]) + " " +
		          Hex(v[6]) + " " + Hex(sc0));
		r             = opd(dummy_param, &al);
		const int st  = status();
		const int sc1 = set(&ck);
		const int up  = update();
		const int sc2 = set(&ck);
		Check("webbrowserdialog OpenForPredeterminedContent (a 255-character address): 0, finished, marked open "
		      "(SetCookie INVALID_STATE); UpdateStatus 3 clears it (SetCookie 0)",
		      r == 0 && st == 3 && sc1 == kWInvalidState && up == 3 && sc2 == 0,
		      Hex(r) + Fmt(" %d ", st) + Hex(sc1) + Fmt(" %d ", up) + Hex(sc2));
	} else {
		r = close();
		Check("webbrowserdialog off: Close with nothing open: 0, status 0", r == 0 && status() == 0, Hex(r));
		r = get(nullptr);
		fresh(nullptr);
		const int g = get(g_wresult);
		Check("webbrowserdialog off: GetResult(null): 0; GetResult: 0, nothing written", r == 0 && g == 0 && result_untouched(),
		      Hex(r) + " " + Hex(g));
		cookie();
		ck.size--;
		const int s0 = set(nullptr);
		const int s1 = set(&ck);
		const int r0 = reset(nullptr);
		Check("webbrowserdialog off: SetCookie(null), SetCookie(size 279), ResetCookie(null): 0 each",
		      s0 == 0 && s1 == 0 && r0 == 0, Hex(s0) + " " + Hex(s1) + " " + Hex(r0));
		r = open(nullptr);
		Check("webbrowserdialog off: Open(null): 0, running (2)", r == 0 && status() == 2, Hex(r));
		cookie();
		const int s2 = set(&ck);
		Check("webbrowserdialog off: SetCookie while open: 0", s2 == 0, Hex(s2));
		r = update();
		Check("webbrowserdialog off: UpdateStatus: 3, GetStatus 3", r == 3 && status() == 3, Fmt("%d", r));
		fresh(nullptr);
		r = get(g_wresult);
		Check("webbrowserdialog off: GetResult when finished: 0, nothing written", r == 0 && result_untouched(), Hex(r));
		r = close();
		Check("webbrowserdialog off: Close: 0, status 3", r == 0 && status() == 3, Hex(r));
		r = opd(nullptr, nullptr);
		Check("webbrowserdialog off: OpenForPredeterminedContent(null, null): 0, running; UpdateStatus 3",
		      r == 0 && status() == 2 && update() == 3, Hex(r));
	}
	Held(w, lib, on, held);
	r = live_term();
	Check(Fmt("%s the live Terminate (libNet.cpp): 0; GetStatus stays 3 (split state)", w), r == 0 && status() == 3, Hex(r));
}

// =====================================================================================================================
// SharePlay
// =====================================================================================================================
constexpr int kSInvalidArgs = static_cast<int>(0x810E0001u);

void CaseSharePlay() {
	g_case          = "shareplay";
	const char* lib = "libSceSharePlay";
	const bool  on  = g_shp;
	const char* w   = on ? "shareplay" : "shareplay off:";
	const std::vector<const char*> held = {"ggnCfalLU-8", "vUMkWXQff3w", "Md7Mdkr8LBc", "9zwJpai7jGc", "VUW2V9cUTP4",
	                                       "XL0WwUJoQPg", "6-1fKaa5HlY", "U28jAuLHj6c", "3Oaux9ITEtY", "QZy+KmyqKPU",
	                                       "co2NCj--pnc", "KADsbjNCgPo", "-F6NddfUsa4", "rWVNHNnEx6g", "zEDkUWLVwFI",
	                                       "aGlema+JxUU", "LpPA6mprZ8Q", "wcI2co2I4Xc", "6egMR0eB8RU", "891hmdoV7UQ"};
	std::vector<const char*> nids = {"OOrLKB0bSDs", "+MCXJlWdi+s"};
	nids.insert(nids.end(), held.begin(), held.end());
	Registration(w, lib, on, nids, held, {"isruqthpYcw", "UaLjloJinow"});

	auto    info   = Fn<PtrArg>("OOrLKB0bSDs", lib);
	auto    info_a = Fn<PtrArg>("+MCXJlWdi+s", lib);
	uint8_t buf[80];
	if (on) {
		int r = info(nullptr);
		std::memset(buf, kS8, sizeof(buf));
		int r2 = info(buf);
		Check("shareplay GetCurrentConnectionInfo: null INVALID_ARGS; 0, 48 bytes zero, user ids -1 at 48 and 52, bytes "
		      "56+ untouched",
		      r == kSInvalidArgs && r2 == 0 && AllBytes(buf, 48, 0) && I32(buf, 48) == -1 && I32(buf, 52) == -1 &&
		          AllBytes(buf + 56, 24, kS8),
		      Hex(r) + " " + Hex(r2));
		r = info_a(nullptr);
		std::memset(buf, kS8, sizeof(buf));
		r2 = info_a(buf);
		Check("shareplay GetCurrentConnectionInfoA: null INVALID_ARGS; 0, 64 bytes zero, user ids -1 at 64 and 68, bytes "
		      "72+ untouched",
		      r == kSInvalidArgs && r2 == 0 && AllBytes(buf, 64, 0) && I32(buf, 64) == -1 && I32(buf, 68) == -1 &&
		          AllBytes(buf + 72, 8, kS8),
		      Hex(r) + " " + Hex(r2));
	} else {
		const int r = info(nullptr);
		std::memset(buf, kS8, sizeof(buf));
		const int r2 = info(buf);
		const int r3 = info_a(nullptr);
		const int r4 = info_a(buf);
		Check("shareplay off: both connection infos, null and not: 0, nothing written",
		      r == 0 && r2 == 0 && r3 == 0 && r4 == 0 && AllBytes(buf, sizeof(buf), kS8),
		      Hex(r) + " " + Hex(r2) + " " + Hex(r3) + " " + Hex(r4));
	}
	Held(w, lib, on, held);
}

// =====================================================================================================================
// GameLiveStreaming
// =====================================================================================================================
constexpr int kGInvalid = static_cast<int>(0x80A00002u);

alignas(8) uint8_t g_gbuf[0x134C + 16];
alignas(8) uint8_t g_tags[17 * 224];
alignas(8) uint8_t g_cmds[6 * 228];
alignas(8) uint8_t g_cam[48];

void CaseGameLiveStreaming() {
	g_case          = "gamelivestreaming";
	const char* lib = "libSceGameLiveStreaming";
	const bool  on  = g_gls;
	const char* w   = on ? "gamelivestreaming" : "gamelivestreaming off:";
	const std::vector<const char*> ported = {"lK8dLBNp9OE", "OIIm19xu+NM", "fo5B8RUaBxQ", "yeQKjHETi40", "PMx7N4WqNdo",
	                                         "hUY-mSOyGL0", "ZuX+zzz2DkA", "ycodiP2I0xo", "x6deXUpQbBo", "lZ2Sd0uEvpo",
	                                         "hggKhPySVgI", "3PSiwAzFISE", "QmQYwQ7OTJI"};
	const std::vector<const char*> match  = {"K0QxEbD7q+c", "q-kxuaF7URU", "wBOQWjbWMfU", "-EHnU68gExU",
	                                         "6c2zGtThFww", "FcHBfHjFXkA", "dWM80AX39o4"};
	const std::vector<const char*> held   = {
        "caqgDl+V9qA", "0i8Lrllxwow", "NqkTzemliC0", "PC4jq87+YQI", "aRSQNqbats4", "CoPMx369EqM", "ysWfX5PPbfc",
        "cvRCb7DTAig", "nFP8qT9YXbo", "b5RaMD2J0So", "hBdd8n6kuvE", "uhCmn81s-mU", "iorzW0pKOiA", "gDSvt78H3Oo",
        "HE93dr-5rx4", "TwuUzTKKeek", "Gw6S4oqlY7E", "Sb5bAXyUt5c", "mCoz3k3zPmA", "MLvYI86FFAo", "y0KkAydy9xE",
        "Y1WxX7dPMCw", "D7dg5QJ4FlE", "bYuGUBuIsaY", "5XHaH3kL+bA"};
	std::vector<const char*> nids = ported;
	nids.insert(nids.end(), match.begin(), match.end());
	nids.insert(nids.end(), held.begin(), held.end());
	Registration(w, lib, on, nids, held, {"kvYEw2lBndk", "9yK6Fk8mKOQ"});

	auto status2 = Fn<PtrArg>("lK8dLBNp9OE", lib);
	auto program = Fn<PtrArg>("OIIm19xu+NM", lib);
	auto sep     = Fn<PtrArg>("fo5B8RUaBxQ", lib);
	auto count   = Fn<Count>("yeQKjHETi40", lib);
	auto msgs    = Fn<Msgs>("PMx7N4WqNdo", lib);
	auto meta    = Fn<Text>("hUY-mSOyGL0", lib);
	auto spoiler = Fn<Entr>("ZuX+zzz2DkA", lib);
	auto preset  = Fn<Entr>("ycodiP2I0xo", lib);
	auto desc    = Fn<Text>("x6deXUpQbBo", lib);
	auto clear   = Fn<IntArg>("lZ2Sd0uEvpo", lib);
	auto post    = Fn<Text>("hggKhPySVgI", lib);
	auto camera  = Fn<CPtr>("3PSiwAzFISE", lib);
	auto session = Fn<Text>("QmQYwQ7OTJI", lib);

	if (on) {
		int r = status2(nullptr);
		std::memset(g_gbuf, kS8, 80);
		int r2 = status2(g_gbuf);
		Check("gamelivestreaming GetCurrentStatus2: null INVALID_ARGUMENT; 0, user id -1, bytes 4-71 zero, 72+ untouched",
		      r == kGInvalid && r2 == 0 && I32(g_gbuf, 0) == -1 && AllBytes(g_gbuf + 4, 68, 0) && AllBytes(g_gbuf + 72, 8, kS8),
		      Hex(r) + " " + Hex(r2));
		r = program(nullptr);
		std::memset(g_gbuf, kS8, sizeof(g_gbuf));
		r2 = program(g_gbuf);
		Check("gamelivestreaming GetProgramInfo: null INVALID_ARGUMENT; 0, 0x134C bytes zero, the rest untouched",
		      r == kGInvalid && r2 == 0 && AllBytes(g_gbuf, 0x134C, 0) && AllBytes(g_gbuf + 0x134C, 16, kS8),
		      Hex(r) + " " + Hex(r2));
		r = sep(nullptr);
		std::memset(g_gbuf, kS8, 80);
		r2 = sep(g_gbuf);
		Check("gamelivestreaming ScreenInitializeSeparateModeParameter: null INVALID_ARGUMENT; 0, 68 bytes zero, 68+ untouched",
		      r == kGInvalid && r2 == 0 && AllBytes(g_gbuf, 68, 0) && AllBytes(g_gbuf + 68, 12, kS8), Hex(r) + " " + Hex(r2));

		uint32_t  c  = kS32;
		const int c0 = count(1, nullptr);
		const int c1 = count(0, &c);
		const int c2 = count(4, &c);
		const bool cu = c == kS32;
		const int c3 = count(3, &c);
		Check("gamelivestreaming GetSocialFeedbackMessagesCount: null, type 0, type 4 INVALID_ARGUMENT (count untouched); "
		      "type 3: 0, count 0",
		      c0 == kGInvalid && c1 == kGInvalid && c2 == kGInvalid && cu && c3 == 0 && c == 0,
		      Hex(c0) + " " + Hex(c1) + " " + Hex(c2) + " " + Hex(c3) + Fmt(", count %u", c));
		size_t n = kS64;
		std::memset(g_gbuf, kS8, 64);
		const int m0 = msgs(2, 4, nullptr, &n);
		const int m1 = msgs(2, 4, g_gbuf, nullptr);
		const int m2 = msgs(0, 4, g_gbuf, &n);
		const bool nu = n == static_cast<size_t>(kS64);
		const int m3 = msgs(1, 4, g_gbuf, &n);
		Check("gamelivestreaming GetSocialFeedbackMessages: null messages, null count, type 0 INVALID_ARGUMENT; type 1: 0, "
		      "none acquired, messages untouched",
		      m0 == kGInvalid && m1 == kGInvalid && m2 == kGInvalid && nu && m3 == 0 && n == 0 && AllBytes(g_gbuf, 64, kS8),
		      Hex(m0) + " " + Hex(m1) + " " + Hex(m2) + " " + Hex(m3));

		struct Limit {
			const char* name;
			Text        fn;
			size_t      max;
		};
		const Limit limits[] = {{"SetMetadata", meta, 240},
		                        {"SetPresetSocialFeedbackCommandsDescription", desc, 720},
		                        {"SetInvitationSessionId", session, 45},
		                        {"PostSocialMessage", post, 360}};
		for (const auto& l: limits) {
			const int t0 = l.fn(nullptr);
			const int t1 = l.fn("");
			const int t2 = l.fn(Chars(l.max));
			const int t3 = l.fn(Chars(l.max + 1));
			Check(Fmt("gamelivestreaming %s: null INVALID_ARGUMENT, empty 0, %zu characters 0, %zu INVALID_ARGUMENT", l.name,
			          l.max, l.max + 1),
			      t0 == kGInvalid && t1 == 0 && t2 == 0 && t3 == kGInvalid,
			      Hex(t0) + " " + Hex(t1) + " " + Hex(t2) + " " + Hex(t3));
		}

		std::memset(g_tags, 0, sizeof(g_tags));
		for (size_t i = 0; i < 17; i++) {
			std::memset(g_tags + i * 224, 't', 192); // text up to 192 bytes
		}
		int s[6];
		s[0] = spoiler(0, nullptr);
		s[1] = spoiler(17, g_tags);
		s[2] = spoiler(16, g_tags);
		s[3] = spoiler(0, g_tags);
		g_tags[224 + 223] = 1; // the tail of tag 1
		s[4]              = spoiler(2, g_tags);
		const int s1only  = spoiler(1, g_tags);
		g_tags[224 + 223] = 0;
		g_tags[224 + 193] = 1;
		s[5]              = spoiler(2, g_tags);
		Check("gamelivestreaming SetSpoilerTag: null, 17 INVALID_ARGUMENT; 16 and 0 tags 0; a tail byte (223 or 193) of tag 1 "
		      "INVALID_ARGUMENT, of a tag not passed 0",
		      s[0] == kGInvalid && s[1] == kGInvalid && s[2] == 0 && s[3] == 0 && s[4] == kGInvalid && s1only == 0 &&
		          s[5] == kGInvalid,
		      Hex(s[0]) + " " + Hex(s[1]) + " " + Hex(s[2]) + " " + Hex(s[3]) + " " + Hex(s[4]) + " " + Hex(s1only) + " " +
		          Hex(s[5]));
		std::memset(g_cmds, 0, sizeof(g_cmds));
		for (size_t i = 0; i < 6; i++) {
			std::memset(g_cmds + i * 228, 'p', 197); // the command's body
		}
		s[0]                  = preset(5, nullptr);
		s[1]                  = preset(6, g_cmds);
		s[2]                  = preset(5, g_cmds);
		g_cmds[4 * 228 + 197] = 1;
		s[3]                  = preset(5, g_cmds);
		s[4]                  = preset(4, g_cmds);
		Check("gamelivestreaming SetPresetSocialFeedbackCommands: null, 6 INVALID_ARGUMENT; 5 with bodies 0; tail byte 197 "
		      "of command 4 INVALID_ARGUMENT, 4 commands 0",
		      s[0] == kGInvalid && s[1] == kGInvalid && s[2] == 0 && s[3] == kGInvalid && s[4] == 0,
		      Hex(s[0]) + " " + Hex(s[1]) + " " + Hex(s[2]) + " " + Hex(s[3]) + " " + Hex(s[4]));
		const int k0 = clear(0);
		const int k1 = clear(1);
		const int k2 = clear(3);
		const int k3 = clear(4);
		const int k4 = clear(-1);
		Check("gamelivestreaming ClearSocialFeedbackMessages: types 1 and 3: 0; 0, 4, -1: INVALID_ARGUMENT",
		      k0 == kGInvalid && k1 == 0 && k2 == 0 && k3 == kGInvalid && k4 == kGInvalid,
		      Hex(k0) + " " + Hex(k1) + " " + Hex(k2) + " " + Hex(k3) + " " + Hex(k4));
		std::memset(g_cam, 0, sizeof(g_cam));
		std::memset(g_cam, 'h', 9);
		g_cam[40]     = 1; // past the 40 bytes read
		const int a0  = camera(nullptr);
		const int a1  = camera(g_cam);
		g_cam[9]      = 1;
		const int a2  = camera(g_cam);
		g_cam[9]      = 0;
		g_cam[39]     = 1;
		const int a3  = camera(g_cam);
		Check("gamelivestreaming SetCameraFrameSetting: null INVALID_ARGUMENT; head bytes set 0; tail byte 9 or 39 "
		      "INVALID_ARGUMENT; byte 40 not read",
		      a0 == kGInvalid && a1 == 0 && a2 == kGInvalid && a3 == kGInvalid,
		      Hex(a0) + " " + Hex(a1) + " " + Hex(a2) + " " + Hex(a3));
	} else {
		std::memset(g_gbuf, kS8, sizeof(g_gbuf));
		uint32_t c  = kS32;
		size_t   n  = kS64;
		int      v[13];
		v[0]  = status2(g_gbuf);
		v[1]  = program(g_gbuf);
		v[2]  = sep(g_gbuf);
		v[3]  = count(1, &c);
		v[4]  = msgs(1, 4, g_gbuf, &n);
		v[5]  = meta(nullptr);
		v[6]  = spoiler(17, nullptr);
		v[7]  = preset(6, nullptr);
		v[8]  = desc(nullptr);
		v[9]  = clear(0);
		v[10] = post(nullptr);
		v[11] = camera(nullptr);
		v[12] = session(nullptr);
		std::string all;
		int         zero = 0;
		for (int x: v) {
			zero += x == 0 ? 1 : 0;
			all += Hex(x) + " ";
		}
		Check("gamelivestreaming off: the 13 edited calls, valid outputs and bad arguments: 0 each, nothing written",
		      zero == 13 && AllBytes(g_gbuf, sizeof(g_gbuf), kS8) && c == kS32 && n == static_cast<size_t>(kS64), all);
	}
	// already match (not edited): 0 either way
	int         zero = 0;
	std::string wrong;
	for (const char* m: match) {
		const int x = Fn<IntArg>(m, lib)(1); // PermitLiveStreaming(true) etc.; the no-argument ones ignore it
		if (x == 0) {
			zero++;
		} else {
			wrong += Fmt(" %s=%s", m, Hex(x).c_str());
		}
	}
	Check(Fmt("%s the 7 calls that already match (Permit*, SetMaxBitrate, Enable*, Clear*Tag/Commands): 0", w), zero == 7,
	      Fmt("%d of 7%s", zero, wrong.c_str()));
	Held(w, lib, on, held);
}

} // namespace tbd0405

int main(int argc, char** argv) {
	using namespace tbd0405;
	g_inv                 = EnvOn("KYTY_BC5_LOAD_INVITATIONDIALOG");
	g_wbd                 = EnvOn("KYTY_BC5_LOAD_WEBBROWSERDIALOG");
	g_shp                 = EnvOn("KYTY_BC5_LOAD_SHAREPLAY");
	g_gls                 = EnvOn("KYTY_BC5_LOAD_GAMELIVESTREAMING");
	const bool  all_on    = g_inv && g_wbd && g_shp && g_gls;
	const bool  all_off   = !g_inv && !g_wbd && !g_shp && !g_gls;
	const char* mode      = all_on ? "on" : all_off ? "off" : "mixed";
	if (argc > 2 || (argc == 2 && std::strcmp(argv[1], mode) != 0)) {
		std::printf("tbd0405: the argument says %s but the switches say %s (invitationdialog %d, webbrowserdialog %d, "
		            "shareplay %d, gamelivestreaming %d)\n",
		            argc == 2 ? argv[1] : "too much", mode, g_inv, g_wbd, g_shp, g_gls);
		return 2;
	}
	std::printf("tbd0405: switches invitationdialog %d, webbrowserdialog %d, shareplay %d, gamelivestreaming %d: %s\n",
	            g_inv, g_wbd, g_shp, g_gls, mode);
	std::fflush(stdout);
	std::thread(Watchdog).detach();

	g_case = "registration";
	// The four tables (each prints its "[bc5] exp 0405: ..." line on stderr), then libNet.cpp's live three.
	Libs::LibInvitationDialog::InitInvitationDialog_1(&g_all);
	Libs::LibWebBrowserDialog::InitWebBrowserDialog_1(&g_all);
	Libs::LibSharePlay::InitSharePlay_1(&g_all);
	Libs::LibGameLiveStreaming::InitGameLiveStreaming_1(&g_all);
	Libs::LibWebBrowserDialog::InitPlatform_1_WebBrowserDialog(&g_all);
	Libs::LibGameLiveStreaming::InitPlatform_1_GameLiveStreaming(&g_all);
	Libs::LibSharePlay::InitPlatform_1_SharePlay(&g_all);
	Libs::LibInvitationDialog::InitInvitationDialog_1(&g_dead);
	Libs::LibWebBrowserDialog::InitWebBrowserDialog_1(&g_dead);
	Libs::LibSharePlay::InitSharePlay_1(&g_dead);
	Libs::LibGameLiveStreaming::InitGameLiveStreaming_1(&g_dead);
	Libs::LibWebBrowserDialog::InitPlatform_1_WebBrowserDialog(&g_live);
	Libs::LibGameLiveStreaming::InitPlatform_1_GameLiveStreaming(&g_live);
	Libs::LibSharePlay::InitPlatform_1_SharePlay(&g_live);

	CaseInvitationDialog();
	CaseWebBrowserDialog();
	CaseSharePlay();
	CaseGameLiveStreaming();

	const int n = g_cases.load();
	const int p = g_passed.load();
	if (p != n) {
		std::printf("tbd0405: %s %d of %d passed; FAIL\n", mode, p, n);
		std::fflush(stdout);
		std::_Exit(1);
	}
	std::printf("tbd0405: %s %d of %d; end\n", mode, p, n);
	std::fflush(stdout);
	std::_Exit(0);
}
