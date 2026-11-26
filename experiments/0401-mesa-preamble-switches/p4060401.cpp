// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0401 series e9, tag p406: the CPU test of mkp4060401.py's two units (p4060401-notes.md): exp 0406's
// BC5_0406_LEARNED_PRUNE (src/libs/bc5LleAgc.cpp) and BC5_0406_AUDIO_SLEEP (src/libs/audio.cpp). BC5_0406_PROBE_LAZY is not
// built; the notes say why. The test calls the units through their seams (bc5_p406_*, bc5_p406a_*, and cap's
// bc5_cap0401_quiet_kind for the journal's quiet filter):
//   - the switches as the units read them, and the parse;
//   - the junk rule and the real load hook on exp 0288's 107 learned windows (experiments/0288-emulator-memory/raw/
//     direct-learned-pkg-20261024.txt, commit dd819f4f);
//   - the eager-heap test and the switch-gated decision of learned_apply's loop on a stand-in heap layout;
//   - the real minute count of learned_apply calls, and every new line against the quiet filter;
//   - the drain sleep, and the real wait on a fake queue and clock.
// Built with -DP406_STANDIN (the laptop's stand-in TUs, made from the outputs' text with stubbed devices), it also runs the
// real learned_load and learned_apply (map_window and scratch_fill recorded) and the real text of QueueSdlAudio's wait.
// No game, no GPU, no window, no sound device, no network: the direct path is never opened (g_dev stays empty in the unit),
// no SDL call is made, nothing is submitted anywhere.
// Modes (each sets both switches before the first call; the units read them once):
//   on     "1"     the new paths (LEARNED_PRUNE's full mode)       off    "0"   the old paths
//   unset  (none)  the old paths        empty  ""    the old paths (Windows' _putenv_s cannot set an empty value: there
//                                                    it is unset; the parse case covers "" on every system)
//   junk   "yes"   the new paths: any value but unset, empty or "0" is on (bc5::env_on's reading, F767); for
//                  LEARNED_PRUNE any on value but "eager" is the full mode
//   eager  LEARNED_PRUNE=eager (the eager skip alone, the junk windows kept), AUDIO_SLEEP=1
// Output: one line per case, then "p4060401: <mode> N of N; end"; without "; end" something failed. Exit 0 only after the end
// line. A watchdog ends a hang after 60 s with a FAIL line (exit 3). No argument or an unknown one: usage, exit 2.
// Build: build0401.py ... src/libs/bc5LleAgc.cpp=<out>/src/libs/bc5LleAgc.cpp src/libs/audio.cpp=<out>/src/libs/audio.cpp
//        --gate p4060401.cpp <dir>/p4060401 --like src/libs/bc5LleAgc.cpp (linked with every emulator object but main.cpp.o,
//        the private bc5LleAgc.cpp.o and audio.cpp.o among them), -std=c++20 -Wall -Wextra -Werror.
// usage: p4060401 on | off | unset | empty | junk | eager

#if defined(_WIN32) && !defined(_CRT_SECURE_NO_WARNINGS)
#define _CRT_SECURE_NO_WARNINGS // the laptop's stand-in build: the Windows CRT marks fopen deprecated
#endif
#include <algorithm>
#include <atomic>
#include <chrono>
#include <cinttypes>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <thread>
#include <utility>
#include <vector>

// The seams of mkp4060401.py's units (always compiled in, never called by the emulator), and cap's quiet filter.
extern "C" int      bc5_p406_parse(const char* e); // the mode: 0 off, 1 eager, 2 full
extern "C" int      bc5_p406_prune_mode();
extern "C" int      bc5_p406_junk(uint64_t base);
extern "C" void     bc5_p406_consts(uint64_t* out);
extern "C" void     bc5_p406_switch_line(int mode, const char* e, char* out, uint32_t cap);
extern "C" void     bc5_p406_prune_line(uint32_t loaded, uint32_t kept, uint32_t high, uint32_t zero, char* out, uint32_t cap);
extern "C" uint32_t bc5_p406_loaded(uint64_t* base, uint64_t* bytes, uint32_t count);
extern "C" int      bc5_p406_inside(const uint64_t* va, const uint64_t* size, const uint8_t* eager, uint32_t count, uint64_t lo, uint64_t n);
extern "C" int      bc5_p406_skip_with(const uint64_t* va, const uint64_t* size, const uint8_t* eager, uint32_t count, int sorted, int memfd, uint64_t lo, uint64_t n);
extern "C" int      bc5_p406_tick(uint64_t took_ns, uint64_t now_ns, double t_s, char* out, uint32_t cap);
extern "C" uint64_t bc5_p406_skips();
extern "C" int      bc5_cap0401_quiet_kind(const char* s, uint64_t n, int complete);
typedef uint32_t (*Bc5P406aQueued)(void* ctx);
typedef uint64_t (*Bc5P406aNow)(void* ctx);
typedef void (*Bc5P406aSleep)(uint32_t us, void* ctx);
typedef void (*Bc5P406aClear)(void* ctx);
extern "C" int      bc5_p406a_parse(const char* e);
extern "C" int      bc5_p406a_on();
extern "C" uint32_t bc5_p406a_rate(int freq, int channels, int bits);
extern "C" uint32_t bc5_p406a_sleep_us(uint32_t queued, uint32_t mark, uint32_t bytes_per_ms);
extern "C" uint32_t bc5_p406a_wait(uint32_t mark, uint64_t start_us, uint64_t timeout_us, uint32_t bytes_per_ms, Bc5P406aQueued q, Bc5P406aNow n, Bc5P406aSleep s,
                                   Bc5P406aClear c, void* ctx, int* cleared);
#ifdef P406_STANDIN
// The laptop stand-ins' drivers (not in the units): the real learned_load / learned_apply with stubbed views and recorded
// map_window / scratch_fill calls; the real text of QueueSdlAudio's wait with a fake queue and clock.
extern "C" void     p406si_views(const uint64_t* va, const uint64_t* size, const uint8_t* eager, const char* const* names, uint32_t count, int sorted, int memfd);
extern "C" uint32_t p406si_apply(uint64_t* mapped, uint32_t* n_mapped, uint64_t* filled, uint32_t* n_filled, uint32_t cap);
extern "C" uint32_t p406si_journal_count(const char* needle);
extern "C" uint32_t p406si_audio(uint32_t q0, uint32_t mark, uint32_t chunk, uint32_t period_us, uint32_t* sleeps, uint32_t cap, uint32_t* n_sleeps, uint32_t* reads,
                                 uint32_t* clears, uint64_t* elapsed_us, uint64_t* blocked_us);
#endif

namespace p4060401 {

static int                      g_pass = 0, g_total = 0, g_case_pass = 0, g_case_total = 0;
static std::atomic<const char*> g_case {"init"};

static void Check(bool ok, const char* what, int line, const std::string& why = "") {
    g_total++;
    g_case_total++;
    if (ok) {
        g_pass++;
        g_case_pass++;
    } else {
        std::printf("p4060401: FAIL %s (line %d): %s%s%s\n", g_case.load(), line, what, why.empty() ? "" : ": ", why.c_str());
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
    std::printf("p4060401: case %s (%s): %d of %d\n", g_case.load(), how, g_case_pass, g_case_total);
    std::fflush(stdout);
}
static std::string hex(uint64_t v) {
    char t[32];
    std::snprintf(t, sizeof(t), "0x%" PRIx64, v);
    return t;
}

// ---- exp 0288's 107 learned windows (base; each 0x6000000 bytes), in the file's order ------------------------------------
constexpr uint64_t kWin                 = 0x6000000ull;
constexpr uint64_t kExp0288[107] = {
    0x11ce000000ull, 0x1182000000ull, 0x11a6000000ull, 0x1192000000ull, 0x1196000000ull, 0x11aa000000ull, 0x1146000000ull, 0x114a000000ull,
    0x1156000000ull, 0x115a000000ull, 0x11a2000000ull, 0x116e000000ull, 0x1186000000ull, 0x11ae000000ull, 0x115e000000ull, 0x1132000000ull,
    0x116a000000ull, 0x1172000000ull, 0x112a000000ull, 0x114e000000ull, 0x117a000000ull, 0x1152000000ull, 0x117e000000ull, 0x1116000000ull,
    0x8002000000ull, 0x118a000000ull, 0x81c6000000ull, 0x11e6000000ull, 0x112e000000ull, 0x11de000000ull, 0x1176000000ull, 0x81b6000000ull,
    0x1296000000ull, 0x1282000000ull, 0x12aa000000ull, 0x12ae000000ull, 0x128a000000ull, 0x12b2000000ull, 0x128e000000ull, 0x81c2000000ull,
    0x1216000000ull, 0x1276000000ull, 0x1286000000ull, 0x127a000000ull, 0x126e000000ull, 0x127e000000ull, 0x1272000000ull, 0x120e000000ull,
    0x126a000000ull, 0x1236000000ull, 0x1246000000ull, 0x12b6000000ull, 0x7ffe000000ull, 0x11ca000000ull, 0x12ba000000ull, 0x12c2000000ull,
    0x125652000000ull, 0xc012ca000000ull, 0x14852000000ull, 0xc01292000000ull, 0x1452000000ull, 0xa125e000000ull, 0x5452000000ull, 0x20124e000000ull,
    0x9167a000000ull, 0x213e4e000000ull, 0x7ffffe000000ull, 0x12c6000000ull, 0x48d292000000ull, 0xd21292000000ull, 0x681292000000ull, 0x12ca000000ull,
    0x6165a000000ull, 0xf81316000000ull, 0x12ce000000ull, 0xafc5e000000ull, 0x881292000000ull, 0x387a4e000000ull, 0x9576a000000ull, 0x71662a000000ull,
    0x12da000000ull, 0x130a000000ull, 0x5125e000000ull, 0x4a1292000000ull, 0x189a66000000ull, 0x18552000000ull, 0x401292000000ull, 0x122252000000ull,
    0x221292000000ull, 0x14c52000000ull, 0x34a52000000ull, 0xfa1292000000ull, 0xb0124e000000ull, 0x8011ce000000ull, 0x11ea000000ull, 0x0ull,
    0x842e000000ull, 0x8516000000ull, 0x84a2000000ull, 0x820a000000ull, 0x83fa000000ull, 0x1762000000ull, 0x1206000000ull, 0x2672000000ull,
    0x145a000000ull, 0x1332000000ull, 0x1472000000ull,
};
// The rule written out again, independently of the unit: a junk base has a bit at 40 or above set, or is 0.
static bool ref_junk(uint64_t a) { return a == 0 || a >= (1ull << 40u); }

// ---- the stand-in heap layout: sorted, disjoint views of direct memory --------------------------------------------------
struct Layout {
    std::vector<uint64_t>    va, size;
    std::vector<uint8_t>     eager;
    std::vector<const char*> name;
    void                     add(uint64_t a, uint64_t n, bool e, const char* nm) {
        va.push_back(a);
        size.push_back(n);
        eager.push_back(e ? 1 : 0);
        name.push_back(nm);
    }
    uint32_t count() const { return static_cast<uint32_t>(va.size()); }
};
static Layout layout() {
    Layout l;
    l.add(0x1140000000ull, 0x40000000ull, true, "RenderGpuWcLarge");         // 1 GiB
    l.add(0x1180000000ull, 0, false, "(empty)");                              // a view of no size at the boundary
    l.add(0x1180000000ull, 0x20000000ull, true, "CommitIABufferAllocator");  // right after the first: 0x117e straddles both
    l.add(0x11a0000000ull, 0x20000000ull, false, "orbis_user_malloc");       // lazy, right after: not eager
    l.add(0x11d0000000ull, 0x20000000ull, true, "DynamicHeap");              // after a gap of 256 MiB
    l.add(0x1200000000ull, 0x8000000ull, true, "Physics");                   // 0x1206 runs past its end
    for (uint64_t a = 0x8000000000ull; a < 0x8200000000ull; a += 0x1000000ull) // AMM: 16-MiB views, one missing
        if (a != 0x81c4000000ull) l.add(a, 0x1000000ull, true, "AMM");
    return l;
}
// The reference: every 1-MiB granule of the window lies under an eager view and under no other (the layout's and the
// windows' bounds are 1-MiB aligned, so this is exact here).
static bool ref_inside(const Layout& l, uint64_t lo, uint64_t n) {
    if (n == 0 || lo + n < lo) return false;
    for (uint64_t g = lo; g < lo + n; g += 1ull << 20u) {
        bool any = false;
        for (uint32_t k = 0; k < l.count(); k++) {
            if (l.size[k] == 0 || g < l.va[k] || g >= l.va[k] + l.size[k]) continue;
            if (l.eager[k] == 0) return false;
            any = true;
        }
        if (!any) return false;
    }
    return true;
}
constexpr uint32_t kInside = 24; // exp 0288's windows inside the layout's eager views (all of them kept by the junk rule)

static int quiet_kind(const std::string& line) { // the journal's quiet filter on a whole line
    const std::string l = line + "\n";
    return bc5_cap0401_quiet_kind(l.c_str(), l.size(), 1);
}

// ---- 1. the switches as the units read them (mode) ----------------------------------------------------------------------
static const char* how(int pm) { return pm == 2 ? "full mode" : pm == 1 ? "eager mode" : "old path"; }
static void Switches(int pm, bool ao) {
    Begin("the switches");
    CHECK(bc5_p406_prune_mode() == pm);
    CHECK(bc5_p406_prune_mode() == pm); // read once
    CHECK(bc5_p406a_on() == (ao ? 1 : 0));
    CHECK(bc5_p406a_on() == (ao ? 1 : 0));
    uint64_t c[2] = {};
    bc5_p406_consts(c);
    CHECK(c[0] == 5000000ull && c[1] == 60000000000ull);
    End(how(pm));
}

// ---- 2. the parse (pure) -------------------------------------------------------------------------------------------------
static void Parse() {
    Begin("the parse");
    for (int (*p)(const char*): {bc5_p406_parse, bc5_p406a_parse}) {
        const int full = p == bc5_p406_parse ? 2 : 1; // LEARNED_PRUNE's full mode; AUDIO_SLEEP's on
        CHECK(p(nullptr) == 0);
        CHECK(p("") == 0);
        CHECK(p("0") == 0);
        CHECK(p("1") == full);
        CHECK(p("eager") == 1); // LEARNED_PRUNE's eager mode; for AUDIO_SLEEP any on value
        for (const char* e: {"yes", "2", "off", "00", " 0", "0 ", "true", "-0", "Eager", "eager ", "eager1"}) CHECKW(p(e) == full, e);
    }
    End("pure");
}

// ---- 3. the lines and the journal's quiet filter (pure) -----------------------------------------------------------------
static void Lines() {
    Begin("the lines and the quiet filter");
    char t[600];
    CHECK(quiet_kind("timing: #5 done at t 1.0 s, 0.1 ms after the sync and hints") == 2); // the filter is live: it drops this kind
    CHECK(quiet_kind("timeout probe: op 2d at 4") == -1);
    bc5_p406_switch_line(2, "1", t, sizeof(t));
    CHECKW(std::string(t) == "exp 0406 (p406): learned prune on, mode full (BC5_0406_LEARNED_PRUNE=1): windows at junk addresses dropped at load, map_window left out "
                             "for windows inside eager heaps; learned_apply calls over 5 ms counted, one line a minute",
           t);
    CHECK(quiet_kind(t) == 0);
    bc5_p406_switch_line(2, "yes", t, sizeof(t));
    CHECKW(std::strstr(t, "learned prune on, mode full (BC5_0406_LEARNED_PRUNE=yes, any value but unset, empty, 0 or eager is the full mode)") != nullptr, t);
    CHECK(quiet_kind(t) == 0);
    bc5_p406_switch_line(1, "eager", t, sizeof(t));
    CHECKW(std::string(t) == "exp 0406 (p406): learned prune on, mode eager (BC5_0406_LEARNED_PRUNE=eager): map_window left out for windows inside eager heaps, the "
                             "junk windows kept and filled as e8; learned_apply calls over 5 ms counted, one line a minute",
           t);
    CHECK(quiet_kind(t) == 0);
    for (const char* e: {static_cast<const char*>(nullptr), "", "0"}) {
        bc5_p406_switch_line(0, e, t, sizeof(t));
        const char* how = e == nullptr ? "(BC5_0406_LEARNED_PRUNE unset)" : e[0] == 0 ? "(BC5_0406_LEARNED_PRUNE empty)" : "(BC5_0406_LEARNED_PRUNE =0)";
        CHECKW(std::strstr(t, "exp 0406 (p406): learned prune off ") == t && std::strstr(t, how) != nullptr && std::strstr(t, ": as e8;") != nullptr, t);
        CHECK(quiet_kind(t) == 0);
    }
    bc5_p406_prune_line(107, 75, 31, 1, t, sizeof(t));
    CHECKW(std::string(t) == "learned prune (exp 0406 p406): 107 learned windows loaded, 75 kept, 32 dropped at junk addresses (31 with a bit at 40 or above set, 1 at base 0); "
                             "the file is unchanged",
           t);
    CHECK(quiet_kind(t) == 0);
    // the skip's line as the unit writes it (its format, with the stand-in layout's first view)
    std::snprintf(t, sizeof(t),
                  "learned prune (exp 0406 p406): window 0x1146000000+0x6000000 lies inside eager views (the first: RenderGpuWcLarge at 0x1140000000+0x40000000): map_window "
                  "left out while it does; its scratch fill stays");
    CHECK(quiet_kind(t) == 0);
    End("pure");
}

// ---- 4. the junk rule (pure) ----------------------------------------------------------------------------------------------
static void Junk() {
    Begin("the junk rule");
    for (const uint64_t a: {0ull, 1ull << 40u, (1ull << 40u) + 0x1000000ull, 1ull << 47u, 0x8011ce000000ull, ~0ull, 0x14852000000ull})
        CHECKW(bc5_p406_junk(a) == 1, hex(a));
    for (const uint64_t a: {1ull, 0xffffffffffull, 0x8000000000ull, 0x11ce000000ull, 0x7ffe000000ull, 0x2672000000ull})
        CHECKW(bc5_p406_junk(a) == 0, hex(a));
    uint32_t high = 0, zero = 0, kept = 0;
    for (const uint64_t a: kExp0288) {
        CHECKW(bc5_p406_junk(a) == (ref_junk(a) ? 1 : 0), hex(a));
        if (a == 0) zero++;
        else if (ref_junk(a)) high++;
        else kept++;
    }
    // exp 0288's README counts 46 junk windows; by the rule written in exp 0406's spec it is 32 of its 107
    CHECKW(high == 31 && zero == 1 && kept == 75, std::to_string(high) + " " + std::to_string(zero) + " " + std::to_string(kept));
    End("pure");
}

// ---- 5. the real load hook on exp 0288's list (mode) -----------------------------------------------------------------------
static void Load(int pm) { // the junk windows leave the list in the full mode only
    Begin("the load hook");
    uint64_t base[107], bytes[107];
    for (uint32_t k = 0; k < 107; k++) base[k] = kExp0288[k], bytes[k] = kWin;
    const uint32_t n = bc5_p406_loaded(base, bytes, 107);
    std::vector<uint64_t> want;
    for (const uint64_t a: kExp0288)
        if (pm != 2 || !ref_junk(a)) want.push_back(a);
    CHECKW(n == want.size(), std::to_string(n));
    bool same = n == want.size();
    for (uint32_t k = 0; same && k < n; k++) same = base[k] == want[k] && bytes[k] == kWin;
    CHECK(same); // the order kept
    End(how(pm));
}

// ---- 6. the eager-heap test (pure) ------------------------------------------------------------------------------------------
static void Inside() {
    Begin("inside an eager heap");
    const Layout l = layout();
    const auto   in = [&l](uint64_t lo, uint64_t n) { return bc5_p406_inside(l.va.data(), l.size.data(), l.eager.data(), l.count(), lo, n); };
    uint32_t     inside = 0;
    for (const uint64_t a: kExp0288) {
        const int r = in(a, kWin);
        CHECKW(r == (ref_inside(l, a, kWin) ? 1 : 0), hex(a));
        inside += r == 1 ? 1u : 0u;
        if (r == 1) CHECKW(!ref_junk(a), hex(a));
    }
    CHECKW(inside == kInside, std::to_string(inside));
    // the cases the layout was made for
    CHECK(in(0x1146000000ull, kWin) == 1);              // inside one view
    CHECK(in(0x117a000000ull, kWin) == 1);              // ends where the view ends
    CHECK(in(0x117e000000ull, kWin) == 1);              // across two eager views and the empty one between
    CHECK(in(0x1140000000ull, 0x40000000ull) == 1);    // the whole view
    CHECK(in(0x1140000000ull, 0x60000000ull) == 1);    // two views, end to end
    CHECK(in(0x113e000000ull, kWin) == 0);              // starts before the first view
    CHECK(in(0x119e000000ull, kWin) == 0);              // runs into the lazy view
    CHECK(in(0x11a2000000ull, kWin) == 0);              // inside the lazy view
    CHECK(in(0x11ce000000ull, kWin) == 0);              // starts in the gap
    CHECK(in(0x1206000000ull, kWin) == 0);              // runs past the last view of a region
    CHECK(in(0x81c2000000ull, kWin) == 0);              // over the missing AMM view
    CHECK(in(0x81c6000000ull, kWin) == 1);              // after it
    CHECK(in(0x81fe000000ull, kWin) == 0);              // runs past the last AMM view
    CHECK(in(0x9000000000ull, kWin) == 0);              // past every view
    CHECK(in(0x1146000000ull, 0) == 0);                 // empty
    CHECK(in(~0ull - 0x100000ull, 0x200000ull) == 0);   // wraps
    CHECK(bc5_p406_inside(nullptr, nullptr, nullptr, 0, 0x1146000000ull, kWin) == 0); // no views
    End("pure");
}

// ---- 7. the switch-gated decision of learned_apply's loop (mode) ----------------------------------------------------------
static void Gate(int pm) { // either on mode skips
    Begin("the loop's decision");
    const Layout l = layout();
    uint32_t     skipped = 0, nomem = 0, unsorted = 0;
    for (const uint64_t a: kExp0288) {
        const int r = bc5_p406_skip_with(l.va.data(), l.size.data(), l.eager.data(), l.count(), 1, 1, a, kWin);
        CHECKW(r == (pm != 0 && ref_inside(l, a, kWin) ? 1 : 0), hex(a));
        skipped += r == 1 ? 1u : 0u;
        nomem += static_cast<uint32_t>(bc5_p406_skip_with(l.va.data(), l.size.data(), l.eager.data(), l.count(), 1, 0, a, kWin));
        unsorted += static_cast<uint32_t>(bc5_p406_skip_with(l.va.data(), l.size.data(), l.eager.data(), l.count(), 0, 1, a, kWin));
    }
    CHECKW(skipped == (pm != 0 ? kInside : 0u), std::to_string(skipped));
    CHECK(nomem == 0 && unsorted == 0); // no memfd, or views not sorted: never left out
    End(how(pm));
}

// ---- 8. the real minute count (mode: it runs on and off) ----------------------------------------------------------------
static void Tick(int pm) {
    Begin("the minute count");
    const uint64_t s0 = 1000000000000ull, ms = 1000000ull, s = 1000000000ull;
    char           t[600];
    t[0] = 0;
    CHECK(bc5_p406_tick(1 * ms, s0, 1.0, t, sizeof(t)) == 0);
    CHECK(bc5_p406_tick(6 * ms, s0 + 1 * s, 2.0, t, sizeof(t)) == 0);
    CHECK(bc5_p406_tick(5 * ms, s0 + 2 * s, 3.0, t, sizeof(t)) == 0); // 5 ms is not over 5 ms
    CHECK(bc5_p406_tick(633 * ms, s0 + 30 * s, 31.0, t, sizeof(t)) == 0);
    CHECK(bc5_p406_tick(1 * ms, s0 + 60 * s - 1, 61.0, t, sizeof(t)) == 0); // 1 ns short of the minute
    CHECK(bc5_p406_tick(7 * ms, s0 + 60 * s, 61.0, t, sizeof(t)) == 1);
    const std::string prune = pm != 0 ? "on" : "off";
    CHECKW(std::string(t) == "learned apply (exp 0406 p406): t 61 s: 3 of 6 calls in the last 60 s over 5 ms, 646.0 ms in all, the longest 633.0 ms; 3 over 5 ms so far, "
                             "0.6 s in all; learned prune " + prune + ", 0 windows left out of map_window so far",
           t);
    CHECK(quiet_kind(t) == 0);
    CHECK(bc5_p406_tick(1 * ms, s0 + 61 * s, 62.0, t, sizeof(t)) == 0); // the next minute starts at its line
    CHECK(bc5_p406_tick(2 * ms, s0 + 120 * s, 121.0, t, sizeof(t)) == 1);
    CHECKW(std::string(t) == "learned apply (exp 0406 p406): t 121 s: 0 of 2 calls in the last 60 s over 5 ms, 0.0 ms in all, the longest 0.0 ms; 3 over 5 ms so far, 0.6 s "
                             "in all; learned prune " + prune + ", 0 windows left out of map_window so far",
           t);
    End(how(pm));
}

// ---- 9. the drain sleep (pure) ------------------------------------------------------------------------------------------------
static void DrainSleep() {
    Begin("the drain sleep");
    CHECK(bc5_p406a_rate(48000, 2, 16) == 192);   // 48 kHz stereo s16
    CHECK(bc5_p406a_rate(48000, 8, 32) == 1536);  // 7.1 f32
    CHECK(bc5_p406a_rate(44100, 2, 16) == 176);   // 176.4, rounded down: the sleep a little longer, at most 2 ms all the same
    CHECK(bc5_p406a_rate(0, 2, 16) == 0 && bc5_p406a_rate(48000, 0, 16) == 0 && bc5_p406a_rate(48000, 2, 0) == 0 && bc5_p406a_rate(-1, 2, 16) == 0);
    CHECK(bc5_p406a_sleep_us(960 + 96, 960, 192) == 500);    // 0.5 ms
    CHECK(bc5_p406a_sleep_us(960 + 10, 960, 192) == 500);    // 52 us: the old poll is the floor
    CHECK(bc5_p406a_sleep_us(960 + 192, 960, 192) == 1000);  // 1 ms
    CHECK(bc5_p406a_sleep_us(960 + 193, 960, 192) == 1006);  // rounded up
    CHECK(bc5_p406a_sleep_us(960 + 384, 960, 192) == 2000);  // 2 ms
    CHECK(bc5_p406a_sleep_us(960 + 385, 960, 192) == 2000);  // the cap
    CHECK(bc5_p406a_sleep_us(0xffffffffu, 0, 1) == 2000);    // the cap, no overflow
    CHECK(bc5_p406a_sleep_us(5000, 960, 0) == 500);          // rate not known: the old poll
    CHECK(bc5_p406a_sleep_us(960, 960, 192) == 500 && bc5_p406a_sleep_us(10, 960, 192) == 500);
    End("pure");
}

// ---- 10. the real wait (Bc5AudioSleepWait) on a fake queue and clock -------------------------------------------------------
struct FakeDev { // the queue loses `chunk` bytes at every multiple of `period` us of the clock (a device callback)
    uint64_t              clock = 0, q = 0;
    uint32_t              chunk = 0, period = 1000;
    uint64_t              under_at = ~0ull; // the clock when the queue first reached the mark
    uint32_t              mark = 0, reads = 0, clears = 0;
    std::vector<uint32_t> sleeps;
    void                  advance(uint64_t us) {
        const uint64_t before = clock / period, after = (clock + us) / period;
        clock += us;
        const uint64_t gone = (after - before) * chunk;
        q                   = q > gone ? q - gone : 0;
        if (q <= mark && under_at == ~0ull) under_at = clock;
    }
};
static uint32_t FQueued(void* c) {
    auto* d = static_cast<FakeDev*>(c);
    d->reads++;
    return static_cast<uint32_t>(d->q);
}
static uint64_t FNow(void* c) { return static_cast<FakeDev*>(c)->clock; }
static void     FSleep(uint32_t us, void* c) {
    auto* d = static_cast<FakeDev*>(c);
    d->sleeps.push_back(us);
    d->advance(us);
}
static void FClear(void* c) {
    auto* d = static_cast<FakeDev*>(c);
    d->clears++;
    d->q = 0;
}
// The old loop, as QueueSdlAudio has it (the reference): the mark, the 1-s clear, a 500-us poll.
static void old_loop(FakeDev& d, uint64_t start) {
    while (FQueued(&d) > d.mark) {
        if (FNow(&d) - start > 1000000ull) {
            FClear(&d);
            break;
        }
        FSleep(500, &d);
    }
}
struct WaitRun {
    FakeDev  dev;
    uint32_t r       = 0;
    int      cleared = 0;
};
static WaitRun run_wait(uint64_t q0, uint32_t mark, uint32_t chunk, uint32_t period, uint32_t rate) {
    WaitRun w;
    w.dev.q      = q0;
    w.dev.mark   = mark;
    w.dev.chunk  = chunk;
    w.dev.period = period;
    w.dev.clock  = 7;
    if (q0 <= mark) w.dev.under_at = w.dev.clock;
    w.r = bc5_p406a_wait(mark, w.dev.clock, 1000000ull, rate, FQueued, FNow, FSleep, FClear, &w.dev, &w.cleared);
    return w;
}
static FakeDev run_old(uint64_t q0, uint32_t mark, uint32_t chunk, uint32_t period) {
    FakeDev d;
    d.q      = q0;
    d.mark   = mark;
    d.chunk  = chunk;
    d.period = period;
    d.clock  = 7;
    if (q0 <= mark) d.under_at = d.clock;
    old_loop(d, d.clock);
    return d;
}
static bool all_between(const std::vector<uint32_t>& v, uint32_t lo, uint32_t hi) {
    return std::all_of(v.begin(), v.end(), [lo, hi](uint32_t x) { return x >= lo && x <= hi; });
}
static void Wait() {
    Begin("the wait");
    // (a) 48 kHz stereo s16, the device takes 192 bytes a ms: 25 ms queued, the mark at 5 ms: 20 ms to wait.
    {
        const WaitRun w = run_wait(192 * 25, 192 * 5, 192, 1000, 192);
        const FakeDev o = run_old(192 * 25, 192 * 5, 192, 1000);
        CHECKW(w.r == 10 && w.dev.sleeps.size() == 10 && all_between(w.dev.sleeps, 2000, 2000) && w.cleared == 0 && w.dev.clears == 0, std::to_string(w.r));
        CHECK(w.dev.q <= w.dev.mark && w.dev.clock - w.dev.under_at <= 2000); // it ends at most 2 ms after the queue reached the mark
        CHECKW(o.sleeps.size() == 40 && o.q <= o.mark && o.clock - o.under_at <= 500, std::to_string(o.sleeps.size()));
        CHECK(w.dev.reads == w.r + 1);
    }
    // (b) 50 bytes over the mark: the floor (500 us), as the old poll.
    {
        const WaitRun w = run_wait(960 + 50, 960, 192, 1000, 192);
        CHECKW(w.r == 2 && all_between(w.dev.sleeps, 500, 500) && w.dev.q <= 960, std::to_string(w.r));
    }
    // (c) a device that takes 1024 frames (4096 bytes) every 21,333 us: three pieces queued, the mark at one.
    {
        const WaitRun w = run_wait(3 * 4096, 4096, 4096, 21333, 192);
        const FakeDev o = run_old(3 * 4096, 4096, 4096, 21333);
        CHECK(w.dev.q <= 4096 && all_between(w.dev.sleeps, 500, 2000) && w.dev.clock - w.dev.under_at <= 2000);
        CHECKW(o.q <= 4096 && w.dev.sleeps.size() * 3 < o.sleeps.size(), std::to_string(w.dev.sleeps.size()) + " against " + std::to_string(o.sleeps.size()));
    }
    // (d) a device that has stopped: the clear after 1 s without progress, as the old loop, in a quarter of its wake-ups.
    {
        const WaitRun w = run_wait(10000, 1000, 0, 1000, 192);
        const FakeDev o = run_old(10000, 1000, 0, 1000);
        CHECKW(w.cleared == 1 && w.dev.clears == 1 && w.dev.q == 0 && w.dev.clock - 7 > 1000000ull && w.dev.clock - 7 <= 1002000ull, std::to_string(w.dev.clock));
        CHECKW(w.r == 501 && all_between(w.dev.sleeps, 2000, 2000), std::to_string(w.r));
        CHECKW(o.clears == 1 && o.sleeps.size() == 2001, std::to_string(o.sleeps.size()));
    }
    // (e) at or under the mark already: no sleep, one read.
    {
        const WaitRun w = run_wait(500, 960, 192, 1000, 192);
        CHECK(w.r == 0 && w.dev.sleeps.empty() && w.dev.reads == 1 && w.cleared == 0);
    }
    // (f) the rate not known: the old poll's 500 us.
    {
        const WaitRun w = run_wait(192 * 25, 192 * 5, 192, 1000, 0);
        CHECKW(w.r == 40 && all_between(w.dev.sleeps, 500, 500), std::to_string(w.r));
    }
    End("pure");
}

#ifdef P406_STANDIN
// ---- 11. (stand-in) the real learned_load and learned_apply (mode) --------------------------------------------------------
static void Apply(int pm) {
    Begin("learned_load and learned_apply (stand-in)");
    const bool            full = pm == 2, skip = pm != 0; // the junk drop: the full mode only; the eager skip: either on mode
    const Layout          l    = layout();
    std::vector<uint64_t> mapped(200), filled(200);
    uint32_t              nm = 0, nf = 0;
    std::vector<uint64_t> kept, want_mapped;
    for (const uint64_t a: kExp0288)
        if (!full || !ref_junk(a)) kept.push_back(a);
    for (const uint64_t a: kept)
        if (!skip || !ref_inside(l, a, kWin)) want_mapped.push_back(a);
    const auto same = [](const std::vector<uint64_t>& got, uint32_t n, const std::vector<uint64_t>& want) {
        if (n != want.size()) return false;
        for (uint32_t k = 0; k < n; k++)
            if (got[k] != want[k]) return false;
        return true;
    };
    // a pass with the memfd and sorted views
    const char* const prune_line = "learned prune (exp 0406 p406): 107 learned windows loaded, 75 kept, 32 dropped at junk addresses";
    CHECK(p406si_journal_count(prune_line) == (full ? 1u : 0u)); // the load case's call of the hook
    p406si_views(l.va.data(), l.size.data(), l.eager.data(), l.name.data(), l.count(), 1, 1);
    uint32_t learned = p406si_apply(mapped.data(), &nm, filled.data(), &nf, 200);
    CHECKW(learned == (full ? 75u : 107u), std::to_string(learned)); // eager mode: all 107 stay loaded
    CHECKW(same(mapped, nm, want_mapped), std::to_string(nm));      // map_window: every kept window but the ones inside
    CHECKW(same(filled, nf, kept), std::to_string(nf));             // scratch_fill: every kept window, as today
    CHECKW(nm == (full ? 51u : skip ? 83u : 107u) && nf == (full ? 75u : 107u), std::to_string(nm) + " " + std::to_string(nf));
    CHECK(p406si_journal_count(prune_line) == (full ? 2u : 0u));      // learned_load's, once
    CHECK(p406si_journal_count("lies inside eager views (the first: ") == (skip ? kInside : 0u));
    CHECK(p406si_journal_count("window 0x117e000000+0x6000000 lies inside eager views (the first: RenderGpuWcLarge at 0x1140000000+0x40000000)") == (skip ? 1u : 0u));
    CHECK(p406si_journal_count("window 0x81c6000000+0x6000000 lies inside eager views (the first: AMM at 0x81c6000000+0x1000000)") == (skip ? 1u : 0u));
    CHECK(bc5_p406_skips() == (skip ? kInside : 0u));
    // a second pass: the same, and each window's line only once
    learned = p406si_apply(mapped.data(), &nm, filled.data(), &nf, 200);
    CHECK(learned == (full ? 75u : 107u) && same(mapped, nm, want_mapped) && same(filled, nf, kept));
    CHECK(p406si_journal_count("lies inside eager views (the first: ") == (skip ? kInside : 0u) && bc5_p406_skips() == (skip ? 2 * kInside : 0u));
    // no memfd, then views not sorted: map_window for every kept window
    p406si_views(l.va.data(), l.size.data(), l.eager.data(), l.name.data(), l.count(), 1, 0);
    p406si_apply(mapped.data(), &nm, filled.data(), &nf, 200);
    CHECKW(same(mapped, nm, kept) && same(filled, nf, kept), std::to_string(nm));
    p406si_views(l.va.data(), l.size.data(), l.eager.data(), l.name.data(), l.count(), 0, 1);
    p406si_apply(mapped.data(), &nm, filled.data(), &nf, 200);
    CHECKW(same(mapped, nm, kept) && same(filled, nf, kept), std::to_string(nm));
    CHECK(bc5_p406_skips() == (skip ? 2 * kInside : 0u));
    // the switch's own line, once, naming the mode
    const char* const line = full ? "exp 0406 (p406): learned prune on, mode full (" : skip ? "exp 0406 (p406): learned prune on, mode eager (" : "exp 0406 (p406): learned prune off (";
    CHECK(p406si_journal_count(line) == 1);
    End(how(pm));
}

// ---- 12. (stand-in) the real text of QueueSdlAudio's wait (mode) ----------------------------------------------------------
static void AudioWait(bool on) { // on: AUDIO_SLEEP
    Begin("QueueSdlAudio's wait (stand-in)");
    uint32_t sl[4000], n = 0, reads = 0, clears = 0;
    uint64_t elapsed = 0, blocked = 0;
    // 25 ms queued, the mark at 5 ms (48 kHz stereo s16: 192 bytes a ms)
    uint32_t q = p406si_audio(192 * 25, 192 * 5, 192, 1000, sl, 4000, &n, &reads, &clears, &elapsed, &blocked);
    std::vector<uint32_t> v(sl, sl + std::min<uint32_t>(n, 4000));
    CHECKW(q <= 192 * 5 && clears == 0 && blocked == elapsed, std::to_string(q));
    if (on) {
        CHECKW(n == 10 && all_between(v, 2000, 2000), std::to_string(n));
        CHECKW(reads == 1 + 11 + 1, std::to_string(reads)); // the trace's read, the computed wait's 11, the old loop's one test
    } else {
        CHECKW(n == 40 && all_between(v, 500, 500), std::to_string(n));
        CHECKW(reads == 1 + 41, std::to_string(reads)); // the trace's read, the old loop's 41 tests
    }
    // a device that has stopped
    q = p406si_audio(10000, 1000, 0, 1000, sl, 4000, &n, &reads, &clears, &elapsed, &blocked);
    CHECKW(q == 0 && clears == 1 && elapsed > 1000000ull && elapsed <= 1002000ull, std::to_string(elapsed));
    CHECKW(n == (on ? 501u : 2001u), std::to_string(n));
    End(on ? "new path" : "old path");
}
#endif

} // namespace p4060401

#ifdef _WIN32
static void set_env(const char* n, const char* v) { _putenv_s(n, v == nullptr ? "" : v); }
#else
static void set_env(const char* n, const char* v) {
    if (v == nullptr) ::unsetenv(n);
    else ::setenv(n, v, 1);
}
#endif

int main(int argc, char** argv) {
    using namespace p4060401;
    // mode, LEARNED_PRUNE, AUDIO_SLEEP
    static const char* const modes[6][3] = {{"on", "1", "1"},   {"off", "0", "0"},       {"unset", nullptr, nullptr},
                                            {"empty", "", ""}, {"junk", "yes", "yes"}, {"eager", "eager", "1"}};
    static const int         pms[6]      = {2, 0, 0, 0, 2, 1}; // LEARNED_PRUNE's mode expected: 0 off, 1 eager, 2 full
    int                      m           = -1;
    for (int k = 0; argc == 2 && k < 6; k++)
        if (std::strcmp(argv[1], modes[k][0]) == 0) m = k;
    if (m < 0) {
        std::printf("p4060401: usage: p4060401 on | off | unset | empty | junk | eager\n");
        return 2;
    }
    const int  pm = pms[m];
    const bool ao = m == 0 || m == 4 || m == 5; // AUDIO_SLEEP on
    set_env("BC5_0406_LEARNED_PRUNE", modes[m][1]);
    set_env("BC5_0406_AUDIO_SLEEP", modes[m][2]);
#ifdef P406_STANDIN
    { // the stand-in's learned file: exp 0288's list (learned_load reads it once, BC5_DIRECT_LEARNED read once)
        FILE* f = std::fopen("p4060401-learned.tmp", "wb");
        if (f == nullptr) {
            std::printf("p4060401: FAIL setup: cannot write p4060401-learned.tmp\n");
            return 1;
        }
        for (const uint64_t a: kExp0288) std::fprintf(f, "0x%" PRIx64 " 0x%" PRIx64 "\n", a, kWin);
        std::fclose(f);
        set_env("BC5_DIRECT_LEARNED", "p4060401-learned.tmp");
    }
#endif
    std::thread([] {
        std::this_thread::sleep_for(std::chrono::seconds(60));
        std::printf("p4060401: FAIL watchdog: case \"%s\" still running after 60 s\n", g_case.load());
        std::fflush(stdout);
        std::_Exit(3);
    }).detach();

    Switches(pm, ao);
    Parse();
    Lines();
    Junk();
    Load(pm);
    Inside();
    Gate(pm);
    Tick(pm);
    DrainSleep();
    Wait();
#ifdef P406_STANDIN
    Apply(pm);
    AudioWait(ao);
    std::remove("p4060401-learned.tmp");
#endif

    std::fflush(stderr);
    std::printf("p4060401: %s %d of %d%s\n", modes[m][0], g_pass, g_total, g_pass == g_total ? "; end" : "");
    std::fflush(stdout);
    std::_Exit(g_pass == g_total ? 0 : 1);
}
