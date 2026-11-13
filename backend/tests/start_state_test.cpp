// SPDX-License-Identifier: GPL-2.0-only
// Experiment 0418 section 4: the start-state table, its switches and packets.
#include "bc5/start_state.hpp"

#include <catch2/catch_test_macros.hpp>

#include <cstdint>
#include <cstdlib>
#include <fstream>
#include <map>
#include <sstream>
#include <string>
#include <vector>

namespace ss = bc5::start_state;

namespace {

struct FakeEnv {
    std::map<std::string, std::string> v;
    const char *operator()(const char *name) const {
        const auto it = v.find(name);
        return it == v.end() ? nullptr : it->second.c_str();
    }
};

std::vector<std::string> split_tabs(const std::string &line) {
    std::vector<std::string> out;
    std::string cell;
    std::istringstream in(line);
    while (std::getline(in, cell, '\t')) out.push_back(cell);
    return out;
}

} // namespace

TEST_CASE("start state: nothing is written with every switch unset", "[start_state]") {
    const FakeEnv env;
    const auto s = ss::select(env);
    CHECK_FALSE(s.table);
    CHECK(s.on == 0);
    CHECK(ss::constant_packets(s).empty());
}

TEST_CASE("start state: BC5_DIRECT_START_STATE=1 turns every row on", "[start_state]") {
    FakeEnv env;
    env.v["BC5_DIRECT_START_STATE"] = "1";
    const auto s = ss::select(env);
    CHECK(s.table);
    CHECK(s.on == (1u << ss::kRowCount) - 1u);
    CHECK(s.by_alias == 0);
    // The five constant rows, one 3-dword packet each, in table order.
    const std::vector<std::uint32_t> want = {
        0xC0017900u, 0x07bu, 0x20u,        // CP_COHER_START_DELAY (SET_UCONFIG_REG, as exp 0401 wrote it)
        0xC0017600u, 0x030u, 0x7u,         // SPI_SHADER_REQ_CTRL_PS (SET_SH_REG, as exp 0401 wrote it)
        0xC0017900u, 0x249u, 0x0u,         // GE_MIN_VTX_INDX
        0xC0017900u, 0x259u, 0xffffffffu,  // GE_MAX_VTX_INDX
        0xC0017900u, 0x25au, 0x0u,         // VGT_INSTANCE_BASE_ID
    };
    CHECK(ss::constant_packets(s) == want);
    CHECK(s.row_on("VGT_TF_RING"));
    CHECK(s.row_on("VGT_HS_OFFCHIP_PARAM"));
    CHECK(s.row_on("VGT_GS_RINGS"));
}

TEST_CASE("start state: \"0\" and empty are off, like bc5::env_on", "[start_state]") {
    FakeEnv env;
    env.v["BC5_DIRECT_START_STATE"] = "0";
    env.v["BC5_DIRECT_GC_TF_RING"] = "";
    CHECK(ss::select(env).on == 0);
}

TEST_CASE("start state: the older switches turn on their own row only", "[start_state]") {
    FakeEnv env;
    env.v["BC5_DIRECT_GC_TF_RING"] = "1";
    env.v["BC5_DIRECT_GC_HS_OFFCHIP"] = "1";
    env.v["BC5_DIRECT_CP_COHER_START_DELAY"] = "1";
    const auto s = ss::select(env);
    CHECK_FALSE(s.table);
    CHECK(s.row_on("VGT_TF_RING"));
    CHECK(s.row_on("VGT_HS_OFFCHIP_PARAM"));
    CHECK(s.row_on("CP_COHER_START_DELAY"));
    CHECK_FALSE(s.row_on("SPI_SHADER_REQ_CTRL_PS"));
    CHECK_FALSE(s.row_on("GE_MAX_VTX_INDX"));
    CHECK_FALSE(s.row_on("VGT_GS_RINGS"));
    CHECK(s.by_alias == s.on);
    // The launcher of 2026-11-13 (GC_TF_RING, GC_HS_OFFCHIP, CP_COHER) gets exp 0401's one packet, unchanged.
    CHECK(ss::constant_packets(s) == std::vector<std::uint32_t>{0xC0017900u, 0x07bu, 0x20u});
    env.v["BC5_DIRECT_SPI_REQ_CTRL_PS"] = "1";
    env.v["BC5_DIRECT_GC_GS_RINGS"] = "1";
    const auto t = ss::select(env);
    CHECK(t.row_on("SPI_SHADER_REQ_CTRL_PS"));
    CHECK(t.row_on("VGT_GS_RINGS"));
}

TEST_CASE("start state: SKIP drops rows whatever turned them on", "[start_state]") {
    FakeEnv env;
    env.v["BC5_DIRECT_START_STATE"] = "1";
    env.v["BC5_DIRECT_GC_HS_OFFCHIP"] = "1";
    env.v["BC5_DIRECT_START_STATE_SKIP"] = "GE_MAX_VTX_INDX, VGT_HS_OFFCHIP_PARAM:NOT_A_ROW";
    const auto s = ss::select(env);
    CHECK_FALSE(s.row_on("GE_MAX_VTX_INDX"));
    CHECK_FALSE(s.row_on("VGT_HS_OFFCHIP_PARAM"));
    CHECK(s.row_on("GE_MIN_VTX_INDX"));
    CHECK(s.row_on("VGT_TF_RING"));
    CHECK(s.skipped == ((1u << ss::index_of("GE_MAX_VTX_INDX")) | (1u << ss::index_of("VGT_HS_OFFCHIP_PARAM"))));
    CHECK(s.unknown_skip == 1);
    // SKIP alone turns nothing on.
    FakeEnv only_skip;
    only_skip.v["BC5_DIRECT_START_STATE_SKIP"] = "GE_MAX_VTX_INDX";
    const auto t = ss::select(only_skip);
    CHECK(t.on == 0);
    CHECK(t.skipped == 0);
}

TEST_CASE("start state: names in SKIP match whole names only", "[start_state]") {
    CHECK(ss::listed("A,B C:D", "C"));
    CHECK(ss::listed("  GE_MIN_VTX_INDX  ", "GE_MIN_VTX_INDX"));
    CHECK_FALSE(ss::listed("GE_MIN_VTX_INDX_X", "GE_MIN_VTX_INDX"));
    CHECK_FALSE(ss::listed("ge_min_vtx_indx", "GE_MIN_VTX_INDX"));
    CHECK_FALSE(ss::listed("", "A"));
    CHECK_FALSE(ss::listed(nullptr, "A"));
}

TEST_CASE("start state: the packets go after CONTEXT_CONTROL and CLEAR_STATE", "[start_state]") {
    const std::vector<std::uint32_t> prefix = {0xC0012800u, 0x80000000u, 0x80000000u, 0xC0001200u, 0u, 0xC0016900u, 0x1u, 0x2u};
    CHECK(ss::insert_at(prefix) == 5);
    const std::vector<std::uint32_t> no_clear = {0xC0016900u, 0x1u, 0x2u};
    CHECK(ss::insert_at(no_clear) == 0);
    CHECK(ss::insert_at({}) == 0);
}

TEST_CASE("start state: GS ring sizes from 0xc00c8110", "[start_state]") {
    ss::GsRings r;
    const std::uint32_t four_eight[3] = {0x400000u, 0x800000u, 0u};
    REQUIRE(ss::gs_rings_from_request(four_eight, r));
    CHECK(r.esgs == 0x4000u);
    CHECK(r.gsvs == 0x8000u);
    const std::uint32_t zero[3] = {0u, 0x800000u, 0u};
    CHECK_FALSE(ss::gs_rings_from_request(zero, r));
    const std::uint32_t odd[3] = {0x400001u, 0x800000u, 0u};
    CHECK_FALSE(ss::gs_rings_from_request(odd, r));
    CHECK_FALSE(ss::gs_rings_from_request(nullptr, r));

    std::vector<std::uint32_t> p;
    ss::gs_rings_packets(p, {0x4000u, 0x8000u}, true);
    CHECK(p == std::vector<std::uint32_t>{0xC0004600u, 0x40fu, 0xC0004600u, 0x24u, 0xC0027900u, 0x240u, 0x4000u, 0x8000u});
    p.clear();
    ss::gs_rings_packets(p, {0x4000u, 0x8000u}, false);
    CHECK(p == std::vector<std::uint32_t>{0xC0027900u, 0x240u, 0x4000u, 0x8000u});
}

TEST_CASE("start state: the header and backend/policy/start-state.tsv agree", "[start_state]") {
    std::ifstream in(BC5_START_STATE_TSV);
    REQUIRE(in.good());
    std::string line;
    std::map<std::string, std::vector<std::string>> written; // constant and request rows of the TSV
    std::size_t rows = 0;
    while (std::getline(in, line)) {
        if (line.empty() || line[0] == '#') continue;
        const auto c = split_tabs(line);
        REQUIRE(c.size() == 10);
        ++rows;
        if (c[4] == "constant" || c[4] == "request") written[c[0]] = c;
        else CHECK(c[4] == "elsewhere");
    }
    CHECK(rows > ss::kRowCount);
    REQUIRE(written.size() == ss::kRowCount);
    for (const auto &r : ss::kRows) {
        INFO(r.name);
        const auto it = written.find(r.name);
        REQUIRE(it != written.end());
        const auto &c = it->second;
        CHECK(c[1] == (r.space == ss::Space::Uconfig ? "uconfig" : "sh"));
        CHECK(std::strtoul(c[2].c_str(), nullptr, 16) == r.offset);
        if (r.kind == ss::Kind::Constant) {
            CHECK(c[4] == "constant");
            CHECK(c[6] == "prefix");
            CHECK(std::strtoul(c[3].c_str(), nullptr, 16) == r.value);
        } else {
            CHECK(c[4] == "request");
            CHECK(c[6] == "cam");
            CHECK(std::strtoul(c[3].c_str(), nullptr, 16) == r.request);
        }
        CHECK(c[5] == (r.status == ss::Status::Cited ? "cited" : "inferred"));
        CHECK(c[7] == (r.alias != nullptr ? r.alias : "-"));
    }
}
