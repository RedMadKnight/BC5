// SPDX-License-Identifier: GPL-2.0-only
// Experiment 0418 section 4: the console's start state as one table instead of one switch per register.
//
// On the console the system programs some GPU state before the title runs, or when the title's driver asks it through
// /dev/gc. Under amdgpu nobody does, unless the host writes it. This header holds the rows the host can write from a user
// IB, the switches that choose them and the packets they become. backend/policy/start-state.tsv is the same table with
// its sources and the rows met elsewhere (the kernel, the BO list, the code rewrite); start_state_test.cpp checks that
// the two agree. The KytyPlus unit (patch 0001, src/bc5/start_state.hpp, an identical copy) writes the rows in every
// job's prefix.
//
// Switches, all off by default and read once:
// - BC5_DIRECT_START_STATE=1: every row of the table.
// - BC5_DIRECT_START_STATE_SKIP=<names>: the named rows are not written, whatever turned them on (bisection). Names are
//   the table's, separated by commas, spaces or colons.
// - The older one-register switches are aliases that turn on their own row: BC5_DIRECT_CP_COHER_START_DELAY and
//   BC5_DIRECT_SPI_REQ_CTRL_PS (exp 0401), BC5_DIRECT_GC_TF_RING and BC5_DIRECT_GC_HS_OFFCHIP (exp 0189),
//   BC5_DIRECT_GC_GS_RINGS (exp 0418). A launcher that sets them keeps working.
//
// Constant rows go first in the prefix (after its CONTEXT_CONTROL and CLEAR_STATE), so the state the title wrote, which
// the full-state prefix writes back after them, still wins. Request rows (the rings) take the value the title's driver
// sent /dev/gc and are written by their own code, through the _UMD addresses the kernel remaps to the real registers
// (GRBM CAM, Linux v7.2 gfx_v10_0.c:7296-7475).
#pragma once

#include <cstddef>
#include <cstdint>
#include <string_view>
#include <vector>

namespace bc5::start_state {

// Where a row is written: a uconfig register (SET_UCONFIG_REG offset = byte address / 4 - 0xc000) or a gfx SH register
// (SET_SH_REG offset = byte address / 4 - 0x2c00).
enum class Space : std::uint8_t { Uconfig, Sh };

// Constant: the value below, in the prefix. Request: the value the title's driver sent /dev/gc, written by the ring code.
enum class Kind : std::uint8_t { Constant, Request };

// Cited: a source says the console's system sets it (or the title asks for it). Inferred: the value the drivers write,
// believed to be what the chip already holds in play here (exp 0418 section 2), until the umr read of section 3 shows it.
enum class Status : std::uint8_t { Cited, Inferred };

struct Row {
    const char *name;        // the table's name, also the SKIP key
    Space space;
    std::uint16_t offset;    // the first register's packet offset
    std::uint32_t value;     // Constant rows; 0 for Request rows
    std::uint32_t request;   // the /dev/gc request a Request row comes from; 0 for Constant rows
    Kind kind;
    Status status;
    const char *alias;       // the older switch that turns this row on alone, or nullptr
};

// Offsets: Linux v7.2 gc_10_1_0_offset.h (uconfig: mm - 0x2000 for BASE_IDX 1; SH: mm + 0x1260 - 0x2c00 for BASE_IDX 0),
// the same as Mesa's R_xxxxxx names. Values: Mesa 0866ae7 src/amd/common/ac_cmdbuf.c (gfx10 preamble) and PAL c5e80007.
inline constexpr Row kRows[] = {
    // reset 0x20 (gc_10_1_0_default.h:3638); Mesa gfx10 0x20 (ac_cmdbuf.c:60); PAL 0x20 (gfx9QueueContexts.cpp:155-165)
    {"CP_COHER_START_DELAY", Space::Uconfig, 0x07b, 0x20u, 0, Kind::Constant, Status::Inferred, "BC5_DIRECT_CP_COHER_START_DELAY"},
    // reset 0 (:2074); Mesa 0x7 (ac_cmdbuf.c:444-446); PAL NumPsWavesSoftGroupedPerCu 4 (settings_gfx9.json:1386-1397)
    {"SPI_SHADER_REQ_CTRL_PS", Space::Sh, 0x030, 0x7u, 0, Kind::Constant, Status::Inferred, "BC5_DIRECT_SPI_REQ_CTRL_PS"},
    // reset 0 (:3745); Mesa 0 (ac_cmdbuf.c:599); PAL 0 (gfx9QueueContexts.cpp:1827-1830)
    {"GE_MIN_VTX_INDX", Space::Uconfig, 0x249, 0x0u, 0, Kind::Constant, Status::Inferred, nullptr},
    // reset 0 (:3761); Mesa ~0 (ac_cmdbuf.c:608); PAL UINT_MAX (gfx9QueueContexts.cpp:1817-1826)
    {"GE_MAX_VTX_INDX", Space::Uconfig, 0x259, 0xffffffffu, 0, Kind::Constant, Status::Inferred, nullptr},
    // reset 0 (:3762); Mesa 0 (ac_cmdbuf.c:609)
    {"VGT_INSTANCE_BASE_ID", Space::Uconfig, 0x25a, 0x0u, 0, Kind::Constant, Status::Inferred, nullptr},
    // VGT_TF_RING_SIZE_UMD 0x24e, VGT_TF_MEMORY_BASE_UMD 0x250, VGT_TF_MEMORY_BASE_HI_UMD 0x261 (F248)
    {"VGT_TF_RING", Space::Uconfig, 0x24e, 0, 0x80108128u, Kind::Request, Status::Cited, "BC5_DIRECT_GC_TF_RING"},
    // VGT_HS_OFFCHIP_PARAM_UMD 0x24f (F785, F786)
    {"VGT_HS_OFFCHIP_PARAM", Space::Uconfig, 0x24f, 0, 0x8004812au, Kind::Request, Status::Cited, "BC5_DIRECT_GC_HS_OFFCHIP"},
    // VGT_ESGS_RING_SIZE_UMD 0x240, VGT_GSVS_RING_SIZE_UMD 0x241; "set gs ring sizes" (RPCSX e8ae148 gc.cpp:295-307)
    {"VGT_GS_RINGS", Space::Uconfig, 0x240, 0, 0xc00c8110u, Kind::Request, Status::Cited, "BC5_DIRECT_GC_GS_RINGS"},
};
inline constexpr std::size_t kRowCount = sizeof(kRows) / sizeof(kRows[0]);
static_assert(kRowCount <= 32, "a Selection holds one bit per row");

// The index of a row by name, or kRowCount.
inline constexpr std::size_t index_of(std::string_view name) {
    for (std::size_t i = 0; i < kRowCount; ++i)
        if (name == kRows[i].name) return i;
    return kRowCount;
}

// The same reading as bc5::env_on (backend/include/bc5/env_flag.hpp, F767): unset, empty and "0" are off.
inline bool switch_on(const char *e) { return e != nullptr && e[0] != 0 && !(e[0] == '0' && e[1] == 0); }

// True when `name` is one of the names in `list` (separated by commas, spaces or colons; exact, case-sensitive).
inline bool listed(const char *list, std::string_view name) {
    if (list == nullptr) return false;
    const std::string_view l(list);
    std::size_t i = 0;
    while (i < l.size()) {
        while (i < l.size() && (l[i] == ',' || l[i] == ' ' || l[i] == ':')) ++i;
        std::size_t j = i;
        while (j < l.size() && l[j] != ',' && l[j] != ' ' && l[j] != ':') ++j;
        if (j > i && l.substr(i, j - i) == name) return true;
        i = j;
    }
    return false;
}

struct Selection {
    bool table = false;           // BC5_DIRECT_START_STATE
    std::uint32_t on = 0;         // rows written
    std::uint32_t by_alias = 0;   // rows an alias switch asked for
    std::uint32_t skipped = 0;    // rows SKIP named that the table or an alias would have written
    std::uint32_t unknown_skip = 0; // count of SKIP names that are no row (reported, not fatal)

    [[nodiscard]] bool row_on(std::size_t i) const { return i < kRowCount && ((on >> i) & 1u) != 0; }
    [[nodiscard]] bool row_on(std::string_view name) const { return row_on(index_of(name)); }
};

// `get` is std::getenv or a stand-in: const char *get(const char *name).
template <class Get> Selection select(Get get) {
    Selection s;
    s.table = switch_on(get("BC5_DIRECT_START_STATE"));
    const char *skip = get("BC5_DIRECT_START_STATE_SKIP");
    for (std::size_t i = 0; i < kRowCount; ++i) {
        const std::uint32_t bit = 1u << i;
        const bool alias = kRows[i].alias != nullptr && switch_on(get(kRows[i].alias));
        if (alias) s.by_alias |= bit;
        if (!s.table && !alias) continue;
        if (listed(skip, kRows[i].name)) {
            s.skipped |= bit;
            continue;
        }
        s.on |= bit;
    }
    if (skip != nullptr) {
        const std::string_view l(skip);
        std::size_t i = 0;
        while (i < l.size()) {
            while (i < l.size() && (l[i] == ',' || l[i] == ' ' || l[i] == ':')) ++i;
            std::size_t j = i;
            while (j < l.size() && l[j] != ',' && l[j] != ' ' && l[j] != ':') ++j;
            if (j > i && index_of(l.substr(i, j - i)) == kRowCount) ++s.unknown_skip;
            i = j;
        }
    }
    return s;
}

// PKT3 headers with COUNT 1 (one register: offset dword + one value): SET_UCONFIG_REG 0x79, SET_SH_REG 0x76.
inline constexpr std::uint32_t kSetUconfig1 = 0xC0017900u;
inline constexpr std::uint32_t kSetSh1 = 0xC0017600u;

// The Constant rows that are on, in table order, one packet each: 3 dwords a row.
inline std::vector<std::uint32_t> constant_packets(const Selection &s) {
    std::vector<std::uint32_t> p;
    for (std::size_t i = 0; i < kRowCount; ++i) {
        if (!s.row_on(i) || kRows[i].kind != Kind::Constant) continue;
        p.push_back(kRows[i].space == Space::Uconfig ? kSetUconfig1 : kSetSh1);
        p.push_back(kRows[i].offset);
        p.push_back(kRows[i].value);
    }
    return p;
}

// Where the constant packets go in a prefix from bc5::full_state::Tracker::emit_prefix(): after its CONTEXT_CONTROL
// (3 dwords) and CLEAR_STATE (2 dwords), or at 0 when those were removed (BC5_DIRECT_PIECES_NO_CLEAR).
inline std::size_t insert_at(const std::vector<std::uint32_t> &prefix) {
    if (prefix.size() >= 5 && prefix[0] == 0xC0012800u && prefix[3] == 0xC0001200u) return 5;
    return 0;
}

// "set gs ring sizes" (0xc00c8110): three dwords {ES->GS ring bytes, GS->VS ring bytes, 0} by RPCSX's layout
// (gc.cpp:295-307, "arg1, arg2, unk // 0"). The unit is taken as bytes, the unit of the PS4 call that sets the same two
// sizes (shadPS4 60c42b9 gnmdriver.cpp:1765-1782: 4-8 MiB, MiB-aligned, the register gets bytes >> 8) and of RADV
// (radv_queue.c:372-374 @ 0866ae7, esgs_ring_size >> 8 into VGT_ESGS_RING_SIZE). TODO(verify): the PS5 driver's unit;
// no title of ours sends it (exp 0189's trace). Values that are 0 or not a multiple of 256 are not programmed.
struct GsRings {
    std::uint32_t esgs = 0; // register values (bytes >> 8)
    std::uint32_t gsvs = 0;
};
inline bool gs_rings_from_request(const std::uint32_t *a, GsRings &out) {
    if (a == nullptr || a[0] == 0 || a[1] == 0 || (a[0] & 0xffu) != 0 || (a[1] & 0xffu) != 0) return false;
    out.esgs = a[0] >> 8u;
    out.gsvs = a[1] >> 8u;
    return true;
}

// The ring sizes as RADV writes them (radv_queue.c:372-374): one SET_UCONFIG_REG of two registers at
// VGT_ESGS_RING_SIZE_UMD. `flush` adds RADV's VS_PARTIAL_FLUSH + VGT_FLUSH before (radv_queue.c:1048-1052; event types
// 15 index 4 and 36 index 0, the encoding Direct::tf_ring_prefix uses): due when the sizes differ from the last written.
inline void gs_rings_packets(std::vector<std::uint32_t> &p, const GsRings &r, bool flush) {
    if (flush) p.insert(p.end(), {0xC0004600u, 0x40fu, 0xC0004600u, 0x24u});
    p.insert(p.end(), {0xC0027900u, 0x240u, r.esgs, r.gsvs});
}

} // namespace bc5::start_state
