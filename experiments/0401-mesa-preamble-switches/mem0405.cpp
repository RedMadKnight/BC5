// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0401 series e5, tag mem: the CPU test of mkmem0405.py's src/kernel/memory.cpp, exp 0405's R3 memory
// ports. It initialises the host's memory subsystem (core, threads, config, log, memory, as amm0401.cpp and KytyPlus's
// tests/VirtualMemoryAllocationTests.cpp do) and calls the real memory functions (kernel/memory.h) on real host memory:
// the guest address space, the direct-memory memfd, the flexible pool. No game, GPU, window, sound or network.
// Each switch is read from the environment with the unit's rule (set, non-empty, not "0") and its case runs on or off:
//   1 BC5_R3_MPROTECT_GAPS (M1)  [A][gap][B]: mprotect 0 and 3 change A and B (range table and host view), the gap
//                                stays unmapped and PROT_NONE; a wholly unmapped range and one starting in the gap give
//                                0; mtypeprotect too; a reserved range records the protection, the host stays PROT_NONE;
//                                an overflowing range gives EINVAL; a batch protect from the gap gives EINVAL, from A 0.
//                                off: mprotect over A alone as today; the gap, overflow and batch-gap calls EXIT today
//                                and are skipped.
//   2 BC5_R3_NULL_ARGS (M21)     on: QueryMemoryProtection(NULL) EACCES, MapNamedFlexibleMemory(NULL) and
//                                MapFlexibleMemory(NULL) EINVAL, the flexible budget unchanged. off: both EXIT today,
//                                skipped; an unmapped non-NULL address gives EACCES (today) in both modes.
//   3 BC5_R3_RELEASE_HOLES (M3)  [allocated][free][allocated], A mapped: the checked release gives ENOENT and frees
//                                nothing (both); the unchecked one gives 0 and on frees both parts and A's mapping;
//                                off frees nothing (today).
//   4 BC5_R3_MUNMAP_HOLES (M7)   flexible [A][gap][B]: on, munmap over all gives 0, A and B go, the budget comes back,
//                                munmap of nothing gives 0; off, both give EACCES and A and B stay (today). munmap(NULL)
//                                gives EACCES in both modes.
//   5 BC5_R3_FLEX_HINT (M6)      a non-fixed flexible map hinted at a reservation: on, it lands there; off, after it
//                                (today). A hint over a partly unreserved range stays a hint in both modes.
//   6 BC5_R3_DMQ_END (M20)       DirectMemoryQuery find-next past the last block: on EACCES; off OK with the terminal
//                                record [size, size) (today).
//   7 BC5_R3_EXEC_EINVAL (M26)   MapDirectMemory with CPU execute: on EINVAL, off EACCES (today); nothing mapped.
//   8 BC5_R3_QUERY_SIZE (M30)    VirtualQuery with 0x50 and DirectMemoryQuery with 32: on OK, only the struct written;
//                                off EINVAL (today). The exact size works and a smaller one is EINVAL in both modes.
// It prints one line per case and per skipped EXIT path, then exactly "mem0405: on N of N; end" (all eight on),
// "mem0405: off N of N; end" (all off or unset) or "mem0405: mixed <items on> N of N; end"; without "; end" something
// failed. Exit 0 only after the end line. A watchdog ends a hang after 60 s with a FAIL line (exit 3).
// Build: the compile command of src/kernel/memory.cpp with this file as the source (build0401.py --gate mem0405.cpp
// <out> --like src/kernel/memory.cpp), linked with every emulator object but main.cpp.o, the private memory.cpp.o
// (mkmem0405.py's output) in place of the shared one. Linux only (it reads /proc/self/maps for the host view).
// usage: BC5_R3_MPROTECT_GAPS=1 BC5_R3_NULL_ARGS=1 ... mem0405 on      (each =0 or unset: mem0405 off;
//        no argument: each switch as the environment sets it)

#include "common/abi.h"
#include "common/commonSubsystem.h"
#include "common/emulatorConfig.h"
#include "common/logging/log.h"
#include "common/subsystems.h"
#include "common/threads.h"
#include "kernel/memory.h"
#include "libs/errno.h"

#include <atomic>
#include <chrono>
#include <cinttypes>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <thread>

namespace mem0405 {

namespace M = Libs::LibKernel::Memory;

constexpr uint64_t P       = 0x4000;
constexpr int      OK_     = 0;
constexpr int      EINVAL_ = Libs::LibKernel::KERNEL_ERROR_EINVAL;
constexpr int      EACCES_ = Libs::LibKernel::KERNEL_ERROR_EACCES;
constexpr int      ENOENT_ = Libs::LibKernel::KERNEL_ERROR_ENOENT;
constexpr int      FIXED   = 0x10;

enum Item { MPROTECT_GAPS, NULL_ARGS, RELEASE_HOLES, MUNMAP_HOLES, FLEX_HINT, DMQ_END, EXEC_EINVAL, QUERY_SIZE, ITEMS };
static const char* const kNames[ITEMS] = {"BC5_R3_MPROTECT_GAPS", "BC5_R3_NULL_ARGS", "BC5_R3_RELEASE_HOLES",
                                          "BC5_R3_MUNMAP_HOLES",  "BC5_R3_FLEX_HINT", "BC5_R3_DMQ_END",
                                          "BC5_R3_EXEC_EINVAL",   "BC5_R3_QUERY_SIZE"};
static bool g_on[ITEMS] = {};

static std::atomic<const char*> g_case {"init"};
static int                      g_cases  = 0;
static int                      g_passed = 0;
static int                      g_fails  = 0; // failed checks in the current case
static std::string              g_first;      // the first failed check of the current case
static int64_t                  g_dm = 0;     // direct memory size

static bool SwitchOn(const char* name) {
	const char* e = std::getenv(name);
	return e != nullptr && e[0] != 0 && std::strcmp(e, "0") != 0;
}

static void Check(bool ok, const char* what, int line) {
	if (!ok) {
		if (g_fails++ == 0) {
			char buf[512];
			std::snprintf(buf, sizeof(buf), "line %d: %s", line, what);
			g_first = buf;
		}
	}
}
#define CHECK(cond) Check((cond), #cond, __LINE__)

static void Begin(const char* name) {
	g_case  = name;
	g_fails = 0;
	g_first.clear();
}

static void End(const char* name, Item item, const char* info) {
	g_cases++;
	const bool ok = (g_fails == 0);
	if (ok) {
		g_passed++;
	}
	std::printf("mem0405: case %d %s [%s %s]: %s (%s)%s%s\n", g_cases, name, kNames[item], g_on[item] ? "on" : "off",
	            ok ? "ok" : "FAIL", info, ok ? "" : "; first failed check: ", ok ? "" : g_first.c_str());
	std::fflush(stdout);
}

static void Skip(Item item, const char* what) {
	std::printf("mem0405: skip [%s off]: %s: today's code EXITs the process, not run\n", kNames[item], what);
	std::fflush(stdout);
}

// ---- helpers over the real functions ---------------------------------------------------------------------------------
static int Prot(uint64_t va, int* prot = nullptr) {
	void* s = nullptr;
	void* e = nullptr;
	int   p = -1;
	const int r = M::KernelQueryMemoryProtection(reinterpret_cast<void*>(va), &s, &e, &p);
	if (prot != nullptr) {
		*prot = p;
	}
	return r;
}

static int ProtOf(uint64_t va) {
	int p = -1;
	return Prot(va, &p) == OK_ ? p : -100;
}

// The host's view of the page at va: the permission column of /proc/self/maps ("rw-s", "---p", ...); "" if unmapped.
static std::string HostPerms(uint64_t va) {
	FILE* f = std::fopen("/proc/self/maps", "r");
	if (f == nullptr) {
		return "?";
	}
	char        line[512];
	std::string out;
	while (std::fgets(line, sizeof(line), f) != nullptr) {
		unsigned long long lo = 0;
		unsigned long long hi = 0;
		char               perms[8] = {};
		if (std::sscanf(line, "%llx-%llx %7s", &lo, &hi, perms) == 3 && va >= lo && va < hi) {
			out = perms;
			break;
		}
	}
	std::fclose(f);
	return out;
}
static bool HostNone(uint64_t va) {
	return HostPerms(va).rfind("---", 0) == 0;
}
static bool HostRw(uint64_t va) {
	return HostPerms(va).rfind("rw", 0) == 0;
}

static uint64_t Reserve(uint64_t pages) {
	void*     a = nullptr;
	const int r = M::KernelReserveVirtualRange(&a, pages * P, 0, 0);
	return r == OK_ ? reinterpret_cast<uint64_t>(a) : 0;
}

static int64_t Alloc(uint64_t pages) {
	int64_t   p = -1;
	const int r = M::KernelAllocateDirectMemory(0, g_dm, pages * P, 0, 0, &p);
	return r == OK_ ? p : -1;
}

static int MapDirect(uint64_t va, int64_t phys, uint64_t len, int prot) {
	void*     a = reinterpret_cast<void*>(va);
	const int r = M::KernelMapDirectMemory(&a, len, prot, FIXED, phys, 0);
	return (r == OK_ && reinterpret_cast<uint64_t>(a) != va) ? -1 : r;
}

static int MapFlex(uint64_t va, uint64_t len, int prot) {
	void*     a = reinterpret_cast<void*>(va);
	const int r = M::KernelMapNamedFlexibleMemory(&a, len, prot, FIXED, "mem0405");
	return (r == OK_ && reinterpret_cast<uint64_t>(a) != va) ? -1 : r;
}

struct DmqInfo {
	int64_t start;
	int64_t end;
	int     memory_type;
};
static_assert(sizeof(DmqInfo) == 24);

static int Dmq(int64_t offset, int flags, DmqInfo* q = nullptr) {
	DmqInfo local {};
	return M::KernelDirectMemoryQuery(offset, flags, q != nullptr ? q : &local, sizeof(DmqInfo));
}

static size_t FlexAvailable() {
	size_t s = 0;
	return M::KernelAvailableFlexibleMemorySize(&s) == OK_ ? s : SIZE_MAX;
}

// [A direct][gap][B direct], CPU read/write: three reserved pages, A and B mapped, the middle reservation removed.
struct Gap {
	uint64_t va   = 0;
	int64_t  phys = -1;
};
static bool MakeGap(Gap* g) {
	g->va   = Reserve(3);
	g->phys = Alloc(2);
	if (g->va == 0 || g->phys < 0) {
		return false;
	}
	return MapDirect(g->va, g->phys, P, 3) == OK_ && MapDirect(g->va + 2 * P, g->phys + static_cast<int64_t>(P), P, 3) == OK_ &&
	       M::KernelMunmap(g->va + P, P) == OK_ && Prot(g->va + P) == EACCES_ && ProtOf(g->va) == 3 &&
	       ProtOf(g->va + 2 * P) == 3;
}
static void FreeGap(const Gap& g) {
	CHECK(M::KernelMunmap(g.va, P) == OK_);
	CHECK(M::KernelMunmap(g.va + 2 * P, P) == OK_);
	CHECK(M::KernelReleaseDirectMemory(g.phys, 2 * P) == OK_);
	CHECK(Dmq(g.phys, 0) == EACCES_);
}

// ---- 1 M1 ------------------------------------------------------------------------------------------------------------
static void CaseMprotectGaps() {
	const char* name = "mprotect over gaps";
	Begin(name);
	Gap g;
	CHECK(MakeGap(&g));
	const uint64_t a = g.va, gap = g.va + P, b = g.va + 2 * P;
	if (g_on[MPROTECT_GAPS]) {
		CHECK(M::KernelMprotect(reinterpret_cast<void*>(a), 3 * P, 0) == OK_);
		CHECK(ProtOf(a) == 0 && ProtOf(b) == 0 && Prot(gap) == EACCES_);
		CHECK(HostNone(a) && HostNone(b) && HostNone(gap));
		CHECK(M::KernelMprotect(reinterpret_cast<void*>(a), 3 * P, 3) == OK_);
		CHECK(ProtOf(a) == 3 && ProtOf(b) == 3 && Prot(gap) == EACCES_);
		CHECK(HostRw(a) && HostRw(b) && HostNone(gap)); // the gap's placeholder is not made accessible
		// wholly unmapped
		CHECK(M::KernelMprotect(reinterpret_cast<void*>(gap), P, 1) == OK_);
		CHECK(Prot(gap) == EACCES_ && ProtOf(a) == 3 && ProtOf(b) == 3 && HostNone(gap));
		// starting in the gap
		CHECK(M::KernelMprotect(reinterpret_cast<void*>(gap), 2 * P, 1) == OK_);
		CHECK(ProtOf(b) == 1 && ProtOf(a) == 3 && Prot(gap) == EACCES_);
		// an unaligned start inside A covers A's page only
		CHECK(M::KernelMprotect(reinterpret_cast<void*>(a + 0x100), 0x100, 1) == OK_);
		CHECK(ProtOf(a) == 1);
		// mtypeprotect over the gap
		CHECK(M::KernelMtypeprotect(reinterpret_cast<void*>(a), 3 * P, 0, 3) == OK_);
		CHECK(ProtOf(a) == 3 && ProtOf(b) == 3 && Prot(gap) == EACCES_);
		// overflowing ranges
		CHECK(M::KernelMprotect(reinterpret_cast<void*>(0xFFFFFFFFFFFFC000ull), 0x8000, 3) == EINVAL_);
		CHECK(M::KernelMprotect(reinterpret_cast<void*>(0x4000ull), SIZE_MAX - 0x10, 3) == EINVAL_);
		// a reserved range: the table records it, the host stays PROT_NONE
		const uint64_t r = Reserve(1);
		CHECK(r != 0);
		CHECK(M::KernelMprotect(reinterpret_cast<void*>(r), P, 3) == OK_);
		CHECK(ProtOf(r) == 3 && HostNone(r));
		CHECK(M::KernelMunmap(r, P) == OK_);
		// batch protect: an unmapped start is EINVAL (nothing done), a mapped start skips the gap
		M::KernelBatchMapEntry e {};
		int                    n = -1;
		e.start                  = reinterpret_cast<void*>(gap);
		e.length                 = 2 * P;
		e.protection             = 1;
		e.operation              = 2; // protect
		CHECK(M::KernelBatchMap2(&e, 1, &n, 0) == EINVAL_ && n == 0);
		e.operation = 4; // type protect
		CHECK(M::KernelBatchMap2(&e, 1, &n, 0) == EINVAL_ && n == 0);
		CHECK(ProtOf(b) == 3);
		e.start     = reinterpret_cast<void*>(a);
		e.length    = 3 * P;
		e.operation = 2;
		CHECK(M::KernelBatchMap2(&e, 1, &n, 0) == OK_ && n == 1);
		CHECK(ProtOf(a) == 1 && ProtOf(b) == 1 && Prot(gap) == EACCES_);
		CHECK(M::KernelMprotect(reinterpret_cast<void*>(a), 3 * P, 3) == OK_);
	} else {
		// today's path over a fully mapped range
		CHECK(M::KernelMprotect(reinterpret_cast<void*>(a), P, 0) == OK_);
		CHECK(ProtOf(a) == 0 && HostNone(a) && ProtOf(b) == 3);
		CHECK(M::KernelMprotect(reinterpret_cast<void*>(a), P, 3) == OK_);
		CHECK(ProtOf(a) == 3 && HostRw(a));
		CHECK(M::KernelMtypeprotect(reinterpret_cast<void*>(b), P, 0, 1) == OK_);
		CHECK(ProtOf(b) == 1);
		M::KernelBatchMapEntry e {};
		int                    n = -1;
		e.start                  = reinterpret_cast<void*>(a);
		e.length                 = P;
		e.protection             = 1;
		e.operation              = 2;
		CHECK(M::KernelBatchMap2(&e, 1, &n, 0) == OK_ && n == 1 && ProtOf(a) == 1);
		Skip(MPROTECT_GAPS, "mprotect/mtypeprotect over [A][gap][B], over the gap alone, from the gap ('not fully mapped')");
		Skip(MPROTECT_GAPS, "mprotect of an overflowing range ('range overflows' / 'not fully mapped')");
		Skip(MPROTECT_GAPS, "mprotect of a reserved range and a batch protect from the gap ('not fully mapped')");
	}
	FreeGap(g);
	End(name, MPROTECT_GAPS, g_on[MPROTECT_GAPS] ? "gaps skipped, mapped parts changed, EINVAL on overflow" : "today's path");
}

// ---- 2 M21 -----------------------------------------------------------------------------------------------------------
static void CaseNullArgs() {
	const char* name = "NULL arguments";
	Begin(name);
	Gap g;
	CHECK(MakeGap(&g));
	CHECK(Prot(g.va + P) == EACCES_); // an unmapped non-NULL address: EACCES today
	CHECK(Prot(g.va) == OK_);
	if (g_on[NULL_ARGS]) {
		void*        s     = reinterpret_cast<void*>(1);
		void*        e     = reinterpret_cast<void*>(1);
		int          p     = 77;
		const size_t avail = FlexAvailable();
		CHECK(M::KernelQueryMemoryProtection(nullptr, &s, &e, &p) == EACCES_);
		CHECK(s == reinterpret_cast<void*>(1) && e == reinterpret_cast<void*>(1) && p == 77);
		CHECK(M::KernelMapNamedFlexibleMemory(nullptr, P, 3, 0, "mem0405-null") == EINVAL_);
		CHECK(M::KernelMapFlexibleMemory(nullptr, P, 3, 0) == EINVAL_);
		CHECK(FlexAvailable() == avail);
	} else {
		Skip(NULL_ARGS, "sceKernelQueryMemoryProtection(NULL) (EXIT_NOT_IMPLEMENTED)");
		Skip(NULL_ARGS, "sceKernelMapNamedFlexibleMemory(NULL, ...) (EXIT_NOT_IMPLEMENTED)");
	}
	FreeGap(g);
	End(name, NULL_ARGS, g_on[NULL_ARGS] ? "EACCES and EINVAL" : "non-NULL paths only");
}

// ---- 3 M3 ------------------------------------------------------------------------------------------------------------
static void CaseReleaseHoles() {
	const char* name = "unchecked release over free gaps";
	Begin(name);
	const int64_t p = Alloc(3);
	CHECK(p >= 0);
	const int64_t pp = static_cast<int64_t>(P);
	CHECK(M::KernelReleaseDirectMemory(p + pp, P) == OK_); // [allocated][free][allocated]
	CHECK(Dmq(p, 0) == OK_ && Dmq(p + pp, 0) == EACCES_ && Dmq(p + 2 * pp, 0) == OK_);
	const uint64_t v = Reserve(1);
	CHECK(v != 0 && MapDirect(v, p, P, 3) == OK_);
	CHECK(M::KernelCheckedReleaseDirectMemory(p, 3 * P) == ENOENT_); // the checked form: unchanged
	CHECK(Dmq(p, 0) == OK_ && Dmq(p + 2 * pp, 0) == OK_ && ProtOf(v) == 3);
	CHECK(M::KernelReleaseDirectMemory(p, 3 * P) == OK_); // OK in both modes
	if (g_on[RELEASE_HOLES]) {
		CHECK(Dmq(p, 0) == EACCES_ && Dmq(p + pp, 0) == EACCES_ && Dmq(p + 2 * pp, 0) == EACCES_);
		CHECK(Prot(v) == EACCES_ && HostNone(v)); // A's mapping went with it
	} else {
		CHECK(Dmq(p, 0) == OK_ && Dmq(p + 2 * pp, 0) == OK_ && ProtOf(v) == 3); // today: nothing freed
		CHECK(M::KernelMunmap(v, P) == OK_);
		CHECK(M::KernelReleaseDirectMemory(p, P) == OK_);
		CHECK(M::KernelReleaseDirectMemory(p + 2 * pp, P) == OK_);
		CHECK(Dmq(p, 0) == EACCES_ && Dmq(p + 2 * pp, 0) == EACCES_);
	}
	End(name, RELEASE_HOLES, g_on[RELEASE_HOLES] ? "both parts and the mapping freed" : "nothing freed, as today");
}

// ---- 4 M7 ------------------------------------------------------------------------------------------------------------
static void CaseMunmapHoles() {
	const char* name = "munmap over holes";
	Begin(name);
	const size_t   avail = FlexAvailable();
	const uint64_t base  = Reserve(3);
	CHECK(base != 0);
	CHECK(MapFlex(base, P, 3) == OK_ && MapFlex(base + 2 * P, P, 3) == OK_);
	CHECK(M::KernelMunmap(base + P, P) == OK_); // the middle reservation goes: [A][gap][B]
	CHECK(ProtOf(base) == 3 && Prot(base + P) == EACCES_ && ProtOf(base + 2 * P) == 3);
	CHECK(FlexAvailable() == avail - 2 * P);
	CHECK(M::KernelMunmap(0, P) == EACCES_); // NULL keeps today's EACCES
	if (g_on[MUNMAP_HOLES]) {
		CHECK(M::KernelMunmap(base, 3 * P) == OK_);
		CHECK(Prot(base) == EACCES_ && Prot(base + 2 * P) == EACCES_);
		CHECK(HostNone(base) && HostNone(base + 2 * P));
		CHECK(FlexAvailable() == avail);
		CHECK(M::KernelMunmap(base, 3 * P) == OK_); // nothing mapped
	} else {
		CHECK(M::KernelMunmap(base, 3 * P) == EACCES_); // today
		CHECK(ProtOf(base) == 3 && ProtOf(base + 2 * P) == 3);
		CHECK(M::KernelMunmap(base + P, P) == EACCES_); // nothing mapped: today
		CHECK(M::KernelMunmap(base, P) == OK_ && M::KernelMunmap(base + 2 * P, P) == OK_);
		CHECK(FlexAvailable() == avail);
	}
	End(name, MUNMAP_HOLES, g_on[MUNMAP_HOLES] ? "holes skipped, nothing mapped is 0" : "EACCES, as today");
}

// ---- 5 M6 ------------------------------------------------------------------------------------------------------------
static void CaseFlexHint() {
	const char* name = "flexible hint inside a reservation";
	Begin(name);
	const uint64_t r = Reserve(2);
	CHECK(r != 0);
	void* h = reinterpret_cast<void*>(r);
	CHECK(M::KernelMapNamedFlexibleMemory(&h, 2 * P, 3, 0, "mem0405-hint") == OK_);
	const auto got = reinterpret_cast<uint64_t>(h);
	alignas(8) M::VirtualQueryInfo info {};
	if (g_on[FLEX_HINT]) {
		CHECK(got == r);
		CHECK(M::KernelVirtualQuery(reinterpret_cast<void*>(r), 0, &info, sizeof(info)) == OK_);
		CHECK(info.is_flexible == 1 && info.is_committed == 1 && std::strcmp(info.name, "mem0405-hint") == 0);
		CHECK(M::KernelMunmap(r, 2 * P) == OK_);
		CHECK(Prot(r) == EACCES_);
	} else {
		CHECK(got != r && got != 0); // today: placed after the reservation
		CHECK(M::KernelVirtualQuery(reinterpret_cast<void*>(r), 0, &info, sizeof(info)) == OK_);
		CHECK(info.is_committed == 0); // still the reservation
		CHECK(M::KernelMunmap(got, 2 * P) == OK_);
		CHECK(M::KernelMunmap(r, 2 * P) == OK_);
	}
	// a hint whose range is only partly reserved ([reserved][gap]) stays a hint (both modes)
	const uint64_t r1 = Reserve(2);
	CHECK(r1 != 0 && M::KernelMunmap(r1 + P, P) == OK_ && Prot(r1 + P) == EACCES_);
	void* h1 = reinterpret_cast<void*>(r1);
	CHECK(M::KernelMapNamedFlexibleMemory(&h1, 2 * P, 3, 0, "mem0405-hint2") == OK_);
	CHECK(reinterpret_cast<uint64_t>(h1) != r1 && h1 != nullptr);
	CHECK(M::KernelMunmap(reinterpret_cast<uint64_t>(h1), 2 * P) == OK_);
	CHECK(M::KernelMunmap(r1, P) == OK_);
	End(name, FLEX_HINT, g_on[FLEX_HINT] ? "placed at the hint" : "placed after it, as today");
}

// ---- 6 M20 -----------------------------------------------------------------------------------------------------------
static void CaseDmqEnd() {
	const char* name = "DirectMemoryQuery find-next past the last block";
	Begin(name);
	const int64_t p = Alloc(1);
	CHECK(p >= 0);
	DmqInfo q {};
	CHECK(Dmq(p, 1, &q) == OK_ && q.start <= p && q.end > p); // a block is found (both)
	const int64_t off = g_dm - static_cast<int64_t>(P);
	CHECK(off > p && Dmq(off, 0) == EACCES_); // nothing allocated at the top
	q = {};
	if (g_on[DMQ_END]) {
		CHECK(Dmq(off, 1, &q) == EACCES_);
	} else {
		CHECK(Dmq(off, 1, &q) == OK_ && q.start == g_dm && q.end == g_dm && q.memory_type == 0); // today
	}
	CHECK(M::KernelReleaseDirectMemory(p, P) == OK_);
	End(name, DMQ_END, g_on[DMQ_END] ? "EACCES" : "terminal record, as today");
}

// ---- 7 M26 -----------------------------------------------------------------------------------------------------------
static void CaseExecEinval() {
	const char* name = "MapDirectMemory with execute";
	Begin(name);
	const int64_t p = Alloc(1);
	CHECK(p >= 0);
	const int expect = g_on[EXEC_EINVAL] ? EINVAL_ : EACCES_;
	for (const int prot: {7, 4, 0x35}) {
		void* a = reinterpret_cast<void*>(0x1234000ull);
		CHECK(M::KernelMapDirectMemory(&a, P, prot, 0, p, 0) == expect);
		CHECK(a == reinterpret_cast<void*>(0x1234000ull));
	}
	DmqInfo q {};
	CHECK(Dmq(p, 0, &q) == OK_); // still allocated, unmapped
	CHECK(M::KernelReleaseDirectMemory(p, P) == OK_);
	End(name, EXEC_EINVAL, g_on[EXEC_EINVAL] ? "EINVAL" : "EACCES, as today");
}

// ---- 8 M30 -----------------------------------------------------------------------------------------------------------
static void CaseQuerySize() {
	const char* name = "query info size larger than the struct";
	Begin(name);
	const uint64_t v = Reserve(1);
	const int64_t  p = Alloc(1);
	CHECK(v != 0 && p >= 0 && MapDirect(v, p, P, 3) == OK_);
	alignas(8) unsigned char buf[0x50];
	auto*                    vq = reinterpret_cast<M::VirtualQueryInfo*>(buf);
	std::memset(buf, 0xAB, sizeof(buf));
	const int r = M::KernelVirtualQuery(reinterpret_cast<void*>(v), 0, vq, sizeof(buf));
	bool tail_kept = true;
	for (size_t i = sizeof(M::VirtualQueryInfo); i < sizeof(buf); i++) {
		tail_kept = tail_kept && buf[i] == 0xAB;
	}
	if (g_on[QUERY_SIZE]) {
		CHECK(r == OK_ && vq->start == v && vq->is_direct == 1 && tail_kept);
	} else {
		CHECK(r == EINVAL_);
	}
	CHECK(M::KernelVirtualQuery(reinterpret_cast<void*>(v), 0, vq, sizeof(M::VirtualQueryInfo)) == OK_);
	CHECK(M::KernelVirtualQuery(reinterpret_cast<void*>(v), 0, vq, 0x40) == EINVAL_);
	std::memset(buf, 0xAB, sizeof(buf));
	const int d = M::KernelDirectMemoryQuery(p, 0, buf, 32);
	tail_kept   = true;
	for (size_t i = 24; i < 32; i++) {
		tail_kept = tail_kept && buf[i] == 0xAB;
	}
	if (g_on[QUERY_SIZE]) {
		CHECK(d == OK_ && reinterpret_cast<DmqInfo*>(buf)->start <= p && tail_kept);
	} else {
		CHECK(d == EINVAL_);
	}
	CHECK(M::KernelDirectMemoryQuery(p, 0, buf, 24) == OK_);
	CHECK(M::KernelDirectMemoryQuery(p, 0, buf, 16) == EINVAL_);
	CHECK(M::KernelMunmap(v, P) == OK_);
	CHECK(M::KernelReleaseDirectMemory(p, P) == OK_);
	End(name, QUERY_SIZE, g_on[QUERY_SIZE] ? "accepted, struct only" : "EINVAL, as today");
}

static void InitMemory() {
	g_case       = "init: subsystems";
	auto& list   = *Common::SubsystemsList::Instance();
	char  arg0[] = "mem0405";
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
		std::printf("mem0405: FAIL the subsystems did not start: %s: %s\n", list.GetFailName(), list.GetFailMsg());
		std::fflush(stdout);
		std::_Exit(2);
	}
}

} // namespace mem0405

int main(int argc, char** argv) {
	using namespace mem0405;
	int         on_count = 0;
	std::string items;
	for (int i = 0; i < ITEMS; i++) {
		g_on[i] = SwitchOn(kNames[i]);
		if (g_on[i]) {
			on_count++;
			items += (items.empty() ? "" : ",");
			items += kNames[i];
		}
	}
	const char* mode = on_count == ITEMS ? "on" : (on_count == 0 ? "off" : "mixed");
	if (argc > 2 || (argc == 2 && std::strcmp(argv[1], mode) != 0)) {
		std::printf("mem0405: the argument says %s but the switches say %s (%s)\n", argc == 2 ? argv[1] : "too much", mode,
		            items.empty() ? "none on" : items.c_str());
		return 2;
	}
	std::thread([] {
		std::this_thread::sleep_for(std::chrono::seconds(60));
		std::printf("mem0405: FAIL watchdog: case \"%s\" still running after 60 s\n", g_case.load());
		std::fflush(stdout);
		std::_Exit(3);
	}).detach();

	InitMemory();
	g_dm = static_cast<int64_t>(M::KernelGetDirectMemorySize());
	if (g_dm <= static_cast<int64_t>(16 * P)) {
		std::printf("mem0405: FAIL setup: direct memory size %" PRId64 "\n", g_dm);
		std::fflush(stdout);
		std::_Exit(1);
	}

	CaseMprotectGaps();
	CaseNullArgs();
	CaseReleaseHoles();
	CaseMunmapHoles();
	CaseFlexHint();
	CaseDmqEnd();
	CaseExecEinval();
	CaseQuerySize();

	const bool all = (g_passed == g_cases);
	if (std::strcmp(mode, "mixed") == 0) {
		std::printf("mem0405: mixed %s %d of %d%s\n", items.c_str(), g_passed, g_cases, all ? "; end" : "");
	} else {
		std::printf("mem0405: %s %d of %d%s\n", mode, g_passed, g_cases, all ? "; end" : "");
	}
	std::fflush(stdout);
	std::fflush(stderr);
	std::_Exit(all ? 0 : 1); // no static destructors under the memory subsystem
}
