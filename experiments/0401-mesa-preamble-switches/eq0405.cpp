// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0401 series e5, port agent "eq" (mkeq0405.py): the CPU test of exp 0405's equeue, timer, kevent and mmap
// items in src/kernel/eventQueue.cpp and src/libs/bc5LleAgc.cpp, against the real unit functions. Run three times on the
// box, in the build container, in a fresh directory:
//   KYTY_BC5_EQUEUE_FIXES=1 KYTY_BC5_MMAP_SHIM_FIXES=1 eq0405 on
//   KYTY_BC5_EQUEUE_FIXES=0 KYTY_BC5_MMAP_SHIM_FIXES=0 eq0405 off
//   eq0405                                                      (both unset: off)
// The program reads both switches itself (its own copy of the documented grammar) and expects each item's behaviour on or
// off as the switches say; with them off, exactly today's behaviour, wherever today's code does not end the process. One
// line per case, then exactly "eq0405: on N of N; end" or "eq0405: off N of N; end" (both switches fully on, or both
// off; item lists print "eq0405: mixed ... N of N; end"); exit 0 only then. A watchdog ends a hang after 90 s with a FAIL
// line (exit 3). The units print "[bc5] exp 0405: equeue fixes on|off ..." (at registration) and "[bc5] exp 0405: mmap
// shim fixes on|off ..." (at the first mmap) on stderr once each.
// Cases (eq0405-notes.md has the reasons):
//   grammar  both switches' parsers against this file's table (unset, "", "0", "1", item lists, unknown names) and the
//            values read once (lesson R41: unset/empty/0/1/invalid/list)
//   kk02     a level user event: on, once per wait (num 4 -> 1, again 1); off, today's 4 and 4
//   edge     an EV_CLEAR user event: 1, then ETIMEDOUT (on and off)
//   ampr     three AMPR completions (pending copies): 3 events with data 1, 2, 3 (on and off)
//   eop      a graphics EOP-style event (EVFILT_GRAPHICS 0x40 with sync.cpp's reset and trigger rules, copied here):
//            3 triggers -> 3 events, then num 2 -> 2 + 1 (on and off: the hazard check)
//   flip     a VideoOut flip-style event (updated in place, reset clears): 2 triggers -> 1 event, fflags 2 (on and off)
//   uintr    the renderer's user interrupt 0x1800 as an edge user event through KernelTriggerUserEventForAll (on and off)
//   mixed    an EOP-style event and a level user event in one queue: the EOP part identical on and off
//   sk03     (on only) sceKernelWaitEqueue with out == NULL: OK and the event filled; ETIMEDOUT on an empty poll
//   g1 x4    kevent (NID RW-GEfpnsqg) with {0,0}, {0,30 ms}, an invalid timespec, and with a ready event / NULL timeout:
//            on, 0 at once / 0 after >= 29 ms / -1 at once / 1; off, today's wait until the event a thread triggers later
//   kk01 x2  on: sceKernelAddTimerEvent (57ZK+ODEXWY) with usec by value (upper half of the register set to garbage):
//            periodic EVFILT_TIMER, EV_CLEAR, data = expirations (checked against the clock); re-add without a duplicate,
//            sceKernelDeleteTimerEvent (YWQFUyXIVdU), a bad queue, a 0 period. off: YWQFUyXIVdU unregistered, and
//            today's reading (a pointer to a timespec: a one-shot EVFILT_HRTIMER)
//   mmap x6  (NID BPE9s9vQQXo) a hint over a live mapping; a free hint; MAP_FIXED over a live mapping; the driver-style
//            device mappings at 0xfe0200000 (MAP_SHARED, fd 5) and 0xfe0204000 (MAP_SHARED | MAP_FIXED); prot 0;
//            prot 1 (on only: today's memset on a read-only mapping faults)
// Build (box0401's build0401.py, series e5): this file compiled with src/kernel/eventQueue.cpp's compile command
// (--gate eq0405.cpp <out> --like src/kernel/eventQueue.cpp) and linked with every emulator object but main.cpp.o, the
// private eventQueue.cpp.o and bc5LleAgc.cpp.o (mkeq0405.py's outputs; bc5LleAgc.cpp also after the "gpu" agent's edit)
// in place of the shared ones. With a shared object in their place the link fails (the 0405 functions declared below are
// undefined): the link shows the private objects are in.
// Runtime state it sets up, as amm0401.cpp does (which ran on the e4 build): the Common, Threads, Config (output silent),
// Log and Memory subsystems; Libs::InitAll registers every library, and the shims are taken by NID from that
// SymbolDatabase (the NIDs below are checked against their names by mkeq0405.py). No Pthread subsystem: PRINT_NAME stays
// off on every thread. No game, GPU, window, sound device or network; the soft CP and the direct path stay idle
// (BC5_DIRECT_CHAIN unset: Bc5ChainObserveEqueue and chain_observe return at once).
// usage: eq0405 [on|off]   (the argument, when given, must match the switches)

#include "common/abi.h"
#include "common/commonSubsystem.h"
#include "common/emulatorConfig.h"
#include "common/logging/log.h"
#include "common/subsystems.h"
#include "common/threads.h"
#include "kernel/eventQueue.h"
#include "kernel/memory.h"
#include "kernel/pthread.h"
#include "libs/errno.h"
#include "libs/libs.h"
#include "loader/symbolDatabase.h"

#include <atomic>
#include <chrono>
#include <cstdarg>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <thread>

// The functions mkeq0405.py adds; no header declares them (the link fails with the shared objects).
namespace Libs::LibKernel::EventQueue {
uint32_t Bc5EqueueFixesParse0405(const char* value);
uint32_t Bc5EqueueFixes0405();
} // namespace Libs::LibKernel::EventQueue
namespace Libs::Bc5LleKernel {
uint32_t Bc5MmapShimFixesParse0405(const char* value);
uint32_t Bc5MmapShimFixes0405();
} // namespace Libs::Bc5LleKernel

namespace eq0405 {

namespace EQ  = Libs::LibKernel::EventQueue;
namespace LK  = Libs::LibKernel;
namespace Mem = Libs::LibKernel::Memory;
using Clock   = std::chrono::steady_clock;

constexpr int kWatchdogSeconds = 90;

// KYTY_BC5_EQUEUE_FIXES items and KYTY_BC5_MMAP_SHIM_FIXES items, as the units document them.
constexpr uint32_t KK02 = 1u, SK03 = 2u, G1 = 4u, KK01 = 8u, EQ_ALL = 15u;
constexpr uint32_t HINT = 1u, PROT = 2u, MM_ALL = 3u;

constexpr int16_t  kFilterTimer    = -7;
constexpr int16_t  kFilterHrTimer  = -15;
constexpr int16_t  kFilterGraphics = -14;
constexpr int16_t  kFilterVideo    = -13;
constexpr int16_t  kFilterUser     = -11;
constexpr uint16_t kEvOneshot      = 0x10;
constexpr uint16_t kEvClear        = 0x20;
constexpr size_t   kPage           = 0x4000;

// {NID, name}: each checked with exp 0327's calculator by mkeq0405.py.
struct Nid {
	const char* nid;
	const char* name;
};
constexpr Nid kMmap {"BPE9s9vQQXo", "mmap"};
constexpr Nid kKevent {"RW-GEfpnsqg", "kevent"};
constexpr Nid kAddTimer {"57ZK+ODEXWY", "sceKernelAddTimerEvent"};
constexpr Nid kDeleteTimer {"YWQFUyXIVdU", "sceKernelDeleteTimerEvent"};

// The shims' types as bc5LleAgc.cpp defines them (the timer's third argument is whatever the guest passes in rdx).
using FnMmap     = void*(KYTY_SYSV_ABI*)(void*, size_t, int, int, int, int64_t);
using FnKevent   = int(KYTY_SYSV_ABI*)(int, const void*, int, void*, int, const void*);
using FnAddTimer = int(KYTY_SYSV_ABI*)(int64_t, int, const void*, void*);
using FnDelTimer = int(KYTY_SYSV_ABI*)(int64_t, int);

uint32_t                 g_eq = 0;
uint32_t                 g_mm = 0;
std::atomic<int>         g_cases {0};
std::atomic<int>         g_passed {0};
std::atomic<const char*> g_case {"start"};
std::atomic<bool>        g_finished {false};
Loader::SymbolDatabase*  g_db = nullptr;

bool On(uint32_t item) {
	return (g_eq & item) != 0;
}
bool MmOn(uint32_t item) {
	return (g_mm & item) != 0;
}

uint64_t NowNs() {
	return static_cast<uint64_t>(
	    std::chrono::duration_cast<std::chrono::nanoseconds>(Clock::now().time_since_epoch()).count());
}
uint64_t MsSince(uint64_t t0) {
	return (NowNs() - t0) / 1000000u;
}
void SleepMs(int ms) {
	std::this_thread::sleep_for(std::chrono::milliseconds(ms));
}

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
	std::printf("eq0405: case %d %s: %s (%s)\n", g_cases.load(), name, ok ? "ok" : "FAIL", info.c_str());
	std::fflush(stdout);
}

void Note(const char* text) {
	std::printf("eq0405: note: %s\n", text);
	std::fflush(stdout);
}

[[noreturn]] void SetupFail(const std::string& what) {
	std::printf("eq0405: FAIL setup: %s\n", what.c_str());
	std::fflush(stdout);
	std::_Exit(2);
}

void Watchdog() {
	const auto start = Clock::now();
	while (!g_finished.load()) {
		std::this_thread::sleep_for(std::chrono::milliseconds(50));
		if (Clock::now() - start > std::chrono::seconds(kWatchdogSeconds)) {
			std::printf("eq0405: FAIL watchdog: case \"%s\" still running after %d s (a hang); %d of %d cases passed "
			            "before it\n",
			            g_case.load(), kWatchdogSeconds, g_passed.load(), g_cases.load());
			std::fflush(stdout);
			std::_Exit(3);
		}
	}
}

// The documented grammar: unset, empty or "0" is off; a comma list turns on the items it names; anything else, all.
uint32_t Expect(const char* v, const char* const* names, const uint32_t* bits, int n, uint32_t all) {
	if (v == nullptr || v[0] == '\0' || std::strcmp(v, "0") == 0) {
		return 0;
	}
	uint32_t          items = 0;
	const std::string s(v);
	size_t            at = 0;
	for (;;) {
		const size_t      comma = s.find(',', at);
		const std::string part  = s.substr(at, comma == std::string::npos ? std::string::npos : comma - at);
		for (int k = 0; k < n; k++) {
			if (part == names[k]) {
				items |= bits[k];
			}
		}
		if (comma == std::string::npos) {
			break;
		}
		at = comma + 1;
	}
	return items != 0 ? items : all;
}
const char* const kEqNames[] = {"kk02", "sk03", "g1", "kk01"};
const uint32_t    kEqBits[]  = {KK02, SK03, G1, KK01};
const char* const kMmNames[] = {"hint", "prot"};
const uint32_t    kMmBits[]  = {HINT, PROT};
uint32_t ExpectEq(const char* v) {
	return Expect(v, kEqNames, kEqBits, 4, EQ_ALL);
}
uint32_t ExpectMm(const char* v) {
	return Expect(v, kMmNames, kMmBits, 2, MM_ALL);
}

const Loader::SymbolRecord* Record(const Nid& n) {
	return g_db->FindByNid(n.nid, Loader::SymbolType::Func);
}

template <typename F>
F Fn(const Nid& n) {
	const auto* r = Record(n);
	if (r == nullptr || r->vaddr == 0) {
		SetupFail(Fmt("%s (%s) is not registered", n.name, n.nid));
	}
	return reinterpret_cast<F>(r->vaddr);
}

EQ::KernelEqueue NewQueue(const char* name) {
	EQ::KernelEqueue eq = 0;
	if (EQ::KernelCreateEqueue(&eq, name) != 0 || eq == EQ::KERNEL_EQUEUE_INVALID) {
		SetupFail(Fmt("sceKernelCreateEqueue(%s)", name));
	}
	return eq;
}

// sceKernelWaitEqueue with a timeout in microseconds (0: a poll).
int Wait(EQ::KernelEqueue eq, EQ::KernelEvent* ev, int num, int* out, uint32_t timo_us) {
	const LK::KernelUseconds t = timo_us;
	return EQ::KernelWaitEqueue(eq, ev, num, out, &t);
}

void Clear(EQ::KernelEvent* ev, int n) {
	for (int k = 0; k < n; k++) {
		ev[k]       = EQ::KernelEvent {};
		ev[k].ident = 0xdeadu;
	}
}

const char* Err(int r) {
	switch (r) {
		case 0: return "OK";
		case LK::KERNEL_ERROR_ETIMEDOUT: return "ETIMEDOUT";
		case LK::KERNEL_ERROR_EBADF: return "EBADF";
		case LK::KERNEL_ERROR_ENOENT: return "ENOENT";
		case LK::KERNEL_ERROR_EINVAL: return "EINVAL";
		case LK::KERNEL_ERROR_EFAULT: return "EFAULT";
		default: return "other";
	}
}

void* P(uintptr_t v) {
	return reinterpret_cast<void*>(v);
}
uintptr_t U(const void* p) {
	return reinterpret_cast<uintptr_t>(p);
}

// ---- graphics-style events, with the rules of today's units copied here (the units' own functions are static) --------
// graphics/host_gpu/renderer/sync.cpp EopEventResetFunc / EopEventTriggerFunc (KytyPlus f266548 + patch 0001), which
// ResetVideoOutEvent of graphics/presentation/videoOut.cpp matches line for line.
void EopReset(EQ::KernelEqueueEvent* e) {
	e->triggered    = false;
	e->event.fflags = 0;
	e->event.data   = 0;
}
void EopTrigger(EQ::KernelEqueueEvent* e, void* data) {
	auto t = e->event;
	t.fflags++;
	t.data = reinterpret_cast<intptr_t>(data);
	if (e->triggered) {
		e->pending_events.push_back(t);
	} else {
		e->event     = t;
		e->triggered = true;
	}
}
// graphics/presentation/videoOut.cpp TriggerVideoOutEvent (experiment 0188: one event, updated in place while unread;
// the data packing is left out).
void FlipTrigger(EQ::KernelEqueueEvent* e, void* data) {
	auto t       = e->event;
	t.fflags     = t.fflags < 0xfu ? t.fflags + 1u : t.fflags;
	t.data       = reinterpret_cast<intptr_t>(data);
	e->event     = t;
	e->triggered = true;
}

int AddEop(EQ::KernelEqueue eq, int id) {
	EQ::KernelEqueueEvent event;
	event.triggered           = false;
	event.event.ident         = static_cast<uintptr_t>(id);
	event.event.filter        = kFilterGraphics;
	event.event.udata         = P(0xe0e0);
	event.event.fflags        = 0;
	event.event.data          = id;
	event.filter.reset_func   = EopReset;
	event.filter.trigger_func = EopTrigger;
	return EQ::KernelAddEvent(eq, event);
}

int AddFlip(EQ::KernelEqueue eq) {
	EQ::KernelEqueueEvent event {};
	event.event.ident         = 0;
	event.event.filter        = kFilterVideo;
	event.event.udata         = P(0xf1f1);
	event.filter.reset_func   = EopReset;
	event.filter.trigger_func = FlipTrigger;
	return EQ::KernelAddEvent(eq, event);
}

bool Is(const EQ::KernelEvent& e, uintptr_t ident, int16_t filter, uint32_t fflags, intptr_t data, uintptr_t udata) {
	return e.ident == ident && e.filter == filter && e.fflags == fflags && e.data == data && U(e.udata) == udata;
}

// ---- cases --------------------------------------------------------------------------------------------------------
void CaseGrammar(const char* e_eq, const char* e_mm) {
	g_case = "grammar";
	struct Row {
		const char* v;
		uint32_t    eq;
		uint32_t    mm;
	};
	const Row rows[] = {{nullptr, 0, 0},     {"", 0, 0},           {"0", 0, 0},       {"1", 15, 3},
	                    {"kk02", 1, 3},      {"sk03", 2, 3},       {"g1", 4, 3},      {"kk01", 8, 3},
	                    {"g1,kk01", 12, 3},  {"kk02,bogus", 1, 3}, {"bogus", 15, 3},  {"kk02,sk03,g1,kk01", 15, 3},
	                    {"hint", 15, 1},     {"prot", 15, 2},      {"hint,prot", 15, 3}, {"prot,x", 15, 2},
	                    {",", 15, 3},        {"00", 15, 3},        {"KK02", 15, 3},   {"kk02,", 1, 3}};
	int bad = 0;
	for (const auto& r: rows) {
		const uint32_t ue = EQ::Bc5EqueueFixesParse0405(r.v);
		const uint32_t um = Libs::Bc5LleKernel::Bc5MmapShimFixesParse0405(r.v);
		if (ue != r.eq || um != r.mm || ExpectEq(r.v) != r.eq || ExpectMm(r.v) != r.mm) {
			bad++;
			std::printf("eq0405: grammar \"%s\": units 0x%x 0x%x, this file 0x%x 0x%x, want 0x%x 0x%x\n",
			            r.v != nullptr ? r.v : "(unset)", ue, um, ExpectEq(r.v), ExpectMm(r.v), r.eq, r.mm);
		}
	}
	const uint32_t once_eq = EQ::Bc5EqueueFixes0405();
	const uint32_t once_mm = Libs::Bc5LleKernel::Bc5MmapShimFixes0405();
	const bool     ok      = bad == 0 && once_eq == g_eq && once_mm == g_mm && g_eq == ExpectEq(e_eq) &&
	                g_mm == ExpectMm(e_mm);
	Report("grammar", ok,
	       Fmt("%d rows, %d wrong; read once: equeue 0x%x, mmap 0x%x; the environment says 0x%x, 0x%x", static_cast<int>(sizeof(rows) / sizeof(rows[0])), bad,
	           once_eq, once_mm, g_eq, g_mm));
}

void CaseLevel() {
	g_case = "kk02 level user event";
	const auto      eq = NewQueue("eq0405 level");
	EQ::KernelEvent ev[4];
	int             out1 = -1, out2 = -1, out3 = -1;
	const int       a    = EQ::KernelAddUserEvent(eq, 5);
	const int       t    = EQ::KernelTriggerUserEvent(eq, 5, P(0x1234));
	Clear(ev, 4);
	const int  r1     = Wait(eq, ev, 4, &out1, 0);
	const int  want   = On(KK02) ? 1 : 4;
	bool       slots  = true;
	for (int k = 0; k < 4; k++) {
		const bool filled = k < want;
		slots = slots && (filled ? Is(ev[k], 5, kFilterUser, 0, 0x1234, 0x1234) : ev[k].ident == 0xdeadu);
	}
	Clear(ev, 4);
	const int r2 = Wait(eq, ev, 4, &out2, 0);
	Clear(ev, 4);
	const int  r3 = Wait(eq, ev, 1, &out3, 0);
	const bool ok = a == 0 && t == 0 && r1 == 0 && out1 == want && slots && r2 == 0 && out2 == want && r3 == 0 &&
	                out3 == 1 && Is(ev[0], 5, kFilterUser, 0, 0x1234, 0x1234);
	Report("kk02 level user event once per wait", ok,
	       Fmt("%s: num 4 -> %d (want %d), again %d, num 1 -> %d; the slots after the event %s", On(KK02) ? "on" : "off (today)",
	           out1, want, out2, out3, slots ? "untouched" : "WRONG"));
	EQ::KernelDeleteEqueue(eq);
}

void CaseEdge() {
	g_case = "edge user event";
	const auto      eq = NewQueue("eq0405 edge");
	EQ::KernelEvent ev[4];
	int             out1 = -1, out2 = -1;
	const int       a = EQ::KernelAddUserEventEdge(eq, 6);
	const int       t = EQ::KernelTriggerUserEvent(eq, 6, P(0x77));
	Clear(ev, 4);
	const int  r1 = Wait(eq, ev, 4, &out1, 0);
	const bool e0 = Is(ev[0], 6, kFilterUser, 0, 0x77, 0x77) && (ev[0].flags & kEvClear) != 0 && ev[1].ident == 0xdeadu;
	const int  r2 = Wait(eq, ev, 4, &out2, 0);
	const bool ok = a == 0 && t == 0 && r1 == 0 && out1 == 1 && e0 && r2 == LK::KERNEL_ERROR_ETIMEDOUT && out2 == 0;
	Report("edge user event unchanged", ok, Fmt("1st wait %s %d, 2nd %s %d", Err(r1), out1, Err(r2), out2));
	EQ::KernelDeleteEqueue(eq);
}

void CaseAmpr() {
	g_case = "ampr pending copies";
	const auto      eq = NewQueue("eq0405 ampr");
	EQ::KernelEvent ev[8];
	int             out1 = -1, out2 = -1;
	const int       a = EQ::KernelAddAmprEvent(eq, 8, P(0xa0));
	int             t = 0;
	for (uintptr_t d = 1; d <= 3; d++) {
		t |= EQ::KernelTriggerAmprEvent(eq, 8, P(d));
	}
	Clear(ev, 8);
	const int r1 = Wait(eq, ev, 8, &out1, 0);
	bool      e  = true;
	for (int k = 0; k < 3; k++) {
		e = e && Is(ev[k], 8, EQ::AmprEventFilter(), 0, k + 1, 0xa0);
	}
	const int  r2 = Wait(eq, ev, 8, &out2, 0);
	const bool ok = a == 0 && t == 0 && r1 == 0 && out1 == 3 && e && ev[3].ident == 0xdeadu &&
	                r2 == LK::KERNEL_ERROR_ETIMEDOUT && out2 == 0;
	Report("ampr completions with pending copies unchanged", ok,
	       Fmt("3 triggers: %s %d events (data %d %d %d), then %s", Err(r1), out1, static_cast<int>(ev[0].data),
	           static_cast<int>(ev[1].data), static_cast<int>(ev[2].data), Err(r2)));
	EQ::KernelDeleteEqueue(eq);
}

void CaseEop() {
	g_case = "graphics eop-style event";
	const auto      eq = NewQueue("eq0405 eop");
	EQ::KernelEvent ev[8];
	const int       a = AddEop(eq, 0x40);
	int             t = 0;
	for (uintptr_t d = 1; d <= 3; d++) {
		t |= EQ::KernelTriggerEvent(eq, 0x40, kFilterGraphics, P(d * 0x100));
	}
	int out1 = -1, out2 = -1, out3 = -1, out4 = -1, out5 = -1;
	Clear(ev, 8);
	const int  r1  = Wait(eq, ev, 8, &out1, 0);
	const bool e1  = Is(ev[0], 0x40, kFilterGraphics, 1, 0x100, 0xe0e0) && Is(ev[1], 0x40, kFilterGraphics, 2, 0x200, 0xe0e0) &&
	                Is(ev[2], 0x40, kFilterGraphics, 2, 0x300, 0xe0e0) && ev[3].ident == 0xdeadu;
	const int r2 = Wait(eq, ev, 8, &out2, 0);
	for (uintptr_t d = 4; d <= 6; d++) {
		t |= EQ::KernelTriggerEvent(eq, 0x40, kFilterGraphics, P(d * 0x100));
	}
	Clear(ev, 8);
	const int  r3 = Wait(eq, ev, 2, &out3, 0);
	const bool e3 = Is(ev[0], 0x40, kFilterGraphics, 1, 0x400, 0xe0e0) && Is(ev[1], 0x40, kFilterGraphics, 2, 0x500, 0xe0e0) &&
	                ev[2].ident == 0xdeadu;
	Clear(ev, 8);
	const int  r4 = Wait(eq, ev, 2, &out4, 0);
	const bool e4 = Is(ev[0], 0x40, kFilterGraphics, 2, 0x600, 0xe0e0) && ev[1].ident == 0xdeadu;
	const int  r5 = Wait(eq, ev, 2, &out5, 0);
	const bool ok = a == 0 && t == 0 && r1 == 0 && out1 == 3 && e1 && r2 == LK::KERNEL_ERROR_ETIMEDOUT && r3 == 0 &&
	                out3 == 2 && e3 && r4 == 0 && out4 == 1 && e4 && r5 == LK::KERNEL_ERROR_ETIMEDOUT && out5 == 0;
	Report("graphics EOP-style event (reset func, pending copies) unchanged", ok,
	       Fmt("3 triggers, num 8: %d events %s; then %s; 3 more, num 2: %d %s, %d %s, then %s", out1, e1 ? "as today" : "WRONG",
	           Err(r2), out3, e3 ? "as today" : "WRONG", out4, e4 ? "as today" : "WRONG", Err(r5)));
	EQ::KernelDeleteEqueue(eq);
}

void CaseFlip() {
	g_case = "flip-style event";
	const auto      eq = NewQueue("eq0405 flip");
	EQ::KernelEvent ev[8];
	const int       a  = AddFlip(eq);
	const int       t1 = EQ::KernelTriggerEvent(eq, 0, kFilterVideo, P(0x11));
	const int       t2 = EQ::KernelTriggerEvent(eq, 0, kFilterVideo, P(0x22));
	int             out1 = -1, out2 = -1;
	Clear(ev, 8);
	const int  r1 = Wait(eq, ev, 8, &out1, 0);
	const bool e1 = Is(ev[0], 0, kFilterVideo, 2, 0x22, 0xf1f1) && ev[1].ident == 0xdeadu;
	const int  r2 = Wait(eq, ev, 8, &out2, 0);
	const bool ok = a == 0 && t1 == 0 && t2 == 0 && r1 == 0 && out1 == 1 && e1 && r2 == LK::KERNEL_ERROR_ETIMEDOUT;
	Report("VideoOut flip-style event (updated in place) unchanged", ok,
	       Fmt("2 triggers, num 8: %d event, fflags %u, %s; then %s", out1, ev[0].fflags, e1 ? "as today" : "WRONG", Err(r2)));
	EQ::KernelDeleteEqueue(eq);
}

void CaseUserInterrupt() {
	g_case = "user interrupt 0x1800";
	const auto      eq = NewQueue("eq0405 uintr");
	EQ::KernelEvent ev[4];
	const int       a = EQ::KernelAddUserEventEdge(eq, 0x1800);
	const int       t = EQ::KernelTriggerUserEventForAll(0x1800, P(0xabc));
	int             out1 = -1, out2 = -1;
	Clear(ev, 4);
	const int  r1 = Wait(eq, ev, 4, &out1, 0);
	const bool e1 = Is(ev[0], 0x1800, kFilterUser, 0, 0xabc, 0xabc) && ev[1].ident == 0xdeadu;
	const int  r2 = Wait(eq, ev, 4, &out2, 0);
	const bool ok = a == 0 && t == 0 && r1 == 0 && out1 == 1 && e1 && r2 == LK::KERNEL_ERROR_ETIMEDOUT;
	Report("renderer user interrupt 0x1800 (edge, ForAll) unchanged", ok,
	       Fmt("trigger %s, wait %s %d, then %s", Err(t), Err(r1), out1, Err(r2)));
	EQ::KernelDeleteEqueue(eq);
}

void CaseMixed() {
	g_case = "mixed queue";
	const auto      eq = NewQueue("eq0405 mixed");
	EQ::KernelEvent ev[8];
	const int       a1 = AddEop(eq, 0x40);
	const int       a2 = EQ::KernelAddUserEvent(eq, 5);
	const int       t1 = EQ::KernelTriggerEvent(eq, 0x40, kFilterGraphics, P(0x100));
	const int       t2 = EQ::KernelTriggerEvent(eq, 0x40, kFilterGraphics, P(0x200));
	const int       t3 = EQ::KernelTriggerUserEvent(eq, 5, P(0x55));
	int             out = -1;
	Clear(ev, 8);
	const int  r      = Wait(eq, ev, 8, &out, 0);
	const bool eop    = Is(ev[0], 0x40, kFilterGraphics, 1, 0x100, 0xe0e0) && Is(ev[1], 0x40, kFilterGraphics, 2, 0x200, 0xe0e0);
	const int  levels = On(KK02) ? 1 : 6;
	bool       user   = true;
	for (int k = 2; k < 8; k++) {
		user = user && (k < 2 + levels ? Is(ev[k], 5, kFilterUser, 0, 0x55, 0x55) : ev[k].ident == 0xdeadu);
	}
	const bool ok = a1 == 0 && a2 == 0 && t1 == 0 && t2 == 0 && t3 == 0 && r == 0 && out == 2 + levels && eop && user;
	Report("EOP-style and level events in one queue", ok,
	       Fmt("%d events: the 2 EOP ones %s, %d level copies (want %d, %s)", out, eop ? "as today" : "WRONG", out - 2, levels,
	           On(KK02) ? "on" : "today"));
	EQ::KernelDeleteEqueue(eq);
}

void CaseNullOut() {
	g_case = "sk03 null out";
	if (!On(SK03)) {
		Note("sk03 not run with the switch off: today's sceKernelWaitEqueue EXITs the host on out == NULL");
		return;
	}
	const auto      eq = NewQueue("eq0405 sk03");
	EQ::KernelEvent ev[2];
	const int       a  = EQ::KernelAddUserEventEdge(eq, 3);
	const int       t1 = EQ::KernelTriggerUserEvent(eq, 3, P(0x33));
	Clear(ev, 2);
	const LK::KernelUseconds zero = 0;
	const int                r1   = EQ::KernelWaitEqueue(eq, ev, 1, nullptr, &zero);
	const bool               e1   = Is(ev[0], 3, kFilterUser, 0, 0x33, 0x33);
	const int                r2   = EQ::KernelWaitEqueue(eq, ev, 1, nullptr, &zero);
	const int                t2   = EQ::KernelTriggerUserEvent(eq, 3, P(0x34));
	Clear(ev, 2);
	const int  r3 = EQ::KernelWaitEqueue(eq, ev, 1, nullptr, nullptr);
	const bool e3 = Is(ev[0], 3, kFilterUser, 0, 0x34, 0x34);
	const bool ok = a == 0 && t1 == 0 && r1 == 0 && e1 && r2 == LK::KERNEL_ERROR_ETIMEDOUT && t2 == 0 && r3 == 0 && e3;
	Report("sk03 sceKernelWaitEqueue with out == NULL", ok,
	       Fmt("poll with an event %s (event %s), empty poll %s, untimed wait with an event %s", Err(r1), e1 ? "filled" : "WRONG",
	           Err(r2), Err(r3)));
	EQ::KernelDeleteEqueue(eq);
}

// kevent: one queue with an edge user event id 9, a thread that triggers it after delay_ms (0: none).
struct KeventRun {
	int      result = -100;
	uint64_t ms     = 0;
	uintptr_t ident = 0;
};
KeventRun KeventWithLateTrigger(FnKevent kevent, EQ::KernelEqueue eq, const LK::KernelTimespec* ts, int delay_ms) {
	EQ::KernelEvent ev[4];
	Clear(ev, 4);
	std::thread later;
	if (delay_ms > 0) {
		later = std::thread([eq, delay_ms] {
			SleepMs(delay_ms);
			EQ::KernelTriggerUserEvent(eq, 9, P(0x99));
		});
	}
	const uint64_t t0 = NowNs();
	KeventRun      run;
	run.result = kevent(static_cast<int>(eq), nullptr, 0, ev, 4, ts);
	run.ms     = MsSince(t0);
	run.ident  = ev[0].ident;
	if (later.joinable()) {
		later.join();
	}
	return run;
}

// After an "on" run that returned before the late trigger: the event is there now, and a poll takes it.
int Drain(FnKevent kevent, EQ::KernelEqueue eq) {
	EQ::KernelEvent        ev[4];
	const LK::KernelTimespec zero {0, 0};
	Clear(ev, 4);
	return kevent(static_cast<int>(eq), nullptr, 0, ev, 4, &zero);
}

void CaseKevent(FnKevent kevent) {
	{
		g_case = "g1 kevent poll";
		const auto               eq = NewQueue("eq0405 kq poll");
		const int                a  = EQ::KernelAddUserEventEdge(eq, 9);
		const LK::KernelTimespec ts {0, 0};
		const KeventRun          k = KeventWithLateTrigger(kevent, eq, &ts, 150);
		bool                     ok = a == 0;
		int                      d  = -100;
		if (On(G1)) {
			d  = Drain(kevent, eq);
			ok = ok && k.result == 0 && k.ms < 100 && d == 1;
		} else {
			ok = ok && k.result == 1 && k.ms >= 140 && k.ident == 9;
		}
		Report("g1 kevent with a {0,0} timeout", ok,
		       Fmt("%s: returned %d after %llu ms%s", On(G1) ? "on, a poll" : "off, today's wait for the event at 150 ms",
		           k.result, static_cast<unsigned long long>(k.ms), On(G1) ? Fmt(", the late event polled: %d", d).c_str() : ""));
		EQ::KernelDeleteEqueue(eq);
	}
	{
		g_case = "g1 kevent timed";
		const auto               eq = NewQueue("eq0405 kq timed");
		const int                a  = EQ::KernelAddUserEventEdge(eq, 9);
		const LK::KernelTimespec ts {0, 30000000};
		const KeventRun          k = KeventWithLateTrigger(kevent, eq, &ts, 300);
		bool                     ok = a == 0;
		int                      d  = -100;
		if (On(G1)) {
			d  = Drain(kevent, eq);
			ok = ok && k.result == 0 && k.ms >= 29 && k.ms < 250 && d == 1;
		} else {
			ok = ok && k.result == 1 && k.ms >= 290 && k.ident == 9;
		}
		Report("g1 kevent with a {0, 30 ms} timeout", ok,
		       Fmt("%s: returned %d after %llu ms%s", On(G1) ? "on, a timed wait" : "off, today's wait for the event at 300 ms",
		           k.result, static_cast<unsigned long long>(k.ms), On(G1) ? Fmt(", the late event polled: %d", d).c_str() : ""));
		EQ::KernelDeleteEqueue(eq);
	}
	{
		g_case = "g1 kevent invalid";
		const auto               eq = NewQueue("eq0405 kq invalid");
		const int                a  = EQ::KernelAddUserEventEdge(eq, 9);
		const LK::KernelTimespec ts {0, 1000000000};
		const KeventRun          k = KeventWithLateTrigger(kevent, eq, &ts, 150);
		bool                     ok = a == 0;
		int                      d  = -100;
		if (On(G1)) {
			d  = Drain(kevent, eq);
			ok = ok && k.result == -1 && k.ms < 100 && d == 1;
		} else {
			ok = ok && k.result == 1 && k.ms >= 140 && k.ident == 9;
		}
		Report("g1 kevent with tv_nsec 1e9", ok,
		       Fmt("%s: returned %d after %llu ms", On(G1) ? "on, EINVAL as -1" : "off, today's wait for the event at 150 ms",
		           k.result, static_cast<unsigned long long>(k.ms)));
		EQ::KernelDeleteEqueue(eq);
	}
	{
		g_case = "g1 kevent ready";
		const auto               eq = NewQueue("eq0405 kq ready");
		const int                a  = EQ::KernelAddUserEventEdge(eq, 9);
		const LK::KernelTimespec ts {0, 0};
		const int                t1 = EQ::KernelTriggerUserEvent(eq, 9, P(0x91));
		const KeventRun          k1 = KeventWithLateTrigger(kevent, eq, &ts, 0);
		const int                t2 = EQ::KernelTriggerUserEvent(eq, 9, P(0x92));
		const KeventRun          k2 = KeventWithLateTrigger(kevent, eq, nullptr, 0);
		const LK::KernelTimespec big {5, 0};
		const int                t3 = EQ::KernelTriggerUserEvent(eq, 9, P(0x93));
		const KeventRun          k3 = KeventWithLateTrigger(kevent, eq, &big, 0);
		const bool ok = a == 0 && t1 == 0 && t2 == 0 && t3 == 0 && k1.result == 1 && k1.ident == 9 && k2.result == 1 &&
		                k2.ident == 9 && k3.result == 1 && k3.ident == 9 && k1.ms < 100 && k2.ms < 100 && k3.ms < 100;
		Report("g1 kevent with an event ready ({0,0}, NULL, {5 s, 0})", ok,
		       Fmt("returned %d, %d, %d", k1.result, k2.result, k3.result));
		EQ::KernelDeleteEqueue(eq);
	}
}

// Timer events: the count of periods that ran out by a read lies between these bounds (the unit's clock is the same
// steady clock; its add time lies in [a0, a1], the read in [r0, r1]).
bool CountIn(int64_t total, uint64_t a0, uint64_t a1, uint64_t r0, uint64_t r1, uint64_t period_ns, int64_t* lo_out,
             int64_t* hi_out) {
	const int64_t lo = r0 > a1 ? static_cast<int64_t>((r0 - a1) / period_ns) : 0;
	const int64_t hi = static_cast<int64_t>((r1 - a0) / period_ns);
	*lo_out          = lo;
	*hi_out          = hi;
	return total >= lo && total <= hi;
}

void CaseTimer() {
	auto*      del_record = Record(kDeleteTimer);
	const auto add        = Fn<FnAddTimer>(kAddTimer);
	if (!On(KK01)) {
		g_case = "kk01 off";
		Note("kk01 off: sceKernelAddTimerEvent with microseconds by value is not run (today's shim reads them as a "
		     "timespec pointer and faults); today's reading of a real timespec pointer is checked instead");
		const auto               eq = NewQueue("eq0405 hrtimer");
		const LK::KernelTimespec ts {0, 5000000};
		EQ::KernelEvent          ev[4];
		int                      out1 = -1, out2 = -1;
		const uint64_t           t0 = NowNs();
		const int                a  = add(eq, 9, &ts, P(0x77));
		Clear(ev, 4);
		const int      r1 = Wait(eq, ev, 4, &out1, 200000);
		const uint64_t ms = MsSince(t0);
		const bool e1 = ev[0].ident == 9 && ev[0].filter == kFilterHrTimer && (ev[0].flags & kEvOneshot) != 0 && U(ev[0].udata) == 0x77;
		const int  r2 = Wait(eq, ev, 4, &out2, 20000);
		const bool ok = del_record == nullptr && a == 0 && r1 == 0 && out1 == 1 && e1 && ms >= 4 &&
		                r2 == LK::KERNEL_ERROR_ETIMEDOUT;
		Report("kk01 off: today's one-shot HR timer, sceKernelDeleteTimerEvent unregistered", ok,
		       Fmt("YWQFUyXIVdU %s; timespec {0, 5 ms}: %s %d event after %llu ms, filter %d, then %s",
		           del_record == nullptr ? "unregistered" : "REGISTERED", Err(r1), out1, static_cast<unsigned long long>(ms),
		           ev[0].filter, Err(r2)));
		EQ::KernelDeleteEqueue(eq);
		return;
	}
	const auto garbage = [](uint32_t usec) {
		return reinterpret_cast<const void*>(static_cast<uintptr_t>(0xdeadbeef00000000ull) | usec);
	};
	{
		g_case                 = "kk01 periodic";
		const auto     eq      = NewQueue("eq0405 timer");
		const uint64_t period  = 20000000; // 20 ms
		EQ::KernelEvent ev[8];
		int             out1 = -1, out2 = -1, out3 = -1;
		const uint64_t  a0 = NowNs();
		const int       a  = add(eq, 7, garbage(20000), P(0x55));
		const uint64_t  a1 = NowNs();
		Clear(ev, 8);
		const uint64_t w0 = NowNs();
		const int      r1 = Wait(eq, ev, 8, &out1, 200000);
		const uint64_t w1 = NowNs();
		const bool     e1 = ev[0].ident == 7 && ev[0].filter == kFilterTimer && (ev[0].flags & kEvClear) != 0 &&
		                U(ev[0].udata) == 0x55 && ev[0].data >= 1 && ev[1].ident == 0xdeadu;
		const int64_t d1    = r1 == 0 ? ev[0].data : 0;
		int64_t       total = d1;
		int64_t       lo1 = 0, hi1 = 0;
		const bool    in1 = CountIn(total, a0, a1, w0, w1, period, &lo1, &hi1);
		// at once again: nothing, unless another period ran out meanwhile (then the count says so)
		Clear(ev, 8);
		const uint64_t p0 = NowNs();
		const int      r2 = Wait(eq, ev, 8, &out2, 0);
		const uint64_t p1 = NowNs();
		const int64_t  d2 = r2 == 0 ? ev[0].data : 0;
		total += d2;
		int64_t lo2 = 0, hi2 = 0;
		const bool in2 = CountIn(total, a0, a1, p0, p1, period, &lo2, &hi2) && (r2 == 0 || r2 == LK::KERNEL_ERROR_ETIMEDOUT);
		SleepMs(70);
		Clear(ev, 8);
		const uint64_t q0 = NowNs();
		const int      r3 = Wait(eq, ev, 8, &out3, 0);
		const uint64_t q1 = NowNs();
		const int64_t  d3 = r3 == 0 ? ev[0].data : 0;
		total += d3;
		int64_t lo3 = 0, hi3 = 0;
		const bool in3 = CountIn(total, a0, a1, q0, q1, period, &lo3, &hi3);
		const bool ok  = a == 0 && r1 == 0 && out1 == 1 && e1 && in1 && in2 && r3 == 0 && out3 == 1 && ev[0].ident == 7 &&
		                d3 >= 2 && in3 && lo3 >= 3;
		Report("kk01 sceKernelAddTimerEvent: periodic EVFILT_TIMER, data = expirations", ok,
		       Fmt("add %s (usec 20000 with 0xdeadbeef in the upper half); first wait %s after %llu ms, data %lld (clock "
		           "%lld..%lld); at once %s, data %lld; after 70 ms %d event, data %lld; %lld periods in all, the clock says "
		           "%lld..%lld",
		           Err(a), Err(r1), static_cast<unsigned long long>((w1 - w0) / 1000000u), static_cast<long long>(d1),
		           static_cast<long long>(lo1), static_cast<long long>(hi1), Err(r2), static_cast<long long>(d2), out3,
		           static_cast<long long>(d3), static_cast<long long>(total), static_cast<long long>(lo3),
		           static_cast<long long>(hi3)));
		EQ::KernelDeleteEqueue(eq);
	}
	{
		g_case          = "kk01 re-add, delete";
		const auto eq   = NewQueue("eq0405 timer 2");
		const auto del  = del_record != nullptr ? reinterpret_cast<FnDelTimer>(del_record->vaddr) : nullptr;
		EQ::KernelEvent ev[8];
		int             out1 = -1, out2 = -1, out3 = -1;
		const int       a1 = add(eq, 7, garbage(20000), P(0x55));
		SleepMs(5);
		const int a2 = add(eq, 7, garbage(20000), P(0x66));
		Clear(ev, 8);
		const int       r1     = Wait(eq, ev, 8, &out1, 200000);
		const uintptr_t udata1 = U(ev[0].udata);
		const bool      one    = out1 == 1 && ev[0].ident == 7 && udata1 == 0x66 && ev[1].ident == 0xdeadu;
		const int  d1   = del != nullptr ? del(eq, 7) : -100;
		const int  r2   = Wait(eq, ev, 8, &out2, 60000);
		const int  d2   = del != nullptr ? del(eq, 7) : -100;
		const int  bad  = add(0x7fffffff, 1, garbage(1000), nullptr);
		const int  z    = add(eq, 8, garbage(0), P(0x88));
		Clear(ev, 8);
		const int  r3   = Wait(eq, ev, 8, &out3, 100000);
		const bool zero = r3 == 0 && out3 == 1 && ev[0].ident == 8 && ev[0].filter == kFilterTimer && ev[0].data >= 1;
		const int  d3   = del != nullptr ? del(eq, 8) : -100;
		const bool ok   = del != nullptr && a1 == 0 && a2 == 0 && r1 == 0 && one && d1 == 0 && r2 == LK::KERNEL_ERROR_ETIMEDOUT &&
		                out2 == 0 && d2 == LK::KERNEL_ERROR_ENOENT && bad == LK::KERNEL_ERROR_EBADF && z == 0 && zero && d3 == 0;
		Report("kk01 re-add, sceKernelDeleteTimerEvent, a bad queue, a 0 period", ok,
		       Fmt("YWQFUyXIVdU %s; re-add: %d event, udata 0x%llx; delete %s, then wait %s, delete again %s; bad queue %s; "
		           "0 period: %s %d event, data %lld, delete %s",
		           del != nullptr ? "registered" : "MISSING", out1, static_cast<unsigned long long>(udata1), Err(d1),
		           Err(r2), Err(d2), Err(bad), Err(r3), out3, static_cast<long long>(ev[0].data), Err(d3)));
		EQ::KernelDeleteEqueue(eq);
	}
}

int QueryProt(void* p) {
	void* start = nullptr;
	void* end   = nullptr;
	int   prot  = -1;
	return Mem::KernelQueryMemoryProtection(p, &start, &end, &prot) == 0 ? prot : -1;
}

bool AllBytes(const void* p, size_t n, uint8_t v) {
	const auto* b = static_cast<const uint8_t*>(p);
	for (size_t k = 0; k < n; k++) {
		if (b[k] != v) {
			return false;
		}
	}
	return true;
}

void CaseMmap(FnMmap shim_mmap) {
	constexpr int kAnon = 0x1002; // MAP_ANON | MAP_PRIVATE (the shim reads only MAP_FIXED, 0x10)
	{
		g_case        = "mmap hint over a live mapping";
		void*      a  = shim_mmap(nullptr, kPage, 3, kAnon, -1, 0);
		if (a != nullptr) {
			std::memset(a, 0xab, kPage);
		}
		void*      b  = a != nullptr ? shim_mmap(a, kPage, 3, kAnon, -1, 0) : nullptr;
		bool       ok = a != nullptr && b != nullptr;
		if (ok && MmOn(HINT)) {
			ok = b != a && AllBytes(a, kPage, 0xab) && QueryProt(a) == 3 && AllBytes(b, kPage, 0);
		} else if (ok) {
			ok = b == a && AllBytes(a, kPage, 0);
		}
		Report("mmap: an anonymous hint over a live mapping", ok,
		       Fmt("%s: first at %p, the hint gave %p; the first mapping %s", MmOn(HINT) ? "on, a hint" : "off, today's fixed map",
		           a, b, a == nullptr ? "-" : (AllBytes(a, kPage, 0xab) ? "intact" : "replaced and cleared")));
	}
	{
		g_case   = "mmap free hint";
		void* c  = shim_mmap(nullptr, kPage, 3, kAnon, -1, 0);
		int   u  = c != nullptr ? Mem::KernelMunmap(U(c), kPage) : -1;
		void* d  = u == 0 ? shim_mmap(c, kPage, 3, kAnon, -1, 0) : nullptr;
		bool  ok = c != nullptr && u == 0 && d == c && AllBytes(d, kPage, 0) && QueryProt(d) == 3;
		Report("mmap: a free hint lands at the hint", ok, Fmt("hint %p -> %p", c, d));
	}
	{
		g_case   = "mmap fixed over a live mapping";
		void* e  = shim_mmap(nullptr, kPage, 3, kAnon, -1, 0);
		if (e != nullptr) {
			std::memset(e, 0xcd, kPage);
		}
		void* f  = e != nullptr ? shim_mmap(e, kPage, 3, kAnon | 0x10, -1, 0) : nullptr;
		bool  ok = e != nullptr && f == e && AllBytes(f, kPage, 0);
		Report("mmap: MAP_FIXED over a live mapping replaces it (unchanged)", ok, Fmt("%p -> %p", e, f));
	}
	{
		g_case          = "mmap driver-style";
		void* const g0  = P(0xfe0200000ull);
		void* const h0  = P(0xfe0204000ull);
		void*       g   = shim_mmap(g0, kPage, 0x22, 0x1, 5, 0);
		const int   gp  = g != nullptr ? QueryProt(g) : -1;
		bool        rw  = false;
		if (g == g0) {
			auto* w = static_cast<volatile uint64_t*>(g);
			w[1]    = 0x0123456789abcdefull;
			rw      = w[1] == 0x0123456789abcdefull && w[0] == 0;
		}
		void*      h  = shim_mmap(h0, kPage, 0x22, 0x11, 5, 0);
		const bool ok = g == g0 && gp == 0x22 && rw && h == h0;
		Report("mmap: the driver-style device mappings keep their fixed addresses", ok,
		       Fmt("0xfe0200000 MAP_SHARED fd 5 -> %p prot 0x%x %s; 0xfe0204000 MAP_SHARED|MAP_FIXED -> %p", g, gp,
		           rw ? "writable, cleared" : "NOT USABLE", h));
		if (g == g0) {
			Mem::KernelMunmap(U(g), kPage);
		}
		if (h == h0) {
			Mem::KernelMunmap(U(h), kPage);
		}
	}
	{
		g_case        = "mmap prot 0";
		void*     p   = shim_mmap(nullptr, kPage, 0, kAnon, -1, 0);
		const int pr  = p != nullptr ? QueryProt(p) : -1;
		bool      ok  = p != nullptr;
		if (ok && MmOn(PROT)) {
			ok = pr == 0; // no access: not touched here
		} else if (ok) {
			ok = pr == 0x33 && AllBytes(p, kPage, 0);
		}
		Report("mmap: prot 0", ok, Fmt("%s: %p with prot 0x%x", MmOn(PROT) ? "on, no access" : "off, today's 0x33", p, pr));
	}
	if (MmOn(PROT)) {
		g_case        = "mmap prot 1";
		void*     q   = shim_mmap(nullptr, kPage, 1, kAnon, -1, 0);
		const int pr  = q != nullptr ? QueryProt(q) : -1;
		const bool ok = q != nullptr && pr == 1 && AllBytes(q, kPage, 0);
		Report("mmap: prot 1 (read only) is mapped and reads zero", ok, Fmt("%p with prot 0x%x", q, pr));
	} else {
		Note("mmap prot 1 not run with \"prot\" off: today's shim clears a read-only mapping with memset and faults");
	}
}

void InitSubsystems() {
	g_case       = "init: subsystems";
	auto& list   = *Common::SubsystemsList::Instance();
	char  arg0[] = "eq0405";
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
	ok          = ok && list.InitAll(false);
	auto* memory = Libs::LibKernel::Memory::MemorySubsystem::Instance();
	list.Add(memory, {core, log});
	ok = ok && list.InitAll(false);
	if (!ok) {
		SetupFail(Fmt("the subsystems did not start: %s: %s", list.GetFailName(), list.GetFailMsg()));
	}
}

} // namespace eq0405

int main(int argc, char** argv) {
	using namespace eq0405;
	const char* e_eq = std::getenv("KYTY_BC5_EQUEUE_FIXES");
	const char* e_mm = std::getenv("KYTY_BC5_MMAP_SHIM_FIXES");
	g_eq             = ExpectEq(e_eq);
	g_mm             = ExpectMm(e_mm);
	const char* mode = (g_eq == EQ_ALL && g_mm == MM_ALL) ? "on" : (g_eq == 0 && g_mm == 0) ? "off" : "mixed";
	if (argc > 2 || (argc == 2 && std::strcmp(argv[1], mode) != 0)) {
		std::printf("eq0405: the argument says %s but the switches say %s (equeue 0x%x, mmap 0x%x)\n",
		            argc == 2 ? argv[1] : "too much", mode, g_eq, g_mm);
		return 2;
	}
	std::thread(Watchdog).detach();

	InitSubsystems();
	g_case = "init: registration";
	static Loader::SymbolDatabase db;
	Libs::InitAll(&db);
	g_db = &db;
	std::printf("eq0405: KYTY_BC5_EQUEUE_FIXES=%s KYTY_BC5_MMAP_SHIM_FIXES=%s, so %s (equeue items 0x%x, mmap items 0x%x)\n",
	            e_eq != nullptr ? e_eq : "(unset)", e_mm != nullptr ? e_mm : "(unset)", mode, g_eq, g_mm);
	std::fflush(stdout);
	const auto     kevent_shim = Fn<FnKevent>(kKevent);
	const auto     mmap_shim   = Fn<FnMmap>(kMmap);
	const uint64_t start  = NowNs();

	CaseGrammar(e_eq, e_mm);
	CaseLevel();
	CaseEdge();
	CaseAmpr();
	CaseEop();
	CaseFlip();
	CaseUserInterrupt();
	CaseMixed();
	CaseNullOut();
	CaseKevent(kevent_shim);
	CaseTimer();
	CaseMmap(mmap_shim);

	g_finished       = true;
	const int passed = g_passed.load();
	const int cases  = g_cases.load();
	if (passed != cases) {
		std::printf("eq0405: %s %d of %d passed in %llu ms; FAIL\n", mode, passed, cases,
		            static_cast<unsigned long long>(MsSince(start)));
		std::fflush(stdout);
		std::_Exit(1);
	}
	if (std::strcmp(mode, "mixed") == 0) {
		std::printf("eq0405: mixed equeue=0x%x mmap=0x%x %d of %d; end\n", g_eq, g_mm, passed, cases);
	} else {
		std::printf("eq0405: %s %d of %d; end\n", mode, passed, cases);
	}
	std::fflush(stdout);
	std::fflush(stderr);
	std::_Exit(0);
}
