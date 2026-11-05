#!/usr/bin/env python3
"""BC5 experiment 0401 series e9, tag p406: exp 0406's proposed code switches (experiments/0406-safeguard-cost-audit/README.md,
"Proposed test build: 0406 = e8 + three code switches", commit f3f8803f), as edits of two units of the e8 tree.
p4060401-notes.md has the design, the costs, the risks and why one of the three is not built.
  BC5_0406_LEARNED_PRUNE    (src/libs/bc5LleAgc.cpp) "eager": learned_apply leaves out map_window for a window that lies
                            entirely inside eager views of direct memory (memfd, sorted views); the junk windows stay loaded
                            and filled as today. "1" (any other on value): that, and at load the learned windows at junk
                            addresses (a bit at 40 or above set, or a base of 0) leave the list. Off: e8's path. On and
                            off, the call site counts learned_apply calls over 5 ms and journals them once a minute.
  BC5_0406_AUDIO_SLEEP=1    (src/libs/audio.cpp) QueueSdlAudio's blocking wait sleeps for the computed drain time to its
                            mark, at least 500 us and at most 2 ms, instead of 500-us polls. Off: e8's loop alone.
                            An audio change: exp 0372's replug check before any play with it on.
  BC5_0406_PROBE_LAZY       not built: its premise does not hold (the timed-out job owns no copy of what it submitted;
                            see the notes), and the top's rule of 2026-11-05 leaves such a switch out.
Each switch: unset, empty or "0" is off, any other value is on (bc5::env_on's reading, F767; for LEARNED_PRUNE, "eager"
is the lesser on mode); read once, one line that names the mode.
Inputs (tree root): src/libs/bc5LleAgc.cpp (pinned: MAIN_MD5) and src/libs/audio.cpp (pinned: AUDIO_MD5). Each anchor occurs
exactly once; every edit keeps braces, parentheses and brackets balanced outside comments and literals; the inserted text is
ASCII; LF line ends; the 'exp 0372' lines of audio.cpp are unchanged; a unit that has the edit already is refused, and so
is an input that is not the pinned one. After editing, the script undoes its edits on each output and asserts that this
gives the input back byte for byte. Prints "<relpath> <md5>" per written file.
CPU test: p4060401.cpp (on, off, unset, empty, junk).
usage: mkp4060401.py <tree root in> <out dir>"""
import hashlib
import os
import sys

MAIN = "src/libs/bc5LleAgc.cpp"
AUDIO = "src/libs/audio.cpp"
MAIN_MD5 = "e8938633a48f1d359c11b690575cd086"   # e9 chain: e8 (bd181169) + zcb + gvw
AUDIO_MD5 = "1f90e7520a6641c8ff3affb06993372d"  # e8's audio.cpp (e5 230f732d + mkfwa0405.py)
PINNED = {MAIN: MAIN_MD5, AUDIO: AUDIO_MD5}
MARKS = (b"BC5_0406_", b"bc5_p406", b"tag p406", b"p406_", b"Bc5AudioSleep")
EXP0372 = b"exp 0372"


def T(text):
    """C++ text written with a visible tab ("»") for each tab of the file's indentation, as ASCII bytes (LF)."""
    return text.replace("»", "\t").encode("ascii")


def tabs(text):
    """C++ written with 4-space indents; the units indent with tabs."""
    out = []
    for line in text.split("\n"):
        body = line.lstrip(" ")
        k = len(line) - len(body)
        out.append("\t" * (k // 4) + " " * (k % 4) + body)
    return "\n".join(out).encode("ascii")


# ============================================ src/libs/bc5LleAgc.cpp ==================================================

# ---- the hooks' declarations, before learned_load -------------------------------------------------------------------
DECL_ANCHOR = b"static void learned_load() {\n"
DECL = tabs(r"""// exp 0406 (tag p406, mkp4060401.py): BC5_0406_LEARNED_PRUNE's hooks, defined in its block after exp 0401 e5's (eq0405)
static void p406_learned_loaded(std::vector<std::pair<uint64_t, uint64_t>>& list); // learned_load: junk windows out (on only)
static bool p406_learned_skip(uint64_t lo, uint64_t n);                            // learned_apply: inside an eager heap (on only)
static void p406_learned_tick(uint64_t took_ns, uint64_t now_ns);                  // the call site: over 5 ms, on and off
""")

# ---- learned_load: the load hook --------------------------------------------------------------------------------------
LOAD_OLD = T(r"""»LOGF("[bc5-direct] learned regions: %zu from %s\n", g_learned.size(), learned_path());
}
""")
LOAD_NEW = T(r"""»LOGF("[bc5-direct] learned regions: %zu from %s\n", g_learned.size(), learned_path());
»p406_learned_loaded(g_learned); // exp 0406 (p406) BC5_0406_LEARNED_PRUNE: the windows at junk addresses dropped (on only)
}
""")

# ---- learned_apply: map_window left out for a window inside an eager heap ----------------------------------------------
LOOP_OLD = T(r"""»for (const auto& [a, n]: g_learned) map_window(a, a + n, have, "learned", a);
""")
LOOP_NEW = T(r"""»for (const auto& [a, n]: g_learned) {
»»if (p406_learned_skip(a, n)) continue; // exp 0406 (p406) BC5_0406_LEARNED_PRUNE: inside an eager heap it imports nothing (on only)
»»map_window(a, a + n, have, "learned", a);
»}
""")

# ---- the call site: the minute's count, on and off ------------------------------------------------------------------
TICK_OLD = T(r"""»const uint64_t tc = SoftCp::now_ns();
»if (tc - t1 > 20'000'000ull) { // experiment 0156: a long learned_apply call, with its thread
""")
TICK_NEW = T(r"""»const uint64_t tc = SoftCp::now_ns();
»p406_learned_tick(tc - t1, tc); // exp 0406 (p406): learned_apply calls over 5 ms, one line a minute (on and off)
»if (tc - t1 > 20'000'000ull) { // experiment 0156: a long learned_apply call, with its thread
""")

# ---- the block, after exp 0401 e5's (eq0405) block --------------------------------------------------------------------
BLOCK_ANCHOR = b"// ---- end of exp 0401 series e5 (eq0405)'s block " + b"-" * 70 + b"\n"
PURE_MARK = b"// ---- exp 0406 (tag p406): the learned windows' prune and count, the pure part"
SEAMS_END = b"// ---- end of exp 0406's (tag p406) seams"
BLOCK_END = b"// ---- end of exp 0406's (tag p406) block"
BLOCK = tabs(r"""
// ---- exp 0406 (exp 0401 series e9, tag p406, mkp4060401.py): BC5_0406_LEARNED_PRUNE -------------------------------------
} // namespace Bc5LleKernel (p406 closes it here for its block and opens it again below)

namespace Bc5Gc::Direct {
#if defined(KYTY_BC5_DIRECT)
// ---- exp 0406 (tag p406): the learned windows' prune and count, the pure part -------------------------------------------
// Exp 0406 (experiments/0406-safeguard-cost-audit/README.md, "Proposed test build", item 5; raw/audit0406-memory.md item
// 16): learned_apply runs on the game thread at every layout change. In exp 0288 it took over 5 ms 10,028 times, 83 s of a
// 1,742-s session (at most 633 ms), and its window loop was 6.4 ms of a 7.6-ms call. BC5_0406_LEARNED_PRUNE (read once, one
// journal and stderr line that names the mode): unset, empty and "0" are off (bc5::env_on's reading, F767); "eager" is the
// skip below alone (the junk windows stay loaded and filled as today); any other value ("1") is the skip and the junk drop.
//   - Full mode only: at load, the windows at junk addresses leave the list; the file is not changed. Junk: a base with a bit at 40 or
//     above set, or a base of 0 (exp 0288 README:57-60). map_window imports nothing for them (no view of direct memory
//     and no VMA lies there). scratch_fill did map the zero buffer over such a window below 2^47, and those zero pages go
//     too: the one at 0 is F208's (geometry-engine reads at address 0, removed by F248's BC5_DIRECT_GC_TF_RING=1).
//   - Both modes: learned_apply leaves out map_window for a window that lies entirely inside eager views of direct memory (with the
//     memfd and sorted views). There direct_force only forces chunks the eager import holds already, or leaves skipped
//     (ZLearned), and no anonymous VMA lies under a memfd view, so map_window imports and maps nothing. The window's
//     scratch_fill stays. Its chunks no longer enter the direct state's forced set (p4060401-notes.md, "The skip").
// On or off, the call site counts learned_apply calls over 5 ms and journals the count once a minute, so both arms measure
// the cost. That line is the one thing the switch's off state adds to e8.
// The mode: 0 off (unset, empty, "0": bc5::env_on's reading, F767); 1 "eager": the skip alone; 2 any other value: the skip
// and the junk drop.
static int p406_parse(const char* e) {
    if (e == nullptr || e[0] == 0 || (e[0] == '0' && e[1] == 0)) return 0;
    return std::strcmp(e, "eager") == 0 ? 1 : 2;
}
static bool p406_junk(uint64_t base) { // a learned window at a junk address: a bit at 40 or above set, or a base of 0
    return base == 0 || (base >> 40u) != 0;
}
struct P406Prune {
    uint32_t loaded = 0, kept = 0, high = 0, zero = 0;
};
static P406Prune p406_prune(std::vector<std::pair<uint64_t, uint64_t>>& list) { // the junk windows out, the order kept
    P406Prune                                  c;
    std::vector<std::pair<uint64_t, uint64_t>> keep;
    keep.reserve(list.size());
    c.loaded = static_cast<uint32_t>(list.size());
    for (const auto& w: list) {
        if (!p406_junk(w.first)) {
            keep.push_back(w);
            continue;
        }
        if (w.first == 0) c.zero++;
        else c.high++;
    }
    c.kept = static_cast<uint32_t>(keep.size());
    list.swap(keep);
    return c;
}
static void p406_switch_text(int mode, const char* e, char* out, size_t cap) {
    if (mode == 2)
        std::snprintf(out, cap,
                      "exp 0406 (p406): learned prune on, mode full (BC5_0406_LEARNED_PRUNE=%.40s%s): windows at junk addresses dropped at load, map_window left "
                      "out for windows inside eager heaps; learned_apply calls over 5 ms counted, one line a minute",
                      e != nullptr ? e : "", e != nullptr && std::strcmp(e, "1") == 0 ? "" : ", any value but unset, empty, 0 or eager is the full mode");
    else if (mode == 1)
        std::snprintf(out, cap,
                      "exp 0406 (p406): learned prune on, mode eager (BC5_0406_LEARNED_PRUNE=eager): map_window left out for windows inside eager heaps, the "
                      "junk windows kept and filled as e8; learned_apply calls over 5 ms counted, one line a minute");
    else
        std::snprintf(out, cap, "exp 0406 (p406): learned prune off (BC5_0406_LEARNED_PRUNE %s): as e8; learned_apply calls over 5 ms counted, one line a minute",
                      e == nullptr ? "unset" : e[0] == 0 ? "empty" : "=0");
}
static void p406_prune_text(const P406Prune& c, char* out, size_t cap) {
    std::snprintf(out, cap, "learned prune (exp 0406 p406): %u learned windows loaded, %u kept, %u dropped at junk addresses (%u with a bit at 40 or above set, %u at base 0); the file is unchanged",
                  c.loaded, c.kept, c.loaded - c.kept, c.high, c.zero);
}
// True when [lo, lo + n) lies entirely inside eager views. The views are sorted by address and disjoint (DViews::sorted).
// A gap, a view that is not eager, or the views ending before the window does: false. first: the first view under it.
template <class V>
static bool p406_inside_eager(const std::vector<V>& views, uint64_t lo, uint64_t n, size_t* first = nullptr) {
    const uint64_t hi = lo + n;
    if (n == 0 || hi < lo) return false;
    size_t   i   = static_cast<size_t>(std::partition_point(views.begin(), views.end(), [lo](const V& v) { return v.va + v.size <= lo; }) - views.begin());
    uint64_t cur = lo;
    if (first != nullptr) *first = i;
    for (; i < views.size() && views[i].va < hi; i++) {
        const V& v = views[i];
        if (v.size == 0) continue;
        if (!v.eager || v.va > cur) return false;
        if (v.va + v.size > cur) cur = v.va + v.size;
        if (cur >= hi) return true;
    }
    return false;
}
constexpr uint64_t kP406Over   = 5000000ull;     // a call over 5 ms, as learned_apply's own "learned apply:" line counts one
constexpr uint64_t kP406Minute = 60000000000ull; // one line a minute
struct P406Tick {
    bool     started  = false;
    uint64_t start_ns = 0, calls = 0, over = 0, over_ns = 0, max_ns = 0; // this minute
    uint64_t all_over = 0, all_over_ns = 0;                             // since the first call
};
// One call of took_ns, ending at now_ns. True when its minute is over: the line is due, and p406_tick_next starts the next.
static bool p406_tick_add(P406Tick& t, uint64_t took_ns, uint64_t now_ns) {
    if (!t.started) {
        t.started  = true;
        t.start_ns = now_ns;
    }
    t.calls++;
    if (took_ns > kP406Over) {
        t.over++;
        t.over_ns += took_ns;
        if (took_ns > t.max_ns) t.max_ns = took_ns;
        t.all_over++;
        t.all_over_ns += took_ns;
    }
    return now_ns - t.start_ns >= kP406Minute;
}
static void p406_tick_text(const P406Tick& t, uint64_t now_ns, double t_s, bool prune, uint64_t skips, char* out, size_t cap) {
    std::snprintf(out, cap,
                  "learned apply (exp 0406 p406): t %.0f s: %" PRIu64 " of %" PRIu64 " calls in the last %.0f s over 5 ms, %.1f ms in all, the longest %.1f ms; %" PRIu64
                  " over 5 ms so far, %.1f s in all; learned prune %s, %" PRIu64 " windows left out of map_window so far",
                  t_s, t.over, t.calls, static_cast<double>(now_ns - t.start_ns) / 1e9, static_cast<double>(t.over_ns) / 1e6, static_cast<double>(t.max_ns) / 1e6, t.all_over,
                  static_cast<double>(t.all_over_ns) / 1e9, prune ? "on" : "off", skips);
}
static void p406_tick_next(P406Tick& t, uint64_t now_ns) {
    t.start_ns = now_ns;
    t.calls = t.over = t.over_ns = t.max_ns = 0;
}
// ---- exp 0406 (tag p406): the host's side ---------------------------------------------------------------------------------
static int p406_prune_mode() { // BC5_0406_LEARNED_PRUNE, read once: 0 off, 1 eager, 2 full
    static const int mode = [] {
        const char* e = std::getenv("BC5_0406_LEARNED_PRUNE");
        const int   v = p406_parse(e);
        char        line[400];
        p406_switch_text(v, e, line, sizeof(line));
        journal("%s\n", line);
        std::fprintf(stderr, "[bc5] %s\n", line);
        return v;
    }();
    return mode;
}
static bool p406_prune_on() { // either mode: the eager skip
    return p406_prune_mode() != 0;
}
// learned_load, once, after the file is read: in the full mode only, the junk windows leave the list; one line with the counts.
static void p406_learned_loaded(std::vector<std::pair<uint64_t, uint64_t>>& list) {
    if (p406_prune_mode() != 2) return;
    const P406Prune c = p406_prune(list);
    char            line[400];
    p406_prune_text(c, line, sizeof(line));
    journal("%s\n", line);
    std::fprintf(stderr, "[bc5] %s\n", line);
}
static std::atomic<uint64_t> g_p406_skips {0}; // map_window calls left out so far
static std::mutex            g_p406_mutex;     // the windows told, the minute's count
static std::set<uint64_t>    g_p406_told;      // the windows whose first skip was journaled
static P406Tick              g_p406_tick;
// The decision learned_apply's loop takes for one window, on views of the caller's: on, the memfd, sorted views, inside.
template <class V>
static bool p406_skip_with(const std::vector<V>& views, bool sorted, bool memfd, uint64_t lo, uint64_t n, size_t* first = nullptr) {
    if (!p406_prune_on() || !memfd || !sorted) return false;
    return p406_inside_eager(views, lo, n, first);
}
// learned_apply, each window: true leaves out its map_window. The views are the ones the pass pinned (t_pinned_views).
static bool p406_learned_skip(uint64_t lo, uint64_t n) {
    if (!p406_prune_on()) return false;
    const bool memfd = dstate_fd(g_d[0]) >= 0;
    if (!memfd) return false;
    const auto views_p = t_pinned_views[0] ? t_pinned_views[0] : direct_views(g_d[0]);
    size_t     first   = 0;
    if (!p406_skip_with(views_p->v, views_p->sorted, memfd, lo, n, &first)) return false;
    g_p406_skips++;
    bool tell = false;
    {
        std::lock_guard lk(g_p406_mutex);
        tell = g_p406_told.insert(lo).second;
    }
    if (tell && first < views_p->v.size())
        journal("learned prune (exp 0406 p406): window 0x%" PRIx64 "+0x%" PRIx64 " lies inside eager views (the first: %s at 0x%" PRIx64 "+0x%" PRIx64 "): map_window left "
                "out while it does; its scratch fill stays\n",
                lo, n, views_p->v[first].name.c_str(), views_p->v[first].va, views_p->v[first].size);
    return true;
}
// The minute's count of one call: true and its line when the minute is over. t_s: the journal's time (nullptr: now).
static bool p406_tick_now(uint64_t took_ns, uint64_t now_ns, const double* t_s, char* out, size_t cap) {
    std::lock_guard lk(g_p406_mutex);
    if (!p406_tick_add(g_p406_tick, took_ns, now_ns)) return false;
    p406_tick_text(g_p406_tick, now_ns, t_s != nullptr ? *t_s : timing_now(), p406_prune_on(), g_p406_skips.load(), out, cap);
    p406_tick_next(g_p406_tick, now_ns);
    return true;
}
static void p406_learned_tick(uint64_t took_ns, uint64_t now_ns) { // the call site, every submission, on and off
    char line[512];
    if (p406_tick_now(took_ns, now_ns, nullptr, line, sizeof(line))) journal("%s\n", line);
}
// ---- exp 0406 (tag p406): the CPU test's seams (p4060401.cpp); always compiled in, never called by the emulator ----------
extern "C" int bc5_p406_parse(const char* e) { // the mode: 0 off, 1 eager, 2 full
    return p406_parse(e);
}
extern "C" int bc5_p406_prune_mode() { // the unit's reading of the switch
    return p406_prune_mode();
}
extern "C" int bc5_p406_junk(uint64_t base) {
    return p406_junk(base) ? 1 : 0;
}
extern "C" void bc5_p406_consts(uint64_t* out) { // kP406Over, kP406Minute
    out[0] = kP406Over;
    out[1] = kP406Minute;
}
extern "C" void bc5_p406_switch_line(int mode, const char* e, char* out, uint32_t cap) {
    p406_switch_text(mode, e, out, cap);
}
extern "C" void bc5_p406_prune_line(uint32_t loaded, uint32_t kept, uint32_t high, uint32_t zero, char* out, uint32_t cap) {
    P406Prune c;
    c.loaded = loaded;
    c.kept   = kept;
    c.high   = high;
    c.zero   = zero;
    p406_prune_text(c, out, cap);
}
// The real load hook (p406_learned_loaded) on a list of the test's own (base, bytes): the list it keeps, in place; its length.
extern "C" uint32_t bc5_p406_loaded(uint64_t* base, uint64_t* bytes, uint32_t count) {
    std::vector<std::pair<uint64_t, uint64_t>> list;
    for (uint32_t k = 0; k < count; k++) list.emplace_back(base[k], bytes[k]);
    p406_learned_loaded(list);
    for (size_t k = 0; k < list.size(); k++) {
        base[k]  = list[k].first;
        bytes[k] = list[k].second;
    }
    return static_cast<uint32_t>(list.size());
}
static std::vector<DView> p406_seam_views(const uint64_t* va, const uint64_t* size, const uint8_t* eager, uint32_t count) {
    std::vector<DView> v;
    for (uint32_t k = 0; k < count; k++) v.push_back({va[k], size[k], va[k], eager[k] != 0 ? "eager" : "other", false, eager[k] != 0});
    return v;
}
// The pure test on views of the test's own (sorted by address, disjoint).
extern "C" int bc5_p406_inside(const uint64_t* va, const uint64_t* size, const uint8_t* eager, uint32_t count, uint64_t lo, uint64_t n) {
    return p406_inside_eager(p406_seam_views(va, size, eager, count), lo, n) ? 1 : 0;
}
// The switch-gated decision of learned_apply's loop (p406_skip_with, as p406_learned_skip calls it) on views of the test's own.
extern "C" int bc5_p406_skip_with(const uint64_t* va, const uint64_t* size, const uint8_t* eager, uint32_t count, int sorted, int memfd, uint64_t lo, uint64_t n) {
    return p406_skip_with(p406_seam_views(va, size, eager, count), sorted != 0, memfd != 0, lo, n) ? 1 : 0;
}
// The real minute count (the unit's own state) at times of the test's own: 1 and the line when one is due.
extern "C" int bc5_p406_tick(uint64_t took_ns, uint64_t now_ns, double t_s, char* out, uint32_t cap) {
    return p406_tick_now(took_ns, now_ns, &t_s, out, cap) ? 1 : 0;
}
extern "C" uint64_t bc5_p406_skips() {
    return g_p406_skips.load();
}
// ---- end of exp 0406's (tag p406) seams -----------------------------------------------------------------------------------
#endif
} // namespace Bc5Gc::Direct

namespace Bc5LleKernel {
// ---- end of exp 0406's (tag p406) block -----------------------------------------------------------------------------------
""")

MAIN_EDITS = [
    ("the hooks' declarations", DECL_ANCHOR, DECL + DECL_ANCHOR),
    ("learned_load: the load hook", LOAD_OLD, LOAD_NEW),
    ("learned_apply: the skip", LOOP_OLD, LOOP_NEW),
    ("the call site: the minute's count", TICK_OLD, TICK_NEW),
    ("the block", BLOCK_ANCHOR, BLOCK_ANCHOR + BLOCK),
]

# ================================================ src/libs/audio.cpp ==================================================

A_ANCHOR = b"// ---- end of tag fwa's switch ----\n"
A_END = b"// ---- end of tag p406's switch ----"
A_BLOCK = tabs(r"""
// ---- experiment 0406, series e9 of experiment 0401, tag p406 (mkp4060401.py): BC5_0406_AUDIO_SLEEP ----
// Exp 0406 (README "Proposed test build"; raw/audit0406-host.md item 1): QueueSdlAudio's blocking wait polls the queue every
// 500 us, about 2,000 wake-ups a second on the title's audio thread (nice -15), each taking SDL's device lock. With the
// switch on, each sleep is the time the device needs to play the queue down to the wait's mark at its own rate (freq x
// channels x bytes a sample), at least the old 500 us and at most 2 ms. The mark, the order of the checks and the clear
// after 1 s without progress are the old loop's. The old loop then finds the queue at or under the mark (or cleared) and
// ends at once: one more queue read a call. TODO(verify): SDL takes the queue in callback-sized pieces, not evenly, so the
// computed time is the earliest the queue can reach the mark. A value: unset, empty or "0" is off (the old 500-us poll
// alone); any other value is on (bc5::env_on's reading, F767). Read once, one stderr line. An audio change: experiment
// 0372's software replug check (s6n0372.sh with replug0372.sh, P1 and P2), then the maintainer's physical replug and a
// DualShock 4, before any play with it on.
static constexpr uint32_t BC5_0406_SLEEP_MIN_US = 500;  // the old poll: never more wake-ups than today
static constexpr uint32_t BC5_0406_SLEEP_MAX_US = 2000; // the cap (exp 0406)

static bool Bc5AudioSleepParse(const char* e) {
    return e != nullptr && e[0] != '\0' && std::strcmp(e, "0") != 0;
}

static bool Bc5AudioSleepOn() {
    static const bool on = [] {
        const char* e = std::getenv("BC5_0406_AUDIO_SLEEP");
        const bool  v = Bc5AudioSleepParse(e);
        if (v) {
            std::fprintf(stderr, "[bc5] exp 0406 (p406): audio sleep on (BC5_0406_AUDIO_SLEEP=%.40s%s): the blocking wait sleeps the drain time, 500 us to 2 ms\n", e,
                         std::strcmp(e, "1") == 0 ? "" : ", any value but unset, empty or 0 is on");
        } else {
            std::fprintf(stderr, "[bc5] exp 0406 (p406): audio sleep off (BC5_0406_AUDIO_SLEEP %s): the 500-us poll\n", e == nullptr ? "unset" : e[0] == '\0' ? "empty" : "=0");
        }
        std::fflush(stderr);
        return v;
    }();
    return on;
}

// The bytes the device plays in a millisecond (its spec: freq, channels, bits a sample); 0 when the spec is not known.
static uint32_t Bc5AudioBytesPerMs(int freq, int channels, int bits) {
    if (freq <= 0 || channels <= 0 || bits <= 0) {
        return 0;
    }
    return static_cast<uint32_t>((static_cast<uint64_t>(freq) * static_cast<uint64_t>(channels) * static_cast<uint64_t>(bits)) / 8000u);
}

// One sleep of the wait: the time (queued - mark) bytes take at bytes_per_ms, rounded up, within 500 us and 2 ms; 500 us when
// the rate is not known.
static uint32_t Bc5AudioSleepUs(uint32_t queued, uint32_t mark, uint32_t bytes_per_ms) {
    if (bytes_per_ms == 0 || queued <= mark) {
        return BC5_0406_SLEEP_MIN_US;
    }
    const uint64_t us = (static_cast<uint64_t>(queued - mark) * 1000u + bytes_per_ms - 1u) / bytes_per_ms;
    return static_cast<uint32_t>(std::clamp<uint64_t>(us, BC5_0406_SLEEP_MIN_US, BC5_0406_SLEEP_MAX_US));
}

// The wait with the switch on: the old loop's checks in its order (the mark, then the 1-s clear), with the computed sleep.
// queued(): the queue's bytes; now_us(): the process time; sleep_us(us); clear(). Returns the sleeps; *cleared after a clear.
template <class Queued, class Now, class Sleep, class Clear>
static uint32_t Bc5AudioSleepWait(uint32_t mark, uint64_t start_us, uint64_t timeout_us, uint32_t bytes_per_ms, Queued queued, Now now_us, Sleep sleep_us, Clear clear,
                                  bool* cleared) {
    uint32_t sleeps = 0;
    for (;;) {
        const uint32_t q = queued();
        if (q <= mark) {
            break;
        }
        if (now_us() - start_us > timeout_us) {
            clear();
            *cleared = true;
            break;
        }
        sleep_us(Bc5AudioSleepUs(q, mark, bytes_per_ms));
        sleeps++;
    }
    return sleeps;
}

// The CPU test's seams (p4060401.cpp); always compiled in, never called by the emulator.
typedef uint32_t (*Bc5P406aQueued)(void* ctx);
typedef uint64_t (*Bc5P406aNow)(void* ctx);
typedef void (*Bc5P406aSleep)(uint32_t us, void* ctx);
typedef void (*Bc5P406aClear)(void* ctx);
extern "C" int bc5_p406a_parse(const char* e) {
    return Bc5AudioSleepParse(e) ? 1 : 0;
}
extern "C" int bc5_p406a_on() { // the unit's reading of the switch
    return Bc5AudioSleepOn() ? 1 : 0;
}
extern "C" uint32_t bc5_p406a_rate(int freq, int channels, int bits) {
    return Bc5AudioBytesPerMs(freq, channels, bits);
}
extern "C" uint32_t bc5_p406a_sleep_us(uint32_t queued, uint32_t mark, uint32_t bytes_per_ms) {
    return Bc5AudioSleepUs(queued, mark, bytes_per_ms);
}
// The real wait (Bc5AudioSleepWait) on a queue and clock of the test's own; *cleared 1 after a clear.
extern "C" uint32_t bc5_p406a_wait(uint32_t mark, uint64_t start_us, uint64_t timeout_us, uint32_t bytes_per_ms, Bc5P406aQueued q, Bc5P406aNow n, Bc5P406aSleep s,
                                   Bc5P406aClear c, void* ctx, int* cleared) {
    bool           cl = false;
    const uint32_t r  = Bc5AudioSleepWait(
        mark, start_us, timeout_us, bytes_per_ms, [q, ctx] { return q(ctx); }, [n, ctx] { return n(ctx); }, [s, ctx](uint32_t us) { s(us, ctx); }, [c, ctx] { c(ctx); }, &cl);
    *cleared = cl ? 1 : 0;
    return r;
}
// ---- end of tag p406's switch ----
""")

W_ANCHOR = b"\t\twhile (SDL_GetQueuedAudioSize(port->audio_device) > min_queued_size) {\n"
W_INSERT = T(r"""»»if (Bc5AudioSleepOn()) { // experiment 0406 (p406, BC5_0406_AUDIO_SLEEP): the computed sleep; the old loop below then ends at once
»»»bool cleared = false;
»»»Bc5AudioSleepWait(
»»»    static_cast<uint32_t>(min_queued_size), wait_start, timeout_us,
»»»    Bc5AudioBytesPerMs(port->audio_spec.freq, port->audio_spec.channels, SDL_AUDIO_BITSIZE(port->audio_spec.format)),
»»»    [port] { return static_cast<uint32_t>(SDL_GetQueuedAudioSize(port->audio_device)); },
»»»    [] { return static_cast<uint64_t>(LibKernel::KernelGetProcessTime()); }, [](uint32_t us) { Common::Thread::SleepMicro(us); },
»»»    [port] { SDL_ClearQueuedAudio(port->audio_device); }, &cleared);
»»»if (cleared) {
»»»»port->tr_clears++;
»»»}
»»}
""")

AUDIO_EDITS = [
    ("the switch and the wait", A_ANCHOR, A_ANCHOR + A_BLOCK),
    ("QueueSdlAudio: the computed sleep", W_ANCHOR, W_INSERT + W_ANCHOR),
]


def strip_code(b):
    """The text with comments and string/char literals removed (for the balance counts)."""
    out = bytearray()
    i, n = 0, len(b)
    while i < n:
        c = b[i:i + 1]
        if b[i:i + 2] == b"//":
            j = b.find(b"\n", i)
            i = n if j < 0 else j
        elif b[i:i + 2] == b"/*":
            j = b.find(b"*/", i + 2)
            i = n if j < 0 else j + 2
        elif c in (b'"', b"'"):
            j = i + 1
            while j < n and b[j:j + 1] != c:
                j += 2 if b[j:j + 1] == b"\\" else 1
            i = j + 1
        else:
            out += c
            i += 1
    return bytes(out)


def balance(b):
    s = strip_code(b)
    return (s.count(b"{") - s.count(b"}"), s.count(b"(") - s.count(b")"), s.count(b"[") - s.count(b"]"))


def md5(b):
    return hashlib.md5(b).hexdigest()


def apply(s, edits, rel):
    for m in MARKS:
        assert m not in s, ("the unit has the edit already", rel, m)
    assert b"\r" not in s, ("a CR in the LF unit", rel)
    done = []
    out = s
    for name, old, new in edits:
        assert out.count(old) == 1, ("an anchor does not occur exactly once", rel, name, out.count(old))
        assert balance(old) == balance(new), ("the edit changes the balance", rel, name, balance(old), balance(new))
        new.decode("ascii")
        assert b"\r" not in new, ("a CR in the inserted text", rel, name)
        out = out.replace(old, new)
        done.append((old, new, name))
    assert balance(out) == balance(s), ("the unit's balance changed", rel, balance(s), balance(out))
    back = out
    for old, new, name in reversed(done):
        assert back.count(new) == 1, ("undo", rel, name)
        back = back.replace(new, old)
    assert back == s, ("undoing the edits does not give the input back", rel)
    assert out.startswith(b"\xef\xbb\xbf") == s.startswith(b"\xef\xbb\xbf"), ("the BOM changed", rel)
    return out


def edit_main(s):
    out = apply(s, MAIN_EDITS, MAIN)
    # Where things landed: the declarations before learned_load, learned_apply's loop, the call site, exp 0401 e5's end
    # marker, then the block (pure part, host side, seams) and the libkernel code that follows it.
    order = [out.index(x) for x in (b"static std::vector<std::pair<uint64_t, uint64_t>> g_learned;", b"static void p406_learned_loaded(std::vector", DECL_ANCHOR,
                                    b"\tp406_learned_loaded(g_learned);", b"static void learned_apply() {", b"\t\tif (p406_learned_skip(a, n)) continue;",
                                    b"\tp406_learned_tick(tc - t1, tc);", BLOCK_ANCHOR, b"} // namespace Bc5LleKernel (p406 closes it here", PURE_MARK,
                                    b"static bool p406_prune_on() {", b"extern \"C\" int bc5_p406_parse(", SEAMS_END, BLOCK_END,
                                    b"// mmap(addr, len, prot, flags, fd, offset).")]
    assert order == sorted(order), ("the edits are out of order", order)
    # the hooks: declaration, call, definition (and the load hook's seam); p406_prune_on(): definition, its three host uses
    # (the skip's two gates, the minute line); p406_prune_mode(): definition, p406_prune_on, the load hook, the seam's name
    # and body; the predicate: definition, p406_skip_with, its seam; p406_skip_with: definition, the window hook, the seam's
    # name and body
    counts = (out.count(b"p406_learned_loaded("), out.count(b"p406_learned_skip("), out.count(b"p406_learned_tick("), out.count(b"p406_prune_on()"),
              out.count(b"p406_prune_mode()"), out.count(b"p406_inside_eager("), out.count(b"p406_skip_with("))
    assert counts == (4, 3, 3, 4, 5, 3, 4), ("the helpers' uses", counts)
    # the block's preprocessor and namespace lines pair up: one #if/#endif, Bc5LleKernel closed once and opened again
    blk = out[out.index(BLOCK_ANCHOR):out.index(BLOCK_END)]
    assert blk.count(b"\n#if defined(KYTY_BC5_DIRECT)\n") == 1 and blk.count(b"\n#endif\n") == 1, "the block's #if"
    assert blk.count(b"\n} // namespace Bc5LleKernel") == 1 and blk.count(b"\nnamespace Bc5LleKernel {\n") == 1, "the block's namespaces"
    assert blk.count(b"\nnamespace Bc5Gc::Direct {\n") == 1 and blk.count(b"\n} // namespace Bc5Gc::Direct\n") == 1, "the block's namespaces"
    return out


def edit_audio(s):
    before = [ln for ln in s.split(b"\n") if EXP0372 in ln]
    out = apply(s, AUDIO_EDITS, AUDIO)
    after = [ln for ln in out.split(b"\n") if EXP0372 in ln]
    assert before == after and len(before) > 0, ("the 'exp 0372' lines changed", len(before), len(after))
    order = [out.index(x) for x in (A_ANCHOR, b"static bool Bc5AudioSleepOn() {", b"extern \"C\" int bc5_p406a_parse(", A_END, b"namespace AudioInternal {",
                                    b"bool Audio::QueueSdlAudio(PortOut* port, const void* data, bool blocking) {", b"\t\tif (Bc5AudioSleepOn()) {", W_ANCHOR,
                                    b"\t\tport->tr_blocked_us += LibKernel::KernelGetProcessTime() - wait_start;")]
    assert order == sorted(order), ("the edits are out of order", order)
    counts = (out.count(b"Bc5AudioSleepOn()"), out.count(b"Bc5AudioSleepWait("), out.count(b"Bc5AudioSleepUs("), out.count(b"Bc5AudioBytesPerMs("))
    assert counts == (3, 3, 3, 3), ("the helpers' uses", counts)
    return out, len(before)


def main():
    assert len(sys.argv) == 3, __doc__
    root, outdir = sys.argv[1], sys.argv[2]
    assert os.path.abspath(root) != os.path.abspath(outdir), "the out dir must not be the tree"
    ins = {}
    for rel in (MAIN, AUDIO):
        with open(os.path.join(root, rel), "rb") as f:
            s = f.read()
        for m in MARKS:
            assert m not in s, ("refused: the unit has the edit already", rel, m.decode())
        assert md5(s) == PINNED[rel], ("refused: not the pinned input", rel, md5(s), PINNED[rel])
        ins[rel] = s
    outs = {MAIN: edit_main(ins[MAIN])}
    outs[AUDIO], n0372 = edit_audio(ins[AUDIO])
    for rel in (MAIN, AUDIO):
        print(f"# in:  {rel} {md5(ins[rel])}  ({len(ins[rel])} bytes, LF)", file=sys.stderr)
    print(f"# 'exp 0372' in {AUDIO}: {n0372} lines before and after", file=sys.stderr)
    for rel in (MAIN, AUDIO):
        dst = os.path.join(outdir, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "wb") as f:
            f.write(outs[rel])
        print(f"{rel} {md5(outs[rel])}")


if __name__ == "__main__":
    main()
