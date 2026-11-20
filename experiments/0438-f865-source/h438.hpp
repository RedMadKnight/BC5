// SPDX-License-Identifier: GPL-2.0
// BC5 experiment 0438 (tag h438): where the Render Thread's host-side time goes, one CSV line per frame (flip to flip).
// Records only, normal build only (BC5_LEAN: every macro is empty), off unless BC5_0438_HOSTWAIT=1. Needs o438.hpp
// (its Render Thread detection, its clock and its flip, which calls h438's frame hook before it resets the frame);
// o438's guest-sync columns are filled only when BC5_0438_OUTSIDE=1 too.
//   BC5_H438_GC(request)    at the top of gc_ioctl: a scoped span, wall and thread CPU, by request code (outermost only)
//   BC5_H438_FLIPSPAN()     at the top of VideoOutSubmitEopFlip: a scoped span
//   BC5_H438_DRAIN_BEGIN()/BC5_H438_DRAIN_END()  around its Direct::drain()
//   BC5_H438_LOCK_ID(id, name, stmt)  a lock site: the time from before stmt (a std::lock_guard / unique_lock declaration) to
//                           after it is the acquisition wait; recorded by site ("mutex@line", the unit line before
//                           mkh438.py) when 20 us or more, the count always
// Per frame (the Render Thread, from o438's flip): wall; thread CPU and run-queue delay and timeslices from
// /proc/self/task/<tid>/schedstat; minor / major faults from /proc/self/task/<tid>/stat; gc calls by code (n, wall us,
// blocked us = wall - CPU); the flip span and its drain; lock waits by name; o438's blocked guest-sync time by kind.
// File: $BC5_0438_HOSTWAIT_FILE, else ~/bc5-work/exp0438/h438-<pid>.csv; written every 64 frames (a SIGTERM loses at
// most the last 63). One stderr line names the file.
#pragma once
#include "o438.hpp"
#ifdef BC5_LEAN
#define BC5_H438_GC(request)
#define BC5_H438_FLIPSPAN()
#define BC5_H438_DRAIN_BEGIN()
#define BC5_H438_DRAIN_END()
#define BC5_H438_LOCK_ID(id, name, stmt) stmt
#else
#include <time.h>

#include <cstdio>
#include <string>

#ifdef BC5_H438_CPU_STUB
#define BC5_H438_THREAD_CPU_NS() BC5_H438_CPU_STUB()
#else
#define BC5_H438_THREAD_CPU_NS() ::bc5::h438::thread_cpu_ns_real()
#endif
namespace bc5::h438 {
inline bool on() {
	static const bool v = [] {
		const char* e = std::getenv("BC5_0438_HOSTWAIT");
		return e != nullptr && e[0] == '1' && e[1] == 0;
	}();
	return v;
}
#ifndef BC5_H438_CPU_STUB
inline uint64_t thread_cpu_ns_real() {
	timespec ts {};
	clock_gettime(CLOCK_THREAD_CPUTIME_ID, &ts);
	return static_cast<uint64_t>(ts.tv_sec) * 1'000'000'000ull + static_cast<uint64_t>(ts.tv_nsec);
}
#endif
// the gc codes kept apart; every other code is "other"
inline constexpr uint64_t kCode[] = {0xc0488131, 0xc0188132, 0xc0108102, 0xc020810c, 0xc0048116, 0xc0048117, 0xc0088133, 0xc0108139};
inline constexpr int      kCodes  = static_cast<int>(sizeof(kCode) / sizeof(kCode[0])) + 1;
inline int                code_ix(uint64_t r) {
    for (int i = 0; i < kCodes - 1; i++)
        if (kCode[i] == r) return i;
    return kCodes - 1;
}
struct Acc {
	uint64_t n = 0, wall = 0, cpu = 0;
};
inline constexpr int kLocks = 512; // lock sites (mkh438.py gives each site its id)
struct Frame {
	Acc         gc[kCodes], flip, drain;
	uint64_t    lock_n[kLocks] = {}, lock_wait[kLocks] = {};
	const char* lock_name[kLocks] = {};
};
struct State {
	std::mutex            m;
	Frame                 f;
	std::atomic<uint32_t> rt_tid {0};
	uint64_t              first = 0, last = 0, cpu0 = 0, runq0 = 0, slices0 = 0, minflt0 = 0, majflt0 = 0, frames = 0;
	bool                  have0 = false;
	std::string           buf;
	FILE*                 out = nullptr;
};
inline State& st() {
	static State s;
	return s;
}
inline bool mine() { // the Render Thread, with h438 on
	if (!on() || ::bc5::o438::role() != 1) return false;
	State& S = st();
	if (S.rt_tid.load(std::memory_order_relaxed) == 0) S.rt_tid.store(::bc5::o438::my_tid(), std::memory_order_relaxed);
	return true;
}
inline int& gc_depth() {
	thread_local int d = 0;
	return d;
}
inline void add(Acc& a, uint64_t w, uint64_t c) {
	a.n++;
	a.wall += w;
	a.cpu += c < w ? c : w;
}
// a gc call: the outermost one of the thread counts (a gc call made inside a gc call is its caller's time)
struct GcSpan {
	bool     active = false, nested = false;
	int      ix     = 0;
	uint64_t t0 = 0, c0 = 0;
	explicit GcSpan(uint64_t request) {
		if (!mine()) return;
		if (gc_depth()++ != 0) {
			nested = true;
			return;
		}
		active = true;
		ix     = code_ix(request);
		t0     = ::bc5::o438::now_ns();
		c0     = BC5_H438_THREAD_CPU_NS();
	}
	~GcSpan() {
		if (!active && !nested) return;
		gc_depth()--;
		if (nested) return;
		const uint64_t  w = ::bc5::o438::now_ns() - t0, c = BC5_H438_THREAD_CPU_NS() - c0;
		State&          S = st();
		std::lock_guard lk(S.m);
		add(S.f.gc[ix], w, c);
	}
	GcSpan(const GcSpan&)            = delete;
	GcSpan& operator=(const GcSpan&) = delete;
};
// the flip (kind 1) or its drain (kind 2)
struct Span {
	int      kind = 0;
	bool     active = false;
	uint64_t t0 = 0, c0 = 0;
	explicit Span(int k) : kind(k) {
		if (!mine()) return;
		active = true;
		t0     = ::bc5::o438::now_ns();
		c0     = BC5_H438_THREAD_CPU_NS();
	}
	~Span() {
		if (!active) return;
		const uint64_t  w = ::bc5::o438::now_ns() - t0, c = BC5_H438_THREAD_CPU_NS() - c0;
		State&          S = st();
		std::lock_guard lk(S.m);
		add(kind == 1 ? S.f.flip : S.f.drain, w, c);
	}
	Span(const Span&)            = delete;
	Span& operator=(const Span&) = delete;
};
inline uint64_t lock_t0() { return mine() ? ::bc5::o438::now_ns() : 0; }
inline void     lock_done(int id, const char* name, uint64_t t0) {
    if (t0 == 0 || id < 0 || id >= kLocks) return;
    const uint64_t  w = ::bc5::o438::now_ns() - t0;
    State&          S = st();
    std::lock_guard lk(S.m);
    S.f.lock_name[id] = name;
    S.f.lock_n[id]++;
    if (w >= 20'000) S.f.lock_wait[id] += w;
}
// /proc/self/task/<tid>/schedstat: cpu ns, run-queue ns, timeslices; .../stat: minflt (field 10), majflt (field 12)
#ifndef BC5_H438_PROC_STUB
inline bool proc_read(uint32_t tid, uint64_t& cpu, uint64_t& runq, uint64_t& slices, uint64_t& minflt, uint64_t& majflt) {
	char p[96];
	std::snprintf(p, sizeof(p), "/proc/self/task/%u/schedstat", tid);
	FILE* f = std::fopen(p, "r");
	if (f == nullptr) return false;
	unsigned long long a = 0, b = 0, c = 0;
	const int          n = std::fscanf(f, "%llu %llu %llu", &a, &b, &c);
	std::fclose(f);
	if (n != 3) return false;
	cpu    = a;
	runq   = b;
	slices = c;
	std::snprintf(p, sizeof(p), "/proc/self/task/%u/stat", tid);
	f = std::fopen(p, "r");
	if (f == nullptr) return false;
	char         s[1024] = {};
	const size_t k       = std::fread(s, 1, sizeof(s) - 1, f);
	std::fclose(f);
	const char* q = std::strrchr(s, ')'); // the comm may hold spaces; the fields start after its ')'
	if (q == nullptr || k == 0) return false;
	unsigned long long v[16] = {};
	// after ')': 3 state, 4 ppid, 5 pgrp, 6 session, 7 tty, 8 tpgid, 9 flags, 10 minflt, 11 cminflt, 12 majflt
	if (std::sscanf(q + 1, " %*c %llu %llu %llu %llu %llu %llu %llu %llu %llu", &v[4], &v[5], &v[6], &v[7], &v[8], &v[9], &v[10], &v[11], &v[12]) != 9) return false;
	minflt = v[10];
	majflt = v[12];
	return true;
}
#else
#define proc_read BC5_H438_PROC_STUB
#endif
inline std::string file_name() {
	const char* e = std::getenv("BC5_0438_HOSTWAIT_FILE");
	if (e != nullptr && e[0] != 0) return e;
	const char* h = std::getenv("HOME");
	return std::string(h != nullptr ? h : ".") + "/bc5-work/exp0438/h438-" + std::to_string(static_cast<long>(::getpid())) + ".csv";
}
inline void flush(State& S) {
	if (S.buf.empty()) return;
	if (S.out == nullptr) {
		const std::string n = file_name();
		S.out               = std::fopen(n.c_str(), "w");
		BC5_O438_PRINTF("h438 (exp 0438): per-frame records of the Render Thread in %s%s\n", n.c_str(), S.out == nullptr ? " (CANNOT OPEN)" : "");
		if (S.out == nullptr) {
			S.buf.clear();
			return;
		}
		std::string h = "t_s,frame_ms,cpu_ms,runq_ms,slices,minflt,majflt";
		for (int i = 0; i < kCodes; i++) {
			char b[64];
			if (i < kCodes - 1) std::snprintf(b, sizeof(b), "%08" PRIx64, kCode[i]);
			else std::snprintf(b, sizeof(b), "other");
			h += std::string(",gc_") + b + "_n,gc_" + b + "_wall_us,gc_" + b + "_blocked_us";
		}
		h += ",flip_n,flip_wall_us,flip_blocked_us,drain_wall_us,drain_blocked_us,lock_wait_us,locks,guest_blocked_us,guest\n";
		std::fputs(h.c_str(), S.out);
	}
	std::fputs(S.buf.c_str(), S.out);
	std::fflush(S.out);
	S.buf.clear();
}
inline void frame_hook(const ::bc5::o438::Agg (&guest)[::bc5::o438::kFnN]) {
	if (!on()) return;
	State&         S   = st();
	const uint32_t tid = S.rt_tid.load(std::memory_order_relaxed);
	if (tid == 0) return; // no Render Thread span yet
	const uint64_t t   = ::bc5::o438::now_ns();
	uint64_t       cpu = 0, runq = 0, slices = 0, minflt = 0, majflt = 0;
	const bool     ok  = proc_read(tid, cpu, runq, slices, minflt, majflt);
	std::lock_guard lk(S.m);
	if (!S.have0 || !ok) {
		S.have0 = ok;
		S.first = S.last = t;
		S.cpu0 = cpu, S.runq0 = runq, S.slices0 = slices, S.minflt0 = minflt, S.majflt0 = majflt;
		S.f = Frame {};
		return;
	}
	auto us = [](uint64_t ns) { return static_cast<double>(ns) / 1e3; };
	char b[512];
	std::snprintf(b, sizeof(b), "%.3f,%.3f,%.3f,%.3f,%" PRIu64 ",%" PRIu64 ",%" PRIu64, static_cast<double>(t - S.first) / 1e9, static_cast<double>(t - S.last) / 1e6,
	              static_cast<double>(cpu - S.cpu0) / 1e6, static_cast<double>(runq - S.runq0) / 1e6, slices - S.slices0, minflt - S.minflt0, majflt - S.majflt0);
	std::string line = b;
	for (const Acc& a: S.f.gc) {
		std::snprintf(b, sizeof(b), ",%" PRIu64 ",%.1f,%.1f", a.n, us(a.wall), us(a.wall - a.cpu));
		line += b;
	}
	uint64_t    lw = 0;
	std::string locks;
	for (int i = 0; i < kLocks; i++) {
		if (S.f.lock_n[i] == 0) continue;
		lw += S.f.lock_wait[i];
		if (S.f.lock_wait[i] == 0) continue;
		std::snprintf(b, sizeof(b), "%s%s=%.1f", locks.empty() ? "" : ";", S.f.lock_name[i] != nullptr ? S.f.lock_name[i] : "?", us(S.f.lock_wait[i]));
		locks += b;
	}
	uint64_t    gb = 0;
	std::string gk;
	for (int k = 0; k < ::bc5::o438::kFnN; k++) {
		if (guest[k].blocked_ns == 0) continue;
		gb += guest[k].blocked_ns;
		std::snprintf(b, sizeof(b), "%s%s=%.1f", gk.empty() ? "" : ";", ::bc5::o438::kFnName[k], us(guest[k].blocked_ns));
		gk += b;
	}
	std::snprintf(b, sizeof(b), ",%" PRIu64 ",%.1f,%.1f,%.1f,%.1f,%.1f,%s,%.1f,%s\n", S.f.flip.n, us(S.f.flip.wall), us(S.f.flip.wall - S.f.flip.cpu), us(S.f.drain.wall), us(S.f.drain.wall - S.f.drain.cpu), us(lw),
	              locks.empty() ? "-" : locks.c_str(), us(gb), gk.empty() ? "-" : gk.c_str());
	line += b;
	S.buf += line;
	S.last = t;
	S.cpu0 = cpu, S.runq0 = runq, S.slices0 = slices, S.minflt0 = minflt, S.majflt0 = majflt;
	S.f = Frame {};
	if (++S.frames % 64 == 0) flush(S);
}
inline const bool g_registered = [] {
	::bc5::o438::g_flip_hook = &frame_hook;
	return true;
}();
} // namespace bc5::h438
#define BC5_H438_CAT2(a, b) a##b
#define BC5_H438_CAT(a, b)  BC5_H438_CAT2(a, b)
#define BC5_H438_GC(request) const ::bc5::h438::GcSpan bc5_h438_gc_(static_cast<uint64_t>(request))
#define BC5_H438_FLIPSPAN()  const ::bc5::h438::Span bc5_h438_flip_(1)
#define BC5_H438_DRAIN_BEGIN() \
	{                          \
		const ::bc5::h438::Span bc5_h438_drain_(2);
#define BC5_H438_DRAIN_END() }
// id: a small constant per mutex name, given by mkh438.py; name: a string literal
#define BC5_H438_LOCK_ID(id, name, stmt)                                     \
	const uint64_t BC5_H438_CAT(bc5_h438_lt_, __LINE__) = ::bc5::h438::lock_t0(); \
	stmt;                                                                   \
	::bc5::h438::lock_done(id, name, BC5_H438_CAT(bc5_h438_lt_, __LINE__))
#endif
