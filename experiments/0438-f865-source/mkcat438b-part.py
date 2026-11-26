
# ---- c438, part 2 (the top session's GO of 2026-11-20): what bc5-ring does with its time ---------------------------
# Records only, normal build only. bc5-ring's time is split into exclusive kinds (a scope pauses the kind around it):
# idle sleep, queue scan (outside Direct::submit), Direct::submit's own work, F10's look, F16's wait, F18's wait, the
# 24-job back-pressure, exp 0436's ring lock, the device mutex, the backend call (prepare + CS ioctl), an acb's CPU wait,
# a wait for the GPU to be idle (w428 ring move, wait_jobs). Recorded: each slice's time inside Direct::submit by kind;
# each look gap of 20 ms or more by kind (what bc5-ring did between two looks at that queue); at a give-up, bc5-ring's
# kind now and the time since the writer queue's last look by kind. The queue views are refreshed at every look.

# 0. the kinds' enum before QueueView (which keeps a total per kind)
rep('''namespace c438 {
struct QueueView {''', '''namespace c438 {
enum : int { kIdle, kScan, kSubmit, kF10, kF16, kF18, kBackPressure, kRingLock, kDevMutex, kBackend, kAcbCpuWait, kWaitIdle, kN }; // exp 0438 (c438 part 2)
struct QueueView {''')

# 1. the kinds, next to the c438 namespace
rep('''inline int bucket(uint64_t ns) {
	return ns < 1'000'000ull ? 0 : ns < 5'000'000ull ? 1 : ns < 20'000'000ull ? 2 : ns < 100'000'000ull ? 3 : 4;
}''', '''inline int bucket(uint64_t ns) {
	return ns < 1'000'000ull ? 0 : ns < 5'000'000ull ? 1 : ns < 20'000'000ull ? 2 : ns < 100'000'000ull ? 3 : 4;
}
// part 2: bc5-ring's exclusive time by kind
inline const char* const kName[kN] = {"idle", "scan", "submit", "F10", "F16", "F18", "back-pressure", "ring-lock", "dev-mutex", "backend+ioctl", "acb-cpu-wait", "wait-idle"};
inline uint64_t now() {
	return static_cast<uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now().time_since_epoch()).count());
}
inline std::atomic<uint64_t>  g_ns[kN] = {};
inline std::atomic<int>       g_cur {kScan};
inline std::atomic<uint64_t>  g_cur_since {0};
inline thread_local bool      t_ring = false;
inline thread_local int       t_kind = kScan;
inline thread_local uint64_t  t_mark = 0;
inline void flip(int k) {
	if (!t_ring) return;
	const uint64_t n = now();
	if (t_mark != 0) g_ns[t_kind] += n - t_mark;
	t_mark = n;
	t_kind = k;
	g_cur.store(k);
	g_cur_since.store(n);
}
struct Scope {
	int  prev = kScan;
	bool on   = false;
	explicit Scope(int k): on(t_ring) {
		if (!on) return;
		prev = t_kind;
		flip(k);
	}
	~Scope() {
		if (on) flip(prev);
	}
};
inline void snap(uint64_t* out) { // the totals now, the running kind included
	for (int k = 0; k < kN; k++) out[k] = g_ns[k].load();
	const uint64_t s = g_cur_since.load();
	const int      c = g_cur.load();
	if (s != 0) out[c] += now() - s;
}
inline void fmt(char* b, size_t cap, const uint64_t* a, const uint64_t* z) { // the kinds of z - a, in ms, the non-zero ones
	int w = 0;
	b[0]  = 0;
	for (int k = 0; k < kN && w < static_cast<int>(cap) - 40; k++) {
		const uint64_t d = z[k] - a[k];
		if (d >= 50'000ull) w += std::snprintf(b + w, cap - static_cast<size_t>(w), "%s%s %.1f", w ? ", " : "", kName[k], static_cast<double>(d) / 1e6);
	}
}
inline std::atomic<uint64_t> g_slice_hist[5] = {}, g_slice_ns[kN] = {}, g_slices {0}, g_slice_max {0}, g_slice_logged {0};
inline std::atomic<uint64_t> g_gap_n {0}, g_gap_ns[kN] = {}, g_gap_logged {0};''')

# 2. QueueView: the time totals at the queue's last look
rep('''	uint64_t deferred_since = 0, label = 0, value = 0, head_seen = 0, poll = 0;
	bool     unready = false;
};''', '''	uint64_t deferred_since = 0, label = 0, value = 0, head_seen = 0, poll = 0;
	bool     unready = false;
	uint64_t at_look[kN] = {}; // part 2: bc5-ring's time totals at this queue's last look
};''')

# 3. bc5-ring is the thread that counts
rep('''	Direct::set_source(1);
''', '''	Direct::set_source(1);
#ifndef BC5_LEAN
	Direct::c438::t_ring = true; // exp 0438 (c438 part 2)
	Direct::c438::flip(Direct::c438::kScan);
#endif
''', 1)

# 4. per look: the gap's kinds (a gap of 20 ms or more), and the view refreshed at every look
rep('''				const uint64_t cn = now_ns(), gap = s.c438_poll == 0 ? 0 : cn - s.c438_poll;
				s.c438_poll = cn;''', '''				const uint64_t cn = now_ns(), gap = s.c438_poll == 0 ? 0 : cn - s.c438_poll;
				s.c438_poll = cn;
				{ // part 2: what bc5-ring did since its last look at this queue; the view refreshed
					uint64_t z[Direct::c438::kN];
					Direct::c438::snap(z);
					std::lock_guard cl(Direct::c438::mu());
					auto&           v  = Direct::c438::views();
					const size_t    qi = static_cast<size_t>(&s - states.data());
					if (v.size() <= qi) v.resize(qi + 1);
					auto& e = v[qi];
					if (gap >= 20'000'000ull && e.poll != 0) {
						Direct::c438::g_gap_n++;
						for (int k = 0; k < Direct::c438::kN; k++) Direct::c438::g_gap_ns[k] += z[k] - e.at_look[k];
						const uint64_t lg = Direct::c438::g_gap_logged++;
						if (lg < 200 || (lg & 0xffu) == 0) {
							char b[600];
							Direct::c438::fmt(b, sizeof(b), e.at_look, z);
							Direct::journal("c438 (exp 0438): queue %u/%u/%u/0x%x: look gap %.3f ms, bc5-ring was: %s (ms; %" PRIu64 " such gaps so far)\\n", q.a, q.b, q.c, q.d, static_cast<double>(gap) / 1e6, b, lg + 1);
						}
					}
					for (int k = 0; k < Direct::c438::kN; k++) e.at_look[k] = z[k];
					e.a       = q.a;
					e.b       = q.b;
					e.c       = q.c;
					e.d       = q.d;
					e.poll    = cn;
					e.pending = (w + n - r) % n;
					if (e.pending == 0) e.unready = false;
				}''')

# 5. the slice's time inside Direct::submit, by kind
rep('''			Direct::chain_begin(); // ADR 0010: the slice's buffers as one submission
			if (w_take > r) {
				Direct::submit(ring + r, w_take - r, "ring");
			} else {
				Direct::submit(ring + r, n - r, "ring");
				if (w_take != 0) Direct::submit(ring, w_take, "ring");
			}
			Direct::chain_end();''', '''#ifndef BC5_LEAN
			uint64_t c438_a[Direct::c438::kN];
			Direct::c438::snap(c438_a);
#endif
			Direct::chain_begin(); // ADR 0010: the slice's buffers as one submission
			if (w_take > r) {
				Direct::submit(ring + r, w_take - r, "ring");
			} else {
				Direct::submit(ring + r, n - r, "ring");
				if (w_take != 0) Direct::submit(ring, w_take, "ring");
			}
			Direct::chain_end();
#ifndef BC5_LEAN
			{ // exp 0438 (c438 part 2): this slice's time inside Direct::submit and chain_end, by kind
				uint64_t z[Direct::c438::kN], tot = 0;
				Direct::c438::snap(z);
				for (int k = 0; k < Direct::c438::kN; k++) {
					Direct::c438::g_slice_ns[k] += z[k] - c438_a[k];
					tot += z[k] - c438_a[k];
				}
				Direct::c438::g_slices++;
				Direct::c438::g_slice_hist[Direct::c438::bucket(tot)]++;
				Direct::c438::maxed(Direct::c438::g_slice_max, tot);
				if (tot >= 20'000'000ull) {
					const uint64_t lg = Direct::c438::g_slice_logged++;
					if (lg < 200 || (lg & 0xffu) == 0) {
						char b[600];
						Direct::c438::fmt(b, sizeof(b), c438_a, z);
						Direct::journal("c438 (exp 0438): queue %u/%u/%u/0x%x slice of %u dwords: %.3f ms inside submit: %s (ms; %" PRIu64 " such slices so far)\\n", q.a, q.b, q.c, q.d, take, static_cast<double>(tot) / 1e6, b, lg + 1);
					}
				}
			}
#endif''')

# 6. the kinds' scopes
rep('''static void submit(const uint32_t* ib, uint32_t num_dwords, const char* kind) {
	mem_line_start(); // experiment 0401 series e3''', '''static void submit(const uint32_t* ib, uint32_t num_dwords, const char* kind) {
#ifndef BC5_LEAN
	const c438::Scope c438_sc(c438::kSubmit); // exp 0438 (c438 part 2)
#endif
	mem_line_start(); // experiment 0401 series e3''')
rep('''inline void f10_observe(uint64_t label) {
	if (g_chain_mode < 2) return;''', '''inline void f10_observe(uint64_t label) {
	if (g_chain_mode < 2) return;
#ifndef BC5_LEAN
	const c438::Scope c438_sc(c438::kF10); // exp 0438 (c438 part 2); F16 and F18 flip it below
#endif''')
rep('''	// F16: the writers still in flight at the bound: wait for their submit_now to return.
''', '''	// F16: the writers still in flight at the bound: wait for their submit_now to return.
#ifndef BC5_LEAN
	c438::flip(c438::kF16); // exp 0438 (c438 part 2)
#endif
''')
rep('''	// F18: a bound still standing.
''', '''	// F18: a bound still standing.
#ifndef BC5_LEAN
	c438::flip(c438::kF18); // exp 0438 (c438 part 2)
#endif
''')
rep('''		const uint64_t t_cap = SoftCp::now_ns();
		while (g_cq_fences.load() >= max_in_flight || g_recovering.load()) std::this_thread::sleep_for(std::chrono::microseconds(50));''', '''		const uint64_t t_cap = SoftCp::now_ns();
#ifndef BC5_LEAN
		const c438::Scope c438_bp(c438::kBackPressure); // exp 0438 (c438 part 2)
#endif
		while (g_cq_fences.load() >= max_in_flight || g_recovering.load()) std::this_thread::sleep_for(std::chrono::microseconds(50));''')
rep('''	std::unique_lock<std::mutex> su_ring;
	if (su) su_ring = std::unique_lock<std::mutex>(g_su436_ring_mu[qring == bc5::direct::kGfxRing ? bc5::direct::kComputeRings : qring]);
	std::unique_lock<std::mutex> lock(g_dev_mutex);''', '''	std::unique_lock<std::mutex> su_ring;
#ifndef BC5_LEAN
	const int c438_prev = c438::t_kind; // exp 0438 (c438 part 2): the ring lock, then the device mutex, then back
	c438::flip(c438::kRingLock);
#endif
	if (su) su_ring = std::unique_lock<std::mutex>(g_su436_ring_mu[qring == bc5::direct::kGfxRing ? bc5::direct::kComputeRings : qring]);
#ifndef BC5_LEAN
	c438::flip(c438::kDevMutex);
#endif
	std::unique_lock<std::mutex> lock(g_dev_mutex);
#ifndef BC5_LEAN
	c438::flip(c438_prev);
#endif''')
rep('''		r = g_dev->submit(std::span<const uint32_t>(sub_ib, sub_n), opt, 2'000'000'000ull, true, qring, unlock_dev);
		if (!lock.owns_lock()) lock.lock();''', '''		{
#ifndef BC5_LEAN
			const c438::Scope c438_be(c438::kBackend); // exp 0438 (c438 part 2)
#endif
			r = g_dev->submit(std::span<const uint32_t>(sub_ib, sub_n), opt, 2'000'000'000ull, true, qring, unlock_dev);
		}
		{
#ifndef BC5_LEAN
			const c438::Scope c438_dm(c438::kDevMutex);
#endif
			if (!lock.owns_lock()) lock.lock();
		}''')
rep('''					if (!broken && (!g_dev || !g_dev->wedged())) {''', '''					if (!broken && (!g_dev || !g_dev->wedged())) {
#ifndef BC5_LEAN
						const c438::Scope c438_cw(c438::kAcbCpuWait); // exp 0438 (c438 part 2): bc5-ring only counts
#endif''')
rep('''		const bool idle = !g_dev || g_dev->wait_idle(2'000'000'000ull);''', '''#ifndef BC5_LEAN
		const c438::Scope c438_wi(c438::kWaitIdle); // exp 0438 (c438 part 2)
#endif
		const bool idle = !g_dev || g_dev->wait_idle(2'000'000'000ull);''')
rep('''	g_dev->wait_idle(2'000'000'000ull);
''', '''#ifndef BC5_LEAN
	const c438::Scope c438_wi(c438::kWaitIdle); // exp 0438 (c438 part 2)
#endif
	g_dev->wait_idle(2'000'000'000ull);
''')
rep('''		std::this_thread::sleep_for(std::chrono::microseconds(idle_ticks > 1000 ? bc5::load_stat::kRingPollUs * 5 : bc5::load_stat::kRingPollUs));''', '''#ifndef BC5_LEAN
		Direct::c438::flip(Direct::c438::kIdle); // exp 0438 (c438 part 2)
#endif
		std::this_thread::sleep_for(std::chrono::microseconds(idle_ticks > 1000 ? bc5::load_stat::kRingPollUs * 5 : bc5::load_stat::kRingPollUs));
#ifndef BC5_LEAN
		Direct::c438::flip(Direct::c438::kScan);
#endif''')

# 7. the 60-s line gains the slice and gap totals
rep('''					Direct::journal("c438 (exp 0438): t %.1f s: %" PRIu64 " acb packets;''', '''					{
						char b1[600], b2[600];
						uint64_t zero[Direct::c438::kN] = {}, sl[Direct::c438::kN], gp[Direct::c438::kN];
						for (int k = 0; k < Direct::c438::kN; k++) {
							sl[k] = Direct::c438::g_slice_ns[k].load();
							gp[k] = Direct::c438::g_gap_ns[k].load();
						}
						Direct::c438::fmt(b1, sizeof(b1), zero, sl);
						Direct::c438::fmt(b2, sizeof(b2), zero, gp);
						Direct::journal("c438 (exp 0438): t %.1f s: %" PRIu64 " slices, time inside submit <1/<5/<20/<100 ms/more %" PRIu64 "/%" PRIu64 "/%" PRIu64 "/%" PRIu64 "/%" PRIu64 ", longest %.3f ms, by kind (ms): %s; "
						                "%" PRIu64 " look gaps of 20 ms or more, bc5-ring's time in them by kind (ms): %s\\n",
						                Direct::timing_now(), Direct::c438::g_slices.load(), Direct::c438::g_slice_hist[0].load(), Direct::c438::g_slice_hist[1].load(), Direct::c438::g_slice_hist[2].load(),
						                Direct::c438::g_slice_hist[3].load(), Direct::c438::g_slice_hist[4].load(), static_cast<double>(Direct::c438::g_slice_max.load()) / 1e6, b1, Direct::c438::g_gap_n.load(), b2);
					}
					Direct::journal("c438 (exp 0438): t %.1f s: %" PRIu64 " acb packets;''')

# 8. at a give-up: bc5-ring's kind now, and per queue its time since that queue's last look by kind
rep('''					if (!ok) { // exp 0438 (c438): every guest queue as bc5-ring last left it
						std::lock_guard cl(c438::mu());
						const uint64_t  cn = SoftCp::now_ns();''', '''					if (!ok) { // exp 0438 (c438): every guest queue as bc5-ring last left it
						uint64_t z[c438::kN];
						c438::snap(z);
						journal("c438 (exp 0438):   bc5-ring is in %s for %.3f ms\\n", c438::kName[c438::g_cur.load()], static_cast<double>(c438::now() - c438::g_cur_since.load()) / 1e6);
						std::lock_guard cl(c438::mu());
						const uint64_t  cn = SoftCp::now_ns();''')
rep('''							else
								journal("c438 (exp 0438):   queue %u/%u/%u/0x%x: %u dwords pending, looked at %.3f ms ago; head ready\\n", e.a, e.b, e.c, e.d, e.pending, static_cast<double>(cn - e.poll) / 1e6);
						}''', '''							else
								journal("c438 (exp 0438):   queue %u/%u/%u/0x%x: %u dwords pending, looked at %.3f ms ago; head ready\\n", e.a, e.b, e.c, e.d, e.pending, static_cast<double>(cn - e.poll) / 1e6);
							if (e.pending != 0) {
								char b[600];
								c438::fmt(b, sizeof(b), e.at_look, z);
								journal("c438 (exp 0438):     since that look bc5-ring was: %s (ms)\\n", b);
							}
						}''')
