// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0401 series e5, tag gpu: the CPU test of mkgpu0405.py's src/libs/bc5LleAgc.cpp, experiment 0405 R3's
// e4-now items G2, G4, G6, G8, G11, G12 and G14 in the soft CP and the gc ioctls (gpu0405-notes.md). It needs no game, no
// GPU, no window, no sound device and no network: it hands synthetic packets to the unit's soft CP (SoftCp::submit, through
// the seam bc5_exp0405_gpu_soft_submit) and calls the unit's gc_ioctl (bc5_exp0405_gpu_gc_ioctl), with this process's own
// memory as the "guest" memory and a KytyPlus event queue for the EOP events. The direct path is never initialised
// (Direct::init_once is not called, no device is opened), so nothing is submitted anywhere.
// The unit's completion queue exists only with BC5_DIRECT_JOURNAL=min (read at load into g_async): the test runs itself
// again once with it set (GPU0405_REEXEC=1 marks the second run; BC5_DIRECT_MEM_LINE=0 keeps exp 0401's memory-line thread
// from starting), so that G6's event comes from the completion thread (bc5-cq0) behind what was queued before, and G12 has
// a queue to wait for. If that fails the test runs synchronously and says so on its second line.
// Switches, each read from the environment as the unit reads them (set, non-empty and not "0"): BC5_R3_MEMSEM_SIGNAL,
// BC5_R3_REWIND_CATCH, BC5_R3_DROP_CATCH, BC5_R3_SUBMIT_EOP_EVENT, BC5_R3_COND_WRITE, BC5_R3_WAIT_IDLE, BC5_R3_TS_100MHZ.
// Each case runs with its own switch on or off; off, it checks today's behaviour (the packets the soft CP ignores today stay
// ignored, the buffer goes on, the ioctls return at once without an event, timestamps in nanoseconds).
// Output: one line per case, then "gpu0405: on N of N; end" (all seven on), "gpu0405: off N of N; end" (all off or unset)
// or "gpu0405: mixed <the items on> N of N; end"; without "; end" something failed. Exit 0 only after the end line. A
// watchdog ends a hang after 60 s with a FAIL line.
// Build: build0401.py ... --gate gpu0405.cpp <out> --like src/libs/bc5LleAgc.cpp (the unit's compile command; linked with
// every emulator object but main.cpp.o, the private bc5LleAgc.cpp.o among them), -std=c++20 -Wall -Wextra -Werror.
// usage: BC5_R3_MEMSEM_SIGNAL=1 BC5_R3_REWIND_CATCH=1 BC5_R3_DROP_CATCH=1 BC5_R3_SUBMIT_EOP_EVENT=1 BC5_R3_COND_WRITE=1
//        BC5_R3_WAIT_IDLE=1 BC5_R3_TS_100MHZ=1 gpu0405 on   |   (each =0 or unset) gpu0405 off   |   gpu0405

#include "common/abi.h"
#include "common/commonSubsystem.h"
#include "common/emulatorConfig.h"
#include "common/logging/log.h"
#include "common/subsystems.h"
#include "common/threads.h"
#include "kernel/eventQueue.h"
#include "libs/errno.h"

#include <unistd.h>

#include <atomic>
#include <cerrno>
#include <chrono>
#include <cinttypes>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <thread>
#include <vector>

// The seams of mkgpu0405.py's unit (always compiled in, never called by the emulator).
extern "C" int      bc5_exp0405_gpu_switches();
extern "C" void     bc5_exp0405_gpu_soft_submit(const uint32_t* buf, uint32_t num_dwords);
extern "C" uint64_t bc5_exp0405_gpu_count(int which);
extern "C" uint64_t bc5_exp0405_gpu_drop_op(uint32_t op);
extern "C" uint64_t bc5_exp0405_gpu_nop_sub(uint32_t sub);
extern "C" int      bc5_exp0405_gpu_has_policy();
extern "C" void     bc5_exp0405_gpu_register_eq(int64_t eq, int ident, int add);
extern "C" void     bc5_exp0405_gpu_post(void (*fn)(void*), void* arg);
extern "C" int      bc5_exp0405_gpu_async();
extern "C" int      bc5_exp0405_gpu_gc_ioctl(uint64_t request, void* argp);

namespace gpu0405 {

namespace EQ = Libs::LibKernel::EventQueue;

static int                      g_pass       = 0;
static int                      g_total      = 0;
static int                      g_case_pass  = 0;
static int                      g_case_total = 0;
static std::atomic<const char*> g_case {"init"};

static void Check(bool ok, const char* what, int line) {
	g_total++;
	g_case_total++;
	if (ok) {
		g_pass++;
		g_case_pass++;
	} else {
		std::printf("gpu0405: FAIL %s (line %d): %s\n", g_case.load(), line, what);
		std::fflush(stdout);
	}
}
#define CHECK(cond) Check((cond), #cond, __LINE__)

static void Begin(const char* name) {
	g_case       = name;
	g_case_pass  = 0;
	g_case_total = 0;
}
static void End(const char* sw) {
	std::printf("gpu0405: case %s (%s): %d of %d\n", g_case.load(), sw, g_case_pass, g_case_total);
	std::fflush(stdout);
}

// The unit's R3GpuCount indices (mkgpu0405.py, enum R3GpuCount).
enum {
	kMemsemSet,
	kMemsemAdd,
	kMemsemWait,
	kMemsemOther,
	kRewind,
	kRewindInvalid,
	kDropPackets,
	kNopCustom,
	kEopEvents,
	kEopChained,
	kCondWritten,
	kCondNotWritten,
	kCondOther,
	kWaitIdle,
	kWaitIdleGaveUp,
	kTsWrites,
	kCountN
};
struct Counts {
	uint64_t v[kCountN];
	Counts() {
		for (int k = 0; k < kCountN; k++) v[k] = bc5_exp0405_gpu_count(k);
	}
	[[nodiscard]] uint64_t d(int k) const { return bc5_exp0405_gpu_count(k) - v[k]; }
};

static bool SwitchOn(const char* name) {
	const char* e = std::getenv(name);
	return e != nullptr && e[0] != '\0' && std::strcmp(e, "0") != 0;
}

static uint64_t SteadyNs() {
	return static_cast<uint64_t>(
	    std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now().time_since_epoch()).count());
}

// A type-3 header of `len` dwords (header included): count = len - 2 (PM4 type 3, as the soft CP's execute() reads it).
static uint32_t Pkt3(uint32_t op, uint32_t len) {
	return 0xc0000000u | ((len - 2u) << 16u) | (op << 8u);
}
static uint32_t Lo(const volatile void* p) {
	return static_cast<uint32_t>(reinterpret_cast<uintptr_t>(p));
}
static uint32_t Hi(const volatile void* p) {
	return static_cast<uint32_t>(reinterpret_cast<uintptr_t>(p) >> 32u);
}
static void Run(const std::vector<uint32_t>& ib) {
	bc5_exp0405_gpu_soft_submit(ib.data(), static_cast<uint32_t>(ib.size()));
}
// WRITE_DATA of one dword to memory: DST_SEL 5 (bits 11:8), address, the dword (the soft CP's write_data).
static void PushWriteData(std::vector<uint32_t>& ib, volatile uint32_t* dst, uint32_t v) {
	ib.insert(ib.end(), {Pkt3(0x37, 5), 5u << 8u, Lo(dst), Hi(dst), v});
}

// ---- G2: MEM_SEMAPHORE signal (BC5_R3_MEMSEM_SIGNAL) ----
// The console's 4-dword form: address lo (bits 31:3), address hi, control (SEM_SEL 31:29, SIGNAL_TYPE bit 20).
alignas(8) static volatile uint64_t g_sem = 0;
static std::vector<uint32_t> Sem(uint32_t control, uint32_t lo_or = 0) {
	return {Pkt3(0x39, 4), Lo(&g_sem) | lo_or, Hi(&g_sem), control};
}
alignas(8) static volatile uint32_t g_after_sem = 0;
static void MemSemaphore(bool on) {
	Begin("G2 MEM_SEMAPHORE signal");
	const Counts c;
	g_sem = 5;
	Run(Sem((6u << 29u) | (1u << 20u))); // signal, SIGNAL_TYPE 1: the word becomes 1
	CHECK(g_sem == (on ? 1u : 5u));
	Run(Sem(6u << 29u)); // signal, SIGNAL_TYPE 0: 1 is added
	CHECK(g_sem == (on ? 2u : 5u));
	Run(Sem(6u << 29u));
	CHECK(g_sem == (on ? 3u : 5u));
	std::vector<uint32_t> ib = Sem(7u << 29u); // a wait: counted, not held; the buffer goes on
	g_after_sem              = 0;
	PushWriteData(ib, &g_after_sem, 0x5e5eu);
	Run(ib);
	CHECK(g_sem == (on ? 3u : 5u));
	CHECK(g_after_sem == 0x5e5eu);
	Run({Pkt3(0x39, 3), Lo(&g_sem), (6u << 29u) | (1u << 20u)}); // the PS4's 3-dword form: not executed
	Run({Pkt3(0x39, 4), 0u, 0u, (6u << 29u) | (1u << 20u)});     // address 0: not executed
	Run(Sem(5u << 29u));                                          // SEM_SEL 5: not executed
	CHECK(g_sem == (on ? 3u : 5u));
	Run(Sem((6u << 29u) | (1u << 20u), 4u)); // address bits 2:0 are not part of the address: the same word
	CHECK(g_sem == (on ? 1u : 5u));
	CHECK(c.d(kMemsemSet) == (on ? 2u : 0u));
	CHECK(c.d(kMemsemAdd) == (on ? 2u : 0u));
	CHECK(c.d(kMemsemWait) == (on ? 1u : 0u));
	CHECK(c.d(kMemsemOther) == (on ? 3u : 0u));
	End(on ? "BC5_R3_MEMSEM_SIGNAL on" : "BC5_R3_MEMSEM_SIGNAL off");
}

// ---- G4: REWIND catcher (BC5_R3_REWIND_CATCH) ----
alignas(8) static volatile uint32_t g_after_rewind = 0;
static void Rewind(bool on) {
	Begin("G4 REWIND catcher");
	const Counts          c;
	std::vector<uint32_t> ib = {Pkt3(0x59, 2), 0x00000000u}; // VALID (bit 31) clear
	g_after_rewind           = 0;
	PushWriteData(ib, &g_after_rewind, 0x2e2eu); // what follows still runs: a catcher only
	Run(ib);
	CHECK(g_after_rewind == 0x2e2eu);
	Run({Pkt3(0x59, 2), 0x80000000u}); // VALID set
	Run({Pkt3(0x59, 2), 0x01000000u}); // OFFLOAD_ENABLE alone: VALID clear
	CHECK(c.d(kRewind) == (on ? 3u : 0u));
	CHECK(c.d(kRewindInvalid) == (on ? 2u : 0u));
	End(on ? "BC5_R3_REWIND_CATCH on" : "BC5_R3_REWIND_CATCH off");
}

// ---- G11: COND_WRITE (BC5_R3_COND_WRITE) ----
// 9 dwords: control (FUNCTION 2:0, POLL_SPACE bit 4, WRITE_SPACE 9:8), poll address, reference, mask, write address, data.
constexpr uint32_t                  kCondMem = (1u << 4u) | (1u << 8u);
alignas(8) static volatile uint32_t g_poll   = 0;
alignas(8) static volatile uint32_t g_dst    = 0;
static std::vector<uint32_t> CondWrite(uint32_t control, uint32_t ref, uint32_t mask, uint32_t data, const volatile void* poll,
                                       const volatile void* dst) {
	return {Pkt3(0x45, 9), control, Lo(poll), Hi(poll), ref, mask, Lo(dst), Hi(dst), data};
}
static void CondWriteCase(bool on) {
	Begin("G11 COND_WRITE");
	const Counts c;
	struct Case {
		uint32_t fn, ref;
		bool     hit;
	};
	// The polled dword is 0x105, the mask 0xff: the soft CP compares 5 with (reference & mask).
	static const Case cases[] = {{0, 99, true}, {1, 6, true},  {1, 5, false}, {2, 5, true}, {2, 4, false},
	                             {3, 5, true},  {3, 6, false}, {4, 6, true},  {4, 5, false}, {5, 5, true},
	                             {5, 6, false}, {6, 4, true},  {6, 5, false}, {3, 0x105, true}};
	g_poll        = 0x105u;
	uint32_t hits = 0, misses = 0;
	for (uint32_t k = 0; k < sizeof(cases) / sizeof(cases[0]); k++) {
		g_dst = 0;
		Run(CondWrite(cases[k].fn | kCondMem, cases[k].ref, 0xffu, 0xa000u + k, &g_poll, &g_dst));
		CHECK(g_dst == (on && cases[k].hit ? 0xa000u + k : 0u));
		(cases[k].hit ? hits : misses)++;
	}
	// Not executed: a register poll, a register destination, the reserved function 7, a poll address of 0.
	g_dst = 0;
	Run(CondWrite(3u | (1u << 8u), 5, 0xffu, 1u, &g_poll, &g_dst));
	Run(CondWrite(3u | (1u << 4u), 5, 0xffu, 2u, &g_poll, &g_dst));
	Run(CondWrite(7u | kCondMem, 5, 0xffu, 3u, &g_poll, &g_dst));
	Run(CondWrite(3u | kCondMem, 5, 0xffu, 4u, nullptr, &g_dst));
	CHECK(g_dst == 0u);
	CHECK(c.d(kCondWritten) == (on ? hits : 0u));
	CHECK(c.d(kCondNotWritten) == (on ? misses : 0u));
	CHECK(c.d(kCondOther) == (on ? 4u : 0u));
	End(on ? "BC5_R3_COND_WRITE on" : "BC5_R3_COND_WRITE off");
}

// ---- G8: what the policy drops, custom NOPs (BC5_R3_DROP_CATCH) ----
alignas(8) static volatile uint64_t g_drop_sem  = 0;
alignas(8) static volatile uint32_t g_drop_poll = 0;
alignas(8) static volatile uint32_t g_drop_dst  = 0;
alignas(8) static volatile uint32_t g_drop_wd   = 0;
static void Drop(bool on) {
	Begin("G8 drop catcher");
	const bool     policy = bc5_exp0405_gpu_has_policy() != 0;
	const Counts   c;
	const uint32_t ops[]  = {0x39, 0x45, 0x59, 0x81, 0x37, 0x10};
	uint64_t       before[6];
	for (int k = 0; k < 6; k++) before[k] = bc5_exp0405_gpu_drop_op(ops[k]);
	const uint64_t        sub17 = bc5_exp0405_gpu_nop_sub(0x17), sub0 = bc5_exp0405_gpu_nop_sub(0);
	std::vector<uint32_t> ib    = {Pkt3(0x39, 4), Lo(&g_drop_sem), Hi(&g_drop_sem), (6u << 29u) | (1u << 20u)}; // MEM_SEMAPHORE
	const auto            cw    = CondWrite(kCondMem, 0, 0, 7u, &g_drop_poll, &g_drop_dst);                      // COND_WRITE
	ib.insert(ib.end(), cw.begin(), cw.end());
	ib.insert(ib.end(), {Pkt3(0x59, 2), 0x80000000u});         // REWIND
	ib.insert(ib.end(), {Pkt3(0x81, 3), 0x0u, 0x12345678u});   // WRITE_CONST_RAM (not in the policy table)
	ib.insert(ib.end(), {0xc004105cu, 1u, 2u, 3u, 4u, 5u});    // a custom NOP, sub-code 0x17 (KytyPS5 pm4.h R_FLIP)
	ib.insert(ib.end(), {Pkt3(0x10, 2), 0u});                  // a plain NOP: not counted
	ib.push_back(0xffff1000u);                                 // the 1-dword filler NOP: not counted
	g_drop_wd = 0;
	PushWriteData(ib, &g_drop_wd, 0x77u); // WRITE_DATA: passed by the policy, not counted; still runs
	Run(ib);
	CHECK(g_drop_wd == 0x77u);
	const bool drops = on && policy;
	for (int k = 0; k < 4; k++) CHECK(bc5_exp0405_gpu_drop_op(ops[k]) - before[k] == (drops ? 1u : 0u));
	CHECK(bc5_exp0405_gpu_drop_op(0x37) - before[4] == 0u);
	CHECK(bc5_exp0405_gpu_drop_op(0x10) - before[5] == 0u);
	CHECK(bc5_exp0405_gpu_nop_sub(0x17) - sub17 == (on ? 1u : 0u));
	CHECK(bc5_exp0405_gpu_nop_sub(0) - sub0 == 0u);
	CHECK(c.d(kDropPackets) == (drops ? 4u : 0u));
	CHECK(c.d(kNopCustom) == (on ? 1u : 0u));
	std::printf("gpu0405: note: the policy table is %s in this build\n", policy ? "linked (KYTY_BC5_DIRECT)" : "absent: opcodes are not counted");
	End(on ? "BC5_R3_DROP_CATCH on" : "BC5_R3_DROP_CATCH off");
}

// ---- G14: 100-MHz timestamps (BC5_R3_TS_100MHZ) ----
alignas(8) static volatile uint64_t g_ts[5];
static std::vector<uint32_t> ReleaseMem(uint32_t data_sel, volatile uint64_t* a) { // gfx10 RELEASE_MEM, 8 dwords, INT_SEL 0
	return {Pkt3(0x49, 8), 0x28u | (5u << 8u), data_sel << 29u, Lo(a), Hi(a), 0u, 0u, 0u};
}
static std::vector<uint32_t> WriteEop(uint32_t data_sel, volatile uint64_t* a) { // EVENT_WRITE_EOP, 6 dwords, INT_SEL 0
	return {Pkt3(0x47, 6), 0x28u | (5u << 8u), Lo(a), (data_sel << 29u) | (Hi(a) & 0xffffu), 0u, 0u};
}
static std::vector<uint32_t> CopyData(uint32_t src_sel, volatile uint64_t* a) { // COPY_DATA to memory, 64 bits
	return {Pkt3(0x40, 6), src_sel | (5u << 8u) | (1u << 16u), 0u, 0u, Lo(a), Hi(a)};
}
static void Timestamps(bool on) {
	Begin("G14 timestamps");
	const Counts c;
	for (auto& t: g_ts) t = 0;
	const uint64_t t0 = SteadyNs();
	Run(ReleaseMem(3, &g_ts[0])); // DATA_SEL 3: the GPU clock
	Run(WriteEop(3, &g_ts[1]));
	Run(CopyData(9, &g_ts[2]));   // SRC_SEL 9: the GPU clock
	Run(ReleaseMem(4, &g_ts[3])); // DATA_SEL 4 and SRC_SEL 0xa keep nanoseconds
	Run(CopyData(0xa, &g_ts[4]));
	const uint64_t t1 = SteadyNs();
	for (int k = 0; k < 3; k++) {
		const uint64_t v = g_ts[k];
		CHECK(on ? (v >= t0 / 10u && v <= t1 / 10u + 1u) : (v >= t0 && v <= t1));
	}
	for (int k = 3; k < 5; k++) {
		const uint64_t v = g_ts[k];
		CHECK(v >= t0 && v <= t1);
	}
	CHECK(c.d(kTsWrites) == (on ? 3u : 0u));
	End(on ? "BC5_R3_TS_100MHZ on" : "BC5_R3_TS_100MHZ off");
}

// ---- G6: the submit-and-write-EOP ioctl's event (BC5_R3_SUBMIT_EOP_EVENT) ----
// An EVFILT_GRAPHICS event as the host's own AddEqEvent registers it (KytyPlus src/graphics/host_gpu/renderer/sync.cpp,
// EopEventTriggerFunc and EopEventResetFunc): each trigger carries its data; a second one before the wait queues behind.
static void TriggerFunc(EQ::KernelEqueueEvent* event, void* trigger_data) {
	auto e = event->event;
	e.fflags++;
	e.data = reinterpret_cast<intptr_t>(trigger_data);
	if (event->triggered) {
		event->pending_events.push_back(e);
	} else {
		event->event     = e;
		event->triggered = true;
	}
}
static void ResetFunc(EQ::KernelEqueueEvent* event) {
	event->triggered    = false;
	event->event.fflags = 0;
	event->event.data   = 0;
}
static bool AddGraphicsEvent(EQ::KernelEqueue eq, int ident) {
	EQ::KernelEqueueEvent ev;
	ev.event.ident         = static_cast<uintptr_t>(ident);
	ev.event.filter        = EQ::KERNEL_EVFILT_GRAPHICS;
	ev.event.data          = ident;
	ev.filter.trigger_func = TriggerFunc;
	ev.filter.reset_func   = ResetFunc;
	return EQ::KernelAddEvent(eq, ev) == OK;
}
struct Got {
	uint64_t ident;
	uint64_t data;
};
// Waits up to `ms` for `want` events (0: the whole time, collecting whatever comes).
static std::vector<Got> WaitEvents(EQ::KernelEqueue eq, size_t want, uint32_t ms) {
	std::vector<Got> got;
	const uint64_t   end = SteadyNs() + static_cast<uint64_t>(ms) * 1'000'000ull;
	for (;;) {
		const uint64_t now = SteadyNs();
		if ((want != 0 && got.size() >= want) || now >= end) break;
		EQ::KernelEvent ev[4];
		int             out  = 0;
		unsigned int    timo = static_cast<unsigned int>((end - now) / 1000u);
		if (timo == 0) timo = 1;
		if (EQ::KernelWaitEqueue(eq, ev, 4, &out, &timo) == OK) {
			for (int k = 0; k < out; k++) got.push_back({static_cast<uint64_t>(ev[k].ident), static_cast<uint64_t>(ev[k].data)});
		}
	}
	return got;
}
static void DrainEvents(EQ::KernelEqueue eq) {
	for (int k = 0; k < 100; k++) {
		EQ::KernelEvent ev[4];
		int             out  = 0;
		unsigned int    zero = 0;
		if (EQ::KernelWaitEqueue(eq, ev, 4, &out, &zero) != OK || out == 0) return;
	}
}
static bool Has(const std::vector<Got>& got, uint64_t ident, uint64_t data) {
	for (const Got& g: got) {
		if (g.ident == ident && g.data == data) return true;
	}
	return false;
}
struct SubmitEopArgs { // the unit's (and RPCSX gc.cpp's) layout of 0xc020810c
	uint32_t  arg0;
	uint32_t  count;
	uint32_t* cmds;
	uint64_t  eop_value;
	uint32_t  wait_flag;
};
static_assert(sizeof(SubmitEopArgs) == 32, "0xc020810c carries 0x20 bytes");
alignas(8) static volatile uint32_t g_eop_label = 0;
static void SubmitEop(bool on, bool async) {
	Begin("G6 submit-and-write-EOP event");
	EQ::KernelEqueue eq = 0;
	CHECK(EQ::KernelCreateEqueue(&eq, "gpu0405") == OK);
	CHECK(AddGraphicsEvent(eq, 0x40));
	CHECK(AddGraphicsEvent(eq, 0));
	bc5_exp0405_gpu_register_eq(eq, 0x40, 1);
	bc5_exp0405_gpu_register_eq(eq, 0, 1);
	DrainEvents(eq);
	const Counts c;
	// 1: one buffer, a WRITE_DATA to a label; the event must come with eop_value, after the buffer has run.
	std::vector<uint32_t> dcb;
	g_eop_label = 0;
	PushWriteData(dcb, &g_eop_label, 0xc0deu);
	uint32_t      ib[4] = {0xc0023f00u, Lo(dcb.data()), Hi(dcb.data()), static_cast<uint32_t>(dcb.size())}; // INDIRECT_BUFFER
	SubmitEopArgs a {0, 1, ib, 0x0123456789abcdefull, 0};
	CHECK(bc5_exp0405_gpu_gc_ioctl(0xc020810c, &a) == 0);
	CHECK(g_eop_label == 0xc0deu); // the soft CP ran the buffer: today's path, on and off
	auto got = WaitEvents(eq, on ? 2 : 0, on ? 2000 : 300);
	if (on) {
		CHECK(Has(got, 0x40, 0x0123456789abcdefull)); // the graphics EOP ident (RPCSX kGcEventGfxEop)
		CHECK(Has(got, 0, 0x0123456789abcdefull));    // and ident 0, as for every graphics EOP of this soft CP
		CHECK(got.size() == 2u);
	} else {
		CHECK(got.empty()); // today: the value is stored only, no event
	}
	// 2: an empty command list.
	SubmitEopArgs b {0, 0, nullptr, 0x42, 0};
	CHECK(bc5_exp0405_gpu_gc_ioctl(0xc020810c, &b) == 0);
	got = WaitEvents(eq, on ? 2 : 0, on ? 2000 : 300);
	if (on) {
		CHECK(Has(got, 0x40, 0x42));
		CHECK(Has(got, 0, 0x42));
		CHECK(got.size() == 2u);
	} else {
		CHECK(got.empty());
	}
	CHECK(c.d(kEopEvents) == (on ? 2u : 0u));
	CHECK(c.d(kEopChained) == 0u); // no chain without a device
	bc5_exp0405_gpu_register_eq(eq, 0x40, 0);
	bc5_exp0405_gpu_register_eq(eq, 0, 0);
	std::printf("gpu0405: note: G6's event %s\n", async ? "came through the completion queue (bc5-cq0)" : "was raised at once (synchronous run)");
	End(on ? "BC5_R3_SUBMIT_EOP_EVENT on" : "BC5_R3_SUBMIT_EOP_EVENT off");
}

// ---- G12: wait idle (BC5_R3_WAIT_IDLE) ----
static std::atomic<int> g_slow1 {0};
static std::atomic<int> g_slow2 {0};
static void SlowPost(void* arg) { // a completion-queue item that takes 300 ms
	std::this_thread::sleep_for(std::chrono::milliseconds(300));
	static_cast<std::atomic<int>*>(arg)->store(1);
}
static bool WaitFlag(const std::atomic<int>& f, int ms) {
	for (int k = 0; k < ms && f.load() == 0; k++) std::this_thread::sleep_for(std::chrono::milliseconds(1));
	return f.load() != 0;
}
static void WaitIdle(bool on, bool async) {
	Begin("G12 wait idle");
	const Counts c;
	uint32_t     dummy = 0;
	if (async) {
		bc5_exp0405_gpu_post(SlowPost, &g_slow1);
		CHECK(bc5_exp0405_gpu_gc_ioctl(0xc0048117, &dummy) == 0); // wait idle
		CHECK(g_slow1.load() == (on ? 1 : 0)); // on: the item ran before the ioctl returned; off: today's, at once
		CHECK(WaitFlag(g_slow1, 3000));
		bc5_exp0405_gpu_post(SlowPost, &g_slow2);
		CHECK(bc5_exp0405_gpu_gc_ioctl(0xc0048116, &dummy) == 0); // submit done: at once, on and off
		CHECK(g_slow2.load() == 0);
		CHECK(WaitFlag(g_slow2, 3000));
	} else {
		CHECK(bc5_exp0405_gpu_gc_ioctl(0xc0048117, &dummy) == 0);
		CHECK(bc5_exp0405_gpu_gc_ioctl(0xc0048116, &dummy) == 0);
		std::printf("gpu0405: note: synchronous run: G12's wait had no completion queue to wait for\n");
	}
	CHECK(c.d(kWaitIdle) == (on ? 1u : 0u));
	CHECK(c.d(kWaitIdleGaveUp) == 0u);
	End(on ? "BC5_R3_WAIT_IDLE on" : "BC5_R3_WAIT_IDLE off");
}

static void InitSubsystems() {
	g_case       = "init: subsystems";
	auto& list   = *Common::SubsystemsList::Instance();
	char  arg0[] = "gpu0405";
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
	if (!ok) {
		std::printf("gpu0405: FAIL the subsystems did not start: %s: %s\n", list.GetFailName(), list.GetFailMsg());
		std::fflush(stdout);
		std::_Exit(2);
	}
}

} // namespace gpu0405

int main(int argc, char** argv) {
	using namespace gpu0405;
	// Once: again, with the unit's completion queue (BC5_DIRECT_JOURNAL=min is read when the unit is loaded).
	if (std::getenv("GPU0405_REEXEC") == nullptr) {
		::setenv("GPU0405_REEXEC", "1", 1);
		::setenv("BC5_DIRECT_JOURNAL", "min", 1);
		::setenv("BC5_DIRECT_MEM_LINE", "0", 1);
		::execv("/proc/self/exe", argv);
		std::printf("gpu0405: note: running again with BC5_DIRECT_JOURNAL=min failed (%s); running synchronously\n", std::strerror(errno));
	}
	::setenv("BC5_DIRECT_MEM_LINE", "0", 1);
	static const char* const names[7] = {"BC5_R3_MEMSEM_SIGNAL", "BC5_R3_REWIND_CATCH", "BC5_R3_DROP_CATCH", "BC5_R3_SUBMIT_EOP_EVENT",
	                                     "BC5_R3_COND_WRITE",    "BC5_R3_WAIT_IDLE",    "BC5_R3_TS_100MHZ"};
	bool        sw[7];
	int         bits = 0, n_on = 0;
	std::string items;
	for (int k = 0; k < 7; k++) {
		sw[k] = SwitchOn(names[k]);
		if (sw[k]) {
			bits |= 1 << k;
			n_on++;
			items += items.empty() ? "" : ",";
			items += names[k];
		}
	}
	const char* mode = n_on == 7 ? "on" : n_on == 0 ? "off" : "mixed";
	if (argc > 2 || (argc == 2 && std::strcmp(argv[1], mode) != 0)) {
		std::printf("gpu0405: the argument says %s but the switches say %s (%s)\n", argc == 2 ? argv[1] : "too much", mode, items.c_str());
		return 2;
	}
	std::thread([] {
		std::this_thread::sleep_for(std::chrono::seconds(60));
		std::printf("gpu0405: FAIL watchdog: case \"%s\" still running after 60 s\n", g_case.load());
		std::fflush(stdout);
		std::_Exit(3);
	}).detach();

	InitSubsystems();
	const bool async = bc5_exp0405_gpu_async() != 0;
	std::printf("gpu0405: completion queue %s\n",
	            async ? "asynchronous (BC5_DIRECT_JOURNAL=min): G6's event comes from bc5-cq0, G12 waits for it"
	                  : "synchronous: G6's event is raised at once, G12's wait is not exercised");

	Begin("switches");
	CHECK(bc5_exp0405_gpu_switches() == bits); // the unit read what the test reads
	End(mode);
	MemSemaphore(sw[0]);
	Rewind(sw[1]);
	Drop(sw[2]);
	SubmitEop(sw[3], async);
	CondWriteCase(sw[4]);
	WaitIdle(sw[5], async);
	Timestamps(sw[6]);

	if (n_on != 0 && n_on != 7) {
		std::printf("gpu0405: mixed %s %d of %d%s\n", items.c_str(), g_pass, g_total, g_pass == g_total ? "; end" : "");
	} else {
		std::printf("gpu0405: %s %d of %d%s\n", mode, g_pass, g_total, g_pass == g_total ? "; end" : "");
	}
	std::fflush(stdout);
	std::fflush(stderr);
	std::_Exit(g_pass == g_total ? 0 : 1); // the completion thread keeps running: no static destructors under it
}
