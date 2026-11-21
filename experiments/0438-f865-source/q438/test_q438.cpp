// SPDX-License-Identifier: GPL-2.0
// BC5 experiment 0438 (tag q438): an offline test of the per-slot submit queue. test_q438.sh cuts, unchanged, from a
// generated unit: r438's state (with q438's switch), the chain block (ChainSlot .. chain_given_up_at: hold_release,
// chain_post_soft_locked, chain_submit, the chain watchdog, chain_register, ~ChainSlot, chain_flush_all, chain_append,
// chain_begin/end, ChainInSubmit), PendingLabelWrite/g_plw, register_label_writes, ring_will_satisfy and (Q438_NEW) the
// q438 block. This file supplies the stubs: submit_now records every call (owner, segments, thread, the slot's flight set
// and queue size at the call) and registers the chain's label writes for real after a simulated preparation; post runs a
// replay at once. The real chain watchdog (bc5-chainwd, 2-ms hold bound) runs in every mode.
// Modes (argv[1]):
//   identity  one game thread, a fixed sequence (flushes, flush_all, a foreign submit, in_submit, soft replays, a drain);
//             prints a trace that test_q438.sh compares between the bake unit and the q438 unit with the switch off;
//   random    4 owner threads + the watchdog + a flush_all thread; checks per slot: take order = submit order, one
//             submit_now at a time, the chain's writes in the flight set during its submit_now, f16_done = submissions,
//             a game-thread wait on the last flushed label finds its writer (switch on: always), drains complete
//             (switch on: always), no early entry left, no BUG line; switch on: all of a slot's submissions on one
//             thread that is not its owner, the queue never over 4;
//   det       (switch on only) gated cases: FIFO, the flight union and f16_done per entry, early registration and the
//             game-thread wait, the invariant (a write never registered: BUG line, removed), the full queue, the nested
//             flush inline, flush_all(5)/(8) drains, sync mode, the slot's destruction with a queue.
#include <algorithm>
#include <atomic>
#include <chrono>
#include <cinttypes>
#include <condition_variable>
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <deque>
#include <functional>
#include <map>
#include <memory>
#include <mutex>
#include <random>
#include <set>
#include <string>
#include <thread>
#include <utility>
#include <vector>
#ifdef _WIN32
static int pthread_self() { return 0; }
static int pthread_setname_np(int, const char*) { return 0; }
#else
#include <pthread.h>
#endif

namespace bc5::direct {
inline constexpr int kGfxRing      = -1;
inline constexpr int kComputeRings = 4;
} // namespace bc5::direct
#define BC5_DIAG_ENV(x) std::getenv(x)
namespace SoftCp {
inline uint64_t now_ns() { return static_cast<uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now().time_since_epoch()).count()); }
inline bool compare(uint32_t f, uint32_t v, uint32_t mask, uint32_t ref) {
	const uint32_t vm = v & mask, rm = ref & mask;
	return f == 3 ? vm == rm : f == 4 ? vm != rm : false;
}
struct GpuDone {
	const uint32_t*      buf;
	std::vector<uint8_t> done;
};
static thread_local std::vector<GpuDone> t_gpu_done;
static void set_gpu_executed(const uint32_t* buf, uint32_t n, const std::vector<uint32_t>&) { t_gpu_done.push_back({buf, std::vector<uint8_t>(n, 1)}); }
static void clear_gpu_executed() { t_gpu_done.clear(); }
static std::atomic<uint64_t> g_soft_runs {0};
static void submit(const uint32_t*, uint32_t, const char*) { g_soft_runs++; }
} // namespace SoftCp
static std::mutex               g_jm;
static std::vector<std::string> g_lines;
static void journal(const char* fmt, ...) {
	char    b[1024];
	va_list ap;
	va_start(ap, fmt);
	std::vsnprintf(b, sizeof(b), fmt, ap);
	va_end(ap);
	std::lock_guard l(g_jm);
	g_lines.emplace_back(b);
}
static double timing_now() { return static_cast<double>(SoftCp::now_ns()) / 1e9; }
static std::atomic<uint64_t> g_posts {0};
static void post(std::function<void(bool failed)> fn) { // the completion queue, inline
	g_posts++;
	fn(false);
}
enum class Stage { Off, All };
static Stage                                 g_stage = Stage::All;
static bool                                  g_async = true; // the unit's is a const; the det mode's sync case clears it
static thread_local int                      t_queue_idx = -1;
static thread_local std::vector<const uint32_t*> t_keep_waits;
static thread_local bool                     t_game = false;
static bool                                  on_game_thread() { return t_game; }
static int                                   w428_rings() { return 4; }
static int                                   job_ring(const char*) { return bc5::direct::kGfxRing; }
static bool                                  wait_satisfied(const uint32_t*, bool) { return false; } // the labels' memory never satisfies
static bool                                  ring_will_satisfy(const uint32_t* p, bool is64, int ring);
#include "q_state.inc"
#include "q_chain.inc"
#include "q_plw.inc"
#include "q_reg.inc"
#include "q_rws.inc"
#ifdef Q438_NEW
#include "q_q.inc"
#endif

// ---- the stub submission ---------------------------------------------------------------------------------------------------
static constexpr int        kOwners = 16;
static uint64_t             g_labels[kOwners];
static ChainSlot*           g_slot_of[kOwners];
static std::thread::id      g_owner_tid[kOwners];
static std::atomic<int>     g_active[kOwners], g_pass[kOwners];
static std::atomic<bool>    g_gated[kOwners], g_nest_ok[kOwners];
static std::atomic<int>     g_prep_us {0}, g_prep_rand_us {0}, g_drop_write {0};
static std::atomic<uint64_t> g_seq_no {0}, g_viol_active {0}, g_viol_flight {0}, g_viol_cap {0}, g_qmax {0};
static std::function<void(int owner, uint32_t first)> g_hook; // set while no submission runs
struct Rec {
	int                   owner = -1;
	std::vector<uint32_t> seqs;
	std::thread::id       tid;
	uint64_t              flight_n = 0; // how often the owner's label was in the flight set at the call
};
static std::mutex       g_rec_mu;
static std::vector<Rec> g_recs;
static uint64_t label_of(int o) { return reinterpret_cast<uintptr_t>(&g_labels[o]); }
static std::vector<uint32_t> seg_of(int o, uint32_t k) { // NOP(owner, seq) + RELEASE_MEM 64-bit of k to the owner's label
	const uint64_t a = label_of(o);
	return {0xC0011000u, static_cast<uint32_t>(o), k, 0xC0064900u, 0x00000528u, 0x40010000u, static_cast<uint32_t>(a), static_cast<uint32_t>(a >> 32u), k, 0, 0};
}
static void wait64(uint32_t* p, uint64_t a, uint64_t v) {
	p[0] = 0xC0079300u; p[1] = 0x00000113u; // ==, memory
	p[2] = static_cast<uint32_t>(a); p[3] = static_cast<uint32_t>(a >> 32u); p[4] = static_cast<uint32_t>(v); p[5] = static_cast<uint32_t>(v >> 32u); p[6] = 0xffffffffu; p[7] = 0xffffffffu; p[8] = 0x19;
}
static void submit_now(const uint32_t* ib, uint32_t num_dwords, const char*, int ring, const Chain* chain) {
	Rec                   r;
	std::vector<uint32_t> executed;
	for (uint32_t q = 0; q < num_dwords;) {
		const uint32_t h = ib[q], c = (h >> 16u) & 0x3fffu, len = c == 0x3fffu ? 1 : c + 2;
		if (((h >> 8u) & 0xffu) == 0x10u) {
			r.owner = static_cast<int>(ib[q + 1]);
			r.seqs.push_back(ib[q + 2]);
		}
		executed.push_back(q);
		q += len;
	}
	if (chain == nullptr || r.owner < 0) std::abort();
	const int o = r.owner;
	r.tid       = std::this_thread::get_id();
	if (g_active[o].fetch_add(1) != 0 && !g_nest_ok[o].load()) g_viol_active++;
	{
		ChainSlot&      s = *g_slot_of[o];
		std::lock_guard lk(s.mu);
		r.flight_n = static_cast<uint64_t>(std::count(s.f10_flight.begin(), s.f10_flight.end(), label_of(o)));
		if (r.flight_n == 0) g_viol_flight++;
#ifdef Q438_NEW
		std::lock_guard ql(s.q_mu);
		if (s.q.size() > kQ438Cap) g_viol_cap++;
		for (uint64_t m = g_qmax.load(); s.q.size() > m && !g_qmax.compare_exchange_weak(m, s.q.size());) {
		}
#endif
	}
	if (g_gated[o].load()) {
		for (;;) {
			int p = g_pass[o].load();
			if (p > 0 && g_pass[o].compare_exchange_weak(p, p - 1)) break;
			std::this_thread::sleep_for(std::chrono::microseconds(100));
		}
	}
	if (g_hook) g_hook(o, r.seqs.front());
	const int pr = g_prep_us.load() + (g_prep_rand_us.load() > 0 ? static_cast<int>(SoftCp::now_ns() % static_cast<uint64_t>(g_prep_rand_us.load())) : 0);
	if (pr > 0) std::this_thread::sleep_for(std::chrono::microseconds(pr)); // the preparation and the CS
	for (int d = g_drop_write.load(); d > 0;) { // the filter dropped a write: its early entry is never registered for real
		if (!g_drop_write.compare_exchange_weak(d, d - 1)) continue;
		std::erase(executed, 3u);
		break;
	}
	register_label_writes(ib, num_dwords, executed, g_seq_no.fetch_add(1) + 1, ring);
	SoftCp::t_gpu_done.push_back({ib, std::vector<uint8_t>(1, 1)}); // a mark, as chain_mark_executed leaves one
	{
		std::lock_guard lk(g_rec_mu);
		g_recs.push_back(std::move(r));
	}
	g_active[o]--;
}

// ---- helpers -------------------------------------------------------------------------------------------------------------
static int fails = 0;
#define CHECK(c, ...)                                     \
	do {                                                  \
		if (!(c)) {                                       \
			std::printf("FAIL line %d: ", __LINE__);      \
			std::printf(__VA_ARGS__);                     \
			std::printf("  [%s]\n", #c);                  \
			fails++;                                      \
		}                                                 \
	} while (0)
static std::vector<std::vector<uint32_t>> calls_of(int o) {
	std::lock_guard                    lk(g_rec_mu);
	std::vector<std::vector<uint32_t>> v;
	for (const auto& r: g_recs)
		if (r.owner == o) v.push_back(r.seqs);
	return v;
}
static std::vector<uint32_t> seqs_of(int o) {
	std::vector<uint32_t> v;
	for (const auto& c: calls_of(o)) v.insert(v.end(), c.begin(), c.end());
	return v;
}
static std::set<std::thread::id> tids_of(int o) {
	std::lock_guard           lk(g_rec_mu);
	std::set<std::thread::id> t;
	for (const auto& r: g_recs)
		if (r.owner == o) t.insert(r.tid);
	return t;
}
static size_t early_entries(uint64_t label = 0) {
	std::lock_guard lk(g_plw_mutex);
	return static_cast<size_t>(std::count_if(g_plw.begin(), g_plw.end(), [label](const PendingLabelWrite& w) { return (w.seq & kR438Early) != 0 && (label == 0 || w.label == label); }));
}
static size_t lines_with(const char* needle) {
	std::lock_guard l(g_jm);
	return static_cast<size_t>(std::count_if(g_lines.begin(), g_lines.end(), [needle](const std::string& x) { return x.find(needle) != std::string::npos; }));
}
static std::vector<std::vector<uint32_t>> g_segs[kOwners]; // the owners' buffers (stable)
static std::mutex                         g_segs_mu;
static void append(int o, uint32_t k) {
	const uint32_t* p = nullptr;
	{
		std::lock_guard lk(g_segs_mu);
		g_segs[o].push_back(seg_of(o, k));
		p = g_segs[o].back().data();
	}
	chain_append(nullptr, 0, p, 11, "dcb", false);
}
static bool wait_ok(int o, uint32_t k) { // a game-thread wait on the owner's label == k: is its writer pending?
	uint32_t w[9];
	wait64(w, label_of(o), k);
	return ring_will_satisfy(w, true, bc5::direct::kGfxRing);
}
static void begin_owner(int o) {
	t_game = true;
	chain_begin(); // mode 2 on a game thread: the slot is registered, its chain held across "ioctls"
	g_slot_of[o]   = &g_chain_tl;
	g_owner_tid[o] = std::this_thread::get_id();
}
// On Windows a thread_local's destructor runs under the loader lock, where joining a thread that exits deadlocks (the
// submitter's exit needs that lock). The test stops the submitter at the owner's scope end there; glibc runs
// thread_local destructors before the thread's exit without such a lock (the box: the destructor itself does it).
struct OwnerEnd {
	~OwnerEnd() {
#if defined(_WIN32) && defined(Q438_NEW)
		if (q438_on()) q438_stop(g_chain_tl);
#endif
	}
};
#define BEGIN_OWNER(o) 	begin_owner(o);    	OwnerEnd owner_end_
struct SlotState {
	size_t   flight = 0;
	uint64_t f16    = 0;
	bool     q_idle = true;
};
static SlotState slot_state(ChainSlot& s) {
	SlotState st;
	{
		std::lock_guard lk(s.mu);
		st.flight = s.f10_flight.size();
	}
	st.f16 = s.f16_done.load();
#ifdef Q438_NEW
	std::lock_guard ql(s.q_mu);
	st.q_idle = s.q.empty() && s.q_taken == s.q_done && !s.q_running;
#endif
	return st;
}

// ---- identity -------------------------------------------------------------------------------------------------------------
static void run_identity() {
	std::vector<std::string> out;
	auto                     state = [&out](const char* step) {
        char            b[512];
        ChainSlot&      s = *g_slot_of[0];
        std::lock_guard lk(s.mu);
        std::snprintf(b, sizeof(b), "%s: flight %zu f16 %" PRIu64 " segs %zu marks %zu soft %zu posts %" PRIu64 " softruns %" PRIu64, step, s.f10_flight.size(), s.f16_done.load(), s.c.segs.size(), s.marks.size(),
		                                  s.soft.size(), g_posts.load(), SoftCp::g_soft_runs.load());
        out.emplace_back(b);
	};
	std::thread t([&] {
		BEGIN_OWNER(0);
		append(0, 1);
		chain_flush(1);
		state("1 flush(1)");
		append(0, 2);
		append(0, 3);
		std::thread([] { chain_flush_all(8); }).join(); // an observe point on another thread: foreign
		state("2 flush_all(8)");
		{
			ChainInSubmit in(true); // the owner inside Direct::submit: a foreign submit leaves the chain
			append(0, 4);
			std::thread([] { chain_submit(*g_slot_of[0], 9, true); }).join();
			state("3 foreign in_submit");
		}
		chain_flush(10);
		state("4 flush(10)");
		static const uint32_t sb[2] = {0xC0001000u, 0};
		chain_soft_push(sb, 2, "dcb"); // nothing held back: posted at once
		state("5 soft, chain empty");
		append(0, 5);
		chain_soft_push(sb, 2, "dcb"); // held back until the chain is submitted
		state("6 soft, chain open");
		chain_flush(1);
		state("7 flush(1)");
		append(0, 6);
		chain_flush(5);
		state("8 flush(5)");
		for (uint32_t k = 1; k <= 7; k++) {
			char b[64];
			std::snprintf(b, sizeof(b), "wait ==%u: %d", k, wait_ok(0, k) ? 1 : 0);
			out.emplace_back(b);
		}
	});
	t.join();
	for (const auto& c: calls_of(0)) {
		std::string l = "call:";
		for (uint32_t k: c) l += " " + std::to_string(k);
		out.push_back(l);
	}
	{
		std::lock_guard lk(g_plw_mutex);
		for (const auto& w: g_plw) {
			char b[128];
			std::snprintf(b, sizeof(b), "plw: label %s value %" PRIu64 " early %d is64 %d order %" PRIu64, w.label == label_of(0) ? "L0" : "?", w.value, (w.seq & kR438Early) != 0 ? 1 : 0, w.is64 ? 1 : 0, w.order);
			out.emplace_back(b);
		}
	}
	for (const auto& l: out) std::printf("%s\n", l.c_str());
	std::printf("journal lines with BUG: %zu\n", lines_with("BUG"));
}

// ---- random ---------------------------------------------------------------------------------------------------------------
struct OwnerStats {
	uint64_t checks = 0, miss = 0, drains = 0, drain_short = 0, appended = 0;
};
static void owner_random(int o, uint32_t n, uint64_t seed, OwnerStats& st, bool q_on) {
	BEGIN_OWNER(o);
	std::mt19937_64 rng(seed);
	auto            check = [&](uint32_t k) {
        st.checks++;
        if (!wait_ok(o, k)) st.miss++;
	};
	auto drain_check = [&](uint32_t k) {
		st.drains++;
		const SlotState ss = slot_state(*g_slot_of[o]);
		if (seqs_of(o).size() != k || ss.flight != 0 || !ss.q_idle) st.drain_short++;
	};
	for (uint32_t k = 1; k <= n; k++) {
		if (rng() % 4 == 0) {
			ChainInSubmit in(true);
			append(o, k);
			if (rng() % 2 == 0) {
				chain_flush(1);
				check(k);
			}
		} else {
			append(o, k);
		}
		st.appended++;
		const int r = static_cast<int>(rng() % 10);
		if (r < 4) {
			chain_flush(1);
			check(k);
		} else if (r < 6) {
			chain_end();
		} else if (r < 8) {
			std::this_thread::sleep_for(std::chrono::microseconds(2500)); // the watchdog's 2-ms bound
			chain_flush(1);
			check(k);
		}
		if (k % 40 == 0) {
			chain_flush(5);
			drain_check(k);
		}
	}
	chain_flush(5);
	drain_check(n);
	std::this_thread::sleep_for(std::chrono::milliseconds(30)); // today's drain does not wait for a foreign submission in flight
	const SlotState ss = slot_state(*g_slot_of[o]);
	const auto      v  = seqs_of(o);
	std::vector<uint32_t> want(n);
	for (uint32_t k = 0; k < n; k++) want[k] = k + 1;
	CHECK(v == want, "owner %d: the segments reached submit_now out of take order or not all (%zu of %u)", o, v.size(), n);
	CHECK(ss.f16 == calls_of(o).size(), "owner %d: f16_done %" PRIu64 " != submissions %zu", o, ss.f16, calls_of(o).size());
	CHECK(ss.flight == 0 && ss.q_idle, "owner %d: flight %zu after the drain", o, ss.flight);
	if (q_on) {
		const auto t = tids_of(o);
		CHECK(t.size() == 1 && t.count(g_owner_tid[o]) == 0, "owner %d: %zu submitting threads (switch on: one submitter, never the owner)", o, t.size());
	}
}
static int run_random(bool q_on) {
	g_prep_rand_us = 400;
	OwnerStats         st[4];
	std::atomic<bool>  stop {false};
	std::thread        fa([&] {
        std::mt19937_64 rng(7);
        while (!stop.load()) {
            std::this_thread::sleep_for(std::chrono::microseconds(700));
            chain_flush_all(rng() % 3 == 0 ? 5 : 8); // the flip's drain / the observe points
        }
	});
	std::vector<std::thread> ow;
	for (int o = 0; o < 4; o++) ow.emplace_back(owner_random, o, 160u, 438u + static_cast<uint64_t>(o), std::ref(st[o]), q_on);
	for (auto& t: ow) t.join();
	stop = true;
	fa.join();
	uint64_t checks = 0, miss = 0, drains = 0, dshort = 0;
	for (const auto& s: st) {
		checks += s.checks;
		miss += s.miss;
		drains += s.drains;
		dshort += s.drain_short;
	}
	uint64_t calls = 0, foreign_calls = 0;
	{
		std::lock_guard lk(g_rec_mu);
		calls = g_recs.size();
		for (const auto& r: g_recs)
			if (r.tid != g_owner_tid[r.owner]) foreign_calls++;
	}
	std::printf("random: 4 owners x 160 segments, %" PRIu64 " submit_now calls (%" PRIu64 " not on the owner's thread), watchdog submissions %" PRIu64 "\n", calls, foreign_calls, g_chain_why[9].load());
	std::printf("random: game-thread waits on the last flushed label %" PRIu64 ", writer not found %" PRIu64 "; drains %" PRIu64 ", short (submissions still missing) %" PRIu64 "\n", checks, miss, drains, dshort);
	std::printf("random: violations: two submit_now of one slot at once %" PRIu64 ", writes not in the flight set %" PRIu64 ", queue over 4 %" PRIu64 "; queue max %" PRIu64 "; early entries left %zu; BUG lines %zu\n",
	            g_viol_active.load(), g_viol_flight.load(), g_viol_cap.load(), g_qmax.load(), early_entries(), lines_with("BUG"));
	CHECK(g_viol_active.load() == 0 && g_viol_flight.load() == 0 && g_viol_cap.load() == 0, "violations");
	CHECK(early_entries() == 0 && lines_with("BUG") == 0, "early entries left or BUG lines");
	if (q_on) {
		CHECK(miss == 0, "switch on: %" PRIu64 " game-thread waits found no writer for a queued chain", miss);
		CHECK(dshort == 0, "switch on: %" PRIu64 " drains returned with submissions missing", dshort);
#ifdef Q438_NEW
		CHECK(g_q438_threads.load() == 0, "submitters still running after the owners' exit: %" PRIu64, g_q438_threads.load());
		std::printf("random: q438 pushed %" PRIu64 ", full waits %" PRIu64 ", nested %" PRIu64 "\n", g_q438_pushed.load(), g_q438_full.load(), g_q438_nested.load());
#endif
	}
	{
		std::lock_guard lk(g_chains_mu);
		CHECK(g_chains.empty(), "%zu slots still registered after the owners' exit", g_chains.size());
	}
	return 0;
}

#ifdef Q438_NEW
// ---- det ------------------------------------------------------------------------------------------------------------------
static void wait_until(const std::function<bool()>& f, const char* what) {
	const uint64_t t0 = SoftCp::now_ns();
	while (!f()) {
		if (SoftCp::now_ns() - t0 > 5'000'000'000ull) {
			std::printf("FAIL: timed out waiting for %s\n", what);
			fails++;
			return;
		}
		std::this_thread::sleep_for(std::chrono::microseconds(200));
	}
}
static size_t label_in_flight(ChainSlot& s, uint64_t l) {
	std::lock_guard lk(s.mu);
	return static_cast<size_t>(std::count(s.f10_flight.begin(), s.f10_flight.end(), l));
}
static void det_fifo_flight(int o) { // gated: 3 entries; FIFO; the union and f16_done per entry; early entries per entry
	g_gated[o] = true;
	g_pass[o]  = 0;
	std::thread t([o] {
		BEGIN_OWNER(o);
		ChainSlot& s = g_chain_tl;
		for (uint32_t k = 1; k <= 3; k++) {
			append(o, k);
			chain_flush(1);
			if (k == 1) wait_until([o] { return g_active[o].load() == 1; }, "entry 1 in submit_now");
		}
		CHECK(label_in_flight(s, label_of(o)) == 3, "fifo: the flight union holds %zu of 3 sets", label_in_flight(s, label_of(o)));
		CHECK(early_entries(label_of(o)) == 3, "fifo: %zu early entries of 3", early_entries(label_of(o)));
		{
			std::lock_guard ql(s.q_mu);
			CHECK(s.q.size() == 2 && s.q_running, "fifo: queue %zu (2 behind the one in flight)", s.q.size());
		}
		for (uint64_t k = 1; k <= 3; k++) {
			CHECK(s.f16_done.load() == k - 1, "fifo: f16_done %" PRIu64 " before entry %" PRIu64, s.f16_done.load(), k);
			g_pass[o]++;
			wait_until([&s, k] { return s.f16_done.load() == k; }, "f16_done per entry");
			CHECK(label_in_flight(s, label_of(o)) == 3 - k, "fifo: after entry %" PRIu64 " the union holds %zu sets", k, label_in_flight(s, label_of(o)));
			CHECK(early_entries(label_of(o)) == 3 - k, "fifo: after entry %" PRIu64 " %zu early entries", k, early_entries(label_of(o)));
		}
		chain_flush(5);
		const auto c = calls_of(o);
		CHECK(c.size() == 3 && c[0] == std::vector<uint32_t> {1} && c[1] == std::vector<uint32_t> {2} && c[2] == std::vector<uint32_t> {3}, "fifo: the entries reached submit_now out of take order (%zu calls, first %u)", c.size(),
		      c.empty() ? 0u : c[0][0]);
	});
	t.join();
	g_gated[o] = false;
	std::printf("det fifo/flight/f16: done\n");
}
static void det_order(int o) { // an earlier entry's real write (and another thread's) must not pass a queued entry's early write
	g_gated[o] = true;
	g_pass[o]  = 0;
	std::thread t([o] {
		BEGIN_OWNER(o);
		append(o, 1);
		chain_flush(1);
		wait_until([o] { return g_active[o].load() == 1; }, "entry 1 in submit_now");
		append(o, 2);
		chain_flush(1); // entry 2 queued: its early write of 2 is registered after entry 1's early write of 1
		g_pass[o]++;    // entry 1 registers its real write of 1 now, after entry 2's early one
		wait_until([o] { return calls_of(o).size() == 1; }, "entry 1's real registration");
		std::atomic<int> got {-1};
		std::thread      game([&got, o] {
            t_game = true;
            got    = wait_ok(o, 2) ? 1 : 0;
		});
		std::this_thread::sleep_for(std::chrono::milliseconds(30));
		const int after1 = got.load();
		static const std::vector<uint32_t> other = seg_of(o, 9); // a real write of 9 by another thread (bc5-ring, another slot)
		std::thread([] { register_label_writes(other.data(), 11, {3}, 900000, bc5::direct::kGfxRing); }).join();
		std::this_thread::sleep_for(std::chrono::milliseconds(20));
		const int after_other = got.load();
		g_pass[o]++; // entry 2's real write
		game.join();
		CHECK(after1 == -1, "order: the wait on 2 returned %d after entry 1's real write passed entry 2's early one", after1);
		CHECK(after_other == -1, "order: the wait on 2 returned %d after another thread's real write", after_other);
		CHECK(got.load() == 1, "order: the wait on 2 found no writer after entry 2's real registration");
		std::printf("det order: after entry 1's real write %d, after another thread's %d (-1 = still waiting for entry 2), at the end %d\n", after1, after_other, got.load());
		chain_flush(5);
	});
	t.join();
	g_gated[o] = false;
}
static void det_early(int o) { // a game-thread wait on a queued chain's label waits for its real registration
	g_gated[o] = true;
	g_pass[o]  = 0;
	std::thread t([o] {
		BEGIN_OWNER(o);
		append(o, 7);
		chain_flush(1); // pushed; the submitter waits at the gate
		wait_until([o] { return g_active[o].load() == 1; }, "the entry in submit_now");
		bool                  other = true;
		std::thread           ng([&] { other = wait_ok(o, 7); }); // not a game thread: early entries are not its writers
		ng.join();
		CHECK(!other, "early: a non-game thread took the early entry for a writer");
		std::thread opener([o] {
			std::this_thread::sleep_for(std::chrono::milliseconds(40));
			g_pass[o]++;
		});
		const uint64_t t0 = SoftCp::now_ns();
		const bool     ok = wait_ok(o, 7);
		const uint64_t dt = SoftCp::now_ns() - t0;
		opener.join();
		CHECK(ok, "early: the game-thread wait found no writer for the queued chain's label (\"no pending write\")");
		CHECK(dt >= 30'000'000ull, "early: the wait returned after %.3f ms, before the real registration", static_cast<double>(dt) / 1e6);
		std::printf("det early: the game-thread wait took %.3f ms (the gate opened at 40 ms), found the writer %d\n", static_cast<double>(dt) / 1e6, ok ? 1 : 0);
		chain_flush(5);
	});
	t.join();
	g_gated[o] = false;
}
static void det_invariant(int o) { // an early write never registered for real: a BUG line, removed
	const size_t   bug0  = lines_with("of a queued chain never reached the ring");
	const uint64_t lost0 = g_q438_lost.load();
	std::thread    t([o] {
        BEGIN_OWNER(o);
        g_drop_write = 1;
        append(o, 1);
        chain_flush(5);
	});
	t.join();
	CHECK(g_q438_lost.load() == lost0 + 1 && lines_with("of a queued chain never reached the ring") == bug0 + 1, "invariant: lost %" PRIu64 ", BUG lines %zu", g_q438_lost.load() - lost0,
	      lines_with("of a queued chain never reached the ring") - bug0);
	CHECK(early_entries(label_of(o)) == 0, "invariant: the early entry was not removed");
	std::printf("det invariant: lost %" PRIu64 ", BUG lines %zu, early entries left %zu\n", g_q438_lost.load() - lost0, lines_with("of a queued chain never reached the ring") - bug0, early_entries(label_of(o)));
}
static void det_cap(int o) { // the owner waits only when the queue is full
	g_gated[o] = true;
	g_pass[o]  = 0;
	std::thread t([o] {
		BEGIN_OWNER(o);
		append(o, 1);
		chain_flush(1);
		wait_until([o] { return g_active[o].load() == 1; }, "entry 1 in submit_now");
		uint64_t worst = 0;
		for (uint32_t k = 2; k <= 5; k++) { // 4 queued behind the one in flight: no wait
			append(o, k);
			const uint64_t t0 = SoftCp::now_ns();
			chain_flush(1);
			worst = std::max<uint64_t>(worst, SoftCp::now_ns() - t0);
		}
		CHECK(worst < 20'000'000ull, "cap: a push with space waited %.3f ms", static_cast<double>(worst) / 1e6);
		std::thread opener([o] {
			std::this_thread::sleep_for(std::chrono::milliseconds(40));
			g_pass[o] = 100;
		});
		append(o, 6);
		const uint64_t t0 = SoftCp::now_ns();
		chain_flush(1); // full: waits for space
		const uint64_t dt = SoftCp::now_ns() - t0;
		opener.join();
		CHECK(dt >= 30'000'000ull, "cap: the push into a full queue returned after %.3f ms", static_cast<double>(dt) / 1e6);
		chain_flush(5);
		CHECK(seqs_of(o) == (std::vector<uint32_t> {1, 2, 3, 4, 5, 6}), "cap: order");
		std::printf("det cap: pushes with space at most %.3f ms, the push into the full queue %.3f ms; queue max %" PRIu64 "\n", static_cast<double>(worst) / 1e6, static_cast<double>(dt) / 1e6, g_qmax.load());
	});
	t.join();
	g_gated[o] = false;
	CHECK(g_viol_cap.load() == 0 && g_qmax.load() <= kQ438Cap, "cap: the queue held %" PRIu64, g_qmax.load());
}
static void det_nested(int o) { // a flush of the slot on its own submitter, inside submit_now, goes inline ahead
	std::atomic<int> phase {0};
	std::thread::id  sub;
	g_nest_ok[o] = true;
	g_hook       = [o, &phase, &sub](int ow, uint32_t first) {
        if (ow != o || first != 1) return;
        sub   = std::this_thread::get_id();
        phase = 1; // the owner appends seg 2 now
        while (phase.load() != 2) std::this_thread::yield();
        chain_submit(*g_slot_of[o], 5, true); // submit_now's mapping sync -> wait_jobs -> chain_flush on this thread
        phase = 3;
	};
	std::thread t([o, &phase] {
		BEGIN_OWNER(o);
		append(o, 1);
		chain_flush(1);
		wait_until([&phase] { return phase.load() == 1; }, "the submitter in the hook");
		append(o, 2);
		phase = 2;
		wait_until([&phase] { return phase.load() == 3; }, "the nested flush to return");
		chain_flush(5);
		const SlotState ss = slot_state(g_chain_tl);
		CHECK(ss.f16 == 2 && ss.flight == 0 && ss.q_idle, "nested: f16 %" PRIu64 " flight %zu", ss.f16, ss.flight);
	});
	t.join();
	g_hook       = nullptr;
	g_nest_ok[o] = false;
	const auto c = calls_of(o);
	std::vector<Rec> rs;
	{
		std::lock_guard lk(g_rec_mu);
		for (const auto& r: g_recs)
			if (r.owner == o) rs.push_back(r);
	}
	CHECK(c.size() == 2 && c[0] == std::vector<uint32_t> {2} && c[1] == std::vector<uint32_t> {1}, "nested: the nested chain did not complete inside the outer one (%zu calls)", c.size());
	CHECK(rs.size() == 2 && rs[0].tid == sub && rs[1].tid == sub, "nested: not on the submitter");
	CHECK(rs.size() == 2 && rs[0].flight_n == 2, "nested: the union held %" PRIu64 " sets during the nested call", rs.empty() ? 0 : rs[0].flight_n);
	CHECK(g_q438_nested.load() >= 1, "nested: not counted");
	std::printf("det nested: calls in completion order %u then %u, on the submitter %d, nested %" PRIu64 "\n", c.size() > 0 ? c[0][0] : 0, c.size() > 1 ? c[1][0] : 0, rs.size() == 2 && rs[0].tid == sub ? 1 : 0, g_q438_nested.load());
}
static void det_flush_all(int o1, int o2, int why) { // flush_all(5)/(8) on another thread returns with every slot drained
	g_prep_us = 3000;
	std::atomic<int> ready {0};
	std::atomic<bool> go {false};
	auto body = [&](int o) {
		BEGIN_OWNER(o);
		for (uint32_t k = 1; k <= 3; k++) {
			append(o, k);
			chain_flush(1);
		}
		append(o, 4); // open: flush_all takes it
		ready++;
		while (!go.load()) std::this_thread::yield();
		while (ready.load() != 3) std::this_thread::yield(); // alive until the check is done
	};
	std::thread a(body, o1), b(body, o2);
	wait_until([&] { return ready.load() == 2; }, "two owners with queues");
	const uint64_t t0 = SoftCp::now_ns();
	std::thread([why] { chain_flush_all(why); }).join();
	const uint64_t dt = SoftCp::now_ns() - t0;
	const size_t   n1 = seqs_of(o1).size(), n2 = seqs_of(o2).size();
	const SlotState s1 = slot_state(*g_slot_of[o1]), s2 = slot_state(*g_slot_of[o2]);
	CHECK(n1 == 4 && n2 == 4 && s1.q_idle && s2.q_idle && s1.flight == 0 && s2.flight == 0, "flush_all(%d): %zu and %zu of 4 segments submitted at its return", why, n1, n2);
	std::printf("det flush_all(%d): returned after %.3f ms with %zu + %zu of 4 + 4 segments submitted\n", why, static_cast<double>(dt) / 1e6, n1, n2);
	go    = true;
	ready = 3;
	a.join();
	b.join();
	g_prep_us = 0;
}
static void det_sync(int o) { // sync mode: no queue, the owner submits inline as today
	g_async = false;
	std::thread t([o] {
		BEGIN_OWNER(o);
		append(o, 1);
		chain_flush(1);
		append(o, 2);
		chain_flush(1);
		std::lock_guard ql(g_chain_tl.q_mu);
		CHECK(!g_chain_tl.q_started && g_chain_tl.q_taken == 0, "sync: a queue was used");
	});
	t.join();
	g_async      = true;
	const auto t2 = tids_of(o);
	CHECK(seqs_of(o) == (std::vector<uint32_t> {1, 2}) && t2.size() == 1 && t2.count(g_owner_tid[o]) == 1, "sync: not submitted inline on the owner");
	std::printf("det sync: %zu calls, on the owner %d\n", calls_of(o).size(), t2.count(g_owner_tid[o]) == 1 ? 1 : 0);
}
static void det_destroy(int o) { // the owner's thread ends with a queue: ~ChainSlot drains it and stops the submitter
	g_gated[o] = true;
	g_pass[o]  = 0;
	const uint64_t th0 = g_q438_threads.load();
	ChainSlot*     sp  = nullptr;
	std::thread    t([o, &sp] {
        BEGIN_OWNER(o);
        sp = &g_chain_tl;
        for (uint32_t k = 1; k <= 3; k++) {
            append(o, k);
            chain_flush(1);
        }
	});
	std::thread opener([o] {
		std::this_thread::sleep_for(std::chrono::milliseconds(50));
		g_pass[o] = 100;
	});
	t.join(); // the thread_local slot's destructor ran
	opener.join();
	g_gated[o] = false;
	CHECK(seqs_of(o) == (std::vector<uint32_t> {1, 2, 3}), "destroy: %zu of 3 segments submitted before the slot went", seqs_of(o).size());
	CHECK(g_q438_threads.load() == th0, "destroy: the submitter still runs");
	{
		std::lock_guard lk(g_chains_mu);
		CHECK(std::find(g_chains.begin(), g_chains.end(), sp) == g_chains.end(), "destroy: the slot is still registered");
	}
	std::printf("det destroy: %zu of 3 submitted at the thread's end, submitters %" PRIu64 " -> %" PRIu64 "\n", seqs_of(o).size(), th0, g_q438_threads.load());
}
#endif

int main(int argc, char** argv) {
	const std::string mode = argc > 1 ? argv[1] : "random";
	std::thread([] { // a hang is a failure
		std::this_thread::sleep_for(std::chrono::seconds(90));
		std::printf("FAIL: timeout (a hang)\n");
		std::fflush(stdout);
		std::_Exit(3);
	}).detach();
	bool q_on = false;
#ifdef Q438_NEW
	q_on = q438_on();
#endif
	if (g_chain_mode != 2) {
		std::printf("FAIL: BC5_DIRECT_CHAIN must be 2 (got %d)\n", g_chain_mode);
		return 2;
	}
	std::printf("%s unit, BC5_0438_SUBMITQ %s, mode %s\n",
#ifdef Q438_NEW
	            "q438",
#else
	            "bake",
#endif
	            q_on ? "on" : "off", mode.c_str());
	if (mode == "identity") {
		run_identity();
		return 0;
	}
	if (mode == "random") run_random(q_on);
#ifdef Q438_NEW
	else if (mode == "det") {
		if (!q_on) {
			std::printf("FAIL: det needs BC5_0438_SUBMITQ=1\n");
			return 2;
		}
		det_fifo_flight(8);
		det_early(9);
		det_order(7);
		det_invariant(10);
		det_cap(11);
		det_nested(12);
		det_flush_all(13, 14, 5);
		det_flush_all(4, 5, 8);
		det_sync(15);
		det_destroy(6);
	}
#endif
	{
		std::lock_guard l(g_jm);
		size_t          shown = 0;
		for (const auto& x: g_lines)
			if (x.find("BUG") != std::string::npos && shown++ < 5) std::printf("  journal: %s", x.c_str());
	}
	std::printf("%s (%d failures)\n", fails == 0 ? "PASS" : "FAIL", fails);
	std::fflush(stdout);
	std::_Exit(fails == 0 ? 0 : 1); // the detached watchdog threads
}
