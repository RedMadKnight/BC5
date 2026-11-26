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

TEST_CASE("start state: every row is written with nothing set", "[start_state]") {
    const FakeEnv env;
    const auto s = ss::select(env);
    CHECK(s.on == (1u << ss::kRowCount) - 1u);
    CHECK(s.skipped == 0);
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

TEST_CASE("start state: the deleted switches are read by nothing", "[start_state]") {
    FakeEnv env;
    for (const char *w : {"BC5_DIRECT_START_STATE", "BC5_DIRECT_CP_COHER_START_DELAY", "BC5_DIRECT_SPI_REQ_CTRL_PS",
                          "BC5_DIRECT_GC_TF_RING", "BC5_DIRECT_GC_HS_OFFCHIP", "BC5_DIRECT_GC_GS_RINGS"})
        env.v[w] = "0";
    const auto s = ss::select(env);
    CHECK(s.on == (1u << ss::kRowCount) - 1u);
    for (auto &kv : env.v) kv.second = "1";
    CHECK(ss::select(env).on == (1u << ss::kRowCount) - 1u);
}

TEST_CASE("start state: SKIP drops the named rows", "[start_state]") {
    FakeEnv env;
    env.v["BC5_DIRECT_START_STATE_SKIP"] = "GE_MAX_VTX_INDX, VGT_HS_OFFCHIP_PARAM:NOT_A_ROW";
    const auto s = ss::select(env);
    CHECK_FALSE(s.row_on("GE_MAX_VTX_INDX"));
    CHECK_FALSE(s.row_on("VGT_HS_OFFCHIP_PARAM"));
    CHECK(s.row_on("GE_MIN_VTX_INDX"));
    CHECK(s.row_on("VGT_TF_RING"));
    CHECK(s.skipped == ((1u << ss::index_of("GE_MAX_VTX_INDX")) | (1u << ss::index_of("VGT_HS_OFFCHIP_PARAM"))));
    CHECK((s.on | s.skipped) == (1u << ss::kRowCount) - 1u);
    CHECK(s.unknown_skip == 1);
    CHECK(ss::constant_packets(s).size() == 4 * 3);
    // An empty SKIP drops nothing.
    FakeEnv empty;
    empty.v["BC5_DIRECT_START_STATE_SKIP"] = "";
    CHECK(ss::select(empty).on == (1u << ss::kRowCount) - 1u);
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
        CHECK(c[5] == (r.status == ss::Status::Cited ? "cited" : "measured"));
        CHECK(c[7] == "-");
    }
}
