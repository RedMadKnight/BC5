# BC5 experiment 0439 (tag pa439): the indirect-argument probe over the private bc5LleAgc.cpp (after mk439.py and the
# other generators; new/bc5LleAgc.cpp md5 31c06acb at the time of writing). Every replacement must match exactly once.
# Diagnostics only: BC5_0439_ARGS_PROBE=1 keeps, at the submit of a job with a compute-form DISPATCH_INDIRECT or a
# DMA_DATA, the host's view of the argument dwords and the DMA_DATA packets (bc5/pa0439.hpp) in a ring of the last 64
# such jobs; the timeout probe prints the timed-out job's entry beside the reads at the timeout and the mapping that
# covers each argument address, then and now. Nothing changes what is submitted; no waits; no journal line per frame.
#   python mkpa439.py <in bc5LleAgc.cpp> <out bc5LleAgc.cpp>
import sys

src, dst = sys.argv[1], sys.argv[2]


def rep(s, a, b, n=1):
    c = s.count(a)
    assert c == n, (a[:90], c)
    return s.replace(a, b)


s = open(src, encoding='utf-8', newline='').read()

GLUE = r'''// ---- BC5 experiment 0439 (tag pa439): the indirect-argument probe (bc5/pa0439.hpp) ----
namespace pa439 {
static bool on() {
	static const bool v = [] {
		const char* e  = std::getenv("BC5_0439_ARGS_PROBE");
		const bool  r  = e != nullptr && e[0] == '1' && e[1] == 0;
		std::fprintf(stderr, "[bc5] exp 0439 (tag pa439): BC5_0439_ARGS_PROBE=%d\n", r ? 1 : 0);
		return r;
	}();
	return v;
}
struct Where {
	bool     found = false;
	uint64_t va = 0, size = 0;
	bool     shared = false, readonly = false;
};
static Where where(const bc5::direct::MappingIndex& maps, uint64_t a) {
	Where w;
	auto  it = std::upper_bound(maps.begin(), maps.end(), a, [](uint64_t v, const bc5::direct::Mapping& m) { return v < m.va; });
	if (it == maps.begin()) return w;
	--it;
	if (a >= it->va + it->size) return w;
	w.found = true, w.va = it->va, w.size = it->size, w.shared = it->shared, w.readonly = it->readonly;
	return w;
}
struct Entry {
	bc5::pa439::Snap   snap;
	const char*        kind = "";
	uint32_t           dwords = 0;
	size_t             mappings = 0;
	std::vector<Where> at; // per indirect dispatch: the mapping that covered its arguments at the submit
	std::vector<uint32_t> ib; // exp 0439 (tag mi439): the job's dwords at the submit (the hung frame's jobs go to files)
	uint32_t vd[2][4] = {}, vb[2][4] = {}; // the V# at table 1 +0x120 and +0x130 and the first 16 bytes at each base
	bool     hvd[2] = {false, false}, hvb[2] = {false, false};
	uint32_t lab[2] = {~0u, ~0u}; // exp 0439 (tag lb439): 0x2000008020 and 0x2000008040 at this job's submit (~0: not readable)
};
constexpr size_t   kRing = 64;
static std::mutex  g_mutex;
static Entry       g_ring[kRing];
static size_t      g_next = 0;
static uint64_t    g_kept = 0;
// exp 0439 (tag gp439): the last three dcbs, top level and every chained or called piece as they were at the submit,
// and the dump session's count and draw records (the BVH build's indirect-dispatch counts, the terrain's draw
// arguments; addresses from the 09:42 run's dcb) read at each dcb's submit. Written to files at the timeout.
static constexpr uint64_t kGpRec[] = {0x507e636900ull, 0x507e627ac0ull, 0x507e63aa00ull, 0x500085d7c0ull, 0x5000000130ull,
                                      0x2009d86e00ull, 0x2009d86e20ull, 0x2009d86e40ull, 0x2009d86e60ull, 0x2009d86e80ull,
                                      0x2009d86ea0ull, 0x2009d86ec0ull, 0x500085d680ull, 0x500085d6a0ull, 0x5084b09480ull,
                                      0x5084b09520ull};
constexpr size_t      kGpN    = sizeof(kGpRec) / sizeof(kGpRec[0]);
struct DcbKeep {
	uint64_t                           n = ~0ull;
	double                             t = 0;
	uint32_t                           dwords = 0;
	std::vector<std::vector<uint32_t>> pieces; // [0] = the top level
	std::vector<uint64_t>              addr;   // each piece's address
	uint32_t                           rec[kGpN][5] = {};
	bool                               hrec[kGpN] = {};
};
static DcbKeep g_dcb[3];
static size_t  g_dcb_next = 0;
static void    dcb_keep(const uint32_t* ib, uint32_t n_dw, uint64_t n, const bc5::direct::MappingIndex& maps) {
	DcbKeep d;
	d.n = n, d.t = timing_now(), d.dwords = n_dw;
	const auto cr = bc5::ib_chain::collect(ib, n_dw, [&maps](uint64_t a, uint64_t b) { return covered_sorted(maps, a, b); }, true);
	for (const auto& pc : cr.pieces) {
		d.pieces.emplace_back(pc.src, pc.src + pc.n);
		d.addr.push_back(reinterpret_cast<uint64_t>(pc.src));
	}
	for (size_t k = 0; k < kGpN; k++)
		if (covered_sorted(maps, kGpRec[k], 20)) {
			const auto* t = reinterpret_cast<const volatile uint32_t*>(kGpRec[k]);
			for (int j = 0; j < 5; j++) d.rec[k][j] = t[j];
			d.hrec[k] = true;
		}
	std::lock_guard lk(g_mutex);
	g_dcb[g_dcb_next] = std::move(d);
	g_dcb_next        = (g_dcb_next + 1) % 3;
}
static void submit(const uint32_t* ib, uint32_t n_dw, const char* kind, uint64_t n, const bc5::direct::MappingIndex& maps) {
	if (!on() || ib == nullptr) return;
	if (std::strncmp(kind, "dcb", 3) == 0) dcb_keep(ib, n_dw, n, maps); // exp 0439 (tag gp439)
	auto s = bc5::pa439::scan(ib, n_dw, [&maps](uint64_t a, uint64_t b) { return covered_sorted(maps, a, b); });
	if (s.ind.empty() && s.dma.empty()) return;
	s.n = n, s.t = timing_now();
	Entry e;
	e.kind = kind, e.dwords = n_dw, e.mappings = maps.size();
	for (const auto& d : s.ind) e.at.push_back(where(maps, d.addr));
	e.ib.assign(ib, ib + n_dw);
	for (int j = 0; j < 2; j++) { // exp 0439 (tag lb439): the clouds part's two labels as memory holds them now
		const uint64_t a = j == 0 ? 0x2000008020ull : 0x2000008040ull;
		if (covered_sorted(maps, a, 4)) e.lab[j] = reinterpret_cast<const volatile uint32_t*>(a)[0];
	}
	for (const auto& d : s.ind) { // exp 0439 (tag mi439): the march loop's direction buffers at the submit
		if (d.table == 0) continue;
		for (int j = 0; j < 2; j++) {
			const uint64_t v = d.table + (j == 0 ? 0x120u : 0x130u);
			if (!covered_sorted(maps, v, 16)) continue;
			const auto* t = reinterpret_cast<const volatile uint32_t*>(v);
			for (int w = 0; w < 4; w++) e.vd[j][w] = t[w];
			e.hvd[j]            = true;
			const uint64_t base = static_cast<uint64_t>(e.vd[j][0]) | (static_cast<uint64_t>(e.vd[j][1] & 0xffffu) << 32u);
			if (base != 0 && covered_sorted(maps, base, 16)) {
				const auto* u = reinterpret_cast<const volatile uint32_t*>(base);
				for (int w = 0; w < 4; w++) e.vb[j][w] = u[w];
				e.hvb[j] = true;
			}
		}
		break;
	}
	e.snap = std::move(s);
	std::lock_guard lk(g_mutex);
	g_ring[g_next] = std::move(e);
	g_next         = (g_next + 1) % kRing;
	g_kept++;
}
static void timeout(uint64_t n) {
	if (!on() || !g_dev) return;
	const auto maps = g_dev->sorted_mappings();
	std::lock_guard lk(g_mutex);
	const Entry* e = nullptr;
	for (const auto& x : g_ring)
		if (x.snap.n == n) e = &x;
	if (e == nullptr) {
		journal("pa439: job #%" PRIu64 " not in the ring (%" PRIu64 " jobs kept; no indirect dispatch or DMA_DATA, or older than the last %zu)\n", n, g_kept, kRing);
		return;
	}
	const double now = timing_now();
	journal("pa439: job #%" PRIu64 " %s %u dwords, submitted at t %.3f s with %zu mappings; now t %.3f s with %zu mappings; %zu indirect dispatches, %zu DMA_DATA\n", n, e->kind,
	        e->dwords, e->snap.t, e->mappings, now, maps->size(), e->snap.ind.size(), e->snap.dma.size());
	for (const auto& d : e->snap.ind) // exp 0439 (tag mi439): each indirect dispatch's program and wave limit (from the job's bytes)
		journal("pa439: indirect at %u: program 0x%" PRIx64 ", COMPUTE_RESOURCE_LIMITS %s0x%x, table 1 0x%" PRIx64 ", table 2 0x%" PRIx64 "\n", d.q, d.pgm,
		        d.limits == ~0u ? "not set in this job, " : "", d.limits == ~0u ? 0u : d.limits, d.table, d.table2);
	{ // exp 0439 (tag mi439): the hung frame's jobs (this one and the ring's others of the last 100 ms) and the first indirect's tables, to files
		const auto put = [](const std::string& name, const volatile uint32_t* w, size_t n) {
			if (FILE* f = std::fopen(name.c_str(), "wb"); f != nullptr) {
				for (size_t i = 0; i < n; i++) {
					const uint32_t x = w[i];
					std::fwrite(&x, 4, 1, f);
				}
				std::fflush(f);
				fsync(fileno(f));
				std::fclose(f);
				journal("pa439: wrote %s (%zu dwords)\n", name.c_str(), n);
			}
		};
		const std::string dir = g_dump_dir.empty() ? std::string(std::getenv("HOME") ? std::getenv("HOME") : ".") + "/bc5-work" : g_dump_dir;
		for (const auto& x : g_ring) {
			if (x.snap.n == ~0ull || x.ib.empty() || (x.snap.t < e->snap.t - 0.1 && &x != e)) continue;
			put(dir + "/pa439-job-" + std::to_string(x.snap.n) + "-" + x.kind + "-" + std::to_string(x.dwords) + ".bin", x.ib.data(), x.ib.size());
		}
		for (const auto& d : e->snap.ind) {
			if (d.table == 0) continue;
			if (covered_sorted(*maps, d.table, 0x700)) put(dir + "/pa439-table1-" + std::to_string(n) + ".bin", reinterpret_cast<const volatile uint32_t*>(d.table), 0x700 / 4);
			if (d.table2 != 0 && covered_sorted(*maps, d.table2, 0x700)) put(dir + "/pa439-table2-" + std::to_string(n) + ".bin", reinterpret_cast<const volatile uint32_t*>(d.table2), 0x700 / 4);
			if (covered_sorted(*maps, d.table, 0x700)) { // exp 0439 (tag mi439): the loop's constants, named by the dump session
				const auto  f  = [&](uint32_t off) { float v; uint32_t w = reinterpret_cast<const volatile uint32_t*>(d.table + off)[0]; std::memcpy(&v, &w, 4); return v; };
				journal("pa439: indirect at %u: table 1 floats: bottom +0x32c %g, top +0x330 %g, scale +0x334 %g +0x338 %g, step scale +0x4b4 %g, growth +0x4b8 %g, "
				        "offsets +0x4c8 %g +0x4cc %g, height offset +0x4d0 %g, curvature +0x4d8 %g\n",
				        d.q, f(0x32c), f(0x330), f(0x334), f(0x338), f(0x4b4), f(0x4b8), f(0x4c8), f(0x4cc), f(0x4d0), f(0x4d8));
			}
			uint64_t bases[2] = {0, 0};
			for (int j = 0; j < 2; j++) {
				const uint64_t v = d.table + (j == 0 ? 0x120u : 0x130u);
				char           sub[160] = "not read at the submit", now[160] = "not readable";
				if (e->hvd[j])
					std::snprintf(sub, sizeof(sub), "V# %08x %08x %08x %08x, at its base %s%08x %08x %08x %08x", e->vd[j][0], e->vd[j][1], e->vd[j][2], e->vd[j][3],
					              e->hvb[j] ? "" : "(not readable) ", e->vb[j][0], e->vb[j][1], e->vb[j][2], e->vb[j][3]);
				if (covered_sorted(*maps, v, 16)) {
					const auto*    t    = reinterpret_cast<const volatile uint32_t*>(v);
					const uint64_t base = static_cast<uint64_t>(t[0]) | (static_cast<uint64_t>(t[1] & 0xffffu) << 32u);
					bases[j]            = base;
					uint32_t b[4]       = {0, 0, 0, 0};
					const bool hb       = base != 0 && covered_sorted(*maps, base, 16);
					if (hb)
						for (int w = 0; w < 4; w++) b[w] = reinterpret_cast<const volatile uint32_t*>(base)[w];
					std::snprintf(now, sizeof(now), "V# %08x %08x %08x %08x (base 0x%" PRIx64 ", stride %u, records %u), at its base %s%08x %08x %08x %08x", t[0], t[1], t[2], t[3], base,
					              (t[1] >> 16u) & 0x3fffu, t[2], hb ? "" : "(not readable) ", b[0], b[1], b[2], b[3]);
					if (hb) { // the direction as floats: x, y at byte 0, z at byte 8 (the dump session)
						float fx, fy, fz;
						std::memcpy(&fx, &b[0], 4), std::memcpy(&fy, &b[1], 4), std::memcpy(&fz, &b[2], 4);
						journal("pa439: indirect at %u: table 1 +0x%x base floats now: %g %g %g\n", d.q, j == 0 ? 0x120u : 0x130u, fx, fy, fz);
					}
				}
				journal("pa439: indirect at %u: table 1 +0x%x at the submit: %s\n", d.q, j == 0 ? 0x120u : 0x130u, sub);
				journal("pa439: indirect at %u: table 1 +0x%x now: %s\n", d.q, j == 0 ? 0x120u : 0x130u, now);
			}
			journal("pa439: indirect at %u: +0x120 and +0x130 %s the same buffer\n", d.q, bases[0] != 0 && bases[0] == bases[1] ? "ARE" : "are not");
			break;
		}
	}
	for (size_t k = 0; k < e->snap.ind.size(); k++) {
		const auto& d = e->snap.ind[k];
		const auto  w = where(*maps, d.addr);
		char        sub[48] = "not readable", cur[48] = "not readable";
		if (d.have) std::snprintf(sub, sizeof(sub), "%u x %u x %u", d.v[0], d.v[1], d.v[2]);
		if (d.addr != 0 && covered_sorted(*maps, d.addr, 12)) {
			const auto* t = reinterpret_cast<const volatile uint32_t*>(d.addr);
			std::snprintf(cur, sizeof(cur), "%u x %u x %u", t[0], t[1], t[2]);
		}
		const auto& a = e->at[k];
		journal("pa439: indirect at %u: arguments 0x%" PRIx64 ": at the submit %s, now %s; mapping then %s0x%" PRIx64 "+0x%" PRIx64 "%s, now %s0x%" PRIx64 "+0x%" PRIx64 "%s\n", d.q,
		        d.addr, sub, cur, a.found ? "" : "none ", a.va, a.size, a.shared ? " shared" : " userptr", w.found ? "" : "none ", w.va, w.size, w.shared ? " shared" : " userptr");
	}
	for (const auto& d : e->snap.ind) { // the first indirect dispatch's two 3D image descriptors (the dump session (exp 0440/0441): table +0x350, +0x38c)
		if (d.table == 0) continue;
		for (const uint64_t off : {0x350ull, 0x38cull, 0x540ull}) { // exp 0439 (tag mi439): +0x540 the 2D one
			const uint64_t x = d.table + off;
			char           b[128] = "not readable";
			if (covered_sorted(*maps, x, 32)) {
				const auto* t = reinterpret_cast<const volatile uint32_t*>(x);
				std::snprintf(b, sizeof(b), "%08x %08x %08x %08x %08x %08x %08x %08x", t[0], t[1], t[2], t[3], t[4], t[5], t[6], t[7]);
			}
			journal("pa439: indirect at %u: table 0x%" PRIx64 " +0x%" PRIx64 " now: %s\n", d.q, d.table, off, b);
			// exp 0439 (tag mi439): the first 16 dwords at the image's base (gfx10 image descriptor: dword 0 = base[39:8],
			// dword 1 bits 7:0 = base[47:40]; Mesa src/amd/registers/gfx10-rsrc.json SQ_IMG_RSRC_WORD0/1 at 0866ae7)
			if (covered_sorted(*maps, x, 8)) {
				const auto*    t    = reinterpret_cast<const volatile uint32_t*>(x);
				const uint64_t base = (static_cast<uint64_t>(t[0]) | (static_cast<uint64_t>(t[1] & 0xffu) << 32u)) << 8u;
				char           m[200] = "not readable";
				if (base != 0 && covered_sorted(*maps, base, 64)) {
					const auto* u = reinterpret_cast<const volatile uint32_t*>(base);
					int         o = 0;
					for (int j = 0; j < 16 && o < 190; j++) o += std::snprintf(m + o, sizeof(m) - o, "%08x ", u[j]);
				}
				journal("pa439: indirect at %u: image at +0x%" PRIx64 " base 0x%" PRIx64 ": %s\n", d.q, off, base, m);
			}
		}
		// exp 0439 (tag mi439): list A through the buffer descriptor at table +0x140 (the dump session: the group id x 4
		// indexes it; entry = cell x low 16, y high 16): the first 64 entries. V#: dword 0 base lo, dword 1 bits 15:0 base hi.
		if (const uint64_t v = d.table + 0x140; covered_sorted(*maps, v, 16)) {
			const auto*    t    = reinterpret_cast<const volatile uint32_t*>(v);
			const uint64_t base = static_cast<uint64_t>(t[0]) | (static_cast<uint64_t>(t[1] & 0xffffu) << 32u);
			journal("pa439: indirect at %u: list A V# %08x %08x %08x %08x, base 0x%" PRIx64 "\n", d.q, t[0], t[1], t[2], t[3], base);
			if (base != 0 && covered_sorted(*maps, base, 256)) {
				const auto* u = reinterpret_cast<const volatile uint32_t*>(base);
				for (int row = 0; row < 4; row++) {
					char m[200];
					int  o = 0;
					for (int j = 0; j < 16; j++) o += std::snprintf(m + o, sizeof(m) - o, "%08x ", u[row * 16 + j]);
					journal("pa439: list A [%d..%d]: %s\n", row * 16, row * 16 + 15, m);
				}
			}
		}
		break;
	}
	for (size_t k = 0; k < e->snap.dma.size(); k++) {
		const auto& d = e->snap.dma[k];
		char        cur[96] = "-";
		if ((d.dst_sel() == 0 || d.dst_sel() == 3) && d.dst() != 0 && covered_sorted(*maps, d.dst(), 16)) {
			const auto* t = reinterpret_cast<const volatile uint32_t*>(d.dst());
			std::snprintf(cur, sizeof(cur), "%08x %08x %08x %08x", t[0], t[1], t[2], t[3]);
		}
		journal("pa439: DMA_DATA %zu at %u: CP_SYNC %u SRC_SEL %u DST_SEL %u engine %u, source 0x%" PRIx64 ", destination 0x%" PRIx64 ", bytes %u (command 0x%08x, word 0x%08x); destination now %s\n", k,
		        d.q, d.cp_sync() ? 1u : 0u, d.src_sel(), d.dst_sel(), d.w[0] & 1u, d.src(), d.dst(), d.bytes(), d.w[5], d.w[0], cur);
	}
	{ // exp 0439 (tag lb439): the labels 0x2000008020 / 0x2000008040 at each kept job's submit, oldest first (the ring's 64 jobs)
		std::vector<const Entry*> v;
		for (const auto& x : g_ring)
			if (x.snap.n != ~0ull) v.push_back(&x);
		std::sort(v.begin(), v.end(), [](const Entry* a, const Entry* b) { return a->snap.n < b->snap.n; });
		std::string line;
		uint64_t    first1 = 0;
		double      first1_t = 0;
		for (const Entry* x : v) {
			char b[64];
			std::snprintf(b, sizeof(b), " #%" PRIu64 "@%.3f:%x/%x", x->snap.n, x->snap.t, x->lab[0], x->lab[1]);
			if (line.size() < 1400) line += b;
			if (first1 == 0 && x->lab[0] == 1u) first1 = x->snap.n, first1_t = x->snap.t;
		}
		journal("pa439: labels 0x2000008020/0x2000008040 at the submits:%s\n", line.c_str());
		if (first1 != 0) journal("pa439: 0x2000008020 first read 1 at the submit of #%" PRIu64 " (t %.3f s) among the ring's jobs\n", first1, first1_t);
		else journal("pa439: 0x2000008020 never read 1 at the ring's submits\n");
	}
	{ // exp 0439 (tag ad439): the TF ring values the prefix programs (tf_ring_prefix): VGT_TF_RING_SIZE = size / 4
		// (bytes to dwords), VGT_TF_MEMORY_BASE = base >> 8, _HI = base >> 40, VGT_HS_OFFCHIP_PARAM (when written)
		uint64_t b = 0, o0 = 0, o1 = 0, o2 = 0;
		uint32_t sz = 0;
		Bc5TfRingState(&b, &sz, &o0, &o1, &o2);
		const uint64_t gb = g_gc_tf_base.load(), go = g_gc_hs_offchip.load();
		const uint32_t gs = g_gc_tf_size.load();
		journal("pa439: ad439 tf ring: SetTFRing base 0x%" PRIx64 " size 0x%x; /dev/gc base 0x%" PRIx64 " size 0x%x (bytes) -> VGT_TF_RING_SIZE 0x%x dwords, "
		        "VGT_TF_MEMORY_BASE 0x%x, _HI 0x%x; offchip SetHs 0x%" PRIx64 " /dev/gc 0x%" PRIx64 " (received %d); ring on %d, offchip row %d\n",
		        b, sz, gb, gs, static_cast<uint32_t>(std::min<uint64_t>((b && sz ? sz : gs) / 4, 0xffffu)), static_cast<uint32_t>((b && sz ? b : gb) >> 8u),
		        static_cast<uint32_t>((b && sz ? b : gb) >> 40u) & 0xffu, o0, go & 0xffffffffull, static_cast<int>(go >> 32u), gc_tf_ring_on() ? 1 : 0, gc_hs_offchip_on() ? 1 : 0);
	}
	{ // exp 0439 (tag gp439): the last three dcbs to files, and the records at their submits and now
		const std::string dir = g_dump_dir.empty() ? std::string(std::getenv("HOME") ? std::getenv("HOME") : ".") + "/bc5-work" : g_dump_dir;
		// exp 0439 (tag gp439 v2): at 10:42 the fault record ended the process while this block wrote 98 piece files with an
		// fsync each, so only the oldest dcb's lines came out. Now: the journal lines first, the newest dcb first, then
		// lr439/ia439 and the records now, and the piece files last, with no fsync per file.
		const DcbKeep* gp_order[3] = {&g_dcb[0], &g_dcb[1], &g_dcb[2]};
		std::sort(gp_order, gp_order + 3, [](const DcbKeep* a, const DcbKeep* b) { return (a->n == ~0ull ? 0 : a->n + 1) > (b->n == ~0ull ? 0 : b->n + 1); });
		for (const DcbKeep* dp : gp_order) {
			const DcbKeep& d = *dp;
			if (d.n == ~0ull) continue;
			size_t total = 0;
			for (size_t k = 0; k < d.pieces.size(); k++) total += d.pieces[k].size();
			journal("pa439: gp439 dcb #%" PRIu64 " %u dwords submitted at t %.3f s: %zu pieces (%zu dwords) to %s/pa439-dcb-%" PRIu64 "-piece-*.bin\n", d.n, d.dwords, d.t,
			        d.pieces.size(), total, dir.c_str(), d.n);
			{ // exp 0439 (tag ad439): piece k at address, dwords
				std::string al;
				for (size_t k = 0; k < d.pieces.size() && k < d.addr.size(); k++) {
					char b[64];
					std::snprintf(b, sizeof(b), " %zu@0x%" PRIx64 "+%zu", k, d.addr[k], d.pieces[k].size());
					al += b;
					if (al.size() > 900) {
						journal("pa439: ad439 dcb #%" PRIu64 " pieces:%s\n", d.n, al.c_str());
						al.clear();
					}
				}
				if (!al.empty()) journal("pa439: ad439 dcb #%" PRIu64 " pieces:%s\n", d.n, al.c_str());
			}
			for (size_t k = 0; k < kGpN; k++)
				if (d.hrec[k])
					journal("pa439: gp439 dcb #%" PRIu64 " record 0x%" PRIx64 " at its submit: %08x %08x %08x %08x %08x\n", d.n, kGpRec[k], d.rec[k][0], d.rec[k][1], d.rec[k][2],
					        d.rec[k][3], d.rec[k][4]);
		}
		// exp 0439 (tag lr439): the targets of the newest kept dcb's LOAD_SH/UCONFIG/CONTEXT_REG_INDEX packets (0x63, 0x64,
		// 0x9f; dwords 1/2 the table's address, dword 4 bits 13:0 the pair count; the register-table form the probe's ud
		// scan reads), and the driver's tables at 0xfe0011000 and 0xfe00425d8 (the dump session), as they are now.
		{
			const DcbKeep* last = nullptr;
			for (const auto& d : g_dcb)
				if (d.n != ~0ull && (last == nullptr || d.n > last->n)) last = &d;
			const auto put = [&](const std::string& name, uint64_t a, uint64_t bytes) {
				if (a == 0 || bytes == 0 || bytes > 0x10000 || !covered_sorted(*maps, a, bytes)) return false;
				if (FILE* f = std::fopen(name.c_str(), "wb"); f != nullptr) {
					std::vector<uint32_t> c(bytes / 4);
					for (size_t i = 0; i < c.size(); i++) c[i] = reinterpret_cast<const volatile uint32_t*>(a)[i];
					std::fwrite(c.data(), 4, c.size(), f);
					std::fclose(f);
					return true;
				}
				return false;
			};
			size_t ntab = 0, nok = 0;
			if (last != nullptr)
				for (size_t k = 0; k < last->pieces.size(); k++) {
					const auto& w = last->pieces[k];
					for (uint32_t q = 0; q < w.size();) {
						const uint32_t h = w[q], ty = h >> 30u;
						uint32_t       len = 1;
						if (ty == 3 || ty == 0) {
							const uint32_t c = (h >> 16u) & 0x3fffu;
							len = c == 0x3fffu ? 1 : c + 2;
						}
						if (q + len > w.size()) break;
						const uint32_t op = (h >> 8u) & 0xffu;
						if (ty == 3 && (op == 0x63 || op == 0x64 || op == 0x9f) && len >= 5 && ntab < 400) {
							const uint64_t a  = (w[q + 1] & ~3u) | (static_cast<uint64_t>(w[q + 2] & 0xffffu) << 32u);
							const uint32_t np = w[q + 4] & 0x3fffu;
							const bool     pairs = (w[q + 3] >> 31u) != 0;
							const uint64_t bytes = pairs ? static_cast<uint64_t>(np) * 8u : static_cast<uint64_t>(np) * 4u;
							ntab++;
							if (put(dir + "/pa439-lri-" + std::to_string(last->n) + "-p" + std::to_string(k) + "-" + std::to_string(q) + "-op" + std::to_string(op) + ".bin", a, bytes)) nok++;
						}
						q += len;
					}
				}
			if (last != nullptr) { // exp 0439 (tag ia439)
				uint64_t    base = 0;
				std::string al;
				size_t      ni = 0;
				uint32_t    hs10 = 0, hs11 = 0;
				bool        h10 = false, h11 = false;
				for (size_t k = 0; k < last->pieces.size(); k++) {
					const auto& w = last->pieces[k];
					for (uint32_t q = 0; q < w.size();) {
						const uint32_t h = w[q], ty = h >> 30u;
						uint32_t       len = 1;
						if (ty == 3 || ty == 0) {
							const uint32_t c = (h >> 16u) & 0x3fffu;
							len = c == 0x3fffu ? 1 : c + 2;
						}
						if (q + len > w.size()) break;
						const uint32_t op = (h >> 8u) & 0xffu;
						if (ty == 3 && op == 0x11 && len >= 4 && (w[q + 1] & 0xfu) == 1u) base = (w[q + 2] & ~7u) | (static_cast<uint64_t>(w[q + 3] & 0xffffu) << 32u);
						if (ty == 3 && (op == 0x76 || op == 0x69 || op == 0x79) && len >= 3) {
							const uint32_t first = w[q + 1] & 0xffffu;
							std::string    rl;
							for (uint32_t j = 0; j + 2 < len; j++) {
								const uint32_t ro = first + j, rv = w[q + 2 + j];
								if (op == 0x76 && ro == 0x116u) hs10 = rv, h10 = true;
								if (op == 0x76 && ro == 0x117u) hs11 = rv, h11 = true;
								if ((op == 0x69 && (ro == 0x2d5u || ro == 0x2d6u)) || (op == 0x79 && ro == 0x242u) || (op == 0x76 && (ro == 0x116u || ro == 0x117u))) {
									char b[40];
									std::snprintf(b, sizeof(b), " 0x%x=%08x", ro, rv);
									rl += b;
								}
							}
							if (!rl.empty() && ni < 300) journal("pa439: ia439 dcb #%" PRIu64 " p%zu:%u op 0x%x direct:%s\n", last->n, k, q, op, rl.c_str());
						}
						if (ty == 3 && (op == 0x16 || op == 0x24 || op == 0x25) && len >= 2 && ni < 300) {
							const uint64_t a  = base + w[q + 1];
							const uint32_t nw = op == 0x16 ? 3u : 5u;
							char           b[160];
							int            o = op == 0x16 ? std::snprintf(b, sizeof(b), " p%zu:%u:di@%" PRIx64 "=", k, q, a)
							                              : std::snprintf(b, sizeof(b), " p%zu:%u:%s[hs %" PRIx64 "]@%" PRIx64 "=", k, q, op == 0x24 ? "dr" : "dx",
							                                              h10 && h11 ? (hs10 | (static_cast<uint64_t>(hs11 & 0xffffu) << 32u)) : 0ull, a);
							if (base != 0 && covered_sorted(*maps, a, nw * 4)) {
								const auto* t = reinterpret_cast<const volatile uint32_t*>(a);
								for (uint32_t j = 0; j < nw; j++) o += std::snprintf(b + o, sizeof(b) - o, "%s%x", j ? "," : "", t[j]);
							} else {
								std::snprintf(b + o, sizeof(b) - o, "unreadable");
							}
							al += b;
							ni++;
							if (al.size() > 900) {
								journal("pa439: ia439 dcb #%" PRIu64 " indirect args now:%s\n", last->n, al.c_str());
								al.clear();
							}
						}
						if (ty == 3 && (op == 0x63 || op == 0x64 || op == 0x9f) && len >= 5 && (w[q + 3] >> 31u) != 0) {
							const uint64_t ta = (w[q + 1] & ~3u) | (static_cast<uint64_t>(w[q + 2] & 0xffffu) << 32u);
							const uint32_t tn = w[q + 4] & 0x3fffu;
							if (ta != 0 && tn != 0 && tn <= 4096 && covered_sorted(*maps, ta, static_cast<uint64_t>(tn) * 8)) {
								const auto* t = reinterpret_cast<const volatile uint32_t*>(ta);
								std::string rl;
								for (uint32_t j = 0; j < tn; j++) {
									const uint32_t ro = t[2 * j] & 0xffffu, rv = t[2 * j + 1];
									if (op == 0x63 && ro == 0x116u) hs10 = rv, h10 = true;
									if (op == 0x63 && ro == 0x117u) hs11 = rv, h11 = true;
									if ((op == 0x9f && (ro == 0x2d5u || ro == 0x2d6u)) || (op == 0x64 && ro == 0x242u) || (op == 0x63 && (ro == 0x116u || ro == 0x117u))) {
										char b[40];
										std::snprintf(b, sizeof(b), " 0x%x=%08x", ro, rv);
										rl += b;
									}
								}
								if (!rl.empty()) journal("pa439: ia439 dcb #%" PRIu64 " p%zu:%u op 0x%x table 0x%" PRIx64 " (%u pairs):%s\n", last->n, k, q, op, ta, tn, rl.c_str());
							}
						}
						q += len;
					}
				}
				if (!al.empty() || ni == 0) journal("pa439: ia439 dcb #%" PRIu64 " indirect args now:%s (%zu)\n", last->n, al.c_str(), ni);
				if (h10 && h11) {
					const uint64_t hp = hs10 | (static_cast<uint64_t>(hs11 & 0xffffu) << 32u);
					if (hp != 0 && covered_sorted(*maps, hp, 0x40)) {
						const auto* t = reinterpret_cast<const volatile uint32_t*>(hp);
						char        m[200];
						int         o = 0;
						for (uint32_t j = 0; j < 16; j++) o += std::snprintf(m + o, sizeof(m) - o, "%08x ", t[j]);
						journal("pa439: ia439 hull user data 10/11 (last loaded) 0x%" PRIx64 ": %s\n", hp, m);
					} else {
						journal("pa439: ia439 hull user data 10/11 (last loaded) 0x%" PRIx64 " not readable\n", hp);
					}
				} else {
					journal("pa439: ia439 hull user data 10/11 not in the dcb's SH tables (%d %d)\n", h10 ? 1 : 0, h11 ? 1 : 0);
				}
			}
			const bool d1 = put(dir + "/pa439-fe0011000.bin", 0xfe0011000ull, 0x1000);
			const bool d2 = put(dir + "/pa439-fe00425d8.bin", 0xfe00425d8ull, 0x400);
			journal("pa439: lr439 dcb #%" PRIu64 ": %zu register-table packets, %zu tables written; driver tables 0xfe0011000 %s, 0xfe00425d8 %s\n", last ? last->n : 0ull, ntab, nok,
			        d1 ? "written" : "not readable", d2 ? "written" : "not readable");
		}
		for (size_t k = 0; k < kGpN; k++)
			if (covered_sorted(*maps, kGpRec[k], 20)) {
				const auto* t = reinterpret_cast<const volatile uint32_t*>(kGpRec[k]);
				journal("pa439: gp439 record 0x%" PRIx64 " now: %08x %08x %08x %08x %08x\n", kGpRec[k], t[0], t[1], t[2], t[3], t[4]);
			} else {
				journal("pa439: gp439 record 0x%" PRIx64 " not readable now\n", kGpRec[k]);
			}
		for (const DcbKeep* dp : gp_order) { // exp 0439 (tag gp439 v2): the piece files last, newest dcb first
			const DcbKeep& d = *dp;
			if (d.n == ~0ull) continue;
			for (size_t k = 0; k < d.pieces.size(); k++) {
				const std::string name = dir + "/pa439-dcb-" + std::to_string(d.n) + "-piece-" + std::to_string(k) + "-" + std::to_string(d.pieces[k].size()) + ".bin";
				if (FILE* f = std::fopen(name.c_str(), "wb"); f != nullptr) {
					std::fwrite(d.pieces[k].data(), 4, d.pieces[k].size(), f);
					std::fclose(f);
				}
			}
			journal("pa439: gp439 dcb #%" PRIu64 " piece files written\n", d.n);
		}
	}
	for (const auto& x : g_ring) { // exp 0439 (tag gp439): every dispatch of the hung frame's jobs: offset, program, table
		if (x.snap.n == ~0ull || x.ib.empty() || (x.snap.t < e->snap.t - 0.1 && &x != e)) continue;
		uint32_t    pl = 0, ph = 0, u0 = 0, u1 = 0;
		std::string line;
		size_t      nd = 0;
		for (uint32_t q = 0; q < x.ib.size();) {
			const uint32_t h = x.ib[q], ty = h >> 30u;
			uint32_t       len = 1;
			if (ty == 3 || ty == 0) {
				const uint32_t c = (h >> 16u) & 0x3fffu;
				len = c == 0x3fffu ? 1 : c + 2;
			}
			if (q + len > x.ib.size()) break;
			const uint32_t op = (h >> 8u) & 0xffu;
			if (ty == 3 && op == 0x76 && len >= 3) {
				const uint32_t off = x.ib[q + 1] & 0xffffu;
				for (uint32_t k = 0; k + 2 < len; k++) {
					if (off + k == 0x20cu) pl = x.ib[q + 2 + k];
					if (off + k == 0x20du) ph = x.ib[q + 2 + k];
					if (off + k == 0x240u) u0 = x.ib[q + 2 + k];
					if (off + k == 0x241u) u1 = x.ib[q + 2 + k];
				}
			}
			if (ty == 3 && (op == 0x15 || op == 0x16)) {
				char b[80];
				std::snprintf(b, sizeof(b), " %u:%s%" PRIx64 "/%" PRIx64, q, op == 0x16 ? "i" : "d", (static_cast<uint64_t>(pl) | (static_cast<uint64_t>(ph & 0xffu) << 32u)) << 8u,
				              u0 | (static_cast<uint64_t>(u1 & 0xffffu) << 32u));
				nd++;
				line += b;
				if (line.size() > 900) {
					journal("pa439: gp439 job #%" PRIu64 " %s %u dispatches (offset:d|i program/table):%s\n", x.snap.n, x.kind, x.dwords, line.c_str());
					line.clear();
				}
			}
			q += len;
		}
		if (!line.empty() || nd == 0) journal("pa439: gp439 job #%" PRIu64 " %s %u dispatches (offset:d|i program/table):%s (%zu)\n", x.snap.n, x.kind, x.dwords, line.c_str(), nd);
	}
	// exp 0439 (tag vg439): the volume generator 0x8000403d00 (the clouds part's first dispatch; the dump session: two
	// counted loops, the count a signed dword at its table +0x108) in every job of the ring's last 100 ms: its table and the
	// dwords the dump session named, at the timeout. The walk tracks COMPUTE_PGM_LO/HI and COMPUTE_USER_DATA_0/1 as
	// pa0439.hpp's scan does, over each job's top-level dwords.
	for (const auto& x : g_ring) {
		if (x.snap.n == ~0ull || x.ib.empty() || (x.snap.t < e->snap.t - 0.1 && &x != e)) continue;
		uint32_t pl = 0, ph = 0, u0 = 0, u1 = 0;
		for (uint32_t q = 0; q < x.ib.size();) {
			const uint32_t h = x.ib[q], ty = h >> 30u;
			uint32_t       len = 1;
			if (ty == 3 || ty == 0) {
				const uint32_t c = (h >> 16u) & 0x3fffu;
				len = c == 0x3fffu ? 1 : c + 2;
			}
			if (q + len > x.ib.size()) break;
			const uint32_t op = (h >> 8u) & 0xffu;
			if (ty == 3 && op == 0x76 && len >= 3) {
				const uint32_t off = x.ib[q + 1] & 0xffffu;
				for (uint32_t k = 0; k + 2 < len; k++) {
					if (off + k == 0x20cu) pl = x.ib[q + 2 + k];
					if (off + k == 0x20du) ph = x.ib[q + 2 + k];
					if (off + k == 0x240u) u0 = x.ib[q + 2 + k];
					if (off + k == 0x241u) u1 = x.ib[q + 2 + k];
				}
			}
			const uint64_t pgm = (static_cast<uint64_t>(pl) | (static_cast<uint64_t>(ph & 0xffu) << 32u)) << 8u;
			if (ty == 3 && (op == 0x15 || op == 0x16) && pgm == 0x8000403d00ull) {
				const uint64_t tb = u0 | (static_cast<uint64_t>(u1 & 0xffffu) << 32u);
				if (tb != 0 && covered_sorted(*maps, tb, 0x130)) {
					const auto* t  = reinterpret_cast<const volatile uint32_t*>(tb);
					const auto  fl = [t](uint32_t off) { float v; const uint32_t w = t[off / 4]; std::memcpy(&v, &w, 4); return v; };
					journal("pa439: vg439 job #%" PRIu64 " %s %u at %u: program 0x8000403d00, table 0x%" PRIx64 ": +0x108 count %d (0x%08x), +0xf0 %g +0xf4 %g +0xf8 %g, +0x124 %g\n", x.snap.n,
					        x.kind, x.dwords, q, tb, static_cast<int32_t>(t[0x108 / 4]), t[0x108 / 4], fl(0xf0), fl(0xf4), fl(0xf8), fl(0x124));
					for (const uint32_t off : {0x0u, 0x60u, 0xc0u, 0xe0u}) {
						const uint32_t n8 = off == 0xe0u ? 4u : 8u;
						char           m[120];
						int            o = 0;
						for (uint32_t j = 0; j < n8; j++) o += std::snprintf(m + o, sizeof(m) - o, "%08x ", t[off / 4 + j]);
						journal("pa439: vg439 job #%" PRIu64 " at %u: table +0x%x %s: %s\n", x.snap.n, q, off, off == 0xe0u ? "sampler" : off == 0xc0u ? "stored image" : "sampled image", m);
					}
				} else {
					journal("pa439: vg439 job #%" PRIu64 " at %u: program 0x8000403d00, table 0x%" PRIx64 " not readable\n", x.snap.n, q, tb);
				}
				break; // the first one per job
			}
			q += len;
		}
	}
	// The other jobs with an indirect dispatch submitted in the 100 ms before this one (the dump session's (exp 0440/0441) question: which
	// job a second queue standing behind a DISPATCH_INDIRECT runs): number, kind, size, the offsets and the group counts.
	for (const auto& x : g_ring) {
		if (&x == e || x.snap.n == ~0ull || x.snap.ind.empty() || x.snap.t < e->snap.t - 0.1) continue;
		std::string line;
		for (const auto& d : x.snap.ind) {
			char b[64];
			if (d.have) std::snprintf(b, sizeof(b), " %u:%ux%ux%u", d.q, d.v[0], d.v[1], d.v[2]);
			else std::snprintf(b, sizeof(b), " %u:?", d.q);
			if (line.size() < 600) line += b;
		}
		journal("pa439: nearby job #%" PRIu64 " %s %u dwords at t %.3f s: %zu indirect (offset:groups at the submit)%s\n", x.snap.n, x.kind, x.dwords, x.snap.t, x.snap.ind.size(), line.c_str());
	}
}
// exp 0439 (tag uw439): the last 1024 completions the finisher saw (submission number, OK), and at each watchdog
// point the memory waits of the newest kept dcb (every piece) whose condition does not hold now, with the jobs of the
// ring (g_ring, top level) that write that label and their state.
static std::mutex g_done_m;
static uint64_t   g_done_n[1024] = {};
static uint8_t    g_done_ok[1024] = {};
static uint64_t   g_done_i = 0;
static void       done(uint64_t n, bool ok) {
    std::lock_guard lk(g_done_m);
    g_done_n[g_done_i % 1024] = n + 1, g_done_ok[g_done_i % 1024] = ok ? 1 : 0;
    g_done_i++;
}
static const char* state_of(uint64_t n) {
	std::lock_guard lk(g_done_m);
	for (size_t k = 0; k < 1024; k++)
		if (g_done_n[k] == n + 1) return g_done_ok[k] ? "done OK" : "done FAILED";
	return "not done (or not among the last 1024 completions)";
}
static bool cond_holds(uint32_t fn, uint32_t v, uint32_t ref) {
	switch (fn & 7u) {
	case 0: return true;
	case 1: return v < ref;
	case 2: return v <= ref;
	case 3: return v == ref;
	case 4: return v != ref;
	case 5: return v >= ref;
	case 6: return v > ref;
	default: return false;
	}
}
static bool safe_read32(uint64_t a, uint32_t& v) { // exp 0439 (tag un439): no lock, no fault
	struct iovec lo {&v, 4}, re {reinterpret_cast<void*>(a), 4};
	return process_vm_readv(getpid(), &lo, 1, &re, 1, 0) == 4;
}
// exp 0439 (tag px439): the compute SH registers (0x200-0x24f) in the newest full prefix built for a dcb (submit_split)
static std::mutex g_px_m;
static uint32_t   g_px_v[0x50] = {};
static bool       g_px_set[0x50] = {};
static double     g_px_t = -1;
static void       note_prefix(const std::vector<uint32_t>& p) {
    uint32_t v[0x50] = {};
    bool     st[0x50] = {};
    for (size_t q = 0; q < p.size();) {
        const uint32_t h = p[q], ty = h >> 30u;
        uint32_t       len = 1;
        if (ty == 3 || ty == 0) {
            const uint32_t c = (h >> 16u) & 0x3fffu;
            len = c == 0x3fffu ? 1 : c + 2;
        }
        if (q + len > p.size()) break;
        if (ty == 3 && ((h >> 8u) & 0xffu) == 0x76 && len >= 3)
            for (uint32_t j = 0; j + 2 < len; j++) {
                const uint32_t ro = (p[q + 1] & 0xffffu) + j;
                if (ro >= 0x200 && ro < 0x250) v[ro - 0x200] = p[q + 2 + j], st[ro - 0x200] = true;
            }
        q += len;
    }
    std::lock_guard lk(g_px_m);
    std::memcpy(g_px_v, v, sizeof(v));
    std::memcpy(g_px_set, st, sizeof(st));
    g_px_t = timing_now();
}
static bool safe_read32(uint64_t a, uint32_t& v);
// exp 0439 (tag rs439): walk the dcb's pieces in order; SET_SH_REG (0x76), LOAD_SH_REG (0x5f: address, then offset/count
// pairs) and LOAD_SH_REG_INDEX (0x63, pair tables) into a 0x200-0x24f image; at each dispatch (0x15, 0x16) a snapshot;
// the last one journaled with where each register was set, or "inherited" (nowhere in this dcb before it).
static void dispatch_state(const DcbKeep& last) {
	uint32_t v[0x50] = {}, sv[0x50] = {};
	int32_t  wp[0x50], swp[0x50];
	uint32_t wq[0x50] = {}, swq[0x50] = {};
	for (auto& x : wp) x = -1;
	for (auto& x : swp) x = -1;
	int      dk = -1;
	uint32_t dq = 0, dop = 0, doff = 0;
	size_t   n_unread = 0; // exp 0439 (tag sc439): pair tables unreadable so far in the walk
	uint64_t sx_ta = 0;    // exp 0439 (tag sx439): the last LOAD_SH_REG_INDEX table and its pair count
	uint32_t sx_tn = 0, sx_k = 0, sx_q = 0;
	uint64_t base = 0, sbase = 0;
	auto     put = [&](uint32_t ro, uint32_t val, int k, uint32_t q) {
        if (ro >= 0x200 && ro < 0x250) v[ro - 0x200] = val, wp[ro - 0x200] = k, wq[ro - 0x200] = q;
	};
	for (size_t k = 0; k < last.pieces.size(); k++) {
		const auto& w = last.pieces[k];
		for (uint32_t q = 0; q < w.size();) {
			const uint32_t h = w[q], ty = h >> 30u;
			uint32_t       len = 1;
			if (ty == 3 || ty == 0) {
				const uint32_t c = (h >> 16u) & 0x3fffu;
				len = c == 0x3fffu ? 1 : c + 2;
			}
			if (q + len > w.size()) break;
			const uint32_t op = (h >> 8u) & 0xffu;
			if (ty == 3 && op == 0x76 && len >= 3)
				for (uint32_t j = 0; j + 2 < len; j++) put((w[q + 1] & 0xffffu) + j, w[q + 2 + j], static_cast<int>(k), q);
			if (ty == 3 && op == 0x5f && len >= 5) {
				const uint64_t a = (w[q + 1] & ~3u) | (static_cast<uint64_t>(w[q + 2] & 0xffffu) << 32u);
				for (uint32_t j = 3; j + 1 < len; j += 2) {
					const uint32_t ro = w[q + j] & 0xffffu, cnt = w[q + j + 1] & 0x3fffu;
					for (uint32_t i = 0; i < cnt && i < 0x50; i++) {
						uint32_t val = 0;
						if (safe_read32(a + 4ull * (ro + i - 0x0), val)) put(ro + i, val, static_cast<int>(k), q); // TODO(verify): LOAD_SH_REG's table indexing
					}
				}
			}
			if (ty == 3 && op == 0x63 && len >= 5 && (w[q + 3] >> 31u) != 0) {
				const uint64_t ta = (w[q + 1] & ~3u) | (static_cast<uint64_t>(w[q + 2] & 0xffffu) << 32u);
				const uint32_t tn = w[q + 4] & 0x3fffu;
				uint32_t       got = 0;
				sx_ta = ta, sx_tn = tn, sx_k = static_cast<uint32_t>(k), sx_q = q; // exp 0439 (tag sx439)
				for (uint32_t i = 0; i < tn && i < 4096; i++, got++) {
					uint32_t ro = 0, val = 0;
					if (!safe_read32(ta + 8ull * i, ro) || !safe_read32(ta + 8ull * i + 4, val)) break;
					put(ro & 0xffffu, val, static_cast<int>(k), q);
				}
				if (got < tn) { // exp 0439 (tag sc439)
					n_unread++;
					journal("pa439: sc439 dcb #%" PRIu64 " piece %zu dword %u: LOAD_SH_REG_INDEX table 0x%" PRIx64 " (%u pairs) UNREADABLE at the trigger after %u pairs\n", last.n, k, q, ta, tn, got);
				}
			}
			if (ty == 3 && op == 0x76 && len >= 3) { // exp 0439 (tag sc439): the table-free markers of a scratch binding
				const uint32_t first = w[q + 1] & 0xffffu;
				if (first <= 0x218u && first + (len - 2) > 0x218u && w[q + 2 + (0x218u - first)] != 0)
					journal("pa439: sc439 dcb #%" PRIu64 " piece %zu dword %u: SET_SH_REG COMPUTE_TMPRING_SIZE = 0x%08x\n", last.n, k, q, w[q + 2 + (0x218u - first)]);
				if (first == 0x240u && len - 2 >= 4)
					if (w[q + 4] != 0 || w[q + 5] != 0)
						journal("pa439: sc439 dcb #%" PRIu64 " piece %zu dword %u: SET_SH_REG USER_DATA_0-3 = 0x%08x 0x%08x 0x%08x 0x%08x%s\n", last.n, k, q, w[q + 2], w[q + 3], w[q + 4], w[q + 5],
						        w[q + 4] == 0x1000u && w[q + 5] == 0x50u ? " (the cloth form's scratch table 0x5000001000)" : "");
			}
			if (ty == 3 && op == 0x11 && len >= 4 && (w[q + 1] & 0xfu) == 1u) base = (w[q + 2] & ~7u) | (static_cast<uint64_t>(w[q + 3] & 0xffffu) << 32u);
			if (ty == 3 && (op == 0x15 || op == 0x16)) {
				std::memcpy(sv, v, sizeof(v)), std::memcpy(swp, wp, sizeof(wp)), std::memcpy(swq, wq, sizeof(wq));
				dk = static_cast<int>(k), dq = q, dop = op, doff = len >= 2 ? w[q + 1] : 0, sbase = base;
				if (((v[0x213 - 0x200] & 1u) != 0 && wp[0x213 - 0x200] >= 0) || (wp[0x242 - 0x200] >= 0 && v[0x242 - 0x200] == 0x10000u && v[0x243 - 0x200] == 0x20u)) { // exp 0439 (tag sx439)
					std::string l;
					char        b[64];
					for (uint32_t i = 0; i < sx_tn && i < 16; i++) {
						uint32_t ro = 0, val = 0;
						if (safe_read32(sx_ta + 8ull * i, ro) && safe_read32(sx_ta + 8ull * i + 4, val)) std::snprintf(b, sizeof(b), " 0x%x=0x%08x", ro & 0xffffu, val);
						else std::snprintf(b, sizeof(b), " unreadable");
						l += b;
					}
					const uint64_t ud = static_cast<uint64_t>(v[0x242 - 0x200]) | (static_cast<uint64_t>(v[0x243 - 0x200]) << 32u);
					std::string    qw;
					for (uint32_t i = 0; i < 16; i++) {
						uint32_t x = 0;
						if (ud != 0 && safe_read32(ud + 4ull * i, x)) std::snprintf(b, sizeof(b), " %08x", x);
						else std::snprintf(b, sizeof(b), " ?");
						qw += b;
					}
					journal("pa439: sx439 dcb #%" PRIu64 " piece %zu dword %u: dispatch init 0x%08x; last table p%u:%u 0x%" PRIx64 " (%u pairs):%s; UD2:3 0x%" PRIx64 " dwords:%s\n", last.n, k, q,
					        op == 0x16 ? (len >= 3 ? w[q + 2] : 0u) : (len >= 5 ? w[q + 4] : 0u), sx_k, sx_q, sx_ta, sx_tn, l.c_str(), ud, qw.c_str());
				}
				if ((v[0x213 - 0x200] & 1u) != 0 && wp[0x213 - 0x200] >= 0) { // exp 0439 (tag sc439): a scratch program
					auto at = [&](uint32_t reg) {
						char b[48];
						const uint32_t i = reg - 0x200;
						if (wp[i] >= 0) std::snprintf(b, sizeof(b), "0x%08x (p%d:%u)", v[i], wp[i], wq[i]);
						else if (n_unread != 0) std::snprintf(b, sizeof(b), "unset (%zu tables unreadable)", n_unread);
						else std::snprintf(b, sizeof(b), "inherited");
						return std::string(b);
					};
					uint32_t a0 = 0, a1 = 0, a2 = 0;
					const bool ok = op == 0x16 && safe_read32(base + w[q + 1], a0) && safe_read32(base + w[q + 1] + 4, a1) && safe_read32(base + w[q + 1] + 8, a2);
					journal("pa439: sc439 dcb #%" PRIu64 " piece %zu dword %u: %s of SCRATCH_EN program 0x%" PRIx64 ": RSRC2 %s TMPRING_SIZE %s UD0 %s UD1 %s UD2 %s UD3 %s RESOURCE_LIMITS %s%s\n", last.n, k, q,
					        op == 0x16 ? "DISPATCH_INDIRECT" : "DISPATCH_DIRECT", (static_cast<uint64_t>(v[0x20c - 0x200]) | (static_cast<uint64_t>(v[0x20d - 0x200] & 0xffu) << 32u)) << 8u,
					        at(0x213).c_str(), at(0x218).c_str(), at(0x240).c_str(), at(0x241).c_str(), at(0x242).c_str(), at(0x243).c_str(), at(0x215).c_str(),
					        ok ? (" args " + std::to_string(a0) + "x" + std::to_string(a1) + "x" + std::to_string(a2)).c_str() : "");
				}
			}
			q += len;
		}
	}
	{ // exp 0439 (tag sc439): the driver area's words (exp 0441: the restore block's flags, the SH shadow at base + 4 x
	  // register, the default SH table's 0x218 / 0x242 / 0x243 pairs; TODO(verify) the shadow's layout)
		static const struct { uint64_t a; const char* n; } words[] = {
		    {0xfe00003e0ull, "restore flag (slot 1)"}, {0xfe00007e0ull, "restore flag (slot 2)"}, {0xfe0040060ull, "counter"},
		    {0xfe0010854ull, "SH shadow 0x215"}, {0xfe0010858ull, "SH shadow 0x216"}, {0xfe001085cull, "SH shadow 0x217"}, {0xfe0010860ull, "SH shadow 0x218"},
		    {0xfe0010864ull, "SH shadow 0x219"}, {0xfe0010868ull, "SH shadow 0x21a"}, {0xfe0010900ull, "SH shadow 0x240"}, {0xfe0010904ull, "SH shadow 0x241"},
		    {0xfe0010908ull, "SH shadow 0x242"}, {0xfe001090cull, "SH shadow 0x243"}, {0xfe0042500ull, "default table pair 0x218 (reg)"}, {0xfe0042504ull, "default table 0x218 value"},
		    {0xfe0042558ull, "default table pair 0x242 (reg)"}, {0xfe004255cull, "default table 0x242 value"}, {0xfe0042560ull, "default table pair 0x243 (reg)"},
		    {0xfe0042564ull, "default table 0x243 value"}};
		std::string l;
		for (const auto& x : words) {
			uint32_t val = 0;
			char     b[96];
			if (safe_read32(x.a, val)) std::snprintf(b, sizeof(b), " [%s 0x%" PRIx64 "]=0x%x", x.n, x.a, val);
			else std::snprintf(b, sizeof(b), " [%s 0x%" PRIx64 "]=unreadable", x.n, x.a);
			l += b;
		}
		journal("pa439: sc439 driver words:%s\n", l.c_str());
	}
	if (dk < 0) {
		journal("pa439: rs439 dcb #%" PRIu64 ": no dispatch in its pieces\n", last.n);
		return;
	}
	char args[96] = "";
	if (dop == 0x16) {
		uint32_t a0 = 0, a1 = 0, a2 = 0;
		const bool ok = safe_read32(sbase + doff, a0) && safe_read32(sbase + doff + 4, a1) && safe_read32(sbase + doff + 8, a2);
		std::snprintf(args, sizeof(args), " base 0x%" PRIx64 " + 0x%x: %s %u x %u x %u", sbase, doff, ok ? "now" : "not readable", a0, a1, a2);
	}
	journal("pa439: rs439 dcb #%" PRIu64 " last dispatch: piece %d dword %u, %s%s\n", last.n, dk, dq, dop == 0x16 ? "DISPATCH_INDIRECT" : "DISPATCH_DIRECT", args);
	static const struct { uint32_t o; const char* n; } names[] = {
	    {0x207, "NUM_THREAD_X"}, {0x208, "NUM_THREAD_Y"}, {0x209, "NUM_THREAD_Z"}, {0x20c, "PGM_LO"}, {0x20d, "PGM_HI"},
	    {0x210, "SH 0x210 (scratch base lo, TODO(verify))"}, {0x211, "SH 0x211 (scratch base hi, TODO(verify))"}, {0x212, "PGM_RSRC1"},
	    {0x213, "PGM_RSRC2"}, {0x215, "RESOURCE_LIMITS"}, {0x216, "STATIC_THREAD_MGMT_SE0"}, {0x217, "STATIC_THREAD_MGMT_SE1"},
	    {0x218, "TMPRING_SIZE"}, {0x219, "STATIC_THREAD_MGMT_SE2"}, {0x21a, "STATIC_THREAD_MGMT_SE3"}, {0x228, "PGM_RSRC3"}};
	std::lock_guard lk(g_px_m);
	for (const auto& nm : names) {
		const uint32_t i = nm.o - 0x200;
		char           w2[64], px[64] = "";
		if (swp[i] >= 0) std::snprintf(w2, sizeof(w2), "set in piece %d dword %u", swp[i], swq[i]);
		else std::snprintf(w2, sizeof(w2), "inherited (not set in this dcb before it)");
		if (g_px_set[i]) std::snprintf(px, sizeof(px), "; our prefix (t %.3f s) 0x%08x", g_px_t, g_px_v[i]);
		journal("pa439: rs439   %s (SH 0x%x) = 0x%08x, %s%s\n", nm.n, nm.o, swp[i] >= 0 ? sv[i] : 0u, w2, px);
	}
	std::string ud;
	for (uint32_t u = 0; u < 16; u++) {
		const uint32_t i = 0x40 + u;
		char           b[48];
		std::snprintf(b, sizeof(b), " %u=%s%08x", u, swp[i] >= 0 ? "" : "inh:", swp[i] >= 0 ? sv[i] : (g_px_set[i] ? g_px_v[i] : 0u));
		ud += b;
	}
	journal("pa439: rs439   USER_DATA 0-15 (SH 0x240-0x24f; inh: not set in this dcb, our prefix's value if it has one):%s\n", ud.c_str());
}
static void unmet_waits(const char* when) {
	static const int pw = [] {
		const char* e = std::getenv("BC5_0439_PIECE_WAITS");
		return e != nullptr && (e[0] == '1' || e[0] == '2') && e[1] == 0 ? e[0] - '0' : 0;
	}();
	DcbKeep last;
	{
		std::unique_lock lk(g_mutex, std::try_to_lock);
		for (int i = 0; i < 50 && !lk.owns_lock(); i++) {
			std::this_thread::sleep_for(std::chrono::milliseconds(2));
			lk.try_lock();
		}
		if (!lk.owns_lock()) {
			journal("pa439: un439 %s: the probe's lock is busy, no record\n", when);
			return;
		}
		const DcbKeep* l = nullptr;
		for (const auto& d : g_dcb)
			if (d.n != ~0ull && (l == nullptr || d.n > l->n)) l = &d;
		if (l == nullptr) {
			journal("pa439: un439 %s: no dcb kept yet\n", when);
			return;
		}
		last = *l;
	}
	static bool files_done = false; // exp 0439 (tag nf439): the hung frame's pieces as files, once, at the first record
	if (!files_done) {
		files_done            = true;
		const std::string dir = g_dump_dir.empty() ? std::string(std::getenv("HOME") ? std::getenv("HOME") : ".") + "/bc5-work" : g_dump_dir;
		std::string       al;
		for (size_t k = 0; k < last.pieces.size(); k++) {
			const std::string name = dir + "/un439-dcb-" + std::to_string(last.n) + "-piece-" + std::to_string(k) + "-" + std::to_string(last.pieces[k].size()) + ".bin";
			if (FILE* f = std::fopen(name.c_str(), "wb"); f != nullptr) {
				std::fwrite(last.pieces[k].data(), 4, last.pieces[k].size(), f);
				std::fclose(f);
			}
			char b[64];
			std::snprintf(b, sizeof(b), " %zu@0x%" PRIx64 "+%zu", k, k < last.addr.size() ? last.addr[k] : 0ull, last.pieces[k].size());
			al += b;
			if (al.size() > 900) journal("pa439: un439 dcb #%" PRIu64 " pieces:%s\n", last.n, al.c_str()), al.clear();
		}
		if (!al.empty()) journal("pa439: un439 dcb #%" PRIu64 " pieces:%s\n", last.n, al.c_str());
		journal("pa439: un439 dcb #%" PRIu64 " submitted at t %.3f s, %u dwords: %zu pieces to %s/un439-dcb-%" PRIu64 "-piece-*.bin\n", last.n, last.t, last.dwords, last.pieces.size(), dir.c_str(), last.n);
		dispatch_state(last); // exp 0439 (tag rs439)
		if (FILE* f = journal_min_file(true); f != nullptr) std::fflush(f);
	}
	size_t nw = 0, nu = 0;
	for (size_t k = 0; k < last.pieces.size(); k++) {
		const auto&           w = last.pieces[k];
		std::vector<uint64_t> piece_writes;
		for (uint32_t q = 0; q < w.size();) {
			const uint32_t h = w[q], ty = h >> 30u;
			uint32_t       len = 1;
			if (ty == 3 || ty == 0) {
				const uint32_t c = (h >> 16u) & 0x3fffu;
				len = c == 0x3fffu ? 1 : c + 2;
			}
			if (q + len > w.size()) break;
			const uint32_t op = (h >> 8u) & 0xffu;
			if (ty == 3 && (op == 0x37 || op == 0x49) && len >= 5) { // the labels this piece writes before its waits
				const uint64_t wa = op == 0x37 ? ((w[q + 2] & ~3u) | (static_cast<uint64_t>(w[q + 3] & 0xffffu) << 32u))
				                               : (len >= 7 ? ((w[q + 3] & ~3u) | (static_cast<uint64_t>(w[q + 4] & 0xffffu) << 32u)) : 0);
				if (wa != 0 && piece_writes.size() < 256) piece_writes.push_back(wa);
			}
			if (ty == 3 && op == 0x3c && len >= 7 && ((w[q + 1] >> 4u) & 1u) != 0) {
				nw++;
				const uint64_t a   = (w[q + 2] & ~3u) | (static_cast<uint64_t>(w[q + 3] & 0xffffu) << 32u);
				const uint32_t ref = w[q + 4], mask = w[q + 5], fn = w[q + 1] & 7u;
				uint32_t       v   = 0;
				const bool     rd  = safe_read32(a, v);
				const bool     own = std::find(piece_writes.begin(), piece_writes.end(), a) != piece_writes.end();
				const char*    fate = k == 0 ? "top level (the host's)" : (own || pw >= 2) ? "kept for the GPU" : "dropped by the piece filter";
				if (rd && cond_holds(fn, v & mask, ref)) {
					q += len;
					continue;
				}
				nu++;
				std::string wl;
				{
					std::lock_guard lk(g_mutex);
					for (const auto& x : g_ring) {
						if (x.snap.n == ~0ull || x.ib.empty()) continue;
						for (uint32_t i = 0; i < x.ib.size();) {
							const uint32_t hh = x.ib[i], tt = hh >> 30u;
							uint32_t       ll = 1;
							if (tt == 3 || tt == 0) {
								const uint32_t c = (hh >> 16u) & 0x3fffu;
								ll = c == 0x3fffu ? 1 : c + 2;
							}
							if (i + ll > x.ib.size()) break;
							const uint32_t o = (hh >> 8u) & 0xffu;
							uint64_t       wa = 0;
							if (tt == 3 && o == 0x37 && ll >= 5) wa = (x.ib[i + 2] & ~3u) | (static_cast<uint64_t>(x.ib[i + 3] & 0xffffu) << 32u);
							if (tt == 3 && o == 0x49 && ll >= 7) wa = (x.ib[i + 3] & ~3u) | (static_cast<uint64_t>(x.ib[i + 4] & 0xffffu) << 32u);
							if (wa == a && wl.size() < 400) {
								char b[160];
								std::snprintf(b, sizeof(b), " #%" PRIu64 " %s %u dw at t %.3f s (%s, op 0x%x at %u)", x.snap.n, x.kind, x.dwords, x.snap.t, state_of(x.snap.n), o, i);
								wl += b;
								break;
							}
							i += ll;
						}
					}
				}
				journal("pa439: un439 %s: dcb #%" PRIu64 " piece %zu dword %u, %s, waits on 0x%" PRIx64 " (function %u, reference 0x%x, mask 0x%x): now %s; writers in the ring:%s\n", when, last.n, k, q, fate, a, fn, ref,
				        mask, rd ? (std::to_string(v) + " (0x" + [&] { char t[16]; std::snprintf(t, sizeof(t), "%x", v); return std::string(t); }() + ")").c_str() : "not readable",
				        wl.empty() ? " none" : wl.c_str());
			}
			q += len;
		}
	}
	journal("pa439: un439 %s: dcb #%" PRIu64 " (%s): %zu memory waits in %zu pieces, %zu not met now (piece waits mode %d)\n", when, last.n, state_of(last.n), nw, last.pieces.size(), nu, pw);
	if (FILE* f = journal_min_file(true); f != nullptr) std::fflush(f); // exp 0439 (tag nf439): on disk before a fault exit
}
} // namespace pa439
static void pw439_unmet_journal(const char* when) { pa439::unmet_waits(when); } // exp 0439 (tag uw439)
static void px439_note_prefix(const std::vector<uint32_t>& p) { pa439::note_prefix(p); } // exp 0439 (tag px439)
static void pw439_done(uint64_t n, bool ok) { pa439::done(n, ok); }

[[maybe_unused]] static void timeout_probe('''

s = rep(s, '#include "bc5/dc0439.hpp"      // exp 0439 (tag dc439): the DCC display buffers\n',
        '#include "bc5/dc0439.hpp"      // exp 0439 (tag dc439): the DCC display buffers\n#include "bc5/pa0439.hpp"      // exp 0439 (tag pa439): the indirect-argument probe\n')
s = rep(s, '[[maybe_unused]] static void timeout_probe(', GLUE)
s = rep(s, '''	tl412_record(sub_ib, sub_n, kind, n); // exp 0412 (tag tl412): first, before the probe's own files''',
        '''	tl412_record(sub_ib, sub_n, kind, n); // exp 0412 (tag tl412): first, before the probe's own files
	pa439::timeout(n);                     // exp 0439 (tag pa439)''')
s = rep(s, '''	dc412_count(ib, num_dwords); // exp 0412 (tag dc412)
	const uint64_t n = g_submits.fetch_add(1);
	// Crash journal:''', '''	dc412_count(ib, num_dwords); // exp 0412 (tag dc412)
	const uint64_t n = g_submits.fetch_add(1);
	pa439::submit(ib, num_dwords, kind, n, *maps_p); // exp 0439 (tag pa439): the arguments as the host sees them now
	// Crash journal:''')
# exp 0439 (tag ms439): BC5_0439_UMR_SCANS=<n> (2..9) with BC5_0439_UMR_WAVES=1: the watchdog's wave dump becomes n scans
# of every wave (`umr -O halt_waves -wa none`, the form the box's sudoers allows), 100 ms apart, each headed by a
# timestamp, in one host shell (one distrobox-host-exec), into the same umr-waves-<k>.txt. Unset: one scan as before.
s = rep(s, r'''		std::snprintf(cmd, sizeof(cmd), "distrobox-host-exec sudo -n /usr/bin/umr -O halt_waves -wa none > %s/umr-waves-%d.txt 2>&1; sync", dir.c_str(), k);''',
        r'''	{
		static const int ms439 = [] { // exp 0439 (tag ms439): the number of wave scans
			const char* e = std::getenv("BC5_0439_UMR_SCANS");
			const int   v = (e != nullptr && e[0] >= '2' && e[0] <= '9' && e[1] == 0) ? e[0] - '0' : 1;
			std::fprintf(stderr, "[bc5] exp 0439 (tag ms439): BC5_0439_UMR_SCANS=%d\n", v);
			return v;
		}();
		if (ms439 > 1) { // exp 0439 (tag ms439 v2, nf439): the host scanner waits for this file; written with no fork
			if (::access((dir + "/ms439-trigger").c_str(), F_OK) != 0)
				if (FILE* t = std::fopen((dir + "/ms439-trigger").c_str(), "w"); t != nullptr) {
					std::fprintf(t, "the watchdog at t %.3f s\n", timing_now());
					std::fclose(t);
				}
			if (FILE* f = journal_min_file(true); f != nullptr) {
				std::fprintf(f, "umr (exp 0439, tag nf439): the scanner's trigger written at t %.3f s (no fork)\n", timing_now());
				std::fflush(f);
			}
			return;
		}
		else
			std::snprintf(cmd, sizeof(cmd), "distrobox-host-exec sudo -n /usr/bin/umr -O halt_waves -wa none > %s/umr-waves-%d.txt 2>&1; sync", dir.c_str(), k);
	}''')
# exp 0439 (tag kw439): candidate G, BC5_0439_KEEP_XQ_WAITS=1 (bc5/kw0439.hpp): on a compute ring, a cross-queue wait
# memory satisfies at the submit is kept for the GPU (the console decides it at the packet) instead of dropped.
s = rep(s, '#include "bc5/pa0439.hpp"      // exp 0439 (tag pa439): the indirect-argument probe\n',
        '#include "bc5/pa0439.hpp"      // exp 0439 (tag pa439): the indirect-argument probe\n#include "bc5/kw0439.hpp"      // exp 0439 (tag kw439): candidate G\n')
s = rep(s, r'''					if (!wait_satisfied(p, op == 0x93) && ring_will_satisfy(p, op == 0x93, job_ring(kind))) {
						static std::atomic<uint64_t> n_kept {0};''', r'''					static const bool kw439 = [] { // exp 0439 (tag kw439): candidate G
						const char* e = std::getenv("BC5_0439_KEEP_XQ_WAITS");
						const bool  v = e != nullptr && e[0] == '1' && e[1] == 0;
						std::fprintf(stderr, "[bc5] exp 0439 (tag kw439): BC5_0439_KEEP_XQ_WAITS=%d\n", v ? 1 : 0);
						return v;
					}();
					if (bc5::kw439::keep_satisfied(kw439, std::strncmp(kind, "acb", 3) == 0, job_ring(kind) != bc5::direct::kGfxRing, false, wait_satisfied(p, op == 0x93))) {
						chain_flush(1); // as the unsatisfied path (ADR 0010): what the chain holds may write this label
						static std::atomic<uint64_t> n_kw {0};
						if ((n_kw++ & 0x3ffu) == 0) journal("kw439: %s %u dwords keeps its satisfied wait at %u on 0x%" PRIx64 " for the GPU (%" PRIu64 " so far)\n", kind, num_dwords, i, label, n_kw.load());
#ifndef BC5_LEAN
						if (wd_acb) wd438_record(ib, num_dwords, i, p, op == 0x93, label, 3); // exp 0438 (wd438): "kept for the GPU"
#endif
						t_keep_waits.push_back(p);
						SoftCp::set_gpu_executed(p, len, {0});
						i += len;
						continue;
					}
					if (!wait_satisfied(p, op == 0x93) && ring_will_satisfy(p, op == 0x93, job_ring(kind))) {
						static std::atomic<uint64_t> n_kept {0};''')
# exp 0439 (tag cw439): the chain-following writer scan, BC5_0439_CHAIN_WRITERS=1 (bc5/cw0439.hpp): a job's chained and
# called pieces are registered with register_label_writes too, under the same seq and ring.
s = rep(s, '#include "bc5/kw0439.hpp"      // exp 0439 (tag kw439): candidate G\n',
        '#include "bc5/kw0439.hpp"      // exp 0439 (tag kw439): candidate G\n#include "bc5/cw0439.hpp"      // exp 0439 (tag cw439): the chain-following writer scan\n')
s = rep(s, '''		register_label_writes(ib, num_dwords, r.executed_offsets, r.seq_no, r.ring); // experiment 0055
''', r'''		register_label_writes(ib, num_dwords, r.executed_offsets, r.seq_no, r.ring); // experiment 0055
		{ // exp 0439 (tag cw439): the job's chained and called pieces too
			static const bool cw439 = [] {
				const char* e = std::getenv("BC5_0439_CHAIN_WRITERS");
				const bool  v = e != nullptr && e[0] == '1' && e[1] == 0;
				std::fprintf(stderr, "[bc5] exp 0439 (tag cw439): BC5_0439_CHAIN_WRITERS=%d\n", v ? 1 : 0);
				return v;
			}();
			if (cw439) {
				const auto mp = g_dev->sorted_mappings();
				const size_t np = bc5::cw439::each_piece(ib, num_dwords, [&mp](uint64_t a, uint64_t b) { return covered_sorted(*mp, a, b); },
				                                         [&](const uint32_t* src, uint32_t pn, const std::vector<uint32_t>& st) { register_label_writes(src, pn, st, r.seq_no, r.ring); });
				static std::atomic<uint64_t> n_cw {0}, n_pieces {0};
				n_pieces += np;
				if (np != 0 && (n_cw++ & 0x3ffu) == 0) journal("cw439: %s %u dwords: %zu pieces' label writes registered too (%" PRIu64 " jobs, %" PRIu64 " pieces so far)\n", kind, num_dwords, np, n_cw.load(), n_pieces.load());
			}
		}
''')
# exp 0439 (tag ms439 v2): the host scanner is started once, at the watchdog's start, and waits for the trigger
s = rep(s, '''static void umr_watchdog_start() {
	static const bool on = BC5_DIAG_ENV("BC5_DIRECT_UMR_ON_TIMEOUT") != nullptr;
	if (!on) return;
	static std::once_flag once;
	std::call_once(once, [] {''', r'''static void umr_watchdog_start() {
	static const bool on = BC5_DIAG_ENV("BC5_DIRECT_UMR_ON_TIMEOUT") != nullptr;
	if (!on) return;
	static std::once_flag once;
	std::call_once(once, [] {
		// exp 0439 (tag ms439 v2): with BC5_0439_UMR_SCANS=<n> and the wave dump on, one host shell starts now and waits
		// (10-ms polls) for <dump dir>/ms439-trigger, then takes the n scans 100 ms apart into umr-waves-0.txt. At 09:41 the
		// launch at the stall (distrobox-host-exec, then umr) took ~1.4 s, past the kernel's reset. The shell ends with
		// this process (kill -0 on its pid).
		if (const char* e = std::getenv("BC5_0439_UMR_SCANS"); e != nullptr && e[0] >= '2' && e[0] <= '9' && e[1] == 0 && uw439_on()) {
			const std::string dir = g_dump_dir.empty() ? std::string(std::getenv("HOME") ? std::getenv("HOME") : ".") + "/bc5-work" : g_dump_dir;
			// exp 0439 (tag lw439): BC5_0439_DUMP_AT_MS=<ms>[,<ms>...] (digits and commas only, at most 4): more dumps at
			// those times after the trigger, each to umr-waves-0-d<ms>.txt with one wave scan after it, while the trigger
			// file is there (the finisher removes it when the waited job completes).
			std::string later;
			if (const char* da = std::getenv("BC5_0439_DUMP_AT_MS"); da != nullptr && *da != 0 && std::strspn(da, "0123456789,") == std::strlen(da) && std::strlen(da) < 40) {
				std::string l = da;
				for (auto& c : l)
					if (c == ',') c = ' ';
				later = "; for d in " + l + "; do while [ -e $T ] && [ $(( ($(date +%s%N) - W) / 1000000 )) -lt $d ]; do sleep 0.05; done; [ -e $T ] || break; "
				        "{ echo \"=== lw439 dump at +${d} ms after the wake, $(date +%T.%N)\"; sudo -n /usr/local/bin/bc5-gpu-hang-dump; echo \"=== lw439 scan at $(date +%T.%N)\"; "
				        "sudo -n /usr/bin/umr -O halt_waves -wa none; echo \"=== lw439 done at $(date +%T.%N)\"; } > " + dir + "/umr-waves-0-d$d.txt 2>&1; done";
			}
			// exp 0439 (tag gt439): BC5_0439_GAP_MS=<ms> (digits, 200..5000): the shell also watches <dump dir>/direct.log;
			// from its first "frame profile" line on, no growth for that long writes the trigger itself (the journal is
			// flushed at every submission; the longest healthy gap between frame-profile lines today was 0.30 s).
			std::string wait_loop = "while [ ! -e $T ] && kill -0 " + std::to_string(getpid()) + " 2>/dev/null; do sleep 0.01; done";
			if (const char* g = std::getenv("BC5_0439_GAP_MS"); g != nullptr && *g != 0 && std::strspn(g, "0123456789") == std::strlen(g) && std::atoi(g) >= 200 && std::atoi(g) <= 5000) {
				const std::string J = dir + "/direct.log";
				wait_loop = "A=0; Z=0; L=$(date +%s%N); while [ ! -e $T ] && kill -0 " + std::to_string(getpid()) + " 2>/dev/null; do "
				            "if [ $A = 0 ]; then grep -q \"^frame profile\" " + J + " 2>/dev/null && { A=1; Z=$(stat -c %s " + J + "); L=$(date +%s%N); echo \"=== gt439 armed at $(date +%T.%N)\"; }; sleep 0.2; continue; fi; "
				            "S=$(stat -c %s " + J + " 2>/dev/null); N=$(date +%s%N); if [ \"$S\" != \"$Z\" ]; then Z=$S; L=$N; "
				            "elif [ $(( (N - L) / 1000000 )) -ge " + std::string(g) + " ]; then echo \"journal gap $(( (N - L) / 1000000 )) ms\" > $T; echo \"=== gt439 fired: no journal growth for $(( (N - L) / 1000000 )) ms at $(date +%T.%N)\"; break; fi; sleep 0.02; done";
			}
			char pre[4000];
			std::snprintf(pre, sizeof(pre),
			              "rm -f %s/ms439-trigger; (distrobox-host-exec sh -c 'T=%s/ms439-trigger; %s; [ -e $T ] || exit 0; W=$(date +%%s%%N); "
			              "echo \"=== ms439 trigger $(cat $T), scanner awake $(date +%%T.%%N)\"; echo \"=== ms439 hang dump at $(date +%%T.%%N)\"; sudo -n /usr/local/bin/bc5-gpu-hang-dump; "
			              "echo \"=== ms439 hang dump done at $(date +%%T.%%N)\"; for s in $(seq 1 %c); do echo \"=== ms439 scan $s at $(date +%%T.%%N)\"; "
			              "sudo -n /usr/bin/umr -O halt_waves -wa none; sleep 0.1; done%s' > %s/umr-waves-0.txt 2>&1 &)",
			              dir.c_str(), dir.c_str(), wait_loop.c_str(), e[0], later.c_str(), dir.c_str());
			const int rc = std::system(pre);
			std::fprintf(stderr, "[bc5] exp 0439 (tag ms439): host scanner started for %c scans (rc %d), trigger %s/ms439-trigger\n", e[0], rc, dir.c_str());
		}''')
# exp 0439 (tag pc439): the draw test that gates the system prefix (exp 0157, prefix_mode 2 "draws") looks at the
# top level only; this title's dcbs draw only in chained or called pieces (the 09:57 hung dcb #412: no draw packet in
# the top level or its six pieces' top levels), so its TF ring, offchip, start-state and GS-ring rows never went out.
# With BC5_0439_PREFIX_CHAINS=1 the test also walks the chain (bc5::ib_chain::collect, the pieces' own dwords).
s = rep(s, '''static std::vector<uint32_t> sx_prefix(const bc5::full_state::Tracker& t) {''', r'''static void px439_note_prefix(const std::vector<uint32_t>& p); // exp 0439 (tag px439), defined after the probe
static bool pc439_on() {
	static const bool v = [] {
		const char* e = std::getenv("BC5_0439_PREFIX_CHAINS");
		const bool  on = e != nullptr && e[0] == '1' && e[1] == 0;
		std::fprintf(stderr, "[bc5] exp 0439 (tag pc439): prefix draw test through chains %s\n", on ? "on" : "off");
		return on;
	}();
	return v;
}
static bool pc439_chain_draw(const uint32_t* ib, uint32_t num_dwords) {
	const auto pm = g_dev ? g_dev->sorted_mappings() : nullptr;
	if (pm == nullptr) return false;
	const auto cr = bc5::ib_chain::collect(ib, num_dwords, [&pm](uint64_t a, uint64_t b) { return covered_sorted(*pm, a, b); }, true);
	for (size_t k = 1; k < cr.pieces.size(); k++)
		if (ib_has_draw(cr.pieces[k].src, cr.pieces[k].n)) {
			static std::atomic<uint64_t> n {0};
			if ((n++ & 0x3ffu) == 0) journal("pa439: pc439 t %.3f s: a dcb of %u dwords draws only in its piece %zu of %zu: the system prefix put in front (%" PRIu64 " such dcbs)\n", timing_now(), num_dwords, k, cr.pieces.size(), n.load());
			return true;
		}
	return false;
}
static std::vector<uint32_t> sx_prefix(const bc5::full_state::Tracker& t) {''')
s = rep(s, '''	if (prefix_all() && std::strcmp(kind, "dcb") == 0 && (prefix_mode() == 1 || ib_has_draw(ib, num_dwords))) { // experiment 0157''',
        '''	if (prefix_all() && std::strcmp(kind, "dcb") == 0 && (prefix_mode() == 1 || ib_has_draw(ib, num_dwords) || (pc439_on() && pc439_chain_draw(ib, num_dwords)))) { // experiment 0157; exp 0439 (tag pc439)''')
# exp 0439 (tag lw439): the host's own completion bound and the watchdog's threshold and arming as words (top, 11-22
# ~10:50). BC5_0439_WAIT_MS=<ms> (100..60000, default 2000): the fence wait of the job finisher and the bound of the
# synchronous submits, so that with amdgpu.lockup_timeout=10000 the kernel decides, not the host.
# BC5_0439_UMR_AFTER_MS=<ms> (100..10000, default 900): the watchdog's age since the job's submission (j.queued_ns).
# BC5_0439_UMR_ARM_S=<s> (default 0): the watchdog fires only from that title time on (timing_now()).
s = rep(s, '''// Experiment 0058: the kernel resets the gfx ring ~2 s after a job hangs on it''', r'''static uint64_t lw439_ms(const char* name, uint64_t def, uint64_t lo, uint64_t hi) {
	const char* e = std::getenv(name);
	if (e == nullptr || *e == 0) return def;
	char*          end = nullptr;
	const uint64_t v   = std::strtoull(e, &end, 10);
	return end != nullptr && *end == 0 && v >= lo && v <= hi ? v : def;
}
static uint64_t lw439_wait_ns() { // exp 0439 (tag lw439)
	static const uint64_t v = [] {
		const uint64_t ms = lw439_ms("BC5_0439_WAIT_MS", 2000, 100, 60000);
		std::fprintf(stderr, "[bc5] exp 0439 (tag lw439): completion bound %" PRIu64 " ms\n", ms);
		return ms * 1'000'000ull;
	}();
	return v;
}
static std::atomic<bool> g_lw439_fired {false}; // exp 0439 (tag lw439): the watchdog fired for the job now waited
static std::atomic<uint64_t> g_lw439_sync_since {0}; // exp 0439 (tag sy439): the start of a synchronous submit now in the kernel, 0 = none
static std::atomic<uint64_t> g_fw439[16] = {}; // exp 0439 (tag fw439): each completion thread's wait start (j.queued_ns), 0 = none
static void fw439_set(int index, uint64_t v) {
	if (index >= 0 && index < 16) g_fw439[index] = v;
}
static uint64_t fw439_oldest() {
	uint64_t m = 0;
	for (const auto& a : g_fw439) {
		const uint64_t v = a.load();
		if (v != 0 && (m == 0 || v < m)) m = v;
	}
	return m;
}
struct Lw439Sync {
	Lw439Sync() { g_lw439_sync_since = SoftCp::now_ns(); }
	~Lw439Sync() { g_lw439_sync_since = 0; }
};
static void pw439_unmet_journal(const char* when); // exp 0439 (tag uw439), defined after the probe
static void pw439_done(uint64_t n, bool ok);
// Experiment 0058: the kernel resets the gfx ring ~2 s after a job hangs on it''')
s = rep(s, '''				const uint64_t t0 = g_fence_wait_since.load();
				if (t0 != 0 && SoftCp::now_ns() - t0 > 900'000'000ull) {
					umr_on_timeout();''', r'''				const uint64_t tf = fw439_oldest(), ts = g_lw439_sync_since.load(); // exp 0439 (tag sy439, fw439): the oldest wait of any completion thread, or a synchronous submit
				const uint64_t t0 = tf == 0 ? ts : (ts == 0 ? tf : std::min(tf, ts));
				{ // exp 0439 (tag gt439): a trigger the shell wrote (the journal gap): the record now and at +3.1 and +7.1 s
					static bool seen = false;
					static uint64_t at = 0;
					static int k = 0;
					if (!seen && !g_lw439_fired.load() && !g_dump_dir.empty() && ::access((g_dump_dir + "/ms439-trigger").c_str(), F_OK) == 0) {
						seen = true, at = SoftCp::now_ns(), k = 0;
						journal("pa439: gt439 the shell's trigger seen at t %.3f s (the journal gap)\n", timing_now());
						pw439_unmet_journal("at the journal gap");
					}
					if (seen && k == 0 && SoftCp::now_ns() - at >= 3'100'000'000ull) pw439_unmet_journal("at the gap +3.1 s"), k = 1;
					if (seen && k == 1 && SoftCp::now_ns() - at >= 7'100'000'000ull) pw439_unmet_journal("at the gap +7.1 s"), k = 2;
				}
				static const uint64_t after_ns = lw439_ms("BC5_0439_UMR_AFTER_MS", 900, 100, 10000) * 1'000'000ull; // exp 0439 (tag lw439)
				static const double   arm_s    = static_cast<double>(lw439_ms("BC5_0439_UMR_ARM_S", 0, 0, 3600));
				if (t0 != 0 && SoftCp::now_ns() - t0 > after_ns && timing_now() >= arm_s && ::access((g_dump_dir + "/ms439-trigger").c_str(), F_OK) != 0) {
					g_lw439_fired = true;
					journal("pa439: lw439 watchdog: a job %.0f ms past its submission at t %.3f s (threshold %" PRIu64 " ms, armed from %.0f s)\n",
					        static_cast<double>(SoftCp::now_ns() - t0) / 1e6, timing_now(), after_ns / 1'000'000ull, arm_s);
					umr_on_timeout();
					pw439_unmet_journal("at the watchdog"); // exp 0439 (tag uw439): and again at 4 and 8 s of the job's age
					const auto cur = [] { const uint64_t a = fw439_oldest(), b = g_lw439_sync_since.load(); return a == 0 ? b : (b == 0 ? a : std::min(a, b)); };
					for (int k = 0; cur() == t0;) {
						std::this_thread::sleep_for(std::chrono::milliseconds(20));
						const uint64_t age = SoftCp::now_ns() - t0;
						if (k == 0 && age >= 4'000'000'000ull) pw439_unmet_journal("at 4 s"), k = 1;
						if (k == 1 && age >= 8'000'000'000ull) pw439_unmet_journal("at 8 s"), k = 2;
					}''')
s = rep(s, '''				static constexpr uint64_t fence_ns = 2'000'000'000ull;
				if (g_dev) r = g_dev->finish(j.seq, j.slot, fence_ns);''', r'''				const uint64_t fence_ns = lw439_wait_ns(); // exp 0439 (tag lw439): was 2 s
				if (g_dev) r = g_dev->finish(j.seq, j.slot, fence_ns);
				pw439_done(j.n, r.ok); // exp 0439 (tag uw439)
				if (g_lw439_fired.exchange(false)) { // exp 0439 (tag lw439): the job the watchdog fired on ended: how
					const std::string dir = g_dump_dir.empty() ? std::string(std::getenv("HOME") ? std::getenv("HOME") : ".") + "/bc5-work" : g_dump_dir;
					std::remove((dir + "/ms439-trigger").c_str());
					journal("pa439: lw439 the waited %s job of %u dwords ended %s %.0f ms after its submission\n", j.kind, j.num_dwords, r.ok ? "OK" : (r.timed_out ? "TIMED OUT" : "FAILED"),
					        static_cast<double>(SoftCp::now_ns() - (j.queued_ns != 0 ? j.queued_ns : SoftCp::now_ns())) / 1e6);
				}''')
s = rep(s, '''		r = g_dev->submit(std::span<const uint32_t>(sub_ib, sub_n), opt, 2'000'000'000ull, true, qring, unlock_dev);''',
        '''		{ const Lw439Sync sy439; r = g_dev->submit(std::span<const uint32_t>(sub_ib, sub_n), opt, lw439_wait_ns(), true, qring, unlock_dev); } // exp 0439 (tag lw439, sy439)''')
s = rep(s, '''		r = g_dev->submit(std::span<const uint32_t>(sub_ib, sub_n), opt, 2'000'000'000ull, true, qring);
''', '''		{ const Lw439Sync sy439; r = g_dev->submit(std::span<const uint32_t>(sub_ib, sub_n), opt, lw439_wait_ns(), true, qring); } // exp 0439 (tag lw439, sy439)
''')
s = rep(s, '''		r       = g_dev->submit(std::span<const uint32_t>(sub_ib, sub_n), opt, 2'000'000'000ull, true, qring);
''', '''		{ const Lw439Sync sy439; r = g_dev->submit(std::span<const uint32_t>(sub_ib, sub_n), opt, lw439_wait_ns(), true, qring); } // exp 0439 (tag lw439, sy439)
''')
# exp 0439 (tag fw439): the completion threads' wait starts, one slot per thread
s = rep(s, '''				g_fence_wait_since = j.queued_ns != 0 ? j.queued_ns : SoftCp::now_ns(); // from the job's submission: the kernel resets ~2 s after it hangs''',
        '''				g_fence_wait_since = j.queued_ns != 0 ? j.queued_ns : SoftCp::now_ns(); // from the job's submission: the kernel resets ~2 s after it hangs
				fw439_set(index, g_fence_wait_since.load()); // exp 0439 (tag fw439)''')
s = rep(s, '''				g_fence_wait_since = 0;
''', '''				g_fence_wait_since = 0;
				fw439_set(index, 0); // exp 0439 (tag fw439)
''')
# exp 0439 (tag px439): note the newest dcb prefix's compute SH registers
s = rep(s, '''		full_prefix = prefix_mode() == 3 ? sx_prefix(t_fs_before) : prefix_of(t_fs_before);
		full_used   = !full_prefix.empty();''', '''		full_prefix = prefix_mode() == 3 ? sx_prefix(t_fs_before) : prefix_of(t_fs_before);
		full_used   = !full_prefix.empty();
		if (full_used) px439_note_prefix(full_prefix); // exp 0439 (tag px439)''')
open(dst, 'w', encoding='utf-8', newline='').write(s)
print('pa439: written', dst)
