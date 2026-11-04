// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0405 (series e7 of experiment 0401), tag "tl2": the CPU test of mktl20405.py's edit of src/libs/libs.cpp
// (notes tl20405-notes.md): batch 2's seventeen of the tables KytyPlus compiles but Libs::InitAll never loaded, each behind
// a switch, loaded after batch 1's six (series e6, tag tld, whose test is tld0405.cpp):
//   KYTY_BC5_LOAD_NPTUS (nptus), _NPPARTY (npparty), _NPPARTNER (nppartner), _NPAUTH (npauth), _NPSNSFACEBOOK
//   (npsnsfacebook), _VOICE (voice), _SCREENSHOT (screenshot), _DISCMAP (discmap), _ULOBJMGR (ulobjmgr), _COMPANIONHTTPD
//   (companionhttpd), _COMPANIONUTIL (companionutil), _INVITATIONDIALOG (invitationdialog), _WEBBROWSERDIALOG
//   (webbrowserdialog), _SHAREPLAY (shareplay), _GAMELIVESTREAMING (gamelivestreaming), _REMOTEPLAY (remoteplay),
//   _VIDEORECORDING (videorecording).
// Batch 1's six switches (KYTY_BC5_LOAD_ZLIB, _JPEG, _IME, _NPCOMMON, _NPMANAGER, _NPTROPHY) must be off (unset, empty or
// "0"); the test refuses to run otherwise.
// No game, no GPU, no window, no sound device, no network, no USB. As tld0405.cpp: it runs the host's own registration
// (the real Libs::InitAll) into a Loader::SymbolDatabase and looks keys and NIDs up the way the loader does (Find: a
// title's import by library and module; FindByNid: the loader's NID-only fallback). A database's records are listed with
// SymbolDatabase::DbgDump into ./tl20405-dump/ and read back (the header has no other way to list them); every listed name
// must give itself back through SymbolDatabase::GenerateName. More databases are built: each switched table's own
// registrations (its init function into a fresh database; batch 1's six too, for the guard), and today's InitAll (the
// input libs.cpp's 42 calls, md5 903fa699db7c20b2b3f288ab572bce8d lines 198-239, copied below call for call). Each
// table's records are counted at run time, so the port agents' edits of the tables' units need no change here.
// Cases (one line each):
//   1 the switches' line: InitAll's stderr (captured into ./tl20405-stderr.txt) has exactly one
//     "[bc5] exp 0405: tables ..." line, the expected one, over two InitAll calls.
//   2 InitAll's record list: with the seventeen off it equals today's InitAll's list, record for record (address and
//     name, in order); with switches on it is the switched tables' own lists in load order, then today's list.
//   3 read once: all 23 switches flipped (on -> "0", off -> "1") before a second InitAll: the same record list.
//   4-20 one per table: each of its keys (nid[library_vN][module_vM.m][Type]) and NIDs, looked up in InitAll's database.
//     On: a key resolves to the table's own function ("new"); a key today's InitAll also registers would resolve to
//     today's function ("kept live"); every NID resolves by NID to the first record with that NID in load order, and the
//     line counts the NIDs whose NID-only lookup now reaches the table instead of today's function ("moved").
//     Off: every key and NID resolves to nothing (or, for a shared one, to today's function).
//     Guard (on and off): a key or a NID+type of the table that today's InitAll (any live table) registers, or that
//     another switched table (the other sixteen, batch 1's six) registers, FAILs the case: tld0405-notes.md found none
//     for these seventeen, and series e7's ports must not add one.
// Build (build0401.py, series e7): --gate tl20405.cpp <out> --like src/libs/libs.cpp, with mktl20405.py's private
// src/libs/libs.cpp (and series e7's other private units, the ports of these tables among them) in place of the shared
// ones, linked with every emulator object but main.cpp.o.
// usage: run in a fresh directory on the NVMe, batch 1's six switches unset, the seventeen set alike:
//   all seventeen =1 -> "tl20405 on";  all =0, or all unset -> "tl20405 off". Other mixes: "tl20405 mixed".
// Prints "tl20405: on|off|mixed N of N; end" and exits 0 only then. A watchdog ends a hang after 120 s with a FAIL line.

#include "libs/libs.h"
#include "loader/symbolDatabase.h"

#include <atomic>
#include <chrono>
#include <cinttypes>
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <map>
#include <memory>
#include <set>
#include <string>
#include <thread>
#include <utility>
#include <vector>

#include <fcntl.h>
#include <unistd.h>

namespace Libs {

// Batch 1's six switched tables (as mktld0405.py declares them in libs.cpp).
namespace LibZlib {
LIB_DEFINE(InitZlib_1);
} // namespace LibZlib
namespace LibJpeg {
LIB_DEFINE(InitJpeg_1);
} // namespace LibJpeg
namespace LibIme {
LIB_DEFINE(InitIme_1);
} // namespace LibIme
namespace NpCommon {
LIB_DEFINE(InitNpCommon_1);
} // namespace NpCommon
namespace NpManager {
LIB_DEFINE(InitNpManager_1);
} // namespace NpManager
namespace NpTrophy {
LIB_DEFINE(InitNpTrophy_1);
} // namespace NpTrophy

// Batch 2's seventeen (as mktl20405.py declares them in libs.cpp).
namespace NpTus {
LIB_DEFINE(InitNpTus_1);
} // namespace NpTus
namespace NpParty {
LIB_DEFINE(InitNpParty_1);
} // namespace NpParty
namespace NpPartner {
LIB_DEFINE(InitNpPartner_1);
} // namespace NpPartner
namespace NpAuth {
LIB_DEFINE(InitNpAuth_1);
} // namespace NpAuth
namespace NpSnsFacebookDialog {
LIB_DEFINE(InitNpSnsFacebookDialog_1);
} // namespace NpSnsFacebookDialog
namespace LibVoice {
LIB_DEFINE(InitVoice_1);
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
namespace LibInvitationDialog {
LIB_DEFINE(InitInvitationDialog_1);
} // namespace LibInvitationDialog
namespace LibWebBrowserDialog {
LIB_DEFINE(InitWebBrowserDialog_1);
} // namespace LibWebBrowserDialog
namespace LibSharePlay {
LIB_DEFINE(InitSharePlay_1);
} // namespace LibSharePlay
namespace LibGameLiveStreaming {
LIB_DEFINE(InitGameLiveStreaming_1);
} // namespace LibGameLiveStreaming
namespace LibRemotePlay {
LIB_DEFINE(InitRemotePlay_1);
} // namespace LibRemotePlay
namespace LibVideoRecording {
LIB_DEFINE(InitVideoRecording_1);
} // namespace LibVideoRecording

// Today's InitAll's tables: the input libs.cpp's own declarations (lines 15-97).
namespace LibContentDelete {
LIB_DEFINE(InitContentDelete_1);
} // namespace LibContentDelete
namespace LibContentExport {
LIB_DEFINE(InitContentExport_1);
} // namespace LibContentExport
namespace LibContentSearch {
LIB_DEFINE(InitContentSearch_1);
} // namespace LibContentSearch
namespace VideoDec2 {
LIB_DEFINE(InitVideoDec2_1);
} // namespace VideoDec2
namespace LibMouse {
LIB_DEFINE(InitMouse_1);
} // namespace LibMouse
namespace LibKeyboard {
LIB_DEFINE(InitKeyboard_1);
} // namespace LibKeyboard
namespace Ime {
LIB_DEFINE(InitPlatform_1_Ime);
} // namespace Ime
namespace LibUlt {
LIB_DEFINE(InitUlt_1);
} // namespace LibUlt
namespace LibPsml {
LIB_DEFINE(InitPsml_1);
} // namespace LibPsml
LIB_DEFINE(InitLibC_1);
LIB_DEFINE(InitAppContent_1);
LIB_DEFINE(InitAmpr_1);
LIB_DEFINE(InitAudio_1);
LIB_DEFINE(InitCoredump_1);
LIB_DEFINE(InitDbgAddressSanitizer_1);
LIB_DEFINE(InitDebug_1);
LIB_DEFINE(InitDialog_1);
LIB_DEFINE(InitFiber_1);
LIB_DEFINE(InitFont_1);
LIB_DEFINE(InitFontFt_1);
LIB_DEFINE(InitGraphicsDriver_1);
LIB_DEFINE(InitLibKernel_1);
LIB_DEFINE(InitNet_1);
namespace NpCppWebApi {
LIB_DEFINE(InitNpCppWebApi_1);
} // namespace NpCppWebApi
namespace PngEnc {
LIB_DEFINE(InitPngEnc_1);
} // namespace PngEnc
namespace PlayGoDialog {
LIB_DEFINE(InitPlayGoDialog_1);
} // namespace PlayGoDialog
namespace NpCommerceDialog {
LIB_DEFINE(InitNpCommerceDialog_1);
} // namespace NpCommerceDialog
namespace PlayerInvitationDialog {
LIB_DEFINE(InitPlayerInvitationDialog_1);
} // namespace PlayerInvitationDialog
LIB_DEFINE(InitPad_1);
LIB_DEFINE(InitPlayGo_1);
LIB_DEFINE(InitPngDec_1);
LIB_DEFINE(InitPlatform_1);
LIB_DEFINE(InitRudp_1);
LIB_DEFINE(InitRtc_1);
LIB_DEFINE(InitSaveData_1);
LIB_DEFINE(InitShare_1);
LIB_DEFINE(InitSysmodule_1);
LIB_DEFINE(InitSystemService_1);
LIB_DEFINE(InitTextToSpeech2_1);
LIB_DEFINE(InitUserService_1);
LIB_DEFINE(InitVideoOut_1);
LIB_DEFINE(InitBc5LleAgc_1);

// Today's InitAll: the input libs.cpp's lines 198-239 (the 42 calls after the switched tables), call for call.
static void Tl20405TodaysInitAll(Loader::SymbolDatabase* s) {
	LIB_LOAD(InitAudio_1);
	LIB_LOAD(InitAmpr_1);
	LIB_LOAD(InitAppContent_1);
	LIB_LOAD(InitCoredump_1);
	LIB_LOAD(LibContentDelete::InitContentDelete_1);
	LIB_LOAD(LibContentExport::InitContentExport_1);
	LIB_LOAD(LibContentSearch::InitContentSearch_1);
	LIB_LOAD(InitLibC_1);
	LIB_LOAD(InitDbgAddressSanitizer_1);
	LIB_LOAD(InitDebug_1);
	LIB_LOAD(InitDialog_1);
	LIB_LOAD(InitFiber_1);
	LIB_LOAD(InitFont_1);
	LIB_LOAD(InitFontFt_1);
	LIB_LOAD(InitGraphicsDriver_1);
	LIB_LOAD(InitLibKernel_1);
	LIB_LOAD(LibMouse::InitMouse_1);
	LIB_LOAD(LibKeyboard::InitKeyboard_1);
	LIB_LOAD(Ime::InitPlatform_1_Ime);
	LIB_LOAD(InitNet_1);
	LIB_LOAD(NpCppWebApi::InitNpCppWebApi_1);
	LIB_LOAD(PngEnc::InitPngEnc_1);
	LIB_LOAD(PlayGoDialog::InitPlayGoDialog_1);
	LIB_LOAD(NpCommerceDialog::InitNpCommerceDialog_1);
	LIB_LOAD(PlayerInvitationDialog::InitPlayerInvitationDialog_1);
	LIB_LOAD(InitPad_1);
	LIB_LOAD(InitPlayGo_1);
	LIB_LOAD(LibPsml::InitPsml_1);
	LIB_LOAD(InitPngDec_1);
	LIB_LOAD(InitPlatform_1);
	LIB_LOAD(InitRudp_1);
	LIB_LOAD(InitRtc_1);
	LIB_LOAD(InitSaveData_1);
	LIB_LOAD(InitShare_1);
	LIB_LOAD(InitSysmodule_1);
	LIB_LOAD(InitSystemService_1);
	LIB_LOAD(InitTextToSpeech2_1);
	LIB_LOAD(LibUlt::InitUlt_1);
	LIB_LOAD(InitUserService_1);
	LIB_LOAD(VideoDec2::InitVideoDec2_1);
	LIB_LOAD(InitVideoOut_1);
	LIB_LOAD(InitBc5LleAgc_1);
}

} // namespace Libs

namespace tl20405 {

constexpr int  kWatchdogSeconds = 120;
constexpr char kDumpDir[]       = "tl20405-dump";
constexpr char kStderrFile[]    = "tl20405-stderr.txt";

std::atomic<int>         g_cases {0};
std::atomic<int>         g_passed {0};
std::atomic<const char*> g_case {"start"};

std::string Fmt(const char* format, ...) __attribute__((format(printf, 1, 2)));
std::string Fmt(const char* format, ...) {
	char    buf[4096];
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
	std::printf("tl20405: case %d %s: %s (%s)\n", g_cases.load(), name, ok ? "ok" : "FAIL", info.c_str());
	std::fflush(stdout);
}

void Info(const char* name, const std::string& info) {
	std::printf("tl20405: info %s: %s\n", name, info.c_str());
	std::fflush(stdout);
}

[[noreturn]] void SetupFail(const std::string& what) {
	std::printf("tl20405: FAIL setup: %s\n", what.c_str());
	std::fflush(stdout);
	std::_Exit(2);
}

void Watchdog() {
	std::this_thread::sleep_for(std::chrono::seconds(kWatchdogSeconds));
	std::printf("tl20405: FAIL watchdog: \"%s\" still running after %d s (a hang); %d of %d cases passed before it\n",
	            g_case.load(), kWatchdogSeconds, g_passed.load(), g_cases.load());
	std::fflush(stdout);
	std::_Exit(3);
}

struct Table {
	const char* env;
	const char* item;
	void (*init)(Loader::SymbolDatabase* s);
};

// Batch 2's seventeen in libs.cpp's load order (mktl20405.py's rows of TABLES, after batch 1's).
const Table kTables[] = {
    {"KYTY_BC5_LOAD_NPTUS", "nptus", Libs::NpTus::InitNpTus_1},
    {"KYTY_BC5_LOAD_NPPARTY", "npparty", Libs::NpParty::InitNpParty_1},
    {"KYTY_BC5_LOAD_NPPARTNER", "nppartner", Libs::NpPartner::InitNpPartner_1},
    {"KYTY_BC5_LOAD_NPAUTH", "npauth", Libs::NpAuth::InitNpAuth_1},
    {"KYTY_BC5_LOAD_NPSNSFACEBOOK", "npsnsfacebook", Libs::NpSnsFacebookDialog::InitNpSnsFacebookDialog_1},
    {"KYTY_BC5_LOAD_VOICE", "voice", Libs::LibVoice::InitVoice_1},
    {"KYTY_BC5_LOAD_SCREENSHOT", "screenshot", Libs::LibScreenShot::InitScreenShot_1},
    {"KYTY_BC5_LOAD_DISCMAP", "discmap", Libs::LibDiscMap::InitDiscMap_1},
    {"KYTY_BC5_LOAD_ULOBJMGR", "ulobjmgr", Libs::LibUlobjmgr::InitUlobjmgr_1},
    {"KYTY_BC5_LOAD_COMPANIONHTTPD", "companionhttpd", Libs::CompanionHttpd::InitCompanionHttpd_1},
    {"KYTY_BC5_LOAD_COMPANIONUTIL", "companionutil", Libs::CompanionUtil::InitCompanionUtil_1},
    {"KYTY_BC5_LOAD_INVITATIONDIALOG", "invitationdialog", Libs::LibInvitationDialog::InitInvitationDialog_1},
    {"KYTY_BC5_LOAD_WEBBROWSERDIALOG", "webbrowserdialog", Libs::LibWebBrowserDialog::InitWebBrowserDialog_1},
    {"KYTY_BC5_LOAD_SHAREPLAY", "shareplay", Libs::LibSharePlay::InitSharePlay_1},
    {"KYTY_BC5_LOAD_GAMELIVESTREAMING", "gamelivestreaming", Libs::LibGameLiveStreaming::InitGameLiveStreaming_1},
    {"KYTY_BC5_LOAD_REMOTEPLAY", "remoteplay", Libs::LibRemotePlay::InitRemotePlay_1},
    {"KYTY_BC5_LOAD_VIDEORECORDING", "videorecording", Libs::LibVideoRecording::InitVideoRecording_1},
};
constexpr size_t kCount = sizeof(kTables) / sizeof(kTables[0]);
static_assert(kCount == 17);

// Batch 1's six (mktld0405.py's TABLES): off for this test; flipped for case 3; their own lists for the guard.
const Table kBatch1[] = {
    {"KYTY_BC5_LOAD_ZLIB", "zlib", Libs::LibZlib::InitZlib_1},
    {"KYTY_BC5_LOAD_JPEG", "jpeg", Libs::LibJpeg::InitJpeg_1},
    {"KYTY_BC5_LOAD_IME", "ime", Libs::LibIme::InitIme_1},
    {"KYTY_BC5_LOAD_NPCOMMON", "npcommon", Libs::NpCommon::InitNpCommon_1},
    {"KYTY_BC5_LOAD_NPMANAGER", "npmanager", Libs::NpManager::InitNpManager_1},
    {"KYTY_BC5_LOAD_NPTROPHY", "nptrophy", Libs::NpTrophy::InitNpTrophy_1},
};
constexpr size_t kCount1 = sizeof(kBatch1) / sizeof(kBatch1[0]);
static_assert(kCount1 == 6);

// env_flag.hpp's rule: unset, empty and "0" are off.
bool EnvOn(const char* e) {
	return e != nullptr && e[0] != '\0' && std::strcmp(e, "0") != 0;
}

// One record of a database, as DbgDump lists it, with its key parsed back into the lookup's fields.
struct Rec {
	uint64_t              vaddr = 0;
	std::string           name;
	Loader::SymbolResolve sr {};
};

using NidKey = std::pair<std::string, int>; // NID, SymbolType

NidKey NidOf(const Rec& r) {
	return {r.sr.name, static_cast<int>(r.sr.type)};
}

// nid[library_vN][module_vM.m][Type] -> the SymbolResolve whose GenerateName is that name (false if none).
bool Parse(const std::string& name, Loader::SymbolResolve* sr) {
	const size_t b0 = name.find('[');
	if (b0 == std::string::npos || b0 == 0 || name.size() < b0 + 2 || name.back() != ']') {
		return false;
	}
	const std::string rest = name.substr(b0 + 1, name.size() - b0 - 2); // library_vN][module_vM.m][Type
	const size_t      p1   = rest.find("][");
	const size_t      p2   = p1 == std::string::npos ? std::string::npos : rest.find("][", p1 + 2);
	if (p2 == std::string::npos || rest.find("][", p2 + 2) != std::string::npos) {
		return false;
	}
	const std::string lib  = rest.substr(0, p1);
	const std::string mod  = rest.substr(p1 + 2, p2 - p1 - 2);
	const std::string type = rest.substr(p2 + 2);
	const size_t      lv   = lib.rfind("_v");
	const size_t      mv   = mod.rfind("_v");
	const size_t      dot  = mv == std::string::npos ? std::string::npos : mod.find('.', mv);
	if (lv == std::string::npos || dot == std::string::npos) {
		return false;
	}
	static const std::pair<const char*, Loader::SymbolType> types[] = {
	    {"Unknown", Loader::SymbolType::Unknown}, {"Func", Loader::SymbolType::Func},
	    {"Object", Loader::SymbolType::Object},   {"TlsModule", Loader::SymbolType::TlsModule},
	    {"NoType", Loader::SymbolType::NoType},
	};
	bool known = false;
	for (const auto& t: types) {
		if (type == t.first) {
			sr->type = t.second;
			known    = true;
		}
	}
	if (!known) {
		return false;
	}
	sr->name                 = name.substr(0, b0);
	sr->library              = lib.substr(0, lv);
	sr->library_version      = std::atoi(lib.c_str() + lv + 2);
	sr->module               = mod.substr(0, mv);
	sr->module_version_major = std::atoi(mod.c_str() + mv + 2);
	sr->module_version_minor = std::atoi(mod.c_str() + dot + 1);
	return Loader::SymbolDatabase::GenerateName(*sr) == name;
}

// A database's records in its order: SymbolDatabase::DbgDump ("%PRIx64 %s", CRLF) into kDumpDir, read back.
std::vector<Rec> List(Loader::SymbolDatabase* db, const char* file) {
	db->DbgDump(kDumpDir, file);
	const std::string path = std::string(kDumpDir) + "/" + file;
	std::ifstream     in(path, std::ios::binary);
	if (!in) {
		SetupFail(Fmt("DbgDump wrote no %s", path.c_str()));
	}
	std::vector<Rec> out;
	std::string      line;
	while (std::getline(in, line)) {
		while (!line.empty() && (line.back() == '\r' || line.back() == '\n')) {
			line.pop_back();
		}
		if (line.empty()) {
			continue;
		}
		const size_t sp = line.find(' ');
		if (sp == std::string::npos || sp == 0) {
			SetupFail(Fmt("%s: a line without an address: \"%s\"", path.c_str(), line.c_str()));
		}
		Rec         r;
		char*       end = nullptr;
		std::string hex = line.substr(0, sp);
		r.vaddr         = std::strtoull(hex.c_str(), &end, 16);
		r.name          = line.substr(sp + 1);
		if (end == nullptr || *end != '\0' || !Parse(r.name, &r.sr)) {
			SetupFail(Fmt("%s: a record that does not parse back into its key: \"%s\"", path.c_str(), line.c_str()));
		}
		out.push_back(std::move(r));
	}
	return out;
}

bool Same(const Rec& a, const Rec& b) {
	return a.vaddr == b.vaddr && a.name == b.name;
}

// First difference of two record lists ("" when equal).
std::string Diff(const std::vector<Rec>& got, const std::vector<Rec>& want) {
	const size_t n = got.size() < want.size() ? got.size() : want.size();
	for (size_t i = 0; i < n; i++) {
		if (!Same(got[i], want[i])) {
			return Fmt("record %zu is 0x%016" PRIx64 " %s, want 0x%016" PRIx64 " %s", i, got[i].vaddr, got[i].name.c_str(),
			           want[i].vaddr, want[i].name.c_str());
		}
	}
	if (got.size() != want.size()) {
		return Fmt("%zu records, want %zu", got.size(), want.size());
	}
	return "";
}

// The part of a key after the NID: "[library_vN][module_vM.m][Type]".
std::string KeyShape(const std::string& name) {
	const size_t b0 = name.find('[');
	return b0 == std::string::npos ? name : name.substr(b0);
}

} // namespace tl20405

int main(int argc, char** argv) {
	using namespace tl20405;
	bool        on[kCount] = {};
	size_t      n_on       = 0;
	std::string items;
	std::string switches;
	for (size_t i = 0; i < kCount; i++) {
		on[i] = EnvOn(std::getenv(kTables[i].env));
		if (on[i]) {
			n_on++;
			items += items.empty() ? "" : ",";
			items += kTables[i].item;
		}
		switches += Fmt("%s%s %d", i == 0 ? "" : ", ", kTables[i].item, on[i] ? 1 : 0);
	}
	std::string batch1_on;
	for (size_t i = 0; i < kCount1; i++) {
		if (EnvOn(std::getenv(kBatch1[i].env))) {
			batch1_on += Fmt("%s%s", batch1_on.empty() ? "" : ",", kBatch1[i].env);
		}
	}
	const char* mode = n_on == kCount ? "on" : n_on == 0 ? "off" : "mixed";
	if (argc != 2 || std::strcmp(argv[1], mode) != 0 || !batch1_on.empty()) {
		std::printf("usage: tl20405 on|off|mixed, matching batch 2's seventeen KYTY_BC5_LOAD_* switches (they say %s; the "
		            "argument is %s), with batch 1's six off (on: %s)\n",
		            mode, argc == 2 ? argv[1] : "missing or too many", batch1_on.empty() ? "none" : batch1_on.c_str());
		return 2;
	}
	std::printf("tl20405: switches %s; batch 1's six off: %s\n", switches.c_str(), mode);
	std::fflush(stdout);
	std::thread(Watchdog).detach();

	// The 23 switches' values, to flip and restore around the second InitAll.
	std::vector<const char*> envs;
	for (size_t i = 0; i < kCount1; i++) {
		envs.push_back(kBatch1[i].env);
	}
	for (size_t i = 0; i < kCount; i++) {
		envs.push_back(kTables[i].env);
	}
	std::vector<bool>        was_set;
	std::vector<bool>        was_on;
	std::vector<std::string> saved;
	for (const char* env: envs) {
		const char* e = std::getenv(env);
		was_set.push_back(e != nullptr);
		was_on.push_back(EnvOn(e));
		saved.emplace_back(e != nullptr ? e : "");
	}

	// ---- two InitAll calls with stderr in a file; between them all 23 switches flipped (each is read once) ----
	const std::string want_line =
	    n_on == 0 ? std::string("[bc5] exp 0405: tables off") : "[bc5] exp 0405: tables on (items: " + items + ")";
	Info("stderr", Fmt("the two InitAll calls' stderr goes to ./%s", kStderrFile));
	std::fflush(stderr);
	const int saved_err = dup(2);
	const int fd        = open(kStderrFile, O_WRONLY | O_CREAT | O_TRUNC, 0644);
	if (saved_err < 0 || fd < 0 || dup2(fd, 2) < 0) {
		SetupFail(Fmt("cannot send stderr to ./%s", kStderrFile));
	}
	close(fd);
	Loader::SymbolDatabase db_all;
	g_case = "the first InitAll";
	Libs::InitAll(&db_all);
	for (size_t k = 0; k < envs.size(); k++) {
		setenv(envs[k], was_on[k] ? "0" : "1", 1);
	}
	Loader::SymbolDatabase db_again;
	g_case = "the second InitAll (switches flipped)";
	Libs::InitAll(&db_again);
	for (size_t k = 0; k < envs.size(); k++) {
		if (was_set[k]) {
			setenv(envs[k], saved[k].c_str(), 1);
		} else {
			unsetenv(envs[k]);
		}
	}
	std::fflush(stderr);
	if (dup2(saved_err, 2) < 0) {
		SetupFail("cannot give stderr back");
	}
	close(saved_err);

	g_case = "the databases";
	Loader::SymbolDatabase db_today;
	Libs::Tl20405TodaysInitAll(&db_today);
	std::vector<std::unique_ptr<Loader::SymbolDatabase>> db_table;
	std::vector<std::vector<Rec>>                        table;
	for (size_t i = 0; i < kCount; i++) {
		db_table.push_back(std::make_unique<Loader::SymbolDatabase>());
		kTables[i].init(db_table.back().get());
		table.push_back(List(db_table.back().get(), (std::string(kTables[i].item) + ".txt").c_str()));
	}
	std::vector<std::unique_ptr<Loader::SymbolDatabase>> db_batch1;
	for (size_t i = 0; i < kCount1; i++) {
		db_batch1.push_back(std::make_unique<Loader::SymbolDatabase>());
		kBatch1[i].init(db_batch1.back().get());
	}
	const std::vector<Rec> all   = List(&db_all, "initall.txt");
	const std::vector<Rec> again = List(&db_again, "initall-again.txt");
	const std::vector<Rec> today = List(&db_today, "today.txt");
	Info("today's InitAll", Fmt("%zu records", today.size()));

	// ---- case 1: the switches' line ----
	g_case = "case 1";
	{
		std::ifstream in(kStderrFile, std::ios::binary);
		std::string   line;
		int           tables_lines = 0;
		bool          match        = false;
		while (std::getline(in, line)) {
			while (!line.empty() && (line.back() == '\r' || line.back() == '\n')) {
				line.pop_back();
			}
			if (line.rfind("[bc5]", 0) == 0) {
				Info("InitAll's stderr", line);
			}
			if (line.rfind("[bc5] exp 0405: tables", 0) == 0) {
				tables_lines++;
				match = line == want_line;
			}
		}
		Report("the switches' line", tables_lines == 1 && match,
		       Fmt("%d \"[bc5] exp 0405: tables\" line(s) over two InitAll calls, want one: \"%s\"", tables_lines,
		           want_line.c_str()));
	}

	// ---- case 2: InitAll's record list ----
	g_case = "case 2";
	std::vector<Rec> want;
	std::string      parts;
	for (size_t i = 0; i < kCount; i++) {
		if (on[i]) {
			want.insert(want.end(), table[i].begin(), table[i].end());
			parts += Fmt("%s%s %zu", parts.empty() ? "" : ", ", kTables[i].item, table[i].size());
		}
	}
	const size_t n_switched = want.size();
	want.insert(want.end(), today.begin(), today.end());
	{
		const std::string d = Diff(all, want);
		if (n_on == 0) {
			Report("InitAll's record list", d.empty(),
			       d.empty() ? Fmt("%zu records, equal to today's InitAll's, record for record", all.size()) : d);
		} else {
			Report("InitAll's record list", d.empty(),
			       d.empty() ? Fmt("%zu records: the switched tables' %zu first (%s), then today's InitAll's %zu, in order",
			                       all.size(), n_switched, parts.c_str(), today.size())
			                 : d);
		}
	}

	// ---- case 3: read once ----
	g_case = "case 3";
	{
		const std::string d = Diff(again, all);
		Report("read once", d.empty(),
		       d.empty() ? Fmt("all 23 switches flipped before a second InitAll: the same %zu records", again.size()) : d);
	}

	// FindByNid's answer in InitAll's database, from the expected list: the first record with that NID and type.
	// Find's answer, likewise: the newest record with that key (SymbolDatabase::Add's insert_or_assign).
	std::map<NidKey, size_t>      first_by_nid;
	std::map<std::string, size_t> last_by_key;
	for (size_t k = 0; k < want.size(); k++) {
		first_by_nid.emplace(NidOf(want[k]), k);
		last_by_key[want[k].name] = k;
	}

	// The other switched tables, for the guard: (item, own database).
	std::vector<std::pair<const char*, const Loader::SymbolDatabase*>> switched;
	for (size_t i = 0; i < kCount1; i++) {
		switched.emplace_back(kBatch1[i].item, db_batch1[i].get());
	}
	for (size_t i = 0; i < kCount; i++) {
		switched.emplace_back(kTables[i].item, db_table[i].get());
	}

	// ---- cases 4-20: each table's keys and NIDs in InitAll's database ----
	size_t total = 0;
	for (size_t i = 0; i < kCount; i++) {
		g_case            = kTables[i].item;
		int         n_new = 0, n_live = 0, n_absent = 0, n_moved = 0, n_live_nid = 0, n_shared_sw = 0, bad = 0;
		std::string first_bad;
		auto fail = [&](const std::string& what) {
			if (bad++ == 0) {
				first_bad = what;
			}
		};
		std::set<std::string> keys;
		std::set<NidKey>      nids;
		std::set<std::string> shapes;
		for (const Rec& r: table[i]) {
			shapes.insert(KeyShape(r.name));
			if (keys.insert(r.name).second) {
				const Loader::SymbolRecord* in_all   = db_all.Find(r.sr);
				const Loader::SymbolRecord* in_today = db_today.Find(r.sr);
				const Loader::SymbolRecord* in_table = db_table[i]->Find(r.sr);
				const auto                  last     = last_by_key.find(r.name); // Find's answer: the newest record
				for (const auto& [item, db]: switched) {
					const Loader::SymbolRecord* other = db->Find(r.sr);
					if (db != db_table[i].get() && other != nullptr) {
						n_shared_sw++;
						fail(Fmt("guard: key %s is also registered by switched table %s (%s)", r.name.c_str(), item,
						         other->dbg_name.c_str()));
					}
				}
				if (in_today != nullptr) { // guard: a key a live table registers
					n_live++;
					fail(Fmt("guard: key %s is also registered by a live table (today's %s)", r.name.c_str(),
					         in_today->dbg_name.c_str()));
				}
				if (in_table == nullptr) {
					fail(Fmt("%s is not found in the table's own database", r.name.c_str()));
				} else if (last == last_by_key.end()) {
					n_absent++; // off: not registered
					if (in_all != nullptr) {
						fail(Fmt("%s is registered with the switch off: %s", r.name.c_str(), in_all->dbg_name.c_str()));
					}
				} else if (in_all == nullptr || in_all->vaddr != want[last->second].vaddr) {
					fail(Fmt("%s: InitAll gives %s, want 0x%016" PRIx64, r.name.c_str(),
					         in_all != nullptr ? in_all->dbg_name.c_str() : "nothing", want[last->second].vaddr));
				} else if (in_today != nullptr) {
					if (in_all->vaddr != in_today->vaddr || in_all->dbg_name != in_today->dbg_name) {
						fail(Fmt("%s: InitAll gives %s, want today's %s", r.name.c_str(), in_all->dbg_name.c_str(),
						         in_today->dbg_name.c_str()));
					}
				} else if (on[i]) {
					n_new++;
					if (in_all->vaddr != in_table->vaddr || in_all->dbg_name != in_table->dbg_name) {
						fail(Fmt("%s: InitAll gives %s, want the table's %s", r.name.c_str(), in_all->dbg_name.c_str(),
						         in_table->dbg_name.c_str()));
					}
				} else {
					n_absent++; // off, but another switched table registers the same key (the guard has failed it)
				}
			}
			if (nids.insert(NidOf(r)).second) {
				const Loader::SymbolRecord* by_all   = db_all.FindByNid(r.sr.name, r.sr.type);
				const Loader::SymbolRecord* by_today = db_today.FindByNid(r.sr.name, r.sr.type);
				const auto                  it       = first_by_nid.find(NidOf(r));
				for (const auto& [item, db]: switched) {
					const Loader::SymbolRecord* other = db->FindByNid(r.sr.name, r.sr.type);
					if (db != db_table[i].get() && other != nullptr) {
						n_shared_sw++;
						fail(Fmt("guard: NID %s is also registered by switched table %s (%s)", r.sr.name.c_str(), item,
						         other->name.c_str()));
					}
				}
				if (by_today != nullptr) { // guard: a NID+type a live table registers, under any key
					n_live_nid++;
					fail(Fmt("guard: NID %s is also registered by a live table (today's %s)", r.sr.name.c_str(),
					         by_today->name.c_str()));
				}
				if (it == first_by_nid.end()) {
					if (by_all != nullptr) {
						fail(Fmt("NID %s is registered with the switch off: %s", r.sr.name.c_str(), by_all->name.c_str()));
					}
				} else if (by_all == nullptr || by_all->vaddr != want[it->second].vaddr || by_all->name != want[it->second].name) {
					fail(Fmt("NID %s: InitAll's FindByNid gives %s, want %s", r.sr.name.c_str(),
					         by_all != nullptr ? by_all->name.c_str() : "nothing", want[it->second].name.c_str()));
				} else if (by_today != nullptr && (by_all->vaddr != by_today->vaddr || by_all->name != by_today->name)) {
					n_moved++; // the NID-only lookup now reaches a switched table, not today's function
				}
			}
		}
		if (table[i].empty()) {
			fail("the table registers nothing");
		}
		if (!on[i] && n_moved != 0) {
			fail(Fmt("%d NID-only lookups moved with the switch off", n_moved));
		}
		total += table[i].size();
		std::string shape;
		for (const std::string& k: shapes) {
			shape += (shape.empty() ? "" : " ") + k;
		}
		const std::string count = table[i].size() == keys.size()
		                              ? Fmt("%zu NIDs %s", keys.size(), shape.c_str())
		                              : Fmt("%zu NIDs in %zu records %s", keys.size(), table[i].size(), shape.c_str());
		std::string info;
		if (on[i]) {
			info = Fmt("%s: %d new (by key: the table's functions); %d kept live by key; NID-only lookups: %d moved; guard: %d "
			           "keys and %d NIDs shared with a live table, %d with another switched table",
			           count.c_str(), n_new, n_live, n_moved, n_live, n_live_nid, n_shared_sw);
		} else {
			info = Fmt("%s: %d keys not registered; NID-only lookups: %zu NIDs resolve to nothing; guard: %d keys and %d NIDs "
			           "shared with a live table, %d with another switched table",
			           count.c_str(), n_absent, nids.size() - static_cast<size_t>(n_live_nid), n_live, n_live_nid,
			           n_shared_sw);
		}
		if (bad != 0) {
			info += Fmt("; %d wrong, the first: %s", bad, first_bad.c_str());
		}
		const std::string name = Fmt("%s (%s)", kTables[i].item, on[i] ? "on" : "off");
		Report(name.c_str(), bad == 0, info);
	}
	Info("batch 2", Fmt("%zu records in the seventeen tables' own lists", total));

	g_case      = "the end";
	const int n = g_cases.load();
	const int p = g_passed.load();
	if (p != n) {
		std::printf("tl20405: %s %d of %d passed; FAIL\n", mode, p, n);
		std::fflush(stdout);
		std::_Exit(1);
	}
	std::printf("tl20405: %s %d of %d; end\n", mode, p, n);
	std::fflush(stdout);
	std::_Exit(0); // no static destructors: the databases and the units' state stay as they are
}
