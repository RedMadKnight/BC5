// Experiment 0430 (tag ho430): F2 and G, after the maintainer's "Tak, zleć poprawkę" (2026-11-16 ~22:00). His play's hang of
// 21:38:40: the compute sort (acb #1980431) waited for label 0x12004b4fc8 == 0, which the graphics buffer dcb #1980428 writes
// (RELEASE_MEM, 0) after its BVH passes. The label held a stale 0 when the acb was submitted, so the wait was dropped as
// met and the sort overwrote memory the running BVH passes still read. Keeping such a wait for the GPU would not help (the GPU
// reads the same stale 0).
// F2, BC5_0430_F2 (on unless "0"): a wait that is satisfied when the host looks, while a job not yet completed on ANOTHER
// ring has a registered pending write to the same label, is not decided until that job has completed: this buffer's own
// submitting thread waits for it on the CPU, at most 250 ms. Refused (and counted) when the writer job holds a kept GPU
// wait on a label this buffer writes (a cycle). The bound running out is counted and journaled. Nothing becomes a GPU wait.
// G, BC5_0430_G (on unless "0"): a ring of label events (waits seen with value and pending writes, writes registered at
// submit, writes the host's filter DROPPED, the F2 events), dumped as g0430-<k>.txt with every dj430 dump; a 30-s summary
// line with the counts, including the GIVEN UP / CYCLE drops of unsatisfied waits. BC5_0430_G_AT=<s>: one more dump at
// that time of the run (g0430-90.txt), for a clean run, which has no stall dump.
// F3, BC5_0430_F3 (on unless "0"), "the missing acquire" (the top session's GO of 2026-11-16 ~22:40 for the precise form):
// a runtime set, in memory only, of cross-queue labels: a label some buffer waited on with == V while a job on another ring
// had a pending write of V to it. At the submit of a buffer that releases such a label (a RELEASE_MEM or WRITE_DATA of V)
// while the label already holds V (the stale case of the 21:38 hang), the host first sets the label to a value that is not
// V: the last such value a wait saw in this run, else V xor 1. The waiter then finds its wait unsatisfied with a pending
// write that satisfies it, and the existing path keeps it for the GPU: it starts when the release executes, as on the
// console. Not done (counted) when the release may not run (inside a COND_EXEC range, among the host's drops, its label not
// mapped), when the buffer itself waits on the label, or when a job in flight on another ring already holds a kept wait
// on it. A label first seen at a wait whose writer is already submitted falls back to F2 (counted).
// HO430_SHARED (the shared patch, mkswap0430.py): the fix alone. F2 and F3 read std::getenv (the lean build too) under the
// shared names BC5_DIRECT_XQ_PENDING (F2), BC5_DIRECT_XQ_ACQUIRE (F3) and BC5_DIRECT_XQ_FENCE (F4, F2's order done by the
// kernel: a CS dependency instead of the CPU wait), each on unless "0"; G is compiled off. They act
// only on a wait whose label has a pending write on ANOTHER ring, so with one ring (way 2 off) they do nothing.
// F5, "the precise form" (2026-11-17, the top session's main line after the maintainer's slow play on build 8):
// BC5_0430_F5 / shared BC5_DIRECT_XQ_PRECISE, on unless "0". F2 and F4 hold a waiter until the WHOLE writer job has
// completed, but the console's wait ends at the writer's release, inside the job. F3 already learns, at the writer's
// submit, whether the stale case is excluded for each cross-queue label the writer releases. It is excluded when F3
// preset the label, or found it not holding the released value, with no other job in flight writing it or holding a
// kept wait on it. For such a writer job, the label can reach the released value only through that job's own release.
// So a wait found satisfied while the job is still pending means the release has already run on the GPU, and needs no
// order. F5 drops those writer jobs from F2's and F4's list. A writer job whose stale case was not excluded keeps F2/F4:
// COND_EXEC, a host drop, the label unknown at its submit, a rebuilt buffer, or another writer in flight.
// No packet is inserted and no buffer is rewritten. Counted as F5-skipped.
// F6, "the GPU decides" (2026-11-17, after the shared control h430C4 hung at 11:59): BC5_0430_F6 / shared
// BC5_DIRECT_XQ_KEEP, on unless "0". In h430C4 the compute buffer was submitted BEFORE this frame's writer of its
// cross-queue label. The label still held the last frame's released value, no writer was in flight, so F2/F4 had no job
// to order on and F3 (at the writer's submit) came too late; the host dropped the wait as met. The console decides a
// WAIT_REG_MEM when its queue reaches the packet, not at submit. F6 keeps such a wait for the GPU, as the host keeps an
// unsatisfied one with a pending writer: a wait (== V) on a label of F3's cross-queue set, satisfied when the host looks,
// with no job in flight writing the label. No memory is written. Counted as F6-kept. Not when the writer seen when the
// label was learned runs on the waiter's own ring (it would sit behind the kept wait: a deadlock). A kept wait whose
// label has not come back within 1 s, with no writer in flight, is journaled (it holds its ring until the TDR).
// Compute-ring waiters (acb) only, since h430Q1: a kept gfx dcb wait held the GFX ring 1.1 s while the host's own submit
// preparation (a remap waiting for GPU idle) blocked the game thread that was to submit the writer acb.
// F7, "count, not look" (2026-11-17 after h430C4, h430C6 and exp 0432's d432V15): BC5_0430_F7 / shared
// BC5_DIRECT_XQ_COUNT, on unless "0". The title's busy mark of a cross-queue label is a plain CPU store, and in the
// failures the compute buffer was submitted before that mark and before its writer, so no look at the label's value, on
// the host or on the GPU (V15: kept, passed early), can tell the stale 0 from the released one. The submission order can:
// per label, releases (writes of the waited value registered at a writer's submit on another ring) and waiting
// submissions strictly alternate (x1: 0x12004b4fc8 24/24). F7 keeps the balance releases - waiting submissions per label
// (acb waiters, == waits) from a release on; after 32 events in {0, 1} the label is stable 1:1. A waiting submission that
// would take a stable label's balance below 0 has its release still to come: its submitting thread waits (at most 250 ms)
// until the next release is registered; then F3/F4/F5 and the host's keep test see the writer pending. A bound reached is
// counted and journaled and the label resyncs. Labels that are not stable 1:1 (0x12004b37c8: 4 waits a release) are left.
// In-process only: the counts live in this store and die with the process; nothing is written to a file or carried
// between runs (the maintainer's rule against learned windows). Never held when the waiter's thread is the one that
// registered the label's last release (it would submit the release itself after the hold: counted as same thread).
// A hold also records when the label first stops holding ref (the busy mark) and both threads' names, for the record.
// F8, "the acb is an observe point" (2026-11-17, from F7's first holds and the code): BC5_0430_F8 / shared
// BC5_DIRECT_XQ_ORDER, on unless "0". The acbs come through the title's compute queues, which bc5-ring polls and
// submits at once; the dcbs go through the title's submit call and, with BC5_DIRECT_CHAIN=2, are held in that thread's
// chain (ADR 0010 section B) for up to 2 ms, unsubmitted and their writes unregistered. bc5-ring's own chain_flush
// does not touch another thread's chain, so an acb the title submitted after a dcb could reach the device before it
// and decide its wait on the last frame's label: F848's whole family, and F7's holds ended exactly when that chain went.
// F8: at an acb's first wait, every other thread's held chain is submitted first (chain_submit, foreign, why 11: the
// non-blocking path the watchdog uses; a chain whose owner is inside its own submit is left to it). Then the existing
// paths decide with the writers registered. No stamps, no counting, no labels.
namespace ho430 {
inline bool not0(const char* e) {
	return e == nullptr || !(e[0] == '0' && e[1] == 0);
}
#ifdef HO430_SHARED
inline bool f2_on() {
	static const bool v = not0(std::getenv("BC5_DIRECT_XQ_PENDING"));
	return v;
}
inline bool g_on() {
	return false;
}
inline bool f3_on() {
	static const bool v = not0(std::getenv("BC5_DIRECT_XQ_ACQUIRE"));
	return v;
}
inline bool f4_on() {
	static const bool v = not0(std::getenv("BC5_DIRECT_XQ_FENCE"));
	return v;
}
inline bool f5_on() {
	static const bool v = not0(std::getenv("BC5_DIRECT_XQ_PRECISE"));
	return v;
}
inline bool f6_on() {
	static const bool v = not0(std::getenv("BC5_DIRECT_XQ_KEEP"));
	return v;
}
inline bool f6b_on() {
	static const bool v = not0(std::getenv("BC5_DIRECT_XQ_KEEP_ALL"));
	return v;
}
inline bool f7_on() {
	static const bool v = not0(std::getenv("BC5_DIRECT_XQ_COUNT"));
	return v;
}
inline bool f7_sensor() { // "2": count the stale waits only, hold none (the step-(2) run: F9 alone, F7 as a pure sensor)
	static const bool v = [] {
		const char* e = std::getenv("BC5_DIRECT_XQ_COUNT");
		return e != nullptr && e[0] == '2' && e[1] == 0;
	}();
	return v;
}
inline bool f8_on() {
	static const bool v = not0(std::getenv("BC5_DIRECT_XQ_ORDER"));
	return v;
}
#else
inline bool f2_on() {
	static const bool v = not0(BC5_DIAG_ENV("BC5_0430_F2"));
	return v;
}
inline bool g_on() {
	static const bool v = not0(BC5_DIAG_ENV("BC5_0430_G"));
	return v;
}
inline bool f3_on() {
	static const bool v = not0(BC5_DIAG_ENV("BC5_0430_F3"));
	return v;
}
inline bool f4_on() {
	static const bool v = not0(BC5_DIAG_ENV("BC5_0430_F4"));
	return v;
}
inline bool f5_on() {
	static const bool v = not0(BC5_DIAG_ENV("BC5_0430_F5"));
	return v;
}
inline bool f6_on() {
	static const bool v = not0(BC5_DIAG_ENV("BC5_0430_F6"));
	return v;
}
inline bool f6b_on() {
	static const bool v = not0(BC5_DIAG_ENV("BC5_0430_F6B"));
	return v;
}
inline bool f7_on() {
	static const bool v = not0(BC5_DIAG_ENV("BC5_0430_F7"));
	return v;
}
inline bool f7_sensor() {
	static const bool v = [] {
		const char* e = BC5_DIAG_ENV("BC5_0430_F7");
		return e != nullptr && e[0] == '2' && e[1] == 0;
	}();
	return v;
}
inline bool f8_on() {
	static const bool v = not0(BC5_DIAG_ENV("BC5_0430_F8"));
	return v;
}
#endif
enum : uint8_t { kWait = 1, kWrite = 2, kDropped = 3, kF2Waited = 4, kF2Cycle = 5, kF2Bound = 6, kGivenUp = 7, kCycle = 8, kF3Preset = 9, kF3Refused = 10, kF3First = 11, kF3NotStale = 12, kF3Met = 13, kF4Fence = 14, kF5Skip = 15, kF6Kept = 16, kF7Held = 17, kF7Bound = 18 };
constexpr uint32_t kTypes = 19;
struct Cross {
	uint64_t v         = 0; // the released value the waits wait for (== v)
	uint64_t nonv      = 0; // the last other value a wait saw on the label
	bool     is64      = false;
	bool     have_nonv = false;
	int      wring     = -100; // F6: the ring of the writer seen when the label was learned (-100: unknown)
};
struct Ev {
	uint64_t t_ns  = 0;
	uint64_t label = 0;
	uint64_t value = 0; // the label's value (waits) or the value written
	uint64_t ref   = 0; // a wait's reference; a write's job seq
	uint64_t n     = 0; // the submission count when it happened
	uint32_t off   = 0;
	int32_t  ring  = 0;
	uint8_t  type  = 0;
	uint8_t  func  = 0;
	uint8_t  sat   = 0; // a wait: satisfied when seen
	uint8_t  pend  = 0; // a wait: pending writes to the label (capped at 255)
	char     kind[4] {};
};
constexpr uint32_t kEvN = 32768;
struct Store {
	std::mutex                                 m;
	std::vector<Ev>                            r;
	uint64_t                                   total = 0;
	std::map<std::pair<int, uint64_t>, std::vector<uint64_t>> job_waits; // (ring, seq) -> the labels of its kept GPU waits
	std::map<uint64_t, Cross>                  cross;                    // F3: the cross-queue labels, in memory only
	std::map<uint64_t, uint64_t>               preset_at;                // F3: label -> SoftCp::now_ns() of a preset whose release has not been seen yet
	std::map<std::pair<int, uint64_t>, std::vector<uint64_t>> job_safe; // F5: (ring, seq) -> labels whose stale case F3 excluded at its submit
	struct Kept {
		uint64_t t_ns = 0, ref = 0;
		bool     is64 = false;
		int      ring = 0;
	};
	std::map<uint64_t, Kept>                   f6_kept; // F6: label -> the last wait kept for the GPU, watched until the label holds ref again
	uint64_t                                   f6_long = 0; // F6: kept waits whose label did not come back within 1 s with no writer in flight
	std::map<uint64_t, uint64_t>               f6_by_label;  // F6: kept waits per label (how many distinct labels it covers)
	uint64_t                                   f6_shared = 0; // F6: not kept because the waiter's host ring carries more than one guest queue
	struct Cnt {
		uint64_t ref     = 0;
		int      wring   = -100; // the waiters' ring
		bool     synced  = false; // counting since a release
		int64_t  bal     = 0;     // releases registered minus waiting submissions since the sync
		uint32_t ok      = 0;     // consecutive events with bal in {0, 1}
		uint64_t rel     = 0;     // releases registered (a hold waits for this to move)
		int      rtid    = 0;     // the thread that registered the last release
		char     rname[16] {};    // its name
	};
	std::map<uint64_t, Cnt>                    f7;           // F7: label -> its release/wait count
	uint64_t                                   f7_held = 0, f7_bound = 0, f7_ns = 0;
	uint64_t                                   f8_calls = 0, f8_chains = 0, f8_ns = 0, f8_busy = 0, f8_gone = 0, f8_bound = 0; // F8: observe points taken, other threads' chains submitted, time
	uint64_t                                   f7_would = 0; // F7 as a sensor: stale waits seen and not held
	uint64_t                                   f7_same = 0;  // F7: not held, the waiter's thread is the one that registers the release
	uint64_t                                   f7_hist[6] {}; // F7: holds < 1, < 5, < 20, < 50, < 250 ms, bound
	uint64_t                                   f7_cls[3] {};  // F7: holds where a title submit call was running at the start / began during it / neither
	uint64_t                                   f7_mark[6] {}; // F7: in a hold, the title's busy mark after the hold's start: < 0.1, < 1, < 5, < 20 ms, later, none
	uint64_t                                   c[kTypes] {};
	uint64_t                                   waited_ns = 0;
};
// F5: what F3 found for the buffer it was just given, handed to job_submitted on the same thread (same buffer and length)
inline thread_local const uint32_t*  t_f5_ib = nullptr;
inline thread_local uint32_t         t_f5_n  = 0;
inline thread_local std::vector<uint64_t> t_f5_safe;
inline void dump(int k);
inline Store& st() {
	static Store s;
	return s;
}
inline void add(const Ev& e) {
	Store&          s = st();
	std::lock_guard lk(s.m);
	if (s.r.size() != kEvN) s.r.assign(kEvN, Ev {});
	s.r[s.total % kEvN] = e;
	s.total++;
	if (e.type < kTypes) s.c[e.type]++;
}
inline Ev ev(uint8_t type, uint64_t label, const char* kind, int ring, uint32_t off) {
	Ev e;
	e.t_ns  = SoftCp::now_ns();
	e.type  = type;
	e.label = label;
	e.ring  = ring;
	e.off   = off;
	e.n     = g_submits.load();
	std::snprintf(e.kind, sizeof(e.kind), "%s", kind != nullptr ? kind : "-");
	return e;
}
// F6: a kept wait whose label does not come back holds its ring until the TDR: say so. At most every 100 ms. The two locks
// are taken one after the other, never nested (job_done runs under g_plw_mutex and takes the store's lock).
inline void f6_watch() {
	static std::atomic<uint64_t> last {0};
	const uint64_t               now = SoftCp::now_ns();
	uint64_t                     was = last.load();
	if (!f6_on() || now - was < 100'000'000ull || !last.compare_exchange_strong(was, now)) return;
	std::vector<uint64_t> busy; // labels a job in flight writes
	{
		std::lock_guard lw(g_plw_mutex);
		for (const auto& w: g_plw) busy.push_back(w.label);
	}
	Store&          s = st();
	std::lock_guard lk(s.m);
	for (auto it = s.f6_kept.begin(); it != s.f6_kept.end();) {
		const uint64_t a = it->first;
		const uint64_t v = it->second.is64 ? *reinterpret_cast<const volatile uint64_t*>(a & ~7ull) : *reinterpret_cast<const volatile uint32_t*>(a & ~3ull);
		if (v == it->second.ref) { it = s.f6_kept.erase(it); continue; }
		if (now - it->second.t_ns > 1'000'000'000ull && std::find(busy.begin(), busy.end(), a) == busy.end()) {
			s.f6_long++;
			journal("ho430 F6: a wait kept on ring %d for 0x%" PRIx64 " (== 0x%" PRIx64 ") %.0f ms ago: the label holds 0x%" PRIx64 " and no writer is in flight (%" PRIu64 " such)\n", it->second.ring, a, it->second.ref,
			        static_cast<double>(now - it->second.t_ns) / 1e6, v, s.f6_long);
			it = s.f6_kept.erase(it);
			continue;
		}
		++it;
	}
}
// One pass over a submitted job: its kept waits (for F2's cycle check), its registered writes and the writes the filter
// dropped (G). executed: the offsets the filter kept, in order.
inline void job_submitted(const uint32_t* ib, uint32_t num_dwords, const std::vector<uint32_t>& executed, uint64_t seq, int ring, const char* kind) {
	std::vector<uint64_t> safe; // F5: only when F3 saw this very buffer just before its submit
	if (t_f5_ib == ib && t_f5_n == num_dwords) safe.swap(t_f5_safe);
	t_f5_ib = nullptr;
	t_f5_safe.clear();
	f6_watch(); // F6 (no lock held here)
	if (!f2_on() && !g_on() && !f3_on() && !f7_on()) return;
	std::vector<uint64_t> waits;
	std::vector<Ev>       evs;
	std::vector<std::pair<uint64_t, uint64_t>> rels; // F7: (label, value) written by this job (ran), once per label
	size_t                e = 0;
	for (uint32_t q = 0; q < num_dwords;) {
		const uint32_t h = ib[q], type = h >> 30u;
		uint32_t       len = 1;
		if (type == 3 || type == 0) { const uint32_t c = (h >> 16u) & 0x3fffu; len = c == 0x3fffu ? 1 : c + 2; }
		if (q + len > num_dwords) break;
		while (e < executed.size() && executed[e] < q) e++;
		const bool ran = e < executed.size() && executed[e] == q;
		if (type == 3) {
			const uint32_t  op = (h >> 8u) & 0xffu;
			const uint32_t* w  = ib + q;
			auto addr = [w](int lo, int hi) { return (static_cast<uint64_t>(w[lo]) & ~3ull) | (static_cast<uint64_t>(w[hi] & 0xffffu) << 32u); };
			uint64_t a = 0, v = 0;
			bool     wr = false;
			if (op == 0x49 && len >= 8 && (w[2] >> 29u) != 0) { a = addr(3, 4); v = w[5] | (static_cast<uint64_t>(w[6]) << 32u); wr = true; }
			else if (op == 0x47 && len >= 6 && (w[3] >> 29u) != 0) { a = addr(2, 3); v = w[4] | (static_cast<uint64_t>(w[5]) << 32u); wr = true; }
			else if (op == 0x37 && len >= 5 && (((w[1] >> 8u) & 0xfu) == 1 || ((w[1] >> 8u) & 0xfu) == 2 || ((w[1] >> 8u) & 0xfu) == 5)) { a = addr(2, 3); v = w[4] | (len >= 6 ? static_cast<uint64_t>(w[5]) << 32u : 0); wr = true; }
			else if ((op == 0x3c || op == 0x93) && len >= 4 && ((w[1] >> 4u) & 1u) != 0 && ran) waits.push_back(addr(2, 3));
			if (wr && ran && f7_on() && std::none_of(rels.begin(), rels.end(), [a](const auto& x) { return x.first == a; })) rels.emplace_back(a, v);
			if (wr && g_on() && a >= 0x100000000ull) {
				Ev x  = ev(ran ? kWrite : kDropped, a, kind, ring, q);
				x.value = v;
				x.ref   = seq;
				x.func  = static_cast<uint8_t>(op);
				evs.push_back(x);
			}
		}
		q += len;
	}
	Store&           s = st();
	std::unique_lock lk(s.m);
	if ((f2_on() || f3_on()) && !waits.empty()) {
		s.job_waits[{ring, seq}] = std::move(waits);
		if (s.job_waits.size() > 4096) s.job_waits.erase(s.job_waits.begin());
	}
	for (const auto& [a, v]: rels) { // F7: a release on another ring than the label's waiters
		const auto it = s.f7.find(a);
		if (it == s.f7.end() || it->second.ref != v || it->second.wring == ring) continue;
		Store::Cnt& c = it->second;
		c.rel++;
		c.rtid = static_cast<int>(syscall(SYS_gettid));
		pthread_getname_np(pthread_self(), c.rname, sizeof(c.rname));
		if (!c.synced) {
			c.synced = true;
			c.bal    = 1;
			c.ok     = 0;
		} else {
			c.bal++;
			c.ok = (c.bal == 0 || c.bal == 1) ? c.ok + 1 : 0;
		}
	}
	if (f5_on() && f3_on() && !safe.empty()) {
		s.job_safe[{ring, seq}] = std::move(safe);
		if (s.job_safe.size() > 4096) s.job_safe.erase(s.job_safe.begin());
	}
	if (s.r.size() != kEvN) s.r.assign(kEvN, Ev {});
	for (const Ev& x: evs) {
		s.r[s.total % kEvN] = x;
		s.total++;
		s.c[x.type]++;
	}
	static uint64_t last_line = 0;
	const uint64_t  now       = SoftCp::now_ns();
	if (g_on() && now - last_line > 30'000'000'000ull) {
		last_line = now;
		journal("ho430 (exp 0430): t %.1f s: waits seen %" PRIu64 ", writes registered %" PRIu64 ", writes DROPPED by the host %" PRIu64 "; F3 cross-queue labels %zu, presets %" PRIu64 ", refused %" PRIu64 ", not stale %" PRIu64
		        ", first seen (to F2) %" PRIu64 ", waits meeting a preset before its release %" PRIu64 "; F2 waited %" PRIu64 " (%.1f ms in all), refused as a cycle %" PRIu64 ", bound reached %" PRIu64 ", F4 fences %" PRIu64 ", F5 skipped %" PRIu64 "; unsatisfied waits dropped: GIVEN UP %" PRIu64 ", CYCLE %" PRIu64 "\n",
		        timing_now(), s.c[kWait], s.c[kWrite], s.c[kDropped], s.cross.size(), s.c[kF3Preset], s.c[kF3Refused], s.c[kF3NotStale], s.c[kF3First], s.c[kF3Met], s.c[kF2Waited], static_cast<double>(s.waited_ns) / 1e6,
		        s.c[kF2Cycle], s.c[kF2Bound], s.c[kF4Fence], s.c[kF5Skip], s.c[kGivenUp], s.c[kCycle]);
	}
	static uint64_t last_f5 = 0; // F5's line without G (the shared form too): the orders kept against the orders skipped
	if (!g_on() && (f3_on() || f7_on()) && now - last_f5 > 60'000'000'000ull) {
		last_f5 = now;
		journal("ho430 F5 (exp 0430): t %.1f s: F3 presets %" PRIu64 ", not stale %" PRIu64 ", refused %" PRIu64 "; F4 fences %" PRIu64 ", F2 waited %" PRIu64 ", F5 skipped %" PRIu64 " (precise %s), F6 kept %" PRIu64 " (keep %s), F6 kept waits not back in 1 s %" PRIu64 ", F6 labels %zu, not kept on a shared ring %" PRIu64 "; F7 labels %zu, held %" PRIu64 " (%.1f ms), bounds %" PRIu64 ", sensor (not held) %" PRIu64 ", same thread %" PRIu64 ", holds <1/<5/<20/<50/<250 ms/bound %" PRIu64 "/%" PRIu64 "/%" PRIu64 "/%" PRIu64 "/%" PRIu64 "/%" PRIu64 ", marks <0.1/<1/<5/<20 ms/later/none %" PRIu64 "/%" PRIu64 "/%" PRIu64 "/%" PRIu64 "/%" PRIu64 "/%" PRIu64 "; F8 observe points %" PRIu64 ", chains made due %" PRIu64 " (%.1f ms), gone within 2 ms %" PRIu64 ", bound %" PRIu64 ", could not look %" PRIu64 "; F7 holds with a title submit call running/begun during/neither %" PRIu64 "/%" PRIu64 "/%" PRIu64 "; F9 chains at a call's end %" PRIu64 ": flushed (a memory write) %" PRIu64 ", held %" PRIu64 "\n", timing_now(), s.c[kF3Preset], s.c[kF3NotStale], s.c[kF3Refused],
		        s.c[kF4Fence], s.c[kF2Waited], s.c[kF5Skip], f5_on() ? "on" : "off", s.c[kF6Kept], f6_on() ? "on" : "off", s.f6_long, s.f6_by_label.size(), s.f6_shared, s.f7.size(), s.f7_held, static_cast<double>(s.f7_ns) / 1e6, s.f7_bound, s.f7_would, s.f7_same,
		        s.f7_hist[0], s.f7_hist[1], s.f7_hist[2], s.f7_hist[3], s.f7_hist[4], s.f7_hist[5], s.f7_mark[0], s.f7_mark[1], s.f7_mark[2], s.f7_mark[3], s.f7_mark[4], s.f7_mark[5],
		        s.f8_calls, s.f8_chains, static_cast<double>(s.f8_ns) / 1e6, s.f8_gone, s.f8_bound, s.f8_busy, s.f7_cls[0], s.f7_cls[1], s.f7_cls[2], g_f9_ended.load(), g_f9_flushed.load(), g_f9_held.load());
	}
#ifndef HO430_SHARED
	static bool         at_done = false; // BC5_0430_G_AT: one dump in a clean run
	static const double g_at    = [] {
		const char* e = BC5_DIAG_ENV("BC5_0430_G_AT");
		return e != nullptr ? std::atof(e) : 0.0;
	}();
	if (g_on() && !at_done && g_at > 0 && timing_now() >= g_at) {
		at_done = true;
		lk.unlock();
		dump(90);
	}
#endif
}
inline void job_done(uint64_t seq, int ring, bool all) {
	if (!f2_on() && !f3_on()) return;
	Store&          s = st();
	std::lock_guard lk(s.m);
	if (all) {
		s.job_waits.clear();
		s.job_safe.clear();
	} else {
		s.job_waits.erase({ring, seq});
		s.job_safe.erase({ring, seq});
	}
}
inline void given_up(bool cycle, uint64_t label, const char* kind, int ring, uint32_t off) {
	if (g_on()) add(ev(cycle ? kCycle : kGivenUp, label, kind, ring, off));
}
// F8 at the first wait of an acb: submit the other threads' held chains first (ADR 0010's observe point).
// F8 v2 (after v1 froze h430K2 at 38.9 s: bc5-ring held g_chains_mu while submitting another thread's chain): bc5-ring
// never submits another thread's chain and never blocks on a lock. Every lock it takes here is a try_lock. It counts the
// other threads' held chains and back-dates their open time so the watchdog (bc5-chainwd, the known-good submitter)
// finds them due, wakes it, and polls, at most 2 ms (the hold bound itself), until none is held. Then the existing paths
// decide; F7 still catches what is left. Counted: observe points, chains made due, gone within the bound, bound reached.
inline uint32_t f8_held_count(bool make_due) { // -1u: could not look without blocking
	if (!g_chains_mu.try_lock()) return ~0u;
	uint32_t n = 0;
	bool     busy = false;
	for (ChainSlot* cs: g_chains) {
		if (cs == &g_chain_tl) continue;
		if (!cs->mu.try_lock()) {
			busy = true;
			continue;
		}
		if (!cs->c.segs.empty() && !cs->in_submit && cs->hold.empty()) {
			n++;
			if (make_due) cs->open_ns = 1; // due now for the watchdog (open_ns + the hold bound is past)
		}
		cs->mu.unlock();
	}
	g_chains_mu.unlock();
	return busy && n == 0 ? ~0u : n;
}
inline void f8_observe(const uint32_t* ib, uint32_t off) {
	static thread_local const uint32_t* last_ib  = nullptr;
	static thread_local uint32_t        last_off = 0;
	const bool                          fresh    = ib != last_ib || off <= last_off;
	last_ib  = ib;
	last_off = off;
	if (!fresh || g_chain_mode < 2) return;
	const uint64_t t0   = SoftCp::now_ns();
	const uint32_t due  = f8_held_count(true);
	bool           gone = false, bound = false;
	if (due != ~0u && due > 0) {
		chainwd_wake();
		for (;;) {
			const uint32_t left = f8_held_count(false);
			if (left == 0) { gone = true; break; }
			if (SoftCp::now_ns() - t0 >= 2'000'000ull) { bound = true; break; }
			std::this_thread::sleep_for(std::chrono::microseconds(20));
		}
	}
	Store&          s = st();
	std::lock_guard lk(s.m);
	s.f8_calls++;
	if (due == ~0u) s.f8_busy++;
	else s.f8_chains += due;
	if (gone) s.f8_gone++;
	if (bound) s.f8_bound++;
	s.f8_ns += SoftCp::now_ns() - t0;
}
// F7 at the first wait of a submission on a label: count it; hold a stale one until its release is registered.
inline void f7_wait(uint64_t label, uint64_t ref, int ring, const uint32_t* ib, uint32_t off, const char* kind) {
	static thread_local const uint32_t*  last_ib  = nullptr;
	static thread_local uint32_t         last_off = 0;
	static thread_local std::vector<uint64_t> seen;
	if (ib != last_ib || off <= last_off) seen.clear(); // a new submission (the same buffer may come again next frame)
	last_ib  = ib;
	last_off = off;
	if (std::find(seen.begin(), seen.end(), label) != seen.end()) return;
	seen.push_back(label);
	Store&   s    = st();
	uint64_t rel0 = 0;
	char     rname[16] {};
	{
		std::lock_guard lk(s.m);
		Store::Cnt&     c = s.f7[label];
		if (c.ref != ref || (c.wring != -100 && c.wring != ring)) { // a new reference, or waiters on two rings: start over
			c       = Store::Cnt {};
			c.ref   = ref;
			c.wring = ring;
			return;
		}
		c.wring = ring;
		if (!c.synced) return;
		if (c.bal >= 1 || c.ok < 32) {
			c.bal--;
			c.ok = (c.bal == 0 || c.bal == 1) ? c.ok + 1 : 0;
			return;
		}
		if (c.rtid == static_cast<int>(syscall(SYS_gettid))) { // the top's check: this thread submits the release later itself
			c.bal--;
			c.ok = 0;
			s.f7_same++;
			return;
		}
		if (f7_sensor()) { // count it, hold nothing: the waiter takes the next release (bal -1 until it comes), ok kept
			c.bal--;
			const uint64_t k = ++s.f7_would;
			if (k <= 256 || (k & 0x3ffu) == 0)
				journal("ho430 F7 sensor: %s on ring %d at %u: its wait on 0x%" PRIx64 " (== 0x%" PRIx64 ") came before its release, not held (%" PRIu64 " so far)\n", kind, ring, off, label, ref, k);
			return;
		}
		rel0 = c.rel; // stable 1:1 and no release since the last waiter: this one's release is still to come
		std::snprintf(rname, sizeof(rname), "%s", c.rname);
	}
	const uint64_t t0     = SoftCp::now_ns();
	const int      run0   = g_xq_in_submit.load();      // the title's submit calls already running when the acb was taken
	const uint64_t ent0   = g_xq_submit_entries.load(); // and begun so far (one beginning during the hold: the title called it after)
	bool           done   = false;
	uint64_t       mark_t = 0; // when the label first held a value other than ref (the title's mark, or F3's preset at the writer's submit)
	while (SoftCp::now_ns() - t0 < 250'000'000ull && (!g_dev || !g_dev->wedged())) {
		if (mark_t == 0 && *reinterpret_cast<const volatile uint64_t*>(label & ~7ull) != ref) mark_t = SoftCp::now_ns();
		{
			std::lock_guard lk(s.m);
			if (s.f7[label].rel != rel0) done = true;
		}
		if (done) break;
		std::this_thread::sleep_for(std::chrono::microseconds(50));
	}
	const uint64_t waited = SoftCp::now_ns() - t0;
	const uint64_t began  = g_xq_submit_entries.load() - ent0;
	const int      cls    = run0 > 0 ? 0 : began > 0 ? 1 : 2; // 0: a submit call was running; 1: one began during the hold; 2: neither
	uint64_t       n      = 0;
	{
		std::lock_guard lk(s.m);
		s.f7_cls[cls]++;
		Store::Cnt&     c = s.f7[label];
		if (done) {
			c.bal--;
			c.ok = (c.bal == 0 || c.bal == 1) ? c.ok + 1 : 0;
			n    = ++s.f7_held;
		} else {
			c.synced = false; // resync at the next release
			c.ok     = 0;
			n        = ++s.f7_bound;
		}
		s.f7_ns += waited;
		const double ms = static_cast<double>(waited) / 1e6;
		s.f7_hist[!done ? 5 : ms < 1 ? 0 : ms < 5 ? 1 : ms < 20 ? 2 : ms < 50 ? 3 : 4]++;
		const double mk = mark_t == 0 ? -1.0 : static_cast<double>(mark_t - t0) / 1e6;
		s.f7_mark[mk < 0 ? 5 : mk < 0.1 ? 0 : mk < 1 ? 1 : mk < 5 ? 2 : mk < 20 ? 3 : 4]++;
	}
	Ev x    = ev(done ? kF7Held : kF7Bound, label, kind, ring, off);
	x.value = waited;
	x.ref   = ref;
	add(x);
	if (!done || n <= 256 || (n & 0x3ffu) == 0)
	{
		char wname[16] {};
		pthread_getname_np(pthread_self(), wname, sizeof(wname));
		journal("ho430 F7: %s on ring %d at %u (thread %s): its wait on 0x%" PRIx64 " (== 0x%" PRIx64 ") came before its release; %s after %.2f ms; the label marked %s%.2f ms in; the last release came from thread %s; title submit calls running at the start %d, begun during the hold %" PRIu64 " (%" PRIu64 " %s)\n", kind, ring, off, wname, label, ref,
		        done ? "held until the release was submitted" : "BOUND REACHED, the label resyncs", static_cast<double>(waited) / 1e6, mark_t == 0 ? "never, " : "", mark_t == 0 ? 0.0 : static_cast<double>(mark_t - t0) / 1e6, rname, run0, began, n, done ? "held" : "bounds");
	}
}
// At a wait of a buffer about to be submitted (submit_split), before the host decides it.
inline void at_wait(const uint32_t* p, bool is64, uint64_t label, const char* kind, int ring, const uint32_t* ib, uint32_t num_dwords, uint32_t off) {
	if (!f2_on() && !g_on() && !f3_on() && !f7_on()) return;
	if (f8_on() && kind != nullptr && std::strncmp(kind, "acb", 3) == 0) f8_observe(ib, off); // F8 first: the title's earlier dcbs go first
	if (f7_on() && (p[1] & 7u) == 3u && kind != nullptr && std::strncmp(kind, "acb", 3) == 0) // F7 first: the rest sees the writer pending
		f7_wait(label, is64 ? (p[4] | (static_cast<uint64_t>(p[5]) << 32u)) : p[4], ring, ib, off, kind);
	const bool     sat   = wait_satisfied(p, is64);
	const uint64_t value = is64 ? *reinterpret_cast<const volatile uint64_t*>(label & ~7ull) : *reinterpret_cast<const volatile uint32_t*>(label & ~3ull);
	const uint64_t ref   = is64 ? (p[4] | (static_cast<uint64_t>(p[5]) << 32u)) : p[4];
	const uint32_t func  = p[1] & 7u;
	std::vector<std::pair<int, uint64_t>> others; // (ring, seq) of pending writes to this label on another ring
	uint32_t                              pend      = 0;
	bool                                  other_ref = false; // a pending write of exactly ref on another ring
	int                                   oring     = -100; // F6: that writer's ring
	{
		std::lock_guard lk(g_plw_mutex);
		for (const auto& w: g_plw) {
			if (w.label != label) continue;
			pend++;
			if (w.ring != ring && w.value == ref && w.is64 == is64) { other_ref = true; oring = w.ring; }
			if (w.ring != ring && std::find(others.begin(), others.end(), std::make_pair(w.ring, w.seq)) == others.end()) others.emplace_back(w.ring, w.seq);
		}
	}
	if (f3_on() && func == 3) { // F3: the cross-queue label set, in memory only
		bool            first = false;
		Store&          s     = st();
		std::lock_guard lk(s.m);
		auto            it = s.cross.find(label);
		if (it == s.cross.end() && other_ref) {
			Cross c;
			c.v     = ref;
			c.is64  = is64;
			c.wring = oring;
			it     = s.cross.emplace(label, c).first;
			first  = true;
		}
		if (it != s.cross.end() && value != it->second.v) {
			it->second.nonv      = value;
			it->second.have_nonv = true;
		}
		if (first && sat && !others.empty()) s.c[kF3First]++; // the writer was submitted before the label was known: F2 below
		// The top session's guard (2): a wait that meets a preset label before its release has landed. Waits kept for the GPU
		// and the host's CPU-side waits on the title's behalf both pass here; the title's own CPU reads of the label do not
		// reach the host and are not seen.
		const auto pa = s.preset_at.find(label);
		if (pa != s.preset_at.end()) {
			if (it != s.cross.end() && value == it->second.v) {
				s.preset_at.erase(pa); // the release has landed
			} else if (SoftCp::now_ns() - pa->second > 2'000'000'000ull) {
				s.preset_at.erase(pa);
			} else {
				s.c[kF3Met]++;
				static uint64_t n_m = 0;
				if (n_m++ < 128 || (n_m & 0x3ffu) == 0)
					journal("ho430 F3: %s on ring %d waits at %u on 0x%" PRIx64 " %.2f ms after its preset, before the release (value 0x%" PRIx64 ", reference 0x%" PRIx64 "; %" PRIu64 " so far)\n", kind, ring, off, label,
					        static_cast<double>(SoftCp::now_ns() - pa->second) / 1e6, value, ref, n_m);
			}
		}
	}
	if (g_on()) {
		Ev x    = ev(kWait, label, kind, ring, off);
		x.value = value;
		x.ref   = ref;
		x.func  = static_cast<uint8_t>(func);
		x.sat   = sat ? 1 : 0;
		x.pend  = static_cast<uint8_t>(std::min<uint32_t>(pend, 255));
		add(x);
	}
	if (!f2_on() || !sat || others.empty()) return;
	if (f5_on() && f3_on()) { // F5: a writer job whose stale case F3 excluded has released already; it needs no order
		std::vector<std::pair<int, uint64_t>> need;
		{
			Store&          s = st();
			std::lock_guard lk(s.m);
			for (const auto& o: others) {
				const auto it = s.job_safe.find(o);
				if (it == s.job_safe.end() || std::find(it->second.begin(), it->second.end(), label) == it->second.end()) need.push_back(o);
			}
		}
		if (need.empty()) {
			Ev x    = ev(kF5Skip, label, kind, ring, off);
			x.value = value;
			x.ref   = others.front().second;
			add(x);
			return;
		}
		others.swap(need);
	}
	// The cycle check: a writer job holding a kept GPU wait on a label this buffer writes cannot complete before this buffer runs.
	std::vector<uint64_t> mine;
	for (uint32_t q = 0; q < num_dwords;) {
		const uint32_t h = ib[q], type = h >> 30u;
		uint32_t       len = 1;
		if (type == 3 || type == 0) { const uint32_t c = (h >> 16u) & 0x3fffu; len = c == 0x3fffu ? 1 : c + 2; }
		if (q + len > num_dwords) break;
		const uint32_t op = (h >> 8u) & 0xffu;
		if (type == 3 && ((op == 0x49 && len >= 6) || (op == 0x37 && len >= 4) || (op == 0x47 && len >= 4))) {
			const int lo = op == 0x49 ? 3 : 2;
			mine.push_back((static_cast<uint64_t>(ib[q + lo]) & ~3ull) | (static_cast<uint64_t>(ib[q + lo + 1] & 0xffffu) << 32u));
		}
		q += len;
	}
	bool cycle = false;
	{
		Store&          s = st();
		std::lock_guard lk(s.m);
		for (const auto& o: others) {
			const auto it = s.job_waits.find(o);
			if (it == s.job_waits.end()) continue;
			for (const uint64_t l: it->second)
				if (std::find(mine.begin(), mine.end(), l) != mine.end()) cycle = true;
		}
	}
	if (cycle) {
		Ev x    = ev(kF2Cycle, label, kind, ring, off);
		x.value = value;
		x.ref   = others.front().second;
		add(x);
		static std::atomic<uint64_t> n_c {0};
		const uint64_t               k = n_c++;
		if (k < 64 || (k & 0xfffu) == 0) journal("ho430 F2: %s wait at %u on 0x%" PRIx64 " (value 0x%" PRIx64 ", satisfied) has a pending write from job %" PRIu64 " on ring %d, which waits on a label this buffer writes: a cycle, F2 refused (%" PRIu64 " so far)\n", kind, off, label, value, others.front().second, others.front().first, k + 1);
		return;
	}
	if (f4_on()) { // F4: the same order through the kernel's scheduler: this buffer's next submission depends on the writer jobs
		for (const auto& o: others) bc5::direct::Device::add_next_submit_dependency(o.first, o.second);
		Ev x    = ev(kF4Fence, label, kind, ring, off);
		x.value = value;
		x.ref   = others.front().second;
		add(x);
		static std::atomic<uint64_t> n_f {0};
		const uint64_t               k = n_f++;
		if (k < 64 || (k & 0x3fffu) == 0)
			journal("ho430 F4: %s wait at %u on 0x%" PRIx64 " was satisfied (value 0x%" PRIx64 ") with a pending write from job %" PRIu64 " on ring %d (%zu such jobs): the submission depends on it (%" PRIu64 " so far)\n", kind, off, label, value,
			        others.front().second, others.front().first, others.size(), k + 1);
		return;
	}
	const uint64_t t0 = SoftCp::now_ns();
	bool           done = false;
	while (SoftCp::now_ns() - t0 < 250'000'000ull && (!g_dev || !g_dev->wedged())) {
		bool left = false;
		{
			std::lock_guard lk(g_plw_mutex);
			for (const auto& w: g_plw)
				if (w.label == label && std::find(others.begin(), others.end(), std::make_pair(w.ring, w.seq)) != others.end()) left = true;
		}
		if (!left) { done = true; break; }
		std::this_thread::sleep_for(std::chrono::microseconds(50));
	}
	const uint64_t waited = SoftCp::now_ns() - t0;
	Ev             x      = ev(done ? kF2Waited : kF2Bound, label, kind, ring, off);
	x.value               = value;
	x.ref                 = others.front().second;
	add(x);
	{
		Store&          s = st();
		std::lock_guard lk(s.m);
		s.waited_ns += waited;
	}
	static std::atomic<uint64_t> n_w {0};
	const uint64_t               k = n_w++;
	if (!done || k < 256 || (k & 0x3ffu) == 0)
		journal("ho430 F2: %s wait at %u on 0x%" PRIx64 " was satisfied (value 0x%" PRIx64 ") with a pending write from job %" PRIu64 " on ring %d (%zu such jobs): %s after %.2f ms (%" PRIu64 " so far)\n", kind, off, label, value,
		        others.front().second, others.front().first, others.size(), done ? "waited for it" : "BOUND REACHED, decided as before", static_cast<double>(waited) / 1e6, k + 1);
}
// F6 at a wait of a buffer about to be submitted (submit_split's keep test): true keeps a satisfied wait for the GPU.
inline bool keep_cross(const uint32_t* p, bool is64, uint64_t label, const char* kind, int ring, uint32_t off) {
	if (!f6_on() || !f3_on() || (p[1] & 7u) != 3u || !wait_satisfied(p, is64)) return false;
	if (kind == nullptr || std::strncmp(kind, "acb", 3) != 0) return false; // compute-ring waiters only (the top, 13:20): the host's own
	                                                                       // prepare can wait behind a kept gfx wait (h430Q1, 1.07 s)
	const uint64_t ref = is64 ? (p[4] | (static_cast<uint64_t>(p[5]) << 32u)) : p[4];
	{
		Store&          s = st();
		std::lock_guard lk(s.m);
		const auto      it = s.cross.find(label);
		const bool      known = it != s.cross.end() && it->second.v == ref && it->second.is64 == is64;
		// F6b (h430C6, 16:11: the same drop on 0x12004b77c8, a slot of the title's label family that F3 had never learned):
		// with BC5_DIRECT_XQ_KEEP_ALL / BC5_0430_F6B every satisfied == wait of an acb is a candidate, learned or not
		if (!known && !f6b_on()) return false;
		if (it != s.cross.end() && it->second.wring == ring) return false; // the writer runs on this ring after the wait: the GPU would deadlock
	}
	{
		std::lock_guard lk(g_plw_mutex);
		for (const auto& w: g_plw)
			if (w.label == label) return false; // a writer in flight: F2/F4/F5 decide
	}
	{ // the top's guard (2): only when the waiter's guest queue has its host ring to itself (way 2's queue -> ring map); a kept
	  // wait must not block another guest queue's writer that shares the ring (the console runs those queues apart)
		int sharing = 0;
		{
			std::lock_guard lq(g_w428_mu);
			for (const auto& [q, e]: g_w428_qring)
				if (e.n > 0 && e.ring == ring) sharing++;
		}
		if (sharing != 1) {
			Store&          s = st();
			std::lock_guard lk(s.m);
			s.f6_shared++;
			return false;
		}
	}
	Ev x    = ev(kF6Kept, label, kind, ring, off);
	x.value = ref;
	add(x);
	{
		Store&          s = st();
		std::lock_guard lk(s.m);
		s.f6_kept[label] = Store::Kept {SoftCp::now_ns(), ref, is64, ring};
		s.f6_by_label[label]++;
	}
	static std::atomic<uint64_t> n_k {0};
	const uint64_t               k = n_k++;
	if (k < 64 || (k & 0x3fffu) == 0) journal("ho430 F6: %s on ring %d keeps its satisfied wait at %u on 0x%" PRIx64 " (== 0x%" PRIx64 ") for the GPU: no writer in flight (%" PRIu64 " so far)\n", kind, ring, off, label, ref, k + 1);
	return true;
}
// F3 at the submit of a buffer (submit_now, before the device call): for each release of a cross-queue label in it, the
// stale case (the label already holds the released value) gets the label set to another value first. ib is the buffer as
// submitted (no rebuilt copy: the caller passes it only when the host did not rebuild it), drops the host's drop offsets.
inline void f3_before_submit(const uint32_t* ib, uint32_t num_dwords, const std::vector<uint32_t>& drops, int ring, const char* kind, const std::vector<bc5::direct::Mapping>& maps) {
	if (!f3_on()) return;
	t_f5_ib = ib; // F5: this buffer's excluded labels, for job_submitted after the device call
	t_f5_n  = num_dwords;
	t_f5_safe.clear();
	{
		Store&          s = st();
		std::lock_guard lk(s.m);
		if (s.cross.empty()) return;
	}
	std::vector<std::pair<uint32_t, uint32_t>> conds; // COND_EXEC ranges [from, to)
	std::vector<uint64_t>                      waited; // labels this buffer waits on before the position
	std::vector<uint64_t>                      done;
	for (uint32_t q = 0; q < num_dwords;) {
		const uint32_t h = ib[q], type = h >> 30u;
		uint32_t       len = 1;
		if (type == 3 || type == 0) { const uint32_t c = (h >> 16u) & 0x3fffu; len = c == 0x3fffu ? 1 : c + 2; }
		if (q + len > num_dwords) break;
		if (type == 3) {
			const uint32_t  op = (h >> 8u) & 0xffu;
			const uint32_t* w  = ib + q;
			auto addr = [w](int lo, int hi) { return (static_cast<uint64_t>(w[lo]) & ~3ull) | (static_cast<uint64_t>(w[hi] & 0xffffu) << 32u); };
			if (op == 0x22 && len >= 5) conds.emplace_back(q + len, q + len + (w[4] & 0x3fffu));
			if ((op == 0x3c || op == 0x93) && len >= 4 && ((w[1] >> 4u) & 1u) != 0) waited.push_back(addr(2, 3));
			uint64_t a = 0, v = 0;
			bool     wr = false, w64 = false;
			if (op == 0x49 && len >= 8 && ((w[2] >> 29u) == 1 || (w[2] >> 29u) == 2)) { a = addr(3, 4); w64 = (w[2] >> 29u) == 2; v = w64 ? (w[5] | (static_cast<uint64_t>(w[6]) << 32u)) : w[5]; wr = true; }
			else if (op == 0x37 && len >= 5 && (((w[1] >> 8u) & 0xfu) == 1 || ((w[1] >> 8u) & 0xfu) == 2 || ((w[1] >> 8u) & 0xfu) == 5)) { a = addr(2, 3); w64 = len >= 6; v = w64 ? (w[4] | (static_cast<uint64_t>(w[5]) << 32u)) : w[4]; wr = true; }
			if (wr && std::find(done.begin(), done.end(), a) == done.end()) {
				Cross c;
				bool  known = false;
				{
					Store&          s = st();
					std::lock_guard lk(s.m);
					const auto      it = s.cross.find(a);
					if (it != s.cross.end()) { c = it->second; known = true; }
				}
				if (known && c.v == v && c.is64 == w64) {
					done.push_back(a);
					const char* why = nullptr;
					if (std::find(drops.begin(), drops.end(), q) != drops.end()) why = "the host drops the release";
					else if (std::any_of(conds.begin(), conds.end(), [q](const auto& r) { return q >= r.first && q < r.second; })) why = "the release is inside a COND_EXEC range";
					else if (std::find(waited.begin(), waited.end(), a) != waited.end()) why = "this buffer waits on the label itself";
					else if (!covered_sorted(maps, a, w64 ? 8 : 4)) why = "the label is not mapped";
					else {
						{ // the top session's guard (1): no job submitted and not completed, on any ring, still writes the label ...
							std::lock_guard lk(g_plw_mutex);
							for (const auto& pw: g_plw)
								if (pw.label == a) why = "a job in flight still writes the label (F2 stays the fallback)";
						}
						if (why == nullptr) { // ... or reads it through a kept wait
							Store&          s = st();
							std::lock_guard lk(s.m);
							for (const auto& [job, labels]: s.job_waits)
								if (std::find(labels.begin(), labels.end(), a) != labels.end()) why = "a job in flight holds a kept wait on the label (F2 stays the fallback)";
						}
					}
					const uint64_t now = w64 ? *reinterpret_cast<const volatile uint64_t*>(a & ~7ull) : *reinterpret_cast<const volatile uint32_t*>(a & ~3ull);
					if (why == nullptr && now != v) {
						add(ev(kF3NotStale, a, kind, ring, q));
						t_f5_safe.push_back(a); // F5: not stale, no other writer or kept wait in flight
					} else if (why != nullptr) {
						Ev x    = ev(kF3Refused, a, kind, ring, q);
						x.value = now;
						add(x);
						static std::atomic<uint64_t> n_r {0};
						const uint64_t               k = n_r++;
						if (k < 64 || (k & 0x3ffu) == 0) journal("ho430 F3: %s release of 0x%" PRIx64 " (value 0x%" PRIx64 ") at %u, label now 0x%" PRIx64 ": no preset, %s (%" PRIu64 " so far)\n", kind, a, v, q, now, why, k + 1);
					} else {
						const uint64_t set = c.have_nonv ? c.nonv : (v ^ 1ull);
						if (w64) *reinterpret_cast<volatile uint64_t*>(a & ~7ull) = set;
						else *reinterpret_cast<volatile uint32_t*>(a & ~3ull) = static_cast<uint32_t>(set);
						Ev x    = ev(kF3Preset, a, kind, ring, q);
						x.value = set;
						x.ref   = v;
						add(x);
						t_f5_safe.push_back(a); // F5: preset, so only this job's release brings the value back
						{
							Store&          s = st();
							std::lock_guard lk(s.m);
							s.preset_at[a] = SoftCp::now_ns();
						}
						static std::atomic<uint64_t> n_p {0};
						const uint64_t               k = n_p++;
						if (k < 256 || (k & 0x3ffu) == 0) journal("ho430 F3: %s on ring %d releases 0x%" PRIx64 " with 0x%" PRIx64 " at %u while it already holds that value: set to 0x%" PRIx64 " first (%" PRIu64 " so far)\n", kind, ring, a, v, q, set, k + 1);
					}
				}
			}
		}
		q += len;
	}
}
inline void dump(int k) {
	if (!g_on()) return;
	std::vector<Ev> all;
	uint64_t        c[kTypes] {};
	{
		Store&          s = st();
		std::lock_guard lk(s.m);
		if (s.r.size() == kEvN)
			for (uint64_t i = s.total > kEvN ? s.total - kEvN : 0; i < s.total; i++) all.push_back(s.r[i % kEvN]);
		std::memcpy(c, s.c, sizeof(c));
	}
	const std::string dir = g_dump_dir.empty() ? std::string(std::getenv("HOME") ? std::getenv("HOME") : ".") + "/bc5-work" : g_dump_dir;
	char              name[640];
	std::snprintf(name, sizeof(name), "%s/g0430-%d.txt", dir.c_str(), k);
	FILE* f = std::fopen(name, "w");
	if (f == nullptr) return;
	static const char* const tn[kTypes] = {"-", "wait", "write", "DROPPED-WRITE", "F2-waited", "F2-cycle", "F2-bound", "GIVEN-UP", "CYCLE", "F3-preset", "F3-refused", "F3-first-seen", "F3-not-stale", "F3-wait-met-preset", "F4-fence", "F5-skipped", "F6-kept", "F7-held", "F7-bound"};
	std::fprintf(f, "g0430 %d at t %.3f s: the last %zu label events, oldest first; counts: waits %" PRIu64 " writes %" PRIu64 " dropped writes %" PRIu64 " F2 waited %" PRIu64 " cycle %" PRIu64 " bound %" PRIu64 " given up %" PRIu64 " cycle-broken %" PRIu64 "\n", k,
	             timing_now(), all.size(), c[1], c[2], c[3], c[4], c[5], c[6], c[7], c[8]);
	std::fprintf(f, "columns: t_s type label kind ring about#n offset | wait: value ref func satisfied pending | write: value job_seq op\n");
	for (const Ev& e: all) {
		std::fprintf(f, "%.6f %s 0x%" PRIx64 " %s %d #%" PRIu64 " %u", static_cast<double>(e.t_ns) / 1e9, e.type < kTypes ? tn[e.type] : "?", e.label, e.kind, e.ring, e.n, e.off);
		if (e.type == kWait) std::fprintf(f, " | value 0x%" PRIx64 " ref 0x%" PRIx64 " func %u %s pending %u\n", e.value, e.ref, e.func, e.sat != 0 ? "SATISFIED" : "unsatisfied", e.pend);
		else std::fprintf(f, " | value 0x%" PRIx64 " job %" PRIu64 " op %02x\n", e.value, e.ref, e.func);
	}
	std::fflush(f);
	fsync(fileno(f));
	std::fclose(f);
}
} // namespace ho430

