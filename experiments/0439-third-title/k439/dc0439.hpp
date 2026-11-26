// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0439 (tag dc439): the third title's DCC display buffers on the direct path
// (experiments/0439-third-title/dcc-present-design.md). Free of the host: the CB_COLORn block of a surface taken
// from a tracked context (bc5::state_stack::Context), and the in-place CB_DCC_DECOMPRESS IB built from it. Tested by
// test_dc0439.cpp on any machine.
//
// Sources (Mesa 0866ae7085c1):
//   - register offsets and fields: src/amd/registers/gfx10.json (context offsets from 0x28000, SH from 0xb000,
//     UCONFIG from 0x30000, in dwords);
//   - CB_COLOR_CONTROL.MODE 6 = CB_DCC_DECOMPRESS (enum CBMode); RADV draws over the image with that mode on the
//     general queue, then flushes CB and CB metadata (src/amd/vulkan/meta/radv_meta_fast_clear.c,
//     radv_decompress_dcc and the custom_blend_mode switch);
//   - a gfx10 PS without exports: COL and Z formats SPI_SHADER_ZERO, "the hw will skip export instructions if any
//     are present" (src/amd/vulkan/radv_pipeline_graphics.c, the comment above the export decision);
//   - legacy VS: window-space positions PA_CL_VTE_CNTL = VTX_XY_FMT | VTX_Z_FMT, SPI_VS_OUT_CONFIG.NO_PC_EXPORT with
//     no params, POS0 4COMP, VGT_SHADER_STAGES_EN.MAX_PRIMGRP_IN_WAVE 2, GE_CNTL.PRIM_GRP_SIZE 128
//     (src/gallium/drivers/radeonsi/gfx/si_state_shaders.cpp si_shader_vs, si_state_draw.cpp);
//   - binning off: PA_SC_BINNER_CNTL_0 = DISABLE_BINNING_USE_LEGACY_SC | DISABLE_START_OF_PRIM
//     (src/gallium/drivers/radeonsi/si_state_binning.c);
//   - packets: src/amd/common/sid.h (CLEAR_STATE 0x12, DRAW_INDEX_AUTO 0x2d, NUM_INSTANCES 0x2f, EVENT_WRITE 0x46,
//     SET_CONTEXT_REG 0x69, SET_SH_REG 0x76, SET_UCONFIG_REG 0x79, SET_UCONFIG_REG_INDEX 0x7a with the index in bits
//     31:28 of the offset dword, si_build_pm4.h radeon_set_reg_seq; VGT_PRIMITIVE_TYPE with index 1);
//   - events: FLUSH_AND_INV_CB_META 0x2e (VGT_EVENT_TYPE; ac_barrier.c writes it after a CB flush).
// The IB brackets its draw with CLEAR_STATE push (cmd 1) and pop (cmd 2), as the console's driver brackets its internal
// draws: the device's state-stack emulation (bc5/state_stack.hpp) runs the kernel's clear state for the push and puts
// back the title's context registers at the pop. SH and UCONFIG registers written here are not restored: the title
// sets its programs and primitive type per draw (TODO(verify) in the first run: the frames after the decompress).
#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <vector>

#include "bc5/ib_chain.hpp" // exp 0439 (tag ib439): the chain rule for walk_draws

namespace bc5::dc439 {

// Context register offsets (dwords from 0x28000).
inline constexpr std::uint32_t kCbColor0Base = 0x318; // + 0xf per MRT: BASE .. DCC_BASE (+0xd), 15 dwords
inline constexpr std::uint32_t kCbStride = 0xf;
inline constexpr std::uint32_t kCbBaseExt = 0x390, kCbCmaskExt = 0x398, kCbFmaskExt = 0x3a0, kCbDccExt = 0x3a8;
inline constexpr std::uint32_t kCbAttrib2 = 0x3b0, kCbAttrib3 = 0x3b8; // + 1 per MRT
inline constexpr std::uint32_t kCbColorControl = 0x202, kCbTargetMask = 0x08e, kCbShaderMask = 0x08f;
inline constexpr std::uint32_t kCbDccControl = 0x109;

// One MRT's CB_COLOR block as the title last set it for a surface.
struct Block {
    bool valid = false;
    std::uint32_t mrt = 0;
    std::array<std::uint32_t, 15> c{}; // BASE, PITCH, SLICE, VIEW, INFO, ATTRIB, DCC_CONTROL, CMASK, CMASK_SLICE,
                                       // FMASK, FMASK_SLICE, CLEAR_WORD0, CLEAR_WORD1, DCC_BASE, (reserved)
    std::uint32_t base_ext = 0, cmask_ext = 0, fmask_ext = 0, dcc_ext = 0, attrib2 = 0, attrib3 = 0;
    std::uint32_t cb_dcc_control = 0;
    bool cb_dcc_control_valid = false;
    bool operator==(const Block &o) const {
        return valid == o.valid && mrt == o.mrt && c == o.c && base_ext == o.base_ext && cmask_ext == o.cmask_ext &&
               fmask_ext == o.fmask_ext && dcc_ext == o.dcc_ext && attrib2 == o.attrib2 && attrib3 == o.attrib3;
    }
    std::uint64_t base() const { return (static_cast<std::uint64_t>(c[0]) << 8) | (static_cast<std::uint64_t>(base_ext & 0xffu) << 40); }
    std::uint64_t dcc_base() const { return (static_cast<std::uint64_t>(c[13]) << 8) | (static_cast<std::uint64_t>(dcc_ext & 0xffu) << 40); }
    std::uint32_t info() const { return c[4]; }
    bool dcc_enable() const { return ((c[4] >> 28) & 1u) != 0; } // CB_COLOR0_INFO.DCC_ENABLE
    std::uint32_t sw_mode() const { return (attrib3 >> 14) & 0x1fu; } // CB_COLOR0_ATTRIB3.COLOR_SW_MODE
    bool meta_linear() const { return ((attrib3 >> 13) & 1u) != 0; }
    bool dcc_pipe_aligned() const { return ((attrib3 >> 30) & 1u) != 0; }
};

// ctx_value / ctx_valid: a tracked context (0x400 registers from 0x28000). The MRT whose BASE (with BASE_EXT) is
// `surface` and whose target mask nibble is not 0; the highest such MRT wins only if no lower one matches.
template <typename Values, typename Valid>
inline Block find(const Values &ctx_value, const Valid &ctx_valid, std::uint64_t surface) {
    Block b;
    if ((surface & 0xffu) != 0) return b;
    for (std::uint32_t m = 0; m < 8; m++) {
        const std::uint32_t o = kCbColor0Base + m * kCbStride;
        if (!ctx_valid[o]) continue;
        const std::uint64_t ext = ctx_valid[kCbBaseExt + m] ? ctx_value[kCbBaseExt + m] : 0;
        const std::uint64_t a = (static_cast<std::uint64_t>(ctx_value[o]) << 8) | ((ext & 0xffu) << 40);
        if (a != surface) continue;
        b.valid = true;
        b.mrt = m;
        for (std::uint32_t k = 0; k < 15; k++) b.c[k] = ctx_valid[o + k] ? ctx_value[o + k] : 0;
        auto v = [&](std::uint32_t r) { return ctx_valid[r] ? static_cast<std::uint32_t>(ctx_value[r]) : 0u; };
        b.base_ext = v(kCbBaseExt + m);
        b.cmask_ext = v(kCbCmaskExt + m);
        b.fmask_ext = v(kCbFmaskExt + m);
        b.dcc_ext = v(kCbDccExt + m);
        b.attrib2 = v(kCbAttrib2 + m);
        b.attrib3 = v(kCbAttrib3 + m);
        b.cb_dcc_control_valid = ctx_valid[kCbDccControl];
        b.cb_dcc_control = v(kCbDccControl);
        return b;
    }
    return b;
}

// The per-draw catcher (p1 found no MRT on the surface at the END of any GFX job: the title rebinds its targets within
// an IB). The context registers followed packet by packet, from `seed` (the tracker's context at the IB's start):
// SET_CONTEXT_REG 0x69, LOAD_CONTEXT_REG_INDEX 0x9f (pairs or consecutive), LOAD_CONTEXT_REG 0x61, CLEAR_STATE 0x12
// (resets the followed set), INDIRECT_BUFFER 0x3f / 0x33 one level deep (read through `readable`). At every draw
// (0x24 0x25 0x27 0x2c 0x2d 0x30 0x35 0x38) each surface whose MRT is bound with a non-zero target-mask nibble gets its
// block and a count. Opcodes: Mesa src/amd/common/sid.h; the packet forms as in backend/src/state_stack.cpp.
struct Ctx {
    std::array<std::uint32_t, 0x400> value{};
    std::array<bool, 0x400> valid{};
    void set(std::uint32_t r, std::uint32_t v) {
        if (r < 0x400) {
            value[r] = v;
            valid[r] = true;
        }
    }
};
inline bool is_draw(std::uint32_t op) {
    return op == 0x24 || op == 0x25 || op == 0x27 || op == 0x2c || op == 0x2d || op == 0x30 || op == 0x35 || op == 0x38;
}
struct Hit {
    Block block;
    std::uint64_t draws = 0;
};
template <typename Readable>
inline void walk_draws(const std::uint32_t *ib, std::size_t n, Ctx &cx, const std::vector<std::uint64_t> &surfaces, std::vector<Hit> &hits,
                       const Readable &readable, int depth = 0, std::size_t chain_left = ib_chain::kMaxChainPieces) {
    for (std::size_t i = 0; i < n;) {
        const std::uint32_t h = ib[i];
        const std::uint32_t type = h >> 30, count = (h >> 16) & 0x3fffu;
        std::size_t len = 1;
        if (type == 3 || type == 0) len = count == 0x3fffu ? 1 : count + 2;
        if (i + len > n) break;
        if (type == 3 && count != 0x3fffu) {
            const std::uint32_t op = (h >> 8) & 0xffu;
            const std::uint32_t *p = ib + i;
            if (op == 0x69 && len >= 3) {
                const std::uint32_t reg = p[1] & 0xffffu;
                for (std::size_t k = 2; k < len; k++) cx.set(reg + static_cast<std::uint32_t>(k - 2), p[k]);
            } else if (op == 0x12) {
                cx.valid.fill(false);
            } else if (op == 0x9f && len >= 5) {
                const std::uint64_t a = (p[1] & ~3u) | (static_cast<std::uint64_t>(p[2] & 0xffffu) << 32);
                const std::uint32_t cnt = p[4] & 0x3fffu;
                const bool pairs = (p[3] >> 31) != 0;
                if (a != 0 && cnt != 0 && cnt <= 4096 && readable(a, static_cast<std::uint64_t>(cnt) * (pairs ? 8 : 4))) {
                    const auto *m = reinterpret_cast<const volatile std::uint32_t *>(a);
                    for (std::uint32_t k = 0; k < cnt; k++) {
                        if (pairs) cx.set(m[2 * k] & 0xffffu, m[2 * k + 1]);
                        else cx.set((p[3] & 0xffffu) + k, m[k]);
                    }
                }
            } else if (op == 0x61 && len >= 5) {
                const std::uint64_t a = (p[1] & ~3u) | (static_cast<std::uint64_t>(p[2] & 0xffffu) << 32);
                for (std::size_t k = 3; k + 1 < len; k += 2) {
                    const std::uint32_t reg = p[k] & 0xffffu, cnt = p[k + 1] & 0x3fffu;
                    const std::uint64_t at = a + static_cast<std::uint64_t>(reg) * 4;
                    if (a != 0 && cnt != 0 && readable(at, static_cast<std::uint64_t>(cnt) * 4)) {
                        const auto *m = reinterpret_cast<const volatile std::uint32_t *>(at);
                        for (std::uint32_t q = 0; q < cnt; q++) cx.set(reg + q, m[q]);
                    }
                }
            } else if ((op == 0x3f || op == 0x33) && len >= 4 &&
                       (ib_chain::enabled() && ib_chain::is_chain(p[3]) ? chain_left > 0 : depth == 0)) {
                // exp 0439 (tag ib439): with BC5_DIRECT_IB_CHAIN=1 a chain (bit 20) keeps this depth and ends this buffer;
                // at most kMaxChainPieces links, so a chain cycle ends (bc5/ib_chain.hpp)
                const bool chain = ib_chain::enabled() && ib_chain::is_chain(p[3]);
                const std::uint64_t a = (p[1] & ~3u) | (static_cast<std::uint64_t>(p[2] & 0xffffu) << 32);
                const std::uint32_t sz = p[3] & 0xfffffu;
                if (a != 0 && sz != 0 && readable(a, static_cast<std::uint64_t>(sz) * 4)) {
                    std::vector<std::uint32_t> sub(sz);
                    const auto *m = reinterpret_cast<const volatile std::uint32_t *>(a);
                    for (std::uint32_t k = 0; k < sz; k++) sub[k] = m[k];
                    walk_draws(sub.data(), sub.size(), cx, surfaces, hits, readable, chain ? depth : depth + 1, chain ? chain_left - 1 : chain_left);
                    if (chain) return;
                }
            } else if (is_draw(op)) {
                const std::uint32_t tm = cx.valid[kCbTargetMask] ? cx.value[kCbTargetMask] : 0xffffffffu;
                for (std::size_t s = 0; s < surfaces.size(); s++) {
                    const Block b = find(cx.value, cx.valid, surfaces[s]);
                    if (!b.valid || ((tm >> (4 * b.mrt)) & 0xfu) == 0) continue;
                    hits[s].block = b;
                    hits[s].draws++;
                }
            }
        }
        i += len;
    }
}

// How many dwords of an IB (and of the 64-dword tables its SET_SH_REG user-data pairs point at) hold `base256`
// (an address >> 8): where the surface's address appears at all, per ring (an image descriptor's BASE_ADDRESS is the
// address >> 8 in its first dword). TODO(verify): a T# match is a hint, not a proof of a write.
template <typename Readable>
inline std::uint32_t count_base(const std::uint32_t *ib, std::size_t n, std::uint32_t base256, const Readable &readable) {
    std::uint32_t c = 0;
    for (std::size_t i = 0; i < n; i++)
        if (ib[i] == base256) c++;
    for (std::size_t i = 0; i < n;) {
        const std::uint32_t h = ib[i];
        const std::uint32_t type = h >> 30, count = (h >> 16) & 0x3fffu;
        std::size_t len = (type == 3 || type == 0) ? (count == 0x3fffu ? 1 : count + 2) : 1;
        if (i + len > n) break;
        if (type == 3 && (((h >> 8) & 0xffu) == 0x76 || ((h >> 8) & 0xffu) == 0x9b) && len >= 4) {
            for (std::size_t k = 2; k + 1 < len; k++) {
                const std::uint64_t a = ib[i + k] | (static_cast<std::uint64_t>(ib[i + k + 1] & 0xffffu) << 32);
                if ((a >> 40) != 0 || a < 0x100000000ull || (a & 3u) != 0 || !readable(a, 256)) continue;
                const auto *m = reinterpret_cast<const volatile std::uint32_t *>(a);
                for (std::uint32_t q = 0; q < 64; q++)
                    if (m[q] == base256) c++;
            }
        }
        i += len;
    }
    return c;
}

// The AGC-era end-of-pipe event (BC5_DIRECT_AGC_EOP_IDENT). Sources, GPL-2.0, checked 2026-11-21 (exp 0439 README):
// KytyPS5 39936ffa src/graphics/host_gpu/renderer/renderContext.cpp ~205-217 (TriggerInterrupt matches registrations by
// event id; data = (context_id << 16) | ident); src/graphics/guest_gpu/graphicsRun.h:51 ComputeQueueBase = 0x20;
// graphicsRun.cpp: the graphics CP's event id 0, a compute CP's ComputeQueueBase + queue_id - 1, RELEASE_MEM with its
// interrupt bit defers TriggerInterrupt(event_id, interrupt context id). AnyPS5 19a1993e
// core/libs/prx/libSceAgcDriver/Eq/src/Event.cpp ~80-91 (AddEqEvent stores id as ident and queue; delivery sets
// data = queue | context << 16). UNVERIFIED on hardware. queue_id here = the queue registration's doorbell slot d (the
// third title's 0x52 = 0x20 + 0x33 - 1 for slot 0x33, queue 2/2/2).
inline constexpr std::uint32_t kAgcComputeQueueBase = 0x20;
inline std::uint32_t agc_eop_ident(bool compute, std::uint32_t queue_slot) { return compute ? kAgcComputeQueueBase + queue_slot - 1u : 0u; }
inline std::uint64_t agc_eop_data(std::uint32_t context_id, std::uint32_t ident) {
    return (static_cast<std::uint64_t>(context_id) << 16u) | ident;
}
// RELEASE_MEM dword 2: INT_SEL in bits 26:24, three bits (gfx10 form; TODO(verify) against AMD PAL's PM4 headers; KytyPS5
// accepts 0..4). The soft CP read two bits, so 4 read as 0 (no interrupt).
inline std::uint32_t release_mem_int_sel(std::uint32_t dword2) { return (dword2 >> 24u) & 7u; }

// The two programs (wave64, gfx1013; llvm-mc 21.1.8 -triple=amdgcn -mcpu=gfx1013 -mattr=+wavefrontsize64
// -show-encoding, k439/vs.s and k439/ps.s):
//   VS: v_and_b32 v1, 1, v0 ; v_and_b32 v2, 2, v0 ; v_mov_b32 v3, s0 ; v_mov_b32 v4, s1 ; v_mov_b32 v5, 0 ;
//       v_cmp_ne_u32 vcc, 0, v1 ; v_cndmask_b32 v6, 0, v3, vcc ; v_cmp_ne_u32 vcc, 0, v2 ; v_cndmask_b32 v7, 0, v4, vcc ;
//       v_mov_b32 v8, 1.0 ; exp pos0 v6, v7, v5, v8 done ; s_endpgm
//       (vertex id 0 -> (0, 0), 1 -> (w, 0), 2 -> (0, h): the RECTLIST's three corners; s0, s1 = w, h as floats)
//   PS: exp null off, off, off, off done vm ; s_endpgm (skipped by the hardware with both export formats ZERO)
inline constexpr std::array<std::uint32_t, 14> kVs = {0x36020081u, 0x36040082u, 0x7E060200u, 0x7E080201u, 0x7E0A0280u,
                                                     0x7D8A0280u, 0x020C0680u, 0x7D8A0480u, 0x020E0880u, 0x7E1002F2u,
                                                     0xF80008CFu, 0x08050706u, 0xBF810000u, 0xBF810000u};
inline constexpr std::array<std::uint32_t, 4> kPs = {0xF8001890u, 0x00000000u, 0xBF810000u, 0xBF810000u};

inline std::uint32_t pkt3(std::uint32_t op, std::uint32_t body) { return 0xC0000000u | ((body - 1u) << 16) | (op << 8); }
inline void ctx(std::vector<std::uint32_t> &o, std::uint32_t reg, std::initializer_list<std::uint32_t> v) {
    o.push_back(pkt3(0x69, 1u + static_cast<std::uint32_t>(v.size())));
    o.push_back(reg);
    o.insert(o.end(), v.begin(), v.end());
}
inline void sh(std::vector<std::uint32_t> &o, std::uint32_t reg, std::initializer_list<std::uint32_t> v) {
    o.push_back(pkt3(0x76, 1u + static_cast<std::uint32_t>(v.size())));
    o.push_back(reg);
    o.insert(o.end(), v.begin(), v.end());
}
inline void uc(std::vector<std::uint32_t> &o, std::uint32_t reg, std::uint32_t v, std::uint32_t idx = 0) {
    o.push_back(pkt3(idx != 0 ? 0x7a : 0x79, 2));
    o.push_back(reg | (idx << 28));
    o.push_back(v);
}
inline std::uint32_t f32(float f) {
    std::uint32_t u;
    std::memcpy(&u, &f, 4);
    return u;
}

// The decompress IB for one surface of w x h pixels whose block b was taken from the title's context; vs_va and ps_va
// 256-byte aligned GPU addresses of kVs and kPs, below 2^40.
// CB_SHADER_MASK is 0xf: Mesa 0866ae7 src/amd/vulkan/radv_cmd_buffer.c radv_bind_fragment_output_state, with a custom blend
// mode (CB_COLOR_CONTROL.MODE != normal) "According to the CB spec states, CB_SHADER_MASK should be set to enable writes to all
// four channels of MRT0". With 0 (the first build, exp 0439 items 38-39) the CB changed no key byte and the present showed
// compressed blocks as plain bytes.
inline std::vector<std::uint32_t> build(const Block &b, std::uint32_t w, std::uint32_t h, std::uint64_t vs_va, std::uint64_t ps_va) {
    std::vector<std::uint32_t> o;
    o.reserve(160);
    o.push_back(pkt3(0x12, 1)); // CLEAR_STATE push (cmd 1): the device's state stack keeps the title's context
    o.push_back(1);
    // MRT0 = the surface, as the title set it (whatever MRT it used); the others stay at the clear state (no format).
    o.push_back(pkt3(0x69, 1 + 15));
    o.push_back(kCbColor0Base);
    o.insert(o.end(), b.c.begin(), b.c.end());
    ctx(o, kCbBaseExt, {b.base_ext});
    ctx(o, kCbCmaskExt, {b.cmask_ext});
    ctx(o, kCbFmaskExt, {b.fmask_ext});
    ctx(o, kCbDccExt, {b.dcc_ext});
    ctx(o, kCbAttrib2, {b.attrib2});
    ctx(o, kCbAttrib3, {b.attrib3});
    if (b.cb_dcc_control_valid) ctx(o, kCbDccControl, {b.cb_dcc_control});
    ctx(o, kCbColorControl, {(0xCCu << 16) | (6u << 4)}); // ROP3 copy, MODE CB_DCC_DECOMPRESS
    ctx(o, kCbTargetMask, {0xFu, 0xFu});                    // CB_TARGET_MASK MRT0 RGBA, CB_SHADER_MASK MRT0 RGBA (above)
    const std::uint32_t br = (w & 0x7fffu) | ((h & 0x7fffu) << 16);
    ctx(o, 0x080, {0u, 0x80000000u, br, 0xFFFFu});          // PA_SC_WINDOW_OFFSET, WINDOW_SCISSOR_TL/BR, CLIPRECT_RULE
    ctx(o, 0x090, {0x80000000u, br});                        // PA_SC_GENERIC_SCISSOR_TL/BR
    ctx(o, 0x00c, {0u, br});                                 // PA_SC_SCREEN_SCISSOR_TL/BR
    ctx(o, 0x094, {0x80000000u, br});                        // PA_SC_VPORT_SCISSOR_0_TL/BR
    ctx(o, 0x2f8, {0u});                                     // PA_SC_AA_CONFIG: one sample
    ctx(o, 0x30e, {0xFFFFFFFFu, 0xFFFFFFFFu});               // PA_SC_AA_MASK_X0Y0_X1Y0, X0Y1_X1Y1
    ctx(o, 0x311, {3u | (1u << 18)});                        // PA_SC_BINNER_CNTL_0: legacy SC, no binning
    ctx(o, 0x204, {1u << 16, 0u, 0x300u, 0u});               // PA_CL_CLIP_CNTL CLIP_DISABLE, PA_SU_SC_MODE_CNTL, VTE XY|Z fmt, VS_OUT_CNTL
    ctx(o, 0x000, {0u});                                     // DB_RENDER_CONTROL
    ctx(o, 0x010, {0u, 0u});                                 // DB_Z_INFO, DB_STENCIL_INFO: no depth, no stencil
    ctx(o, 0x200, {0u});                                     // DB_DEPTH_CONTROL
    ctx(o, 0x203, {0u});                                     // DB_SHADER_CONTROL
    ctx(o, 0x1b1, {0x80u});                                  // SPI_VS_OUT_CONFIG: NO_PC_EXPORT, no params
    ctx(o, 0x1b3, {0x2u, 0x2u});                             // SPI_PS_INPUT_ENA/ADDR: PERSP_CENTER (one is required)
    ctx(o, 0x1b6, {0u});                                     // SPI_PS_IN_CONTROL: no interpolants, wave64
    ctx(o, 0x1c3, {4u, 0u, 0u});                             // SPI_SHADER_POS_FORMAT 4COMP, Z_FORMAT ZERO, COL_FORMAT ZERO
    ctx(o, 0x290, {0u});                                     // VGT_GS_MODE off
    ctx(o, 0x2d5, {2u << 15});                               // VGT_SHADER_STAGES_EN: legacy VS, MAX_PRIMGRP_IN_WAVE 2
    // Programs (SH): VS 9 VGPRs (encoded (9 - 1) / 4 = 2), FLOAT_MODE 0xc0, DX10_CLAMP; 2 user SGPRs = w, h.
    sh(o, 0x046, {0xFFFFu | (0x3Fu << 16)});                 // SPI_SHADER_PGM_RSRC3_VS: CU_EN all, WAVE_LIMIT 0x3f
    sh(o, 0x048, {static_cast<std::uint32_t>(vs_va >> 8), static_cast<std::uint32_t>(vs_va >> 40),
                  2u | (0xC0u << 12) | (1u << 21), 2u << 1, f32(static_cast<float>(w)), f32(static_cast<float>(h))});
    sh(o, 0x007, {0xFFFFu | (0x3Fu << 16)});                 // SPI_SHADER_PGM_RSRC3_PS
    sh(o, 0x008, {static_cast<std::uint32_t>(ps_va >> 8), static_cast<std::uint32_t>(ps_va >> 40),
                  0u | (0xC0u << 12) | (1u << 21), 0u});     // PS: 4 VGPRs, no user SGPRs
    uc(o, 0x242, 0x11u, 1);                                  // VGT_PRIMITIVE_TYPE RECTLIST (index 1)
    uc(o, 0x25b, 128u);                                      // GE_CNTL PRIM_GRP_SIZE 128, VERT_GRP_SIZE 0
    o.push_back(pkt3(0x2f, 1));                              // NUM_INSTANCES 1
    o.push_back(1);
    o.push_back(pkt3(0x2d, 2));                              // DRAW_INDEX_AUTO 3 vertices, DI_SRC_SEL_AUTO_INDEX
    o.push_back(3);
    o.push_back(2);
    o.push_back(pkt3(0x46, 1));                              // EVENT_WRITE FLUSH_AND_INV_CB_META
    o.push_back(0x2eu);
    o.push_back(pkt3(0x46, 1));                              // EVENT_WRITE FLUSH_AND_INV_CB_PIXEL_DATA
    o.push_back(0x31u);
    o.push_back(pkt3(0x12, 1)); // CLEAR_STATE pop (cmd 2): the title's context registers put back
    o.push_back(2);
    return o;
}

} // namespace bc5::dc439
