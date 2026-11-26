// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0405 (series e6 of experiment 0401), tag "pad": the CPU test of mkpad0405.py's edit of src/libs/libPad.cpp
// (notes pad0405-notes.md), behind one switch: KYTY_BC5_FW_PAD (items infotype, argchecks, queries; "1" = all).
// No game, no GPU, no window, no sound device, no network. The test registers the host's libraries into its own
// SymbolDatabase (Libs::InitAll, as lib0405.cpp does), takes the functions by NID and calls them as a title would.
// Cases (one line each):
//   registration  with an item on, its NIDs resolve; with it off, they do not (today: the loader's stub answers). scePadInit
//                 is Controller::PadInit with every item off, and the recording wrapper with any item on.
//   before scePadInit (every item that is on): the calls that check the init state answer NOT_INITIALIZED (0x80920005)
//                 after the checks AnyPS5's code makes before it (a null output for scePadGetInfoByPortType);
//                 scePadGetIdleCount 0; scePadReadStateExt checks only its handle and output.
//   after scePadInit: each call's null-output, handle, size and type checks, its writes (ActiveTime 0, DeviceId -1,
//                 MotionTimerUnit 0.0, ParseUniqueDataLeonardo's 0x18 cleared bytes) and outputs it must leave alone,
//                 and its answer past the checks (0 for infotype/argchecks; DEVICE_NOT_CONNECTED or INVALID_HANDLE for
//                 queries).
// Build (build0401.py, series e6): --gate pad0405.cpp <out> --like src/libs/libPad.cpp, with the private libPad.cpp from
// mkpad0405.py in place of the shared one, linked with every emulator object but main.cpp.o.
// usage: run in a fresh directory on the NVMe:
//   KYTY_BC5_FW_PAD=1 -> "pad0405 on";  KYTY_BC5_FW_PAD=0 or unset -> "pad0405 off". An item list is allowed: each case
//   then expects its item's state, and the last line says "mixed". The argument may be left out.
// Prints "pad0405: on|off|mixed N of N; end" and exits 0 only then. A watchdog ends a hang after 60 s with a FAIL line.

#include "common/abi.h"
#include "common/commonSubsystem.h"
#include "common/emulatorConfig.h"
#include "common/logging/log.h"
#include "common/singleton.h"
#include "common/subsystems.h"
#include "common/threads.h"
#include "kernel/memory.h"
#include "kernel/pthread.h"
#include "libs/controller.h"
#include "libs/libs.h"
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
#include <string>
#include <thread>

namespace pad0405 {

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
	std::printf("pad0405: case %d %s: %s (%s)\n", g_cases.load(), name, ok ? "ok" : "FAIL", info.c_str());
	std::fflush(stdout);
}

[[noreturn]] void SetupFail(const std::string& what) {
	std::printf("pad0405: FAIL setup: %s\n", what.c_str());
	std::fflush(stdout);
	std::_Exit(2);
}

void Watchdog() {
	std::this_thread::sleep_for(std::chrono::seconds(kWatchdogSeconds));
	std::printf("pad0405: FAIL watchdog: case \"%s\" still running after %d s (a hang); %d of %d cases passed before it\n",
	            g_case.load(), kWatchdogSeconds, g_passed.load(), g_cases.load());
	std::fflush(stdout);
	std::_Exit(3);
}

std::string Hex(int v) {
	return Fmt("0x%08X", static_cast<unsigned>(v));
}

// ---- the switch, read as libPad.cpp reads it ------------------------------------------------------------------------
constexpr uint32_t kInfoType  = 1u;
constexpr uint32_t kArgChecks = 2u;
constexpr uint32_t kQueries   = 4u;
constexpr uint32_t kAll       = 7u;

uint32_t Items(const char* e) {
	if (e == nullptr || e[0] == '\0' || std::strcmp(e, "0") == 0) {
		return 0;
	}
	static const char* const names[] = {"infotype", "argchecks", "queries"};
	uint32_t                 parts   = 0;
	const char*              p       = e;
	for (;;) {
		const char*  comma = std::strchr(p, ',');
		const size_t n     = comma != nullptr ? static_cast<size_t>(comma - p) : std::strlen(p);
		for (uint32_t i = 0; i < 3; i++) {
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

uint64_t Vaddr(const char* nid) {
	const auto* r = g_db->FindByNid(nid, Loader::SymbolType::Func);
	return r != nullptr ? r->vaddr : 0;
}

template <typename F>
F Fn(const char* nid) {
	const uint64_t v = Vaddr(nid);
	if (v == 0) {
		SetupFail(Fmt("%s is not registered", nid));
	}
	return reinterpret_cast<F>(v);
}

constexpr int kOk           = 0;
constexpr int kInvalidArg   = static_cast<int>(0x80920001u);
constexpr int kInvalidHdl   = static_cast<int>(0x80920003u);
constexpr int kNotInit      = static_cast<int>(0x80920005u);
constexpr int kNotConnected = static_cast<int>(0x80920007u);
constexpr int kHandle       = 1;  // player 1's handle (Controller: PAD_HANDLE_BASE)
constexpr int kBadHandle    = 99; // no player slot

// The calls, by NID (mkpad0405.py's registration; the NIDs from exp 0327's calculator, nid0401.py's, self-checked).
struct Nids {
	const char* nid;
	uint32_t    item;
	const char* name;
};
const Nids kNids[] = {
    {"4x5Im8pr0-4", kInfoType, "scePadGetInfoByPortType"},       {"4rS5zG7RFaM", kArgChecks, "scePadGetDeviceInfo"},
    {"qtasqbvwgV4", kArgChecks, "scePadGetCapability"},          {"QuOaoOcSOw0", kArgChecks, "scePadGetVersionInfo"},
    {"kiA9bZhbnAg", kArgChecks, "scePadGetIdleCount"},           {"UxPKyWeAT7Y", kArgChecks, "scePadGetControllerIdleCount"},
    {"k0RJXTO3SbQ", kArgChecks, "scePadGetActiveTime"},          {"B8Rwqqw5Ejw", kArgChecks, "scePadSetPS4BcVibrationMode"},
    {"1DmZjZAuzEM", kArgChecks, "scePadGetExtensionUnitInfo"},   {"3u4M8ck9vJM", kArgChecks, "scePadReadHistory"},
    {"71E9e6n+2R8", kArgChecks, "scePadOpenExt2"},               {"5Wf4q349s+Q", kArgChecks, "scePadReadStateExt"},
    {"hDgisSGkOgw", kArgChecks, "scePadGetDeviceId"},            {"k4+nDV9vbT0", kQueries, "scePadGetMotionTimerUnit"},
    {"WPIB7zBWxVE", kQueries, "scePadGetMotionSensorPosition"},  {"do-JDWX+zRs", kQueries, "scePadGetSphereRadius"},
    {"Q66U8FdrMaw", kQueries, "scePadGetBluetoothAddress"},      {"d3Q+WyyvihI", kQueries, "scePadParseUniqueDataLeonardo"},
};

using IntOut    = int (KYTY_SYSV_ABI*)(int, void*);
using IntU32    = int (KYTY_SYSV_ABI*)(int, uint32_t*);
using IntU64    = int (KYTY_SYSV_ABI*)(int, uint64_t*);
using IntF32    = int (KYTY_SYSV_ABI*)(int, float*);
using IntI32    = int (KYTY_SYSV_ABI*)(int, int32_t*);
using IdleCount = uint64_t (KYTY_SYSV_ABI*)(int);
using Active    = int (KYTY_SYSV_ABI*)(int, int, uint64_t*);
using BcMode    = int (KYTY_SYSV_ABI*)(uint8_t);
using History   = int (KYTY_SYSV_ABI*)(int, void*, uint32_t);
using OpenExt2  = int (KYTY_SYSV_ABI*)(int, int, const void*);
using Leonardo  = int (KYTY_SYSV_ABI*)(int, const void*, void*);
using PadInit   = int (KYTY_SYSV_ABI*)();

// A buffer that a call must leave alone: filled with 0x5A, checked afterwards.
struct Buf {
	uint8_t b[0x1000];
	Buf() { std::memset(b, 0x5A, sizeof(b)); }
	bool Untouched() const {
		for (const uint8_t c: b) {
			if (c != 0x5A) {
				return false;
			}
		}
		return true;
	}
};

void Expect(const char* name, int got, int want, bool extra = true, const char* extra_what = "") {
	Report(name, got == want && extra, Fmt("%s; want %s%s%s", Hex(got).c_str(), Hex(want).c_str(), extra_what[0] != '\0' ? ", " : "", extra_what));
}

// ---- registration ---------------------------------------------------------------------------------------------------
void CaseRegistration() {
	g_case = "registration";
	for (uint32_t item: {kInfoType, kArgChecks, kQueries}) {
		const bool on      = On(item);
		int        found   = 0;
		int        total   = 0;
		std::string missing;
		for (const auto& n: kNids) {
			if (n.item != item) {
				continue;
			}
			total++;
			if (Vaddr(n.nid) != 0) {
				found++;
			} else if (on) {
				missing += std::string(" ") + n.name;
			}
		}
		const char* name = item == kInfoType ? "registration infotype" : item == kArgChecks ? "registration argchecks" : "registration queries";
		Report(name, found == (on ? total : 0),
		       Fmt("%s: %d of %d NIDs resolve; want %d%s", on ? "on" : "off", found, total, on ? total : 0, missing.c_str()));
	}
	const uint64_t init = Vaddr("hv1luiJrqQM");
	const uint64_t host = reinterpret_cast<uint64_t>(&Libs::Controller::PadInit);
	const bool     any  = g_items != 0;
	Report("registration scePadInit", init != 0 && ((init == host) != any),
	       Fmt("scePadInit 0x%016llx, Controller::PadInit 0x%016llx; want %s", static_cast<unsigned long long>(init),
	           static_cast<unsigned long long>(host), any ? "the recording wrapper (another address)" : "Controller::PadInit"));
}

// ---- before scePadInit ----------------------------------------------------------------------------------------------
void CaseBeforeInit() {
	if (On(kInfoType)) {
		g_case     = "infotype before init";
		auto f     = Fn<IntOut>("4x5Im8pr0-4");
		Buf  out;
		Expect("infotype before init, null output (checked first)", f(0, nullptr), kInvalidArg);
		Expect("infotype before init, type 0", f(0, out.b), kNotInit, out.Untouched(), "output untouched");
	}
	if (On(kArgChecks)) {
		g_case = "argchecks before init";
		Buf      out;
		uint64_t u64 = 7;
		int32_t  i32 = 7;
		uint32_t u32 = 7;
		Expect("argchecks before init, GetDeviceInfo", Fn<IntOut>("4rS5zG7RFaM")(0, out.b), kNotInit);
		Expect("argchecks before init, GetCapability", Fn<IntU32>("qtasqbvwgV4")(0, &u32), kNotInit, u32 == 7, "untouched");
		Expect("argchecks before init, GetVersionInfo", Fn<IntOut>("QuOaoOcSOw0")(kHandle, out.b), kNotInit);
		const uint64_t idle = Fn<IdleCount>("kiA9bZhbnAg")(1000);
		Report("argchecks before init, GetIdleCount", idle == 0, Fmt("%llu; want 0", static_cast<unsigned long long>(idle)));
		Expect("argchecks before init, GetControllerIdleCount", Fn<IntU64>("UxPKyWeAT7Y")(kHandle, &u64), kNotInit, u64 == 7, "untouched");
		Expect("argchecks before init, GetActiveTime", Fn<Active>("k0RJXTO3SbQ")(kHandle, 0, &u64), kNotInit, u64 == 7, "untouched");
		Expect("argchecks before init, SetPS4BcVibrationMode", Fn<BcMode>("B8Rwqqw5Ejw")(1), kNotInit);
		Expect("argchecks before init, GetExtensionUnitInfo", Fn<IntOut>("1DmZjZAuzEM")(kHandle, out.b), kNotInit);
		Expect("argchecks before init, ReadHistory", Fn<History>("3u4M8ck9vJM")(kHandle, out.b, 0x960), kNotInit);
		Expect("argchecks before init, OpenExt2", Fn<OpenExt2>("71E9e6n+2R8")(1000, 0x10, out.b), kNotInit);
		Expect("argchecks before init, GetDeviceId", Fn<IntI32>("hDgisSGkOgw")(kHandle, &i32), kNotInit, i32 == 7, "untouched");
		Expect("argchecks before init, ReadStateExt unknown handle (no init check)", Fn<IntOut>("5Wf4q349s+Q")(kBadHandle, out.b),
		       kInvalidHdl, out.Untouched(), "output untouched");
	}
	if (On(kQueries)) {
		g_case = "queries before init";
		Buf      out;
		float    f32 = 1.0f;
		uint64_t u64 = 7;
		Expect("queries before init, GetMotionTimerUnit", Fn<IntF32>("k4+nDV9vbT0")(kHandle, &f32), kNotInit, f32 == 1.0f, "untouched");
		Expect("queries before init, GetMotionSensorPosition", Fn<IntOut>("WPIB7zBWxVE")(kHandle, out.b), kNotInit);
		Expect("queries before init, GetSphereRadius", Fn<IntF32>("do-JDWX+zRs")(kHandle, &f32), kNotInit);
		Expect("queries before init, GetBluetoothAddress", Fn<IntU64>("Q66U8FdrMaw")(kHandle, &u64), kNotInit, u64 == 7, "untouched");
		Buf data;
		Expect("queries before init, ParseUniqueDataLeonardo", Fn<Leonardo>("d3Q+WyyvihI")(kHandle, data.b, out.b), kNotInit,
		       out.Untouched(), "output untouched");
	}
}

// ---- after scePadInit -----------------------------------------------------------------------------------------------
void CaseAfterInit() {
	if (On(kInfoType)) {
		g_case = "infotype after init";
		auto f = Fn<IntOut>("4x5Im8pr0-4");
		Buf  out;
		Expect("infotype null output", f(2, nullptr), kInvalidArg);
		Expect("infotype type 1", f(1, out.b), kInvalidArg, out.Untouched(), "output untouched");
		Expect("infotype type 3", f(3, out.b), kInvalidArg, out.Untouched(), "output untouched");
		Expect("infotype type 16", f(16, out.b), kInvalidArg, out.Untouched(), "output untouched");
		Expect("infotype type -1", f(-1, out.b), kInvalidArg, out.Untouched(), "output untouched");
		Expect("infotype type 0 (past the checks)", f(0, out.b), kOk, out.Untouched(), "nothing written");
		Expect("infotype type 2 (past the checks)", f(2, out.b), kOk, out.Untouched(), "nothing written");
	}
	if (On(kArgChecks)) {
		g_case = "argchecks after init";
		Buf      out;
		uint32_t u32 = 7;
		Expect("argchecks GetDeviceInfo null", Fn<IntOut>("4rS5zG7RFaM")(0, nullptr), kInvalidArg);
		Expect("argchecks GetDeviceInfo", Fn<IntOut>("4rS5zG7RFaM")(0, out.b), kOk, out.Untouched(), "nothing written");
		Expect("argchecks GetCapability null", Fn<IntU32>("qtasqbvwgV4")(0, nullptr), kInvalidArg);
		Expect("argchecks GetCapability", Fn<IntU32>("qtasqbvwgV4")(0, &u32), kOk, u32 == 7, "nothing written");
		Expect("argchecks GetVersionInfo null", Fn<IntOut>("QuOaoOcSOw0")(kHandle, nullptr), kInvalidArg);
		Expect("argchecks GetVersionInfo", Fn<IntOut>("QuOaoOcSOw0")(kHandle, out.b), kOk, out.Untouched(), "nothing written");
		Expect("argchecks GetExtensionUnitInfo null", Fn<IntOut>("1DmZjZAuzEM")(kHandle, nullptr), kInvalidArg);
		Expect("argchecks GetExtensionUnitInfo", Fn<IntOut>("1DmZjZAuzEM")(kHandle, out.b), kOk, out.Untouched(), "nothing written");
		const uint64_t idle = Fn<IdleCount>("kiA9bZhbnAg")(1000);
		Report("argchecks GetIdleCount", idle == 0, Fmt("%llu; want 0", static_cast<unsigned long long>(idle)));
		uint64_t count = 7;
		Expect("argchecks GetControllerIdleCount handle 0", Fn<IntU64>("UxPKyWeAT7Y")(0, &count), kInvalidArg, count == 7, "untouched");
		Expect("argchecks GetControllerIdleCount null", Fn<IntU64>("UxPKyWeAT7Y")(kHandle, nullptr), kInvalidArg);
		Expect("argchecks GetControllerIdleCount", Fn<IntU64>("UxPKyWeAT7Y")(kHandle, &count), kOk, count == 7, "nothing written");
		uint64_t active = 7;
		Expect("argchecks GetActiveTime null", Fn<Active>("k0RJXTO3SbQ")(kHandle, 0, nullptr), kInvalidArg);
		Expect("argchecks GetActiveTime", Fn<Active>("k0RJXTO3SbQ")(kHandle, 0, &active), kOk, active == 0, "0 written");
		Expect("argchecks SetPS4BcVibrationMode", Fn<BcMode>("B8Rwqqw5Ejw")(1), kOk);
		Expect("argchecks ReadHistory size 0x95F", Fn<History>("3u4M8ck9vJM")(kHandle, out.b, 0x95F), kInvalidArg);
		Expect("argchecks ReadHistory size 0x960", Fn<History>("3u4M8ck9vJM")(kHandle, out.b, 0x960), kOk, out.Untouched(), "nothing written");
		Expect("argchecks ReadHistory null data (not checked)", Fn<History>("3u4M8ck9vJM")(kHandle, nullptr, 0x960), kOk);
		Buf param;
		Expect("argchecks OpenExt2 null parameter", Fn<OpenExt2>("71E9e6n+2R8")(1000, 0x10, nullptr), kInvalidArg);
		Expect("argchecks OpenExt2 size 0x11", Fn<OpenExt2>("71E9e6n+2R8")(1000, 0x11, param.b), kInvalidArg);
		Expect("argchecks OpenExt2", Fn<OpenExt2>("71E9e6n+2R8")(1000, 0x10, param.b), kOk, param.Untouched(), "parameter untouched");
		Expect("argchecks ReadStateExt unknown handle", Fn<IntOut>("5Wf4q349s+Q")(kBadHandle, out.b), kInvalidHdl);
		Expect("argchecks ReadStateExt null", Fn<IntOut>("5Wf4q349s+Q")(kHandle, nullptr), kInvalidArg);
		Expect("argchecks ReadStateExt", Fn<IntOut>("5Wf4q349s+Q")(kHandle, out.b), kOk, out.Untouched(), "nothing written");
		int32_t id = 7;
		Expect("argchecks GetDeviceId null", Fn<IntI32>("hDgisSGkOgw")(kHandle, nullptr), kInvalidArg);
		Expect("argchecks GetDeviceId unknown handle", Fn<IntI32>("hDgisSGkOgw")(kBadHandle, &id), kInvalidHdl, id == -1, "-1 written");
		id = 7;
		Expect("argchecks GetDeviceId", Fn<IntI32>("hDgisSGkOgw")(kHandle, &id), kOk, id == -1, "-1 written");
	}
	if (On(kQueries)) {
		g_case = "queries after init";
		Buf   out;
		float unit = 1.0f;
		Expect("queries GetMotionTimerUnit null", Fn<IntF32>("k4+nDV9vbT0")(kHandle, nullptr), kInvalidArg);
		Expect("queries GetMotionTimerUnit unknown handle", Fn<IntF32>("k4+nDV9vbT0")(kBadHandle, &unit), kInvalidHdl, unit == 0.0f, "0.0 written");
		unit = 1.0f;
		Expect("queries GetMotionTimerUnit", Fn<IntF32>("k4+nDV9vbT0")(kHandle, &unit), kNotConnected, unit == 0.0f, "0.0 written");
		Expect("queries GetMotionSensorPosition null", Fn<IntOut>("WPIB7zBWxVE")(kHandle, nullptr), kInvalidArg);
		Expect("queries GetMotionSensorPosition unknown handle", Fn<IntOut>("WPIB7zBWxVE")(kBadHandle, out.b), kInvalidHdl, out.Untouched(), "untouched");
		Expect("queries GetMotionSensorPosition", Fn<IntOut>("WPIB7zBWxVE")(kHandle, out.b), kNotConnected, out.Untouched(), "untouched");
		float radius = 1.0f;
		Expect("queries GetSphereRadius null", Fn<IntF32>("do-JDWX+zRs")(kHandle, nullptr), kInvalidArg);
		Expect("queries GetSphereRadius (no special-port handle here)", Fn<IntF32>("do-JDWX+zRs")(kHandle, &radius), kInvalidHdl, radius == 1.0f, "untouched");
		uint64_t address = 7;
		Expect("queries GetBluetoothAddress null", Fn<IntU64>("Q66U8FdrMaw")(kHandle, nullptr), kInvalidArg);
		Expect("queries GetBluetoothAddress unknown handle", Fn<IntU64>("Q66U8FdrMaw")(kBadHandle, &address), kInvalidHdl, address == 7, "untouched");
		Expect("queries GetBluetoothAddress", Fn<IntU64>("Q66U8FdrMaw")(kHandle, &address), kNotConnected, address == 7, "untouched");
		Buf  data;
		auto leo = Fn<Leonardo>("d3Q+WyyvihI");
		Expect("queries ParseUniqueDataLeonardo null data", leo(kHandle, nullptr, out.b), kInvalidArg, out.Untouched(), "untouched");
		Expect("queries ParseUniqueDataLeonardo null output", leo(kHandle, data.b, nullptr), kInvalidArg);
		const int r       = leo(kHandle, data.b, out.b);
		bool      cleared = true;
		for (size_t i = 0; i < 0x20; i++) {
			cleared = cleared && out.b[i] == (i < 0x18 ? 0 : 0x5A);
		}
		Expect("queries ParseUniqueDataLeonardo", r, kInvalidHdl, cleared, "0x18 bytes cleared, the rest untouched");
	}
}

// ---- the subsystems, as lib0405.cpp starts them ---------------------------------------------------------------------
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
	slist.Add(log, {core, config});
	slist.Add(timer, {core, log});
	slist.Add(memory, {core, log});
	slist.Add(pthread, {core, log, timer});
	if (!slist.InitAll(false)) {
		SetupFail(Fmt("subsystem %s: %s", slist.GetFailName(), slist.GetFailMsg()));
	}
	(void)Common::Singleton<Loader::RuntimeLinker>::Instance();

	g_case = "init: registration";
	static Loader::SymbolDatabase db;
	Libs::InitAll(&db); // libPad.cpp prints "[bc5] exp 0405: fw pad on (items: ...)" or "... fw pad off" on stderr
	g_db = &db;
}

} // namespace pad0405

int main(int argc, char** argv) {
	using namespace pad0405;
	g_items          = Items(std::getenv("KYTY_BC5_FW_PAD"));
	const char* mode = g_items == kAll ? "on" : g_items == 0 ? "off" : "mixed";
	if (argc > 2 || (argc == 2 && std::strcmp(argv[1], mode) != 0)) {
		std::printf("pad0405: the argument says %s but KYTY_BC5_FW_PAD says %s (items 0x%x)\n", argc == 2 ? argv[1] : "too much",
		            mode, g_items);
		return 2;
	}
	std::printf("pad0405: KYTY_BC5_FW_PAD items 0x%x (infotype 1, argchecks 2, queries 4): %s\n", g_items, mode);
	std::fflush(stdout);
	::Log::Bc5SetLogging(false); // the units' LOGF lines stay off stdout
	std::thread(Watchdog).detach();

	char  arg0[] = "pad0405";
	char* args[] = {arg0, nullptr};
	Init(1, args);

	CaseRegistration();
	CaseBeforeInit();
	g_case = "scePadInit";
	const auto init = Fn<PadInit>("hv1luiJrqQM");
	if (init == nullptr || init() != 0) {
		SetupFail("scePadInit is not registered or failed");
	}
	CaseAfterInit();

	const int n = g_cases.load();
	const int p = g_passed.load();
	if (p != n) {
		std::printf("pad0405: %s %d of %d passed; FAIL\n", mode, p, n);
		std::fflush(stdout);
		std::_Exit(1);
	}
	std::printf("pad0405: %s %d of %d; end\n", mode, p, n);
	std::fflush(stdout);
	std::_Exit(0); // no static destructors: the Pthread subsystem's helper thread may still run
}
