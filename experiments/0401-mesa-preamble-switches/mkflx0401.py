#!/usr/bin/env python3
"""BC5 experiment 0401 series e7, tag "flx": five default-off switches for the fast-launch draw-class hang (19:54 and
22:54; hang1954-0401.md "Proposed switches" A1, F1, F2 and section A3's A4/A5), as one edit of src/libs/bc5LleAgc.cpp's
exp 0404 block (the crumbs: fl_scan, fl_build, fl_plan_buffer, fl_after, fl_probe). flx0401-notes.md has the design, the
packets with their sources, the costs and the risks.
  BC5_DIRECT_FL_PROBE_STATE=1                    A1 catcher (CPU, at a fence timeout): the tracked NGG state and all GS/ES
                                                 user data of the first draw issued and not done and of the last done one,
                                                 and the next draw's ring entry; journal lines only
  BC5_DIRECT_FL_VGT_FLUSH=prefix|transition|all  F1 fix candidate: EVENT_WRITE VS_PARTIAL_FLUSH + VGT_FLUSH (at host prefix
                                                 heads / before a fast-launch draw after other work / before every one)
  BC5_DIRECT_FL_SERIAL=1                         F2 fix candidate: EVENT_WRITE VS_PARTIAL_FLUSH after every fast-launch draw
  BC5_DIRECT_FL_MESHLET_PROBE=1                  A4 catcher (CPU, at a fence timeout): the meshlet control path of every draw
                                                 issued and not done, per point, counts only (host mapping reads, ~2 s late)
  BC5_DIRECT_FL_CRUMBS_MESHLET=1                 A5 catcher: the crumbs copy point 0's object record and meshlet headers
                                                 (addresses computed by the CPU at submit) instead of the V# bases' bytes
Unset, every switch leaves exp 0404's path exactly as it is (no packet, no copy, no extra tracking).
Unit (one input): src/libs/bc5LleAgc.cpp, series e6's d1cfd9bb; the e7 chain runs zsk, lzr, cap, then this script, and
re-pins PINNED below (one dict). Every edit lies in the exp 0404 block (from "// ---- experiment 0404 (in exp 0401's unit):
fast-launch draw crumbs and skip, the pure part" to fl_probe's end), except three exp 0404 lines in submit_now and the
completion thread (the fl_after call, the two fl_probe calls). Each replaced unit is pinned by its own md5 too, so a change
by another script in the chain stops this one.
Functions and structs touched: FlState, fl_merge_state, FlDraw, FlPlan, FlOptions, fl_scan, fl_build (pure part);
fl_plan_buffer, fl_after, fl_probe (host side); submit_now (the fl_after line, a line after the sync fl_probe call);
completion_thread (a line after its fl_probe call). New: the flx block before FlState (constants, kFlx* register table,
flx_index/_off/_set/_range/_covers/_forget, flx_pattern, flx_mesh_point, flx_mesh_counts, flx_user_data, flx_v6,
fl_vgt_flush, fl_vs_flush), flx_plan_ml after FlOptions, the late pure block before exp 0404's end marker (flx_parse_flush,
flx_heads, flx_next_draw, flx_entry_reading, flx_fmt, flx_state_lines, flx_mesh_line), the host block after the g_fl_*
counters (FlxSwitches, flx_switches, flx_note, fl_keep_done, flx_kept, flx_probe_state, flx_probe_kept, flx_probe_ml,
flx_probe_mesh) and the CPU test's seams bc5_flx0401_* after fl_probe (always compiled in, never called by the emulator).
Every anchor must occur exactly once (in its function where it has one); a unit that has the edit already is refused; each
edit keeps braces, parentheses and brackets balanced outside comments and literals; the inserted text is ASCII; LF line
ends. After editing, the script undoes its edits on the output and asserts that this gives the input back byte for byte.
Prints "src/libs/bc5LleAgc.cpp <md5>". CPU test: flx0401.cpp (--gate flx0401.cpp <out> --like src/libs/bc5LleAgc.cpp).
usage: mkflx0401.py <tree root in> <out dir>"""
import hashlib
import os
import sys

REL = "src/libs/bc5LleAgc.cpp"
PINNED = {  # input md5 of the unit this script edits (series e6's; the top session re-pins it after zsk, lzr and cap)
    REL: "bcbdd3082bf5371393989bb69b1f76fa",  # e7 chain: d1cfd9bb + zsk + lzr + cap
}

MARKS = (b"BC5_DIRECT_FL_VGT_FLUSH", b"bc5_flx0401_", b"(tag flx)")
REGION = (b"// ---- experiment 0404 (in exp 0401's unit): fast-launch draw crumbs and skip, the pure part",
          b"// ---- experiment 0024: jobs in flight")


def tabs(text):
    """The C++ below is written with 4-space indents; the unit indents with tabs."""
    out = []
    for line in text.split("\n"):
        body = line.lstrip(" ")
        k = len(line) - len(body)
        out.append("\t" * (k // 4) + " " * (k % 4) + body)
    return "\n".join(out).encode("ascii")


# =====================================================================================================================
# The flx block before FlState: constants, the register table, the meshlet path (pure).
FLX_DECL = tabs(r"""// ---- exp 0401 series e7 (tag flx): F1/F2 flushes and the A1/A4/A5 catchers, the pure part ----------------------------
// mkflx0401.py adds this and the edits marked "flx" to exp 0404's pure part (flx0401-notes.md; CPU test flx0401.cpp through
// the seams bc5_flx0401_*). Five switches, each off by default and read once (bc5::env_on: unset, empty and "0" are off;
// with all five unset this is exp 0404's path exactly):
//   BC5_DIRECT_FL_PROBE_STATE=1                    A1 catcher, CPU at a fence timeout: fl_probe also prints kFlx*'s registers
//                                                  as fl_scan tracked them at the first draw issued and not done and at the
//                                                  last done one, and the ring entry of the next draw with crumbs
//   BC5_DIRECT_FL_VGT_FLUSH=prefix|transition|all  F1 fix candidate: EVENT_WRITE VS_PARTIAL_FLUSH, then EVENT_WRITE VGT_FLUSH:
//                                                  at the head of every host prefix of a dcb (prefix), before a fast-launch
//                                                  draw whose last work before it may be other work (transition: a draw that
//                                                  is not fast-launch, a dispatch, or not known), or before every fast-launch
//                                                  draw (all)
//   BC5_DIRECT_FL_SERIAL=1                         F2 fix candidate: EVENT_WRITE VS_PARTIAL_FLUSH after every fast-launch draw:
//                                                  the next draw starts after its geometry waves are done
//   BC5_DIRECT_FL_MESHLET_PROBE=1                  A4 catcher, CPU at a fence timeout: the meshlet control path of every draw
//                                                  issued and not done, followed for each point, counts only
//   BC5_DIRECT_FL_CRUMBS_MESHLET=1                 A5 catcher: a pattern draw's three 32-byte crumb copies are its point 0's
//                                                  object record and meshlet headers instead of the V# bases' bytes
// A1, A4 and A5 extend the crumbs (BC5_DIRECT_FL_CRUMBS=1) and do nothing without them; F1 and F2 work with or without.
// "Fast-launch" is the crumbs' set, a planned draw of class 3, 2 or 0 (fl_class): a two-valued or unknown state gets the
// flushes too (they change timing, not results).
// The packets go into the draw's own unit of fl_build's copy, as the crumbs do: a COND_EXEC range grows by them and skips
// them with the draw, and the backend's draw check still lands right before the draw. Around a draw: [F1] [crumbs: head,
// copies, tail, issued] <draw> [crumbs: done] [F2].
//   EVENT_WRITE  PKT3(0x46, 0) = 0xC0004600 (backend/src/indirect_check.cpp kEventWrite, the form of exp 0380's args_flush,
//                which ran on this ring; Mesa src/amd/common/sid.h:129 PKT3_EVENT_WRITE @ ab2374a) and one dword: EVENT_TYPE
//                bits 5:0 (gfx10.json VGT_EVENT_INITIATOR.EVENT_TYPE) | EVENT_INDEX bits 11:8 (indirect_check.cpp
//                kCsPartialFlush; the title's own CS_PARTIAL_FLUSH 0x407). VS_PARTIAL_FLUSH is event 15 with index 4,
//                VGT_FLUSH event 36 with index 0 (gfx10.json VGT_EVENT_TYPE; the index as Mesa ac_cmdbuf.h:396-405 picks it,
//                sid.h:131-137 "4 - *S_PARTIAL_FLUSH"). The policy passes 0x46 (backend/policy/pm4-policy.tsv).
//   F1           VS_PARTIAL_FLUSH, VGT_FLUSH: Mesa's pair and order in ac_shadowed_regs.c:2984-2989 ("Wait for idle, because
//                we'll update VGT ring pointers." / "VGT_FLUSH is required even if VGT is idle. It resets VGT pointers.") and
//                radv_queue.c:1050-1052 @ ab2374a, and si_state_shaders.cpp:3622-3628 @ 0866ae7 (hang1954-0401.md)
//   F2           VS_PARTIAL_FLUSH alone: the ME waits until the geometry waves before it are done (Mesa ac_barrier.c:270-281
//                @ ab2374a: on GFX10 it, and not PS_PARTIAL_FLUSH, waits for GS waves that send "gs_alloc_req 0").
//                TODO(verify) its completion point on gfx1013.
constexpr uint32_t kFlEventWrite = 0xC0004600u;      // PKT3(EVENT_WRITE, 0, 0)
constexpr uint32_t kFlVsPartial  = 15u | (4u << 8u); // VS_PARTIAL_FLUSH, EVENT_INDEX 4
constexpr uint32_t kFlVgtFlush   = 36u;              // VGT_FLUSH, EVENT_INDEX 0
constexpr uint32_t kFlxMeshCap   = 4096;             // A4: points followed per draw at most
static void fl_vgt_flush(std::vector<uint32_t>& out) { // F1: 4 dwords
    out.insert(out.end(), {kFlEventWrite, kFlVsPartial, kFlEventWrite, kFlVgtFlush});
}
static void fl_vs_flush(std::vector<uint32_t>& out) { // F2: 2 dwords
    out.insert(out.end(), {kFlEventWrite, kFlVsPartial});
}
// kFlx*: the registers A1 prints and A4/A5 read, tracked in FlState::x while one of them is on (Mesa src/amd/registers/
// gfx10.json @ fe554882, vendored in tools/bc5-agc/regdb: the byte address minus 0x28000 (context), 0xb000 (SH) or 0x30000
// (uconfig), over 4). x holds the context ones, the uconfig ones, then two runs of SH registers. Written by the packets
// fl_scan follows for its own registers, plus SET_UCONFIG_REG(_INDEX) 0x79/0x7a and LOAD_UCONFIG_REG(_INDEX) 0x5e/0x64 for
// the uconfig ones (backend/src/full_state.cpp reads them so; the policy passes them); CLEAR_STATE treats the context ones
// as it treats VGT_SHADER_STAGES_EN (full_state.cpp: the context space only).
constexpr uint32_t kFlxCtx = 12, kFlxUc = 5, kFlxShA = 36, kFlxShB = 18;
constexpr uint32_t kFlxUcAt = kFlxCtx, kFlxShAAt = kFlxUcAt + kFlxUc, kFlxShBAt = kFlxShAAt + kFlxShA, kFlxN = kFlxShBAt + kFlxShB;
constexpr uint32_t kFlxShAFirst = 0x88u; // SPI_SHADER_PGM_LO_GS 0xb220, _HI_GS, _RSRC1_GS 0xb228, _RSRC2_GS 0xb22c, then
                                         // SPI_SHADER_USER_DATA_GS_0..31 0xb230..0xb2ac
constexpr uint32_t kFlxShBFirst = 0xcau; // SPI_SHADER_PGM_RSRC1_ES 0xb328, _RSRC2_ES 0xb32c, then SPI_SHADER_USER_DATA_ES_0..15
                                         // 0xb330..0xb36c (gfx10.json has ES_0..15)
constexpr uint32_t kFlxGsUd = kFlxShAAt + 4u, kFlxEsUd = kFlxShBAt + 2u; // the x index of USER_DATA_GS_0 / USER_DATA_ES_0
struct FlxReg {
    uint32_t    off;
    const char* name;
};
constexpr FlxReg kFlxCtxRegs[kFlxCtx] = {{0x1ffu, "GE_MAX_OUTPUT_PER_SUBGROUP"}, {0x2ceu, "VGT_GS_MAX_VERT_OUT"}, {0x29bu, "VGT_GS_OUT_PRIM_TYPE"},
                                         {0x291u, "VGT_GS_ONCHIP_CNTL"}, {0x2d3u, "GE_NGG_SUBGRP_CNTL"}, {0x2abu, "VGT_ESGS_RING_ITEMSIZE"},
                                         {0x290u, "VGT_GS_MODE"}, {0x2e4u, "VGT_GS_INSTANCE_CNT"}, {0x20eu, "PA_CL_NGG_CNTL"},
                                         {0x1c2u, "SPI_SHADER_IDX_FORMAT"}, {0x1c3u, "SPI_SHADER_POS_FORMAT"}, {0x2a6u, "VGT_DRAW_PAYLOAD_CNTL"}};
constexpr FlxReg kFlxUcRegs[kFlxUc] = {{0x242u, "VGT_PRIMITIVE_TYPE"}, {0x25bu, "GE_CNTL"}, {0x262u, "GE_USER_VGPR_EN"}, {0x25cu, "GE_USER_VGPR1"}, {0x260u, "GE_PC_ALLOC"}};
constexpr uint32_t kFlxUserVgprEn = kFlxUcAt + 2u, kFlxUserVgpr1 = kFlxUcAt + 3u;
static int flx_index(int space, uint32_t r) { // space 0 context, 1 SH, 2 uconfig: r's index in x, or -1
    if (space == 1) {
        if (r - kFlxShAFirst < kFlxShA) return static_cast<int>(kFlxShAAt + (r - kFlxShAFirst));
        if (r - kFlxShBFirst < kFlxShB) return static_cast<int>(kFlxShBAt + (r - kFlxShBFirst));
        return -1;
    }
    if (space == 0 && r - 0x1c2u <= 0x2e4u - 0x1c2u) {
        for (uint32_t k = 0; k < kFlxCtx; k++) {
            if (kFlxCtxRegs[k].off == r) return static_cast<int>(k);
        }
    } else if (space == 2 && r - 0x242u <= 0x262u - 0x242u) {
        for (uint32_t k = 0; k < kFlxUc; k++) {
            if (kFlxUcRegs[k].off == r) return static_cast<int>(kFlxUcAt + k);
        }
    }
    return -1;
}
static uint32_t flx_off(uint32_t i, int& space) { // the register at x index i, and its space
    if (i < kFlxUcAt) {
        space = 0;
        return kFlxCtxRegs[i].off;
    }
    if (i < kFlxShAAt) {
        space = 2;
        return kFlxUcRegs[i - kFlxUcAt].off;
    }
    space = 1;
    return i < kFlxShBAt ? kFlxShAFirst + (i - kFlxShAAt) : kFlxShBFirst + (i - kFlxShBAt);
}
static void flx_set(std::vector<FlVal>& x, int space, uint32_t r, uint32_t v) { // no-op while x is not tracked (empty)
    if (x.empty()) return;
    if (const int i = flx_index(space, r); i >= 0) x[static_cast<std::size_t>(i)] = fl_val(v);
}
// registers [first, first + count) of space from t; t == nullptr: unreadable, unknown
static void flx_range(std::vector<FlVal>& x, int space, uint32_t first, uint32_t count, const uint32_t* t) {
    for (uint32_t i = 0; i < x.size(); i++) {
        int            sp = 0;
        const uint32_t r  = flx_off(i, sp);
        if (sp == space && r - first < count) x[i] = t != nullptr ? fl_val(t[r - first]) : FlVal {};
    }
}
static bool flx_covers(const std::vector<FlVal>& x, int space, uint32_t first, uint32_t count) {
    for (uint32_t i = 0; i < x.size(); i++) {
        int            sp = 0;
        const uint32_t r  = flx_off(i, sp);
        if (sp == space && r - first < count) return true;
    }
    return false;
}
static void flx_forget(std::vector<FlVal>& x, int space) {
    for (uint32_t i = 0; i < x.size(); i++) {
        int sp = 0;
        flx_off(i, sp);
        if (sp == space) x[i] = FlVal {};
    }
}
// A4/A5: the meshlet control path of the fast-launch ES programs hang1954-0401.md section A3 read (findings only; no code
// here): pattern 1 is ES 0x11d01345, pattern 2 ES 0x11d00f85 and 0x11d00f8d. User data k is the merged shader's s[8 + k]
// (A3; Mesa radv_shader_args.c:617). One point per input vertex (Mesa radv_shader_info.c:775-784 @ ab2374a: "drawing 1
// input vertex ~ launching 1 mesh shader workgroup"; ac_nir_lower_ngg_mesh.c:603-611: with FAST_LAUNCH=1 the zero-based
// vertex id is the workgroup's index). The group's first thread reads, in this order:
//   the path flag at +0 of the V# in user data path_ud..+3. Not 0: the start at +4, then the index buffer (the V# at +0x540
//   of the table V# in user data table_ud..+3, 32-bit typed loads): e = ib[ib[start] + point], object = e >> 16,
//   meshlet = e & 0xffff. 0: object = user data base_ud + v6, meshlet = point
//   the object's record index: 32 bits at (object << 4) + entry_off of the V# in user data 0..3
//   the object record: the V# at table +0x620, at (record index << 6) & 0xffffc0: +0x1c flags (bit 6 clear: s_trap 1),
//   +0x18 meshlet count (meshlet >= count: s_trap 1), +0x14 header base
//   the meshlet header: the V# at table +0x5a0, at (meshlet << 2) + header base: primitives bits 31:24 + 1, vertices bits
//   23:17 + 1, the GS_ALLOC_REQ counts
// v5 is the vertex id and v6 the first user VGPR (Mesa radv_shader_args.c:327-331 and 861-865 @ ab2374a: GFX10 NGG/mesh
// input VGPRs v0-v4, then vertex_id, user VGPR, user VGPR, instance_id); flx takes v6 = GE_USER_VGPR1 when GE_USER_VGPR_EN
// bit 0 is set and 0 otherwise: TODO(verify) both. A V# is read as exp 0297 reads a gfx10 buffer resource (dword 0
// base[31:0], dword 1 base[47:32] and STRIDE bits 29:16, dword 2 NUM_RECORDS, in bytes when STRIDE is 0; TODO(verify) the
// positions): a scalar load at offset o reads base + o, a typed load of element i base + i * STRIDE. A load past
// NUM_RECORDS (bytes for a scalar load, elements for a typed one) is taken as 0 and counted: TODO(verify) the hardware's
// range check and that it returns 0.
struct FlxPattern {
    uint32_t objtab_ud, entry_off, path_ud, table_ud, base_ud;
};
constexpr FlxPattern kFlxPatterns[3] = {{0u, 0u, 0u, 0u, 0u}, {0u, 8u, 12u, 16u, 20u}, {0u, 4u, 8u, 12u, 16u}};
static int flx_pattern(uint64_t es_lo) { // SPI_SHADER_PGM_LO_ES: 1, 2, or 0 (not one of these programs)
    return es_lo == 0x11d01345u ? 1 : (es_lo == 0x11d00f85u || es_lo == 0x11d00f8du) ? 2 : 0;
}
struct FlxMeshPoint {
    bool     ok = false, rec_ok = false; // followed to the header / to the object record's address
    uint32_t path = 0, object = 0, rindex = 0, meshlet = 0, flags = 0, count = 0, hbase = 0, header = 0;
    uint64_t rec = 0, hdr = 0; // the GPU addresses of the object record and of the header
    uint32_t oob = 0;          // loads past NUM_RECORDS, taken as 0
};
// One point's path; ud: user data 0..31. read(address, bytes): the memory, or nullptr. False when a read was refused.
template <class Read>
static bool flx_mesh_point(int pat, const uint32_t* ud, uint32_t v6, uint32_t point, const Read& read, FlxMeshPoint& m) {
    m = FlxMeshPoint {};
    if (pat < 1 || pat > 2) return false;
    const FlxPattern& P       = kFlxPatterns[pat];
    bool              good    = true;
    const auto        base_of = [](const uint32_t* v) { return static_cast<uint64_t>(v[0]) | (static_cast<uint64_t>(v[1] & 0xffffu) << 32u); };
    const auto        sload   = [&](const uint32_t* v, uint32_t off, uint32_t words, uint32_t* out) { // s_buffer_load_dword(x4)
        const uint32_t stride = (v[1] >> 16u) & 0x3fffu;
        const uint64_t extent = stride != 0 ? static_cast<uint64_t>(v[2]) * stride : v[2];
        for (uint32_t k = 0; k < words; k++) out[k] = 0;
        if (static_cast<uint64_t>(off) + 4ull * words > extent) {
            m.oob++;
            return;
        }
        const uint32_t* t = read((base_of(v) + off) & ~3ull, 4ull * words);
        if (t == nullptr) {
            good = false;
            return;
        }
        for (uint32_t k = 0; k < words; k++) out[k] = t[k];
    };
    const auto tload = [&](const uint32_t* v, uint32_t index, uint32_t* out) { // buffer_load_format_x idxen, 32 bits
        const uint32_t stride = (v[1] >> 16u) & 0x3fffu;
        *out                  = 0;
        if (index >= v[2]) {
            m.oob++;
            return;
        }
        const uint32_t* t = read((base_of(v) + static_cast<uint64_t>(index) * stride) & ~3ull, 4);
        if (t == nullptr) {
            good = false;
            return;
        }
        *out = t[0];
    };
    const uint32_t* objtab = ud + P.objtab_ud;
    const uint32_t* path   = ud + P.path_ud;
    const uint32_t* table  = ud + P.table_ud;
    sload(path, 0, 1, &m.path);
    if (m.path != 0) { // the index path
        uint32_t start = 0, ibv[4] = {}, e1 = 0, e2 = 0;
        sload(path, 4, 1, &start);
        sload(table, 0x540u, 4, ibv);
        tload(ibv, start, &e1);
        tload(ibv, e1 + point, &e2);
        m.object  = e2 >> 16u;
        m.meshlet = e2 & 0xffffu;
    } else { // the direct path
        m.object  = ud[P.base_ud] + v6;
        m.meshlet = point;
    }
    uint32_t recv[4] = {}, hdrv[4] = {};
    sload(table, 0x620u, 4, recv);
    sload(table, 0x5a0u, 4, hdrv);
    sload(objtab, (m.object << 4u) + P.entry_off, 1, &m.rindex);
    const uint32_t roff = (m.rindex << 6u) & 0xffffc0u;
    m.rec               = (base_of(recv) + roff) & ~3ull;
    m.rec_ok            = good;
    sload(recv, roff + 0x1cu, 1, &m.flags);
    sload(recv, roff + 0x18u, 1, &m.count);
    sload(recv, roff + 0x14u, 1, &m.hbase);
    const uint32_t hoff = (m.meshlet << 2u) + m.hbase;
    m.hdr               = (base_of(hdrv) + hoff) & ~3ull;
    sload(hdrv, hoff, 1, &m.header);
    m.ok = good;
    return good;
}
struct FlxMeshCounts { // A4's counts for one draw
    uint32_t points = 0, followed = 0, unread = 0, index_path = 0, flag6 = 0, index = 0, over_v = 0, over_p = 0, max_v = 0, max_p = 0, oob = 0;
    int32_t  first_flag6 = -1, first_index = -1, first_over = -1; // the first point of each kind
};
template <class Read>
static FlxMeshCounts flx_mesh_counts(int pat, const uint32_t* ud, uint32_t v6, uint32_t points, uint32_t cap, const Read& read) {
    FlxMeshCounts c;
    c.points = std::min(points, cap);
    for (uint32_t i = 0; i < c.points; i++) {
        FlxMeshPoint m;
        if (!flx_mesh_point(pat, ud, v6, i, read, m)) {
            c.unread++;
            continue;
        }
        c.followed++;
        c.oob += m.oob;
        if (m.path != 0) c.index_path++;
        const uint32_t v = ((m.header >> 17u) & 0x7fu) + 1u, p = (m.header >> 24u) + 1u;
        c.max_v          = std::max(c.max_v, v);
        c.max_p          = std::max(c.max_p, p);
        if ((m.flags & 0x40u) == 0) {
            c.flag6++;
            if (c.first_flag6 < 0) c.first_flag6 = static_cast<int32_t>(i);
        }
        if (m.meshlet >= m.count) {
            c.index++;
            if (c.first_index < 0) c.first_index = static_cast<int32_t>(i);
        }
        if (v > 32u) c.over_v++;
        if (p > 64u) c.over_p++;
        if ((v > 32u || p > 64u) && c.first_over < 0) c.first_over = static_cast<int32_t>(i);
    }
    return c;
}
// user data 0..31 from x; false unless every one pattern pat reads is known for certain
static bool flx_user_data(const std::vector<FlVal>& x, int pat, uint32_t* ud) {
    if (x.size() != kFlxN || pat < 1 || pat > 2) return false;
    const FlxPattern& P  = kFlxPatterns[pat];
    bool              ok = true;
    for (uint32_t k = 0; k < 32; k++) {
        const FlVal& v = x[kFlxGsUd + k];
        ud[k]          = v.n == 1 ? static_cast<uint32_t>(v.v[0]) : 0u;
        const bool used = k - P.objtab_ud < 4u || k - P.path_ud < 4u || k - P.table_ud < 4u || k == P.base_ud;
        if (used && v.n != 1) ok = false;
    }
    return ok;
}
// v6: 0 from GE_USER_VGPR1 (GE_USER_VGPR_EN bit 0 set), 1 zero (bit 0 clear), 2 zero assumed (either not known for certain)
static int flx_v6(const std::vector<FlVal>& x, uint32_t& v6) {
    v6 = 0;
    if (x.size() != kFlxN) return 2;
    const FlVal &en = x[kFlxUserVgprEn], &v1 = x[kFlxUserVgpr1];
    if (en.n != 1) return 2;
    if ((en.v[0] & 1u) == 0) return 1;
    if (v1.n != 1) return 2;
    v6 = static_cast<uint32_t>(v1.v[0]);
    return 0;
}
// ---- end of exp 0401 series e7's (tag flx) first pure block -----------------------------------------------------------
""")

NEW_FLSTATE = tabs(r"""struct FlState { // the GFX context's tracked registers, carried from buffer to buffer
    FlVal              stages, es_lo, es_hi, base1;
    FlVal              ud[6];
    std::vector<FlVal> stack; // VGT_SHADER_STAGES_EN as CLEAR_STATE cmd 1 pushed it (full_state's stack, 8 deep)
    FlVal                           last;   // exp 0401 e7 (flx): the GFX ring's last draw or dispatch: 1 fast-launch, 0 other work
    std::vector<FlVal>              x;      // exp 0401 e7 (flx): kFlx*'s registers, kFlxN once A1, A4 or A5 is on (else empty)
    std::vector<std::vector<FlVal>> xstack; // exp 0401 e7 (flx): x's context registers as CLEAR_STATE cmd 1 pushed them
};
""")

NEW_MERGE = tabs(r"""static void fl_merge_state(FlState& s, const FlState& o) { // s: the taken branch's state, o: what a skip leaves
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
    // exp 0401 e7 (flx): the last work and kFlx*'s registers alike; x's stack follows the stack's depth
    s.last = fl_merge(s.last, o.last);
    if (s.x.size() != o.x.size()) {
        for (FlVal& v: s.x) v = FlVal {};
    } else {
        for (std::size_t k = 0; k < s.x.size(); k++) s.x[k] = fl_merge(s.x[k], o.x[k]);
    }
    if (s.xstack.size() != s.stack.size() || o.xstack.size() != s.xstack.size()) {
        s.xstack.clear();
    } else {
        for (std::size_t k = 0; k < s.xstack.size(); k++) {
            for (std::size_t i = 0; i < s.xstack[k].size() && i < o.xstack[k].size(); i++) s.xstack[k][i] = fl_merge(s.xstack[k][i], o.xstack[k][i]);
        }
    }
}
""")

FLDRAW_MEMBERS = tabs(r"""    bool               flush  = false; // exp 0401 e7 (flx) F1: VS_PARTIAL_FLUSH + VGT_FLUSH before it (before its crumbs)
    bool               serial = false; // exp 0401 e7 (flx) F2: VS_PARTIAL_FLUSH after it (after its done crumb)
    uint32_t           vcount = 0;     // exp 0401 e7 (flx) A4: a DRAW_INDEX_AUTO's count, from its packet
    int32_t            ml     = 0;     // exp 0401 e7 (flx) A5: the pattern whose object record and headers base[] holds (0: V# bases)
    FlxMeshPoint       mp0;            // exp 0401 e7 (flx) A5: point 0's control path as the CPU followed it at submit
    std::vector<FlVal> x;              // exp 0401 e7 (flx) A1, A4: kFlx*'s registers at the draw (empty unless tracked)
""")

FLPLAN_MEMBERS = tabs(r"""    std::vector<uint32_t> heads;                                                     // exp 0401 e7 (flx) F1 prefix: the host prefixes' heads (sorted)
    bool                  inserts = false;                                           // exp 0401 e7 (flx): F1 or F2 has something to lay
    uint32_t              flushes = 0, serials = 0, heads_laid = 0, ml = 0, ml_failed = 0; // exp 0401 e7 (flx): laid; A5 planned, not followed
""")

FLOPTIONS_MEMBERS = tabs(r"""    int                          flush   = 0;       // exp 0401 e7 (flx) F1: 0 off, 1 prefix (the caller's heads), 2 transition, 3 all
    bool                         serial  = false;   // exp 0401 e7 (flx) F2
    bool                         state   = false;   // exp 0401 e7 (flx) A1, A4, A5: track kFlx*'s registers
    bool                         ml      = false;   // exp 0401 e7 (flx) A5: a crumbed pattern draw copies its object record and headers
""")

FLX_PLAN_ML = tabs(r"""// exp 0401 e7 (flx) A5: the crumbs' three 32-byte copies of a pattern draw take point 0's object record (+0x00, +0x20) and
// its meshlet headers (from point 0's header on) instead of the bytes at the V# bases. The CP cannot follow the pointers
// (COPY_DATA copies from the address in its packet), so the addresses are the CPU's reading at submit (flx_mesh_point); the
// probe prints the CPU's reads at submit and now beside the CP's copy. The record alone when the header is not reachable.
// False (the V# bases are copied, as without A5) when the user data it reads are not known for certain or the record's
// address cannot be computed; counted.
template <class Read>
static bool flx_plan_ml(FlDraw& d, const FlState& st, const Read& read, FlPlan& plan) {
    const int    pat    = flx_pattern(st.es_lo.v[0]);
    uint32_t     ud[32] = {}, v6 = 0;
    FlxMeshPoint m;
    flx_v6(st.x, v6);
    if (!flx_user_data(st.x, pat, ud) || (!flx_mesh_point(pat, ud, v6, 0, read, m) && !m.rec_ok)) {
        plan.ml_failed++;
        return false;
    }
    const uint64_t a3[3] = {m.rec, m.rec + 32u, m.ok ? m.hdr : 0u};
    for (uint32_t b = 0; b < 3; b++) {
        if (a3[b] == 0) continue;
        if (const uint32_t* t = read(a3[b], 32 + 4); t != nullptr) { // + 4: the filter's operand check (fl_scan's comment)
            d.base[b] = a3[b];
            for (uint32_t k = 0; k < 8; k++) d.snap[4 + 8 * b + k] = t[k];
        }
    }
    d.ml  = pat;
    d.mp0 = m;
    plan.ml++;
    return true;
}
""")

# ---- fl_scan: snippet edits ----------------------------------------------------------------------------------------
SCAN_SUBS = [
    (tabs(r"""    bool              lost = false; // more than 32 ranges open: nothing is known from there on
"""), tabs(r"""    bool              lost = false; // more than 32 ranges open: nothing is known from there on
    if (o.state && st.x.size() != kFlxN) { // exp 0401 e7 (flx): kFlx*'s registers are tracked from here on, unknown at first
        st.x.assign(kFlxN, FlVal {});
        st.xstack.clear();
    }
""")),
    (tabs(r"""    const auto forget_sh = [&st] {
        st.es_lo = st.es_hi = FlVal {};
        for (FlVal& u: st.ud) u = FlVal {};
    };
    const auto forget_all = [&st, &forget_sh] {
        st.stages = st.base1 = FlVal {};
        st.stack.clear();
        forget_sh();
    };
"""), tabs(r"""    const auto forget_sh = [&st] {
        st.es_lo = st.es_hi = FlVal {};
        for (FlVal& u: st.ud) u = FlVal {};
        flx_forget(st.x, 1); // exp 0401 e7 (flx)
    };
    const auto forget_all = [&st, &forget_sh] {
        st.stages = st.base1 = FlVal {};
        st.stack.clear();
        forget_sh();
        flx_forget(st.x, 0); // exp 0401 e7 (flx): the context and uconfig registers too, and the last work
        flx_forget(st.x, 2);
        st.xstack.clear();
        st.last = FlVal {};
    };
""")),
    (tabs(r"""        const uint32_t  op = (h >> 8u) & 0xffu;
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
"""), tabs(r"""        const uint32_t  op = (h >> 8u) & 0xffu;
        const uint32_t* p  = ib + q;
        bool            ran = true; // exp 0401 e7 (flx): a draw dropped by the caller or by the ES skip is no last work
        if (op == 0x69 && len >= 3) { // SET_CONTEXT_REG
            const uint32_t first = p[1] & 0xffffu;
            if (kFlStages - first < len - 2u) st.stages = fl_val(p[2u + kFlStages - first]);
            flx_range(st.x, 0, first, len - 2u, p + 2); // flx
        } else if ((op == 0x76 || op == 0x9b) && len >= 3) { // SET_SH_REG, SET_SH_REG_INDEX
            const uint32_t first = p[1] & 0xffffu;
            for (uint32_t k = 0; k + 2u < len; k++) {
                if (FlVal* v = fl_sh(st, first + k); v != nullptr) *v = fl_val(p[2u + k]);
                flx_set(st.x, 1, first + k, p[2u + k]); // flx
            }
        } else if ((op == 0x79 || op == 0x7a) && len >= 3) { // flx: SET_UCONFIG_REG, SET_UCONFIG_REG_INDEX (as full_state.cpp reads them)
            flx_range(st.x, 2, p[1] & 0xffffu, len - 2u, p + 2);
        } else if ((op == 0x61 || op == 0x5f || op == 0x5e) && len >= 5) { // LOAD_CONTEXT_REG, LOAD_SH_REG (+ flx: LOAD_UCONFIG_REG)
            const bool     ctx  = op == 0x61;
            const int      sp   = op == 0x61 ? 0 : op == 0x5f ? 1 : 2; // flx: the register space
            const uint64_t base = addr(p[1], p[2]);
            for (uint32_t k = 3; k + 1u < len; k += 2) {
                const uint32_t first = p[k] & 0xffffu, count = p[k + 1u] & 0x3fffu;
                const bool     mine = sp != 2 && covers(ctx, first, count), xs = flx_covers(st.x, sp, first, count);
                if (count == 0 || (!mine && !xs)) continue;
                const uint32_t* t = read(base + static_cast<uint64_t>(first) * 4u, static_cast<uint64_t>(count) * 4u);
                if (t == nullptr) plan.unread++;
                if (mine) load_range(ctx, first, count, t);
                flx_range(st.x, sp, first, count, t); // flx
            }
        } else if ((op == 0x9f || op == 0x63 || op == 0x64) && len >= 5) { // LOAD_CONTEXT_REG_INDEX, LOAD_SH_REG_INDEX (+ flx: LOAD_UCONFIG_REG_INDEX)
            const bool     ctx   = op == 0x9f;
            const int      sp    = op == 0x9f ? 0 : op == 0x63 ? 1 : 2; // flx: the register space
            const uint64_t a     = addr(p[1], p[2]);
            const uint32_t count = p[4] & 0x3fffu;
            if (sp == 2 && st.x.empty()) {
                // flx off: LOAD_UCONFIG_REG_INDEX is not followed, as before
            } else if (count != 0 && (p[3] >> 31u) != 0) { // (offset, value) pairs
                const uint32_t* t = read(a, static_cast<uint64_t>(count) * 8u);
                if (t == nullptr) {
                    plan.unread++;
                    if (ctx) st.stages = FlVal {};
                    else if (sp == 1) forget_sh();
                    flx_forget(st.x, sp); // flx
                } else {
                    for (uint32_t k = 0; k < count; k++) {
                        const uint32_t r = t[2u * k] & 0xffffu;
                        if (ctx) {
                            if (r == kFlStages) st.stages = fl_val(t[2u * k + 1u]);
                        } else if (FlVal* v = sp == 1 ? fl_sh(st, r) : nullptr; v != nullptr) {
                            *v = fl_val(t[2u * k + 1u]);
                        }
                        flx_set(st.x, sp, r, t[2u * k + 1u]); // flx
                    }
                }
            } else if (count != 0) { // count registers from the offset in dword 3
                const uint32_t first = p[3] & 0xffffu;
                const bool     mine  = sp != 2 && covers(ctx, first, count), xs = flx_covers(st.x, sp, first, count);
                if (mine || xs) {
                    const uint32_t* t = read(a, static_cast<uint64_t>(count) * 4u);
                    if (t == nullptr) plan.unread++;
                    if (mine) load_range(ctx, first, count, t);
                    flx_range(st.x, sp, first, count, t); // flx
                }
            }
        } else if (op == 0x12 && len >= 2) { // CLEAR_STATE
            const uint32_t cmd = p[1] & 0xfu;
            if (cmd == 1) {
                if (st.stack.size() < 8) {
                    if (!st.x.empty() && st.xstack.size() == st.stack.size()) st.xstack.emplace_back(st.x.begin(), st.x.begin() + kFlxCtx); // flx
                    else st.xstack.clear();
                    st.stack.push_back(st.stages);
                }
                st.stages = FlVal {};
                flx_forget(st.x, 0); // flx
            } else if (cmd == 2 && !st.stack.empty()) {
                const bool xs = !st.x.empty() && st.xstack.size() == st.stack.size(); // flx
                st.stages     = st.stack.back();
                st.stack.pop_back();
                if (xs) { // flx
                    std::copy(st.xstack.back().begin(), st.xstack.back().end(), st.x.begin());
                    st.xstack.pop_back();
                } else {
                    flx_forget(st.x, 0);
                    st.xstack.clear();
                }
            } else {
                st.stages = FlVal {};
                flx_forget(st.x, 0); // flx
            }
        } else if (op == 0x3f || op == 0x33) { // INDIRECT_BUFFER (_CONST): not followed, it may set anything
""")),
    (tabs(r"""            if (o.drops != nullptr && std::binary_search(o.drops->begin(), o.drops->end(), q)) {
                plan.host_dropped++;
            } else if (cls == 1) {
"""), tabs(r"""            if (o.drops != nullptr && std::binary_search(o.drops->begin(), o.drops->end(), q)) {
                plan.host_dropped++;
                ran = false; // flx
            } else if (cls == 1) {
""")),
    (tabs(r"""                if (cls == 3 && listed) { // certainly fast-launch, and its ES certainly listed
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
"""), tabs(r"""                if (cls == 3 && listed) { // certainly fast-launch, and its ES certainly listed
                    d.drop = true;
                    plan.skipped++;
                    ran = false; // flx
                } else {
                    if (o.crumbs) {
                        d.crumbs = true;
                        plan.planned++;
                        if (fl_is_indirect(op) && len >= 2 && st.base1.n == 1 && st.base1.v[0] != 0) {
                            const uint64_t a = (st.base1.v[0] + p[1]) & ~3ull;
                            if (const uint32_t* t = read(a, 16 + 4); t != nullptr) { // + 4: the filter's operand check, below
                                d.args = a;
                                for (uint32_t k = 0; k < 4; k++) d.snap[k] = t[k];
                            }
                        }
                        // flx A5: a pattern draw's copies are its object record and headers (flx_plan_ml), else the V# bases
                        const bool ml = o.ml && st.es_lo.n == 1 && flx_pattern(st.es_lo.v[0]) != 0 && flx_plan_ml(d, st, read, plan);
                        for (uint32_t b = 0; b < 3 && !ml; b++) {
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
                    // exp 0401 e7 (flx) F1: before a fast-launch draw whose last work may be other work (transition) or before
                    // every one (all); F2: after every one. A1, A4: kFlx*'s registers at the draw, a DRAW_INDEX_AUTO's count
                    // (dword 1, Mesa radv_cmd_buffer.c:11663-11665 @ ab2374a).
                    d.flush  = o.flush == 3 || (o.flush == 2 && fl_test(st.last, [](uint64_t v) { return v == 1; }) != 3);
                    d.serial = o.serial;
                    if (op == 0x2d && len >= 2) d.vcount = p[1];
                    if (!st.x.empty()) d.x = st.x;
                }
                if (d.drop || d.crumbs || d.flush || d.serial) plan.draws.push_back(d);
            }
        }
        if (ran && (fl_is_draw(op) || op == 0x15 || op == 0x16)) { // exp 0401 e7 (flx): the last work, for F1's transition arm
            const int lc = fl_is_draw(op) ? fl_class(st.stages) : 1;     // DISPATCH_DIRECT / _INDIRECT: other work
            st.last      = lc == 3 ? fl_val(1) : lc == 1 ? fl_val(0) : lc == 2 ? fl_merge(fl_val(0), fl_val(1)) : FlVal {};
        }
        q += len;
    }
""")),
]

# ---- fl_build: snippet edits ---------------------------------------------------------------------------------------
BUILD_SUBS = [
    (tabs(r"""    uint32_t              made   = 0;
"""), tabs(r"""    uint32_t              made   = 0, laid = 0; // + exp 0401 e7 (flx): laid counts F1's and F2's packet groups
""")),
    (tabs(r"""        made          = 0;
        std::size_t k = 0;
        for (uint32_t q = 0; q < n;) {
            const uint32_t len = len_at(q);
            unit_at[q]         = static_cast<uint32_t>(out.size());
            while (k < plan.draws.size() && plan.draws[k].at < q) k++;
            FlDraw*    d    = k < plan.draws.size() && plan.draws[k].at == q ? &plan.draws[k] : nullptr;
            const bool with = d != nullptr && d->crumbs && plan.lay.entries != 0;
            if (with) {
"""), tabs(r"""        made          = 0;
        laid          = 0; // flx
        plan.flushes = plan.serials = plan.heads_laid = 0;
        std::size_t k = 0, hk = 0;
        for (uint32_t q = 0; q < n;) {
            const uint32_t len = len_at(q);
            unit_at[q]         = static_cast<uint32_t>(out.size());
            while (k < plan.draws.size() && plan.draws[k].at < q) k++;
            FlDraw*    d    = k < plan.draws.size() && plan.draws[k].at == q ? &plan.draws[k] : nullptr;
            const bool with = d != nullptr && d->crumbs && plan.lay.entries != 0;
            while (hk < plan.heads.size() && plan.heads[hk] < q) hk++;
            if (hk < plan.heads.size() && plan.heads[hk] == q) { // flx F1 prefix: at the head of a host prefix
                fl_vgt_flush(out);
                plan.heads_laid++;
                laid++;
            }
            if (d != nullptr && d->flush) { // flx F1 transition, all: before the draw's crumbs
                fl_vgt_flush(out);
                plan.flushes++;
                laid++;
            }
            if (with) {
""")),
    (tabs(r"""            if (with) fl_post(*d, plan.lay, out);
            q += len;
        }
"""), tabs(r"""            if (with) fl_post(*d, plan.lay, out);
            if (d != nullptr && d->serial) { // flx F2: after the draw's done crumb
                fl_vs_flush(out);
                plan.serials++;
                laid++;
            }
            q += len;
        }
""")),
    (tabs(r"""            if (inside && d.crumbs) {
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
"""), tabs(r"""            if (inside && (d.crumbs || d.flush || d.serial)) { // + flx: its F1 and F2 packets with its crumbs
                d.crumbs    = false;
                d.flush     = false;
                d.serial    = false;
                d.cond_full = true;
                d.id        = 0;
                plan.cond_full++;
                excluded++;
            }
        }
        for (std::size_t j = plan.heads.size(); j-- > 0;) { // flx: a prefix head inside such a range keeps no flush
            bool inside = false;
            for (const auto& [lo, hi]: full) inside = inside || (plan.heads[j] >= lo && plan.heads[j] < hi);
            if (inside) {
                plan.heads.erase(plan.heads.begin() + static_cast<std::ptrdiff_t>(j));
                plan.cond_full++;
                excluded++;
            }
        }
        if (!fitted && excluded == 0) break; // cannot happen: a range grows only by crumbs inside it
    }
    if (!fitted || made + laid == 0) {
        out.clear();
        old_to_new.clear();
        new_to_old.clear();
        for (FlDraw& d: plan.draws) d.crumbs = d.flush = d.serial = false; // + flx
        plan.with_crumbs = 0;
        plan.flushes = plan.serials = plan.heads_laid = 0; // flx
        return 0;
    }
""")),
    (tabs(r"""    plan.with_crumbs = made;
    return made;
"""), tabs(r"""    plan.with_crumbs = made;
    return made + laid; // flx: laid is 0 without F1 and F2
""")),
]

# ---- the late pure block, before exp 0404's end marker ---------------------------------------------------------------
FLX_LATE = tabs(r"""// ---- exp 0401 series e7 (tag flx): the late pure block (after fl_find and fl_entry_check) ------------------------------
// BC5_DIRECT_FL_VGT_FLUSH's value: 1 prefix, 2 transition, 3 all; 0 off (unset, empty, "0", or a value that does not
// parse: *bad then says so and the switch is off)
static int flx_parse_flush(const char* e, bool* bad) {
    *bad = false;
    if (e == nullptr || e[0] == 0 || (e[0] == '0' && e[1] == 0)) return 0;
    if (std::strcmp(e, "prefix") == 0) return 1;
    if (std::strcmp(e, "transition") == 0) return 2;
    if (std::strcmp(e, "all") == 0) return 3;
    *bad = true;
    return 0;
}
// F1 prefix: the heads of the host prefixes in the buffer submit_now got, sorted. With a chain (ADR 0010), each segment's
// that has a prefix (segs: offset in the chain, prefix dwords: ChainSeg::off, ::prefix); without one, the buffer's head
// when it is a dcb (a prefixed piece's prefix starts there; a plain dcb gets one too).
static std::vector<uint32_t> flx_heads(const std::vector<std::pair<uint32_t, uint32_t>>& segs, bool chain, bool dcb, uint32_t n) {
    std::vector<uint32_t> h;
    if (!chain) {
        if (dcb && n != 0) h.push_back(0);
        return h;
    }
    for (const auto& [off, prefix]: segs) {
        if (prefix != 0 && off < n) h.push_back(off);
    }
    std::sort(h.begin(), h.end());
    h.erase(std::unique(h.begin(), h.end()), h.end());
    return h;
}
// A1: the draw with crumbs after the last one issued (fl_find's last, or the one issued when it is done), or -1
static int flx_next_draw(const FlPlan& plan, const FlFind& f) {
    const int from = f.status == 2 ? f.last : f.status == 1 ? f.issued : -1;
    if (from < 0) return -1;
    for (std::size_t k = static_cast<std::size_t>(from) + 1u; k < plan.draws.size(); k++) {
        if (plan.draws[k].crumbs) return static_cast<int>(k);
    }
    return -1;
}
// A1: that draw's ring entry (32 dwords) for its id: 0 complete, 1 begun (as fl_entry_check), 2 another draw of this
// submission (the ring wrapped), 3 never written, 4 an earlier submission's (the head's low dword is another submission's)
static int flx_entry_reading(const uint32_t* e, uint64_t id) {
    const int st = fl_entry_check(e, id);
    if (st != 2) return st;
    return e[0] != static_cast<uint32_t>(id) ? 4 : 2;
}
static void flx_fmt(const FlVal& v, char* out, std::size_t cap) { // "00000020", "00000020|00000040" (one of two), "?"
    if (v.n == 0) std::snprintf(out, cap, "?");
    else if (v.n == 1) std::snprintf(out, cap, "%08x", static_cast<uint32_t>(v.v[0]));
    else std::snprintf(out, cap, "%08x|%08x", static_cast<uint32_t>(v.v[0]), static_cast<uint32_t>(v.v[1]));
}
// A1's lines for kFlx*'s registers as tracked at a draw (without the journal's prefix): context, uconfig, SH, GS user data
// 0-15 and 16-31, ES user data 0-15; one line when they were not tracked
static std::vector<std::string> flx_state_lines(const std::vector<FlVal>& x) {
    std::vector<std::string> out;
    if (x.size() != kFlxN) {
        out.emplace_back("registers: not tracked for this draw (BC5_DIRECT_FL_PROBE_STATE, _MESHLET_PROBE and _CRUMBS_MESHLET were off, or the crumbs, when it was planned)");
        return out;
    }
    char        v[40];
    std::string s = "context:";
    for (uint32_t k = 0; k < kFlxCtx; k++) {
        flx_fmt(x[k], v, sizeof(v));
        s = s + " " + kFlxCtxRegs[k].name + " " + v;
    }
    out.push_back(s);
    s = "uconfig:";
    for (uint32_t k = 0; k < kFlxUc; k++) {
        flx_fmt(x[kFlxUcAt + k], v, sizeof(v));
        s = s + " " + kFlxUcRegs[k].name + " " + v;
    }
    out.push_back(s);
    static const char* const sh_names[6] = {"SPI_SHADER_PGM_LO_GS", "SPI_SHADER_PGM_HI_GS", "SPI_SHADER_PGM_RSRC1_GS", "SPI_SHADER_PGM_RSRC2_GS", "SPI_SHADER_PGM_RSRC1_ES", "SPI_SHADER_PGM_RSRC2_ES"};
    static const uint32_t    sh_at[6]    = {kFlxShAAt, kFlxShAAt + 1u, kFlxShAAt + 2u, kFlxShAAt + 3u, kFlxShBAt, kFlxShBAt + 1u};
    s                                    = "SH:";
    for (uint32_t k = 0; k < 6; k++) {
        flx_fmt(x[sh_at[k]], v, sizeof(v));
        s = s + " " + sh_names[k] + " " + v;
    }
    out.push_back(s);
    const auto run = [&x, &v, &out](const char* name, uint32_t at, uint32_t count) {
        std::string r = name;
        for (uint32_t k = 0; k < count; k++) {
            flx_fmt(x[at + k], v, sizeof(v));
            r = r + " " + v;
        }
        out.push_back(r);
    };
    run("GS user data 0-15:", kFlxGsUd, 16);
    run("GS user data 16-31:", kFlxGsUd + 16u, 16);
    run("ES user data 0-15:", kFlxEsUd, 16);
    return out;
}
// A4's line for one draw (without the journal's prefix). from: where its point count came from; v6_from: flx_v6's answer.
static std::string flx_mesh_line(const FlxMeshCounts& c, int pat, uint32_t es, uint32_t points, uint32_t instances, const char* from, uint32_t v6, int v6_from) {
    static const char* const v6s[3] = {"GE_USER_VGPR1", "GE_USER_VGPR_EN bit 0 clear", "assumed: GE_USER_VGPR_EN or GE_USER_VGPR1 not known"};
    char                     b[1024];
    std::snprintf(b, sizeof(b),
                  "ES %08x (pattern %d), %u x %u points (from %s), %u followed%s: %u read, %u not readable, %u by the index path; record flag bit 6 clear %u (first at point %d), "
                  "meshlet index >= count %u (first %d), headers up to %u vertices and %u primitives, above 32 vertices %u, above 64 primitives %u (first %d), loads past "
                  "NUM_RECORDS %u; v6 %08x (%s); read now, about 2 s after the GPU ran it (the timeout), not at GPU time",
                  es, pat, points, instances, from, c.points, c.points < points ? " (capped)" : "", c.followed, c.unread, c.index_path, c.flag6, c.first_flag6, c.index,
                  c.first_index, c.max_v, c.max_p, c.over_v, c.over_p, c.first_over, c.oob, v6, v6s[v6_from < 0 || v6_from > 2 ? 2 : v6_from]);
    return b;
}
// ---- end of exp 0401 series e7's (tag flx) late pure block -------------------------------------------------------------
""")

# ---- the host's side: after the g_fl_* counters --------------------------------------------------------------------
FLX_GLUE = tabs(r"""// ---- exp 0401 series e7 (tag flx): the switches and the host's side of F1, F2, A1, A4 and A5 -----------------------------
struct FlxSwitches {
    bool probe_state = false, serial = false, meshlet_probe = false, crumbs_meshlet = false;
    int  flush       = 0; // F1: 0 off, 1 prefix, 2 transition, 3 all
};
static const FlxSwitches& flx_switches() {
    static const FlxSwitches s = [] {
        FlxSwitches v;
        v.probe_state    = bc5::env_on(std::getenv("BC5_DIRECT_FL_PROBE_STATE"));
        v.serial         = bc5::env_on(std::getenv("BC5_DIRECT_FL_SERIAL"));
        v.meshlet_probe  = bc5::env_on(std::getenv("BC5_DIRECT_FL_MESHLET_PROBE"));
        v.crumbs_meshlet = bc5::env_on(std::getenv("BC5_DIRECT_FL_CRUMBS_MESHLET"));
        bool bad         = false;
        v.flush          = flx_parse_flush(std::getenv("BC5_DIRECT_FL_VGT_FLUSH"), &bad);
        const bool               crumbs = fl_crumbs_on();
        static const char* const arm[4] = {"off", "prefix", "transition", "all"};
        const char* const        need   = " (needs BC5_DIRECT_FL_CRUMBS=1: nothing without it)";
        char                     line[700];
        std::snprintf(line, sizeof(line), "exp 0401 e7 (flx): fl probe state %s%s, fl vgt flush %s%s, fl serial %s, fl meshlet probe %s%s, fl crumbs meshlet %s%s",
                      v.probe_state ? "on" : "off", v.probe_state && !crumbs ? need : "", arm[v.flush], bad ? " (BC5_DIRECT_FL_VGT_FLUSH does not parse: prefix, transition or all)" : "",
                      v.serial ? "on" : "off", v.meshlet_probe ? "on" : "off", v.meshlet_probe && !crumbs ? need : "", v.crumbs_meshlet ? "on" : "off",
                      v.crumbs_meshlet && !crumbs ? need : "");
        journal("%s\n", line);
        std::fprintf(stderr, "[bc5] %s\n", line);
        return v;
    }();
    return s;
}
static std::atomic<uint64_t> g_flx_flushes {0}, g_flx_heads {0}, g_flx_serials {0}, g_flx_bufs {0}, g_flx_ml {0}, g_flx_ml_failed {0};
// fl_after, once the copy is laid: F1's and F2's packets and A5's draws counted; the first 16 buffers and every 16384th
// journaled, and A5's first 16 draws it could not follow
static void flx_note(const FlPlan& plan, uint64_t submit, const char* kind) {
    if (plan.ml_failed != 0) {
        const uint64_t k = g_flx_ml_failed.fetch_add(plan.ml_failed);
        if (k < 16)
            journal("fl crumbs meshlet (exp 0401 e7 flx A5): submit #%" PRIu64 " %s: %u pattern draws not followed at submit (user data not known for certain, or the record not reachable): their V# bases are copied\n",
                    submit, kind, plan.ml_failed);
    }
    g_flx_ml += plan.ml;
    if (plan.flushes + plan.serials + plan.heads_laid == 0) return;
    const uint64_t f = g_flx_flushes += plan.flushes, h = g_flx_heads += plan.heads_laid, s = g_flx_serials += plan.serials;
    const uint64_t b = g_flx_bufs++;
    if (b < 16 || (b & 0x3fffu) == 0)
        journal("fl vgt flush / serial (exp 0401 e7 flx): submit #%" PRIu64 " %s: %u VS_PARTIAL_FLUSH + VGT_FLUSH before fast-launch draws, %u at host prefix heads, %u VS_PARTIAL_FLUSH after fast-launch draws; so far %" PRIu64 " buffers, %" PRIu64 " / %" PRIu64 " / %" PRIu64 ", A5 %" PRIu64 " draws (%" PRIu64 " not followed)\n",
                submit, kind, plan.flushes, plan.heads_laid, plan.serials, b + 1, f, h, s, g_flx_ml.load(), g_flx_ml_failed.load());
}
// A1: the last draw with crumbs of the job that completed last (by submission number), for a later timeout whose "done"
// names it. One FlDraw; kept only with BC5_DIRECT_FL_PROBE_STATE.
static std::mutex g_flx_kept_mutex;
static FlDraw     g_flx_kept;
static uint64_t   g_flx_kept_n = 0;
static bool       g_flx_kept_any = false;
static void fl_keep_done(const FlPlan& plan, uint64_t n) {
    if (!flx_switches().probe_state || !plan.crumbs) return;
    for (std::size_t k = plan.draws.size(); k-- > 0;) {
        if (!plan.draws[k].crumbs) continue;
        std::lock_guard lk(g_flx_kept_mutex);
        if (!g_flx_kept_any || n >= g_flx_kept_n) {
            g_flx_kept     = plan.draws[k];
            g_flx_kept_n   = n;
            g_flx_kept_any = true;
        }
        return;
    }
}
static bool flx_kept(uint64_t id, FlDraw& d, uint64_t& n) {
    std::lock_guard lk(g_flx_kept_mutex);
    if (!g_flx_kept_any || g_flx_kept.id != id) return false;
    d = g_flx_kept;
    n = g_flx_kept_n;
    return true;
}
static void flx_probe_state(const FlDraw& d) { // A1: kFlx*'s registers at the draw
    for (const std::string& l: flx_state_lines(d.x)) journal("fl crumbs (flx A1):     %s\n", l.c_str());
}
static void flx_probe_kept(uint64_t done) { // A1: the last done draw when it is not this buffer's
    FlDraw   d;
    uint64_t kn = 0;
    if (!flx_kept(done, d, kn)) {
        journal("fl crumbs (flx A1):   the last done (#%u +%u) is neither this buffer's draw nor the last draw with crumbs of the job that completed last: its registers were not kept\n",
                static_cast<uint32_t>(done), static_cast<uint32_t>(done >> 32u));
        return;
    }
    char sg[40], el[40];
    fl_fmt(d.stages, sg, sizeof(sg));
    fl_fmt(d.es_lo, el, sizeof(el));
    journal("fl crumbs (flx A1):   the last done, of submit #%" PRIu64 " (the job that completed last): op %02x at %u (chain segment %d +%u): stages %s, es lo %s\n", kn, d.op, d.at, d.seg,
            d.seg_at, sg, el);
    flx_probe_state(d);
}
static void flx_probe_ml(const FlDraw& d) { // A5: point 0's control path as the CPU followed it at submit
    const FlxMeshPoint& m = d.mp0;
    journal("fl crumbs (flx A5):     point 0 at submit (pattern %d): %s path, object %u, record index %u at 0x%" PRIx64 " (flags %08x, meshlet count %u, header base %08x), meshlet %u, header %08x at 0x%" PRIx64 " (%u vertices, %u primitives), %u loads past NUM_RECORDS%s; the CP copied these addresses, it cannot follow the pointers\n",
            d.ml, m.path != 0 ? "index" : "direct", m.object, m.rindex, m.rec, m.flags, m.count, m.hbase, m.meshlet, m.header, m.hdr, ((m.header >> 17u) & 0x7fu) + 1u, (m.header >> 24u) + 1u, m.oob,
            m.ok ? "" : " (the header was not reachable: the object record only)");
}
// A4: the meshlet control path of a draw issued and not done, for each of its points (at most kFlxMeshCap), through the
// host's mapping of guest memory (covered_sorted), read now: about 2 s after the GPU ran it. e: its ring entry, entry_state
// fl_entry_check's answer (the CP's copy of the arguments counts the points when it is complete).
static void flx_probe_mesh(const FlDraw& d, const uint32_t* e, int entry_state, const std::vector<bc5::direct::Mapping>& maps) {
    char where[48];
    std::snprintf(where, sizeof(where), "op %02x at %u", d.op, d.at);
    if (d.es_lo.n != 1 || flx_pattern(d.es_lo.v[0]) == 0) {
        char el[40];
        fl_fmt(d.es_lo, el, sizeof(el));
        journal("fl crumbs (flx A4):     %s: es lo %s is not 0x11d01345, 0x11d00f85 or 0x11d00f8d for certain: not followed\n", where, el);
        return;
    }
    const int pat    = flx_pattern(d.es_lo.v[0]);
    uint32_t  ud[32] = {}, v6 = 0;
    if (!flx_user_data(d.x, pat, ud)) {
        journal("fl crumbs (flx A4):     %s: the user data it reads were not known for certain at the draw (or not tracked): not followed\n", where);
        return;
    }
    const int   v6_from = flx_v6(d.x, v6);
    uint32_t    points = 0, inst = 0;
    const char* from   = nullptr;
    if (d.op == 0x2d) {
        points = d.vcount;
        inst   = 1;
        from   = "the packet";
    } else if (d.args != 0 && entry_state == 0) {
        points = e[2];
        inst   = e[3];
        from   = "the CP's copy";
    } else if (d.args != 0 && covered_sorted(maps, d.args, 8)) {
        const auto* t = reinterpret_cast<const volatile uint32_t*>(d.args);
        points        = t[0];
        inst          = t[1];
        from          = "memory now";
    }
    if (from == nullptr) {
        journal("fl crumbs (flx A4):     %s: no argument copy or readable arguments to count its points: not followed\n", where);
        return;
    }
    const auto reader = [&maps](uint64_t a, uint64_t bytes) -> const uint32_t* {
        return covered_sorted(maps, a, bytes) ? reinterpret_cast<const uint32_t*>(a) : nullptr;
    };
    const FlxMeshCounts c = flx_mesh_counts(pat, ud, v6, points, kFlxMeshCap, reader);
    journal("fl crumbs (flx A4):     %s: %s\n", where, flx_mesh_line(c, pat, static_cast<uint32_t>(d.es_lo.v[0]), points, inst, from, v6, v6_from).c_str());
}
// ---- end of exp 0401 series e7's (tag flx) host block ------------------------------------------------------------------
""")

# ---- fl_plan_buffer, fl_after, fl_probe: snippet edits --------------------------------------------------------------
PLAN_SUBS = [
    (tabs(r"""    const std::vector<uint32_t>& skip   = fl_skip_es();
    if (!crumbs && skip.empty()) return;
"""), tabs(r"""    const std::vector<uint32_t>& skip   = fl_skip_es();
    const FlxSwitches&           sw     = flx_switches(); // exp 0401 e7 (flx)
    if (!crumbs && skip.empty() && sw.flush == 0 && !sw.serial) return;
""")),
    (tabs(r"""    o.skip_es           = &skip;
"""), tabs(r"""    o.skip_es           = &skip;
    o.flush             = o.draws ? sw.flush : 0;                                              // flx F1 (prefix: the heads below)
    o.serial            = o.draws && sw.serial;                                                // flx F2
    o.state             = crumbs && (sw.probe_state || sw.meshlet_probe || sw.crumbs_meshlet); // flx A1, A4, A5
    o.ml                = o.crumbs && sw.crumbs_meshlet;                                       // flx A5
""")),
    (tabs(r"""        fl_scan(ib, n, reader, g_fl_state, o, plan);
    }
"""), tabs(r"""        fl_scan(ib, n, reader, g_fl_state, o, plan);
    }
    if (o.flush == 1) { // flx F1 prefix: the heads of the host prefixes (flx_heads)
        std::vector<std::pair<uint32_t, uint32_t>> segs;
        if (chain != nullptr) {
            for (const ChainSeg& s: chain->segs) segs.emplace_back(s.off, s.prefix);
        }
        plan.heads = flx_heads(segs, chain != nullptr, std::strcmp(kind, "dcb") == 0, n);
    }
    for (const FlDraw& d: plan.draws) plan.inserts = plan.inserts || d.flush || d.serial; // flx
    plan.inserts = plan.inserts || !plan.heads.empty();
""")),
]

AFTER_SUBS = [
    (tabs(r"""    if (!plan.crumbs || plan.planned == 0) return;
    if (mec_rebuilt) { // a compute buffer's rebuild: never a dcb's; counted, no crumbs
        for (FlDraw& d: plan.draws) d.crumbs = false;
"""), tabs(r"""    if ((!plan.crumbs || plan.planned == 0) && !plan.inserts) return; // + exp 0401 e7 (flx): F1 and F2 lay theirs without crumbs
    if (mec_rebuilt) { // a compute buffer's rebuild: never a dcb's; counted, no crumbs
        for (FlDraw& d: plan.draws) d.crumbs = d.flush = d.serial = false; // + flx
        plan.heads.clear();                                               // flx
""")),
    (tabs(r"""    std::erase(opt.keep_wait_offsets, ~0u);
"""), tabs(r"""    std::erase(opt.keep_wait_offsets, ~0u);
    flx_note(plan, submit, kind);      // exp 0401 e7 (flx): F1's and F2's packets counted
    if (plan.with_crumbs == 0) return; // flx: F1 or F2 without crumbs
""")),
    (tabs(r"""            journal("fl crumbs (exp 0404): submit #%" PRIu64 " %s op %02x at %u (+%u in the copy), entry %u: stages %s es %s, arguments 0x%" PRIx64 ", V# bases 0x%" PRIx64 " 0x%" PRIx64 " 0x%" PRIx64 " (%" PRIu64 " draws so far)\n",
                    submit, kind, d.op, d.at, d.new_at, d.entry, sg, es, d.args, d.base[0], d.base[1], d.base[2], k + 1);
"""), tabs(r"""            journal("fl crumbs (exp 0404): submit #%" PRIu64 " %s op %02x at %u (+%u in the copy), entry %u: stages %s es %s, arguments 0x%" PRIx64 ", V# bases 0x%" PRIx64 " 0x%" PRIx64 " 0x%" PRIx64 "%s (%" PRIu64 " draws so far)\n",
                    submit, kind, d.op, d.at, d.new_at, d.entry, sg, es, d.args, d.base[0], d.base[1], d.base[2], d.ml != 0 ? " (flx A5: the object record +0x00, +0x20 and the meshlet headers instead)" : "", k + 1);
""")),
]

PROBE_SUBS = [
    (tabs(r"""    const auto maps_p = g_dev->sorted_mappings();
    const auto show   = [&](const FlDraw& d, const char* tag, bool with_data) {
        uint32_t                 e[32];
        const volatile uint32_t* ev = sh + (plan.lay.ring - plan.lay.shadow) / 4u + static_cast<std::size_t>(d.entry) * (kFlEntryBytes / 4u);
        for (uint32_t k = 0; k < 32; k++) e[k] = ev[k];
        const int                st       = fl_entry_check(e, d.id);
"""), tabs(r"""    const FlxSwitches& sw     = flx_switches(); // exp 0401 e7 (flx)
    const auto         maps_p = g_dev->sorted_mappings();
    const auto         entry  = [&](const FlDraw& d, uint32_t* e) { // flx: the draw's ring entry as the CP left it, and its state
        const volatile uint32_t* ev = sh + (plan.lay.ring - plan.lay.shadow) / 4u + static_cast<std::size_t>(d.entry) * (kFlEntryBytes / 4u);
        for (uint32_t k = 0; k < 32; k++) e[k] = ev[k];
        return fl_entry_check(e, d.id);
    };
    const auto show = [&](const FlDraw& d, const char* tag, bool with_data, bool regs) { // + flx: regs, A1's registers
        uint32_t                 e[32];
        const int                st       = entry(d, e);
""")),
    (tabs(r"""        if (!with_data) return;
"""), tabs(r"""        if (regs && sw.probe_state) flx_probe_state(d);        // flx A1
        if (d.ml != 0 && (with_data || regs)) flx_probe_ml(d); // flx A5
        if (!with_data) return;
""")),
    (tabs(r"""        one("arguments", d.args, 4, 2, 0);
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
"""), tabs(r"""        one("arguments", d.args, 4, 2, 0);
        if (d.ml != 0) { // flx A5: the copies are point 0's object record and meshlet headers
            one("object record +0x00 (flx A5)", d.base[0], 8, 6, 4);
            one("object record +0x20 (flx A5)", d.base[1], 8, 14, 12);
            one("meshlet headers (flx A5)", d.base[2], 8, 22, 20);
            return;
        }
        one("s[8:9] V# base", d.base[0], 8, 6, 4);
        one("s[20:21] V# base", d.base[1], 8, 14, 12);
        one("s[24:25] V# base", d.base[2], 8, 22, 20);
    };
    if (f.status == 2) {
        if (f.done >= 0) show(plan.draws[static_cast<std::size_t>(f.done)], "the last done", false, true);
        else if (sw.probe_state) flx_probe_kept(done); // flx A1: the last done is an earlier job's
        uint32_t lines = 0;
        for (int k = f.first; k >= 0 && k <= f.last && lines < 64; k++) {
            const FlDraw& d = plan.draws[static_cast<std::size_t>(k)];
            if (!d.crumbs) continue;
            show(d, k == f.first ? "FIRST ISSUED, NOT DONE" : "issued, not done", k == f.first, k == f.first);
            if (sw.meshlet_probe) { // flx A4: every draw issued and not done
                uint32_t  e[32];
                const int st = entry(d, e);
                flx_probe_mesh(d, e, st, *maps_p);
            }
            lines++;
        }
    } else if (f.status == 1) {
        show(plan.draws[static_cast<std::size_t>(f.issued)], "issued last and done", true, true);
    } else if (f.status == 3) {
        show(plan.draws[static_cast<std::size_t>(f.issued)], "issued", false, false);
        show(plan.draws[static_cast<std::size_t>(f.done)], "done", false, false);
    } else {
        for (const FlDraw& d: plan.draws) {
            if (!d.crumbs) continue;
            show(d, "the first draw with crumbs, not issued", true, true);
            break;
        }
    }
    if (sw.probe_state) { // flx A1: the ring entry of the next draw with crumbs after the last one issued
        const int nx = flx_next_draw(plan, f);
        if (nx < 0) {
            journal("fl crumbs (flx A1):   the next draw: none with crumbs after the last one issued in this buffer\n");
        } else {
            static const char* const reading[5] = {
                "complete: the ME passed its copies (it stands at this draw's check or later)", "begun, not finished: the ME stands inside its copies",
                "another draw of this buffer (the ring wrapped): no reading",
                "never written: the ME has not reached its crumbs (it stands in this draw's state loads, or in an F1 flush before them)",
                "an earlier submission's: the ME has not reached its crumbs (it stands in this draw's state loads, or in an F1 flush before them)"};
            const FlDraw& d = plan.draws[static_cast<std::size_t>(nx)];
            uint32_t      e[32];
            entry(d, e);
            journal("fl crumbs (flx A1):   the next draw: op %02x at %u (+%u in the copy), entry %u: head #%u +%u, tail #%u +%u: %s\n", d.op, d.at, d.new_at, d.entry, e[0], e[1], e[30], e[31],
                    reading[flx_entry_reading(e, d.id)]);
        }
    }
""")),
]

# ---- the CPU test's seams, after fl_probe ---------------------------------------------------------------------------
SEAMS = tabs(r"""// ---- exp 0401 series e7 (tag flx): the CPU test's seams (flx0401.cpp); always compiled in, never called by the emulator ----
typedef const uint32_t* (*FlxReadFn)(uint64_t a, uint64_t bytes, void* ctx);
static FlState               g_flx_seam_state; // bc5_flx0401_build's carried state (never the emulator's g_fl_state)
static FlPlan                g_flx_seam_plan;  // its last plan, for the queries below
static std::vector<uint32_t> g_flx_seam_o2n, g_flx_seam_n2o;
constexpr uint32_t           kFlxSeamRec = 20; // dwords per draw in bc5_flx0401_build's rec
extern "C" void bc5_flx0401_switches(int* out) { // the unit's reading: probe state, vgt flush (0..3), serial, meshlet probe, crumbs meshlet, crumbs
    const FlxSwitches& s = flx_switches();
    out[0]               = s.probe_state ? 1 : 0;
    out[1]               = s.flush;
    out[2]               = s.serial ? 1 : 0;
    out[3]               = s.meshlet_probe ? 1 : 0;
    out[4]               = s.crumbs_meshlet ? 1 : 0;
    out[5]               = fl_crumbs_on() ? 1 : 0;
}
extern "C" void bc5_flx0401_consts(uint32_t* out) { // 16 constants
    const uint32_t v[16] = {kFlEventWrite, kFlVsPartial, kFlVgtFlush, kFlxN, kFlxCtx, kFlxUcAt, kFlxShAAt, kFlxShBAt, kFlxGsUd, kFlxEsUd, kFlxUserVgprEn, kFlxUserVgpr1, kFlxMeshCap, kFlEntryBytes, static_cast<uint32_t>(kFlAreaOff), kFlEntries};
    for (uint32_t k = 0; k < 16; k++) out[k] = v[k];
}
extern "C" int bc5_flx0401_index(int space, uint32_t r) {
    return flx_index(space, r);
}
extern "C" const char* bc5_flx0401_name(uint32_t i) { // a named register's name at x index i (nullptr for user data)
    if (i < kFlxUcAt) return kFlxCtxRegs[i].name;
    if (i < kFlxShAAt) return kFlxUcRegs[i - kFlxUcAt].name;
    return nullptr;
}
extern "C" int bc5_flx0401_parse_flush(const char* e, int* bad) {
    bool      b = false;
    const int v = flx_parse_flush(e, &b);
    *bad        = b ? 1 : 0;
    return v;
}
extern "C" uint32_t bc5_flx0401_heads(const uint32_t* segs, uint32_t nseg, int chain, int dcb, uint32_t n, uint32_t* out, uint32_t cap) { // segs: (off, prefix) pairs
    std::vector<std::pair<uint32_t, uint32_t>> s;
    for (uint32_t k = 0; k < nseg; k++) s.emplace_back(segs[2 * k], segs[2 * k + 1]);
    const std::vector<uint32_t> h = flx_heads(s, chain != 0, dcb != 0, n);
    for (std::size_t k = 0; k < h.size() && k < cap; k++) out[k] = h[k];
    return static_cast<uint32_t>(h.size());
}
// fl_scan and fl_build on a buffer of the test's own. opt: [0] crumbs, [1] F1 0..3, [2] F2, [3] state, [4] A5, [5] carry the
// seams' state from the last call (0: start afresh), [6] a dcb (plan its draws), [7] build. info [28]: fl_build's return,
// with_crumbs, flushes, serials, heads_laid, cond_full, total, not_fl, fl, maybe, unknown, skipped, planned, ml, ml_failed,
// draws, the last work's n, v[0], v[1], x's size, the copy's size, unread, ib2, host_dropped, x's stack depth, the stack's
// depth, inserts, heads. rec: kFlxSeamRec dwords per draw: at, op, cls, crumbs, flush, serial, drop, cond_full, new_at,
// entry, ml, vcount, args lo, hi, base[0] lo, hi, base[1] lo, hi, base[2] lo, hi. Returns the draws planned.
extern "C" uint32_t bc5_flx0401_build(const uint32_t* ib, uint32_t n, const uint32_t* opt, const uint32_t* heads, uint32_t nheads, const uint32_t* drops, uint32_t ndrops, const uint32_t* skip,
                                      uint32_t nskip, FlxReadFn read, void* ctx, uint64_t shadow, uint64_t submit, uint32_t* out, uint32_t out_cap, uint32_t* info, uint32_t* rec, uint32_t rec_cap) {
    if (opt[5] == 0) g_flx_seam_state = FlState {};
    const std::vector<uint32_t> dr(drops, drops + ndrops), sk(skip, skip + nskip);
    FlOptions                   o;
    o.crumbs     = opt[0] != 0;
    o.flush      = static_cast<int>(opt[1]);
    o.serial     = opt[2] != 0;
    o.state      = opt[3] != 0;
    o.ml         = opt[4] != 0;
    o.draws      = opt[6] != 0;
    o.skip_es    = &sk;
    o.drops      = &dr;
    FlPlan& plan = g_flx_seam_plan;
    plan         = FlPlan {};
    plan.crumbs  = o.crumbs;
    if (o.crumbs) plan.lay = fl_layout(shadow);
    const auto reader = [read, ctx](uint64_t a, uint64_t bytes) { return read(a, bytes, ctx); };
    fl_scan(ib, n, reader, g_flx_seam_state, o, plan);
    plan.heads.assign(heads, heads + nheads);
    for (const FlDraw& d: plan.draws) plan.inserts = plan.inserts || d.flush || d.serial;
    plan.inserts = plan.inserts || !plan.heads.empty();
    std::vector<uint32_t> copy;
    g_flx_seam_o2n.clear();
    g_flx_seam_n2o.clear();
    uint32_t made = 0;
    if (opt[7] != 0 && (plan.inserts || (plan.crumbs && plan.planned != 0))) made = fl_build(ib, n, plan, submit, copy, g_flx_seam_o2n, g_flx_seam_n2o); // fl_after's condition
    const FlState& st     = g_flx_seam_state;
    const uint32_t v[28] = {made, plan.with_crumbs, plan.flushes, plan.serials, plan.heads_laid, plan.cond_full, plan.total, plan.not_fl, plan.fl, plan.maybe, plan.unknown, plan.skipped,
                            plan.planned, plan.ml, plan.ml_failed, static_cast<uint32_t>(plan.draws.size()), st.last.n, static_cast<uint32_t>(st.last.v[0]),
                            static_cast<uint32_t>(st.last.v[1]), static_cast<uint32_t>(st.x.size()), static_cast<uint32_t>(copy.size()), plan.unread, plan.ib2, plan.host_dropped,
                            static_cast<uint32_t>(st.xstack.size()), static_cast<uint32_t>(st.stack.size()), plan.inserts ? 1u : 0u, static_cast<uint32_t>(plan.heads.size())};
    for (uint32_t k = 0; k < 28; k++) info[k] = v[k];
    for (std::size_t k = 0; k < copy.size() && k < out_cap; k++) out[k] = copy[k];
    for (std::size_t k = 0; k < plan.draws.size() && k < rec_cap; k++) {
        const FlDraw&  d    = plan.draws[k];
        uint32_t*      r    = rec + k * kFlxSeamRec;
        const uint32_t w[kFlxSeamRec] = {d.at, d.op, d.cls, d.crumbs ? 1u : 0u, d.flush ? 1u : 0u, d.serial ? 1u : 0u, d.drop ? 1u : 0u, d.cond_full ? 1u : 0u, d.new_at, d.entry,
                                         static_cast<uint32_t>(d.ml), d.vcount, static_cast<uint32_t>(d.args), static_cast<uint32_t>(d.args >> 32u), static_cast<uint32_t>(d.base[0]),
                                         static_cast<uint32_t>(d.base[0] >> 32u), static_cast<uint32_t>(d.base[1]), static_cast<uint32_t>(d.base[1] >> 32u),
                                         static_cast<uint32_t>(d.base[2]), static_cast<uint32_t>(d.base[2] >> 32u)};
        for (uint32_t i = 0; i < kFlxSeamRec; i++) r[i] = w[i];
    }
    return static_cast<uint32_t>(plan.draws.size());
}
// the last build's offset maps (old to new, n + 1 entries; new to old), as fl_after uses them
extern "C" uint32_t bc5_flx0401_maps(uint32_t* o2n, uint32_t* n2o, uint32_t cap) {
    for (std::size_t k = 0; k < g_flx_seam_o2n.size() && k < cap; k++) o2n[k] = g_flx_seam_o2n[k];
    for (std::size_t k = 0; k < g_flx_seam_n2o.size() && k < cap; k++) n2o[k] = g_flx_seam_n2o[k];
    return static_cast<uint32_t>(g_flx_seam_n2o.size());
}
static uint32_t flx_seam_x(const std::vector<FlVal>& x, uint32_t* ns, uint32_t* v0, uint32_t* v1) {
    for (std::size_t k = 0; k < x.size(); k++) {
        ns[k] = x[k].n;
        v0[k] = static_cast<uint32_t>(x[k].v[0]);
        v1[k] = static_cast<uint32_t>(x[k].v[1]);
    }
    return static_cast<uint32_t>(x.size());
}
static std::vector<FlVal> flx_seam_vals(const uint32_t* ns, const uint32_t* v0, const uint32_t* v1, uint32_t count) {
    std::vector<FlVal> x(count);
    for (uint32_t k = 0; k < count; k++) {
        x[k].n    = ns[k];
        x[k].v[0] = v0[k];
        x[k].v[1] = v1[k];
    }
    return x;
}
extern "C" uint32_t bc5_flx0401_draw_x(uint32_t k, uint32_t* ns, uint32_t* v0, uint32_t* v1) { // the last build's draw k: x
    return k < g_flx_seam_plan.draws.size() ? flx_seam_x(g_flx_seam_plan.draws[k].x, ns, v0, v1) : 0u;
}
extern "C" uint32_t bc5_flx0401_state_x(uint32_t* ns, uint32_t* v0, uint32_t* v1) { // the seams' carried state: x
    return flx_seam_x(g_flx_seam_state.x, ns, v0, v1);
}
extern "C" int bc5_flx0401_draw_mp0(uint32_t k, uint64_t* out) { // the last build's draw k: A5's point 0 (13 values)
    if (k >= g_flx_seam_plan.draws.size()) return 0;
    const FlxMeshPoint& m      = g_flx_seam_plan.draws[k].mp0;
    const uint64_t      v[13] = {m.ok ? 1u : 0u, m.rec_ok ? 1u : 0u, m.path, m.object, m.rindex, m.meshlet, m.flags, m.count, m.hbase, m.header, m.rec, m.hdr, m.oob};
    for (uint32_t i = 0; i < 13; i++) out[i] = v[i];
    return 1;
}
extern "C" uint32_t bc5_flx0401_state_text(const uint32_t* ns, const uint32_t* v0, const uint32_t* v1, uint32_t count, char* out, uint32_t cap) { // A1's lines, '\n' after each
    std::string s;
    for (const std::string& l: flx_state_lines(flx_seam_vals(ns, v0, v1, count))) s += l + "\n";
    std::snprintf(out, cap, "%s", s.c_str());
    return static_cast<uint32_t>(s.size());
}
extern "C" int bc5_flx0401_mesh(uint32_t es, const uint32_t* ud, uint32_t v6, uint32_t points, uint32_t cap, FlxReadFn read, void* ctx, int32_t* out) { // A4's counts (14 values)
    const auto          reader = [read, ctx](uint64_t a, uint64_t bytes) { return read(a, bytes, ctx); };
    const int           pat    = flx_pattern(es);
    const FlxMeshCounts c      = flx_mesh_counts(pat, ud, v6, points, cap, reader);
    const int32_t       v[14]  = {static_cast<int32_t>(c.points), static_cast<int32_t>(c.followed), static_cast<int32_t>(c.unread), static_cast<int32_t>(c.index_path),
                                  static_cast<int32_t>(c.flag6), static_cast<int32_t>(c.index), static_cast<int32_t>(c.over_v), static_cast<int32_t>(c.over_p),
                                  static_cast<int32_t>(c.max_v), static_cast<int32_t>(c.max_p), static_cast<int32_t>(c.oob), c.first_flag6, c.first_index, c.first_over};
    for (uint32_t k = 0; k < 14; k++) out[k] = v[k];
    return pat;
}
extern "C" int bc5_flx0401_mesh_point(uint32_t es, const uint32_t* ud, uint32_t v6, uint32_t point, FlxReadFn read, void* ctx, uint64_t* out) { // one point (13 values)
    const auto   reader = [read, ctx](uint64_t a, uint64_t bytes) { return read(a, bytes, ctx); };
    FlxMeshPoint m;
    const bool   ok    = flx_mesh_point(flx_pattern(es), ud, v6, point, reader, m);
    const uint64_t v[13] = {m.ok ? 1u : 0u, m.rec_ok ? 1u : 0u, m.path, m.object, m.rindex, m.meshlet, m.flags, m.count, m.hbase, m.header, m.rec, m.hdr, m.oob};
    for (uint32_t i = 0; i < 13; i++) out[i] = v[i];
    return ok ? 1 : 0;
}
extern "C" uint32_t bc5_flx0401_mesh_text(uint32_t es, const uint32_t* ud, uint32_t v6, int v6_from, uint32_t points, uint32_t instances, const char* from, FlxReadFn read, void* ctx, char* out,
                                          uint32_t cap) { // A4's line
    const auto          reader = [read, ctx](uint64_t a, uint64_t bytes) { return read(a, bytes, ctx); };
    const int           pat    = flx_pattern(es);
    const FlxMeshCounts c      = flx_mesh_counts(pat, ud, v6, points, kFlxMeshCap, reader);
    const std::string   s      = flx_mesh_line(c, pat, es, points, instances, from, v6, v6_from);
    std::snprintf(out, cap, "%s", s.c_str());
    return static_cast<uint32_t>(s.size());
}
extern "C" int bc5_flx0401_v6(const uint32_t* ns, const uint32_t* v0, const uint32_t* v1, uint32_t count, uint32_t* v6) {
    return flx_v6(flx_seam_vals(ns, v0, v1, count), *v6);
}
extern "C" int bc5_flx0401_user_data(const uint32_t* ns, const uint32_t* v0, const uint32_t* v1, uint32_t count, int pat, uint32_t* ud) {
    return flx_user_data(flx_seam_vals(ns, v0, v1, count), pat, ud) ? 1 : 0;
}
extern "C" int bc5_flx0401_next(const uint32_t* crumbs, uint32_t nd, int status, int issued, int last) { // flx_next_draw on a plan of nd draws
    FlPlan p;
    for (uint32_t k = 0; k < nd; k++) {
        FlDraw d;
        d.crumbs = crumbs[k] != 0;
        p.draws.push_back(d);
    }
    FlFind f;
    f.status = status;
    f.issued = issued;
    f.last   = last;
    return flx_next_draw(p, f);
}
extern "C" int bc5_flx0401_entry_reading(const uint32_t* e, uint64_t id) {
    return flx_entry_reading(e, id);
}
// the real fl_plan_buffer on a buffer of the test's own (GFX ring, no chain, no mapping): info [8] total, draws, with F1,
// with F2, heads, inserts, crumbs, x's size in g_fl_state. Returns the draws planned.
extern "C" uint32_t bc5_flx0401_plan_buffer(const uint32_t* ib, uint32_t n, const char* kind, uint32_t* info) {
    FlPlan                                  plan;
    std::vector<uint32_t>                   drops;
    const std::vector<bc5::direct::Mapping> none;
    fl_plan_buffer(ib, n, kind, bc5::direct::kGfxRing, nullptr, none, drops, plan);
    uint32_t f = 0, s = 0;
    for (const FlDraw& d: plan.draws) {
        f += d.flush ? 1u : 0u;
        s += d.serial ? 1u : 0u;
    }
    uint32_t xs = 0;
    {
        std::lock_guard lk(g_fl_mutex);
        xs = static_cast<uint32_t>(g_fl_state.x.size());
    }
    const uint32_t v[8] = {plan.total, static_cast<uint32_t>(plan.draws.size()), f, s, static_cast<uint32_t>(plan.heads.size()), plan.inserts ? 1u : 0u, plan.crumbs ? 1u : 0u, xs};
    for (uint32_t k = 0; k < 8; k++) info[k] = v[k];
    return static_cast<uint32_t>(plan.draws.size());
}
// the real fl_plan_buffer and fl_after, as submit_now calls them (submission 7): the copy into out, the caller's drop
// offsets (drops, nd) mapped into it in place. info [6]: the copy's size, flushes, serials, heads laid, drops kept, crumbs.
extern "C" uint32_t bc5_flx0401_after(const uint32_t* ib, uint32_t n, const char* kind, uint32_t* drops, uint32_t nd, uint32_t* out, uint32_t cap, uint32_t* info) {
    FlPlan                                  plan;
    bc5::policy::FilterOptions              opt;
    const std::vector<bc5::direct::Mapping> none;
    opt.drop_offsets.assign(drops, drops + nd);
    fl_plan_buffer(ib, n, kind, bc5::direct::kGfxRing, nullptr, none, opt.drop_offsets, plan);
    std::vector<uint32_t> copy, n2o;
    if (!plan.draws.empty() || plan.inserts) fl_after(ib, n, kind, 7, false, plan, opt, copy, n2o);
    for (std::size_t k = 0; k < copy.size() && k < cap; k++) out[k] = copy[k];
    for (std::size_t k = 0; k < opt.drop_offsets.size() && k < nd; k++) drops[k] = opt.drop_offsets[k];
    const uint32_t v[6] = {static_cast<uint32_t>(copy.size()), plan.flushes, plan.serials, plan.heads_laid, static_cast<uint32_t>(opt.drop_offsets.size()), plan.crumbs ? 1u : 0u};
    for (uint32_t k = 0; k < 6; k++) info[k] = v[k];
    return static_cast<uint32_t>(copy.size());
}
// ---- end of exp 0401 series e7's (tag flx) seams ----------------------------------------------------------------------
""")

# ---- the three exp 0404 lines in submit_now and the completion thread -----------------------------------------------
L_AFTER_OLD = b"\tif (!fl_plan.draws.empty()) fl_after(ib, num_dwords, kind, n, mec_expand_ib, fl_plan, opt, fl_ib, fl_new_to_old);\n"
L_AFTER_NEW = (b"\tif (!fl_plan.draws.empty() || fl_plan.inserts) fl_after(ib, num_dwords, kind, n, mec_expand_ib, fl_plan, opt, fl_ib, fl_new_to_old);"
               b" // + exp 0401 e7 (flx): a prefix head alone\n")
L_SYNC_OLD = b"\tif (r.timed_out && fl_plan.crumbs) fl_probe(fl_plan, n, kind, true); // experiment 0404: first, before the long probe\n"
L_SYNC_NEW = L_SYNC_OLD + (b"\tif (!r.timed_out && r.ok && !r.pending && fl_plan.crumbs) fl_keep_done(fl_plan, n);"
                           b" // exp 0401 e7 (flx) A1: the last done draw, for a later timeout\n")
L_CQ_OLD = (b"\t\t\tif (r.timed_out && j.fl_plan.crumbs) fl_probe(j.fl_plan, j.n, j.kind, g_dev && j.dev_gen == g_dev_gen.load());"
            b" // experiment 0404: first, before the long probe\n")
L_CQ_NEW = L_CQ_OLD + (b"\t\t\tif (!r.timed_out && r.ok && j.fl_plan.crumbs) fl_keep_done(j.fl_plan, j.n);"
                       b" // exp 0401 e7 (flx) A1: the last done draw, for a later timeout\n")

G_ANCHOR = (b"static std::atomic<uint64_t> g_fl_bufs {0}, g_fl_draws {0}, g_fl_maybe {0}, g_fl_unknown {0}, g_fl_cond_full {0},"
            b" g_fl_skipped {0}, g_fl_refused {0};\n")
END_ANCHOR = b"// ---- end of experiment 0404's pure part"

# (name, head, end, md5 of the span in the input, kind, payload)
#   kind "whole": payload is the new span; "subs": payload is [(old, new)], each old once in the span;
#   "append": payload is text put before the span's closing "};\n" (structs)
UNITS = [
    ("FlState", b"struct FlState { // the GFX context's tracked registers, carried from buffer to buffer\n", b"\n};\n",
     "8f59c009f89660088b38e138b68b5d80", "whole", FLX_DECL + b"\n" + NEW_FLSTATE),
    ("fl_merge_state", b"static void fl_merge_state(FlState& s, const FlState& o) {", b"\n}\n",
     "0932bcee04f5be599344bdc0fd4861c1", "whole", NEW_MERGE),
    ("FlDraw", b"struct FlDraw {\n", b"\n};\n", "8f7c4b17ca337656275d035a68e7fc24", "append", FLDRAW_MEMBERS),
    ("FlPlan", b"struct FlPlan {\n", b"\n};\n", "87b5d35204481dc94f8abd721c126e1a", "append", FLPLAN_MEMBERS),
    ("FlOptions", b"struct FlOptions {\n", b"\n};\n", "148f5b45c2596a26a388663247950c28", "append+", (FLOPTIONS_MEMBERS, FLX_PLAN_ML)),
    ("fl_scan", b"static void fl_scan(const uint32_t* ib, uint32_t n, const Read& read, FlState& st, const FlOptions& o, FlPlan& plan) {\n",
     b"\n}\n", "0d6c74706b0a983c45131696ec6d6006", "subs", SCAN_SUBS),
    ("fl_build", b"static uint32_t fl_build(const uint32_t* ib, uint32_t n, FlPlan& plan, uint64_t submit, std::vector<uint32_t>& out,\n",
     b"\n}\n", "72a0d84e96a375cbf5e5fa3e5dc48a36", "subs", BUILD_SUBS),
    ("fl_plan_buffer", b"static void fl_plan_buffer(const uint32_t* ib, uint32_t n, const char* kind, int ring, const Chain* chain,"
     b" const std::vector<bc5::direct::Mapping>& maps,\n", b"\n}\n", "a7c990c55c9fb4c190121aa166f285f7", "subs", PLAN_SUBS),
    ("fl_after", b"static void fl_after(const uint32_t* ib, uint32_t n, const char* kind, uint64_t submit, bool mec_rebuilt, FlPlan& plan,"
     b" bc5::policy::FilterOptions& opt,\n", b"\n}\n", "d92439fa543260ac4c309328a11bc14b", "subs", AFTER_SUBS),
    ("fl_probe", b"static void fl_probe(const FlPlan& plan, uint64_t n, const char* kind, bool same_device) {\n", b"\n}\n",
     "8b793a997a11c92fdc62182314781ddf", "subs+", (PROBE_SUBS, b"\n" + SEAMS)),
]
# (name, anchor, new text for the anchor): each anchor once in the unit
LINES = [
    ("the host block", G_ANCHOR, G_ANCHOR + FLX_GLUE),
    ("the late pure block", END_ANCHOR, FLX_LATE + END_ANCHOR),
    ("submit_now: the fl_after call", L_AFTER_OLD, L_AFTER_NEW),
    ("submit_now: after the sync fl_probe call", L_SYNC_OLD, L_SYNC_NEW),
    ("completion_thread: after its fl_probe call", L_CQ_OLD, L_CQ_NEW),
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


def span(s, head, end):
    assert s.count(head) == 1, ("a head does not occur exactly once", head[:60], s.count(head))
    a = s.index(head)
    return a, s.index(end, a) + len(end)


def new_unit(old, kind, payload, name):
    if kind == "whole":
        return payload
    if kind in ("append", "append+"):
        members, after = (payload, b"") if kind == "append" else payload
        assert old.endswith(b"\n};\n") and old.count(b"\n};\n") == 1, ("the struct's end", name)
        return old[:-3] + members + b"};\n" + after
    subs, after = (payload, b"") if kind == "subs" else payload
    new = old
    for o, w in subs:
        assert new.count(o) == 1, ("a snippet does not occur exactly once in its function", name, o[:80], new.count(o))
        assert balance(o) == balance(w), ("a snippet changes the balance", name, o[:60], balance(o), balance(w))
        new = new.replace(o, w)
    return new + after


def edit_unit(s):
    for m in MARKS:
        assert m not in s, ("the unit has the edit already", m)
    assert b"\r" not in s, "a CR in the LF unit"
    assert s.count(REGION[0]) == 1 and s.count(REGION[1]) == 1, "the exp 0404 block's bounds"
    r0, r1 = s.index(REGION[0]), s.index(REGION[1])
    done = []  # (old, new) in the order applied, for the undo
    out = s
    for name, head, end, pin, kind, payload in UNITS:
        a, b = span(out, head, end)
        assert r0 <= a and b <= out.index(REGION[1]) + 0, ("a unit outside the exp 0404 block", name)
        old = out[a:b]
        assert md5(old) == pin, ("a unit is not exp 0404's as pinned (another script changed it?)", name, md5(old), pin)
        new = new_unit(old, kind, payload, name)
        assert balance(old) == balance(new), ("the edit changes the balance", name, balance(old), balance(new))
        new.decode("ascii")
        assert b"\r" not in new
        out = out[:a] + new + out[b:]
        done.append((old, new, name))
    for name, old, new in LINES:
        assert out.count(old) == 1, ("an anchor does not occur exactly once", name, out.count(old))
        assert balance(old) == balance(new), ("the edit changes the balance", name, balance(old), balance(new))
        new.decode("ascii")
        assert b"\r" not in new
        out = out.replace(old, new)
        done.append((old, new, name))
    # The block anchors lie in the exp 0404 block; the three lines outside it are exp 0404's own.
    e0, e1 = out.index(REGION[0]), out.index(REGION[1])
    for marker in (b"// ---- exp 0401 series e7 (tag flx): F1/F2 flushes", b"// ---- exp 0401 series e7 (tag flx): the late pure block",
                   b"// ---- exp 0401 series e7 (tag flx): the switches and the host's side", b"// ---- exp 0401 series e7 (tag flx): the CPU test's seams"):
        assert out.count(marker) == 1 and e0 < out.index(marker) < e1, ("a block outside the exp 0404 block", marker)
    order = [out.index(x) for x in (b"// ---- exp 0401 series e7 (tag flx): F1/F2 flushes", b"struct FlState {", b"struct FlDraw {", b"struct FlOptions {",
                                    b"static bool flx_plan_ml(", b"static void fl_scan(", b"static uint32_t fl_build(", b"static FlFind fl_find(",
                                    b"static int flx_next_draw(", END_ANCHOR, b"static const FlxSwitches& flx_switches()", b"static void fl_plan_buffer(",
                                    b"static void fl_after(", b"static void fl_probe(", b"extern \"C\" void bc5_flx0401_switches(", REGION[1])]
    assert order == sorted(order), ("the blocks are out of order", order)
    assert out.count(b"fl_keep_done(") == 3 and out.count(b"flx_switches()") == 5  # definition, fl_keep_done, fl_plan_buffer, fl_probe, a seam
    assert balance(out) == balance(s), ("the unit's balance changed", balance(s), balance(out))
    # Undo (last first): the input must come back byte for byte.
    back = out
    for old, new, name in reversed(done):
        assert back.count(new) == 1, ("undo", name)
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
