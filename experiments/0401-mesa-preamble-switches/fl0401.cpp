// BC5 experiment 0401, exp 0404's switches (BC5_DIRECT_FL_CRUMBS, BC5_DIRECT_FL_SKIP_ES): the CPU test of fl_scan.inc, the
// exact text mkfl0401.py puts into the unit. Synthetic dcbs only: fast-launch draws and others, ES programs in and out of
// the skip list, state set by SET_*_REG, by LOAD_*_REG_INDEX pair tables and the other LOAD forms, state carried from a
// previous buffer, draws inside COND_EXEC ranges (the counts grown by exactly the crumbs inside them, or left alone when
// they cannot grow), multi-draws, the ring's wrap, the offset maps, the probe's reading of the slots and of a ring entry,
// and the list parser. The expected packets are spelled out here with their own constants, not taken from the include.
// Build (on the box, in the container): clang++ -std=c++20 -Wall -Wextra -Werror -I<dir of fl_scan.inc> fl0401.cpp
// Prints "fl0401: N of N cases; end" and exits 0 only then. No GPU, no emulator objects.
#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <initializer_list>
#include <map>
#include <string>
#include <utility>
#include <vector>

#include "fl_scan.inc"

namespace {

constexpr uint64_t kShadow = 0x100004000000ull; // the backend's GDS shadow VA (direct.cpp kShadowVa)
constexpr uint64_t kSubmit = 595662;            // exp 0404's dcb
constexpr uint32_t kFl     = 0x00482030u;       // exp 0404's VGT_SHADER_STAGES_EN: GS_FAST_LAUNCH 1
constexpr uint32_t kNgg    = 0x00402030u;       // the same without GS_FAST_LAUNCH
constexpr uint32_t kEs     = 0x11d00f85u, kEs2 = 0x11d00f8du, kEs3 = 0x11d00cdeu, kEsOther = 0x11d01000u;
constexpr uint64_t kBase1  = 0x1193ad3900ull;   // exp 0404's SET_BASE
constexpr uint64_t kVa     = 0x1123502050ull, kVb = 0x2240fda0ull, kVc = 0x1130000000ull, kVd = 0x1140000000ull;

uint32_t lo(uint64_t a) { return static_cast<uint32_t>(a); }
uint32_t hi16(uint64_t a) { return static_cast<uint32_t>(a >> 32u) & 0xffffu; }
uint32_t hdr(uint32_t op, uint32_t len) { return 0xC0000000u | ((len - 2u) << 16u) | (op << 8u); }

struct Ib {
    std::vector<uint32_t> d;
    uint32_t at() const { return static_cast<uint32_t>(d.size()); }
    Ib& pkt(uint32_t op, std::initializer_list<uint32_t> body) {
        d.push_back(hdr(op, 1u + static_cast<uint32_t>(body.size())));
        d.insert(d.end(), body);
        return *this;
    }
    Ib& ctx(uint32_t reg, std::initializer_list<uint32_t> v) {
        d.push_back(hdr(0x69, 2u + static_cast<uint32_t>(v.size())));
        d.push_back(reg);
        d.insert(d.end(), v);
        return *this;
    }
    Ib& sh(uint32_t reg, std::initializer_list<uint32_t> v, uint32_t op = 0x76) {
        d.push_back(hdr(op, 2u + static_cast<uint32_t>(v.size())));
        d.push_back(reg);
        d.insert(d.end(), v);
        return *this;
    }
    Ib& stages(uint32_t v) { return ctx(0x2d5, {v}); }
    Ib& es(uint32_t lo_value) { return sh(0xc8, {lo_value, 0u}); } // SPI_SHADER_PGM_LO_ES, HI_ES
    Ib& ud(uint32_t k, uint64_t base) { return sh(0x8cu + k, {lo(base), static_cast<uint32_t>(base >> 32u)}); }
    Ib& base1(uint64_t a) { return pkt(0x11, {1u, lo(a), static_cast<uint32_t>(a >> 32u)}); }
    Ib& draw_ind(uint32_t off) { return pkt(0x24, {off, 0u, 0u, 0u}); }
    Ib& draw_idx_ind(uint32_t off) { return pkt(0x25, {off, 0u, 0u, 0u}); }
    Ib& draw_auto(uint32_t count) { return pkt(0x2d, {count, 2u}); }
    Ib& draw_idx2(uint32_t count) { return pkt(0x27, {count, 0x1000u, 0u, count, 0u}); }
    Ib& multi(uint32_t op, uint32_t off, uint32_t count, uint32_t stride) { return pkt(op, {off, 0u, 0u, 0u, count, 0u, 0u, stride, 0u}); }
    Ib& cond(uint32_t count) { return pkt(0x22, {0x5000u, 0x11u, 0u, count}); }
    Ib& load_pairs(uint32_t op, uint64_t table, uint32_t pairs) { return pkt(op, {lo(table), hi16(table), 0x80000000u, pairs}); }
    Ib& load_index_range(uint32_t op, uint64_t a, uint32_t reg, uint32_t count) { return pkt(op, {lo(a), hi16(a), reg, count}); }
    Ib& load_reg(uint32_t op, uint64_t base, uint32_t reg, uint32_t count) { return pkt(op, {lo(base), hi16(base), reg, count}); }
    Ib& clear(uint32_t cmd) { return pkt(0x12, {cmd}); }
    Ib& ib2() { return pkt(0x3f, {0x1000u, 0u, 16u}); }
    Ib& nop(uint32_t len) {
        d.push_back(hdr(0x10, len));
        d.insert(d.end(), len - 1u, 0u);
        return *this;
    }
    Ib& fl_state(uint32_t es_lo) { return stages(kFl).es(es_lo); }
};

struct Mem { // GPU address -> dwords the "CPU" may read
    std::map<uint64_t, std::vector<uint32_t>> r;
    void put(uint64_t a, std::vector<uint32_t> v) { r[a] = std::move(v); }
    const uint32_t* operator()(uint64_t a, uint64_t bytes) const {
        for (const auto& [base, v]: r) {
            if (a >= base && a + bytes <= base + v.size() * 4u && (a - base) % 4u == 0) return v.data() + (a - base) / 4u;
        }
        return nullptr;
    }
};
Mem standard_mem() {
    Mem m;
    m.put(kBase1, std::vector<uint32_t>(0x1000, 0u));
    m.r[kBase1][0x1620 / 4] = 3479; // 0404's arguments at +0x1620: 3479 vertices x 1 instance
    m.r[kBase1][0x1620 / 4 + 1] = 1;
    m.put(kVa, {0xa0, 0xa1, 0xa2, 0xa3, 0xa4, 0xa5, 0xa6, 0xa7, 0xa8}); // one dword more: the filter checks 8 bytes per copy
    m.put(kVb, {0xb0, 0xb1, 0xb2, 0xb3, 0xb4, 0xb5, 0xb6, 0xb7, 0xb8});
    m.put(kVd, {0xd0, 0xd1, 0xd2, 0xd3, 0xd4, 0xd5, 0xd6, 0xd7});       // 32 bytes and nothing after them
    m.put(kVc, {0xc0, 0xc1, 0xc2, 0xc3, 0xc4, 0xc5, 0xc6, 0xc7, 0xc8, 0xc9});
    return m;
}

struct Run {
    FlPlan                plan;
    std::vector<uint32_t> out, o2n, n2o;
    uint32_t              made = 0;
};
Run run(const Ib& ib, FlState& st, const Mem& mem, bool crumbs, const std::vector<uint32_t>* skip = nullptr, const std::vector<uint32_t>* drops = nullptr,
        bool draws = true) {
    Run       r;
    FlOptions o;
    o.draws       = draws;
    o.crumbs      = crumbs;
    o.skip_es     = skip;
    o.drops       = drops;
    r.plan.crumbs = crumbs;
    if (crumbs) r.plan.lay = fl_layout(kShadow);
    fl_scan(ib.d.data(), ib.at(), mem, st, o, r.plan);
    if (crumbs) r.made = fl_build(ib.d.data(), ib.at(), r.plan, kSubmit, r.out, r.o2n, r.n2o);
    return r;
}
Run run1(const Ib& ib, const Mem& mem, bool crumbs, const std::vector<uint32_t>* skip = nullptr, const std::vector<uint32_t>* drops = nullptr) {
    FlState st;
    return run(ib, st, mem, crumbs, skip, drops);
}

uint64_t id_of(uint32_t at) { return (static_cast<uint64_t>(at) << 32u) | static_cast<uint32_t>(kSubmit); }
// The crumbs as fl0401-notes.md spells them: WRITE_DATA 0xC0043700 / 0x00100500, COPY_DATA 0xC0044000 / 0x00100501,
// RELEASE_MEM 0xC0064900 / 0x00000528 / 0x40000000; slots at the shadow + 0x8000 / 0x8008, entry k at + 0x8100 + 128 k.
std::vector<uint32_t> want_pre(uint32_t at, uint32_t entry, uint64_t args, uint64_t ba, uint64_t bb, uint64_t bc) {
    const uint64_t        e  = kShadow + 0x8100u + 128ull * entry, id = id_of(at);
    std::vector<uint32_t> w;
    const auto            wr = [&](uint64_t va) { w.insert(w.end(), {0xC0043700u, 0x00100500u, lo(va), hi16(va), lo(id), static_cast<uint32_t>(id >> 32u)}); };
    const auto            cp = [&](uint64_t s, uint64_t dst) { w.insert(w.end(), {0xC0044000u, 0x00100501u, lo(s), hi16(s), lo(dst), hi16(dst)}); };
    wr(e);
    for (uint32_t k = 0; args != 0 && k < 4; k++) cp(args + 4u * k, e + 8u + 4u * k);
    const uint64_t bases[3] = {ba, bb, bc};
    for (uint32_t b = 0; b < 3; b++) {
        for (uint32_t k = 0; bases[b] != 0 && k < 8; k++) cp(bases[b] + 4u * k, e + 24u + 32u * b + 4u * k);
    }
    wr(e + 120u);
    wr(kShadow + 0x8000u);
    return w;
}
std::vector<uint32_t> want_post(uint32_t at) {
    const uint64_t id = id_of(at), done = kShadow + 0x8008u;
    return {0xC0064900u, 0x00000528u, 0x40000000u, lo(done), hi16(done), lo(id), static_cast<uint32_t>(id >> 32u), 0u};
}
struct Ins {
    uint32_t              at;
    std::vector<uint32_t> pre, post;
};
// ib with the insertions, and the COND_EXEC at old offset c given the count v (hand-computed by the case)
std::vector<uint32_t> laid(const Ib& ib, const std::vector<Ins>& ins, std::initializer_list<std::pair<uint32_t, uint32_t>> counts = {}) {
    std::vector<uint32_t>        w;
    std::map<uint32_t, uint32_t> pos;
    for (uint32_t q = 0; q < ib.at();) {
        const uint32_t h = ib.d[q], c = (h >> 16u) & 0x3fffu;
        const uint32_t len = std::min((h >> 30u) == 3 && c != 0x3fffu ? c + 2u : 1u, ib.at() - q);
        const Ins*     in  = nullptr;
        for (const Ins& i: ins) in = i.at == q ? &i : in;
        if (in != nullptr) w.insert(w.end(), in->pre.begin(), in->pre.end());
        pos[q] = static_cast<uint32_t>(w.size());
        w.insert(w.end(), ib.d.begin() + q, ib.d.begin() + q + len);
        if (in != nullptr) w.insert(w.end(), in->post.begin(), in->post.end());
        q += len;
    }
    for (const auto& [c, v]: counts) w[pos[c] + 4u] = (w[pos[c] + 4u] & ~0x3fffu) | v;
    return w;
}

int g_cases = 0, g_bad = 0;
bool check(const char* name, bool ok, const std::string& why = "") {
    g_cases++;
    if (ok) return true;
    g_bad++;
    std::printf("fl0401: FAIL %s%s%s\n", name, why.empty() ? "" : ": ", why.c_str());
    return false;
}
std::string diff(const std::vector<uint32_t>& got, const std::vector<uint32_t>& want) {
    char b[200];
    for (std::size_t k = 0; k < std::max(got.size(), want.size()); k++) {
        const uint32_t g = k < got.size() ? got[k] : 0xdeadu, w = k < want.size() ? want[k] : 0xdeadu;
        if (g != w || k >= got.size() || k >= want.size()) {
            std::snprintf(b, sizeof(b), "%zu dwords (want %zu), first difference at %zu: %08x, want %08x", got.size(), want.size(), k, g, w);
            return b;
        }
    }
    return "";
}
// The maps both ways: every title packet at its new place, unchanged but for a COND_EXEC count, and back; every other
// packet of the copy one of the three crumbs.
bool maps_ok(const Ib& ib, const Run& r, std::string& why) {
    uint32_t packets = 0;
    for (uint32_t q = 0; q < ib.at();) {
        const uint32_t h = ib.d[q], c = (h >> 16u) & 0x3fffu, len = std::min((h >> 30u) == 3 && c != 0x3fffu ? c + 2u : 1u, ib.at() - q);
        const uint32_t p = r.o2n[q];
        if (p == ~0u || p + len > r.out.size() || r.n2o[p] != q) return why = "packet " + std::to_string(q) + " not mapped both ways", false;
        for (uint32_t k = 0; k < len; k++) {
            const bool cond_count = ((h >> 8u) & 0xffu) == 0x22 && k == 4;
            if (!cond_count && r.out[p + k] != ib.d[q + k]) return why = "packet " + std::to_string(q) + " changed", false;
        }
        packets++;
        q += len;
    }
    uint32_t back = 0;
    for (uint32_t p = 0; p < r.out.size();) {
        const uint32_t h = r.out[p], c = (h >> 16u) & 0x3fffu, len = (h >> 30u) == 3 && c != 0x3fffu ? c + 2u : 1u;
        if (r.n2o[p] != ~0u) {
            back++;
        } else if (h != 0xC0043700u && h != 0xC0044000u && h != 0xC0064900u) {
            return why = "a packet at " + std::to_string(p) + " that is neither the title's nor a crumb", false;
        }
        p += len;
    }
    return back == packets || (why = "the copy has " + std::to_string(back) + " title packets, the buffer " + std::to_string(packets), false);
}

void case_one_draw() {
    const Mem m = standard_mem();
    Ib        ib;
    ib.fl_state(kEs).ud(8, kVa).ud(20, kVb).ud(24, kVc).base1(kBase1);
    const uint32_t at = ib.at();
    ib.draw_ind(0x1620).nop(2);
    const Run      r = run1(ib, m, true);
    const FlDraw*  d = r.plan.draws.empty() ? nullptr : &r.plan.draws[0];
    check("one fast-launch DRAW_INDIRECT: planned", r.plan.draws.size() == 1 && d->cls == 3 && d->crumbs && !d->drop && d->at == at && d->op == 0x24 && r.plan.fl == 1);
    check("... its arguments and three V# bases", d != nullptr && d->args == kBase1 + 0x1620 && d->base[0] == kVa && d->base[1] == kVb && d->base[2] == kVc);
    check("... read at submit", d != nullptr && d->snap[0] == 3479 && d->snap[1] == 1 && d->snap[4] == 0xa0 && d->snap[11] == 0xa7 && d->snap[12] == 0xb0 && d->snap[27] == 0xc7);
    check("... id, entry", d != nullptr && d->id == id_of(at) && d->entry == 0 && r.made == 1 && r.plan.with_crumbs == 1);
    const std::vector<uint32_t> pre = want_pre(at, 0, kBase1 + 0x1620, kVa, kVb, kVc), want = laid(ib, {{at, pre, want_post(at)}});
    check("... the exact crumbs: head, 4 + 24 copies, tail, issued, the draw, done", r.out == want, diff(r.out, want));
    check("... 194 dwords added", r.out.size() == ib.d.size() + 194u && pre.size() == 186u);
    std::string why;
    check("... the offsets mapped both ways", maps_ok(ib, r, why), why);
    check("... the draw's new offset; the crumbs map to no title packet", d != nullptr && d->new_at == at + pre.size() && r.o2n[at] == d->new_at && r.n2o[d->new_at] == at && r.n2o[at] == ~0u);
}

void case_not_fast_launch() {
    const Mem m = standard_mem();
    Ib        ib;
    ib.stages(kNgg).es(kEs).base1(kBase1).draw_ind(0x1620).stages(0).draw_auto(3);
    const Run r = run1(ib, m, true);
    check("NGG without GS_FAST_LAUNCH, and 0: no crumbs, nothing laid", r.plan.draws.empty() && r.plan.not_fl == 2 && r.plan.total == 2 && r.made == 0 && r.out.empty());
}

void case_skip() {
    const Mem                   m    = standard_mem();
    const std::vector<uint32_t> skip = {kEs3, kEs, kEs2}; // fl_parse_es_list sorts; fl_scan wants it sorted
    std::vector<uint32_t>       sorted(skip);
    std::sort(sorted.begin(), sorted.end());
    Ib ib;
    ib.fl_state(kEs).base1(kBase1);
    const uint32_t a = ib.at();
    ib.draw_ind(0x1620).es(kEsOther);
    const uint32_t b = ib.at();
    ib.draw_auto(3).stages(kNgg).es(kEs2);
    const uint32_t c = ib.at();
    ib.draw_auto(3);
    Run r = run1(ib, m, true, &sorted);
    check("ES listed, fast-launch: dropped, no crumbs", r.plan.draws.size() == 2 && r.plan.draws[0].at == a && r.plan.draws[0].drop && !r.plan.draws[0].crumbs && r.plan.skipped == 1);
    check("ES not listed: crumbs", r.plan.draws.size() == 2 && r.plan.draws[1].at == b && r.plan.draws[1].crumbs && !r.plan.draws[1].drop && r.made == 1);
    check("ES listed, not fast-launch: neither", r.plan.not_fl == 1 && r.plan.draws.size() == 2 && r.plan.draws.back().at != c);
    const std::vector<uint32_t> want = laid(ib, {{b, want_pre(b, 0, 0, 0, 0, 0), want_post(b)}});
    check("... the dropped draw keeps no crumbs, the other has them", r.out == want, diff(r.out, want));
    r = run1(ib, m, false, &sorted);
    check("skip without crumbs: the dropped draw alone is recorded", r.plan.draws.size() == 1 && r.plan.draws[0].drop && r.out.empty() && r.plan.planned == 0);
}

void case_tables() {
    Mem m = standard_mem();
    m.put(0x20000000, {0x2d3u, 5u, 0x2d5u, kFl});                                                           // context pairs
    m.put(0x20001000, {0xc8u, kEs, 0xc9u, 0u, 0x94u, lo(kVa), 0x95u, static_cast<uint32_t>(kVa >> 32u)}); // SH pairs
    Ib ib;
    ib.load_pairs(0x9f, 0x20000000, 2).load_pairs(0x63, 0x20001000, 4);
    const uint32_t at = ib.at();
    ib.draw_auto(3);
    const std::vector<uint32_t> skip = {kEs};
    Run                         r    = run1(ib, m, true);
    check("state from LOAD_CONTEXT_REG_INDEX and LOAD_SH_REG_INDEX pair tables", r.plan.draws.size() == 1 && r.plan.draws[0].cls == 3 && r.plan.draws[0].es_lo.n == 1 &&
                                                                                     r.plan.draws[0].es_lo.v[0] == kEs && r.plan.draws[0].base[0] == kVa && r.plan.draws[0].args == 0);
    const std::vector<uint32_t> want = laid(ib, {{at, want_pre(at, 0, 0, kVa, 0, 0), want_post(at)}});
    check("... a direct draw: crumbs and the V# copy, no argument copy", r.out == want, diff(r.out, want));
    r = run1(ib, m, false, &skip);
    check("... its ES from the table is skipped", r.plan.draws.size() == 1 && r.plan.draws[0].drop);

    Ib u;
    u.fl_state(kEs).load_pairs(0x63, 0x30000000, 4).draw_auto(3);
    r = run1(u, m, true, &skip);
    check("an unreadable SH pair table: the ES unknown, not dropped, crumbs", r.plan.draws.size() == 1 && r.plan.draws[0].es_lo.n == 0 && !r.plan.draws[0].drop &&
                                                                                  r.plan.draws[0].crumbs && r.plan.draws[0].cls == 3 && r.plan.unread == 1);
    Ib v;
    v.fl_state(kEs).load_pairs(0x9f, 0x30000000, 4).draw_auto(3);
    r = run1(v, m, true, &skip);
    check("an unreadable context pair table: the stages unknown, crumbs, not dropped", r.plan.draws.size() == 1 && r.plan.draws[0].cls == 0 && r.plan.unknown == 1 &&
                                                                                          r.plan.draws[0].crumbs && !r.plan.draws[0].drop);
    m.put(0x20002000, {kEs2, 0u});                          // LOAD_SH_REG_INDEX, offset format: 2 registers from SH 0xc8
    m.put(0x20003000 + 0x90u * 4u, {0u, 0u, 0u, 0u, lo(kVb), 0u, 0u, 0u}); // LOAD_SH_REG: SH 0x90.. at its base + 0x90 * 4
    m.put(0x20004000 + 0x2d0u * 4u, {0u, 0u, 0u, 0u, 0u, kFl, 0u, 0u}); // LOAD_CONTEXT_REG: registers from 0x2d0
    Ib w;
    w.load_index_range(0x63, 0x20002000, 0xc8, 2).load_reg(0x5f, 0x20003000, 0x90, 8).load_reg(0x61, 0x20004000, 0x2d0, 8).draw_auto(3);
    r = run1(w, m, true);
    check("offset-format LOAD_SH_REG_INDEX, LOAD_SH_REG and LOAD_CONTEXT_REG ranges", r.plan.draws.size() == 1 && r.plan.draws[0].cls == 3 && r.plan.draws[0].es_lo.v[0] == kEs2 &&
                                                                                          r.plan.draws[0].base[0] == kVb);
    Ib x;
    x.fl_state(kEs).sh(0xc8, {kEs3}, 0x9b).draw_auto(3);
    r = run1(x, m, false, &skip);
    check("SET_SH_REG_INDEX sets the ES too", r.plan.draws.empty() && r.plan.fl == 1);
}

void case_carried() {
    const Mem m = standard_mem();
    FlState   st;
    Ib        a;
    a.fl_state(kEs).ud(8, kVa).base1(kBase1).draw_auto(3); // a buffer that is not a dcb: its draw is not planned
    Run ra = run(a, st, m, true, nullptr, nullptr, false);
    Ib  b;
    const uint32_t at = b.at();
    b.draw_ind(0x1620);
    const Run rb = run(b, st, m, true);
    check("state carried from the buffer before", ra.plan.draws.empty() && ra.plan.total == 0 && rb.plan.draws.size() == 1 && rb.plan.draws[0].cls == 3 &&
                                                      rb.plan.draws[0].args == kBase1 + 0x1620 && rb.plan.draws[0].base[0] == kVa);
    const std::vector<uint32_t> want = laid(b, {{at, want_pre(at, 0, kBase1 + 0x1620, kVa, 0, 0), want_post(at)}});
    check("... crumbs with the carried base and V#", rb.out == want, diff(rb.out, want));
}

void case_cond() {
    const Mem m = standard_mem();
    Ib        ib;
    ib.fl_state(kEs).base1(kBase1);
    const uint32_t c1 = ib.at();
    ib.cond(5);
    const uint32_t d1 = ib.at();
    ib.draw_ind(0x1620);
    const uint32_t d2 = ib.at();
    ib.draw_auto(3);
    Run                         r    = run1(ib, m, true);
    const std::vector<uint32_t> pre1 = want_pre(d1, 0, kBase1 + 0x1620, 0, 0, 0), post1 = want_post(d1);
    const uint32_t              grown = 5u + static_cast<uint32_t>(pre1.size() + post1.size());
    std::vector<uint32_t>       want  = laid(ib, {{d1, pre1, post1}, {d2, want_pre(d2, 1, 0, 0, 0, 0), want_post(d2)}}, {{c1, grown}});
    check("a draw inside a COND_EXEC range: the count grows by its crumbs", r.out == want, diff(r.out, want));
    check("... the range ends where the next draw's crumbs start", r.o2n[c1] + 5u + (r.out[r.o2n[c1] + 4] & 0x3fffu) == r.o2n[d2] - want_pre(d2, 1, 0, 0, 0, 0).size());
    check("... ranges open at each draw", r.plan.draws.size() == 2 && r.plan.draws[0].cond == 1 && r.plan.draws[1].cond == 0);
    std::string why;
    check("... the offsets mapped both ways", maps_ok(ib, r, why), why);

    Ib e; // a range that ends inside the draw: with it
    e.fl_state(kEs);
    const uint32_t c2 = e.at();
    e.cond(2);
    const uint32_t d3 = e.at();
    e.draw_auto(3).nop(2);
    r    = run1(e, m, true);
    want = laid(e, {{d3, want_pre(d3, 0, 0, 0, 0, 0), want_post(d3)}}, {{c2, static_cast<uint32_t>(want_pre(d3, 0, 0, 0, 0, 0).size()) + 3u + 8u}});
    check("a range ending inside its draw covers the draw and its crumbs", r.out == want, diff(r.out, want));

    Ib f; // nested ranges: both grow
    f.fl_state(kEs);
    const uint32_t c3 = f.at();
    f.cond(5 + 3 + 2);
    const uint32_t c4 = f.at();
    f.cond(3);
    const uint32_t d4 = f.at();
    f.draw_auto(3).nop(2).nop(2);
    r                     = run1(f, m, true);
    const uint32_t add    = static_cast<uint32_t>(want_pre(d4, 0, 0, 0, 0, 0).size()) + 8u;
    want                  = laid(f, {{d4, want_pre(d4, 0, 0, 0, 0, 0), want_post(d4)}}, {{c3, 10u + add}, {c4, 3u + add}});
    check("nested ranges: both counts grow", r.out == want, diff(r.out, want));

    Ib g; // a range that cannot grow: its draw keeps no crumbs, the count stays
    g.fl_state(kEs);
    const uint32_t c5 = g.at();
    g.cond(0x3ffa).nop(0x3ffa - 3);
    const uint32_t d5 = g.at();
    g.draw_auto(3);
    const uint32_t d6 = g.at();
    g.draw_auto(3);
    r    = run1(g, m, true);
    want = laid(g, {{d6, want_pre(d6, 0, 0, 0, 0, 0), want_post(d6)}});
    check("a COND_EXEC range that cannot grow: no crumbs inside, the count unchanged", r.out == want && r.plan.cond_full == 1 && r.plan.draws[0].at == d5 &&
                                                                                          !r.plan.draws[0].crumbs && r.plan.draws[0].cond_full && r.made == 1,
          diff(r.out, want));
    check("... the count", r.out[r.o2n[c5] + 4] == 0x3ffau);
    Ib h;
    h.fl_state(kEs).cond(0x3ffa).nop(0x3ffa - 3).draw_auto(3);
    r = run1(h, m, true);
    check("... its only draw: nothing laid", r.made == 0 && r.out.empty() && r.plan.draws.size() == 1 && !r.plan.draws[0].crumbs);
}

void case_cond_state() {
    const Mem                   m    = standard_mem();
    const std::vector<uint32_t> skip = {kEs};
    Ib                          ib;
    ib.fl_state(kEs).cond(3).stages(kNgg);
    const uint32_t a = ib.at();
    ib.draw_auto(3);
    Run r = run1(ib, m, true, &skip);
    check("the stages set inside a range: either after it, crumbs, no drop", r.plan.draws.size() == 1 && r.plan.draws[0].at == a && r.plan.draws[0].cls == 2 &&
                                                                                 r.plan.draws[0].stages.n == 2 && r.plan.draws[0].crumbs && !r.plan.draws[0].drop && r.plan.maybe == 1);
    Ib in;
    in.fl_state(kEs).cond(3 + 3).stages(kNgg).draw_auto(3);
    r = run1(in, m, true);
    check("... a draw inside the range after the write: not fast-launch", r.plan.draws.empty() && r.plan.not_fl == 1);
    Ib same;
    same.fl_state(kEs).cond(3).stages(kFl).draw_auto(3);
    r = run1(same, m, true, &skip);
    check("... the same value written inside: certain, dropped", r.plan.draws.size() == 1 && r.plan.draws[0].cls == 3 && r.plan.draws[0].drop);
    Ib es;
    es.fl_state(kEs).cond(3).sh(0xc8, {kEsOther}).draw_auto(3);
    r = run1(es, m, true, &skip);
    check("an ES written inside a range: one of two, not dropped", r.plan.draws.size() == 1 && r.plan.draws[0].es_lo.n == 2 && !r.plan.draws[0].drop && r.plan.draws[0].crumbs);
    const std::vector<uint32_t> both = {kEs, kEsOther};
    r = run1(es, m, true, &both);
    check("... both values listed: dropped", r.plan.draws.size() == 1 && r.plan.draws[0].drop);
    Ib b1;
    b1.fl_state(kEs).base1(kBase1).cond(4).base1(kBase1 + 0x1000).draw_ind(0x1620);
    r = run1(b1, m, true);
    check("a SET_BASE inside a range: the base uncertain, no argument copy", r.plan.draws.size() == 1 && r.plan.draws[0].args == 0 && r.plan.draws[0].crumbs);
}

void case_clear_state_ib2() {
    const Mem m = standard_mem();
    Ib        ib;
    ib.fl_state(kEs).base1(kBase1).clear(1).stages(kNgg).draw_auto(3).clear(2);
    const uint32_t a = ib.at();
    ib.draw_auto(3).clear(0);
    const uint32_t b = ib.at();
    ib.draw_auto(3);
    const std::vector<uint32_t> skip = {kEs};
    Run                         r    = run1(ib, m, true, &skip);
    check("CLEAR_STATE: push, a non-fast-launch draw, pop, a fast-launch one (dropped), cmd 0, unknown (crumbs)",
          r.plan.not_fl == 1 && r.plan.draws.size() == 2 && r.plan.draws[0].at == a && r.plan.draws[0].drop && r.plan.draws[1].at == b && r.plan.draws[1].cls == 0 &&
              r.plan.draws[1].crumbs && !r.plan.draws[1].drop);
    Ib i;
    i.fl_state(kEs).base1(kBase1).ud(8, kVa).ib2().draw_ind(0x1620);
    r = run1(i, m, true, &skip);
    check("an INDIRECT_BUFFER: everything unknown after it", r.plan.ib2 == 1 && r.plan.draws.size() == 1 && r.plan.draws[0].cls == 0 && r.plan.draws[0].es_lo.n == 0 &&
                                                                 !r.plan.draws[0].drop && r.plan.draws[0].args == 0 && r.plan.draws[0].base[0] == 0);
    Ib k; // a push inside a COND_EXEC range: after it the stack depth is not known, so a pop gives an unknown state
    k.fl_state(kEs).cond(2 + 3).clear(1).stages(kFl).clear(2).draw_auto(3);
    r = run1(k, m, true, &skip);
    check("CLEAR_STATE push inside a COND_EXEC range, pop after it: unknown, crumbs, no drop", r.plan.draws.size() == 1 && r.plan.draws[0].cls == 0 && r.plan.draws[0].crumbs &&
                                                                                                !r.plan.draws[0].drop);
}

void case_multi_and_direct() {
    const Mem m = standard_mem();
    Ib        ib;
    ib.fl_state(kEs).base1(kBase1);
    const uint32_t a = ib.at();
    ib.multi(0x2c, 0x100, 2, 16);
    const uint32_t b = ib.at();
    ib.multi(0x38, 0x200, 3, 20);
    const uint32_t c = ib.at();
    ib.draw_idx_ind(0x300);
    const uint32_t d = ib.at();
    ib.draw_idx2(6);
    const uint32_t e = ib.at();
    ib.pkt(0x35, {0u, 6u, 0u});
    const Run                   r    = run1(ib, m, true);
    const std::vector<uint32_t> want = laid(ib, {{a, want_pre(a, 0, kBase1 + 0x100, 0, 0, 0), want_post(a)},
                                                 {b, want_pre(b, 1, kBase1 + 0x200, 0, 0, 0), want_post(b)},
                                                 {c, want_pre(c, 2, kBase1 + 0x300, 0, 0, 0), want_post(c)},
                                                 {d, want_pre(d, 3, 0, 0, 0, 0), want_post(d)},
                                                 {e, want_pre(e, 4, 0, 0, 0, 0), want_post(e)}});
    check("multi-draws (first record), DRAW_INDEX_INDIRECT, DRAW_INDEX_2, DRAW_INDEX_OFFSET_2", r.made == 5 && r.out == want, diff(r.out, want));
}

void case_drops_bases_wrap_cut() {
    Mem m = standard_mem();
    Ib  ib;
    ib.fl_state(kEs);
    const uint32_t              a     = ib.at();
    const std::vector<uint32_t> drops = {a};
    ib.draw_auto(3);
    Run r = run1(ib, m, true, nullptr, &drops);
    check("the caller's drops are not planned", r.plan.host_dropped == 1 && r.plan.draws.empty() && r.made == 0);

    Ib v; // a misaligned base is copied from the dword below it (kVc's region holds kVc + 4 .. + 40)
    v.fl_state(kEs).ud(8, 0).ud(20, 0x7700000000ull).ud(24, 0x1130000006ull);
    const uint32_t at = v.at();
    v.draw_auto(3);
    r                                = run1(v, m, true);
    const std::vector<uint32_t> want = laid(v, {{at, want_pre(at, 0, 0, 0, 0, 0x1130000004ull), want_post(at)}});
    check("V# bases 0, unmapped and misaligned", r.plan.draws.size() == 1 && r.plan.draws[0].base[0] == 0 && r.plan.draws[0].base[1] == 0 &&
                                                     r.plan.draws[0].base[2] == 0x1130000004ull && r.out == want,
          diff(r.out, want));
    Ib edge;
    edge.fl_state(kEs).ud(8, kVd).draw_auto(3);
    r = run1(edge, m, true);
    check("a V# base whose 32 bytes are mapped and the 4 after them not: not copied (the filter would NOP the last copy)",
          r.plan.draws.size() == 1 && r.plan.draws[0].base[0] == 0 && r.plan.draws[0].crumbs);

    Ib w;
    w.fl_state(kEs);
    for (int k = 0; k < 70; k++) w.draw_auto(3);
    r = run1(w, m, true);
    check("ring entries wrap after 64 draws", r.made == 70 && r.plan.draws.size() == 70 && r.plan.draws[63].entry == 63 && r.plan.draws[64].entry == 0 &&
                                                  r.plan.draws[69].entry == 5 && r.plan.with_crumbs > r.plan.lay.entries);
    std::string why;
    check("... the offsets mapped both ways", maps_ok(w, r, why), why);

    Ib cut;
    cut.fl_state(kEs).draw_auto(3).pkt(0x10, {0u, 0u, 0u});
    cut.d.pop_back(); // a cut last packet
    r = run1(cut, m, true);
    check("a cut last packet is copied as it is", r.made == 1 && r.out.size() == cut.d.size() + want_pre(cut.at(), 0, 0, 0, 0, 0).size() + 8u &&
                                                      std::equal(cut.d.end() - 3, cut.d.end(), r.out.end() - 3));
}

void case_probe() {
    FlPlan p;
    p.crumbs = true;
    for (uint32_t k = 0; k < 5; k++) {
        FlDraw d;
        d.at     = 100u * (k + 1u);
        d.crumbs = k != 2; // the third has none (a COND_EXEC range that was full)
        d.id     = d.crumbs ? id_of(d.at) : 0;
        p.draws.push_back(d);
    }
    const uint64_t other = (static_cast<uint64_t>(700) << 32u) | (kSubmit - 1u); // an earlier submission's draw
    FlFind         f     = fl_find(p, id_of(400), id_of(100));
    check("probe: issued 400, done 100: 200..400 not done, from 200", f.status == 2 && f.first == 1 && f.last == 3 && f.done == 0);
    f = fl_find(p, id_of(400), id_of(200));
    check("probe: done 200: the next with crumbs is 400 (300 has none)", f.status == 2 && f.first == 3 && f.last == 3);
    f = fl_find(p, id_of(200), other);
    check("probe: done names an earlier submission: from the buffer's first", f.status == 2 && f.first == 0 && f.last == 1 && f.done == -1);
    f = fl_find(p, id_of(500), id_of(500));
    check("probe: issued is done", f.status == 1 && f.issued == 4);
    f = fl_find(p, other, other);
    check("probe: issued names no draw of the buffer", f.status == 0 && f.issued == -1);
    f = fl_find(p, id_of(200), id_of(400));
    check("probe: done after issued", f.status == 3);
    f = fl_find(p, id_of(300), id_of(100));
    check("probe: an offset without crumbs is no draw", f.status == 0);

    uint32_t       e[32] = {};
    const uint64_t id    = id_of(1234);
    check("entry: never written", fl_entry_check(e, id) == 3);
    e[0] = lo(id), e[1] = static_cast<uint32_t>(id >> 32u);
    check("entry: begun, not finished", fl_entry_check(e, id) == 1);
    e[30] = e[0], e[31] = e[1];
    check("entry: complete", fl_entry_check(e, id) == 0);
    e[1] = 99; // the head names the draw at +99 of the same submission
    check("entry: overwritten", fl_entry_check(e, id) == 2);
}

void case_parse_and_values() {
    std::vector<uint32_t> v;
    check("list: 0404's three arms", fl_parse_es_list("0x11d00f85,0x11d00f8d,0x11d00cde", v) && v == std::vector<uint32_t> {kEs3, kEs, kEs2});
    check("list: spaces, no 0x, upper case, twice", fl_parse_es_list(" 11D00F85 0x11d00f85,,11d00cde ", v) && v == std::vector<uint32_t> {kEs3, kEs});
    check("list: the probe's 16 digits", fl_parse_es_list("0000000011d00f85", v) && v == std::vector<uint32_t> {kEs});
    check("list: unset, empty, 0: off", !fl_parse_es_list(nullptr, v) && !fl_parse_es_list("", v) && !fl_parse_es_list("0", v) && v.empty());
    check("list: not hexadecimal, a 0, too large, a bare 0x: off", !fl_parse_es_list("11d00f85,zz", v) && v.empty() && !fl_parse_es_list("11d00f85,0", v) &&
                                                                     !fl_parse_es_list("0x11d00f8500", v) && !fl_parse_es_list("0x", v) && !fl_parse_es_list("-1", v));
    const FlVal a = fl_val(kFl), b = fl_val(kNgg), c = fl_val(0x1234);
    const FlVal ab = fl_merge(a, b), aa = fl_merge(a, a), abc = fl_merge(ab, c), u = fl_merge(a, FlVal {});
    check("values: merged, the same, a third, unknown", ab.n == 2 && aa.n == 1 && abc.n == 0 && u.n == 0 && fl_merge(ab, fl_merge(b, a)).n == 2);
    check("values: classes", fl_class(a) == 3 && fl_class(b) == 1 && fl_class(ab) == 2 && fl_class(FlVal {}) == 0 && fl_class(fl_merge(a, fl_val(kFl | (2u << 19u)))) == 3);
    char s1[40], s2[40], s3[40];
    fl_fmt(a, s1, sizeof(s1));
    fl_fmt(ab, s2, sizeof(s2));
    fl_fmt(FlVal {}, s3, sizeof(s3));
    check("values: printed", std::strcmp(s1, "00482030") == 0 && std::strcmp(s2, "00482030|00402030") == 0 && std::strcmp(s3, "unknown") == 0);
    const FlLayout l = fl_layout(kShadow);
    check("layout: GDS shadow +0x8000, +0x8008, +0x8100, 64 x 128 bytes to +0xa100", l.issued == kShadow + 0x8000u && l.done == kShadow + 0x8008u && l.ring == kShadow + 0x8100u &&
                                                                                       l.entries == 64 && kFlAreaOff + kFlAreaBytes == 0xa100u && kFlEntryBytes == 128u);
    check("packets: the constants", kFlWriteData2 == 0xC0043700u && kFlWriteCtl == 0x00100500u && kFlCopyData == 0xC0044000u && kFlCopyCtl == 0x00100501u &&
                                        kFlReleaseMem == 0xC0064900u && kFlEopEvent == 0x528u && kFlEopData64 == 0x40000000u && kFlStages == 0x2d5u && kFlEsLo == 0xc8u &&
                                        kFlEsHi == 0xc9u && kFlUd[0] == 0x94u && kFlUd[5] == 0xa5u && fl_is_draw(0x38) && !fl_is_draw(0x15) && fl_is_indirect(0x2c) &&
                                        !fl_is_indirect(0x2d) && fl_fast_launch(kFl) && !fl_fast_launch(kNgg));
    FlState st;
    FlVal*  p = fl_sh(st, 0xa4);
    check("state: SH registers tracked", p == &st.ud[4] && fl_sh(st, 0xc9) == &st.es_hi && fl_sh(st, 0x8c) == nullptr);
    FlState t = st;
    t.stages  = a;
    st.stages = b;
    t.stack.push_back(a);
    fl_merge_state(st, t);
    check("state: merged, stacks of different depths dropped", st.stages.n == 2 && st.stack.empty());
    FlState deeper;
    deeper.stack.push_back(a);
    fl_merge_state(deeper, FlState {});
    FlState same_depth;
    same_depth.stack.push_back(a);
    FlState other_depth;
    other_depth.stack.push_back(b);
    fl_merge_state(same_depth, other_depth);
    check("state: the taken branch's deeper stack dropped too; equal depths merged", deeper.stack.empty() && same_depth.stack.size() == 1 && same_depth.stack[0].n == 2);
    std::vector<uint32_t> o;
    FlDraw                d;
    d.id = id_of(8);
    fl_write(o, kShadow + 0x8000u, d.id);
    fl_copy(o, 0x1000u, 0x2000u);
    fl_post(d, l, o);
    check("packets: one of each", o.size() == 20u && o[0] == 0xC0043700u && o[6] == 0xC0044000u && o[12] == 0xC0064900u && o[15] == lo(kShadow + 0x8008u));
    std::vector<uint32_t> pre;
    d.entry = 3;
    fl_pre(d, l, pre);
    check("packets: crumbs without copies", pre == want_pre(8, 3, 0, 0, 0, 0), diff(pre, want_pre(8, 3, 0, 0, 0, 0)));
}

} // namespace

int main() {
    case_one_draw();
    case_not_fast_launch();
    case_skip();
    case_tables();
    case_carried();
    case_cond();
    case_cond_state();
    case_clear_state_ib2();
    case_multi_and_direct();
    case_drops_bases_wrap_cut();
    case_probe();
    case_parse_and_values();
    if (g_bad != 0) {
        std::printf("fl0401: %d of %d cases failed\n", g_bad, g_cases);
        return 1;
    }
    std::printf("fl0401: %d of %d cases; end\n", g_cases, g_cases);
    return 0;
}
