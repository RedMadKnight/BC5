#!/usr/bin/env python3
# BC5 exp 0439 (tag gv439, 11-25 night, the top session's census of what the GPU can reach). On the console a page of
# direct memory mapped without the GPU protection bits (KytyPlus memory.cpp: PROT_GPU_READ 0x10, PROT_GPU_WRITE 0x20)
# cannot be addressed by the GPU at all, so only GPU-mapped pages need a GPU mapping here; a CPU-only page need not be
# pinned. BC5 imports by the views of direct memory whatever their protection. With BC5_0439_GV_CENSUS=1 (normal build,
# off by default) a journal line every 10 s:
#   viewed bytes (union of file ranges) under views WITH a GPU bit and under views WITHOUT, and the bytes per protection
#   value (sizes summed);
#   pinned bytes (S.bos) in 2 MiB chunks covered by at least one GPU-mapped view, and in chunks covered by CPU-only views
#   alone (what an import rule "GPU-mapped views only" would not pin), with the size histogram of the latter runs.
# Applied after mkmg439.py (needs its census call site). Usage: python3 mkgv439.py <d2/new>
import os
import sys

p = os.path.join(sys.argv[1], 'bc5LleAgc.cpp')
s = open(p, 'rb').read().decode('utf-8', 'surrogateescape')
assert 'gv439' not in s and 'mg439_census' in s
crlf = '\r\n' in s
s = s.replace('\r\n', '\n')


def rep(a, b):
    global s
    assert s.count(a) == 1, (a[:70], s.count(a))
    s = s.replace(a, b)


rep('static void direct_sync_one(DState& S, bool force) {\n', r'''#ifndef BC5_LEAN
// exp 0439 (tag gv439): BC5_0439_GV_CENSUS=1, the GPU-mapped against CPU-only census line every 10 s (see mkgv439.py)
static void gv439_census(const DState& S) {
	static const bool on = [] {
		const char* e = std::getenv("BC5_0439_GV_CENSUS");
		return e != nullptr && e[0] == '1' && e[1] == 0;
	}();
	if (!on || S.kind != 0) return;
	static uint64_t last_ns = 0;
	const uint64_t  now     = SoftCp::now_ns();
	if (last_ns != 0 && now - last_ns < 10'000'000'000ull) return;
	last_ns = now;
	struct R { uint64_t off, size; int prot; };
	std::vector<R> rs;
	Libs::LibKernel::Memory::Bc5ForEachMappedRange(nullptr, &rs, [](uint64_t, uint64_t size, uint64_t offset, int type, int prot, const char*, void* ctx) {
		if (type == 0 && size != 0) static_cast<std::vector<R>*>(ctx)->push_back({offset, size, prot});
	});
	auto uni = [](std::vector<std::pair<uint64_t, uint64_t>>& v) {
		std::sort(v.begin(), v.end());
		std::vector<std::pair<uint64_t, uint64_t>> o;
		for (const auto& x: v) {
			if (!o.empty() && x.first <= o.back().second) o.back().second = std::max(o.back().second, x.second);
			else o.push_back(x);
		}
		v.swap(o);
	};
	std::vector<std::pair<uint64_t, uint64_t>> g, c;
	std::map<int, uint64_t> by_prot;
	for (const auto& r: rs) {
		((r.prot & 0x30) != 0 ? g : c).emplace_back(r.off, r.off + r.size);
		by_prot[r.prot] += r.size;
	}
	uni(g);
	uni(c);
	uint64_t gb = 0, cb = 0;
	for (const auto& x: g) gb += x.second - x.first;
	for (const auto& x: c) cb += x.second - x.first;
	// chunks covered by a GPU-mapped view
	std::set<uint64_t> gch;
	for (const auto& x: g)
		for (uint64_t k = x.first & ~(kDChunk - 1); k < x.second; k += kDChunk) gch.insert(k);
	uint64_t pin_g = 0, pin_c = 0;
	std::map<uint64_t, uint64_t> hist; // run size (MiB, power of two) -> count
	uint64_t run = 0;
	for (const auto& b: S.bos) {
		for (uint64_t k = b.off; k < b.off + b.size; k += kDChunk) {
			if (gch.count(k)) {
				pin_g += kDChunk;
				if (run) { uint64_t m = 1; while (m < (run >> 20)) m <<= 1; hist[m]++; run = 0; }
			} else {
				pin_c += kDChunk;
				run += kDChunk;
			}
		}
		if (run) { uint64_t m = 1; while (m < (run >> 20)) m <<= 1; hist[m]++; run = 0; }
	}
	std::string ps, hs;
	char t[64];
	for (const auto& [k, v]: by_prot) { std::snprintf(t, sizeof(t), " 0x%x:%.0f", k, static_cast<double>(v) / 1048576.0); ps += t; }
	for (const auto& [k, v]: hist) { std::snprintf(t, sizeof(t), " <=%" PRIu64 "M:%" PRIu64, k, v); hs += t; }
	journal("gv439 (exp 0439): t %.0f s: viewed GPU-mapped %.0f MiB, CPU-only %.0f MiB (union each); pinned %.0f MiB in chunks under a GPU-mapped view, %.0f MiB under CPU-only views alone; MiB per prot (summed):%s; CPU-only pinned runs:%s\n",
	        timing_now(), static_cast<double>(gb) / 1048576.0, static_cast<double>(cb) / 1048576.0, static_cast<double>(pin_g) / 1048576.0,
	        static_cast<double>(pin_c) / 1048576.0, ps.c_str(), hs.empty() ? " none" : hs.c_str());
}
#endif
static void direct_sync_one(DState& S, bool force) {
''')
rep('\tmg439_census(S, views, fd); // exp 0439 (tag mg439)\n', '\tmg439_census(S, views, fd); // exp 0439 (tag mg439)\n\tgv439_census(S); // exp 0439 (tag gv439)\n')
if crlf:
    s = s.replace('\n', '\r\n')
open(p, 'wb').write(s.encode('utf-8', 'surrogateescape'))
print('mkgv439: patched', p)
