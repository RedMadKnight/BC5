// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0401 series e8, tag smp: the CPU test of mksmp0401.py's src/libs/bc5LleAgc.cpp (smp0401-notes.md): the
// switch BC5_DIRECT_FL_MESHLET_SAMPLE, A4's per-point meshlet walk on completed draws in two range models. It calls the
// unit through its seams (bc5_smp0401_* and flx's bc5_flx0401_*): the switch's reading, the parse, the pure timer and the
// real one, both range models of the walk on synthetic object tables, records and headers (model 0 is flx's walk unchanged),
// the journal line of one draw, and the real fl_plan_buffer and smp_sample. No game, no GPU, no window, no sound device, no
// network: the direct path is never opened (g_dev stays empty), nothing is submitted anywhere.
// "on" sets BC5_DIRECT_FL_MESHLET_SAMPLE=5 before the first call, "off" unsets it; both set BC5_DIRECT_FL_CRUMBS=1 and
// BC5_DIRECT_FL_SERIAL=1 (so that fl_plan_buffer plans the draws without a device) and unset flx's other switches. The
// unit reads each switch once. The pure cases run in both modes; the switch and glue cases check the mode.
// Output: one line per case, then "smp0401: on N of N; end" or "smp0401: off N of N; end"; without "; end" something
// failed. Exit 0 only after the end line. A watchdog ends a hang after 60 s with a FAIL line.
// Build: build0401.py ... --gate smp0401.cpp <out> --like src/libs/bc5LleAgc.cpp (the unit's compile command; linked with
// every emulator object but main.cpp.o, the private bc5LleAgc.cpp.o among them), -std=c++20 -Wall -Wextra -Werror.
// usage: smp0401 on | smp0401 off

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

// The seams of mksmp0401.py's unit (always compiled in, never called by the emulator), and two of flx's.
typedef const uint32_t* (*FlxReadFn)(uint64_t a, uint64_t bytes, void* ctx);
extern "C" int      bc5_smp0401_parse(const char* e, int* bad);
extern "C" int      bc5_smp0401_period();
extern "C" int      bc5_smp0401_due(int64_t now_ms, int64_t* next_ms, int period);
extern "C" int      bc5_smp0401_take(int period);
extern "C" void     bc5_smp0401_consts(uint32_t* out);
extern "C" int      bc5_smp0401_mesh(uint32_t es, const uint32_t* ud, uint32_t v6, uint32_t points, uint32_t cap, int raw, FlxReadFn read, void* ctx, int32_t* out);
extern "C" int      bc5_smp0401_point(uint32_t es, const uint32_t* ud, uint32_t v6, uint32_t point, int raw, FlxReadFn read, void* ctx, uint64_t* out);
extern "C" int      bc5_smp0401_text(const uint32_t* ns, const uint32_t* v0, const uint32_t* v1, uint32_t count, uint32_t es, uint32_t op, uint32_t at, uint64_t args, uint32_t vcount,
                                     FlxReadFn read, void* ctx, char* out, uint32_t cap);
extern "C" uint32_t bc5_smp0401_plan_x(const uint32_t* ib, uint32_t n, const char* kind, uint32_t* info);
extern "C" uint64_t bc5_smp0401_sample(int crumbs, uint32_t es);
extern "C" void     bc5_flx0401_consts(uint32_t* out);
extern "C" int      bc5_flx0401_mesh(uint32_t es, const uint32_t* ud, uint32_t v6, uint32_t points, uint32_t cap, FlxReadFn read, void* ctx, int32_t* out);
extern "C" int      bc5_flx0401_mesh_point(uint32_t es, const uint32_t* ud, uint32_t v6, uint32_t point, FlxReadFn read, void* ctx, uint64_t* out);

namespace smp0401 {

static int                      g_pass = 0, g_total = 0, g_case_pass = 0, g_case_total = 0;
static std::atomic<const char*> g_case {"init"};

static void Check(bool ok, const char* what, int line, const std::string& why = "") {
    g_total++;
    g_case_total++;
    if (ok) {
        g_pass++;
        g_case_pass++;
    } else {
        std::printf("smp0401: FAIL %s (line %d): %s%s%s\n", g_case.load(), line, what, why.empty() ? "" : ": ", why.c_str());
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
    std::printf("smp0401: case %s (%s): %d of %d\n", g_case.load(), how, g_case_pass, g_case_total);
    std::fflush(stdout);
}

// ---- the test's own constants and synthetic memory (flx0401.cpp's section 10, the same tables) -----------------------
constexpr uint32_t kFl  = 0x00482030u; // VGT_SHADER_STAGES_EN: fast-launch
constexpr uint32_t kEsA = 0x11d01345u, kEsB = 0x11d00f85u, kEsOther = 0x11d01000u;
constexpr uint64_t kObj = 0x30000000ull, kPath = 0x30001000ull, kPath2 = 0x30003000ull, kTab = 0x30002000ull, kRecs = 0x30010000ull, kHdrs = 0x30020000ull, kIbuf = 0x30030000ull;
constexpr uint64_t kArgs = 0x30040000ull;

uint32_t lo(uint64_t a) { return static_cast<uint32_t>(a); }
uint32_t hi16(uint64_t a) { return static_cast<uint32_t>(a >> 32u) & 0xffffu; }
uint32_t hdr(uint32_t op, uint32_t len) { return 0xC0000000u | ((len - 2u) << 16u) | (op << 8u); }

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
    Ib& stages(uint32_t v) { return set(0x69, 0x2d5, {v}); }
    Ib& es(uint32_t lo_value) { return set(0x76, 0xc8, {lo_value, 0u}); } // SPI_SHADER_PGM_LO_ES, HI_ES
    Ib& draw_auto(uint32_t count) { return pkt(0x2d, {count, 2u}); }
    Ib& nop(uint32_t len) {
        d.push_back(hdr(0x10, len));
        d.insert(d.end(), len - 1u, 0u);
        return *this;
    }
};

struct Mem { // GPU address -> dwords the "CPU" may read
    std::map<uint64_t, std::vector<uint32_t>> r;
    void      put(uint64_t a, std::vector<uint32_t> v) { r[a] = std::move(v); }
    uint32_t& at(uint64_t base, uint64_t byte) { return r[base][byte / 4u]; }
    const uint32_t* get(uint64_t a, uint64_t bytes) const {
        for (const auto& [base, v]: r) {
            if (a >= base && a + bytes <= base + v.size() * 4u && (a - base) % 4u == 0) return v.data() + (a - base) / 4u;
        }
        return nullptr;
    }
};
const uint32_t* MemRead(uint64_t a, uint64_t bytes, void* ctx) { return static_cast<const Mem*>(ctx)->get(a, bytes); }

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
    m.put(kArgs, {6u, 1u, 5000u, 1u});
    return m;
}
std::vector<uint32_t> ud_pattern(int pat, uint64_t path, uint32_t base, uint32_t obj_records = 100) {
    std::vector<uint32_t> ud(32, 0u);
    const auto            put = [&ud](uint32_t k, const std::vector<uint32_t>& v) { std::copy(v.begin(), v.end(), ud.begin() + k); };
    put(0, vs(kObj, 16, obj_records));
    put(pat == 1 ? 12 : 8, vs(path, 0, 8));
    put(pat == 1 ? 16 : 12, vs(kTab, 0, 0x700));
    ud[pat == 1 ? 20 : 16] = base;
    return ud;
}
std::string str(const int32_t* c, int k) {
    std::string s;
    for (int i = 0; i < k; i++) s += std::to_string(c[i]) + " ";
    return s;
}

// ---- 1. the switch as the unit reads it (mode) ------------------------------------------------------------------------
static void Switch(bool on) {
    Begin("the switch");
    CHECK(bc5_smp0401_period() == (on ? 5 : 0));
    CHECK(bc5_smp0401_period() == (on ? 5 : 0)); // read once
    uint32_t c[3] = {}, f[16] = {};
    bc5_smp0401_consts(c);
    bc5_flx0401_consts(f);
    CHECK(c[0] == 1024 && c[1] == 64 && c[2] == 4096 && f[12] == 4096);
    End(on ? "on" : "off");
}

// ---- 2. the parse ----------------------------------------------------------------------------------------------------
static void Parse() {
    Begin("the parse");
    int bad = 9;
    CHECK(bc5_smp0401_parse(nullptr, &bad) == 0 && bad == 0);
    CHECK(bc5_smp0401_parse("", &bad) == 0 && bad == 0);
    CHECK(bc5_smp0401_parse("0", &bad) == 0 && bad == 0);
    CHECK(bc5_smp0401_parse("off", &bad) == 0 && bad == 0);
    CHECK(bc5_smp0401_parse("1", &bad) == 1 && bad == 0);
    CHECK(bc5_smp0401_parse("5", &bad) == 5 && bad == 0);
    CHECK(bc5_smp0401_parse("3600", &bad) == 3600 && bad == 0);
    for (const char* e: {"3601", "-5", "5s", "abc", "on", "1.5", "99999999999999999999"}) CHECKW(bc5_smp0401_parse(e, &bad) == 0 && bad == 1, e);
    End("pure");
}

// ---- 3. the timer: the pure rule, then the unit's own --------------------------------------------------------------
static void Timer() {
    Begin("the timer");
    int64_t next = 0;
    CHECK(bc5_smp0401_due(100, &next, 5) == 1 && next == 5100);
    CHECK(bc5_smp0401_due(5099, &next, 5) == 0 && next == 5100);
    CHECK(bc5_smp0401_due(5100, &next, 5) == 1 && next == 10100);
    CHECK(bc5_smp0401_due(1'000'000, &next, 0) == 0 && next == 10100); // off: never due
    CHECK(bc5_smp0401_due(1'000'000, &next, -3) == 0);
    next = 0;
    CHECK(bc5_smp0401_due(0, &next, 3600) == 1 && next == 3'600'000);
    // The real timer: once a period, for one caller. smp_sample without a device never reaches it (the case below runs first).
    CHECK(bc5_smp0401_take(5) == 1);
    CHECK(bc5_smp0401_take(5) == 0 && bc5_smp0401_take(5) == 0);
    End("pure");
}

// ---- 4. the two range models -------------------------------------------------------------------------------------------
static void Models() {
    Begin("both range models");
    Mem     m = mesh_mem();
    int32_t a[14], b[14], c[14];
    // Model 0 is flx's walk, unchanged: the direct path, the index path, pattern 2, a load past NUM_RECORDS, a cap.
    const std::vector<uint32_t> u1 = ud_pattern(1, kPath, 1), ui = ud_pattern(1, kPath2, 1), u2 = ud_pattern(2, kPath, 1);
    struct Arm {
        uint32_t                     es;
        const std::vector<uint32_t>* ud;
        uint32_t                     v6, points;
    };
    for (const Arm& r: {Arm {kEsA, &u1, 2, 6}, Arm {kEsA, &u1, 4, 6}, Arm {kEsA, &ui, 99, 6}, Arm {kEsB, &u2, 2, 6}, Arm {kEsA, &u1, 2, 5000}, Arm {kEsOther, &u1, 2, 6}}) {
        const int pa = bc5_smp0401_mesh(r.es, r.ud->data(), r.v6, r.points, 4096, 0, MemRead, &m, a);
        const int pb = bc5_flx0401_mesh(r.es, r.ud->data(), r.v6, r.points, 4096, MemRead, &m, b);
        CHECKW(pa == pb && std::memcmp(a, b, sizeof(a)) == 0, str(a, 14) + "| " + str(b, 14));
    }
    // With no load past NUM_RECORDS, model 1 is model 0.
    CHECK(bc5_smp0401_mesh(kEsA, u1.data(), 2, 6, 4096, 1, MemRead, &m, a) == 1 && bc5_smp0401_mesh(kEsA, u1.data(), 2, 6, 4096, 0, MemRead, &m, b) == 1);
    CHECKW(std::memcmp(a, b, sizeof(a)) == 0 && a[10] == 0, str(a, 14));
    // The scalar load: an object table of 2 records (32 bytes) puts object 3's entry (byte 56) past it. Model 0 reads 0 and
    // lands on the empty record 0 for every point; model 1 reads the table there and walks as with 100 records.
    const std::vector<uint32_t> us = ud_pattern(1, kPath, 1, 2);
    CHECK(bc5_smp0401_mesh(kEsA, us.data(), 2, 6, 4096, 0, MemRead, &m, a) == 1);
    CHECKW(a[1] == 6 && a[4] == 6 && a[5] == 6 && a[12] == 0 && a[10] == 6 && a[8] == 1 && a[9] == 1, str(a, 14)); // flag 6 clear, index >= count 0, headers 0
    CHECK(bc5_smp0401_mesh(kEsA, us.data(), 2, 6, 4096, 1, MemRead, &m, b) == 1 && bc5_smp0401_mesh(kEsA, u1.data(), 2, 6, 4096, 0, MemRead, &m, c) == 1);
    CHECKW(std::memcmp(b, c, 10 * sizeof(int32_t)) == 0 && b[10] == 6 && c[10] == 0 && b[11] == c[11] && b[12] == c[12] && b[13] == c[13], str(b, 14) + "| " + str(c, 14));
    uint64_t p[13], q[13];
    CHECK(bc5_smp0401_point(kEsA, us.data(), 2, 0, 0, MemRead, &m, p) == 1 && p[4] == 0 && p[7] == 0 && p[10] == kRecs && p[12] == 1); // record 0, count 0
    CHECK(bc5_smp0401_point(kEsA, us.data(), 2, 0, 1, MemRead, &m, p) == 1 && p[4] == 3 && p[7] == 4 && p[10] == kRecs + 3 * 64 && p[12] == 1);
    CHECK(bc5_flx0401_mesh_point(kEsA, us.data(), 2, 0, MemRead, &m, q) == 1 && q[4] == 0 && q[12] == 1); // flx: model 0
    // The typed load: an index buffer of 22 records puts points 2..5 of the index path past it.
    put_vsharp(m, kTab, 0x540, kIbuf, 4, 22);
    CHECK(bc5_smp0401_mesh(kEsA, ui.data(), 0, 6, 4096, 0, MemRead, &m, a) == 1 && a[10] == 4 && a[1] == 6);
    CHECK(bc5_smp0401_mesh(kEsA, ui.data(), 0, 6, 4096, 1, MemRead, &m, b) == 1 && b[10] == 4);
    put_vsharp(m, kTab, 0x540, kIbuf, 4, 64);
    CHECK(bc5_smp0401_mesh(kEsA, ui.data(), 0, 6, 4096, 0, MemRead, &m, c) == 1 && c[10] == 0);
    CHECKW(std::memcmp(b, c, 10 * sizeof(int32_t)) == 0 && std::memcmp(a, c, 10 * sizeof(int32_t)) != 0, str(a, 14) + "| " + str(b, 14) + "| " + str(c, 14));
    // Model 1 still refuses what cannot be read: past the end of the memory the reader has.
    put_vsharp(m, kTab, 0x540, kIbuf, 4, 22);
    m.at(kIbuf, 10 * 4) = 60; // start 60: points 0..5 at 60..65, the buffer has 64 dwords
    CHECK(bc5_smp0401_mesh(kEsA, ui.data(), 0, 6, 4096, 1, MemRead, &m, a) == 1);
    CHECKW(a[1] == 4 && a[2] == 2, str(a, 14)); // 60..63 read, 64 and 65 not readable
    End("pure");
}

// ---- 5. one draw's line ------------------------------------------------------------------------------------------------
struct X {
    std::vector<uint32_t> n, v0, v1;
};
static X draw_x(const std::vector<uint32_t>& ud, uint32_t v6) {
    uint32_t f[16] = {};
    bc5_flx0401_consts(f); // [3] kFlxN, [8] kFlxGsUd, [10] kFlxUserVgprEn, [11] kFlxUserVgpr1
    X x;
    x.n.assign(f[3], 0u);
    x.v0.assign(f[3], 0u);
    x.v1.assign(f[3], 0u);
    x.n[f[10]] = 1, x.v0[f[10]] = 1;  // GE_USER_VGPR_EN bit 0
    x.n[f[11]] = 1, x.v0[f[11]] = v6; // GE_USER_VGPR1
    for (uint32_t k = 0; k < 32 && f[8] + k < f[3]; k++) x.n[f[8] + k] = 1, x.v0[f[8] + k] = ud[k];
    return x;
}
static void Text() {
    Begin("one draw's line");
    Mem         m  = mesh_mem();
    const X     x  = draw_x(ud_pattern(1, kPath, 1), 2);
    const auto  tx = [&](const X& xx, uint32_t es, uint32_t op, uint64_t args, uint32_t vcount, std::string& s) {
        char      t[4096];
        const int r = bc5_smp0401_text(xx.n.data(), xx.v0.data(), xx.v1.data(), static_cast<uint32_t>(xx.n.size()), es, op, 1702, args, vcount, MemRead, &m, t, sizeof(t));
        s           = t;
        return r;
    };
    std::string s;
    CHECK(tx(x, kEsA, 0x24, kArgs, 0, s) == 3);
    CHECKW(s.find("fl meshlet sample (exp 0401 e8 smp): test: submit #7 dcb op 24 at 1702: ES 11d01345 (pattern 1): 6 x 1 points (from memory now), v6 00000002 (GE_USER_VGPR1)") == 0, s);
    CHECKW(s.find("; model 0 (past NUM_RECORDS read as 0): 6 followed of 6 (0 not readable), 0 by the index path, record flag bit 6 clear 0, meshlet index >= count 2 (first 4), "
                  "headers up to 33 vertices and 65 primitives, above 32 vertices 1, above 64 primitives 1, loads past NUM_RECORDS 0; model 1 (past NUM_RECORDS read as the memory there): 6 followed of 6") !=
               std::string::npos,
           s);
    CHECKW(s.find("; point 0, model 0: object 3, record index 3 at 0x300100c0 (flags 00000040, meshlet count 4, header base 00000040), meshlet 0, header 3f3e0000 (32 vertices, 64 primitives), "
                  "0 loads past NUM_RECORDS; point 0, model 1: object 3, record index 3 at 0x300100c0") != std::string::npos,
           s);
    CHECK(tx(x, kEsA, 0x2d, 0, 6, s) == 3 && s.find("6 x 1 points (from the packet), v6") != std::string::npos);
    CHECK(tx(x, kEsA, 0x24, kArgs + 8, 0, s) == 3 && s.find("5000 x 1 points (from memory now), walked up to the cap") != std::string::npos &&
          s.find("model 0 (past NUM_RECORDS read as 0): 1024 followed of 1024") != std::string::npos);
    CHECK(tx(x, kEsA, 0x24, 0x50000000ull, 0, s) == 2 && s.find(": no readable arguments to count its points: not walked") != std::string::npos);
    CHECK(tx(x, kEsA, 0x24, 0, 0, s) == 2);
    CHECK(tx(x, kEsOther, 0x24, kArgs, 0, s) == 0 && s.empty());
    X none; // no tracked state
    CHECK(tx(none, kEsA, 0x24, kArgs, 0, s) == 1 && s.find(": the user data it reads were not known for certain at the draw: not walked") != std::string::npos);
    const X xs = draw_x(ud_pattern(1, kPath, 1, 2), 2); // the object table of 2 records: model 0's empty record
    CHECK(tx(xs, kEsA, 0x24, kArgs, 0, s) == 3);
    CHECKW(s.find("model 0 (past NUM_RECORDS read as 0): 6 followed of 6 (0 not readable), 0 by the index path, record flag bit 6 clear 6, meshlet index >= count 6 (first 0)") != std::string::npos &&
               s.find("; point 0, model 0: object 3, record index 0 at 0x30010000 (flags 00000000, meshlet count 0, header base 00000000)") != std::string::npos &&
               s.find("; point 0, model 1: object 3, record index 3 at 0x300100c0 (flags 00000040, meshlet count 4") != std::string::npos,
           s);
    End("pure");
}

// ---- 6. the real fl_plan_buffer and smp_sample (mode) ------------------------------------------------------------------
static void Glue(bool on) {
    Begin("fl_plan_buffer and smp_sample");
    // smp_sample with no device never walks and never takes the timer (the timer case runs after this one).
    CHECK(bc5_smp0401_sample(1, kEsA) == 0 && bc5_smp0401_sample(0, kEsA) == 0);
    Ib g;
    g.stages(kFl).es(kEsA);
    g.draw_auto(3);
    g.nop(2);
    uint32_t info[3] = {9, 9, 9};
    bc5_smp0401_plan_x(g.d.data(), g.at(), "dcb", info);
    // F2 plans the draw without a device in both modes; the state is tracked for it only with the switch on.
    CHECK(info[0] == 1 && info[2] == 0);
    uint32_t f[16] = {};
    bc5_flx0401_consts(f);
    CHECKW(on ? info[1] == f[3] : info[1] == 0, std::to_string(info[1]));
    End(on ? "on" : "off");
}

} // namespace smp0401

#ifdef _WIN32
static void set_env(const char* n, const char* v) { _putenv_s(n, v == nullptr ? "" : v); }
#else
static void set_env(const char* n, const char* v) {
    if (v == nullptr) ::unsetenv(n);
    else ::setenv(n, v, 1);
}
#endif

int main(int argc, char** argv) {
    using namespace smp0401;
    if (argc != 2 || (std::strcmp(argv[1], "on") != 0 && std::strcmp(argv[1], "off") != 0)) {
        std::printf("smp0401: usage: smp0401 on | smp0401 off\n");
        return 2;
    }
    const bool on = std::strcmp(argv[1], "on") == 0;
    set_env("BC5_DIRECT_FL_MESHLET_SAMPLE", on ? "5" : nullptr);
    set_env("BC5_DIRECT_FL_CRUMBS", "1");
    set_env("BC5_DIRECT_FL_SERIAL", "1");
    for (const char* n: {"BC5_DIRECT_FL_PROBE_STATE", "BC5_DIRECT_FL_VGT_FLUSH", "BC5_DIRECT_FL_MESHLET_PROBE", "BC5_DIRECT_FL_CRUMBS_MESHLET", "BC5_DIRECT_FL_SKIP_ES"}) set_env(n, nullptr);
    std::thread([] {
        std::this_thread::sleep_for(std::chrono::seconds(60));
        std::printf("smp0401: FAIL watchdog: case \"%s\" still running after 60 s\n", g_case.load());
        std::fflush(stdout);
        std::_Exit(3);
    }).detach();

    Switch(on);
    Parse();
    Glue(on);
    Timer();
    Models();
    Text();

    std::fflush(stderr);
    std::printf("smp0401: %s %d of %d%s\n", on ? "on" : "off", g_pass, g_total, g_pass == g_total ? "; end" : "");
    std::fflush(stdout);
    std::_Exit(g_pass == g_total ? 0 : 1);
}
