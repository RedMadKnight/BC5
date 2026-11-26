#!/usr/bin/env python3
# BC5 exp 0439 (tag sr439c, 11-23, the top session's order): the pass census's unit half, after mksr439b (and mkpw439,
# mkph439). Normal build only: every line under #ifndef BC5_LEAN; the lean unit defines no bc5_sr439c_block, so the
# backend's weak hook is null. bc5/sr0439c.hpp holds the logic (det-tested by test_sr0439c.cpp).
#   BC5_0439_PASS_DUMP=<private dir>  turns it on (unset: one relaxed load per submit and per flip).
#   BC5_0439_PASS_AT=60,100           arm at these seconds after the first flip (each once); L3 + R3 held 1 s arms too
#                                     (with PASS_DUMP set the pad goes to this catcher, not to sr439b's).
#   BC5_0439_PASS_MB=<cap>            the arena's cap (default 1024, 64..8192); the budget is also bounded by
#                                     MemAvailable - 768 MiB and the GTT headroom - 256 MiB, read at the survey's end.
#   BC5_0439_PASS_WINDOW=x0,x1,y0,y1  the window copied whole (default 0.35,0.65,0.25,0.95: the character's box).
#   BC5_0439_PASS_STRIDE=<n>          every n-th other 64 KiB tile or chunk (default 16).
#   BC5_0439_PASS_MEC=0               no copies on the compute rings (their DMA_DATA is unverified on the MEC).
# One arm: the survey frame (each submit walked piece by piece: its ops' output surfaces, the sampled hash of each at its
# first sight), at its flip a drain, the hashes again, the plan (sr0439c.hpp: need, budget, level) and the arena; then
# copy frame A (and B when the level is 3): each piece's block of copies is queued for the backend; at the frame's flip a
# drain, the census of every copied 64 KiB tile, and the files: <dir>/sr439c-<time>-a<n>-<A|B>/{meta.txt, surf.tsv,
# ops.tsv, inc.tsv, tiles.tsv, tiles.bin (the window tiles raw)}. Frames are cut at the flips as sr439b's are: submits
# made while the flip drains and plans belong to no frame.
# Usage: python mksr439c.py UNIT.cpp OUT.cpp   (every anchor exactly once)
import sys

src, dst = sys.argv[1], sys.argv[2]
s = open(src, 'rb').read().decode('utf-8', 'surrogateescape')
assert 'sr439c' not in s and 'tag sr439b' in s
crlf = '\r\n' in s
s = s.replace('\r\n', '\n')


def rep(a, b):
    global s
    assert s.count(a) == 1, (a[:70], s.count(a))
    s = s.replace(a, b)


NS = r'''} // namespace srb439
#endif
#ifndef BC5_LEAN
#include "bc5/sr0439c.hpp" // exp 0439 (tag sr439c): the pass census (normal build only)
#include <deque>
#include <memory>
extern "C" int bc5_sr439c_arena(uint64_t bytes, void** cpu, uint64_t* va); // the backend (k439/mksr439cbe.py)
// exp 0439 (tag sr439c): the pass census's state. Lock order: a submitter (device lock) then g_mu; the backend's block
// hook (inside the device's submit) takes g_mu; the flip drains with no lock, takes g_mu for its work and calls the
// arena (which takes the device's locks) with g_mu released.
namespace scu439 {
namespace sc = bc5::sr439c;
static const char* dir() {
	static const char* d = [] {
		const char* e = std::getenv("BC5_0439_PASS_DUMP");
		return e != nullptr && e[0] != 0 ? e : static_cast<const char*>(nullptr);
	}();
	return d;
}
struct Cfg {
	sc::Window win;
	uint32_t   stride = 16;
	uint64_t   cap    = 1024ull << 20;
	bool       mec    = true;
	bool       dcc_only = false; // v3 (BC5_0439_PASS_DCC_ONLY=1): only DCC colour targets, copied whole with their keys
	bool       cblog    = false; // cblog (BC5_0439_PASS_CBLOG=1): every draw's colour and depth target registers, pieces lo..hi
	uint32_t   cb_lo = 140, cb_hi = 175, cb_nodump = 0;
};
static const Cfg& cfg() {
	static const Cfg c = [] {
		Cfg x;
		x.win = sc::parse_window(std::getenv("BC5_0439_PASS_WINDOW"));
		if (const char* e = std::getenv("BC5_0439_PASS_STRIDE"); e != nullptr) x.stride = static_cast<uint32_t>(std::clamp<unsigned long>(std::strtoul(e, nullptr, 10), 1, 1024));
		if (const char* e = std::getenv("BC5_0439_PASS_MB"); e != nullptr) x.cap = std::clamp<unsigned long long>(std::strtoull(e, nullptr, 10), 64, 8192) << 20;
		if (const char* e = std::getenv("BC5_0439_PASS_MEC"); e != nullptr && e[0] == '0' && e[1] == 0) x.mec = false;
		if (const char* e = std::getenv("BC5_0439_PASS_DCC_ONLY"); e != nullptr && e[0] == '1' && e[1] == 0) x.dcc_only = true;
		if (const char* e = std::getenv("BC5_0439_PASS_CBLOG"); e != nullptr && e[0] == '1' && e[1] == 0) x.cblog = true;
		if (const char* e = std::getenv("BC5_0439_PASS_CBLOG_PIECES"); e != nullptr) std::sscanf(e, "%u,%u", &x.cb_lo, &x.cb_hi);
		if (const char* e = std::getenv("BC5_0439_PASS_NORAW"); e != nullptr && e[0] == '1' && e[1] == 0) x.cb_nodump = 1;
		if (x.cblog) std::fprintf(stderr, "[bc5] exp 0439 (tag sr439c cblog): every draw's CB_COLOR0-7 and depth target registers in pieces %u-%u of each copy frame (cblog.tsv)\n", x.cb_lo, x.cb_hi);
		if (x.dcc_only) std::fprintf(stderr, "[bc5] exp 0439 (tag sr439c v3): DCC colour targets only, each copied whole with its keys and the COPY decompressed after the frame\n");
		std::fprintf(stderr, "[bc5] exp 0439 (tag sr439c): the pass census to %s: window %.2f-%.2f x %.2f-%.2f, stride %u, cap %llu MiB, compute rings %s, arms at %s\n", dir(), x.win.x0, x.win.x1, x.win.y0,
		             x.win.y1, x.stride, static_cast<unsigned long long>(x.cap >> 20), x.mec ? "on" : "off", std::getenv("BC5_0439_PASS_AT") != nullptr ? std::getenv("BC5_0439_PASS_AT") : "(none: L3 + R3 only)");
		return x;
	}();
	return c;
}
struct Surf {
	uint64_t          base = 0, bytes = 0, dcc_base = 0;
	uint32_t          w = 0, h = 0, d = 1, bpe = 0, sw = 0, fmt = 0;
	bc5::sr439b::Kind kind = bc5::sr439b::Kind::Other;
	bool              cb = false, depth = false, dcc = false, buffer = false;
	sc::Geo           g;
	std::vector<sc::Range> rr;
	uint64_t          h0 = 0, h1 = 0;
	uint32_t          depth_k = 0;
	bool              surveyed = false;
};
struct Inc {
	uint32_t surf = 0, submit = 0, piece = 0, op0 = 0, op1 = 0;
	int      ring = 0, where = -1;
	uint64_t off = 0, bytes = 0, keys_off = 0, keys_len = 0;
	bool     placed = false;
	std::vector<sc::Range> rr; // the ranges copied (mapped), in order, packed from off
	// v3: a DCC target copied whole: its guest addresses, size, and the context at its pass (for dc439::find)
	bool     dcc = false, decompressed = false;
	uint32_t w = 0, h = 0;
	uint64_t src = 0, dcc_src = 0;
	std::shared_ptr<sc::RegState> snap;
};
struct Pend {
	int                   ring = 0;
	const uint32_t*       src  = nullptr;
	std::vector<uint32_t> blk, incs;
	uint64_t              gen = 0; // rsv439: the resolve submit count when queued (an unclaimed one is dropped later)
};
struct OpRow {
	uint32_t    seq = 0, submit = 0, piece = 0;
	int         ring = 0;
	char        kind = 'd';
	uint64_t    pgm  = 0;
	std::string refs;
};
constexpr uint64_t kHeader = 64 * 1024;
static std::mutex                         g_mu;
static sc::Machine                        g_m;
static bc5::sr439b::Recorder              g_rec;
static std::unordered_map<int, sc::DbTrack> g_db;
static std::unordered_map<int, sc::CtxTrack> g_ct; // v3: the context at each DCC target's draws (GFX ring)
static uint64_t g_skip_nondcc = 0, g_skip_nosnap = 0;
static std::vector<std::string> g_cblog; // cblog: the rows of this copy frame
static uint32_t g_cq_now = 0; // the device's jobs in flight when the hook ran (set by the caller)
static std::vector<std::string> g_subrows; // submits.tsv: submit, ring, time, jobs in flight
static std::atomic<int>                   g_phase {0}, g_pad {-1};
static std::vector<Surf>                  g_s;
static std::unordered_map<uint64_t, uint32_t> g_si;
static std::vector<Inc>                   g_inc;
static std::deque<Pend>                   g_q;
static std::vector<OpRow>                 g_ops;
static std::vector<sc::PlanItem>          g_items;
static std::vector<uint32_t>              g_item_surf; // the surface of each survey item
static sc::Plan                           g_plan;
static uint8_t*                           g_cpu = nullptr;
static uint64_t                           g_va = 0, g_size = 0, g_off = 0, g_run = 0;
static uint32_t                           g_fence = 0, g_submits = 0, g_captures = 0;
static uint64_t g_skip_hash = 0, g_skip_depth = 0, g_skip_split = 0, g_skip_room = 0, g_skip_mec = 0, g_skip_unmapped = 0, g_skip_bytes = 0;
static std::string g_base, g_cdir, g_survey_note;
static std::string g_label_dir; // v2: the frame whose picture the next decompressed display surface is
static uint64_t    g_mem_avail = 0, g_gtt_total = 0, g_gtt_used = 0;

static double mb(uint64_t v) { return static_cast<double>(v) / 1e6; }
static uint64_t key(uint64_t base, uint32_t fmt, int role) { return base ^ (static_cast<uint64_t>(fmt) << 48) ^ (static_cast<uint64_t>(role) << 60); }
static uint32_t add(Surf s, uint64_t k) {
	if (auto it = g_si.find(k); it != g_si.end()) return it->second;
	s.rr = sc::ranges(s.g, s.w, s.h, cfg().win, cfg().stride);
	g_s.push_back(std::move(s));
	g_si.emplace(k, static_cast<uint32_t>(g_s.size() - 1));
	return static_cast<uint32_t>(g_s.size() - 1);
}
static uint32_t surf_of(const bc5::sr439b::Surface& x) {
	const int role = x.cb ? 1 : x.image ? 2 : 3;
	Surf      s;
	s.base = x.base, s.bytes = x.bytes, s.w = x.w, s.h = x.h, s.d = x.d, s.bpe = x.f.bpe, s.sw = x.sw_mode, s.fmt = x.fmt, s.kind = x.f.kind;
	s.cb = x.cb, s.dcc = x.cb && x.dcc, s.dcc_base = x.dcc_base, s.buffer = role == 3;
	s.g = role == 3 ? sc::geo(0, 0, 1, 0, 0, x.bytes) : sc::geo(x.w, x.h, x.d, x.f.bpe, x.sw_mode, x.bytes);
	return add(std::move(s), key(x.base, x.fmt, role));
}
static uint32_t depth_of(const sc::Depth& d) {
	Surf s;
	s.base = d.base, s.w = d.w, s.h = d.h, s.bpe = d.bpe, s.sw = d.sw, s.fmt = 2000 + d.bpe, s.depth = true;
	s.kind  = d.bpe == 4 ? bc5::sr439b::Kind::F32 : bc5::sr439b::Kind::Other; // Z_32_FLOAT (Z_24 counts as raw 32-bit words)
	s.bytes = static_cast<uint64_t>(d.w) * d.h * d.bpe;
	s.g     = sc::geo(d.w, d.h, 1, d.bpe, d.sw, s.bytes);
	return add(std::move(s), key(d.base, s.fmt, 4));
}
template <class Cov>
static std::vector<sc::Range> mapped(const Surf& x, Cov& cov) {
	std::vector<sc::Range> r;
	for (const auto& q: x.rr)
		if (cov(x.base + q.off, q.len)) r.push_back(q);
	return r;
}
static uint64_t keys_whole(const Surf& x) { return ((x.g.bytes / 256) + 0x1ffffull) & ~0xffffull; } // v3: the keys with slack
static uint64_t keys_len(const Surf& x) { return x.dcc && x.dcc_base != 0 ? std::min<uint64_t>((x.g.bytes + 255) / 256, 4ull << 20) : 0; }
static uint64_t hash(const Surf& x) {
	// 64 samples over the whole surface and, for a tiled one, 64 over its window tiles
	uint64_t h = sc::sampled_hash(x.g.bytes, [&x](uint64_t off, uint8_t* d, size_t n) { return srb439::copy(x.base + off, d, n); });
	for (const auto& q: x.rr)
		if (q.window && q.len >= 64) {
			const uint64_t w = sc::sampled_hash(q.len, [&x, &q](uint64_t off, uint8_t* d, size_t n) { return srb439::copy(x.base + q.off + off, d, n); });
			h = (h ^ w) * 1099511628211ull;
		}
	return h | 1;
}

// One submit of the survey (phase 1) or a copy frame (phase 2), before the device sees it.
template <class Cov>
static void submit(const uint32_t* ib, uint32_t num_dwords, int ring, Cov& cov, int phase) {
	const auto cr = bc5::ib_chain::collect(ib, num_dwords, cov, true);
	std::lock_guard lk(g_mu);
	if (g_phase.load() != phase) return;
	const uint32_t sub = g_submits++;
	const bool     gfx = ring == bc5::direct::kGfxRing;
	if (phase == 2) {
		char row[96];
		std::snprintf(row, sizeof(row), "%u\t%d\t%.3f\t%u", sub, ring, std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now().time_since_epoch()).count(), g_cq_now);
		g_subrows.emplace_back(row);
	}
	auto&          db  = g_db[ring];
	// 1. each piece's ops and output surfaces (sorted)
	struct PW {
		uint32_t              op0 = 0, op1 = 0;
		std::vector<uint32_t> outs;
		std::unordered_map<uint64_t, std::shared_ptr<sc::RegState>> snap; // v3: DCC target base -> the context at its last draw here
	};
	std::vector<PW> pw(cr.pieces.size());
	for (size_t k = 0; k < cr.pieces.size(); k++) {
		const auto&                                     pc = cr.pieces[k];
		PW&                                             w  = pw[k];
		std::vector<std::pair<const uint32_t*, size_t>> one {{pc.src, static_cast<size_t>(pc.n)}};
		w.op0 = static_cast<uint32_t>(g_rec.ops.size());
		g_rec.submit(one, ring, cov);
		w.op1    = static_cast<uint32_t>(g_rec.ops.size());
		auto out = [&w](uint32_t x) {
			if (std::find(w.outs.begin(), w.outs.end(), x) == w.outs.end()) w.outs.push_back(x);
		};
		for (uint32_t o = w.op0; o < w.op1; o++) {
			const auto& op = g_rec.ops[o];
			std::string refs;
			for (const auto& r: op.refs) {
				const uint32_t x = surf_of(g_rec.surf[r.surf]);
				refs += (refs.empty() ? "" : ",") + std::to_string(x) + (r.cb ? ":w" : ":v");
				if (op.kind == 'c' || r.cb) out(x);
			}
			g_ops.push_back({op.seq, sub, static_cast<uint32_t>(k), ring, op.kind, op.pgm, std::move(refs)});
		}
		db.walk(pc.src, pc.n, cov, [&](const sc::Depth& d) { out(depth_of(d)); });
		uint32_t draw_no = 0;
		g_ct[ring].piece = static_cast<uint16_t>(k);
		if ((cfg().dcc_only || cfg().cblog) && gfx)
			g_ct[ring].walk(pc.src, pc.n, k == 0, cov, [&w, &draw_no, &cov, k, sub, phase](const sc::CtxTrack& t) {
				if (cfg().cblog && phase == 2 && k >= cfg().cb_lo && k <= cfg().cb_hi) { // cblog: one row per bound target
					const auto& c  = t.s.ctx;
					const auto& ok = t.s.ctx_ok;
					auto        val = [&](uint32_t r) { return ok[r] ? c[r] : 0u; };
					auto        src = [&](uint32_t r) {
                        char b[24];
                        if (!ok[r]) return std::string("-");
                        std::snprintf(b, sizeof(b), "%s%u", t.s.ctx_kind[r] == 2 ? "L" : t.s.ctx_kind[r] == 1 ? "S" : "?", static_cast<unsigned>(t.s.ctx_piece[r]));
                        return std::string(b);
					};
					const uint32_t tm = val(0x08e);
					for (uint32_t m = 0; m < 8; m++) {
						const uint32_t b = 0x318 + m * 0xf;
						if (!ok[b] && ((tm >> (4 * m)) & 0xfu) == 0) continue;
						const uint64_t base = (static_cast<uint64_t>(val(b)) << 8) | (static_cast<uint64_t>(val(0x390 + m) & 0xffu) << 40);
						const uint64_t dccb = (static_cast<uint64_t>(val(b + 13)) << 8) | (static_cast<uint64_t>(val(0x3a8 + m) & 0xffu) << 40);
						const uint32_t a2 = val(0x3b0 + m), tw = ((a2 >> 14) & 0x3fffu) + 1, th = (a2 & 0x3fffu) + 1;
						const char*    rd = base == 0 ? "zero" : !cov(base, 4096) ? "unmapped" : !cov(base, static_cast<uint64_t>(tw) * th * 4) ? "partial" : "ok";
						char row[512];
						std::snprintf(row, sizeof(row), "%u\t%zu\t%u\t%u\t%x\t0x%" PRIx64 "\t%s\t0x%08x\t%s\t0x%08x\t0x%08x\t0x%08x\t0x%08x\t%s\t0x%" PRIx64 "\t%s\t%s", sub, k, draw_no, m, (tm >> (4 * m)) & 0xfu, base, src(b).c_str(),
						              val(b + 4), src(b + 4).c_str(), val(b + 5), a2, val(0x3b8 + m), val(b + 6), src(b + 6).c_str(), dccb, src(b + 13).c_str(), rd);
						g_cblog.emplace_back(row);
					}
					{ // the depth target (DB_Z_INFO 0x010, DB_Z_WRITE_BASE 0x014 / _HI 0x01c, DB_DEPTH_SIZE_XY 0x007)
						const uint64_t zb = (static_cast<uint64_t>(val(0x014)) << 8) | (static_cast<uint64_t>(val(0x01c) & 0xffu) << 40);
						const char*    rd = zb == 0 ? "zero" : !cov(zb, 4096) ? "unmapped" : "ok";
						char row[512];
						std::snprintf(row, sizeof(row), "%u\t%zu\t%u\t8\t-\t0x%" PRIx64 "\t%s\t0x%08x\t%s\t-\t0x%08x\t-\t-\t-\t-\t-\t%s", sub, k, draw_no, zb, src(0x014).c_str(), val(0x010), src(0x010).c_str(), val(0x007), rd);
						g_cblog.emplace_back(row);
					}
				}
				draw_no++;
				if (!cfg().dcc_only) return;
				const auto&    c  = t.s.ctx;
				const auto&    ok = t.s.ctx_ok;
				const uint32_t tm = ok[0x08e] ? c[0x08e] : 0xffffffffu;
				for (uint32_t m = 0; m < 8; m++) {
					const uint32_t b = 0x318 + m * 0xf;
					if (((tm >> (4 * m)) & 0xfu) == 0 || !ok[b] || !ok[b + 4] || ((c[b + 4] >> 28) & 1u) == 0) continue;
					const uint64_t base = (static_cast<uint64_t>(c[b]) << 8) | (static_cast<uint64_t>(ok[0x390 + m] ? c[0x390 + m] & 0xffu : 0u) << 40);
					w.snap[base] = std::make_shared<sc::RegState>(t.s);
				}
			});
		std::sort(w.outs.begin(), w.outs.end());
	}
	// 2. passes: runs of pieces with the same output set (pieces with none do not break a run); each pass's copies go at
	// the end of its last piece, so a G-buffer pass drawn over ~100 chained pieces is copied once, as the top session
	// defined a pass (one target set, or one dispatch's outputs)
	for (size_t i = 0; i < pw.size();) {
		if (pw[i].outs.empty()) {
			i++;
			continue;
		}
		size_t last = i, j = i + 1;
		for (; j < pw.size(); j++) {
			if (pw[j].outs.empty()) continue;
			if (pw[j].outs != pw[i].outs) break;
			last = j;
		}
		const size_t                 k    = last;
		const auto&                  pc   = cr.pieces[k];
		const uint32_t               op0  = pw[i].op0, op1 = pw[last].op1;
		const std::vector<uint32_t>& outs = pw[i].outs;
		std::unordered_map<uint64_t, std::shared_ptr<sc::RegState>> gsnap; // v3: the pass's last context per DCC target
		for (size_t j = i; j <= last; j++)
			for (const auto& [b, st]: pw[j].snap) gsnap[b] = st;
		i = last + 1;
		if (phase == 1) { // the survey: each incarnation's size, each surface's first-sight hash
			for (const uint32_t x: outs) {
				Surf& v = g_s[x];
				if (cfg().dcc_only && !(v.cb && v.dcc && v.dcc_base != 0 && v.g.tiled)) continue;
				if (!v.surveyed) v.surveyed = true, v.h0 = hash(v);
				sc::PlanItem pi;
				pi.bytes = keys_len(v);
				for (const auto& q: mapped(v, cov)) pi.bytes += q.len;
				if (cfg().dcc_only) pi.bytes = v.g.bytes + keys_whole(v) + (4ull << 20); // whole, plus the two alignments
				pi.target  = v.cb || v.depth;
				pi.depth   = v.depth;
				pi.depth_k = v.depth ? v.depth_k++ : 0u;
				g_items.push_back(pi);
				g_item_surf.push_back(x); // `changed` is resolved at the survey's end, from this surface's two hashes
			}
			continue;
		}
		std::vector<uint32_t> blk, incs;
		for (const uint32_t x: outs) {
			Surf&      v      = g_s[x];
			const bool target = v.cb || v.depth;
			if (g_plan.level >= 1 && !target && v.surveyed && v.h0 == v.h1) {
				g_skip_hash++;
				continue;
			}
			if (v.depth && (v.depth_k++ & 1u) != 0 && g_plan.level >= 2) {
				g_skip_depth++;
				continue;
			}
			if (cfg().dcc_only) { // v3
				if (!(v.cb && v.dcc && v.dcc_base != 0 && v.g.tiled)) {
					g_skip_nondcc++;
					continue;
				}
				const uint64_t kl = keys_whole(v);
				const auto     it = gsnap.find(v.base);
				if (!cov(v.base, v.g.bytes) || !cov(v.dcc_base, kl)) {
					g_skip_unmapped++;
					continue;
				}
				if (it == gsnap.end()) {
					g_skip_nosnap++;
					continue;
				}
				constexpr uint64_t kAl   = 2ull << 20;
				auto               align = [](uint64_t off, uint64_t src) {
                    const uint64_t have = (g_va + kHeader + off) & (kAl - 1), want = src & (kAl - 1);
                    return off + ((want - have) & (kAl - 1));
				};
				const uint64_t so = align(g_off, v.base), ko = align(so + v.g.bytes, v.dcc_base), end = ko + kl;
				const uint64_t run = g_run;
				g_run += end - g_off;
				if (g_plan.level == 3 && (g_m.frame_b() ? run < g_plan.split_at : run >= g_plan.split_at)) {
					g_skip_split++;
					continue;
				}
				if (end > g_size) {
					g_skip_room++, g_skip_bytes += end - g_off;
					continue;
				}
				Inc in;
				in.dcc = true, in.src = v.base, in.dcc_src = v.dcc_base, in.w = v.w, in.h = v.h, in.snap = it->second;
				in.surf = x, in.submit = sub, in.piece = static_cast<uint32_t>(k), in.op0 = op0, in.op1 = op1, in.ring = ring;
				in.off = so, in.bytes = v.g.bytes, in.keys_off = ko, in.keys_len = kl;
				in.rr.push_back({0, v.g.bytes, false});
				sc::dma(blk, v.base, g_va + kHeader + so, v.g.bytes);
				sc::dma(blk, v.dcc_base, g_va + kHeader + ko, kl);
				g_off = end;
				incs.push_back(static_cast<uint32_t>(g_inc.size()));
				g_inc.push_back(std::move(in));
				continue;
			}
			Inc in;
			in.rr = mapped(v, cov);
			if (in.rr.size() != v.rr.size()) g_skip_unmapped++;
			for (const auto& q: in.rr) in.bytes += q.len;
			in.keys_len = keys_len(v);
			if (in.keys_len != 0 && !cov(v.dcc_base, in.keys_len)) in.keys_len = 0;
			const uint64_t b = in.bytes + in.keys_len;
			if (b == 0) continue;
			const uint64_t run = g_run;
			g_run += b;
			if (g_plan.level == 3 && (g_m.frame_b() ? run < g_plan.split_at : run >= g_plan.split_at)) {
				g_skip_split++;
				continue;
			}
			if (!gfx && !cfg().mec) {
				g_skip_mec++;
				continue;
			}
			if (g_off + b > g_size) {
				g_skip_room++, g_skip_bytes += b;
				continue;
			}
			in.surf = x, in.submit = sub, in.piece = static_cast<uint32_t>(k), in.op0 = op0, in.op1 = op1, in.ring = ring, in.off = g_off;
			uint64_t at = g_va + kHeader + g_off;
			for (const auto& q: in.rr) sc::dma(blk, v.base + q.off, at, q.len), at += q.len;
			if (in.keys_len != 0) in.keys_off = g_off + in.bytes, sc::dma(blk, v.dcc_base, at, in.keys_len);
			g_off += b;
			incs.push_back(static_cast<uint32_t>(g_inc.size()));
			g_inc.push_back(std::move(in));
		}
		if (incs.empty()) continue;
		std::vector<uint32_t> full;
		if (gfx) sc::flush_gfx(full, g_va + 64ull * static_cast<uint64_t>(ring + 1), ++g_fence);
		else sc::flush_mec(full);
		full.insert(full.end(), blk.begin(), blk.end());
		g_q.push_back({ring, pc.src, std::move(full), std::move(incs)});
	}
}
static uint64_t meminfo(const char* field) {
	uint64_t v = 0;
	if (FILE* f = std::fopen("/proc/meminfo", "r"); f != nullptr) {
		char line[256];
		while (std::fgets(line, sizeof(line), f) != nullptr)
			if (std::strncmp(line, field, std::strlen(field)) == 0) v = std::strtoull(line + std::strlen(field), nullptr, 10) << 10;
		std::fclose(f);
	}
	return v;
}
static uint64_t sysfs(const std::string& p) {
	uint64_t v = 0;
	if (FILE* f = std::fopen(p.c_str(), "r"); f != nullptr) {
		char b[64] {};
		if (std::fgets(b, sizeof(b), f) != nullptr) v = std::strtoull(b, nullptr, 10);
		std::fclose(f);
	}
	return v;
}
static void begin_survey() {
	std::lock_guard lk(g_mu);
	g_rec.reset(), g_db.clear(), g_ct.clear(), g_ops.clear(), g_items.clear(), g_item_surf.clear(), g_inc.clear(), g_q.clear();
	g_s.clear(), g_si.clear();
	g_submits = 0;
	g_captures++;
	char       ts[32];
	const auto now = std::time(nullptr);
	std::strftime(ts, sizeof(ts), "%Y%m%d-%H%M%S", std::localtime(&now));
	g_base = std::string(dir()) + "/sr439c-" + ts + "-a" + std::to_string(g_captures);
	std::fprintf(stderr, "[bc5] exp 0439 (tag sr439c): arm %u: the survey frame (%s)\n", g_captures, g_base.c_str());
}
// After the survey's drain: the hashes again, the plan, the arena. False: no copy frame.
static bool survey_end() {
	uint64_t bytes = 0;
	{
		std::lock_guard lk(g_mu);
		for (auto& v: g_s)
			if (v.surveyed) v.h1 = hash(v);
		for (size_t i = 0; i < g_items.size(); i++) {
			const Surf& v       = g_s[g_item_surf[i]];
			g_items[i].changed = g_items[i].target || v.h0 != v.h1;
		}
		g_mem_avail = meminfo("MemAvailable:");
		g_gtt_total = g_gtt_used = 0;
		for (int c = 0; c < 4 && g_gtt_total == 0; c++) {
			const std::string d = "/sys/class/drm/card" + std::to_string(c) + "/device/";
			g_gtt_total = sysfs(d + "mem_info_gtt_total"), g_gtt_used = sysfs(d + "mem_info_gtt_used");
		}
		g_plan = sc::plan(g_items, sc::budget(cfg().cap, g_mem_avail, g_gtt_total, g_gtt_used));
		g_m.split = g_plan.level == 3;
		char note[512];
		std::snprintf(note, sizeof(note), "survey: %zu incarnations in %u submits, %zu surfaces; need %.1f / %.1f / %.1f / %.1f MB (all / hash skip / + depth half / + two frames), budget %.1f MB (MemAvailable %.1f MB, GTT %.1f of %.1f MB), level %d, arena %.1f MB%s",
		              g_items.size(), g_submits, g_s.size(), mb(g_plan.need[0]), mb(g_plan.need[1]), mb(g_plan.need[2]), mb(g_plan.need[3]), mb(g_plan.budget), mb(g_mem_avail), mb(g_gtt_used),
		              mb(g_gtt_total), g_plan.level, mb(g_plan.arena), g_plan.truncated ? ", TRUNCATED (copies past the arena are skipped and counted)" : "");
		g_survey_note = note;
		bytes         = g_plan.arena;
	}
	std::fprintf(stderr, "[bc5] exp 0439 (tag sr439c): %s\n", g_survey_note.c_str());
	void*    cpu = nullptr;
	uint64_t va  = 0;
	const int rc = bytes != 0 ? bc5_sr439c_arena(bytes + kHeader, &cpu, &va) : -22;
	std::lock_guard lk(g_mu);
	if (rc != 0 || cpu == nullptr) {
		std::fprintf(stderr, "[bc5] exp 0439 (tag sr439c): NO copy frame: the arena of %.1f MB was not allocated (rc %d)\n", mb((bytes + kHeader)), rc);
		g_m.state = 0, g_m.split = false;
		return false;
	}
	g_cpu = static_cast<uint8_t*>(cpu), g_va = va, g_size = bytes;
	std::memset(g_cpu, 0, kHeader);
	return true;
}
static void begin_copy() {
	std::lock_guard lk(g_mu);
	g_rec.reset(), g_db.clear(), g_ct.clear(), g_ops.clear(), g_inc.clear(), g_q.clear();
	g_skip_nondcc = g_skip_nosnap = 0;
	g_cblog.clear();
	g_subrows.clear();
	for (auto& v: g_s) v.depth_k = 0;
	g_off = g_run = 0, g_submits = 0;
	g_skip_hash = g_skip_depth = g_skip_split = g_skip_room = g_skip_mec = g_skip_unmapped = g_skip_bytes = 0;
	g_cdir = g_base + (g_m.frame_b() ? "-B" : "-A");
}
// After a copy frame's drain: the census of every copied tile, the tables, the window tiles raw.
static void copy_end() {
	std::lock_guard lk(g_mu);
	constexpr uint64_t kMinFree = 20ull << 30, kRawCap = 3ull << 30;
	mkdir(g_cdir.c_str(), 0700);
	const uint64_t fr     = srb439::free_bytes(dir());
	const bool     rawok  = fr > kMinFree + kRawCap;
	FILE*          tb     = rawok ? std::fopen((g_cdir + "/tiles.bin").c_str(), "wb") : nullptr;
	FILE*          tt     = std::fopen((g_cdir + "/tiles.tsv").c_str(), "w");
	FILE*          it     = std::fopen((g_cdir + "/inc.tsv").c_str(), "w");
	uint64_t       placed = 0, raw = 0, unplaced = g_q.size();
	if (tt != nullptr) std::fprintf(tt, "inc\toff\tlen\twindow\telems\tzero\tdark\tnan\tinf\thash\tfile_off\n");
	if (it != nullptr) std::fprintf(it, "inc\tsurf\tsubmit\tring\tpiece\top0\top1\twhere\tplaced\tbytes\tkeys\tkeys_ff\tkeys_00\tkeys_other\tkeys_top\telems\tzero\tdark\tnan\tinf\tw_elems\tw_zero\tw_dark\tw_nan\tw_inf\n");
	for (size_t i = 0; i < g_inc.size(); i++) {
		const Inc&  in = g_inc[i];
		const Surf& v  = g_s[in.surf];
		bc5::sr439b::Census all, win;
		bc5::sr439b::KeyHist kh;
		if (in.placed) {
			placed++;
			uint64_t at = kHeader + in.off;
			for (const auto& q: in.rr) {
				for (uint64_t t = 0; t < q.len; t += sc::kTile) {
					const uint64_t n = std::min(sc::kTile, q.len - t);
					const uint8_t* p = g_cpu + at + t;
					const auto     c = bc5::sr439b::count(p, n, v.kind);
					all.add(c);
					if (q.window) win.add(c);
					long long fo = -1;
					if (q.window && tb != nullptr && raw + n <= kRawCap) fo = static_cast<long long>(raw), raw += std::fwrite(p, 1, n, tb);
					if (tt != nullptr)
						std::fprintf(tt, "%zu\t%" PRIu64 "\t%" PRIu64 "\t%d\t%" PRIu64 "\t%" PRIu64 "\t%" PRIu64 "\t%" PRIu64 "\t%" PRIu64 "\t%016" PRIx64 "\t%lld\n", i, q.off + t, n, q.window ? 1 : 0, c.elems, c.zero, c.dark, c.nan, c.inf,
						             sc::fnv(p, n), fo);
				}
				at += q.len;
			}
			if (in.keys_len != 0) kh.add(g_cpu + kHeader + in.keys_off, in.keys_len), kh.finish();
		}
		uint32_t tv = 0;
		uint64_t tc = 0;
		kh.top(tv, tc);
		if (it != nullptr)
			std::fprintf(it, "%zu\t%u\t%u\t%d\t%u\t%u\t%u\t%d\t%d\t%" PRIu64 "\t%" PRIu64 "\t%" PRIu64 "\t%" PRIu64 "\t%" PRIu64 "\t0x%02x\t%" PRIu64 "\t%" PRIu64 "\t%" PRIu64 "\t%" PRIu64 "\t%" PRIu64 "\t%" PRIu64 "\t%" PRIu64 "\t%" PRIu64 "\t%" PRIu64 "\t%" PRIu64 "\n",
			             i, in.surf, in.submit, in.ring, in.piece, in.op0, in.op1, in.where, in.placed ? 1 : 0, in.bytes, in.keys_len, kh.ff, kh.z, kh.other, tv, all.elems, all.zero, all.dark, all.nan, all.inf, win.elems, win.zero,
			             win.dark, win.nan, win.inf);
	}
	if (tb != nullptr) std::fclose(tb);
	if (tt != nullptr) std::fclose(tt);
	if (cfg().cblog) { // cblog: the colour targets of this frame that the late draws sample, as their V#s say
		std::vector<uint64_t> cbb;
		for (const auto& x: g_rec.surf)
			if (x.cb) cbb.push_back(x.base);
		std::sort(cbb.begin(), cbb.end());
		if (FILE* f = std::fopen((g_cdir + "/cbreads.tsv").c_str(), "w"); f != nullptr) {
			std::fprintf(f, "submit\tpiece\tseq\tkind\tbase\tfmt\tw\th\tsw\tcompressed\tword6\tword7\n");
			for (size_t i = 0; i < g_rec.ops.size() && i < g_ops.size(); i++) {
				const auto& o = g_ops[i];
				if (o.piece < cfg().cb_lo || o.piece > cfg().cb_hi || o.ring != bc5::direct::kGfxRing) continue;
				for (const auto& r: g_rec.ops[i].refs) {
					const auto& x = g_rec.surf[r.surf];
					if (r.cb || !x.image || !std::binary_search(cbb.begin(), cbb.end(), x.base)) continue;
					std::fprintf(f, "%u\t%u\t%u\t%c\t0x%" PRIx64 "\t%u\t%u\t%u\t%u\t%d\t0x%08x\t0x%08x\n", o.submit, o.piece, o.seq, o.kind, x.base, x.fmt, x.w, x.h, x.sw_mode, x.dcc ? 1 : 0, x.word6, x.word7);
				}
			}
			std::fclose(f);
		}
	}
	if (!g_subrows.empty())
		if (FILE* f = std::fopen((g_cdir + "/submits.tsv").c_str(), "w"); f != nullptr) {
			std::fprintf(f, "submit\tring\tms\tjobs_in_flight\n");
			for (const auto& r: g_subrows) std::fprintf(f, "%s\n", r.c_str());
			std::fclose(f);
		}
	if (!g_cblog.empty())
		if (FILE* f = std::fopen((g_cdir + "/cblog.tsv").c_str(), "w"); f != nullptr) { // cblog
			std::fprintf(f, "submit\tpiece\tdraw\tmrt\tmask\tbase\tbase_src\tinfo\tinfo_src\tattrib\tattrib2\tattrib3\tdcc_control\tdcc_control_src\tdcc_base\tdcc_base_src\treadable\n");
			for (const auto& r: g_cblog) std::fprintf(f, "%s\n", r.c_str());
			std::fclose(f);
		}
	if (FILE* f = std::fopen((g_cdir + "/dcc.tsv").c_str(), "w"); f != nullptr) { // v3: the whole DCC copies
		std::fprintf(f, "inc\tsurf\tsrc\tdcc_src\tw\th\tbytes\tkeys\tdecompressed\tfile\tkeys_file\n");
		uint64_t written = 0;
		for (size_t i = 0; i < g_inc.size(); i++) {
			const Inc& in = g_inc[i];
			if (!in.dcc || !in.placed) continue;
			char sf[64], kf[64];
			std::snprintf(sf, sizeof(sf), "d%04zu.raw", i);
			std::snprintf(kf, sizeof(kf), "d%04zu.keys", i);
			const bool room = rawok && cfg().cb_nodump == 0 && written + in.bytes + in.keys_len <= (8ull << 30);
			if (room) {
				if (FILE* g = std::fopen((g_cdir + "/" + sf).c_str(), "wb"); g != nullptr) written += std::fwrite(g_cpu + kHeader + in.off, 1, in.bytes, g), std::fclose(g);
				if (FILE* g = std::fopen((g_cdir + "/" + kf).c_str(), "wb"); g != nullptr) written += std::fwrite(g_cpu + kHeader + in.keys_off, 1, in.keys_len, g), std::fclose(g);
			}
			std::fprintf(f, "%zu\t%u\t0x%" PRIx64 "\t0x%" PRIx64 "\t%u\t%u\t%" PRIu64 "\t%" PRIu64 "\t%d\t%s\t%s\n", i, in.surf, in.src, in.dcc_src, in.w, in.h, in.bytes, in.keys_len, in.decompressed ? 1 : 0,
			             room ? sf : "-", room ? kf : "-");
		}
		std::fclose(f);
	}
	if (it != nullptr) std::fclose(it);
	if (FILE* f = std::fopen((g_cdir + "/surf.tsv").c_str(), "w"); f != nullptr) {
		std::fprintf(f, "id\tbase\tbytes\tpadded\tkind\tfmt\tw\th\td\tbpe\tsw\trole\tdcc\tdcc_base\ttiled\ttx\tty\tbw\tbh\th0\th1\n");
		for (size_t i = 0; i < g_s.size(); i++) {
			const Surf& v = g_s[i];
			std::fprintf(f, "%zu\t0x%" PRIx64 "\t%" PRIu64 "\t%" PRIu64 "\t%s\t%u\t%u\t%u\t%u\t%u\t%u\t%s\t%d\t0x%" PRIx64 "\t%d\t%u\t%u\t%u\t%u\t%016" PRIx64 "\t%016" PRIx64 "\n", i, v.base, v.bytes, v.g.bytes, bc5::sr439b::kind_name(v.kind), v.fmt,
			             v.w, v.h, v.d, v.bpe, v.sw, v.depth ? "depth" : v.cb ? "cb" : v.buffer ? "buffer" : "image", v.dcc ? 1 : 0, v.dcc_base, v.g.tiled ? 1 : 0, v.g.tx, v.g.ty, v.g.bw, v.g.bh, v.h0, v.h1);
		}
		std::fclose(f);
	}
	if (FILE* f = std::fopen((g_cdir + "/ops.tsv").c_str(), "w"); f != nullptr) {
		std::fprintf(f, "seq\tsubmit\tring\tpiece\tkind\tpgm\trefs\n");
		for (const auto& o: g_ops) std::fprintf(f, "%u\t%u\t%d\t%u\t%c\t0x%" PRIx64 "\t%s\n", o.seq, o.submit, o.ring, o.piece, o.kind, o.pgm, o.refs.c_str());
		std::fclose(f);
	}
	if (FILE* f = std::fopen((g_cdir + "/meta.txt").c_str(), "w"); f != nullptr) {
		const auto now = std::time(nullptr);
		std::fprintf(f, "frame %s ending %s", g_m.frame_b() ? "A" : (g_m.split ? "B" : "A"), std::ctime(&now));
		std::fprintf(f, "%s\nwindow %.3f %.3f %.3f %.3f stride %u mec %d\n", g_survey_note.c_str(), cfg().win.x0, cfg().win.x1, cfg().win.y0, cfg().win.y1, cfg().stride, cfg().mec ? 1 : 0);
		std::fprintf(f, "split_at %" PRIu64 " arena %" PRIu64 " used %" PRIu64 "\nincarnations %zu placed %" PRIu64 " queued-but-unplaced %" PRIu64 "\n", g_plan.split_at, g_size, g_off, g_inc.size(), placed, unplaced);
		std::fprintf(f, "skipped: not DCC %" PRIu64 ", DCC without its draw's context %" PRIu64 ", unchanged %" PRIu64 ", depth half rate %" PRIu64 ", other frame %" PRIu64 ", no room %" PRIu64 " (%" PRIu64 " bytes), compute ring %" PRIu64 ", incarnations with unmapped ranges %" PRIu64 "\nraw window tiles %" PRIu64 " bytes%s\n",
		             g_skip_nondcc, g_skip_nosnap, g_skip_hash, g_skip_depth, g_skip_split, g_skip_room, g_skip_bytes, g_skip_mec, g_skip_unmapped, raw, rawok ? "" : " (none: under 23 GB free)");
		std::fclose(f);
	}
	std::fprintf(stderr, "[bc5] exp 0439 (tag sr439c): %s: %zu incarnations, %" PRIu64 " placed, %" PRIu64 " unplaced, %.1f of %.1f MB used; skipped %" PRIu64 " unchanged, %" PRIu64 " depth, %" PRIu64 " other frame, %" PRIu64 " no room\n", g_cdir.c_str(),
	             g_inc.size(), placed, unplaced, mb(g_off), mb(g_size), g_skip_hash, g_skip_depth, g_skip_split, g_skip_room);
	g_q.clear();
}
static void finish() {
	{
		std::lock_guard lk(g_mu);
		g_cpu = nullptr, g_va = 0, g_size = 0;
	}
	bc5_sr439c_arena(0, nullptr, nullptr);
}
} // namespace scu439
#include <functional>
#endif
'''
rep('''} // namespace srb439
#endif
''', NS)

rep('''static void submit_now(const uint32_t* ib, uint32_t num_dwords, const char* kind, int ring, const Chain* chain) {
	if (g_stage == Stage::Off || !g_dev || ib == nullptr || num_dwords == 0) {
		return;
	}
''', '''#ifndef BC5_LEAN
static void rsv439_submit(const uint32_t* ib, uint32_t num_dwords, int ring, const std::function<bool(uint64_t, uint64_t)>& cov); // exp 0439 (tag rsv439): defined after the dc439 namespace, in this one
// exp 0439 (tag dir439, mode c): does this stream's top level wait (memory WAIT_REG_MEM / WAIT_REG_MEM64, decoded as the
// piece filter decodes them) on a label it has not written itself and that a GFX job in flight has a pending write of?
static bool x439_waits_on_gfx(const uint32_t* ib, uint32_t num_dwords) {
	std::vector<uint64_t> written, waits;
	for (uint32_t i = 0; i < num_dwords;) {
		const uint32_t h    = ib[i];
		const uint32_t type = h >> 30u;
		uint32_t       len  = 1;
		if (type == 3 || type == 0) { const uint32_t c = (h >> 16u) & 0x3fffu; len = c == 0x3fffu ? 1 : c + 2; }
		if (i + len > num_dwords) break;
		const uint32_t  op = (h >> 8u) & 0xffu;
		const uint32_t* p  = ib + i;
		if (type == 3) {
			const uint32_t dst_sel = len >= 2 ? (p[1] >> 8u) & 0xfu : 0;
			if (op == 0x37 && len >= 4 && (dst_sel == 1 || dst_sel == 2 || dst_sel == 5)) written.push_back((p[2] & ~3u) | (static_cast<uint64_t>(p[3] & 0xffffu) << 32u));
			else if (op == 0x49 && len >= 6) written.push_back((p[3] & ~3u) | (static_cast<uint64_t>(p[4] & 0xffffu) << 32u));
			else if ((op == 0x47 || op == 0x1e) && len >= 4) written.push_back((p[2] & ~3u) | (static_cast<uint64_t>(p[3] & 0xffffu) << 32u));
			else if ((op == 0x3c || op == 0x93) && len >= 4 && ((p[1] >> 4u) & 1u) != 0) {
				const uint64_t label = (p[2] & ~3u) | (static_cast<uint64_t>(p[3] & 0xffffu) << 32u);
				if (std::find(written.begin(), written.end(), label) == written.end()) waits.push_back(label);
			}
		}
		i += len;
	}
	if (waits.empty()) return false;
	std::lock_guard lk(g_plw_mutex);
	for (const auto& w: g_plw)
		if (w.ring == bc5::direct::kGfxRing && std::find(waits.begin(), waits.end(), w.label) != waits.end()) return true;
	return false;
}
#endif
static void submit_now(const uint32_t* ib, uint32_t num_dwords, const char* kind, int ring, const Chain* chain) {
	if (g_stage == Stage::Off || !g_dev || ib == nullptr || num_dwords == 0) {
		return;
	}
#ifndef BC5_LEAN
	{ // exp 0439 (tag ser439 / dir439; the top session's orders of 11-23 ~17:50 and ~18:50; diagnostic arms, normal build only):
	  // BC5_0439_SERIAL selects what a title submit waits for before its kernel submit, bounded at 50 ms (past the bound
	  // it is submitted anyway and the bound is journaled):
	  //   1  every earlier job on every ring has completed (the completion queue is empty);
	  //   a  a compute submit (an acb, ring != GFX) waits until every earlier GFX job has completed;
	  //   b  a GFX submit waits until every earlier compute job has completed;
	  //   c  as a, only for an acb whose top-level stream holds a memory WAIT_REG_MEM (not on a label written earlier in
	  //      the same stream) on a label that a GFX job still in flight has a pending write of (g_plw).
	  // Rings and queues as they are; the census's own jobs (dc439, sr439c*) neither wait nor count.
		static const char mode = [] {
			const char* e = std::getenv("BC5_0439_SERIAL");
			const char  m = (e != nullptr && e[0] != 0 && e[1] == 0 && (e[0] == '1' || e[0] == 'a' || e[0] == 'b' || e[0] == 'c' || e[0] == 'd')) ? e[0] : 0;
			std::fprintf(stderr, "[bc5] exp 0439 (tag ser439): BC5_0439_SERIAL=%c (1: all earlier jobs; a: acb after GFX; b: GFX after acbs; c: acb after GFX when it waits on a GFX label; 50 ms bound)\\n", m != 0 ? m : '0');
			return m;
		}();
		if (mode != 0 && g_async && std::strncmp(kind, "dc439", 5) != 0 && std::strncmp(kind, "sr439c", 6) != 0) {
			const bool                   gfx  = ring == bc5::direct::kGfxRing;
			const std::atomic<uint32_t>* busy = nullptr;
			if (mode == '1') busy = &g_cq_items;
			else if (mode == 'a' && !gfx) busy = &g_x439_inf[1];
			else if (mode == 'b' && gfx) busy = &g_x439_inf[2];
			else if (mode == 'c' && !gfx && g_x439_inf[1].load() != 0 && x439_waits_on_gfx(ib, num_dwords)) busy = &g_x439_inf[1];
			static std::atomic<uint64_t> n {0}, held {0}, bounded {0}, waited_us {0};
			const uint64_t               c = ++n;
			if (busy != nullptr && busy->load() != 0) {
				held++;
				const uint64_t t0 = SoftCp::now_ns();
				while (busy->load() != 0 && SoftCp::now_ns() - t0 < 50'000'000ull) std::this_thread::sleep_for(std::chrono::microseconds(20));
				waited_us += (SoftCp::now_ns() - t0) / 1000;
				if (const uint32_t left = busy->load(); left != 0) {
					const uint64_t b = ++bounded;
					if (b <= 64 || b % 1000 == 0)
						std::fprintf(stderr, "[bc5] exp 0439 (tag ser439): mode %c: %s of %u dwords on ring %d submitted at the 50 ms bound with %u jobs still running (%" PRIu64 " such of %" PRIu64 " submits)\\n", mode, kind, num_dwords, ring, left, b, c);
				}
			}
			if ((c & 0x3ffu) == 0)
				std::fprintf(stderr, "[bc5] exp 0439 (tag ser439): mode %c: %" PRIu64 " submits, %" PRIu64 " held, %" PRIu64 " at the bound, mean wait %.2f ms per submit\\n", mode, c, held.load(), bounded.load(), static_cast<double>(waited_us.load()) / 1000.0 / static_cast<double>(c));
		}
	}
#endif
''')
rep('''	shader_dump(ib, num_dwords, *maps_p); // experiment 0049
''', '''#ifndef BC5_LEAN
	rsv439_submit(ib, num_dwords, ring, [&maps_p](uint64_t a, uint64_t b) { return covered_sorted(*maps_p, a, b); }); // exp 0439 (tag rsv439), before the census
	if (const int ph = scu439::g_phase.load(std::memory_order_relaxed); ph != 0) { // exp 0439 (tag sr439c): survey or copy frame
		const auto cov = [&maps_p](uint64_t a, uint64_t b) { return covered_sorted(*maps_p, a, b); };
		scu439::g_cq_now = g_cq_items.load(); // the jobs in flight at this submit (submits.tsv)
		scu439::submit(ib, num_dwords, ring, cov, ph);
	}
#endif
	shader_dump(ib, num_dwords, *maps_p); // experiment 0049
''')

rep('''#else
static void sr439b_flip() {}
''', r'''// exp 0439 (tag rsv439, BC5_0439_DCC_RESOLVE=1, the top session's order of 11-23 ~16:00; normal build only): at the end
// of every GFX pass that wrote a DCC colour target, every frame, the target is decompressed in place by dc439's own
// decompress draw (CB_DCC_DECOMPRESS, the draw BC5_DIRECT_DCC_PRESENT runs on the display surface at a flip), so that
// a later pass sampling it with COMPRESSION_EN finds every block decompressed with keys the hardware itself left (the dk
// arm's hand-written keys made that arm invalid). Inside the title's stream (the backend's block hook, before the
// pass's outgoing chain), as a bracket the device would otherwise emulate: CLEAR_STATE cmd 0, the decompress, then the
// title's context registers, the SH and UCONFIG registers the decompress wrote, and NUM_INSTANCES written back from a
// tracker of this ring's stream (sr0439c.hpp CtxTrack, resolve_block). A test of the cause, not a fix.
namespace rsv439 {
static bool on() {
	static const bool v = [] {
		const char* e = std::getenv("BC5_0439_DCC_RESOLVE");
		const bool  b = e != nullptr && e[0] == '1' && e[1] == 0;
		std::fprintf(stderr, "[bc5] exp 0439 (tag rsv439): BC5_0439_DCC_RESOLVE=%d (1: every pass's DCC colour targets decompressed in place at its end)\n", b ? 1 : 0);
		return b;
	}();
	return v;
}
static bc5::sr439c::CtxTrack g_t; // the GFX ring's stream (submits are serialised there)
static uint64_t              g_submits = 0, g_blocks = 0, g_targets = 0, g_bad = 0, g_dropped = 0;
} // namespace rsv439
static void rsv439_submit(const uint32_t* ib, uint32_t num_dwords, int ring, const std::function<bool(uint64_t, uint64_t)>& cov) {
	if (!rsv439::on() || ring != bc5::direct::kGfxRing) return; // the tracker walks every GFX submit from the start; blocks only once the programs are there
	const auto      cr = bc5::ib_chain::collect(ib, num_dwords, cov, true);
	std::lock_guard lk(scu439::g_mu);
	const uint64_t  gen = ++rsv439::g_submits;
	for (auto it = scu439::g_q.begin(); it != scu439::g_q.end();) { // resolve blocks the device never claimed (a rebuilt or split root)
		if (it->incs.empty() && it->gen + 64 < gen) {
			it = scu439::g_q.erase(it);
			rsv439::g_dropped++;
		} else {
			++it;
		}
	}
	struct PT {
		std::vector<uint64_t>                      bases;
		std::vector<bc5::dc439::Block>             blocks;
		std::vector<std::pair<uint32_t, uint32_t>> wh;
		bc5::sr439c::RegState                      st;
	};
	std::vector<PT> pt(cr.pieces.size());
	for (size_t k = 0; k < cr.pieces.size(); k++) {
		PT& w = pt[k];
		rsv439::g_t.walk(cr.pieces[k].src, cr.pieces[k].n, k == 0, cov, [&w](const bc5::sr439c::CtxTrack& t) {
			const auto&    c  = t.s.ctx;
			const auto&    ok = t.s.ctx_ok;
			const uint32_t tm = ok[0x08e] ? c[0x08e] : 0xffffffffu;
			for (uint32_t m = 0; m < 8; m++) {
				const uint32_t b = 0x318 + m * 0xf;
				if (((tm >> (4 * m)) & 0xfu) == 0 || !ok[b] || !ok[b + 4] || ((c[b + 4] >> 28) & 1u) == 0) continue;
				const uint64_t base = (static_cast<uint64_t>(c[b]) << 8) | (static_cast<uint64_t>(ok[0x390 + m] ? c[0x390 + m] & 0xffu : 0u) << 40);
				if (std::find(w.bases.begin(), w.bases.end(), base) != w.bases.end()) continue;
				const bc5::dc439::Block bl = bc5::dc439::find(c, ok, base);
				if (!bl.valid || !bl.dcc_enable()) continue;
				const uint32_t a2 = ok[0x3b0 + m] ? c[0x3b0 + m] : 0;
				w.bases.push_back(base);
				w.blocks.push_back(bl);
				w.wh.emplace_back(((a2 >> 14) & 0x3fffu) + 1, (a2 & 0x3fffu) + 1);
			}
		});
		w.st = rsv439::g_t.s;
	}
	// a pass: consecutive pieces writing the same set of DCC targets (pieces with none do not break it); the decompress
	// goes at the end of its last piece, with the register state there
	auto same = [](std::vector<uint64_t> a, std::vector<uint64_t> b) {
		std::sort(a.begin(), a.end());
		std::sort(b.begin(), b.end());
		return a == b;
	};
	for (size_t i = 0; dc439::g_code_ok && i < pt.size();) {
		if (pt[i].blocks.empty()) {
			i++;
			continue;
		}
		size_t last = i;
		for (size_t j = i + 1; j < pt.size(); j++) {
			if (pt[j].blocks.empty()) continue;
			if (!same(pt[j].bases, pt[i].bases)) break;
			last = j;
		}
		std::vector<uint32_t> blk;
		for (size_t t = 0; t < pt[i].blocks.size(); t++) {
			const auto dc = bc5::dc439::build(pt[i].blocks[t], pt[i].wh[t].first, pt[i].wh[t].second, dc439::g_vs_va, dc439::g_ps_va);
			if (bc5::sr439c::resolve_block(dc, pt[last].st, blk)) rsv439::g_targets++;
			else rsv439::g_bad++;
		}
		if (!blk.empty()) {
			scu439::Pend pe;
			pe.ring = ring, pe.src = cr.pieces[last].src, pe.blk = std::move(blk), pe.gen = gen;
			scu439::g_q.push_back(std::move(pe));
			rsv439::g_blocks++;
		}
		i = last + 1;
	}
	if ((gen & 0x3ffu) == 1)
		std::fprintf(stderr, "[bc5] exp 0439 (tag rsv439): %" PRIu64 " GFX submits: %" PRIu64 " resolve blocks, %" PRIu64 " targets decompressed, %" PRIu64 " not built, %" PRIu64 " unclaimed and dropped\n", gen, rsv439::g_blocks,
		             rsv439::g_targets, rsv439::g_bad, rsv439::g_dropped);
}
// exp 0439 (tag sr439c v3, the top session's order of 11-23 ~16:20): after a copy frame's drain, each whole DCC copy in
// the arena is decompressed in place by dc439's decompress draw (the draw DCC_PRESENT runs on the display surface), with
// the target's own CB registers from its pass (dc439::find on the context at its last draw) and only its two addresses
// moved to the copy and its keys copy (each placed at the guest address's bits below 2 MiB). The real target and the
// title's stream are not touched; the draws run as their own jobs and are drained before the census reads the arena.
static void sr439c_dcc_decompress() {
	if (!scu439::cfg().dcc_only) return;
	std::vector<std::vector<uint32_t>> ibs;
	std::vector<size_t>                which;
	uint64_t                           nofind = 0, nocode = 0;
	{
		std::lock_guard lk(scu439::g_mu);
		for (size_t i = 0; i < scu439::g_inc.size(); i++) {
			auto& in = scu439::g_inc[i];
			if (!in.dcc || !in.placed || !in.snap) continue;
			if (!dc439::g_code_ok) {
				nocode++;
				continue;
			}
			bc5::dc439::Block bl = bc5::dc439::find(in.snap->ctx, in.snap->ctx_ok, in.src);
			if (!bl.valid || !bl.dcc_enable()) {
				nofind++;
				continue;
			}
			const uint64_t nb = scu439::g_va + scu439::kHeader + in.off, nd = scu439::g_va + scu439::kHeader + in.keys_off;
			bl.c[0]     = static_cast<uint32_t>(nb >> 8);
			bl.base_ext = static_cast<uint32_t>((nb >> 40) & 0xffu);
			bl.c[13]    = static_cast<uint32_t>(nd >> 8);
			bl.dcc_ext  = static_cast<uint32_t>((nd >> 40) & 0xffu);
			ibs.push_back(bc5::dc439::build(bl, in.w, in.h, dc439::g_vs_va, dc439::g_ps_va));
			which.push_back(i);
		}
	}
	for (auto& ib: ibs) submit_now(ib.data(), static_cast<uint32_t>(ib.size()), "sr439c-dcc", bc5::direct::kGfxRing, nullptr);
	drain();
	std::lock_guard lk(scu439::g_mu);
	for (const size_t i: which) scu439::g_inc[i].decompressed = true;
	std::fprintf(stderr, "[bc5] exp 0439 (tag sr439c v3): %zu DCC copies decompressed in the arena (%" PRIu64 " without a matching block, %" PRIu64 " before the decompress programs were loaded)\n", which.size(), nofind, nocode);
}
static void sr439c_flip() { // exp 0439 (tag sr439c): the pass census's state machine, at every flip
	if (scu439::dir() == nullptr) return;
	{ // exp 0439 (tag sr439c v2): a label request the last flip did not serve (no decompressed display surface there)
		std::lock_guard lk(scu439::g_mu);
		if (!scu439::g_label_dir.empty()) {
			std::fprintf(stderr, "[bc5] exp 0439 (tag sr439c): NO picture for %s (no decompressed display surface at its flip)\n", scu439::g_label_dir.c_str());
			scu439::g_label_dir.clear();
		}
	}
	using bc5::sr439c::Act;
	const double t   = srb439::now_s();
	const int    pad = scu439::g_pad.exchange(-1);
	Act          a;
	{
		std::lock_guard lk(scu439::g_mu);
		static bool once = false;
		if (!once) once = true, scu439::cfg(), scu439::g_m.times = bc5::sr439c::parse_times(std::getenv("BC5_0439_PASS_AT"));
		if (pad >= 0) scu439::g_m.pad(pad != 0, t);
		a = scu439::g_m.flip(t);
	}
	if (a == Act::None) return;
	if (a == Act::Survey) {
		scu439::begin_survey();
		scu439::g_phase.store(1);
		return;
	}
	scu439::g_phase.store(0);
	drain(); // every ring's jobs of the frame are done
	if (a == Act::SurveyEnd) {
		if (scu439::survey_end()) scu439::begin_copy(), scu439::g_phase.store(2);
		return;
	}
	sr439c_dcc_decompress(); // v3: the whole DCC copies, decompressed in the arena before the census reads it
	scu439::copy_end();
	{
		std::lock_guard lk(scu439::g_mu);
		scu439::g_label_dir = scu439::g_cdir; // v2: this flip's decompressed display surface is the copied frame's picture
	}
	if (scu439::g_m.frame_b()) {
		scu439::begin_copy();
		scu439::g_phase.store(2);
	} else {
		scu439::finish();
	}
}
// exp 0439 (tag sr439c v2, the top session's order of 11-23 ~14:45): the label of a copied frame is its own picture.
// Called after dc439's in-place decompress of the display surface at the frame's flip (the decompress has been waited
// for), it saves the whole surface raw (tiled as the GPU left it, plain after the decompress) to <frame dir>/display.raw
// with display.txt (width, height, bytes, guest address); sr439cread.py --display turns it into a PNG.
static void sr439c_display(uint64_t data, uint32_t w, uint32_t h) {
	if (scu439::dir() == nullptr || data == 0 || w == 0 || h == 0) return;
	std::lock_guard lk(scu439::g_mu);
	if (scu439::g_label_dir.empty()) return;
	const std::string d = scu439::g_label_dir;
	scu439::g_label_dir.clear();
	const uint64_t bytes = bc5::sr439c::geo(w, h, 1, 4, 27, static_cast<uint64_t>(w) * h * 4).bytes;
	uint64_t       done  = 0;
	if (FILE* f = std::fopen((d + "/display.raw").c_str(), "wb"); f != nullptr) {
		std::vector<uint8_t> b(16u << 20);
		for (uint64_t off = 0; off < bytes; off += b.size()) {
			const size_t n = static_cast<size_t>(std::min<uint64_t>(b.size(), bytes - off));
			if (!srb439::copy(data + off, b.data(), n)) break;
			done += std::fwrite(b.data(), 1, n, f);
		}
		std::fclose(f);
	}
	if (FILE* f = std::fopen((d + "/display.txt").c_str(), "w"); f != nullptr) {
		std::fprintf(f, "width %u height %u bytes %" PRIu64 " written %" PRIu64 " address 0x%" PRIx64 "\n", w, h, bytes, done, data);
		std::fclose(f);
	}
	std::fprintf(stderr, "[bc5] exp 0439 (tag sr439c): the picture of %s: display surface %ux%u, %" PRIu64 " of %" PRIu64 " bytes\n", d.c_str(), w, h, done, bytes);
}
#else
static void sr439c_flip() {}
template <class F>
static void rsv439_submit(const uint32_t*, uint32_t, int, F&&) {}
static void sr439c_display(uint64_t, uint32_t, uint32_t) {}
static void sr439b_flip() {}
''')
rep('''	sr439b_flip(); // exp 0439 (tag sr439b)
''', '''	sr439b_flip(); // exp 0439 (tag sr439b)
	sr439c_flip(); // exp 0439 (tag sr439c)
''')
rep('''	if (ok) sr439b_dark(s.data, s.w, s.h); // exp 0439 (tag sr439b): the decompressed display surface
''', '''	if (ok) sr439b_dark(s.data, s.w, s.h); // exp 0439 (tag sr439b): the decompressed display surface
	if (ok) sr439c_display(s.data, s.w, s.h); // exp 0439 (tag sr439c v2): a copied frame's own picture
''')
rep('''	if (srb439::dir() != nullptr) srb439::g_pad.store(both != 0 ? 1 : 0);
''', '''	if (scu439::dir() != nullptr) scu439::g_pad.store(both != 0 ? 1 : 0); // exp 0439 (tag sr439c): with PASS_DUMP the pad arms the pass census only
	else if (srb439::dir() != nullptr) srb439::g_pad.store(both != 0 ? 1 : 0);
''')
s = s.rstrip('\n') + r'''

// exp 0439 (tag sr439c): the block of copies queued for this buffer (the backend's weak hook; mksr439cbe.py). out null:
// its size; else written and taken off the queue (its incarnations marked placed, with where).
#if defined(KYTY_BC5_DIRECT) && !defined(BC5_LEAN)
extern "C" uint32_t bc5_sr439c_block(const uint32_t* src, int ring, int where, uint32_t* out, uint32_t cap) {
	static const bool rsv = [] { // exp 0439 (tag rsv439): the switch read here too (its namespace is not in scope at the file's end)
		const char* e = std::getenv("BC5_0439_DCC_RESOLVE");
		return e != nullptr && e[0] == '1' && e[1] == 0;
	}();
	if (scu439::g_phase.load(std::memory_order_relaxed) != 2 && !rsv) return 0;
	std::lock_guard lk(scu439::g_mu);
	uint32_t n = 0;
	for (const auto& e: scu439::g_q)
		if (e.ring == ring && e.src == src) n += static_cast<uint32_t>(e.blk.size());
	if (n == 0 || out == nullptr) return n;
	if (cap < n) return 0;
	uint32_t at = 0;
	for (int pass = 0; pass < 2; pass++) // exp 0439 (tag rsv439): the resolve blocks (no incarnations) first, then the copies
		for (auto it = scu439::g_q.begin(); it != scu439::g_q.end();) {
			if (it->ring != ring || it->src != src || it->incs.empty() != (pass == 0)) {
				++it;
				continue;
			}
			std::memcpy(out + at, it->blk.data(), it->blk.size() * 4);
			at += static_cast<uint32_t>(it->blk.size());
			for (const uint32_t i: it->incs) scu439::g_inc[i].placed = true, scu439::g_inc[i].where = where;
			it = scu439::g_q.erase(it);
		}
	return at;
}
#endif
'''
assert s.count('tag sr439c') >= 7, s.count('tag sr439c')
if crlf:
    s = s.replace('\n', '\r\n')
# 3. per-class in-flight counters: the job's class, counted at cq_push, released at the fence
rep(r'''static std::atomic<uint32_t> g_cq_fences {0}, g_cq_items {0};
''', r'''static std::atomic<uint32_t> g_cq_fences {0}, g_cq_items {0};
#ifndef BC5_LEAN
static std::atomic<uint32_t> g_x439_inf[3] = {}; // exp 0439 (tag dir439): fence jobs in flight by class: 0 other (census), 1 GFX, 2 compute
#endif
''')
rep(r'''	FlPlan                   fl_plan;     // experiment 0404: the fast-launch draws' crumbs, for fl_probe
''', r'''	FlPlan                   fl_plan;     // experiment 0404: the fast-launch draws' crumbs, for fl_probe
#ifndef BC5_LEAN
	uint8_t                  x439 = 0;    // exp 0439 (tag dir439): 0 other, 1 GFX, 2 compute
#endif
''')
rep(r'''		if (it.fence) g_cq_fences++;
''', r'''		if (it.fence) g_cq_fences++;
#ifndef BC5_LEAN
		if (it.fence) g_x439_inf[it.job.x439 < 3 ? it.job.x439 : 0]++; // exp 0439 (tag dir439)
#endif
''')
rep(r'''			g_cq_fences--;
''', r'''#ifndef BC5_LEAN
			g_x439_inf[j.x439 < 3 ? j.x439 : 0]--; // exp 0439 (tag dir439)
#endif
			g_cq_fences--;
''')
rep(r'''		it.job.dev_gen    = g_dev_gen.load();
''', r'''		it.job.dev_gen    = g_dev_gen.load();
#ifndef BC5_LEAN
		it.job.x439 = (std::strncmp(kind, "dc439", 5) == 0 || std::strncmp(kind, "sr439c", 6) == 0) ? 0 : (ring == bc5::direct::kGfxRing ? 1 : 2); // exp 0439 (tag dir439)
#endif
''')

# exp 0439 (tag rr439, the top session's order of 11-23 ~19:45): the per-job record, arm d and the ring rule, appended
# by edit_rr.py. Normal build only. BC5_0439_RR_RECORD=1: the job table (each job's ring, guest queue, its unmet
# top-level waits at submit; done at its fence), written to the journal at a fence timeout. BC5_0439_RING_FREE=1 (implies
# the record): an acb is not submitted onto a libdrm compute ring while a job of ANOTHER guest queue on that ring has an
# unmet wait (head-of-line blocking behind a waiter; on the console each queue runs on its own), bounded at 50 ms.
# BC5_0439_SERIAL=d: an acb is held until each of its own top-level waits (on labels it has not written itself) is met
# in memory, bounded at 50 ms. The probe also writes its piece lines to <dump>.pieces.txt (the journal's tail can be cut).
rep(r'''#ifndef BC5_LEAN
static std::atomic<uint32_t> g_x439_inf[3] = {}; // exp 0439 (tag dir439): fence jobs in flight by class: 0 other (census), 1 GFX, 2 compute
#endif
''', r'''#ifndef BC5_LEAN
static std::atomic<uint32_t> g_x439_inf[3] = {}; // exp 0439 (tag dir439): fence jobs in flight by class: 0 other (census), 1 GFX, 2 compute
// exp 0439 (tag rr439): the job table (see mksr439c.py's tail). A job's waits are copies of its unmet top-level memory
// waits at submit (labels it has not written earlier itself), at most 8; wait_satisfied reads the label as it is now.
struct Rr439Job {
	uint64_t id = 0, n = 0, t_sub = 0, t_done = 0;
	char     kind[12] = {};
	int      ring = 0, queue = -1;
	uint32_t dwords = 0, nwaits = 0, nopen = 0;
	bool     done = true;
	uint32_t w[8][9] = {};
};
static std::mutex       g_rr_mu;
static Rr439Job         g_rr_jobs[512];
static uint64_t         g_rr_next = 1; // under g_rr_mu; 0 is "no record"
static std::atomic<uint64_t> g_rr_holds {0}, g_rr_bounds {0}, g_rr_hold_us {0}, g_rr_d_holds {0}, g_rr_d_bounds {0}, g_rr_d_us {0};
static int rr439_mode() { // 0 off, 1 record, 2 record + ring rule
	static const int v = [] {
		const char* f = std::getenv("BC5_0439_RING_FREE");
		const char* r = std::getenv("BC5_0439_RR_RECORD");
		const int   m = (f != nullptr && f[0] == '1' && f[1] == 0) ? 2 : (r != nullptr && r[0] == '1' && r[1] == 0) ? 1 : 0;
		std::fprintf(stderr, "[bc5] exp 0439 (tag rr439): job record %s, ring rule %s\n", m >= 1 ? "on" : "off", m == 2 ? "on (BC5_0439_RING_FREE=1)" : "off");
		return m;
	}();
	return v;
}
// the top-level memory waits of a stream on labels it has not written earlier itself (decoded as the piece filter does)
static void rr439_waits(const uint32_t* ib, uint32_t num_dwords, std::vector<const uint32_t*>* out) {
	std::vector<uint64_t> written;
	for (uint32_t i = 0; i < num_dwords;) {
		const uint32_t h    = ib[i];
		const uint32_t type = h >> 30u;
		uint32_t       len  = 1;
		if (type == 3 || type == 0) { const uint32_t c = (h >> 16u) & 0x3fffu; len = c == 0x3fffu ? 1 : c + 2; }
		if (i + len > num_dwords) break;
		const uint32_t  op = (h >> 8u) & 0xffu;
		const uint32_t* p  = ib + i;
		if (type == 3) {
			const uint32_t dst_sel = len >= 2 ? (p[1] >> 8u) & 0xfu : 0;
			if (op == 0x37 && len >= 4 && (dst_sel == 1 || dst_sel == 2 || dst_sel == 5)) written.push_back((p[2] & ~3u) | (static_cast<uint64_t>(p[3] & 0xffffu) << 32u));
			else if (op == 0x49 && len >= 6) written.push_back((p[3] & ~3u) | (static_cast<uint64_t>(p[4] & 0xffffu) << 32u));
			else if ((op == 0x47 || op == 0x1e) && len >= 4) written.push_back((p[2] & ~3u) | (static_cast<uint64_t>(p[3] & 0xffffu) << 32u));
			else if (((op == 0x3c && len >= 6) || (op == 0x93 && len >= 9)) && ((p[1] >> 4u) & 1u) != 0) {
				const uint64_t label = (p[2] & ~3u) | (static_cast<uint64_t>(p[3] & 0xffffu) << 32u);
				if (label != 0 && std::find(written.begin(), written.end(), label) == written.end()) out->push_back(p);
			}
		}
		i += len;
	}
}
static uint64_t rr439_submit(uint64_t n, const char* kind, int ring, int queue, const uint32_t* ib, uint32_t num_dwords) {
	if (rr439_mode() == 0) return 0;
	std::vector<const uint32_t*> ws;
	rr439_waits(ib, num_dwords, &ws);
	std::lock_guard lk(g_rr_mu);
	const uint64_t id = g_rr_next++;
	Rr439Job&      j  = g_rr_jobs[id & 511u];
	j                 = Rr439Job {};
	j.id = id; j.n = n; j.ring = ring; j.queue = queue; j.dwords = num_dwords; j.done = false; j.t_sub = SoftCp::now_ns();
	std::snprintf(j.kind, sizeof(j.kind), "%s", kind);
	for (const uint32_t* p: ws) {
		const bool is64 = ((p[0] >> 8u) & 0xffu) == 0x93;
		if (wait_satisfied(p, is64)) continue;
		j.nopen++;
		if (j.nwaits < 8) { std::memcpy(j.w[j.nwaits], p, (is64 ? 9 : 6) * sizeof(uint32_t)); j.nwaits++; }
	}
	return id;
}
static void rr439_done(uint64_t id) {
	if (id == 0) return;
	std::lock_guard lk(g_rr_mu);
	Rr439Job& j = g_rr_jobs[id & 511u];
	if (j.id == id) { j.done = true; j.t_done = SoftCp::now_ns(); }
}
static bool rr439_open_wait(const Rr439Job& j, uint64_t* label) { // a recorded wait not met now
	for (uint32_t k = 0; k < j.nwaits; k++) {
		const bool is64 = ((j.w[k][0] >> 8u) & 0xffu) == 0x93;
		if (!wait_satisfied(j.w[k], is64)) { *label = (j.w[k][2] & ~3u) | (static_cast<uint64_t>(j.w[k][3] & 0xffffu) << 32u); return true; }
	}
	return false;
}
// a job of another guest queue in flight on this libdrm ring with a wait not met now (the head-of-line case)
static bool rr439_blocked(int ring, int queue, uint64_t* who, uint64_t* label) {
	std::lock_guard lk(g_rr_mu);
	for (const Rr439Job& j: g_rr_jobs)
		if (j.id != 0 && !j.done && j.ring == ring && j.queue != queue && rr439_open_wait(j, label)) { *who = j.n; return true; }
	return false;
}
static void rr439_dump(const char* why) {
	if (rr439_mode() == 0) return;
	static std::atomic<int> dumps {0};
	if (dumps++ >= 4) return;
	std::lock_guard lk(g_rr_mu);
	const uint64_t now = SoftCp::now_ns();
	journal("rr439: job table at %s: jobs not done, oldest first (ring -1 is GFX; queue is the guest queue; open = unmet top-level waits at submit; now = a recorded wait still unmet now); holds so far %" PRIu64 " (%" PRIu64 " at the bound), d holds %" PRIu64 " (%" PRIu64 " at the bound)\n",
	        why, g_rr_holds.load(), g_rr_bounds.load(), g_rr_d_holds.load(), g_rr_d_bounds.load());
	const uint64_t last = g_rr_next;
	for (uint64_t id = last > 512 ? last - 512 : 1; id < last; id++) {
		const Rr439Job& j = g_rr_jobs[id & 511u];
		if (j.id != id || j.done) continue;
		uint64_t   label = 0;
		const bool open  = rr439_open_wait(j, &label);
		journal("rr439: #%" PRIu64 " %s %u dwords ring %d queue %d, submitted %.1f ms ago, open waits %u (recorded %u), %s 0x%" PRIx64 "\n", j.n, j.kind, j.dwords, j.ring, j.queue,
		        static_cast<double>(now - j.t_sub) / 1e6, j.nopen, j.nwaits, open ? "first unmet now" : "all recorded met now", label);
		for (uint32_t k = 0; k < j.nwaits; k++)
			journal("rr439:   wait on 0x%" PRIx64 " function %u reference 0x%x mask 0x%x\n", (j.w[k][2] & ~3u) | (static_cast<uint64_t>(j.w[k][3] & 0xffffu) << 32u), j.w[k][1] & 7u, j.w[k][4], j.w[k][5]);
	}
	for (int r = -1; r < bc5::direct::kComputeRings; r++) {
		uint32_t inflight = 0, waiters = 0;
		for (const Rr439Job& j: g_rr_jobs) {
			uint64_t l = 0;
			if (j.id == 0 || j.done || j.ring != r) continue;
			inflight++;
			if (rr439_open_wait(j, &l)) waiters++;
		}
		journal("rr439: ring %d: %u jobs in flight, %u with an unmet wait now\n", r, inflight, waiters);
	}
}
#endif
''')
rep(r'''	uint8_t                  x439 = 0;    // exp 0439 (tag dir439): 0 other, 1 GFX, 2 compute
''', r'''	uint8_t                  x439 = 0;    // exp 0439 (tag dir439): 0 other, 1 GFX, 2 compute
	uint64_t                 rr   = 0;    // exp 0439 (tag rr439): its job-table id (0: not recorded)
''')
rep(r'''			g_x439_inf[j.x439 < 3 ? j.x439 : 0]--; // exp 0439 (tag dir439)
''', r'''			g_x439_inf[j.x439 < 3 ? j.x439 : 0]--; // exp 0439 (tag dir439)
			if (r.timed_out) rr439_dump("a fence timeout"); // exp 0439 (tag rr439): before the job is marked done
			rr439_done(j.rr);                                // exp 0439 (tag rr439)
''')
rep(r'''		it.job.x439 = (std::strncmp(kind, "dc439", 5) == 0 || std::strncmp(kind, "sr439c", 6) == 0) ? 0 : (ring == bc5::direct::kGfxRing ? 1 : 2); // exp 0439 (tag dir439)
''', r'''		it.job.x439 = (std::strncmp(kind, "dc439", 5) == 0 || std::strncmp(kind, "sr439c", 6) == 0) ? 0 : (ring == bc5::direct::kGfxRing ? 1 : 2); // exp 0439 (tag dir439)
		it.job.rr   = rr439_submit(n, kind, ring, t_queue_idx, ib, num_dwords);                                                                       // exp 0439 (tag rr439)
''')
rep(r'''#ifndef BC5_LEAN
	{ // exp 0439 (tag ser439 / dir439;''', r'''#ifndef BC5_LEAN
	if (g_async && ring != bc5::direct::kGfxRing && std::strncmp(kind, "dc439", 5) != 0 && std::strncmp(kind, "sr439c", 6) != 0) {
		// exp 0439 (tag rr439): the ring rule (BC5_0439_RING_FREE=1): not onto a ring where another guest queue's job waits
		if (rr439_mode() == 2) {
			uint64_t who = 0, label = 0;
			if (rr439_blocked(ring, t_queue_idx, &who, &label)) {
				const uint64_t h  = ++g_rr_holds;
				const uint64_t t0 = SoftCp::now_ns();
				while (rr439_blocked(ring, t_queue_idx, &who, &label) && SoftCp::now_ns() - t0 < 50'000'000ull) std::this_thread::sleep_for(std::chrono::microseconds(20));
				g_rr_hold_us += (SoftCp::now_ns() - t0) / 1000;
				if (rr439_blocked(ring, t_queue_idx, &who, &label)) {
					const uint64_t b = ++g_rr_bounds;
					if (b <= 64 || b % 1000 == 0) journal("rr439: %s of %u dwords (queue %d) submitted onto ring %d at the 50 ms bound behind #%" PRIu64 " of another queue, still waiting on 0x%" PRIx64 " (%" PRIu64 " such of %" PRIu64 " holds)\n", kind, num_dwords, t_queue_idx, ring, who, label, b, h);
				}
				if ((h & 0x3ffu) == 0) std::fprintf(stderr, "[bc5] exp 0439 (tag rr439): %" PRIu64 " ring-rule holds, %" PRIu64 " at the bound, %.1f ms in all\n", h, g_rr_bounds.load(), static_cast<double>(g_rr_hold_us.load()) / 1000.0);
			}
		}
		// exp 0439 (tag rr439, BC5_0439_SERIAL=d): hold an acb until its own top-level waits are met in memory
		static const bool d_on = [] { const char* e = std::getenv("BC5_0439_SERIAL"); return e != nullptr && e[0] == 'd' && e[1] == 0; }();
		if (d_on) {
			std::vector<const uint32_t*> ws;
			rr439_waits(ib, num_dwords, &ws);
			auto open = [&ws] { for (const uint32_t* p: ws) if (!wait_satisfied(p, ((p[0] >> 8u) & 0xffu) == 0x93)) return true; return false; };
			if (open()) {
				const uint64_t h  = ++g_rr_d_holds;
				const uint64_t t0 = SoftCp::now_ns();
				while (open() && SoftCp::now_ns() - t0 < 50'000'000ull) std::this_thread::sleep_for(std::chrono::microseconds(20));
				g_rr_d_us += (SoftCp::now_ns() - t0) / 1000;
				if (open()) g_rr_d_bounds++;
				if ((h & 0x3ffu) == 0) std::fprintf(stderr, "[bc5] exp 0439 (tag rr439): mode d: %" PRIu64 " acbs held for their own waits, %" PRIu64 " at the bound, %.1f ms in all\n", h, g_rr_d_bounds.load(), static_cast<double>(g_rr_d_us.load()) / 1000.0);
			}
		}
	}
	{ // exp 0439 (tag ser439 / dir439;''')
rep(r'''				        ok ? "" : ", NOT mapped: not read");
				if (!ok) continue;
				const auto* b = reinterpret_cast<const uint32_t*>(e.a);''', r'''				        ok ? "" : ", NOT mapped: not read");
#ifndef BC5_LEAN
				if (FILE* sf = std::fopen((std::string(name) + ".pieces.txt").c_str(), "a"); sf != nullptr) { // exp 0439 (tag rr439): beside the dumps
					std::fprintf(sf, "piece %zu (call depth %d, %s at dword %u of %s %d): 0x%" PRIx64 ", %u dwords%s\n", k, e.depth, e.chain ? "chained" : "called", e.parent_off, e.parent < 0 ? "the buffer" : "piece", e.parent, e.a, e.n, ok ? "" : ", NOT mapped: not read");
					std::fclose(sf);
				}
#endif
				if (!ok) continue;
				const auto* b = reinterpret_cast<const uint32_t*>(e.a);''')

# exp 0439 (tag rr439b, the top session's order of 11-23 ~20:10, build b): the naming record moved inside the timeout
# probe. With BC5_0439_RR_RECORD=1 (or RING_FREE=1): (1) the job table is written at the start of each timeout probe
# (every job not done: ring, guest queue, age, its first wait still unmet now; per ring the jobs in flight), before the
# fault record can end the game; (2) the fault record waits (at most 8 s) while a probe is still running or another
# completion queue still waits on a fence, so the whole piece walk reaches the record; (3) the walk journals each
# piece's LOAD_SH_REG_INDEX (op 0x63, as the probe's own state tracker reads it) and, for each piece wait NOT met, the
# label's pending writes in g_plw (the host's writer table: kernel seq, ring, value); (4) at each dispatch of a timed-out
# buffer: COMPUTE_USER_DATA_0..15 (sh 0x240-0x24f, tools/bc5-agc/regdb/gfx10.json: mm 47360-47420 bytes = 0x2e40-0x2e4f)
# as tracked, and the first 32 dwords at each user-data pair that is a mapped address (its tables: V#s, constants).
rep(r'''[[noreturn]] static void fr412_record_and_exit(uint64_t fault, uint32_t status, bool timed_out, int rc) {
	const double t = timing_now();
''', r'''#ifndef BC5_LEAN
static std::atomic<int> g_rr_probes {0}; // exp 0439 (tag rr439b): timeout probes still running
static uint32_t         rr439_fences_pending(); // defined with the job table
static int              rr439_mode();
static void             rr439_dump(const char* why);
static void             rr439_writers(uint64_t label, char* out, size_t cap); // the label's pending writes in g_plw
#endif
[[noreturn]] static void fr412_record_and_exit(uint64_t fault, uint32_t status, bool timed_out, int rc) {
#ifndef BC5_LEAN
	if (rr439_mode() != 0) { // exp 0439 (tag rr439b): let the other probes reach the record
		const uint64_t t0 = SoftCp::now_ns();
		while ((g_rr_probes.load() > 0 || (SoftCp::now_ns() - t0 < 3'000'000'000ull && rr439_fences_pending() > 1)) && SoftCp::now_ns() - t0 < 8'000'000'000ull)
			std::this_thread::sleep_for(std::chrono::milliseconds(5));
		journal("rr439: fault record after %.0f ms of waiting for probes (%d still running, %u fences pending)\n", static_cast<double>(SoftCp::now_ns() - t0) / 1e6, g_rr_probes.load(), rr439_fences_pending());
	}
#endif
	const double t = timing_now();
''')
rep(r'''static void rr439_dump(const char* why) {
	if (rr439_mode() == 0) return;''', r'''static uint32_t rr439_fences_pending() { return g_cq_fences.load(); }
static void rr439_writers(uint64_t label, char* out, size_t cap) {
	size_t o = 0;
	out[0]   = 0;
	std::lock_guard lk(g_plw_mutex);
	int n = 0;
	for (const auto& w: g_plw)
		if (w.label == label && o + 64 < cap && n++ < 8) o += static_cast<size_t>(std::snprintf(out + o, cap - o, " [seq %" PRIu64 "%s ring %d value 0x%" PRIx64 "]", w.seq & ~(1ull << 63u), (w.seq >> 63u) != 0 ? " early" : "", w.ring, w.value));
	if (n == 0) std::snprintf(out, cap, " none pending");
}
static void rr439_dump(const char* why) {
	if (rr439_mode() == 0) return;''')
rep(r'''			if (r.timed_out && !j.ib_copy.empty()) timeout_probe(j.ib_copy.data(), static_cast<uint32_t>(j.ib_copy.size()), j.kind, j.n, &j.ran_copy, &j.ge_probe); // experiment 0160''', r'''			if (r.timed_out) { // exp 0439 (tag rr439b): the job table first, then the probe, counted for the fault record
				g_rr_probes++;
				rr439_dump("a fence timeout (before the probe)");
			}
			if (r.timed_out && !j.ib_copy.empty()) timeout_probe(j.ib_copy.data(), static_cast<uint32_t>(j.ib_copy.size()), j.kind, j.n, &j.ran_copy, &j.ge_probe); // experiment 0160
			if (r.timed_out) g_rr_probes--; // exp 0439 (tag rr439b)''')
rep(r'''						const bool     mp  = covered_sorted(*pm, l, 8);
						const uint32_t now = mp ? *reinterpret_cast<const volatile uint32_t*>(l) : 0;
						journal("timeout probe:   piece %zu wait at %u on 0x%" PRIx64 " function %u reference 0x%x mask 0x%x; now 0x%x (%s)\n", k, i, l, b[i + 1] & 7u, b[i + 4], b[i + 5], now,
						        !mp ? "label unmapped" : wait_satisfied(&b[i], op == 0x93) ? "met" : "NOT met");''', r'''						const bool     mp  = covered_sorted(*pm, l, 8);
						const uint32_t now = mp ? *reinterpret_cast<const volatile uint32_t*>(l) : 0;
						journal("timeout probe:   piece %zu wait at %u on 0x%" PRIx64 " function %u reference 0x%x mask 0x%x; now 0x%x (%s)\n", k, i, l, b[i + 1] & 7u, b[i + 4], b[i + 5], now,
						        !mp ? "label unmapped" : wait_satisfied(&b[i], op == 0x93) ? "met" : "NOT met");
#ifndef BC5_LEAN
						if (rr439_mode() != 0) { // exp 0439 (tag rr439b): the label's pending writers, also beside the dumps
							char wr[640];
							rr439_writers(l, wr, sizeof(wr));
							const bool met = mp && wait_satisfied(&b[i], op == 0x93);
							if (!met) journal("timeout probe:     its pending writes:%s\n", wr);
							if (FILE* sf = std::fopen((std::string(name) + ".pieces.txt").c_str(), "a"); sf != nullptr) {
								std::fprintf(sf, "  piece %zu wait at %u on 0x%" PRIx64 " function %u reference 0x%x; now 0x%x (%s); pending writes:%s\n", k, i, l, b[i + 1] & 7u, b[i + 4], now, !mp ? "label unmapped" : met ? "met" : "NOT met", wr);
								std::fclose(sf);
							}
						}
#endif''')
rep(r'''						if (l != 0) {
							journal("timeout probe:   piece %zu writes 0x%" PRIx64 " at %u (op %02x)\n", k, l, i, op);
							nl++;
						}''', r'''						if (l != 0) {
							journal("timeout probe:   piece %zu writes 0x%" PRIx64 " at %u (op %02x)\n", k, l, i, op);
							nl++;
						}
#ifndef BC5_LEAN
						if (op == 0x63 && len >= 5 && rr439_mode() != 0) { // exp 0439 (tag rr439b): LOAD_SH_REG_INDEX as the probe's state tracker reads it
							const uint64_t ta = (b[i + 1] & ~3u) | (static_cast<uint64_t>(b[i + 2] & 0xffffu) << 32u);
							const uint32_t tn = b[i + 4] & 0x3fffu;
							char           tb[400];
							if ((b[i + 3] >> 31u) != 0 && ta != 0 && tn != 0 && tn <= 64 && covered_sorted(*pm, ta, static_cast<uint64_t>(tn) * 8)) {
								size_t o = 0;
								for (uint32_t z = 0; z < tn && z < 16 && o + 24 < sizeof(tb); z++) o += static_cast<size_t>(std::snprintf(tb + o, sizeof(tb) - o, " sh 0x%x=%08x", reinterpret_cast<const volatile uint32_t*>(ta)[2 * z] & 0xffffu, reinterpret_cast<const volatile uint32_t*>(ta)[2 * z + 1]));
							} else std::snprintf(tb, sizeof(tb), " (table not read)");
							journal("timeout probe:   piece %zu op 63 at %u: table 0x%" PRIx64 ", %u pairs:%s\n", k, i, ta, tn, tb);
							if (FILE* sf = std::fopen((std::string(name) + ".pieces.txt").c_str(), "a"); sf != nullptr) {
								std::fprintf(sf, "  piece %zu op 63 at %u: table 0x%" PRIx64 ", %u pairs:%s\n", k, i, ta, tn, tb);
								std::fclose(sf);
							}
						}
#endif''')
rep(r'''						journal("timeout probe: dispatch op %02x at %u: program %s0x%" PRIx64 ", groups %s%s%s\n", op, q, pl == 0xffffffffu ? "not set in this buffer, " : "",
						        (static_cast<uint64_t>(pl) | (static_cast<uint64_t>(ph & 0xffu) << 32u)) << 8u, grid, where, ex);''', r'''						journal("timeout probe: dispatch op %02x at %u: program %s0x%" PRIx64 ", groups %s%s%s\n", op, q, pl == 0xffffffffu ? "not set in this buffer, " : "",
						        (static_cast<uint64_t>(pl) | (static_cast<uint64_t>(ph & 0xffu) << 32u)) << 8u, grid, where, ex);
#ifndef BC5_LEAN
						if (rr439_mode() != 0) { // exp 0439 (tag rr439b): the dispatch's user data and the tables it points at
							static std::atomic<int> nud439 {0};
							if (nud439++ < 256) {
								char   ud[200];
								size_t o = 0;
								for (uint32_t z = 0; z < 16 && o + 10 < sizeof(ud); z++) o += static_cast<size_t>(std::snprintf(ud + o, sizeof(ud) - o, " %08x", g(st_sh, 0x240u + z)));
								journal("timeout probe:   user data at %u (COMPUTE_USER_DATA_0..15):%s\n", q, ud);
								for (uint32_t z = 0; z + 1 < 16; z++) {
									const uint32_t lo = g(st_sh, 0x240u + z), hi = g(st_sh, 0x241u + z);
									if (lo == 0xffffffffu || hi == 0xffffffffu) continue;
									const uint64_t a = static_cast<uint64_t>(lo) | (static_cast<uint64_t>(hi & 0xffffu) << 32u);
									if (a < 0x100000000ull || (a & 3u) != 0 || !covered_sorted(*pm, a, 128)) continue;
									char tb[600];
									rd(a, 32, tb, sizeof(tb));
									journal("timeout probe:     user data %u-%u as an address: %s\n", z, z + 1, tb);
								}
							}
						}
#endif''')

# exp 0439 (tag rb439, ring binding v2, after the m2 naming run of 11-23 20:19): BC5_0439_RING_BIND=2 (normal build
# only; turns the job record on). The m2 record: every title acb in flight sat on libdrm ring 0 behind acb #102 of
# another guest queue, which waited for a label GFX writes after the GFX piece wait that itself waited for later work
# of the title: head-of-line blocking, a host artifact (on the console each guest queue runs on its own). w428 keeps a
# queue on ring 0 until its 256th acb. With RING_BIND=2 an acb goes to the ring of its own queue's jobs still in flight
# (the queue's order stays FIFO); a queue with nothing in flight takes a ring with no unmet wait among its jobs in flight
# (an idle one first, else the least loaded); when every ring holds such a waiter the acb is held on the host until one
# frees, bounded at 50 ms, then the ring with the fewest waiters (journaled). The queue's compute state comes from
# aq424's per-queue prefix as before (a libdrm ring index is no fixed hardware queue, exp 0427), so a move needs no idle
# wait. Counts on stderr every 1024 acbs.
rep(r'''static int                   acb_ring(const uint32_t* ib, uint32_t num_dwords) {
	int ring = compute_ring_env();
	if (ring < 0) return bc5::direct::kGfxRing;
	if (w428_rings() > 1) ring = w428_queue_ring(); // exp 0428 (tag w428): this guest queue's ring index''', r'''#ifndef BC5_LEAN
static int rb439_ring(int queue, int rings); // exp 0439 (tag rb439): defined with the job table; -1 when off
#endif
static int                   acb_ring(const uint32_t* ib, uint32_t num_dwords) {
	int ring = compute_ring_env();
	if (ring < 0) return bc5::direct::kGfxRing;
#ifndef BC5_LEAN
	if (const int rb = w428_rings() > 1 ? rb439_ring(t_queue_idx, w428_rings()) : -1; rb >= 0) ring = rb; // exp 0439 (tag rb439)
	else
#endif
	if (w428_rings() > 1) ring = w428_queue_ring(); // exp 0428 (tag w428): this guest queue's ring index''')
rep(r'''static int rr439_mode() { // 0 off, 1 record, 2 record + ring rule
	static const int v = [] {
		const char* f = std::getenv("BC5_0439_RING_FREE");
		const char* r = std::getenv("BC5_0439_RR_RECORD");
		const int   m = (f != nullptr && f[0] == '1' && f[1] == 0) ? 2 : (r != nullptr && r[0] == '1' && r[1] == 0) ? 1 : 0;''', r'''static bool rb439_on() { // exp 0439 (tag rb439): BC5_0439_RING_BIND=2
	static const bool v = [] {
		const char* e = std::getenv("BC5_0439_RING_BIND");
		const bool  b = e != nullptr && e[0] == '2' && e[1] == 0;
		std::fprintf(stderr, "[bc5] exp 0439 (tag rb439): ring binding v2 %s\n", b ? "on (BC5_0439_RING_BIND=2: a queue keeps the ring of its jobs in flight, else a ring without an unmet wait)" : "off");
		return b;
	}();
	return v;
}
static int rr439_mode() { // 0 off, 1 record, 2 record + ring rule
	static const int v = [] {
		const char* f = std::getenv("BC5_0439_RING_FREE");
		const char* r = std::getenv("BC5_0439_RR_RECORD");
		const int   m = (f != nullptr && f[0] == '1' && f[1] == 0) ? 2 : ((r != nullptr && r[0] == '1' && r[1] == 0) || rb439_on()) ? 1 : 0;''')
rep(r'''static void rr439_done(uint64_t id) {''', r'''static bool rr439_open_wait(const Rr439Job& j, uint64_t* label);
static std::atomic<uint64_t> g_rb_n {0}, g_rb_kept {0}, g_rb_free {0}, g_rb_holds {0}, g_rb_bounds {0}, g_rb_hold_us {0};
static int rb439_ring(int queue, int rings) {
	if (!rb439_on() || rr439_mode() == 0) return -1;
	if (rings > bc5::direct::kComputeRings) rings = bc5::direct::kComputeRings;
	const uint64_t c  = ++g_rb_n;
	const uint64_t t0 = SoftCp::now_ns();
	int            pick = -1;
	bool           held = false;
	for (;;) {
		uint32_t inflight[bc5::direct::kComputeRings] = {}, waiters[bc5::direct::kComputeRings] = {};
		int      own = -1;
		{
			std::lock_guard lk(g_rr_mu);
			for (const Rr439Job& j: g_rr_jobs) {
				if (j.id == 0 || j.done || j.ring < 0 || j.ring >= rings) continue;
				if (j.queue == queue) own = j.ring;
				inflight[j.ring]++;
				uint64_t l = 0;
				if (rr439_open_wait(j, &l)) waiters[j.ring]++;
			}
		}
		if (own >= 0) { g_rb_kept++; pick = own; break; } // the queue's order: behind its own jobs
		int best = -1;
		for (int r = 0; r < rings; r++)
			if (waiters[r] == 0 && (best < 0 || inflight[r] < inflight[best])) best = r;
		if (best >= 0) { g_rb_free++; pick = best; break; }
		if (!held) { held = true; g_rb_holds++; }
		if (SoftCp::now_ns() - t0 >= 50'000'000ull) { // every ring holds a waiter: the fewest waiters, journaled
			best = 0;
			for (int r = 1; r < rings; r++) if (waiters[r] < waiters[best]) best = r;
			const uint64_t b = ++g_rb_bounds;
			if (b <= 64 || b % 1000 == 0) journal("rb439: an acb of queue %d placed on ring %d at the 50 ms bound: every ring holds a job with an unmet wait (%" PRIu64 " such)\n", queue, best, b);
			pick = best;
			break;
		}
		std::this_thread::sleep_for(std::chrono::microseconds(20));
	}
	if (held) g_rb_hold_us += (SoftCp::now_ns() - t0) / 1000;
	if ((c & 0x3ffu) == 0)
		std::fprintf(stderr, "[bc5] exp 0439 (tag rb439): %" PRIu64 " acbs placed: %" PRIu64 " behind their own queue, %" PRIu64 " onto a ring without a waiter, %" PRIu64 " held (%" PRIu64 " at the bound, %.1f ms in all)\n", c, g_rb_kept.load(),
		             g_rb_free.load(), g_rb_holds.load(), g_rb_bounds.load(), static_cast<double>(g_rb_hold_us.load()) / 1000.0);
	return pick;
}
static void rr439_done(uint64_t id) {''')

# exp 0439 (tag rr439d, the top session's order of 11-23 ~20:45): the writer search. With the job record on:
# BC5_0439_RR_WATCH=<base>,<count>,<stride> (hex base; e.g. 0x2000008200,8,0x20): the labels whose values are recorded
# at every job's submit and at the timeout (read only through the GPU mapping check). Each recorded job keeps a copy of
# its buffer (up to 16384 dwords). At a fence timeout, the last 64 jobs (done or not) are written beside the dumps
# (rr-<n>-<kind>-q<queue>-r<ring>.bin) and each one with its pieces (0x3f/0x33 calls to depth 3 and chains, read
# through the mapping check, 256 pieces at most) is searched for every packet that names a watched label (in any
# address pair of its payload): the job, piece, dword, op, and for waits the function and reference.
rep(r'''	uint32_t w[8][9] = {};
};''', r'''	uint32_t w[8][9] = {};
	uint32_t ctr[16] = {};          // exp 0439 (tag rr439d): the watched labels at submit
	std::vector<uint32_t> ibc;      // exp 0439 (tag rr439d): the job's buffer as submitted
};
struct Rr439Watch {
	uint64_t base = 0;
	uint32_t count = 0, stride = 0;
};
static const Rr439Watch& rr439_watch() {
	static const Rr439Watch v = [] {
		Rr439Watch  w;
		const char* e = std::getenv("BC5_0439_RR_WATCH");
		if (e != nullptr && e[0] != 0) {
			char* end = nullptr;
			w.base    = std::strtoull(e, &end, 16);
			if (end != nullptr && *end == ',') w.count = static_cast<uint32_t>(std::strtoul(end + 1, &end, 10));
			if (end != nullptr && *end == ',') w.stride = static_cast<uint32_t>(std::strtoul(end + 1, &end, 16));
			if (w.count > 16) w.count = 16;
			if (w.stride == 0) w.count = 0;
		}
		std::fprintf(stderr, "[bc5] exp 0439 (tag rr439d): watched labels: %u from 0x%" PRIx64 " stride 0x%x\n", w.count, w.base, w.stride);
		return w;
	}();
	return v;
}
static void rr439_read_watch(uint32_t* out) {
	const Rr439Watch& w = rr439_watch();
	if (w.count == 0 || !g_dev) return;
	const auto pm = g_dev->sorted_mappings();
	for (uint32_t k = 0; k < w.count; k++) {
		const uint64_t a = w.base + static_cast<uint64_t>(k) * w.stride;
		out[k]           = covered_sorted(*pm, a, 4) ? *reinterpret_cast<const volatile uint32_t*>(a) : 0xdeadbeefu;
	}
}''')
rep(r'''	j.id = id; j.n = n; j.ring = ring; j.queue = queue; j.dwords = num_dwords; j.done = false; j.t_sub = SoftCp::now_ns();''', r'''	j.id = id; j.n = n; j.ring = ring; j.queue = queue; j.dwords = num_dwords; j.done = false; j.t_sub = SoftCp::now_ns();
	rr439_read_watch(j.ctr);                                              // exp 0439 (tag rr439d)
	if (num_dwords <= 16384) j.ibc.assign(ib, ib + num_dwords);           // exp 0439 (tag rr439d)''')
rep(r'''	for (int r = -1; r < bc5::direct::kComputeRings; r++) {
		uint32_t inflight = 0, waiters = 0;''', r'''	{ // exp 0439 (tag rr439d): the watched labels now, at each of the last 64 submits, and every packet naming them
		const Rr439Watch& wt = rr439_watch();
		if (wt.count != 0) {
			uint32_t cur[16] = {};
			rr439_read_watch(cur);
			char   line[400];
			size_t o = 0;
			for (uint32_t k = 0; k < wt.count; k++) o += static_cast<size_t>(std::snprintf(line + o, sizeof(line) - o, " 0x%" PRIx64 "=%08x", wt.base + static_cast<uint64_t>(k) * wt.stride, cur[k]));
			journal("rr439d: watched labels now:%s\n", line);
		}
		const auto pm   = g_dev ? g_dev->sorted_mappings() : nullptr;
		const uint64_t lastid = g_rr_next;
		for (uint64_t id = lastid > 64 ? lastid - 64 : 1; id < lastid; id++) {
			const Rr439Job& j = g_rr_jobs[id & 511u];
			if (j.id != id) continue;
			char   line[400];
			size_t o = 0;
			for (uint32_t k = 0; k < wt.count; k++) o += static_cast<size_t>(std::snprintf(line + o, sizeof(line) - o, " %08x", j.ctr[k]));
			journal("rr439d: #%" PRIu64 " %s %u dwords ring %d queue %d %s, %.1f ms ago; watched at submit:%s\n", j.n, j.kind, j.dwords, j.ring, j.queue, j.done ? "done" : "NOT done",
			        static_cast<double>(now - j.t_sub) / 1e6, line);
			if (!g_dump_dir.empty() && !j.ibc.empty()) {
				char fn[700];
				std::snprintf(fn, sizeof(fn), "%s/rr-%06" PRIu64 "-%s-q%d-r%d.bin", g_dump_dir.c_str(), j.n, j.kind, j.queue, j.ring);
				if (FILE* f = std::fopen(fn, "wb"); f != nullptr) {
					std::fwrite(j.ibc.data(), 4, j.ibc.size(), f);
					std::fclose(f);
				}
			}
			if (wt.count == 0 || j.ibc.empty() || !pm) continue;
			// the buffer and its pieces: every packet whose payload names a watched label
			struct Pc {
				const uint32_t* p;
				uint32_t        n;
				int             depth;
				uint64_t        a;
			};
			std::vector<Pc>       todo {{j.ibc.data(), static_cast<uint32_t>(j.ibc.size()), 0, 0}};
			std::vector<uint64_t> seen;
			for (size_t t = 0; t < todo.size() && t < 256; t++) {
				const Pc pc = todo[t];
				for (uint32_t i = 0; i < pc.n;) {
					const uint32_t h  = pc.p[i];
					const uint32_t ty = h >> 30u;
					uint32_t       ln = 1;
					if (ty == 3 || ty == 0) { const uint32_t c = (h >> 16u) & 0x3fffu; ln = c == 0x3fffu ? 1 : c + 2; }
					if (i + ln > pc.n) break;
					const uint32_t op = (h >> 8u) & 0xffu;
					if (ty == 3 && (op == 0x3f || op == 0x33) && ln >= 4) {
						const uint64_t a  = (pc.p[i + 1] & ~3u) | (static_cast<uint64_t>(pc.p[i + 2] & 0xffffu) << 32u);
						const uint32_t sz = pc.p[i + 3] & 0xfffffu;
						const bool     ch = (pc.p[i + 3] & (1u << 20)) != 0;
						const int      d  = ch ? pc.depth : pc.depth + 1;
						if (a != 0 && sz != 0 && sz <= (1u << 20) && d <= 3 && std::find(seen.begin(), seen.end(), a) == seen.end() && covered_sorted(*pm, a, static_cast<uint64_t>(sz) * 4)) {
							seen.push_back(a);
							todo.push_back({reinterpret_cast<const uint32_t*>(a), sz, d, a});
						}
					}
					if (ty == 3)
						for (uint32_t k = 1; k + 1 < ln; k++) {
							const uint64_t a = (pc.p[i + k] & ~3u) | (static_cast<uint64_t>(pc.p[i + k + 1] & 0xffffu) << 32u);
							if (a < wt.base || a >= wt.base + static_cast<uint64_t>(wt.count) * wt.stride || (a - wt.base) % wt.stride != 0) continue;
							if ((op == 0x3c || op == 0x93) && k == 2) journal("rr439d:   #%" PRIu64 " %s 0x%" PRIx64 " dword %u: WAIT on 0x%" PRIx64 " function %u reference 0x%x\n", j.n, t == 0 ? "top" : "piece", pc.a, i, a, pc.p[i + 1] & 7u, ln > 4 ? pc.p[i + 4] : 0u);
							else journal("rr439d:   #%" PRIu64 " %s 0x%" PRIx64 " dword %u: op %02x names 0x%" PRIx64 " at payload dword %u (%u dwords)\n", j.n, t == 0 ? "top" : "piece", pc.a, i, op, a, k, ln);
						}
					i += ln;
				}
			}
		}
	}
	for (int r = -1; r < bc5::direct::kComputeRings; r++) {
		uint32_t inflight = 0, waiters = 0;''')

# exp 0439 (tag f4p439, arm A, the top session's word of 11-23 ~21:00; a private test arm, normal build only):
# BC5_0439_F4_PIECES=1, effective with BC5_0439_PIECE_WAITS=2 (the GFX piece waits kept for the GPU). ho430's cycle
# guard (F2: no F4 kernel dependency when the writer job holds a kept GPU wait on a label the waiting buffer writes)
# knows only the writer's ROOT kept waits. With this arm, ho430::job_submitted also records the memory waits of the
# job's pieces (bc5/f4p0439.hpp, det-tested by test_f4p0439.cpp; each piece read only when mapped): in mode 2 every
# piece wait reaches the GPU. The w2 hang: acb #171 (queue 24) waited on 0x2000008000, met in memory, with a pending
# write of it by the GFX dcb, whose piece 19 waited on 0x20000082e0, which #171 releases: F4 ordered #171 behind the
# whole dcb. With the arm the guard sees the cycle and adds no dependency (exp 0430's F848 stale-pass risk accepted for
# a test arm; a bake would need the second title's fight test, not installed).
rep(r'''#include <tuple>
#include <vector>

// Experiment 0336: the process parameter''', r'''#include <tuple>
#include <vector>
#ifndef BC5_LEAN
#include "bc5/f4p0439.hpp" // exp 0439 (tag f4p439, arm A)
#endif

// Experiment 0336: the process parameter''')
rep(r'''inline void job_submitted(const uint32_t* ib, uint32_t num_dwords, const std::vector<uint32_t>& executed, uint64_t seq, int ring, const char* kind) {
	(void)kind;''', r'''#ifndef BC5_LEAN
static bool f4p439_on() { // exp 0439 (tag f4p439, arm A)
	static const bool v = [] {
		const char* e = std::getenv("BC5_0439_F4_PIECES");
		const char* m = std::getenv("BC5_0439_PIECE_WAITS");
		const bool  b = e != nullptr && e[0] == '1' && e[1] == 0 && m != nullptr && m[0] == '2' && m[1] == 0;
		std::fprintf(stderr, "[bc5] exp 0439 (tag f4p439): F2 guard with the writer's piece waits %s\n", b ? "on (BC5_0439_F4_PIECES=1, PIECE_WAITS=2)" : "off");
		return b;
	}();
	return v;
}
#endif
inline void job_submitted(const uint32_t* ib, uint32_t num_dwords, const std::vector<uint32_t>& executed, uint64_t seq, int ring, const char* kind) {
	(void)kind;''')
rep(r'''	Store&          s = st();
	std::lock_guard lk(s.m);
	if (!waits.empty()) {
		s.job_waits[{ring, seq}] = std::move(waits);''', r'''#ifndef BC5_LEAN
	if (f4p439_on() && g_dev) { // exp 0439 (tag f4p439, arm A): the pieces' waits are kept waits too in mode 2
		const auto pm = g_dev->sorted_mappings();
		const auto pw = bc5::f4p439::piece_waits(ib, num_dwords, executed, [&pm](uint64_t a, uint32_t n) -> const uint32_t* { return covered_sorted(*pm, a, static_cast<uint64_t>(n) * 4) ? reinterpret_cast<const uint32_t*>(a) : nullptr; });
		waits.insert(waits.end(), pw.begin(), pw.end());
	}
#endif
	Store&          s = st();
	std::lock_guard lk(s.m);
	if (!waits.empty()) {
		s.job_waits[{ring, seq}] = std::move(waits);''')

# exp 0439 (tag tsp439, arm C, the top session's "C yes" of 11-23 ~21:00; a private test arm, normal build only):
# BC5_0439_DCB_TAIL_SPLIT=1. A dcb whose root ends in a CHAIN into its pieces (bc5/f4p0439.hpp tail_chain_at,
# det-tested) goes to the kernel as two jobs: the root up to the chain (it holds the root's label releases, here
# RELEASE_MEM of 0x2000008000 at root dword 1882) and then the chain behind the root's register state replayed by the
# dry tracker (the split path submit_split already uses at a wait the host serves, exp 0077-0079/0119/0428). ho430's
# F4 then orders a waiting acb behind the job that actually holds the release, not behind the pieces with their kept
# waits: in w2 acb #171 would run as soon as the root's release is done, and the GFX wait in piece 19 meets its
# release. When the awaited release sits inside the pieces (job 2), F4 still orders by that whole job and the cycle
# can remain; arm A's guard is the cover for that case. Counts on stderr every 1024 splits.
rep(r'''static void submit_split(const uint32_t* ib, uint32_t num_dwords, const char* kind) {
	if (std::strcmp(kind, "dcb") == 0) ph439_hold(ib, num_dwords); // exp 0439 (tag ph439): before the buffer goes
	t_wait_given_up = false;
	t_keep_waits.clear();
	std::vector<uint64_t> written;
	uint32_t start = 0, i = 0;''', r'''#ifndef BC5_LEAN
static bool tsp439_on() { // exp 0439 (tag tsp439, arm C)
	static const bool v = [] {
		const char* e = std::getenv("BC5_0439_DCB_TAIL_SPLIT");
		const bool  b = e != nullptr && e[0] == '1' && e[1] == 0;
		std::fprintf(stderr, "[bc5] exp 0439 (tag tsp439): dcb tail split %s\n", b ? "on (BC5_0439_DCB_TAIL_SPLIT=1: the root before its final chain is its own job)" : "off");
		return b;
	}();
	return v;
}
static std::atomic<uint64_t> g_tsp_splits {0}, g_tsp_nodry {0};
#endif
static void submit_split(const uint32_t* ib, uint32_t num_dwords, const char* kind) {
	if (std::strcmp(kind, "dcb") == 0) ph439_hold(ib, num_dwords); // exp 0439 (tag ph439): before the buffer goes
	t_wait_given_up = false;
	t_keep_waits.clear();
	std::vector<uint64_t> written;
	uint32_t start = 0, i = 0;
#ifndef BC5_LEAN
	const int64_t tsp_at = tsp439_on() && std::strcmp(kind, "dcb") == 0 ? bc5::f4p439::tail_chain_at(ib, num_dwords) : -1; // exp 0439 (tag tsp439)
#endif''')
rep(r'''		std::erase_if(t_keep_waits, [&one](const uint32_t* w) { return w >= one.data() && w < one.data() + one.size(); });
	};
	while (i < num_dwords) {
		const uint32_t h = ib[i];
		const uint32_t type = h >> 30u;
		uint32_t len = 1;
		if (type == 3 || type == 0) { const uint32_t c = (h >> 16u) & 0x3fffu; len = c == 0x3fffu ? 1 : c + 2; }
		if (i + len > num_dwords) break;
		const uint32_t  op = (h >> 8u) & 0xffu;
		const uint32_t* p  = ib + i;
		if (type == 3) {
			const uint32_t dst_sel = len >= 2 ? (p[1] >> 8u) & 0xfu : 0;
			if (op == 0x37 && len >= 4 && (dst_sel == 1 || dst_sel == 2 || dst_sel == 5)) written.push_back((p[2] & ~3u) | (static_cast<uint64_t>(p[3] & 0xffffu) << 32u));
			else if (op == 0x49 && len >= 6) written.push_back((p[3] & ~3u) | (static_cast<uint64_t>(p[4] & 0xffffu) << 32u));
			else if (op == 0x47 && len >= 4) written.push_back((p[2] & ~3u) | (static_cast<uint64_t>(p[3] & 0xffffu) << 32u));
			else if (op == 0x1e && len >= 4) written.push_back((p[2] & ~3u) | (static_cast<uint64_t>(p[3] & 0xffffu) << 32u));''', r'''		std::erase_if(t_keep_waits, [&one](const uint32_t* w) { return w >= one.data() && w < one.data() + one.size(); });
	};
	while (i < num_dwords) {
		const uint32_t h = ib[i];
		const uint32_t type = h >> 30u;
		uint32_t len = 1;
		if (type == 3 || type == 0) { const uint32_t c = (h >> 16u) & 0x3fffu; len = c == 0x3fffu ? 1 : c + 2; }
		if (i + len > num_dwords) break;
		const uint32_t  op = (h >> 8u) & 0xffu;
		const uint32_t* p  = ib + i;
#ifndef BC5_LEAN
		if (tsp_at >= 0 && static_cast<int64_t>(i) == tsp_at && i > start) { // exp 0439 (tag tsp439, arm C): the root before its tail chain goes first
			if (t_fs_valid && g_dev) {
				std::shared_ptr<const bc5::direct::MappingIndex> maps_p = g_dev->sorted_mappings();
				const bc5::full_state::Tracker::Reader read = [&maps_p](uint64_t a, uint64_t bytes) -> const uint32_t* {
					return covered_sorted(*maps_p, a, bytes) ? reinterpret_cast<const uint32_t*>(a) : nullptr;
				};
				if (!dry) {
					dry.emplace(t_fs_before);
					g_dry_bufs++;
				}
				bc5::full_state::Stats dst;
				dry->apply(std::span<const uint32_t>(ib + dry_at, i - dry_at), read, dst);
				dry_at = i;
				if ((start > 0 || prefix_all() || cs_used) && !full_prefix.empty()) submit_prefixed(full_prefix, ib + start, i - start);
				else submit_one(ib + start, i - start, kind);
				chain_flush(1); // ADR 0010: the head is its own job
				full_prefix = prefix_of(*dry);
				start       = i;
				full_used   = true;
				const uint64_t k = ++g_tsp_splits;
				if ((k & 0x3ffu) == 0 || k <= 4) std::fprintf(stderr, "[bc5] exp 0439 (tag tsp439): %" PRIu64 " dcbs split before their tail chain (%" PRIu64 " not split: no register state)\n", k, g_tsp_nodry.load());
			} else {
				g_tsp_nodry++;
			}
		}
#endif
		if (type == 3) {
			const uint32_t dst_sel = len >= 2 ? (p[1] >> 8u) & 0xfu : 0;
			if (op == 0x37 && len >= 4 && (dst_sel == 1 || dst_sel == 2 || dst_sel == 5)) written.push_back((p[2] & ~3u) | (static_cast<uint64_t>(p[3] & 0xffffu) << 32u));
			else if (op == 0x49 && len >= 6) written.push_back((p[3] & ~3u) | (static_cast<uint64_t>(p[4] & 0xffffu) << 32u));
			else if (op == 0x47 && len >= 4) written.push_back((p[2] & ~3u) | (static_cast<uint64_t>(p[3] & 0xffffu) << 32u));
			else if (op == 0x1e && len >= 4) written.push_back((p[2] & ~3u) | (static_cast<uint64_t>(p[3] & 0xffffu) << 32u));''')

# exp 0439 (tag fn439): at each timeout the job table's dump also writes the backend's kernel-submit record (the last
# 1024 submits with their fences' status now, mkfn439be.py) beside the dumps as fn439-<k>.txt (BC5_0439_FN_RECORD=1).
rep(r'''static void rr439_dump(const char* why) {
	if (rr439_mode() == 0) return;''', r'''extern "C" int bc5_fn439_write(const char* path); // exp 0439 (tag fn439): the backend (k439/mkfn439be.py)
static void rr439_dump(const char* why) {
	if (rr439_mode() == 0) return;
	{ // exp 0439 (tag fn439)
		static std::atomic<int> nfn {0};
		const int               k = nfn++;
		if (k < 4 && !g_dump_dir.empty()) {
			const std::string path = g_dump_dir + "/fn439-" + std::to_string(k) + ".txt";
			const int         rc   = bc5_fn439_write(path.c_str());
			journal("rr439: kernel-submit record %s (%s)\n", path.c_str(), rc == 0 ? "written" : "off or failed");
		}
	}''')

# exp 0439 (tag f4p439, step 2, the top session's order of 11-23 ~22:05): in vk the guard missed one cycle after about
# 1,100 frames (GFX job 2257 waited in piece 36 on 0x20000081c0, which the acb F4 ordered behind it releases). ho430's
# job_waits is a map keyed (ring, seq) capped at 4096 entries by erasing begin(): the GFX ring (-1) sorts first, so once
# the map is full a GFX job's entry (with arm A's piece waits) can be the one erased. With arm A on, the cap is 65536
# (the map's size journaled every 4096), and every F4 that fires is journaled with each writer job's recorded kept-wait
# count and whether the waiting buffer's writes are among them.
rep(r'''		s.job_waits[{ring, seq}] = std::move(waits);
		if (s.job_waits.size() > 4096) s.job_waits.erase(s.job_waits.begin());''', r'''		s.job_waits[{ring, seq}] = std::move(waits);
#ifndef BC5_LEAN
		if (f4p439_on()) { // exp 0439 (tag f4p439 step 2): a larger cap; the size journaled
			if ((s.job_waits.size() & 0xfffu) == 0) journal("f4p439: ho430 job_waits holds %zu jobs\n", s.job_waits.size());
			if (s.job_waits.size() > 65536) s.job_waits.erase(s.job_waits.begin());
		} else
#endif
		if (s.job_waits.size() > 4096) s.job_waits.erase(s.job_waits.begin());''')
rep(r'''#ifndef BC5_LEAN
	const uint64_t k = s.f4_fence++;
#endif
	lk.unlock();''', r'''#ifndef BC5_LEAN
	if (f4p439_on()) // exp 0439 (tag f4p439 step 2): why the guard let this F4 through
		for (const auto& o: others) {
			const auto it  = s.job_waits.find(o);
			size_t     nin = 0;
			if (it != s.job_waits.end())
				for (const uint64_t l: it->second) nin += std::find(writes.begin(), writes.end(), l) != writes.end() ? 1 : 0;
			journal("f4p439: F4 on 0x%" PRIx64 " (%s at %u): writer job %" PRIu64 " ring %d: %s, %zu kept waits recorded, %zu of them on labels this buffer writes (%zu writes); job_waits holds %zu jobs\n", label, kind, off,
			        o.second, o.first, it == s.job_waits.end() ? "NOT in job_waits" : "in job_waits", it == s.job_waits.end() ? size_t {0} : it->second.size(), nin, writes.size(), s.job_waits.size());
		}
	const uint64_t k = s.f4_fence++;
#endif
	lk.unlock();''')

# exp 0439 (tag f4p439, step 3, after vk2 of 11-23 22:10): the F4 that slipped had its writer (a GFX job) NOT in
# ho430's job_waits ("0 kept waits recorded; job_waits holds 0 jobs"): job_submitted recorded nothing for that dcb (its
# executed offsets did not reach the root's IB packets), so arm A's piece walk never ran for it. Step 3, with arm A on:
# at F4 time each writer job is looked up in the rr439 job table by its kernel seq (kept at submit) and its buffer as
# submitted is walked with bc5/f4p0439.hpp piece_waits (every packet taken as executed; each piece read only when
# mapped); a cycle there refuses the dependency as F2 does, journaled.
rep(r'''	uint64_t id = 0, n = 0, t_sub = 0, t_done = 0;''', r'''	uint64_t id = 0, n = 0, t_sub = 0, t_done = 0, kseq = 0; // kseq: the kernel's seq (exp 0439 f4p439 step 3)''')
rep(r'''static uint64_t rr439_submit(uint64_t n, const char* kind, int ring, int queue, const uint32_t* ib, uint32_t num_dwords) {''', r'''static uint64_t rr439_submit(uint64_t n, const char* kind, int ring, int queue, const uint32_t* ib, uint32_t num_dwords, uint64_t kseq) {''')
rep(r'''	j.id = id; j.n = n; j.ring = ring; j.queue = queue; j.dwords = num_dwords; j.done = false; j.t_sub = SoftCp::now_ns();''', r'''	j.id = id; j.n = n; j.ring = ring; j.queue = queue; j.dwords = num_dwords; j.done = false; j.t_sub = SoftCp::now_ns(); j.kseq = kseq;''')
rep(r'''		it.job.rr   = rr439_submit(n, kind, ring, t_queue_idx, ib, num_dwords);''', r'''		it.job.rr   = rr439_submit(n, kind, ring, t_queue_idx, ib, num_dwords, r.seq_no);''')
rep(r'''static void rr439_done(uint64_t id) {''', r'''// exp 0439 (tag f4p439 step 3): does a writer job (ring, kernel seq) still in flight wait, in its pieces, on a label
// the waiting buffer writes? 1 yes, 0 no, -1 not in the table (or no buffer copy).
static int rr439_writer_piece_cycle(int ring, uint64_t kseq, const std::vector<uint64_t>& writes, size_t* nwaits) {
	std::vector<uint32_t> ibc;
	{
		std::lock_guard lk(g_rr_mu);
		for (const Rr439Job& j: g_rr_jobs)
			if (j.id != 0 && !j.done && j.ring == ring && j.kseq == kseq && !j.ibc.empty()) {
				ibc = j.ibc;
				break;
			}
	}
	if (ibc.empty() || !g_dev) return -1;
	std::vector<uint32_t> all;
	for (uint32_t q = 0; q < ibc.size();) {
		all.push_back(q);
		q += bc5::f4p439::pkt_len(ibc[q]);
	}
	const auto pm = g_dev->sorted_mappings();
	const auto pw = bc5::f4p439::piece_waits(ibc.data(), static_cast<uint32_t>(ibc.size()), all, [&pm](uint64_t a, uint32_t n) -> const uint32_t* { return covered_sorted(*pm, a, static_cast<uint64_t>(n) * 4) ? reinterpret_cast<const uint32_t*>(a) : nullptr; });
	if (nwaits != nullptr) *nwaits = pw.size();
	return bc5::f4p439::cycle(pw, writes) ? 1 : 0;
}
static void rr439_done(uint64_t id) {''')
rep(r'''namespace ho430 {
''', r'''#ifndef BC5_LEAN
static int rr439_writer_piece_cycle(int ring, uint64_t kseq, const std::vector<uint64_t>& writes, size_t* nwaits); // exp 0439 (tag f4p439 step 3), defined with the job table
#endif
namespace ho430 {
''')
rep(r'''#ifndef BC5_LEAN
	if (f4p439_on()) // exp 0439 (tag f4p439 step 2): why the guard let this F4 through''', r'''#ifndef BC5_LEAN
	if (f4p439_on()) { // exp 0439 (tag f4p439 step 3): the writer's pieces from the job table
		for (const auto& o: others) {
			size_t    nw = 0;
			const int c  = rr439_writer_piece_cycle(o.first, o.second, writes, &nw);
			if (c == 1) {
				static std::atomic<uint64_t> n3 {0};
				const uint64_t               k3 = n3++;
				if (k3 < 64 || (k3 & 0xfffu) == 0)
					journal("f4p439: %s wait at %u on 0x%" PRIx64 " (satisfied): writer job %" PRIu64 " ring %d waits in its pieces (%zu waits) on a label this buffer writes: a cycle, not ordered (step 3, %" PRIu64 " so far)\n", kind, off, label, o.second, o.first, nw, k3 + 1);
				return;
			}
		}
	}
	if (f4p439_on()) // exp 0439 (tag f4p439 step 2): why the guard let this F4 through''')

# exp 0439 (tag f4off439, after vk3 of 11-23 22:21; a private test arm, normal build only): BC5_0439_F4_OFF=1 with
# BC5_0439_PIECE_WAITS=2: ho430's F4 adds no kernel dependency at all (each case it would have added journaled, the
# first 64 and every 4096th). vk3 ran about 815 frames and hung on an F4 whose writer GFX job held 48 kept waits, none
# on the waiting buffer's own writes: the cycle ran through work queued behind the ordered buffer, which F2's question
# (this buffer's writes) cannot see. On the console the waits are decided by each queue's CP when it reaches them; F4
# exists for exp 0430's F848 (a stale label passing a wait), whose risk this arm takes.
rep(r'''#ifndef BC5_LEAN
	if (f4p439_on()) { // exp 0439 (tag f4p439 step 3): the writer's pieces from the job table''', r'''#ifndef BC5_LEAN
	{ // exp 0439 (tag f4off439): BC5_0439_F4_OFF=1 with mode 2: no F4 dependency
		static const bool f4_off = [] {
			const char* e = std::getenv("BC5_0439_F4_OFF");
			const char* m = std::getenv("BC5_0439_PIECE_WAITS");
			const bool  b = e != nullptr && e[0] == '1' && e[1] == 0 && m != nullptr && m[0] == '2' && m[1] == 0;
			std::fprintf(stderr, "[bc5] exp 0439 (tag f4off439): ho430 F4 %s\n", b ? "OFF (BC5_0439_F4_OFF=1, PIECE_WAITS=2): no whole-job dependency is added" : "as built");
			return b;
		}();
		if (f4_off) {
			static std::atomic<uint64_t> n {0};
			const uint64_t               k = n++;
			if (k < 64 || (k & 0xfffu) == 0) journal("f4off439: %s wait at %u on 0x%" PRIx64 " (satisfied) with a pending write from job %" PRIu64 " on ring %d: no dependency added (%" PRIu64 " so far)\n", kind, off, label, others.front().second, others.front().first, k + 1);
			return;
		}
	}
	if (f4p439_on()) { // exp 0439 (tag f4p439 step 3): the writer's pieces from the job table''')

# exp 0439 (tag nm439, after vf of 11-23 22:50; a private test arm, normal build only): BC5_0439_NO_MERGE=1 skips the
# direct-memory BO merge pass (exp 0022/0169: neighbouring imports replaced by one merged import, every mapping on them
# unmapped and mapped again). In vf a merge re-cut 0x1006c00000 (0x7200000 -> 0x7400000) 2.6 ms after the GFX dcb's
# submit; the kernel's page-table clear for that unmap waited for the GFX job and held every later submit. Without
# merges an import is only ever added (MAP), at the cost of more, smaller BOs in each submission's list (the reason the
# merge exists: exp 0022). Counted once at start on stderr.
rep(r'''	if (now - S.merge_ns > 250'000'000ull) {''', r'''	static const bool nm439 = [] { // exp 0439 (tag nm439)
		const char* e = std::getenv("BC5_0439_NO_MERGE");
		const bool  b = e != nullptr && e[0] == '1' && e[1] == 0;
		std::fprintf(stderr, "[bc5] exp 0439 (tag nm439): direct-memory BO merges %s\n", b ? "OFF (BC5_0439_NO_MERGE=1): imports are only added" : "as built");
		return b;
	}();
	if (!nm439 && now - S.merge_ns > 250'000'000ull) {''')

# exp 0439 (tag rb439 v3, after vs of 11-23 23:07): BC5_0439_RING_BIND=3. As v2, but a queue whose own ring now holds
# another queue's job with an unmet wait is held (on the host, at most 50 ms) until its own jobs in flight are done,
# then placed on a ring without a waiter; at the bound it stays behind its own jobs, journaled. In vs queue 24's acb that
# GFX waited for sat on ring 1 behind queue 0's waiting acb, which v2 had put on ring 1 while ring 1 held only queue
# 24's jobs: five busy guest queues on four libdrm rings.
rep(r'''		const char* e = std::getenv("BC5_0439_RING_BIND");
		const bool  b = e != nullptr && e[0] == '2' && e[1] == 0;''', r'''		const char* e = std::getenv("BC5_0439_RING_BIND");
		const bool  b = e != nullptr && (e[0] == '2' || e[0] == '3') && e[1] == 0;''')
rep(r'''		uint32_t inflight[bc5::direct::kComputeRings] = {}, waiters[bc5::direct::kComputeRings] = {};
		int      own = -1;
		{
			std::lock_guard lk(g_rr_mu);
			for (const Rr439Job& j: g_rr_jobs) {
				if (j.id == 0 || j.done || j.ring < 0 || j.ring >= rings) continue;
				if (j.queue == queue) own = j.ring;
				inflight[j.ring]++;
				uint64_t l = 0;
				if (rr439_open_wait(j, &l)) waiters[j.ring]++;
			}
		}
		if (own >= 0) { g_rb_kept++; pick = own; break; } // the queue's order: behind its own jobs''', r'''		uint32_t inflight[bc5::direct::kComputeRings] = {}, waiters[bc5::direct::kComputeRings] = {}, other_waiters[bc5::direct::kComputeRings] = {};
		int      own = -1;
		{
			std::lock_guard lk(g_rr_mu);
			for (const Rr439Job& j: g_rr_jobs) {
				if (j.id == 0 || j.done || j.ring < 0 || j.ring >= rings) continue;
				if (j.queue == queue) own = j.ring;
				inflight[j.ring]++;
				uint64_t l = 0;
				if (rr439_open_wait(j, &l)) {
					waiters[j.ring]++;
					if (j.queue != queue) other_waiters[j.ring]++;
				}
			}
		}
		static const bool v3 = [] { const char* e = std::getenv("BC5_0439_RING_BIND"); return e != nullptr && e[0] == '3' && e[1] == 0; }();
		if (own >= 0 && v3 && other_waiters[own] != 0) { // v3: not behind another queue's waiter; wait for our own jobs
			if (!held) { held = true; g_rb_holds++; }
			if (SoftCp::now_ns() - t0 < 50'000'000ull) { std::this_thread::sleep_for(std::chrono::microseconds(20)); continue; }
			const uint64_t b = ++g_rb_bounds;
			if (b <= 64 || b % 1000 == 0) journal("rb439 v3: queue %d stays on ring %d behind another queue's waiter at the 50 ms bound (its own jobs still in flight; %" PRIu64 " such)\n", queue, own, b);
		}
		if (own >= 0) { g_rb_kept++; pick = own; break; } // the queue's order: behind its own jobs''')

open(dst, 'wb').write(s.encode('utf-8', 'surrogateescape'))
print('mksr439c: wrote', dst)
