// BC5 experiment 0438 (tag e438, build 12): e438_maps (second form: diff of the view tuples, local lazy updates,
// retried failed maps) against the full rebuild, on random view and BO lists, both DStates; no full rebuild may happen
// after the first one. Based on test_e438.cpp (build 11).
// The pieces cut from the unit by test_e438.sh: e438_types.inc (DView..DState), e438_ns.inc (DViews + namespace e438),
// e438_k1r.inc (namespace k1r412), e438_kl.inc (namespace kl412), e438_maps.inc (e438_g412_any's declaration ..
// e438_maps). Everything else is a stand-in here. Checked after every step:
//   S.maps == the full rebuild's list (the views' own mappings + k1r412 covers, lazy views without written chunks),
//   the fake device holds exactly S.maps, and no map/unmap went to an address that does not match.
#include <algorithm>
#include <atomic>
#include <cinttypes>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <map>
#include <memory>
#include <mutex>
#include <random>
#include <set>
#include <string>
#include <vector>

static double g_now_s = 0;
static double timing_now() { return g_now_s; }
static uint64_t g_now_ns = 1;
namespace SoftCp {
inline uint64_t now_ns() { return g_now_ns; }
}
static void journal(const char*, ...) {}
#define BC5_DIAG_ENV(x) std::getenv(x)
constexpr uint64_t kDChunk = 2ull << 20u;
#include "e438_types.inc"
#include "e438_ns.inc"
// the fake device
static int g_fail = 0;
#define CHECK(c, ...)                                                       \
	do {                                                                    \
		if (!(c)) {                                                         \
			std::printf("FAIL %s:%d: ", __FILE__, __LINE__);               \
			std::printf(__VA_ARGS__);                                       \
			std::printf("\n");                                              \
			if (++g_fail > 10) std::exit(1);                                \
		}                                                                   \
	} while (0)
#include <random>
static std::mt19937_64 rng_dev(4381);
struct FakeDev {
	std::map<uint64_t, DMap> m;
	uint64_t                 maps = 0, unmaps = 0;
	int  fail_pct = 0; // a map fails at this rate (the retry path)
	bool map_shared(uint32_t id, uint64_t bo_off, uint64_t size, uint64_t va, bool = false) {
		if (fail_pct != 0 && static_cast<int>(rng_dev() % 100) < fail_pct) return false;
		auto it = m.lower_bound(va);
		CHECK(it == m.end() || it->first >= va + size, "map over an existing mapping at 0x%" PRIx64, va);
		if (it != m.begin()) {
			auto p = std::prev(it);
			CHECK(p->first + p->second.size <= va, "map under an existing mapping at 0x%" PRIx64, va);
		}
		m[va] = {va, size, bo_off, id};
		maps++;
		return true;
	}
	void unmap_shared(uint64_t va) {
		CHECK(m.erase(va) == 1, "unmap of no mapping at 0x%" PRIx64, va);
		unmaps++;
	}
};
static std::unique_ptr<FakeDev> g_dev = std::make_unique<FakeDev>();
// stand-ins for what e438_maps reads
struct ZSet {
	bool empty() const { return true; }
};
static ZSet                                        g_zskip;
static std::vector<std::pair<uint64_t, uint64_t>>  g_scratch;
static void                                        scratch_release(uint64_t, uint64_t) {}
static std::map<uint64_t, int>                     g_zpieces;
static void                                        zskip_release(uint64_t, uint64_t) {}
static bool                                        guard0412_cap_changed(const DState&) { return false; }
namespace kc412 {
inline bool on() { return false; }
} // namespace kc412
#include "e438_k1r.inc"
#include "e438_kl.inc"
static uint32_t     g_k1r_id = 0xfffffff0u; // above every BO id the test hands out
static uint32_t     k1r412_bo() { return g_k1r_id; }
static bool         k1r412_map(const DMap& w) { return g_dev->map_shared(w.id, w.bo_off, w.size, w.va, w.id == g_k1r_id); }
static kl412::Known g_kl412;
// the title's writes into lazy views' chunks (the truth SEEK_DATA would see), with the time of the write
static std::map<uint64_t, uint64_t> g_truth;
static std::map<std::pair<uint64_t, uint64_t>, uint64_t> cover_since; // a zero cover (va, chunk) -> when it was first seen in S.maps
static bool                         e438_has_data(int, uint64_t choff) { return g_truth.count(choff) != 0; }
#include "e438_maps.inc"
static bool e438_g412_any() { return false; }

// the full rebuild, as direct_sync_one's old path makes the list (views' own, k1r412_want's covers; no scan)
static std::vector<DMap> full_want(const DState& S, const std::vector<DView>& views) {
	const bool covers = S.kind == 0;
	std::vector<DMap> want;
	for (const auto& v: views) {
		const uint64_t vend = v.off + v.size;
		auto           it   = std::upper_bound(S.bos.begin(), S.bos.end(), v.off, [](uint64_t o, const DBo& b) { return o < b.off; });
		if (it != S.bos.begin()) --it;
		for (; it != S.bos.end() && it->off < vend; ++it) {
			const uint64_t lo = it->off > v.off ? it->off : v.off;
			const uint64_t hi = it->off + it->size < vend ? it->off + it->size : vend;
			if (lo >= hi) continue;
			want.push_back({v.va + (lo - v.off), hi - lo, lo - it->off, it->id});
		}
	}
	std::vector<k1r412::Bo> bos;
	for (const auto& b: S.bos) bos.push_back({b.off, b.size});
	std::vector<k1r412::Piece> pieces;
	for (const auto& v: views) {
		if (!covers) break;
		pieces.clear();
		k1r412::cover(v.va, v.off, v.size, bos, kDChunk, pieces);
		if (v.lazy) kl412::drop_written(pieces, v.va, v.off, kDChunk, g_kl412, false, [](uint64_t) { return false; });
		for (const auto& p: pieces) want.push_back({p.va, p.size, 0, g_k1r_id});
	}
	std::sort(want.begin(), want.end(), [](const DMap& a, const DMap& b) { return a.va < b.va; });
	return want;
}

static void sign(DViews& d) {
	uint64_t sig = 1469598103934665603ull;
	d.sorted     = true;
	for (size_t i = 0; i < d.v.size(); i++) {
		const auto& v = d.v[i];
		for (const uint64_t x: {v.va, v.size, v.off}) sig = (sig ^ x) * 1099511628211ull;
		if (i > 0 && d.v[i - 1].va + d.v[i - 1].size > v.va) d.sorted = false;
	}
	d.sig = sig;
}
static std::mt19937_64 rng(438);
static uint64_t        rnd(uint64_t n) { return n == 0 ? 0 : rng() % n; }
constexpr uint64_t     kPage = 4096, kFile = 64 * kDChunk, kSpace = 1ull << 32u;
static uint32_t        g_next_id = 1;

// a random view list: disjoint in va, rising, offsets anywhere in the file (aliases allowed)
static std::vector<DView> rand_views(int n) {
	std::vector<DView> v;
	uint64_t           va = 0x100000000ull;
	for (int i = 0; i < n; i++) {
		va += kPage * (1 + rnd(512));
		const uint64_t size = kPage * (1 + rnd(1024));
		const uint64_t off  = kPage * rnd((kFile - size) / kPage);
		v.push_back({va, size, off, "v", rnd(5) == 0, false});
		va += size;
	}
	return v;
}
static std::vector<DBo> rand_bos() {
	std::vector<DBo> b;
	for (uint64_t c = 0; c < kFile;) {
		const uint64_t n = kDChunk * (1 + rnd(4));
		if (rnd(3) != 0 && c + n <= kFile) b.push_back({c, n, g_next_id++, 0});
		c += n + kDChunk * rnd(2);
	}
	return b;
}
// one step of change on the views: some removed, resized, moved, added; returns the changed va spans
static std::vector<DView> step_views(const std::vector<DView>& old, std::vector<std::pair<uint64_t, uint64_t>>& spans) {
	std::vector<DView> nv;
	for (const auto& v: old) {
		const uint64_t r = rnd(40);
		if (r == 0) { // unmap
			spans.emplace_back(v.va, v.size);
		} else if (r == 1) { // shrink from the end
			DView w = v;
			w.size  = kPage * (1 + rnd(v.size / kPage));
			if (w.size < v.size) spans.emplace_back(w.va + w.size, v.size - w.size);
			nv.push_back(w);
		} else if (r == 2) { // remap at another offset
			DView w = v;
			w.off   = kPage * rnd((kFile - v.size) / kPage);
			spans.emplace_back(v.va, v.size);
			nv.push_back(w);
		} else if (r == 3) { // split: the middle unmapped
			const uint64_t pages = v.size / kPage;
			if (pages >= 3) {
				const uint64_t a = 1 + rnd(pages - 2), b = a + 1 + rnd(pages - a - 1);
				DView          l = v, h = v;
				l.size = a * kPage;
				h.va   = v.va + b * kPage;
				h.off  = v.off + b * kPage;
				h.size = v.size - b * kPage;
				spans.emplace_back(v.va + a * kPage, (b - a) * kPage);
				nv.push_back(l);
				nv.push_back(h);
			} else {
				nv.push_back(v);
			}
		} else if (r == 4) { // protect: same view, a span over it
			spans.emplace_back(v.va, v.size);
			nv.push_back(v);
		} else {
			nv.push_back(v);
		}
	}
	// a few new views in the gaps
	std::vector<DView> add;
	for (size_t i = 0; i + 1 < nv.size(); i++) {
		const uint64_t gap_lo = nv[i].va + nv[i].size, gap_hi = nv[i + 1].va;
		if (gap_hi - gap_lo >= 2 * kPage && rnd(30) == 0) {
			const uint64_t size = kPage * (1 + rnd((gap_hi - gap_lo) / kPage - 1));
			const uint64_t va   = gap_lo + kPage * rnd((gap_hi - gap_lo - size) / kPage + 1);
			add.push_back({va, size, kPage * rnd((kFile - size) / kPage), "n", rnd(5) == 0, false});
			spans.emplace_back(va, size);
		}
	}
	nv.insert(nv.end(), add.begin(), add.end());
	std::sort(nv.begin(), nv.end(), [](const DView& a, const DView& b) { return a.va < b.va; });
	return nv;
}
// one step of change on the BOs: imports into holes, merges of neighbours, a retire
static void step_bos(std::vector<DBo>& b) {
	std::vector<DBo> nb;
	for (size_t i = 0; i < b.size(); i++) {
		if (i + 1 < b.size() && b[i].off + b[i].size == b[i + 1].off && rnd(10) == 0) { // merge two
			nb.push_back({b[i].off, b[i].size + b[i + 1].size, g_next_id++, 0});
			i++;
		} else if (rnd(60) == 0) { // retired (lzr-like cut)
		} else {
			nb.push_back(b[i]);
		}
	}
	// imports into holes
	std::vector<DBo> add;
	uint64_t         cur = 0;
	for (const auto& x: nb) {
		if (x.off > cur && rnd(6) == 0) add.push_back({cur, kDChunk, g_next_id++, 0});
		cur = x.off + x.size;
	}
	if (cur + kDChunk <= kFile && rnd(3) == 0) add.push_back({cur, kDChunk, g_next_id++, 0});
	nb.insert(nb.end(), add.begin(), add.end());
	std::sort(nb.begin(), nb.end(), [](const DBo& x, const DBo& y) { return x.off < y.off; });
	b.swap(nb);
}

int main() {
	uint64_t incremental = 0, refused_after_first = 0, steps = 0, total_plus = 0, lazy_checked = 0, retry_rounds = 0, diag_checked = 0;
	for (int scen = 0; scen < 80; scen++) {
		const int kind  = scen % 4 == 3 ? 1 : 0; // every fourth scenario: the private DState (no covers, no lazy rule)
		g_dev           = std::make_unique<FakeDev>();
		g_dev->fail_pct = scen % 5 == 1 ? 3 : 0; // some scenarios: maps fail now and then
		g_truth.clear();
		cover_since.clear();
		g_kl412 = kl412::Known {};
		e438::pending.clear();
		const int k = kind;
		e438::prev_v[k].clear();
		e438::prev_sig[k] = 0;
		e438::retry[k].clear();
		DState S {kind, kind == 0 ? "direct" : "private", {}, {}, {}, {}, {}};
		S.bos        = rand_bos();
		auto views_p = std::make_shared<DViews>();
		views_p->v   = rand_views(40 + static_cast<int>(rnd(200)));
		if (kind == 1) {
			for (auto& v: views_p->v) v.lazy = false;
		}
		sign(*views_p);
		// the first build: the full list (the old rebuild), then the state direct_sync_one keeps
		const bool fail_was = g_dev->fail_pct != 0;
		g_dev->fail_pct     = 0;
		S.maps              = full_want(S, views_p->v);
		for (const auto& m: S.maps) g_dev->map_shared(m.id, m.bo_off, m.size, m.va);
		g_dev->fail_pct = fail_was ? 3 : 0;
		const auto keep = [&] {
			e438::prev_v[k].clear();
			for (const auto& v: views_p->v) e438::prev_v[k].push_back({v.va, v.size, v.off, v.lazy, v.eager});
			e438::prev_sig[k] = views_p->sig;
			e438::bos_at[k]   = S.bos;
			e438::have[k]     = true;
			e438::k1r_at[k]   = g_k1r_id;
			e438::pending.clear();
		};
		keep();
		for (int st = 0; st < 120; st++) {
			steps++;
			g_now_s = st < 10 ? 1.0 : 100.0;
			g_now_ns += 50'000'000ull;
			if (kind == 0) {
				for (const auto& v: views_p->v) {
					if (v.lazy && rnd(8) == 0) {
						const uint64_t c = (v.off + kPage * rnd(v.size / kPage)) & ~(kDChunk - 1);
						g_truth.emplace(c, g_now_ns);
					}
				}
			}
			const uint64_t what = rnd(4); // 0 views, 1 BOs, 2 both, 3 nothing (only the lazy scan may find something)
			if (what == 0 || what == 2) {
				std::vector<std::pair<uint64_t, uint64_t>> spans;
				auto nv = step_views(views_p->v, spans);
				if (kind == 1) {
					for (auto& v: nv) v.lazy = false;
				}
				std::vector<e438::Span> sp;
				e438::before(views_p->v, spans, sp);
				auto d = std::make_shared<DViews>(*views_p);
				d->v   = nv;
				e438::after(*d, sp, false);
				sign(*d);
				views_p = d;
			}
			if (what == 1 || what == 2) step_bos(S.bos);
			// as direct_sync_one: the lazy scan first, then the update; failed maps are retried at the next updates
			std::vector<uint64_t> lazy;
			if (kind == 0) lazy = e438_lazy_scan(S, *views_p, 0);
			uint32_t   mapped = 0, unmapped = 0, failed = 0;
			bool       ok     = e438_maps(S, *views_p, false, lazy, mapped, unmapped, failed);
			for (int round = 0; ok && !e438::retry[k].empty() && round < 200; round++) {
				retry_rounds++;
				uint32_t m2 = 0, u2 = 0, f2 = 0;
				ok = e438_maps(S, *views_p, false, {}, m2, u2, f2);
				mapped += m2;
			}
			CHECK(e438::retry[k].empty(), "scenario %d step %d: retries left after 200 rounds", scen, st);
			if (!ok) {
				refused_after_first++;
				CHECK(false, "scenario %d step %d: a full rebuild after the first one (why: first %" PRIu64 ", reopen %" PRIu64 ", unsorted %" PRIu64 ")", scen, st, e438::m_why[0], e438::m_why[1], e438::m_why[2]);
				for (const auto& m: S.maps) g_dev->unmap_shared(m.va);
				S.maps = full_want(S, views_p->v);
				for (const auto& m: S.maps) g_dev->map_shared(m.id, m.bo_off, m.size, m.va);
			} else {
				incremental++;
				total_plus += mapped;
			}
			keep();
			// freshness (direct only): a zero cover may sit on a written lazy chunk only until the next scan
			if (kind == 0) {
				std::map<std::pair<uint64_t, uint64_t>, uint64_t> next_since;
				for (const auto& m: S.maps) {
					if (m.id != g_k1r_id) continue;
					auto v = std::partition_point(views_p->v.begin(), views_p->v.end(), [&m](const DView& x) { return x.va + x.size <= m.va; });
					if (v == views_p->v.end() || !v->lazy || v->va > m.va) continue;
					const std::pair<uint64_t, uint64_t> key {m.va, (v->off + (m.va - v->va)) & ~(kDChunk - 1)};
					auto                                cs     = cover_since.find(key);
					const uint64_t                      since0 = cs != cover_since.end() ? cs->second : g_now_ns;
					next_since[key]                         = since0;
					auto it = g_truth.find(key.second);
					if (it == g_truth.end()) continue;
					lazy_checked++;
					const uint64_t since = std::max(it->second, since0);
					CHECK(g_now_ns - since < 150'000'000ull, "scenario %d step %d: a zero cover on lazy chunk 0x%" PRIx64 " for %.0f ms since the write or the cover", scen, st, key.second,
					      static_cast<double>(g_now_ns - since) / 1e6);
				}
				cover_since.swap(next_since);
			}
			const auto want = full_want(S, views_p->v);
			CHECK(S.maps == want, "scenario %d step %d: S.maps (%zu) differs from the full rebuild (%zu)", scen, st, S.maps.size(), want.size());
			const auto diag = e438_full_want(S, *views_p); // the unit's own diagnostic list
			diag_checked++;
			CHECK(diag == want, "scenario %d step %d: the unit's diagnostic list (%zu) differs from the test's (%zu)", scen, st, diag.size(), want.size());
			CHECK(g_dev->m.size() == S.maps.size(), "scenario %d step %d: the device holds %zu, S.maps %zu", scen, st, g_dev->m.size(), S.maps.size());
			for (const auto& m: S.maps) {
				auto it = g_dev->m.find(m.va);
				CHECK(it != g_dev->m.end() && it->second == m, "scenario %d step %d: S.maps entry 0x%" PRIx64 " not on the device", scen, st, m.va);
			}
		}
	}
	std::printf("f438 test: %" PRIu64 " steps, %" PRIu64 " incremental, %" PRIu64 " full rebuilds after the first (must be 0); maps added incrementally %" PRIu64 "; local lazy updates %" PRIu64
	            ", retry rounds %" PRIu64 "; lazy chunks out of a cover %" PRIu64 " in %" PRIu64 " scans (longest wait %.0f ms), recent-write covers seen %" PRIu64 "; diagnostic lists compared %" PRIu64 "; %s\n",
	            steps, incremental, refused_after_first, total_plus, e438::m_lazy_local, retry_rounds, e438::kl_out, e438::kl_scans, static_cast<double>(e438::kl_out_max_ns) / 1e6, lazy_checked,
	            diag_checked, g_fail == 0 ? "PASS" : "FAIL");
	return g_fail == 0 ? 0 : 1;
}
