#!/usr/bin/env python3
# BC5 experiment 0310: who writes node data into the count records — the leaf builder 0x909936c00's node buffer against
# the count pass 0x909939400's two-record argument block, read at filter time from the tree's struct, compared at the
# timeout. In src/libs/bc5LleAgc.cpp of the shared tree as integrated on the box (md5 5bccbb80). No packet added, journal
# only. Exp 0277's probe fix carried as exp 0300/0302/0308 did.
#   The reading (exp 0310 step 1, the programs' code, a field decode of the shader dumps; TODO(verify) with llvm-mc):
#   - the count pass: s[0:1] = ud0:1 = the tree's struct; its argument block is the V# at ud2:5 = {struct + 0x100, stride
#     0x20, 2 records}; thread 0 stores record 1 = {arr[0] - struct[0x78], 1, 1, flags} where arr = the dword array at
#     struct + struct[0x50:0x54] (records struct[0x6c]); the leaf builder's DISPATCH_INDIRECT reads record 1 (+0x120).
#   - the leaf builder: s[4:5] = ud4:5 = the same kind of struct; its OUTPUT node buffer is the V# {base struct +
#     (struct[0x7c] << 6), stride 0x40, records struct[0x78]}; it stores a 0x40-byte node at index v28 = arr[ud8] + the
#     thread's index (arr the same dword array, read by s_buffer_load). So the node buffer is addressed from the struct:
#     node k lies at struct + (struct[0x7c] + k) * 0x40, and node (4 - struct[0x7c]) would lie exactly over the argument
#     block at struct + 0x100: a struct[0x7c] below 4 - (records written) puts node data over the counts.
#   1. Filter time, per leaf-builder dispatch: the struct, struct[0x78] (records), struct[0x7c] (node base in 64-byte
#      units), struct[0x50:0x54] + struct[0x6c] (the dword array), the node extent [struct + 0x7c*64, + records*64), the
#      argument block [struct + 0x100, +0x40) and its record 1 now, the first node indices (arr[ud8]) — and the test "the
#      node extent covers the argument block" (NODES COVER THE COUNT RECORDS), journaled at once (256 loud lines) and
#      otherwise one per 4096 ("leaf (exp 0310)"). The last 4096 readings kept by struct.
#   2. Filter time, per count-pass dispatch: struct (ud0:1), the V# at ud2:5 (base, stride, records) against struct +
#      0x100, arr[0] and struct[0x78] (the count it will write), journaled the first 16 and every 4096th ("count (exp
#      0310)").
#   3. At the timeout, per leaf-builder DISPATCH_INDIRECT in the hung buffer: the struct named by its user data as the
#      probe tracks them (COMPUTE_USER_DATA_4/5), struct[0x7c] / [0x78] now vs the kept reading, the node extent vs the
#      argument block, and record 1 now ("timeout probe: leaf (exp 0310)").
# usage: patch0310.py <src root of the shared tree> <out dir>   (writes <out dir>/bc5LleAgc.cpp and <out dir>/patch_0310.diff)
import difflib, hashlib, os, sys

EDITS = {
    'src/libs/bc5LleAgc.cpp': [
        ('''static void timeout_probe(const uint32_t* sub_ib, uint32_t sub_n, const char* kind, uint64_t n, const std::vector<uint32_t>* ran, const std::vector<GeProbeSlot>* gep = nullptr) {
''', 1, '''// Experiment 0310: the leaf builder's node buffer against the count pass's argument block, both addressed from the
// tree's struct (exp 0310 step 1). Kept at filter time by struct address for the probe.
struct LeafSnap {
	uint64_t st = 0, submit = 0;
	double   t = 0;
	uint32_t h78 = 0, h7c = 0, h6c = 0, h50 = 0, h54 = 0, ud8 = 0;
	uint32_t rec1[3] = {};
	uint32_t arr0 = 0, arr_ud8 = 0;
	bool     st_ok = false, arr_ok = false, rec_ok = false;
};
static std::mutex           g_x0310_m;
static std::deque<LeafSnap> g_x0310; // the last 4096
static double x0310_now() {
	timespec ts {};
	clock_gettime(CLOCK_MONOTONIC, &ts);
	return static_cast<double>(ts.tv_sec) + static_cast<double>(ts.tv_nsec) * 1e-9;
}
static uint64_t x0310_env_pgm(const char* name, uint64_t dflt) {
	const char* e = std::getenv(name);
	return e != nullptr && *e != 0 ? std::strtoull(e, nullptr, 16) : dflt;
}
// The struct's dwords the two programs read, and the argument block's record 1, as memory reads now.
static LeafSnap x0310_read(const std::vector<bc5::direct::Mapping>& maps, uint64_t st, uint32_t ud8) {
	LeafSnap s;
	s.st  = st;
	s.ud8 = ud8;
	s.t   = x0310_now();
	if (st != 0 && covered_sorted(maps, st, 0x140)) {
		const auto* h = reinterpret_cast<const volatile uint32_t*>(st);
		s.h50 = h[0x14], s.h54 = h[0x15], s.h6c = h[0x1b], s.h78 = h[0x1e], s.h7c = h[0x1f];
		s.rec1[0] = h[0x48], s.rec1[1] = h[0x49], s.rec1[2] = h[0x4a]; // struct + 0x120: record 1 of the argument block
		s.st_ok = s.rec_ok = true;
		const uint64_t arr = st + (s.h50 | (static_cast<uint64_t>(s.h54) << 32u));
		if (s.h54 < 0x100u && covered_sorted(maps, arr, (static_cast<uint64_t>(ud8) + 1) * 4)) {
			const auto* a = reinterpret_cast<const volatile uint32_t*>(arr);
			s.arr0 = a[0], s.arr_ud8 = a[ud8], s.arr_ok = true;
		}
	}
	return s;
}
static void timeout_probe(const uint32_t* sub_ib, uint32_t sub_n, const char* kind, uint64_t n, const std::vector<uint32_t>* ran, const std::vector<GeProbeSlot>* gep = nullptr) {
'''),
        # 0310c: the CPU-writer test first — before the dump and every other probe line (0310b's per-dispatch sampling was
        #   lost when the emulator crashed ~2 s after the hang): the last 24 distinct structs the filter saw, record 1 read in
        #   three passes 50 ms apart (~100 ms in all); the journal flushes every line.
        ('''	if (sub_ib == nullptr || sub_n == 0 || BC5_DIAG_ENV("BC5_DIRECT_TIMEOUT_PROBE") == nullptr || g_dump_dir.empty() || !g_dev) return;
''', 1, '''	if (sub_ib == nullptr || sub_n == 0 || BC5_DIAG_ENV("BC5_DIRECT_TIMEOUT_PROBE") == nullptr || g_dump_dir.empty() || !g_dev) return;
	{ // experiment 0310c: the GPU is wedged here, so a record 1 that still moves between reads 50 ms apart has a CPU writer
		static std::atomic<uint32_t> n_once {0};
		if (n_once++ < 4) {
			std::vector<uint64_t> structs;
			{
				std::lock_guard<std::mutex> lk(g_x0310_m);
				for (auto it = g_x0310.rbegin(); it != g_x0310.rend() && structs.size() < 24; ++it) {
					if (std::find(structs.begin(), structs.end(), it->st) == structs.end()) structs.push_back(it->st);
				}
			}
			const auto           maps0 = g_dev->sorted_mappings();
			std::vector<uint32_t> a(structs.size() * 9, 0u);
			std::vector<bool>     ok(structs.size(), false);
			for (int k = 0; k < 3; k++) {
				for (size_t i = 0; i < structs.size(); i++) {
					if (k == 0) ok[i] = structs[i] != 0 && covered_sorted(*maps0, structs[i] + 0x120u, 12);
					if (!ok[i]) continue;
					const auto* h = reinterpret_cast<const volatile uint32_t*>(structs[i] + 0x120u);
					a[i * 9 + k * 3] = h[0], a[i * 9 + k * 3 + 1] = h[1], a[i * 9 + k * 3 + 2] = h[2];
				}
				if (k < 2) { timespec sl {0, 50 * 1000 * 1000}; nanosleep(&sl, nullptr); }
			}
			uint32_t moving = 0;
			for (size_t i = 0; i < structs.size(); i++) {
				if (!ok[i]) continue;
				const uint32_t* v = a.data() + i * 9;
				const bool moves = v[0] != v[3] || v[1] != v[4] || v[2] != v[5] || v[3] != v[6] || v[4] != v[7] || v[5] != v[8];
				if (moves) moving++;
				journal("timeout probe: leaf (exp 0310c): record 1 of struct 0x%" PRIx64 " sampled 3x 50 ms apart while the GPU is wedged: %08x %08x %08x | %08x %08x %08x | %08x %08x %08x -> %s\\n", structs[i],
				        v[0], v[1], v[2], v[3], v[4], v[5], v[6], v[7], v[8], moves ? "MOVES: A CPU WRITER" : "still");
			}
			journal("timeout probe: leaf (exp 0310c): %u of %zu structs' record 1 moved within 100 ms while the GPU is wedged%s\\n", moving, structs.size(), moving ? ": THE TITLE'S CPU WRITES THERE" : ": no CPU writer seen in this window");
		}
	}
'''),
        ('''	std::vector<uint32_t> mec_positions;         // offsets of its compute-form DISPATCH_INDIRECT
''', 1, '''	std::vector<uint32_t> mec_positions;         // offsets of its compute-form DISPATCH_INDIRECT
	std::vector<uint32_t> probe_old_to_new;       // experiment 0277's probe fix, carried by 0310: the timeout probe reads the rebuilt IB, so its executed offsets go forward again
'''),
        ('''			if (type == 3 && (op == 0x2c || op == 0x38) && len >= 10 && ib[q + 5] > 65536u) { // experiment 0054
''', 1, '''			// Experiment 0310: the leaf builder's node buffer against the count pass's argument block, at filter time.
			{
				static const uint64_t leaf_pgm  = x0310_env_pgm("BC5_DIRECT_LEAF_PGM", 0x909936c00ull);
				static const uint64_t count_pgm = x0310_env_pgm("BC5_DIRECT_COUNT_PGM", 0x909939400ull);
				if (type == 3 && (op == 0x15 || op == 0x16) && pgm == leaf_pgm) {
					const uint64_t st = ud[4] | (static_cast<uint64_t>(ud[5] & 0xffffu) << 32u);
					LeafSnap       s  = x0310_read(*maps_p, st, ud[8]);
					s.submit          = g_submits.load();
					const uint64_t node_lo = s.st_ok ? st + (static_cast<uint64_t>(s.h7c) << 6u) : 0;
					const uint64_t node_hi = s.st_ok ? node_lo + (static_cast<uint64_t>(s.h78) << 6u) : 0;
					const bool     covers  = s.st_ok && node_lo < st + 0x140u && node_hi > st + 0x100u;
					static std::atomic<uint64_t> n_leaf {0}, n_loud {0};
					const uint64_t nl   = n_leaf++;
					const bool     loud = !s.st_ok || covers || (s.st_ok && s.h7c < 8u);
					if ((loud && n_loud++ < 256) || (nl & 0xfffu) == 0) {
						journal("leaf (exp 0310): %s dispatch op %02x at %u before #%" PRIu64 ": struct 0x%" PRIx64 " %s: [0x78] records %u, [0x7c] node base %u (x64 = +0x%x), [0x50] arr +0x%x%08x [0x6c] %u, ud8 %u, arr[0] %u arr[ud8] %u%s; "
						        "nodes [0x%" PRIx64 ", 0x%" PRIx64 ") vs the argument block [0x%" PRIx64 ", +0x40): %s; record 1 now %08x %08x %08x (%" PRIu64 " so far)\\n",
						        kind, op, q, s.submit, st, s.st_ok ? "read" : "NOT MAPPED", s.h78, s.h7c, s.h7c << 6u, s.h54, s.h50, s.h6c, ud[8], s.arr0, s.arr_ud8, s.arr_ok ? "" : " (arr not mapped)",
						        node_lo, node_hi, st + 0x100u, covers ? "NODES COVER THE COUNT RECORDS" : "apart", s.rec1[0], s.rec1[1], s.rec1[2], nl + 1);
					}
					std::lock_guard<std::mutex> lk(g_x0310_m);
					g_x0310.push_back(s);
					if (g_x0310.size() > 4096) g_x0310.pop_front();
				}
				if (type == 3 && (op == 0x15 || op == 0x16) && pgm == count_pgm) {
					const uint64_t st  = ud[0] | (static_cast<uint64_t>(ud[1] & 0xffffu) << 32u);
					const uint64_t vb  = ud[2] | (static_cast<uint64_t>(ud[3] & 0xffffu) << 32u);
					const uint32_t vst = (ud[3] >> 16u) & 0x3fffu;
					LeafSnap       s   = x0310_read(*maps_p, st, 0);
					static std::atomic<uint64_t> n_cnt {0};
					const uint64_t nc = n_cnt++;
					if (nc < 16 || (nc & 0xfffu) == 0 || vb != st + 0x100u) {
						journal("count (exp 0310): %s dispatch op %02x at %u before #%" PRIu64 ": struct 0x%" PRIx64 " %s, argument V# base 0x%" PRIx64 " stride %u records %u (%s), will write record 1 = {arr[0] %u - [0x78] %u = %d, 1, 1}; record 1 now %08x %08x %08x; [0x7c] %u (%" PRIu64 " so far)\\n",
						        kind, op, q, g_submits.load(), st, s.st_ok ? "read" : "NOT MAPPED", vb, vst, ud[4], vb == st + 0x100u ? "struct + 0x100" : "NOT struct + 0x100", s.arr0, s.h78, static_cast<int32_t>(s.arr0 - s.h78),
						        s.rec1[0], s.rec1[1], s.rec1[2], s.h7c, nc + 1);
					}
				}
			}
			if (type == 3 && (op == 0x2c || op == 0x38) && len >= 10 && ib[q + 5] > 65536u) { // experiment 0054
'''),
        ('''			sub_ib = mec_ib.data();
			sub_n  = static_cast<uint32_t>(mec_ib.size());
''', 1, '''			sub_ib = mec_ib.data();
			sub_n  = static_cast<uint32_t>(mec_ib.size());
			probe_old_to_new.swap(old_to_new); // experiment 0277's probe fix (exp 0310)
'''),
        ('''	auto r = g_dev->submit(std::span<const uint32_t>(sub_ib, sub_n), opt, 2'000'000'000ull, with_gds, qring);
	mec_back(r.executed_offsets);
''', 1, '''	auto probe_ran = [&probe_old_to_new](const std::vector<uint32_t>& offsets) { // experiment 0277's probe fix (exp 0310)
		if (probe_old_to_new.empty()) return offsets;
		std::vector<uint32_t> fwd;
		fwd.reserve(offsets.size());
		for (const uint32_t o: offsets) {
			if (o < probe_old_to_new.size() && probe_old_to_new[o] != ~0u) fwd.push_back(probe_old_to_new[o]);
		}
		return fwd;
	};
	auto r = g_dev->submit(std::span<const uint32_t>(sub_ib, sub_n), opt, 2'000'000'000ull, with_gds, qring);
	mec_back(r.executed_offsets);
'''),
        ('''	if (r.timed_out) timeout_probe(sub_ib, sub_n, kind, g_submits.load(), &r.executed_offsets); // experiment 0160
''', 1, '''	if (r.timed_out) { // experiment 0160; experiment 0277's probe fix (exp 0310): the executed offsets in the rebuilt IB
		const std::vector<uint32_t> ran_new = probe_ran(r.executed_offsets);
		timeout_probe(sub_ib, sub_n, kind, g_submits.load(), &ran_new);
	}
'''),
        ('''it.job.ran_copy = r.executed_offsets; } // experiment 0160
''', 1, '''it.job.ran_copy = probe_ran(r.executed_offsets); } // experiment 0160 (0277's probe fix, exp 0310: in the rebuilt IB)
'''),
        ('''					n_disp++;
				}
				if (op == 0x11 || op == 0x26 || op == 0x13 || op == 0x2a''', 1, '''					// Experiment 0310: for the leaf builder's dispatches in the hung buffer, the struct's node base and records now vs
					// the filter-time reading, the node extent vs the argument block, and record 1 now.
					if (op == 0x15 || op == 0x16) {
						static const uint64_t        leaf_pgm = x0310_env_pgm("BC5_DIRECT_LEAF_PGM", 0x909936c00ull);
						static std::atomic<uint32_t> n_x {0};
						const uint64_t pg = (static_cast<uint64_t>(pl) | (static_cast<uint64_t>(ph & 0xffu) << 32u)) << 8u;
						if (pl != 0xffffffffu && pg == leaf_pgm && n_x++ < 256) {
							const uint32_t u4 = g(st_sh, 0x244u), u5 = g(st_sh, 0x245u), u8 = g(st_sh, 0x248u);
							const uint64_t st = (u4 == 0xffffffffu || u5 == 0xffffffffu) ? 0 : (static_cast<uint64_t>(u4) | (static_cast<uint64_t>(u5 & 0xffffu) << 32u));
							LeafSnap       now = x0310_read(*pm, st, u8 == 0xffffffffu ? 0u : u8);
							LeafSnap       then;
							bool           have = false;
							{
								std::lock_guard<std::mutex> lk(g_x0310_m);
								for (auto it = g_x0310.rbegin(); it != g_x0310.rend(); ++it) {
									if (it->st == st) { then = *it; have = true; break; }
								}
							}
							const uint64_t node_lo = now.st_ok ? st + (static_cast<uint64_t>(now.h7c) << 6u) : 0;
							const uint64_t node_hi = now.st_ok ? node_lo + (static_cast<uint64_t>(now.h78) << 6u) : 0;
							const bool     covers  = now.st_ok && node_lo < st + 0x140u && node_hi > st + 0x100u;
							journal("timeout probe: leaf (exp 0310): dispatch at %u: struct 0x%" PRIx64 " %s: [0x7c] node base %u [0x78] records %u ud8 %u arr[ud8] %u now%s; nodes [0x%" PRIx64 ", 0x%" PRIx64 ") vs the argument block [0x%" PRIx64 ", +0x40): %s; record 1 now %08x %08x %08x%s\\n",
							        q, st, now.st_ok ? "read" : "NOT MAPPED", now.h7c, now.h78, now.ud8, now.arr_ud8,
							        have ? (then.h7c == now.h7c && then.h78 == now.h78 ? " (as at filter time)" : " (CHANGED since filter time)") : " (no filter-time reading)",
							        node_lo, node_hi, st + 0x100u, covers ? "NODES COVER THE COUNT RECORDS" : "apart", now.rec1[0], now.rec1[1], now.rec1[2],
							        have ? (then.rec1[0] == now.rec1[0] && then.rec1[1] == now.rec1[1] && then.rec1[2] == now.rec1[2] ? ", record 1 unchanged" : ", record 1 CHANGED") : "");
							if (have && (then.h7c != now.h7c || then.h78 != now.h78))
								journal("timeout probe: leaf (exp 0310):   at filter time (before #%" PRIu64 ", %.3f s ago): [0x7c] %u [0x78] %u record 1 %08x %08x %08x\\n", then.submit, x0310_now() - then.t, then.h7c, then.h78, then.rec1[0], then.rec1[1], then.rec1[2]);
						}
					}
					n_disp++;
				}
				if (op == 0x11 || op == 0x26 || op == 0x13 || op == 0x2a'''),
    ],
}


def main():
    if len(sys.argv) != 3:
        print('usage: patch0310.py <src root> <out dir>')
        sys.exit(2)
    root, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    diff = []
    for rel, edits in EDITS.items():
        path = os.path.join(root, rel)
        src = open(path, encoding='utf-8').read()
        print(f'{rel}: md5 {hashlib.md5(src.encode("utf-8")).hexdigest()[:8]} in')
        dst = src
        for k, (old, n, new) in enumerate(edits, 1):
            c = dst.count(old)
            if c != n:
                print(f'{rel}: edit {k}: anchor found {c} times, expected {n}:\n{old}')
                sys.exit(1)
            dst = dst.replace(old, new)
        target = os.path.join(out, os.path.basename(rel))
        open(target, 'w', encoding='utf-8', newline='\n').write(dst)
        diff += difflib.unified_diff(src.splitlines(True), dst.splitlines(True), 'a/' + rel, 'b/' + rel)
        print(f'{rel}: {len(edits)} edits -> {target}, md5 {hashlib.md5(dst.encode("utf-8")).hexdigest()[:8]} out')
    open(os.path.join(out, 'patch_0310.diff'), 'w', encoding='utf-8', newline='\n').write(''.join(diff))
    print(f'patch_0310.diff: {sum(1 for l in diff if l.startswith("+") and not l.startswith("+++"))} added lines')


if __name__ == '__main__':
    main()
