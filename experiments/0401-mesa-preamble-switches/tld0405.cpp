// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0405 (series e6 of experiment 0401), tag "tld": the CPU test of mktld0405.py's edit of src/libs/libs.cpp
// (notes tld0405-notes.md): six of the tables KytyPlus compiles but Libs::InitAll never loaded, each behind a switch:
//   KYTY_BC5_LOAD_ZLIB (zlib), KYTY_BC5_LOAD_JPEG (jpeg), KYTY_BC5_LOAD_IME (ime), KYTY_BC5_LOAD_NPCOMMON (npcommon),
//   KYTY_BC5_LOAD_NPMANAGER (npmanager), KYTY_BC5_LOAD_NPTROPHY (nptrophy).
// No game, no GPU, no window, no sound device, no network. Like npgate0401.cpp, it runs the host's own registration
// (the real Libs::InitAll) into a Loader::SymbolDatabase and looks NIDs up the way the loader does (Find: a title's import
// by library and module; FindByNid: the loader's NID-only fallback). A database's records are listed with
// SymbolDatabase::DbgDump into ./tld0405-dump/ and read back (the header has no other way to list them); every listed
// name must give itself back through SymbolDatabase::GenerateName. Three more databases are built: each table's own
// registrations (its init function into a fresh database), and today's InitAll (the input libs.cpp's 41 calls, md5
// 309aecf7c85a5b47217060bb87ec6512 lines 93-136, copied below call for call).
// Cases (one line each):
//   1 the switches' line: InitAll's stderr (captured into ./tld0405-stderr.txt) has exactly one
//     "[bc5] exp 0405: tables ..." line, the expected one, over two InitAll calls.
//   2 InitAll's record list: with the switches off it equals today's InitAll's list, record for record (address and
//     name, in order); with switches on it is the switched tables' own lists in load order, then today's list.
//   3 read once: every switch flipped (on -> "0", off -> "1") before a second InitAll: the same record list.
//   4-9 one per table: each of its keys (nid[library_vN][module_vM.m][Type]) and NIDs, looked up in InitAll's database.
//     On: a key today's InitAll also registers resolves to today's (live) function ("kept live"), any other key to the
//     table's own function ("new"); every NID resolves by NID to the first record with that NID in load order, and the
//     line counts the NIDs whose NID-only lookup now reaches the table instead of today's function (risk 1 of the notes:
//     reported, not a failure, as the design loads the switched tables first). Off: a key today's InitAll registers
//     resolves to today's function, any other key and NID resolves to nothing.
// Build (build0401.py, series e6): --gate tld0405.cpp <out> --like src/libs/libs.cpp, with mktld0405.py's private
// src/libs/libs.cpp (and series e6's other private units, tbc's libZlib.cpp/libJpeg.cpp/libIme.cpp and tbn's libNp.cpp
// among them) in place of the shared ones, linked with every emulator object but main.cpp.o.
// usage: run in a fresh directory on the NVMe, with the six switches set alike:
//   all six =1 -> "tld0405 on";  all six =0, or all unset -> "tld0405 off". Other mixes: "tld0405 mixed".
// Prints "tld0405: on|off|mixed N of N; end" and exits 0 only then. A watchdog ends a hang after 120 s with a FAIL line.

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

// The six switched tables (as mktld0405.py declares them in libs.cpp).
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

// Today's InitAll's tables: the input libs.cpp's own declarations (lines 13-91).
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

// Today's InitAll: the input libs.cpp's lines 93-136, call for call.
static void Tld0405TodaysInitAll(Loader::SymbolDatabase* s) {
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

namespace tld0405 {

constexpr int  kWatchdogSeconds = 120;
constexpr char kDumpDir[]       = "tld0405-dump";
constexpr char kStderrFile[]    = "tld0405-stderr.txt";

std::atomic<int>         g_cases {0};
std::atomic<int>         g_passed {0};
std::atomic<const char*> g_case {"start"};

std::string Fmt(const char* format, ...) __attribute__((format(printf, 1, 2)));
std::string Fmt(const char* format, ...) {
	char    buf[2048];
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
	std::printf("tld0405: case %d %s: %s (%s)\n", g_cases.load(), name, ok ? "ok" : "FAIL", info.c_str());
	std::fflush(stdout);
}

void Info(const char* name, const std::string& info) {
	std::printf("tld0405: info %s: %s\n", name, info.c_str());
	std::fflush(stdout);
}

[[noreturn]] void SetupFail(const std::string& what) {
	std::printf("tld0405: FAIL setup: %s\n", what.c_str());
	std::fflush(stdout);
	std::_Exit(2);
}

void Watchdog() {
	std::this_thread::sleep_for(std::chrono::seconds(kWatchdogSeconds));
	std::printf("tld0405: FAIL watchdog: \"%s\" still running after %d s (a hang); %d of %d cases passed before it\n",
	            g_case.load(), kWatchdogSeconds, g_passed.load(), g_cases.load());
	std::fflush(stdout);
	std::_Exit(3);
}

// The switched tables in libs.cpp's load order (mktld0405.py's TABLES).
struct Table {
	const char* env;
	const char* item;
	void (*init)(Loader::SymbolDatabase* s);
};
const Table kTables[] = {
    {"KYTY_BC5_LOAD_ZLIB", "zlib", Libs::LibZlib::InitZlib_1},
    {"KYTY_BC5_LOAD_JPEG", "jpeg", Libs::LibJpeg::InitJpeg_1},
    {"KYTY_BC5_LOAD_IME", "ime", Libs::LibIme::InitIme_1},
    {"KYTY_BC5_LOAD_NPCOMMON", "npcommon", Libs::NpCommon::InitNpCommon_1},
    {"KYTY_BC5_LOAD_NPMANAGER", "npmanager", Libs::NpManager::InitNpManager_1},
    {"KYTY_BC5_LOAD_NPTROPHY", "nptrophy", Libs::NpTrophy::InitNpTrophy_1},
};
constexpr size_t kCount = sizeof(kTables) / sizeof(kTables[0]);
static_assert(kCount == 6);

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

} // namespace tld0405

int main(int argc, char** argv) {
	using namespace tld0405;
	bool        on[kCount] = {};
	size_t      n_on       = 0;
	std::string items;
	std::string saved[kCount];
	bool        was_set[kCount] = {};
	for (size_t i = 0; i < kCount; i++) {
		const char* e = std::getenv(kTables[i].env);
		was_set[i]    = e != nullptr;
		saved[i]      = e != nullptr ? e : "";
		on[i]         = EnvOn(e);
		if (on[i]) {
			n_on++;
			items += items.empty() ? "" : ",";
			items += kTables[i].item;
		}
	}
	const char* mode = n_on == kCount ? "on" : n_on == 0 ? "off" : "mixed";
	if (argc != 2 || std::strcmp(argv[1], mode) != 0) {
		std::printf("usage: tld0405 on|off|mixed, matching the six KYTY_BC5_LOAD_* switches (they say %s; the argument is %s)\n",
		            mode, argc == 2 ? argv[1] : "missing or too many");
		return 2;
	}
	std::printf("tld0405: switches zlib %d, jpeg %d, ime %d, npcommon %d, npmanager %d, nptrophy %d: %s\n", on[0], on[1],
	            on[2], on[3], on[4], on[5], mode);
	std::fflush(stdout);
	std::thread(Watchdog).detach();

	// ---- two InitAll calls with stderr in a file; between them every switch flipped (each is read once) ----
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
	for (size_t i = 0; i < kCount; i++) {
		setenv(kTables[i].env, on[i] ? "0" : "1", 1);
	}
	Loader::SymbolDatabase db_again;
	g_case = "the second InitAll (switches flipped)";
	Libs::InitAll(&db_again);
	for (size_t i = 0; i < kCount; i++) {
		if (was_set[i]) {
			setenv(kTables[i].env, saved[i].c_str(), 1);
		} else {
			unsetenv(kTables[i].env);
		}
	}
	std::fflush(stderr);
	if (dup2(saved_err, 2) < 0) {
		SetupFail("cannot give stderr back");
	}
	close(saved_err);

	g_case = "the databases";
	Loader::SymbolDatabase db_today;
	Libs::Tld0405TodaysInitAll(&db_today);
	std::vector<std::unique_ptr<Loader::SymbolDatabase>> db_table;
	std::vector<std::vector<Rec>>                        table;
	for (size_t i = 0; i < kCount; i++) {
		db_table.push_back(std::make_unique<Loader::SymbolDatabase>());
		kTables[i].init(db_table.back().get());
		table.push_back(List(db_table.back().get(), (std::string(kTables[i].item) + ".txt").c_str()));
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
		       d.empty() ? Fmt("every switch flipped before a second InitAll: the same %zu records", again.size()) : d);
	}

	// FindByNid's answer in InitAll's database, from the expected list: the first record with that NID and type.
	// Find's answer, likewise: the newest record with that key (SymbolDatabase::Add's insert_or_assign).
	std::map<NidKey, size_t>      first_by_nid;
	std::map<std::string, size_t> last_by_key;
	for (size_t k = 0; k < want.size(); k++) {
		first_by_nid.emplace(NidOf(want[k]), k);
		last_by_key[want[k].name] = k;
	}

	// ---- cases 4-9: each table's keys and NIDs in InitAll's database ----
	for (size_t i = 0; i < kCount; i++) {
		g_case            = kTables[i].item;
		int         n_new = 0, n_live = 0, n_absent = 0, n_moved = 0, n_live_nid = 0, bad = 0;
		std::string first_bad;
		auto fail = [&](const std::string& what) {
			if (bad++ == 0) {
				first_bad = what;
			}
		};
		std::set<std::string> keys;
		std::set<NidKey>      nids;
		for (const Rec& r: table[i]) {
			if (keys.insert(r.name).second) {
				const Loader::SymbolRecord* in_all   = db_all.Find(r.sr);
				const Loader::SymbolRecord* in_today = db_today.Find(r.sr);
				const Loader::SymbolRecord* in_table = db_table[i]->Find(r.sr);
				const auto                  last     = last_by_key.find(r.name); // Find's answer: the newest record
				if (in_table == nullptr) {
					fail(Fmt("%s is not found in the table's own database", r.name.c_str()));
				} else if (last == last_by_key.end()) {
					n_absent++; // off, and no other switched table has the key
					if (in_all != nullptr) {
						fail(Fmt("%s is registered with the switch off: %s", r.name.c_str(), in_all->dbg_name.c_str()));
					}
				} else if (in_all == nullptr || in_all->vaddr != want[last->second].vaddr) {
					fail(Fmt("%s: InitAll gives %s, want 0x%016" PRIx64, r.name.c_str(),
					         in_all != nullptr ? in_all->dbg_name.c_str() : "nothing", want[last->second].vaddr));
				} else if (in_today != nullptr) { // today's InitAll registers this key: the live function
					n_live++;
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
					n_absent++; // off, but another switched table registers the same key (a mix)
					Info(kTables[i].item, Fmt("%s comes from another switched table: %s", r.name.c_str(), in_all->dbg_name.c_str()));
				}
			}
			if (nids.insert(NidOf(r)).second) {
				const Loader::SymbolRecord* by_all   = db_all.FindByNid(r.sr.name, r.sr.type);
				const Loader::SymbolRecord* by_today = db_today.FindByNid(r.sr.name, r.sr.type);
				const auto                  it       = first_by_nid.find(NidOf(r));
				if (by_today != nullptr) {
					n_live_nid++;
				}
				if (it == first_by_nid.end()) {
					if (by_all != nullptr) {
						fail(Fmt("NID %s is registered with the switch off: %s", r.sr.name.c_str(), by_all->name.c_str()));
					}
				} else if (by_all == nullptr || by_all->vaddr != want[it->second].vaddr || by_all->name != want[it->second].name) {
					fail(Fmt("NID %s: InitAll's FindByNid gives %s, want %s", r.sr.name.c_str(),
					         by_all != nullptr ? by_all->name.c_str() : "nothing", want[it->second].name.c_str()));
				} else if (by_today != nullptr && (by_all->vaddr != by_today->vaddr || by_all->name != by_today->name)) {
					n_moved++; // the NID-only lookup now reaches a switched table, not today's function (risk 1)
				}
			}
		}
		if (table[i].empty()) {
			fail("the table registers nothing");
		}
		if (!on[i] && n_moved != 0) {
			fail(Fmt("%d NID-only lookups moved with the switch off", n_moved));
		}
		const std::string count = table[i].size() == keys.size() ? Fmt("%zu NIDs", keys.size())
		                                                           : Fmt("%zu NIDs in %zu records", keys.size(), table[i].size());
		std::string info;
		if (on[i]) {
			info = Fmt("%s: %d new (by key: the table's functions); %d kept live by key (today's functions); NID-only lookups: "
			           "%d of the %d NIDs today's InitAll also registers now reach the table (risk 1)",
			           count.c_str(), n_new, n_live, n_moved, n_live_nid);
		} else {
			info = Fmt("%s: %d keys not registered; %d live by key as today; NID-only lookups: %d NIDs today's InitAll also "
			           "registers as today, the other %zu none",
			           count.c_str(), n_absent, n_live, n_live_nid, nids.size() - static_cast<size_t>(n_live_nid));
		}
		if (bad != 0) {
			info += Fmt("; %d wrong, the first: %s", bad, first_bad.c_str());
		}
		const std::string name = Fmt("%s (%s)", kTables[i].item, on[i] ? "on" : "off");
		Report(name.c_str(), bad == 0, info);
	}

	g_case      = "the end";
	const int n = g_cases.load();
	const int p = g_passed.load();
	if (p != n) {
		std::printf("tld0405: %s %d of %d passed; FAIL\n", mode, p, n);
		std::fflush(stdout);
		std::_Exit(1);
	}
	std::printf("tld0405: %s %d of %d; end\n", mode, p, n);
	std::fflush(stdout);
	std::_Exit(0); // no static destructors: the databases and the units' state stay as they are
}
