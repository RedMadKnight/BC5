#!/usr/bin/env python3
"""BC5 experiment 0401, exp 0404's two switches (README section 4 "Proposed switches", Verdict Q4) in series e3's
src/libs/bc5LleAgc.cpp (unit d3b7f9b0, mkunit0401.py --acb-restore --catcher --inherit3 --memline):
  BC5_DIRECT_FL_CRUMBS=1        catcher, default off: crumbs around every draw of a dcb whose tracked
                                VGT_SHADER_STAGES_EN is (or may be) fast-launch; fl_probe prints them at a fence timeout
  BC5_DIRECT_FL_SKIP_ES=<list>  diagnostic, default off: drops the fast-launch draws whose SPI_SHADER_PGM_LO_ES is listed,
                                through FilterOptions::drop_offsets (as BC5_DIRECT_SKIP_PGM drops dispatches)
Design, sources, memory, costs and doubts: fl0401-notes.md. The pure part (state tracking, the plan, the crumbs' packets,
the probe's classification, the list parser) goes into the unit and, byte for byte, into <inc out dir>/fl_scan.inc for
the CPU test fl0401.cpp. Every anchor must occur exactly once; a unit that has the edit already is refused. Prints the
output unit's md5.
usage: mkfl0401.py <unit in> <unit out> <inc out dir>"""
import hashlib
import os
import sys

E3_MD5 = "d3b7f9b0ab43184ee11de83e9e233ff8"  # series e3's unit (exp0401e3q)
MARK = b"BC5_DIRECT_FL_CRUMBS"


def tabs(text):
    """The C++ below is written with 4-space indents; the unit indents with tabs."""
    out = []
    for line in text.split("\n"):
        body = line.lstrip(" ")
        k = len(line) - len(body)
        out.append("\t" * (k // 4) + " " * (k % 4) + body)
    return "\n".join(out).encode("ascii")


# ---------------------------------------------------------------------------------------------------------------------
# The pure part: in the unit and in fl_scan.inc.
FL_SCAN = tabs(r"""// ---- experiment 0404 (in exp 0401's unit): fast-launch draw crumbs and skip, the pure part ------------------------------
// mkfl0401.py writes this block into the unit and, byte for byte, into fl_scan.inc for the CPU test fl0401.cpp. It needs
// <algorithm>, <cstddef>, <cstdint>, <cstdio>, <utility> and <vector>. No GPU access, no global state.
//
// What fl_scan follows, per GFX-class buffer in submission order (the caller carries FlState from buffer to buffer, as
// submit_now carries base1 and the program in g_carried): VGT_SHADER_STAGES_EN (context 0x2d5: Mesa
// src/amd/registers/gfx10.json @ fe554882, vendored in tools/bc5-agc/regdb, has it at 0x28b54), SPI_SHADER_PGM_LO_ES /
// SPI_SHADER_PGM_HI_ES (SH 0xc8 / 0xc9; gfx10.json 0xb320 / 0xb324, HI's field MEM_BASE bits 7:0),
// SPI_SHADER_USER_DATA_GS_8/9, 20/21 and 24/25 (SH 0x94/0x95, 0xa0/0xa1, 0xa4/0xa5; gfx10.json SPI_SHADER_USER_DATA_GS_0 is
// 0xb230 = SH 0x8c: the user data timeout_probe prints as "gs user data", whose s[8:9], s[20:21] and s[24:25] it reads as
// V# bases, exp 0160) and the SET_BASE index-1 base. The packets that set them are the ones backend/src/full_state.cpp
// follows (ADR 0008), read as it reads them: SET_CONTEXT_REG 0x69 and SET_SH_REG 0x76 / SET_SH_REG_INDEX 0x9b (register
// offset in dword 1 bits 15:0, the values after it); LOAD_CONTEXT_REG 0x61 / LOAD_SH_REG 0x5f (address in dwords 1-2,
// then (offset, count) pairs, the values at address + 4 * offset); LOAD_CONTEXT_REG_INDEX 0x9f / LOAD_SH_REG_INDEX 0x63
// (address in dwords 1-2; DATA_FORMAT, dword 3 bit 31, set: dword 4 bits 13:0 (offset, value) pairs there, else that
// many registers from the offset in dword 3 bits 15:0); CLEAR_STATE 0x12 (cmd 0 forgets the context registers, cmd 1
// pushes them, cmd 2 pops them: the host emulates the console's stack, Device::set_state_stack); SET_BASE 0x11 index 1
// as submit_now's walk reads it (dword 1 bits 3:0 = 1, address in dwords 2-3). A table the reader refuses and an
// INDIRECT_BUFFER 0x3f / 0x33 (not followed) make what they may set unknown; no count is clamped (lesson R28). Type-0
// packets and the other SET / LOAD forms are NOP-ed by the policy (backend/policy/pm4-policy.tsv) and do not count.
//
// COND_EXEC 0x22 (5 dwords; dword 4 bits 13:0 count the dwords skipped after the packet, as the mec rebuild and
// ib_cond_past_end read it): after its range a register holds either branch's value (lesson R22: taken and skipped
// merged), so it is one of two values, or unknown past two. A range ending inside a packet ends with it; a range past the
// buffer's end ends there (ADR 0010: such a buffer goes alone).
//
// "Fast-launch": VGT_SHADER_STAGES_EN's GS_FAST_LAUNCH field (bits 20:19, gfx10.json) is not 0. Exp 0404's hang class
// has 0x482030 (field 1). TODO(verify): what the field does on gfx1013.
//
// The draws (the draw half of backend/src/policy.cpp is_draw_or_dispatch): DRAW_INDIRECT 0x24, DRAW_INDEX_INDIRECT 0x25,
// DRAW_INDEX_2 0x27, DRAW_INDIRECT_MULTI 0x2c, DRAW_INDEX_AUTO 0x2d, DRAW_INDEX_OFFSET_2 0x35, DRAW_INDEX_INDIRECT_MULTI
// 0x38. The indirect ones read their arguments at the SET_BASE index-1 base + dword 1 (submit_now's walk and the table
// catcher; the first record of the multi forms). 16 bytes are copied: VkDrawIndirectCommand, or the first 16 of the 20
// bytes of VkDrawIndexedIndirectCommand (backend/include/bc5/draw_args.hpp). The policy's operand check reads 8 bytes at
// every COPY_DATA source (backend/src/policy.cpp memory_operands), so the last 32-bit copy of a range is checked 4 bytes
// past it: the plan copies a range only when those 4 bytes are readable too, or the filter would NOP that copy unseen.
//
// The crumbs (fl_pre, fl_post); every packet is a form the host already sends on this ring:
//   WRITE_DATA  PKT3(0x37, 4) = 0xC0043700; dword 1 DST_SEL 5 (memory, bits 11:8) | WR_CONFIRM (bit 20), ENGINE_SEL 0
//               (ME); address in dwords 2/3, two data dwords (backend/src/indirect_check.cpp kWriteData, kWriteDataMem,
//               kWrConfirm, from Mesa src/amd/common/sid.h; one more data dword is one more in the count)
//   COPY_DATA   PKT3(0x40, 4) = 0xC0044000; dword 1 SRC_SEL 1 (memory, bits 3:0) | DST_SEL 5 << 8 | WR_CONFIRM, ME, 32 bits
//               (no COUNT_SEL); source in dwords 2/3, destination in dwords 4/5 (indirect_check.cpp kCopyData,
//               kCopyMemToMem: exp 0380's argument copy, which ran on this GFX ring)
//   RELEASE_MEM PKT3(0x49, 6) = 0xC0064900; dword 1 event 0x28 BOTTOM_OF_PIPE_TS, EVENT_INDEX 5 (bits 11:8), no cache
//               action; dword 2 DATA_SEL 2 (bits 31:29: the 64-bit value of dwords 5/6), DST_SEL 0, INT_SEL 0; address in
//               dwords 3/4; dword 7 0 (backend/src/direct.cpp's job timestamp, which has DATA_SEL 3; the fields as
//               policy.cpp's memory_operands and timeout_probe read them; DATA_SEL 2 "send 64-bit data" is Mesa sid.h's
//               EOP_DATA_SEL, TODO(verify) its wording at fe554882, which is not on the laptop)
// Per draw with crumbs, in this order: head (WRITE_DATA entry + 0 = id), the copies (COPY_DATA: 4 argument dwords to
// entry + 8, 8 dwords at each copied V# base b to entry + 24 + 32 b), tail (WRITE_DATA entry + 120 = id), issued
// (WRITE_DATA = id), the title's draw (the backend's own check of it, when on, lands between the crumbs and the draw),
// then done (RELEASE_MEM = id). id = (the draw's dword offset in the buffer submit_now got << 32) | the low 32 bits of the
// submission's number. A ring entry is 128 bytes: head, 4 argument dwords, 3 x 8 V# dwords, tail.
//
// fl_build lays the crumbs into a copy and grows the buffer's own COND_EXEC counts by the crumbs inside their ranges (a
// draw's crumbs belong to it and are skipped with it), as submit_now's mec rebuild and indirect_check::insert_before do;
// a range whose count would no longer fit its 14 bits keeps its draws without crumbs (counted), and the copy is laid
// again.
constexpr uint32_t kFlStages       = 0x2d5u;                         // context: VGT_SHADER_STAGES_EN
constexpr uint32_t kFlEsLo         = 0xc8u;                          // SH: SPI_SHADER_PGM_LO_ES
constexpr uint32_t kFlEsHi         = 0xc9u;                          // SH: SPI_SHADER_PGM_HI_ES
constexpr uint32_t kFlUd[6]        = {0x94u, 0x95u, 0xa0u, 0xa1u, 0xa4u, 0xa5u}; // SH: SPI_SHADER_USER_DATA_GS_8/9, 20/21, 24/25
constexpr uint32_t kFlWriteData2   = 0xC0043700u;                    // PKT3(WRITE_DATA, 4, 0)
constexpr uint32_t kFlWriteCtl     = (5u << 8u) | (1u << 20u);       // DST_SEL memory, WR_CONFIRM, ENGINE_SEL ME
constexpr uint32_t kFlCopyData     = 0xC0044000u;                    // PKT3(COPY_DATA, 4, 0)
constexpr uint32_t kFlCopyCtl      = 1u | (5u << 8u) | (1u << 20u);  // SRC_SEL memory, DST_SEL memory, WR_CONFIRM, ME
constexpr uint32_t kFlReleaseMem   = 0xC0064900u;                    // PKT3(RELEASE_MEM, 6, 0)
constexpr uint32_t kFlEopEvent     = 0x28u | (5u << 8u);             // BOTTOM_OF_PIPE_TS, EVENT_INDEX 5
constexpr uint32_t kFlEopData64    = 2u << 29u;                      // DATA_SEL 2: the 64-bit value; DST_SEL 0, INT_SEL 0
constexpr uint32_t kFlEntries      = 64;                             // ring entries per submission
constexpr uint32_t kFlEntryBytes   = 128;
constexpr uint64_t kFlAreaOff      = 0x8000u;                        // in the GDS shadow: issued +0, done +8, ring +0x100
constexpr uint64_t kFlAreaBytes    = 0x100u + static_cast<uint64_t>(kFlEntries) * kFlEntryBytes;

struct FlVal { // a tracked register: n 0 unknown, 1 v[0], 2 v[0] or v[1] (either branch of a COND_EXEC range)
    uint32_t n    = 0;
    uint64_t v[2] = {0, 0};
};
static FlVal fl_val(uint64_t x) {
    FlVal r;
    r.n    = 1;
    r.v[0] = x;
    return r;
}
static FlVal fl_merge(const FlVal& a, const FlVal& b) { // either a or b: both sets of values, unknown past two
    if (a.n == 0 || b.n == 0) return FlVal {};
    FlVal r = a;
    for (uint32_t k = 0; k < b.n; k++) {
        if (b.v[k] == r.v[0] || (r.n == 2 && b.v[k] == r.v[1])) continue;
        if (r.n == 2) return FlVal {};
        r.v[r.n++] = b.v[k];
    }
    return r;
}
// 0 unknown, 1 false for every value, 2 true for one of two, 3 true for every value
template <class P>
static int fl_test(const FlVal& x, const P& p) {
    if (x.n == 0) return 0;
    uint32_t t = 0;
    for (uint32_t k = 0; k < x.n; k++) t += p(x.v[k]) ? 1u : 0u;
    return t == 0 ? 1 : (t == x.n ? 3 : 2);
}
static bool fl_fast_launch(uint64_t stages) { // VGT_SHADER_STAGES_EN.GS_FAST_LAUNCH, bits 20:19, not 0
    return ((stages >> 19u) & 3u) != 0;
}
static int fl_class(const FlVal& stages) { // as fl_test: 0 unknown, 1 not fast-launch, 2 maybe, 3 fast-launch
    return fl_test(stages, [](uint64_t v) { return fl_fast_launch(v); });
}

struct FlState { // the GFX context's tracked registers, carried from buffer to buffer
    FlVal              stages, es_lo, es_hi, base1;
    FlVal              ud[6];
    std::vector<FlVal> stack; // VGT_SHADER_STAGES_EN as CLEAR_STATE cmd 1 pushed it (full_state's stack, 8 deep)
};
static FlVal* fl_sh(FlState& s, uint32_t r) {
    if (r == kFlEsLo) return &s.es_lo;
    if (r == kFlEsHi) return &s.es_hi;
    for (uint32_t k = 0; k < 6; k++) {
        if (r == kFlUd[k]) return &s.ud[k];
    }
    return nullptr;
}
static void fl_merge_state(FlState& s, const FlState& o) { // s: the taken branch's state, o: what a skip leaves
    s.stages = fl_merge(s.stages, o.stages);
    s.es_lo  = fl_merge(s.es_lo, o.es_lo);
    s.es_hi  = fl_merge(s.es_hi, o.es_hi);
    s.base1  = fl_merge(s.base1, o.base1);
    for (uint32_t k = 0; k < 6; k++) s.ud[k] = fl_merge(s.ud[k], o.ud[k]);
    if (s.stack.size() != o.stack.size()) {
        s.stack.clear(); // the branches pushed differently: a later pop is unknown
    } else {
        for (std::size_t k = 0; k < s.stack.size(); k++) s.stack[k] = fl_merge(s.stack[k], o.stack[k]);
    }
}
static bool fl_is_draw(uint32_t op) {
    return op == 0x24 || op == 0x25 || op == 0x27 || op == 0x2c || op == 0x2d || op == 0x35 || op == 0x38;
}
static bool fl_is_indirect(uint32_t op) {
    return op == 0x24 || op == 0x25 || op == 0x2c || op == 0x38;
}

struct FlLayout { // GPU addresses of the crumbs
    uint64_t shadow = 0, issued = 0, done = 0, ring = 0;
    uint32_t entries = 0;
};
static FlLayout fl_layout(uint64_t shadow_va) {
    FlLayout l;
    l.shadow  = shadow_va;
    l.issued  = shadow_va + kFlAreaOff;
    l.done    = shadow_va + kFlAreaOff + 8u;
    l.ring    = shadow_va + kFlAreaOff + 0x100u;
    l.entries = kFlEntries;
    return l;
}
struct FlDraw {
    uint32_t at = 0, len = 0, op = 0; // the packet: dword offset in the buffer, dwords, opcode
    uint32_t cls  = 0;                // fl_class of its VGT_SHADER_STAGES_EN: 0 unknown, 2 maybe, 3 fast-launch
    uint32_t cond = 0;                // COND_EXEC ranges open at the draw
    bool     drop      = false;       // BC5_DIRECT_FL_SKIP_ES drops it
    bool     crumbs    = false;       // it has crumbs (fl_build clears it where a COND_EXEC count cannot grow)
    bool     cond_full = false;       // ... cleared so
    FlVal    stages, es_lo, es_hi;    // the tracked values at the draw
    uint64_t args    = 0;             // the 16 argument bytes copied from here (0: none: a direct draw, base unknown, unmapped)
    uint64_t base[3] = {0, 0, 0};     // the 32 bytes copied at the s[8:9], s[20:21], s[24:25] V# bases (0: none)
    uint32_t snap[28] = {};           // the same dwords as the CPU read them at submit: arguments 0-3, bases 4-11, 12-19, 20-27
    uint64_t id    = 0;               // (at << 32) | the submission number's low 32 bits: the crumbs' value
    uint32_t entry = 0;               // its ring entry
    uint32_t new_at = 0;              // the packet's offset in the copy with the crumbs
    int32_t  seg    = -1;             // the chain segment it lies in (the caller's; -1: not a chain)
    uint32_t seg_at = 0;              // its offset in that segment's buffer (the caller's)
};
struct FlPlan {
    std::vector<FlDraw> draws;        // the draws with crumbs or dropped, in buffer order
    bool     crumbs = false;          // BC5_DIRECT_FL_CRUMBS planned this buffer
    FlLayout lay;
    uint64_t submit = 0;
    uint32_t total = 0, host_dropped = 0, not_fl = 0, fl = 0, maybe = 0, unknown = 0; // the draws of a dcb, by class
    uint32_t skipped = 0, planned = 0, with_crumbs = 0, cond_full = 0, ib2 = 0, unread = 0;
};
struct FlOptions {
    bool                         draws   = false;   // a dcb: plan its draws (otherwise only the state is followed)
    bool                         crumbs  = false;   // plan crumbs for them
    const std::vector<uint32_t>* skip_es = nullptr; // sorted SPI_SHADER_PGM_LO_ES values (BC5_DIRECT_FL_SKIP_ES)
    const std::vector<uint32_t>* drops   = nullptr; // sorted offsets the caller drops already: not planned
};

// Follows ib (n dwords) from st and leaves st as the buffer leaves the GPU's state; with o.draws, plans its draws.
// read(address, bytes): the memory at address, or nullptr when the host may not read it.
template <class Read>
static void fl_scan(const uint32_t* ib, uint32_t n, const Read& read, FlState& st, const FlOptions& o, FlPlan& plan) {
    struct Open {
        uint32_t end;
        FlState  at; // the state where the range starts: what a skip leaves
    };
    std::vector<Open> ranges;
    bool              lost = false; // more than 32 ranges open: nothing is known from there on
    const auto addr = [](uint32_t lo, uint32_t hi) {
        return (static_cast<uint64_t>(lo) & ~3ull) | (static_cast<uint64_t>(hi & 0xffffu) << 32u);
    };
    const auto forget_sh = [&st] {
        st.es_lo = st.es_hi = FlVal {};
        for (FlVal& u: st.ud) u = FlVal {};
    };
    const auto forget_all = [&st, &forget_sh] {
        st.stages = st.base1 = FlVal {};
        st.stack.clear();
        forget_sh();
    };
    const auto close_ranges = [&ranges, &st](uint32_t q) {
        for (std::size_t k = ranges.size(); k-- > 0;) {
            if (ranges[k].end <= q) {
                fl_merge_state(st, ranges[k].at);
                ranges.erase(ranges.begin() + static_cast<std::ptrdiff_t>(k));
            }
        }
    };
    const auto covers = [](bool ctx, uint32_t first, uint32_t count) {
        if (ctx) return kFlStages - first < count;
        bool any = kFlEsLo - first < count || kFlEsHi - first < count;
        for (uint32_t k = 0; k < 6; k++) any = any || kFlUd[k] - first < count;
        return any;
    };
    // registers [first, first + count) of the context (ctx) or SH space from t; t == nullptr: unreadable, unknown
    const auto load_range = [&st](bool ctx, uint32_t first, uint32_t count, const uint32_t* t) {
        if (ctx) {
            if (kFlStages - first < count) st.stages = t != nullptr ? fl_val(t[kFlStages - first]) : FlVal {};
            return;
        }
        const uint32_t regs[8] = {kFlEsLo, kFlEsHi, kFlUd[0], kFlUd[1], kFlUd[2], kFlUd[3], kFlUd[4], kFlUd[5]};
        for (const uint32_t r: regs) {
            if (r - first < count) *fl_sh(st, r) = t != nullptr ? fl_val(t[r - first]) : FlVal {};
        }
    };
    for (uint32_t q = 0; q < n;) {
        close_ranges(q);
        const uint32_t h = ib[q], type = h >> 30u, c = (h >> 16u) & 0x3fffu;
        const uint32_t len = (type == 3 || type == 0) && c != 0x3fffu ? c + 2u : 1u;
        if (q + len > n) break;
        if (type != 3 || c == 0x3fffu) {
            q += len;
            continue;
        }
        if (lost) forget_all();
        const uint32_t  op = (h >> 8u) & 0xffu;
        const uint32_t* p  = ib + q;
        if (op == 0x69 && len >= 3) { // SET_CONTEXT_REG
            const uint32_t first = p[1] & 0xffffu;
            if (kFlStages - first < len - 2u) st.stages = fl_val(p[2u + kFlStages - first]);
        } else if ((op == 0x76 || op == 0x9b) && len >= 3) { // SET_SH_REG, SET_SH_REG_INDEX
            const uint32_t first = p[1] & 0xffffu;
            for (uint32_t k = 0; k + 2u < len; k++) {
                if (FlVal* v = fl_sh(st, first + k); v != nullptr) *v = fl_val(p[2u + k]);
            }
        } else if ((op == 0x61 || op == 0x5f) && len >= 5) { // LOAD_CONTEXT_REG, LOAD_SH_REG
            const bool     ctx  = op == 0x61;
            const uint64_t base = addr(p[1], p[2]);
            for (uint32_t k = 3; k + 1u < len; k += 2) {
                const uint32_t first = p[k] & 0xffffu, count = p[k + 1u] & 0x3fffu;
                if (count == 0 || !covers(ctx, first, count)) continue;
                const uint32_t* t = read(base + static_cast<uint64_t>(first) * 4u, static_cast<uint64_t>(count) * 4u);
                if (t == nullptr) plan.unread++;
                load_range(ctx, first, count, t);
            }
        } else if ((op == 0x9f || op == 0x63) && len >= 5) { // LOAD_CONTEXT_REG_INDEX, LOAD_SH_REG_INDEX
            const bool     ctx   = op == 0x9f;
            const uint64_t a     = addr(p[1], p[2]);
            const uint32_t count = p[4] & 0x3fffu;
            if (count != 0 && (p[3] >> 31u) != 0) { // (offset, value) pairs
                const uint32_t* t = read(a, static_cast<uint64_t>(count) * 8u);
                if (t == nullptr) {
                    plan.unread++;
                    if (ctx) st.stages = FlVal {};
                    else forget_sh();
                } else {
                    for (uint32_t k = 0; k < count; k++) {
                        const uint32_t r = t[2u * k] & 0xffffu;
                        if (ctx) {
                            if (r == kFlStages) st.stages = fl_val(t[2u * k + 1u]);
                        } else if (FlVal* v = fl_sh(st, r); v != nullptr) {
                            *v = fl_val(t[2u * k + 1u]);
                        }
                    }
                }
            } else if (count != 0 && covers(ctx, p[3] & 0xffffu, count)) { // count registers from the offset in dword 3
                const uint32_t* t = read(a, static_cast<uint64_t>(count) * 4u);
                if (t == nullptr) plan.unread++;
                load_range(ctx, p[3] & 0xffffu, count, t);
            }
        } else if (op == 0x12 && len >= 2) { // CLEAR_STATE
            const uint32_t cmd = p[1] & 0xfu;
            if (cmd == 1) {
                if (st.stack.size() < 8) st.stack.push_back(st.stages);
                st.stages = FlVal {};
            } else if (cmd == 2 && !st.stack.empty()) {
                st.stages = st.stack.back();
                st.stack.pop_back();
            } else {
                st.stages = FlVal {};
            }
        } else if (op == 0x3f || op == 0x33) { // INDIRECT_BUFFER (_CONST): not followed, it may set anything
            forget_all();
            plan.ib2++;
        } else if (op == 0x11 && len >= 4 && (p[1] & 0xfu) == 1) { // SET_BASE index 1
            st.base1 = fl_val(addr(p[2], p[3]));
        } else if (op == 0x22 && len == 5) { // COND_EXEC
            if (ranges.size() >= 32) {
                lost = true;
                forget_all();
            } else {
                ranges.push_back(Open {std::min(q + 5u + (p[4] & 0x3fffu), n), st});
            }
        } else if (o.draws && fl_is_draw(op)) {
            plan.total++;
            const int cls = fl_class(st.stages);
            if (o.drops != nullptr && std::binary_search(o.drops->begin(), o.drops->end(), q)) {
                plan.host_dropped++;
            } else if (cls == 1) {
                plan.not_fl++;
            } else {
                FlDraw d;
                d.at     = q;
                d.len    = len;
                d.op     = op;
                d.cls    = static_cast<uint32_t>(cls);
                d.cond   = static_cast<uint32_t>(ranges.size());
                d.stages = st.stages;
                d.es_lo  = st.es_lo;
                d.es_hi  = st.es_hi;
                (cls == 3 ? plan.fl : cls == 2 ? plan.maybe : plan.unknown)++;
                const bool listed = o.skip_es != nullptr && !o.skip_es->empty() && fl_test(st.es_lo, [&o](uint64_t v) {
                    return std::binary_search(o.skip_es->begin(), o.skip_es->end(), static_cast<uint32_t>(v));
                }) == 3;
                if (cls == 3 && listed) { // certainly fast-launch, and its ES certainly listed
                    d.drop = true;
                    plan.skipped++;
                } else if (o.crumbs) {
                    d.crumbs = true;
                    plan.planned++;
                    if (fl_is_indirect(op) && len >= 2 && st.base1.n == 1 && st.base1.v[0] != 0) {
                        const uint64_t a = (st.base1.v[0] + p[1]) & ~3ull;
                        if (const uint32_t* t = read(a, 16 + 4); t != nullptr) { // + 4: the filter's operand check, below
                            d.args = a;
                            for (uint32_t k = 0; k < 4; k++) d.snap[k] = t[k];
                        }
                    }
                    for (uint32_t b = 0; b < 3; b++) {
                        const FlVal &lo = st.ud[2 * b], &hi = st.ud[2 * b + 1];
                        if (lo.n != 1 || hi.n != 1) continue;
                        const uint64_t a = (lo.v[0] | ((hi.v[0] & 0xffffu) << 32u)) & ~3ull; // the V# base, as timeout_probe reads it
                        if (a == 0) continue;
                        if (const uint32_t* t = read(a, 32 + 4); t != nullptr) {
                            d.base[b] = a;
                            for (uint32_t k = 0; k < 8; k++) d.snap[4 + 8 * b + k] = t[k];
                        }
                    }
                }
                if (d.drop || d.crumbs) plan.draws.push_back(d);
            }
        }
        q += len;
    }
    close_ranges(~0u);
    if (lost) forget_all();
}

static void fl_write(std::vector<uint32_t>& out, uint64_t va, uint64_t v) { // WRITE_DATA, two dwords, ME, confirmed
    out.insert(out.end(), {kFlWriteData2, kFlWriteCtl, static_cast<uint32_t>(va) & ~3u, static_cast<uint32_t>(va >> 32u) & 0xffffu,
                           static_cast<uint32_t>(v), static_cast<uint32_t>(v >> 32u)});
}
static void fl_copy(std::vector<uint32_t>& out, uint64_t src, uint64_t dst) { // COPY_DATA memory to memory, 32 bits, ME, confirmed
    out.insert(out.end(), {kFlCopyData, kFlCopyCtl, static_cast<uint32_t>(src) & ~3u, static_cast<uint32_t>(src >> 32u) & 0xffffu,
                           static_cast<uint32_t>(dst) & ~3u, static_cast<uint32_t>(dst >> 32u) & 0xffffu});
}
static void fl_pre(const FlDraw& d, const FlLayout& lay, std::vector<uint32_t>& out) { // head, copies, tail, issued
    const uint64_t e = lay.ring + static_cast<uint64_t>(d.entry) * kFlEntryBytes;
    fl_write(out, e, d.id);
    if (d.args != 0) {
        for (uint32_t k = 0; k < 4; k++) fl_copy(out, d.args + 4u * k, e + 8u + 4u * k);
    }
    for (uint32_t b = 0; b < 3; b++) {
        if (d.base[b] == 0) continue;
        for (uint32_t k = 0; k < 8; k++) fl_copy(out, d.base[b] + 4u * k, e + 24u + 32u * b + 4u * k);
    }
    fl_write(out, e + 120u, d.id);
    fl_write(out, lay.issued, d.id);
}
static void fl_post(const FlDraw& d, const FlLayout& lay, std::vector<uint32_t>& out) { // done: end of pipe
    out.insert(out.end(), {kFlReleaseMem, kFlEopEvent, kFlEopData64, static_cast<uint32_t>(lay.done) & ~3u,
                           static_cast<uint32_t>(lay.done >> 32u) & 0xffffu, static_cast<uint32_t>(d.id), static_cast<uint32_t>(d.id >> 32u), 0u});
}
// Lays the crumbs of the draws planned with them into a copy of ib (out). Returns the draws given crumbs; 0 (out empty,
// every d.crumbs false) when none. old_to_new: each old packet start's offset in out (~0u elsewhere, [n] = out.size());
// new_to_old: each title packet's old offset at its new start (~0u at the crumbs).
static uint32_t fl_build(const uint32_t* ib, uint32_t n, FlPlan& plan, uint64_t submit, std::vector<uint32_t>& out,
                         std::vector<uint32_t>& old_to_new, std::vector<uint32_t>& new_to_old) {
    const auto len_at = [ib, n](uint32_t q) { // a cut last packet is copied as it is
        const uint32_t h = ib[q], type = h >> 30u, c = (h >> 16u) & 0x3fffu;
        const uint32_t len = (type == 3 || type == 0) && c != 0x3fffu ? c + 2u : 1u;
        return q + len > n ? n - q : len;
    };
    plan.submit = submit;
    std::vector<uint32_t> unit_at; // where the packet at an old offset starts in out, its crumbs included
    uint32_t              made   = 0;
    bool                  fitted = false;
    for (int attempt = 0; attempt < 64 && !fitted; attempt++) {
        out.clear();
        unit_at.assign(n + 1u, ~0u);
        old_to_new.assign(n + 1u, ~0u);
        made          = 0;
        std::size_t k = 0;
        for (uint32_t q = 0; q < n;) {
            const uint32_t len = len_at(q);
            unit_at[q]         = static_cast<uint32_t>(out.size());
            while (k < plan.draws.size() && plan.draws[k].at < q) k++;
            FlDraw*    d    = k < plan.draws.size() && plan.draws[k].at == q ? &plan.draws[k] : nullptr;
            const bool with = d != nullptr && d->crumbs && plan.lay.entries != 0;
            if (with) {
                d->entry = made++ % plan.lay.entries;
                d->id    = (static_cast<uint64_t>(q) << 32u) | static_cast<uint32_t>(submit);
                fl_pre(*d, plan.lay, out);
            }
            old_to_new[q] = static_cast<uint32_t>(out.size());
            if (d != nullptr) d->new_at = old_to_new[q];
            out.insert(out.end(), ib + q, ib + q + len);
            if (with) fl_post(*d, plan.lay, out);
            q += len;
        }
        unit_at[n] = old_to_new[n] = static_cast<uint32_t>(out.size());
        std::vector<std::pair<uint32_t, uint32_t>> full; // ranges whose grown count does not fit
        for (uint32_t q = 0; q < n;) {
            const uint32_t len = len_at(q);
            if (ib[q] >> 30u == 3 && ((ib[q] >> 8u) & 0xffu) == 0x22 && len == 5) {
                uint32_t e = std::min(q + 5u + (ib[q + 4] & 0x3fffu), n);
                while (unit_at[e] == ~0u) e++; // a range ending inside a packet: with it
                const uint32_t count = unit_at[e] - (old_to_new[q] + 5u);
                if (count > 0x3fffu) full.emplace_back(q + 5u, e);
                else out[old_to_new[q] + 4u] = (out[old_to_new[q] + 4u] & ~0x3fffu) | count;
            }
            q += len;
        }
        fitted            = full.empty();
        uint32_t excluded = 0;
        for (FlDraw& d: plan.draws) {
            bool inside = false;
            for (const auto& [lo, hi]: full) inside = inside || (d.at >= lo && d.at < hi);
            if (inside && d.crumbs) {
                d.crumbs    = false;
                d.cond_full = true;
                d.id        = 0;
                plan.cond_full++;
                excluded++;
            }
        }
        if (!fitted && excluded == 0) break; // cannot happen: a range grows only by crumbs inside it
    }
    if (!fitted || made == 0) {
        out.clear();
        old_to_new.clear();
        new_to_old.clear();
        for (FlDraw& d: plan.draws) d.crumbs = false;
        plan.with_crumbs = 0;
        return 0;
    }
    new_to_old.assign(out.size(), ~0u);
    for (uint32_t q = 0; q < n; q++) {
        if (old_to_new[q] != ~0u) new_to_old[old_to_new[q]] = q;
    }
    plan.with_crumbs = made;
    return made;
}

// The probe's reading of the two slots. status 0: issued names no draw with crumbs of this buffer; 1: the draw issued
// last is done; 2: draws first..last (indices into plan.draws) were issued and are not done, first being the first draw
// with crumbs after the one done names (or the buffer's first when done names none of its draws); 3: done names a draw
// after the one issued names (inconsistent). It assumes end-of-pipe events retire in order (TODO(verify) on gfx1013).
struct FlFind {
    int status = 0;
    int issued = -1, done = -1, first = -1, last = -1;
};
static FlFind fl_find(const FlPlan& plan, uint64_t issued, uint64_t done) {
    FlFind f;
    for (std::size_t k = 0; k < plan.draws.size(); k++) {
        if (!plan.draws[k].crumbs) continue;
        if (plan.draws[k].id == issued) f.issued = static_cast<int>(k);
        if (plan.draws[k].id == done) f.done = static_cast<int>(k);
    }
    if (f.issued < 0) return f;
    if (f.done == f.issued) {
        f.status = 1;
        return f;
    }
    if (f.done > f.issued) {
        f.status = 3;
        return f;
    }
    for (int k = f.done + 1; k <= f.issued; k++) {
        if (plan.draws[static_cast<std::size_t>(k)].crumbs) {
            f.first = k;
            break;
        }
    }
    f.last   = f.issued;
    f.status = 2;
    return f;
}
// A ring entry (32 dwords) as the CP left it, for the draw id: 0 complete (head and tail name it), 1 begun (the head
// names it, the tail does not: the CP stopped inside its copies), 2 overwritten (the head names another draw: the ring
// wrapped), 3 never written (head 0).
static int fl_entry_check(const uint32_t* e, uint64_t id) {
    const uint64_t head = e[0] | (static_cast<uint64_t>(e[1]) << 32u), tail = e[30] | (static_cast<uint64_t>(e[31]) << 32u);
    if (head == id) return tail == id ? 0 : 1;
    return head == 0 ? 3 : 2;
}
// BC5_DIRECT_FL_SKIP_ES: SPI_SHADER_PGM_LO_ES values (the program address >> 8, as exp 0404 writes them; the timeout
// probe's "es" prints HI_ES then LO_ES), hexadecimal with or without 0x, separated by commas or spaces; each 1..ffffffff
// (more digits are fine while the value fits: the probe's 16-digit "0000000011d00f85" is 0x11d00f85). out: sorted, once
// each. False, and out empty, for an unset, empty or "0" value (F767) and for one that does not parse (the switch is
// then off).
static bool fl_parse_es_list(const char* e, std::vector<uint32_t>& out) {
    out.clear();
    if (e == nullptr || e[0] == 0 || (e[0] == '0' && e[1] == 0)) return false;
    for (const char* c = e; *c != 0;) {
        if (*c == ',' || *c == ' ') {
            c++;
            continue;
        }
        if (c[0] == '0' && (c[1] == 'x' || c[1] == 'X')) c += 2;
        uint64_t v = 0;
        int      digits = 0;
        for (; *c != 0 && *c != ',' && *c != ' '; c++) {
            const char x = *c;
            const int  d = x >= '0' && x <= '9' ? x - '0' : x >= 'a' && x <= 'f' ? x - 'a' + 10 : x >= 'A' && x <= 'F' ? x - 'A' + 10 : -1;
            if (d < 0 || v > 0xffffffffull) {
                out.clear();
                return false;
            }
            v = v * 16u + static_cast<uint64_t>(d);
            digits++;
        }
        if (digits == 0 || v == 0 || v > 0xffffffffull) {
            out.clear();
            return false;
        }
        out.push_back(static_cast<uint32_t>(v));
    }
    std::sort(out.begin(), out.end());
    out.erase(std::unique(out.begin(), out.end()), out.end());
    return !out.empty();
}
static void fl_fmt(const FlVal& x, char* out, std::size_t cap) { // "00482030", "00482030|00000000" (one of two), "unknown"
    if (x.n == 0) std::snprintf(out, cap, "unknown");
    else if (x.n == 1) std::snprintf(out, cap, "%08x", static_cast<uint32_t>(x.v[0]));
    else std::snprintf(out, cap, "%08x|%08x", static_cast<uint32_t>(x.v[0]), static_cast<uint32_t>(x.v[1]));
}
// ---- end of experiment 0404's pure part -----------------------------------------------------------------------------
""")

# ---------------------------------------------------------------------------------------------------------------------
# The host's side: the switches, the walk's call, the crumbs' copy, the probe. In the unit only.
FL_GLUE = tabs(r"""// ---- experiment 0404: the switches and the host's side ------------------------------------------------------------------
// BC5_DIRECT_FL_CRUMBS=1 (catcher, default off; on/off as F767's env_on): every draw of a dcb whose VGT_SHADER_STAGES_EN
// is fast-launch, or may be (one of two values after a COND_EXEC range, or unknown), gets fl_build's crumbs: before it
// (and before the backend's own check of it) a head, the CP's copies of its 16 argument bytes and of 32 bytes at each V#
// base of its GS user data, a tail and "issued"; after it an end-of-pipe "done". The slots and the ring lie in the
// backend's 64 KiB GDS shadow (Device::gds_shadow_va, on every BO list; CPU view gds_shadow_cpu) from +0x8000: issued
// +0x8000, done +0x8008, 64 entries of 128 bytes at +0x8100..+0xa100. That part is free: the backend writes the shadow
// only through FilterOptions::gds_shadow_va (backend/src/policy.cpp), which this unit never sets (mkfl0401.py asserts it),
// and its only other user, the GE probe (exp 0160), has +0xc000..+0xffff (static_assert below). At a fence timeout
// fl_probe journals both slots, the draws issued and not done, and the ring entry of the first one: its argument and V#
// bytes as the CP's ME copied them when it reached the crumbs. That is a CP read just before the draw's check, not the
// shader's own fetch (lessons R12, R13); the CPU's reads at submit and at the timeout are printed beside it.
// Cost when on, per such draw: 3 WRITE_DATA, up to 28 COPY_DATA and one RELEASE_MEM (at most 194 dwords, each write
// confirmed) and one end-of-pipe event; the catcher changes the timing it watches (R12). Off: two flag tests per buffer
// and one compare per memory operand in the filter's mapped(); nothing is inserted, nothing dropped.
// BC5_DIRECT_FL_SKIP_ES=<hex list> (diagnostic, default off): a draw of a dcb whose VGT_SHADER_STAGES_EN is certainly
// fast-launch and whose SPI_SHADER_PGM_LO_ES is certainly one of the values (fl_parse_es_list) is dropped through
// FilterOptions::drop_offsets, as BC5_DIRECT_SKIP_PGM drops dispatches. Not a fix: the scene loses those meshes.
static_assert(kFlAreaOff + kFlAreaBytes <= kGeProbeOff, "the crumbs' area overlaps the GE probe's slots");
static bool fl_crumbs_on() {
    static const bool on = [] {
        const bool v = bc5::env_on(std::getenv("BC5_DIRECT_FL_CRUMBS"));
        journal("exp 0404: fl crumbs %s\n", v ? "on (the fast-launch draws of each dcb: issued/done crumbs and their inputs copied by the CP into the GDS shadow +0x8000; read at a fence timeout)" : "off");
        return v;
    }();
    return on;
}
static const std::vector<uint32_t>& fl_skip_es() {
    static const std::vector<uint32_t> list = [] {
        std::vector<uint32_t> v;
        const char*           e = std::getenv("BC5_DIRECT_FL_SKIP_ES");
        if (!fl_parse_es_list(e, v)) {
            if (bc5::env_on(e)) journal("exp 0404: fl skip es off (BC5_DIRECT_FL_SKIP_ES=\"%s\" does not parse: hexadecimal SPI_SHADER_PGM_LO_ES values 1..ffffffff, separated by commas)\n", e);
            else journal("exp 0404: fl skip es off\n");
            return v;
        }
        std::string values, programs;
        for (const uint32_t x: v) {
            char b[48];
            std::snprintf(b, sizeof(b), "%s0x%x", values.empty() ? "" : ",", x);
            values += b;
            std::snprintf(b, sizeof(b), "%s0x%" PRIx64, programs.empty() ? "" : ", ", static_cast<uint64_t>(x) << 8u);
            programs += b;
        }
        journal("exp 0404: fl skip es %s (SPI_SHADER_PGM_LO_ES values: the programs at %s while SPI_SHADER_PGM_HI_ES is 0; a draw whose VGT_SHADER_STAGES_EN is certainly fast-launch and whose ES is certainly listed is dropped)\n",
                values.c_str(), programs.c_str());
        return v;
    }();
    return list;
}
static uint64_t fl_crumbs_area() { // the crumbs' area (GPU VA), 0 when the crumbs are off or the device has no GDS shadow
    if (!fl_crumbs_on() || !g_dev || g_dev->gds_shadow_va() == 0 || g_dev->gds_shadow_cpu() == nullptr) return 0;
    return g_dev->gds_shadow_va() + kFlAreaOff;
}
static std::mutex            g_fl_mutex;
static FlState               g_fl_state; // the GFX context's tracked registers, in submission order (submit_now's buffers)
static std::atomic<uint64_t> g_fl_bufs {0}, g_fl_draws {0}, g_fl_maybe {0}, g_fl_unknown {0}, g_fl_cond_full {0}, g_fl_skipped {0}, g_fl_refused {0};
// submit_now, after its walk and before the filter: follows the state through the buffer (every GFX-class buffer of the
// GFX ring), plans the draws of a dcb, and adds the ES skip's drops (offsets in ib).
static void fl_plan_buffer(const uint32_t* ib, uint32_t n, const char* kind, int ring, const Chain* chain, const std::vector<bc5::direct::Mapping>& maps,
                           std::vector<uint32_t>& drop_offsets, FlPlan& plan) {
    const bool                   crumbs = fl_crumbs_on();
    const std::vector<uint32_t>& skip   = fl_skip_es();
    if (!crumbs && skip.empty()) return;
    if (std::strncmp(kind, "acb", 3) == 0 && ring != bc5::direct::kGfxRing) return; // a compute ring's own context
    FlOptions      o;
    const uint64_t area = fl_crumbs_area();
    o.draws             = std::strncmp(kind, "dcb", 3) == 0;
    o.crumbs            = crumbs && o.draws && area != 0;
    o.skip_es           = &skip;
    std::vector<uint32_t> drops(drop_offsets);
    std::sort(drops.begin(), drops.end());
    o.drops = &drops;
    if (crumbs && o.draws && area == 0) {
        static std::atomic<bool> told {false};
        if (!told.exchange(true)) journal("fl crumbs (exp 0404): the device has no GDS shadow: no crumbs\n");
        g_fl_refused++;
    }
    plan.crumbs = o.crumbs;
    if (o.crumbs) plan.lay = fl_layout(area - kFlAreaOff);
    const auto reader = [&maps](uint64_t a, uint64_t bytes) -> const uint32_t* {
        return covered_sorted(maps, a, bytes) ? reinterpret_cast<const uint32_t*>(a) : nullptr;
    };
    {
        std::lock_guard lk(g_fl_mutex);
        fl_scan(ib, n, reader, g_fl_state, o, plan);
    }
    for (FlDraw& d: plan.draws) {
        if (d.drop) drop_offsets.push_back(d.at);
        d.seg_at = d.at;
        if (chain == nullptr) continue;
        for (std::size_t k = 0; k < chain->segs.size(); k++) {
            const ChainSeg& s = chain->segs[k];
            if (d.at >= s.off + s.prefix && d.at < s.off + s.prefix + s.n) {
                d.seg    = static_cast<int32_t>(k);
                d.seg_at = d.at - s.off - s.prefix;
                break;
            }
        }
    }
}
// submit_now, once the submission's number is known (before the mec rebuild's offset maps are used): journals the ES
// skip's drops and, with the crumbs, lays them into out and maps the drop and kept-wait offsets into it. new_to_old maps
// the executed offsets back (fl_back), as mec_back does for the mec rebuild.
static void fl_after(const uint32_t* ib, uint32_t n, const char* kind, uint64_t submit, bool mec_rebuilt, FlPlan& plan, bc5::policy::FilterOptions& opt,
                     std::vector<uint32_t>& out, std::vector<uint32_t>& new_to_old) {
    for (const FlDraw& d: plan.draws) {
        if (!d.drop) continue;
        const uint64_t k = g_fl_skipped++;
        if (k < 16 || (k & 0xfffu) == 0) {
            char sg[40], es[40];
            fl_fmt(d.stages, sg, sizeof(sg));
            fl_fmt(d.es_lo, es, sizeof(es));
            journal("fl skip es (exp 0404): submit #%" PRIu64 " %s op %02x at %u: es %s, stages %s: dropped (%" PRIu64 " so far)\n", submit, kind, d.op, d.at, es, sg, k + 1);
        }
    }
    if (!plan.crumbs || plan.planned == 0) return;
    if (mec_rebuilt) { // a compute buffer's rebuild: never a dcb's; counted, no crumbs
        for (FlDraw& d: plan.draws) d.crumbs = false;
        g_fl_refused++;
        return;
    }
    std::vector<uint32_t> old_to_new;
    const uint32_t        made = fl_build(ib, n, plan, submit, out, old_to_new, new_to_old);
    if (plan.cond_full != 0) {
        const uint64_t k = g_fl_cond_full.fetch_add(plan.cond_full);
        if (k < 16 || (k >> 12u) != ((k + plan.cond_full) >> 12u))
            journal("fl crumbs (exp 0404): submit #%" PRIu64 " %s: %u draws left without crumbs, a COND_EXEC count would not fit 14 bits (%" PRIu64 " so far)\n", submit, kind, plan.cond_full, k + plan.cond_full);
    }
    if (made == 0) return;
    for (uint32_t& d: opt.drop_offsets) d = d < n && old_to_new[d] != ~0u ? old_to_new[d] : ~0u;
    for (uint32_t& d: opt.keep_wait_offsets) d = d < n && old_to_new[d] != ~0u ? old_to_new[d] : ~0u;
    std::erase(opt.drop_offsets, ~0u);
    std::erase(opt.keep_wait_offsets, ~0u);
    g_fl_maybe += plan.maybe;
    g_fl_unknown += plan.unknown;
    {
        static std::atomic<bool> told {false};
        if (!told.exchange(true))
            journal("fl crumbs (exp 0404): issued at 0x%" PRIx64 ", done at 0x%" PRIx64 ", %u ring entries of %u bytes at 0x%" PRIx64 " (the GDS shadow +0x%" PRIx64 ")\n", plan.lay.issued, plan.lay.done,
                    plan.lay.entries, kFlEntryBytes, plan.lay.ring, kFlAreaOff);
    }
    for (const FlDraw& d: plan.draws) {
        if (!d.crumbs) continue;
        const uint64_t k = g_fl_draws++;
        if (k < 16 || (k & 0xfffu) == 0) {
            char sg[40], es[40];
            fl_fmt(d.stages, sg, sizeof(sg));
            fl_fmt(d.es_lo, es, sizeof(es));
            journal("fl crumbs (exp 0404): submit #%" PRIu64 " %s op %02x at %u (+%u in the copy), entry %u: stages %s es %s, arguments 0x%" PRIx64 ", V# bases 0x%" PRIx64 " 0x%" PRIx64 " 0x%" PRIx64 " (%" PRIu64 " draws so far)\n",
                    submit, kind, d.op, d.at, d.new_at, d.entry, sg, es, d.args, d.base[0], d.base[1], d.base[2], k + 1);
        }
    }
    if ((g_fl_bufs++ & 0x3fffu) == 0)
        journal("fl crumbs (exp 0404): %" PRIu64 " buffers with crumbs, %" PRIu64 " draws (%" PRIu64 " of them maybe fast-launch, %" PRIu64 " of unknown state), %" PRIu64 " left without (COND_EXEC full), %" PRIu64 " skipped (es), %" PRIu64 " refused\n",
                g_fl_bufs.load(), g_fl_draws.load(), g_fl_maybe.load(), g_fl_unknown.load(), g_fl_cond_full.load(), g_fl_skipped.load(), g_fl_refused.load());
}
// At a fence timeout, before timeout_probe (whose lines take long): the slots, the draws issued and not done, and the ring
// entry of the first of them. same_device: the job ran on the device still open (no reopen since; the shadow is the job's).
static void fl_probe(const FlPlan& plan, uint64_t n, const char* kind, bool same_device) {
    if (!plan.crumbs) return;
    if (!same_device || !g_dev || g_dev->gds_shadow_cpu() == nullptr || g_dev->gds_shadow_va() != plan.lay.shadow) {
        journal("fl crumbs (exp 0404): at the timeout of submit #%" PRIu64 " %s: the device was opened again before the probe; the crumbs are gone\n", n, kind);
        return;
    }
    const volatile uint32_t* sh     = g_dev->gds_shadow_cpu();
    const volatile uint32_t* slot   = sh + kFlAreaOff / 4u;
    const uint64_t           issued = slot[0] | (static_cast<uint64_t>(slot[1]) << 32u);
    const uint64_t           done   = slot[2] | (static_cast<uint64_t>(slot[3]) << 32u);
    const FlFind             f      = fl_find(plan, issued, done);
    static const char* const what[4] = {"issued names no draw with crumbs of this buffer", "the draw issued last is done: the CP stands past its end-of-pipe crumb",
                                        "the draws issued and not done follow, the first one first (end-of-pipe events retire in order: TODO(verify))",
                                        "done names a draw after the one issued names: inconsistent"};
    journal("fl crumbs (exp 0404): at the timeout of submit #%" PRIu64 " %s: issued #%u +%u, done #%u +%u (submission number's low 32 bits, dword offset); %u draws with crumbs of %u (%u fast-launch, %u maybe, %u unknown state), %u skipped (es), %u without crumbs (COND_EXEC full)%s: %s\n",
            n, kind, static_cast<uint32_t>(issued), static_cast<uint32_t>(issued >> 32u), static_cast<uint32_t>(done), static_cast<uint32_t>(done >> 32u), plan.with_crumbs, plan.total, plan.fl, plan.maybe,
            plan.unknown, plan.skipped, plan.cond_full, plan.with_crumbs > plan.lay.entries ? "; the ring wrapped in this buffer" : "", what[f.status]);
    const auto maps_p = g_dev->sorted_mappings();
    const auto show   = [&](const FlDraw& d, const char* tag, bool with_data) {
        uint32_t                 e[32];
        const volatile uint32_t* ev = sh + (plan.lay.ring - plan.lay.shadow) / 4u + static_cast<std::size_t>(d.entry) * (kFlEntryBytes / 4u);
        for (uint32_t k = 0; k < 32; k++) e[k] = ev[k];
        const int                st       = fl_entry_check(e, d.id);
        static const char* const state[4] = {"complete", "begun, not finished (the CP stopped inside its copies)", "overwritten by another draw (the ring wrapped)", "never written"};
        char                     sg[40], el[40], eh[40];
        fl_fmt(d.stages, sg, sizeof(sg));
        fl_fmt(d.es_lo, el, sizeof(el));
        fl_fmt(d.es_hi, eh, sizeof(eh));
        journal("fl crumbs (exp 0404):   %s: op %02x at %u (chain segment %d +%u; +%u in the copy), entry %u %s (head #%u +%u): stages %s, es hi %s lo %s, %u COND_EXEC ranges open\n", tag, d.op, d.at, d.seg, d.seg_at,
                d.new_at, d.entry, state[st], e[0], e[1], sg, eh, el, d.cond);
        if (!with_data) return;
        const auto one = [&](const char* name, uint64_t a, uint32_t words, uint32_t at_e, uint32_t at_snap) {
            if (a == 0) {
                journal("fl crumbs (exp 0404):     %s: not copied (a direct draw, a base not known for certain, 0, or unmapped)\n", name);
                return;
            }
            char cp[120] = {}, sb[120] = {}, now[120] = "unmapped";
            int  wc = 0, ws = 0, wn = 0;
            for (uint32_t k = 0; k < words; k++) {
                wc += std::snprintf(cp + wc, sizeof(cp) - static_cast<std::size_t>(wc), " %08x", e[at_e + k]);
                ws += std::snprintf(sb + ws, sizeof(sb) - static_cast<std::size_t>(ws), " %08x", d.snap[at_snap + k]);
            }
            if (covered_sorted(*maps_p, a, static_cast<uint64_t>(words) * 4u)) {
                const auto* t = reinterpret_cast<const volatile uint32_t*>(a);
                for (uint32_t k = 0; k < words; k++) wn += std::snprintf(now + wn, sizeof(now) - static_cast<std::size_t>(wn), " %08x", t[k]);
            }
            journal("fl crumbs (exp 0404):     %s at 0x%" PRIx64 ": CP before the draw%s%s | CPU at submit%s | CPU now%s\n", name, a, st == 0 ? "" : " (NOT this draw's: see the entry)", cp, sb, now);
        };
        one("arguments", d.args, 4, 2, 0);
        one("s[8:9] V# base", d.base[0], 8, 6, 4);
        one("s[20:21] V# base", d.base[1], 8, 14, 12);
        one("s[24:25] V# base", d.base[2], 8, 22, 20);
    };
    if (f.status == 2) {
        if (f.done >= 0) show(plan.draws[static_cast<std::size_t>(f.done)], "the last done", false);
        uint32_t lines = 0;
        for (int k = f.first; k >= 0 && k <= f.last && lines < 64; k++) {
            const FlDraw& d = plan.draws[static_cast<std::size_t>(k)];
            if (!d.crumbs) continue;
            show(d, k == f.first ? "FIRST ISSUED, NOT DONE" : "issued, not done", k == f.first);
            lines++;
        }
    } else if (f.status == 1) {
        show(plan.draws[static_cast<std::size_t>(f.issued)], "issued last and done", true);
    } else if (f.status == 3) {
        show(plan.draws[static_cast<std::size_t>(f.issued)], "issued", false);
        show(plan.draws[static_cast<std::size_t>(f.done)], "done", false);
    } else {
        for (const FlDraw& d: plan.draws) {
            if (!d.crumbs) continue;
            show(d, "the first draw with crumbs, not issued", true);
            break;
        }
    }
    if (g_journal_min) {
        if (FILE* jf = journal_min_file(true); jf != nullptr) fsync(fileno(jf));
    }
}

""")

# ---------------------------------------------------------------------------------------------------------------------
# The edits of submit_now, PendingJob and the completion thread: (anchor, text, where).
SCAN_CALL = tabs(r"""    // Experiment 0404 (BC5_DIRECT_FL_CRUMBS, BC5_DIRECT_FL_SKIP_ES; both off by default): the graphics state the GPU will
    // see, followed through this buffer (fl_scan, carried from the buffers before), its fast-launch draws planned and the
    // ES skip's drops added; the crumbs are laid in below, once the submission's number is known. Off: two flag tests.
    FlPlan fl_plan;
    fl_plan_buffer(ib, num_dwords, kind, qring, chain, *maps_p, opt.drop_offsets, fl_plan);
""")
BUILD_BLOCK = tabs(r"""    // Experiment 0404 (BC5_DIRECT_FL_CRUMBS): the copy with the crumbs around the planned draws (fl_build; the buffer's own
    // COND_EXEC counts grown as the mec rebuild above grows them), the drop and kept-wait offsets mapped into it; fl_back
    // maps the executed offsets back to the buffer's own, as mec_back does. The probes get the buffer without the crumbs.
    std::vector<uint32_t> fl_ib, fl_new_to_old;
    if (!fl_plan.draws.empty()) fl_after(ib, num_dwords, kind, n, mec_expand_ib, fl_plan, opt, fl_ib, fl_new_to_old);
    if (!fl_ib.empty()) {
        sub_ib = fl_ib.data();
        sub_n  = static_cast<uint32_t>(fl_ib.size());
    }
    auto fl_back = [&fl_new_to_old](std::vector<uint32_t>& offsets) {
        if (fl_new_to_old.empty()) return;
        std::vector<uint32_t> back;
        back.reserve(offsets.size());
        for (const uint32_t o: offsets) {
            if (o < fl_new_to_old.size() && fl_new_to_old[o] != ~0u) back.push_back(fl_new_to_old[o]);
        }
        offsets.swap(back);
    };
""")
MAPPED_OLD = b"\topt.mapped = [&maps_p](uint64_t a, uint64_t bytes) {\n"
MAPPED_NEW = tabs(r"""    // Experiment 0404: with BC5_DIRECT_FL_CRUMBS the crumbs' area of the GDS shadow passes the operand check (fl_crumbs_area()
    // is 0 when the switch is off: one compare per operand).
    const uint64_t fl_area = fl_crumbs_area();
    opt.mapped = [&maps_p, fl_area](uint64_t a, uint64_t bytes) {
        if (fl_area != 0 && a >= fl_area && a + bytes <= fl_area + kFlAreaBytes) return true; // experiment 0404
""")
SUBMIT1 = b"\tauto r = g_dev->submit(std::span<const uint32_t>(sub_ib, sub_n), opt, 2'000'000'000ull, true, qring);\n\tmec_back(r.executed_offsets);\n"
SUBMIT2 = b"\t\tr       = g_dev->submit(std::span<const uint32_t>(sub_ib, sub_n), opt, 2'000'000'000ull, true, qring);\n\t\tmec_back(r.executed_offsets);\n"
SYNC_PROBE_OLD = b"\tif (r.timed_out) timeout_probe(sub_ib, sub_n, kind, g_submits.load(), &r.executed_offsets); // experiment 0160\n"
SYNC_PROBE_NEW = (b"\tif (r.timed_out && fl_plan.crumbs) fl_probe(fl_plan, n, kind, true); // experiment 0404: first, before the long probe\n"
                  b"\tif (r.timed_out) timeout_probe(fl_ib.empty() ? sub_ib : ib, fl_ib.empty() ? sub_n : num_dwords, kind, g_submits.load(), &r.executed_offsets); // experiment 0160 (+ exp 0404: the buffer without the crumbs, as the offsets)\n")
COPY_OLD = b"\t\tif (BC5_DIAG_ENV(\"BC5_DIRECT_TIMEOUT_PROBE\") != nullptr) { it.job.ib_copy.assign(sub_ib, sub_ib + sub_n); it.job.ran_copy = r.executed_offsets; } // experiment 0160\n"
COPY_NEW = (b"\t\tif (BC5_DIAG_ENV(\"BC5_DIRECT_TIMEOUT_PROBE\") != nullptr) { if (fl_ib.empty()) it.job.ib_copy.assign(sub_ib, sub_ib + sub_n); else it.job.ib_copy.assign(ib, ib + num_dwords); "
            b"it.job.ran_copy = r.executed_offsets; } // experiment 0160 (+ exp 0404: without the crumbs)\n")
CQ_PROBE = b"\t\t\tif (r.timed_out && !j.ib_copy.empty()) timeout_probe(j.ib_copy.data(), static_cast<uint32_t>(j.ib_copy.size()), j.kind, j.n, &j.ran_copy, &j.ge_probe); // experiment 0160\n"

EDITS = (
    (b"// ---- experiment 0024: jobs in flight ---------------------------------------------------------\n", FL_SCAN + FL_GLUE, "before"),
    (b"\tstd::vector<CatchSlot>   catch_slots; // experiment 0401 series e: the table catcher's slots\n",
     b"\tFlPlan                   fl_plan;     // experiment 0404: the fast-launch draws' crumbs, for fl_probe\n", "after"),
    (MAPPED_OLD, MAPPED_NEW, "replace"),
    (b"\t// Experiment 0038, BC5_DIRECT_OPS_DUMP=<n>: the opcode sequence (offset:op[/event or\n", SCAN_CALL, "before"),
    (b"\tauto mec_back = [&mec_new_to_old](std::vector<uint32_t>& offsets) {\n", BUILD_BLOCK, "before"),
    (SUBMIT1, b"\tfl_back(r.executed_offsets); // experiment 0404\n", "after"),
    (SUBMIT2, b"\t\tfl_back(r.executed_offsets); // experiment 0404\n", "after"),
    (SYNC_PROBE_OLD, SYNC_PROBE_NEW, "replace"),
    (COPY_OLD, COPY_NEW, "replace"),
    (b"\t\tit.job.catch_slots.swap(catch_slots); // experiment 0401 series e\n", b"\t\tit.job.fl_plan = std::move(fl_plan); // experiment 0404\n", "after"),
    (CQ_PROBE, b"\t\t\tif (r.timed_out && j.fl_plan.crumbs) fl_probe(j.fl_plan, j.n, j.kind, g_dev && j.dev_gen == g_dev_gen.load()); // experiment 0404: first, before the long probe\n", "before"),
)


def apply_edits(s, edits):
    for anchor, text, where in edits:
        assert s.count(anchor) == 1, ("anchor", anchor[:70], s.count(anchor))
        new = {"before": text + anchor, "after": anchor + text, "replace": text}[where]
        s = s.replace(anchor, new)
    return s


def edit(s):
    assert MARK not in s and b"fl_scan" not in s and b"FlPlan" not in s, "the unit has exp 0404's switches already"
    assert b"\r\n" not in s, "the unit has CRLF line endings: not the e3 unit"
    # The crumbs' area of the GDS shadow is free (fl0401-notes.md): the unit never redirects GDS into the shadow, and the
    # shadow's only other user is the GE probe at +0xc000 (512 slots of 32 bytes, to +0x10000).
    assert s.count(b"opt.gds_shadow_va") == 0 and s.count(b"gds_shadow_va =") == 0, "the unit redirects GDS into the shadow now: look again"
    assert s.count(b"gds_shadow_va()") == 5 and s.count(b"gds_shadow_cpu()") == 2, "a new user of the GDS shadow: check +0x8000..+0xa100"
    assert s.count(b"static constexpr uint64_t                   kGeProbeOff      = 0xc000; // byte offset in the 64 KiB shadow\n") == 1
    assert s.count(b"static constexpr uint32_t                   kGeProbeSlots    = 512;    // 32 bytes each\n") == 1
    # submit_now's locals the blocks use: sub_ib / sub_n are not const, n is the submission's number
    assert s.count(b"\tconst uint32_t*       sub_ib = ib;\n\tuint32_t              sub_n  = num_dwords;\n") == 1
    assert s.count(b"\tconst uint64_t n = g_submits.fetch_add(1);\n\t// Crash journal:") == 1
    out = apply_edits(s, EDITS)
    assert out.count(FL_SCAN) == 1 and out.count(FL_GLUE) == 1
    assert out.count(b"fl_plan_buffer(") == 2 and out.count(b"fl_after(") == 2 and out.count(b"fl_probe(") == 3
    assert out.count(b"fl_back(r.executed_offsets); // experiment 0404\n") == 2
    # order in submit_now: the walk, the scan, n, the mec rebuild, the crumbs, the submit, the probe
    i_scan, i_n = out.index(b"\tfl_plan_buffer(ib, num_dwords"), out.index(b"\tconst uint64_t n = g_submits.fetch_add(1);\n\t// Crash journal:")
    i_mec, i_after = out.index(b"\tstd::vector<uint32_t> mec_ib;\n"), out.index(b"fl_after(ib, num_dwords, kind, n,")
    i_submit, i_probe = out.index(SUBMIT1), out.index(b"\tif (r.timed_out && fl_plan.crumbs) fl_probe(")
    assert out.index(b"const uint64_t fl_area = fl_crumbs_area();") < i_scan < i_n < i_mec < i_after < i_submit < i_probe
    assert out.index(b"struct FlPlan {") < out.index(b"struct PendingJob {") < out.index(b"FlPlan                   fl_plan;")
    return out


def main():
    assert len(sys.argv) == 4, __doc__
    with open(sys.argv[1], "rb") as f:
        s = f.read()
    if hashlib.md5(s).hexdigest() != E3_MD5:
        print(f"mkfl0401: note: the unit is not series e3's ({E3_MD5}); the anchors decide", file=sys.stderr)
    out = edit(s)
    os.makedirs(sys.argv[3], exist_ok=True)
    with open(os.path.join(sys.argv[3], "fl_scan.inc"), "wb") as f:
        f.write(FL_SCAN)
    with open(sys.argv[2], "wb") as f:
        f.write(out)
    print(hashlib.md5(out).hexdigest())


if __name__ == "__main__":
    main()
