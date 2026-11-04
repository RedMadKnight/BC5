// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0405 (series e7 of experiment 0401), tag tbv: the CPU test of mktbv0405.py's ports (exp 0405 decision 4,
// dead-table batch 2) in src/libs/libVoice.cpp, libScreenShot.cpp, libDiscMap.cpp, libUlobjmgr.cpp, libCompanion.cpp and
// libVideoRecording.cpp, behind KYTY_BC5_LOAD_VOICE, _SCREENSHOT, _DISCMAP, _ULOBJMGR, _COMPANIONHTTPD, _COMPANIONUTIL and
// _VIDEORECORDING (notes tbv0405-notes.md). It starts the subsystems a guest thread needs plus the file system (as
// tbn0405.cpp does), registers the seven tables into its own SymbolDatabase by calling their LIB_DEFINEs in tl2's order
// (the switched tables first, then the live libSceVoice table of libs/libAudio.cpp; with a switch off the init still runs
// here, to call today's stubs), takes each function by its exact key (NID, library, versions) as a title's import resolves
// it, and calls it as a title would. Outputs start as a sentinel, so each case sees whether a call wrote them.
//   voice           on: VADSetVersion's versions, GetResourceInfo's null check before and after the live sceVoiceInit,
//                   its limits held; the 16 live NIDs left to libAudio.cpp (Find and FindByNid); the 12 held or
//                   already-matching calls give 0. off: 0 everywhere, nothing written.
//   screenshot      on: Disable / Enable / IsDisabled; SetOverlayImage(WithOrigin)'s checks in order, against files this
//                   test makes under ./tbv0405-app0 mounted at /app0 (a file, an empty file, 8 MiB, 8 MiB + 1, a
//                   directory, a missing file, 1023- and 1024-byte paths), no descriptor left open; the 9 held or
//                   matching calls give 0. off: 0 everywhere, nothing written.
//   discmap         on: NO_BITMAP_INFO from IsRequestOnHDD and ioKMruft1ek, with and without arguments, nothing written.
//   ulobjmgr        on: RegisterObject's EINVAL (22) cases and id 0, UnregisterObject's id limit.
//   companionhttpd  on: the server state (OptParamInitialize, Initialize, Register/Unregister, Start/Stop, Terminate,
//                   GetEvent), the two adapted answers, Initialize2 (held) marking the library initialized; the response
//                   calls give 0 with the response untouched.
//   companionutil   on: GetEvent's NO_EVENT, nothing written.
//   videorecording  SetInfo held: 0 both ways.
// Each case follows its own table's switch, so any mix of switches is valid. No game, GPU, window, sound device, network,
// USB or camera. Prints one line per case and finally "tbv0405: on|off|mixed N of N; end" (all set: on; all unset or 0:
// off; else mixed); exit 0 only then. An optional argument "on"/"off"/"mixed" must match the switches (else exit 2). A
// watchdog ends a hang after 60 s with a FAIL line. Run it in a fresh directory: it writes ./tbv0405-app0 and removes it.
// Build: build0401.py ... src/libs/libVoice.cpp=<out>/src/libs/libVoice.cpp (and the other five units of mktbv0405.py)
//        --gate tbv0405.cpp <bin> --like src/libs/libVoice.cpp

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
#include <vector>

#include <unistd.h>

namespace Libs {
namespace LibVoice {
LIB_DEFINE(InitVoice_1);
LIB_DEFINE(InitAudio_1_Voice); // the live libSceVoice table, libs/libAudio.cpp
} // namespace LibVoice
namespace LibScreenShot {
LIB_DEFINE(InitScreenShot_1);
} // namespace LibScreenShot
namespace LibDiscMap {
LIB_DEFINE(InitDiscMap_1);
} // namespace LibDiscMap
namespace LibUlobjmgr {
LIB_DEFINE(InitUlobjmgr_1);
} // namespace LibUlobjmgr
namespace CompanionHttpd {
LIB_DEFINE(InitCompanionHttpd_1);
} // namespace CompanionHttpd
namespace CompanionUtil {
LIB_DEFINE(InitCompanionUtil_1);
} // namespace CompanionUtil
namespace LibVideoRecording {
LIB_DEFINE(InitVideoRecording_1);
} // namespace LibVideoRecording
} // namespace Libs

namespace tbv0405 {

template <typename... A>
using IFn = int (KYTY_SYSV_ABI*)(A...);

constexpr int      kWatchdogSeconds = 60;
constexpr uint32_t kS32             = 0x5A5A5A5Au; // an output the call has not written
constexpr uint64_t kS64             = 0x5A5A5A5A5A5A5A5Aull;
constexpr char     kApp0[]          = "tbv0405-app0";

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
	std::printf("tbv0405: case %d %s: %s (%s)\n", g_cases.load(), name.c_str(), ok ? "ok" : "FAIL", info.c_str());
	std::fflush(stdout);
}

std::string Hex(int r) {
	return Fmt("0x%08x", static_cast<uint32_t>(r));
}

// A case that compares return values with the wanted ones (and, optionally, more conditions).
void Rcs(const std::string& name, const std::vector<int>& got, const std::vector<int>& want, bool more = true,
         const std::string& info = "") {
	bool        same = got.size() == want.size();
	std::string text;
	for (size_t i = 0; i < got.size(); i++) {
		same = same && got[i] == want[i];
		text += (i == 0 ? "" : " ") + Hex(got[i]);
	}
	text += ", want";
	for (int w: want) {
		text += " " + Hex(w);
	}
	Report(name, same && more, info.empty() ? text : text + "; " + info);
}

void Rc(const std::string& name, int got, int want, bool more = true, const std::string& info = "") {
	Rcs(name, {got}, {want}, more, info);
}

[[noreturn]] void SetupFail(const std::string& what) {
	std::printf("tbv0405: FAIL setup: %s\n", what.c_str());
	std::fflush(stdout);
	std::_Exit(2);
}

void Watchdog() {
	std::this_thread::sleep_for(std::chrono::seconds(kWatchdogSeconds));
	std::printf("tbv0405: FAIL watchdog: case \"%s\" still running after %d s (a hang); %d of %d cases passed before it\n",
	            g_case.load(), kWatchdogSeconds, g_passed.load(), g_cases.load());
	std::fflush(stdout);
	std::_Exit(3);
}

// The units' rule (env_flag.hpp): set, non-empty and not "0" is on.
bool SwitchOn(const char* name) {
	const char* e = std::getenv(name);
	return e != nullptr && e[0] != '\0' && std::strcmp(e, "0") != 0;
}

bool g_voice = false;
bool g_ss    = false;
bool g_dm    = false;
bool g_ul    = false;
bool g_httpd = false;
bool g_util  = false;
bool g_vr    = false;

// ---- registration and lookup ----------------------------------------------------------------------------------------
Loader::SymbolDatabase g_all;        // the seven tables, then the live libSceVoice table (tl2's order with them on)
Loader::SymbolDatabase g_dead_voice; // InitVoice_1 alone
Loader::SymbolDatabase g_live_voice; // libAudio.cpp's InitAudio_1_Voice alone

uint64_t Addr(const Loader::SymbolDatabase& db, const char* nid, const char* lib) {
	Loader::SymbolResolve sr {};
	sr.name                 = nid;
	sr.library              = lib;
	sr.library_version      = 1;
	sr.module               = lib;
	sr.module_version_major = 1;
	sr.module_version_minor = 1;
	sr.type                 = Loader::SymbolType::Func;
	const auto* r           = db.Find(sr);
	return r != nullptr ? r->vaddr : 0;
}

uint64_t ByNid(const Loader::SymbolDatabase& db, const char* nid) {
	const auto* r = db.FindByNid(nid, Loader::SymbolType::Func);
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

int Registered(const std::vector<const char*>& nids, const char* lib) {
	int n = 0;
	for (const char* nid: nids) {
		n += Addr(g_all, nid, lib) != 0 ? 1 : 0;
	}
	return n;
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

// Each held (or already matching) stub, called without arguments: today's 0.
void HeldZero(const std::string& name, const std::vector<const char*>& nids, const char* lib) {
	int         zero = 0;
	std::string wrong;
	for (const char* nid: nids) {
		const int v = Fn<IFn<>>(nid, lib)();
		if (v == 0) {
			zero++;
		} else {
			wrong += Fmt(" %s=%s", nid, Hex(v).c_str());
		}
	}
	Report(name, zero == static_cast<int>(nids.size()), Fmt("%d of %zu give 0%s", zero, nids.size(), wrong.c_str()));
}

// =====================================================================================================================
// Voice
// =====================================================================================================================
constexpr int kVoiceArg = static_cast<int>(0x804E0805u);

const std::vector<const char*> kVoiceDead = {"Pc4z1QjForU", "Z6QV6j7igvE", "IPHvnM5+g04", "x0slGBQW+wY", "Dinob0yMRl8",
                                             "udAxvCePkUs", "gAgN+HkiEzY", "jbkJFmOZ9U0", "TexwmOHQsDg", "gwUynkEgNFY",
                                             "oUha0S-Ij9Q", "jSZNP7xJrcw", "hg9T73LlRiU", "wFeAxEeEi-8"};
const std::vector<const char*> kVoiceLive = {"9TrhuGzberQ", "clyKUyi3RYU", "nXpje5yNpaE", "oV9GAdJ23Gw",
                                             "ajVj3QG2um4", "b7kJI+nx2hg", "Oo0S5PH7FIQ", "54phPH2LZls",
                                             "Ao2YNSA7-Qo", "cQ6DGsQEjV4", "YeJl6yDlhW0", "CrLqDwWLoXM",
                                             "elcxZTEfHZM", "cJLufzou6bc", "QBFoAIjJoXQ", "jjkCjneOYSs"};
// The 12 calls held for split state or already giving AnyPS5's answer (all but VADSetVersion and GetResourceInfo).
const std::vector<const char*> kVoiceHeld = {"Pc4z1QjForU", "IPHvnM5+g04", "x0slGBQW+wY", "Dinob0yMRl8",
                                             "udAxvCePkUs", "gAgN+HkiEzY", "jbkJFmOZ9U0", "TexwmOHQsDg",
                                             "gwUynkEgNFY", "oUha0S-Ij9Q", "jSZNP7xJrcw", "hg9T73LlRiU"};

void CaseVoice() {
	g_case          = "voice";
	const char* lib = "libSceVoice";
	const bool  on  = g_voice;
	const char* off = on ? "" : "off: ";

	int dead_own = 0, dead_live = 0, live_own = 0, live_dead = 0;
	for (const char* n: kVoiceDead) {
		dead_own += Addr(g_dead_voice, n, lib) != 0 ? 1 : 0;
		live_dead += Addr(g_live_voice, n, lib) != 0 ? 1 : 0;
	}
	for (const char* n: kVoiceLive) {
		dead_live += Addr(g_dead_voice, n, lib) != 0 ? 1 : 0;
		live_own += Addr(g_live_voice, n, "Voice") != 0 ? 1 : 0;
	}
	Report("voice registration: this table 14 NIDs, none of the live table's 16; the live table none of the 14",
	       dead_own == 14 && dead_live == 0 && live_own == 16 && live_dead == 0,
	       Fmt("dead %d + %d live NIDs, live %d + %d dead NIDs", dead_own, dead_live, live_own, live_dead));
	int live_ok = 0, dead_ok = 0;
	for (const char* n: kVoiceLive) {
		const uint64_t lv = Addr(g_live_voice, n, "Voice");
		live_ok += (lv != 0 && Addr(g_all, n, lib) == lv && ByNid(g_all, n) == lv) ? 1 : 0;
	}
	for (const char* n: kVoiceDead) {
		const uint64_t dv = Addr(g_dead_voice, n, lib);
		dead_ok += (dv != 0 && Addr(g_all, n, lib) == dv && ByNid(g_all, n) == dv) ? 1 : 0;
	}
	Report("voice in tl2's order: the 16 live NIDs resolve to libAudio.cpp, the 14 to this table (Find and FindByNid)",
	       live_ok == 16 && dead_ok == 14, Fmt("%d of 16, %d of 14", live_ok, dead_ok));

	const auto set_version = Fn<IFn<int32_t>>("wFeAxEeEi-8", lib);
	Rcs(std::string(off) + "voice VADSetVersion(0), (1): 0", {set_version(0), set_version(1)}, {0, 0});
	Rcs(on ? "voice VADSetVersion(2), (-1), (100): INVALID_ARGUMENT" : "voice off: VADSetVersion(2), (-1), (100): 0",
	    {set_version(2), set_version(-1), set_version(100)}, on ? std::vector<int> {kVoiceArg, kVoiceArg, kVoiceArg}
	                                                           : std::vector<int> {0, 0, 0});

	const auto resource = Fn<IFn<void*>>("Z6QV6j7igvE", lib);
	uint8_t    info[16];
	Rc(on ? "voice GetResourceInfo(null): INVALID_ARGUMENT (the library counts as initialized)"
	      : "voice off: GetResourceInfo(null): 0",
	   resource(nullptr), on ? kVoiceArg : 0);
	std::memset(info, 0xA5, sizeof(info));
	int r = resource(info);
	Rc(std::string(off) + "voice GetResourceInfo(info): 0, nothing written (the limits are held)", r, 0,
	   AllBytes(info, sizeof(info), 0xA5));

	// The live sceVoiceInit (libAudio.cpp) changes nothing for this table.
	const auto live_init = Fn<IFn<void*, int32_t>>("9TrhuGzberQ", lib);
	const auto live_end  = Fn<IFn<>>("Oo0S5PH7FIQ", lib);
	uint8_t    init_param[32] {};
	init_param[0] = 4;
	Rc("voice setup: the live sceVoiceInit", live_init(init_param, 100), 0);
	Rc(on ? "voice GetResourceInfo(null) after the live Init: INVALID_ARGUMENT" : "voice off: GetResourceInfo(null) after the live Init: 0",
	   resource(nullptr), on ? kVoiceArg : 0);
	std::memset(info, 0xA5, sizeof(info));
	r = resource(info);
	Rc(std::string(off) + "voice GetResourceInfo(info) after the live Init: 0, nothing written", r, 0,
	   AllBytes(info, sizeof(info), 0xA5));
	Rc("voice setup: the live sceVoiceEnd", live_end(), 0);

	const auto get_mute = Fn<IFn<uint32_t, uint8_t*>>("Pc4z1QjForU", lib);
	uint8_t    mute     = 0xA5;
	r                   = get_mute(1, &mute);
	Rc(std::string(off) + "voice GetMuteFlag(1, out) (held): 0, nothing written", r, 0, mute == 0xA5);
	HeldZero(std::string(off) + "voice the 12 held or already-matching calls: 0", kVoiceHeld, lib);
}

// =====================================================================================================================
// ScreenShot
// =====================================================================================================================
constexpr int kSsArg  = static_cast<int>(0x80BE0001u);
constexpr int kSsFile = static_cast<int>(0x80BE0003u);
constexpr int kSsSize = static_cast<int>(0x80BE000Eu);

void MakeFile(const std::filesystem::path& p, uintmax_t size) {
	{
		std::ofstream f(p, std::ios::binary | std::ios::trunc);
		if (!f) {
			SetupFail("cannot write " + p.string());
		}
		const char head[16] = {'t', 'b', 'v', '0', '4', '0', '5'};
		f.write(head, static_cast<std::streamsize>(size < sizeof(head) ? size : sizeof(head)));
	}
	std::error_code ec;
	std::filesystem::resize_file(p, size, ec);
	if (ec || std::filesystem::file_size(p) != size) {
		SetupFail("cannot size " + p.string());
	}
}

void MakeOverlayFiles() {
	const std::filesystem::path dir(kApp0);
	std::filesystem::create_directories(dir / "dir.png");
	MakeFile(dir / "ok.png", 16);
	MakeFile(dir / "empty.png", 0);
	MakeFile(dir / "max.png", uintmax_t {8} * 1024 * 1024);
	MakeFile(dir / "big.png", uintmax_t {8} * 1024 * 1024 + 1);
	Libs::LibKernel::FileSystem::Mount(std::filesystem::absolute(dir), "/app0");
}

void CaseScreenShot() {
	g_case          = "screenshot";
	const char* lib = "libSceScreenShot";
	const bool  on  = g_ss;
	const char* off = on ? "" : "off: ";
	const int   ok  = 0;
	auto        w   = [on](int x) { return on ? x : 0; };

	Rc("screenshot registration: 14 NIDs", Registered({"AS45QoYHjc4", "JuMLLmmvRgk", "tIYf0W5VTi8", "ysfza71rm9M",
	                                                    "2xxUtuC-RzE", "BDUaqlVdSAY", "hNmK4SdhPT0", "VlAQIgXa2R0",
	                                                    "-SV-oTNGFQk", "ICNJ-1POs84", "ahHhOf+QNkQ", "73WQ4Jj0nJI",
	                                                    "G7KlmIYFIZc", "itlWFWV3Tzc"},
	                                                   lib),
	   14);
	const auto disable     = Fn<IFn<>>("tIYf0W5VTi8", lib);
	const auto enable      = Fn<IFn<>>("2xxUtuC-RzE", lib);
	const auto is_disabled = Fn<IFn<int, int32_t*>>("-SV-oTNGFQk", lib);
	const auto overlay     = Fn<IFn<const char*, int, int>>("ahHhOf+QNkQ", lib);
	const auto overlay_o   = Fn<IFn<const char*, int, int, int>>("73WQ4Jj0nJI", lib);

	auto v = static_cast<int32_t>(kS32);
	int  r = is_disabled(0, &v);
	Rc(on ? "screenshot IsDisabled(0) at start: 0, 0 written" : "screenshot off: IsDisabled(0): 0, nothing written", r, 0,
	   on ? v == 0 : v == static_cast<int32_t>(kS32), Fmt("out 0x%08x", static_cast<uint32_t>(v)));
	v = static_cast<int32_t>(kS32);
	r = is_disabled(-1, &v);
	Rc(on ? "screenshot IsDisabled(-1): ERROR_ARGUMENT, nothing written" : "screenshot off: IsDisabled(-1): 0", r, w(kSsArg),
	   v == static_cast<int32_t>(kS32));
	Rc(on ? "screenshot IsDisabled(0, null): ERROR_ARGUMENT" : "screenshot off: IsDisabled(0, null): 0", is_disabled(0, nullptr),
	   w(kSsArg));
	r = disable();
	v = static_cast<int32_t>(kS32);
	const int r2 = is_disabled(7, &v);
	Rcs(on ? "screenshot Disable, then IsDisabled(7): 0, 0, 1 written" : "screenshot off: Disable, IsDisabled(7): 0, 0, nothing written",
	    {r, r2}, {0, 0}, on ? v == 1 : v == static_cast<int32_t>(kS32), Fmt("out 0x%08x", static_cast<uint32_t>(v)));
	r = enable();
	v = static_cast<int32_t>(kS32);
	const int r3 = is_disabled(0, &v);
	Rcs(on ? "screenshot Enable, then IsDisabled(0): 0, 0, 0 written" : "screenshot off: Enable, IsDisabled(0): 0, 0, nothing written",
	    {r, r3}, {0, 0}, on ? v == 0 : v == static_cast<int32_t>(kS32), Fmt("out 0x%08x", static_cast<uint32_t>(v)));
	Rcs("screenshot EnableNotification, DisableNotification (already AnyPS5's answer): 0",
	    {Fn<IFn<>>("BDUaqlVdSAY", lib)(), Fn<IFn<>>("ysfza71rm9M", lib)()}, {0, 0});

	// Overlay images, against ./tbv0405-app0 mounted at /app0. The test's SDK version is the kernel's default (no program
	// is loaded: 0x0A000000, 3.50 or later), so the large limits apply.
	MakeOverlayFiles();
	const int fd0 = Libs::LibKernel::FileSystem::KernelOpen("/app0/ok.png", 0, 0);
	if (fd0 >= 0) {
		(void)Libs::LibKernel::FileSystem::KernelClose(fd0);
	}
	Report("screenshot setup: the test's file opens through the kernel", fd0 >= 0, Fmt("descriptor %d", fd0));
	Rcs(std::string(off) + "screenshot SetOverlayImage(ok.png) at (0, 0) and (3839, 2159): 0, 0",
	    {overlay("/app0/ok.png", 0, 0), overlay("/app0/ok.png", 3839, 2159)}, {ok, ok});
	Rc(on ? "screenshot SetOverlayImage(null): ERROR_ARGUMENT" : "screenshot off: SetOverlayImage(null): 0",
	   overlay(nullptr, 0, 0), w(kSsArg));
	Rcs(on ? "screenshot SetOverlayImage(ok.png) at x -1, x 3840, y -1, y 2160: ERROR_ARGUMENT x4"
	       : "screenshot off: SetOverlayImage out of range x4: 0",
	    {overlay("/app0/ok.png", -1, 0), overlay("/app0/ok.png", 3840, 0), overlay("/app0/ok.png", 0, -1),
	     overlay("/app0/ok.png", 0, 2160)},
	    {w(kSsArg), w(kSsArg), w(kSsArg), w(kSsArg)});
	const std::string p1024 = "/tbv0405-none/" + std::string(1024 - 14, 'a'); // 1024 bytes, no mount point
	const std::string p1023 = "/tbv0405-none/" + std::string(1023 - 14, 'a'); // 1023 bytes
	Rcs(on ? "screenshot SetOverlayImage of a 1024-byte path: ERROR_ARGUMENT; 1023 bytes, not a file: ERROR_OVERLAY_FILE"
	       : "screenshot off: SetOverlayImage of 1024- and 1023-byte paths: 0",
	    {overlay(p1024.c_str(), 0, 0), overlay(p1023.c_str(), 0, 0)}, {w(kSsArg), w(kSsFile)},
	    p1024.size() == 1024 && p1023.size() == 1023);
	Rcs(on ? "screenshot SetOverlayImage of a missing file and a directory: ERROR_OVERLAY_FILE x2"
	       : "screenshot off: SetOverlayImage of a missing file and a directory: 0",
	    {overlay("/app0/missing.png", 0, 0), overlay("/app0/dir.png", 0, 0)}, {w(kSsFile), w(kSsFile)});
	Rcs(on ? "screenshot SetOverlayImage of 0 bytes, 8 MiB, 8 MiB + 1: ERROR_OVERLAY_SIZE, 0, ERROR_OVERLAY_SIZE"
	       : "screenshot off: SetOverlayImage of 0 bytes, 8 MiB, 8 MiB + 1: 0",
	    {overlay("/app0/empty.png", 0, 0), overlay("/app0/max.png", 0, 0), overlay("/app0/big.png", 0, 0)},
	    {w(kSsSize), ok, w(kSsSize)});
	Rcs(on ? "screenshot SetOverlayImageWithOrigin(ok.png) origin 0, 10, null path with origin 0: ERROR_ARGUMENT x3"
	       : "screenshot off: SetOverlayImageWithOrigin origin 0, 10, null: 0",
	    {overlay_o("/app0/ok.png", 0, 0, 0), overlay_o("/app0/ok.png", 0, 0, 10), overlay_o(nullptr, 0, 0, 0)},
	    {w(kSsArg), w(kSsArg), w(kSsArg)});
	Rcs(std::string(off) + "screenshot SetOverlayImageWithOrigin(ok.png) origin 1 at (0, 0), origin 9 at (3839, 2159): 0, 0",
	    {overlay_o("/app0/ok.png", 0, 0, 1), overlay_o("/app0/ok.png", 3839, 2159, 9)}, {ok, ok});
	Rcs(on ? "screenshot SetOverlayImageWithOrigin origin 5: x 3840, missing, 8 MiB + 1: ARGUMENT, OVERLAY_FILE, OVERLAY_SIZE"
	       : "screenshot off: SetOverlayImageWithOrigin origin 5, three bad images: 0",
	    {overlay_o("/app0/ok.png", 3840, 0, 5), overlay_o("/app0/missing.png", 0, 0, 5), overlay_o("/app0/big.png", 0, 0, 5)},
	    {w(kSsArg), w(kSsFile), w(kSsSize)});
	const int fd1 = Libs::LibKernel::FileSystem::KernelOpen("/app0/ok.png", 0, 0);
	if (fd1 >= 0) {
		(void)Libs::LibKernel::FileSystem::KernelClose(fd1);
	}
	Report("screenshot no descriptor left open: the next open gets the same descriptor", fd1 == fd0 && fd1 >= 0,
	       Fmt("%d, then %d", fd0, fd1));
	HeldZero(std::string(off) + "screenshot the 7 held calls (Dummy, Capture, GetAppInfo, Get/SetDrcParam, IsVsh..., SetParam): 0",
	         {"AS45QoYHjc4", "JuMLLmmvRgk", "hNmK4SdhPT0", "VlAQIgXa2R0", "ICNJ-1POs84", "G7KlmIYFIZc", "itlWFWV3Tzc"}, lib);
}

// =====================================================================================================================
// DiscMap
// =====================================================================================================================
constexpr int kNoBitmap = static_cast<int>(0x81100004u);

void CaseDiscMap() {
	g_case          = "discmap";
	const char* lib = "libSceDiscMap";
	const bool  on  = g_dm;
	const char* off = on ? "" : "off: ";
	const int   nb  = on ? kNoBitmap : 0;

	Rc("discmap registration: 5 NIDs", Registered({"fl1eoDnwQ4s", "lbQKqsERhtE", "fJgP+wqifno", "ioKMruft1ek", "5+vOlukvkfg"}, lib),
	   5);
	const auto on_hdd = Fn<IFn<const char*, int64_t, int64_t, int32_t*>>("lbQKqsERhtE", lib);
	const auto blocks = Fn<IFn<const char*, int64_t, int64_t, uint64_t*, uint64_t*, uint64_t*>>("ioKMruft1ek", lib);
	auto       result = static_cast<int32_t>(kS32);
	int        r      = on_hdd("/app0/ok.png", 0, 16, &result);
	Rc(std::string(off) + (on ? "discmap IsRequestOnHDD: NO_BITMAP_INFO, nothing written" : "discmap IsRequestOnHDD: 0, nothing written"),
	   r, nb, result == static_cast<int32_t>(kS32));
	Rc(std::string(off) + "discmap IsRequestOnHDD(null, -1, -1, null): the same, no argument read", on_hdd(nullptr, -1, -1, nullptr), nb);
	uint64_t a = kS64, b = kS64, c = kS64;
	r          = blocks("/app0/ok.png", 0, 16, &a, &b, &c);
	Rc(std::string(off) + (on ? "discmap ioKMruft1ek: NO_BITMAP_INFO, nothing written" : "discmap ioKMruft1ek: 0, nothing written"),
	   r, nb, a == kS64 && b == kS64 && c == kS64);
	Rc(std::string(off) + "discmap ioKMruft1ek(null, ..., null): the same, no argument read",
	   blocks(nullptr, 0, 0, nullptr, nullptr, nullptr), nb);
	HeldZero(std::string(off) + "discmap the 3 held calls (GetPackageSize, fJgP+wqifno, 5+vOlukvkfg): 0",
	         {"fl1eoDnwQ4s", "fJgP+wqifno", "5+vOlukvkfg"}, lib);
}

// =====================================================================================================================
// ulobjmgr
// =====================================================================================================================
void CaseUlobjmgr() {
	g_case          = "ulobjmgr";
	const char* lib = "ulobjmgr";
	const bool  on  = g_ul;
	const char* off = on ? "" : "off: ";
	const int   inv = on ? 22 : 0;

	Rc("ulobjmgr registration: 4 NIDs", Registered({"BG26hBGiNlw", "Smf+fUNblPc", "HZ9Q2c+4BU4", "SweJO7t3pkk"}, lib), 4);
	const auto reg   = Fn<IFn<uint64_t, int32_t, uint32_t*>>("BG26hBGiNlw", lib);
	const auto unreg = Fn<IFn<uint32_t>>("Smf+fUNblPc", lib);
	uint32_t   id    = kS32;
	const int  r0    = reg(0x1000, 1, &id);
	Rc(on ? "ulobjmgr RegisterObject(0x1000, 1, id): 0, id 0 written" : "ulobjmgr off: RegisterObject: 0, nothing written", r0, 0,
	   on ? id == 0 : id == kS32, Fmt("id 0x%08x", id));
	id      = kS32;
	int r1  = reg(0, 1, &id);
	int r2  = reg(0x1000, 0, &id);
	int r3  = reg(0x1000, 1, nullptr);
	Rcs(on ? "ulobjmgr RegisterObject with a zero object, a zero kind, a null id: EINVAL (22) x3, nothing written"
	       : "ulobjmgr off: RegisterObject's three bad calls: 0",
	    {r1, r2, r3}, {inv, inv, inv}, id == kS32);
	Rcs(std::string(off) + "ulobjmgr UnregisterObject(0), (0x3fff): 0, 0", {unreg(0), unreg(0x3fff)}, {0, 0});
	Rcs(on ? "ulobjmgr UnregisterObject(0x4000), (0xffffffff): EINVAL (22) x2" : "ulobjmgr off: UnregisterObject(0x4000), (0xffffffff): 0",
	    {unreg(0x4000), unreg(0xffffffffu)}, {inv, inv});
	HeldZero(std::string(off) + "ulobjmgr the 2 held calls: 0", {"HZ9Q2c+4BU4", "SweJO7t3pkk"}, lib);
}

// =====================================================================================================================
// CompanionHttpd and CompanionUtil
// =====================================================================================================================
constexpr int kHInvalid     = static_cast<int>(0x80E40004u);
constexpr int kHNotInit     = static_cast<int>(0x80E40006u);
constexpr int kHAlreadyInit = static_cast<int>(0x80E40007u);
constexpr int kHNoEvent     = static_cast<int>(0x80E40008u);
constexpr int kHStarted     = static_cast<int>(0x80E4000Au);
constexpr int kHNotStarted  = static_cast<int>(0x80E4000Bu);
constexpr int kHRegistered  = static_cast<int>(0x80E4000Cu);
constexpr int kUNoEvent     = static_cast<int>(0x80AD0008u);

int KYTY_SYSV_ABI RequestCallback(int, int, const void*, void*, void*) { // never called: no companion device connects
	std::printf("tbv0405: FAIL the request callback was called\n");
	std::fflush(stdout);
	std::_Exit(4);
}

void CaseCompanionHttpd() {
	g_case          = "companionhttpd";
	const char* lib = "libSceCompanionHttpd";
	const bool  on  = g_httpd;
	const char* off = on ? "" : "off: ";
	auto        w   = [on](int x) { return on ? x : 0; };

	Rc("companionhttpd registration: 17 NIDs",
	   Registered({"8pWltDG7h6A", "B-QBMeFdNgY", "Vku4big+IYM", "0SySxcuVNG0", "ykNpWs3ktLY", "OA6FbORefbo", "r-2-a0c7Kfc",
	               "fHNmij7kAUM", "OaWw+IVEdbI", "-0c9TCTwnGs", "h3OvVxzX4qM", "w7oz0AWHpT4", "k7F0FcDM-Xc", "0SCgzfVQHpo",
	               "+-du9tWgE9s", "ZSHiUfYK+QI", "xweOi2QT-BE"},
	              lib),
	   17);
	const auto get_event = Fn<IFn<void*>>("Vku4big+IYM", lib);
	const auto init      = Fn<IFn<const void*>>("ykNpWs3ktLY", lib);
	const auto init2     = Fn<IFn<>>("OA6FbORefbo", lib);
	const auto opt_init  = Fn<IFn<void*>>("r-2-a0c7Kfc", lib);
	const auto reg       = Fn<IFn<const void*, void*>>("OaWw+IVEdbI", lib);
	const auto start     = Fn<IFn<>>("k7F0FcDM-Xc", lib);
	const auto stop      = Fn<IFn<>>("0SCgzfVQHpo", lib);
	const auto term      = Fn<IFn<>>("+-du9tWgE9s", lib);
	const auto unreg     = Fn<IFn<>>("xweOi2QT-BE", lib);
	const auto cb        = reinterpret_cast<const void*>(reinterpret_cast<uintptr_t>(&RequestCallback)); // as a title passes it
	uint8_t    event[64];
	uint8_t    opt[0x70];
	int        arg = 0;

	std::memset(event, 0xA5, sizeof(event));
	int r = get_event(event);
	Rc(on ? "companionhttpd GetEvent before Initialize: NOT_INITIALIZED, nothing written" : "companionhttpd off: GetEvent: 0, nothing written",
	   r, w(kHNotInit), AllBytes(event, sizeof(event), 0xA5));
	Rc(on ? "companionhttpd GetEvent(null): INVALID_PARAM (checked first)" : "companionhttpd off: GetEvent(null): 0", get_event(nullptr),
	   w(kHInvalid));
	Rcs(on ? "companionhttpd before Initialize: Start, Stop, Terminate, UnregisterRequestCallback: NOT_INITIALIZED x4"
	       : "companionhttpd off: Start, Stop, Terminate, UnregisterRequestCallback: 0",
	    {start(), stop(), term(), unreg()}, {w(kHNotInit), w(kHNotInit), w(kHNotInit), w(kHNotInit)});
	Rcs(on ? "companionhttpd before Initialize: RegisterRequestCallback(f): NOT_INITIALIZED; (null): INVALID_PARAM"
	       : "companionhttpd off: RegisterRequestCallback(f), (null): 0",
	    {reg(cb, &arg), reg(nullptr, &arg)}, {w(kHNotInit), w(kHInvalid)});
	Rc(on ? "companionhttpd OptParamInitialize(null): INVALID_PARAM" : "companionhttpd off: OptParamInitialize(null): 0", opt_init(nullptr),
	   w(kHInvalid));
	std::memset(opt, 0xA5, sizeof(opt));
	const int ro = opt_init(opt);
	Rc(on ? "companionhttpd OptParamInitialize: 0, the 0x60 bytes cleared, the next ones untouched"
	      : "companionhttpd off: OptParamInitialize: 0, nothing written",
	   ro, 0, on ? (AllBytes(opt, 0x60, 0) && AllBytes(opt + 0x60, sizeof(opt) - 0x60, 0xA5)) : AllBytes(opt, sizeof(opt), 0xA5));
	Rc(on ? "companionhttpd Initialize(null): INVALID_PARAM" : "companionhttpd off: Initialize(null): 0", init(nullptr), w(kHInvalid));
	Rcs(on ? "companionhttpd Initialize, again: 0, ALREADY_INITIALIZED" : "companionhttpd off: Initialize twice: 0, 0",
	    {init(opt), init(opt)}, {0, w(kHAlreadyInit)});
	std::memset(event, 0xA5, sizeof(event));
	r = get_event(event);
	Rc(on ? "companionhttpd GetEvent: NO_EVENT, nothing written" : "companionhttpd off: GetEvent after Initialize: 0, nothing written", r,
	   w(kHNoEvent), AllBytes(event, sizeof(event), 0xA5));
	Rcs(on ? "companionhttpd RegisterRequestCallback, again: 0, ALREADY_REGISTERED" : "companionhttpd off: RegisterRequestCallback twice: 0, 0",
	    {reg(cb, &arg), reg(cb, &arg)}, {0, w(kHRegistered)});
	Rcs(on ? "companionhttpd Start, again: 0, ALREADY_STARTED" : "companionhttpd off: Start twice: 0, 0", {start(), start()},
	    {0, w(kHStarted)});
	Rcs(on ? "companionhttpd Stop, again: 0, NOT_STARTED" : "companionhttpd off: Stop twice: 0, 0", {stop(), stop()}, {0, w(kHNotStarted)});
	Rcs(std::string(off) + "companionhttpd UnregisterRequestCallback, again with none (adapted: today's 0): 0, 0", {unreg(), unreg()},
	    {0, 0});
	Rcs(on ? "companionhttpd Terminate, again: 0, NOT_INITIALIZED" : "companionhttpd off: Terminate twice: 0, 0", {term(), term()},
	    {0, w(kHNotInit)});
	Rcs(on ? "companionhttpd Initialize, Start, Terminate while started (adapted: stops and terminates), Start: 0, 0, 0, NOT_INITIALIZED"
	       : "companionhttpd off: Initialize, Start, Terminate, Start: 0 x4",
	    {init(opt), start(), term(), start()}, {0, 0, 0, w(kHNotInit)});
	Rcs(on ? "companionhttpd Initialize2 (held: today's 0, the library marked initialized), Start, Stop, Terminate, Terminate: 0 x4, "
	         "NOT_INITIALIZED"
	       : "companionhttpd off: Initialize2, Start, Stop, Terminate, Terminate: 0 x5",
	    {init2(), start(), stop(), term(), term()}, {0, 0, 0, 0, w(kHNotInit)});
	uint8_t   response[64];
	const int value = 200;
	std::memset(response, 0xA5, sizeof(response));
	const std::vector<int> built = {Fn<IFn<const char*, const char*, void*>>("8pWltDG7h6A", lib)("k", "v", response),
	                                Fn<IFn<int, void*>>("w7oz0AWHpT4", lib)(value, response),
	                                Fn<IFn<const char*, uint64_t, void*>>("h3OvVxzX4qM", lib)("b", 1, response)};
	Rcs(std::string(off) + "companionhttpd AddHeader, SetStatus, SetBody (already AnyPS5's answer): 0 x3, the response untouched", built,
	    {0, 0, 0}, AllBytes(response, sizeof(response), 0xA5));
	HeldZero(std::string(off) + "companionhttpd the 5 other held calls: 0",
	         {"B-QBMeFdNgY", "0SySxcuVNG0", "fHNmij7kAUM", "-0c9TCTwnGs", "ZSHiUfYK+QI"}, lib);
}

void CaseCompanionUtil() {
	g_case          = "companionutil";
	const char* lib = "libSceCompanionUtil";
	const bool  on  = g_util;
	const char* off = on ? "" : "off: ";

	Rc("companionutil registration: 5 NIDs", Registered({"cE5Msy11WhU", "MaVrz79mT5o", "xb1xlIhf0QY", "IPN-FRSrafk", "H1fYQd5lFAI"}, lib),
	   5);
	const auto get_event = Fn<IFn<void*>>("cE5Msy11WhU", lib);
	uint8_t    event[64];
	std::memset(event, 0xA5, sizeof(event));
	const int r = get_event(event);
	Rc(on ? "companionutil GetEvent: NO_EVENT, nothing written" : "companionutil off: GetEvent: 0, nothing written", r, on ? kUNoEvent : 0,
	   AllBytes(event, sizeof(event), 0xA5));
	Rc(on ? "companionutil GetEvent(null): NO_EVENT, nothing read" : "companionutil off: GetEvent(null): 0", get_event(nullptr),
	   on ? kUNoEvent : 0);
	HeldZero(std::string(off) + "companionutil GetRemoteOskEvent, Initialize, OptParamInitialize, Terminate (already the answer): 0",
	         {"MaVrz79mT5o", "xb1xlIhf0QY", "IPN-FRSrafk", "H1fYQd5lFAI"}, lib);
}

// =====================================================================================================================
// VideoRecording
// =====================================================================================================================
void CaseVideoRecording() {
	g_case          = "videorecording";
	const char* lib = "libSceVideoRecording";
	const char* off = g_vr ? "" : "off: ";

	Rc("videorecording registration: 1 NID", Registered({"Fc8qxlKINYQ"}, lib), 1);
	const auto  set_info = Fn<IFn<int32_t, const void*, uint64_t>>("Fc8qxlKINYQ", lib);
	const float volume   = 0.5f;
	Rcs(std::string(off) + "videorecording SetInfo (held) for 0x8002, 0xa004 and 0: 0 x3",
	    {set_info(0x8002, &volume, sizeof(volume)), set_info(0xa004, nullptr, 0), set_info(0, nullptr, 0)}, {0, 0, 0});
}

// ---- the subsystems a guest thread needs, as tbn0405.cpp starts them, with the file system ----------------------------
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
	(void)Common::Singleton<Loader::RuntimeLinker>::Instance(); // no program loaded: the process parameter is 0
	Libs::LibKernel::PthreadInitSelfForMainThread();            // the main thread becomes a guest thread
}

} // namespace tbv0405

int main(int argc, char** argv) {
	using namespace tbv0405;
	g_voice              = SwitchOn("KYTY_BC5_LOAD_VOICE");
	g_ss                 = SwitchOn("KYTY_BC5_LOAD_SCREENSHOT");
	g_dm                 = SwitchOn("KYTY_BC5_LOAD_DISCMAP");
	g_ul                 = SwitchOn("KYTY_BC5_LOAD_ULOBJMGR");
	g_httpd              = SwitchOn("KYTY_BC5_LOAD_COMPANIONHTTPD");
	g_util               = SwitchOn("KYTY_BC5_LOAD_COMPANIONUTIL");
	g_vr                 = SwitchOn("KYTY_BC5_LOAD_VIDEORECORDING");
	const bool  all_on   = g_voice && g_ss && g_dm && g_ul && g_httpd && g_util && g_vr;
	const bool  all_off  = !g_voice && !g_ss && !g_dm && !g_ul && !g_httpd && !g_util && !g_vr;
	const char* mode     = all_on ? "on" : (all_off ? "off" : "mixed");
	if (argc > 2 || (argc == 2 && std::strcmp(argv[1], mode) != 0)) {
		std::printf("tbv0405: the argument says %s but the switches say %s\n", argc == 2 ? argv[1] : "too much", mode);
		return 2;
	}
	std::printf("tbv0405: switches voice %d, screenshot %d, discmap %d, ulobjmgr %d, companionhttpd %d, companionutil %d, "
	            "videorecording %d: %s\n",
	            g_voice, g_ss, g_dm, g_ul, g_httpd, g_util, g_vr, mode);
	std::fflush(stdout);
	unsetenv("KYTY_BC5_APP0_OVERRIDE"); // /app0 is this test's mount only
	::Log::Bc5SetLogging(false);        // the kernel's LOGF lines stay off stdout
	std::thread(Watchdog).detach();

	char  arg0[] = "tbv0405";
	char* args[] = {arg0, nullptr};
	Init(1, args);

	g_case = "init: registration"; // each init prints its "[bc5] exp 0405: <table> port on|off" line on stderr
	Libs::LibVoice::InitVoice_1(&g_all);
	Libs::LibScreenShot::InitScreenShot_1(&g_all);
	Libs::LibDiscMap::InitDiscMap_1(&g_all);
	Libs::LibUlobjmgr::InitUlobjmgr_1(&g_all);
	Libs::CompanionHttpd::InitCompanionHttpd_1(&g_all);
	Libs::CompanionUtil::InitCompanionUtil_1(&g_all);
	Libs::LibVideoRecording::InitVideoRecording_1(&g_all);
	Libs::LibVoice::InitAudio_1_Voice(&g_all); // the live tables load after the switched ones (tl2)
	Libs::LibVoice::InitVoice_1(&g_dead_voice);
	Libs::LibVoice::InitAudio_1_Voice(&g_live_voice);

	CaseVoice();
	CaseScreenShot();
	CaseDiscMap();
	CaseUlobjmgr();
	CaseCompanionHttpd();
	CaseCompanionUtil();
	CaseVideoRecording();

	std::error_code ec;
	std::filesystem::remove_all(kApp0, ec);
	const int n = g_cases.load();
	const int p = g_passed.load();
	if (p != n) {
		std::printf("tbv0405: %s %d of %d passed; FAIL\n", mode, p, n);
		std::fflush(stdout);
		std::_Exit(1);
	}
	std::printf("tbv0405: %s %d of %d; end\n", mode, p, n);
	std::fflush(stdout);
	std::_Exit(0); // no static destructors: the Pthread subsystem's helper thread may still run
}
