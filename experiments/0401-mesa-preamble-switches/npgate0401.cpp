// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0401 series e, switch 1 (KYTY_BC5_NP_SESSION_V2): the R32 gate on the box. Lesson R32 (a NID bound a
// function of another ABI): name -> NID (nid0401.py, laptop) -> the real SymbolDatabase after Libs::InitAll -> the
// function. It runs the host's own registration, then for each of the ten NIDs mknp0401.py adds:
//   on:  FindByNid and Find (the title's import key) give a record whose address is that function, whose debug name is
//        its mangled name, and whose library and module are those of exp 0328's other 136 entry points;
//   off: neither finds anything (the loader's return-0 stub answers, as before the switch).
// Then it calls the nine requests and factories (their bodies take no arguments: AnyPS5's and ours ignore them, so a
// call with none is safe) and expects SCE_NP_WEBAPI_ERROR_NOT_SIGNED_IN, and the parameter initialize with null
// arguments (its body ignores them) and expects 0. Exit 0 only after the end marker.
// Build: the compile command of src/libs/libNpCppWebApi.cpp with this file as the source, linked with every emulator
// object but main.cpp.o (the private libNpCppWebApi.cpp.o among them) and the link line's libraries.
// usage: KYTY_BC5_NP_SESSION_V2=1 npgate0401 on      KYTY_BC5_NP_SESSION_V2=0 npgate0401 off   (unset is off too)

#include "common/abi.h"
#include "libs/libs.h"
#include "loader/symbolDatabase.h"

#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <type_traits>

namespace npgate {
struct IntrusivePtr { // the unit's IntrusivePtr (libNpCppWebApi.cpp): object, deleter, libContext
	void* object;
	void (KYTY_SYSV_ABI* deleter)(void*);
	void* libContext;
};
static_assert(sizeof(IntrusivePtr) == 0x18);
} // namespace npgate

// The ten, declared exactly as mknp0401.py defines them (extern "C", so the namespace of the definition does not matter).
extern "C" {
int KYTY_SYSV_ABI _ZN3sce2Np9CppWebApi14SessionManager2V117PlayerSessionsApi20createPlayerSessionsEiRKNS4_31ParameterToCreatePlayerSessionsERNS1_6Common11TransactionINS8_12IntrusivePtrINS3_30PostPlayerSessionsResponseBodyEEENSA_INS8_18ResponseHeaderBaseEEEEE();
int KYTY_SYSV_ABI _ZN3sce2Np9CppWebApi14SessionManager2V117PlayerSessionsApi25joinPlayerSessionAsPlayerEiRKNS4_36ParameterToJoinPlayerSessionAsPlayerERNS1_6Common11TransactionINS8_12IntrusivePtrINS3_52PostPlayerSessionsSessionIdMemberPlayersResponseBodyEEENSA_INS8_18ResponseHeaderBaseEEEEE();
int KYTY_SYSV_ABI _ZN3sce2Np9CppWebApi14SessionManager2V117PlayerSessionsApi18leavePlayerSessionEiRKNS4_29ParameterToLeavePlayerSessionERNS1_6Common11TransactionINS8_15DefaultResponseENS8_12IntrusivePtrINS8_18ResponseHeaderBaseEEEEE();
int KYTY_SYSV_ABI _ZN3sce2Np9CppWebApi14SessionManager2V117PlayerSessionsApi27getPlayerSessionInvitationsEiRKNS4_38ParameterToGetPlayerSessionInvitationsERNS1_6Common11TransactionINS8_12IntrusivePtrINS3_54GetUsersAccountIdPlayerSessionsInvitationsResponseBodyEEENSA_INS8_18ResponseHeaderBaseEEEEE();
int KYTY_SYSV_ABI _ZN3sce2Np9CppWebApi14SessionManager2V117PlayerSessionsApi36ParameterToJoinPlayerSessionAsPlayer10initializeEPNS1_6Common10LibContextEPKcNS6_12IntrusivePtrINS3_51PostPlayerSessionsSessionIdMemberPlayersRequestBodyEEE(void* self, const uint64_t* context, const char* sessionId, const npgate::IntrusivePtr* body);
int KYTY_SYSV_ABI _ZN3sce2Np9CppWebApi14SessionManager2V127RequestPlayerSessionFactory6createEPNS1_6Common10LibContextEiNS5_12IntrusivePtrINS3_32RequestPlayerSessionMemberPlayerEEERKNS5_6VectorINS5_6StringEEENS8_INS3_15LocalizedStringEEEPNS8_INS3_20RequestPlayerSessionEEE();
int KYTY_SYSV_ABI _ZN3sce2Np9CppWebApi14SessionManager2V139RequestCreatePlayerSessionPlayerFactory6createEPNS1_6Common10LibContextEPKcS9_RKNS5_6VectorINS5_12IntrusivePtrINS3_24PlayerSessionPushContextEEEEEPNSB_INS3_32RequestCreatePlayerSessionPlayerEEE();
int KYTY_SYSV_ABI _ZN3sce2Np9CppWebApi14SessionManager2V139RequestPlayerSessionMemberPlayerFactory6createEPNS1_6Common10LibContextERKNS5_6VectorINS5_12IntrusivePtrINS3_32RequestCreatePlayerSessionPlayerEEEEEPNS9_INS3_32RequestPlayerSessionMemberPlayerEEE();
int KYTY_SYSV_ABI _ZN3sce2Np9CppWebApi14SessionManager2V136PostPlayerSessionsRequestBodyFactory6createEPNS1_6Common10LibContextERKNS5_6VectorINS5_12IntrusivePtrINS3_20RequestPlayerSessionEEEEEPNS9_INS3_29PostPlayerSessionsRequestBodyEEE();
int KYTY_SYSV_ABI _ZN3sce2Np9CppWebApi14SessionManager2V158PostPlayerSessionsSessionIdMemberPlayersRequestBodyFactory6createEPNS1_6Common10LibContextERKNS5_6VectorINS5_12IntrusivePtrINS3_26RequestPlayerSessionPlayerEEEEEPNS9_INS3_51PostPlayerSessionsSessionIdMemberPlayersRequestBodyEEE();
}

namespace npgate {
using Request = int (KYTY_SYSV_ABI*)();
using Init    = int (KYTY_SYSV_ABI*)(void*, const uint64_t*, const char*, const IntrusivePtr*);

static_assert(std::is_same_v<decltype(&_ZN3sce2Np9CppWebApi14SessionManager2V117PlayerSessionsApi20createPlayerSessionsEiRKNS4_31ParameterToCreatePlayerSessionsERNS1_6Common11TransactionINS8_12IntrusivePtrINS3_30PostPlayerSessionsResponseBodyEEENSA_INS8_18ResponseHeaderBaseEEEEE), Request>);
static_assert(std::is_same_v<decltype(&_ZN3sce2Np9CppWebApi14SessionManager2V117PlayerSessionsApi36ParameterToJoinPlayerSessionAsPlayer10initializeEPNS1_6Common10LibContextEPKcNS6_12IntrusivePtrINS3_51PostPlayerSessionsSessionIdMemberPlayersRequestBodyEEE), Init>);

struct Entry {
	const char* nid;
	const char* name;
	Request     request; // null for the initialize
	Init        init;    // null for the requests
};

// NID -> mangled name: nid0401.py checks each pair on the laptop with exp 0327's calculator.
#define NPGATE_REQ(nid, f) Entry {nid, #f, &f, nullptr}
static const Entry kTen[] = {
    NPGATE_REQ("eVU3cXIJz0w", _ZN3sce2Np9CppWebApi14SessionManager2V117PlayerSessionsApi20createPlayerSessionsEiRKNS4_31ParameterToCreatePlayerSessionsERNS1_6Common11TransactionINS8_12IntrusivePtrINS3_30PostPlayerSessionsResponseBodyEEENSA_INS8_18ResponseHeaderBaseEEEEE),
    NPGATE_REQ("BY1jyWLZrcA", _ZN3sce2Np9CppWebApi14SessionManager2V117PlayerSessionsApi25joinPlayerSessionAsPlayerEiRKNS4_36ParameterToJoinPlayerSessionAsPlayerERNS1_6Common11TransactionINS8_12IntrusivePtrINS3_52PostPlayerSessionsSessionIdMemberPlayersResponseBodyEEENSA_INS8_18ResponseHeaderBaseEEEEE),
    NPGATE_REQ("JiY4sfHkV34", _ZN3sce2Np9CppWebApi14SessionManager2V117PlayerSessionsApi18leavePlayerSessionEiRKNS4_29ParameterToLeavePlayerSessionERNS1_6Common11TransactionINS8_15DefaultResponseENS8_12IntrusivePtrINS8_18ResponseHeaderBaseEEEEE),
    NPGATE_REQ("LbhH9NeB93I", _ZN3sce2Np9CppWebApi14SessionManager2V117PlayerSessionsApi27getPlayerSessionInvitationsEiRKNS4_38ParameterToGetPlayerSessionInvitationsERNS1_6Common11TransactionINS8_12IntrusivePtrINS3_54GetUsersAccountIdPlayerSessionsInvitationsResponseBodyEEENSA_INS8_18ResponseHeaderBaseEEEEE),
    Entry {"XuVY56j7GM0", "_ZN3sce2Np9CppWebApi14SessionManager2V117PlayerSessionsApi36ParameterToJoinPlayerSessionAsPlayer10initializeEPNS1_6Common10LibContextEPKcNS6_12IntrusivePtrINS3_51PostPlayerSessionsSessionIdMemberPlayersRequestBodyEEE", nullptr,
           &_ZN3sce2Np9CppWebApi14SessionManager2V117PlayerSessionsApi36ParameterToJoinPlayerSessionAsPlayer10initializeEPNS1_6Common10LibContextEPKcNS6_12IntrusivePtrINS3_51PostPlayerSessionsSessionIdMemberPlayersRequestBodyEEE},
    NPGATE_REQ("fIzsqjyD5oY", _ZN3sce2Np9CppWebApi14SessionManager2V127RequestPlayerSessionFactory6createEPNS1_6Common10LibContextEiNS5_12IntrusivePtrINS3_32RequestPlayerSessionMemberPlayerEEERKNS5_6VectorINS5_6StringEEENS8_INS3_15LocalizedStringEEEPNS8_INS3_20RequestPlayerSessionEEE),
    NPGATE_REQ("sRn6qePT54Q", _ZN3sce2Np9CppWebApi14SessionManager2V139RequestCreatePlayerSessionPlayerFactory6createEPNS1_6Common10LibContextEPKcS9_RKNS5_6VectorINS5_12IntrusivePtrINS3_24PlayerSessionPushContextEEEEEPNSB_INS3_32RequestCreatePlayerSessionPlayerEEE),
    NPGATE_REQ("-0Vv7HKZaBM", _ZN3sce2Np9CppWebApi14SessionManager2V139RequestPlayerSessionMemberPlayerFactory6createEPNS1_6Common10LibContextERKNS5_6VectorINS5_12IntrusivePtrINS3_32RequestCreatePlayerSessionPlayerEEEEEPNS9_INS3_32RequestPlayerSessionMemberPlayerEEE),
    NPGATE_REQ("yl3T9brJay4", _ZN3sce2Np9CppWebApi14SessionManager2V136PostPlayerSessionsRequestBodyFactory6createEPNS1_6Common10LibContextERKNS5_6VectorINS5_12IntrusivePtrINS3_20RequestPlayerSessionEEEEEPNS9_INS3_29PostPlayerSessionsRequestBodyEEE),
    NPGATE_REQ("xjVhrq2KPJA", _ZN3sce2Np9CppWebApi14SessionManager2V158PostPlayerSessionsSessionIdMemberPlayersRequestBodyFactory6createEPNS1_6Common10LibContextERKNS5_6VectorINS5_12IntrusivePtrINS3_26RequestPlayerSessionPlayerEEEEEPNS9_INS3_51PostPlayerSessionsSessionIdMemberPlayersRequestBodyEEE),
};
#undef NPGATE_REQ
static_assert(sizeof(kTen) / sizeof(kTen[0]) == 10);

constexpr int  kNotSignedIn = static_cast<int>(0x80552907);
constexpr char kSibling[]   = "ZZpDSZob2Bs"; // exp 0328's ParameterToLeavePlayerSession::initialize, always registered

static Loader::SymbolResolve Import(const char* nid) { // the key a title's import of libSceNpCppWebApi looks up
	Loader::SymbolResolve r {};
	r.name                 = nid;
	r.library              = "libSceNpCppWebApi";
	r.library_version      = 1;
	r.module               = "libSceNpCppWebApi";
	r.module_version_major = 1;
	r.module_version_minor = 1;
	r.type                 = Loader::SymbolType::Func;
	return r;
}

static uint64_t Address(const Entry& e) {
	return e.request != nullptr ? reinterpret_cast<uint64_t>(e.request) : reinterpret_cast<uint64_t>(e.init);
}
} // namespace npgate

int main(int argc, char** argv) {
	using namespace npgate;
	if (argc != 2 || (std::strcmp(argv[1], "on") != 0 && std::strcmp(argv[1], "off") != 0)) {
		std::printf("usage: npgate0401 on|off (with KYTY_BC5_NP_SESSION_V2 set to match)\n");
		return 2;
	}
	const bool  want   = std::strcmp(argv[1], "on") == 0;
	const char* v2     = std::getenv("KYTY_BC5_NP_SESSION_V2");
	const bool  env_on = v2 != nullptr && v2[0] != '\0' && std::strcmp(v2, "0") != 0;
	if (want != env_on) {
		std::printf("npgate0401: the argument says %s but KYTY_BC5_NP_SESSION_V2 is %s\n", argv[1], v2 != nullptr ? v2 : "unset");
		return 2;
	}

	Loader::SymbolDatabase db;
	Libs::InitAll(&db);

	const Loader::SymbolRecord* sib = db.FindByNid(kSibling, Loader::SymbolType::Func);
	if (sib == nullptr || sib->name.find('[') == std::string::npos || db.Find(Import(kSibling)) == nullptr) {
		std::printf("npgate0401: FAIL exp 0328's %s is not found the way the title imports it: InitAll did not run as expected\n", kSibling);
		return 1;
	}
	const std::string suffix = sib->name.substr(sib->name.find('[')); // [NpCppWebApi_v1][NpCppWebApi_v1.1][Func]

	int registered = 0;
	int bad        = 0;
	for (const Entry& e: kTen) {
		const Loader::SymbolRecord* by_nid = db.FindByNid(e.nid, Loader::SymbolType::Func);
		const Loader::SymbolRecord* by_key = db.Find(Import(e.nid));
		if (want) {
			const bool ok = by_nid != nullptr && by_key != nullptr && by_nid->vaddr == Address(e) && by_key->vaddr == Address(e) &&
			                by_nid->dbg_name == e.name && by_nid->name == std::string(e.nid) + suffix;
			if (ok) {
				registered++;
			} else {
				bad++;
				std::printf("npgate0401: FAIL %s: by NID %s (0x%016llx, %s), by import key %s, want 0x%016llx %s\n", e.nid,
				            by_nid != nullptr ? by_nid->name.c_str() : "none",
				            by_nid != nullptr ? static_cast<unsigned long long>(by_nid->vaddr) : 0ull,
				            by_nid != nullptr ? by_nid->dbg_name.c_str() : "-", by_key != nullptr ? "found" : "none",
				            static_cast<unsigned long long>(Address(e)), e.name);
			}
		} else if (by_nid != nullptr || by_key != nullptr) {
			bad++;
			std::printf("npgate0401: FAIL %s is registered with the switch off: %s\n", e.nid,
			            by_nid != nullptr ? by_nid->dbg_name.c_str() : "by import key only");
		}
	}

	int not_signed_in = 0;
	int init_ok       = 0;
	for (const Entry& e: kTen) {
		if (e.request != nullptr) {
			const int r = e.request();
			if (r == kNotSignedIn) {
				not_signed_in++;
			} else {
				bad++;
				std::printf("npgate0401: FAIL %s returned 0x%08x, want 0x80552907\n", e.nid, static_cast<unsigned>(r));
			}
		} else {
			const int r = e.init(nullptr, nullptr, nullptr, nullptr);
			if (r == 0) {
				init_ok++;
			} else {
				bad++;
				std::printf("npgate0401: FAIL %s returned 0x%08x, want 0\n", e.nid, static_cast<unsigned>(r));
			}
		}
	}

	if (bad != 0) {
		std::printf("npgate0401: %s %d failures\n", argv[1], bad);
		return 1;
	}
	if (want) {
		std::printf("npgate0401: on %d of 10 registered as their functions in %s, %d of 9 NOT_SIGNED_IN, initialize %d of 1; end\n",
		            registered, suffix.c_str(), not_signed_in, init_ok);
	} else {
		std::printf("npgate0401: off 10 of 10 unregistered, %d of 9 NOT_SIGNED_IN, initialize %d of 1; end\n", not_signed_in, init_ok);
	}
	return 0;
}
