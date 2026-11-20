#!/usr/bin/env python3
"""BC5 experiment 0438 (tag w438): the doorbell watcher and one submitter thread per guest queue, woken by the
title's kick. On top of the r438 + c438 + c438d unit.

Usage: mkw438.py IN.cpp OUT.cpp   (IN: mkc438d.py's output on r438.cpp)

Switches (behaviour, so in lean too):
  BC5_0438_WATCHER  on in this test build unless "0": bc5-ring becomes a watcher ("bc5-dbw") that only reads the
                    queues' write pointers and hands each moved queue to its own submitter ("bc5-rq<N>"), which runs
                    today's consumer body for that queue alone. "0": today's single bc5-ring.
  BC5_0438_KICK     on unless "0" (and only with the watcher): /dev/gc 0xc010811c (the title's "ding dong" kick) wakes
                    the watcher at once instead of at its next 50 us look.
The hand-over (namespace w438) is self-contained so that test_w438.sh can cut it out and test it.
"""
import hashlib
import sys

IN, OUT = sys.argv[1], sys.argv[2]
src = open(IN, 'rb').read()
s = src.decode('utf-8')


def rep(old, new, count=1):
    global s
    n = s.count(old)
    assert n == count, (n, old[:120])
    s = s.replace(old, new)


# 1. the hand-over, before namespace SoftCp's consumer (in Bc5Gc, next to QueueReg)
rep('''static std::vector<QueueReg> g_queues;
''', '''static std::vector<QueueReg> g_queues;
// BC5 experiment 0438 (tag w438): the doorbell watcher's hand-over to one submitter per guest queue. Self-contained (cut
// out by test_w438.sh). A submitter waits on its slot until the watcher bumps the slot's sequence (a pointer move it
// saw) or its own timeout passes (a deferred head is retried). The kick bumps the watcher's own sequence.
namespace w438 {
inline bool on() {
	static const bool v = [] {
		const char* e = std::getenv("BC5_0438_WATCHER");
		return !(e != nullptr && e[0] == '0' && e[1] == 0);
	}();
	return v;
}
inline bool kick_on() {
	static const bool v = [] {
		const char* e = std::getenv("BC5_0438_KICK");
		return on() && !(e != nullptr && e[0] == '0' && e[1] == 0);
	}();
	return v;
}
constexpr int kSlots = 128;
struct Slot {
	std::mutex              m;
	std::condition_variable cv;
	uint64_t                seq     = 0;     // bumped by the watcher at a move it saw
	bool                    started = false; // a submitter runs for this queue
	uint64_t                last_w  = ~0ull; // the watcher's last read of the pointer
};
inline Slot* slots() {
	static Slot s[kSlots];
	return s;
}
inline std::mutex& wmu() {
	static std::mutex m;
	return m;
}
inline std::condition_variable& wcv() {
	static std::condition_variable c;
	return c;
}
inline uint64_t& wseq() { // the kicks so far, under wmu()
	static uint64_t v = 0;
	return v;
}
inline std::atomic<uint64_t>& g_handoffs() {
	static std::atomic<uint64_t> v {0};
	return v;
}
inline std::atomic<uint64_t>& g_kick_wakes() {
	static std::atomic<uint64_t> v {0};
	return v;
}
// The watcher: a queue's pointer read now. True when it moved since the watcher's last read (the submitter is woken).
inline bool observe(int idx, uint64_t w) {
	if (idx < 0 || idx >= kSlots) return false;
	Slot& sl = slots()[idx];
	{
		std::lock_guard l(sl.m);
		if (sl.last_w == w) return false;
		sl.last_w = w;
		sl.seq++;
	}
	sl.cv.notify_one();
	g_handoffs()++;
	return true;
}
// A submitter: wait for a move after `seen` (returns the new sequence), at most `timeout_us` (returns `seen` then).
inline uint64_t wait_move(int idx, uint64_t seen, uint32_t timeout_us) {
	Slot&             sl = slots()[idx];
	std::unique_lock  l(sl.m);
	sl.cv.wait_for(l, std::chrono::microseconds(timeout_us), [&] { return sl.seq != seen; });
	return sl.seq;
}
inline uint64_t seq_of(int idx) {
	Slot&           sl = slots()[idx];
	std::lock_guard l(sl.m);
	return sl.seq;
}
// Claim a queue's submitter (true once per queue).
inline bool claim(int idx) {
	if (idx < 0 || idx >= kSlots) return false;
	Slot&           sl = slots()[idx];
	std::lock_guard l(sl.m);
	if (sl.started) return false;
	sl.started = true;
	return true;
}
// The kick (on the title's thread): the watcher looks at once.
inline void kick() {
	{
		std::lock_guard l(wmu());
		wseq()++;
	}
	wcv().notify_one();
	g_kick_wakes()++;
}
// The watcher's sleep between looks: `us`, or until a kick after `seen` (returns the kick sequence).
inline uint64_t watcher_sleep(uint64_t seen, uint32_t us) {
	std::unique_lock l(wmu());
	wcv().wait_for(l, std::chrono::microseconds(us), [&] { return wseq() != seen; });
	return wseq();
}
} // namespace w438
''')

# 2. the consumer: one queue only when `only` >= 0; the watcher dispatches
rep('''static void queue_consumer_thread() {
	pthread_setname_np(pthread_self(), "bc5-ring"); // BC5: host threads named for per-thread CPU views (F81)
	pthread_setname_np(pthread_self(), "bc5-ring"); // BC5: host threads named for per-thread CPU views (F81)
	Direct::set_source(1);''', '''static void queue_consumer_loop(int only); // exp 0438 (tag w438): today's body; `only` >= 0 = one guest queue's submitter
// exp 0438 (tag w438): the watcher. With BC5_0438_WATCHER=0, today's bc5-ring (the loop over every queue).
static void queue_consumer_thread() {
	if (!w438::on()) {
		queue_consumer_loop(-1);
		return;
	}
	pthread_setname_np(pthread_self(), "bc5-dbw");
	uint64_t kseen = 0;
	for (;;) {
		size_t nq = 0;
		{
			std::lock_guard lock(g_mutex);
			nq = g_queues.size();
		}
		for (size_t i = 0; i < nq && i < static_cast<size_t>(w438::kSlots); i++) {
			QueueReg q;
			{
				std::lock_guard lock(g_mutex);
				q = g_queues[i];
			}
			const uint32_t n = static_cast<uint32_t>((q.ring_end - q.ring_base) / 4);
			if (n == 0) continue;
			const uint64_t w = reinterpret_cast<const volatile uint64_t*>(q.doorbell_page)[q.d == 0 ? 0 : q.d - 1] % n;
			if (w438::observe(static_cast<int>(i), w) && w438::claim(static_cast<int>(i))) std::thread(queue_consumer_loop, static_cast<int>(i)).detach();
		}
		kseen = w438::watcher_sleep(kseen, 50);
	}
}
static void queue_consumer_loop(int only) {
	char w438_name[16] = "bc5-ring";
	if (only >= 0) std::snprintf(w438_name, sizeof(w438_name), "bc5-rq%d", only); // exp 0438 (tag w438)
	pthread_setname_np(pthread_self(), w438_name); // BC5: host threads named for per-thread CPU views (F81)
	Direct::set_source(1);''')

# 3. only this submitter's queue
rep('''		bool progressed = false;
		for (auto& s: states) {
			const auto& q     = s.reg;
			t_queue_idx       = static_cast<int>(&s - states.data()); // experiment 0133''', '''		bool progressed = false;
		const uint64_t w438_seq = only >= 0 ? w438::seq_of(only) : 0; // exp 0438 (tag w438): the moves seen before this pass
		for (auto& s: states) {
			if (only >= 0 && static_cast<int>(&s - states.data()) != only) continue; // exp 0438 (tag w438): this submitter's queue
			const auto& q     = s.reg;
			t_queue_idx       = static_cast<int>(&s - states.data()); // experiment 0133''')

# 4. the submitter's wait instead of the poll sleep
rep('''		std::this_thread::sleep_for(std::chrono::microseconds(idle_ticks > 1000 ? bc5::load_stat::kRingPollUs * 5 : bc5::load_stat::kRingPollUs));''',
    '''		if (only >= 0) {
			// exp 0438 (tag w438): a submitter waits for the watcher's next move on its queue; a deferred head is retried after
			// the poll period as before, an idle queue sleeps until a move (at most 50 ms, then looks anyway).
			(void)w438::wait_move(only, w438_seq, progressed ? 0u : (idle_ticks > 1000 ? 50'000u : bc5::load_stat::kRingPollUs));
		} else {
			std::this_thread::sleep_for(std::chrono::microseconds(idle_ticks > 1000 ? bc5::load_stat::kRingPollUs * 5 : bc5::load_stat::kRingPollUs));
		}''')

# 5. the consumer's shared statics made safe for N submitters
rep('''static std::vector<AcbHead> g_acb_heads; // the queue consumer thread only''',
    '''static thread_local std::vector<AcbHead> g_acb_heads; // the queue consumer thread only; exp 0438 (w438): per submitter (an acb belongs to one queue)''')
rep('''		static bool ls_slept = false;''', '''		static thread_local bool ls_slept = false; // exp 0438 (w438): per submitter''')
rep('''				static uint64_t c438_last = 0;
				if (cn - c438_last > 60'000'000'000ull) {
					c438_last = cn;''', '''				static std::atomic<uint64_t> c438_last {0}; // exp 0438 (w438): one 60-s line for all submitters
				uint64_t                     c438_was = c438_last.load();
				if (cn - c438_was > 60'000'000'000ull && c438_last.compare_exchange_strong(c438_was, cn)) {''')

# 6. the kick wakes the watcher
rep('''	c438d_note(request, argp); // exp 0438 (tag c438d): records only
#endif''', '''	c438d_note(request, argp); // exp 0438 (tag c438d): records only
#endif
	if (request == 0xc010811c && w438::kick_on()) w438::kick(); // exp 0438 (tag w438): the title's kick wakes the watcher''')

# 7. the counts on c438d's 60-s line
rep('''"; pointer moves seen %" PRIu64 ", of them after a kick %" PRIu64''', '''"; w438 %s kick %s: hand-overs %" PRIu64 ", kick wakes %" PRIu64 "; pointer moves seen %" PRIu64 ", of them after a kick %" PRIu64''')
rep('''						                Direct::c438::g_kick_seen_before.load(), Direct::c438::g_moves.load()''', '''						                Direct::c438::g_kick_seen_before.load(), w438::on() ? "ON" : "off", w438::kick_on() ? "ON" : "off", w438::g_handoffs().load(), w438::g_kick_wakes().load(), Direct::c438::g_moves.load()''')

out = s.encode('utf-8')
open(OUT, 'wb').write(out)
print('w438 unit', hashlib.md5(out).hexdigest(), len(out))
