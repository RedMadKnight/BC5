// BC5 experiment 0412 (tag sg412): the save guard of the fault record. GPL-2.0.
// The fault record (tag fr412, BC5_FAULT_RECORD) ends the game at a GPU fault. The title's saves are written through
// the host's own calls (the save-data library and the file calls on a save mount, "/savedata<n>/..."), so the host
// knows when a save is being written. Before the exit:
//   1. DRAIN (bounded): a save already being written goes on to its end (the host calls on a mount that has been
//      written since it was mounted go on); nothing new starts (a first write on a clean mount, a new mount, a call of
//      the save-data library that writes: the caller is held and never returns);
//   2. FINAL: every guarded call is held; the caller then flushes and syncs and exits.
// "A save being written" is: a guarded call in flight, or a save mount that has been written and is not unmounted yet
// (the title mounts, writes its files and unmounts). The outcome of the wait is returned for the record.
// Without a close() nothing here changes any call: two atomic adds per guarded call.
// Portable C++20 (no POSIX): the CPU test saveguard0412.cpp builds on the laptop and on the box.
#pragma once
#include <atomic>
#include <chrono>
#include <cstddef>
#include <cstdint>
#include <thread>

namespace sg412 {

inline constexpr int kSlots = 16; // save mounts "/savedata0" .. "/savedata15"
inline constexpr int kLib   = 16; // the save-data library's own writers (no mount)
inline constexpr int kNone  = -1; // not save storage: not guarded

enum : int { kOpen = 0, kDraining = 1, kFinal = 2 };
enum : int { kUnmounted = 0, kClean = 1, kDirty = 2 };

inline std::atomic<int>     g_phase{kOpen};
inline std::atomic<int>     g_ops{0};
inline std::atomic<int>     g_slot[kSlots]{};
inline std::atomic<int64_t> g_last_ms{-1};  // the last guarded call's start, ms on the steady clock
inline std::atomic<int>     g_held{0};      // callers held since the close began
inline void (*g_hold_hook)() = nullptr;     // the CPU test's stand-in for "held for ever" (it throws)

inline int64_t now_ms() {
	return std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now().time_since_epoch()).count();
}

// "/savedata<n>" or "/savedata<n>/..." -> n, anything else -> kNone.
inline int slot_of(const char* path) {
	if (path == nullptr) return kNone;
	static const char pre[] = "/savedata";
	int               i     = 0;
	for (; pre[i] != 0; i++) {
		if (path[i] != pre[i]) return kNone;
	}
	if (path[i] < '0' || path[i] > '9') return kNone;
	int n = 0;
	for (; path[i] >= '0' && path[i] <= '9'; i++) {
		n = n * 10 + (path[i] - '0');
		if (n >= kSlots) return kNone;
	}
	return (path[i] == 0 || path[i] == '/') ? n : kNone;
}

inline int dirty_mounts() {
	int n = 0;
	for (const auto& s: g_slot) n += s.load() == kDirty ? 1 : 0;
	return n;
}

[[noreturn]] inline void hold() {
	g_held.fetch_add(1);
	if (g_hold_hook != nullptr) g_hold_hook();
	for (;;) std::this_thread::sleep_for(std::chrono::hours(1));
}

// May this call start now? (the phase is read after the call was counted, so close() never misses it)
inline bool allowed(int slot, bool writes) {
	const int phase = g_phase.load();
	if (phase == kOpen) return true;
	if (phase == kFinal) return false;
	// draining: a save already being written goes on; a call that writes nothing (close, sync) goes on
	if (!writes) return true;
	return slot >= 0 && slot < kSlots && g_slot[slot].load() == kDirty;
}

// One guarded host call. slot: slot_of(path), kLib, or kNone (then nothing is done). writes: the call changes the save.
struct Op {
	bool counted = false;
	Op(int slot, bool writes) {
		if (slot == kNone) return;
		g_ops.fetch_add(1);
		if (!allowed(slot, writes)) {
			g_ops.fetch_sub(1);
			hold();
		}
		counted = true;
		g_last_ms.store(now_ms());
		if (writes && slot >= 0 && slot < kSlots) {
			int clean = kClean;
			g_slot[slot].compare_exchange_strong(clean, kDirty);
		}
	}
	~Op() {
		if (counted) g_ops.fetch_sub(1);
	}
	Op(const Op&)            = delete;
	Op& operator=(const Op&) = delete;
};

// The host directory of the first save mount of the run (every save of the title lies on its file system): what
// the exit syncs. Written once.
inline char              g_root[1024] = "";
inline std::atomic<bool> g_root_claimed{false};
inline std::atomic<bool> g_root_set{false};
inline void              note_root(const char* dir) {
	if (dir == nullptr || dir[0] == 0 || g_root_claimed.exchange(true)) return;
	size_t i = 0;
	for (; dir[i] != 0 && i + 1 < sizeof(g_root); i++) g_root[i] = dir[i];
	g_root[i] = 0;
	g_root_set.store(dir[i] == 0); // a name too long to keep is not used
}

inline void mounted(int slot) {
	if (slot >= 0 && slot < kSlots) g_slot[slot].store(kClean);
}
inline void unmounted(int slot) {
	if (slot >= 0 && slot < kSlots) g_slot[slot].store(kUnmounted);
}

struct Closed {
	int     ops_at_request   = 0;  // guarded calls in flight when the exit was asked for
	int     dirty_at_request = 0;  // save mounts written and not yet unmounted then
	int64_t last_op_age_ms   = -1; // how long before the request the last guarded call began (-1: there was none)
	int64_t waited_ms        = 0;
	int     ops_left         = 0;
	int     dirty_left       = 0;
	int     held             = 0;  // callers refused and held
	bool    in_flight        = false; // a save was being written at the request
	bool    complete         = false; // nothing was left in flight when the wait ended
};

// Called once, by the thread that is about to end the process. After it every guarded call is held.
inline Closed close(int64_t timeout_ms) {
	Closed        c;
	const int64_t t0 = now_ms();
	g_phase.store(kDraining);
	c.ops_at_request   = g_ops.load();
	c.dirty_at_request = dirty_mounts();
	const int64_t last = g_last_ms.load();
	c.last_op_age_ms   = last < 0 ? -1 : t0 - last;
	c.in_flight        = c.ops_at_request != 0 || c.dirty_at_request != 0;
	while ((g_ops.load() != 0 || dirty_mounts() != 0) && now_ms() - t0 < timeout_ms) std::this_thread::sleep_for(std::chrono::milliseconds(2));
	g_phase.store(kFinal);
	// calls that were counted before the phase changed end here (bounded: a quarter of the time on top)
	const int64_t t1 = now_ms();
	while (g_ops.load() != 0 && now_ms() - t1 < timeout_ms / 4) std::this_thread::sleep_for(std::chrono::milliseconds(2));
	c.waited_ms  = now_ms() - t0;
	c.ops_left   = g_ops.load();
	c.dirty_left = dirty_mounts();
	c.held       = g_held.load();
	c.complete   = c.ops_left == 0 && c.dirty_left == 0;
	return c;
}

// The record's words for the outcome.
inline const char* verdict(const Closed& c) {
	if (!c.in_flight) return "no save was being written when the game was ended";
	if (c.complete) return "a save was being written; it was let finish before the game was ended";
	return "A SAVE WAS BEING WRITTEN AND DID NOT FINISH IN THE TIME ALLOWED: THAT SAVE MAY BE INCOMPLETE";
}

} // namespace sg412
