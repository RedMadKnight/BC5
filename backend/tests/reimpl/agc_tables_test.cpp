// SPDX-License-Identifier: GPL-2.0-only
// Tests of the own-source data of the libSceAgc / libSceAgcDriver re-creations: the register
// default tables, CU-ROWS, PRIM-CLASS, the driver's default context state, the trap handler, the
// fill shader header, and the data-source switches (own data by default, module-file data only
// with BC5_REIMPL_FW_DATA, BC5_REIMPL_FW_COMPARE reports differences). Every "module file" here is
// synthetic.
#include "bc5/reimpl/agc.hpp"
#include "bc5/reimpl/agc_driver_tables.hpp"
#include "bc5/reimpl/agc_fill_shader.hpp"
#include "bc5/reimpl/agc_regdb.hpp"
#include "bc5/reimpl/agc_tables.hpp"
#include "bc5/reimpl/data_source.hpp"

#include <catch2/catch_test_macros.hpp>

#include <algorithm>
#include <cstring>
#include <map>
#include <string>
#include <vector>

namespace agc = bc5::reimpl::agc;
namespace tables = bc5::reimpl::agc::tables;
namespace drv = bc5::reimpl::agc_driver::tables;
namespace rdb = bc5::reimpl::regdb;
using tables::TableId;
using u32 = std::uint32_t;
using u64 = std::uint64_t;

namespace {

// Field value by explicit bit positions (independent of the generated field constants).
u32 get(u32 v, u32 lo, u32 hi) {
    const u32 w = hi - lo + 1;
    return w >= 32 ? v : (v >> lo) & ((1u << w) - 1u);
}

std::size_t nonzero(std::span<const agc::RegPair> t) {
    return static_cast<std::size_t>(
        std::count_if(t.begin(), t.end(), [](const agc::RegPair &p) { return p.value != 0; }));
}

u32 value_of(TableId id, u32 offset) {
    for (const agc::RegPair &p : tables::table(id)) {
        if (p.offset == offset) {
            return p.value;
        }
    }
    FAIL("offset not in table");
    return 0;
}

std::size_t index_of(TableId id, u32 offset) {
    const auto t = tables::table(id);
    for (std::size_t i = 0; i < t.size(); ++i) {
        if (t[i].offset == offset) {
            return i;
        }
    }
    return t.size();
}

// A synthetic module file for both modules.
class FakeFile : public bc5::reimpl::FirmwareData {
  public:
    void put(const std::string &module, u64 vaddr, const void *data, std::size_t size) {
        auto &v = blocks_[{module, vaddr}];
        v.assign(static_cast<const std::uint8_t *>(data),
                 static_cast<const std::uint8_t *>(data) + size);
    }
    const std::uint8_t *get(const char *module, u64 vaddr, u64 size) override {
        for (auto &[key, bytes] : blocks_) {
            if (key.first == module && vaddr >= key.second &&
                vaddr + size <= key.second + bytes.size()) {
                return bytes.data() + (vaddr - key.second);
            }
        }
        return nullptr;
    }

  private:
    std::map<std::pair<std::string, u64>, std::vector<std::uint8_t>> blocks_;
};

std::vector<std::string> g_log;
void capture(const char *, const char *message) { g_log.emplace_back(message); }

struct Env {
    Env() {
        agc::testing::reset();
        agc::testing::clear_imports();
        bc5::reimpl::set_firmware_data(nullptr);
        bc5::reimpl::set_data_switches({});
        g_log.clear();
        bc5::reimpl::set_log(&capture);
    }
    ~Env() {
        bc5::reimpl::set_firmware_data(nullptr);
        bc5::reimpl::reset_data_switches();
        bc5::reimpl::set_log(nullptr);
        agc::testing::reset();
    }
    Env(const Env &) = delete;
    Env &operator=(const Env &) = delete;
};

std::size_t logged(const std::string &needle) {
    return static_cast<std::size_t>(std::count_if(g_log.begin(), g_log.end(), [&](const auto &l) {
        return l.find(needle) != std::string::npos;
    }));
}

} // namespace

TEST_CASE("own AGC tables: entry and non-zero counts", "[reimpl-tables]") {
    struct Expect {
        TableId id;
        std::size_t entries, nonzero;
    };
    const Expect expect[] = {
        {TableId::CxSoc, 523, 147}, {TableId::ShSoc, 161, 4},  {TableId::UcSoc, 43, 1},
        {TableId::IntSocA, 1, 1},   {TableId::IntSocB, 12, 5}, {TableId::CxV0_3, 523, 147},
        {TableId::ShV0_3, 161, 4},  {TableId::UcV0_3, 43, 1},  {TableId::CxV11, 486, 154},
        {TableId::ShV11, 162, 6},   {TableId::UcV11, 56, 1},   {TableId::IntV11_1, 9, 4},
        {TableId::IntV11_2, 12, 9}, {TableId::IntV11_3, 1, 0},
        // tables2.md, table summary
        {TableId::CxOther, 488, 151}, {TableId::ShOther, 162, 6}, {TableId::UcOther, 56, 1},
        {TableId::IntOtherCx, 8, 3}, {TableId::IntOtherSh, 12, 7}, {TableId::IntOtherUc, 1, 0},
        {TableId::FourthOther, 6, 0}, {TableId::IntV0_3Cx, 1, 1}, {TableId::IntV0_3Sh, 12, 5},
        {TableId::FourthV0_3, 4, 0}, {TableId::CxV4, 488, 146}, {TableId::ShV4, 158, 3},
        {TableId::UcV4, 43, 1}, {TableId::IntV4Cx, 2, 2}, {TableId::IntV4Sh, 15, 6},
        {TableId::FourthV4, 4, 0}, {TableId::CxV5_6, 491, 147}, {TableId::ShV5_6, 159, 3},
        {TableId::UcV5_6, 75, 1}, {TableId::IntV5_6Cx, 3, 3}, {TableId::IntV5_6Sh, 15, 6},
        {TableId::FourthV5_6, 6, 0}, {TableId::CxV7, 489, 147}, {TableId::ShV7, 159, 3},
        {TableId::UcV7, 55, 1}, {TableId::IntV7Cx, 4, 4}, {TableId::IntV7Sh, 15, 6},
        {TableId::FourthV7, 6, 0}, {TableId::CxV8, 489, 147}, {TableId::ShV8, 159, 3},
        {TableId::UcV8, 55, 1}, {TableId::IntV8Cx, 4, 4}, {TableId::IntV8Sh, 15, 6},
        {TableId::FourthV8, 6, 0}, {TableId::CxV9, 489, 147}, {TableId::ShV9, 160, 3},
        {TableId::UcV9, 55, 1}, {TableId::IntV9Cx, 4, 4}, {TableId::IntV9Sh, 14, 6},
        {TableId::IntV9Uc, 1, 0}, {TableId::FourthV9, 6, 0}, {TableId::CxV10_12, 482, 148},
        {TableId::ShV10_12, 159, 3}, {TableId::UcV10_12, 55, 1}, {TableId::IntV10_12Cx, 9, 4},
        {TableId::IntV10_12Sh, 15, 6}, {TableId::IntV10_12Uc, 1, 0},
        {TableId::FourthV10_12, 6, 0}, {TableId::FourthSoc, 4, 0}, {TableId::FourthV11, 6, 0},
    };
    static_assert(tables::kTableCount == 14 + 50);
    REQUIRE(std::size(expect) == static_cast<std::size_t>(tables::kTableCount));
    for (const Expect &e : expect) {
        INFO(tables::table_name(e.id));
        CHECK(tables::table(e.id).size() == e.entries);
        CHECK(nonzero(tables::table(e.id)) == e.nonzero);
    }
}

TEST_CASE("own AGC tables: the counts the selector expects", "[reimpl-tables]") {
    // The selector's counts per image address (agc_system.cpp set_for, from the description).
    CHECK(tables::table(TableId::CxSoc).size() == 0x20B);
    CHECK(tables::table(TableId::ShSoc).size() == 0xA1);
    CHECK(tables::table(TableId::UcSoc).size() == 0x2B);
    CHECK(tables::table(TableId::CxV11).size() == 0x1E6);
    CHECK(tables::table(TableId::ShV11).size() == 0xA2);
    CHECK(tables::table(TableId::UcV11).size() == 0x38);
    TableId id{};
    REQUIRE(tables::table_at_image_address(0x34120, id));
    CHECK(id == TableId::CxSoc);
    REQUIRE(tables::table_at_image_address(0x38F00, id));
    CHECK(id == TableId::UcV0_3);
    CHECK_FALSE(tables::table_at_image_address(0x12345, id));
    // tables2.md's addresses: every table has its own, and each maps back to its table.
    const std::pair<u64, TableId> more[] = {
        {0x35E38, TableId::CxOther},     {0x36D78, TableId::ShOther},
        {0x37288, TableId::UcOther},     {0x35C90, TableId::IntOtherCx},
        {0x35CD0, TableId::IntOtherSh},  {0x35D30, TableId::IntOtherUc},
        {0x35E08, TableId::FourthOther}, {0x37898, TableId::IntV0_3Cx},
        {0x37980, TableId::FourthV0_3},  {0x39660, TableId::CxV4},
        {0x3C668, TableId::UcV5_6},      {0x3CDA8, TableId::IntV7Cx},
        {0x40530, TableId::IntV9Uc},     {0x42218, TableId::CxV10_12},
        {0x421E8, TableId::FourthV10_12}, {0x34100, TableId::FourthSoc},
        {0x43D78, TableId::FourthV11},
    };
    for (const auto &[vaddr, want] : more) {
        REQUIRE(tables::table_at_image_address(vaddr, id));
        CHECK(id == want);
    }
    for (int i = 0; i < tables::kTableCount; ++i) {
        const auto t = static_cast<TableId>(i);
        REQUIRE(tables::table_image_address(t) != 0);
        REQUIRE(tables::table_at_image_address(tables::table_image_address(t), id));
        CHECK(id == t);
    }
}

namespace {

std::vector<u32> offsets_of(TableId id) {
    std::vector<u32> o;
    for (const agc::RegPair &p : tables::table(id)) {
        o.push_back(p.offset);
    }
    return o;
}

std::size_t occurrences(TableId id, u32 offset) {
    const auto t = tables::table(id);
    return static_cast<std::size_t>(std::count_if(
        t.begin(), t.end(), [offset](const agc::RegPair &p) { return p.offset == offset; }));
}

// The k-th entry (from 1) with this register; table size when absent.
std::size_t index_of_k(TableId id, u32 offset, std::size_t k) {
    const auto t = tables::table(id);
    for (std::size_t i = 0; i < t.size(); ++i) {
        if (t[i].offset == offset && --k == 0) {
            return i;
        }
    }
    return t.size();
}

bool same_pairs(TableId a, TableId b) {
    const auto x = tables::table(a);
    const auto y = tables::table(b);
    return x.size() == y.size() && std::equal(x.begin(), x.end(), y.begin(), [](auto &p, auto &q) {
               return p.offset == q.offset && p.value == q.value;
           });
}

} // namespace

TEST_CASE("own AGC tables (tables2.md): the second game's group OTHER", "[reimpl-tables]") {
    namespace ctx = rdb::ctx;
    namespace sh = rdb::sh;
    // CX-OTHER = CX-V11 minus 0x018, 0x212, 0x1B7, plus a second DB_HTILE_SURFACE right after
    // DB_EQAA and four extra 0x0DB entries.
    const auto cx = tables::table(TableId::CxOther);
    REQUIRE(cx.size() == 488);
    CHECK(index_of(TableId::CxOther, 0x018) == cx.size());
    CHECK(index_of(TableId::CxOther, 0x212) == cx.size());
    CHECK(index_of(TableId::CxOther, 0x1B7) == cx.size());
    CHECK(occurrences(TableId::CxV11, ctx::DB_HTILE_SURFACE) == 1);
    CHECK(occurrences(TableId::CxOther, ctx::DB_HTILE_SURFACE) == 2);
    CHECK(cx[index_of(TableId::CxOther, ctx::DB_EQAA) + 1].offset == ctx::DB_HTILE_SURFACE);
    CHECK(occurrences(TableId::CxV11, 0x0DB) == 1);
    CHECK(occurrences(TableId::CxOther, 0x0DB) == 5);
    CHECK(cx[index_of(TableId::CxOther, ctx::DB_SHADER_CONTROL) + 1].offset == 0x0DBu);
    CHECK(cx[index_of(TableId::CxOther, ctx::DB_STENCIL_CONTROL) + 1].offset == 0x0DBu);
    CHECK(cx[index_of(TableId::CxOther, ctx::PA_SU_VTX_CNTL) + 1].offset == 0x0DBu);
    // The third 0x0DB is the one right after PA_CL_OBJPRIM_ID_CNTL (where CX-V11 has 0x212) and
    // holds bit 13; the others are zero.
    const std::size_t third = index_of_k(TableId::CxOther, 0x0DB, 3);
    REQUIRE(third < cx.size());
    CHECK(cx[third - 1].offset == ctx::PA_CL_OBJPRIM_ID_CNTL);
    CHECK(cx[third].value == 0x2000u);
    for (std::size_t k : {1u, 2u, 4u, 5u}) {
        CHECK(cx[index_of_k(TableId::CxOther, 0x0DB, k)].value == 0u);
    }
    // Both DB_HTILE_SURFACE entries: PIPE_ALIGNED (bit 18), the inserted one by the value rule.
    CHECK(cx[index_of_k(TableId::CxOther, ctx::DB_HTILE_SURFACE, 1)].value == 0x40000u);
    CHECK(cx[index_of_k(TableId::CxOther, ctx::DB_HTILE_SURFACE, 2)].value == 0x40000u);
    // File values zero here (non-zero in CX-V11).
    for (u32 o : {ctx::DB_EQAA, ctx::PA_SC_AA_CONFIG, ctx::VGT_DRAW_PAYLOAD_CNTL,
                  ctx::DB_RENDER_OVERRIDE2}) {
        CHECK(value_of(TableId::CxV11, o) != 0u);
        CHECK(value_of(TableId::CxOther, o) == 0u);
    }
    // Everything else as CX-V11 (PA_STEREO_CNTL bit 26 stays).
    CHECK(value_of(TableId::CxOther, ctx::PA_STEREO_CNTL) == 0x04000000u);
    CHECK(value_of(TableId::CxOther, ctx::CB_DCC_CONTROL) ==
          value_of(TableId::CxV11, ctx::CB_DCC_CONTROL));

    // SH-OTHER: SH-V11's list; checksums the low 24 bits instead of the high 24; CU_EN all ones.
    CHECK(offsets_of(TableId::ShOther) == offsets_of(TableId::ShV11));
    for (u32 o : {sh::COMPUTE_SHADER_CHKSUM, sh::SPI_SHADER_PGM_CHKSUM_GS,
                  sh::SPI_SHADER_PGM_CHKSUM_PS}) {
        CHECK(value_of(TableId::ShV11, o) == 0xFFFFFF00u);
        CHECK(value_of(TableId::ShOther, o) == 0x00FFFFFFu);
    }
    CHECK(value_of(TableId::ShOther, sh::SPI_SHADER_PGM_RSRC3_HS) == 0xFFFF0000u);
    CHECK(value_of(TableId::ShOther, sh::SPI_SHADER_PGM_RSRC3_GS) == 0x0000FFFFu);
    CHECK(value_of(TableId::ShOther, sh::SPI_SHADER_PGM_RSRC3_PS) == 0x0000FFFFu);

    // UC-OTHER = UC-V11 without 0x263, a second 0x0A2 right after GE_USER_VGPR_EN.
    const auto uc = tables::table(TableId::UcOther);
    CHECK(index_of(TableId::UcV11, 0x263) < tables::table(TableId::UcV11).size());
    CHECK(index_of(TableId::UcOther, 0x263) == uc.size());
    CHECK(uc[index_of(TableId::UcOther, rdb::uc::GE_USER_VGPR_EN) + 1].offset == 0x0A2u);
    CHECK(occurrences(TableId::UcOther, 0x0A2) == 2);
    CHECK(value_of(TableId::UcOther, 0x383) == 0x40000040u);

    // INT-OTHER-CX = INT-V11-1 without 0x019.
    std::vector<u32> i1 = offsets_of(TableId::IntV11_1);
    i1.erase(std::find(i1.begin(), i1.end(), 0x019u));
    CHECK(offsets_of(TableId::IntOtherCx) == i1);
    CHECK(get(value_of(TableId::IntOtherCx, ctx::PA_SC_NGG_MODE_CNTL), 0, 10) == 514u);
    // INT-OTHER-SH: INT-V11-2's list; checksum low 24 bits, RSRC4_GS/HS zero, RSRC4_PS CUs 0-1.
    CHECK(offsets_of(TableId::IntOtherSh) == offsets_of(TableId::IntV11_2));
    CHECK(value_of(TableId::IntV11_2, 0x100) == 0xFFFFFF00u);
    CHECK(value_of(TableId::IntOtherSh, 0x100) == 0x00FFFFFFu);
    CHECK(value_of(TableId::IntOtherSh, 0x081) == 0u);
    CHECK(value_of(TableId::IntOtherSh, 0x101) == 0u);
    CHECK(value_of(TableId::IntOtherSh, 0x001) == 0x3u);
    CHECK(value_of(TableId::IntOtherSh, sh::COMPUTE_DESTINATION_EN_SE2) == 0xFFFFFFFFu);
    CHECK(same_pairs(TableId::IntOtherUc, TableId::IntV11_3));
    // The 6-entry fourth list.
    CHECK(offsets_of(TableId::FourthOther) ==
          std::vector<u32>{0x26C, 0x094, 0x095, 0x26E, 0x278, 0x262});
    CHECK(nonzero(tables::table(TableId::FourthOther)) == 0);
}

TEST_CASE("own AGC tables (tables2.md): the version groups of other SoCs", "[reimpl-tables]") {
    namespace ctx = rdb::ctx;
    namespace sh = rdb::sh;
    // Identities the description states.
    CHECK(same_pairs(TableId::IntV0_3Cx, TableId::IntSocA));
    CHECK(same_pairs(TableId::IntV0_3Sh, TableId::IntSocB));
    CHECK(same_pairs(TableId::UcV4, TableId::UcSoc));
    CHECK(same_pairs(TableId::IntV5_6Sh, TableId::IntV4Sh));
    CHECK(same_pairs(TableId::IntV7Sh, TableId::IntV4Sh));
    CHECK(same_pairs(TableId::IntV8Sh, TableId::IntV4Sh));
    CHECK(same_pairs(TableId::IntV10_12Sh, TableId::IntV4Sh));
    CHECK(same_pairs(TableId::ShV7, TableId::ShV5_6));
    CHECK(same_pairs(TableId::ShV8, TableId::ShV5_6));
    CHECK(same_pairs(TableId::ShV10_12, TableId::ShV5_6));
    CHECK(same_pairs(TableId::UcV8, TableId::UcV7));
    CHECK(same_pairs(TableId::UcV9, TableId::UcV7));
    CHECK(same_pairs(TableId::UcV10_12, TableId::UcV7));
    CHECK(same_pairs(TableId::IntV8Cx, TableId::IntV7Cx));
    CHECK(same_pairs(TableId::IntV9Cx, TableId::IntV7Cx));
    CHECK(same_pairs(TableId::IntV9Uc, TableId::IntV11_3));
    CHECK(same_pairs(TableId::IntV10_12Uc, TableId::IntV11_3));
    for (TableId t : {TableId::FourthSoc, TableId::FourthV0_3, TableId::FourthV4}) {
        CHECK(offsets_of(t) == std::vector<u32>{0x26C, 0x26E, 0x278, 0x262});
        CHECK(nonzero(tables::table(t)) == 0);
    }
    for (TableId t : {TableId::FourthV5_6, TableId::FourthV7, TableId::FourthV8, TableId::FourthV9,
                      TableId::FourthV10_12, TableId::FourthV11}) {
        CHECK(same_pairs(t, TableId::FourthOther));
    }

    // CX-V4: no DB_HTILE_SURFACE and no 0x0DB; the clears and 0x0F1/0x0F2 back in CX-SOC's places.
    const auto v4 = tables::table(TableId::CxV4);
    CHECK(index_of(TableId::CxV4, ctx::DB_HTILE_SURFACE) == v4.size());
    CHECK(index_of(TableId::CxV4, 0x0DB) == v4.size());
    CHECK(occurrences(TableId::CxV4, ctx::CB_BLENDn_CONTROL[0]) == 1);
    CHECK(v4[index_of(TableId::CxV4, ctx::DB_COUNT_CONTROL) + 1].offset == ctx::DB_DEPTH_CLEAR);
    CHECK(v4[index_of(TableId::CxV4, ctx::DB_STENCILREFMASK_BF) + 1].offset ==
          ctx::DB_STENCIL_CLEAR);
    CHECK(v4[index_of(TableId::CxV4, 0x0F0) + 1].offset == 0x0F1u);
    CHECK(v4[index_of(TableId::CxV4, 0x0F0) + 2].offset == 0x0F2u);
    const std::size_t w5 = index_of(TableId::CxV4, ctx::PA_CL_UCP_n_W[5]);
    CHECK(v4[w5 + 1].offset == ctx::PA_CL_PROG_NEAR_CLIP_Z);
    CHECK(v4[w5 + 2].offset == 0x188u);
    CHECK(v4[w5 + 8].offset == 0x18Eu);
    CHECK(get(value_of(TableId::CxV4, ctx::CB_DCC_CONTROL), 2, 6) == 2u);
    CHECK(get(value_of(TableId::CxV4, ctx::CB_DCC_CONTROL), 1, 1) == 0u);
    CHECK(value_of(TableId::CxV4, ctx::PA_STEREO_CNTL) == 0u);
    CHECK(get(value_of(TableId::CxV4, ctx::VGT_TESS_DISTRIBUTION), 0, 7) == 16u); // ISOLINE
    const u32 b0v4 = value_of(TableId::CxV4, ctx::PA_SC_BINNER_CNTL_0);
    CHECK(get(b0v4, 0, 1) == 0u);
    CHECK(get(b0v4, 19, 26) == 63u);
    // SH-V4 = SH-SOC without the three RSRC4; INT-V4-CX/-SH.
    CHECK(index_of(TableId::ShV4, sh::SPI_SHADER_PGM_RSRC4_PS) == 158u);
    CHECK(offsets_of(TableId::IntV4Cx) == std::vector<u32>{0x2AF, 0x1B5});
    CHECK(value_of(TableId::IntV4Cx, 0x2AF) == 0x40000u);
    const auto i4 = tables::table(TableId::IntV4Sh);
    CHECK(i4[12].offset == 0x081u);
    CHECK(i4[13].offset == 0x101u);
    CHECK(i4[14].offset == 0x001u);
    CHECK(i4[14].value == 0x3u);
    CHECK(i4[12].value == 0u);

    // CX-V5_6: 0x0DB after PA_SC_CLIPRECT_3_BR, the clears after DB_DEPTH_SIZE_XY, 0x0F1/0x0F2
    // twice; PA_STEREO_CNTL bit 26, binning off.
    const auto v56 = tables::table(TableId::CxV5_6);
    CHECK(v56[index_of(TableId::CxV5_6, ctx::PA_SC_CLIPRECT_n_BR[3]) + 1].offset == 0x0DBu);
    const std::size_t xy = index_of(TableId::CxV5_6, ctx::DB_DEPTH_SIZE_XY);
    CHECK(v56[xy + 1].offset == ctx::DB_DEPTH_CLEAR);
    CHECK(v56[xy + 2].offset == ctx::DB_STENCIL_CLEAR);
    CHECK(v56[index_of(TableId::CxV5_6, 0x0EC) + 1].offset == 0x0F1u);
    CHECK(occurrences(TableId::CxV5_6, 0x0F1) == 2);
    CHECK(value_of(TableId::CxV5_6, ctx::PA_STEREO_CNTL) == 0x04000000u);
    CHECK(get(value_of(TableId::CxV5_6, ctx::PA_SC_BINNER_CNTL_0), 0, 1) == 2u);
    CHECK(tables::table(TableId::ShV5_6)[index_of(TableId::ShV5_6, 0x280) - 1].offset ==
          sh::SPI_SHADER_PGM_HI_PS);
    // UC-V5_6: 32 entries after TA_CS_BC_BASE_ADDR_HI, ending in GE_USER_VGPR3.
    const auto u56 = tables::table(TableId::UcV5_6);
    const std::size_t bc = index_of(TableId::UcV5_6, rdb::uc::TA_CS_BC_BASE_ADDR_HI);
    CHECK(u56[bc + 1].offset == 0x2E4u);
    CHECK(u56[bc + 9].offset == 0x2C4u);
    CHECK(u56[bc + 25].offset == 0x2BCu);
    CHECK(u56[bc + 29].offset == 0x0A2u);
    CHECK(u56[bc + 32].offset == rdb::uc::GE_USER_VGPR3);
    CHECK(occurrences(TableId::UcV5_6, 0x2E4) == 2);
    CHECK(offsets_of(TableId::IntV5_6Cx) == std::vector<u32>{0x00E, 0x2AF, 0x1B5});
    CHECK(get(value_of(TableId::IntV5_6Cx, 0x00E), 0, 1) == 2u); // FORCE_OFF

    // CX-V7 = CX-V5_6 without the first 0x0F1/0x0F2; CX-V8 no isoline; CX-V9 watermark 4.
    CHECK(occurrences(TableId::CxV7, 0x0F1) == 1);
    CHECK(tables::table(TableId::CxV7)[index_of(TableId::CxV7, 0x0EC) + 1].offset == 0x0F1u);
    CHECK(offsets_of(TableId::CxV8) == offsets_of(TableId::CxV7));
    CHECK(get(value_of(TableId::CxV7, ctx::VGT_TESS_DISTRIBUTION), 0, 7) == 16u);
    CHECK(get(value_of(TableId::CxV8, ctx::VGT_TESS_DISTRIBUTION), 0, 7) == 0u);
    CHECK(get(value_of(TableId::CxV8, ctx::VGT_TESS_DISTRIBUTION), 8, 15) == 16u);
    CHECK(offsets_of(TableId::CxV9) == offsets_of(TableId::CxV8));
    CHECK(get(value_of(TableId::CxV9, ctx::CB_DCC_CONTROL), 2, 6) == 4u);
    CHECK(get(value_of(TableId::CxV8, ctx::CB_DCC_CONTROL), 2, 6) == 2u);
    CHECK(index_of(TableId::UcV7, 0x263) == 55u);
    CHECK(offsets_of(TableId::IntV7Cx) == std::vector<u32>{0x00E, 0x2AF, 0x314, 0x1B5});
    CHECK(get(value_of(TableId::IntV7Cx, 0x314), 0, 10) == 514u);
    // SH-V9: RSRC4_GS (zero) after RSRC3_GS; INT-V9-SH without 0x081.
    const auto s9 = tables::table(TableId::ShV9);
    CHECK(s9[index_of(TableId::ShV9, sh::SPI_SHADER_PGM_RSRC3_GS) + 1].offset ==
          sh::SPI_SHADER_PGM_RSRC4_GS);
    CHECK(value_of(TableId::ShV9, sh::SPI_SHADER_PGM_RSRC4_GS) == 0u);
    CHECK(index_of(TableId::IntV9Sh, 0x081) == 14u);

    // CX-V10_12 = CX-OTHER without both DB_HTILE_SURFACE and the first four 0x0DB.
    CHECK(index_of(TableId::CxV10_12, ctx::DB_HTILE_SURFACE) == 482u);
    CHECK(occurrences(TableId::CxV10_12, 0x0DB) == 1);
    CHECK(value_of(TableId::CxV10_12, 0x0DB) == 0u);
    CHECK(value_of(TableId::CxV10_12, ctx::DB_EQAA) == 0u);
    CHECK(offsets_of(TableId::IntV10_12Cx)[1] == 0x2AFu);
    CHECK(offsets_of(TableId::IntV10_12Cx)[0] == 0x00Eu);
    CHECK(value_of(TableId::IntV10_12Cx, 0x2AF) == 0x40000u);
}

TEST_CASE("own AGC tables: order", "[reimpl-tables]") {
    namespace ctx = rdb::ctx;
    namespace sh = rdb::sh;
    const auto cx = tables::table(TableId::CxSoc);
    // The alphabetical head of CX-SOC.
    CHECK(cx[0].offset == ctx::CB_COLOR_CONTROL);
    CHECK(cx[1].offset == ctx::CB_DCC_CONTROL);
    CHECK(cx[2].offset == ctx::CB_RMI_GL2_CACHE_CONTROL);
    CHECK(cx[3].offset == ctx::CB_SHADER_MASK);
    CHECK(cx[4].offset == ctx::CB_TARGET_MASK);
    CHECK(cx[5].offset == ctx::DB_ALPHA_TO_MASK);
    CHECK(cx[11].offset == 0x006u); // unnamed, sorts between DB_RENDER_CONTROL and DB_RMI_*
    CHECK(cx[57].offset == ctx::VGT_TF_PARAM);
    CHECK(cx[58].offset == ctx::PA_SC_CENTROID_PRIORITY_0);
    CHECK(cx.back().offset == ctx::PA_SC_WINDOW_SCISSOR_BR);
    // Offsets are the gfx10.json ones (context base 0xA000).
    CHECK(ctx::CB_COLOR_CONTROL == 0x202u);
    CHECK(ctx::DB_EQAA == 0x201u);

    // CX-V0_3 has the same list.
    const auto v03 = tables::table(TableId::CxV0_3);
    for (std::size_t i = 0; i < cx.size(); ++i) {
        CHECK(v03[i].offset == cx[i].offset);
    }

    // CX-V11: the extra CB_BLEND0_CONTROL near the top, the moved clears and unnamed entries.
    const auto v11 = tables::table(TableId::CxV11);
    CHECK(v11[2].offset == ctx::CB_BLENDn_CONTROL[0]);
    CHECK(std::count_if(v11.begin(), v11.end(), [](const agc::RegPair &p) {
              return p.offset == ctx::CB_BLENDn_CONTROL[0];
          }) == 2);
    const std::size_t xy = index_of(TableId::CxV11, ctx::DB_DEPTH_SIZE_XY);
    REQUIRE(xy + 6 < v11.size());
    CHECK(v11[xy + 1].offset == ctx::DB_DEPTH_CLEAR);
    CHECK(v11[xy + 2].offset == ctx::DB_STENCIL_CLEAR);
    CHECK(v11[xy + 3].offset == 0x0EBu);
    CHECK(v11[xy + 4].offset == 0x0ECu);
    CHECK(v11[xy + 5].offset == 0x0F1u);
    CHECK(v11[xy + 6].offset == 0x0F2u);
    CHECK(index_of(TableId::CxV11, ctx::CB_COLORn_PITCH[3]) == v11.size());
    CHECK(index_of(TableId::CxV11, ctx::PA_CL_PROG_NEAR_CLIP_Z) == v11.size());
    CHECK(v11[index_of(TableId::CxV11, ctx::PA_CL_OBJPRIM_ID_CNTL) + 1].offset == 0x212u);

    // SH-V11: inserted checksum entries.
    const auto shv11 = tables::table(TableId::ShV11);
    CHECK(shv11[index_of(TableId::ShV11, sh::COMPUTE_RESOURCE_LIMITS) + 1].offset ==
          sh::COMPUTE_SHADER_CHKSUM);
    CHECK(shv11[index_of(TableId::ShV11, sh::SPI_SHADER_PGM_HI_PS) + 1].offset == 0x280u);
    CHECK(index_of(TableId::ShV11, sh::SPI_SHADER_PGM_RSRC4_PS) == shv11.size());

    // UC-V11: the regrouped unnamed block behind TA_CS_BC_BASE_ADDR_HI.
    const auto ucv11 = tables::table(TableId::UcV11);
    const std::size_t hi = index_of(TableId::UcV11, rdb::uc::TA_CS_BC_BASE_ADDR_HI);
    CHECK(ucv11[hi + 1].offset == 0x2E4u);
    CHECK(ucv11[hi + 9].offset == 0x2C4u);
    CHECK(ucv11.back().offset == rdb::uc::GE_USER_VGPR3);

    // INT-V11-2: RSRC4 entries after SPI_SHADER_PGM_CHKSUM_HS.
    const auto i2 = tables::table(TableId::IntV11_2);
    CHECK(i2[8].offset == 0x100u);
    CHECK(i2[9].offset == 0x081u);
    CHECK(i2[10].offset == 0x101u);
    CHECK(i2[11].offset == 0x001u);
}

TEST_CASE("own AGC tables: values decoded field by field", "[reimpl-tables]") {
    namespace ctx = rdb::ctx;
    namespace sh = rdb::sh;
    // CB_COLOR_CONTROL: MODE (bits 4..6) = CB_NORMAL (1), ROP3 (16..23) = ROP3_COPY (0xCC).
    const u32 ccc = value_of(TableId::CxSoc, ctx::CB_COLOR_CONTROL);
    CHECK(get(ccc, 4, 6) == 1u);
    CHECK(get(ccc, 16, 23) == 0xCCu);
    CHECK((ccc & ~(0x70u | 0xFF0000u)) == 0u);
    // CB_DCC_CONTROL: watermark 2 plus bit 1 in CX-SOC, watermark only in CX-V0_3, 4 in CX-V11.
    CHECK((value_of(TableId::CxSoc, ctx::CB_DCC_CONTROL) & 2u) == 2u);
    CHECK((value_of(TableId::CxV0_3, ctx::CB_DCC_CONTROL) & 2u) == 0u);
    // PA_SU_POLY_OFFSET_DB_FMT_CNTL: -23 in 8 bits, float depth.
    const u32 pof = value_of(TableId::CxSoc, ctx::PA_SU_POLY_OFFSET_DB_FMT_CNTL);
    CHECK(get(pof, 0, 7) == 233u);
    CHECK(get(pof, 8, 8) == 1u);
    // PA_SC_BINNER_CNTL_1: MAX_ALLOC_COUNT (0..15) = 128, MAX_PRIM_PER_BATCH (16..31) = 1023.
    const u32 b1 = value_of(TableId::CxSoc, ctx::PA_SC_BINNER_CNTL_1);
    CHECK(get(b1, 0, 15) == 128u);
    CHECK(get(b1, 16, 31) == 1023u);
    // PA_SC_BINNER_CNTL_0: CONTEXT_STATES_PER_BIN (10..12) 1 in SOC, 0 in V0_3; V11 binning off.
    CHECK(get(value_of(TableId::CxSoc, ctx::PA_SC_BINNER_CNTL_0), 10, 12) == 1u);
    CHECK(get(value_of(TableId::CxV0_3, ctx::PA_SC_BINNER_CNTL_0), 10, 12) == 0u);
    const u32 b0v11 = value_of(TableId::CxV11, ctx::PA_SC_BINNER_CNTL_0);
    CHECK(get(b0v11, 0, 1) == 2u); // DISABLE_BINNING_USE_NEW_SC
    CHECK(get(b0v11, 18, 18) == 1u);
    CHECK(get(b0v11, 19, 26) == 63u);
    // CB_COLOR3_ATTRIB3: COLOR_SW_MODE (14..18) 27, FMASK_SW_MODE (19..23) 24, RESOURCE_LEVEL 1.
    const u32 a3 = value_of(TableId::CxSoc, ctx::CB_COLORn_ATTRIB3[3]);
    CHECK(get(a3, 14, 18) == 27u);
    CHECK(get(a3, 19, 23) == 24u);
    CHECK(get(a3, 27, 29) == 1u);
    // Viewport scales and guard band are float 1.0; the reset index is all ones.
    CHECK(value_of(TableId::CxSoc, ctx::PA_CL_VPORT_XSCALE_n[0]) == 0x3F800000u);
    CHECK(value_of(TableId::CxSoc, ctx::PA_CL_VPORT_ZSCALE_n[15]) == 0x3F800000u);
    CHECK(value_of(TableId::CxSoc, ctx::PA_CL_GB_HORZ_DISC_ADJ) == 0x3F800000u);
    CHECK(value_of(TableId::CxSoc, ctx::VGT_MULTI_PRIM_IB_RESET_INDX) == 0xFFFFFFFFu);
    // Unnamed entries given by bit position.
    CHECK(value_of(TableId::CxSoc, 0x0EB) == 0xFF00FF00u);
    CHECK(value_of(TableId::CxSoc, 0x0EC) == 0x00010000u);
    CHECK(value_of(TableId::UcSoc, 0x383) == 0x40000040u);
    CHECK(value_of(TableId::CxV11, 0x212) == 0x00002400u);
    // V11 overrides: DB_EQAA HIGH_QUALITY_INTERSECTIONS (bit 16), single bits.
    CHECK(value_of(TableId::CxV11, ctx::DB_EQAA) == 0x00010000u);
    CHECK(value_of(TableId::CxV11, ctx::PA_STEREO_CNTL) == 0x04000000u);
    // SH: CU_EN of RSRC3_HS is the high half, of RSRC3_GS/PS and RSRC4 the low half.
    CHECK(value_of(TableId::ShSoc, sh::SPI_SHADER_PGM_RSRC3_HS) == 0xFFFF0000u);
    CHECK(value_of(TableId::ShSoc, sh::SPI_SHADER_PGM_RSRC3_GS) == 0x0000FFFFu);
    CHECK(value_of(TableId::ShSoc, sh::SPI_SHADER_PGM_RSRC4_PS) == 0x00000003u);
    CHECK(value_of(TableId::ShV11, sh::SPI_SHADER_PGM_RSRC3_HS) == 0x3FFF0000u);
    CHECK(value_of(TableId::ShV11, sh::COMPUTE_SHADER_CHKSUM) == 0xFFFFFF00u);
    // Internal tables.
    CHECK(value_of(TableId::IntSocB, sh::COMPUTE_DESTINATION_EN_SE0) == 0xFFFFFFFFu);
    const u32 tunnel = value_of(TableId::IntSocB, sh::COMPUTE_DISPATCH_TUNNEL);
    CHECK(get(tunnel, 0, 9) == 255u); // OFF_DELAY
    CHECK(get(tunnel, 10, 10) == 1u); // IMMEDIATE
    CHECK(value_of(TableId::IntV11_1, 0x019) == 0xF3u);
    CHECK(get(value_of(TableId::IntV11_1, ctx::PA_SC_NGG_MODE_CNTL), 0, 10) == 514u);
    CHECK(value_of(TableId::IntV11_2, 0x101) == 0x3FFFu);
}

TEST_CASE("own AGC tables: CU-ROWS and PRIM-CLASS", "[reimpl-tables]") {
    const auto rows = tables::cu_rows();
    REQUIRE(rows.size() == 60);
    const u32 cols[10] = {0x216, 0x217, 0x219, 0x21A, 0x107, 0x087, 0x007, 0x101, 0x081, 0x001};
    for (u32 r = 0; r < 6; ++r) {
        for (u32 c = 0; c < 10; ++c) {
            CHECK(rows[r * 10 + c].offset == cols[c]);
        }
    }
    CHECK(rows[0].value == 0xFFFFFFFFu);
    CHECK(rows[4].value == 0xFFFF0000u);  // row 0 RSRC3_HS: CU_EN in the high half
    CHECK(rows[9].value == 0x3u);         // row 0 RSRC4_PS
    CHECK(rows[10].value == 0x00FF03FFu); // row 1 SE mask
    CHECK(rows[16].value == 0x3FFu);      // row 1 RSRC3_PS
    CHECK(rows[38].value == 0x1u);        // row 3 RSRC4_GS
    CHECK(rows[45].value == 0x01FFu);     // row 4 RSRC3_GS
    CHECK(rows[55].value == 0x7FFFu);     // row 5 RSRC3_GS

    const auto pc = tables::prim_classes();
    const u32 expect[18] = {0, 1, 1, 2, 2, 2, 3, 2, 2, 1, 1, 2, 2, 2, 2, 2, 4, 1};
    REQUIRE(pc.size() == 18);
    for (u32 i = 0; i < 18; ++i) {
        CHECK(pc[i] == expect[i]);
    }
}

TEST_CASE("own driver tables: default context ranges", "[reimpl-tables]") {
    const auto ranges = drv::default_ranges();
    REQUIRE(ranges.size() == 8);
    const u32 first[8] = {0xA000, 0xA0D8, 0xA1F5, 0xA1FF, 0xA2A0, 0xA2A3, 0xA2A5, 0xA2F5};
    const u32 count[8] = {215, 272, 4, 158, 2, 1, 66, 203};
    const std::size_t nz[8] = {62, 5, 0, 5, 0, 0, 1, 12};
    for (std::size_t i = 0; i < 8; ++i) {
        INFO("DRV-CS-" << (i + 1));
        CHECK(ranges[i].first == first[i]);
        CHECK(ranges[i].count == count[i]);
        const auto v = drv::default_range_values(ranges[i]);
        REQUIRE(v.size() == count[i]);
        CHECK(static_cast<std::size_t>(
                  std::count_if(v.begin(), v.end(), [](u32 x) { return x != 0; })) == nz[i]);
    }
    const auto all = drv::default_context_values();
    REQUIRE(all.size() == 0x400);
    CHECK(all[rdb::ctx::PA_SC_VPORT_ZMAX_n[0]] == 0x3F800000u);
    CHECK(all[0x100] == 0xFFFFFFFFu);      // VGT_MAX_VTX_INDX (gfx10.json)
    CHECK(get(all[0x2AA], 0, 15) == 255u); // IA_MULTI_VGT_PARAM.PRIMGROUP_SIZE
    CHECK(all[0xD7] == 0u);                // between DRV-CS-1 and DRV-CS-2: not covered
}

TEST_CASE("own trap handler and fill shader header", "[reimpl-tables]") {
    const auto trap = drv::trap_handler_code();
    REQUIRE(trap.size() == 4);
    u32 dw = 0;
    std::memcpy(&dw, trap.data(), 4);
    CHECK(dw == 0xBF810000u); // s_endpgm

    namespace fs = agc::fill_shader;
    // the assembled fill16.s: 17 dwords, the buffer store inside, s_endpgm last
    const auto code = fs::code();
    REQUIRE(code.size() == 17);
    CHECK(code[9] == 0xe0782000u); // buffer_store_dwordx4 ... idxen
    CHECK(code[1] == 0xbf85000eu); // s_cbranch_scc1 to the end (+14 dwords)
    CHECK(code[15] == 0xbf85fff9u); // s_cbranch_scc1 back to the store (-7 dwords)
    CHECK(code.back() == 0xbf810000u); // s_endpgm
    std::vector<std::uint8_t> blob(fs::header_bytes() + 8, 0xEE);
    fs::build_header(blob.data(), 0x40);
    agc::Shader h{};
    std::memcpy(&h, blob.data(), sizeof h);
    CHECK(h.magic == 0x34333231u);
    CHECK(h.version == 0x18u);
    CHECK(h.code_address == 0u);
    CHECK(h.stage == 0);
    CHECK(h.code_bytes == 0x40u);
    CHECK(h.header_bytes == fs::header_bytes());
    REQUIRE(h.num_sh_regs == 8);
    // Self-relative pointers resolved by hand.
    const std::uint8_t *base = blob.data();
    std::vector<agc::RegPair> regs(h.num_sh_regs);
    std::memcpy(regs.data(), base + offsetof(agc::Shader, sh_regs) + h.sh_regs,
                regs.size() * sizeof(agc::RegPair));
    CHECK(regs[0].offset == rdb::sh::COMPUTE_PGM_LO);
    CHECK(regs[1].offset == rdb::sh::COMPUTE_PGM_HI);
    for (const agc::RegPair &r : regs) {
        if (r.offset == rdb::sh::COMPUTE_PGM_RSRC2) {
            CHECK(get(r.value, 1, 5) == 9u); // USER_SGPR
            CHECK(get(r.value, 7, 7) == 1u); // TGID_X_EN
        }
        if (r.offset == rdb::sh::COMPUTE_NUM_THREAD_X) {
            CHECK(get(r.value, 0, 15) == 256u);
        }
        if (r.offset == rdb::sh::COMPUTE_PGM_RSRC1) {
            CHECK(get(r.value, 0, 5) == 1u); // (6 VGPRs - 1) / 4
        }
    }
    const std::uint8_t *extra = base + offsetof(agc::Shader, extra) + h.extra;
    std::uint16_t user = 0;
    std::memcpy(&user, extra + 0x2A, 2);
    CHECK(user == 9);
    u64 first = 0;
    std::memcpy(&first, extra, 8);
    std::uint16_t slot = 0xFFFF;
    std::memcpy(&slot, extra + first + 2, 2);
    CHECK(slot == 0);
}

TEST_CASE("data source: own tables by default, module file only with the switch",
          "[reimpl-tables]") {
    Env env;
    agc::testing::set_soc_id(0x840F00u);
    // A module file whose CX-SOC differs from ours in entry 0 and whose primitive classes are 7.
    std::vector<agc::RegPair> cx(tables::table(TableId::CxSoc).begin(),
                                 tables::table(TableId::CxSoc).end());
    cx[0].value ^= 0x5A5A0000u;
    FakeFile file;
    file.put("libSceAgc", 0x34120, cx.data(), cx.size() * sizeof(agc::RegPair));
    const u32 seven[18] = {7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7};
    file.put("libSceAgc", 0x23f1c, seven, sizeof seven);
    bc5::reimpl::set_firmware_data(&file);

    agc::PrimStateCx pcx{{0x2d5, 0}, {0x29b, 0}};
    SECTION("default: own data even with a module file installed") {
        const agc::RegisterDefaults *d = agc::sceAgcGetRegisterDefaults2(5);
        REQUIRE(d != nullptr);
        REQUIRE(d->cx_count == 523);
        CHECK((*d->cx)[0].value == tables::table(TableId::CxSoc)[0].value);
        CHECK(d->sh_count == 161);
        CHECK(d->uc_count == 43);
        CHECK(agc::sceAgcUpdatePrimState(&pcx, nullptr, 1) == 0);
        CHECK(pcx.gs_out_prim_type.value == 0u);
        CHECK(logged("FW_COMPARE") == 0);
    }
    SECTION("no module file at all: own data") {
        bc5::reimpl::set_firmware_data(nullptr);
        const agc::RegisterDefaults *d = agc::sceAgcGetRegisterDefaults2(5);
        REQUIRE(d->cx_count == 523);
        const agc::RegisterDefaults *in = agc::sceAgcGetRegisterDefaults2Internal(5);
        CHECK(in->cx_count == 1);
        CHECK(in->sh_count == 12);
    }
    SECTION("FW_DATA: the module file's data where present") {
        bc5::reimpl::set_data_switches({true, false});
        const agc::RegisterDefaults *d = agc::sceAgcGetRegisterDefaults2(5);
        REQUIRE(d->cx_count == 523);
        CHECK((*d->cx)[0].value == cx[0].value);
        CHECK(d->sh_count == 161); // not in the file: own table
        CHECK(agc::sceAgcUpdatePrimState(&pcx, nullptr, 1) == 0);
        CHECK(pcx.gs_out_prim_type.value == 7u);
    }
    SECTION("FW_COMPARE: reports the planted difference once, data stays ours") {
        bc5::reimpl::set_data_switches({false, true});
        const agc::RegisterDefaults *d = agc::sceAgcGetRegisterDefaults2(5);
        CHECK((*d->cx)[0].value == tables::table(TableId::CxSoc)[0].value);
        CHECK(logged("FW_COMPARE CX-SOC[0]: ours") == 1);
        CHECK(logged("FW_COMPARE CX-SOC: 1 of 523 entries differ") == 1);
        CHECK(agc::sceAgcUpdatePrimState(&pcx, nullptr, 1) == 0);
        CHECK(logged("FW_COMPARE PRIM-CLASS") == 19); // 18 entries + summary
        CHECK(agc::sceAgcUpdatePrimState(&pcx, nullptr, 2) == 0);
        CHECK(logged("FW_COMPARE PRIM-CLASS") == 19); // once only
    }
}

TEST_CASE("data source: compare helper", "[reimpl-tables]") {
    Env env;
    bc5::reimpl::set_data_switches({false, true});
    const u32 ours[4] = {1, 2, 3, 4};
    const u32 file[4] = {1, 9, 3, 8};
    const auto *bytes = reinterpret_cast<const std::uint8_t *>(file);
    CHECK(bc5::reimpl::compare_with_firmware("m", "T", ours, bytes, 2, 2) == 2);
    CHECK(logged("FW_COMPARE T[1]: ours {0x00000003,0x00000004} file {0x00000003,0x00000008}") ==
          1);
    CHECK(bc5::reimpl::compare_with_firmware("m", "T", ours, bytes, 2, 2) == 0); // once
    CHECK(bc5::reimpl::compare_with_firmware("m", "U", ours, bytes, 4, 1) == 2);
}
