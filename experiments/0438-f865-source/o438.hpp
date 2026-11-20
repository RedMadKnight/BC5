// SPDX-License-Identifier: GPL-2.0
// BC5 experiment 0438 (tag o438): which wait the Render Thread and game-main are blocked in, and who wakes them.
// Records only, normal build only (BC5_LEAN: every macro is empty), off unless BC5_0438_OUTSIDE=1.
//   BC5_O438_WAIT(fn, obj)  at the top of a sync HLE that can block: a scoped span; only the outermost span of a
//                           thread counts (a cond wait re-locking its mutex is the cond wait's time). Recorded for the
//                           Render Thread (role 1) and game-main (role 2), found by the OS thread name.
//   BC5_O438_SIGNAL(obj)    at a site that can wake a waiter of obj (unlock, signal, post, set, trigger, wake): the
//                           calling thread's tid is stored for obj in a hashed table (a race only mis-attributes).
//   BC5_O438_FLIP()         at each flip: a frame over 100 ms prints the roles' spans inside it; every 60 s the totals.
// A span of 50 us or more counts as blocked; its waker is the last signaller of its object (tid -> /proc comm at print).
// Output: stderr lines "o438 (exp 0438): ..." (play.log), so the runner keeps them with the run.
#pragma once
#ifdef BC5_LEAN
#define BC5_O438_WAIT(fn, obj)
#define BC5_O438_SIGNAL(obj)
#define BC5_O438_FLIP()
#else
#include <pthread.h>
#include <sys/syscall.h>
#include <unistd.h>

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cinttypes>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <map>
#include <mutex>
#include <string>
#include <utility>
#include <vector>

// test_o438.sh's stub <pthread.h> defines these two; the build gets stderr and /proc
#ifndef BC5_O438_PRINTF
#define BC5_O438_PRINTF(...) std::fprintf(stderr, __VA_ARGS__)
#endif
namespace bc5::o438 {
enum Fn : int { kWaitSema, kPosixSemWait, kPthreadSemWait, kWaitEventFlag, kMutexLock, kCondWait, kWaitEqueue, kUsleep, kNanosleep, kSyncOnAddressWait, kJoin, kYield, kFnN };
inline const char* const kFnName[kFnN] = {"KernelWaitSema", "sem_wait/timedwait", "PthreadSemWait/Timedwait", "KernelWaitEventFlag", "PthreadMutexLock/Timedlock",
                                          "PthreadCondWait/Timedwait", "KernelWaitEqueue", "KernelUsleep", "KernelNanosleep", "KernelSyncOnAddressWait", "PthreadJoin", "PthreadYield"};
inline const char* const kRoleName[3] = {"other", "Render Thread", "game-main"};
inline bool on() {
	static const bool v = [] {
		const char* e = std::getenv("BC5_0438_OUTSIDE");
		return e != nullptr && e[0] == '1' && e[1] == 0;
	}();
	return v;
}
template <typename T>
inline const void* as_obj(T* p) { // any object pointer, volatile ones too: only its value is a key
	return reinterpret_cast<const void*>(reinterpret_cast<uintptr_t>(p));
}
inline const void* as_obj(std::nullptr_t) { return nullptr; }
inline const void* as_obj(int64_t h) { // a handle (KernelEqueue): its value, tagged apart from pointers
	return reinterpret_cast<const void*>(static_cast<uintptr_t>(h) | (static_cast<uintptr_t>(1) << 63u));
}
inline uint64_t now_ns() { return static_cast<uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now().time_since_epoch()).count()); }
inline uint32_t my_tid() {
	thread_local const uint32_t t = static_cast<uint32_t>(::syscall(SYS_gettid));
	return t;
}
// 1 Render Thread, 2 game-main, 0 other; the name is read again now and then until it is one of the two
inline int role() {
	thread_local int      r = 0;
	thread_local uint32_t k = 0;
	if (r == 0 && (k++ & 255u) == 0) {
		char n[32] = {};
		pthread_getname_np(pthread_self(), n, sizeof(n));
		if (std::strncmp(n, "Render", 6) == 0) r = 1;
		else if (std::strcmp(n, "game-main") == 0) r = 2;
	}
	return r;
}
inline int& depth() {
	thread_local int d = 0;
	return d;
}
struct Slot {
	std::atomic<const void*> obj {nullptr};
	std::atomic<uint32_t>    tid {0};
};
inline constexpr size_t kSlots = 8192;
inline Slot             g_slots[kSlots];
inline size_t           slot_of(const void* o) {
	const auto x = reinterpret_cast<uintptr_t>(o);
	return static_cast<size_t>((x >> 3u) ^ (x >> 15u) ^ (x >> 29u)) & (kSlots - 1);
}
inline void signal(const void* o) {
	if (!on() || o == nullptr) return;
	Slot& s = g_slots[slot_of(o)];
	s.tid.store(my_tid(), std::memory_order_relaxed);
	s.obj.store(o, std::memory_order_release);
}
inline uint32_t waker_of(const void* o) {
	if (o == nullptr) return 0;
	const Slot& s = g_slots[slot_of(o)];
	return s.obj.load(std::memory_order_acquire) == o ? s.tid.load(std::memory_order_relaxed) : 0;
}
struct Agg {
	uint64_t n = 0, ns = 0, max = 0, blocked = 0, blocked_ns = 0;
	void add(uint64_t d) {
		n++;
		ns += d;
		if (d > max) max = d;
		if (d >= 50'000) {
			blocked++;
			blocked_ns += d;
		}
	}
};
struct Rec {
	std::mutex                                     m;
	Agg                                            tot[3][kFnN], frame[3][kFnN];
	std::map<std::pair<int, uint32_t>, uint64_t>   wake[3], frame_wake[3]; // (fn, waker tid) -> blocked ns
	uint64_t                                       last_flip = 0, last_line = 0, frames = 0, long_frames = 0;
};
inline Rec& rec() {
	static Rec r;
	return r;
}
inline void record(int r, int fn, const void* obj, uint64_t d) {
	const uint32_t w = d >= 50'000 ? waker_of(obj) : 0;
	Rec&           R = rec();
	std::lock_guard lk(R.m);
	R.tot[r][fn].add(d);
	R.frame[r][fn].add(d);
	if (d >= 50'000) {
		R.wake[r][{fn, w}] += d;
		R.frame_wake[r][{fn, w}] += d;
	}
}
struct Span {
	int         fn = 0, r = 0;
	const void* obj = nullptr;
	uint64_t    t0  = 0;
	bool        top = false;
	Span(int f, const void* o) {
		if (!on()) return;
		r = role();
		if (r == 0) return;
		fn  = f;
		obj = o;
		top = depth()++ == 0;
		t0  = now_ns();
	}
	~Span() {
		if (r == 0) return;
		depth()--;
		if (top) record(r, fn, obj, now_ns() - t0);
	}
	Span(const Span&)            = delete;
	Span& operator=(const Span&) = delete;
};
inline std::string comm(uint32_t tid) {
	if (tid == 0) return "unknown";
#ifdef BC5_O438_COMM_STUB
	return BC5_O438_COMM_STUB(tid) + ":" + std::to_string(tid);
#endif
	char path[64];
	std::snprintf(path, sizeof(path), "/proc/self/task/%u/comm", tid);
	char  b[64] = {};
	FILE* f     = std::fopen(path, "r");
	if (f == nullptr) return "gone:" + std::to_string(tid);
	const size_t n = std::fread(b, 1, sizeof(b) - 1, f);
	std::fclose(f);
	std::string s(b, n);
	while (!s.empty() && (s.back() == '\n' || s.back() == '\r')) s.pop_back();
	return s + ":" + std::to_string(tid);
}
// one role's spans, largest blocked time first: "fn n/blocked total/blocked ms (wakers: name ms, ...)"
inline std::string line_of(const Agg (&a)[kFnN], const std::map<std::pair<int, uint32_t>, uint64_t>& wk, int max_fns) {
	std::vector<int> order;
	for (int f = 0; f < kFnN; f++)
		if (a[f].n != 0) order.push_back(f);
	std::sort(order.begin(), order.end(), [&a](int x, int y) { return a[x].ns > a[y].ns; });
	std::string out;
	char        b[512];
	int         k = 0;
	for (const int f: order) {
		if (k++ >= max_fns) break;
		std::snprintf(b, sizeof(b), "%s%s %" PRIu64 "/%" PRIu64 " calls %.1f/%.1f ms max %.1f ms", out.empty() ? "" : "; ", kFnName[f], a[f].n, a[f].blocked, static_cast<double>(a[f].ns) / 1e6,
		              static_cast<double>(a[f].blocked_ns) / 1e6, static_cast<double>(a[f].max) / 1e6);
		out += b;
		std::vector<std::pair<uint64_t, uint32_t>> ws;
		for (const auto& [key, ns]: wk)
			if (key.first == f) ws.emplace_back(ns, key.second);
		std::sort(ws.rbegin(), ws.rend());
		if (!ws.empty()) {
			out += " (wakers:";
			for (size_t i = 0; i < ws.size() && i < 4; i++) {
				std::snprintf(b, sizeof(b), "%s %s %.1f ms", i ? "," : "", comm(ws[i].second).c_str(), static_cast<double>(ws[i].first) / 1e6);
				out += b;
			}
			out += ")";
		}
	}
	return out.empty() ? "none" : out;
}
// exp 0438 (tag h438): h438.hpp's per-frame hook, called at each flip with the Render Thread's spans of the frame
// (all zero unless BC5_0438_OUTSIDE=1), before they are reset; nullptr unless h438.hpp is in the program
inline void (*g_flip_hook)(const Agg (&)[kFnN]) = nullptr;
inline void flip() {
	if (!on()) {
		if (g_flip_hook != nullptr) {
			static const Agg none[kFnN] = {};
			g_flip_hook(none);
		}
		return;
	}
	Rec&            R = rec();
	std::lock_guard lk(R.m);
	if (g_flip_hook != nullptr) g_flip_hook(R.frame[1]);
	const uint64_t  t        = now_ns();
	const uint64_t  interval = R.last_flip != 0 ? t - R.last_flip : 0;
	R.last_flip              = t;
	R.frames++;
	if (R.last_line == 0) R.last_line = t;
	if (interval > 100'000'000ull) {
		R.long_frames++;
		BC5_O438_PRINTF("o438 (exp 0438): frame of %.1f ms: Render Thread [%s]; game-main [%s]\n", static_cast<double>(interval) / 1e6, line_of(R.frame[1], R.frame_wake[1], 5).c_str(),
		             line_of(R.frame[2], R.frame_wake[2], 5).c_str());
	}
	for (int r = 0; r < 3; r++) {
		for (auto& a: R.frame[r]) a = Agg {};
		R.frame_wake[r].clear();
	}
	if (t - R.last_line >= 60'000'000'000ull) {
		R.last_line = t;
		for (int r = 1; r < 3; r++)
			BC5_O438_PRINTF("o438 (exp 0438): 60-s totals (frames %" PRIu64 ", over 100 ms %" PRIu64 "), %s: %s\n", R.frames, R.long_frames, kRoleName[r], line_of(R.tot[r], R.wake[r], kFnN).c_str());
	}
}
} // namespace bc5::o438
#define BC5_O438_WAIT(fn, obj) const ::bc5::o438::Span bc5_o438_span_(::bc5::o438::fn, ::bc5::o438::as_obj(obj))
#define BC5_O438_SIGNAL(obj)   ::bc5::o438::signal(::bc5::o438::as_obj(obj))
#define BC5_O438_FLIP()        ::bc5::o438::flip()
#endif
