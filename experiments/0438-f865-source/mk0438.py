#!/usr/bin/env python3
"""BC5 experiment 0438 (tag k438): applies the F865 source fix to patch bb04219b's src/libs/bc5LleAgc.cpp.

Usage: mk0438.py IN.cpp OUT.cpp
IN must be the shared tree's unit (md5 a62e8bf6..., exp 0436's bake/bc5LleAgc.cpp). Every anchor must occur exactly
once. Bytes in, bytes out (no newline translation).
"""
import hashlib
import os
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


# 1. the k438 namespace, before register_label_writes (it uses PendingLabelWrite, wait_satisfied, covered_sorted, g_dev)
NS = r'''// BC5 experiment 0438 (tag k438): F865's source. A wait of the title's game thread in a graphics buffer (dcb) on a label
// that a compute buffer (acb) releases, when that acb has not reached the host yet, was polled on the title's own thread
// (exp 0428's 8 ms, then the 8 ms limit) and then GIVEN UP and dropped (the F262 family): the dcb ran ahead of the acb's
// work. In u436sS3 (2026-11-20 00:59) four such waits in a row (0x12004b3c38, 4438, 4c38, 5438; ~83 ms) were given up;
// dcb chain #165177 then carried the dropped wait at dword 1285 on 0x12004b4c38 (busy 0x907616589), and acb #165180,
// which releases it at its dword 2332, reached the host 20 ms after the dcb: the GFX ring hung in that dcb and the acb's
// release never ran (the label still busy at the stall). The console's CP decides the wait when it reaches the packet and
// the title's submit call does not block on it. Fix: such a wait is kept for the GPU (the packet stays in the buffer),
// the title's thread goes on. BC5_0438_KEEP (REFUTED by u438sK2, off unless set): 1 = keep instead of giving up, after exp 0428's 8 ms poll;
// 2 = keep at once when no writer is on a ring (no poll); 0 = off (the give-up as before). Two guards come with it:
// - G1: while such a kept wait is open (not satisfied, and its label not written by a compute job submitted since),
//   compute-ring submissions are not held by the 24-job in-flight cap: the acb that releases it must reach its ring
//   while the GFX ring waits for it.
// - G2: F2's cycle check also looks at the kept waits of the jobs ahead of a pending writer on its ring: F4's fence on a
//   GFX writer queued behind a dcb that waits for this acb could never be met.
// Not kept (the path as before): a host flip label, a label not in the GPU's mappings.
namespace k438 {
inline int mode() {
	static const int v = [] {
		const char* e = std::getenv("BC5_0438_KEEP");
		if (e == nullptr || e[0] == 0) return 0; // refuted (u438sK2): off unless set
		return std::atoi(e);
	}();
	return v;
}
struct Open {
	uint32_t p[9];
	bool     is64;
	uint64_t label;
};
inline std::mutex& mu() {
	static std::mutex m;
	return m;
}
inline std::vector<Open>& opened() {
	static std::vector<Open> v;
	return v;
}
#ifndef BC5_LEAN
inline std::atomic<uint64_t> g_kept[2] = {}; // [0] after the poll, [1] at once
inline std::atomic<uint64_t> g_refused {0}; // not kept: a flip label or not mapped
inline std::atomic<uint64_t> g_bp {0};      // compute submissions let past the in-flight cap (G1)
inline std::atomic<uint64_t> g_cyc {0};     // G2: cycles found ahead of the writer on its ring
#endif
// Can this wait stay in the buffer for the GPU? (the label is GPU memory, not a host flip label)
inline bool can_keep(uint64_t label) {
	const auto l0 = reinterpret_cast<uint64_t>(&g_labels[0]);
	if (label >= l0 && label < l0 + sizeof(g_labels)) return false;
	if (!g_dev) return false;
	const auto maps = g_dev->sorted_mappings();
	return maps && covered_sorted(*maps, label & ~7ull, 8);
}
inline void kept(const uint32_t* p, uint32_t len, bool is64, uint64_t label, bool at_once, const char* kind, uint32_t num_dwords, uint32_t off) {
	Open o {};
	for (uint32_t k = 0; k < 9 && k < len; k++) o.p[k] = p[k];
	o.is64  = is64;
	o.label = label;
	{
		std::lock_guard lk(mu());
		auto& v = opened();
		if (v.size() >= 256) v.erase(v.begin());
		v.push_back(o);
	}
#ifndef BC5_LEAN
	const uint64_t n = g_kept[at_once ? 1 : 0]++;
	if (n < 64 || (n & 0x3ffu) == 0)
		journal("k438 (exp 0438): %s %u dwords keeps its wait at %u on 0x%" PRIx64 " for the GPU (value 0x%" PRIx64 ", no writer on a ring; %s; %" PRIu64 " so far)\n", kind, num_dwords, off, label,
		        is64 ? *reinterpret_cast<const volatile uint64_t*>(label & ~7ull) : static_cast<uint64_t>(*reinterpret_cast<const volatile uint32_t*>(label & ~3ull)), at_once ? "at once" : "after the poll", n + 1);
#else
	(void)at_once;
	(void)kind;
	(void)num_dwords;
	(void)off;
#endif
}
// A compute job's registered writes close the kept waits on those labels.
inline void seen(const std::vector<PendingLabelWrite>& found, int ring) {
	if (ring == bc5::direct::kGfxRing) return;
	std::lock_guard lk(mu());
	auto& v = opened();
	if (v.empty()) return;
	std::erase_if(v, [&found](const Open& o) { return std::any_of(found.begin(), found.end(), [&o](const PendingLabelWrite& w) { return w.label == o.label; }); });
}
// G1: is a kept wait still open?
inline bool open_now() {
	std::lock_guard lk(mu());
	auto& v = opened();
	if (v.empty()) return false;
	std::erase_if(v, [](const Open& o) { return wait_satisfied(o.p, o.is64); });
	return !v.empty();
}
} // namespace k438
'''
rep('static void register_label_writes(const uint32_t* ib, uint32_t num_dwords, const std::vector<uint32_t>& executed, uint64_t seq, int ring) {\n',
    NS + 'static void register_label_writes(const uint32_t* ib, uint32_t num_dwords, const std::vector<uint32_t>& executed, uint64_t seq, int ring) {\n')

# 2. register_label_writes: a compute job's writes close the kept waits on those labels
rep('''	if (found.empty()) return;
	std::lock_guard lk(g_plw_mutex);
	static uint64_t order = 0;
''', '''	if (found.empty()) return;
	k438::seen(found, ring); // exp 0438 (tag k438)
	std::lock_guard lk(g_plw_mutex);
	static uint64_t order = 0;
''')

# 3a. mode 2: keep at once, before exp 0428's poll
rep('''						if (split_late >= 3) {
							const uint64_t t2  = SoftCp::now_ns();
''', '''						if (split_late >= 3 && k438::mode() >= 2 && !wait_satisfied(p, op == 0x93) && !ring_will_satisfy(p, op == 0x93, bc5::direct::kGfxRing)) {
							if (k438::can_keep(label)) { // exp 0438 (tag k438): the GPU decides it at the packet
								k438::kept(p, len, op == 0x93, label, true, kind, num_dwords, i);
								t_keep_waits.push_back(p);
								SoftCp::set_gpu_executed(p, len, {0});
								i += len;
								continue;
							}
#ifndef BC5_LEAN
							k438::g_refused++;
#endif
						}
						if (split_late >= 3) {
							const uint64_t t2  = SoftCp::now_ns();
''')

# 3b. mode 1: keep instead of the rest of the path (the second poll, the limit, the give-up) after the poll
rep('''							if (res == 2) {
								ok = true;
								SoftCp::set_gpu_executed(p, len, {0});
								i += len;
								continue;
							}
						}
''', '''							if (res == 2) {
								ok = true;
								SoftCp::set_gpu_executed(p, len, {0});
								i += len;
								continue;
							}
							if ((res == 3 || res == 4) && k438::mode() >= 1) {
								if (k438::can_keep(label)) { // exp 0438 (tag k438): kept, not given up; the GPU decides it at the packet
									k438::kept(p, len, op == 0x93, label, false, kind, num_dwords, i);
									t_keep_waits.push_back(p);
									SoftCp::set_gpu_executed(p, len, {0});
									i += len;
									continue;
								}
#ifndef BC5_LEAN
								k438::g_refused++;
#endif
							}
						}
''')

# 4. G1: compute submissions pass the in-flight cap while a kept wait is open
rep('''		while (g_cq_fences.load() >= max_in_flight || g_recovering.load()) std::this_thread::sleep_for(std::chrono::microseconds(50));
''', '''		const bool k438_pass = k438::mode() >= 1 && ring != bc5::direct::kGfxRing; // exp 0438 G1
		while ((g_cq_fences.load() >= max_in_flight && !(k438_pass && k438::open_now())) || g_recovering.load()) std::this_thread::sleep_for(std::chrono::microseconds(50));
#ifndef BC5_LEAN
		if (k438_pass && g_cq_fences.load() >= max_in_flight) k438::g_bp++;
#endif
''')

# 5. G2: the cycle check over the jobs ahead of the writer on its ring
rep('''	for (const auto& o: others) {
		const auto it = s.job_waits.find(o);
		if (it == s.job_waits.end()) continue;
		for (const uint64_t l: it->second)
			if (std::find(writes.begin(), writes.end(), l) != writes.end()) {
#ifndef BC5_LEAN
				const uint64_t k = s.f2_cycle++;
''', '''	for (const auto& o: others) {
		// exp 0438 G2: with k438 on, every pending job of the writer's ring up to the writer (seq per ring), not only the writer
		const bool k438_ahead = k438::mode() >= 1;
		for (auto it = k438_ahead ? s.job_waits.lower_bound({o.first, 0}) : s.job_waits.find(o); it != s.job_waits.end() && it->first.first == o.first && it->first.second <= o.second; ++it)
		for (const uint64_t l: it->second)
			if (std::find(writes.begin(), writes.end(), l) != writes.end()) {
#ifndef BC5_LEAN
				if (it->first.second != o.second) k438::g_cyc++;
				const uint64_t k = s.f2_cycle++;
''')

# 6. the counts on ho430's 60-s line (normal build)
rep('''		        "bounds that stood %" PRIu64 "\\n",''', '''		        "bounds that stood %" PRIu64 "; k438 kept after the poll %" PRIu64 ", at once %" PRIu64 ", refused %" PRIu64 ", compute past the cap %" PRIu64 ", G2 cycles ahead %" PRIu64 "\\n",''')
rep('''		        s.stands);
	}
#endif
}''', '''		        s.stands, k438::g_kept[0].load(), k438::g_kept[1].load(), k438::g_refused.load(), k438::g_bp.load(), k438::g_cyc.load());
	}
#endif
}''')

exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mk0438b-part.py'), encoding='utf-8').read())

out = s.encode('utf-8')
open(OUT, 'wb').write(out)
print('k438 unit', hashlib.md5(out).hexdigest(), len(out))
