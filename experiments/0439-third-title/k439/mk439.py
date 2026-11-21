# BC5 experiment 0439 (tag dc439): the private units from the shared tree's (patch 9889b06a) bc5LleAgc.cpp and
# videoOut.cpp. Every replacement must match exactly once.
#   python mk439.py <dir with the two originals> <out dir>
import sys

src, dst = sys.argv[1], sys.argv[2]


def rep(s, a, b, n=1):
    c = s.count(a)
    assert c == n, (a[:90], c)
    return s.replace(a, b)


GLUE = r'''
// ---- BC5 experiment 0439 (tag dc439): the third title's DCC display buffers (dcc-present-design.md) ----
// BC5_DIRECT_DCC_PRESENT (read in the lean build too): unset/0 off; 1 L1, log only: the GFX ring's context registers
// followed by a host state_stack::Tracker over every GFX job, the CB_COLORn block whose BASE is a registered compressed
// video-out surface remembered, logged at its flips; 2 L1 + D: at the title's flip of such a surface, after a drain,
// one host-built GFX job decompresses it in place (CB_DCC_DECOMPRESS, bc5/dc0439.hpp), a drain again, and the
// present reads it as uncompressed (bc5_dc439_plain).
namespace dc439 {
static int mode() {
	static const int v = [] {
		const char* e = std::getenv("BC5_DIRECT_DCC_PRESENT");
		const int   m = e != nullptr ? std::atoi(e) : 0;
		std::fprintf(stderr, "[bc5] exp 0439 (tag dc439): BC5_DIRECT_DCC_PRESENT=%d (0 off, 1 log, 2 decompress at the flip)\n", m);
		return m;
	}();
	return v;
}
struct Surface {
	int      index = -1;
	uint64_t data = 0, meta = 0, fmt = 0;
	uint32_t w = 0, h = 0, dcc = 0;
	bc5::dc439::Block block;         // as the title last set it, at a GFX job
	uint64_t          block_job = 0; // the tracked GFX job that set it
	uint64_t          flips = 0, done = 0, failed = 0, no_block = 0, logged = 0;
	uint64_t          draws = 0, gfx_hits = 0, other_hits = 0, other_jobs = 0; // draws into it; its address in jobs
	bool              plain = false; // decompressed for the flip in flight
	uint64_t          flip_seq = 0;  // the order of its last flip (indices sharing a buffer: the latest decides)
};
static std::mutex                g_mu;
static std::vector<Surface>      g_surf;
static bc5::state_stack::Tracker g_tracker;
static std::vector<uint32_t>     g_io;
static uint64_t                  g_jobs = 0;
static std::atomic<bool>         g_any {false};
static bool                      g_code_ok = false;
static uint64_t                  g_vs_va = 0, g_ps_va = 0;
static uint64_t                  g_flip_seq = 0;
} // namespace dc439

// exp 0439 (tag wr439), problem 3: every submitted packet (any ring) whose memory operand (bc5::policy::memory_operands:
// the waits' addresses as well as the writes') meets a watched address is logged, with the ring, the job and the packet.
// BC5_0439_WATCH=hex,hex,... (each watched as 8 bytes); unset: the third title's stall labels of a6 (2026-11-21).
static void wr439_scan(const uint32_t* ib, uint32_t n, int ring, const char* kind, const bc5::policy::FilterOptions& opt, int depth = 0) {
	static const std::vector<uint64_t> w = [] {
		std::vector<uint64_t> v;
		const char*           e = std::getenv("BC5_0439_WATCH");
		std::string           s = e != nullptr ? e : "2000000000,2010449750,20104aa630,20104cd100,20104cd120,20104cd140,20104cd160,20104cd180,20104cd1a0,20104cd1c0,20104cd1e0,20000081e0,2000008000";
		for (size_t a = 0; a < s.size();) {
			size_t b = s.find(',', a);
			if (b == std::string::npos) b = s.size();
			if (b > a) v.push_back(std::strtoull(s.substr(a, b - a).c_str(), nullptr, 16));
			a = b + 1;
		}
		std::fprintf(stderr, "[bc5] exp 0439 (tag wr439): watching %zu addresses\n", v.size());
		return v;
	}();
	static std::recursive_mutex m;
	static uint64_t             jobs = 0, lines = 0;
	std::lock_guard             lk(m);
	if (depth == 0) jobs++;
	{ // the Agc MemSemaphore builders' marker in front of a signal / wait on label 0 (0x2000000000): 0xC9010020 / 0xC9020020
		static uint64_t mk = 0;
		for (uint32_t k = 0; k < n; k++)
			if ((ib[k] == 0xC9010020u || ib[k] == 0xC9020020u) && mk++ < 100)
				std::fprintf(stderr, "[bc5] exp 0439 (tag wr439): t %.3f s ring %d %s job %" PRIu64 " dword %u = 0x%08x (next 0x%08x 0x%08x 0x%08x)\n", timing_now(), ring, kind, jobs, k, ib[k], k + 1 < n ? ib[k + 1] : 0u, k + 2 < n ? ib[k + 2] : 0u, k + 3 < n ? ib[k + 3] : 0u);
	}
	for (uint32_t q = 0; q < n;) {
		const uint32_t h = ib[q];
		uint32_t       len = 1;
		if ((h >> 30u) == 3 || (h >> 30u) == 0) {
			const uint32_t c = (h >> 16u) & 0x3fffu;
			len              = c == 0x3fffu ? 1 : c + 2;
		}
		if (q + len > n) break;
		if ((h >> 30u) == 3 && depth < 3 && len >= 4 && (((h >> 8u) & 0xffu) == 0x3f || ((h >> 8u) & 0xffu) == 0x33)) { // one level of nested IBs
			const uint64_t na = (ib[q + 1] & ~3u) | (static_cast<uint64_t>(ib[q + 2] & 0xffffu) << 32u);
			const uint32_t nn = ib[q + 3] & 0xfffffu;
			if (na != 0 && nn != 0 && opt.mapped && opt.mapped(na, static_cast<uint64_t>(nn) * 4)) wr439_scan(reinterpret_cast<const uint32_t*>(na), nn, ring, depth == 0 ? "nested1" : depth == 1 ? "nested2" : "nested3", opt, depth + 1);
		}
		if ((h >> 30u) == 3 && ((h >> 8u) & 0xffu) == 0x47u && len >= 6 && ((ib[q + 3] >> 24u) & 7u) != 0) { // exp 0439 (tag f52): EVENT_WRITE_EOP with an interrupt
			static uint64_t ei = 0;
			if (ei++ < 100) std::fprintf(stderr, "[bc5] exp 0439 (tag f52): t %.3f s ring %d %s job %" PRIu64 " @%u EVENT_WRITE_EOP INT_SEL %u data 0x%08x%08x\n", timing_now(), ring, kind, jobs, q, (ib[q + 3] >> 24u) & 7u, ib[q + 5], ib[q + 4]);
		}
		if ((h >> 30u) == 3 && ((h >> 8u) & 0xffu) == 0x49u && len >= 8 && ((ib[q + 2] >> 24u) & 7u) != 0) { // exp 0439 (tag tk439)
			// RELEASE_MEM with an interrupt (INT_SEL dword 2 bits 26:24): its context id (dword 7) is where a flip token goes
			// (AnyPS5 VideoOutDriver.cpp, GPL-2.0, 8b403579: the token in INT_CTXID with INT_SEL 2; UNVERIFIED there)
			static uint64_t ri = 0;
			if (ri++ < 200)
				std::fprintf(stderr, "[bc5] exp 0439 (tag tk439): t %.3f s ring %d %s job %" PRIu64 " @%u RELEASE_MEM event 0x%x INT_SEL %u DATA_SEL %u address 0x%" PRIx64 " data 0x%08x%08x INT_CTXID 0x%08x\n", timing_now(), ring, kind, jobs, q,
				             ib[q + 1] & 0x3fu, (ib[q + 2] >> 24u) & 7u, ib[q + 2] >> 29u, (ib[q + 3] & ~3ull) | (static_cast<uint64_t>(ib[q + 4] & 0xffffu) << 32u), ib[q + 6], ib[q + 5], ib[q + 7]);
		}
		if ((h >> 30u) == 3 && ((h >> 8u) & 0xffu) == 0x39u && len >= 3) { // MEM_SEMAPHORE: not in memory_operands
			static uint64_t ms = 0;
			const uint64_t  ma  = (ib[q + 1] & ~7u) | (static_cast<uint64_t>(ib[q + 2] & 0xffffu) << 32u);
			const uint32_t  ctl = len >= 4 ? ib[q + 3] : 0u;
			if (ms++ < 300) std::fprintf(stderr, "[bc5] exp 0439 (tag wr439): t %.3f s ring %d %s job %" PRIu64 " @%u MEM_SEMAPHORE %u dwords address 0x%" PRIx64 " control 0x%08x (SEM_SEL %u, SIGNAL_TYPE %u)\n", timing_now(), ring, kind, jobs, q, len, ma, ctl, ctl >> 29u, (ctl >> 20u) & 1u);
		}
		if ((h >> 30u) == 3) {
			for (const auto& [a, bytes]: bc5::policy::memory_operands(ib + q, len)) {
				const uint64_t nb = bytes == 0 ? 8 : bytes;
				for (const uint64_t x: w) {
					if (a < x + 8 && x < a + nb && lines++ < 400) {
						char words[160];
						int  o = 0;
						for (uint32_t k = 0; k < len && k < 8 && o < 150; k++) o += std::snprintf(words + o, sizeof(words) - o, " %08x", ib[q + k]);
						std::fprintf(stderr, "[bc5] exp 0439 (tag wr439): t %.3f s ring %d %s job %" PRIu64 " (%u dwords at %p) @%u op 0x%02x operand 0x%" PRIx64 "+%" PRIu64 " meets 0x%" PRIx64 ":%s\n", timing_now(), ring,
						             kind, jobs, n, static_cast<const void*>(ib), q, (h >> 8u) & 0xffu, a, nb, x, words);
					}
				}
			}
		}
		q += len;
	}
}

static void dc439_track(const uint32_t* ib, uint32_t n, const bc5::policy::FilterOptions& opt, int ring, const char* kind) {
	if (ib != nullptr && n != 0) wr439_scan(ib, n, ring, kind, opt); // exp 0439 (tag wr439)
	if (dc439::mode() == 0 || !dc439::g_any.load(std::memory_order_relaxed) || ib == nullptr || n == 0) return;
	std::lock_guard lk(dc439::g_mu);
	auto readable = [&opt](uint64_t a, uint64_t b) { return opt.mapped && opt.mapped(a, b); };
	if (ring != bc5::direct::kGfxRing) { // where the surface's address appears in compute jobs
		for (auto& s: dc439::g_surf) {
			const uint32_t c = bc5::dc439::count_base(ib, n, static_cast<uint32_t>(s.data >> 8), readable);
			s.other_hits += c;
			if (c != 0) s.other_jobs++;
		}
		return;
	}
	{ // the per-draw catcher, from the tracker's context at the job's start
		static bc5::dc439::Ctx cx;
		const auto&            c0 = dc439::g_tracker.context();
		for (uint32_t r = 0; r < 0x400; r++) {
			cx.value[r] = c0.value[r];
			cx.valid[r] = c0.valid.test(r);
		}
		std::vector<uint64_t>        addrs;
		std::vector<bc5::dc439::Hit> hits(dc439::g_surf.size());
		for (const auto& s: dc439::g_surf) addrs.push_back(s.data);
		bc5::dc439::walk_draws(ib, n, cx, addrs, hits, readable);
		for (size_t k = 0; k < dc439::g_surf.size(); k++) {
			auto& s = dc439::g_surf[k];
			s.gfx_hits += bc5::dc439::count_base(ib, n, static_cast<uint32_t>(s.data >> 8), readable);
			if (hits[k].draws == 0) continue;
			s.block     = hits[k].block;
			s.block_job = dc439::g_jobs + 1;
			s.draws += hits[k].draws;
		}
	}
	dc439::g_io.assign(ib, ib + n);
	bc5::state_stack::Stats st;
	dc439::g_tracker.apply_in_place(std::span<const uint32_t>(ib, n), dc439::g_io, opt.mapped, st);
	dc439::g_jobs++;
	const auto& c = dc439::g_tracker.context();
	for (auto& s: dc439::g_surf) {
		if (s.draws != 0) continue; // a block from a draw wins over the job-end context
		const auto b = bc5::dc439::find(c.value, c.valid, s.data);
		if (!b.valid) continue;
		s.block     = b;
		s.block_job = dc439::g_jobs;
	}
}

static void dc439_log(const dc439::Surface& s, const char* what) {
	const auto& b = s.block;
	std::fprintf(stderr,
	             "[bc5] exp 0439 (tag dc439): t %.3f s %s: index %d surface 0x%" PRIx64 " meta 0x%" PRIx64 " %ux%u dcc 0x%x; flips %" PRIu64 " done %" PRIu64 " failed %" PRIu64 " no-block %" PRIu64 "; "
	             "block %s (job %" PRIu64 " of %" PRIu64 "): MRT %u BASE 0x%" PRIx64 " DCC_BASE 0x%" PRIx64 " (%s the registered metadata) VIEW 0x%08x INFO 0x%08x (DCC_ENABLE %d, FORMAT %u, COMPRESSION %u, FAST_CLEAR %u) "
	             "ATTRIB 0x%08x DCC_CONTROL 0x%08x ATTRIB2 0x%08x ATTRIB3 0x%08x (SW_MODE %u, META_LINEAR %d, DCC_PIPE_ALIGNED %d) CMASK 0x%08x FMASK 0x%08x CB_DCC_CONTROL %s0x%08x\n",
	             timing_now(), what, s.index, s.data, s.meta, s.w, s.h, s.dcc, s.flips, s.done, s.failed, s.no_block, b.valid ? "found" : "NOT FOUND", s.block_job, dc439::g_jobs, b.mrt, b.base(), b.dcc_base(),
	             b.dcc_base() == s.meta ? "equals" : "DIFFERS FROM", b.c[3], b.c[4], b.dcc_enable() ? 1 : 0, (b.c[4] >> 2) & 0x1fu, (b.c[4] >> 14) & 1u, (b.c[4] >> 13) & 1u, b.c[5], b.c[6], b.attrib2, b.attrib3, b.sw_mode(),
	             b.meta_linear() ? 1 : 0, b.dcc_pipe_aligned() ? 1 : 0, b.c[7], b.c[9], b.cb_dcc_control_valid ? "" : "(unset) ", b.cb_dcc_control);
	// where it was written from, and what its metadata holds now (the view is CPU-visible guest memory)
	uint64_t    hist[256] = {};
	const auto* meta      = reinterpret_cast<const volatile uint8_t*>(s.meta);
	for (uint32_t k = 0; k < 0x20000; k++) hist[meta[k]]++;
	int top[5] = {-1, -1, -1, -1, -1};
	for (int v = 0; v < 256; v++)
		for (int t = 0; t < 5; t++)
			if (top[t] < 0 || hist[v] > hist[top[t]]) {
				for (int u = 4; u > t; u--) top[u] = top[u - 1];
				top[t] = v;
				break;
			}
	const auto* px = reinterpret_cast<const volatile uint32_t*>(s.data);
	uint64_t    nz = 0;
	for (uint32_t k = 0; k < (4u << 20) / 4; k++) nz += px[k] != 0;
	std::fprintf(stderr, "[bc5] exp 0439 (tag dc439):   index %d: draws into it %" PRIu64 "; its address in GFX jobs %" PRIu64 " times, in compute jobs %" PRIu64 " times (%" PRIu64 " jobs); metadata bytes (first 128 KiB) top: 0x%02x x%" PRIu64 ", 0x%02x x%" PRIu64 ", 0x%02x x%" PRIu64 ", 0x%02x x%" PRIu64 ", 0x%02x x%" PRIu64 "; non-zero dwords in the first 4 MiB of the surface %" PRIu64 " of %u\n",
	             s.index, s.draws, s.gfx_hits, s.other_hits, s.other_jobs, top[0], hist[top[0]], top[1], hist[top[1]], top[2], hist[top[2]], top[3], hist[top[3]], top[4], hist[top[4]], nz, (4u << 20) / 4);
}

// The title flips buffer `index`: in mode 2, a registered compressed surface is decompressed in place first.
static void dc439_flip(int index) {
	const int m = dc439::mode();
	if (m == 0 || !dc439::g_any.load()) return;
	dc439::Surface s;
	{
		std::lock_guard lk(dc439::g_mu);
		auto it = std::find_if(dc439::g_surf.begin(), dc439::g_surf.end(), [index](const dc439::Surface& x) { return x.index == index; });
		if (it == dc439::g_surf.end()) return;
		it->flips++;
		it->plain    = false;
		it->flip_seq = ++dc439::g_flip_seq;
		if (it->logged < 8 || (it->flips & 1023u) == 0) {
			it->logged++;
			dc439_log(*it, "flip");
		}
		s = *it;
	}
	if (m < 2) return;
	{ // the keys first (p1b: the start-up flips show a buffer no job wrote, keys all 0x00, data all zero). Mesa
	  // 0866ae7085c1 src/amd/common/ac_descriptors.h: 0xFF DCC_UNCOMPRESSED, 0x00 DCC_CLEAR_0000 ("all bits are 0").
		const uint64_t keys  = static_cast<uint64_t>(s.w) * s.h * 4u / 256u; // one key byte per 256 B (MAX_UNCOMPRESSED 256B)
		const auto*    meta  = reinterpret_cast<const volatile uint8_t*>(s.meta);
		uint64_t       n00 = 0, nff = 0;
		for (uint64_t k = 0; k < keys; k++) {
			const uint8_t v = meta[k];
			n00 += v == 0x00;
			nff += v == 0xFF;
		}
		bool        plain = nff == keys;
		const char* why   = "keys all 0xFF (uncompressed)";
		if (!plain && n00 == keys) {
			const auto*    px = reinterpret_cast<const volatile uint64_t*>(s.data);
			const uint64_t nq = static_cast<uint64_t>(s.w) * s.h * 4u / 8u;
			uint64_t       nz = 0;
			for (uint64_t k = 0; k < nq && nz == 0; k++) nz += px[k] != 0;
			plain = nz == 0;
			why   = "keys all 0x00 (clear 0000) and the surface all zero";
		}
		std::lock_guard lk(dc439::g_mu);
		for (auto& x: dc439::g_surf) {
			if (x.index != index) continue;
			x.plain = plain;
			if (plain) {
				x.done++;
				if (x.done <= 4 || (x.done & 1023u) == 0) std::fprintf(stderr, "[bc5] exp 0439 (tag dc439): t %.3f s index %d presented as plain without a pass: %s\n", timing_now(), index, why);
			} else if (x.logged < 16) {
				x.logged++;
				std::fprintf(stderr, "[bc5] exp 0439 (tag dc439): t %.3f s index %d keys: 0x00 %" PRIu64 ", 0xFF %" PRIu64 ", other %" PRIu64 " of %" PRIu64 ": a pass is needed\n", timing_now(), index, n00, nff, keys - n00 - nff, keys);
			}
		}
		if (plain) return;
	}
	if (!s.block.valid || !s.block.dcc_enable() || s.block.dcc_base() != s.meta) {
		std::lock_guard lk(dc439::g_mu);
		for (auto& x: dc439::g_surf)
			if (x.index == index && x.no_block++ < 8) dc439_log(x, "NOT decompressed (no matching DCC block)");
		return;
	}
	if (!dc439::g_code_ok) {
		auto* code = static_cast<volatile uint32_t*>(g_dev ? g_dev->code_area() : nullptr);
		if (code == nullptr) return;
		constexpr uint64_t kOff = 7ull << 20; // the code area's last MiB; exp 0137/0141 use its start and +4 MiB
		for (size_t k = 0; k < bc5::dc439::kVs.size(); k++) code[kOff / 4 + k] = bc5::dc439::kVs[k];
		for (size_t k = 0; k < bc5::dc439::kPs.size(); k++) code[(kOff + 256) / 4 + k] = bc5::dc439::kPs[k];
		std::atomic_thread_fence(std::memory_order_seq_cst);
		dc439::g_vs_va   = bc5::direct::Device::kCodeVa + kOff;
		dc439::g_ps_va   = bc5::direct::Device::kCodeVa + kOff + 256;
		dc439::g_code_ok = true;
		std::fprintf(stderr, "[bc5] exp 0439 (tag dc439): decompress programs at 0x%" PRIx64 " (VS) and 0x%" PRIx64 " (PS)\n", dc439::g_vs_va, dc439::g_ps_va);
	}
	static std::vector<uint32_t> ib; // kept until the drain below
	ib = bc5::dc439::build(s.block, s.w, s.h, dc439::g_vs_va, dc439::g_ps_va);
	const double t0 = timing_now();
	drain(); // the frame's jobs on every ring are done: the surface holds the title's last write
	const double   t1        = timing_now();
	const uint64_t ok_before = g_ok.load();
	submit_now(ib.data(), static_cast<uint32_t>(ib.size()), "dc439", bc5::direct::kGfxRing, nullptr);
	drain();
	const double t2 = timing_now();
	const bool   ok = g_dev && !g_dev->wedged() && g_ok.load() > ok_before;
	std::lock_guard lk(dc439::g_mu);
	for (auto& x: dc439::g_surf) {
		if (x.index != index) continue;
		x.plain = ok;
		if (ok) x.done++;
		else x.failed++;
		if (x.done + x.failed <= 4 || !ok || ((x.done + x.failed) & 1023u) == 0) {
			std::fprintf(stderr, "[bc5] exp 0439 (tag dc439): t %.3f s decompress of index %d (0x%" PRIx64 ", %zu dwords): %s; drain before %.2f ms, the job and its drain %.2f ms\n", t2, index, x.data, ib.size(),
			             ok ? "OK" : "FAILED", (t1 - t0) * 1e3, (t2 - t1) * 1e3);
		}
	}
}
'''

TAIL = r'''
// exp 0439 (tag dc439): called by VideoOut (videoOut.cpp) for a registered compressed buffer and at the present.
extern "C" void bc5_dc439_register(int index, uint64_t data, uint64_t meta, uint32_t w, uint32_t h, uint32_t dcc, uint64_t fmt) {
	if (Libs::Bc5Gc::Direct::dc439::mode() == 0) return;
	std::lock_guard lk(Libs::Bc5Gc::Direct::dc439::g_mu);
	auto& v = Libs::Bc5Gc::Direct::dc439::g_surf;
	v.erase(std::remove_if(v.begin(), v.end(), [index](const Libs::Bc5Gc::Direct::dc439::Surface& x) { return x.index == index; }), v.end());
	Libs::Bc5Gc::Direct::dc439::Surface s;
	s.index = index;
	s.data  = data;
	s.meta  = meta;
	s.w     = w;
	s.h     = h;
	s.dcc   = dcc;
	s.fmt   = fmt;
	v.push_back(s);
	Libs::Bc5Gc::Direct::dc439::g_any = true;
	std::fprintf(stderr, "[bc5] exp 0439 (tag dc439): registered compressed buffer index %d: data 0x%" PRIx64 " metadata 0x%" PRIx64 " %ux%u dcc_control 0x%x pixel_format 0x%016" PRIx64 "\n", index, data, meta, w, h, dcc, fmt);
}
extern "C" int bc5_dc439_plain(uint64_t data) {
	if (Libs::Bc5Gc::Direct::dc439::mode() < 2) return 0;
	std::lock_guard lk(Libs::Bc5Gc::Direct::dc439::g_mu);
	// several indices share one buffer (0, 2, 4 and 1, 3, 5 here): the one flipped last decides
	const Libs::Bc5Gc::Direct::dc439::Surface* last = nullptr;
	for (const auto& x: Libs::Bc5Gc::Direct::dc439::g_surf)
		if (x.data == data && x.flip_seq != 0 && (last == nullptr || x.flip_seq > last->flip_seq)) last = &x;
	return last != nullptr && last->plain ? 1 : 0;
}
'''


# exp 0439 (tag mw439): the map-call rule (the top session's decision 1 of 11-21): a direct view the title mapped with
# GPU write (KytyPlus memory.cpp PROT_GPU_WRITE 0x20; TODO(verify) the bit's meaning against a public source, the
# evidence is run n4's map log) is eager, with no name list, when BC5_DIRECT_EAGER_GPU_WRITE=1.
MW = r"""
// exp 0439 (tag mw439): BC5_DIRECT_EAGER_GPU_WRITE=1: a view of direct memory whose map call gave GPU write (KytyPlus
// PROT_GPU_WRITE 0x20, the protection the title passed; TODO(verify) against a public source) is imported whole, as
// the eager names are: the GPU writes it from the map call on, the CPU may never (the third title's 3.4 GB view at
// 0x5000000000, fault records 20261121-113617/-114357). A by-data name (bd412) still wins.
static bool mw439_on() {
	static const bool v = [] {
		const char* e = std::getenv("BC5_DIRECT_EAGER_GPU_WRITE");
		const bool  on = e != nullptr && e[0] == '1' && e[1] == 0;
		std::fprintf(stderr, "[bc5] exp 0439 (tag mw439): BC5_DIRECT_EAGER_GPU_WRITE=%d (1: GPU-writable direct views eager)\n", on ? 1 : 0);
		return on;
	}();
	return v;
}
static bool mw439_eager(uint64_t start, uint64_t size, int prot, const char* name) {
	if (!mw439_on() || (prot & 0x20) == 0 || bd412_name(name)) return false;
	static std::mutex                   m;
	static std::set<uint64_t>           seen;
	static uint64_t                     total = 0;
	std::lock_guard                     lk(m);
	if (seen.insert(start).second) {
		total += size;
		if (seen.size() <= 64) std::fprintf(stderr, "[bc5] exp 0439 (tag mw439): view 0x%" PRIx64 "+0x%" PRIx64 " (%s, prot 0x%x) eager by its GPU write; %zu such views, %.1f MiB\n", start, size, name != nullptr && *name != 0 ? name : "unnamed", prot, seen.size(), static_cast<double>(total) / 1048576.0);
	}
	return true;
}
"""
s = open(src + '/bc5LleAgc.cpp', encoding='utf-8', newline='').read()
a = 'static std::vector<DView> direct_views_build(const DState& S) {\n'
s = rep(s, a, MW + a)
a = ('\t\tLibs::LibKernel::Memory::Bc5ForEachMappedRange(nullptr, &v, [](uint64_t start, uint64_t size, uint64_t offset, int type, int, const char* name, void* p) {\n'
     '\t\t\tif (type == 0 && size != 0) static_cast<std::vector<DView>*>(p)->push_back({start, size, offset, name != nullptr ? name : "", ls415_name_class(name, false), ls415_name_class(name, true)});\n')
s = rep(s, a, '\t\tLibs::LibKernel::Memory::Bc5ForEachMappedRange(nullptr, &v, [](uint64_t start, uint64_t size, uint64_t offset, int type, int prot, const char* name, void* p) {\n'
     '\t\t\tif (type == 0 && size != 0) {\n'
     '\t\t\t\tconst bool gw = mw439_eager(start, size, prot, name); // exp 0439 (tag mw439)\n'
     '\t\t\t\tstatic_cast<std::vector<DView>*>(p)->push_back({start, size, offset, name != nullptr ? name : "", ls415_name_class(name, false) && !gw, ls415_name_class(name, true) || gw});\n'
     '\t\t\t}\n')
s = rep(s, '#include "bc5/direct.hpp"\n',
        '#include "bc5/direct.hpp"\n'
        '#include "bc5/state_stack.hpp" // exp 0439 (tag dc439): the GFX ring\'s context, followed on the host\n'
        '#include "bc5/dc0439.hpp"      // exp 0439 (tag dc439): the DCC display buffers\n')
a = 'static void submit_now(const uint32_t* ib, uint32_t num_dwords, const char* kind, int ring, const Chain* chain);\n'
s = rep(s, a, a + 'static void dc439_track(const uint32_t* ib, uint32_t n, const bc5::policy::FilterOptions& opt, int ring, const char* kind); // exp 0439 (tag dc439)\n')
a = '\tconst uint64_t ls_t3 = SoftCp::now_ns(); // experiment 0415 (ls415c)\n\tbc5::direct::SubmitResult r;\n'
s = rep(s, a, '\tconst uint64_t ls_t3 = SoftCp::now_ns(); // experiment 0415 (ls415c)\n'
        '\tdc439_track(sub_ib, sub_n, opt, qring, kind); // exp 0439 (tag dc439): before the job, under the device lock\n'
        '\tbc5::direct::SubmitResult r;\n')
a = '#else\nstatic void init_once() {}\nstatic void submit(const uint32_t*, uint32_t, const char*) {}\n'
s = rep(s, a, GLUE + '#else\nstatic void dc439_flip(int) {}\nstatic void init_once() {}\nstatic void submit(const uint32_t*, uint32_t, const char*) {}\n')
a = ('\t\tLOGF("[bc5-gc] VideoOutSubmitEopFlip(%d, %d, %d, 0x%" PRIx64 ", %p)\\n", handle, index,\n'
     '\t\t     flip_mode, flip_arg, unk);\n\t}\n')
EF = r'''	{ // exp 0439 (tag ef439): what the title passes as the fifth argument (a pointer into its stack)
		static int ef_n = 0;
		if (unk != nullptr && ef_n++ < 6) {
			const auto* q = static_cast<const uint64_t*>(unk);
			std::fprintf(stderr, "[bc5] exp 0439 (tag ef439): SubmitEopFlip(%d, %d, %d, 0x%llx, %p): %016llx %016llx %016llx %016llx %016llx %016llx %016llx %016llx\n", handle, index, flip_mode,
			             static_cast<unsigned long long>(flip_arg), unk, (unsigned long long)q[0], (unsigned long long)q[1], (unsigned long long)q[2], (unsigned long long)q[3], (unsigned long long)q[4],
			             (unsigned long long)q[5], (unsigned long long)q[6], (unsigned long long)q[7]);
		}
	}
	{ // exp 0439 (tag tk439): BC5_0439_EOP_TOKEN=1: the fifth argument is an OUT pointer to a 32-bit flip token (AnyPS5
	  // core/libs/prx/libSceVideoOut/src/VideoOutDriver.cpp SubmitEopFlip, GPL-2.0, 8b403579: AgcDriverReserveEopFlip's token,
	  // 0x04000000..0x07ffffff, never repeated; 0 = FLIP_QUEUE_FULL; the console encoding UNVERIFIED there). We wrote nothing.
		static const bool tk = [] {
			const char* e = std::getenv("BC5_0439_EOP_TOKEN");
			const bool  on = e != nullptr && e[0] == '1' && e[1] == 0;
			std::fprintf(stderr, "[bc5] exp 0439 (tag tk439): BC5_0439_EOP_TOKEN=%d\n", on ? 1 : 0);
			return on;
		}();
		static std::atomic<uint32_t> next {0x04000000u};
		if (tk && unk != nullptr) {
			auto*          t   = static_cast<uint32_t*>(unk);
			const uint32_t old = *t;
			const uint32_t v   = next.fetch_add(1);
			*t                 = v;
			static int tk_n = 0;
			if (tk_n++ < 16) std::fprintf(stderr, "[bc5] exp 0439 (tag tk439): SubmitEopFlip(%d, %d): token 0x%08x written to %p (was 0x%08x)\n", handle, index, v, unk, old);
		}
	}
	{ // exp 0439 (tag fc439): a running flip count for any title (the smokes' rate)
		static std::atomic<uint64_t> fc {0};
		const uint64_t               k = ++fc;
		if (k == 1 || k % 300 == 0) std::fprintf(stderr, "[bc5] exp 0439 (tag fc439): t %.3f s flip %" PRIu64 "\n", Bc5Gc::Direct::timing_now(), k);
	}
	Bc5Gc::Direct::dc439_flip(index); // exp 0439 (tag dc439): a compressed display buffer decompressed in place (mode 2)
'''
s = rep(s, a, a + EF)
s += TAIL
# 2) the soft CP's executions and refusals of MEM_SEMAPHORE, to stderr
s = rep(s, '''	g_r3gpu_count[set ? kR3MemsemSet : kR3MemsemAdd]++;''', '''	g_r3gpu_count[set ? kR3MemsemSet : kR3MemsemAdd]++;
	{ // exp 0439 (tag wr439)
		static int k = 0;
		if (k++ < 64) std::fprintf(stderr, "[bc5] exp 0439 (tag wr439): soft CP MEM_SEMAPHORE signal (%s) on 0x%" PRIx64 " -> 0x%" PRIx64 "\\n", set ? "set 1" : "add 1", a, *w);
	}''')
# exp 0439 (tag eq439): BC5_0439_EQ_ANY=1: a RELEASE_MEM / EVENT_WRITE_EOP interrupt reaches every registered
# EVFILT_GRAPHICS ident (the third title registers ident 0x52, which fire_eop never fires), with INT_SEL read as 3 bits
# (its packets carry INT_SEL 4, which "& 3" turned into no interrupt) and data = INT_CTXID << 16.
s = rep(s, '''static void release_mem(const uint32_t* p, uint32_t payload, bool write) {''', '''// exp 0439 (tag eq439), BC5_0439_EQ_ANY=1 (default off): the third title registers EVFILT_GRAPHICS ident 0x52 (kevent
// change, run t1) and raises its interrupts with RELEASE_MEM INT_SEL 4 and an INT_CTXID (0x08100001, run t1). Today
// INT_SEL is read as 2 bits (4 & 3 = 0: no interrupt) and fire_eop() fires the fixed idents 0x40 / 0 / compute only.
// With the switch: INT_SEL is 3 bits (dword 2 bits 26:24; TODO(verify) the width and value 4 "send INT_CTXID", AMD PAL's
// gfx9-plus PM4 packet headers; Mesa 0866ae7085c1 sid.h only defines EOP_INT_SEL(x) << 24 with 0 and 3), and every
// registered EVFILT_GRAPHICS ident is fired with data = INT_CTXID << 16 (reimpl-agc-psml's description: the title reads
// the context id from the event data >> 16; TODO(verify)).
static bool eq439_on() {
	static const bool v = [] {
		const char* e = std::getenv("BC5_0439_EQ_ANY");
		const bool  on = e != nullptr && e[0] == '1' && e[1] == 0;
		std::fprintf(stderr, "[bc5] exp 0439 (tag eq439): BC5_0439_EQ_ANY=%d\\n", on ? 1 : 0);
		return on;
	}();
	return v;
}
static void eq439_fire_all(uint32_t int_sel, uint32_t ctxid) {
	std::vector<EqRegistration> eqs;
	{
		std::lock_guard lock(g_eq_mutex);
		eqs = g_eqs;
	}
	const uint64_t data = static_cast<uint64_t>(ctxid) << 16u;
	for (const auto& r: eqs) {
		Libs::LibKernel::EventQueue::KernelTriggerEvent(r.eq, static_cast<uintptr_t>(r.ident), Libs::LibKernel::EventQueue::KERNEL_EVFILT_GRAPHICS, reinterpret_cast<void*>(data));
	}
	static std::atomic<int> n {0};
	if (n++ < 32) std::fprintf(stderr, "[bc5] exp 0439 (tag eq439): interrupt INT_SEL %u INT_CTXID 0x%08x fired to %zu registered EVFILT_GRAPHICS idents (data 0x%" PRIx64 ")\\n", int_sel, ctxid, eqs.size(), data);
}

static void release_mem(const uint32_t* p, uint32_t payload, bool write) {''')
s = rep(s, '''	if (write) write_timestamp_or_data(data_sel, a, lo, hi);
	if (int_sel != 0) {
		fire_eop(lo | (static_cast<uint64_t>(hi) << 32u));
	}
}''', '''	if (write) write_timestamp_or_data(data_sel, a, lo, hi);
	{ // exp 0439 (tag eq439): the soft CP's RELEASE_MEMs, as it sees them
		static std::atomic<int> rn {0};
		if (rn++ < 64) std::fprintf(stderr, "[bc5] exp 0439 (tag eq439): soft CP RELEASE_MEM write %d INT_SEL %u DATA_SEL %u address 0x%" PRIx64 " INT_CTXID 0x%08x\\n", write ? 1 : 0, (data_cntl >> 24u) & 7u, data_sel, a, payload >= 7 ? p[7] : 0u);
	}
	if (eq439_on() && ((data_cntl >> 24u) & 7u) != 0) { // exp 0439 (tag eq439)
		eq439_fire_all((data_cntl >> 24u) & 7u, payload >= 7 ? p[7] : 0u);
		if (int_sel != 0) fire_eop(lo | (static_cast<uint64_t>(hi) << 32u)); // the fixed idents as before
		return;
	}
	if (int_sel != 0) {
		fire_eop(lo | (static_cast<uint64_t>(hi) << 32u));
	}
}''')
s = rep(s, '''static void register_eq(Libs::LibKernel::EventQueue::KernelEqueue eq, int ident, bool add) {
	std::lock_guard lock(g_eq_mutex);''', '''static void register_eq(Libs::LibKernel::EventQueue::KernelEqueue eq, int ident, bool add) {
	std::fprintf(stderr, "[bc5] exp 0439 (tag eq439): EVFILT_GRAPHICS ident 0x%x %s\\n", ident, add ? "registered" : "removed");
	std::lock_guard lock(g_eq_mutex);''')
# exp 0439 (tag rp439): the soft CP's replays of the title's dcbs (submit list, kind "dcb"): start and end of each,
# and every COND_EXEC it meets in a dcb (guard address, value, guarded dwords, skipped or run).
s = rep(s, '''	t_cur_buf  = buf; // experiment 0343: for the soft-cp wait lines
	t_cur_n    = num_dwords;
	t_cur_kind = kind;
	execute(buf, num_dwords, 0);''', '''	t_cur_buf  = buf; // experiment 0343: for the soft-cp wait lines
	t_cur_n    = num_dwords;
	t_cur_kind = kind;
	static std::atomic<int> rp_n {0};
	const bool              rp_dcb = kind != nullptr && std::strcmp(kind, "dcb") == 0;
	const int               rp_k   = rp_dcb ? rp_n++ : 1 << 30;
	if (rp_k < 60) std::fprintf(stderr, "[bc5] exp 0439 (tag rp439): t %.3f s soft CP replay %d of dcb %p (%u dwords) starts\\n", Direct::timing_now(), rp_k, static_cast<const void*>(buf), num_dwords);
	execute(buf, num_dwords, 0);
	if (rp_k < 60) std::fprintf(stderr, "[bc5] exp 0439 (tag rp439): t %.3f s soft CP replay %d of dcb %p ends\\n", Direct::timing_now(), rp_k, static_cast<const void*>(buf));''')
s = rep(s, '''					const uint32_t exec_count = p[4] & 0x3fffu;
					if (a != 0 && *reinterpret_cast<volatile uint32_t*>(a) == 0) {
						len += exec_count;
					}''', '''					const uint32_t exec_count = p[4] & 0x3fffu;
					const uint32_t rp_v       = a != 0 ? *reinterpret_cast<volatile uint32_t*>(a) : 0u;
					if (a != 0 && *reinterpret_cast<volatile uint32_t*>(a) == 0) {
						len += exec_count;
					}
					{ // exp 0439 (tag rp439)
						static std::atomic<int> ce_n {0};
						if (t_cur_kind != nullptr && std::strcmp(t_cur_kind, "dcb") == 0 && ce_n++ < 120)
							std::fprintf(stderr, "[bc5] exp 0439 (tag rp439): dcb %p @%u COND_EXEC guard 0x%" PRIx64 " = 0x%08x, %u dwords %s (next op 0x%02x)\\n", static_cast<const void*>(t_cur_buf), static_cast<unsigned>(p - t_cur_buf), a, rp_v,
							             exec_count, a != 0 && rp_v == 0 ? "SKIPPED" : "run", ((p[5] >> 8u) & 0xffu));
					}''')
# exp 0439 (tag f52): BC5_0439_FIRE52=1|2|3, a test arm (the top session, 11-21): the third title's ProxySetSync waits on
# its "ProxySet Cull" equeue for EVFILT_GRAPHICS ident 0x52, which nothing raises. 1: once at our first flip, 2: at every flip,
# 3: once at the first guest compute-queue job's completion. Off by default; a guess, not a fix.
s = rep(s, '''static void fire_eop(uint64_t data) {''', '''// exp 0439 (tag f52): see the generator's note; mode 'A' or 'B' from BC5_0439_FIRE52, 0 off.
static char f52_mode() {
	static const char v = [] {
		const char* e = std::getenv("BC5_0439_FIRE52");
		const char  m = (e != nullptr && e[0] >= '1' && e[0] <= '4' && e[1] == 0) ? e[0] : 0; // 1 first flip, 2 every flip, 3 first compute job, 4 at 60 Hz
		std::fprintf(stderr, "[bc5] exp 0439 (tag f52): BC5_0439_FIRE52=%c\\n", m != 0 ? m : '0');
		return m;
	}();
	return v;
}
static void f52_fire(const char* why) {
	std::vector<EqRegistration> eqs;
	{
		std::lock_guard lock(g_eq_mutex);
		eqs = g_eqs;
	}
	int n = 0;
	for (const auto& r: eqs) {
		if (r.ident != 0x52) continue;
		Libs::LibKernel::EventQueue::KernelTriggerEvent(r.eq, static_cast<uintptr_t>(r.ident), Libs::LibKernel::EventQueue::KERNEL_EVFILT_GRAPHICS, reinterpret_cast<void*>(uint64_t {0}));
		n++;
	}
	static std::atomic<int> k {0};
	if (k++ < 40) std::fprintf(stderr, "[bc5] exp 0439 (tag f52): t %.3f s ident 0x52 fired (%s) to %d registration(s), data 0x0\\n", Direct::timing_now(), why, n);
}

static void f52_stream_start() { // mode 4: a host thread at 60 Hz, our stand-in for the present clock, once 0x52 is registered
	static std::once_flag once;
	std::call_once(once, [] {
		std::thread([] {
			pthread_setname_np(pthread_self(), "bc5-f52-60hz");
			for (;;) {
				std::this_thread::sleep_for(std::chrono::microseconds(16667));
				if (f52_registered()) f52_fire("60 Hz");
			}
		}).detach();
	});
}

static void fire_eop(uint64_t data) {''')
s = rep(s, '''					t_gpu_done.clear();
					// The read pointer goes where the queue registration named it and — what the
					// driver library's free-space check actually reads (its queue table, +0x70;
					// experiment 0018) — into the dword right behind the ring.''', '''					t_gpu_done.clear();
					{ // exp 0439 (tag f52): mode 3, once, the first guest compute-queue job's completion
						static std::atomic<bool> f52_once {false};
						if (f52_mode() == '3' && !f52_once.exchange(true)) f52_fire("the first compute-queue job completed");
					}
					// The read pointer goes where the queue registration named it and — what the
					// driver library's free-space check actually reads (its queue table, +0x70;
					// experiment 0018) — into the dword right behind the ring.''')
s = rep(s, '''		Bc5Gc::Direct::post([handle, index, flip_mode, flip_arg](bool) {
			VideoOut::VideoOutSubmitFlip(handle, index, flip_mode, flip_arg);''', '''		Bc5Gc::Direct::post([handle, index, flip_mode, flip_arg](bool) {
			VideoOut::VideoOutSubmitFlip(handle, index, flip_mode, flip_arg);
			{ // exp 0439 (tag f52): mode 1 once at our first flip, mode 2 at every flip
				static std::atomic<bool> f52_first {false};
				const char               m = Bc5Gc::SoftCp::f52_mode();
				if (m == '2' || (m == '1' && !f52_first.exchange(true))) Bc5Gc::SoftCp::f52_fire("our flip completed");
			}''')
# exp 0439 (tag kv439): the title's kevent waits (the third title's ProxySetSync on "ProxySet Cull"): start and return,
# with every returned event; and f52's data variants (BC5_0439_FIRE52_DATA=x52: (n << 16) | 0x52, n counting from 1).
s = rep(s, '''	if (nevents > 0 && events != nullptr) {
		int out = 0;
		Bc5Gc::Direct::chain_observe(); // ADR 0010 section B: the EOP events it waits for come after the chain's fence''', '''	auto kv_log = [&](const char* what, int n) { // exp 0439 (tag kv439)
		static std::atomic<int> kv_n {0};
		if (kv_n++ >= 80) return;
		char tn[32] = {};
		pthread_getname_np(pthread_self(), tn, sizeof(tn));
		std::fprintf(stderr, "[bc5] exp 0439 (tag kv439): t %.3f s %s: eq %d thread %s nevents %d -> %d\\n", Bc5Gc::Direct::timing_now(), what, kq, tn, nevents, n);
		for (int k = 0; k < n && k < 4 && events != nullptr; k++) {
			const auto* e = reinterpret_cast<const EQ::KernelEvent*>(events) + k;
			std::fprintf(stderr, "[bc5] exp 0439 (tag kv439):   event %d: ident 0x%" PRIx64 " filter %d flags 0x%x fflags 0x%x data 0x%" PRIx64 " udata %p\\n", k, static_cast<uint64_t>(e->ident), static_cast<int>(e->filter),
			             static_cast<unsigned>(e->flags), static_cast<unsigned>(e->fflags), static_cast<uint64_t>(e->data), e->udata);
		}
	};
	if (nevents > 0 && events != nullptr) {
		kv_log("wait starts", 0);
		int out = 0;
		Bc5Gc::Direct::chain_observe(); // ADR 0010 section B: the EOP events it waits for come after the chain's fence''')
s = rep(s, '''			const int n = Bc5KeventTimed0405(eq, reinterpret_cast<EQ::KernelEvent*>(events), nevents, timeout);
			Bc5Gc::Direct::frame_profile_eqwait(static_cast<double>(Bc5Gc::SoftCp::now_ns() - t_eq) / 1e6);
			return n;''', '''			const int n = Bc5KeventTimed0405(eq, reinterpret_cast<EQ::KernelEvent*>(events), nevents, timeout);
			Bc5Gc::Direct::frame_profile_eqwait(static_cast<double>(Bc5Gc::SoftCp::now_ns() - t_eq) / 1e6);
			kv_log("timed wait returns", n);
			return n;''')
s = rep(s, '''		(void)timeout; // TODO(bc5): honour the timespec
		return r == 0 ? out : -1;''', '''		(void)timeout; // TODO(bc5): honour the timespec
		kv_log("wait returns", r == 0 ? out : -1);
		return r == 0 ? out : -1;''')
# f52: data variants and mode 3 after the registration
s = rep(s, '''		Libs::LibKernel::EventQueue::KernelTriggerEvent(r.eq, static_cast<uintptr_t>(r.ident), Libs::LibKernel::EventQueue::KERNEL_EVFILT_GRAPHICS, reinterpret_cast<void*>(uint64_t {0}));
		n++;
	}
	static std::atomic<int> k {0};
	if (k++ < 40) std::fprintf(stderr, "[bc5] exp 0439 (tag f52): t %.3f s ident 0x52 fired (%s) to %d registration(s), data 0x0\\n", Direct::timing_now(), why, n);''', '''		Libs::LibKernel::EventQueue::KernelTriggerEvent(r.eq, static_cast<uintptr_t>(r.ident), Libs::LibKernel::EventQueue::KERNEL_EVFILT_GRAPHICS, reinterpret_cast<void*>(f52_data_next));
		n++;
	}
	static std::atomic<int> k {0};
	if (k++ < 40) std::fprintf(stderr, "[bc5] exp 0439 (tag f52): t %.3f s ident 0x52 fired (%s) to %d registration(s), data 0x%" PRIx64 "\\n", Direct::timing_now(), why, n, f52_data_next);''')
s = rep(s, '''static void f52_fire(const char* why) {
	std::vector<EqRegistration> eqs;''', '''static bool f52_registered() {
	std::lock_guard lock(g_eq_mutex);
	for (const auto& r: g_eqs)
		if (r.ident == 0x52) return true;
	return false;
}
static void f52_fire(const char* why) {
	static const bool        x52 = [] { const char* e = std::getenv("BC5_0439_FIRE52_DATA"); return e != nullptr && std::strcmp(e, "x52") == 0; }();
	static std::atomic<uint64_t> f52_seq {0};
	const uint64_t           f52_data_next = x52 ? ((f52_seq.fetch_add(1) + 1) << 16u) | 0x52u : 0u;
	std::vector<EqRegistration> eqs;''')
s = rep(s, '''						if (f52_mode() == '3' && !f52_once.exchange(true)) f52_fire("the first compute-queue job completed");''', '''						if (f52_mode() == '3' && f52_registered() && !f52_once.exchange(true)) f52_fire("the first compute-queue job completed after 0x52 was registered");
						if (f52_mode() == '4') f52_stream_start();''')
# exp 0439 (tag ae439): BC5_DIRECT_AGC_EOP_IDENT=1 (off by default): the soft CP raises an end-of-pipe interrupt as the
# AGC-era hosts do (bc5/dc0439.hpp agc_eop_ident / agc_eop_data / release_mem_int_sel, sources there): INT_SEL read as
# 3 bits; the ident is the queue's (graphics CP 0, a compute queue 0x20 + slot - 1, slot = the queue registration's
# doorbell slot d, known while the queue consumer replays that queue); data = (INT_CTXID << 16) | ident. Off: today's
# PS4-style fire_eop (0x40 / 0 / compute A/B) unchanged.
s = rep(s, '''static void release_mem(const uint32_t* p, uint32_t payload, bool write) {''', '''static thread_local uint32_t t_ae439_slot = 0; // exp 0439 (tag ae439): the replayed compute queue's slot, 0 = graphics
static bool ae439_on() {
	static const bool v = [] {
		const char* e = std::getenv("BC5_DIRECT_AGC_EOP_IDENT");
		const bool  on = e != nullptr && e[0] == '1' && e[1] == 0;
		std::fprintf(stderr, "[bc5] exp 0439 (tag ae439): BC5_DIRECT_AGC_EOP_IDENT=%d\\n", on ? 1 : 0);
		return on;
	}();
	return v;
}
static void ae439_fire(uint32_t int_sel, uint32_t ctxid, const char* what) {
	const bool     compute = t_ae439_slot != 0;
	const uint32_t ident   = bc5::dc439::agc_eop_ident(compute, t_ae439_slot);
	const uint64_t data    = bc5::dc439::agc_eop_data(ctxid, ident);
	std::vector<EqRegistration> eqs;
	{
		std::lock_guard lock(g_eq_mutex);
		eqs = g_eqs;
	}
	int n = 0;
	for (const auto& r: eqs) {
		if (r.ident != static_cast<int>(ident)) continue;
		Libs::LibKernel::EventQueue::KernelTriggerEvent(r.eq, static_cast<uintptr_t>(r.ident), Libs::LibKernel::EventQueue::KERNEL_EVFILT_GRAPHICS, reinterpret_cast<void*>(data));
		n++;
	}
	static std::atomic<int> k {0};
	if (k++ < 64) std::fprintf(stderr, "[bc5] exp 0439 (tag ae439): t %.3f s %s INT_SEL %u on %s (slot 0x%x): ident 0x%x data 0x%" PRIx64 " to %d registration(s)\\n", Direct::timing_now(), what, int_sel, compute ? "a compute queue" : "graphics", t_ae439_slot, ident, data, n);
}

static void release_mem(const uint32_t* p, uint32_t payload, bool write) {''')
s = rep(s, '''	if (eq439_on() && ((data_cntl >> 24u) & 7u) != 0) { // exp 0439 (tag eq439)''', '''	if (ae439_on()) { // exp 0439 (tag ae439); the data write above has run already
		const uint32_t is3 = bc5::dc439::release_mem_int_sel(data_cntl);
		if (is3 != 0) ae439_fire(is3, payload >= 7 ? p[7] : 0u, "RELEASE_MEM");
		return;
	}
	if (eq439_on() && ((data_cntl >> 24u) & 7u) != 0) { // exp 0439 (tag eq439)''')
s = rep(s, '''	const uint64_t a         = addr64(p[2], data_cntl);
	if (write) write_timestamp_or_data(data_sel, a, p[4], p[5]);
	if (int_sel != 0) {''', '''	const uint64_t a         = addr64(p[2], data_cntl);
	if (write) write_timestamp_or_data(data_sel, a, p[4], p[5]);
	if (ae439_on()) { // exp 0439 (tag ae439): EVENT_WRITE_EOP carries no context id: 0
		if (int_sel != 0) ae439_fire(int_sel, 0u, "EVENT_WRITE_EOP");
		return;
	}
	if (int_sel != 0) {''')
s = rep(s, '''							t_compute_ring = (qq.a == 2); // TODO(bc5): which engine is compute is a guess''', '''							t_compute_ring = (qq.a == 2); // TODO(bc5): which engine is compute is a guess
							t_ae439_slot   = qq.d;        // exp 0439 (tag ae439): every registered queue is a compute queue here''')
s = rep(s, '''							t_compute_ring = false;
						}''', '''							t_compute_ring = false;
							t_ae439_slot   = 0;
						}''')
open(dst + '/bc5LleAgc.cpp', 'w', encoding='utf-8', newline='').write(s)

v = open(src + '/videoOut.cpp', encoding='utf-8', newline='').read()
a = 'extern "C" double Bc5OsdTitleFps(double* frame_ms) {'
v = rep(v, a, 'extern "C" void bc5_dc439_register(int index, uint64_t data, uint64_t meta, uint32_t w, uint32_t h, uint32_t dcc, uint64_t fmt); // exp 0439 (tag dc439)\n'
        'extern "C" int  bc5_dc439_plain(uint64_t data); // exp 0439 (tag dc439)\n' + a)
a = ('\t\tLOGF("\\tbuffers[%d] = %016" PRIx64 " metadata = %016" PRIx64 " dcc = %08" PRIx32 "\\n",\n'
     '\t\t     buffer_index_start + i, buffer.data_address, buffer.metadata_address,\n'
     '\t\t     attribute->dcc_control);\n')
v = rep(v, a, a + '\t\tif (category == VIDEO_OUT_BUFFER_ATTRIBUTE_CATEGORY_COMPRESSED) { // exp 0439 (tag dc439)\n'
        '\t\t\tbc5_dc439_register(buffer_index_start + i, buffer.data_address, buffer.metadata_address, attribute->width,\n'
        '\t\t\t                   attribute->height, attribute->dcc_control, attribute->pixel_format);\n\t\t}\n')
a = ('\t\tif (bc5_direct && source_info.data.Valid()) {\n'
     '\t\t\tLibKernel::Memory::InvalidateMemory(source_info.data.address, source_info.data.size);\n\t\t}\n')
v = rep(v, a, a + '\t\t// exp 0439 (tag dc439): a compressed surface decompressed in place at its flip is read as plain bytes.\n'
        '\t\tif (bc5_direct && source_info.metadata.compression != Graphics::VideoOutCompression::Uncompressed &&\n'
        '\t\t    bc5_dc439_plain(source_info.data.address) != 0) {\n'
        '\t\t\tsource_info.metadata = {};\n\t\t}\n')
open(dst + '/videoOut.cpp', 'w', encoding='utf-8', newline='').write(v)
print("ok")
