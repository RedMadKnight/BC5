// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0401 series e7, tag flx: the CPU test of mkflx0401.py's src/libs/bc5LleAgc.cpp (flx0401-notes.md): the five
// switches for the fast-launch draw-class hang, BC5_DIRECT_FL_PROBE_STATE (A1), BC5_DIRECT_FL_VGT_FLUSH (F1),
// BC5_DIRECT_FL_SERIAL (F2), BC5_DIRECT_FL_MESHLET_PROBE (A4) and BC5_DIRECT_FL_CRUMBS_MESHLET (A5). It calls the unit
// through its seams (bc5_flx0401_*): the real fl_scan and fl_build on synthetic buffers with fast-launch draws, other draws
// and dispatches (which draws get a flush in each F1 arm, the F2 waits, the COND_EXEC counts after the insertions, the
// offset maps, the crumbs as exp 0404 lays them when every new switch is off), the A1 tracking of the NGG registers and the
// user data and its lines from a synthetic tracked state, the A4 meshlet walk on synthetic object tables, records and
// headers, the A5 copies, and the unit's own reading of the switches through the real fl_plan_buffer and fl_after. The
// expected packets are spelled out here with their own constants (flx0401-notes.md section 3), not taken from the unit.
// No game, no GPU, no window, no sound device, no network: the direct path is never opened (g_dev stays empty), nothing is
// submitted anywhere.
// "on" sets all five switches (BC5_DIRECT_FL_VGT_FLUSH=transition) before the first call, "off" unsets them; both unset
// BC5_DIRECT_FL_CRUMBS and BC5_DIRECT_FL_SKIP_ES. The unit reads each switch once. The pure cases pass their options
// explicitly and run in both modes; the switch and glue cases check the mode (off: exp 0404's path, nothing laid).
// Output: one line per case, then "flx0401: on N of N; end" or "flx0401: off N of N; end"; without "; end" something
// failed. Exit 0 only after the end line. A watchdog ends a hang after 60 s with a FAIL line.
// Build: build0401.py ... --gate flx0401.cpp <out> --like src/libs/bc5LleAgc.cpp (the unit's compile command; linked with
// every emulator object but main.cpp.o, the private bc5LleAgc.cpp.o among them), -std=c++20 -Wall -Wextra -Werror.
// usage: flx0401 on | flx0401 off

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cinttypes>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <initializer_list>
#include <map>
#include <string>
#include <thread>
#include <utility>
#include <vector>

// The seams of mkflx0401.py's unit (always compiled in, never called by the emulator).
typedef const uint32_t* (*FlxReadFn)(uint64_t a, uint64_t bytes, void* ctx);
extern "C" void        bc5_flx0401_switches(int* out);
extern "C" void        bc5_flx0401_consts(uint32_t* out);
extern "C" int         bc5_flx0401_index(int space, uint32_t r);
extern "C" const char* bc5_flx0401_name(uint32_t i);
extern "C" int         bc5_flx0401_parse_flush(const char* e, int* bad);
extern "C" uint32_t    bc5_flx0401_heads(const uint32_t* segs, uint32_t nseg, int chain, int dcb, uint32_t n, uint32_t* out, uint32_t cap);
extern "C" uint32_t    bc5_flx0401_build(const uint32_t* ib, uint32_t n, const uint32_t* opt, const uint32_t* heads, uint32_t nheads, const uint32_t* drops, uint32_t ndrops,
                                         const uint32_t* skip, uint32_t nskip, FlxReadFn read, void* ctx, uint64_t shadow, uint64_t submit, uint32_t* out, uint32_t out_cap,
                                         uint32_t* info, uint32_t* rec, uint32_t rec_cap);
extern "C" uint32_t    bc5_flx0401_maps(uint32_t* o2n, uint32_t* n2o, uint32_t cap);
extern "C" uint32_t    bc5_flx0401_draw_x(uint32_t k, uint32_t* ns, uint32_t* v0, uint32_t* v1);
extern "C" uint32_t    bc5_flx0401_state_x(uint32_t* ns, uint32_t* v0, uint32_t* v1);
extern "C" int         bc5_flx0401_draw_mp0(uint32_t k, uint64_t* out);
extern "C" uint32_t    bc5_flx0401_state_text(const uint32_t* ns, const uint32_t* v0, const uint32_t* v1, uint32_t count, char* out, uint32_t cap);
extern "C" int         bc5_flx0401_mesh(uint32_t es, const uint32_t* ud, uint32_t v6, uint32_t points, uint32_t cap, FlxReadFn read, void* ctx, int32_t* out);
extern "C" int         bc5_flx0401_mesh_point(uint32_t es, const uint32_t* ud, uint32_t v6, uint32_t point, FlxReadFn read, void* ctx, uint64_t* out);
extern "C" uint32_t    bc5_flx0401_mesh_text(uint32_t es, const uint32_t* ud, uint32_t v6, int v6_from, uint32_t points, uint32_t instances, const char* from, FlxReadFn read, void* ctx,
                                             char* out, uint32_t cap);
extern "C" int         bc5_flx0401_v6(const uint32_t* ns, const uint32_t* v0, const uint32_t* v1, uint32_t count, uint32_t* v6);
extern "C" int         bc5_flx0401_user_data(const uint32_t* ns, const uint32_t* v0, const uint32_t* v1, uint32_t count, int pat, uint32_t* ud);
extern "C" int         bc5_flx0401_next(const uint32_t* crumbs, uint32_t nd, int status, int issued, int last);
extern "C" int         bc5_flx0401_entry_reading(const uint32_t* e, uint64_t id);
extern "C" uint32_t    bc5_flx0401_plan_buffer(const uint32_t* ib, uint32_t n, const char* kind, uint32_t* info);
extern "C" uint32_t    bc5_flx0401_after(const uint32_t* ib, uint32_t n, const char* kind, uint32_t* drops, uint32_t nd, uint32_t* out, uint32_t cap, uint32_t* info);

namespace flx0401 {

static int                      g_pass = 0, g_total = 0, g_case_pass = 0, g_case_total = 0;
static std::atomic<const char*> g_case {"init"};

static void Check(bool ok, const char* what, int line, const std::string& why = "") {
    g_total++;
    g_case_total++;
    if (ok) {
        g_pass++;
        g_case_pass++;
    } else {
        std::printf("flx0401: FAIL %s (line %d): %s%s%s\n", g_case.load(), line, what, why.empty() ? "" : ": ", why.c_str());
        std::fflush(stdout);
    }
}
#define CHECK(cond) Check((cond), #cond, __LINE__)
#define CHECKW(cond, why) Check((cond), #cond, __LINE__, (why))
static void Begin(const char* name) {
    g_case       = name;
    g_case_pass  = 0;
    g_case_total = 0;
}
static void End(const char* how) {
    std::printf("flx0401: case %s (%s): %d of %d\n", g_case.load(), how, g_case_pass, g_case_total);
    std::fflush(stdout);
}

// ---- the test's own constants (flx0401-notes.md section 3; fl0401-notes.md section 3 for the crumbs) ----------------
constexpr uint64_t kShadow = 0x100004000000ull; // the backend's GDS shadow VA (direct.cpp kShadowVa)
constexpr uint64_t kSubmit = 412352;            // the 19:54 dcb
constexpr uint32_t kFl = 0x00482030u, kNgg = 0x00402030u, kNgg2 = 0x02002000u; // VGT_SHADER_STAGES_EN: fast-launch, NGG, 22:54's other NGG
constexpr uint32_t kEsA = 0x11d01345u, kEsB = 0x11d00f85u, kEsB2 = 0x11d00f8du, kEsOther = 0x11d01000u;
constexpr uint64_t kBase1 = 0x1193ad3900ull;    // the SET_BASE of 19:54 and 22:54
constexpr uint64_t kVa = 0x1123502050ull, kVb = 0x2240fda0ull, kVc = 0x1130000000ull;
// EVENT_WRITE PKT3(0x46, 0); VS_PARTIAL_FLUSH 15 | EVENT_INDEX 4 << 8; VGT_FLUSH 36 (gfx10.json VGT_EVENT_TYPE)
constexpr uint32_t kEw = 0xC0004600u, kVsPf = 0x0000040fu, kVgtF = 0x00000024u;
const std::vector<uint32_t> kF1 = {kEw, kVsPf, kEw, kVgtF}, kF2 = {kEw, kVsPf};

uint32_t lo(uint64_t a) { return static_cast<uint32_t>(a); }
uint32_t hi16(uint64_t a) { return static_cast<uint32_t>(a >> 32u) & 0xffffu; }
uint32_t hdr(uint32_t op, uint32_t len) { return 0xC0000000u | ((len - 2u) << 16u) | (op << 8u); }
std::vector<uint32_t> cat(std::initializer_list<std::vector<uint32_t>> parts) {
    std::vector<uint32_t> r;
    for (const auto& p: parts) r.insert(r.end(), p.begin(), p.end());
    return r;
}

struct Ib {
    std::vector<uint32_t> d;
    uint32_t              at() const { return static_cast<uint32_t>(d.size()); }
    Ib&                   pkt(uint32_t op, std::initializer_list<uint32_t> body) {
        d.push_back(hdr(op, 1u + static_cast<uint32_t>(body.size())));
        d.insert(d.end(), body);
        return *this;
    }
    Ib& set(uint32_t op, uint32_t reg, std::initializer_list<uint32_t> v) {
        d.push_back(hdr(op, 2u + static_cast<uint32_t>(v.size())));
        d.push_back(reg);
        d.insert(d.end(), v);
        return *this;
    }
    Ib& ctx(uint32_t reg, std::initializer_list<uint32_t> v) { return set(0x69, reg, v); }
    Ib& sh(uint32_t reg, std::initializer_list<uint32_t> v) { return set(0x76, reg, v); }
    Ib& uc(uint32_t reg, std::initializer_list<uint32_t> v) { return set(0x79, reg, v); }
    Ib& stages(uint32_t v) { return ctx(0x2d5, {v}); }
    Ib& es(uint32_t lo_value) { return sh(0xc8, {lo_value, 0u}); } // SPI_SHADER_PGM_LO_ES, HI_ES
    Ib& ud(uint32_t k, uint64_t base) { return sh(0x8cu + k, {lo(base), static_cast<uint32_t>(base >> 32u)}); }
    Ib& vsharp(uint32_t k, uint64_t base, uint32_t stride, uint32_t records) { return sh(0x8cu + k, {lo(base), hi16(base) | (stride << 16u), records, 0x0002'0000u}); }
    Ib& base1(uint64_t a) { return pkt(0x11, {1u, lo(a), static_cast<uint32_t>(a >> 32u)}); }
    Ib& draw_ind(uint32_t off) { return pkt(0x24, {off, 0u, 0u, 2u}); }
    Ib& draw_auto(uint32_t count) { return pkt(0x2d, {count, 2u}); }
    Ib& dispatch() { return pkt(0x15, {8u, 1u, 1u, 0x41u}); }
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
    uint32_t& at(uint64_t base, uint64_t byte) { return r[base][byte / 4u]; }
    const uint32_t* get(uint64_t a, uint64_t bytes) const {
        for (const auto& [base, v]: r) {
            if (a >= base && a + bytes <= base + v.size() * 4u && (a - base) % 4u == 0) return v.data() + (a - base) / 4u;
        }
        return nullptr;
    }
};
const uint32_t* MemRead(uint64_t a, uint64_t bytes, void* ctx) { return static_cast<const Mem*>(ctx)->get(a, bytes); }
Mem standard_mem() {
    Mem m;
    m.put(kBase1, std::vector<uint32_t>(0x1000, 0u));
    m.r[kBase1][0x1620 / 4]     = 366; // 19:54's arguments: 366 x 1
    m.r[kBase1][0x1620 / 4 + 1] = 1;
    m.put(kVa, {0xa0, 0xa1, 0xa2, 0xa3, 0xa4, 0xa5, 0xa6, 0xa7, 0xa8});
    m.put(kVb, {0xb0, 0xb1, 0xb2, 0xb3, 0xb4, 0xb5, 0xb6, 0xb7, 0xb8});
    m.put(kVc, {0xc0, 0xc1, 0xc2, 0xc3, 0xc4, 0xc5, 0xc6, 0xc7, 0xc8});
    return m;
}

struct Opt {
    uint32_t crumbs = 0, flush = 0, serial = 0, state = 0, ml = 0, carry = 0, draws = 1, build = 1;
};
constexpr uint32_t kRec = 20;
struct Run {
    std::vector<uint32_t> out, rec;
    uint32_t              info[28] = {};
    uint32_t              draws    = 0;
    uint32_t made() const { return info[0]; }
    uint32_t flushes() const { return info[2]; }
    uint32_t serials() const { return info[3]; }
    uint32_t heads() const { return info[4]; }
    uint32_t cond_full() const { return info[5]; }
    uint32_t d(uint32_t k, uint32_t f) const { return k < draws ? rec[k * kRec + f] : 0xdeadbeefu; } // 0 at, 1 op, 2 cls, 3 crumbs, 4 flush, 5 serial, 6 drop, 7 cond_full, 8 new_at, 9 entry, 10 ml, 11 vcount
    uint64_t d64(uint32_t k, uint32_t f) const { return k < draws ? rec[k * kRec + f] | (static_cast<uint64_t>(rec[k * kRec + f + 1]) << 32u) : 0; } // 12 args, 14/16/18 base[0..2]
};
Run run(const Ib& ib, const Mem& mem, const Opt& o, std::vector<uint32_t> heads = {}, std::vector<uint32_t> drops = {}, std::vector<uint32_t> skip = {}) {
    Run            r;
    const uint32_t opt[8] = {o.crumbs, o.flush, o.serial, o.state, o.ml, o.carry, o.draws, o.build};
    r.out.assign(ib.d.size() * 4 + 4096, 0u);
    r.rec.assign(256 * kRec, 0u);
    std::sort(drops.begin(), drops.end());
    std::sort(skip.begin(), skip.end());
    r.draws = bc5_flx0401_build(ib.d.data(), ib.at(), opt, heads.data(), static_cast<uint32_t>(heads.size()), drops.data(), static_cast<uint32_t>(drops.size()), skip.data(),
                                static_cast<uint32_t>(skip.size()), MemRead, const_cast<Mem*>(&mem), kShadow, kSubmit, r.out.data(), static_cast<uint32_t>(r.out.size()), r.info,
                                r.rec.data(), 256);
    r.out.resize(r.info[20]);
    return r;
}

uint64_t id_of(uint32_t at) { return (static_cast<uint64_t>(at) << 32u) | static_cast<uint32_t>(kSubmit); }
// The crumbs as fl0401-notes.md spells them: WRITE_DATA 0xC0043700 / 0x00100500, COPY_DATA 0xC0044000 / 0x00100501,
// RELEASE_MEM 0xC0064900 / 0x00000528 / 0x40000000; slots at the shadow + 0x8000 / 0x8008, entry k at + 0x8100 + 128 k.
std::vector<uint32_t> want_pre(uint32_t at, uint32_t entry, uint64_t args, uint64_t ba, uint64_t bb, uint64_t bc) {
    const uint64_t        e = kShadow + 0x8100u + 128ull * entry, id = id_of(at);
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
// ib with the insertions, and the COND_EXEC at old offset c given the count v (computed by the case)
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
// The last build's maps both ways: every title packet at its new place, unchanged but for a COND_EXEC count, and back; every
// other packet of the copy a crumb or an EVENT_WRITE.
bool maps_ok(const Ib& ib, const Run& r, std::string& why) {
    std::vector<uint32_t> o2n(r.out.size() + ib.d.size() + 2, ~0u), n2o(r.out.size() + ib.d.size() + 2, ~0u);
    const uint32_t        nn = bc5_flx0401_maps(o2n.data(), n2o.data(), static_cast<uint32_t>(o2n.size()));
    if (nn != r.out.size()) return why = "the new-to-old map has " + std::to_string(nn) + " entries", false;
    uint32_t packets = 0;
    for (uint32_t q = 0; q < ib.at();) {
        const uint32_t h = ib.d[q], c = (h >> 16u) & 0x3fffu, len = std::min((h >> 30u) == 3 && c != 0x3fffu ? c + 2u : 1u, ib.at() - q);
        const uint32_t p = o2n[q];
        if (p == ~0u || p + len > r.out.size() || n2o[p] != q) return why = "packet " + std::to_string(q) + " not mapped both ways", false;
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
        if (n2o[p] != ~0u) back++;
        else if (h != 0xC0043700u && h != 0xC0044000u && h != 0xC0064900u && h != kEw) return why = "a packet at " + std::to_string(p) + " that is neither the title's nor inserted", false;
        p += len;
    }
    return back == packets || (why = "the copy has " + std::to_string(back) + " title packets, the buffer " + std::to_string(packets), false);
}

// ---- 1. the unit's reading of the switches (mode) -------------------------------------------------------------------
static void Switches(bool on) {
    Begin("switches");
    int s[6] = {-1, -1, -1, -1, -1, -1};
    bc5_flx0401_switches(s);
    if (on) {
        CHECK(s[0] == 1 && s[1] == 2 && s[2] == 1 && s[3] == 1 && s[4] == 1); // probe state, transition, serial, meshlet probe, crumbs meshlet
    } else {
        CHECK(s[0] == 0 && s[1] == 0 && s[2] == 0 && s[3] == 0 && s[4] == 0);
    }
    CHECK(s[5] == 0); // BC5_DIRECT_FL_CRUMBS unset in both modes
    End(on ? "on" : "off");
}

// ---- 2. the constants, and the register table against gfx10.json's addresses ----------------------------------------
static void Consts() {
    Begin("constants");
    uint32_t c[16] = {};
    bc5_flx0401_consts(c);
    CHECK(c[0] == 0xC0004600u && c[1] == 0x40fu && c[2] == 0x24u);                              // EVENT_WRITE, VS_PARTIAL_FLUSH|4<<8, VGT_FLUSH
    CHECK(c[3] == 71 && c[4] == 12 && c[5] == 12 && c[6] == 17 && c[7] == 53 && c[8] == 21 && c[9] == 55); // x's layout
    CHECK(c[10] == 14 && c[11] == 15 && c[12] == 4096 && c[13] == 128 && c[14] == 0x8000 && c[15] == 64);
    struct R {
        uint32_t    addr;
        const char* name;
    };
    // tools/bc5-agc/regdb/gfx10.json (Mesa fe554882) byte addresses
    static const R ctx[12] = {{0x287fc, "GE_MAX_OUTPUT_PER_SUBGROUP"}, {0x28b38, "VGT_GS_MAX_VERT_OUT"}, {0x28a6c, "VGT_GS_OUT_PRIM_TYPE"}, {0x28a44, "VGT_GS_ONCHIP_CNTL"},
                              {0x28b4c, "GE_NGG_SUBGRP_CNTL"}, {0x28aac, "VGT_ESGS_RING_ITEMSIZE"}, {0x28a40, "VGT_GS_MODE"}, {0x28b90, "VGT_GS_INSTANCE_CNT"},
                              {0x28838, "PA_CL_NGG_CNTL"}, {0x28708, "SPI_SHADER_IDX_FORMAT"}, {0x2870c, "SPI_SHADER_POS_FORMAT"}, {0x28a98, "VGT_DRAW_PAYLOAD_CNTL"}};
    static const R uc[5]   = {{0x30908, "VGT_PRIMITIVE_TYPE"}, {0x3096c, "GE_CNTL"}, {0x30988, "GE_USER_VGPR_EN"}, {0x30970, "GE_USER_VGPR1"}, {0x30980, "GE_PC_ALLOC"}};
    for (uint32_t k = 0; k < 12; k++) {
        CHECK(bc5_flx0401_index(0, (ctx[k].addr - 0x28000u) / 4u) == static_cast<int>(k));
        CHECK(bc5_flx0401_name(k) != nullptr && std::strcmp(bc5_flx0401_name(k), ctx[k].name) == 0);
    }
    for (uint32_t k = 0; k < 5; k++) {
        CHECK(bc5_flx0401_index(2, (uc[k].addr - 0x30000u) / 4u) == static_cast<int>(12 + k));
        CHECK(bc5_flx0401_name(12 + k) != nullptr && std::strcmp(bc5_flx0401_name(12 + k), uc[k].name) == 0);
    }
    const auto sh = [](uint32_t addr) { return bc5_flx0401_index(1, (addr - 0xb000u) / 4u); };
    CHECK(sh(0xb220) == 17 && sh(0xb22c) == 20 && sh(0xb230) == 21 && sh(0xb2ac) == 52); // LO_GS, RSRC2_GS, USER_DATA_GS_0, _31
    CHECK(sh(0xb328) == 53 && sh(0xb32c) == 54 && sh(0xb330) == 55 && sh(0xb36c) == 70); // RSRC1_ES, RSRC2_ES, USER_DATA_ES_0, _15
    CHECK(sh(0xb320) == -1 && sh(0xb324) == -1 && sh(0xb370) == -1 && sh(0xb21c) == -1); // LO_ES/HI_ES (exp 0404's own), past ES_15, RSRC3_GS
    CHECK(bc5_flx0401_index(0, 0x2d5) == -1 && bc5_flx0401_index(2, 0x243) == -1 && bc5_flx0401_index(2, 0x1ff) == -1 && bc5_flx0401_index(0, 0x242) == -1);
    CHECK(bc5_flx0401_name(17) == nullptr);
    End("pure");
}

// ---- 3. BC5_DIRECT_FL_VGT_FLUSH's values, and the prefix heads ------------------------------------------------------
static void ParseHeads() {
    Begin("parse and heads");
    struct Row {
        const char* e;
        int         v, bad;
    };
    static const Row rows[] = {{nullptr, 0, 0}, {"", 0, 0},          {"0", 0, 0},   {"prefix", 1, 0},      {"transition", 2, 0}, {"all", 3, 0},
                               {"1", 0, 1},     {"Prefix", 0, 1},    {"all ", 0, 1}, {"transitions", 0, 1}, {"on", 0, 1},         {"00", 0, 1}};
    for (const Row& r: rows) {
        int       bad = -1;
        const int v   = bc5_flx0401_parse_flush(r.e, &bad);
        CHECK(v == r.v && bad == r.bad);
    }
    uint32_t       out[8] = {};
    const uint32_t segs[] = {0, 1273, 2940, 0, 3000, 50, 9000, 12}; // (off, prefix): 19:54's prefix of 1273 dwords at 0; 9000 past the end
    CHECK(bc5_flx0401_heads(segs, 4, 1, 1, 4000, out, 8) == 2 && out[0] == 0 && out[1] == 3000);
    CHECK(bc5_flx0401_heads(segs, 4, 0, 1, 4000, out, 8) == 1 && out[0] == 0); // no chain, a dcb: its head
    CHECK(bc5_flx0401_heads(segs, 4, 0, 0, 4000, out, 8) == 0);               // no chain, not a dcb
    CHECK(bc5_flx0401_heads(segs, 0, 1, 1, 4000, out, 8) == 0);               // a chain without segments
    End("pure");
}

// ---- 4. every new switch off: exp 0404's crumbs exactly, or nothing ----------------------------------------------
static void OffToday() {
    Begin("off is exp 0404's path");
    const Mem m = standard_mem();
    Ib        ib;
    ib.fl_state(kEsA).ud(8, kVa).ud(20, kVb).ud(24, kVc).base1(kBase1);
    const uint32_t at = ib.at();
    ib.draw_ind(0x1620).nop(2);
    Opt o;
    o.crumbs                         = 1;
    Run                         r    = run(ib, m, o);
    const std::vector<uint32_t> pre  = want_pre(at, 0, kBase1 + 0x1620, kVa, kVb, kVc);
    const std::vector<uint32_t> want = laid(ib, {{at, pre, want_post(at)}});
    CHECKW(r.out == want, diff(r.out, want)); // fl0401's case_one_draw: 186 + 8 crumb dwords
    CHECK(r.made() == 1 && r.flushes() == 0 && r.serials() == 0 && r.heads() == 0 && pre.size() == 186u && r.out.size() == ib.d.size() + 194u);
    CHECK(r.draws == 1 && r.d(0, 4) == 0 && r.d(0, 5) == 0 && r.d(0, 10) == 0 && r.info[19] == 0); // no flush, no wait, no A5, x not tracked
    std::string why;
    CHECKW(maps_ok(ib, r, why), why);
    o.state = 1; // A1's tracking alone: the same packets
    r       = run(ib, m, o);
    CHECKW(r.out == want, diff(r.out, want));
    CHECK(r.info[19] == 71);
    Opt none; // nothing on: nothing planned, nothing laid
    r = run(ib, m, none);
    CHECK(r.draws == 0 && r.made() == 0 && r.out.empty() && r.info[8] == 1);
    std::vector<uint32_t> skip = {kEsA}; // the ES skip, F1 all and F2 on: the dropped draw gets neither
    o                          = Opt {};
    o.flush                    = 3;
    o.serial                   = 1;
    r                          = run(ib, m, o, {}, {}, skip);
    CHECK(r.draws == 1 && r.d(0, 6) == 1 && r.d(0, 4) == 0 && r.d(0, 5) == 0 && r.made() == 0 && r.out.empty());
    End("pure");
}

// The F1/F2 stream: X not fast-launch, A B fast-launch, a dispatch, C, Y not fast-launch, E.
struct Stream {
    Ib       ib;
    uint32_t x = 0, a = 0, b = 0, disp = 0, c = 0, y = 0, e = 0;
};
static Stream stream() {
    Stream s;
    s.ib.stages(kNgg2);
    s.x = s.ib.at();
    s.ib.draw_auto(3).fl_state(kEsA);
    s.a = s.ib.at();
    s.ib.draw_auto(3);
    s.b = s.ib.at();
    s.ib.draw_auto(3);
    s.disp = s.ib.at();
    s.ib.dispatch();
    s.c = s.ib.at();
    s.ib.draw_auto(3).stages(kNgg);
    s.y = s.ib.at();
    s.ib.draw_auto(3).stages(kFl);
    s.e = s.ib.at();
    s.ib.draw_auto(3);
    return s;
}

// ---- 5. F1 all / transition / prefix and F2 on the stream -------------------------------------------------------------
static void Flushes() {
    Begin("F1 and F2");
    const Mem    m = standard_mem();
    const Stream s = stream();
    std::string  why;
    Opt          o;
    o.flush                     = 3; // all
    Run                   r     = run(s.ib, m, o);
    std::vector<uint32_t> want = laid(s.ib, {{s.a, kF1, {}}, {s.b, kF1, {}}, {s.c, kF1, {}}, {s.e, kF1, {}}});
    CHECKW(r.out == want, diff(r.out, want));
    CHECK(r.flushes() == 4 && r.made() == 4 && r.draws == 4 && r.info[1] == 0); // no crumbs
    CHECKW(maps_ok(s.ib, r, why), why);
    o.flush = 2; // transition, a fresh state: A after X, C after the dispatch, E after Y; not B
    r       = run(s.ib, m, o);
    want    = laid(s.ib, {{s.a, kF1, {}}, {s.c, kF1, {}}, {s.e, kF1, {}}});
    CHECKW(r.out == want, diff(r.out, want));
    CHECK(r.flushes() == 3 && r.draws == 3 && r.d(0, 0) == s.a && r.d(1, 0) == s.c && r.d(2, 0) == s.e); // B, with nothing to lay, is not kept
    CHECK(r.info[16] == 1 && r.info[17] == 1); // the last work: E, fast-launch
    o.flush = 0;
    o.serial = 1; // F2: after A, B, C, E
    r        = run(s.ib, m, o);
    want     = laid(s.ib, {{s.a, {}, kF2}, {s.b, {}, kF2}, {s.c, {}, kF2}, {s.e, {}, kF2}});
    CHECKW(r.out == want, diff(r.out, want));
    CHECK(r.serials() == 4 && r.flushes() == 0);
    CHECKW(maps_ok(s.ib, r, why), why);
    o.serial = 0;
    o.flush  = 1; // prefix: at the heads only (the buffer's head and the dispatch, as the caller would name them)
    r        = run(s.ib, m, o, {0, s.disp});
    want     = laid(s.ib, {{0, kF1, {}}, {s.disp, kF1, {}}});
    CHECKW(r.out == want, diff(r.out, want));
    CHECK(r.heads() == 2 && r.flushes() == 0 && r.draws == 0);
    r = run(s.ib, m, o); // prefix without heads: nothing
    CHECK(r.out.empty() && r.made() == 0);
    // all three with the crumbs: [F1] [crumbs] <draw> [done] [F2], entries counted over the crumbed draws only
    o        = Opt {};
    o.crumbs = 1;
    o.flush  = 2;
    o.serial = 1;
    r        = run(s.ib, m, o, {0});
    want     = laid(s.ib, {{0, kF1, {}},
                           {s.a, cat({kF1, want_pre(s.a, 0, 0, 0, 0, 0)}), cat({want_post(s.a), kF2})},
                           {s.b, want_pre(s.b, 1, 0, 0, 0, 0), cat({want_post(s.b), kF2})},
                           {s.c, cat({kF1, want_pre(s.c, 2, 0, 0, 0, 0)}), cat({want_post(s.c), kF2})},
                           {s.e, cat({kF1, want_pre(s.e, 3, 0, 0, 0, 0)}), cat({want_post(s.e), kF2})}});
    CHECKW(r.out == want, diff(r.out, want)); // the head at 0 precedes the stages write; X has no draw packet at 0
    CHECK(r.made() == 4 + 3 + 4 + 1 && r.info[1] == 4 && r.heads() == 1);
    CHECKW(maps_ok(s.ib, r, why), why);
    End("pure");
}

// ---- 6. F1 transition across buffers, drops, the ES skip, COND_EXEC, an INDIRECT_BUFFER -----------------------------
static void Transition() {
    Begin("F1 transition");
    const Mem m = standard_mem();
    Opt       o;
    o.flush  = 2;
    o.serial = 1; // so that every fast-launch draw is kept in the plan and its flush can be read
    Ib b1;
    b1.fl_state(kEsA).draw_auto(3);
    Run r = run(b1, m, o); // a fresh state: the last work is not known: flush
    CHECK(r.flushes() == 1 && r.serials() == 1);
    o.carry = 1;
    Ib b2;
    b2.draw_auto(3); // carried: the last work was fast-launch: none
    r = run(b2, m, o);
    CHECK(r.flushes() == 0 && r.draws == 1 && r.d(0, 4) == 0 && r.info[8] == 1);
    Ib b3; // a buffer that is not a dcb (an acb on the GFX ring) with a dispatch
    b3.dispatch();
    Opt o3  = o;
    o3.draws = 0;
    r        = run(b3, m, o3);
    CHECK(r.info[16] == 1 && r.info[17] == 0); // the last work: other
    r = run(b2, m, o);                         // then the dcb's first fast-launch draw: flush
    CHECK(r.flushes() == 1);
    o.carry = 0;
    Ib d; // A, then X dropped by the caller, then B: X never ran, so B follows A: none
    d.fl_state(kEsA).draw_auto(3).stages(kNgg);
    const uint32_t xd = d.at();
    d.draw_auto(3).stages(kFl);
    const uint32_t bd = d.at();
    d.draw_auto(3);
    r = run(d, m, o, {}, {xd});
    CHECK(r.info[23] == 1 && r.draws == 2 && r.d(0, 4) == 1 && r.d(1, 0) == bd && r.d(1, 4) == 0);
    r = run(d, m, o); // not dropped: B follows X: flush
    CHECK(r.d(1, 0) == bd && r.d(1, 4) == 1 && r.flushes() == 2);
    Ib k; // X, then S (fast-launch, ES listed: skipped), then B: S did not run, B follows X: flush
    k.stages(kNgg).draw_auto(3).fl_state(kEsB);
    const uint32_t sk = k.at();
    k.draw_auto(3).es(kEsA);
    const uint32_t bk = k.at();
    k.draw_auto(3);
    r = run(k, m, o, {}, {}, {kEsB});
    CHECK(r.draws == 2 && r.d(0, 0) == sk && r.d(0, 6) == 1 && r.d(0, 4) == 0 && r.d(1, 0) == bk && r.d(1, 4) == 1);
    Ib c; // A, then a COND_EXEC range over X, then B: either branch: flush
    c.fl_state(kEsA).draw_auto(3).cond(3 + 3).stages(kNgg).draw_auto(3).stages(kFl);
    const uint32_t bc = c.at();
    c.draw_auto(3);
    r = run(c, m, o);
    CHECK(r.draws == 2 && r.d(1, 0) == bc && r.d(1, 4) == 1);
    Ib c2; // A, then a COND_EXEC range over a fast-launch draw, then B: the last work is fast-launch either way: none
    c2.fl_state(kEsA).draw_auto(3).cond(3).draw_auto(3).draw_auto(3);
    r = run(c2, m, o);
    CHECK(r.draws == 3 && r.d(0, 4) == 1 && r.d(1, 4) == 0 && r.d(2, 4) == 0);
    Ib i; // after an INDIRECT_BUFFER nothing is known: flush
    i.fl_state(kEsA).draw_auto(3).ib2().stages(kFl).draw_auto(3);
    r = run(i, m, o);
    CHECK(r.draws == 2 && r.d(1, 4) == 1 && r.info[22] == 1);
    Ib u; // a draw of unknown state (CLEAR_STATE cmd 0) after a fast-launch one: planned, no flush; after it the last work is unknown
    u.fl_state(kEsA).draw_auto(3).clear(0).draw_auto(3).stages(kFl).draw_auto(3);
    r = run(u, m, o);
    CHECK(r.draws == 3 && r.d(1, 2) == 0 && r.d(1, 4) == 0 && r.d(2, 4) == 1);
    o.serial = 0; // without F2 a fast-launch draw with no flush is not kept: only A and the draw after the INDIRECT_BUFFER
    r        = run(i, m, o);
    CHECK(r.draws == 2 && r.flushes() == 2);
    r = run(c2, m, o);
    CHECK(r.draws == 1 && r.flushes() == 1);
    End("pure");
}

// ---- 7. COND_EXEC counts grown by the insertions, and a range that cannot grow ------------------------------------------
static void Cond() {
    Begin("COND_EXEC");
    const Mem m = standard_mem();
    Ib        ib;
    ib.fl_state(kEsA).base1(kBase1);
    const uint32_t c1 = ib.at();
    ib.cond(5);
    const uint32_t d1 = ib.at();
    ib.draw_ind(0x1620);
    const uint32_t d2 = ib.at();
    ib.draw_auto(3);
    Opt o;
    o.crumbs                          = 1;
    o.flush                           = 3;
    o.serial                          = 1;
    const Run                   r     = run(ib, m, o);
    const std::vector<uint32_t> pre1  = cat({kF1, want_pre(d1, 0, kBase1 + 0x1620, 0, 0, 0)}), post1 = cat({want_post(d1), kF2});
    const uint32_t              grown = 5u + static_cast<uint32_t>(pre1.size() + post1.size());
    const std::vector<uint32_t> want  = laid(ib, {{d1, pre1, post1}, {d2, cat({kF1, want_pre(d2, 1, 0, 0, 0, 0)}), cat({want_post(d2), kF2})}}, {{c1, grown}});
    CHECKW(r.out == want, diff(r.out, want)); // the range covers the draw's F1, crumbs and F2
    std::string why;
    CHECKW(maps_ok(ib, r, why), why);
    Ib g; // a range that cannot grow by F1 + F2 (6 dwords): its draw keeps neither, the count stays, the next draw has both
    g.fl_state(kEsA);
    const uint32_t c5 = g.at();
    g.cond(0x3ffa).nop(0x3ffa - 3);
    const uint32_t d5 = g.at();
    g.draw_auto(3);
    const uint32_t d6 = g.at();
    g.draw_auto(3);
    o.crumbs = 0;
    Run rg   = run(g, m, o);
    CHECKW(rg.out == laid(g, {{d6, kF1, kF2}}), diff(rg.out, laid(g, {{d6, kF1, kF2}})));
    CHECK(rg.cond_full() == 1 && rg.d(0, 0) == d5 && rg.d(0, 7) == 1 && rg.d(0, 4) == 0 && rg.d(0, 5) == 0 && rg.out[c5 + 4] == 0x3ffau);
    Ib h; // a prefix head inside a range that cannot grow by 4: no flush there, nothing laid
    h.fl_state(kEsA).cond(0x3ffc);
    const uint32_t nh = h.at();
    h.nop(0x3ffc);
    Opt oh;
    oh.flush = 1;
    rg       = run(h, m, oh, {nh});
    CHECK(rg.cond_full() == 1 && rg.made() == 0 && rg.out.empty() && rg.info[27] == 0);
    End("pure");
}

// ---- 8. A1: the registers fl_scan tracks ------------------------------------------------------------------------------
struct X {
    std::vector<uint32_t> n, v0, v1;
    uint32_t              size = 0;
    bool                  is(uint32_t i, uint32_t v) const { return i < size && n[i] == 1 && v0[i] == v; }
    bool                  unknown(uint32_t i) const { return i < size && n[i] == 0; }
};
static X draw_x(uint32_t k) {
    X x;
    x.n.assign(80, 0);
    x.v0.assign(80, 0);
    x.v1.assign(80, 0);
    x.size = bc5_flx0401_draw_x(k, x.n.data(), x.v0.data(), x.v1.data());
    return x;
}
static void Tracking() {
    Begin("A1 tracking");
    Mem m = standard_mem();
    m.put(0x20000000, {0x262u, 1u, 0x25cu, 7u});              // LOAD_UCONFIG_REG_INDEX pairs: GE_USER_VGPR_EN 1, GE_USER_VGPR1 7
    m.put(0x20001000, {0x160u, 0x161u, 0x162u, 0x163u, 0x164u}); // LOAD_SH_REG_INDEX, offset form: user data 16..20
    m.put(0x20002000 + 0x25bu * 4u, {0x0301u});                // LOAD_UCONFIG_REG: GE_CNTL at its base + 0x25b * 4
    m.put(0x20003000 + 0x2a6u * 4u, {0x11u, 0u, 0u, 0u, 0u, 0x22u}); // LOAD_CONTEXT_REG: 0x2a6..0x2ab
    Ib ib;
    ib.ctx(0x1ff, {0x20}).ctx(0x2ce, {0x20}).ctx(0x29b, {2}).ctx(0x290, {0x40, 0x00400801}).ctx(0x2d3, {0x40});
    ib.uc(0x242, {1}).uc(0x25b, {0x201}).load_pairs(0x64, 0x20000000, 2);
    ib.sh(0x8a, {0x111, 0x0009002a}).sh(0x8c, {0xd0, 0xd1, 0xd2, 0xd3}).load_index_range(0x63, 0x20001000, 0x9c, 5);
    ib.sh(0xca, {0x333, 0x444}).sh(0xcc, {0xe0, 0xe1}).fl_state(kEsA);
    ib.draw_auto(3);                                // A
    ib.clear(1).ctx(0x1ff, {0x40}).stages(kFl);    // push: the context registers forgotten, one written
    ib.draw_auto(3);                                // B
    ib.clear(2);                                    // pop: A's context registers back
    ib.draw_auto(3);                                // C
    ib.cond(3).ctx(0x1ff, {0x80});                  // written inside a range: one of two
    ib.load_reg(0x5e, 0x20002000, 0x25b, 1).load_reg(0x61, 0x20003000, 0x2a6, 6);
    ib.draw_auto(3);                                // D
    ib.load_pairs(0x63, 0x30000000, 4);             // an unreadable SH pair table: SH registers unknown
    ib.draw_auto(3);                                // E
    ib.ib2().stages(kFl).draw_auto(3);              // F: after an INDIRECT_BUFFER everything is unknown
    Opt o;
    o.crumbs = 1;
    o.state  = 1;
    Run r    = run(ib, m, o);
    CHECK(r.draws == 6);
    X a = draw_x(0);
    CHECK(a.size == 71);
    CHECK(a.is(0, 0x20) && a.is(1, 0x20) && a.is(2, 2) && a.is(6, 0x40) && a.is(3, 0x00400801) && a.is(4, 0x40) && a.unknown(5) && a.unknown(11));
    CHECK(a.is(12, 1) && a.is(13, 0x201) && a.is(14, 1) && a.is(15, 7) && a.unknown(16));
    CHECK(a.unknown(17) && a.is(19, 0x111) && a.is(20, 0x0009002a) && a.is(21, 0xd0) && a.is(24, 0xd3) && a.unknown(25));
    CHECK(a.is(21 + 16, 0x160) && a.is(21 + 20, 0x164) && a.unknown(21 + 21) && a.is(53, 0x333) && a.is(54, 0x444) && a.is(55, 0xe0) && a.is(56, 0xe1) && a.unknown(57));
    X b = draw_x(1);
    CHECK(b.is(0, 0x40) && b.unknown(1) && b.unknown(2) && b.is(12, 1) && b.is(19, 0x111) && b.is(21, 0xd0)); // the push forgot the context ones only
    X c = draw_x(2);
    CHECK(c.is(0, 0x20) && c.is(2, 2) && c.is(3, 0x00400801)); // the pop brought them back
    X d = draw_x(3);
    CHECK(d.size == 71 && d.n[0] == 2 && ((d.v0[0] == 0x80 && d.v1[0] == 0x20) || (d.v0[0] == 0x20 && d.v1[0] == 0x80)));
    CHECK(d.is(13, 0x301) && d.is(11, 0x11) && d.is(5, 0x22)); // LOAD_UCONFIG_REG and LOAD_CONTEXT_REG ranges
    X e = draw_x(4);
    CHECK(e.unknown(19) && e.unknown(21) && e.unknown(55) && e.is(13, 0x301) && e.n[0] == 2); // SH forgotten, the rest kept
    X f = draw_x(5);
    bool all_unknown = f.size == 71;
    for (uint32_t i = 0; i < f.size; i++) all_unknown = all_unknown && f.n[i] == 0;
    CHECK(all_unknown);
    o.state = 0; // off: nothing tracked, the same packets
    const Run r0 = run(ib, m, o);
    CHECK(r0.info[19] == 0 && draw_x(0).size == 0 && r0.out == r.out);
    End("pure");
}

// ---- 9. A1: the lines, the next draw, its ring entry ------------------------------------------------------------------
static void ProbeText() {
    Begin("A1 lines");
    std::vector<uint32_t> n(71, 0), v0(71, 0), v1(71, 0);
    n[0] = 1, v0[0] = 0x20;
    n[1] = 2, v0[1] = 0x20, v1[1] = 0x40;
    n[21] = 1, v0[21] = 0xabcd;
    n[55] = 1, v0[55] = 0x1234;
    char           t[8192];
    const uint32_t len = bc5_flx0401_state_text(n.data(), v0.data(), v1.data(), 71, t, sizeof(t));
    const std::string s(t);
    CHECK(len == s.size() && std::count(s.begin(), s.end(), '\n') == 6);
    CHECK(s.rfind("context: GE_MAX_OUTPUT_PER_SUBGROUP 00000020 VGT_GS_MAX_VERT_OUT 00000020|00000040 VGT_GS_OUT_PRIM_TYPE ? VGT_GS_ONCHIP_CNTL ?", 0) == 0);
    CHECK(s.find("\nuconfig: VGT_PRIMITIVE_TYPE ? GE_CNTL ? GE_USER_VGPR_EN ? GE_USER_VGPR1 ? GE_PC_ALLOC ?\n") != std::string::npos);
    CHECK(s.find("\nSH: SPI_SHADER_PGM_LO_GS ? SPI_SHADER_PGM_HI_GS ? SPI_SHADER_PGM_RSRC1_GS ? SPI_SHADER_PGM_RSRC2_GS ? SPI_SHADER_PGM_RSRC1_ES ? SPI_SHADER_PGM_RSRC2_ES ?\n") !=
          std::string::npos);
    CHECK(s.find("\nGS user data 0-15: 0000abcd ? ? ? ? ? ? ? ? ? ? ? ? ? ? ?\n") != std::string::npos);
    CHECK(s.find("\nGS user data 16-31: ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ?\n") != std::string::npos);
    CHECK(s.find("\nES user data 0-15: 00001234 ? ? ? ? ? ? ? ? ? ? ? ? ? ? ?\n") != std::string::npos);
    bc5_flx0401_state_text(n.data(), v0.data(), v1.data(), 0, t, sizeof(t));
    CHECK(std::string(t).rfind("registers: not tracked for this draw", 0) == 0);
    const uint32_t crumbs[6] = {1, 0, 1, 1, 0, 1};
    CHECK(bc5_flx0401_next(crumbs, 6, 2, 2, 2) == 3 && bc5_flx0401_next(crumbs, 6, 2, 3, 3) == 5 && bc5_flx0401_next(crumbs, 6, 1, 5, -1) == -1);
    CHECK(bc5_flx0401_next(crumbs, 6, 1, 0, -1) == 2 && bc5_flx0401_next(crumbs, 6, 0, -1, -1) == -1 && bc5_flx0401_next(crumbs, 6, 3, 3, -1) == -1);
    uint32_t       e[32] = {};
    const uint64_t id    = id_of(1702);
    CHECK(bc5_flx0401_entry_reading(e, id) == 3); // never written
    e[0] = lo(id), e[1] = static_cast<uint32_t>(id >> 32u);
    CHECK(bc5_flx0401_entry_reading(e, id) == 1); // begun
    e[30] = e[0], e[31] = e[1];
    CHECK(bc5_flx0401_entry_reading(e, id) == 0); // complete
    e[1] = 1780;                                  // this submission's draw at +1780 (the ring wrapped)
    CHECK(bc5_flx0401_entry_reading(e, id) == 2);
    e[0] = static_cast<uint32_t>(kSubmit - 1u), e[1] = 5; // an earlier submission's
    CHECK(bc5_flx0401_entry_reading(e, id) == 4);
    End("pure");
}

// ---- 10. A4: the meshlet walk on synthetic tables ---------------------------------------------------------------------
constexpr uint64_t kObj = 0x30000000ull, kPath = 0x30001000ull, kPath2 = 0x30003000ull, kTab = 0x30002000ull, kRecs = 0x30010000ull, kHdrs = 0x30020000ull, kIbuf = 0x30030000ull;
void put_vsharp(Mem& m, uint64_t base, uint64_t byte, uint64_t a, uint32_t stride, uint32_t records) {
    m.at(base, byte)      = lo(a);
    m.at(base, byte + 4)  = hi16(a) | (stride << 16u);
    m.at(base, byte + 8)  = records;
    m.at(base, byte + 12) = 0x0002'0000u;
}
std::vector<uint32_t> vs(uint64_t a, uint32_t stride, uint32_t records) { return {lo(a), hi16(a) | (stride << 16u), records, 0x0002'0000u}; }
Mem mesh_mem() {
    Mem m;
    m.put(kObj, std::vector<uint32_t>(400, 0u)); // 100 records of 16 bytes
    m.at(kObj, 3 * 16 + 8) = 3;                  // pattern 1: object 3 -> record 3
    m.at(kObj, 5 * 16 + 8) = 5;                  // object 5 -> record 5
    m.at(kObj, 3 * 16 + 4) = 3;                  // pattern 2: object 3 -> record 3
    m.put(kPath, {0u, 0u});                      // the direct path
    m.put(kPath2, {1u, 10u});                    // the index path, start 10
    m.put(kTab, std::vector<uint32_t>(0x700 / 4, 0u));
    put_vsharp(m, kTab, 0x540, kIbuf, 4, 64);
    put_vsharp(m, kTab, 0x5a0, kHdrs, 4, 0x100);
    put_vsharp(m, kTab, 0x620, kRecs, 64, 16);
    m.put(kRecs, std::vector<uint32_t>(16 * 16, 0u));
    m.at(kRecs, 3 * 64 + 0x14) = 0x40; // header base
    m.at(kRecs, 3 * 64 + 0x18) = 4;    // meshlet count
    m.at(kRecs, 3 * 64 + 0x1c) = 0x40; // flag bit 6
    m.at(kRecs, 5 * 64 + 0x18) = 100;  // record 5: flags 0
    m.put(kHdrs, std::vector<uint32_t>(0x100, 0u));
    m.at(kHdrs, 0x40 + 0) = (63u << 24u) | (31u << 17u); // 64 primitives, 32 vertices
    m.at(kHdrs, 0x40 + 4) = 32u << 17u;                  // 33 vertices
    m.at(kHdrs, 0x40 + 8) = 64u << 24u;                  // 65 primitives
    m.put(kIbuf, std::vector<uint32_t>(64, 0u));
    m.at(kIbuf, 10 * 4) = 20;
    for (uint32_t p = 0; p < 8; p++) m.at(kIbuf, (20 + p) * 4) = (3u << 16u) | p;
    return m;
}
std::vector<uint32_t> ud_pattern(int pat, uint64_t path, uint32_t base) {
    std::vector<uint32_t> ud(32, 0u);
    const auto            put = [&ud](uint32_t k, const std::vector<uint32_t>& v) { std::copy(v.begin(), v.end(), ud.begin() + k); };
    put(0, vs(kObj, 16, 100));
    put(pat == 1 ? 12 : 8, vs(path, 0, 8));
    put(pat == 1 ? 16 : 12, vs(kTab, 0, 0x700));
    ud[pat == 1 ? 20 : 16] = base;
    return ud;
}
static void Meshlet() {
    Begin("A4 meshlet walk");
    Mem                   m  = mesh_mem();
    std::vector<uint32_t> u1 = ud_pattern(1, kPath, 1);
    int32_t               c[14];
    CHECK(bc5_flx0401_mesh(kEsA, u1.data(), 2, 6, 4096, MemRead, &m, c) == 1); // object 1 + v6 2 = 3; meshlets 0..5
    CHECK(c[0] == 6 && c[1] == 6 && c[2] == 0 && c[3] == 0 && c[4] == 0 && c[5] == 2 && c[6] == 1 && c[7] == 1 && c[8] == 33 && c[9] == 65 && c[10] == 0);
    CHECK(c[11] == -1 && c[12] == 4 && c[13] == 1);
    uint64_t p[13];
    CHECK(bc5_flx0401_mesh_point(kEsA, u1.data(), 2, 0, MemRead, &m, p) == 1);
    CHECK(p[0] == 1 && p[1] == 1 && p[2] == 0 && p[3] == 3 && p[4] == 3 && p[5] == 0 && p[6] == 0x40 && p[7] == 4 && p[8] == 0x40 && p[9] == ((63u << 24u) | (31u << 17u)));
    CHECK(p[10] == kRecs + 3 * 64 && p[11] == kHdrs + 0x40 && p[12] == 0);
    CHECK(bc5_flx0401_mesh(kEsA, u1.data(), 4, 6, 4096, MemRead, &m, c) == 1); // object 5: flag bit 6 clear, count 100
    CHECK(c[4] == 6 && c[11] == 0 && c[5] == 0 && c[8] == 1 && c[9] == 1);
    std::vector<uint32_t> u2 = ud_pattern(2, kPath, 1); // pattern 2: entry +4, user data 8 / 12 / 16
    CHECK(bc5_flx0401_mesh(kEsB, u2.data(), 2, 6, 4096, MemRead, &m, c) == 2 && c[1] == 6 && c[5] == 2 && c[8] == 33 && c[9] == 65);
    CHECK(bc5_flx0401_mesh(kEsB2, u2.data(), 2, 6, 4096, MemRead, &m, c) == 2 && c[1] == 6 && c[5] == 2);
    std::vector<uint32_t> ui = ud_pattern(1, kPath2, 1); // the index path: ib[ib[10] + p] = (3 << 16) | p
    CHECK(bc5_flx0401_mesh(kEsA, ui.data(), 99, 6, 4096, MemRead, &m, c) == 1 && c[3] == 6 && c[5] == 2 && c[8] == 33 && c[9] == 65 && c[10] == 0);
    CHECK(bc5_flx0401_mesh_point(kEsA, ui.data(), 99, 5, MemRead, &m, p) == 1 && p[2] == 1 && p[3] == 3 && p[5] == 5);
    put_vsharp(m, kTab, 0x540, kIbuf, 4, 22); // 22 records: points 2..5 read past NUM_RECORDS (taken as 0)
    CHECK(bc5_flx0401_mesh(kEsA, ui.data(), 0, 6, 4096, MemRead, &m, c) == 1 && c[10] == 4 && c[1] == 6);
    put_vsharp(m, kTab, 0x540, kIbuf, 4, 64);
    std::vector<uint32_t> uu = u1; // the object table in unmapped memory: nothing readable
    uu[0]                    = 0x50000000u;
    CHECK(bc5_flx0401_mesh(kEsA, uu.data(), 2, 6, 4096, MemRead, &m, c) == 1 && c[1] == 0 && c[2] == 6);
    CHECK(bc5_flx0401_mesh_point(kEsA, uu.data(), 2, 0, MemRead, &m, p) == 0 && p[0] == 0 && p[1] == 0);
    CHECK(bc5_flx0401_mesh(kEsA, u1.data(), 2, 5000, 4096, MemRead, &m, c) == 1 && c[0] == 4096 && c[1] == 4096); // capped
    CHECK(bc5_flx0401_mesh(kEsOther, u1.data(), 2, 6, 4096, MemRead, &m, c) == 0 && c[1] == 0);                 // not a pattern program
    char t[2048];
    bc5_flx0401_mesh_text(kEsA, u1.data(), 2, 0, 6, 1, "the CP's copy", MemRead, &m, t, sizeof(t));
    const std::string s(t);
    CHECK(s.find("ES 11d01345 (pattern 1), 6 x 1 points (from the CP's copy), 6 followed: 6 read, 0 not readable, 0 by the index path") == 0);
    CHECK(s.find("record flag bit 6 clear 0 (first at point -1), meshlet index >= count 2 (first 4)") != std::string::npos);
    CHECK(s.find("headers up to 33 vertices and 65 primitives, above 32 vertices 1, above 64 primitives 1 (first 1)") != std::string::npos);
    CHECK(s.find("v6 00000002 (GE_USER_VGPR1); read now, about 2 s after the GPU ran it (the timeout), not at GPU time") != std::string::npos);
    bc5_flx0401_mesh_text(kEsA, u1.data(), 2, 2, 5000, 1, "memory now", MemRead, &m, t, sizeof(t));
    CHECK(std::string(t).find("5000 x 1 points (from memory now), 4096 followed (capped)") != std::string::npos && std::string(t).find("(assumed:") != std::string::npos);
    // flx_v6 and flx_user_data on a tracked state
    std::vector<uint32_t> n(71, 0), v0(71, 0), v1(71, 0);
    uint32_t              v6 = 99, ud[32];
    CHECK(bc5_flx0401_v6(n.data(), v0.data(), v1.data(), 71, &v6) == 2 && v6 == 0); // GE_USER_VGPR_EN not known
    n[14] = 1, v0[14] = 0;
    CHECK(bc5_flx0401_v6(n.data(), v0.data(), v1.data(), 71, &v6) == 1 && v6 == 0); // bit 0 clear
    v0[14] = 1;
    CHECK(bc5_flx0401_v6(n.data(), v0.data(), v1.data(), 71, &v6) == 2); // GE_USER_VGPR1 not known
    n[15] = 1, v0[15] = 7;
    CHECK(bc5_flx0401_v6(n.data(), v0.data(), v1.data(), 71, &v6) == 0 && v6 == 7);
    for (uint32_t k = 0; k < 21; k++) n[21 + k] = 1, v0[21 + k] = 0x100 + k;
    n[21 + 5] = 0; // user data 5: not read by either pattern
    CHECK(bc5_flx0401_user_data(n.data(), v0.data(), v1.data(), 71, 1, ud) == 1 && ud[20] == 0x114 && ud[5] == 0);
    n[21 + 13] = 0; // user data 13: pattern 1's path V#, pattern 2's table V#
    CHECK(bc5_flx0401_user_data(n.data(), v0.data(), v1.data(), 71, 1, ud) == 0 && bc5_flx0401_user_data(n.data(), v0.data(), v1.data(), 71, 2, ud) == 0);
    n[21 + 13] = 1, n[21 + 20] = 0; // user data 20: pattern 1's base only
    CHECK(bc5_flx0401_user_data(n.data(), v0.data(), v1.data(), 71, 1, ud) == 0 && bc5_flx0401_user_data(n.data(), v0.data(), v1.data(), 71, 2, ud) == 1);
    CHECK(bc5_flx0401_user_data(n.data(), v0.data(), v1.data(), 0, 2, ud) == 0); // not tracked
    End("pure");
}

// ---- 11. A5: the crumbs copy the object record and the headers --------------------------------------------------------
static void CrumbsMeshlet() {
    Begin("A5 crumbs copies");
    Mem m = mesh_mem();
    m.put(kBase1, std::vector<uint32_t>(0x1000, 0u));
    m.r[kBase1][0x1620 / 4] = 366;
    m.r[kBase1][0x1620 / 4 + 1] = 1;
    const auto set_ud = [](Ib& ib, const std::vector<uint32_t>& u, bool all) {
        ib.sh(0x8c, {u[0], u[1], u[2], u[3]});
        ib.sh(0x8cu + 12u, {u[12], u[13], u[14], u[15]});
        ib.sh(0x8cu + 16u, {u[16], u[17], u[18], u[19]});
        if (all) ib.sh(0x8cu + 20u, {u[20]});
    };
    std::vector<uint32_t> u1 = ud_pattern(1, kPath, 1);
    Ib                    ib;
    ib.uc(0x262, {1}).uc(0x25c, {2}); // v6 = 2: object 3
    set_ud(ib, u1, true);
    ib.fl_state(kEsA).base1(kBase1);
    const uint32_t at = ib.at();
    ib.draw_ind(0x1620);
    Opt o;
    o.crumbs = 1;
    o.state  = 1;
    o.ml     = 1;
    Run r    = run(ib, m, o);
    const uint64_t rec = kRecs + 3 * 64, hd = kHdrs + 0x40;
    CHECK(r.draws == 1 && r.d(0, 10) == 1 && r.info[13] == 1 && r.info[14] == 0);
    CHECK(r.d64(0, 14) == rec && r.d64(0, 16) == rec + 32 && r.d64(0, 18) == hd);
    std::vector<uint32_t> want = laid(ib, {{at, want_pre(at, 0, kBase1 + 0x1620, rec, rec + 32, hd), want_post(at)}});
    CHECKW(r.out == want, diff(r.out, want)); // the same three 32-byte copies, at the record and the headers
    uint64_t p[13];
    CHECK(bc5_flx0401_draw_mp0(0, p) == 1 && p[0] == 1 && p[3] == 3 && p[4] == 3 && p[10] == rec && p[11] == hd);
    o.ml = 0; // A5 off: the V# bases (user data 8/9 not set, 20/21 half set, 24/25 not set): no V# copy
    r    = run(ib, m, o);
    want = laid(ib, {{at, want_pre(at, 0, kBase1 + 0x1620, 0, 0, 0), want_post(at)}});
    CHECKW(r.out == want, diff(r.out, want));
    CHECK(r.d(0, 10) == 0 && r.info[13] == 0);
    o.ml = 1; // the headers' V# in unmapped memory: the object record only
    put_vsharp(m, kTab, 0x5a0, 0x60000000ull, 4, 0x100);
    r = run(ib, m, o);
    CHECK(r.d(0, 10) == 1 && r.d64(0, 14) == rec && r.d64(0, 16) == rec + 32 && r.d64(0, 18) == 0);
    want = laid(ib, {{at, want_pre(at, 0, kBase1 + 0x1620, rec, rec + 32, 0), want_post(at)}});
    CHECKW(r.out == want, diff(r.out, want));
    put_vsharp(m, kTab, 0x5a0, kHdrs, 4, 0x100);
    Ib iu; // user data 20 (the base) not set: not followed, counted, the V# bases instead
    iu.uc(0x262, {1}).uc(0x25c, {2});
    set_ud(iu, u1, false);
    iu.fl_state(kEsA).base1(kBase1).draw_ind(0x1620);
    r = run(iu, m, o);
    CHECK(r.d(0, 10) == 0 && r.info[13] == 0 && r.info[14] == 1);
    Ib io; // another ES: not a pattern draw, not counted
    io.uc(0x262, {1}).uc(0x25c, {2});
    set_ud(io, u1, true);
    io.fl_state(kEsOther).base1(kBase1).draw_ind(0x1620);
    r = run(io, m, o);
    CHECK(r.d(0, 10) == 0 && r.info[13] == 0 && r.info[14] == 0);
    Ib i2; // pattern 2, GE_USER_VGPR_EN bit 0 clear: v6 0, base 3
    std::vector<uint32_t> u2 = ud_pattern(2, kPath, 3);
    i2.uc(0x262, {0});
    i2.sh(0x8c, {u2[0], u2[1], u2[2], u2[3]}).sh(0x8cu + 8u, {u2[8], u2[9], u2[10], u2[11]}).sh(0x8cu + 12u, {u2[12], u2[13], u2[14], u2[15], u2[16]});
    i2.fl_state(kEsB).base1(kBase1).draw_ind(0x1620);
    r = run(i2, m, o);
    CHECK(r.d(0, 10) == 2 && r.d64(0, 14) == rec && r.d64(0, 18) == hd);
    End("pure");
}

// ---- 12. the unit's reading through the real fl_plan_buffer and fl_after (mode) -----------------------------------
static void Glue(bool on) {
    Begin("fl_plan_buffer and fl_after");
    Ib g;
    g.stages(kNgg);
    g.draw_auto(3).fl_state(kEsA);
    const uint32_t a = g.at();
    g.draw_auto(3);
    const uint32_t b = g.at();
    g.draw_auto(3);
    const uint32_t nn = g.at();
    g.nop(2);
    uint32_t info[8] = {};
    bc5_flx0401_plan_buffer(g.d.data(), g.at(), "dcb", info);
    if (on) {
        CHECK(info[0] == 3 && info[1] == 2 && info[2] == 1 && info[3] == 2 && info[4] == 0 && info[5] == 1 && info[6] == 0 && info[7] == 0); // transition: A only
    } else {
        CHECK(info[0] == 0 && info[1] == 0 && info[5] == 0); // exp 0404's early return: nothing followed
    }
    std::vector<uint32_t> out(g.d.size() + 64, 0u);
    uint32_t              drops[1] = {nn}, ai[6] = {};
    const uint32_t        size     = bc5_flx0401_after(g.d.data(), g.at(), "dcb", drops, 1, out.data(), static_cast<uint32_t>(out.size()), ai);
    out.resize(size);
    if (on) {
        const std::vector<uint32_t> want = laid(g, {{a, kF1, kF2}, {b, {}, kF2}});
        CHECKW(out == want, diff(out, want));
        CHECK(ai[1] == 1 && ai[2] == 2 && ai[3] == 0 && ai[5] == 0 && drops[0] == nn + 8u); // the drop offset mapped into the copy
    } else {
        CHECK(size == 0 && drops[0] == nn && ai[1] == 0 && ai[2] == 0);
    }
    End(on ? "on" : "off");
}

} // namespace flx0401

#ifdef _WIN32
static void set_env(const char* n, const char* v) { _putenv_s(n, v == nullptr ? "" : v); }
#else
static void set_env(const char* n, const char* v) {
    if (v == nullptr) ::unsetenv(n);
    else ::setenv(n, v, 1);
}
#endif

int main(int argc, char** argv) {
    using namespace flx0401;
    if (argc != 2 || (std::strcmp(argv[1], "on") != 0 && std::strcmp(argv[1], "off") != 0)) {
        std::printf("flx0401: usage: flx0401 on | flx0401 off\n");
        return 2;
    }
    const bool on = std::strcmp(argv[1], "on") == 0;
    set_env("BC5_DIRECT_FL_PROBE_STATE", on ? "1" : nullptr);
    set_env("BC5_DIRECT_FL_VGT_FLUSH", on ? "transition" : nullptr);
    set_env("BC5_DIRECT_FL_SERIAL", on ? "1" : nullptr);
    set_env("BC5_DIRECT_FL_MESHLET_PROBE", on ? "1" : nullptr);
    set_env("BC5_DIRECT_FL_CRUMBS_MESHLET", on ? "1" : nullptr);
    set_env("BC5_DIRECT_FL_CRUMBS", nullptr);
    set_env("BC5_DIRECT_FL_SKIP_ES", nullptr);
    std::thread([] {
        std::this_thread::sleep_for(std::chrono::seconds(60));
        std::printf("flx0401: FAIL watchdog: case \"%s\" still running after 60 s\n", g_case.load());
        std::fflush(stdout);
        std::_Exit(3);
    }).detach();

    Switches(on);
    Consts();
    ParseHeads();
    OffToday();
    Flushes();
    Transition();
    Cond();
    Tracking();
    ProbeText();
    Meshlet();
    CrumbsMeshlet();
    Glue(on);

    std::fflush(stderr);
    std::printf("flx0401: %s %d of %d%s\n", on ? "on" : "off", g_pass, g_total, g_pass == g_total ? "; end" : "");
    std::fflush(stdout);
    std::_Exit(g_pass == g_total ? 0 : 1);
}
