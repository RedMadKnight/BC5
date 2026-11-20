#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""BC5 experiment 0438 (tag b438): r438 alone on the shared tree's unit, in the shape a bake would take.
Usage: mkb438.py IN.cpp OUT.cpp   (IN: patch bb04219b's src/libs/bc5LleAgc.cpp = exp 0436's bake unit, md5 a62e8bf6...)

What it carries over from mkr438.py (exp 0438 results 6-12), and nothing else (no c438, k438, u438, s438, e438):
  - at the take of a queue slice, bc5-ring registers the label writes of the slice's compute buffers as pending "early"
    entries (seq | bit 63); at the slice's end each must have been registered for real by the slice's jobs, and the
    early entries go;
  - ring_will_satisfy on the game thread: a label whose last pending write is early is polled until it is real, then the
    wait is decided again and kept in ring order (no give-up). Other threads, and F2/F4, ignore early entries;
  - mode 1 only (r438a's mode 2 never fired, result 7). Switch BC5_0438_EARLYREG: on unless "0" (behaviour: in lean too).
PLWCV (BC5_0438_PLWCV, on unless "0", lean reads it; the top session's fix of 2026-11-20): the game thread's wait for
an early writer sleeps on a condition variable (g_plw_cv, at most 10 ms per sleep, the wait goes on), signalled when a
job registers its writes and at the slice's end; "0" keeps r438's 20-us poll, which re-took g_plw_mutex between scans
and held the registering thread off (test_b438 case 6).
Lean: early writes that never reached the ring are counted; the first one prints one stderr line, and the total is
printed at a normal exit (a SIGTERM ends the process without it: the tree installs no handler).
p438 (BC5_0438_PROLMERGE, on unless "0", lean reads it; the maintainer's word of 2026-11-20): the submit header's
prologue (0xc0488131: context control + 3 header IBs) is not submitted alone. Its packets are copied to a stable slot
and submitted at the head of the next 0xc0188132's chain (one kernel submit fewer; same packets, order and ring).
Flushed alone first, as today, before any other gc submit (0xc0108102, 0xc020810c), at "submit done" / "wait idle", and
at the EOP flip. Submitted alone at once, as today, when one of its header IBs writes memory or nests an IB (a CPU waiter
could need it before the next submit), when 8 are pending, or with the acb rings off (w428_rings() == 0: acbs share the
GFX ring). Records (normal): merged, alone by reason, every 60 s.
Normal build only (#ifndef BC5_LEAN): the counters, the BUG lines (a lost early write; a game-thread wait at 100 ms,
200 ms, ...; the wait goes on) and a 60-s line "r438 (exp 0438, b438)". Lean keeps the registration, the poll and the
removal of a lost write's early entry, with no counter and no line.
"""
import hashlib
import sys

IN, OUT = sys.argv[1], sys.argv[2]
src = open(IN, 'rb').read()
assert hashlib.md5(src).hexdigest() == 'a62e8bf6251a44f147a23d9689449e21', 'not patch bb04219b tree unit'
s = src.decode('utf-8')
assert '\r' not in s


def rep(old, new, count=1):
    global s
    n = s.count(old)
    assert n == count, (n, old[:120])
    s = s.replace(old, new)


NL = chr(92) + 'n'

# 1. the state, before its first use
rep('''static thread_local UnreadyWait t_unready;
''', '''static thread_local UnreadyWait t_unready;
// BC5 experiment 0438 (tag b438): r438, early registration of a taken queue slice's label writes (defined after
// register_label_writes). Switch BC5_0438_EARLYREG: on unless "0".
static void r438_begin(const uint32_t* s1, uint32_t n1, const uint32_t* s2, uint32_t n2);
static void r438_end();
static constexpr uint64_t                 kR438Early = 1ull << 63u; // early entries carry seq | kR438Early
static uint64_t                           g_plw_order = 0;          // under g_plw_mutex, shared with register_label_writes
static thread_local bool                  t_r438_on_slice = false;
static thread_local std::vector<uint64_t> t_r438_real;              // the labels the slice's jobs registered for real
static bool r438_on() {
	static const bool v = [] {
		const char* e = std::getenv("BC5_0438_EARLYREG");
		return !(e != nullptr && e[0] == '0' && e[1] == 0);
	}();
	return v;
}
static bool r438_cv() { // exp 0438 (b438, PLWCV): the early-writer wait on a condition variable, on unless "0"
	static const bool v = [] {
		const char* e = std::getenv("BC5_0438_PLWCV");
		return !(e != nullptr && e[0] == '0' && e[1] == 0);
	}();
	return v;
}
#ifdef BC5_LEAN
static std::atomic<uint64_t> g_r438_lost_lean {0}; // exp 0438 (b438): lean's one counter, printed at a normal exit
struct R438LeanExit {
	~R438LeanExit() {
		if (r438_on()) std::fprintf(stderr, "r438 (exp 0438, b438, lean): early writes that never reached the ring %" PRIu64 "\\n", g_r438_lost_lean.load());
	}
};
static R438LeanExit g_r438_lean_exit;
#endif
#ifndef BC5_LEAN
static std::atomic<uint64_t> g_r438_early {0}, g_r438_lost {0}, g_r438_waits {0}, g_r438_wait_ns {0}, g_r438_wait_max {0}, g_r438_long {0};
#endif
static std::atomic<uint64_t> g_r438_slices {0};
''')

# 2. register_label_writes: what the slice's jobs registered; the order counter shared
rep('''	if (found.empty()) return;
	std::lock_guard lk(g_plw_mutex);
	static uint64_t order = 0;''', '''	if (found.empty()) return;
	if (t_r438_on_slice) for (const auto& w: found) t_r438_real.push_back(w.label); // exp 0438 (b438): what this slice's jobs registered
	std::lock_guard lk(g_plw_mutex);
	static uint64_t& order = g_plw_order; // exp 0438 (b438): shared with the early registration''')

# 3. the scan, the take and the end
rep('''static void forget_label_writes(uint64_t seq, int ring, bool all) {''', '''// exp 0438 (tag b438): the slice bc5-ring has taken: its compute buffers' label writes, early.
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
#ifndef BC5_LEAN
	g_r438_early += found.size();
#endif
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
#ifndef BC5_LEAN
	for (const auto& w: lost) {
		const uint64_t k = g_r438_lost++;
		if (k < 200 || (k & 0xffu) == 0)
			journal("r438 (exp 0438, b438): BUG: the early-registered write of 0x%" PRIx64 " (value 0x%" PRIx64 ") of slice %" PRIu64 " never reached the ring (%" PRIu64 " so far)NL", w.label, w.value, t_r438_slice, k + 1);
	}
	static uint64_t last_line = 0;
	const uint64_t  now       = SoftCp::now_ns();
	if (last_line == 0) last_line = now;
	if (now - last_line > 60'000'000'000ull) {
		last_line = now;
		journal("r438 (exp 0438, b438): t %.1f s: slices %" PRIu64 ", early writes %" PRIu64 ", early writes that never reached the ring %" PRIu64 "; game-thread waits for an early writer %" PRIu64 ", %.1f ms in all, longest %.3f ms, bug lines (over 100 ms) %" PRIu64 "NL",
		        timing_now(), g_r438_slices.load(), g_r438_early.load(), g_r438_lost.load(), g_r438_waits.load(), static_cast<double>(g_r438_wait_ns.load()) / 1e6, static_cast<double>(g_r438_wait_max.load()) / 1e6, g_r438_long.load());
	}
#else
	if (!lost.empty() && g_r438_lost_lean.fetch_add(lost.size()) == 0)
		std::fprintf(stderr, "r438 (exp 0438, b438, lean): an early-registered write never reached the ring (the first; the total is printed at a normal exit)NL");
#endif
	if (r438_cv()) g_plw_cv.notify_all(); // PLWCV: the slice's early entries are gone
	t_r438_real.clear();
}
static void forget_label_writes(uint64_t seq, int ring, bool all) {'''.replace('NL', NL))

# 3b. PLWCV: the condition variable beside g_plw, signalled when a job registers its writes
rep('''static std::vector<PendingLabelWrite>      g_plw;''',
    '''static std::vector<PendingLabelWrite>      g_plw;
static std::condition_variable             g_plw_cv; // exp 0438 (b438, PLWCV): real writes registered or early ones gone''')
rep('''	g_plw.insert(g_plw.end(), found.begin(), found.end());
}
''', '''	g_plw.insert(g_plw.end(), found.begin(), found.end());
	if (r438_cv()) g_plw_cv.notify_all(); // exp 0438 (b438, PLWCV)
}
''')

# 4. F2/F4 need a real job: early entries are not theirs
rep('''			if (w.label == label && w.ring != ring && std::find(others.begin(), others.end(), std::make_pair(w.ring, w.seq)) == others.end()) others.emplace_back(w.ring, w.seq);''',
    '''			if (w.label == label && w.ring != ring && (w.seq & kR438Early) == 0 && std::find(others.begin(), others.end(), std::make_pair(w.ring, w.seq)) == others.end()) others.emplace_back(w.ring, w.seq); // exp 0438 (b438): no early entry''')

# 5. ring_will_satisfy: an early last write is polled on the game thread until it is real; others skip it
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
	for (uint64_t r438_t0 = 0, r438_rec = 0;;) { // exp 0438 (b438): an early last write is waited for on the game thread
		last = nullptr;
		for (const auto& w: g_plw) {
			if (w.label == a && (game || (w.seq & kR438Early) == 0) && (last == nullptr || w.order >= last->order)) last = &w;
		}
		if (last == nullptr || (last->seq & kR438Early) == 0) {
#ifndef BC5_LEAN
			if (r438_t0 != 0) {
				const uint64_t d = SoftCp::now_ns() - r438_t0;
				g_r438_waits++;
				g_r438_wait_ns += d;
				for (uint64_t m = g_r438_wait_max.load(); d > m && !g_r438_wait_max.compare_exchange_weak(m, d);) {
				}
			}
#endif
			break;
		}
		if (r438_t0 == 0) r438_t0 = SoftCp::now_ns();
#ifndef BC5_LEAN
		const uint64_t held = SoftCp::now_ns() - r438_t0;
		if (held >= 100'000'000ull * (r438_rec + 1) && r438_rec < 10) { // a bug line at 100 ms, 200 ms, ...; the wait goes on
			r438_rec++;
			g_r438_long++;
			lk.unlock();
			journal("r438 (exp 0438, b438): BUG: a game-thread wait on 0x%" PRIx64 " has waited %.1f ms for an early-registered writer to reach the ringNL", a, static_cast<double>(held) / 1e6);
			lk.lock();
			continue;
		}
#else
		(void)r438_rec;
#endif
		if (r438_cv()) { // PLWCV: sleep until a job registers its writes or the slice ends (10 ms bound per sleep)
			g_plw_cv.wait_for(lk, std::chrono::milliseconds(10));
		} else {
			lk.unlock();
			std::this_thread::sleep_for(std::chrono::microseconds(20));
			lk.lock();
		}
	}
	if (last == nullptr) return false;'''.replace('NL', NL))

# 6. the slice: early at the take, the end after chain_end
rep('''			Direct::chain_begin(); // ADR 0010: the slice's buffers as one submission
			if (w_take > r) {
				Direct::submit(ring + r, w_take - r, "ring");
			} else {
				Direct::submit(ring + r, n - r, "ring");
				if (w_take != 0) Direct::submit(ring, w_take, "ring");
			}
			Direct::chain_end();''', '''			if (w_take > r) Direct::r438_begin(ring + r, w_take - r, nullptr, 0); // exp 0438 (b438): the slice's writes, early
			else Direct::r438_begin(ring + r, n - r, ring, w_take);
			Direct::chain_begin(); // ADR 0010: the slice's buffers as one submission
			if (w_take > r) {
				Direct::submit(ring + r, w_take - r, "ring");
			} else {
				Direct::submit(ring + r, n - r, "ring");
				if (w_take != 0) Direct::submit(ring, w_take, "ring");
			}
			Direct::chain_end();
			Direct::r438_end(); // exp 0438 (b438): every early write must have reached the ring''')

# 7. p438: the prologue merge (definitions before gc_ioctl; the hooks in its cases and at the EOP flip)
rep('''// Returns 0 on success or a positive errno (the libkernel wrapper turns it into -1/errno).
static int gc_ioctl(uint64_t request, void* argp) {''', '''// BC5 experiment 0438 (tag p438): the prologue merge (BC5_0438_PROLMERGE, on unless "0").
namespace p438 {
struct Prol {
	uint32_t cc[3];
	uint32_t cmds[12];
};
inline std::mutex      g_m;
inline Prol            g_slots[64]; // stable storage: the soft CP may still read a submitted prologue's dwords later
inline uint32_t        g_next = 0;
inline std::vector<int> g_pending;  // slot indices, in call order
enum : int { kMerged, kAloneOther, kAloneIdle, kAloneFlip, kAloneWrites, kAloneMany, kAloneNoRings, kN };
#ifndef BC5_LEAN
inline std::atomic<uint64_t> g_n[kN] = {};
#endif
inline bool on() {
	static const bool v = [] {
		const char* e = std::getenv("BC5_0438_PROLMERGE");
		return !(e != nullptr && e[0] == '0' && e[1] == 0);
	}();
	return v;
}
inline void count(int k, uint64_t n = 1) {
#ifndef BC5_LEAN
	g_n[k] += n;
	static std::atomic<uint64_t> last {0};
	const uint64_t               t = SoftCp::now_ns();
	uint64_t                     l = last.load();
	if (l == 0) last = t;
	else if (t - l > 60'000'000'000ull && last.compare_exchange_strong(l, t))
		Direct::journal("p438 (exp 0438): t %.1f s: prologues merged %" PRIu64 "; alone: before another submit %" PRIu64 ", at done/idle %" PRIu64 ", at the flip %" PRIu64 ", writes memory or nests %" PRIu64 ", 8 pending %" PRIu64 ", acb rings off %" PRIu64 "NL",
		                Direct::timing_now(), g_n[kMerged].load(), g_n[kAloneOther].load(), g_n[kAloneIdle].load(), g_n[kAloneFlip].load(), g_n[kAloneWrites].load(), g_n[kAloneMany].load(), g_n[kAloneNoRings].load());
#else
	(void)k;
	(void)n;
#endif
}
// a header IB that writes memory (RELEASE_MEM, EVENT_WRITE_EOP, WRITE_DATA, DMA_DATA) or nests an IB
inline bool writes(const uint32_t* pkt) {
	if (pkt[0] == 0) return false;
	const auto*    ib = reinterpret_cast<const uint32_t*>((static_cast<uint64_t>(pkt[2]) << 32u) | pkt[1]);
	const uint32_t n  = pkt[3] & 0xfffffu;
	for (uint32_t q = 0; q < n;) {
		const uint32_t h   = ib[q];
		uint32_t       len = 1;
		if ((h >> 30u) == 3 || (h >> 30u) == 0) {
			const uint32_t c = (h >> 16u) & 0x3fffu;
			len              = c == 0x3fffu ? 1 : c + 2;
		}
		if ((h >> 30u) == 3) {
			const uint32_t op = (h >> 8u) & 0xffu;
			if (op == 0x49 || op == 0x47 || op == 0x37 || op == 0x50 || op == 0x3f || op == 0x33) return true;
		}
		q += len;
	}
	return false;
}
} // namespace p438
static void p438_submit(const p438::Prol& p) { // today's header submission, packet for packet
	submit_raw(p.cc, 3, "cc");
	for (int i = 0; i < 3; i++) submit_ib_packet(p.cmds + i * 4, "hib");
}
// the pending prologues, each as today's own submission, before whatever comes next
static void p438_flush_alone(int why) {
	std::vector<int> take;
	{
		std::lock_guard lk(p438::g_m);
		take.swap(p438::g_pending);
	}
	for (const int i: take) {
		Direct::chain_begin();
		p438_submit(p438::g_slots[i]);
		Direct::chain_end();
		soft_posts_end();
	}
	if (!take.empty()) p438::count(why, take.size());
}
// 0xc0488131: true when the prologue was kept for the next 0xc0188132
static bool p438_defer(const uint32_t* cc, const uint32_t* cmds) {
	if (!p438::on()) return false;
	int why = -1;
	if (Direct::w428_rings() == 0) why = p438::kAloneNoRings;
	for (int i = 0; why < 0 && i < 3; i++)
		if (p438::writes(cmds + i * 4)) why = p438::kAloneWrites;
	if (why < 0) {
		std::lock_guard lk(p438::g_m);
		if (p438::g_pending.size() < 8) {
			const int k = static_cast<int>(p438::g_next++ % 64);
			std::memcpy(p438::g_slots[k].cc, cc, sizeof(p438::g_slots[k].cc));
			std::memcpy(p438::g_slots[k].cmds, cmds, sizeof(p438::g_slots[k].cmds));
			p438::g_pending.push_back(k);
			return true;
		}
		why = p438::kAloneMany;
	}
	p438_flush_alone(why); // the earlier ones first, as today's order
	p438::count(why);
	return false;
}
// 0xc0188132, inside its chain, before its DCBs
static void p438_take_into_chain() {
	std::vector<int> take;
	{
		std::lock_guard lk(p438::g_m);
		take.swap(p438::g_pending);
	}
	for (const int i: take) p438_submit(p438::g_slots[i]);
	if (!take.empty()) p438::count(p438::kMerged, take.size());
}

// Returns 0 on success or a positive errno (the libkernel wrapper turns it into -1/errno).
static int gc_ioctl(uint64_t request, void* argp) {'''.replace('NL', chr(92) + 'n'))
rep('''			Direct::chain_begin(); // ADR 0010: the header's buffers as one submission
			submit_raw(a->context_control, 3, "cc");''', '''			if (p438_defer(a->context_control, a->cmds)) { // exp 0438 (p438): kept for the next submit list's chain
				a->status = 0;
				return 0;
			}
			Direct::chain_begin(); // ADR 0010: the header's buffers as one submission
			submit_raw(a->context_control, 3, "cc");''')
rep('''			Direct::chain_begin(); // ADR 0010
			for (uint32_t i = 0; i < a->count / 2; i++) {''', '''			Direct::chain_begin(); // ADR 0010
			p438_take_into_chain(); // exp 0438 (p438): the pending prologues at the head of this chain
			for (uint32_t i = 0; i < a->count / 2; i++) {''')
rep('''		case 0xc0108102: { // submit: count x IB packet
''', '''		case 0xc0108102: { // submit: count x IB packet
			p438_flush_alone(p438::kAloneOther); // exp 0438 (p438)
''')
rep('''		case 0xc020810c: { // submit and write eop
''', '''		case 0xc020810c: { // submit and write eop
			p438_flush_alone(p438::kAloneOther); // exp 0438 (p438)
''')
rep('''		case 0xc0048117: { // wait idle
''', '''		case 0xc0048117: { // wait idle
			p438_flush_alone(p438::kAloneIdle); // exp 0438 (p438)
''')
rep('''	if (!defer) Bc5Gc::Direct::drain(); // nothing of the frame may still be in flight''',
    '''	Bc5Gc::p438_flush_alone(Bc5Gc::p438::kAloneFlip); // exp 0438 (p438): a pending prologue goes before the flip, as today
	if (!defer) Bc5Gc::Direct::drain(); // nothing of the frame may still be in flight''')

out = s.encode('utf-8')
open(OUT, 'wb', ).write(out)
print('b438 unit', hashlib.md5(out).hexdigest(), len(out))
