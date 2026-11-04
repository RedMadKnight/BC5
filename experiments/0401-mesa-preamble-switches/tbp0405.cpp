// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0405 (series e7 of experiment 0401), tag tbp: the CPU test of mktbp0405.py's ports in src/libs/libNp.cpp
// (exp 0405 decision 4, dead-table batch 2: the NpAuth, NpPartner001, NpParty and NpSnsFacebookDialog tables), behind
// KYTY_BC5_LOAD_NPAUTH, KYTY_BC5_LOAD_NPPARTNER, KYTY_BC5_LOAD_NPPARTY and KYTY_BC5_LOAD_NPSNSFACEBOOK. It registers the four
// tables into its own Loader::SymbolDatabase by calling their LIB_DEFINEs (as libs.cpp does when a switch is on; with a
// switch off the init still runs here, to call today's stubs), then the live NpAuth table of libNet.cpp
// (LibNpAuth::InitNet_1_NpAuth, which libs.cpp's InitNet_1 loads after the switched tables), takes each function by NID
// and calls it as a title would. While the four inits run (twice, into two databases), stderr goes to
// ./tbp0405-stderr.txt: each table must print its one "[bc5] exp 0405: <table> port on|off" line exactly once.
//   on:  the ported answers (AnyPS5 4f41f4c37 / shadPS4 60c42b9, see tbp0405-notes.md); the held exports keep today's
//        answer; NpAuth's SetTimeout gets a request the live table made, and a held getter leaves a live asynchronous
//        request as it was (the live poll still says "not started").
//   off: today's answers (0, or 0x80550005 where today's stub says "not signed in") with every output left as it was.
// Each table's cases follow its own switch, so any mix runs. The final line says on (all four on), off (all four off or
// unset) or mixed; an optional argument "on", "off" or "mixed" must match. No game, GPU, window, sound device, network or
// USB, and no emulator subsystem is started (PRINT_NAME is off by default; LOGF is silenced below).
// Prints one line per case and finally "tbp0405: on|off|mixed N of N; end"; exit 0 only then. A watchdog ends a hang after
// 60 s with a FAIL line. Run it in a fresh directory: it writes ./tbp0405-stderr.txt.
// Build: build0401.py ... src/libs/libNp.cpp=<out>/src/libs/libNp.cpp --gate tbp0405.cpp <bin> --like src/libs/libNp.cpp

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
#include <string>
#include <thread>
#include <vector>

#include <fcntl.h>
#include <unistd.h>

namespace Libs {
namespace NpAuth {
LIB_DEFINE(InitNpAuth_1);
} // namespace NpAuth
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

// A case that compares a return value and, optionally, more conditions.
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

template <typename F>
F Fn(const char* nid) {
	const auto* r = g_db->FindByNid(nid, Loader::SymbolType::Func);
	if (r == nullptr || r->vaddr == 0) {
		SetupFail(Fmt("%s is not registered", nid));
	}
	return reinterpret_cast<F>(r->vaddr);
}

// A guest buffer filled with 0x5A, to see whether a call wrote into it.
struct Box {
	alignas(8) uint8_t b[4112];
	Box() { std::memset(b, 0x5A, sizeof(b)); }
	[[nodiscard]] bool Untouched() const {
		for (uint8_t v: b) {
			if (v != 0x5A) {
				return false;
			}
		}
		return true;
	}
};

// =====================================================================================================================
// NpAuth: 5 NIDs; SetTimeout's argument checks ported, its request lookup and the four getters held
// =====================================================================================================================
constexpr const char* kAuthNids[] = {"KxGkOrQJTqY", "qAUXQ9GdWp8", "uaB-LoJqHis", "CocbHVIKPE8", "PM3IZCw-7m0"};

void CaseNpAuth(bool on) {
	g_case                 = "npauth";
	const auto set_timeout = Fn<IFn<int, int32_t, uint32_t, uint32_t, uint32_t, uint32_t>>("PM3IZCw-7m0");
	const auto code        = Fn<IFn<int, const void*, void*>>("KxGkOrQJTqY");
	const auto code_a      = Fn<IFn<int, const void*, void*, int*>>("qAUXQ9GdWp8");
	const auto token       = Fn<IFn<int, const void*, void*>>("uaB-LoJqHis");
	const auto token_a     = Fn<IFn<int, const void*, void*>>("CocbHVIKPE8");
	// the live table (libNet.cpp LibNpAuth)
	const auto create       = Fn<IFn<>>("6bwFkosYRQg");
	const auto create_async = Fn<IFn<const void*>>("N+mr7GjTvr8");
	const auto delete_req   = Fn<IFn<int>>("H8wG9Bk-nPc");
	const auto poll         = Fn<IFn<int, int*>>("gjSyfzSsDcE");

	alignas(8) uint8_t async_param[0x18] = {0x18};
	const int          req               = create();
	const int          async_req         = create_async(async_param);
	if (req <= 0 || async_req <= 0) {
		SetupFail(Fmt("the live sceNpAuthCreateRequest / CreateAsyncRequest gave 0x%08x / 0x%08x", static_cast<unsigned>(req),
		              static_cast<unsigned>(async_req)));
	}
	constexpr int kInvalid = static_cast<int>(0x80550301u);
	constexpr int kUnknown = 0x7FFF0001; // no live request has this id
	constexpr uint32_t k1s  = 1000000;
	constexpr uint32_t k10s = 10000000;

	if (on) {
		Rc("npauth: SetTimeout all five 0", set_timeout(req, 0, 0, 0, 0, 0), kInvalid);
		Rc("npauth: SetTimeout retry -1", set_timeout(req, -1, k1s, 0, 0, 0), kInvalid);
		Rc("npauth: SetTimeout resolve 999999 us", set_timeout(req, 0, k1s - 1, 0, 0, 0), kInvalid);
		Rc("npauth: SetTimeout connect 9999999 us", set_timeout(req, 0, 0, k10s - 1, 0, 0), kInvalid);
		Rc("npauth: SetTimeout send 9999999 us", set_timeout(req, 0, 0, 0, k10s - 1, 0), kInvalid);
		Rc("npauth: SetTimeout receive 9999999 us", set_timeout(req, 0, 0, 0, 0, k10s - 1), kInvalid);
		Rc("npauth: SetTimeout retry 1 only", set_timeout(req, 1, 0, 0, 0, 0), 0);
		Rc("npauth: SetTimeout the minimums (1 s, 10 s, 10 s, 10 s)", set_timeout(req, 0, k1s, k10s, k10s, k10s), 0);
		Rc("npauth: SetTimeout on the live async request", set_timeout(async_req, 3, 0, 0, 0, 0), 0);
		Rc("npauth: SetTimeout bad values, unknown request (values checked first)", set_timeout(kUnknown, 0, 0, 0, 0, 0),
		   kInvalid);
		Rc("npauth: SetTimeout good values, unknown request (lookup held: today's 0)", set_timeout(kUnknown, 1, 0, 0, 0, 0), 0);
	} else {
		Rc("npauth: SetTimeout all five 0 (today's 0)", set_timeout(req, 0, 0, 0, 0, 0), 0);
		Rc("npauth: SetTimeout retry -1 (today's 0)", set_timeout(req, -1, k1s, 0, 0, 0), 0);
		Rc("npauth: SetTimeout good values (today's 0)", set_timeout(req, 1, 0, 0, 0, 0), 0);
	}

	// The four getters are held in both modes: today's 0x80550005, nothing written, the live request left as it was.
	// (Every call whose outputs a case checks is made in its own statement first: argument order is unspecified.)
	alignas(8) uint8_t param[0x28] = {0x28};
	Box                out;
	int                issuer = 0x5A5A5A5A;
	int                r      = code(req, param, out.b);
	Rc("npauth: GetAuthorizationCode (held: today's answer)", r, kNotSignedIn, out.Untouched());
	r = code_a(req, param, out.b, &issuer);
	Rc("npauth: GetAuthorizationCodeA (held: today's answer)", r, kNotSignedIn, out.Untouched() && issuer == 0x5A5A5A5A);
	r = token(req, param, out.b);
	Rc("npauth: GetIdToken (held: today's answer)", r, kNotSignedIn, out.Untouched());
	r = token_a(req, param, out.b);
	Rc("npauth: GetIdTokenA (held: today's answer)", r, kNotSignedIn, out.Untouched());
	r = code_a(async_req, param, out.b, &issuer);
	Rc("npauth: GetAuthorizationCodeA on the live async request (held: today's answer)", r, kNotSignedIn,
	   out.Untouched() && issuer == 0x5A5A5A5A);
	int result = 0x5A5A5A5A;
	r          = poll(async_req, &result);
	Rc("npauth: the live PollAsync after it: not started (INVALID_ID), the live state untouched", r,
	   static_cast<int>(0x80550307u), result == 0x5A5A5A5A);
	r = delete_req(req);
	r |= delete_req(async_req);
	Rc("npauth: the live DeleteRequest of both requests", r, 0);

	// No NID of the dead table is registered by the live table (a database that holds only the live table).
	Loader::SymbolDatabase live_only;
	Libs::LibNpAuth::InitNet_1_NpAuth(&live_only);
	std::string shared;
	for (const char* nid: kAuthNids) {
		if (live_only.FindByNid(nid, Loader::SymbolType::Func) != nullptr) {
			shared += std::string(" ") + nid;
		}
	}
	const bool live_ok = live_only.FindByNid("6bwFkosYRQg", Loader::SymbolType::Func) != nullptr;
	Report("npauth: no NID of the table is in the live NpAuth table", shared.empty() && live_ok,
	       shared.empty() ? "5 NIDs, none live; the live table holds CreateRequest" : "shared:" + shared);
}

// =====================================================================================================================
// NpPartner001: 4 NIDs; Initialize, Terminate and HasEAAccessSubscription ported, pQfYTZHznMc held
// =====================================================================================================================
void CaseNpPartner(bool on) {
	g_case            = "nppartner";
	const auto init   = Fn<IFn<>>("7CxI50-xlCk");
	const auto term   = Fn<IFn<>>("pMxXhNozUX8");
	const auto has    = Fn<IFn<int, bool*>>("+OnbUs1CV0M");
	const auto abort_ = Fn<IFn<>>("pQfYTZHznMc");
	constexpr int kNotInit = static_cast<int>(0x819D0001u);
	constexpr int kInvalid = static_cast<int>(0x819D0002u);
	Box           flag;
	auto*         flag_p = reinterpret_cast<bool*>(flag.b);
	int           r      = 0; // a call whose outputs a case checks is made first, in its own statement

	if (on) {
		r = has(1000, flag_p);
		Rc("nppartner: HasEAAccessSubscription before Initialize", r, kNotInit, flag.Untouched());
		Rc("nppartner: Terminate before Initialize", term(), kNotInit);
		Rc("nppartner: Initialize", init(), 0);
		Rc("nppartner: Initialize again", init(), 0);
		Rc("nppartner: HasEAAccessSubscription(null)", has(1000, nullptr), kInvalid);
		r = has(1000, flag_p);
		Rc("nppartner: HasEAAccessSubscription", r, 0, flag.b[0] == 0 && flag.b[1] == 0x5A,
		   Fmt("byte 0x%02x", static_cast<unsigned>(flag.b[0])));
		Rc("nppartner: pQfYTZHznMc (held: today's 0)", abort_(), 0);
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
		Rc("nppartner: pQfYTZHznMc (today's 0)", abort_(), 0);
		Rc("nppartner: Terminate (today's 0)", term(), 0);
	}
}

// =====================================================================================================================
// NpParty: 26 NIDs; 15 ported, 11 held
// =====================================================================================================================
constexpr const char* kPartyHeld[] = {"nOZRy-slBoA", "XQSUbbnpPBA", "o7grRhiGHYI", "-lc6XZnQXvM",
                                      "RXNCDw2GDEg", "J8jAi-tfJHc", "zo4G5WWYpKg", "nazKyHygHhY",
                                      "-MFiL7hEnPE", "yARHEYLajs0", "zQ7gIvt11Pc"};

void CaseNpParty(bool on) {
	g_case                = "npparty";
	const auto check_cb   = Fn<IFn<>>("3e4k2mzLkmc");
	const auto get_id     = Fn<IFn<void*>>("DRA3ay-1DFQ");
	const auto member     = Fn<IFn<uint16_t, void*>>("F1P+-wpxQow");
	const auto member_a   = Fn<IFn<uint16_t, void*>>("v2RYVGrJDkM");
	const auto members    = Fn<IFn<void*>>("T2UOKf00ZN0");
	const auto members_a  = Fn<IFn<void*>>("TaNw7W25QJw");
	const auto session    = Fn<IFn<uint16_t, void*>>("4gOMfNYzllw");
	const auto voice      = Fn<IFn<uint16_t, uint16_t, uint8_t*>>("EKi1jx59SP4");
	const auto get_state  = Fn<IFn<uint16_t*>>("aEzKdJzATZ0");
	const auto as_user_a  = Fn<IFn<int32_t, uint16_t*>>("EjyAI+QNgFw");
	const auto init       = Fn<IFn<const void*>>("lhYCTQmBkds");
	const auto handler    = Fn<IFn<const void*, void*>>("kA88gbv71ao");
	const auto handler_a  = Fn<IFn<const void*, void*>>("+v4fVHMwFWc");
	const auto send       = Fn<IFn<const void*>>("U6VdUe-PNAY");
	const auto term       = Fn<IFn<>>("oLYkibiHqRA");
	constexpr int kAlready  = static_cast<int>(0x80552502u);
	constexpr int kNotInit  = static_cast<int>(0x80552503u);
	constexpr int kInvalid  = static_cast<int>(0x80552504u);
	constexpr int kNoParty  = static_cast<int>(0x80552506u);
	alignas(8) uint8_t init_param[0x20] = {};
	alignas(8) uint8_t handlers[0x40]   = {};
	Box                out;
	uint16_t           state = 0x5A5A;
	int                r     = 0; // a call whose outputs a case checks is made first, in its own statement

	if (on) {
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
		for (const char* nid: kPartyHeld) {
			Rc(Fmt("npparty: held export %s (today's 0x80550005)", nid), Fn<IFn<>>(nid)(), kNotSignedIn);
		}
		Rc("npparty: Terminate", term(), 0);
		Rc("npparty: Terminate again", term(), kNotInit);
		state = 0x5A5A;
		r     = get_state(&state);
		Rc("npparty: GetState after Terminate", r, kNotInit, state == 0x5A5A);
	} else {
		// Today's stubs: every one of the 26 gives 0x80550005 and writes nothing.
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
		int held_ok = 0;
		for (const char* nid: kPartyHeld) {
			held_ok += Fn<IFn<>>(nid)() == kNotSignedIn ? 1 : 0;
		}
		Rc("npparty: the 11 held exports (today's)", held_ok, 11);
		Rc("npparty: Terminate (today's)", term(), kNotSignedIn);
	}
}

// =====================================================================================================================
// NpSnsFacebookDialog: 1 NID, already matches (both modes: 0)
// =====================================================================================================================
void CaseNpSnsFacebook(bool on) {
	g_case             = "npsnsfacebook";
	const auto update  = Fn<IFn<>>("fjV7C8H0Y8k");
	Rc(on ? "npsnsfacebook: UpdateStatus (already matches: status none, 0)" : "npsnsfacebook: UpdateStatus (today's 0)", update(),
	   0);
}

// ---- the journal lines ------------------------------------------------------------------------------------------------
struct Table {
	const char* sw;
	const char* item;
	const char* on_line;
	void (*init)(Loader::SymbolDatabase*);
};
const Table kTables[] = {
    {"KYTY_BC5_LOAD_NPAUTH", "npauth", "[bc5] exp 0405: npauth port on (items: settimeout-arguments)",
     Libs::NpAuth::InitNpAuth_1},
    {"KYTY_BC5_LOAD_NPPARTNER", "nppartner", "[bc5] exp 0405: nppartner port on (items: init subscription)",
     Libs::NpPartner::InitNpPartner_1},
    {"KYTY_BC5_LOAD_NPPARTY", "npparty", "[bc5] exp 0405: npparty port on (items: init state members handler message)",
     Libs::NpParty::InitNpParty_1},
    {"KYTY_BC5_LOAD_NPSNSFACEBOOK", "npsnsfacebook",
     "[bc5] exp 0405: npsnsfacebook port on (items: none, UpdateStatus already matches)",
     Libs::NpSnsFacebookDialog::InitNpSnsFacebookDialog_1},
};

// Registers the four tables into db and again into db2 with stderr in ./tbp0405-stderr.txt, then checks the lines.
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
	RegisterAndCheckLines(&db, &db2); // the switched tables first, as libs.cpp loads them
	g_case = "init: the live NpAuth table";
	Libs::LibNpAuth::InitNet_1_NpAuth(&db); // then the live table, as libs.cpp's InitNet_1 does
	g_db = &db;

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
