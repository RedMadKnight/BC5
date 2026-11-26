#!/usr/bin/env python3
"""BC5 exp 0429: rrshared0429.cpp, the shared form of candidate R, from the tested private block rr0429.cpp (build 14).
    mkrshared0429.py            writes rrshared0429.cpp next to this script
The maintainer, 2026-11-18 (through the top session): R on by default in the shared builds, and at once a clean-up of what R makes unneeded. What changes
against build 14, and nothing else:
  - one rule, the worker-family sleepers (build 13's mode 3, the one tested on the box under rtkit 64: h429K17/K18,
    rep15, a429C); modes 1 and 2 and the pool table of mode 2 are gone. KYTY_BC5_0429_RR: on unless "0" (kSoft gives
    "1"); any other value is the same rule;
  - the reserve is fixed at 4 places (build 14's default; KYTY_BC5_0429_RESERVE is gone);
  - lean: no diagnostics at all. The minute count line, the counters and the event ring are normal-build only (the
    count line in lean was this experiment's only, 2026-11-17).
Every anchor must occur once."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
s = open(os.path.join(HERE, 'rr0429.cpp'), encoding='utf-8').read()


def rep(a, b, what):
    global s
    if s.count(a) != 1:
        sys.exit('mkrshared0429 STOP: %s: anchor occurs %d times' % (what, s.count(a)))
    s = s.replace(a, b)


def cut(a, b, new, what):  # replaces from anchor a up to (not including) anchor b
    global s
    if s.count(a) != 1 or s.count(b) != 1 or s.index(a) > s.index(b):
        sys.exit('mkrshared0429 STOP: %s: anchors' % what)
    i, j = s.index(a), s.index(b)
    s = s[:i] + new + s[j:]


HEADER = '''
// ---- experiment 0429 R: the console's "a lower number wins" for the guest's job workers ----------------------------
// Shared since 2026-11-18 (the maintainer's word), on by default for every title through kSoft in
// bc5/switch_defaults.hpp; KYTY_BC5_0429_RR=0 turns it off with no build. It replaces exp 0359's JobArenaFix (removed
// 2026-11-17) and exp 0425's wake slice (removed with this change).
// On the console a woken job worker takes its CPU at once from any lower-priority thread there (TODO(verify): the
// console's kernel; the title's own priorities and masks, exp 0429's trace). Here a woken worker waited behind threads
// of lower guest priority (h429Z1: 18 % of the job-semaphore wakes took 0.1-2 ms) while the title's main thread ran the
// job itself (the second title's fight crash at eboot+0x3d7eca0).
// The rule, for any title and with no title rows: a guest thread of a worker family (two or more threads whose names
// differ only by a trailing index, "Job Hi 0".."Job Hi 7") that sleeps on a guest semaphore its family shares gets
// SCHED_RR from RealtimeKit1 (rtkit, the system bus; no privilege of our own), with an RR priority in the guest's order
// (a lower guest number, a higher RR priority), if its guest priority is below 700. A lone thread (an audio manager) and
// the runtime's main thread are never promoted.
// Bounds (the box runs with RT throttling off, sched_rt_runtime_us = period):
//   1. RLIMIT_RTTIME on the process: soft 20 ms of RR time without blocking -> SIGXCPU, whose handler drops the running
//      RR thread back to SCHED_OTHER for good (a spinner); hard 200 ms -> the kernel ends the emulator (never the box);
//   2. a watchdog thread every 5 ms: an RR thread that ran 100 ms with no new time slice is dropped for good;
//   3. at most (online CPUs - 2) guest threads hold RR at once, so host threads always have two CPUs.
// When the cap is full, the holder with the numerically highest guest priority above a newcomer's is evicted; it comes
// back at a later sleep when a place is free. rtkit's calls: at most 15 per 20 s window; a refusal stops new promotions
// until the window turns, except to replace an evicted thread.
// rtkit's room: rtkit serves at most --threads-per-user-max threads of one user (read from its command line; 25 by
// default, 64 on the box since 2026-11-18 08:17, the maintainer's word), counting every thread of the user it made RT or
// nice < 0 that still is. The watchdog counts them once a second from /proc (processes with CAP_SYS_NICE, which set
// their own priorities, left out), and R promotes only while that count + 1 + 4 fits, so 4 places stay for the
// emulator's own audio threads and PipeWire. A thread denied for room or budget is promoted at a later sleep.
// Tested on the box (exp 0429, 2026-11-17/18): under the crash stressor 4 of 4 clean with R against 7 of 9 crashed
// without; all 8 Job Hi workers RR with 0 rtkit refusals (rtkit 64); fps with and without R within run-to-run spread on
// both titles. Normal build: every promotion, drop and refusal is logged (the first 200) and one count line a minute;
// the lean build logs nothing.
'''
cut('\n// ---- experiment 0429 candidate R:', '#if KYTY_PLATFORM == KYTY_PLATFORM_LINUX\n#include <dirent.h>', HEADER, 'header')

cut('// KYTY_BC5_0429_RR: 0 or unset off;', 'constexpr int     kMaxSlots   = 64;\n', '''static bool On() { // KYTY_BC5_0429_RR, on unless "0" (kSoft gives "1")
	static const bool v = [] {
		const bool on = bc5::env_rule::on(std::getenv("KYTY_BC5_0429_RR"));
#ifndef BC5_LEAN
		std::fprintf(stderr, "[bc5] exp 0429: R (RR for the guest's worker-family sleepers) %s\\n", on ? "ON" : "off");
#endif
		return on;
	}();
	return v;
}
''', 'Mode')

rep('''static int Reserve() { // build 13: rtkit places left for the emulator's own and others' requests; build 14: KYTY_BC5_0429_RESERVE (0-10), default 4
	static const int v = [] {
		const char* e = std::getenv("KYTY_BC5_0429_RESERVE");
		return (e != nullptr && e[0] >= '0' && e[0] <= '9') ? std::clamp(std::atoi(e), 0, 10) : 4;
	}();
	return v;
}
''', '''constexpr int           kReserve = 4;          // rtkit places left for the emulator's own and others' requests
''', 'Reserve')

rep('''static std::atomic<int> g_spinner_tid[kMaxSlots]; // dropped for good
// build 11: counters in both builds (lean too: one stderr line a minute from the watchdog thread, for this experiment
// only; it goes from lean before any swap), and the last 16 losses as kind and guest priority
enum Ev''', '''static std::atomic<int> g_spinner_tid[kMaxSlots]; // dropped for good
// counters and the last 16 losses as kind and guest priority (normal build only: the count line a minute)
enum Ev''', 'counters comment')
rep('''static const char       kEvName[kEvN] = {'P', 'R', 'C', 'B', 'E', 'X', 'W', 'H', 'G', 'N'};
static std::atomic<int> g_ev[kEvN];
static std::atomic<int> g_last[16];
static std::atomic<int> g_last_n {0};
static void Count(Ev e, int prio) { // async-signal-safe
	g_ev[e].fetch_add(1, std::memory_order_relaxed);
	if (e == kPromoted || e == kCapDenied || e == kRoomDenied) {
		return; // the ring keeps the losses: drops, evictions, refusals, budget denials
	}
	g_last[g_last_n.fetch_add(1, std::memory_order_relaxed) & 15].store(e * 10000 + (prio < 0 ? 9999 : prio), std::memory_order_relaxed);
}''', '''#ifndef BC5_LEAN
static const char       kEvName[kEvN] = {'P', 'R', 'C', 'B', 'E', 'X', 'W', 'H', 'G', 'N'};
static std::atomic<int> g_ev[kEvN];
static std::atomic<int> g_last[16];
static std::atomic<int> g_last_n {0};
#endif
static void Count(Ev e, int prio) { // async-signal-safe
#ifndef BC5_LEAN
	g_ev[e].fetch_add(1, std::memory_order_relaxed);
	if (e == kPromoted || e == kCapDenied || e == kRoomDenied) {
		return; // the ring keeps the losses: drops, evictions, refusals, budget denials
	}
	g_last[g_last_n.fetch_add(1, std::memory_order_relaxed) & 15].store(e * 10000 + (prio < 0 ? 9999 : prio), std::memory_order_relaxed);
#else
	(void)e;
	(void)prio;
#endif
}''', 'Count')
rep('''		{ // build 14: a process with CAP_SYS_NICE''', '''		{ // a process with CAP_SYS_NICE''', 'capnice comment')
rep('''static bool HasWorseHolder(int prio) { // a holder of a numerically higher guest priority (build 14)''',
    '''static bool HasWorseHolder(int prio) { // a holder of a numerically higher guest priority''', 'worse comment')
rep('''static bool RoomOk() { // one more RR thread leaves Reserve() of rtkit's places
	const int u = g_user_rt.load(std::memory_order_relaxed);
	return u >= 0 && u + 1 + Reserve() <= g_rtkit_max;''', '''static bool RoomOk() { // one more RR thread leaves kReserve of rtkit's places
	const int u = g_user_rt.load(std::memory_order_relaxed);
	return u >= 0 && u + 1 + kReserve <= g_rtkit_max;''', 'RoomOk')
rep('''	             g_rtkit_max, g_user_rt.load(), Reserve());''', '''	             g_rtkit_max, g_user_rt.load(), kReserve);''', 'watchdog line')
rep('''		if (tick % 200 == 0) { // build 13: rtkit's count of the user, once a second
			g_user_rt.store(UserRtThreads());
		}
		if (tick % 12000 == 0) { // about a minute''', '''		if (tick % 200 == 0) { // rtkit's count of the user, once a second
			g_user_rt.store(UserRtThreads());
		}
#ifndef BC5_LEAN
		if (tick % 12000 == 0) { // about a minute''', 'count line open')
rep('''			             g_user_rt.load(), g_rtkit_max, last);
		}
''', '''			             g_user_rt.load(), g_rtkit_max, last);
		}
#endif
''', 'count line close')
rep('''static char             g_rtkit_err[200] {};   // build 13: the last refusal's D-Bus error, name: message''',
    '''static char             g_rtkit_err[200] {};   // the last refusal's D-Bus error, name: message''', 'err comment')
rep('''	if (cap_full || !RoomOk()) { // build 14: a short rtkit room evicts like a full cap''',
    '''	if (cap_full || !RoomOk()) { // a short rtkit room evicts like a full cap''', 'apply comment')
rep('''		MarkEvicted(victim); // build 12: it comes back at a later sleep when a place is free''',
    '''		MarkEvicted(victim); // it comes back at a later sleep when a place is free''', 'evict comment')
rep('''		MarkEvicted(tid); // build 13: waits for room, promoted at a later sleep''',
    '''		MarkEvicted(tid); // waits for room, promoted at a later sleep''', 'room comment')
rep('''		MarkEvicted(tid); // build 13: waits, promoted at a later sleep (it was lost for good before)''',
    '''		MarkEvicted(tid); // waits, promoted at a later sleep''', 'budget comment')
rep('''constexpr int64_t        kWindowMs  = 20000; // build 12: the rtkit budget per window''',
    '''constexpr int64_t        kWindowMs  = 20000; // the rtkit budget per window''', 'window comment')
rep('''static std::atomic<int> g_user_rt {-1};        // the user's RT or nice < 0 threads (rtkit's count), -1 before the first scan''',
    '''static std::atomic<int> g_user_rt {-1};        // the user's RT or nice < 0 threads (rtkit's count), -1 before the first scan''', 'noop')

cut('''// A guest thread's sleep on a guest semaphore (kernel/semaphore.cpp, after the resume): mark it a sleeper. Mode 2:''',
    '''namespace bc5_0429r {
constexpr int kPools = 512;''', '''// A guest thread's sleep on a guest semaphore (kernel/semaphore.cpp, after the resume, under the semaphore's lock): mark
// it a sleeper when the semaphore belongs to its worker family. A thread that slept on it first is marked at its next
// sleep there.
''', 'pool comment')
rep('''namespace bc5_0429r {
constexpr int kPools = 512;
struct PoolSlot {
	std::atomic<uintptr_t> sem {0};
	std::atomic<int>       first {0};
	std::atomic<bool>      pool {false};
};
static PoolSlot g_pools[kPools];
// build 13, mode 3: a semaphore's worker family.''', '''namespace bc5_0429r {
constexpr int kPools = 512;
// A semaphore's worker family.''', 'pool table')
cut('''static bool     IsPool(const void* sem, int tid) {''', '''} // namespace bc5_0429r
extern "C" void bc5_0429_r_on_sleep''', '', 'IsPool')
rep('''	if (self->bc5_rr_sleeper) { // build 12: an evicted sleeper comes back when a place is free''',
    '''	if (self->bc5_rr_sleeper) { // an evicted sleeper comes back when a place is free''', 'sleeper comment')
rep('''	if (bc5_0429r::Mode() == 2 && !bc5_0429r::IsPool(sem, static_cast<int>(self->host_thread_id))) {
		return;
	}
	if (bc5_0429r::Mode() == 3 && !bc5_0429r::IsFamilyPool(''', '''	if (!bc5_0429r::IsFamilyPool(''', 'on_sleep modes')
rep('''// ---- end of experiment 0429 candidate R ---''', '''// ---- end of experiment 0429 R -----------''', 'end')

for bad in ('Mode()', 'Reserve()', 'RESERVE', 'IsPool(', 'build 1', 'g_pools'):
    if bad in s:
        sys.exit('mkrshared0429 STOP: "%s" is left' % bad)
open(os.path.join(HERE, 'rrshared0429.cpp'), 'w', encoding='utf-8', newline='\n').write(s)
print('mkrshared0429: rrshared0429.cpp, %d lines' % s.count('\n'))
