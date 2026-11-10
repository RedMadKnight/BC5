// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0401 series e6, tag jit: the CPU test of mkjit0405.py's two units, src/kernel/memory.cpp and
// src/libs/libKernel.cpp: exp 0405 R3 M31, the JIT shared-memory calls (KYTY_BC5_JIT_SHM), and R1 520a8249a,
// sceKernelSendNotificationRequest (KYTY_BC5_FW_KERNEL, item notify). It starts the host's memory subsystem (core,
// threads, config, log, memory, as mem0405.cpp does), runs the real Libs::InitAll into a Loader::SymbolDatabase (as
// npgate0401.cpp does) and calls what the NIDs resolve to, as a title's import would. No game, GPU, window, sound or
// network. Each switch is on when set, non-empty and not "0" (the units' rule).
//   1 registration [JIT] on: the three NIDs (exp 0327's calculator, checked in mkjit0405.py) resolve, by NID and by the
//                  libkernel import key, to memory.cpp's Bc5JitArea*; off: neither finds anything (today).
//   2 close        [JIT] sceKernelClose, close (libkernel and Posix) and _close resolve to the JIT wrappers (on) or to
//                  today's functions (off); in both modes sceKernelClose(1) gives EPERM and close(1) 0, today's answers.
//   3 create       [JIT on] 4 pages, ceiling RWX: OK, a handle 0x40000 up; a second create gives another handle; size 0,
//                  0x1000 and 4 pages + 0x2000, ceiling 0x10 and no handle out give EINVAL, the handle untouched.
//   4 alias        [JIT on] an RX alias and a read alias of it: OK; RW from the RX alias EACCES; bits 0x20 and no
//                  handle out EINVAL; unknown handles EBADF.
//   5 views        [JIT on] an RW view of the area, an RX view of the RX alias, a read view of the read alias: three
//                  addresses, 16 KiB aligned, in the guest range; /proc/self/maps shows them as the memfd "bc5-jit";
//                  QueryMemoryProtection gives each view's prot and bounds; bytes written through RW read back through
//                  the RX and read views; on x86-64, code written through RW runs through RX.
//   6 map errors   [JIT on] RW and W through the RX alias, RX through the read alias: EACCES; bits 0x8 and no address:
//                  EINVAL; unknown handle: EBADF; the address untouched. A hint at an occupied address gives another
//                  address at or above it.
//   7 lifetimes    [JIT on] munmap of the RX view: OK, the range gone (EACCES), its host pages no longer the memfd; each
//                  of the four handles closed through a different resolved close entry point gives OK/0, then map and
//                  alias of it give EBADF; the RW and read views still show the bytes; munmap of both OK.
//   8 notify       [FW] on: zl7hupSO0C0 resolves to Bc5KernelSendNotificationRequest; a kind 5 request of 0xc30 bytes
//                  gives 0, a kind 0 one 0, a NULL one EFAULT; off: not registered (today).
// With KYTY_BC5_JIT_SHM off, cases 3-7 are not run (the calls are not registered; nothing else changes). It prints one
// line per case, then exactly "jit0405: on N of N; end" (both switches on), "jit0405: off N of N; end" (both off or
// unset) or "jit0405: mixed <switch on> N of N; end"; without "; end" something failed. Exit 0 only after the end line.
// A watchdog ends a hang after 60 s with a FAIL line (exit 3). An argument that disagrees with the switches exits 2.
// Build: the compile command of src/kernel/memory.cpp with this file as the source (build0401.py --gate jit0405.cpp
// <out> --like src/kernel/memory.cpp), linked with every emulator object but main.cpp.o, the private memory.cpp.o and
// libKernel.cpp.o (mkjit0405.py's outputs) in place of the shared ones. Linux only (memfd, /proc/self/maps).
// usage: KYTY_BC5_JIT_SHM=1 KYTY_BC5_FW_KERNEL=1 jit0405 on      (both =0 or unset: jit0405 off; no argument: as set)
#include "common/abi.h"
#include "common/commonSubsystem.h"
#include "common/emulatorConfig.h"
#include "common/logging/log.h"
#include "common/subsystems.h"
#include "common/threads.h"
#include "kernel/fileSystem.h"
#include "kernel/memory.h"
#include "libs/errno.h"
#include "libs/libs.h"
#include "loader/symbolDatabase.h"

#include <atomic>
#include <chrono>
#include <cinttypes>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <thread>
#include <type_traits>

namespace Libs::LibKernel::Memory { // kernel/memory.cpp (mkjit0405.py), declared as libKernel.cpp declares them
int KYTY_SYSV_ABI Bc5JitAreaCreate(const char* label, size_t bytes, int ceiling, int* handle_out);
int KYTY_SYSV_ABI Bc5JitAreaAlias(int handle, int ceiling, int* handle_out);
int KYTY_SYSV_ABI Bc5JitAreaMap(int handle, int prot, void** where);
} // namespace Libs::LibKernel::Memory

namespace jit0405 {

namespace M  = Libs::LibKernel::Memory;
namespace FS = Libs::LibKernel::FileSystem;

using CreateFn = int (KYTY_SYSV_ABI*)(const char*, size_t, int, int*);
using AliasFn  = int (KYTY_SYSV_ABI*)(int, int, int*);
using MapFn    = int (KYTY_SYSV_ABI*)(int, int, void**);
using CloseFn  = int (KYTY_SYSV_ABI*)(int);
using NotifyFn = int (KYTY_SYSV_ABI*)(int, const void*, size_t, int);
static_assert(std::is_same_v<decltype(&M::Bc5JitAreaCreate), CreateFn>);
static_assert(std::is_same_v<decltype(&M::Bc5JitAreaAlias), AliasFn>);
static_assert(std::is_same_v<decltype(&M::Bc5JitAreaMap), MapFn>);
static_assert(std::is_same_v<decltype(&FS::KernelClose), CloseFn>);

constexpr int      OK_     = 0;
constexpr int      EINVAL_ = Libs::LibKernel::KERNEL_ERROR_EINVAL;
constexpr int      EBADF_  = Libs::LibKernel::KERNEL_ERROR_EBADF;
constexpr int      EACCES_ = Libs::LibKernel::KERNEL_ERROR_EACCES;
constexpr int      EFAULT_ = Libs::LibKernel::KERNEL_ERROR_EFAULT;
constexpr int      EPERM_  = Libs::LibKernel::KERNEL_ERROR_EPERM;
constexpr int      R       = 1;
constexpr int      W       = 2;
constexpr int      X       = 4;
constexpr size_t   PAGE    = 0x4000;
constexpr size_t   AREA    = 4 * PAGE;
constexpr uint64_t GUEST_LO = 0x40000ull;      // memoryAddressSpace.inc HOST_SYSTEM_MANAGED_MIN
constexpr uint64_t GUEST_HI = 0xfc00000000ull; // memoryAddressSpace.inc HOST_USER_MAX + 1
constexpr int      FIRST_HANDLE = 0x40000;

static std::atomic<const char*> g_case {"start"};
static int                      g_cases   = 0;
static int                      g_passed  = 0;
static bool                     g_case_ok = true;
static std::string              g_why;
static Loader::SymbolDatabase*  g_db = nullptr;

static void Check(bool ok, int line, const char* what) {
	if (!ok && g_case_ok) {
		g_case_ok = false;
		g_why     = "line " + std::to_string(line) + ": " + what;
	}
}
#define CHECK(c) Check((c), __LINE__, #c)

static void Begin(const char* name) {
	g_case    = name;
	g_case_ok = true;
	g_why.clear();
	g_cases++;
}

static void End(const char* name, const char* tag, const char* detail) {
	if (g_case_ok) {
		g_passed++;
	}
	std::printf("jit0405: case %d %s [%s]: %s (%s)\n", g_cases, name, tag, g_case_ok ? "ok" : "FAIL",
	            g_case_ok ? detail : g_why.c_str());
	std::fflush(stdout);
}

static bool EnvOn(const char* name) {
	const char* v = std::getenv(name);
	return v != nullptr && v[0] != '\0' && std::strcmp(v, "0") != 0;
}

static Loader::SymbolResolve Key(const char* nid, const char* library) { // a title's import of libkernel's module
	Loader::SymbolResolve r {};
	r.name                 = nid;
	r.library              = library;
	r.library_version      = 1;
	r.module               = "libkernel";
	r.module_version_major = 1;
	r.module_version_minor = 1;
	r.type                 = Loader::SymbolType::Func;
	return r;
}

static const Loader::SymbolRecord* Rec(const char* nid, const char* library = "libkernel") {
	return g_db->Find(Key(nid, library));
}

template <typename F>
static F Fn(const char* nid, const char* library = "libkernel") {
	const auto* r = Rec(nid, library);
	return r != nullptr ? reinterpret_cast<F>(r->vaddr) : nullptr;
}

// The /proc/self/maps line of the mapping that holds addr, or "".
static std::string MapsLine(uint64_t addr) {
	FILE* f = std::fopen("/proc/self/maps", "r");
	if (f == nullptr) {
		return "";
	}
	static char line[4096];
	std::string found;
	while (std::fgets(line, sizeof(line), f) != nullptr) {
		unsigned long long lo = 0;
		unsigned long long hi = 0;
		if (std::sscanf(line, "%llx-%llx", &lo, &hi) == 2 && addr >= lo && addr < hi) {
			found = line;
			break;
		}
	}
	std::fclose(f);
	return found;
}

static bool IsJitMemfd(uint64_t addr) {
	return MapsLine(addr).find("memfd:bc5-jit") != std::string::npos;
}

static int Prot(uint64_t va, uint64_t* start, uint64_t* end) {
	void* s = nullptr;
	void* e = nullptr;
	int   p = -100;
	const int r = M::KernelQueryMemoryProtection(reinterpret_cast<void*>(va), &s, &e, &p);
	*start      = reinterpret_cast<uint64_t>(s);
	*end        = reinterpret_cast<uint64_t>(e);
	return r == OK_ ? p : r;
}

static bool ViewOk(uint64_t va) {
	return va >= GUEST_LO && va + AREA <= GUEST_HI && (va & (PAGE - 1u)) == 0;
}

static uint8_t Pattern(size_t i) {
	return static_cast<uint8_t>((i * 7u + 3u) & 0xffu);
}

static bool HasPattern(uint64_t va, size_t bytes) {
	const auto* p = reinterpret_cast<const volatile uint8_t*>(va);
	for (size_t i = 0; i < bytes; i++) {
		if (p[i] != Pattern(i)) {
			return false;
		}
	}
	return true;
}

// The calls as a title reaches them, and the state cases 3-7 share.
static CreateFn g_create = nullptr;
static AliasFn  g_alias  = nullptr;
static MapFn    g_map    = nullptr;
static int      g_h      = -1; // the area, ceiling RWX
static int      g_h2     = -1; // a second area
static int      g_a      = -1; // an alias of g_h, ceiling RX
static int      g_b      = -1; // an alias of g_a, ceiling R
static uint64_t g_rw     = 0;  // view of g_h, RW
static uint64_t g_rx     = 0;  // view of g_a, RX
static uint64_t g_ro     = 0;  // view of g_b, R

static void CaseRegistration(bool on) {
	const char* name = "registration";
	Begin(name);
	struct Entry {
		const char* nid;
		const char* dbg;
		uint64_t    addr;
	};
	const Entry three[] = {
	    {"avvJ3J0H0EY", "Memory::Bc5JitAreaCreate", reinterpret_cast<uint64_t>(&M::Bc5JitAreaCreate)},
	    {"MR221Mwo0Pc", "Memory::Bc5JitAreaAlias", reinterpret_cast<uint64_t>(&M::Bc5JitAreaAlias)},
	    {"YKT49TOLQWs", "Memory::Bc5JitAreaMap", reinterpret_cast<uint64_t>(&M::Bc5JitAreaMap)},
	};
	for (const auto& e: three) {
		const auto* by_nid = g_db->FindByNid(e.nid, Loader::SymbolType::Func);
		const auto* by_key = Rec(e.nid);
		if (on) {
			CHECK(by_nid != nullptr && by_nid->vaddr == e.addr && by_nid->dbg_name == e.dbg);
			CHECK(by_key != nullptr && by_key->vaddr == e.addr);
		} else {
			CHECK(by_nid == nullptr);
			CHECK(by_key == nullptr);
		}
	}
	if (on) {
		g_create = Fn<CreateFn>("avvJ3J0H0EY");
		g_alias  = Fn<AliasFn>("MR221Mwo0Pc");
		g_map    = Fn<MapFn>("YKT49TOLQWs");
		CHECK(g_create != nullptr && g_alias != nullptr && g_map != nullptr);
	}
	End(name, on ? "KYTY_BC5_JIT_SHM on" : "KYTY_BC5_JIT_SHM off",
	    on ? "3 NIDs resolve to Bc5JitArea*" : "the 3 NIDs are not registered, as today");
}

static void CaseClose(bool on) {
	const char* name = "close";
	Begin(name);
	struct Entry {
		const char* nid;
		const char* library;
		const char* dbg_on;
		const char* dbg_off;
		bool        sce;
	};
	const Entry four[] = {
	    {"UK2Tl2DWUns", "libkernel", "LibKernel::Bc5JitSceClose", "FileSystem::KernelClose", true},
	    {"bY-PO6JhzhQ", "libkernel", "LibKernel::Bc5JitPosixClose", "LibKernel::close", false},
	    {"bY-PO6JhzhQ", "Posix", "LibKernel::Bc5JitPosixClose", "LibKernel::close", false},
	    {"NNtFaKJbPt0", "libkernel", "LibKernel::Bc5JitPosixClose", "LibKernel::close", false},
	};
	for (const auto& e: four) {
		const auto* r = Rec(e.nid, e.library);
		CHECK(r != nullptr);
		if (r == nullptr) {
			continue;
		}
		CHECK(r->dbg_name == (on ? e.dbg_on : e.dbg_off));
		if (!on && e.sce) {
			CHECK(r->vaddr == reinterpret_cast<uint64_t>(&FS::KernelClose));
		}
		// Descriptor 1 never reaches the file table: today's answers are EPERM (sce) and 0 (posix), in both modes.
		const auto close_fn = reinterpret_cast<CloseFn>(r->vaddr);
		CHECK(close_fn(1) == (e.sce ? EPERM_ : 0));
	}
	End(name, on ? "KYTY_BC5_JIT_SHM on" : "KYTY_BC5_JIT_SHM off",
	    on ? "4 close entry points are the wrappers; close(1) answers as today" : "today's close functions");
}

static void CaseCreate() {
	const char* name = "create";
	Begin(name);
	if (g_create == nullptr) {
		CHECK(!"not resolved");
		End(name, "KYTY_BC5_JIT_SHM on", "");
		return;
	}
	CHECK(g_create("jit0405", AREA, R | W | X, &g_h) == OK_);
	CHECK(g_h >= FIRST_HANDLE);
	CHECK(g_create(nullptr, AREA, R | W | X, &g_h2) == OK_);
	CHECK(g_h2 >= FIRST_HANDLE && g_h2 != g_h);
	int h = -7;
	CHECK(g_create("x", 0, R | W | X, &h) == EINVAL_);
	CHECK(g_create("x", 0x1000, R | W | X, &h) == EINVAL_);
	CHECK(g_create("x", AREA + 0x2000, R | W | X, &h) == EINVAL_);
	CHECK(g_create("x", AREA, 0x10, &h) == EINVAL_);
	CHECK(g_create("x", AREA, R | W | X, nullptr) == EINVAL_);
	CHECK(h == -7);
	End(name, "KYTY_BC5_JIT_SHM on", "two areas, handles 0x40000 up; 5 EINVAL cases");
}

static void CaseAlias() {
	const char* name = "alias";
	Begin(name);
	if (g_alias == nullptr || g_h < 0) {
		CHECK(!"no area");
		End(name, "KYTY_BC5_JIT_SHM on", "");
		return;
	}
	CHECK(g_alias(g_h, R | X, &g_a) == OK_);
	CHECK(g_a >= FIRST_HANDLE && g_a != g_h && g_a != g_h2);
	CHECK(g_alias(g_a, R, &g_b) == OK_);
	CHECK(g_b >= FIRST_HANDLE && g_b != g_a);
	int x = -7;
	CHECK(g_alias(g_a, R | W, &x) == EACCES_);
	CHECK(g_alias(g_a, W, &x) == EACCES_); // write counts as read and write
	CHECK(g_alias(g_b, R | X, &x) == EACCES_);
	CHECK(g_alias(g_h, 0x20, &x) == EINVAL_);
	CHECK(g_alias(g_h, R, nullptr) == EINVAL_);
	CHECK(g_alias(12345, R, &x) == EBADF_);
	CHECK(g_alias(-1, R, &x) == EBADF_);
	CHECK(g_alias(0x7ffffff0, R, &x) == EBADF_);
	CHECK(x == -7);
	End(name, "KYTY_BC5_JIT_SHM on", "RX alias and its read alias; 3 EACCES, 2 EINVAL, 3 EBADF");
}

static void CaseViews() {
	const char* name = "views";
	Begin(name);
	if (g_map == nullptr || g_h < 0 || g_a < 0 || g_b < 0) {
		CHECK(!"no handles");
		End(name, "KYTY_BC5_JIT_SHM on", "");
		return;
	}
	void* p = nullptr;
	CHECK(g_map(g_h, R | W, &p) == OK_);
	g_rw = reinterpret_cast<uint64_t>(p);
	p    = nullptr;
	CHECK(g_map(g_a, R | X, &p) == OK_);
	g_rx = reinterpret_cast<uint64_t>(p);
	p    = nullptr;
	CHECK(g_map(g_b, R, &p) == OK_);
	g_ro = reinterpret_cast<uint64_t>(p);
	CHECK(ViewOk(g_rw) && ViewOk(g_rx) && ViewOk(g_ro));
	CHECK(g_rw != g_rx && g_rw != g_ro && g_rx != g_ro);
	if (!ViewOk(g_rw) || !ViewOk(g_rx) || !ViewOk(g_ro)) {
		g_rw = g_rx = g_ro = 0;
		End(name, "KYTY_BC5_JIT_SHM on", "");
		return;
	}
	CHECK(IsJitMemfd(g_rw) && IsJitMemfd(g_rx) && IsJitMemfd(g_ro));
	uint64_t s = 0;
	uint64_t e = 0;
	CHECK(Prot(g_rw, &s, &e) == (R | W) && s == g_rw && e == g_rw + AREA);
	CHECK(Prot(g_rx, &s, &e) == (R | X) && s == g_rx && e == g_rx + AREA);
	CHECK(Prot(g_ro, &s, &e) == R && s == g_ro && e == g_ro + AREA);
	auto* rw = reinterpret_cast<volatile uint8_t*>(g_rw);
	for (size_t i = 0; i < AREA; i++) {
		rw[i] = Pattern(i);
	}
	CHECK(HasPattern(g_rx, AREA));
	CHECK(HasPattern(g_ro, AREA));
#if defined(__x86_64__)
	// mov eax, 42; ret (Intel SDM vol. 2: MOV r32, imm32 is B8+rd id; RET is C3), written through RW, run through RX.
	static const uint8_t code[] = {0xb8, 0x2a, 0x00, 0x00, 0x00, 0xc3};
	std::memcpy(reinterpret_cast<void*>(g_rw + 3 * PAGE), code, sizeof(code));
	using Code = int (*)();
	CHECK(reinterpret_cast<Code>(g_rx + 3 * PAGE)() == 42);
	const char* detail = "3 views of one memfd; bytes through RW seen through RX and R; code runs through RX";
#else
	const char* detail = "3 views of one memfd; bytes through RW seen through RX and R (code run: x86-64 only)";
#endif
	End(name, "KYTY_BC5_JIT_SHM on", detail);
}

static void CaseMapErrors() {
	const char* name = "map errors";
	Begin(name);
	if (g_map == nullptr || g_rw == 0) {
		CHECK(!"no views");
		End(name, "KYTY_BC5_JIT_SHM on", "");
		return;
	}
	void* const sentinel = reinterpret_cast<void*>(static_cast<uintptr_t>(0x1234000));
	void*       p        = sentinel;
	CHECK(g_map(g_a, R | W, &p) == EACCES_);
	CHECK(g_map(g_a, W, &p) == EACCES_);
	CHECK(g_map(g_b, R | X, &p) == EACCES_);
	CHECK(g_map(g_h, 0x8, &p) == EINVAL_);
	CHECK(g_map(g_h, R, nullptr) == EINVAL_);
	CHECK(g_map(54321, R, &p) == EBADF_);
	CHECK(g_map(-1, R, &p) == EBADF_);
	CHECK(p == sentinel);
	void* hint = reinterpret_cast<void*>(g_rw); // occupied: a hint, not a place
	CHECK(g_map(g_h, R | W, &hint) == OK_);
	const auto at = reinterpret_cast<uint64_t>(hint);
	CHECK(at != g_rw && at >= g_rw && ViewOk(at));
	if (at != g_rw && ViewOk(at)) {
		CHECK(HasPattern(at, PAGE));
		CHECK(M::KernelMunmap(at, AREA) == OK_);
	}
	End(name, "KYTY_BC5_JIT_SHM on", "3 EACCES, 2 EINVAL, 2 EBADF, address untouched; an occupied hint maps above it");
}

static void CaseLifetimes() {
	const char* name = "lifetimes";
	Begin(name);
	if (g_map == nullptr || g_rw == 0) {
		CHECK(!"no views");
		End(name, "KYTY_BC5_JIT_SHM on", "");
		return;
	}
	uint64_t s = 0;
	uint64_t e = 0;
	CHECK(M::KernelMunmap(g_rx, AREA) == OK_);
	CHECK(Prot(g_rx, &s, &e) == EACCES_);
	CHECK(!IsJitMemfd(g_rx));
	const auto sce_close   = Fn<CloseFn>("UK2Tl2DWUns");
	const auto close_lk    = Fn<CloseFn>("bY-PO6JhzhQ");
	const auto close_posix = Fn<CloseFn>("bY-PO6JhzhQ", "Posix");
	const auto close_us    = Fn<CloseFn>("NNtFaKJbPt0");
	CHECK(sce_close != nullptr && close_lk != nullptr && close_posix != nullptr && close_us != nullptr);
	if (sce_close != nullptr && close_lk != nullptr && close_posix != nullptr && close_us != nullptr) {
		CHECK(sce_close(g_a) == OK_);
		CHECK(close_lk(g_h) == 0);
		CHECK(close_posix(g_b) == 0);
		CHECK(close_us(g_h2) == 0);
		for (const int handle: {g_a, g_h, g_b, g_h2}) {
			void* p = nullptr;
			int   x = -7;
			CHECK(g_map(handle, R, &p) == EBADF_);
			CHECK(g_alias(handle, R, &x) == EBADF_);
		}
	}
	CHECK(HasPattern(g_rw, PAGE)); // the views outlive the handles
	CHECK(HasPattern(g_ro, PAGE));
	CHECK(IsJitMemfd(g_rw) && IsJitMemfd(g_ro));
	CHECK(M::KernelMunmap(g_rw, AREA) == OK_);
	CHECK(M::KernelMunmap(g_ro, AREA) == OK_);
	CHECK(Prot(g_rw, &s, &e) == EACCES_ && Prot(g_ro, &s, &e) == EACCES_);
	End(name, "KYTY_BC5_JIT_SHM on", "munmap drops a view; 4 closes through 4 entry points; views outlive handles");
}

static void CaseNotify(bool on) {
	const char* name = "notify";
	Begin(name);
	const auto* by_nid = g_db->FindByNid("zl7hupSO0C0", Loader::SymbolType::Func);
	const auto* by_key = Rec("zl7hupSO0C0");
	if (on) {
		CHECK(by_nid != nullptr && by_nid->dbg_name == "LibKernel::Bc5KernelSendNotificationRequest");
		CHECK(by_key != nullptr && by_nid != nullptr && by_key->vaddr == by_nid->vaddr);
		if (by_key != nullptr) {
			const auto notify = reinterpret_cast<NotifyFn>(by_key->vaddr);
			static uint8_t block[0xc30];
			std::memset(block, 0, sizeof(block));
			const int32_t kind5 = 5;
			std::memcpy(block, &kind5, sizeof(kind5));
			std::strcpy(reinterpret_cast<char*>(block + 0x2d), "jit0405 notification text");
			CHECK(notify(0, block, sizeof(block), 0) == OK_);
			const int32_t kind0 = 0;
			std::memcpy(block, &kind0, sizeof(kind0));
			CHECK(notify(0, block, sizeof(block), 0) == OK_);
			CHECK(notify(0, block, 16, 0) == OK_);
			CHECK(notify(0, nullptr, sizeof(block), 0) == EFAULT_);
		}
	} else {
		CHECK(by_nid == nullptr);
		CHECK(by_key == nullptr);
	}
	End(name, on ? "KYTY_BC5_FW_KERNEL on" : "KYTY_BC5_FW_KERNEL off",
	    on ? "registered; kind 5, kind 0 and a short request 0, NULL EFAULT" : "not registered, as today");
}

static void InitMemory() {
	g_case       = "init: subsystems";
	auto& list   = *Common::SubsystemsList::Instance();
	char  arg0[] = "jit0405";
	char* argv[] = {arg0, nullptr};
	list.SetArgs(1, argv);
	auto* core    = Common::CommonSubsystem::Instance();
	auto* threads = Common::ThreadsSubsystem::Instance();
	list.Add(core, {});
	list.Add(threads, {core});
	bool  ok     = list.InitAll(false);
	auto* config = Config::ConfigSubsystem::Instance();
	list.Add(config, {core});
	ok = ok && list.InitAll(false);
	Config::ConfigOptions options;
	options.printf_direction = Config::OutputDirection::Silent;
	Config::Load(options);
	auto* log = Log::LogSubsystem::Instance();
	list.Add(log, {core, config});
	ok = ok && list.InitAll(false);
	auto* memory = M::MemorySubsystem::Instance();
	list.Add(memory, {core, log});
	ok = ok && list.InitAll(false);
	if (!ok) {
		std::printf("jit0405: FAIL the subsystems did not start: %s: %s\n", list.GetFailName(), list.GetFailMsg());
		std::fflush(stdout);
		std::_Exit(2);
	}
}

} // namespace jit0405

int main(int argc, char** argv) {
	using namespace jit0405;
	const bool  jit_on = EnvOn("KYTY_BC5_JIT_SHM");
	const bool  fw_on  = EnvOn("KYTY_BC5_FW_KERNEL");
	const char* mode   = (jit_on && fw_on) ? "on" : (!jit_on && !fw_on ? "off" : "mixed");
	if (argc > 2 || (argc == 2 && std::strcmp(argv[1], mode) != 0)) {
		std::printf("jit0405: the argument says %s but the switches say %s (KYTY_BC5_JIT_SHM %s, KYTY_BC5_FW_KERNEL %s)\n",
		            argc == 2 ? argv[1] : "too much", mode, jit_on ? "on" : "off", fw_on ? "on" : "off");
		return 2;
	}
	std::thread([] {
		std::this_thread::sleep_for(std::chrono::seconds(60));
		std::printf("jit0405: FAIL watchdog: case \"%s\" still running after 60 s\n", g_case.load());
		std::fflush(stdout);
		std::_Exit(3);
	}).detach();

	InitMemory();
	g_case = "init: Libs::InitAll";
	static Loader::SymbolDatabase db;
	Libs::InitAll(&db);
	g_db = &db;
	// Setup check: an entry point registered in every mode resolves the way a title imports it.
	const auto* mprotect = Rec("vSMAm3cxYTY");
	if (mprotect == nullptr || mprotect->vaddr != reinterpret_cast<uint64_t>(&M::KernelMprotect)) {
		std::printf("jit0405: FAIL setup: sceKernelMprotect (vSMAm3cxYTY) does not resolve: InitAll did not run as expected\n");
		std::fflush(stdout);
		std::_Exit(1);
	}

	CaseRegistration(jit_on);
	CaseClose(jit_on);
	if (jit_on) {
		CaseCreate();
		CaseAlias();
		CaseViews();
		CaseMapErrors();
		CaseLifetimes();
	}
	CaseNotify(fw_on);

	const bool all = (g_passed == g_cases);
	if (std::strcmp(mode, "mixed") == 0) {
		std::printf("jit0405: mixed %s %d of %d%s\n", jit_on ? "KYTY_BC5_JIT_SHM" : "KYTY_BC5_FW_KERNEL", g_passed,
		            g_cases, all ? "; end" : "");
	} else {
		std::printf("jit0405: %s %d of %d%s\n", mode, g_passed, g_cases, all ? "; end" : "");
	}
	std::fflush(stdout);
	std::fflush(stderr);
	std::_Exit(all ? 0 : 1); // no static destructors under the memory subsystem
}
