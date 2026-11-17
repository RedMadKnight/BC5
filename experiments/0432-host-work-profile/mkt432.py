#!/usr/bin/env python3
"""BC5 experiment 0432, the ONE test build's host unit (tags d432, a432, v432). Run on a tree that is patch bc39a035 with
exp 0415's kit/0415-l6-on-B.diff applied (git apply --reject; semaphore.cpp and load_stat.hpp reverted, the two rejected
hunks of bc5LleAgc.cpp left out: a journal line and a statistic):
    mkt432.py <tree>/src/libs/bc5LleAgc.cpp
Every replacement must match exactly once. Switches, all read with plain getenv (the lean build has them), all ON
unless the word is "0":
  BC5_DIRECT_UNMAP_NOWAIT  item D: no host wait for an idle GPU before a mapping change (README, item D)
  BC5_DIRECT_ANON_EVENTS   item A: exp 0415's "events" form of the anonymous sync (tag as415c): the walk of
                           /proc/self/maps runs after a counted anonymous map or protect call in the guest's span, after
                           -EFAULT and a reopen, and on its old timing while an anonymous guest VMA exists; else left out
  BC5_DIRECT_VIEWS_KEPT    item V: exp 0415's kept view list (tag mr415d): change records applied in place, the full
                           build only as a check every 2 s (KYTY_BC5_MAP_RECORDS_CHECK_MS)
"0" for each gives the shared build's path (for A and V: whatever KYTY_BC5_ANON_SYNC / KYTY_BC5_MAP_RECORDS say, off
when unset). Exp 0415's new load_stat causes are not taken (load_stat.hpp is included by units this build does not
recompile); their counts go to this build's own counters, printed at most every 10 s on stderr and in the journal.
"""
import sys

p = sys.argv[1]
s = open(p, "rb").read().decode("utf-8")
assert "\r" not in s


def sub(old, new, n=1):
    global s
    got = s.count(old)
    assert got == n, "%d matches, wanted %d: %r" % (got, n, old[:90])
    s = s.replace(old, new)


# the switches and the counters, before their first use
sub("static void wait_jobs();\n",
    "static void wait_jobs();\n"
    "static void chain_flush(int why); // exp 0432 (tag d432)\n"
    "// exp 0432: the test build's three host switches (each on unless \"0\") and its counters.\n"
    "namespace d432 {\n"
    "inline bool word_on(const char* name) {\n"
    "\tconst char* e = std::getenv(name);\n"
    "\treturn !(e != nullptr && e[0] == '0' && e[1] == 0);\n"
    "}\n"
    "inline bool on() { // item D: BC5_DIRECT_UNMAP_NOWAIT (the kernel orders the page-table clear behind this VM's submissions: amdgpu_vm_clear_freed, v7.3)\n"
    "\tstatic const bool v = word_on(\"BC5_DIRECT_UNMAP_NOWAIT\");\n"
    "\treturn v;\n"
    "}\n"
    "inline bool anon_events() { // item A\n"
    "\tstatic const bool v = word_on(\"BC5_DIRECT_ANON_EVENTS\");\n"
    "\treturn v;\n"
    "}\n"
    "inline bool views_kept() { // item V\n"
    "\tstatic const bool v = word_on(\"BC5_DIRECT_VIEWS_KEPT\");\n"
    "\treturn v;\n"
    "}\n"
    "inline bool maps_fast() { // item M\n"
    "\tstatic const bool v = word_on(\"BC5_DIRECT_MAPS_FAST\");\n"
    "\treturn v;\n"
    "}\n"
    "inline std::atomic<uint64_t> g_maps_fast {0}, g_maps_sorted {0};\n"
    "inline std::atomic<uint64_t> g_rebuilds {0}, g_busy {0}, g_unmaps_busy {0}, g_bos_busy {0}, g_unmaps {0}, g_drains {0}, g_drain_ns {0}, g_drain_max_ns {0},\n"
    "    g_prep_max_ns {0}, g_prep_over20 {0}, g_last_ns {0}, g_anon_walks {0}, g_anon_skips {0}, g_anon_ev {0}, g_anon_ev_miss {0}, g_anon_vmas {0}, g_views_clone {0},\n"
    "    g_rec_mismatch {0}, g_sync_ns {0};\n"
    "inline void maxed(std::atomic<uint64_t>& m, uint64_t v) {\n"
    "\tuint64_t was = m.load(std::memory_order_relaxed);\n"
    "\twhile (v > was && !m.compare_exchange_weak(was, v, std::memory_order_relaxed)) {\n"
    "\t}\n"
    "}\n"
    "} // namespace d432\n")

# item V: the mode, and exp 0415's counts
sub("\t\tconst char* e = BC5_DIAG_ENV(\"KYTY_BC5_MAP_RECORDS\");\n"
    "\t\tif (!bc5::load_stat::env_set(e)) return 0;\n",
    "\t\tif (d432::views_kept()) return 2; // exp 0432 (tag v432): BC5_DIRECT_VIEWS_KEPT\n"
    "\t\tconst char* e = BC5_DIAG_ENV(\"KYTY_BC5_MAP_RECORDS\");\n"
    "\t\tif (!bc5::load_stat::env_set(e)) return 0;\n")
sub("\t\t\t\tbc5::load_stat::count(bc5::load_stat::kViewsClone, kept_p->v.size());\n", "\t\t\t\td432::g_views_clone++; // exp 0432\n")
sub("\t\t\tbc5::load_stat::count(bc5::load_stat::kRecMismatch);\n", "\t\t\tbc5::load_stat::count(bc5::load_stat::kRecMismatch);\n\t\t\td432::g_rec_mismatch++; // exp 0432\n", 3)

# item A: the mode, and exp 0415's counts
sub("\tstatic const int mode = bc5::anon_sync::mode_of(BC5_DIAG_ENV(\"KYTY_BC5_ANON_SYNC\")) != 0 ? 1 : 0; // exp 0419 phase 2: verify only\n",
    "\tstatic const int mode = d432::anon_events() ? 3 : (bc5::anon_sync::mode_of(BC5_DIAG_ENV(\"KYTY_BC5_ANON_SYNC\")) != 0 ? 1 : 0); // exp 0419 phase 2: verify only; exp 0432 (tag a432): BC5_DIRECT_ANON_EVENTS is \"events\"\n")
sub("\t\t\tbc5::load_stat::count(bc5::load_stat::kAnonEvCalls);\n", "")
sub("\t\t\tbc5::load_stat::count(bc5::load_stat::kAnonSkip);\n", "\t\t\td432::g_anon_skips++; // exp 0432\n")
sub("\tif (as_mode != 0 && as_ev_moved) bc5::load_stat::count(bc5::load_stat::kAnonEvents, g_as415_walk_valid ? as_ev - g_as415_walk_ev : 0);\n",
    "\tif (as_ev_moved) d432::g_anon_ev++; // exp 0432: walks that the map/protect counter asked for\n\td432::g_anon_walks++;\n")
sub("\t\t\tbc5::load_stat::count(bc5::load_stat::kAnonEvMiss);\n", "\t\t\td432::g_anon_ev_miss++; // exp 0432\n")
sub("\tg_vmas = vmas;\n", "\tg_vmas = vmas;\n\td432::g_anon_vmas = vmas.size(); // exp 0432\n")

# item D
sub("\tif (pass.done.empty() || !g_dev) return;\n"
    "\tif (g_dev->wait_idle(0)) return;\n",
    "\tif (pass.done.empty() || !g_dev) return;\n"
    "\tif (d432::on()) return; // exp 0432 (tag d432): the cut stands, the kernel retires the old mappings behind the jobs in flight\n"
    "\tif (g_dev->wait_idle(0)) return;\n")
sub("\t\twait_jobs(); // mappings are about to go or be replaced\n"
    "\t\tg_dprof_drains++;\n"
    "\t}\n",
    "\t\td432::g_rebuilds++;\n"
    "\t\tif (d432::on()) { // exp 0432 (tag d432): no wait; the chain is flushed as wait_jobs() did first\n"
    "\t\t\tchain_flush(5);\n"
    "\t\t\td432_busy = !g_dev->wait_idle(0); // a count only: was anything in flight\n"
    "\t\t\tif (d432_busy) d432::g_busy++;\n"
    "\t\t} else {\n"
    "\t\t\twait_jobs(); // mappings are about to go or be replaced\n"
    "\t\t\tg_dprof_drains++;\n"
    "\t\t\tconst uint64_t w = SoftCp::now_ns() - t_drain0;\n"
    "\t\t\td432::g_drains++;\n"
    "\t\t\td432::g_drain_ns += w;\n"
    "\t\t\td432::maxed(d432::g_drain_max_ns, w);\n"
    "\t\t}\n"
    "\t}\n")
sub("\tconst uint64_t t_drain0 = SoftCp::now_ns(); // experiment 0169\n",
    "\tconst uint64_t t_drain0 = SoftCp::now_ns(); // experiment 0169\n"
    "\tbool           d432_busy = false;           // exp 0432 (tag d432)\n")
sub("\tfor (const uint32_t id: retired) g_dev->free_shared(id);\n"
    "\tguard0412_after_cuts(lzr.done.size()); // exp 0412 (tag g412c): BC5_GUARD_SPLIT\n",
    "\td432::g_unmaps += unmapped; // exp 0432 (tag d432)\n"
    "\tif (d432_busy) {\n"
    "\t\td432::g_unmaps_busy += unmapped;\n"
    "\t\td432::g_bos_busy += retired.size();\n"
    "\t}\n"
    "\tfor (const uint32_t id: retired) g_dev->free_shared(id);\n"
    "\tguard0412_after_cuts(lzr.done.size()); // exp 0412 (tag g412c): BC5_GUARD_SPLIT\n")

# item M (tag m432): the mapping rebuild's passes over every wanted mapping, same result with less work
sub("\t\tguard0412_want(S, views, want); // exp 0412 (tag g412b): the zero buffer under the views of put-off chunks\n",
    "\t\tconst size_t m432_n1 = want.size(); // exp 0432 (tag m432): the views' own mappings end here\n"
    "\t\tguard0412_want(S, views, want); // exp 0412 (tag g412b): the zero buffer under the views of put-off chunks\n")
sub("\t\tstd::sort(want.begin(), want.end(), [](const DMap& a, const DMap& b) { return a.va < b.va; });\n",
    "\t\t// exp 0432 (tag m432), BC5_DIRECT_MAPS_FAST: the list is two runs that are nearly always in order already (the views'\n"
    "\t\t// mappings, then the covers); they are merged instead of sorted when each run is strictly rising, and the result is\n"
    "\t\t// taken only if it is strictly rising too (then it is the one order a sort can give). Otherwise the old sort.\n"
    "\t\tconst auto m432_less = [](const DMap& a, const DMap& b) { return a.va < b.va; };\n"
    "\t\tconst auto m432_rising = [&want](size_t from, size_t to) {\n"
    "\t\t\tfor (size_t i = from + 1; i < to; i++) {\n"
    "\t\t\t\tif (want[i - 1].va >= want[i].va) return false;\n"
    "\t\t\t}\n"
    "\t\t\treturn true;\n"
    "\t\t};\n"
    "\t\tbool m432_fast = d432::maps_fast() && m432_rising(0, m432_n1) && m432_rising(m432_n1, want.size());\n"
    "\t\tif (m432_fast) {\n"
    "\t\t\tstd::inplace_merge(want.begin(), want.begin() + static_cast<std::ptrdiff_t>(m432_n1), want.end(), m432_less);\n"
    "\t\t\tm432_fast = m432_rising(0, want.size());\n"
    "\t\t}\n"
    "\t\tif (!m432_fast) std::sort(want.begin(), want.end(), m432_less);\n"
    "\t\t(m432_fast ? d432::g_maps_fast : d432::g_maps_sorted)++;\n")
sub("\t\t\tconst auto w = std::lower_bound(want.begin(), want.end(), m.va, [](const DMap& a, uint64_t va) { return a.va < va; });\n"
    "\t\t\tif (w != want.end() && *w == m) {\n",
    "\t\t\t// exp 0432 (tag m432): both lists rise by address, so the place of m in `want` only moves forward; a step back in\n"
    "\t\t\t// S.maps (never seen) takes the old search\n"
    "\t\t\tauto w = want.end();\n"
    "\t\t\tif (m432_fast && m.va >= m432_prev) {\n"
    "\t\t\t\twhile (m432_k < want.size() && want[m432_k].va < m.va) m432_k++;\n"
    "\t\t\t\tw = want.begin() + static_cast<std::ptrdiff_t>(m432_k);\n"
    "\t\t\t} else {\n"
    "\t\t\t\tw = std::lower_bound(want.begin(), want.end(), m.va, [](const DMap& a, uint64_t va) { return a.va < va; });\n"
    "\t\t\t\tm432_k = static_cast<size_t>(w - want.begin());\n"
    "\t\t\t}\n"
    "\t\t\tm432_prev = m.va;\n"
    "\t\t\tif (w != want.end() && *w == m) {\n")
sub("\t\tfor (const auto& m: S.maps) { // drop what no view asks for any more, before adding (addresses get reused)\n",
    "\t\tsize_t   m432_k    = 0; // exp 0432 (tag m432)\n"
    "\t\tuint64_t m432_prev = 0;\n"
    "\t\tfor (const auto& m: S.maps) { // drop what no view asks for any more, before adding (addresses get reused)\n")

# the line
sub("\thint_targets(ib, num_dwords);\n"
    "\tconst uint64_t t2 = SoftCp::now_ns();\n",
    "\thint_targets(ib, num_dwords);\n"
    "\tconst uint64_t t2 = SoftCp::now_ns();\n"
    "\t{ // exp 0432: the sync + hints part of every submission (\"prepare\" here), and the counters at most every 10 s\n"
    "\t\td432::g_sync_ns += t2 - t0;\n"
    "\t\td432::maxed(d432::g_prep_max_ns, t2 - t0);\n"
    "\t\tif (t2 - t0 > 20'000'000ull) d432::g_prep_over20++;\n"
    "\t\tuint64_t was = d432::g_last_ns.load(std::memory_order_relaxed);\n"
    "\t\tif (t2 - was >= 10'000'000'000ull && d432::g_last_ns.compare_exchange_strong(was, t2)) {\n"
    "\t\t\tchar line[900];\n"
    "\t\t\tstd::snprintf(line, sizeof(line),\n"
    "\t\t\t              \"exp 0432 (tag d432): t %.1f s: unmap-nowait %s, anon-events %s, views-kept %s; sync+hints of all submissions %.1f s, longest %.1f ms, over 20 ms %\" PRIu64\n"
    "\t\t\t              \"; rebuilds that change mappings %\" PRIu64 \", with a ring busy %\" PRIu64 \"; mappings dropped %\" PRIu64 \", while busy %\" PRIu64 \", BOs retired while busy %\" PRIu64\n"
    "\t\t\t              \"; blocking drains %\" PRIu64 \", %.1f ms in all, longest %.1f ms; anon walks %\" PRIu64 \" (asked by the counter %\" PRIu64 \"), left out %\" PRIu64 \", event misses %\" PRIu64\n"
    "\t\t\t              \", anonymous guest VMAs %\" PRIu64 \"; view builds %\" PRIu64 \", list copies %\" PRIu64 \", record mismatches %\" PRIu64 \"; maps-fast %s: merged %\" PRIu64 \", sorted %\" PRIu64,\n"
    "\t\t\t              timing_now(), d432::on() ? \"ON\" : \"off\", d432::anon_events() ? \"ON\" : \"off\", d432::views_kept() ? \"ON\" : \"off\",\n"
    "\t\t\t              static_cast<double>(d432::g_sync_ns.load()) / 1e9, static_cast<double>(d432::g_prep_max_ns.load()) / 1e6, d432::g_prep_over20.load(), d432::g_rebuilds.load(),\n"
    "\t\t\t              d432::g_busy.load(), d432::g_unmaps.load(), d432::g_unmaps_busy.load(), d432::g_bos_busy.load(), d432::g_drains.load(),\n"
    "\t\t\t              static_cast<double>(d432::g_drain_ns.load()) / 1e6, static_cast<double>(d432::g_drain_max_ns.load()) / 1e6, d432::g_anon_walks.load(), d432::g_anon_ev.load(),\n"
    "\t\t\t              d432::g_anon_skips.load(), d432::g_anon_ev_miss.load(), d432::g_anon_vmas.load(), static_cast<uint64_t>(g_views_builds), d432::g_views_clone.load(),\n"
    "\t\t\t              d432::g_rec_mismatch.load(), d432::maps_fast() ? \"ON\" : \"off\", d432::g_maps_fast.load(), d432::g_maps_sorted.load());\n"
    "\t\t\tstd::fprintf(stderr, \"[bc5] %s\\n\", line);\n"
    "\t\t\tjournal(\"%s\\n\", line);\n"
    "\t\t}\n"
    "\t}\n")
open(p, "w", encoding="utf-8", newline="\n").write(s)
print("edited", p)
