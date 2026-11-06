// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0401 series e10, tag m10: the CPU test of mkm100401.py's src/libs/bc5LleAgc.cpp (m100401-notes.md), the
// switches BC5_DIRECT_PROT_CENSUS, BC5_DIRECT_JOURNAL_DONTNEED and BC5_DIRECT_AMM_NULL_BO. It calls the unit through its seams
// (bc5_m10_*, and cap's bc5_cap0401_* for the journal and its quiet filter):
//   - the switches as the unit reads them, their parse and their lines;
//   - the census: its schedule, its groups, overlaps, classes and totals on ranges and BOs of the test's own (checked against
//     a reference written out here), the 400-line bound, the forced chunks on a memfd of the test's own (data in some chunks,
//     holes in others; the real SEEK_DATA), and the real tick: the census thread, the device lock, a census left out;
//   - the dontneed arithmetic, then the real step (fstat, posix_fadvise, sync_file_range) on a file of the test's own, then
//     the real journal end to end: the test gives it a directory of its own, writes 17 MB through journal() and reads the file
//     back; then it runs itself again (M100401_REEXEC) in the other journal mode ("min" or not) with BC5_DIRECT_JOURNAL_QUIET=1,
//     so both of the journal's write paths are taken;
//   - the AMM window's decision with a recorded fake instead of a device: which call, the fallback, the sysfs reads, the
//     held lines; the real sysfs reader on a file that is not there.
// No game, no GPU, no window, no sound device, no network: the direct path is never opened (g_dev stays empty), nothing is
// submitted anywhere. Every new journal line is checked against the quiet filter (cap's bc5_cap0401_quiet_kind).
// Modes. "on" and "off" take the three switches from the environment as the box sets them (on: each on; off: each =0 or
// unset) and refuse a mismatch (rc 2); the others set them here: unset (all unset), empty (all "": on Windows that is unset),
// junk (CENSUS=yes, DONTNEED=yes, NULL_BO=Rw: read-only), rw (1, 1, rw). The checks follow the values the test reads itself.
// Output: one line per case, then "m100401: <mode> N of N; end" (from the second run, with the first run's counts); without
// "; end" something failed. Exit 0 only after the end line. A watchdog ends a hang after 60 s with a FAIL line (exit 3). No
// argument or an unknown one: usage, exit 2. Run each mode in a fresh directory (it writes ./m100401-* there and removes them).
// Build: build0401.py ... src/libs/bc5LleAgc.cpp=<out>/src/libs/bc5LleAgc.cpp --gate m100401.cpp <dir>/m100401 --like
//        src/libs/bc5LleAgc.cpp (linked with every emulator object but main.cpp.o), -std=c++20 -Wall -Wextra -Werror.
// usage: m100401 on | off | unset | empty | junk | rw

#if defined(_WIN32) && !defined(_CRT_SECURE_NO_WARNINGS)
#define _CRT_SECURE_NO_WARNINGS // the laptop's stand-in build: the Windows CRT marks fopen deprecated
#endif
#include <fcntl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cinttypes>
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <map>
#include <sstream>
#include <string>
#include <thread>
#include <tuple>
#include <vector>

// The seams of mkm100401.py's unit (always compiled in, never called by the emulator), and cap's journal seams.
extern "C" int      bc5_m10_parse(const char* e);
extern "C" int      bc5_m10_null_parse(const char* e);
extern "C" void     bc5_m10_switches(int* out);
extern "C" void     bc5_m10_switch_line(int which, int mode, const char* e, char* out, uint32_t cap);
extern "C" void     bc5_m10_consts(uint64_t* out);
extern "C" void     bc5_m10_capture(int on);
extern "C" uint64_t bc5_m10_lines(uint64_t from, char* out, uint64_t cap);
extern "C" double   bc5_m10_next(double t);
extern "C" int      bc5_m10_due(double next, double t);
extern "C" void     bc5_m10_start(int mem_line);
extern "C" void     bc5_m10_tick(double t);
extern "C" void     bc5_m10_census_state(uint64_t* out);
extern "C" void     bc5_m10_dev_lock(int take);
extern "C" uint64_t bc5_m10_overlap(const uint64_t* off, const uint64_t* size, uint32_t n, uint64_t lo, uint64_t hi);
extern "C" int      bc5_m10_class(int type, int eager, int lazy);
extern "C" int      bc5_m10_gpu_class(int prot);
extern "C" uint64_t bc5_m10_census_lines(const uint64_t* start, const uint64_t* size, const uint64_t* offset, const int* type, const int* prot, const char* const* name,
                                         uint32_t n, const uint64_t* bo_off0, const uint64_t* bo_size0, uint32_t nb0, const uint64_t* bo_off1, const uint64_t* bo_size1,
                                         uint32_t nb1, double t, char* out, uint64_t cap);
extern "C" void     bc5_m10_forced(int fd, const uint64_t* forced, uint32_t nf, const uint64_t* eager_lo, const uint64_t* eager_hi, uint32_t ne, const uint64_t* bo_off,
                                   const uint64_t* bo_size, uint32_t nb, uint64_t* out, char* line, uint32_t cap);
extern "C" void     bc5_m10_drop_plan(uint64_t started, uint64_t dropped, uint64_t end, uint64_t* out);
extern "C" int      bc5_m10_drop_step(int fd, uint64_t* st);
extern "C" void     bc5_m10_drop_state(uint64_t* st);
extern "C" int      bc5_m10_drop_tell(uint64_t told_syncs, uint64_t told_errs, uint64_t syncs, uint64_t errs);
extern "C" void     bc5_m10_drop_line(uint64_t syncs, uint64_t drops, uint64_t started, uint64_t dropped, double t, char* out, uint32_t cap);
extern "C" int      bc5_m10_amm(int mode, int null_rc, int prt_ok, char* calls, uint32_t cap);
extern "C" void     bc5_m10_amm_window(const char* when, int hold, int null_rc, int prt_ok, const int64_t* sysfs, char* calls, uint32_t cap);
extern "C" uint64_t bc5_m10_held();
extern "C" void     bc5_m10_amm_pending();
extern "C" int      bc5_m10_null_call(int has_method, int ok, int writable, int* got_writable);
extern "C" int      bc5_m10_backend_has_null();
extern "C" int64_t  bc5_m10_sysfs(const char* leaf);
extern "C" int      bc5_cap0401_quiet_kind(const char* s, uint64_t n, int complete);
extern "C" int      bc5_cap0401_journal_open(const char* dir);
extern "C" void     bc5_cap0401_journal(const char* text);
extern "C" void     bc5_cap0401_journal_flush();
extern "C" int      bc5_cap0401_journal_min();

namespace m100401 {

static int                      g_pass = 0, g_total = 0, g_case_pass = 0, g_case_total = 0;
static std::atomic<const char*> g_case {"init"};

static void Check(bool ok, const char* what, int line, const std::string& why = "") {
    g_total++;
    g_case_total++;
    if (ok) {
        g_pass++;
        g_case_pass++;
    } else {
        std::printf("m100401: FAIL %s (line %d): %s%s%s\n", g_case.load(), line, what, why.empty() ? "" : ": ", why.c_str());
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
    std::printf("m100401: case %s (%s): %d of %d\n", g_case.load(), how, g_case_pass, g_case_total);
    std::fflush(stdout);
}
static std::string Fmt(const char* fmt, ...) __attribute__((format(printf, 1, 2)));
static std::string Fmt(const char* fmt, ...) {
    char    t[2048];
    va_list ap;
    va_start(ap, fmt);
    const int n = std::vsnprintf(t, sizeof(t), fmt, ap);
    va_end(ap);
    return n < 0 ? std::string() : std::string(t, std::min(static_cast<size_t>(n), sizeof(t) - 1));
}
static unsigned long long U(uint64_t v) { return static_cast<unsigned long long>(v); }
static int quiet_kind(const std::string& line) { // the journal's quiet filter on a whole line (with its newline)
    return bc5_cap0401_quiet_kind(line.c_str(), line.size(), 1);
}
static std::vector<std::string> SplitLines(const std::string& s) { // each with its newline
    std::vector<std::string> v;
    size_t                   i = 0;
    while (i < s.size()) {
        const size_t j = s.find('\n', i);
        if (j == std::string::npos) {
            v.push_back(s.substr(i));
            break;
        }
        v.push_back(s.substr(i, j + 1 - i));
        i = j + 1;
    }
    return v;
}
static std::vector<char> g_buf(4u << 20u);
static uint64_t Captured() { // how many lines the unit captured so far
    return bc5_m10_lines(~0ull >> 1u, g_buf.data(), g_buf.size());
}
static std::vector<std::string> LinesFrom(uint64_t from) {
    bc5_m10_lines(from, g_buf.data(), g_buf.size());
    return SplitLines(std::string(g_buf.data()));
}
static bool StartsWith(const std::string& s, const std::string& p) { return s.compare(0, p.size(), p) == 0; }

// ---- the switches the test expects, read independently of the unit ------------------------------------------------------
static bool EnvOn(const char* e) { return e != nullptr && e[0] != 0 && !(e[0] == '0' && e[1] == 0); } // F767
struct Want {
    int         census = 0, dontneed = 0, null = 0;
    const char* census_e = nullptr;
    const char* dontneed_e = nullptr;
    const char* null_e = nullptr;
};
static Want WantFromEnv() {
    Want w;
    w.census_e   = std::getenv("BC5_DIRECT_PROT_CENSUS");
    w.dontneed_e = std::getenv("BC5_DIRECT_JOURNAL_DONTNEED");
    w.null_e     = std::getenv("BC5_DIRECT_AMM_NULL_BO");
    w.census     = EnvOn(w.census_e) ? 1 : 0;
    w.dontneed   = EnvOn(w.dontneed_e) ? 1 : 0;
    w.null       = !EnvOn(w.null_e) ? 0 : std::strcmp(w.null_e, "rw") == 0 ? 2 : 1;
    return w;
}
static const char* OffHow(const char* e) { return e == nullptr ? "unset" : e[0] == 0 ? "empty" : "=0"; }
// The switch lines, written out again here (not built from the unit's code).
static std::string WantLine(int which, int mode, const char* e) {
    const std::string v   = e != nullptr ? e : "";
    const bool        one = v == "1";
    if (which == 0 && mode != 0)
        return "exp 0401 e10 (m10): prot census on (BC5_DIRECT_PROT_CENSUS=" + v + (one ? "" : ", any value but unset, empty or 0 is on") +
               "): the guest ranges by type, name and protection with the bytes imported for them, and the pin of the forced chunks, at journal time 120, 300 and 600 s, "
               "then every 600 s\n";
    if (which == 0) return std::string("exp 0401 e10 (m10): prot census off (BC5_DIRECT_PROT_CENSUS ") + OffHow(e) + "): as e9\n";
    if (which == 1 && mode != 0)
        return "exp 0401 e10 (m10): journal dontneed on (BC5_DIRECT_JOURNAL_DONTNEED=" + v + (one ? "" : ", any value but unset, empty or 0 is on") +
               "): each time the journal has grown 8 MiB, the writeback of the new part is started (sync_file_range) and the part started the time before leaves the page "
               "cache (posix_fadvise DONTNEED); exp 0330's switch\n";
    if (which == 1) return std::string("exp 0401 e10 (m10): journal dontneed off (BC5_DIRECT_JOURNAL_DONTNEED ") + OffHow(e) + "): as e9\n";
    if (mode == 2)
        return "exp 0401 e10 (m10): amm null bo on, writable (BC5_DIRECT_AMM_NULL_BO=rw): with BC5_DIRECT_AMM_PRT set, the AMM window 0x8000000000+0x1000000000 as "
               "writable null pages (map_null_window), its PRT window if that fails\n";
    if (mode == 1)
        return "exp 0401 e10 (m10): amm null bo on, read-only (BC5_DIRECT_AMM_NULL_BO=" + v + (one ? "" : ", any value but unset, empty, 0 or rw is read-only") +
               "): with BC5_DIRECT_AMM_PRT set, the AMM window 0x8000000000+0x1000000000 as read-only null pages (map_null_window), its PRT window if that fails\n";
    return std::string("exp 0401 e10 (m10): amm null bo off (BC5_DIRECT_AMM_NULL_BO ") + OffHow(e) + "): with BC5_DIRECT_AMM_PRT set, the AMM window as e9's PRT window\n";
}

// ---- 1. the switches as the unit reads them (mode) ------------------------------------------------------------------------
static void Switches(const Want& w) {
    Begin("the switches");
    int a[3] = {-1, -1, -1}, b[3] = {-1, -1, -1};
    bc5_m10_switches(a);
    bc5_m10_switches(b); // read once
    CHECKW(a[0] == w.census && a[1] == w.dontneed && a[2] == w.null, Fmt("%d %d %d", a[0], a[1], a[2]));
    CHECK(a[0] == b[0] && a[1] == b[1] && a[2] == b[2]);
    uint64_t c[6] = {};
    bc5_m10_consts(c);
    CHECK(c[0] == (8ull << 20u) && c[1] == 64 && c[2] == 400 && c[3] == 0x8000000000ull && c[4] == 0x1000000000ull && c[5] == (2ull << 20u));
    End(Fmt("census %d, dontneed %d, null bo %d", w.census, w.dontneed, w.null).c_str());
}

// ---- 2. the parse (pure) ------------------------------------------------------------------------------------------------------
static void Parse() {
    Begin("the parse");
    for (const char* e: {static_cast<const char*>(nullptr), "", "0"}) {
        CHECK(bc5_m10_parse(e) == 0);
        CHECK(bc5_m10_null_parse(e) == 0);
    }
    for (const char* e: {"1", "yes", "00", " 0", "0 ", "-0", "off", "rw", "false"}) CHECKW(bc5_m10_parse(e) == 1, e);
    CHECK(bc5_m10_null_parse("rw") == 2);
    for (const char* e: {"1", "RW", "rw ", " rw", "ro", "yes", "rw1", "Rw"}) CHECKW(bc5_m10_null_parse(e) == 1, e);
    End("pure");
}

// ---- 3. the switch lines and the quiet filter (pure) ---------------------------------------------------------------------------
static void SwitchLines() {
    Begin("the switch lines");
    char t[600];
    CHECK(quiet_kind("timing: #5 done at t 1.0 s, 0.1 ms after the sync and hints\n") == 2); // the filter is live
    struct Row {
        int         which, mode;
        const char* e;
    };
    const Row rows[] = {{0, 1, "1"}, {0, 1, "yes"}, {0, 0, nullptr}, {0, 0, ""}, {0, 0, "0"}, {1, 1, "1"}, {1, 1, "on"}, {1, 0, nullptr}, {1, 0, ""}, {1, 0, "0"},
                        {2, 1, "1"}, {2, 1, "Rw"}, {2, 2, "rw"}, {2, 0, nullptr}, {2, 0, ""}, {2, 0, "0"}};
    for (const Row& r: rows) {
        bc5_m10_switch_line(r.which, r.mode, r.e, t, sizeof(t));
        const std::string want = WantLine(r.which, r.mode, r.e);
        CHECKW(std::string(t) == want, std::string(t) + " | want " + want);
        CHECKW(quiet_kind(t) == 0, t);
    }
    End("pure");
}

// ---- 4. the census's schedule (pure) -----------------------------------------------------------------------------------------
static void Schedule() {
    Begin("the census schedule");
    const double ts[]   = {0.0, 119.9, 120.0, 299.0, 300.0, 599.9, 600.0, 1199.0, 1200.0, 5000.0, 5400.0};
    const double next[] = {120.0, 120.0, 300.0, 300.0, 600.0, 600.0, 1200.0, 1200.0, 1800.0, 5400.0, 6000.0};
    for (size_t k = 0; k < sizeof(ts) / sizeof(ts[0]); k++) CHECKW(bc5_m10_next(ts[k]) == next[k], Fmt("%.1f -> %.1f", ts[k], bc5_m10_next(ts[k])));
    CHECK(bc5_m10_due(120.0, 119.999) == 0 && bc5_m10_due(120.0, 120.0) == 1 && bc5_m10_due(300.0, 5000.0) == 1);
    End("pure");
}

// ---- 5. the census's groups, overlaps, classes, totals and lines on ranges of the test's own (pure) ---------------------------
// The test sets BC5_DIRECT_EAGER_NAMES and BC5_DIRECT_LAZY_NAMES before the unit reads them (main): the unit's own reading.
static const char* const kEagerNames = "RenderGpuWcLarge,CommitIABufferAllocator,KernelEager,Both";
static const char* const kLazyNames  = "orbis_user_malloc,KernelLazy,stack_main,Both";
struct TRange {
    uint64_t    start, size, offset;
    int         type, prot;
    std::string name;
};
struct TBo {
    uint64_t off, size;
};
static bool InList(const char* list, const std::string& n) {
    std::stringstream s(list);
    std::string       x;
    while (std::getline(s, x, ','))
        if (!n.empty() && x == n) return true;
    return false;
}
static uint64_t RefOverlap(const std::vector<TBo>& bos, uint64_t lo, uint64_t hi) { // byte by run, every BO looked at
    uint64_t n = 0;
    for (const TBo& b: bos) {
        const uint64_t a = b.off > lo ? b.off : lo, e = b.off + b.size < hi ? b.off + b.size : hi;
        if (a < e) n += e - a;
    }
    return n;
}
static const char* RefType(int t) {
    static const char* const n[6] = {"direct", "flexible", "pooled", "stack", "code", "runtime"};
    return t >= 0 && t < 6 ? n[t] : "other";
}
static std::string RefClass(int type, const std::string& name) {
    if (!(type == 0 || (type >= 3 && type <= 5))) return "no view";
    if (InList(kEagerNames, name)) return "eager name";
    if (type == 3) return "lazy stacks";
    return InList(kLazyNames, name) ? "lazy name" : "data";
}
static std::string RefClean(const std::string& s) {
    std::string o;
    for (const char c: s) {
        if (o.size() == 64) break;
        o.push_back(c >= 0x20 && c <= 0x7e && c != '"' ? c : '?');
    }
    return o;
}
static std::string RefProt(int p) {
    std::string s = "cpu ";
    s += (p & 1) != 0 ? 'r' : '-';
    s += (p & 2) != 0 ? 'w' : '-';
    s += (p & 4) != 0 ? 'x' : '-';
    s += " gpu ";
    s += (p & 0x10) != 0 ? 'r' : '-';
    s += (p & 0x20) != 0 ? 'w' : '-';
    return s;
}
static const std::string kP = "prot census (exp 0401 e10 m10): ";
static std::string ForcedZeroLine(const char* label, double t) {
    return kP + Fmt("t %.0f s: forced %s: 0 chunks of 2 MiB the hints and learned windows asked for: 0 under an eager view, 0 more hold data, 0 neither (the pin the "
                    "windows alone cause), 0 of those imported (0.0 MiB); 0 SEEK_DATA, 0.000 ms\n",
                    t, label);
}
// The reference lines of one census of these ranges (the unit's order: most imported first, then most bytes, ties in (type,
// name, protection) order; at most 400 group lines).
static std::vector<std::string> RefCensus(const std::vector<TRange>& rs, const std::vector<TBo>& d, const std::vector<TBo>& p, double t) {
    struct G {
        int         type = 0, prot = 0;
        std::string name;
        uint64_t    views = 0, bytes = 0, imported = 0;
    };
    std::map<std::tuple<int, std::string, int>, G> m;
    uint64_t                                         tv[4] = {}, tb[4] = {}, ti[4] = {};
    for (const TRange& r: rs) {
        uint64_t imp = 0;
        if (r.type == 0) imp = RefOverlap(d, r.offset, r.offset + r.size);
        else if (r.type >= 3 && r.type <= 5) imp = RefOverlap(p, r.start, r.start + r.size);
        G& g   = m[std::make_tuple(r.type, r.name, r.prot)];
        g.type = r.type;
        g.prot = r.prot;
        g.name = r.name;
        g.views++;
        g.bytes += r.size;
        g.imported += imp;
        const int k = ((r.prot & 0x10) != 0 ? 1 : 0) + ((r.prot & 0x20) != 0 ? 2 : 0);
        tv[k]++;
        tb[k] += r.size;
        ti[k] += imp;
    }
    std::vector<G> v;
    for (auto& kv: m) v.push_back(kv.second);
    std::stable_sort(v.begin(), v.end(), [](const G& a, const G& b) { return a.imported != b.imported ? a.imported > b.imported : a.bytes > b.bytes; });
    uint64_t db = 0, pb = 0;
    for (const TBo& b: d) db += b.size;
    for (const TBo& b: p) pb += b.size;
    std::vector<std::string> out;
    out.push_back(kP + Fmt("t %.0f s: census 1: %zu guest ranges in %zu groups of type, name and protection (the title's bits as it gave them); direct memfd %zu BOs, %.1f MiB "
                           "imported; private memfd %zu BOs, %.1f MiB imported; the device lock waited 0.000 ms, held 0.000 ms; a page under two views counts twice\n",
                           t, rs.size(), v.size(), d.size(), static_cast<double>(db) / 1048576.0, p.size(), static_cast<double>(pb) / 1048576.0));
    uint64_t mv = 0, mb = 0, mi = 0;
    for (size_t i = 0; i < v.size(); i++) {
        if (i >= 400) {
            mv += v[i].views;
            mb += v[i].bytes;
            mi += v[i].imported;
            continue;
        }
        out.push_back(kP + Fmt("t %.0f s: %s \"%s\" prot 0x%x (%s): %llu views, %llu bytes, %llu imported; %s\n", t, RefType(v[i].type), RefClean(v[i].name).c_str(),
                               static_cast<unsigned>(v[i].prot), RefProt(v[i].prot).c_str(), U(v[i].views), U(v[i].bytes), U(v[i].imported),
                               RefClass(v[i].type, v[i].name).c_str()));
    }
    if (v.size() > 400) out.push_back(kP + Fmt("t %.0f s: ... %zu more groups not listed: %llu views, %llu bytes, %llu imported\n", t, v.size() - 400, U(mv), U(mb), U(mi)));
    static const char* const gn[4] = {"no gpu bit", "gpu read only", "gpu write only", "gpu read and write"};
    for (int k = 0; k < 4; k++)
        out.push_back(kP + Fmt("t %.0f s: total, %s: %llu views, %llu bytes (%.1f MiB), %llu imported (%.1f MiB)\n", t, gn[k], U(tv[k]), U(tb[k]), static_cast<double>(tb[k]) / 1048576.0,
                               U(ti[k]), static_cast<double>(ti[k]) / 1048576.0));
    out.push_back(ForcedZeroLine("direct", t));
    out.push_back(ForcedZeroLine("private", t));
    return out;
}
static std::vector<std::string> UnitCensus(const std::vector<TRange>& rs, const std::vector<TBo>& d, const std::vector<TBo>& p, double t, uint64_t* n_lines) {
    std::vector<uint64_t>    st, sz, of, bo0, bs0, bo1, bs1;
    std::vector<int>         ty, pr;
    std::vector<const char*> nm;
    for (const TRange& r: rs) {
        st.push_back(r.start);
        sz.push_back(r.size);
        of.push_back(r.offset);
        ty.push_back(r.type);
        pr.push_back(r.prot);
        nm.push_back(r.name.c_str());
    }
    for (const TBo& b: d) bo0.push_back(b.off), bs0.push_back(b.size);
    for (const TBo& b: p) bo1.push_back(b.off), bs1.push_back(b.size);
    *n_lines = bc5_m10_census_lines(st.data(), sz.data(), of.data(), ty.data(), pr.data(), nm.data(), static_cast<uint32_t>(rs.size()), bo0.data(), bs0.data(),
                                    static_cast<uint32_t>(d.size()), bo1.data(), bs1.data(), static_cast<uint32_t>(p.size()), t, g_buf.data(), g_buf.size());
    return SplitLines(std::string(g_buf.data()));
}
static bool SameLines(const std::vector<std::string>& got, const std::vector<std::string>& want) {
    for (size_t i = 0; i < got.size() || i < want.size(); i++) {
        const std::string g = i < got.size() ? got[i] : "(none)\n", w = i < want.size() ? want[i] : "(none)\n";
        if (g != w) {
            std::printf("m100401:   line %zu differs:\n    got  %s    want %s", i, g.c_str(), w.c_str());
            return false;
        }
    }
    return true;
}
static void CensusPure() {
    Begin("the census's groups and lines");
    const uint64_t      M = 1ull << 20u;
    std::vector<TRange> rs = {
        {0x1140000000ull, 0x40000000ull, 0x100000000ull, 0, 0x33, "RenderGpuWcLarge"}, // eager; a third imported
        {0x1180000000ull, 0x20000000ull, 0x140000000ull, 0, 0x33, "CommitIABufferAllocator"},
        {0x11a0000000ull, 0x20000000ull, 0x160000000ull, 0, 0x03, "orbis_user_malloc"}, // lazy, no GPU bit, a BO inside it
        {0x8000000000ull, 0x1000000ull, 0x200000000ull, 0, 0x13, "AMM"},                // two views, one group
        {0x8001000000ull, 0x1000000ull, 0x201000000ull, 0, 0x13, "AMM"},
        {0x8002000000ull, 0x1000000ull, 0x202000000ull, 0, 0x23, "AMM"},                // another protection: its own group
        {0x9000000000ull, 0x10000000ull, 0x100000000ull, 0, 0x33, "alias"},             // an alias of RenderGpuWcLarge's pages
        {0x200000000ull, 0x4000000ull, 0, 1, 0x33, "flex"},                             // flexible: no view (offset 0 and its address both hit BOs)
        {0x210000000ull, 0x200000ull, 0, 2, 0x10, "pool"},                              // pooled: no view
        {0x7ff000000ull, 0x100000ull, 0, 3, 0x03, "stack_main"},                        // private, by address
        {0x800000000ull, 0x2000000ull, 0, 4, 0x05, "eboot.bin"},
        {0x900000000ull, 0x200000ull, 0, 5, 0x33, "KernelEager"},
        {0x900200000ull, 0x200000ull, 0, 5, 0x01, "KernelLazy"},
        {0x9100000000ull, 0x4000ull, 0x300000000ull, 0, 0x33, ""},
        {0x9100004000ull, 0x4000ull, 0x300004000ull, 0, 0x33, "x\"y\nz"},
        {0x9200000000ull, 0x4000ull, 0x300008000ull, 0, 0x33, "Both"}, // eager and lazy: eager, as the mapper reads it
    };
    const std::vector<TBo> d = {{0, 0x200000}, {0x100000000ull, 0x30000000ull}, {0x150000000ull, 0x8000000ull}, {0x16f000000ull, 0x2000000ull}, {0x200000000ull, 0x800000ull}};
    const std::vector<TBo> p = {{0x200000000ull, 0x400000ull}, {0x7ff000000ull, 0x80000ull}, {0x800000000ull, 0x1000000ull}};
    // the small census: every group listed
    uint64_t       n     = 0;
    auto           got   = UnitCensus(rs, d, p, 120.0, &n);
    const auto     want  = RefCensus(rs, d, p, 120.0);
    CHECKW(n == 1 + 15 + 4 + 2 && got.size() == n, std::to_string(n));
    CHECK(SameLines(got, want));
    // the reference's own numbers, by hand
    const std::string h = kP + "t 120 s: ";
    const auto has = [&got](const std::string& l) { return std::count(got.begin(), got.end(), l) == 1; };
    CHECK(has(h + "direct \"RenderGpuWcLarge\" prot 0x33 (cpu rw- gpu rw): 1 views, 1073741824 bytes, 805306368 imported; eager name\n"));
    CHECK(has(h + "direct \"orbis_user_malloc\" prot 0x3 (cpu rw- gpu --): 1 views, 536870912 bytes, 33554432 imported; lazy name\n"));
    CHECK(has(h + "direct \"AMM\" prot 0x13 (cpu rw- gpu r-): 2 views, 33554432 bytes, 8388608 imported; data\n"));
    CHECK(has(h + "direct \"AMM\" prot 0x23 (cpu rw- gpu -w): 1 views, 16777216 bytes, 0 imported; data\n"));
    CHECK(has(h + "direct \"alias\" prot 0x33 (cpu rw- gpu rw): 1 views, 268435456 bytes, 268435456 imported; data\n"));
    CHECK(has(h + "flexible \"flex\" prot 0x33 (cpu rw- gpu rw): 1 views, 67108864 bytes, 0 imported; no view\n"));
    CHECK(has(h + "pooled \"pool\" prot 0x10 (cpu --- gpu r-): 1 views, 2097152 bytes, 0 imported; no view\n"));
    CHECK(has(h + "stack \"stack_main\" prot 0x3 (cpu rw- gpu --): 1 views, 1048576 bytes, 524288 imported; lazy stacks\n"));
    CHECK(has(h + "code \"eboot.bin\" prot 0x5 (cpu r-x gpu --): 1 views, 33554432 bytes, 16777216 imported; data\n"));
    CHECK(has(h + "runtime \"KernelEager\" prot 0x33 (cpu rw- gpu rw): 1 views, 2097152 bytes, 0 imported; eager name\n"));
    CHECK(has(h + "runtime \"KernelLazy\" prot 0x1 (cpu r-- gpu --): 1 views, 2097152 bytes, 0 imported; lazy name\n"));
    CHECK(has(h + "direct \"x?y?z\" prot 0x33 (cpu rw- gpu rw): 1 views, 16384 bytes, 0 imported; data\n"));
    CHECK(has(h + "direct \"Both\" prot 0x33 (cpu rw- gpu rw): 1 views, 16384 bytes, 0 imported; eager name\n"));
    CHECK(got.size() > 2 && StartsWith(got[1], h + "direct \"RenderGpuWcLarge\"") && StartsWith(got[2], h + "direct \"alias\"")); // most imported first
    CHECK(has(h + "total, no gpu bit: 4 views, 573571072 bytes (547.0 MiB), 50855936 imported (48.5 MiB)\n"));
    CHECK(has(h + "total, gpu read only: 3 views, 35651584 bytes (34.0 MiB), 8388608 imported (8.0 MiB)\n"));
    CHECK(has(h + "total, gpu write only: 1 views, 16777216 bytes (16.0 MiB), 0 imported (0.0 MiB)\n"));
    for (const auto& l: got) CHECKW(quiet_kind(l) == 0, l);
    // 410 more groups: 400 group lines, then one for the rest
    std::vector<std::string> names;
    for (uint32_t k = 0; k < 410; k++) names.push_back(Fmt("g%03u", k));
    for (uint32_t k = 0; k < 410; k++) rs.push_back({0xa000000000ull + k * M, 0x1000ull * (k + 1), 0x400000000ull + k * M, 0, 0x33, names[k]});
    got                  = UnitCensus(rs, d, p, 600.0, &n);
    const auto want_big  = RefCensus(rs, d, p, 600.0);
    CHECKW(n == 1 + 400 + 1 + 4 + 2 && got.size() == n, std::to_string(n));
    CHECK(SameLines(got, want_big));
    CHECK(got.size() > 401 && got[401] == kP + "t 600 s: ... 25 more groups not listed: 25 views, 1085440 bytes, 0 imported\n");
    for (const auto& l: got) CHECKW(quiet_kind(l) == 0, l);
    // the pure helpers
    const uint64_t bo[] = {0x1000, 0x5000, 0x9000}, bs[] = {0x1000, 0x2000, 0x1000};
    CHECK(bc5_m10_overlap(bo, bs, 3, 0, 0x10000) == 0x4000 && bc5_m10_overlap(bo, bs, 3, 0x1800, 0x5800) == 0x1000 && bc5_m10_overlap(bo, bs, 3, 0x6000, 0x6000) == 0);
    CHECK(bc5_m10_overlap(bo, bs, 3, 0x6fff, 0x9001) == 0x2 && bc5_m10_overlap(bo, bs, 0, 0, ~0ull) == 0 && bc5_m10_overlap(bo, bs, 3, 0x2000, 0x5000) == 0);
    CHECK(bc5_m10_class(0, 1, 1) == 0 && bc5_m10_class(0, 0, 1) == 1 && bc5_m10_class(3, 0, 0) == 2 && bc5_m10_class(3, 1, 0) == 0 && bc5_m10_class(4, 0, 0) == 3);
    CHECK(bc5_m10_class(1, 1, 1) == 4 && bc5_m10_class(2, 0, 0) == 4 && bc5_m10_class(5, 0, 1) == 1 && bc5_m10_class(6, 0, 0) == 4);
    CHECK(bc5_m10_gpu_class(0x07) == 0 && bc5_m10_gpu_class(0x10) == 1 && bc5_m10_gpu_class(0x23) == 2 && bc5_m10_gpu_class(0x33) == 3 && bc5_m10_gpu_class(0xcf) == 0);
    End("pure");
}

// ---- 6. the forced chunks on a memfd of the test's own (pure; the real SEEK_DATA) ------------------------------------------------
static int Memfd(const char* name, uint64_t size) {
    const int fd = memfd_create(name, 0);
    if (fd < 0) return -1;
    if (ftruncate(fd, static_cast<off_t>(size)) != 0) {
        close(fd);
        return -1;
    }
    return fd;
}
static bool Poke(int fd, uint64_t off) {
    const unsigned char v = 0x5a;
    return pwrite(fd, &v, 1, static_cast<off_t>(off)) == 1;
}
static void Forced() {
    Begin("the forced chunks");
    const uint64_t M  = 1ull << 20u;
    const int      fd = Memfd("m100401-forced", 32 * M);
    CHECK(fd >= 0);
    if (fd < 0) {
        End("no memfd");
        return;
    }
    // data in chunk 1 (at its start + 5), chunk 4 (its last byte), chunk 5 (its first byte), chunk 9 (its middle)
    CHECK(Poke(fd, 2 * M + 5) && Poke(fd, 10 * M - 1) && Poke(fd, 10 * M) && Poke(fd, 19 * M));
    const uint64_t forced[]  = {12 * 2 * M, 0, 2 * M, 4 * M, 6 * M, 8 * M, 10 * M, 12 * M, 14 * M, 18 * M, 20 * M}; // chunks 12, 0-7, 9, 10 (unsorted)
    const uint64_t eager_lo[] = {20 * M, 21 * M, 6 * M + 4096, 11 * M, 14 * M}, eager_hi[] = {22 * M, 24 * M, 8 * M, 12 * M, 14 * M}; // chunks 3, 5, 10; an empty one
    const uint64_t bo_off[]   = {0, 8 * M, 15 * M, 24 * M}, bo_size[] = {4 * M, 2 * M, 64 * 1024, 2 * M};
    uint64_t       out[7]     = {};
    char           line[600];
    bc5_m10_forced(fd, forced, 11, eager_lo, eager_hi, 5, bo_off, bo_size, 4, out, line, sizeof(line));
    // eager: 3, 5, 10; data (one SEEK_DATA each, 8 in all): 1, 4, 9; neither: 0, 2, 6, 7, 12; of those imported: 0 (the BO at 0),
    // 7 (64 KiB of it), 12
    CHECKW(out[0] == 11 && out[1] == 3 && out[2] == 3 && out[3] == 5 && out[4] == 3 && out[5] == 4 * M + 64 * 1024 && out[6] == 8,
           Fmt("%llu %llu %llu %llu %llu %llu %llu", U(out[0]), U(out[1]), U(out[2]), U(out[3]), U(out[4]), U(out[5]), U(out[6])));
    const std::string want = kP + "t 120 s: forced direct: 11 chunks of 2 MiB the hints and learned windows asked for: 3 under an eager view, 3 more hold data, 5 neither "
                                  "(the pin the windows alone cause), 3 of those imported (4.1 MiB); 8 SEEK_DATA, 0.000 ms\n";
    CHECKW(std::string(line) == want, line);
    CHECK(quiet_kind(line) == 0);
    // nothing forced; no eager view and no data: every chunk neither
    bc5_m10_forced(fd, forced, 0, eager_lo, eager_hi, 5, bo_off, bo_size, 4, out, line, sizeof(line));
    CHECK(out[0] == 0 && out[6] == 0 && std::string(line) == ForcedZeroLine("direct", 120.0));
    const uint64_t far[] = {28 * M, 30 * M};
    bc5_m10_forced(fd, far, 2, eager_lo, eager_hi, 0, bo_off, bo_size, 0, out, line, sizeof(line));
    CHECK(out[0] == 2 && out[1] == 0 && out[2] == 0 && out[3] == 2 && out[4] == 0 && out[6] == 2);
    close(fd);
    End("pure");
}

// ---- 7. the dontneed arithmetic (pure) ----------------------------------------------------------------------------------------
static void DropPlan() {
    Begin("the dontneed plan");
    const uint64_t M = 1ull << 20u;
    struct Row {
        uint64_t started, dropped, end, act, dlo, dlen, slo, slen;
    };
    const Row rows[] = {
        {0, 0, 8 * M - 1, 0, 0, 0, 0, 0},           {0, 0, 8 * M, 1, 0, 0, 0, 8 * M},              {8 * M, 0, 16 * M - 1, 0, 0, 0, 0, 0},
        {8 * M, 0, 17 * M, 1, 0, 8 * M, 8 * M, 9 * M}, {17 * M, 8 * M, 25 * M, 1, 8 * M, 9 * M, 17 * M, 8 * M}, {17 * M, 17 * M, 30 * M, 1, 0, 0, 17 * M, 13 * M},
        {17 * M, 8 * M, 1 * M, 0, 0, 0, 0, 0},       {17 * M, 8 * M, 17 * M, 0, 0, 0, 0, 0},
    };
    for (const Row& r: rows) {
        uint64_t o[5] = {9, 9, 9, 9, 9};
        bc5_m10_drop_plan(r.started, r.dropped, r.end, o);
        CHECKW(o[0] == r.act && o[1] == r.dlo && o[2] == r.dlen && o[3] == r.slo && o[4] == r.slen,
               Fmt("%llu %llu %llu: %llu %llu+%llu %llu+%llu", U(r.started), U(r.dropped), U(r.end), U(o[0]), U(o[1]), U(o[2]), U(o[3]), U(o[4])));
    }
    CHECK(bc5_m10_drop_tell(0, 0, 63, 0) == 0 && bc5_m10_drop_tell(0, 0, 64, 0) == 1 && bc5_m10_drop_tell(64, 0, 127, 0) == 0 && bc5_m10_drop_tell(64, 0, 128, 0) == 1);
    CHECK(bc5_m10_drop_tell(64, 0, 64, 1) == 1 && bc5_m10_drop_tell(64, 1, 65, 1) == 0 && bc5_m10_drop_tell(0, 0, 0, 0) == 0);
    char t[600];
    bc5_m10_drop_line(64, 63, 64 * 8 * M + 3 * M, 63 * 8 * M, 640.0, t, sizeof(t));
    CHECKW(std::string(t) == "journal dontneed (exp 0401 e10 m10): t 640 s: 64 writebacks started (sync_file_range), 63 ranges dropped (posix_fadvise DONTNEED); started up to "
                             "515.0 MiB, dropped up to 504.0 MiB; failures 0 and 0, the last results 0 and 0\n",
           t);
    CHECK(quiet_kind(t) == 0);
    End("pure");
}

// ---- 8. the real step on a file of the test's own (the syscalls) ------------------------------------------------------------------
static bool Grow(FILE* f, uint64_t to) {
    if (std::fseek(f, 0, SEEK_END) != 0) return false;
    const long at = std::ftell(f);
    if (at < 0) return false;
    static const std::vector<char> block(64 * 1024, 'x');
    for (uint64_t n = static_cast<uint64_t>(at); n < to;) {
        const size_t k = static_cast<size_t>(std::min<uint64_t>(block.size(), to - n));
        if (std::fwrite(block.data(), 1, k, f) != k) return false;
        n += k;
    }
    return std::fflush(f) == 0;
}
static void DropStep() {
    Begin("the dontneed step on a file");
    const uint64_t M = 1ull << 20u;
    FILE*          f = std::fopen("m100401-drop.tmp", "wb+");
    CHECK(f != nullptr);
    if (f == nullptr) {
        End("no file");
        return;
    }
    const int fd     = fileno(f);
    uint64_t  st[10] = {};
    const auto step  = [fd, &st](int acts) { // one step; acts: 1 when it must start a writeback
        return bc5_m10_drop_step(fd, st) == acts;
    };
    CHECK(Grow(f, 3 * M) && step(0) && st[0] == 0 && st[2] == 0);
    CHECK(Grow(f, 8 * M - 1) && step(0) && st[2] == 0);
    CHECK(Grow(f, 8 * M) && step(1));
    CHECKW(st[0] == 8 * M && st[1] == 0 && st[2] == 1 && st[3] == 0 && st[4] == 0 && st[5] == 8 * M && st[8] == 0, Fmt("%llu %llu rc %lld", U(st[0]), U(st[2]), static_cast<long long>(st[8])));
    CHECK(Grow(f, 13 * M) && step(0) && st[2] == 1);
    CHECK(Grow(f, 17 * M) && step(1));
    CHECKW(st[0] == 17 * M && st[1] == 8 * M && st[2] == 2 && st[3] == 1 && st[4] == 8 * M && st[5] == 9 * M && st[6] == 0 && st[7] == 8 * M && st[8] == 0 && st[9] == 0,
           Fmt("%llu %llu %llu %llu rc %lld %lld", U(st[0]), U(st[1]), U(st[2]), U(st[3]), static_cast<long long>(st[8]), static_cast<long long>(st[9])));
    CHECK(Grow(f, 25 * M) && step(1));
    CHECK(st[0] == 25 * M && st[1] == 17 * M && st[2] == 3 && st[3] == 2 && st[4] == 17 * M && st[5] == 8 * M && st[6] == 8 * M && st[7] == 9 * M && st[8] == 0 && st[9] == 0);
    CHECK(ftruncate(fd, static_cast<off_t>(1 * M)) == 0 && step(0) && st[2] == 3); // a file that got shorter: nothing until it passes started + 8 MiB
    CHECK(bc5_m10_drop_step(-1, st) == 0 && st[2] == 3);
    std::fclose(f);
    std::remove("m100401-drop.tmp");
    End("the syscalls");
}

// ---- 9. the AMM window's decision with recorded fakes (pure) ------------------------------------------------------------------------
static void AmmPure() {
    Begin("the amm decision");
    char c[200];
    for (int prt = 0; prt <= 1; prt++) {
        CHECK(bc5_m10_amm(0, 1, prt, c, sizeof(c)) == (2 | (prt << 2) | (1 << 3)) && std::string(c) == "prt");
        for (int mode = 1; mode <= 2; mode++) {
            const std::string n = mode == 2 ? "null(rw)" : "null(ro)";
            CHECK(bc5_m10_amm(mode, 1, prt, c, sizeof(c)) == (1 | (2 << 3)) && std::string(c) == n);
            CHECK(bc5_m10_amm(mode, 0, prt, c, sizeof(c)) == (1 | 2 | (prt << 2) | (1 << 3)) && std::string(c) == n + ",prt");
            CHECK(bc5_m10_amm(mode, -1, prt, c, sizeof(c)) == (1 | 2 | (prt << 2)) && std::string(c) == n + ",prt");
        }
    }
    int w = 9;
    CHECK(bc5_m10_null_call(1, 1, 1, &w) == 1 && w == 1);
    CHECK(bc5_m10_null_call(1, 0, 0, &w) == 0 && w == 0);
    CHECK(bc5_m10_null_call(1, 1, 0, &w) == 1 && w == 0);
    CHECK(bc5_m10_null_call(0, 1, 1, &w) == -1 && w == -1);
    std::printf("m100401:   this build's backend Device has map_null_window: %s\n", bc5_m10_backend_has_null() != 0 ? "yes" : "NO (the switch falls back to PRT)");
    End("pure");
}

// ---- 10. the AMM window: the switch line, BC5_DIRECT_AMM_PRT, the sysfs reads, the line, the held lines (mode) --------------------
static std::vector<std::string> g_held_lines; // what the open's calls held, for the journal case
#ifdef _WIN32
static void set_env(const char* n, const char* v) { _putenv_s(n, v == nullptr ? "" : v); }
#else
static void set_env(const char* n, const char* v) {
    if (v == nullptr) ::unsetenv(n);
    else ::setenv(n, v, 1);
}
#endif
static bool AmmLine(const std::string& l, const std::string& when, const std::string& what, const std::string& mem) { // the ms value is the only free part
    const std::string head = "amm window (exp 0401 e10 m10): " + when + ": " + what + ", ";
    const std::string tail = " ms" + mem + "\n";
    if (!StartsWith(l, head) || l.size() < head.size() + tail.size() || l.compare(l.size() - tail.size(), tail.size(), tail) != 0) return false;
    const std::string ms = l.substr(head.size(), l.size() - head.size() - tail.size());
    char*             e  = nullptr;
    const double      v  = std::strtod(ms.c_str(), &e);
    return !ms.empty() && e != nullptr && *e == 0 && v >= 0.0 && ms.find('.') == ms.size() - 4;
}
static void AmmWindow(const Want& w) {
    Begin("the amm window");
    const bool     rd   = w.null != 0 || w.census != 0; // the sysfs reads: with NULL_BO or PROT_CENSUS on
    const int64_t  s1[] = {100, 200, 150, 260}, s2[] = {-1, -1, -1, -1};
    const std::string reads = "mem_info_vram_used,mem_info_gtt_used";
    const std::string mem1  = rd ? "; vram used 100 -> 150, gtt used 200 -> 260 bytes (-1: not read)" : "";
    const std::string mem2  = rd ? "; vram used -1 -> -1, gtt used -1 -> -1 bytes (-1: not read)" : "";
    const std::string kind  = w.null == 2 ? "writable" : "read-only";
    const std::string nc    = w.null == 2 ? "null(rw)" : "null(ro)";
    const auto        calls = [&](const std::string& dev) { return rd ? reads + "," + dev + "," + reads : dev; };
    char              c[400];
    CHECK(bc5_m10_held() == 0);
    // (a) BC5_DIRECT_AMM_PRT unset: no window (e9), only the switch's line, held (the journal has no directory yet)
    set_env("BC5_DIRECT_AMM_PRT", nullptr);
    uint64_t from = Captured();
    bc5_m10_amm_window("open", 1, 1, 1, s1, c, sizeof(c));
    auto l = LinesFrom(from);
    CHECKW(std::string(c).empty(), c);
    CHECKW(l.size() == 1 && l[0] == WantLine(2, w.null, w.null_e), l.empty() ? "" : l[0]);
    CHECK(bc5_m10_held() == 1);
    g_held_lines = l;
    // (b) set: the open's window
    set_env("BC5_DIRECT_AMM_PRT", "1");
    from = Captured();
    bc5_m10_amm_window("open", 1, 1, 1, s1, c, sizeof(c));
    l = LinesFrom(from);
    CHECKW(std::string(c) == calls(w.null == 0 ? "prt" : nc), c);
    CHECKW(l.size() == 1 && AmmLine(l[0], "open", w.null == 0 ? "the PRT window (as e9): map_prt_window ok" : "null pages, " + kind + ": map_null_window ok", mem1),
           l.empty() ? "" : l[0]);
    CHECK(bc5_m10_held() == 2);
    if (l.size() == 1) g_held_lines.push_back(l[0]);
    // (c) a reopen whose null pages fail: PRT instead (not held)
    from = Captured();
    bc5_m10_amm_window("reopen", 0, 0, 1, s1, c, sizeof(c));
    l = LinesFrom(from);
    CHECKW(std::string(c) == calls(w.null == 0 ? "prt" : nc + ",prt"), c);
    CHECKW(l.size() == 1 && AmmLine(l[0], "reopen", w.null == 0 ? "the PRT window (as e9): map_prt_window ok" : "null pages, " + kind + ": map_null_window FAILED, map_prt_window instead: ok", mem1),
           l.empty() ? "" : l[0]);
    CHECK(bc5_m10_held() == 2);
    // (d) no map_null_window in the backend, PRT failing, sysfs unreadable
    from = Captured();
    bc5_m10_amm_window("reopen", 0, -1, 0, s2, c, sizeof(c));
    l = LinesFrom(from);
    CHECKW(std::string(c) == calls(w.null == 0 ? "prt" : nc + ",prt"), c);
    CHECKW(l.size() == 1 &&
               AmmLine(l[0], "reopen", w.null == 0 ? "the PRT window (as e9): map_prt_window FAILED" : "null pages, " + kind + ": map_null_window is not in this backend, map_prt_window instead: FAILED", mem2),
           l.empty() ? "" : l[0]);
    // (e) BC5_DIRECT_AMM_PRT=0 is set, as e9 reads it (getenv != nullptr): the window is mapped
    set_env("BC5_DIRECT_AMM_PRT", "0");
    bc5_m10_amm_window("reopen", 0, 1, 1, s1, c, sizeof(c));
    CHECKW(std::string(c) == calls(w.null == 0 ? "prt" : nc), c);
    set_env("BC5_DIRECT_AMM_PRT", nullptr);
    for (const auto& x: LinesFrom(from)) CHECKW(quiet_kind(x) == 0, x);
    for (const auto& x: g_held_lines) CHECKW(quiet_kind(x) == 0, x);
    End(w.null == 0 ? "e9's PRT" : w.null == 2 ? "writable null pages" : "read-only null pages");
}

// ---- 11. the real sysfs reader ----------------------------------------------------------------------------------------------------
static void Sysfs() {
    Begin("the sysfs reader");
    CHECK(bc5_m10_sysfs("m100401_no_such_file") == -1);
    const int64_t v = bc5_m10_sysfs("mem_info_vram_used");
    CHECK(v >= -1);
    std::printf("m100401:   this machine's mem_info_vram_used: %lld (-1: not read)\n", static_cast<long long>(v));
    End("pure");
}

// ---- 12. the real census tick: the schedule, the census thread, the device lock (mode) --------------------------------------------
static void State(uint64_t* s) { bc5_m10_census_state(s); }
static bool WaitDone(uint64_t want, int ms) {
    for (int k = 0; k < ms / 10; k++) {
        uint64_t s[4] = {};
        State(s);
        if (s[0] >= want && s[1] == 0) return true;
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }
    return false;
}
static size_t Count(const std::vector<std::string>& v, const std::string& p) {
    return static_cast<size_t>(std::count_if(v.begin(), v.end(), [&p](const std::string& s) { return StartsWith(s, p); }));
}
static bool CensusLines(const std::vector<std::string>& l, double t, uint32_t no) { // one census: header, groups, 4 totals, 2 forced lines
    const std::string h = kP + Fmt("t %.0f s: census %u: ", t, no);
    if (l.empty() || !StartsWith(l[0], h)) return false;
    unsigned long long ranges = 0, groups = 0;
    if (std::sscanf(l[0].c_str() + h.size(), "%llu guest ranges in %llu groups", &ranges, &groups) != 2) return false;
    const size_t want = 1 + std::min<size_t>(groups, 400) + (groups > 400 ? 1 : 0) + 4 + 2;
    return l.size() == want && Count(l, kP + Fmt("t %.0f s: total, ", t)) == 4 && Count(l, kP + Fmt("t %.0f s: forced ", t)) == 2;
}
static void CensusReal(const Want& w) {
    Begin("the census tick");
    uint64_t s[4] = {};
    uint64_t from = Captured();
    for (const double t: {10.0, 50.0, 119.9}) bc5_m10_tick(t);
    std::this_thread::sleep_for(std::chrono::milliseconds(100));
    State(s);
    CHECK(s[0] == 0 && s[3] == 0 && LinesFrom(from).empty());
    struct Step {
        double   t;
        uint32_t no; // 0: none due
    };
    const Step steps[] = {{120.0, 1}, {125.0, 0}, {300.0, 2}, {599.9, 0}, {600.0, 3}, {5000.0, 4}, {5399.0, 0}, {5400.0, 5}};
    uint32_t   done    = 0;
    for (const Step& st: steps) {
        from = Captured();
        bc5_m10_tick(st.t);
        if (w.census != 0 && st.no != 0) {
            done++;
            CHECKW(WaitDone(done, 10000), Fmt("census at %.1f", st.t));
            const auto l = LinesFrom(from);
            CHECKW(CensusLines(l, st.t, st.no), l.empty() ? Fmt("no lines at %.1f", st.t) : l[0]);
            for (const auto& x: l) CHECKW(quiet_kind(x) == 0, x);
        } else {
            std::this_thread::sleep_for(std::chrono::milliseconds(30));
            CHECKW(LinesFrom(from).empty(), Fmt("lines at %.1f", st.t));
        }
    }
    State(s);
    CHECKW(s[0] == done && s[1] == 0 && s[3] == done && (w.census == 0 || s[2] == 6000000), Fmt("%llu %llu %llu %llu", U(s[0]), U(s[1]), U(s[2]), U(s[3])));
    // the device lock held (as a long submission holds it): the census waits for it; a tick meanwhile leaves its census out
    bc5_m10_dev_lock(1);
    from = Captured();
    bc5_m10_tick(6000.0);
    std::this_thread::sleep_for(std::chrono::milliseconds(300));
    const size_t during = LinesFrom(from).size();
    bc5_m10_tick(6600.0);
    std::this_thread::sleep_for(std::chrono::milliseconds(30));
    const auto skipped = LinesFrom(from);
    bc5_m10_dev_lock(0);
    if (w.census != 0) {
        CHECK(during == 0);
        CHECKW(skipped.size() == 1 && skipped[0] == kP + "t 6600 s: census 7 left out: the one before still runs\n", skipped.empty() ? "" : skipped[0]);
        CHECK(WaitDone(done + 1, 10000));
        auto l = LinesFrom(from);
        if (!l.empty()) l.erase(l.begin()); // the left-out line
        CHECKW(CensusLines(l, 6000.0, 6), l.empty() ? "" : l[0]);
        double waited = -1.0;
        if (!l.empty()) {
            const size_t at = l[0].find("the device lock waited ");
            if (at != std::string::npos) waited = std::strtod(l[0].c_str() + at + 23, nullptr);
        }
        CHECKW(waited >= 250.0, std::to_string(waited));
        for (const auto& x: skipped) CHECKW(quiet_kind(x) == 0, x);
        State(s);
        CHECK(s[0] == done + 1 && s[3] == done + 2);
    } else {
        CHECK(during == 0 && skipped.empty());
        State(s);
        CHECK(s[0] == 0 && s[1] == 0 && s[3] == 0);
    }
    End(w.census != 0 ? "on" : "off: no census");
}

#ifdef M10_STANDIN
// ---- 12b. (stand-in) the real census on a mapper state of the test's own (mode) -------------------------------------------------
// The laptop's stand-in gives memory.cpp's functions ranges, private regions and two memfds of the test's own, and fills the
// unit's g_d (BOs, forced chunks). The census thread's lines must be the seam's for the same ranges and BOs, plus the forced
// chunks counted by the real snapshot, views and SEEK_DATA.
extern "C" void m10si_state(const uint64_t* r_start, const uint64_t* r_size, const uint64_t* r_off, const int* r_type, const int* r_prot, const char* const* r_name, uint32_t nr,
                            const uint64_t* p_start, const uint64_t* p_size, const int* p_type, const char* const* p_name, uint32_t np, const uint64_t* bo0, const uint64_t* bs0,
                            uint32_t nb0, const uint64_t* bo1, const uint64_t* bs1, uint32_t nb1, const uint64_t* f0, uint32_t nf0, const uint64_t* f1, uint32_t nf1, int fd0,
                            int fd1);
static void StandinCensus(const Want& w) {
    Begin("the real census on a stand-in state (stand-in)");
    const uint64_t            M = 1ull << 20u;
    const std::vector<TRange> rs = {
        {0x1140000000ull, 64 * M, 0, 0, 0x33, "RenderGpuWcLarge"},   // eager: its file range [0, 64 MiB) is an eager view
        {0x11a0000000ull, 64 * M, 64 * M, 0, 0x03, "orbis_user_malloc"}, // lazy
        {0x11c0000000ull, 64 * M, 128 * M, 0, 0x13, "Data"},
        {0x1000000ull, 4 * M, 0, 4, 0x05, "eboot.bin"},              // private: by address
        {0x2000000ull, 2 * M, 0, 3, 0x03, "stack"},
        {0x3000000ull, 2 * M, 0, 1, 0x33, "flex"},
    };
    const std::vector<TBo> d = {{0, 32 * M}, {80 * M, 2 * M}, {128 * M, 4 * M}};
    const std::vector<TBo> p = {{16 * M, 2 * M}};
    std::vector<uint64_t>    st, sz, of, bo0, bs0, bo1, bs1;
    std::vector<int>         ty, pr;
    std::vector<const char*> nm;
    for (const TRange& r: rs) {
        st.push_back(r.start);
        sz.push_back(r.size);
        of.push_back(r.offset);
        ty.push_back(r.type);
        pr.push_back(r.prot);
        nm.push_back(r.name.c_str());
    }
    for (const TBo& b: d) bo0.push_back(b.off), bs0.push_back(b.size);
    for (const TBo& b: p) bo1.push_back(b.off), bs1.push_back(b.size);
    const uint64_t    ps[] = {0x1000000ull, 0x2000000ull}, pz[] = {4 * M, 2 * M};
    const int         pt[] = {4, 3};
    const char* const pn[] = {"eboot.bin", "stack"};
    // forced, direct: 0 (eager), 64 MiB (data), 80 MiB (neither, imported), 96 MiB (neither), 128 MiB (neither, imported), 160 MiB (data)
    const uint64_t f0[] = {0, 64 * M, 80 * M, 96 * M, 128 * M, 160 * M};
    // forced, private (offset = address): 16 MiB (data), 18 MiB (neither), 32 MiB (stacks: neither)
    const uint64_t f1[]  = {16 * M, 18 * M, 32 * M};
    const int      fd0   = Memfd("m100401-si-direct", 256 * M), fd1 = Memfd("m100401-si-private", 256 * M);
    CHECK(fd0 >= 0 && fd1 >= 0 && Poke(fd0, 64 * M + 5) && Poke(fd0, 162 * M - 1) && Poke(fd1, 16 * M + 16));
    m10si_state(st.data(), sz.data(), of.data(), ty.data(), pr.data(), nm.data(), 6, ps, pz, pt, pn, 2, bo0.data(), bs0.data(), 3, bo1.data(), bs1.data(), 1, f0, 6, f1, 3, fd0,
                fd1);
    uint64_t n = 0;
    const auto seam = UnitCensus(rs, d, p, 7200.0, &n); // the same ranges and BOs through the seam
    uint64_t s[4] = {};
    bc5_m10_census_state(s);
    const uint64_t from = Captured(), done = s[0];
    bc5_m10_tick(7200.0);
    if (w.census == 0) {
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
        CHECK(LinesFrom(from).empty());
        End("off: no census");
        return;
    }
    CHECK(WaitDone(done + 1, 10000));
    const auto l = LinesFrom(from);
    CHECKW(l.size() == n && n == 1 + 6 + 4 + 2, std::to_string(l.size()));
    if (l.size() == n) {
        const std::string h = kP + "t 7200 s: census ";
        const size_t      a = l[0].find(": 6 guest ranges in 6 groups"), b = l[0].find("the device lock waited "), sa = seam[0].find(": 6 guest ranges"),
                     sb = seam[0].find("the device lock waited ");
        CHECKW(StartsWith(l[0], h) && a != std::string::npos && b != std::string::npos && sa != std::string::npos && sb != std::string::npos &&
                   l[0].substr(a, b - a) == seam[0].substr(sa, sb - sa),
               l[0] + " | " + seam[0]);
        for (size_t k = 1; k + 2 < n; k++) CHECKW(l[k] == seam[k], l[k] + " | " + seam[k]); // the groups and the totals
        const auto forced = [](const std::string& x, const std::string& want) {
            const size_t e = x.find(" SEEK_DATA, ");
            return e != std::string::npos && x.substr(0, e + 12) == want && x.size() > e + 12 + 4 && x.compare(x.size() - 4, 4, " ms\n") == 0;
        };
        CHECKW(forced(l[n - 2], kP + "t 7200 s: forced direct: 6 chunks of 2 MiB the hints and learned windows asked for: 1 under an eager view, 2 more hold data, 3 neither "
                                     "(the pin the windows alone cause), 2 of those imported (4.0 MiB); 5 SEEK_DATA, "),
               l[n - 2]);
        CHECKW(forced(l[n - 1], kP + "t 7200 s: forced private: 3 chunks of 2 MiB the hints and learned windows asked for: 0 under an eager view, 1 more hold data, 2 neither "
                                     "(the pin the windows alone cause), 0 of those imported (0.0 MiB); 3 SEEK_DATA, "),
               l[n - 1]);
        CHECK(l[1] == kP + "t 7200 s: direct \"RenderGpuWcLarge\" prot 0x33 (cpu rw- gpu rw): 1 views, 67108864 bytes, 33554432 imported; eager name\n");
    }
    for (const auto& x: l) CHECKW(quiet_kind(x) == 0, x);
    // no memfd for the private state: its forced chunks are not classified
    m10si_state(st.data(), sz.data(), of.data(), ty.data(), pr.data(), nm.data(), 6, ps, pz, pt, pn, 2, bo0.data(), bs0.data(), 3, bo1.data(), bs1.data(), 1, f0, 6, f1, 3, fd0, -1);
    const uint64_t from2 = Captured();
    bc5_m10_tick(7800.0);
    CHECK(WaitDone(done + 2, 10000));
    const auto l2 = LinesFrom(from2);
    CHECKW(!l2.empty() && l2.back() == kP + "t 7800 s: forced private: 3 chunks of 2 MiB the hints and learned windows asked for; no memfd, not classified\n",
           l2.empty() ? "" : l2.back());
    m10si_state(nullptr, nullptr, nullptr, nullptr, nullptr, nullptr, 0, nullptr, nullptr, nullptr, nullptr, 0, nullptr, nullptr, 0, nullptr, nullptr, 0, nullptr, 0, nullptr, 0, -1,
                -1);
    close(fd0);
    close(fd1);
    End("on");
}
#endif

// ---- 13. the real journal end to end (mode, journal mode) ----------------------------------------------------------------------------
static std::string Slurp(const std::filesystem::path& p) {
    std::ifstream     in(p); // text mode: the stand-in's Windows journal writes CRLF
    std::stringstream s;
    s << in.rdbuf();
    return s.str();
}
static void DropState(uint64_t* st) { bc5_m10_drop_state(st); }
static void Journal(const Want& w, bool first_run) {
    Begin("the journal");
    const bool min   = bc5_cap0401_journal_min() != 0;
    const bool quiet = EnvOn(std::getenv("BC5_DIRECT_JOURNAL_QUIET"));
    std::printf("m100401:   journal mode: %s, quiet %s\n", min ? "min (one buffered file, the play's)" : "not min (a file opened per line)", quiet ? "on" : "off");
    const uint64_t              M = 1ull << 20u;
    std::error_code             ec;
    const std::filesystem::path dir = std::filesystem::current_path() / (min ? "m100401-jmin" : "m100401-jplain");
    std::filesystem::create_directories(dir, ec);
    std::filesystem::remove(dir / "direct.log", ec);
    CHECK(bc5_cap0401_journal_open(dir.string().c_str()) == 1);
    uint64_t from = Captured();
    bc5_m10_amm_pending(); // the open's held lines (first run only)
    CHECK(bc5_m10_held() == 0);
    bc5_m10_start(1); // mem_line_start's call: the census and dontneed lines
    const auto start_lines = LinesFrom(from);
    CHECKW(start_lines.size() == 2 && start_lines[0] == WantLine(0, w.census, w.census_e) && start_lines[1] == WantLine(1, w.dontneed, w.dontneed_e),
           start_lines.empty() ? "" : start_lines[0]);
    std::vector<std::string> bulk;
    const auto               put = [&bulk](uint32_t n) {
        for (uint32_t k = 0; k < n; k++) {
            std::string l = Fmt("m100401 journal line %06u ", static_cast<unsigned>(bulk.size()));
            l.append(999 - l.size(), 'y');
            l += '\n';
            bc5_cap0401_journal(l.c_str());
            bulk.push_back(l);
        }
        bc5_cap0401_journal_flush();
    };
    uint64_t st[10] = {};
    put(8500);
    const uint64_t size1 = std::filesystem::file_size(dir / "direct.log", ec);
    DropState(st);
    const uint64_t started1 = st[0];
    if (w.dontneed != 0) {
        CHECKW(st[2] == 1 && st[3] == 0 && st[4] == 0 && st[5] == started1 && started1 >= 8 * M && started1 <= size1 && st[8] == 0,
               Fmt("syncs %llu drops %llu started %llu size %llu rc %lld", U(st[2]), U(st[3]), U(started1), U(size1), static_cast<long long>(st[8])));
    } else {
        CHECK(st[0] == 0 && st[2] == 0 && st[3] == 0);
    }
    put(8500);
    const uint64_t size2 = std::filesystem::file_size(dir / "direct.log", ec);
    DropState(st);
    if (w.dontneed != 0) {
        CHECKW(st[2] == 2 && st[3] == 1 && st[6] == 0 && st[7] == started1 && st[1] == started1 && st[4] == started1 && st[0] - started1 >= 8 * M && st[0] <= size2 &&
                   st[5] == st[0] - started1 && st[8] == 0 && st[9] == 0,
               Fmt("syncs %llu drops %llu started %llu dropped %llu size %llu rc %lld %lld", U(st[2]), U(st[3]), U(st[0]), U(st[1]), U(size2), static_cast<long long>(st[8]),
                   static_cast<long long>(st[9])));
    } else {
        CHECK(st[0] == 0 && st[2] == 0 && st[3] == 0);
    }
    // the file: [the quiet state line] + the held lines + the two switch lines + the 17,000 lines, every byte as written
    std::string want;
    for (const auto& x: first_run ? g_held_lines : std::vector<std::string>()) want += x;
    for (const auto& x: start_lines) want += x;
    for (const auto& x: bulk) want += x;
    std::string got = Slurp(dir / "direct.log");
    if (quiet) {
        const size_t nl = got.find('\n');
        CHECK(StartsWith(got, "exp 0401 e7: journal quiet on, not written: ") && nl != std::string::npos);
        got = nl == std::string::npos ? std::string() : got.substr(nl + 1);
    }
    CHECKW(got == want, Fmt("%zu bytes, want %zu", got.size(), want.size()));
    CHECK(size2 >= 17000000);
    std::filesystem::remove(dir / "direct.log", ec); // the min file stays open: on Linux the name goes, the blocks with the last close
    std::filesystem::remove(dir, ec);
    End(Fmt("%s, quiet %s, dontneed %s", min ? "min" : "not min", quiet ? "on" : "off", w.dontneed != 0 ? "on" : "off").c_str());
}

} // namespace m100401

int main(int argc, char** argv) {
    using namespace m100401;
    static const char* const modes[] = {"on", "off", "unset", "empty", "junk", "rw"};
    int                      m       = -1;
    for (int k = 0; argc == 2 && k < 6; k++)
        if (std::strcmp(argv[1], modes[k]) == 0) m = k;
    if (m < 0) {
        std::printf("m100401: usage: m100401 on | off | unset | empty | junk | rw (in a fresh directory)\n");
        return 2;
    }
    const bool second = std::getenv("M100401_REEXEC") != nullptr;
    if (m >= 2) { // the modes that set the switches here
        static const char* const v[4][3] = {{nullptr, nullptr, nullptr}, {"", "", ""}, {"yes", "yes", "Rw"}, {"1", "1", "rw"}};
        set_env("BC5_DIRECT_PROT_CENSUS", v[m - 2][0]);
        set_env("BC5_DIRECT_JOURNAL_DONTNEED", v[m - 2][1]);
        set_env("BC5_DIRECT_AMM_NULL_BO", v[m - 2][2]);
    }
    const Want w = WantFromEnv();
    if ((m == 0 && (w.census == 0 || w.dontneed == 0 || w.null == 0)) || (m == 1 && (w.census != 0 || w.dontneed != 0 || w.null != 0))) {
        std::printf("m100401: the argument says %s but the switches say census %d, dontneed %d, null bo %d\n", modes[m], w.census, w.dontneed, w.null);
        return 2;
    }
    set_env("BC5_DIRECT_EAGER_NAMES", kEagerNames); // read once by the unit, at the census's first name test
    set_env("BC5_DIRECT_LAZY_NAMES", kLazyNames);
    set_env("BC5_DIRECT_AMM_PRT", nullptr);
    set_env("BC5_DIRECT_MEM_LINE", "0");
    if (!second) set_env("BC5_DIRECT_JOURNAL_QUIET", "0"); // the first run: today's journal path; the second: quiet (the play's)
    std::thread([] {
        std::this_thread::sleep_for(std::chrono::seconds(60));
        std::printf("m100401: FAIL watchdog: case \"%s\" still running after 60 s\n", g_case.load());
        std::fflush(stdout);
        std::_Exit(3);
    }).detach();
    bc5_m10_capture(1);

    if (!second) {
        Switches(w);
        Parse();
        SwitchLines();
        Schedule();
        CensusPure();
        Forced();
        DropPlan();
        DropStep();
        AmmPure();
        AmmWindow(w);
        Sysfs();
        CensusReal(w);
#ifdef M10_STANDIN
        StandinCensus(w);
#endif
        Journal(w, true);
#ifndef _WIN32
        // Again, in the other journal mode, quiet: BC5_DIRECT_JOURNAL is read when the unit is loaded.
        const bool min = bc5_cap0401_journal_min() != 0;
        set_env("M100401_REEXEC", "1");
        set_env("M100401_CARRY", Fmt("%d %d", g_pass, g_total).c_str());
        set_env("BC5_DIRECT_JOURNAL", min ? nullptr : "min");
        set_env("BC5_DIRECT_JOURNAL_QUIET", "1");
        std::printf("m100401: first run %d of %d; running again with BC5_DIRECT_JOURNAL %s and BC5_DIRECT_JOURNAL_QUIET=1\n", g_pass, g_total, min ? "unset" : "=min");
        std::fflush(stdout);
        std::fflush(stderr);
        ::execv("/proc/self/exe", argv);
        CHECKW(false, "the second run could not start");
#else
        std::printf("m100401: note: no second run on this system (run again with M100401_REEXEC=1 M100401_CARRY=\"0 0\" BC5_DIRECT_JOURNAL=min BC5_DIRECT_JOURNAL_QUIET=1)\n");
#endif
    } else {
        int p0 = 0, t0 = 0;
        if (const char* c = std::getenv("M100401_CARRY"); c == nullptr || std::sscanf(c, "%d %d", &p0, &t0) != 2) {
            std::printf("m100401: FAIL the second run has no first run's counts\n");
            t0 = 1;
        }
        Switches(w);
        Journal(w, false);
        g_pass += p0;
        g_total += t0;
    }

    std::fflush(stderr);
    std::printf("m100401: %s %d of %d%s\n", modes[m], g_pass, g_total, g_pass == g_total ? "; end" : "");
    std::fflush(stdout);
    std::_Exit(g_pass == g_total ? 0 : 1); // the unit's census threads may still be detached: no static destructors under them
}
