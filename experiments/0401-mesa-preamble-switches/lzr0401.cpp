// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0401 series e7, tag lzr: the CPU test of lzr0401.inc, the exact text mklzr0401.py puts into
// src/libs/bc5LleAgc.cpp for BC5_DIRECT_LAZY_RELEASE. Synthetic BO lists, views and forced sets only: no GPU, no game,
// no emulator state (the emulator's objects are linked in by the box's gate build and not called).
//   parse        the switch's grammar: unset, empty, 0, digits 1-86400, the words dry and eager, everything else off
//                with a reason (lesson R41); apply_allowed, period, due
//   covers       ranges merged, hits at their edges, the view classes (eager before lazy before data; zero)
//   idle         a chunk under no view is cut exactly at the idle time after a pass first found it so, not before; a view
//                in between restarts the time; a clock that went back restarts it too
//   never        under a view (eager, data, lazy), forced, last seen eager (without the word), a zero-list heap (even
//                with it), never seen under a view (without the word, or with the zero skip set), a BO not chunk-aligned
//   cuts         the kept runs of a split, a whole BO, splits off, the mapping budget, the cut count, apply and undo on a
//                BO list, the record of cuts, undos and returns
//   re-import    the released chunks a view covers again (partial views, edges), their runs, the BO list after the
//                import, the state of a chunk imported again, the eager or data path's import counted as a return
//   env          the switch as the process has it: on, a chunk cut after its idle time; off, nothing planned, no state
// It prints one line per case, then exactly "lzr0401: on N of N; end" (BC5_DIRECT_LAZY_RELEASE on) or
// "lzr0401: off N of N; end" (unset, empty, 0 or not parsing); without "; end" something failed. Exit 0 only after the
// end line; an argument that disagrees with the switch exits 2.
// Build (box): build0401.py --gate lzr0401.cpp <out> --like src/libs/bc5LleAgc.cpp, with lzr0401.inc in src/ beside this
// file (box0401.sh copies the .inc files the scripts write beside the unit there). Laptop:
// clang++ -std=c++20 -Wall -Wextra -Werror -I<dir of lzr0401.inc> lzr0401.cpp
// usage: BC5_DIRECT_LAZY_RELEASE=1 lzr0401 on      (=0 or unset: lzr0401 off; no argument: as set)
#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <initializer_list>
#include <set>
#include <string>
#include <utility>
#include <vector>

#if __has_include("src/lzr0401.inc")
#include "src/lzr0401.inc"
#elif __has_include("lzr0401.inc")
#include "lzr0401.inc"
#else
#error "lzr0401.inc not found: mklzr0401.py writes it beside the unit"
#endif

namespace {

using namespace Lzr0401;

constexpr uint64_t C  = 2ull << 20u;  // the chunk, spelled out here (2 MiB)
constexpr uint64_t S1 = 1'000'000'000ull;
constexpr uint64_t T0 = 1000 * S1;    // a clock that is not near 0
constexpr uint64_t H  = 0x200000000ull; // a memfd offset where the test's BOs start

struct TView { // DView's fields the pure part reads
    uint64_t off, size;
    bool     eager, lazy, zero;
};
struct TBo { // DBo's layout
    uint64_t off, size;
    uint32_t id;
    uint64_t t_ns;
};

int         g_checks = 0, g_case_fail = 0;
std::string g_why;
void check(bool ok, const char* what, int line) {
    g_checks++;
    if (!ok) {
        g_case_fail++;
        if (g_why.empty()) g_why = std::string(what) + " (line " + std::to_string(line) + ")";
    }
}
#define CHECK(x) check((x), #x, __LINE__)

Covers cov(const std::vector<TView>& v) { return covers(v, [](const TView& t) { return t.zero; }); }
Opts   on(uint64_t secs, bool eager = false, bool dry = false) {
    Opts o;
    o.on      = true;
    o.idle_ns = secs * S1;
    o.eager   = eager;
    o.dry     = dry;
    return o;
}
uint64_t ch(int k) { return H + static_cast<uint64_t>(k) * C; }
TView    data_view(int k0, int n) { return {ch(k0), static_cast<uint64_t>(n) * C, false, false, false}; }
TView    eager_view(int k0, int n) { return {ch(k0), static_cast<uint64_t>(n) * C, true, false, false}; }
TView    lazy_view(int k0, int n) { return {ch(k0), static_cast<uint64_t>(n) * C, false, true, false}; }
TView    zero_view(int k0, int n) { return {ch(k0), static_cast<uint64_t>(n) * C, true, false, true}; }
BoIn     bo(int k0, int n, uint32_t id, uint32_t maps = 0) { return {ch(k0), static_cast<uint64_t>(n) * C, id, maps}; }
const std::set<uint64_t> kNone;

// One pass with the usual budget: 512 mappings, 32 cuts, splits on, no zero skip.
Plan pass(const Opts& o, State& st, const std::vector<BoIn>& bos, const std::vector<TView>& views, uint64_t now, const std::set<uint64_t>& forced = kNone, bool zero_skip = false) {
    return plan(o, st, bos, cov(views), forced, now, 512, 32, true, zero_skip);
}

// ---- parse --------------------------------------------------------------------------------------------------------
void t_parse_off() {
    const Opts a = parse(nullptr), b = parse(""), c = parse("0");
    CHECK(!a.on && a.why == "unset");
    CHECK(!b.on && b.why == "empty");
    CHECK(!c.on && c.why == "0");
    CHECK(!apply_allowed(a) && !apply_allowed(b) && !apply_allowed(c));
    State st;
    CHECK(!due(a, st, T0));
}
void t_parse_on() {
    const Opts a = parse("1");
    CHECK(a.on && !a.dry && !a.eager && a.idle_ns == S1 && a.why == "1 s");
    const Opts b = parse("30");
    CHECK(b.on && b.idle_ns == 30 * S1 && apply_allowed(b));
    const Opts c = parse("86400");
    CHECK(c.on && c.idle_ns == 86400 * S1);
    const Opts d = parse("007");
    CHECK(d.on && d.idle_ns == 7 * S1);
    const Opts e = parse("30,dry");
    CHECK(e.on && e.dry && !e.eager && !apply_allowed(e) && e.why == "30 s, dry");
    const Opts f = parse("30,eager");
    CHECK(f.on && f.eager && !f.dry && apply_allowed(f) && f.why == "30 s, eager");
    const Opts g = parse("30,dry,eager"), h = parse("30,eager,dry"), i = parse("30,dry,dry");
    CHECK(g.on && g.dry && g.eager && h.on && h.dry && h.eager && i.on && i.dry && !i.eager);
    CHECK(period(a) == S1);           // a quarter of 1 s, raised to 1 s
    CHECK(period(b) == 7'500'000'000ull);
    CHECK(period(c) == 15 * S1);      // a quarter of a day, cut to 15 s
}
void t_parse_bad() {
    for (const char* s: {"abc", "-5", "30s", " 30", "30 ", "86401", "100000", "0,dry", "000", "30,", "30,foo", ",dry", "30,,dry", "1e3", "on", "true", "30,DRY", "+30"}) {
        const Opts o = parse(s);
        CHECK(!o.on && !o.dry && !o.eager && o.idle_ns == 0);
        CHECK(o.why.find("does not parse") != std::string::npos && o.why.find(s) != std::string::npos);
    }
    CHECK(parse("30,foo").why.find("\"foo\"") != std::string::npos);
}

// ---- covers -------------------------------------------------------------------------------------------------------
void t_merged_hits() {
    const auto m = merged({{30, 40}, {10, 20}, {20, 25}, {5, 5}, {38, 50}, {60, 61}});
    CHECK(m.size() == 3 && m[0].lo == 10 && m[0].hi == 25 && m[1].lo == 30 && m[1].hi == 50 && m[2].lo == 60 && m[2].hi == 61);
    CHECK(hits(m, 24, 26) && hits(m, 10, 11) && hits(m, 0, 11) && hits(m, 49, 100) && hits(m, 60, 61));
    CHECK(!hits(m, 25, 30) && !hits(m, 0, 10) && !hits(m, 50, 60) && !hits(m, 61, 1000) && !hits({}, 0, 100));
}
void t_covers_classes() {
    std::vector<TView> v = {data_view(0, 2), eager_view(1, 2), lazy_view(4, 1), {ch(5), C, true, true, false}, zero_view(8, 1), {ch(9), 0, true, false, true}};
    const Covers c = cov(v);
    CHECK(c.all.size() == 3 && c.all[0].lo == ch(0) && c.all[0].hi == ch(3) && c.all[1].lo == ch(4) && c.all[1].hi == ch(6) && c.all[2].lo == ch(8) && c.all[2].hi == ch(9));
    CHECK(hits(c.eager, ch(5), ch(6)) && !hits(c.lazy, ch(5), ch(6))); // eager and lazy both: eager, as the import loop ranks them
    CHECK(hits(c.lazy, ch(4), ch(5)) && hits(c.data, ch(0), ch(1)) && !hits(c.data, ch(2), ch(3)));
    CHECK(c.zero.size() == 1 && c.zero[0].lo == ch(8) && c.zero[0].hi == ch(9)); // a view of size 0 is no view
}

// ---- idle ---------------------------------------------------------------------------------------------------------
void t_plan_off() {
    State      st;
    const Opts o = parse(nullptr);
    const Plan p = pass(o, st, {bo(0, 4, 1)}, {}, T0);
    CHECK(p.cuts.empty() && p.imported == 0 && st.passes == 0 && st.chunks.empty() && st.last_pass == 0);
}
void t_viewed_never() {
    State                    st;
    const Opts               o     = on(1, true);
    const std::vector<BoIn>  bos   = {bo(0, 3, 1)};
    const std::vector<TView> views = {eager_view(0, 1), data_view(1, 1), lazy_view(2, 1)};
    Plan                     p;
    for (int k = 0; k < 20; k++) {
        p = pass(o, st, bos, views, T0 + static_cast<uint64_t>(k) * 10 * S1);
        CHECK(p.cuts.empty() && p.ready == 0 && p.unviewed == 0);
    }
    CHECK(p.imported == 3 * C && p.eager_v == C && p.data_v == C && p.lazy_v == C);
    CHECK(st.chunks.size() == 3 && st.chunks[0].seen && st.chunks[0].eager && !st.chunks[1].eager && st.chunks[2].since == 0);
}
void t_idle_exact() {
    State      st;
    const Opts o = on(30);
    const std::vector<BoIn> bos = {bo(0, 2, 7)};
    pass(o, st, bos, {data_view(0, 2)}, T0); // both seen under a data view
    const std::vector<TView> later = {data_view(0, 1)};
    Plan p = pass(o, st, bos, later, T0 + 5 * S1); // chunk 1 under no view from here
    CHECK(p.cuts.empty() && p.unviewed == C && p.ready == 0 && st.chunks[1].since == T0 + 5 * S1);
    p = pass(o, st, bos, later, T0 + 35 * S1 - 1);
    CHECK(p.cuts.empty() && p.ready == 0);
    p = pass(o, st, bos, later, T0 + 35 * S1);
    CHECK(p.cuts.size() == 1 && p.ready == C && p.drop == C);
    CHECK(p.cuts.size() == 1 && p.cuts[0].id == 7 && p.cuts[0].dropped == std::vector<uint64_t> {ch(1)} && p.cuts[0].keep.size() == 1 && p.cuts[0].keep[0].lo == ch(0) &&
          p.cuts[0].keep[0].hi == ch(1));
}
void t_idle_restart() {
    State      st;
    const Opts o = on(30);
    const std::vector<BoIn> bos = {bo(0, 1, 1)};
    pass(o, st, bos, {data_view(0, 1)}, T0);
    pass(o, st, bos, {}, T0 + S1);                       // under no view from T0 + 1 s
    pass(o, st, bos, {data_view(0, 1)}, T0 + 20 * S1);   // under a view again
    Plan p = pass(o, st, bos, {}, T0 + 25 * S1);         // and not again from T0 + 25 s
    CHECK(p.cuts.empty() && st.chunks[0].since == T0 + 25 * S1);
    p = pass(o, st, bos, {}, T0 + 54 * S1);
    CHECK(p.cuts.empty());
    p = pass(o, st, bos, {}, T0 + 55 * S1);
    CHECK(p.cuts.size() == 1 && p.cuts[0].keep.empty());
}
void t_clock_back() {
    State      st;
    const Opts o = on(10);
    const std::vector<BoIn> bos = {bo(0, 1, 1)};
    pass(o, st, bos, {data_view(0, 1)}, T0);
    pass(o, st, bos, {}, T0 + 100 * S1);
    Plan p = pass(o, st, bos, {}, T0 + 50 * S1); // the clock went back: since is reset to now, nothing is ready
    CHECK(p.cuts.empty() && p.ready == 0 && st.chunks[0].since == T0 + 50 * S1);
    p = pass(o, st, bos, {}, T0 + 60 * S1);
    CHECK(p.cuts.size() == 1);
}
void t_due() {
    State      st;
    const Opts o = on(30); // period 7.5 s
    CHECK(due(o, st, T0));
    pass(o, st, {}, {}, T0);
    CHECK(!due(o, st, T0 + 7 * S1) && due(o, st, T0 + 7'500'000'000ull));
    const Opts one = on(1); // period 1 s
    State      s2;
    pass(one, s2, {}, {}, T0);
    CHECK(!due(one, s2, T0 + S1 - 1) && due(one, s2, T0 + S1));
}

// ---- never --------------------------------------------------------------------------------------------------------
void t_forced_never() {
    State      st;
    const Opts o = on(1, true);
    const std::vector<BoIn> bos = {bo(0, 2, 1)};
    const std::set<uint64_t> forced = {ch(1)};
    pass(o, st, bos, {data_view(0, 2)}, T0, forced);
    Plan p;
    for (int k = 1; k < 10; k++) p = pass(o, st, bos, {}, T0 + static_cast<uint64_t>(k) * 100 * S1, forced);
    CHECK(p.cuts.size() == 1 && p.cuts[0].dropped == std::vector<uint64_t> {ch(0)} && p.forced_u == C && p.unviewed == C);
    CHECK(st.chunks[1].since == 0);
}
void t_eager_word() {
    const std::vector<BoIn>  bos   = {bo(0, 1, 1)};
    const std::vector<TView> views = {eager_view(0, 1)};
    State                    a, b;
    pass(on(5), a, bos, views, T0);
    pass(on(5, true), b, bos, views, T0);
    pass(on(5), a, bos, {}, T0 + S1);
    pass(on(5, true), b, bos, {}, T0 + S1);
    const Plan pa = pass(on(5), a, bos, {}, T0 + 100 * S1);
    const Plan pb = pass(on(5, true), b, bos, {}, T0 + 100 * S1);
    CHECK(pa.cuts.empty() && pa.ready == C && pa.seen_eager == C && pa.never_seen == 0);
    CHECK(pb.cuts.size() == 1 && pb.seen_eager == C);
}
void t_zero_never() {
    const std::vector<BoIn> bos = {bo(0, 2, 1)};
    State                   st;
    const Opts              o = on(1, true);
    pass(o, st, bos, {zero_view(0, 1), {ch(1), C / 2, false, false, true}}, T0, kNone, true); // a zero-list heap that is not eager, too
    Plan p;
    for (int k = 1; k < 5; k++) p = pass(o, st, bos, {}, T0 + static_cast<uint64_t>(k) * 100 * S1, kNone, true);
    CHECK(p.cuts.empty() && p.ready == 2 * C && p.seen_eager == 2 * C);
}
void t_never_seen() {
    const std::vector<BoIn> bos = {bo(0, 1, 1)};
    State                   a, b, c;
    Plan                    pa, pb, pc;
    for (int k = 0; k < 5; k++) { // imported, and never under a view at a pass
        const uint64_t t = T0 + static_cast<uint64_t>(k) * 100 * S1;
        pa = pass(on(1), a, bos, {}, t);
        pb = pass(on(1, true), b, bos, {}, t);
        pc = pass(on(1, true), c, bos, {}, t, kNone, true);
    }
    CHECK(pa.cuts.empty() && pa.never_seen == C && pa.ready == C);
    CHECK(pb.cuts.size() == 1 && pb.never_seen == C);
    CHECK(pc.cuts.empty() && pc.never_seen == C); // the zero skip is set: it might be one of its heaps
}
void t_unaligned() {
    State                   st;
    const Opts              o   = on(1, true);
    const std::vector<BoIn> bos = {{ch(0) + 0x1000, C, 3, 0}, {ch(4), C + 0x1000, 4, 0}, {ch(8), 0, 5, 0}};
    Plan                    p;
    for (int k = 0; k < 5; k++) p = pass(o, st, bos, {}, T0 + static_cast<uint64_t>(k) * 100 * S1);
    CHECK(p.cuts.empty() && p.imported == 2 * C + 0x1000 && st.chunks.empty());
}

// ---- cuts ---------------------------------------------------------------------------------------------------------
// Five chunks: 0 and 3 under views, 1, 2 and 4 under none after T0.
Plan five(State& st, const Opts& o, uint32_t maps = 0) {
    const std::vector<BoIn> bos = {bo(0, 5, 9, maps)};
    pass(o, st, bos, {data_view(0, 5)}, T0);
    pass(o, st, bos, {data_view(0, 1), data_view(3, 1)}, T0 + S1);
    return pass(o, st, bos, {data_view(0, 1), data_view(3, 1)}, T0 + 100 * S1);
}
void t_split_runs() {
    State      st;
    const Plan p = five(st, on(10));
    CHECK(p.cuts.size() == 1 && p.drop == 3 * C && p.data_v == 2 * C && p.unviewed == 3 * C);
    const Cut& c = p.cuts[0];
    CHECK(c.off == ch(0) && c.size == 5 * C && c.id == 9 && c.drop == 3 * C);
    CHECK(c.dropped == (std::vector<uint64_t> {ch(1), ch(2), ch(4)}));
    CHECK(c.keep.size() == 2 && c.keep[0].lo == ch(0) && c.keep[0].hi == ch(1) && c.keep[1].lo == ch(3) && c.keep[1].hi == ch(4));
}
void t_whole() {
    State                   st;
    const Opts              o   = on(10);
    const std::vector<BoIn> bos = {bo(0, 3, 4), bo(3, 1, 5)};
    pass(o, st, bos, {data_view(0, 4)}, T0);
    const Plan p = pass(o, st, bos, {data_view(3, 1)}, T0 + 50 * S1);
    CHECK(p.cuts.empty());
    const Plan q = pass(o, st, bos, {data_view(3, 1)}, T0 + 70 * S1);
    CHECK(q.cuts.size() == 1 && q.cuts[0].keep.empty() && q.cuts[0].id == 4 && q.cuts[0].drop == 3 * C && q.data_v == C);
}
void t_no_splits() {
    State                   st;
    const Opts              o   = on(1);
    const std::vector<BoIn> bos = {bo(0, 2, 1), bo(2, 2, 2)};
    pass(o, st, bos, {data_view(0, 4)}, T0);
    pass(o, st, bos, {data_view(0, 1)}, T0 + S1);
    const Plan p = plan(o, st, bos, cov({data_view(0, 1)}), kNone, T0 + 10 * S1, 512, 32, false, false);
    CHECK(p.cuts.size() == 1 && p.cuts[0].id == 2 && p.cuts[0].keep.empty() && p.nosplit == 1 && p.deferred == 0);
}
void t_map_budget() {
    State                   st;
    const Opts              o   = on(1);
    const std::vector<BoIn> bos = {bo(0, 2, 1, 300), bo(2, 2, 2, 300), bo(4, 1, 3, 0)};
    const std::vector<TView> v1 = {data_view(0, 5)}, v2 = {data_view(0, 1), data_view(2, 1)};
    pass(o, st, bos, v1, T0);
    pass(o, st, bos, v2, T0 + S1);
    const Plan p = plan(o, st, bos, cov(v2), kNone, T0 + 10 * S1, 512, 32, true, false);
    CHECK(p.cuts.size() == 2 && p.cuts[0].id == 1 && p.cuts[0].maps == 300 && p.cuts[1].id == 3 && p.deferred == 1 && st.deferred == 1);
    const Plan q = plan(o, st, bos, cov(v2), kNone, T0 + 20 * S1, 100, 32, true, false);
    CHECK(q.cuts.size() == 1 && q.cuts[0].id == 3 && q.deferred == 2);
}
void t_max_cuts() {
    State                   st;
    const Opts              o   = on(1);
    const std::vector<BoIn> bos = {bo(0, 1, 1), bo(1, 1, 2), bo(2, 1, 3)};
    pass(o, st, bos, {data_view(0, 3)}, T0);
    pass(o, st, bos, {}, T0 + S1);
    const Plan p = plan(o, st, bos, cov({}), kNone, T0 + 10 * S1, 512, 2, true, false);
    CHECK(p.cuts.size() == 2 && p.cuts[0].id == 1 && p.cuts[1].id == 2 && p.deferred == 1 && p.ready == 3 * C && p.drop == 2 * C);
}
void t_dry() {
    State      st;
    const Opts o = on(10, false, true);
    const Plan p = five(st, o);
    CHECK(!apply_allowed(o) && p.cuts.size() == 1 && p.drop == 3 * C); // the plan is made; the host cuts nothing (apply_allowed)
    CHECK(st.released.empty() && st.cuts == 0);
}
void t_apply_undo() {
    State      st;
    const Plan p   = five(st, on(10));
    const Cut& cut = p.cuts[0];
    std::vector<TBo> bos = {{ch(0) - 4 * C, 4 * C, 8, 11}, {ch(0), 5 * C, 9, 22}, {ch(5), C, 10, 33}};
    const std::vector<TBo> before = bos;
    uint64_t old_t = 0;
    CHECK(!apply_cut(bos, cut, {100}, T0, &old_t));      // one id for two runs: refused, nothing changed
    Cut other = cut;
    other.id  = 77;
    CHECK(!apply_cut(bos, other, {100, 101}, T0, &old_t)); // another BO there: refused
    CHECK(bos.size() == 3 && bos[1].id == 9);
    CHECK(apply_cut(bos, cut, {100, 101}, T0 + 5, &old_t) && old_t == 22);
    CHECK(bos.size() == 4 && bos[1].off == ch(0) && bos[1].size == C && bos[1].id == 100 && bos[1].t_ns == T0 + 5 && bos[2].off == ch(3) && bos[2].size == C && bos[2].id == 101 &&
          bos[3].id == 10);
    CHECK(covered_end(bos, ch(1)) == 0 && covered_end(bos, ch(2)) == 0 && covered_end(bos, ch(4)) == 0);
    CHECK(covered_end(bos, ch(0)) == ch(1) && covered_end(bos, ch(3)) == ch(4) && covered_end(bos, ch(5)) == ch(6) && covered_end(bos, ch(0) - 4 * C) == ch(0));
    CHECK(!undo_cut(bos, cut, {100, 102}, old_t)); // a wrong id: refused
    CHECK(undo_cut(bos, cut, {100, 101}, old_t));
    bool same = bos.size() == before.size();
    for (size_t i = 0; same && i < bos.size(); i++) same = bos[i].off == before[i].off && bos[i].size == before[i].size && bos[i].id == before[i].id && bos[i].t_ns == before[i].t_ns;
    CHECK(same);
    // a chunk cut out and imported again meanwhile: the BO cannot come back
    CHECK(apply_cut(bos, cut, {100, 101}, T0, &old_t));
    insert_bo(bos, ch(2), C, 200, T0);
    CHECK(!undo_cut(bos, cut, {100, 101}, old_t) && covered_end(bos, ch(2)) == ch(3));
}
void t_record() {
    State      st;
    const Plan p = five(st, on(10));
    note_cut(st, p.cuts[0]);
    CHECK(st.cuts == 1 && st.splits == 1 && st.wholes == 0 && st.cut_bytes == 3 * C && st.released == (std::set<uint64_t> {ch(1), ch(2), ch(4)}));
    note_undo(st, p.cuts[0]);
    CHECK(st.cuts == 0 && st.splits == 0 && st.undone == 1 && st.cut_bytes == 0 && st.released.empty());
    Cut whole;
    whole.dropped = {ch(7)};
    whole.drop    = C;
    note_cut(st, whole);
    CHECK(st.wholes == 1 && st.released.size() == 1);
    note_back(st, ch(7));
    note_back(st, ch(7)); // a second time: nothing
    CHECK(st.back_bytes == C && st.released.empty());
}
void t_prune() {
    State      st;
    const Opts o = on(10);
    const Plan p = five(st, o);
    CHECK(st.chunks.size() == 5);
    std::vector<BoIn> after = {bo(0, 1, 100), bo(3, 1, 101)}; // the cut applied
    pass(o, st, after, {data_view(0, 1), data_view(3, 1)}, T0 + 101 * S1);
    CHECK(st.chunks.size() == 2 && st.chunks[0].off == ch(0) && st.chunks[1].off == ch(3) && p.cuts.size() == 1);
}
void t_state_across_merge() {
    // The merge joins two BOs into one: the chunks keep their times.
    State      st;
    const Opts o = on(30);
    pass(o, st, {bo(0, 1, 1), bo(1, 1, 2)}, {data_view(0, 2)}, T0);
    pass(o, st, {bo(0, 1, 1), bo(1, 1, 2)}, {data_view(0, 1)}, T0 + 10 * S1);
    const Plan p = pass(o, st, {bo(0, 2, 3)}, {data_view(0, 1)}, T0 + 40 * S1);
    CHECK(p.cuts.size() == 1 && p.cuts[0].id == 3 && p.cuts[0].dropped == std::vector<uint64_t> {ch(1)});
}

// ---- re-import ----------------------------------------------------------------------------------------------------
void t_reviewed() {
    const std::set<uint64_t> rel = {ch(1), ch(2), ch(4), ch(9)};
    const std::vector<TView> v   = {
        {ch(2) + C / 2, 0x10000, false, false, false}, // 64 KiB inside chunk 2
        {ch(3), C, false, false, false},               // ends where chunk 4 starts: not chunk 4
        {ch(4) - C / 2, C, true, false, false},        // half in chunk 3, half in chunk 4
        {ch(9), 0, false, false, false},               // empty
        {ch(2), C, false, true, false},                // chunk 2 again
    };
    CHECK(reviewed(rel, v) == (std::vector<uint64_t> {ch(2), ch(4)}));
    const std::vector<TView> inside = {{ch(2) + C / 2, 0x10000, false, false, false}}; // only a view that starts inside the chunk
    CHECK(reviewed(rel, inside) == std::vector<uint64_t> {ch(2)});
    CHECK(reviewed(std::set<uint64_t> {}, v).empty() && reviewed(rel, std::vector<TView> {}).empty());
}
void t_runs() {
    const std::vector<uint64_t> c = {ch(0), ch(1), ch(2), ch(5), ch(6)};
    const auto                  a = runs(c, 2 * C); // 4 MiB: two chunks a run
    CHECK(a.size() == 3 && a[0].lo == ch(0) && a[0].hi == ch(2) && a[1].lo == ch(2) && a[1].hi == ch(3) && a[2].lo == ch(5) && a[2].hi == ch(7));
    const auto b = runs(c, 64ull << 20u);
    CHECK(b.size() == 2 && b[0].lo == ch(0) && b[0].hi == ch(3) && b[1].lo == ch(5) && b[1].hi == ch(7));
    CHECK(runs({}, C).empty() && runs({ch(3)}, C).size() == 1);
}
void t_reimport_cycle() {
    // The host's sequence on a BO list: cut, released; a view over a cut chunk again; the chunk not covered, imported as
    // a run; the released set empty; the next pass sees a fresh chunk under a view; under no view again, it waits the
    // whole idle time anew.
    State            st;
    const Opts       o   = on(10);
    const Plan       p   = five(st, o);
    std::vector<TBo> bos = {{ch(0), 5 * C, 9, 1}};
    uint64_t         old_t = 0;
    CHECK(apply_cut(bos, p.cuts[0], {100, 101}, T0 + 100 * S1, &old_t));
    note_cut(st, p.cuts[0]);
    CHECK(st.chunks.size() == 2 && st.chunks[0].off == ch(0) && st.chunks[1].off == ch(3)); // the cut chunks' records are gone
    const std::vector<TView> views = {data_view(0, 1), data_view(3, 1), lazy_view(4, 1)}; // chunk 4 under a (lazy) view again
    const auto back = reviewed(st.released, views);
    CHECK(back == std::vector<uint64_t> {ch(4)} && covered_end(bos, ch(4)) == 0);
    for (const auto& r: runs(back, 64ull << 20u)) {
        insert_bo(bos, r.lo, r.hi - r.lo, 102, T0 + 101 * S1);
        for (uint64_t c = r.lo; c < r.hi; c += kChunk) note_back(st, c);
    }
    CHECK(covered_end(bos, ch(4)) == ch(5) && st.released == (std::set<uint64_t> {ch(1), ch(2)}) && st.back_bytes == C);
    std::vector<BoIn> in;
    for (const auto& b: bos) in.push_back({b.off, b.size, b.id, 0});
    Plan q = pass(o, st, in, views, T0 + 102 * S1);
    CHECK(q.cuts.empty() && q.lazy_v == C && q.data_v == 2 * C && st.chunks.size() == 3 && st.chunks[2].off == ch(4) && st.chunks[2].seen && st.chunks[2].since == 0);
    q = pass(o, st, in, {data_view(0, 1), data_view(3, 1)}, T0 + 103 * S1);
    CHECK(q.cuts.empty() && st.chunks[2].since == T0 + 103 * S1);
    q = pass(o, st, in, {data_view(0, 1), data_view(3, 1)}, T0 + 113 * S1);
    CHECK(q.cuts.size() == 1 && q.cuts[0].id == 102 && q.cuts[0].keep.empty());
    // the eager path imported a released chunk in the same sync: only the record changes
    note_back(st, ch(1));
    CHECK(st.released == std::set<uint64_t> {ch(2)} && st.back_bytes == 2 * C);
    // a chunk imported again whose view is gone by the next pass: never seen, so it stays (without the eager word)
    insert_bo(bos, ch(2), C, 103, T0 + 114 * S1);
    note_back(st, ch(2));
    in.clear();
    for (const auto& b: bos) in.push_back({b.off, b.size, b.id, 0});
    pass(o, st, in, {data_view(0, 1), data_view(3, 1)}, T0 + 115 * S1);
    q          = pass(o, st, in, {data_view(0, 1), data_view(3, 1)}, T0 + 200 * S1);
    bool no103 = true;
    for (const auto& c: q.cuts) no103 = no103 && c.id != 103;
    CHECK(no103 && q.never_seen == C && st.released.empty() && st.back_bytes == 3 * C);
}

// ---- env ----------------------------------------------------------------------------------------------------------
bool g_env_on = false;
void t_env() {
    const char* e = std::getenv("BC5_DIRECT_LAZY_RELEASE");
    const Opts  o = parse(e);
    CHECK(o.on == g_env_on);
    State                   st;
    const std::vector<BoIn> bos = {bo(0, 2, 1)};
    const uint64_t          idle = o.on ? o.idle_ns : 30 * S1;
    pass(o, st, bos, {data_view(0, 2)}, T0);
    pass(o, st, bos, {data_view(0, 1)}, T0 + S1);
    const Plan p = pass(o, st, bos, {data_view(0, 1)}, T0 + S1 + idle);
    if (o.on) {
        CHECK(p.cuts.size() == 1 && p.cuts[0].dropped == std::vector<uint64_t> {ch(1)} && st.passes == 3);
        CHECK(apply_allowed(o) == !o.dry);
    } else {
        CHECK(p.cuts.empty() && p.imported == 0 && st.passes == 0 && st.chunks.empty() && !due(o, st, T0) && !apply_allowed(o));
    }
}

struct Case {
    const char* name;
    void (*run)();
};
const Case kCases[] = {
    {"parse: off", t_parse_off},          {"parse: on", t_parse_on},
    {"parse: not parsing", t_parse_bad},  {"covers: merged, hits", t_merged_hits},
    {"covers: classes", t_covers_classes}, {"plan: off", t_plan_off},
    {"never: under views", t_viewed_never}, {"idle: exact", t_idle_exact},
    {"idle: restart", t_idle_restart},    {"idle: clock back", t_clock_back},
    {"idle: due", t_due},                 {"never: forced", t_forced_never},
    {"never: eager word", t_eager_word},  {"never: zero list", t_zero_never},
    {"never: never seen", t_never_seen},  {"never: unaligned BO", t_unaligned},
    {"cuts: split runs", t_split_runs},   {"cuts: whole BO", t_whole},
    {"cuts: splits off", t_no_splits},    {"cuts: mapping budget", t_map_budget},
    {"cuts: per pass", t_max_cuts},       {"cuts: dry", t_dry},
    {"cuts: apply and undo", t_apply_undo}, {"cuts: record", t_record},
    {"cuts: state pruned", t_prune},      {"cuts: state across a merge", t_state_across_merge},
    {"re-import: reviewed", t_reviewed},  {"re-import: runs", t_runs},
    {"re-import: cycle", t_reimport_cycle}, {"env: the switch as set", t_env},
};

} // namespace

int main(int argc, char** argv) {
    static_assert(kChunk == C, "the chunk is 2 MiB");
    const Opts env = parse(std::getenv("BC5_DIRECT_LAZY_RELEASE"));
    g_env_on       = env.on;
    const char* mode = env.on ? "on" : "off";
    if (argc > 1 && std::strcmp(argv[1], mode) != 0) {
        std::printf("lzr0401: the argument %s disagrees with BC5_DIRECT_LAZY_RELEASE (%s: %s)\n", argv[1], mode, env.why.c_str());
        return 2;
    }
    std::printf("lzr0401: BC5_DIRECT_LAZY_RELEASE %s (%s)\n", mode, env.why.c_str());
    int passed = 0, total = 0;
    for (const Case& c: kCases) {
        g_case_fail = 0;
        g_why.clear();
        const int before = g_checks;
        c.run();
        total++;
        if (g_case_fail == 0) {
            passed++;
            std::printf("ok   %-28s %d checks\n", c.name, g_checks - before);
        } else {
            std::printf("FAIL %-28s %d of %d checks failed; first: %s\n", c.name, g_case_fail, g_checks - before, g_why.c_str());
        }
    }
    if (passed != total) {
        std::printf("lzr0401: %s %d of %d failed\n", mode, total - passed, total);
        return 1;
    }
    std::printf("lzr0401: %s %d of %d; end\n", mode, passed, total);
    return 0;
}
