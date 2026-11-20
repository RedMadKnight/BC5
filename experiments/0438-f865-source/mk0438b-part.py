
# ---- k438b (exp 0438): ADR 0013's held tail on the way-2 path, with no give-up ----------------------------------------
# The held-tail machinery (HoldCond, hold_release, hold_note_writes, chain_submit's gate, the watchdog's and F10/F18's
# "hold.empty()" checks) is still in the unit; build W removed only its entry points (hold_keep_wait, the holder thread
# and the two call sites), when every compute buffer ran on the GFX ring. Exp 0428's way 2 brought the compute rings
# back without them. k438b puts them back on exp 0428's path (BC5_DIRECT_ACB_SPLIT_LATE=3), as of patch 4945ef1b
# (a2468923^), with one change: at hold_ns() the kept wait is NOT dropped (no give-up); the hold is journaled as a record
# at 100 ms, 1 s and every 10 s while it stands.

# 1. a record level on HoldCond
rep('''	const uint32_t* p     = nullptr; // the wait in the title's buffer: its kept offset is found by it
	bool            is64  = false;
	uint64_t        label = 0, t0 = 0;
};''', '''	const uint32_t* p     = nullptr; // the wait in the title's buffer: its kept offset is found by it
	bool            is64  = false;
	uint64_t        label = 0, t0 = 0;
	uint32_t        rec   = 0; // exp 0438 (k438b): the records journaled for this hold so far (100 ms, 1 s, then every 10 s)
};''')

# 2. the switch, counters, and no give-up in hold_release
rep('''static std::atomic<uint64_t>   g_hold_writer {0}, g_hold_sat {0}, g_hold_lost {0}, g_hold_ns_sum {0}, g_hold_ns_max {0};
''', '''static std::atomic<uint64_t>   g_hold_writer {0}, g_hold_sat {0}, g_hold_lost {0}, g_hold_ns_sum {0}, g_hold_ns_max {0};
// exp 0438 (tag k438b): BC5_0438_HOLD, on in this test build unless "0". The held tail of ADR 0013 on exp 0428's way-2 path,
// with no give-up: a hold past hold_ns() stays held and is journaled (a record), never dropped.
static bool k438b_on() {
	static const bool v = [] {
		const char* e = std::getenv("BC5_0438_HOLD");
		return !(e != nullptr && e[0] == '0' && e[1] == 0);
	}();
	return v;
}
static std::atomic<uint64_t>   g_hold_n {0}, g_hold_inner {0}, g_hold_records {0}, g_hold_blocked {0}, g_hold_block_ns {0}, g_hold_block_max {0};
static std::mutex              g_hold_mu;
static std::condition_variable g_hold_cv;
''')
rep('''				const bool lost = !sat && !wr && now - c.t0 >= hold_ns();
				if (!sat && !wr && !lost) {
					k++;
					continue;
				}''', '''				const bool lost = !sat && !wr && now - c.t0 >= hold_ns() && !k438b_on();
				if (!sat && !wr && !lost) {
					if (k438b_on()) { // exp 0438 (k438b): no give-up; a record at 100 ms, 1 s, then every 10 s
						const uint64_t age = now - c.t0;
						const uint64_t due = c.rec == 0 ? hold_ns() : (c.rec == 1 ? 1'000'000'000ull : 1'000'000'000ull + 10'000'000'000ull * (c.rec - 1));
						if (age >= due) {
							c.rec++;
							g_hold_records++;
							char pend[160];
							describe_pending(c.label, pend, sizeof(pend));
							journal("hold tail (exp 0438, k438b): STILL HELD after %.1f ms on 0x%" PRIx64 " (value 0x%" PRIx64 ", the writer not on a ring; %s); the wait stays kept, nothing is dropped (record %u)\\n",
							        static_cast<double>(age) / 1e6, c.label,
							        c.is64 ? *reinterpret_cast<const volatile uint64_t*>(c.label & ~7ull) : static_cast<uint64_t>(*reinterpret_cast<const volatile uint32_t*>(c.label & ~3ull)), pend, c.rec);
						}
					}
					k++;
					continue;
				}''')
# the time an owner's flush is held by a hold (block = true), counted
rep('''static bool hold_release(ChainSlot& s, bool block) {
	for (;;) {''', '''static bool hold_release(ChainSlot& s, bool block) {
	const uint64_t hb0 = SoftCp::now_ns(); // exp 0438 (k438b): how long a blocking caller waits
	bool           waited = false;
	for (;;) {''')
rep('''			if (s.hold.empty()) return true;
		}
		if (!block) return false;
		std::this_thread::sleep_for(std::chrono::microseconds(20));''', '''			if (s.hold.empty()) {
				if (waited) {
					const uint64_t d = SoftCp::now_ns() - hb0;
					g_hold_blocked++;
					g_hold_block_ns += d;
					for (uint64_t m = g_hold_block_max.load(); d > m && !g_hold_block_max.compare_exchange_weak(m, d);) {
					}
				}
				return true;
			}
		}
		if (!block) return false;
		waited = true;
		std::this_thread::sleep_for(std::chrono::microseconds(20));''')

# 3. the entry points of patch 4945ef1b (hold_stats, hold_chain_held, hold_keep_wait, hold_thread), before the chain counters
rep('''static std::atomic<uint64_t> g_chain_flushes {0}, g_chain_segments {0}, g_chain_single {0}, g_chain_dwords {0}, g_chain_cond_segs {0};
static std::atomic<uint64_t> g_chain_why[12];''', '''// exp 0438 (k438b): ADR 0013's entry points as of patch 4945ef1b, the give-up count replaced by the records.
static void hold_stats(bool force) {
	static double last = 0;
	const double  now  = timing_now();
	if (!force && now - last < 10.0) return;
	last            = now;
	const uint64_t done = g_hold_writer.load() + g_hold_sat.load() + g_hold_lost.load();
	journal("hold tail (exp 0438, k438b): %" PRIu64 " holds; released with the writer on a ring %" PRIu64 ", satisfied %" PRIu64 ", given up %" PRIu64 "; held %.2f ms on average, %.2f ms at most; %" PRIu64
	        " waits kept inside held chains; records (still held at 100 ms / 1 s / 10 s) %" PRIu64 "; owner flushes that waited for a hold %" PRIu64 ", %.1f ms in all, longest %.1f ms\\n",
	        g_hold_n.load(), g_hold_writer.load(), g_hold_sat.load(), g_hold_lost.load(), done != 0 ? static_cast<double>(g_hold_ns_sum.load()) / 1e6 / static_cast<double>(done) : 0.0,
	        static_cast<double>(g_hold_ns_max.load()) / 1e6, g_hold_inner.load(), g_hold_records.load(), g_hold_blocked.load(), static_cast<double>(g_hold_block_ns.load()) / 1e6,
	        static_cast<double>(g_hold_block_max.load()) / 1e6);
}
static bool hold_chain_held() {
	ChainSlot&      s = g_chain_tl;
	std::lock_guard lk(s.mu);
	return !s.hold.empty();
}
static void hold_thread();
// Keeps a game-thread wait in the held chain: with a condition, unless the held chain writes its label itself.
// join: only if the chain is still held (the holder may have released and submitted it since the caller looked);
// false then, and the caller takes the normal path (its split sends the head first).
static bool hold_keep_wait(const uint32_t* p, uint32_t len, bool is64, uint64_t label, uint64_t t0, bool join) {
	ChainSlot& s = g_chain_tl;
	{
		std::lock_guard lk(s.mu);
		if (join && s.hold.empty()) return false;
		if (!s.hold.empty() && std::find(s.hold_writes.begin(), s.hold_writes.end(), label & ~3ull) != s.hold_writes.end()) {
			g_hold_inner++;
			return true; // the chain writes it first: the GPU's order serves it
		}
		HoldCond c;
		const uint32_t n = is64 ? 8u : (len < 8 ? len : 8u);
		for (uint32_t k = 0; k < n; k++) c.pkt[k] = p[k];
		c.p     = p;
		c.is64  = is64;
		c.label = label;
		c.t0    = t0;
		s.hold.push_back(c);
	}
	if (++g_hold_n <= 20 || (g_hold_n.load() & 0x3fu) == 0) journal("hold tail (exp 0438, k438b): the game thread's chain is held on 0x%" PRIx64 " at t %.6f s (%" PRIu64 " so far)\\n", label, timing_now(), g_hold_n.load());
	static std::once_flag started;
	std::call_once(started, [] { std::thread(hold_thread).detach(); });
	g_hold_cv.notify_one();
	return true;
}
// The holder: submits each held chain once its conditions are met (chain_submit's gate decides).
static void hold_thread() {
	pthread_setname_np(pthread_self(), "bc5-hold");
	for (;;) {
		bool any = false;
		{
			std::lock_guard lk(g_chains_mu);
			for (ChainSlot* s: g_chains) {
				bool held = false, busy = false;
				{
					std::lock_guard sl(s->mu);
					held = !s->hold.empty();
					busy = s->in_submit;
				}
				if (!held) continue;
				any = true;
				if (!busy) chain_submit(*s, 11, true);
			}
		}
		hold_stats(false);
		if (any) {
			std::this_thread::sleep_for(std::chrono::microseconds(20));
			continue;
		}
		std::unique_lock lk(g_hold_mu);
		g_hold_cv.wait_for(lk, std::chrono::milliseconds(50));
	}
}
static std::atomic<uint64_t> g_chain_flushes {0}, g_chain_segments {0}, g_chain_single {0}, g_chain_dwords {0}, g_chain_cond_segs {0};
static std::atomic<uint64_t> g_chain_why[12];''')

# 4. the call sites, on exp 0428's way-2 path before its 8 ms poll (and before k438's)
rep('''						if (split_late >= 3 && k438::mode() >= 2 && !wait_satisfied(p, op == 0x93) && !ring_will_satisfy(p, op == 0x93, bc5::direct::kGfxRing)) {''', '''						// exp 0438 (tag k438b): ADR 0013 (experiment 0226) on the way-2 path. The thread's chain is held already: this wait
						// joins it, kept for the GPU (with a condition unless its writer is on a ring or the held chain writes its label); no
						// split, no polling. Else, when no writer is on a ring: the head goes (or there was none), the rest waits in the held
						// chain, and the title's thread goes on; bc5-hold submits the chain once the label is met or its writer is on a ring.
						if (split_late >= 3 && k438b_on() && chain_cross() && !wait_satisfied(p, op == 0x93)) {
							if (hold_chain_held() && (ring_will_satisfy(p, op == 0x93, bc5::direct::kGfxRing) || hold_keep_wait(p, len, op == 0x93, label, t0, true))) {
								t_keep_waits.push_back(p);
								SoftCp::set_gpu_executed(p, len, {0});
								i += len;
								continue;
							}
							if (!ring_will_satisfy(p, op == 0x93, bc5::direct::kGfxRing)) {
								bool hsplit = false;
								if (dry_here && i > start) {
									if ((start > 0 || prefix_all() || cs_used) && !full_prefix.empty()) submit_prefixed(full_prefix, ib + start, i - start);
									else submit_one(ib + start, i - start, kind);
									chain_flush(1); // ADR 0010: the head goes first
									full_prefix = prefix_of(*dry);
									start       = i;
									full_used   = true;
									hsplit      = true;
									g_full_pieces++;
								}
								if ((hsplit || i == start) && !wait_satisfied(p, op == 0x93) && !ring_will_satisfy(p, op == 0x93, bc5::direct::kGfxRing)) {
									if (!hsplit) chain_flush(1); // what the chain holds from earlier buffers goes first, as the split's flush does
									hold_keep_wait(p, len, op == 0x93, label, t0, false);
									t_keep_waits.push_back(p);
									SoftCp::set_gpu_executed(p, len, {0});
									i += len;
									continue;
								}
							}
						}
						if (split_late >= 3 && k438::mode() >= 2 && !wait_satisfied(p, op == 0x93) && !ring_will_satisfy(p, op == 0x93, bc5::direct::kGfxRing)) {''')

# 5. while the thread's chain is held, its owner does not flush it at a later wait (that flush would wait for the hold
#    on the title's thread, the F284 shape ADR 0013 removed): the wait joins the hold on the path above instead.
rep('''					if (!wait_satisfied(p, op == 0x93)) chain_flush(1); // ADR 0010: what the chain holds may write this label''',
    '''					if (!wait_satisfied(p, op == 0x93) && !(k438b_on() && on_game_thread() && hold_chain_held())) chain_flush(1); // ADR 0010: what the chain holds may write this label; exp 0438 (k438b): not while it is held''')
rep('''							else if (split_late >= 2) {
								chain_flush(1); // ADR 0010: the thread's earlier buffers go; this one is not split''',
    '''							else if (split_late >= 2 && !(k438b_on() && hold_chain_held())) { // exp 0438 (k438b): not while the chain is held
								chain_flush(1); // ADR 0010: the thread's earlier buffers go; this one is not split''')
