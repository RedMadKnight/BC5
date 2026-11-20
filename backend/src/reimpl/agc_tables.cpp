// SPDX-License-Identifier: GPL-2.0-only
// Own-source data tables of the libSceAgc re-creation (see include/bc5/reimpl/agc_tables.hpp).
//
// Written from a description of each table's meaning (clean-room, src/reimpl/PROVENANCE.md):
// which registers a table holds, in which order, and what each non-zero value means. Register
// offsets, field positions and enum values come from Mesa's gfx10 register database
// (tools/bc5-agc/regdb/gfx10.json, MIT) through the generated agc_regdb.hpp. A name with a
// lower-case `n` is a register family indexed by n (CB_BLENDn_CONTROL[3] = CB_BLEND3_CONTROL).
// Offsets without a gfx10 name in their space are written as unnamed(0x...); values are written
// as bit positions only where the description gives them so (no gfx10 name or field).
//
// Element order matters: the descriptors locate registers by position and the init code scans
// the lists in order, so every list is built in exactly the order of the description.
#include "bc5/reimpl/agc_tables.hpp"

#include "bc5/reimpl/agc_regdb.hpp"

#include <array>
#include <map>
#include <set>
#include <vector>

namespace bc5::reimpl::agc::tables {

namespace {

using namespace bc5::reimpl::regdb;
using u32 = std::uint32_t;

// An offset of the table's register space that has no gfx10 name there.
constexpr u32 unnamed(u32 offset) { return offset; }

// An ordered register list.
class List {
  public:
    List &add(std::initializer_list<u32> offsets) {
        offsets_.insert(offsets_.end(), offsets.begin(), offsets.end());
        return *this;
    }
    // Every register from `first` to `last` inclusive, ascending ("A .. B").
    List &range(u32 first, u32 last) {
        for (u32 o = first; o <= last; ++o) {
            offsets_.push_back(o);
        }
        return *this;
    }
    const std::vector<u32> &offsets() const { return offsets_; }

  private:
    std::vector<u32> offsets_;
};

// Non-zero values by register offset; every other entry is zero.
using Values = std::map<u32, u32>;

// "The list X with these edits": removals and insertions refer to positions in the base list and
// apply at once (an insertion after A follows the place where A stands in the base, even when A
// itself is removed).
struct Insert {
    u32 after;
    std::vector<u32> offsets;
};
List edited(const List &base, const std::set<u32> &remove, const std::vector<Insert> &inserts) {
    List out;
    for (u32 o : base.offsets()) {
        if (remove.count(o) == 0) {
            out.add({o});
        }
        for (const Insert &ins : inserts) {
            if (ins.after == o) {
                for (u32 x : ins.offsets) {
                    out.add({x});
                }
            }
        }
    }
    return out;
}

std::vector<RegPair> make(const List &list, const Values &values) {
    std::vector<RegPair> pairs;
    pairs.reserve(list.offsets().size());
    for (u32 o : list.offsets()) {
        const auto it = values.find(o);
        pairs.push_back({o, it != values.end() ? it->second : 0u});
    }
    return pairs;
}

// "Every entry has the value its register has in BASE, except these, whose complete values are".
Values with_overrides(Values base, const Values &overrides) {
    for (const auto &[o, v] : overrides) {
        if (v == 0) {
            base.erase(o);
        } else {
            base[o] = v;
        }
    }
    return base;
}

// ---- CX-SOC: public context defaults, SoC family 0x840F00 --------------------------------------

List cx_soc_list() {
    List l;
    // The first 58 entries are in alphabetical order of their register names.
    l.add({ctx::CB_COLOR_CONTROL, ctx::CB_DCC_CONTROL, ctx::CB_RMI_GL2_CACHE_CONTROL,
           ctx::CB_SHADER_MASK, ctx::CB_TARGET_MASK});
    l.add({ctx::DB_ALPHA_TO_MASK, ctx::DB_COUNT_CONTROL, ctx::DB_DEPTH_CLEAR, ctx::DB_DEPTH_CONTROL,
           ctx::DB_EQAA, ctx::DB_RENDER_CONTROL});
    l.add({unnamed(0x006), ctx::DB_RMI_L2_CACHE_CONTROL, ctx::DB_SHADER_CONTROL,
           ctx::DB_SRESULTS_COMPARE_STATE0});
    l.add({ctx::DB_SRESULTS_COMPARE_STATE1, ctx::DB_STENCILREFMASK, ctx::DB_STENCILREFMASK_BF,
           ctx::DB_STENCIL_CLEAR});
    l.add({ctx::DB_STENCIL_CONTROL, ctx::GE_MAX_OUTPUT_PER_SUBGROUP, ctx::PA_CL_CLIP_CNTL,
           ctx::PA_CL_OBJPRIM_ID_CNTL});
    l.add({ctx::PA_CL_VTE_CNTL, ctx::PA_SC_AA_CONFIG, ctx::PA_SC_CLIPRECT_RULE,
           ctx::PA_SC_CONSERVATIVE_RASTERIZATION_CNTL, unnamed(0x0F0)});
    l.add({unnamed(0x0F1), unnamed(0x0F2), ctx::PA_SC_HORIZ_GRID, ctx::PA_SC_LEFT_VERT_GRID,
           ctx::PA_SC_MODE_CNTL_0, ctx::PA_SC_MODE_CNTL_1});
    l.add({ctx::PA_SC_RIGHT_VERT_GRID, ctx::PA_SC_WINDOW_OFFSET, ctx::PA_STATE_STEREO_X,
           ctx::PA_STEREO_CNTL});
    l.add({ctx::PA_SU_HARDWARE_SCREEN_OFFSET, ctx::PA_SU_LINE_CNTL, ctx::PA_SU_POINT_MINMAX,
           ctx::PA_SU_POINT_SIZE});
    l.add({ctx::PA_SU_POLY_OFFSET_CLAMP, ctx::PA_SU_POLY_OFFSET_DB_FMT_CNTL,
           ctx::PA_SU_SC_MODE_CNTL});
    l.add({ctx::PA_SU_SMALL_PRIM_FILTER_CNTL, ctx::PA_SU_VTX_CNTL, ctx::SPI_TMPRING_SIZE,
           ctx::VGT_DRAW_PAYLOAD_CNTL});
    l.add({ctx::VGT_GS_MAX_VERT_OUT, ctx::VGT_GS_OUT_PRIM_TYPE, ctx::VGT_LS_HS_CONFIG,
           ctx::VGT_MULTI_PRIM_IB_RESET_INDX});
    l.add({ctx::VGT_PRIMITIVEID_EN, ctx::VGT_REUSE_OFF, ctx::VGT_SHADER_STAGES_EN,
           ctx::VGT_TESS_DISTRIBUTION, ctx::VGT_TF_PARAM});
    // From here on the list follows register blocks.
    l.add({ctx::PA_SC_CENTROID_PRIORITY_0, ctx::PA_SC_CENTROID_PRIORITY_1});
    for (u32 n = 0; n <= 1; ++n) {
        l.range(ctx::PA_SC_AA_SAMPLE_LOCS_PIXEL_X0Yn_0[n],
                ctx::PA_SC_AA_SAMPLE_LOCS_PIXEL_X1Yn_3[n]);
    }
    l.add({ctx::PA_SC_AA_MASK_X0Y0_X1Y0, ctx::PA_SC_AA_MASK_X0Y1_X1Y1, ctx::PA_SC_BINNER_CNTL_0,
           ctx::PA_SC_BINNER_CNTL_1});
    l.range(ctx::CB_BLEND_RED, ctx::CB_BLEND_ALPHA);
    for (u32 n = 0; n <= 7; ++n) {
        l.add({ctx::CB_BLENDn_CONTROL[n]});
    }
    l.add({ctx::TA_BC_BASE_ADDR, ctx::TA_BC_BASE_ADDR_HI});
    for (u32 n = 0; n <= 3; ++n) {
        l.add({ctx::PA_SC_CLIPRECT_n_TL[n], ctx::PA_SC_CLIPRECT_n_BR[n]});
    }
    l.add({ctx::DB_DEPTH_BOUNDS_MIN, ctx::DB_DEPTH_BOUNDS_MAX});
    l.range(ctx::DB_Z_INFO, ctx::DB_RESERVED_REG_3);
    l.range(ctx::DB_Z_READ_BASE_HI, ctx::DB_HTILE_DATA_BASE_HI);
    l.add({ctx::DB_DEPTH_VIEW, ctx::DB_HTILE_DATA_BASE, ctx::DB_HTILE_SURFACE});
    l.add({ctx::DB_DEPTH_SIZE_XY, unnamed(0x0EB), unnamed(0x0EC), ctx::PA_SC_GENERIC_SCISSOR_TL,
           ctx::PA_SC_GENERIC_SCISSOR_BR});
    l.range(ctx::PA_CL_GB_VERT_CLIP_ADJ, ctx::PA_CL_GB_HORZ_DISC_ADJ);
    l.add({ctx::PA_SU_POLY_OFFSET_BACK_SCALE});
    l.add({ctx::PA_SU_POLY_OFFSET_BACK_OFFSET, ctx::PA_SU_POLY_OFFSET_FRONT_SCALE,
           ctx::PA_SU_POLY_OFFSET_FRONT_OFFSET});
    l.add({ctx::DB_RENDER_OVERRIDE, ctx::DB_RENDER_OVERRIDE2});
    for (u32 n = 0; n <= 7; ++n) {
        l.range(ctx::CB_COLORn_BASE[n], ctx::CB_COLORn_DCC_BASE[n]);
        l.add({ctx::CB_COLORn_BASE_EXT[n], ctx::CB_COLORn_CMASK_BASE_EXT[n],
               ctx::CB_COLORn_FMASK_BASE_EXT[n], ctx::CB_COLORn_DCC_BASE_EXT[n],
               ctx::CB_COLORn_ATTRIB2[n], ctx::CB_COLORn_ATTRIB3[n]});
    }
    l.add({ctx::PA_SC_SCREEN_SCISSOR_TL, ctx::PA_SC_SCREEN_SCISSOR_BR});
    for (u32 n = 0; n <= 31; ++n) {
        l.add({ctx::SPI_PS_INPUT_CNTL_n[n]});
    }
    for (u32 n = 0; n <= 5; ++n) {
        l.range(ctx::PA_CL_UCP_n_X[n], ctx::PA_CL_UCP_n_W[n]);
    }
    l.add({ctx::PA_CL_PROG_NEAR_CLIP_Z, unnamed(0x188), unnamed(0x189), unnamed(0x18A),
           unnamed(0x18B), unnamed(0x18C), unnamed(0x18D), unnamed(0x18E)});
    for (u32 n = 0; n <= 15; ++n) {
        l.add({ctx::PA_CL_VPORT_XSCALE_n[n], ctx::PA_CL_VPORT_YSCALE_n[n],
               ctx::PA_CL_VPORT_ZSCALE_n[n], ctx::PA_CL_VPORT_XOFFSET_n[n],
               ctx::PA_CL_VPORT_YOFFSET_n[n], ctx::PA_CL_VPORT_ZOFFSET_n[n],
               ctx::PA_SC_VPORT_SCISSOR_n_TL[n], ctx::PA_SC_VPORT_SCISSOR_n_BR[n],
               ctx::PA_SC_VPORT_ZMIN_n[n], ctx::PA_SC_VPORT_ZMAX_n[n]});
    }
    l.add({ctx::PA_SC_WINDOW_SCISSOR_TL, ctx::PA_SC_WINDOW_SCISSOR_BR});
    return l;
}

// A scissor's bottom-right corner at 2^14 in x and y (the largest window coordinate).
template <typename BR> constexpr u32 scissor_br_max() {
    return fld(BR::BR_X, 16384) | fld(BR::BR_Y, 16384);
}

Values cx_soc_values() {
    Values v;
    v[ctx::CB_COLOR_CONTROL] =
        fld(f::CB_COLOR_CONTROL::MODE, e::CB_NORMAL) | fld(f::CB_COLOR_CONTROL::ROP3, e::ROP3_COPY);
    v[ctx::CB_DCC_CONTROL] = fld(f::CB_DCC_CONTROL::OVERWRITE_COMBINER_WATERMARK, 2) |
                             bit(1); // bit 1: outside every gfx10 field
    v[ctx::DB_ALPHA_TO_MASK] = fld(f::DB_ALPHA_TO_MASK::ALPHA_TO_MASK_OFFSET0, 2) |
                               fld(f::DB_ALPHA_TO_MASK::ALPHA_TO_MASK_OFFSET1, 2) |
                               fld(f::DB_ALPHA_TO_MASK::ALPHA_TO_MASK_OFFSET2, 2) |
                               fld(f::DB_ALPHA_TO_MASK::ALPHA_TO_MASK_OFFSET3, 2);
    v[ctx::DB_COUNT_CONTROL] = fld(f::DB_COUNT_CONTROL::ZPASS_ENABLE, 1) |
                               fld(f::DB_COUNT_CONTROL::SLICE_EVEN_ENABLE, 1) |
                               fld(f::DB_COUNT_CONTROL::SLICE_ODD_ENABLE, 1);
    v[ctx::PA_CL_VTE_CNTL] = fld(f::PA_CL_VTE_CNTL::VPORT_X_SCALE_ENA, 1) |
                             fld(f::PA_CL_VTE_CNTL::VPORT_X_OFFSET_ENA, 1) |
                             fld(f::PA_CL_VTE_CNTL::VPORT_Y_SCALE_ENA, 1) |
                             fld(f::PA_CL_VTE_CNTL::VPORT_Y_OFFSET_ENA, 1) |
                             fld(f::PA_CL_VTE_CNTL::VPORT_Z_SCALE_ENA, 1) |
                             fld(f::PA_CL_VTE_CNTL::VPORT_Z_OFFSET_ENA, 1) |
                             fld(f::PA_CL_VTE_CNTL::VTX_W0_FMT, 1);
    // Every inside/outside combination of the four clip rects passes: clip rects have no effect.
    v[ctx::PA_SC_CLIPRECT_RULE] = all_ones(f::PA_SC_CLIPRECT_RULE::CLIP_RULE);
    v[ctx::PA_SC_CONSERVATIVE_RASTERIZATION_CNTL] =
        fld(f::PA_SC_CONSERVATIVE_RASTERIZATION_CNTL::OVERRIDE_OVER_RAST_INNER_TO_NORMAL, 1) |
        fld(f::PA_SC_CONSERVATIVE_RASTERIZATION_CNTL::OVERRIDE_UNDER_RAST_INNER_TO_NORMAL, 1);
    v[ctx::PA_SC_MODE_CNTL_0] = fld(f::PA_SC_MODE_CNTL_0::VPORT_SCISSOR_ENABLE, 1);
    v[ctx::PA_SC_MODE_CNTL_1] =
        fld(f::PA_SC_MODE_CNTL_1::MULTI_SHADER_ENGINE_PRIM_DISCARD_ENABLE, 1) |
        fld(f::PA_SC_MODE_CNTL_1::FORCE_EOV_CNTDWN_ENABLE, 1) |
        fld(f::PA_SC_MODE_CNTL_1::FORCE_EOV_REZ_ENABLE, 1);
    // Half-width 0.5 px in 12.4 fixed point: 1-pixel lines and points.
    v[ctx::PA_SU_LINE_CNTL] = fld(f::PA_SU_LINE_CNTL::WIDTH, 8);
    v[ctx::PA_SU_POINT_MINMAX] = all_ones(f::PA_SU_POINT_MINMAX::MAX_SIZE);
    v[ctx::PA_SU_POINT_SIZE] =
        fld(f::PA_SU_POINT_SIZE::HEIGHT, 8) | fld(f::PA_SU_POINT_SIZE::WIDTH, 8);
    // Minus 23 (8-bit two's complement), the mantissa width of a 32-bit float depth buffer.
    v[ctx::PA_SU_POLY_OFFSET_DB_FMT_CNTL] =
        fld(f::PA_SU_POLY_OFFSET_DB_FMT_CNTL::POLY_OFFSET_NEG_NUM_DB_BITS, 233) |
        fld(f::PA_SU_POLY_OFFSET_DB_FMT_CNTL::POLY_OFFSET_DB_IS_FLOAT_FMT, 1);
    v[ctx::PA_SU_SC_MODE_CNTL] =
        fld(f::PA_SU_SC_MODE_CNTL::POLYMODE_FRONT_PTYPE, e::X_DRAW_TRIANGLES) |
        fld(f::PA_SU_SC_MODE_CNTL::POLYMODE_BACK_PTYPE, e::X_DRAW_TRIANGLES);
    v[ctx::PA_SU_SMALL_PRIM_FILTER_CNTL] =
        fld(f::PA_SU_SMALL_PRIM_FILTER_CNTL::SMALL_PRIM_FILTER_ENABLE, 1) |
        fld(f::PA_SU_SMALL_PRIM_FILTER_CNTL::SRBSL_ENABLE, 1);
    v[ctx::PA_SU_VTX_CNTL] = fld(f::PA_SU_VTX_CNTL::PIX_CENTER, 1) |
                             fld(f::PA_SU_VTX_CNTL::ROUND_MODE, e::X_ROUND_TO_EVEN) |
                             fld(f::PA_SU_VTX_CNTL::QUANT_MODE, e::X_16_8_FIXED_POINT_1_256TH);
    v[ctx::VGT_GS_MAX_VERT_OUT] = fld(f::VGT_GS_MAX_VERT_OUT::MAX_VERT_OUT, 1024);
    v[ctx::VGT_GS_OUT_PRIM_TYPE] = fld(f::VGT_GS_OUT_PRIM_TYPE::OUTPRIM_TYPE, e::TRISTRIP);
    // Primitive-restart index = the largest 32-bit index (Mesa gives the register no fields).
    v[ctx::VGT_MULTI_PRIM_IB_RESET_INDX] = kAll32;
    v[ctx::VGT_SHADER_STAGES_EN] = fld(f::VGT_SHADER_STAGES_EN::PRIMGEN_EN, 1); // NGG on
    v[ctx::VGT_TESS_DISTRIBUTION] = fld(f::VGT_TESS_DISTRIBUTION::ACCUM_ISOLINE, 16) |
                                    fld(f::VGT_TESS_DISTRIBUTION::ACCUM_TRI, 16) |
                                    fld(f::VGT_TESS_DISTRIBUTION::ACCUM_QUAD, 16) |
                                    fld(f::VGT_TESS_DISTRIBUTION::DONUT_SPLIT, 8) |
                                    fld(f::VGT_TESS_DISTRIBUTION::TRAP_SPLIT, 4);
    v[ctx::PA_SC_AA_MASK_X0Y0_X1Y0] = all_ones(f::PA_SC_AA_MASK_X0Y0_X1Y0::AA_MASK_X0Y0) |
                                      all_ones(f::PA_SC_AA_MASK_X0Y0_X1Y0::AA_MASK_X1Y0);
    v[ctx::PA_SC_AA_MASK_X0Y1_X1Y1] = all_ones(f::PA_SC_AA_MASK_X0Y1_X1Y1::AA_MASK_X0Y1) |
                                      all_ones(f::PA_SC_AA_MASK_X0Y1_X1Y1::AA_MASK_X1Y1);
    v[ctx::PA_SC_BINNER_CNTL_0] = fld(f::PA_SC_BINNER_CNTL_0::CONTEXT_STATES_PER_BIN, 1) |
                                  fld(f::PA_SC_BINNER_CNTL_0::PERSISTENT_STATES_PER_BIN, 9) |
                                  fld(f::PA_SC_BINNER_CNTL_0::FPOVS_PER_BATCH, 63);
    v[ctx::PA_SC_BINNER_CNTL_1] = fld(f::PA_SC_BINNER_CNTL_1::MAX_ALLOC_COUNT, 128) |
                                  fld(f::PA_SC_BINNER_CNTL_1::MAX_PRIM_PER_BATCH, 1023);
    for (u32 n = 0; n <= 7; ++n) {
        v[ctx::CB_BLENDn_CONTROL[n]] = fld(f::CB_BLENDn_CONTROL::COLOR_SRCBLEND, e::BLEND_ONE) |
                                       fld(f::CB_BLENDn_CONTROL::ALPHA_SRCBLEND, e::BLEND_ONE) |
                                       fld(f::CB_BLENDn_CONTROL::SEPARATE_ALPHA_BLEND, 1);
    }
    for (u32 n = 0; n <= 3; ++n) {
        v[ctx::PA_SC_CLIPRECT_n_BR[n]] =
            fld(f::PA_SC_CLIPRECT_n_BR::BR_X, 8192) | fld(f::PA_SC_CLIPRECT_n_BR::BR_Y, 8192);
    }
    // Swizzle modes have no gfx10.json enum; 24 is the 64 KiB Z-order "X" mode of AMD addrlib.
    v[ctx::DB_Z_INFO] = fld(f::DB_Z_INFO::SW_MODE, 24) | fld(f::DB_Z_INFO::ZRANGE_PRECISION, 1);
    v[ctx::DB_STENCIL_INFO] =
        fld(f::DB_STENCIL_INFO::SW_MODE, 24) | fld(f::DB_STENCIL_INFO::TILE_STENCIL_DISABLE, 1);
    v[ctx::DB_HTILE_SURFACE] = fld(f::DB_HTILE_SURFACE::PIPE_ALIGNED, 1);
    v[unnamed(0x0EB)] = bits(8, 15) | bits(24, 31);
    v[unnamed(0x0EC)] = bit(16);
    for (u32 n = 0; n <= 15; ++n) {
        v[ctx::PA_SC_VPORT_SCISSOR_n_TL[n]] =
            fld(f::PA_SC_VPORT_SCISSOR_n_TL::WINDOW_OFFSET_DISABLE, 1);
        v[ctx::PA_SC_VPORT_SCISSOR_n_BR[n]] = scissor_br_max<f::PA_SC_VPORT_SCISSOR_n_BR>();
    }
    v[ctx::PA_SC_GENERIC_SCISSOR_TL] = fld(f::PA_SC_GENERIC_SCISSOR_TL::WINDOW_OFFSET_DISABLE, 1);
    v[ctx::PA_SC_WINDOW_SCISSOR_TL] = fld(f::PA_SC_WINDOW_SCISSOR_TL::WINDOW_OFFSET_DISABLE, 1);
    v[ctx::PA_SC_GENERIC_SCISSOR_BR] = scissor_br_max<f::PA_SC_GENERIC_SCISSOR_BR>();
    v[ctx::PA_SC_SCREEN_SCISSOR_BR] = scissor_br_max<f::PA_SC_SCREEN_SCISSOR_BR>();
    v[ctx::PA_SC_WINDOW_SCISSOR_BR] = scissor_br_max<f::PA_SC_WINDOW_SCISSOR_BR>();
    for (u32 n = 0; n <= 15; ++n) {
        v[ctx::PA_CL_VPORT_XSCALE_n[n]] = kFloatOne;
        v[ctx::PA_CL_VPORT_YSCALE_n[n]] = kFloatOne;
        v[ctx::PA_CL_VPORT_ZSCALE_n[n]] = kFloatOne;
    }
    v[ctx::PA_CL_GB_VERT_CLIP_ADJ] = kFloatOne;
    v[ctx::PA_CL_GB_VERT_DISC_ADJ] = kFloatOne;
    v[ctx::PA_CL_GB_HORZ_CLIP_ADJ] = kFloatOne;
    v[ctx::PA_CL_GB_HORZ_DISC_ADJ] = kFloatOne;
    for (u32 n = 0; n <= 7; ++n) {
        v[ctx::CB_COLORn_DCC_CONTROL[n]] =
            fld(f::CB_COLORn_DCC_CONTROL::MAX_UNCOMPRESSED_BLOCK_SIZE, e::MAX_BLOCK_SIZE_256B) |
            fld(f::CB_COLORn_DCC_CONTROL::MAX_COMPRESSED_BLOCK_SIZE, 2);
        // 27: the 64 KiB rotated "X" swizzle mode of AMD addrlib (no gfx10.json enum).
        v[ctx::CB_COLORn_ATTRIB3[n]] = fld(f::CB_COLORn_ATTRIB3::COLOR_SW_MODE, 27) |
                                       fld(f::CB_COLORn_ATTRIB3::FMASK_SW_MODE, 24) |
                                       fld(f::CB_COLORn_ATTRIB3::RESOURCE_LEVEL, 1);
    }
    return v;
}

// ---- SH-SOC and UC-SOC --------------------------------------------------------------------------

List sh_soc_list() {
    List l;
    l.add({sh::COMPUTE_PGM_RSRC1, sh::COMPUTE_PGM_RSRC2, sh::COMPUTE_PGM_RSRC3,
           sh::COMPUTE_RESOURCE_LIMITS, sh::COMPUTE_TMPRING_SIZE});
    // for n = 1..2: SPI_SHADER_PGM_RSRC{n}_GS, _HS, _PS
    l.add({sh::SPI_SHADER_PGM_RSRC1_GS, sh::SPI_SHADER_PGM_RSRC1_HS, sh::SPI_SHADER_PGM_RSRC1_PS});
    l.add({sh::SPI_SHADER_PGM_RSRC2_GS, sh::SPI_SHADER_PGM_RSRC2_HS, sh::SPI_SHADER_PGM_RSRC2_PS});
    l.range(sh::COMPUTE_USER_ACCUM_0, sh::COMPUTE_USER_ACCUM_3);
    l.add({sh::SPI_SHADER_PGM_RSRC3_HS, sh::SPI_SHADER_PGM_RSRC4_HS, sh::SPI_SHADER_PGM_RSRC3_GS,
           sh::SPI_SHADER_PGM_RSRC4_GS, sh::SPI_SHADER_PGM_RSRC3_PS, sh::SPI_SHADER_PGM_RSRC4_PS});
    l.add({sh::COMPUTE_PGM_LO, sh::COMPUTE_PGM_HI, sh::SPI_SHADER_PGM_LO_ES,
           sh::SPI_SHADER_PGM_HI_ES, sh::SPI_SHADER_PGM_LO_GS, sh::SPI_SHADER_PGM_HI_GS,
           sh::SPI_SHADER_PGM_LO_HS, sh::SPI_SHADER_PGM_HI_HS, sh::SPI_SHADER_PGM_LO_LS,
           sh::SPI_SHADER_PGM_HI_LS, sh::SPI_SHADER_PGM_LO_PS, sh::SPI_SHADER_PGM_HI_PS});
    l.range(sh::SPI_SHADER_USER_ACCUM_ESGS_0, sh::SPI_SHADER_USER_ACCUM_ESGS_3);
    l.range(sh::SPI_SHADER_USER_ACCUM_LSHS_0, sh::SPI_SHADER_USER_ACCUM_LSHS_3);
    l.range(sh::SPI_SHADER_USER_ACCUM_PS_0, sh::SPI_SHADER_USER_ACCUM_PS_3);
    l.add({sh::SPI_SHADER_USER_DATA_ADDR_LO_GS, sh::SPI_SHADER_USER_DATA_ADDR_HI_GS,
           sh::SPI_SHADER_USER_DATA_ADDR_LO_HS, sh::SPI_SHADER_USER_DATA_ADDR_HI_HS});
    for (u32 n = 0; n <= 15; ++n) {
        l.add({sh::COMPUTE_USER_DATA_n[n]});
    }
    for (u32 n = 0; n <= 31; ++n) {
        l.add({sh::SPI_SHADER_USER_DATA_GS_n[n]});
    }
    for (u32 n = 0; n <= 31; ++n) {
        l.add({sh::SPI_SHADER_USER_DATA_HS_n[n]});
    }
    for (u32 n = 0; n <= 31; ++n) {
        l.add({sh::SPI_SHADER_USER_DATA_PS_n[n]});
    }
    return l;
}

Values sh_soc_values() {
    Values v;
    v[sh::SPI_SHADER_PGM_RSRC3_HS] = all_ones(f::SPI_SHADER_PGM_RSRC3_HS::CU_EN);
    v[sh::SPI_SHADER_PGM_RSRC3_GS] = all_ones(f::SPI_SHADER_PGM_RSRC3_GS::CU_EN);
    v[sh::SPI_SHADER_PGM_RSRC3_PS] = all_ones(f::SPI_SHADER_PGM_RSRC3_PS::CU_EN);
    v[sh::SPI_SHADER_PGM_RSRC4_PS] = low_bits(f::SPI_SHADER_PGM_RSRC4_PS::CU_EN, 2); // CUs 0-1
    return v;
}

List uc_soc_list() {
    List l;
    l.add({uc::GDS_OA_ADDRESS, uc::GDS_OA_CNTL, uc::GDS_OA_COUNTER, uc::GE_CNTL, uc::GE_INDX_OFFSET,
           uc::GE_MULTI_PRIM_IB_RESET_EN});
    l.add({uc::GE_STEREO_CNTL, uc::GE_USER_VGPR_EN, unnamed(0x2BB), unnamed(0x2E4), unnamed(0x2E5),
           unnamed(0x2C4), unnamed(0x2C5), unnamed(0x2C6), unnamed(0x2C7), unnamed(0x2E8)});
    l.add({unnamed(0x2E9), unnamed(0x2CC), unnamed(0x2CD), unnamed(0x2CE), unnamed(0x2CF),
           unnamed(0x2BD), unnamed(0x2BC), unnamed(0x2E6), unnamed(0x2E7), unnamed(0x2C8),
           unnamed(0x2C9), unnamed(0x2CA)});
    l.add({unnamed(0x2CB), unnamed(0x2EA), unnamed(0x2EB), unnamed(0x2D0), unnamed(0x2D1),
           unnamed(0x2D2), unnamed(0x2D3), unnamed(0x2BF), unnamed(0x2BE), unnamed(0x384),
           unnamed(0x383), unnamed(0x248)});
    l.add({uc::VGT_PRIMITIVE_TYPE, uc::TA_CS_BC_BASE_ADDR, uc::TA_CS_BC_BASE_ADDR_HI});
    return l;
}

Values uc_soc_values() {
    Values v;
    v[unnamed(0x383)] = bit(6) | bit(30);
    return v;
}

// ---- internal descriptor lists, SoC family 0x840F00 ---------------------------------------------
// Given by dword offset; the gfx10 name at that offset is used where Mesa has one, and the
// static_asserts tie it to the description's offset.

static_assert(ctx::SPI_INTERP_CONTROL_0 == 0x1B5);
static_assert(sh::COMPUTE_DESTINATION_EN_SE0 == 0x216 && sh::COMPUTE_DESTINATION_EN_SE1 == 0x217 &&
              sh::COMPUTE_DESTINATION_EN_SE2 == 0x219 && sh::COMPUTE_DESTINATION_EN_SE3 == 0x21A);
static_assert(sh::COMPUTE_DISPATCH_TUNNEL == 0x27D && sh::COMPUTE_SHADER_CHKSUM == 0x22A);
static_assert(sh::COMPUTE_START_X == 0x204 && sh::COMPUTE_START_Y == 0x205 &&
              sh::COMPUTE_START_Z == 0x206);
static_assert(sh::SPI_SHADER_PGM_CHKSUM_GS == 0x080 && sh::SPI_SHADER_PGM_CHKSUM_HS == 0x100 &&
              sh::SPI_SHADER_PGM_CHKSUM_PS == 0x006);
static_assert(sh::SPI_SHADER_PGM_RSRC4_GS == 0x081 && sh::SPI_SHADER_PGM_RSRC4_HS == 0x101 &&
              sh::SPI_SHADER_PGM_RSRC4_PS == 0x001);
static_assert(ctx::DB_DFSM_CONTROL == 0x00E && ctx::GE_NGG_SUBGRP_CNTL == 0x2D3 &&
              ctx::PA_CL_VS_OUT_CNTL == 0x207 && ctx::PA_SC_NGG_MODE_CNTL == 0x314 &&
              ctx::SPI_VS_OUT_CONFIG == 0x1B1 && ctx::VGT_GS_INSTANCE_CNT == 0x2E4 &&
              ctx::VGT_GS_ONCHIP_CNTL == 0x291);
static_assert(uc::GE_PC_ALLOC == 0x260);

List int_soc_a_list() { return List().add({ctx::SPI_INTERP_CONTROL_0}); }
Values int_soc_a_values() {
    return {{ctx::SPI_INTERP_CONTROL_0, fld(f::SPI_INTERP_CONTROL_0::FLAT_SHADE_ENA, 1)}};
}

List int_soc_b_list() {
    return List().add({sh::COMPUTE_DESTINATION_EN_SE0, sh::COMPUTE_DESTINATION_EN_SE1,
                       sh::COMPUTE_DESTINATION_EN_SE2, sh::COMPUTE_DESTINATION_EN_SE3,
                       sh::COMPUTE_DISPATCH_TUNNEL, sh::COMPUTE_SHADER_CHKSUM, sh::COMPUTE_START_X,
                       sh::COMPUTE_START_Y, sh::COMPUTE_START_Z, sh::SPI_SHADER_PGM_CHKSUM_GS,
                       sh::SPI_SHADER_PGM_CHKSUM_HS, sh::SPI_SHADER_PGM_CHKSUM_PS});
}
Values int_soc_b_values() {
    Values v;
    // Every CU of both shader arrays of each shader engine (Mesa gives these no fields).
    v[sh::COMPUTE_DESTINATION_EN_SE0] = kAll32;
    v[sh::COMPUTE_DESTINATION_EN_SE1] = kAll32;
    v[sh::COMPUTE_DESTINATION_EN_SE2] = kAll32;
    v[sh::COMPUTE_DESTINATION_EN_SE3] = kAll32;
    v[sh::COMPUTE_DISPATCH_TUNNEL] = fld(f::COMPUTE_DISPATCH_TUNNEL::OFF_DELAY, 255) |
                                     fld(f::COMPUTE_DISPATCH_TUNNEL::IMMEDIATE, 1);
    return v;
}

// ---- version 0..3 set (other SoCs) --------------------------------------------------------------

Values cx_v0_3_values() {
    return with_overrides(
        cx_soc_values(),
        {{ctx::CB_DCC_CONTROL, fld(f::CB_DCC_CONTROL::OVERWRITE_COMBINER_WATERMARK, 2)},
         {ctx::PA_SC_BINNER_CNTL_0, fld(f::PA_SC_BINNER_CNTL_0::PERSISTENT_STATES_PER_BIN, 9) |
                                        fld(f::PA_SC_BINNER_CNTL_0::FPOVS_PER_BATCH, 63)}});
}

// ---- version 11 set
// ------------------------------------------------------------------------------

List cx_v11_list() {
    std::set<u32> remove = {ctx::DB_DEPTH_CLEAR,
                            ctx::DB_STENCIL_CLEAR,
                            unnamed(0x0F1),
                            unnamed(0x0F2),
                            ctx::DB_RESERVED_REG_1,
                            ctx::DB_RESERVED_REG_3,
                            ctx::PA_CL_PROG_NEAR_CLIP_Z,
                            unnamed(0x188),
                            unnamed(0x189),
                            unnamed(0x18A),
                            unnamed(0x18B),
                            unnamed(0x18C),
                            unnamed(0x18D),
                            unnamed(0x18E)};
    for (u32 n = 0; n <= 7; ++n) {
        remove.insert({ctx::CB_COLORn_PITCH[n], ctx::CB_COLORn_SLICE[n],
                       ctx::CB_COLORn_CMASK_SLICE[n], ctx::CB_COLORn_FMASK_SLICE[n]});
    }
    const std::vector<Insert> inserts = {
        {ctx::CB_DCC_CONTROL, {ctx::CB_BLENDn_CONTROL[0]}}, // a second CB_BLEND0_CONTROL entry
        {ctx::DB_SHADER_CONTROL, {unnamed(0x018)}},
        {ctx::PA_CL_OBJPRIM_ID_CNTL, {unnamed(0x212)}},
        {ctx::PA_SU_VTX_CNTL, {unnamed(0x1B7)}},
        {ctx::PA_SC_CLIPRECT_n_BR[3], {unnamed(0x0DB)}},
        {ctx::DB_DEPTH_SIZE_XY, {ctx::DB_DEPTH_CLEAR, ctx::DB_STENCIL_CLEAR}},
        {unnamed(0x0EC), {unnamed(0x0F1), unnamed(0x0F2)}},
    };
    return edited(cx_soc_list(), remove, inserts);
}

Values cx_v11_values() {
    return with_overrides(
        cx_soc_values(),
        {{ctx::CB_DCC_CONTROL, fld(f::CB_DCC_CONTROL::OVERWRITE_COMBINER_WATERMARK, 4)},
         {ctx::DB_EQAA, fld(f::DB_EQAA::HIGH_QUALITY_INTERSECTIONS, 1)},
         {unnamed(0x212), bit(10) | bit(13)},
         // Single bits outside every gfx10 field.
         {ctx::PA_SC_AA_CONFIG, bit(28)},
         {ctx::DB_RENDER_OVERRIDE2, bit(28)},
         {ctx::PA_STEREO_CNTL, bit(26)},
         {ctx::VGT_DRAW_PAYLOAD_CNTL, bit(6)},
         // No isoline accumulation.
         {ctx::VGT_TESS_DISTRIBUTION, fld(f::VGT_TESS_DISTRIBUTION::ACCUM_TRI, 16) |
                                          fld(f::VGT_TESS_DISTRIBUTION::ACCUM_QUAD, 16) |
                                          fld(f::VGT_TESS_DISTRIBUTION::DONUT_SPLIT, 8) |
                                          fld(f::VGT_TESS_DISTRIBUTION::TRAP_SPLIT, 4)},
         // Binning off with the new scan converter.
         {ctx::PA_SC_BINNER_CNTL_0,
          fld(f::PA_SC_BINNER_CNTL_0::BINNING_MODE, e::DISABLE_BINNING_USE_NEW_SC) |
              fld(f::PA_SC_BINNER_CNTL_0::PERSISTENT_STATES_PER_BIN, 9) |
              fld(f::PA_SC_BINNER_CNTL_0::DISABLE_START_OF_PRIM, 1) |
              fld(f::PA_SC_BINNER_CNTL_0::FPOVS_PER_BATCH, 63)}});
}

List sh_v11_list() {
    return edited(
        sh_soc_list(),
        {sh::SPI_SHADER_PGM_RSRC4_HS, sh::SPI_SHADER_PGM_RSRC4_GS, sh::SPI_SHADER_PGM_RSRC4_PS},
        {{sh::COMPUTE_RESOURCE_LIMITS, {sh::COMPUTE_SHADER_CHKSUM}},
         {sh::COMPUTE_TMPRING_SIZE, {sh::SPI_SHADER_PGM_CHKSUM_GS, sh::SPI_SHADER_PGM_CHKSUM_PS}},
         {sh::SPI_SHADER_PGM_HI_PS, {unnamed(0x280)}}});
}

Values sh_v11_values() {
    // The checksum registers have no gfx10 fields: bits 8..31 set.
    return with_overrides(
        sh_soc_values(),
        {{sh::COMPUTE_SHADER_CHKSUM, bits(8, 31)},
         {sh::SPI_SHADER_PGM_CHKSUM_GS, bits(8, 31)},
         {sh::SPI_SHADER_PGM_CHKSUM_PS, bits(8, 31)},
         {sh::SPI_SHADER_PGM_RSRC3_HS, low_bits(f::SPI_SHADER_PGM_RSRC3_HS::CU_EN, 14)},
         {sh::SPI_SHADER_PGM_RSRC3_GS, low_bits(f::SPI_SHADER_PGM_RSRC3_GS::CU_EN, 14)}});
}

List uc_v11_list() {
    List l;
    l.add({uc::GDS_OA_ADDRESS, uc::GDS_OA_CNTL, uc::GDS_OA_COUNTER, uc::GE_CNTL, uc::GE_INDX_OFFSET,
           uc::GE_MULTI_PRIM_IB_RESET_EN});
    l.add({uc::GE_STEREO_CNTL, uc::GE_USER_VGPR_EN, unnamed(0x263), unnamed(0x2BB), unnamed(0x384),
           unnamed(0x383), unnamed(0x248), uc::VGT_PRIMITIVE_TYPE});
    l.add({uc::TA_CS_BC_BASE_ADDR, uc::TA_CS_BC_BASE_ADDR_HI});
    // The unnamed 0x2BC..0x2EB block, regrouped: 0x2E4..0x2EB, 0x2C4..0x2D3, 0x2BC..0x2BF.
    l.range(unnamed(0x2E4), unnamed(0x2EB));
    l.range(unnamed(0x2C4), unnamed(0x2D3));
    l.range(unnamed(0x2BC), unnamed(0x2BF));
    l.range(unnamed(0x035), unnamed(0x03C));
    l.add({unnamed(0x0A2)});
    l.range(uc::GE_USER_VGPR1, uc::GE_USER_VGPR3);
    return l;
}

List int_v11_1_list() {
    return List().add({ctx::DB_DFSM_CONTROL, unnamed(0x019), ctx::GE_NGG_SUBGRP_CNTL,
                       ctx::PA_CL_VS_OUT_CNTL, ctx::PA_SC_NGG_MODE_CNTL, ctx::SPI_INTERP_CONTROL_0,
                       ctx::SPI_VS_OUT_CONFIG, ctx::VGT_GS_INSTANCE_CNT, ctx::VGT_GS_ONCHIP_CNTL});
}
Values int_v11_1_values() {
    Values v;
    v[ctx::DB_DFSM_CONTROL] = fld(f::DB_DFSM_CONTROL::PUNCHOUT_MODE, e::FORCE_OFF);
    v[unnamed(0x019)] = bits(0, 1) | bits(4, 7);
    v[ctx::PA_SC_NGG_MODE_CNTL] = fld(f::PA_SC_NGG_MODE_CNTL::MAX_DEALLOCS_IN_WAVE, 514);
    v[ctx::SPI_INTERP_CONTROL_0] = fld(f::SPI_INTERP_CONTROL_0::FLAT_SHADE_ENA, 1);
    return v;
}

List int_v11_2_list() {
    return edited(
        int_soc_b_list(),
        {sh::COMPUTE_SHADER_CHKSUM, sh::SPI_SHADER_PGM_CHKSUM_GS, sh::SPI_SHADER_PGM_CHKSUM_PS},
        {{sh::SPI_SHADER_PGM_CHKSUM_HS,
          {sh::SPI_SHADER_PGM_RSRC4_GS, sh::SPI_SHADER_PGM_RSRC4_HS,
           sh::SPI_SHADER_PGM_RSRC4_PS}}});
}
Values int_v11_2_values() {
    return with_overrides(
        int_soc_b_values(),
        {{sh::SPI_SHADER_PGM_CHKSUM_HS, bits(8, 31)}, // no gfx10 fields
         {sh::SPI_SHADER_PGM_RSRC4_GS, low_bits(f::SPI_SHADER_PGM_RSRC4_GS::CU_EN, 14)},
         {sh::SPI_SHADER_PGM_RSRC4_HS, low_bits(f::SPI_SHADER_PGM_RSRC4_HS::CU_EN, 14)},
         {sh::SPI_SHADER_PGM_RSRC4_PS, low_bits(f::SPI_SHADER_PGM_RSRC4_PS::CU_EN, 14)}});
}

List int_v11_3_list() { return List().add({uc::GE_PC_ALLOC}); }

// ---- the table set
// --------------------------------------------------------------------------------

struct TableInfo {
    const char *name;
    std::uint64_t image_address; // where the original module stores it
};
// Image addresses: interoperability facts of the description (descriptor table pointers).
constexpr TableInfo kInfo[kTableCount] = {
    {"CX-SOC", 0x34120},    {"SH-SOC", 0x35178},    {"UC-SOC", 0x35680},  {"INT-SOC-A", 0x34018},
    {"INT-SOC-B", 0x34020}, {"CX-V0_3", 0x379A0},   {"SH-V0_3", 0x389F8}, {"UC-V0_3", 0x38F00},
    {"CX-V11", 0x43DA8},    {"SH-V11", 0x44CD8},    {"UC-V11", 0x451E8},  {"INT-V11-1", 0x43BF0},
    {"INT-V11-2", 0x43C38}, {"INT-V11-3", 0x43C98},
};

std::vector<RegPair> build(TableId id) {
    switch (id) {
    case TableId::CxSoc:
        return make(cx_soc_list(), cx_soc_values());
    case TableId::ShSoc:
    case TableId::ShV0_3: // identical to SH-SOC
        return make(sh_soc_list(), sh_soc_values());
    case TableId::UcSoc:
    case TableId::UcV0_3: // identical to UC-SOC
        return make(uc_soc_list(), uc_soc_values());
    case TableId::IntSocA:
        return make(int_soc_a_list(), int_soc_a_values());
    case TableId::IntSocB:
        return make(int_soc_b_list(), int_soc_b_values());
    case TableId::CxV0_3: // same list as CX-SOC
        return make(cx_soc_list(), cx_v0_3_values());
    case TableId::CxV11:
        return make(cx_v11_list(), cx_v11_values());
    case TableId::ShV11:
        return make(sh_v11_list(), sh_v11_values());
    case TableId::UcV11:
        return make(uc_v11_list(), uc_soc_values()); // same single non-zero entry as UC-SOC
    case TableId::IntV11_1:
        return make(int_v11_1_list(), int_v11_1_values());
    case TableId::IntV11_2:
        return make(int_v11_2_list(), int_v11_2_values());
    case TableId::IntV11_3:
        return make(int_v11_3_list(), {}); // every entry zero
    case TableId::Count:
        break;
    }
    return {};
}

// ---- CU-ROWS
// -------------------------------------------------------------------------------------

// One console-variant row in column order. `se` is the value of the four compute SE masks.
struct CuRow {
    u32 se;
    u32 rsrc3_hs, rsrc3_gs, rsrc3_ps;
    u32 rsrc4_hs, rsrc4_gs, rsrc4_ps;
};

// Shader array 0: CUs 0 to 9; shader array 1: CUs 0 to 7 (low/high 16 bits by AMD convention;
// Mesa gives COMPUTE_DESTINATION_EN_SEn no fields).
constexpr u32 kSeSoc840FC0 = bits(0, 9) | bits(16, 23);

using R3HS = f::SPI_SHADER_PGM_RSRC3_HS;
using R3GS = f::SPI_SHADER_PGM_RSRC3_GS;
using R3PS = f::SPI_SHADER_PGM_RSRC3_PS;
using R4HS = f::SPI_SHADER_PGM_RSRC4_HS;
using R4GS = f::SPI_SHADER_PGM_RSRC4_GS;
using R4PS = f::SPI_SHADER_PGM_RSRC4_PS;

constexpr CuRow kCuRows[kCuRowCount] = {
    // 0: ordinary console, SDK version up to 12.
    {kAll32, all_ones(R3HS::CU_EN), all_ones(R3GS::CU_EN), all_ones(R3PS::CU_EN), 0, 0,
     low_bits(R4PS::CU_EN, 2)},
    // 1: SoC family 0x840FC0, up to 12.
    {kSeSoc840FC0, low_bits(R3HS::CU_EN, 8), low_bits(R3GS::CU_EN, 8), low_bits(R3PS::CU_EN, 10),
     low_bits(R4HS::CU_EN, 8), low_bits(R4GS::CU_EN, 8), low_bits(R4PS::CU_EN, 8)},
    // 2: the external transcode check true, up to 12.
    {kAll32, low_bits(R3HS::CU_EN, 14), low_bits(R3GS::CU_EN, 14), all_ones(R3PS::CU_EN),
     low_bits(R4HS::CU_EN, 14), low_bits(R4GS::CU_EN, 14), low_bits(R4PS::CU_EN, 14)},
    // 3: ordinary console, SDK version above 12.
    {kAll32, all_ones(R3HS::CU_EN), all_ones(R3GS::CU_EN), all_ones(R3PS::CU_EN),
     low_bits(R4HS::CU_EN, 2), low_bits(R4GS::CU_EN, 1), low_bits(R4PS::CU_EN, 2)},
    // 4: SoC family 0x840FC0, above 12.
    {kSeSoc840FC0, low_bits(R3HS::CU_EN, 10), low_bits(R3GS::CU_EN, 9), low_bits(R3PS::CU_EN, 10),
     low_bits(R4HS::CU_EN, 8), low_bits(R4GS::CU_EN, 8), low_bits(R4PS::CU_EN, 8)},
    // 5: the external transcode check true, above 12.
    {kAll32, all_ones(R3HS::CU_EN), low_bits(R3GS::CU_EN, 15), all_ones(R3PS::CU_EN),
     low_bits(R4HS::CU_EN, 14), low_bits(R4GS::CU_EN, 14), low_bits(R4PS::CU_EN, 14)},
};

std::vector<RegPair> build_cu_rows() {
    std::vector<RegPair> out;
    for (const CuRow &r : kCuRows) {
        const RegPair row[kCuColumnCount] = {
            {sh::COMPUTE_DESTINATION_EN_SE0, r.se},    {sh::COMPUTE_DESTINATION_EN_SE1, r.se},
            {sh::COMPUTE_DESTINATION_EN_SE2, r.se},    {sh::COMPUTE_DESTINATION_EN_SE3, r.se},
            {sh::SPI_SHADER_PGM_RSRC3_HS, r.rsrc3_hs}, {sh::SPI_SHADER_PGM_RSRC3_GS, r.rsrc3_gs},
            {sh::SPI_SHADER_PGM_RSRC3_PS, r.rsrc3_ps}, {sh::SPI_SHADER_PGM_RSRC4_HS, r.rsrc4_hs},
            {sh::SPI_SHADER_PGM_RSRC4_GS, r.rsrc4_gs}, {sh::SPI_SHADER_PGM_RSRC4_PS, r.rsrc4_ps},
        };
        out.insert(out.end(), std::begin(row), std::end(row));
    }
    return out;
}

// ---- PRIM-CLASS
// ----------------------------------------------------------------------------------

// Class values: the GS output primitive type (VGT_GS_OUT_PRIM_TYPE.OUTPRIM_TYPE) to assume.
constexpr u32 kPoints = e::POINTLIST;
constexpr u32 kLines = e::LINESTRIP;
constexpr u32 kTriangles = e::TRISTRIP;
// The two rectangle classes keep the older numbering: 3 = two-dimensional rectangle (gfx10.json
// names value 3 RECTLIST), 4 = rectangle list (no gfx10.json name).
constexpr u32 kRect2d = 3;
constexpr u32 kRectList = 4;

std::array<u32, kPrimClassCount> build_prim_classes() {
    // Index = AGC primitive type - 1, and the AGC type is the draw-initiator type
    // (VGT_DI_PRIM_TYPE); unused slots, patches and flagged/adjacency triangles are triangles.
    std::array<u32, kPrimClassCount> c{};
    c.fill(kTriangles);
    c[e::DI_PT_POINTLIST - 1] = kPoints;
    c[e::DI_PT_LINELIST - 1] = kLines;
    c[e::DI_PT_LINESTRIP - 1] = kLines;
    c[e::DI_PT_LINELIST_ADJ - 1] = kLines;
    c[e::DI_PT_LINESTRIP_ADJ - 1] = kLines;
    c[e::DI_PT_LINELOOP - 1] = kLines;
    c[e::DI_PT_2D_RECTANGLE - 1] = kRect2d;
    c[e::DI_PT_RECTLIST - 1] = kRectList;
    return c;
}
static_assert(e::DI_PT_LINELOOP == kPrimClassCount);

} // namespace

const char *table_name(TableId id) {
    const int i = static_cast<int>(id);
    return i >= 0 && i < kTableCount ? kInfo[i].name : "?";
}

std::span<const RegPair> table(TableId id) {
    static const auto all = [] {
        std::array<std::vector<RegPair>, kTableCount> t;
        for (int i = 0; i < kTableCount; ++i) {
            t[static_cast<std::size_t>(i)] = build(static_cast<TableId>(i));
        }
        return t;
    }();
    const int i = static_cast<int>(id);
    if (i < 0 || i >= kTableCount) {
        return {};
    }
    return all[static_cast<std::size_t>(i)];
}

std::uint64_t table_image_address(TableId id) {
    const int i = static_cast<int>(id);
    return i >= 0 && i < kTableCount ? kInfo[i].image_address : 0;
}

bool table_at_image_address(std::uint64_t vaddr, TableId &out) {
    for (int i = 0; i < kTableCount; ++i) {
        if (kInfo[i].image_address == vaddr) {
            out = static_cast<TableId>(i);
            return true;
        }
    }
    return false;
}

std::span<const RegPair> cu_rows() {
    static const std::vector<RegPair> rows = build_cu_rows();
    return rows;
}

std::span<const std::uint32_t> prim_classes() {
    static const std::array<u32, kPrimClassCount> classes = build_prim_classes();
    return classes;
}

} // namespace bc5::reimpl::agc::tables
