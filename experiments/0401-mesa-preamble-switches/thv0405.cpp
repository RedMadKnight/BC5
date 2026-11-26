// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0405 (series e7 of experiment 0401), tag thv: the CPU test of mkthv0405.py's ports (exp 0405 decision 4,
// dead-table batch 2, hardware group) in src/libs/libHmd.cpp, libVrTracker.cpp and libMove.cpp, behind KYTY_BC5_LOAD_HMD,
// KYTY_BC5_LOAD_VRTRACKER and KYTY_BC5_LOAD_MOVE (notes thv0405-notes.md). It starts the subsystems a guest thread needs
// (as tbn0405.cpp does), registers the three tables into its own SymbolDatabase by calling their LIB_DEFINEs (with a
// switch off the init still runs here, to call today's stubs), takes each function by its exact key (NID, library,
// versions) as a title's import resolves it, and calls it as a title would. Outputs start as a sentinel, so each case sees
// whether a call wrote them. No headset, tracker, camera or Move controller is needed or opened: every port answers for a
// console with none attached.
//   hmd        on: the 17 ported or matching NIDs registered, the 120 held ones not; Initialize / Initialize315 /
//              Terminate state and argument checks; Open's checks and DEVICE_DISCONNECTED; the handle calls'
//              HANDLE_INVALID / NOT_INITIALIZED; GetDeviceInformation's 32 bytes; GetAssyError, GetFieldOfView,
//              InternalGetDeviceStatus; the 5 matching calls give 0.
//   vrtracker  on: the 10 ported NIDs registered, the 29 held ones not; QueryMemory's sizes and checks; Init's checks
//              (the 0x80-byte parameter) and state; the 144-byte parameter's held answer; device registration,
//              unregistration, recalibration, tracking duration; GpuWaitAndCpuProcess; Term keeps the handles.
//   move       on: the 11 ported NIDs; Init / Term; Open's handles (0x30B0100, then every 0x100) and ALREADY_OPENED;
//              the no-controller answer 1; the order init, arguments, handle; Close; another user's held answer.
//   off (each table): every NID registered, every call gives today's 0 and writes nothing.
// Each case follows its own table's switch, so any mix of switches is valid. No game, GPU, window, sound device, network,
// USB, camera or VR device. Prints one line per case and finally "thv0405: on|off|mixed N of N; end" (all set: on; all
// unset or 0: off; else mixed); exit 0 only then. An optional argument "on"/"off"/"mixed" must match the switches (else
// exit 2). A watchdog ends a hang after 60 s with a FAIL line. Run it in a fresh directory (it writes no file).
// Build: build0401.py ... src/libs/libHmd.cpp=<out>/src/libs/libHmd.cpp (and libVrTracker.cpp, libMove.cpp of
//        mkthv0405.py) --gate thv0405.cpp <bin> --like src/libs/libHmd.cpp

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
#include <string>
#include <thread>
#include <vector>

namespace Libs {
namespace LibHmd {
LIB_DEFINE(InitHmd_1);
} // namespace LibHmd
namespace LibVrTracker {
LIB_DEFINE(InitVrTracker_1);
} // namespace LibVrTracker
namespace LibMove {
LIB_DEFINE(InitMove_1);
} // namespace LibMove
} // namespace Libs

namespace thv0405 {

template <typename... A>
using IFn = int (KYTY_SYSV_ABI*)(A...);

constexpr int      kWatchdogSeconds = 60;
constexpr uint8_t  kS8              = 0x5A; // a byte the call has not written
constexpr uint32_t kS32             = 0x5A5A5A5Au;

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
	std::printf("thv0405: case %d %s: %s (%s)\n", g_cases.load(), name.c_str(), ok ? "ok" : "FAIL", info.c_str());
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
	std::printf("thv0405: FAIL setup: %s\n", what.c_str());
	std::fflush(stdout);
	std::_Exit(2);
}

void Watchdog() {
	std::this_thread::sleep_for(std::chrono::seconds(kWatchdogSeconds));
	std::printf("thv0405: FAIL watchdog: case \"%s\" still running after %d s (a hang); %d of %d cases passed before it\n",
	            g_case.load(), kWatchdogSeconds, g_passed.load(), g_cases.load());
	std::fflush(stdout);
	std::_Exit(3);
}

// The units' rule (env_flag.hpp): set, non-empty and not "0" is on.
bool SwitchOn(const char* name) {
	const char* e = std::getenv(name);
	return e != nullptr && e[0] != '\0' && std::strcmp(e, "0") != 0;
}

bool g_hmd  = false;
bool g_vr   = false;
bool g_move = false;

// ---- registration and lookup ----------------------------------------------------------------------------------------
Loader::SymbolDatabase g_all; // the three tables

uint64_t Addr(const char* nid, const char* lib) {
	Loader::SymbolResolve sr {};
	sr.name                 = nid;
	sr.library              = lib;
	sr.library_version      = 1;
	sr.module               = lib;
	sr.module_version_major = 1;
	sr.module_version_minor = 1;
	sr.type                 = Loader::SymbolType::Func;
	const auto* r           = g_all.Find(sr);
	return r != nullptr ? r->vaddr : 0;
}

template <typename F>
F Fn(const char* nid, const char* lib) {
	const uint64_t a = Addr(nid, lib);
	if (a == 0) {
		SetupFail(Fmt("%s (%s) is not registered", nid, lib));
	}
	return reinterpret_cast<F>(a);
}

int Registered(const std::vector<const char*>& nids, const char* lib) {
	int n = 0;
	for (const char* nid: nids) {
		n += Addr(nid, lib) != 0 ? 1 : 0;
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

uint32_t Get32(const void* p, size_t at) {
	uint32_t v = 0;
	std::memcpy(&v, static_cast<const uint8_t*>(p) + at, sizeof(v));
	return v;
}

void Put32(std::vector<uint8_t>& b, size_t at, uint32_t v) {
	std::memcpy(b.data() + at, &v, sizeof(v));
}

void Put64(std::vector<uint8_t>& b, size_t at, uint64_t v) {
	std::memcpy(b.data() + at, &v, sizeof(v));
}

// Each NID called without arguments: today's 0 (a held stub with the switch off, or a call that already matches).
void ZeroCalls(const std::string& name, const std::vector<const char*>& nids, const char* lib) {
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

// The held NIDs: on, none is registered (a title's call reaches exp 0327's stubbed-import line); off, all are, giving 0.
void Held(const std::string& word, bool on, const std::vector<const char*>& nids, const char* lib) {
	if (on) {
		Rc(Fmt("%s the %zu held NIDs are not registered", word.c_str(), nids.size()), Registered(nids, lib), 0);
	} else {
		ZeroCalls(Fmt("%s off: the %zu held NIDs are registered and give 0", word.c_str(), nids.size()), nids, lib);
	}
}

// =====================================================================================================================
// Hmd
// =====================================================================================================================
constexpr int kHAlready     = static_cast<int>(0x81110001u);
constexpr int kHNotInit     = static_cast<int>(0x81110002u);
constexpr int kHHandle      = static_cast<int>(0x81110003u);
constexpr int kHDisconnect  = static_cast<int>(0x81110004u);
constexpr int kHNull        = static_cast<int>(0x81110008u);
constexpr int kHInvalid     = static_cast<int>(0x81110009u);
constexpr int kHUnsupported = static_cast<int>(0x81110016u);

const std::vector<const char*> kHmdPorted = {"6biw1XHTSqQ", "BWY-qKM5hxE", "Yx+CuF11D3Q", "thDt9upZlp8",
                                             "1pxQfif1rkE", "NPQwYFqi0bs", "rU3HK9Q0r8o", "K4KnH0QkT2c",
                                             "s-J66ar9g50", "PPCqsD8B5uM", "d2g5Ij7EUzo", "z-RMILqP6tE"};
// InternalMmapIsConnect and the four InternalIs*Vr2d queries: today's 0 is AnyPS5's answer.
const std::vector<const char*> kHmdMatch = {"1PNiQR-7L6k", "GwFVF2KkIT4", "LWQpWHOSUvk", "YiIVBPLxmfE", "LMlWs+oKHTg"};
const std::vector<const char*> kHmdHeld  = {
    "riPQfAdebHk", "wHnZU1qtiqw", "NuEjeN8WCBA", "QasPTUPWVZE", "Wr5KVtyVDG0", "whRxl6Hhrzg", "w8BEUsIYn8w", "0cQDAbkOt2A",
    "Asczi8gw1NM", "6+v7m1vwE+0", "E0BLvy57IiQ", "UTqrWB+1+SU", "ego1YdqNGpI", "WR7XsLdjcqQ", "eMI1Hq+NEwY", "dI3StPLQlMM",
    "lqPT-Bf1s4I", "QxhJs6zHUmU", "A2jWOLPzHHE", "E9scVxt0DNg", "6RclvsKxr3I", "cE99PJR6b8w", "SuE90Qscg0s", "5f-6lp7L5cY",
    "dv2RqD7ZBd4", "pN0HjRU86Jo", "mdc++HCXSsQ", "gjyqnphjGZE", "bl4MkWNLxKs", "a1LmvXhZ6TM", "+UzzSnc0z9A", "uQc9P8Hrr6U",
    "nK1g+MwMV10", "L5WZgOTw41Y", "3w8SkMfCHY0", "1Xmb76MHXug", "S0ITgPRkfUg", "mxjolbeBa78", "RFIi20Wp9j0", "P04LQJQZ43Y",
    "-u82z1UhOq4", "iINSFzCIaB8", "Csuvq2MMXHU", "UhFPniZvm8U", "aTg7K0466r8", "9exeDpk7JU8", "yNtYRsxZ6-A", "EKn+IFVsz0M",
    "AxQ6HtktYfQ", "ynKv9QCSbto", "3jcyx7XOm7A", "+PDyXnclP5w", "67q17ERGBuw", "uGyN1CkvwYU", "p9lSvZujLuo", "-Z+-9u98m9o",
    "df+b0FQnnVQ", "i6yROd9ygJs", "Aajiktl6JXU", "nBv4CKUGX0Y", "4hTD8I3CyAk", "EJwPtSSZykY", "r7f7M5q3snU", "gCjTEtEsOOw",
    "HAr740Mt9Hs", "9-jaAXUNG-A", "1gkbLH5+kxU", "6kHBllapJas", "k1W6RPkd0mc", "dp1wu22jSGc", "d2TeoKeqM5U", "WxsnAsjPF7Q",
    "eOOeG9SpEuc", "gA4Xnn+NSGk", "stQ7AsondmE", "jfnS-OoDayM", "roHN4ml+tB8", "0z2qLqedQH0", "xhx5rVZEpnw", "e7laRxRGCHc",
    "CRyJ7Q-ap3g", "dG4XPW4juU4", "rAXmGoO-VmE", "lu9I7jnUvWQ", "hyATMTuQSoQ", "c4mSi64bXUw", "U9kPT4g1mFE", "dX-MVpXIPwQ",
    "4KIjvAf8PCA", "NbxTfUKO184", "NnRKjf+hxW4", "4AP0X9qGhqw", "Mzzz2HPWM+8", "LkBkse9Pit0", "v243mvYg0Y0", "EwXvkZpo9Go",
    "g3DKNOy1tYw", "mjMsl838XM8", "8IS0KLkDNQY", "afhK5KcJOJY", "+zPvzIiB+BU", "9z8Lc64NF1c", "s5EqYh5kbwM", "a1LMFZtK9b0",
    "-6FjKlMA+Yc", "IC0NGmh-zS8", "NY2-gYo9ihI", "XMutp2-o9A4", "Y9QDFn3AjPA", "eRVgwy9PbWg", "fJVZYeqFttM", "mVIneDkja6c",
    "miduc55U7q8", "nlAZlOKJy+c", "ox9NqLO9LhI", "qS18I6w2SZM", "rczCXLh2-b4", "sWZSZB-mnw4", "-Bk71lPyry4", "-y4OUwFf4jE"};

void CaseHmd() {
	g_case          = "hmd";
	const char* lib = "libSceHmd";
	const bool  on  = g_hmd;
	const char* off = on ? "" : "off: ";
	const auto  W   = [on](int want) { return on ? want : 0; };

	Rc("hmd registration: the 12 ported and 5 matching NIDs", Registered(kHmdPorted, lib) + Registered(kHmdMatch, lib), 17);
	Held("hmd", on, kHmdHeld, lib);

	const auto close    = Fn<IFn<int32_t>>("6biw1XHTSqQ", lib);
	const auto eye      = Fn<IFn<int32_t, void*, void*>>("BWY-qKM5hxE", lib);
	const auto assy     = Fn<IFn<void*>>("Yx+CuF11D3Q", lib);
	const auto devinfo  = Fn<IFn<void*>>("thDt9upZlp8", lib);
	const auto byhandle = Fn<IFn<int32_t, void*>>("1pxQfif1rkE", lib);
	const auto fov      = Fn<IFn<int32_t, void*>>("NPQwYFqi0bs", lib);
	const auto inertial = Fn<IFn<int32_t, void*, uint32_t>>("rU3HK9Q0r8o", lib);
	const auto init     = Fn<IFn<const void*>>("K4KnH0QkT2c", lib);
	const auto init315  = Fn<IFn<const void*>>("s-J66ar9g50", lib);
	const auto status   = Fn<IFn<void*>>("PPCqsD8B5uM", lib);
	const auto open     = Fn<IFn<int32_t, int32_t, int32_t, const void*>>("d2g5Ij7EUzo", lib);
	const auto term     = Fn<IFn<>>("z-RMILqP6tE", lib);

	uint8_t a[64];
	uint8_t b[64];
	std::memset(a, kS8, sizeof(a));
	std::memset(b, kS8, sizeof(b));
	std::vector<uint8_t> zeros(16, 0);     // an InitializeParam with its first field null
	std::vector<uint8_t> with_ptr(16, 0);  // ... with its first field set
	Put64(with_ptr, 0, 0x10000);
	const std::vector<uint8_t> open_param(32, 0);

	// Each case's calls run first (a braced list runs left to right), then its checks of what they wrote.
	std::vector<int> got = {open(1000, 0, 0, nullptr), close(0), term(), byhandle(0, a), eye(0, a, b), inertial(0, a, 1)};
	Rcs(std::string(off) + "hmd before Initialize: Open, Close, Terminate, GetDeviceInformationByHandle, Get2DEyeOffset, "
	                       "GetInertialSensorData: NOT_INITIALIZED x6, nothing written",
	    got, std::vector<int>(6, W(kHNotInit)), AllBytes(a, sizeof(a), kS8) && AllBytes(b, sizeof(b), kS8));
	got = {devinfo(nullptr), devinfo(a)};
	Rcs(std::string(off) + "hmd before Initialize: GetDeviceInformation(null) PARAMETER_NULL, (info) NOT_INITIALIZED",
	    got, {W(kHNull), W(kHNotInit)}, AllBytes(a, sizeof(a), kS8));
	got = {fov(0, nullptr), fov(0, a)};
	Rcs(std::string(off) + "hmd before Initialize: GetFieldOfView(0, null) PARAMETER_NULL, (0, out) NOT_INITIALIZED", got,
	    {W(kHNull), W(kHNotInit)}, AllBytes(a, sizeof(a), kS8));
	got = {assy(nullptr), assy(a)};
	Rcs(std::string(off) + "hmd before Initialize: GetAssyError(null) PARAMETER_NULL, (out) NOT_INITIALIZED", got,
	    {W(kHNull), W(kHNotInit)}, AllBytes(a, sizeof(a), kS8));
	uint32_t st = kS32;
	got         = {status(nullptr), status(&st)};
	Rcs(on ? "hmd InternalGetDeviceStatus(null) PARAMETER_NULL, (out) 0 with 2 (not detected), before Initialize"
	       : "hmd off: InternalGetDeviceStatus(null), (out): 0, 0, nothing written",
	    got, {W(kHNull), 0}, on ? st == 2 : st == kS32, Fmt("status 0x%08x", st));
	Rcs(std::string(off) + "hmd Initialize / Initialize315 with null: PARAMETER_NULL; with the first field set: "
	                       "UNSUPPORTED_FEATURE; the library stays uninitialized",
	    {init(nullptr), init(with_ptr.data()), init315(nullptr), init315(with_ptr.data()), close(0)},
	    {W(kHNull), W(kHUnsupported), W(kHNull), W(kHUnsupported), W(kHNotInit)});
	Rcs(std::string(off) + "hmd Initialize: 0; again, Initialize315, Initialize with the first field set: "
	                       "ALREADY_INITIALIZED x3",
	    {init(zeros.data()), init(zeros.data()), init315(zeros.data()), init(with_ptr.data())},
	    {0, W(kHAlready), W(kHAlready), W(kHAlready)});
	Rcs(std::string(off) + "hmd Open(1000, 0, 0, null): DEVICE_DISCONNECTED; type 1, index 1, user -1, user 0xFF, a "
	                       "param: PARAMETER_INVALID x5",
	    {open(1000, 0, 0, nullptr), open(1000, 1, 0, nullptr), open(1000, 0, 1, nullptr), open(-1, 0, 0, nullptr),
	     open(0xFF, 0, 0, nullptr), open(1000, 0, 0, open_param.data())},
	    {W(kHDisconnect), W(kHInvalid), W(kHInvalid), W(kHInvalid), W(kHInvalid), W(kHInvalid)});
	got = {close(0), close(0x0F000000), byhandle(0, a), eye(0, a, b), inertial(0, a, 1)};
	Rcs(std::string(off) + "hmd Close(0), Close(0x0F000000), GetDeviceInformationByHandle, Get2DEyeOffset, "
	                       "GetInertialSensorData: HANDLE_INVALID x5, nothing written",
	    got, std::vector<int>(5, W(kHHandle)), AllBytes(a, sizeof(a), kS8) && AllBytes(b, sizeof(b), kS8));
	got = {fov(0, a), fov(0, nullptr)};
	Rcs(std::string(off) + "hmd GetFieldOfView(0, out) HANDLE_INVALID, (0, null) PARAMETER_NULL, nothing written", got,
	    {W(kHHandle), W(kHNull)}, AllBytes(a, sizeof(a), kS8));
	const int r = devinfo(a);
	const bool layout = on ? (Get32(a, 0) == 2 && Get32(a, 4) == 0xFFFFFFFFu && AllBytes(a + 8, 24, 0) &&
	                          AllBytes(a + 32, sizeof(a) - 32, kS8))
	                       : AllBytes(a, sizeof(a), kS8);
	Rc(on ? "hmd GetDeviceInformation: 0; 32 bytes: status 2, user -1, 24 zero bytes; the bytes after them untouched"
	      : "hmd off: GetDeviceInformation: 0, nothing written",
	   r, 0, layout, Fmt("status 0x%08x user 0x%08x", Get32(a, 0), Get32(a, 4)));
	std::memset(a, kS8, sizeof(a));
	const int ra = assy(a);
	Rc(std::string(off) + "hmd GetAssyError(out): DEVICE_DISCONNECTED, nothing written", ra, W(kHDisconnect),
	   AllBytes(a, sizeof(a), kS8));
	got = {term(), term(), devinfo(a), init315(zeros.data()), open(1000, 0, 0, nullptr), term()};
	Rcs(std::string(off) + "hmd Terminate 0, again NOT_INITIALIZED, GetDeviceInformation NOT_INITIALIZED, Initialize315 "
	                       "0, Open DEVICE_DISCONNECTED, Terminate 0",
	    got, {0, W(kHNotInit), W(kHNotInit), 0, W(kHDisconnect), 0}, AllBytes(a, sizeof(a), kS8));
	ZeroCalls(std::string(off) + "hmd the 5 calls that already match (InternalMmapIsConnect, the four InternalIs*Vr2d): 0",
	          kHmdMatch, lib);
}

// =====================================================================================================================
// VrTracker
// =====================================================================================================================
constexpr int kVNotInit      = static_cast<int>(0x81260801u);
constexpr int kVAlready      = static_cast<int>(0x81260802u);
constexpr int kVNotReg       = static_cast<int>(0x81260803u);
constexpr int kVAlreadyReg   = static_cast<int>(0x81260804u);
constexpr int kVArg          = static_cast<int>(0x81260806u);
constexpr int kVNoGpuSubmit  = static_cast<int>(0x81260815u);

const std::vector<const char*> kVrPorted = {"24kDA+A0Ox0", "ARhgpXvwoR0", "QkRl7pART9M", "K7yhYrsIBPc", "EUCaQtXXYNI",
                                            "sIh8GwcevaQ", "ufexf4aNiwg", "qBjnR0HtMYI", "IBv4P3q1pQ0", "Q8skQqEwn5c"};
const std::vector<const char*> kVrHeld   = {"5IFOAYv-62g", "zvyKP0Z3UvU", "76OBvrrQXUc", "XoeWzXlrnMw", "TVegDMLaBB8",
                                            "gkGuO9dd57M", "VItTwN8DmS8", "CtWUbFgmq+I", "E0P0sN-wy+4", "bDGZVTwwZ1A",
                                            "NhPkY3V8E+8", "vpsLLotiSUg", "lgWSHQ8p4i4", "9fvHMUbsom4", "D6TJSfjTAk4",
                                            "KFxq-AnEL34", "mmzbIQNmT4o", "tNJrfYsY3wY", "jGqEkPy0iLU", "ERmwvjmfN+c",
                                            "SSi0OBa8RA0", "hj7zLvyw+pw", "5ucmy8hcSPk", "9kB+RsZt84M", "sBkAqyF5Gns",
                                            "rvCywCbc7Pk", "lm6T1Ur6JRk", "qa1+CeXKDPc", "3YCwwpHkHIg"};

// A QueryMemory parameter (0x40 bytes): size, profile, then the calibration modes at +0x20 (headset, pad, Move, gun).
std::vector<uint8_t> VrQuery(uint32_t size, uint32_t profile, uint32_t headset, uint32_t pad, uint32_t move, uint32_t gun) {
	std::vector<uint8_t> q(0x40, 0);
	Put32(q, 0x00, size);
	Put32(q, 0x04, profile);
	Put32(q, 0x20, headset);
	Put32(q, 0x24, pad);
	Put32(q, 0x28, move);
	Put32(q, 0x2C, gun);
	return q;
}

// A valid Init parameter (0x80 bytes, room for 0x90): automatic pad, Move and gun calibration, so the onion block is
// 0x800000; blocks at made-up addresses (the library does not look them up); pipe 6, queue 7.
std::vector<uint8_t> VrInit() {
	std::vector<uint8_t> p(0x90, 0);
	Put32(p, 0x00, 0x80);
	Put32(p, 0x2C, 1); // pad
	Put32(p, 0x30, 1); // Move
	Put32(p, 0x34, 1); // gun
	Put64(p, 0x48, 0x100000000ull);
	Put32(p, 0x50, 0x800000);
	Put32(p, 0x54, 0x10000);
	Put64(p, 0x58, 0x200000000ull);
	Put32(p, 0x60, 0x3000000);
	Put32(p, 0x64, 0x10000);
	Put64(p, 0x68, 0x300000000ull);
	Put32(p, 0x70, 0x1000000);
	Put32(p, 0x74, 0x10000);
	Put32(p, 0x78, 6);
	Put32(p, 0x7C, 7);
	return p;
}

std::vector<uint8_t> With32(std::vector<uint8_t> p, size_t at, uint32_t v) {
	Put32(p, at, v);
	return p;
}

std::vector<uint8_t> With64(std::vector<uint8_t> p, size_t at, uint64_t v) {
	Put64(p, at, v);
	return p;
}

std::vector<uint8_t> VrRecal(uint32_t size, uint32_t type) {
	std::vector<uint8_t> p(0x20, 0);
	Put32(p, 0x00, size);
	Put32(p, 0x04, type);
	return p;
}

void CaseVrTracker() {
	g_case          = "vrtracker";
	const char* lib = "libSceVrTracker";
	const bool  on  = g_vr;
	const char* off = on ? "" : "off: ";
	const auto  W   = [on](int want) { return on ? want : 0; };

	Rc("vrtracker registration: the 10 ported NIDs", Registered(kVrPorted, lib), 10);
	Held("vrtracker", on, kVrHeld, lib);

	const auto reg2    = Fn<IFn<int32_t, int32_t>>("24kDA+A0Ox0", lib);
	const auto gpuwait = Fn<IFn<>>("ARhgpXvwoR0", lib);
	const auto init    = Fn<IFn<const void*>>("QkRl7pART9M", lib);
	const auto query   = Fn<IFn<const void*, void*>>("K7yhYrsIBPc", lib);
	const auto recal   = Fn<IFn<const void*>>("EUCaQtXXYNI", lib);
	const auto reg     = Fn<IFn<int32_t, int32_t>>("sIh8GwcevaQ", lib);
	const auto regi    = Fn<IFn<int32_t, int32_t, int32_t, int32_t>>("ufexf4aNiwg", lib);
	const auto setdur  = Fn<IFn<int32_t, uint32_t>>("qBjnR0HtMYI", lib);
	const auto term    = Fn<IFn<>>("IBv4P3q1pQ0", lib);
	const auto unreg   = Fn<IFn<int32_t>>("Q8skQqEwn5c", lib);

	uint8_t res[0x48];
	std::memset(res, kS8, sizeof(res));
	const auto q0 = VrQuery(0x40, 0, 0, 0, 0, 0);
	int        r  = query(q0.data(), res);
	const bool q0_ok =
	    on ? (AllBytes(res, 4, kS8) && Get32(res, 0x04) == 0x400000 && Get32(res, 0x08) == 0x10000 &&
	          Get32(res, 0x0C) == 0x3000000 && Get32(res, 0x10) == 0x10000 && Get32(res, 0x14) == 0x1000000 &&
	          Get32(res, 0x18) == 0x10000 && AllBytes(res + 0x1C, sizeof(res) - 0x1C, kS8))
	       : AllBytes(res, sizeof(res), kS8);
	Rc(on ? "vrtracker QueryMemory(profile 0, manual) before Init: 0; onion 0x400000, garlic 0x3000000, work 0x1000000, "
	        "each aligned 0x10000, at +4..+0x1B; the size field and the rest untouched"
	      : "vrtracker off: QueryMemory: 0, nothing written",
	   r, 0, q0_ok, Fmt("onion 0x%08x garlic 0x%08x work 0x%08x", Get32(res, 4), Get32(res, 0xC), Get32(res, 0x14)));
	std::memset(res, kS8, sizeof(res));
	const auto q1 = VrQuery(0x40, 100, 0, 1, 1, 1);
	r             = query(q1.data(), res);
	Rc(on ? "vrtracker QueryMemory(profile 100, automatic pad, Move, gun): 0, onion 0x800000"
	      : "vrtracker off: QueryMemory(profile 100, ...): 0, nothing written",
	   r, 0, on ? Get32(res, 4) == 0x800000 : AllBytes(res, sizeof(res), kS8), Fmt("onion 0x%08x", Get32(res, 4)));
	std::memset(res, kS8, sizeof(res));
	const std::vector<std::vector<uint8_t>> bad = {VrQuery(0x3C, 0, 0, 0, 0, 0), VrQuery(0x40, 50, 0, 0, 0, 0),
	                                               VrQuery(0x40, 0, 1, 0, 0, 0), VrQuery(0x40, 0, 0, 2, 0, 0),
	                                               VrQuery(0x40, 0, 0, 0, 2, 0), VrQuery(0x40, 0, 0, 0, 0, 2)};
	std::vector<int> got = {query(nullptr, res), query(q0.data(), nullptr)};
	for (const auto& q: bad) {
		got.push_back(query(q.data(), res));
	}
	Rcs(std::string(off) + "vrtracker QueryMemory: null param, null result, size 0x3C, profile 50, automatic headset, pad 2, "
	                       "Move 2, gun 2: ARGUMENT_INVALID x8, nothing written",
	    got, std::vector<int>(8, W(kVArg)), AllBytes(res, sizeof(res), kS8));

	const auto ok   = VrInit();
	const auto rc1  = VrRecal(0x20, 1);
	Rcs(std::string(off) + "vrtracker before Init: Term, RegisterDevice, RegisterDevice2, RegisterDeviceInternal, "
	                       "UnregisterDevice, Recalibrate, SetDurationUntilStatusNotTracking, GpuWaitAndCpuProcess: NOT_INIT x8",
	    {term(), reg(1, 0x100), reg2(1, 0x100), regi(1, 0x100, -1, 0), unreg(0x100), recal(rc1.data()), setdur(0, 30),
	     gpuwait()},
	    std::vector<int>(8, W(kVNotInit)));
	const std::vector<std::vector<uint8_t>> bad_init = {
	    With32(ok, 0x00, 0x7C),     With64(ok, 0x58, 0),          With32(ok, 0x64, 0x1000),      With32(ok, 0x60, 0x2000000),
	    With64(ok, 0x48, 0),        With32(ok, 0x50, 0x400000),   With32(ok, 0x74, 0x20000),     With32(ok, 0x70, 0),
	    With64(ok, 0x68, 0),        With32(ok, 0x78, 7),          With32(ok, 0x7C, 8),           With32(ok, 0x78, 0xFFFFFFFFu),
	    With32(ok, 0x28, 1)};
	got = {init(nullptr)};
	for (const auto& p: bad_init) {
		got.push_back(init(p.data()));
	}
	got.push_back(gpuwait());
	Rcs(std::string(off) + "vrtracker Init: null, size 0x7C, null garlic, garlic alignment 0x1000, garlic size, null onion, "
	                       "onion 0x400000 with automatic Move, work alignment, work size 0, null work, pipe 7, queue 8, pipe "
	                       "-1, automatic headset: ARGUMENT_INVALID x14; still not initialized",
	    got, [&] {
		    std::vector<int> w(14, W(kVArg));
		    w.push_back(W(kVNotInit));
		    return w;
	    }());
	const auto large = With32(ok, 0x00, 144);
	Rcs(std::string(off) + "vrtracker Init: 0; again, with a 144-byte param, with null: ALREADY_INITIALIZED x3",
	    {init(ok.data()), init(ok.data()), init(large.data()), init(nullptr)}, {0, W(kVAlready), W(kVAlready), W(kVAlready)});
	Rc(std::string(off) + "vrtracker GpuWaitAndCpuProcess: NOT_EXECUTE_GPU_SUBMIT (no camera, no GPU submission)", gpuwait(),
	   W(kVNoGpuSubmit));
	Rcs(std::string(off) + "vrtracker RegisterDevice(1) 0, again ALREADY_REGISTERED; RegisterDevice2(2) 0; "
	                       "RegisterDeviceInternal(3, option 5) ARGUMENT_INVALID, (3, option 4) 0; type 4, type -1 "
	                       "ARGUMENT_INVALID; RegisterDevice2(3) ALREADY_REGISTERED",
	    {reg(1, 0x100), reg(1, 0x101), reg2(2, 0x30B0100), regi(3, 0x300, 5, 0), regi(3, 0x300, 4, 1), reg(4, 1), reg(-1, 1),
	     reg2(3, 0x301)},
	    {0, W(kVAlreadyReg), 0, W(kVArg), 0, W(kVArg), W(kVArg), W(kVAlreadyReg)});
	const auto rc_small = VrRecal(0x1C, 1);
	const auto rc4      = VrRecal(0x20, 4);
	const auto rc0      = VrRecal(0x20, 0);
	const auto rc2      = VrRecal(0x20, 2);
	const auto rc3      = VrRecal(0x20, 3);
	Rcs(std::string(off) + "vrtracker Recalibrate: null, size 0x1C, type 4: ARGUMENT_INVALID; headset: DEVICE_NOT_REGISTERED; "
	                       "pad, Move, gun (registered): 0",
	    {recal(nullptr), recal(rc_small.data()), recal(rc4.data()), recal(rc0.data()), recal(rc1.data()), recal(rc2.data()),
	     recal(rc3.data())},
	    {W(kVArg), W(kVArg), W(kVArg), W(kVNotReg), 0, 0, 0});
	Rcs(std::string(off) + "vrtracker RegisterDevice(headset) 0; Recalibrate(headset) still DEVICE_NOT_REGISTERED",
	    {reg(0, 0x0F000000), recal(rc0.data())}, {0, W(kVNotReg)});
	Rcs(std::string(off) + "vrtracker UnregisterDevice(pad's handle) 0; Recalibrate(pad) DEVICE_NOT_REGISTERED; again, -1: "
	                       "ARGUMENT_INVALID x2; RegisterDevice(1) 0",
	    {unreg(0x100), recal(rc1.data()), unreg(0x100), unreg(-1), reg(1, 0x102)}, {0, W(kVNotReg), W(kVArg), W(kVArg), 0});
	Rcs(std::string(off) + "vrtracker SetDurationUntilStatusNotTracking: types 0 and 3: 0; 4 and -1: ARGUMENT_INVALID",
	    {setdur(0, 30), setdur(3, 30), setdur(4, 30), setdur(-1, 30)}, {0, 0, W(kVArg), W(kVArg)});
	Rcs(std::string(off) + "vrtracker Term 0; again, RegisterDevice, GpuWaitAndCpuProcess: NOT_INIT x3; QueryMemory 0",
	    {term(), term(), reg(1, 0x103), gpuwait(), query(q0.data(), res)}, {0, W(kVNotInit), W(kVNotInit), W(kVNotInit), 0});
	Rcs(on ? "vrtracker Init with a 144-byte param (held: today's 0, initialized); a 0x80 Init ALREADY_INITIALIZED; "
	         "RegisterDevice(1) ALREADY_REGISTERED (Term kept the handles); GpuWaitAndCpuProcess NOT_EXECUTE_GPU_SUBMIT; Term 0"
	       : "vrtracker off: Init(144 bytes), Init, RegisterDevice, GpuWaitAndCpuProcess, Term: 0",
	    {init(large.data()), init(ok.data()), reg(1, 0x104), gpuwait(), term()},
	    {0, W(kVAlready), W(kVAlreadyReg), W(kVNoGpuSubmit), 0});
}

// =====================================================================================================================
// Move
// =====================================================================================================================
constexpr int kMNotInit  = static_cast<int>(0x80EE0001u);
constexpr int kMAlready  = static_cast<int>(0x80EE0002u);
constexpr int kMArg      = static_cast<int>(0x80EE0003u);
constexpr int kMHandle   = static_cast<int>(0x80EE0004u);
constexpr int kMOpened   = static_cast<int>(0x80EE0007u);
constexpr int kMNone     = 1; // no controller connected
constexpr int kMH1       = 0x30B0100;
constexpr int kMH2       = 0x30B0200;
constexpr int kMBad      = 0x30B0180; // never issued

const std::vector<const char*> kMovePorted = {"j1ITE-EoJmE", "HzC60MfjJxU", "GWXTyxs4QbE", "ttU+JOhShl4",
                                              "f2bcpK6kJfg", "y5h7f8H1Jnk", "IFQwtT2CeY0", "T8KYHPs1JE8",
                                              "zuxWAg3HAac", "XX6wlxpHyeo", "tsZi60H4ypY"};

void CaseMove() {
	g_case          = "move";
	const char* lib = "libSceMove";
	const bool  on  = g_move;
	const char* off = on ? "" : "off: ";
	const auto  W   = [on](int want) { return on ? want : 0; };

	Rc("move registration: the 11 ported NIDs", Registered(kMovePorted, lib), 11);

	const auto init   = Fn<IFn<>>("j1ITE-EoJmE", lib);
	const auto open   = Fn<IFn<int32_t, int32_t, int32_t>>("HzC60MfjJxU", lib);
	const auto info   = Fn<IFn<int32_t, void*>>("GWXTyxs4QbE", lib);
	const auto latest = Fn<IFn<int32_t, void*>>("ttU+JOhShl4", lib);
	const auto recent = Fn<IFn<int32_t, int64_t, void*, int32_t*>>("f2bcpK6kJfg", lib);
	const auto ext    = Fn<IFn<int32_t, void*>>("y5h7f8H1Jnk", lib);
	const auto vib    = Fn<IFn<int32_t, uint8_t>>("IFQwtT2CeY0", lib);
	const auto light  = Fn<IFn<int32_t, uint8_t, uint8_t, uint8_t>>("T8KYHPs1JE8", lib);
	const auto reset  = Fn<IFn<int32_t>>("zuxWAg3HAac", lib);
	const auto close  = Fn<IFn<int32_t>>("XX6wlxpHyeo", lib);
	const auto term   = Fn<IFn<>>("tsZi60H4ypY", lib);

	uint8_t d[256];
	std::memset(d, kS8, sizeof(d));
	auto       count     = static_cast<int32_t>(kS32);
	const auto untouched = [&] { return AllBytes(d, sizeof(d), kS8) && count == static_cast<int32_t>(kS32); };

	// Each case's calls run first (a braced list runs left to right), then its check that nothing was written.
	std::vector<int> got = {term(),          open(1000, 0, 0), close(kMH1),
	                        info(kMH1, d),   ext(kMH1, d),     latest(kMH1, d),
	                        recent(kMH1, 0, d, &count),        vib(kMH1, 1),
	                        light(kMH1, 1, 2, 3),              reset(kMH1),
	                        info(kMH1, nullptr)};
	Rcs(std::string(off) + "move before Init: Term, Open, Close, GetDeviceInfo, GetExtensionPortInfo, ReadStateLatest, "
	                       "ReadStateRecent, SetVibration, SetLightSphere, ResetLightSphere, GetDeviceInfo(null): "
	                       "NOT_INIT x11, nothing written",
	    got, std::vector<int>(11, W(kMNotInit)), untouched());
	got = {init(), init()};
	Rcs(std::string(off) + "move Init 0, again ALREADY_INIT", got, {0, W(kMAlready)});
	got = {open(1000, 0, 0), open(1000, 0, 0), open(1000, 0, 1), open(1000, 1, 0)};
	Rcs(on ? "move Open(1000, 0, 0) 0x30B0100; again ALREADY_OPENED; (1000, 0, 1) 0x30B0200; (1000, 1, 0) 0x30B0300"
	       : "move off: Open x4: 0",
	    got, {W(kMH1), W(kMOpened), W(kMH2), W(0x30B0300)});
	got = {info(kMH1, d), ext(kMH1, d), latest(kMH1, d), recent(kMH1, 0, d, &count), recent(kMH1, 12345, d, &count)};
	Rcs(std::string(off) + "move GetDeviceInfo, GetExtensionPortInfo, ReadStateLatest, ReadStateRecent(time 0), (time "
	                       "12345): 1 (no controller) x5, nothing written",
	    got, std::vector<int>(5, W(kMNone)), untouched());
	got = {info(kMH1, nullptr),         ext(kMH1, nullptr),          latest(kMH1, nullptr),
	       recent(kMH1, -1, d, &count), recent(kMH1, 0, d, nullptr), recent(kMH1, 0, nullptr, &count)};
	Rcs(std::string(off) + "move a null out x3, ReadStateRecent with time -1, a null count, a null out (SDK 0x0A000000: no "
	                       "program loaded): INVALID_ARG x6",
	    got, std::vector<int>(6, W(kMArg)), untouched());
	got = {info(kMBad, nullptr), recent(kMBad, -1, d, &count), info(kMBad, d),
	       ext(kMBad, d),        latest(kMBad, d),             recent(kMBad, 0, d, &count)};
	Rcs(std::string(off) + "move a handle never issued: with bad arguments INVALID_ARG x2 (arguments first), with good ones "
	                       "INVALID_HANDLE x4",
	    got, {W(kMArg), W(kMArg), W(kMHandle), W(kMHandle), W(kMHandle), W(kMHandle)}, untouched());
	got = {vib(kMH1, 255), light(kMH1, 255, 0, 0), reset(kMH1), vib(kMBad, 0), light(kMBad, 0, 0, 0), reset(kMBad)};
	Rcs(std::string(off) + "move SetVibration 1, SetLightSphere 1, ResetLightSphere 0; with a handle never issued: "
	                       "INVALID_HANDLE x3",
	    got, {W(kMNone), W(kMNone), 0, W(kMHandle), W(kMHandle), W(kMHandle)});
	got = {close(kMH2), close(kMH2), info(kMH2, d), open(1000, 0, 1), close(-1)};
	Rcs(std::string(off) + "move Close(0x30B0200) 0; again INVALID_HANDLE; GetDeviceInfo on it INVALID_HANDLE; Open(1000, 0, "
	                       "1) 0x30B0400 (the numbers go on); Close(-1) INVALID_HANDLE",
	    got, {0, W(kMHandle), W(kMHandle), W(0x30B0400), W(kMHandle)}, untouched());
	got = {open(1001, 0, 5), open(1001, 0, 5), info(0, d), open(1000, 0, 5)};
	Rcs(on ? "move Open for user 1001 (held: today's 0, no handle), twice; GetDeviceInfo(0) INVALID_HANDLE; Open(1000, 0, 5) "
	         "0x30B0500 (nothing was opened for 1001)"
	       : "move off: Open(1001) x2, GetDeviceInfo(0), Open(1000, 0, 5): 0",
	    got, {0, 0, W(kMHandle), W(0x30B0500)}, untouched());
	got = {term(), term(), info(kMH1, d), close(kMH1)};
	Rcs(std::string(off) + "move Term 0; again, GetDeviceInfo, Close: NOT_INIT x3", got,
	    {0, W(kMNotInit), W(kMNotInit), W(kMNotInit)}, untouched());
	got = {init(), info(kMH1, d), open(1000, 0, 0), close(0x30B0600), term()};
	Rcs(on ? "move Init 0; GetDeviceInfo(0x30B0100) INVALID_HANDLE (Term closed it); Open(1000, 0, 0) 0x30B0600; Close 0; "
	         "Term 0"
	       : "move off: Init, GetDeviceInfo, Open, Close, Term: 0",
	    got, {0, W(kMHandle), W(0x30B0600), 0, 0}, untouched());
}

// ---- subsystems (as tbn0405.cpp) ------------------------------------------------------------------------------------
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

} // namespace thv0405

int main(int argc, char** argv) {
	using namespace thv0405;
	g_hmd               = SwitchOn("KYTY_BC5_LOAD_HMD");
	g_vr                = SwitchOn("KYTY_BC5_LOAD_VRTRACKER");
	g_move              = SwitchOn("KYTY_BC5_LOAD_MOVE");
	const bool  all_on  = g_hmd && g_vr && g_move;
	const bool  all_off = !g_hmd && !g_vr && !g_move;
	const char* mode    = all_on ? "on" : (all_off ? "off" : "mixed");
	if (argc > 2 || (argc == 2 && std::strcmp(argv[1], mode) != 0)) {
		std::printf("thv0405: the argument says %s but the switches say %s\n", argc == 2 ? argv[1] : "too much", mode);
		return 2;
	}
	std::printf("thv0405: switches hmd %d, vrtracker %d, move %d: %s\n", g_hmd, g_vr, g_move, mode);
	std::fflush(stdout);
	::Log::Bc5SetLogging(false); // the kernel's LOGF lines stay off stdout
	std::thread(Watchdog).detach();

	char  arg0[] = "thv0405";
	char* args[] = {arg0, nullptr};
	Init(1, args);

	g_case = "init: registration"; // each init prints its "[bc5] exp 0405: <table> port on|off" line on stderr
	Libs::LibHmd::InitHmd_1(&g_all);
	Libs::LibVrTracker::InitVrTracker_1(&g_all);
	Libs::LibMove::InitMove_1(&g_all);

	CaseHmd();
	CaseVrTracker();
	CaseMove();

	const int n = g_cases.load();
	const int p = g_passed.load();
	if (p != n) {
		std::printf("thv0405: %s %d of %d passed; FAIL\n", mode, p, n);
		std::fflush(stdout);
		std::_Exit(1);
	}
	std::printf("thv0405: %s %d of %d; end\n", mode, p, n);
	std::fflush(stdout);
	std::_Exit(0); // no static destructors: the Pthread subsystem's helper thread may still run
}
