// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0405 (series e7 of experiment 0401), tag tcm: the CPU test of mktcm0405.py's port in src/libs/libCamera.cpp
// (exp 0405 decision 4, dead-table batch 2, hardware group: the Camera table), behind KYTY_BC5_LOAD_CAMERA. It registers the
// table into its own Loader::SymbolDatabase by calling its LIB_DEFINE (as libs.cpp does when the switch is on; with the
// switch off the init still runs here, to call today's stubs), takes each function by NID and calls it as a title would.
// While the init runs (twice, into two databases), stderr goes to ./tcm0405-stderr.txt: the table must print its one
// "[bc5] exp 0405: camera port on|off" line exactly once.
//   on:  the ported answers of a console with no camera attached (AnyPS5 4f41f4c37 / shadPS4 60c42b9, see
//        tcm0405-notes.md): argument checks, the handle rules (handles from 1, never handed out twice), "not connected",
//        the default settings and configurations; the 22 held NIDs are NOT in the database; the 4 exports that already
//        match answer 0.
//   off: today's answers: all 76 NIDs registered, every one answers 0 and writes nothing.
// The final line says on or off (unset is off); an optional argument "on" or "off" must match. No game, GPU, window, sound
// device, camera, network or USB, and no emulator subsystem is started (PRINT_NAME is off by default).
// Prints one line per case and finally "tcm0405: on|off N of N; end"; exit 0 only then. A watchdog ends a hang after 60 s
// with a FAIL line. Run it in a fresh directory: it writes ./tcm0405-stderr.txt.
// Build: build0401.py ... src/libs/libCamera.cpp=<out>/src/libs/libCamera.cpp --gate tcm0405.cpp <bin> --like src/libs/libCamera.cpp

#include "common/abi.h"
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
#include <fstream>
#include <initializer_list>
#include <iterator>
#include <string>
#include <thread>
#include <vector>

#include <fcntl.h>
#include <unistd.h>

namespace Libs {
namespace LibCamera {
LIB_DEFINE(InitCamera_1);
} // namespace LibCamera
} // namespace Libs

namespace tcm0405 {

template <typename... A>
using IFn = int (KYTY_SYSV_ABI*)(A...);

constexpr int      kWatchdogSeconds = 60;
constexpr char     kStderrFile[]    = "tcm0405-stderr.txt";
constexpr char     kSwitch[]        = "KYTY_BC5_LOAD_CAMERA";
constexpr char     kOnLine[] = "[bc5] exp 0405: camera port on (items: isattached open-close start-stop frame config attributes "
                               "device-queries audio)";
constexpr char     kOffLine[]       = "[bc5] exp 0405: camera port off";
constexpr int      kParam           = static_cast<int>(0x802E0000u);
constexpr int      kNotInit         = static_cast<int>(0x802E0002u);
constexpr int      kNotOpen         = static_cast<int>(0x802E0004u);
constexpr int      kFormatUnknown   = static_cast<int>(0x802E0007u);
constexpr int      kNotConnected    = static_cast<int>(0x802E0010u);
constexpr int      kFatal           = static_cast<int>(0x802E00FFu);
constexpr int32_t  kSystemUser      = 0xFF;
constexpr int32_t  kUnopened        = 0x7FFF0000; // never handed out here
constexpr uint32_t kFill            = 0x5A5A5A5Au;
constexpr uint32_t kNoFrame         = 0xFFFFFFFFu;

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
	std::printf("tcm0405: case %d %s: %s (%s)\n", g_cases.load(), name.c_str(), ok ? "ok" : "FAIL", info.c_str());
	std::fflush(stdout);
}

// A case that compares a return value and, optionally, more conditions.
void Rc(const std::string& name, int got, int want, bool more = true, const std::string& info = "") {
	Report(name, got == want && more,
	       Fmt("0x%08x, want 0x%08x%s%s%s", static_cast<unsigned>(got), static_cast<unsigned>(want), more ? "" : "; outputs wrong",
	           info.empty() ? "" : "; ", info.c_str()));
}

[[noreturn]] void SetupFail(const std::string& what) {
	std::printf("tcm0405: FAIL setup: %s\n", what.c_str());
	std::fflush(stdout);
	std::_Exit(2);
}

void Watchdog() {
	std::this_thread::sleep_for(std::chrono::seconds(kWatchdogSeconds));
	std::printf("tcm0405: FAIL watchdog: case \"%s\" still running after %d s (a hang); %d of %d cases passed before it\n",
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
	const auto* r = g_db->FindByNid(nid, Loader::SymbolType::Func);
	return r != nullptr && r->vaddr != 0;
}

template <typename F>
F Fn(const char* nid) {
	const auto* r = g_db->FindByNid(nid, Loader::SymbolType::Func);
	if (r == nullptr || r->vaddr == 0) {
		SetupFail(Fmt("%s is not registered", nid));
	}
	return reinterpret_cast<F>(r->vaddr);
}

// A guest buffer of 32-bit words filled with 0x5A, to see what a call wrote into it.
template <size_t N>
struct Words {
	alignas(8) uint32_t w[N];
	Words() {
		for (auto& v: w) {
			v = kFill;
		}
	}
	bool operator==(const Words& o) const { return std::memcmp(w, o.w, sizeof(w)) == 0; }
	[[nodiscard]] bool Untouched() const {
		for (uint32_t v: w) {
			if (v != kFill) {
				return false;
			}
		}
		return true;
	}
};
using Attr   = Words<28>;  // 112 bytes: size, channel, window[4], exposure[4], balance[4], gamma[2+4], sat, con, sharp, hue, 4
using Config = Words<26>;  // 104 bytes: size, type, two outputs of 12 words (format[4], res, fps, w, h, unused, pad, extra[2])
using Frame  = Words<146>; // 584 bytes: size at word 0, the two status words at 58 and 59
using Start  = Words<6>;   // 24 bytes: size, format[2], pad, extra[2]
using Box    = Words<64>;  // an opaque output

Attr MakeAttr(uint32_t size, uint32_t channel) {
	Attr a;
	a.w[0] = size;
	a.w[1] = channel;
	return a;
}
Config MakeConfig(uint32_t size) {
	Config c;
	c.w[0] = size;
	return c;
}
Frame MakeFrame(uint32_t size, uint32_t s0 = kFill, uint32_t s1 = kFill) {
	Frame f;
	f.w[0]  = size;
	f.w[58] = s0;
	f.w[59] = s1;
	return f;
}
Start MakeStart(uint32_t size, uint32_t f0, uint32_t f1) {
	Start s;
	s.w[0] = size;
	s.w[1] = f0;
	s.w[2] = f1;
	return s;
}

// ---- the table's NIDs ------------------------------------------------------------------------------------------------
struct Nid {
	const char* nid;
	const char* name;
};
constexpr Nid kHeld[] = {
    {"QhjrPkRPUZQ", "AccGetData"},           {"Y0pCDajzkVQ", "ChangeAppModuleState"},
    {"hHA1frlMxYE", "GetCalibData"},         {"jTJCdyv9GLU", "GetDeviceID"},
    {"-H3UwGQvNZI", "GetDeviceIDWithoutOpen"}, {"olojYZKYiYs", "GetRegister"},
    {"IAz2HgZQWzE", "GetVrCaptureInfo"},     {"0wnf2a60FqI", "InitializeRegistryCalibData"},
    {"wQfd7kfRZvo", "IsConfigChangeDone"},   {"eTywOSWsEiI", "OpenByModuleId"},
    {"py8p6kZcHmA", "RemoveAppModuleFocus"}, {"j5isFVIlZLk", "SetAppModuleFocus"},
    {"LEMk5cTHKEA", "SetCalibData"},         {"vejouEusC7g", "SetDebugStop"},
    {"jeTpU0MqKU0", "SetForceActivate"},     {"lS0tM6n+Q5E", "SetProcessFocus"},
    {"NVITuK83Z7o", "SetProcessFocusByHandle"}, {"8MjO05qk5hA", "SetRegister"},
    {"3VJOpzKoIeM", "SetTrackerMode"},       {"nnR7KAIDPv8", "SetUacModeInternal"},
    {"wpeyFwJ+UEI", "SetVideoSync"},         {"8WtmqmE4edw", "SetVideoSyncInternal"},
};
constexpr Nid kKept[] = { // the 50 ported and the 4 that already match
    {"UFonL7xopFM", "AudioClose"}, {"fkZE7Hup2ro", "AudioGetData"}, {"hftC5A1C8OQ", "AudioGetData2"},
    {"DhqqFiBU+6g", "AudioOpen"}, {"wyU98EXAYxU", "AudioReset"}, {"OMS9LlcrvBo", "Close"},
    {"ztqH5qNTpTk", "CloseByHandle"}, {"nBH6i2s4Glc", "DeviceOpen"}, {"0btIPD5hg5A", "GetAttribute"},
    {"oEi6vM-3E2c", "GetAutoExposureGain"}, {"qTPRMh4eY60", "GetAutoWhiteBalance"},
    {"5Oie5RArfWs", "GetCalibDataFromDevice"}, {"RHYJ7GKOSMg", "GetCalibrationData"}, {"ZaqmGEtYuL0", "GetConfig"},
    {"a5xFueMZIMs", "GetContrast"}, {"tslCukqFE+E", "GetDefectivePixelCancellation"}, {"DSOLCrc3Kh8", "GetDeviceConfig"},
    {"n+rFeP1XXyM", "GetDeviceConfigWithoutHandle"}, {"WZpxnSAM-ds", "GetDeviceInfo"}, {"ObIste7hqdk", "GetExposureGain"},
    {"mxgMmR+1Kr0", "GetFrameData"}, {"WVox2rwGuSc", "GetGamma"}, {"zrIUDKZx0iE", "GetHue"},
    {"XqYRHc4aw3w", "GetLensCorrection"}, {"B260o9pSzM8", "GetMmapConnectedCount"}, {"ULxbwqiYYuU", "GetProductInfo"},
    {"hawKak+Auw4", "GetRegistryInfo"}, {"RTDOsWWqdME", "GetSaturation"}, {"c6Fp9M1EXXc", "GetSharpness"},
    {"HX5524E5tMY", "GetWhiteBalance"}, {"p6n3Npi3YY4", "IsAttached"}, {"U3BVwQl2R5Q", "IsValidFrameData"},
    {"BHn83xrF92E", "Open"}, {"doPlf33ab-U", "SetAttribute"}, {"96F7zp1Xo+k", "SetAttributeInternal"},
    {"yfSdswDaElo", "SetAutoExposureGain"}, {"zIKL4kZleuc", "SetAutoWhiteBalance"}, {"VQ+5kAqsE2Q", "SetConfig"},
    {"9+SNhbctk64", "SetConfigInternal"}, {"3i5MEzrC1pg", "SetContrast"},
    {"jMv40y2A23g", "SetDefectivePixelCancellation"}, {"vER3cIMBHqI", "SetDefectivePixelCancellationInternal"},
    {"wgBMXJJA6K4", "SetExposureGain"}, {"lhEIsHzB8r4", "SetGamma"}, {"QI8GVJUy2ZY", "SetHue"},
    {"K7W7H4ZRwbc", "SetLensCorrection"}, {"eHa3vhGu2rQ", "SetLensCorrectionInternal"}, {"bSKEi2PzzXI", "SetSaturation"},
    {"P-7MVfzvpsM", "SetSharpness"}, {"k3zPIcgFNv0", "SetWhiteBalance"}, {"9EpRYMy7rHU", "Start"},
    {"cLxF1QtHch0", "StartByHandle"}, {"2G2C0nmd++M", "Stop"}, {"+X1Kgnn3bzg", "StopByHandle"},
};
static_assert(std::size(kHeld) == 22 && std::size(kKept) == 54);

// ---- the functions, by NID -------------------------------------------------------------------------------------------
using GetU32 = IFn<int32_t, uint32_t, uint32_t*, void*>;
using SetU32 = IFn<int32_t, uint32_t, uint32_t, const void*>;
using GetObj = IFn<int32_t, uint32_t, void*, void*>;
using SetObj = IFn<int32_t, uint32_t, const void*, const void*>;
struct Camera {
	IFn<int32_t>                          is_attached = Fn<IFn<int32_t>>("p6n3Npi3YY4");
	IFn<int32_t, int32_t, int32_t, void*> open        = Fn<IFn<int32_t, int32_t, int32_t, void*>>("BHn83xrF92E");
	IFn<int32_t>                          close       = Fn<IFn<int32_t>>("OMS9LlcrvBo");
	IFn<int32_t>                          close_h     = Fn<IFn<int32_t>>("ztqH5qNTpTk");
	IFn<int32_t, const void*>             start       = Fn<IFn<int32_t, const void*>>("9EpRYMy7rHU");
	IFn<int32_t, const void*>             start_h     = Fn<IFn<int32_t, const void*>>("cLxF1QtHch0");
	IFn<int32_t>                          stop        = Fn<IFn<int32_t>>("2G2C0nmd++M");
	IFn<int32_t>                          stop_h      = Fn<IFn<int32_t>>("+X1Kgnn3bzg");
	IFn<int32_t, void*>                   get_frame   = Fn<IFn<int32_t, void*>>("mxgMmR+1Kr0");
	IFn<int32_t, const void*>             valid_frame = Fn<IFn<int32_t, const void*>>("U3BVwQl2R5Q");
	IFn<int32_t, void*>                   get_config  = Fn<IFn<int32_t, void*>>("ZaqmGEtYuL0");
	IFn<int32_t, const void*>             set_config  = Fn<IFn<int32_t, const void*>>("VQ+5kAqsE2Q");
	IFn<int32_t, const void*>             set_config_i = Fn<IFn<int32_t, const void*>>("9+SNhbctk64");
	IFn<int32_t, void*>                   get_dev_config    = Fn<IFn<int32_t, void*>>("DSOLCrc3Kh8");
	IFn<void*>                            get_dev_config_nh = Fn<IFn<void*>>("n+rFeP1XXyM");
	IFn<int32_t, const void*>             get_dev_info      = Fn<IFn<int32_t, const void*>>("WZpxnSAM-ds");
	IFn<void*>                            get_product       = Fn<IFn<void*>>("ULxbwqiYYuU");
	IFn<void*>                            get_registry      = Fn<IFn<void*>>("hawKak+Auw4");
	IFn<uint32_t*>                        get_mmap          = Fn<IFn<uint32_t*>>("B260o9pSzM8");
	IFn<>                                   calib_dev         = Fn<IFn<>>("5Oie5RArfWs");
	IFn<const void*, void*>               calib             = Fn<IFn<const void*, void*>>("RHYJ7GKOSMg");
	IFn<>                                   audio_open        = Fn<IFn<>>("DhqqFiBU+6g");
	IFn<void*>                            audio_data        = Fn<IFn<void*>>("fkZE7Hup2ro");
	IFn<void*>                            audio_data2       = Fn<IFn<void*>>("hftC5A1C8OQ");
	IFn<int32_t, void*>                   get_attr          = Fn<IFn<int32_t, void*>>("0btIPD5hg5A");
	IFn<int32_t, const void*>             set_attr          = Fn<IFn<int32_t, const void*>>("doPlf33ab-U");
	GetU32                                     get_ae            = Fn<GetU32>("oEi6vM-3E2c");
	GetU32                                     get_awb           = Fn<GetU32>("qTPRMh4eY60");
	GetU32                                     get_dpc           = Fn<GetU32>("tslCukqFE+E");
	GetU32                                     get_lens          = Fn<GetU32>("XqYRHc4aw3w");
	GetU32                                     get_contrast      = Fn<GetU32>("a5xFueMZIMs");
	GetU32                                     get_saturation    = Fn<GetU32>("RTDOsWWqdME");
	GetU32                                     get_sharpness     = Fn<GetU32>("c6Fp9M1EXXc");
	IFn<int32_t, uint32_t, int32_t*, void*> get_hue = Fn<IFn<int32_t, uint32_t, int32_t*, void*>>("zrIUDKZx0iE");
	GetObj                                     get_exposure      = Fn<GetObj>("ObIste7hqdk");
	GetObj                                     get_wb            = Fn<GetObj>("HX5524E5tMY");
	GetObj                                     get_gamma         = Fn<GetObj>("WVox2rwGuSc");
	SetU32                                     set_ae            = Fn<SetU32>("yfSdswDaElo");
	SetU32                                     set_awb           = Fn<SetU32>("zIKL4kZleuc");
	SetU32                                     set_dpc           = Fn<SetU32>("jMv40y2A23g");
	SetU32                                     set_dpc_i         = Fn<SetU32>("vER3cIMBHqI");
	SetU32                                     set_lens          = Fn<SetU32>("K7W7H4ZRwbc");
	SetU32                                     set_lens_i        = Fn<SetU32>("eHa3vhGu2rQ");
	SetU32                                     set_contrast      = Fn<SetU32>("3i5MEzrC1pg");
	SetU32                                     set_saturation    = Fn<SetU32>("bSKEi2PzzXI");
	SetU32                                     set_sharpness     = Fn<SetU32>("P-7MVfzvpsM");
	IFn<int32_t, uint32_t, int32_t, const void*> set_hue = Fn<IFn<int32_t, uint32_t, int32_t, const void*>>("QI8GVJUy2ZY");
	SetObj                                     set_exposure      = Fn<SetObj>("wgBMXJJA6K4");
	SetObj                                     set_wb            = Fn<SetObj>("k3zPIcgFNv0");
	SetObj                                     set_gamma         = Fn<SetObj>("lhEIsHzB8r4");
	// already today's answer
	IFn<> audio_close = Fn<IFn<>>("UFonL7xopFM");
	IFn<> audio_reset = Fn<IFn<>>("wyU98EXAYxU");
	IFn<> device_open = Fn<IFn<>>("nBH6i2s4Glc");
	IFn<> set_attr_i  = Fn<IFn<>>("96F7zp1Xo+k");
};

// =====================================================================================================================
// registration: on, the 22 held NIDs are absent and the other 54 present; off, all 76 present
// =====================================================================================================================
void CaseRegistration(bool on) {
	g_case        = "registration";
	int         n = 0;
	std::string list;
	for (const auto& h: kHeld) {
		if (Has(h.nid)) {
			n++;
		} else {
			list += Fmt(" %s", h.name);
		}
	}
	if (on) {
		Report("registration: the 22 held NIDs are not registered", n == 0, Fmt("%d of 22 registered", n));
	} else {
		Report("registration: the 22 held NIDs are registered (today's table)", n == 22,
		       Fmt("%d of 22 registered;%s", n, list.empty() ? " none missing" : list.c_str()));
	}
	int         k = 0;
	std::string missing;
	for (const auto& h: kKept) {
		if (Has(h.nid)) {
			k++;
		} else {
			missing += Fmt(" %s", h.name);
		}
	}
	Report("registration: the 50 ported and 4 matching NIDs are registered", k == 54,
	       Fmt("%d of 54;%s", k, missing.empty() ? " none missing" : missing.c_str()));
}

// The four exports that already match: 0 in both modes.
void CaseMatch(const Camera& c) {
	g_case = "match";
	Rc("match: AudioClose", c.audio_close(), 0);
	Rc("match: AudioReset", c.audio_reset(), 0);
	Rc("match: DeviceOpen", c.device_open(), 0);
	Rc("match: SetAttributeInternal", c.set_attr_i(), 0);
}

// =====================================================================================================================
// on
// =====================================================================================================================
void CaseOnNothingOpen(const Camera& c) {
	g_case = "on: nothing open";
	Rc("on: IsAttached(0) = 0, no camera", c.is_attached(0), 0);
	Rc("on: IsAttached(1)", c.is_attached(1), kParam);
	Rc("on: IsAttached(-1)", c.is_attached(-1), kParam);
	Rc("on: AudioOpen", c.audio_open(), kFatal);
	Box box;
	int r = c.audio_data(nullptr);
	Rc("on: AudioGetData(null)", r, kParam);
	r = c.audio_data(box.w);
	Rc("on: AudioGetData(buffer), nothing written", r, 0, box.Untouched());
	r = c.audio_data2(nullptr);
	Rc("on: AudioGetData2(null)", r, kParam);
	r = c.audio_data2(box.w);
	Rc("on: AudioGetData2(buffer), nothing written", r, 0, box.Untouched());
	Rc("on: GetCalibDataFromDevice", c.calib_dev(), kNotConnected);

	uint32_t q[3] = {12, 0, 0};
	r             = c.calib(q, box.w);
	Rc("on: GetCalibrationData(rectification)", r, kNotConnected, box.Untouched());
	q[2] = 1;
	r    = c.calib(q, box.w);
	Rc("on: GetCalibrationData(inverse rectification)", r, kNotConnected, box.Untouched());
	q[2] = 2;
	Rc("on: GetCalibrationData(function 2)", c.calib(q, box.w), kParam);
	q[2] = 0;
	q[1] = 1;
	Rc("on: GetCalibrationData(format 1)", c.calib(q, box.w), kParam);
	q[1] = 0;
	q[0] = 11;
	Rc("on: GetCalibrationData(size 11)", c.calib(q, box.w), kParam);
	q[0] = 12;
	Rc("on: GetCalibrationData(null query)", c.calib(nullptr, box.w), kParam);
	Rc("on: GetCalibrationData(null data)", c.calib(q, nullptr), kParam);

	r = c.get_product(box.w);
	Rc("on: GetProductInfo before any open (not init)", r, kNotInit, box.Untouched());
	r = c.get_registry(box.w);
	Rc("on: GetRegistryInfo before any open (not init)", r, kNotInit, box.Untouched());
	Rc("on: GetProductInfo(null)", c.get_product(nullptr), kParam);
	uint32_t info[4] = {16, 1, kFill, kFill};
	Rc("on: GetDeviceInfo before any open (not init)", c.get_dev_info(0, info), kNotInit);
	Rc("on: GetDeviceInfo(reserved 1)", c.get_dev_info(1, info), kParam);
	info[0] = 15;
	Rc("on: GetDeviceInfo(size 15)", c.get_dev_info(0, info), kParam);
	info[0] = 16;
	info[1] = 2;
	Rc("on: GetDeviceInfo(revision 2)", c.get_dev_info(0, info), kParam);
	Rc("on: GetDeviceInfo(null)", c.get_dev_info(0, nullptr), kParam);

	uint32_t count = kFill;
	r              = c.get_mmap(&count);
	Rc("on: GetMmapConnectedCount before any open", r, kNotOpen, count == kFill);
	Config cfg = MakeConfig(104);
	Config was = cfg;
	r          = c.get_dev_config_nh(cfg.w);
	Rc("on: GetDeviceConfigWithoutHandle before any open", r, kNotOpen, cfg == was);
	Rc("on: Stop(1) before any open", c.stop(1), kNotOpen);
}

void CaseOnOpen(const Camera& c, int32_t* h1, int32_t* h2) {
	g_case = "on: open";
	Rc("on: Open(user 1)", c.open(1, 0, 0, nullptr), kParam);
	Rc("on: Open(type 1)", c.open(kSystemUser, 1, 0, nullptr), kParam);
	Rc("on: Open(index 1)", c.open(kSystemUser, 0, 1, nullptr), kParam);
	Box box;
	*h1 = c.open(kSystemUser, 0, 0, box.w);
	Report("on: Open(system user, 0, 0) hands out a handle, the parameter is not read", *h1 >= 1 && box.Untouched(),
	       Fmt("handle %d", *h1));
	*h2 = c.open(kSystemUser, 0, 0, nullptr);
	Report("on: a second Open hands out the next handle", *h2 == *h1 + 1, Fmt("handle %d after %d", *h2, *h1));
}

void CaseOnDevice(const Camera& c) {
	g_case         = "on: device";
	uint32_t count = kFill;
	int      r     = c.get_mmap(&count);
	Rc("on: GetMmapConnectedCount = 0", r, 0, count == 0);
	Rc("on: GetMmapConnectedCount(null)", c.get_mmap(nullptr), kParam);
	Box box;
	r = c.get_product(box.w);
	Rc("on: GetProductInfo (not connected)", r, kNotConnected, box.Untouched());
	r = c.get_registry(box.w);
	Rc("on: GetRegistryInfo (not connected)", r, kNotConnected, box.Untouched());
	uint32_t info[4] = {16, 1, kFill, kFill};
	r                = c.get_dev_info(0, info);
	Rc("on: GetDeviceInfo (not connected)", r, kNotConnected, info[2] == kFill && info[3] == kFill);
	Config cfg = MakeConfig(104);
	r          = c.get_dev_config_nh(cfg.w);
	bool zero  = true;
	for (uint32_t v: cfg.w) {
		zero = zero && v == 0;
	}
	Rc("on: GetDeviceConfigWithoutHandle clears all 104 bytes, the size too", r, 0, zero);
	cfg        = MakeConfig(100);
	Config was = cfg;
	r          = c.get_dev_config_nh(cfg.w);
	Rc("on: GetDeviceConfigWithoutHandle(size 100)", r, kParam, cfg == was);
	Rc("on: GetDeviceConfigWithoutHandle(null)", c.get_dev_config_nh(nullptr), kParam);
}

void CaseOnStartStop(const Camera& c, int32_t h1) {
	g_case        = "on: start/stop";
	const Start a = MakeStart(24, 1, 0);
	Rc("on: Start(level 1, 0): not connected", c.start(h1, a.w), kNotConnected);
	Start b = MakeStart(24, 0, 0);
	Rc("on: Start(levels 0, 0): format unknown", c.start(h1, b.w), kFormatUnknown);
	b = MakeStart(24, 0x10, 1);
	Rc("on: Start(level 0x10): format unknown", c.start(h1, b.w), kFormatUnknown);
	b = MakeStart(24, 0xF, 0xF);
	Rc("on: Start(levels 0xF, 0xF): not connected", c.start(h1, b.w), kNotConnected);
	b = MakeStart(16, 1, 0);
	Rc("on: Start(size 16)", c.start(h1, b.w), kParam);
	Rc("on: Start(null)", c.start(h1, nullptr), kParam);
	Rc("on: Start(handle 0)", c.start(0, a.w), kParam);
	Rc("on: Start(unopened handle)", c.start(kUnopened, a.w), kNotOpen);
	Rc("on: StartByHandle = 0", c.start_h(h1, a.w), 0);
	b = MakeStart(24, 0, 0);
	Rc("on: StartByHandle(levels 0, 0) = 0, no format check", c.start_h(h1, b.w), 0);
	Rc("on: StartByHandle(unopened handle)", c.start_h(kUnopened, a.w), kNotOpen);
	Rc("on: StartByHandle(null)", c.start_h(h1, nullptr), kParam);
	Rc("on: Stop = 0", c.stop(h1), 0);
	Rc("on: Stop(handle 0)", c.stop(0), kParam);
	Rc("on: Stop(unopened handle)", c.stop(kUnopened), kNotOpen);
	Rc("on: StopByHandle = 0", c.stop_h(h1), 0);
	Rc("on: StopByHandle(handle -3)", c.stop_h(-3), kParam);
}

void CaseOnFrames(const Camera& c, int32_t h1) {
	g_case  = "on: frames";
	Frame f = MakeFrame(584);
	Frame e = MakeFrame(584, kNoFrame, kNoFrame);
	int   r = c.get_frame(h1, f.w);
	Rc("on: GetFrameData: not open, both status words 'no frame', nothing else written", r, kNotOpen, f == e);
	f = MakeFrame(585);
	e = MakeFrame(585, kNoFrame, kNoFrame);
	r = c.get_frame(h1, f.w);
	Rc("on: GetFrameData(size 585): status written, then refused", r, kParam, f == e);
	f = MakeFrame(584);
	e = MakeFrame(584, kNoFrame, kNoFrame);
	r = c.get_frame(0, f.w);
	Rc("on: GetFrameData(handle 0): status written, then refused", r, kParam, f == e);
	Rc("on: GetFrameData(null)", c.get_frame(h1, nullptr), kParam);

	f = MakeFrame(584, 1, 1);
	Rc("on: IsValidFrameData(status 1, 1) = 1", c.valid_frame(h1, f.w), 1);
	f = MakeFrame(584, 1, kNoFrame);
	Rc("on: IsValidFrameData(status 1, no frame) = 0", c.valid_frame(h1, f.w), 0);
	f = MakeFrame(240, 1, 1);
	Rc("on: IsValidFrameData(size 240, status 1, 1) = 1", c.valid_frame(h1, f.w), 1);
	f = MakeFrame(585, 1, 1);
	Rc("on: IsValidFrameData(size 585)", c.valid_frame(h1, f.w), kParam);
	Rc("on: IsValidFrameData(null)", c.valid_frame(h1, nullptr), kParam);
	f = MakeFrame(584, 1, 1);
	Rc("on: IsValidFrameData(unopened handle)", c.valid_frame(kUnopened, f.w), kNotOpen);
	Rc("on: IsValidFrameData(handle 0)", c.valid_frame(0, f.w), kParam);
}

void CaseOnConfig(const Camera& c, int32_t h1) {
	g_case     = "on: config";
	Config cfg = MakeConfig(104);
	int    r   = c.get_config(h1, cfg.w);
	bool   ok  = cfg.w[0] == 104 && cfg.w[1] == 1;
	for (int o = 0; o < 2; o++) { // format 0 (YUV422), 4, 4, 4 (scaled Y8); resolution 0; 60 fps; 0; 0; 0; (pad); null
		const uint32_t* x = cfg.w + 2 + o * 12;
		ok = ok && x[0] == 0 && x[1] == 4 && x[2] == 4 && x[3] == 4 && x[4] == 0 && x[5] == 60 && x[6] == 0 && x[7] == 0 &&
		     x[8] == 0 && x[10] == 0 && x[11] == 0;
	}
	Rc("on: GetConfig: type 1, both outputs YUV422 + 3 x Y8, 1280x800, 60 fps", r, 0, ok,
	   Fmt("type %u, output 0: %u %u %u %u res %u fps %u", cfg.w[1], cfg.w[2], cfg.w[3], cfg.w[4], cfg.w[5], cfg.w[6], cfg.w[7]));
	cfg        = MakeConfig(103);
	Config was = cfg;
	r          = c.get_config(h1, cfg.w);
	Rc("on: GetConfig(size 103)", r, kParam, cfg == was);
	cfg = MakeConfig(104);
	was = cfg;
	r   = c.get_config(kUnopened, cfg.w);
	Rc("on: GetConfig(unopened handle)", r, kNotOpen, cfg == was);
	Rc("on: GetConfig(handle 0)", c.get_config(0, cfg.w), kParam);
	r = c.set_config(h1, cfg.w);
	Rc("on: SetConfig: not connected, nothing written", r, kNotConnected, cfg == was);
	Config bad = MakeConfig(0);
	Rc("on: SetConfig(size 0)", c.set_config(h1, bad.w), kParam);
	Rc("on: SetConfig(unopened handle)", c.set_config(kUnopened, cfg.w), kNotOpen);
	Rc("on: SetConfigInternal: not connected", c.set_config_i(h1, cfg.w), kNotConnected);
	Rc("on: SetConfigInternal(null)", c.set_config_i(h1, nullptr), kParam);
	cfg = MakeConfig(104);
	r   = c.get_dev_config(h1, cfg.w);
	ok  = cfg.w[0] == 104;
	for (int i = 1; i < 26; i++) {
		ok = ok && cfg.w[i] == 0;
	}
	Rc("on: GetDeviceConfig: size 104, the rest cleared", r, 0, ok);
	cfg = MakeConfig(104);
	was = cfg;
	r   = c.get_dev_config(kUnopened, cfg.w);
	Rc("on: GetDeviceConfig(unopened handle)", r, kNotOpen, cfg == was);
	bad = MakeConfig(1);
	Rc("on: GetDeviceConfig(size 1)", c.get_dev_config(h1, bad.w), kParam);
}

// The image settings every getter reports (shadPS4 camera_config.cpp defaults, via AnyPS5).
bool AttrIsDefault(const Attr& a, uint32_t channel) {
	const uint32_t want[28] = {112, channel, 0, 0, 0, 0, 0, 83, 100, 0, 0, 768, 768, 512, 0, 4, 0, 0, 0, 0,
	                           64,  32,      1, 1, 0, 0, 0, 0};
	return std::memcmp(a.w, want, sizeof(want)) == 0;
}

void CaseOnGetters(const Camera& c, int32_t h1) {
	g_case = "on: getters";
	Attr a = MakeAttr(112, 1);
	int  r = c.get_attr(h1, a.w);
	Rc("on: GetAttribute(channel 0): the defaults", r, 0, AttrIsDefault(a, 1),
	   Fmt("exposure %u gain %u balance %u/%u/%u gamma %u sat %u con %u sharp %u hue %u", a.w[7], a.w[8], a.w[11], a.w[12],
	       a.w[13], a.w[15], a.w[20], a.w[21], a.w[22], a.w[23]));
	a = MakeAttr(112, 2);
	r = c.get_attr(h1, a.w);
	Rc("on: GetAttribute(channel 1): the defaults", r, 0, AttrIsDefault(a, 2));
	for (uint32_t ch: {3u, 0u}) {
		a              = MakeAttr(112, ch);
		const Attr was = a;
		r              = c.get_attr(h1, a.w);
		Rc(Fmt("on: GetAttribute(channel value %u)", ch), r, kParam, a == was);
	}
	a = MakeAttr(111, 1);
	Rc("on: GetAttribute(size 111)", c.get_attr(h1, a.w), kParam);
	a              = MakeAttr(112, 1);
	const Attr was = a;
	r              = c.get_attr(kUnopened, a.w);
	Rc("on: GetAttribute(unopened handle)", r, kNotOpen, a == was);
	Rc("on: GetAttribute(null)", c.get_attr(h1, nullptr), kParam);

	uint32_t en = kFill;
	r           = c.get_ae(h1, 1, &en, nullptr);
	Rc("on: GetAutoExposureGain = off", r, 0, en == 0);
	uint32_t t[2] = {8, 0x10};
	en            = kFill;
	r             = c.get_ae(h1, 2, &en, t);
	Rc("on: GetAutoExposureGain(target): off, target cleared (size too)", r, 0, en == 0 && t[0] == 0 && t[1] == 0);
	t[0] = 7;
	t[1] = 0x10;
	en   = kFill;
	r    = c.get_ae(h1, 1, &en, t);
	Rc("on: GetAutoExposureGain(target size 7)", r, kParam, en == kFill && t[0] == 7 && t[1] == 0x10);
	Rc("on: GetAutoExposureGain(both channels)", c.get_ae(h1, 3, &en, nullptr), kParam);
	Rc("on: GetAutoExposureGain(null)", c.get_ae(h1, 1, nullptr, nullptr), kParam);
	en = kFill;
	r  = c.get_ae(kUnopened, 1, &en, nullptr);
	Rc("on: GetAutoExposureGain(unopened handle)", r, kNotOpen, en == kFill);

	struct U32Getter {
		const char* name;
		GetU32      f;
		uint32_t    want;
	};
	const U32Getter getters[] = {
	    {"GetAutoWhiteBalance", c.get_awb, 0},      {"GetDefectivePixelCancellation", c.get_dpc, 0},
	    {"GetLensCorrection", c.get_lens, 0},       {"GetContrast", c.get_contrast, 32},
	    {"GetSaturation", c.get_saturation, 64},    {"GetSharpness", c.get_sharpness, 1},
	};
	for (const auto& g: getters) {
		uint32_t v = kFill;
		r          = g.f(h1, 1, &v, nullptr);
		Rc(Fmt("on: %s = %u", g.name, g.want), r, 0, v == g.want, Fmt("value %u", v));
	}
	int32_t hue = static_cast<int32_t>(kFill);
	r           = c.get_hue(h1, 2, &hue, nullptr);
	Rc("on: GetHue = 1", r, 0, hue == 1);
	Words<4> eg;
	r = c.get_exposure(h1, 1, eg.w, nullptr);
	Rc("on: GetExposureGain = {0, 20, 100, 0}", r, 0, eg.w[0] == 0 && eg.w[1] == 20 && eg.w[2] == 100 && eg.w[3] == 0);
	Words<4> wb;
	r = c.get_wb(h1, 1, wb.w, nullptr);
	Rc("on: GetWhiteBalance = {0, 768, 768, 512}", r, 0, wb.w[0] == 0 && wb.w[1] == 768 && wb.w[2] == 768 && wb.w[3] == 512);
	Words<6> gm;
	r = c.get_gamma(h1, 1, gm.w, nullptr);
	Rc("on: GetGamma = {0, 4, 16 zero bytes}", r, 0,
	   gm.w[0] == 0 && gm.w[1] == 4 && gm.w[2] == 0 && gm.w[3] == 0 && gm.w[4] == 0 && gm.w[5] == 0);

	uint32_t v = kFill;
	Box      opt;
	r = c.get_awb(h1, 1, &v, opt.w);
	Rc("on: GetAutoWhiteBalance(an option)", r, kParam, v == kFill);
	r = c.get_contrast(h1, 3, &v, nullptr);
	Rc("on: GetContrast(both channels)", r, kParam, v == kFill);
	r = c.get_contrast(h1, 0, &v, nullptr);
	Rc("on: GetContrast(channel value 0)", r, kParam, v == kFill);
	r = c.get_saturation(kUnopened, 1, &v, nullptr);
	Rc("on: GetSaturation(unopened handle)", r, kNotOpen, v == kFill);
	Rc("on: GetSharpness(handle 0)", c.get_sharpness(0, 1, &v, nullptr), kParam);
	Rc("on: GetHue(null)", c.get_hue(h1, 1, nullptr, nullptr), kParam);
	Rc("on: GetExposureGain(null)", c.get_exposure(h1, 1, nullptr, nullptr), kParam);
}

void CaseOnSetters(const Camera& c, int32_t h1) {
	g_case = "on: setters";
	Attr a = MakeAttr(112, 3);
	Attr w = a;
	int  r = c.set_attr(h1, a.w);
	Rc("on: SetAttribute(both channels): not connected, nothing written", r, kNotConnected, a == w);
	a = MakeAttr(112, 4);
	Rc("on: SetAttribute(channel value 4)", c.set_attr(h1, a.w), kParam);
	a = MakeAttr(112, 0);
	Rc("on: SetAttribute(channel value 0)", c.set_attr(h1, a.w), kParam);
	a = MakeAttr(100, 1);
	Rc("on: SetAttribute(size 100)", c.set_attr(h1, a.w), kParam);
	Rc("on: SetAttribute(null)", c.set_attr(h1, nullptr), kParam);
	a = MakeAttr(112, 1);
	Rc("on: SetAttribute(unopened handle)", c.set_attr(kUnopened, a.w), kNotOpen);

	uint32_t t[2] = {8, 0x14};
	Rc("on: SetAutoExposureGain(no target): not connected", c.set_ae(h1, 1, 1, nullptr), kNotConnected);
	Rc("on: SetAutoExposureGain(target 0x14, both channels): not connected", c.set_ae(h1, 3, 0, t), kNotConnected);
	t[1] = 0x20;
	Rc("on: SetAutoExposureGain(target 0x20): not connected", c.set_ae(h1, 1, 1, t), kNotConnected);
	t[1] = 0x15;
	Rc("on: SetAutoExposureGain(target 0x15)", c.set_ae(h1, 1, 1, t), kParam);
	t[0] = 9;
	t[1] = 0x10;
	Rc("on: SetAutoExposureGain(target size 9)", c.set_ae(h1, 1, 1, t), kParam);
	Box opt;
	Rc("on: SetAutoWhiteBalance: not connected", c.set_awb(h1, 2, 1, nullptr), kNotConnected);
	Rc("on: SetAutoWhiteBalance(an option)", c.set_awb(h1, 2, 1, opt.w), kParam);
	Rc("on: SetDefectivePixelCancellation(1): not connected", c.set_dpc(h1, 1, 1, nullptr), kNotConnected);
	Rc("on: SetDefectivePixelCancellation(2)", c.set_dpc(h1, 1, 2, nullptr), kParam);
	Rc("on: SetDefectivePixelCancellation(an option)", c.set_dpc(h1, 1, 0, opt.w), kParam);
	Rc("on: SetDefectivePixelCancellationInternal(2): not connected", c.set_dpc_i(h1, 1, 2, nullptr), kNotConnected);
	Rc("on: SetDefectivePixelCancellationInternal(3)", c.set_dpc_i(h1, 1, 3, nullptr), kParam);
	Rc("on: SetLensCorrection(1): not connected", c.set_lens(h1, 1, 1, nullptr), kNotConnected);
	Rc("on: SetLensCorrection(2)", c.set_lens(h1, 1, 2, nullptr), kParam);
	Rc("on: SetLensCorrectionInternal(2): not connected", c.set_lens_i(h1, 1, 2, nullptr), kNotConnected);
	Rc("on: SetLensCorrectionInternal(3)", c.set_lens_i(h1, 1, 3, nullptr), kParam);
	Rc("on: SetContrast: not connected", c.set_contrast(h1, 1, 100, nullptr), kNotConnected);
	Rc("on: SetContrast(an option)", c.set_contrast(h1, 1, 100, opt.w), kParam);
	Rc("on: SetContrast(channel value 0)", c.set_contrast(h1, 0, 1, nullptr), kParam);
	Rc("on: SetContrast(channel value 4)", c.set_contrast(h1, 4, 1, nullptr), kParam);
	Rc("on: SetSaturation(both channels): not connected", c.set_saturation(h1, 3, 0, nullptr), kNotConnected);
	Rc("on: SetSaturation(unopened handle)", c.set_saturation(kUnopened, 1, 0, nullptr), kNotOpen);
	Rc("on: SetSharpness(10): not connected", c.set_sharpness(h1, 1, 10, nullptr), kNotConnected);
	Rc("on: SetSharpness(11)", c.set_sharpness(h1, 1, 11, nullptr), kParam);
	Rc("on: SetHue(-5): not connected", c.set_hue(h1, 1, -5, nullptr), kNotConnected);
	Rc("on: SetHue(handle 0)", c.set_hue(0, 1, 1, nullptr), kParam);
	Words<4> eg;
	const Words<4> eg0 = eg;
	r                  = c.set_exposure(h1, 1, eg.w, nullptr);
	Rc("on: SetExposureGain: not connected, nothing written", r, kNotConnected, eg == eg0);
	Rc("on: SetExposureGain(null)", c.set_exposure(h1, 1, nullptr, nullptr), kParam);
	Words<4> wb;
	Rc("on: SetWhiteBalance: not connected", c.set_wb(h1, 2, wb.w, nullptr), kNotConnected);
	Rc("on: SetWhiteBalance(null)", c.set_wb(h1, 2, nullptr, nullptr), kParam);
	Words<6> gm;
	Rc("on: SetGamma: not connected", c.set_gamma(h1, 1, gm.w, nullptr), kNotConnected);
	Rc("on: SetGamma(an option)", c.set_gamma(h1, 1, gm.w, opt.w), kParam);
}

void CaseOnClose(const Camera& c, int32_t h1, int32_t h2) {
	g_case = "on: close";
	Rc("on: Close(first handle)", c.close(h1), 0);
	Rc("on: Close(first handle) again", c.close(h1), kNotOpen);
	Rc("on: Stop(closed handle)", c.stop(h1), kNotOpen);
	uint32_t count = kFill;
	int      r     = c.get_mmap(&count);
	Rc("on: GetMmapConnectedCount with the second handle still open", r, 0, count == 0);
	Rc("on: Close(handle 0)", c.close(0), kParam);
	Rc("on: Close(handle -1)", c.close(-1), kParam);
	Rc("on: CloseByHandle(second handle)", c.close_h(h2), 0);
	Rc("on: CloseByHandle(second handle) again", c.close_h(h2), kNotOpen);
	Rc("on: CloseByHandle(handle 0)", c.close_h(0), kParam);
	count = kFill;
	r     = c.get_mmap(&count);
	Rc("on: GetMmapConnectedCount after all closed", r, kNotOpen, count == kFill);
	Config cfg = MakeConfig(104);
	Config was = cfg;
	r          = c.get_dev_config_nh(cfg.w);
	Rc("on: GetDeviceConfigWithoutHandle after all closed", r, kNotOpen, cfg == was);
	Box box;
	Rc("on: GetProductInfo after all closed (not init)", c.get_product(box.w), kNotInit);
	const int h3 = c.open(kSystemUser, 0, 0, nullptr);
	Report("on: Open after all closed: a new handle, none reused", h3 == h2 + 1, Fmt("handle %d after %d", h3, h2));
	Rc("on: Close(the new handle)", c.close(h3), 0);
}

void CaseOn(const Camera& c) {
	CaseOnNothingOpen(c);
	int32_t h1 = 0;
	int32_t h2 = 0;
	CaseOnOpen(c, &h1, &h2);
	if (h1 < 1 || h2 < 1) {
		SetupFail("Open did not hand out handles; the cases that need them cannot run");
	}
	CaseOnDevice(c);
	CaseOnStartStop(c, h1);
	CaseOnFrames(c, h1);
	CaseOnConfig(c, h1);
	CaseOnGetters(c, h1);
	CaseOnSetters(c, h1);
	CaseOnClose(c, h1, h2);
}

// =====================================================================================================================
// off: today's stubs: every export answers 0 (OK) and writes nothing, whatever it is given
// =====================================================================================================================
void CaseOff(const Camera& c) {
	g_case = "off";
	Box      box;
	Attr     a   = MakeAttr(112, 1);
	Config   cfg = MakeConfig(104);
	Frame    f   = MakeFrame(584, 1, 1);
	Start    s   = MakeStart(24, 1, 0);
	uint32_t q[3]    = {12, 0, 0};
	uint32_t info[4] = {16, 1, kFill, kFill};
	uint32_t t[2]    = {8, 0x10};
	uint32_t v       = kFill;
	int32_t  hue     = static_cast<int32_t>(kFill);
	Words<4> eg;
	Words<6> gm;
	const Box    box0 = box;
	const Attr   a0   = a;
	const Config cfg0 = cfg;
	const Frame  f0   = f;
	int          r    = 0;
	auto         same = [&] {
        return box == box0 && a == a0 && cfg == cfg0 && f == f0 && v == kFill && hue == static_cast<int32_t>(kFill) &&
               eg.Untouched() && gm.Untouched() && t[0] == 8 && t[1] == 0x10 && info[2] == kFill;
	};
	r = c.is_attached(1);
	Rc("off: IsAttached(1) = today's 0", r, 0);
	r = c.open(kSystemUser, 0, 0, box.w);
	Rc("off: Open = today's 0, no handle", r, 0, same());
	r = c.close(1);
	Rc("off: Close = 0", r, 0);
	r = c.close_h(1);
	Rc("off: CloseByHandle = 0", r, 0);
	r = c.start(1, s.w);
	Rc("off: Start = 0", r, 0);
	r = c.start_h(1, s.w);
	Rc("off: StartByHandle = 0", r, 0);
	r = c.stop(1);
	Rc("off: Stop = 0", r, 0);
	r = c.stop_h(1);
	Rc("off: StopByHandle = 0", r, 0);
	r = c.get_frame(1, f.w);
	Rc("off: GetFrameData = 0, nothing written", r, 0, same());
	r = c.valid_frame(1, f.w);
	Rc("off: IsValidFrameData = 0", r, 0);
	r = c.get_config(1, cfg.w);
	Rc("off: GetConfig = 0, nothing written", r, 0, same());
	r = c.set_config(1, cfg.w);
	Rc("off: SetConfig = 0", r, 0);
	r = c.set_config_i(1, cfg.w);
	Rc("off: SetConfigInternal = 0", r, 0);
	r = c.get_dev_config(1, cfg.w);
	Rc("off: GetDeviceConfig = 0, nothing written", r, 0, same());
	r = c.get_dev_config_nh(cfg.w);
	Rc("off: GetDeviceConfigWithoutHandle = 0, nothing written", r, 0, same());
	r = c.get_dev_info(0, info);
	Rc("off: GetDeviceInfo = 0", r, 0, same());
	r = c.get_product(box.w);
	Rc("off: GetProductInfo = 0, nothing written", r, 0, same());
	r = c.get_registry(box.w);
	Rc("off: GetRegistryInfo = 0, nothing written", r, 0, same());
	r = c.get_mmap(&v);
	Rc("off: GetMmapConnectedCount = 0, nothing written", r, 0, same());
	r = c.calib_dev();
	Rc("off: GetCalibDataFromDevice = 0", r, 0);
	r = c.calib(q, box.w);
	Rc("off: GetCalibrationData = 0, nothing written", r, 0, same());
	r = c.audio_open();
	Rc("off: AudioOpen = 0", r, 0);
	r = c.audio_data(box.w);
	Rc("off: AudioGetData = 0", r, 0, same());
	r = c.audio_data2(box.w);
	Rc("off: AudioGetData2 = 0", r, 0, same());
	r = c.get_attr(1, a.w);
	Rc("off: GetAttribute = 0, nothing written", r, 0, same());
	r = c.set_attr(1, a.w);
	Rc("off: SetAttribute = 0", r, 0);
	r = c.get_ae(1, 1, &v, t);
	Rc("off: GetAutoExposureGain = 0, nothing written", r, 0, same());
	struct U32Getter {
		const char* name;
		GetU32      f;
	};
	const U32Getter getters[] = {{"GetAutoWhiteBalance", c.get_awb}, {"GetDefectivePixelCancellation", c.get_dpc},
	                             {"GetLensCorrection", c.get_lens},  {"GetContrast", c.get_contrast},
	                             {"GetSaturation", c.get_saturation}, {"GetSharpness", c.get_sharpness}};
	for (const auto& g: getters) {
		r = g.f(1, 1, &v, nullptr);
		Rc(Fmt("off: %s = 0, nothing written", g.name), r, 0, same());
	}
	r = c.get_hue(1, 1, &hue, nullptr);
	Rc("off: GetHue = 0, nothing written", r, 0, same());
	r = c.get_exposure(1, 1, eg.w, nullptr);
	Rc("off: GetExposureGain = 0, nothing written", r, 0, same());
	r = c.get_wb(1, 1, eg.w, nullptr);
	Rc("off: GetWhiteBalance = 0, nothing written", r, 0, same());
	r = c.get_gamma(1, 1, gm.w, nullptr);
	Rc("off: GetGamma = 0, nothing written", r, 0, same());
	struct U32Setter {
		const char* name;
		SetU32      f;
	};
	const U32Setter setters[] = {
	    {"SetAutoExposureGain", c.set_ae},   {"SetAutoWhiteBalance", c.set_awb},
	    {"SetDefectivePixelCancellation", c.set_dpc}, {"SetDefectivePixelCancellationInternal", c.set_dpc_i},
	    {"SetLensCorrection", c.set_lens},   {"SetLensCorrectionInternal", c.set_lens_i},
	    {"SetContrast", c.set_contrast},     {"SetSaturation", c.set_saturation},
	    {"SetSharpness", c.set_sharpness},
	};
	for (const auto& g: setters) {
		r = g.f(1, 7, 99, box.w); // values the port refuses
		Rc(Fmt("off: %s = 0", g.name), r, 0, same());
	}
	r = c.set_hue(1, 7, 1, box.w);
	Rc("off: SetHue = 0", r, 0, same());
	r = c.set_exposure(1, 1, nullptr, nullptr);
	Rc("off: SetExposureGain = 0", r, 0);
	r = c.set_wb(1, 1, nullptr, nullptr);
	Rc("off: SetWhiteBalance = 0", r, 0);
	r = c.set_gamma(1, 1, nullptr, nullptr);
	Rc("off: SetGamma = 0", r, 0);
	// The 22 held exports: today's stubs, registered.
	for (const auto& h: kHeld) {
		r = Fn<IFn<>>(h.nid)();
		Rc(Fmt("off: held %s = 0 (today's stub)", h.name), r, 0);
	}
}

// ---- the journal line ------------------------------------------------------------------------------------------------
// Registers the table into db and again into db2 with stderr in ./tcm0405-stderr.txt, then checks the line.
void RegisterAndCheckLine(Loader::SymbolDatabase* db, Loader::SymbolDatabase* db2, bool on) {
	g_case = "init: registration";
	std::fflush(stderr);
	const int saved_err = dup(2);
	const int fd        = open(kStderrFile, O_WRONLY | O_CREAT | O_TRUNC, 0644);
	if (saved_err < 0 || fd < 0 || dup2(fd, 2) < 0) {
		SetupFail(Fmt("cannot send stderr to ./%s", kStderrFile));
	}
	close(fd);
	Libs::LibCamera::InitCamera_1(db);
	Libs::LibCamera::InitCamera_1(db2); // a second registration: the switch is read once, so no second line
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
			std::printf("tcm0405: info stderr: %s\n", line.c_str());
		}
	}
	const std::string want = on ? kOnLine : kOffLine;
	Report("journal: one line, read once", lines.size() == 1 && lines[0] == want,
	       Fmt("%zu lines; want \"%s\"", lines.size(), want.c_str()));
}

} // namespace tcm0405

int main(int argc, char** argv) {
	using namespace tcm0405;
	const bool  on   = SwitchOn(kSwitch);
	const char* mode = on ? "on" : "off";
	if (argc > 2 || (argc == 2 && std::strcmp(argv[1], mode) != 0)) {
		std::printf("tcm0405: the switch (camera %d: %s) does not match the argument %s\n", on, mode,
		            argc == 2 ? argv[1] : "(too many)");
		return 2;
	}
	std::printf("tcm0405: switch camera %d: %s\n", on, mode);
	std::fflush(stdout);
	std::thread(Watchdog).detach();

	static Loader::SymbolDatabase db;
	static Loader::SymbolDatabase db2;
	RegisterAndCheckLine(&db, &db2, on);
	g_db = &db;

	CaseRegistration(on);
	g_case = "lookups";
	const Camera camera {};
	CaseMatch(camera);
	if (on) {
		CaseOn(camera);
	} else {
		CaseOff(camera);
	}

	const int n = g_cases.load();
	const int p = g_passed.load();
	if (p != n) {
		std::printf("tcm0405: %s %d of %d passed; FAIL\n", mode, p, n);
		std::fflush(stdout);
		std::_Exit(1);
	}
	std::printf("tcm0405: %s %d of %d; end\n", mode, p, n);
	std::fflush(stdout);
	std::_Exit(0);
}
