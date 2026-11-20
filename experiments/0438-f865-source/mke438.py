#!/usr/bin/env python3
"""BC5 experiment 0438, build 11 (tag e438): the layout-change path made event-driven and incremental, plus y438's and
e438's records. On the y438 unit (mks438y.py on s438.cpp).

Usage: mke438.py IN.cpp OUT.cpp   (IN: y438.cpp, md5 7e338e9f...)

Switches:
  BC5_0438_LAYOUT     e438, behaviour (lean too): on unless "0".
  BC5_0438_MERGESCAN  s438, dropped after result 10: now OFF unless "1" (the code stays, for the record).

The design is in README.md, section "Build 11". In short:
- Views (12.8 s per 420 s in result 10): the direct-memory view list is kept from the range table's change records
  (exp 0415's mr415 path, mode "views"), not rebuilt from all ~11,600 ranges at every change. A full build still
  runs every 2 s as a check (mr415's own period) and whenever the record log reports a gap.
- Mappings (16.1 s per 420 s): a change updates only the GPU mappings of the views it touched. The touched address
  intervals come from (a) the change records' spans, (b) the imported BOs that differ from those the mappings were
  made with (imports, merges), mapped back to the views that show them. Inside those intervals the wanted mappings
  (views' own, and k1r412's read-only zero covers) are computed as the old rebuild does, old mappings that are not
  wanted are unmapped, missing ones mapped. Everything else keeps its mappings.
- A full rebuild (today's code) stays for: the first rebuild and a device reopen (no mappings yet, or a new zero
  buffer), a record-log gap or a mismatch of the kept list, a list that is not sorted, zskip (g_zskip or a new zero
  list), the guard cap (g412), the cover log (kc412), a failed map in an earlier incremental pass, and every 2 s per
  DState as a check (its changes are counted: an incremental pass that left a stale or missing mapping shows here).
- Under lazy views the zero covers use kl412's known-written set without a new SEEK_DATA scan; the scan runs at the
  2-s full rebuild (today: at a rebuild at least 100 ms after the last scan).
- Locks: everything above runs where it runs today. direct_views' mutex for the kept list and the records; the
  pending spans have their own mutex (e438::mu); the mappings and S.* under g_dev_mutex.
"""
import hashlib
import sys

IN, OUT = sys.argv[1], sys.argv[2]
src = open(IN, 'rb').read()
assert hashlib.md5(src).hexdigest() == '7e338e9fa2ae7bfbd0d07d3da25ce594', 'not y438.cpp (mks438y on s438)'
s = src.decode('utf-8')


def rep(old, new, count=1):
    global s
    n = s.count(old)
    assert n == count, (n, old[:120])
    s = s.replace(old, new)


# 0. s438 dropped: off unless "1"
rep('''		const char* e = std::getenv("BC5_0438_MERGESCAN");
		return !(e != nullptr && e[0] == '0' && e[1] == 0);''', '''		const char* e = std::getenv("BC5_0438_MERGESCAN"); // exp 0438 build 11: s438 dropped (result 10), off unless "1"
		return e != nullptr && e[0] == '1' && e[1] == 0;''')

# 1. DViews carries the record sequence it was made at; the e438 namespace (records, pending spans)
rep('''struct DViews {
	std::vector<DView> v;
	uint64_t           sig = 0;
	bool               sorted = true;
};''', '''struct DViews {
	std::vector<DView> v;
	uint64_t           sig = 0;
	bool               sorted = true;
	uint64_t           e438_seq = 0; // exp 0438 (tag e438): the change-record step this list is at (0: not from records)
};
// BC5 experiment 0438 (tag e438): the layout-change path, event-driven and incremental (BC5_0438_LAYOUT, on unless "0").
namespace e438 {
inline bool on() {
	static const bool v = [] {
		const char* e = std::getenv("BC5_0438_LAYOUT");
		return !(e != nullptr && e[0] == '0' && e[1] == 0);
	}();
	return v;
}
struct Pend {
	uint64_t seq, lo, hi;
	bool     full; // the kept list may be wrong (a gap or a mismatch): the next mapping update must be a full rebuild
};
inline std::mutex        mu;      // the pending spans
inline std::vector<Pend> pending; // under mu
inline uint64_t          seq = 0; // under direct_views' mutex (the only writer)
// one span of a change: the views it overlapped before and after
struct Tup {
	uint64_t va, size, off;
	bool     lazy, eager;
	bool     operator==(const Tup& o) const { return va == o.va && size == o.size && off == o.off && lazy == o.lazy && eager == o.eager; }
};
struct Span {
	uint64_t         lo, hi;
	std::vector<Tup> old_v;
};
// records: [phase 0 load (< 60 s) / 1 play][class 0 map, 1 unmap, 2 remap, 3 same (protect or name), 4 other (no direct view)]
inline std::atomic<uint64_t> r_n[2][5], r_bytes[2][5], r_size[2][4]; // r_size: map/unmap/remap spans < 64 KiB, < 2 MiB, < 64 MiB, more
inline std::atomic<uint64_t> r_gaps {0}, r_mismatch {0};
inline int phase() { return timing_now() < 60.0 ? 0 : 1; }
inline void overlapping(const std::vector<DView>& v, uint64_t lo, uint64_t hi, std::vector<Tup>& out) {
	out.clear();
	auto it = std::partition_point(v.begin(), v.end(), [lo](const DView& x) { return x.va + x.size <= lo; });
	for (; it != v.end() && it->va < hi; ++it) out.push_back({it->va, it->size, it->off, it->lazy, it->eager});
}
inline uint64_t span_end(uint64_t start, uint64_t size) { return size > ~0ull - start ? ~0ull : start + size; }
inline void before(const std::vector<DView>& kept, const std::vector<std::pair<uint64_t, uint64_t>>& spans, std::vector<Span>& out) {
	out.resize(spans.size());
	for (size_t i = 0; i < spans.size(); i++) {
		out[i].lo = spans[i].first;
		out[i].hi = span_end(spans[i].first, spans[i].second);
		overlapping(kept, out[i].lo, out[i].hi, out[i].old_v);
	}
}
// after the records were applied to d: classify, queue the changed spans, give d its step
inline void after(DViews& d, const std::vector<Span>& sp, bool full) {
	const uint64_t   s = ++seq;
	const int        ph = phase();
	std::vector<Tup> nv;
	std::vector<Pend> add;
	for (const auto& x: sp) {
		overlapping(d.v, x.lo, x.hi, nv);
		int c = 4;
		if (x.old_v.empty() && !nv.empty()) c = 0;
		else if (!x.old_v.empty() && nv.empty()) c = 1;
		else if (!x.old_v.empty()) c = x.old_v == nv ? 3 : 2;
		const uint64_t b = x.hi - x.lo;
		r_n[ph][c]++;
		r_bytes[ph][c] += b;
		if (c <= 2) {
			r_size[ph][b < (64ull << 10u) ? 0 : b < (2ull << 20u) ? 1 : b < (64ull << 20u) ? 2 : 3]++;
			add.push_back({s, x.lo, x.hi, false});
		}
	}
	if (full) add.push_back({s, 0, 0, true});
	d.e438_seq = s;
	std::lock_guard l(mu);
	pending.insert(pending.end(), add.begin(), add.end());
}
inline void mark_full(DViews& d) {
	const uint64_t s = ++seq;
	d.e438_seq       = s;
	std::lock_guard l(mu);
	pending.push_back({s, 0, 0, true});
}
// the mapping side (under g_dev_mutex): per DState kind, what the mappings were made from
inline std::vector<DBo> bos_at[2];
inline bool             have[2]       = {false, false};
inline bool             force_full[2] = {false, false};
inline uint64_t         seq_at[2]     = {0, 0};
inline uint32_t         k1r_at[2]     = {0, 0};
inline uint64_t         check_ns[2]   = {0, 0};
// counters (under g_dev_mutex)
inline uint64_t m_inc = 0, m_full = 0, m_check = 0, m_check_plus = 0, m_check_minus = 0, m_intervals = 0, m_views = 0, m_plus = 0, m_minus = 0, m_inc_ns = 0, m_full_ns = 0;
inline uint64_t m_why[12] = {};
// chunks of lazy views taken out of a zero cover (found written by a kl412 scan), both paths: count, and the time
// since the scan before (how long each can have sat under the cover), sum and longest (under g_dev_mutex)
inline uint64_t kl_out = 0, kl_out_ns = 0, kl_out_max_ns = 0, kl_scans = 0;
inline void kl_note(const std::set<uint64_t>& before, const std::set<uint64_t>& after, uint64_t prev_ns, uint64_t now_ns) {
	kl_scans++;
	const uint64_t dt = prev_ns != 0 && now_ns > prev_ns ? now_ns - prev_ns : 0;
	for (const uint64_t c: after) {
		if (before.count(c) != 0) continue;
		kl_out++;
		kl_out_ns += dt;
		if (dt > kl_out_max_ns) kl_out_max_ns = dt;
	}
}
} // namespace e438''')

# 1b. the kl412 scan's note on today's path (k1r412_want)
rep('''	uint64_t            kl_dropped = 0;
	const uint64_t      kl_t0      = SoftCp::now_ns();
	const bool          kl_scan    = kl.begin(kl_t0, kl412::kPeriodNs);''', '''	uint64_t            kl_dropped = 0;
	const uint64_t      kl_t0      = SoftCp::now_ns();
	const bool          e438_due   = !kl.scanned || kl_t0 - kl.last_ns >= kl412::kPeriodNs; // exp 0438 (tag e438): the note below
	const uint64_t      e438_prev  = kl.last_ns;
	std::set<uint64_t>  e438_before;
	if (e438_due) e438_before = kl.written;
	const bool          kl_scan    = kl.begin(kl_t0, kl412::kPeriodNs);''')
rep('''	if (kl_scan) kl.scan_ns += now - kl_t0; // exp 0412 (tag kl412): a rebuild's cover pass with its scan''', '''	if (kl_scan) kl.scan_ns += now - kl_t0; // exp 0412 (tag kl412): a rebuild's cover pass with its scan
	if (kl_scan) e438::kl_note(e438_before, kl.written, e438_prev, kl_t0); // exp 0438 (tag e438)''')
#

# 2. mr415 "views" mode under e438; the old builder's second list left out under e438
rep('''		if (d432::views_kept()) return 2; // exp 0432 (tag v432): BC5_DIRECT_VIEWS_KEPT''', '''		if (d432::views_kept()) return 2; // exp 0432 (tag v432): BC5_DIRECT_VIEWS_KEPT
		if (e438::on()) return 2;         // exp 0438 (tag e438): the view list kept from the change records''')
rep('''g2 == gen && !d432::views_kept()) { // exp 0432''', '''g2 == gen && !d432::views_kept() && !e438::on()) { // exp 0438 (e438): not under e438; exp 0432''')

# 3. the in-place path: classify and queue
rep('''			std::vector<DView>& kept = kept_p->v;
			for (size_t i = 0; i < spans.size(); i++) bc5::map_records::apply(kept, lists[i], spans[i].first, bc5::map_records::end_of(spans[i].first, spans[i].second), make);
			bc5::load_stat::count(bc5::load_stat::kMapRecord, spans.size());
			*gen_out = gen;
			return kept_p;''', '''			std::vector<DView>&     kept = kept_p->v;
			std::vector<e438::Span> e438_sp; // exp 0438 (tag e438)
			if (e438::on()) e438::before(kept, spans, e438_sp);
			for (size_t i = 0; i < spans.size(); i++) bc5::map_records::apply(kept, lists[i], spans[i].first, bc5::map_records::end_of(spans[i].first, spans[i].second), make);
			if (e438::on()) e438::after(*kept_p, e438_sp, false);
			bc5::load_stat::count(bc5::load_stat::kMapRecord, spans.size());
			*gen_out = gen;
			return kept_p;''')
rep('''		bc5::load_stat::count(bc5::load_stat::kRecOverflow);
		have = false; // the log had a gap: the kept list is not to be compared, only replaced''', '''		bc5::load_stat::count(bc5::load_stat::kRecOverflow);
		if (e438::on()) e438::r_gaps++; // exp 0438 (tag e438): the full build below marks the mappings for a full rebuild
		have = false; // the log had a gap: the kept list is not to be compared, only replaced''')

# 4. the full (check) path
rep('''	static int logged = 0;
	if (have && complete) {
		if (kept_p.use_count() > 1) kept_p = std::make_shared<DViews>(*kept_p);
		std::vector<DView>& kept = kept_p->v;
		for (const auto& [start, size]: spans) bc5::map_records::apply(kept, ranges, start, bc5::map_records::end_of(start, size), make);
		bc5::load_stat::count(bc5::load_stat::kMapRecord, spans.size());
		if (!same(kept, full)) {''', '''	static int logged = 0;
	bool       e438_ok = false; // exp 0438 (tag e438): the kept list, with these records, equals the full build
	std::vector<e438::Span> e438_sp;
	if (have && complete) {
		if (kept_p.use_count() > 1) kept_p = std::make_shared<DViews>(*kept_p);
		std::vector<DView>& kept = kept_p->v;
		if (e438::on()) e438::before(kept, spans, e438_sp);
		for (const auto& [start, size]: spans) bc5::map_records::apply(kept, ranges, start, bc5::map_records::end_of(start, size), make);
		bc5::load_stat::count(bc5::load_stat::kMapRecord, spans.size());
		e438_ok = same(kept, full);
		if (e438::on() && !e438_ok) e438::r_mismatch++;
		if (!same(kept, full)) {''')
rep('''	kept_p     = std::make_shared<DViews>();
	kept_p->v  = std::move(full);
	have       = true;
	checked_ns = now;
	*gen_out   = gen;
	return kept_p;''', '''	kept_p     = std::make_shared<DViews>();
	kept_p->v  = std::move(full);
	if (e438::on()) { // exp 0438 (tag e438): the same list as the records made: its spans; otherwise a full rebuild
		if (e438_ok) e438::after(*kept_p, e438_sp, false);
		else e438::mark_full(*kept_p);
	}
	have       = true;
	checked_ns = now;
	*gen_out   = gen;
	return kept_p;''')

# 5. kl412's known-written set at file scope (the incremental covers read it without a scan)
rep('''	static kl412::Known kl; // exp 0412 (tag kl412)''', '''	kl412::Known&       kl = g_kl412; // exp 0412 (tag kl412); exp 0438 (e438): at file scope''')
rep('''static void k1r412_want(const DState& S, const std::vector<DView>& views, std::vector<DMap>& want, int fd) { // exp 0412 (tag kl412): fd, the direct file''',
    '''static kl412::Known g_kl412; // exp 0438 (tag e438): k1r412_want's known-written set, read by e438_maps without a scan
static void k1r412_want(const DState& S, const std::vector<DView>& views, std::vector<DMap>& want, int fd) { // exp 0412 (tag kl412): fd, the direct file''')

# 6. the incremental mapping update, before s438's namespace (before direct_sync_one)
rep('''// BC5 experiment 0438 (tag s438): direct_sync's scan left out on a merge-only pass''', '''// BC5 experiment 0438 (tag e438): the mapping update for the touched intervals only. Under g_dev_mutex. False: the caller
// rebuilds the old way (m_why says why).
static bool e438_has_data(int fd, uint64_t choff) { // exp 0438 (tag e438): kl412's question, as k1r412_want asks it
	const off_t d = lseek(fd, static_cast<off_t>(choff), SEEK_DATA);
	return d >= 0 && static_cast<uint64_t>(d) < choff + kDChunk;
}
static bool e438_g412_any(); // defined after g_g412_off
// The lazy views' zero covers at today's freshness: when kl412's scan is due (100 ms, as k1r412_want), the chunks under
// the lazy views' covers are asked again (SEEK_DATA). True when the known-written set changed: the caller rebuilds the old
// way (whose k1r412_want then finds the scan done and uses the fresh set).
static bool e438_lazy_scan(const DState& S, const DViews& V, int fd) {
	const uint64_t now = SoftCp::now_ns();
	if (g_kl412.scanned && now - g_kl412.last_ns < kl412::kPeriodNs) return false;
	bool any_lazy = false;
	for (const auto& v: V.v) any_lazy = any_lazy || v.lazy;
	if (!any_lazy) return false;
	const uint64_t                    prev   = g_kl412.last_ns;
	const std::set<uint64_t>          before = g_kl412.written;
	static std::vector<k1r412::Bo>    sbos;
	static std::vector<k1r412::Piece> spieces;
	sbos.clear();
	for (const auto& b: S.bos) sbos.push_back({b.off, b.size});
	g_kl412.begin(now, kl412::kPeriodNs);
	for (const auto& v: V.v) {
		if (!v.lazy) continue;
		spieces.clear();
		k1r412::cover(v.va, v.off, v.size, sbos, kDChunk, spieces);
		kl412::drop_written(spieces, v.va, v.off, kDChunk, g_kl412, true, [fd](uint64_t choff) { return e438_has_data(fd, choff); });
	}
	g_kl412.scan_ns += SoftCp::now_ns() - now;
	e438::kl_note(before, g_kl412.written, prev, now);
	return g_kl412.written != before;
}
static bool e438_maps(DState& S, const DViews& V, bool zskip_new, int fd, uint32_t& mapped, uint32_t& unmapped, uint32_t& map_failed) {
	using IV       = std::pair<uint64_t, uint64_t>;
	const int k    = S.kind == 0 ? 0 : 1;
	int       why  = -1;
	bool      pend_full = false;
	std::vector<IV> D;
	{
		std::lock_guard l(e438::mu);
		for (const auto& p: e438::pending) {
			if (p.seq > V.e438_seq || p.seq <= e438::seq_at[k]) continue;
			if (p.full) pend_full = true;
			else D.emplace_back(p.lo, p.hi);
		}
	}
	if (S.kind != 0) why = 0;
	else if (V.e438_seq == 0) why = 1;                           // the list did not come from the records
	else if (pend_full || e438::force_full[k]) why = 2;          // a gap, a mismatch or a failed map
	else if (!V.sorted) why = 3;
	else if (!g_zskip.empty() || zskip_new) why = 4;
	else if (e438_g412_any() || guard0412_cap_changed(S)) why = 5;
	else if (kc412::on()) why = 6;
	else if (!e438::have[k] || S.maps.empty()) why = 7;          // the first rebuild, or after a reopen
	else if (k1r412::on() && g_k1r_id != e438::k1r_at[k]) why = 8; // a new zero buffer (reopen)
	else if (e438::seq_at[k] > V.e438_seq) why = 9;
	if (why < 0 && k1r412::on() && e438_lazy_scan(S, V, fd)) why = 11; // a lazy chunk was written (or freed): the old rebuild
	if (why >= 0) {
		e438::m_why[why]++;
		return false;
	}
	const uint64_t t0   = SoftCp::now_ns();
	const auto     norm = [](std::vector<IV>& x) { // sorted, touching and overlapping intervals joined
		std::sort(x.begin(), x.end());
		size_t w = 0;
		for (size_t r = 0; r < x.size(); r++) {
			if (w > 0 && x[r].first <= x[w - 1].second) x[w - 1].second = std::max(x[w - 1].second, x[r].second);
			else x[w++] = x[r];
		}
		x.resize(w);
	};
	// (b) the BOs that differ from those the mappings were made with, as file intervals -> the views that show them
	{
		std::vector<IV> F;
		const auto&     ob = e438::bos_at[k];
		size_t          i = 0, j = 0;
		while (i < ob.size() || j < S.bos.size()) {
			if (i < ob.size() && j < S.bos.size() && ob[i].off == S.bos[j].off && ob[i].size == S.bos[j].size && ob[i].id == S.bos[j].id) {
				i++;
				j++;
			} else if (j >= S.bos.size() || (i < ob.size() && ob[i].off < S.bos[j].off)) {
				F.emplace_back(ob[i].off, ob[i].off + ob[i].size);
				i++;
			} else if (i >= ob.size() || S.bos[j].off < ob[i].off) {
				F.emplace_back(S.bos[j].off, S.bos[j].off + S.bos[j].size);
				j++;
			} else {
				F.emplace_back(ob[i].off, std::max(ob[i].off + ob[i].size, S.bos[j].off + S.bos[j].size));
				i++;
				j++;
			}
		}
		if (!F.empty()) {
			norm(F); // disjoint and rising: the ends rise too
			for (const auto& v: V.v) { // the views are not sorted by file offset: every one is looked at
				const uint64_t ve = v.off + v.size;
				auto           f  = std::partition_point(F.begin(), F.end(), [&v](const IV& x) { return x.second <= v.off; });
				if (f != F.end() && f->first < ve) D.emplace_back(v.va, v.va + v.size);
			}
		}
	}
	norm(D);
	if (D.empty()) { // nothing touched (a change was undone, or only BO ids of no view changed)
		e438::m_inc++;
		e438::m_inc_ns += SoftCp::now_ns() - t0;
		return true;
	}
	// the intervals grown to whole old mappings and whole new views, until they stop growing
	for (int round = 0; round < 16; round++) {
		std::vector<IV> add;
		for (const auto& [lo, hi]: D) {
			auto m = std::partition_point(S.maps.begin(), S.maps.end(), [lo](const DMap& x) { return x.va + x.size <= lo; });
			for (; m != S.maps.end() && m->va < hi; ++m) {
				if (m->va < lo || m->va + m->size > hi) add.emplace_back(m->va, m->va + m->size);
			}
			auto v = std::partition_point(V.v.begin(), V.v.end(), [lo](const DView& x) { return x.va + x.size <= lo; });
			for (; v != V.v.end() && v->va < hi; ++v) {
				if (v->va < lo || v->va + v->size > hi) add.emplace_back(v->va, v->va + v->size);
			}
		}
		if (add.empty()) break;
		D.insert(D.end(), add.begin(), add.end());
		norm(D);
		if (round == 15) {
			e438::m_why[10]++;
			return false;
		}
	}
	// the wanted mappings inside D, as the old rebuild makes them: the views' own, then k1r412's covers
	std::vector<DMap>                 want;
	static std::vector<k1r412::Bo>    kbos;
	static std::vector<k1r412::Piece> pieces;
	const uint32_t                    kid = k1r412::on() ? k1r412_bo() : 0;
	if (kid != 0) {
		kbos.clear();
		for (const auto& b: S.bos) kbos.push_back({b.off, b.size});
	}
	uint64_t nviews = 0;
	for (const auto& [lo, hi]: D) {
		auto v = std::partition_point(V.v.begin(), V.v.end(), [lo](const DView& x) { return x.va + x.size <= lo; });
		for (; v != V.v.end() && v->va < hi; ++v) {
			nviews++;
			const uint64_t vend = v->off + v->size;
			auto           it   = std::upper_bound(S.bos.begin(), S.bos.end(), v->off, [](uint64_t o, const DBo& b) { return o < b.off; });
			if (it != S.bos.begin()) --it;
			for (; it != S.bos.end() && it->off < vend; ++it) {
				const uint64_t a = it->off > v->off ? it->off : v->off;
				const uint64_t b = it->off + it->size < vend ? it->off + it->size : vend;
				if (a >= b) continue;
				want.push_back({v->va + (a - v->off), b - a, a - it->off, it->id});
			}
			if (kid != 0) {
				pieces.clear();
				k1r412::cover(v->va, v->off, v->size, kbos, kDChunk, pieces);
				if (v->lazy) kl412::drop_written(pieces, v->va, v->off, kDChunk, g_kl412, false, [](uint64_t) { return false; }); // no scan here (the 2-s rebuild scans)
				for (const auto& p: pieces) want.push_back({p.va, p.size, 0, kid});
			}
		}
	}
	std::sort(want.begin(), want.end(), [](const DMap& a, const DMap& b) { return a.va < b.va; });
	// the splice: outside D every mapping stays; inside, the wanted ones stay, the others go, the missing ones are added
	std::vector<DMap> next, added;
	next.reserve(S.maps.size() + want.size());
	std::vector<char> have_w(want.size(), 0);
	size_t            q = 0;
	for (const auto& m: S.maps) {
		while (q < D.size() && D[q].second <= m.va) q++;
		if (q >= D.size() || m.va < D[q].first) {
			next.push_back(m);
			continue;
		}
		auto w = std::lower_bound(want.begin(), want.end(), m.va, [](const DMap& a, uint64_t va) { return a.va < va; });
		if (w != want.end() && *w == m) {
			have_w[static_cast<size_t>(w - want.begin())] = 1;
			next.push_back(m);
		} else {
			g_dev->unmap_shared(m.va);
			unmapped++;
		}
	}
	for (size_t i = 0; i < want.size(); i++) {
		if (have_w[i] != 0) continue;
		const DMap& w = want[i];
		if (!g_scratch.empty()) scratch_release(w.va, w.va + w.size);
		if (!g_zpieces.empty()) zskip_release(w.va, w.va + w.size);
		if (k1r412_map(w)) {
			added.push_back(w);
			mapped++;
		} else {
			map_failed++;
		}
	}
	if (!added.empty()) {
		std::vector<DMap> merged_maps;
		merged_maps.reserve(next.size() + added.size());
		std::merge(next.begin(), next.end(), added.begin(), added.end(), std::back_inserter(merged_maps), [](const DMap& a, const DMap& b) { return a.va < b.va; });
		next.swap(merged_maps);
	}
	S.maps.swap(next);
	e438::m_inc++;
	e438::m_intervals += D.size();
	e438::m_views += nviews;
	e438::m_plus += mapped;
	e438::m_minus += unmapped;
	e438::m_inc_ns += SoftCp::now_ns() - t0;
	return true;
}
// BC5 experiment 0438 (tag s438): direct_sync's scan left out on a merge-only pass''')

rep('''static bool                  g_g412_off_changed = false;''', '''static bool                  g_g412_off_changed = false;
static bool e438_g412_any() { return !g_g412_off.empty(); } // exp 0438 (tag e438)''')

# 7. direct_sync_one: the 2-s check enters the rebuild; e438 first; the old rebuild otherwise; the state after
rep('''	uint32_t mapped = 0, unmapped = 0, map_failed = 0;
	if (sig != S.views_sig || S.bos.size() != S.bos_mapped || !retired.empty() || guard0412_cap_changed(S)) { // exp 0412 (tag g412b)''', '''	uint32_t mapped = 0, unmapped = 0, map_failed = 0;
	const int  e438_k     = S.kind == 0 ? 0 : 1; // exp 0438 (tag e438)
	const bool e438_check = e438::on() && S.kind == 0 && now - e438::check_ns[e438_k] >= 2'000'000'000ull; // the 2-s full rebuild (the check)
	const bool e438_check_only = e438_check && !(sig != S.views_sig || S.bos.size() != S.bos_mapped || !retired.empty() || guard0412_cap_changed(S));
	bool       e438_done  = false;
	if (sig != S.views_sig || S.bos.size() != S.bos_mapped || !retired.empty() || guard0412_cap_changed(S) || e438_check) { // exp 0412 (tag g412b); exp 0438 (e438): the check
		const uint64_t e438_t0 = SoftCp::now_ns();
		if (e438_check) e438::check_ns[e438_k] = now;
		if (e438::on() && !e438_check) e438_done = e438_maps(S, *views_p, zskip_new, fd, mapped, unmapped, map_failed); // exp 0438 (tag e438)''')
rep('''		if (d432::maps_diff() != 0 && retired.empty() && S.bos.size() == S.bos_mapped''', '''		if (!e438_done && d432::maps_diff() != 0 && retired.empty() && S.bos.size() == S.bos_mapped''')
rep('''		if (!x432_done) {
		d432::g_x_full++;''', '''		if (!x432_done && !e438_done) {
		d432::g_x_full++;''')
rep('''		x432_prev[x432_k] = views_p; // exp 0432 (tag x432)''', '''		x432_prev[x432_k] = e438::on() ? nullptr : views_p; // exp 0432 (tag x432); exp 0438 (e438): not held (the kept list is changed in place when nobody holds it)
		if (e438::on()) { // exp 0438 (tag e438): what the mappings are now made from
			if (!e438_done) {
				e438::m_full++;
				e438::m_full_ns += SoftCp::now_ns() - e438_t0;
				if (e438_check) e438::m_check++;
				if (e438_check_only) {
					e438::m_check_plus += mapped;
					e438::m_check_minus += unmapped;
				}
			}
			e438::bos_at[e438_k]     = S.bos;
			e438::have[e438_k]       = true;
			e438::force_full[e438_k] = map_failed != 0;
			e438::seq_at[e438_k]     = std::max(e438::seq_at[e438_k], views_p->e438_seq);
			e438::k1r_at[e438_k]     = g_k1r_id;
			std::lock_guard l(e438::mu);
			const uint64_t  upto = e438::seq_at[e438_k];
			e438::pending.erase(std::remove_if(e438::pending.begin(), e438::pending.end(), [upto](const e438::Pend& p) { return p.seq <= upto; }), e438::pending.end());
		}''')

# 8. the 60-s lines
rep('''		for (int ph = 0; ph < 2; ph++) { // exp 0438 (tag y438)''', '''		if (e438::on() || true) { // exp 0438 (tag e438): the layout changes and the mapping updates
			const auto mib = [](uint64_t b) { return static_cast<double>(b) / 1048576.0; };
			for (int ph = 0; ph < 2; ph++) {
				journal("e438 layout (exp 0438): t %.1f s: %s: change spans map %" PRIu64 " (%.1f MiB), unmap %" PRIu64 " (%.1f MiB), remap %" PRIu64 " (%.1f MiB), same (protect/name) %" PRIu64 ", no direct view %" PRIu64
				        "; map/unmap/remap spans < 64 KiB %" PRIu64 ", < 2 MiB %" PRIu64 ", < 64 MiB %" PRIu64 ", more %" PRIu64 "\\n",
				        timing_now(), ph == 0 ? "load (t < 60 s)" : "play (t >= 60 s)", e438::r_n[ph][0].load(), mib(e438::r_bytes[ph][0].load()), e438::r_n[ph][1].load(), mib(e438::r_bytes[ph][1].load()),
				        e438::r_n[ph][2].load(), mib(e438::r_bytes[ph][2].load()), e438::r_n[ph][3].load(), e438::r_n[ph][4].load(), e438::r_size[ph][0].load(), e438::r_size[ph][1].load(),
				        e438::r_size[ph][2].load(), e438::r_size[ph][3].load());
			}
			journal("e438 (exp 0438): t %.1f s: layout %s; mapping updates incremental %" PRIu64 " (%.1f ms; %" PRIu64 " intervals, %" PRIu64 " views, maps +%" PRIu64 " -%" PRIu64 "), full %" PRIu64 " (%.1f ms), of them 2-s checks %" PRIu64
			        " (changes when nothing else changed: +%" PRIu64 " -%" PRIu64 "); full because: not direct %" PRIu64 ", list not from records %" PRIu64 ", gap/mismatch/failed map %" PRIu64 ", unsorted %" PRIu64 ", zskip %" PRIu64
			        ", g412 %" PRIu64 ", kc412 %" PRIu64 ", first %" PRIu64 ", zero buffer %" PRIu64 ", order %" PRIu64 ", no fixpoint %" PRIu64 ", lazy chunk written %" PRIu64 "; lazy chunks taken out of a zero cover %" PRIu64 " in %" PRIu64 " scans, time since the scan before %.1f ms on average, longest %.1f ms; record gaps %" PRIu64 ", kept-list mismatches %" PRIu64 ", view builds %" PRIu64
			        ", clones %" PRIu64 "\\n",
			        timing_now(), e438::on() ? "ON" : "off", e438::m_inc, static_cast<double>(e438::m_inc_ns) / 1e6, e438::m_intervals, e438::m_views, e438::m_plus, e438::m_minus, e438::m_full,
			        static_cast<double>(e438::m_full_ns) / 1e6, e438::m_check, e438::m_check_plus, e438::m_check_minus, e438::m_why[0], e438::m_why[1], e438::m_why[2], e438::m_why[3], e438::m_why[4],
			        e438::m_why[5], e438::m_why[6], e438::m_why[7], e438::m_why[8], e438::m_why[9], e438::m_why[10], e438::m_why[11], e438::kl_out, e438::kl_scans,
			        e438::kl_out != 0 ? static_cast<double>(e438::kl_out_ns) / 1e6 / static_cast<double>(e438::kl_out) : 0.0, static_cast<double>(e438::kl_out_max_ns) / 1e6, e438::r_gaps.load(), e438::r_mismatch.load(),
			        static_cast<uint64_t>(g_views_builds), static_cast<uint64_t>(d432::g_views_clone.load()));
		}
		for (int ph = 0; ph < 2; ph++) { // exp 0438 (tag y438)''')

out = s.encode('utf-8')
open(OUT, 'wb').write(out)
print('e438 unit', hashlib.md5(out).hexdigest(), len(out))
