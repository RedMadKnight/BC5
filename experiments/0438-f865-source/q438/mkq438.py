#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""BC5 experiment 0438 (tag q438): the per-slot submit queue, switch BC5_0438_SUBMITQ (on only when "1").
Usage: python -I mkq438.py IN.cpp OUT.cpp   (IN: the bake unit, md5 ff9e8fe2e4139264ebaf74f9e84bd892, or A2's host
       unit ../a2host.cpp, md5 0402a183e527bca6d1d27b5d02bc0c38; the same exact-once replacements on either)
Design: README.md "The per-slot submit queue (design, not built; for every title)" and q438/README-q438.md.
Edits, each an exact-once replacement in IN:
  E1 the switch q438_on(), t_q438_on / t_q438_real and kQ438Early, beside r438's state;
  E2 register_label_writes records the labels a queued entry's submission registered (t_q438_on), as r438 does;
  E2b and, switch on, renumbers queued chains' early writes of the labels it registers after them (ring order);
  E3 Q438Entry / Q438Tail and the queue's members in ChainSlot;
  E4 q438_busy_locked (chain_post_soft_locked defers while the slot's queue holds an entry), q438_flight_gone, the
     forward declarations;
  E5 chain_submit: with the switch on, async mode and a registered slot, q438_submit instead of today's body;
  E6 ~ChainSlot: the submitter drains and stops first (switch on);
  E7 the q438 block after forget_label_writes: early registration, the submitter thread, push, nested, drain wait;
  E9 g_plw's two trims keep early entries (switch on; inserted before today's trim line, which then has nothing to do);
  E8 F16's waiter (ho430::f10_observe): with the switch on, a bump counts only once the label left the flight union.
With the switch off every inserted branch is skipped; E8's predicate reduces to today's.
Writes OUT (LF) and prints both md5s.
"""
import hashlib
import sys

IN, OUT = sys.argv[1], sys.argv[2]
src = open(IN, 'rb').read()
INPUTS = {'ff9e8fe2e4139264ebaf74f9e84bd892': 'the bake unit', '0402a183e527bca6d1d27b5d02bc0c38': "A2's host unit (a2/mka2host.py on the bake unit)"}
assert hashlib.md5(src).hexdigest() in INPUTS, 'not the bake unit (ff9e8fe2) or A2\'s host unit (0402a183)'
print('input:', INPUTS[hashlib.md5(src).hexdigest()])
s = src.decode('utf-8')
assert '\r' not in s


def rep(old, new):
    global s
    n = s.count(old)
    assert n == 1, f'{n} matches for: {old[:90]!r}'
    s = s.replace(old, new)


# E1
rep('static thread_local std::vector<uint64_t> t_r438_real;              // the labels the slice\'s jobs registered for real\n',
    'static thread_local std::vector<uint64_t> t_r438_real;              // the labels the slice\'s jobs registered for real\n'
    '// BC5 experiment 0438 (tag q438): the per-slot submit queue, BC5_0438_SUBMITQ, on only when "1" (defined with ChainSlot).\n'
    'static constexpr uint64_t                 kQ438Early = kR438Early | (1ull << 62u); // a queued chain\'s early entries: seq = kQ438Early | id\n'
    'static thread_local bool                  t_q438_on = false; // this thread runs a queued entry\'s submit_now\n'
    'static thread_local std::vector<uint64_t> t_q438_real;       // the labels that submission registered for real\n'
    'static thread_local uint64_t              t_q438_early = 0;  // that entry\'s own early id (it is not reordered by its own writes)\n'
    'static bool q438_on() {\n'
    '\tstatic const bool v = [] {\n'
    '\t\tconst char* e = std::getenv("BC5_0438_SUBMITQ");\n'
    '\t\treturn e != nullptr && e[0] == \'1\' && e[1] == 0;\n'
    '\t}();\n'
    '\treturn v;\n'
    '}\n')

# E2
rep('\tif (t_r438_on_slice) for (const auto& w: found) t_r438_real.push_back(w.label); // exp 0438 (b438): what this slice\'s jobs registered\n',
    '\tif (t_r438_on_slice) for (const auto& w: found) t_r438_real.push_back(w.label); // exp 0438 (b438): what this slice\'s jobs registered\n'
    '\tif (t_q438_on) for (const auto& w: found) t_q438_real.push_back(w.label); // exp 0438 (q438): what the queued entry registered\n')
# E2b: ring order. A queued chain's early writes are not in the kernel yet, so they stay after every real write of their
# label registered later (an earlier entry of the slot, another slot, bc5-ring); without this the later real write's
# order passes them and ring_will_satisfy takes an older value for the last one (Codex's review: 3 of 11 random runs).
rep('\tg_plw.insert(g_plw.end(), found.begin(), found.end());\n\tif (r438_cv()) g_plw_cv.notify_all(); // exp 0438 (b438, PLWCV)\n',
    '\tg_plw.insert(g_plw.end(), found.begin(), found.end());\n'
    '\tif (q438_on()) { // exp 0438 (q438): queued chains\' early writes of these labels stay last, in their own order\n'
    '\t\tstd::vector<PendingLabelWrite*> early;\n'
    '\t\tfor (auto& w: g_plw)\n'
    '\t\t\tif ((w.seq & kQ438Early) == kQ438Early && w.seq != t_q438_early && std::any_of(found.begin(), found.end(), [&w](const PendingLabelWrite& f) { return f.label == w.label; })) early.push_back(&w);\n'
    '\t\tstd::sort(early.begin(), early.end(), [](const PendingLabelWrite* a, const PendingLabelWrite* b) { return a->order < b->order; });\n'
    '\t\tfor (PendingLabelWrite* w: early) w->order = ++order;\n'
    '\t}\n'
    '\tif (r438_cv()) g_plw_cv.notify_all(); // exp 0438 (b438, PLWCV)\n')
# E9: g_plw's trim (8192 entries, the oldest 4096 go by position) dropped early entries too: a queued chain's writer, not
# in the kernel yet, then read as "no pending write". With the switch on the oldest 4096 real entries go and early
# entries stay; today's trim line after it then finds nothing to do (insertion only). Off: skipped.
rep('static std::condition_variable             g_plw_cv; // exp 0438 (b438, PLWCV): real writes registered or early ones gone\n',
    'static std::condition_variable             g_plw_cv; // exp 0438 (b438, PLWCV): real writes registered or early ones gone\n'
    'static std::atomic<uint64_t>               g_q438_trims {0}; // exp 0438 (q438): trims that kept early entries\n'
    'static void q438_plw_trim_locked() { // exp 0438 (q438), caller holds g_plw_mutex: the trim keeps early entries (not in the kernel yet)\n'
    '\tif (!q438_on() || g_plw.size() <= 8192) return;\n'
    '\tstd::vector<PendingLabelWrite> kept;\n'
    '\tkept.reserve(g_plw.size());\n'
    '\tsize_t gone = 0;\n'
    '\tfor (const auto& w: g_plw) {\n'
    '\t\tif (gone < 4096 && (w.seq & kR438Early) == 0) {\n'
    '\t\t\tgone++;\n'
    '\t\t\tcontinue;\n'
    '\t\t}\n'
    '\t\tkept.push_back(w);\n'
    '\t}\n'
    '\tg_plw.swap(kept);\n'
    '\tg_q438_trims++;\n'
    '}\n'
    '// ---- end of exp 0438 (q438) g_plw trim\n')
rep('\t\tw.order = ++order;\n\t}\n\tif (g_plw.size() > 8192) g_plw.erase(g_plw.begin(), g_plw.begin() + 4096);\n',
    '\t\tw.order = ++order;\n\t}\n\tq438_plw_trim_locked(); // exp 0438 (q438)\n\tif (g_plw.size() > 8192) g_plw.erase(g_plw.begin(), g_plw.begin() + 4096);\n')
rep('\t\tw.order = ++g_plw_order;\n\t}\n\tif (g_plw.size() > 8192) g_plw.erase(g_plw.begin(), g_plw.begin() + 4096);\n',
    '\t\tw.order = ++g_plw_order;\n\t}\n\tq438_plw_trim_locked(); // exp 0438 (q438)\n\tif (g_plw.size() > 8192) g_plw.erase(g_plw.begin(), g_plw.begin() + 4096);\n')

# E3
rep('struct ChainSlot {\n\tChain                        c;\n',
    '// exp 0438 (tag q438): one taken chain in its slot\'s queue, with what submit_now and chain_submit\'s tail need.\n'
    'struct Q438Entry {\n'
    '\tChain                 c;\n'
    '\tstd::vector<uint64_t> f10;           // its F10 write set (part of the slot\'s flight union until its tail)\n'
    '\tint                   why     = -1;   // fs415: why it was flushed\n'
    '\tuint64_t              fs_open = 0;    // fs415: when its first segment was appended\n'
    '\tuint32_t              segs    = 0;    // fs415: its segments\n'
    '\tuint64_t              ticket  = 0;    // take order in the slot (bit 63: a nested inline take)\n'
    '\tuint64_t              early   = 0;    // the seq of its early entries in g_plw (0: none)\n'
    '\tint                   qidx    = -1;   // the pushing thread\'s t_queue_idx\n'
    '};\n'
    'struct Q438Tail { // what chain_submit\'s tail does after submit_now, applied by the submitter under the slot\'s mu\n'
    '\tuint64_t                     ticket = 0;\n'
    '\tstd::vector<SoftCp::GpuDone> marks;\n'
    '\tbool                         counted = false; // a queued entry (q_done counts it), not a nested one\n'
    '};\n'
    'struct ChainSlot {\n\tChain                        c;\n')
rep('\tstd::atomic<int>             f16_phase {0}; // exp 0430 F16: 0 idle, 1 in chain_submit before the device lock (back-pressure), 2 asking for g_dev_mutex, 3 holding it, 4 draining the GPU (wait_jobs)\n\t~ChainSlot();\n',
    '\tstd::atomic<int>             f16_phase {0}; // exp 0430 F16: 0 idle, 1 in chain_submit before the device lock (back-pressure), 2 asking for g_dev_mutex, 3 holding it, 4 draining the GPU (wait_jobs)\n'
    '\t// exp 0438 (tag q438, BC5_0438_SUBMITQ=1): the slot\'s FIFO of taken chains and its one submitter thread\n'
    '\tstd::mutex                   q_mu; // q, q_taken, q_done, q_applying, q_running, q_stop (lock order: mu, then q_mu)\n'
    '\tstd::condition_variable      q_cv; // an entry for the submitter, space, entries done\n'
    '\tstd::deque<Q438Entry>        q;\n'
    '\tuint64_t                     q_taken = 0, q_done = 0, q_applying = 0; // pushed; tails applied; tails being applied now\n'
    '\tbool                         q_running = false, q_stop = false;\n'
    '\tbool                         q_started = false; // under mu and q_mu: the submitter thread exists\n'
    '\tstd::thread                  q_thr;\n'
    '\tstd::vector<std::pair<uint64_t, std::vector<uint64_t>>> q_sets; // under mu: the entries\' F10 write sets; f10_flight is their union\n'
    '\tstd::vector<Q438Tail>        q_tails;      // the submitter thread\'s own: tails waiting for mu\n'
    '\tuint64_t                     q_nested = 0; // the submitter thread\'s own: nested inline takes\n'
    '\t~ChainSlot();\n')

# E4
rep('static void chain_post_soft_locked(ChainSlot& s) {\n\tif (s.soft.empty()) return;\n',
    '// exp 0438 (tag q438): a queued or in-flight entry whose tail is not applied yet holds the replays back (caller holds s.mu)\n'
    'static bool q438_busy_locked(ChainSlot& s) {\n'
    '\tif (!s.q_started) return false;\n'
    '\tstd::lock_guard ql(s.q_mu);\n'
    '\treturn s.q_taken != s.q_done + s.q_applying;\n'
    '}\n'
    '// exp 0438 (tag q438): F16\'s waiter: the label left the slot\'s flight union (false while the slot is busy)\n'
    'static bool q438_flight_gone(ChainSlot* cs, uint64_t label) {\n'
    '\tif (!cs->mu.try_lock()) return false;\n'
    '\tconst bool in = std::find(cs->f10_flight.begin(), cs->f10_flight.end(), label) != cs->f10_flight.end();\n'
    '\tcs->mu.unlock();\n'
    '\treturn !in;\n'
    '}\n'
    'static void q438_submit(ChainSlot& s, int why, bool foreign); // exp 0438 (tag q438), defined after forget_label_writes\n'
    'static void q438_stop(ChainSlot& s);\n'
    'static void chain_post_soft_locked(ChainSlot& s) {\n\tif (s.soft.empty()) return;\n'
    '\tif (q438_busy_locked(s)) return; // exp 0438 (q438): posted by the submitter after the entry\'s tail\n')

# E5
rep('static void chain_submit(ChainSlot& s, int why, bool foreign) {\n',
    'static void chain_submit(ChainSlot& s, int why, bool foreign) {\n'
    '\tif (q438_on() && g_async && s.registered) { // exp 0438 (q438): pushed to the slot\'s queue; sync mode keeps today\'s path\n'
    '\t\tq438_submit(s, why, foreign);\n'
    '\t\treturn;\n'
    '\t}\n')

# E6
rep('ChainSlot::~ChainSlot() {\n\tif (!registered) return;\n',
    'ChainSlot::~ChainSlot() {\n\tif (!registered) return;\n'
    '\tif (q438_on()) q438_stop(*this); // exp 0438 (q438): out of g_chains, then the submitter drains its queue and stops\n')

# E7
Q438 = r'''

// ---- BC5 experiment 0438 (tag q438): the per-slot submit queue (BC5_0438_SUBMITQ=1) ------------------------------------
// The README's "The per-slot submit queue". A registered (cross) slot's chain_submit takes the chain under s.mu as before and
// pushes it, in take order, to the slot's FIFO (at most kQ438Cap); one submitter thread per slot runs exactly today's
// submit_now and chain_submit's tail for each entry in that order. The owner, the watchdog and flush_all only push. They
// wait only: for space; at a drain (why 5: the flip's chain_flush / chain_flush_all, wait_jobs, d432) and an observe
// point (why 8: the title asks about the GPU, "wait idle" must not find a queued chain) until the slot's queue is empty and
// its last tail applied. A queued chain's label writes are registered early at the push, under s.mu (kQ438Early | id):
// r438's game-thread rule in ring_will_satisfy waits for the real registration; at the entry's end an early write not
// registered for real is a BUG line and is removed (r438's invariant). The submitter never blocks on s.mu between entries
// (a thread in hold_release may hold it while it waits for a queued entry's early writer): tails wait in q_tails.
static constexpr size_t      kQ438Cap = 4;
static thread_local ChainSlot* t_q438_slot = nullptr; // the slot whose submitter this thread is
static std::atomic<uint64_t> g_q438_ids {0}, g_q438_threads {0}, g_q438_lost {0}, g_q438_pushed {0}, g_q438_nested {0}, g_q438_nested_skip {0}, g_q438_full {0};
// The chain's label writes at every top-level packet, as register_label_writes reads them (its executed offsets are not
// known before the filter).
static void q438_scan(const std::vector<uint32_t>& b, std::vector<PendingLabelWrite>& out) {
	const uint32_t n = static_cast<uint32_t>(b.size());
	for (uint32_t q = 0; q < n;) {
		const uint32_t* w   = b.data() + q;
		const uint32_t  h   = w[0];
		uint32_t        len = 1;
		if ((h >> 30u) == 3 || (h >> 30u) == 0) {
			const uint32_t c = (h >> 16u) & 0x3fffu;
			len              = c == 0x3fffu ? 1 : c + 2;
		}
		if (q + len > n) break;
		const uint32_t op = (h >> 8u) & 0xffu;
		auto addr = [w](int lo, int hi) { return (static_cast<uint64_t>(w[lo]) & ~3ull) | (static_cast<uint64_t>(w[hi] & 0xffffu) << 32u); };
		if ((h >> 30u) == 3) {
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
// At the push, under s.mu: no thread sees the chain gone from the slot before its writes are pending.
static uint64_t q438_early_begin(const Chain& c) {
	std::vector<PendingLabelWrite> found;
	q438_scan(c.buf, found);
	if (found.empty()) return 0;
	const uint64_t id = kQ438Early | (g_q438_ids.fetch_add(1) + 1);
	std::lock_guard lk(g_plw_mutex);
	for (auto& w: found) {
		w.seq   = id;
		w.ring  = c.ring;
		w.order = ++g_plw_order;
	}
	q438_plw_trim_locked();
	if (g_plw.size() > 8192) g_plw.erase(g_plw.begin(), g_plw.begin() + 4096);
	g_plw.insert(g_plw.end(), found.begin(), found.end());
	return id;
}
// The entry's end, on the submitter after its submit_now: every early write must have been registered for real.
static void q438_early_end(uint64_t id) {
	if (id == 0) return;
	std::vector<PendingLabelWrite> lost;
	{
		std::lock_guard lk(g_plw_mutex);
		for (auto it = g_plw.begin(); it != g_plw.end();) {
			if (it->seq == id) {
				if (std::find(t_q438_real.begin(), t_q438_real.end(), it->label) == t_q438_real.end()) lost.push_back(*it);
				it = g_plw.erase(it);
			} else {
				++it;
			}
		}
	}
	for (const auto& w: lost) {
		const uint64_t k = g_q438_lost++;
#ifndef BC5_LEAN
		if (k < 200 || (k & 0xffu) == 0)
			journal("q438 (exp 0438): BUG: the early-registered write of 0x%" PRIx64 " (value 0x%" PRIx64 ") of a queued chain never reached the ring (%" PRIu64 " so far)\n", w.label, w.value, k + 1);
#else
		(void)k;
		(void)w;
#endif
	}
	if (r438_cv()) g_plw_cv.notify_all(); // PLWCV: the entry's early entries are gone
}
static void q438_flight_locked(ChainSlot& s) { // caller holds s.mu: f10_flight = the union of the entries' write sets
	s.f10_flight.clear();
	for (const auto& e: s.q_sets) s.f10_flight.insert(s.f10_flight.end(), e.second.begin(), e.second.end());
}
// chain_submit's tail for the entries done: their flight sets go, f16_done per entry, the cross marks, the replays.
// Submitter only; block: wait for s.mu (only at the stop), else try.
static bool q438_apply_tails(ChainSlot& s, bool block) {
	if (s.q_tails.empty()) return true;
	std::unique_lock lk(s.mu, std::defer_lock);
	if (block) lk.lock();
	else if (!lk.try_lock()) return false;
	std::vector<Q438Tail> tails;
	tails.swap(s.q_tails);
	uint64_t counted = 0;
	for (const auto& t: tails) {
		std::erase_if(s.q_sets, [&t](const std::pair<uint64_t, std::vector<uint64_t>>& e) { return e.first == t.ticket; });
		if (t.counted) counted++;
	}
	q438_flight_locked(s); // exp 0430 F10: its writes are registered now
	s.f16_done.fetch_add(tails.size()); // exp 0430 F16: after the clear, per entry
	{
		std::lock_guard ql(s.q_mu);
		s.q_applying = counted;
	}
	if (s.cross) { // section B.4, as chain_submit's tail
		for (auto& t: tails) s.marks.insert(s.marks.end(), t.marks.begin(), t.marks.end());
		if (s.c.segs.empty() && !s.in_submit) chain_post_soft_locked(s);
	}
	{
		std::lock_guard ql(s.q_mu);
		s.q_applying = 0;
		s.q_done += counted;
	}
	lk.unlock();
	s.q_cv.notify_all();
	return true;
}
// One entry, exactly today's submit_now with the thread-locals chain_submit set for it. A nested flush on this thread
// (submit_now's mapping sync -> wait_jobs -> chain_flush ...) finds s.flush_mu its own, as today.
static void q438_run(ChainSlot& s, Q438Entry& e, bool counted) {
	std::lock_guard order(s.flush_mu);
	t_fs415_open_ns = e.fs_open; // experiment 0415 (fs415c)
	t_fs415_why     = e.why;
	t_fs415_segs    = e.segs;
	const int qidx  = t_queue_idx;
	t_queue_idx     = e.qidx;
	ChainSlot* const f16_prev = t_f16_slot; // exp 0430 F16
	t_f16_slot = &s;
	s.f16_phase.store(1);
	const bool outer = !t_q438_on;
	if (outer) t_q438_real.clear();
	t_q438_on = true;
	const uint64_t early_prev = t_q438_early;
	t_q438_early              = e.early;
	submit_now(e.c.buf.data(), static_cast<uint32_t>(e.c.buf.size()), e.c.compute ? "acb" : "dcb", e.c.ring, &e.c);
	t_q438_early = early_prev;
	t_q438_on    = !outer;
	s.f16_phase.store(0);
	t_f16_slot  = f16_prev;
	t_queue_idx = qidx;
	q438_early_end(e.early);
	if (outer) t_q438_real.clear();
	s.q_tails.push_back({e.ticket, std::move(SoftCp::t_gpu_done), counted});
	SoftCp::t_gpu_done.clear();
}
static void q438_thread(ChainSlot* sp) {
	ChainSlot& s = *sp;
	pthread_setname_np(pthread_self(), "bc5-submitq");
	t_q438_slot = &s;
	g_q438_threads++;
	for (;;) {
		q438_apply_tails(s, false);
		const bool tails = !s.q_tails.empty();
		Q438Entry  e;
		bool       have = false, stop = false;
		{
			std::unique_lock ql(s.q_mu);
			const auto ready = [&s] { return !s.q.empty() || s.q_stop; };
			if (tails) s.q_cv.wait_for(ql, std::chrono::microseconds(50), ready);
			else s.q_cv.wait(ql, ready);
			if (!s.q.empty()) {
				e = std::move(s.q.front());
				s.q.pop_front();
				s.q_running = true;
				have        = true;
			} else {
				stop = s.q_stop;
			}
		}
		if (have) {
			s.q_cv.notify_all(); // space
			q438_run(s, e, true);
			{
				std::lock_guard ql(s.q_mu);
				s.q_running = false;
			}
			continue;
		}
		if (stop) {
			q438_apply_tails(s, true);
			break;
		}
	}
	g_q438_threads--;
	t_q438_slot = nullptr;
}
static void q438_count(const Q438Entry& e, int why) { // chain_submit's counters and its 10-s line
	g_chain_flushes++;
	g_chain_segments += e.c.segs.size();
	g_chain_dwords += e.c.buf.size();
	if (e.c.segs.size() == 1) g_chain_single++;
	g_chain_why[why < 12 ? why : 7]++;
	static double last = 0;
	const double  now  = timing_now();
	if (now - last >= 10.0) {
		last = now;
		journal("chains: %" PRIu64 " submitted, %" PRIu64 " segments (%" PRIu64 " single, %" PRIu64 " with cond_exec), %" PRIu64 " dwords; closed by: end %" PRIu64 " wait %" PRIu64 " ring/class %" PRIu64 " cond_exec %" PRIu64 " size %" PRIu64 " drain %" PRIu64 " acb-head %" PRIu64 " other %" PRIu64 " observe %" PRIu64 " hold-wd %" PRIu64 " hold-end %" PRIu64 "; q438 pushed %" PRIu64 " (full waits %" PRIu64 "), nested %" PRIu64 " (skipped %" PRIu64 "), early writes lost %" PRIu64 "\n",
		        g_chain_flushes.load(), g_chain_segments.load(), g_chain_single.load(), g_chain_cond_segs.load(), g_chain_dwords.load(), g_chain_why[0].load(), g_chain_why[1].load(),
		        g_chain_why[2].load(), g_chain_why[3].load(), g_chain_why[4].load(), g_chain_why[5].load(), g_chain_why[6].load(), g_chain_why[7].load(), g_chain_why[8].load(),
		        g_chain_why[9].load(), g_chain_why[10].load(), g_q438_pushed.load(), g_q438_full.load(), g_q438_nested.load(), g_q438_nested_skip.load(), g_q438_lost.load());
	}
}
// The take of chain_submit (caller holds s.mu), into e.
static void q438_take_locked(ChainSlot& s, Q438Entry& e, int why) {
	Chain& c = s.c;
	e.c.buf.swap(c.buf);
	e.c.segs.swap(c.segs);
	e.c.ring    = c.ring;
	e.c.compute = c.compute;
	e.fs_open   = s.open_ns;
	s.open_ns   = 0;
	s.hold_writes.clear(); // ADR 0013
	e.f10.swap(s.f10_writes); // exp 0430 F10: in flight until the entry's tail
	s.f10_writes.clear();
	s.f10_wanted = false;
	e.why        = why;
	e.segs       = static_cast<uint32_t>(e.c.segs.size());
	e.qidx       = t_queue_idx;
}
// Push: take (under s.mu) and append to the FIFO (under q_mu) in one step, so take order is queue order. Waits for space.
static bool q438_push(ChainSlot& s, int why, bool foreign) {
	for (bool waited = false;;) {
		{
			std::unique_lock ql(s.q_mu);
			if (s.q.size() >= kQ438Cap && !waited) {
				waited = true;
				g_q438_full++;
			}
			s.q_cv.wait(ql, [&s] { return s.q.size() < kQ438Cap; });
		}
		Q438Entry e;
		{
			std::lock_guard lk(s.mu);
			if (s.c.segs.empty() || (foreign && s.in_submit)) return false;
			std::unique_lock ql(s.q_mu);
			if (s.q.size() >= kQ438Cap) continue; // another pusher took the space
			q438_take_locked(s, e, why);
			e.ticket = ++s.q_taken;
			s.q_sets.emplace_back(e.ticket, e.f10);
			q438_flight_locked(s);
			e.early = q438_early_begin(e.c);
			q438_count(e, why);
			if (!s.q_started) {
				s.q_started = true;
				s.q_thr     = std::thread(q438_thread, &s);
			}
			s.q.push_back(std::move(e));
			g_q438_pushed++;
		}
		s.q_cv.notify_all();
		return true;
	}
}
// On the slot's own submitter, inside an entry's submit_now: the chain goes inline, ahead of the queue (today's recursive
// flush_mu). s.mu is only tried: a thread may hold it while it waits for the outer entry's early writer.
static void q438_nested(ChainSlot& s, int why, bool foreign) {
	std::lock_guard order(s.flush_mu); // this thread's own
	Q438Entry       e;
	{
		std::unique_lock lk(s.mu, std::try_to_lock);
		if (!lk.owns_lock()) {
			g_q438_nested_skip++;
			return;
		}
		if (s.c.segs.empty() || (foreign && s.in_submit)) return;
		if (!s.hold.empty()) { // ADR 0013: left to the hold (hold_release would need s.mu)
			g_q438_nested_skip++;
			return;
		}
		q438_take_locked(s, e, why);
		e.ticket = (1ull << 63u) | ++s.q_nested;
		s.q_sets.emplace_back(e.ticket, e.f10);
		q438_flight_locked(s);
		q438_count(e, why);
	}
	g_q438_nested++;
	q438_run(s, e, false);
}
static void q438_wait_done(ChainSlot& s) {
	std::unique_lock ql(s.q_mu);
	s.q_cv.wait(ql, [&s] { return s.q_taken == s.q_done; });
}
static void q438_submit(ChainSlot& s, int why, bool foreign) {
	if (t_q438_slot == &s) {
		q438_nested(s, why, foreign);
		return;
	}
	bool any = false;
	{
		std::lock_guard lk(s.mu);
		any = !s.c.segs.empty() && !(foreign && s.in_submit);
	}
	if (any && hold_release(s, !(foreign && (why == 9 || why == 11)))) q438_push(s, why, foreign); // ADR 0013 (experiment 0226)
	if (why == 5 || why == 8) q438_wait_done(s); // the drain and the observe points: every taken chain submitted
}
static void q438_stop(ChainSlot& s) {
	{
		std::lock_guard lk(g_chains_mu);
		std::erase(g_chains, &s); // no new foreign push
	}
	{
		std::lock_guard ql(s.q_mu);
		s.q_stop = true;
	}
	s.q_cv.notify_all();
	if (s.q_thr.joinable()) s.q_thr.join(); // the queue drained, the tails applied
}
// ---- end of exp 0438 (tag q438) -------------------------------------------------------------------------------------------'''
rep('\n\n// Experiment 0401 series e11 (tag m11): the label writes the jobs in flight had pending at a timeout',
    Q438 + '\n\n// Experiment 0401 series e11 (tag m11): the label writes the jobs in flight had pending at a timeout')

# E8
rep('\t\t\t\t\tstd::erase_if(fl, [](const W& w) { return std::find(g_f10_reg.begin(), g_f10_reg.end(), w.cs) == g_f10_reg.end() || w.cs->f16_done.load() != w.done; });\n',
    '\t\t\t\t\tstd::erase_if(fl, [label](const W& w) { return std::find(g_f10_reg.begin(), g_f10_reg.end(), w.cs) == g_f10_reg.end() || (w.cs->f16_done.load() != w.done && (!q438_on() || q438_flight_gone(w.cs, label))); }); // exp 0438 (q438): per entry\n')

out = s.encode('utf-8')
open(OUT, 'wb').write(out)
print('IN ', hashlib.md5(src).hexdigest(), IN)
print('OUT', hashlib.md5(out).hexdigest(), OUT, f'({s.count(chr(10))} lines)')
