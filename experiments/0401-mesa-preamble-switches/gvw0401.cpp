// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0401 series e9, tag gvw: the CPU test of mkgvw0401.py's src/libs/bc5LleAgc.cpp (gvw0401-notes.md): the
// given-up-wait side's four switches, BC5_DIRECT_WAIT_LATE_PRODUCER_MS, BC5_DIRECT_UNWAITED_FL_DROP, BC5_DIRECT_GIVEUP_JOURNAL
// and BC5_DIRECT_FL_MESHLET_SAMPLE_UNWAITED. It calls the unit through its seams (bc5_gvw0401_*, and smp's, flx's and
// cap's): the switches' reading and parse, the late-producer decision and the compute-queue scan on queues and buffers of
// its own, the host's decision with the unit's real registries (exp 0055's pending writes, the guest queues, the doorbell
// consumer's take), the real wait with its bound, the drop window and the plan's drop, the give-up journal (writers,
// arrivals, submissions, frames, the timeout line), the unwaited sample's selection, caps and lines (smp's walk), and the
// quiet filter on every line. No game, no GPU, no window, no sound device, no network: the direct path is never opened
// (g_dev stays empty), nothing is submitted anywhere; the "labels", rings and doorbell pages are the test's own memory.
// "on" sets the four switches (BC5_DIRECT_WAIT_LATE_PRODUCER_MS=300, the others 1 or on) before the first call, "off" sets
// them to 0 or off, "unset" unsets them; all three set BC5_DIRECT_FL_CRUMBS=1 and unset flx's and smp's switches. The unit
// reads each switch once. The pure cases run in every mode; the host cases check the mode (off and unset: e8's behaviour,
// nothing kept, nothing dropped, no wait, no line).
// Output: one line per case, then "gvw0401: on N of N; end" (or off, unset); without "; end" something failed. Exit 0 only
// after the end line. A watchdog ends a hang after 60 s with a FAIL line.
// Build: build0401.py ... --gate gvw0401.cpp <out> --like src/libs/bc5LleAgc.cpp (the unit's compile command; linked with
// every emulator object but main.cpp.o, the private bc5LleAgc.cpp.o among them), -std=c++20 -Wall -Wextra -Werror.
// usage: gvw0401 on | gvw0401 off | gvw0401 unset

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

typedef const uint32_t* (*FlxReadFn)(uint64_t a, uint64_t bytes, void* ctx);
extern "C" int         bc5_gvw0401_parse_ms(const char* e, int* bad);
extern "C" int         bc5_gvw0401_parse_on(const char* e, int* bad);
extern "C" void        bc5_gvw0401_switches(int* out);
extern "C" void        bc5_gvw0401_consts(uint64_t* out);
extern "C" int         bc5_gvw0401_meets(const uint32_t* w, int is64, uint64_t value);
extern "C" int         bc5_gvw0401_decide(int bound_ms, int can_wait, int cycle, int pending, int writer, int capped);
extern "C" int         bc5_gvw0401_waits(int code);
extern "C" const char* bc5_gvw0401_suffix(int code);
extern "C" int         bc5_gvw0401_scan(const uint32_t* const* rings, const uint32_t* ns, const uint32_t* rs, const uint32_t* ws, uint32_t nq, const uint32_t* w, int is64, FlxReadFn read,
                                        void* ctx, const uint64_t* met, uint32_t nmet, const uint64_t* ours, uint32_t nours, uint64_t* out);
extern "C" void        bc5_gvw0401_plw(uint64_t label, uint64_t value, int is64, int ring, int clear);
extern "C" void        bc5_gvw0401_queue(uint64_t ring_base, uint64_t ring_end, uint64_t doorbell_page, uint32_t d, int clear);
extern "C" void        bc5_gvw0401_taken(uint32_t queue, uint32_t rptr);
extern "C" int bc5_gvw0401_late_code(const uint32_t* w, int is64, const uint32_t* rest, uint32_t rest_n, int can_wait, int cycle, int bound_ms, FlxReadFn read, void* ctx, uint64_t* out);
extern "C" int bc5_gvw0401_late(const uint32_t* w, int is64, const uint32_t* rest, uint32_t rest_n, int cycle, int* code, double* ms);
extern "C" uint32_t bc5_gvw0401_window(const uint64_t* labels, const uint64_t* t_open, const int* checkable, uint32_t n, uint64_t now, const uint64_t* met, uint32_t nmet, int* why);
extern "C" uint32_t bc5_gvw0401_fl_take(const uint32_t* cls, const uint32_t* at, const int* drop, const int* crumbs, const int* serial, uint32_t count, uint32_t* out);
extern "C" uint32_t bc5_gvw0401_fl_drop(const char* kind, const uint32_t* cls, const uint32_t* at, uint32_t count, uint32_t* left);
extern "C" int      bc5_gvw0401_submitted(uint64_t n, const char* kind, int crumbs);
extern "C" uint64_t bc5_gvw0401_given_up(const uint32_t* w, uint32_t len, int is64, const char* kind, int cls);
extern "C" uint32_t bc5_gvw0401_open();
extern "C" void     bc5_gvw0401_split_start(const uint32_t* ib, uint32_t n, const char* kind);
extern "C" void     bc5_gvw0401_flip();
extern "C" uint64_t bc5_gvw0401_now();
extern "C" void     bc5_gvw0401_at_timeout(uint64_t n, const char* kind, uint64_t submit_ns);
extern "C" void     bc5_gvw0401_reset();
extern "C" uint32_t bc5_gvw0401_last(char* out, uint32_t cap);
extern "C" int      bc5_gvw0401_flips_between(const uint64_t* f, uint32_t n, uint64_t g, uint64_t s);
extern "C" int      bc5_gvw0401_in_frame(const uint64_t* f, uint32_t n, uint64_t g, uint64_t s);
extern "C" int bc5_gvw0401_timeout_line(uint64_t n, uint64_t s, const uint64_t* labels, const uint64_t* ts, const int* cls, uint32_t count, const uint64_t* flips, uint32_t nflips, char* out,
                                        uint32_t cap);
extern "C" int      bc5_gvw0401_rate(int64_t now_ms, int64_t* sec, uint32_t* used);
extern "C" int      bc5_gvw0401_sample(uint64_t n, int walkable, int64_t now_ms, const uint32_t* ns, const uint32_t* v0, const uint32_t* v1, uint32_t count, const uint32_t* es, uint32_t ndraws,
                                       uint64_t args, FlxReadFn read, void* ctx, char* out, uint32_t cap);
extern "C" uint64_t bc5_gvw0401_refused();
extern "C" uint32_t bc5_gvw0401_texts(char* out, uint32_t cap);
extern "C" int      bc5_smp0401_text(const uint32_t* ns, const uint32_t* v0, const uint32_t* v1, uint32_t count, uint32_t es, uint32_t op, uint32_t at, uint64_t args, uint32_t vcount,
                                     FlxReadFn read, void* ctx, char* out, uint32_t cap);
extern "C" void     bc5_flx0401_consts(uint32_t* out);
extern "C" int      bc5_cap0401_quiet_kind(const char* s, uint64_t n, int complete);

namespace gvw0401 {

static int                      g_pass = 0, g_total = 0, g_case_pass = 0, g_case_total = 0;
static std::atomic<const char*> g_case {"init"};
static std::vector<std::string> g_all; // every line the unit's host side wrote, and every line a seam formatted

static void Check(bool ok, const char* what, int line, const std::string& why = "") {
    g_total++;
    g_case_total++;
    if (ok) {
        g_pass++;
        g_case_pass++;
    } else {
        std::printf("gvw0401: FAIL %s (line %d): %s%s%s\n", g_case.load(), line, what, why.empty() ? "" : ": ", why.c_str());
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
    std::printf("gvw0401: case %s (%s): %d of %d\n", g_case.load(), how, g_case_pass, g_case_total);
    std::fflush(stdout);
}
static bool has(const std::string& s, const char* t) {
    return s.find(t) != std::string::npos;
}
static std::vector<std::string> split(const std::string& all) {
    std::vector<std::string> v;
    std::size_t              a = 0;
    while (a < all.size()) {
        const std::size_t b = all.find('\n', a);
        if (b == std::string::npos) break;
        v.push_back(all.substr(a, b - a));
        a = b + 1;
    }
    return v;
}
static std::vector<std::string> last() { // the unit's lines since its last reset (kept in g_all as well)
    static char buf[64 * 1024];
    buf[0] = 0;
    bc5_gvw0401_last(buf, sizeof(buf));
    return split(buf);
}
static std::string joined(const std::vector<std::string>& v) {
    std::string s;
    for (const std::string& l: v) s += l + "\n";
    return s;
}
static void reset() { // the lines go to g_all first
    for (const std::string& l: last()) g_all.push_back(l);
    bc5_gvw0401_reset();
}

// ---- the test's own packets and memory -----------------------------------------------------------------------------
constexpr uint64_t kL1 = 0x12004b4438ull, kL2 = 0x12004b3c38ull, kLM = 0x12004b4fc8ull, kLX = 0x12004b5038ull;
uint32_t lo(uint64_t a) {
    return static_cast<uint32_t>(a);
}
uint32_t hi(uint64_t a) {
    return static_cast<uint32_t>(a >> 32u) & 0xffffu;
}
uint32_t hdr(uint32_t op, uint32_t len) {
    return 0xC0000000u | ((len - 2u) << 16u) | (op << 8u);
}
using Pk = std::vector<uint32_t>;
Pk wait64(uint64_t label, uint64_t ref = 0, uint32_t fn = 3, uint64_t mask = ~0ull) { // WAIT_REG_MEM64, memory, function fn
    return {hdr(0x93, 9), 0x10u | fn, lo(label), hi(label), lo(ref), static_cast<uint32_t>(ref >> 32u), lo(mask), static_cast<uint32_t>(mask >> 32u), 10u};
}
Pk wait32(uint64_t label, uint32_t ref, uint32_t mask, uint32_t fn = 3) {
    return {hdr(0x3c, 7), 0x10u | fn, lo(label), hi(label), ref, mask, 10u};
}
Pk rel64(uint64_t label, uint64_t v) { // RELEASE_MEM, DATA_SEL 2
    return {hdr(0x49, 8), 0x0000'0500u, 2u << 29u, lo(label), hi(label), lo(v), static_cast<uint32_t>(v >> 32u), 0u};
}
Pk rel32(uint64_t label, uint32_t v) { // RELEASE_MEM, DATA_SEL 1
    return {hdr(0x49, 8), 0x0000'0500u, 1u << 29u, lo(label), hi(label), v, 0u, 0u};
}
Pk rel_ts(uint64_t label) { // RELEASE_MEM, DATA_SEL 3 (a timestamp): no label value
    return {hdr(0x49, 8), 0x0000'0500u, 3u << 29u, lo(label), hi(label), 0u, 0u, 0u};
}
Pk atomic(uint64_t label) { // ATOMIC_MEM
    return {hdr(0x1e, 9), 0u, lo(label), hi(label), 1u, 0u, 0u, 0u, 0u};
}
Pk nop(uint32_t len) {
    Pk p(len, 0u);
    p[0] = hdr(0x10, len);
    return p;
}
Pk ibp(uint64_t a, uint32_t n) { // INDIRECT_BUFFER, as the guest queue's ring holds it
    return {hdr(0x3f, 4), lo(a) & ~3u, static_cast<uint32_t>(a >> 32u) & 0xffu, n};
}
Pk cat(std::initializer_list<Pk> ps) {
    Pk o;
    for (const Pk& p: ps) o.insert(o.end(), p.begin(), p.end());
    return o;
}

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
const uint32_t* MemRead(uint64_t a, uint64_t bytes, void* ctx) {
    return static_cast<const Mem*>(ctx)->get(a, bytes);
}
constexpr uint64_t kIbA = 0x31000000ull, kIbB = 0x31010000ull, kIbC = 0x31020000ull, kIbD = 0x31030000ull, kIbE = 0x31040000ull, kIbF = 0x31050000ull, kIbG = 0x31060000ull,
                   kIbH = 0x31070000ull, kIbI = 0x31080000ull, kIbJ = 0x31090000ull, kNone = 0x3f000000ull;

// ---- 1. the switches as the unit reads them (mode) -------------------------------------------------------------------
static void Switches(int mode) {
    Begin("the switches");
    int s[4] = {9, 9, 9, 9};
    bc5_gvw0401_switches(s);
    if (mode == 0) CHECKW(s[0] == 300 && s[1] == 1 && s[2] == 1 && s[3] == 1, std::to_string(s[0]));
    else CHECK(s[0] == 0 && s[1] == 0 && s[2] == 0 && s[3] == 0);
    int t[4] = {};
    bc5_gvw0401_switches(t);
    CHECK(std::memcmp(s, t, sizeof(s)) == 0); // read once
    uint64_t c[7] = {};
    bc5_gvw0401_consts(c);
    CHECK(c[0] == 2000 && c[1] == 1'000'000'000ull && c[2] == 2'000'000'000ull && c[3] == 16 && c[4] == 1024 && c[5] == (1u << 21u) && c[6] == 64);
    End(mode == 0 ? "on" : mode == 1 ? "off" : "unset");
}

// ---- 2. the parse --------------------------------------------------------------------------------------------------
static void Parse() {
    Begin("the parse");
    int bad = 9;
    for (const char* e: {static_cast<const char*>(nullptr), "", "0", "off"}) {
        CHECKW(bc5_gvw0401_parse_ms(e, &bad) == 0 && bad == 0, e == nullptr ? "null" : e);
        CHECKW(bc5_gvw0401_parse_on(e, &bad) == 0 && bad == 0, e == nullptr ? "null" : e);
    }
    CHECK(bc5_gvw0401_parse_ms("1", &bad) == 1 && bad == 0);
    CHECK(bc5_gvw0401_parse_ms("500", &bad) == 500 && bad == 0);
    CHECK(bc5_gvw0401_parse_ms("2000", &bad) == 2000 && bad == 0);
    for (const char* e: {"2001", "-5", "5ms", "abc", "on", "1.5", "99999999999999999999"}) CHECKW(bc5_gvw0401_parse_ms(e, &bad) == 0 && bad == 1, e);
    CHECK(bc5_gvw0401_parse_on("1", &bad) == 1 && bad == 0);
    CHECK(bc5_gvw0401_parse_on("on", &bad) == 1 && bad == 0);
    for (const char* e: {"2", "yes", "true", "01", " 1", "ON", "1 "}) CHECKW(bc5_gvw0401_parse_on(e, &bad) == 0 && bad == 1, e);
    End("pure");
}

// ---- 3. the wait's comparison --------------------------------------------------------------------------------------
static void Meets() {
    Begin("the wait's comparison");
    const Pk e = wait64(kL1);
    CHECK(bc5_gvw0401_meets(e.data(), 1, 0) == 1 && bc5_gvw0401_meets(e.data(), 1, 1) == 0 && bc5_gvw0401_meets(e.data(), 1, 1ull << 32u) == 0);
    const Pk e32 = wait32(kL1, 0, 0xffffffffu);
    CHECK(bc5_gvw0401_meets(e32.data(), 0, 1ull << 32u) == 1 && bc5_gvw0401_meets(e32.data(), 0, 1) == 0); // 32 bits only
    const Pk ne = wait64(kL1, 5, 4), lt = wait64(kL1, 5, 1), ge = wait64(kL1, 5, 5), al = wait64(kL1, 5, 0), f7 = wait64(kL1, 5, 7);
    CHECK(bc5_gvw0401_meets(ne.data(), 1, 5) == 0 && bc5_gvw0401_meets(ne.data(), 1, 6) == 1);
    CHECK(bc5_gvw0401_meets(lt.data(), 1, 4) == 1 && bc5_gvw0401_meets(lt.data(), 1, 5) == 0);
    CHECK(bc5_gvw0401_meets(ge.data(), 1, 5) == 1 && bc5_gvw0401_meets(ge.data(), 1, 4) == 0);
    CHECK(bc5_gvw0401_meets(al.data(), 1, 77) == 1 && bc5_gvw0401_meets(f7.data(), 1, 77) == 1);
    const Pk m = wait64(kL1, 0, 3, 0xffu);
    CHECK(bc5_gvw0401_meets(m.data(), 1, 0x100) == 1 && bc5_gvw0401_meets(m.data(), 1, 0x101) == 0);
    End("pure");
}

// ---- 4. the decision -----------------------------------------------------------------------------------------------
static void Decide() {
    Begin("the late-producer decision");
    CHECK(bc5_gvw0401_decide(0, 1, 0, 1, 1, 0) == 0);  // off
    CHECK(bc5_gvw0401_decide(40, 0, 0, 1, 1, 0) == 1); // not this switch's class
    CHECK(bc5_gvw0401_decide(40, 1, 1, 1, 1, 0) == 2); // a cycle (run 123's test) wins
    CHECK(bc5_gvw0401_decide(40, 1, 0, 1, 0, 0) == 5); // a job on a ring writes it: another queue
    CHECK(bc5_gvw0401_decide(40, 1, 0, 0, 1, 0) == 6); // a queue holds the writer: another thread
    CHECK(bc5_gvw0401_decide(40, 1, 0, 0, 1, 1) == 6);
    CHECK(bc5_gvw0401_decide(40, 1, 0, 0, 3, 0) == 2); // the writer behind a cycle
    CHECK(bc5_gvw0401_decide(40, 1, 0, 0, 2, 0) == 4); // behind a wait without a known writer
    CHECK(bc5_gvw0401_decide(40, 1, 0, 0, 0, 1) == 4); // not everything seen
    CHECK(bc5_gvw0401_decide(40, 1, 0, 0, 0, 0) == 3); // not rung anywhere: the same thread, no wait
    for (int c = 0; c <= 6; c++) CHECKW(bc5_gvw0401_waits(c) == (c == 5 || c == 6 ? 1 : 0), std::to_string(c));
    CHECK(std::strcmp(bc5_gvw0401_suffix(5), " (late-producer bound)") == 0 && std::strcmp(bc5_gvw0401_suffix(6), " (late-producer bound)") == 0);
    for (int c: {-1, 0, 1, 2, 3, 4}) CHECKW(bc5_gvw0401_suffix(c)[0] == 0, std::to_string(c)); // e8's cpu-wait line unchanged
    End("pure");
}

// ---- 5. the compute-queue scan on queues of the test's own -------------------------------------------------------------
struct Q {
    Pk       ring;
    uint32_t r = 0, w = 0;
};
static int Scan(std::vector<Q>& qs, const Pk& w, Mem& m, std::vector<uint64_t> met, std::vector<uint64_t> ours, uint64_t* out) {
    std::vector<const uint32_t*> rings;
    std::vector<uint32_t>        ns, rs, ws;
    for (Q& q: qs) {
        rings.push_back(q.ring.data());
        ns.push_back(static_cast<uint32_t>(q.ring.size()));
        rs.push_back(q.r);
        ws.push_back(q.w);
    }
    return bc5_gvw0401_scan(rings.data(), ns.data(), rs.data(), ws.data(), static_cast<uint32_t>(qs.size()), w.data(), w[0] == hdr(0x93, 9) ? 1 : 0, MemRead, &m, met.data(),
                            static_cast<uint32_t>(met.size()), ours.data(), static_cast<uint32_t>(ours.size()), out);
}
static Q ring_of(std::initializer_list<Pk> entries, uint32_t size = 64) {
    Q q;
    q.ring = cat(entries);
    q.w    = static_cast<uint32_t>(q.ring.size());
    q.ring.resize(std::max<std::size_t>(size, q.ring.size()), 0u);
    return q;
}
static void ScanCase() {
    Begin("the compute-queue scan");
    Mem m;
    m.put(kIbA, cat({nop(4), rel64(kLX, 0)}));                         // writes another label
    m.put(kIbB, cat({nop(2), rel64(kL1, 0), nop(3)}));                 // writes the label, 0: meets == 0
    m.put(kIbC, cat({wait64(kLM), rel64(kL1, 0)}));                    // the label after a wait on M
    m.put(kIbD, cat({wait64(kLM), nop(2)}));                           // a wait on M, nothing else
    m.put(kIbE, cat({rel64(kL1, 1)}));                                 // writes the label, 1: does not meet
    m.put(kIbF, cat({atomic(kL1)}));                                   // ATOMIC_MEM on it: a value not known
    m.put(kIbG, cat({rel64(kLM, 0), wait64(kLM), rel64(kL1, 0)}));     // M written before its wait: not unready
    m.put(kIbH, cat({{hdr(0x93, 5), 0x13u, lo(kLM), hi(kLM), 0u}, rel64(kL1, 0)})); // a short WAIT_REG_MEM64
    m.put(kIbI, cat({rel_ts(kL1), nop(2)}));                           // a timestamp to it: no label value
    m.put(kIbJ, cat({rel32(kL1, 0x10000u)}));                          // 32-bit 0x10000
    const Pk w = wait64(kL1);
    uint64_t o[6];
    std::vector<Q> qs = {ring_of({ibp(kIbA, 12), ibp(kIbB, 13)})};
    CHECKW(Scan(qs, w, m, {}, {}, o) == 1 && o[0] == 0 && o[1] == 0 && o[3] == 2 && o[4] == 2 && o[5] == 25, std::to_string(o[3]) + " " + std::to_string(o[5]));
    qs = {ring_of({ibp(kIbC, 17)})};
    CHECK(Scan(qs, w, m, {}, {kLM}, o) == 3 && o[2] == kLM); // the writer waits on M, which the waiting buffer writes: a cycle
    CHECK(Scan(qs, w, m, {}, {}, o) == 2 && o[2] == kLM);    // M without a known writer
    CHECK(Scan(qs, w, m, {kLM}, {}, o) == 1);                // M met: it goes on
    qs = {ring_of({ibp(kIbD, 11), ibp(kIbB, 13)})};
    CHECK(Scan(qs, w, m, {}, {kLM}, o) == 3 && o[2] == kLM); // an entry ahead of the writer holds the queue
    CHECK(Scan(qs, w, m, {}, {}, o) == 2);
    CHECK(Scan(qs, w, m, {kLM}, {}, o) == 1);
    qs = {ring_of({ibp(kIbE, 8)})};
    CHECK(Scan(qs, w, m, {}, {}, o) == 0 && o[0] == 0); // a write that does not meet the wait is no writer
    qs = {ring_of({ibp(kIbF, 9)})};
    CHECK(Scan(qs, w, m, {}, {}, o) == 1);
    qs = {ring_of({ibp(kIbG, 25)})};
    CHECK(Scan(qs, w, m, {}, {kLM}, o) == 1);
    qs = {ring_of({ibp(kIbH, 13)})};
    CHECK(Scan(qs, w, m, {kLM}, {}, o) == 2); // a short WAIT_REG_MEM64 is not read: unknown, even with M met
    qs = {ring_of({ibp(kIbI, 10)})};
    CHECK(Scan(qs, w, m, {}, {}, o) == 0);
    const Pk w32 = wait32(kL1, 0, 0xffffu), w32b = wait32(kL1, 0, 0xffffffffu);
    qs           = {ring_of({ibp(kIbJ, 8)})};
    CHECK(Scan(qs, w32, m, {}, {}, o) == 1 && Scan(qs, w32b, m, {}, {}, o) == 0); // the mask decides
    // Taken: the consumer's read pointer past the writer.
    qs      = {ring_of({ibp(kIbB, 13), ibp(kIbA, 12)})};
    qs[0].r = 4;
    CHECK(Scan(qs, w, m, {}, {}, o) == 0 && o[3] == 1);
    qs[0].r = 0;
    qs[0].w = 4;
    CHECK(Scan(qs, w, m, {}, {}, o) == 1 && o[3] == 1);
    qs[0].w = 0;
    CHECK(Scan(qs, w, m, {}, {}, o) == 0 && o[3] == 0); // nothing rung
    // Across the ring's end: entries at 8..11 and 0..3 of 12 dwords; one packet crossing the end is not followed.
    Q wrap;
    wrap.ring = cat({ibp(kIbB, 13), nop(4), ibp(kIbA, 12)});
    wrap.r    = 8;
    wrap.w    = 4;
    qs        = {wrap};
    CHECK(Scan(qs, w, m, {}, {}, o) == 1 && o[3] == 2);
    Q cross;
    cross.ring = cat({nop(8), ibp(kIbB, 13)});
    cross.ring.resize(10);
    cross.r = 8;
    cross.w = 2;
    qs      = {cross};
    CHECK(Scan(qs, w, m, {}, {}, o) == 0 && o[0] == 1);
    // Not readable: ahead of the writer, it may hold the queue.
    qs = {ring_of({ibp(kNone, 40), ibp(kIbB, 13)})};
    CHECK(Scan(qs, w, m, {}, {}, o) == 2 && o[0] == 1 && o[2] == 0);
    qs = {ring_of({ibp(kNone, 40)})};
    CHECK(Scan(qs, w, m, {}, {}, o) == 0 && o[0] == 1);
    // Two queues: the best answer.
    qs = {ring_of({ibp(kIbC, 17)}), ring_of({ibp(kIbB, 13)})};
    CHECK(Scan(qs, w, m, {}, {kLM}, o) == 1 && o[1] == 1);
    qs = {ring_of({ibp(kIbC, 17)}), ring_of({ibp(kIbD, 11), ibp(kIbB, 13)})};
    CHECK(Scan(qs, w, m, {}, {}, o) == 2);
    // A packet the soft CP runs on the ring itself.
    qs = {ring_of({nop(3), rel64(kL1, 0)})};
    CHECK(Scan(qs, w, m, {}, {}, o) == 1 && o[4] == 0);
    // The entries' cap.
    Q many;
    for (int k = 0; k < 1100; k++) many.ring.insert(many.ring.end(), {hdr(0x10, 2), 0u});
    const Pk tail = ibp(kIbB, 13);
    many.ring.insert(many.ring.end(), tail.begin(), tail.end());
    many.w = static_cast<uint32_t>(many.ring.size());
    many.ring.push_back(0);
    qs = {many};
    CHECK(Scan(qs, w, m, {}, {}, o) == 0 && o[0] == 1 && o[3] == 1024);
    End("pure");
}

// ---- 6. the host's decision: the unit's real registries and queues, the test's memory (every mode: the bound is given) --
alignas(8) static volatile uint64_t g_lab_l = 1, g_lab_m = 1, g_lab_x = 1;
static uint64_t A(volatile uint64_t& v) {
    return reinterpret_cast<uint64_t>(&v);
}
struct Fake { // a guest queue: its ring, the published read pointer behind it, a doorbell page
    std::vector<uint32_t> ring;
    std::vector<uint64_t> page = std::vector<uint64_t>(4, 0);
    uint32_t              n    = 0;
};
static void put_queue(Fake& f, std::initializer_list<Pk> entries, uint32_t n = 64) {
    f.ring = cat(entries);
    const uint32_t w = static_cast<uint32_t>(f.ring.size());
    f.n              = n;
    f.ring.resize(n + 1, 0u); // [n]: the read pointer the consumer publishes (0)
    f.page[0] = w;            // doorbell slot d = 1
    const uint64_t base = reinterpret_cast<uint64_t>(f.ring.data());
    bc5_gvw0401_queue(base, base + 4ull * n, reinterpret_cast<uint64_t>(f.page.data()), 1, 0);
}
static int LateCode(const Pk& w, const Pk& rest, Mem& m, uint64_t* o, int can_wait = 1, int cycle = 0, int bound = 40) {
    return bc5_gvw0401_late_code(w.data(), 1, rest.empty() ? nullptr : rest.data(), static_cast<uint32_t>(rest.size()), can_wait, cycle, bound, MemRead, &m, o);
}
static void HostDecision() {
    Begin("the host's decision");
    bc5_gvw0401_plw(0, 0, 0, 0, 1);
    bc5_gvw0401_queue(0, 0, 0, 0, 1);
    g_lab_l = 1;
    g_lab_m = 1;
    Mem      m;
    uint64_t o[5];
    const Pk w = wait64(A(g_lab_l));
    CHECK(LateCode(w, {}, m, o) == 3 && o[0] == 0 && o[1] == 0); // nothing pending, no queue: the same thread
    bc5_gvw0401_plw(A(g_lab_l), 0, 1, 1, 0);
    CHECK(LateCode(w, {}, m, o) == 5 && o[0] == 1); // a job on ring 1 writes 0
    bc5_gvw0401_plw(A(g_lab_l), 1, 1, 1, 0);
    CHECK(LateCode(w, {}, m, o) == 3 && o[0] == 0); // its last pending write is 1: does not meet
    bc5_gvw0401_plw(0, 0, 0, 0, 1);
    m.put(kIbB, cat({nop(2), rel64(A(g_lab_l), 0)}));
    m.put(kIbC, cat({wait64(A(g_lab_m)), rel64(A(g_lab_l), 0)}));
    Fake f;
    put_queue(f, {ibp(kIbA, 4), ibp(kIbB, 10)}); // kIbA is not in m: not readable
    CHECK(LateCode(w, {}, m, o) == 4 && o[2] == 1);
    bc5_gvw0401_queue(0, 0, 0, 0, 1);
    put_queue(f, {ibp(kIbB, 10)});
    CHECK(LateCode(w, {}, m, o) == 6 && o[1] == 1 && o[3] == 1 && o[4] == 1); // rung, not taken: bc5-ring submits it
    bc5_gvw0401_taken(0, 4);
    CHECK(LateCode(w, {}, m, o) == 3 && o[3] == 0); // taken by the consumer (its jobs' writes would be pending): nothing rung
    bc5_gvw0401_taken(0, 0);
    CHECK(LateCode(w, {}, m, o) == 6);
    bc5_gvw0401_queue(0, 0, 0, 0, 1);
    put_queue(f, {ibp(kIbC, 17)});
    const Pk rest = cat({nop(3), rel64(A(g_lab_m), 0)}); // the waiting buffer's rest writes M
    CHECK(LateCode(w, rest, m, o) == 2 && o[1] == 3);  // the writer waits on M, which only the waiting buffer writes: a cycle
    CHECK(LateCode(w, {}, m, o) == 4 && o[1] == 2);    // M without a known writer: not known
    bc5_gvw0401_plw(A(g_lab_m), 0, 1, 1, 0);
    CHECK(LateCode(w, rest, m, o) == 6); // M's write pending on a ring: the writer goes on
    bc5_gvw0401_plw(0, 0, 0, 0, 1);
    g_lab_m = 0;
    CHECK(LateCode(w, rest, m, o) == 6); // M met
    g_lab_m = 1;
    CHECK(LateCode(w, {}, m, o, 0) == 1 && LateCode(w, {}, m, o, 1, 1) == 2 && LateCode(w, {}, m, o, 1, 0, 0) == 0);
    Mem empty;
    CHECK(LateCode(w, {}, empty, o) == 4 && o[2] == 1);
    bc5_gvw0401_queue(0, 0, 0, 0, 1);
    End("pure host");
}

// ---- 7. the real wait (mode) ----------------------------------------------------------------------------------------
static void LateWait(int mode) {
    Begin("the late-producer wait");
    reset();
    bc5_gvw0401_plw(0, 0, 0, 0, 1);
    bc5_gvw0401_queue(0, 0, 0, 0, 1);
    const Pk w = wait64(A(g_lab_l));
    g_lab_l    = 1;
    bc5_gvw0401_plw(A(g_lab_l), 0, 1, 1, 0);
    int         code = -9;
    double      ms   = -1;
    std::thread t([] {
        const auto t1 = std::chrono::steady_clock::now(); // a spin, not a sleep: a sleep's length is the OS timer's (70-90 ms for 10 on the laptop)
        while (std::chrono::steady_clock::now() - t1 < std::chrono::milliseconds(10)) {
        }
        g_lab_l = 0;
    });
    const int r = bc5_gvw0401_late(w.data(), 1, nullptr, 0, 0, &code, &ms);
    t.join();
    if (mode == 0) {
        CHECKW(r == 1 && code == 5 && ms >= 9 && ms < 300, std::to_string(ms)); // met within the bound (300 ms)
        const std::string l = joined(last());
        CHECKW(has(l, "gvw (exp 0401 e9): late producer of 0x") && has(l, "waited: a job on a ring writes the label") && has(l, "then met: served late after"), l);
        CHECKW(has(l, "cpu-wait WAIT_REG_MEM64 at 0 on 0x") && has(l, ": served late after ") && has(l, " ms (exp 0401 e9 gvw: waited: a job on a ring writes the label"), l);
    } else {
        CHECKW(r == 0 && code == 0 && ms < 5, std::to_string(ms));
        CHECK(last().empty());
    }
    reset();
    g_lab_l = 1; // pending still, never written: the bound
    code    = -9;
    const int r2 = bc5_gvw0401_late(w.data(), 1, nullptr, 0, 0, &code, &ms);
    if (mode == 0) {
        CHECKW(r2 == 0 && code == 5 && ms >= 300 && ms < 600, std::to_string(ms)); // the bound, plus at most one poll's sleep
        CHECK(std::strcmp(bc5_gvw0401_suffix(code), " (late-producer bound)") == 0);
        CHECK(has(joined(last()), "then still not met: given up at the bound after"));
    } else {
        CHECKW(r2 == 0 && code == 0 && ms < 5, std::to_string(ms));
    }
    reset();
    bc5_gvw0401_plw(0, 0, 0, 0, 1); // nothing pending, no queue: no wait
    const int r3 = bc5_gvw0401_late(w.data(), 1, nullptr, 0, 0, &code, &ms);
    CHECKW(r3 == 0 && code == (mode == 0 ? 3 : 0) && ms < 5, std::to_string(ms));
    if (mode == 0) CHECK(has(joined(last()), "not waited: the same thread") && has(joined(last()), "then given up as without the switch"));
    const int r4 = bc5_gvw0401_late(w.data(), 1, nullptr, 0, 1, &code, &ms);
    CHECKW(r4 == 0 && code == (mode == 0 ? 2 : 0) && ms < 5, std::to_string(ms));
    if (mode != 0) CHECK(last().empty());
    reset();
    End(mode == 0 ? "on" : mode == 1 ? "off" : "unset");
}

// ---- 8. the drop window (pure) ----------------------------------------------------------------------------------------
static void Window() {
    Begin("the drop window");
    constexpr uint64_t ms = 1'000'000ull;
    int                why[3];
    {
        const uint64_t l[3] = {kL1, kL2, kLX}, t[3] = {0, 0, 500 * ms}, met[2] = {kL1, kL2};
        const int      c[3] = {1, 0, 1};
        CHECK(bc5_gvw0401_window(l, t, c, 3, 600 * ms, met, 2, why) == 2 && why[0] == 1 && why[1] == 0 && why[2] == 0); // L2's packet not whole: not met
        CHECK(bc5_gvw0401_window(l, t, c, 3, 1000 * ms, met, 0, why) == 1 && why[0] == 2 && why[1] == 2 && why[2] == 0);
        CHECK(bc5_gvw0401_window(l, t, c, 3, 1000 * ms - 1, met, 0, why) == 3 && why[0] == 0 && why[1] == 0 && why[2] == 0);
        CHECK(bc5_gvw0401_window(l, t, c, 3, 1500 * ms, met, 0, why) == 0 && why[2] == 2);
    }
    {
        const uint64_t l[2] = {kL1, kL1}, t[2] = {0, 900 * ms};
        const int      c[2] = {1, 1};
        CHECK(bc5_gvw0401_window(l, t, c, 2, 1200 * ms, nullptr, 0, why) == 1 && why[0] == -1 && why[1] == 0); // a new give-up starts it again
    }
    End("pure");
}

// ---- 9. the plan's drop (pure) -----------------------------------------------------------------------------------------
static void FlTake() {
    Begin("the plan's drop");
    uint32_t o[16] = {};
    {
        const uint32_t cls[5] = {3, 2, 3, 0, 3}, at[5] = {10, 20, 30, 40, 50};
        const int      drop[5] = {0, 0, 1, 0, 0}, crumbs[5] = {1, 1, 0, 1, 1}, serial[5] = {0, 0, 0, 0, 1};
        CHECK(bc5_gvw0401_fl_take(cls, at, drop, crumbs, serial, 5, o) == 2);
        CHECKW(o[0] == 3 && o[1] == 2 && o[2] == 1 && o[3] == 2 && o[4] == 0 && o[5] == 3 && o[6] == 10 && o[7] == 50,
               std::to_string(o[0]) + " " + std::to_string(o[1]) + " " + std::to_string(o[2]) + " " + std::to_string(o[3]) + " " + std::to_string(o[4]));
    }
    {
        const uint32_t cls[2] = {2, 0}, at[2] = {10, 20};
        const int      z[2] = {0, 0}, serial[2] = {1, 0};
        CHECK(bc5_gvw0401_fl_take(cls, at, z, z, serial, 2, o) == 0 && o[0] == 2 && o[5] == 1 && o[4] == 1);
    }
    {
        const uint32_t cls[2] = {3, 2}, at[2] = {10, 20};
        const int      z[2] = {0, 0}, serial[2] = {0, 1};
        CHECK(bc5_gvw0401_fl_take(cls, at, z, z, serial, 2, o) == 1 && o[0] == 1 && o[4] == 1); // a kept draw's F2 stays
    }
    End("pure");
}

// ---- 10. the drop on the host's windows (mode) ----------------------------------------------------------------------
static void HostDrop(int mode) {
    Begin("the unwaited fl drop");
    reset();
    g_lab_l                = 1;
    const Pk       w       = wait64(A(g_lab_l));
    const uint32_t cls[3]  = {3, 3, 2}, at[3] = {5, 6, 7};
    uint32_t       left    = 9;
    const uint64_t records = bc5_gvw0401_given_up(w.data(), 9, 1, "dcb", 0);
    CHECK(records == (mode == 0 ? 1u : 0u) && bc5_gvw0401_open() == (mode == 0 ? 1u : 0u));
    CHECK(bc5_gvw0401_fl_drop("acb", cls, at, 3, &left) == 0 && left == 3);
    CHECK(bc5_gvw0401_fl_drop("dcb", cls, at, 3, &left) == (mode == 0 ? 2u : 0u) && left == (mode == 0 ? 1u : 3u));
    CHECK(bc5_gvw0401_submitted(501, "dcb", 0) == 0);
    std::string l = joined(last());
    if (mode == 0) {
        CHECKW(has(l, "gvw (exp 0401 e9): unwaited fl drop: submit #501 dcb: 2 certainly fast-launch draws dropped of 3 (1 maybe or unknown kept); open give-ups: 0x") &&
                   has(l, " (give-up #1, "),
               l);
        CHECKW(has(l, "gvw (exp 0401 e9): give-up #1 on 0x") && has(l, ": its buffer went to the GPU in submit #501 dcb, "), l);
    } else {
        CHECK(l.empty());
    }
    g_lab_l = 0; // the label met: the window closes at the next dcb
    CHECK(bc5_gvw0401_fl_drop("dcb", cls, at, 3, &left) == 0 && left == 3 && bc5_gvw0401_open() == 0);
    bc5_gvw0401_submitted(502, "dcb", 0);
    l = joined(last());
    if (mode == 0) CHECKW(has(l, "gvw (exp 0401 e9): unwaited fl drop window of give-up #1 on 0x") && has(l, " closed: the label met after ") && has(l, "; 2 draws dropped in 1 dcbs under it"), l);
    reset();
    bc5_gvw0401_given_up(w.data(), 4, 1, "dcb", 0); // the packet not whole: only the bound closes it
    CHECK(bc5_gvw0401_fl_drop("dcb", cls, at, 3, &left) == (mode == 0 ? 2u : 0u));
    reset();
    bc5_gvw0401_given_up(w.data(), 9, 1, "acb", 2); // a timeout (the 2-s class): no window
    CHECK(bc5_gvw0401_open() == 0 && bc5_gvw0401_fl_drop("dcb", cls, at, 3, &left) == 0 && left == 3);
    reset();
    End(mode == 0 ? "on" : mode == 1 ? "off" : "unset");
}

// ---- 11. the give-up journal: writers, arrivals, submissions (mode) ---------------------------------------------------
static void Journal(int mode) {
    Begin("the give-up journal");
    reset();
    bc5_gvw0401_plw(0, 0, 0, 0, 1);
    g_lab_l = 1;
    g_lab_m = 1;
    g_lab_x = 1;
    const Pk wl = wait64(A(g_lab_l)), wm = wait64(A(g_lab_m)), wx = wait64(A(g_lab_x));
    const Pk writer = cat({rel64(A(g_lab_l), 0)}), other = cat({nop(4)});
    bc5_gvw0401_split_start(writer.data(), static_cast<uint32_t>(writer.size()), "acb"); // L's last writer
    bc5_gvw0401_given_up(wl.data(), 9, 1, "dcb", 0);
    std::string l = joined(last());
    if (mode == 0)
        CHECKW(has(l, "gvw (exp 0401 e9): give-up #") && has(l, ": the wait on 0x") && has(l, " (GIVEN UP) of dcb 100 dwords at ") && has(l, ", at 3, after 8.5 ms, t ") &&
                   has(l, "late producer: not asked (its switch off, or not a wait of its class); the label's writer: no job on a ring writes it; last seen written by acb 8 dwords from the game's thread, "),
               l);
    bc5_gvw0401_split_start(other.data(), static_cast<uint32_t>(other.size()), "dcb");
    CHECK(!has(joined(last()), "arrived"));
    bc5_gvw0401_split_start(writer.data(), static_cast<uint32_t>(writer.size()), "acb");
    l = joined(last());
    if (mode == 0) CHECKW(has(l, ": its writer arrived: acb 8 dwords from the game's thread, ") && has(l, " ms after the give-up, 0 flips later"), l);
    bc5_gvw0401_given_up(wm.data(), 9, 1, "dcb", 1);
    g_lab_m = 0;
    bc5_gvw0401_split_start(other.data(), static_cast<uint32_t>(other.size()), "dcb");
    if (mode == 0) CHECK(has(joined(last()), " (CYCLE) of dcb") && has(joined(last()), ": the label met, no writer seen, "));
    g_lab_m = 1;
    bc5_gvw0401_given_up(wx.data(), 9, 1, "dcb", 0);
    bc5_gvw0401_plw(A(g_lab_x), 0, 1, 1, 0);
    bc5_gvw0401_split_start(other.data(), static_cast<uint32_t>(other.size()), "dcb");
    if (mode == 0) CHECK(has(joined(last()), ": a job on ring 1 writes it now (its buffer was not seen at submit_split's start), "));
    bc5_gvw0401_plw(0, 0, 0, 0, 1);
    // Submissions: no chain, this thread's give-ups of its current submit_split call.
    reset();
    bc5_gvw0401_given_up(wl.data(), 9, 1, "dcb", 0);
    bc5_gvw0401_submitted(600, "dcb", 0);
    bc5_gvw0401_submitted(601, "dcb", 0);
    l = joined(last());
    if (mode == 0) CHECKW(has(l, ": its buffer went to the GPU in submit #600 dcb, ") && !has(l, "submit #601"), l);
    bc5_gvw0401_given_up(wl.data(), 9, 1, "dcb", 0);
    bc5_gvw0401_split_start(other.data(), static_cast<uint32_t>(other.size()), "dcb"); // the next buffer: this call's give-ups start afresh
    bc5_gvw0401_submitted(602, "dcb", 0);
    CHECK(!has(joined(last()), "submit #602"));
    bc5_gvw0401_given_up(wl.data(), 9, 1, "acb", 2);
    bc5_gvw0401_submitted(603, "dcb", 0);
    bc5_gvw0401_submitted(604, "acb", 0);
    l = joined(last());
    if (mode == 0) CHECKW(has(l, " (TIMEOUT) of acb") && !has(l, "submit #603") && has(l, "in submit #604 acb"), l);
    if (mode != 0) CHECK(l.empty());
    reset();
    End(mode == 0 ? "on" : mode == 1 ? "off" : "unset");
}

// ---- 12. frames and the timeout line (pure, then the host's, mode) ------------------------------------------------------
static void Frames(int mode) {
    Begin("frames and the timeout line");
    const uint64_t f[3] = {100, 200, 300};
    CHECK(bc5_gvw0401_flips_between(f, 3, 50, 150) == 1 && bc5_gvw0401_flips_between(f, 3, 150, 250) == 1 && bc5_gvw0401_flips_between(f, 3, 150, 160) == 0);
    CHECK(bc5_gvw0401_flips_between(f, 3, 300, 300) == 0 && bc5_gvw0401_flips_between(f, 3, 250, 300) == 1 && bc5_gvw0401_flips_between(f, 3, 200, 100) == -1);
    CHECK(bc5_gvw0401_flips_between(f, 3, 0, 1000) == 3);
    CHECK(bc5_gvw0401_in_frame(f, 3, 150, 160) == 1 && bc5_gvw0401_in_frame(f, 3, 50, 150) == 0 && bc5_gvw0401_in_frame(f, 3, 200, 100) == 0);
    CHECK(bc5_gvw0401_in_frame(nullptr, 0, 0, 1'500'000'000ull) == 0 && bc5_gvw0401_in_frame(nullptr, 0, 600'000'000ull, 1'500'000'000ull) == 1);
    constexpr uint64_t ms = 1'000'000ull;
    const uint64_t     labels[4] = {kL1, kL2, kLX, kLM}, ts[4] = {100 * ms, 400 * ms, 900 * ms, 2000 * ms};
    const int          cls[4] = {0, 2, 0, 0};
    char               t[2048];
    const uint64_t     fl1[1] = {500 * ms}, fl2[1] = {950 * ms};
    CHECK(bc5_gvw0401_timeout_line(7, 1000 * ms, labels, ts, cls, 4, fl1, 1, t, sizeof(t)) == 1);
    CHECKW(std::string(t) == "gvw (exp 0401 e9): at the timeout of submit #7 dcb: it followed a given-up wait in its frame: yes; give-ups within 1 s before its submission: 3: 0x12004b5038 (give-up #3, "
                             "GIVEN UP, 100.0 ms before, 0 flips between), 0x12004b3c38 (give-up #2, TIMEOUT, 600.0 ms before, 1 flips between), 0x12004b4438 (give-up #1, GIVEN UP, 900.0 ms before, 1 "
                             "flips between)",
           t);
    CHECK(bc5_gvw0401_timeout_line(7, 1000 * ms, labels, ts, cls, 4, fl2, 1, t, sizeof(t)) == 0 && has(t, "in its frame: no; give-ups within 1 s before its submission: 3: "));
    CHECK(bc5_gvw0401_timeout_line(7, 450 * ms, labels, ts, cls, 4, fl1, 1, t, sizeof(t)) == 1 && has(t, "submission: 2: 0x12004b3c38"));
    CHECK(bc5_gvw0401_timeout_line(7, 5000 * ms, labels, ts, cls, 4, fl1, 1, t, sizeof(t)) == 0 && has(t, "submission: 0") && !has(t, "0x"));
    // The host's: a flip, a give-up, the timeout of a job submitted after it in the same frame; then after a flip.
    reset();
    g_lab_l     = 1;
    const Pk wl = wait64(A(g_lab_l));
    bc5_gvw0401_flip();
    bc5_gvw0401_given_up(wl.data(), 9, 1, "dcb", 0);
    bc5_gvw0401_at_timeout(700, "dcb", bc5_gvw0401_now());
    std::string l = joined(last());
    if (mode == 0) CHECKW(has(l, "gvw (exp 0401 e9): at the timeout of submit #700 dcb: it followed a given-up wait in its frame: yes; give-ups within 1 s before its submission: 1: 0x"), l);
    else CHECK(l.empty());
    bc5_gvw0401_flip();
    bc5_gvw0401_at_timeout(701, "dcb", bc5_gvw0401_now());
    l = joined(last());
    if (mode == 0) CHECKW(has(l, "at the timeout of submit #701 dcb: it followed a given-up wait in its frame: no; give-ups within 1 s before its submission: 1: 0x") && has(l, "1 flips between)"), l);
    reset();
    End(mode == 0 ? "on" : mode == 1 ? "off" : "unset");
}

// ---- 13. the unwaited sample: selection, caps and smp's walk (mode) -----------------------------------------------------
// smp0401.cpp's synthetic object table, records and headers (flx0401.cpp's section 10).
constexpr uint32_t kEsA = 0x11d01345u, kEsOther = 0x11d01000u;
constexpr uint64_t kObj = 0x30000000ull, kPath = 0x30001000ull, kTab = 0x30002000ull, kRecs = 0x30010000ull, kHdrs = 0x30020000ull, kIbuf = 0x30030000ull, kArgs = 0x30040000ull;
void put_vsharp(Mem& m, uint64_t base, uint64_t byte, uint64_t a, uint32_t stride, uint32_t records) {
    m.at(base, byte)      = lo(a);
    m.at(base, byte + 4)  = hi(a) | (stride << 16u);
    m.at(base, byte + 8)  = records;
    m.at(base, byte + 12) = 0x0002'0000u;
}
std::vector<uint32_t> vs(uint64_t a, uint32_t stride, uint32_t records) {
    return {lo(a), hi(a) | (stride << 16u), records, 0x0002'0000u};
}
Mem mesh_mem() {
    Mem m;
    m.put(kObj, std::vector<uint32_t>(400, 0u));
    m.at(kObj, 3 * 16 + 8) = 3;
    m.at(kObj, 5 * 16 + 8) = 5;
    m.at(kObj, 3 * 16 + 4) = 3;
    m.put(kPath, {0u, 0u});
    m.put(kTab, std::vector<uint32_t>(0x700 / 4, 0u));
    put_vsharp(m, kTab, 0x540, kIbuf, 4, 64);
    put_vsharp(m, kTab, 0x5a0, kHdrs, 4, 0x100);
    put_vsharp(m, kTab, 0x620, kRecs, 64, 16);
    m.put(kRecs, std::vector<uint32_t>(16 * 16, 0u));
    m.at(kRecs, 3 * 64 + 0x14) = 0x40;
    m.at(kRecs, 3 * 64 + 0x18) = 4;
    m.at(kRecs, 3 * 64 + 0x1c) = 0x40;
    m.put(kHdrs, std::vector<uint32_t>(0x100, 0u));
    m.at(kHdrs, 0x40 + 0) = (63u << 24u) | (31u << 17u);
    m.at(kHdrs, 0x40 + 4) = 32u << 17u;
    m.at(kHdrs, 0x40 + 8) = 64u << 24u;
    m.put(kIbuf, std::vector<uint32_t>(64, 0u));
    m.put(kArgs, {6u, 1u, 5000u, 1u});
    return m;
}
std::vector<uint32_t> ud_pattern1() {
    std::vector<uint32_t> ud(32, 0u);
    const auto            put = [&ud](uint32_t k, const std::vector<uint32_t>& v) { std::copy(v.begin(), v.end(), ud.begin() + k); };
    put(0, vs(kObj, 16, 100));
    put(12, vs(kPath, 0, 8));
    put(16, vs(kTab, 0, 0x700));
    ud[20] = 1;
    return ud;
}
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
    x.n[f[10]] = 1, x.v0[f[10]] = 1;
    x.n[f[11]] = 1, x.v0[f[11]] = v6;
    for (uint32_t k = 0; k < 32 && f[8] + k < f[3]; k++) x.n[f[8] + k] = 1, x.v0[f[8] + k] = ud[k];
    return x;
}
static char g_out[256 * 1024];
static int  SampleOf(uint64_t n, int walkable, int64_t now_ms, const X& x, const uint32_t* es, uint32_t ndraws, Mem& m) {
    return bc5_gvw0401_sample(n, walkable, now_ms, x.n.data(), x.v0.data(), x.v1.data(), static_cast<uint32_t>(x.n.size()), es, ndraws, kArgs, MemRead, &m, g_out, sizeof(g_out));
}
static void Sample(int mode) {
    Begin("the unwaited sample");
    int64_t  sec = -1;
    uint32_t used = 0;
    int      ok   = 0;
    for (int k = 0; k < 16; k++) ok += bc5_gvw0401_rate(5000 + k, &sec, &used);
    CHECK(ok == 16 && bc5_gvw0401_rate(5999, &sec, &used) == 0 && bc5_gvw0401_rate(6000, &sec, &used) == 1 && used == 1);
    reset();
    g_lab_l              = 1;
    const Pk       wl    = wait64(A(g_lab_l));
    Mem            m     = mesh_mem();
    const X        x     = draw_x(ud_pattern1(), 2);
    const uint32_t es3[3] = {kEsA, kEsOther, kEsA};
    CHECK(bc5_gvw0401_submitted(800, "dcb", 1) == 0); // no give-up: not marked
    bc5_gvw0401_given_up(wl.data(), 9, 1, "dcb", 0);
    CHECK(bc5_gvw0401_submitted(801, "dcb", 1) == (mode == 0 ? 1 : 0));
    CHECK(bc5_gvw0401_submitted(802, "dcb", 0) == 0 && bc5_gvw0401_submitted(803, "acb", 1) == 0); // no crumbs; not a dcb
    const int k = SampleOf(801, 1, 100'000, x, es3, 3, m);
    if (mode == 0) {
        const std::vector<std::string> v = split(g_out);
        CHECKW(k == 3 && v.size() == 3, std::to_string(k));
        char s[4096];
        CHECK(bc5_smp0401_text(x.n.data(), x.v0.data(), x.v1.data(), static_cast<uint32_t>(x.n.size()), kEsA, 0x24, 1702, kArgs, 0, MemRead, &m, s, sizeof(s)) == 3);
        const std::string sl = s;
        if (v.size() == 3) {
            CHECKW(v[0].rfind("fl meshlet sample (exp 0401 e9 gvw): unwaited, completed: submit #801 dcb op 24 at 100: ES 11d01345 (pattern 1): 6 x 1 points (from memory now)", 0) == 0, v[0]);
            const std::size_t a = sl.find(" (pattern 1)"), b = v[0].find(" (pattern 1)");
            CHECKW(a != std::string::npos && b != std::string::npos && sl.substr(a) == v[0].substr(b), sl + " | " + v[0]); // smp's fields, unchanged
            CHECK(v[1].rfind("fl meshlet sample (exp 0401 e9 gvw): unwaited, completed: submit #801 dcb op 24 at 102: ES 11d01345 (pattern 1)", 0) == 0);
            CHECKW(v[2].rfind("fl meshlet sample (exp 0401 e9 gvw): unwaited: submit #801 dcb completed: 2 pattern draws of 3 planned, 2 walked; after give-up #1 on 0x", 0) == 0 &&
                       has(v[2], " ms before its submission)"),
                   v[2]);
            CHECK(has(v[0], "; model 0 (past NUM_RECORDS read as 0): ") && has(v[0], "; model 1 (past NUM_RECORDS read as the memory there): ")); // both range models
        }
        for (const std::string& l: v) g_all.push_back(l);
    } else {
        CHECK(k == -1 && g_out[0] == 0);
    }
    CHECK(SampleOf(801, 1, 100'000, x, es3, 3, m) == -1); // the mark went with the walk
    bc5_gvw0401_flip();
    CHECK(bc5_gvw0401_submitted(804, "dcb", 1) == 0); // a flip since the give-up: another frame
    reset();
    bc5_gvw0401_given_up(wl.data(), 9, 1, "acb", 2);
    CHECK(bc5_gvw0401_submitted(805, "dcb", 1) == 0); // a timeout (the 2-s class) is not a dcb's give-up
    // The cap of 64 draws a job.
    reset();
    bc5_gvw0401_given_up(wl.data(), 9, 1, "dcb", 0);
    bc5_gvw0401_submitted(810, "dcb", 1);
    const std::vector<uint32_t> es70(70, kEsA);
    const int                   k70 = SampleOf(810, 1, 101'000, x, es70.data(), 70, m);
    if (mode == 0) {
        const std::vector<std::string> v = split(g_out);
        CHECKW(k70 == 65 && v.size() == 65 && has(v.back(), "70 pattern draws of 70 planned, 64 walked"), std::to_string(k70));
        for (const std::string& l: v) g_all.push_back(l);
    } else {
        CHECK(k70 == -1);
    }
    // The cap of 16 jobs a second: 18 marked jobs completing within one second.
    reset();
    bc5_gvw0401_given_up(wl.data(), 9, 1, "dcb", 0);
    const uint64_t refused0 = bc5_gvw0401_refused();
    int            taken    = 0;
    for (uint64_t n = 811; n < 829; n++) bc5_gvw0401_submitted(n, "dcb", 1);
    for (uint64_t n = 811; n < 829; n++) {
        const int r = SampleOf(n, 1, 102'500, x, es3, 1, m);
        taken += r >= 0 ? 1 : 0;
        if (r >= 0) {
            for (const std::string& l: split(g_out)) g_all.push_back(l);
        }
    }
    CHECKW(taken == (mode == 0 ? 16 : 0) && bc5_gvw0401_refused() - refused0 == (mode == 0 ? 2u : 0u), std::to_string(taken));
    CHECK(SampleOf(829, 1, 103'000, x, es3, 1, m) == -1); // never marked
    // Not walkable (no crumbs, another device): the mark goes, nothing is walked. A timeout takes the mark too.
    bc5_gvw0401_submitted(830, "dcb", 1);
    CHECK(SampleOf(830, 0, 103'000, x, es3, 1, m) == -1 && SampleOf(830, 1, 103'000, x, es3, 1, m) == -1);
    bc5_gvw0401_submitted(831, "dcb", 1);
    bc5_gvw0401_at_timeout(831, "dcb", bc5_gvw0401_now());
    CHECK(SampleOf(831, 1, 104'000, x, es3, 1, m) == -1);
    bc5_gvw0401_submitted(832, "dcb", 1);
    const int k832 = SampleOf(832, 1, 104'000, x, es3, 1, m);
    CHECK(k832 == (mode == 0 ? 2 : -1)); // the control: marked, walkable, within the rate
    if (k832 >= 0) {
        for (const std::string& l: split(g_out)) g_all.push_back(l);
    }
    reset();
    End(mode == 0 ? "on" : mode == 1 ? "off" : "unset");
}

// ---- 14. every line through the quiet filter (BC5_DIRECT_JOURNAL_QUIET's journal_quiet_kind, cap's seam) ---------------
static bool known_prefix(const std::string& l) {
    for (const char* p: {"exp 0401 e9 (gvw): ", "gvw (exp 0401 e9): ", "cpu-wait ", "fl meshlet sample (exp 0401 e9 gvw): "}) {
        if (l.rfind(p, 0) == 0) return true;
    }
    return false;
}
static int quiet(const std::string& l) {
    const std::string s = l + "\n";
    return bc5_cap0401_quiet_kind(s.c_str(), s.size(), 1);
}
static void Quiet(int mode) {
    Begin("the quiet filter");
    static char t[32 * 1024];
    const uint32_t                 n = bc5_gvw0401_texts(t, sizeof(t));
    const std::vector<std::string> v = split(t);
    CHECKW(n == 18 && v.size() == 18, std::to_string(n));
    uint32_t timeouts = 0;
    for (const std::string& l: v) {
        const bool to = has(l, "at the timeout");
        timeouts += to ? 1u : 0u;
        CHECKW(known_prefix(l) && quiet(l) == (to ? -1 : 0), l); // kept; the timeout line also writes quiet mode's held lines first
    }
    CHECK(timeouts == 1);
    CHECK(has(t, "(needs exp 0404's plan of the dcbs' draws, BC5_DIRECT_FL_CRUMBS=1: nothing without it)") && has(t, "(needs BC5_DIRECT_FL_CRUMBS=1 and the draws' user data"));
    CHECK(has(t, "(BC5_DIRECT_WAIT_LATE_PRODUCER_MS does not parse: ") && has(t, "(BC5_DIRECT_UNWAITED_FL_DROP does not parse: ") && has(t, "(BC5_DIRECT_GIVEUP_JOURNAL does not parse: ") &&
          has(t, "(BC5_DIRECT_FL_MESHLET_SAMPLE_UNWAITED does not parse: "));
    CHECK(has(t, "cpu-wait WAIT_REG_MEM64 at 120 on 0x12004b4438: GIVEN UP after 500.0 ms (late-producer bound)\n"));
    reset();
    if (mode == 0) {
        CHECKW(g_all.size() >= 40, std::to_string(g_all.size()));
        for (const std::string& l: g_all) CHECKW(known_prefix(l) && quiet(l) <= 0, l);
    } else {
        CHECKW(g_all.empty(), g_all.empty() ? "" : g_all.front()); // off and unset: no line at all
    }
    End(mode == 0 ? "on" : mode == 1 ? "off" : "unset");
}

} // namespace gvw0401

#ifdef _WIN32
static void set_env(const char* n, const char* v) {
    _putenv_s(n, v == nullptr ? "" : v);
}
#else
static void set_env(const char* n, const char* v) {
    if (v == nullptr) ::unsetenv(n);
    else ::setenv(n, v, 1);
}
#endif

int main(int argc, char** argv) {
    using namespace gvw0401;
    const int mode = argc == 2 ? (std::strcmp(argv[1], "on") == 0 ? 0 : std::strcmp(argv[1], "off") == 0 ? 1 : std::strcmp(argv[1], "unset") == 0 ? 2 : -1) : -1;
    if (mode < 0) {
        std::printf("gvw0401: usage: gvw0401 on | gvw0401 off | gvw0401 unset\n");
        return 2;
    }
    static const char* const names[4]  = {"BC5_DIRECT_WAIT_LATE_PRODUCER_MS", "BC5_DIRECT_UNWAITED_FL_DROP", "BC5_DIRECT_GIVEUP_JOURNAL", "BC5_DIRECT_FL_MESHLET_SAMPLE_UNWAITED"};
    static const char* const on[4]     = {"300", "1", "on", "1"};
    static const char* const off[4]    = {"0", "off", "0", "off"};
    for (int k = 0; k < 4; k++) set_env(names[k], mode == 0 ? on[k] : mode == 1 ? off[k] : nullptr);
    set_env("BC5_DIRECT_FL_CRUMBS", "1");
    for (const char* n: {"BC5_DIRECT_FL_PROBE_STATE", "BC5_DIRECT_FL_VGT_FLUSH", "BC5_DIRECT_FL_SERIAL", "BC5_DIRECT_FL_MESHLET_PROBE", "BC5_DIRECT_FL_CRUMBS_MESHLET", "BC5_DIRECT_FL_SKIP_ES",
                         "BC5_DIRECT_FL_MESHLET_SAMPLE"})
        set_env(n, nullptr);
    std::thread([] {
        std::this_thread::sleep_for(std::chrono::seconds(60));
        std::printf("gvw0401: FAIL watchdog: case \"%s\" still running after 60 s\n", g_case.load());
        std::fflush(stdout);
        std::_Exit(3);
    }).detach();

    Switches(mode);
    Parse();
    Meets();
    Decide();
    ScanCase();
    HostDecision();
    LateWait(mode);
    Window();
    FlTake();
    HostDrop(mode);
    Journal(mode);
    Frames(mode);
    Sample(mode);
    Quiet(mode);

    std::fflush(stderr);
    static const char* const how[3] = {"on", "off", "unset"};
    std::printf("gvw0401: %s %d of %d%s\n", how[mode], g_pass, g_total, g_pass == g_total ? "; end" : "");
    std::fflush(stdout);
    std::_Exit(g_pass == g_total ? 0 : 1);
}
