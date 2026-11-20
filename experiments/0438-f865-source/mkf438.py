#!/usr/bin/env python3
"""BC5 experiment 0438, build 12 (tag e438, second form): the mapping index updated in place, with no full rebuild after
the first one except at a device reopen. On the build-11 unit (mke438.py's output).

Usage: mkf438.py IN.cpp OUT.cpp   (IN: e438.cpp, md5 3fe3a79a...)

The top session's order (relaying the maintainer: "a full rebuild shouldn't be needed; an update of the mapping index is
enough"):
1. A lazy chunk found written (or freed) by kl412's scan is a local update: the lazy views that show that chunk are
   recomputed (their zero cover on it goes; their mappings of an imported BO, if the chunk is imported, come), no full
   rebuild. As today, a written lazy chunk that is not imported is left unmapped (it faults by name); importing it
   would undo F394's 242 MiB.
2. Every full-rebuild reason of build 11 gets an incremental path or a proof that it cannot occur after load:
   - the touched intervals now come from a diff of the view list the mappings were made from (a copy of its
     (va, size, off, lazy, eager) tuples, per DState) against the current one, not from the change records. So a
     record gap, a kept-list mismatch, a list not made from records, the private DState and a list older than the
     mappings are all ordinary diffs;
   - a failed map is retried on its own interval at the next update (no full rebuild);
   - the growth to whole mappings and whole views runs until it stops (it only grows, inside a finite set of
     endpoints), no cap;
   - an unsorted list cannot occur: the direct views are the guest range table's ranges, disjoint by construction
     (VirtualRanges), and the private views are the address space's map; it is counted as a bug if it does;
   - zskip (BC5_DIRECT_ZERO_SKIP), the g412 cap (BC5_GUARD_CAP_ACT) and kc412 (BC5_GUARD_COVER_LOG) are environment
     switches read once at start, unset in every launcher (exp 0419 took zskip and the pin cap out of the defaults);
     they cannot turn on during play. With one of them set (a diagnostic run) the old rebuild is used, counted.
   - Left: the first build of each DState and a device reopen (a new zero buffer, or no mappings).
3. The 2-s check is a diagnostic: normal build only (#ifndef BC5_LEAN). It compares S.maps with the full list made
   the old way (views' own mappings and covers, from the same known-written set) and records any difference. It does
   not repair; a difference is a bug.
"""
import hashlib
import sys

IN, OUT = sys.argv[1], sys.argv[2]
src = open(IN, 'rb').read()
assert hashlib.md5(src).hexdigest() == '3fe3a79a459cb1ea60a7d27ff92f8c14', 'not e438.cpp (build 11)'
s = src.decode('utf-8')


def rep(old, new, count=1):
    global s
    n = s.count(old)
    assert n == count, (n, old[:120])
    s = s.replace(old, new)


def cut(start_marker, end_marker, new):
    """Replace s[start:end) where start is the first start_marker and end is the first end_marker after it."""
    global s
    assert s.count(start_marker) == 1, (s.count(start_marker), start_marker[:80])
    a = s.index(start_marker)
    b = s.index(end_marker, a)
    s = s[:a] + new + s[b:]


# 0. result 11: the view list kept from the change records cost 24.0-28.7 s per 420 s against 12.3 s for today's full
#    build (about 60 change spans per layout change). Build 12 builds the list as today; the records are not used.
rep('''		if (e438::on()) return 2;         // exp 0438 (tag e438): the view list kept from the change records''', '''		// exp 0438 (tag e438, build 12): the view list is built as today (result 11: the records were slower)''')

# 1. the mapping side's state: the view tuples the mappings were made from, the failed intervals, the counters
rep('''inline bool             force_full[2] = {false, false};''', '''inline bool             force_full[2] = {false, false}; // build 11 only
inline std::vector<Tup> prev_v[2];   // build 12: the view list S.maps was made from, as tuples
inline uint64_t         prev_sig[2] = {0, 0};
inline std::vector<std::pair<uint64_t, uint64_t>> retry[2]; // build 12: va intervals of maps that failed, retried at the next update
inline uint64_t         d_mismatch = 0, d_checks = 0, d_extra = 0, d_missing = 0, m_unsorted = 0, m_lazy_local = 0, m_retried = 0;''')

# 2. the lazy scan returns what changed; e438_maps (second form); the diagnostic's full list
cut('''// The lazy views' zero covers at today's freshness''', '''// BC5 experiment 0438 (tag s438): direct_sync's scan left out''', '''// The lazy views' zero covers at today's freshness: when kl412's scan is due (100 ms, as k1r412_want), the chunks under
// the lazy views' covers are asked again (SEEK_DATA). Build 12: returns the chunks whose written state changed (written,
// or freed), for a local update of the lazy views that show them.
static std::vector<uint64_t> e438_lazy_scan(const DState& S, const DViews& V, int fd) {
	std::vector<uint64_t> changed;
	const uint64_t        now = SoftCp::now_ns();
	if (g_kl412.scanned && now - g_kl412.last_ns < kl412::kPeriodNs) return changed;
	bool any_lazy = false;
	for (const auto& v: V.v) any_lazy = any_lazy || v.lazy;
	if (!any_lazy) return changed;
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
	std::set_symmetric_difference(before.begin(), before.end(), g_kl412.written.begin(), g_kl412.written.end(), std::back_inserter(changed));
	return changed;
}
// The wanted mappings of one view, as the old rebuild makes them: the view's own (one per BO it shows), then, for the
// direct DState with k1r412 on, the read-only zero covers of its gaps (a lazy view: not over known-written chunks).
static void e438_view_want(const DState& S, const DView& v, uint32_t kid, const std::vector<k1r412::Bo>& kbos, std::vector<DMap>& want) {
	static std::vector<k1r412::Piece> pieces;
	const uint64_t                    vend = v.off + v.size;
	auto                              it   = std::upper_bound(S.bos.begin(), S.bos.end(), v.off, [](uint64_t o, const DBo& b) { return o < b.off; });
	if (it != S.bos.begin()) --it;
	for (; it != S.bos.end() && it->off < vend; ++it) {
		const uint64_t a = it->off > v.off ? it->off : v.off;
		const uint64_t b = it->off + it->size < vend ? it->off + it->size : vend;
		if (a >= b) continue;
		want.push_back({v.va + (a - v.off), b - a, a - it->off, it->id});
	}
	if (kid == 0) return;
	pieces.clear();
	k1r412::cover(v.va, v.off, v.size, kbos, kDChunk, pieces);
	if (v.lazy) kl412::drop_written(pieces, v.va, v.off, kDChunk, g_kl412, false, [](uint64_t) { return false; });
	for (const auto& p: pieces) want.push_back({p.va, p.size, 0, kid});
}
static uint32_t e438_kid(const DState& S) { return S.kind == 0 && k1r412::on() ? k1r412_bo() : 0; }
#ifndef BC5_LEAN
// The diagnostic's full list (normal build): every view's wanted mappings, sorted.
static std::vector<DMap> e438_full_want(const DState& S, const DViews& V) {
	std::vector<DMap>       want;
	std::vector<k1r412::Bo> kbos;
	const uint32_t          kid = e438_kid(S);
	if (kid != 0) {
		for (const auto& b: S.bos) kbos.push_back({b.off, b.size});
	}
	for (const auto& v: V.v) e438_view_want(S, v, kid, kbos, want);
	std::sort(want.begin(), want.end(), [](const DMap& a, const DMap& b) { return a.va < b.va; });
	return want;
}
#endif
static bool e438_maps(DState& S, const DViews& V, bool zskip_new, const std::vector<uint64_t>& lazy_changed, uint32_t& mapped, uint32_t& unmapped, uint32_t& map_failed) {
	using IV    = std::pair<uint64_t, uint64_t>;
	const int k = S.kind == 0 ? 0 : 1;
	int       why = -1;
	if (!e438::have[k] || S.maps.empty()) why = 0;                         // the first build, or after a reopen (no mappings)
	else if (S.kind == 0 && k1r412::on() && g_k1r_id != e438::k1r_at[k]) why = 1; // a new zero buffer: a reopen
	else if (!V.sorted) {                                                  // cannot occur (the ranges are disjoint): a bug
		why = 2;
		e438::m_unsorted++;
	} else if (S.kind == 0 && (!g_zskip.empty() || zskip_new)) why = 3;   // diagnostic switches, set at start only
	else if (e438_g412_any() || guard0412_cap_changed(S)) why = 4;
	else if (kc412::on()) why = 5;
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
	std::vector<IV> D;
	// (a) the view list against the one the mappings were made from (both sorted by va)
	if (V.sig != e438::prev_sig[k] || V.v.size() != e438::prev_v[k].size()) {
		const auto& ov = e438::prev_v[k];
		const auto& nv = V.v;
		size_t      i = 0, j = 0;
		while (i < ov.size() || j < nv.size()) {
			const int ph   = e438::phase();
			const auto note = [ph](int c, uint64_t b) { // build 12: the layout statistics from the diff (0 view gone, 1 view new, 2 view changed)
				const int cls = c == 0 ? 1 : c == 1 ? 0 : 2; // as the records' classes: 0 map, 1 unmap, 2 remap
				e438::r_n[ph][cls]++;
				e438::r_bytes[ph][cls] += b;
				e438::r_size[ph][b < (64ull << 10u) ? 0 : b < (2ull << 20u) ? 1 : b < (64ull << 20u) ? 2 : 3]++;
			};
			if (i < ov.size() && j < nv.size() && ov[i] == e438::Tup {nv[j].va, nv[j].size, nv[j].off, nv[j].lazy, nv[j].eager}) {
				i++;
				j++;
			} else if (j >= nv.size() || (i < ov.size() && ov[i].va < nv[j].va)) {
				D.emplace_back(ov[i].va, ov[i].va + ov[i].size);
				note(0, ov[i].size);
				i++;
			} else if (i >= ov.size() || nv[j].va < ov[i].va) {
				D.emplace_back(nv[j].va, nv[j].va + nv[j].size);
				note(1, nv[j].size);
				j++;
			} else {
				D.emplace_back(ov[i].va, ov[i].va + ov[i].size);
				D.emplace_back(nv[j].va, nv[j].va + nv[j].size);
				note(2, nv[j].size);
				i++;
				j++;
			}
		}
	}
	// (b) the BOs that differ from those the mappings were made with, as file intervals -> the views that show them
	std::vector<IV> F;
	{
		const auto& ob = e438::bos_at[k];
		size_t      i = 0, j = 0;
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
	}
	// (c) lazy chunks whose written state changed (kl412's scan at today's cadence): the lazy views that show them
	std::vector<IV> L;
	for (const uint64_t c: lazy_changed) L.emplace_back(c, c + kDChunk); // scanned by direct_sync_one before the drain decision
	if (!L.empty()) e438::m_lazy_local++;
	if (!F.empty() || !L.empty()) {
		norm(F);
		norm(L);
		for (const auto& v: V.v) { // the views are not sorted by file offset: every one is looked at
			const uint64_t ve = v.off + v.size;
			auto           f  = std::partition_point(F.begin(), F.end(), [&v](const IV& x) { return x.second <= v.off; });
			bool           hit = f != F.end() && f->first < ve;
			if (!hit && v.lazy) {
				auto l = std::partition_point(L.begin(), L.end(), [&v](const IV& x) { return x.second <= v.off; });
				hit    = l != L.end() && l->first < ve;
			}
			if (hit) D.emplace_back(v.va, v.va + v.size);
		}
	}
	// (d) the maps that failed at an earlier update
	if (!e438::retry[k].empty()) {
		e438::m_retried++;
		D.insert(D.end(), e438::retry[k].begin(), e438::retry[k].end());
		e438::retry[k].clear();
	}
	norm(D);
	if (D.empty()) {
		e438::m_inc++;
		e438::m_inc_ns += SoftCp::now_ns() - t0;
		return true;
	}
	// the intervals grown to whole old mappings and whole new views until they stop growing (they only grow)
	for (;;) {
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
	}
	// the wanted mappings inside D, as the old rebuild makes them
	std::vector<DMap>              want;
	static std::vector<k1r412::Bo> kbos;
	const uint32_t                 kid = e438_kid(S);
	if (kid != 0) {
		kbos.clear();
		for (const auto& b: S.bos) kbos.push_back({b.off, b.size});
	}
	uint64_t nviews = 0;
	for (const auto& [lo, hi]: D) {
		auto v = std::partition_point(V.v.begin(), V.v.end(), [lo](const DView& x) { return x.va + x.size <= lo; });
		for (; v != V.v.end() && v->va < hi; ++v) {
			nviews++;
			e438_view_want(S, *v, kid, kbos, want);
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
			e438::retry[k].emplace_back(w.va, w.va + w.size); // retried at the next update, on its own interval
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
''')

# 3a. the lazy scan before the drain decision (build 12)
rep('''	if (!retired.empty() || sig != S.views_sig || guard0412_cap_changed(S) || (k1r412::on() && S.kind == 0 && S.bos.size() != S.bos_mapped)) { // exp 0412 (tag g412b; k1r412: covers are about to be unmapped and replaced)''',
    '''	// exp 0438 (tag e438, build 12): kl412's scan at today's cadence (100 ms), before the drain decision: a chunk whose
	// written state changed is a local update of the lazy views that show it, drained as today's rebuild was.
	std::vector<uint64_t> e438_lazy;
	if (e438::on() && S.kind == 0 && k1r412::on() && e438::have[0] && !S.maps.empty()) e438_lazy = e438_lazy_scan(S, *views_p, fd);
	if (!retired.empty() || sig != S.views_sig || guard0412_cap_changed(S) || (k1r412::on() && S.kind == 0 && S.bos.size() != S.bos_mapped) || !e438_lazy.empty()) { // exp 0412 (tag g412b; k1r412: covers are about to be unmapped and replaced); exp 0438 (build 12): a lazy change''')

# 3. direct_sync_one: no check inside the update; the state after, with the view tuples
rep('''	const int  e438_k     = S.kind == 0 ? 0 : 1; // exp 0438 (tag e438)
	const bool e438_check = e438::on() && S.kind == 0 && now - e438::check_ns[e438_k] >= 2'000'000'000ull; // the 2-s full rebuild (the check)
	const bool e438_check_only = e438_check && !(sig != S.views_sig || S.bos.size() != S.bos_mapped || !retired.empty() || guard0412_cap_changed(S));
	bool       e438_done  = false;
	if (sig != S.views_sig || S.bos.size() != S.bos_mapped || !retired.empty() || guard0412_cap_changed(S) || e438_check) { // exp 0412 (tag g412b); exp 0438 (e438): the check
		const uint64_t e438_t0 = SoftCp::now_ns();
		if (e438_check) e438::check_ns[e438_k] = now;
		if (e438::on() && !e438_check) e438_done = e438_maps(S, *views_p, zskip_new, fd, mapped, unmapped, map_failed); // exp 0438 (tag e438)''',
    '''	const int  e438_k     = S.kind == 0 ? 0 : 1; // exp 0438 (tag e438)
	bool       e438_done  = false;
	if (sig != S.views_sig || S.bos.size() != S.bos_mapped || !retired.empty() || guard0412_cap_changed(S) || (e438::on() && !e438::retry[e438_k].empty()) || !e438_lazy.empty()) { // exp 0412 (tag g412b); exp 0438 (e438, build 12): retries and a lazy change
		const uint64_t e438_t0 = SoftCp::now_ns();
		if (e438::on()) e438_done = e438_maps(S, *views_p, zskip_new, e438_lazy, mapped, unmapped, map_failed); // exp 0438 (tag e438)''')
rep('''			if (!e438_done) {
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
			e438::force_full[e438_k] = map_failed != 0;''', '''			if (!e438_done) {
				e438::m_full++;
				e438::m_full_ns += SoftCp::now_ns() - e438_t0;
				e438::retry[e438_k].clear(); // the old rebuild retries by itself (S.bos_mapped)
			}
			if (e438::prev_sig[e438_k] != views_p->sig || e438::prev_v[e438_k].size() != views_p->v.size()) { // build 12: the tuples the maps are made from
				e438::prev_v[e438_k].clear();
				for (const auto& v: views_p->v) e438::prev_v[e438_k].push_back({v.va, v.size, v.off, v.lazy, v.eager});
				e438::prev_sig[e438_k] = views_p->sig;
			}
			e438::bos_at[e438_k]     = S.bos;
			e438::have[e438_k]       = true;''')
rep('''			std::lock_guard l(e438::mu);
			const uint64_t  upto = e438::seq_at[e438_k];''', '''			if (e438_done && map_failed != 0) S.bos_mapped = S.bos.size(); // build 12: the failure is on e438::retry, not a reason for the old rebuild
			std::lock_guard l(e438::mu);
			const uint64_t  upto = e438::seq_at[e438_k];''')
# the diagnostic check after the update (normal build only, no repair)
rep('''	g_dprof_maps_ns += SoftCp::now_ns() - t_maps0; // experiment 0169''', '''#ifndef BC5_LEAN
	if (e438::on() && e438::have[e438_k] && now - e438::check_ns[e438_k] >= 2'000'000'000ull && g_zskip.empty() && !e438_g412_any() && !kc412::on() && S.views_sig == sig) {
		// exp 0438 (tag e438, build 12): the diagnostic check. S.maps against the full list made the old way, from the same
		// known-written set; a difference is a bug, recorded, not repaired.
		e438::check_ns[e438_k] = now;
		e438::d_checks++;
		const std::vector<DMap> full = e438_full_want(S, *views_p);
		size_t                  i = 0, j = 0;
		uint64_t                extra = 0, missing = 0;
		while (i < S.maps.size() || j < full.size()) {
			if (i < S.maps.size() && j < full.size() && S.maps[i] == full[j]) {
				i++;
				j++;
			} else if (j >= full.size() || (i < S.maps.size() && S.maps[i].va < full[j].va)) {
				extra++;
				i++;
			} else if (i >= S.maps.size() || full[j].va < S.maps[i].va) {
				missing++;
				j++;
			} else {
				extra++;
				missing++;
				i++;
				j++;
			}
		}
		if (extra != 0 || missing != 0) {
			e438::d_mismatch++;
			e438::d_extra += extra;
			e438::d_missing += missing;
			static int logged = 0;
			if (logged++ < 8) journal("e438 (exp 0438): BUG: t %.3f s: %s: the mappings differ from the full list: %" PRIu64 " extra, %" PRIu64 " missing (%zu against %zu); not repaired\\n", timing_now(), S.label, extra, missing, S.maps.size(), full.size());
		}
	}
#endif
	g_dprof_maps_ns += SoftCp::now_ns() - t_maps0; // experiment 0169''')

# 4. the 60-s line, build 12's counters
a = s.index('			journal("e438 (exp 0438): t %.1f s: layout %s;')
b = s.index('static_cast<uint64_t>(d432::g_views_clone.load()));', a) + len('static_cast<uint64_t>(d432::g_views_clone.load()));')
s = s[:a] + '''			journal("e438 (exp 0438, build 12): t %.1f s: layout %s; mapping updates incremental %" PRIu64 " (%.1f ms; %" PRIu64 " intervals, %" PRIu64 " views, maps +%" PRIu64 " -%" PRIu64
			        "; local lazy updates %" PRIu64 ", retries %" PRIu64 "), full %" PRIu64 " (%.1f ms) because: first/no maps %" PRIu64 ", reopen %" PRIu64 ", unsorted (bug) %" PRIu64 ", zskip %" PRIu64 ", g412 %" PRIu64
			        ", kc412 %" PRIu64 "; diagnostic checks %" PRIu64 ", with a difference (bug) %" PRIu64 " (extra %" PRIu64 ", missing %" PRIu64 "); lazy chunks taken out of a zero cover %" PRIu64 " in %" PRIu64
			        " scans, time since the scan before %.1f ms on average, longest %.1f ms; record gaps %" PRIu64 ", kept-list mismatches %" PRIu64 ", view builds %" PRIu64 ", clones %" PRIu64 "\\n",
			        timing_now(), e438::on() ? "ON" : "off", e438::m_inc, static_cast<double>(e438::m_inc_ns) / 1e6, e438::m_intervals, e438::m_views, e438::m_plus, e438::m_minus, e438::m_lazy_local,
			        e438::m_retried, e438::m_full, static_cast<double>(e438::m_full_ns) / 1e6, e438::m_why[0], e438::m_why[1], e438::m_why[2], e438::m_why[3], e438::m_why[4], e438::m_why[5],
			        e438::d_checks, e438::d_mismatch, e438::d_extra, e438::d_missing, e438::kl_out, e438::kl_scans,
			        e438::kl_out != 0 ? static_cast<double>(e438::kl_out_ns) / 1e6 / static_cast<double>(e438::kl_out) : 0.0, static_cast<double>(e438::kl_out_max_ns) / 1e6, e438::r_gaps.load(),
			        e438::r_mismatch.load(), static_cast<uint64_t>(g_views_builds), static_cast<uint64_t>(d432::g_views_clone.load()));''' + s[b:]

out = s.encode('utf-8')
open(OUT, 'wb').write(out)
print('f438 unit', hashlib.md5(out).hexdigest(), len(out))
