// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0405 (series e6 of experiment 0401), tag "fwn": the CPU test of mkfwn0405.py's edits of src/libs/libRtc.cpp,
// libRudp.cpp, network.cpp, libSystemService.cpp and libNpCppWebApi.cpp (notes fwn0405-notes.md), behind one switch:
//   KYTY_BC5_FW_NET (items rtc, rudp, resolver, param400, npwebapi; "1" = all).
// No game, no GPU, no window, no sound device, no network (the resolver cases convert the literal "127.0.0.1", no host
// lookup). The test registers the host's libraries into its own SymbolDatabase (Libs::InitAll, as lib0405.cpp and
// npgate0401.cpp do), takes the functions by NID and calls them as a title would. Every case runs both ways and expects
// the answer of the state its item is in; with an item off the expected answer is today's.
// Cases (one line each; fwn0405-notes.md has the sources):
//   rtc       sceRtcFormatRFC3339: ticks in years 65536, 65537, 75535 and 10000, the last tick of 9999, UINT64_MAX with an
//             eastern zone, a zone of 1440 minutes, tick 0 with a western zone, the epoch, a distant tick (AnyPS5's test
//             vectors of 4dd4ec5ff), a null text, a null tick (now). On a refusal the text is left as it was.
//   rudp      sceRudpSetEventHandler before sceRudpInit, then (after it) with a null and with a real handler.
//   resolver  sceNetResolverStartNtoa("127.0.0.1") with timeouts 0, 1, 999999, 1000000, INT_MAX, -1, retry -1, an
//             unknown resolver with timeouts 1 and 0, and flags 2; the address written or left as it was, the net errno.
//   param400  sceSystemServiceParamGetInt 1, 400 (on: parameter 1's answer; off: 0) and 401 (0 both ways).
//   npwebapi  the five finish entry points libNpCppWebApi.cpp registers (on: 0x80553508; off: 0).
// Build (build0401.py, series e6): --gate fwn0405.cpp <out> --like src/libs/libRtc.cpp, with the five private units
// (src/libs/libRtc.cpp=<it> ... from mkfwn0405.py) in place of the shared ones, linked with every emulator object but
// main.cpp.o.
// usage: run in a fresh directory on the NVMe:
//   KYTY_BC5_FW_NET=1 -> "fwn0405 on";  KYTY_BC5_FW_NET=0 or unset -> "fwn0405 off". An item list ("rtc,param400") is
//   allowed: each case then expects its item's state, and the last line says "mixed". The argument may be left out.
// It unsets KYTY_BC5_INPUT_CONFIG (parameter 1 then answers --console-language, 1 by default) and e5's
// KYTY_BC5_SYSTEMSERVICE_VALUES / KYTY_BC5_SYSTEMSERVICE_PARAMS_7_1000 (parameter 401 then answers today's 0).
// Prints "fwn0405: on|off|mixed N of N; end" and exits 0 only then. A watchdog ends a hang after 60 s with a FAIL line.

#include "common/abi.h"
#include "common/commonSubsystem.h"
#include "common/emulatorConfig.h"
#include "common/logging/log.h"
#include "common/singleton.h"
#include "common/subsystems.h"
#include "common/threads.h"
#include "kernel/memory.h"
#include "kernel/pthread.h"
#include "libs/libs.h"
#include "libs/network.h"
#include "loader/runtimeLinker.h"
#include "loader/symbolDatabase.h"
#include "loader/timer.h"

#include <atomic>
#include <chrono>
#include <climits>
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <thread>

#include <unistd.h>

namespace fwn0405 {

constexpr int kWatchdogSeconds = 60;

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

void Report(const char* name, bool ok, const std::string& info) {
	g_cases++;
	if (ok) {
		g_passed++;
	}
	std::printf("fwn0405: case %d %s: %s (%s)\n", g_cases.load(), name, ok ? "ok" : "FAIL", info.c_str());
	std::fflush(stdout);
}

[[noreturn]] void SetupFail(const std::string& what) {
	std::printf("fwn0405: FAIL setup: %s\n", what.c_str());
	std::fflush(stdout);
	std::_Exit(2);
}

void Watchdog() {
	std::this_thread::sleep_for(std::chrono::seconds(kWatchdogSeconds));
	std::printf("fwn0405: FAIL watchdog: case \"%s\" still running after %d s (a hang); %d of %d cases passed before it\n",
	            g_case.load(), kWatchdogSeconds, g_passed.load(), g_cases.load());
	std::fflush(stdout);
	std::_Exit(3);
}

// ---- the switch, read as the units read it ---------------------------------------------------------------------------
constexpr uint32_t kRtc      = 1u;
constexpr uint32_t kRudp     = 2u;
constexpr uint32_t kResolver = 4u;
constexpr uint32_t kParam400 = 8u;
constexpr uint32_t kNpWebApi = 16u;
constexpr uint32_t kAll      = 31u;

uint32_t Items(const char* e) {
	if (e == nullptr || e[0] == '\0' || std::strcmp(e, "0") == 0) {
		return 0;
	}
	static const char* const names[] = {"rtc", "rudp", "resolver", "param400", "npwebapi"};
	uint32_t                 parts   = 0;
	const char*              p       = e;
	for (;;) {
		const char*  comma = std::strchr(p, ',');
		const size_t n     = comma != nullptr ? static_cast<size_t>(comma - p) : std::strlen(p);
		for (uint32_t i = 0; i < 5; i++) {
			if (n == std::strlen(names[i]) && std::strncmp(p, names[i], n) == 0) {
				parts |= 1u << i;
			}
		}
		if (comma == nullptr) {
			break;
		}
		p = comma + 1;
	}
	return parts != 0 ? parts : kAll;
}

uint32_t g_items = 0;

bool On(uint32_t item) {
	return (g_items & item) != 0;
}

// ---- function lookup ------------------------------------------------------------------------------------------------
Loader::SymbolDatabase* g_db = nullptr;

template <typename F>
F Fn(const char* nid, const char* name) {
	const auto* r = g_db->FindByNid(nid, Loader::SymbolType::Func);
	if (r == nullptr || r->vaddr == 0) {
		SetupFail(Fmt("%s (%s) is not registered", name, nid));
	}
	return reinterpret_cast<F>(r->vaddr);
}

std::string Hex(int v) {
	return Fmt("0x%08X", static_cast<unsigned>(v));
}

// =====================================================================================================================
// rtc: sceRtcFormatRFC3339
// =====================================================================================================================
constexpr int kRtcInvalidPointer = static_cast<int>(0x80B50002u);
constexpr int kRtcInvalidValue   = static_cast<int>(0x80B50003u);
constexpr int kRtcInvalidYear    = static_cast<int>(0x80B50008u);

using FormatRFC3339 = int (KYTY_SYSV_ABI*)(char* date_time, const uint64_t* utc, int time_zone_minutes);

// One FormatRFC3339 case: the answer, and the text (an OK answer) or the untouched buffer (an error).
void RtcCase(FormatRFC3339 f, const char* name, const uint64_t* tick, int zone, int want, const char* want_text) {
	g_case = name;
	char text[64];
	std::memset(text, 'x', sizeof(text));
	text[sizeof(text) - 1] = '\0';
	const int  r  = f(text, tick, zone);
	bool       ok = r == want;
	std::string got;
	if (want == 0) {
		ok  = ok && std::strcmp(text, want_text) == 0;
		got = Fmt("\"%s\"", text);
	} else {
		bool untouched = true;
		for (size_t i = 0; i + 1 < sizeof(text); i++) {
			untouched = untouched && text[i] == 'x';
		}
		ok  = ok && untouched;
		got = untouched ? "text untouched" : "text written";
	}
	Report(name, ok,
	       Fmt("%s %s: %s, %s; want %s%s%s", On(kRtc) ? "on" : "off", tick != nullptr ? Fmt("tick %llu", static_cast<unsigned long long>(*tick)).c_str() : "null tick",
	           Hex(r).c_str(), got.c_str(), Hex(want).c_str(), want == 0 ? " " : "", want == 0 ? want_text : ""));
}

void CaseRtc() {
	auto f = Fn<FormatRFC3339>("WJ3rqFwymew", "sceRtcFormatRFC3339");
	// Ticks of AnyPS5 4dd4ec5ff's test (core/libs/tests/GuestRtc.cpp:93-104) and of this file's own arithmetic.
	const uint64_t y65536   = 2068084742400000000ull; // 65536-01-01: the 16-bit year is 0
	const uint64_t y65537   = 2068116364800000000ull; // 65537-01-01: the 16-bit year is 1
	const uint64_t y75535   = 2383622726400000000ull; // 75535-01-01: the 16-bit year is 9999
	const uint64_t y10000   = 315537897600000000ull;  // 10000-01-01
	const uint64_t last9999 = 315537897599999999ull;  // 9999-12-31 23:59:59.999999
	const uint64_t max      = UINT64_MAX;
	const uint64_t epoch    = 62135596800000000ull; // 1970-01-01 (this file's RTC_UNIX_EPOCH_TICKS)
	const uint64_t zero     = 0;
	const uint64_t distant  = 4239646359910459728ull; // 134350-01-17: the 16-bit year is 3278 (AnyPS5's "distant" RFC 2822 vector); today's code refuses it (past 9999), box run of 2026-11-04
	const bool     on       = On(kRtc);

	RtcCase(f, "rtc year 65536, zone 0", &y65536, 0, on ? kRtcInvalidYear : kRtcInvalidValue, "");
	RtcCase(f, "rtc year 65537, zone +60", &y65537, 60, on ? 0 : kRtcInvalidValue, "0001-01-01T01:00:00.00+01:00");
	RtcCase(f, "rtc year 75535, zone -60", &y75535, -60, on ? 0 : kRtcInvalidValue, "9998-12-31T23:00:00.00-01:00");
	RtcCase(f, "rtc year 10000, zone 0", &y10000, 0, on ? kRtcInvalidYear : kRtcInvalidValue, "");
	RtcCase(f, "rtc UINT64_MAX, zone +1", &max, 1, on ? kRtcInvalidValue : 0, "0001-01-01T00:00:59.99+00:01");
	RtcCase(f, "rtc epoch, zone 1440", &epoch, 1440, on ? kRtcInvalidValue : 0, "1970-01-02T00:00:00.00+24:00");
	RtcCase(f, "rtc tick 0, zone -1", &zero, -1, kRtcInvalidValue, "");
	RtcCase(f, "rtc last tick of 9999, zone 0", &last9999, 0, 0, "9999-12-31T23:59:59.99Z");
	RtcCase(f, "rtc epoch, zone +120", &epoch, 120, 0, "1970-01-01T02:00:00.00+02:00");
	RtcCase(f, "rtc distant tick, zone -821", &distant, -821, on ? 0 : kRtcInvalidValue, "3278-01-17T10:44:10.45-13:41");

	{
		g_case          = "rtc null text";
		const int r     = f(nullptr, &epoch, 0);
		Report("rtc null text", r == kRtcInvalidPointer, Fmt("%s; want %s", Hex(r).c_str(), Hex(kRtcInvalidPointer).c_str()));
	}
	{
		g_case = "rtc null tick (now), zone 0";
		char text[64];
		std::memset(text, 'x', sizeof(text));
		const int  r  = f(text, nullptr, 0);
		const bool ok = r == 0 && std::strlen(text) == 23 && text[0] == '2' && text[4] == '-' && text[10] == 'T' && text[22] == 'Z';
		Report("rtc null tick (now), zone 0", ok, Fmt("%s \"%.40s\"; want 0 and \"2YYY-MM-DDTHH:MM:SS.ccZ\"", Hex(r).c_str(), text));
	}
}

// =====================================================================================================================
// rudp: sceRudpSetEventHandler
// =====================================================================================================================
constexpr int kRudpNotInitialized  = static_cast<int>(0x80770001u);
constexpr int kRudpNoEventHandler = static_cast<int>(0x80770022u);

using RudpHandler    = void (KYTY_SYSV_ABI*)(int ctx_id, int event_id, int error_code, void* arg);
using RudpInit       = int (KYTY_SYSV_ABI*)(void* mem_pool, int mem_pool_size);
using RudpSetHandler = int (KYTY_SYSV_ABI*)(RudpHandler handler, void* arg);

void KYTY_SYSV_ABI RudpEvent([[maybe_unused]] int ctx_id, [[maybe_unused]] int event_id, [[maybe_unused]] int error_code,
                             [[maybe_unused]] void* arg) {}

void CaseRudp() {
	auto       init = Fn<RudpInit>("amuBfI-AQc4", "sceRudpInit");
	auto       set  = Fn<RudpSetHandler>("SUEVes8gvmw", "sceRudpSetEventHandler");
	const bool on   = On(kRudp);
	static int arg  = 0;

	g_case       = "rudp SetEventHandler before Init";
	const int r1 = set(RudpEvent, &arg); // nothing else in this process calls sceRudpInit
	Report("rudp SetEventHandler before Init", r1 == (on ? kRudpNotInitialized : 0),
	       Fmt("%s: %s; want %s", on ? "on" : "off", Hex(r1).c_str(), Hex(on ? kRudpNotInitialized : 0).c_str()));

	g_case = "rudp Init";
	alignas(8) static unsigned char pool[0x4000];
	const int ri = init(pool, static_cast<int>(sizeof(pool)));
	if (ri != 0) {
		SetupFail(Fmt("sceRudpInit returned %s", Hex(ri).c_str()));
	}

	g_case       = "rudp SetEventHandler(null) after Init";
	const int r2 = set(nullptr, &arg);
	Report("rudp SetEventHandler(null) after Init", r2 == (on ? kRudpNoEventHandler : 0),
	       Fmt("%s: %s; want %s", on ? "on" : "off", Hex(r2).c_str(), Hex(on ? kRudpNoEventHandler : 0).c_str()));

	g_case       = "rudp SetEventHandler(handler) after Init";
	const int r3 = set(RudpEvent, &arg);
	Report("rudp SetEventHandler(handler) after Init", r3 == 0, Fmt("%s; want 0x00000000", Hex(r3).c_str()));
}

// =====================================================================================================================
// resolver: sceNetResolverStartNtoa
// =====================================================================================================================
constexpr int kNetEinval = static_cast<int>(0x80410116u);
constexpr int kNetEbadf  = static_cast<int>(0x80410109u);

using NetInit           = int (KYTY_SYSV_ABI*)();
using NetErrno          = int* (KYTY_SYSV_ABI*)();
using NetPoolCreate     = int (KYTY_SYSV_ABI*)(const char* name, int size, int flags);
using NetResolverCreate = int (KYTY_SYSV_ABI*)(const char* name, int memid, int flags);
using NetStartNtoa      = int (KYTY_SYSV_ABI*)(int rid, const char* hostname, void* addr, int timeout, int retry, int flags);

void CaseResolver() {
	auto net_init = Fn<NetInit>("Nlev7Lg8k3A", "sceNetInit");
	auto net_errno = Fn<NetErrno>("HQOwnfMGipQ", "sceNetErrnoLoc");
	auto pool_create = Fn<NetPoolCreate>("dgJBaeJnGpo", "sceNetPoolCreate");
	auto resolver_create = Fn<NetResolverCreate>("C4UgDHHPvdw", "sceNetResolverCreate");
	auto ntoa = Fn<NetStartNtoa>("Nd91WaWmG2w", "sceNetResolverStartNtoa");
	const bool on = On(kResolver);

	g_case = "resolver setup";
	if (net_init() != 0) {
		SetupFail("sceNetInit failed");
	}
	const int memid = pool_create("fwn0405", 0x4000, 0);
	if (memid < 0) {
		SetupFail(Fmt("sceNetPoolCreate returned %s", Hex(memid).c_str()));
	}
	const int rid = resolver_create("fwn0405", memid, 0);
	if (rid < 0) {
		SetupFail(Fmt("sceNetResolverCreate returned %s", Hex(rid).c_str()));
	}

	struct Ntoa {
		const char* name;
		int         rid;
		int         timeout;
		int         retry;
		int         flags;
		int         want_on;
		int         want_off;
	};
	const Ntoa cases[] = {
	    {"resolver timeout 0", rid, 0, 0, 0, 0, 0},
	    {"resolver timeout 1", rid, 1, 0, 0, kNetEinval, 0},
	    {"resolver timeout 999999", rid, 999999, 0, 0, kNetEinval, 0},
	    {"resolver timeout 1000000", rid, 1000000, 0, 0, 0, 0},
	    {"resolver timeout INT_MAX", rid, INT_MAX, 0, 0, 0, 0},
	    {"resolver timeout -1", rid, -1, 0, 0, kNetEinval, 0},
	    {"resolver retry -1", rid, 0, -1, 0, kNetEinval, 0},
	    {"resolver unknown resolver, timeout 1", rid + 1000, 1, 0, 0, kNetEinval, kNetEbadf},
	    {"resolver unknown resolver, timeout 0", rid + 1000, 0, 0, 0, kNetEbadf, kNetEbadf},
	    {"resolver flags 2", rid, 0, 0, 2, kNetEinval, kNetEinval},
	};
	for (const auto& c: cases) {
		g_case        = c.name;
		uint8_t addr[4] = {0xAA, 0xAA, 0xAA, 0xAA};
		*net_errno()  = 0;
		const int r   = ntoa(c.rid, "127.0.0.1", addr, c.timeout, c.retry, c.flags);
		const int e   = *net_errno();
		const int want = on ? c.want_on : c.want_off;
		bool      ok   = r == want;
		if (want == 0) {
			ok = ok && addr[0] == 127 && addr[1] == 0 && addr[2] == 0 && addr[3] == 1;
		} else {
			ok = ok && addr[0] == 0xAA && addr[1] == 0xAA && addr[2] == 0xAA && addr[3] == 0xAA && e == want;
		}
		Report(c.name, ok,
		       Fmt("%s: %s, address %u.%u.%u.%u, net errno %s; want %s%s", on ? "on" : "off", Hex(r).c_str(), addr[0], addr[1],
		           addr[2], addr[3], Hex(e).c_str(), Hex(want).c_str(),
		           want == 0 ? " and 127.0.0.1" : " with the address untouched and the errno set"));
	}
}

// =====================================================================================================================
// param400: sceSystemServiceParamGetInt
// =====================================================================================================================
using ParamGetInt = int (KYTY_SYSV_ABI*)(int param_id, int* value);

void CaseParam400() {
	auto       get = Fn<ParamGetInt>("fZo48un7LK4", "sceSystemServiceParamGetInt");
	const bool on  = On(kParam400);

	g_case        = "param400 parameter 1";
	int       v1  = -77;
	const int r1  = get(1, &v1);
	Report("param400 parameter 1 (the language)", r1 == 0 && v1 != -77,
	       Fmt("%s, %d; want 0 and a value written (--console-language, 1 by default; %s)", Hex(r1).c_str(), v1,
	           v1 != 0 ? "not 0, so the parameter 400 case tells on from off" : "0: the parameter 400 case cannot tell on from off"));

	g_case        = "param400 parameter 400";
	int       v4  = -77;
	const int r4  = get(400, &v4);
	const int w4  = on ? v1 : 0;
	Report("param400 parameter 400", r4 == 0 && v4 == w4,
	       Fmt("%s: %s, %d; want 0 and %d (%s)", on ? "on" : "off", Hex(r4).c_str(), v4, w4,
	           on ? "parameter 1's answer" : "today's unsupported 0"));

	g_case        = "param400 parameter 401";
	int       v5  = -77;
	const int r5  = get(401, &v5);
	Report("param400 parameter 401", r5 == 0 && v5 == 0, Fmt("%s, %d; want 0 and 0 (today's, both ways)", Hex(r5).c_str(), v5));
}

// =====================================================================================================================
// npwebapi: the finish entry points
// =====================================================================================================================
constexpr int kNpNotStarted = static_cast<int>(0x80553508u);

using Finish = int (KYTY_SYSV_ABI*)();

void CaseNpWebApi() {
	const bool on = On(kNpWebApi);
	struct F {
		const char* nid;
		const char* name;
	};
	static const F finishes[] = {
	    {"0oIoKcDA0Fw", "npwebapi DownStreamTransaction<DownloadDataResponseHeaders>::finish"},
	    {"VXm5RXt+uJ0", "npwebapi TransactionBase<PostPlayerSessionsResponseBody>::finish"},
	    {"ogc2cNOobW8", "npwebapi TransactionBase<PostPlayerSessionsSessionIdMemberPlayersResponseBody>::finish"},
	    {"q+50oeoRpnY", "npwebapi TransactionBase<DefaultResponse>::finish"},
	    {"rPxhVLFJBm4", "npwebapi TransactionBase<GetUsersAccountIdPlayerSessionsInvitationsResponseBody>::finish"},
	};
	for (const auto& e: finishes) {
		g_case      = e.name;
		auto      f = Fn<Finish>(e.nid, e.name);
		const int r = f(); // our bodies take no arguments (exp 0328's port ignores `this`)
		const int w = on ? kNpNotStarted : 0;
		Report(e.name, r == w, Fmt("%s: %s; want %s", on ? "on" : "off", Hex(r).c_str(), Hex(w).c_str()));
	}
}

// ---- the subsystems, as lib0405.cpp starts them, plus the network subsystem (emulator.cpp: core, log, pthread) -------
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
	auto* network = Libs::Network::NetworkSubsystem::Instance();
	slist.Add(log, {core, config});
	slist.Add(timer, {core, log});
	slist.Add(memory, {core, log});
	slist.Add(pthread, {core, log, timer});
	slist.Add(network, {core, log, pthread});
	if (!slist.InitAll(false)) {
		SetupFail(Fmt("subsystem %s: %s", slist.GetFailName(), slist.GetFailMsg()));
	}
	(void)Common::Singleton<Loader::RuntimeLinker>::Instance();

	g_case = "init: registration";
	static Loader::SymbolDatabase db;
	Libs::InitAll(&db); // libRtc.cpp prints "[bc5] exp 0405: fw-net on (items: ...)" or "... fw-net off" on stderr
	g_db = &db;
}

} // namespace fwn0405

int main(int argc, char** argv) {
	using namespace fwn0405;
	g_items            = Items(std::getenv("KYTY_BC5_FW_NET"));
	const char* mode   = g_items == kAll ? "on" : g_items == 0 ? "off" : "mixed";
	if (argc > 2 || (argc == 2 && std::strcmp(argv[1], mode) != 0)) {
		std::printf("fwn0405: the argument says %s but KYTY_BC5_FW_NET says %s (items 0x%x)\n", argc == 2 ? argv[1] : "too much",
		            mode, g_items);
		return 2;
	}
	std::printf("fwn0405: KYTY_BC5_FW_NET items 0x%x (rtc 1, rudp 2, resolver 4, param400 8, npwebapi 16): %s\n", g_items, mode);
	std::fflush(stdout);
	unsetenv("KYTY_BC5_INPUT_CONFIG");                // parameter 1 then answers --console-language (1 by default)
	unsetenv("KYTY_BC5_SYSTEMSERVICE_VALUES");        // e5's switches: parameter 401 then answers today's 0
	unsetenv("KYTY_BC5_SYSTEMSERVICE_PARAMS_7_1000"); //
	::Log::Bc5SetLogging(false);                      // the units' LOGF lines stay off stdout
	std::thread(Watchdog).detach();

	char  arg0[] = "fwn0405";
	char* args[] = {arg0, nullptr};
	Init(1, args);

	CaseRtc();
	CaseRudp();
	CaseResolver();
	CaseParam400();
	CaseNpWebApi();

	const int n = g_cases.load();
	const int p = g_passed.load();
	if (p != n) {
		std::printf("fwn0405: %s %d of %d passed; FAIL\n", mode, p, n);
		std::fflush(stdout);
		std::_Exit(1);
	}
	std::printf("fwn0405: %s %d of %d; end\n", mode, p, n);
	std::fflush(stdout);
	std::_Exit(0); // no static destructors: the Pthread subsystem's helper thread may still run
}
