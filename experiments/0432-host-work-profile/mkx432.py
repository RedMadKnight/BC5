#!/usr/bin/env python3
"""BC5 experiment 0432, item X (tag x432), BC5_DIRECT_MAPS_DIFF: the mapping rebuild for the changed views only.
    mkx432.py <tree>/src/libs/bc5LleAgc.cpp      (after mkt432.py; the unit must be 74311888)

Why: result 1 and result 6. A rebuild of the mappings runs about 17 times a second in play, and each one walks every
view (up to 30,631) against the imported buffers, orders the list and walks every mapping twice, though a rebuild
caused by the guest's ranges changes a handful of views.

What: when the ONLY cause of a rebuild is a new view list (no buffer retired, none imported since the last rebuild,
no cap change, no cover or zero-list mappings in play), the new list is compared with the list the mappings were made
from (kept by reference; both rise by address without overlap, the builder's `sorted`). A view present in both with
the same address, size and offset keeps its mappings: a mapping is one (view, buffer) intersection and the buffers
did not change. Every other old or new view gives an address interval; the old mappings inside the intervals are
dropped unless a changed new view asks for the same one, then the changed new views' mappings are added, by the old
add pass's own steps. Any other cause takes the old rebuild.

Switch: off unless the word is "1" (on) or "verify" (on, and after each such rebuild the whole list is also made the
old way and compared; a difference is counted, journaled, and the next sync rebuilds the old way). Untested code:
off by default until a verify run shows 0 differences.

If it were wrong: a mapping kept that should have gone (the GPU reads pages the guest gave back) or one missing (a
GPU page fault, which ends the game with a record).
"""
import hashlib, re, sys

p = sys.argv[1]
b = open(p, "rb").read()
assert hashlib.md5(b).hexdigest()[:8] == "74311888", "the unit is not mkt432.py's 74311888"
s = b.decode("utf-8")


def sub(old, new, n=1):
    global s
    got = s.count(old)
    assert got == n, "%d matches, wanted %d: %r" % (got, n, old[:80])
    s = s.replace(old, new)


def cpp(text):  # a leading run of '~' is that many tabs
    return re.sub(r"(?m)^~+", lambda m: "\t" * len(m.group(0)), text)


sub("inline std::atomic<uint64_t> g_maps_fast {0}, g_maps_sorted {0};\n", cpp("""inline std::atomic<uint64_t> g_maps_fast {0}, g_maps_sorted {0};
inline int maps_diff() { // item X: 0 off, 1 on, 2 on and checked against the old rebuild; OFF unless the word is "1" or "verify"
~static const int v = [] {
~~const char* e = std::getenv("BC5_DIRECT_MAPS_DIFF");
~~if (e == nullptr) return 0;
~~if (std::strcmp(e, "verify") == 0) return 2;
~~return e[0] == '1' && e[1] == 0 ? 1 : 0;
~}();
~return v;
}
inline std::atomic<uint64_t> g_x_diff {0}, g_x_full {0}, g_x_views {0}, g_x_mismatch {0};
inline std::atomic<uint64_t> g_x_why[11]; // which condition sent a rebuild the old way (the first that failed)
"""))

sub("\t\tstd::vector<DMap> want;\n\t\tfor (const auto& v: views) {\n\t\t\tconst uint64_t vend = v.off + v.size;\n", cpp("""~~// exp 0432 (tag x432), BC5_DIRECT_MAPS_DIFF: see mkx432.py. x432_prev is the view list S.maps was made from;
~~// x432_plain says that rebuild's wanted list held the views' own mappings only (no zero buffer, no cover).
~~static std::shared_ptr<const DViews> x432_prev[2];
~~static bool                          x432_plain[2] = {false, false};
~~const int                            x432_k        = S.kind == 0 ? 0 : 1;
~~bool                                 x432_done     = false, x432_bad = false;
~~if (d432::maps_diff() != 0 && retired.empty() && S.bos.size() == S.bos_mapped && !guard0412_cap_changed(S) && !k1r412::on() && g_zskip.empty() && !zskip_new &&
~~    x432_plain[x432_k] && x432_prev[x432_k] != nullptr && x432_prev[x432_k]->sig == S.views_sig && x432_prev[x432_k]->sorted && views_p->sorted) {
~~~const std::vector<DView>&                   ov = x432_prev[x432_k]->v;
~~~std::vector<std::pair<uint64_t, uint64_t>> iv; // the changed views' address intervals; their starts never fall
~~~std::vector<const DView*>                  nv; // the changed views of the new list, rising
~~~const auto put = [&iv](uint64_t a, uint64_t e) {
~~~~if (!iv.empty() && a <= iv.back().second) {
~~~~~if (e > iv.back().second) iv.back().second = e;
~~~~} else {
~~~~~iv.emplace_back(a, e);
~~~~}
~~~};
~~~for (size_t i = 0, j = 0; i < ov.size() || j < views.size();) {
~~~~if (i < ov.size() && j < views.size() && ov[i].va == views[j].va && ov[i].size == views[j].size && ov[i].off == views[j].off) {
~~~~~i++;
~~~~~j++;
~~~~} else if (j >= views.size() || (i < ov.size() && ov[i].va < views[j].va)) {
~~~~~put(ov[i].va, ov[i].va + ov[i].size);
~~~~~i++;
~~~~} else if (i >= ov.size() || views[j].va < ov[i].va) {
~~~~~put(views[j].va, views[j].va + views[j].size);
~~~~~nv.push_back(&views[j]);
~~~~~j++;
~~~~} else { // the same address, another size or offset
~~~~~put(ov[i].va, ov[i].va + ov[i].size);
~~~~~put(views[j].va, views[j].va + views[j].size);
~~~~~nv.push_back(&views[j]);
~~~~~i++;
~~~~~j++;
~~~~}
~~~}
~~~const auto x432_want = [&S](const DView& v, std::vector<DMap>& out) {
~~~~const uint64_t vend = v.off + v.size;
~~~~auto it = std::upper_bound(S.bos.begin(), S.bos.end(), v.off, [](uint64_t o, const DBo& b) { return o < b.off; });
~~~~if (it != S.bos.begin()) --it;
~~~~for (; it != S.bos.end() && it->off < vend; ++it) {
~~~~~const uint64_t lo = it->off > v.off ? it->off : v.off;
~~~~~const uint64_t hi = it->off + it->size < vend ? it->off + it->size : vend;
~~~~~if (lo >= hi) continue;
~~~~~out.push_back({v.va + (lo - v.off), hi - lo, lo - it->off, it->id});
~~~~}
~~~};
~~~std::vector<DMap> want; // of the changed new views only; rising
~~~for (const DView* v: nv) x432_want(*v, want);
~~~std::vector<DMap> next;
~~~next.reserve(S.maps.size() + want.size());
~~~size_t q = 0, wk = 0;
~~~for (const auto& m: S.maps) { // drop before adding (addresses get reused)
~~~~while (q < iv.size() && iv[q].second <= m.va) q++;
~~~~if (q >= iv.size() || m.va < iv[q].first) {
~~~~~next.push_back(m); // under an unchanged view
~~~~~continue;
~~~~}
~~~~while (wk < want.size() && want[wk].va < m.va) wk++;
~~~~if (wk < want.size() && want[wk] == m) {
~~~~~next.push_back(m);
~~~~} else {
~~~~~g_dev->unmap_shared(m.va);
~~~~~unmapped++;
~~~~}
~~~}
~~~std::vector<DMap> added;
~~~{
~~~~size_t k = 0;
~~~~for (const auto& w: want) {
~~~~~while (k < next.size() && next[k].va < w.va) k++;
~~~~~if (k < next.size() && next[k] == w) continue;
~~~~~if (!g_scratch.empty()) scratch_release(w.va, w.va + w.size);
~~~~~if (!g_zpieces.empty()) zskip_release(w.va, w.va + w.size);
~~~~~if (g_dev->map_shared(w.id, w.bo_off, w.size, w.va)) {
~~~~~~added.push_back(w);
~~~~~~mapped++;
~~~~~} else {
~~~~~~map_failed++;
~~~~~}
~~~~}
~~~}
~~~if (!added.empty()) {
~~~~std::vector<DMap> merged_maps;
~~~~merged_maps.reserve(next.size() + added.size());
~~~~std::merge(next.begin(), next.end(), added.begin(), added.end(), std::back_inserter(merged_maps), [](const DMap& a, const DMap& b) { return a.va < b.va; });
~~~~next.swap(merged_maps);
~~~}
~~~S.maps.swap(next);
~~~d432::g_x_diff++;
~~~d432::g_x_views += nv.size();
~~~if (d432::maps_diff() == 2 && map_failed == 0) { // the whole list the old way, compared
~~~~std::vector<DMap> all;
~~~~all.reserve(S.maps.size());
~~~~for (const auto& v: views) x432_want(v, all);
~~~~size_t at = 0;
~~~~while (at < all.size() && at < S.maps.size() && all[at] == S.maps[at]) at++;
~~~~if (at != all.size() || at != S.maps.size()) {
~~~~~x432_bad = true;
~~~~~d432::g_x_mismatch++;
~~~~~static int logged = 0;
~~~~~if (logged++ < 8) {
~~~~~~journal("exp 0432 (tag x432): MISMATCH: the mappings by diff (%zu) and the old rebuild's list (%zu) differ at index %zu; %zu views changed; the next sync rebuilds the old way\\n",
~~~~~~        S.maps.size(), all.size(), at, nv.size());
~~~~~}
~~~~}
~~~}
~~~x432_done = true;
~~}
~~if (!x432_done) {
~~d432::g_x_full++;
~~if (d432::maps_diff() != 0) { // result 7: X was never taken and nothing said why
~~~const bool x432_c[11] = {!retired.empty(), S.bos.size() != S.bos_mapped, guard0412_cap_changed(S), k1r412::on(), !g_zskip.empty(), zskip_new, !x432_plain[x432_k],
~~~                         x432_prev[x432_k] == nullptr, x432_prev[x432_k] != nullptr && x432_prev[x432_k]->sig != S.views_sig,
~~~                         x432_prev[x432_k] != nullptr && !x432_prev[x432_k]->sorted, !views_p->sorted};
~~~for (int x432_i = 0; x432_i < 11; x432_i++) {
~~~~if (x432_c[x432_i]) {
~~~~~d432::g_x_why[x432_i]++;
~~~~~break;
~~~~}
~~~}
~~}
~~std::vector<DMap> want;
~~for (const auto& v: views) {
~~~const uint64_t vend = v.off + v.size;
"""))

sub("\t\tS.maps.swap(next);\n\t\tif (S.kind == 0 && (zskip_new || sig != S.views_sig)) zskip_map(views); // experiment 0379\n"
    "\t\tS.views_sig  = sig;\n"
    "\t\tS.bos_mapped = map_failed == 0 ? S.bos.size() : 0; // a failure is retried at the next sync\n",
    cpp("""~~x432_plain[x432_k] = m432_n1 == want.size(); // exp 0432 (tag x432)
~~S.maps.swap(next);
~~} // exp 0432 (tag x432): the old rebuild ends here
~~if (S.kind == 0 && (zskip_new || sig != S.views_sig)) zskip_map(views); // experiment 0379
~~S.views_sig  = sig;
~~S.bos_mapped = map_failed == 0 ? S.bos.size() : 0; // a failure is retried at the next sync
~~x432_prev[x432_k] = views_p; // exp 0432 (tag x432)
~~if (x432_bad) { // the next sync takes the old rebuild, which drops and adds until the lists agree
~~~x432_prev[x432_k].reset();
~~~S.bos_mapped = 0;
~~}
"""))

# the line
sub("\t\t\tchar line[900];\n", "\t\t\tchar line[1600];\n")
sub("\"; maps-fast %s: merged %\" PRIu64 \", sorted %\" PRIu64,\n",
    "\"; maps-fast %s: merged %\" PRIu64 \", sorted %\" PRIu64 \"; maps-diff %s: by diff %\" PRIu64 \", the old way %\" PRIu64 \", views changed %\" PRIu64 \", mismatches %\" PRIu64\n"
    "\t\t\t              \" (the old way because: retired %\" PRIu64 \", new BOs %\" PRIu64 \", cap %\" PRIu64 \", k1r %\" PRIu64 \", zero list %\" PRIu64 \", zero new %\" PRIu64\n"
    "\t\t\t              \", not plain %\" PRIu64 \", no list %\" PRIu64 \", sig %\" PRIu64 \", old unsorted %\" PRIu64 \", new unsorted %\" PRIu64 \")\",\n")
sub("d432::maps_fast() ? \"ON\" : \"off\", d432::g_maps_fast.load(), d432::g_maps_sorted.load());\n",
    "d432::maps_fast() ? \"ON\" : \"off\", d432::g_maps_fast.load(), d432::g_maps_sorted.load(),\n"
    "\t\t\t              d432::maps_diff() == 2 ? \"VERIFY\" : d432::maps_diff() == 1 ? \"ON\" : \"off\", d432::g_x_diff.load(), d432::g_x_full.load(), d432::g_x_views.load(),\n"
    "\t\t\t              d432::g_x_mismatch.load(), d432::g_x_why[0].load(), d432::g_x_why[1].load(), d432::g_x_why[2].load(), d432::g_x_why[3].load(), d432::g_x_why[4].load(),\n"
    "\t\t\t              d432::g_x_why[5].load(), d432::g_x_why[6].load(), d432::g_x_why[7].load(), d432::g_x_why[8].load(), d432::g_x_why[9].load(), d432::g_x_why[10].load());\n")
open(p, "w", encoding="utf-8", newline="\n").write(s)
print("edited", p, "(item X)")
