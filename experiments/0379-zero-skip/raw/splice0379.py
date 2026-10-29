# exp 0379: splices the zero scan and the zero skip into a copy of bc5LleAgc.cpp (patch 0001 9420cfa0, blob 8d2f498).
# usage: python -I splice0379.py <orig.cpp> <block.cpp> <out.cpp>
import sys
orig, blockf, outp = sys.argv[1:4]
s = open(orig, encoding='utf-8', newline='').read()
block = open(blockf, encoding='utf-8', newline='').read()
def rep(a, b, n=1):
    global s
    c = s.count(a)
    assert c == n, ("anchor count", c, a[:80])
    s = s.replace(a, b)

rep('#include "bc5/full_state.hpp"\n',
    '#include "bc5/full_state.hpp"\n#include "bc5/zero_skip.hpp" // experiment 0379\n#include <sys/resource.h>\n#include <sys/syscall.h>\n')

# the block goes before direct_sync_one, after the scratch declarations it sits beside
rep('static void scratch_release(uint64_t lo, uint64_t hi);\n\nstatic void direct_sync_one(DState& S, bool force) {\n',
    'static void scratch_release(uint64_t lo, uint64_t hi);\n\n' + block + 'static void direct_sync_one(DState& S, bool force) {\n')

# 1. resolve, take canary hits into account and run the scan before the fast path
rep('''	const uint64_t sig = views_p->sig;
	if (sig != S.views_sig) g_layout_gen++;
	{
		struct stat st {};''',
'''	const uint64_t sig = views_p->sig;
	if (sig != S.views_sig) g_layout_gen++;
	// Experiment 0379: place the zero list before the heaps' first import; a canary hit forces a full sync.
	const bool zskip_new = S.kind == 0 && zskip_resolve(views);
	if (S.kind == 0) {
		zscan_tick(S, views);
		zskip_report();
		for (size_t r = 0; r < g_zskip.run_count() && r < g_zruns && !g_zskip.empty(); r++) {
			if (g_zflag[r].load() == 1) S.blocks = ~0ull;
		}
		if (zskip_new) S.blocks = ~0ull;
	}
	{
		struct stat st {};''')

# 2. take chunks back (CPU writes, canary hits) on the full path, and leave skipped chunks out of the import
rep('''	const uint64_t t_scan0 = SoftCp::now_ns(); // experiment 0169
	// 1. chunks to import: data inside a view, and the forced ones
	std::vector<uint64_t> need;''',
'''	const uint64_t t_scan0 = SoftCp::now_ns(); // experiment 0169
	zskip_take_back(S, fd); // experiment 0379
	const bool zskip_on = S.kind == 0 && !g_zskip.empty();
	// 1. chunks to import: data inside a view, and the forced ones
	std::vector<uint64_t> need;''')
rep('''			for (uint64_t c = v.off & ~(kDChunk - 1); c < v.off + v.size; c += kDChunk) {
				if (direct_covered_end(S, c) == 0) need.push_back(c);
			}
			continue;''',
'''			for (uint64_t c = v.off & ~(kDChunk - 1); c < v.off + v.size; c += kDChunk) {
				if (zskip_on && g_zskip.contains(c)) continue; // experiment 0379: on the zero list, under the canary
				if (direct_covered_end(S, c) == 0) need.push_back(c);
			}
			continue;''')
rep('''	for (const uint64_t c: S.forced) {
		if (direct_covered_end(S, c) == 0) need.push_back(c);
	}''',
'''	for (const uint64_t c: S.forced) {
		if (zskip_on && g_zskip.contains(c)) continue; // experiment 0379: forced only by a learned window
		if (direct_covered_end(S, c) == 0) need.push_back(c);
	}''')

# 3. a real mapping replaces the canary under it
rep('''				if (!g_scratch.empty()) {
					const uint64_t ts = SoftCp::now_ns();
					scratch_release(w.va, w.va + w.size);
					scratch_ns += SoftCp::now_ns() - ts;
				}''',
'''				if (!g_scratch.empty()) {
					const uint64_t ts = SoftCp::now_ns();
					scratch_release(w.va, w.va + w.size);
					scratch_ns += SoftCp::now_ns() - ts;
				}
				if (!g_zpieces.empty()) zskip_release(w.va, w.va + w.size); // experiment 0379''')

# 4. the canary under every skipped chunk, for new views and a new placement
rep('''		S.maps.swap(next);
		S.views_sig  = sig;''',
'''		S.maps.swap(next);
		if (S.kind == 0 && (zskip_new || sig != S.views_sig)) zskip_map(views); // experiment 0379
		S.views_sig  = sig;''')

# 5. a hint takes a skipped chunk back; a learned window does not
rep('''			for (uint64_t c = (v.off + (a - v.va)) & ~(kDChunk - 1); c < v.off + (b - v.va); c += kDChunk) {
				if (S.forced.insert(c).second) here += kDChunk;
			}''',
'''			for (uint64_t c = (v.off + (a - v.va)) & ~(kDChunk - 1); c < v.off + (b - v.va); c += kDChunk) {
				// Experiment 0379: a hint window (a render target, a user-data pointer) takes a skipped chunk back.
				bool back = false;
				if (S.kind == 0 && !t_force_learned && !g_zskip.empty()) {
					const long run = g_zskip.run_of(c);
					if (run >= 0 && g_zskip.erase_chunk(c)) {
						back = true;
						g_zstat_hint++;
						if (static_cast<size_t>(run) < g_zleft.size()) g_zleft[static_cast<size_t>(run)] -= kDChunk;
						S.blocks = ~0ull;
					}
				}
				if (S.forced.insert(c).second || back) here += kDChunk;
			}''')
rep('''static void map_window(uint64_t lo, uint64_t hi, std::vector<bc5::direct::Mapping>& have, const char* what, uint64_t addr) {
	if (const uint64_t asked = direct_force(lo, hi); asked != 0) {''',
'''static void map_window(uint64_t lo, uint64_t hi, std::vector<bc5::direct::Mapping>& have, const char* what, uint64_t addr) {
	t_force_learned = std::strcmp(what, "learned") == 0; // experiment 0379: a learned window leaves skipped chunks skipped
	const uint64_t asked_w = direct_force(lo, hi);
	t_force_learned = false;
	if (const uint64_t asked = asked_w; asked != 0) {''')

# 6. a device reopen ends the skip
rep('''			g_hinted.clear();
			g_scratch.clear();
			g_scratch_id = 0;''',
'''			g_hinted.clear();
			g_scratch.clear();
			g_scratch_id = 0;
			zskip_disable("device reopen"); // experiment 0379''')

open(outp, 'w', encoding='utf-8', newline='\n').write(s)
print("ok", s.count('experiment 0379'), "marks")
