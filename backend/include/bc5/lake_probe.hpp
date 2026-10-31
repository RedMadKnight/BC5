// SPDX-License-Identifier: GPL-2.0-only
// Experiment 0385: the test build's catchers and candidate fixes for the night lake's holes (Q21), all
// behind one set of switches that the host re-reads during a run (BC5_DIRECT_LAKE_CTL, direct.cpp), so
// one run with holes can turn each of them on and off. With that variable unset none of this runs.
//
// plan() walks one GFX job's top-level packets with a full_state::Tracker and returns the packets to
// insert (indirect_check::insert_before). A lake writer is a draw with the lake's depth bound
// (DB_Z_WRITE_BASE = 0x1129ec0000 >> 8, F484) and Z_ENABLE and Z_WRITE_ENABLE set. Nothing here writes
// the title's packets; every insert is host-owned. Draws in nested IBs cannot be wrapped: they are
// followed for the state and counted by the census.
//
// The candidate fixes (hypotheses, none proven; they follow from F333, F359, F486, F761):
//   cache=wb|inv|wbinv|all   ACQUIRE_MEM before the job's first lake writer, or each with cache_at=each.
//                            "all" is the kernel's own gfx_v10_0_emit_mem_sync set.
//   cull=1                   CS_PARTIAL_FLUSH and a GL2 write-back and invalidate after each culling pass.
//   pfp=1                    PFP_SYNC_ME before every COND_EXEC and every indirect lake writer.
//   dbmeta=1                 FLUSH_AND_INV_DB_META after each HTILE fill, whose compute shader writes the
//                            metadata behind the DB's back (F310).
//   idle=1                   CS and PS partial flushes before the job's first lake writer.
//   nohiz=1                  DB_RENDER_OVERRIDE forces HiZ and HiS off for the lake writers.
//   trackercf=1              full_state's walkers stop at an INDIRECT_BUFFER CHAIN (F761).
// The catchers:
//   census=1                 per job: lake writers, those inside a COND_EXEC, nested IBs, predication.
//   zpass=1                  occlusion counters around each lake writer, as RADV takes them (Mesa ab2374a
//                            radv_query.c:146-151, radv_cmd_buffer.c:6339-6341). A record whose begin
//                            stayed zero was skipped by the CP.
// TODO(verify): the RB count of gfx1013 (kRecordBytes allows 16); FORCE_HIZ/HIS on hardware; that
// FLUSH_AND_INV_DB_META takes EVENT_INDEX 0 on gfx10 (the regdb names the event, not its index).
// No GPU access.
#pragma once

#include "bc5/full_state.hpp"
#include "bc5/indirect_check.hpp"

#include <cstdint>
#include <span>
#include <string>
#include <string_view>
#include <vector>

namespace bc5::lake_probe {

enum class Cache { off, wb, inv, wbinv, all };

struct Switches {
    Cache cache = Cache::off;
    bool cache_each = false;
    bool cull = false, pfp = false, dbmeta = false, idle = false, nohiz = false, trackercf = false;
    bool census = false, zpass = false;
    bool operator==(const Switches &) const = default;
};

// Space-separated tokens (or a line per token); "#" starts a comment; empty means all off. False, with
// the first bad token, and `out` all off: an unreadable request must not leave a fix half on.
bool parse(std::string_view text, Switches &out, std::string &bad);
std::string describe(const Switches &s);

struct Config {
    std::uint32_t depth_base = 0x1129ec00;
    std::vector<std::uint64_t> cull = {0x11d0375600, 0x11d0376b00, 0x11d0415700, 0x11d04f0c00}; // F355
    std::uint64_t htile_fill = 0x11d0288a00;                                                    // F310
};

inline constexpr std::uint32_t kRecordBytes = 256; // 16 bytes per RB, begin at +0, end at +8 (radv_query.c:1810)

// The occlusion records: one per wrapped writer until they run out.
struct Zpass {
    std::uint64_t va = 0;
    std::uint32_t capacity = 0, used = 0;
};

struct Writer {
    std::size_t at = 0;
    std::uint64_t ps = 0;
    std::uint8_t op = 0;
    bool in_cond = false;
    std::int64_t record = -1;
};

struct Result {
    std::vector<indirect_check::Insert> inserts;
    std::vector<Writer> writers;
    std::uint64_t cond_exec = 0, predication = 0, nested_ibs = 0, cull_barriers = 0, htile_fills = 0;
};

// Advances t over the whole buffer in every case, so a switch can come on at any job.
Result plan(std::span<const std::uint32_t> ib, full_state::Tracker &t, const full_state::Tracker::Reader &read,
            const Switches &s, const Config &c, Zpass *z);

// One run: the control file, re-read every 32 jobs (missing or empty: all off; bad: all off, with a line), the
// census lines, and the records, written to <out> and <out>.meta 200 jobs after zpass goes off or they run out,
// when every job that wrote them is done (the host lets far fewer fly, BC5_DIRECT_MAX_IN_FLIGHT). Times are
// steady_clock ms: CLOCK_MONOTONIC on the box, the clock the poller's lines use. Device owns the records' memory.
class Session {
public:
    Session(std::string ctl, std::string out);
    void attach(std::uint64_t va, void *cpu, std::uint32_t bytes); // zeroed memory; none: zpass wraps nothing
    void step(std::vector<std::uint32_t> &ib, const full_state::Tracker::Reader &read); // one GFX job
    const Switches &switches() const { return sw_; }
    std::uint64_t refused() const { return refused_; } // jobs whose inserts did not fit a COND_EXEC count
    bool dumped() const { return dumped_; }

private:
    void read_ctl();
    void dump();
    std::string ctl_, out_, text_, meta_;
    Switches sw_;
    Config cfg_;
    Zpass z_;
    void *cpu_ = nullptr;
    full_state::Tracker t_;
    std::uint64_t jobs_ = 0, refused_ = 0, census_lines_ = 0;
    std::uint32_t since_end_ = 0;
    bool dumped_ = false;
};

} // namespace bc5::lake_probe
