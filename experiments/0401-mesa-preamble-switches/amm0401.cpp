// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0401 series e4: CPU tests of mkamm0401.py's src/libs/libAmpr.cpp, the port of AnyPS5's AMM PRT commands,
// the other AMM commands and the AMPR waits (github.com/boykopovar/AnyPS5, GPL-2.0-only, @ 4f41f4c37 with e3b5192cb,
// 79fc99774, 37881a5da; the cases follow its core/libs/tests/GuestAmpr.cpp TestAmmPrt, TestAmmRemapAndProtect and
// TestAmmPrtAllocationFailureKeepsZeros, rewritten for this host). It initialises the host's memory subsystem (as
// KytyPlus's tests/VirtualMemoryAllocationTests.cpp does), runs the host's own registration (Libs::InitAll), takes every
// function by NID from the SymbolDatabase (lesson R32: the NIDs below are checked against their names by mkamm0401.py),
// builds command buffers and runs them against real host memory: the AMM window, the AMM pool, the direct memory memfd.
// Each switch is read from the environment and its cases run on or off:
//   KYTY_BC5_AMM_PRT_CMDS   on: the 6 NIDs registered; MapAsPrt reads 0; AllocatePaForPrt backs only the unbacked runs;
//                           a forced failure (no direct memory, then a failed map) rolls the run back to the pool and to
//                           zero pages; UnmapToPrt, RemapIntoPrt, the measures, the checks; a map or unmap ends PRT.
//                           off: the 6 NIDs unregistered.
//   KYTY_BC5_AMM_EXTRA_CMDS on: the 16 NIDs; Remap, MultiMap (a pool page returns with its last mapping), ModifyProtect,
//                           ModifyMtypeProtect, the GpuMaskId forms, the measures, the refused cases. off: unregistered.
//   (both AMM switches off: today's map and unmap, and no AMM page table)
//   KYTY_BC5_AMPR_WAITS     on: the 4 NIDs; WaitOnAddress against a writer thread, with a 100-ms "still waiting" check;
//                           WaitOnCounter against a counter write from another priority; WaitOnCounter_04_00 with a mask;
//                           WriteCounter_04_00's add and WriteAddressFromCounter(Pair). off: the 4 NIDs unregistered,
//                           WriteCounterOnCompletion today's, WaitOnCounter_04_00 a no-op, WriteAddressFromCounter 0, and
//                           today's WaitOnAddress_04_00 against a writer thread.
// A watchdog ends any hang after 120 s with a FAIL line. The last line is "amm0401: on N of N; end" (all three switches
// on), "amm0401: off N of N; end" (all off) or "amm0401: mixed prt=.. extra=.. waits=.. N of N; end"; without "; end"
// something failed. Exit 0 only after the end line.
// Build: the compile command of src/libs/libAmpr.cpp with this file as the source (build0401.py --gate amm0401.cpp <out>
// --like src/libs/libAmpr.cpp), linked with every emulator object but main.cpp.o, the private libAmpr.cpp.o among them.
// usage: KYTY_BC5_AMM_PRT_CMDS=1 KYTY_BC5_AMM_EXTRA_CMDS=1 KYTY_BC5_AMPR_WAITS=1 amm0401 on
//        (each =0 or unset: amm0401 off; no argument: each switch as the environment sets it)

#include "common/abi.h"
#include "common/commonSubsystem.h"
#include "common/emulatorConfig.h"
#include "common/logging/log.h"
#include "common/subsystems.h"
#include "common/threads.h"
#include "kernel/memory.h"
#include "libs/libs.h"
#include "loader/symbolDatabase.h"

#include <atomic>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <thread>

// The test seams of mkamm0401.py's unit (always compiled in, unused by the emulator).
extern "C" void bc5_exp0401_amm_fail_backing(uint32_t n);
extern "C" void bc5_exp0401_amm_stats(uint64_t* pool_free, uint64_t* pages, uint64_t* prt_bytes);
extern "C" int  bc5_exp0401_amm_page(uint64_t va, uint64_t* dmem, int32_t* type, int32_t* prot);

namespace amm0401 {

constexpr uint64_t PAGE    = 0x4000;
constexpr int      EINVAL_ = static_cast<int>(0x80020016u);
constexpr int      EAGAIN_ = static_cast<int>(0x80020023u);

static int                      g_pass = 0;
static int                      g_total = 0;
static std::atomic<const char*> g_case {"init"};

static void Check(bool ok, const char* what, int line) {
	g_total++;
	if (ok) {
		g_pass++;
	} else {
		std::printf("amm0401: FAIL %s (line %d): %s\n", g_case.load(), line, what);
		std::fflush(stdout);
	}
}
#define CHECK(cond) Check((cond), #cond, __LINE__)

// ---- the NIDs: {"NID", "name"} pairs, each checked by mkamm0401.py with exp 0327's calculator ----
struct Nid {
	const char* nid;
	const char* name;
	const char* function; // the debug name the host's LIB_FUNC gives it when registered (new ones only)
	int         sw;       // 0 KYTY_BC5_AMM_PRT_CMDS, 1 KYTY_BC5_AMM_EXTRA_CMDS, 2 KYTY_BC5_AMPR_WAITS, -1 registered today
};
static const Nid kNids[] = {
    {"ZJCgt+aPHAU", "sceAmprAmmCommandBufferMapAsPrt", "Ampr::Bc5AmmCommandBufferMapAsPrt", 0},
    {"d3lKWPM6odc", "sceAmprAmmCommandBufferAllocatePaForPrt", "Ampr::Bc5AmmCommandBufferAllocatePaForPrt", 0},
    {"0Xo9g4goDXU", "sceAmprAmmCommandBufferRemapIntoPrt", "Ampr::Bc5AmmCommandBufferRemapIntoPrt", 0},
    {"3A2X6OCHtnA", "sceAmprAmmCommandBufferUnmapToPrt", "Ampr::Bc5AmmCommandBufferUnmapToPrt", 0},
    {"4SSJ+cn+Pvg", "sceAmprAmmMeasureAmmCommandSizeMapAsPrt", "Ampr::Bc5MeasureAmmCommandSizeMapAsPrt", 0},
    {"2yYv9QWB3hU", "sceAmprAmmMeasureAmmCommandSizeAllocatePaForPrt", "Ampr::Bc5MeasureAmmCommandSizeAllocatePaForPrt", 0},
    {"ijvRMHfwwjc", "sceAmprAmmCommandBufferRemap", "Ampr::Bc5AmmCommandBufferRemap", 1},
    {"Fo0Oaoqukg4", "sceAmprAmmCommandBufferRemapWithGpuMaskId", "Ampr::Bc5AmmCommandBufferRemapWithGpuMaskId", 1},
    {"j2C9no3P4Nw", "sceAmprAmmCommandBufferMultiMap", "Ampr::Bc5AmmCommandBufferMultiMap", 1},
    {"Qyz8VbxnaII", "sceAmprAmmCommandBufferMultiMapWithGpuMaskId", "Ampr::Bc5AmmCommandBufferMultiMapWithGpuMaskId", 1},
    {"joNORJjCFhg", "sceAmprAmmCommandBufferModifyProtect", "Ampr::Bc5AmmCommandBufferModifyProtect", 1},
    {"spjcxyNX-KE", "sceAmprAmmCommandBufferModifyProtectWithGpuMaskId", "Ampr::Bc5AmmCommandBufferModifyProtectWithGpuMaskId", 1},
    {"rKq9nG+L9Xo", "sceAmprAmmCommandBufferModifyMtypeProtect", "Ampr::Bc5AmmCommandBufferModifyMtypeProtect", 1},
    {"ie-UuLGbYXo", "sceAmprAmmCommandBufferModifyMtypeProtectWithGpuMaskId", "Ampr::Bc5AmmCommandBufferModifyMtypeProtectWithGpuMaskId", 1},
    {"8sFq5s8eHnQ", "sceAmprAmmMeasureAmmCommandSizeRemap", "Ampr::Bc5MeasureAmmCommandSizeRemap", 1},
    {"b50TWwRmzu8", "sceAmprAmmMeasureAmmCommandSizeRemapWithGpuMaskId", "Ampr::Bc5MeasureAmmCommandSizeRemapWithGpuMaskId", 1},
    {"U6PxwrRchl4", "sceAmprAmmMeasureAmmCommandSizeMultiMap", "Ampr::Bc5MeasureAmmCommandSizeRemap", 1},
    {"uGs4yyYTASM", "sceAmprAmmMeasureAmmCommandSizeMultiMapWithGpuMaskId", "Ampr::Bc5MeasureAmmCommandSizeRemapWithGpuMaskId", 1},
    {"JPQagYw-y+4", "sceAmprAmmMeasureAmmCommandSizeModifyProtect", "Ampr::Bc5MeasureAmmCommandSizeModifyProtect", 1},
    {"gdSoJ6dvztU", "sceAmprAmmMeasureAmmCommandSizeModifyProtectWithGpuMaskId", "Ampr::Bc5MeasureAmmCommandSizeModifyProtectWithGpuMaskId", 1},
    {"Ok2Nxka7qI4", "sceAmprAmmMeasureAmmCommandSizeModifyMtypeProtect", "Ampr::Bc5MeasureAmmCommandSizeModifyMtypeProtect", 1},
    {"c5D63Y35GjI", "sceAmprAmmMeasureAmmCommandSizeModifyMtypeProtectWithGpuMaskId", "Ampr::Bc5MeasureAmmCommandSizeModifyMtypeProtectWithGpuMaskId", 1},
    {"V7GQTEeUfhw", "sceAmprCommandBufferWaitOnAddress", "Ampr::Bc5CommandBufferWaitOnAddress", 2},
    {"FrCNL9TQ8ms", "sceAmprCommandBufferWaitOnCounter", "Ampr::Bc5CommandBufferWaitOnCounter", 2},
    {"jIlc4p5dSD0", "sceAmprMeasureCommandSizeWaitOnAddress", "Ampr::Bc5MeasureCommandSizeWait", 2},
    {"6jLL5BIZ88U", "sceAmprMeasureCommandSizeWaitOnCounter", "Ampr::Bc5MeasureCommandSizeWait", 2},
    // registered today
    {"8aI7R7WaOlc", "sceAmprCommandBufferConstructor", "", -1},
    {"GuchCTefuZw", "sceAmprCommandBufferDestructor", "", -1},
    {"N-FSPA4S3nI", "sceAmprCommandBufferSetBuffer", "", -1},
    {"GnxKOHEawhk", "sceAmprCommandBufferGetCurrentOffset", "", -1},
    {"wkQR9+xTFKY", "sceAmprAmmGetVirtualAddressRanges", "", -1},
    {"Q07J7XpvhrU", "sceAmprAmmGiveDirectMemory", "", -1},
    {"JEVYGhDc97M", "sceAmprAmmCommandBufferMap", "", -1},
    {"8TBE+9XCZbI", "sceAmprAmmCommandBufferMapDirect", "", -1},
    {"M-VFI2DJWQA", "sceAmprAmmCommandBufferUnmap", "", -1},
    {"Ayg6PIon2wA", "sceAmprAmmMeasureAmmCommandSizeUnmap", "", -1},
    {"OJf3vCckPAM", "sceAmprAmmSubmitCommandBuffer2", "", -1},
    {"HXymib4T8gc", "sceAmprAmmWaitCommandBufferCompletion", "", -1},
    {"sJXyWHjP-F8", "sceAmprCommandBufferWriteAddressOnCompletion", "", -1},
    {"DLfoNxTFNVk", "sceAmprCommandBufferWaitOnAddress_04_00", "", -1},
    {"cQb8Zr8Q0Y0", "sceAmprCommandBufferWaitOnCounter_04_00", "", -1},
    {"jK+yuYCI7MA", "sceAmprCommandBufferWriteCounter_04_00", "", -1},
    {"3wn42MWTzTs", "sceAmprCommandBufferWriteCounterOnCompletion", "", -1},
    {"t4ExS+SwLjs", "sceAmprCommandBufferWriteAddressFromCounter_04_00", "", -1},
    {"enZm-6GjWqw", "sceAmprCommandBufferWriteAddressFromCounterPair_04_00", "", -1},
    {"qvMUCyyaCSI", "sceKernelAprSubmitCommandBufferAndGetId", "", -1},
    {"rqwFKI4PAiM", "sceKernelAprWaitCommandBuffer", "", -1},
};

static Loader::SymbolDatabase* g_db = nullptr;

static const Nid& ByName(const char* name) {
	for (const Nid& n: kNids) {
		if (std::strcmp(n.name, name) == 0) {
			return n;
		}
	}
	std::printf("amm0401: FAIL the test names %s, which is not in its NID table\n", name);
	std::fflush(stdout);
	std::_Exit(2);
}

static const Loader::SymbolRecord* Record(const char* name) {
	return g_db->FindByNid(ByName(name).nid, Loader::SymbolType::Func);
}

template <typename F>
static F Fn(const char* name) {
	const auto* r = Record(name);
	if (r == nullptr || r->vaddr == 0) {
		std::printf("amm0401: FAIL %s (%s) is not registered\n", name, ByName(name).nid);
		std::fflush(stdout);
		std::_Exit(2);
	}
	return reinterpret_cast<F>(r->vaddr);
}

// ---- the functions' types (this host's signatures; the new ones as mkamm0401.py defines them) ----
using FnCb          = int(KYTY_SYSV_ABI*)(void*);
using FnSetBuffer   = int(KYTY_SYSV_ABI*)(void*, void*, uint32_t, uint64_t, uint64_t, uint64_t);
using FnOffset      = uint64_t(KYTY_SYSV_ABI*)(void*);
using FnRanges      = void(KYTY_SYSV_ABI*)(uint64_t*, uint64_t*, uint64_t*, uint64_t*);
using FnGive        = int(KYTY_SYSV_ABI*)(int64_t, int64_t, uint64_t, uint64_t, int32_t, int64_t*);
using FnMap         = int(KYTY_SYSV_ABI*)(void*, uint64_t, uint64_t, int32_t, int32_t);
using FnMapDirect   = int(KYTY_SYSV_ABI*)(void*, uint64_t, uint64_t, uint64_t, int32_t, int32_t);
using FnRange       = int(KYTY_SYSV_ABI*)(void*, uint64_t, uint64_t); // Unmap, MapAsPrt, UnmapToPrt
using FnMeasure2    = int64_t(KYTY_SYSV_ABI*)(uint64_t, uint64_t);
using FnSubmit2     = int(KYTY_SYSV_ABI*)(void*, uint32_t, uint32_t, void*, uint32_t*);
using FnId          = int(KYTY_SYSV_ABI*)(uint32_t);
using FnAprSubmitId = int(KYTY_SYSV_ABI*)(void*, uint64_t, uint32_t*);
using FnWriteAddr   = int(KYTY_SYSV_ABI*)(void*, volatile uint64_t*, uint64_t);
using FnWaitAddr    = int(KYTY_SYSV_ABI*)(void*, volatile uint64_t*, uint64_t, uint8_t, uint8_t);
using FnWaitCtr0400 = int(KYTY_SYSV_ABI*)(void*, uint8_t, uint8_t, uint64_t, uint8_t, uint8_t, uint64_t, uint8_t);
using FnWriteCtr0400 = int(KYTY_SYSV_ABI*)(void*, uint8_t, uint8_t, uint64_t, uint8_t, uint32_t);
using FnAddrFromCtr = int(KYTY_SYSV_ABI*)(void*, volatile uint64_t*, uint8_t, uint32_t);
using FnAllocPrt    = int(KYTY_SYSV_ABI*)(void*, uint64_t, uint64_t, int32_t, int32_t);
using FnRemapPrt    = int(KYTY_SYSV_ABI*)(void*, uint64_t, uint64_t, uint64_t, int32_t, uint32_t);
using FnMeasure4    = int64_t(KYTY_SYSV_ABI*)(uint64_t, uint64_t, int32_t, int32_t); // AllocatePaForPrt, ModifyProtect
using FnRemap       = int(KYTY_SYSV_ABI*)(void*, uint64_t, uint64_t, uint64_t, int32_t);
using FnRemapGpu    = int(KYTY_SYSV_ABI*)(void*, uint64_t, uint64_t, uint64_t, int32_t, uint8_t);
using FnMRemap      = int64_t(KYTY_SYSV_ABI*)(uint64_t, uint64_t, uint64_t, int32_t);
using FnMRemapGpu   = int64_t(KYTY_SYSV_ABI*)(uint64_t, uint64_t, uint64_t, int32_t, uint8_t);
using FnProtect     = int(KYTY_SYSV_ABI*)(void*, uint64_t, uint64_t, int32_t, int32_t);
using FnProtectGpu  = int(KYTY_SYSV_ABI*)(void*, uint64_t, uint64_t, int32_t, int32_t, uint8_t);
using FnMtype       = int(KYTY_SYSV_ABI*)(void*, uint64_t, uint64_t, int32_t, int32_t, int32_t);
using FnMtypeGpu    = int(KYTY_SYSV_ABI*)(void*, uint64_t, uint64_t, int32_t, int32_t, int32_t, uint8_t);
using FnMProtectGpu = int64_t(KYTY_SYSV_ABI*)(uint64_t, uint64_t, int32_t, int32_t, uint8_t);
using FnMMtype      = int64_t(KYTY_SYSV_ABI*)(uint64_t, uint64_t, int32_t, int32_t, int32_t);
using FnMMtypeGpu   = int64_t(KYTY_SYSV_ABI*)(uint64_t, uint64_t, int32_t, int32_t, int32_t, uint8_t);
using FnWaitCtr     = int(KYTY_SYSV_ABI*)(void*, uint8_t, uint32_t, uint8_t, uint8_t);
using FnMeasure0    = uint64_t(KYTY_SYSV_ABI*)();
using FnWriteCtrOnC = int(KYTY_SYSV_ABI*)(void*, uint8_t, uint32_t);

// ---- a command buffer: this host's object (0x18 bytes, 0x28 for APR state) and a buffer it records into ----
struct Recorder {
	alignas(16) uint8_t object[0x40] {};
	alignas(16) uint8_t buffer[0x2000] {};

	Recorder() {
		CHECK(Fn<FnCb>("sceAmprCommandBufferConstructor")(object) == 0);
		CHECK(Fn<FnSetBuffer>("sceAmprCommandBufferSetBuffer")(object, buffer, sizeof(buffer), reinterpret_cast<uint64_t>(buffer), 0, 0) == 0);
	}
	~Recorder() { (void)Fn<FnCb>("sceAmprCommandBufferDestructor")(object); }
	Recorder(const Recorder&)            = delete;
	Recorder& operator=(const Recorder&) = delete;

	void*    Cb() { return object; }
	uint64_t Offset() { return Fn<FnOffset>("sceAmprCommandBufferGetCurrentOffset")(object); }
};

struct SubmitResult {
	int32_t  result      = -1;
	uint32_t errorOffset = 0;
};

// An AMM buffer: submitted by its buffer address, as a title does; the host runs AMM-only buffers at once.
static int SubmitAmm(Recorder& r) {
	SubmitResult res {};
	uint32_t     id = 0;
	const int    rc = Fn<FnSubmit2>("sceAmprAmmSubmitCommandBuffer2")(r.buffer, static_cast<uint32_t>(r.Offset()), 0, &res, &id);
	if (rc != 0) {
		return rc;
	}
	(void)Fn<FnId>("sceAmprAmmWaitCommandBufferCompletion")(id);
	return res.result;
}

// An APR buffer: submitted by its object through libkernel at a priority; each priority has its own queue.
static uint32_t SubmitApr(Recorder& r, uint32_t priority) {
	uint32_t id = 0;
	CHECK(Fn<FnAprSubmitId>("sceKernelAprSubmitCommandBufferAndGetId")(r.Cb(), priority, &id) == 0);
	return id;
}

static bool WaitFor(const volatile uint64_t* p, uint64_t value, int ms) {
	for (int k = 0; k < ms; k++) {
		if (*p == value) {
			return true;
		}
		std::this_thread::sleep_for(std::chrono::milliseconds(1));
	}
	return *p == value;
}

static uint64_t Peek(uint64_t a) {
	return *reinterpret_cast<volatile uint64_t*>(a);
}
static void Poke(uint64_t a, uint64_t v) {
	*reinterpret_cast<volatile uint64_t*>(a) = v;
}

struct Stats {
	uint64_t pool  = 0;
	uint64_t pages = 0;
	uint64_t prt   = 0;
};
static Stats GetStats() {
	Stats s;
	bc5_exp0401_amm_stats(&s.pool, &s.pages, &s.prt);
	return s;
}
static int PageFlags(uint64_t va, int32_t* type = nullptr, int32_t* prot = nullptr) {
	return bc5_exp0401_amm_page(va, nullptr, type, prot);
}

static bool SwitchOn(const char* name) {
	const char* e = std::getenv(name);
	return e != nullptr && e[0] != '\0' && std::strcmp(e, "0") != 0;
}

// The registration of the new NIDs: with its switch on, each is registered as its function; off, not at all.
static void CheckRegistration(int sw, bool on) {
	g_case = sw == 0 ? "registration prt" : sw == 1 ? "registration extra" : "registration waits";
	int n = 0;
	for (const Nid& e: kNids) {
		if (e.sw != sw) {
			continue;
		}
		n++;
		const auto* r = g_db->FindByNid(e.nid, Loader::SymbolType::Func);
		if (on) {
			Check(r != nullptr && r->vaddr != 0 && r->dbg_name == e.function, e.name, __LINE__);
		} else {
			Check(r == nullptr, e.name, __LINE__);
		}
	}
	CHECK(n == (sw == 0 ? 6 : sw == 1 ? 16 : 4));
}

static uint64_t g_start    = 0; // the AMM window
static uint64_t g_multimap = 0;

// ---- both AMM switches off: today's map and unmap, no page table ----
static void TodayAmm() {
	g_case = "today amm";
	const uint64_t va     = g_start + 0x0100000;
	const Stats    before = GetStats();
	{
		Recorder m;
		CHECK(Fn<FnMap>("sceAmprAmmCommandBufferMap")(m.Cb(), va, 2 * PAGE, 0, 0x03) == 0);
		CHECK(SubmitAmm(m) == 0);
	}
	Poke(va, 0x1111);
	Poke(va + PAGE, 0x2222);
	CHECK(Peek(va) == 0x1111 && Peek(va + PAGE) == 0x2222);
	const Stats mapped = GetStats();
	CHECK(mapped.pages == 0 && mapped.prt == 0);
	CHECK(mapped.pool + 2 * PAGE == before.pool);
	{
		Recorder u;
		CHECK(Fn<FnRange>("sceAmprAmmCommandBufferUnmap")(u.Cb(), va, 2 * PAGE) == 0);
		CHECK(SubmitAmm(u) == 0);
	}
	CHECK(GetStats().pool == before.pool);
	CHECK(PageFlags(va) == 0);
}

// ---- KYTY_BC5_AMM_PRT_CMDS on ----
static void Prt() {
	auto map_as_prt     = Fn<FnRange>("sceAmprAmmCommandBufferMapAsPrt");
	auto unmap_to_prt   = Fn<FnRange>("sceAmprAmmCommandBufferUnmapToPrt");
	auto allocate       = Fn<FnAllocPrt>("sceAmprAmmCommandBufferAllocatePaForPrt");
	auto remap_into_prt = Fn<FnRemapPrt>("sceAmprAmmCommandBufferRemapIntoPrt");
	auto measure_prt    = Fn<FnMeasure2>("sceAmprAmmMeasureAmmCommandSizeMapAsPrt");
	auto measure_alloc  = Fn<FnMeasure4>("sceAmprAmmMeasureAmmCommandSizeAllocatePaForPrt");
	auto measure_unmap  = Fn<FnMeasure2>("sceAmprAmmMeasureAmmCommandSizeUnmap");
	auto map            = Fn<FnMap>("sceAmprAmmCommandBufferMap");
	auto unmap          = Fn<FnRange>("sceAmprAmmCommandBufferUnmap");

	const uint64_t prt   = g_start + 0x0200000;
	const uint64_t src   = g_start + 0x0280000;
	const uint64_t plain = g_start + 0x02C0000; // never PRT
	const uint64_t r     = g_start + 0x0300000;

	g_case = "prt measures and checks";
	CHECK(measure_prt(prt, PAGE) == 0x20);
	CHECK(measure_prt(prt, 0) == EINVAL_);
	CHECK(measure_prt(prt + 8, PAGE) == EINVAL_);
	CHECK(measure_alloc(prt, PAGE, 0, 0x03) == 0x30);
	CHECK(measure_alloc(prt, PAGE, 0, 0x08) == EINVAL_);
	CHECK(measure_alloc(prt + 8, PAGE, 0, 0x03) == EINVAL_);
	{
		Recorder e;
		CHECK(map_as_prt(e.Cb(), prt + 8, PAGE) == EINVAL_);
		CHECK(map_as_prt(nullptr, prt, PAGE) == EINVAL_);
		CHECK(allocate(e.Cb(), prt, PAGE, 0, 0x04) == EINVAL_);
		CHECK(allocate(e.Cb(), prt, 0, 0, 0x03) == EINVAL_);
		CHECK(remap_into_prt(e.Cb(), prt, src + 8, PAGE, 0x03, 0) == EINVAL_);
		CHECK(remap_into_prt(e.Cb(), prt, src, PAGE, 0x04, 0) == EINVAL_);
		CHECK(unmap_to_prt(e.Cb(), prt, PAGE + 8) == EINVAL_);
		CHECK(e.Offset() == 0);
	}

	g_case = "prt MapAsPrt reads 0, the old backing goes back";
	const Stats s0 = GetStats();
	{
		Recorder m;
		CHECK(map(m.Cb(), prt, PAGE, 0, 0x03) == 0);
		CHECK(SubmitAmm(m) == 0);
	}
	Poke(prt, 0x5555);
	CHECK(Peek(prt) == 0x5555 && PageFlags(prt) == 1);
	{
		Recorder b;
		uint64_t o = b.Offset();
		CHECK(map_as_prt(b.Cb(), prt, 4 * PAGE) == 0);
		CHECK(b.Offset() - o == static_cast<uint64_t>(measure_prt(prt, 4 * PAGE)));
		CHECK(map(b.Cb(), src, PAGE, 0, 0x03) == 0);
		CHECK(SubmitAmm(b) == 0);
	}
	const Stats s1 = GetStats();
	CHECK(Peek(prt) == 0 && Peek(prt + 4 * PAGE - 8) == 0 && Peek(prt + 2 * PAGE + 0x100) == 0);
	CHECK(s1.pool + PAGE == s0.pool); // prt's page back in the pool, src's out
	CHECK(s1.prt == s0.prt + 4 * PAGE);
	CHECK(PageFlags(prt) == 2 && PageFlags(prt + 3 * PAGE) == 2 && PageFlags(src) == 1);

	g_case = "prt AllocatePaForPrt backs the range";
	{
		Recorder b;
		uint64_t o = b.Offset();
		CHECK(allocate(b.Cb(), prt + PAGE, 2 * PAGE, 0, 0x03) == 0);
		CHECK(b.Offset() - o == static_cast<uint64_t>(measure_alloc(prt + PAGE, 2 * PAGE, 0, 0x03)));
		CHECK(SubmitAmm(b) == 0);
	}
	const Stats s2 = GetStats();
	CHECK(s2.pool + 2 * PAGE == s1.pool);
	Poke(prt + PAGE, 0x71);
	Poke(prt + 2 * PAGE, 0x72);
	CHECK(Peek(prt + PAGE) == 0x71 && Peek(prt + 2 * PAGE) == 0x72);
	CHECK(Peek(prt) == 0 && Peek(prt + 3 * PAGE) == 0);
	CHECK(PageFlags(prt + PAGE) == 3 && PageFlags(prt) == 2);

	g_case = "prt AllocatePaForPrt backs only the unbacked runs";
	{
		Recorder b;
		CHECK(allocate(b.Cb(), prt, 4 * PAGE, 2, 0x33) == 0);
		CHECK(SubmitAmm(b) == 0);
	}
	const Stats s3 = GetStats();
	CHECK(s3.pool + 2 * PAGE == s2.pool); // pages 0 and 3 only
	CHECK(Peek(prt + PAGE) == 0x71 && Peek(prt + 2 * PAGE) == 0x72);
	{
		int32_t type = -1;
		int32_t prot = -1;
		CHECK(PageFlags(prt + PAGE, &type, &prot) == 3 && type == 2 && prot == 0x33);
		CHECK(PageFlags(prt + 3 * PAGE, &type, &prot) == 3 && type == 2 && prot == 0x33);
	}
	Poke(prt, 0x90);
	Poke(prt + 3 * PAGE, 0x93);
	CHECK(Peek(prt) == 0x90 && Peek(prt + 3 * PAGE) == 0x93);

	g_case = "prt UnmapToPrt";
	{
		Recorder b;
		uint64_t o = b.Offset();
		CHECK(unmap_to_prt(b.Cb(), prt + PAGE, 2 * PAGE) == 0);
		CHECK(b.Offset() - o == static_cast<uint64_t>(measure_unmap(prt + PAGE, 2 * PAGE)));
		CHECK(SubmitAmm(b) == 0);
	}
	const Stats s4 = GetStats();
	CHECK(s4.pool == s3.pool + 2 * PAGE);
	CHECK(Peek(prt + PAGE) == 0 && Peek(prt + 2 * PAGE) == 0 && Peek(prt) == 0x90 && Peek(prt + 3 * PAGE) == 0x93);
	CHECK(PageFlags(prt + PAGE) == 2 && PageFlags(prt + 2 * PAGE) == 2);

	g_case = "prt RemapIntoPrt";
	Poke(src, 0x88);
	{
		Recorder b;
		uint64_t o = b.Offset();
		CHECK(remap_into_prt(b.Cb(), prt + 2 * PAGE, src, PAGE, 0x03, 0) == 0);
		CHECK(b.Offset() - o == 0x30);
		CHECK(SubmitAmm(b) == 0);
	}
	CHECK(Peek(prt + 2 * PAGE) == 0x88 && Peek(prt + PAGE) == 0);
	CHECK(PageFlags(src) == 0 && PageFlags(prt + 2 * PAGE) == (1 | 2 | 4));
	CHECK(GetStats().pool == s4.pool);

	g_case = "prt refused: RemapIntoPrt and UnmapToPrt outside PRT";
	{
		Recorder b;
		CHECK(remap_into_prt(b.Cb(), plain, prt, PAGE, 0x03, 0) == 0);
		CHECK(SubmitAmm(b) == EINVAL_);
	}
	CHECK(Peek(prt) == 0x90 && PageFlags(prt) == 3);
	{
		Recorder b;
		CHECK(unmap_to_prt(b.Cb(), plain, PAGE) == 0);
		CHECK(SubmitAmm(b) == EINVAL_);
	}
	{
		Recorder b; // a PRT remap onto its own source
		CHECK(remap_into_prt(b.Cb(), prt, prt, PAGE, 0x03, 0) == 0);
		CHECK(SubmitAmm(b) == EINVAL_);
	}
	CHECK(Peek(prt) == 0x90);

	g_case = "prt forced failure 1: no direct memory for the run";
	{
		const uint64_t dm  = Libs::LibKernel::Memory::KernelGetDirectMemorySize();
		const uint64_t big = ((dm >> 30u) + 2u) << 30u; // more than all the direct memory
		const uint64_t at  = g_start + (1ull << 30u);
		if (big <= (28ull << 30u)) {
			{
				Recorder b;
				CHECK(map_as_prt(b.Cb(), at, big) == 0);
				CHECK(SubmitAmm(b) == 0);
			}
			const Stats f0 = GetStats();
			{
				Recorder b;
				CHECK(allocate(b.Cb(), at, big, 0, 0x03) == 0);
				CHECK(SubmitAmm(b) == EAGAIN_);
			}
			const Stats f1 = GetStats();
			CHECK(f1.pool == f0.pool && f1.pages == f0.pages && f1.prt == f0.prt);
			CHECK(Peek(at) == 0 && Peek(at + big / 2) == 0 && Peek(at + big - 8) == 0);
			CHECK(PageFlags(at) == 2 && PageFlags(at + big - PAGE) == 2);
		} else {
			std::printf("amm0401: note: %llu MiB of direct memory, the no-memory case is skipped\n",
			            static_cast<unsigned long long>(dm >> 20u));
		}
	}

	g_case = "prt forced failure 2: the run's map fails, the run rolls back";
	{
		{
			Recorder b;
			CHECK(map_as_prt(b.Cb(), r, 4 * PAGE) == 0);
			CHECK(allocate(b.Cb(), r + PAGE, PAGE, 0, 0x03) == 0);
			CHECK(SubmitAmm(b) == 0);
		}
		Poke(r + PAGE, 0xA5);
		const Stats f0 = GetStats();
		bc5_exp0401_amm_fail_backing(2); // the run at r is backed, the run at r + 2 pages fails
		{
			Recorder b;
			CHECK(allocate(b.Cb(), r, 4 * PAGE, 0, 0x03) == 0);
			CHECK(SubmitAmm(b) == EAGAIN_);
		}
		bc5_exp0401_amm_fail_backing(0);
		const Stats f1 = GetStats();
		CHECK(f1.pool + PAGE == f0.pool); // only the first run's page stays out of the pool
		CHECK(Peek(r + PAGE) == 0xA5 && Peek(r + 2 * PAGE) == 0 && Peek(r + 3 * PAGE + 0x80) == 0);
		CHECK(PageFlags(r) == 3 && PageFlags(r + 2 * PAGE) == 2 && PageFlags(r + 3 * PAGE) == 2);
		Poke(r, 0xA4);
		CHECK(Peek(r) == 0xA4);
	}

	g_case = "prt a map and an unmap end PRT";
	{
		const Stats e0 = GetStats();
		{
			Recorder b;
			CHECK(map(b.Cb(), prt + 3 * PAGE, PAGE, 0, 0x03) == 0);
			CHECK(SubmitAmm(b) == 0);
		}
		CHECK(GetStats().prt + PAGE == e0.prt);
		CHECK(PageFlags(prt + 3 * PAGE) == 1);
		{
			Recorder b;
			CHECK(allocate(b.Cb(), prt + 3 * PAGE, PAGE, 0, 0x03) == 0);
			CHECK(SubmitAmm(b) == EINVAL_);
		}
		{
			Recorder b;
			CHECK(unmap(b.Cb(), prt + PAGE, PAGE) == 0); // an unbacked PRT page
			CHECK(SubmitAmm(b) == 0);
		}
		CHECK(GetStats().prt + 2 * PAGE == e0.prt);
		CHECK(PageFlags(prt + PAGE) == 0);
	}
}

// ---- KYTY_BC5_AMM_EXTRA_CMDS on ----
static void Extra(int64_t direct) {
	auto map            = Fn<FnMap>("sceAmprAmmCommandBufferMap");
	auto map_direct     = Fn<FnMapDirect>("sceAmprAmmCommandBufferMapDirect");
	auto unmap          = Fn<FnRange>("sceAmprAmmCommandBufferUnmap");
	auto remap          = Fn<FnRemap>("sceAmprAmmCommandBufferRemap");
	auto remap_gpu      = Fn<FnRemapGpu>("sceAmprAmmCommandBufferRemapWithGpuMaskId");
	auto multimap       = Fn<FnRemap>("sceAmprAmmCommandBufferMultiMap");
	auto multimap_gpu   = Fn<FnRemapGpu>("sceAmprAmmCommandBufferMultiMapWithGpuMaskId");
	auto protect        = Fn<FnProtect>("sceAmprAmmCommandBufferModifyProtect");
	auto protect_gpu    = Fn<FnProtectGpu>("sceAmprAmmCommandBufferModifyProtectWithGpuMaskId");
	auto mtype          = Fn<FnMtype>("sceAmprAmmCommandBufferModifyMtypeProtect");
	auto mtype_gpu      = Fn<FnMtypeGpu>("sceAmprAmmCommandBufferModifyMtypeProtectWithGpuMaskId");
	auto m_remap        = Fn<FnMRemap>("sceAmprAmmMeasureAmmCommandSizeRemap");
	auto m_remap_gpu    = Fn<FnMRemapGpu>("sceAmprAmmMeasureAmmCommandSizeRemapWithGpuMaskId");
	auto m_multimap     = Fn<FnMRemap>("sceAmprAmmMeasureAmmCommandSizeMultiMap");
	auto m_multimap_gpu = Fn<FnMRemapGpu>("sceAmprAmmMeasureAmmCommandSizeMultiMapWithGpuMaskId");
	auto m_protect      = Fn<FnMeasure4>("sceAmprAmmMeasureAmmCommandSizeModifyProtect");
	auto m_protect_gpu  = Fn<FnMProtectGpu>("sceAmprAmmMeasureAmmCommandSizeModifyProtectWithGpuMaskId");
	auto m_mtype        = Fn<FnMMtype>("sceAmprAmmMeasureAmmCommandSizeModifyMtypeProtect");
	auto m_mtype_gpu    = Fn<FnMMtypeGpu>("sceAmprAmmMeasureAmmCommandSizeModifyMtypeProtectWithGpuMaskId");

	const uint64_t source        = g_start + 0x0400000;
	const uint64_t direct_source = g_start + 0x0440000;
	const uint64_t moved         = g_start + 0x0480000;
	const uint64_t fresh         = g_start + 0x04C0000;
	const uint64_t returned      = g_start + 0x0500000;
	const uint64_t nothing       = g_start + 0x0540000; // never mapped
	const uint64_t alias         = g_multimap + 0x0400000;
	const uint64_t direct_alias  = g_multimap + 0x0440000;

	g_case = "extra measures and checks";
	CHECK(m_remap(moved, source, PAGE, 0x03) == 0x30 && m_remap_gpu(moved, source, PAGE, 0x03, 1) == 0x30);
	CHECK(m_remap(moved, source + 8, PAGE, 0x03) == EINVAL_ && m_remap(moved, source, PAGE, 0x04) == EINVAL_);
	CHECK(m_multimap(alias, moved, PAGE, 0x03) == 0x30 && m_multimap_gpu(alias, moved, PAGE, 0x03, 2) == 0x30);
	CHECK(m_multimap(alias, moved, 0, 0x03) == EINVAL_);
	CHECK(m_protect(returned, PAGE, 0x01, 0x02) == 0x30 && m_protect_gpu(returned, PAGE, 0x01, 0x02, 0) == 0x30);
	CHECK(m_protect(returned, PAGE, 0x04, 0x02) == EINVAL_ && m_protect(returned, PAGE, 0x01, 0x08) == EINVAL_);
	CHECK(m_mtype(returned, PAGE, 3, 0x22, 0x22) == 0x30 && m_mtype_gpu(returned, PAGE, 3, 0x22, 0x22, 0) == 0x30);
	CHECK(m_mtype(returned + 8, PAGE, 3, 0x22, 0x22) == EINVAL_);
	{
		Recorder e;
		CHECK(remap(nullptr, moved, source, PAGE, 0x03) == EINVAL_);
		CHECK(remap(e.Cb(), moved, source + 8, PAGE, 0x03) == EINVAL_);
		CHECK(multimap(e.Cb(), alias, moved, PAGE, 0x404) == EINVAL_);
		CHECK(protect(e.Cb(), returned, PAGE, 0x01, 0x08) == EINVAL_);
		CHECK(mtype(e.Cb(), returned, PAGE + 8, 1, 0x01, 0x01) == EINVAL_);
		CHECK(e.Offset() == 0);
	}

	g_case = "extra Remap moves the pages";
	const Stats s0 = GetStats();
	{
		Recorder b;
		CHECK(map(b.Cb(), source, 2 * PAGE, 0, 0x03) == 0);
		CHECK(map_direct(b.Cb(), direct_source, static_cast<uint64_t>(direct), PAGE, 0, 0x03) == 0);
		CHECK(SubmitAmm(b) == 0);
	}
	Poke(source, 0xA1);
	Poke(source + PAGE, 0xA2);
	Poke(direct_source, 0xD1);
	const Stats s1 = GetStats();
	CHECK(s1.pool + 2 * PAGE == s0.pool);
	{
		Recorder b;
		uint64_t o = b.Offset();
		CHECK(remap(b.Cb(), moved, source, 2 * PAGE, 0x03) == 0);
		CHECK(b.Offset() - o == static_cast<uint64_t>(m_remap(moved, source, 2 * PAGE, 0x03)));
		CHECK(SubmitAmm(b) == 0);
	}
	CHECK(Peek(moved) == 0xA1 && Peek(moved + PAGE) == 0xA2);
	CHECK(PageFlags(source) == 0 && PageFlags(moved) == (1 | 4));
	CHECK(GetStats().pool == s1.pool);

	g_case = "extra MultiMap maps them twice";
	{
		Recorder b;
		CHECK(multimap(b.Cb(), alias, moved, 2 * PAGE, 0x03) == 0);
		CHECK(multimap_gpu(b.Cb(), direct_alias, direct_source, PAGE, 0xC0, 2) == 0);
		CHECK(SubmitAmm(b) == 0);
	}
	CHECK(Peek(alias + PAGE) == 0xA2);
	Poke(alias, 0xB1);
	CHECK(Peek(moved) == 0xB1);
	CHECK(Peek(direct_alias) == 0xD1);
	CHECK(GetStats().pool == s1.pool);

	g_case = "extra a pool page returns with its last mapping";
	{
		Recorder b;
		CHECK(unmap(b.Cb(), moved, 2 * PAGE) == 0);
		CHECK(SubmitAmm(b) == 0);
	}
	CHECK(GetStats().pool == s1.pool); // the alias still holds them
	CHECK(Peek(alias) == 0xB1 && Peek(alias + PAGE) == 0xA2);
	{
		Recorder b;
		CHECK(unmap(b.Cb(), alias, 2 * PAGE) == 0);
		CHECK(SubmitAmm(b) == 0);
	}
	CHECK(GetStats().pool == s0.pool);

	g_case = "extra RemapWithGpuMaskId, then a map at the source";
	{
		Recorder b;
		CHECK(map(b.Cb(), fresh, 2 * PAGE, 0, 0x03) == 0);
		CHECK(SubmitAmm(b) == 0);
	}
	Poke(fresh, 0xC1);
	Poke(fresh + PAGE, 0xC2);
	{
		Recorder b;
		CHECK(remap_gpu(b.Cb(), returned, fresh, 2 * PAGE, 0x03, 1) == 0);
		CHECK(map(b.Cb(), fresh, 2 * PAGE, 0, 0x03) == 0);
		CHECK(SubmitAmm(b) == 0);
	}
	CHECK(Peek(returned) == 0xC1 && Peek(returned + PAGE) == 0xC2);
	Poke(fresh, 0xE1);
	CHECK(Peek(returned) == 0xC1 && Peek(fresh) == 0xE1);
	CHECK(GetStats().pool + 4 * PAGE == s0.pool);

	g_case = "extra ModifyProtect and ModifyMtypeProtect";
	{
		Recorder b;
		uint64_t o = b.Offset();
		CHECK(protect(b.Cb(), returned, 2 * PAGE, 0x01, 0x02) == 0);
		CHECK(b.Offset() - o == static_cast<uint64_t>(m_protect(returned, 2 * PAGE, 0x01, 0x02)));
		o = b.Offset();
		CHECK(mtype(b.Cb(), returned, PAGE, 3, 0x22, 0x22) == 0);
		CHECK(b.Offset() - o == static_cast<uint64_t>(m_mtype(returned, PAGE, 3, 0x22, 0x22)));
		CHECK(protect_gpu(b.Cb(), direct_alias, PAGE, 0x00, 0x80, 0) == 0);
		CHECK(mtype_gpu(b.Cb(), fresh, PAGE, 1, 0x10, 0x13, 0) == 0);
		CHECK(SubmitAmm(b) == 0);
	}
	{
		int32_t type = -1;
		int32_t prot = -1;
		CHECK(PageFlags(returned, &type, &prot) != 0 && prot == 0x23 && type == 3);
		CHECK(PageFlags(returned + PAGE, &type, &prot) != 0 && prot == 0x01 && type == 0);
		CHECK(PageFlags(direct_alias, &type, &prot) != 0 && prot == 0x40);
		CHECK(PageFlags(fresh, &type, &prot) != 0 && prot == 0x10 && type == 1);
		CHECK(PageFlags(fresh + PAGE, &type, &prot) != 0 && prot == 0x03);
	}
	CHECK(Peek(returned) == 0xC1 && Peek(fresh) == 0xE1 && Peek(direct_alias) == 0xD1); // the host keeps CPU access

	g_case = "extra refused: an unmapped source, an alias onto its source, a protection change of unmapped pages";
	{
		Recorder b;
		CHECK(remap(b.Cb(), returned, nothing, PAGE, 0x03) == 0);
		CHECK(SubmitAmm(b) == EINVAL_);
	}
	CHECK(Peek(returned) == 0xC1);
	{
		Recorder b;
		CHECK(multimap(b.Cb(), returned, returned, PAGE, 0x03) == 0);
		CHECK(SubmitAmm(b) == EINVAL_);
	}
	{
		Recorder b;
		CHECK(protect(b.Cb(), nothing, PAGE, 0x01, 0x03) == 0);
		CHECK(SubmitAmm(b) == EINVAL_);
	}
	CHECK(Peek(returned) == 0xC1);
}

// ---- the waits ----
alignas(8) static volatile uint64_t g_flag  = 0;
alignas(8) static volatile uint64_t g_done  = 0;
alignas(8) static volatile uint64_t g_done2 = 0;
alignas(8) static volatile uint64_t g_done3 = 0;
alignas(8) static volatile uint64_t g_v1    = 0;
alignas(8) static volatile uint64_t g_v2    = 0;
alignas(8) static volatile uint64_t g_v3    = 0;

// WaitOnAddress (either form) against a writer thread: still waiting after 100 ms, done within 5 s of the write.
static void WaitAgainstWriter(FnWaitAddr wait, uint32_t priority, const char* what) {
	g_case  = what;
	g_flag  = 1;
	g_done  = 0;
	Recorder b;
	CHECK(wait(b.Cb(), &g_flag, 5, 0, 0) == 0);
	CHECK(Fn<FnWriteAddr>("sceAmprCommandBufferWriteAddressOnCompletion")(b.Cb(), &g_done, 0x1234) == 0);
	const uint32_t id = SubmitApr(b, priority);
	std::this_thread::sleep_for(std::chrono::milliseconds(100));
	CHECK(g_done == 0); // the wait holds (a 100-ms timeout)
	std::thread writer([] {
		std::this_thread::sleep_for(std::chrono::milliseconds(20));
		g_flag = 5;
	});
	const bool done = WaitFor(&g_done, 0x1234, 5000);
	writer.join();
	CHECK(done);
	if (done) {
		CHECK(Fn<FnId>("sceKernelAprWaitCommandBuffer")(id) == 0);
	}
}

static void WaitsOff() {
	auto wait0400  = Fn<FnWaitCtr0400>("sceAmprCommandBufferWaitOnCounter_04_00");
	auto addr_ctr  = Fn<FnAddrFromCtr>("sceAmprCommandBufferWriteAddressFromCounter_04_00");
	auto write_adr = Fn<FnWriteAddr>("sceAmprCommandBufferWriteAddressOnCompletion");

	g_case = "waits off: WriteCounterOnCompletion is today's";
	{
		const auto* r = Record("sceAmprCommandBufferWriteCounterOnCompletion");
		CHECK(r != nullptr && r->dbg_name == "Ampr::CommandBufferWriteCounterOnCompletion");
	}
	WaitAgainstWriter(Fn<FnWaitAddr>("sceAmprCommandBufferWaitOnAddress_04_00"), 2, "waits off: today's WaitOnAddress_04_00");

	g_case  = "waits off: WaitOnCounter_04_00 records a no-op, WriteAddressFromCounter writes 0";
	g_done2 = 0;
	g_v1    = 0xFFFF;
	{
		Recorder b;
		CHECK(wait0400(b.Cb(), 5, 1, 7, 0, 0, 0, 0) == 0);
		CHECK(addr_ctr(b.Cb(), &g_v1, 5, 0) == 0);
		CHECK(write_adr(b.Cb(), &g_done2, 1) == 0);
		const uint32_t id = SubmitApr(b, 3);
		const bool     ok = WaitFor(&g_done2, 1, 5000);
		CHECK(ok);
		if (ok) {
			CHECK(Fn<FnId>("sceKernelAprWaitCommandBuffer")(id) == 0);
		}
	}
	CHECK(g_v1 == 0);
}

static void WaitsOn() {
	auto wait_addr = Fn<FnWaitAddr>("sceAmprCommandBufferWaitOnAddress");
	auto wait_ctr  = Fn<FnWaitCtr>("sceAmprCommandBufferWaitOnCounter");
	auto m_wait_a  = Fn<FnMeasure0>("sceAmprMeasureCommandSizeWaitOnAddress");
	auto m_wait_c  = Fn<FnMeasure0>("sceAmprMeasureCommandSizeWaitOnCounter");
	auto wait0400  = Fn<FnWaitCtr0400>("sceAmprCommandBufferWaitOnCounter_04_00");
	auto write0400 = Fn<FnWriteCtr0400>("sceAmprCommandBufferWriteCounter_04_00");
	auto write_oc  = Fn<FnWriteCtrOnC>("sceAmprCommandBufferWriteCounterOnCompletion");
	auto addr_ctr  = Fn<FnAddrFromCtr>("sceAmprCommandBufferWriteAddressFromCounter_04_00");
	auto addr_pair = Fn<FnAddrFromCtr>("sceAmprCommandBufferWriteAddressFromCounterPair_04_00");
	auto write_adr = Fn<FnWriteAddr>("sceAmprCommandBufferWriteAddressOnCompletion");

	g_case = "waits on: WriteCounterOnCompletion is AnyPS5's";
	{
		const auto* r = Record("sceAmprCommandBufferWriteCounterOnCompletion");
		CHECK(r != nullptr && r->dbg_name == "Ampr::Bc5WriteCounterOnCompletion");
	}

	g_case = "waits on: measures and checks";
	CHECK(m_wait_a() == 0x20 && m_wait_c() == 0x20);
	{
		Recorder e;
		CHECK(wait_addr(e.Cb(), reinterpret_cast<volatile uint64_t*>(reinterpret_cast<uintptr_t>(&g_flag) + 4), 5, 0, 0) == EINVAL_);
		CHECK(wait_addr(e.Cb(), &g_flag, 5, 4, 0) == EINVAL_);
		CHECK(wait_addr(e.Cb(), nullptr, 5, 0, 0) == EINVAL_);
		CHECK(wait_ctr(e.Cb(), 128, 1, 0, 0) == EINVAL_);
		CHECK(wait_ctr(e.Cb(), 3, 1, 4, 0) == EINVAL_);
		CHECK(write0400(e.Cb(), 3, 8, 1, 0, 0) == EINVAL_);
		CHECK(write0400(e.Cb(), 3, 1, 1, 5, 0) == EINVAL_);
		CHECK(write_oc(e.Cb(), 128, 1) == EINVAL_);
		CHECK(addr_pair(e.Cb(), &g_v2, 3, 0) == EINVAL_); // a pair starts at an even counter
		CHECK(wait0400(e.Cb(), 3, 8, 1, 0, 0, 0, 0) == EINVAL_);
		CHECK(e.Offset() == 0);
		uint64_t o = e.Offset();
		CHECK(wait_addr(e.Cb(), &g_flag, 5, 0, 0) == 0);
		CHECK(e.Offset() - o == m_wait_a());
		o = e.Offset();
		CHECK(wait_ctr(e.Cb(), 3, 1, 0, 0) == 0);
		CHECK(e.Offset() - o == m_wait_c());
	}

	WaitAgainstWriter(wait_addr, 2, "waits on: WaitOnAddress against a writer thread");

	g_case  = "waits on: WaitOnCounter against a counter write from another priority";
	g_done2 = 0;
	{
		Recorder a;
		CHECK(wait_ctr(a.Cb(), 3, 9, 0, 0) == 0);
		CHECK(write_adr(a.Cb(), &g_done2, 1) == 0);
		const uint32_t id_a = SubmitApr(a, 3);
		std::this_thread::sleep_for(std::chrono::milliseconds(100));
		CHECK(g_done2 == 0);
		Recorder b;
		CHECK(write_oc(b.Cb(), 3, 9) == 0);
		const uint32_t id_b = SubmitApr(b, 4);
		const bool     ok   = WaitFor(&g_done2, 1, 5000);
		CHECK(ok);
		if (ok) {
			CHECK(Fn<FnId>("sceKernelAprWaitCommandBuffer")(id_a) == 0);
			CHECK(Fn<FnId>("sceKernelAprWaitCommandBuffer")(id_b) == 0);
		}
	}

	g_case  = "waits on: WaitOnCounter_04_00 with a byte access and a mask";
	g_done3 = 0;
	{
		Recorder a; // byte 0 of counter 10, masked to its low nibble, greater than 5
		CHECK(wait0400(a.Cb(), 10, 4, 5, 1, 1, 0xF, 0) == 0);
		CHECK(write_adr(a.Cb(), &g_done3, 1) == 0);
		const uint32_t id_a = SubmitApr(a, 5);
		Recorder       b; // 0x34: low nibble 4, not yet
		CHECK(write0400(b.Cb(), 10, 1, 0x34, 0, 0) == 0);
		const uint32_t id_b = SubmitApr(b, 6);
		CHECK(Fn<FnId>("sceKernelAprWaitCommandBuffer")(id_b) == 0);
		std::this_thread::sleep_for(std::chrono::milliseconds(100));
		CHECK(g_done3 == 0);
		Recorder c; // add 2: 0x36, low nibble 6
		CHECK(write0400(c.Cb(), 10, 1, 2, 4, 0) == 0);
		const uint32_t id_c = SubmitApr(c, 6);
		const bool     ok   = WaitFor(&g_done3, 1, 5000);
		CHECK(ok);
		if (ok) {
			CHECK(Fn<FnId>("sceKernelAprWaitCommandBuffer")(id_a) == 0);
			CHECK(Fn<FnId>("sceKernelAprWaitCommandBuffer")(id_c) == 0);
		}
	}

	g_case = "waits on: WriteCounter_04_00 and WriteAddressFromCounter(Pair)";
	g_done = 0;
	g_v1   = 0;
	g_v2   = 0;
	g_v3   = 0;
	{
		Recorder b;
		CHECK(write0400(b.Cb(), 20, 1, 0x10, 0, 0) == 0); // store
		CHECK(write0400(b.Cb(), 20, 1, 0x5, 4, 0) == 0);  // add
		CHECK(write0400(b.Cb(), 21, 1, 0xAB, 0, 0) == 0);
		CHECK(write0400(b.Cb(), 21, 4, 0xFF, 1, 0) == 0); // or into byte 0 of counter 21
		CHECK(addr_ctr(b.Cb(), &g_v1, 20, 0) == 0);
		CHECK(addr_pair(b.Cb(), &g_v2, 20, 0) == 0);
		CHECK(write0400(b.Cb(), 22, 0, 0x1122334455667788ull, 0, 0) == 0); // 64 bits: counters 22 and 23
		CHECK(addr_pair(b.Cb(), &g_v3, 22, 0) == 0);
		CHECK(write_adr(b.Cb(), &g_done, 1) == 0);
		const uint32_t id = SubmitApr(b, 7);
		const bool     ok = WaitFor(&g_done, 1, 5000);
		CHECK(ok);
		if (ok) {
			CHECK(Fn<FnId>("sceKernelAprWaitCommandBuffer")(id) == 0);
		}
	}
	CHECK(g_v1 == 0x15);
	CHECK(g_v2 == 0x000000FF00000015ull);
	CHECK(g_v3 == 0x1122334455667788ull);
}

static void InitMemory() {
	g_case     = "init: subsystems";
	auto& list = *Common::SubsystemsList::Instance();
	char  arg0[] = "amm0401";
	char* argv[] = {arg0, nullptr};
	list.SetArgs(1, argv);
	auto* core    = Common::CommonSubsystem::Instance();
	auto* threads = Common::ThreadsSubsystem::Instance();
	list.Add(core, {});
	list.Add(threads, {core});
	bool ok = list.InitAll(false);
	auto* config = Config::ConfigSubsystem::Instance();
	list.Add(config, {core});
	ok = ok && list.InitAll(false);
	Config::ConfigOptions options;
	options.printf_direction = Config::OutputDirection::Silent;
	Config::Load(options);
	auto* log = Log::LogSubsystem::Instance();
	list.Add(log, {core, config});
	ok = ok && list.InitAll(false);
	auto* memory = Libs::LibKernel::Memory::MemorySubsystem::Instance();
	list.Add(memory, {core, log});
	ok = ok && list.InitAll(false);
	if (!ok) {
		std::printf("amm0401: FAIL the subsystems did not start: %s: %s\n", list.GetFailName(), list.GetFailMsg());
		std::fflush(stdout);
		std::_Exit(2);
	}
}

} // namespace amm0401

int main(int argc, char** argv) {
	using namespace amm0401;
	const bool  prt   = SwitchOn("KYTY_BC5_AMM_PRT_CMDS");
	const bool  extra = SwitchOn("KYTY_BC5_AMM_EXTRA_CMDS");
	const bool  waits = SwitchOn("KYTY_BC5_AMPR_WAITS");
	const char* mode  = (prt && extra && waits) ? "on" : (!prt && !extra && !waits) ? "off" : "mixed";
	if (argc > 2 || (argc == 2 && std::strcmp(argv[1], mode) != 0)) {
		std::printf("amm0401: the argument says %s but the switches say %s (prt %d, extra %d, waits %d)\n",
		            argc == 2 ? argv[1] : "too much", mode, prt, extra, waits);
		return 2;
	}
	std::thread([] {
		std::this_thread::sleep_for(std::chrono::seconds(120));
		std::printf("amm0401: FAIL watchdog: case \"%s\" still running after 120 s\n", g_case.load());
		std::fflush(stdout);
		std::_Exit(3);
	}).detach();

	InitMemory();
	g_case = "init: registration";
	static Loader::SymbolDatabase db;
	Libs::InitAll(&db);
	g_db = &db;

	g_case = "init: the AMM window and the pool";
	uint64_t start = 0, end = 0, multimap_start = 0, multimap_end = 0;
	Fn<FnRanges>("sceAmprAmmGetVirtualAddressRanges")(&start, &end, &multimap_start, &multimap_end);
	CHECK(start != 0 && end > start && multimap_start > start && multimap_end == end);
	g_start    = start;
	g_multimap = multimap_start;
	const auto dm     = static_cast<int64_t>(Libs::LibKernel::Memory::KernelGetDirectMemorySize());
	int64_t    pool   = -1;
	int64_t    direct = -1;
	CHECK(Fn<FnGive>("sceAmprAmmGiveDirectMemory")(0, dm, 64 * PAGE, PAGE, 1, &pool) == 0 && pool >= 0);
	CHECK(Fn<FnGive>("sceAmprAmmGiveDirectMemory")(0, dm, 4 * PAGE, PAGE, 0, &direct) == 0 && direct >= 0);
	if (start == 0 || pool < 0 || direct < 0) {
		std::printf("amm0401: %s %d of %d\n", mode, g_pass, g_total);
		std::fflush(stdout);
		std::_Exit(1);
	}

	CheckRegistration(0, prt);
	CheckRegistration(1, extra);
	CheckRegistration(2, waits);
	if (!prt && !extra) {
		TodayAmm();
	}
	if (prt) {
		Prt();
	}
	if (extra) {
		Extra(direct);
	}
	if (waits) {
		WaitsOn();
	} else {
		WaitsOff();
	}

	if (std::strcmp(mode, "mixed") == 0) {
		std::printf("amm0401: mixed prt=%s extra=%s waits=%s %d of %d%s\n", prt ? "on" : "off", extra ? "on" : "off",
		            waits ? "on" : "off", g_pass, g_total, g_pass == g_total ? "; end" : "");
	} else {
		std::printf("amm0401: %s %d of %d%s\n", mode, g_pass, g_total, g_pass == g_total ? "; end" : "");
	}
	std::fflush(stdout);
	std::fflush(stderr);
	std::_Exit(g_pass == g_total ? 0 : 1); // the APR workers keep running: no static destructors under them
}
