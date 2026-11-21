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
#if defined(Q438_STACK) // mkstack438.py: the trim is r438o's, its counter g_r438o_trims
#define Q438_TRIMS g_r438o_trims
#else
#define Q438_TRIMS g_q438_trims
#endif
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
// The label's memory, as the unit's wait_satisfied reads it for "==" (the owners' labels stay 0: their waits on k >= 1 never pass)
static bool wait_satisfied(const uint32_t* p, bool is64) {
	const uint64_t a = (p[2] & ~3u) | (static_cast<uint64_t>(p[3] & 0xffffu) << 32u);
	if ((p[1] & 7u) != 3) return false;
	if (is64) {
		const uint64_t ref = p[4] | (static_cast<uint64_t>(p[5]) << 32u), mask = p[6] | (static_cast<uint64_t>(p[7]) << 32u);
		return (*reinterpret_cast<const volatile uint64_t*>(a & ~7ull) & mask) == (ref & mask);
	}
	return SoftCp::compare(3, *reinterpret_cast<const volatile uint32_t*>(a & ~3ull), p[5], p[4]);
}
static bool                                  ring_will_satisfy(const uint32_t* p, bool is64, int ring);
// exp 0438 (labelmap, q438ng): the device's mappings and the filter's operand layouts, for the cut label_write_mapped,
// covered_sorted and ho430. g_dev stays empty in every case but the labelmap ones (no snapshot: no check, as before).
namespace bc5::direct {
struct Mapping {
	uint64_t va = 0, size = 0;
	bool     shared = false, readonly = false;
};
struct MappingIndex {
	std::vector<Mapping> v;
	auto                 begin() const { return v.begin(); }
	auto                 end() const { return v.end(); }
	size_t               size() const { return v.size(); }
};
static std::mutex                                 g_deps_mu;
static std::vector<std::pair<int, uint64_t>>      g_deps; // F4's kernel dependencies asked for
struct Device {
	static void add_next_submit_dependency(int ring, uint64_t seq) {
		std::lock_guard lk(g_deps_mu);
		g_deps.emplace_back(ring, seq);
	}
};
} // namespace bc5::direct
namespace bc5::policy { // backend/src/policy.cpp memory_operands, the three label-write packets (WRITE_DATA, RELEASE_MEM, EOP)
static std::vector<std::pair<uint64_t, uint64_t>> memory_operands(const uint32_t* p, uint32_t len) {
	std::vector<std::pair<uint64_t, uint64_t>> out;
	if ((p[0] >> 30) != 3 || len < 2) return out;
	const auto op   = static_cast<uint8_t>((p[0] >> 8) & 0xff);
	auto       addr = [&](uint32_t lo, uint32_t hi) { return (static_cast<uint64_t>(p[lo]) & ~3ull) | (static_cast<uint64_t>(p[hi] & 0xffffu) << 32); };
	if (op == 0x37 && len >= 4 && (((p[1] >> 8) & 0xf) == 1 || ((p[1] >> 8) & 0xf) == 2 || ((p[1] >> 8) & 0xf) == 5)) out.emplace_back(addr(2, 3), (len - 4) * 4ull);
	if (op == 0x49 && len >= 6 && ((p[2] >> 29) & 7) != 0) out.emplace_back(addr(3, 4), 8);
	if (op == 0x47 && len >= 4 && ((p[3] >> 29) & 7) != 0) out.emplace_back(addr(2, 3), 8);
	return out;
}
} // namespace bc5::policy
namespace cv412 {
inline bool hole(bool, bool) { return false; }
} // namespace cv412
struct TestDev {
	std::mutex                         m;
	std::vector<bc5::direct::Mapping>  maps;
	std::shared_ptr<const bc5::direct::MappingIndex> sorted_mappings() {
		std::lock_guard lk(m);
		auto            p = std::make_shared<bc5::direct::MappingIndex>();
		p->v              = maps;
		std::sort(p->v.begin(), p->v.end(), [](const bc5::direct::Mapping& a, const bc5::direct::Mapping& b) { return a.va < b.va; });
		return p;
	}
	uint64_t gds_shadow_va() const { return 0; }
	void     map(uint64_t va, uint64_t size) {
        std::lock_guard lk(m);
        maps.push_back({va, size, false, false});
	}
	void unmap(uint64_t va) {
		std::lock_guard lk(m);
		std::erase_if(maps, [va](const bc5::direct::Mapping& x) { return x.va == va; });
	}
};
static std::unique_ptr<TestDev>             g_dev;
static constexpr uint64_t                   kFlAreaBytes = 0x100;
static uint64_t                             fl_crumbs_area() { return 0; }
static std::pair<uint32_t, uint32_t>        ge_probe_range() { return {0, 0}; }
static std::atomic<int>                     g_stub_phase {0}; // >0: the stub submit_now holds this F16 phase (3: holding the device)
#include "q_state.inc"
#ifdef Q438_X
#include "q_cov.inc"
#include "q_lwm.inc"
#include "q_ng.inc"
#endif
#include "q_chain.inc"
#include "q_plw.inc"
#include "q_reg.inc"
#include "q_rws.inc"
#ifdef Q438_NEW
#include "q_q.inc"
#endif
#include "q_ho.inc" // ho430, cut from every unit

// ---- the stub submission ---------------------------------------------------------------------------------------------------
static constexpr int        kOwners = 24;
static uint64_t             g_labels[kOwners];
static ChainSlot*           g_slot_of[kOwners];
static std::thread::id      g_owner_tid[kOwners];
static std::atomic<int>     g_active[kOwners], g_pass[kOwners];
static std::atomic<bool>    g_gated[kOwners], g_nest_ok[kOwners];
static std::atomic<int>     g_prep_us {0}, g_prep_rand_us {0}, g_drop_write {0};
static std::atomic<uint64_t> g_seq_no {0}, g_viol_active {0}, g_viol_flight {0}, g_viol_cap {0}, g_qmax {0}, g_call_max_ns {0};
static std::atomic<uint64_t> g_ph_lock {0}, g_ph_gate {0}, g_ph_prep {0}, g_ph_reg {0}, g_ph_prep_us {0}; // the ungated calls: max per phase (ns)
static void ph_max(std::atomic<uint64_t>& a, uint64_t d) { for (uint64_t m = a.load(); d > m && !a.compare_exchange_weak(m, d);) {} }
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
	const uint64_t t_call = SoftCp::now_ns();
	if (g_stub_phase.load() > 0 && t_f16_slot != nullptr) t_f16_slot->f16_phase.store(g_stub_phase.load()); // as submit_now's 2, 3
	bool writes = false;
	for (uint32_t q = 0; q < num_dwords;) {
		const uint32_t h = ib[q], c = (h >> 16u) & 0x3fffu, len = c == 0x3fffu ? 1 : c + 2;
		if ((h >> 30u) == 3 && ((h >> 8u) & 0xffu) == 0x49u) writes = true;
		q += len;
	}
	if (g_active[o].fetch_add(1) != 0 && !g_nest_ok[o].load()) g_viol_active++;
	uint64_t t_locked = 0, t_gate = 0, t_prep = 0;
	{
		ChainSlot&      s = *g_slot_of[o];
		std::lock_guard lk(s.mu);
		t_locked   = SoftCp::now_ns();
		r.flight_n = static_cast<uint64_t>(std::count(s.f10_flight.begin(), s.f10_flight.end(), label_of(o)));
		if (r.flight_n == 0 && writes) g_viol_flight++;
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
	t_gate = SoftCp::now_ns();
	if (g_hook) g_hook(o, r.seqs.front());
	const int pr = g_prep_us.load() + (g_prep_rand_us.load() > 0 ? static_cast<int>(SoftCp::now_ns() % static_cast<uint64_t>(g_prep_rand_us.load())) : 0);
	if (pr > 0) std::this_thread::sleep_for(std::chrono::microseconds(pr)); // the preparation and the CS
	t_prep = SoftCp::now_ns();
	for (int d = g_drop_write.load(); d > 0;) { // the filter dropped a write: its early entry is never registered for real
		if (!g_drop_write.compare_exchange_weak(d, d - 1)) continue;
		std::erase(executed, 3u);
		break;
	}
#ifdef Q438_X
	if (g_dev) { // the filter: a packet whose memory operand is not mapped is NOPed (backend policy.cpp), so it is not registered
		const auto maps = g_dev->sorted_mappings();
		std::erase_if(executed, [&](uint32_t q) {
			const uint32_t h = ib[q], c = (h >> 16u) & 0x3fffu, len = c == 0x3fffu ? 1 : c + 2;
			return !lw_packet_mapped(*maps, 0, ib + q, len);
		});
	}
#endif
	register_label_writes(ib, num_dwords, executed, g_seq_no.fetch_add(1) + 1, ring);
	if (!g_gated[o].load() && !g_nest_ok[o].load()) {
		const uint64_t t_reg = SoftCp::now_ns();
		ph_max(g_ph_lock, t_locked - t_call); ph_max(g_ph_gate, t_gate - t_locked); ph_max(g_ph_prep, t_prep - t_gate); ph_max(g_ph_reg, t_reg - t_prep);
		if (t_prep - t_gate > g_ph_prep.load() - 1) g_ph_prep_us = static_cast<uint64_t>(pr);
	}
	if (!g_gated[o].load() && !g_nest_ok[o].load())
		for (uint64_t d = SoftCp::now_ns() - t_call, m = g_call_max_ns.load(); d > m && !g_call_max_ns.compare_exchange_weak(m, d);) {
		}
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
	std::printf("random: longest game-thread wait for an early writer %.3f ms (%" PRIu64 " such waits); longest ungated submit_now (stub, entry to registration) %.3f ms\n", static_cast<double>(g_r438_wait_max.load()) / 1e6, g_r438_waits.load(),
	            static_cast<double>(g_call_max_ns.load()) / 1e6);
	std::printf("random: ungated submit_now phases, max ms: slot lock %.3f, gate %.3f, preparation sleep %.3f (asked %" PRIu64 " us at that max), register_label_writes %.3f\n",
	            g_ph_lock.load() / 1e6, g_ph_gate.load() / 1e6, g_ph_prep.load() / 1e6, g_ph_prep_us.load(), g_ph_reg.load() / 1e6);
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
// Risk a: the submitter held in submit_now (as by GPU back-pressure, g_cq_fences >= 24, or a recovery's 12 s) while a game
// thread waits on its queued entry's early write. The wait must neither end early nor be cut by a timeout: it runs until
// the real registration, and r438's compare-only BUG line ("has waited ... for an early-registered writer") marks every
// 100 ms of it (at most 10 lines).
static void det_backpressure(int o) {
	g_gated[o] = true;
	g_pass[o]  = 0;
	const size_t b0 = lines_with("for an early-registered writer to reach the ring");
	std::thread  t([o] {
        BEGIN_OWNER(o);
        append(o, 3);
        chain_flush(1);
        wait_until([o] { return g_active[o].load() == 1; }, "the entry held in submit_now");
        std::atomic<int> got {-1};
        std::thread      game([&got, o] {
            t_game = true;
            got    = wait_ok(o, 3) ? 1 : 0;
        });
        std::this_thread::sleep_for(std::chrono::milliseconds(350));
        const int held = got.load();
        g_pass[o]++; // back-pressure gone: the entry registers its write
        game.join();
        CHECK(held == -1, "backpressure: the wait ended (%d) while its writer was held", held);
        CHECK(got.load() == 1, "backpressure: no writer after the release");
        chain_flush(5);
	});
	t.join();
	g_gated[o]     = false;
	const size_t n = lines_with("for an early-registered writer to reach the ring") - b0;
	CHECK(n >= 3 && n <= 4, "backpressure: %zu BUG lines for a 350-ms wait (one per 100 ms)", n);
	std::printf("det backpressure: the wait held 350 ms ended only at the release, %zu BUG lines (\"has waited ... for an early-registered writer\")\n", n);
}
// Risk c: g_plw past its 8192-entry trim while a queued entry's early write is among the oldest: it must stay.
static uint64_t g_fill_label;
static void det_trim(int o) {
	g_gated[o] = true;
	g_pass[o]  = 0;
	std::thread t([o] {
		BEGIN_OWNER(o);
		append(o, 5);
		chain_flush(1); // early entry of 5, old: g_plw is small now
		wait_until([o] { return g_active[o].load() == 1; }, "the entry held in submit_now");
		std::vector<uint32_t> fill;
		std::vector<uint32_t> at;
		const uint64_t        a = reinterpret_cast<uintptr_t>(&g_fill_label);
		for (uint32_t i = 0; i < 1000; i++) {
			at.push_back(static_cast<uint32_t>(fill.size()));
			const uint32_t p[8] = {0xC0064900u, 0x00000528u, 0x40010000u, static_cast<uint32_t>(a), static_cast<uint32_t>(a >> 32u), i, 0, 0};
			fill.insert(fill.end(), p, p + 8);
		}
		size_t max_n = 0;
		for (int k = 0; k < 10; k++) { // 10,000 real writes of another label: the trim runs
			register_label_writes(fill.data(), static_cast<uint32_t>(fill.size()), at, 700000 + static_cast<uint64_t>(k), bc5::direct::kGfxRing);
			std::lock_guard lk(g_plw_mutex);
			max_n = std::max(max_n, g_plw.size());
		}
		const size_t kept = early_entries(label_of(o));
		std::atomic<int> got {-1};
		std::thread      game([&got, o] {
            t_game = true;
            got    = wait_ok(o, 5) ? 1 : 0;
		});
		std::this_thread::sleep_for(std::chrono::milliseconds(30));
		const int held = got.load();
		g_pass[o]++;
		game.join();
		CHECK(kept == 1, "trim: the queued entry's early write was dropped by the trim (%zu left)", kept);
		CHECK(held == -1 && got.load() == 1, "trim: the wait on the queued write returned %d before its registration, %d after", held, got.load());
		CHECK(Q438_TRIMS.load() >= 1, "trim: no trim ran (g_plw at most %zu)", max_n);
		std::printf("det trim: g_plw reached %zu entries, %" PRIu64 " trims; the early write kept %zu, the wait %d then %d\n", max_n, Q438_TRIMS.load(), kept, held, got.load());
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

#ifdef Q438_X
// ---- labelmap and q438ng (mkq438x.py) -------------------------------------------------------------------------------------
static const char* const kNever = "of a queued chain never reached the ring";
// (i): a label write to an address with no GPU mapping leaves no early entry and no BUG line; its mapped twin gets one.
static void det_lwm_map(int om, int ou) {
	g_dev = std::make_unique<TestDev>();
	g_dev->map(label_of(om), 8);
	const size_t   bug0  = lines_with(kNever);
	const uint64_t skip0 = g_lwm_skipped.load();
	size_t         early[2] {};
	int            k = 0;
	for (int o: {om, ou}) {
		g_gated[o] = true;
		g_pass[o]  = 0;
		std::thread t([o, &early, k] {
			BEGIN_OWNER(o);
			append(o, 1);
			chain_flush(1);
			wait_until([o] { return g_active[o].load() == 1; }, "the entry in submit_now");
			early[k] = early_entries(label_of(o));
			g_pass[o]++;
			chain_flush(5);
		});
		t.join();
		g_gated[o] = false;
		k++;
	}
	std::atomic<int> rm {-1}, ru {-1};
	std::thread([&] {
		t_game = true;
		rm     = wait_ok(om, 1) ? 1 : 0;
		ru     = wait_ok(ou, 1) ? 1 : 0;
	}).join();
	const size_t bugs = lines_with(kNever) - bug0;
	CHECK(early[0] == 1 && early[1] == 0, "labelmap (i): early entries mapped %zu (want 1), unmapped %zu (want 0)", early[0], early[1]);
	CHECK(bugs == 0, "labelmap (i): %zu BUG lines", bugs);
	CHECK(g_lwm_skipped.load() == skip0 + 1, "labelmap (i): the scan left out %" PRIu64 " writes (want 1)", g_lwm_skipped.load() - skip0);
	CHECK(rm.load() == 1 && ru.load() == 0, "labelmap (i): after the submissions the mapped label has its writer (%d), the unmapped none (%d)", rm.load(), ru.load());
	std::printf("det labelmap (i): early entries mapped %zu, unmapped %zu; left out %" PRIu64 "; BUG lines %zu; real writer mapped %d, unmapped %d\n", early[0], early[1], g_lwm_skipped.load() - skip0, bugs, rm.load(),
	            ru.load());
	g_dev.reset();
}
// (iii): the mapping changes between the scan and submit_now.
//   a. mapped at the scan, unmapped at the submit: the early entry never turns real: a BUG line at the entry's end, the entry
//      removed; a game-thread wait held on it until then, then sees no writer (the GPU will not write it either).
//   b. unmapped at the scan, mapped at the submit: no early entry; the real write appears at the submit. In between a
//      game-thread wait sees no writer (as before r438/q438 for any writer not yet submitted).
static void det_lwm_change(int oa, int ob) {
	g_dev          = std::make_unique<TestDev>();
	const size_t b0 = lines_with(kNever);
	int          held_a = 0, end_a = -1, before_b = 0, end_b = -1;
	size_t       early_a = 0, early_b = 0;
	g_dev->map(label_of(oa), 8);
	g_gated[oa] = true;
	g_pass[oa]  = 0;
	std::thread ta([&] {
		BEGIN_OWNER(oa);
		append(oa, 1);
		chain_flush(1);
		wait_until([oa] { return g_active[oa].load() == 1; }, "a: the entry in submit_now");
		early_a = early_entries(label_of(oa));
		g_dev->unmap(label_of(oa));
		std::atomic<int> got {-1};
		std::thread      game([&got, oa] {
            t_game = true;
            got    = wait_ok(oa, 1) ? 1 : 0;
		});
		std::this_thread::sleep_for(std::chrono::milliseconds(30));
		held_a = got.load();
		g_pass[oa]++;
		game.join();
		end_a = got.load();
		chain_flush(5);
	});
	ta.join();
	g_gated[oa]      = false;
	const size_t bug_a = lines_with(kNever) - b0;
	g_gated[ob] = true;
	g_pass[ob]  = 0;
	std::thread tb([&] {
		BEGIN_OWNER(ob);
		append(ob, 1);
		chain_flush(1);
		wait_until([ob] { return g_active[ob].load() == 1; }, "b: the entry in submit_now");
		early_b = early_entries(label_of(ob));
		g_dev->map(label_of(ob), 8);
		std::atomic<int> got {-1};
		std::thread      game([&got, ob] { // no early entry: it must return at once (no writer); -1 after 30 ms is a waiter on one
            t_game = true;
            got    = wait_ok(ob, 1) ? 1 : 0;
		});
		std::this_thread::sleep_for(std::chrono::milliseconds(30));
		before_b = got.load();
		g_pass[ob]++;
		game.join();
		chain_flush(5);
		std::thread([&end_b, ob] {
			t_game = true;
			end_b  = wait_ok(ob, 1) ? 1 : 0;
		}).join();
	});
	tb.join();
	g_gated[ob] = false;
	const size_t bug_b = lines_with(kNever) - b0 - bug_a;
	CHECK(early_a == 1 && held_a == -1 && end_a == 0 && bug_a == 1 && early_entries(label_of(oa)) == 0,
	      "labelmap (iii a): early %zu, the wait %d while queued then %d, BUG lines %zu, left %zu", early_a, held_a, end_a, bug_a, early_entries(label_of(oa)));
	CHECK(early_b == 0 && before_b == 0 && end_b == 1 && bug_b == 0, "labelmap (iii b): early %zu, the wait %d before the submit, %d after, BUG lines %zu", early_b, before_b, end_b, bug_b);
	std::printf("det labelmap (iii a, mapped at the scan, unmapped at the submit): early %zu, the wait held %d then %d (no writer), BUG lines %zu\n", early_a, held_a, end_a, bug_a);
	std::printf("det labelmap (iii b, unmapped at the scan, mapped at the submit): early %zu, the wait %d before the submit, %d after, BUG lines %zu\n", early_b, before_b, end_b, bug_b);
	g_dev.reset();
}
// q438ng: entry 1 held in submit_now, entry 2 (the writer of L, value 2) queued behind it; L's memory holds a stale 1; an acb
// on bc5-ring (not a game thread) waits on L == 1.
//   the gate: acb_ready's test (acb_wait_unready, unit line ~7665): must hold the acb while the writer is queued;
//   the submit stage as today: ho430::at_wait (F10, F16, F18) then submit_split's keep test (unit ~10655): it returns
//   after its bounds with the writer still queued, and the stale memory passes the wait: the hazard, shown, not asserted.
static void det_ng(int o) {
	g_labels[o] = 1; // last frame's value
	g_stub_phase = 3; // entry 1 holds the device (F16 phase 3: no phase-gate give-up)
	g_gated[o]   = true;
	g_pass[o]    = 0;
	const uint64_t L = label_of(o);
	uint32_t       w[9];
	wait64(w, L, 1);
	int      gate_q = -1, gate_r = -1;
	bool     queued_at_return = false, passes_today = false, kept = false;
	double   at_ms = 0;
	size_t   deps_after = 0;
	std::thread t([&] {
		BEGIN_OWNER(o);
		static const uint32_t nowrite[3] = {0xC0011000u, static_cast<uint32_t>(o), 1};
		chain_append(nullptr, 0, nowrite, 3, "dcb", false); // entry 1: writes nothing
		chain_flush(1);
		wait_until([o] { return g_active[o].load() == 1; }, "entry 1 held in submit_now");
		append(o, 2); // entry 2: the writer, L = 2
		chain_flush(1);
		std::thread ring([&] { // bc5-ring: not a game thread
			gate_q = acb_wait_unready(w, true, L, 0) ? 1 : 0;
			const uint64_t t0 = SoftCp::now_ns();
			ho430::at_wait(w, true, L, "acb", 0, w, 9, 0);
			at_ms            = static_cast<double>(SoftCp::now_ns() - t0) / 1e6;
			queued_at_return = early_entries(L) != 0;
			kept             = !wait_satisfied(w, true) && ring_will_satisfy(w, true, 0);
			passes_today     = wait_satisfied(w, true);
		});
		ring.join();
		g_pass[o] = 100; // both entries go
		chain_flush(5);
		std::thread ring2([&] {
			gate_r = acb_wait_unready(w, true, L, 0) ? 1 : 0;
			{
				std::lock_guard lk(bc5::direct::g_deps_mu);
				bc5::direct::g_deps.clear();
			}
			ho430::at_wait(w, true, L, "acb", 0, w, 9, 0);
			std::lock_guard lk(bc5::direct::g_deps_mu);
			deps_after = bc5::direct::g_deps.size();
		});
		ring2.join();
	});
	t.join();
	g_gated[o]   = false;
	g_stub_phase = 0;
	CHECK(gate_q == 1, "q438ng: acb_ready's test let the acb go (%d) while its label's writer was queued", gate_q);
	CHECK(gate_r == 0, "q438ng: acb_ready's test still held the acb (%d) after the writer was submitted", gate_r);
	CHECK(deps_after >= 1, "q438ng: after the writer's submission F4 asked for no kernel dependency");
	std::printf("det q438ng: the gate held the acb while the writer was queued %d, let it go after the writer's submission %d (F4 dependencies %zu)\n", gate_q, gate_r == 0 ? 1 : 0, deps_after);
	std::printf("det q438ng, today's submit stage with the writer queued: at_wait returned after %.1f ms, the writer still queued %d, the stale value passes the wait %d (kept for the GPU %d)%s\n", at_ms,
	            queued_at_return ? 1 : 0, passes_today ? 1 : 0, kept ? 1 : 0, queued_at_return && passes_today ? ": THE HAZARD (an acb decided without its queued writer)" : "");
	g_labels[o] = 0;
}
#endif


// ---- inflight: q438ng's stale-value window without the queue (any unit; BC5_0438_SUBMITQ off) ----------------------------
// A game thread's chain (the writer of L, value 2) is taken and in its submit_now (held at the stub's gate, F16 phase 3: the
// kernel call in flight); L's memory holds a stale 1; an acb on bc5-ring (not a game thread) waits on L == 1.
//   the gate: acb_ready's test (unit ~7665; mkq438x.py's acb_wait_unready when cut);
//   the submit stage: ho430::at_wait (F10, F16, F18), then the stale value in memory.
// With BC5_0438_INFLIGHT_NG=1 (a mkq438x.py unit) the gate must hold the acb until the writer's real registration.
#ifdef Q438_X
#define ACB_UNREADY(p, is64, label, ring) acb_wait_unready(p, is64, label, ring)
#else
#define ACB_UNREADY(p, is64, label, ring) (!wait_satisfied(p, is64) && !ring_will_satisfy(p, is64, ring)) // acb_ready's test, unit ~7665
#endif
#ifdef Q438_X
static const Wd438* wd438_last(uint64_t label, int decision) { // the newest complete wd438 entry for label with this decision
	const uint64_t n0 = g_wd438_n.load();
	for (uint64_t k = n0; k-- > (n0 > 256 ? n0 - 256 : 0);) {
		const Wd438& e = g_wd438[k & 255u];
		if (e.seq.load() == k + 1 && e.label == label && e.decision == decision) return &e;
	}
	return nullptr;
}
#endif
static int run_inflight() {
	constexpr int o = 21;
#ifdef Q438_X
	const uint64_t h0 = g_ng438_holds[0].load(), r0 = g_ng438_rel[0].load(), f0 = g_ng438_fb.load();
#endif
	g_labels[o]  = 1;
	const char* ph = std::getenv("Q438_INFLIGHT_PHASE"); // 3 (default): holding the device; 1: GPU back-pressure
	g_stub_phase   = ph != nullptr && ph[0] == '1' ? 1 : 3;
	std::printf("inflight: the writer held at F16 phase %d\n", g_stub_phase.load());
	g_gated[o]   = true;
	g_pass[o]    = 0;
	const uint64_t L = label_of(o);
	uint32_t       w[9];
	wait64(w, L, 1);
	std::thread owner([] {
		BEGIN_OWNER(o);
		append(o, 2);
		chain_flush(1); // no queue: the owner itself is in submit_now until the gate opens
		chain_flush(5);
	});
	for (const uint64_t ta = SoftCp::now_ns(); g_active[o].load() != 1;) { // the writer in submit_now (5 s bound)
		if (SoftCp::now_ns() - ta > 5'000'000'000ull) {
			std::printf("FAIL: the writer never reached submit_now\n");
			std::_Exit(2);
		}
		std::this_thread::sleep_for(std::chrono::microseconds(200));
	}
	const int      gate1 = ACB_UNREADY(w, true, L, 0) ? 1 : 0; // this thread is not a game thread: bc5-ring's view
	const uint64_t t0    = SoftCp::now_ns();
	ho430::at_wait(w, true, L, "acb", 0, w, 9, 0);
	const double at_ms = static_cast<double>(SoftCp::now_ns() - t0) / 1e6;
	bool         in_flight = false;
	{
		ChainSlot&      s = *g_slot_of[o];
		std::lock_guard lk(s.mu);
		in_flight = std::find(s.f10_flight.begin(), s.f10_flight.end(), L) != s.f10_flight.end();
	}
	const bool passes = wait_satisfied(w, true);
	const int  gate1b = ACB_UNREADY(w, true, L, 0) ? 1 : 0; // still in flight
	g_pass[o]         = 100;
	owner.join();
	{
		std::lock_guard lk(bc5::direct::g_deps_mu);
		bc5::direct::g_deps.clear();
	}
	const int gate2 = ACB_UNREADY(w, true, L, 0) ? 1 : 0; // the writer registered for real
	ho430::at_wait(w, true, L, "acb", 0, w, 9, 0);
	size_t deps = 0;
	{
		std::lock_guard lk(bc5::direct::g_deps_mu);
		deps = bc5::direct::g_deps.size();
	}
	const int phase_held = g_stub_phase.load();
	g_stub_phase         = 0;
	g_gated[o]           = false;
	g_labels[o]          = 0;
	bool fix = false;
#ifdef Q438_X
	fix = inflight_ng_on();
	{ // wd438: bc5-ring's gate decision while the writer was in flight, with the label's writer state at that moment
		const Wd438* e = wd438_last(L, fix ? 0 : 1);
		std::printf("inflight, wd438's entry of the gate decision: %s\n", e == nullptr ? "MISSING" : "");
		std::fflush(stdout);
		if (e != nullptr) {
			std::printf("   decision %s, memory 0x%" PRIx64 ", reference 0x%" PRIx64 ", writer in flight %d (early entry %d, slots %d, phase %d)\n", e->decision == 0 ? "deferred at the gate" : "met at the gate", e->value, e->ref,
			            e->early || e->slots > 0 ? 1 : 0, e->early ? 1 : 0, e->slots, e->phase[0]);
		}
		CHECK(e != nullptr && e->slots == 1 && e->phase[0] == phase_held, "inflight: wd438 has no gate entry with the writer's slot in flight at phase %d", phase_held);
	}
	if (fix) { // ng438's counts for this hold, then a hold let go by the consumer's 10-s fallback (called as the consumer does)
		const uint64_t dh = g_ng438_holds[0].load() - h0, dr = g_ng438_rel[0].load() - r0, df = g_ng438_fb.load() - f0;
		std::printf("inflight, ng438: holds %" PRIu64 ", released after the registration %" PRIu64 ", by the fallback %" PRIu64 "\n", dh, dr, df);
		CHECK(dh == 1 && dr == 1 && df == 0, "inflight: ng438 counted holds %" PRIu64 ", registration releases %" PRIu64 ", fallbacks %" PRIu64 " (want 1, 1, 0)", dh, dr, df);
		constexpr int o2 = 22;
		g_labels[o2]     = 1;
		g_gated[o2]      = true;
		g_pass[o2]       = 0;
		uint32_t w2[9];
		wait64(w2, label_of(o2), 1);
		std::thread owner2([] {
			BEGIN_OWNER(o2);
			append(o2, 2);
			chain_flush(1);
			chain_flush(5);
		});
		for (const uint64_t ta = SoftCp::now_ns(); g_active[o2].load() != 1 && SoftCp::now_ns() - ta < 5'000'000'000ull;) std::this_thread::sleep_for(std::chrono::microseconds(200));
		const int    held2 = ACB_UNREADY(w2, true, label_of(o2), 0) ? 1 : 0;
		const size_t b0    = lines_with("went by the 10-s fallback");
		ng438_fallback(label_of(o2)); // the queue consumer's 10-s branch (unit ~1682)
		const size_t b1 = lines_with("went by the 10-s fallback") - b0;
		g_pass[o2]      = 100;
		owner2.join();
		g_labels[o2] = 0;
		const uint64_t df2 = g_ng438_fb.load() - f0;
		ng438_line();
		std::string line;
		{
			std::lock_guard lk(g_jm);
			for (const auto& x: g_lines)
				if (x.find("ng438 (exp 0438): t ") != std::string::npos) line = x;
		}
		std::printf("inflight, ng438 fallback case: held %d, fallback releases %" PRIu64 ", BUG lines %zu\n   journal: %s", held2, df2, b1, line.c_str());
		CHECK(held2 == 1 && df2 == 1 && b1 == 1, "inflight: the fallback case held %d, counted %" PRIu64 ", BUG lines %zu (want 1, 1, 1)", held2, df2, b1);
		std::printf("inflight, wd438 (the last entries):\n");
		std::fflush(stdout);
		wd438_dump_to(stdout);
	}
#endif
	std::printf("inflight (BC5_0438_INFLIGHT_NG %s): the gate with the writer in its submit_now: %s (%d, again after at_wait %d); after the writer's real registration: %s (%d), F4 dependencies %zu\n",
	            fix ? "on" : "off", gate1 ? "HELD" : "passed", gate1, gate1b, gate2 ? "held" : "released", gate2, deps);
	std::printf("inflight, the submit stage: at_wait returned after %.1f ms, the writer still in flight %d, the stale value passes the wait %d%s\n", at_ms, in_flight ? 1 : 0, passes ? 1 : 0,
	            !gate1 && in_flight && passes ? ": THE HAZARD (an acb decided while its writer's kernel call is in flight)" : "");
	CHECK(deps >= 1, "inflight: after the writer's registration F4 asked for no kernel dependency");
	CHECK(gate2 == 0, "inflight: the gate still held the acb after the writer's registration");
	if (fix) {
		CHECK(gate1 == 1 && gate1b == 1, "inflight: BC5_0438_INFLIGHT_NG=1 let the acb go (%d, %d) while its writer was in flight", gate1, gate1b);
	}
	return 0;
}

// ---- rings: a two-ring hang through ring order (any unit; BC5_0438_SUBMITQ off) ---------------------------------------------
// The box's shape: acb A (compute) waits on L == 1 reading 0; dcb D (gfx) waits on M == 1 reading 0; neither writes the other's
// label; A's writer W is on the gfx ring behind D. Jobs, in the order the host takes them:
//   E  compute: M = 1                      (registered: D's wait on M is kept against it)
//   D  gfx, a game thread's chain: waits M == 1, then N = 1   (taken, in its submit_now: not yet registered)
//   X  compute acb: waits N == 1 (N holds last frame's 1), then M = 0   (the title orders X after D by N)
//   W  gfx: L = 1
//   A  compute acb: waits L == 1           (kept for the GPU against W on the gfx ring, w428)
// The host's decisions are the real ones: ring_will_satisfy / wait_satisfied on g_plw, acb_ready's test (ACB_UNREADY),
// ho430::at_wait's F4 kernel dependency. Then two simulated rings run the jobs in order (compute first, as a busy gfx ring
// lets it): a WAIT blocks its ring while the memory differs, a job's pending writes go at its end (forget_label_writes).
static uint64_t g_rlab_m = 0, g_rlab_l = 0; // M and L; N is owner 23's label
struct SimOp {
	bool      wait;
	uint64_t* label;
	uint64_t  v;
};
struct SimJob {
	const char*            name;
	int                    ring;
	uint64_t               seq;
	std::vector<SimOp>     ops;
	std::vector<uint64_t>  deps; // F4: jobs (by seq) that must have ended first
	size_t                 pc = 0;
	bool                   done = false;
};
static std::vector<uint32_t> rel_buf(uint64_t* label, uint64_t v) {
	const uint64_t a = reinterpret_cast<uintptr_t>(label);
	return {0xC0064900u, 0x00000528u, 0x40010000u, static_cast<uint32_t>(a), static_cast<uint32_t>(a >> 32u), static_cast<uint32_t>(v), static_cast<uint32_t>(v >> 32u), 0};
}
static void register_job(const SimJob& j) { // its writes, as submit_now registers them
	for (const auto& op: j.ops)
		if (!op.wait) {
			const std::vector<uint32_t> b = rel_buf(op.label, op.v);
			register_label_writes(b.data(), 8, {0}, j.seq, j.ring);
		}
}
static int run_rings() {
	// D's state when X is decided (Q438_RINGS_STATE): flight (its owner's submit_now, no queue), open (appended to its
	// owner's chain, not taken), queued (Q438: behind another entry held in submit_now), submitnow (Q438: its entry in
	// submit_now), real (registered before X). Q438_RINGS_SPLIT=1: X has a head (P = 1) ahead of its wait.
	const char*      st    = std::getenv("Q438_RINGS_STATE");
	const std::string state = st != nullptr ? st : "flight";
	const bool        split = std::getenv("Q438_RINGS_SPLIT") != nullptr && std::getenv("Q438_RINGS_SPLIT")[0] == '1';
	constexpr int o = 23;
	uint64_t*     N = &g_labels[o];
	static uint64_t g_rlab_p = 0;
	g_rlab_m = 0;
	g_rlab_l = 0;
	g_rlab_p = 0;
	*N       = 1; // last frame's value
	g_stub_phase = 3;
	g_gated[o]   = true;
	g_pass[o]    = state == "real" ? 100 : 0;
	std::vector<SimJob> jobs;
	auto                wait_pkt = [](uint64_t* label, uint64_t v, uint32_t* w) { wait64(w, reinterpret_cast<uintptr_t>(label), v); };
	uint32_t            w[9];
	jobs.push_back({"E", 0, 9001, {{false, &g_rlab_m, 1}}, {}});
	register_job(jobs.back());
	wait_pkt(&g_rlab_m, 1, w);
	const bool        d_kept = !wait_satisfied(w, true) && ring_will_satisfy(w, true, bc5::direct::kGfxRing);
	std::atomic<int>  owner_at {0}, go {0};
	std::thread owner([&state, &owner_at, &go] {
		BEGIN_OWNER(o);
		if (state == "queued") { // another entry first, held in submit_now
			static const uint32_t nowrite[3] = {0xC0011000u, static_cast<uint32_t>(o), 0};
			chain_append(nullptr, 0, nowrite, 3, "dcb", false);
			chain_flush(1);
			while (g_active[o].load() != 1) std::this_thread::yield();
		}
		if (state == "open") {
			{
				ChainInSubmit in(true); // the owner inside Direct::submit: the watchdog leaves the chain open
				append(o, 1);
				owner_at = 1;
				while (go.load() == 0) std::this_thread::yield();
			}
			chain_flush(1);
		} else {
			append(o, 1); // D: writes N = 1
			owner_at = 1; // before the flush: without the queue the owner itself stays in submit_now until released
			chain_flush(1);
		}
		chain_flush(5);
		owner_at = 2;
	});
	while (owner_at.load() == 0) std::this_thread::yield();
	if (state == "flight" || state == "submitnow" || state == "queued")
		for (const uint64_t ta = SoftCp::now_ns(); g_active[o].load() != 1 && SoftCp::now_ns() - ta < 5'000'000'000ull;) std::this_thread::sleep_for(std::chrono::microseconds(200));
	if (state == "real")
		while (owner_at.load() != 2) std::this_thread::yield();
	auto d_real = [N]() -> uint64_t {
		std::lock_guard lk(g_plw_mutex);
		for (const auto& e: g_plw)
			if (e.label == reinterpret_cast<uintptr_t>(N) && (e.seq & kR438Early) == 0) return e.seq;
		return 0;
	};
	// X on bc5-ring: its gate, then (when it passes) the submit stage
	wait_pkt(N, 1, w);
	const int x_gate1    = ACB_UNREADY(w, true, reinterpret_cast<uintptr_t>(N), 0) ? 1 : 0;
	bool      d_released = state == "real";
	auto      release_d  = [&] {
        g_pass[o] = 100;
        go        = 1;
        owner.join();
        d_released = true;
	};
	if (x_gate1 && split) { // acb_ready's split: the head (before the wait) goes ahead, the rest waits
		jobs.push_back({"Xhead", 0, 9005, {{false, &g_rlab_p, 1}}, {}});
		register_job(jobs.back());
	}
	int x_gate2 = x_gate1;
	if (x_gate1) {
		release_d();
		x_gate2 = ACB_UNREADY(w, true, reinterpret_cast<uintptr_t>(N), 0) ? 1 : 0;
	}
	{
		std::lock_guard lk(bc5::direct::g_deps_mu);
		bc5::direct::g_deps.clear();
	}
	ho430::at_wait(w, true, reinterpret_cast<uintptr_t>(N), "acb", 0, w, 9, 0);
	std::vector<uint64_t> x_deps;
	{
		std::lock_guard lk(bc5::direct::g_deps_mu);
		for (const auto& [r, sq]: bc5::direct::g_deps) x_deps.push_back(sq);
	}
	const bool x_met = wait_satisfied(w, true);
	SimJob     x {"X", 0, 9002, {{true, N, 1}, {false, &g_rlab_m, 0}}, x_deps};
	if (split && !x_gate1) x.ops.insert(x.ops.begin(), SimOp {false, &g_rlab_p, 1}); // no split: the head goes with it
	if (x_met) std::erase_if(x.ops, [N](const SimOp& op) { return op.wait && op.label == N; });
	jobs.push_back(x);
	register_job(jobs.back());
	if (!d_released) release_d();
	else if (owner.joinable()) owner.join();
	jobs.push_back({"D", bc5::direct::kGfxRing, d_real(), {{true, &g_rlab_m, 1}, {false, N, 1}}, {}});
	if (!d_kept) jobs.back().ops.erase(jobs.back().ops.begin());
	if (state == "real") std::erase_if(jobs, [](const SimJob& j) { return j.name[0] == 'D'; }); // already run: its N = 1 is in memory
	if (state == "real") *N = 1;
	jobs.push_back({"W", bc5::direct::kGfxRing, 9003, {{false, &g_rlab_l, 1}}, {}});
	register_job(jobs.back());
	wait_pkt(&g_rlab_l, 1, w);
	const int  a_gate = ACB_UNREADY(w, true, reinterpret_cast<uintptr_t>(&g_rlab_l), 0) ? 1 : 0;
	const bool a_kept = !wait_satisfied(w, true) && ring_will_satisfy(w, true, 0);
	jobs.push_back({"A", 0, 9004, {{true, &g_rlab_l, 1}}, {}});
	register_job(jobs.back());
	g_stub_phase = 0;
	g_gated[o]   = false;
	if (state == "real") g_rlab_m = 1; // D ran before X: E's M = 1 had reached D
	auto ended = [&](uint64_t seq) {
		for (const auto& j: jobs)
			if (j.seq == seq) return j.done;
		return true;
	};
	for (bool moved = true; moved;) { // each round: the compute ring until it blocks (a busy gfx ring), then one gfx job
		moved = false;
		for (int ring: {0, 0, 0, 0, 0, 0, 0, 0, bc5::direct::kGfxRing}) {
			for (auto& j: jobs) {
				if (j.ring != ring || j.done) continue;
				bool blocked = false;
				for (uint64_t d: j.deps)
					if (!ended(d)) blocked = true;
				while (!blocked && j.pc < j.ops.size()) {
					const SimOp& op = j.ops[j.pc];
					if (op.wait && *op.label != op.v) {
						blocked = true;
						break;
					}
					if (!op.wait) *op.label = op.v;
					j.pc++;
					moved = true;
				}
				if (!blocked) {
					j.done = true;
					moved  = true;
					std::lock_guard lk(g_plw_mutex);
					std::erase_if(g_plw, [&j](const PendingLabelWrite& e) { return e.seq == j.seq && e.ring == j.ring; });
				}
				break;
			}
		}
	}
	bool ng = false, open = false;
#ifdef Q438_X
	ng   = inflight_ng_on();
	open = open_ng_on();
#endif
	std::printf("rings, D %s%s (INFLIGHT_NG %d, OPEN_NG %d, SUBMITQ %s): D's wait on M kept %d; X's gate %s, then %d; X's F4 dependencies %zu; X's wait dropped as met %d; A kept for the GPU %d (gate %d)\n", state.c_str(),
	            split ? ", X split" : "", ng ? 1 : 0, open ? 1 : 0, std::getenv("BC5_0438_SUBMITQ") != nullptr ? std::getenv("BC5_0438_SUBMITQ") : "unset", d_kept ? 1 : 0, x_gate1 ? "HELD" : "passed", x_gate2, x_deps.size(),
	            x_met ? 1 : 0, a_kept ? 1 : 0, a_gate);
	bool hung = false;
	for (const auto& j: jobs) {
		if (j.done) continue;
		hung = true;
		const SimOp* op = j.pc < j.ops.size() ? &j.ops[j.pc] : nullptr;
		std::printf("   %s on the %s ring is stuck%s", j.name, j.ring == bc5::direct::kGfxRing ? "gfx" : "compute", op != nullptr && op->wait ? "" : " behind a dependency or a job ahead\n");
		if (op != nullptr && op->wait) std::printf(" at its wait on %s == %" PRIu64 ", which reads %" PRIu64 "\n", op->label == &g_rlab_m ? "M" : (op->label == &g_rlab_l ? "L" : "N"), op->v, *op->label);
	}
	std::printf("rings: %s\n", hung ? "THE TWO-RING HANG (both rings stuck through ring order)" : "every job ran");
#ifdef Q438_X
	std::printf("rings, ng438: in flight held %" PRIu64 " released %" PRIu64 " longest %.3f ms; open chain held %" PRIu64 " released %" PRIu64 " longest %.3f ms; fallback %" PRIu64 "; busy %" PRIu64 "\n", g_ng438_holds[0].load(), g_ng438_rel[0].load(),
	            static_cast<double>(g_ng438_max[0].load()) / 1e6, g_ng438_holds[1].load(), g_ng438_rel[1].load(), static_cast<double>(g_ng438_max[1].load()) / 1e6, g_ng438_fb.load(), g_ng438_busy.load());
	if (ng || open) {
		ng438_line();
		std::lock_guard lk(g_jm);
		std::printf("rings, journal: %s", g_lines.empty() ? "\n" : g_lines.back().c_str());
	}
	if (state == "open" && ng && open) CHECK(g_ng438_holds[1].load() == 1 && g_ng438_rel[1].load() == 1 && g_ng438_holds[0].load() == 0, "rings open: ng438 counted open holds %" PRIu64 ", releases %" PRIu64 ", in-flight holds %" PRIu64 " (want 1, 1, 0)", g_ng438_holds[1].load(), g_ng438_rel[1].load(), g_ng438_holds[0].load());
#endif
	const bool fix = state == "open" ? (ng && open) : ng;
	CHECK(!(fix && hung), "rings, D %s: the gate did not prevent the two-ring hang", state.c_str());
	*N = 0;
	return 0;
}

#if defined(_WIN32) // Q438_TIMER1=1: Windows' timer at 1 ms, so the stub's sub-ms sleeps are not rounded up to a 15.6-ms tick
extern "C" __declspec(dllimport) unsigned __stdcall timeBeginPeriod(unsigned);
#pragma comment(lib, "winmm.lib")
#endif
int main(int argc, char** argv) {
	const std::string mode = argc > 1 ? argv[1] : "random";
#if defined(_WIN32)
	if (const char* e = std::getenv("Q438_TIMER1"); e != nullptr && e[0] == '1') std::fprintf(stderr, "timer: timeBeginPeriod(1) rc %u\n", timeBeginPeriod(1));
#endif
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
	else if (mode == "inflight") run_inflight();
	else if (mode == "rings") run_rings();
#ifdef Q438_NEW
	else if (mode == "det") {
		if (!q_on) {
			std::printf("FAIL: det needs BC5_0438_SUBMITQ=1\n");
			return 2;
		}
		det_fifo_flight(8);
		det_early(9);
		det_order(7);
		det_backpressure(3);
		det_trim(2);
		det_invariant(10);
		det_cap(11);
		det_nested(12);
		det_flush_all(13, 14, 5);
		det_flush_all(4, 5, 8);
		det_sync(15);
		det_destroy(6);
#ifdef Q438_X
		det_lwm_map(16, 17);
		det_lwm_change(18, 19);
		det_ng(20);
#endif
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
