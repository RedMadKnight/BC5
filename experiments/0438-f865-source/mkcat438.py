#!/usr/bin/env python3
"""BC5 experiment 0438 (tag c438): the catcher for the open question of F865, applied to patch bb04219b's unit.

Is the writer acb late on the title's side (its queue's write pointer shows it late) or on the host's side (bc5-ring
saw it and submitted it late)? Records only, normal build only (#ifndef BC5_LEAN), no switch, no behaviour change:
- per compute-queue IB packet: when bc5-ring first saw the write pointer past it, the gap since bc5-ring's previous
  look at that queue (the window in which the title wrote it), and when the slice holding it went to Direct::submit;
- a 60-s line: packets, the seen->submit histogram (<1, <5, <20, <100 ms, more), the poll-gap histogram, the longest
  of each; each packet with seen->submit >= 20 ms or a poll gap >= 20 ms journaled (first 200, then every 256th);
- at each "cpu-wait ... GIVEN UP / TIMEOUT / CYCLE": every guest queue's state as bc5-ring left it (pending dwords,
  deferred since, the unready head's label, value and position, the time since its packet was first seen).

Usage: mkcat438.py IN.cpp OUT.cpp   (IN: the tree unit a62e8bf6..., exp 0436's bake/bc5LleAgc.cpp)
"""
import hashlib
import sys

IN, OUT = sys.argv[1], sys.argv[2]
src = open(IN, 'rb').read()
assert hashlib.md5(src).hexdigest() == 'a62e8bf6251a44f147a23d9689449e21', 'not patch bb04219b\'s unit'
s = src.decode('utf-8')


def rep(old, new, count=1):
    global s
    n = s.count(old)
    assert n == count, (n, old[:120])
    s = s.replace(old, new)


# 1. the shared snapshot and the counters, beside t_unready (before namespace SoftCp)
rep('''static thread_local UnreadyWait t_unready;
''', '''static thread_local UnreadyWait t_unready;
#ifndef BC5_LEAN
// BC5 experiment 0438 (tag c438): the catcher (records only). bc5-ring's view of each guest queue, for the journal line
// at a given-up wait on another thread.
namespace c438 {
struct QueueView {
	uint32_t a = 0, b = 0, c = 0, d = 0, pending = 0, pos = 0;
	uint64_t deferred_since = 0, label = 0, value = 0, head_seen = 0, poll = 0;
	bool     unready = false;
};
inline std::mutex& mu() {
	static std::mutex m;
	return m;
}
inline std::vector<QueueView>& views() {
	static std::vector<QueueView> v;
	return v;
}
inline std::atomic<uint64_t> g_pk {0}, g_hist_sub[5] = {}, g_hist_gap[5] = {}, g_max_sub {0}, g_max_gap {0}, g_logged {0};
inline int bucket(uint64_t ns) {
	return ns < 1'000'000ull ? 0 : ns < 5'000'000ull ? 1 : ns < 20'000'000ull ? 2 : ns < 100'000'000ull ? 3 : 4;
}
inline void maxed(std::atomic<uint64_t>& m, uint64_t v) {
	for (uint64_t x = m.load(); v > x && !m.compare_exchange_weak(x, v);) {
	}
}
} // namespace c438
#endif
''')

# 2. bc5-ring: per-queue seen times
rep('''		uint64_t deferred_since = 0; // direct mode: this queue's next IB waits on another queue
		uint64_t deferred_report = 0; // when the deferral was last journaled (run 118)
	};''', '''		uint64_t deferred_since = 0; // direct mode: this queue's next IB waits on another queue
		uint64_t deferred_report = 0; // when the deferral was last journaled (run 118)
#ifndef BC5_LEAN
		uint64_t c438_w    = ~0ull; // exp 0438 (c438): the write pointer bc5-ring saw last
		uint64_t c438_poll = 0;     // exp 0438 (c438): bc5-ring's previous look at this queue
		struct Seen {
			uint32_t off;
			uint64_t ib;
			uint32_t dw;
			uint64_t seen, gap;
		};
		std::vector<Seen> c438_seen; // the IB packets seen and not yet submitted, in ring order
#endif
	};''')

rep('''			const uint32_t w = static_cast<uint32_t>(wraw % n);
			const uint32_t r = static_cast<uint32_t>(s.rptr % n);
			if (w == r) {
				continue;
			}''', '''			const uint32_t w = static_cast<uint32_t>(wraw % n);
			const uint32_t r = static_cast<uint32_t>(s.rptr % n);
#ifndef BC5_LEAN
			{ // exp 0438 (c438): the packets the write pointer moved past since the last look, with their seen time
				const uint64_t cn = now_ns(), gap = s.c438_poll == 0 ? 0 : cn - s.c438_poll;
				s.c438_poll = cn;
				if (s.c438_w != w) {
					const auto* rg = reinterpret_cast<const uint32_t*>(q.ring_base);
					uint32_t    k  = s.c438_w == ~0ull ? r : static_cast<uint32_t>(s.c438_w);
					for (uint32_t guard = 0; k != w && guard < 4096; guard++) {
						const uint32_t hh = rg[k];
						uint32_t       ll = 1;
						if ((hh >> 30u) == 3) {
							const uint32_t c = (hh >> 16u) & 0x3fffu;
							ll               = c == 0x3fffu ? 1 : c + 2;
						}
						if ((hh >> 30u) == 3 && (((hh >> 8u) & 0xffu) == IT_INDIRECT_BUFFER || ((hh >> 8u) & 0xffu) == IT_INDIRECT_BUFFER_CNST) && ll >= 4 && k + ll <= n) {
							const uint64_t ta = (rg[k + 1] & ~3u) | (static_cast<uint64_t>(rg[k + 2] & 0xffu) << 32u);
							if (s.c438_seen.size() < 4096) s.c438_seen.push_back({k, ta, rg[k + 3] & 0xfffffu, cn, gap});
						}
						k = (k + ll) % n;
					}
					s.c438_w = w;
				}
			}
#endif
			if (w == r) {
				continue;
			}''')

# 3. the queue's state for the snapshot: deferred or not, with the unready head
rep('''				const uint64_t now = now_ns();
				if (!ready && ready_len != 0) {''', '''				const uint64_t now = now_ns();
#ifndef BC5_LEAN
				{ // exp 0438 (c438): this queue's state as bc5-ring leaves it
					std::lock_guard cl(Direct::c438::mu());
					auto&           v = Direct::c438::views();
					const size_t    qi = static_cast<size_t>(&s - states.data());
					if (v.size() <= qi) v.resize(qi + 1);
					auto& e   = v[qi];
					e.a       = q.a;
					e.b       = q.b;
					e.c       = q.c;
					e.d       = q.d;
					e.pending = pending;
					e.poll    = now;
					e.unready = !ready;
					if (!ready) {
						const auto& u    = Direct::t_unready;
						e.label          = u.label;
						e.value          = u.value;
						e.pos            = u.pos;
						e.deferred_since = s.deferred_since == 0 ? now : s.deferred_since;
						e.head_seen      = 0;
						for (const auto& x: s.c438_seen)
							if (x.ib == reinterpret_cast<uint64_t>(u.ib)) {
								e.head_seen = x.seen;
								break;
							}
					} else {
						e.deferred_since = 0;
					}
				}
#endif
				if (!ready && ready_len != 0) {''')

# 4. at the slice's submit: seen -> submit for each packet it takes
rep('''			Direct::chain_begin(); // ADR 0010: the slice's buffers as one submission
			if (w_take > r) {''', '''#ifndef BC5_LEAN
			{ // exp 0438 (c438): the packets of this slice, seen -> submit (the slice goes to Direct::submit now)
				const uint64_t cn = now_ns();
				const uint32_t tk = (w_take + n - r) % n;
				while (!s.c438_seen.empty()) {
					const auto&    x  = s.c438_seen.front();
					const uint32_t dx = (x.off + n - r) % n;
					if (dx >= pending) { // behind the read pointer or past the write pointer: not a live entry
						s.c438_seen.erase(s.c438_seen.begin());
						continue;
					}
					if (dx >= tk && !(tk == 0 && take != 0)) break; // not in this slice
					const uint64_t d = cn - x.seen;
					Direct::c438::g_pk++;
					Direct::c438::g_hist_sub[Direct::c438::bucket(d)]++;
					Direct::c438::g_hist_gap[Direct::c438::bucket(x.gap)]++;
					Direct::c438::maxed(Direct::c438::g_max_sub, d);
					Direct::c438::maxed(Direct::c438::g_max_gap, x.gap);
					if (d >= 20'000'000ull || x.gap >= 20'000'000ull) {
						const uint64_t k = Direct::c438::g_logged++;
						if (k < 200 || (k & 0xffu) == 0)
							Direct::journal("c438 (exp 0438): queue %u/%u/%u/0x%x acb %u dwords at 0x%" PRIx64 ": seen at t %.6f s, %.3f ms after bc5-ring's previous look; submitted %.3f ms after it was seen (%" PRIu64 " such so far)\\n",
							                q.a, q.b, q.c, q.d, x.dw, x.ib, Direct::timing_now() - static_cast<double>(cn - x.seen) / 1e9, static_cast<double>(x.gap) / 1e6, static_cast<double>(d) / 1e6, k + 1);
					}
					s.c438_seen.erase(s.c438_seen.begin());
				}
				static uint64_t c438_last = 0;
				if (cn - c438_last > 60'000'000'000ull) {
					c438_last = cn;
					Direct::journal("c438 (exp 0438): t %.1f s: %" PRIu64 " acb packets; seen->submit <1/<5/<20/<100 ms/more %" PRIu64 "/%" PRIu64 "/%" PRIu64 "/%" PRIu64 "/%" PRIu64 ", longest %.3f ms; "
					                "bc5-ring's look gap before the seen <1/<5/<20/<100 ms/more %" PRIu64 "/%" PRIu64 "/%" PRIu64 "/%" PRIu64 "/%" PRIu64 ", longest %.3f ms\\n",
					                Direct::timing_now(), Direct::c438::g_pk.load(), Direct::c438::g_hist_sub[0].load(), Direct::c438::g_hist_sub[1].load(), Direct::c438::g_hist_sub[2].load(), Direct::c438::g_hist_sub[3].load(),
					                Direct::c438::g_hist_sub[4].load(), static_cast<double>(Direct::c438::g_max_sub.load()) / 1e6, Direct::c438::g_hist_gap[0].load(), Direct::c438::g_hist_gap[1].load(), Direct::c438::g_hist_gap[2].load(),
					                Direct::c438::g_hist_gap[3].load(), Direct::c438::g_hist_gap[4].load(), static_cast<double>(Direct::c438::g_max_gap.load()) / 1e6);
				}
			}
#endif
			Direct::chain_begin(); // ADR 0010: the slice's buffers as one submission
			if (w_take > r) {''')

# 5. at a given-up / timed-out / cycle-broken CPU wait: the queues as bc5-ring left them
rep('''					if (!ok) journal("cpu-wait %s at %u on 0x%" PRIx64 ": %s after %.1f ms\\n", op == 0x93 ? "WAIT_REG_MEM64" : "WAIT_REG_MEM", i, label, broken ? "CYCLE" : (limit < 1'000'000'000ull ? "GIVEN UP" : "TIMEOUT"), static_cast<double>(SoftCp::now_ns() - t0) / 1e6);''',
    '''					if (!ok) journal("cpu-wait %s at %u on 0x%" PRIx64 ": %s after %.1f ms\\n", op == 0x93 ? "WAIT_REG_MEM64" : "WAIT_REG_MEM", i, label, broken ? "CYCLE" : (limit < 1'000'000'000ull ? "GIVEN UP" : "TIMEOUT"), static_cast<double>(SoftCp::now_ns() - t0) / 1e6);
#ifndef BC5_LEAN
					if (!ok) { // exp 0438 (c438): every guest queue as bc5-ring last left it
						std::lock_guard cl(c438::mu());
						const uint64_t  cn = SoftCp::now_ns();
						for (const auto& e: c438::views()) {
							if (e.unready)
								journal("c438 (exp 0438):   queue %u/%u/%u/0x%x: %u dwords pending, looked at %.3f ms ago; head UNREADY for %.3f ms at %u on 0x%" PRIx64 " (value 0x%" PRIx64 "), its packet seen %.3f ms ago\\n", e.a, e.b, e.c, e.d,
								        e.pending, static_cast<double>(cn - e.poll) / 1e6, static_cast<double>(cn - e.deferred_since) / 1e6, e.pos, e.label, e.value,
								        e.head_seen != 0 ? static_cast<double>(cn - e.head_seen) / 1e6 : -1.0);
							else
								journal("c438 (exp 0438):   queue %u/%u/%u/0x%x: %u dwords pending, looked at %.3f ms ago; head ready\\n", e.a, e.b, e.c, e.d, e.pending, static_cast<double>(cn - e.poll) / 1e6);
						}
					}
#endif''')

out = s.encode('utf-8')
open(OUT, 'wb').write(out)
print('c438 unit', hashlib.md5(out).hexdigest(), len(out))
