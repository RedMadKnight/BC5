#!/usr/bin/env python3
"""BC5 experiment 0438 (tag r438): the fix "register early", with c438's records, on top of the catcher unit.

Usage: mkr438.py IN.cpp OUT.cpp   (IN: cat/bc5LleAgc.cpp made by mkcat438.py, md5 3623fd41...)

r438 (switch BC5_0438_EARLYREG, on in this test build unless "0"; behaviour, so in lean too):
- When bc5-ring takes a queue slice, before chain_end and submit_now's preparation, the label writes of the slice's
  compute buffers (RELEASE_MEM / EVENT_WRITE_EOP with 32/64-bit data, WRITE_DATA to memory; top-level packets from the
  part not yet submitted, as register_label_writes reads them) are registered as pending ("early", a seq with bit 63).
- A game-thread wait whose label's last pending write is early is kept for the GPU in ring order, as for any pending
  writer, but only once that early write has become real: ring_will_satisfy on the game thread waits (polls) until
  bc5-ring has ended the slice (the real registration after the kernel call), then decides again. So the writer job is
  in the kernel before the waiter's buffer, the order ring-order keeps always had (k438 broke it). A wait over 100 ms
  is journaled as a bug line and the poll goes on: no give-up, no recovery.
- bc5-ring itself, F2/F4 (they need a real job to fence on) and the reset path ignore early entries.
- The invariant: every early write reaches the ring. At the slice's end each early write must have been registered
  for real by a job of that slice (register_label_writes on bc5-ring during the slice). One that was not is a bug line
  and counted ("early writes that never reached the ring"), then removed.
Records (normal build only): submit_now's preparation split into pre-passes / anon sync / direct sync / learned /
hints / filter (new c438 kinds); bc5-ring's device-mutex waits attributed to the holder at the wait's start (game
thread / bc5-ring / other, and the holder's part); r438's counts on the c438 60-s line.
"""
import hashlib
import sys

IN, OUT = sys.argv[1], sys.argv[2]
src = open(IN, 'rb').read()
assert hashlib.md5(src).hexdigest() == '3623fd41142c49514fce913c34c2efab', 'not the c438 part-2 unit'
s = src.decode('utf-8')


def rep(old, new, count=1):
    global s
    n = s.count(old)
    assert n == count, (n, old[:120])
    s = s.replace(old, new)


# ---- records: the prepare kinds and the device-mutex holder ----------------------------------------------------------
rep('''enum : int { kIdle, kScan, kSubmit, kF10, kF16, kF18, kBackPressure, kRingLock, kDevMutex, kBackend, kAcbCpuWait, kWaitIdle, kN }; // exp 0438 (c438 part 2)''',
    '''enum : int { kIdle, kScan, kSubmit, kF10, kF16, kF18, kBackPressure, kRingLock, kDevMutex, kBackend, kAcbCpuWait, kWaitIdle, kPre, kAnonSync, kDirectSync, kLearned, kHints, kFilter, kPreWw, kPreK1, kPreDt, kN }; // exp 0438 (c438 part 2; r438 build: the prepare parts)''')
rep('''inline const char* const kName[kN] = {"idle", "scan", "submit", "F10", "F16", "F18", "back-pressure", "ring-lock", "dev-mutex", "backend+ioctl", "acb-cpu-wait", "wait-idle"};''',
    '''inline const char* const kName[kN] = {"idle", "scan", "submit", "F10", "F16", "F18", "back-pressure", "ring-lock", "dev-mutex", "backend+ioctl", "acb-cpu-wait", "wait-idle", "prep-pre", "prep-anon-sync", "prep-direct-sync", "prep-learned", "prep-hints", "prep-filter", "prep-pre-ww412", "prep-pre-k1f412", "prep-pre-dt412"};
// r438 build: who holds the device mutex (1 game thread, 2 bc5-ring, 3 other) * 32 + the holder's kind; bc5-ring's waits by it
inline std::atomic<int>      g_holder {0};
inline std::atomic<uint64_t> g_dm_by[128] = {};
inline thread_local int t_who = 3; // set at submit_now's start: 1 game thread, 2 bc5-ring, 3 other
inline void hold(int k) {
	g_holder.store(t_who * 32 + k);
}''')
# t_cq is defined later in the unit; mirror it through a small thread_local the submit path sets
rep('''static thread_local UnreadyWait t_unready;
''', '''static thread_local UnreadyWait t_unready;
// BC5 experiment 0438 (tag r438): early registration of a taken queue slice's label writes (defined after
// register_label_writes).
static void r438_begin(const uint32_t* s1, uint32_t n1, const uint32_t* s2, uint32_t n2);
static void r438_end();
// exp 0438 (tag r438): early entries carry seq | kR438Early; the order counter is shared with register_label_writes.
static constexpr uint64_t                  kR438Early = 1ull << 63u;
static uint64_t                            g_plw_order = 0; // under g_plw_mutex
static thread_local bool                   t_r438_on_slice = false;
static thread_local std::vector<uint64_t>  t_r438_real; // the labels the slice's jobs registered for real
static int r438_mode() { // 0 off, 1 r438 (wait on any early last write), 2 r438a (wait only when no real pending write satisfies); unset: 2 in this test build
	static const int v = [] {
		const char* e = std::getenv("BC5_0438_EARLYREG");
		if (e == nullptr || e[0] == 0) return 2;
		return std::atoi(e);
	}();
	return v;
}
static bool r438_on() { return r438_mode() >= 1; }
static std::atomic<uint64_t> g_r438_slices {0}, g_r438_early {0}, g_r438_lost {0}, g_r438_waits {0}, g_r438_wait_ns {0}, g_r438_wait_max {0}, g_r438_long {0}, g_r438_cheap {0};
''')
rep('''static void submit_now(const uint32_t* ib, uint32_t num_dwords, const char* kind, int ring, const Chain* chain) {''',
    '''static void submit_now(const uint32_t* ib, uint32_t num_dwords, const char* kind, int ring, const Chain* chain) {
#ifndef BC5_LEAN
	const c438::Scope c438_sn(c438::t_kind); // exp 0438 (r438 build): submit_now's kinds end with it
	c438::t_who = c438::t_ring ? 2 : (t_cq == 0 ? 1 : 3);
#endif''')
rep('''#ifndef BC5_LEAN
	c438::flip(c438::kDevMutex);
#endif
	std::unique_lock<std::mutex> lock(g_dev_mutex);
#ifndef BC5_LEAN
	c438::flip(c438_prev);
#endif''', '''#ifndef BC5_LEAN
	c438::flip(c438::kDevMutex);
	const int      c438_h0 = c438::g_holder.load(); // r438 build: the holder at the wait's start
	const uint64_t c438_w0 = c438::now();
#endif
	std::unique_lock<std::mutex> lock(g_dev_mutex);
#ifndef BC5_LEAN
	(void)c438_prev;
	if (c438::t_ring) c438::g_dm_by[c438_h0 & 127] += c438::now() - c438_w0;
	c438::flip(c438::kPre);
	c438::hold(c438::kPre);
#endif''')
for var, kind in (('ta', 'kAnonSync'), ('tb', 'kDirectSync'), ('tc', 'kHints'), ('t2', 'kFilter')):
    rep('''	const uint64_t %s = SoftCp::now_ns();
''' % var, '''	const uint64_t %s = SoftCp::now_ns();
#ifndef BC5_LEAN
	c438::flip(c438::%s); // exp 0438 (r438 build)
	c438::hold(c438::%s);
#endif
''' % (var, kind, kind))
rep('''	}
	const uint64_t t1 = SoftCp::now_ns();
	uint64_t       fs_ds[8];''', '''	}
	const uint64_t t1 = SoftCp::now_ns();
#ifndef BC5_LEAN
	c438::flip(c438::kLearned); // exp 0438 (r438 build)
	c438::hold(c438::kLearned);
#endif
	uint64_t       fs_ds[8];''')
rep('''	const uint64_t ls_t3 = SoftCp::now_ns(); // experiment 0415 (ls415c)''', '''	const uint64_t ls_t3 = SoftCp::now_ns(); // experiment 0415 (ls415c)
#ifndef BC5_LEAN
	c438::hold(c438::kBackend); // exp 0438 (r438 build)
#endif''')


rep('''	ww412_packets(ib, num_dwords); // exp 0412 (tag ww412)
	k1f412_pass(ib, num_dwords, kind); // exp 0412 (tag k1f412)
	dt412_pass(ib, num_dwords, kind); // exp 0412 (tag dt412): before the mappings are synced''', '''#ifndef BC5_LEAN
	c438::flip(c438::kPreWw); // exp 0438 (r438 build, mode 2 build): prep-pre by pass
	c438::hold(c438::kPreWw);
#endif
	ww412_packets(ib, num_dwords); // exp 0412 (tag ww412)
#ifndef BC5_LEAN
	c438::flip(c438::kPreK1);
	c438::hold(c438::kPreK1);
#endif
	k1f412_pass(ib, num_dwords, kind); // exp 0412 (tag k1f412)
#ifndef BC5_LEAN
	c438::flip(c438::kPreDt);
	c438::hold(c438::kPreDt);
#endif
	dt412_pass(ib, num_dwords, kind); // exp 0412 (tag dt412): before the mappings are synced
#ifndef BC5_LEAN
	c438::flip(c438::kPre);
	c438::hold(c438::kPre);
#endif''')

# ---- r438: early registration --------------------------------------------------------------------------------------
# a. the definitions, after register_label_writes' insertion into g_plw
rep('''	if (found.empty()) return;
	std::lock_guard lk(g_plw_mutex);
	static uint64_t order = 0;''', '''	if (found.empty()) return;
	if (t_r438_on_slice) for (const auto& w: found) t_r438_real.push_back(w.label); // exp 0438 (r438): what this slice's jobs registered
	std::lock_guard lk(g_plw_mutex);
	static uint64_t& order = g_plw_order; // exp 0438 (r438): shared with the early registration''')
rep('''static std::mutex                          g_plw_mutex;
static std::vector<PendingLabelWrite>      g_plw;''', '''static std::mutex                          g_plw_mutex;
static std::vector<PendingLabelWrite>      g_plw;
// exp 0438 (tag r438): early entries carry seq | kR438Early; the order counter is shared with register_label_writes.
''')

rep('''static void forget_label_writes(uint64_t seq, int ring, bool all) {''', '''// exp 0438 (tag r438): the slice bc5-ring has taken: its compute buffers' label writes, early.
static thread_local uint64_t t_r438_slice = 0;
static void r438_scan(const uint32_t* ring_part, uint32_t n, std::vector<PendingLabelWrite>& out) {
	for (uint32_t k = 0; k < n;) {
		const uint32_t hh = ring_part[k];
		uint32_t       ll = 1;
		if ((hh >> 30u) == 3) {
			const uint32_t c = (hh >> 16u) & 0x3fffu;
			ll               = c == 0x3fffu ? 1 : c + 2;
		}
		if ((hh >> 30u) == 3 && (((hh >> 8u) & 0xffu) == 0x3f || ((hh >> 8u) & 0xffu) == 0x33) && ll >= 4 && k + ll <= n) {
			const uint64_t ta = (ring_part[k + 1] & ~3u) | (static_cast<uint64_t>(ring_part[k + 2] & 0xffu) << 32u);
			const uint32_t tn = ring_part[k + 3] & 0xfffffu;
			const auto*    ib = reinterpret_cast<const uint32_t*>(ta);
			uint32_t       done = 0;
			for (const auto& e: g_acb_heads)
				if (e.ib == ib && e.num_dwords == tn) done = e.done;
			for (uint32_t q = done; ta != 0 && q < tn;) {
				const uint32_t* w   = ib + q;
				const uint32_t  h   = w[0];
				uint32_t        len = 1;
				if ((h >> 30u) == 3 || (h >> 30u) == 0) {
					const uint32_t c = (h >> 16u) & 0x3fffu;
					len              = c == 0x3fffu ? 1 : c + 2;
				}
				if (q + len > tn) break;
				const uint32_t op = (h >> 8u) & 0xffu;
				auto addr = [w](int lo, int hi) { return (static_cast<uint64_t>(w[lo]) & ~3ull) | (static_cast<uint64_t>(w[hi] & 0xffffu) << 32u); };
				if ((h >> 30u) == 3) { // as register_label_writes reads them
					if (op == 0x49 && len >= 8) {
						const uint32_t ds = w[2] >> 29u;
						if (ds == 1) out.push_back({addr(3, 4), w[5], 0, false});
						if (ds == 2) out.push_back({addr(3, 4), w[5] | (static_cast<uint64_t>(w[6]) << 32u), 0, true});
					} else if (op == 0x47 && len >= 6) {
						const uint32_t ds = w[3] >> 29u;
						if (ds == 1) out.push_back({addr(2, 3), w[4], 0, false});
						if (ds == 2) out.push_back({addr(2, 3), w[4] | (static_cast<uint64_t>(w[5]) << 32u), 0, true});
					} else if (op == 0x37 && len >= 5) {
						const uint32_t dst = (w[1] >> 8u) & 0xfu;
						if (dst == 1 || dst == 2 || dst == 5) {
							if (len >= 6) out.push_back({addr(2, 3), w[4] | (static_cast<uint64_t>(w[5]) << 32u), 0, true});
							else out.push_back({addr(2, 3), w[4], 0, false});
						}
					}
				}
				q += len;
			}
		}
		k += ll;
	}
}
static void r438_begin(const uint32_t* s1, uint32_t n1, const uint32_t* s2, uint32_t n2) {
	if (!r438_on()) return;
	std::vector<PendingLabelWrite> found;
	r438_scan(s1, n1, found);
	if (s2 != nullptr) r438_scan(s2, n2, found);
	t_r438_slice    = g_r438_slices.fetch_add(1) + 1;
	t_r438_on_slice = true;
	t_r438_real.clear();
	if (found.empty()) return;
	std::lock_guard lk(g_plw_mutex);
	for (auto& w: found) {
		w.seq   = kR438Early | t_r438_slice;
		w.ring  = 0; // a compute ring; with the acb rings on, ring_will_satisfy keeps a writer on another ring
		w.order = ++g_plw_order;
	}
	if (g_plw.size() > 8192) g_plw.erase(g_plw.begin(), g_plw.begin() + 4096);
	g_plw.insert(g_plw.end(), found.begin(), found.end());
	g_r438_early += found.size();
}
// The slice's end: every early write must have been registered for real by the slice's jobs; the early entries go.
static void r438_end() {
	if (!r438_on() || !t_r438_on_slice) return;
	t_r438_on_slice = false;
	std::vector<PendingLabelWrite> lost;
	{
		std::lock_guard lk(g_plw_mutex);
		for (auto it = g_plw.begin(); it != g_plw.end();) {
			if (it->seq == (kR438Early | t_r438_slice)) {
				if (std::find(t_r438_real.begin(), t_r438_real.end(), it->label) == t_r438_real.end()) lost.push_back(*it);
				it = g_plw.erase(it);
			} else {
				++it;
			}
		}
	}
	for (const auto& w: lost) {
		const uint64_t k = g_r438_lost++;
		if (k < 200 || (k & 0xffu) == 0)
			journal("r438 (exp 0438): BUG: the early-registered write of 0x%" PRIx64 " (value 0x%" PRIx64 ") of slice %" PRIu64 " never reached the ring (%" PRIu64 " so far)\\n", w.label, w.value, t_r438_slice, k + 1);
	}
	t_r438_real.clear();
}
static void forget_label_writes(uint64_t seq, int ring, bool all) {''')

# b. F2/F4 need a real job: early entries are not theirs
rep('''			if (w.label == label && w.ring != ring && std::find(others.begin(), others.end(), std::make_pair(w.ring, w.seq)) == others.end()) others.emplace_back(w.ring, w.seq);''',
    '''			if (w.label == label && w.ring != ring && (w.seq & kR438Early) == 0 && std::find(others.begin(), others.end(), std::make_pair(w.ring, w.seq)) == others.end()) others.emplace_back(w.ring, w.seq); // exp 0438 (r438): no early entry''')

# c. ring_will_satisfy: an early last write: the game thread waits until it is real, then decides again; others skip it
rep('''static bool ring_will_satisfy(const uint32_t* p, bool is64, int ring) {
	const uint32_t function = p[1] & 7u;
	const uint64_t a        = (p[2] & ~3u) | (static_cast<uint64_t>(p[3] & 0xffffu) << 32u);
	std::lock_guard lk(g_plw_mutex);
	const PendingLabelWrite* last = nullptr;
	for (const auto& w: g_plw) {
		if (w.label == a && (last == nullptr || w.order >= last->order)) last = &w;
	}
	if (last == nullptr) return false;''', '''static bool ring_will_satisfy(const uint32_t* p, bool is64, int ring) {
	const uint32_t function = p[1] & 7u;
	const uint64_t a        = (p[2] & ~3u) | (static_cast<uint64_t>(p[3] & 0xffffu) << 32u);
	const bool     game     = on_game_thread();
	std::unique_lock lk(g_plw_mutex);
	const PendingLabelWrite* last = nullptr;
	for (uint64_t r438_t0 = 0, r438_rec = 0;;) { // exp 0438 (r438): an early last write is waited for on the game thread
		last = nullptr;
		for (const auto& w: g_plw) {
			if (w.label == a && (game || (w.seq & kR438Early) == 0) && (last == nullptr || w.order >= last->order)) last = &w;
		}
		if (last != nullptr && (last->seq & kR438Early) != 0 && game && r438_mode() >= 2) { // r438a: a real pending write that satisfies needs no wait
			const PendingLabelWrite* real = nullptr;
			for (const auto& w: g_plw)
				if (w.label == a && (w.seq & kR438Early) == 0 && (real == nullptr || w.order >= real->order)) real = &w;
			if (real != nullptr && (real->ring == ring || w428_rings() != 0)) {
				bool sat = false;
				if (is64) {
					if (real->is64) {
						const uint64_t ref = p[4] | (static_cast<uint64_t>(p[5]) << 32u), mask = p[6] | (static_cast<uint64_t>(p[7]) << 32u);
						const uint64_t vm = real->value & mask, rm = ref & mask;
						sat = function == 1 ? vm < rm : function == 2 ? vm <= rm : function == 3 ? vm == rm : function == 4 ? vm != rm : function == 5 ? vm >= rm : function == 6 ? vm > rm : false;
					}
				} else {
					sat = SoftCp::compare(function, static_cast<uint32_t>(real->value), p[5], p[4]);
				}
				if (sat) {
					g_r438_cheap++;
					last = real;
					break;
				}
			}
		}
		if (last == nullptr || (last->seq & kR438Early) == 0) {
			if (r438_t0 != 0) {
				const uint64_t d = SoftCp::now_ns() - r438_t0;
				g_r438_waits++;
				g_r438_wait_ns += d;
				for (uint64_t m = g_r438_wait_max.load(); d > m && !g_r438_wait_max.compare_exchange_weak(m, d);) {
				}
			}
			break;
		}
		if (r438_t0 == 0) r438_t0 = SoftCp::now_ns();
		const uint64_t held = SoftCp::now_ns() - r438_t0;
		if (held >= 100'000'000ull * (r438_rec + 1) && r438_rec < 10) { // a bug line at 100 ms, 200 ms, ...; the wait goes on
			r438_rec++;
			g_r438_long++;
			lk.unlock();
			journal("r438 (exp 0438): BUG: a game-thread wait on 0x%" PRIx64 " has waited %.1f ms for an early-registered writer to reach the ring\\n", a, static_cast<double>(held) / 1e6);
			lk.lock();
			continue;
		}
		lk.unlock();
		std::this_thread::sleep_for(std::chrono::microseconds(20));
		lk.lock();
	}
	if (last == nullptr) return false;''')

# d. the slice: early at take, end after chain_end
rep('''			Direct::chain_begin(); // ADR 0010: the slice's buffers as one submission
			if (w_take > r) {
				Direct::submit(ring + r, w_take - r, "ring");
			} else {
				Direct::submit(ring + r, n - r, "ring");
				if (w_take != 0) Direct::submit(ring, w_take, "ring");
			}
			Direct::chain_end();''', '''			if (w_take > r) Direct::r438_begin(ring + r, w_take - r, nullptr, 0); // exp 0438 (r438): the slice's writes, early
			else Direct::r438_begin(ring + r, n - r, ring, w_take);
			Direct::chain_begin(); // ADR 0010: the slice's buffers as one submission
			if (w_take > r) {
				Direct::submit(ring + r, w_take - r, "ring");
			} else {
				Direct::submit(ring + r, n - r, "ring");
				if (w_take != 0) Direct::submit(ring, w_take, "ring");
			}
			Direct::chain_end();
			Direct::r438_end(); // exp 0438 (r438): every early write must have reached the ring''')

# e. the counts on c438's 60-s line (normal build)
rep('''						Direct::journal("c438 (exp 0438): t %.1f s: %" PRIu64 " slices, time inside submit''', '''						{
							char hb[900];
							int  hw = 0;
							hb[0]   = 0;
							for (int h = 0; h < 128 && hw < 820; h++) {
								const uint64_t v = Direct::c438::g_dm_by[h].load();
								if (v >= 50'000'000ull) hw += std::snprintf(hb + hw, sizeof(hb) - static_cast<size_t>(hw), "%s%s/%s %.1f", hw ? ", " : "", (h >> 5) == 1 ? "game" : (h >> 5) == 2 ? "ring" : (h >> 5) == 3 ? "other" : "?",
								                       Direct::c438::kName[(h & 31) < Direct::c438::kN ? (h & 31) : 0], static_cast<double>(v) / 1e9);
							}
							Direct::journal("r438 (exp 0438): t %.1f s: mode %d %s; real write satisfied, no wait %" PRIu64 "; slices %" PRIu64 ", early writes %" PRIu64 ", early writes that never reached the ring %" PRIu64 "; game-thread waits for an early writer %" PRIu64 ", %.1f ms in all, longest %.3f ms, bug lines (over 100 ms) %" PRIu64 "; "
							                "bc5-ring's device-mutex waits by the holder at their start (s): %s\\n",
							                Direct::timing_now(), Direct::r438_mode(), Direct::r438_on() ? "ON" : "off", Direct::g_r438_cheap.load(), Direct::g_r438_slices.load(), Direct::g_r438_early.load(), Direct::g_r438_lost.load(), Direct::g_r438_waits.load(),
							                static_cast<double>(Direct::g_r438_wait_ns.load()) / 1e6, static_cast<double>(Direct::g_r438_wait_max.load()) / 1e6, Direct::g_r438_long.load(), hb);
						}
						Direct::journal("c438 (exp 0438): t %.1f s: %" PRIu64 " slices, time inside submit''')

out = s.encode('utf-8')
open(OUT, 'wb').write(out)
print('r438 unit', hashlib.md5(out).hexdigest(), len(out))
