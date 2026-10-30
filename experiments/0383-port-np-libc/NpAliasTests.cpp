// SPDX-License-Identifier: GPL-2.0-only
// BC5 PORT-NP: tests of the self-aliasing fix in the real src/libs/libNpCppWebApi.cpp. The test patterns (alias-append,
// alias-vector, many lengths and substring points) follow AnyPS5's core/libs/tests/GuestNpCppWebApiString.cpp and
// GuestNpCppWebApiIntrusivePtr.cpp at daf4eb3 (boykopovar/AnyPS5, GPL-2.0-only); the code here is written for this tree.
//
// The unit is included, not linked: its std::malloc, calloc, realloc and free go to the tracker below, so that every
// realloc really moves the block, the n-th allocation can be made to fail, and leaks and double frees are counted
// whatever the platform's sanitizer offers. Everything else is the unit's own code, called through its mangled symbols.
//
//   NpAliasTests list        the case names, one per line
//   NpAliasTests <case>      one case; a sanitizer abort stops only that case when a runner starts one process per case
//   NpAliasTests all         every case in one process
#include "common/abi.h"
#include "common/assert.h"
#include "common/hostException.h"
#include "common/logging/log.h"
#include "libs/libs.h"
#include "loader/symbolDatabase.h"

#include <atomic>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <map>
#include <string>
#include <vector>

namespace Tracker {
enum Kind { Any = 0, Malloc = 1, Calloc = 2, Realloc = 4 };

std::map<void*, std::size_t> g_blocks;
int  g_call_index = 0;   // allocation calls since the last Arm
int  g_fail_at    = 0;   // 1-based; 0 = never
int  g_fail_kinds = Any; // which calls count
bool g_injected   = false;
int  g_bad_frees  = 0;
int  g_moves      = 0;

bool ShouldFail(Kind kind) {
	if (g_fail_at == 0) return false;
	if (g_fail_kinds != Any && (g_fail_kinds & kind) == 0) return false;
	if (++g_call_index != g_fail_at) return false;
	g_fail_at  = 0;
	g_injected = true;
	return true;
}
void Arm(int fail_at, int kinds = Any) {
	g_call_index = 0;
	g_fail_at    = fail_at;
	g_fail_kinds = kinds;
	g_injected   = false;
}
void Disarm() { g_fail_at = 0; }
} // namespace Tracker

namespace std {
void* TrackedMalloc(size_t size) {
	if (Tracker::ShouldFail(Tracker::Malloc)) return nullptr;
	void* p = ::malloc(size);
	if (p != nullptr) Tracker::g_blocks[p] = size;
	return p;
}
void* TrackedCalloc(size_t count, size_t size) {
	if (Tracker::ShouldFail(Tracker::Calloc)) return nullptr;
	void* p = ::calloc(count, size);
	if (p != nullptr) Tracker::g_blocks[p] = count * size;
	return p;
}
void TrackedFree(void* p) {
	if (p == nullptr) return;
	const auto it = Tracker::g_blocks.find(p);
	if (it == Tracker::g_blocks.end()) {
		Tracker::g_bad_frees++;
		return;
	}
	::memset(p, 0xDD, it->second);
	Tracker::g_blocks.erase(it);
	::free(p);
}
// Always a new block: a realloc that happens to grow in place would hide the bug.
void* TrackedRealloc(void* p, size_t size) {
	if (Tracker::ShouldFail(Tracker::Realloc)) return nullptr;
	void* moved = ::malloc(size);
	if (moved == nullptr) return nullptr;
	Tracker::g_blocks[moved] = size;
	if (p != nullptr) {
		const size_t old = Tracker::g_blocks[p];
		::memcpy(moved, p, old < size ? old : size);
		TrackedFree(p);
		Tracker::g_moves++;
	}
	return moved;
}
} // namespace std

// Only the unit sees these names: every header it includes is already in.
#define malloc  TrackedMalloc
#define calloc  TrackedCalloc
#define realloc TrackedRealloc
#define free    TrackedFree
#include "libs/libNpCppWebApi.cpp"
#undef malloc
#undef calloc
#undef realloc
#undef free

namespace {

using namespace Libs::NpCppWebApi;

int g_failed = 0;
void Check(bool v, const char* what) {
	if (v) return;
	std::fprintf(stderr, "NpAliasTests: FAILED: %s\n", what);
	g_failed++;
}

// The title's entry points, through the types it calls them with.
auto* const StringCtor   = &_ZN3sce2Np9CppWebApi6Common6StringC1EPNS2_10LibContextE;
auto* const StringDtor   = &_ZN3sce2Np9CppWebApi6Common6StringD1Ev;
auto* const StringAppend = &_ZN3sce2Np9CppWebApi6Common6String6appendEPKc;
auto* const SVectorCtor  = &_ZN3sce2Np9CppWebApi6Common6VectorINS2_6StringEEC1EPNS2_10LibContextE;
auto* const SVectorDtor  = &_ZN3sce2Np9CppWebApi6Common6VectorINS2_6StringEED1Ev;
auto* const SVectorPush  = &_ZN3sce2Np9CppWebApi6Common6VectorINS2_6StringEE8pushBackERKS4_;
auto* const IVectorCtor  = &_ZN3sce2Np9CppWebApi6Common6VectorINS2_12IntrusivePtrINS1_14SessionManager2V132RequestCreatePlayerSessionPlayerEEEEC1EPNS2_10LibContextE;
auto* const IVectorDtor  = &_ZN3sce2Np9CppWebApi6Common6VectorINS2_12IntrusivePtrINS1_14SessionManager2V132RequestCreatePlayerSessionPlayerEEEED1Ev;
auto* const IVectorPush  = &_ZN3sce2Np9CppWebApi6Common6VectorINS2_12IntrusivePtrINS1_14SessionManager2V132RequestCreatePlayerSessionPlayerEEEE8pushBackERKS8_;
using IPush = int (KYTY_SYSV_ABI*)(IntrusivePtr*, const void*);
const IPush g_i_pushes[] = {
    IVectorPush,
    &_ZN3sce2Np9CppWebApi6Common6VectorINS2_12IntrusivePtrINS1_14SessionManager2V120RequestPlayerSessionEEEE8pushBackERKS8_,
    &_ZN3sce2Np9CppWebApi6Common6VectorINS2_12IntrusivePtrINS1_14SessionManager2V124PlayerSessionPushContextEEEE8pushBackERKS8_,
    &_ZN3sce2Np9CppWebApi6Common6VectorINS2_12IntrusivePtrINS1_14SessionManager2V126RequestPlayerSessionPlayerEEEE8pushBackERKS8_,
};

std::string Pattern(std::size_t length, unsigned seed = 0) {
	std::string text(length, 'a');
	for (std::size_t i = 0; i < length; i++) text[i] = static_cast<char>('a' + (i * 7 + seed) % 26);
	return text;
}

struct Str {
	CommonString s {};
	Str() { StringCtor(&s, nullptr); }
	explicit Str(const std::string& text) {
		StringCtor(&s, nullptr);
		Check(StringAppend(&s, text.c_str()) == 0, "seed append");
	}
	~Str() { StringDtor(&s); }
	Str(const Str&)            = delete;
	Str& operator=(const Str&) = delete;
	[[nodiscard]] std::string Text() const { return s.buffer != nullptr ? std::string(s.buffer) : std::string(); }
};

// One self-append and what it must leave.
void SelfAppend(Str& value, std::size_t offset, const char* what) {
	const std::string before   = value.Text();
	const std::string expected = before + before.substr(offset);
	Check(StringAppend(&value.s, value.s.buffer + offset) == 0, what);
	Check(value.Text() == expected, what);
	Check(value.s.bufferSize >= expected.size() + 1, "capacity holds the text");
}

// ---- Common::String::append ----

void string_repro_40_39() {
	Str value(std::string(40, 'a'));
	Check(value.s.bufferSize == 64, "40 characters take a 64-byte buffer");
	SelfAppend(value, 1, "append(buffer + 1) grows");
	Check(value.s.bufferSize == 128 && value.Text().size() == 79, "64 -> 128, length 79");
}
void string_self_offset0_growth() {
	Str value(Pattern(20));
	const auto capacity = value.s.bufferSize;
	SelfAppend(value, 0, "append(buffer) grows");
	Check(value.s.bufferSize > capacity, "the buffer did grow");
}
void string_self_offset0_no_growth() {
	// widen the capacity without changing the text: grow, then cut with a terminator
	Str value(Pattern(15));
	Check(StringAppend(&value.s, "x") == 0, "grow");
	value.s.buffer[15] = '\0';
	Check(value.s.bufferSize == 32, "32 bytes for 15 characters");
	const auto* buffer = value.s.buffer;
	SelfAppend(value, 0, "append(buffer): source and target share the terminator's byte");
	Check(value.s.buffer == buffer, "no reallocation");
}
void string_substring_no_growth() {
	for (std::size_t offset: {3u, 9u, 15u}) {
		Str value(Pattern(16));
		Check(value.s.bufferSize == 32, "16 characters take 32 bytes");
		const auto* buffer = value.s.buffer;
		SelfAppend(value, offset, "a substring, no growth");
		Check(value.s.buffer == buffer, "no reallocation");
		Check(value.Text().substr(0, 16) == Pattern(16), "the prefix is intact");
	}
}
void string_substring_growth() {
	for (std::size_t offset: {1u, 5u, 15u}) {
		Str value(Pattern(31)); // 32 bytes, full
		const auto capacity = value.s.bufferSize;
		SelfAppend(value, offset, "a substring with growth");
		Check(value.s.bufferSize > capacity, "the buffer did grow");
	}
}
void string_empty_own_terminator() {
	Str value(Pattern(10));
	const auto* buffer   = value.s.buffer;
	const auto  capacity = value.s.bufferSize;
	const auto  text     = value.Text();
	Check(StringAppend(&value.s, value.s.buffer + 10) == 0, "append(own terminator)");
	Check(value.s.buffer == buffer && value.s.bufferSize == capacity && value.Text() == text, "nothing changes");
}
void string_empty_external() {
	Str value;
	Check(StringAppend(&value.s, "") == 0 && value.s.buffer != nullptr && value.Text().empty(), "empty into an empty string");
	Check(StringAppend(&value.s, nullptr) == 0, "a null text is ignored");
	Check(value.Text().empty(), "still empty");
}
void string_exact_fit() {
	Str value(Pattern(16));
	const auto capacity = value.s.bufferSize;
	SelfAppend(value, 1, "16 + 15 + 1 == 32: fits exactly");
	Check(value.s.bufferSize == capacity && capacity == 32, "no growth at the exact fit");
	SelfAppend(value, 30, "31 + 1 + 1 == 33: one byte past");
	Check(value.s.bufferSize == 64, "growth one byte past the fit");
}
void string_repeated_growth() {
	Str value(Pattern(9));
	int growths = 0;
	for (int i = 0; i < 12; i++) {
		const auto capacity = value.s.bufferSize;
		SelfAppend(value, i == 0 ? 0 : 1, "repeated self-append");
		if (value.s.bufferSize > capacity) growths++;
	}
	Check(growths >= 8, "several real growths");
}
void string_length_offset_sweep() {
	for (std::size_t length = 1; length <= 130; length++) {
		for (std::size_t offset = 0; offset <= length; offset++) {
			Str value(Pattern(length, static_cast<unsigned>(offset)));
			SelfAppend(value, offset, "length and offset sweep");
		}
	}
}
void string_external_appends() {
	Str value;
	std::string model;
	for (int i = 0; i < 40; i++) {
		const auto text = Pattern(static_cast<std::size_t>(i), 3);
		Check(StringAppend(&value.s, text.c_str()) == 0, "external append");
		model += text;
		Check(value.Text() == model, "external append content");
	}
}
void string_oom_self_growth() {
	Str value(Pattern(31)); // 32 bytes, full
	const auto* buffer   = value.s.buffer;
	const auto  capacity = value.s.bufferSize;
	const auto  text     = value.Text();
	Tracker::Arm(1);
	Check(StringAppend(&value.s, value.s.buffer + 1) == -1, "a failed allocation returns -1");
	Tracker::Disarm();
	Check(value.s.buffer == buffer && value.s.bufferSize == capacity && value.Text() == text, "the string is unchanged");
	SelfAppend(value, 1, "the same append succeeds afterwards");
}

// ---- Vector<IntrusivePtr<T>>::pushBack ----

struct FakeObject {
	std::int32_t  refcount; // at offset 0, as the console's objects
	std::int32_t  pad;
	std::uint64_t id;
};
std::map<std::uint64_t, int> g_deletions;
std::uint64_t                g_next_id = 1;

void KYTY_SYSV_ABI CountingDeleter(void* object) {
	auto* fake = static_cast<FakeObject*>(object);
	g_deletions[fake->id]++;
	delete fake;
}

// An owner outside the vector: the title's own IntrusivePtr to a new object.
IntrusivePtr NewOwner() {
	auto* object            = new FakeObject {1, 0, g_next_id++};
	g_deletions[object->id] = 0;
	return IntrusivePtr {object, &CountingDeleter, nullptr};
}
FakeObject* Fake(const IntrusivePtr& p) { return static_cast<FakeObject*>(p.object); }
void ReleaseOwner(IntrusivePtr& owner) { ReleaseIntrusivePtr(&owner, ReferenceCountOffset, __func__); }

struct IVec {
	IntrusivePtr v {};
	IVec() { IVectorCtor(&v, nullptr); }
	~IVec() {
		if (v.object != nullptr) IVectorDtor(&v);
	}
	IVec(const IVec&)            = delete;
	IVec& operator=(const IVec&) = delete;
	[[nodiscard]] VectorBody*   Body() const { return static_cast<VectorBody*>(v.object); }
	[[nodiscard]] IntrusivePtr* Elements() const { return static_cast<IntrusivePtr*>(Body()->elements); }
};

void CheckIVecAfterSelfPush(const IVec& vec, const std::vector<IntrusivePtr>& owners, std::size_t index, std::size_t size_before) {
	Check(vec.Body()->size == size_before + 1, "one more element");
	for (std::size_t i = 0; i < size_before; i++) {
		Check(vec.Elements()[i].object == owners[i].object && vec.Elements()[i].deleter == &CountingDeleter, "old elements survive the move");
	}
	Check(vec.Elements()[size_before].object == owners[index].object, "the new element is the aliased one");
	Check(vec.Elements()[size_before].deleter == &CountingDeleter, "the new element keeps the deleter");
	for (std::size_t i = 0; i < owners.size(); i++) {
		Check(Fake(owners[i])->refcount == (i == index ? 3 : 2), "exact reference counts");
	}
}

void ivec_self_growth_each_index() {
	for (std::size_t index = 0; index < 4; index++) {
		std::vector<IntrusivePtr> owners;
		{
			IVec vec;
			for (int i = 0; i < 4; i++) {
				owners.push_back(NewOwner());
				Check(IVectorPush(&vec.v, &owners.back()) == 0, "seed push");
			}
			Check(vec.Body()->capacity == 4, "the storage is full");
			const auto* before = vec.Elements();
			const int   moves  = Tracker::g_moves;
			Check(IVectorPush(&vec.v, &vec.Elements()[index]) == 0, "push of an own element with growth");
			Check(vec.Elements() != before && Tracker::g_moves == moves + 1, "the storage really moved");
			CheckIVecAfterSelfPush(vec, owners, index, 4);
		}
		for (auto& owner: owners) {
			Check(Fake(owner)->refcount == 1, "the vector gave back every reference");
			const auto id = Fake(owner)->id;
			ReleaseOwner(owner);
			Check(g_deletions[id] == 1, "one deleter call after the last owner");
		}
	}
}
void ivec_self_no_growth() {
	std::vector<IntrusivePtr> owners;
	{
		IVec vec;
		for (int i = 0; i < 2; i++) {
			owners.push_back(NewOwner());
			Check(IVectorPush(&vec.v, &owners.back()) == 0, "seed push");
		}
		const auto* before = vec.Elements();
		Check(IVectorPush(&vec.v, &vec.Elements()[1]) == 0, "push of an own element, no growth");
		Check(vec.Elements() == before, "no move");
		CheckIVecAfterSelfPush(vec, owners, 1, 2);
	}
	for (auto& owner: owners) ReleaseOwner(owner);
}
void ivec_self_null_element_growth() {
	IVec vec;
	const IntrusivePtr empty {};
	for (int i = 0; i < 4; i++) Check(IVectorPush(&vec.v, &empty) == 0, "seed push of a null pointer");
	Check(IVectorPush(&vec.v, &vec.Elements()[2]) == 0, "push of an own null element with growth");
	Check(vec.Body()->size == 5 && vec.Elements()[4].object == nullptr, "the null element is copied");
}
void ivec_repeated_growth() {
	auto owner    = NewOwner();
	const auto id = Fake(owner)->id;
	{
		IVec vec;
		Check(IVectorPush(&vec.v, &owner) == 0, "seed push");
		ReleaseOwner(owner); // the vector is now the last owner
		Check(g_deletions[id] == 0, "the vector keeps the object alive");
		for (int i = 1; i < 100; i++) {
			Check(IVectorPush(&vec.v, &vec.Elements()[static_cast<std::size_t>(i) / 2]) == 0, "repeated self-push");
			Check(vec.Elements()[i].object == vec.Elements()[0].object, "the new element");
			Check(Fake(vec.Elements()[0])->refcount == i + 1, "exact count while growing");
		}
		Check(vec.Body()->capacity == 128 && vec.Body()->size == 100, "several growths");
	}
	Check(g_deletions[id] == 1, "one deleter call after the last owner");
}
void ivec_all_instantiations() {
	for (const auto push: g_i_pushes) {
		auto owner = NewOwner();
		{
			IVec vec;
			for (int i = 0; i < 4; i++) Check(push(&vec.v, &owner) == 0, "seed push");
			Check(push(&vec.v, &vec.Elements()[3]) == 0, "push of an own element with growth");
			Check(Fake(owner)->refcount == 6, "exact count");
		}
		Check(Fake(owner)->refcount == 1, "all given back");
		ReleaseOwner(owner);
	}
}
void ivec_oom_grow_self() {
	std::vector<IntrusivePtr> owners;
	{
		IVec vec;
		for (int i = 0; i < 4; i++) {
			owners.push_back(NewOwner());
			Check(IVectorPush(&vec.v, &owners.back()) == 0, "seed push");
		}
		const auto* before = vec.Elements();
		Tracker::Arm(1, Tracker::Realloc);
		Check(IVectorPush(&vec.v, &vec.Elements()[1]) == -1, "a failed growth returns -1");
		Tracker::Disarm();
		Check(vec.Elements() == before && vec.Body()->size == 4 && vec.Body()->capacity == 4, "the storage is unchanged");
		for (std::size_t i = 0; i < 4; i++) {
			Check(Fake(owners[i])->refcount == 2 && vec.Elements()[i].object == owners[i].object, "no reference taken");
		}
		Check(IVectorPush(&vec.v, &vec.Elements()[1]) == 0, "the retry succeeds");
		CheckIVecAfterSelfPush(vec, owners, 1, 4);
	}
	for (auto& owner: owners) ReleaseOwner(owner);
}
void ivec_oom_first_body() {
	auto owner = NewOwner();
	{
		IVec vec;
		Tracker::Arm(1, Tracker::Calloc);
		Check(IVectorPush(&vec.v, &owner) == -1, "no body: -1");
		Tracker::Disarm();
		Check(vec.v.object == nullptr && Fake(owner)->refcount == 1, "nothing changed");
	}
	ReleaseOwner(owner);
}
void ivec_oom_first_storage() {
	auto owner = NewOwner();
	{
		IVec vec;
		Tracker::Arm(1, Tracker::Realloc);
		Check(IVectorPush(&vec.v, &owner) == -1, "no storage: -1");
		Tracker::Disarm();
		Check(Fake(owner)->refcount == 1 && vec.Body()->size == 0, "no reference taken");
	}
	ReleaseOwner(owner);
}
void ivec_fault_sweep() {
	for (int fail_at = 1;; fail_at++) {
		std::vector<IntrusivePtr> owners;
		owners.reserve(3);
		bool injected = false;
		{
			IVec vec;
			Tracker::Arm(fail_at);
			for (std::size_t i = 0; i < 12; i++) {
				if (i < 3) owners.push_back(NewOwner());
				const IntrusivePtr* source      = i < 3 ? &owners[i] : &vec.Elements()[i % 3];
				const std::uint64_t size_before = vec.v.object != nullptr ? vec.Body()->size : 0;
				if (IVectorPush(&vec.v, source) != 0) {
					Check(Tracker::g_injected, "a failure only from the injection");
					Check((vec.v.object != nullptr ? vec.Body()->size : 0) == size_before, "a failed push adds nothing");
					Tracker::Disarm();
					source = i < 3 ? &owners[i] : &vec.Elements()[i % 3];
					Check(IVectorPush(&vec.v, source) == 0, "the retry succeeds");
				}
			}
			injected = Tracker::g_injected;
			Tracker::Disarm();
			Check(vec.Body()->size == 12, "twelve elements");
			for (const auto& owner: owners) Check(Fake(owner)->refcount == 5, "the owner and four elements each");
		}
		for (auto& owner: owners) {
			const auto id = Fake(owner)->id;
			Check(Fake(owner)->refcount == 1, "all references given back");
			ReleaseOwner(owner);
			Check(g_deletions[id] == 1, "one deleter call");
		}
		if (!injected) {
			Check(fail_at > 3, "the sweep reached the allocations");
			return;
		}
	}
}

// ---- Vector<String>::pushBack ----

struct SVec {
	IntrusivePtr v {};
	SVec() { SVectorCtor(&v, nullptr); }
	~SVec() {
		if (v.object != nullptr) SVectorDtor(&v);
	}
	SVec(const SVec&)            = delete;
	SVec& operator=(const SVec&) = delete;
	[[nodiscard]] VectorBody*   Body() const { return static_cast<VectorBody*>(v.object); }
	[[nodiscard]] CommonString* Elements() const { return static_cast<CommonString*>(Body()->elements); }
	[[nodiscard]] std::string   Text(std::size_t i) const {
		return Elements()[i].buffer != nullptr ? std::string(Elements()[i].buffer) : std::string("<null>");
	}
};

void CheckSVec(const SVec& vec, const std::vector<std::string>& model) {
	Check(vec.Body()->size == model.size(), "the expected size");
	for (std::size_t i = 0; i < model.size() && i < vec.Body()->size; i++) Check(vec.Text(i) == model[i], "element text");
}

void svec_self_growth_each_index() {
	for (std::size_t index = 0; index < 4; index++) {
		SVec vec;
		std::vector<std::string> model;
		for (int i = 0; i < 4; i++) {
			model.push_back(Pattern(static_cast<std::size_t>(5 + i * 9), static_cast<unsigned>(i)));
			Str s(model.back());
			Check(SVectorPush(&vec.v, &s.s) == 0, "seed push");
		}
		Check(vec.Body()->capacity == 4, "the storage is full");
		const auto* before = vec.Elements();
		Check(SVectorPush(&vec.v, &vec.Elements()[index]) == 0, "push of an own element with growth");
		model.push_back(model[index]);
		Check(vec.Elements() != before, "the storage really moved");
		CheckSVec(vec, model);
		Check(vec.Elements()[4].buffer != vec.Elements()[index].buffer, "a deep copy");
		Check(vec.Elements()[4].bufferSize == model[index].size() + 1, "the copy's size");
	}
}
void svec_self_no_growth() {
	SVec vec;
	std::vector<std::string> model {"first", "second"};
	for (const auto& text: model) {
		Str s(text);
		Check(SVectorPush(&vec.v, &s.s) == 0, "seed push");
	}
	const auto* before = vec.Elements();
	Check(SVectorPush(&vec.v, &vec.Elements()[0]) == 0, "push of an own element, no growth");
	model.push_back("first");
	Check(vec.Elements() == before, "no move");
	CheckSVec(vec, model);
}
void svec_self_null_buffer_growth() {
	SVec vec;
	Str empty;
	for (int i = 0; i < 4; i++) Check(SVectorPush(&vec.v, &empty.s) == 0, "seed push of a string without a buffer");
	Check(SVectorPush(&vec.v, &vec.Elements()[1]) == 0, "push of an own empty element with growth");
	Check(vec.Body()->size == 5 && vec.Elements()[4].buffer == nullptr && vec.Elements()[4].bufferSize == 0, "stays without a buffer");
}
void svec_repeated_growth() {
	SVec vec;
	std::vector<std::string> model {Pattern(33)};
	{
		Str s(model[0]);
		Check(SVectorPush(&vec.v, &s.s) == 0, "seed push");
	}
	for (std::size_t i = 1; i < 100; i++) {
		Check(SVectorPush(&vec.v, &vec.Elements()[i / 2]) == 0, "repeated self-push");
		model.push_back(model[i / 2]);
	}
	Check(vec.Body()->capacity == 128, "several growths");
	CheckSVec(vec, model);
}
void svec_copies_are_independent() {
	SVec vec;
	Str source(Pattern(20));
	source.s.libContext = reinterpret_cast<void*>(0x1234);
	Check(SVectorPush(&vec.v, &source.s) == 0, "push");
	source.s.buffer[0] = '!';
	Check(vec.Text(0) == Pattern(20), "the source changes alone");
	vec.Elements()[0].buffer[1] = '?';
	Check(source.Text()[1] == Pattern(20)[1], "the element changes alone");
	Check(vec.Elements()[0].referenceCount == 0 && vec.Elements()[0].libContext == reinterpret_cast<void*>(0x1234), "the copy's other fields");
}
void SeedFourStrings(SVec& vec, std::vector<std::string>& model) {
	for (int i = 0; i < 4; i++) {
		model.push_back(Pattern(10, static_cast<unsigned>(i)));
		Str s(model.back());
		Check(SVectorPush(&vec.v, &s.s) == 0, "seed push");
	}
}
void svec_oom_copy() {
	SVec vec;
	std::vector<std::string> model;
	SeedFourStrings(vec, model);
	const auto* before = vec.Elements();
	Tracker::Arm(1, Tracker::Malloc);
	Check(SVectorPush(&vec.v, &vec.Elements()[2]) == -1, "a failed copy returns -1");
	Tracker::Disarm();
	Check(vec.Elements() == before && vec.Body()->capacity == 4, "the storage is unchanged");
	CheckSVec(vec, model);
}
void svec_oom_grow() {
	SVec vec;
	std::vector<std::string> model;
	SeedFourStrings(vec, model);
	const auto* before = vec.Elements();
	const auto  blocks = Tracker::g_blocks.size();
	Tracker::Arm(1, Tracker::Realloc);
	Check(SVectorPush(&vec.v, &vec.Elements()[2]) == -1, "a failed growth returns -1");
	Tracker::Disarm();
	Check(Tracker::g_blocks.size() == blocks, "the copy is freed");
	Check(vec.Elements() == before && vec.Body()->capacity == 4, "the storage is unchanged");
	CheckSVec(vec, model);
	Check(SVectorPush(&vec.v, &vec.Elements()[2]) == 0, "the retry succeeds");
	model.push_back(model[2]);
	CheckSVec(vec, model);
}
void svec_fault_sweep() {
	for (int fail_at = 1;; fail_at++) {
		bool injected = false;
		{
			SVec vec;
			std::vector<std::string> model;
			Str seed(Pattern(25));
			Tracker::Arm(fail_at);
			for (std::size_t i = 0; i < 12; i++) {
				const CommonString* source = i < 3 ? &seed.s : &vec.Elements()[i % 3];
				const std::string   text   = i < 3 ? Pattern(25) : vec.Text(i % 3);
				const std::size_t   before = model.size();
				if (SVectorPush(&vec.v, source) != 0) {
					Check(Tracker::g_injected, "a failure only from the injection");
					Check((vec.v.object != nullptr ? vec.Body()->size : 0) == before, "a failed push adds nothing");
					Tracker::Disarm();
					source = i < 3 ? &seed.s : &vec.Elements()[i % 3];
					Check(SVectorPush(&vec.v, source) == 0, "the retry succeeds");
				}
				model.push_back(text);
			}
			injected = Tracker::g_injected;
			Tracker::Disarm();
			CheckSVec(vec, model);
		}
		if (!injected) {
			Check(fail_at > 3, "the sweep reached the allocations");
			return;
		}
	}
}

// ---- layout: the structures the title reads and the fix must not touch ----

void layout() {
	static_assert(sizeof(IntrusivePtr) == 0x18 && offsetof(IntrusivePtr, deleter) == 0x08 && offsetof(IntrusivePtr, libContext) == 0x10);
	static_assert(sizeof(CommonString) == 0x20 && offsetof(CommonString, referenceCount) == 0x00 && offsetof(CommonString, buffer) == 0x08);
	static_assert(offsetof(CommonString, bufferSize) == 0x10 && offsetof(CommonString, libContext) == 0x18);
	static_assert(sizeof(VectorBody) == 0x50 && offsetof(VectorBody, referenceCount) == 0x30 && offsetof(VectorBody, elementKind) == 0x34);
	static_assert(offsetof(VectorBody, elements) == 0x38 && offsetof(VectorBody, size) == 0x40 && offsetof(VectorBody, capacity) == 0x48);
	Check(ReferenceCountOffset == 0 && VectorReferenceCountOffset == 0x30, "the reference count offsets");
}

struct Case {
	const char* name;
	void (*run)();
};
#define CASE(n) {#n, n}
const Case g_cases[] = {
    CASE(string_repro_40_39), CASE(string_self_offset0_growth), CASE(string_self_offset0_no_growth),
    CASE(string_substring_no_growth), CASE(string_substring_growth), CASE(string_empty_own_terminator),
    CASE(string_empty_external), CASE(string_exact_fit), CASE(string_repeated_growth),
    CASE(string_length_offset_sweep), CASE(string_external_appends), CASE(string_oom_self_growth),
    CASE(ivec_self_growth_each_index), CASE(ivec_self_no_growth), CASE(ivec_self_null_element_growth),
    CASE(ivec_repeated_growth), CASE(ivec_all_instantiations), CASE(ivec_oom_grow_self), CASE(ivec_oom_first_body),
    CASE(ivec_oom_first_storage), CASE(ivec_fault_sweep),
    CASE(svec_self_growth_each_index), CASE(svec_self_no_growth), CASE(svec_self_null_buffer_growth),
    CASE(svec_repeated_growth), CASE(svec_copies_are_independent), CASE(svec_oom_copy), CASE(svec_oom_grow),
    CASE(svec_fault_sweep), CASE(layout),
};

void RunCase(const Case& c) {
	const int  failed_before = g_failed;
	const int  bad_frees     = Tracker::g_bad_frees;
	const auto blocks        = Tracker::g_blocks.size();
	c.run();
	Check(Tracker::g_blocks.size() == blocks, "no block left behind");
	Check(Tracker::g_bad_frees == bad_frees, "no double or foreign free");
	for (const auto& [id, count]: g_deletions) Check(count <= 1, "no object deleted twice");
	std::fprintf(stderr, "NpAliasTests: %s: %s\n", g_failed == failed_before ? "ok" : "FAILED", c.name);
}

} // namespace

int main(int argc, char** argv) {
	if (argc != 2) {
		std::fprintf(stderr, "usage: NpAliasTests list|all|<case>\n");
		return 2;
	}
	const std::string what = argv[1];
	if (what == "list") {
		for (const auto& c: g_cases) std::printf("%s\n", c.name);
		return 0;
	}
	int run = 0;
	for (const auto& c: g_cases) {
		if (what != "all" && what != c.name) continue;
		RunCase(c);
		run++;
	}
	if (run == 0) {
		std::fprintf(stderr, "NpAliasTests: no such case: %s\n", what.c_str());
		return 2;
	}
	if (g_failed != 0) {
		std::fprintf(stderr, "NpAliasTests: %d check(s) FAILED\n", g_failed);
		return 1;
	}
	std::fprintf(stderr, "NpAliasTests: all checks passed (%d cases)\n", run);
	return 0;
}
