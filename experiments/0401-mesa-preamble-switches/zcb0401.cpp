// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0401 series e9, tag zcb: the CPU test of mkzcb0401.py's src/libs/bc5LleAgc.cpp (zcb0401-notes.md): the
// switches BC5_DIRECT_ZERO_SKIP_EXCLUDE, BC5_DIRECT_ZERO_SKIP_COPYBACK, BC5_DIRECT_ZERO_SKIP_PROBE and BC5_DIRECT_SCRATCH_WATCH.
// It calls the unit through its seams (bc5_zcb0401_* and zsk's bc5_zsk0401_*): the switches' reading and parse, the
// exclusion by file offset, the copy-back's chunk selection (still skipped, taken back, written by the CPU) on a slice and a
// "direct memory" of the test's own, the probe's non-zero summary and its lines at a take-back and at a timeout, the scratch
// watch's rule and its real thread, and the quiet filter on every line. The session runs the real zero skip as zsk0401.cpp
// does: the test's zero list, zskip_resolve's canary memfd without a BO (bc5_zsk0401_reset(1)), the unit's own canary
// thread, zskip_take_back on the test's memfd. No game, no GPU, no window, no sound device, no network: the direct path is
// never opened (g_dev stays empty: the device's wait is the test's own function), nothing is submitted anywhere.
// Modes: "on" sets EXCLUDE=0x5800000,0X4200000,xyz,0x123, (two entries, three bad ones), COPYBACK=1, PROBE=on and
// SCRATCH_WATCH=1; "off" sets EXCLUDE=off, COPYBACK=0, PROBE=off, SCRATCH_WATCH=0; "unset" unsets all four. Every mode turns
// the zero skip on (BC5_DIRECT_ZERO_SKIP = the test's list, written into the current directory: run each mode in a fresh
// one), so off and unset show e8's zero skip: the same take-backs, no copy, no wait, no line but the four switch lines.
// The unit reads each switch once. The pure cases run in every mode; the session cases check the mode.
// Output: one line per case, then "zcb0401: <mode> N of N; end"; without "; end" something failed. Exit 0 only after the
// end line. A watchdog ends a hang after 60 s with a FAIL line.
// Build: build0401.py ... --gate zcb0401.cpp <out> --like src/libs/bc5LleAgc.cpp (the unit's compile command; linked with
// every emulator object but main.cpp.o, the private bc5LleAgc.cpp.o among them), -std=c++20 -Wall -Wextra -Werror.
// usage (each in a fresh directory): zcb0401 on | zcb0401 off | zcb0401 unset

#include <fcntl.h>
#include <sys/mman.h>
#include <unistd.h>

#include <atomic>
#include <chrono>
#include <cinttypes>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <initializer_list>
#include <string>
#include <thread>
#include <vector>

// The seams of mkzcb0401.py's unit, and zsk's (always compiled in, never called by the emulator).
extern "C" void     bc5_zcb0401_capture(int on);
extern "C" uint64_t bc5_zcb0401_lines(uint64_t from, char* out, uint64_t cap);
extern "C" int      bc5_zcb0401_quiet_kind(const char* line);
extern "C" int      bc5_zcb0401_flag(const char* e, int* bad);
extern "C" uint32_t bc5_zcb0401_exclude_parse(const char* e, uint64_t* offs, uint32_t* bad, char* why, uint64_t cap);
extern "C" void     bc5_zcb0401_switches(uint64_t* out);
extern "C" void     bc5_zcb0401_consts(uint64_t* out);
extern "C" uint64_t bc5_zcb0401_exclude(const char* text, const char* exclude, uint64_t base, uint64_t* runs, uint64_t cap, uint32_t* hits);
extern "C" void     bc5_zcb0401_summary(const void* p, uint64_t n, uint64_t* out);
extern "C" int      bc5_zcb0401_watch_due(double now_t, double line_t, uint32_t lines);
extern "C" uint64_t bc5_zcb0401_watch_steps(const uint64_t* sums, const double* ts, uint64_t n, char* out, uint64_t cap, uint64_t* info);
extern "C" uint64_t bc5_zcb0401_copy(int fd, const void* slice, const uint64_t* chunks, uint64_t n, uint64_t* out);
extern "C" void     bc5_zcb0401_set_wait(int (*fn)(uint64_t, void*), void* ctx);
extern "C" int      bc5_zcb0401_wait(uint64_t ns);
extern "C" void     bc5_zcb0401_snapshot();
extern "C" void     bc5_zcb0401_at_timeout(uint64_t n, const char* kind, const void* ib, uint32_t num_dwords, const uint32_t* copy, uint32_t copy_n);
extern "C" int      bc5_zcb0401_watch_start(int fd);
extern "C" uint64_t bc5_zcb0401_state(int what, uint64_t a);
extern "C" uint64_t bc5_zsk0401_state(int what, uint64_t a);
extern "C" int      bc5_zsk0401_reset(int cpu_canary);
extern "C" int      bc5_zsk0401_sync_start(int kind, const char* const* names, const uint64_t* offs, const uint64_t* sizes, const int* eager, size_t n, uint64_t* blocks);
extern "C" void     bc5_zsk0401_take_back(int kind, int fd, uint64_t* blocks);
extern "C" size_t   bc5_zsk0401_pieces(uint64_t va, uint64_t size, uint32_t run, uint64_t lo, uint64_t hi);

namespace zcb0401 {

static int                      g_pass = 0, g_total = 0, g_case_pass = 0, g_case_total = 0;
static std::atomic<const char*> g_case {"init"};

static void Check(bool ok, const char* what, int line, const std::string& why = "") {
    g_total++;
    g_case_total++;
    if (ok) {
        g_pass++;
        g_case_pass++;
    } else {
        std::printf("zcb0401: FAIL %s (line %d): %s%s%s\n", g_case.load(), line, what, why.empty() ? "" : ": ", why.c_str());
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
    std::printf("zcb0401: case %s (%s): %d of %d\n", g_case.load(), how, g_case_pass, g_case_total);
    std::fflush(stdout);
}

constexpr uint64_t M = 1ull << 20u, kChunk = 2 * M, kNone = ~0ull, kMark = 7;
// zsk's state indices (mkzsk0401.py), and zcb's (mkzcb0401.py).
enum { kBytes = 0, kRuns = 1, kSlices = 2, kHeapsRead = 5, kCpu = 8, kHits = 9, kContains = 12, kLeft = 14, kFlag = 15, kCanaryFd = 17 };
enum { zBacks = 0, zHits = 1, zKept = 2, zRun = 3, zIsHit = 4, zChunks = 5, zVas = 6, zSnapRuns = 7, zSnapLeft = 8, zSnapFlag = 9, zScans = 10, zFirstMs = 11, zChanges = 12, zChangeLines = 13,
       zMapped = 14, zExclHits = 15, zExclReported = 16 };
static uint64_t Zs(int what, uint64_t a = 0) {
    return bc5_zsk0401_state(what, a);
}
static uint64_t Zc(int what, uint64_t a = 0) {
    return bc5_zcb0401_state(what, a);
}

// The session's list (exp 0379's format). Heap A (64 MiB) has runs 0-3: 8 MiB at 0, 4 MiB at 16 MiB, 16 MiB at 32 MiB, 2 MiB at
// 56 MiB (file 0x5800000, the one "on" excludes); heap B's views span 34 MiB, not the listed 32, so it is refused.
static const char* const kList = "# bc5 zero list v1 (experiment 0379): chunks all-zero in every scan, offsets from the heap's start\n"
                                 "heap ZcbHeapA 0x4000000 3\n"
                                 "zero ZcbHeapA 0x0 0x800000\n"
                                 "zero ZcbHeapA 0x1000000 0x400000\n"
                                 "zero ZcbHeapA 0x2000000 0x1000000\n"
                                 "zero ZcbHeapA 0x3800000 0x200000\n"
                                 "heap ZcbHeapB 0x2000000 3\n"
                                 "zero ZcbHeapB 0x0 0x400000\n";
constexpr uint64_t       kBaseA = 0x2000000, kBaseB = 0x6000000, kFileSize = 0x9000000, kRun3 = kBaseA + 0x3800000;
static const char* const kNames[] = {"ZcbHeapA", "ZcbHeapA", "ZcbHeapA", "ZcbHeapB"};
static const uint64_t    kOffs[]  = {kBaseA, kBaseA + 0x2800000, 0x8400000, kBaseB};
static const uint64_t    kSizes[] = {0x2800000, 0x1800000, 0x200000, 0x2200000};
static const int         kEager[] = {1, 1, 0, 1};
// The canary mappings the test declares (zskip_map makes none without a device): runs 0, 1 and 2, and an alias of run 2.
constexpr uint64_t kVa0 = 0x10002000000ull, kVa1 = 0x10003000000ull, kVa2 = 0x10004000000ull, kVaAlias = 0x20000000000ull;

static int  g_direct = -1; // the test's direct memory (a memfd of kFileSize)
static bool g_on     = false;

static bool Poke(int fd, uint64_t off, unsigned char v) {
    return pwrite(fd, &v, 1, static_cast<off_t>(off)) == 1;
}
static int Peek(int fd, uint64_t off) {
    unsigned char v = 0;
    return pread(fd, &v, 1, static_cast<off_t>(off)) == 1 ? v : -1;
}
static int Memfd(const char* name, uint64_t size) {
    const int fd = memfd_create(name, MFD_CLOEXEC);
    if (fd < 0 || ftruncate(fd, static_cast<off_t>(size)) != 0) return -1;
    return fd;
}
static bool WaitFlag(uint64_t run, uint64_t want, int ms) { // the unit's canary watcher looks at one slice per 50 ms
    const auto until = std::chrono::steady_clock::now() + std::chrono::milliseconds(ms);
    while (std::chrono::steady_clock::now() < until) {
        if (Zs(kFlag, run) == want) return true;
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }
    return Zs(kFlag, run) == want;
}
static int SyncStart(uint64_t* blocks) {
    return bc5_zsk0401_sync_start(0, kNames, kOffs, kSizes, kEager, 4, blocks);
}
static void TakeBack() {
    uint64_t b = kMark;
    bc5_zsk0401_take_back(0, g_direct, &b);
}
// The test's FNV-1a over 8-byte little-endian words (the summary's hash, written again from its comment).
static uint64_t Fnv(const unsigned char* p, size_t n) {
    uint64_t h = 0xcbf29ce484222325ull;
    for (size_t i = 0; i < n; i += 8) {
        uint64_t w = 0;
        for (size_t k = 0; k < 8 && i + k < n; k++) w |= static_cast<uint64_t>(p[i + k]) << (8u * k);
        h = (h ^ w) * 0x100000001b3ull;
    }
    return h;
}
static uint64_t Fnv2M(std::initializer_list<std::pair<uint32_t, unsigned char>> bytes) { // a 2 MiB slice with these bytes set
    std::vector<unsigned char> b(kChunk, 0);
    for (const auto& [at, v]: bytes) b[at] = v;
    return Fnv(b.data(), b.size());
}
static std::string Hex16(uint64_t v) {
    char t[32];
    std::snprintf(t, sizeof(t), "0x%016" PRIx64, v);
    return t;
}
// The lines zcb journaled, from index `from` on.
static std::vector<char> g_buf(4u << 20u);
static uint64_t          NLines() {
    char b[1];
    return bc5_zcb0401_lines(~0ull >> 1u, b, 1);
}
static std::vector<std::string> Lines(uint64_t from) {
    bc5_zcb0401_lines(from, g_buf.data(), g_buf.size());
    std::vector<std::string> v;
    std::string              cur;
    for (const char* p = g_buf.data(); *p != 0; p++) {
        if (*p == '\n') {
            v.push_back(cur);
            cur.clear();
        } else {
            cur.push_back(*p);
        }
    }
    return v;
}
static int Has(const std::vector<std::string>& v, const std::string& a, const std::string& b = "", const std::string& c = "") { // lines with all three
    int n = 0;
    for (const auto& l: v) n += l.find(a) != std::string::npos && l.find(b) != std::string::npos && l.find(c) != std::string::npos ? 1 : 0;
    return n;
}
static std::string Join(const std::vector<std::string>& v) {
    std::string s;
    for (const auto& l: v) s += l + " | ";
    return s;
}
// The device's wait, as the test gives it (bc5_zcb0401_set_wait): ns 0 is PROBE's zero-time query; any other wait is COPYBACK's.
struct WaitCtx {
    int      canary = -1;
    int      mode   = 0; // 0: a job ends while waited for and writes 0x77 at slice 0's 0x20000, then idle; 1: the bound is hit
    int      calls = 0, zero_calls = 0;
    uint64_t ns = 0;
};
static int TestWait(uint64_t ns, void* ctx) {
    auto* w = static_cast<WaitCtx*>(ctx);
    if (ns == 0) {
        w->zero_calls++;
        return 1;
    }
    w->calls++;
    w->ns = ns;
    if (w->mode == 0) {
        Poke(w->canary, 0x20000, 0x77);
        return 1;
    }
    return 0;
}
static WaitCtx g_wait;

// ---- 1. the switches as the unit reads them (mode) ----------------------------------------------------------------------
static void Switches(const char* mode) {
    Begin("the switches");
    uint64_t sw[21] = {}, c[10] = {};
    bc5_zcb0401_switches(sw);
    bc5_zcb0401_consts(c);
    CHECK(c[0] == 16 && c[1] == 500000000ull && c[2] == 4096 && c[3] == 64 && c[4] == 4 && c[7] == 50 && c[8] == 10000 && c[9] == 64);
    const std::vector<std::string> l = Lines(0);
    CHECKW(l.size() == 4 && Has(l, "exp 0401 e9 (zcb): ") == 4, Join(l));
    if (g_on) {
        CHECK(sw[0] == 2 && sw[1] == 3 && sw[2] == 1 && sw[3] == 1 && sw[4] == 1 && sw[5] == 0x5800000 && sw[6] == 0x4200000 && sw[7] == 0);
        CHECKW(Has(l, "exp 0401 e9 (zcb): BC5_DIRECT_ZERO_SKIP_EXCLUDE: a run of the zero list at file 0x5800000 or 0x4200000 is placed as normal memory, not skipped; 3 bad entries ignored: "
                      "'xyz' (not a hex number), '0x123' (not 2 MiB aligned), '' (empty)") == 1,
               Join(l));
        CHECK(Has(l, "exp 0401 e9 (zcb): BC5_DIRECT_ZERO_SKIP_COPYBACK on: at a canary hit, after a wait of at most 500 ms a ring for the jobs in flight") == 1);
        CHECK(Has(l, "exp 0401 e9 (zcb): BC5_DIRECT_ZERO_SKIP_PROBE on: each take-back") == 1 && Has(l, "exp 0401 e9 (zcb): BC5_DIRECT_SCRATCH_WATCH on: the hole scratch BO") == 1);
        CHECK(Has(l, "the zero skip is off") == 0 && Has(l, "does not parse") == 0);
    } else {
        for (int k = 0; k < 21; k++) CHECKW(sw[k] == 0, std::to_string(k));
        CHECKW(l.size() == 4 && l[0] == "exp 0401 e9 (zcb): BC5_DIRECT_ZERO_SKIP_EXCLUDE off" && l[1] == "exp 0401 e9 (zcb): BC5_DIRECT_ZERO_SKIP_COPYBACK off" &&
                   l[2] == "exp 0401 e9 (zcb): BC5_DIRECT_ZERO_SKIP_PROBE off" && l[3] == "exp 0401 e9 (zcb): BC5_DIRECT_SCRATCH_WATCH off",
               Join(l));
    }
    bc5_zcb0401_switches(sw); // read once: no second set of lines
    CHECK(NLines() == 4);
    End(mode);
}

// ---- 2. the parse ----------------------------------------------------------------------------------------------------
static void Parse() {
    Begin("the parse");
    int bad = 9;
    for (const char* e: {static_cast<const char*>(nullptr), "", "0", "off"}) CHECKW(bc5_zcb0401_flag(e, &bad) == 0 && bad == 0, e == nullptr ? "null" : e);
    CHECK(bc5_zcb0401_flag("1", &bad) == 1 && bad == 0);
    CHECK(bc5_zcb0401_flag("on", &bad) == 1 && bad == 0);
    for (const char* e: {"2", "yes", "01", "on1", " 1", "ON", "true", "-1", "1 "}) CHECKW(bc5_zcb0401_flag(e, &bad) == 0 && bad == 1, e);
    uint64_t    o[16] = {};
    uint32_t    nb    = 9;
    char        why[512];
    const auto  P     = [&](const char* e) { return bc5_zcb0401_exclude_parse(e, o, &nb, why, sizeof(why)); };
    const auto  W     = [&]() { return std::string(why); };
    for (const char* e: {static_cast<const char*>(nullptr), "", "0", "off"}) CHECKW(P(e) == 0 && nb == 0 && W().empty(), e == nullptr ? "null" : e);
    CHECK(P("0x22da00000") == 1 && nb == 0 && o[0] == 0x22da00000ull);
    CHECK(P("22da00000") == 1 && nb == 0 && o[0] == 0x22da00000ull);
    CHECK(P("0X1BC400000,0x22da00000") == 2 && nb == 0 && o[0] == 0x1bc400000ull && o[1] == 0x22da00000ull);
    CHECK(P("0x0") == 1 && nb == 0 && o[0] == 0);
    CHECKW(P("0x22da00000,0x22da00000") == 1 && nb == 1 && W() == "'0x22da00000' (repeated)", W());
    CHECKW(P("0x22da0000") == 0 && nb == 1 && W() == "'0x22da0000' (not 2 MiB aligned)", W());
    CHECKW(P("xyz") == 0 && nb == 1 && W() == "'xyz' (not a hex number)", W());
    CHECKW(P("0x") == 0 && nb == 1 && W() == "'0x' (not a hex number)", W());
    CHECKW(P(",") == 0 && nb == 2 && W() == "'' (empty), '' (empty)", W());
    CHECKW(P("0x200000, 0x400000") == 1 && nb == 1 && W() == "' 0x400000' (not a hex number)", W());
    CHECKW(P("0x10000000000000000") == 0 && nb == 1 && W() == "'0x10000000000000000' (more than 16 hex digits)", W());
    std::string many;
    for (int k = 1; k <= 17; k++) many += (k == 1 ? "" : ",") + std::to_string(2 * k) + "00000"; // 0x200000 .. 0x3400000 (hex digits read as hex)
    CHECKW(P(many.c_str()) == 16 && nb == 1 && o[15] == 0x3200000ull && W() == "'3400000' (past the 16th entry)", W());
    CHECKW(P("a,b,c,d,e,f,g,h,i,j") == 0 && nb == 10 && W().find("'h' (not a hex number) and 2 more") != std::string::npos, W());
    End("pure");
}

// ---- 3. the exclusion by file offset (pure) ----------------------------------------------------------------------------
static void Exclude() {
    Begin("the exclusion");
    const char* const list = "heap H 0x4000000 3\nzero H 0x0 0x800000\nzero H 0x1000000 0x400000\nzero H 0x2000000 0x1000000\n";
    uint64_t          r[16] = {};
    uint32_t          h[16] = {};
    const uint64_t    from  = NLines();
    CHECK(bc5_zcb0401_exclude(list, "0x41000000", 0x40000000, r, 8, h) == 2 && r[0] == 0 && r[1] == 0x800000 && r[2] == 0x2000000 && r[3] == 0x1000000 && h[0] == 1);
    std::vector<std::string> l = Lines(from);
    CHECKW(l.size() == 1 && Has(l, "zero skip exclude (exp 0401 e9 zcb): H: the run at file 0x41000000 +4.0 MiB is not skipped: it is placed as normal memory (BC5_DIRECT_ZERO_SKIP_EXCLUDE)") == 1,
           Join(l));
    h[0] = 0;
    CHECK(bc5_zcb0401_exclude(list, "0x41200000", 0x40000000, r, 8, h) == 3 && h[0] == 0); // inside run 1, not its start
    CHECK(bc5_zcb0401_exclude(list, "", 0x40000000, r, 8, h) == 3);
    CHECK(bc5_zcb0401_exclude(list, "0x40000000,0x42000000", 0x40000000, r, 8, h) == 1 && r[0] == 0x1000000 && r[1] == 0x400000 && h[0] == 1 && h[1] == 1);
    h[0] = h[1] = 0;
    CHECK(bc5_zcb0401_exclude(list, "0x1000000", 0, r, 8, h) == 2 && r[2] == 0x2000000 && h[0] == 1); // the heap's offset counts: base + run
    CHECK(bc5_zcb0401_exclude(list, "0x1000000", 0x40000000, r, 8, h) == 3);
    CHECK(NLines() == from + 4);
    End("pure");
}

// ---- 4. the non-zero summary (pure) ------------------------------------------------------------------------------------
static void Summary() {
    Begin("the non-zero summary");
    std::vector<unsigned char> b(kChunk + 3, 0);
    uint64_t                   s[4] = {};
    bc5_zcb0401_summary(b.data(), b.size(), s);
    CHECK(s[0] == 0 && s[1] == ~0ull && s[2] == ~0ull && s[3] == Fnv(b.data(), b.size()));
    b[0] = 1, b[7] = 2, b[4096] = 3, b[b.size() - 1] = 4;
    bc5_zcb0401_summary(b.data(), b.size(), s);
    CHECKW(s[0] == 4 && s[1] == 0 && s[2] == b.size() - 1 && s[3] == Fnv(b.data(), b.size()), std::to_string(s[0]) + " " + std::to_string(s[1]) + " " + std::to_string(s[2]));
    b[7] = 0;
    uint64_t t[4] = {};
    bc5_zcb0401_summary(b.data(), b.size(), t);
    CHECK(t[0] == 3 && t[3] != s[3] && t[3] == Fnv(b.data(), b.size()));
    bc5_zcb0401_summary(b.data(), 0, s);
    CHECK(s[0] == 0 && s[1] == ~0ull && s[3] == 0xcbf29ce484222325ull);
    const unsigned char five[5] = {0, 0, 0, 0, 9}; // a part word at the end
    bc5_zcb0401_summary(five, 5, s);
    CHECK(s[0] == 1 && s[1] == 4 && s[2] == 4 && s[3] == Fnv(five, 5));
    End("pure");
}

// ---- 5. the scratch watch's rule (pure) ----------------------------------------------------------------------------------
static void WatchRule() {
    Begin("the scratch watch's rule");
    CHECK(bc5_zcb0401_watch_due(5.0, -1.0, 0) == 1);
    CHECK(bc5_zcb0401_watch_due(5.0, 1.0, 0) == 0);
    CHECK(bc5_zcb0401_watch_due(11.0, 1.0, 0) == 1);
    CHECK(bc5_zcb0401_watch_due(11.0, 1.0, 63) == 1 && bc5_zcb0401_watch_due(11.0, 1.0, 64) == 0);
    const uint64_t N = ~0ull;
    const uint64_t sums[] = {0, N, N, 0, 1, 0x10, 0x10, 0xabc, 1, 0x10, 0x10, 0xabc, 2, 0x10, 0x20, 0xdef, 2, 0x10, 0x20, 0xdef, 2, 0x10, 0x20, 0xdef, 0, N, N, 0, 0, N, N, 0};
    const double   ts[]   = {1.0, 1.05, 1.10, 2.0, 5.0, 11.06, 11.10, 21.2};
    char           out[4096];
    uint64_t       info[4] = {};
    CHECK(bc5_zcb0401_watch_steps(sums, ts, 8, out, sizeof(out), info) == 3);
    const std::string s = out;
    CHECKW(s.find("scratch watch (exp 0401 e9 zcb): t 1.050 s: the hole scratch BO is not all zero: 1 non-zero bytes, first at 0x10, last at 0x10, hash 0x0000000000000abc (a GPU write into a hole") == 0,
           s);
    CHECKW(s.find("\nscratch watch (exp 0401 e9 zcb): t 11.060 s: the hole scratch BO changed (1 changes since t 1.050 s): 2 non-zero bytes, first at 0x10, last at 0x20, hash 0x0000000000000def\n") !=
               std::string::npos,
           s);
    CHECKW(s.find("\nscratch watch (exp 0401 e9 zcb): t 21.200 s: the hole scratch BO changed (2 changes since t 1.050 s): all zero again\n") != std::string::npos, s);
    CHECK(info[0] == 8 && info[1] == 2 && info[2] == 2 && info[3] == 0);
    // A change in the gap waits: the scan at 2.0 changed, and no line came before 11.06.
    CHECK(bc5_zcb0401_watch_steps(sums, ts, 5, out, sizeof(out), info) == 1 && info[1] == 1 && info[2] == 0 && info[3] == 1);
    // All zero from the start: no line at all.
    const uint64_t zero[] = {0, N, N, 0, 0, N, N, 0};
    CHECK(bc5_zcb0401_watch_steps(zero, ts, 2, out, sizeof(out), info) == 0 && info[0] == 2 && info[1] == 0);
    End("pure");
}

// ---- 6. the copy itself: which chunks, which pages (pure, a memfd of the test's own) -------------------------------------
static void CopyPure() {
    Begin("the copy's chunk selection");
    const int fd = Memfd("zcb0401-copy", 10 * M);
    CHECK(fd >= 0);
    CHECK(Poke(fd, 2 * M + 100, 0x5c));          // chunk 2 MiB: the CPU wrote it
    CHECK(Poke(fd, 6 * M + kChunk - 1, 0x5d));   // chunk 6 MiB: its last byte
    std::vector<unsigned char> slice(kChunk, 0);
    slice[0] = 0xa1, slice[0x1fff00] = 0xb2;     // pages 0 and 0x1ff000
    const uint64_t chunks[] = {0, 2 * M, 4 * M, 6 * M};
    uint64_t       out[6]   = {};
    CHECK(bc5_zcb0401_copy(fd, slice.data(), chunks, 4, out) == 2);
    CHECKW(out[0] == 4 && out[1] == 2 && out[2] == 2 && out[3] == 0 && out[4] == 2 && out[5] == 2 * 2 * 4096, std::to_string(out[2]) + " " + std::to_string(out[5]));
    CHECK(Peek(fd, 0) == 0xa1 && Peek(fd, 0x1fff00) == 0xb2 && Peek(fd, 4 * M) == 0xa1 && Peek(fd, 4 * M + 0x1fff00) == 0xb2);
    CHECK(Peek(fd, 2 * M) == 0 && Peek(fd, 2 * M + 100) == 0x5c && Peek(fd, 2 * M + 0x1fff00) == 0); // the CPU's chunk is left as it is
    CHECK(Peek(fd, 6 * M) == 0 && Peek(fd, 6 * M + kChunk - 1) == 0x5d);
    CHECK(Peek(fd, 1000) == 0 && Peek(fd, 4 * M + 0x1000) == 0); // only the non-zero pages were written; the rest reads zeros as before
    const std::vector<unsigned char> zero(kChunk, 0);
    const uint64_t                   eight[] = {8 * M};
    CHECK(bc5_zcb0401_copy(fd, zero.data(), eight, 1, out) == 1 && out[4] == 0 && out[5] == 0); // an all-zero slice: nothing to write
    CHECK(bc5_zcb0401_copy(-1, slice.data(), eight, 1, out) == 0 && out[3] == 1);                // a write that fails is counted
    close(fd);
    End("pure");
}

// ---- 7. the session: the placement with the exclusion (mode) --------------------------------------------------------------
static void Placement(const char* mode) {
    Begin("placement and exclusion");
    const uint64_t from = NLines();
    CHECK(bc5_zsk0401_reset(1) == 0);
    uint64_t b = kMark;
    CHECK(SyncStart(&b) == 1 && b == kNone);
    CHECK(Zs(kHeapsRead) == 2 && Zs(kSlices) == 5); // one slice per run of the list, the excluded run's included
    CHECK(Zs(kRuns) == (g_on ? 3u : 4u));
    CHECKW(Zs(kBytes) == (g_on ? 28 : 30) * M, std::to_string(Zs(kBytes) / M));
    CHECK(Zs(kContains, kRun3) == (g_on ? 0u : 1u));
    CHECK(Zs(kContains, kBaseA) == 1 && Zs(kContains, kBaseA + 16 * M) == 1 && Zs(kContains, kBaseA + 32 * M) == 1 && Zs(kContains, kBaseB) == 0);
    const std::vector<std::string> l = Lines(from);
    if (g_on) {
        CHECKW(l.size() == 2 && Has(l, "zero skip exclude (exp 0401 e9 zcb): ZcbHeapA: the run at file 0x5800000 +2.0 MiB is not skipped: it is placed as normal memory") == 1 &&
                   Has(l, "zero skip exclude (exp 0401 e9 zcb): 0x4200000 is the start of no run of the list's placed heaps: nothing left out for it") == 1,
               Join(l));
        CHECK(Zc(zExclHits, 0) == 1 && Zc(zExclHits, 1) == 0 && Zc(zExclReported) == 1);
    } else {
        CHECKW(l.empty(), Join(l));
        CHECK(Zc(zExclHits, 0) == 0 && Zc(zExclReported) == 0);
    }
    for (uint64_t k = 0; k < 4; k++) bc5_zsk0401_pieces(kVa0 + k * kChunk, kChunk, 0, 0, 0);
    for (uint64_t k = 0; k < 2; k++) bc5_zsk0401_pieces(kVa1 + k * kChunk, kChunk, 1, 0, 0);
    bc5_zsk0401_pieces(kVa2, 8 * M, 2, 0, 0);
    CHECK(bc5_zsk0401_pieces(kVa2 + 8 * M, 8 * M, 2, 0, 0) == 8);
    CHECK(bc5_zsk0401_pieces(kVaAlias, kChunk, 2, 0, 0) == 9);
    bc5_zcb0401_snapshot(); // as zskip_map does after a pass
    CHECK(Zc(zSnapRuns) == (g_on ? 3u : kNone));
    CHECK(Zc(zSnapLeft, 0) == (g_on ? 8 * M : kNone) && Zc(zSnapFlag, 0) == (g_on ? 0u : kNone));
    CHECK(NLines() == from + (g_on ? 2u : 0u));
    End(mode);
}

// ---- 8. a CPU write takes a chunk back (mode) -------------------------------------------------------------------------------
static void CpuWrite(const char* mode) {
    Begin("CPU write");
    const uint64_t from = NLines();
    CHECK(Poke(g_direct, kBaseA + 2 * M + 5, 0x33)); // run 0's chunk 1
    TakeBack();
    CHECK(Zs(kCpu) == 1 && Zs(kLeft, 0) == 6 * M && Zs(kContains, kBaseA + 2 * M) == 0);
    CHECK(Zs(kBytes) == (g_on ? 26 : 28) * M);
    const std::vector<std::string> l = Lines(from);
    if (g_on) {
        CHECKW(l.size() == 1 && Has(l, "zero skip probe (exp 0401 e9 zcb): t ",
                                    " s: take-back by CPU writes: run 0, file 0x2000000-0x2800000 (+8.0 MiB), 1 chunks taken back (0x2200000), 3 still skipped; the run's canary VAs: "
                                    "0x10002000000-0x10002800000; its slice: all zero (hash " + Hex16(Fnv2M({})) + "); jobs in flight: 0 submissions so far; every ring idle now: no device") == 1,
               Join(l));
        CHECK(Zc(zBacks) == 1 && Zc(zHits) == 0 && Zc(zRun) == 0 && Zc(zIsHit) == 0 && Zc(zChunks) == 1 && Zc(zVas) == 1);
        CHECK(Zc(zSnapLeft, 0) == 6 * M); // the snapshot after the take-back
    } else {
        CHECKW(l.empty(), Join(l));
        CHECK(Zc(zBacks) == 0 && Zc(zRun) == kNone);
    }
    End(mode);
}

// ---- 9. a canary hit in run 0: the copy-back after the wait (mode) ----------------------------------------------------------
static void Hit0(const char* mode) {
    Begin("canary hit, run 0");
    g_wait.canary = static_cast<int>(Zs(kCanaryFd)) - 1;
    g_wait.mode   = 0;
    CHECK(g_wait.canary >= 0);
    bc5_zcb0401_set_wait(TestWait, &g_wait);
    CHECK(Poke(g_direct, kBaseA + 6 * M + 9, 0x44)); // run 0's chunk 3: the CPU wrote it after the last walk, so it is still skipped at the hit
    CHECK(Poke(g_wait.canary, 0x1234, 0x5a));        // "the GPU" wrote into run 0's slice
    CHECK(Poke(g_wait.canary, 0x10000, 0xa5));
    CHECK(WaitFlag(0, 1, 10000));
    const uint64_t from = NLines();
    TakeBack();
    CHECK(Zs(kHits) == 1 && Zs(kFlag, 0) == 2 && Zs(kLeft, 0) == 0 && Zs(kContains, kBaseA) == 0 && Zs(kContains, kBaseA + 6 * M) == 0); // e8's take-back, every mode
    CHECK(Zs(kBytes) == (g_on ? 20 : 22) * M);
    const std::vector<std::string> l = Lines(from);
    if (g_on) {
        CHECK(g_wait.calls == 1 && g_wait.ns == 500000000ull && g_wait.zero_calls >= 1);
        CHECKW(l.size() == 2, Join(l));
        CHECKW(l.size() == 2 &&
                   l[0].find(" s: take-back by a canary hit: run 0, file 0x2000000-0x2800000 (+8.0 MiB), 3 of 4 chunks still skipped (the others are real memory already); its canary VAs: "
                             "0x10002000000-0x10002800000; its slice: 2 non-zero bytes, first at 0x1234, last at 0x10000, hash " +
                             Hex16(Fnv2M({{0x1234, 0x5a}, {0x10000, 0xa5}})) + "; jobs in flight: 0 submissions so far; every ring idle now: yes") != std::string::npos &&
                   l[0].find("zero skip probe (exp 0401 e9 zcb): t ") == 0,
               Join(l));
        CHECKW(l.size() == 2 && l[1].find("zero skip copy-back (exp 0401 e9 zcb): t ") == 0 && l[1].find(" s: run 0 (file 0x2000000 +8.0 MiB): waited ") != std::string::npos &&
                   l[1].find(" ms (at most 500 ms a ring) for the jobs in flight: every ring idle; the slice has 3 non-zero pages of 4 KiB; 24576 bytes copied into 2 of the 3 chunks still "
                             "skipped, 1 of them held CPU data and were left as they are, 0 writes failed; 1 chunks taken back before stay as they are") != std::string::npos,
               Join(l));
        // The still-skipped chunks hold the slice now, the write made during the wait included; the CPU's chunks are as they were.
        for (const uint64_t c: {kBaseA, kBaseA + 4 * M}) CHECK(Peek(g_direct, c + 0x1234) == 0x5a && Peek(g_direct, c + 0x10000) == 0xa5 && Peek(g_direct, c + 0x20000) == 0x77);
        CHECK(Zc(zBacks) == 2 && Zc(zHits) == 1 && Zc(zRun) == 0 && Zc(zIsHit) == 1 && Zc(zChunks) == 3);
        CHECK(Zc(zSnapLeft, 0) == 0 && Zc(zSnapFlag, 0) == 2);
    } else {
        CHECK(g_wait.calls == 0 && g_wait.zero_calls == 0); // e8: no wait
        CHECKW(l.empty(), Join(l));
        for (const uint64_t c: {kBaseA, kBaseA + 4 * M}) CHECK(Peek(g_direct, c + 0x1234) == 0 && Peek(g_direct, c + 0x10000) == 0 && Peek(g_direct, c + 0x20000) == 0); // e8: no copy
    }
    CHECK(Peek(g_direct, kBaseA + 2 * M + 0x1234) == 0 && Peek(g_direct, kBaseA + 2 * M + 5) == 0x33 && Peek(g_direct, kBaseA + 2 * M + 0x10000) == 0); // taken back before: as it was
    CHECK(Peek(g_direct, kBaseA + 6 * M + 0x1234) == 0 && Peek(g_direct, kBaseA + 6 * M + 9) == 0x44);                                              // the CPU's data stays
    End(mode);
}

// ---- 10. a fence timeout before the scratch BO is watched (mode) --------------------------------------------------------------
static uint32_t Hdr(uint32_t op, uint32_t len) {
    return 0xC0000000u | ((len - 2u) << 16u) | (op << 8u);
}
static void Timeout1(const char* mode) {
    Begin("a timeout: the take-backs and the job's records");
    // The host's copy: WRITE_DATA to run 2's VAs, COMPUTE_USER_DATA 0-1 pointing into run 1's, a dispatch, an EOP elsewhere.
    const uint32_t copy[20] = {Hdr(0x37, 5), 5u << 8u, 0x04010000u, 0x100u, 1u,           Hdr(0x76, 4), 0x240u, 0x03000100u, 0x100u, Hdr(0x15, 5),
                               1u,           1u,       1u,          0u,     Hdr(0x47, 6), 0x14u,        0x30000000u, 1u << 29u, 7u,    0u};
    const uint64_t from     = NLines();
    bc5_zcb0401_at_timeout(77, "acb", reinterpret_cast<const void*>(static_cast<uintptr_t>(kVa0 + M)), 64, copy, 20);
    const std::vector<std::string> l = Lines(from);
    if (g_on) {
        CHECKW(l.size() == 5, Join(l));
        CHECKW(Has(l, "zero skip probe (exp 0401 e9 zcb): at the timeout of submit #77 acb: t ", " s: 2 take-backs so far (1 by canary hits), the last 2 below, newest first; the skip by run as of t ") == 1,
               Join(l));
        CHECKW(Has(l, "zero skip probe (exp 0401 e9 zcb): at the timeout of submit #77: take-back 2 of 2, ",
                   " s ago, by a canary hit: run 0, file 0x2000000-0x2800000 (+8.0 MiB), 3 chunks still skipped then; its VAs: 0x10002000000-0x10002800000") == 1,
               Join(l));
        CHECKW(Has(l, "zero skip probe (exp 0401 e9 zcb): at the timeout of submit #77: take-back 1 of 2, ",
                   " s ago, by CPU writes: run 0, file 0x2000000-0x2800000 (+8.0 MiB), chunks 0x2200000; the run's VAs: 0x10002000000-0x10002800000") == 1,
               Join(l));
        CHECKW(Has(l, "zero skip probe (exp 0401 e9 zcb): at the timeout of submit #77 acb: the job's own records: the buffer 0x10002100000 +0x100; from the host's copy of 20 dwords, 2 memory "
                      "operands and 1 user-data pairs at dispatches; touching a taken-back run: run 0, taken back by a canary hit ",
                   " s ago (the buffer: 0x10002100000); touching a still-skipped run: run 2, 8 of 8 chunks still skipped (op 37 at dword 0: 0x10004010000); run 1, 2 of 2 chunks still skipped (user "
                   "data 0-1 at the dispatch at dword 9: 0x10003000100) (an address in a range is no proof that the GPU used it") == 1,
               Join(l));
        CHECKW(Has(l, "scratch watch (exp 0401 e9 zcb): at the timeout of submit #77 acb: the scratch BO is not watched") == 1, Join(l));
        for (const auto& s: l) CHECKW(bc5_zcb0401_quiet_kind(s.c_str()) == -1, s); // timeout lines: kept, and the quiet ring goes out before the first
    } else {
        CHECKW(l.empty(), Join(l));
    }
    End(mode);
}

// ---- 11. a canary hit in run 1 whose wait hits its bound (mode) -----------------------------------------------------------------
static void Hit1(const char* mode) {
    Begin("canary hit, run 1, the wait's bound");
    g_wait.mode  = 1;
    g_wait.calls = 0;
    CHECK(Poke(g_wait.canary, kChunk + 0x40, 0x99));
    CHECK(WaitFlag(1, 1, 10000));
    const uint64_t from = NLines();
    TakeBack();
    CHECK(Zs(kHits) == 2 && Zs(kLeft, 1) == 0 && Zs(kBytes) == (g_on ? 16 : 18) * M);
    const std::vector<std::string> l = Lines(from);
    if (g_on) {
        CHECK(g_wait.calls == 1);
        CHECKW(l.size() == 2 && Has(l, "take-back by a canary hit: run 1, file 0x3000000-0x3400000 (+4.0 MiB), 2 of 2 chunks still skipped") == 1 &&
                   Has(l, "zero skip copy-back (exp 0401 e9 zcb): t ",
                       " ms (at most 500 ms a ring) for the jobs in flight: NOT idle within the bound: the GPU may still write into the slice; the slice has 1 non-zero pages of 4 KiB; 8192 bytes "
                       "copied into 2 of the 2 chunks still skipped, 0 of them held CPU data and were left as they are, 0 writes failed; 0 chunks taken back before stay as they are") == 1,
               Join(l));
        CHECK(Peek(g_direct, kBaseA + 16 * M + 0x40) == 0x99 && Peek(g_direct, kBaseA + 18 * M + 0x40) == 0x99);
    } else {
        CHECK(g_wait.calls == 0);
        CHECKW(l.empty(), Join(l));
        CHECK(Peek(g_direct, kBaseA + 16 * M + 0x40) == 0 && Peek(g_direct, kBaseA + 18 * M + 0x40) == 0);
    }
    End(mode);
}

// ---- 12. three CPU writes in run 2, one take-back each (mode) -------------------------------------------------------------------
static void CpuWrites2(const char* mode) {
    Begin("CPU writes, run 2");
    const uint64_t from = NLines();
    for (uint64_t k = 0; k < 3; k++) {
        CHECK(Poke(g_direct, kBaseA + 32 * M + k * kChunk + 1, static_cast<unsigned char>(0x10 + k)));
        TakeBack();
    }
    CHECK(Zs(kCpu) == 4 && Zs(kLeft, 2) == 10 * M);
    const std::vector<std::string> l = Lines(from);
    if (g_on) {
        CHECKW(l.size() == 3 && Has(l, "take-back by CPU writes: run 2, file 0x4000000-0x5000000 (+16.0 MiB), 1 chunks taken back (0x4000000), 7 still skipped") == 1 &&
                   Has(l, "(0x4200000), 6 still skipped") == 1 && Has(l, "(0x4400000), 5 still skipped; the run's canary VAs: 0x10004000000-0x10005000000, 0x20000000000-0x20000200000") == 1,
               Join(l));
        CHECK(Zc(zBacks) == 6 && Zc(zKept) == 6 && Zc(zHits) == 2 && Zc(zVas) == 2);
    } else {
        CHECKW(l.empty(), Join(l));
    }
    End(mode);
}

// ---- 13. the scratch watch's real thread (mode) -------------------------------------------------------------------------------
static bool WaitState(int what, uint64_t not_value, int ms) {
    const auto until = std::chrono::steady_clock::now() + std::chrono::milliseconds(ms);
    while (std::chrono::steady_clock::now() < until) {
        if (Zc(what) != not_value) return true;
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }
    return Zc(what) != not_value;
}
static void Watch(const char* mode) {
    Begin("the scratch watch");
    const int fd = Memfd("zcb0401-scratch", kChunk); // the scratch BO's memfd, as scratch_bo makes it
    CHECK(fd >= 0);
    const uint64_t from = NLines();
    CHECK(bc5_zcb0401_watch_start(fd) == (g_on ? 1 : 0));
    CHECK(bc5_zcb0401_watch_start(fd) == (g_on ? 1 : 0)); // once a session
    CHECK(Zc(zMapped) == (g_on ? 1u : 0u));
    CHECK(Poke(fd, 0x1000, 0x42)); // "the GPU" wrote into a hole
    if (g_on) {
        CHECK(WaitState(zFirstMs, kNone, 5000));
        CHECK(Poke(fd, kChunk - 1, 0x01));
        CHECK(WaitState(zChanges, 0, 5000));
        CHECK(Zc(zChangeLines) == 0); // within the 10-s gap: counted, not journaled
        const std::vector<std::string> l = Lines(from);
        CHECKW(l.size() == 2 && Has(l, "scratch watch (exp 0401 e9 zcb): t ", " s: watching the hole scratch BO (memfd ", ", 2 MiB, mapped read-only here) every 50 ms") == 1 &&
                   Has(l, "scratch watch (exp 0401 e9 zcb): t ", " s: the hole scratch BO is not all zero: 1 non-zero bytes, first at 0x1000, last at 0x1000, hash " + Hex16(Fnv2M({{0x1000, 0x42}}))) ==
                       1,
               Join(l));
    } else {
        std::this_thread::sleep_for(std::chrono::milliseconds(300));
        CHECK(Zc(zScans) == 0 && Zc(zFirstMs) == kNone);
        const std::vector<std::string> l = Lines(from);
        CHECKW(l.empty(), Join(l));
    }
    End(mode);
}

// ---- 14. a later timeout: the last 4 of 6, a taken-back run, the scratch BO dirty (mode) ------------------------------------------
static void Timeout2(const char* mode) {
    Begin("a later timeout");
    const uint64_t from = NLines();
    bc5_zcb0401_at_timeout(78, "dcb", reinterpret_cast<const void*>(static_cast<uintptr_t>(kVa1 + 0x1000)), 16, nullptr, 0);
    const std::vector<std::string> l = Lines(from);
    if (g_on) {
        CHECKW(l.size() == 7, Join(l));
        CHECK(Has(l, "at the timeout of submit #78 dcb: t ", " s: 6 take-backs so far (2 by canary hits), the last 4 below, newest first") == 1);
        CHECK(Has(l, "take-back 6 of 6, ", "by CPU writes: run 2, file 0x4000000-0x5000000 (+16.0 MiB), chunks 0x4400000; the run's VAs: 0x10004000000-0x10005000000, 0x20000000000-0x20000200000") == 1);
        CHECK(Has(l, "take-back 5 of 6, ", "chunks 0x4200000") == 1 && Has(l, "take-back 4 of 6, ", "chunks 0x4000000") == 1);
        CHECK(Has(l, "take-back 3 of 6, ", "by a canary hit: run 1, file 0x3000000-0x3400000 (+4.0 MiB), 2 chunks still skipped then; its VAs: 0x10003000000-0x10003400000") == 1);
        CHECK(Has(l, "take-back 2 of 6") == 0 && Has(l, "take-back 1 of 6") == 0);
        CHECKW(Has(l, "at the timeout of submit #78 dcb: the job's own records: the buffer 0x10003001000 +0x40; no host copy of the buffer (the completion thread keeps one with "
                      "BC5_DIRECT_TIMEOUT_PROBE only); touching a taken-back run: run 1, taken back by a canary hit ",
                   " s ago (the buffer: 0x10003001000); touching a still-skipped run: none (") == 1,
               Join(l));
        CHECKW(Has(l, "scratch watch (exp 0401 e9 zcb): at the timeout of submit #78 dcb: the hole scratch BO is DIRTY: 2 non-zero bytes, first at 0x1000, last at 0x1fffff, hash " +
                          Hex16(Fnv2M({{0x1000, 0x42}, {0x1fffff, 0x01}})) + " (the watcher saw non-zero bytes first at t ") == 1,
               Join(l));
    } else {
        CHECKW(l.empty(), Join(l));
    }
    CHECK(bc5_zcb0401_wait(0) == 1); // the test's wait stands for the device ...
    bc5_zcb0401_set_wait(nullptr, nullptr);
    CHECK(bc5_zcb0401_wait(0) == -1); // ... without it there is none
    End(mode);
}

// ---- 15. every line through the quiet filter; off and unset: e8's lines only ----------------------------------------------------
static void Quiet(const char* mode) {
    Begin("the quiet filter and e8's lines");
    const std::vector<std::string> l = Lines(0);
    for (const auto& s: l) {
        const int k = bc5_zcb0401_quiet_kind(s.c_str());
        CHECKW(k == (s.find("at the timeout") != std::string::npos ? -1 : 0), std::to_string(k) + ": " + s);
        CHECKW(s.find("exp 0401 e9 (zcb)") == 0 || s.find("(exp 0401 e9 zcb): ") != std::string::npos, s);
    }
    CHECK(Has(l, "exp 0401 e9 (zcb): ") == 4);
    const size_t later = static_cast<size_t>(Has(l, "the hole scratch BO changed")); // a watch line 10 s after the first, if the run was that slow
    if (g_on) {
        // switches 4, exclusion (pure) 4, placement 2, CPU 1, hit 2, timeout 5, hit 2, CPU 3, watch 2, timeout 7
        CHECKW(l.size() - later == 4 + 4 + 2 + 1 + 2 + 5 + 2 + 3 + 2 + 7, std::to_string(l.size()));
    } else {
        CHECKW(l.size() == 4 + 4, std::to_string(l.size())); // the four switch lines and the pure exclusion case's: nothing from the session
    }
    End(mode);
}

} // namespace zcb0401

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
    using namespace zcb0401;
    if (argc != 2 || (std::strcmp(argv[1], "on") != 0 && std::strcmp(argv[1], "off") != 0 && std::strcmp(argv[1], "unset") != 0)) {
        std::printf("zcb0401: usage: zcb0401 on | zcb0401 off | zcb0401 unset (each in a fresh directory)\n");
        return 2;
    }
    const char* mode = argv[1];
    g_on             = std::strcmp(mode, "on") == 0;
    const bool unset = std::strcmp(mode, "unset") == 0;
    set_env("BC5_DIRECT_ZERO_SKIP_EXCLUDE", g_on ? "0x5800000,0X4200000,xyz,0x123," : unset ? nullptr : "off");
    set_env("BC5_DIRECT_ZERO_SKIP_COPYBACK", g_on ? "1" : unset ? nullptr : "0");
    set_env("BC5_DIRECT_ZERO_SKIP_PROBE", g_on ? "on" : unset ? nullptr : "off");
    set_env("BC5_DIRECT_SCRATCH_WATCH", g_on ? "1" : unset ? nullptr : "0");
    std::thread([] {
        std::this_thread::sleep_for(std::chrono::seconds(60));
        std::printf("zcb0401: FAIL watchdog: case \"%s\" still running after 60 s\n", g_case.load());
        std::fflush(stdout);
        std::_Exit(3);
    }).detach();
    g_direct = Memfd("zcb0401-direct", kFileSize);
    char cwd[4096] = {};
    if (g_direct < 0 || getcwd(cwd, sizeof(cwd)) == nullptr) {
        std::printf("zcb0401: FAIL no memfd for the direct memory, or no current directory\n");
        return 2;
    }
    const std::string list = std::string(cwd) + "/zcb0401-list.txt"; // the zero skip, on in every mode: the test's list
    FILE*             f    = std::fopen(list.c_str(), "w");
    if (f == nullptr || std::fputs(kList, f) < 0 || std::fclose(f) != 0) {
        std::printf("zcb0401: FAIL cannot write %s\n", list.c_str());
        return 2;
    }
    set_env("BC5_DIRECT_ZERO_SKIP", list.c_str());
    bc5_zcb0401_capture(1);

    Switches(mode);
    Parse();
    Exclude();
    Summary();
    WatchRule();
    CopyPure();
    Placement(mode);
    CpuWrite(mode);
    Hit0(mode);
    Timeout1(mode);
    Hit1(mode);
    CpuWrites2(mode);
    Watch(mode);
    Timeout2(mode);
    Quiet(mode);

    std::fflush(stderr);
    std::printf("zcb0401: %s %d of %d%s\n", mode, g_pass, g_total, g_pass == g_total ? "; end" : "");
    std::fflush(stdout);
    std::_Exit(g_pass == g_total ? 0 : 1); // the unit's canary and scratch watchers keep running: no static destructors under them
}
