#!/usr/bin/env python3
"""BC5 experiment 0401 series e9, tag "gvw": the given-up-wait side of the next private test build, as one edit of
src/libs/bc5LleAgc.cpp. hang1954-0401.md, "Deep analysis 2026-11-05 (after e8)" part (b) and "Box reads after the analysis",
is why; gvw0401-notes.md has the design, the costs and the risks. Four switches, each default off:
  BC5_DIRECT_WAIT_LATE_PRODUCER_MS=<ms>       fix (1-2000): a game-thread cpu-wait of the DCB_WAIT_MS class that is about
                                              to be given up keeps waiting on the CPU up to <ms> in all, but only when the
                                              label's writer can still come from another thread or queue: a job on a ring
                                              (exp 0055's registry) or a compute-queue entry the doorbell consumer has not
                                              taken yet, with nothing ahead of it that waits on a label without a writer.
                                              Not when the writer is not rung yet (the waiting thread rings the doorbell,
                                              F284), nor at a cycle. Journal "served late after X ms" or "GIVEN UP after X
                                              ms (late-producer bound)".
  BC5_DIRECT_UNWAITED_FL_DROP=1               fix: after a given-up wait on L, the certainly fast-launch draws of every dcb
                                              submitted later are dropped (FilterOptions::drop_offsets, as exp 0054's drop
                                              and exp 0404's ES skip) until L meets its wait, or for 1 s. Needs exp 0404's
                                              plan (BC5_DIRECT_FL_CRUMBS=1).
  BC5_DIRECT_GIVEUP_JOURNAL=1                 catcher (CPU): each give-up journals its label, its buffer, the label's last
                                              known writer, its submission and its writer's arrival; a fence timeout says
                                              whether the stuck job followed a give-up in its frame.
  BC5_DIRECT_FL_MESHLET_SAMPLE_UNWAITED=1     catcher (CPU): smp's walk (both range models) on every pattern draw of a dcb
                                              submitted after a give-up in its frame, at completion; at most 16 jobs a
                                              second, 64 draws each. Needs BC5_DIRECT_FL_CRUMBS=1 and the draws' state (smp,
                                              or flx A1/A4/A5, as fl_plan_buffer tracks it).
Unset, empty, 0 or "off": e8's behaviour. The only code that runs then: the switch line once, one relaxed atomic store per
slice the doorbell consumer takes, and the flag tests at the hooks.
Unit (one input): src/libs/bc5LleAgc.cpp, series e8's bd181169 (PINNED; re-pinned by the caller when chained after zcb).
Edits (each anchor exactly once in the unit when applied): g_gvw_taken after g_queues; one line after the doorbell
consumer's take; the forward declarations after t_wait_given_up; one line after the hold tail's give-up line; one line at
submit_split's start; the late-producer wait before the "wait detail" line, the " (late-producer bound)" suffix on the
cpu-wait line, the give-up record after "t_wait_given_up = true"; the pure block after smp's pure block; the host block
after smp's host block; the drop after fl_plan_buffer in submit_now and the submission note after its number; the seams
after smp's seams; one line after each of smp's two smp_sample lines; one line before each of the two timeout_probe
timeout lines; the flip after frame_profile_flip in SubmitEopFlip and its stub in the non-direct branch. Each edit keeps
braces, parentheses and brackets balanced outside comments and literals; the inserted text is ASCII; LF line ends; a unit
that has the edit already is refused. After editing, the script undoes its edits on the output and asserts that this
gives the input back byte for byte.
Prints "src/libs/bc5LleAgc.cpp <md5>". CPU test: gvw0401.cpp (on, off, unset).
usage: mkgvw0401.py <tree root in> <out dir>"""
import hashlib
import os
import sys

REL = "src/libs/bc5LleAgc.cpp"
PINNED = {REL: "2fcf42d2d7528e269d821444ee4fbe9e"}  # e9 chain: e8 (bd181169) + zcb
MARKS = (b"BC5_DIRECT_WAIT_LATE_PRODUCER_MS", b"bc5_gvw0401_", b"(tag gvw)", b"g_gvw_taken")


def tabs(text):
    """The C++ below is written with 4-space indents; the unit indents with tabs."""
    out = []
    for line in text.split("\n"):
        body = line.lstrip(" ")
        k = len(line) - len(body)
        out.append("\t" * (k // 4) + " " * (k % 4) + body)
    return "\n".join(out).encode("ascii")


# ---- 1. the doorbell consumer's take, mirrored for the late-producer test -------------------------------------------
QUEUES_OLD = b"static std::vector<QueueReg> g_queues;\n"
QUEUES_NEW = QUEUES_OLD + (b"static std::atomic<uint64_t> g_gvw_taken[64]; // exp 0401 e9 (gvw): 1 + each guest queue's read pointer as the doorbell"
                           b" consumer took it last (0: not yet), for BC5_DIRECT_WAIT_LATE_PRODUCER_MS\n")
TAKE_OLD = b"\t\t\ts.rptr = w_take; // what was served; the rest of the slice stays for the next poll\n"
TAKE_NEW = TAKE_OLD + (b"\t\t\tif (static_cast<std::size_t>(&s - states.data()) < 64) g_gvw_taken[&s - states.data()].store(1ull + w_take, std::memory_order_relaxed);"
                       b" // exp 0401 e9 (gvw): where it took last (one store a slice)\n")

# ---- 2. forward declarations, after t_wait_given_up -----------------------------------------------------------------
TWG_OLD = b"static thread_local bool t_wait_given_up = false;\n"
TWG_NEW = TWG_OLD + tabs(r"""// exp 0401 series e9 (tag gvw): defined in its host block (gvw0401-notes.md), declared here for submit_split and the hold tail.
static int         gvw_late_ms();
static bool        gvw_late(const uint32_t* p, bool is64, uint64_t label, const char* kind, uint32_t num_dwords, uint32_t at, const uint32_t* rest, uint32_t rest_n, uint64_t t0, bool cycle, int* code);
static const char* gvw_bound_suffix(int code);
static void        gvw_given_up(const uint32_t* pkt, uint32_t len, const uint32_t* where, bool is64, uint64_t label, const char* kind, uint32_t num_dwords, uint32_t at, double waited_ms, int code, int cls);
static void        gvw_split_start(const uint32_t* ib, uint32_t num_dwords, const char* kind);
""")

# ---- 3. the hold tail's give-up (ADR 0013) --------------------------------------------------------------------------
HOLD_OLD = (b"\t\t\t\t\tjournal(\"hold tail: the wait on 0x%\" PRIx64 \" GIVEN UP after %.1f ms: its kept wait dropped, the chain goes\\n\", c.label,"
            b" static_cast<double>(held) / 1e6);\n")
HOLD_NEW = HOLD_OLD + (b"\t\t\t\t\tgvw_given_up(c.pkt, 8, c.p, c.is64, c.label, \"dcb\", 0, 0, static_cast<double>(held) / 1e6, -1, 3);"
                       b" // exp 0401 e9 (gvw): the hold tail's give-up, as submit_split's\n")

# ---- 4. submit_split: its start, the late-producer wait, the suffix, the record --------------------------------------
SS_OLD = b"static void submit_split(const uint32_t* ib, uint32_t num_dwords, const char* kind) {\n\tt_wait_given_up = false;\n"
SS_NEW = SS_OLD + (b"\tgvw_split_start(ib, num_dwords, kind); // exp 0401 e9 (gvw): BC5_DIRECT_GIVEUP_JOURNAL's writers and arrivals;"
                   b" this call's give-ups start afresh\n")
LATE_OLD = b"\t\t\t\t\tif (!ok && op == 0x93 && len >= 8) {\n"
LATE_NEW = (b"\t\t\t\t\tint gvw_lp = -1; // exp 0401 e9 (gvw): the late-producer decision (-1: not asked, the switch off)\n"
            b"\t\t\t\t\tif (!ok && limit < 1'000'000'000ull && gvw_late_ms() > 0) ok = gvw_late(p, op == 0x93, label, kind, num_dwords, i, ib + start,"
            b" num_dwords - start, t0, broken, &gvw_lp); // exp 0401 e9 (gvw): BC5_DIRECT_WAIT_LATE_PRODUCER_MS\n") + LATE_OLD
GU_OLD = (b"\t\t\t\t\tif (!ok) journal(\"cpu-wait %s at %u on 0x%\" PRIx64 \": %s after %.1f ms\\n\", op == 0x93 ? \"WAIT_REG_MEM64\" : \"WAIT_REG_MEM\", i,"
          b" label, broken ? \"CYCLE\" : (limit < 1'000'000'000ull ? \"GIVEN UP\" : \"TIMEOUT\"), static_cast<double>(SoftCp::now_ns() - t0) / 1e6);\n")
GU_NEW = (b"\t\t\t\t\tif (!ok) journal(\"cpu-wait %s at %u on 0x%\" PRIx64 \": %s after %.1f ms%s\\n\", op == 0x93 ? \"WAIT_REG_MEM64\" : \"WAIT_REG_MEM\", i,"
          b" label, broken ? \"CYCLE\" : (limit < 1'000'000'000ull ? \"GIVEN UP\" : \"TIMEOUT\"), static_cast<double>(SoftCp::now_ns() - t0) / 1e6,"
          b" gvw_bound_suffix(gvw_lp)); // + exp 0401 e9 (gvw): \" (late-producer bound)\" when it waited for a late producer\n")
REC_OLD = b"\t\t\t\t\tif (!ok) t_wait_given_up = true;\n"
REC_NEW = REC_OLD + (b"\t\t\t\t\tif (!ok) gvw_given_up(p, len, p, op == 0x93, label, kind, num_dwords, i, static_cast<double>(SoftCp::now_ns() - t0) / 1e6, gvw_lp,"
                     b" broken ? 1 : (limit < 1'000'000'000ull ? 0 : 2)); // exp 0401 e9 (gvw): the give-up, for its switches\n")

# ---- 5. the pure block, after smp's -----------------------------------------------------------------------------------
PURE_ANCHOR = b"// ---- end of exp 0401 series e8's (tag smp) pure block ------------------------------------------------------------------\n"
GVW_PURE = tabs(r"""// ---- exp 0401 series e9 (tag gvw): the given-up-wait side, the pure part ---------------------------------------------------
// hang1954-0401.md "Deep analysis 2026-11-05 (after e8)" (b): in both crumbed draw-class hangs (19:54, r7all 06:40) the
// frame's acb reached the host after the hung meshlet dcb; the frame's dcbs had given up (BC5_DIRECT_DCB_WAIT_MS) their
// WAIT_REG_MEM64 == 0 on the acb's section labels, and exp 0054's drop covers only the buffer whose wait was given up
// (t_wait_given_up is per submit_split, chain_given_up_at per segment). gvw0401-notes.md has the four switches. This part
// reads nothing of the host's; the host's side below calls it with the host's state.
constexpr int      kGvwLateMaxMs   = 2000;             // BC5_DIRECT_WAIT_LATE_PRODUCER_MS: whole ms 1-2000
constexpr uint64_t kGvwWindowNs    = 1'000'000'000ull; // a drop window's bound, and how far back a frame reaches
constexpr uint64_t kGvwArriveNs    = 2'000'000'000ull; // how long the give-up journal looks for a give-up's writer
constexpr uint32_t kGvwSampleJobs  = 16;               // unwaited samples a second, each of at most kSmpDraws draws
constexpr uint32_t kGvwScanEntries = 1024;             // compute-queue entries one scan looks at
constexpr uint32_t kGvwScanDwords  = 1u << 21u;        // queue-buffer dwords one scan reads
static int gvw_parse_ms(const char* e, bool* bad) { // whole ms 1-2000; unset, empty, "0" or "off": 0 (off); anything else: 0, bad
    *bad = false;
    if (e == nullptr || *e == '\0' || std::strcmp(e, "0") == 0 || std::strcmp(e, "off") == 0) return 0;
    char*      end = nullptr;
    const long v   = std::strtol(e, &end, 10);
    if (end == e || *end != '\0' || v < 1 || v > kGvwLateMaxMs) {
        *bad = true;
        return 0;
    }
    return static_cast<int>(v);
}
static int gvw_parse_on(const char* e, bool* bad) { // "1" or "on": 1; unset, empty, "0" or "off": 0; anything else: 0, bad
    *bad = false;
    if (e == nullptr || *e == '\0' || std::strcmp(e, "0") == 0 || std::strcmp(e, "off") == 0) return 0;
    if (std::strcmp(e, "1") == 0 || std::strcmp(e, "on") == 0) return 1;
    *bad = true;
    return 0;
}
static uint32_t gvw_len(uint32_t h) { // a packet's dwords, as the unit's walks count them (type 2 and a count of 0x3fff: 1)
    const uint32_t type = h >> 30u, c = (h >> 16u) & 0x3fffu;
    return (type == 3 || type == 0) && c != 0x3fffu ? c + 2u : 1u;
}
static uint64_t gvw_addr(uint32_t lo, uint32_t hi) { // a label's address, as acb_ready and submit_split read it
    return (static_cast<uint64_t>(lo) & ~3ull) | (static_cast<uint64_t>(hi & 0xffffu) << 32u);
}
// Would a label holding value meet the wait w? WAIT_REG_MEM: reference w[4], mask w[5]; WAIT_REG_MEM64: w[4..5], w[6..7];
// compared as wait_satisfied compares (functions 0 and 7: always met).
static bool gvw_meets(const uint32_t* w, bool is64, uint64_t value) {
    const uint64_t ref  = is64 ? (w[4] | (static_cast<uint64_t>(w[5]) << 32u)) : w[4];
    const uint64_t mask = is64 ? (w[6] | (static_cast<uint64_t>(w[7]) << 32u)) : w[5];
    const uint64_t v = (is64 ? value : (value & 0xffffffffull)) & mask, r = ref & mask;
    switch (w[1] & 7u) {
        case 1: return v < r;
        case 2: return v <= r;
        case 3: return v == r;
        case 4: return v != r;
        case 5: return v >= r;
        case 6: return v > r;
        default: return true;
    }
}
// A memory wait at p (WAIT_REG_MEM 0x3c or WAIT_REG_MEM64 0x93 with MEM_SPACE, dword 1 bit 4, as submit_split takes them).
static bool gvw_is_wait(const uint32_t* p, uint32_t len, uint64_t* label, bool* is64) {
    const uint32_t op = (p[0] >> 8u) & 0xffu;
    if ((p[0] >> 30u) != 3 || (op != 0x3c && op != 0x93) || len < 4 || ((p[1] >> 4u) & 1u) == 0) return false;
    *label = gvw_addr(p[2], p[3]);
    *is64  = op == 0x93;
    return true;
}
// The label a packet (len dwords) writes: 0 none, 1 a 32-bit value, 2 a 64-bit value (*v), 3 a value not known (ATOMIC_MEM
// 0x1e). The packets and fields are the ones acb_ready and register_label_writes (experiment 0055) read: WRITE_DATA to
// memory (DST_SEL 1, 2, 5), RELEASE_MEM (DATA_SEL dword 2 bits 31:29), EVENT_WRITE_EOP (DATA_SEL dword 3 bits 31:29).
// A DATA_SEL other than 1 or 2 counts as no label write, as register_label_writes keeps only those two (TODO(verify):
// whether a timestamp select could release a wait on the label).
static int gvw_write_of(const uint32_t* p, uint32_t len, uint64_t* a, uint64_t* v) {
    *a = 0;
    *v = 0;
    if ((p[0] >> 30u) != 3) return 0;
    const uint32_t op = (p[0] >> 8u) & 0xffu;
    if (op == 0x37 && len >= 5) {
        const uint32_t dst = (p[1] >> 8u) & 0xfu;
        if (dst != 1 && dst != 2 && dst != 5) return 0;
        *a = gvw_addr(p[2], p[3]);
        *v = len >= 6 ? (p[4] | (static_cast<uint64_t>(p[5]) << 32u)) : p[4];
        return len >= 6 ? 2 : 1;
    }
    if (op == 0x49 && len >= 8) {
        const uint32_t ds = p[2] >> 29u;
        if (ds != 1 && ds != 2) return 0;
        *a = gvw_addr(p[3], p[4]);
        *v = ds == 2 ? (p[5] | (static_cast<uint64_t>(p[6]) << 32u)) : p[5];
        return static_cast<int>(ds);
    }
    if (op == 0x47 && len >= 6) {
        const uint32_t ds = p[3] >> 29u;
        if (ds != 1 && ds != 2) return 0;
        *a = gvw_addr(p[2], p[3]);
        *v = ds == 2 ? (p[4] | (static_cast<uint64_t>(p[5]) << 32u)) : p[4];
        return static_cast<int>(ds);
    }
    if (op == 0x1e && len >= 4) {
        *a = gvw_addr(p[2], p[3]);
        return 3;
    }
    return 0;
}
static void gvw_labels(const uint32_t* ib, uint32_t n, std::vector<uint64_t>& out) { // every label the packets ib[0, n) write
    for (uint32_t q = 0; q < n;) {
        const uint32_t len = gvw_len(ib[q]);
        if (q + len > n) break;
        uint64_t a = 0, v = 0;
        if (gvw_write_of(ib + q, len, &a, &v) != 0) out.push_back(a);
        q += len;
    }
}
// One buffer of a compute queue, for the wait w on label: does it write the label with a value that meets w (or one not
// known) before its first unready wait, only after it, or not at all? Unready as acb_ready holds a buffer back: a memory
// wait whose label no earlier packet of the buffer writes and that met(packet, is64) does not count as served. block_class:
// 2 its label has no writer the host knows of (whoever writes it may be the waiting thread), 3 the waiting buffer's part
// not yet submitted writes it (ours(label)): a cycle.
struct GvwIbScan {
    bool     before = false, after = false;
    int64_t  block  = -1; // the first unready wait's dword offset (-1: none)
    uint64_t block_label = 0;
    int      block_class = 0;
};
template <class Met, class Ours>
static GvwIbScan gvw_scan_ib(const uint32_t* ib, uint32_t n, const uint32_t* w, bool is64, uint64_t label, const Met& met, const Ours& ours) {
    GvwIbScan             s;
    std::vector<uint64_t> written;
    for (uint32_t q = 0; q < n;) {
        const uint32_t len = gvw_len(ib[q]);
        if (q + len > n) break;
        const uint32_t* p = ib + q;
        uint64_t        a = 0, v = 0, m = 0;
        bool            m64 = false;
        const int       k   = gvw_write_of(p, len, &a, &v);
        if (k != 0) {
            if (a == label && (k == 3 || gvw_meets(w, is64, v))) {
                (s.block < 0 ? s.before : s.after) = true;
                return s;
            }
            if (s.block < 0) written.push_back(a);
        } else if (s.block < 0 && gvw_is_wait(p, len, &m, &m64) && std::find(written.begin(), written.end(), m) == written.end()) {
            if (m64 && len < 8) { // a short WAIT_REG_MEM64 is not read: unknown
                s.block       = q;
                s.block_label = m;
                s.block_class = 2;
            } else if (!met(p, m64)) {
                s.block       = q;
                s.block_label = m;
                s.block_class = ours(m) ? 3 : 2;
            }
        }
        q += len;
    }
    return s;
}
// A guest compute queue's ring as the doorbell consumer reads it (n dwords): r where the consumer took last, w the
// doorbell's write pointer (both taken mod n). The entries [r, w) are rung and not taken yet.
struct GvwQueue {
    const uint32_t* ring = nullptr;
    uint32_t        n = 0, r = 0, w = 0;
};
struct GvwScan {
    bool     scanned = false;
    int      writer  = 0;     // 0 none found; 1 found, nothing unready ahead of it; 2 behind an unready wait without a known writer; 3 behind a cycle
    bool     capped  = false; // a cap was reached, or an entry could not be read or crossed the ring's end: not everything was seen
    int      queue   = -1;    // the queue of the writer taken
    uint64_t block   = 0;     // writer 2, 3: the label it waits behind (0: an entry that could not be read)
    uint32_t entries = 0, ibs = 0, dwords = 0;
};
// Every queue's rung entries in order: INDIRECT_BUFFER entries are read (read(address, bytes): the memory or nullptr) and
// scanned; other packets the soft CP runs on the ring itself in the consumer's post, after the jobs before them. The best
// answer over the queues: a writer with nothing ahead of it, then one behind an unknown wait, then one behind a cycle.
template <class Read, class Met, class Ours>
static GvwScan gvw_scan(const std::vector<GvwQueue>& qs, const uint32_t* w, bool is64, uint64_t label, const Read& read, const Met& met, const Ours& ours) {
    static constexpr int kRank[4] = {3, 0, 1, 2};
    GvwScan              s;
    s.scanned = true;
    for (std::size_t qi = 0; qi < qs.size(); qi++) {
        const GvwQueue& q = qs[qi];
        if (q.ring == nullptr || q.n == 0) continue;
        const uint32_t r = q.r % q.n, pending = (q.w % q.n + q.n - r) % q.n;
        int            hold = 0, found = 0; // hold: the worst unready wait ahead so far (0, 2 or 3)
        uint64_t       hold_label = 0, found_block = 0;
        for (uint32_t k = 0; k < pending && found == 0;) {
            if (s.entries >= kGvwScanEntries) {
                s.capped = true;
                break;
            }
            const uint32_t  off = (r + k) % q.n;
            const uint32_t* p   = q.ring + off;
            const uint32_t  len = gvw_len(p[0]);
            if (off + len > q.n) { // across the ring's end (the consumer submits such a slice in two parts): not followed
                s.capped = true;
                break;
            }
            s.entries++;
            const uint32_t op = (p[0] >> 8u) & 0xffu;
            uint64_t       a = 0, v = 0;
            if ((p[0] >> 30u) == 3 && (op == 0x3f || op == 0x33) && len >= 4) { // INDIRECT_BUFFER (_CNST), read as the consumer reads it
                const uint64_t ta = (p[1] & ~3u) | (static_cast<uint64_t>(p[2] & 0xffu) << 32u);
                const uint32_t tn = p[3] & 0xfffffu;
                if (ta != 0 && tn != 0) {
                    const uint32_t* t = s.dwords + tn <= kGvwScanDwords ? read(ta, static_cast<uint64_t>(tn) * 4u) : nullptr;
                    if (t == nullptr) { // not read: it may write the label, and it may hold the queue
                        s.capped = true;
                        hold     = std::max(hold, 2);
                    } else {
                        s.ibs++;
                        s.dwords += tn;
                        const GvwIbScan b = gvw_scan_ib(t, tn, w, is64, label, met, ours);
                        if (b.before) {
                            found       = hold == 0 ? 1 : hold;
                            found_block = hold_label;
                        } else if (b.after) {
                            found       = std::max(hold, b.block_class);
                            found_block = b.block_class >= hold ? b.block_label : hold_label;
                        }
                        if (b.block >= 0 && b.block_class > hold) {
                            hold       = b.block_class;
                            hold_label = b.block_label;
                        }
                    }
                }
            } else if (const int kw = gvw_write_of(p, len, &a, &v); kw != 0 && a == label && (kw == 3 || gvw_meets(w, is64, v))) {
                found       = hold == 0 ? 1 : hold;
                found_block = hold_label;
            }
            k += len;
        }
        if (found != 0 && kRank[found] < kRank[s.writer]) {
            s.writer = found;
            s.queue  = static_cast<int>(qi);
            s.block  = found_block;
        }
    }
    return s;
}
// The late-producer decision for a wait about to be given up; codes for the journal (gvw_late_name):
//   0 off; 1 not this switch's class (not a game-thread DCB_WAIT_MS wait, or the device is wedged); 2 a cycle (the run-123
//   test, or the writer's queue waits on a label this buffer writes); 3 the same thread: no job on a ring writes the label
//   and no compute queue holds a writer, so it comes only once the waiting thread goes on (F284); 4 not known: the writer
//   waits behind a wait without a known writer, or an entry could not be read; 5 a job on a ring writes it (exp 0055's
//   registry): waited; 6 a compute queue holds the writer and nothing unready stands ahead of it (bc5-ring submits it):
//   waited.
static int gvw_late_decide(int bound_ms, bool can_wait, bool cycle, bool pending, const GvwScan& s) {
    if (bound_ms <= 0) return 0;
    if (!can_wait) return 1;
    if (cycle) return 2;
    if (pending) return 5;
    if (s.writer == 1) return 6;
    if (s.writer == 3) return 2;
    if (s.writer == 2 || s.capped) return 4;
    return 3;
}
static bool gvw_late_waits(int code) {
    return code == 5 || code == 6;
}
static const char* gvw_late_name(int code) {
    static const char* const names[7] = {"off",
                                         "not waited: not a game-thread wait of the DCB_WAIT_MS class, or the device is wedged",
                                         "not waited: a cycle (the run-123 test, or the writer's queue waits on a label this buffer writes)",
                                         "not waited: the same thread (no job on a ring writes the label and no compute queue holds a writer: it comes once the waiting thread goes on, F284)",
                                         "not waited: not known (the writer waits behind a wait without a known writer, or a queue entry could not be read)",
                                         "waited: a job on a ring writes the label (exp 0055's registry)",
                                         "waited: a compute queue holds the writer (bc5-ring submits it)"};
    return code >= 0 && code <= 6 ? names[code] : "?";
}
static const char* gvw_bound_suffix(int code) { // the cpu-wait line's suffix when it waited for a late producer and was given up
    return gvw_late_waits(code) ? " (late-producer bound)" : "";
}
// The drop windows (BC5_DIRECT_UNWAITED_FL_DROP): one per label, open from a give-up until its label meets the wait (only
// when the wait packet was copied whole: checkable) or for kGvwWindowNs; a new give-up on the label starts it again.
struct GvwOpen {
    uint64_t label = 0, t_ns = 0, id = 0;
    uint32_t pkt[8] = {};
    bool     is64 = false, checkable = false;
    uint32_t dcbs = 0, draws = 0; // dropped under it so far
};
static void gvw_window_open(std::vector<GvwOpen>& open, const GvwOpen& o) {
    for (GvwOpen& x: open) {
        if (x.label != o.label) continue;
        const uint32_t d = x.dcbs, k = x.draws;
        x                = o;
        x.dcbs           = d;
        x.draws          = k;
        return;
    }
    open.push_back(o);
}
template <class Met>
static void gvw_window_step(std::vector<GvwOpen>& open, uint64_t now, const Met& met, std::vector<std::pair<GvwOpen, int>>& closed) { // closed: 1 met, 2 the bound
    for (std::size_t k = 0; k < open.size();) {
        const GvwOpen& o   = open[k];
        const int      why = o.checkable && met(o.pkt, o.is64) ? 1 : (now >= o.t_ns && now - o.t_ns >= kGvwWindowNs ? 2 : 0);
        if (why == 0) {
            k++;
            continue;
        }
        closed.emplace_back(o, why);
        open.erase(open.begin() + static_cast<std::ptrdiff_t>(k));
    }
}
// The certainly fast-launch draws of a dcb's plan (fl_class 3, not dropped by the ES skip) go to the filter's drop list, as
// exp 0404's ES skip and exp 0054's drop send theirs (FilterOptions::drop_offsets), and leave the plan as fl_scan leaves a
// draw its caller drops: not planned, no crumbs, no F1/F2 packet, counted as host_dropped. Maybe and unknown draws stay.
static uint32_t gvw_fl_take(FlPlan& plan, std::vector<uint32_t>& drop_offsets) {
    uint32_t taken = 0;
    for (std::size_t k = 0; k < plan.draws.size();) {
        const FlDraw& d = plan.draws[k];
        if (d.cls != 3 || d.drop) {
            k++;
            continue;
        }
        drop_offsets.push_back(d.at);
        if (d.crumbs && plan.planned > 0) plan.planned--;
        if (plan.fl > 0) plan.fl--;
        plan.host_dropped++;
        taken++;
        plan.draws.erase(plan.draws.begin() + static_cast<std::ptrdiff_t>(k));
    }
    if (taken != 0) {
        bool inserts = !plan.heads.empty();
        for (const FlDraw& x: plan.draws) inserts = inserts || x.flush || x.serial;
        plan.inserts = inserts;
    }
    return taken;
}
// Frames: the flips (their times) after g and at or before s, -1 when g is after s; a give-up at g is in the frame of a
// submission at s when no flip came between them and g is at most kGvwWindowNs before s.
static int gvw_flips_between(const std::vector<uint64_t>& flips, uint64_t g, uint64_t s) {
    if (g > s) return -1;
    int k = 0;
    for (const uint64_t f: flips) k += f > g && f <= s ? 1 : 0;
    return k;
}
static bool gvw_in_frame(const std::vector<uint64_t>& flips, uint64_t g, uint64_t s) {
    return gvw_flips_between(flips, g, s) == 0 && s - g <= kGvwWindowNs;
}
static bool gvw_rate(int64_t now_ms, int64_t& sec, uint32_t& used) { // at most kGvwSampleJobs a second (whole seconds of now_ms)
    const int64_t this_sec = now_ms / 1000;
    if (this_sec != sec) {
        sec  = this_sec;
        used = 0;
    }
    if (used >= kGvwSampleJobs) return false;
    used++;
    return true;
}
static std::string gvw_retag(const std::string& line) { // smp's draw line under gvw's tag: the same fields after it
    static const std::string from = "fl meshlet sample (exp 0401 e8 smp): ";
    if (line.compare(0, from.size(), from) != 0) return line;
    return "fl meshlet sample (exp 0401 e9 gvw): " + line.substr(from.size());
}
// The journal's lines. Each starts with a prefix BC5_DIRECT_JOURNAL_QUIET keeps (journal_quiet_kind drops only its six
// kinds): "exp 0401 e9 (gvw): ", "gvw (exp 0401 e9): ", "cpu-wait " or "fl meshlet sample (exp 0401 e9 gvw): "; the timeout
// line says "at the timeout", which quiet mode keeps and writes its held lines before.
static std::string gvw_fmt(const char* fmt, ...) __attribute__((format(printf, 1, 2)));
static std::string gvw_fmt(const char* fmt, ...) {
    char    t[1024];
    va_list ap;
    va_start(ap, fmt);
    const int k = std::vsnprintf(t, sizeof(t), fmt, ap);
    va_end(ap);
    if (k < 0) return std::string();
    return std::string(t, std::min(static_cast<std::size_t>(k), sizeof(t) - 1));
}
static const char* gvw_cls_name(int cls) { // what the give-up was
    static const char* const names[4] = {"GIVEN UP", "CYCLE", "TIMEOUT", "the hold tail's GIVEN UP"};
    return cls >= 0 && cls <= 3 ? names[cls] : "?";
}
static std::string gvw_switch_line(int late_ms, bool late_bad, bool drop, bool drop_bad, bool planned, bool gj, bool gj_bad, bool sample, bool sample_bad, bool state) {
    std::string s = late_ms > 0 ? gvw_fmt("exp 0401 e9 (gvw): late producer wait up to %d ms in all", late_ms) : std::string("exp 0401 e9 (gvw): late producer wait off");
    if (late_bad) s += " (BC5_DIRECT_WAIT_LATE_PRODUCER_MS does not parse: whole ms 1-2000, 0 or off)";
    s += drop ? ", unwaited fl drop on" : ", unwaited fl drop off";
    if (drop && !planned) s += " (needs exp 0404's plan of the dcbs' draws, BC5_DIRECT_FL_CRUMBS=1: nothing without it)";
    if (drop_bad) s += " (BC5_DIRECT_UNWAITED_FL_DROP does not parse: 1, on, 0 or off)";
    s += gj ? ", give-up journal on" : ", give-up journal off";
    if (gj_bad) s += " (BC5_DIRECT_GIVEUP_JOURNAL does not parse: 1, on, 0 or off)";
    s += sample ? ", unwaited meshlet sample on (at most 16 jobs a second, 64 pattern draws each)" : ", unwaited meshlet sample off";
    if (sample && !state)
        s += " (needs BC5_DIRECT_FL_CRUMBS=1 and the draws' user data, which fl_plan_buffer tracks with BC5_DIRECT_FL_MESHLET_SAMPLE, _FL_PROBE_STATE, _FL_MESHLET_PROBE or "
             "_FL_CRUMBS_MESHLET: no draw walked without them)";
    if (sample_bad) s += " (BC5_DIRECT_FL_MESHLET_SAMPLE_UNWAITED does not parse: 1, on, 0 or off)";
    return s;
}
static std::string gvw_line_decision(uint64_t label, const char* kind, uint32_t dwords, uint32_t at, double before_ms, int code, const GvwScan& s, bool pending, bool ok, double after_ms) {
    std::string seen;
    if (pending) {
        seen = "a job on a ring writes it";
    } else if (!s.scanned) {
        seen = "the queues not scanned";
    } else {
        seen = gvw_fmt("queues: %u entries, %u buffers, %u dwords read%s", s.entries, s.ibs, s.dwords, s.capped ? ", not all seen" : "");
        if (s.writer != 0) seen += gvw_fmt("; the writer in queue %d", s.queue);
        if (s.writer >= 2) seen += gvw_fmt(", behind a wait on 0x%" PRIx64, s.block);
    }
    return gvw_fmt("gvw (exp 0401 e9): late producer of 0x%" PRIx64 " (%s %u dwords, its wait at %u not met after %.1f ms): %s; %s; then %s after %.1f ms", label, kind, dwords, at, before_ms,
                   gvw_late_name(code), seen.c_str(), !gvw_late_waits(code) ? "given up as without the switch" : (ok ? "met: served late" : "still not met: given up at the bound"),
                   after_ms);
}
static std::string gvw_line_served(bool is64, uint32_t at, uint64_t label, double ms, int code) {
    return gvw_fmt("cpu-wait %s at %u on 0x%" PRIx64 ": served late after %.1f ms (exp 0401 e9 gvw: %s)", is64 ? "WAIT_REG_MEM64" : "WAIT_REG_MEM", at, label, ms, gvw_late_name(code));
}
static std::string gvw_line_giveup(uint64_t id, uint64_t label, int cls, const char* kind, uint32_t dwords, const void* where, uint32_t at, double waited_ms, double t_s, uint64_t flip, int code,
                                   int pending_ring, bool seen, const char* w_kind, uint32_t w_dwords, bool w_game, double w_ago_ms) {
    std::string wr = pending_ring >= 0 ? gvw_fmt("a job on ring %d writes it (pending)", pending_ring) : std::string("no job on a ring writes it");
    wr += seen ? gvw_fmt("; last seen written by %s %u dwords from %s, %.1f ms before", w_kind, w_dwords, w_game ? "the game's thread" : "bc5-ring", w_ago_ms)
               : std::string("; not seen written since the switch was read");
    return gvw_fmt("gvw (exp 0401 e9): give-up #%" PRIu64 ": the wait on 0x%" PRIx64 " (%s) of %s %u dwords at %p, at %u, after %.1f ms, t %.3f s, flip %" PRIu64
                   "; late producer: %s; the label's writer: %s",
                   id, label, gvw_cls_name(cls), kind, dwords, where, at, waited_ms, t_s, flip, code < 0 ? "not asked (its switch off, or not a wait of its class)" : gvw_late_name(code), wr.c_str());
}
// how: 1 a buffer that writes it passed submit_split, 2 a job on a ring writes it now, 3 the label met, 4 none within 2 s
static std::string gvw_line_arrival(uint64_t id, uint64_t label, int how, double ms, uint64_t flips, const char* kind, uint32_t dwords, bool game, int ring) {
    std::string what;
    if (how == 1) what = gvw_fmt("its writer arrived: %s %u dwords from %s", kind, dwords, game ? "the game's thread" : "bc5-ring");
    else if (how == 2) what = gvw_fmt("a job on ring %d writes it now (its buffer was not seen at submit_split's start)", ring);
    else if (how == 3) what = "the label met, no writer seen";
    else what = "no writer seen and the label not met";
    return gvw_fmt("gvw (exp 0401 e9): give-up #%" PRIu64 " on 0x%" PRIx64 ": %s, %.1f ms after the give-up, %" PRIu64 " flips later", id, label, what.c_str(), ms, flips);
}
static std::string gvw_line_carried(uint64_t id, uint64_t label, uint64_t n, const char* kind, double ms) {
    return gvw_fmt("gvw (exp 0401 e9): give-up #%" PRIu64 " on 0x%" PRIx64 ": its buffer went to the GPU in submit #%" PRIu64 " %s, %.1f ms after the give-up", id, label, n, kind, ms);
}
static std::string gvw_line_drop(uint64_t n, const char* kind, uint32_t dropped, uint32_t draws, uint32_t kept, const std::string& open) {
    return gvw_fmt("gvw (exp 0401 e9): unwaited fl drop: submit #%" PRIu64 " %s: %u certainly fast-launch draws dropped of %u (%u maybe or unknown kept); open give-ups: %s", n, kind, dropped,
                   draws, kept, open.c_str());
}
static std::string gvw_line_closed(const GvwOpen& o, int why, double ms) {
    return gvw_fmt("gvw (exp 0401 e9): unwaited fl drop window of give-up #%" PRIu64 " on 0x%" PRIx64 " closed: %s after %.1f ms; %u draws dropped in %u dcbs under it", o.id, o.label,
                   why == 1 ? "the label met" : "the 1-s bound", ms, o.draws, o.dcbs);
}
struct GvwGu { // a give-up, for the timeout line
    uint64_t id = 0, label = 0, t_ns = 0;
    int      cls = 0;
};
// At a fence timeout: did the stuck job (submitted at s) follow a give-up in its frame? The give-ups within kGvwWindowNs
// before s, newest first (8 named), with their ages and the flips between.
static std::string gvw_line_timeout(uint64_t n, const char* kind, uint64_t s, const std::vector<GvwGu>& gus, const std::vector<uint64_t>& flips, bool* in_frame) {
    std::string list;
    uint32_t    within = 0;
    bool        frame  = false;
    for (auto it = gus.rbegin(); it != gus.rend(); ++it) {
        if (it->t_ns > s || s - it->t_ns > kGvwWindowNs) continue;
        const int f = gvw_flips_between(flips, it->t_ns, s);
        frame       = frame || f == 0;
        if (within++ < 8)
            list += gvw_fmt("%s0x%" PRIx64 " (give-up #%" PRIu64 ", %s, %.1f ms before, %d flips between)", list.empty() ? ": " : ", ", it->label, it->id, gvw_cls_name(it->cls),
                            static_cast<double>(s - it->t_ns) / 1e6, f);
    }
    if (in_frame != nullptr) *in_frame = frame;
    return gvw_fmt("gvw (exp 0401 e9): at the timeout of submit #%" PRIu64 " %s: it followed a given-up wait in its frame: %s; give-ups within 1 s before its submission: %u%s", n, kind,
                   frame ? "yes" : "no", within, list.c_str());
}
static std::string gvw_line_sample_end(uint64_t n, const char* kind, uint32_t pattern, std::size_t planned, uint32_t walked, const std::string& why) {
    return gvw_fmt("fl meshlet sample (exp 0401 e9 gvw): unwaited: submit #%" PRIu64 " %s completed: %u pattern draws of %zu planned, %u walked; %s", n, kind, pattern, planned, walked,
                   why.c_str());
}
// ---- end of exp 0401 series e9's (tag gvw) pure block ------------------------------------------------------------------
""")

# ---- 6. the host block, after smp's -----------------------------------------------------------------------------------
HOST_ANCHOR = b"// ---- end of exp 0401 series e8's (tag smp) host block ------------------------------------------------------------------\n"
GVW_HOST = tabs(r"""// ---- exp 0401 series e9 (tag gvw): the host's side ----------------------------------------------------------------------
// The thread model the late-producer test rests on (gvw0401-notes.md section 2): a dcb reaches the host on the title's own
// thread, inside its submit ioctl (gc_ioctl 0xc0488131, 0xc0188132, 0xc0108102, 0xc020810c: submit_raw / submit_ib_packet
// -> Direct::submit -> submit_split; on_game_thread(), t_cq 0); an acb only on bc5-ring (queue_consumer_thread, set_source(1),
// "ring" slices -> submit_split(..., "acb")), from the guest compute queues the title rings by writing their doorbell page.
// F284: no doorbell is written while the game thread sits in such a wait. So a writer that is not rung yet comes only once
// the waiting thread returns: waiting for it is a self-deadlock until the bound, and the switch does not wait then.
struct GvwSwitches {
    int  late_ms = 0;
    bool drop = false, gu_journal = false, sample = false;
    bool any() const {
        return drop || gu_journal || sample;
    }
};
static const GvwSwitches& gvw_switches() { // read once; the first submit_split (or flip) journals them
    static const GvwSwitches s = [] {
        GvwSwitches v;
        bool        bad[4] = {false, false, false, false};
        v.late_ms          = gvw_parse_ms(std::getenv("BC5_DIRECT_WAIT_LATE_PRODUCER_MS"), &bad[0]);
        v.drop             = gvw_parse_on(std::getenv("BC5_DIRECT_UNWAITED_FL_DROP"), &bad[1]) != 0;
        v.gu_journal       = gvw_parse_on(std::getenv("BC5_DIRECT_GIVEUP_JOURNAL"), &bad[2]) != 0;
        v.sample           = gvw_parse_on(std::getenv("BC5_DIRECT_FL_MESHLET_SAMPLE_UNWAITED"), &bad[3]) != 0;
        // What switches 2 and 4 need of exp 0404 and flx, asked only when they are on (off: nothing else is read here).
        // planned: fl_plan_buffer plans the draws; state: it also tracks their user data (its o.state).
        const bool        planned = v.drop && (fl_crumbs_on() || !fl_skip_es().empty() || flx_switches().flush != 0 || flx_switches().serial);
        const bool        state   = v.sample && fl_crumbs_on() && (flx_switches().probe_state || flx_switches().meshlet_probe || flx_switches().crumbs_meshlet || smp_period() > 0);
        const std::string line    = gvw_switch_line(v.late_ms, bad[0], v.drop, bad[1], planned, v.gu_journal, bad[2], v.sample, bad[3], state);
        journal("%s\n", line.c_str());
        std::fprintf(stderr, "[bc5] %s\n", line.c_str());
        return v;
    }();
    return s;
}
static int gvw_late_ms() {
    return gvw_switches().late_ms;
}
struct GvwRecord { // a give-up
    uint64_t        id = 0, label = 0, t_ns = 0, flip = 0, submit = ~0ull;
    double          t_s = 0, waited_ms = 0;
    const uint32_t* wait = nullptr; // the wait in the title's buffer: the chain segment that carries it is found by it
    uint32_t        pkt[8] = {};
    bool            is64 = false, checkable = false, game = false;
    char            kind[12] = {};
    uint32_t        dwords = 0, at = 0;
    int             cls = 0, arrived = 0; // cls: gvw_cls_name; arrived: 0 not yet, else gvw_line_arrival's how
};
struct GvwWriter { // a label's last writer seen at submit_split's start
    uint64_t t_ns = 0;
    char     kind[12] = {};
    uint32_t dwords = 0;
    bool     game = false;
};
static std::mutex                              g_gvw_mu;          // everything below but the line ring
static std::deque<GvwRecord>                   g_gvw_recs;        // the last 256 give-ups
static uint64_t                                g_gvw_ids = 0;     // give-ups so far
static std::vector<GvwOpen>                    g_gvw_open;        // switch 2's windows
static std::deque<uint64_t>                    g_gvw_flips;       // the last 64 flips (SoftCp::now_ns)
static uint64_t                                g_gvw_flip_n = 0;  // flips so far
static std::unordered_map<uint64_t, GvwWriter> g_gvw_writers;     // switch 3: each label's last writer
static std::map<uint64_t, std::string>         g_gvw_marks;       // switch 4: dcbs submitted after a give-up in their frame, and why
static int64_t                                 g_gvw_rate_sec  = -1;
static uint32_t                                g_gvw_rate_used = 0;
static uint64_t                                g_gvw_refused   = 0; // switch 4: marked jobs the 16-a-second cap left unwalked
static std::mutex                              g_gvw_last_mu;
static std::deque<std::string>                 g_gvw_last;        // the last 32 lines written (bc5_gvw0401_last reads them)
static thread_local std::vector<uint64_t>      t_gvw_ids;         // the give-ups of this thread's current submit_split call
static void gvw_put(const std::string& line) {
    journal("%s\n", line.c_str());
    std::lock_guard lk(g_gvw_last_mu);
    g_gvw_last.push_back(line);
    if (g_gvw_last.size() > 32) g_gvw_last.pop_front();
}
static double gvw_ms(uint64_t now, uint64_t then) {
    return now >= then ? static_cast<double>(now - then) / 1e6 : 0.0;
}
static void gvw_flip() { // SubmitEopFlip: a frame boundary
    if (!gvw_switches().any()) return;
    std::lock_guard lk(g_gvw_mu);
    g_gvw_flips.push_back(SoftCp::now_ns());
    if (g_gvw_flips.size() > 64) g_gvw_flips.pop_front();
    g_gvw_flip_n++;
}
// Exp 0055's registry: the ring of the label's last pending write (a job submitted and not completed), -1 none.
static int gvw_pending_ring(uint64_t label) {
    std::lock_guard          lk(g_plw_mutex);
    const PendingLabelWrite* last = nullptr;
    for (const auto& x: g_plw) {
        if (x.label == label && (last == nullptr || x.order >= last->order)) last = &x;
    }
    return last == nullptr ? -1 : last->ring;
}
static bool gvw_pending_meets(const uint32_t* w, bool is64) { // will that write meet the wait w (ring_will_satisfy on its ring)
    const int ring = gvw_pending_ring(gvw_addr(w[2], w[3]));
    return ring >= 0 && ring_will_satisfy(w, is64, ring);
}
static bool gvw_within(const uint32_t* p, const uint32_t* src, uint32_t n) {
    const uintptr_t a = reinterpret_cast<uintptr_t>(p), b = reinterpret_cast<uintptr_t>(src);
    return a >= b && a < b + static_cast<uintptr_t>(n) * 4u;
}
// The guest compute queues as the doorbell consumer sees them: from where it took last (g_gvw_taken; before its first take,
// the read pointer it publishes in the dword right behind the ring) to the doorbell's write pointer (queue_consumer_thread).
static std::vector<GvwQueue> gvw_queues() {
    std::vector<QueueReg> regs;
    {
        std::lock_guard lock(g_mutex);
        regs = g_queues;
    }
    std::vector<GvwQueue> qs(regs.size());
    for (std::size_t i = 0; i < regs.size(); i++) {
        const QueueReg& q = regs[i];
        if (q.ring_base == 0 || q.ring_end <= q.ring_base || q.doorbell_page == 0) continue;
        GvwQueue& g          = qs[i];
        g.n                  = static_cast<uint32_t>((q.ring_end - q.ring_base) / 4);
        g.ring               = g.n != 0 ? reinterpret_cast<const uint32_t*>(q.ring_base) : nullptr;
        const uint64_t taken = i < 64 ? g_gvw_taken[i].load(std::memory_order_relaxed) : 0;
        const uint64_t pub   = *reinterpret_cast<const volatile uint32_t*>(q.ring_end);
        g.r                  = g.n != 0 ? static_cast<uint32_t>((taken != 0 ? taken - 1 : pub) % g.n) : 0;
        g.w                  = g.n != 0 ? static_cast<uint32_t>(reinterpret_cast<const volatile uint64_t*>(q.doorbell_page)[q.d == 0 ? 0 : q.d - 1] % g.n) : 0;
    }
    return qs;
}
// Switch 1's inputs and decision: a pending write (exp 0055), else the queues' scan; rest: the waiting buffer's part not
// yet submitted (its labels make a cycle). read: a queue buffer's memory, or nullptr.
template <class Read>
static int gvw_late_code(const uint32_t* w, bool is64, uint64_t label, const uint32_t* rest, uint32_t rest_n, bool can_wait, bool cycle, int bound_ms, const Read& read, GvwScan& scan,
                         bool& pending) {
    scan    = GvwScan {};
    pending = false;
    if (bound_ms > 0 && can_wait && !cycle) {
        pending = gvw_pending_meets(w, is64);
        if (!pending) {
            std::vector<uint64_t> ours;
            gvw_labels(rest, rest_n, ours);
            const auto met  = [](const uint32_t* x, bool x64) { return wait_satisfied(x, x64) || gvw_pending_meets(x, x64); };
            const auto mine = [&ours](uint64_t a) { return std::find(ours.begin(), ours.end(), a) != ours.end(); };
            scan            = gvw_scan(gvw_queues(), w, is64, label, read, met, mine);
        }
    }
    return gvw_late_decide(bound_ms, can_wait, cycle, pending, scan);
}
static bool gvw_late_poll(const uint32_t* w, bool is64, uint64_t t0, uint64_t bound_ns) { // the label until it meets w, up to bound_ns after t0
    for (;;) {
        if (wait_satisfied(w, is64)) return true;
        if (SoftCp::now_ns() - t0 >= bound_ns) return false;
        std::this_thread::sleep_for(std::chrono::microseconds(50));
    }
}
// submit_split, a game-thread wait of the DCB_WAIT_MS class about to be given up (the switch on): decide, and wait when the
// writer can still come from another thread or queue. True: met (served late). *code: the decision.
static bool gvw_late(const uint32_t* p, bool is64, uint64_t label, const char* kind, uint32_t num_dwords, uint32_t at, const uint32_t* rest, uint32_t rest_n, uint64_t t0, bool cycle, int* code) {
    const int                                                bound    = gvw_late_ms();
    const bool                                               can_wait = !g_dev || !g_dev->wedged();
    std::shared_ptr<const std::vector<bc5::direct::Mapping>> maps_p;
    if (g_dev) maps_p = g_dev->sorted_mappings();
    const auto reader = [&maps_p](uint64_t a, uint64_t bytes) -> const uint32_t* { // a queue's buffer through the host's mapping (covered_sorted)
        return maps_p && covered_sorted(*maps_p, a, bytes) ? reinterpret_cast<const uint32_t*>(a) : nullptr;
    };
    const double before  = gvw_ms(SoftCp::now_ns(), t0);
    GvwScan      scan;
    bool         pending = false;
    *code                = gvw_late_code(p, is64, label, rest, rest_n, can_wait, cycle, bound, reader, scan, pending);
    const bool   ok      = gvw_late_waits(*code) && gvw_late_poll(p, is64, t0, static_cast<uint64_t>(bound) * 1'000'000ull);
    const double after   = gvw_ms(SoftCp::now_ns(), t0);
    if (*code != 0) gvw_put(gvw_line_decision(label, kind, num_dwords, at, before, *code, scan, pending, ok, after));
    if (ok) gvw_put(gvw_line_served(is64, at, label, after, *code));
    return ok;
}
// A give-up (submit_split's, with cls 0 given up, 1 a cycle, 2 a timeout; the hold tail's, cls 3): kept for switches 2-4.
static void gvw_given_up(const uint32_t* pkt, uint32_t len, const uint32_t* where, bool is64, uint64_t label, const char* kind, uint32_t num_dwords, uint32_t at, double waited_ms, int code, int cls) {
    const GvwSwitches& sw = gvw_switches();
    if (!sw.any()) return;
    GvwRecord r;
    r.label     = label;
    r.t_ns      = SoftCp::now_ns();
    r.t_s       = timing_now();
    r.wait      = where;
    r.is64      = is64;
    r.checkable = len >= (is64 ? 8u : 6u); // what wait_satisfied reads
    for (uint32_t k = 0; k < 8 && k < len; k++) r.pkt[k] = pkt[k];
    r.game = on_game_thread();
    std::snprintf(r.kind, sizeof(r.kind), "%s", kind);
    r.dwords        = num_dwords;
    r.at            = at;
    r.cls           = cls;
    r.waited_ms     = waited_ms;
    const int ring  = sw.gu_journal ? gvw_pending_ring(label) : -1;
    bool      seen  = false;
    GvwWriter wr;
    {
        std::lock_guard lk(g_gvw_mu);
        r.id   = ++g_gvw_ids;
        r.flip = g_gvw_flip_n;
        if (const auto it = g_gvw_writers.find(label); sw.gu_journal && it != g_gvw_writers.end()) {
            wr   = it->second;
            seen = true;
        }
        g_gvw_recs.push_back(r);
        if (g_gvw_recs.size() > 256) g_gvw_recs.pop_front();
        if (sw.drop && cls != 2) {
            GvwOpen o;
            o.label = label;
            o.t_ns  = r.t_ns;
            o.id    = r.id;
            std::copy(r.pkt, r.pkt + 8, o.pkt);
            o.is64      = is64;
            o.checkable = r.checkable;
            gvw_window_open(g_gvw_open, o);
        }
    }
    t_gvw_ids.push_back(r.id);
    if (sw.gu_journal)
        gvw_put(gvw_line_giveup(r.id, label, cls, kind, num_dwords, where, at, waited_ms, r.t_s, r.flip, code, ring, seen, wr.kind, wr.dwords, wr.game, gvw_ms(r.t_ns, wr.t_ns)));
}
// submit_split's start: with the give-up journal on, the buffer's label writes go to the writer registry, and the give-ups
// whose writer was not seen yet are looked at: this buffer writes it, a job on a ring writes it, the label met, or 2 s.
static void gvw_split_start(const uint32_t* ib, uint32_t num_dwords, const char* kind) {
    t_gvw_ids.clear();
    if (!gvw_switches().gu_journal || ib == nullptr) return;
    struct W {
        uint64_t a = 0, v = 0;
        int      k = 0;
    };
    std::vector<W> ws;
    for (uint32_t q = 0; q < num_dwords;) {
        const uint32_t len = gvw_len(ib[q]);
        if (q + len > num_dwords) break;
        W x;
        x.k = gvw_write_of(ib + q, len, &x.a, &x.v);
        if (x.k != 0) ws.push_back(x);
        q += len;
    }
    const uint64_t           now  = SoftCp::now_ns();
    const bool               game = on_game_thread();
    std::vector<std::string> lines;
    {
        std::lock_guard lk(g_gvw_mu);
        if (g_gvw_writers.size() > 16384) g_gvw_writers.clear();
        for (const W& x: ws) {
            GvwWriter& e = g_gvw_writers[x.a];
            e.t_ns       = now;
            std::snprintf(e.kind, sizeof(e.kind), "%s", kind);
            e.dwords = num_dwords;
            e.game   = game;
        }
        for (GvwRecord& r: g_gvw_recs) {
            if (r.arrived != 0) continue;
            int how = 0, ring = -1;
            for (const W& x: ws) how = how != 0 || (x.a == r.label && (x.k == 3 || !r.checkable || gvw_meets(r.pkt, r.is64, x.v))) ? 1 : 0;
            if (how == 0 && r.checkable && wait_satisfied(r.pkt, r.is64)) how = 3;
            if (how == 0) {
                ring = gvw_pending_ring(r.label);
                if (ring >= 0) how = 2;
            }
            if (how == 0 && now >= r.t_ns && now - r.t_ns >= kGvwArriveNs) how = 4;
            if (how == 0) continue;
            r.arrived = how;
            lines.push_back(gvw_line_arrival(r.id, r.label, how, gvw_ms(now, r.t_ns), g_gvw_flip_n - r.flip, kind, num_dwords, game, ring));
        }
    }
    for (const std::string& l: lines) gvw_put(l);
}
// Switch 2 in submit_now, after fl_plan_buffer: the windows stepped; while one is open the dcb's certainly fast-launch
// draws are dropped. The lines go out with the submission's number (gvw_submitted).
struct GvwDropNote {
    uint32_t                 dropped = 0, draws = 0, kept = 0;
    std::string              open;
    std::vector<std::string> closed;
};
static GvwDropNote gvw_fl_drop(FlPlan& plan, const char* kind, std::vector<uint32_t>& drop_offsets) {
    GvwDropNote note;
    if (!gvw_switches().drop || std::strncmp(kind, "dcb", 3) != 0) return note;
    const uint64_t  now = SoftCp::now_ns();
    std::lock_guard lk(g_gvw_mu);
    if (g_gvw_open.empty()) return note;
    std::vector<std::pair<GvwOpen, int>> closed;
    gvw_window_step(g_gvw_open, now, [](const uint32_t* x, bool x64) { return wait_satisfied(x, x64); }, closed);
    for (const auto& c: closed) note.closed.push_back(gvw_line_closed(c.first, c.second, gvw_ms(now, c.first.t_ns)));
    if (g_gvw_open.empty()) return note;
    note.draws   = plan.total;
    note.dropped = gvw_fl_take(plan, drop_offsets);
    note.kept    = plan.maybe + plan.unknown;
    for (GvwOpen& o: g_gvw_open) {
        if (note.dropped != 0) {
            o.dcbs++;
            o.draws += note.dropped;
        }
        note.open += gvw_fmt("%s0x%" PRIx64 " (give-up #%" PRIu64 ", %.1f ms)", note.open.empty() ? "" : ", ", o.label, o.id, gvw_ms(now, o.t_ns));
    }
    return note;
}
// submit_now, once the submission's number is known: switch 2's lines; switch 3: the give-ups this submission carries (no
// chain: this thread's; a chain: by the segments given up); switch 4: a dcb after a give-up in its frame is marked.
static void gvw_submitted(uint64_t n, const char* kind, const Chain* chain, const GvwDropNote& note, const FlPlan& plan) {
    const GvwSwitches& sw = gvw_switches();
    if (!sw.any()) return;
    std::vector<std::string> lines(note.closed);
    if (note.dropped != 0) lines.push_back(gvw_line_drop(n, kind, note.dropped, note.draws, note.kept, note.open));
    if (sw.gu_journal || sw.sample) {
        const uint64_t  now = SoftCp::now_ns();
        const bool      acb = std::strncmp(kind, "acb", 3) == 0;
        std::lock_guard lk(g_gvw_mu);
        for (GvwRecord& r: g_gvw_recs) {
            if (!sw.gu_journal || r.submit != ~0ull || (std::strncmp(r.kind, "acb", 3) == 0) != acb) continue;
            bool here = false;
            if (chain == nullptr) {
                here = std::find(t_gvw_ids.begin(), t_gvw_ids.end(), r.id) != t_gvw_ids.end();
            } else {
                for (const ChainSeg& s: chain->segs) here = here || (s.given_up && s.src != nullptr && gvw_within(r.wait, s.src, s.n));
            }
            if (!here) continue;
            r.submit = n;
            lines.push_back(gvw_line_carried(r.id, r.label, n, kind, gvw_ms(now, r.t_ns)));
        }
        if (sw.sample && plan.crumbs && std::strcmp(kind, "dcb") == 0) {
            const std::vector<uint64_t> flips(g_gvw_flips.begin(), g_gvw_flips.end());
            std::string                 why;
            for (auto it = g_gvw_recs.rbegin(); it != g_gvw_recs.rend() && why.size() < 300; ++it) {
                if (it->cls == 2 || !gvw_in_frame(flips, it->t_ns, now)) continue;
                why += gvw_fmt("%sgive-up #%" PRIu64 " on 0x%" PRIx64 " (%.1f ms before its submission)", why.empty() ? "after " : ", ", it->id, it->label, gvw_ms(now, it->t_ns));
            }
            if (!why.empty()) {
                g_gvw_marks[n] = why;
                while (g_gvw_marks.size() > 4096) g_gvw_marks.erase(g_gvw_marks.begin());
            }
        }
    }
    for (const std::string& l: lines) gvw_put(l);
}
// Switch 4 at a job's completion: true (and why) when n is marked and the rate allows a walk now; the mark goes either way.
static bool gvw_sample_take(uint64_t n, int64_t now_ms, bool walkable, std::string& why) {
    std::lock_guard lk(g_gvw_mu);
    const auto      it = g_gvw_marks.find(n);
    if (it == g_gvw_marks.end()) return false;
    why = it->second;
    g_gvw_marks.erase(it);
    if (!walkable) return false;
    if (!gvw_rate(now_ms, g_gvw_rate_sec, g_gvw_rate_used)) {
        g_gvw_refused++;
        return false;
    }
    return true;
}
// smp's walk (smp_text, both range models) on the plan's pattern draws, at most kSmpDraws, under gvw's tag; then a summary.
template <class Read>
static std::vector<std::string> gvw_sample_lines(const FlPlan& plan, uint64_t n, const char* kind, const std::string& why, const Read& read) {
    std::vector<std::string> out;
    uint32_t                 pattern = 0, walked = 0;
    for (const FlDraw& d: plan.draws) pattern += d.es_lo.n == 1 && flx_pattern(d.es_lo.v[0]) != 0 ? 1u : 0u;
    for (const FlDraw& d: plan.draws) {
        if (walked >= kSmpDraws) break;
        if (d.es_lo.n != 1 || flx_pattern(d.es_lo.v[0]) == 0) continue;
        std::string line;
        if (smp_text(d, read, "unwaited, completed", n, kind, line) != 0) out.push_back(gvw_retag(line));
        walked++;
    }
    out.push_back(gvw_line_sample_end(n, kind, pattern, plan.draws.size(), walked, why));
    return out;
}
static void gvw_sample(const FlPlan& plan, uint64_t n, const char* kind, bool same_device) { // after smp_sample, at a job's completion
    if (!gvw_switches().sample) return;
    const int64_t now_ms = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now().time_since_epoch()).count();
    std::string   why;
    if (!gvw_sample_take(n, now_ms, plan.crumbs && same_device && g_dev != nullptr, why)) return;
    const auto maps_p = g_dev->sorted_mappings();
    const auto reader = [&maps_p](uint64_t a, uint64_t bytes) -> const uint32_t* {
        return covered_sorted(*maps_p, a, bytes) ? reinterpret_cast<const uint32_t*>(a) : nullptr;
    };
    for (const std::string& l: gvw_sample_lines(plan, n, kind, why, reader)) gvw_put(l);
}
// At a fence timeout (before timeout_probe): the give-up journal's line; switch 4's mark of the job goes.
static void gvw_at_timeout(uint64_t n, const char* kind, uint64_t submit_ns) {
    const GvwSwitches& sw = gvw_switches();
    if (!sw.gu_journal && !sw.sample) return;
    std::string line;
    {
        std::lock_guard lk(g_gvw_mu);
        g_gvw_marks.erase(n);
        if (sw.gu_journal) {
            std::vector<GvwGu> gus;
            for (const GvwRecord& r: g_gvw_recs) gus.push_back(GvwGu {r.id, r.label, r.t_ns, r.cls});
            line = gvw_line_timeout(n, kind, submit_ns, gus, std::vector<uint64_t>(g_gvw_flips.begin(), g_gvw_flips.end()), nullptr);
        }
    }
    if (!line.empty()) gvw_put(line);
}
// ---- end of exp 0401 series e9's (tag gvw) host block ------------------------------------------------------------------
""")

# ---- 7. submit_now: the drop after the plan, the note after the number ------------------------------------------------
A_OLD = b"\tfl_plan_buffer(ib, num_dwords, kind, qring, chain, *maps_p, opt.drop_offsets, fl_plan);\n"
A_NEW = A_OLD + (b"\tconst GvwDropNote gvw_drop = gvw_fl_drop(fl_plan, kind, opt.drop_offsets); // exp 0401 e9 (gvw): BC5_DIRECT_UNWAITED_FL_DROP,"
                 b" through exp 0404's plan and the filter's drop list\n")
B_OLD = (b"\tconst uint64_t n = g_submits.fetch_add(1);\n"
         b"\t// Crash journal: a hang takes the machine down before any buffered log reaches the disk, so\n")
B_NEW = (b"\tconst uint64_t n = g_submits.fetch_add(1);\n"
         b"\tgvw_submitted(n, kind, chain, gvw_drop, fl_plan); // exp 0401 e9 (gvw): the drop's lines, the give-ups it carries, switch 4's mark\n"
         b"\t// Crash journal: a hang takes the machine down before any buffered log reaches the disk, so\n")

# ---- 8. the seams, after smp's ----------------------------------------------------------------------------------------
SEAMS_ANCHOR = b"// ---- end of exp 0401 series e8's (tag smp) seams ----------------------------------------------------------------------\n"
GVW_SEAMS = tabs(r"""// ---- exp 0401 series e9 (tag gvw): the CPU test's seams (gvw0401.cpp); always compiled in, never called by the emulator ----
extern "C" int bc5_gvw0401_parse_ms(const char* e, int* bad) {
    bool      b = false;
    const int v = gvw_parse_ms(e, &b);
    *bad        = b ? 1 : 0;
    return v;
}
extern "C" int bc5_gvw0401_parse_on(const char* e, int* bad) {
    bool      b = false;
    const int v = gvw_parse_on(e, &b);
    *bad        = b ? 1 : 0;
    return v;
}
extern "C" void bc5_gvw0401_switches(int* out) { // the unit's reading: late ms, drop, give-up journal, unwaited sample
    const GvwSwitches& s = gvw_switches();
    out[0]               = s.late_ms;
    out[1]               = s.drop ? 1 : 0;
    out[2]               = s.gu_journal ? 1 : 0;
    out[3]               = s.sample ? 1 : 0;
}
extern "C" void bc5_gvw0401_consts(uint64_t* out) {
    const uint64_t v[7] = {static_cast<uint64_t>(kGvwLateMaxMs), kGvwWindowNs, kGvwArriveNs, kGvwSampleJobs, kGvwScanEntries, kGvwScanDwords, kSmpDraws};
    for (uint32_t k = 0; k < 7; k++) out[k] = v[k];
}
extern "C" int bc5_gvw0401_meets(const uint32_t* w, int is64, uint64_t value) {
    return gvw_meets(w, is64 != 0, value) ? 1 : 0;
}
extern "C" int bc5_gvw0401_decide(int bound_ms, int can_wait, int cycle, int pending, int writer, int capped) {
    GvwScan s;
    s.writer = writer;
    s.capped = capped != 0;
    return gvw_late_decide(bound_ms, can_wait != 0, cycle != 0, pending != 0, s);
}
extern "C" int bc5_gvw0401_waits(int code) {
    return gvw_late_waits(code) ? 1 : 0;
}
extern "C" const char* bc5_gvw0401_suffix(int code) {
    return gvw_bound_suffix(code);
}
// gvw_scan on queues of the test's own: rings[k] (ns[k] dwords, read pointer rs[k], write pointer ws[k]); read: the test's
// memory; a wait whose label is in met[] counts as served; a label in ours[] as written by the waiting buffer. out[6]:
// capped, queue, block, entries, ibs, dwords. Returns the writer.
extern "C" int bc5_gvw0401_scan(const uint32_t* const* rings, const uint32_t* ns, const uint32_t* rs, const uint32_t* ws, uint32_t nq, const uint32_t* w, int is64, FlxReadFn read, void* ctx,
                                const uint64_t* met, uint32_t nmet, const uint64_t* ours, uint32_t nours, uint64_t* out) {
    std::vector<GvwQueue> qs(nq);
    for (uint32_t k = 0; k < nq; k++) {
        qs[k].ring = rings[k];
        qs[k].n    = ns[k];
        qs[k].r    = rs[k];
        qs[k].w    = ws[k];
    }
    const auto    reader = [read, ctx](uint64_t a, uint64_t bytes) { return read(a, bytes, ctx); };
    const auto    m      = [met, nmet](const uint32_t* x, bool) { return std::find(met, met + nmet, gvw_addr(x[2], x[3])) != met + nmet; };
    const auto    o      = [ours, nours](uint64_t a) { return std::find(ours, ours + nours, a) != ours + nours; };
    const GvwScan s      = gvw_scan(qs, w, is64 != 0, gvw_addr(w[2], w[3]), reader, m, o);
    const uint64_t v[6]  = {s.capped ? 1u : 0u, static_cast<uint64_t>(static_cast<int64_t>(s.queue)), s.block, s.entries, s.ibs, s.dwords};
    for (uint32_t k = 0; k < 6; k++) out[k] = v[k];
    return s.writer;
}
// Exp 0055's registry and the guest queues, real: entries of the test's own (clear: emptied first, and the takes forgotten).
extern "C" void bc5_gvw0401_plw(uint64_t label, uint64_t value, int is64, int ring, int clear) {
    static uint64_t order = 1ull << 40u;
    std::lock_guard lk(g_plw_mutex);
    if (clear != 0) {
        g_plw.clear();
        return;
    }
    PendingLabelWrite x {label, value, 0, is64 != 0};
    x.ring  = ring;
    x.order = ++order;
    g_plw.push_back(x);
}
extern "C" void bc5_gvw0401_queue(uint64_t ring_base, uint64_t ring_end, uint64_t doorbell_page, uint32_t d, int clear) {
    std::lock_guard lock(g_mutex);
    if (clear != 0) {
        g_queues.clear();
        for (auto& t: g_gvw_taken) t.store(0);
        return;
    }
    QueueReg q {};
    q.a             = 2;
    q.d             = d;
    q.ring_base     = ring_base;
    q.ring_end      = ring_end;
    q.doorbell_page = doorbell_page;
    g_queues.push_back(q);
}
extern "C" void bc5_gvw0401_taken(uint32_t queue, uint32_t rptr) { // as the doorbell consumer's line after its take
    if (queue < 64) g_gvw_taken[queue].store(1ull + rptr, std::memory_order_relaxed);
}
// The real gvw_late_code (the real registries, queues and decision) with the test's reader. out[5]: pending, writer, capped,
// entries, ibs.
extern "C" int bc5_gvw0401_late_code(const uint32_t* w, int is64, const uint32_t* rest, uint32_t rest_n, int can_wait, int cycle, int bound_ms, FlxReadFn read, void* ctx, uint64_t* out) {
    const auto reader  = [read, ctx](uint64_t a, uint64_t bytes) { return read(a, bytes, ctx); };
    GvwScan    s;
    bool       pending = false;
    const int  c       = gvw_late_code(w, is64 != 0, gvw_addr(w[2], w[3]), rest, rest_n, can_wait != 0, cycle != 0, bound_ms, reader, s, pending);
    const uint64_t v[5] = {pending ? 1u : 0u, static_cast<uint64_t>(s.writer), s.capped ? 1u : 0u, s.entries, s.ibs};
    for (uint32_t k = 0; k < 5; k++) out[k] = v[k];
    return c;
}
// The real hook (submit_split's call, with the unit's switch and the host's reader; t0 now). Returns met; *ms the time in it.
extern "C" int bc5_gvw0401_late(const uint32_t* w, int is64, const uint32_t* rest, uint32_t rest_n, int cycle, int* code, double* ms) {
    const uint64_t t0 = SoftCp::now_ns();
    const bool     ok = gvw_late(w, is64 != 0, gvw_addr(w[2], w[3]), "dcb", rest_n, 0, rest, rest_n, t0, cycle != 0, code);
    *ms               = gvw_ms(SoftCp::now_ns(), t0);
    return ok ? 1 : 0;
}
// gvw_window_open and gvw_window_step at now on windows of the test's own (labels[k], opened at t_open[k], id k + 1); a
// window's label in met[] meets it. why[k]: 0 open, 1 closed met, 2 closed at the bound, -1 replaced by a later give-up on
// its label. Returns the windows still open.
extern "C" uint32_t bc5_gvw0401_window(const uint64_t* labels, const uint64_t* t_open, const int* checkable, uint32_t n, uint64_t now, const uint64_t* met, uint32_t nmet, int* why) {
    std::vector<GvwOpen> open;
    for (uint32_t k = 0; k < n; k++) {
        GvwOpen o;
        o.label     = labels[k];
        o.t_ns      = t_open[k];
        o.id        = k + 1;
        o.checkable = checkable[k] != 0;
        o.pkt[2]    = static_cast<uint32_t>(labels[k]);
        o.pkt[3]    = static_cast<uint32_t>(labels[k] >> 32u);
        gvw_window_open(open, o);
    }
    std::vector<std::pair<GvwOpen, int>> closed;
    gvw_window_step(open, now, [met, nmet](const uint32_t* x, bool) { return std::find(met, met + nmet, gvw_addr(x[2], x[3])) != met + nmet; }, closed);
    for (uint32_t k = 0; k < n; k++) {
        why[k] = -1;
        for (const GvwOpen& o: open) why[k] = o.id == k + 1 ? 0 : why[k];
        for (const auto& c: closed) why[k] = c.first.id == k + 1 ? c.second : why[k];
    }
    return static_cast<uint32_t>(open.size());
}
// A plan of the test's own: draw k of class cls[k] at at[k] (drop: the ES skip's, crumbs, serial: F2), counted as fl_scan counts.
static FlPlan gvw_seam_plan(const uint32_t* cls, const uint32_t* at, const int* drop, const int* crumbs, const int* serial, uint32_t count) {
    FlPlan plan;
    for (uint32_t k = 0; k < count; k++) {
        FlDraw d;
        d.cls    = cls[k];
        d.at     = at[k];
        d.drop   = drop != nullptr && drop[k] != 0;
        d.crumbs = crumbs != nullptr && crumbs[k] != 0;
        d.serial = serial != nullptr && serial[k] != 0;
        plan.total++;
        (d.cls == 3 ? plan.fl : d.cls == 2 ? plan.maybe : plan.unknown)++;
        plan.planned += d.crumbs ? 1u : 0u;
        plan.skipped += d.drop ? 1u : 0u;
        plan.inserts = plan.inserts || d.serial;
        plan.draws.push_back(d);
    }
    plan.crumbs = true;
    return plan;
}
// gvw_fl_take on such a plan, with one drop (offset 7) already in the list. out: draws left, host_dropped, fl, planned,
// inserts, drops in the list, then the drops' offsets after the first (at most 8).
extern "C" uint32_t bc5_gvw0401_fl_take(const uint32_t* cls, const uint32_t* at, const int* drop, const int* crumbs, const int* serial, uint32_t count, uint32_t* out) {
    FlPlan                plan  = gvw_seam_plan(cls, at, drop, crumbs, serial, count);
    std::vector<uint32_t> drops = {7};
    const uint32_t        k     = gvw_fl_take(plan, drops);
    out[0]                      = static_cast<uint32_t>(plan.draws.size());
    out[1]                      = plan.host_dropped;
    out[2]                      = plan.fl;
    out[3]                      = plan.planned;
    out[4]                      = plan.inserts ? 1u : 0u;
    out[5]                      = static_cast<uint32_t>(drops.size());
    for (std::size_t i = 1; i < drops.size() && i <= 8; i++) out[5 + i] = drops[i];
    return k;
}
static GvwDropNote g_gvw_seam_note; // the last bc5_gvw0401_fl_drop's note, for bc5_gvw0401_submitted
// The real gvw_fl_drop on a plan of the test's own (no crumbs, no ES skip). *left: the draws left in the plan.
extern "C" uint32_t bc5_gvw0401_fl_drop(const char* kind, const uint32_t* cls, const uint32_t* at, uint32_t count, uint32_t* left) {
    FlPlan                plan = gvw_seam_plan(cls, at, nullptr, nullptr, nullptr, count);
    std::vector<uint32_t> drops;
    g_gvw_seam_note = gvw_fl_drop(plan, kind, drops);
    *left           = static_cast<uint32_t>(plan.draws.size());
    return static_cast<uint32_t>(drops.size()) == g_gvw_seam_note.dropped ? g_gvw_seam_note.dropped : 0xffffffffu;
}
// The real gvw_submitted (no chain: this thread's give-ups) with the last fl_drop's note; returns whether n is marked.
extern "C" int bc5_gvw0401_submitted(uint64_t n, const char* kind, int crumbs) {
    FlPlan plan;
    plan.crumbs = crumbs != 0;
    gvw_submitted(n, kind, nullptr, g_gvw_seam_note, plan);
    g_gvw_seam_note = GvwDropNote {};
    std::lock_guard lk(g_gvw_mu);
    return g_gvw_marks.count(n) != 0 ? 1 : 0;
}
// The real gvw_given_up (as submit_split calls it: the wait is its own place); returns the give-ups kept.
extern "C" uint64_t bc5_gvw0401_given_up(const uint32_t* w, uint32_t len, int is64, const char* kind, int cls) {
    gvw_given_up(w, len, w, is64 != 0, gvw_addr(w[2], w[3]), kind, 100, 3, 8.5, -1, cls);
    std::lock_guard lk(g_gvw_mu);
    return g_gvw_recs.size();
}
extern "C" uint32_t bc5_gvw0401_open() {
    std::lock_guard lk(g_gvw_mu);
    return static_cast<uint32_t>(g_gvw_open.size());
}
extern "C" void bc5_gvw0401_split_start(const uint32_t* ib, uint32_t n, const char* kind) {
    gvw_split_start(ib, n, kind);
}
extern "C" void bc5_gvw0401_flip() {
    gvw_flip();
}
extern "C" uint64_t bc5_gvw0401_now() {
    return SoftCp::now_ns();
}
extern "C" void bc5_gvw0401_at_timeout(uint64_t n, const char* kind, uint64_t submit_ns) {
    gvw_at_timeout(n, kind, submit_ns);
}
extern "C" void bc5_gvw0401_reset() { // a case starts afresh: no give-ups (numbered from 1 again), windows, flips, writers, marks, lines
    {
        std::lock_guard lk(g_gvw_mu);
        g_gvw_ids    = 0;
        g_gvw_flip_n = 0;
        g_gvw_recs.clear();
        g_gvw_open.clear();
        g_gvw_flips.clear();
        g_gvw_writers.clear();
        g_gvw_marks.clear();
        g_gvw_rate_sec  = -1;
        g_gvw_rate_used = 0;
    }
    t_gvw_ids.clear();
    std::lock_guard lk(g_gvw_last_mu);
    g_gvw_last.clear();
}
extern "C" uint32_t bc5_gvw0401_last(char* out, uint32_t cap) { // the lines written since the last reset, one per line
    std::lock_guard lk(g_gvw_last_mu);
    std::string     all;
    for (const std::string& l: g_gvw_last) all += l + "\n";
    std::snprintf(out, cap, "%s", all.c_str());
    return static_cast<uint32_t>(g_gvw_last.size());
}
extern "C" int bc5_gvw0401_flips_between(const uint64_t* f, uint32_t n, uint64_t g, uint64_t s) {
    return gvw_flips_between(std::vector<uint64_t>(f, f + n), g, s);
}
extern "C" int bc5_gvw0401_in_frame(const uint64_t* f, uint32_t n, uint64_t g, uint64_t s) {
    return gvw_in_frame(std::vector<uint64_t>(f, f + n), g, s) ? 1 : 0;
}
extern "C" int bc5_gvw0401_timeout_line(uint64_t n, uint64_t s, const uint64_t* labels, const uint64_t* ts, const int* cls, uint32_t count, const uint64_t* flips, uint32_t nflips, char* out,
                                        uint32_t cap) {
    std::vector<GvwGu> gus;
    for (uint32_t k = 0; k < count; k++) gus.push_back(GvwGu {k + 1, labels[k], ts[k], cls[k]});
    bool frame = false;
    std::snprintf(out, cap, "%s", gvw_line_timeout(n, "dcb", s, gus, std::vector<uint64_t>(flips, flips + nflips), &frame).c_str());
    return frame ? 1 : 0;
}
extern "C" int bc5_gvw0401_rate(int64_t now_ms, int64_t* sec, uint32_t* used) {
    return gvw_rate(now_ms, *sec, *used) ? 1 : 0;
}
// gvw_sample's two steps on a plan of the test's own: n's mark taken (walkable: the crumbs and the same device), then the
// lines of its ndraws draws (ES es[k], the user data x, op 24 at 100 + k, the arguments at args) read through the test's
// memory. Returns the lines (one per line in out), -1 when not taken.
extern "C" int bc5_gvw0401_sample(uint64_t n, int walkable, int64_t now_ms, const uint32_t* ns, const uint32_t* v0, const uint32_t* v1, uint32_t count, const uint32_t* es, uint32_t ndraws,
                                  uint64_t args, FlxReadFn read, void* ctx, char* out, uint32_t cap) {
    out[0] = 0;
    std::string why;
    if (!gvw_sample_take(n, now_ms, walkable != 0, why)) return -1;
    FlPlan plan;
    plan.crumbs = true;
    for (uint32_t k = 0; k < ndraws; k++) {
        FlDraw d;
        d.x          = flx_seam_vals(ns, v0, v1, count);
        d.es_lo.n    = 1;
        d.es_lo.v[0] = es[k];
        d.op         = 0x24;
        d.at         = 100 + k;
        d.args       = args;
        plan.draws.push_back(d);
    }
    const auto                     reader = [read, ctx](uint64_t a, uint64_t bytes) { return read(a, bytes, ctx); };
    const std::vector<std::string> lines  = gvw_sample_lines(plan, n, "dcb", why, reader);
    std::string                    all;
    for (const std::string& l: lines) all += l + "\n";
    std::snprintf(out, cap, "%s", all.c_str());
    return static_cast<int>(lines.size());
}
extern "C" uint64_t bc5_gvw0401_refused() {
    std::lock_guard lk(g_gvw_mu);
    return g_gvw_refused;
}
// One line of each kind the pure part formats, with sample values, one per line (the quiet filter's test reads them).
extern "C" uint32_t bc5_gvw0401_texts(char* out, uint32_t cap) {
    GvwScan s;
    s.scanned = true;
    s.entries = 3;
    s.ibs     = 2;
    s.dwords  = 11130;
    s.writer  = 2;
    s.queue   = 1;
    s.block   = 0x12004b4fc8ull;
    GvwOpen o;
    o.label = 0x12004b4438ull;
    o.id    = 4;
    const std::vector<GvwGu>       gus   = {GvwGu {4, 0x12004b4438ull, 1'000'000'000ull, 0}};
    const std::vector<uint64_t>    flips = {900'000'000ull};
    const std::vector<std::string> l     = {gvw_switch_line(500, false, true, false, false, true, false, true, false, false),
                                            gvw_switch_line(0, true, false, true, false, false, true, false, true, false),
                                            gvw_line_decision(0x12004b4438ull, "dcb", 2940, 120, 8.2, 6, s, false, true, 37.5),
                                            gvw_line_decision(0x12004b4438ull, "dcb", 2940, 120, 8.2, 3, GvwScan {}, false, false, 8.3),
                                            gvw_line_served(true, 120, 0x12004b4438ull, 37.5, 6),
                                            gvw_line_giveup(4, 0x12004b4438ull, 0, "dcb", 2940, nullptr, 120, 16.0, 427.274, 812, 3, -1, true, "acb", 11130, false, 33.3),
                                            gvw_line_arrival(4, 0x12004b4438ull, 1, 354.0, 0, "acb", 11130, false, -1),
                                            gvw_line_arrival(4, 0x12004b4438ull, 2, 12.0, 1, "dcb", 0, true, 1),
                                            gvw_line_arrival(4, 0x12004b4438ull, 3, 2.0, 0, "dcb", 0, true, -1),
                                            gvw_line_arrival(4, 0x12004b4438ull, 4, 2000.0, 60, "dcb", 0, true, -1),
                                            gvw_line_carried(4, 0x12004b4438ull, 412352, "dcb", 0.4),
                                            gvw_line_drop(412353, "dcb", 3, 37, 1, "0x12004b4438 (give-up #4, 10.0 ms)"),
                                            gvw_line_closed(o, 1, 354.0),
                                            gvw_line_closed(o, 2, 1000.0),
                                            gvw_line_timeout(412352, "dcb", 1'010'000'000ull, gus, flips, nullptr),
                                            gvw_line_sample_end(412353, "dcb", 2, 3, 2, "after give-up #4 on 0x12004b4438 (12.0 ms before its submission)"),
                                            gvw_retag("fl meshlet sample (exp 0401 e8 smp): unwaited, completed: submit #1 dcb op 24 at 100: ES 11d01345 (pattern 1): 6 x 1 points"),
                                            std::string("cpu-wait WAIT_REG_MEM64 at 120 on 0x12004b4438: GIVEN UP after 500.0 ms") + gvw_bound_suffix(6)};
    std::string                    all;
    for (const std::string& x: l) all += x + "\n";
    std::snprintf(out, cap, "%s", all.c_str());
    return static_cast<uint32_t>(l.size());
}
// ---- end of exp 0401 series e9's (tag gvw) seams ----------------------------------------------------------------------
""")

# ---- 9. after smp's two smp_sample lines; before the two timeout_probe timeout lines ------------------------------------
L_SYNC_OLD = (b"\tif (!r.timed_out && r.ok && !r.pending && fl_plan.crumbs) smp_sample(fl_plan, n, kind, true);"
              b" // exp 0401 e8 (smp): the draws of a completed job, at most every N s\n")
L_SYNC_NEW = L_SYNC_OLD + (b"\tif (!r.timed_out && r.ok && !r.pending && fl_plan.crumbs) gvw_sample(fl_plan, n, kind, true);"
                           b" // exp 0401 e9 (gvw): the draws of a completed dcb after a give-up in its frame\n")
L_CQ_OLD = (b"\t\t\tif (!r.timed_out && r.ok && j.fl_plan.crumbs) smp_sample(j.fl_plan, j.n, j.kind, g_dev && j.dev_gen == g_dev_gen.load());"
            b" // exp 0401 e8 (smp): the draws of a completed job, at most every N s\n")
L_CQ_NEW = L_CQ_OLD + (b"\t\t\tif (!r.timed_out && r.ok && j.fl_plan.crumbs) gvw_sample(j.fl_plan, j.n, j.kind, g_dev && j.dev_gen == g_dev_gen.load());"
                       b" // exp 0401 e9 (gvw): the draws of a completed dcb after a give-up in its frame\n")
TO_SYNC_OLD = b"\n\tif (r.timed_out) timeout_probe(fl_ib.empty() ? sub_ib : ib,"
TO_SYNC_NEW = (b"\n\tif (r.timed_out) gvw_at_timeout(n, kind, t0); // exp 0401 e9 (gvw): did the stuck job follow a give-up in its frame\n"
               b"\tif (r.timed_out) timeout_probe(fl_ib.empty() ? sub_ib : ib,")
TO_CQ_OLD = b"\n\t\t\tif (r.timed_out && !j.ib_copy.empty()) timeout_probe(j.ib_copy.data(),"
TO_CQ_NEW = (b"\n\t\t\tif (r.timed_out) gvw_at_timeout(j.n, j.kind, j.queued_ns); // exp 0401 e9 (gvw): did the stuck job follow a give-up in its frame\n"
             b"\t\t\tif (r.timed_out && !j.ib_copy.empty()) timeout_probe(j.ib_copy.data(),")

# ---- 10. the flip ------------------------------------------------------------------------------------------------------
FLIP_OLD = b"\tBc5Gc::Direct::frame_profile_flip((Bc5Gc::Direct::timing_now() - t_drain) * 1e3);\n"
FLIP_NEW = FLIP_OLD + b"\tBc5Gc::Direct::gvw_flip(); // exp 0401 e9 (gvw): a frame boundary for the give-up journal and the unwaited sample\n"
STUB_OLD = b"static void frame_profile_flip(double) {}\n"
STUB_NEW = STUB_OLD + b"static void gvw_flip() {} // exp 0401 e9 (gvw)\n"

# (name, anchor, new text for the anchor), applied in this order; each anchor exactly once in the unit when applied
EDITS = [
    ("g_gvw_taken", QUEUES_OLD, QUEUES_NEW),
    ("the doorbell consumer's take", TAKE_OLD, TAKE_NEW),
    ("the forward declarations", TWG_OLD, TWG_NEW),
    ("the hold tail's give-up", HOLD_OLD, HOLD_NEW),
    ("submit_split's start", SS_OLD, SS_NEW),
    ("the late-producer wait", LATE_OLD, LATE_NEW),
    ("the cpu-wait line's suffix", GU_OLD, GU_NEW),
    ("the give-up record", REC_OLD, REC_NEW),
    ("the pure block", PURE_ANCHOR, PURE_ANCHOR + GVW_PURE),
    ("the host block", HOST_ANCHOR, HOST_ANCHOR + GVW_HOST),
    ("submit_now: the drop", A_OLD, A_NEW),
    ("submit_now: the submission", B_OLD, B_NEW),
    ("the seams", SEAMS_ANCHOR, SEAMS_ANCHOR + GVW_SEAMS),
    ("submit_now: after smp_sample", L_SYNC_OLD, L_SYNC_NEW),
    ("completion_thread: after smp_sample", L_CQ_OLD, L_CQ_NEW),
    ("submit_now: before timeout_probe", TO_SYNC_OLD, TO_SYNC_NEW),
    ("completion_thread: before timeout_probe", TO_CQ_OLD, TO_CQ_NEW),
    ("SubmitEopFlip: the flip", FLIP_OLD, FLIP_NEW),
    ("the non-direct stubs: gvw_flip", STUB_OLD, STUB_NEW),
]


def strip_code(b):
    """The text with comments and string/char literals removed (for the balance counts). A digit separator (1'000) is
    not a char literal."""
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
        elif c == b"'" and i > 0 and b[i - 1:i].isalnum() and b[i + 1:i + 2].isalnum():
            i += 1  # a digit separator
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
    # Where the blocks landed: g_gvw_taken before the doorbell consumer; the declarations after t_wait_given_up and before the
    # hold tail; the pure block in exp 0404's pure part after smp's; the host block after smp's and before fl_plan_buffer;
    # the seams after smp's and before exp 0024's jobs; the hooks in submit_split, submit_now, the completion thread and
    # SubmitEopFlip; the stub in the non-direct branch.
    order = [out.index(x) for x in (b"static std::atomic<uint64_t> g_gvw_taken[64];", b"static void queue_consumer_thread() {", b"g_gvw_taken[&s - states.data()]",
                                    b"static thread_local bool t_wait_given_up = false;", b"static int         gvw_late_ms();", b"static bool hold_release(",
                                    b"gvw_given_up(c.pkt, 8, c.p,", b"static void submit_split(", b"\tgvw_split_start(ib, num_dwords, kind);", b"int gvw_lp = -1;",
                                    b"gvw_bound_suffix(gvw_lp));", b"if (!ok) gvw_given_up(p, len, p,", b"struct FlDraw {", b"static std::string smp_counts(",
                                    PURE_ANCHOR, b"static int gvw_parse_ms(", b"// ---- end of experiment 0404's pure part", HOST_ANCHOR, b"static const GvwSwitches& gvw_switches()",
                                    b"static void gvw_at_timeout(", b"static void fl_plan_buffer(", SEAMS_ANCHOR, b"extern \"C\" int bc5_gvw0401_parse_ms(",
                                    b"// ---- experiment 0024: jobs in flight", b"static void completion_thread(int index) {", b"gvw_sample(j.fl_plan, j.n, j.kind,",
                                    b"gvw_at_timeout(j.n, j.kind, j.queued_ns);", b"static void submit_now(const uint32_t* ib, uint32_t num_dwords, const char* kind, int ring, const Chain* chain) {",
                                    b"const GvwDropNote gvw_drop =", b"gvw_submitted(n, kind, chain, gvw_drop, fl_plan);", b"gvw_sample(fl_plan, n, kind, true);",
                                    b"gvw_at_timeout(n, kind, t0);", b"static void gvw_flip() {}", b"Bc5Gc::Direct::gvw_flip();")]
    assert order == sorted(order), ("the blocks are out of order", order)
    # The calls: the declaration, the definition, the hook(s), the seam(s).
    want = {b"gvw_late(": 4, b"gvw_given_up(": 5, b"gvw_split_start(": 4, b"gvw_bound_suffix(": 5, b"gvw_late_ms()": 4, b"gvw_fl_drop(": 3,
            b"gvw_submitted(": 3, b"gvw_sample(": 3, b"gvw_at_timeout(": 4, b"gvw_flip()": 4, b"g_gvw_taken[": 4}
    got = {k: out.count(k) for k in want}
    assert got == want, ("the calls", got)
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
