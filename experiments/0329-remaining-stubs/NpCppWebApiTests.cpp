// BC5 experiment 0328: tests of the ported libSceNpCppWebApi unit, after AnyPS5's tests/GuestNpCppWebApiString.cpp and
// tests/GuestNpCppWebApiIntrusivePtr.cpp (boykopovar/AnyPS5, GPL-2.0; the same Require style), on the instantiations
// the second title imports. The functions are called through their mangled symbols as the title calls them.
#include "common/abi.h"

#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>

struct IntrusivePtr {
	void* object;
	void (KYTY_SYSV_ABI* deleter)(void*);
	void* libContext;
};

extern "C" {
// Common::String
void KYTY_SYSV_ABI        _ZN3sce2Np9CppWebApi6Common6StringC1EPNS2_10LibContextE(void* self, void* libContext);
void KYTY_SYSV_ABI        _ZN3sce2Np9CppWebApi6Common6StringD1Ev(void* self);
int KYTY_SYSV_ABI         _ZN3sce2Np9CppWebApi6Common6String6appendEPKc(void* self, const char* text);
const char* KYTY_SYSV_ABI _ZNK3sce2Np9CppWebApi6Common6String5c_strEv(const void* self);
// Common::Vector<String>
void KYTY_SYSV_ABI _ZN3sce2Np9CppWebApi6Common6VectorINS2_6StringEEC1EPNS2_10LibContextE(void* self, void* libContext);
void KYTY_SYSV_ABI _ZN3sce2Np9CppWebApi6Common6VectorINS2_6StringEED1Ev(void* self);
int KYTY_SYSV_ABI  _ZN3sce2Np9CppWebApi6Common6VectorINS2_6StringEE8pushBackERKS4_(void* self, const void* element);
// Common::IntrusivePtr<SessionManager::V1::LocalizedString>
void KYTY_SYSV_ABI _ZN3sce2Np9CppWebApi6Common12IntrusivePtrINS1_14SessionManager2V115LocalizedStringEEC1Ev(IntrusivePtr*);
void KYTY_SYSV_ABI _ZN3sce2Np9CppWebApi6Common12IntrusivePtrINS1_14SessionManager2V115LocalizedStringEED1Ev(IntrusivePtr*);
// Common::IntrusivePtr<LocalizedString>: copy (the title imports this instantiation's copy ctor); RequestPlayerSession: operator->
void KYTY_SYSV_ABI  _ZN3sce2Np9CppWebApi6Common12IntrusivePtrINS1_14SessionManager2V115LocalizedStringEEC1ERS7_(IntrusivePtr*, const IntrusivePtr*);
void KYTY_SYSV_ABI  _ZN3sce2Np9CppWebApi6Common12IntrusivePtrINS1_14SessionManager2V120RequestPlayerSessionEED1Ev(IntrusivePtr*);
void* KYTY_SYSV_ABI _ZNK3sce2Np9CppWebApi6Common12IntrusivePtrINS1_14SessionManager2V120RequestPlayerSessionEEptEv(const IntrusivePtr*);
// Common::Vector<IntrusivePtr<RequestCreatePlayerSessionPlayer>>
void KYTY_SYSV_ABI _ZN3sce2Np9CppWebApi6Common6VectorINS2_12IntrusivePtrINS1_14SessionManager2V132RequestCreatePlayerSessionPlayerEEEEC1EPNS2_10LibContextE(IntrusivePtr*, void*);
void KYTY_SYSV_ABI _ZN3sce2Np9CppWebApi6Common6VectorINS2_12IntrusivePtrINS1_14SessionManager2V132RequestCreatePlayerSessionPlayerEEEED1Ev(IntrusivePtr*);
int KYTY_SYSV_ABI  _ZN3sce2Np9CppWebApi6Common6VectorINS2_12IntrusivePtrINS1_14SessionManager2V132RequestCreatePlayerSessionPlayerEEEE8pushBackERKS8_(IntrusivePtr*, const IntrusivePtr*);
// Common::initialize / terminate / LibContext
int KYTY_SYSV_ABI _ZN3sce2Np9CppWebApi6Common10LibContextC1Ev(uint64_t* self);
int KYTY_SYSV_ABI _ZN3sce2Np9CppWebApi6Common10initializeERKNS2_10InitParamsERNS2_10LibContextE(const void* params, uint64_t* context);
int KYTY_SYSV_ABI _ZN3sce2Np9CppWebApi6Common9terminateERNS2_10LibContextE(uint64_t* context);
// a request entry point: PlayerSessionsApi::ParameterToJoinPlayerSessionAsPlayer ctor/dtor exist; the API call itself
int KYTY_SYSV_ABI _ZN3sce2Np9CppWebApi14SessionManager2V117PlayerSessionsApi29ParameterToLeavePlayerSession10initializeEPNS1_6Common10LibContextEPKcSA_();
// experiment 0329: the transaction start named by cand0329.pl
int KYTY_SYSV_ABI _ZN3sce2Np9CppWebApi6Common15TransactionBaseINS2_12IntrusivePtrINS1_14SessionManager2V154GetUsersAccountIdPlayerSessionsInvitationsResponseBodyEEENS4_INS2_18ResponseHeaderBaseEEEE5startEPNS2_10LibContextE();
}

namespace {

int g_failed = 0;
void Check(bool v, const char* what) {
	std::fprintf(stderr, "NpCppWebApiTests: %s: %s\n", v ? "ok" : "FAILED", what);
	if (!v) g_failed++;
}

struct FakeObject {
	std::int32_t refcount; // at offset 0, as the console's objects
	std::int32_t pad;
	std::uint64_t payload;
};
int g_deleted = 0;
void KYTY_SYSV_ABI FakeDeleter(void* object) {
	g_deleted++;
	std::free(object);
}

void TestString() {
	alignas(8) unsigned char storage[0x20 + 16];
	std::memset(storage, 0xA5, sizeof(storage));
	void* s = storage;
	_ZN3sce2Np9CppWebApi6Common6StringC1EPNS2_10LibContextE(s, reinterpret_cast<void*>(0x1234));
	Check(*reinterpret_cast<std::int32_t*>(storage) == 0, "String ctor zeroes the reference count");
	Check(*reinterpret_cast<void**>(storage + 0x18) == reinterpret_cast<void*>(0x1234), "String ctor keeps the context at +0x18");
	Check(_ZN3sce2Np9CppWebApi6Common6String6appendEPKc(s, "abc") == 0, "append returns 0");
	Check(_ZN3sce2Np9CppWebApi6Common6String6appendEPKc(s, "defghijklmnopqrstuvwxyz0123456789") == 0, "append grows the buffer");
	Check(std::strcmp(_ZNK3sce2Np9CppWebApi6Common6String5c_strEv(s), "abcdefghijklmnopqrstuvwxyz0123456789") == 0, "c_str holds both appends");
	_ZN3sce2Np9CppWebApi6Common6StringD1Ev(s);
	Check(*reinterpret_cast<void**>(storage + 0x08) == nullptr, "String dtor frees and clears the buffer");
	for (int i = 0x20; i < 0x30; i++) {
		if (storage[i] != 0xA5) { Check(false, "String stays within 0x20 bytes"); return; }
	}
	Check(true, "String stays within 0x20 bytes");
}

void TestVectorOfString() {
	alignas(8) unsigned char v[0x18];
	std::memset(v, 0, sizeof(v));
	_ZN3sce2Np9CppWebApi6Common6VectorINS2_6StringEEC1EPNS2_10LibContextE(v, nullptr);
	alignas(8) unsigned char s[0x20];
	_ZN3sce2Np9CppWebApi6Common6StringC1EPNS2_10LibContextE(s, nullptr);
	_ZN3sce2Np9CppWebApi6Common6String6appendEPKc(s, "leader");
	Check(_ZN3sce2Np9CppWebApi6Common6VectorINS2_6StringEE8pushBackERKS4_(v, s) == 0, "Vector<String>::pushBack returns 0");
	Check(_ZN3sce2Np9CppWebApi6Common6VectorINS2_6StringEE8pushBackERKS4_(v, s) == 0, "a second pushBack returns 0");
	auto* body = *reinterpret_cast<unsigned char**>(v);
	Check(body != nullptr, "the vector has a body after pushBack");
	if (body != nullptr) {
		Check(*reinterpret_cast<std::uint64_t*>(body + 0x40) == 2, "the body holds two elements");
		Check(*reinterpret_cast<std::int32_t*>(body + 0x30) == 1, "the body's reference count is 1");
	}
	_ZN3sce2Np9CppWebApi6Common6StringD1Ev(s);
	_ZN3sce2Np9CppWebApi6Common6VectorINS2_6StringEED1Ev(v);
	Check(*reinterpret_cast<void**>(v) == nullptr, "Vector<String> dtor releases the body");
}

void TestIntrusivePtr() {
	IntrusivePtr empty {};
	_ZN3sce2Np9CppWebApi6Common12IntrusivePtrINS1_14SessionManager2V115LocalizedStringEEC1Ev(&empty);
	Check(empty.object == nullptr && empty.deleter == nullptr, "a default IntrusivePtr is empty");
	_ZN3sce2Np9CppWebApi6Common12IntrusivePtrINS1_14SessionManager2V115LocalizedStringEED1Ev(&empty);
	Check(true, "destroying an empty IntrusivePtr is a no-op");

	auto* obj = static_cast<FakeObject*>(std::calloc(1, sizeof(FakeObject)));
	obj->refcount = 1;
	obj->payload  = 42;
	IntrusivePtr a {obj, &FakeDeleter, nullptr};
	IntrusivePtr b {};
	_ZN3sce2Np9CppWebApi6Common12IntrusivePtrINS1_14SessionManager2V115LocalizedStringEEC1ERS7_(&b, &a);
	Check(obj->refcount == 2 && b.object == obj && b.deleter == &FakeDeleter, "the copy ctor shares the object and adds a reference");
	Check(_ZNK3sce2Np9CppWebApi6Common12IntrusivePtrINS1_14SessionManager2V120RequestPlayerSessionEEptEv(&b) == obj, "operator-> returns the object");
	g_deleted = 0;
	_ZN3sce2Np9CppWebApi6Common12IntrusivePtrINS1_14SessionManager2V115LocalizedStringEED1Ev(&b);
	Check(obj->refcount == 1 && g_deleted == 0, "releasing one of two references keeps the object (the field is left as AnyPS5 leaves it)");
	_ZN3sce2Np9CppWebApi6Common12IntrusivePtrINS1_14SessionManager2V120RequestPlayerSessionEED1Ev(&a);
	Check(g_deleted == 1 && a.object == nullptr && a.deleter == nullptr, "releasing the last reference calls the deleter once");
}

void TestVectorOfIntrusivePtr() {
	IntrusivePtr v {};
	_ZN3sce2Np9CppWebApi6Common6VectorINS2_12IntrusivePtrINS1_14SessionManager2V132RequestCreatePlayerSessionPlayerEEEEC1EPNS2_10LibContextE(&v, nullptr);
	auto* obj = static_cast<FakeObject*>(std::calloc(1, sizeof(FakeObject)));
	obj->refcount = 1;
	IntrusivePtr e {obj, &FakeDeleter, nullptr};
	g_deleted = 0;
	Check(_ZN3sce2Np9CppWebApi6Common6VectorINS2_12IntrusivePtrINS1_14SessionManager2V132RequestCreatePlayerSessionPlayerEEEE8pushBackERKS8_(&v, &e) == 0, "pushBack of an IntrusivePtr returns 0");
	Check(obj->refcount == 2, "the vector holds a reference to the element");
	_ZN3sce2Np9CppWebApi6Common6VectorINS2_12IntrusivePtrINS1_14SessionManager2V132RequestCreatePlayerSessionPlayerEEEED1Ev(&v);
	Check(obj->refcount == 1 && g_deleted == 0 && v.object == nullptr, "destroying the vector releases its element's reference");
	_ZN3sce2Np9CppWebApi6Common12IntrusivePtrINS1_14SessionManager2V120RequestPlayerSessionEED1Ev(&e);
	Check(g_deleted == 1, "the element's last reference deletes it");
}

void TestContextAndOfflineRequests() {
	uint64_t ctx = 99;
	Check(_ZN3sce2Np9CppWebApi6Common10LibContextC1Ev(&ctx) == 0 && ctx == 0, "LibContext ctor zeroes the context");
	Check(_ZN3sce2Np9CppWebApi6Common10initializeERKNS2_10InitParamsERNS2_10LibContextE(nullptr, &ctx) == 0 && ctx == 1, "initialize succeeds as on an offline console");
	Check(_ZN3sce2Np9CppWebApi14SessionManager2V117PlayerSessionsApi29ParameterToLeavePlayerSession10initializeEPNS1_6Common10LibContextEPKcSA_() == 0, "a parameter initialize succeeds (bookkeeping)");
	Check(_ZN3sce2Np9CppWebApi6Common9terminateERNS2_10LibContextE(&ctx) == 0, "terminate returns 0");
}

} // namespace

int main() {
	TestString();
	TestVectorOfString();
	TestIntrusivePtr();
	TestVectorOfIntrusivePtr();
	TestContextAndOfflineRequests();
	Check(_ZN3sce2Np9CppWebApi6Common15TransactionBaseINS2_12IntrusivePtrINS1_14SessionManager2V154GetUsersAccountIdPlayerSessionsInvitationsResponseBodyEEENS4_INS2_18ResponseHeaderBaseEEEE5startEPNS2_10LibContextE() == static_cast<int>(0x80552907), "exp 0329: the invitations transaction's start is NOT_SIGNED_IN");
	if (g_failed != 0) {
		std::fprintf(stderr, "NpCppWebApiTests: %d check(s) FAILED\n", g_failed);
		return 1;
	}
	std::fprintf(stderr, "NpCppWebApiTests: all checks passed\n");
	return 0;
}
