// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0405 (series e7 of experiment 0401), tag tbp: the CPU test of mktbp0405.py (exp 0405 decision 4,
// dead-table batch 2): the NpPartner001, NpParty and NpSnsFacebookDialog tables of src/libs/libNp.cpp behind
// KYTY_BC5_LOAD_NPPARTNER, KYTY_BC5_LOAD_NPPARTY and KYTY_BC5_LOAD_NPSNSFACEBOOK, and the dead NpAuth table's five functions,
// ported into the live NpAuth table of src/libs/libNet.cpp (LibNpAuth::InitNet_1_NpAuth) behind KYTY_BC5_LOAD_NPAUTH.
// It registers the three switched tables into its own Loader::SymbolDatabase by calling their LIB_DEFINEs (as libs.cpp does
// when a switch is on; with a switch off the init still runs here, to call today's stubs), then the live NpAuth table (as
// libs.cpp's InitNet_1 does after the switched tables), takes each function by NID and calls it as a title would. While the
// four inits run (twice, into two databases), stderr goes to ./tbp0405-stderr.txt: each must print its one
// "[bc5] exp 0405: <item> port on|off" line exactly once. The database is then dumped (SymbolDatabase::DbgDump, into
// ./tbp0405-dump/) and read back: no NID is registered twice, and the record count is the expected one.
//   on:  the ported answers (AnyPS5 4f41f4c37 / shadPS4 60c42b9, see tbp0405-notes.md); the held stubs are not registered;
//        NpAuth's five use the live requests (sync, async, aborted, finished, unknown, deleted).
//   off: today's answers (0, or 0x80550005 where today's stub says "not signed in") with every output left as it was; the
//        held stubs registered as today; the live NpAuth table is today's eight NIDs, without the five.
// Each table's cases follow its own switch, so any mix runs. The final line says on (all four on), off (all four off or
// unset) or mixed; an optional argument "on", "off" or "mixed" must match. No game, GPU, window, sound device, network or
// USB, and no emulator subsystem is started (PRINT_NAME is off by default; LOGF is silenced below).
// Prints one line per case and finally "tbp0405: on|off|mixed N of N; end"; exit 0 only then. A watchdog ends a hang after
// 60 s with a FAIL line. Run it in a fresh directory: it writes ./tbp0405-stderr.txt and ./tbp0405-dump/.
// Build: build0401.py ... src/libs/libNp.cpp=<out>/src/libs/libNp.cpp src/libs/libNet.cpp=<out>/src/libs/libNet.cpp
//        --gate tbp0405.cpp <bin> --like src/libs/libNp.cpp

#include "common/abi.h"
#include "common/logging/log.h"
#include "libs/libs.h"
#include "loader/symbolDatabase.h"

#include <atomic>
#include <chrono>
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <map>
#include <string>
#include <thread>
#include <vector>

#include <fcntl.h>
#include <unistd.h>

namespace Libs {
namespace NpPartner {
LIB_DEFINE(InitNpPartner_1);
} // namespace NpPartner
namespace NpParty {
LIB_DEFINE(InitNpParty_1);
} // namespace NpParty
namespace NpSnsFacebookDialog {
LIB_DEFINE(InitNpSnsFacebookDialog_1);
} // namespace NpSnsFacebookDialog
namespace LibNpAuth {
LIB_DEFINE(InitNet_1_NpAuth); // the live NpAuth table, libNet.cpp
} // namespace LibNpAuth
} // namespace Libs

namespace tbp0405 {

template <typename... A>
using IFn = int (KYTY_SYSV_ABI*)(A...);

constexpr int  kWatchdogSeconds = 60;
constexpr char kStderrFile[]    = "tbp0405-stderr.txt";
constexpr char kDumpDir[]       = "./tbp0405-dump/";
constexpr char kDumpFile[]      = "db.txt";
constexpr int  kNotSignedIn     = static_cast<int>(0x80550005u); // today's NP_NOT_SIGNED_IN (libNp.cpp)

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

void Report(const std::string& name, bool ok, const std::string& info) {
	g_cases++;
	if (ok) {
		g_passed++;
	}
	std::printf("tbp0405: case %d %s: %s (%s)\n", g_cases.load(), name.c_str(), ok ? "ok" : "FAIL", info.c_str());
	std::fflush(stdout);
}

// A case that compares a return value and, optionally, more conditions. A call whose outputs `more` reads is always made
// in its own statement first: the order in which a call's arguments are evaluated is unspecified.
void Rc(const std::string& name, int got, int want, bool more = true, const std::string& info = "") {
	Report(name, got == want && more,
	       Fmt("0x%08x, want 0x%08x%s%s", static_cast<unsigned>(got), static_cast<unsigned>(want), info.empty() ? "" : "; ",
	           info.c_str()));
}

[[noreturn]] void SetupFail(const std::string& what) {
	std::printf("tbp0405: FAIL setup: %s\n", what.c_str());
	std::fflush(stdout);
	std::_Exit(2);
}

void Watchdog() {
	std::this_thread::sleep_for(std::chrono::seconds(kWatchdogSeconds));
	std::printf("tbp0405: FAIL watchdog: case \"%s\" still running after %d s (a hang); %d of %d cases passed before it\n",
	            g_case.load(), kWatchdogSeconds, g_passed.load(), g_cases.load());
	std::fflush(stdout);
	std::_Exit(3);
}

bool SwitchOn(const char* name) { // env_flag.hpp's rule: set, non-empty and not "0"
	const char* e = std::getenv(name);
	return e != nullptr && e[0] != '\0' && std::strcmp(e, "0") != 0;
}

// ---- lookups ----------------------------------------------------------------------------------------------------------
Loader::SymbolDatabase* g_db = nullptr;

bool Has(const char* nid) {
	return g_db->FindByNid(nid, Loader::SymbolType::Func) != nullptr;
}

template <typename F>
F Fn(const char* nid) {
	const auto* r = g_db->FindByNid(nid, Loader::SymbolType::Func);
	if (r == nullptr || r->vaddr == 0) {
		SetupFail(Fmt("%s is not registered", nid));
	}
	return reinterpret_cast<F>(r->vaddr);
}

// "absent"/"present" for a list of NIDs: the case passes when every one is as wanted.
void Registered(const std::string& name, const std::vector<const char*>& nids, bool want_present) {
	std::string wrong;
	for (const char* nid: nids) {
		if (Has(nid) != want_present) {
			wrong += std::string(" ") + nid;
		}
	}
	Report(name, wrong.empty(),
	       wrong.empty() ? Fmt("%zu NIDs %s", nids.size(), want_present ? "registered" : "not registered")
	                     : (want_present ? "missing:" : "registered:") + wrong);
}

// A guest buffer filled with 0x5A, to see whether (and how far) a call wrote into it.
struct Box {
	alignas(8) uint8_t b[4112];
	Box() { Reset(); }
	void Reset() { std::memset(b, 0x5A, sizeof(b)); }
	[[nodiscard]] bool Untouched() const { return ZeroUpTo(0); }
	// The first n bytes are 0 and the rest is still 0x5A.
	[[nodiscard]] bool ZeroUpTo(size_t n) const {
		for (size_t i = 0; i < sizeof(b); i++) {
			if (b[i] != (i < n ? 0 : 0x5A)) {
				return false;
			}
		}
		return true;
	}
};

// =====================================================================================================================
// NpAuth: the dead table's five, in the live table (libNet.cpp) when KYTY_BC5_LOAD_NPAUTH is on
// =====================================================================================================================
const std::vector<const char*> kAuthFive = {"KxGkOrQJTqY", "qAUXQ9GdWp8", "uaB-LoJqHis", "CocbHVIKPE8", "PM3IZCw-7m0"};
const std::vector<const char*> kAuthLive = {"6bwFkosYRQg", "N+mr7GjTvr8", "H8wG9Bk-nPc", "cE7wIsqXdZ8",
                                            "SK-S7daqJSE", "gjSyfzSsDcE", "KI4dHLlTNl0", "RdsFVsgSpZY"};

void CaseNpAuth(bool on) {
	g_case                  = "npauth";
	const auto create       = Fn<IFn<>>("6bwFkosYRQg");
	const auto create_async = Fn<IFn<const void*>>("N+mr7GjTvr8");
	const auto delete_req   = Fn<IFn<int>>("H8wG9Bk-nPc");
	const auto abort_req    = Fn<IFn<int>>("cE7wIsqXdZ8");
	const auto poll         = Fn<IFn<int, int*>>("gjSyfzSsDcE");
	const auto code_v3      = Fn<IFn<int, const void*, void*, int*>>("KI4dHLlTNl0");
	constexpr int      kInvalid   = static_cast<int>(0x80550301u);
	constexpr int      kAborted   = static_cast<int>(0x80550304u);
	constexpr int      kNotFound  = static_cast<int>(0x80550306u);
	constexpr int      kInvalidId = static_cast<int>(0x80550307u);
	constexpr int      kSignedOut = static_cast<int>(0x80550006u);
	constexpr int      kUnknown   = 0x7FFF0001; // no live request has this id
	constexpr uint32_t k1s        = 1000000;
	constexpr uint32_t k10s       = 10000000;
	constexpr size_t   kCodeSize  = 136;  // what the live V3 call clears (libNet.cpp NpAuthGetAuthorizationCodeV3)
	constexpr size_t   kTokenSize = 4104; // likewise (NpAuthGetIdTokenV3)

	alignas(8) uint8_t async_param[0x18] = {0x18};
	alignas(8) uint8_t param[0x28]       = {0x28};
	std::vector<int>   requests;
	auto               make = [&](bool async) {
        const int id = async ? create_async(async_param) : create();
        if (id <= 0) {
            SetupFail(Fmt("the live sceNpAuthCreate%sRequest gave 0x%08x", async ? "Async" : "", static_cast<unsigned>(id)));
        }
        requests.push_back(id);
        return id;
	};
	Box out;
	int r = 0;

	if (on) {
		Registered("npauth: the five are in the live table", kAuthFive, true);
		Registered("npauth: the live eight are still there", kAuthLive, true);
		const auto code        = Fn<IFn<int, const void*, void*>>("KxGkOrQJTqY");
		const auto code_a      = Fn<IFn<int, const void*, void*, int*>>("qAUXQ9GdWp8");
		const auto token       = Fn<IFn<int, const void*, void*>>("uaB-LoJqHis");
		const auto token_a     = Fn<IFn<int, const void*, void*>>("CocbHVIKPE8");
		const auto set_timeout = Fn<IFn<int, int32_t, uint32_t, uint32_t, uint32_t, uint32_t>>("PM3IZCw-7m0");
		int        issuer      = 0x5A5A5A5A;

		const int sync1 = make(false);
		r               = code(sync1, nullptr, out.b);
		Rc("npauth: GetAuthorizationCode(null parameter)", r, kInvalid, out.Untouched());
		Rc("npauth: GetAuthorizationCode(null output)", code(sync1, param, nullptr), kInvalid);
		r = code(kUnknown, param, out.b);
		Rc("npauth: GetAuthorizationCode, unknown request (the live V3 clears the output first)", r, kNotFound,
		   out.ZeroUpTo(kCodeSize));
		out.Reset();
		r = code(sync1, param, out.b);
		Rc("npauth: GetAuthorizationCode, synchronous request: signed out", r, kSignedOut, out.ZeroUpTo(kCodeSize));
		r = code(sync1, param, out.b);
		Rc("npauth: GetAuthorizationCode, the same request again (finished)", r, kInvalid);

		const int sync2 = make(false);
		out.Reset();
		r = code_a(sync2, nullptr, out.b, &issuer);
		Rc("npauth: GetAuthorizationCodeA(null parameter)", r, kInvalid, out.Untouched() && issuer == 0x5A5A5A5A);
		r = code_a(sync2, param, out.b, &issuer);
		Rc("npauth: GetAuthorizationCodeA, synchronous request: signed out, issuer 0", r, kSignedOut,
		   out.ZeroUpTo(kCodeSize) && issuer == 0, Fmt("issuer %d", issuer));

		const int sync3 = make(false);
		out.Reset();
		r = token(sync3, nullptr, out.b);
		Rc("npauth: GetIdToken(null parameter)", r, kInvalid, out.Untouched());
		r = token(sync3, param, out.b);
		Rc("npauth: GetIdToken, synchronous request: signed out", r, kSignedOut, out.ZeroUpTo(kTokenSize));

		const int async1 = make(true);
		Rc("npauth: GetIdTokenA(null output)", token_a(async1, param, nullptr), kInvalid);
		int result = 0x5A5A5A5A;
		r          = poll(async1, &result);
		Rc("npauth: the live PollAsync before the request starts: INVALID_ID", r, kInvalidId, result == 0x5A5A5A5A);
		out.Reset();
		r = token_a(async1, param, out.b);
		Rc("npauth: GetIdTokenA, asynchronous request: 0 (the result goes to the poll)", r, 0, out.ZeroUpTo(kTokenSize));
		r = poll(async1, &result);
		Rc("npauth: the live PollAsync after it: finished, signed out", r, 0, result == kSignedOut,
		   Fmt("result 0x%08x", static_cast<unsigned>(result)));

		const int sync4 = make(false);
		Rc("npauth: the live AbortRequest", abort_req(sync4), 0);
		r = code_a(sync4, param, out.b, &issuer);
		Rc("npauth: GetAuthorizationCodeA on the aborted request", r, kAborted);

		const int sync5 = make(false);
		Rc("npauth: SetTimeout all five 0", set_timeout(sync5, 0, 0, 0, 0, 0), kInvalid);
		Rc("npauth: SetTimeout retry -1", set_timeout(sync5, -1, k1s, 0, 0, 0), kInvalid);
		Rc("npauth: SetTimeout resolve 999999 us", set_timeout(sync5, 0, k1s - 1, 0, 0, 0), kInvalid);
		Rc("npauth: SetTimeout connect 9999999 us", set_timeout(sync5, 0, 0, k10s - 1, 0, 0), kInvalid);
		Rc("npauth: SetTimeout send 9999999 us", set_timeout(sync5, 0, 0, 0, k10s - 1, 0), kInvalid);
		Rc("npauth: SetTimeout receive 9999999 us", set_timeout(sync5, 0, 0, 0, 0, k10s - 1), kInvalid);
		Rc("npauth: SetTimeout retry 1 only", set_timeout(sync5, 1, 0, 0, 0, 0), 0);
		Rc("npauth: SetTimeout the minimums (1 s, 10 s, 10 s, 10 s)", set_timeout(sync5, 0, k1s, k10s, k10s, k10s), 0);
		Rc("npauth: SetTimeout on a finished request (still known)", set_timeout(sync1, 2, 0, 0, 0, 0), 0);
		Rc("npauth: SetTimeout good values, unknown request", set_timeout(kUnknown, 1, 0, 0, 0, 0), kNotFound);
		Rc("npauth: SetTimeout bad values, unknown request (values checked first)", set_timeout(kUnknown, 0, 0, 0, 0, 0),
		   kInvalid);
		Rc("npauth: the live DeleteRequest", delete_req(sync5), 0);
		Rc("npauth: SetTimeout on the deleted request", set_timeout(sync5, 1, 0, 0, 0, 0), kNotFound);
		requests.pop_back(); // sync5 is gone
	} else {
		Registered("npauth: the five are not in the live table (today's)", kAuthFive, false);
		Registered("npauth: the live eight are there (today's)", kAuthLive, true);
		const int sync1  = make(false);
		const int async1 = make(true);
		int       issuer = 0x5A5A5A5A;
		r                = code_v3(sync1, param, out.b, &issuer);
		Rc("npauth: the live GetAuthorizationCodeV3 (today's: signed out, output cleared, issuer 0)", r, kSignedOut,
		   out.ZeroUpTo(kCodeSize) && issuer == 0);
		int result = 0x5A5A5A5A;
		r          = poll(async1, &result);
		Rc("npauth: the live PollAsync before the request starts (today's INVALID_ID)", r, kInvalidId, result == 0x5A5A5A5A);
	}
	r = 0;
	for (const int id: requests) {
		r |= delete_req(id);
	}
	Rc(Fmt("npauth: the live DeleteRequest of the other %zu requests", requests.size()), r, 0);
}

// =====================================================================================================================
// NpPartner001: 4 NIDs; Initialize, Terminate and HasEAAccessSubscription ported, pQfYTZHznMc held (unregistered when on)
// =====================================================================================================================
void CaseNpPartner(bool on) {
	g_case          = "nppartner";
	const auto init = Fn<IFn<>>("7CxI50-xlCk");
	const auto term = Fn<IFn<>>("pMxXhNozUX8");
	const auto has  = Fn<IFn<int, bool*>>("+OnbUs1CV0M");
	constexpr int kNotInit = static_cast<int>(0x819D0001u);
	constexpr int kInvalid = static_cast<int>(0x819D0002u);
	Box           flag;
	auto*         flag_p = reinterpret_cast<bool*>(flag.b);
	int           r      = 0;

	if (on) {
		Registered("nppartner: held pQfYTZHznMc not registered", {"pQfYTZHznMc"}, false);
		r = has(1000, flag_p);
		Rc("nppartner: HasEAAccessSubscription before Initialize", r, kNotInit, flag.Untouched());
		Rc("nppartner: Terminate before Initialize", term(), kNotInit);
		Rc("nppartner: Initialize", init(), 0);
		Rc("nppartner: Initialize again", init(), 0);
		Rc("nppartner: HasEAAccessSubscription(null)", has(1000, nullptr), kInvalid);
		r = has(1000, flag_p);
		Rc("nppartner: HasEAAccessSubscription", r, 0, flag.b[0] == 0 && flag.b[1] == 0x5A,
		   Fmt("byte 0x%02x", static_cast<unsigned>(flag.b[0])));
		Rc("nppartner: Terminate", term(), 0);
		Rc("nppartner: Terminate again", term(), kNotInit);
		Box after;
		r = has(1000, reinterpret_cast<bool*>(after.b));
		Rc("nppartner: HasEAAccessSubscription after Terminate", r, kNotInit, after.Untouched());
	} else {
		r = has(1000, flag_p);
		Rc("nppartner: HasEAAccessSubscription before Initialize (today's 0, nothing written)", r, 0, flag.Untouched());
		Rc("nppartner: Terminate before Initialize (today's 0)", term(), 0);
		Rc("nppartner: Initialize (today's 0)", init(), 0);
		r = has(1000, flag_p);
		Rc("nppartner: HasEAAccessSubscription (today's 0, nothing written)", r, 0, flag.Untouched());
		Rc("nppartner: pQfYTZHznMc (registered, today's 0)", Fn<IFn<>>("pQfYTZHznMc")(), 0);
		Rc("nppartner: Terminate (today's 0)", term(), 0);
	}
}

// =====================================================================================================================
// NpParty: 26 NIDs; 15 ported, 11 held (unregistered when on)
// =====================================================================================================================
const std::vector<const char*> kPartyHeld = {"nOZRy-slBoA", "XQSUbbnpPBA", "o7grRhiGHYI", "-lc6XZnQXvM",
                                             "RXNCDw2GDEg", "J8jAi-tfJHc", "zo4G5WWYpKg", "nazKyHygHhY",
                                             "-MFiL7hEnPE", "yARHEYLajs0", "zQ7gIvt11Pc"};

void CaseNpParty(bool on) {
	g_case               = "npparty";
	const auto check_cb  = Fn<IFn<>>("3e4k2mzLkmc");
	const auto get_id    = Fn<IFn<void*>>("DRA3ay-1DFQ");
	const auto member    = Fn<IFn<uint16_t, void*>>("F1P+-wpxQow");
	const auto member_a  = Fn<IFn<uint16_t, void*>>("v2RYVGrJDkM");
	const auto members   = Fn<IFn<void*>>("T2UOKf00ZN0");
	const auto members_a = Fn<IFn<void*>>("TaNw7W25QJw");
	const auto session   = Fn<IFn<uint16_t, void*>>("4gOMfNYzllw");
	const auto voice     = Fn<IFn<uint16_t, uint16_t, uint8_t*>>("EKi1jx59SP4");
	const auto get_state = Fn<IFn<uint16_t*>>("aEzKdJzATZ0");
	const auto as_user_a = Fn<IFn<int32_t, uint16_t*>>("EjyAI+QNgFw");
	const auto init      = Fn<IFn<const void*>>("lhYCTQmBkds");
	const auto handler   = Fn<IFn<const void*, void*>>("kA88gbv71ao");
	const auto handler_a = Fn<IFn<const void*, void*>>("+v4fVHMwFWc");
	const auto send      = Fn<IFn<const void*>>("U6VdUe-PNAY");
	const auto term      = Fn<IFn<>>("oLYkibiHqRA");
	constexpr int kAlready = static_cast<int>(0x80552502u);
	constexpr int kNotInit = static_cast<int>(0x80552503u);
	constexpr int kInvalid = static_cast<int>(0x80552504u);
	constexpr int kNoParty = static_cast<int>(0x80552506u);
	alignas(8) uint8_t init_param[0x20] = {};
	alignas(8) uint8_t handlers[0x40]   = {};
	Box                out;
	uint16_t           state = 0x5A5A;
	int                r     = 0;

	if (on) {
		Registered("npparty: the 11 held not registered", kPartyHeld, false);
		r = get_state(&state);
		Rc("npparty: GetState before Initialize", r, kNotInit, state == 0x5A5A);
		Rc("npparty: CheckCallback before Initialize", check_cb(), kNotInit);
		r = get_id(out.b);
		Rc("npparty: GetId before Initialize", r, kNotInit, out.Untouched());
		r = as_user_a(-1, &state);
		Rc("npparty: GetStateAsUserA(-1) before Initialize (NOT_INITIALIZED first)", r, kNotInit, state == 0x5A5A);
		Rc("npparty: RegisterHandlerA before Initialize", handler_a(handlers, nullptr), kNotInit);
		Rc("npparty: Terminate before Initialize", term(), kNotInit);
		Rc("npparty: Initialize(null)", init(nullptr), kInvalid);
		Rc("npparty: Initialize", init(init_param), 0);
		Rc("npparty: Initialize again", init(init_param), kAlready);
		Rc("npparty: CheckCallback", check_cb(), 0);
		Rc("npparty: GetState(null)", get_state(nullptr), kInvalid);
		r = get_state(&state);
		Rc("npparty: GetState", r, 0, state == 2, Fmt("state %u", static_cast<unsigned>(state)));
		state = 0x5A5A;
		r     = as_user_a(-1, &state);
		Rc("npparty: GetStateAsUserA(-1)", r, kInvalid, state == 0x5A5A);
		r = as_user_a(1000, &state);
		Rc("npparty: GetStateAsUserA(1000)", r, 0, state == 2, Fmt("state %u", static_cast<unsigned>(state)));
		Rc("npparty: GetStateAsUserA(1000, null)", as_user_a(1000, nullptr), kInvalid);
		Rc("npparty: GetId(null)", get_id(nullptr), kInvalid);
		r = get_id(out.b);
		Rc("npparty: GetId", r, kNoParty, out.Untouched());
		r = member(0, out.b);
		Rc("npparty: GetMemberInfo", r, kNoParty, out.Untouched());
		r = member_a(0, out.b);
		Rc("npparty: GetMemberInfoA", r, kNoParty, out.Untouched());
		Rc("npparty: GetMemberInfoA(null)", member_a(0, nullptr), kInvalid);
		r = members(out.b);
		Rc("npparty: GetMembers", r, kNoParty, out.Untouched());
		r = members_a(out.b);
		Rc("npparty: GetMembersA", r, kNoParty, out.Untouched());
		r = session(0, out.b);
		Rc("npparty: GetMemberSessionInfo", r, kNoParty, out.Untouched());
		r = voice(0, 0, out.b);
		Rc("npparty: GetMemberVoiceInfo", r, kNoParty, out.Untouched());
		Rc("npparty: GetMemberVoiceInfo(null)", voice(0, 0, nullptr), kInvalid);
		r = send(out.b);
		Rc("npparty: SendBinaryMessage", r, kNoParty, out.Untouched());
		Rc("npparty: RegisterHandler(null)", handler(nullptr, nullptr), kInvalid);
		Rc("npparty: RegisterHandler", handler(handlers, nullptr), 0);
		r = handler_a(handlers, out.b);
		Rc("npparty: RegisterHandlerA", r, 0, out.Untouched());
		Rc("npparty: Terminate", term(), 0);
		Rc("npparty: Terminate again", term(), kNotInit);
		state = 0x5A5A;
		r     = get_state(&state);
		Rc("npparty: GetState after Terminate", r, kNotInit, state == 0x5A5A);
	} else {
		// Today's stubs: every one of the 26 is registered, gives 0x80550005 and writes nothing.
		Rc("npparty: Initialize (today's)", init(init_param), kNotSignedIn);
		Rc("npparty: CheckCallback (today's)", check_cb(), kNotSignedIn);
		r = get_state(&state);
		Rc("npparty: GetState (today's, nothing written)", r, kNotSignedIn, state == 0x5A5A);
		r = as_user_a(1000, &state);
		Rc("npparty: GetStateAsUserA (today's, nothing written)", r, kNotSignedIn, state == 0x5A5A);
		r = get_id(out.b);
		Rc("npparty: GetId (today's, nothing written)", r, kNotSignedIn, out.Untouched());
		int member_ok = 0;
		member_ok += member(0, out.b) == kNotSignedIn ? 1 : 0;
		member_ok += member_a(0, out.b) == kNotSignedIn ? 1 : 0;
		member_ok += members(out.b) == kNotSignedIn ? 1 : 0;
		member_ok += members_a(out.b) == kNotSignedIn ? 1 : 0;
		member_ok += session(0, out.b) == kNotSignedIn ? 1 : 0;
		member_ok += voice(0, 0, out.b) == kNotSignedIn ? 1 : 0;
		Rc("npparty: GetMemberInfo / A, GetMembers / A, GetMemberSessionInfo, GetMemberVoiceInfo (today's, nothing written)",
		   member_ok, 6, out.Untouched());
		r = send(out.b);
		Rc("npparty: SendBinaryMessage (today's)", r, kNotSignedIn, out.Untouched());
		Rc("npparty: RegisterHandler (today's)", handler(handlers, nullptr), kNotSignedIn);
		Rc("npparty: RegisterHandlerA (today's)", handler_a(handlers, nullptr), kNotSignedIn);
		Registered("npparty: the 11 held registered (today's)", kPartyHeld, true);
		int held_ok = 0;
		for (const char* nid: kPartyHeld) {
			held_ok += Fn<IFn<>>(nid)() == kNotSignedIn ? 1 : 0;
		}
		Rc("npparty: the 11 held exports (today's 0x80550005)", held_ok, 11);
		Rc("npparty: Terminate (today's)", term(), kNotSignedIn);
	}
}

// =====================================================================================================================
// NpSnsFacebookDialog: 1 NID, already matches (both modes: 0)
// =====================================================================================================================
void CaseNpSnsFacebook(bool on) {
	g_case            = "npsnsfacebook";
	const auto update = Fn<IFn<>>("fjV7C8H0Y8k");
	Rc(on ? "npsnsfacebook: UpdateStatus (already matches: status none, 0)" : "npsnsfacebook: UpdateStatus (today's 0)",
	   update(), 0);
}

// ---- the journal lines, and the registration ----------------------------------------------------------------------------
struct Table {
	const char* sw;
	const char* item;
	const char* on_line;
	int         nids_on;  // records the init adds with its switch on
	int         nids_off; // and off
	void (*init)(Loader::SymbolDatabase*);
};
const Table kTables[] = { // the switched tables first, then the live NpAuth table, as libs.cpp loads them
    {"KYTY_BC5_LOAD_NPPARTNER", "nppartner", "[bc5] exp 0405: nppartner port on (items: init subscription)", 3, 4,
     Libs::NpPartner::InitNpPartner_1},
    {"KYTY_BC5_LOAD_NPPARTY", "npparty", "[bc5] exp 0405: npparty port on (items: init state members handler message)", 15,
     26, Libs::NpParty::InitNpParty_1},
    {"KYTY_BC5_LOAD_NPSNSFACEBOOK", "npsnsfacebook",
     "[bc5] exp 0405: npsnsfacebook port on (items: none, UpdateStatus already matches)", 1, 1,
     Libs::NpSnsFacebookDialog::InitNpSnsFacebookDialog_1},
    {"KYTY_BC5_LOAD_NPAUTH", "npauth", "[bc5] exp 0405: npauth port on (items: getters settimeout)", 13, 8,
     Libs::LibNpAuth::InitNet_1_NpAuth},
};

// Registers the four into db and again into db2 with stderr in ./tbp0405-stderr.txt, then checks the lines.
void RegisterAndCheckLines(Loader::SymbolDatabase* db, Loader::SymbolDatabase* db2) {
	g_case = "init: registration";
	std::fflush(stderr);
	const int saved_err = dup(2);
	const int fd        = open(kStderrFile, O_WRONLY | O_CREAT | O_TRUNC, 0644);
	if (saved_err < 0 || fd < 0 || dup2(fd, 2) < 0) {
		SetupFail(Fmt("cannot send stderr to ./%s", kStderrFile));
	}
	close(fd);
	for (const auto& t: kTables) {
		t.init(db);
	}
	for (const auto& t: kTables) { // a second registration: each switch is read once, so no second line
		t.init(db2);
	}
	std::fflush(stderr);
	if (dup2(saved_err, 2) < 0) {
		SetupFail("cannot give stderr back");
	}
	close(saved_err);

	std::vector<std::string> lines;
	std::ifstream            in(kStderrFile);
	for (std::string line; std::getline(in, line);) {
		if (!line.empty() && line.back() == '\r') {
			line.pop_back();
		}
		if (line.rfind("[bc5] exp 0405:", 0) == 0) {
			lines.push_back(line);
			std::printf("tbp0405: info stderr: %s\n", line.c_str());
		}
	}
	bool        ok = lines.size() == std::size(kTables);
	std::string info;
	for (const auto& t: kTables) {
		const std::string want = SwitchOn(t.sw) ? t.on_line : Fmt("[bc5] exp 0405: %s port off", t.item);
		int               n    = 0;
		for (const auto& l: lines) {
			n += l == want ? 1 : 0;
		}
		ok = ok && n == 1;
		info += Fmt("%s%s x%d", info.empty() ? "" : ", ", t.item, n);
	}
	Report("journal: one line per table, read once", ok, Fmt("%zu lines; %s", lines.size(), info.c_str()));
}

// The database's records, read back from SymbolDatabase::DbgDump: every NID once, and the expected number of records.
void CheckNoNidTwice(Loader::SymbolDatabase* db) {
	g_case = "registration: dump";
	db->DbgDump(kDumpDir, kDumpFile);
	std::ifstream              in(std::string(kDumpDir) + kDumpFile);
	std::map<std::string, int> count;
	int                        records = 0;
	for (std::string line; std::getline(in, line);) {
		if (!line.empty() && line.back() == '\r') {
			line.pop_back();
		}
		const auto sp = line.find(' ');
		if (sp == std::string::npos) {
			continue;
		}
		const std::string name = line.substr(sp + 1);
		count[name.substr(0, name.find('['))]++;
		records++;
	}
	int want = 0;
	for (const auto& t: kTables) {
		want += SwitchOn(t.sw) ? t.nids_on : t.nids_off;
	}
	std::string twice;
	for (const auto& [nid, n]: count) {
		if (n != 1) {
			twice += Fmt(" %s x%d", nid.c_str(), n);
		}
	}
	Report("registration: no NID registered twice, the expected number of records", twice.empty() && records == want,
	       Fmt("%d records, want %d%s%s", records, want, twice.empty() ? "" : "; twice:", twice.c_str()));
}

} // namespace tbp0405

int main(int argc, char** argv) {
	using namespace tbp0405;
	const bool  auth    = SwitchOn("KYTY_BC5_LOAD_NPAUTH");
	const bool  partner = SwitchOn("KYTY_BC5_LOAD_NPPARTNER");
	const bool  party   = SwitchOn("KYTY_BC5_LOAD_NPPARTY");
	const bool  fb      = SwitchOn("KYTY_BC5_LOAD_NPSNSFACEBOOK");
	const char* mode    = auth && partner && party && fb ? "on" : (!auth && !partner && !party && !fb ? "off" : "mixed");
	if (argc > 2 || (argc == 2 && std::strcmp(argv[1], mode) != 0)) {
		std::printf("tbp0405: the switches (npauth %d, nppartner %d, npparty %d, npsnsfacebook %d: %s) do not match the argument "
		            "%s\n",
		            auth, partner, party, fb, mode, argc == 2 ? argv[1] : "(too many)");
		return 2;
	}
	std::printf("tbp0405: switches npauth %d, nppartner %d, npparty %d, npsnsfacebook %d: %s\n", auth, partner, party, fb, mode);
	std::fflush(stdout);
	::Log::Bc5SetLogging(false); // the live NpAuth table's LOGF lines stay off stdout; no subsystem is started
	std::thread(Watchdog).detach();

	static Loader::SymbolDatabase db;
	static Loader::SymbolDatabase db2;
	RegisterAndCheckLines(&db, &db2);
	g_db = &db;
	CheckNoNidTwice(&db);

	CaseNpAuth(auth);
	CaseNpPartner(partner);
	CaseNpParty(party);
	CaseNpSnsFacebook(fb);

	const int n = g_cases.load();
	const int p = g_passed.load();
	if (p != n) {
		std::printf("tbp0405: %s %d of %d passed; FAIL\n", mode, p, n);
		std::fflush(stdout);
		std::_Exit(1);
	}
	std::printf("tbp0405: %s %d of %d; end\n", mode, p, n);
	std::fflush(stdout);
	std::_Exit(0);
}
