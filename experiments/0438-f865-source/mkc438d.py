#!/usr/bin/env python3
"""BC5 experiment 0438 (tag c438d): the gc-ioctl catcher, on top of the c438 unit (records only, normal build only).

Usage: mkc438d.py IN.cpp OUT.cpp   (IN: cat/bc5LleAgc.cpp made by mkcat438.py, md5 3623fd41...)

- Every /dev/gc request is counted, with the calling thread's name (pthread_getname_np).
- 0xc010811c ("ding dong for workload", A:16669-16674: me, pipe, queue, offset) in full for the first 64 and counted:
  the registered queues whose a/b/c match me/pipe/queue (the mapping is not known: TODO(verify)); that queue's write
  pointer now (read from its doorbell page as bc5-ring reads it); whether offset equals it; the time since bc5-ring
  last saw the queue's pointer move; and whether bc5-ring had already seen this pointer.
- bc5-ring, at each look that finds a queue's pointer moved: was there a kick for that queue since its last move, and
  how long before.
- A c438d line every 60 s (with c438's): the request counts, the kicks by thread, the offset matches, kick->seen and
  the moves with no kick.
"""
import hashlib
import sys

IN, OUT = sys.argv[1], sys.argv[2]
src = open(IN, 'rb').read()
assert hashlib.md5(src).hexdigest() in ('3623fd41142c49514fce913c34c2efab', '94d696fbfe6cca223346ba255338a0f0'), 'not the c438 part-2 unit or the r438 unit on it'
s = src.decode('utf-8')


def rep(old, new, count=1):
    global s
    n = s.count(old)
    assert n == count, (n, old[:120])
    s = s.replace(old, new)


# 1. QueueView: the pointer and the times of its last move and last kick
rep('''	uint64_t at_look[kN] = {}; // part 2: bc5-ring's time totals at this queue's last look
};''', '''	uint64_t at_look[kN] = {}; // part 2: bc5-ring's time totals at this queue's last look
	uint64_t moved = 0, kick = 0; // c438d: when bc5-ring last saw the pointer move; the last kick for this queue not yet followed by a seen move
	uint32_t wptr = 0, ring_n = 0; // c438d: the pointer bc5-ring last saw, the ring's size in dwords
	int      idx = -1;             // c438d: the index in g_queues
};
// exp 0438 (tag c438d): the gc-ioctl catcher's counters
inline std::atomic<uint64_t> g_kicks {0}, g_kick_match {0}, g_kick_nomatch {0}, g_kick_eq {0}, g_kick_seen_before {0}, g_kick_seen[5] = {}, g_moves {0}, g_moves_kick {0}, g_kick_logged {0};''')

# 2. bc5-ring's look: a move, and the kick before it
rep('''					for (int k = 0; k < Direct::c438::kN; k++) e.at_look[k] = z[k];
					e.a       = q.a;''', '''					for (int k = 0; k < Direct::c438::kN; k++) e.at_look[k] = z[k];
					if (s.c438_w != w) { // exp 0438 (c438d): a move seen
						Direct::c438::g_moves++;
						if (e.kick != 0 && e.kick <= cn) {
							Direct::c438::g_moves_kick++;
							Direct::c438::g_kick_seen[Direct::c438::bucket(cn - e.kick)]++;
							e.kick = 0;
						}
						e.moved = cn;
					}
					e.wptr   = w;
					e.ring_n = n;
					e.idx    = static_cast<int>(qi);
					e.a       = q.a;''')

# 3. the hook at gc_ioctl's entry
rep('''static int gc_ioctl(uint64_t request, void* argp) {
	switch (request) {''', '''#ifndef BC5_LEAN
// exp 0438 (tag c438d): every /dev/gc request counted by request and thread; the kick in detail.
static std::mutex                               g_c438d_mu;
static std::map<uint64_t, uint64_t>             g_c438d_req;
static std::map<std::string, uint64_t>          g_c438d_thr; // "request thread-name" -> count
static void c438d_note(uint64_t request, void* argp) {
	char tn[32] = {};
	pthread_getname_np(pthread_self(), tn, sizeof(tn));
	{
		std::lock_guard l(g_c438d_mu);
		g_c438d_req[request]++;
		char key[64];
		std::snprintf(key, sizeof(key), "%" PRIx64 " %s", request, tn);
		g_c438d_thr[key]++;
	}
	if (request != 0xc010811c || argp == nullptr) return;
	const auto*    a  = static_cast<const uint32_t*>(argp);
	const uint64_t cn = SoftCp::now_ns();
	Direct::c438::g_kicks++;
	char           where[400];
	int            ww    = 0;
	bool           match = false;
	where[0]             = 0;
	{
		std::lock_guard cl(Direct::c438::mu());
		for (auto& e: Direct::c438::views()) {
			if (e.idx < 0 || e.a != a[0] || e.b != a[1] || e.c != a[2]) continue;
			match = true;
			uint32_t now_w = e.wptr;
			if (static_cast<size_t>(e.idx) < g_queues.size() && e.ring_n != 0) {
				const auto& q = g_queues[static_cast<size_t>(e.idx)];
				now_w         = static_cast<uint32_t>(reinterpret_cast<const volatile uint64_t*>(q.doorbell_page)[q.d == 0 ? 0 : q.d - 1] % e.ring_n);
			}
			if (now_w == a[3]) Direct::c438::g_kick_eq++;
			if (now_w == e.wptr) Direct::c438::g_kick_seen_before++;
			e.kick = cn;
			if (ww < 340)
				ww += std::snprintf(where + ww, sizeof(where) - static_cast<size_t>(ww), "%squeue %d (%u/%u/%u/0x%x) pointer now %u, last seen %u, %s, last move seen %.3f ms ago", ww ? "; " : "", e.idx, e.a, e.b,
				                    e.c, e.d, now_w, e.wptr, now_w == a[3] ? "offset == pointer" : "offset != pointer", e.moved != 0 ? static_cast<double>(cn - e.moved) / 1e6 : -1.0);
		}
	}
	(match ? Direct::c438::g_kick_match : Direct::c438::g_kick_nomatch)++;
	const uint64_t k = Direct::c438::g_kick_logged++;
	if (k < 64 || (k & 0xfffu) == 0)
		Direct::journal("c438d (exp 0438): kick me %u pipe %u queue %u offset %u on thread %s at t %.6f s: %s (%" PRIu64 " so far)\\n", a[0], a[1], a[2], a[3], tn, Direct::timing_now(), match ? where : "no registered queue with a/b/c = me/pipe/queue",
		                Direct::c438::g_kicks.load());
}
static std::string c438d_line() {
	std::lock_guard l(g_c438d_mu);
	std::string     out;
	char            b[160];
	for (const auto& [r, c]: g_c438d_req) {
		std::snprintf(b, sizeof(b), "%s0x%" PRIx64 " %" PRIu64, out.empty() ? "" : ", ", r, c);
		out += b;
	}
	out += "; by thread:";
	for (const auto& [kname, c]: g_c438d_thr) {
		std::snprintf(b, sizeof(b), " [%s %" PRIu64 "]", kname.c_str(), c);
		out += b;
	}
	return out;
}
#endif
static int gc_ioctl(uint64_t request, void* argp) {
#ifndef BC5_LEAN
	c438d_note(request, argp); // exp 0438 (tag c438d): records only
#endif
	switch (request) {''')

# 4. the 60-s line
rep('''					Direct::journal("c438 (exp 0438): t %.1f s: %" PRIu64 " acb packets;''', '''					{ // exp 0438 (tag c438d)
						const std::string rq = Direct::c438d_line_fwd();
						Direct::journal("c438d (exp 0438): t %.1f s: kicks %" PRIu64 ", a queue with a/b/c = me/pipe/queue %" PRIu64 ", none %" PRIu64 ", offset == the queue's pointer %" PRIu64 ", the pointer already seen by bc5-ring %" PRIu64
						                "; pointer moves seen %" PRIu64 ", of them after a kick %" PRIu64 ", kick->seen <1/<5/<20/<100 ms/more %" PRIu64 "/%" PRIu64 "/%" PRIu64 "/%" PRIu64 "/%" PRIu64 "; requests: %s\\n",
						                Direct::timing_now(), Direct::c438::g_kicks.load(), Direct::c438::g_kick_match.load(), Direct::c438::g_kick_nomatch.load(), Direct::c438::g_kick_eq.load(),
						                Direct::c438::g_kick_seen_before.load(), Direct::c438::g_moves.load(), Direct::c438::g_moves_kick.load(), Direct::c438::g_kick_seen[0].load(), Direct::c438::g_kick_seen[1].load(),
						                Direct::c438::g_kick_seen[2].load(), Direct::c438::g_kick_seen[3].load(), Direct::c438::g_kick_seen[4].load(), rq.c_str());
					}
					Direct::journal("c438 (exp 0438): t %.1f s: %" PRIu64 " acb packets;''')
# the 60-s line is in SoftCp (before gc_ioctl's definition): a forward declaration through a function pointer-free shim
rep('''static thread_local UnreadyWait t_unready;
''', '''static thread_local UnreadyWait t_unready;
#ifndef BC5_LEAN
static std::string c438d_line_fwd(); // exp 0438 (tag c438d): defined after gc_ioctl's catcher
#endif
''')
rep('''static int gc_ioctl(uint64_t request, void* argp) {
#ifndef BC5_LEAN
	c438d_note(request, argp); // exp 0438 (tag c438d): records only''', '''#ifndef BC5_LEAN
namespace Direct {
static std::string c438d_line_fwd() { return c438d_line(); }
} // namespace Direct
#endif
static int gc_ioctl(uint64_t request, void* argp) {
#ifndef BC5_LEAN
	c438d_note(request, argp); // exp 0438 (tag c438d): records only''')

out = s.encode('utf-8')
open(OUT, 'wb').write(out)
print('c438d unit', hashlib.md5(out).hexdigest(), len(out))
