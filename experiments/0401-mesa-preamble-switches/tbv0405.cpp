// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0405 (series e7 of experiment 0401), tag tbv: the CPU test of mktbv0405.py's edits (exp 0405 decision 4,
// dead-table batch 2) of src/libs/libVoice.cpp, libScreenShot.cpp, libDiscMap.cpp, libUlobjmgr.cpp, libCompanion.cpp and
// libAudio.cpp, behind KYTY_BC5_LOAD_VOICE, _SCREENSHOT, _DISCMAP, _ULOBJMGR, _COMPANIONHTTPD, _COMPANIONUTIL and
// KYTY_BC5_VOICE_PORTS (notes tbv0405-notes.md). It starts the subsystems a guest thread needs plus the file system (as
// tbn0405.cpp does), registers the six dead tables into its own SymbolDatabase by calling their LIB_DEFINEs in tl2's order
// (the switched tables first, then the live libSceVoice table of libs/libAudio.cpp; with a switch off the init still runs
// here, to call today's stubs), takes each function by its exact key (NID, library, versions) as a title's import resolves
// it, and calls it as a title would. Outputs start as a sentinel, so each case sees whether a call wrote them. With a dead
// table's switch on, its held stubs are not registered (exp 0327's "stubbed import called" line then shows a call); off,
// every NID is registered as today.
//   voice           VADSetVersion's versions; GetResourceInfo's null check before and after the live sceVoiceInit, its
//                   limits held; which of the 14 NIDs this table registers (the 8 held only with both switches off, the
//                   nine port calls never while KYTY_BC5_VOICE_PORTS is on), none registered twice, each resolving
//                   (Find and FindByNid, tl2's order) to the table that registered it; the registered stubs give 0.
//   voiceports      on: the live table registers the nine; CreatePort hands out the console's ids 0-127 and refuses a
//                   129th; the nine at both ends (0 and 127) and beyond (128, 254, 0xffffffff); the live calls through the
//                   id map; mute flags (CreatePort, SetMuteFlag, SetMuteFlagAll, UpdatePort), Pause/Resume/ResetPort,
//                   SetBitRate and UpdatePort against the live GetBitRate and GetVolume, the adapted answers, DeletePort,
//                   InitHQ and End resetting. off: the live table as today: ids 1 and 254 at both ends, 0 and 255 beyond.
//   screenshot      Disable / Enable / IsDisabled; SetOverlayImage(WithOrigin)'s checks in order, against files this test
//                   makes under ./tbv0405-app0 mounted at /app0 (a file, an empty file, 8 MiB, 8 MiB + 1, a directory, a
//                   missing file, 1023- and 1024-byte paths), no descriptor left open; the 7 held.
//   discmap         NO_BITMAP_INFO from IsRequestOnHDD and ioKMruft1ek, with and without arguments; the 3 held.
//   ulobjmgr        RegisterObject's EINVAL (22) cases and id 0, UnregisterObject's id limit; the 2 held.
//   companionhttpd  the server state (OptParamInitialize, Initialize, Register/Unregister, Start/Stop, Terminate,
//                   GetEvent), the two adapted answers, Initialize2 (adapted) marking the library initialized; the
//                   response calls give 0 with the response untouched; the 5 held.
//   companionutil   GetEvent's NO_EVENT, nothing written.
// Off, each ported call gives today's answer (0, nothing written). Each case follows its own table's switch (voice also
// KYTY_BC5_VOICE_PORTS), so any mix of switches is valid. No game, GPU, window, sound device, network, USB or camera.
// Prints one line per case and finally "tbv0405: on|off|mixed N of N; end" (all seven set: on; all unset or 0: off; else
// mixed); exit 0 only then. An optional argument "on"/"off"/"mixed" must match the switches (else exit 2). A watchdog ends a
// hang after 60 s with a FAIL line. Run it in a fresh directory: it writes ./tbv0405-app0 and removes it.
// Build: build0401.py ... src/libs/libVoice.cpp=<out>/src/libs/libVoice.cpp (and the other five units of mktbv0405.py,
//        libAudio.cpp among them) --gate tbv0405.cpp <bin> --like src/libs/libVoice.cpp

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
#include <cmath>
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <limits>
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
		same = same && i < want.size() && got[i] == want[i];
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
bool g_ports = false; // KYTY_BC5_VOICE_PORTS
bool g_ss    = false;
bool g_dm    = false;
bool g_ul    = false;
bool g_httpd = false;
bool g_util  = false;

// ---- registration and lookup ----------------------------------------------------------------------------------------
Loader::SymbolDatabase g_all;        // the six dead tables, then the live libSceVoice table (tl2's order)
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

// A table's held stubs: with its switch on none is registered; off, each is registered and gives today's 0.
void HeldCase(const std::string& name, const std::vector<const char*>& nids, const char* lib, bool on) {
	if (on) {
		const int n = Registered(nids, lib);
		Report(name + Fmt(": the %zu held stubs are not registered", nids.size()), n == 0, Fmt("%d registered", n));
		return;
	}
	int         zero = 0;
	std::string wrong;
	for (const char* nid: nids) {
		const uint64_t a = Addr(g_all, nid, lib);
		const int      v = a != 0 ? reinterpret_cast<IFn<>>(a)() : -1;
		if (a != 0 && v == 0) {
			zero++;
		} else {
			wrong += Fmt(" %s=%s", nid, a == 0 ? "absent" : Hex(v).c_str());
		}
	}
	Report(name + Fmt(" off: the %zu held stubs are registered and give 0", nids.size()), zero == static_cast<int>(nids.size()),
	       Fmt("%d of %zu%s", zero, nids.size(), wrong.c_str()));
}

// =====================================================================================================================
// Voice: the dead table (libVoice.cpp) and its split with the live one (libAudio.cpp)
// =====================================================================================================================
constexpr int kVoiceArg      = static_cast<int>(0x804E0805u);
constexpr int kVoicePort     = static_cast<int>(0x804E0804u);
constexpr int kVoiceNotFound = static_cast<int>(0x804E0807u);
constexpr int kVoiceFull     = static_cast<int>(0x804E0808u);

const std::vector<const char*> kVoiceLive = {"9TrhuGzberQ", "clyKUyi3RYU", "nXpje5yNpaE", "oV9GAdJ23Gw",
                                             "ajVj3QG2um4", "b7kJI+nx2hg", "Oo0S5PH7FIQ", "54phPH2LZls",
                                             "Ao2YNSA7-Qo", "cQ6DGsQEjV4", "YeJl6yDlhW0", "CrLqDwWLoXM",
                                             "elcxZTEfHZM", "cJLufzou6bc", "QBFoAIjJoXQ", "jjkCjneOYSs"};
// The dead table's 14, by group: always registered; SetMuteFlagAll; the 8 held here.
const std::vector<const char*> kVoiceBase = {"Z6QV6j7igvE", "Dinob0yMRl8", "jbkJFmOZ9U0", "hg9T73LlRiU", "wFeAxEeEi-8"};
constexpr char                 kVoiceMuteAll[] = "oUha0S-Ij9Q";
const std::vector<const char*> kVoiceHeld8 = {"Pc4z1QjForU", "IPHvnM5+g04", "x0slGBQW+wY", "udAxvCePkUs",
                                              "gAgN+HkiEzY", "TexwmOHQsDg", "gwUynkEgNFY", "jSZNP7xJrcw"};

bool InList(const std::vector<const char*>& list, const char* nid) {
	for (const char* n: list) {
		if (std::strcmp(n, nid) == 0) {
			return true;
		}
	}
	return false;
}

void CaseVoice() {
	g_case          = "voice";
	const char* lib = "libSceVoice";
	const bool  on  = g_voice;
	const char* off = on ? "" : "off: ";

	// Which table registers each of the 30 NIDs.
	std::vector<const char*> dead_all = kVoiceBase;
	dead_all.push_back(kVoiceMuteAll);
	dead_all.insert(dead_all.end(), kVoiceHeld8.begin(), kVoiceHeld8.end());
	int         right = 0;
	std::string wrong;
	for (const char* n: dead_all) {
		const bool dead      = Addr(g_dead_voice, n, lib) != 0;
		const bool live      = Addr(g_live_voice, n, "Voice") != 0;
		const bool is_base   = InList(kVoiceBase, n);
		const bool want_dead = is_base || (std::strcmp(n, kVoiceMuteAll) == 0 ? !g_ports : (!on && !g_ports));
		const bool want_live = !is_base && g_ports;
		if (dead == want_dead && live == want_live) {
			right++;
		} else {
			wrong += Fmt(" %s(dead %d live %d)", n, dead, live);
		}
	}
	for (const char* n: kVoiceLive) {
		const bool dead = Addr(g_dead_voice, n, lib) != 0;
		const bool live = Addr(g_live_voice, n, "Voice") != 0;
		if (!dead && live) {
			right++;
		} else {
			wrong += Fmt(" %s(dead %d live %d)", n, dead, live);
		}
	}
	const int want_dead_n = 5 + (g_ports ? 0 : 1) + ((!on && !g_ports) ? 8 : 0);
	Report(Fmt("voice registration (voice %d, voiceports %d): this table %d of its 14, the 8 held only with both off, the nine "
	           "port calls the live table's only while voiceports is on, none twice",
	           on, g_ports, want_dead_n),
	       right == 30, Fmt("%d of 30 right%s", right, wrong.c_str()));
	int resolved = 0;
	for (const char* n: dead_all) {
		const uint64_t d = Addr(g_dead_voice, n, lib);
		const uint64_t l = Addr(g_live_voice, n, "Voice");
		const uint64_t w = d != 0 ? d : l; // 0: registered by neither (held, the switch on)
		resolved += (Addr(g_all, n, lib) == w && ByNid(g_all, n) == w) ? 1 : 0;
	}
	for (const char* n: kVoiceLive) {
		const uint64_t l = Addr(g_live_voice, n, "Voice");
		resolved += (l != 0 && Addr(g_all, n, lib) == l && ByNid(g_all, n) == l) ? 1 : 0;
	}
	Report("voice in tl2's order: each of the 30 NIDs resolves (Find and FindByNid) to the table that registered it, or to "
	       "nothing",
	       resolved == 30, Fmt("%d of 30", resolved));

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

	// The stubs this table registers (all but VADSetVersion and GetResourceInfo) give today's 0.
	int         zero = 0, want = 0;
	std::string bad;
	for (const char* n: dead_all) {
		if (std::strcmp(n, "wFeAxEeEi-8") == 0 || std::strcmp(n, "Z6QV6j7igvE") == 0) {
			continue;
		}
		const uint64_t d = Addr(g_dead_voice, n, lib);
		if (d == 0) {
			continue;
		}
		want++;
		const int v = reinterpret_cast<IFn<>>(d)();
		zero += v == 0 ? 1 : 0;
		if (v != 0) {
			bad += Fmt(" %s=%s", n, Hex(v).c_str());
		}
	}
	const int want_stubs = 3 + (g_ports ? 0 : 1) + ((!on && !g_ports) ? 8 : 0);
	Report(Fmt("voice the %d stubs this table registers give 0", want_stubs), want == want_stubs && zero == want,
	       Fmt("%d of %d%s", zero, want, bad.c_str()));
}

// ---- voiceports: the live table (libAudio.cpp) with KYTY_BC5_VOICE_PORTS ---------------------------------------------
struct TestPortParam { // the 24-byte port parameter a title passes to sceVoiceCreatePort and sceVoiceUpdatePort
	int32_t  port_type;
	uint16_t threshold;
	uint16_t mute;
	float    volume;
	int32_t  word0; // a voice port's bitrate
	int32_t  word1;
	int32_t  word2;
};
static_assert(sizeof(TestPortParam) == 24);

TestPortParam PortParam(int32_t type, uint16_t mute, float volume, int32_t bitrate) {
	TestPortParam p {};
	p.port_type = type;
	p.mute      = mute;
	p.volume    = volume;
	p.word0     = bitrate;
	return p;
}

void CaseVoicePorts() {
	g_case             = "voiceports";
	const char* lib    = "libSceVoice";
	const bool  on     = g_ports;
	const auto  init   = Fn<IFn<void*, int32_t>>("9TrhuGzberQ", lib);
	const auto  create = Fn<IFn<uint32_t*, const TestPortParam*>>("nXpje5yNpaE", lib);
	const auto  del    = Fn<IFn<uint32_t>>("b7kJI+nx2hg", lib);
	const auto  end    = Fn<IFn<>>("Oo0S5PH7FIQ", lib);
	const auto  start  = Fn<IFn<const void*>>("54phPH2LZls", lib);
	const auto  stop   = Fn<IFn<>>("Ao2YNSA7-Qo", lib);
	const auto  info   = Fn<IFn<uint32_t, void*>>("CrLqDwWLoXM", lib);
	const auto  get_br = Fn<IFn<uint32_t, uint32_t*>>("cJLufzou6bc", lib);
	const auto  set_vo = Fn<IFn<uint32_t, float>>("QBFoAIjJoXQ", lib);
	const auto  get_vo = Fn<IFn<uint32_t, float*>>("jjkCjneOYSs", lib);
	auto        type_of = [&info](uint32_t id) {
        uint8_t buf[64] {};
        (void)info(id, buf);
        int32_t t = 0;
        std::memcpy(&t, buf, sizeof(t));
        return t;
	};
	auto volume_of = [&get_vo](uint32_t id) {
		float v = -9.0f;
		(void)get_vo(id, &v);
		return v;
	};
	auto rate_of = [&get_br](uint32_t id) {
		uint32_t v = kS32;
		(void)get_br(id, &v);
		return v;
	};
	uint8_t init_param[32] {};
	init_param[0] = 4;

	int nine = 0;
	for (const char* n: kVoiceHeld8) {
		nine += Addr(g_live_voice, n, "Voice") != 0 ? 1 : 0;
	}
	nine += Addr(g_live_voice, kVoiceMuteAll, "Voice") != 0 ? 1 : 0;
	Report(on ? "voiceports registration: the live table registers the nine port calls (25 NIDs)"
	          : "voiceports off: the live table registers none of the nine (16 NIDs, today's)",
	       nine == (on ? 9 : 0), Fmt("%d of the nine", nine));
	Rc("voiceports setup: the live sceVoiceInit", init(init_param, 100), 0);

	if (!on) {
		// Today's live table: ids 1-254, 0 and 255 beyond.
		std::vector<uint32_t> ids;
		int                   bad = 0;
		for (int i = 0; i < 254; i++) {
			const auto p  = PortParam(3, 0, i == 0 ? 0.75f : 0.5f, 0);
			uint32_t   id = kS32;
			bad += create(&id, &p) != 0 ? 1 : 0;
			ids.push_back(id);
		}
		bool in_order = bad == 0;
		for (uint32_t i = 0; i < ids.size(); i++) {
			in_order = in_order && ids[i] == i + 1;
		}
		Report("voiceports off: CreatePort x254 hands out 1-254 in order (today's)", in_order,
		       Fmt("%d failed, first %u, last %u", bad, ids.front(), ids.back()));
		uint32_t   id  = kS32;
		const auto p   = PortParam(3, 0, 0.5f, 0);
		const int  rf  = create(&id, &p);
		Rc("voiceports off: a 255th CreatePort: RESOURCE_INSUFFICIENT 0x804e0808, nothing written", rf, kVoiceFull, id == kS32);
		Report("voiceports off: the ends 1 and 254: the ports' volumes 0.75 and 0.5, types 3",
		       volume_of(1) == 0.75f && volume_of(254) == 0.5f && type_of(1) == 3 && type_of(254) == 3,
		       Fmt("%g %g, %d %d", static_cast<double>(volume_of(1)), static_cast<double>(volume_of(254)), type_of(1), type_of(254)));
		Report("voiceports off: beyond them, 0 and 255: no port (volume 1.0, type -1, today's defaults); 128 is a port",
		       volume_of(0) == 1.0f && volume_of(255) == 1.0f && type_of(0) == -1 && type_of(255) == -1 && type_of(128) == 3,
		       Fmt("%g %g, %d %d %d", static_cast<double>(volume_of(0)), static_cast<double>(volume_of(255)), type_of(0),
		           type_of(255), type_of(128)));
		Rc("voiceports off: the live sceVoiceEnd", end(), 0);
		return;
	}

	const auto get_mute = Fn<IFn<uint32_t, uint8_t*>>("Pc4z1QjForU", lib);
	const auto set_mute = Fn<IFn<uint32_t, uint8_t>>("gwUynkEgNFY", lib);
	const auto mute_all = Fn<IFn<uint8_t>>("oUha0S-Ij9Q", lib);
	const auto pause    = Fn<IFn<uint32_t>>("x0slGBQW+wY", lib);
	const auto resume   = Fn<IFn<uint32_t>>("gAgN+HkiEzY", lib);
	const auto reset    = Fn<IFn<uint32_t>>("udAxvCePkUs", lib);
	const auto set_rate = Fn<IFn<uint32_t, uint32_t>>("TexwmOHQsDg", lib);
	const auto update   = Fn<IFn<uint32_t, const TestPortParam*>>("jSZNP7xJrcw", lib);
	const auto init_hq  = Fn<IFn<void*, int32_t>>("IPHvnM5+g04", lib);
	auto       mute_of  = [&get_mute](uint32_t id) {
        uint8_t m = 0xA5;
        const int r = get_mute(id, &m);
        return r == 0 ? static_cast<int>(m) : r;
	};

	// The console's ids: 0-127, the first 0; a 129th port is refused.
	std::vector<uint32_t> ids;
	int                   bad = 0;
	for (int i = 0; i < 128; i++) {
		const auto p  = i == 0 ? PortParam(2, 1, 1.0f, 16000)   // console id 0: an input voice port, created muted
		              : i == 1 ? PortParam(4, 0, 1.0f, 16000)   // 1: an output voice port
		              : i == 2 ? PortParam(0, 0, 1.0f, 0)       // 2: an input device port
		                       : PortParam(3, 0, 0.5f, 0);      // the rest: output PCM ports
		uint32_t   id = kS32;
		bad += create(&id, &p) != 0 ? 1 : 0;
		ids.push_back(id);
	}
	bool in_order = bad == 0;
	for (uint32_t i = 0; i < ids.size(); i++) {
		in_order = in_order && ids[i] == i;
	}
	Report("voiceports CreatePort x128 hands out the console's ids 0-127 in order", in_order,
	       Fmt("%d failed, first %u, last %u", bad, ids.front(), ids.back()));
	uint32_t   extra = kS32;
	const auto pe    = PortParam(3, 0, 0.5f, 0);
	const int  rf    = create(&extra, &pe);
	Rc("voiceports a 129th CreatePort: RESOURCE_INSUFFICIENT 0x804e0808 (slots 129-254 stay unused), nothing written", rf,
	   kVoiceFull, extra == kS32);

	// The ends, 0 and 127, and beyond: 128, 254, 0xffffffff.
	Rcs("voiceports GetMuteFlag at the ends: 0 (created muted) gives 1, 127 gives 0", {mute_of(0), mute_of(127)}, {1, 0});
	uint8_t   m  = 0xA5;
	const int b1 = get_mute(128, &m);
	const int b2 = get_mute(254, &m);
	const int b3 = get_mute(0xffffffffu, &m);
	Rcs("voiceports GetMuteFlag beyond: 128, 254, 0xffffffff: INVALID_PORT, nothing written", {b1, b2, b3},
	    {kVoicePort, kVoicePort, kVoicePort}, m == 0xA5);
	Rcs("voiceports GetMuteFlag(0, null): INVALID_ARGUMENT; (128, null): INVALID_PORT (the id is checked first)",
	    {get_mute(0, nullptr), get_mute(128, nullptr)}, {kVoiceArg, kVoicePort});
	Report("voiceports the live calls through the map: GetPortInfo 0, 1, 2, 127 give types 2, 4, 0, 3; GetBitRate 0 gives 16000",
	       type_of(0) == 2 && type_of(1) == 4 && type_of(2) == 0 && type_of(127) == 3 && rate_of(0) == 16000,
	       Fmt("%d %d %d %d, %u", type_of(0), type_of(1), type_of(2), type_of(127), rate_of(0)));
	Report("voiceports the live calls beyond the map: GetPortInfo 128, 254: no port (-1); GetVolume 128: 1.0 (default)",
	       type_of(128) == -1 && type_of(254) == -1 && volume_of(128) == 1.0f,
	       Fmt("%d %d, %g", type_of(128), type_of(254), static_cast<double>(volume_of(128))));
	const int sv = set_vo(127, 0.25f); // each call before the checks that read its effect
	Rc("voiceports live SetVolume(127, 0.25), GetVolume(127): 0.25", sv, 0, volume_of(127) == 0.25f,
	   Fmt("%g", static_cast<double>(volume_of(127))));

	// Mute flags.
	Rcs("voiceports SetMuteFlag(127, 1), GetMuteFlag(127); SetMuteFlag(128, 1): 0, 1, INVALID_PORT",
	    {set_mute(127, 1), mute_of(127), set_mute(128, 1)}, {0, 1, kVoicePort});
	Rcs("voiceports SetMuteFlagAll(1): GetMuteFlag 1 and 2 read 1 (their own flags 0)", {mute_all(1), mute_of(1), mute_of(2)},
	    {0, 1, 1});
	Rcs("voiceports SetMuteFlagAll(0): GetMuteFlag 1 reads 0, 0 and 127 keep their own 1", {mute_all(0), mute_of(1), mute_of(0), mute_of(127)},
	    {0, 0, 1, 1});

	// Pause, resume, reset.
	Rcs("voiceports PausePort 0, ResumePort 0, PausePort 127: 0 x3", {pause(0), resume(0), pause(127)}, {0, 0, 0});
	Rcs("voiceports PausePort 128, ResumePort 0xffffffff, ResetPort 254: INVALID_PORT x3",
	    {pause(128), resume(0xffffffffu), reset(254)}, {kVoicePort, kVoicePort, kVoicePort});
	uint8_t start_param[32] {};
	Rcs("voiceports ResetPort 0, ResetPort 2 (a device port, not started): 0, 0", {reset(0), reset(2)}, {0, 0});
	Rcs("voiceports live Start, ResetPort 2 while started (adapted: today's 0, a catcher line), live Stop: 0 x3",
	    {start(start_param), reset(2), stop()}, {0, 0, 0});

	// Bitrate, against the live GetBitRate.
	const int sr1 = set_rate(0, 22533);
	Rc("voiceports SetBitRate(0, 22533): 0, the live GetBitRate(0) 22533", sr1, 0, rate_of(0) == 22533, Fmt("%u", rate_of(0)));
	const int sr2 = set_rate(0, 1234);
	const int sr3 = set_rate(127, 16000);
	Rcs("voiceports SetBitRate(0, 1234), (127 a PCM port, 16000) (adapted: today's 0, nothing changed): 0, 0", {sr2, sr3}, {0, 0},
	    rate_of(0) == 22533 && rate_of(127) == 48000, Fmt("%u %u", rate_of(0), rate_of(127)));
	Rc("voiceports SetBitRate(128, 16000): INVALID_PORT", set_rate(128, 16000), kVoicePort);

	// UpdatePort, against the live GetVolume and GetBitRate.
	const auto u1  = PortParam(4, 1, 0.25f, 7300);
	const int  up1 = update(1, &u1);
	Rc("voiceports UpdatePort(1, voice out, muted, 0.25, 7300): 0; mute 1, volume 0.25, bitrate 7300", up1, 0,
	   mute_of(1) == 1 && volume_of(1) == 0.25f && rate_of(1) == 7300,
	   Fmt("%d %g %u", mute_of(1), static_cast<double>(volume_of(1)), rate_of(1)));
	const auto             u2  = PortParam(2, 0, 0.75f, 16000); // another port type
	const auto             u3  = PortParam(4, 0, 0.75f, 999);   // a rate outside the list
	const std::vector<int> ups = {update(1, nullptr), update(1, &u2), update(1, &u3)};
	Rcs("voiceports UpdatePort(1, null), (1, another type), (1, rate 999) (adapted: today's 0, nothing changed): 0 x3", ups, {0, 0, 0},
	    mute_of(1) == 1 && volume_of(1) == 0.25f && rate_of(1) == 7300,
	    Fmt("%d %g %u", mute_of(1), static_cast<double>(volume_of(1)), rate_of(1)));
	Rcs("voiceports UpdatePort(128, p), (128, null): INVALID_PORT x2 (the id is checked first)", {update(128, &u1), update(128, nullptr)},
	    {kVoicePort, kVoicePort});
	const auto u4  = PortParam(3, 0, std::numeric_limits<float>::quiet_NaN(), 0);
	const int  up4 = update(127, &u4);
	Rc("voiceports UpdatePort(127, PCM, unmuted, volume NaN): 0; mute 0, volume 0", up4, 0, mute_of(127) == 0 && volume_of(127) == 0.0f,
	   Fmt("%d %g", mute_of(127), static_cast<double>(volume_of(127))));

	// DeletePort, a new port in the freed slot, InitHQ and End.
	uint8_t   mm = 0xA5;
	const int d1 = del(127);
	const int d2 = get_mute(127, &mm);
	Rcs("voiceports live DeletePort(127); then GetMuteFlag, PausePort, SetBitRate, UpdatePort(127): 0, PORT_NOT_FOUND x4",
	    {d1, d2, pause(127), set_rate(127, 16000), update(127, &u4)}, {0, kVoiceNotFound, kVoiceNotFound, kVoiceNotFound, kVoiceNotFound},
	    mm == 0xA5);
	uint32_t   again = kS32;
	const auto pa    = PortParam(3, 0, 0.5f, 0);
	const int  ra    = create(&again, &pa);
	Rcs("voiceports CreatePort after it: 0, id 127 again, unmuted", {ra}, {0}, again == 127 && mute_of(127) == 0,
	    Fmt("id %u, mute %d", again, mute_of(127)));
	Rcs("voiceports SetMuteFlagAll(1), InitHQ (this table's Init: ports and flags reset): 0, 0; GetMuteFlag(0) PORT_NOT_FOUND",
	    {mute_all(1), init_hq(init_param, 100), mute_of(0)}, {0, 0, kVoiceNotFound});
	uint32_t   first = kS32;
	const auto pf    = PortParam(3, 0, 0.5f, 0);
	const int  rfi   = create(&first, &pf);
	Rcs("voiceports CreatePort after InitHQ: 0, id 0, reads unmuted (the all-mute flag reset)", {rfi, mute_of(0)}, {0, 0},
	    first == 0, Fmt("id %u", first));
	Rcs("voiceports live sceVoiceEnd; then GetMuteFlag(0): 0, PORT_NOT_FOUND", {end(), mute_of(0)}, {0, kVoiceNotFound});
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

	const std::vector<const char*> held = {"AS45QoYHjc4", "JuMLLmmvRgk", "hNmK4SdhPT0", "VlAQIgXa2R0",
	                                       "ICNJ-1POs84", "G7KlmIYFIZc", "itlWFWV3Tzc"};
	Rc(on ? "screenshot registration: 7 of 14 (the ported and matching ones)" : "screenshot off: registration: 14 NIDs",
	   Registered({"AS45QoYHjc4", "JuMLLmmvRgk", "tIYf0W5VTi8", "ysfza71rm9M", "2xxUtuC-RzE", "BDUaqlVdSAY", "hNmK4SdhPT0",
	               "VlAQIgXa2R0", "-SV-oTNGFQk", "ICNJ-1POs84", "ahHhOf+QNkQ", "73WQ4Jj0nJI", "G7KlmIYFIZc", "itlWFWV3Tzc"},
	              lib),
	   on ? 7 : 14);
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
	HeldCase("screenshot (Dummy, Capture, GetAppInfo, Get/SetDrcParam, IsVsh..., SetParam)", held, lib, on);
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

	Rc(on ? "discmap registration: 2 of 5" : "discmap off: registration: 5 NIDs",
	   Registered({"fl1eoDnwQ4s", "lbQKqsERhtE", "fJgP+wqifno", "ioKMruft1ek", "5+vOlukvkfg"}, lib), on ? 2 : 5);
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
	HeldCase("discmap (GetPackageSize, fJgP+wqifno, 5+vOlukvkfg)", {"fl1eoDnwQ4s", "fJgP+wqifno", "5+vOlukvkfg"}, lib, on);
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

	Rc(on ? "ulobjmgr registration: 2 of 4" : "ulobjmgr off: registration: 4 NIDs",
	   Registered({"BG26hBGiNlw", "Smf+fUNblPc", "HZ9Q2c+4BU4", "SweJO7t3pkk"}, lib), on ? 2 : 4);
	const auto reg   = Fn<IFn<uint64_t, int32_t, uint32_t*>>("BG26hBGiNlw", lib);
	const auto unreg = Fn<IFn<uint32_t>>("Smf+fUNblPc", lib);
	uint32_t   id    = kS32;
	const int  r0    = reg(0x1000, 1, &id);
	Rc(on ? "ulobjmgr RegisterObject(0x1000, 1, id): 0, id 0 written" : "ulobjmgr off: RegisterObject: 0, nothing written", r0, 0,
	   on ? id == 0 : id == kS32, Fmt("id 0x%08x", id));
	id     = kS32;
	int r1 = reg(0, 1, &id);
	int r2 = reg(0x1000, 0, &id);
	int r3 = reg(0x1000, 1, nullptr);
	Rcs(on ? "ulobjmgr RegisterObject with a zero object, a zero kind, a null id: EINVAL (22) x3, nothing written"
	       : "ulobjmgr off: RegisterObject's three bad calls: 0",
	    {r1, r2, r3}, {inv, inv, inv}, id == kS32);
	Rcs(std::string(off) + "ulobjmgr UnregisterObject(0), (0x3fff): 0, 0", {unreg(0), unreg(0x3fff)}, {0, 0});
	Rcs(on ? "ulobjmgr UnregisterObject(0x4000), (0xffffffff): EINVAL (22) x2" : "ulobjmgr off: UnregisterObject(0x4000), (0xffffffff): 0",
	    {unreg(0x4000), unreg(0xffffffffu)}, {inv, inv});
	HeldCase("ulobjmgr", {"HZ9Q2c+4BU4", "SweJO7t3pkk"}, lib, on);
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

	Rc(on ? "companionhttpd registration: 12 of 17" : "companionhttpd off: registration: 17 NIDs",
	   Registered({"8pWltDG7h6A", "B-QBMeFdNgY", "Vku4big+IYM", "0SySxcuVNG0", "ykNpWs3ktLY", "OA6FbORefbo", "r-2-a0c7Kfc",
	               "fHNmij7kAUM", "OaWw+IVEdbI", "-0c9TCTwnGs", "h3OvVxzX4qM", "w7oz0AWHpT4", "k7F0FcDM-Xc", "0SCgzfVQHpo",
	               "+-du9tWgE9s", "ZSHiUfYK+QI", "xweOi2QT-BE"},
	              lib),
	   on ? 12 : 17);
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
	Rcs(on ? "companionhttpd Initialize2 (adapted: today's 0, the library marked initialized), Start, Stop, Terminate, Terminate: "
	         "0 x4, NOT_INITIALIZED"
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
	HeldCase("companionhttpd", {"B-QBMeFdNgY", "0SySxcuVNG0", "fHNmij7kAUM", "-0c9TCTwnGs", "ZSHiUfYK+QI"}, lib, on);
}

void CaseCompanionUtil() {
	g_case          = "companionutil";
	const char* lib = "libSceCompanionUtil";
	const bool  on  = g_util;
	const char* off = on ? "" : "off: ";

	Rc("companionutil registration: 5 NIDs (none held)",
	   Registered({"cE5Msy11WhU", "MaVrz79mT5o", "xb1xlIhf0QY", "IPN-FRSrafk", "H1fYQd5lFAI"}, lib), 5);
	const auto get_event = Fn<IFn<void*>>("cE5Msy11WhU", lib);
	uint8_t    event[64];
	std::memset(event, 0xA5, sizeof(event));
	const int r = get_event(event);
	Rc(on ? "companionutil GetEvent: NO_EVENT, nothing written" : "companionutil off: GetEvent: 0, nothing written", r, on ? kUNoEvent : 0,
	   AllBytes(event, sizeof(event), 0xA5));
	Rc(on ? "companionutil GetEvent(null): NO_EVENT, nothing read" : "companionutil off: GetEvent(null): 0", get_event(nullptr),
	   on ? kUNoEvent : 0);
	Rcs(std::string(off) + "companionutil GetRemoteOskEvent, Initialize, OptParamInitialize, Terminate (already the answer): 0 x4",
	    {Fn<IFn<>>("MaVrz79mT5o", lib)(), Fn<IFn<>>("xb1xlIhf0QY", lib)(), Fn<IFn<>>("IPN-FRSrafk", lib)(), Fn<IFn<>>("H1fYQd5lFAI", lib)()},
	    {0, 0, 0, 0});
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

// Reads the seven switches; the mode they give.
const char* ReadSwitches() {
	g_voice            = SwitchOn("KYTY_BC5_LOAD_VOICE");
	g_ports            = SwitchOn("KYTY_BC5_VOICE_PORTS");
	g_ss               = SwitchOn("KYTY_BC5_LOAD_SCREENSHOT");
	g_dm               = SwitchOn("KYTY_BC5_LOAD_DISCMAP");
	g_ul               = SwitchOn("KYTY_BC5_LOAD_ULOBJMGR");
	g_httpd            = SwitchOn("KYTY_BC5_LOAD_COMPANIONHTTPD");
	g_util             = SwitchOn("KYTY_BC5_LOAD_COMPANIONUTIL");
	const bool all_on  = g_voice && g_ports && g_ss && g_dm && g_ul && g_httpd && g_util;
	const bool all_off = !g_voice && !g_ports && !g_ss && !g_dm && !g_ul && !g_httpd && !g_util;
	return all_on ? "on" : (all_off ? "off" : "mixed");
}

// tl2's order: the switched tables, then the live ones; and the two Voice tables alone.
void RegisterTables() {
	g_case = "init: registration"; // each init prints its "[bc5] exp 0405: <table> port on|off" line on stderr
	Libs::LibVoice::InitVoice_1(&g_all);
	Libs::LibScreenShot::InitScreenShot_1(&g_all);
	Libs::LibDiscMap::InitDiscMap_1(&g_all);
	Libs::LibUlobjmgr::InitUlobjmgr_1(&g_all);
	Libs::CompanionHttpd::InitCompanionHttpd_1(&g_all);
	Libs::CompanionUtil::InitCompanionUtil_1(&g_all);
	Libs::LibVoice::InitAudio_1_Voice(&g_all); // the live table loads after the switched ones (tl2)
	Libs::LibVoice::InitVoice_1(&g_dead_voice);
	Libs::LibVoice::InitAudio_1_Voice(&g_live_voice);
}

void RunCases() {
	CaseVoice();
	CaseVoicePorts();
	CaseScreenShot();
	CaseDiscMap();
	CaseUlobjmgr();
	CaseCompanionHttpd();
	CaseCompanionUtil();
}

[[noreturn]] void Finish(const char* mode) {
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

} // namespace tbv0405

int main(int argc, char** argv) {
	using namespace tbv0405;
	const char* mode = ReadSwitches();
	if (argc > 2 || (argc == 2 && std::strcmp(argv[1], mode) != 0)) {
		std::printf("tbv0405: the argument says %s but the switches say %s\n", argc == 2 ? argv[1] : "too much", mode);
		return 2;
	}
	std::printf("tbv0405: switches voice %d, voiceports %d, screenshot %d, discmap %d, ulobjmgr %d, companionhttpd %d, "
	            "companionutil %d: %s\n",
	            g_voice, g_ports, g_ss, g_dm, g_ul, g_httpd, g_util, mode);
	std::fflush(stdout);
	unsetenv("KYTY_BC5_APP0_OVERRIDE"); // /app0 is this test's mount only
	::Log::Bc5SetLogging(false);        // the kernel's LOGF lines stay off stdout
	std::thread(Watchdog).detach();

	char  arg0[] = "tbv0405";
	char* args[] = {arg0, nullptr};
	Init(1, args);
	RegisterTables();
	RunCases();
	Finish(mode);
}
