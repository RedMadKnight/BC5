// SPDX-License-Identifier: GPL-2.0-only
// BC5 PORT-LIBC: tests of the libc NID registrations on the host's real SymbolDatabase, filled by the real path
// InitAll -> InitLibC_1 -> InitLibcInternal_1 (src/emulator.cpp calls Libs::InitAll on the runtime linker's database).
// Each function is reached the way the linker reaches it, by Find with the import's library and module or by FindByNid,
// and called through a SysV function pointer of its real type. The expected NIDs are the public algorithm's
// (check_nids.py recomputes them); the commit they come from is KytyPS5 8c01d8e (GPL-2.0-only).
//
// BC5_LAPTOP_SLICE: the laptop has no fmt or Linux host link, so run_libc_laptop.py compiles the InitLibcInternal_1 block
// of the real libC.cpp and starts from there. The box plan in README.md builds without the macro.
#include "common/abi.h"
#include "libs/libs.h"
#include "loader/symbolDatabase.h"

#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>

namespace Libs {
#ifdef BC5_LAPTOP_SLICE
namespace LibcInternal {
void InitLibcInternal_1(Loader::SymbolDatabase* s);
}
#endif
namespace LibcInternal {
int KYTY_SYSV_ABI    strcmp(const char* s1, const char* s2);
int KYTY_SYSV_ABI    strncmp(const char* s1, const char* s2, size_t n);
char* KYTY_SYSV_ABI  strcpy(char* dest, const char* src);
char* KYTY_SYSV_ABI  strncpy(char* dest, const char* src, size_t n);
size_t KYTY_SYSV_ABI strlen(const char* s);
} // namespace LibcInternal
} // namespace Libs

namespace {

constexpr char NID_STRCMP[]   = "Ovb2dSJOAuE";
constexpr char NID_STRNCMP[]  = "aesyjrHVWy4";
constexpr char NID_STRCPY[]   = "kiZSXIWd9vg";
constexpr char NID_STRCPY_S[] = "5Xa2ACNECdo";
constexpr char NID_STRLEN[]   = "j4ViWNHEgww";
constexpr char NID_STRNCPY[]  = "6sJWiWSRuqk";

using StrcmpFunc  = int (KYTY_SYSV_ABI*)(const char*, const char*);
using StrncmpFunc = int (KYTY_SYSV_ABI*)(const char*, const char*, size_t);
using StrcpyFunc  = char* (KYTY_SYSV_ABI*)(char*, const char*);

int g_failed = 0;
void Check(bool v, const char* what) {
	std::fprintf(stderr, "LibcNidTests: %s: %s\n", v ? "ok" : "FAILED", what);
	if (!v) g_failed++;
}

Loader::SymbolResolve Import(const char* nid, const char* library, const char* module) {
	Loader::SymbolResolve sr {};
	sr.name                 = nid;
	sr.library              = library;
	sr.library_version      = 1;
	sr.module               = module;
	sr.module_version_major = 1;
	sr.module_version_minor = 1;
	sr.type                 = Loader::SymbolType::Func;
	return sr;
}

// The one record behind a NID, by both of the linker's lookups, or nullptr if the two disagree or it is absent.
const Loader::SymbolRecord* Resolve(const Loader::SymbolDatabase& db, const char* nid) {
	const auto* by_import = db.Find(Import(nid, "libSceLibcInternal", "libSceLibcInternal"));
	const auto* by_short  = db.Find(Import(nid, "LibcInternal", "LibcInternal"));
	const auto* by_nid    = db.FindByNid(nid, Loader::SymbolType::Func);
	if (by_import == nullptr || by_short != by_import || by_nid != by_import) return nullptr;
	return by_import;
}

void CheckBinding(const Loader::SymbolDatabase& db, const char* nid, uint64_t function, const char* dbg_name) {
	const auto* record = Resolve(db, nid);
	Check(record != nullptr, dbg_name);
	Check(record != nullptr && record->vaddr == function, "the NID binds that wrapper");
	Check(record != nullptr && record->dbg_name == dbg_name, "the record names that wrapper");
}

void TestBindings(const Loader::SymbolDatabase& db) {
	CheckBinding(db, NID_STRCMP, reinterpret_cast<uint64_t>(&Libs::LibcInternal::strcmp), "LibcInternal::strcmp");
	CheckBinding(db, NID_STRNCMP, reinterpret_cast<uint64_t>(&Libs::LibcInternal::strncmp), "LibcInternal::strncmp");
	CheckBinding(db, NID_STRCPY, reinterpret_cast<uint64_t>(&Libs::LibcInternal::strcpy), "LibcInternal::strcpy");
	// neighbours in the same table, untouched
	CheckBinding(db, NID_STRLEN, reinterpret_cast<uint64_t>(&Libs::LibcInternal::strlen), "LibcInternal::strlen");
	CheckBinding(db, NID_STRNCPY, reinterpret_cast<uint64_t>(&Libs::LibcInternal::strncpy), "LibcInternal::strncpy");
}

void TestStrcmp(const Loader::SymbolDatabase& db) {
	const auto* record = Resolve(db, NID_STRCMP);
	Check(record != nullptr, "strcmp resolves");
	if (record == nullptr) return;
	const auto f = reinterpret_cast<StrcmpFunc>(record->vaddr);
	Check(f("abc", "abc") == 0, "strcmp: equal");
	Check(f("abcX", "abcY") < 0, "strcmp: sees past the third byte, below");
	Check(f("abcY", "abcX") > 0, "strcmp: above");
	Check(f("abc", "abcd") < 0, "strcmp: a prefix sorts first");
}

void TestStrncmp(const Loader::SymbolDatabase& db) {
	const auto* record = Resolve(db, NID_STRNCMP);
	Check(record != nullptr, "strncmp resolves");
	if (record == nullptr) return;
	const auto f = reinterpret_cast<StrncmpFunc>(record->vaddr);
	Check(f("abcX", "abcY", 3) == 0, "strncmp: a difference past n does not count");
	Check(f("abcX", "abcY", 4) < 0, "strncmp: a difference at n does");
	Check(f("abcY", "abcX", 4) > 0, "strncmp: above");
	Check(f("abcX", "zzzz", 0) == 0, "strncmp: n = 0");
	Check(f("abc", "abc", 100) == 0, "strncmp: stops at the terminator");
}

void TestStrcpy(const Loader::SymbolDatabase& db) {
	const auto* record = Resolve(db, NID_STRCPY);
	Check(record != nullptr, "strcpy resolves");
	if (record == nullptr) return;
	const auto f = reinterpret_cast<StrcpyFunc>(record->vaddr);

	unsigned char area[32];
	std::memset(area, 0xA5, sizeof(area));
	auto* dest = reinterpret_cast<char*>(area + 8);
	Check(f(dest, "hello, world") == dest, "strcpy returns dest");
	Check(std::strcmp(dest, "hello, world") == 0, "strcpy copies the text and the terminator");
	bool guards = true;
	for (std::size_t i = 0; i < 8; i++) guards = guards && area[i] == 0xA5;
	for (std::size_t i = 8 + 13; i < sizeof(area); i++) guards = guards && area[i] == 0xA5;
	Check(guards, "strcpy leaves the guard bytes");

	Check(f(dest, "") == dest && dest[0] == '\0', "strcpy of an empty string writes the terminator");
	Check(area[8 + 1] == 'e', "and nothing past it");
}

// The console's strcpy_s(dest, size, src) has three arguments. The old table sent its NID to the two-argument strcpy, so
// src landed in the wrapper as the size. It stays unresolved until a real wrapper with the size and error contract
// exists: the linker then stubs and logs the import.
void TestNoStrcpyS(const Loader::SymbolDatabase& db) {
	Check(db.Find(Import(NID_STRCPY_S, "libSceLibcInternal", "libSceLibcInternal")) == nullptr, "strcpy_s: no Find");
	Check(db.FindByNid(NID_STRCPY_S, Loader::SymbolType::Func) == nullptr, "strcpy_s: no FindByNid as a function");
	Check(db.FindByNid(NID_STRCPY_S, Loader::SymbolType::Object) == nullptr, "strcpy_s: no FindByNid as an object");
	Check(db.FindByName(NID_STRCPY_S, Loader::SymbolType::Func) == nullptr, "strcpy_s: no FindByName");
}

} // namespace

int main() {
	Loader::SymbolDatabase db;
#ifdef BC5_LAPTOP_SLICE
	Libs::LibcInternal::InitLibcInternal_1(&db);
#else
	Libs::InitAll(&db);
#endif
	TestBindings(db);
	TestStrcmp(db);
	TestStrncmp(db);
	TestStrcpy(db);
	TestNoStrcpyS(db);
	if (g_failed != 0) {
		std::fprintf(stderr, "LibcNidTests: %d check(s) FAILED\n", g_failed);
		return 1;
	}
	std::fprintf(stderr, "LibcNidTests: all checks passed\n");
	return 0;
}
