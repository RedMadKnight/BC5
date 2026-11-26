// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0405 (series e5 of experiment 0401), tag "lib": the CPU test of mklib0405.py's edits of src/libs/libJson2.cpp,
// libUlt.cpp, libUserService.cpp and libSystemService.cpp (notes lib0405-notes.md), behind five switches:
//   KYTY_BC5_JSON2_FIXES (value,string,array,object), KYTY_BC5_ULT_FIXES (join,queue),
//   KYTY_BC5_USERSERVICE_VALUES (age,login,name,zoom), KYTY_BC5_SYSTEMSERVICE_VALUES (int,table,string),
//   KYTY_BC5_SYSTEMSERVICE_PARAMS_7_1000.
// No game, no GPU, no window, no sound device, no network. The test registers the host's libraries into its own
// SymbolDatabase (Libs::InitAll, as amm0401.cpp does), takes the functions by NID and calls them as a title would. The
// subsystems a guest thread needs (Ult's ulthreads are LibKernel::PthreadCreate threads: Memory gives the guest stack, the
// RuntimeLinker drops its TLS at the end) are started as sav0401.cpp starts them.
// Freed memory: while the Json2 cases run, this program's operator delete fills each freed block with 0xA5 and keeps it
// (a quarantine of 16384 blocks) instead of freeing it, so a read of freed memory gets the canary (a type 0xA5A5A5A5, a
// pointer 0xA5A5... that faults) instead of whatever the allocator left there: an ASan-like check without ASan.
// Cases (one line each; lib0405-notes.md has the reasons):
//   json2  the items' alias cases (v = v["a"], set(own String / its c_str / a member's String), set(own Array / a
//          member's Array), set(own Object / a member's Object), obj = a member's object): with the item on, the
//          fixed result; with it off they are not run in this process (today they read freed memory), but once each in a
//          child process (fork), and what the child did is printed as an info line, not counted.
//          Both ways: v["a"] = v (today a wrong result, no freed read), obj = obj (today empties obj), independent
//          sources, dst == src, a parse into a value that owns a payload, the members' parent pointers.
//   ult    sequential join then a second join (STATE), an unknown runtime, a handle created twice, a self-join (STATE
//          both ways: today glibc's EDEADLK), the queue push past num_data (on: kept; off: dropped as today). With "join"
//          on only: two joiners of one ulthread (one gets the status, the other STATE) and 100 creates each joined at
//          once from another thread (today's double PthreadJoin and unclaimed join are undefined, so not run off).
//   user   age level, the login-before-null order in GetAgeLevel and the six accessibility getters, ZoomFollowFocus,
//          GetUserName: the returns and the cases that today EXIT (those off: in a child, info only).
//   system ParamGetInt over parameters 0..6, 7, 8, 99..112, 199..214, 299..301, 399..401, 999..1001, 2048 and a null
//          pointer (the value written or left as it was); ParamGetString 6 with 64 and 65 bytes, a null buffer, and the
//          unknown parameters (off: today's EXIT, in a child, info only).
// Build (build0401.py, series e5): --gate lib0405.cpp <out> --like src/libs/libJson2.cpp, with the four private units
// (src/libs/libJson2.cpp=<it> ... from mklib0405.py) in place of the shared ones, linked with every emulator object but
// main.cpp.o.
// usage: run in a fresh directory on the NVMe, with the five switches set alike:
//   all five =1 -> "lib0405 on";  all five =0, or all unset -> "lib0405 off". Item lists ("value,object") are allowed: the
//   cases of each item then expect its own state, and the last line says "mixed". The argument may be left out.
// Prints "lib0405: on|off|mixed N of N; end" and exits 0 only then. A watchdog ends a hang after 150 s with a FAIL line.

#include "common/abi.h"
#include "common/commonSubsystem.h"
#include "common/emulatorConfig.h"
#include "common/logging/log.h"
#include "common/singleton.h"
#include "common/subsystems.h"
#include "common/threads.h"
#include "kernel/memory.h"
#include "kernel/pthread.h"
#include "libs/errno.h"
#include "libs/libs.h"
#include "loader/runtimeLinker.h"
#include "loader/symbolDatabase.h"
#include "loader/timer.h"

#include <atomic>
#include <chrono>
#include <cinttypes>
#include <csignal>
#include <cstdarg>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <functional>
#include <initializer_list>
#include <new>
#include <string>
#include <thread>
#include <vector>

#include <fcntl.h>
#include <malloc.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>

// ---- freed memory: poisoned and quarantined while g_poison is set ----------------------------------------------------
namespace lib0405_alloc {
std::atomic<bool> g_poison {false};
std::atomic_flag  g_lock; // clear (C++20)
constexpr size_t  kQuarantine = 16384;
void*             g_held[kQuarantine];
size_t            g_next = 0;

void PoisonAndHold(void* p) {
	std::memset(p, 0xA5, malloc_usable_size(p));
	while (g_lock.test_and_set(std::memory_order_acquire)) {
	}
	void* old       = g_held[g_next];
	g_held[g_next]  = p;
	g_next          = (g_next + 1) % kQuarantine;
	g_lock.clear(std::memory_order_release);
	std::free(old);
}
} // namespace lib0405_alloc

// The replaceable deallocation functions (the default operator new allocates with malloc).
void operator delete(void* p) noexcept {
	if (p == nullptr) {
		return;
	}
	if (lib0405_alloc::g_poison.load(std::memory_order_relaxed)) {
		lib0405_alloc::PoisonAndHold(p);
		return;
	}
	std::free(p);
}

void operator delete(void* p, std::size_t /*size*/) noexcept {
	operator delete(p);
}

namespace lib0405 {

using Clock = std::chrono::steady_clock;

constexpr int kWatchdogSeconds = 150;
constexpr int kChildSeconds    = 5;

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

void Report(const char* name, bool ok, const std::string& info) {
	g_cases++;
	if (ok) {
		g_passed++;
	}
	std::printf("lib0405: case %d %s: %s (%s)\n", g_cases.load(), name, ok ? "ok" : "FAIL", info.c_str());
	std::fflush(stdout);
}

void Info(const char* name, const std::string& info) {
	std::printf("lib0405: info %s: %s\n", name, info.c_str());
	std::fflush(stdout);
}

[[noreturn]] void SetupFail(const std::string& what) {
	std::printf("lib0405: FAIL setup: %s\n", what.c_str());
	std::fflush(stdout);
	std::_Exit(2);
}

void Watchdog() {
	std::this_thread::sleep_for(std::chrono::seconds(kWatchdogSeconds));
	std::printf("lib0405: FAIL watchdog: case \"%s\" still running after %d s (a hang); %d of %d cases passed before it\n",
	            g_case.load(), kWatchdogSeconds, g_passed.load(), g_cases.load());
	std::fflush(stdout);
	std::_Exit(3);
}

// Runs f in a child process (fork) with its stdout and stderr on /dev/null, and says what the child did: returned
// (f's answer: true "the fixed result", false "another result"), died of a signal, ended the process itself (the host's
// EXIT path), or hung (killed after kChildSeconds).
std::string InChild(const std::function<bool()>& f) {
	int fds[2];
	if (pipe(fds) != 0) {
		return "no pipe";
	}
	std::fflush(stdout);
	std::fflush(stderr);
	const pid_t pid = fork();
	if (pid < 0) {
		close(fds[0]);
		close(fds[1]);
		return "no fork";
	}
	if (pid == 0) {
		close(fds[0]);
		const int devnull = open("/dev/null", O_WRONLY);
		if (devnull >= 0) {
			dup2(devnull, 1);
			dup2(devnull, 2);
		}
		const char c = f() ? 'Y' : 'N';
		if (write(fds[1], &c, 1) != 1) {
			_exit(1);
		}
		_exit(0);
	}
	close(fds[1]);
	int        status = 0;
	bool       killed = false;
	const auto t0     = Clock::now();
	for (;;) {
		const pid_t r = waitpid(pid, &status, WNOHANG);
		if (r == pid || r < 0) {
			break;
		}
		if (Clock::now() - t0 > std::chrono::seconds(kChildSeconds)) {
			kill(pid, SIGKILL);
			waitpid(pid, &status, 0);
			killed = true;
			break;
		}
		std::this_thread::sleep_for(std::chrono::milliseconds(5));
	}
	char          c = 0;
	const ssize_t n = read(fds[0], &c, 1);
	close(fds[0]);
	if (n == 1) {
		return c == 'Y' ? "the child returned the fixed result" : "the child returned another result";
	}
	if (killed) {
		return Fmt("the child hung (killed after %d s)", kChildSeconds);
	}
	if (WIFSIGNALED(status)) {
		return Fmt("the child died of signal %d", WTERMSIG(status));
	}
	if (WIFEXITED(status)) {
		return Fmt("the child ended the process, exit code %d (the host's EXIT path)", WEXITSTATUS(status));
	}
	return "the child: unknown status";
}

// ---- the switches, read as the units read them ----------------------------------------------------------------------
uint32_t Items(const char* name, std::initializer_list<const char*> names) {
	const char* e = std::getenv(name);
	if (e == nullptr || e[0] == '\0' || std::strcmp(e, "0") == 0) {
		return 0;
	}
	uint32_t    parts = 0;
	const char* p     = e;
	for (;;) {
		const char*  comma = std::strchr(p, ',');
		const size_t n     = comma != nullptr ? static_cast<size_t>(comma - p) : std::strlen(p);
		uint32_t     bit   = 1;
		for (const char* item: names) {
			if (n == std::strlen(item) && std::strncmp(p, item, n) == 0) {
				parts |= bit;
			}
			bit <<= 1u;
		}
		if (comma == nullptr) {
			break;
		}
		p = comma + 1;
	}
	return parts != 0 ? parts : ((1u << names.size()) - 1u);
}

uint32_t g_json2  = 0; // value 1, string 2, array 4, object 8
uint32_t g_ult    = 0; // join 1, queue 2
uint32_t g_user   = 0; // age 1, login 2, name 4, zoom 8
uint32_t g_sys    = 0; // int 1, table 2, string 4
bool     g_p71000 = false;

// ---- function lookup ------------------------------------------------------------------------------------------------
Loader::SymbolDatabase* g_db = nullptr;

template <typename F>
F Fn(const char* nid, const char* name) {
	const auto* r = g_db->FindByNid(nid, Loader::SymbolType::Func);
	if (r == nullptr || r->vaddr == 0) {
		SetupFail(Fmt("%s (%s) is not registered", name, nid));
	}
	return reinterpret_cast<F>(r->vaddr);
}

// =====================================================================================================================
// Json2
// =====================================================================================================================
struct JValue { // libJson2.cpp's JsonValue, 32 bytes
	JValue*  parent;
	void*    rootparam;
	uint64_t payload;
	char     padding[4];
	uint32_t type;
};
static_assert(sizeof(JValue) == 32);

struct JString { // libJson2.cpp's JsonString
	void* impl;
};

struct Json2 {
	void*(KYTY_SYSV_ABI* ctor)(void*);
	void(KYTY_SYSV_ABI* dtor)(void*);
	int32_t(KYTY_SYSV_ABI* parse)(JValue*, const char*, size_t);
	const JValue*(KYTY_SYSV_ABI* index)(const JValue*, const char*);
	JValue*(KYTY_SYSV_ABI* assign)(JValue*, const JValue*);
	void(KYTY_SYSV_ABI* set_value)(JValue*, const JValue*);
	void(KYTY_SYSV_ABI* set_string)(JValue*, const JString*);
	void(KYTY_SYSV_ABI* set_cstring)(JValue*, const char*);
	void(KYTY_SYSV_ABI* set_array)(JValue*, const void*);
	void(KYTY_SYSV_ABI* set_object)(JValue*, const void*);
	void*(KYTY_SYSV_ABI* object_assign)(void*, const void*);
	const JString*(KYTY_SYSV_ABI* get_string)(const JValue*);
	const void*(KYTY_SYSV_ABI* get_array)(const JValue*);
	const void*(KYTY_SYSV_ABI* get_object)(const JValue*);
	void*(KYTY_SYSV_ABI* refer_object)(JValue*);
	const char*(KYTY_SYSV_ABI* cstr)(const JString*);
	JString*(KYTY_SYSV_ABI* string_ctor)(JString*);
	void(KYTY_SYSV_ABI* string_dtor)(JString*);
	int32_t(KYTY_SYSV_ABI* serialize)(JValue*, JString*);
};
Json2 J {};

void LoadJson2() {
	J.ctor          = Fn<decltype(J.ctor)>("qBMjqyBn3OM", "sce::Json::Value::Value()");
	J.dtor          = Fn<decltype(J.dtor)>("WTtYf+cNnXI", "sce::Json::Value::~Value()");
	J.parse         = Fn<decltype(J.parse)>("S5JxQnoGF3E", "sce::Json::Parser::parse");
	J.index         = Fn<decltype(J.index)>("HwDt5lD9Bfo", "sce::Json::Value::operator[](const char*)");
	J.assign        = Fn<decltype(J.assign)>("4zrm6VrgIAw", "sce::Json::Value::operator=");
	J.set_value     = Fn<decltype(J.set_value)>("XL8+BUqjB1w", "sce::Json::Value::set(const Value&)");
	J.set_string    = Fn<decltype(J.set_string)>("6l3Bv2gysNc", "sce::Json::Value::set(const String&)");
	J.set_cstring   = Fn<decltype(J.set_cstring)>("n6FC+l9DU70", "sce::Json::Value::set(const char*)");
	J.set_array     = Fn<decltype(J.set_array)>("195ad-jAsTU", "sce::Json::Value::set(const Array&)");
	J.set_object    = Fn<decltype(J.set_object)>("dFCphqnd+a4", "sce::Json::Value::set(const Object&)");
	J.object_assign = Fn<decltype(J.object_assign)>("urOpESTBZmo", "sce::Json::Object::operator=");
	J.get_string    = Fn<decltype(J.get_string)>("epJ6x2LV0kU", "sce::Json::Value::getString");
	J.get_array     = Fn<decltype(J.get_array)>("ONT8As5R1ug", "sce::Json::Value::getArray");
	J.get_object    = Fn<decltype(J.get_object)>("IlsmvBtMkak", "sce::Json::Value::getObject");
	J.refer_object  = Fn<decltype(J.refer_object)>("-NxEk7XLkDY", "sce::Json::Value::referObject");
	J.cstr          = Fn<decltype(J.cstr)>("L1KAkYWml-M", "sce::Json::String::c_str");
	J.string_ctor   = Fn<decltype(J.string_ctor)>("qSmqLXXCPas", "sce::Json::String::String()");
	J.string_dtor   = Fn<decltype(J.string_dtor)>("cG1VE2HMl6c", "sce::Json::String::~String()");
	J.serialize     = Fn<decltype(J.serialize)>("R7FDWtcN6f8", "sce::Json::Value::serialize");
}

// A value parsed from `text` (setup fails when the parser refuses it).
JValue* Parse(const char* text) {
	auto* v = new JValue {};
	J.ctor(v);
	if (J.parse(v, text, std::strlen(text)) != 0) {
		SetupFail(Fmt("Json2 parse of %s", text));
	}
	return v;
}

void Free(JValue* v) {
	J.dtor(v);
	delete v;
}

std::string Text(JValue* v) {
	JString s {};
	J.string_ctor(&s);
	J.serialize(v, &s);
	std::string out = J.cstr(&s);
	J.string_dtor(&s);
	return out;
}

JValue* Member(const JValue* v, const char* key) {
	return const_cast<JValue*>(J.index(v, key));
}

constexpr uint32_t kValue  = 1;
constexpr uint32_t kString = 2;
constexpr uint32_t kArray  = 4;
constexpr uint32_t kObject = 8;

const char* const kLong1 = "a string long enough to live on the heap, not in the object";
const char* const kLong2 = "inner text long enough to live on the heap too";

// An alias case: run() builds its value, does the call, and returns the value's text; `fixed` is the text the fix gives.
struct AliasCase {
	const char*                  name;
	uint32_t                     item;
	std::function<std::string()> run;
	std::string                  fixed;
};

std::vector<AliasCase> AliasCases() {
	std::vector<AliasCase> c;
	c.push_back({"json2 value: v = v[\"a\"]", kValue,
	             [] {
		             JValue* v = Parse(R"({"a":{"b":1},"c":2})");
		             J.assign(v, Member(v, "a"));
		             std::string t = Text(v);
		             Free(v);
		             return t;
	             },
	             R"({"b":1})"});
	c.push_back({"json2 value: v.set(v[\"a\"][\"b\"])", kValue,
	             [] {
		             JValue* v = Parse(R"({"a":{"b":[1,2]}})");
		             J.set_value(v, Member(Member(v, "a"), "b"));
		             std::string t = Text(v);
		             Free(v);
		             return t;
	             },
	             "[1,2]"});
	c.push_back({"json2 string: v.set(v.getString())", kString,
	             [] {
		             JValue* v = Parse((std::string("\"") + kLong1 + "\"").c_str());
		             J.set_string(v, J.get_string(v));
		             std::string t = Text(v);
		             Free(v);
		             return t;
	             },
	             std::string("\"") + kLong1 + "\""});
	c.push_back({"json2 string: v.set(v.getString().c_str())", kString,
	             [] {
		             JValue* v = Parse((std::string("\"") + kLong1 + "\"").c_str());
		             J.set_cstring(v, J.cstr(J.get_string(v)));
		             std::string t = Text(v);
		             Free(v);
		             return t;
	             },
	             std::string("\"") + kLong1 + "\""});
	c.push_back({"json2 string: v.set(v[\"a\"].getString())", kString,
	             [] {
		             JValue* v = Parse((std::string(R"({"a":")") + kLong2 + "\"}").c_str());
		             J.set_string(v, J.get_string(Member(v, "a")));
		             std::string t = Text(v);
		             Free(v);
		             return t;
	             },
	             std::string("\"") + kLong2 + "\""});
	c.push_back({"json2 array: v.set(v.getArray())", kArray,
	             [] {
		             JValue* v = Parse(R"([1,[2,3],"x"])");
		             J.set_array(v, J.get_array(v));
		             std::string t = Text(v);
		             Free(v);
		             return t;
	             },
	             R"([1,[2,3],"x"])"});
	c.push_back({"json2 array: v.set(v[\"a\"].getArray())", kArray,
	             [] {
		             JValue* v = Parse(R"({"a":[1,2,{"b":3}]})");
		             J.set_array(v, J.get_array(Member(v, "a")));
		             std::string t = Text(v);
		             Free(v);
		             return t;
	             },
	             R"([1,2,{"b":3}])"});
	c.push_back({"json2 object: v.set(v.getObject())", kObject,
	             [] {
		             JValue* v = Parse(R"({"k":1,"m":"t"})");
		             J.set_object(v, J.get_object(v));
		             std::string t = Text(v);
		             Free(v);
		             return t;
	             },
	             R"({"k":1,"m":"t"})"});
	c.push_back({"json2 object: v.set(v[\"a\"].getObject())", kObject,
	             [] {
		             JValue* v = Parse(R"({"a":{"x":1,"y":[2]},"z":0})");
		             J.set_object(v, J.get_object(Member(v, "a")));
		             std::string t = Text(v);
		             Free(v);
		             return t;
	             },
	             R"({"x":1,"y":[2]})"});
	c.push_back({"json2 object: obj = v[\"a\"].getObject()", kObject,
	             [] {
		             JValue* v = Parse(R"({"a":{"x":1},"z":0})");
		             J.object_assign(J.refer_object(v), J.get_object(Member(v, "a")));
		             std::string t = Text(v);
		             Free(v);
		             return t;
	             },
	             R"({"x":1})"});
	return c;
}

void CaseJson2() {
	lib0405_alloc::g_poison = true;
	for (const auto& a: AliasCases()) {
		g_case = a.name;
		if ((g_json2 & a.item) != 0) {
			const std::string t = a.run();
			Report(a.name, t == a.fixed, "got " + t + ", want " + a.fixed);
		} else {
			Info(a.name, "item off, today's code (reads freed memory) run once in a child: " +
			                 InChild([&a] { return a.run() == a.fixed; }));
		}
	}

	g_case = "json2 value: v[\"a\"] = v";
	{
		JValue* v = Parse(R"({"a":{"b":1},"c":2})");
		J.assign(Member(v, "a"), v);
		const std::string t    = Text(v);
		const bool        on   = (g_json2 & kValue) != 0;
		const char*       want = on ? R"({"a":{"a":{"b":1},"c":2},"c":2})" : R"({"a":{"a":{},"c":2},"c":2})";
		Report("json2 value: v[\"a\"] = v (dst inside src)", t == want,
		       "got " + t + ", want " + want + (on ? " (a copy of v as it was)" : " (today's result)"));
		Free(v);
	}

	g_case = "json2 object: obj = obj";
	{
		JValue* v = Parse(R"({"k":1,"m":"t"})");
		void*   o = J.refer_object(v);
		J.object_assign(o, o);
		const std::string t    = Text(v);
		const bool        on   = (g_json2 & kObject) != 0;
		const char*       want = on ? R"({"k":1,"m":"t"})" : "{}";
		Report("json2 object: obj = obj", t == want, "got " + t + ", want " + want + (on ? " (unchanged)" : " (today: emptied)"));
		Free(v);
	}

	g_case = "json2 string: own String keeps its storage";
	if ((g_json2 & kString) != 0) {
		JValue*        v = Parse((std::string("\"") + kLong1 + "\"").c_str());
		const JString* s = J.get_string(v);
		J.set_string(v, s);
		Report("json2 string: v.set(v.getString()) keeps the String", J.get_string(v) == s && std::strcmp(J.cstr(s), kLong1) == 0,
		       "the same String object, its text unchanged");
		Free(v);
	}

	g_case = "json2 independent sources";
	{
		JValue* w = Parse(R"({"q":[true,"s"],"r":{"t":2.5}})");
		JValue* v = Parse(R"({"a":1})");
		J.assign(v, w);
		const std::string t1 = Text(v);
		J.set_value(v, Member(w, "q"));
		const std::string t2 = Text(v);
		J.set_string(v, J.get_string(Member(Member(w, "q"), "x"))); // a missing member: the empty String
		const std::string t3 = Text(v);
		J.set_cstring(v, "plain");
		const std::string t4 = Text(v);
		J.set_array(v, J.get_array(Member(w, "q")));
		const std::string t5 = Text(v);
		J.set_object(v, J.get_object(Member(w, "r")));
		const std::string t6 = Text(v);
		JValue* x = Parse(R"({"u":3})");
		J.object_assign(J.refer_object(x), J.get_object(w));
		const std::string t7 = Text(x);
		const bool ok = t1 == R"({"q":[true,"s"],"r":{"t":2.500000}})" && t2 == R"([true,"s"])" && t3 == "\"\"" &&
		                t4 == "\"plain\"" && t5 == R"([true,"s"])" && t6 == R"({"t":2.500000})" &&
		                t7 == R"({"q":[true,"s"],"r":{"t":2.500000}})" && Text(w) == t1;
		Report("json2 independent sources (all seven calls)", ok,
		       t1 + " | " + t2 + " | " + t3 + " | " + t4 + " | " + t5 + " | " + t6 + " | " + t7);
		Free(x);
		Free(v);
		Free(w);
	}

	g_case = "json2 value: dst == src";
	{
		JValue* v = Parse(R"({"a":[1,2]})");
		J.assign(v, v);
		J.set_value(v, v);
		const std::string t = Text(v);
		Report("json2 value: v = v and v.set(v)", t == R"({"a":[1,2]})", "got " + t + " (unchanged, today's dst == src rule)");
		Free(v);
	}

	g_case = "json2 parse into a value that owns a payload";
	{
		JValue* v = Parse(R"({"a":1})");
		const bool parsed = J.parse(v, "[1,2]", 5) == 0;
		const std::string t = Text(v);
		Report("json2 parse into a value that owns a payload", parsed && t == "[1,2]", "got " + t);
		Free(v);
	}

	g_case = "json2 parent pointers";
	{
		JValue* w = Parse(R"({"b":{"c":1}})");
		JValue* v = Parse(R"([0])");
		J.assign(v, w);
		JValue*    b  = Member(v, "b");
		const bool ok = b != nullptr && b->parent == v && Member(b, "c")->parent == b && v->parent == nullptr;
		Report("json2 parent pointers after v = w", ok, "the members point at v, theirs at them");
		Free(v);
		Free(w);
		if ((g_json2 & kValue) != 0) {
			JValue* u = Parse(R"({"a":{"b":{"c":1}}})");
			J.assign(u, Member(u, "a"));
			JValue*    ub  = Member(u, "b");
			const bool ok2 = ub != nullptr && ub->type == 7 && ub->parent == u && Member(ub, "c")->parent == ub;
			Report("json2 parent pointers after v = v[\"a\"]", ok2, "the moved members point at v");
			Free(u);
		}
	}
	lib0405_alloc::g_poison = false;
}

// =====================================================================================================================
// Ult
// =====================================================================================================================
using UltEntry = int32_t(KYTY_SYSV_ABI*)(uint64_t);

struct Ult {
	int(KYTY_SYSV_ABI* runtime_create)(void*, const char*, uint32_t, uint32_t, void*, const void*, uint32_t);
	int(KYTY_SYSV_ABI* create)(void*, const char*, UltEntry, uint64_t, void*, uint64_t, void*, const void*, uint32_t);
	int(KYTY_SYSV_ABI* join)(void*, int32_t*);
	int(KYTY_SYSV_ABI* wpool_create)(void*, const char*, uint32_t, uint32_t, void*, const void*, uint32_t);
	int(KYTY_SYSV_ABI* dpool_create)(void*, const char*, uint32_t, uint64_t, uint32_t, void*, void*, const void*, uint32_t);
	int(KYTY_SYSV_ABI* queue_create)(void*, const char*, uint64_t, void*, void*, const void*, uint32_t);
	int(KYTY_SYSV_ABI* push)(void*, const void*);
	int(KYTY_SYSV_ABI* try_pop)(void*, void*);
};
Ult U {};

constexpr int kUltState = -2139029498; // 0x80810006
constexpr int kUltAgain = -2139029496; // 0x80810008

alignas(64) unsigned char g_runtime[4096];
alignas(64) unsigned char g_context[4096];
alignas(64) unsigned char g_work[65536];

struct Handle {
	alignas(64) unsigned char bytes[512];
};

void LoadUlt() {
	U.runtime_create = Fn<decltype(U.runtime_create)>("jw9FkZBXo-g", "sceUltUlthreadRuntimeCreate");
	U.create         = Fn<decltype(U.create)>("znI3q8S7KQ4", "_sceUltUlthreadCreate");
	U.join           = Fn<decltype(U.join)>("gCeAI57LGgI", "sceUltUlthreadJoin");
	U.wpool_create   = Fn<decltype(U.wpool_create)>("YiHujOG9vXY", "sceUltWaitingQueueResourcePoolCreate");
	U.dpool_create   = Fn<decltype(U.dpool_create)>("TFHm6-N6vks", "sceUltQueueDataResourcePoolCreate");
	U.queue_create   = Fn<decltype(U.queue_create)>("9Y5keOvb6ok", "sceUltQueueCreate");
	U.push           = Fn<decltype(U.push)>("dUwpX3e5NDE", "sceUltQueuePush");
	U.try_pop        = Fn<decltype(U.try_pop)>("uZz3ci7XYqc", "sceUltQueueTryPop");
}

// An ulthread's entry: sleeps (arg >> 32) ms and returns the low 16 bits of arg.
KYTY_SYSV_ABI int32_t EntryValue(uint64_t arg) {
	const auto ms = static_cast<int>(arg >> 32u);
	if (ms > 0) {
		std::this_thread::sleep_for(std::chrono::milliseconds(ms));
	}
	return static_cast<int32_t>(arg & 0xffffu);
}

struct SelfJoin {
	void*            handle = nullptr;
	std::atomic<int> result {1};
};

// An ulthread's entry that joins itself and keeps the answer.
KYTY_SYSV_ABI int32_t EntrySelfJoin(uint64_t arg) {
	auto*   s  = reinterpret_cast<SelfJoin*>(arg);
	int32_t st = -1;
	s->result  = U.join(s->handle, &st);
	return 77;
}

int Create(Handle* h, UltEntry entry, uint64_t arg, void* runtime = g_runtime) {
	return U.create(h->bytes, "lib0405", entry, arg, g_context, sizeof(g_context), runtime, nullptr, 0);
}

uint64_t Arg(int ms, int value) {
	return (static_cast<uint64_t>(ms) << 32u) | static_cast<uint64_t>(value & 0xffff);
}

void CaseUlt() {
	const bool join_on  = (g_ult & 1u) != 0;
	const bool queue_on = (g_ult & 2u) != 0;
	g_case              = "ult runtime";
	if (U.runtime_create(g_runtime, "lib0405", 128, 4, g_work, nullptr, 0) != 0) {
		SetupFail("sceUltUlthreadRuntimeCreate");
	}

	g_case = "ult sequential join";
	{
		static Handle h;
		const int     c  = Create(&h, EntryValue, Arg(20, 42));
		int32_t       st = -1;
		const int     j1 = U.join(h.bytes, &st);
		int32_t       st2 = -1;
		const int     j2  = U.join(h.bytes, &st2);
		Report("ult create, join, join again", c == 0 && j1 == 0 && st == 42 && j2 == kUltState,
		       Fmt("create %d, join %d status %d, second join 0x%08x (want STATE 0x80810006)", c, j1, st, static_cast<unsigned>(j2)));
	}

	g_case = "ult unknown runtime";
	{
		static Handle h;
		alignas(64) static unsigned char bogus[4096];
		const int c = Create(&h, EntryValue, Arg(0, 1), bogus);
		Report("ult create on an unknown runtime", c == kUltState, Fmt("0x%08x (want STATE)", static_cast<unsigned>(c)));
	}

	g_case = "ult handle created twice";
	{
		static Handle h;
		const int     c1 = Create(&h, EntryValue, Arg(100, 5));
		const int     c2 = Create(&h, EntryValue, Arg(0, 6));
		int32_t       st = -1;
		const int     j  = U.join(h.bytes, &st);
		Report("ult a handle created twice", c1 == 0 && c2 == kUltState && j == 0 && st == 5,
		       Fmt("first %d, second 0x%08x (want STATE), join %d status %d", c1, static_cast<unsigned>(c2), j, st));
	}

	g_case = "ult self-join";
	{
		static Handle   h;
		static SelfJoin s;
		s.handle     = h.bytes;
		const int c  = Create(&h, EntrySelfJoin, reinterpret_cast<uint64_t>(&s));
		const auto t0 = Clock::now();
		while (s.result.load() == 1 && Clock::now() - t0 < std::chrono::seconds(10)) {
			std::this_thread::sleep_for(std::chrono::milliseconds(1));
		}
		int32_t   st = -1;
		const int j  = U.join(h.bytes, &st);
		Report("ult self-join", c == 0 && s.result.load() == kUltState && j == 0 && st == 77,
		       Fmt("create %d, the ulthread's own join 0x%08x (want STATE; %s), then join %d status %d", c,
		           static_cast<unsigned>(s.result.load()), join_on ? "the claim rule" : "today via glibc's EDEADLK", j, st));
	}

	if (join_on) {
		g_case = "ult two joiners";
		{
			static Handle    h;
			const int        c = Create(&h, EntryValue, Arg(300, 42));
			std::atomic<int> go {0};
			int              r[2]  = {1, 1};
			int32_t          st[2] = {-1, -1};
			std::thread      a([&] {
                go++;
                while (go.load() < 2) {
                }
                r[0] = U.join(h.bytes, &st[0]);
            });
			std::thread      b([&] {
                go++;
                while (go.load() < 2) {
                }
                r[1] = U.join(h.bytes, &st[1]);
            });
			a.join();
			b.join();
			const bool one_ok = (r[0] == 0 && st[0] == 42 && r[1] == kUltState) || (r[1] == 0 && st[1] == 42 && r[0] == kUltState);
			Report("ult two joiners of one ulthread", c == 0 && one_ok,
			       Fmt("create %d; joins 0x%08x (status %d) and 0x%08x (status %d): one 0 with 42, one STATE", c,
			           static_cast<unsigned>(r[0]), st[0], static_cast<unsigned>(r[1]), st[1]));
		}

		g_case = "ult create then join at once";
		{
			constexpr int       kRounds = 100;
			std::vector<Handle> hs(kRounds);
			int                 good = 0;
			int                 bad  = 0;
			std::string         first_bad;
			for (int i = 0; i < kRounds; i++) {
				Handle*          h = &hs[static_cast<size_t>(i)];
				std::atomic<int> r {1};
				int32_t          st = -1;
				std::thread      joiner([&] {
                    const auto t0 = Clock::now();
                    for (;;) {
                        const int x = U.join(h->bytes, &st);
                        if (x != kUltState || Clock::now() - t0 > std::chrono::seconds(5)) {
                            r = x;
                            break;
                        }
                    }
                });
				const int        c = Create(h, EntryValue, Arg(0, i));
				joiner.join();
				if (c == 0 && r.load() == 0 && st == i) {
					good++;
				} else {
					bad++;
					if (first_bad.empty()) {
						first_bad = Fmt(", first bad round %d: create %d join 0x%08x status %d", i, c, static_cast<unsigned>(r.load()), st);
					}
				}
			}
			Report("ult 100 creates, each joined at once from another thread", good == kRounds,
			       Fmt("%d of %d joined with their status%s", good, kRounds, first_bad.c_str()));
			(void)bad;
		}
	} else {
		Info("ult two joiners / create then join at once", "not run with \"join\" off: today both call PthreadJoin on one thread "
		                                                  "twice or on one not made yet (undefined)");
	}

	g_case = "ult queue push past num_data";
	{
		alignas(64) static unsigned char wpool[256];
		alignas(64) static unsigned char dpool[512];
		alignas(64) static unsigned char queue[512];
		const int w = U.wpool_create(wpool, "lib0405w", 4, 4, g_work, nullptr, 0);
		const int d = U.dpool_create(dpool, "lib0405d", 2, 8, 1, wpool, g_work, nullptr, 0);
		const int q = U.queue_create(queue, "lib0405q", 8, wpool, dpool, nullptr, 0);
		if (w != 0 || d != 0 || q != 0) {
			SetupFail(Fmt("Ult pools and queue: %d %d %d", w, d, q));
		}
		int p[3] = {1, 1, 1};
		for (uint64_t x = 1; x <= 3; x++) {
			p[x - 1] = U.push(queue, &x);
		}
		uint64_t got[4] = {0, 0, 0, 0};
		int      r[4]   = {1, 1, 1, 1};
		for (int i = 0; i < 4; i++) {
			r[i] = U.try_pop(queue, &got[i]);
		}
		bool ok = p[0] == 0 && p[1] == 0 && p[2] == 0 && r[0] == 0 && got[0] == 1 && r[1] == 0 && got[1] == 2;
		if (queue_on) {
			ok = ok && r[2] == 0 && got[2] == 3 && r[3] == kUltAgain;
		} else {
			ok = ok && r[2] == kUltAgain && r[3] == kUltAgain;
		}
		Report("ult queue: 3 pushes into num_data 2, then 4 pops", ok,
		       Fmt("pushes %d %d %d; pops %d:%" PRIu64 " %d:%" PRIu64 " 0x%08x:%" PRIu64 " 0x%08x (%s)", p[0], p[1], p[2], r[0],
		           got[0], r[1], got[1], static_cast<unsigned>(r[2]), got[2], static_cast<unsigned>(r[3]),
		           queue_on ? "on: 1, 2, 3, then AGAIN" : "off: 1, 2, then AGAIN, the third dropped as today"));
	}
}

// =====================================================================================================================
// UserService
// =====================================================================================================================
constexpr int kNotLoggedIn   = -2137653239; // 0x80960009
constexpr int kInvalid       = -2137653243; // 0x80960005
constexpr int kTooShort      = -2137653238; // 0x8096000A
constexpr int kUnknownUser   = -2137652987; // 0x80960105

using FnGetter = int(KYTY_SYSV_ABI*)(int, void*);
using FnName   = int(KYTY_SYSV_ABI*)(int, char*, size_t);

struct Getter {
	const char* name;
	const char* nid;
	int32_t     today;  // today's value for a logged-in user
	int32_t     on;     // the value with the switch's item on
	uint32_t    item;   // the item that changes the value (0: none)
	FnGetter    fn;
};

void CaseUser() {
	const bool age   = (g_user & 1u) != 0;
	const bool login = (g_user & 2u) != 0;
	const bool name  = (g_user & 4u) != 0;
	const bool zoom  = (g_user & 8u) != 0;

	std::vector<Getter> getters = {
	    {"GetAgeLevel", "woNpu+45RLk", 9, -1, 1u, nullptr},
	    {"GetAccessibilityChatTranscription", "rnEhHqG-4xo", 0, 0, 0u, nullptr},
	    {"GetAccessibilityPressAndHoldDelay", "ZKJtxdgvzwg", 0, 0, 0u, nullptr},
	    {"GetAccessibilityVibration", "qWYHOFwqCxY", 1, 1, 0u, nullptr},
	    {"GetAccessibilityTriggerEffect", "-3Y5GO+-i78", 1, 1, 0u, nullptr},
	    {"GetAccessibilityZoomEnabled", "hD-H81EN9Vg", 0, 0, 0u, nullptr},
	    {"GetAccessibilityZoomFollowFocus", "O6IW1-Dwm-w", 0, 1, 8u, nullptr},
	};
	for (auto& g: getters) {
		g.fn = Fn<FnGetter>(g.nid, g.name);
	}
	for (const auto& g: getters) {
		g_case = g.name;
		const bool changed = g.item != 0 && (g_user & g.item) != 0;
		const int  want    = changed ? g.on : g.today;
		int32_t    v1      = 0x5A5A5A5A;
		const int  r1      = g.fn(1000, &v1);
		int32_t    v2      = 0x5A5A5A5A;
		const int  r2      = g.fn(1003, &v2);
		const int  r3      = g.fn(1000, nullptr);
		int32_t    v4      = 0x5A5A5A5A;
		const int  r4      = g.fn(5, &v4);
		const int  r5      = g.fn(-1, nullptr);
		const int  want5   = login ? kNotLoggedIn : kInvalid;
		const bool ok = r1 == 0 && v1 == want && r2 == 0 && v2 == want && r3 == kInvalid && r4 == kNotLoggedIn && v4 == 0x5A5A5A5A &&
		                r5 == want5;
		Report(Fmt("user %s", g.name).c_str(), ok,
		       Fmt("(1000) %d -> 0x%08x want 0x%08x; (1003) %d; (1000, null) 0x%08x; (5) 0x%08x untouched %d; "
		           "(-1, null) 0x%08x want 0x%08x (%s)",
		           r1, static_cast<unsigned>(v1), static_cast<unsigned>(want), r2, static_cast<unsigned>(r3),
		           static_cast<unsigned>(r4), v4 == 0x5A5A5A5A, static_cast<unsigned>(r5), static_cast<unsigned>(want5),
		           login ? "login before null" : "null before login, today"));
	}
	(void)age;
	(void)zoom;

	g_case            = "user GetUserName";
	const FnName get  = Fn<FnName>("1xxcMiGu2fo", "sceUserServiceGetUserName");
	auto         Name = [&](int user, size_t size, int* r) {
        char buf[32];
        std::memset(buf, 'Z', sizeof(buf));
        *r = get(user, buf, size);
        buf[31] = '\0';
        return std::string(buf);
	};
	{
		int               r1 = 1;
		int               r2 = 1;
		int               r3 = 1;
		const std::string n1 = Name(1000, 16, &r1);
		const std::string n2 = Name(1003, 16, &r2);
		const std::string n3 = Name(1000, 7, &r3);
		Report("user GetUserName of a known user", r1 == 0 && n1 == "Kyty-1" && r2 == 0 && n2 == "Kyty-4" && r3 == 0 && n3 == "Kyty-1",
		       Fmt("(1000, 16) %d %s, (1003, 16) %d %s, (1000, 7) %d %s", r1, n1.c_str(), r2, n2.c_str(), r3, n3.c_str()));
	}
	const std::string untouched(31, 'Z');
	if (name) {
		int               r1 = 1;
		int               r2 = 1;
		int               r3 = 1;
		int               r4 = 1;
		const std::string n1 = Name(5, 16, &r1);
		const std::string n2 = Name(-1, 16, &r2);
		const std::string n3 = Name(1000, 4, &r3);
		const std::string n4 = Name(1000, 6, &r4);
		const int         r5 = get(1000, nullptr, 16);
		Report("user GetUserName errors instead of EXIT",
		       r1 == kUnknownUser && n1 == untouched && r2 == kUnknownUser && n2 == untouched && r3 == kTooShort && n3 == untouched &&
		           r4 == kTooShort && n4 == untouched && r5 == kInvalid,
		       Fmt("(5) 0x%08x, (-1) 0x%08x want 0x80960105; (1000, 4) 0x%08x, (1000, 6) 0x%08x want 0x8096000A; (1000, null) "
		           "0x%08x want 0x80960005; buffers untouched %d %d %d %d",
		           static_cast<unsigned>(r1), static_cast<unsigned>(r2), static_cast<unsigned>(r3), static_cast<unsigned>(r4),
		           static_cast<unsigned>(r5), n1 == untouched, n2 == untouched, n3 == untouched, n4 == untouched));
	} else {
		int r = 0;
		Info("user GetUserName(5, buf, 16) today", InChild([&] { (void)Name(5, 16, &r); return r == kUnknownUser; }));
		Info("user GetUserName(1000, buf, 4) today", InChild([&] { (void)Name(1000, 4, &r); return r == kTooShort; }));
		Info("user GetUserName(1000, buf, 6) today", InChild([&] { (void)Name(1000, 6, &r); return r == kTooShort; }));
		Info("user GetUserName(1000, null, 16) today", InChild([&] { return get(1000, nullptr, 16) == kInvalid; }));
	}
}

// =====================================================================================================================
// SystemService
// =====================================================================================================================
constexpr int kSysParameter = -2136932349; // 0x80A10003

using FnParamInt    = int(KYTY_SYSV_ABI*)(int, int*);
using FnParamString = int(KYTY_SYSV_ABI*)(int, char*, size_t);

// The value today's code answers for an integer parameter (libSystemService.cpp:113-130); 1 is not compared.
int TodayInt(int id) {
	switch (id) {
		case 2: return 1;   // DDMMYYYY
		case 3: return 1;   // 24 hours
		case 4: return 180; // time zone
		case 7: return 0;   // parental off
		case 1000: return 1; // cross
		default: return 0;
	}
}

int TableInt(int id) {
	switch (id) {
		case 101: return 1;
		case 102: return 2;
		case 103:
		case 107:
		case 109: return 100;
		case 104:
		case 110: return 0x20202;
		case 209: return 1;
		case 210: return 71;
		default: return 0;
	}
}

bool Answers(int id) { // the 13.40 sweep (debt :74), without 7 and 1000
	return (id >= 1 && id <= 5) || (id >= 100 && id <= 111) || (id >= 200 && id <= 213) || id == 300 || id == 400;
}

void CaseSystem() {
	const bool int_on    = (g_sys & 1u) != 0;
	const bool table_on  = (g_sys & 2u) != 0;
	const bool string_on = (g_sys & 4u) != 0;
	const auto get_int   = Fn<FnParamInt>("fZo48un7LK4", "sceSystemServiceParamGetInt");
	const auto get_str   = Fn<FnParamString>("SsC-m-S9JTA", "sceSystemServiceParamGetString");

	g_case = "system ParamGetInt";
	std::vector<int> ids;
	for (int i = 0; i <= 8; i++) {
		ids.push_back(i);
	}
	for (int i = 99; i <= 112; i++) {
		ids.push_back(i);
	}
	for (int i = 199; i <= 214; i++) {
		ids.push_back(i);
	}
	for (int id: {299, 300, 301, 399, 400, 401, 999, 1000, 1001, 2048, -1}) {
		ids.push_back(id);
	}
	int         wrong = 0;
	std::string first;
	for (int id: ids) {
		int       v = 0x5A5A5A5A;
		const int r = get_int(id, &v);
		bool      refused;
		if (id == 7 || id == 1000) {
			refused = g_p71000;
		} else {
			refused = int_on && !Answers(id);
		}
		bool ok;
		if (refused) {
			ok = r == kSysParameter && v == 0x5A5A5A5A;
		} else if (id == 1) {
			ok = r == 0 && v != 0x5A5A5A5A; // the language: the configuration's, not compared
		} else {
			const bool in_table = (id >= 100 && id <= 111) || (id >= 200 && id <= 213) || id == 300;
			const int  want     = table_on && in_table ? TableInt(id) : TodayInt(id);
			ok                  = r == 0 && v == want;
		}
		if (!ok) {
			wrong++;
			if (first.empty()) {
				first = Fmt("; first wrong: %d -> %d value 0x%08x", id, r, static_cast<unsigned>(v));
			}
		}
	}
	Report("system ParamGetInt over the parameter list", wrong == 0,
	       Fmt("%zu parameters, %d wrong; int %s, table %s, params 7/1000 %s%s", ids.size(), wrong, int_on ? "on" : "off",
	           table_on ? "on" : "off", g_p71000 ? "on" : "off", first.c_str()));
	{
		const int r = get_int(1, nullptr);
		Report("system ParamGetInt(1, null)", r == kSysParameter, Fmt("0x%08x want 0x80A10003 (today too)", static_cast<unsigned>(r)));
	}

	g_case = "system ParamGetString";
	{
		char      b64[80];
		char      b65[80];
		std::memset(b64, 0x5A, sizeof(b64));
		std::memset(b65, 0x5A, sizeof(b65));
		const int r64  = get_str(6, b64, 64);
		const int r65  = get_str(6, b65, 65);
		const int rnul = get_str(6, nullptr, 65);
		bool      ok;
		if (string_on) {
			bool padded = std::strcmp(b65, "Kyty") == 0 && b65[65] == 0x5A;
			for (int i = 4; i < 65; i++) {
				padded = padded && b65[i] == 0;
			}
			bool left = true;
			for (char c: b64) {
				left = left && c == 0x5A;
			}
			ok = r64 == kSysParameter && left && r65 == 0 && padded && rnul == kSysParameter;
		} else {
			ok = r64 == 0 && std::strcmp(b64, "Kyty") == 0 && b64[5] == 0x5A && r65 == 0 && std::strcmp(b65, "Kyty") == 0 &&
			     b65[5] == 0x5A && rnul == kSysParameter;
		}
		Report("system ParamGetString(6) with 64 and 65 bytes and a null buffer", ok,
		       Fmt("64: %d, 65: %d, null: 0x%08x (%s)", r64, r65, static_cast<unsigned>(rnul),
		           string_on ? "on: 64 refused untouched, 65 NUL-padded" : "off: both answer, nothing padded, today"));
	}
	if (string_on) {
		char      b[80];
		std::memset(b, 0x5A, sizeof(b));
		const int r0 = get_str(0, b, 65);
		const int r7 = get_str(7, b, 65);
		const int r1 = get_str(1000, b, 65);
		bool      left = true;
		for (char c: b) {
			left = left && c == 0x5A;
		}
		Report("system ParamGetString of unknown parameters", r0 == kSysParameter && r7 == kSysParameter && r1 == kSysParameter && left,
		       Fmt("0: 0x%08x, 7: 0x%08x, 1000: 0x%08x, buffer untouched %d", static_cast<unsigned>(r0), static_cast<unsigned>(r7),
		           static_cast<unsigned>(r1), left));
	} else {
		Info("system ParamGetString(7, buf, 65) today", InChild([&] {
			     char b[80];
			     return get_str(7, b, 65) == kSysParameter;
		     }));
	}
}

// ---- the subsystems a guest thread needs, as sav0401.cpp starts them -------------------------------------------------
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
	slist.Add(log, {core, config});
	slist.Add(timer, {core, log});
	slist.Add(memory, {core, log});
	slist.Add(pthread, {core, log, timer});
	if (!slist.InitAll(false)) {
		SetupFail(Fmt("subsystem %s: %s", slist.GetFailName(), slist.GetFailMsg()));
	}
	(void)Common::Singleton<Loader::RuntimeLinker>::Instance();

	g_case = "init: registration";
	static Loader::SymbolDatabase db;
	Libs::InitAll(&db); // prints the units' five "[bc5] exp 0405: ..." lines on stderr
	g_db = &db;
}

} // namespace lib0405

int main(int argc, char** argv) {
	using namespace lib0405;
	g_json2  = Items("KYTY_BC5_JSON2_FIXES", {"value", "string", "array", "object"});
	g_ult    = Items("KYTY_BC5_ULT_FIXES", {"join", "queue"});
	g_user   = Items("KYTY_BC5_USERSERVICE_VALUES", {"age", "login", "name", "zoom"});
	g_sys    = Items("KYTY_BC5_SYSTEMSERVICE_VALUES", {"int", "table", "string"});
	const char* p71000 = std::getenv("KYTY_BC5_SYSTEMSERVICE_PARAMS_7_1000");
	g_p71000           = p71000 != nullptr && p71000[0] != '\0' && std::strcmp(p71000, "0") != 0;
	const bool  all_on  = g_json2 == 15 && g_ult == 3 && g_user == 15 && g_sys == 7 && g_p71000;
	const bool  all_off = g_json2 == 0 && g_ult == 0 && g_user == 0 && g_sys == 0 && !g_p71000;
	const char* mode    = all_on ? "on" : all_off ? "off" : "mixed";
	if (argc > 2 || (argc == 2 && std::strcmp(argv[1], mode) != 0)) {
		std::printf("lib0405: the argument says %s but the switches say %s (json2 0x%x, ult 0x%x, user 0x%x, system 0x%x, params "
		            "7/1000 %d)\n",
		            argc == 2 ? argv[1] : "too much", mode, g_json2, g_ult, g_user, g_sys, g_p71000);
		return 2;
	}
	std::printf("lib0405: switches json2 0x%x, ult 0x%x, user 0x%x, system 0x%x, params 7/1000 %d: %s\n", g_json2, g_ult, g_user,
	            g_sys, g_p71000, mode);
	std::fflush(stdout);
	unsetenv("KYTY_BC5_INPUT_CONFIG"); // ParamGetInt(1) then answers --console-language, read from nothing on disk
	::Log::Bc5SetLogging(false);       // the units' LOGF lines stay off stdout
	std::thread(Watchdog).detach();

	char  arg0[] = "lib0405";
	char* args[] = {arg0, nullptr};
	Init(1, args);
	LoadJson2();
	LoadUlt();

	CaseJson2();
	CaseUlt();
	CaseUser();
	CaseSystem();

	const int n = g_cases.load();
	const int p = g_passed.load();
	if (p != n) {
		std::printf("lib0405: %s %d of %d passed; FAIL\n", mode, p, n);
		std::fflush(stdout);
		std::_Exit(1);
	}
	std::printf("lib0405: %s %d of %d; end\n", mode, p, n);
	std::fflush(stdout);
	std::_Exit(0); // no static destructors: the Pthread subsystem's helper thread may still run
}
