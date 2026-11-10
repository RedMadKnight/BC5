#!/usr/bin/env python3
"""BC5 experiment 0401 series e7, tag "cap": caps on the two maps of exp 0403's acb inherit tracking that only grow, each
behind its own switch, off by default (cap0401-notes.md: the survey of every e-series catcher's buffers and the journal,
the memory lines of the night routes, and why these two are the only ones without a bound in the code).
  BC5_DIRECT_INHERIT_PROG_CAP    g_inh_prog (one entry per compute program address a bound acb dispatch ran) at most N
                                 entries, default 65536
  BC5_DIRECT_INHERIT_CENSUS_CAP  each guest queue's ring census (one entry per SET_SH_REG first register and count) at most
                                 N entries, default 4096
Off (unset, empty or "0", bc5::env_on's reading), cap_slot is the map's operator[]: the same entry and the same counts as
today. On, a full map records no new key (counted; journaled the first time and every 65536th); keys already in keep
counting. Both maps exist only with BC5_DIRECT_ACB_INHERIT on: with it off nothing here runs.
And (the top session's follow-up, same evening): BC5_DIRECT_JOURNAL_QUIET, default off: the direct journal (direct.log)
without its per-event lines (per-submission, per-job, per-wait and per-flip timing lines, acb rest prefixes, the
every-64th "submit #n ... OK" lines). Summaries, the memory line, the timeout probe and the crumbs at a timeout, every
catcher's first-occurrence and sampled lines and every error or warning line are written as today. The dropped lines go to
a ring of the last 8192 in memory, written out just before the first line of a fence timeout; every 10 s a line counts
what was dropped. Off: the line takes today's path (one flag test a line, one stderr state line at the first line).
Functions touched: journal (one inserted block after its logging check). New, between journal_min_file and journal:
jq_prefix, jq_has, journal_quiet_kind, JournalQuietRing, journal_quiet_put, journal_quiet_summary, journal_quiet_flush,
journal_quiet_on, journal_quiet_vtake and the test's seams bc5_cap0401_quiet_* / bc5_cap0401_journal_*. The script also
asserts that the unit still writes each line a rule matches with exactly the format the rule was written for.
Unit (one input): src/libs/bc5LleAgc.cpp, series e6's d1cfd9bb (mkgpu0405.py's output); the e7 chain runs zsk, then lzr,
then this script, and re-pins PINNED below (one dict). Functions touched: acb_inherit_track (its four g_inh_prog lines
become one inh_prog_note call), acb_inherit_census (its c.sh line becomes one inh_census_sh call). New, all in the
unit's exp 0403 block (between "// Experiment 0403 (exp 0401 series e3; BC5_DIRECT_ACB_INHERIT" and "// Experiment 0401
(BC5_DIRECT_ACB_CS_PREFIX=1"): cap_parse, cap_slot, inh_caps, inh_cap_refused, inh_prog_note, inh_census_sh, and the CPU
test's extern "C" seams bc5_cap0401_* (always compiled in, never called by the emulator), as exp 0405's gpu seams.
Every anchor must occur exactly once in the input and lie inside that block; a unit that has the edit already is refused;
each edit keeps braces, parentheses and brackets balanced; the inserted text is ASCII; line ends (LF) and the BOM (none)
stay as they are. After editing, the script undoes its edits on the output and asserts that this gives the input back
byte for byte. Prints "src/libs/bc5LleAgc.cpp <md5>". CPU test: cap0401.cpp (--gate cap0401.cpp <out> --like
src/libs/bc5LleAgc.cpp).
usage: mkcap0401.py <tree root in> <out dir>"""
import hashlib
import os
import sys

REL = "src/libs/bc5LleAgc.cpp"
PINNED = {  # input md5 of the unit this script edits (series e6's unit; the top session re-pins it after zsk and lzr)
    REL: "8ddf48f372f7c555c1b3abe609d0905b",  # e7 chain: d1cfd9bb + zsk (8710207e) + lzr
}

MARKS = (b"BC5_DIRECT_INHERIT_PROG_CAP", b"bc5_cap0401_", b"(tag cap)", b"BC5_DIRECT_JOURNAL_QUIET")
REGION = (b"// Experiment 0403 (exp 0401 series e3; BC5_DIRECT_ACB_INHERIT=journal|queue|skip, default off)",
          b"// Experiment 0401 (BC5_DIRECT_ACB_CS_PREFIX=1, default off): the acb side of experiment 0195's CS prefix.")
JREGION = (b"// A line in BC5_GC_DUMP_DIR/direct.log, the record that survives a hang.",
           b"// Seconds since the first call: the time base of the BC5_DIRECT_TIMING journal lines.")
# The lines the quiet rules drop or watch for, each with the exact format the unit writes it with (asserted: a rule must
# not drift from its writer). (format, minimum count in the unit)
QUIET_FORMATS = (
    (rb'journal("timing: t %.3f s %s %u dwords: sync%s %.1f ms, hints %.1f ms q%d\n"', 1),  # rule 1, submit_now
    (rb'journal("timing: #%" PRIu64 " done at t %.3f s, %.1f ms after the sync and hints; device: prepare %.2f list %.2f cs '
     rb'%.2f fence %.2f ms, %u BOs%s\n"', 2),  # rule 2, completion_thread and submit_now
    (rb'journal("timing: t %.3f s after that wait (%s %u dwords)\n"', 1),  # rule 3, submit_split
    (rb'journal("timing: t %.3f s flip %d/%d, VideoOutSubmitFlip took %.1f ms\n"', 1),  # rule 4, SubmitEopFlip
    (rb'journal("acb rest %u..%u of %u dwords: state prefix of %u dwords replayed first\n"', 1),  # rule 5, submit
    (rb'journal("submit #%" PRIu64 " %s %u dwords at %p: pass %" PRIu64 " rewrite %" PRIu64 " drop %" PRIu64 " unmapped %"'
     rb' PRIu64 " cc %" PRIu64 " mappings %zu ... %s rc %d%s%s %.2f ms\n"', 2),  # rule 6, completion_thread, submit_now
    (rb'journal("timeout: fault 0x%" PRIx64 " status 0x%08x\n"', 1),  # triggers
    (rb'journal("reopen: %s\n"', 1),
    (rb'journal("timeout probe: ', 10),
    (rb'at the timeout', 3),
)


def tabs(text):
    """The C++ below is written with 4-space indents; the unit indents with tabs."""
    out = []
    for line in text.split("\n"):
        body = line.lstrip(" ")
        k = len(line) - len(body)
        out.append("\t" * (k // 4) + " " * (k % 4) + body)
    return "\n".join(out).encode("ascii")


# ---- edit 1: the caps' block, after the g_inh_* declarations ---------------------------------------------------------
A_OLD = (b"static std::atomic<uint64_t>          g_inh_skip_heads {0}, g_inh_dropped {0};"
         b"                                     // skip mode\n"
         b"static uint32_t inherit_len(uint32_t h) {\n")
A_BLOCK = tabs(r"""// ---- exp 0401 series e7 (tag cap): caps on the two exp 0403 maps that only grow --------------------------------------
// cap0401-notes.md surveys every e-series catcher's buffers and the journal. With BC5_DIRECT_ACB_INHERIT on,
// acb_inherit_track adds an entry to g_inh_prog for each program address a bound acb dispatch runs, and
// acb_inherit_census one to its queue's census for each SET_SH_REG (first register, count) on a guest ring; nothing ever
// removes one. Both are bounded only by what the title sends. Two switches, each off by default and read once (unset, empty
// and "0" are off, bc5::env_on), cap them:
//   BC5_DIRECT_INHERIT_PROG_CAP    g_inh_prog at most N programs (default 65536: about 5 MiB of map nodes)
//   BC5_DIRECT_INHERIT_CENSUS_CAP  each queue's census at most N SET_SH_REG kinds (default 4096)
// An on value that is a decimal number from 2 to 2^32 is N; any other on value ("1") takes the default. A full map records
// no new key (counted, journaled the first time and every 65536th); the keys already in keep counting. A program that was
// not recorded reads as one never bound in a part of its own: queue mode then leaves its head on the ring's state
// ("unknown, fallback ring"), today's answer for an unknown program; journal mode prints it so. Off (cap 0), cap_slot is
// the map's operator[]: today's entry and counts. The first use journals and prints one line,
// "exp 0401 e7: acb inherit caps: programs <N|off>, census <N|off> per queue".
constexpr uint64_t kInhProgCapDefault   = 65536;
constexpr uint64_t kInhCensusCapDefault = 4096;
static uint64_t cap_parse(const char* e, uint64_t dflt) { // 0: off; otherwise the cap
    if (!bc5::env_on(e)) return 0;
    uint64_t    v = 0;
    const char* c = e;
    for (; *c >= '0' && *c <= '9' && v <= (1ull << 32u); c++) v = v * 10u + static_cast<uint64_t>(*c - '0');
    return *c == 0 && v >= 2 && v <= (1ull << 32u) ? v : dflt;
}
// The entry for key in m, inserted when m holds fewer than cap entries; nullptr when key is new and m is full. cap 0: m[key].
template <class Map>
static typename Map::mapped_type* cap_slot(Map& m, const typename Map::key_type& key, uint64_t cap) {
    if (cap == 0) return &m[key];
    const auto it = m.find(key);
    if (it != m.end()) return &it->second;
    if (m.size() >= cap) return nullptr;
    return &m.emplace(key, typename Map::mapped_type {}).first->second;
}
struct InhCaps {
    uint64_t prog = 0, census = 0; // 0: off
};
static const InhCaps& inh_caps() {
    static const InhCaps c = [] {
        InhCaps v;
        v.prog   = cap_parse(std::getenv("BC5_DIRECT_INHERIT_PROG_CAP"), kInhProgCapDefault);
        v.census = cap_parse(std::getenv("BC5_DIRECT_INHERIT_CENSUS_CAP"), kInhCensusCapDefault);
        char p[24] = "off", s[24] = "off";
        if (v.prog != 0) std::snprintf(p, sizeof(p), "%" PRIu64, v.prog);
        if (v.census != 0) std::snprintf(s, sizeof(s), "%" PRIu64, v.census);
        journal("exp 0401 e7: acb inherit caps: programs %s, census %s per queue\n", p, s);
        std::fprintf(stderr, "[bc5] exp 0401 e7: acb inherit caps: programs %s, census %s per queue\n", p, s);
        return v;
    }();
    return c;
}
static std::atomic<uint64_t> g_inh_cap_refused[2]; // the new keys a full map did not record: 0 programs, 1 census kinds
static void inh_cap_refused(int which, size_t size, uint64_t cap) {
    const uint64_t k = g_inh_cap_refused[which & 1]++;
    if (k == 0 || (k & 0xffffu) == 0)
        journal("exp 0401 e7: acb inherit %s full at %zu entries (cap %" PRIu64 "): a new %s is not recorded (%" PRIu64 " so far)\n", which == 0 ? "program map" : "census", size, cap,
                which == 0 ? "program" : "SET_SH_REG kind", k + 1);
}
// g_inh_prog's entry for pgm as acb_inherit_track keeps it: the title's own dispatches by wave mode, and the queue and part
// that last made one. The caller holds g_inh_mutex. False when the cap did not record a new program.
static bool inh_prog_note(uint64_t pgm, bool w32, const uint32_t* part) {
    const uint64_t cap = inh_caps().prog;
    InheritProg*   p   = cap_slot(g_inh_prog, pgm, cap);
    if (p == nullptr) {
        inh_cap_refused(0, g_inh_prog.size(), cap);
        return false;
    }
    (w32 ? p->own32 : p->own64)++;
    p->queue = t_queue_idx;
    p->part  = part;
    return true;
}
// One SET_SH_REG kind counted in a queue's census, as acb_inherit_census counts it. The caller holds g_inh_mutex.
static bool inh_census_sh(InheritCensus& c, uint32_t key) {
    const uint64_t cap = inh_caps().census;
    uint64_t*      v   = cap_slot(c.sh, key, cap);
    if (v == nullptr) {
        inh_cap_refused(1, c.sh.size(), cap);
        return false;
    }
    (*v)++;
    return true;
}
// ---- end of exp 0401 series e7's (tag cap) block -----------------------------------------------------------------------
""")
A_NEW = (b"static std::atomic<uint64_t>          g_inh_skip_heads {0}, g_inh_dropped {0};"
         b"                                     // skip mode\n" + A_BLOCK +
         b"static uint32_t inherit_len(uint32_t h) {\n")

# ---- edit 2: acb_inherit_track's four g_inh_prog lines -----------------------------------------------------------------
B_OLD = (b"\t\tInheritProg& p = g_inh_prog[pgm];\n"
         b"\t\t(d.w32 ? p.own32 : p.own64)++;\n"
         b"\t\tp.queue = t_queue_idx;\n"
         b"\t\tp.part  = part;\n")
B_NEW = (b"\t\tinh_prog_note(pgm, d.w32, part); // exp 0401 series e7 (tag cap): today's four lines; BC5_DIRECT_INHERIT_PROG_CAP"
         b" off is g_inh_prog[pgm]\n")

# ---- edit 3: acb_inherit_census's c.sh line ------------------------------------------------------------------------------
C_OLD = b"\tif (op == 0x76 && len >= 3) c.sh[((p[1] & 0xffffu) << 8u) | std::min<uint32_t>(len - 2, 255u)]++;\n"
C_NEW = (b"\tif (op == 0x76 && len >= 3) inh_census_sh(c, ((p[1] & 0xffffu) << 8u) | std::min<uint32_t>(len - 2, 255u));"
         b" // exp 0401 series e7 (tag cap): BC5_DIRECT_INHERIT_CENSUS_CAP off is c.sh[key]++\n")

# ---- edit 4: the CPU test's seams, after acb_inherit_census_slice ------------------------------------------------------
D_OLD = (b"\t" + rb"""journal("acb inherit census (exp 0403): queue %d after %" PRIu64 " ring slices, non-IB type-3 packets:%s\n", """
         rb"""t_queue_idx, k + 1, line.empty() ? " none" : line.c_str());""" b"\n}\n\n")
D_SEAMS = tabs(r"""// ---- exp 0401 series e7 (tag cap): the CPU test's seams (cap0401.cpp); always compiled in, never called by the emulator ---
extern "C" uint64_t bc5_cap0401_parse(const char* e, uint64_t dflt) {
    return cap_parse(e, dflt);
}
// cap_slot over a map of the test's own: each key counted once more, as the census counts; out gets (key, count) in key
// order (at most out_cap of them); returns the map's size.
extern "C" uint64_t bc5_cap0401_slot(const uint32_t* keys, uint64_t n, uint64_t cap, uint32_t* out_keys, uint64_t* out_counts, uint64_t out_cap, uint64_t* refused) {
    std::map<uint32_t, uint64_t> m;
    *refused = 0;
    for (uint64_t k = 0; k < n; k++) {
        if (uint64_t* v = cap_slot(m, keys[k], cap); v != nullptr) (*v)++;
        else (*refused)++;
    }
    uint64_t i = 0;
    for (const auto& [key, cnt]: m) {
        if (i < out_cap) {
            out_keys[i]   = key;
            out_counts[i] = cnt;
        }
        i++;
    }
    return i;
}
extern "C" void bc5_cap0401_caps(uint64_t* prog, uint64_t* census) {
    std::lock_guard lk(g_inh_mutex);
    const InhCaps&  c = inh_caps();
    *prog             = c.prog;
    *census           = c.census;
}
extern "C" int bc5_cap0401_prog_note(uint64_t pgm, int w32) { // acb_inherit_track's update of g_inh_prog, for one bound dispatch
    std::lock_guard lk(g_inh_mutex);
    return inh_prog_note(pgm, w32 != 0, nullptr) ? 1 : 0;
}
extern "C" uint64_t bc5_cap0401_prog_size() {
    std::lock_guard lk(g_inh_mutex);
    return g_inh_prog.size();
}
extern "C" int bc5_cap0401_prog_get(uint64_t pgm, uint64_t* own32, uint64_t* own64) {
    std::lock_guard lk(g_inh_mutex);
    const auto      it = g_inh_prog.find(pgm);
    if (it == g_inh_prog.end()) return 0;
    *own32 = it->second.own32;
    *own64 = it->second.own64;
    return 1;
}
extern "C" void bc5_cap0401_census(const uint32_t* p, uint32_t len) { // the real acb_inherit_census (BC5_DIRECT_ACB_INHERIT on)
    acb_inherit_census(p, len);
}
extern "C" uint64_t bc5_cap0401_census_size(uint64_t* ops_76) { // this thread's queue (t_queue_idx): its SET_SH_REG kinds
    std::lock_guard lk(g_inh_mutex);
    *ops_76       = 0;
    const auto it = g_inh_census.find(t_queue_idx);
    if (it == g_inh_census.end()) return 0;
    const auto o = it->second.ops.find(0x76u);
    if (o != it->second.ops.end()) *ops_76 = o->second;
    return it->second.sh.size();
}
extern "C" uint64_t bc5_cap0401_census_get(uint32_t key) {
    std::lock_guard lk(g_inh_mutex);
    const auto      it = g_inh_census.find(t_queue_idx);
    if (it == g_inh_census.end()) return 0;
    const auto s = it->second.sh.find(key);
    return s == it->second.sh.end() ? 0 : s->second;
}
extern "C" uint64_t bc5_cap0401_refused(int which) {
    return g_inh_cap_refused[which & 1].load();
}
// ---- end of exp 0401 series e7's (tag cap) seams ------------------------------------------------------------------------
""")
D_NEW = D_OLD[:-1] + D_SEAMS + b"\n"

# ---- edit 5: BC5_DIRECT_JOURNAL_QUIET, a block between journal_min_file and journal, and one call in journal ----------
J_OLD = (b"\treturn f;\n}\n"
         b"static void journal(const char* fmt, ...) {\n"
         b"\tif (g_dump_dir.empty() || !::Log::Bc5LoggingOn()) { // BC5: the session's logging switch\n"
         b"\t\treturn;\n"
         b"\t}\n"
         b"\tif (g_journal_min) {\n")
J_BLOCK = tabs(r"""// ---- exp 0401 series e7 (tag cap): BC5_DIRECT_JOURNAL_QUIET, the journal without its per-event lines -------------------
// cap0401-notes.md section 6. In the play's environment (bc5-run.env: BC5_DIRECT_JOURNAL=min, BC5_DIRECT_TIMING=1,
// BC5_DIRECT_FRAME_PROFILE=1) direct.log grows by about 0.5 GB in 15 minutes, every arm alike; much of it is lines written
// once per submission, per completed job, per CPU-served wait and per flip. With BC5_DIRECT_JOURNAL_QUIET on (bc5::env_on's
// reading: unset, empty and "0" are off; read once) a whole line of one of these kinds is not written:
//   1 "timing: t <t> s <kind> <n> dwords: sync..."             each submission (submit_now, BC5_DIRECT_TIMING)
//   2 "timing: #<n> done at t ..."                             each completed job (BC5_DIRECT_TIMING)
//   3 "timing: t <t> s after that wait (...)"                  each CPU-served wait (submit_split, BC5_DIRECT_TIMING)
//   4 "timing: t <t> s flip ..., VideoOutSubmitFlip took ..."  each flip (BC5_DIRECT_TIMING; the frame profile line stays)
//   5 "acb rest <a>..<b> of <n> dwords: state prefix of ..."   each acb rest that replays a state prefix (submit)
//   6 "submit #<n> ... OK rc 0 <ms> ms"                        the every-64th submission line, when it went well
// Everything else is written as today: the summaries (timing split, frame profile, job ts, chains, hold tail, the gpu
// group's, the memory line), the timeout probe and the crumbs at a timeout, every catcher's first-occurrence and sampled
// lines, and every line that says FAILED, TIMEOUT, GIVEN UP or the like ("submit #" with FAILED, TIMEOUT or "(retried)"
// stays). Only a whole line is dropped: one that ends with a newline and fits the 1024-byte buffer (longer ones take
// today's path). The dropped lines go to a ring of the last 8192 (192 bytes a line, 1.5 MiB, touched only when on); just
// before the first line of a fence timeout ("submit #... TIMEOUT", "... at the timeout ...", "timeout probe: ",
// "timeout: ", "reopen: ") they are written, oldest first, between two marker lines, so the run-up to a hang that the host
// survives is kept. At most every 10 s, one line counts what was dropped and its bytes. Off: one flag test a line and the
// line takes today's path; the first line journaled prints "[bc5] exp 0401 e7: journal quiet on|off" on stderr.
static double timing_now(); // defined below (the journal's time base)
static bool   jq_prefix(const char* s, size_t n, const char* p) {
    const size_t k = std::strlen(p);
    return n >= k && std::memcmp(s, p, k) == 0;
}
static bool jq_has(const char* s, size_t n, const char* p) { // p within the first n bytes of s
    const size_t k = std::strlen(p);
    for (size_t i = 0; i + k <= n; i++) {
        if (std::memcmp(s + i, p, k) == 0) return true;
    }
    return false;
}
// The kind of a formatted line (n bytes; complete: formatted whole): 1-6 a kind quiet mode drops (the list above), 0 kept,
// -1 kept and the first line of a fence timeout (the dropped lines go out before it).
static int journal_quiet_kind(const char* s, size_t n, bool complete) {
    if (jq_prefix(s, n, "timeout: ") || jq_prefix(s, n, "timeout probe: ") || jq_prefix(s, n, "reopen: ") || jq_has(s, n, "at the timeout") ||
        (jq_prefix(s, n, "submit #") && jq_has(s, n, " TIMEOUT")))
        return -1;
    if (!complete || n == 0 || s[n - 1] != '\n') return 0;
    if (jq_prefix(s, n, "timing: t ")) {
        if (jq_has(s, n, " dwords: sync")) return 1;
        if (jq_has(s, n, " s after that wait")) return 3;
        if (jq_has(s, n, " s flip ") && jq_has(s, n, ", VideoOutSubmitFlip took ")) return 4;
        return 0;
    }
    if (jq_prefix(s, n, "timing: #") && jq_has(s, n, " done at t ")) return 2;
    if (jq_prefix(s, n, "acb rest ") && jq_has(s, n, " dwords: state prefix of ")) return 5;
    if (jq_prefix(s, n, "submit #") && jq_has(s, n, " ... OK rc 0 ") && !jq_has(s, n, "(retried)") && !jq_has(s, n, "FAILED")) return 6;
    return 0;
}
constexpr uint32_t kJqRingLines = 8192;
constexpr uint32_t kJqRingBytes = 192;
struct JournalQuietRing { // the last kJqRingLines dropped lines, each cut to kJqRingBytes - 1 bytes ("...\n" marks a cut)
    char     text[kJqRingLines][kJqRingBytes];
    uint64_t pushed = 0; // lines pushed since the last drain
    void     push(const char* s, size_t n) {
        char* d = text[pushed % kJqRingLines];
        if (n >= kJqRingBytes) {
            std::memcpy(d, s, kJqRingBytes - 5);
            std::memcpy(d + kJqRingBytes - 5, "...\n", 5);
        } else {
            std::memcpy(d, s, n);
            d[n] = 0;
        }
        pushed++;
    }
    template <class F>
    uint32_t drain(F f) { // f(line) for each line held, oldest first; empties the ring; returns how many
        const uint64_t from = pushed > kJqRingLines ? pushed - kJqRingLines : 0;
        for (uint64_t k = from; k < pushed; k++) f(static_cast<const char*>(text[k % kJqRingLines]));
        const uint32_t held = static_cast<uint32_t>(pushed - from);
        pushed              = 0;
        return held;
    }
};
static JournalQuietRing      g_jq_ring;  // BSS: its pages are touched only with the switch on
static std::mutex            g_jq_mutex; // the ring and the count's clock
static std::atomic<uint64_t> g_jq_lines[7], g_jq_bytes {0};
// A formatted line, written as journal() writes one (the same file, the same flushing).
static void journal_quiet_put(const char* s) {
    if (g_journal_min) {
        if (FILE* f = journal_min_file(false); f != nullptr) std::fputs(s, f);
        return;
    }
    char name[512];
    std::snprintf(name, sizeof(name), "%s/direct.log", g_dump_dir.c_str());
    if (FILE* f = std::fopen(name, "a"); f != nullptr) {
        std::fputs(s, f);
        std::fflush(f);
        std::fclose(f);
    }
}
static void journal_quiet_summary(char* out, size_t cap) {
    static const char* const names[7] = {"", "per-submission timing", "per-job timing", "per-wait timing", "per-flip timing", "acb rest", "submit progress"};
    uint64_t                 total    = 0;
    size_t                   w        = 0;
    const auto               add      = [&](int k) {
        if (w < cap) w += static_cast<size_t>(std::max(0, k));
    };
    add(std::snprintf(out, cap, "journal quiet (exp 0401 e7): t %.1f s: not written so far", timing_now()));
    for (int k = 1; k < 7; k++) {
        const uint64_t v = g_jq_lines[k].load();
        total += v;
        if (w < cap) add(std::snprintf(out + w, cap - w, "%s %s %" PRIu64, k == 1 ? ":" : ",", names[k], v));
    }
    if (w < cap) std::snprintf(out + w, cap - w, "; %" PRIu64 " lines, %" PRIu64 " bytes in all\n", total, g_jq_bytes.load());
}
static void journal_quiet_flush() { // the dropped lines held, before a timeout line; the caller holds g_jq_mutex
    if (g_jq_ring.pushed == 0) return;
    char head[200];
    std::snprintf(head, sizeof(head), "journal quiet (exp 0401 e7): the last %" PRIu64 " lines it did not write, oldest first, before the timeout line below:\n",
                  std::min<uint64_t>(g_jq_ring.pushed, kJqRingLines));
    journal_quiet_put(head);
    g_jq_ring.drain([](const char* l) { journal_quiet_put(l); });
    journal_quiet_put("journal quiet (exp 0401 e7): end of the lines it did not write\n");
}
static bool journal_quiet_on() {
    static const bool on = [] {
        const char* e = std::getenv("BC5_DIRECT_JOURNAL_QUIET");
        const bool  v = e != nullptr && e[0] != 0 && !(e[0] == '0' && e[1] == 0); // bc5::env_on's reading (that header comes with the backend)
        std::fprintf(stderr, "[bc5] exp 0401 e7: journal quiet %s\n", v ? "on" : "off");
        if (v)
            journal_quiet_put("exp 0401 e7: journal quiet on, not written: the per-submission, per-job, per-wait and per-flip timing lines, the acb rest "
                              "prefix lines and the every-64th submit lines that went well; the last 8192 of them are written before a fence timeout; "
                              "a count at most every 10 s\n");
        return v;
    }();
    return on;
}
// journal() with the switch on: formats the line; true when it was dropped (and held in the ring) or written here, false
// when journal() writes it as today (longer than the buffer).
static bool journal_quiet_vtake(const char* fmt, va_list ap) __attribute__((format(printf, 1, 0)));
static bool journal_quiet_vtake(const char* fmt, va_list ap) {
    char      line[1024];
    const int n = std::vsnprintf(line, sizeof(line), fmt, ap);
    if (n < 0) return false;
    const bool   complete = static_cast<size_t>(n) < sizeof(line);
    const size_t len      = complete ? static_cast<size_t>(n) : sizeof(line) - 1;
    const int    kind     = journal_quiet_kind(line, len, complete);
    if (kind > 0) {
        g_jq_lines[kind]++;
        g_jq_bytes += len;
        char sum[512] = {};
        {
            std::lock_guard lk(g_jq_mutex);
            g_jq_ring.push(line, len);
            static uint64_t last_ns = 0;
            const uint64_t  now     = SoftCp::now_ns();
            if (last_ns == 0) {
                last_ns = now;
            } else if (now - last_ns >= 10'000'000'000ull) {
                last_ns = now;
                journal_quiet_summary(sum, sizeof(sum));
            }
        }
        if (sum[0] != 0) journal_quiet_put(sum);
        return true;
    }
    if (kind < 0) {
        std::lock_guard lk(g_jq_mutex);
        journal_quiet_flush();
    }
    if (!complete) return false;
    journal_quiet_put(line);
    return true;
}
// The CPU test's seams (cap0401.cpp); always compiled in, never called by the emulator.
extern "C" int bc5_cap0401_quiet_kind(const char* s, uint64_t n, int complete) {
    return journal_quiet_kind(s, static_cast<size_t>(n), complete != 0);
}
// A ring of the test's own: the lines pushed, then drained into out (at most out_cap - 1 bytes, NUL-ended); returns the lines
// drained, *again the lines a second drain gives (0).
extern "C" uint64_t bc5_cap0401_quiet_ring(const char* const* lines, uint64_t n, char* out, uint64_t out_cap, uint64_t* again) {
    auto        ring = std::make_unique<JournalQuietRing>();
    std::string all;
    for (uint64_t k = 0; k < n; k++) ring->push(lines[k], std::strlen(lines[k]));
    const uint32_t held = ring->drain([&all](const char* l) { all += l; });
    *again              = ring->drain([](const char*) {});
    const size_t c      = std::min<size_t>(all.size(), out_cap != 0 ? static_cast<size_t>(out_cap) - 1 : 0);
    std::memcpy(out, all.data(), c);
    if (out_cap != 0) out[c] = 0;
    return held;
}
extern "C" int bc5_cap0401_journal_open(const char* dir) { // the journal's directory, as BC5_GC_DUMP_DIR gives it
    if (!g_dump_dir.empty() || dir == nullptr || dir[0] == 0) return 0;
    g_dump_dir = dir;
    return 1;
}
extern "C" void bc5_cap0401_journal(const char* text) { // one call of the real journal()
    journal("%s", text);
}
extern "C" void bc5_cap0401_journal_flush() {
    if (g_journal_min && !g_dump_dir.empty()) (void)journal_min_file(true);
}
extern "C" int bc5_cap0401_journal_min() {
    return g_journal_min ? 1 : 0;
}
extern "C" int bc5_cap0401_journal_quiet() { // -1 before bc5_cap0401_journal_open (the state line needs the directory)
    return g_dump_dir.empty() ? -1 : journal_quiet_on() ? 1 : 0;
}
extern "C" uint64_t bc5_cap0401_quiet_count(int kind) { // 1-6: the lines of that kind dropped; 0: the bytes dropped
    return kind >= 1 && kind <= 6 ? g_jq_lines[kind].load() : kind == 0 ? g_jq_bytes.load() : 0;
}
extern "C" void bc5_cap0401_quiet_summary(char* out, uint64_t cap) {
    journal_quiet_summary(out, static_cast<size_t>(cap));
}
// ---- end of exp 0401 series e7's (tag cap) journal block ----------------------------------------------------------------
""")
J_CALL = tabs(r"""    if (journal_quiet_on()) { // exp 0401 series e7 (tag cap): BC5_DIRECT_JOURNAL_QUIET; off, the line takes today's path below
        va_list ap;
        va_start(ap, fmt);
        const bool taken = journal_quiet_vtake(fmt, ap);
        va_end(ap);
        if (taken) return;
    }
""")
J_NEW = (b"\treturn f;\n}\n" + J_BLOCK +
         b"static void journal(const char* fmt, ...) {\n"
         b"\tif (g_dump_dir.empty() || !::Log::Bc5LoggingOn()) { // BC5: the session's logging switch\n"
         b"\t\treturn;\n"
         b"\t}\n" + J_CALL +
         b"\tif (g_journal_min) {\n")

EDITS = ((A_OLD, A_NEW, "the caps' block"), (B_OLD, B_NEW, "acb_inherit_track"), (C_OLD, C_NEW, "acb_inherit_census"),
         (D_OLD, D_NEW, "the seams"), (J_OLD, J_NEW, "the journal's quiet switch"))


def balance(b):
    return (b.count(b"{") - b.count(b"}"), b.count(b"(") - b.count(b")"), b.count(b"[") - b.count(b"]"))


def md5(b):
    return hashlib.md5(b).hexdigest()


def function_span(s, head):
    """[start, end) of the function whose first line is head, to its closing brace at column 0."""
    assert s.count(head) == 1, ("the function", head, s.count(head))
    a = s.index(head)
    return a, s.index(b"\n}\n", a) + 3


def edit_unit(s):
    for m in MARKS:
        assert m not in s, ("the unit has the edit already", m)
    assert b"\r" not in s, "a CR in the LF unit"
    assert s.count(REGION[0]) == 1 and s.count(REGION[1]) == 1, "the exp 0403 block's bounds"
    r0, r1 = s.index(REGION[0]), s.index(REGION[1])
    assert r0 < r1
    assert s.count(JREGION[0]) == 1 and s.count(JREGION[1]) == 1, "the journal's bounds"
    j0, j1 = s.index(JREGION[0]), s.index(JREGION[1])
    assert j0 < j1
    spans = {"acb_inherit_track": function_span(s, b"static void acb_inherit_track(const uint32_t* part, uint32_t n) {\n"),
             "acb_inherit_census": function_span(s, b"static void acb_inherit_census(const uint32_t* p, uint32_t len) {\n"),
             "acb_inherit_census_slice": function_span(s, b"static void acb_inherit_census_slice() {\n"),
             "journal_min_file": function_span(s, b"static FILE* journal_min_file(bool flush_now) {\n"),
             "journal": function_span(s, b"static void journal(const char* fmt, ...) {\n")}
    for old, new, what in EDITS:
        assert s.count(old) == 1, ("an anchor does not occur exactly once", what, s.count(old))
        at = s.index(old)
        lo, hi = (j0, j1) if old is J_OLD else (r0, r1)
        assert lo < at and at + len(old) <= hi, ("an anchor lies outside its block", what)
        assert balance(old) == balance(new), ("the edit changes the balance", what, balance(old), balance(new))
        new.decode("ascii")
        assert b"\r" not in new
    # Each replaced line lies in the function it belongs to.
    a, b = spans["acb_inherit_track"]
    assert a < s.index(B_OLD) < b, "edit 2 is not in acb_inherit_track"
    a, b = spans["acb_inherit_census"]
    assert a < s.index(C_OLD) < b, "edit 3 is not in acb_inherit_census"
    a, b = spans["acb_inherit_census_slice"]
    assert a < s.index(D_OLD) < b + 1, "edit 4's anchor is not acb_inherit_census_slice's end"
    a, b = spans["journal_min_file"]
    c, d = spans["journal"]
    assert s.index(J_OLD) == b - len(b"\treturn f;\n}\n") and b == c, "edit 5 is not journal_min_file's end and journal's start"
    assert s.index(J_OLD) + len(J_OLD) < d, "edit 5 runs past journal's start"
    # The quiet rules key on the exact lines the unit writes: each format is still there.
    for fmt, least in QUIET_FORMATS:
        assert s.count(fmt) >= least, ("a line the quiet rules key on is not written as they expect", fmt[:70], s.count(fmt), least)
    out = s
    for old, new, what in EDITS:
        assert out.count(old) == 1, ("anchor after the edits before it", what)
        out = out.replace(old, new)
    # Nothing else changed: every other use of the two maps is as it was.
    for name in (b"g_inh_prog", b"g_inh_census", b".sh[", b".sh."):
        before = s.count(name)
        added = sum(new.count(name) - old.count(name) for old, new, _ in EDITS)
        assert out.count(name) == before + added, ("an unexpected use of", name)
    today = b"InheritProg& p = g_inh_prog[pgm];"
    assert s.count(today) == 1 and out.count(today) == 0, "today's operator[] on g_inh_prog"
    assert s.count(b"g_inh_prog[") == 1 and out.count(b"g_inh_prog[") == 1, "only the comment names g_inh_prog[pgm] now"
    assert balance(out) == balance(s), ("the unit's balance changed", balance(s), balance(out))
    # Undo (last first): the input must come back byte for byte.
    back = out
    for old, new, what in reversed(EDITS):
        assert back.count(new) == 1, ("undo", what)
        back = back.replace(new, old)
    assert back == s, "undoing the edits does not give the input back"
    assert b"\r" not in out, "a CR in the LF unit"
    assert out.startswith(b"\xef\xbb\xbf") == s.startswith(b"\xef\xbb\xbf"), "the BOM changed"
    return out


def main():
    assert len(sys.argv) == 3, __doc__
    root, outdir = sys.argv[1], sys.argv[2]
    assert os.path.abspath(root) != os.path.abspath(outdir), "the out dir must not be the tree"
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
