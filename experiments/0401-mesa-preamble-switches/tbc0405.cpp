// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0405 (series e6 of experiment 0401), tag "tbc": the CPU test of mktbc0405.py's edits of src/libs/libZlib.cpp,
// libJpeg.cpp and libIme.cpp (notes tbc0405-notes.md): three of the tables that are compiled but never loaded, ported
// first (exp 0405 decision 4), each behind its own switch:
//   KYTY_BC5_LOAD_ZLIB (no items), KYTY_BC5_LOAD_JPEG (no items), KYTY_BC5_LOAD_IME (items panel,test).
// No game, no GPU, no window, no sound device, no network, no subsystem. The test registers the three tables and the live
// Ime table into its own SymbolDatabase in the order Libs::InitAll uses with the switches on (tag "tld": the unloaded
// tables first, then the live ones), takes the functions by their exact keys (NID, library, versions) as a title's import
// resolves them, and calls them as a title would. Each output a title gets is checked as written or left as it was
// (outputs start as a sentinel).
// Cases (one line each; tbc0405-notes.md has the reasons):
//   zlib  registration (5 NIDs); on: the not-initialized answers, Initialize's checks and ALREADY_INITIALIZED, Inflate's
//         argument checks, an inflate (result, the bytes, a repeated GetResult), NO_SPACE, FATAL for a corrupt and a
//         truncated stream, three requests handed out in order, 64 KiB, a destination off 2 KiB, TIMED_OUT (0 and 2000 us),
//         GetResult's checks and NOT_FOUND, a wait that Finalize ends, results dropped by Finalize, ids that keep counting.
//         off: every call returns 0 and writes nothing (today's stubs).
//   jpeg  registration (4 NIDs); on: QueryMemorySize and Create's checks, the handle at the first 32-byte boundary, Delete
//         and Encode's handle checks, 33 encode-parameter cases, an Encode that passes (held: 0, nothing written).
//         off: every call returns 0 and writes nothing.
//   ime   registration (41 NIDs: the 7 the live Ime table registers are not this table's, both ways), the 7 resolved to
//         ime.cpp's functions by the exact key and by the NID-only fallback FindByNid, the 39 held NIDs to this table,
//         GetPanelPositionAndForm with no panel, a Default panel, a Number panel over 2K and after Close,
//         ForTestFunction, and the 39 held stubs (0 both ways).
// Build (build0401.py, series e6): --gate tbc0405.cpp <out> --like src/libs/libZlib.cpp, with the three private units
// (src/libs/libZlib.cpp=<it> ... from mktbc0405.py) in place of the shared ones, linked with every emulator object but
// main.cpp.o.
// usage: run in a fresh directory, with the three switches set alike:
//   all three =1 -> "tbc0405 on";  all three =0, or all unset -> "tbc0405 off". KYTY_BC5_LOAD_IME may name items
//   ("panel"): each case then expects its own item's state, and the last line says "mixed". The argument may be left
//   out. Prints "tbc0405: on|off|mixed N of N; end" and exits 0 only then. A watchdog ends a hang after 60 s with a FAIL
//   line.

#include "common/abi.h"
#include "libs/errno.h"
#include "libs/ime.h"
#include "libs/libs.h"
#include "loader/symbolDatabase.h"

#include <zlib.h>

#include <atomic>
#include <chrono>
#include <cinttypes>
#include <cstdarg>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <thread>
#include <vector>

namespace Libs::LibZlib {
LIB_DEFINE(InitZlib_1);
} // namespace Libs::LibZlib
namespace Libs::LibJpeg {
LIB_DEFINE(InitJpeg_1);
} // namespace Libs::LibJpeg
namespace Libs::LibIme {
LIB_DEFINE(InitIme_1);
} // namespace Libs::LibIme
namespace Libs::Ime {
LIB_DEFINE(InitPlatform_1_Ime);
} // namespace Libs::Ime

namespace tbc0405 {

using Clock = std::chrono::steady_clock;

constexpr int      kWatchdogSeconds = 60;
constexpr uint64_t kS64             = 0x5A5A5A5A5A5A5A5Aull; // an output the call has not written
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

void Check(const char* name, bool ok, const std::string& info) {
	g_cases++;
	if (ok) {
		g_passed++;
	}
	std::printf("tbc0405: case %d %s: %s (%s)\n", g_cases.load(), name, ok ? "ok" : "FAIL", info.c_str());
	std::fflush(stdout);
}

[[noreturn]] void SetupFail(const std::string& what) {
	std::printf("tbc0405: FAIL setup: %s\n", what.c_str());
	std::fflush(stdout);
	std::_Exit(2);
}

void Watchdog() {
	std::this_thread::sleep_for(std::chrono::seconds(kWatchdogSeconds));
	std::printf("tbc0405: FAIL watchdog: case \"%s\" still running after %d s (a hang); %d of %d cases passed before it\n",
	            g_case.load(), kWatchdogSeconds, g_passed.load(), g_cases.load());
	std::fflush(stdout);
	std::_Exit(3);
}

// ---- the switches, read as the units read them ----------------------------------------------------------------------
bool EnvOn(const char* name) {
	const char* e = std::getenv(name);
	return e != nullptr && e[0] != '\0' && !(e[0] == '0' && e[1] == '\0');
}

uint32_t ImeItems() {
	const char* e = std::getenv("KYTY_BC5_LOAD_IME");
	if (e == nullptr || e[0] == '\0' || std::strcmp(e, "0") == 0) {
		return 0;
	}
	static const char* const names[] = {"panel", "test"};
	uint32_t                 parts   = 0;
	const char*              p       = e;
	for (;;) {
		const char*  comma = std::strchr(p, ',');
		const size_t n     = comma != nullptr ? static_cast<size_t>(comma - p) : std::strlen(p);
		for (uint32_t i = 0; i < 2; i++) {
			if (n == std::strlen(names[i]) && std::strncmp(p, names[i], n) == 0) {
				parts |= 1u << i;
			}
		}
		if (comma == nullptr) {
			break;
		}
		p = comma + 1;
	}
	return parts != 0 ? parts : 3u;
}

bool     g_zlib = false;
bool     g_jpeg = false;
uint32_t g_ime  = 0; // panel 1, test 2

// ---- registration and lookup ----------------------------------------------------------------------------------------
Loader::SymbolDatabase g_all;      // the three tables, then the live Ime table (the order of Libs::InitAll with them on)
Loader::SymbolDatabase g_dead_ime; // InitIme_1 alone
Loader::SymbolDatabase g_live_ime; // InitPlatform_1_Ime alone

const Loader::SymbolRecord* Exact(const Loader::SymbolDatabase& db, const char* nid, const char* lib) {
	Loader::SymbolResolve sr {};
	sr.name                 = nid;
	sr.library              = lib;
	sr.library_version      = 1;
	sr.module               = lib;
	sr.module_version_major = 1;
	sr.module_version_minor = 1;
	sr.type                 = Loader::SymbolType::Func;
	return db.Find(sr);
}

uint64_t Addr(const Loader::SymbolDatabase& db, const char* nid, const char* lib) {
	const auto* r = Exact(db, nid, lib);
	return r != nullptr ? r->vaddr : 0;
}

template <typename F>
F Fn(const char* nid, const char* lib) {
	const uint64_t a = Addr(g_all, nid, lib);
	if (a == 0) {
		SetupFail(Fmt("%s (%s) is not registered", nid, lib));
	}
	return reinterpret_cast<F>(a);
}

std::string Hex(int r) {
	return Fmt("0x%08x", static_cast<uint32_t>(r));
}

bool AllBytes(const uint8_t* p, size_t n, uint8_t v) {
	for (size_t i = 0; i < n; i++) {
		if (p[i] != v) {
			return false;
		}
	}
	return true;
}

// =====================================================================================================================
// Zlib
// =====================================================================================================================
using ZInit    = int(KYTY_SYSV_ABI*)(const void*, uint64_t);
using ZFin     = int(KYTY_SYSV_ABI*)();
using ZInflate = int(KYTY_SYSV_ABI*)(const void*, uint32_t, void*, uint32_t, uint64_t*);
using ZWait    = int(KYTY_SYSV_ABI*)(uint64_t*, const uint32_t*);
using ZGet     = int(KYTY_SYSV_ABI*)(uint64_t, uint32_t*, int32_t*);

constexpr int kZNotFound    = static_cast<int>(0x81120002u);
constexpr int kZInvalid     = static_cast<int>(0x81120016u);
constexpr int kZNoSpace     = static_cast<int>(0x8112001Cu);
constexpr int kZTimedOut    = static_cast<int>(0x81120027u);
constexpr int kZNotInit     = static_cast<int>(0x81120032u);
constexpr int kZAlreadyInit = static_cast<int>(0x81120033u);
constexpr int kZFatal       = static_cast<int>(0x811200FFu);

alignas(2048) uint8_t g_dst[65536 + 4096];
alignas(64) uint8_t g_work[4096];

std::vector<uint8_t> Pattern(size_t n, uint32_t seed) {
	std::vector<uint8_t> p(n);
	uint32_t             x = seed * 2654435761u + 1u;
	for (size_t i = 0; i < n; i++) {
		x    = x * 1103515245u + 12345u;
		p[i] = static_cast<uint8_t>((i % 61 < 40) ? (i & 0xffu) : (x >> 16)); // part runs, part noise
	}
	return p;
}

std::vector<uint8_t> Deflate(const std::vector<uint8_t>& p) {
	uLongf               n = compressBound(static_cast<uLong>(p.size()));
	std::vector<uint8_t> out(n);
	if (compress2(out.data(), &n, p.data(), static_cast<uLong>(p.size()), 6) != Z_OK) {
		SetupFail("compress2");
	}
	out.resize(n);
	return out;
}

void CaseZlib() {
	g_case = "zlib";
	const char* lib  = "libSceZlib";
	const char* nids[] = {"m1YErdIXCp4", "6na+Sa-B83w", "TLar1HULv1Q", "uB8VlDD4e0s", "2eDcGHC0YaM"};
	int         found  = 0;
	for (const char* n: nids) {
		found += Addr(g_all, n, lib) != 0 ? 1 : 0;
	}
	Check("zlib registration", found == 5, Fmt("%d of 5 NIDs registered", found));

	auto init    = Fn<ZInit>("m1YErdIXCp4", lib);
	auto fin     = Fn<ZFin>("6na+Sa-B83w", lib);
	auto inflate = Fn<ZInflate>("TLar1HULv1Q", lib);
	auto wait    = Fn<ZWait>("uB8VlDD4e0s", lib);
	auto get     = Fn<ZGet>("2eDcGHC0YaM", lib);

	const auto p1 = Pattern(3000, 1);
	const auto s1 = Deflate(p1);
	const auto n1 = static_cast<uint32_t>(s1.size());

	if (!g_zlib) {
		int r1 = init(nullptr, 0);
		int r2 = init(nullptr, 0);
		int r3 = init(nullptr, 16);
		Check("zlib off: Initialize x3 (no checks, no ALREADY_INITIALIZED)", r1 == 0 && r2 == 0 && r3 == 0,
		      Hex(r1) + " " + Hex(r2) + " " + Hex(r3));
		uint64_t id = kS64;
		std::memset(g_dst, 0xA5, 4096);
		int r = inflate(s1.data(), n1, g_dst, 4096, &id);
		Check("zlib off: Inflate of a valid stream: 0, no request id, nothing inflated", r == 0 && id == kS64 && AllBytes(g_dst, 4096, 0xA5),
		      Fmt("%s, id %s, destination %s", Hex(r).c_str(), id == kS64 ? "not written" : "written",
		          AllBytes(g_dst, 4096, 0xA5) ? "not written" : "written"));
		r = inflate(nullptr, 0, nullptr, 0, nullptr);
		Check("zlib off: Inflate of nulls: 0", r == 0, Hex(r));
		uint64_t w = kS64;
		r          = wait(&w, nullptr);
		Check("zlib off: WaitForDone without timeout returns at once: 0, nothing written", r == 0 && w == kS64,
		      Fmt("%s, id %s", Hex(r).c_str(), w == kS64 ? "not written" : "written"));
		uint32_t len = kS32;
		int32_t  st  = static_cast<int32_t>(kS32);
		r            = get(1, &len, &st);
		Check("zlib off: GetResult: 0, nothing written", r == 0 && len == kS32 && st == static_cast<int32_t>(kS32),
		      Fmt("%s, length %s, status %s", Hex(r).c_str(), len == kS32 ? "not written" : "written",
		          st == static_cast<int32_t>(kS32) ? "not written" : "written"));
		r1 = fin();
		r2 = fin();
		Check("zlib off: Finalize x2", r1 == 0 && r2 == 0, Hex(r1) + " " + Hex(r2));
		return;
	}

	// before Initialize
	int r = fin();
	Check("zlib Finalize before Initialize: NOT_INITIALIZED", r == kZNotInit, Hex(r));
	uint64_t id = kS64;
	r           = inflate(s1.data(), n1, g_dst, 4096, &id);
	Check("zlib Inflate before Initialize: NOT_INITIALIZED, no id", r == kZNotInit && id == kS64, Hex(r));
	r = wait(&id, nullptr);
	Check("zlib WaitForDone before Initialize: NOT_INITIALIZED, no id", r == kZNotInit && id == kS64, Hex(r));
	uint32_t len = kS32;
	int32_t  st  = static_cast<int32_t>(kS32);
	r            = get(1, &len, &st);
	Check("zlib GetResult before Initialize: NOT_INITIALIZED, nothing written",
	      r == kZNotInit && len == kS32 && st == static_cast<int32_t>(kS32), Hex(r));

	// Initialize
	r = init(nullptr, 16);
	Check("zlib Initialize(null, 16): INVALID_ARGUMENT", r == kZInvalid, Hex(r));
	r = init(g_work, 0);
	Check("zlib Initialize(memory, 0): INVALID_ARGUMENT", r == kZInvalid, Hex(r));
	r = init(nullptr, 0);
	Check("zlib Initialize(null, 0): 0", r == 0, Hex(r));
	r = init(nullptr, 0);
	Check("zlib Initialize again: ALREADY_INITIALIZED", r == kZAlreadyInit, Hex(r));

	// Inflate's argument checks
	struct Bad {
		const char* name;
		const void* src;
		uint32_t    src_len;
		void*       dst;
		uint32_t    dst_len;
		bool        null_id;
	};
	const Bad bad[] = {
	    {"zlib Inflate null source: INVALID_ARGUMENT", nullptr, n1, g_dst, 4096, false},
	    {"zlib Inflate source length 0: INVALID_ARGUMENT", s1.data(), 0, g_dst, 4096, false},
	    {"zlib Inflate null destination: INVALID_ARGUMENT", s1.data(), n1, nullptr, 4096, false},
	    {"zlib Inflate null request id: INVALID_ARGUMENT", s1.data(), n1, g_dst, 4096, true},
	    {"zlib Inflate destination length 0: INVALID_ARGUMENT", s1.data(), n1, g_dst, 0, false},
	    {"zlib Inflate destination length 66 KiB: INVALID_ARGUMENT", s1.data(), n1, g_dst, 65536 + 2048, false},
	    {"zlib Inflate destination length 3000 (not 2 KiB steps): INVALID_ARGUMENT", s1.data(), n1, g_dst, 3000, false},
	};
	for (const auto& b: bad) {
		id = kS64;
		r  = inflate(b.src, b.src_len, b.dst, b.dst_len, b.null_id ? nullptr : &id);
		Check(b.name, r == kZInvalid && id == kS64, Fmt("%s, id %s", Hex(r).c_str(), id == kS64 ? "not written" : "written"));
	}

	// one request
	std::memset(g_dst, 0xA5, sizeof(g_dst));
	uint64_t id1 = kS64;
	r            = inflate(s1.data(), n1, g_dst, 4096, &id1);
	Check("zlib Inflate of 3000 bytes into 4 KiB: 0 and an id", r == 0 && id1 != kS64, Fmt("%s, id %" PRIu64, Hex(r).c_str(), id1));
	uint64_t w = kS64;
	r          = wait(&w, nullptr);
	Check("zlib WaitForDone: that id", r == 0 && w == id1, Fmt("%s, id %" PRIu64, Hex(r).c_str(), w));
	r = get(id1, &len, &st);
	const bool bytes1 = std::memcmp(g_dst, p1.data(), p1.size()) == 0 && AllBytes(g_dst + 3000, 4096 - 3000, 0xA5);
	Check("zlib GetResult: 3000 bytes, status 0, the bytes, nothing past them", r == 0 && len == 3000 && st == 0 && bytes1,
	      Fmt("%s, length %u, status %s, bytes %s", Hex(r).c_str(), len, Hex(st).c_str(), bytes1 ? "equal" : "differ"));
	len = kS32;
	st  = static_cast<int32_t>(kS32);
	r   = get(id1, &len, &st);
	Check("zlib GetResult again: the same result", r == 0 && len == 3000 && st == 0,
	      Fmt("%s, length %u, status %s", Hex(r).c_str(), len, Hex(st).c_str()));

	// three requests, handed out in order: NO_SPACE, a corrupt stream, a truncated stream
	const auto p2 = Pattern(5000, 2);
	const auto s2 = Deflate(p2);
	const char corrupt[] = "this is not a zlib stream, just some text";
	uint64_t   a = kS64, b = kS64, c = kS64;
	std::memset(g_dst, 0xA5, sizeof(g_dst));
	const int ra = inflate(s2.data(), static_cast<uint32_t>(s2.size()), g_dst, 2048, &a);
	const int rb = inflate(corrupt, sizeof(corrupt), g_dst + 8192, 2048, &b);
	const int rc = inflate(s1.data(), n1 / 2, g_dst + 16384, 4096, &c);
	Check("zlib three Inflates: 0 each, three ids", ra == 0 && rb == 0 && rc == 0 && a != kS64 && b != kS64 && c != kS64,
	      Fmt("%s %s %s; ids %" PRIu64 " %" PRIu64 " %" PRIu64, Hex(ra).c_str(), Hex(rb).c_str(), Hex(rc).c_str(), a, b, c));
	uint64_t w1 = kS64, w2 = kS64, w3 = kS64;
	const int r1 = wait(&w1, nullptr);
	const int r2 = wait(&w2, nullptr);
	const int r3 = wait(&w3, nullptr);
	Check("zlib WaitForDone x3: the ids in submission order", r1 == 0 && r2 == 0 && r3 == 0 && w1 == a && w2 == b && w3 == c,
	      Fmt("%" PRIu64 " %" PRIu64 " %" PRIu64, w1, w2, w3));
	r = get(a, &len, &st);
	const bool bytes2 = std::memcmp(g_dst, p2.data(), 2048) == 0 && AllBytes(g_dst + 2048, 2048, 0xA5);
	Check("zlib 5000 bytes into 2 KiB: NO_SPACE, 2048 bytes written, the first 2048 bytes",
	      r == 0 && st == kZNoSpace && len == 2048 && bytes2,
	      Fmt("%s, length %u, status %s, bytes %s", Hex(r).c_str(), len, Hex(st).c_str(), bytes2 ? "equal" : "differ"));
	r = get(b, &len, &st);
	Check("zlib corrupt stream: FATAL, 0 bytes", r == 0 && st == kZFatal && len == 0,
	      Fmt("%s, length %u, status %s", Hex(r).c_str(), len, Hex(st).c_str()));
	r = get(c, &len, &st);
	Check("zlib truncated stream: FATAL", r == 0 && st == kZFatal && len < 3000,
	      Fmt("%s, length %u, status %s", Hex(r).c_str(), len, Hex(st).c_str()));

	// 64 KiB
	const auto p3 = Pattern(65536, 3);
	const auto s3 = Deflate(p3);
	uint64_t   d  = kS64;
	r             = inflate(s3.data(), static_cast<uint32_t>(s3.size()), g_dst, 65536, &d);
	w             = kS64;
	const int rw  = wait(&w, nullptr);
	const int rg  = get(d, &len, &st);
	const bool bytes3 = std::memcmp(g_dst, p3.data(), p3.size()) == 0;
	Check("zlib 64 KiB into 64 KiB: status 0, 65536 bytes", r == 0 && rw == 0 && w == d && rg == 0 && st == 0 && len == 65536 && bytes3,
	      Fmt("%s %s %s, length %u, status %s, bytes %s", Hex(r).c_str(), Hex(rw).c_str(), Hex(rg).c_str(), len, Hex(st).c_str(),
	          bytes3 ? "equal" : "differ"));

	// a destination off 2 KiB (AnyPS5 throws there; here written as any other)
	const auto p4 = Pattern(100, 4);
	const auto s4 = Deflate(p4);
	std::memset(g_dst, 0xA5, 4096);
	uint64_t e = kS64;
	r          = inflate(s4.data(), static_cast<uint32_t>(s4.size()), g_dst + 16, 2048, &e);
	w          = kS64;
	(void)wait(&w, nullptr);
	const int  re     = get(e, &len, &st);
	const bool bytes4 = std::memcmp(g_dst + 16, p4.data(), p4.size()) == 0 && AllBytes(g_dst, 16, 0xA5);
	Check("zlib destination off 2 KiB: written (TODO(verify))", r == 0 && re == 0 && st == 0 && len == 100 && bytes4,
	      Fmt("%s %s, length %u, status %s, bytes %s", Hex(r).c_str(), Hex(re).c_str(), len, Hex(st).c_str(), bytes4 ? "equal" : "differ"));

	// nothing pending: timeouts
	const uint32_t t0 = 0;
	w                 = kS64;
	r                 = wait(&w, &t0);
	Check("zlib WaitForDone(timeout 0) with nothing pending: TIMED_OUT, no id", r == kZTimedOut && w == kS64, Hex(r));
	const uint32_t t2    = 2000;
	const auto     start = Clock::now();
	r                    = wait(&w, &t2);
	const auto us        = std::chrono::duration_cast<std::chrono::microseconds>(Clock::now() - start).count();
	Check("zlib WaitForDone(timeout 2000 us): TIMED_OUT after about 2 ms", r == kZTimedOut && w == kS64 && us >= 1500 && us < 2000000,
	      Fmt("%s after %lld us", Hex(r).c_str(), static_cast<long long>(us)));
	r = wait(nullptr, &t0);
	Check("zlib WaitForDone(null id): INVALID_ARGUMENT", r == kZInvalid, Hex(r));

	// GetResult's checks
	len = kS32;
	st  = static_cast<int32_t>(kS32);
	r   = get(0x7fffffffffffull, &len, &st);
	Check("zlib GetResult of an unknown id: NOT_FOUND, nothing written", r == kZNotFound && len == kS32 && st == static_cast<int32_t>(kS32),
	      Hex(r));
	r = get(id1, nullptr, &st);
	Check("zlib GetResult(null length): INVALID_ARGUMENT", r == kZInvalid, Hex(r));
	r = get(id1, &len, nullptr);
	Check("zlib GetResult(null status): INVALID_ARGUMENT", r == kZInvalid, Hex(r));

	// a wait that Finalize ends
	g_case = "zlib: a wait that Finalize ends";
	std::atomic<int>       waited {1};
	std::atomic<long long> waited_ms {0};
	std::thread            waiter([&] {
        uint64_t   x  = kS64;
        const auto t  = Clock::now();
        waited        = wait(&x, nullptr);
        waited_ms     = std::chrono::duration_cast<std::chrono::milliseconds>(Clock::now() - t).count();
    });
	std::this_thread::sleep_for(std::chrono::milliseconds(300));
	r = fin();
	waiter.join();
	Check("zlib a WaitForDone without timeout that Finalize ends: NOT_INITIALIZED (TODO(verify))",
	      r == 0 && waited == kZNotInit && waited_ms >= 50,
	      Fmt("Finalize %s, the wait %s after %lld ms", Hex(r).c_str(), Hex(waited.load()).c_str(), waited_ms.load()));
	g_case = "zlib";

	// after Finalize
	r = get(id1, &len, &st);
	Check("zlib GetResult after Finalize: NOT_INITIALIZED", r == kZNotInit, Hex(r));
	r = init(g_work, sizeof(g_work));
	Check("zlib Initialize with a work memory: 0 (accepted, not used; TODO(verify))", r == 0, Hex(r));
	r = get(id1, &len, &st);
	Check("zlib results dropped by Finalize: NOT_FOUND", r == kZNotFound, Hex(r));
	uint64_t f = kS64;
	r          = inflate(s1.data(), n1, g_dst, 4096, &f);
	w          = kS64;
	const int rf  = wait(&w, nullptr);
	const int rf2 = get(f, &len, &st);
	Check("zlib after a new Initialize: ids keep counting, the inflate works",
	      r == 0 && rf == 0 && rf2 == 0 && w == f && f > e && st == 0 && len == 3000,
	      Fmt("id %" PRIu64 " after %" PRIu64 ", status %s, length %u", f, e, Hex(st).c_str(), len));
	r              = fin();
	const int rfin = fin();
	Check("zlib Finalize, then Finalize again: 0, NOT_INITIALIZED", r == 0 && rfin == kZNotInit, Hex(r) + " " + Hex(rfin));
}

// =====================================================================================================================
// Jpeg
// =====================================================================================================================
using JQuery  = int(KYTY_SYSV_ABI*)(const void*);
using JCreate = int(KYTY_SYSV_ABI*)(const void*, void*, uint32_t, void**);
using JDelete = int(KYTY_SYSV_ABI*)(void*);
using JEncode = int(KYTY_SYSV_ABI*)(void*, const void*, void*);

constexpr int kJAddr   = static_cast<int>(0x80650101u);
constexpr int kJSize   = static_cast<int>(0x80650102u);
constexpr int kJParam  = static_cast<int>(0x80650103u);
constexpr int kJHandle = static_cast<int>(0x80650104u);

struct JCreateParam {
	uint32_t size;
	uint32_t attr;
};

struct JEncodeParam {
	const void* image;
	void*       jpeg;
	uint32_t    image_size;
	uint32_t    jpeg_size;
	uint32_t    image_width;
	uint32_t    image_height;
	uint32_t    image_pitch;
	uint16_t    pixel_format;
	uint16_t    encode_mode;
	uint16_t    color_space;
	uint8_t     sampling_type;
	uint8_t     compression_ratio;
	int32_t     restart_interval;
};
static_assert(sizeof(JEncodeParam) == 0x30);

struct JOutputInfo {
	uint32_t size;
	uint32_t height;
};

alignas(64) uint8_t g_jmem[0x900];
alignas(64) uint8_t g_jzero[64];
alignas(64) uint8_t g_img[64 * 64 * 4];
alignas(64) uint8_t g_jpg[4096];

void CaseJpeg() {
	g_case             = "jpeg";
	const char* lib    = "libSceJpegEnc";
	const char* nids[] = {"K+rocojkr-I", "j1LyMdaM+C0", "QbrU0cUghEM", "o6ZgXfFdWXQ"};
	int         found  = 0;
	for (const char* n: nids) {
		found += Addr(g_all, n, lib) != 0 ? 1 : 0;
	}
	Check("jpeg registration", found == 4, Fmt("%d of 4 NIDs registered", found));

	auto create = Fn<JCreate>("K+rocojkr-I", lib);
	auto del    = Fn<JDelete>("j1LyMdaM+C0", lib);
	auto encode = Fn<JEncode>("QbrU0cUghEM", lib);
	auto query  = Fn<JQuery>("o6ZgXfFdWXQ", lib);

	const JCreateParam ok_cp {8, 0};
	JEncodeParam       base {};
	base.image             = g_img;
	base.jpeg              = g_jpg;
	base.image_size        = 16 * 64;
	base.jpeg_size         = sizeof(g_jpg);
	base.image_width       = 16;
	base.image_height      = 16;
	base.image_pitch       = 64;
	base.pixel_format      = 0; // R8G8B8A8
	base.encode_mode       = 0;
	base.color_space       = 1; // YCC
	base.sampling_type     = 2; // 4:2:0
	base.compression_ratio = 128;
	base.restart_interval  = 0;

	if (!g_jpeg) {
		int r1 = query(&ok_cp);
		int r2 = query(nullptr);
		Check("jpeg off: QueryMemorySize: 0 (no memory size), also for null", r1 == 0 && r2 == 0, Hex(r1) + " " + Hex(r2));
		void* h = reinterpret_cast<void*>(kS64);
		std::memset(g_jmem, 0xA5, sizeof(g_jmem));
		int r = create(&ok_cp, g_jmem, 0x800, &h);
		Check("jpeg off: Create: 0, no handle written, the memory untouched",
		      r == 0 && h == reinterpret_cast<void*>(kS64) && AllBytes(g_jmem, sizeof(g_jmem), 0xA5), Hex(r));
		r = del(nullptr);
		Check("jpeg off: Delete(null): 0", r == 0, Hex(r));
		JOutputInfo info {kS32, kS32};
		std::memset(g_jpg, 0xA5, sizeof(g_jpg));
		r1 = encode(nullptr, nullptr, &info);
		r2 = encode(g_jmem, &base, &info);
		Check("jpeg off: Encode (null and a valid-looking call): 0, nothing written",
		      r1 == 0 && r2 == 0 && info.size == kS32 && info.height == kS32 && AllBytes(g_jpg, sizeof(g_jpg), 0xA5),
		      Hex(r1) + " " + Hex(r2));
		return;
	}

	// QueryMemorySize
	const JCreateParam small {4, 0};
	const JCreateParam attr {8, 1};
	int                r = query(nullptr);
	Check("jpeg QueryMemorySize(null): INVALID_ADDR", r == kJAddr, Hex(r));
	r = query(&small);
	Check("jpeg QueryMemorySize(size 4): INVALID_SIZE", r == kJSize, Hex(r));
	r = query(&attr);
	Check("jpeg QueryMemorySize(attr 1): INVALID_PARAM", r == kJParam, Hex(r));
	r = query(&ok_cp);
	Check("jpeg QueryMemorySize: 0x800", r == 0x800, Hex(r));

	// Create
	struct BadCreate {
		const char*         name;
		const JCreateParam* cp;
		void*               mem;
		uint32_t            size;
		bool                null_handle;
		int                 want;
	};
	const BadCreate bad_create[] = {
	    {"jpeg Create(null param): INVALID_ADDR", nullptr, g_jmem, 0x800, false, kJAddr},
	    {"jpeg Create(param size 4): INVALID_SIZE", &small, g_jmem, 0x800, false, kJSize},
	    {"jpeg Create(attr 1): INVALID_PARAM", &attr, g_jmem, 0x800, false, kJParam},
	    {"jpeg Create(null memory): INVALID_ADDR", &ok_cp, nullptr, 0x800, false, kJAddr},
	    {"jpeg Create(memory 0x7ff): INVALID_SIZE", &ok_cp, g_jmem, 0x7ff, false, kJSize},
	    {"jpeg Create(null handle): INVALID_ADDR", &ok_cp, g_jmem, 0x800, true, kJAddr},
	};
	for (const auto& b: bad_create) {
		void* h = reinterpret_cast<void*>(kS64);
		r       = create(b.cp, b.mem, b.size, b.null_handle ? nullptr : &h);
		Check(b.name, r == b.want && h == reinterpret_cast<void*>(kS64), Hex(r));
	}
	std::memset(g_jmem, 0, sizeof(g_jmem));
	void* h = reinterpret_cast<void*>(kS64);
	r       = create(&ok_cp, g_jmem + 3, 0x800, &h);
	Check("jpeg Create(memory + 3): 0, the handle at the first 32-byte boundary, pointing at itself",
	      r == 0 && h == g_jmem + 0x20 && *static_cast<void**>(h) == h,
	      Fmt("%s, handle memory+0x%llx", Hex(r).c_str(), static_cast<long long>(static_cast<uint8_t*>(h) - g_jmem)));

	// Delete and Encode's handle checks
	r = del(nullptr);
	Check("jpeg Delete(null): INVALID_HANDLE", r == kJHandle, Hex(r));
	r = del(g_jmem + 0x28);
	Check("jpeg Delete(off 32 bytes): INVALID_HANDLE", r == kJHandle, Hex(r));
	std::memset(g_jzero, 0, sizeof(g_jzero));
	r = del(g_jzero);
	Check("jpeg Delete(an aligned block that is not a handle): INVALID_HANDLE", r == kJHandle, Hex(r));
	JOutputInfo info {kS32, kS32};
	r = encode(nullptr, &base, &info);
	Check("jpeg Encode(null handle): INVALID_HANDLE", r == kJHandle, Hex(r));
	r = encode(g_jzero, &base, &info);
	Check("jpeg Encode(not a handle): INVALID_HANDLE", r == kJHandle, Hex(r));
	r = encode(h, nullptr, &info);
	Check("jpeg Encode(null param): INVALID_ADDR", r == kJAddr, Hex(r));

	// Encode's parameter checks
	struct Mut {
		const char* name;
		void (*apply)(JEncodeParam*);
		int want;
	};
	const Mut muts[] = {
	    {"image null: INVALID_ADDR", [](JEncodeParam* p) { p->image = nullptr; }, kJAddr},
	    {"RGBA image off 4 bytes: INVALID_ADDR", [](JEncodeParam* p) { p->image = g_img + 1; }, kJAddr},
	    {"jpeg null: INVALID_ADDR", [](JEncodeParam* p) { p->jpeg = nullptr; }, kJAddr},
	    {"image size 0: INVALID_SIZE", [](JEncodeParam* p) { p->image_size = 0; }, kJSize},
	    {"jpeg size 0: INVALID_SIZE", [](JEncodeParam* p) { p->jpeg_size = 0; }, kJSize},
	    {"width 0: INVALID_PARAM", [](JEncodeParam* p) { p->image_width = 0; }, kJParam},
	    {"height 0: INVALID_PARAM", [](JEncodeParam* p) { p->image_height = 0; }, kJParam},
	    {"width 0x10000: INVALID_PARAM", [](JEncodeParam* p) { p->image_width = 0x10000; }, kJParam},
	    {"pitch 0: INVALID_PARAM", [](JEncodeParam* p) { p->image_pitch = 0; }, kJParam},
	    {"RGBA pitch 66 (not 4-byte steps): INVALID_PARAM", [](JEncodeParam* p) { p->image_pitch = 66; }, kJParam},
	    {"pitch 0x10000000: INVALID_PARAM", [](JEncodeParam* p) { p->image_pitch = 0x10000000; }, kJParam},
	    {"height x pitch over the image size: INVALID_PARAM", [](JEncodeParam* p) { p->image_size = 16 * 64 - 1; }, kJParam},
	    {"encode mode 2: INVALID_PARAM", [](JEncodeParam* p) { p->encode_mode = 2; }, kJParam},
	    {"colour space 0: INVALID_PARAM", [](JEncodeParam* p) { p->color_space = 0; }, kJParam},
	    {"colour space 3: INVALID_PARAM", [](JEncodeParam* p) { p->color_space = 3; }, kJParam},
	    {"sampling 3: INVALID_PARAM", [](JEncodeParam* p) { p->sampling_type = 3; }, kJParam},
	    {"restart interval -2: INVALID_PARAM", [](JEncodeParam* p) { p->restart_interval = -2; }, kJParam},
	    {"restart interval 0x10000: INVALID_PARAM", [](JEncodeParam* p) { p->restart_interval = 0x10000; }, kJParam},
	    {"restart interval -1 (one MCU row): passes", [](JEncodeParam* p) { p->restart_interval = -1; }, 0},
	    {"restart interval 0xFFFF: passes", [](JEncodeParam* p) { p->restart_interval = 0xFFFF; }, 0},
	    {"RGBA pitch / 4 under the width: INVALID_PARAM", [](JEncodeParam* p) { p->image_width = 17; }, kJParam},
	    {"RGBA grayscale: INVALID_PARAM", [](JEncodeParam* p) { p->color_space = 2; }, kJParam},
	    {"RGBA 4:4:4: INVALID_PARAM", [](JEncodeParam* p) { p->sampling_type = 0; }, kJParam},
	    {"BGRA 4:2:2: passes", [](JEncodeParam* p) { p->pixel_format = 1, p->sampling_type = 1; }, 0},
	    {"Y8U8Y8V8 pitch 32 width 16: passes", [](JEncodeParam* p) { p->pixel_format = 10, p->image_pitch = 32; }, 0},
	    {"Y8U8Y8V8 pitch 32 width 17 (rounded to 18): INVALID_PARAM",
	     [](JEncodeParam* p) { p->pixel_format = 10, p->image_pitch = 32, p->image_width = 17; }, kJParam},
	    {"Y8 grayscale 4:4:4 at an odd address and pitch 17: passes",
	     [](JEncodeParam* p) {
		     p->pixel_format = 11, p->color_space = 2, p->sampling_type = 0, p->image = g_img + 1, p->image_pitch = 17;
	     },
	     0},
	    {"Y8 with YCC: INVALID_PARAM", [](JEncodeParam* p) { p->pixel_format = 11, p->sampling_type = 0, p->image_pitch = 16; },
	     kJParam},
	    {"Y8 with 4:2:0: INVALID_PARAM", [](JEncodeParam* p) { p->pixel_format = 11, p->color_space = 2, p->image_pitch = 16; },
	     kJParam},
	    {"pixel format 5: INVALID_PARAM", [](JEncodeParam* p) { p->pixel_format = 5; }, kJParam},
	    {"MJPEG mode: passes", [](JEncodeParam* p) { p->encode_mode = 1; }, 0},
	    {"the base call (RGBA 16x16 4:2:0): passes", [](JEncodeParam*) {}, 0},
	    {"64x64 RGBA at the size limit of the image buffer: passes",
	     [](JEncodeParam* p) { p->image_width = 64, p->image_height = 64, p->image_pitch = 256, p->image_size = 64 * 256; }, 0},
	};
	bool held = true;
	for (const auto& m: muts) {
		JEncodeParam p = base;
		m.apply(&p);
		info = {kS32, kS32};
		std::memset(g_jpg, 0xA5, sizeof(g_jpg));
		r = encode(h, &p, &info);
		if (m.want == 0) {
			held = held && info.size == kS32 && info.height == kS32 && AllBytes(g_jpg, sizeof(g_jpg), 0xA5);
		}
		Check((std::string("jpeg Encode ") + m.name).c_str(), r == m.want, Hex(r));
	}
	Check("jpeg Encode that passes the checks (held): 0, the JPEG buffer and the output info not written", held,
	      held ? "nothing written" : "written");

	// Delete
	r = del(h);
	Check("jpeg Delete: 0, the handle cleared", r == 0 && h == g_jmem + 0x20 && *static_cast<void**>(h) == nullptr,
	      Hex(r));
	r = del(h);
	Check("jpeg Delete again: INVALID_HANDLE", r == kJHandle, Hex(r));
	r = encode(h, &base, &info);
	Check("jpeg Encode after Delete: INVALID_HANDLE", r == kJHandle, Hex(r));
}

// =====================================================================================================================
// Ime
// =====================================================================================================================
using IForm  = int(KYTY_SYSV_ABI*)(void*);
using INoArg = int(KYTY_SYSV_ABI*)();

constexpr int kINotOpened   = static_cast<int>(0x80bc0002u);
constexpr int kIInvalidAddr = static_cast<int>(0x80bc0031u);
constexpr int kIInternal    = static_cast<int>(0x80bc00ffu);

struct PForm { // libs/imeDialog.h's PositionAndForm
	uint32_t type;
	float    posx;
	float    posy;
	uint32_t horizontal_alignment;
	uint32_t vertical_alignment;
	uint32_t width;
	uint32_t height;
};
static_assert(sizeof(PForm) == 0x1c);

const char* const kImeLive[] = {"TmVP8LzcFcY", "ziPDcIjO0Vk", "RPydv-Jr1bc", "WmYDzdC4EHI",
                                "WLxUN2WMim8", "ieCNrVrzKd4", "TXYHFRuL8UY"};
const char* const kImeHeld[] = {
    "mN+ZoSN-8hQ", "uTW+63goeJs", "Lf3DeGWC6xg", "zHuMUGb-AQI", "OTb0Mg+1i1k", "Ho5NVQzpKHo", "P5dPeiLwm-M", "tKLmVIUkpyM",
    "NYDsL9a0oEo", "l01GKoyiQrY", "E2OcGgi-FPY", "JAiMBkOTYKI", "JoPdCUXOzMU", "FuEl46uHDyo", "E+f1n8e8DAw", "evjOsE18yuI",
    "oYkJlMK51SA", "3Hx2Uw9xnv8", "16UI54cWRQk", "TQaogSaqkEk", "oOwl47ouxoM", "gtoTsGM9vEY", "wTKF4mUlSew", "rM-1hkuOhh0",
    "42xMaQ+GLeQ", "ZmmV6iukhyo", "EQBusz6Uhp8", "LBicRa-hj3A", "-IAOwd2nO7g", "qDagOjvJdNk", "tNOlmxee-Nk", "rASXozKkQ9g",
    "idvMaIu5H+k", "ga5GOgThbjo", "RuSca8rS6yA", "J7COZrgSFRA", "WqAayyok5p0", "O7Fdd+Oc-qQ", "fwcPR7+7Rks"};
static_assert(sizeof(kImeHeld) / sizeof(kImeHeld[0]) == 39);

alignas(16) uint8_t g_ime_work[Libs::Ime::WORK_BUFFER_SIZE];
char16_t g_ime_text[2048 + 0x80];

void KYTY_SYSV_ABI ImeHandler(void* /*arg*/, const Libs::Ime::Event* /*event*/) {}

bool OpenPanel(Libs::Ime::Type type, uint32_t option, float x, float y, uint32_t h, uint32_t v) {
	Libs::Ime::Param p {};
	Libs::Ime::ImeParamInit(&p);
	p.user_id              = 1;
	p.type                 = type;
	p.option               = option;
	p.max_text_length      = 16;
	p.input_text_buffer    = g_ime_text;
	p.posx                 = x;
	p.posy                 = y;
	p.horizontal_alignment = static_cast<Libs::Ime::Alignment>(h);
	p.vertical_alignment   = static_cast<Libs::Ime::Alignment>(v);
	p.work                 = g_ime_work;
	p.handler              = ImeHandler;
	std::memset(g_ime_text, 0, sizeof(g_ime_text));
	const int r = Libs::Ime::ImeOpen(&p, nullptr);
	if (r != 0) {
		Check("ime setup: the live ImeOpen", false, Hex(r));
		return false;
	}
	return true;
}

std::string FormText(const PForm& f) {
	return Fmt("type %u, (%g, %g), alignments %u %u, %ux%u", f.type, static_cast<double>(f.posx), static_cast<double>(f.posy),
	           f.horizontal_alignment, f.vertical_alignment, f.width, f.height);
}

bool Untouched(const PForm& f) {
	return AllBytes(reinterpret_cast<const uint8_t*>(&f), sizeof(f), 0xA5);
}

void CaseIme() {
	g_case            = "ime";
	const char* lib   = "libSceIme";
	const bool  panel = (g_ime & 1u) != 0;
	const bool  test  = (g_ime & 2u) != 0;

	// registration
	int dead_n = 0;
	for (const char* n: kImeHeld) {
		dead_n += Addr(g_dead_ime, n, lib) != 0 ? 1 : 0;
	}
	dead_n += Addr(g_dead_ime, "T6FYjZXG93o", lib) != 0 ? 1 : 0;
	dead_n += Addr(g_dead_ime, "wVkehxutK-U", lib) != 0 ? 1 : 0;
	int dead_live = 0;
	for (const char* n: kImeLive) {
		dead_live += Addr(g_dead_ime, n, lib) != 0 ? 1 : 0;
	}
	Check("ime registration: 41 NIDs, none of the 7 the live Ime table registers", dead_n == 41 && dead_live == 0,
	      Fmt("%d + %d of the 7 shared", dead_n, dead_live));
	// ime.cpp's functions for kImeLive, in its order
	const uint64_t ime_cpp[] = {
	    reinterpret_cast<uint64_t>(Libs::Ime::ImeClose),     reinterpret_cast<uint64_t>(Libs::Ime::ImeGetPanelSize),
	    reinterpret_cast<uint64_t>(Libs::Ime::ImeOpen),      reinterpret_cast<uint64_t>(Libs::Ime::ImeParamInit),
	    reinterpret_cast<uint64_t>(Libs::Ime::ImeSetCaret),  reinterpret_cast<uint64_t>(Libs::Ime::ImeSetText),
	    reinterpret_cast<uint64_t>(Libs::Ime::ImeSetTextGeometry)};
	int exact_live = 0;
	int nid_live   = 0;
	for (size_t i = 0; i < 7; i++) {
		const char* n = kImeLive[i];
		exact_live += (Addr(g_live_ime, n, lib) == ime_cpp[i] && Addr(g_all, n, lib) == ime_cpp[i]) ? 1 : 0;
		const auto* fb = g_all.FindByNid(n, Loader::SymbolType::Func);
		nid_live += (fb != nullptr && fb->vaddr == ime_cpp[i]) ? 1 : 0;
	}
	Check("ime the 7 shared NIDs by Find (exact key): ime.cpp's functions", exact_live == 7, Fmt("%d of 7", exact_live));
	Check("ime the 7 shared NIDs by FindByNid (the loader's NID-only fallback): ime.cpp's functions", nid_live == 7,
	      Fmt("%d of 7", nid_live));
	int same = 0;
	for (const char* n: kImeHeld) {
		const uint64_t dv = Addr(g_dead_ime, n, lib);
		same += (dv != 0 && Addr(g_all, n, lib) == dv) ? 1 : 0;
	}
	Check("ime the 39 held NIDs resolve to this table", same == 39, Fmt("%d of 39", same));

	// GetPanelPositionAndForm
	auto  form = Fn<IForm>("T6FYjZXG93o", lib);
	PForm f {};
	std::memset(&f, 0xA5, sizeof(f));
	int r = form(&f);
	Check(panel ? "ime GetPanelPositionAndForm with no panel: NOT_OPENED, nothing written"
	            : "ime off: GetPanelPositionAndForm with no panel: 0, nothing written",
	      r == (panel ? kINotOpened : 0) && Untouched(f), Hex(r));
	r = form(nullptr);
	Check(panel ? "ime GetPanelPositionAndForm(null) with no panel: NOT_OPENED (checked first)"
	            : "ime off: GetPanelPositionAndForm(null): 0",
	      r == (panel ? kINotOpened : 0), Hex(r));
	if (OpenPanel(Libs::Ime::Type::Default, 0, 100.5f, 200.25f, 1, 2)) {
		std::memset(&f, 0xA5, sizeof(f));
		r = form(&f);
		if (panel) {
			Check("ime GetPanelPositionAndForm with a Default panel: 0, its type, position, alignments and 793x408",
			      r == 0 && f.type == 0 && f.posx == 100.5f && f.posy == 200.25f && f.horizontal_alignment == 1 &&
			          f.vertical_alignment == 2 && f.width == 793 && f.height == 408,
			      Hex(r) + ", " + FormText(f));
		} else {
			Check("ime off: GetPanelPositionAndForm with a panel open: 0, nothing written", r == 0 && Untouched(f), Hex(r));
		}
		r = form(nullptr);
		Check(panel ? "ime GetPanelPositionAndForm(null) with a panel: INVALID_ADDRESS"
		            : "ime off: GetPanelPositionAndForm(null) with a panel: 0",
		      r == (panel ? kIInvalidAddr : 0), Hex(r));
		r = Libs::Ime::ImeClose();
		Check("ime setup: the live ImeClose", r == 0, Hex(r));
	}
	if (OpenPanel(Libs::Ime::Type::Number, 0x4000, 3000.0f, 2000.0f, 0, 0)) {
		std::memset(&f, 0xA5, sizeof(f));
		r = form(&f);
		if (panel) {
			Check("ime GetPanelPositionAndForm with a Number panel over 2K: 0, type 4, (3000, 2000), 740x804",
			      r == 0 && f.type == 4 && f.posx == 3000.0f && f.posy == 2000.0f && f.horizontal_alignment == 0 &&
			          f.vertical_alignment == 0 && f.width == 740 && f.height == 804,
			      Hex(r) + ", " + FormText(f));
		} else {
			Check("ime off: GetPanelPositionAndForm with a Number panel: 0, nothing written", r == 0 && Untouched(f), Hex(r));
		}
		r = Libs::Ime::ImeClose();
		Check("ime setup: the live ImeClose", r == 0, Hex(r));
	}
	std::memset(&f, 0xA5, sizeof(f));
	r = form(&f);
	Check(panel ? "ime GetPanelPositionAndForm after Close: NOT_OPENED, nothing written"
	            : "ime off: GetPanelPositionAndForm after Close: 0, nothing written",
	      r == (panel ? kINotOpened : 0) && Untouched(f), Hex(r));

	// ForTestFunction
	auto      for_test = Fn<INoArg>("wVkehxutK-U", lib);
	const int t1       = for_test();
	const int t2       = for_test();
	Check(test ? "ime ForTestFunction: 0x80bc00ff, twice" : "ime off: ForTestFunction: 0", t1 == (test ? kIInternal : 0) && t2 == t1,
	      Hex(t1) + " " + Hex(t2));

	// the held stubs
	int         zero  = 0;
	std::string wrong;
	for (const char* n: kImeHeld) {
		const int v = Fn<INoArg>(n, lib)();
		if (v == 0) {
			zero++;
		} else {
			wrong += Fmt(" %s=%s", n, Hex(v).c_str());
		}
	}
	Check("ime the 39 held stubs: 0 (today's answer)", zero == 39, Fmt("%d of 39%s", zero, wrong.c_str()));
}

} // namespace tbc0405

int main(int argc, char** argv) {
	using namespace tbc0405;
	g_zlib                 = EnvOn("KYTY_BC5_LOAD_ZLIB");
	g_jpeg                 = EnvOn("KYTY_BC5_LOAD_JPEG");
	g_ime                  = ImeItems();
	const bool  all_on     = g_zlib && g_jpeg && g_ime == 3u;
	const bool  all_off    = !g_zlib && !g_jpeg && g_ime == 0u;
	const char* mode       = all_on ? "on" : all_off ? "off" : "mixed";
	if (argc > 2 || (argc == 2 && std::strcmp(argv[1], mode) != 0)) {
		std::printf("tbc0405: the argument says %s but the switches say %s (zlib %d, jpeg %d, ime 0x%x)\n",
		            argc == 2 ? argv[1] : "too much", mode, g_zlib, g_jpeg, g_ime);
		return 2;
	}
	std::printf("tbc0405: switches zlib %d, jpeg %d, ime 0x%x (panel 1, test 2): %s\n", g_zlib, g_jpeg, g_ime, mode);
	std::fflush(stdout);
	std::thread(Watchdog).detach();

	g_case = "registration";
	Libs::LibZlib::InitZlib_1(&g_all); // each prints its "[bc5] exp 0405: ..." line on stderr
	Libs::LibJpeg::InitJpeg_1(&g_all);
	Libs::LibIme::InitIme_1(&g_all);
	Libs::Ime::InitPlatform_1_Ime(&g_all);
	Libs::LibIme::InitIme_1(&g_dead_ime);
	Libs::Ime::InitPlatform_1_Ime(&g_live_ime);

	CaseZlib();
	CaseJpeg();
	CaseIme();

	const int n = g_cases.load();
	const int p = g_passed.load();
	if (p != n) {
		std::printf("tbc0405: %s %d of %d passed; FAIL\n", mode, p, n);
		std::fflush(stdout);
		std::_Exit(1);
	}
	std::printf("tbc0405: %s %d of %d; end\n", mode, p, n);
	std::fflush(stdout);
	std::_Exit(0);
}
