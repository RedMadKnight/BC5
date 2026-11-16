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
namespace ho430 {
inline bool on_env(const char* name) {
	const char* e = BC5_DIAG_ENV(name);
	return e == nullptr || !(e[0] == '0' && e[1] == 0);
}
inline bool f2_on() {
	static const bool v = on_env("BC5_0430_F2");
	return v;
}
inline bool g_on() {
	static const bool v = on_env("BC5_0430_G");
	return v;
}
inline bool f3_on() {
	static const bool v = on_env("BC5_0430_F3");
	return v;
}
enum : uint8_t { kWait = 1, kWrite = 2, kDropped = 3, kF2Waited = 4, kF2Cycle = 5, kF2Bound = 6, kGivenUp = 7, kCycle = 8, kF3Preset = 9, kF3Refused = 10, kF3First = 11, kF3NotStale = 12 };
constexpr uint32_t kTypes = 16;
struct Cross {
	uint64_t v         = 0; // the released value the waits wait for (== v)
	uint64_t nonv      = 0; // the last other value a wait saw on the label
	bool     is64      = false;
	bool     have_nonv = false;
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
	uint64_t                                   c[kTypes] {};
	uint64_t                                   waited_ns = 0;
};
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
// One pass over a submitted job: its kept waits (for F2's cycle check), its registered writes and the writes the filter
// dropped (G). executed: the offsets the filter kept, in order.
inline void job_submitted(const uint32_t* ib, uint32_t num_dwords, const std::vector<uint32_t>& executed, uint64_t seq, int ring, const char* kind) {
	if (!f2_on() && !g_on() && !f3_on()) return;
	std::vector<uint64_t> waits;
	std::vector<Ev>       evs;
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
		        ", first seen (to F2) %" PRIu64 "; F2 waited %" PRIu64 " (%.1f ms in all), refused as a cycle %" PRIu64 ", bound reached %" PRIu64 "; unsatisfied waits dropped: GIVEN UP %" PRIu64 ", CYCLE %" PRIu64 "\n",
		        timing_now(), s.c[kWait], s.c[kWrite], s.c[kDropped], s.cross.size(), s.c[kF3Preset], s.c[kF3Refused], s.c[kF3NotStale], s.c[kF3First], s.c[kF2Waited], static_cast<double>(s.waited_ns) / 1e6,
		        s.c[kF2Cycle], s.c[kF2Bound], s.c[kGivenUp], s.c[kCycle]);
	}
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
}
inline void job_done(uint64_t seq, int ring, bool all) {
	if (!f2_on() && !f3_on()) return;
	Store&          s = st();
	std::lock_guard lk(s.m);
	if (all) s.job_waits.clear();
	else s.job_waits.erase({ring, seq});
}
inline void given_up(bool cycle, uint64_t label, const char* kind, int ring, uint32_t off) {
	if (g_on()) add(ev(cycle ? kCycle : kGivenUp, label, kind, ring, off));
}
// At a wait of a buffer about to be submitted (submit_split), before the host decides it.
inline void at_wait(const uint32_t* p, bool is64, uint64_t label, const char* kind, int ring, const uint32_t* ib, uint32_t num_dwords, uint32_t off) {
	if (!f2_on() && !g_on() && !f3_on()) return;
	const bool     sat   = wait_satisfied(p, is64);
	const uint64_t value = is64 ? *reinterpret_cast<const volatile uint64_t*>(label & ~7ull) : *reinterpret_cast<const volatile uint32_t*>(label & ~3ull);
	const uint64_t ref   = is64 ? (p[4] | (static_cast<uint64_t>(p[5]) << 32u)) : p[4];
	const uint32_t func  = p[1] & 7u;
	std::vector<std::pair<int, uint64_t>> others; // (ring, seq) of pending writes to this label on another ring
	uint32_t                              pend      = 0;
	bool                                  other_ref = false; // a pending write of exactly ref on another ring
	{
		std::lock_guard lk(g_plw_mutex);
		for (const auto& w: g_plw) {
			if (w.label != label) continue;
			pend++;
			if (w.ring != ring && w.value == ref && w.is64 == is64) other_ref = true;
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
			c.v    = ref;
			c.is64 = is64;
			it     = s.cross.emplace(label, c).first;
			first  = true;
		}
		if (it != s.cross.end() && value != it->second.v) {
			it->second.nonv      = value;
			it->second.have_nonv = true;
		}
		if (first && sat && !others.empty()) s.c[kF3First]++; // the writer was submitted before the label was known: F2 below
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
// F3 at the submit of a buffer (submit_now, before the device call): for each release of a cross-queue label in it, the
// stale case (the label already holds the released value) gets the label set to another value first. ib is the buffer as
// submitted (no rebuilt copy: the caller passes it only when the host did not rebuild it), drops the host's drop offsets.
inline void f3_before_submit(const uint32_t* ib, uint32_t num_dwords, const std::vector<uint32_t>& drops, int ring, const char* kind, const std::vector<bc5::direct::Mapping>& maps) {
	if (!f3_on()) return;
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
						Store&          s = st();
						std::lock_guard lk(s.m);
						for (const auto& [job, labels]: s.job_waits)
							if (job.first != ring && std::find(labels.begin(), labels.end(), a) != labels.end()) why = "a job in flight on another ring holds a kept wait on it";
					}
					const uint64_t now = w64 ? *reinterpret_cast<const volatile uint64_t*>(a & ~7ull) : *reinterpret_cast<const volatile uint32_t*>(a & ~3ull);
					if (why == nullptr && now != v) {
						add(ev(kF3NotStale, a, kind, ring, q));
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
	static const char* const tn[kTypes] = {"-", "wait", "write", "DROPPED-WRITE", "F2-waited", "F2-cycle", "F2-bound", "GIVEN-UP", "CYCLE", "F3-preset", "F3-refused", "F3-first-seen", "F3-not-stale", "?", "?", "?"};
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

