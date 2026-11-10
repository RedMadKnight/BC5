#!/usr/bin/env python3
"""BC5 experiment 0401 series e8, tag "smp": one default-off switch, the control hang1954-0401.md section "r7all 06:40 (e7
catchers)" asks for, as one edit of src/libs/bc5LleAgc.cpp after the e7 chain (zsk, lzr, cap, flx). smp0401-notes.md has
the design, the costs and the risks.
  BC5_DIRECT_FL_MESHLET_SAMPLE=<s>   catcher (CPU only, no packet): at most once every <s> seconds (1-3600), when a job with
                                     crumbs completes, A4's per-point meshlet walk on its pattern draws (ES 0x11d01345,
                                     0x11d00f85, 0x11d00f8d), read a few ms after its fence; and at a fence timeout the same
                                     walk on the last done draw and on every draw issued and not done. Every walk counts
                                     both range models: model 0 takes a load past NUM_RECORDS as 0 (A4's reading), model 1
                                     reads the memory there all the same. Journal lines only. Needs BC5_DIRECT_FL_CRUMBS=1.
Unset, 0, empty or "off", the unit does what flx's unit does: the walk's two functions keep their old behaviour (the new
parameter defaults to model 0), no state is tracked for it, nothing is kept, nothing is read, no line but the switch line.
Unit (one input): src/libs/bc5LleAgc.cpp, series e7's b010db09 (d1cfd9bb + zsk + lzr + cap + flx).
Edits (each anchor exactly once in the unit): flx_mesh_point and flx_mesh_counts get a defaulted "raw" parameter (model 1);
the smp pure block before exp 0404's end marker (kSmpCap, kSmpDraws, smp_parse, smp_due, smp_counts, smp_point, smp_text);
the switch (smp_period) before flx's host block; fl_keep_done keeps the last done draw with the switch on too; the smp host
block after flx's host block (smp_take, smp_walk, smp_sample, smp_at_timeout); fl_plan_buffer tracks the state with the
switch on; fl_probe walks at a timeout; the CPU test's seams bc5_smp0401_* after flx's seams (always compiled in, never
called by the emulator); one line after each of flx's two fl_keep_done calls (submit_now's sync path, the completion
thread). Each edit keeps braces, parentheses and brackets balanced outside comments and literals; the inserted text is
ASCII; LF line ends; a unit that has the edit already is refused. After editing, the script undoes its edits on the output
and asserts that this gives the input back byte for byte.
Prints "src/libs/bc5LleAgc.cpp <md5>". CPU test: smp0401.cpp (--gate smp0401.cpp <out> --like src/libs/bc5LleAgc.cpp).
usage: mksmp0401.py <tree root in> <out dir>"""
import hashlib
import os
import sys

REL = "src/libs/bc5LleAgc.cpp"
PINNED = {REL: "b010db09b5ab83b36e76e0328671e955"}  # e7 chain: d1cfd9bb + zsk + lzr + cap + flx
MARKS = (b"BC5_DIRECT_FL_MESHLET_SAMPLE", b"bc5_smp0401_", b"(tag smp)")


def tabs(text):
    """The C++ below is written with 4-space indents; the unit indents with tabs."""
    out = []
    for line in text.split("\n"):
        body = line.lstrip(" ")
        k = len(line) - len(body)
        out.append("\t" * (k // 4) + " " * (k % 4) + body)
    return "\n".join(out).encode("ascii")


# ---- the walk's two functions: a defaulted "raw" parameter (range model 1) ------------------------------------------
POINT_SIG_OLD = b"static bool flx_mesh_point(int pat, const uint32_t* ud, uint32_t v6, uint32_t point, const Read& read, FlxMeshPoint& m) {\n"
POINT_SIG_NEW = (b"static bool flx_mesh_point(int pat, const uint32_t* ud, uint32_t v6, uint32_t point, const Read& read, FlxMeshPoint& m, bool raw = false) {"
                 b" // + exp 0401 e8 (smp): raw, range model 1\n")
SLOAD_OLD = b"\t\tif (static_cast<uint64_t>(off) + 4ull * words > extent) {\n\t\t\tm.oob++;\n\t\t\treturn;\n\t\t}\n"
SLOAD_NEW = (b"\t\tif (static_cast<uint64_t>(off) + 4ull * words > extent) {\n\t\t\tm.oob++;\n"
             b"\t\t\tif (!raw) return; // exp 0401 e8 (smp) model 1: read past NUM_RECORDS all the same\n\t\t}\n")
TLOAD_OLD = b"\t\tif (index >= v[2]) {\n\t\t\tm.oob++;\n\t\t\treturn;\n\t\t}\n"
TLOAD_NEW = (b"\t\tif (index >= v[2]) {\n\t\t\tm.oob++;\n"
             b"\t\t\tif (!raw) return; // exp 0401 e8 (smp) model 1: read past NUM_RECORDS all the same\n\t\t}\n")
COUNTS_SIG_OLD = b"static FlxMeshCounts flx_mesh_counts(int pat, const uint32_t* ud, uint32_t v6, uint32_t points, uint32_t cap, const Read& read) {\n"
COUNTS_SIG_NEW = (b"static FlxMeshCounts flx_mesh_counts(int pat, const uint32_t* ud, uint32_t v6, uint32_t points, uint32_t cap, const Read& read, bool raw = false) {"
                  b" // + exp 0401 e8 (smp)\n")
COUNTS_CALL_OLD = b"\t\tif (!flx_mesh_point(pat, ud, v6, i, read, m)) {\n"
COUNTS_CALL_NEW = b"\t\tif (!flx_mesh_point(pat, ud, v6, i, read, m, raw)) {\n"

# ---- the pure block, before exp 0404's end marker -------------------------------------------------------------------
END_ANCHOR = b"// ---- end of experiment 0404's pure part"
SMP_PURE = tabs(r"""// ---- exp 0401 series e8 (tag smp): BC5_DIRECT_FL_MESHLET_SAMPLE, the pure part --------------------------------------------
// hang1954-0401.md "r7all 06:40 (e7 catchers)": A4's readings of the hung draws (point 0 past an 8-entry object list, the
// empty record, headers above the programmed limit of 32) were also seen at submit in completed draws, but no completed
// draw was ever walked per point. smp walks completed draws, and the draws of a timeout again, in two range models: model
// 0 takes a load past NUM_RECORDS as 0 (A4's reading), model 1 reads the memory there all the same. TODO(verify) which
// one the hardware does (hang1954-0401.md: the gfx10 V# OOB_SELECT question).
constexpr uint32_t kSmpCap   = 1024; // points walked per draw and model
constexpr uint32_t kSmpDraws = 64;   // pattern draws walked per sample
static int smp_parse(const char* e, bool* bad) { // whole seconds 1-3600; unset, empty, "0" or "off": 0 (off); anything else: 0, bad
    *bad = false;
    if (e == nullptr || *e == '\0' || std::strcmp(e, "0") == 0 || std::strcmp(e, "off") == 0) return 0;
    char*      end = nullptr;
    const long v   = std::strtol(e, &end, 10);
    if (end == e || *end != '\0' || v < 1 || v > 3600) {
        *bad = true;
        return 0;
    }
    return static_cast<int>(v);
}
static bool smp_due(int64_t now_ms, int64_t& next_ms, int period_s) { // due once now reaches next; then next is a period on
    if (period_s <= 0 || now_ms < next_ms) return false;
    next_ms = now_ms + static_cast<int64_t>(period_s) * 1000;
    return true;
}
static std::string smp_counts(const FlxMeshCounts& c) {
    char t[512];
    std::snprintf(t, sizeof(t),
                  "%u followed of %u (%u not readable), %u by the index path, record flag bit 6 clear %u, meshlet index >= count %u (first %d), headers up to %u vertices "
                  "and %u primitives, above 32 vertices %u, above 64 primitives %u, loads past NUM_RECORDS %u",
                  c.followed, c.points, c.unread, c.index_path, c.flag6, c.index, c.first_index, c.max_v, c.max_p, c.over_v, c.over_p, c.oob);
    return t;
}
static std::string smp_point(const FlxMeshPoint& m) {
    char t[384];
    std::snprintf(t, sizeof(t), "object %u, record index %u at 0x%" PRIx64 " (flags %08x, meshlet count %u, header base %08x), meshlet %u, header %08x (%u vertices, %u primitives), %u loads past NUM_RECORDS%s",
                  m.object, m.rindex, m.rec, m.flags, m.count, m.hbase, m.meshlet, m.header, ((m.header >> 17u) & 0x7fu) + 1u, (m.header >> 24u) + 1u, m.oob, m.ok ? "" : " (a read was refused)");
    return t;
}
// One draw: 0 not a pattern draw (its ES), 1 the user data it reads not known for certain, 2 no readable arguments, 3
// walked. line: the journal line (not for 0). read(address, bytes): the memory, or nullptr.
template <class Read>
static int smp_text(const FlDraw& d, const Read& read, const char* tag, uint64_t n, const char* kind, std::string& line) {
    if (d.es_lo.n != 1 || flx_pattern(d.es_lo.v[0]) == 0) return 0;
    const int pat = flx_pattern(d.es_lo.v[0]);
    char      where[200];
    std::snprintf(where, sizeof(where), "fl meshlet sample (exp 0401 e8 smp): %s: submit #%" PRIu64 " %s op %02x at %u: ES %08x (pattern %d)", tag, n, kind, d.op, d.at,
                  static_cast<uint32_t>(d.es_lo.v[0]), pat);
    uint32_t ud[32] = {}, v6 = 0;
    if (!flx_user_data(d.x, pat, ud)) {
        line = std::string(where) + ": the user data it reads were not known for certain at the draw: not walked";
        return 1;
    }
    const int   v6_from = flx_v6(d.x, v6);
    uint32_t    points = 0, inst = 0;
    const char* from   = nullptr;
    if (d.op == 0x2d) {
        points = d.vcount;
        inst   = 1;
        from   = "the packet";
    } else if (d.args != 0) {
        if (const uint32_t* t = read(d.args, 8); t != nullptr) {
            points = t[0];
            inst   = t[1];
            from   = "memory now";
        }
    }
    if (from == nullptr) {
        line = std::string(where) + ": no readable arguments to count its points: not walked";
        return 2;
    }
    const FlxMeshCounts c0 = flx_mesh_counts(pat, ud, v6, points, kSmpCap, read, false);
    const FlxMeshCounts c1 = flx_mesh_counts(pat, ud, v6, points, kSmpCap, read, true);
    FlxMeshPoint        m0, m1;
    flx_mesh_point(pat, ud, v6, 0, read, m0, false);
    flx_mesh_point(pat, ud, v6, 0, read, m1, true);
    static const char* const v6s[3] = {"GE_USER_VGPR1", "GE_USER_VGPR_EN bit 0 clear", "assumed: GE_USER_VGPR_EN or GE_USER_VGPR1 not known"};
    char                     head[200];
    std::snprintf(head, sizeof(head), ": %u x %u points (from %s)%s, v6 %08x (%s)", points, inst, from, points > kSmpCap ? ", walked up to the cap" : "", v6,
                  v6s[v6_from < 0 || v6_from > 2 ? 2 : v6_from]);
    line = std::string(where) + head + "; model 0 (past NUM_RECORDS read as 0): " + smp_counts(c0) + "; model 1 (past NUM_RECORDS read as the memory there): " + smp_counts(c1) +
           "; point 0, model 0: " + smp_point(m0) + "; point 0, model 1: " + smp_point(m1);
    return 3;
}
// ---- end of exp 0401 series e8's (tag smp) pure block ------------------------------------------------------------------
""")

# ---- the switch, before flx's host block ----------------------------------------------------------------------------
GLUE_ANCHOR = b"// ---- exp 0401 series e7 (tag flx): the switches and the host's side of F1, F2, A1, A4 and A5"
SMP_SWITCH = tabs(r"""// ---- exp 0401 series e8 (tag smp): the switch ------------------------------------------------------------------------------
static int smp_period() { // BC5_DIRECT_FL_MESHLET_SAMPLE: the seconds between two samples, 0 off; read once
    static const int p = [] {
        bool       bad    = false;
        const int  v      = smp_parse(std::getenv("BC5_DIRECT_FL_MESHLET_SAMPLE"), &bad);
        const bool crumbs = fl_crumbs_on();
        char       line[400];
        if (v > 0)
            std::snprintf(line, sizeof(line), "exp 0401 e8 (smp): fl meshlet sample every %d s, at most %u pattern draws of a completed job, %u points per draw and range model%s", v,
                          kSmpDraws, kSmpCap, crumbs ? "" : " (needs BC5_DIRECT_FL_CRUMBS=1: nothing without it)");
        else
            std::snprintf(line, sizeof(line), "exp 0401 e8 (smp): fl meshlet sample off%s", bad ? " (BC5_DIRECT_FL_MESHLET_SAMPLE does not parse: whole seconds 1-3600, 0 or off)" : "");
        journal("%s\n", line);
        std::fprintf(stderr, "[bc5] %s\n", line);
        return v;
    }();
    return p;
}
""")

# ---- fl_keep_done keeps the last done draw with the switch on too ---------------------------------------------------
KEEP_OLD = b"\tif (!flx_switches().probe_state || !plan.crumbs) return;\n"
KEEP_NEW = b"\tif ((!flx_switches().probe_state && smp_period() == 0) || !plan.crumbs) return; // + exp 0401 e8 (smp): kept for its timeout walk too\n"

# ---- the host block, after flx's ------------------------------------------------------------------------------------
HOST_ANCHOR = b"// ---- end of exp 0401 series e7's (tag flx) host block ------------------------------------------------------------------\n"
SMP_HOST = tabs(r"""// ---- exp 0401 series e8 (tag smp): the host's side ----------------------------------------------------------------------
static std::atomic<int64_t>  g_smp_next {0};
static std::atomic<uint64_t> g_smp_samples {0};
static bool smp_take(int period) { // the sample timer: true for one caller once a period
    const int64_t now  = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now().time_since_epoch()).count();
    int64_t       next = g_smp_next.load();
    for (;;) {
        int64_t want = next;
        if (!smp_due(now, want, period)) return false;
        if (g_smp_next.compare_exchange_weak(next, want)) return true;
    }
}
// One draw through the host's mapping of guest memory (covered_sorted), read now; its line in the journal.
static void smp_walk(const FlDraw& d, const std::vector<bc5::direct::Mapping>& maps, const char* tag, uint64_t n, const char* kind) {
    const auto reader = [&maps](uint64_t a, uint64_t bytes) -> const uint32_t* {
        return covered_sorted(maps, a, bytes) ? reinterpret_cast<const uint32_t*>(a) : nullptr;
    };
    std::string line;
    if (smp_text(d, reader, tag, n, kind, line) != 0) journal("%s\n", line.c_str());
}
// A job with crumbs completed (submit_now's sync path, the completion thread): at most once every N s, its pattern draws
// (at most kSmpDraws), walked per point at once, a few ms after its fence, in both range models.
static void smp_sample(const FlPlan& plan, uint64_t n, const char* kind, bool same_device) {
    const int period = smp_period();
    if (period == 0 || !plan.crumbs || !same_device || !g_dev) return;
    uint32_t pattern = 0;
    for (const FlDraw& d: plan.draws) pattern += d.es_lo.n == 1 && flx_pattern(d.es_lo.v[0]) != 0 ? 1u : 0u;
    if (pattern == 0 || !smp_take(period)) return;
    const auto     maps_p = g_dev->sorted_mappings();
    const uint64_t s      = g_smp_samples++;
    char           tag[64];
    std::snprintf(tag, sizeof(tag), "sample %" PRIu64 ", completed", s + 1);
    uint32_t walked = 0;
    for (const FlDraw& d: plan.draws) {
        if (walked >= kSmpDraws) break;
        if (d.es_lo.n != 1 || flx_pattern(d.es_lo.v[0]) == 0) continue;
        smp_walk(d, *maps_p, tag, n, kind);
        walked++;
    }
    journal("fl meshlet sample (exp 0401 e8 smp): sample %" PRIu64 ": submit #%" PRIu64 " %s completed: %u pattern draws of %zu planned, %u walked\n", s + 1, n, kind, pattern,
            plan.draws.size(), walked);
}
// At a fence timeout (fl_probe, the draws issued and not done): the last done draw (this buffer's, or the one fl_keep_done
// kept) and every draw issued and not done, in both range models, read now.
static void smp_at_timeout(const FlPlan& plan, const FlFind& f, uint64_t done, uint64_t n, const char* kind, const std::vector<bc5::direct::Mapping>& maps) {
    if (f.done >= 0) {
        smp_walk(plan.draws[static_cast<std::size_t>(f.done)], maps, "at the timeout, the last done of this buffer", n, kind);
    } else {
        FlDraw   kd;
        uint64_t kn = 0;
        if (flx_kept(done, kd, kn)) smp_walk(kd, maps, "at the timeout, the last done (of the job that completed last)", kn, "-");
        else journal("fl meshlet sample (exp 0401 e8 smp): at the timeout of submit #%" PRIu64 " %s: the last done draw was not kept: not walked\n", n, kind);
    }
    uint32_t lines = 0;
    for (int k = f.first; k >= 0 && k <= f.last && lines < 64; k++) {
        const FlDraw& d = plan.draws[static_cast<std::size_t>(k)];
        if (!d.crumbs) continue;
        smp_walk(d, maps, "at the timeout, issued and not done", n, kind);
        lines++;
    }
}
// ---- end of exp 0401 series e8's (tag smp) host block ------------------------------------------------------------------
""")

# ---- fl_plan_buffer: the state tracked with the switch on -----------------------------------------------------------
STATE_OLD = b"\to.state             = crumbs && (sw.probe_state || sw.meshlet_probe || sw.crumbs_meshlet); // flx A1, A4, A5\n"
STATE_NEW = b"\to.state             = crumbs && (sw.probe_state || sw.meshlet_probe || sw.crumbs_meshlet || smp_period() > 0); // flx A1, A4, A5; exp 0401 e8 (smp)\n"

# ---- fl_probe: the walk at a timeout --------------------------------------------------------------------------------
PROBE_OLD = b"\t\t\tlines++;\n\t\t}\n\t} else if (f.status == 1) {\n"
PROBE_NEW = (b"\t\t\tlines++;\n\t\t}\n"
             b"\t\tif (smp_period() > 0) smp_at_timeout(plan, f, done, n, kind, *maps_p); // exp 0401 e8 (smp): both range models\n"
             b"\t} else if (f.status == 1) {\n")

# ---- the CPU test's seams, after flx's ------------------------------------------------------------------------------
SEAMS_ANCHOR = b"// ---- end of exp 0401 series e7's (tag flx) seams ----------------------------------------------------------------------\n"
SMP_SEAMS = tabs(r"""// ---- exp 0401 series e8 (tag smp): the CPU test's seams (smp0401.cpp); always compiled in, never called by the emulator ----
extern "C" int bc5_smp0401_parse(const char* e, int* bad) {
    bool      b = false;
    const int v = smp_parse(e, &b);
    *bad        = b ? 1 : 0;
    return v;
}
extern "C" int bc5_smp0401_period() { // the unit's reading of the switch
    return smp_period();
}
extern "C" int bc5_smp0401_due(int64_t now_ms, int64_t* next_ms, int period) {
    return smp_due(now_ms, *next_ms, period) ? 1 : 0;
}
extern "C" int bc5_smp0401_take(int period) { // the real timer (the unit's own, global)
    return smp_take(period) ? 1 : 0;
}
extern "C" void bc5_smp0401_consts(uint32_t* out) { // kSmpCap, kSmpDraws, kFlxMeshCap
    out[0] = kSmpCap;
    out[1] = kSmpDraws;
    out[2] = kFlxMeshCap;
}
extern "C" int bc5_smp0401_mesh(uint32_t es, const uint32_t* ud, uint32_t v6, uint32_t points, uint32_t cap, int raw, FlxReadFn read, void* ctx, int32_t* out) { // as bc5_flx0401_mesh, a model
    const auto          reader = [read, ctx](uint64_t a, uint64_t bytes) { return read(a, bytes, ctx); };
    const int           pat    = flx_pattern(es);
    const FlxMeshCounts c      = flx_mesh_counts(pat, ud, v6, points, cap, reader, raw != 0);
    const int32_t       v[14]  = {static_cast<int32_t>(c.points), static_cast<int32_t>(c.followed), static_cast<int32_t>(c.unread), static_cast<int32_t>(c.index_path),
                                  static_cast<int32_t>(c.flag6), static_cast<int32_t>(c.index), static_cast<int32_t>(c.over_v), static_cast<int32_t>(c.over_p),
                                  static_cast<int32_t>(c.max_v), static_cast<int32_t>(c.max_p), static_cast<int32_t>(c.oob), c.first_flag6, c.first_index, c.first_over};
    for (uint32_t k = 0; k < 14; k++) out[k] = v[k];
    return pat;
}
extern "C" int bc5_smp0401_point(uint32_t es, const uint32_t* ud, uint32_t v6, uint32_t point, int raw, FlxReadFn read, void* ctx, uint64_t* out) { // as bc5_flx0401_mesh_point, a model
    const auto     reader = [read, ctx](uint64_t a, uint64_t bytes) { return read(a, bytes, ctx); };
    FlxMeshPoint   m;
    const bool     ok   = flx_mesh_point(flx_pattern(es), ud, v6, point, reader, m, raw != 0);
    const uint64_t v[13] = {m.ok ? 1u : 0u, m.rec_ok ? 1u : 0u, m.path, m.object, m.rindex, m.meshlet, m.flags, m.count, m.hbase, m.header, m.rec, m.hdr, m.oob};
    for (uint32_t i = 0; i < 13; i++) out[i] = v[i];
    return ok ? 1 : 0;
}
// smp_text on a draw of the test's own: x as flx's seams give it (n, v0, v1 per index), es lo, op, at, args, vcount
extern "C" int bc5_smp0401_text(const uint32_t* ns, const uint32_t* v0, const uint32_t* v1, uint32_t count, uint32_t es, uint32_t op, uint32_t at, uint64_t args, uint32_t vcount,
                                FlxReadFn read, void* ctx, char* out, uint32_t cap) {
    FlDraw d;
    d.x          = flx_seam_vals(ns, v0, v1, count);
    d.es_lo.n    = 1;
    d.es_lo.v[0] = es;
    d.op         = op;
    d.at         = at;
    d.args       = args;
    d.vcount     = vcount;
    const auto  reader = [read, ctx](uint64_t a, uint64_t bytes) { return read(a, bytes, ctx); };
    std::string line;
    const int   r = smp_text(d, reader, "test", 7, "dcb", line);
    std::snprintf(out, cap, "%s", line.c_str());
    return r;
}
// the real fl_plan_buffer on a buffer of the test's own (GFX ring, no chain, no mapping): info [3]: draws planned, the size
// of draw 0's tracked state (x), the plan's crumbs
extern "C" uint32_t bc5_smp0401_plan_x(const uint32_t* ib, uint32_t n, const char* kind, uint32_t* info) {
    FlPlan                                  plan;
    std::vector<uint32_t>                   drops;
    const std::vector<bc5::direct::Mapping> none;
    fl_plan_buffer(ib, n, kind, bc5::direct::kGfxRing, nullptr, none, drops, plan);
    info[0] = static_cast<uint32_t>(plan.draws.size());
    info[1] = plan.draws.empty() ? 0u : static_cast<uint32_t>(plan.draws[0].x.size());
    info[2] = plan.crumbs ? 1u : 0u;
    return info[0];
}
// the real smp_sample on a plan of the test's own (no device: it never walks); returns the samples taken so far
extern "C" uint64_t bc5_smp0401_sample(int crumbs, uint32_t es) {
    FlPlan p;
    p.crumbs = crumbs != 0;
    FlDraw d;
    d.es_lo.n    = 1;
    d.es_lo.v[0] = es;
    p.draws.push_back(d);
    smp_sample(p, 9, "dcb", true);
    return g_smp_samples.load();
}
// ---- end of exp 0401 series e8's (tag smp) seams ----------------------------------------------------------------------
""")

# ---- one line after each of flx's two fl_keep_done calls ------------------------------------------------------------
L_SYNC_OLD = (b"\tif (!r.timed_out && r.ok && !r.pending && fl_plan.crumbs) fl_keep_done(fl_plan, n);"
              b" // exp 0401 e7 (flx) A1: the last done draw, for a later timeout\n")
L_SYNC_NEW = L_SYNC_OLD + (b"\tif (!r.timed_out && r.ok && !r.pending && fl_plan.crumbs) smp_sample(fl_plan, n, kind, true);"
                           b" // exp 0401 e8 (smp): the draws of a completed job, at most every N s\n")
L_CQ_OLD = (b"\t\t\tif (!r.timed_out && r.ok && j.fl_plan.crumbs) fl_keep_done(j.fl_plan, j.n);"
            b" // exp 0401 e7 (flx) A1: the last done draw, for a later timeout\n")
L_CQ_NEW = L_CQ_OLD + (b"\t\t\tif (!r.timed_out && r.ok && j.fl_plan.crumbs) smp_sample(j.fl_plan, j.n, j.kind, g_dev && j.dev_gen == g_dev_gen.load());"
                       b" // exp 0401 e8 (smp): the draws of a completed job, at most every N s\n")

# (name, anchor, new text for the anchor), applied in this order; each anchor exactly once in the unit when applied
EDITS = [
    ("flx_mesh_point: raw", POINT_SIG_OLD, POINT_SIG_NEW),
    ("flx_mesh_point: the scalar load past NUM_RECORDS", SLOAD_OLD, SLOAD_NEW),
    ("flx_mesh_point: the typed load past NUM_RECORDS", TLOAD_OLD, TLOAD_NEW),
    ("flx_mesh_counts: raw", COUNTS_SIG_OLD, COUNTS_SIG_NEW),
    ("flx_mesh_counts: its call", COUNTS_CALL_OLD, COUNTS_CALL_NEW),
    ("the pure block", END_ANCHOR, SMP_PURE + END_ANCHOR),
    ("the switch", GLUE_ANCHOR, SMP_SWITCH + GLUE_ANCHOR),
    ("fl_keep_done", KEEP_OLD, KEEP_NEW),
    ("the host block", HOST_ANCHOR, HOST_ANCHOR + SMP_HOST),
    ("fl_plan_buffer: the state", STATE_OLD, STATE_NEW),
    ("fl_probe: the walk at a timeout", PROBE_OLD, PROBE_NEW),
    ("the seams", SEAMS_ANCHOR, SEAMS_ANCHOR + SMP_SEAMS),
    ("submit_now: after fl_keep_done", L_SYNC_OLD, L_SYNC_NEW),
    ("completion_thread: after fl_keep_done", L_CQ_OLD, L_CQ_NEW),
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


def edit_unit(s):
    for m in MARKS:
        assert m not in s, ("the unit has the edit already", m)
    assert b"\r" not in s, "a CR in the LF unit"
    done = []  # (old, new, name) in the order applied, for the undo
    out = s
    for name, old, new in EDITS:
        assert out.count(old) == 1, ("an anchor does not occur exactly once", name, out.count(old))
        assert balance(old) == balance(new), ("the edit changes the balance", name, balance(old), balance(new))
        new.decode("ascii")
        assert b"\r" not in new
        out = out.replace(old, new)
        done.append((old, new, name))
    # Where the blocks landed: the pure block in exp 0404's pure part, the switch before flx's host block, the host block
    # after it and before fl_plan_buffer, the seams after flx's seams and before exp 0024's jobs.
    order = [out.index(x) for x in (b"static bool flx_mesh_point(", b"struct FlDraw {", b"static int smp_parse(", END_ANCHOR, b"static int smp_period()", GLUE_ANCHOR,
                                    b"static void fl_keep_done(", b"static bool flx_kept(", HOST_ANCHOR, b"static void smp_sample(", b"static void smp_at_timeout(",
                                    b"static void fl_plan_buffer(", b"static void fl_probe(", SEAMS_ANCHOR, b"extern \"C\" int bc5_smp0401_parse(",
                                    b"// ---- experiment 0024: jobs in flight")]
    assert order == sorted(order), ("the blocks are out of order", order)
    # definition, the seam, the two call lines / definition, fl_probe / definition, smp_sample, fl_keep_done,
    # fl_plan_buffer, fl_probe, the seam
    assert out.count(b"smp_sample(") == 4 and out.count(b"smp_at_timeout(") == 2 and out.count(b"smp_period()") == 6, \
        (out.count(b"smp_sample("), out.count(b"smp_at_timeout("), out.count(b"smp_period()"))
    assert balance(out) == balance(s), ("the unit's balance changed", balance(s), balance(out))
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
