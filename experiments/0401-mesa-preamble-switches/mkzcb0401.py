#!/usr/bin/env python3
"""BC5 experiment 0401 series e9, tag "zcb": the zero skip's side of the e9 build, as one edit of src/libs/bc5LleAgc.cpp
after series e8 (zsk, lzr, cap, flx, smp). hang1954-0401.md, sections "Deep analysis 2026-11-05 (after e8)" and "Box reads
after the analysis", is why; zcb0401-notes.md has the design, the costs and the risks. Four switches, each default off:
  BC5_DIRECT_ZERO_SKIP_EXCLUDE=<hex>[,<hex>...]  fix: a run of the zero list whose file offset (as the journal prints it,
                                                 "file 0x22da00000") is listed is placed as normal memory, not skipped (up
                                                 to 16 entries; bad ones are reported and ignored)
  BC5_DIRECT_ZERO_SKIP_COPYBACK=1                fix: at a canary hit, after a bounded wait for the jobs in flight
                                                 (Device::wait_idle), the run's slice goes into each chunk of the run that
                                                 is still skipped (its non-zero pages, pwrite on the direct-memory memfd),
                                                 before the real chunks are imported and mapped
  BC5_DIRECT_ZERO_SKIP_PROBE=1                   catcher (CPU only, lines only): each take-back journaled; at a fence
                                                 timeout the last 4 and what the stuck job's own records touch
  BC5_DIRECT_SCRATCH_WATCH=1                     catcher (CPU only): a thread scans the hole scratch BO every 50 ms
Unset, empty, "0" or "off": e8's path (each switch adds its one switch line and nothing else).
Unit (one input): src/libs/bc5LleAgc.cpp, series e8's bd181169 (PINNED below, the one constant to re-pin).
Edits (each anchor exactly once in the unit): a block of declarations in exp 0379's zero-skip block, before zskip_release
(the functions below are called from zskip_map, zskip_resolve and zskip_take_back, which come before the block's end);
zskip_map: a snapshot after a mapping pass; zskip_resolve: the switch lines, the exclusion and its report; zskip_take_back:
the copy-back and the probe at a canary hit, the probe for CPU writes, a snapshot at its end; the host block and the CPU
test's seams (bc5_zcb0401_*, always compiled in, never called by the emulator) before the zero-skip block's end line; one
comment line and one call in the scratch BO's creation (scratch_bo); one line before each of exp 0404's two fl_probe
lines (the completion thread, submit_now's sync path). Every edit keeps braces, parentheses and brackets balanced outside
comments and literals; the inserted text is ASCII; LF line ends; a unit that has the edit already is refused, and so is
an unpinned input. Outside the zero-skip block and the scratch BO's creation the unit is asserted unchanged except for the
two timeout lines, and from exp 0404's block on only those two lines are added. After editing, the script undoes its
edits on the output and asserts that this gives the input back byte for byte.
Prints "src/libs/bc5LleAgc.cpp <md5>". CPU test: zcb0401.cpp (--gate zcb0401.cpp <out> --like src/libs/bc5LleAgc.cpp).
usage: mkzcb0401.py <tree root in> <out dir>"""
import hashlib
import os
import sys

REL = "src/libs/bc5LleAgc.cpp"
PINNED = {REL: "bd1811690b685369194602027b61a2d5"}  # e8 chain: d1cfd9bb + zsk + lzr + cap + flx + smp
MARKS = (b"BC5_DIRECT_ZERO_SKIP_EXCLUDE", b"bc5_zcb0401_", b"(tag zcb)")


def tabs(text):
    """The C++ below is written with 4-space indents; the unit indents with tabs."""
    out = []
    for line in text.split("\n"):
        body = line.lstrip(" ")
        k = len(line) - len(body)
        out.append("\t" * (k // 4) + " " * (k % 4) + body)
    return "\n".join(out).encode("ascii")


# ---- 1. declarations, in the zero-skip block before zskip_release ----------------------------------------------------
DECL_ANCHOR = b"// Unmaps the canary mappings that overlap [lo, hi) (a real mapping is about to go there).\n"
DECLS = tabs(r"""// ---- exp 0401 series e9 (tag zcb): the calls zskip_map, zskip_resolve and zskip_take_back make; defined in zcb's host block --
// below (before the end of this block), declared here because those three come first. zcb0401-notes.md.
static void                 zcb_switch_lines();                                         // the four switches, read once; their lines
static bool                 zcb_probe_on();                                             // BC5_DIRECT_ZERO_SKIP_PROBE
static bc5::zero_skip::Heap zcb_exclude(const bc5::zero_skip::Heap& h, uint64_t base); // BC5_DIRECT_ZERO_SKIP_EXCLUDE
static void                 zcb_exclude_done(bool all_placed);                          // entries that matched no run
static void                 zcb_hit(int fd, size_t r);                                  // a canary hit: COPYBACK, PROBE
static void                 zcb_cpu_back(size_t r, const std::vector<uint64_t>& chunks); // CPU writes took chunks back: PROBE
static void                 zcb_take_back_end();                                        // the end of zskip_take_back: PROBE's snapshot
static void                 zcb_snapshot();                                             // the skip by run, for a timeout: PROBE
""") + b"\n"

# ---- 2. zskip_map: the snapshot after a mapping pass --------------------------------------------------------------------
MAP_OLD = b"\tif (added != 0 || failed != 0) journal(\"zero skip: canary +%u mappings (%zu)%s\\n\", added, g_zpieces.size(), failed != 0 ? \"; SOME CANARY MAPS FAILED\" : \"\");\n"
MAP_NEW = (b"\tif (added != 0) zcb_snapshot(); // + exp 0401 e9 (zcb): PROBE keeps the canary mappings by run for a timeout (off: returns at once)\n"
           + MAP_OLD)

# ---- 3. zskip_resolve: the switch lines, the exclusion, its report ------------------------------------------------------
RES_OLD = (b"static bool zskip_resolve(const std::vector<DView>& views) {\n"
           b"\tif (zskip_path() == nullptr || g_zskip_off || g_zskip_placed.size() == g_zskip_list.size() + 1) return false;\n")
RES_NEW = (b"static bool zskip_resolve(const std::vector<DView>& views) {\n"
           b"\tzcb_switch_lines(); // + exp 0401 e9 (zcb): the four switches read once and journaled (unset: each line says off)\n"
           b"\tif (zskip_path() == nullptr || g_zskip_off || g_zskip_placed.size() == g_zskip_list.size() + 1) return false;\n")
PLACE_OLD = tabs(r"""        const uint64_t n = bc5::zero_skip::place(h, base, &g_zskip);
        g_zstat_placed += n;
        placed = true;
        journal("zero skip: %s at file 0x%" PRIx64 ": %.1f MiB in %zu runs skipped\n", h.name.c_str(), base, static_cast<double>(n) / 1048576.0, h.runs.size());
""")
PLACE_NEW = tabs(r"""        const bc5::zero_skip::Heap hz = zcb_exclude(h, base); // + exp 0401 e9 (zcb): BC5_DIRECT_ZERO_SKIP_EXCLUDE leaves the listed runs out (off: h as it is)
        const uint64_t n = bc5::zero_skip::place(hz, base, &g_zskip);
        g_zstat_placed += n;
        placed = true;
        journal("zero skip: %s at file 0x%" PRIx64 ": %.1f MiB in %zu runs skipped\n", h.name.c_str(), base, static_cast<double>(n) / 1048576.0, hz.runs.size());
""")
DONE_OLD = b"\tif (!placed) return false;\n"
DONE_NEW = (b"\tzcb_exclude_done(g_zskip_placed.size() == g_zskip_list.size() + 1); // + exp 0401 e9 (zcb): an entry that matched no run, once every heap is placed or refused\n"
            + DONE_OLD)

# ---- 4. zskip_take_back: a canary hit, CPU writes, the end ----------------------------------------------------------------
HIT_OLD = tabs(r"""        g_zflag[r] = 2;
        const auto     [o, l] = g_zskip.run(static_cast<uint32_t>(r));
        const uint64_t n      = g_zskip.erase_run(static_cast<uint32_t>(r));
""")
HIT_NEW = tabs(r"""        g_zflag[r] = 2;
        const auto     [o, l] = g_zskip.run(static_cast<uint32_t>(r));
        zcb_hit(fd, r); // + exp 0401 e9 (zcb): PROBE journals the run; COPYBACK copies its slice into its chunks still skipped, after a bounded wait (off: nothing)
        const uint64_t n      = g_zskip.erase_run(static_cast<uint32_t>(r));
""")
WALK_OLD = tabs(r"""        const auto [o, l] = g_zskip.run(static_cast<uint32_t>(r));
        for (uint64_t pos = o; pos < o + l;) {
            const off_t d = lseek(fd, static_cast<off_t>(pos), SEEK_DATA);
            if (d < 0 || static_cast<uint64_t>(d) >= o + l) break;
            const uint64_t c = static_cast<uint64_t>(d) & ~(kDChunk - 1);
            if (g_zskip.run_of(c) == static_cast<long>(r) && g_zskip.erase_chunk(c)) {
                g_zstat_cpu++;
                g_zleft[r] -= kDChunk;
            }
            pos = c + kDChunk;
        }
    }
}
static void zskip_report() {
""")
WALK_NEW = tabs(r"""        const auto [o, l] = g_zskip.run(static_cast<uint32_t>(r));
        std::vector<uint64_t> zcb_cpu; // + exp 0401 e9 (zcb): the chunks this walk takes back, for PROBE (stays empty when it is off)
        for (uint64_t pos = o; pos < o + l;) {
            const off_t d = lseek(fd, static_cast<off_t>(pos), SEEK_DATA);
            if (d < 0 || static_cast<uint64_t>(d) >= o + l) break;
            const uint64_t c = static_cast<uint64_t>(d) & ~(kDChunk - 1);
            if (g_zskip.run_of(c) == static_cast<long>(r) && g_zskip.erase_chunk(c)) {
                g_zstat_cpu++;
                g_zleft[r] -= kDChunk;
                if (zcb_probe_on()) zcb_cpu.push_back(c); // + exp 0401 e9 (zcb)
            }
            pos = c + kDChunk;
        }
        if (!zcb_cpu.empty()) zcb_cpu_back(r, zcb_cpu); // + exp 0401 e9 (zcb): PROBE journals this take-back
    }
    zcb_take_back_end(); // + exp 0401 e9 (zcb): PROBE keeps the skip by run after a take-back, for a timeout (off: returns at once)
}
static void zskip_report() {
""")

# ---- 5. the host block and the seams, before the zero-skip block's end line ---------------------------------------------
END_LINE = b"// ---- end of experiment 0379's zero skip (exp 0401 e7) -------------------------------------------------------------------\n"
ZCB_HOST = tabs(r"""// ---- exp 0401 series e9 (tag zcb): BC5_DIRECT_ZERO_SKIP_EXCLUDE, _COPYBACK, _PROBE and BC5_DIRECT_SCRATCH_WATCH -------------
// hang1954-0401.md, "Deep analysis 2026-11-05 (after e8)" and "Box reads after the analysis": both e8 F403 hangs came 0.05 to
// 0.11 s after a canary take-back of run 37 (file 0x22da00000, 46 MiB, CommitIABufferAllocator); the 16 clean arms only took
// back run 23 (file 0x1bc400000), without harm. zskip_map maps every chunk of a skipped run onto the same 2 MiB slice of the
// canary, so the GPU's writes alias across the run's chunks; zskip_take_back then maps the real chunks with no copy, and the
// GPU's view of that memory changes between frames, from the aliased canary data to the file's zeros. The hole scratch BO
// (scratch_fill) is one read-write 2 MiB mapping over every hole, and nobody has looked at whether the GPU writes there.
//   BC5_DIRECT_ZERO_SKIP_EXCLUDE=<hex>[,...]  fix: a run of the list at a listed file offset (as "zero skip: canary hit in run
//                                             r (file 0x..." prints it) is placed as normal memory; up to 16, bad ones ignored
//   BC5_DIRECT_ZERO_SKIP_COPYBACK=1           fix: at a canary hit, after a bounded wait for the jobs in flight, the slice's
//                                             non-zero pages go into each chunk of the run still skipped (pwrite on the
//                                             direct-memory memfd), before the real chunks are imported and mapped
//   BC5_DIRECT_ZERO_SKIP_PROBE=1              catcher: each take-back (a canary hit, CPU writes) journaled; at a fence timeout
//                                             the last 4 and whether the stuck job's own records touch such a run
//   BC5_DIRECT_SCRATCH_WATCH=1                catcher: a thread scans the hole scratch BO every 50 ms, as zcanary_watch does
// Each is off when unset, empty, "0" or "off" (e8's path: its switch line is all that is added); "1" or "on" turns one of
// the last three on; anything else is off and its line says so. Every line starts with "exp 0401 e9 (zcb)", "zero skip ...
// (exp 0401 e9 zcb)" or "scratch watch (exp 0401 e9 zcb)", which BC5_DIRECT_JOURNAL_QUIET keeps (journal_quiet_kind drops six
// per-event kinds only, none of these); a line written at a fence timeout says "at the timeout", so the quiet ring goes
// out before the first one. Hints (zskip_hint_back) also take chunks back; PROBE does not see those.
constexpr uint32_t kZcbExcludeMax = 16;          // EXCLUDE: entries at most
constexpr uint64_t kZcbWaitNs     = 500000000ull; // COPYBACK: the bound of Device::wait_idle (it applies it to each ring in turn)
constexpr uint64_t kZcbPage       = 4096;        // COPYBACK writes the slice's non-zero 4 KiB pages only
constexpr size_t   kZcbBacksKept  = 64;          // PROBE: take-backs kept for a timeout ...
constexpr size_t   kZcbBacksShown = 4;           // ... the last 4 journaled there
constexpr size_t   kZcbListShown  = 8;           // VA ranges, chunks and touches named per line
constexpr size_t   kZcbAddrsMax   = 4096;        // PROBE: addresses taken from a stuck job's records
constexpr uint32_t kZcbWatchMs    = 50;          // SCRATCH_WATCH: one scan of the BO per 50 ms
constexpr double   kZcbWatchGapS  = 10.0;        // after the first non-zero bytes, a change line at most every 10 s ...
constexpr uint32_t kZcbWatchLines = 64;          // ... and 64 of them in a session

// The lines: journal(), and the CPU test's capture when zcb0401.cpp turned it on (bc5_zcb0401_capture).
static std::atomic<bool>        g_zcb_capture {false};
static std::mutex               g_zcb_capture_mu;
static std::vector<std::string> g_zcb_captured;
static void zcb_line(const std::string& s) { // s without its newline
    journal("%s\n", s.c_str());
    if (g_zcb_capture.load()) {
        std::lock_guard lk(g_zcb_capture_mu);
        g_zcb_captured.push_back(s);
    }
}
static std::string zcb_fmt(const char* fmt, ...) __attribute__((format(printf, 1, 2)));
static std::string zcb_fmt(const char* fmt, ...) {
    char    b[4096];
    va_list ap;
    va_start(ap, fmt);
    const int k = std::vsnprintf(b, sizeof(b), fmt, ap);
    va_end(ap);
    return k < 0 ? std::string() : std::string(b);
}

// ---- the switches ----
struct ZcbExclude {
    uint64_t    off[kZcbExcludeMax] = {};
    uint32_t    n = 0, bad = 0;
    std::string why; // the bad entries and why, for the switch line
};
static bool zcb_off_word(const char* e) { // unset, empty, "0" or "off"
    return e == nullptr || *e == '\0' || std::strcmp(e, "0") == 0 || std::strcmp(e, "off") == 0;
}
static int zcb_parse_flag(const char* e, bool* bad) { // 0 off, 1 on ("1" or "on"); anything else: 0 and *bad
    *bad = false;
    if (zcb_off_word(e)) return 0;
    if (std::strcmp(e, "1") == 0 || std::strcmp(e, "on") == 0) return 1;
    *bad = true;
    return 0;
}
// Comma-separated file offsets, hex with or without 0x, each 2 MiB aligned (a run starts on a chunk); off as above. An entry
// that is empty, not hex, longer than 16 digits, not aligned, repeated or past the 16th is bad: left out and named in why.
static ZcbExclude zcb_parse_exclude(const char* e) {
    ZcbExclude x;
    if (zcb_off_word(e)) return x;
    const std::string s = e;
    for (size_t at = 0;;) {
        const size_t      comma = s.find(',', at);
        const std::string t     = s.substr(at, comma == std::string::npos ? std::string::npos : comma - at);
        const size_t      k0    = t.size() > 2 && t[0] == '0' && (t[1] == 'x' || t[1] == 'X') ? 2 : 0;
        const char*       why   = t.empty() ? "empty" : t.size() - k0 > 16 ? "more than 16 hex digits" : nullptr;
        uint64_t          v     = 0;
        for (size_t k = k0; why == nullptr && k < t.size(); k++) {
            const char c = t[k];
            const int  d = c >= '0' && c <= '9' ? c - '0' : c >= 'a' && c <= 'f' ? c - 'a' + 10 : c >= 'A' && c <= 'F' ? c - 'A' + 10 : -1;
            if (d < 0) why = "not a hex number";
            else v = (v << 4u) | static_cast<uint64_t>(d);
        }
        if (why == nullptr && v % bc5::zero_skip::kChunk != 0) why = "not 2 MiB aligned";
        for (uint32_t i = 0; why == nullptr && i < x.n; i++) {
            if (x.off[i] == v) why = "repeated";
        }
        if (why == nullptr && x.n == kZcbExcludeMax) why = "past the 16th entry";
        if (why == nullptr) {
            x.off[x.n++] = v;
        } else if (++x.bad <= 8) {
            x.why += (x.why.empty() ? "'" : ", '") + t.substr(0, 24) + (t.size() > 24 ? "...' (" : "' (") + why + ")";
        }
        if (comma == std::string::npos) break;
        at = comma + 1;
    }
    if (x.bad > 8) x.why += zcb_fmt(" and %u more", x.bad - 8);
    return x;
}
struct ZcbSwitches {
    ZcbExclude exclude;
    bool       copyback = false, probe = false, watch = false;
};
static const ZcbSwitches& zcb_sw() { // read once; the four lines go to the journal then, and to stderr
    static const ZcbSwitches sw = [] {
        ZcbSwitches v;
        v.exclude      = zcb_parse_exclude(std::getenv("BC5_DIRECT_ZERO_SKIP_EXCLUDE"));
        bool bad_copy  = false, bad_probe = false, bad_watch = false;
        v.copyback     = zcb_parse_flag(std::getenv("BC5_DIRECT_ZERO_SKIP_COPYBACK"), &bad_copy) != 0;
        v.probe        = zcb_parse_flag(std::getenv("BC5_DIRECT_ZERO_SKIP_PROBE"), &bad_probe) != 0;
        v.watch        = zcb_parse_flag(std::getenv("BC5_DIRECT_SCRATCH_WATCH"), &bad_watch) != 0;
        const char* const no_skip  = zskip_path() == nullptr ? " (the zero skip is off: nothing to do)" : "";
        const char* const no_parse = " (the value does not parse: 1, on, 0 or off)";
        std::string       ex;
        for (uint32_t i = 0; i < v.exclude.n; i++) ex += zcb_fmt("%s0x%" PRIx64, i == 0 ? "" : i + 1 == v.exclude.n ? " or " : ", ", v.exclude.off[i]);
        std::string lines[4];
        lines[0] = v.exclude.n != 0 ? "exp 0401 e9 (zcb): BC5_DIRECT_ZERO_SKIP_EXCLUDE: a run of the zero list at file " + ex + " is placed as normal memory, not skipped" + no_skip
                                    : std::string("exp 0401 e9 (zcb): BC5_DIRECT_ZERO_SKIP_EXCLUDE off");
        if (v.exclude.bad != 0) lines[0] += zcb_fmt("; %u bad %s ignored: %s", v.exclude.bad, v.exclude.bad == 1 ? "entry" : "entries", v.exclude.why.c_str());
        lines[1] = v.copyback ? zcb_fmt("exp 0401 e9 (zcb): BC5_DIRECT_ZERO_SKIP_COPYBACK on: at a canary hit, after a wait of at most %" PRIu64
                                        " ms a ring for the jobs in flight, the slice's non-zero 4 KiB pages go into each chunk of the run still skipped%s",
                                        static_cast<uint64_t>(kZcbWaitNs / 1000000u), no_skip)
                              : std::string("exp 0401 e9 (zcb): BC5_DIRECT_ZERO_SKIP_COPYBACK off") + (bad_copy ? no_parse : "");
        lines[2] = v.probe ? std::string("exp 0401 e9 (zcb): BC5_DIRECT_ZERO_SKIP_PROBE on: each take-back (a canary hit, CPU writes) journaled; at a fence timeout the last 4 and what the "
                                         "stuck job's own records touch") + no_skip
                           : std::string("exp 0401 e9 (zcb): BC5_DIRECT_ZERO_SKIP_PROBE off") + (bad_probe ? no_parse : "");
        lines[3] = v.watch ? std::string("exp 0401 e9 (zcb): BC5_DIRECT_SCRATCH_WATCH on: the hole scratch BO scanned every 50 ms once it is made")
                           : std::string("exp 0401 e9 (zcb): BC5_DIRECT_SCRATCH_WATCH off") + (bad_watch ? no_parse : "");
        for (const std::string& l: lines) {
            zcb_line(l);
            std::fprintf(stderr, "[bc5] %s\n", l.c_str());
        }
        return v;
    }();
    return sw;
}
static void zcb_switch_lines() {
    (void)zcb_sw();
}
static bool zcb_probe_on() {
    return zcb_sw().probe;
}

// ---- EXCLUDE ----
static uint32_t g_zcb_excl_hits[kZcbExcludeMax] = {}; // the runs each entry left out (the syncing thread's)
static bool     g_zcb_excl_reported             = false;
// The heap h (at file offset base) without the runs whose file offset x lists; a line for each run left out; hits[i] counts
// the runs entry i matched.
static bc5::zero_skip::Heap zcb_exclude_with(const bc5::zero_skip::Heap& h, uint64_t base, const ZcbExclude& x, uint32_t* hits) {
    if (x.n == 0) return h;
    bc5::zero_skip::Heap kept {h.name, h.size, h.scans, {}};
    for (const auto& [o, l]: h.runs) {
        uint32_t i = 0;
        while (i < x.n && x.off[i] != base + o) i++;
        if (i == x.n) {
            kept.runs.emplace_back(o, l);
            continue;
        }
        hits[i]++;
        zcb_line(zcb_fmt("zero skip exclude (exp 0401 e9 zcb): %s: the run at file 0x%" PRIx64 " +%.1f MiB is not skipped: it is placed as normal memory (BC5_DIRECT_ZERO_SKIP_EXCLUDE)",
                         h.name.c_str(), base + o, static_cast<double>(l) / 1048576.0));
    }
    return kept;
}
static bc5::zero_skip::Heap zcb_exclude(const bc5::zero_skip::Heap& h, uint64_t base) {
    return zcb_exclude_with(h, base, zcb_sw().exclude, g_zcb_excl_hits);
}
static void zcb_exclude_done(bool all_placed) {
    const ZcbExclude& x = zcb_sw().exclude;
    if (x.n == 0 || !all_placed || g_zcb_excl_reported) return;
    g_zcb_excl_reported = true;
    for (uint32_t i = 0; i < x.n; i++) {
        if (g_zcb_excl_hits[i] == 0)
            zcb_line(zcb_fmt("zero skip exclude (exp 0401 e9 zcb): 0x%" PRIx64 " is the start of no run of the list's placed heaps: nothing left out for it", x.off[i]));
    }
}

// ---- what the probe and the watch read ----
// TODO(verify), as zcanary_check says: whether the CPU sees the GPU's writes to an imported memfd page without a flush; the
// lines are flushed first, so a stale cached line cannot hide a write.
static void zcb_flush(const unsigned char* p, uint64_t n) {
    for (uint64_t o = 0; o < n; o += 64) __builtin_ia32_clflush(p + o);
    __builtin_ia32_mfence();
}
struct ZcbSum {
    uint64_t nonzero = 0, hash = 0;
    int64_t  first = -1, last = -1; // byte offsets; -1: none
};
// The non-zero bytes of [p, p + n): how many, the first and the last, and a 64-bit hash of all of it (FNV-1a's step over
// 8-byte little-endian words, the last one zero-padded: h = (h ^ w) * 0x100000001b3, from 0xcbf29ce484222325).
static ZcbSum zcb_summary(const unsigned char* p, uint64_t n) {
    ZcbSum   s;
    uint64_t h = 0xcbf29ce484222325ull;
    for (uint64_t i = 0; i < n; i += 8) {
        uint64_t w = 0;
        std::memcpy(&w, p + i, static_cast<size_t>(n - i < 8 ? n - i : 8));
        h = (h ^ w) * 0x100000001b3ull;
        if (w == 0) continue;
        for (uint64_t k = i; k < i + 8 && k < n; k++) {
            if (p[k] == 0) continue;
            s.nonzero++;
            if (s.first < 0) s.first = static_cast<int64_t>(k);
            s.last = static_cast<int64_t>(k);
        }
    }
    s.hash = h;
    return s;
}
static std::string zcb_sum_text(const ZcbSum& s) {
    if (s.nonzero == 0) return zcb_fmt("all zero (hash 0x%016" PRIx64 ")", s.hash);
    return zcb_fmt("%" PRIu64 " non-zero bytes, first at 0x%" PRIx64 ", last at 0x%" PRIx64 ", hash 0x%016" PRIx64, s.nonzero, static_cast<uint64_t>(s.first),
                   static_cast<uint64_t>(s.last), s.hash);
}
using ZcbRanges = std::vector<std::pair<uint64_t, uint64_t>>; // [va, end), by address, touching pieces merged
static void zcb_range_add(ZcbRanges& v, uint64_t va, uint64_t size) {
    if (!v.empty() && v.back().second == va) v.back().second = va + size;
    else v.emplace_back(va, va + size);
}
static ZcbRanges zcb_vas_of(uint32_t run) { // the run's canary mappings now (g_zpieces, the syncing thread's)
    ZcbRanges v;
    for (const auto& [va, piece]: g_zpieces) {
        if (piece.run == run) zcb_range_add(v, va, piece.size);
    }
    return v;
}
static std::string zcb_vas_text(const ZcbRanges& v) {
    if (v.empty()) return "none mapped";
    std::string s;
    for (size_t i = 0; i < v.size() && i < kZcbListShown; i++) s += zcb_fmt("%s0x%" PRIx64 "-0x%" PRIx64, i == 0 ? "" : ", ", v[i].first, v[i].second);
    if (v.size() > kZcbListShown) s += zcb_fmt(" and %zu more", v.size() - kZcbListShown);
    return s;
}
static std::string zcb_chunks_text(const std::vector<uint64_t>& c) {
    std::string s;
    for (size_t i = 0; i < c.size() && i < kZcbListShown; i++) s += zcb_fmt("%s0x%" PRIx64, i == 0 ? "" : ", ", c[i]);
    if (c.size() > kZcbListShown) s += zcb_fmt(" and %zu more", c.size() - kZcbListShown);
    return s;
}
// The jobs in flight: Device::wait_idle waits for the job queued last on each ring (a ring runs its jobs in order;
// bc5/direct.hpp), querying each ring's fence with the bound in turn (backend/src/direct.cpp). A fence query: it does not
// wait for the completion threads, so the syncing thread cannot deadlock on them. 1 all done, 0 not within the bound, -1
// no device.
static int (*g_zcb_test_wait)(uint64_t, void*) = nullptr; // exp 0401 e9: zcb0401.cpp's stand-in for the device only (bc5_zcb0401_set_wait)
static void* g_zcb_test_wait_ctx               = nullptr;
static int zcb_wait(uint64_t ns) {
    if (g_zcb_test_wait != nullptr) return g_zcb_test_wait(ns, g_zcb_test_wait_ctx);
    if (!g_dev) return -1;
    return g_dev->wait_idle(ns) ? 1 : 0;
}
// What this point of the unit can say of the jobs in flight: the jobs themselves are in exp 0024's completion queues
// (g_cqs, PendingJob), defined after exp 0404's block, which zcb leaves alone; so the submissions so far and whether every
// ring was idle at that moment (a zero-time Device::wait_idle).
static std::string zcb_in_flight() {
    const uint64_t s = g_submits.load();
    const int      w = zcb_wait(0);
    std::string    t = zcb_fmt("%" PRIu64 " submissions so far", s);
    if (s != 0) t += zcb_fmt(" (the last #%" PRIu64 ")", s - 1);
    return t + "; every ring idle now: " + (w < 0 ? "no device" : w != 0 ? "yes" : "no");
}

// ---- PROBE: the take-backs and the skip by run, kept for a timeout on another thread ----
struct ZcbBack {
    double                t   = 0;
    bool                  hit = false; // a canary hit (else CPU writes)
    uint32_t              run = 0;
    uint64_t              off = 0, len = 0;
    std::vector<uint64_t> chunks; // a canary hit: the chunks still skipped then; CPU writes: the chunks taken back
    ZcbRanges             vas;    // the run's canary mappings then
};
struct ZcbRun {
    uint32_t  run = 0;
    uint64_t  off = 0, len = 0, left = 0; // left: bytes still skipped
    uint8_t   flag = 0;                   // g_zflag: 0 watched, 1 hit, 2 done (255: none)
    ZcbRanges vas;
};
static std::mutex          g_zcb_mu;    // the records, the snapshot and the watch: the syncing thread, the watcher, a completion thread
static std::deque<ZcbBack> g_zcb_backs; // the last kZcbBacksKept, oldest first
static uint64_t            g_zcb_backs_n = 0, g_zcb_hits_n = 0;
static std::vector<ZcbRun> g_zcb_snap;
static double              g_zcb_snap_t   = -1.0;
static bool                g_zcb_snap_due = false; // the syncing thread's: a take-back since the last snapshot
// One take-back's line and record. chunks: a canary hit's chunks still skipped, or the chunks CPU writes took back; still:
// the run's chunks still skipped after it.
static void zcb_probe_back(bool hit, size_t r, const std::vector<uint64_t>& chunks, uint64_t still) {
    const auto [o, l] = g_zskip.run(static_cast<uint32_t>(r));
    ZcbBack b;
    b.t      = timing_now();
    b.hit    = hit;
    b.run    = static_cast<uint32_t>(r);
    b.off    = o;
    b.len    = l;
    b.chunks = chunks;
    b.vas    = zcb_vas_of(b.run);
    std::string slice = "not mapped";
    if (g_zcanary_cpu != nullptr && r < g_zruns) {
        const unsigned char* p = g_zcanary_cpu + r * kDChunk;
        zcb_flush(p, kDChunk);
        slice = zcb_sum_text(zcb_summary(p, kDChunk));
    }
    const std::string what = hit ? zcb_fmt("a canary hit: run %zu, file 0x%" PRIx64 "-0x%" PRIx64 " (+%.1f MiB), %" PRIu64 " of %" PRIu64 " chunks still skipped (the others are real memory already)", r, o, o + l,
                                           static_cast<double>(l) / 1048576.0, still, l / kDChunk)
                                 : zcb_fmt("CPU writes: run %zu, file 0x%" PRIx64 "-0x%" PRIx64 " (+%.1f MiB), %zu chunks taken back (%s), %" PRIu64 " still skipped", r, o, o + l,
                                           static_cast<double>(l) / 1048576.0, chunks.size(), zcb_chunks_text(chunks).c_str(), still);
    zcb_line(zcb_fmt("zero skip probe (exp 0401 e9 zcb): t %.3f s: take-back by %s; %s canary VAs: %s; its slice: %s; jobs in flight: %s", b.t, what.c_str(), hit ? "its" : "the run's",
                     zcb_vas_text(b.vas).c_str(), slice.c_str(), zcb_in_flight().c_str()));
    g_zcb_snap_due = true;
    std::lock_guard lk(g_zcb_mu);
    g_zcb_backs.push_back(std::move(b));
    if (g_zcb_backs.size() > kZcbBacksKept) g_zcb_backs.pop_front();
    g_zcb_backs_n++;
    if (hit) g_zcb_hits_n++;
}
static void zcb_snapshot() { // zskip_map after a pass, zskip_take_back after a take-back: the skip by run, for a timeout
    if (!zcb_probe_on()) return;
    std::map<uint32_t, ZcbRanges> vas;
    for (const auto& [va, piece]: g_zpieces) zcb_range_add(vas[piece.run], va, piece.size);
    std::vector<ZcbRun> v;
    for (size_t r = 0; r < g_zskip.run_count(); r++) {
        ZcbRun x;
        x.run             = static_cast<uint32_t>(r);
        const auto [o, l] = g_zskip.run(x.run);
        x.off             = o;
        x.len             = l;
        x.left            = g_zskip.run_left(x.run);
        x.flag            = g_zflag != nullptr && r < g_zruns ? g_zflag[r].load() : uint8_t {255};
        if (const auto it = vas.find(x.run); it != vas.end()) x.vas = it->second;
        v.push_back(std::move(x));
    }
    const double t = timing_now();
    std::lock_guard lk(g_zcb_mu);
    g_zcb_snap.swap(v);
    g_zcb_snap_t = t;
}
static void zcb_take_back_end() {
    if (!g_zcb_snap_due) return;
    g_zcb_snap_due = false;
    zcb_snapshot();
}

// ---- COPYBACK ----
struct ZcbCopy {
    uint32_t chunks = 0, copied = 0, cpu_data = 0, failed = 0, pages = 0;
    uint64_t bytes = 0;
};
// The slice's non-zero 4 KiB pages into each chunk of `chunks` (file offsets of the direct-memory memfd fd) that holds no
// data yet (SEEK_DATA finds none in it: the file reads zeros there, all the CPU saw); a chunk the CPU wrote since the last
// walk keeps its data and is only counted. In a chunk the file read as zeros, those pages make it the slice byte for byte.
static ZcbCopy zcb_copy_chunks(int fd, const unsigned char* slice, const std::vector<uint64_t>& chunks) {
    ZcbCopy c;
    c.chunks = static_cast<uint32_t>(chunks.size());
    std::vector<uint64_t> pages;
    for (uint64_t p = 0; p < kDChunk; p += kZcbPage) {
        if (!bc5::zero_skip::all_zero(slice + p, kZcbPage)) pages.push_back(p);
    }
    c.pages = static_cast<uint32_t>(pages.size());
    for (const uint64_t ch: chunks) {
        const off_t d = lseek(fd, static_cast<off_t>(ch), SEEK_DATA);
        if (d >= 0 && static_cast<uint64_t>(d) < ch + kDChunk) {
            c.cpu_data++;
            continue;
        }
        bool ok = true;
        for (const uint64_t p: pages) {
            if (pwrite(fd, slice + p, kZcbPage, static_cast<off_t>(ch + p)) != static_cast<ssize_t>(kZcbPage)) {
                ok = false;
                break;
            }
            c.bytes += kZcbPage;
        }
        if (ok) c.copied++;
        else c.failed++;
    }
    return c;
}
// At a canary hit (zskip_take_back, on the syncing thread, under g_dev_mutex where every submission is made): wait for the
// jobs in flight, bounded, so that nothing the GPU runs still writes into the slice; then the copy, before the run leaves
// the skip set and its real chunks are imported and mapped by the same direct_sync_one. Its line.
static void zcb_copy_back(int fd, size_t r, const std::vector<uint64_t>& left) {
    const auto           [o, l] = g_zskip.run(static_cast<uint32_t>(r));
    const double         t0     = timing_now();
    const int            w      = zcb_wait(kZcbWaitNs);
    const double         ms     = (timing_now() - t0) * 1000.0;
    const unsigned char* slice  = g_zcanary_cpu != nullptr && r < g_zruns ? g_zcanary_cpu + r * kDChunk : nullptr;
    ZcbCopy              c;
    c.chunks = static_cast<uint32_t>(left.size());
    if (slice != nullptr && fd >= 0) {
        zcb_flush(slice, kDChunk);
        c = zcb_copy_chunks(fd, slice, left);
    }
    const char* how = w < 0 ? "no device: nothing to wait for" : w != 0 ? "every ring idle" : "NOT idle within the bound: the GPU may still write into the slice";
    zcb_line(zcb_fmt("zero skip copy-back (exp 0401 e9 zcb): t %.3f s: run %zu (file 0x%" PRIx64 " +%.1f MiB): waited %.1f ms (at most %" PRIu64 " ms a ring) for the jobs in flight: %s; "
                     "the slice has %u non-zero pages of 4 KiB; %" PRIu64 " bytes copied into %u of the %u chunks still skipped, %u of them held CPU data and were left as they are, "
                     "%u writes failed; %" PRIu64 " chunks taken back before stay as they are%s",
                     timing_now(), r, o, static_cast<double>(l) / 1048576.0, ms, static_cast<uint64_t>(kZcbWaitNs / 1000000u), how, c.pages, c.bytes, c.copied, c.chunks, c.cpu_data, c.failed,
                     static_cast<uint64_t>(l / kDChunk - left.size()), slice == nullptr ? "; no slice mapped: nothing copied" : ""));
}
static void zcb_hit(int fd, size_t r) {
    const ZcbSwitches& sw = zcb_sw();
    if (!sw.copyback && !sw.probe) return;
    const auto [o, l] = g_zskip.run(static_cast<uint32_t>(r));
    std::vector<uint64_t> left; // the run's chunks still skipped; the others went back by CPU writes or hints and are real memory
    for (uint64_t c = o; c < o + l; c += kDChunk) {
        if (g_zskip.run_of(c) == static_cast<long>(r)) left.push_back(c);
    }
    if (sw.probe) zcb_probe_back(true, r, left, left.size());
    if (sw.copyback) zcb_copy_back(fd, r, left);
}
static void zcb_cpu_back(size_t r, const std::vector<uint64_t>& chunks) {
    if (zcb_probe_on()) zcb_probe_back(false, r, chunks, r < g_zleft.size() ? g_zleft[r] / kDChunk : 0);
}

// ---- SCRATCH_WATCH ----
struct ZcbWatch {
    ZcbSum   last;
    double   first_t = -1.0, line_t = -1.0; // the first non-zero scan's time, the last line's
    uint64_t scans = 0, changes = 0;
    uint32_t lines = 0;       // change lines so far
    bool     pending = false; // a change not journaled yet (the gap)
};
static bool zcb_same(const ZcbSum& a, const ZcbSum& b) {
    return a.nonzero == b.nonzero && a.first == b.first && a.last == b.last && a.hash == b.hash;
}
static bool zcb_watch_due(double now_t, double line_t, uint32_t lines) {
    return lines < kZcbWatchLines && (line_t < 0 || now_t - line_t >= kZcbWatchGapS);
}
// One scan's result s at time t: the line to journal, or "". The first non-zero scan is journaled at once; after it a change
// at most once per kZcbWatchGapS (a change in the gap waits, and the scan that ends the gap gives the state then), up to
// kZcbWatchLines change lines in a session.
static std::string zcb_watch_step(ZcbWatch& w, const ZcbSum& s, double t) {
    w.scans++;
    std::string line;
    if (s.nonzero != 0 && w.first_t < 0) {
        w.first_t = t;
        w.line_t  = t;
        line      = zcb_fmt("scratch watch (exp 0401 e9 zcb): t %.3f s: the hole scratch BO is not all zero: %s (a GPU write into a hole stays, and shows at the same offset in every hole)", t,
                            zcb_sum_text(s).c_str());
    } else if (w.first_t >= 0) {
        if (!zcb_same(s, w.last)) {
            w.changes++;
            w.pending = true;
        }
        if (w.pending && zcb_watch_due(t, w.line_t, w.lines)) {
            w.pending = false;
            w.line_t  = t;
            w.lines++;
            line = zcb_fmt("scratch watch (exp 0401 e9 zcb): t %.3f s: the hole scratch BO changed (%" PRIu64 " changes since t %.3f s): %s%s", t, w.changes, w.first_t,
                           s.nonzero == 0 ? "all zero again" : zcb_sum_text(s).c_str(), w.lines == kZcbWatchLines ? "; no more change lines in this session" : "");
        }
    }
    w.last = s;
    return line;
}
static std::atomic<const unsigned char*> g_zcb_scratch_cpu {nullptr}; // the scratch BO's memfd, mapped read-only here
static std::atomic<bool>                 g_zcb_watch_started {false};
static ZcbWatch                          g_zcb_watch; // under g_zcb_mu
static void zcb_watch_thread() {
    setpriority(PRIO_PROCESS, static_cast<id_t>(syscall(SYS_gettid)), 19);
    for (;;) {
        std::this_thread::sleep_for(std::chrono::milliseconds(kZcbWatchMs));
        const unsigned char* p = g_zcb_scratch_cpu.load();
        if (p == nullptr) continue;
        zcb_flush(p, kDChunk);
        const ZcbSum s = bc5::zero_skip::all_zero(p, kDChunk) ? ZcbSum {} : zcb_summary(p, kDChunk);
        std::string  line;
        {
            std::lock_guard lk(g_zcb_mu);
            line = zcb_watch_step(g_zcb_watch, s, timing_now());
        }
        if (!line.empty()) zcb_line(line);
    }
}
// scratch_bo, once the scratch memfd is imported: scratch_bo never maps it on the CPU, so it is mapped read-only here
// (BC5_DIRECT_SCRATCH_WATCH). Once a session; the memfd outlives a device reopen (only its import is made again).
static void zcb_scratch_watch_start(int fd) {
    if (!zcb_sw().watch || fd < 0 || g_zcb_watch_started.exchange(true)) return;
    void* p = mmap(nullptr, kDChunk, PROT_READ, MAP_SHARED, fd, 0);
    if (p == MAP_FAILED) {
        zcb_line(zcb_fmt("scratch watch (exp 0401 e9 zcb): t %.3f s: the scratch BO's memfd %d could not be mapped: not watched", timing_now(), fd));
        return;
    }
    g_zcb_scratch_cpu = static_cast<const unsigned char*>(p);
    zcb_line(zcb_fmt("scratch watch (exp 0401 e9 zcb): t %.3f s: watching the hole scratch BO (memfd %d, 2 MiB, mapped read-only here) every %u ms", timing_now(), fd, kZcbWatchMs));
    std::thread(zcb_watch_thread).detach();
}

// ---- at a fence timeout (the completion thread, submit_now's sync path; before exp 0404's crumbs) ----
struct ZcbAddr {
    uint64_t    a = 0, n = 1;
    std::string what;
};
// The stuck job's own records as addresses: its buffer, and from the host's copy of what it ran (when one is at hand) each
// packet's memory operands (bc5::policy::memory_operands: SET_BASE, INDEX_BASE, label waits and writes, DMA_DATA, ...) and
// the COMPUTE_USER_DATA pairs (sh 0x240-0x24f, as timeout_probe reads them) at each dispatch, read as 48-bit addresses: V#
// bases or pointers, or neither. V#s and tables in memory are not read.
static std::vector<ZcbAddr> zcb_job_addrs(const void* ib, uint32_t num_dwords, const uint32_t* copy, uint32_t copy_n, uint32_t* ops, uint32_t* uds) {
    std::vector<ZcbAddr> v;
    *ops = 0;
    *uds = 0;
    if (ib != nullptr && num_dwords != 0) v.push_back({static_cast<uint64_t>(reinterpret_cast<uintptr_t>(ib)), 4ull * num_dwords, "the buffer"});
    uint32_t           ud[16] = {};
    uint32_t           have   = 0; // bit k: COMPUTE_USER_DATA_k set in the buffer
    std::set<uint64_t> pairs;
    for (uint32_t q = 0; copy != nullptr && q < copy_n && v.size() < kZcbAddrsMax;) {
        const uint32_t h = copy[q], type = h >> 30u;
        uint32_t       len = 1;
        if (type == 3 || type == 0) {
            const uint32_t c = (h >> 16u) & 0x3fffu;
            len              = c == 0x3fffu ? 1 : c + 2;
        }
        if (q + len > copy_n) break;
        if (type == 3) {
            const uint32_t op = (h >> 8u) & 0xffu;
            for (const auto& [a, bytes]: bc5::policy::memory_operands(copy + q, len)) {
                if (a == 0) continue;
                v.push_back({a, bytes == 0 ? uint64_t {4} : bytes, zcb_fmt("op %02x at dword %u", op, q)});
                (*ops)++;
            }
            if (op == 0x76 && len >= 3) {
                const uint32_t first = copy[q + 1] & 0xffffu;
                for (uint32_t k = 0; k + 2 < len; k++) {
                    if (first + k < 0x240u || first + k >= 0x250u) continue;
                    ud[first + k - 0x240u] = copy[q + 2 + k];
                    have |= 1u << (first + k - 0x240u);
                }
            }
            if ((op == 0x15 || op == 0x16) && len >= 2) {
                for (uint32_t k = 0; k < 16; k += 2) {
                    if (((have >> k) & 3u) != 3u) continue;
                    const uint64_t a = ud[k] | (static_cast<uint64_t>(ud[k + 1] & 0xffffu) << 32u);
                    if (a == 0 || !pairs.insert(a).second) continue;
                    v.push_back({a, 1, zcb_fmt("user data %u-%u at the dispatch at dword %u", k, k + 1, q)});
                    (*uds)++;
                }
            }
        }
        q += len;
    }
    return v;
}
struct ZcbRangeOf {
    uint64_t    lo = 0, hi = 0;
    uint32_t    run = 0;
    bool        back = false; // taken back (else still skipped)
    std::string state;
};
// Which addresses fall in a run's canary VAs: a run taken back (a canary hit's record, or the snapshot's run with nothing
// left), or a run still skipped (the snapshot's). Each (address, run) once, records first.
static void zcb_touch(const std::vector<ZcbAddr>& addrs, const std::deque<ZcbBack>& backs, const std::vector<ZcbRun>& snap, double now, std::string* back, std::string* skipped) {
    std::vector<ZcbRangeOf> rs;
    for (const ZcbBack& b: backs) {
        if (!b.hit) continue;
        const std::string st = zcb_fmt("taken back by a canary hit %.3f s ago", now - b.t);
        for (const auto& [lo, hi]: b.vas) rs.push_back({lo, hi, b.run, true, st});
    }
    for (const ZcbRun& x: snap) {
        const bool        gone = x.left == 0 || x.flag == 2;
        const std::string st   = gone ? std::string("taken back") : zcb_fmt("%" PRIu64 " of %" PRIu64 " chunks still skipped", x.left / kDChunk, x.len / kDChunk);
        for (const auto& [lo, hi]: x.vas) rs.push_back({lo, hi, x.run, gone, st});
    }
    std::set<std::pair<size_t, uint32_t>> said;
    uint32_t                              nb = 0, ns = 0;
    for (size_t i = 0; i < addrs.size(); i++) {
        const ZcbAddr& z = addrs[i];
        for (const ZcbRangeOf& g: rs) {
            if (z.a >= g.hi || z.a + z.n <= g.lo || !said.insert({i, g.run}).second) continue;
            std::string& out = g.back ? *back : *skipped;
            uint32_t&    cnt = g.back ? nb : ns;
            if (cnt++ < kZcbListShown) out += zcb_fmt("%srun %u, %s (%s: 0x%" PRIx64 ")", out.empty() ? "" : "; ", g.run, g.state.c_str(), z.what.c_str(), z.a);
        }
    }
    if (nb > kZcbListShown) *back += zcb_fmt(" and %zu more", static_cast<size_t>(nb) - kZcbListShown);
    if (ns > kZcbListShown) *skipped += zcb_fmt(" and %zu more", static_cast<size_t>(ns) - kZcbListShown);
    if (back->empty()) *back = "none";
    if (skipped->empty()) *skipped = "none";
}
static void zcb_probe_timeout(uint64_t n, const char* kind, const void* ib, uint32_t num_dwords, const uint32_t* copy, uint32_t copy_n) {
    const double t  = timing_now();
    const char*  kd = kind != nullptr ? kind : "?";
    if (zskip_path() == nullptr) {
        zcb_line(zcb_fmt("zero skip probe (exp 0401 e9 zcb): at the timeout of submit #%" PRIu64 " %s: the zero skip is off: no take-backs", n, kd));
        return;
    }
    std::deque<ZcbBack> backs;
    std::vector<ZcbRun> snap;
    uint64_t            total = 0, hits = 0;
    double              snap_t = -1.0;
    {
        std::lock_guard lk(g_zcb_mu);
        backs  = g_zcb_backs;
        snap   = g_zcb_snap;
        total  = g_zcb_backs_n;
        hits   = g_zcb_hits_n;
        snap_t = g_zcb_snap_t;
    }
    const size_t shown = std::min(backs.size(), kZcbBacksShown);
    zcb_line(zcb_fmt("zero skip probe (exp 0401 e9 zcb): at the timeout of submit #%" PRIu64 " %s: t %.3f s: %" PRIu64 " take-backs so far (%" PRIu64 " by canary hits), the last %zu below, newest first; the skip by run as of %s",
                     n, kd, t, total, hits, shown, snap_t < 0 ? "no snapshot yet" : zcb_fmt("t %.3f s", snap_t).c_str()));
    for (size_t i = 0; i < shown; i++) {
        const ZcbBack& b = backs[backs.size() - 1 - i];
        zcb_line(zcb_fmt("zero skip probe (exp 0401 e9 zcb): at the timeout of submit #%" PRIu64 ": take-back %" PRIu64 " of %" PRIu64 ", %.3f s ago, by %s: run %u, file 0x%" PRIx64 "-0x%" PRIx64
                         " (+%.1f MiB), %s; %s VAs: %s",
                         n, total - i, total, t - b.t, b.hit ? "a canary hit" : "CPU writes", b.run, b.off, b.off + b.len, static_cast<double>(b.len) / 1048576.0,
                         b.hit ? zcb_fmt("%zu chunks still skipped then", b.chunks.size()).c_str() : zcb_fmt("chunks %s", zcb_chunks_text(b.chunks).c_str()).c_str(), b.hit ? "its" : "the run's",
                         zcb_vas_text(b.vas).c_str()));
    }
    uint32_t                   ops = 0, uds = 0;
    const std::vector<ZcbAddr> addrs = zcb_job_addrs(ib, num_dwords, copy, copy_n, &ops, &uds);
    std::string                back, skipped;
    zcb_touch(addrs, backs, snap, t, &back, &skipped);
    zcb_line(zcb_fmt("zero skip probe (exp 0401 e9 zcb): at the timeout of submit #%" PRIu64 " %s: the job's own records: the buffer 0x%" PRIx64 " +0x%" PRIx64 "; %s; touching a taken-back run: %s; "
                     "touching a still-skipped run: %s (an address in a range is no proof that the GPU used it; V#s and tables in memory are not read)",
                     n, kd, static_cast<uint64_t>(reinterpret_cast<uintptr_t>(ib)), static_cast<uint64_t>(num_dwords) * 4u,
                     copy != nullptr && copy_n != 0 ? zcb_fmt("from the host's copy of %u dwords, %u memory operands and %u user-data pairs at dispatches", copy_n, ops, uds).c_str()
                                                    : "no host copy of the buffer (the completion thread keeps one with BC5_DIRECT_TIMEOUT_PROBE only)",
                     back.c_str(), skipped.c_str()));
}
static void zcb_watch_timeout(uint64_t n, const char* kind) {
    const char*          kd = kind != nullptr ? kind : "?";
    const unsigned char* p  = g_zcb_scratch_cpu.load();
    if (p == nullptr) {
        zcb_line(zcb_fmt("scratch watch (exp 0401 e9 zcb): at the timeout of submit #%" PRIu64 " %s: the scratch BO is not watched (not made yet: no hole filled; or its memfd could not be mapped)", n, kd));
        return;
    }
    zcb_flush(p, kDChunk);
    const ZcbSum s = bc5::zero_skip::all_zero(p, kDChunk) ? ZcbSum {} : zcb_summary(p, kDChunk);
    ZcbWatch     w;
    {
        std::lock_guard lk(g_zcb_mu);
        w = g_zcb_watch;
    }
    if (s.nonzero == 0) {
        zcb_line(zcb_fmt("scratch watch (exp 0401 e9 zcb): at the timeout of submit #%" PRIu64 " %s: the hole scratch BO is clean: all zero now (%" PRIu64 " scans; %s)", n, kd, w.scans,
                         w.first_t < 0 ? "never seen non-zero" : zcb_fmt("non-zero first at t %.3f s", w.first_t).c_str()));
    } else {
        zcb_line(zcb_fmt("scratch watch (exp 0401 e9 zcb): at the timeout of submit #%" PRIu64 " %s: the hole scratch BO is DIRTY: %s (%s; %" PRIu64 " scans, %" PRIu64 " changes)", n, kd,
                         zcb_sum_text(s).c_str(), w.first_t < 0 ? "the watcher has not seen it yet" : zcb_fmt("the watcher saw non-zero bytes first at t %.3f s", w.first_t).c_str(), w.scans,
                         w.changes));
    }
}
static void zcb_at_timeout(uint64_t n, const char* kind, const void* ib, uint32_t num_dwords, const uint32_t* copy, uint32_t copy_n) {
    const ZcbSwitches& sw = zcb_sw();
    if (sw.probe) zcb_probe_timeout(n, kind, ib, num_dwords, copy, copy_n);
    if (sw.watch) zcb_watch_timeout(n, kind);
}
// ---- end of exp 0401 series e9's (tag zcb) host block ------------------------------------------------------------------
""")
ZCB_SEAMS = tabs(r"""// ---- exp 0401 series e9 (tag zcb): the CPU test's seams (zcb0401.cpp); always compiled in, never called by the emulator ----
extern "C" void bc5_zcb0401_capture(int on) { // the lines zcb journals, kept for the test from now on
    g_zcb_capture = on != 0;
}
// The captured lines from index `from` on, each ended by '\n', into out (at most cap - 1 bytes, NUL-ended); all lines so far.
extern "C" uint64_t bc5_zcb0401_lines(uint64_t from, char* out, uint64_t cap) {
    std::lock_guard lk(g_zcb_capture_mu);
    std::string     all;
    for (size_t i = static_cast<size_t>(from); i < g_zcb_captured.size(); i++) all += g_zcb_captured[i] + "\n";
    if (cap != 0) {
        const size_t c = std::min<size_t>(all.size(), static_cast<size_t>(cap) - 1);
        std::memcpy(out, all.data(), c);
        out[c] = 0;
    }
    return g_zcb_captured.size();
}
extern "C" int bc5_zcb0401_quiet_kind(const char* line) { // the quiet filter's kind of the line as journal() gets it (with its newline)
    const std::string s = std::string(line) + "\n";
    return journal_quiet_kind(s.c_str(), s.size(), true);
}
extern "C" int bc5_zcb0401_flag(const char* e, int* bad) {
    bool      b = false;
    const int v = zcb_parse_flag(e, &b);
    *bad        = b ? 1 : 0;
    return v;
}
extern "C" uint32_t bc5_zcb0401_exclude_parse(const char* e, uint64_t* offs, uint32_t* bad, char* why, uint64_t cap) { // offs: kZcbExcludeMax
    const ZcbExclude x = zcb_parse_exclude(e);
    for (uint32_t i = 0; i < x.n; i++) offs[i] = x.off[i];
    *bad = x.bad;
    if (cap != 0) std::snprintf(why, static_cast<size_t>(cap), "%s", x.why.c_str());
    return x.n;
}
extern "C" void bc5_zcb0401_switches(uint64_t* out) { // the unit's reading: [0] entries [1] bad [2] copyback [3] probe [4] watch [5..20] the entries
    const ZcbSwitches& sw = zcb_sw();
    out[0]                = sw.exclude.n;
    out[1]                = sw.exclude.bad;
    out[2]                = sw.copyback ? 1 : 0;
    out[3]                = sw.probe ? 1 : 0;
    out[4]                = sw.watch ? 1 : 0;
    for (uint32_t i = 0; i < kZcbExcludeMax; i++) out[5 + i] = sw.exclude.off[i];
}
extern "C" void bc5_zcb0401_consts(uint64_t* out) {
    const uint64_t v[10] = {kZcbExcludeMax, kZcbWaitNs, kZcbPage, kZcbBacksKept, kZcbBacksShown, kZcbListShown, kZcbAddrsMax, kZcbWatchMs, static_cast<uint64_t>(kZcbWatchGapS * 1000.0), kZcbWatchLines};
    for (uint32_t i = 0; i < 10; i++) out[i] = v[i];
}
// zcb_exclude_with, with the entries `exclude` (EXCLUDE's grammar), on every heap of the list `text` placed at file offset
// base: the runs kept, as (offset, length) pairs into runs (up to cap); their count. hits: kZcbExcludeMax counters.
extern "C" uint64_t bc5_zcb0401_exclude(const char* text, const char* exclude, uint64_t base, uint64_t* runs, uint64_t cap, uint32_t* hits) {
    const ZcbExclude x = zcb_parse_exclude(exclude);
    uint64_t         k = 0;
    for (const auto& h: bc5::zero_skip::parse_list(text != nullptr ? text : "")) {
        for (const auto& [o, l]: zcb_exclude_with(h, base, x, hits).runs) {
            if (k < cap) {
                runs[2 * k]     = o;
                runs[2 * k + 1] = l;
            }
            k++;
        }
    }
    return k;
}
extern "C" void bc5_zcb0401_summary(const void* p, uint64_t n, uint64_t* out) { // non-zero bytes, first, last (~0: none), hash
    const ZcbSum s = zcb_summary(static_cast<const unsigned char*>(p), n);
    out[0]         = s.nonzero;
    out[1]         = static_cast<uint64_t>(s.first);
    out[2]         = static_cast<uint64_t>(s.last);
    out[3]         = s.hash;
}
extern "C" int bc5_zcb0401_watch_due(double now_t, double line_t, uint32_t lines) {
    return zcb_watch_due(now_t, line_t, lines) ? 1 : 0;
}
// A watch of the seam's own through n scans: sums[4k..4k+3] scan k's non-zero bytes, first, last (~0: -1) and hash, ts[k] its
// time. The lines it gives, each ended by '\n', into out; info: scans, changes, change lines, pending. Returns the lines.
extern "C" uint64_t bc5_zcb0401_watch_steps(const uint64_t* sums, const double* ts, uint64_t n, char* out, uint64_t cap, uint64_t* info) {
    ZcbWatch    w;
    std::string all;
    uint64_t    lines = 0;
    for (uint64_t k = 0; k < n; k++) {
        ZcbSum s;
        s.nonzero           = sums[4 * k];
        s.first             = sums[4 * k + 1] == ~0ull ? -1 : static_cast<int64_t>(sums[4 * k + 1]);
        s.last              = sums[4 * k + 2] == ~0ull ? -1 : static_cast<int64_t>(sums[4 * k + 2]);
        s.hash              = sums[4 * k + 3];
        const std::string l = zcb_watch_step(w, s, ts[k]);
        if (l.empty()) continue;
        all += l + "\n";
        lines++;
    }
    if (cap != 0) std::snprintf(out, static_cast<size_t>(cap), "%s", all.c_str());
    info[0] = w.scans;
    info[1] = w.changes;
    info[2] = w.lines;
    info[3] = w.pending ? 1 : 0;
    return lines;
}
// zcb_copy_chunks on the test's own memfd and slice: out = chunks, copied, CPU data, failed, pages, bytes; returns copied.
extern "C" uint64_t bc5_zcb0401_copy(int fd, const void* slice, const uint64_t* chunks, uint64_t n, uint64_t* out) {
    const ZcbCopy  c    = zcb_copy_chunks(fd, static_cast<const unsigned char*>(slice), std::vector<uint64_t>(chunks, chunks + n));
    const uint64_t v[6] = {c.chunks, c.copied, c.cpu_data, c.failed, c.pages, c.bytes};
    for (uint32_t i = 0; i < 6; i++) out[i] = v[i];
    return c.copied;
}
extern "C" void bc5_zcb0401_set_wait(int (*fn)(uint64_t, void*), void* ctx) { // the device's wait, for COPYBACK and PROBE (nullptr: the device's)
    g_zcb_test_wait     = fn;
    g_zcb_test_wait_ctx = ctx;
}
extern "C" int bc5_zcb0401_wait(uint64_t ns) {
    return zcb_wait(ns);
}
extern "C" void bc5_zcb0401_snapshot() { // as zskip_map does after a pass that added canary mappings
    zcb_snapshot();
}
extern "C" void bc5_zcb0401_at_timeout(uint64_t n, const char* kind, const void* ib, uint32_t num_dwords, const uint32_t* copy, uint32_t copy_n) { // as the two timeout lines call it
    zcb_at_timeout(n, kind, ib, num_dwords, copy, copy_n);
}
extern "C" int bc5_zcb0401_watch_start(int fd) { // as scratch_bo calls it; 1 when the scratch BO is watched now
    zcb_scratch_watch_start(fd);
    return g_zcb_scratch_cpu.load() != nullptr ? 1 : 0;
}
// 0 take-backs so far, 1 by canary hits, 2 kept, 3 the newest's run (~0: none), 4 the newest is a hit, 5 its chunks, 6 its VA
// ranges, 7 snapshot runs (~0: no snapshot), 8 snapshot run a's bytes left (~0: none), 9 its flag (~0: none), 10 watch scans,
// 11 the watch's first non-zero time in ms (~0: none), 12 watch changes, 13 watch change lines, 14 the scratch BO mapped,
// 15 the runs entry a matched, 16 the unmatched entries reported.
extern "C" uint64_t bc5_zcb0401_state(int what, uint64_t a) {
    std::lock_guard lk(g_zcb_mu);
    const ZcbBack*  b = g_zcb_backs.empty() ? nullptr : &g_zcb_backs.back();
    const ZcbRun*   x = nullptr;
    for (const ZcbRun& y: g_zcb_snap) {
        if (y.run == a) x = &y;
    }
    switch (what) {
    case 0: return g_zcb_backs_n;
    case 1: return g_zcb_hits_n;
    case 2: return g_zcb_backs.size();
    case 3: return b != nullptr ? static_cast<uint64_t>(b->run) : ~0ull;
    case 4: return b != nullptr && b->hit ? 1 : 0;
    case 5: return b != nullptr ? static_cast<uint64_t>(b->chunks.size()) : 0;
    case 6: return b != nullptr ? static_cast<uint64_t>(b->vas.size()) : 0;
    case 7: return g_zcb_snap_t < 0 ? ~0ull : static_cast<uint64_t>(g_zcb_snap.size());
    case 8: return x != nullptr ? x->left : ~0ull;
    case 9: return x != nullptr ? static_cast<uint64_t>(x->flag) : ~0ull;
    case 10: return g_zcb_watch.scans;
    case 11: return g_zcb_watch.first_t < 0 ? ~0ull : static_cast<uint64_t>(g_zcb_watch.first_t * 1000.0);
    case 12: return g_zcb_watch.changes;
    case 13: return g_zcb_watch.lines;
    case 14: return g_zcb_scratch_cpu.load() != nullptr ? 1 : 0;
    case 15: return a < kZcbExcludeMax ? static_cast<uint64_t>(g_zcb_excl_hits[a]) : ~0ull;
    case 16: return g_zcb_excl_reported ? 1 : 0;
    default: return ~0ull;
    }
}
// ---- end of exp 0401 series e9's (tag zcb) seams -----------------------------------------------------------------------
""")

# ---- 6. the scratch BO's creation: a comment line, the watch's start ------------------------------------------------------
SCR_CMT_OLD = (b"// there (learned_apply checks on every layout change; the direct mapper unmaps before it maps).\n"
               b"static uint32_t                                    g_scratch_id = 0;\n")
SCR_CMT_NEW = (b"// there (learned_apply checks on every layout change; the direct mapper unmaps before it maps).\n"
               b"// Exp 0401 e9 (zcb): \"its writes go nowhere\" is wrong: this is one read-write 2 MiB memfd BO mapped at every hole, so a GPU\n"
               b"// write into a hole stays and shows at the same offset in every other hole (hang1954-0401.md); BC5_DIRECT_SCRATCH_WATCH looks.\n"
               b"static uint32_t                                    g_scratch_id = 0;\n")
SCR_OLD = b"\tg_scratch_id = g_dev->import_memfd(g_scratch_fd, 0, kDChunk);\n\treturn g_scratch_id;\n"
SCR_NEW = (b"\tg_scratch_id = g_dev->import_memfd(g_scratch_fd, 0, kDChunk);\n"
           b"\tif (g_scratch_id != 0) zcb_scratch_watch_start(g_scratch_fd); // + exp 0401 e9 (zcb): BC5_DIRECT_SCRATCH_WATCH (off: returns at once)\n"
           b"\treturn g_scratch_id;\n")

# ---- 7. one line before each of exp 0404's two fl_probe lines -------------------------------------------------------------
CQ_OLD = b"\t\t\tif (r.timed_out && j.fl_plan.crumbs) fl_probe(j.fl_plan, j.n, j.kind, g_dev && j.dev_gen == g_dev_gen.load()); // experiment 0404: first, before the long probe\n"
CQ_LINE = (b"\t\t\tif (r.timed_out) zcb_at_timeout(j.n, j.kind, j.ib, j.num_dwords, j.ib_copy.empty() ? nullptr : j.ib_copy.data(), static_cast<uint32_t>(j.ib_copy.size()));"
           b" // exp 0401 e9 (zcb): the zero skip's last take-backs and the scratch BO (PROBE, SCRATCH_WATCH; off: nothing)\n")
SYNC_OLD = b"\tif (r.timed_out && fl_plan.crumbs) fl_probe(fl_plan, n, kind, true); // experiment 0404: first, before the long probe\n"
SYNC_LINE = (b"\tif (r.timed_out) zcb_at_timeout(n, kind, ib, num_dwords, sub_ib, sub_n);"
             b" // exp 0401 e9 (zcb): the zero skip's last take-backs and the scratch BO (PROBE, SCRATCH_WATCH; off: nothing)\n")

# (name, anchor, new text for the anchor), in file order; each anchor exactly once in the unit when applied
EDITS = [
    ("the declarations", DECL_ANCHOR, DECLS + DECL_ANCHOR),
    ("zskip_map: the snapshot", MAP_OLD, MAP_NEW),
    ("zskip_resolve: the switch lines", RES_OLD, RES_NEW),
    ("zskip_resolve: the exclusion", PLACE_OLD, PLACE_NEW),
    ("zskip_resolve: the unmatched entries", DONE_OLD, DONE_NEW),
    ("zskip_take_back: a canary hit", HIT_OLD, HIT_NEW),
    ("zskip_take_back: CPU writes, the end", WALK_OLD, WALK_NEW),
    ("the host block and the seams", END_LINE, ZCB_HOST + ZCB_SEAMS + END_LINE),
    ("the scratch BO: its comment", SCR_CMT_OLD, SCR_CMT_NEW),
    ("the scratch BO: the watch", SCR_OLD, SCR_NEW),
    ("completion_thread: the timeout line", CQ_OLD, CQ_LINE + CQ_OLD),
    ("submit_now: the timeout line", SYNC_OLD, SYNC_LINE + SYNC_OLD),
]

ZERO_START = b"// ---- experiment 0379: the zero list (BC5_DIRECT_ZEROSCAN_AT/_OUT) and the skip (BC5_DIRECT_ZERO_SKIP) ---------------\n"
SCR_START = b"// Experiment 0037: a learned fault window may cover addresses the guest has no range at all in:\n"
SCR_END = b"// Unmaps the scratch pieces that overlap [lo, hi).\n"
FL_START = b"// ---- experiment 0404 (in exp 0401's unit): fast-launch draw crumbs and skip, the pure part"


def strip_code(b):
    """The text with comments and string/char literals removed (for the balance counts). A ' between an alphanumeric and
    a hex digit is a C++14 digit separator (2'000'000'000ull in the unit), not a character literal: mksmp0401.py's
    stripper took those for literals, which left e8's whole unit at (21, 15, 2) instead of (0, 0, 0)."""
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
        elif c == b"'" and i > 0 and b[i - 1:i].isalnum() and i + 1 < n and b[i + 1:i + 2] in b"0123456789abcdefABCDEF":
            i += 1
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


def inserted(old, new):
    """The lines new adds to old, or None when new is not old with whole lines inserted."""
    a, b = old.splitlines(keepends=True), new.splitlines(keepends=True)
    added, i = [], 0
    for line in b:
        if i < len(a) and line == a[i]:
            i += 1
        else:
            added.append(line)
    return b"".join(added) if i == len(a) else None


def md5(b):
    return hashlib.md5(b).hexdigest()


def edit_unit(s):
    for m in MARKS:
        assert m not in s, ("the unit has the edit already", m)
    assert b"\r" not in s, "a CR in the LF unit"
    for name, old, new in EDITS:
        assert s.count(old) == 1, ("an anchor does not occur exactly once in the input", name, s.count(old))
        assert balance(old) == balance(new), ("the edit changes the balance", name, balance(old), balance(new))
        new.decode("ascii")
        assert b"\r" not in new, name
    pos = [s.index(old) for _name, old, _new in EDITS]
    assert pos == sorted(pos), ("the anchors are not in file order", pos)
    # Where the anchors lie: the zero-skip block (exp 0379's), the scratch BO's creation, the two lines after exp 0404's
    # pure block starts.
    z0, z1 = s.index(ZERO_START), s.index(END_LINE)
    c0, c1 = s.index(SCR_START), s.index(SCR_END)
    f0 = s.index(FL_START)
    assert z0 < z1 < c0 < c1 < f0
    assert all(z0 < p <= z1 for p in pos[:8]), "an anchor lies outside the zero-skip block"
    assert all(c0 < p < c1 for p in pos[8:10]), "an anchor lies outside the scratch BO's creation"
    assert all(f0 < p for p in pos[10:]), "a timeout line lies before exp 0404's block"
    assert s.index(b"static void zskip_release(") > pos[0] and s.index(b"static void zskip_map(") < pos[1] < s.index(b"static bool zskip_resolve(")
    assert s.index(b"static bool zskip_resolve(") <= pos[2] < pos[4] < s.index(b"static void zskip_take_back(") < pos[5] < pos[6] < s.index(b"static void zskip_report(")
    assert s.index(b"static uint32_t scratch_bo() {") < pos[9] < s.index(b"static void scratch_release(uint64_t lo, uint64_t hi) {")
    assert s.index(b"static void completion_thread(int index) {") < pos[10] < s.index(b"static void cq_push(")
    assert s.index(b"static void submit_now(const uint32_t* ib, uint32_t num_dwords, const char* kind, int ring, const Chain* chain) {") < pos[11]
    out = s
    done = []
    for name, old, new in EDITS:
        assert out.count(old) == 1, ("an anchor does not occur exactly once when applied", name)
        out = out.replace(old, new)
        done.append((old, new, name))
    for _old, new, name in done:
        assert out.count(new) == 1, ("the new text is not there once", name)
    # Outside the zero-skip block and the scratch BO's creation nothing changed but the two timeout lines; from exp 0404's
    # block on, only those two lines were added (the given-up waits' code and the rest stay as they are).
    oz0, oz1 = out.index(ZERO_START), out.index(END_LINE)
    oc0, oc1 = out.index(SCR_START), out.index(SCR_END)
    of0 = out.index(FL_START)
    assert out[:oz0] == s[:z0], "the unit before the zero-skip block changed"
    assert out[oz1:oc0] == s[z1:c0], "the unit between the zero-skip block and the scratch BO changed"
    assert out[oc1:of0] == s[c1:f0], "the unit between the scratch BO and exp 0404's block changed"
    assert inserted(s[f0:], out[of0:]) == CQ_LINE + SYNC_LINE, "exp 0404's block on: more than the two timeout lines"
    assert inserted(s[c0:c1], out[oc0:oc1]) is not None, "the scratch BO's creation: not insert-only"
    # Each zcb function: its uses (declaration, definition, calls, seams), as written above.
    want = {b"zcb_switch_lines(": 3, b"zcb_probe_on(": 5, b"zcb_exclude(": 3, b"zcb_exclude_done(": 3, b"zcb_hit(": 3, b"zcb_cpu_back(": 3,
            b"zcb_take_back_end(": 3, b"zcb_snapshot(": 5, b"zcb_at_timeout(": 4, b"zcb_scratch_watch_start(": 3, b"zcb_copy_back(": 2,
            b"zcb_copy_chunks(": 3, b"zcb_exclude_with(": 3, b"std::getenv(\"BC5_DIRECT_ZERO_SKIP_EXCLUDE\")": 1,
            b"std::getenv(\"BC5_DIRECT_ZERO_SKIP_COPYBACK\")": 1, b"std::getenv(\"BC5_DIRECT_ZERO_SKIP_PROBE\")": 1, b"std::getenv(\"BC5_DIRECT_SCRATCH_WATCH\")": 1}
    for k, v in want.items():
        assert out.count(k) == v, ("uses", k, out.count(k), v)
    # Each function's definition comes before its first call (the declarations block covers zskip_map/_resolve/_take_back).
    for name in (b"zcb_line(", b"zcb_fmt(", b"zcb_sw(", b"zcb_wait(", b"zcb_summary(", b"zcb_probe_back(", b"zcb_copy_chunks(", b"zcb_copy_back(", b"zcb_watch_step(",
                 b"zcb_job_addrs(", b"zcb_touch(", b"zcb_probe_timeout(", b"zcb_watch_timeout(", b"zcb_at_timeout(", b"zcb_scratch_watch_start("):
        first = out.index(name)
        assert out[out.rindex(b"\n", 0, first) + 1:first].startswith(b"static "), ("used before its definition", name)
    assert out.index(b" zcb_switch_lines();") < out.index(b"static void zskip_map(") < out.index(b"static void zcb_switch_lines() {") < out.index(END_LINE)
    assert out.index(b"// ---- end of exp 0401 series e9's (tag zcb) seams") < out.index(END_LINE) < out.index(b"static void direct_sync_one(")
    assert balance(s) == (0, 0, 0) and balance(out) == (0, 0, 0), ("the unit's balance", balance(s), balance(out))
    # Undo (last first): the input must come back byte for byte.
    back = out
    for old, new, name in reversed(done):
        assert back.count(new) == 1, ("undo", name)
        back = back.replace(new, old)
    assert back == s, "undoing the edits does not give the input back"
    assert out.startswith(b"\xef\xbb\xbf") == s.startswith(b"\xef\xbb\xbf"), "the BOM changed"
    return out


def main():
    assert len(sys.argv) == 3, __doc__
    root, outdir = sys.argv[1], sys.argv[2]
    assert os.path.realpath(root) != os.path.realpath(outdir), "the out dir must not be the tree"
    with open(os.path.join(root, REL), "rb") as f:
        s = f.read()
    for m in MARKS:
        assert m not in s, ("refused: the unit has the edit already", REL, m.decode())
    assert md5(s) == PINNED[REL], ("refused: not the pinned input", REL, md5(s), PINNED[REL])
    out = edit_unit(s)
    print(f"# in:  {REL} {md5(s)}  ({len(s)} bytes, LF)", file=sys.stderr)
    dst = os.path.join(outdir, REL)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(dst, "wb") as f:
        f.write(out)
    print(f"{REL} {md5(out)}")


if __name__ == "__main__":
    main()
