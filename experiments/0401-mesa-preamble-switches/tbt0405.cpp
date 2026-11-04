// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0405 (series e7 of experiment 0401), tag tbt: the CPU test of mktbt0405.py's port in src/libs/libNp.cpp
// (the NpTus table, exp 0405 decision 4), behind KYTY_BC5_LOAD_NPTUS. It registers the table into its own SymbolDatabase by
// calling its LIB_DEFINE (as libs.cpp does when the switch is on; with the switch off the init still runs here, to call
// today's stubs), takes each function by NID with the exact key a title's import of libSceNpTus looks up, and calls it as a
// title would.
//   on:  the ported answers (AnyPS5 4f41f4c37, see tbt0405-notes.md): title contexts (32 at most, TUS and TSS share them),
//        requests (256 at most; poll, wait, abort, delete, a context's delete taking its requests), and for each of the 63
//        *Async/blocking pairs its argument checks in AnyPS5's order: each check on a fresh request (the *Async form
//        answers the check's error and leaves the request unstarted, or 0 and the request finishes SIGNED_OUT; the
//        blocking form answers the error or SIGNED_OUT), on an unknown request (the argument check first, else
//        INVALID_ID), and once on an aborted request (ABORTED); no output is ever written. The 6 held stubs are not
//        registered (neither by the exact key nor by FindByNid).
//        With KYTY_BC5_NPTUS_FRIENDS_RUN also on, the A and cross-save friends calls, sceNpTusGetDataForCrossSaveVUser and
//        sceNpTusDeleteMultiSlotDataVUser answer as the firmware 13.42 run that AnyPS5's debt note reports (the same
//        checks, the run's expectations); every other call as without it.
//   off: today's answer, 0x80550005 from all 142 (all registered), with every output left as it was; the run switch has no
//        effect.
// No game, GPU, window, sound device, network or USB; no subsystem is started (the port needs none). Prints one line per
// case and finally "tbt0405: on|off|mixed N of N; end" (on: both switches on; off: both off or unset; mixed: one of them,
// run with the expectations of that setting); exit 0 only then. A watchdog ends a hang after 60 s with a FAIL line. An
// optional argument "on"/"off"/"mixed" must match the switches. Run it in a fresh directory: it writes ./tbt0405-dump (the
// symbol dump) and removes it.
// Build: build0401.py ... src/libs/libNp.cpp=<out>/src/libs/libNp.cpp --gate tbt0405.cpp <bin> --like src/libs/libNp.cpp

#include "common/abi.h"
#include "libs/libs.h"
#include "loader/symbolDatabase.h"

#include <atomic>
#include <chrono>
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <functional>
#include <string>
#include <thread>
#include <utility>
#include <vector>

namespace Libs {
namespace NpTus {
LIB_DEFINE(InitNpTus_1);
} // namespace NpTus
} // namespace Libs

namespace tbt0405 {

template <typename... A>
using IFn = int (KYTY_SYSV_ABI*)(A...);

constexpr int kWatchdogSeconds = 60;

std::atomic<int>         g_cases {0};
std::atomic<int>         g_passed {0};
std::atomic<const char*> g_case {"start"};
char                     g_case_buf[256];
bool                     g_on  = false; // KYTY_BC5_LOAD_NPTUS
bool                     g_run = false; // KYTY_BC5_NPTUS_FRIENDS_RUN, in effect (only with the port on)

std::string Fmt(const char* format, ...) __attribute__((format(printf, 1, 2)));
std::string Fmt(const char* format, ...) {
	char    buf[4096];
	va_list args;
	va_start(args, format);
	std::vsnprintf(buf, sizeof(buf), format, args);
	va_end(args);
	return buf;
}

void SetCase(const std::string& name) {
	std::snprintf(g_case_buf, sizeof(g_case_buf), "%s", name.c_str());
	g_case = g_case_buf;
}

void Report(const std::string& name, bool ok, const std::string& info) {
	g_cases++;
	if (ok) {
		g_passed++;
	}
	std::printf("tbt0405: case %d %s: %s (%s)\n", g_cases.load(), name.c_str(), ok ? "ok" : "FAIL", info.c_str());
	std::fflush(stdout);
}

[[noreturn]] void SetupFail(const std::string& what) {
	std::printf("tbt0405: FAIL setup: %s\n", what.c_str());
	std::fflush(stdout);
	std::_Exit(2);
}

void Watchdog() {
	std::this_thread::sleep_for(std::chrono::seconds(kWatchdogSeconds));
	std::printf("tbt0405: FAIL watchdog: case \"%s\" still running after %d s (a hang); %d of %d cases passed before it\n",
	            g_case.load(), kWatchdogSeconds, g_passed.load(), g_cases.load());
	std::fflush(stdout);
	std::_Exit(3);
}

bool SwitchOn(const char* name) {
	const char* e = std::getenv(name);
	return e != nullptr && e[0] != '\0' && std::strcmp(e, "0") != 0;
}

std::string Hex(int v) {
	return Fmt("0x%08x", static_cast<unsigned>(v));
}

// ---- the table: every NID InitNpTus_1 registers, with today's symbol name (from the e7 sweep, sweep-nids.tsv) -------------
struct Entry {
	const char* nid;
	const char* name;
};
constexpr Entry kTable[] = {
	{"sRVb2Cf0GHg", "sceNpTssCreateNpTitleCtx"},
	{"cRVmNrJDbG8", "sceNpTusAddAndGetVariable"},
	{"Q2UmHdK04c8", "sceNpTusAddAndGetVariableAsync"},
	{"ukr6FBSrkJw", "sceNpTusAddAndGetVariableVUser"},
	{"lliK9T6ylJg", "sceNpTusAddAndGetVariableVUserAsync"},
	{"BIkMmUfNKWM", "sceNpTusCreateNpTitleCtx"},
	{"0DT5bP6YzBo", "sceNpTusDeleteMultiSlotData"},
	{"OCozl1ZtxRY", "sceNpTusDeleteMultiSlotDataAsync"},
	{"mYhbiRtkE1Y", "sceNpTusDeleteMultiSlotVariable"},
	{"0nDVqcYECoM", "sceNpTusDeleteMultiSlotVariableAsync"},
	{"XOzszO4ONWU", "sceNpTusGetData"},
	{"uHtKS5V1T5k", "sceNpTusGetDataAsync"},
	{"GQHCksS7aLs", "sceNpTusGetDataVUser"},
	{"5R6kI-8f+Hk", "sceNpTusGetDataVUserAsync"},
	{"DXigwIBTjWE", "sceNpTusGetFriendsDataStatus"},
	{"LUwvy0MOSqw", "sceNpTusGetFriendsDataStatusAsync"},
	{"cy+pAALkHp8", "sceNpTusGetFriendsVariable"},
	{"YFYWOwYI6DY", "sceNpTusGetFriendsVariableAsync"},
	{"pgcNwFHoOL4", "sceNpTusGetMultiSlotDataStatus"},
	{"Qyek420uZmM", "sceNpTusGetMultiSlotDataStatusAsync"},
	{"NGCeFUl5ckM", "sceNpTusGetMultiSlotDataStatusVUser"},
	{"bHWFSg6jvXc", "sceNpTusGetMultiSlotDataStatusVUserAsync"},
	{"F+eQlfcka98", "sceNpTusGetMultiSlotVariable"},
	{"bcPB2rnhQqo", "sceNpTusGetMultiSlotVariableAsync"},
	{"uFxVYJEkcmc", "sceNpTusGetMultiSlotVariableVUser"},
	{"qp-rTrq1klk", "sceNpTusGetMultiSlotVariableVUserAsync"},
	{"NvHjFkx2rnU", "sceNpTusGetMultiUserDataStatus"},
	{"0zkr0T+NYvI", "sceNpTusGetMultiUserDataStatusAsync"},
	{"xwJIlK0bHgA", "sceNpTusGetMultiUserDataStatusVUser"},
	{"I5dlIKkHNkQ", "sceNpTusGetMultiUserDataStatusVUserAsync"},
	{"6G9+4eIb+cY", "sceNpTusGetMultiUserVariable"},
	{"YRje5yEXS0U", "sceNpTusGetMultiUserVariableAsync"},
	{"zB0vaHTzA6g", "sceNpTusGetMultiUserVariableVUser"},
	{"xZXQuNSTC6o", "sceNpTusGetMultiUserVariableVUserAsync"},
	{"4NrufkNCkiE", "sceNpTusSetData"},
	{"G68xdfQuiyU", "sceNpTusSetDataAsync"},
	{"+RhzSuuXwxo", "sceNpTusSetDataVUser"},
	{"E4BCVfx-YfM", "sceNpTusSetDataVUserAsync"},
	{"c6aYoa47YgI", "sceNpTusSetMultiSlotVariable"},
	{"5J9GGMludxY", "sceNpTusSetMultiSlotVariableAsync"},
	{"ukC55HsotJ4", "sceNpTusTryAndSetVariable"},
	{"xQfR51i4kck", "sceNpTusTryAndSetVariableAsync"},
	{"ZbitD262GhY", "sceNpTusTryAndSetVariableVUser"},
	{"trZ6QGW6jHs", "sceNpTusTryAndSetVariableVUserAsync"},
	{"lBtrk+7lk14", "sceNpTssCreateNpTitleCtxA"},
	{"-SUR+UoLS6c", "sceNpTssGetData"},
	{"DS2yu3Sjj1o", "sceNpTssGetDataAsync"},
	{"lL+Z3zCKNTs", "sceNpTssGetSmallStorage"},
	{"f2Pe4LGS2II", "sceNpTssGetSmallStorageAsync"},
	{"IVSbAEOxJ6I", "sceNpTssGetStorage"},
	{"k5NZIzggbuk", "sceNpTssGetStorageAsync"},
	{"2eq1bMwgZYo", "sceNpTusAbortRequest"},
	{"wPFah4-5Xec", "sceNpTusAddAndGetVariableA"},
	{"2dB427dT3Iw", "sceNpTusAddAndGetVariableAAsync"},
	{"Nt1runsPVJc", "sceNpTusAddAndGetVariableAVUser"},
	{"GjlEgLCh4DY", "sceNpTusAddAndGetVariableAVUserAsync"},
	{"EPeq43CQKxY", "sceNpTusAddAndGetVariableForCrossSave"},
	{"mXZi1D2xwZE", "sceNpTusAddAndGetVariableForCrossSaveAsync"},
	{"4VLlu7EIjzk", "sceNpTusAddAndGetVariableForCrossSaveVUser"},
	{"6Lu9geO5TiA", "sceNpTusAddAndGetVariableForCrossSaveVUserAsync"},
	{"wjNhItL2wzg", "sceNpTusChangeModeForOtherSaveDataOwners"},
	{"1n-dGukBgnY", "sceNpTusCreateNpTitleCtxA"},
	{"3bh2aBvvmvM", "sceNpTusCreateRequest"},
	{"hhy8+oecGac", "sceNpTusCreateTitleCtx"},
	{"iXzUOM9sXU0", "sceNpTusDeleteMultiSlotDataA"},
	{"6-+Yqc-NppQ", "sceNpTusDeleteMultiSlotDataAAsync"},
	{"xutwCvsydkk", "sceNpTusDeleteMultiSlotDataVUser"},
	{"zDeH4tr+0cQ", "sceNpTusDeleteMultiSlotDataVUserAsync"},
	{"pwnE9Oa1uF8", "sceNpTusDeleteMultiSlotVariableA"},
	{"NQIw7tzo0Ow", "sceNpTusDeleteMultiSlotVariableAAsync"},
	{"o02Mtf8G6V0", "sceNpTusDeleteMultiSlotVariableVUser"},
	{"WCzd3cxhubo", "sceNpTusDeleteMultiSlotVariableVUserAsync"},
	{"H3uq7x0sZOI", "sceNpTusDeleteNpTitleCtx"},
	{"CcIH40dYS88", "sceNpTusDeleteRequest"},
	{"yWEHUFkY1qI", "sceNpTusGetDataA"},
	{"xzG8mG9YlKY", "sceNpTusGetDataAAsync"},
	{"iaH+Sxlw32k", "sceNpTusGetDataAVUser"},
	{"uoFvgzwawAY", "sceNpTusGetDataAVUserAsync"},
	{"1TE3OvH61qo", "sceNpTusGetDataForCrossSave"},
	{"CFPx3eyaT34", "sceNpTusGetDataForCrossSaveAsync"},
	{"-LxFGYCJwww", "sceNpTusGetDataForCrossSaveVUser"},
	{"B7rBR0CoYLI", "sceNpTusGetDataForCrossSaveVUserAsync"},
	{"yixh7HDKWfk", "sceNpTusGetFriendsDataStatusA"},
	{"OheijxY5RYE", "sceNpTusGetFriendsDataStatusAAsync"},
	{"TDoqRD+CE+M", "sceNpTusGetFriendsDataStatusForCrossSave"},
	{"68B6XDgSANk", "sceNpTusGetFriendsDataStatusForCrossSaveAsync"},
	{"C8TY-UnQoXg", "sceNpTusGetFriendsVariableA"},
	{"wrImtTqUSGM", "sceNpTusGetFriendsVariableAAsync"},
	{"mD6s8HtMdpk", "sceNpTusGetFriendsVariableForCrossSave"},
	{"FabW3QpY3gQ", "sceNpTusGetFriendsVariableForCrossSaveAsync"},
	{"833Y2TnyonE", "sceNpTusGetMultiSlotDataStatusA"},
	{"7uLPqiNvNLc", "sceNpTusGetMultiSlotDataStatusAAsync"},
	{"azmjx3jBAZA", "sceNpTusGetMultiSlotDataStatusAVUser"},
	{"668Ij9MYKEU", "sceNpTusGetMultiSlotDataStatusAVUserAsync"},
	{"DgpRToHWN40", "sceNpTusGetMultiSlotDataStatusForCrossSave"},
	{"LQ6CoHcp+ug", "sceNpTusGetMultiSlotDataStatusForCrossSaveAsync"},
	{"KBfBmtxCdmI", "sceNpTusGetMultiSlotDataStatusForCrossSaveVUser"},
	{"4UF2uu2eDCo", "sceNpTusGetMultiSlotDataStatusForCrossSaveVUserAsync"},
	{"GDXlRTxgd+M", "sceNpTusGetMultiSlotVariableA"},
	{"2BnPSY1Oxd8", "sceNpTusGetMultiSlotVariableAAsync"},
	{"AsziNQ9X2uk", "sceNpTusGetMultiSlotVariableAVUser"},
	{"y-DJK+d+leg", "sceNpTusGetMultiSlotVariableAVUserAsync"},
	{"m9XZnxw9AmE", "sceNpTusGetMultiSlotVariableForCrossSave"},
	{"DFlBYT+Lm2I", "sceNpTusGetMultiSlotVariableForCrossSaveAsync"},
	{"wTuuw4-6HI8", "sceNpTusGetMultiSlotVariableForCrossSaveVUser"},
	{"DPcu0qWsd7Q", "sceNpTusGetMultiSlotVariableForCrossSaveVUserAsync"},
	{"lxNDPDnWfMc", "sceNpTusGetMultiUserDataStatusA"},
	{"kt+k6jegYZ8", "sceNpTusGetMultiUserDataStatusAAsync"},
	{"fJU2TZId210", "sceNpTusGetMultiUserDataStatusAVUser"},
	{"WBh3zfrjS38", "sceNpTusGetMultiUserDataStatusAVUserAsync"},
	{"cVeBif6zdZ4", "sceNpTusGetMultiUserDataStatusForCrossSave"},
	{"lq0Anwhj0wY", "sceNpTusGetMultiUserDataStatusForCrossSaveAsync"},
	{"w-c7U0MW2KY", "sceNpTusGetMultiUserDataStatusForCrossSaveVUser"},
	{"H6sQJ99usfE", "sceNpTusGetMultiUserDataStatusForCrossSaveVUserAsync"},
	{"Gjixv5hqRVY", "sceNpTusGetMultiUserVariableA"},
	{"eGunerNP9n0", "sceNpTusGetMultiUserVariableAAsync"},
	{"fVvocpq4mG4", "sceNpTusGetMultiUserVariableAVUser"},
	{"V8ZA3hHrAbw", "sceNpTusGetMultiUserVariableAVUserAsync"},
	{"Q5uQeScvTPE", "sceNpTusGetMultiUserVariableForCrossSave"},
	{"oZ8DMeTU-50", "sceNpTusGetMultiUserVariableForCrossSaveAsync"},
	{"Djuj2+1VNL0", "sceNpTusGetMultiUserVariableForCrossSaveVUser"},
	{"82RP7itI-zI", "sceNpTusGetMultiUserVariableForCrossSaveVUserAsync"},
	{"t7b6dmpQNiI", "sceNpTusPollAsync"},
	{"VzxN3tOouj8", "sceNpTusSetDataA"},
	{"4u58d6g6uwU", "sceNpTusSetDataAAsync"},
	{"kbWqOt3QjKU", "sceNpTusSetDataAVUser"},
	{"Fmx4tapJGzo", "sceNpTusSetDataAVUserAsync"},
	{"cf-WMA0jYCc", "sceNpTusSetMultiSlotVariableA"},
	{"ypMObSwfcns", "sceNpTusSetMultiSlotVariableAAsync"},
	{"1Cz0hTJFyh4", "sceNpTusSetMultiSlotVariableVUser"},
	{"CJAxTxQdwHM", "sceNpTusSetMultiSlotVariableVUserAsync"},
	{"6GKDdRCFx8c", "sceNpTusSetThreadParam"},
	{"KMlHj+tgfdQ", "sceNpTusSetTimeout"},
	{"0up4MP1wNtc", "sceNpTusTryAndSetVariableA"},
	{"bGTjTkHPHTE", "sceNpTusTryAndSetVariableAAsync"},
	{"oGIcxlUabSA", "sceNpTusTryAndSetVariableAVUser"},
	{"uf77muc5Bog", "sceNpTusTryAndSetVariableAVUserAsync"},
	{"MGvSJEHwyL8", "sceNpTusTryAndSetVariableForCrossSave"},
	{"JKGYZ2F1yT8", "sceNpTusTryAndSetVariableForCrossSaveAsync"},
	{"fcCwKpi4CbU", "sceNpTusTryAndSetVariableForCrossSaveVUser"},
	{"CjVIpztpTNc", "sceNpTusTryAndSetVariableForCrossSaveVUserAsync"},
	{"hYPJFWzFPjA", "sceNpTusWaitAsync"},
};
constexpr int kTableSize = static_cast<int>(sizeof(kTable) / sizeof(kTable[0]));
static_assert(kTableSize == 142);

// The 6 stubs AnyPS5 does not implement: held, today's answer on and off.
constexpr const char* kHeld[] = {"sceNpTssGetStorage",     "sceNpTssGetStorageAsync", "sceNpTusChangeModeForOtherSaveDataOwners",
                                 "sceNpTusCreateTitleCtx", "sceNpTusSetThreadParam",  "sceNpTusSetTimeout"};

// ---- lookups: the exact key a title's import of libSceNpTus looks up --------------------------------------------------
Loader::SymbolDatabase g_db;

Loader::SymbolResolve Key(const char* nid) {
	Loader::SymbolResolve r {};
	r.name                 = nid;
	r.library              = "libSceNpTus";
	r.library_version      = 1;
	r.module               = "libSceNpTus";
	r.module_version_major = 1;
	r.module_version_minor = 1;
	r.type                 = Loader::SymbolType::Func;
	return r;
}

const char* NidOf(const std::string& name) {
	for (const auto& e: kTable) {
		if (name == e.name) {
			return e.nid;
		}
	}
	SetupFail("no NID for " + name);
}

template <typename F>
F Fn(const std::string& name) {
	const char* nid = NidOf(name);
	const auto* r   = g_db.Find(Key(nid));
	if (r == nullptr || r->vaddr == 0) {
		SetupFail(Fmt("%s (%s) is not registered", name.c_str(), nid));
	}
	return reinterpret_cast<F>(r->vaddr);
}

// ---- answers ----------------------------------------------------------------------------------------------------------
constexpr int kToday        = static_cast<int>(0x80550005u); // today's stubs: NP_NOT_SIGNED_IN
constexpr int kSignedOut    = static_cast<int>(0x80550006u);
constexpr int kInvArg       = static_cast<int>(0x80550704u);
constexpr int kTooManyObj   = static_cast<int>(0x80550706u);
constexpr int kAborted      = static_cast<int>(0x80550707u);
constexpr int kInsuff       = static_cast<int>(0x8055070Cu);
constexpr int kInvalidId    = static_cast<int>(0x8055070Eu);
constexpr int kInvType      = static_cast<int>(0x80550711u);
constexpr int kInvAlign     = static_cast<int>(0x80550714u);
constexpr int kTooManySlots = static_cast<int>(0x80550718u);
constexpr int kTooManyNpId  = static_cast<int>(0x80550719u);
constexpr int kSentinel     = 0x5A5A5A5A;
constexpr int kUnknownReq   = 0x7FFF0000;

// ---- guest data -------------------------------------------------------------------------------------------------------
struct OnlineId {
	char data[16];
	char term;
	char dummy[3];
};
static_assert(sizeof(OnlineId) == 20);
struct NpId {
	OnlineId handle;
	uint8_t  opt[8];
	uint8_t  reserved[8];
};
static_assert(sizeof(NpId) == 36);
struct FriendsOpt { // the A and cross-save friends calls' option: its size, a start rank, the hits (never written)
	uint64_t  size;
	uint32_t* start_rank;
	uint32_t* hits;
};
static_assert(sizeof(FriendsOpt) == 0x18);
struct TssOpt { // sceNpTssGetData's option: its size, an offset, a last byte, a condition (only the size is read)
	uint64_t  size;
	uint64_t* offset;
	uint64_t* last_byte;
	void*     condition;
};
static_assert(sizeof(TssOpt) == 0x20);

constexpr uint64_t kAccount = 0x0123456789ABCDEFull;
alignas(16) uint8_t g_out[4096]; // every output the calls get; filled with 0x5A, never written by the port
uint8_t             g_opt[64];   // a non-null option the calls refuse unread
OnlineId            g_user {};
OnlineId            g_noname {};
NpId                g_npid {};
OnlineId            g_users[102];
OnlineId            g_users_hole[102]; // the third name empty
uint64_t            g_accounts[102];
NpId                g_npids[102];
int32_t             g_slots[65];
int32_t             g_slots_neg[3]    = {0, -1, 2};
int32_t             g_slots_neg65[65];  // 0..64, the sixth -1
int64_t             g_values[65];
uint8_t             g_data[256];
uint32_t            g_rank1 = 1;
uint32_t            g_rank0 = 0;

void FillOut() {
	std::memset(g_out, 0x5A, sizeof(g_out));
}

bool OutUntouched() {
	for (const uint8_t v: g_out) {
		if (v != 0x5A) {
			return false;
		}
	}
	return true;
}

void InitData() {
	std::snprintf(g_user.data, sizeof(g_user.data), "%s", "vuser01");
	std::snprintf(g_npid.handle.data, sizeof(g_npid.handle.data), "%s", "alpha");
	for (int i = 0; i < 102; i++) {
		std::snprintf(g_users[i].data, sizeof(g_users[i].data), "user%03d", i);
		g_users_hole[i]  = g_users[i];
		g_accounts[i]    = 0x1000u + static_cast<uint64_t>(i);
		g_npids[i]       = g_npid;
	}
	g_users_hole[2] = g_noname;
	for (int i = 0; i < 65; i++) {
		g_slots[i]       = i;
		g_slots_neg65[i] = i;
		g_values[i]      = 100 + i;
	}
	g_slots_neg65[5] = -1;
	FillOut();
}

// ---- the core: contexts and requests ----------------------------------------------------------------------------------
using CtxNpFn  = IFn<uint32_t, const void*>;
using CtxAFn   = IFn<uint32_t, int>;
using IdFn     = IFn<int>;
using ResultFn = IFn<int, int*>;
using SmallFn  = IFn<int, void*, uint64_t, uint64_t*, void*>;

IdFn     g_create_req = nullptr;
IdFn     g_delete_req = nullptr;
IdFn     g_abort_req  = nullptr;
ResultFn g_poll       = nullptr;
ResultFn g_wait       = nullptr;
int      g_ctx        = 1; // the title context of the pair checks

int NewRequest() {
	const int r = g_create_req(g_ctx);
	if (r <= 0) {
		SetupFail(Fmt("sceNpTusCreateRequest(%d) answered %s", g_ctx, Hex(r).c_str()));
	}
	return r;
}

bool IsHeld(const char* name) {
	for (const char* h: kHeld) {
		if (std::strcmp(h, name) == 0) {
			return true;
		}
	}
	return false;
}

void CaseRegistration() {
	SetCase("registration");
	int         found = 0;
	std::string bad;
	for (const auto& e: kTable) {
		if (g_on && IsHeld(e.name)) {
			continue; // CaseHeld
		}
		const auto* r  = g_db.Find(Key(e.nid));
		const auto* rn = g_db.FindByNid(e.nid, Loader::SymbolType::Func);
		if (r != nullptr && r->vaddr != 0 && rn != nullptr && rn->vaddr == r->vaddr) {
			found++;
		} else {
			bad += Fmt(" %s", e.nid);
		}
	}
	const int want = g_on ? 136 : 142;
	// every record of the database: the table registers these 142 and nothing else
	std::error_code ec;
	std::filesystem::remove_all("tbt0405-dump", ec);
	g_db.DbgDump("tbt0405-dump/", "symbols.txt");
	int           lines = 0;
	std::ifstream dump("tbt0405-dump/symbols.txt");
	for (std::string line; std::getline(dump, line);) {
		if (!line.empty() && line != "\r") {
			lines++;
		}
	}
	dump.close();
	std::filesystem::remove_all("tbt0405-dump", ec);
	Report(g_on ? "registration: the 136 ported NIDs by the exact key and by FindByNid, and no other record"
	            : "off: registration: the 142 NIDs by the exact key and by FindByNid, and no other record",
	       found == want && lines == want, Fmt("%d found, %d records, want %d%s", found, lines, want, bad.c_str()));
}

void CaseCore() {
	SetCase("core");
	const auto tss_np   = Fn<CtxNpFn>("sceNpTssCreateNpTitleCtx");
	const auto tus_np   = Fn<CtxNpFn>("sceNpTusCreateNpTitleCtx");
	const auto tss_a    = Fn<CtxAFn>("sceNpTssCreateNpTitleCtxA");
	const auto tus_a    = Fn<CtxAFn>("sceNpTusCreateNpTitleCtxA");
	const auto del_ctx  = Fn<IdFn>("sceNpTusDeleteNpTitleCtx");
	const auto small    = Fn<SmallFn>("sceNpTssGetSmallStorage");
	const auto small_as = Fn<SmallFn>("sceNpTssGetSmallStorageAsync");
	g_create_req        = Fn<IdFn>("sceNpTusCreateRequest");
	g_delete_req        = Fn<IdFn>("sceNpTusDeleteRequest");
	g_abort_req         = Fn<IdFn>("sceNpTusAbortRequest");
	g_poll              = Fn<ResultFn>("sceNpTusPollAsync");
	g_wait              = Fn<ResultFn>("sceNpTusWaitAsync");
	int res             = kSentinel;

	if (!g_on) {
		const auto today = [](const char* name, int got, bool more = true) {
			Report(Fmt("off: %s: today's 0x80550005", name), got == kToday && more, Hex(got));
		};
		today("sceNpTssCreateNpTitleCtx", tss_np(1, &g_npid));
		today("sceNpTusCreateNpTitleCtx", tus_np(1, &g_npid));
		today("sceNpTssCreateNpTitleCtxA", tss_a(1, 1));
		today("sceNpTusCreateNpTitleCtxA", tus_a(1, 1));
		today("sceNpTusCreateRequest", g_create_req(1));
		today("sceNpTusDeleteNpTitleCtx", del_ctx(1));
		today("sceNpTusDeleteRequest", g_delete_req(1));
		today("sceNpTusAbortRequest", g_abort_req(1));
		today("sceNpTusPollAsync, result untouched", g_poll(1, &res), res == kSentinel);
		today("sceNpTusWaitAsync, result untouched", g_wait(1, &res), res == kSentinel);
		g_ctx = 1;
		return;
	}

	// title contexts
	const int e1 = tss_np(1, nullptr);
	const int e2 = tss_np(0xFFFFFFFFu, &g_npid);
	const int e3 = tss_np(0xFFFFFFFFu, nullptr);
	const int c1 = tss_np(1, &g_npid);
	Report("contexts: sceNpTssCreateNpTitleCtx: null NpId INSUFFICIENT, label 0xFFFFFFFF INVALID_ARGUMENT, both INSUFFICIENT, "
	       "else a new id",
	       e1 == kInsuff && e2 == kInvArg && e3 == kInsuff && c1 > 0,
	       Fmt("%s %s %s, id %d", Hex(e1).c_str(), Hex(e2).c_str(), Hex(e3).c_str(), c1));
	const int f1 = tus_np(1, nullptr);
	const int f2 = tus_np(0xFFFFFFFFu, &g_npid);
	const int c2 = tus_np(2, &g_npid);
	Report("contexts: sceNpTusCreateNpTitleCtx: the same checks, the next id", f1 == kInsuff && f2 == kInvArg && c2 == c1 + 1,
	       Fmt("%s %s, id %d", Hex(f1).c_str(), Hex(f2).c_str(), c2));
	const int c3 = tss_a(0xFFFFFFFFu, -1);
	const int c4 = tus_a(7, 0x1234);
	Report("contexts: the user forms (TSS, TUS) check neither label nor user: the next ids", c3 == c2 + 1 && c4 == c3 + 1,
	       Fmt("ids %d %d", c3, c4));

	std::vector<int> extra;
	int              refused = 0;
	for (int i = 0; i < 40 && refused == 0; i++) {
		const int c = tus_a(1, 1);
		if (c > 0) {
			extra.push_back(c);
		} else {
			refused = c;
		}
	}
	const int full_tss = tss_np(1, &g_npid); // the same table
	const int gone     = extra.empty() ? 0 : extra.back();
	const int d1       = del_ctx(gone);
	const int d2       = del_ctx(gone);
	const int again    = tss_np(1, &g_npid);
	if (!extra.empty()) {
		extra.back() = again;
	}
	size_t deleted = 0;
	for (const int c: extra) {
		deleted += del_ctx(c) == 0 ? 1 : 0;
	}
	Report("contexts: 32 at most, TUS and TSS together: the 33rd TOO_MANY_OBJECTS; delete 0, then INVALID_ID; one more made",
	       extra.size() == 28 && refused == kTooManyObj && full_tss == kTooManyObj && d1 == 0 && d2 == kInvalidId && again > 0 &&
	           deleted == extra.size(),
	       Fmt("%zu more made, then %s and %s; delete %s %s; again %d", extra.size(), Hex(refused).c_str(), Hex(full_tss).c_str(),
	           Hex(d1).c_str(), Hex(d2).c_str(), again));

	// requests
	const int u1 = g_create_req(0);
	const int u2 = g_create_req(999999);
	const int u3 = g_create_req(gone);
	Report("requests: on an unknown context (0, 999999, a deleted one): INVALID_ID",
	       u1 == kInvalidId && u2 == kInvalidId && u3 == kInvalidId,
	       Fmt("%s %s %s", Hex(u1).c_str(), Hex(u2).c_str(), Hex(u3).c_str()));

	int r = g_create_req(c2);
	res   = kSentinel;
	int p = g_poll(r, &res);
	int w = g_wait(r, &res);
	int pn = g_poll(r, nullptr);
	int dr = g_delete_req(r);
	Report("requests: a new one: poll 1 (not started), wait INVALID_ARGUMENT, nothing written; poll with no result 1",
	       r > 0 && p == 1 && w == kInvArg && pn == 1 && res == kSentinel && dr == 0,
	       Fmt("id %d, poll %s, wait %s, poll %s, result %s, delete %s", r, Hex(p).c_str(), Hex(w).c_str(), Hex(pn).c_str(),
	           Hex(res).c_str(), Hex(dr).c_str()));

	const int k1 = g_delete_req(kUnknownReq);
	const int k2 = g_abort_req(kUnknownReq);
	const int k3 = g_poll(kUnknownReq, &res);
	const int k4 = g_wait(kUnknownReq, &res);
	Report("requests: an unknown id: delete, abort, poll, wait INVALID_ID, nothing written",
	       k1 == kInvalidId && k2 == kInvalidId && k3 == kInvalidId && k4 == kInvalidId && res == kSentinel,
	       Fmt("%s %s %s %s", Hex(k1).c_str(), Hex(k2).c_str(), Hex(k3).c_str(), Hex(k4).c_str()));

	r          = g_create_req(c2);
	const int x1 = g_delete_req(r);
	const int x2 = g_delete_req(r);
	const int x3 = g_poll(r, &res);
	Report("requests: delete 0, then delete and poll INVALID_ID", x1 == 0 && x2 == kInvalidId && x3 == kInvalidId,
	       Fmt("%s %s %s", Hex(x1).c_str(), Hex(x2).c_str(), Hex(x3).c_str()));

	uint64_t len = 0xA5A5A5A5A5A5A5A5ull;
	r            = g_create_req(c3);
	const int s1 = small_as(r, g_out, 1024, &len, nullptr);
	int       pr = kSentinel;
	int       wr = kSentinel;
	p            = g_poll(r, &pr);
	w            = g_wait(r, &wr);
	pn           = g_poll(r, nullptr);
	const int wn = g_wait(r, nullptr);
	const int s2 = small(r, g_out, 1024, &len, nullptr);
	dr           = g_delete_req(r);
	Report("requests: started (TSS small storage on a user context): poll 0 and wait 0 with SIGNED_OUT, null results taken; "
	       "the blocking form SIGNED_OUT; nothing written",
	       s1 == 0 && p == 0 && pr == kSignedOut && w == 0 && wr == kSignedOut && pn == 0 && wn == 0 && s2 == kSignedOut &&
	           len == 0xA5A5A5A5A5A5A5A5ull && OutUntouched() && dr == 0,
	       Fmt("async %s, poll %s/%s, wait %s/%s, %s %s, blocking %s", Hex(s1).c_str(), Hex(p).c_str(), Hex(pr).c_str(),
	           Hex(w).c_str(), Hex(wr).c_str(), Hex(pn).c_str(), Hex(wn).c_str(), Hex(s2).c_str()));

	r             = g_create_req(c4);
	const int a1  = g_abort_req(r);
	const int ap  = g_poll(r, &res);
	const int as  = small_as(r, g_out, 16, &len, nullptr);
	pr            = kSentinel;
	wr            = kSentinel;
	p             = g_poll(r, &pr);
	w             = g_wait(r, &wr);
	const int ab  = small(r, g_out, 16, &len, nullptr);
	const int a2  = g_abort_req(r);
	dr            = g_delete_req(r);
	Report("requests: aborted before a start: poll still 1; the start finishes ABORTED (poll, wait); the blocking form "
	       "ABORTED; abort again 0",
	       a1 == 0 && ap == 1 && as == 0 && p == 0 && pr == kAborted && w == 0 && wr == kAborted && ab == kAborted && a2 == 0 &&
	           dr == 0,
	       Fmt("abort %s, poll %s, async %s, poll %s/%s, wait %s/%s, blocking %s", Hex(a1).c_str(), Hex(ap).c_str(),
	           Hex(as).c_str(), Hex(p).c_str(), Hex(pr).c_str(), Hex(w).c_str(), Hex(wr).c_str(), Hex(ab).c_str()));

	r            = g_create_req(c2);
	const int b1 = small_as(r, g_out, 16, &len, nullptr);
	const int b2 = g_abort_req(r);
	pr           = kSentinel;
	p            = g_poll(r, &pr);
	const int b3 = small_as(r, g_out, 16, &len, nullptr);
	wr           = kSentinel;
	w            = g_wait(r, &wr);
	dr           = g_delete_req(r);
	Report("requests: aborted after a start: poll keeps SIGNED_OUT; the next start finishes ABORTED",
	       b1 == 0 && b2 == 0 && p == 0 && pr == kSignedOut && b3 == 0 && w == 0 && wr == kAborted && dr == 0,
	       Fmt("%s %s, poll %s/%s, %s, wait %s/%s", Hex(b1).c_str(), Hex(b2).c_str(), Hex(p).c_str(), Hex(pr).c_str(),
	           Hex(b3).c_str(), Hex(w).c_str(), Hex(wr).c_str()));

	std::vector<int> reqs;
	int              over = 0;
	for (int i = 0; i < 300 && over == 0; i++) {
		const int q = g_create_req(c1);
		if (q > 0) {
			reqs.push_back(q);
		} else {
			over = q;
		}
	}
	const int other = g_create_req(c2); // the limit counts every context's requests
	const int dc1   = del_ctx(c1);      // and takes its requests with it
	const int pf    = reqs.empty() ? 0 : g_poll(reqs.front(), &res);
	const int pl    = reqs.empty() ? 0 : g_poll(reqs.back(), &res);
	const int dc2   = del_ctx(c1);
	const int rc1   = g_create_req(c1);
	r               = g_create_req(c2);
	dr              = g_delete_req(r);
	Report("requests: 256 at most: the 257th TOO_MANY_OBJECTS, on any context; deleting the context deletes its requests; "
	       "the context again INVALID_ID",
	       reqs.size() == 256 && over == kTooManyObj && other == kTooManyObj && dc1 == 0 && pf == kInvalidId && pl == kInvalidId &&
	           dc2 == kInvalidId && rc1 == kInvalidId && r > 0 && dr == 0,
	       Fmt("%zu made, then %s and %s; delete %s, polls %s %s, delete %s, request %s, then %d", reqs.size(), Hex(over).c_str(),
	           Hex(other).c_str(), Hex(dc1).c_str(), Hex(pf).c_str(), Hex(pl).c_str(), Hex(dc2).c_str(), Hex(rc1).c_str(), r));
	g_ctx = c2;
}

// ---- the 63 *Async/blocking pairs ---------------------------------------------------------------------------------------
using Call = std::function<int(int, bool)>; // (request, blocking form) -> answer

struct Check {
	std::string what;
	int         want; // the *Async form's answer: 0 (accepted) or the argument error
	Call        call;
};

template <typename F>
struct Fns {
	F async_fn = nullptr;
	F block_fn = nullptr;
	F operator()(bool block) const { return block ? block_fn : async_fn; }
};

template <typename F>
Fns<F> Pair2(const std::string& base) {
	Fns<F> f;
	f.async_fn = Fn<F>(base + "Async");
	f.block_fn = Fn<F>(base);
	return f;
}

template <typename A, typename M>
A With(A a, M mut) {
	mut(a);
	return a;
}

// Each check: on a fresh request (the *Async form: the check's answer, and the request started only when it is 0; the
// blocking form: the error or SIGNED_OUT), and on an unknown request (the argument error first, else INVALID_ID). Then
// the first (valid) check once on an aborted request. Off: the first check only, today's answer from both forms.
void RunPair(const std::string& base, const std::vector<Check>& checks) {
	SetCase(base);
	FillOut();
	std::string bad;
	if (!g_on) {
		const int a = checks.front().call(1, false);
		const int b = checks.front().call(1, true);
		Report("off: " + base + " and " + base + "Async: today's 0x80550005, nothing written", a == kToday && b == kToday && OutUntouched(),
		       Hex(a) + " " + Hex(b));
		return;
	}
	for (const auto& c: checks) {
		const int ra = NewRequest();
		const int a  = c.call(ra, false);
		int       pr = kSentinel;
		int       wr = kSentinel;
		const int p  = g_poll(ra, &pr);
		const int w  = g_wait(ra, &wr);
		g_delete_req(ra);
		const bool ok_a = a == c.want && (c.want == 0 ? (p == 0 && pr == kSignedOut && w == 0 && wr == kSignedOut)
		                                               : (p == 1 && pr == kSentinel && w == kInvArg && wr == kSentinel));
		const int  rb   = NewRequest();
		const int  b    = c.call(rb, true);
		g_delete_req(rb);
		const bool ok_b = b == (c.want == 0 ? kSignedOut : c.want);
		const int  ua   = c.call(kUnknownReq, false);
		const int  ub   = c.call(kUnknownReq, true);
		const int  uw   = c.want == 0 ? kInvalidId : c.want;
		if (!(ok_a && ok_b && ua == uw && ub == uw)) {
			bad += Fmt(" [%s: async %s poll %s/%s wait %s/%s, blocking %s, unknown request %s/%s; want %s]", c.what.c_str(),
			           Hex(a).c_str(), Hex(p).c_str(), Hex(pr).c_str(), Hex(w).c_str(), Hex(wr).c_str(), Hex(b).c_str(),
			           Hex(ua).c_str(), Hex(ub).c_str(), Hex(c.want).c_str());
		}
	}
	const int r  = NewRequest();
	const int ab = g_abort_req(r);
	const int a  = checks.front().call(r, false);
	int       pr = kSentinel;
	const int p  = g_poll(r, &pr);
	const int b  = checks.front().call(r, true);
	g_delete_req(r);
	if (!(ab == 0 && a == 0 && p == 0 && pr == kAborted && b == kAborted)) {
		bad += Fmt(" [aborted: %s %s poll %s/%s blocking %s]", Hex(ab).c_str(), Hex(a).c_str(), Hex(p).c_str(), Hex(pr).c_str(),
		           Hex(b).c_str());
	}
	if (!OutUntouched()) {
		bad += " [an output was written]";
	}
	Report(base + " and " + base + "Async", bad.empty(), Fmt("%zu checks%s", checks.size(), bad.c_str()));
}

enum class Form { NpId, Account, CrossSave, User, UserA, UserCrossSave };

bool ByName(Form f) {
	return f == Form::User || f == Form::UserA || f == Form::UserCrossSave;
}

const void* Target(Form f) {
	return ByName(f) ? static_cast<const void*>(&g_user) : static_cast<const void*>(&g_npid);
}

bool AccountForm(Form f) {
	return f == Form::Account || f == Form::CrossSave;
}

// -- multi-slot variables (get, set), multi-slot delete, multi-slot data statuses: (target, slot ids, array, count, option)
struct SlotArgs {
	const void*    target = nullptr;
	const int32_t* ids    = g_slots;
	void*          array  = g_out;
	int            count  = 3;
	void*          option = nullptr;
};

enum class SlotKind { Get, Set, Delete, Status };

Call SlotCall(const std::string& base, Form form, SlotKind kind, const SlotArgs& a) {
	const bool account = AccountForm(form);
	switch (kind) {
		case SlotKind::Get:
		case SlotKind::Status: {
			if (account) {
				const auto f = Pair2<IFn<int, uint64_t, const int32_t*, void*, uint64_t, int, void*>>(base);
				return [=](int req, bool block) { return f(block)(req, kAccount, a.ids, a.array, 64, a.count, a.option); };
			}
			const auto f = Pair2<IFn<int, const void*, const int32_t*, void*, uint64_t, int, void*>>(base);
			return [=](int req, bool block) { return f(block)(req, a.target, a.ids, a.array, 64, a.count, a.option); };
		}
		case SlotKind::Set: {
			const auto* values = static_cast<const int64_t*>(a.array);
			if (account) {
				const auto f = Pair2<IFn<int, uint64_t, const int32_t*, const int64_t*, int, void*>>(base);
				return [=](int req, bool block) { return f(block)(req, kAccount, a.ids, values, a.count, a.option); };
			}
			const auto f = Pair2<IFn<int, const void*, const int32_t*, const int64_t*, int, void*>>(base);
			return [=](int req, bool block) { return f(block)(req, a.target, a.ids, values, a.count, a.option); };
		}
		case SlotKind::Delete: {
			if (account) {
				const auto f = Pair2<IFn<int, uint64_t, const int32_t*, int, void*>>(base);
				return [=](int req, bool block) { return f(block)(req, kAccount, a.ids, a.count, a.option); };
			}
			const auto f = Pair2<IFn<int, const void*, const int32_t*, int, void*>>(base);
			return [=](int req, bool block) { return f(block)(req, a.target, a.ids, a.count, a.option); };
		}
	}
	SetupFail("slot kind");
}

// need_slots: the form answers no slot with INSUFFICIENT_ARGUMENT; npid_limit: too many slots is TOO_MANY_NPID;
// target_checked: a null NpId target is INSUFFICIENT_ARGUMENT (the NpId delete and data-status forms);
// run_form: sceNpTusDeleteMultiSlotDataVUser, which KYTY_BC5_NPTUS_FRIENDS_RUN changes (the 13.42 run: a null or empty user
// and arrayLen -1 taken, 0 INVALID_ARGUMENT; the rest as AnyPS5).
void SlotFamily(const std::string& base, Form form, SlotKind kind, bool need_slots, bool npid_limit, bool target_checked,
                bool run_form = false) {
	SlotArgs v;
	v.target = Target(form);
	if (kind == SlotKind::Set) {
		v.array = g_values;
	}
	const bool run       = g_run && run_form;
	const bool has_array = kind != SlotKind::Delete;
	const int  no_slot   = run ? kInvArg : (need_slots ? kInsuff : kInvArg);
	const int  minus_one = run ? 0 : (need_slots ? kInsuff : kInvArg);
	const int  minus_two = need_slots ? kInsuff : kInvArg; // the run keeps AnyPS5's answer
	const int  too_many  = npid_limit ? kTooManyNpId : kTooManySlots;
	const auto C         = [&](const char* what, int want, auto mut) {
        return Check {what, want, SlotCall(base, form, kind, With(v, mut))};
	};
	std::vector<Check> c;
	c.push_back(C("valid", 0, [](SlotArgs&) {}));
	c.push_back(C("64 slots", 0, [](SlotArgs& a) { a.count = 64; }));
	c.push_back(C("slot ids null", kInsuff, [](SlotArgs& a) { a.ids = nullptr; }));
	c.push_back(C("no slot", no_slot, [](SlotArgs& a) { a.count = 0; }));
	c.push_back(C("count -1", minus_one, [](SlotArgs& a) { a.count = -1; }));
	c.push_back(C("count -2", minus_two, [](SlotArgs& a) { a.count = -2; }));
	c.push_back(C("count -1 and an option", run ? kInvArg : minus_one, [](SlotArgs& a) {
		a.count  = -1;
		a.option = g_opt;
	}));
	c.push_back(C("count -1 and slot ids null", kInsuff, [](SlotArgs& a) {
		a.count = -1;
		a.ids   = nullptr;
	}));
	c.push_back(C("an option", kInvArg, [](SlotArgs& a) { a.option = g_opt; }));
	c.push_back(C("65 slots", too_many, [](SlotArgs& a) { a.count = 65; }));
	c.push_back(C("a negative slot id", kInvArg, [](SlotArgs& a) { a.ids = g_slots_neg; }));
	c.push_back(C("65 slots, one negative", too_many, [](SlotArgs& a) {
		a.ids   = g_slots_neg65;
		a.count = 65;
	}));
	c.push_back(C("no slot and an option", no_slot, [](SlotArgs& a) {
		a.count  = 0;
		a.option = g_opt;
	}));
	c.push_back(C("slot ids null and an option", kInsuff, [](SlotArgs& a) {
		a.ids    = nullptr;
		a.option = g_opt;
	}));
	if (has_array) {
		c.push_back(C("array null", kInsuff, [](SlotArgs& a) { a.array = nullptr; }));
		c.push_back(C("array null and an option", kInsuff, [](SlotArgs& a) {
			a.array  = nullptr;
			a.option = g_opt;
		}));
	}
	if (form == Form::NpId) {
		c.push_back(C(target_checked ? "NpId null" : "NpId null (not checked)", target_checked ? kInsuff : 0,
		              [](SlotArgs& a) { a.target = nullptr; }));
	}
	if (target_checked && form == Form::NpId) {
		c.push_back(C("NpId null and an option", kInsuff, [](SlotArgs& a) {
			a.target = nullptr;
			a.option = g_opt;
		}));
	}
	if (ByName(form)) {
		c.push_back(C("user null", run ? 0 : kInsuff, [](SlotArgs& a) { a.target = nullptr; }));
		c.push_back(C("user null and an option", run ? kInvArg : kInsuff, [](SlotArgs& a) {
			a.target = nullptr;
			a.option = g_opt;
		}));
		c.push_back(C("an empty name", run ? 0 : kInvArg, [](SlotArgs& a) { a.target = &g_noname; }));
		c.push_back(C("an empty name and 65 slots", too_many, [](SlotArgs& a) {
			a.target = &g_noname;
			a.count  = 65;
		}));
		c.push_back(C("an empty name and no slot", no_slot, [](SlotArgs& a) {
			a.target = &g_noname;
			a.count  = 0;
		}));
	}
	RunPair(base, c);
}

// -- add and get: (target, slot, value, author, date, out, out size, option)
struct AddArgs {
	const void* target = nullptr;
	int32_t     slot   = 1;
	void*       out    = g_out;
	void*       option = nullptr;
};

enum class AddOrder { NpId, Account, CrossSave, VUser, UserA }; // AnyPS5 :465, :206, :477, :499, :454/:488

void AddFamily(const std::string& base, Form form, AddOrder order) {
	AddArgs v;
	v.target           = Target(form);
	const bool account = AccountForm(form);
	const auto fa      = account ? Pair2<IFn<int, uint64_t, int32_t, int64_t, const void*, const void*, void*, uint64_t, void*>>(base)
	                             : Fns<IFn<int, uint64_t, int32_t, int64_t, const void*, const void*, void*, uint64_t, void*>> {};
	const auto fp = account ? Fns<IFn<int, const void*, int32_t, int64_t, const void*, const void*, void*, uint64_t, void*>> {}
	                        : Pair2<IFn<int, const void*, int32_t, int64_t, const void*, const void*, void*, uint64_t, void*>>(base);
	const auto C  = [&](const char* what, int want, auto mut) {
        const AddArgs a = With(v, mut);
        Call          call;
        if (account) {
            call = [=](int req, bool block) { return fa(block)(req, kAccount, a.slot, 5, nullptr, nullptr, a.out, 8, a.option); };
        } else {
            call = [=](int req, bool block) { return fp(block)(req, a.target, a.slot, 5, nullptr, nullptr, a.out, 8, a.option); };
        }
        return Check {what, want, call};
	};
	// out null and an option / out null and slot -1: which check comes first in each form
	const int out_opt  = order == AddOrder::NpId || order == AddOrder::VUser || order == AddOrder::CrossSave ? kInvArg : kInsuff;
	const int out_slot = order == AddOrder::CrossSave ? kInvArg : kInsuff;
	std::vector<Check> c;
	c.push_back(C("valid", 0, [](AddArgs&) {}));
	c.push_back(C("out null", kInsuff, [](AddArgs& a) { a.out = nullptr; }));
	c.push_back(C("slot -1", kInvArg, [](AddArgs& a) { a.slot = -1; }));
	c.push_back(C("an option", kInvArg, [](AddArgs& a) { a.option = g_opt; }));
	c.push_back(C("out null and an option", out_opt, [](AddArgs& a) {
		a.out    = nullptr;
		a.option = g_opt;
	}));
	c.push_back(C("out null and slot -1", out_slot, [](AddArgs& a) {
		a.out  = nullptr;
		a.slot = -1;
	}));
	if (form == Form::NpId) {
		c.push_back(C("NpId null (not checked)", 0, [](AddArgs& a) { a.target = nullptr; }));
	}
	if (ByName(form)) {
		c.push_back(C("user null", kInsuff, [](AddArgs& a) { a.target = nullptr; }));
		c.push_back(C("user null and an option", order == AddOrder::VUser ? kInvArg : kInsuff, [](AddArgs& a) {
			a.target = nullptr;
			a.option = g_opt;
		}));
		c.push_back(C("an empty name", kInvArg, [](AddArgs& a) { a.target = &g_noname; }));
		c.push_back(C("an empty name and out null", kInsuff, [](AddArgs& a) {
			a.target = &g_noname;
			a.out    = nullptr;
		}));
	}
	RunPair(base, c);
}

// -- get data: (target, slot, status, status size, data, recv size, option)
struct DataGetArgs {
	const void* target = nullptr;
	int32_t     slot   = 1;
	void*       status = g_out;
	uint64_t    size   = 0x1F0; // one of the two sizes the 13.42 run takes; AnyPS5 takes any size but 0
	void*       data   = g_out + 1024;
	void*       option = nullptr;
};

void DataGetFamily(const std::string& base, Form form) {
	DataGetArgs v;
	v.target           = Target(form);
	const bool account = AccountForm(form);
	const bool cross   = form == Form::CrossSave || form == Form::UserCrossSave;
	// KYTY_BC5_NPTUS_FRIENDS_RUN changes sceNpTusGetDataForCrossSaveVUser (the 13.42 run): only sizes 0x1F0 and 0x210 are
	// taken (another: INVALID_ALIGNMENT here, TODO(verify)), a null status and an empty name are taken
	const bool run     = g_run && form == Form::UserCrossSave;
	using FA           = IFn<int, uint64_t, int32_t, void*, uint64_t, void*, uint64_t, void*>;
	using FP           = IFn<int, const void*, int32_t, void*, uint64_t, void*, uint64_t, void*>;
	const auto fa      = account ? Pair2<FA>(base) : Fns<FA> {};
	const auto fp      = account ? Fns<FP> {} : Pair2<FP>(base);
	const auto C       = [&](const char* what, int want, auto mut) {
        const DataGetArgs a = With(v, mut);
        Call              call;
        if (account) {
            call = [=](int req, bool block) { return fa(block)(req, kAccount, a.slot, a.status, a.size, a.data, 32, a.option); };
        } else {
            call = [=](int req, bool block) { return fp(block)(req, a.target, a.slot, a.status, a.size, a.data, 32, a.option); };
        }
        return Check {what, want, call};
	};
	std::vector<Check> c;
	c.push_back(C("valid", 0, [](DataGetArgs&) {}));
	c.push_back(C("status size 0x210", 0, [](DataGetArgs& a) { a.size = 0x210; }));
	c.push_back(C("status size 0x200", run ? kInvAlign : 0, [](DataGetArgs& a) { a.size = 0x200; }));
	c.push_back(C("data null (not checked)", 0, [](DataGetArgs& a) { a.data = nullptr; }));
	c.push_back(C("status null", run ? 0 : kInsuff, [](DataGetArgs& a) { a.status = nullptr; }));
	c.push_back(C("status size 0", run ? kInvAlign : kInsuff, [](DataGetArgs& a) { a.size = 0; }));
	c.push_back(C("status null and size 0", run ? kInvAlign : kInsuff, [](DataGetArgs& a) {
		a.status = nullptr;
		a.size   = 0;
	}));
	c.push_back(C("slot -1", kInvArg, [](DataGetArgs& a) { a.slot = -1; }));
	c.push_back(C("an option", kInvArg, [](DataGetArgs& a) { a.option = g_opt; }));
	c.push_back(C("status null and an option", kInvArg, [](DataGetArgs& a) {
		a.status = nullptr;
		a.option = g_opt;
	}));
	c.push_back(C("slot -1 and status size 0", cross ? kInvArg : kInsuff, [](DataGetArgs& a) {
		a.slot = -1;
		a.size = 0;
	}));
	if (form == Form::NpId) {
		c.push_back(C("NpId null (not checked)", 0, [](DataGetArgs& a) { a.target = nullptr; }));
	}
	if (ByName(form)) {
		c.push_back(C("user null", kInsuff, [](DataGetArgs& a) { a.target = nullptr; }));
		c.push_back(C("user null and status size 0x200", kInsuff, [](DataGetArgs& a) {
			a.target = nullptr;
			a.size   = 0x200;
		}));
		c.push_back(C("an empty name", run ? 0 : kInvArg, [](DataGetArgs& a) { a.target = &g_noname; }));
		c.push_back(C("an empty name and status size 0", run ? kInvAlign : kInsuff, [](DataGetArgs& a) {
			a.target = &g_noname;
			a.size   = 0;
		}));
		c.push_back(C("user null and slot -1", cross ? kInvArg : kInsuff, [](DataGetArgs& a) {
			a.target = nullptr;
			a.slot   = -1;
		}));
	}
	RunPair(base, c);
}

// -- friends: (slot, include self, sort type, array, array size, count, option)
struct FriendsArgs {
	int32_t slot   = 0;
	int32_t sort   = 1;
	void*   array  = g_out;
	int     count  = 10;
	void*   option = nullptr;
};

FriendsOpt g_fopt_ok {sizeof(FriendsOpt), &g_rank1, nullptr};
FriendsOpt g_fopt_norank {sizeof(FriendsOpt), nullptr, nullptr};
FriendsOpt g_fopt_small {0x10, &g_rank1, nullptr};
FriendsOpt g_fopt_rank0 {sizeof(FriendsOpt), &g_rank0, nullptr};
FriendsOpt g_fopt_small0 {0x10, &g_rank0, nullptr};

void FriendsFamily(const std::string& base, int32_t last_sort, bool option_read) {
	using F      = IFn<int, int32_t, int32_t, int32_t, void*, uint64_t, int, void*>;
	const auto f = Pair2<F>(base);
	FriendsArgs v;
	const auto C = [&](const char* what, int want, auto mut) {
		const FriendsArgs a = With(v, mut);
		return Check {what, want, [=](int req, bool block) { return f(block)(req, a.slot, 1, a.sort, a.array, 640, a.count, a.option); }};
	};
	std::vector<Check> c;
	c.push_back(C("valid", 0, [](FriendsArgs&) {}));
	c.push_back(C("100 friends", 0, [](FriendsArgs& a) { a.count = 100; }));
	c.push_back(C("the last sort type", 0, [last_sort](FriendsArgs& a) { a.sort = last_sort; }));
	c.push_back(C("array null", kInsuff, [](FriendsArgs& a) { a.array = nullptr; }));
	c.push_back(C("no friend", kInvArg, [](FriendsArgs& a) { a.count = 0; }));
	c.push_back(C("slot -1", kInvArg, [](FriendsArgs& a) { a.slot = -1; }));
	c.push_back(C("101 friends", kTooManyNpId, [](FriendsArgs& a) { a.count = 101; }));
	c.push_back(C("sort type 0", kInvArg, [](FriendsArgs& a) { a.sort = 0; }));
	c.push_back(C("a sort type past the last", kInvArg, [last_sort](FriendsArgs& a) { a.sort = last_sort + 1; }));
	c.push_back(C("array null and no friend", kInsuff, [](FriendsArgs& a) {
		a.array = nullptr;
		a.count = 0;
	}));
	c.push_back(C("101 friends and sort type 0", kTooManyNpId, [](FriendsArgs& a) {
		a.count = 101;
		a.sort  = 0;
	}));
	if (!option_read) {
		c.push_back(C("an option (refused unread)", kInvArg, [](FriendsArgs& a) { a.option = &g_fopt_ok; }));
		c.push_back(C("an option and array null", kInsuff, [](FriendsArgs& a) {
			a.option = &g_fopt_ok;
			a.array  = nullptr;
		}));
	} else {
		// KYTY_BC5_NPTUS_FRIENDS_RUN (the 13.42 run): an option of another size is INVALID_ARGUMENT, start rank 0 is taken
		g_fopt_ok.hits      = reinterpret_cast<uint32_t*>(g_out + 2048); // never written
		g_fopt_norank.hits  = reinterpret_cast<uint32_t*>(g_out + 2048);
		g_fopt_small0.hits  = reinterpret_cast<uint32_t*>(g_out + 2048);
		const int bad_size  = g_run ? kInvArg : kInvAlign;
		c.push_back(C("an option, start rank 1", 0, [](FriendsArgs& a) { a.option = &g_fopt_ok; }));
		c.push_back(C("an option, no start rank", 0, [](FriendsArgs& a) { a.option = &g_fopt_norank; }));
		c.push_back(C("an option of size 0x10", bad_size, [](FriendsArgs& a) { a.option = &g_fopt_small; }));
		c.push_back(C("an option, start rank 0", g_run ? 0 : kInvArg, [](FriendsArgs& a) { a.option = &g_fopt_rank0; }));
		c.push_back(C("an option of size 0x10 and start rank 0", bad_size, [](FriendsArgs& a) { a.option = &g_fopt_small0; }));
		c.push_back(C("sort type 0 and an option of size 0x10", kInvArg, [](FriendsArgs& a) {
			a.sort   = 0;
			a.option = &g_fopt_small;
		}));
		c.push_back(C("101 friends and an option of size 0x10", kTooManyNpId, [](FriendsArgs& a) {
			a.count  = 101;
			a.option = &g_fopt_small;
		}));
	}
	RunPair(base, c);
}

// -- several users: (targets, slot, array, array size, count, option)
struct UsersArgs {
	const void* targets = nullptr;
	int32_t     slot    = 0;
	void*       array   = g_out;
	int         count   = 3;
	void*       option  = nullptr;
};

enum class UsersForm { NpId, VUser, Account, Names }; // AnyPS5 :675/732, :702/763, :656/683/713/740, :664/691/721/752

void UsersFamily(const std::string& base, UsersForm form) {
	using F               = IFn<int, const void*, int32_t, void*, uint64_t, int, void*>;
	const auto f          = Pair2<F>(base);
	const bool names      = form == UsersForm::VUser || form == UsersForm::Names;
	const bool need_count = form == UsersForm::NpId || form == UsersForm::VUser;
	const int  no_user    = need_count ? kInsuff : kInvArg;
	UsersArgs  v;
	v.targets = names ? static_cast<const void*>(g_users)
	                  : (form == UsersForm::NpId ? static_cast<const void*>(g_npids) : static_cast<const void*>(g_accounts));
	const auto C = [&](const char* what, int want, auto mut) {
		const UsersArgs a = With(v, mut);
		return Check {what, want, [=](int req, bool block) { return f(block)(req, a.targets, a.slot, a.array, 640, a.count, a.option); }};
	};
	std::vector<Check> c;
	c.push_back(C("valid", 0, [](UsersArgs&) {}));
	c.push_back(C("101 users", 0, [](UsersArgs& a) { a.count = 101; }));
	c.push_back(C("targets null", kInsuff, [](UsersArgs& a) { a.targets = nullptr; }));
	c.push_back(C("array null", kInsuff, [](UsersArgs& a) { a.array = nullptr; }));
	c.push_back(C("no user", no_user, [](UsersArgs& a) { a.count = 0; }));
	c.push_back(C("an option", kInvArg, [](UsersArgs& a) { a.option = g_opt; }));
	c.push_back(C("slot -1", kInvArg, [](UsersArgs& a) { a.slot = -1; }));
	c.push_back(C("102 users", kTooManyNpId, [](UsersArgs& a) { a.count = 102; }));
	c.push_back(C("an option and array null", kInsuff, [](UsersArgs& a) {
		a.option = g_opt;
		a.array  = nullptr;
	}));
	c.push_back(C("no user and an option", no_user, [](UsersArgs& a) {
		a.count  = 0;
		a.option = g_opt;
	}));
	c.push_back(C("102 users and slot -1", kInvArg, [](UsersArgs& a) {
		a.count = 102;
		a.slot  = -1;
	}));
	if (names) {
		c.push_back(C("the third name empty", kInvArg, [](UsersArgs& a) { a.targets = g_users_hole; }));
		c.push_back(C("the third name empty, 2 users", 0, [](UsersArgs& a) {
			a.targets = g_users_hole;
			a.count   = 2;
		}));
		c.push_back(C("the third name empty, 102 users", kTooManyNpId, [](UsersArgs& a) {
			a.targets = g_users_hole;
			a.count   = 102;
		}));
	} else {
		c.push_back(C("entries with an empty name (not read)", 0, [](UsersArgs& a) { a.targets = g_users_hole; }));
	}
	RunPair(base, c);
}

// -- set data: (target, slot, total size, send size, data, info, info size, author, date, option)
struct DataSetArgs {
	const void* target = nullptr;
	int32_t     slot   = 0;
	uint64_t    total  = 100;
	uint64_t    send   = 50;
	const void* data   = g_data;
	void*       option = nullptr;
};

void DataSetFamily(const std::string& base, Form form) {
	DataSetArgs v;
	v.target           = Target(form);
	const bool account = AccountForm(form);
	using FA = IFn<int, uint64_t, int32_t, uint64_t, uint64_t, const void*, const void*, uint64_t, const void*, const void*, void*>;
	using FP = IFn<int, const void*, int32_t, uint64_t, uint64_t, const void*, const void*, uint64_t, const void*, const void*, void*>;
	const auto fa = account ? Pair2<FA>(base) : Fns<FA> {};
	const auto fp = account ? Fns<FP> {} : Pair2<FP>(base);
	const auto C  = [&](const char* what, int want, auto mut) {
        const DataSetArgs a = With(v, mut);
        Call              call;
        if (account) {
            call = [=](int req, bool block) {
                return fa(block)(req, kAccount, a.slot, a.total, a.send, a.data, nullptr, 0, nullptr, nullptr, a.option);
            };
        } else {
            call = [=](int req, bool block) {
                return fp(block)(req, a.target, a.slot, a.total, a.send, a.data, nullptr, 0, nullptr, nullptr, a.option);
            };
        }
        return Check {what, want, call};
	};
	std::vector<Check> c;
	c.push_back(C("valid", 0, [](DataSetArgs&) {}));
	c.push_back(C("send size = total size", 0, [](DataSetArgs& a) { a.send = 100; }));
	c.push_back(C("data null", kInsuff, [](DataSetArgs& a) { a.data = nullptr; }));
	c.push_back(C("send size 0", kInsuff, [](DataSetArgs& a) { a.send = 0; }));
	c.push_back(C("slot -1", kInvArg, [](DataSetArgs& a) { a.slot = -1; }));
	c.push_back(C("send size > total size", kInvArg, [](DataSetArgs& a) { a.send = 101; }));
	c.push_back(C("an option", kInvArg, [](DataSetArgs& a) { a.option = g_opt; }));
	c.push_back(C("an option and data null", kInvArg, [](DataSetArgs& a) {
		a.option = g_opt;
		a.data   = nullptr;
	}));
	c.push_back(C("data null and slot -1", kInsuff, [](DataSetArgs& a) {
		a.data = nullptr;
		a.slot = -1;
	}));
	if (form == Form::NpId) {
		c.push_back(C("NpId null (not checked)", 0, [](DataSetArgs& a) { a.target = nullptr; }));
	}
	if (ByName(form)) {
		c.push_back(C("user null", kInsuff, [](DataSetArgs& a) { a.target = nullptr; }));
		c.push_back(C("user null and an option", kInvArg, [](DataSetArgs& a) {
			a.target = nullptr;
			a.option = g_opt;
		}));
		c.push_back(C("an empty name", kInvArg, [](DataSetArgs& a) { a.target = &g_noname; }));
		c.push_back(C("an empty name and send size 0", kInsuff, [](DataSetArgs& a) {
			a.target = &g_noname;
			a.send   = 0;
		}));
	}
	RunPair(base, c);
}

// -- try and set: (target, slot, operation, value, compare value, author, date, result, result size, option)
struct TryArgs {
	const void* target = nullptr;
	int32_t     slot   = 0;
	int32_t     op     = 1;
	void*       result = g_out;
	void*       option = nullptr;
};

void TryFamily(const std::string& base, Form form) {
	TryArgs v;
	v.target           = Target(form);
	const bool account = AccountForm(form);
	const int  bad_op  = form == Form::NpId || form == Form::User ? kInvArg : kInvType; // AnyPS5 :848, :886 / :822-:873
	using FA = IFn<int, uint64_t, int32_t, int32_t, int64_t, const int64_t*, const void*, const void*, void*, uint64_t, void*>;
	using FP = IFn<int, const void*, int32_t, int32_t, int64_t, const int64_t*, const void*, const void*, void*, uint64_t, void*>;
	const auto fa = account ? Pair2<FA>(base) : Fns<FA> {};
	const auto fp = account ? Fns<FP> {} : Pair2<FP>(base);
	const auto C  = [&](const char* what, int want, auto mut) {
        const TryArgs a = With(v, mut);
        Call          call;
        if (account) {
            call = [=](int req, bool block) {
                return fa(block)(req, kAccount, a.slot, a.op, 7, g_values, nullptr, nullptr, a.result, 8, a.option);
            };
        } else {
            call = [=](int req, bool block) {
                return fp(block)(req, a.target, a.slot, a.op, 7, g_values, nullptr, nullptr, a.result, 8, a.option);
            };
        }
        return Check {what, want, call};
	};
	std::vector<Check> c;
	c.push_back(C("valid", 0, [](TryArgs&) {}));
	c.push_back(C("operation 6", 0, [](TryArgs& a) { a.op = 6; }));
	c.push_back(C("result null", kInsuff, [](TryArgs& a) { a.result = nullptr; }));
	c.push_back(C("an option", kInvArg, [](TryArgs& a) { a.option = g_opt; }));
	c.push_back(C("slot -1", kInvArg, [](TryArgs& a) { a.slot = -1; }));
	c.push_back(C("operation 0", bad_op, [](TryArgs& a) { a.op = 0; }));
	c.push_back(C("operation 7", bad_op, [](TryArgs& a) { a.op = 7; }));
	c.push_back(C("result null and an option", kInsuff, [](TryArgs& a) {
		a.result = nullptr;
		a.option = g_opt;
	}));
	c.push_back(C("an option and operation 0", kInvArg, [](TryArgs& a) {
		a.option = g_opt;
		a.op     = 0;
	}));
	if (form == Form::NpId) {
		c.push_back(C("NpId null", kInsuff, [](TryArgs& a) { a.target = nullptr; }));
	}
	if (ByName(form)) {
		c.push_back(C("user null", kInsuff, [](TryArgs& a) { a.target = nullptr; }));
		c.push_back(C("an empty name", kInvArg, [](TryArgs& a) { a.target = &g_noname; }));
		c.push_back(C("an empty name and operation 0", bad_op, [](TryArgs& a) {
			a.target = &g_noname;
			a.op     = 0;
		}));
	}
	RunPair(base, c);
}

// -- TSS: get data (slot, status, status size, data, recv size, option) and small storage (data, max size, length, option)
struct TssArgs {
	int32_t     slot   = 0;
	void*       status = g_out;
	uint64_t    size   = 0x18;
	void*       data   = g_out + 1024;
	const void* option = nullptr;
};

uint64_t g_tss_offset = 4;
TssOpt   g_topt_ok {sizeof(TssOpt), &g_tss_offset, &g_tss_offset, nullptr};
TssOpt   g_topt_bad {0x18, nullptr, nullptr, nullptr};

void TssDataFamily() {
	using F      = IFn<int, int32_t, void*, uint64_t, void*, uint64_t, const void*>;
	const auto f = Pair2<F>("sceNpTssGetData");
	TssArgs    v;
	const auto C = [&](const char* what, int want, auto mut) {
		const TssArgs a = With(v, mut);
		return Check {what, want, [=](int req, bool block) { return f(block)(req, a.slot, a.status, a.size, a.data, 64, a.option); }};
	};
	std::vector<Check> c;
	c.push_back(C("valid", 0, [](TssArgs&) {}));
	c.push_back(C("slot 15", 0, [](TssArgs& a) { a.slot = 15; }));
	c.push_back(C("status null, its size 7 (not checked)", 0, [](TssArgs& a) {
		a.status = nullptr;
		a.size   = 7;
	}));
	c.push_back(C("data null (not checked)", 0, [](TssArgs& a) { a.data = nullptr; }));
	c.push_back(C("an option of size 0x20", 0, [](TssArgs& a) { a.option = &g_topt_ok; }));
	c.push_back(C("status size 0x10", kInvAlign, [](TssArgs& a) { a.size = 0x10; }));
	c.push_back(C("slot -1", kInvArg, [](TssArgs& a) { a.slot = -1; }));
	c.push_back(C("slot 16", kInvArg, [](TssArgs& a) { a.slot = 16; }));
	c.push_back(C("an option of size 0x18", kInvAlign, [](TssArgs& a) { a.option = &g_topt_bad; }));
	c.push_back(C("a bad option and slot 16", kInvAlign, [](TssArgs& a) {
		a.option = &g_topt_bad;
		a.slot   = 16;
	}));
	c.push_back(C("status size 0x10 and slot 16", kInvAlign, [](TssArgs& a) {
		a.size = 0x10;
		a.slot = 16;
	}));
	RunPair("sceNpTssGetData", c);
}

void TssSmallFamily() {
	const auto f = Pair2<SmallFn>("sceNpTssGetSmallStorage");
	auto* len    = reinterpret_cast<uint64_t*>(g_out + 3072); // never written
	const auto C = [&](const char* what, int want, void* data, uint64_t max, uint64_t* length, void* option) {
		return Check {what, want, [=](int req, bool block) { return f(block)(req, data, max, length, option); }};
	};
	std::vector<Check> c;
	c.push_back(C("valid", 0, g_out, 1024, len, nullptr));
	c.push_back(C("64 KiB", 0, g_out, 65536, len, nullptr));
	c.push_back(C("data and length null (not checked)", 0, nullptr, 1024, nullptr, nullptr));
	c.push_back(C("64 KiB + 1", kInvArg, g_out, 65537, len, nullptr));
	c.push_back(C("an option", kInvArg, g_out, 1024, len, g_opt));
	RunPair("sceNpTssGetSmallStorage", c);
}

void CasePairs() {
	// multi-slot variables: get (AnyPS5 :185, :255, :263, :271, :283, :295)
	SlotFamily("sceNpTusGetMultiSlotVariable", Form::NpId, SlotKind::Get, false, false, false);
	SlotFamily("sceNpTusGetMultiSlotVariableA", Form::Account, SlotKind::Get, false, false, false);
	SlotFamily("sceNpTusGetMultiSlotVariableForCrossSave", Form::CrossSave, SlotKind::Get, false, false, false);
	SlotFamily("sceNpTusGetMultiSlotVariableVUser", Form::User, SlotKind::Get, true, false, false);
	SlotFamily("sceNpTusGetMultiSlotVariableAVUser", Form::UserA, SlotKind::Get, false, false, false);
	SlotFamily("sceNpTusGetMultiSlotVariableForCrossSaveVUser", Form::UserCrossSave, SlotKind::Get, false, false, false);
	// multi-slot variables: set (:193, :311, :318)
	SlotFamily("sceNpTusSetMultiSlotVariable", Form::NpId, SlotKind::Set, false, false, false);
	SlotFamily("sceNpTusSetMultiSlotVariableA", Form::Account, SlotKind::Set, false, false, false);
	SlotFamily("sceNpTusSetMultiSlotVariableVUser", Form::User, SlotKind::Set, false, false, false);
	// multi-slot delete (:200, :329, :339, :350, :511, :520)
	SlotFamily("sceNpTusDeleteMultiSlotVariable", Form::NpId, SlotKind::Delete, true, false, true);
	SlotFamily("sceNpTusDeleteMultiSlotVariableA", Form::Account, SlotKind::Delete, false, false, false);
	SlotFamily("sceNpTusDeleteMultiSlotVariableVUser", Form::User, SlotKind::Delete, true, false, false);
	SlotFamily("sceNpTusDeleteMultiSlotData", Form::NpId, SlotKind::Delete, true, false, true);
	SlotFamily("sceNpTusDeleteMultiSlotDataA", Form::Account, SlotKind::Delete, false, false, false);
	SlotFamily("sceNpTusDeleteMultiSlotDataVUser", Form::User, SlotKind::Delete, true, false, false, true);
	// multi-slot data statuses (:597, :607, :617, :626, :636, :646)
	SlotFamily("sceNpTusGetMultiSlotDataStatus", Form::NpId, SlotKind::Status, true, true, true);
	SlotFamily("sceNpTusGetMultiSlotDataStatusVUser", Form::User, SlotKind::Status, true, true, false);
	SlotFamily("sceNpTusGetMultiSlotDataStatusA", Form::Account, SlotKind::Status, false, false, false);
	SlotFamily("sceNpTusGetMultiSlotDataStatusForCrossSave", Form::CrossSave, SlotKind::Status, false, false, false);
	SlotFamily("sceNpTusGetMultiSlotDataStatusAVUser", Form::UserA, SlotKind::Status, false, false, false);
	SlotFamily("sceNpTusGetMultiSlotDataStatusForCrossSaveVUser", Form::UserCrossSave, SlotKind::Status, false, false, false);
	// add and get (:206, :454, :465, :477, :488, :499)
	AddFamily("sceNpTusAddAndGetVariable", Form::NpId, AddOrder::NpId);
	AddFamily("sceNpTusAddAndGetVariableA", Form::Account, AddOrder::Account);
	AddFamily("sceNpTusAddAndGetVariableForCrossSave", Form::CrossSave, AddOrder::CrossSave);
	AddFamily("sceNpTusAddAndGetVariableVUser", Form::User, AddOrder::VUser);
	AddFamily("sceNpTusAddAndGetVariableAVUser", Form::UserA, AddOrder::UserA);
	AddFamily("sceNpTusAddAndGetVariableForCrossSaveVUser", Form::UserCrossSave, AddOrder::UserA);
	// get data (:371, :528, :538, :548, :558, :567)
	DataGetFamily("sceNpTusGetData", Form::NpId);
	DataGetFamily("sceNpTusGetDataA", Form::Account);
	DataGetFamily("sceNpTusGetDataForCrossSave", Form::CrossSave);
	DataGetFamily("sceNpTusGetDataVUser", Form::User);
	DataGetFamily("sceNpTusGetDataAVUser", Form::UserA);
	DataGetFamily("sceNpTusGetDataForCrossSaveVUser", Form::UserCrossSave);
	// friends (:384-430, :577, :587)
	FriendsFamily("sceNpTusGetFriendsDataStatus", 2, false);
	FriendsFamily("sceNpTusGetFriendsVariable", 4, false);
	FriendsFamily("sceNpTusGetFriendsDataStatusA", 2, true);
	FriendsFamily("sceNpTusGetFriendsDataStatusForCrossSave", 2, true);
	FriendsFamily("sceNpTusGetFriendsVariableA", 4, true);
	FriendsFamily("sceNpTusGetFriendsVariableForCrossSave", 4, true);
	// several users (:656-772)
	UsersFamily("sceNpTusGetMultiUserDataStatus", UsersForm::NpId);
	UsersFamily("sceNpTusGetMultiUserDataStatusVUser", UsersForm::VUser);
	UsersFamily("sceNpTusGetMultiUserDataStatusA", UsersForm::Account);
	UsersFamily("sceNpTusGetMultiUserDataStatusForCrossSave", UsersForm::Account);
	UsersFamily("sceNpTusGetMultiUserDataStatusAVUser", UsersForm::Names);
	UsersFamily("sceNpTusGetMultiUserDataStatusForCrossSaveVUser", UsersForm::Names);
	UsersFamily("sceNpTusGetMultiUserVariable", UsersForm::NpId);
	UsersFamily("sceNpTusGetMultiUserVariableVUser", UsersForm::VUser);
	UsersFamily("sceNpTusGetMultiUserVariableA", UsersForm::Account);
	UsersFamily("sceNpTusGetMultiUserVariableForCrossSave", UsersForm::Account);
	UsersFamily("sceNpTusGetMultiUserVariableAVUser", UsersForm::Names);
	UsersFamily("sceNpTusGetMultiUserVariableForCrossSaveVUser", UsersForm::Names);
	// set data (:774-820)
	DataSetFamily("sceNpTusSetData", Form::NpId);
	DataSetFamily("sceNpTusSetDataA", Form::Account);
	DataSetFamily("sceNpTusSetDataVUser", Form::User);
	DataSetFamily("sceNpTusSetDataAVUser", Form::UserA);
	// try and set (:822-897)
	TryFamily("sceNpTusTryAndSetVariable", Form::NpId);
	TryFamily("sceNpTusTryAndSetVariableVUser", Form::User);
	TryFamily("sceNpTusTryAndSetVariableA", Form::Account);
	TryFamily("sceNpTusTryAndSetVariableForCrossSave", Form::CrossSave);
	TryFamily("sceNpTusTryAndSetVariableAVUser", Form::UserA);
	TryFamily("sceNpTusTryAndSetVariableForCrossSaveVUser", Form::UserCrossSave);
	// TSS (:432-452, :899)
	TssDataFamily();
	TssSmallFamily();
}

void CaseHeld() {
	SetCase("held");
	std::string bad;
	if (g_on) {
		int absent = 0;
		for (const char* n: kHeld) {
			const char* nid = NidOf(n);
			if (g_db.Find(Key(nid)) == nullptr && g_db.FindByNid(nid, Loader::SymbolType::Func) == nullptr) {
				absent++;
			} else {
				bad += Fmt(" %s", n);
			}
		}
		Report("the 6 held stubs (AnyPS5 does not implement them) are not registered (exact key, FindByNid)", absent == 6,
		       Fmt("%d of 6 absent%s", absent, bad.c_str()));
		return;
	}
	int today = 0;
	for (const char* n: kHeld) {
		const int v = Fn<IFn<>>(n)();
		if (v == kToday) {
			today++;
		} else {
			bad += Fmt(" %s=%s", n, Hex(v).c_str());
		}
	}
	Report("off: the 6 held stubs are registered and answer today's 0x80550005", today == 6,
	       Fmt("%d of 6%s", today, bad.c_str()));
}

} // namespace tbt0405

int main(int argc, char** argv) {
	using namespace tbt0405;
	const bool  on   = SwitchOn("KYTY_BC5_LOAD_NPTUS");
	const bool  run  = SwitchOn("KYTY_BC5_NPTUS_FRIENDS_RUN");
	const char* mode = on && run ? "on" : (!on && !run ? "off" : "mixed");
	if (argc > 2 || (argc == 2 && std::strcmp(argv[1], mode) != 0)) {
		std::printf("tbt0405: the argument says %s but the switches say %s (nptus %d, friends run %d)\n",
		            argc == 2 ? argv[1] : "too much", mode, on ? 1 : 0, run ? 1 : 0);
		return 2;
	}
	g_on  = on;
	g_run = on && run; // the run switch acts only with the port on
	std::printf("tbt0405: switches nptus %d, friends run %d (in effect %d): %s\n", on ? 1 : 0, run ? 1 : 0, g_run ? 1 : 0,
	            mode);
	std::fflush(stdout);
	std::thread(Watchdog).detach();
	InitData();

	SetCase("init: registration");
	Libs::NpTus::InitNpTus_1(&g_db); // prints its "[bc5] exp 0405: nptus port on|off" line on stderr

	CaseRegistration();
	CaseCore();
	CasePairs();
	CaseHeld();

	const int n = g_cases.load();
	const int p = g_passed.load();
	if (p != n) {
		std::printf("tbt0405: %s %d of %d passed; FAIL\n", mode, p, n);
		std::fflush(stdout);
		std::_Exit(1);
	}
	std::printf("tbt0405: %s %d of %d; end\n", mode, p, n);
	std::fflush(stdout);
	std::_Exit(0);
}
