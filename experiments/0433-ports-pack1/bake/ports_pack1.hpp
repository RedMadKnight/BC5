// SPDX-License-Identifier: GPL-2.0-only
// Ports pack 1, BUILT IN (exp 0433, 2026-11-19): fixes ported from KytyPS5 (GPL-2.0) and AnyPS5 (GPL-2.0), every one
// on, with no switch: the KYTY_BC5_P1_* words are gone and nothing reads the environment. A call site's
// BC5_P1("KYTY_BC5_P1_<NAME>") is a constant `true`, so each site runs the path tested as arm P in exp 0433
// (experiments/0433-ports-pack1/README.md: 12 fight runs and 2 ASTRO BOT runs, no cost outside run-to-run noise).
// The site's old path is still in the source but can never be taken; the name is checked at compile time.
//
// Hit counts, normal build only (compiled out of the lean build with the rest of the diagnostics, exp 0419): a hit is
// one pass of a fix's decision point, counted per thread and added to the global count in batches of 256 (the first 64
// hits of a fix at once), so the count is a lower bound. A line is printed when a fix's count passes a power of two:
//   [bc5] ports pack 1 hits: PTHREAD_KEYS 1024 (t 12.3 s)   (t: seconds since the first hit of any fix)
#pragma once

#include <atomic>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>

namespace bc5::p1 {

// The fixes of the pack, in the order of the per-fix table (experiments/0433-ports-pack1/README.md).
inline constexpr const char* kNames[] = {
    "EQ_WAKE_ALL",      // A1  AnyPS5 daad982457: equeue add/trigger wakes every waiter
    "NO_COND_REGISTRY", // A2  KytyPS5 18a1e0fa: no global CondVar waiter registry
    "FAULT_MASK",       // A3  KytyPS5 3b0a78a9: the fault handler masks the guest signal too
    "SEMA_UAF",         // A6  AnyPS5 ff9a68aed4: semaphore delete waits for its waiters to leave
    "AMPR_RESULT",      // B1  AnyPS5 23a0020ab1: submit does not overwrite the worker's result
    "APR_FILE_ID",      // K1  KytyPS5 e43aadf7: APR file ids from a counter, not a path hash
    "COND_SIGNAL_ONE",  // K2  KytyPS5 47b26e49: pthread_cond_signal wakes the chosen waiter only
    "ALTSTACK",         // K6  KytyPS5 21124245/b61360a0: per-thread signal stacks
    "PTHREAD_KEYS",     // K3  KytyPS5 733842ca: pthread key values per thread
    "PROT_RANGES",      // K4  KytyPS5 73363f12: no per-page protection map
    "FILE_UNBUFFERED",  // K7  KytyPS5 cbe5b629: unbuffered host file handles
    "AJM_GAPLESS",      // R2a KytyPS5 2e315a3c/1cc0ac7e: AJM gapless control before codec init
    "AMPR_FILTER",      // R2b KytyPS5 deb45a8b: APR completions on the AMPR filter (-25)
    "FATAL_TO_ERROR",   // C   AnyPS5: error codes in place of host exits
};

inline constexpr int kCount = static_cast<int>(sizeof(kNames) / sizeof(kNames[0]));

constexpr bool Same(const char* a, const char* b) {
	while (*a != 0 && *a == *b) {
		a++;
		b++;
	}
	return *a == *b;
}

// "KYTY_BC5_P1_<NAME>" -> its index, at compile time (the call site's string is not in the binary); -1 if unknown.
constexpr int Index(const char* word) {
	const char* const prefix = "KYTY_BC5_P1_";
	for (int k = 0; k < 12; k++) {
		if (word[k] != prefix[k]) return -1;
	}
	for (int i = 0; i < kCount; i++) {
		if (Same(kNames[i], word + 12)) return i;
	}
	return -1;
}

#ifdef BC5_LEAN
inline void Hit(int) {}
#else
struct alignas(64) HitSlot {
	std::atomic<uint64_t> n {0};
};

inline double Seconds() {
	static const auto t0 = std::chrono::steady_clock::now();
	return std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
}

inline void Hit(int i) {
	static HitSlot g[kCount];
	thread_local uint32_t pend[kCount] {};
	uint32_t p = ++pend[i];
	if (p < 256 && g[i].n.load(std::memory_order_relaxed) >= 64) return;
	pend[i] = 0;
	uint64_t before = g[i].n.fetch_add(p, std::memory_order_relaxed);
	uint64_t after  = before + p;
	if (before == 0 || (63 - __builtin_clzll(before)) != (63 - __builtin_clzll(after))) {
		std::fprintf(stderr, "[bc5] ports pack 1 hits: %s %llu (t %.1f s)\n", kNames[i], static_cast<unsigned long long>(after),
		             Seconds());
	}
}
#endif

} // namespace bc5::p1

// Always true: the fix is built in. `name` must be one of the pack's words (checked at compile time).
#define BC5_P1(name)                                                                                                   \
	([] {                                                                                                              \
		constexpr int bc5_p1_i = ::bc5::p1::Index(name);                                                              \
		static_assert(bc5_p1_i >= 0, "BC5_P1: not a word of ports pack 1");                                           \
		::bc5::p1::Hit(bc5_p1_i);                                                                                     \
		return true;                                                                                                   \
	}())
