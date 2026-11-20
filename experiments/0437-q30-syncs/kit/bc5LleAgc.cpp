#include "bc5/env_rule.hpp" // exp 0419 (build W): BC5_DIAG_ENV, BC5_FIXED_ENV, BC5_LEAN_OR
// SPDX-License-Identifier: GPL-2.0-only
//
// BC5 track B (github.com/RedMadKnight/BC5, docs/HANDOFF.md D11, experiments 0009/0010).
//
// When a game's own copies of Sony's libSceAgc.sprx and libSceAgcDriver.sprx (shipped in the
// dump's fakelib/) are LLE-loaded through SHADPS4_SYSMODULES_PACK_DIR instead of KytyPlus's HLE,
// they need 29 imports the HLE does not provide. This file provides them, plus a /dev/gc device
// whose submit ioctls hand the DCBs that Sony's code built to KytyPlus's own GPU path, and an
// optional raw capture of every submitted command buffer (BC5_GC_DUMP_DIR, BC5_GC_DUMP_LIMIT).
//
// Signatures were recovered from the call sites in the two modules (BC5 experiment 0010:
// objdump of the SELF text, arguments per SysV register order). ioctl request codes and their
// argument layouts follow RPCSX rpcsx/iodev/gc.cpp (GPL-2.0, commit e8ae148); codes RPCSX does not
// handle are logged and answered with zeros. Everything here is a first cut whose purpose is to get
// Sony's driver through its initialisation; expect TODOs.

#include <cmath>
#include <optional>
#include <span>
#include <pthread.h>
#include "common/abi.h"
#include "common/assert.h"
#include "common/common.h"
#include "common/logging/log.h"
#include "graphics/presentation/videoOut.h"
#include "kernel/eventQueue.h"
#include "kernel/fileSystem.h"
#include "kernel/memory.h"
#include "libs/agc.h"
#include "libs/errno.h"
#include "libs/libs.h"
#include "bc5/save_guard0412.hpp" // exp 0412 (tag sg412): the save guard of the fault record
#include "loader/symbolDatabase.h"
#include "bc5/start_state.hpp" // experiment 0418 section 4: the start-state table (backend/include/bc5's copy)
#include "bc5/gc_trace.hpp"    // experiment 0418 section 3b: the /dev/gc caller trace (backend/include/bc5's copy)
#include "common/singleton.h"  // experiment 0418 section 3b: the runtime linker, for the callers' modules
#include "loader/elf.h"
#include "loader/runtimeLinker.h"
#if defined(__linux__)
#include <sys/uio.h> // experiment 0418 section 3b: process_vm_readv, a read of the guest's stack that cannot fault
#include <unistd.h>  // experiment 0418 section 3b: getpid
#endif

#if defined(KYTY_BC5_DIRECT)
#include "bc5/direct.hpp"
#include "bc5/full_state.hpp"
#include "bc5/load_stat.hpp" // experiment 0415 (ls415)
#include "bc5/sync_fast.hpp" // experiment 0415 (ls415d)
#include "bc5/map_records.hpp" // experiment 0415 (mr415)
#include "bc5/anon_sync.hpp" // experiment 0415 (as415)
#include <sys/resource.h> // experiment 0379 (exp 0401 e7, mkzsk0401.py): setpriority, for the zero scan and the canary
#include <sys/syscall.h>  // experiment 0379: SYS_gettid
// ---- experiment 0379's backend/include/bc5/zero_skip.hpp (782ca0e9) lines 13-228, inlined by exp 0401's mkzsk0401.py ----
// Series e7 changes no include path, so the header's text is here, byte for byte; the backend keeps its copy and its
// Catch2 test (backend/tests/zero_skip_test.cpp). The skip's host side is in namespace Direct, before direct_sync_one.
#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <map>
#include <sstream>
#include <string>
#include <utility>
#include <vector>

namespace bc5::zero_skip {

inline constexpr std::uint64_t kChunk = 2ull << 20u;

// One heap of the list: its name, its total size (a later run uses the list only if the heap has the same size) and
// its zero runs as (offset from the heap's start, length), chunk aligned, sorted, disjoint.
struct Heap {
    std::string                                       name;
    std::uint64_t                                     size  = 0;
    std::uint32_t                                     scans = 0;
    std::vector<std::pair<std::uint64_t, std::uint64_t>> runs;
};

// The file: "# comment" lines; "heap <name> <size hex> <scans>"; "zero <name> <offset hex> <length hex>".
inline std::string format_list(const std::vector<Heap>& heaps) {
    std::string s = "# bc5 zero list v1 (experiment 0379): chunks all-zero in every scan, offsets from the heap's start\n";
    char        line[256];
    for (const auto& h: heaps) {
        std::snprintf(line, sizeof line, "heap %s 0x%llx %u\n", h.name.c_str(), static_cast<unsigned long long>(h.size), h.scans);
        s += line;
        for (const auto& [o, n]: h.runs) {
            std::snprintf(line, sizeof line, "zero %s 0x%llx 0x%llx\n", h.name.c_str(), static_cast<unsigned long long>(o), static_cast<unsigned long long>(n));
            s += line;
        }
    }
    return s;
}

// Parses format_list's output. Malformed lines, runs that are not chunk aligned, out of the heap or overlapping, and
// runs of an unknown heap are dropped; `bad` counts them.
inline std::vector<Heap> parse_list(const std::string& text, std::uint32_t* bad = nullptr) {
    std::vector<Heap>  heaps;
    std::uint32_t      nbad = 0;
    std::istringstream in(text);
    std::string        line;
    auto               find = [&heaps](const std::string& n) -> Heap* {
        for (auto& h: heaps) {
            if (h.name == n) return &h;
        }
        return nullptr;
    };
    while (std::getline(in, line)) {
        if (!line.empty() && line.back() == '\r') line.pop_back();
        if (line.empty() || line[0] == '#') continue;
        std::istringstream ls(line);
        std::string        kind, name, a, b;
        if (!(ls >> kind >> name >> a >> b)) { nbad++; continue; }
        char*                    e1 = nullptr;
        char*                    e2 = nullptr;
        const unsigned long long x  = std::strtoull(a.c_str(), &e1, 16);
        const unsigned long long y  = std::strtoull(b.c_str(), &e2, kind == "heap" ? 10 : 16);
        if (*e1 != 0 || *e2 != 0) { nbad++; continue; }
        if (kind == "heap") {
            if (find(name) != nullptr || x == 0) { nbad++; continue; }
            heaps.push_back({name, x, static_cast<std::uint32_t>(y), {}});
        } else if (kind == "zero") {
            Heap* h = find(name);
            if (h == nullptr || x % kChunk != 0 || y == 0 || y % kChunk != 0 || x + y > h->size || x + y < x ||
                (!h->runs.empty() && h->runs.back().first + h->runs.back().second > x)) {
                nbad++;
                continue;
            }
            h->runs.emplace_back(x, y);
        } else {
            nbad++;
        }
    }
    if (bad != nullptr) *bad = nbad;
    return heaps;
}

// The scan's state for one heap: chunk i is a candidate while it was all-zero in every scan so far.
class ZeroMask {
public:
    explicit ZeroMask(std::uint64_t heap_size) : zero_((heap_size + kChunk - 1) / kChunk, 1) {}
    std::size_t chunks() const { return zero_.size(); }
    std::uint32_t scans() const { return scans_; }
    // One scan's result for every chunk (1 = all zero now).
    void intersect(const std::vector<std::uint8_t>& now) {
        for (std::size_t i = 0; i < zero_.size(); i++) zero_[i] = zero_[i] != 0 && i < now.size() && now[i] != 0 ? 1 : 0;
        scans_++;
    }
    std::uint64_t zero_bytes() const {
        return static_cast<std::uint64_t>(std::count(zero_.begin(), zero_.end(), std::uint8_t {1})) * kChunk;
    }
    // Runs of at least min_bytes, as (offset, length); a last partial chunk is never listed.
    std::vector<std::pair<std::uint64_t, std::uint64_t>> runs(std::uint64_t heap_size, std::uint64_t min_bytes) const {
        std::vector<std::pair<std::uint64_t, std::uint64_t>> r;
        const std::size_t whole = static_cast<std::size_t>(heap_size / kChunk);
        for (std::size_t i = 0; i < whole;) {
            if (zero_[i] == 0) { i++; continue; }
            std::size_t j = i;
            while (j < whole && zero_[j] != 0) j++;
            const std::uint64_t n = static_cast<std::uint64_t>(j - i) * kChunk;
            if (scans_ != 0 && n >= min_bytes) r.emplace_back(static_cast<std::uint64_t>(i) * kChunk, n);
            i = j;
        }
        return r;
    }

private:
    std::vector<std::uint8_t> zero_;
    std::uint32_t             scans_ = 0;
};

// True when [p, p + n) holds only zero bytes.
inline bool all_zero(const void* p, std::size_t n) {
    const auto* b = static_cast<const unsigned char*>(p);
    std::size_t i = 0;
    for (; i + 8 <= n; i += 8) {
        std::uint64_t w = 0;
        std::memcpy(&w, b + i, 8);
        if (w != 0) return false;
    }
    for (; i < n; i++) {
        if (b[i] != 0) return false;
    }
    return true;
}

// The run's skip set at run time, in absolute chunk offsets (file offsets of the direct-memory memfd). Each run keeps
// its index (its canary slice) for the session; chunks leave one at a time (a CPU write, a hint) or a run at a time
// (a canary hit).
class SkipSet {
public:
    // Adds a run [off, off + len) with a new index; returns the index. Overlaps with present chunks are not added.
    std::uint32_t add_run(std::uint64_t off, std::uint64_t len) {
        const auto idx = static_cast<std::uint32_t>(runs_.size());
        runs_.push_back({off, len});
        for (std::uint64_t c = off; c < off + len; c += kChunk) {
            if (chunk_.emplace(c, idx).second) bytes_ += kChunk;
        }
        return idx;
    }
    bool          contains(std::uint64_t c) const { return chunk_.count(c) != 0; }
    bool          empty() const { return chunk_.empty(); }
    std::uint64_t bytes() const { return bytes_; }
    std::size_t   run_count() const { return runs_.size(); }
    // The run index of a skipped chunk, or -1.
    long run_of(std::uint64_t c) const {
        const auto it = chunk_.find(c);
        return it == chunk_.end() ? -1 : static_cast<long>(it->second);
    }
    std::pair<std::uint64_t, std::uint64_t> run(std::uint32_t idx) const { return runs_.at(idx); }
    // Chunks of run idx still skipped.
    std::uint64_t run_left(std::uint32_t idx) const {
        std::uint64_t n = 0;
        const auto [o, l] = runs_.at(idx);
        for (std::uint64_t c = o; c < o + l; c += kChunk) {
            const auto it = chunk_.find(c);
            if (it != chunk_.end() && it->second == idx) n += kChunk;
        }
        return n;
    }
    // Takes one chunk back; true if it was skipped.
    bool erase_chunk(std::uint64_t c) {
        if (chunk_.erase(c) == 0) return false;
        bytes_ -= kChunk;
        return true;
    }
    // Takes a whole run back; returns the bytes that were still skipped.
    std::uint64_t erase_run(std::uint32_t idx) {
        std::uint64_t n = 0;
        const auto [o, l] = runs_.at(idx);
        for (std::uint64_t c = o; c < o + l; c += kChunk) {
            const auto it = chunk_.find(c);
            if (it != chunk_.end() && it->second == idx) {
                chunk_.erase(it);
                n += kChunk;
            }
        }
        bytes_ -= n;
        return n;
    }
    // Skipped chunks in [lo, hi), ascending.
    std::vector<std::uint64_t> chunks_in(std::uint64_t lo, std::uint64_t hi) const {
        std::vector<std::uint64_t> v;
        for (auto it = chunk_.lower_bound(lo & ~(kChunk - 1)); it != chunk_.end() && it->first < hi; ++it) v.push_back(it->first);
        return v;
    }
    void clear() {
        chunk_.clear();
        runs_.clear();
        bytes_ = 0;
    }

private:
    std::map<std::uint64_t, std::uint32_t>               chunk_; // chunk offset -> run index
    std::vector<std::pair<std::uint64_t, std::uint64_t>> runs_;
    std::uint64_t                                        bytes_ = 0;
};

// Places a list heap at its absolute file offset `base` (the lowest offset of the heap's views) into the skip set.
// Returns the bytes added.
inline std::uint64_t place(const Heap& h, std::uint64_t base, SkipSet* set) {
    std::uint64_t n = 0;
    for (const auto& [o, l]: h.runs) {
        const std::uint64_t before = set->bytes();
        set->add_run(base + o, l);
        n += set->bytes() - before;
    }
    return n;
}

} // namespace bc5::zero_skip
// ---- end of experiment 0379's zero_skip.hpp ------------------------------------------------------------------------
#include "graphics/guest_gpu/tile.h"
#include <fcntl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>
#endif

#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <cstdarg>
#include <fstream>
#include <memory>
#include <cinttypes>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <condition_variable>
#include <deque>
#include <functional>
#include <map>
#include <iterator>
#include <unordered_map>
#include <set>
#include <mutex>
#include <shared_mutex>
#include <string>
#include <thread>
#include <tuple>
#include <vector>

// Experiment 0336: the process parameter (loader/runtimeLinker.cpp)
namespace Loader {
uint64_t Bc5ProcParam();
} // namespace Loader

namespace Libs {

namespace Bc5Gc {

constexpr int OK = 0;

// FreeBSD struct kevent, 64-bit layout (32 bytes); identical to EventQueue::KernelEvent.
struct KEvent {
	uint64_t ident;
	int16_t  filter;
	uint16_t flags;
	uint32_t fflags;
	int64_t  data;
	void*    udata;
};
static_assert(sizeof(KEvent) == 32);

constexpr uint16_t EV_ADD    = 0x0001;
constexpr uint16_t EV_DELETE = 0x0002;

constexpr uint32_t GUEST_MAP_FIXED = 0x10;

static std::mutex        g_mutex;
static void*             g_submit_area = nullptr; // 0xc008811b "submit done flag" page
// sceVideoOutGetBufferLabelAddress target. Experiment 0071: on a page of its own, anonymous and
// read-write, so that it can be mapped for the GPU (the direct path's anonymous mappings and an
// explicit map before a flip-label wait is left to the GPU); in the binary's data it was not
// mapped, and the first wait left to the GPU hung the ring (run 312).
static uint64_t (&g_labels)[64] = *reinterpret_cast<uint64_t (*)[64]>(
    ::mmap(nullptr, 4096, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0));
// Experiment 0069: deferred flips (BC5_DIRECT_FLIP_DEFER) of each buffer still queued; while one
// is, the buffer's label is legitimately set and the next frame must not render into it.
static std::atomic<int>  g_flip_pending[64];
static std::atomic<int>  g_dump_count {0};
static int               g_dump_limit = -1;
static std::string       g_dump_dir;
// BC5_DIRECT_JOURNAL=min (experiment 0022): the crash journal — raw and filtered IB of every
// submission in files, a second filter pass for its "about to submit" line, a sync per
// submission — took half of a frame (81 of 167 ms, run 100). "min" keeps one buffered line per
// submission and the summary lines, flushed twice a second and at once on a failure; nothing is
// dumped. For chasing a hang leave it unset.
// BC5_GC_LOG=verbose: the per-flip and per-ioctl lines of the gc layer (submit headers, the two
// VideoOut ioctls answered with zeros, VideoOut* calls, queue deferrals) in the guest log. Off by
// default since 2026-10-07: they were a fifth of a 780 MB capture and say the same thing every
// frame. The first few of each kind are still logged.
static const bool g_gc_verbose = [] {
	const char* e = BC5_DIAG_ENV("BC5_GC_LOG");
	return e != nullptr && std::strcmp(e, "verbose") == 0;
}();
static bool gc_log_few(int* counter, int limit = 8) {
	return g_gc_verbose || (*counter)++ < limit;
}
// Experiment 0189: what the title's own libSceAgcDriver (LLE) sends /dev/gc for the rings the console's kernel
// programs (run R0 of the second title, once each before its first submission):
//   0x80108128 (16 bytes in): u64 base, u32 size, u32 0 = its tessellation-factor ring (0x1120000000, 0x3fff8),
//                             the arguments of sceAgcDriverSetTFRing by their shape;
//   0x8004812a (4 bytes in):  one dword, 0x1ff, sent right after it: by its place the HS offchip parameter
//                             (sceAgcDriverSetHsOffchipParam). TODO(verify): which register value it is.
// Before, both were answered as unhandled (nothing written back, nothing programmed). They are recorded here;
// Direct::tf_ring_prefix programs them through the start-state table's rows VGT_TF_RING and VGT_HS_OFFCHIP_PARAM (exp 0418:
// always on, as on the console, where the system programs what the driver sends; BC5_DIRECT_START_STATE_SKIP drops a row).
static std::atomic<uint64_t> g_gc_tf_base {0};
static std::atomic<uint32_t> g_gc_tf_size {0};
static std::atomic<uint64_t> g_gc_hs_offchip {0}; // bit 32 = received
// Experiment 0418: "set gs ring sizes" (0xc00c8110) as register values: ESGS bits 0-31, GSVS bits 32-62, bit 63 = received.
static std::atomic<uint64_t> g_gc_gs_rings {0};
// Experiment 0418 section 4: which rows of the start-state table (bc5/start_state.hpp, backend/policy/start-state.tsv)
// are written: all of them, less those BC5_DIRECT_START_STATE_SKIP=<names> names (a diagnostic, read once). The table
// replaced BC5_DIRECT_START_STATE and the one-row switches BC5_DIRECT_GC_TF_RING, BC5_DIRECT_GC_HS_OFFCHIP,
// BC5_DIRECT_CP_COHER_START_DELAY, BC5_DIRECT_SPI_REQ_CTRL_PS and BC5_DIRECT_GC_GS_RINGS; nothing reads them now
// (the top session's dispositions of 2026-11-13, after the umr reads of exp 0418).
static const bc5::start_state::Selection& start_state_sel() {
	static const bc5::start_state::Selection s = [] {
		const auto v = bc5::start_state::select([](const char* n) { return static_cast<const char*>(std::getenv(n)); });
		{
			std::string on, skipped;
			for (std::size_t i = 0; i < bc5::start_state::kRowCount; i++) {
				const char* n = bc5::start_state::kRows[i].name;
				if (((v.on >> i) & 1u) != 0) on += std::string(" ") + n;
				if (((v.skipped >> i) & 1u) != 0) skipped += std::string(" ") + n;
			}
			std::fprintf(stderr, "bc5-direct: start state (exp 0418): rows on:%s; skipped:%s%s\n",
			             on.empty() ? " none" : on.c_str(), skipped.empty() ? " none" : skipped.c_str(),
			             v.unknown_skip != 0 ? "; BC5_DIRECT_START_STATE_SKIP names a row that does not exist" : "");
		}
		return v;
	}();
	return s;
}
static bool gc_tf_ring_on() {
	static const bool v = start_state_sel().row_on("VGT_TF_RING");
	return v;
}
static bool gc_hs_offchip_on() {
	static const bool v = start_state_sel().row_on("VGT_HS_OFFCHIP_PARAM");
	return v;
}
static bool gc_gs_rings_on() {
	static const bool v = start_state_sel().row_on("VGT_GS_RINGS");
	return v;
}

#ifdef BC5_LEAN
static const bool g_journal_min = true; // KYTY_BC5_LEAN: the "min" mode's behaviour (async allowed), no journal
#else
static const bool g_journal_min = [] {
	const char* e = BC5_DIAG_ENV("BC5_DIRECT_JOURNAL");
	return e != nullptr && std::strcmp(e, "min") == 0;
}();
#endif

// Compute/graphics queues registered through ioctl 0xc0408121. Until the doorbell protocol is
// understood, a probe thread logs the submit page and the ring heads for the first minute.
struct QueueReg {
	uint32_t a, b, c, d;
	uint64_t ring_base, ring_end, doorbell_page, doorbell_slot, rptr_addr;
};
static std::vector<QueueReg> g_queues;
// Experiment 0133: the guest queue the ring thread is serving (index into g_queues), -1 elsewhere.
static thread_local int t_queue_idx = -1;
// BC5 (experiment 0161): the CP keeps SET_BASE, the compute program and the user data across the
// buffers of a queue (an INDIRECT_BUFFER continues the ring's state); the filter tracked them per
// buffer from zero, so a DISPATCH_INDIRECT or a BC5_DIRECT_SKIP_PGM program set in an earlier
// buffer went unseen. One per ring kind (graphics, compute), shared by the submitting threads.
// Carrying them did not change the "args not mapped"
// drops (runs 790-791): those come from the title's own SET_BASE [1,0,0] with small offsets
// (0x40, 0x2dfa20) in the same buffer. TODO(verify): what the CP reads for those dispatches.
struct CarriedCpState {
	uint64_t base1 = 0, pgm = 0, ud01 = 0;
	uint32_t ud[16] = {};
};
static CarriedCpState g_carried[2];
static std::mutex     g_carried_mutex;
static bool                  g_queue_probe_started = false;
// Observed protocol (experiment 0012): the mmap'd submit page is an array of u64 write pointers
// in dwords, indexed by (d - 1); the game appends IT_INDIRECT_BUFFER packets to the 16 KiB ring
// and bumps the pointer (8 -> 0x18 -> 0x20 seen for queues 0x21 and 0x29). The read pointer the
// driver looks at lives at rptr_addr. Queues with a == 1 are one engine, a == 2 the other.

static void dump_init() {
	static std::once_flag once;
	std::call_once(once, [] {
		if (const char* d = BC5_DIAG_ENV("BC5_GC_DUMP_DIR"); d != nullptr && *d != 0) {
			g_dump_dir = d;
			g_dump_limit = 4000;
			if (const char* l = BC5_DIAG_ENV("BC5_GC_DUMP_LIMIT"); l != nullptr && *l != 0) {
				g_dump_limit = std::atoi(l);
			}
			LOGF_COLOR(Log::Color::Green, "[bc5-gc] capturing command buffers to %s (limit %d)\n",
			           g_dump_dir.c_str(), g_dump_limit);
		}
	});
}

static void dump_cb(const char* kind, const uint32_t* dwords, uint32_t num_dwords) {
	dump_init();
	if (g_dump_dir.empty() || g_journal_min || !::Log::Bc5LoggingOn() || dwords == nullptr || num_dwords == 0) {
		return;
	}
	int n = g_dump_count.fetch_add(1);
	if (g_dump_limit >= 0 && n >= g_dump_limit) {
		return;
	}
	char name[512];
	std::snprintf(name, sizeof(name), "%s/%06d-%s.bin", g_dump_dir.c_str(), n, kind);
	if (FILE* f = std::fopen(name, "wb"); f != nullptr) {
		std::fwrite(dwords, sizeof(uint32_t), num_dwords, f);
		std::fclose(f);
	}
}

// ---------------------------------------------------------------------------------------------
// Soft CP: executes only the packets a console DCB uses to synchronise with the CPU and the
// display (memory writes, atomics, conditionals, waits, indirect buffers) and skips everything
// else by packet length. Every submit therefore "completes" immediately: labels get written,
// EOP events fire, the game keeps producing frames. Nothing is rendered. KytyPlus's own gfx9
// interpreter cannot consume PS5 buffers (experiment 0011), and this is the seed of BC5's phase-3 CP.
// Packet layouts follow RPCSX rpcsx/gpu/Pipe.cpp @ e8ae148 (GPL-2.0) and AMD's PM4 documentation.
// BC5_GC_MODE=kyty forwards the buffers to KytyPlus's interpreter instead.
// ---------------------------------------------------------------------------------------------
namespace Direct {
// Defined below; the queue consumer hands ring slices to the direct path as well.
static void submit(const uint32_t* ib, uint32_t num_dwords, const char* kind);
// Experiment 0273: the window's Emulation > Ray tracing switch. The pending value is taken at the next
// flip (a frame boundary, ApplyPendingRayTracing in the VideoOut path); the filter reads the active one
// per buffer. KYTY_BC5_RT=0 starts it off; the input configuration's RayTracing.<TITLE_ID>=on|off
// overrides that at load (hostInput.cpp). With it off, dispatches of programs that carry a gfx10
// IMAGE_BVH(64)_INTERSECT_RAY and of the per-title build list (KYTY_BC5_RT_BUILD_PGM) are dropped as
// BC5_DIRECT_SKIP_PGM drops them.
static std::atomic<bool>     g_rt_on {[] { const char* e = std::getenv("KYTY_BC5_RT"); return !(e != nullptr && e[0] == '0' && e[1] == 0); }()};
static std::atomic<int>      g_rt_pending {-1};
static std::atomic<uint64_t> g_rt_dropped {0};
void SetRayTracing(bool on) {
	g_rt_pending.store(on ? 1 : 0, std::memory_order_relaxed);
}
bool GetRayTracing() {
	const int p = g_rt_pending.load(std::memory_order_relaxed);
	return p < 0 ? g_rt_on.load(std::memory_order_relaxed) : p != 0;
}
void ApplyPendingRayTracing() {
	const int p = g_rt_pending.exchange(-1, std::memory_order_relaxed);
	if (p < 0) return;
	const bool on = p != 0;
	if (g_rt_on.exchange(on, std::memory_order_relaxed) != on) {
		std::fprintf(stderr, "bc5-direct: ray tracing %s at the flip (%" PRIu64 " dispatches dropped so far)\n", on ? "on" : "off", g_rt_dropped.load());
	}
}
// Are every cross-queue wait of a compute IB (labels no earlier packet of it writes) satisfied?
// Run 118: what the last acb_ready() that answered "not ready" stopped at — the wait's
// position, label, function, reference and the label's value — for the consumer's diagnostic.
struct UnreadyWait {
	const uint32_t* ib = nullptr;
	uint32_t        num_dwords = 0, pos = 0, function = 0;
	uint64_t        label = 0, value = 0, reference = 0;
};
static thread_local UnreadyWait t_unready;
// Run 123: the label the doorbell consumer's first unready buffer waits on, for the game thread
// to see a cycle — a buffer of its own that waits for that queue while writing the very label
// the queue waits for. 0 when the consumer is not blocked.
static std::atomic<uint64_t> g_unready_label {0};
static std::mutex            g_unready_mutex;
static std::vector<uint64_t> g_unready_writes; // the labels that buffer writes past its wait
static bool acb_ready(const uint32_t* ib, uint32_t num_dwords);
static bool ring_will_satisfy(const uint32_t* p, bool is64, int ring); // experiment 0055
static bool wait_trace();                                        // experiment 0133
static void describe_pending(uint64_t a, char* out, size_t cap); // experiment 0133
static void journal(const char* fmt, ...) __attribute__((format(printf, 1, 2)));
static double timing_now(); // experiment 0343: the journal's time base, for the soft CP's lines
// Experiment 0024: what has to follow a buffer's execution on the GPU — the
// soft CP's pass over it, a ring's read-pointer publication — runs through post(): at once when
// submissions are waited for, otherwise on the completion thread, in submission order, after the
// buffer's jobs have finished. `failed`: one of those jobs did not complete, so none of the
// buffer's packets counts as executed by the GPU. drain() returns when nothing is in flight.
static void post(std::function<void(bool failed)> fn);
static void drain();
// ADR 0010 (BC5_DIRECT_CHAIN=1): the buffers one call hands over go to the GPU as one submission.
static void chain_begin(); // at the start of a submit ioctl / a ring slice: the soft-CP marks start afresh
static void chain_end();   // at its end: the chain is submitted (mode 1), or kept open across the game thread's ioctls (mode 2, ADR 0010 section B)
static bool chain_on();
static bool chain_cross();   // ADR 0010 section B: this thread's chain is held across its ioctls (BC5_DIRECT_CHAIN=2, a game thread)
static bool chain_cross_mode(); // BC5_DIRECT_CHAIN=2 at all
static void chain_observe(); // the title can observe the GPU now (submit done / wait idle / an event-queue wait): every held chain is submitted
static void chain_soft_push_copy(const uint32_t* dwords, uint32_t n, const char* kind);
static void chain_soft_push(const uint32_t* dwords, uint32_t n, const char* kind); // a soft-CP replay to post once the chain holding the buffer is submitted
// The doorbell-queue consumer (source 1) keeps waiting for its own jobs and runs its soft-CP
// pass itself: a compute buffer may end in a wait for the next frame's label, and that wait has
// to block the compute queue and nothing else (run 110: on a shared completion thread it held
// up the game's flip until its timeout). Only the game's threads (source 0) queue and go on.
static void set_source(int index);
// Experiment 0025 (BC5_DIRECT_FRAME_PROFILE=1): where a frame's wall-clock time goes — one journal
// line per flip with the game thread's time inside the host (sync, hints, prepare, list, CS
// ioctl, and the fence when it is waited for), the wait at the flip, the rest (the game's own
// work), and the GPU's busy time from the jobs' queue and completion times.
static void frame_profile_submit(bool game_thread, double sync_ms, double hints_ms);
static void frame_profile_job(bool game_thread, double prepare_ms, double list_ms, double cs_ms);
static void frame_profile_prep(bool game_thread, double filter_ms, double tracker_ms, double cu_ms, double nested_ms, double copy_ms);
static void frame_profile_done(bool game_thread, uint64_t queued_ns, uint64_t done_ns, double fence_ms);
static void frame_profile_flip(double drain_ms);
static bool async_on();
static bool on_game_thread(); // the submitting thread is the game's, not the doorbell consumer's
static void frame_profile_wait(bool game_thread, bool cap, double ms);
static void frame_profile_eqwait(double ms); // the render thread's wait for its event queues
static void frame_profile_post(double ms);   // a soft-CP pass on the completion thread
static void init_once();
} // namespace Direct

namespace SoftCp {

constexpr uint32_t IT_NOP                  = 0x10;
constexpr uint32_t IT_ATOMIC_MEM           = 0x1e;
constexpr uint32_t IT_COND_EXEC            = 0x22;
constexpr uint32_t IT_INDIRECT_BUFFER_CNST = 0x33;
constexpr uint32_t IT_WRITE_DATA           = 0x37;
constexpr uint32_t IT_WAIT_REG_MEM         = 0x3c;
constexpr uint32_t IT_INDIRECT_BUFFER      = 0x3f;
constexpr uint32_t IT_COPY_DATA            = 0x40;
constexpr uint32_t IT_EVENT_WRITE_EOP      = 0x47;
constexpr uint32_t IT_RELEASE_MEM          = 0x49;
constexpr uint32_t IT_DMA_DATA             = 0x50;
constexpr uint32_t IT_WAIT_REG_MEM64       = 0x93;

constexpr int GFX_EOP_EVENT = 0x40; // EVFILT_GRAPHICS ident the driver registers for EOP (RPCSX kGcEventGfxEop)
// The driver also registers 0x48 and 0x46; which one is the compute EOP is not known yet, so a
// compute-ring RELEASE_MEM fires both (TODO(bc5): pin down from the driver's kevent handling).
constexpr int GFX_EOP_EVENT_0     = 0x00; // registered by the game's per-thread EOP queues (run 76)
constexpr int COMPUTE_EOP_EVENT_A = 0x48;
constexpr int COMPUTE_EOP_EVENT_B = 0x46;
static thread_local bool t_compute_ring = false;

struct EqRegistration {
	Libs::LibKernel::EventQueue::KernelEqueue eq;
	int                                        ident;
};
static std::mutex                   g_eq_mutex;
static std::vector<EqRegistration>  g_eqs;
static std::atomic<uint64_t>        g_submits {0};
static std::atomic<uint64_t>        g_packets {0};
static uint64_t                     g_skipped[256];
static std::atomic<uint64_t>        g_waits_timed_out {0};
// Experiment 0343: the soft CP's label polls journaled and, in a replay, bounded. t_wait_bound_ns is
// the deadline of a WAIT_REG_MEM poll on this thread (0: the 2-s deadline of the standalone soft CP
// and of the ring thread's own pass; the completion threads set BC5_DIRECT_SOFT_WAIT_MS around the
// replays they run). t_cur_* name the buffer submit() is executing, for the lines. The counters feed
// the frame profile (polls not satisfied at the first look, their time, those that ran to the deadline).
static thread_local uint64_t        t_wait_bound_ns = 0;
static thread_local const uint32_t* t_cur_buf  = nullptr;
static thread_local uint32_t        t_cur_n    = 0;
static thread_local const char*     t_cur_kind = "?";
static std::atomic<uint64_t>        g_soft_polls {0}, g_soft_poll_ns {0}, g_soft_timeouts {0}, g_soft_lines {0};

static void register_eq(Libs::LibKernel::EventQueue::KernelEqueue eq, int ident, bool add) {
	std::lock_guard lock(g_eq_mutex);
	if (add) {
		g_eqs.push_back({eq, ident});
	} else {
		for (size_t i = 0; i < g_eqs.size(); i++) {
			if (g_eqs[i].eq == eq && g_eqs[i].ident == ident) {
				g_eqs.erase(g_eqs.begin() + static_cast<long>(i));
				break;
			}
		}
	}
}

static void fire(int ident, uint64_t data, bool quiet = false) {
	std::vector<EqRegistration> eqs;
	{
		std::lock_guard lock(g_eq_mutex);
		eqs = g_eqs;
	}
	int n = 0;
	for (const auto& r: eqs) {
		if (r.ident == ident) {
			Libs::LibKernel::EventQueue::KernelTriggerEvent(
			    r.eq, static_cast<uintptr_t>(ident), Libs::LibKernel::EventQueue::KERNEL_EVFILT_GRAPHICS,
			    reinterpret_cast<void*>(data));
			n++;
		}
	}
	if (n == 0 && !quiet) {
		LOGF_COLOR(Log::Color::Yellow, "[bc5-cp] event 0x%x fired but nobody is listening\n", ident);
	}
}

static void fire_eop(uint64_t data) {
	if (t_compute_ring) {
		fire(COMPUTE_EOP_EVENT_A, data);
		fire(COMPUTE_EOP_EVENT_B, data);
	} else {
		fire(GFX_EOP_EVENT, data);
		// The game's five "GpuDevice::EopEq" queues register EVFILT_GRAPHICS ident 0 and every
		// wait on them timed out (experiment 0016, run 76: five timeouts and ~3 s per frame).
		// TODO(verify): which interrupt the console maps to ident 0 — here every gfx-queue EOP
		// interrupt wakes them (the waiters re-check their labels, as they do after a timeout).
		fire(GFX_EOP_EVENT_0, data, true);
	}
}

static inline uint64_t now_ns() {
	return static_cast<uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(
	                                 std::chrono::steady_clock::now().time_since_epoch())
	                                 .count());
}

static inline uint64_t addr64(uint32_t lo, uint32_t hi, uint32_t hi_mask = 0xffffu) {
	return (lo & ~3u) | (static_cast<uint64_t>(hi & hi_mask) << 32u);
}

static bool compare(uint32_t function, uint32_t value, uint32_t mask, uint32_t reference) {
	value &= mask;
	reference &= mask;
	switch (function & 7u) {
		case 0: return true;
		case 1: return value < reference;
		case 2: return value <= reference;
		case 3: return value == reference;
		case 4: return value != reference;
		case 5: return value >= reference;
		case 6: return value > reference;
		default: return true;
	}
}

// ---- experiment 0405 (exp 0401 series e5, tag gpu): R3's e4-now items in the soft CP and the gc ioctls ---------------
// Experiment 0405 raw/r3-gpu-memory.md, "e4-now port specs" G2, G4, G6, G8, G11, G12 and G14. Nothing here changes what is
// submitted to amdgpu: the policy (backend/policy/pm4-policy.tsv, "default-op drop") still NOPs MEM_SEMAPHORE, COND_WRITE
// and REWIND on the GPU path. What changes is the soft CP's own execution, host events after a fence, and catchers (a
// count, and one journal line per kind). No header is touched: all state lives in this file. Each item has its own switch,
// off by default and read once, at the first use (bc5::env_on, backend/include/bc5/env_flag.hpp, F767: on when set,
// non-empty and not "0"); off, each site takes today's path. The first use prints one line on stderr:
// "[bc5] exp 0405: gpu on (items: <switches>)" or "[bc5] exp 0405: gpu off".
//   BC5_R3_MEMSEM_SIGNAL     G2   MEM_SEMAPHORE (0x39) signals run in the soft CP; waits are counted only
//   BC5_R3_REWIND_CATCH      G4   catcher: REWIND (0x59) with its VALID bit clear
//   BC5_R3_DROP_CATCH        G8   catcher: packets the policy table drops, per opcode; custom NOPs, per sub-code
//   BC5_R3_SUBMIT_EOP_EVENT  G6   ioctl 0xc020810c raises the graphics EOP event after the call's buffers
//   BC5_R3_COND_WRITE        G11  COND_WRITE (0x45) runs in the soft CP
//   BC5_R3_WAIT_IDLE         G12  ioctl 0xc0048117 returns once the completion queues are empty (at most 2 s)
//   BC5_R3_TS_100MHZ         G14  the soft CP's GPU-clock timestamps as a 100-MHz count
// Journal (Direct::journal, BC5_GC_DUMP_DIR/direct.log): the first occurrence of each kind with where it was, then only
// counts; a summary line "exp 0405 gpu: ..." at most every 10 s (from submit() below) when a count has moved.
// Upstream code is GPL (AnyPS5 4f41f4c37 GPL-2.0-only, KytyPS5 dfec14a GPL-2.0, shadPS4 60c42b9 GPL-2.0-or-later, RPCSX
// e8ae148 GPL-2.0, sharpemu 514d766 GPL-2.0-or-later): only behaviour is taken, rewritten here, and their copyrights stay
// with their authors. Mesa ab2374a (MIT) gives opcode facts only.
constexpr uint32_t IT_MEM_SEMAPHORE = 0x39; // Mesa ab2374a src/amd/common/sid.h:88
constexpr uint32_t IT_COND_WRITE    = 0x45; // sid.h:128
constexpr uint32_t IT_REWIND        = 0x59; // sid.h:206, "GFX8+ [any ring]"

struct R3Gpu {
	bool memsem = false, rewind = false, drop = false, submit_eop = false, cond_write = false, wait_idle = false, ts100 = false;
	bool any() const { return memsem || rewind || drop || submit_eop || cond_write || wait_idle || ts100; }
};
static bool r3gpu_env(const char* name) {
	const char* e = std::getenv(name);
#if defined(KYTY_BC5_DIRECT)
	return bc5::env_on(e);
#else
	return e != nullptr && e[0] != 0 && !(e[0] == '0' && e[1] == 0); // bc5::env_on's reading (its header comes with the backend)
#endif
}
static const R3Gpu& r3gpu() {
	static const R3Gpu s = [] {
		R3Gpu       v;
		std::string items;
		auto        take = [&items](const char* name) {
			const bool on = r3gpu_env(name);
			if (on) {
				if (!items.empty()) items += ", ";
				items += name;
			}
			return on;
		};
		v.memsem     = BC5_LEAN_OR(true, take("BC5_R3_MEMSEM_SIGNAL"));
		v.rewind     = false; /* exp 0419: option removed */
		v.drop       = false; /* exp 0419: option removed */
		v.submit_eop = false; /* exp 0419: option removed (the walk never reaches its path) */
		v.cond_write = BC5_LEAN_OR(true, take("BC5_R3_COND_WRITE"));
		v.wait_idle  = BC5_LEAN_OR(true, take("BC5_R3_WAIT_IDLE"));
		v.ts100      = BC5_LEAN_OR(true, take("BC5_R3_TS_100MHZ"));
		if (v.any()) {
			std::fprintf(stderr, "[bc5] exp 0405: gpu on (items: %s)\n", items.c_str());
		} else {
			std::fprintf(stderr, "[bc5] exp 0405: gpu off\n");
		}
		return v;
	}();
	return s;
}

// The counts (the CPU test reads them by these indices through bc5_exp0405_gpu_count).
enum R3GpuCount : int {
	kR3MemsemSet,      // G2: signals with SIGNAL_TYPE 1 (the word set to 1)
	kR3MemsemAdd,      // G2: signals with SIGNAL_TYPE 0 (1 added)
	kR3MemsemWait,     // G2: waits (op 7), not held (G3 is a later port)
	kR3MemsemOther,    // G2: not executed (not 4 dwords, address 0, an op other than 6 and 7)
	kR3Rewind,         // G4: REWIND packets walked
	kR3RewindInvalid,  // G4: ... with VALID (dword 1 bit 31) clear
	kR3DropPackets,    // G8: packets whose opcode the policy table drops
	kR3NopCustom,      // G8: NOPs with header bits 7:2 not 0
	kR3EopEvents,      // G6: EOP events raised for the submit-and-write-EOP ioctl
	kR3EopChained,     // G6: ... of which handed to a held chain (BC5_DIRECT_CHAIN=2)
	kR3CondWritten,    // G11: condition true, the dword written
	kR3CondNotWritten, // G11: condition false
	kR3CondOther,      // G11: not executed (register poll or destination, function 7, not 9 dwords, address 0)
	kR3WaitIdle,       // G12: wait-idle ioctls that waited
	kR3WaitIdleGaveUp, // G12: ... that gave up at 2 s
	kR3TsWrites,       // G14: timestamps written as a 100-MHz count
	kR3CountN
};
static std::atomic<uint64_t> g_r3gpu_count[kR3CountN];
static std::atomic<uint64_t> g_r3gpu_drop_op[256]; // G8, per opcode
static std::atomic<uint64_t> g_r3gpu_nop_sub[64];  // G8, per custom-NOP sub-code
static std::atomic<uint64_t> g_r3gpu_seen[6];      // the kinds journaled once: bits 0-255 opcodes, 256-319 sub-codes, 320+ others
constexpr uint32_t           kR3SeenSub   = 256;
constexpr uint32_t           kR3SeenOther = 320;
static bool r3gpu_first(uint32_t bit) {
	const uint64_t m = 1ull << (bit & 63u);
	return (g_r3gpu_seen[bit >> 6u].fetch_or(m, std::memory_order_relaxed) & m) == 0;
}
// Where a packet was, for a journal line: its address and offset in the buffer the soft CP walks (the submitted buffer or
// an INDIRECT_BUFFER target), and the buffer submit() was handed (t_cur_*; stale on the ring thread's own passes).
static void r3gpu_where(char* out, size_t cap, const uint32_t* buf, uint32_t at) {
	std::snprintf(out, cap, "packet at %p (offset %u of the buffer at %p), in %s %u dwords at %p", static_cast<const void*>(buf + at), at,
				  static_cast<const void*>(buf), t_cur_kind, t_cur_n, static_cast<const void*>(t_cur_buf));
}

// G2 (BC5_R3_MEMSEM_SIGNAL). The console's form, 4 dwords (KytyPS5 src/graphics/guest_gpu/command_processor/
// pm4Handlers.cpp:2077-2088, header 0xc0023900; AnyPS5 core/libs/prx/libSceAgcDriver/Execution/src/Pm4.cpp:507-512, size 4;
// sharpemu src/SharpEmu.Libs/Agc/AgcExports.MemSemaphore.cs:47-58, the builder: op << 29 | type << 20 | mailbox << 16):
// dword 1 the address (bits 31:3), dword 2 its high bits, dword 3 the control: SEM_SEL bits 31:29 (6 signal, 7 wait),
// SIGNAL_TYPE bit 20, USE_MAILBOX bit 16 (the field names: shadPS4 src/video_core/amdgpu/pm4_cmds.h PM4CmdMemSemaphore, in
// the PS4's 3-dword form). The semaphore is a 64-bit word (AnyPS5 docs/dev/debt/libSceAgcDriver.md:62: inferred from the
// 8-byte alignment the builder checks, not measured). A signal with SIGNAL_TYPE 1 stores 1, with 0 adds 1, atomically
// (AnyPS5 Pm4.cpp:1130-1147; KytyPS5 src/graphics/guest_gpu/graphicsRun.cpp:277-285; shadPS4 pm4_cmds.h Signal(),
// src/video_core/amdgpu/liverpool.cpp:799-809); KytyPS5 notes a signal's mailbox never stalls. A wait (op 7, G3) is
// counted and journaled only: holding the queue is a later port. The address's high dword keeps 16 bits, as everywhere
// in this soft CP (addr64; KytyPS5 keeps 18, AnyPS5 all: the same for user addresses below 2^47). The GPU path still NOPs
// the packet (pm4-policy.tsv default-op drop).
static void r3gpu_mem_semaphore(const uint32_t* buf, uint32_t at, uint32_t len) {
	const uint32_t* p       = buf + at;
	const uint32_t  control = len == 4 ? p[3] : 0u;
	const uint32_t  sel     = control >> 29u;
	const uint64_t  a       = len == 4 ? addr64(p[1] & ~7u, p[2]) : 0;
	char            where[256];
	if (len != 4 || a == 0 || (sel != 6 && sel != 7)) {
		g_r3gpu_count[kR3MemsemOther]++;
		if (r3gpu_first(kR3SeenOther + 0)) {
			r3gpu_where(where, sizeof(where), buf, at);
			Direct::journal("exp 0405 gpu: MEM_SEMAPHORE not executed (%u dwords, control 0x%08x, address 0x%" PRIx64 "), %s; counted from here\n", len, control, a, where);
		}
		return;
	}
	if (sel == 7) {
		g_r3gpu_count[kR3MemsemWait]++;
		if (r3gpu_first(kR3SeenOther + 1)) {
			r3gpu_where(where, sizeof(where), buf, at);
			Direct::journal("exp 0405 gpu: MEM_SEMAPHORE wait on 0x%" PRIx64 " (control 0x%08x) not held (G3 is a later port), %s; counted from here\n", a, control, where);
		}
		return;
	}
	auto*      w   = reinterpret_cast<uint64_t*>(a);
	const bool set = (control & 0x100000u) != 0;
	if (set) {
		__atomic_store_n(w, uint64_t {1}, __ATOMIC_RELEASE);
	} else {
		__atomic_fetch_add(w, uint64_t {1}, __ATOMIC_ACQ_REL);
	}
	g_r3gpu_count[set ? kR3MemsemSet : kR3MemsemAdd]++;
	if (r3gpu_first(kR3SeenOther + 2)) {
		r3gpu_where(where, sizeof(where), buf, at);
		Direct::journal("exp 0405 gpu: MEM_SEMAPHORE signal (%s) on 0x%" PRIx64 " executed by the soft CP, %s; counted from here\n", set ? "set 1" : "add 1", a, where);
	}
}

// G4 (BC5_R3_REWIND_CATCH), a catcher: nothing is executed. REWIND is 2 dwords, dword 1 bit 31 VALID and bit 24
// OFFLOAD_ENABLE (AnyPS5 Execution/include/Pm4.hpp:162-163, Pm4.cpp:497-500; shadPS4 pm4_cmds.h PM4CmdRewind; KytyPS5
// pm4Handlers.cpp:1324-1333, header 0xc0005900). With VALID clear the console's parser stops there until the CPU sets the
// bit and then fetches what follows afresh (shadPS4 liverpool.cpp:815-824, KytyPS5 WaitForRewind). The GPU path NOPs it
// and runs the copy made at submission. Counted: every REWIND the soft CP walks, and those with VALID clear; the first of
// these is journaled with where it was and how many of the dwords after it in that buffer are not 0. The soft CP reads
// guest memory when it runs (after the fence when posted), when the CPU may have set the bit already: a lower bound.
static void r3gpu_rewind(const uint32_t* buf, uint32_t at, uint32_t num_dwords, uint32_t len) {
	g_r3gpu_count[kR3Rewind]++;
	if (len != 2 || (buf[at + 1] & 0x80000000u) != 0) return;
	g_r3gpu_count[kR3RewindInvalid]++;
	if (!r3gpu_first(kR3SeenOther + 3)) return;
	uint32_t nonzero = 0;
	for (uint32_t k = at + len; k < num_dwords; k++) {
		if (buf[k] != 0) nonzero++;
	}
	char where[256];
	r3gpu_where(where, sizeof(where), buf, at);
	Direct::journal("exp 0405 gpu: REWIND with VALID clear (dword 1 0x%08x), %s; %u of the %u dwords after it in that buffer are not 0; counted from here\n", buf[at + 1], where,
					nonzero, num_dwords - at - len);
}

// G8 (BC5_R3_DROP_CATCH), a catcher on the unit's side (the backend's FilterStats has no per-opcode count, and the backend
// is not this experiment's to change): every type-3 packet the soft CP walks whose opcode the policy table gives the
// verdict Drop (bc5::policy::Policy::builtin().op(), the table the filter uses: pm4-policy.tsv's "default-op drop" line,
// and its two listed drops 0x4a PREAMBLE_CNTL and 0x8e GET_LOD_STATS, which the query cannot tell apart), per opcode; and
// every NOP (0x10) whose header bits 7:2 are not 0, per sub-code: the console's custom NOPs (KytyPS5
// src/graphics/guest_gpu/pm4.h:74-84 and command_processor/pm4Dispatch.cpp:223-229; AnyPS5 Execution/src/Pm4.cpp:223-240,
// header & 0xfc, sub-code (header >> 2) & 0x3f). The policy passes NOP and the AMD CP ignores its payload. The first packet
// of each opcode and of each sub-code is journaled. Not seen: what a COND_EXEC skipped in the soft CP, IBs nested deeper
// than 4, and the filter's own drops in code (unmapped operands and the like). Without the direct path (no
// KYTY_BC5_DIRECT) there is no policy: only the sub-codes are counted.
static void r3gpu_drop_note(const uint32_t* buf, uint32_t at, uint32_t header, uint32_t op) {
	char where[256];
	if (op == IT_NOP) {
		if ((header & 0xfcu) == 0) return;
		const uint32_t sub = (header >> 2u) & 0x3fu;
		g_r3gpu_nop_sub[sub]++;
		g_r3gpu_count[kR3NopCustom]++;
		if (r3gpu_first(kR3SeenSub + sub)) {
			r3gpu_where(where, sizeof(where), buf, at);
			Direct::journal("exp 0405 gpu: custom NOP sub-code 0x%02x (header 0x%08x), %s; counted from here\n", sub, header, where);
		}
		return;
	}
#if defined(KYTY_BC5_DIRECT)
	if (bc5::policy::Policy::builtin().op(static_cast<uint8_t>(op)) != bc5::policy::Verdict::Drop) return;
	g_r3gpu_drop_op[op & 0xffu]++;
	g_r3gpu_count[kR3DropPackets]++;
	if (r3gpu_first(op & 0xffu)) {
		r3gpu_where(where, sizeof(where), buf, at);
		Direct::journal("exp 0405 gpu: opcode 0x%02x (header 0x%08x) is NOP-ed by the policy on the GPU path, %s; counted from here\n", op, header, where);
	}
#endif
}

// G11 (BC5_R3_COND_WRITE): COND_WRITE, 9 dwords: dword 1 FUNCTION bits 2:0, POLL_SPACE bit 4 (1 memory), WRITE_SPACE bits
// 9:8 (1 memory); the poll address in dwords 2-3, the reference in 4, the mask in 5, the write address in 6-7, the data in
// 8 (AnyPS5 Execution/src/Pm4.cpp:513-520 and 736-739; RPCSX rpcsx/gpu/Pipe.cpp:1266-1300). When (*poll & mask) <function>
// (reference & mask) holds, the dword is written. RPCSX masks both sides (Pipe.cpp:66-88), as this soft CP's compare() does
// for WAIT_REG_MEM; AnyPS5 (Pm4.cpp:589-600) masks the value only: they differ only for reference bits outside the mask,
// TODO(verify). Register polls, register or scratch destinations and the reserved function 7 are counted and not executed
// (AnyPS5 refuses them, RPCSX's compare is false for 7). The GPU path still NOPs the packet.
static void r3gpu_cond_write(const uint32_t* buf, uint32_t at, uint32_t len) {
	const uint32_t* p       = buf + at;
	const uint32_t  control = len == 9 ? p[1] : 0u;
	const uint64_t  poll    = len == 9 ? addr64(p[2], p[3]) : 0;
	const uint64_t  dst     = len == 9 ? addr64(p[6], p[7]) : 0;
	char            where[256];
	if (len != 9 || (control & 7u) == 7u || ((control >> 4u) & 1u) == 0 || ((control >> 8u) & 3u) != 1u || poll == 0 || dst == 0) {
		g_r3gpu_count[kR3CondOther]++;
		if (r3gpu_first(kR3SeenOther + 4)) {
			r3gpu_where(where, sizeof(where), buf, at);
			Direct::journal("exp 0405 gpu: COND_WRITE not executed (%u dwords, control 0x%08x, poll 0x%" PRIx64 ", write 0x%" PRIx64 "), %s; counted from here\n", len, control, poll, dst,
							where);
		}
		return;
	}
	const uint32_t value = *reinterpret_cast<volatile uint32_t*>(poll);
	const bool     hit   = compare(control & 7u, value, p[5], p[4]);
	if (hit) *reinterpret_cast<volatile uint32_t*>(dst) = p[8];
	g_r3gpu_count[hit ? kR3CondWritten : kR3CondNotWritten]++;
	if (r3gpu_first(kR3SeenOther + 5)) {
		r3gpu_where(where, sizeof(where), buf, at);
		Direct::journal("exp 0405 gpu: COND_WRITE executed by the soft CP (function %u, value 0x%08x, reference 0x%08x, mask 0x%08x: %s 0x%08x to 0x%" PRIx64 "), %s; counted from here\n",
						control & 7u, value, p[4], p[5], hit ? "wrote" : "did not write", p[8], dst, where);
	}
}

// G6 (BC5_R3_SUBMIT_EOP_EVENT): the gc ioctl 0xc020810c "submit and write eop" raises the graphics EOP interrupt with its
// eopValue once its buffers are done. RPCSX rpcsx/iodev/gc.cpp:250-277 submits the buffers, then DeviceCtl::submitWriteEop
// (rpcsx/gpu/DeviceCtl.cpp:60-80): an EVENT_WRITE_EOP with address 0, INT_SEL 2 and DATA_SEL 2 carrying eopValue, which its
// pipe delivers as kGcEventGfxEop 0x40 (rpcsx/gpu/Pipe.cpp:20-30). Here: fire_eop(eopValue) on the graphics side (0x40,
// and ident 0 quietly, as for a RELEASE_MEM with INT_SEL), through Direct::post: after the fence of the call's buffers on
// the completion thread when submission is asynchronous (BC5_DIRECT_JOURNAL=min), at once when each job is waited for or
// there is no direct path. With the game thread's chain held across its ioctls (BC5_DIRECT_CHAIN=2) the buffers are not
// submitted yet, so RPCSX's EVENT_WRITE_EOP itself (6 dwords, the form event_write_eop below reads; address 0, so nothing
// is written) goes to the chain as a soft-CP replay, posted behind the chain's fence. The replay reads it later, so it
// owns a copy through completion of its callback. Nothing is submitted to the GPU for it. RPCSX also waits for idle at the end of this
// ioctl (gc.cpp:271); that is not ported here (G12 is the wait-idle ioctl's).
static void r3gpu_submit_eop(uint64_t eop_value) {
	g_r3gpu_count[kR3EopEvents]++;
	const bool chained = Direct::chain_cross();
	if (chained) {
		uint32_t s[6] {}; // copied into the queued replay before returning
		s[0]        = 0xc0044700u;                 // PKT3 EVENT_WRITE_EOP (0x47), count 4: 6 dwords
		s[1]        = 0;                           // EVENT_CNTL (RPCSX: the event type is not used)
		s[2]        = 0;                           // address lo
		s[3]        = (2u << 24u) | (2u << 29u);   // INT_SEL 2, DATA_SEL 2, address hi 0
		s[4]        = static_cast<uint32_t>(eop_value);
		s[5]        = static_cast<uint32_t>(eop_value >> 32u);
		g_r3gpu_count[kR3EopChained]++;
		Direct::chain_soft_push_copy(s, 6, "r3eop");
	} else {
		Direct::post([eop_value](bool) { fire_eop(eop_value); });
	}
	if (r3gpu_first(kR3SeenOther + 6)) {
		Direct::journal("exp 0405 gpu: submit-and-write-EOP ioctl: the graphics EOP event (0x40) with 0x%" PRIx64 " raised after the call's buffers%s; counted from here\n", eop_value,
						chained ? " (behind the held chain)" : "");
	}
}

// G12 (BC5_R3_WAIT_IDLE): the count and the journal of the wait in gc_ioctl (0xc0048117).
static void r3gpu_wait_idle_note(bool gave_up, double ms) {
	g_r3gpu_count[kR3WaitIdle]++;
	if (gave_up) g_r3gpu_count[kR3WaitIdleGaveUp]++;
	if (r3gpu_first(kR3SeenOther + 7)) Direct::journal("exp 0405 gpu: wait-idle ioctl waited %.1f ms for the completion queues; counted from here\n", ms);
	if (gave_up && r3gpu_first(kR3SeenOther + 8)) Direct::journal("exp 0405 gpu: wait-idle ioctl gave up after %.1f ms with the completion queues not empty; counted from here\n", ms);
}

// G14 (BC5_R3_TS_100MHZ): the soft CP's GPU-clock timestamps (RELEASE_MEM / EVENT_WRITE_EOP DATA_SEL 3, Mesa sid.h:168
// EOP_DATA_SEL_TIMESTAMP; COPY_DATA SRC_SEL 9, sid.h:107 COPY_DATA_TIMESTAMP) as a 100-MHz count. AnyPS5's debt note
// docs/dev/debt/libSceAgcDriver.md:287 measured both as one counter at 98.0 and 99.8 MHz on a PS5 (firmware 13.40), and
// AnyPS5 Execution/src/Pm4.cpp:1178-1180 writes the steady clock in 10-ns ticks. The epoch is the host's steady clock, not
// the GPU's own counter that the direct path's GPU-written timestamps carry: TODO(verify) the box's gpu_counter_freq (amdgpu
// device info) before mixing the two. DATA_SEL 4 and SRC_SEL 0xa keep nanoseconds: their console frequency is not measured.
static uint64_t r3gpu_clock() {
	g_r3gpu_count[kR3TsWrites]++;
	return now_ns() / 10u;
}

// The summary line, at most every 10 s and only when a count has moved; from submit() (any switch on).
static void r3gpu_summary() {
	static std::mutex m;
	static uint64_t   last_ns = 0, last_total = 0;
	std::unique_lock  lk(m, std::try_to_lock);
	if (!lk.owns_lock()) return;
	const uint64_t now = now_ns();
	if (last_ns != 0 && now - last_ns < 10'000'000'000ull) return;
	last_ns = now;
	uint64_t c[kR3CountN];
	uint64_t total = 0;
	for (int k = 0; k < kR3CountN; k++) {
		c[k] = g_r3gpu_count[k].load(std::memory_order_relaxed);
		total += c[k];
	}
	if (total == last_total) return;
	last_total = total;
	std::string ops, subs;
	char        b[32];
	for (uint32_t k = 0; k < 256; k++) {
		if (const uint64_t v = g_r3gpu_drop_op[k].load(std::memory_order_relaxed); v != 0) {
			std::snprintf(b, sizeof(b), " %02x:%" PRIu64, k, v);
			ops += b;
		}
	}
	for (uint32_t k = 0; k < 64; k++) {
		if (const uint64_t v = g_r3gpu_nop_sub[k].load(std::memory_order_relaxed); v != 0) {
			std::snprintf(b, sizeof(b), " %02x:%" PRIu64, k, v);
			subs += b;
		}
	}
	Direct::journal("exp 0405 gpu: t %.3f s: MEM_SEMAPHORE set %" PRIu64 " add %" PRIu64 " wait %" PRIu64 " other %" PRIu64 "; REWIND %" PRIu64 " (VALID clear %" PRIu64 "); dropped by the policy %" PRIu64
					" (by opcode:%s); custom NOPs %" PRIu64 " (by sub-code:%s); submit-EOP events %" PRIu64 " (chained %" PRIu64 "); COND_WRITE wrote %" PRIu64 " not %" PRIu64 " other %" PRIu64
					"; wait idle %" PRIu64 " (gave up %" PRIu64 "); 100-MHz timestamps %" PRIu64 "\n",
					Direct::timing_now(), c[kR3MemsemSet], c[kR3MemsemAdd], c[kR3MemsemWait], c[kR3MemsemOther], c[kR3Rewind], c[kR3RewindInvalid], c[kR3DropPackets], ops.c_str(),
					c[kR3NopCustom], subs.c_str(), c[kR3EopEvents], c[kR3EopChained], c[kR3CondWritten], c[kR3CondNotWritten], c[kR3CondOther], c[kR3WaitIdle], c[kR3WaitIdleGaveUp],
					c[kR3TsWrites]);
}
// ---- end of experiment 0405's (tag gpu) soft-CP block ------------------------------------------------------------------

// Writes `value` per DATA_SEL (bits 31:29 of the data-control dword) to `address`.
static void write_timestamp_or_data(uint32_t data_sel, uint64_t address, uint32_t lo, uint32_t hi) {
	if (address == 0) {
		return;
	}
	switch (data_sel) {
		case 0: break;
		case 1: *reinterpret_cast<volatile uint32_t*>(address) = lo; break;
		case 2:
			*reinterpret_cast<volatile uint64_t*>(address) = lo | (static_cast<uint64_t>(hi) << 32u);
			break;
		case 3:
			if (r3gpu().ts100) { // experiment 0405 G14 (BC5_R3_TS_100MHZ): the GPU clock as a 100-MHz count; off, today's ns
				*reinterpret_cast<volatile uint64_t*>(address) = r3gpu_clock();
				break;
			}
			[[fallthrough]];
		case 4: *reinterpret_cast<volatile uint64_t*>(address) = now_ns(); break;
		default:
			LOGF_COLOR(Log::Color::Yellow, "[bc5-cp] data_sel %u not handled\n", data_sel);
			break;
	}
}

// Packets of the buffer the real GPU has just executed (direct mode, same thread: Direct::submit
// then SoftCp::submit). For those the soft CP skips the memory side effects (writes, atomics,
// copies, waits) the GPU already produced and only keeps what the GPU cannot do here: the
// EVFILT_GRAPHICS events (INT_SEL is cleared by the filter).
struct GpuDone {
	const uint32_t*      buf;
	std::vector<uint8_t> done;
};
static thread_local std::vector<GpuDone> t_gpu_done; // the IB and its INDIRECT_BUFFER targets
static void set_gpu_executed(const uint32_t* buf, uint32_t num_dwords, const std::vector<uint32_t>& offsets) {
	GpuDone g {buf, std::vector<uint8_t>(num_dwords, 0)};
	for (const uint32_t o: offsets) {
		if (o < num_dwords) g.done[o] = 1;
	}
	t_gpu_done.push_back(std::move(g));
}
static void clear_gpu_executed() {
	t_gpu_done.clear();
}
// Experiment 0157: the marks of a copy that ran on the GPU (a prefix of `skip` dwords, then `n` dwords
// of `orig`) carried over to `orig`; the copy's own entry goes, its memory is about to be reused.
static void alias_gpu_executed(const uint32_t* copy, size_t skip, const uint32_t* orig, uint32_t n) {
	for (auto it = t_gpu_done.begin(); it != t_gpu_done.end(); ++it) {
		if (it->buf != copy) continue;
		GpuDone h {orig, std::vector<uint8_t>(n, 0)};
		for (uint32_t o = 0; o < n && skip + o < it->done.size(); o++) h.done[o] = it->done[skip + o];
		t_gpu_done.erase(it);
		t_gpu_done.push_back(std::move(h));
		return;
	}
}
// Was the packet at `pkt` executed by the real GPU? The entries are the IB, its INDIRECT_BUFFER
// targets and, for an IB split at a cross-queue wait, its pieces — so the lookup is by range.
static bool gpu_packet_done(const uint32_t* pkt) {
	for (const auto& g: t_gpu_done) {
		if (pkt >= g.buf && pkt < g.buf + g.done.size()) return g.done[static_cast<size_t>(pkt - g.buf)] != 0;
	}
	return false;
}

static void atomic_mem(const uint32_t* p) {
	const uint32_t op    = p[1] & 0x7fu;
	const uint64_t addr  = addr64(p[2], p[3]);
	const uint64_t src   = p[4] | (static_cast<uint64_t>(p[5]) << 32u);
	const uint64_t cmp   = p[6] | (static_cast<uint64_t>(p[7]) << 32u);
	const bool     is64  = (op & 0x40u) != 0;
	const uint32_t base  = op & 0x1fu; // TC_OP without the RTN/64 modifiers
	if (addr == 0) {
		return;
	}
	auto apply = [&](uint64_t old) -> uint64_t {
		switch (base) {
			case 0x00: return src;                                     // swap
			case 0x01: return old == cmp ? src : old;                  // cmpswap
			case 0x07: return old + src;                               // add
			case 0x08: return old - src;                               // sub
			case 0x09: return static_cast<int64_t>(old) < static_cast<int64_t>(src) ? old : src; // smin
			case 0x0a: return old < src ? old : src;                   // umin
			case 0x0b: return static_cast<int64_t>(old) > static_cast<int64_t>(src) ? old : src; // smax
			case 0x0c: return old > src ? old : src;                   // umax
			case 0x0d: return old & src;                               // and
			case 0x0e: return old | src;                               // or
			case 0x0f: return old ^ src;                               // xor
			case 0x10: return old >= src ? 0 : old + 1;                // inc (wrap at src)
			case 0x11: return (old == 0 || old > src) ? src : old - 1; // dec
			default:
				LOGF_COLOR(Log::Color::Yellow, "[bc5-cp] atomic op 0x%02x not handled\n", op);
				return old;
		}
	};
	if (is64) {
		auto* m = reinterpret_cast<volatile uint64_t*>(addr);
		*m      = apply(*m);
	} else {
		auto* m = reinterpret_cast<volatile uint32_t*>(addr);
		*m      = static_cast<uint32_t>(apply(*m));
	}
}

static void copy_data(const uint32_t* p) {
	const uint32_t control  = p[1];
	const uint32_t src_sel  = control & 0xfu;
	const uint32_t dst_sel  = (control >> 8u) & 0xfu;
	const bool     is64     = ((control >> 16u) & 1u) != 0;
	uint64_t       value    = 0;
	switch (src_sel) {
		case 1:
		case 2: { // memory (sync / TC L2)
			const uint64_t a = addr64(p[2], p[3]);
			if (a == 0) return;
			value = is64 ? *reinterpret_cast<volatile uint64_t*>(a) : *reinterpret_cast<volatile uint32_t*>(a);
			break;
		}
		case 5: value = p[2] | (static_cast<uint64_t>(p[3]) << 32u); break; // immediate
		case 9:                                                              // perf counter
			// Experiment 0405 G14 (BC5_R3_TS_100MHZ): SRC_SEL 9 is the GPU clock (Mesa sid.h:107 COPY_DATA_TIMESTAMP),
			// as a 100-MHz count; off, today's ns.
			if (r3gpu().ts100) {
				value = r3gpu_clock();
				break;
			}
			[[fallthrough]];
		case 0xa: value = now_ns(); break;                                   // timestamp
		default:
			LOGF_COLOR(Log::Color::Yellow, "[bc5-cp] COPY_DATA src_sel %u not handled\n", src_sel);
			return;
	}
	switch (dst_sel) {
		case 1:
		case 2:
		case 5: { // memory
			const uint64_t a = addr64(p[4], p[5]);
			if (a == 0) return;
			if (is64) {
				*reinterpret_cast<volatile uint64_t*>(a) = value;
			} else {
				*reinterpret_cast<volatile uint32_t*>(a) = static_cast<uint32_t>(value);
			}
			break;
		}
		default:
			LOGF_COLOR(Log::Color::Yellow, "[bc5-cp] COPY_DATA dst_sel %u not handled\n", dst_sel);
			break;
	}
}

static void write_data(const uint32_t* p, uint32_t payload) {
	const uint32_t control = p[1];
	const uint32_t dst_sel = (control >> 8u) & 0xfu;
	const bool     one_addr = ((control >> 16u) & 1u) != 0;
	if (dst_sel != 1 && dst_sel != 2 && dst_sel != 5) {
		return; // registers, GDS: nothing to do
	}
	const uint64_t a = addr64(p[2], p[3]);
	if (a == 0 || payload < 3) {
		return;
	}
	const uint32_t n = payload - 3;
	auto*          d = reinterpret_cast<volatile uint32_t*>(a);
	for (uint32_t i = 0; i < n; i++) {
		if (one_addr) {
			*d = p[4 + i];
		} else {
			d[i] = p[4 + i];
		}
	}
}

// Experiment 0343: a poll that was not satisfied at the first look. Counted for the frame profile;
// journaled through Direct::journal (which the session's printf direction does not silence) when it
// lasted over 50 ms or ran to its deadline: the label, function, reference and value, the buffer
// (kind, pointer; the packet's offset in it, or its address when it lies in an INDIRECT_BUFFER target)
// and whether the marks were empty (then every packet counts as not run by the GPU). Exp 0341's 22-s
// hold (F415) was eleven such polls at 2 s each inside bc5-cq0's replays, with no line anywhere.
static void soft_wait_done(const uint32_t* p, bool is64, uint64_t a, uint32_t function, uint64_t t0, bool timed_out) {
	const uint64_t held = now_ns() - t0;
	g_soft_polls++;
	g_soft_poll_ns += held;
	if (timed_out) g_soft_timeouts++;
	if (held < 50'000'000ull && !timed_out) return;
	if (g_soft_lines++ >= 2000) return; // the counters go on, the lines stop
	const uint64_t  ref   = is64 ? (p[4] | (static_cast<uint64_t>(p[5]) << 32u)) : p[4];
	const uint64_t  value = is64 ? *reinterpret_cast<volatile uint64_t*>(a) : *reinterpret_cast<volatile uint32_t*>(a);
	const bool      in    = t_cur_buf != nullptr && p >= t_cur_buf && p < t_cur_buf + t_cur_n;
	const long long where = in ? static_cast<long long>(p - t_cur_buf) : -1;
	Direct::journal("soft-cp wait: t %.3f s WAIT_REG_MEM%s on 0x%" PRIx64 " %s after %.1f ms (bound %" PRIu64 " ms): fn %u ref 0x%" PRIx64 " value 0x%" PRIx64 "; %s %u dwords at %p, packet at %p (offset %lld); marks %s\n",
	                Direct::timing_now(), is64 ? "64" : "", a, timed_out ? "TIMED OUT" : "satisfied", static_cast<double>(held) / 1e6,
	                (t_wait_bound_ns != 0 ? t_wait_bound_ns : 2'000'000'000ull) / 1'000'000ull, function, ref, value, t_cur_kind, t_cur_n,
	                static_cast<const void*>(t_cur_buf), static_cast<const void*>(p), where, t_gpu_done.empty() ? "empty" : "set");
}

static void wait_reg_mem(const uint32_t* p, bool is64) {
	const uint32_t function  = p[1] & 7u;
	const bool     mem_space = ((p[1] >> 4u) & 1u) != 0;
	if (!mem_space) {
		return; // register polls are meaningless here
	}
	const uint64_t a = addr64(p[2], p[3]);
	if (a == 0) {
		return;
	}
	const uint64_t t0       = now_ns();
	const uint64_t deadline = t0 + (t_wait_bound_ns != 0 ? t_wait_bound_ns : 2'000'000'000ull); // experiment 0343
	bool           polled   = false; // experiment 0343: not satisfied at the first look
	for (;;) {
		bool ok;
		if (is64) {
			// WAIT_REG_MEM64: ref lo/hi at p[4],p[5], mask lo/hi at p[6],p[7]
			const uint64_t v    = *reinterpret_cast<volatile uint64_t*>(a);
			const uint64_t ref  = p[4] | (static_cast<uint64_t>(p[5]) << 32u);
			const uint64_t mask = p[6] | (static_cast<uint64_t>(p[7]) << 32u);
			const uint64_t vm = v & mask, rm = ref & mask;
			switch (function) {
				case 0: ok = true; break;
				case 1: ok = vm < rm; break;
				case 2: ok = vm <= rm; break;
				case 3: ok = vm == rm; break;
				case 4: ok = vm != rm; break;
				case 5: ok = vm >= rm; break;
				case 6: ok = vm > rm; break;
				default: ok = true; break;
			}
		} else {
			ok = compare(function, *reinterpret_cast<volatile uint32_t*>(a), p[5], p[4]);
		}
		if (ok) {
			if (polled) soft_wait_done(p, is64, a, function, t0, false); // experiment 0343
			return;
		}
		polled = true;
		if (now_ns() > deadline) {
			g_waits_timed_out++;
			soft_wait_done(p, is64, a, function, t0, true); // experiment 0343
			LOGF_COLOR(Log::Color::Yellow, "[bc5-cp] WAIT_REG_MEM%s on 0x%" PRIx64 " timed out (fn %u ref 0x%x), continuing\n",
			           is64 ? "64" : "", a, function, p[4]);
			return;
		}
		std::this_thread::yield();
	}
}

static void release_mem(const uint32_t* p, uint32_t payload, bool write) {
	// gfx10 form (8 dwords): event_cntl, data_cntl, addr lo, addr hi, data lo, data hi, int_ctxid
	const uint32_t data_cntl = p[2];
	const uint32_t data_sel  = data_cntl >> 29u;
	const uint32_t int_sel   = (data_cntl >> 24u) & 3u;
	const uint64_t a         = addr64(p[3], p[4]);
	const uint32_t lo = p[5], hi = p[6];
	(void)payload;
	if (write) write_timestamp_or_data(data_sel, a, lo, hi);
	if (int_sel != 0) {
		fire_eop(lo | (static_cast<uint64_t>(hi) << 32u));
	}
}

static void event_write_eop(const uint32_t* p, bool write) {
	// PS4 form: event_cntl, addr lo, data_cntl (addr hi 15:0, int_sel 25:24, data_sel 31:29), data lo, hi
	const uint32_t data_cntl = p[3];
	const uint32_t data_sel  = data_cntl >> 29u;
	const uint32_t int_sel   = (data_cntl >> 24u) & 3u;
	const uint64_t a         = addr64(p[2], data_cntl);
	if (write) write_timestamp_or_data(data_sel, a, p[4], p[5]);
	if (int_sel != 0) {
		fire_eop(p[4] | (static_cast<uint64_t>(p[5]) << 32u));
	}
}

static void execute(const uint32_t* buf, uint32_t num_dwords, int depth);

// ---- compute dispatch capture (phase 2 task 3) ------------------------------------------------
// SH register shadow (offsets relative to 0x2c00) kept per executing thread; on every dispatch the
// compute state and the shader code are written next to the command buffers. Register offsets from
// Mesa gfx10.json via bc5-agc (COMPUTE_PGM_LO 0x20c etc., HANDOFF F7).
constexpr uint32_t IT_DISPATCH_DIRECT   = 0x15;
constexpr uint32_t IT_DISPATCH_INDIRECT = 0x16;
constexpr uint32_t IT_SET_SH_REG        = 0x76;
constexpr uint32_t IT_SET_SH_REG_INDEX  = 0x9b;
constexpr uint32_t S_CODE_END           = 0xbf9f0000u; // gfx10 s_code_end (pads every shader)
constexpr uint32_t S_ENDPGM             = 0xbf810000u;

static thread_local uint32_t t_sh[0x400];
static std::mutex            g_shader_mutex;
static std::vector<uint64_t> g_shaders_dumped; // shader VAs already written
static std::atomic<uint64_t> g_dispatches {0};

static void set_sh_regs(const uint32_t* p, uint32_t payload, bool indexed) {
	if (payload < 2) {
		return;
	}
	const uint32_t off = p[1] & 0xffffu;
	for (uint32_t i = 0; i + 1 < payload; i++) {
		if (off + i < 0x400) {
			t_sh[off + i] = p[2 + i];
		}
	}
	(void)indexed;
}

// Length of a shader: up to and including the first s_code_end, capped at 64 KiB. Scanning stops
// early at an unmapped page boundary check is not possible here, so the cap keeps reads inside the
// code allocation (Sony pads every program with s_code_end).
static uint32_t shader_length_dwords(const uint32_t* code) {
	constexpr uint32_t cap = 65536 / 4;
	for (uint32_t i = 0; i < cap; i++) {
		if (code[i] == S_CODE_END) {
			return i + 1;
		}
		// An s_endpgm followed by four dwords of zero padding ends a program that is not padded
		// with s_code_end (Sony's small built-in programs, e.g. the buffer fill: 9 dwords).
		if (code[i] == S_ENDPGM && i + 4 < cap && code[i + 1] == 0 && code[i + 2] == 0 &&
		    code[i + 3] == 0 && code[i + 4] == 0) {
			return i + 1;
		}
	}
	return cap;
}

static void record_dispatch(const uint32_t* p, bool indirect) {
	const uint64_t n = g_dispatches.fetch_add(1);
	if (g_dump_dir.empty() || g_journal_min || !::Log::Bc5LoggingOn()) {
		return;
	}
	const uint64_t pgm = (static_cast<uint64_t>(t_sh[0x20c]) | (static_cast<uint64_t>(t_sh[0x20d]) << 32u)) << 8u;
	bool           dump_code = false;
	{
		std::lock_guard lock(g_shader_mutex);
		if (pgm != 0 && std::find(g_shaders_dumped.begin(), g_shaders_dumped.end(), pgm) == g_shaders_dumped.end()) {
			g_shaders_dumped.push_back(pgm);
			dump_code = true;
		}
	}
	uint32_t code_dwords = 0;
	if (pgm != 0) {
		const auto* code = reinterpret_cast<const uint32_t*>(pgm);
		code_dwords      = shader_length_dwords(code);
		if (dump_code) {
			char name[512];
			std::snprintf(name, sizeof(name), "%s/cs-%012" PRIx64 ".bin", g_dump_dir.c_str(), pgm);
			if (FILE* f = std::fopen(name, "wb"); f != nullptr) {
				std::fwrite(code, 4, code_dwords, f);
				std::fclose(f);
			}
		}
	}
	char name[512];
	std::snprintf(name, sizeof(name), "%s/dispatch-%06" PRIu64 ".txt", g_dump_dir.c_str(), n);
	FILE* f = std::fopen(name, "w");
	if (f == nullptr) {
		return;
	}
	std::fprintf(f, "dispatch %" PRIu64 " %s ring=%s\n", n, indirect ? "indirect" : "direct",
	             t_compute_ring ? "compute" : "gfx");
	if (indirect) {
		std::fprintf(f, "indirect_offset 0x%08x\n", p[1]);
	} else {
		std::fprintf(f, "dim %u %u %u initiator 0x%08x\n", p[1], p[2], p[3], p[4]);
	}
	std::fprintf(f, "pgm_va 0x%012" PRIx64 " code_dwords %u\n", pgm, code_dwords);
	std::fprintf(f, "rsrc1 0x%08x rsrc2 0x%08x rsrc3 0x%08x\n", t_sh[0x212], t_sh[0x213], t_sh[0x228]);
	std::fprintf(f, "num_thread %u %u %u resource_limits 0x%08x tmpring 0x%08x\n", t_sh[0x207],
	             t_sh[0x208], t_sh[0x209], t_sh[0x215], t_sh[0x218]);
	std::fprintf(f, "static_thread_mgmt 0x%08x 0x%08x 0x%08x 0x%08x\n", t_sh[0x216], t_sh[0x217],
	             t_sh[0x219], t_sh[0x21a]);
	std::fprintf(f, "user_data");
	for (int i = 0; i < 16; i++) {
		std::fprintf(f, " %08x", t_sh[0x240 + i]);
	}
	std::fprintf(f, "\n");
	std::fclose(f);
}

static void indirect_buffer(const uint32_t* p, int depth) {
	const uint64_t a    = addr64(p[1], p[2], 0xffu);
	const uint32_t size = p[3] & 0xfffffu;
	if (a == 0 || size == 0 || depth >= 4) {
		return;
	}
	dump_cb(depth == 0 ? "ib1" : "ib2", reinterpret_cast<const uint32_t*>(a), size);
	execute(reinterpret_cast<const uint32_t*>(a), size, depth + 1);
}

static void execute(const uint32_t* buf, uint32_t num_dwords, int depth) {
	uint32_t i = 0;
	while (i < num_dwords) {
		const bool done = !t_gpu_done.empty() && gpu_packet_done(buf + i); // this packet ran on the real GPU
		const uint32_t header = buf[i];
		const uint32_t type   = header >> 30u;
		uint32_t       len    = 1;
		if (type == 3) {
			const uint32_t count = (header >> 16u) & 0x3fffu;
			len                  = count == 0x3fffu ? 1 : count + 2;
			const uint32_t op    = (header >> 8u) & 0xffu;
			const uint32_t* p    = buf + i;
			if (i + len > num_dwords) {
				LOGF_COLOR(Log::Color::Red, "[bc5-cp] packet 0x%08x at %u overruns the buffer (%u dwords)\n",
				           header, i, num_dwords);
				break;
			}
			g_packets++;
			if (r3gpu().drop) r3gpu_drop_note(buf, i, header, op); // experiment 0405 G8 (BC5_R3_DROP_CATCH): a catcher, nothing executed
			switch (op) {
				case IT_NOP: break;
				case IT_COND_EXEC: {
					// skip the next exec_count dwords when the 32-bit value at the address is zero
					const uint64_t a = addr64(p[1], p[2]);
					const uint32_t exec_count = p[4] & 0x3fffu;
					if (a != 0 && *reinterpret_cast<volatile uint32_t*>(a) == 0) {
						len += exec_count;
					}
					break;
				}
				case IT_INDIRECT_BUFFER:
				case IT_INDIRECT_BUFFER_CNST: indirect_buffer(p, depth); break;
				case IT_WRITE_DATA: if (!done) write_data(p, len - 1); break;
				case IT_WAIT_REG_MEM: if (!done) wait_reg_mem(p, false); break;
				case IT_WAIT_REG_MEM64: if (!done) wait_reg_mem(p, true); break;
				case IT_COPY_DATA: if (!done) copy_data(p); break;
				case IT_ATOMIC_MEM: if (!done) atomic_mem(p); break;
				case IT_EVENT_WRITE_EOP: event_write_eop(p, !done); break;
				case IT_RELEASE_MEM: release_mem(p, len - 1, !done); break;
				case IT_SET_SH_REG: set_sh_regs(p, len - 1, false); g_skipped[op]++; break;
				case IT_SET_SH_REG_INDEX: set_sh_regs(p, len - 1, true); g_skipped[op]++; break;
				case IT_DISPATCH_DIRECT: record_dispatch(p, false); g_skipped[op]++; break;
				case IT_DISPATCH_INDIRECT: record_dispatch(p, true); g_skipped[op]++; break;
				// Experiment 0405 (exp 0401 series e5, tag gpu): G2, G11 and G4. Off, each takes the default's path below.
				case IT_MEM_SEMAPHORE: // G2 (BC5_R3_MEMSEM_SIGNAL)
					if (!r3gpu().memsem) {
						g_skipped[op & 0xffu]++;
						break;
					}
					if (!done) r3gpu_mem_semaphore(buf, i, len);
					break;
				case IT_COND_WRITE: // G11 (BC5_R3_COND_WRITE)
					if (!r3gpu().cond_write) {
						g_skipped[op & 0xffu]++;
						break;
					}
					if (!done) r3gpu_cond_write(buf, i, len);
					break;
				case IT_REWIND: // G4 (BC5_R3_REWIND_CATCH): counted, not executed
					if (r3gpu().rewind) r3gpu_rewind(buf, i, num_dwords, len);
					g_skipped[op & 0xffu]++;
					break;
				default: g_skipped[op & 0xffu]++; break;
			}
		} else if (type == 0) {
			len = ((header >> 16u) & 0x3fffu) + 2; // type-0 register write: N+1 registers
		} else if (type == 2) {
			len = 1;
		} else {
			LOGF_COLOR(Log::Color::Red, "[bc5-cp] type-1 packet 0x%08x at %u: stopping this buffer\n", header, i);
			break;
		}
		i += len;
	}
}

static void submit(const uint32_t* buf, uint32_t num_dwords, const char* kind) {
	const uint64_t n = g_submits.fetch_add(1);
	t_cur_buf  = buf; // experiment 0343: for the soft-cp wait lines
	t_cur_n    = num_dwords;
	t_cur_kind = kind;
	execute(buf, num_dwords, 0);
	if (r3gpu().any()) r3gpu_summary(); // experiment 0405 (tag gpu): at most every 10 s
	if (n < 16 || (n & 0xffu) == 0) {
		std::string skipped;
		for (int op = 0; op < 256; op++) {
			if (g_skipped[op] != 0) {
				char b[32];
				std::snprintf(b, sizeof(b), " %02x:%" PRIu64, op, g_skipped[op]);
				skipped += b;
			}
		}
		if (!g_journal_min) {
			LOGF("[bc5-cp] submit #%" PRIu64 " (%s, %u dwords) done; packets so far %" PRIu64 "; skipped by opcode:%s; wait timeouts %" PRIu64 "\n",
			     n, kind, num_dwords, g_packets.load(), skipped.c_str(), g_waits_timed_out.load());
		}
	}
}

// ---- experiment 0405 (tag gpu): the CPU test's seams (gpu0405.cpp); always compiled in, never called by the emulator ----
// bc5_exp0405_gpu_count takes the R3GpuCount indices above.
extern "C" int bc5_exp0405_gpu_switches() {
	const R3Gpu& s = r3gpu();
	return (s.memsem ? 1 : 0) | (s.rewind ? 2 : 0) | (s.drop ? 4 : 0) | (s.submit_eop ? 8 : 0) | (s.cond_write ? 16 : 0) | (s.wait_idle ? 32 : 0) |
		   (s.ts100 ? 64 : 0);
}
extern "C" void bc5_exp0405_gpu_soft_submit(const uint32_t* buf, uint32_t num_dwords) {
	submit(buf, num_dwords, "gpu0405");
}
extern "C" uint64_t bc5_exp0405_gpu_count(int which) {
	return which >= 0 && which < kR3CountN ? g_r3gpu_count[which].load() : 0;
}
extern "C" uint64_t bc5_exp0405_gpu_drop_op(uint32_t op) {
	return g_r3gpu_drop_op[op & 0xffu].load();
}
extern "C" uint64_t bc5_exp0405_gpu_nop_sub(uint32_t sub) {
	return g_r3gpu_nop_sub[sub & 0x3fu].load();
}
extern "C" int bc5_exp0405_gpu_has_policy() {
#if defined(KYTY_BC5_DIRECT)
	return 1;
#else
	return 0;
#endif
}
extern "C" void bc5_exp0405_gpu_register_eq(int64_t eq, int ident, int add) {
	register_eq(eq, ident, add != 0);
}
extern "C" void bc5_exp0405_gpu_post(void (*fn)(void*), void* arg) {
	Direct::post([fn, arg](bool) { fn(arg); });
}
extern "C" int bc5_exp0405_gpu_async() {
	return Direct::async_on() ? 1 : 0;
}
// ---- end of experiment 0405's (tag gpu) seams ------------------------------------------------------------------------

// Consumes the hardware-style queues the driver registered (ioctl 0xc0408121): for each queue,
// packets between our read pointer and the game's write pointer (submit page, u64 per queue, in
// dwords) are executed, the read pointer is published at rptr_addr. Compute-ring EOPs fire the
// compute event idents. Polled at 1 kHz; the driver never tells us about a doorbell write.
static const bool g_direct_rings = std::getenv("BC5_GC_MODE") != nullptr && std::strcmp(std::getenv("BC5_GC_MODE"), "direct") == 0;

static void queue_consumer_thread() {
	pthread_setname_np(pthread_self(), "bc5-ring"); // BC5: host threads named for per-thread CPU views (F81)
	pthread_setname_np(pthread_self(), "bc5-ring"); // BC5: host threads named for per-thread CPU views (F81)
	Direct::set_source(1);
	struct State {
		QueueReg reg;
		uint64_t rptr           = 0;
		uint64_t count          = 0;
		uint64_t deferred_since = 0; // direct mode: this queue's next IB waits on another queue
		uint64_t deferred_report = 0; // when the deferral was last journaled (run 118)
	};
	std::vector<State> states;
	uint64_t           idle_ticks = 0;
	for (;;) {
		{
			std::lock_guard lock(g_mutex);
			while (states.size() < g_queues.size()) {
				states.push_back({g_queues[states.size()], 0, 0});
			}
		}
		bool progressed = false;
		for (auto& s: states) {
			const auto& q     = s.reg;
			t_queue_idx       = static_cast<int>(&s - states.data()); // experiment 0133
			if (s.count == 0 && s.deferred_report == 0 && ::Log::Bc5LoggingOn() && BC5_DIAG_ENV("BC5_DIRECT_WAIT_TRACE") != nullptr) {
				s.deferred_report = 1;
				Direct::journal("queue %d: a %u b %u c %u d %u ring 0x%" PRIx64 "-0x%" PRIx64 "\n", t_queue_idx, q.a, q.b, q.c, q.d, q.ring_base, q.ring_end);
			}
			const auto* page  = reinterpret_cast<const volatile uint64_t*>(q.doorbell_page);
			const uint64_t wraw = page[q.d == 0 ? 0 : q.d - 1];
			const uint32_t n    = static_cast<uint32_t>((q.ring_end - q.ring_base) / 4);
			if (n == 0) {
				continue;
			}
			// The pointers are dword offsets inside the ring: the driver writes its doorbell
			// modulo the ring size (experiment 0018, run 92: after the first wrap the old absolute
			// comparison walked the whole ring again and again), and reads the read pointer the
			// same way. s.rptr is kept below n.
			const uint32_t w = static_cast<uint32_t>(wraw % n);
			const uint32_t r = static_cast<uint32_t>(s.rptr % n);
			if (w == r) {
				continue;
			}
			const uint32_t pending = (w + n - r) % n;
			const auto* ring = reinterpret_cast<const uint32_t*>(q.ring_base);
			auto packet_len = [&](uint32_t off) -> uint32_t {
				const uint32_t hh = ring[off];
				if ((hh >> 30u) != 3) return 1;
				const uint32_t c = (hh >> 16u) & 0x3fffu;
				return c == 0x3fffu ? 1 : c + 2;
			};
			// Direct mode, queue ordering (run 46): a compute IB whose cross-queue wait is not yet
			// satisfied is left in its queue — the read pointer stays, the other queues are served
			// (the writer is one of them or the gfx queue) — and retried on the next poll, for up
			// to 10 s. That is the console's blocking compute queue, on one ring.
			// A queue runs its entries in order: the ones in front whose waits are satisfied are
			// served now, whatever stands behind them (experiment 0024: with all-or-nothing, a
			// buffer whose label had been set was held back by the next one in the queue until
			// the game reset the label — a slot label is only set for two frames).
			uint32_t take = pending;
			if (g_direct_rings) {
				bool     ready     = true;
				uint32_t ready_len = 0;
				for (uint32_t k = 0; k < pending && ready;) {
					const uint32_t off = (r + k) % n;
					const uint32_t hh  = ring[off];
					const uint32_t ll  = packet_len(off);
					if ((hh >> 30u) == 3 && (((hh >> 8u) & 0xffu) == IT_INDIRECT_BUFFER || ((hh >> 8u) & 0xffu) == IT_INDIRECT_BUFFER_CNST) && ll >= 4 && off + ll <= n) {
						const uint64_t ta = (ring[off + 1] & ~3u) | (static_cast<uint64_t>(ring[off + 2] & 0xffu) << 32u);
						const uint32_t tn = ring[off + 3] & 0xfffffu;
						if (ta != 0 && tn != 0 && !Direct::acb_ready(reinterpret_cast<const uint32_t*>(ta), tn)) ready = false;
					}
					k += ll;
					if (ready) ready_len = k < pending ? k : pending;
				}
				const uint64_t now = now_ns();
				if (!ready && ready_len != 0) {
					take             = ready_len;
					s.deferred_since = 0;
				} else if (!ready) {
					if (s.deferred_since == 0) s.deferred_since = now;
					if (now - s.deferred_since >= 1'000'000'000ull && now - s.deferred_report >= 1'000'000'000ull) {
						s.deferred_report = now;
						const auto& u = Direct::t_unready;
						const char* msg = "[bc5-q] queue %u/%u/%u/0x%x: deferred %.1f s, %u dwords pending, %u ready in front; the first unready buffer (%u dwords at %p) waits at %u on 0x%" PRIx64 ": function %u, value 0x%" PRIx64 ", reference 0x%" PRIx64 "\n";
						LOGF_COLOR(Log::Color::Yellow, msg, q.a, q.b, q.c, q.d, static_cast<double>(now - s.deferred_since) / 1e9, pending, ready_len, u.num_dwords, static_cast<const void*>(u.ib), u.pos, u.label, u.function, u.value, u.reference);
						Direct::journal(msg, q.a, q.b, q.c, q.d, static_cast<double>(now - s.deferred_since) / 1e9, pending, ready_len, u.num_dwords, static_cast<const void*>(u.ib), u.pos, u.label, u.function, u.value, u.reference);
					}
					if (now - s.deferred_since < 10'000'000'000ull) continue; // served later
					LOGF_COLOR(Log::Color::Yellow, "[bc5-q] queue %u/%u/%u/0x%x: cross-queue wait unsatisfied for 10 s, proceeding\n", q.a, q.b, q.c, q.d);
					s.deferred_since = 0;
				} else {
					static int deferred_logged = 0;
					if (s.deferred_since != 0 && gc_log_few(&deferred_logged, 32)) {
						LOGF("[bc5-q] queue %u/%u/%u/0x%x: deferred %.1f ms for another queue\n", q.a, q.b, q.c, q.d, static_cast<double>(now - s.deferred_since) / 1e6);
					}
					s.deferred_since = 0;
				}
			}
			const uint32_t w_all = w;
			(void)w_all;
			const uint32_t w_take = (r + take) % n;
			// Direct mode: the ring slice [r, w_take) is itself a valid IB of INDIRECT_BUFFER packets;
			// a slice that wraps is submitted in two parts.
			Direct::chain_begin(); // ADR 0010: the slice's buffers as one submission
			if (w_take > r) {
				Direct::submit(ring + r, w_take - r, "ring");
			} else {
				Direct::submit(ring + r, n - r, "ring");
				if (w_take != 0) Direct::submit(ring, w_take, "ring");
			}
			Direct::chain_end();
			{
				auto marks = std::move(t_gpu_done);
				t_gpu_done.clear();
				const QueueReg qq     = q;
				const uint64_t count0 = s.count;
				s.count += take;
				Direct::post([ring, r, n, w = w_take, pending = take, qq, count0, marks = std::move(marks)](bool failed) mutable {
					t_gpu_done = failed ? std::vector<GpuDone>() : std::move(marks);
					auto plen = [&](uint32_t off) -> uint32_t {
						const uint32_t hh = ring[off];
						if ((hh >> 30u) != 3) return 1;
						const uint32_t c = (hh >> 16u) & 0x3fffu;
						return c == 0x3fffu ? 1 : c + 2;
					};
					uint32_t done = 0, guard = 0;
					uint64_t count = count0;
					while (done < pending && guard++ < 4096) {
						const uint32_t off    = (r + done) % n;
						const uint32_t header = ring[off];
						const uint32_t len    = plen(off);
						if ((header >> 30u) == 3 && off + len <= n) {
							t_compute_ring = (qq.a == 2); // TODO(bc5): which engine is compute is a guess
							const uint32_t op = (header >> 8u) & 0xffu;
							if (count < 8) {
								LOGF("[bc5-q] queue %u/%u/%u/0x%x: packet #%" PRIu64 " op 0x%02x len %u (rptr %u wptr %u)\n",
								     qq.a, qq.b, qq.c, qq.d, count, op, len, off, w);
							}
							if (op == IT_INDIRECT_BUFFER || op == IT_INDIRECT_BUFFER_CNST) {
								indirect_buffer(ring + off, 0);
							} else {
								execute(ring + off, len, 1);
							}
							t_compute_ring = false;
						}
						done += len;
						count++;
						g_packets++;
					}
					t_gpu_done.clear();
					// The read pointer goes where the queue registration named it and — what the
					// driver library's free-space check actually reads (its queue table, +0x70;
					// experiment 0018) — into the dword right behind the ring.
					*reinterpret_cast<volatile uint32_t*>(qq.rptr_addr) = w;
					*reinterpret_cast<volatile uint32_t*>(qq.ring_end) = w;
				});
			}
			s.rptr = w_take; // what was served; the rest of the slice stays for the next poll
			// The read pointer goes where the queue registration named it and — what the driver
			// library's free-space check actually reads (its queue table, +0x70; experiment
			// 0018) — into the dword right behind the ring. Nothing wrote the latter before, so
			// each ring looked never drained and was "full" after 4,088 dwords: the game stopped
			// at its 511th frame.
			progressed = true;
		}
		if (progressed) {
			idle_ticks = 0;
		} else {
			idle_ticks++;
		}
		// Experiment 0415 (ls415): the poll's period is 200 us, the long-idle sleep 5 times it. The counters say how many
		// passes found work right after a sleep.
		static bool ls_slept = false;
		if (progressed) {
			bc5::load_stat::count(bc5::load_stat::kRingPass);
			if (ls_slept) bc5::load_stat::count(bc5::load_stat::kRingAfterSleep);
			bc5::load_stat::delay(bc5::load_stat::kRingPass);
		}
		ls_slept = true;
		std::this_thread::sleep_for(std::chrono::microseconds(idle_ticks > 1000 ? bc5::load_stat::kRingPollUs * 5 : bc5::load_stat::kRingPollUs));
	}
}

} // namespace SoftCp

static bool use_soft_cp() {
	static const bool soft = [] {
		const char* m = std::getenv("BC5_GC_MODE");
		return m == nullptr || std::strcmp(m, "kyty") != 0;
	}();
	return soft;
}

// ---------------------------------------------------------------------------------------------
// Direct submission (ADR 0005), BC5_GC_MODE=direct. The guest's resident anonymous memory is
// mapped 1:1 into the GPU as userptr BOs (amdgpu refuses
// file-backed pages), every IB the game submits goes through the policy filter to the GFX ring,
// and the soft CP still runs afterwards for the events and labels.
// A fence timeout (2 s) wedges the device: nothing more is submitted, the soft CP carries on.
// ---------------------------------------------------------------------------------------------
namespace Direct {

enum class Stage { Off, All };

// A line in BC5_GC_DUMP_DIR/direct.log, the record that survives a hang. The file is synced to
// disk once per submission, right before the IB goes to the GPU (the "submit #n" line), which
// makes every earlier line durable too. Syncing each line and each IB dump cost most of a frame
// (run 78: 1.3 s for the frame DCB with its hundred table lines).
static void journal(const char* fmt, ...) __attribute__((format(printf, 1, 2)));
static FILE* journal_min_file(bool flush_now) {
	static FILE* const f = [] {
		char name[512];
		std::snprintf(name, sizeof(name), "%s/direct.log", g_dump_dir.c_str());
		FILE* o = std::fopen(name, "a");
		if (o != nullptr) std::setvbuf(o, nullptr, _IOFBF, 1u << 20u);
		return o;
	}();
	static std::atomic<uint64_t> last_flush {0};
	if (f != nullptr) {
		const uint64_t now = SoftCp::now_ns();
		if (flush_now || now - last_flush > 500'000'000ull) {
			std::fflush(f);
			last_flush = now;
		}
	}
	return f;
}
// ---- exp 0401 series e7 (tag cap): BC5_DIRECT_JOURNAL_QUIET, the journal without its per-event lines -------------------
// cap0401-notes.md section 6. In the play's environment (bc5-run.env: BC5_DIRECT_JOURNAL=min, BC5_DIRECT_TIMING=1,
// BC5_DIRECT_FRAME_PROFILE=1) direct.log grows by about 0.5 GB in 15 minutes, every arm alike; much of it is lines written
// once per submission, per completed job, per CPU-served wait and per flip. With BC5_DIRECT_JOURNAL_QUIET on (bc5::env_on's
// reading: unset, empty and "0" are off; read once) a whole line of one of these kinds is not written:
//   1 "timing: t <t> s <kind> <n> dwords: sync..."             each submission (submit_now, BC5_DIRECT_TIMING)
//   2 "timing: #<n> done at t ..."                             each completed job (BC5_DIRECT_TIMING)
//   3 "timing: t <t> s after that wait (...)"                  each CPU-served wait (submit_split, BC5_DIRECT_TIMING)
//   4 "timing: t <t> s flip ..., VideoOutSubmitFlip took ..."  each flip (BC5_DIRECT_TIMING; the frame profile line stays)
//   5 "acb rest <a>..<b> of <n> dwords: state prefix of ..."   each acb rest that replays a state prefix (submit)
//   6 "submit #<n> ... OK rc 0 <ms> ms"                        the every-64th submission line, when it went well
// Everything else is written as today: the summaries (timing split, frame profile, job ts, chains, hold tail, the gpu
// group's, the memory line), the timeout probe and the crumbs at a timeout, every catcher's first-occurrence and sampled
// lines, and every line that says FAILED, TIMEOUT, GIVEN UP or the like ("submit #" with FAILED, TIMEOUT or "(retried)"
// stays). Only a whole line is dropped: one that ends with a newline and fits the 1024-byte buffer (longer ones take
// today's path). The dropped lines go to a ring of the last 8192 (192 bytes a line, 1.5 MiB, touched only when on); just
// before the first line of a fence timeout ("submit #... TIMEOUT", "... at the timeout ...", "timeout probe: ",
// "timeout: ", "reopen: ") they are written, oldest first, between two marker lines, so the run-up to a hang that the host
// survives is kept. At most every 10 s, one line counts what was dropped and its bytes. Off: one flag test a line and the
// line takes today's path; the first line journaled prints "[bc5] exp 0401 e7: journal quiet on|off" on stderr.
static double timing_now(); // defined below (the journal's time base)
static bool   jq_prefix(const char* s, size_t n, const char* p) {
	const size_t k = std::strlen(p);
	return n >= k && std::memcmp(s, p, k) == 0;
}
static bool jq_has(const char* s, size_t n, const char* p) { // p within the first n bytes of s
	const size_t k = std::strlen(p);
	for (size_t i = 0; i + k <= n; i++) {
		if (std::memcmp(s + i, p, k) == 0) return true;
	}
	return false;
}
// The kind of a formatted line (n bytes; complete: formatted whole): 1-6 a kind quiet mode drops (the list above), 0 kept,
// -1 kept and the first line of a fence timeout (the dropped lines go out before it).
static int journal_quiet_kind(const char* s, size_t n, bool complete) {
	if (jq_prefix(s, n, "timeout: ") || jq_prefix(s, n, "timeout probe: ") || jq_prefix(s, n, "reopen: ") || jq_has(s, n, "at the timeout") ||
		(jq_prefix(s, n, "submit #") && jq_has(s, n, " TIMEOUT")))
		return -1;
	if (!complete || n == 0 || s[n - 1] != '\n') return 0;
	if (jq_prefix(s, n, "timing: t ")) {
		if (jq_has(s, n, " dwords: sync")) return 1;
		if (jq_has(s, n, " s after that wait")) return 3;
		if (jq_has(s, n, " s flip ") && jq_has(s, n, ", VideoOutSubmitFlip took ")) return 4;
		return 0;
	}
	if (jq_prefix(s, n, "timing: #") && jq_has(s, n, " done at t ")) return 2;
	if (jq_prefix(s, n, "acb rest ") && jq_has(s, n, " dwords: state prefix of ")) return 5;
	if (jq_prefix(s, n, "submit #") && jq_has(s, n, " ... OK rc 0 ") && !jq_has(s, n, "(retried)") && !jq_has(s, n, "FAILED")) return 6;
	return 0;
}
constexpr uint32_t kJqRingLines = 8192;
constexpr uint32_t kJqRingBytes = 192;
struct JournalQuietRing { // the last kJqRingLines dropped lines, each cut to kJqRingBytes - 1 bytes ("...\n" marks a cut)
	char     text[kJqRingLines][kJqRingBytes];
	uint64_t pushed = 0; // lines pushed since the last drain
	void     push(const char* s, size_t n) {
		char* d = text[pushed % kJqRingLines];
		if (n >= kJqRingBytes) {
			std::memcpy(d, s, kJqRingBytes - 5);
			std::memcpy(d + kJqRingBytes - 5, "...\n", 5);
		} else {
			std::memcpy(d, s, n);
			d[n] = 0;
		}
		pushed++;
	}
	template <class F>
	uint32_t drain(F f) { // f(line) for each line held, oldest first; empties the ring; returns how many
		const uint64_t from = pushed > kJqRingLines ? pushed - kJqRingLines : 0;
		for (uint64_t k = from; k < pushed; k++) f(static_cast<const char*>(text[k % kJqRingLines]));
		const uint32_t held = static_cast<uint32_t>(pushed - from);
		pushed              = 0;
		return held;
	}
};
static JournalQuietRing      g_jq_ring;  // BSS: its pages are touched only with the switch on
static std::mutex            g_jq_mutex; // the ring and the count's clock
static std::atomic<uint64_t> g_jq_lines[7], g_jq_bytes {0};
// A formatted line, written as journal() writes one (the same file, the same flushing).
static void journal_quiet_put(const char* s) {
	if (g_journal_min) {
		if (FILE* f = journal_min_file(false); f != nullptr) std::fputs(s, f);
		return;
	}
	char name[512];
	std::snprintf(name, sizeof(name), "%s/direct.log", g_dump_dir.c_str());
	if (FILE* f = std::fopen(name, "a"); f != nullptr) {
		std::fputs(s, f);
		std::fflush(f);
		std::fclose(f);
	}
}
static void journal_quiet_summary(char* out, size_t cap) {
	static const char* const names[7] = {"", "per-submission timing", "per-job timing", "per-wait timing", "per-flip timing", "acb rest", "submit progress"};
	uint64_t                 total    = 0;
	size_t                   w        = 0;
	const auto               add      = [&](int k) {
		if (w < cap) w += static_cast<size_t>(std::max(0, k));
	};
	add(std::snprintf(out, cap, "journal quiet (exp 0401 e7): t %.1f s: not written so far", timing_now()));
	for (int k = 1; k < 7; k++) {
		const uint64_t v = g_jq_lines[k].load();
		total += v;
		if (w < cap) add(std::snprintf(out + w, cap - w, "%s %s %" PRIu64, k == 1 ? ":" : ",", names[k], v));
	}
	if (w < cap) std::snprintf(out + w, cap - w, "; %" PRIu64 " lines, %" PRIu64 " bytes in all\n", total, g_jq_bytes.load());
}
static void journal_quiet_flush() { // the dropped lines held, before a timeout line; the caller holds g_jq_mutex
	if (g_jq_ring.pushed == 0) return;
	char head[200];
	std::snprintf(head, sizeof(head), "journal quiet (exp 0401 e7): the last %" PRIu64 " lines it did not write, oldest first, before the timeout line below:\n",
				  std::min<uint64_t>(g_jq_ring.pushed, kJqRingLines));
	journal_quiet_put(head);
	g_jq_ring.drain([](const char* l) { journal_quiet_put(l); });
	journal_quiet_put("journal quiet (exp 0401 e7): end of the lines it did not write\n");
}
static bool journal_quiet_on() {
	static const bool on = [] {
		const char* e = std::getenv("BC5_DIRECT_JOURNAL_QUIET");
		const bool  v = e != nullptr && e[0] != 0 && !(e[0] == '0' && e[1] == 0); // bc5::env_on's reading (that header comes with the backend)
		std::fprintf(stderr, "[bc5] exp 0401 e7: journal quiet %s\n", v ? "on" : "off");
		if (v)
			journal_quiet_put("exp 0401 e7: journal quiet on, not written: the per-submission, per-job, per-wait and per-flip timing lines, the acb rest "
							  "prefix lines and the every-64th submit lines that went well; the last 8192 of them are written before a fence timeout; "
							  "a count at most every 10 s\n");
		return v;
	}();
	return on;
}
// journal() with the switch on: formats the line; true when it was dropped (and held in the ring) or written here, false
// when journal() writes it as today (longer than the buffer).
static bool journal_quiet_vtake(const char* fmt, va_list ap) __attribute__((format(printf, 1, 0)));
static bool journal_quiet_vtake(const char* fmt, va_list ap) {
	char      line[1024];
	const int n = std::vsnprintf(line, sizeof(line), fmt, ap);
	if (n < 0) return false;
	const bool   complete = static_cast<size_t>(n) < sizeof(line);
	const size_t len      = complete ? static_cast<size_t>(n) : sizeof(line) - 1;
	const int    kind     = journal_quiet_kind(line, len, complete);
	if (kind > 0) {
		g_jq_lines[kind]++;
		g_jq_bytes += len;
		char sum[512] = {};
		{
			std::lock_guard lk(g_jq_mutex);
			g_jq_ring.push(line, len);
			static uint64_t last_ns = 0;
			const uint64_t  now     = SoftCp::now_ns();
			if (last_ns == 0) {
				last_ns = now;
			} else if (now - last_ns >= 10'000'000'000ull) {
				last_ns = now;
				journal_quiet_summary(sum, sizeof(sum));
			}
		}
		if (sum[0] != 0) journal_quiet_put(sum);
		return true;
	}
	if (kind < 0) {
		std::lock_guard lk(g_jq_mutex);
		journal_quiet_flush();
	}
	if (!complete) return false;
	journal_quiet_put(line);
	return true;
}
// The CPU test's seams (cap0401.cpp); always compiled in, never called by the emulator.
extern "C" int bc5_cap0401_quiet_kind(const char* s, uint64_t n, int complete) {
	return journal_quiet_kind(s, static_cast<size_t>(n), complete != 0);
}
// A ring of the test's own: the lines pushed, then drained into out (at most out_cap - 1 bytes, NUL-ended); returns the lines
// drained, *again the lines a second drain gives (0).
extern "C" uint64_t bc5_cap0401_quiet_ring(const char* const* lines, uint64_t n, char* out, uint64_t out_cap, uint64_t* again) {
	auto        ring = std::make_unique<JournalQuietRing>();
	std::string all;
	for (uint64_t k = 0; k < n; k++) ring->push(lines[k], std::strlen(lines[k]));
	const uint32_t held = ring->drain([&all](const char* l) { all += l; });
	*again              = ring->drain([](const char*) {});
	const size_t c      = std::min<size_t>(all.size(), out_cap != 0 ? static_cast<size_t>(out_cap) - 1 : 0);
	std::memcpy(out, all.data(), c);
	if (out_cap != 0) out[c] = 0;
	return held;
}
extern "C" int bc5_cap0401_journal_open(const char* dir) { // the journal's directory, as BC5_GC_DUMP_DIR gives it
	if (!g_dump_dir.empty() || dir == nullptr || dir[0] == 0) return 0;
	g_dump_dir = dir;
	return 1;
}
extern "C" void bc5_cap0401_journal(const char* text) { // one call of the real journal()
	journal("%s", text);
}
extern "C" void bc5_cap0401_journal_flush() {
	if (g_journal_min && !g_dump_dir.empty()) (void)journal_min_file(true);
}
extern "C" int bc5_cap0401_journal_min() {
	return g_journal_min ? 1 : 0;
}
extern "C" int bc5_cap0401_journal_quiet() { // -1 before bc5_cap0401_journal_open (the state line needs the directory)
	return g_dump_dir.empty() ? -1 : journal_quiet_on() ? 1 : 0;
}
extern "C" uint64_t bc5_cap0401_quiet_count(int kind) { // 1-6: the lines of that kind dropped; 0: the bytes dropped
	return kind >= 1 && kind <= 6 ? g_jq_lines[kind].load() : kind == 0 ? g_jq_bytes.load() : 0;
}
extern "C" void bc5_cap0401_quiet_summary(char* out, uint64_t cap) {
	journal_quiet_summary(out, static_cast<size_t>(cap));
}
// ---- end of exp 0401 series e7's (tag cap) journal block ----------------------------------------------------------------
static void journal(const char* fmt, ...) {
	if (g_dump_dir.empty() || !::Log::Bc5LoggingOn()) { // BC5: the session's logging switch
		return;
	}
	if (journal_quiet_on()) { // exp 0401 series e7 (tag cap): BC5_DIRECT_JOURNAL_QUIET; off, the line takes today's path below
		va_list ap;
		va_start(ap, fmt);
		const bool taken = journal_quiet_vtake(fmt, ap);
		va_end(ap);
		if (taken) return;
	}
	if (g_journal_min) {
		if (FILE* f = journal_min_file(false); f != nullptr) {
			va_list ap;
			va_start(ap, fmt);
			std::vfprintf(f, fmt, ap);
			va_end(ap);
		}
		return;
	}
	char name[512];
	std::snprintf(name, sizeof(name), "%s/direct.log", g_dump_dir.c_str());
	FILE* f = std::fopen(name, "a");
	if (f == nullptr) {
		return;
	}
	va_list ap;
	va_start(ap, fmt);
	std::vfprintf(f, fmt, ap);
	va_end(ap);
	std::fflush(f);
	std::fclose(f);
}

// Seconds since the first call: the time base of the BC5_DIRECT_TIMING journal lines.
static void fs415_flip(uint64_t called_ns); // experiment 0415 (fs415): defined after the completion code
static double timing_now() {
	static const uint64_t t_first = [] {
		const uint64_t t = SoftCp::now_ns();
		std::fprintf(stderr, "bc5 clock: journal t 0 = monotonic %.3f s\n", static_cast<double>(t) / 1e9);
		return t;
	}();
	return static_cast<double>(SoftCp::now_ns() - t_first) / 1e9;
}

#if defined(KYTY_BC5_DIRECT)
static std::unique_ptr<bc5::direct::Device> g_dev;
// BC5 experiment 0412 (tag mr412, DESIGN-learned-windows.md, README sections 51-53): the learned windows replaced by a
// rule. Three switches, each off when unset or 0 (one test of a constant where it is asked):
//   BC5_GUARD_MAP_RULE=1|2   R1: every 2 MiB chunk under a view of direct memory is imported when the view exists, with
//                            no name list and no "has data" test (1: the direct-memory file; 2: the private file too).
//   BC5_GUARD_PRT_BG=1       R2: one PRT mapping (reads 0, writes dropped, no memory) under the guest's address span
//                            [kBgLo, kBgHi) at device open; real mappings replace it. It acts ONLY with MAP_RULE on:
//                            with the "by data" import a PRT page under an unimported view would turn a loud miss
//                            (a GPU fault) into a silent one (the top session's point 3). scratch_fill does nothing
//                            inside the span then.
//   BC5_GUARD_LEARN_LOG=1|2  the catcher: a GPU fault that would be learned is journaled with what lay at its address
//                            (classify below), and nothing is written to the learned file or the alias file.
//                            1: the window still joins this run's list in memory, so the same place does not fault
//                            again in this run; 2: nothing is added at all.
// The span: 4 GiB (above libdrm's 32-bit range, where the device keeps its argument slot) to the end of the title's
// AMM window (0x9000000000); the device's own addresses are at 16 TiB and its code page at 0xFE00000000
// (backend/include/bc5/direct.hpp kCodeVa, backend/src/direct.cpp kScratchVa), outside it.
// This text is included by the main unit and by the CPU test maprule0412.cpp.
namespace mr412 {
static constexpr uint64_t kBgLo = 0x100000000ull, kBgHi = 0x9000000000ull;
inline int env_digit(const char* name, int max) {
	const char* e = std::getenv(name);
	if (e == nullptr || e[0] < '0' || e[0] > '9' || e[1] != 0) return 0;
	const int v = e[0] - '0';
	return v > max ? 0 : v;
}
inline int rule() {
	return 0; /* exp 0419 (candidate G): BC5_GUARD_MAP_RULE is gone; K1r replaced it */
}
inline bool rule_for(int kind) { return rule() == 2 || (rule() == 1 && kind == 0); } // kind: 0 direct memory, 1 private memory
inline bool prt_bg() {
	return false; /* exp 0419 (candidate G): BC5_GUARD_PRT_BG is gone */
}
inline int learn_log() {
	static const int v = env_digit("BC5_GUARD_LEARN_LOG", 2);
	return v;
}
// Is [lo, hi) wholly inside the background span? (scratch_fill's question; a piece that straddles an end is left to it.)
inline bool in_bg(uint64_t lo, uint64_t hi) { return lo >= kBgLo && hi <= kBgHi && lo < hi; }
// The chunks of the file a view [off, off + size) touches, as the eager loop walks them.
inline void view_chunks(uint64_t off, uint64_t size, uint64_t chunk, std::vector<uint64_t>& out) {
	if (size == 0) return;
	for (uint64_t c = off & ~(chunk - 1); c < off + size; c += chunk) out.push_back(c);
}
// What lay at a faulting address, for the catcher's line. The order is the order of the questions that matter:
// was it a guest address at all, did the guest have a range there, did we hold its memory, had the GPU a mapping.
inline const char* classify(bool junk_bits, bool guest_range, bool under_view, bool view_lazy, bool view_eager, bool chunk_imported, bool gpu_mapped) {
	if (junk_bits) return "K4 junk address (a bit above 40 set)";
	if (!guest_range && !under_view) return "K3 no guest range (a hole)";
	if (under_view && !chunk_imported) return view_lazy ? "K1 under a LAZY view, chunk not imported" : (view_eager ? "K1 under an EAGER view, chunk not imported (import failed or late)" : "K1 under a BY-DATA view, chunk never written by the CPU");
	if (under_view && !gpu_mapped) return "K5 imported but not GPU-mapped at the fault (timing or a dropped mapping)";
	if (under_view) return "K6 imported and GPU-mapped (a protection fault or a stale report)";
	return gpu_mapped ? "K6 guest range outside direct memory, GPU-mapped" : "K2 guest range outside direct memory (anonymous), not GPU-mapped";
}
} // namespace mr412
static bool g_mr412_bg = false; // exp 0412 (tag mr412): the PRT background span is mapped on the open device
// Experiment 0412 (tag mr412): the PRT mappings a freshly opened device gets. With BC5_GUARD_PRT_BG (and MAP_RULE) the
// whole guest span; otherwise, or when the kernel refuses the span, the AMM window alone as before (BC5_DIRECT_AMM_PRT).
static void mr412_prt_open() {
	g_mr412_bg = false;
	if (!g_dev) return;
	if (mr412::prt_bg()) {
		const uint64_t t0 = SoftCp::now_ns();
		g_mr412_bg        = g_dev->map_prt_window(mr412::kBgLo, mr412::kBgHi - mr412::kBgLo);
		journal("map rule (exp 0412, tag mr412): PRT background 0x%" PRIx64 "-0x%" PRIx64 ": %s, %.1f ms\n", mr412::kBgLo, mr412::kBgHi, g_mr412_bg ? "mapped" : "REFUSED (the AMM window alone, as before)",
		        static_cast<double>(SoftCp::now_ns() - t0) / 1e6);
		if (g_mr412_bg) return; // the AMM window lies inside the span
	}
	const bool amm_prt = bc5::env_on(std::getenv("BC5_DIRECT_AMM_PRT")); // exp 0419: "=0" is off; // experiment 0102
	if (amm_prt) g_dev->map_prt_window(0x8000000000ull, 0x1000000000ull);
}
static std::mutex                           g_dev_mutex;
// Experiment 0024: jobs are queued and completed by a thread of their own
// (needs BC5_DIRECT_JOURNAL=min: the crash journal writes one line in two halves around a job).
// Run 119: the doorbell consumer's jobs are not waited for inline either.
// Waiting made its pass over the queues as slow as the GPU (a compute head queued behind a
// frame's buffers), and a compute tail served late met its slot label cleared by the main buffer
// two frames on (the water in the second level: 4 s a frame).
static const bool g_async = g_journal_min;
// Experiment 0415 (ls415): an import with its count, bytes and time.
// Experiment 0415 (fs415d): what this thread spent, since submit_now last cleared it, in the parts of direct_sync_one
// (0 views, 1 scan with its imports, 2 merges and the lazy release, 3 the drain, 4 the mappings, 5 the imports alone,
// which lie inside 1 and 2), 6 in sync_mappings' read of /proc/self/maps; 7 flags of sync_mappings: 1 it walked,
// 2 the call was urgent, 4 the walk was left out (KYTY_BC5_ANON_SYNC=thread). Nanoseconds; for the frame counter's line.
static thread_local uint64_t t_fs415_ds[8] = {};

static uint32_t ls415_import(int fd, uint64_t off, uint64_t size) {
	bc5::load_stat::Scope ls_scope(bc5::load_stat::kImport);
	ls_scope.items = size;
	const uint64_t t0 = SoftCp::now_ns();
	const uint32_t id = g_dev->import_memfd(fd, off, size);
	t_fs415_ds[5] += SoftCp::now_ns() - t0;
	return id;
}
static std::shared_mutex g_finish_mutex; // shared: waiting for a job on g_dev; exclusive: replacing g_dev
// With jobs in flight a mapping must not go away or change under a job that may be using it
// (the kernel clears the page-table entries at once, whatever is still running): waits until
// everything queued so far has run. Defined with the completion queue.
static void wait_jobs();
static void chain_flush(int why); // exp 0432 (tag d432)
// exp 0432: the test build's three host switches (each on unless "0") and its counters.
namespace d432 {
#ifdef BC5_LEAN
struct Cnt { // the lean build: a counter that is nothing
	constexpr Cnt() = default;
	explicit constexpr Cnt(int) {}
	void     operator++(int) const {}
	void     operator+=(uint64_t) const {}
	void     operator=(uint64_t) const {}
	uint64_t load() const { return 0; }
};
#else
using Cnt = std::atomic<uint64_t>;
#endif
inline bool word_on(const char* name) {
	const char* e = std::getenv(name);
	return !(e != nullptr && e[0] == '0' && e[1] == 0);
}
inline bool on() { // item D: BC5_DIRECT_UNMAP_NOWAIT (the kernel orders the page-table clear behind this VM's submissions: amdgpu_vm_clear_freed, v7.3)
	static const bool v = BC5_LEAN_OR(true, word_on("BC5_DIRECT_UNMAP_NOWAIT"));
	return v;
}
inline bool anon_events() { // item A: OFF unless the word is "1" (the T runs of 2026-11-17: its counter moved 15 times a second in the maintainer's scene, and each move is a walk)
	static const bool v = BC5_LEAN_OR(false, ([] {
		const char* e = std::getenv("BC5_DIRECT_ANON_EVENTS");
		return e != nullptr && e[0] == '1' && e[1] == 0;
	}()));
	return v;
}
inline bool anon_thread() { // item W
	static const bool v = BC5_LEAN_OR(true, word_on("BC5_DIRECT_ANON_THREAD"));
	return v;
}
inline bool refused_ends() { // item R
	static const bool v = BC5_LEAN_OR(true, word_on("BC5_DIRECT_REFUSED_ENDS"));
	return v;
}
inline bool views_kept() { // item V: OFF unless the word is "1" (builds 1 and 3: the view list cost 4,152 and 4,182 ms of the sample with it, 2,414 without)
	static const bool v = BC5_LEAN_OR(false, ([] {
		const char* e = std::getenv("BC5_DIRECT_VIEWS_KEPT");
		return e != nullptr && e[0] == '1' && e[1] == 0;
	}()));
	return v;
}
inline bool maps_fast() { // item M
	static const bool v = BC5_LEAN_OR(true, word_on("BC5_DIRECT_MAPS_FAST"));
	return v;
}
inline Cnt g_maps_fast {0}, g_maps_sorted {0};
inline int maps_diff() { // item X: 0 off, 1 on, 2 on and checked against the old rebuild; OFF unless the word is "1" or "verify"
	static const int v = BC5_LEAN_OR(0, ([] {
		const char* e = std::getenv("BC5_DIRECT_MAPS_DIFF");
		if (e == nullptr) return 0;
		if (std::strcmp(e, "verify") == 0) return 2;
		return e[0] == '1' && e[1] == 0 ? 1 : 0;
	}()));
	return v;
}
inline Cnt g_x_diff {0}, g_x_full {0}, g_x_views {0}, g_x_mismatch {0};
inline Cnt g_x_why[11]; // which condition sent a rebuild the old way (the first that failed)
inline Cnt g_rebuilds {0}, g_busy {0}, g_unmaps_busy {0}, g_bos_busy {0}, g_unmaps {0}, g_drains {0}, g_drain_ns {0}, g_drain_max_ns {0},
    g_prep_max_ns {0}, g_prep_over20 {0}, g_last_ns {0}, g_anon_walks {0}, g_anon_skips {0}, g_anon_ev {0}, g_anon_ev_miss {0}, g_anon_vmas {0}, g_views_clone {0},
    g_rec_mismatch {0}, g_sync_ns {0};
#ifdef BC5_LEAN
inline void maxed(const Cnt&, uint64_t) {}
#else
inline void maxed(std::atomic<uint64_t>& m, uint64_t v) {
	uint64_t was = m.load(std::memory_order_relaxed);
	while (v > was && !m.compare_exchange_weak(was, v, std::memory_order_relaxed)) {
	}
}
#endif
} // namespace d432
static Stage                                g_stage = Stage::Off;
static constexpr uint32_t                   g_cu_mask = 0xffffffffu;
static constexpr const char*                kRenderNode = "/dev/dri/renderD128";
static std::atomic<uint64_t>                g_submits {0};
static std::atomic<uint64_t>                g_ok {0};
static std::atomic<uint64_t>                g_bytes_mapped {0};
static std::atomic<uint64_t>                g_swapped_pages {0};
static uint64_t                             g_last_sync_ns = 0;

// Experiment 0107: every /dev/gc ioctl calls init_once(); taking g_dev_mutex there made the title's
// render thread wait for the ring thread's submissions even for ioctls that never touch the device
// (5 of 19 render-thread stack samples in run 397). Once initialisation has finished, return
// without the lock.
static void              init_once_locked();
static std::atomic<bool> g_init_finished {false};
static void init_once() {
	if (g_init_finished.load(std::memory_order_acquire)) return;
	init_once_locked();
	g_init_finished.store(true, std::memory_order_release);
}

static void init_once_locked() {
	std::lock_guard lock(g_dev_mutex);
	static bool done = false;
	if (done) {
		return;
	}
	done = true;
	const char* mode = std::getenv("BC5_GC_MODE");
	if (mode == nullptr || std::strcmp(mode, "direct") != 0) {
		return;
	}
	g_stage = Stage::All;
	bc5::direct::OpenOptions oo;
	oo.gds_kib    = 64;
	oo.oa_count   = 16;
	oo.gws_count  = 64;
	oo.gds_shadow = true;
	g_dev = bc5::direct::Device::open(kRenderNode, oo);
	if (!g_dev) {
		LOGF_COLOR(Log::Color::Red, "[bc5-direct] device open failed; staying on the soft CP\n");
		g_stage = Stage::Off;
		return;
	}
	// The console CP's context-state stack (CLEAR_STATE cmd 1 / cmd 2 around the driver's
	// internal draws; bc5/state_stack.hpp) is emulated. Without it the game loses its context
	// registers after every internal clear (run 73: its triangle strips then lose their first
	// vertex to a primitive-restart index of 0; run 75: with it they draw).
	g_dev->set_state_stack(true);
	// Experiment 0102 (prepared, not yet run; GPU, only with the maintainer present):
	// BC5_DIRECT_AMM_PRT=1 maps the title's AMM window (0x8000000000, 64 GiB, as the guest log's
	// "AMM" reservation shows) as PRT pages before anything is imported there: pages the title leaves
	// unbacked read as 0 and drop writes, as its sparse UI layer expects (F161).
	mr412_prt_open(); // exp 0412 (tag mr412): the AMM window's PRT mapping, or the whole span with BC5_GUARD_PRT_BG
	// Submissions without draws and dispatches list only the BOs their packets name
	// (Device::set_short_lists; run 81: 0.05 ms instead of 27 ms in the CS ioctl for half of a
	// frame's submissions).
	g_dev->set_short_lists(true);
	// Every IB ends by waiting for CP DMA to be idle (Device::set_dma_idle; experiment 0017).
	g_dev->set_dma_idle(true);
	g_dev->set_async(g_async);
	if (g_async) journal("direct: jobs are not waited for at submission\n");
	dump_init();
	journal("direct: enabled, stage all, cu mask 0x%08x, bo list with mappings\n", g_cu_mask);
	LOGF_COLOR(Log::Color::Green, "[bc5-direct] enabled: stage all, cu mask 0x%08x\n", g_cu_mask);
	// BC5_DIRECT_SELFTEST=1: before the game submits anything, run synthetic IBs through the very
	// same path (no userptr BOs yet): 8 NOPs, 152 NOPs, 8 x (CONTEXT_CONTROL + NOPs) — the shapes
	// that hung the box from inside this process but not standalone (experiment 0016).
	if (BC5_DIAG_ENV("BC5_DIRECT_SELFTEST") != nullptr) {
		std::vector<uint32_t> ib;
		bc5::policy::FilterOptions opt;
		auto run = [&](const char* name) {
			journal("selftest %s (%zu dwords) ... ", name, ib.size());
			const auto r = g_dev->submit(ib, opt, 2'000'000'000ull);
			journal("%s rc %d%s %.2f ms\n", r.ok ? "OK" : "FAILED", r.rc, r.timed_out ? " TIMEOUT" : "", r.submit_ms);
			return r.ok;
		};
		ib.assign(8, 0xffff1000u);
		if (!run("8 nops")) return;
		ib.assign(152, 0xffff1000u);
		if (!run("152 nops")) return;
		ib.assign(152, 0xffff1000u);
		ib[7] = 0xc0012800u; ib[8] = 0x80000000u; ib[9] = 0x80000000u;
		ib[138] = 0xc0012800u; ib[139] = 0x80000000u; ib[140] = 0x80000000u;
		for (int i = 0; i < 8; i++) {
			if (!run("cc-at-8-and-139")) return;
		}
		journal("selftest: all passed\n");
	}
}

// Keeps the 1:1 userptr mappings in step with the guest's anonymous rw memory. Guest windows:
// KytyPlus keeps guest memory in [0x40000, 0xfbffffffff]; the emulator's own heap and libraries
// live above. Two passes over /proc/self/maps:
//   1. revalidation: a mapping whose pages are no longer inside one rw anonymous VMA (the guest
//      unmapped or re-protected the range — KernelMunmap, a released stack, a placeholder) is
//      unmapped, otherwise the next amdgpu_cs_submit fails for every BO with -EFAULT
//      (amdgpu_ttm_tt_get_user_pages → hmm_range_fault; experiment 0016, run b1: 30 OK then 42
//      EFAULT after a 4-mapping batch);
//   2. addition: every resident run (mincore(), 64 KiB grain) not mapped yet becomes a userptr
//      BO. mincore() keeps untouched reservations out (userptr would otherwise materialise them).
// `force` skips the 50 ms throttle (used after an EFAULT).
struct Vma {
	uint64_t start, end;
	bool     readonly; // r-- or r-x: mapped for GPU read/execute only (shader code, rodata)
};
static std::vector<Vma> g_vmas; // rw anonymous guest VMAs of the last sync

// ---- ADR 0006: the guest's direct memory as imported dma-bufs ---------------------------------
// KytyPlus keeps its upstream direct-memory
// backing, one memfd with MAP_SHARED views at the guest's addresses, sealed against shrinking.
// The host hands ranges of that memfd to the GPU as udmabufs imported into amdgpu
// (Device::import_memfd) and maps them at the views' addresses: the same pages on both sides,
// aliases included, and no userptr BO whose pages the kernel walks on every submission (F38).
// What gets imported: every 2 MiB chunk of the file that holds data inside a view (SEEK_DATA),
// plus what the render-target hints and the learned fault regions ask for; adjacent chunks go
// into one BO of at most 32 MiB. An imported chunk is pinned in full, so guest writes into it
// later need no further work. The anonymous rest of the guest (stacks, module data, the host's
// own areas) stays on the userptr path above, which no longer sees the direct views.
constexpr uint64_t kDChunk = 2ull << 20u;
// The largest import: what one udmabuf may hold (the module's size_limit_mb, 64 by default).
static const uint64_t kDMaxBo = [] {
	unsigned long mb = 32;
	if (FILE* f = std::fopen("/sys/module/udmabuf/parameters/size_limit_mb", "r")) {
		if (std::fscanf(f, "%lu", &mb) != 1) mb = 32;
		std::fclose(f);
	}
	if (mb < 2) mb = 2;
	if (mb > 1024) mb = 1024;
	return (static_cast<uint64_t>(mb) << 20u) & ~((2ull << 20u) - 1);
}();
struct DView {
	uint64_t    va, size, off;
	std::string name;
	bool        lazy;
	bool        eager;
};
struct DBo { uint64_t off, size; uint32_t id; uint64_t t_ns; };
struct DMap {
	uint64_t va, size, bo_off;
	uint32_t id;
	bool operator==(const DMap& o) const { return va == o.va && size == o.size && bo_off == o.bo_off && id == o.id; }
};
// Two files are handed to the GPU this way (experiment 0023): the direct-memory pool, whose
// views carry a file offset, and the file behind KytyPlus's private guest memory (module images,
// stacks, runtime areas), where the offset is the guest address itself.
struct DState {
	int                kind;  // 0: direct memory, 1: private memory
	const char*        label; // journal prefix
	std::vector<DBo>   bos;   // disjoint chunk-aligned file ranges, sorted by offset
	std::vector<DMap>  maps;  // sorted by va
	std::set<uint64_t> forced; // chunk offsets the hints and learned regions asked for
	std::set<uint64_t> failed; // chunks whose import failed (not retried)
	std::set<uint64_t> merge_failed; // run starts whose merged import failed (not retried)
	uint64_t           views_sig = 0, bos_mapped = 0, bytes = 0, sync_ns = 0, file_size = 0, merge_ns = 0;
	uint64_t           ranges_gen = 0; // experiment 0037: Bc5MappedRangesGeneration at the last sync
	uint64_t           blocks = ~0ull, forced_seen = ~0ull, reported = 0;
};
static DState g_d[2] = {{0, "direct", {}, {}, {}, {}, {}}, {1, "private", {}, {}, {}, {}, {}}};
static int dstate_fd(const DState& S) {
	return S.kind == 0 ? Libs::LibKernel::Memory::Bc5DirectMemoryFd() : Libs::LibKernel::Memory::Bc5PrivateMemoryFd();
}
// Experiment 0022, step 3: what the learned regions and the direct mapper work on changes rarely.
// g_layout_gen counts the changes (views of direct memory, anonymous VMAs, learned list, device
// reopen); S.blocks is the memfd's allocated size at the last full scan (st_blocks grows with
// every page the game first writes), so an unchanged file needs no SEEK_DATA walk.
static uint64_t g_layout_gen = 1;
static uint64_t g_dprof_views_ns = 0, g_dprof_full = 0, g_dprof_fast = 0; // direct_sync profile (timing split line)
// Experiment 0169: where a full direct sync goes - the chunk scan and imports, the merge pass, the
// GPU drain before the mappings change, the mapping rebuild - and how many full syncs drained.
static uint64_t g_dprof_scan_ns = 0, g_dprof_merge_ns = 0, g_dprof_drain_ns = 0, g_dprof_maps_ns = 0, g_dprof_drains = 0;
static uint64_t g_dprof_want_ns = 0, g_dprof_drop_ns = 0, g_dprof_scratch_ns = 0, g_dprof_add_ns = 0; // the mapping rebuild's parts

// BC5_DIRECT_LAZY_NAMES=name[,name...]: views of direct memory with these names (the game names
// its mappings; "orbis_user_malloc" is its CPU heap) are not imported for holding data, only where
// a hint or a learned fault region asks. Everything a draw's BO list names has to sit in the
// driver's GTT domain at once, and that domain is half of the machine's RAM by default (run 96:
// -ENOMEM at 6.8 GiB imported, experiment 0020); memory the GPU never reads should not count.
static bool direct_lazy_name(const char* name) {
	static const std::vector<std::string> names = [] {
		std::vector<std::string> v;
		if (const char* e = std::getenv("BC5_DIRECT_LAZY_NAMES"); e != nullptr) {
			std::string cur;
			for (const char* c = e;; c++) {
				if (*c == ',' || *c == 0) {
					if (!cur.empty()) v.push_back(cur);
					cur.clear();
					if (*c == 0) break;
				} else {
					cur.push_back(*c);
				}
			}
		}
		// exp 0419 (build V) for exp 0412: "FileSystem" is never lazy (fault record 20261114-184017: a shader read two
		// of its written pages, which a lazy heap does not import). BC5_DIAG_LAZY_FILESYSTEM=1 keeps the old list.
		if (!bc5::env_on(BC5_DIAG_ENV("BC5_DIAG_LAZY_FILESYSTEM"))) {
			const auto it = std::find(v.begin(), v.end(), std::string("FileSystem"));
			if (it != v.end()) {
				v.erase(it);
				std::fprintf(stderr, "[bc5] exp 0419: FileSystem taken out of BC5_DIRECT_LAZY_NAMES (fault record 20261114-184017); "
				                     "BC5_DIAG_LAZY_FILESYSTEM=1 keeps the old list\n");
			}
		}
		return v;
	}();
	static const bool by_data = [] { // exp 0412 (tag kl412): BC5_GUARD_LAZY_BY_DATA=1, no view is lazy
		const char* e = BC5_DIAG_ENV("BC5_GUARD_LAZY_BY_DATA");
		const bool  v = e != nullptr && e[0] != 0 && !(e[0] == '0' && e[1] == 0);
		if (v) std::fprintf(stderr, "[bc5] exp 0412 (tag kl412): BC5_GUARD_LAZY_BY_DATA on: BC5_DIRECT_LAZY_NAMES is ignored, every view of direct memory is imported where it holds data\n");
		return v;
	}();
	if (by_data) return false;
	if (name == nullptr || names.empty()) return false;
	return std::find(names.begin(), names.end(), name) != names.end();
}

// Experiment 0412 (tag bd412): bd0412.inc, BC5_GUARD_BYDATA_NAMES, option B's rule per heap.
namespace bd412 {
inline std::vector<std::string> parse(const char* e) {
	std::vector<std::string> v;
	if (e == nullptr) return v;
	std::string cur;
	for (const char* c = e;; c++) {
		if (*c == ',' || *c == 0) {
			if (!cur.empty() && std::find(v.begin(), v.end(), cur) == v.end()) v.push_back(cur);
			cur.clear();
			if (*c == 0) break;
		} else {
			cur.push_back(*c);
		}
	}
	return v;
}
inline bool has(const std::vector<std::string>& names, const char* name) {
	return name != nullptr && std::find(names.begin(), names.end(), name) != names.end();
}
} // namespace bd412
static const std::vector<std::string>& bd412_names() {
	static const std::vector<std::string> v = [] {
		auto n = bd412::parse(BC5_DIAG_ENV("BC5_GUARD_BYDATA_NAMES"));
		for (const auto& s: n) std::fprintf(stderr, "[bc5] exp 0412 (tag bd412): BC5_GUARD_BYDATA_NAMES: the heap \"%s\" is imported by data, not whole\n", s.c_str());
		return n;
	}();
	return v;
}
static bool bd412_name(const char* name) {
	const auto& n = bd412_names();
	return !n.empty() && bd412::has(n, name);
}
// BC5_DIRECT_EAGER_NAMES=name[,name...]: views with these names are imported in full as soon as
// they exist, data or not. The game's GPU heaps hold render targets and GPU-written textures no
// CPU ever touches; the first draw into one faulted, and a fault is a 14 s freeze (2 s fence
// timeout, 12 s for the kernel's reset; run 103: opening the pause menu). 17 of the 18 regions learned
// from faults so far lie in those two heaps.
static bool direct_eager_name(const char* name) {
	static const std::vector<std::string> names = [] {
		std::vector<std::string> v;
		if (const char* e = std::getenv("BC5_DIRECT_EAGER_NAMES"); e != nullptr) {
			std::string cur;
			for (const char* c = e;; c++) {
				if (*c == ',' || *c == 0) {
					if (!cur.empty()) v.push_back(cur);
					cur.clear();
					if (*c == 0) break;
				} else {
					cur.push_back(*c);
				}
			}
		}
		// Exp 0421 (tag fs421e): the title's heap "FileSystem" is always eager: imported whole when its view appears, as
		// the heaps of BC5_DIRECT_EAGER_NAMES are. The title keeps GPU-written buffers there (F443, F468, F472) and the
		// GPU read its CPU-written chunks (fault record 20261114-184017); on the console every page of it is the GPU's
		// from the map call. One import of the view instead of one per freshly written 2 MiB chunk during the loads.
		if (std::find(v.begin(), v.end(), std::string("FileSystem")) == v.end()) v.push_back("FileSystem");
#ifndef BC5_LEAN
		std::fprintf(stderr, "[bc5] exp 0421 (tag fs421e): \"FileSystem\" is eager (imported whole when its view appears)\n");
#endif
		return v;
	}();
	if (bd412_name(name)) return false; // exp 0412 (tag bd412): this heap is imported by data
	if (name == nullptr || names.empty()) return false;
	return std::find(names.begin(), names.end(), name) != names.end();
}

// Experiment 0415 (ls415d), KYTY_BC5_NAMES_FAST (default off; "verify" asks the old function too): the lazy and eager
// class of a range's name remembered per name. Both lists are read once from the environment, so a name's class never
// changes. Used only from direct_views_build, which runs under direct_views' mutex. If this were wrong, a heap would
// be imported eagerly or lazily against its list: memory pinned that should not be, or a GPU fault on a heap that
// should have been imported whole.
static bool ls415_name_class(const char* name, bool eager) { // exp 0419 phase 2: KYTY_BC5_NAMES_FAST is gone
	return eager ? direct_eager_name(name) : direct_lazy_name(name);
}

static std::vector<DView> direct_views_build(const DState& S) {
	std::vector<DView> v;
	if (S.kind == 0) {
		Libs::LibKernel::Memory::Bc5ForEachMappedRange(nullptr, &v, [](uint64_t start, uint64_t size, uint64_t offset, int type, int, const char* name, void* p) {
			if (type == 0 && size != 0) static_cast<std::vector<DView>*>(p)->push_back({start, size, offset, name != nullptr ? name : "", ls415_name_class(name, false), ls415_name_class(name, true)});
		});
	} else {
		// Private regions: the file offset is the address. Thread stacks (type 3) are lazy:
		// a hundred MiB nothing on the GPU has asked for so far; a fault
		// in one would be learned like any other.
		Libs::LibKernel::Memory::Bc5ForEachPrivateRegion(&v, [](uint64_t start, uint64_t size, int type, const char* name, void* p) {
			if (size == 0) return;
			std::string n = name != nullptr && *name != 0 ? name : "(unnamed)";
			if (type == 3) n = "(thread stacks)";
			static_cast<std::vector<DView>*>(p)->push_back({start, size, start, n, ls415_name_class(name, false) || type == 3, ls415_name_class(name, true)});
		});
	}
	return v;
}

// Experiment 0037: the views of direct memory are built once per change of the guest's ranges
// (Bc5MappedRangesGeneration) instead of on every sync: a title with 11,500 views spent 34 ms of
// every frame building them. Shared, so a caller keeps its snapshot while another rebuilds; sorted
// by address, with their signature.
struct DViews {
	std::vector<DView> v;
	uint64_t           sig = 0;
	bool               sorted = true;
};
static std::atomic<uint64_t> g_views_builds {0}; // experiment 0156: rebuilds of the views
// Experiment 0437 (tag vg437), BC5_DIRECT_VIEWS_GEN (on in this test build unless "0"): the direct-memory view list
// (direct_views, kind 0) and direct_sync_one's 50 ms gate follow Bc5DirectRangesGeneration, which moves only when a
// direct range's start, size, offset or name changes, instead of Bc5MappedRangesGeneration, which moves with every
// edit of any guest range. Exp 0430's 57-minute play (play-f18) rebuilt the list 86,004 times in 3,035 s of play
// (28 a second, 12,500-30,000 ranges each, under the device mutex) for 128 s of "views"; at t 555 s the layout had
// changed 8,950 times in about 23,400 builds. The private-region list (kind 1) keeps the old generation. Off, nothing
// changes.
static bool vg437_on() {
	static const bool v = [] {
		const char* e  = std::getenv("BC5_DIRECT_VIEWS_GEN"); // the test build: on unless "0" (the candidate's arm is the binary)
		const bool  on = e == nullptr || e[0] == 0 || bc5::env_on(e);
		std::fprintf(stderr, "[bc5] exp 0437 (tag vg437): BC5_DIRECT_VIEWS_GEN %s: the direct view list follows %s\n", on ? "ON" : "off",
		             on ? "the direct ranges' generation" : "every edit of the guest's ranges");
		return on;
	}();
	return v;
}
static uint64_t vg437_gen() {
	return vg437_on() ? Libs::LibKernel::Memory::Bc5DirectRangesGeneration() : Libs::LibKernel::Memory::Bc5MappedRangesGeneration();
}
// Experiment 0415 (tag mr415), stage S1 of experiments/0415-load-times-fps/DESIGN-lock-side.md, KYTY_BC5_MAP_RECORDS
// (default off; any value but 0 is "verify", the only mode yet): a list of the direct-memory views is kept up to date
// from the range table's change records and compared, at every rebuild of the views, with the list built from the
// same snapshot's every range. Nothing uses the kept list: this only proves (or refutes) that the records are
// complete and in order, before any later stage relies on them. Called under direct_views' mutex.
// Tag mr415b (the top session's review, 2026-11-12): with KYTY_BC5_MAP_RECORDS on, every 5 s on a thread of its own and
// under no lock of the direct path, the readable VMAs of /proc/self/maps inside the guest's address span are held
// against the range table: bytes of such a VMA that no range of the table covers are counted (maps_check,
// maps_uncovered) and the first ten spans journaled. A mapper that changes the guest's address space without telling
// the table shows up here as a stable non-zero count; a map call caught half-way shows as a count that comes and goes
// (the two readings are not taken at one instant). Counts only: nothing acts on it.
static void mr415_maps_check_thread() {
	pthread_setname_np(pthread_self(), "bc5-mapschk");
	constexpr uint64_t kGuestMin = 0x40000ull, kGuestMax = 0xfbffffffffull; // sync_mappings' span
	int                logged    = 0;
	for (;;) {
		std::this_thread::sleep_for(std::chrono::seconds(5));
		uint64_t                                   uncovered = 0, spans = 0;
		std::vector<std::pair<uint64_t, uint64_t>> guest;
		std::ifstream                              maps("/proc/self/maps");
		std::string                                line;
		while (std::getline(maps, line)) {
			uint64_t start = 0, end = 0;
			char     perms[8] = {};
			if (std::sscanf(line.c_str(), "%" SCNx64 "-%" SCNx64 " %7s", &start, &end, perms) < 3) continue;
			if (perms[0] != 'r' || start < kGuestMin || end > kGuestMax + 1 || end <= start) continue;
			Libs::LibKernel::Memory::Bc5GuestRangesIn(start, end, &guest);
			uint64_t cur = start;
			auto     gap = [&](uint64_t a, uint64_t b) {
				uncovered += b - a;
				spans++;
				if (logged < 10) {
					logged++;
					journal("maps check (exp 0415, mr415b): 0x%" PRIx64 "-0x%" PRIx64 " (%s) is readable in /proc/self/maps and in no range of the table\n", a, b, perms);
				}
			};
			for (const auto& [a, b]: guest) {
				if (a > cur) gap(cur, a < end ? a : end);
				if (b > cur) cur = b;
				if (cur >= end) break;
			}
			if (cur < end) gap(cur, end);
		}
		bc5::load_stat::count(bc5::load_stat::kMapsCheck, uncovered);
		if (spans != 0) bc5::load_stat::count(bc5::load_stat::kMapsUncovered, spans);
	}
}

// The modes of KYTY_BC5_MAP_RECORDS: 0 off (unset, empty, "0"); 2 "views" (stage S2, tag mr415c: the kept list is used);
// 1 anything else ("verify": stage S1, the kept list is only compared).
static int mr415_mode() {
	static const int mode = [] {
		if (d432::views_kept()) return 2; // exp 0432 (tag v432): BC5_DIRECT_VIEWS_KEPT
		const char* e = BC5_DIAG_ENV("KYTY_BC5_MAP_RECORDS");
		if (!bc5::load_stat::env_set(e)) return 0;
		return std::strcmp(e, "views") == 0 ? 2 : 1;
	}();
	return mode;
}

static void mr415_verify() {
	static const int mode = mr415_mode();
	if (mode != 1) return;
	static std::once_flag maps_check_once;
	std::call_once(maps_check_once, [] { std::thread(mr415_maps_check_thread).detach(); });
	struct R {
		uint64_t    start, size, offset;
		int         type;
		std::string name;
	};
	static std::vector<DView> kept;
	static bool               have = false;
	std::vector<R>                             ranges;
	std::vector<std::pair<uint64_t, uint64_t>> spans;
	uint64_t                                   gen      = 0;
	bool                                       complete = false;
	if (!Libs::LibKernel::Memory::Bc5RangesWithDirty(
	        [](uint64_t start, uint64_t size, uint64_t offset, int type, int, const char* name, void* p) {
		        static_cast<std::vector<R>*>(p)->push_back({start, size, offset, type, name != nullptr ? name : ""});
	        },
	        &ranges, &gen, &spans, &complete)) {
		return;
	}
	auto make = [](const R& r, DView* v) {
		if (r.type != 0 || r.size == 0) return false;
		*v = {r.start, r.size, r.offset, r.name, ls415_name_class(r.name.c_str(), false), ls415_name_class(r.name.c_str(), true)};
		return true;
	};
	std::vector<DView> full;
	for (const R& r: ranges) {
		DView v;
		if (make(r, &v)) full.push_back(std::move(v));
	}
	if (have && complete) {
		for (const auto& [start, size]: spans) bc5::map_records::apply(kept, ranges, start, bc5::map_records::end_of(start, size), make);
		bool   same = kept.size() == full.size();
		size_t at   = 0;
		for (; same && at < full.size(); at++) {
			const DView &a = kept[at], &b = full[at];
			if (a.va != b.va || a.size != b.size || a.off != b.off || a.name != b.name || a.lazy != b.lazy || a.eager != b.eager) same = false;
		}
		bc5::load_stat::count(bc5::load_stat::kMapRecord, spans.size());
		if (!same) {
			bc5::load_stat::count(bc5::load_stat::kRecMismatch);
			d432::g_rec_mismatch++; // exp 0432
			static int logged = 0;
			if (logged++ < 8) {
				journal("map records (exp 0415, mr415): MISMATCH at generation %" PRIu64 " after %zu records: kept %zu views, rebuilt %zu, first difference at index %zu\n", gen,
				        spans.size(), kept.size(), full.size(), at == 0 ? size_t {0} : at - 1);
			}
		}
	} else if (have) {
		bc5::load_stat::count(bc5::load_stat::kRecOverflow);
	}
	kept = std::move(full);
	have = true;
}
// Experiment 0415 (tag mr415c), stage S2: KYTY_BC5_MAP_RECORDS=views. The direct-memory view list is the one kept from
// the range table's change records (stage S1 found it equal to the rebuilt list in 7,991 comparisons over 866,732
// records, both titles); the list is rebuilt from every range only every KYTY_BC5_MAP_RECORDS_CHECK_MS (2,000 when
// unset), and at that moment the kept list is compared with it and with the old builder's list (rec_mismatch) and
// replaced by it. If the record log reports a gap the list is rebuilt at once. Called under direct_views' mutex.
// Tag mr415d (build L5d): build L5b copied the kept list (12,500-28,000 views, a string each) into every new snapshot
// and so saved nothing (README section 15). The kept list is now the object handed out: records are applied to it in
// place when nobody else holds it (direct_views lets go of its own reference first), and only otherwise to a copy
// (views_clone). A holder never sees its list change: it holds a reference, so the count is above one.
// If a record were missing, a view would be absent (its memory not on the GPU) or would stay after the guest unmapped
// it (the GPU reads pages the guest gave back) until the next check, at most the check period.
static std::shared_ptr<DViews> mr415_views(const DState& S, uint64_t* gen_out) {
	struct R {
		uint64_t    start, size, offset;
		int         type;
		std::string name;
	};
	static std::shared_ptr<DViews> kept_p = std::make_shared<DViews>();
	static bool                    have   = false;
	static uint64_t           checked_ns = 0;
	static const uint64_t     period_ns  = bc5::load_stat::env_num("KYTY_BC5_MAP_RECORDS_CHECK_MS", 2000, 600'000) * 1'000'000ull;
	auto make = [](const R& r, DView* v) {
		if (r.type != 0 || r.size == 0) return false;
		*v = {r.start, r.size, r.offset, r.name, ls415_name_class(r.name.c_str(), false), ls415_name_class(r.name.c_str(), true)};
		return true;
	};
	const uint64_t                             now = SoftCp::now_ns();
	std::vector<std::pair<uint64_t, uint64_t>> spans;
	uint64_t                                   gen      = 0;
	bool                                       complete = false;
	if (have && now - checked_ns < period_ns) {
		std::vector<std::vector<R>> lists;
		if (Libs::LibKernel::Memory::Bc5RangesDirtyTouching(
		        [](size_t index, uint64_t start, uint64_t size, uint64_t offset, int type, int, const char* name, void* p) {
			        auto* l = static_cast<std::vector<std::vector<R>>*>(p);
			        if (l->size() <= index) l->resize(index + 1);
			        (*l)[index].push_back({start, size, offset, type, name != nullptr ? name : ""});
		        },
		        &lists, &gen, &spans, &complete) &&
		    complete) {
			lists.resize(spans.size());
			if (kept_p.use_count() > 1) { // someone still reads the list: leave theirs alone
				d432::g_views_clone++; // exp 0432
				kept_p = std::make_shared<DViews>(*kept_p);
			}
			std::vector<DView>& kept = kept_p->v;
			for (size_t i = 0; i < spans.size(); i++) bc5::map_records::apply(kept, lists[i], spans[i].first, bc5::map_records::end_of(spans[i].first, spans[i].second), make);
			bc5::load_stat::count(bc5::load_stat::kMapRecord, spans.size());
			*gen_out = gen;
			return kept_p;
		}
		bc5::load_stat::count(bc5::load_stat::kRecOverflow);
		have = false; // the log had a gap: the kept list is not to be compared, only replaced
	}
	std::vector<R> ranges;
	spans.clear();
	if (!Libs::LibKernel::Memory::Bc5RangesWithDirty(
	        [](uint64_t start, uint64_t size, uint64_t offset, int type, int, const char* name, void* p) {
		        static_cast<std::vector<R>*>(p)->push_back({start, size, offset, type, name != nullptr ? name : ""});
	        },
	        &ranges, &gen, &spans, &complete)) {
		auto d = std::make_shared<DViews>();
		d->v   = direct_views_build(S);
		return d;
	}
	std::vector<DView> full;
	for (const R& r: ranges) {
		DView v;
		if (make(r, &v)) full.push_back(std::move(v));
	}
	auto same = [](const std::vector<DView>& a, const std::vector<DView>& b) {
		if (a.size() != b.size()) return false;
		for (size_t i = 0; i < a.size(); i++) {
			if (a[i].va != b[i].va || a[i].size != b[i].size || a[i].off != b[i].off || a[i].name != b[i].name || a[i].lazy != b[i].lazy || a[i].eager != b[i].eager) return false;
		}
		return true;
	};
	static int logged = 0;
	if (have && complete) {
		if (kept_p.use_count() > 1) kept_p = std::make_shared<DViews>(*kept_p);
		std::vector<DView>& kept = kept_p->v;
		for (const auto& [start, size]: spans) bc5::map_records::apply(kept, ranges, start, bc5::map_records::end_of(start, size), make);
		bc5::load_stat::count(bc5::load_stat::kMapRecord, spans.size());
		if (!same(kept, full)) {
			bc5::load_stat::count(bc5::load_stat::kRecMismatch);
			d432::g_rec_mismatch++; // exp 0432
			if (logged++ < 8) journal("map records (exp 0415, mr415c): MISMATCH of the list in use at generation %" PRIu64 ": kept %zu views, rebuilt %zu\n", gen, kept.size(), full.size());
		}
	}
	// the old builder's list, read a moment later: it can differ only if the ranges changed in between
	if (const uint64_t g2 = Libs::LibKernel::Memory::Bc5MappedRangesGeneration(); g2 == gen && !d432::views_kept()) { // exp 0432: build 1 showed this second build in single calls of 104-114 ms
		const std::vector<DView> old = direct_views_build(S);
		if (Libs::LibKernel::Memory::Bc5MappedRangesGeneration() == gen && !same(old, full)) {
			bc5::load_stat::count(bc5::load_stat::kRecMismatch);
			d432::g_rec_mismatch++; // exp 0432
			if (logged++ < 8) journal("map records (exp 0415, mr415c): the snapshot's list differs from the old builder's at generation %" PRIu64 ": %zu against %zu views\n", gen, full.size(), old.size());
		}
	}
	kept_p     = std::make_shared<DViews>();
	kept_p->v  = std::move(full);
	have       = true;
	checked_ns = now;
	*gen_out   = gen;
	return kept_p;
}

static std::shared_ptr<const DViews> direct_views(const DState& S) {
	static std::mutex                    m;
	static std::shared_ptr<const DViews> cache[2];
	static uint64_t                      gen[2] = {0, 0};
	const int                            k = S.kind == 0 ? 0 : 1;
	// Private regions follow the same ranges (every private mapping is a range of the guest's),
	// but their list comes from the address space's own map: to be safe it is also rebuilt once a
	// second. Listing them walked all 11,600 ranges for each of the 140 regions.
	static uint64_t built_ns[2] = {0, 0};
	const uint64_t  g           = k == 0 ? vg437_gen() : Libs::LibKernel::Memory::Bc5MappedRangesGeneration(); // exp 0437 (tag vg437)
	const uint64_t  now         = SoftCp::now_ns();
	std::lock_guard l(m);
	if (g != 0 && g == gen[k] && cache[k] != nullptr && (k == 0 || now - built_ns[k] < 1'000'000'000ull)) return cache[k];
	built_ns[k] = now;
	g_views_builds++;
	std::shared_ptr<DViews> d;
	uint64_t                g_used = g;
	if (k == 0 && mr415_mode() == 2) { // experiment 0415 (mr415c), stage S2: the list kept from the change records
		cache[k].reset();              // mr415d: so that the kept list can change in place when no caller holds it
		d = mr415_views(S, &g_used);
	} else {
		d    = std::make_shared<DViews>();
		d->v = direct_views_build(S);
		if (k == 0) mr415_verify(); // experiment 0415 (mr415)
	}
	d->sorted = true;
	uint64_t sig = 1469598103934665603ull;
	for (size_t i = 0; i < d->v.size(); i++) {
		const auto& v = d->v[i];
		for (const uint64_t x: {v.va, v.size, v.off}) sig = (sig ^ x) * 1099511628211ull;
		if (i > 0 && d->v[i - 1].va + d->v[i - 1].size > v.va) d->sorted = false;
	}
	d->sig   = sig;
	cache[k] = d;
	gen[k]   = k == 0 && vg437_on() ? g : g_used; // experiment 0415 (mr415c): the generation of the snapshot the list was made from; exp 0437 (vg437): kind 0's direct generation
	return d;
}

// The driver's GTT accounting, from sysfs (mem_info_gtt_total / mem_info_gtt_used of the render
// node's device), 0 when unreadable.
static uint64_t direct_gtt(const char* leaf) {
	const std::string n = kRenderNode;
	const size_t      cut  = n.rfind('/');
	const std::string path = "/sys/class/drm/" + (cut == std::string::npos ? n : n.substr(cut + 1)) + "/device/" + leaf;
	unsigned long long v = 0;
	if (FILE* f = std::fopen(path.c_str(), "r")) {
		if (std::fscanf(f, "%llu", &v) != 1) v = 0;
		std::fclose(f);
	}
	return v;
}

// End of the imported range that holds `off`, 0 when none does.
static uint64_t direct_covered_end(const DState& S, uint64_t off) {
	auto it = std::upper_bound(S.bos.begin(), S.bos.end(), off, [](uint64_t o, const DBo& b) { return o < b.off; });
	if (it == S.bos.begin()) return 0;
	--it;
	return off < it->off + it->size ? it->off + it->size : 0;
}

// Where the imported memory is, by the name the game gave each mapping: reserved, holding data
// (SEEK_DATA/SEEK_HOLE over the memfd), imported. Journalled each time the imported total has
// grown by 512 MiB, and when a submission fails with -ENOMEM.
static void direct_breakdown_one(DState& S, const char* why, uint32_t list_bos) {
	const int fd = dstate_fd(S);
	if (fd < 0) return;
	struct Row {
		uint64_t reserved = 0, data = 0, imported = 0;
		uint32_t views = 0;
		bool     lazy = false;
	};
	std::map<std::string, Row> rows;
	Row                        total;
	const auto views_p = direct_views(S);
	for (const auto& v: views_p->v) {
		Row&           r   = rows[v.size >= (1ull << 20u) ? v.name : std::string("(views under 1 MiB)")];
		const uint64_t end = v.off + v.size;
		uint64_t       data = 0, imported = 0;
		for (uint64_t pos = v.off; pos < end;) {
			const off_t d = lseek(fd, static_cast<off_t>(pos), SEEK_DATA);
			if (d < 0 || static_cast<uint64_t>(d) >= end) break;
			const off_t    h  = lseek(fd, d, SEEK_HOLE);
			const uint64_t he = h < 0 || static_cast<uint64_t>(h) > end ? end : static_cast<uint64_t>(h);
			if (he <= static_cast<uint64_t>(d)) break;
			data += he - static_cast<uint64_t>(d);
			pos = he;
		}
		auto it = std::upper_bound(S.bos.begin(), S.bos.end(), v.off, [](uint64_t o, const DBo& b) { return o < b.off; });
		if (it != S.bos.begin()) --it;
		for (; it != S.bos.end() && it->off < end; ++it) {
			const uint64_t lo = it->off > v.off ? it->off : v.off;
			const uint64_t hi = it->off + it->size < end ? it->off + it->size : end;
			if (lo < hi) imported += hi - lo;
		}
		r.views++;
		r.reserved += v.size;
		r.data += data;
		r.imported += imported;
		r.lazy = r.lazy || v.lazy;
		total.views++;
		total.reserved += v.size;
		total.data += data;
		total.imported += imported;
	}
	const double mib = 1048576.0;
	journal("%s by name (%s): %zu BOs, %.1f MiB imported; BO list of the submit %u; GTT %.1f of %.1f MiB in use\n", S.label, why, S.bos.size(),
	        static_cast<double>(S.bytes) / mib, list_bos, static_cast<double>(direct_gtt("mem_info_gtt_used")) / mib, static_cast<double>(direct_gtt("mem_info_gtt_total")) / mib);
	for (const auto& [name, r]: rows) {
		journal("  %-28s %3u views: %8.1f MiB reserved, %8.1f with data, %8.1f imported%s\n", name.c_str(), r.views, static_cast<double>(r.reserved) / mib,
		        static_cast<double>(r.data) / mib, static_cast<double>(r.imported) / mib, r.lazy ? " (lazy)" : "");
	}
	journal("  %-28s %3u views: %8.1f MiB reserved, %8.1f with data, %8.1f imported\n", "total (views may alias)", total.views, static_cast<double>(total.reserved) / mib,
	        static_cast<double>(total.data) / mib, static_cast<double>(total.imported) / mib);
}

static void direct_breakdown(const char* why, uint32_t list_bos) {
	for (auto& S: g_d) direct_breakdown_one(S, why, list_bos);
}

// ---- experiment 0401 series e7, lzr: BC5_DIRECT_LAZY_RELEASE, the pure part --------------------------------------------
// mklzr0401.py writes this block into the unit and, byte for byte, into lzr0401.inc for the CPU test lzr0401.cpp. It needs
// <algorithm>, <cstddef>, <cstdint>, <set>, <string>, <utility> and <vector>. No GPU access, no global state.
//
// The direct path pins the direct memfd in 2 MiB chunks and never gives one back (direct_sync_one, ADR 0006; exp 0379
// README, "What the code allows"). A chunk under no view has no GPU mapping: each rebuild drops every mapping no view
// asks for. No submission can reach it, and a draw's BO list names its BO only for the BO's other chunks
// (backend/src/direct.cpp: the full list holds every imported BO that is mapped somewhere). plan() finds the imported
// chunks that have been under no view for the idle time and are not forced (S.forced: the hint and learned windows,
// the host's only record that the GPU needs memory no CPU wrote), and cuts them out of their BOs: the BO's other chunks
// become imports of their own and the old BO is retired, as the merge retires one. A chunk last seen under an eager
// view, or never seen under a view, is cut only with the "eager" word; a chunk of a zero-list heap (BC5_DIRECT_ZERO_SKIP,
// exp 0379) never. reviewed() names the released chunks a view covers again; the caller imports them before the mappings
// are built, so every mapping a rebuild makes has the chunks it would have without the switch. Nothing here punches the
// memfd: a released chunk keeps its pages and data, unpinned.
namespace Lzr0401 {

constexpr uint64_t kChunk  = 2ull << 20u;
constexpr uint64_t kSecond = 1'000'000'000ull;

struct Opts {
	bool        on      = false;
	bool        dry     = false; // count and journal; cut nothing
	bool        eager   = false; // also chunks last seen under an eager view, or never seen under a view
	uint64_t    idle_ns = 0;
	std::string why;             // the reading, for the journal
};

// BC5_DIRECT_LAZY_RELEASE=<seconds>[,dry][,eager]. Unset, empty and "0" are off (F767). The seconds are 1 to 86400 in
// decimal digits; any other text leaves the switch off, and why says so (lesson R41).
inline Opts parse(const char* e) {
	Opts o;
	if (e == nullptr || e[0] == 0 || (e[0] == '0' && e[1] == 0)) {
		o.why = e == nullptr ? "unset" : e[0] == 0 ? "empty" : "0";
		return o;
	}
	const std::string        s(e);
	std::vector<std::string> parts(1);
	for (const char c: s) {
		if (c == ',') {
			parts.emplace_back();
		} else {
			parts.back().push_back(c);
		}
	}
	uint64_t secs   = 0;
	bool     digits = !parts[0].empty() && parts[0].size() <= 5;
	for (const char c: parts[0]) {
		digits = digits && c >= '0' && c <= '9';
		if (digits) secs = secs * 10 + static_cast<uint64_t>(c - '0');
	}
	if (!digits || secs == 0 || secs > 86400) {
		o.why = "\"" + s + "\" does not parse: the idle time is 1 to 86400 seconds";
		return o;
	}
	bool dry_word = false, eager_word = false;
	for (size_t k = 1; k < parts.size(); k++) {
		if (parts[k] == "dry") {
			dry_word = true;
		} else if (parts[k] == "eager") {
			eager_word = true;
		} else {
			o.why = "\"" + s + "\" does not parse: the word \"" + parts[k] + "\" is not dry or eager";
			return o;
		}
	}
	o.on      = true;
	o.dry     = dry_word;
	o.eager   = eager_word;
	o.idle_ns = secs * kSecond;
	o.why     = std::to_string(secs) + " s" + (dry_word ? ", dry" : "") + (eager_word ? ", eager" : "");
	return o;
}

// Cuts are made only when on and not dry.
inline bool apply_allowed(const Opts& o) { return o.on && !o.dry; }

// The pass period: a quarter of the idle time, 1 to 15 seconds.
inline uint64_t period(const Opts& o) {
	const uint64_t q = o.idle_ns / 4;
	return q < kSecond ? kSecond : q > 15 * kSecond ? 15 * kSecond : q;
}

struct Range {
	uint64_t lo, hi; // [lo, hi), memfd offsets
};

// Sorted, with overlapping or touching ranges joined and empty ones dropped.
inline std::vector<Range> merged(std::vector<Range> v) {
	v.erase(std::remove_if(v.begin(), v.end(), [](const Range& r) { return r.lo >= r.hi; }), v.end());
	std::sort(v.begin(), v.end(), [](const Range& a, const Range& b) { return a.lo < b.lo; });
	std::vector<Range> out;
	for (const auto& r: v) {
		if (!out.empty() && r.lo <= out.back().hi) {
			out.back().hi = std::max(out.back().hi, r.hi);
		} else {
			out.push_back(r);
		}
	}
	return out;
}

// Whether [lo, hi) meets one of c's ranges (c from merged()).
inline bool hits(const std::vector<Range>& c, uint64_t lo, uint64_t hi) {
	const auto it = std::partition_point(c.begin(), c.end(), [lo](const Range& r) { return r.hi <= lo; });
	return it != c.end() && it->lo < hi;
}

// The views' memfd ranges by class, as direct_sync_one's import loop ranks them: eager first, then lazy, then data
// (neither); zero: a heap of the zero skip's list. V has off, size, eager and lazy (DView); zero(v) says whether v is a
// zero-list heap.
struct Covers {
	std::vector<Range> all, eager, data, lazy, zero;
};
template <class V, class Z> Covers covers(const std::vector<V>& views, Z zero) {
	Covers c;
	for (const auto& v: views) {
		if (v.size == 0) continue;
		const Range r {v.off, v.off + v.size};
		c.all.push_back(r);
		if (v.eager) {
			c.eager.push_back(r);
		} else if (v.lazy) {
			c.lazy.push_back(r);
		} else {
			c.data.push_back(r);
		}
		if (zero(v)) c.zero.push_back(r);
	}
	c.all   = merged(std::move(c.all));
	c.eager = merged(std::move(c.eager));
	c.data  = merged(std::move(c.data));
	c.lazy  = merged(std::move(c.lazy));
	c.zero  = merged(std::move(c.zero));
	return c;
}

// What the passes remember of each imported chunk.
struct Chunk {
	uint64_t off   = 0;
	uint64_t since = 0;     // when a pass first found it under no view and not forced (0: not so at the last pass)
	bool     seen  = false; // a pass found it under a view
	bool     eager = false; // ... and an eager view was among them, at the last such pass
	bool     zero  = false; // ... or a zero-list heap
};
struct State {
	std::vector<Chunk> chunks;   // the imported chunks at the last pass, by offset
	std::set<uint64_t> released; // chunks cut out and not imported again since
	uint64_t           last_pass = 0, last_report = 0, passes = 0;
	uint64_t           cuts = 0, wholes = 0, splits = 0, cut_bytes = 0, back_bytes = 0, undone = 0, import_failed = 0, deferred = 0;
};
struct BoIn {
	uint64_t off, size; // a BO of S.bos
	uint32_t id;
	uint32_t maps;      // the GPU mappings on it (S.maps)
};
struct Cut {
	uint64_t              off = 0, size = 0; // the BO
	uint32_t              id = 0, maps = 0;
	std::vector<Range>    keep;    // its chunks that stay, as runs: each becomes an import of its own
	std::vector<uint64_t> dropped; // the chunks cut out
	uint64_t              drop = 0; // their bytes
};
struct Plan {
	std::vector<Cut> cuts;
	uint64_t         imported = 0, eager_v = 0, data_v = 0, lazy_v = 0; // bytes: imported; under eager, data, lazy views
	uint64_t         forced_u = 0, unviewed = 0;     // under no view: forced; not forced
	uint64_t         seen_eager = 0, never_seen = 0; // of unviewed: last seen under an eager or zero-list view; never seen
	uint64_t         ready = 0, drop = 0;            // of unviewed: idle for the idle time; cut in this plan
	uint32_t         deferred = 0, nosplit = 0;      // BOs left for a later pass: budget or cut count; splits off
};

// A pass is due when on, at the first call, then once per period.
inline bool due(const Opts& o, const State& st, uint64_t now) { return o.on && (st.passes == 0 || now - st.last_pass >= period(o)); }

// One pass. bos: S.bos in order (disjoint; a BO not chunk-aligned is never cut); forced: S.forced; now: the sync's
// SoftCp::now_ns(); map_budget: the GPU mappings the cuts may move (the merge's budget, what the merge left of it);
// max_cuts: BOs cut per pass; splits: false when a BO may only go whole (BC5_DIRECT_ALIASES: the aliases of a BO's
// mappings come back only at the next aliases_apply); zero_skip: BC5_DIRECT_ZERO_SKIP is set. Updates st.chunks and
// counts; cuts nothing itself.
inline Plan plan(const Opts& o, State& st, const std::vector<BoIn>& bos, const Covers& cv, const std::set<uint64_t>& forced, uint64_t now, uint32_t map_budget,
				 size_t max_cuts, bool splits, bool zero_skip) {
	Plan p;
	if (!o.on) return p;
	st.last_pass = now;
	st.passes++;
	std::vector<Chunk> next;
	next.reserve(st.chunks.size());
	size_t k = 0;
	for (const auto& b: bos) {
		if (b.size == 0 || b.off % kChunk != 0 || b.size % kChunk != 0) {
			p.imported += b.size;
			continue;
		}
		std::vector<uint64_t> drop;
		for (uint64_t c = b.off; c < b.off + b.size; c += kChunk) {
			while (k < st.chunks.size() && st.chunks[k].off < c) k++;
			Chunk ch;
			ch.off = c;
			if (k < st.chunks.size() && st.chunks[k].off == c) ch = st.chunks[k];
			p.imported += kChunk;
			if (hits(cv.all, c, c + kChunk)) {
				ch.since = 0;
				ch.seen  = true;
				ch.eager = hits(cv.eager, c, c + kChunk);
				ch.zero  = hits(cv.zero, c, c + kChunk);
				if (ch.eager) {
					p.eager_v += kChunk;
				} else if (hits(cv.data, c, c + kChunk)) {
					p.data_v += kChunk;
				} else {
					p.lazy_v += kChunk;
				}
			} else if (forced.count(c) != 0) {
				ch.since = 0;
				p.forced_u += kChunk;
			} else {
				p.unviewed += kChunk;
				if (ch.since == 0 || ch.since > now) ch.since = now;
				const bool ready   = now - ch.since >= o.idle_ns;
				const bool allowed = ch.seen ? !ch.zero && (o.eager || !ch.eager) : o.eager && !zero_skip;
				if (!ch.seen) {
					p.never_seen += kChunk;
				} else if (ch.eager || ch.zero) {
					p.seen_eager += kChunk;
				}
				if (ready) p.ready += kChunk;
				if (ready && allowed) drop.push_back(c);
			}
			next.push_back(ch);
		}
		if (drop.empty()) continue;
		const bool whole = static_cast<uint64_t>(drop.size()) * kChunk == b.size;
		if (!whole && !splits) {
			p.nosplit++;
			continue;
		}
		if (p.cuts.size() >= max_cuts || b.maps > map_budget) {
			p.deferred++;
			continue;
		}
		map_budget -= b.maps;
		Cut cut;
		cut.off  = b.off;
		cut.size = b.size;
		cut.id   = b.id;
		cut.maps = b.maps;
		uint64_t run  = 0;
		bool     open = false;
		size_t   di   = 0;
		for (uint64_t c = b.off; c < b.off + b.size; c += kChunk) {
			if (di < drop.size() && drop[di] == c) {
				di++;
				if (open) cut.keep.push_back({run, c});
				open = false;
			} else if (!open) {
				run  = c;
				open = true;
			}
		}
		if (open) cut.keep.push_back({run, b.off + b.size});
		cut.drop    = static_cast<uint64_t>(drop.size()) * kChunk;
		cut.dropped = std::move(drop);
		p.drop += cut.drop;
		p.cuts.push_back(std::move(cut));
	}
	st.chunks.swap(next);
	st.deferred += p.deferred;
	return p;
}

// The released chunks a view covers again (V has off and size), sorted.
template <class V> std::vector<uint64_t> reviewed(const std::set<uint64_t>& released, const std::vector<V>& views) {
	std::vector<uint64_t> out;
	if (released.empty()) return out;
	for (const auto& v: views) {
		if (v.size == 0) continue;
		for (auto it = released.lower_bound(v.off - v.off % kChunk); it != released.end() && *it < v.off + v.size; ++it) out.push_back(*it);
	}
	std::sort(out.begin(), out.end());
	out.erase(std::unique(out.begin(), out.end()), out.end());
	return out;
}

// Chunks (sorted, unique) as runs of neighbours of at most max_bytes each (kDMaxBo), as direct_sync_one groups imports.
inline std::vector<Range> runs(const std::vector<uint64_t>& chunks, uint64_t max_bytes) {
	std::vector<Range> out;
	for (const uint64_t c: chunks) {
		if (!out.empty() && out.back().hi == c && c + kChunk - out.back().lo <= max_bytes) {
			out.back().hi = c + kChunk;
		} else {
			out.push_back({c, c + kChunk});
		}
	}
	return out;
}

// On a sorted BO list whose B is {off, size, id, t_ns} (DBo): the end of the BO that holds off, 0 when none does
// (direct_covered_end's rule); a BO put in its place; a cut applied (the BO replaced by its kept runs with the new ids,
// false and nothing changed when the list does not hold that BO); a cut undone (the kept runs out, the BO back).
template <class B> uint64_t covered_end(const std::vector<B>& bos, uint64_t off) {
	auto it = std::upper_bound(bos.begin(), bos.end(), off, [](uint64_t o, const B& b) { return o < b.off; });
	if (it == bos.begin()) return 0;
	--it;
	return off < it->off + it->size ? it->off + it->size : 0;
}
template <class B> void insert_bo(std::vector<B>& bos, uint64_t off, uint64_t size, uint32_t id, uint64_t t_ns) {
	bos.insert(std::upper_bound(bos.begin(), bos.end(), off, [](uint64_t o, const B& b) { return o < b.off; }), B {off, size, id, t_ns});
}
template <class B> bool apply_cut(std::vector<B>& bos, const Cut& cut, const std::vector<uint32_t>& ids, uint64_t now, uint64_t* old_t) {
	if (ids.size() != cut.keep.size()) return false;
	const auto it = std::lower_bound(bos.begin(), bos.end(), cut.off, [](const B& b, uint64_t o) { return b.off < o; });
	if (it == bos.end() || it->off != cut.off || it->size != cut.size || it->id != cut.id) return false;
	if (old_t != nullptr) *old_t = it->t_ns;
	bos.erase(it);
	for (size_t i = 0; i < ids.size(); i++) insert_bo(bos, cut.keep[i].lo, cut.keep[i].hi - cut.keep[i].lo, ids[i], now);
	return true;
}
template <class B> bool undo_cut(std::vector<B>& bos, const Cut& cut, const std::vector<uint32_t>& ids, uint64_t old_t) {
	if (ids.size() != cut.keep.size()) return false;
	auto at = [&bos](uint64_t off) { return std::lower_bound(bos.begin(), bos.end(), off, [](const B& b, uint64_t o) { return b.off < o; }); };
	for (size_t i = 0; i < ids.size(); i++) {
		const auto it = at(cut.keep[i].lo);
		if (it == bos.end() || it->off != cut.keep[i].lo || it->size != cut.keep[i].hi - cut.keep[i].lo || it->id != ids[i]) return false;
	}
	for (const uint64_t c: cut.dropped) {
		if (covered_end(bos, c) != 0) return false; // something holds a cut chunk now: the BO cannot come back whole
	}
	for (size_t i = 0; i < ids.size(); i++) bos.erase(at(cut.keep[i].lo));
	insert_bo(bos, cut.off, cut.size, cut.id, old_t);
	return true;
}

// The record of cuts made, undone and taken back. A cut chunk leaves st.chunks: imported again, it starts as never seen.
inline void note_cut(State& st, const Cut& cut) {
	st.cuts++;
	(cut.keep.empty() ? st.wholes : st.splits)++;
	st.cut_bytes += cut.drop;
	for (const uint64_t c: cut.dropped) st.released.insert(c);
	st.chunks.erase(std::remove_if(st.chunks.begin(), st.chunks.end(), [&cut](const Chunk& k) { return std::binary_search(cut.dropped.begin(), cut.dropped.end(), k.off); }),
					st.chunks.end());
}
inline void note_undo(State& st, const Cut& cut) {
	st.undone++;
	st.cuts--;
	(cut.keep.empty() ? st.wholes : st.splits)--;
	st.cut_bytes -= cut.drop;
	for (const uint64_t c: cut.dropped) st.released.erase(c);
}
inline void note_back(State& st, uint64_t c) {
	if (st.released.erase(c) != 0) st.back_bytes += kChunk;
}

} // namespace Lzr0401

// ---- experiment 0401 series e7, lzr: BC5_DIRECT_LAZY_RELEASE, the host's side -----------------------------------------
// lzr_pass runs in direct_sync_one between the merge and the mapping rebuild, for the direct memfd only:
//   1. released chunks a view covers again are imported (in that sync, before the rebuild maps the view); one the eager
//      or data path took already only leaves the released set;
//   2. once per pass period, not in a sync whose merge did something, plan() picks the chunks to cut. Each cut BO's kept
//      runs are imported first (a failed import leaves the BO whole), then the BO is replaced in S.bos and its id goes to
//      `retired`: the rebuild's drain (wait_jobs) runs, the mappings move to the new BOs, and the old BO is freed after
//      the rebuild, as the merge's are.
// lzr_confirm runs right after that drain: a cut stands only when every ring is idle (Device::wait_idle(0)); otherwise
// each cut is undone (its new BOs were never mapped, so they are freed at once) and the chunks wait for a later pass.
// Off (the default): one journal line at the first sync, then a return.
struct LzrDone {
	Lzr0401::Cut          cut;
	std::vector<uint32_t> ids;
	uint64_t              old_t = 0;
};
struct LzrPass {
	std::vector<LzrDone> done;
};
static Lzr0401::State g_lzr;
static uint64_t       g_lzr_rv_sig = 0; // the views' signature at the last look for released chunks under a view
static const Lzr0401::Opts& lzr_opts() {
	static const Lzr0401::Opts o = Lzr0401::parse(std::getenv("BC5_DIRECT_LAZY_RELEASE"));
	return o;
}
// Exp 0379's zero skip, read by its switch and heap names (BC5_DIRECT_ZERO_SKIP set; BC5_DIRECT_ZERO_NAMES, default
// RenderGpuWcLarge,CommitIABufferAllocator), so this block needs none of the skip's code.
static bool lzr_zero_skip() {
	static const bool on = false; /* exp 0419: option removed */
	return on;
}
static bool lzr_zero_name(const std::string& name) {
	static const std::vector<std::string> names = [] {
		std::vector<std::string> v;
		if (!lzr_zero_skip()) return v;
		const char* e = nullptr; /* exp 0419: option removed */
		std::string s = e != nullptr ? e : "RenderGpuWcLarge,CommitIABufferAllocator", cur;
		for (const char c: s + ",") {
			if (c == ',') {
				if (!cur.empty()) v.push_back(cur);
				cur.clear();
			} else {
				cur.push_back(c);
			}
		}
		return v;
	}();
	return !names.empty() && std::find(names.begin(), names.end(), name) != names.end();
}
static bool guard0412_split(); // exp 0412 (tag g412c): BC5_GUARD_SPLIT
static LzrPass lzr_pass(DState& S, const std::vector<DView>& views, uint64_t sig, int fd, uint64_t now, uint32_t merged, std::vector<uint32_t>& retired, uint32_t merge_remaps,
						uint32_t map_cap) {
	LzrPass                    out;
	const Lzr0401::Opts&       o   = lzr_opts();
	static constexpr double    mib = 1048576.0;
	static bool                said = false;
	if (!said) {
		said = true;
		if (o.on) {
			journal("lazy release (exp 0401 e7): on (%s): an imported chunk of the direct memfd under no view for %" PRIu64 " s, not forced by a hint or learned window, %s, is cut out of its "
					"BO%s; a view over it again imports it before the mappings are built; passes every %.1f s\n",
					o.why.c_str(), o.idle_ns / Lzr0401::kSecond, o.eager ? "eager-heap chunks too, zero-list chunks never" : "never one of an eager or zero-list heap",
					o.dry ? " (dry: counted only, nothing cut)" : "", static_cast<double>(Lzr0401::period(o)) / 1e9);
		} else {
			journal("lazy release (exp 0401 e7): off (BC5_DIRECT_LAZY_RELEASE %s)\n", o.why.c_str());
		}
	}
	if (!o.on || S.kind != 0 || !g_dev || fd < 0) return out;
	const bool apply = Lzr0401::apply_allowed(o);
	// 1. Released chunks under a view again.
	if (apply && !g_lzr.released.empty() && sig != g_lzr_rv_sig) {
		bool                  retry = false;
		uint64_t              got = 0, had = 0;
		std::vector<uint64_t> need;
		for (const uint64_t c: Lzr0401::reviewed(g_lzr.released, views)) {
			if (Lzr0401::covered_end(S.bos, c) != 0) {
				Lzr0401::note_back(g_lzr, c); // the eager or data path imported it in this sync
				had += Lzr0401::kChunk;
			} else {
				need.push_back(c);
			}
		}
		for (const auto& r: Lzr0401::runs(need, kDMaxBo)) {
			const uint32_t id = r.hi <= S.file_size ? ls415_import(fd, r.lo, r.hi - r.lo) : 0;
			if (id == 0) {
				retry = true;
				if (g_lzr.import_failed++ < 16) journal("lazy release (exp 0401 e7): import 0x%" PRIx64 " +0x%" PRIx64 " of released chunks under a view again FAILED (tried again at the next sync)\n", r.lo, r.hi - r.lo);
				continue;
			}
			Lzr0401::insert_bo(S.bos, r.lo, r.hi - r.lo, id, now);
			S.bytes += r.hi - r.lo;
			got += r.hi - r.lo;
			for (uint64_t c = r.lo; c < r.hi; c += Lzr0401::kChunk) Lzr0401::note_back(g_lzr, c);
		}
		static uint64_t n_back = 0;
		if ((got != 0 || had != 0) && (n_back++ < 16 || (n_back & 63u) == 0)) {
			journal("lazy release (exp 0401 e7): released chunks under a view again: %.1f MiB imported now, %.1f MiB imported by the eager or data path; %zu chunks still released\n",
					static_cast<double>(got) / mib, static_cast<double>(had) / mib, g_lzr.released.size());
		}
		g_lzr_rv_sig = retry ? 0 : sig;
	}
	// 2. The pass.
	if (!Lzr0401::due(o, g_lzr, now) || merged != 0) return out;
	static Lzr0401::Covers cov;
	static uint64_t        cov_sig = 0;
	static bool            cov_ok  = false;
	if (!cov_ok || cov_sig != sig) {
		cov     = Lzr0401::covers(views, [](const DView& v) { return lzr_zero_name(v.name); });
		cov_sig = sig;
		cov_ok  = true;
	}
	std::unordered_map<uint32_t, uint32_t> maps_on;
	for (const auto& m: S.maps) maps_on[m.id]++;
	std::vector<Lzr0401::BoIn> bos;
	bos.reserve(S.bos.size());
	for (const auto& b: S.bos) {
		const auto it = maps_on.find(b.id);
		bos.push_back({b.off, b.size, b.id, it != maps_on.end() ? it->second : 0u});
	}
	const bool          splits = !bc5::env_on(std::getenv("BC5_DIRECT_ALIASES")) || guard0412_split(); // exp 0412 (tag g412c)
	const Lzr0401::Plan p      = Lzr0401::plan(o, g_lzr, bos, cov, S.forced, now, map_cap > merge_remaps ? map_cap - merge_remaps : 0u, 32, splits, lzr_zero_skip());
	if (g_lzr.last_report == 0 || now - g_lzr.last_report >= 60 * Lzr0401::kSecond) {
		g_lzr.last_report = now;
		journal("lazy release (exp 0401 e7): t %.0f s: %.1f MiB imported: %.1f under eager views, %.1f under data views, %.1f under lazy views, %.1f forced and under no view, %.1f under no view "
				"(%.1f last seen under an eager or zero-list view, %.1f never seen under one; %.1f idle %" PRIu64 " s or more)%s; cut %.1f MiB in %" PRIu64 " BOs (%" PRIu64 " whole, %" PRIu64
				" split), back %.1f MiB, %zu chunks released now, %" PRIu64 " undone, %" PRIu64 " imports failed, %" PRIu64 " BOs deferred, %u not split (aliases); GTT %.1f of %.1f MiB\n",
				timing_now(), static_cast<double>(p.imported) / mib, static_cast<double>(p.eager_v) / mib, static_cast<double>(p.data_v) / mib, static_cast<double>(p.lazy_v) / mib,
				static_cast<double>(p.forced_u) / mib, static_cast<double>(p.unviewed) / mib, static_cast<double>(p.seen_eager) / mib, static_cast<double>(p.never_seen) / mib,
				static_cast<double>(p.ready) / mib, o.idle_ns / Lzr0401::kSecond, o.dry ? "; dry, nothing cut" : "", static_cast<double>(g_lzr.cut_bytes) / mib, g_lzr.cuts, g_lzr.wholes,
				g_lzr.splits, static_cast<double>(g_lzr.back_bytes) / mib, g_lzr.released.size(), g_lzr.undone, g_lzr.import_failed, g_lzr.deferred, p.nosplit,
				static_cast<double>(direct_gtt("mem_info_gtt_used")) / mib, static_cast<double>(direct_gtt("mem_info_gtt_total")) / mib);
	}
	if (!apply || p.cuts.empty()) return out;
	uint64_t cut_bytes = 0;
	uint32_t moved     = 0;
	for (const auto& cut: p.cuts) {
		std::vector<uint32_t> ids;
		bool                  ok = true;
		for (const auto& r: cut.keep) {
			const uint32_t id = ls415_import(fd, r.lo, r.hi - r.lo);
			if (id == 0) {
				ok = false;
				break;
			}
			ids.push_back(id);
		}
		uint64_t old_t = 0;
		if (!ok || !Lzr0401::apply_cut(S.bos, cut, ids, now, &old_t)) {
			for (const uint32_t id: ids) g_dev->free_shared(id); // never mapped
			if (!ok && g_lzr.import_failed++ < 16) journal("lazy release (exp 0401 e7): an import of the kept part of BO 0x%" PRIx64 " +0x%" PRIx64 " FAILED: the BO stays whole\n", cut.off, cut.size);
			continue;
		}
		retired.push_back(cut.id);
		moved += cut.maps;
		S.bytes -= cut.drop;
		cut_bytes += cut.drop;
		Lzr0401::note_cut(g_lzr, cut);
		out.done.push_back({cut, std::move(ids), old_t});
	}
	static uint64_t n_cut = 0;
	if (!out.done.empty() && (n_cut++ < 16 || (n_cut & 63u) == 0)) {
		journal("lazy release (exp 0401 e7): cut %.1f MiB out of %zu BOs (%u mappings to move); %.1f MiB cut in all, %zu chunks released now\n", static_cast<double>(cut_bytes) / mib, out.done.size(),
				moved, static_cast<double>(g_lzr.cut_bytes) / mib, g_lzr.released.size());
	}
	return out;
}
static void lzr_confirm(DState& S, LzrPass& pass, std::vector<uint32_t>& retired) {
	if (pass.done.empty() || !g_dev) return;
	if (d432::on()) return; // exp 0432 (tag d432): the cut stands, the kernel retires the old mappings behind the jobs in flight
	if (g_dev->wait_idle(0)) return;
	uint64_t back = 0;
	size_t   n    = 0;
	for (auto it = pass.done.rbegin(); it != pass.done.rend(); ++it) {
		if (!Lzr0401::undo_cut(S.bos, it->cut, it->ids, it->old_t)) {
			journal("lazy release (exp 0401 e7): BO 0x%" PRIx64 " +0x%" PRIx64 " could not be put back: the cut stands on a GPU that was not idle\n", it->cut.off, it->cut.size);
			continue;
		}
		for (const uint32_t id: it->ids) g_dev->free_shared(id); // never mapped
		retired.erase(std::remove(retired.begin(), retired.end(), it->cut.id), retired.end());
		S.bytes += it->cut.drop;
		back += it->cut.drop;
		n++;
		Lzr0401::note_undo(g_lzr, it->cut);
	}
	journal("lazy release (exp 0401 e7): a ring was still busy after the drain: %zu cuts undone (%.1f MiB), tried again at a later pass\n", n, static_cast<double>(back) / 1048576.0);
}

static std::vector<std::pair<uint64_t, uint64_t>> g_scratch; // experiment 0037: zero-buffer pieces, va and size
static void scratch_release(uint64_t lo, uint64_t hi);

// Experiment 0412 (tag ww412): ww0412.inc, BC5_GUARD_WRITERS, the log-only catcher for unnamed writers.
namespace ww412 {
inline bool on() {
	static const bool v = [] {
		const char* e = BC5_DIAG_ENV("BC5_GUARD_WRITERS");
		return e != nullptr && e[0] != 0 && !(e[0] == '0' && e[1] == 0);
	}();
	return v;
}
struct Turned {
	uint64_t              turned = 0, named = 0; // chunks all zero before and not now; of them named
	std::vector<uint64_t> unnamed;               // file offsets of the first not-named ones (at most keep)
};
// prev and now: one flag per scan slot of a heap (1 = all zero), slot i at file offset base + i * chunk (base need not
// lie on the file's chunk grid). is_named(file chunk offset on the grid) says whether that chunk was ever named. A
// slot that straddles two grid chunks is named when either is.
template <typename F> inline Turned classify(const std::vector<uint8_t>& prev, const std::vector<uint8_t>& now, uint64_t base, uint64_t chunk, size_t keep, F&& is_named) {
	Turned t;
	if (prev.size() != now.size()) return t; // the heap's span changed: no comparison for this interval
	for (size_t i = 0; i < now.size(); i++) {
		if (prev[i] != 1 || now[i] != 0) continue;
		t.turned++;
		const uint64_t c  = base + static_cast<uint64_t>(i) * chunk;
		const uint64_t g0 = (c / chunk) * chunk, g1 = ((c + chunk - 1) / chunk) * chunk;
		if (is_named(g0) || (g1 != g0 && is_named(g1))) t.named++;
		else if (t.unnamed.size() < keep) t.unnamed.push_back(c);
	}
	return t;
}
} // namespace ww412
// Experiment 0412 (tag wc412): wc0412.inc, BC5_GUARD_WRITERS=2, the CPU/GPU split by the soft-dirty bit.
#include <sys/sysmacros.h> // major, minor
namespace wc412 {
inline int level() { // 0 off, 1 the catcher, 2 the catcher with the CPU/GPU split
	static const int v = [] {
		const char* e = BC5_DIAG_ENV("BC5_GUARD_WRITERS");
		if (e == nullptr || e[0] == 0 || (e[0] == '0' && e[1] == 0)) return 0;
		return e[0] == '2' && e[1] == 0 ? 2 : 1;
	}();
	return v;
}
struct MapLine {
	uint64_t va = 0, len = 0, off = 0; // a mapping of the file: [va, va + len) shows the file from off
};
// The lines of /proc/self/maps that map the file with this device and inode ("start-end perms offset maj:min inode path").
inline std::vector<MapLine> parse_maps(const std::string& text, unsigned maj, unsigned min, uint64_t ino) {
	std::vector<MapLine> out;
	size_t               pos = 0;
	while (pos < text.size()) {
		size_t nl = text.find('\n', pos);
		if (nl == std::string::npos) nl = text.size();
		const std::string  line = text.substr(pos, nl - pos);
		pos                     = nl + 1;
		unsigned long long a = 0, b = 0, off = 0, i = 0;
		unsigned           ma = 0, mi = 0;
		char               perms[8] = {};
		if (std::sscanf(line.c_str(), "%llx-%llx %7s %llx %x:%x %llu", &a, &b, perms, &off, &ma, &mi, &i) != 7) continue;
		if (ma != maj || mi != min || i != ino || b <= a) continue;
		out.push_back({a, b - a, off});
	}
	return out;
}
// Every address range that shows a part of the file range [off, off + len): f(va, bytes).
template <typename F> inline void for_va(const std::vector<MapLine>& maps, uint64_t off, uint64_t len, F&& f) {
	for (const auto& m: maps) {
		const uint64_t lo = off > m.off ? off : m.off;
		const uint64_t hi = off + len < m.off + m.len ? off + len : m.off + m.len;
		if (lo < hi) f(m.va + (lo - m.off), hi - lo);
	}
}
inline bool any_soft_dirty(const uint64_t* entries, size_t n) {
	for (size_t i = 0; i < n; i++) {
		if (((entries[i] >> 55u) & 1u) != 0) return true;
	}
	return false;
}
} // namespace wc412
static std::mutex         g_ww_mutex;
static std::set<uint64_t> g_ww_named; // file chunk offsets of direct memory that a hint, a force or a packet operand has named
static void ww412_name(uint64_t choff) {
	if (!ww412::on()) return;
	std::lock_guard lk(g_ww_mutex);
	g_ww_named.insert(choff);
}
static std::map<std::string, std::vector<uint8_t>> g_ww_prev;      // tag ww412: each heap's flags at its last scan; only the scan thread, one scan at a time
static std::map<std::string, uint64_t>             g_ww_prev_base; // ... and its base then
static std::vector<wc412::MapLine>                 g_wc_maps;      // tag wc412: the direct file's mappings, read at this scan's start
static std::set<uint64_t>                          g_wc_before;    // slots (file offsets) that had a soft-dirty page before this scan's clear
static int                                         g_wc_pm = -1;   // /proc/self/pagemap
static int                                         g_wc_ok = 0;    // 0 not tried, 1 the soft-dirty bit works, -1 not available
static bool wc412_va_dirty(uint64_t va, uint64_t bytes) {
	const uint64_t        first = va / 4096, n = (va + bytes + 4095) / 4096 - first;
	std::vector<uint64_t> e(n);
	const ssize_t         r = pread(g_wc_pm, e.data(), n * 8, static_cast<off_t>(first * 8));
	return r > 0 && wc412::any_soft_dirty(e.data(), static_cast<size_t>(r) / 8);
}
static bool wc412_dirty(uint64_t off) { // a soft-dirty page at any address that maps the slot [off, off + kDChunk) of the direct file
	bool d = false;
	wc412::for_va(g_wc_maps, off, kDChunk, [&d](uint64_t va, uint64_t bytes) { d = d || wc412_va_dirty(va, bytes); });
	return d;
}
// At a scan's start, before the scan reads the file: the bits of every slot that was zero at the last scan, then the clear.
static void wc412_begin(int fd, uint32_t k) {
	if (wc412::level() < 2 || g_wc_ok < 0) return;
	const double t0 = timing_now();
	if (g_wc_pm < 0) g_wc_pm = open("/proc/self/pagemap", O_RDONLY | O_CLOEXEC);
	struct stat st {};
	std::string text;
	if (std::ifstream in("/proc/self/maps"); in) text.assign(std::istreambuf_iterator<char>(in), std::istreambuf_iterator<char>());
	if (g_wc_pm >= 0 && fstat(fd, &st) == 0) g_wc_maps = wc412::parse_maps(text, major(st.st_dev), minor(st.st_dev), st.st_ino);
	else g_wc_maps.clear();
	static char* probe = static_cast<char*>(mmap(nullptr, 4096, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0));
	if (g_wc_maps.empty() || probe == MAP_FAILED) {
		g_wc_ok = -1;
		journal("writers (exp 0412, tag wc412): scan %u: the CPU/GPU split is NOT available (pagemap %d, %zu mappings of the direct file found in /proc/self/maps): the catcher goes on without it\n", k, g_wc_pm, g_wc_maps.size());
		return;
	}
	g_wc_before.clear();
	uint64_t looked = 0;
	if (g_wc_ok == 1) {
		for (const auto& [heap, flags]: g_ww_prev) {
			const uint64_t base = g_ww_prev_base[heap];
			for (size_t i = 0; i < flags.size(); i++) {
				if (flags[i] != 1) continue;
				looked++;
				const uint64_t off = base + static_cast<uint64_t>(i) * kDChunk;
				if (wc412_dirty(off)) g_wc_before.insert(off);
			}
		}
	}
	probe[0]         = 1; // the page exists
	const double t1  = timing_now();
	bool         ok  = false;
	if (const int f = open("/proc/self/clear_refs", O_WRONLY | O_CLOEXEC); f >= 0) {
		ok = write(f, "4", 1) == 1;
		close(f);
	}
	const double t2      = timing_now();
	const bool   cleared = ok && !wc412_va_dirty(reinterpret_cast<uint64_t>(probe), 4096);
	probe[0]             = 2;
	const bool set_again = wc412_va_dirty(reinterpret_cast<uint64_t>(probe), 4096);
	if (!cleared || !set_again) {
		g_wc_ok = -1;
		journal("writers (exp 0412, tag wc412): scan %u: the CPU/GPU split is NOT available: the soft-dirty bit does not work here (clear_refs written %d, the probe page clean after the clear %d, dirty after a write %d); the catcher goes on without it\n",
		        k, ok ? 1 : 0, cleared ? 1 : 0, set_again ? 1 : 0);
		return;
	}
	g_wc_ok = 1;
	journal("writers (exp 0412, tag wc412): scan %u: soft-dirty: %zu mappings of the direct file; %" PRIu64 " slots that were zero at the last scan looked at, %zu of them written by the CPU since the last clear; cleared for the whole process in %.1f ms (%.1f ms in all)\n",
	        k, g_wc_maps.size(), looked, g_wc_before.size(), (t2 - t1) * 1000.0, (timing_now() - t0) * 1000.0);
}
// The zero scan's hook (its background thread): one heap's flags of this scan against the last scan's.
static void ww412_scan(const std::string& heap, uint64_t base, const std::vector<uint8_t>& now, uint32_t k) {
	if (!ww412::on()) return;
	auto&          p = g_ww_prev[heap];
	ww412::Turned  t;
	size_t         named_all = 0;
	const bool     compared  = p.size() == now.size() && g_ww_prev_base[heap] == base;
	const bool     split     = compared && wc412::level() >= 2 && g_wc_ok == 1; // tag wc412
	{
		std::lock_guard lk(g_ww_mutex);
		named_all = g_ww_named.size();
		if (compared) t = ww412::classify(p, now, base, kDChunk, split ? now.size() : 8, [](uint64_t g) { return g_ww_named.count(g) != 0; });
	}
	if (compared) {
		uint64_t cpu = 0, gpu = 0, lines = 0;
		for (const uint64_t c: t.unnamed) {
			const bool by_cpu = split && (g_wc_before.count(c) != 0 || wc412_dirty(c));
			if (split) (by_cpu ? cpu : gpu)++;
			if (lines >= (split && !by_cpu ? 64u : 8u)) continue; // a chunk with no CPU write is the finding: up to 64 of them are written
			lines++;
			journal("writers (exp 0412, tag ww412): scan %u: %s: the chunk at file offset 0x%" PRIx64 " was all zero at the last scan and holds data now; no hint, force or packet operand named it%s\n", k, heap.c_str(), c,
			        !split ? "" : by_cpu ? "; the CPU wrote it (soft-dirty)" : "; NO CPU write since the last scan: a GPU writer nobody named");
		}
		journal("writers (exp 0412, tag ww412): scan %u: %s: %" PRIu64 " chunks (%" PRIu64 " MiB) turned non-zero since the last scan: %" PRIu64 " named by a hint, force or packet operand, %" PRIu64
		        " NOT named (upper bound of unknown GPU writers: a CPU write and a chunk that left its view count here too); %zu chunks named so far in all heaps\n",
		        k, heap.c_str(), t.turned, t.turned * (kDChunk >> 20u), t.named, t.turned - t.named, named_all);
		if (split) {
			journal("writers (exp 0412, tag wc412): scan %u: %s: of the %" PRIu64 " NOT named: %" PRIu64 " written by the CPU (soft-dirty; a GPU write as well is not excluded), %" PRIu64 " with NO CPU write (GPU writers nobody named)\n",
			        k, heap.c_str(), t.turned - t.named, cpu, gpu);
		}
	} else {
		journal("writers (exp 0412, tag ww412): scan %u: %s: first scan of this span (%zu slots): nothing to compare yet\n", k, heap.c_str(), now.size());
	}
	p                    = now;
	g_ww_prev_base[heap] = base;
}
// ---- experiment 0379: the zero list (BC5_DIRECT_ZEROSCAN_AT/_OUT) and the skip (BC5_DIRECT_ZERO_SKIP) ---------------
// RenderGpuWcLarge and CommitIABufferAllocator are eager, so every chunk of them is pinned, and exp 0333 found ~2.8 GB
// of them all-zero for 20 minutes (F402); with RT on the box then runs out of page cache (F505). A diagnostic run scans
// the named heaps (BC5_DIRECT_ZERO_NAMES) on a background thread at the given times and writes the chunks that were
// all-zero in every scan (bc5/zero_skip.hpp). A later run leaves those chunks out of the eager import. Each skipped
// run is mapped onto its own 2 MiB slice of one canary BO at every VA that maps it, so a GPU access never faults: a
// read gets zeros, a write shows in the slice, which a background thread checks (one slice per 50 ms), and the run
// is then taken back. A CPU write (SEEK_DATA), a hint window and a device reopen take chunks back too; a learned
// window does not (the learned windows in these heaps predate their eager import, F96). Off unless
// BC5_DIRECT_ZERO_SKIP names a list.
// Exp 0401 series e7 (mkzsk0401.py, zsk0401-notes.md): exp 0379's patch0379-bc5LleAgc.diff carried onto the e6 unit, for
// the memory pressure of the e6 plays. Against 0379's text: BC5_DIRECT_ZERO_SKIP is read as every e-series switch (unset,
// empty and "0" are off, any other value is the list's path); bc5/zero_skip.hpp is inlined at the top of the unit; the
// canary check, the start of a sync and the hint take-back are functions of their own (the same statements), and a
// learned window is marked by a scope guard (ZLearned); a canary hit on a run that hints and CPU writes have already taken
// back in full is retired (0379 kept its flag raised, which forced a full sync at every later call while anything stayed
// skipped); the seams bc5_zsk0401_* at the end serve the CPU test zsk0401.cpp only.
static const std::vector<std::string>& zero_names() {
	static const std::vector<std::string> names = [] {
		std::vector<std::string> v;
		const char*              e = BC5_DIAG_ENV("BC5_DIRECT_ZERO_NAMES");
		std::string              s = e != nullptr ? e : "RenderGpuWcLarge,CommitIABufferAllocator", cur;
		for (const char c: s + ",") {
			if (c == ',') {
				if (!cur.empty()) v.push_back(cur);
				cur.clear();
			} else {
				cur.push_back(c);
			}
		}
		return v;
	}();
	return names;
}
// The file range a named heap's eager views span (the lowest offset and the span), 0 when none is there yet.
static std::pair<uint64_t, uint64_t> zero_heap_span(const std::vector<DView>& views, const std::string& name) {
	uint64_t lo = ~0ull, hi = 0;
	for (const auto& v: views) {
		if (!(v.eager || bd412_name(v.name.c_str())) || v.name != name) continue; // exp 0412 (tag bd412)
		lo = std::min(lo, v.off);
		hi = std::max(hi, v.off + v.size);
	}
	return hi > lo ? std::pair<uint64_t, uint64_t> {lo, hi - lo} : std::pair<uint64_t, uint64_t> {0, 0};
}

// The diagnostic scan (arm S).
struct ZScanHeap {
	std::string                                  name;
	uint64_t                                     base = 0, span = 0;
	std::vector<std::pair<uint64_t, uint64_t>> ranges; // the views' file ranges
};
static std::mutex                                      g_zscan_mutex;
static std::map<std::string, bc5::zero_skip::ZeroMask> g_zscan_masks;
static std::map<std::string, uint64_t>                 g_zscan_spans;
static std::atomic<bool>                               g_zscan_busy {false};
static void zscan_run(int fd, std::vector<ZScanHeap> heaps, double t_start, uint32_t k) {
	setpriority(PRIO_PROCESS, static_cast<id_t>(syscall(SYS_gettid)), 19);
	wc412_begin(fd, k); // exp 0412 (tag wc412)
	const char*         out     = BC5_DIAG_ENV("BC5_DIRECT_ZEROSCAN_OUT");
	const uint64_t      min_mib = BC5_DIAG_ENV("BC5_DIRECT_ZERO_MIN_MIB") != nullptr ? std::strtoull(BC5_DIAG_ENV("BC5_DIRECT_ZERO_MIN_MIB"), nullptr, 10) : 8ull;
	std::vector<char>   buf(kDChunk);
	std::vector<bc5::zero_skip::Heap> list;
	for (const auto& h: heaps) {
		const size_t         n = static_cast<size_t>((h.span + kDChunk - 1) / kDChunk);
		std::vector<uint8_t> now(n, 0);
		uint64_t             zero_now = 0;
		for (size_t i = 0; i < n; i++) {
			const uint64_t c = h.base + static_cast<uint64_t>(i) * kDChunk;
			bool           in = false;
			for (const auto& [a, b]: h.ranges) in = in || (c >= a && c + kDChunk <= b);
			if (!in) continue; // not wholly inside a view: never listed
			const ssize_t r = pread(fd, buf.data(), kDChunk, static_cast<off_t>(c));
			if (r == static_cast<ssize_t>(kDChunk) && bc5::zero_skip::all_zero(buf.data(), kDChunk)) {
				now[i] = 1;
				zero_now += kDChunk;
			}
		}
		ww412_scan(h.name, h.base, now, k); // exp 0412 (tag ww412)
		std::lock_guard lk(g_zscan_mutex);
		if (auto s = g_zscan_spans.find(h.name); s != g_zscan_spans.end() && s->second != h.span) {
			journal("zero scan %u: %s spans 0x%" PRIx64 ", not 0x%" PRIx64 " as before: its mask starts again\n", k, h.name.c_str(), h.span, s->second);
			g_zscan_masks.erase(h.name);
		}
		g_zscan_spans[h.name] = h.span;
		auto& m = g_zscan_masks.try_emplace(h.name, h.span).first->second;
		m.intersect(now);
		bc5::zero_skip::Heap lh {h.name, h.span, m.scans(), m.runs(h.span, min_mib << 20u)};
		uint64_t             listed = 0;
		for (const auto& [o, l]: lh.runs) listed += l;
		journal("zero scan %u at t %.1f s: %s %.1f MiB, zero now %.1f MiB, zero in all %u scans %.1f MiB, listed %.1f MiB in %zu runs of >= %" PRIu64 " MiB (%.0f ms)\n", k,
				t_start, h.name.c_str(), static_cast<double>(h.span) / 1048576.0, static_cast<double>(zero_now) / 1048576.0, m.scans(),
				static_cast<double>(m.zero_bytes()) / 1048576.0, static_cast<double>(listed) / 1048576.0, lh.runs.size(), min_mib, (timing_now() - t_start) * 1000.0);
		list.push_back(std::move(lh));
	}
	if (out != nullptr) {
		const std::string tmp = std::string(out) + ".tmp";
		if (FILE* f = std::fopen(tmp.c_str(), "w")) {
			const std::string text = bc5::zero_skip::format_list(list);
			const bool        ok   = std::fwrite(text.data(), 1, text.size(), f) == text.size();
			if (std::fclose(f) == 0 && ok && std::rename(tmp.c_str(), out) == 0) journal("zero scan %u: list written to %s\n", k, out);
		}
	}
	g_zscan_busy = false;
}
static void zscan_tick(const DState& S, const std::vector<DView>& views) {
	static const std::vector<double> at = [] {
		std::vector<double> v;
		if (const char* e = BC5_DIAG_ENV("BC5_DIRECT_ZEROSCAN_AT"); e != nullptr) {
			for (const char* p = e; *p != 0;) {
				char* end = nullptr;
				const double t = std::strtod(p, &end);
				if (end == p) break;
				v.push_back(t);
				p = *end == ',' ? end + 1 : end;
			}
			std::sort(v.begin(), v.end());
		}
		return v;
	}();
	static size_t   next = 0;
	static uint32_t k    = 0;
	if (S.kind != 0 || next >= at.size() || timing_now() < at[next] || g_zscan_busy) return;
	const double t = timing_now();
	while (next < at.size() && at[next] <= t) next++; // times that passed while a scan ran go to this one
	std::vector<ZScanHeap> heaps;
	for (const auto& name: zero_names()) {
		const auto [base, span] = zero_heap_span(views, name);
		if (span == 0) continue;
		ZScanHeap h {name, base, span, {}};
		for (const auto& v: views) {
			if ((v.eager || bd412_name(v.name.c_str())) && v.name == name) h.ranges.emplace_back(v.off, v.off + v.size); // exp 0412 (tag bd412)
		}
		heaps.push_back(std::move(h));
	}
	const int fd = dstate_fd(S);
	if (heaps.empty() || fd < 0) return;
	g_zscan_busy = true;
	std::thread(zscan_run, fd, std::move(heaps), t, ++k).detach();
}

// The skip (arm B). One thread does the sync, the forcing and the mapping (as the rest of this path); the canary
// thread only reads the slices and raises a run's flag.
static bc5::zero_skip::SkipSet                  g_zskip;
struct ZPiece { uint64_t size; uint32_t run; };
static std::map<uint64_t, ZPiece>               g_zpieces; // canary mappings by VA
static std::set<std::string>                    g_zskip_placed; // list heaps placed or refused
static std::vector<bc5::zero_skip::Heap>        g_zskip_list;
static bool                                     g_zskip_off = false;
static int                                      g_zcanary_fd = -1;
static uint32_t                                 g_zcanary_id = 0;
static const unsigned char*                     g_zcanary_cpu = nullptr;
static std::unique_ptr<std::atomic<uint8_t>[]>  g_zflag; // per run: 0 watched, 1 hit (not yet taken back), 2 done
static size_t                                   g_zruns = 0; // the list's runs: one slice each, whatever order the heaps are placed in
static std::vector<uint64_t>                    g_zleft; // per run: bytes still skipped (0: nothing to look at)
static std::atomic<bool>                        g_zcanary_stop {false};
static uint64_t g_zstat_cpu = 0, g_zstat_hint = 0, g_zstat_hits = 0, g_zstat_placed = 0;
static thread_local bool t_force_learned = false; // direct_force called for a learned window (map_window)
static bool                                     g_zsk_cpu_test = false; // exp 0401 e7: set by zsk0401.cpp only (bc5_zsk0401_reset): a canary with no BO
static const char* zskip_path() {
	static const char* p = nullptr; /* exp 0419: option removed */ // exp 0401 e7: unset, empty and "0" are off (F767)
	return p;
}
// One look at run r's canary slice (exp 0401 e7: the watcher's loop body as 0379 wrote it, in a function of its own).
static void zcanary_check(size_t r) {
	if (g_zflag[r].load() != 0) return;
	const unsigned char* p = g_zcanary_cpu + r * kDChunk;
	// TODO(verify): whether the CPU sees the GPU's writes to an imported udmabuf page without a flush; the
	// lines are flushed first, so a stale cached zero line cannot hide a write.
	for (uint64_t o = 0; o < kDChunk; o += 64) __builtin_ia32_clflush(p + o);
	__builtin_ia32_mfence();
	if (!bc5::zero_skip::all_zero(p, kDChunk)) g_zflag[r] = 1;
}
static void zcanary_watch(size_t runs) {
	setpriority(PRIO_PROCESS, static_cast<id_t>(syscall(SYS_gettid)), 10);
	for (size_t r = 0; !g_zcanary_stop; r = (r + 1) % runs) {
		std::this_thread::sleep_for(std::chrono::milliseconds(50));
		zcanary_check(r);
	}
}
// Unmaps the canary mappings that overlap [lo, hi) (a real mapping is about to go there).
static void zskip_release(uint64_t lo, uint64_t hi) {
	auto it = g_zpieces.lower_bound(lo >= kDChunk ? lo - kDChunk : 0);
	while (it != g_zpieces.end() && it->first < hi) {
		if (it->first + it->second.size > lo) {
			if (g_dev) g_dev->unmap_shared(it->first);
			it = g_zpieces.erase(it);
		} else {
			++it;
		}
	}
}
// Maps the canary under every skipped chunk at every VA a view gives it, where no canary is yet.
static void zskip_map(const std::vector<DView>& views) {
	if (g_zskip.empty() || g_zcanary_id == 0 || !g_dev) return;
	uint32_t added = 0, failed = 0;
	for (const auto& v: views) {
		for (const uint64_t c: g_zskip.chunks_in(v.off, v.off + v.size)) {
			const uint64_t lo = std::max(c, v.off), hi = std::min(c + kDChunk, v.off + v.size);
			if (lo >= hi) continue;
			const uint64_t va = v.va + (lo - v.off);
			if (g_zpieces.count(va) != 0) continue;
			const long run = g_zskip.run_of(c);
			if (run < 0) continue;
			if (g_dev->map_shared(g_zcanary_id, static_cast<uint64_t>(run) * kDChunk + (lo - c), hi - lo, va)) {
				g_zpieces.emplace(va, ZPiece {hi - lo, static_cast<uint32_t>(run)});
				added++;
			} else {
				failed++;
			}
		}
	}
	if (added != 0 || failed != 0) journal("zero skip: canary +%u mappings (%zu)%s\n", added, g_zpieces.size(), failed != 0 ? "; SOME CANARY MAPS FAILED" : "");
}
// Places the list's heaps once their views are there (same span as in the list), before their first import.
static bool zskip_resolve(const std::vector<DView>& views) {
	if (zskip_path() == nullptr || g_zskip_off || g_zskip_placed.size() == g_zskip_list.size() + 1) return false;
	if (g_zskip_placed.empty()) { // first call: load the list
		g_zskip_placed.insert(""); // the marker that the list was read
		std::string text;
		if (FILE* f = std::fopen(zskip_path(), "r")) {
			char   b[4096];
			size_t n = 0;
			while ((n = std::fread(b, 1, sizeof b, f)) > 0) text.append(b, n);
			std::fclose(f);
		}
		uint32_t bad = 0;
		g_zskip_list = bc5::zero_skip::parse_list(text, &bad);
		uint64_t total = 0;
		for (const auto& h: g_zskip_list) {
			for (const auto& [o, l]: h.runs) total += l;
		}
		journal("zero skip: list %s, %zu heaps, %.1f MiB listed, %u bad lines\n", zskip_path(), g_zskip_list.size(), static_cast<double>(total) / 1048576.0, bad);
	}
	bool placed = false;
	for (const auto& h: g_zskip_list) {
		if (g_zskip_placed.count(h.name) != 0) continue;
		const auto [base, span] = zero_heap_span(views, h.name);
		if (span == 0) continue; // not there yet
		g_zskip_placed.insert(h.name);
		if (span != h.size) {
			journal("zero skip: %s spans 0x%" PRIx64 ", the list says 0x%" PRIx64 ": not skipped\n", h.name.c_str(), span, h.size);
			continue;
		}
		if (g_zskip.run_count() + h.runs.size() > (g_zruns != 0 ? g_zruns : ~size_t {0})) { journal("zero skip: %s: no canary slice left: not skipped\n", h.name.c_str()); continue; }
		const uint64_t n = bc5::zero_skip::place(h, base, &g_zskip);
		g_zstat_placed += n;
		placed = true;
		journal("zero skip: %s at file 0x%" PRIx64 ": %.1f MiB in %zu runs skipped\n", h.name.c_str(), base, static_cast<double>(n) / 1048576.0, h.runs.size());
	}
	if (!placed) return false;
	// The canary: one memfd BO with one 2 MiB slice for each run of the list, made at the first placement (add_run
	// numbers the runs in placement order, so every placed run has a slice).
	if (g_zcanary_id == 0 && g_zcanary_fd < 0) {
		g_zruns = 0;
		for (const auto& h: g_zskip_list) g_zruns += h.runs.size();
		const uint64_t size = static_cast<uint64_t>(g_zruns) * kDChunk;
		g_zcanary_fd = memfd_create("bc5-zero-canary", MFD_CLOEXEC | MFD_ALLOW_SEALING);
		void* cpu = MAP_FAILED;
		if (g_zcanary_fd >= 0 && ftruncate(g_zcanary_fd, static_cast<off_t>(size)) == 0 && fcntl(g_zcanary_fd, F_ADD_SEALS, F_SEAL_SHRINK) == 0) {
			cpu = mmap(nullptr, size, PROT_READ, MAP_SHARED, g_zcanary_fd, 0);
		}
		g_zcanary_id = cpu != MAP_FAILED && g_dev ? g_dev->import_memfd(g_zcanary_fd, 0, size) : (cpu != MAP_FAILED && g_zsk_cpu_test ? 1u : 0u); // exp 0401 e7: zsk0401.cpp's canary has no BO
		if (g_zcanary_id == 0) {
			journal("zero skip: the canary BO (%zu runs) could not be made: nothing skipped\n", g_zruns);
			g_zskip.clear();
			g_zskip_off = true;
			return false;
		}
		g_zcanary_cpu = static_cast<const unsigned char*>(cpu);
		g_zflag.reset(new std::atomic<uint8_t>[g_zruns]);
		g_zleft.assign(g_zruns, 0);
		for (size_t r = 0; r < g_zruns; r++) g_zflag[r] = 0;
		std::thread(zcanary_watch, g_zruns).detach();
		journal("zero skip: canary BO %u, %zu slices of 2 MiB\n", g_zcanary_id, g_zruns);
	}
	for (size_t r = 0; r < g_zskip.run_count() && r < g_zleft.size(); r++) {
		if (g_zleft[r] == 0 && g_zflag[r].load() == 0) g_zleft[r] = g_zskip.run_left(static_cast<uint32_t>(r));
	}
	return true;
}
// Takes back the chunks of skipped runs the CPU has written (SEEK_DATA) and the runs whose canary was hit.
static void zskip_take_back(DState& S, int fd) {
	if (S.kind != 0 || g_zskip.empty()) return;
	for (size_t r = 0; r < g_zskip.run_count() && r < g_zruns; r++) {
		if (g_zflag[r].load() != 1) continue;
		if (g_zleft[r] == 0) { // exp 0401 e7: hints and CPU writes took the whole run back already: the hit is retired
			g_zflag[r] = 2;
			const auto [o, l] = g_zskip.run(static_cast<uint32_t>(r));
			journal("zero skip: canary hit in run %zu (file 0x%" PRIx64 " +%.1f MiB) after all of it was taken back: nothing to take\n", r, o, static_cast<double>(l) / 1048576.0);
			continue;
		}
		g_zflag[r] = 2;
		const auto     [o, l] = g_zskip.run(static_cast<uint32_t>(r));
		const uint64_t n      = g_zskip.erase_run(static_cast<uint32_t>(r));
		g_zleft[r]            = 0;
		g_zstat_hits++;
		S.blocks = ~0ull;
		journal("zero skip: canary hit in run %zu (file 0x%" PRIx64 " +%.1f MiB): %.1f MiB taken back\n", r, o, static_cast<double>(l) / 1048576.0, static_cast<double>(n) / 1048576.0);
	}
	for (size_t r = 0; r < g_zskip.run_count() && r < g_zleft.size(); r++) {
		if (g_zleft[r] == 0) continue;
		const auto [o, l] = g_zskip.run(static_cast<uint32_t>(r));
		for (uint64_t pos = o; pos < o + l;) {
			const off_t d = lseek(fd, static_cast<off_t>(pos), SEEK_DATA);
			if (d < 0 || static_cast<uint64_t>(d) >= o + l) break;
			const uint64_t c = static_cast<uint64_t>(d) & ~(kDChunk - 1);
			if (g_zskip.run_of(c) == static_cast<long>(r) && g_zskip.erase_chunk(c)) {
				g_zstat_cpu++;
				g_zleft[r] -= kDChunk;
			}
			pos = c + kDChunk;
		}
	}
}
static void zskip_report() {
	static double last = 0.0;
	if (zskip_path() == nullptr || g_zskip_placed.empty() || timing_now() - last < 60.0) return;
	last = timing_now();
	journal("zero skip: %.1f MiB still skipped of %.1f placed; taken back: %" PRIu64 " chunks by CPU writes, %" PRIu64 " by hints, %" PRIu64 " runs by canary hits; %zu canary mappings%s\n",
			static_cast<double>(g_zskip.bytes()) / 1048576.0, static_cast<double>(g_zstat_placed) / 1048576.0, g_zstat_cpu, g_zstat_hint, g_zstat_hits, g_zpieces.size(),
			g_zskip_off ? "; OFF" : "");
}
// After a device reopen the canary BO and its mappings are gone: the skip ends and everything is imported.
static void zskip_disable(const char* why) {
	if (zskip_path() == nullptr) return;
	g_zcanary_stop = true;
	g_zskip.clear();
	g_zpieces.clear();
	g_zcanary_id = 0;
	g_zskip_off  = true;
	journal("zero skip: off (%s)\n", why);
}
// Experiment 0379, in direct_force: a hint window (a render target, a user-data pointer) takes a skipped chunk back; a
// learned window (map_window, under ZLearned) does not. True when chunk c left the skip set; direct_force then counts the
// chunk as asked for, as 0379's "|| back" did (exp 0401 e7: 0379's statements, in a function of their own).
static bool zskip_hint_back(DState& S, uint64_t c) {
	if (S.kind != 0 || t_force_learned || g_zskip.empty()) return false;
	const long run = g_zskip.run_of(c);
	if (run < 0 || !g_zskip.erase_chunk(c)) return false;
	g_zstat_hint++;
	if (static_cast<size_t>(run) < g_zleft.size()) g_zleft[static_cast<size_t>(run)] -= kDChunk;
	S.blocks = ~0ull;
	return true;
}
// Experiment 0379, in map_window: direct_force for a learned window leaves skipped chunks skipped (exp 0401 e7: a scope
// guard instead of 0379's set, call, reset around the call, so map_window's own lines stay as they are).
struct ZLearned {
	explicit ZLearned(bool learned) { t_force_learned = learned; }
	~ZLearned() { t_force_learned = false; }
	ZLearned(const ZLearned&)            = delete;
	ZLearned& operator=(const ZLearned&) = delete;
};
// Experiment 0379, at the start of direct_sync_one: places the zero list before the heaps' first import; a canary hit
// forces a full sync. True when a heap was placed just now (exp 0401 e7: 0379's lines, in a function of their own).
static bool zskip_sync_start(DState& S, const std::vector<DView>& views) {
	const bool zskip_new = S.kind == 0 && zskip_resolve(views);
	if (S.kind == 0) {
		zscan_tick(S, views);
		zskip_report();
		for (size_t r = 0; r < g_zskip.run_count() && r < g_zruns && !g_zskip.empty(); r++) {
			if (g_zflag[r].load() == 1) S.blocks = ~0ull;
		}
		if (zskip_new) S.blocks = ~0ull;
	}
	return zskip_new;
}

// ---- exp 0401 series e7: the seams of the CPU test zsk0401.cpp (always compiled in, never called by the emulator) ------
// The list's pure parts (bc5::zero_skip) run on the seams' own skip set; the skip's steps run on this session's state,
// with no device: bc5_zsk0401_reset(1) lets zskip_resolve make its canary memfd without a BO (g_zsk_cpu_test), and the
// canary watcher then runs as in a session. Nothing is reset once a canary watcher reads the slices.
static bc5::zero_skip::SkipSet g_zsk_test_set; // bc5_zsk0401_set's and bc5_zsk0401_place_set's own, never the session's
extern "C" int bc5_zsk0401_switch(char* path, size_t cap) {
	const char* p = zskip_path();
	if (p != nullptr && path != nullptr && cap != 0) std::snprintf(path, cap, "%s", p);
	return p != nullptr ? 1 : 0;
}
// parse_list, then format_list of what it kept, into out (cap bytes). The heaps kept; *bad: the lines dropped.
extern "C" uint32_t bc5_zsk0401_list(const char* text, char* out, size_t cap, uint32_t* bad) {
	const std::vector<bc5::zero_skip::Heap> heaps = bc5::zero_skip::parse_list(text != nullptr ? text : "", bad);
	if (out != nullptr && cap != 0) std::snprintf(out, cap, "%s", bc5::zero_skip::format_list(heaps).c_str());
	return static_cast<uint32_t>(heaps.size());
}
// A ZeroMask of heap_size given n_scans scans one after another (scan k: lens[k] entries, 1 = all zero now). info: chunks,
// scans, zero bytes; runs: up to cap (offset, length) pairs of runs(heap_size, min_bytes). The runs it gives.
extern "C" size_t bc5_zsk0401_mask(uint64_t heap_size, const uint8_t* scans, const size_t* lens, size_t n_scans, uint64_t min_bytes, uint64_t* info, uint64_t* runs, size_t cap) {
	bc5::zero_skip::ZeroMask m(heap_size);
	size_t                   at = 0;
	for (size_t k = 0; k < n_scans; k++) {
		m.intersect(std::vector<uint8_t>(scans + at, scans + at + lens[k]));
		at += lens[k];
	}
	const auto r = m.runs(heap_size, min_bytes);
	info[0]      = m.chunks();
	info[1]      = m.scans();
	info[2]      = m.zero_bytes();
	for (size_t i = 0; i < r.size() && i < cap; i++) {
		runs[2 * i]     = r[i].first;
		runs[2 * i + 1] = r[i].second;
	}
	return r.size();
}
extern "C" int bc5_zsk0401_all_zero(const void* p, size_t n) {
	return bc5::zero_skip::all_zero(p, n) ? 1 : 0;
}
// The seams' own skip set: 0 clear, 1 add_run(a, b) (its index), 2 contains(a), 3 run_of(a) + 1 (0: none), 4 bytes,
// 5 run_count, 6 run_left(a), 7 erase_chunk(a), 8 erase_run(a), 9 chunks_in(a, b)'s size, 10 its element k (~0: none),
// 11 empty.
extern "C" uint64_t bc5_zsk0401_set(int op, uint64_t a, uint64_t b, uint64_t k) {
	auto& s = g_zsk_test_set;
	switch (op) {
	case 0: s.clear(); return 0;
	case 1: return s.add_run(a, b);
	case 2: return s.contains(a) ? 1 : 0;
	case 3: return static_cast<uint64_t>(s.run_of(a) + 1);
	case 4: return s.bytes();
	case 5: return s.run_count();
	case 6: return s.run_left(static_cast<uint32_t>(a));
	case 7: return s.erase_chunk(a) ? 1 : 0;
	case 8: return s.erase_run(static_cast<uint32_t>(a));
	case 9: return s.chunks_in(a, b).size();
	case 10: {
		const std::vector<uint64_t> v = s.chunks_in(a, b);
		return k < v.size() ? v[k] : ~0ull;
	}
	case 11: return s.empty() ? 1 : 0;
	default: return ~0ull;
	}
}
// Every heap of the list `text` placed at file offset base into the seams' own set (bc5::zero_skip::place): bytes added.
extern "C" uint64_t bc5_zsk0401_place_set(const char* text, uint64_t base) {
	uint64_t n = 0;
	for (const auto& h: bc5::zero_skip::parse_list(text != nullptr ? text : "")) n += bc5::zero_skip::place(h, base, &g_zsk_test_set);
	return n;
}
// This session's skip: 0 bytes still skipped, 1 runs placed, 2 the list's runs (canary slices), 3 the canary BO id, 4 off,
// 5 heaps read from the list, 6 bytes placed, 7 chunks taken back by hints, 8 by CPU writes, 9 runs by canary hits,
// 10 canary mappings, 11 the watcher told to stop, 12 contains(a), 13 run_of(a) + 1 (0: none), 14 g_zleft[a] (~0: none),
// 15 g_zflag[a] (255: none), 16 t_force_learned on this thread, 17 the canary memfd + 1 (0: none), 18 heaps placed or
// refused.
extern "C" uint64_t bc5_zsk0401_state(int what, uint64_t a) {
	switch (what) {
	case 0: return g_zskip.bytes();
	case 1: return g_zskip.run_count();
	case 2: return g_zruns;
	case 3: return g_zcanary_id;
	case 4: return g_zskip_off ? 1 : 0;
	case 5: return g_zskip_list.size();
	case 6: return g_zstat_placed;
	case 7: return g_zstat_hint;
	case 8: return g_zstat_cpu;
	case 9: return g_zstat_hits;
	case 10: return g_zpieces.size();
	case 11: return g_zcanary_stop.load() ? 1 : 0;
	case 12: return g_zskip.contains(a) ? 1 : 0;
	case 13: return static_cast<uint64_t>(g_zskip.run_of(a) + 1);
	case 14: return a < g_zleft.size() ? g_zleft[a] : ~0ull;
	case 15: return g_zflag != nullptr && a < g_zruns ? static_cast<uint64_t>(g_zflag[a].load()) : uint64_t {255};
	case 16: return t_force_learned ? 1 : 0;
	case 17: return static_cast<uint64_t>(g_zcanary_fd + 1);
	case 18: return g_zskip_placed.empty() ? size_t {0} : g_zskip_placed.size() - 1; // without the "list read" marker
	default: return ~0ull;
	}
}
// Clears this session's skip as it was at the start (the list is read again at the next zskip_resolve); cpu_canary 1 lets
// zskip_resolve make its canary without a device. -1, and nothing cleared, once a canary watcher runs.
extern "C" int bc5_zsk0401_reset(int cpu_canary) {
	if (g_zcanary_cpu != nullptr) return -1;
	g_zskip.clear();
	g_zpieces.clear();
	g_zskip_placed.clear();
	g_zskip_list.clear();
	g_zskip_off = false;
	if (g_zcanary_fd >= 0) close(g_zcanary_fd);
	g_zcanary_fd = -1;
	g_zcanary_id = 0;
	g_zflag.reset();
	g_zruns = 0;
	g_zleft.clear();
	g_zstat_cpu = g_zstat_hint = g_zstat_hits = g_zstat_placed = 0;
	g_zsk_cpu_test = cpu_canary != 0;
	return 0;
}
// n views of direct memory: names[i] at file offset offs[i], sizes[i] bytes, eager[i], at va 0x10000000000 + offs[i].
static std::vector<DView> zsk_views(const char* const* names, const uint64_t* offs, const uint64_t* sizes, const int* eager, size_t n) {
	std::vector<DView> v;
	for (size_t i = 0; i < n; i++) v.push_back(DView {0x10000000000ull + offs[i], sizes[i], offs[i], names[i], false, eager[i] != 0});
	return v;
}
// A state of this kind (0 direct memory, 1 private memory) with this st_blocks mark.
static DState zsk_state(int kind, uint64_t blocks) {
	DState S {};
	S.kind   = kind;
	S.label  = kind == 0 ? "direct" : "private";
	S.blocks = blocks;
	return S;
}
// zskip_sync_start over those views; *blocks: the state's mark before and after. 1 when a heap was placed just now.
extern "C" int bc5_zsk0401_sync_start(int kind, const char* const* names, const uint64_t* offs, const uint64_t* sizes, const int* eager, size_t n, uint64_t* blocks) {
	DState     S = zsk_state(kind, *blocks);
	const bool r = zskip_sync_start(S, zsk_views(names, offs, sizes, eager, n));
	*blocks      = S.blocks;
	return r ? 1 : 0;
}
// zskip_hint_back for chunk c, as direct_force calls it for a hint window (learned 0) or, under map_window's guard, for a
// learned window (learned 1). 1 when the chunk left the skip set.
extern "C" int bc5_zsk0401_hint(int kind, uint64_t c, int learned, uint64_t* blocks) {
	DState S    = zsk_state(kind, *blocks);
	bool   back = false;
	{
		const ZLearned guard(learned != 0);
		back = zskip_hint_back(S, c);
	}
	*blocks = S.blocks;
	return back ? 1 : 0;
}
// zskip_take_back over the direct-memory file fd.
extern "C" void bc5_zsk0401_take_back(int kind, int fd, uint64_t* blocks) {
	DState S = zsk_state(kind, *blocks);
	zskip_take_back(S, fd);
	*blocks = S.blocks;
}
// A canary mapping at va (size bytes, run `run`) when size is not 0, then zskip_release(lo, hi) when hi > lo: the
// mappings left.
extern "C" size_t bc5_zsk0401_pieces(uint64_t va, uint64_t size, uint32_t run, uint64_t lo, uint64_t hi) {
	if (size != 0) g_zpieces.emplace(va, ZPiece {size, run});
	if (hi > lo) zskip_release(lo, hi);
	return g_zpieces.size();
}
extern "C" void bc5_zsk0401_disable() {
	zskip_disable("exp 0401 zsk0401.cpp");
}
// ---- end of experiment 0379's zero skip (exp 0401 e7) -------------------------------------------------------------------

static void guard0412_imported(int kind, int fd, uint64_t off, uint64_t size); // exp 0412 (tag g412)
static void guard0412_cap(DState& S, const std::vector<DView>& views, std::vector<uint64_t>& need); // exp 0412 (tag g412b)
static bool guard0412_cap_changed(const DState& S);
static void guard0412_want(const DState& S, const std::vector<DView>& views, std::vector<DMap>& want);
static void guard0412_synced(const DState& S);
static void guard0412_after_cuts(size_t cuts); // exp 0412 (tag g412c)
static void aliases_apply(bool force);
// BC5 experiment 0412 (tag k1r412, README sections 62 and 63; design section 8): the read-only zero cover.
// ON by default since 2026-11-13 (the top's order after the maintainer's play); BC5_GUARD_K1R=0 turns it off. Every part of a view of direct
// memory that no imported buffer covers (a chunk the CPU has never written, in a heap that is imported by data or
// lazily) is GPU-mapped READABLE ONLY onto one shared 2 MiB zero buffer of its own. Nothing is pinned for it.
//   - a GPU READ there returns zeros, which is what the file holds there (E1 case 2; his play of 2026-11-13 faulted on
//     exactly such a read);
//   - a GPU WRITE there is a named page fault (E1 case 4): the job is lost and the catcher names the address as its own
//     kind; nothing can be written into the shared zero buffer, so nothing is aliased through it (the zero skip's
//     defect, section 48, is excluded by the mapping's missing write bit, not by a watcher);
//   - an address under NO view gets nothing: it stays unmapped and loud;
//   - when the CPU writes the chunk, the import's SEEK_DATA pass sees data, the chunk is imported and the same mapping
//     rebuild drops the cover and maps the real pages, before the submission that follows the sync reaches the kernel.
//     Ordering relied on: the title writes its data before it submits what reads it, and the sync runs before every
//     submission. A chunk written since the last sync is still zero for the GPU until that sync: for an unimported
//     chunk that was a fault before, never the real data.
// The cover's pieces are computed here, free of the host, and tested by k1r0412.cpp.
namespace k1r412 {
struct Bo {
	uint64_t off, size; // an imported range of the file, chunk aligned; the list is sorted by off and disjoint
};
struct Piece {
	uint64_t va, size; // a GPU mapping of the zero buffer: [va, va + size), size <= chunk, page aligned
	bool     operator==(const Piece& o) const { return va == o.va && size == o.size; }
};
inline bool on() {
	static const bool v = [] {
		const char* e = BC5_DIAG_ENV("BC5_GUARD_K1R");
		return e == nullptr || !(e[0] == '0' && e[1] == 0); // on unless "0"
	}();
	return v;
}
// The parts of the view [voff, voff + vsize) of the file, mapped at vva, that no imported range covers, cut at the
// file's chunk boundaries (so that a piece never exceeds the zero buffer and a chunk's later import replaces whole
// pieces). Appended to out in ascending address order.
// steps, when given, counts the list entries looked at (the CPU test's measure of the pass's cost).
template <typename Bos> inline void cover(uint64_t vva, uint64_t voff, uint64_t vsize, const Bos& bos, uint64_t chunk, std::vector<Piece>& out, uint64_t* steps = nullptr) {
	const uint64_t vend = voff + vsize;
	uint64_t       cur  = voff;
	auto           emit = [&](uint64_t lo, uint64_t hi) { // a gap [lo, hi) of the file under the view
		while (lo < hi) {
			const uint64_t stop = ((lo / chunk) + 1) * chunk;
			const uint64_t e    = stop < hi ? stop : hi;
			out.push_back({vva + (lo - voff), e - lo});
			lo = e;
		}
	};
	// Start at the last range that begins at or before the view's start (the list is sorted and disjoint, so nothing
	// before it can reach into the view). 2026-11-13: the walk from the list's start for each of 21,000 views cost
	// 20 ms a rebuild and a 1 s stall in the menu (README section 78).
	auto first = std::upper_bound(bos.begin(), bos.end(), cur, [](uint64_t o, const auto& b) { return o < b.off; });
	if (first != bos.begin()) --first;
	for (auto it = first; it != bos.end(); ++it) {
		const auto& b = *it;
		if (steps != nullptr) ++*steps;
		if (b.off + b.size <= cur) continue;
		if (b.off >= vend) break;
		if (b.off > cur) emit(cur, b.off < vend ? b.off : vend);
		if (b.off + b.size > cur) cur = b.off + b.size;
		if (cur >= vend) break;
	}
	if (cur < vend) emit(cur, vend);
}
// The fault status' write bit, read off two kernel lines (E1 case 4: status 0x00741041, "RW: 0x1"; the play of
// 2026-11-13: 0x00601431, "RW: 0x0"): bit 18. TODO(verify) against the gfx10 register header; the raw status is
// always journaled beside it.
inline bool status_write(uint32_t status) { return (status & (1u << 18u)) != 0; }
} // namespace k1r412
// Experiment 0412 (tag k1r412): BC5_GUARD_K1R, the host's part of the read-only zero cover (k1r0412.inc).
static int            g_k1r_fd  = -1;
static uint32_t       g_k1r_id  = 0;       // the zero buffer's import on the open device (0 after a reopen)
static const uint8_t* g_k1r_cpu = nullptr; // a read-only CPU view of it, for the "still zero" check
static uint32_t k1r412_bo() {
	if (g_k1r_id != 0 || !g_dev) return g_k1r_id;
	if (g_k1r_fd < 0) {
		g_k1r_fd = memfd_create("bc5-k1r-zero", MFD_CLOEXEC | MFD_ALLOW_SEALING);
		if (g_k1r_fd < 0) return 0;
		if (ftruncate(g_k1r_fd, static_cast<off_t>(kDChunk)) != 0 || fcntl(g_k1r_fd, F_ADD_SEALS, F_SEAL_SHRINK) != 0) {
			close(g_k1r_fd);
			g_k1r_fd = -1;
			return 0;
		}
		void* p = mmap(nullptr, kDChunk, PROT_READ, MAP_SHARED, g_k1r_fd, 0);
		g_k1r_cpu = p == MAP_FAILED ? nullptr : static_cast<const uint8_t*>(p);
	}
	g_k1r_id = g_dev->import_memfd(g_k1r_fd, 0, kDChunk);
	return g_k1r_id;
}
static bool k1r412_is_cover(uint32_t id) { return g_k1r_id != 0 && id == g_k1r_id; }
// The add pass: one wanted mapping; a cover is mapped READ-ONLY. (The map-over form, BC5_GUARD_K1R_REPLACE with
// AMDGPU_VA_OP_REPLACE, was removed on 2026-11-13: it ran once, run k1rg, and was never shown faster; README section 77.)
static bool k1r412_map(const DMap& w) {
	return k1r412_is_cover(w.id) ? g_dev->map_shared(w.id, w.bo_off, w.size, w.va, true) : g_dev->map_shared(w.id, w.bo_off, w.size, w.va);
}
// The mapping rebuild's hook: every part of a view of direct memory that no imported buffer covers is one or more
// read-only mappings of the zero buffer. Not with the zero skip or the pin cap (they put their own buffer there).
// Experiment 0412 (tag kl412): kl0412.inc, under a lazy view K1r covers only never-written chunks.
namespace kl412 {
constexpr uint64_t kPeriodNs = 100'000'000ull; // the least time between two scans
struct Known {
	std::set<uint64_t> written;                                         // file chunk offsets that held data at the last scan
	uint64_t           last_ns = 0, scans = 0, asked = 0, scan_ns = 0; // counters for the journal
	bool               scanned = false;
	// A scan is due at the first call and when the period has passed; a due scan forgets the last answer.
	bool begin(uint64_t now_ns, uint64_t period) {
		if (scanned && now_ns - last_ns < period) return false;
		scanned = true;
		last_ns = now_ns;
		scans++;
		written.clear();
		return true;
	}
};
// The pieces of ONE lazy view (mapped at vva, file offset voff; each piece lies inside one chunk): those whose chunk
// holds data are removed, the order of the rest kept. has_data(chunk offset) is asked only during a scan, once per
// chunk. Returns the number removed.
template <typename Piece, typename F> inline uint64_t drop_written(std::vector<Piece>& pieces, uint64_t vva, uint64_t voff, uint64_t chunk, Known& k, bool scan, F&& has_data) {
	uint64_t dropped = 0;
	size_t   w       = 0;
	for (size_t i = 0; i < pieces.size(); i++) {
		const uint64_t choff = ((voff + (pieces[i].va - vva)) / chunk) * chunk;
		bool           wr    = k.written.count(choff) != 0;
		if (!wr && scan) {
			k.asked++;
			if (has_data(choff)) {
				k.written.insert(choff);
				wr = true;
			}
		}
		if (wr) {
			dropped++;
			continue;
		}
		if (w != i) pieces[w] = pieces[i];
		w++;
	}
	pieces.resize(w);
	return dropped;
}
} // namespace kl412
static void k1r412_want(const DState& S, const std::vector<DView>& views, std::vector<DMap>& want, int fd) { // exp 0412 (tag kl412): fd, the direct file
	if (!k1r412::on() || S.kind != 0) return;
	static const bool refused = [] {
		const bool r = false; /* exp 0419: BC5_DIRECT_ZERO_SKIP and BC5_GUARD_PIN_CAP are gone */
		journal("k1r (exp 0412, tag k1r412): BC5_GUARD_K1R on%s: never-written parts of the views of direct memory are GPU-mapped read-only onto one zero buffer; nothing is pinned for them\n",
		        r ? ", but REFUSED because BC5_DIRECT_ZERO_SKIP or BC5_GUARD_PIN_CAP is set (they map their own buffer there)" : "");
		return r;
	}();
	if (refused) return;
	const uint32_t id = k1r412_bo();
	if (id == 0) {
		static bool said = false;
		if (!said) {
			said = true;
			journal("k1r (exp 0412, tag k1r412): no zero buffer: no cover\n");
		}
		return;
	}
	static std::vector<k1r412::Bo>    bos;
	static std::vector<k1r412::Piece> pieces;
	bos.clear();
	for (const auto& b: S.bos) bos.push_back({b.off, b.size});
	uint64_t n = 0, bytes = 0;
	static kl412::Known kl; // exp 0412 (tag kl412)
	uint64_t            kl_dropped = 0;
	const uint64_t      kl_t0      = SoftCp::now_ns();
	const bool          kl_scan    = kl.begin(kl_t0, kl412::kPeriodNs);
	for (const auto& v: views) {
		pieces.clear();
		k1r412::cover(v.va, v.off, v.size, bos, kDChunk, pieces);
		if (v.lazy) { // exp 0412 (tag kl412): a written chunk of a lazy view gets no zero cover
			kl_dropped += kl412::drop_written(pieces, v.va, v.off, kDChunk, kl, kl_scan, [fd](uint64_t choff) {
				const off_t d = lseek(fd, static_cast<off_t>(choff), SEEK_DATA);
				return d >= 0 && static_cast<uint64_t>(d) < choff + kDChunk;
			});
		}
		for (const auto& p: pieces) {
			want.push_back({p.va, p.size, 0, id});
			n++;
			bytes += p.size;
		}
	}
	static uint64_t last_n = ~0ull, last_ns = 0, rebuilds = 0;
	rebuilds++;
	const uint64_t now = SoftCp::now_ns();
	if (kl_scan) kl.scan_ns += now - kl_t0; // exp 0412 (tag kl412): a rebuild's cover pass with its scan
	if (n != last_n && now - last_ns >= 10'000'000'000ull) {
		last_n  = n;
		last_ns = now;
		journal("k1r written chunks (exp 0412, tag kl412): t %.0f s: %" PRIu64 " pieces under lazy views hold data and get NO cover (unmapped; a GPU read there faults by name); %zu chunks known written; %" PRIu64 " scans, %" PRIu64 " SEEK_DATA calls, %.1f ms in all (%.3f ms a scan)\n",
		        timing_now(), kl_dropped, kl.written.size(), kl.scans, kl.asked, static_cast<double>(kl.scan_ns) / 1e6,
		        kl.scans != 0 ? static_cast<double>(kl.scan_ns) / 1e6 / static_cast<double>(kl.scans) : 0.0);
		uint64_t nonzero = 0;
		if (g_k1r_cpu != nullptr) {
			for (uint64_t i = 0; i < kDChunk; i += 8) nonzero += *reinterpret_cast<const uint64_t*>(g_k1r_cpu + i) != 0 ? 1u : 0u;
		}
		journal("k1r (exp 0412, tag k1r412): t %.0f s: %" PRIu64 " read-only zero pieces cover %.1f MiB of never-written memory under %zu views (rebuild %" PRIu64 "); the zero buffer holds %" PRIu64 " non-zero words%s\n",
		        timing_now(), n, static_cast<double>(bytes) / 1048576.0, views.size(), rebuilds, nonzero, nonzero != 0 ? " <-- IT MUST BE ZERO" : "");
	}
}
// Experiment 0412 (tag kc412): kc0412.inc, the cover -> data log.
namespace kc412 {
inline bool on() {
	static const bool v = [] {
		const char* e = BC5_DIAG_ENV("BC5_GUARD_COVER_LOG");
		return e != nullptr && e[0] != 0 && !(e[0] == '0' && e[1] == 0);
	}();
	return v;
}
enum Kind : unsigned { kGone = 0, kData = 1, kCover = 2 };
// A cover piece [va, va + size) is being unmapped. want is the new list of mappings, sorted by va, its entries
// disjoint. kData: a mapping that is not a cover lies over some part of it (the title's data takes its place);
// kCover: only covers do (the piece was cut or joined); kGone: nothing does (its view went away).
template <typename Maps, typename IsCover> inline Kind after(uint64_t va, uint64_t size, const Maps& want, IsCover&& is_cover) {
	auto it = std::upper_bound(want.begin(), want.end(), va, [](uint64_t a, const auto& m) { return a < m.va; });
	if (it != want.begin()) --it;
	Kind k = kGone;
	for (; it != want.end() && it->va < va + size; ++it) {
		if (it->va + it->size <= va) continue;
		if (!is_cover(it->id)) return kData;
		k = kCover;
	}
	return k;
}
struct Tally {
	uint64_t n[3] = {0, 0, 0}, bytes[3] = {0, 0, 0};
	uint64_t first_data_va = 0;
	void     add(Kind k, uint64_t va, uint64_t size) {
		if (k == kData && n[kData] == 0) first_data_va = va;
		n[k]++;
		bytes[k] += size;
	}
};
} // namespace kc412
// Experiment 0412 (tag kc412): BC5_GUARD_COVER_LOG, the host's part. Called by the mapping rebuild only (one thread).
static kc412::Tally g_kc_tally;
static uint64_t     g_kc_total = 0;
static void kc412_dropped(const DMap& m, const std::vector<DMap>& want) {
	if (!kc412::on() || !k1r412_is_cover(m.id)) return;
	g_kc_tally.add(kc412::after(m.va, m.size, want, [](uint32_t id) { return k1r412_is_cover(id); }), m.va, m.size);
}
static void kc412_rebuilt(const std::vector<DView>& views) {
	if (!kc412::on()) return;
	static bool said = false;
	if (!said) {
		said = true;
		journal("cover log (exp 0412, tag kc412): BC5_GUARD_COVER_LOG on, armed: every mapping rebuild in which a K1r cover gives way to the title's data is journaled\n");
	}
	const kc412::Tally& t = g_kc_tally;
	if (t.n[kc412::kData] != 0) {
		const char* name = "no view";
		for (const auto& v: views) {
			if (t.first_data_va >= v.va && t.first_data_va < v.va + v.size) {
				name = v.name.c_str();
				break;
			}
		}
		g_kc_total += t.n[kc412::kData];
		journal("cover log (exp 0412, tag kc412): t %.2f s: %" PRIu64 " cover pieces (%.2f MiB) gave way to the title's data, the first at 0x%" PRIx64 " in %s; %" PRIu64 " re-covered, %" PRIu64 " gone with their view; %" PRIu64 " gave way since the start\n",
		        timing_now(), t.n[kc412::kData], static_cast<double>(t.bytes[kc412::kData]) / 1048576.0, t.first_data_va, name, t.n[kc412::kCover], t.n[kc412::kGone], g_kc_total);
	}
	g_kc_tally = kc412::Tally {};
}
// At a GPU fault: was it under the cover, and was it a write?
static void k1r412_fault(uint64_t fault, uint32_t status, bool under_view, bool chunk_imported) {
	if (!k1r412::on() || !under_view || chunk_imported) return;
	journal("k1r (exp 0412, tag k1r412): fault 0x%" PRIx64 " status 0x%08x under the read-only zero cover: %s\n", fault, status,
	        k1r412::status_write(status) ? "a GPU WRITE (kind K1w): the job is lost; the cure is the import of this write target when the title binds it"
	                                     : "a READ although the cover serves reads: a defect (was the cover mapped at that moment?)");
}
// Experiment 0412 (tag wa412): BC5_GUARD_WATCH, the state of up to four guest addresses in the journal. A catcher.
namespace wa412 {
inline const std::vector<uint64_t>& list() {
	static const std::vector<uint64_t> v = [] {
		std::vector<uint64_t> o;
		const char*           e = BC5_DIAG_ENV("BC5_GUARD_WATCH");
		while (e != nullptr && *e != 0 && o.size() < 4) {
			char*              end = nullptr;
			const uint64_t     a   = std::strtoull(e, &end, 16);
			if (end == e) break;
			o.push_back(a);
			e = (*end == ',') ? end + 1 : end;
			if (*end != ',') break;
		}
		return o;
	}();
	return v;
}
} // namespace wa412
// The state of one address in words (also used by the read probe of mkpr0412.py).
static void wa412_text(const DState& S, const std::vector<DView>& views, int fd, uint64_t addr, char* text, size_t cap) {
	{
		const uint64_t page = addr & ~0xfffull;
		const DView*   v    = nullptr;
		for (const auto& x: views) {
			if (page >= x.va && page < x.va + x.size) {
				v = &x;
				break;
			}
		}
		int n = 0;
		if (v == nullptr) {
			n = std::snprintf(text, cap, "under NO view");
		} else {
			const uint64_t choff    = (v->off + (page - v->va)) & ~(kDChunk - 1);
			const off_t    d        = lseek(fd, static_cast<off_t>(choff), SEEK_DATA);
			const bool     written  = d >= 0 && static_cast<uint64_t>(d) < choff + kDChunk;
			const bool     imported = direct_covered_end(S, choff) != 0;
			n = std::snprintf(text, cap, "under \"%s\" (%s; view 0x%" PRIx64 "+0x%" PRIx64 ", 0x%" PRIx64 " into it; file chunk 0x%" PRIx64 "): the chunk %s by the CPU, %s", v->name.c_str(),
			                  v->eager ? "eager" : (v->lazy ? "lazy" : "by data"), v->va, v->size, page - v->va, choff, written ? "WRITTEN" : "never written", imported ? "IMPORTED" : "not imported");
		}
		auto it = std::upper_bound(S.maps.begin(), S.maps.end(), page, [](uint64_t p, const DMap& m) { return p < m.va; });
		const DMap* m = nullptr;
		if (it != S.maps.begin()) {
			--it;
			if (page < it->va + it->size) m = &*it;
		}
		if (n > 0 && static_cast<size_t>(n) < cap) {
			std::snprintf(text + n, cap - static_cast<size_t>(n), "; GPU: %s", m == nullptr ? "NO MAPPING (a read here faults)" : (k1r412_is_cover(m->id) ? "a read-only zero cover (K1r)" : "the title's memory"));
		}
	}
}
static void wa412_look(const DState& S, const std::vector<DView>& views, int fd) {
	const auto& a = wa412::list();
	if (a.empty() || S.kind != 0) return;
	static uint64_t    last_ns = 0;
	static std::string last[4];
	const uint64_t     now  = SoftCp::now_ns();
	const bool         tick = now - last_ns >= 10'000'000'000ull;
	for (size_t i = 0; i < a.size(); i++) {
		char text[640];
		wa412_text(S, views, fd, a[i], text, sizeof(text));
		const bool changed = last[i] != text;
		if (changed || tick) journal("watch (exp 0412, tag wa412): t %.1f s: 0x%" PRIx64 ": %s%s\n", timing_now(), a[i], text, changed ? "  <-- changed" : "");
		last[i] = text;
	}
	if (tick) last_ns = now;
}
static void direct_sync_one(DState& S, bool force) {
	if (!g_dev) return;
	const uint64_t now = SoftCp::now_ns();
	// Experiment 0037: at most every 50 ms, unless the guest's ranges changed since the last sync
	// (an AMM map or unmap, a new heap): then the GPU must not run on the old mappings for up to
	// 50 ms, reading whatever the old pages hold.
	const uint64_t    ranges_gen  = S.kind == 0 ? vg437_gen() : S.ranges_gen; // exp 0437 (tag vg437)
	if (!force && now - S.sync_ns < 50'000'000ull && ranges_gen == S.ranges_gen) return;
	S.ranges_gen = ranges_gen;
	S.sync_ns = now;
	const int fd = dstate_fd(S);
	if (fd < 0) return;
	if (S.file_size == 0) {
		const off_t e = lseek(fd, 0, SEEK_END);
		S.file_size = e > 0 ? static_cast<uint64_t>(e) : 0;
		journal("%s memory: memfd %d, %.1f MiB; chunks of %" PRIu64 " MiB, BOs up to %" PRIu64 " MiB; GTT %.1f of %.1f MiB in use%s%s\n", S.label, fd,
		        static_cast<double>(S.file_size) / 1048576.0, kDChunk >> 20u, kDMaxBo >> 20u, static_cast<double>(direct_gtt("mem_info_gtt_used")) / 1048576.0,
		        static_cast<double>(direct_gtt("mem_info_gtt_total")) / 1048576.0, std::getenv("BC5_DIRECT_LAZY_NAMES") != nullptr ? "; lazy names: " : "",
		        std::getenv("BC5_DIRECT_LAZY_NAMES") != nullptr ? std::getenv("BC5_DIRECT_LAZY_NAMES") : "");
		if (const char* e = std::getenv("BC5_DIRECT_EAGER_NAMES"); e != nullptr && S.kind == 0) journal("direct memory: eager names: %s\n", e);
		if (const char* e = BC5_DIAG_ENV("BC5_GUARD_BYDATA_NAMES"); e != nullptr && e[0] != 0 && S.kind == 0) journal("direct memory (exp 0412, tag bd412): by data, not whole, though eager by name: %s\n", e);
	}
	const auto               views_p = direct_views(S);
	const std::vector<DView>& views  = views_p->v;
	wa412_look(S, views, fd); // exp 0412 (tag wa412)
	g_dprof_views_ns += SoftCp::now_ns() - now;
	t_fs415_ds[0] += SoftCp::now_ns() - now; // experiment 0415 (fs415d)
	if (bc5::load_stat::on()) bc5::load_stat::add(bc5::load_stat::kDsViews, SoftCp::now_ns() - now); // experiment 0415 (ls415c)
	const uint64_t sig = views_p->sig;
	if (sig != S.views_sig) g_layout_gen++;
	const bool zskip_new = zskip_sync_start(S, views); // experiment 0379 (exp 0401 e7): place the zero list; a canary hit forces a full sync
	{
		struct stat st {};
		const uint64_t blocks = fstat(fd, &st) == 0 ? static_cast<uint64_t>(st.st_blocks) : ~0ull;
		const bool merge_due = now - S.merge_ns > 250'000'000ull;
		if (blocks != ~0ull && blocks == S.blocks && sig == S.views_sig && S.forced.size() == S.forced_seen && S.bos.size() == S.bos_mapped && !merge_due) {
			g_dprof_fast++;
			return; // nothing new in the file, no new view, nothing forced, nothing to merge yet
		}
		g_dprof_full++;
		S.blocks      = blocks;
		S.forced_seen = S.forced.size();
	}

	const uint64_t t_scan0 = SoftCp::now_ns(); // experiment 0169
	zskip_take_back(S, fd); // experiment 0379: CPU writes and canary hits take skipped chunks back
	const bool zskip_on = S.kind == 0 && !g_zskip.empty();
	// 1. chunks to import: data inside a view, and the forced ones
	std::vector<uint64_t> need;
	for (const auto& v: views) {
		if (v.eager || mr412::rule_for(S.kind)) { // BC5_DIRECT_EAGER_NAMES: every chunk of the view; exp 0412 (tag mr412): BC5_GUARD_MAP_RULE, of every view
			for (uint64_t c = v.off & ~(kDChunk - 1); c < v.off + v.size; c += kDChunk) {
				if (zskip_on && g_zskip.contains(c)) continue; // experiment 0379: on the zero list, under the canary
				if (direct_covered_end(S, c) == 0) need.push_back(c);
			}
			continue;
		}
		if (v.lazy) continue; // BC5_DIRECT_LAZY_NAMES: only what is forced
		const uint64_t end = v.off + v.size;
		uint64_t pos = v.off & ~(kDChunk - 1);
		while (pos < end) {
			if (const uint64_t ce = direct_covered_end(S, pos); ce != 0) { pos = ce; continue; }
			const off_t d = lseek(fd, static_cast<off_t>(pos), SEEK_DATA);
			if (d < 0 || static_cast<uint64_t>(d) >= end) break;
			const uint64_t c = static_cast<uint64_t>(d) & ~(kDChunk - 1);
			if (direct_covered_end(S, c) == 0) need.push_back(c);
			pos = c + kDChunk;
		}
	}
	for (const uint64_t c: S.forced) {
		if (zskip_on && g_zskip.contains(c)) continue; // experiment 0379: forced only by a learned window
		if (direct_covered_end(S, c) == 0) need.push_back(c);
	}
	std::sort(need.begin(), need.end());
	need.erase(std::unique(need.begin(), need.end()), need.end());
	guard0412_cap(S, views, need); // exp 0412 (tag g412b): BC5_GUARD_CAP_ACT puts soft chunks over the cap off
	uint32_t imported = 0;
	for (size_t i = 0; i < need.size();) {
		if (S.failed.count(need[i]) != 0 || need[i] + kDChunk > S.file_size) { i++; continue; }
		size_t j = i + 1;
		while (j < need.size() && need[j] == need[j - 1] + kDChunk && need[j] + kDChunk - need[i] <= kDMaxBo && S.failed.count(need[j]) == 0 && need[j] + kDChunk <= S.file_size) j++;
		const uint64_t off = need[i], size = need[j - 1] + kDChunk - need[i];
		const uint32_t id = ls415_import(fd, off, size);
		if (id == 0) {
			journal("%s import 0x%" PRIx64 " +0x%" PRIx64 " FAILED\n", S.label, off, size);
			for (size_t k = i; k < j; k++) S.failed.insert(need[k]);
		} else {
			S.bos.insert(std::upper_bound(S.bos.begin(), S.bos.end(), off, [](uint64_t o, const DBo& b) { return o < b.off; }), DBo {off, size, id, now});
			S.bytes += size;
			guard0412_imported(S.kind, fd, off, size); // exp 0412 (tag g412): the guardian's ledger and BC5_GUARD_MLOCK
			imported++;
		}
		i = j;
	}

	// 1b. Memory is imported as it fills, 2 MiB at a time, so the imports end up many and small
	// (run 100: 1,475 BOs averaging 5 MiB), and every BO costs time in each submission that
	// lists it (experiment 0022). Neighbours that have been there for a while are replaced by
	// one merged import — a bounded amount per call, the old BOs freed after the remap below.
	const uint64_t        t_merge0 = SoftCp::now_ns(); // experiment 0169
	g_dprof_scan_ns += t_merge0 - t_scan0;
	t_fs415_ds[1] += t_merge0 - t_scan0; // experiment 0415 (fs415d)
	if (bc5::load_stat::on()) bc5::load_stat::add(bc5::load_stat::kDsScan, t_merge0 - t_scan0); // experiment 0415 (ls415c)
	std::vector<uint32_t> retired;
	uint32_t              merged = 0;
	// Experiment 0167 (F222): a merge moves every GPU mapping that lies on the merged BOs - an
	// unmap and a map each, on this thread, with the GPU drained first - and the second title's
	// streaming heaps carry thousands of small AMM mappings: one merge pass remapped 7,800-8,100
	// of them and held the game thread for 0.4-0.75 s (the maintainer's session of 12:19, frames
	// at t 169-181 s). The pass now has a budget of mappings to move (512);
	// a run of BOs whose mappings do not fit is left for a
	// later pass, so the per-submission saving of the merge arrives over several frames instead
	// of one stall.
	static constexpr uint32_t merge_map_cap = 512u;
	uint32_t remaps = 0, deferred = 0; // experiment 0167
	if (now - S.merge_ns > 250'000'000ull) {
		S.merge_ns = now;
		constexpr uint64_t settle = 3'000'000'000ull;
		uint64_t           budget = 256ull << 20u;
		std::unordered_map<uint32_t, uint32_t> maps_on_bo; // BO id -> mappings that lie on it
		for (const auto& m: S.maps) maps_on_bo[m.id]++;
		for (size_t i = 0; i < S.bos.size();) {
			size_t   j       = i;
			uint64_t total   = S.bos[i].size;
			bool     settled = now - S.bos[i].t_ns > settle;
			// Experiment 0066: a run is cut at the budget too; with udmabuf allowing 1 GiB the runs grew past
			// the 256 MiB budget and none was merged (run 294: 1,854 BOs of 2 MiB instead of ~150).
			while (j + 1 < S.bos.size() && S.bos[j].off + S.bos[j].size == S.bos[j + 1].off && total + S.bos[j + 1].size <= std::min(kDMaxBo, budget)) {
				j++;
				total += S.bos[j].size;
				settled = settled && now - S.bos[j].t_ns > settle;
			}
			if (j == i || !settled || total > budget || S.merge_failed.count(S.bos[i].off) != 0) {
				i = j + 1;
				continue;
			}
			{ // experiment 0167: the run's mappings must fit the pass's budget
				uint32_t run_maps = 0;
				for (size_t k = i; k <= j; k++) {
					if (auto it = maps_on_bo.find(S.bos[k].id); it != maps_on_bo.end()) run_maps += it->second;
				}
				if (remaps + run_maps > merge_map_cap) {
					deferred++;
					i = j + 1;
					continue;
				}
				remaps += run_maps;
			}
			const uint64_t off = S.bos[i].off;
			const uint32_t id  = ls415_import(fd, off, total);
			if (id == 0) {
				journal("%s merge 0x%" PRIx64 " +0x%" PRIx64 " FAILED\n", S.label, off, total);
				S.merge_failed.insert(off);
				i = j + 1;
				continue;
			}
			for (size_t k = i; k <= j; k++) retired.push_back(S.bos[k].id);
			S.bos.erase(S.bos.begin() + static_cast<std::ptrdiff_t>(i), S.bos.begin() + static_cast<std::ptrdiff_t>(j) + 1);
			S.bos.insert(S.bos.begin() + static_cast<std::ptrdiff_t>(i), DBo {off, total, id, now});
			budget -= total;
			merged++;
			i++;
		}
	}

	// Experiment 0401 series e7 (lzr, BC5_DIRECT_LAZY_RELEASE): released chunks a view covers again are imported here, and
	// once per pass period chunks under no view for the idle time are cut out of their BOs (retired as the merge retires
	// its BOs: the drain below, the rebuild, then free_shared).
	LzrPass lzr = lzr_pass(S, views, sig, fd, now, merged, retired, remaps, merge_map_cap);
	// 2. the views' addresses: every (view, imported range) intersection is one GPU mapping
	const uint64_t t_drain0 = SoftCp::now_ns(); // experiment 0169
	bool           d432_busy = false;           // exp 0432 (tag d432)
	g_dprof_merge_ns += t_drain0 - t_merge0;
	t_fs415_ds[2] += t_drain0 - t_merge0; // experiment 0415 (fs415d)
	if (bc5::load_stat::on()) bc5::load_stat::add(bc5::load_stat::kDsMerge, t_drain0 - t_merge0); // experiment 0415 (ls415c)
	if (!retired.empty() || sig != S.views_sig || guard0412_cap_changed(S) || (k1r412::on() && S.kind == 0 && S.bos.size() != S.bos_mapped)) { // exp 0412 (tag g412b; k1r412: covers are about to be unmapped and replaced)
		d432::g_rebuilds++;
		if (d432::on()) { // exp 0432 (tag d432): no wait; the chain is flushed as wait_jobs() did first
			chain_flush(5);
			d432_busy = !g_dev->wait_idle(0); // a count only: was anything in flight
			if (d432_busy) d432::g_busy++;
		} else {
			wait_jobs(); // mappings are about to go or be replaced
			g_dprof_drains++;
			const uint64_t w = SoftCp::now_ns() - t_drain0;
			d432::g_drains++;
			d432::g_drain_ns += w;
			d432::maxed(d432::g_drain_max_ns, w);
		}
	}
	const uint64_t t_maps0 = SoftCp::now_ns();
	g_dprof_drain_ns += t_maps0 - t_drain0;
	t_fs415_ds[3] += t_maps0 - t_drain0; // experiment 0415 (fs415d)
	if (bc5::load_stat::on()) bc5::load_stat::add(bc5::load_stat::kDsDrain, t_maps0 - t_drain0); // experiment 0415 (ls415c)
	lzr_confirm(S, lzr, retired); // experiment 0401 series e7 (lzr): a cut stands only when every ring is idle after the drain
	uint32_t mapped = 0, unmapped = 0, map_failed = 0;
	if (sig != S.views_sig || S.bos.size() != S.bos_mapped || !retired.empty() || guard0412_cap_changed(S)) { // exp 0412 (tag g412b)
		// exp 0432 (tag x432), BC5_DIRECT_MAPS_DIFF: see mkx432.py. x432_prev is the view list S.maps was made from;
		// x432_plain says that rebuild's wanted list held the views' own mappings only (no zero buffer, no cover).
		static std::shared_ptr<const DViews> x432_prev[2];
		static bool                          x432_plain[2] = {false, false};
		const int                            x432_k        = S.kind == 0 ? 0 : 1;
		bool                                 x432_done     = false, x432_bad = false;
		if (d432::maps_diff() != 0 && retired.empty() && S.bos.size() == S.bos_mapped && !guard0412_cap_changed(S) && !k1r412::on() && g_zskip.empty() && !zskip_new &&
		    x432_plain[x432_k] && x432_prev[x432_k] != nullptr && x432_prev[x432_k]->sig == S.views_sig && x432_prev[x432_k]->sorted && views_p->sorted) {
			const std::vector<DView>&                   ov = x432_prev[x432_k]->v;
			std::vector<std::pair<uint64_t, uint64_t>> iv; // the changed views' address intervals; their starts never fall
			std::vector<const DView*>                  nv; // the changed views of the new list, rising
			const auto put = [&iv](uint64_t a, uint64_t e) {
				if (!iv.empty() && a <= iv.back().second) {
					if (e > iv.back().second) iv.back().second = e;
				} else {
					iv.emplace_back(a, e);
				}
			};
			for (size_t i = 0, j = 0; i < ov.size() || j < views.size();) {
				if (i < ov.size() && j < views.size() && ov[i].va == views[j].va && ov[i].size == views[j].size && ov[i].off == views[j].off) {
					i++;
					j++;
				} else if (j >= views.size() || (i < ov.size() && ov[i].va < views[j].va)) {
					put(ov[i].va, ov[i].va + ov[i].size);
					i++;
				} else if (i >= ov.size() || views[j].va < ov[i].va) {
					put(views[j].va, views[j].va + views[j].size);
					nv.push_back(&views[j]);
					j++;
				} else { // the same address, another size or offset
					put(ov[i].va, ov[i].va + ov[i].size);
					put(views[j].va, views[j].va + views[j].size);
					nv.push_back(&views[j]);
					i++;
					j++;
				}
			}
			const auto x432_want = [&S](const DView& v, std::vector<DMap>& out) {
				const uint64_t vend = v.off + v.size;
				auto it = std::upper_bound(S.bos.begin(), S.bos.end(), v.off, [](uint64_t o, const DBo& b) { return o < b.off; });
				if (it != S.bos.begin()) --it;
				for (; it != S.bos.end() && it->off < vend; ++it) {
					const uint64_t lo = it->off > v.off ? it->off : v.off;
					const uint64_t hi = it->off + it->size < vend ? it->off + it->size : vend;
					if (lo >= hi) continue;
					out.push_back({v.va + (lo - v.off), hi - lo, lo - it->off, it->id});
				}
			};
			std::vector<DMap> want; // of the changed new views only; rising
			for (const DView* v: nv) x432_want(*v, want);
			std::vector<DMap> next;
			next.reserve(S.maps.size() + want.size());
			size_t q = 0, wk = 0;
			for (const auto& m: S.maps) { // drop before adding (addresses get reused)
				while (q < iv.size() && iv[q].second <= m.va) q++;
				if (q >= iv.size() || m.va < iv[q].first) {
					next.push_back(m); // under an unchanged view
					continue;
				}
				while (wk < want.size() && want[wk].va < m.va) wk++;
				if (wk < want.size() && want[wk] == m) {
					next.push_back(m);
				} else {
					g_dev->unmap_shared(m.va);
					unmapped++;
				}
			}
			std::vector<DMap> added;
			{
				size_t k = 0;
				for (const auto& w: want) {
					while (k < next.size() && next[k].va < w.va) k++;
					if (k < next.size() && next[k] == w) continue;
					if (!g_scratch.empty()) scratch_release(w.va, w.va + w.size);
					if (!g_zpieces.empty()) zskip_release(w.va, w.va + w.size);
					if (g_dev->map_shared(w.id, w.bo_off, w.size, w.va)) {
						added.push_back(w);
						mapped++;
					} else {
						map_failed++;
					}
				}
			}
			if (!added.empty()) {
				std::vector<DMap> merged_maps;
				merged_maps.reserve(next.size() + added.size());
				std::merge(next.begin(), next.end(), added.begin(), added.end(), std::back_inserter(merged_maps), [](const DMap& a, const DMap& b) { return a.va < b.va; });
				next.swap(merged_maps);
			}
			S.maps.swap(next);
			d432::g_x_diff++;
			d432::g_x_views += nv.size();
			if (d432::maps_diff() == 2 && map_failed == 0) { // the whole list the old way, compared
				std::vector<DMap> all;
				all.reserve(S.maps.size());
				for (const auto& v: views) x432_want(v, all);
				size_t at = 0;
				while (at < all.size() && at < S.maps.size() && all[at] == S.maps[at]) at++;
				if (at != all.size() || at != S.maps.size()) {
					x432_bad = true;
					d432::g_x_mismatch++;
					static int logged = 0;
					if (logged++ < 8) {
						journal("exp 0432 (tag x432): MISMATCH: the mappings by diff (%zu) and the old rebuild's list (%zu) differ at index %zu; %zu views changed; the next sync rebuilds the old way\n",
						        S.maps.size(), all.size(), at, nv.size());
					}
				}
			}
			x432_done = true;
		}
		if (!x432_done) {
		d432::g_x_full++;
		if (d432::maps_diff() != 0) { // result 7: X was never taken and nothing said why
			const bool x432_c[11] = {!retired.empty(), S.bos.size() != S.bos_mapped, guard0412_cap_changed(S), k1r412::on(), !g_zskip.empty(), zskip_new, !x432_plain[x432_k],
			                         x432_prev[x432_k] == nullptr, x432_prev[x432_k] != nullptr && x432_prev[x432_k]->sig != S.views_sig,
			                         x432_prev[x432_k] != nullptr && !x432_prev[x432_k]->sorted, !views_p->sorted};
			for (int x432_i = 0; x432_i < 11; x432_i++) {
				if (x432_c[x432_i]) {
					d432::g_x_why[x432_i]++;
					break;
				}
			}
		}
		std::vector<DMap> want;
		for (const auto& v: views) {
			const uint64_t vend = v.off + v.size;
			auto it = std::upper_bound(S.bos.begin(), S.bos.end(), v.off, [](uint64_t o, const DBo& b) { return o < b.off; });
			if (it != S.bos.begin()) --it;
			for (; it != S.bos.end() && it->off < vend; ++it) {
				const uint64_t lo = it->off > v.off ? it->off : v.off;
				const uint64_t hi = it->off + it->size < vend ? it->off + it->size : vend;
				if (lo >= hi) continue;
				want.push_back({v.va + (lo - v.off), hi - lo, lo - it->off, it->id});
			}
		}
		const size_t m432_n1 = want.size(); // exp 0432 (tag m432): the views' own mappings end here
		guard0412_want(S, views, want); // exp 0412 (tag g412b): the zero buffer under the views of put-off chunks
		k1r412_want(S, views, want, fd); // exp 0412 (tag k1r412; kl412: fd)
		// exp 0432 (tag m432), BC5_DIRECT_MAPS_FAST: the list is two runs that are nearly always in order already (the views'
		// mappings, then the covers); they are merged instead of sorted when each run is strictly rising, and the result is
		// taken only if it is strictly rising too (then it is the one order a sort can give). Otherwise the old sort.
		const auto m432_less = [](const DMap& a, const DMap& b) { return a.va < b.va; };
		const auto m432_rising = [&want](size_t from, size_t to) {
			for (size_t i = from + 1; i < to; i++) {
				if (want[i - 1].va >= want[i].va) return false;
			}
			return true;
		};
		bool m432_fast = d432::maps_fast() && m432_rising(0, m432_n1) && m432_rising(m432_n1, want.size());
		if (m432_fast) {
			std::inplace_merge(want.begin(), want.begin() + static_cast<std::ptrdiff_t>(m432_n1), want.end(), m432_less);
			m432_fast = m432_rising(0, want.size());
		}
		if (!m432_fast) std::sort(want.begin(), want.end(), m432_less);
		(m432_fast ? d432::g_maps_fast : d432::g_maps_sorted)++;
		const uint64_t    t_want = SoftCp::now_ns(); // experiment 0169
		g_dprof_want_ns += t_want - t_maps0;
		std::vector<DMap> next;
		next.reserve(want.size());
		size_t   m432_k    = 0; // exp 0432 (tag m432)
		uint64_t m432_prev = 0;
		for (const auto& m: S.maps) { // drop what no view asks for any more, before adding (addresses get reused)
			// exp 0432 (tag m432): both lists rise by address, so the place of m in `want` only moves forward; a step back in
			// S.maps (never seen) takes the old search
			auto w = want.end();
			if (m432_fast && m.va >= m432_prev) {
				while (m432_k < want.size() && want[m432_k].va < m.va) m432_k++;
				w = want.begin() + static_cast<std::ptrdiff_t>(m432_k);
			} else {
				w = std::lower_bound(want.begin(), want.end(), m.va, [](const DMap& a, uint64_t va) { return a.va < va; });
				m432_k = static_cast<size_t>(w - want.begin());
			}
			m432_prev = m.va;
			if (w != want.end() && *w == m) {
				next.push_back(m);
			} else {
				kc412_dropped(m, want); // exp 0412 (tag kc412)
				g_dev->unmap_shared(m.va);
				unmapped++;
			}
		}
		kc412_rebuilt(views); // exp 0412 (tag kc412)
		const uint64_t t_drop = SoftCp::now_ns(); // experiment 0169
		g_dprof_drop_ns += t_drop - t_want;
		// Experiment 0169: the zero pieces are released only for the mappings about to be added. A
		// zero piece is never under a kept mapping (scratch_fill fills holes between mappings), so
		// the old pass over every wanted mapping (~17,000) against every piece found nothing new and
		// cost ~25 ms per rebuild on the game thread - most of the second title's slow frames.
		// The new mappings are collected first and merged into `next` in one pass (inserting each
		// into the sorted vector was quadratic as well).
		std::vector<DMap> added;
		uint64_t          scratch_ns = 0;
		{
			size_t k = 0;
			for (const auto& w: want) {
				while (k < next.size() && next[k].va < w.va) k++;
				if (k < next.size() && next[k] == w) continue;
				if (!g_scratch.empty()) {
					const uint64_t ts = SoftCp::now_ns();
					scratch_release(w.va, w.va + w.size);
					scratch_ns += SoftCp::now_ns() - ts;
				}
				if (!g_zpieces.empty()) zskip_release(w.va, w.va + w.size); // experiment 0379
				if (k1r412_map(w)) { // exp 0412 (tag k1r412): a cover is mapped READ-ONLY
					added.push_back(w);
					mapped++;
				} else {
					map_failed++;
				}
			}
		}
		if (!added.empty()) {
			std::vector<DMap> merged_maps;
			merged_maps.reserve(next.size() + added.size());
			std::merge(next.begin(), next.end(), added.begin(), added.end(), std::back_inserter(merged_maps),
			           [](const DMap& a, const DMap& b) { return a.va < b.va; });
			next.swap(merged_maps);
		}
		g_dprof_scratch_ns += scratch_ns;
		g_dprof_add_ns += SoftCp::now_ns() - t_drop - scratch_ns;
		x432_plain[x432_k] = m432_n1 == want.size(); // exp 0432 (tag x432)
		S.maps.swap(next);
		} // exp 0432 (tag x432): the old rebuild ends here
		if (S.kind == 0 && (zskip_new || sig != S.views_sig)) zskip_map(views); // experiment 0379
		S.views_sig  = sig;
		S.bos_mapped = map_failed == 0 ? S.bos.size() : 0; // a failure is retried at the next sync
		x432_prev[x432_k] = views_p; // exp 0432 (tag x432)
		if (x432_bad) { // the next sync takes the old rebuild, which drops and adds until the lists agree
			x432_prev[x432_k].reset();
			S.bos_mapped = 0;
		}
	}
	g_dprof_maps_ns += SoftCp::now_ns() - t_maps0; // experiment 0169
	t_fs415_ds[4] += SoftCp::now_ns() - t_maps0; // experiment 0415 (fs415d)
	if (bc5::load_stat::on()) bc5::load_stat::add(bc5::load_stat::kDsMaps, SoftCp::now_ns() - t_maps0); // experiment 0415 (ls415c)
	if (imported != 0) S.blocks = ~0ull; // pinning may have allocated pages: look once more
	d432::g_unmaps += unmapped; // exp 0432 (tag d432)
	if (d432_busy) {
		d432::g_unmaps_busy += unmapped;
		d432::g_bos_busy += retired.size();
	}
	for (const uint32_t id: retired) g_dev->free_shared(id);
	guard0412_after_cuts(lzr.done.size()); // exp 0412 (tag g412c): BC5_GUARD_SPLIT
	guard0412_synced(S); // exp 0412 (tag g412b): the ledger's view of what is imported
	if (merged != 0 || deferred != 0) {
		journal("%s merge: %zu BOs became %u (%zu BOs now), %u mappings moved, %u runs deferred by the mapping budget\n", S.label, retired.size(), merged, S.bos.size(),
		        remaps, deferred);
	}
	if (imported != 0 || mapped != 0 || unmapped != 0 || map_failed != 0) {
		journal("%s: %zu views; +%u BOs (%zu, %.1f MiB pinned); maps +%u -%u (%zu)%s\n", S.label, views.size(), imported, S.bos.size(), static_cast<double>(S.bytes) / 1048576.0,
		        mapped, unmapped, S.maps.size(), map_failed != 0 ? "; SOME MAPS FAILED" : "");
	}
	// Experiment 0051: the breakdown walks every view of the memfd with SEEK_DATA/SEEK_HOLE (11,000
	// views, aliases included, over 9 GiB): 25-80 s on the game's thread each time the second
	// title's imports grew by 512 MiB while it loads. A diagnostic now, BC5_DIRECT_BREAKDOWN=1;
	// the breakdown on -ENOMEM stays.
	static const bool breakdown = BC5_DIAG_ENV("BC5_DIRECT_BREAKDOWN") != nullptr;
	if (S.bytes >= S.reported + (512ull << 20u)) {
		S.reported = S.bytes;
		if (breakdown) direct_breakdown_one(S, "growth", 0);
	}
}

static void direct_sync(bool force) {
	bc5::load_stat::Scope ls_scope(bc5::load_stat::kDirectSync); // experiment 0415 (ls415)
	for (auto& S: g_d) direct_sync_one(S, force);
}

// A guest address window the GPU will touch whether or not the CPU ever wrote it (render
// targets, learned fault regions): its direct-memory part is imported now. Returns the bytes
// newly asked for.
// Experiment 0156: a pass over the 95 learned windows (learned_apply, on every layout change)
// asked direct_views for each window, and while the title mapped pages at one a millisecond every
// call found a new generation and rebuilt the 7,000 views: 191 rebuilds and 20-65 ms per pass, 6 s
// in the second title's first six seconds. The pass pins the views it starts with; a view that
// appears meanwhile is covered by the next pass.
static thread_local std::shared_ptr<const DViews> t_pinned_views[2];

static uint64_t direct_force(uint64_t lo, uint64_t hi) {
	if (!g_dev) return 0;
	uint64_t asked = 0;
	for (auto& S: g_d) {
		if (dstate_fd(S) < 0) continue;
		uint64_t   here    = 0;
		const auto views_p = t_pinned_views[S.kind == 0 ? 0 : 1] ? t_pinned_views[S.kind == 0 ? 0 : 1] : direct_views(S);
		const auto& views  = views_p->v;
		// Sorted views: start at the first one that ends after lo (experiment 0037).
		size_t first = 0;
		if (views_p->sorted) {
			first = static_cast<size_t>(std::partition_point(views.begin(), views.end(), [lo](const DView& v) { return v.va + v.size <= lo; }) - views.begin());
		}
		for (size_t vi = first; vi < views.size(); vi++) {
			const auto& v = views[vi];
			if (views_p->sorted && v.va >= hi) break;
			const uint64_t a = lo > v.va ? lo : v.va;
			const uint64_t b = hi < v.va + v.size ? hi : v.va + v.size;
			if (a >= b) continue;
			for (uint64_t c = (v.off + (a - v.va)) & ~(kDChunk - 1); c < v.off + (b - v.va); c += kDChunk) {
				ww412_name(c); // exp 0412 (tag ww412): a hint or force names this chunk
				if (zskip_hint_back(S, c) && S.forced.count(c) != 0) here += kDChunk; // experiment 0379: a hint takes a skipped chunk back (with the next line: 0379's "|| back")
				if (S.forced.insert(c).second) here += kDChunk;
			}
		}
		if (here != 0) direct_sync_one(S, true);
		asked += here;
	}
	return asked;
}

// Experiment 0415 (tag as415), stage S5 of experiments/0415-load-times-fps/DESIGN-lock-side.md, KYTY_BC5_ANON_SYNC
// (default off). Build L5b measured sync_mappings at 11-16 ms of each frame over 50 ms, under the device mutex; with
// private guest memory in a file it is expected to find no anonymous VMA at all, and its cost is the read of
// /proc/self/maps (tens of thousands of lines).
//   "verify": the walk runs as before. A thread of its own (bc5-anonchk) reads /proc/self/maps with the same rule every
//             KYTY_BC5_ANON_SYNC_MS (1,000 when unset; an urgent call wakes it, at most every 50 ms) under no lock of
//             the direct path. Each walk is held against what "thread" would have done: anon_needed counts walks that
//             found a VMA, a changed list or a mapping to add or drop; anon_miss those of them "thread" would have left
//             out.
//   "thread": the submission path leaves the walk out while the thread's last pass saw what the last walk saw: the same
//             VMAs and the same resident runs (bc5/anon_sync.hpp, the signature and can_skip); an urgent call wakes the
//             thread. The walk after -EFAULT always runs, and so does the first one after a device reopen. With pages in
//             swap the walk counts swapped pages as resident and the thread does not: the signatures then differ and
//             the walk runs as before.
// What "thread" gives up: an anonymous guest VMA that appears is walked at the first call after the thread's next pass
// instead of at once for an urgent call (operands on it are dropped by the filter until then, as they are today for a
// non-urgent call for up to a second). So it stays off until "verify" shows no miss.
//   "events" (tag as415c, DESIGN-lock-side.md section 8): no thread and no read on a schedule. The host's map and
//             protect sites count the calls that can make anonymous memory readable in the guest's span
//             (bc5::anon_sync::note). A call here walks at once, whatever the time limits say, when that counter has
//             moved since the last walk read it, after -EFAULT and after a device reopen; it leaves the walk out when
//             the counter has not moved and the last walk found no anonymous guest VMA; while such a VMA exists the
//             walk keeps its old timing (its pages become resident without any call). "verify" counts what this rule
//             would have missed (anon_ev_miss) and how often the counter moves (anon_events).
static std::mutex              g_as415_mu;
static std::condition_variable g_as415_cv;
static uint64_t                g_as415_sig    = 0;     // the thread's last pass: its signature
static uint64_t                g_as415_walk_sig   = 0; // the last walk's signature (the submission path, under the device mutex)
static bool                    g_as415_walk_valid = false;
static uint64_t                g_as415_walk_ev    = 0; // as415c: the map/protect counter as the last walk read it (before its read of the maps)
static uint64_t                g_as415_passes = 0;     // passes finished
static bool                    g_as415_kick   = false; // an urgent call asks for a pass now

static int as415_mode() {
	static const int mode = d432::anon_events() ? 3 : (bc5::anon_sync::mode_of(BC5_DIAG_ENV("KYTY_BC5_ANON_SYNC")) != 0 ? 1 : 0); // exp 0419 phase 2: verify only; exp 0432 (tag a432): BC5_DIRECT_ANON_EVENTS is "events"
	return mode;
}

static void anon_vmas_read(std::vector<Vma>* vmas) {
	std::ifstream maps("/proc/self/maps");
	std::string   line;
	while (std::getline(maps, line)) {
		uint64_t start = 0, end = 0;
		bool     readonly = false;
		// r-- and r-x anonymous pages (the executable's segments after the loader's
		// mprotect) hold shader code and rodata: the first draw of step (d) faulted in the
		// SQC on 0x908e86000, 8 KiB past the last rw run (experiment 0016, run 27).
		if (bc5::anon_sync::parse_line(line.c_str(), &start, &end, &readonly)) vmas->push_back({start, end, readonly});
	}
}

static void as415_thread() {
	pthread_setname_np(pthread_self(), "bc5-anonchk");
	const auto period = std::chrono::milliseconds(BC5_LEAN_OR(1000, bc5::load_stat::env_num("KYTY_BC5_ANON_SYNC_MS", 1000, 60'000)));
	for (;;) {
		const uint64_t   t0 = SoftCp::now_ns();
		std::vector<Vma> vmas;
		anon_vmas_read(&vmas);
		uint64_t                   sig = bc5::anon_sync::kSigEmpty;
		std::vector<unsigned char> vec;
		for (const auto& v: vmas) {
			sig = bc5::anon_sync::sig_vma(sig, v.start, v.end, v.readonly);
			const size_t pages = static_cast<size_t>((v.end - v.start) / 4096);
			vec.assign(pages, 0);
			if (mincore(reinterpret_cast<void*>(v.start), v.end - v.start, vec.data()) != 0) continue;
			sig = bc5::anon_sync::sig_runs(sig, v.start, v.end, vec.data(), pages);
		}
		bc5::load_stat::add(bc5::load_stat::kAnonThread, SoftCp::now_ns() - t0, vmas.size());
		{
			std::unique_lock lk(g_as415_mu);
			g_as415_sig = sig;
			g_as415_passes++;
			g_as415_kick = false;
			g_as415_cv.wait_for(lk, period, [] { return g_as415_kick; });
		}
		std::this_thread::sleep_for(std::chrono::milliseconds(50)); // a kicked pass is at least 50 ms after the last
	}
}

// exp 0432 (tag w432): see mkt432.py, item W
static std::atomic<bool>     g_w432_found {false};
static std::atomic<uint64_t> g_w432_passes {0};
static void w432_thread() {
	pthread_setname_np(pthread_self(), "bc5-anonchk");
	for (;;) {
		std::this_thread::sleep_for(std::chrono::milliseconds(1000));
		std::vector<Vma> vmas;
		anon_vmas_read(&vmas);
		g_w432_passes++;
		if (!vmas.empty()) g_w432_found.store(true, std::memory_order_release);
	}
}

// force: before a submission whose shaders may read memory the filter does not see. With the
// direct memory on the dma-buf path (ADR 0006) what is left here are the anonymous VMAs (module
// data, stacks, flexible memory), walked through /proc/self/maps and mincore — 0.9 ms a call,
// seven calls a frame (experiment 0022). A forced call is therefore skipped when the last walk
// is younger than 100 ms; urgent calls (an
// operand of the IB is unmapped, -EFAULT from a submission) always walk.
static void sync_mappings(bool force = false, bool urgent = false, bool must = false) { // must (exp 0415, as415): after -EFAULT, never left out
	const uint64_t now = SoftCp::now_ns();
	// Experiment 0415 (as415, as415c), KYTY_BC5_ANON_SYNC: see as415_thread.
	const int      as_mode       = as415_mode();
	const uint64_t as_ev         = bc5::anon_sync::events().load(std::memory_order_acquire); // read BEFORE the maps are read
	const bool     as_ev_moved   = bc5::anon_sync::events_moved(as_ev, g_as415_walk_ev, g_as415_walk_valid);
	const bool     as_prev_empty = g_vmas.empty();
	bool           as_ev_now     = false; // "events": this call walks whatever the time limits say
	if (as_mode == 1) { // "verify": how many calls "events" would turn into walks
		static uint64_t seen_ev = 0;
		if (as_ev != seen_ev) {
			seen_ev = as_ev;
		}
	}
	if (as_mode == 3) {
		if (!must && bc5::anon_sync::events_skip(as_ev_moved, as_prev_empty)) {
			if (urgent) bc5::load_stat::count(bc5::load_stat::kAnonUrgent);
			d432::g_anon_skips++; // exp 0432
			t_fs415_ds[7] |= urgent ? 6 : 4;
			return;
		}
		as_ev_now = must || as_ev_moved;
	}
	if (d432::anon_thread() && as_mode != 3 && !urgent && !must) { // exp 0432 (tag w432)
		if (g_w432_found.exchange(false, std::memory_order_acq_rel)) {
			as_ev_now = true; // the thread saw an anonymous guest VMA: walk now, whatever the time limits say
		} else if (g_last_sync_ns != 0 && g_as415_walk_valid && as_prev_empty && Libs::LibKernel::Memory::Bc5PrivateMemoryFd() >= 0) {
			static std::once_flag w432_once;
			std::call_once(w432_once, [] { std::thread(w432_thread).detach(); });
			d432::g_anon_skips++;
			return;
		}
	}
	if (!as_ev_now && !force && now - g_last_sync_ns < 50'000'000ull) { // at most every 50 ms
		return;
	}
	static constexpr uint64_t anon_min_ns = 100ull * 1'000'000ull;
	if (!as_ev_now && force && !urgent && g_last_sync_ns != 0 && now - g_last_sync_ns < anon_min_ns) {
		return;
	}
	// With private guest memory in a file as well (experiment 0023) the walk should find nothing
	// anonymous in the guest's range; it stays as a check, once a second.
	if (!as_ev_now && !urgent && g_last_sync_ns != 0 && Libs::LibKernel::Memory::Bc5PrivateMemoryFd() >= 0 && now - g_last_sync_ns < 1'000'000'000ull) {
		return;
	}
	g_last_sync_ns = now;
	bool as_skip_ok = false;
	if (as_ev_moved) d432::g_anon_ev++; // exp 0432: walks that the map/protect counter asked for
	d432::g_anon_walks++;
	if (urgent) {
		bc5::load_stat::count(bc5::load_stat::kAnonUrgent);
		t_fs415_ds[7] |= 2;
	}
	if (as_mode == 1 || as_mode == 2) { // "events" has no thread
		static std::once_flag once;
		std::call_once(once, [] { std::thread(as415_thread).detach(); });
		std::lock_guard lk(g_as415_mu);
		as_skip_ok = bc5::anon_sync::can_skip(g_as415_passes, g_as415_sig, g_as415_walk_valid, g_as415_walk_sig);
		// KYTY_BC5_ANON_SYNC_KICK=0 (as415b, a measuring knob): urgent calls do not wake the thread, so that with a long
		// KYTY_BC5_ANON_SYNC_MS the cost of the thread's own reads can be told from the rest.
		static const bool kick = BC5_LEAN_OR(true, bc5::load_stat::env_num("KYTY_BC5_ANON_SYNC_KICK", 1, 1) != 0); // exp 0430: a measuring knob, not in lean
		if (urgent && kick && !g_as415_kick) {
			g_as415_kick = true;
			g_as415_cv.notify_one();
		}
	}
	t_fs415_ds[7] |= 1;
	bc5::load_stat::Scope ls_scope(bc5::load_stat::kAnonSync); // experiment 0415 (ls415)
	constexpr uint64_t kPage = 4096, kGrain = 65536;

	// Pass 0: the rw anonymous guest VMAs.
	std::vector<Vma> vmas;
	{
		const uint64_t tr = SoftCp::now_ns();
		anon_vmas_read(&vmas);
		const uint64_t dr = SoftCp::now_ns() - tr;
		t_fs415_ds[6] += dr;
		if (bc5::load_stat::on()) bc5::load_stat::add(bc5::load_stat::kAnonRead, dr, vmas.size());
	}
	const bool as_changed =
	    vmas.size() != g_vmas.size() || !std::equal(vmas.begin(), vmas.end(), g_vmas.begin(), [](const Vma& a, const Vma& b) { return a.start == b.start && a.end == b.end && a.readonly == b.readonly; });
	if (as_changed) {
		g_layout_gen++;
	}
	g_vmas = vmas;
	d432::g_anon_vmas = vmas.size(); // exp 0432
	// exp 0419 phase 2: KYTY_BC5_VMA_FAST is gone; the walk over every VMA, as when it was unset
	auto inside_vma = [&](uint64_t a, uint64_t b, bool readonly) { return bc5::sync_fast::inside_old(vmas, a, b, readonly); };

	// Pass 1: revalidation.
	std::vector<bc5::direct::Mapping> have = g_dev->mappings();
	int removed = 0;
	for (const auto& m: have) {
		if (m.shared) continue; // an imported direct-memory range: direct_sync's business
		if (inside_vma(m.va, m.va + m.size, m.readonly)) continue;
		wait_jobs();
		journal("unmap 0x%" PRIx64 " +0x%" PRIx64 " (no longer %s anonymous) ... ", m.va, m.size, m.readonly ? "r--/r-x" : "rw");
		const bool ok = g_dev->unmap_userptr(m.va);
		journal("%s\n", ok ? "ok" : "FAILED");
		if (ok) {
			g_bytes_mapped -= m.size;
			removed++;
		}
	}
	if (removed != 0) {
		have = g_dev->mappings();
	}

	// Pass 2: addition.
	auto already = [&](uint64_t a, uint64_t b) {
		for (const auto& m: have) {
			if (a >= m.va && b <= m.va + m.size) return true;
		}
		return false;
	};
	std::vector<unsigned char> vec;
	int added = 0;
	uint64_t vma_total = 0, vma_resident = 0;
	uint64_t as_sig = bc5::anon_sync::kSigEmpty; // experiment 0415 (as415)
	for (const auto& v: vmas) {
		const uint64_t start = v.start, end = v.end;
		const size_t pages = static_cast<size_t>((end - start) / kPage);
		vec.assign(pages, 0);
		as_sig = bc5::anon_sync::sig_vma(as_sig, start, end, v.readonly);
		if (mincore(reinterpret_cast<void*>(start), end - start, vec.data()) != 0) {
			continue;
		}
		vma_total += end - start;
		// mincore() reports a page that went to swap (zram on the dev box) as not resident, yet
		// it holds data the CPU wrote: /proc/self/pagemap bit 62 (swapped; Linux
		// Documentation/admin-guide/mm/pagemap.rst) brings those back.
		static const int pagemap_fd = open("/proc/self/pagemap", O_RDONLY | O_CLOEXEC);
		// The pagemap read costs ~40 ms per sync over the guest's 13 GB (run 77: one sync per
		// submission, most of a second per frame), so it runs only while this process has
		// anything in swap (VmSwap in /proc/self/status, re-read at most once a second).
		static uint64_t vmswap_checked_ns = 0;
		static bool     vmswap_nonzero    = false;
		if (pagemap_fd >= 0 && (vmswap_checked_ns == 0 || SoftCp::now_ns() - vmswap_checked_ns > 1'000'000'000ull)) {
			vmswap_checked_ns = SoftCp::now_ns();
			vmswap_nonzero    = false;
			if (FILE* st = std::fopen("/proc/self/status", "r")) {
				char line[256];
				while (std::fgets(line, sizeof(line), st) != nullptr) {
					if (std::strncmp(line, "VmSwap:", 7) == 0) {
						vmswap_nonzero = std::strtoull(line + 7, nullptr, 10) != 0;
						break;
					}
				}
				std::fclose(st);
			}
		}
		if (pagemap_fd >= 0 && vmswap_nonzero) {
			static std::vector<uint64_t> pm;
			const size_t chunk = 1u << 16; // pages per read
			pm.resize(chunk);
			for (size_t k = 0; k < pages; k += chunk) {
				const size_t n = (pages - k) < chunk ? (pages - k) : chunk;
				const ssize_t got = pread(pagemap_fd, pm.data(), n * 8, static_cast<off_t>(((start / kPage) + k) * 8));
				if (got <= 0) break;
				const size_t have_n = static_cast<size_t>(got) / 8;
				for (size_t q = 0; q < have_n; q++) {
					if ((pm[q] >> 62u) & 1u) {
						if ((vec[k + q] & 1) == 0) g_swapped_pages++;
						vec[k + q] |= 1;
					}
				}
			}
		}
		for (size_t k = 0; k < pages; k++) vma_resident += (vec[k] & 1) ? kPage : 0;
		as_sig = bc5::anon_sync::sig_runs(as_sig, start, end, vec.data(), pages); // experiment 0415 (as415): after the swapped pages were added
		// Resident runs at 64 KiB granularity.
		size_t i = 0;
		while (i < pages) {
			while (i < pages && (vec[i] & 1) == 0) i++;
			if (i >= pages) break;
			size_t j = i;
			while (j < pages && (vec[j] & 1) != 0) j++;
			uint64_t a = start + (i * kPage / kGrain) * kGrain;
			uint64_t b = start + ((j * kPage + kGrain - 1) / kGrain) * kGrain;
			if (b > end) b = end;
			if (!already(a, b)) {
				// Map the pieces of [a, b) not covered by an existing mapping (interval
				// subtraction against the mapping list); failures are remembered so the same
				// piece is not retried every 50 ms.
				static std::vector<std::pair<uint64_t, uint64_t>> failed;
				std::vector<std::pair<uint64_t, uint64_t>> pieces = {{a, b}};
				for (const auto& m: have) {
					std::vector<std::pair<uint64_t, uint64_t>> next;
					for (const auto& [pa, pb]: pieces) {
						if (m.va + m.size <= pa || m.va >= pb) { next.emplace_back(pa, pb); continue; }
						if (m.va > pa) next.emplace_back(pa, m.va);
						if (m.va + m.size < pb) next.emplace_back(m.va + m.size, pb);
					}
					pieces.swap(next);
				}
				for (const auto& [pa, pb]: pieces) {
					if (pb <= pa) continue;
					bool known_bad = false;
					for (const auto& [fa, fb]: failed) {
						if (fa == pa && fb == pb) { known_bad = true; break; }
					}
					if (known_bad) continue;
					journal("map%s 0x%" PRIx64 " +0x%" PRIx64 " ... ", v.readonly ? " ro" : "", pa, pb - pa);
					const bool mapped_ok = g_dev->map_userptr(pa, pb - pa, v.readonly);
					journal("%s\n", mapped_ok ? "ok" : "FAILED");
					if (mapped_ok) {
						g_bytes_mapped += pb - pa;
						added++;
						have.push_back({pa, pb - pa});
					} else {
						failed.emplace_back(pa, pb);
					}
				}
			}
			i = j;
		}
	}
	const bool as_same = g_as415_walk_valid && g_as415_walk_sig == as_sig; // experiment 0415 (as415)
	g_as415_walk_sig   = as_sig;
	g_as415_walk_valid = true;
	g_as415_walk_ev    = as_ev;
	if (as_mode != 0 && (as_changed || added != 0 || removed != 0 || !as_same)) {
		bc5::load_stat::count(bc5::load_stat::kAnonNeeded, vmas.size());
		if (as_mode == 1 && !must && bc5::anon_sync::events_skip(as_ev_moved, as_prev_empty)) { // as415c: "events" would have left this walk out
			d432::g_anon_ev_miss++; // exp 0432
			static int ev_logged = 0;
			if (ev_logged++ < 8) {
				journal("anon sync (exp 0415, as415c): EVENT MISS: %zu VMAs, list %s, signature %s, +%d -%d mappings, %s, while the map/protect counter stood at %" PRIu64 " and the list before was empty: a site is not counted\n",
				        vmas.size(), as_changed ? "changed" : "same", as_same ? "same" : "changed", added, removed, urgent ? "urgent" : "not urgent", as_ev);
			}
		}
		if (as_skip_ok) {
			bc5::load_stat::count(bc5::load_stat::kAnonMiss);
			static int logged = 0;
			if (logged++ < 8) {
				journal("anon sync (exp 0415, as415): MISS: %zu VMAs, list %s, signature %s, +%d -%d mappings, %s, while the thread's last pass matched the walk before\n", vmas.size(),
				        as_changed ? "changed" : "same", as_same ? "same" : "changed", added, removed, urgent ? "urgent" : "not urgent");
			}
		}
	}
	if (added != 0 || removed != 0) {
		const double mib = 1024.0 * 1024.0;
		LOGF("[bc5-direct] mappings: +%d -%d, %zu total, %.1f MiB (rw anon VMAs: %zu, %.1f MiB, %.1f MiB resident)\n", added, removed, have.size(), static_cast<double>(g_bytes_mapped.load()) / mib, vmas.size(), static_cast<double>(vma_total) / mib, static_cast<double>(vma_resident) / mib);
		journal("swapped pages taken as resident so far: %" PRIu64 "\n", g_swapped_pages.load());
		journal("vmas %zu total %.1f MiB resident %.1f MiB mapped %.1f MiB\n", vmas.size(), static_cast<double>(vma_total) / mib, static_cast<double>(vma_resident) / mib, static_cast<double>(g_bytes_mapped.load()) / mib);
	}
}

// Render targets and depth buffers are written by the GPU and mostly never touched by the CPU
// (survey, experiment 0016: 52 of 55 CB/DB base addresses in ASTRO BOT's context tables were
// not resident), so the resident-run mapping misses them and the first draw would fault. Before
// a submit, the context registers the IB sets (SET_CONTEXT_REG) or loads (LOAD_CONTEXT_REG_INDEX
// tables, offset/data format) are scanned for the base registers and a window (32 MiB)
// from each base is mapped, clipped to the containing rw VMA. Offsets: Mesa gfx10
// (bc5-agc regdb): CB_COLOR0_BASE mm 0xa318 (+0xf per target), CB_COLOR0_BASE_EXT 0xa390 (+1),
// CMASK 0xa31f / EXT 0xa398, FMASK 0xa321 / EXT 0xa3a0, DCC 0xa325 / EXT 0xa3a8, DB_HTILE_DATA_BASE
// 0xa005 / HI 0xa01e, DB_Z_READ_BASE 0xa012 / HI 0xa01a, DB_STENCIL_READ_BASE 0xa013 / HI 0xa01b,
// DB_Z_WRITE_BASE 0xa014 / HI 0xa01c, DB_STENCIL_WRITE_BASE 0xa015 / HI 0xa01d.
// Experiment 0412 (tag cv412): cover0412.inc, what a K1r cover is to the host (no switch).
namespace cv412 {
// One mapping of the device's list: is it a hole for the host?
inline bool hole(bool shared, bool readonly, bool covers_visible) { return shared && readonly && !covers_visible; }
inline bool hole(bool shared, bool readonly) { return hole(shared, readonly, false); }

// The unit's covered_sorted() with the rule, over any mapping type with va, size, shared, readonly (sorted by va,
// disjoint): the CPU test's model of it.
template <typename M> inline bool covered_sorted(const std::vector<M>& maps, uint64_t a, uint64_t bytes, bool covers_visible) {
	const uint64_t end = a + bytes;
	uint64_t       pos = a;
	for (int guard = 0; pos < end && guard < 64; guard++) {
		auto it = std::upper_bound(maps.begin(), maps.end(), pos, [](uint64_t v, const M& m) { return v < m.va; });
		if (it == maps.begin()) return false;
		--it;
		if (hole(it->shared, it->readonly, covers_visible)) return false;
		if (pos >= it->va + it->size) return false;
		pos = it->va + it->size;
	}
	return pos >= end;
}
} // namespace cv412
static bool covered(const std::vector<bc5::direct::Mapping>& maps, uint64_t a, uint64_t bytes);
// Experiment 0027: the same over a list sorted by address, by binary search — the filter asks
// for every operand of a 25,000-dword buffer, and the linear walk over ~340 mappings was a
// measurable part of prepare.
static bool covered_sorted(const std::vector<bc5::direct::Mapping>& maps, uint64_t a, uint64_t bytes);

// Regions learned from GPU VM faults (BC5_DIRECT_LEARNED, default ~/bc5-work/direct-learned.txt,
// one "0x<addr> 0x<bytes>" per line): mapped like hint windows before every submit. A fault
// under a draw (a texture the CPU never touched) wedges the run; the next run maps the region
// from the start. Written from Direct::submit on a timeout that reports a fault address.
// g_learned: removed with the learned windows // exp 0412 (tag nl412)
// learned_path(): removed with the learned file // exp 0412 (tag nl412)
// learned_load(): removed; no learned file is read // exp 0412 (tag nl412)
// Experiment 0056 (BC5_DIRECT_ALIASES=1): the guest's memory also mapped under a non-zero address
// byte 47:40. The title's faults have a valid address in their low 40 bits and junk above
// (experiment 0055: its programs at 0x11d03xxxxx fetched at 0x8011d03xxxxx) — as if the PS5 GPU
// ignored bits 40-47, TODO(verify). Each (byte, window) from
// ~/bc5-work/direct-aliases-pkg.txt ("byte lo size" in hex per line) is mapped at
// (byte << 40) + address over what is mapped in the window (Device::map_alias), again whenever the
// mappings change (at most once a second); a timeout's fault with such a byte adds its window.
static std::mutex                                        g_alias_mutex;
static std::vector<std::tuple<uint64_t, uint64_t, uint64_t>> g_aliases; // byte, lo, size
static const char* alias_path() {
	static const std::string p = std::string(std::getenv("HOME") ? std::getenv("HOME") : ".") + "/bc5-work/direct-aliases-pkg.txt";
	return p.c_str();
}
static bool aliases_on() {
	static const bool on = bc5::env_on(std::getenv("BC5_DIRECT_ALIASES")); // exp 0419: "=0" and empty are off
	return on;
}
static void aliases_load() {
	static bool done = false;
	if (done) return;
	done = true;
	if (FILE* f = std::fopen(alias_path(), "r")) {
		unsigned long long t = 0, a = 0, n = 0;
		while (std::fscanf(f, "%llx %llx %llx", &t, &a, &n) == 3) g_aliases.emplace_back(t, a, n);
		std::fclose(f);
	}
}
static void aliases_apply(bool force) {
	if (!aliases_on() || !g_dev) return;
	static const void* last_maps = nullptr;
	static double      last_t    = -10.0;
	std::lock_guard lk(g_alias_mutex);
	aliases_load();
	if (g_aliases.empty()) return;
	const auto   maps = g_dev->sorted_mappings();
	const double now  = timing_now();
	if (!force && (maps.get() == last_maps || now - last_t < 1.0)) return;
	last_maps = maps.get();
	last_t    = now;
	g_dev->unmap_aliases();
	uint64_t bytes = 0;
	for (const auto& [t, a, n]: g_aliases) bytes += g_dev->map_alias(a, n, (t << 40u) + a);
	static int reports = 0;
	if (reports++ < 20) journal("aliases: %zu windows, %.1f MiB mapped again under their address bytes\n", g_aliases.size(), static_cast<double>(bytes) / 1048576.0);
}
[[maybe_unused]] static void alias_learn(uint64_t fault_addr) { // exp 0419: not called
	if (!aliases_on()) return;
	if (mr412::learn_log() == 2) return; // exp 0412 (tag mr412): BC5_GUARD_LEARN_LOG=2
	const uint64_t t = fault_addr >> 40u, low = fault_addr & ((1ull << 40u) - 1);
	if (t == 0 || t == 0x10 || low == 0) return; // 0x10: the device's own scratch at 16 TiB
	// Experiment 0195: a fault whose low 40 bits name no guest memory is not a tagged guest address. Session 0808's
	// SQC fault at 0x800000005000 was another process's program address left in COMPUTE_PGM_LO/HI (Mesa's 32-bit
	// shader window: address32_hi 0xffff8000 on the box, COMPUTE_PGM_HI 0x80), and the alias learned for it (0x80
	// over 0x0+0x6000000) mapped guest 0-96 MiB under the byte for every later run.
	if (g_dev && !covered_sorted(*g_dev->sorted_mappings(), low & ~0xfffull, 4)) {
		journal("aliases: fault 0x%" PRIx64 ": no guest memory at 0x%" PRIx64 ", not learned\n", fault_addr, low);
		return;
	}
	const uint64_t lo = (low & ~0x3ffffffull) > 0x2000000ull ? (low & ~0x3ffffffull) - 0x2000000ull : 0;
	const uint64_t n  = 0x6000000ull;
	{
		std::lock_guard lk(g_alias_mutex);
		aliases_load();
		for (const auto& [ta, a, b]: g_aliases) {
			if (ta == t && a == lo && b == n) return;
		}
		g_aliases.emplace_back(t, lo, n);
	}
	if (FILE* f = mr412::learn_log() != 0 ? nullptr : std::fopen(alias_path(), "a")) { // exp 0412 (tag mr412): the catcher writes no file
		std::fprintf(f, "0x%llx 0x%llx 0x%llx\n", static_cast<unsigned long long>(t), static_cast<unsigned long long>(lo), static_cast<unsigned long long>(n));
		std::fclose(f);
	}
	journal("aliases: fault 0x%" PRIx64 " -> byte 0x%" PRIx64 " over 0x%" PRIx64 "+0x%" PRIx64 " (saved)\n", fault_addr, t, lo, n);
}
// Experiment 0401 series e11 (tag m11, mkm110401.py; hang2242-0401.md section 4, the 2026-11-09 22:42 hang): four
// switches, default off; unset, empty and "0" are off (bc5::env_on, F767), each read once.
//   BC5_DIRECT_RESET_REPLAY_ACB     an acb head's GPU marks taken before a device reopen are dropped when the head is used
//                                   again, so the soft CP replays the head's memory side effects (its label writes).
//   BC5_DIRECT_RESET_LABELS         at the reopen, the lost jobs' label writes (exp 0055's list at the timeout) go to guest
//                                   memory: the last write of each label, where memory does not hold it already.
//   BC5_DIRECT_LEARN_GUEST_ONLY     a fault whose learned window holds no guest range is not learned or saved.
//   BC5_DIRECT_RESET_LABEL_JOURNAL  the lost label writes are journaled at the reopen, and 5 s and 30 s later.
// hang2242's switch 5 (STUCK_AFTER_REOPEN) is not in this build (the runner's external stall0409.sh dump stands in), nor
// switch 6 (FAULT_PAGES: the runner keeps every amdgpu fault line of dmesg).
#ifdef BC5_LEAN
static const char* const kM11Names[4] = {"", "", "", ""}; // exp 0419 (build W): the names are not in the lean binary
#else
static const char* const kM11Names[4] = {"BC5_DIRECT_RESET_REPLAY_ACB", "BC5_DIRECT_RESET_LABELS", "BC5_DIRECT_LEARN_GUEST_ONLY", "BC5_DIRECT_RESET_LABEL_JOURNAL"};
#endif
static bool m11_on(int k) {
	static const bool v[4] = {false, false, false,
							  false /* exp 0419: option removed */};
	return k >= 0 && k < 4 && v[k];
}
static void m11_switch_line() {
	static std::atomic<bool> done {false};
	if (done.exchange(true)) return;
	journal("e11: switches: %s %s, %s %s, %s %s, %s %s (exp 0401 e11, tag m11)\n", kM11Names[0], m11_on(0) ? "on" : "off", kM11Names[1], m11_on(1) ? "on" : "off", kM11Names[2],
			m11_on(2) ? "on" : "off", kM11Names[3], m11_on(3) ? "on" : "off");
}
static bool m11_guest_in_real(uint64_t lo, uint64_t hi) {
	std::vector<std::pair<uint64_t, uint64_t>> guest;
	Libs::LibKernel::Memory::Bc5GuestRangesIn(lo, hi, &guest);
	return !guest.empty();
}
static bool (*g_m11_guest_in)(uint64_t lo, uint64_t hi) = m11_guest_in_real; // true when [lo, hi) meets a guest range; the CPU test puts its own here
static std::atomic<uint64_t> g_m11_reopens {0};                                // device reopens so far (m11_after_reopen, every reopen)
// BC5_DIRECT_LEARN_GUEST_ONLY: true when the window [lo, lo + n) that learned_add would save for fault_addr holds no guest range.
static bool m11_learn_refused(uint64_t fault_addr, uint64_t lo, uint64_t n) {
	if (!m11_on(2)) return false;
	m11_switch_line();
	if (g_m11_guest_in(lo, lo + n)) return false;
	journal("e11: fault 0x%" PRIx64 ": no guest range in its window 0x%" PRIx64 "+0x%" PRIx64 ", not learned\n", fault_addr, lo, n);
	return true;
}
// BC5_DIRECT_RESET_REPLAY_ACB: an acb head's marks taken before the last device reopen are dropped, so the soft CP replays them.
static void m11_head_check(std::vector<SoftCp::GpuDone>& marks, uint64_t& reopens, const char* where) {
	if (!m11_on(0)) return;
	const uint64_t now = g_m11_reopens.load();
	if (reopens == now) return;
	m11_switch_line();
	static std::atomic<uint32_t> lines {0};
	if (lines++ < 200) journal("e11: acb head (%s): %zu GPU marks from before reopen %" PRIu64 " dropped, the soft CP replays that part\n", where, marks.size(), now);
	marks.clear();
	reopens = now;
}
// Experiment 0412 (tag mr412): BC5_GUARD_LEARN_LOG. What lay at the address of a GPU fault that would be learned: one
// journal line per fault, the sample the rule's design asks for. Called before the learning, on the thread that learns.
static void mr412_would_learn(uint64_t fault, uint32_t status) {
	if (fault == 0) return; // exp 0412 (tag nl412): always; BC5_GUARD_LEARN_LOG no longer decides
	const bool     junk = (fault >> 40u) != 0;
	const uint64_t page = (junk ? fault & ((1ull << 40u) - 1) : fault) & ~0xfffull;
	std::vector<std::pair<uint64_t, uint64_t>> guest;
	Libs::LibKernel::Memory::Bc5GuestRangesIn(page, page + 0x1000ull, &guest);
	bool        under = false, lazy = false, eager = false, imported = false, forced = false;
	int         kind = -1;
	std::string name;
	for (auto& S: g_d) {
		if (under || dstate_fd(S) < 0) continue;
		const auto views_p = direct_views(S);
		for (const auto& v: views_p->v) {
			if (page < v.va || page >= v.va + v.size) continue;
			const uint64_t c = (v.off + (page - v.va)) & ~(kDChunk - 1);
			under    = true;
			lazy     = v.lazy;
			eager    = v.eager;
			kind     = S.kind;
			name     = v.name;
			imported = direct_covered_end(S, c) != 0;
			forced   = S.forced.count(c) != 0;
			break;
		}
	}
	const bool     mapped = g_dev && covered_sorted(*g_dev->sorted_mappings(), page, 4);
	const uint64_t lo     = (fault & ~0x3ffffffull) > 0x2000000ull ? (fault & ~0x3ffffffull) - 0x2000000ull : 0;
	k1r412_fault(fault, status, under, imported); // exp 0412 (tag k1r412)
	journal("would learn (exp 0412, tag mr412): t %.3f s: fault 0x%" PRIx64 " status 0x%08x: %s; guest range %s; view %s%s%s; chunk %s%s; GPU mapping %s; PRT background %s; the window it would once have learned 0x%" PRIx64 "+0x6000000; nothing is added or written (tag nl412)\n",
	        timing_now(), fault, status, mr412::classify(junk, !guest.empty(), under, lazy, eager, imported, mapped), guest.empty() ? "no" : "yes", under ? name.c_str() : "none",
	        under ? (kind == 0 ? " (direct" : " (private") : "", under ? (eager ? ", eager)" : (lazy ? ", lazy)" : ", by data)")) : "", imported ? "imported" : "not imported", forced ? ", forced" : "",
	        mapped ? "yes" : "no", g_mr412_bg ? "on" : "off", lo);
}
// learned_add(): removed; a GPU fault adds no window and writes no file (mr412_would_learn journals it) // exp 0412 (tag nl412)
// Experiment 0156: the mapping list a learned pass works on stays sorted by address, so
// scratch_fill finds a window's holes in one pass instead of sorting the list per window.
static void have_insert(std::vector<bc5::direct::Mapping>& have, bc5::direct::Mapping m) {
	have.insert(std::upper_bound(have.begin(), have.end(), m, [](const bc5::direct::Mapping& a, const bc5::direct::Mapping& b) { return a.va < b.va; }), m);
}

// map_window(): removed; no window is forced or mapped for a past fault // exp 0412 (tag nl412)
// Experiment 0037: a learned fault window may cover addresses the guest has no range at all in:
// one title's GPU reads up to 24 KiB past the end of a 2.7 GiB heap, and a fault is a 14 s freeze
// and sometimes a stuck game. Such holes get a 2 MiB zero buffer of our own mapped over them (the
// GPU reads zeros, its writes go nowhere); a hole is given back as soon as the guest puts a range
// there (learned_apply checks on every layout change; the direct mapper unmaps before it maps).
static uint32_t                                    g_scratch_id = 0;
static int                                         g_scratch_fd = -1;
static uint32_t scratch_bo() {
	if (g_scratch_id != 0 || !g_dev) return g_scratch_id;
	if (g_scratch_fd < 0) {
		g_scratch_fd = memfd_create("bc5-scratch", MFD_CLOEXEC | MFD_ALLOW_SEALING);
		if (g_scratch_fd < 0) return 0;
		if (ftruncate(g_scratch_fd, static_cast<off_t>(kDChunk)) != 0 || fcntl(g_scratch_fd, F_ADD_SEALS, F_SEAL_SHRINK) != 0) {
			close(g_scratch_fd);
			g_scratch_fd = -1;
			return 0;
		}
	}
	g_scratch_id = g_dev->import_memfd(g_scratch_fd, 0, kDChunk);
	return g_scratch_id;
}
// Unmaps the scratch pieces that overlap [lo, hi).
static void scratch_release(uint64_t lo, uint64_t hi) {
	for (size_t i = 0; i < g_scratch.size();) {
		const auto [va, n] = g_scratch[i];
		if (va < hi && va + n > lo) {
			g_dev->unmap_shared(va);
			g_scratch.erase(g_scratch.begin() + static_cast<std::ptrdiff_t>(i));
		} else {
			i++;
		}
	}
}
static void scratch_fill(uint64_t lo, uint64_t hi, std::vector<bc5::direct::Mapping>& have) {
	if (!g_dev) return;
	if (g_mr412_bg && mr412::in_bg(lo, hi)) return; // exp 0412 (tag mr412): BC5_GUARD_PRT_BG, the hole is PRT already
	constexpr uint64_t kGpuVaEnd = 1ull << 47u; // windows learned from faults at garbage addresses lie beyond it
	if (lo >= kGpuVaEnd) return;
	if (hi > kGpuVaEnd) hi = kGpuVaEnd;
	// Experiment 0156: the holes of [lo, hi) among the mappings, from a sorted walk. Cutting the
	// window by every mapping in turn was quadratic (7,000 mappings, a window split into thousands
	// of pieces by the title's small AMM pages): 1.9 s per 128 submissions while the second title
	// loaded.
	std::vector<std::pair<uint64_t, uint64_t>> pieces;
	{
		uint64_t cur = lo; // `have` is sorted by address (have_insert)
		for (const auto& m: have) {
			if (m.va >= hi) break;
			if (m.va + m.size <= lo) continue;
			if (m.va > cur) pieces.emplace_back(cur, m.va);
			if (m.va + m.size > cur) cur = m.va + m.size;
			if (cur >= hi) break;
		}
		if (cur < hi) pieces.emplace_back(cur, hi);
	}
	auto cut = [&pieces](uint64_t a, uint64_t b) {
		std::vector<std::pair<uint64_t, uint64_t>> next;
		for (const auto& [pa, pb]: pieces) {
			if (b <= pa || a >= pb) { next.emplace_back(pa, pb); continue; }
			if (a > pa) next.emplace_back(pa, a);
			if (b < pb) next.emplace_back(b, pb);
		}
		pieces.swap(next);
	};
	std::vector<std::pair<uint64_t, uint64_t>> guest;
	Libs::LibKernel::Memory::Bc5GuestRangesIn(lo, hi, &guest);
	for (const auto& [a, b]: guest) cut(a, b);
	uint64_t added = 0;
	for (auto [pa, pb]: pieces) {
		pa = (pa + 0xfffull) & ~0xfffull;
		pb &= ~0xfffull;
		while (pa < pb) {
			const uint64_t n  = pb - pa < kDChunk ? pb - pa : kDChunk;
			const uint32_t id = scratch_bo();
			if (id == 0) break;
			if (!g_dev->map_shared(id, 0, n, pa)) {
				// Experiment 0160 (F208): amdgpu refuses a GPU VA below its reserved bottom (the first 64 KiB on
				// recent kernels, amdgpu_vm.h AMDGPU_VA_RESERVED_BOTTOM, TODO(verify) the value of this box's
				// 7.2.8 kernel). The learned window at 0 lost all its zero pages to the one refusal at 0, and
				// the geometry engine's reads of pages 0x0-0x2f000 faulted. Below 2 MiB the piece is retried
				// from the next 64 KiB boundary, so the pages above the reserved bottom read as zero.
				if (pa < 0x200000ull) {
					static std::atomic<uint64_t> n_low {0};
					if ((n_low++ & 0xffu) == 0) journal("scratch: zero page at 0x%" PRIx64 " refused, trying from 0x%" PRIx64 "\n", pa, pa + 0x10000ull);
					pa += 0x10000ull;
					continue;
				}
				break;
			}
			g_scratch.emplace_back(pa, n);
			have_insert(have, {pa, n});
			added += n;
			pa += n;
		}
	}
	if (added != 0) journal("scratch: window 0x%" PRIx64 "+0x%" PRIx64 ", %.1f MiB of holes get a zero buffer\n", lo, hi - lo, static_cast<double>(added) / 1048576.0);
}

// SPDX-License-Identifier: GPL-2.0-only
// Experiment 0412 (tag g412, mkguard0412.py): the memory guardian. The first build's six switches and, since the second
// build (g412b, after the plays of 2026-11-10), BC5_GUARD_CAP_ACT and BC5_GUARD_CAP_NAMES. All default off; unset, empty
// and "0" are off (bc5::env_on, F767), each read once.
//   BC5_GUARD_LEDGER=1             log only: every 10 s what is pinned, per heap name, and what no view covers ("orphans").
//   BC5_GUARD_MLOCK=pinned|guest   pinned: every imported file range is mapped once more, read-only, and mlock()ed, so the
//                                  kernel takes its pages off the reclaim lists (they cannot be freed anyway).
//                                  guest: that, plus mlock2(MLOCK_ONFAULT) on the direct-memory views that are not eager
//                                  (the title's CPU heaps): the guest is not swapped. Needs "ulimit -l unlimited".
//   BC5_GUARD_FILE=random,dontneed with BC5_GUARD_FILE_ROOT=<the game's directory>: open files under it get
//                                  POSIX_FADV_RANDOM (no read-ahead); dontneed drops their page cache under pressure.
//   BC5_GUARD_PSI=<percent>        the pressure threshold (PSI memory "some", avg10) for dontneed and the pressure line;
//                                  10 when dontneed is on and this is unset.
//   BC5_GUARD_PIN_CAP=<MiB>        the cap on what both files have pinned. Alone it only logs: one line each time the pinned
//                                  total passes the cap by 64 MiB more.
//   BC5_GUARD_CAP_ACT=1            the cap acts (needs BC5_GUARD_PIN_CAP): a chunk a sync would import over the cap is put
//                                  off when it is "soft", and every view over it gets the 2 MiB zero buffer instead (the GPU
//                                  reads zeros, its writes are lost), so no access faults. Soft: wanted only for holding data
//                                  or by an eager view whose name is in BC5_GUARD_CAP_NAMES, and not forced by a hint or a
//                                  learned window. Every other chunk is imported as before, cap or not. A put-off chunk is
//                                  imported as soon as the total allows (each full sync asks again).
//   BC5_GUARD_CAP_NAMES=a,b        the eager heaps whose chunks are soft; "AMM" when unset. "-" names none.
//   BC5_GUARD_SPLIT=1              (the third build, g412c) the lazy release (BC5_DIRECT_LAZY_RELEASE, exp 0401 e7) may cut
//                                  orphan chunks out of a BO that keeps other chunks although BC5_DIRECT_ALIASES is set.
//                                  Without it such a BO only goes whole, and with BOs merged up to 1 GiB that is almost
//                                  never (night arm a2orphans: 194 MiB of orphans idle, 0 cut, "3 not split (aliases)").
//                                  The reason for the rule was that freeing the old BO drops its alias mappings until the
//                                  next aliases_apply (at most once a second); with this switch the sync that made cuts
//                                  ends with aliases_apply(true), before any submission can use them.
//   BC5_GUARD_APPLY_MIN_MS=<ms>    learned_apply runs at most once per <ms> (1..1000) while the layout keeps changing; the
//                                  first call after a device reopen is never put off.
//   BC5_GUARD_FORGET=<s>           (the fourth build, g412d) a chunk that a hint or a learned window forced and that has been
//                                  under no view for <s> seconds (1..3600) leaves the forced set, so the lazy release can
//                                  cut it. Night arm z1zscan: 264 MiB "forced and under no view" after 300 s and rising,
//                                  the larger part of the orphans. A chunk under no view has no GPU mapping. A learned
//                                  window forces its chunks again at the next learned_apply once a view is back; a hint
//                                  window does not (it is mapped once), so a view of a heap that is not eager, back at the
//                                  same file range and written only by the GPU, would fault once and be learned.
// With all of them off nothing here runs: no thread, one config read, one early return per import and per submission.
// The text between G412_PURE_BEGIN and G412_PURE_END has no system call and is what test0412.cpp runs on the laptop.
// G412_PURE_BEGIN
namespace g412 {

struct Cfg {
    bool        ledger = false;
    int         mlock = 0; // 0 off, 1 pinned, 2 guest (and pinned)
    bool        f_random = false, f_dontneed = false;
    std::string root;
    double      psi = 0.0;      // percent; 0 = off
    uint64_t    cap = 0;        // bytes; 0 = off
    uint64_t    apply_ns = 0;   // 0 = off
    bool        cap_act = false; // the cap puts soft chunks off
    std::vector<std::string> cap_names; // eager heaps whose chunks are soft
    std::string bad;            // switches whose value was not understood (they stay off)
    bool worker() const { return ledger || mlock != 0 || f_random || f_dontneed || psi > 0.0 || cap != 0; }
};

static Cfg parse(const char* ledger, const char* mlock, const char* file, const char* root, const char* psi, const char* cap, const char* apply,
                 const char* cap_act = nullptr, const char* cap_names = nullptr) {
    Cfg c;
    c.ledger = bc5::env_on(ledger);
    if (bc5::env_on(mlock)) {
        const std::string v = mlock;
        if (v == "pinned" || v == "1") c.mlock = 1;
        else if (v == "guest") c.mlock = 2;
        else c.bad += " BC5_GUARD_MLOCK";
    }
    if (bc5::env_on(file)) {
        std::string v = file;
        bool        ok = true;
        size_t      at = 0;
        while (at <= v.size()) {
            const size_t      e = std::min(v.find(',', at), v.size());
            const std::string w = v.substr(at, e - at);
            if (w == "random") c.f_random = true;
            else if (w == "dontneed") c.f_dontneed = true;
            else ok = false;
            at = e + 1;
        }
        if (root == nullptr || root[0] != '/' || root[1] == 0) ok = false; // a root is required, and "/" is refused
        if (!ok) {
            c.f_random = c.f_dontneed = false;
            c.bad += " BC5_GUARD_FILE";
        } else {
            c.root = root;
            if (c.root.back() != '/') c.root += '/';
        }
    }
    if (bc5::env_on(psi)) {
        char*        end = nullptr;
        const double v = std::strtod(psi, &end);
        if (end != psi && *end == 0 && v > 0.0 && v <= 100.0) c.psi = v;
        else c.bad += " BC5_GUARD_PSI";
    }
    if (c.f_dontneed && c.psi == 0.0) c.psi = 10.0;
    if (bc5::env_on(cap)) {
        char*                    end = nullptr;
        const unsigned long long v = std::strtoull(cap, &end, 10);
        if (end != cap && *end == 0 && v >= 1024 && v <= 65536) c.cap = static_cast<uint64_t>(v) << 20u;
        else c.bad += " BC5_GUARD_PIN_CAP";
    }
    if (bc5::env_on(apply)) {
        char*                    end = nullptr;
        const unsigned long long v = std::strtoull(apply, &end, 10);
        if (end != apply && *end == 0 && v >= 1 && v <= 1000) c.apply_ns = static_cast<uint64_t>(v) * 1'000'000ull;
        else c.bad += " BC5_GUARD_APPLY_MIN_MS";
    }
    if (bc5::env_on(cap_act)) {
        if (c.cap != 0 && std::strcmp(cap_act, "1") == 0) c.cap_act = true;
        else c.bad += " BC5_GUARD_CAP_ACT";
    }
    if (c.cap_act) {
        const std::string v = bc5::env_on(cap_names) ? cap_names : "AMM";
        size_t            at = 0;
        while (at <= v.size()) {
            const size_t      e = std::min(v.find(',', at), v.size());
            const std::string w = v.substr(at, e - at);
            if (!w.empty() && w != "-") c.cap_names.push_back(w);
            at = e + 1;
        }
    }
    return c;
}

static bool cap_name(const Cfg& c, const std::string& name) {
    return std::find(c.cap_names.begin(), c.cap_names.end(), name) != c.cap_names.end();
}

// BC5_GUARD_CAP_ACT: which of the chunks a sync wants are imported. need: the chunk offsets, sorted and unique; soft[i]
// says whether need[i] may be put off; pinned: the bytes both files have pinned now. A hard chunk is always kept. Soft
// chunks are kept in order while the total, with every hard chunk counted first, stays within the cap.
struct CapPlan {
    std::vector<uint64_t> keep, off; // both sorted
    uint64_t              hard = 0;  // hard chunks kept
};
static CapPlan cap_plan(const std::vector<uint64_t>& need, const std::vector<char>& soft, uint64_t pinned, uint64_t cap, uint64_t chunk) {
    CapPlan  p;
    uint64_t total = pinned;
    for (size_t i = 0; i < need.size(); i++) {
        if (i >= soft.size() || soft[i] == 0) total += chunk, p.hard++;
    }
    for (size_t i = 0; i < need.size(); i++) {
        const bool s = i < soft.size() && soft[i] != 0;
        if (!s) {
            p.keep.push_back(need[i]);
        } else if (total + chunk <= cap) {
            total += chunk;
            p.keep.push_back(need[i]);
        } else {
            p.off.push_back(need[i]);
        }
    }
    return p;
}

// A set of disjoint [lo, hi) ranges; touching ranges are joined.
struct Ranges {
    std::map<uint64_t, uint64_t> m;
    uint64_t                     bytes = 0;
    // Adds [lo, hi) and returns the parts that were not in the set yet.
    std::vector<std::pair<uint64_t, uint64_t>> add(uint64_t lo, uint64_t hi) {
        std::vector<std::pair<uint64_t, uint64_t>> fresh;
        if (lo >= hi) return fresh;
        auto it = m.upper_bound(lo);
        if (it != m.begin()) {
            auto p = std::prev(it);
            if (p->second >= lo) it = p;
        }
        uint64_t cur = lo, nlo = lo, nhi = hi;
        while (it != m.end() && it->first <= hi) {
            if (it->first > cur) fresh.emplace_back(cur, it->first);
            cur = std::max(cur, it->second);
            nlo = std::min(nlo, it->first);
            nhi = std::max(nhi, it->second);
            it  = m.erase(it);
        }
        if (cur < hi) fresh.emplace_back(cur, hi);
        m[nlo] = nhi;
        for (const auto& f: fresh) bytes += f.second - f.first;
        return fresh;
    }
    uint64_t overlap(uint64_t lo, uint64_t hi) const {
        uint64_t n = 0;
        auto     it = m.upper_bound(lo);
        if (it != m.begin()) --it;
        for (; it != m.end() && it->first < hi; ++it) {
            const uint64_t a = std::max(lo, it->first), b = std::min(hi, it->second);
            if (b > a) n += b - a;
        }
        return n;
    }
};

struct VIn {
    uint64_t           off, size;
    const std::string* name;
    bool               eager, lazy;
};
struct Row {
    std::string name;
    char        cls = 'D'; // E eager, L lazy, D by data
    uint64_t    reserved = 0, pinned = 0;
    uint32_t    views = 0;
};
struct Ledger {
    std::vector<Row> rows; // by pinned bytes, largest first; views of one name may share file ranges, so rows can sum past the total
    uint64_t         pinned = 0, reserved_union = 0, pinned_under = 0, orphans = 0;
    size_t           views = 0;
};

static Ledger ledger(const std::vector<VIn>& v, const Ranges& pinned) {
    Ledger                                     L;
    std::map<std::string, size_t>              idx;
    std::vector<std::pair<uint64_t, uint64_t>> spans;
    spans.reserve(v.size());
    for (const auto& x: v) {
        if (x.size == 0) continue;
        const char  cls = x.eager ? 'E' : x.lazy ? 'L' : 'D';
        std::string key = *x.name;
        key += cls;
        auto [it, fresh] = idx.try_emplace(key, L.rows.size());
        if (fresh) {
            L.rows.emplace_back();
            L.rows.back().name = x.name->empty() ? "(unnamed)" : *x.name;
            L.rows.back().cls  = cls;
        }
        Row& r = L.rows[it->second];
        r.reserved += x.size;
        r.pinned += pinned.overlap(x.off, x.off + x.size);
        r.views++;
        spans.emplace_back(x.off, x.off + x.size);
        L.views++;
    }
    std::sort(spans.begin(), spans.end());
    uint64_t lo = 0, hi = 0;
    bool     have = false;
    auto     flush = [&] {
        if (!have) return;
        L.reserved_union += hi - lo;
        L.pinned_under += pinned.overlap(lo, hi);
    };
    for (const auto& s: spans) {
        if (have && s.first <= hi) {
            hi = std::max(hi, s.second);
            continue;
        }
        flush();
        lo = s.first, hi = s.second, have = true;
    }
    flush();
    L.pinned  = pinned.bytes;
    L.orphans = L.pinned - L.pinned_under;
    std::stable_sort(L.rows.begin(), L.rows.end(), [](const Row& a, const Row& b) { return a.pinned > b.pinned; });
    return L;
}

// "name[E] pinned/reserved" in whole MiB for the first `top` rows, then the rest as one entry. At most `room` characters.
static std::string heaps_text(const Ledger& L, size_t top, size_t room) {
    std::string out;
    uint64_t    rp = 0, rr = 0;
    size_t      rest = 0;
    for (size_t i = 0; i < L.rows.size(); i++) {
        const Row& r = L.rows[i];
        char       b[96];
        std::snprintf(b, sizeof(b), "%s%.28s[%c] %" PRIu64 "/%" PRIu64, out.empty() ? "" : ", ", r.name.c_str(), r.cls, r.pinned >> 20u, r.reserved >> 20u);
        if (i < top && out.size() + std::strlen(b) + 40 <= room) {
            out += b;
        } else {
            rp += r.pinned, rr += r.reserved, rest++;
        }
    }
    if (rest != 0) {
        char b[96];
        std::snprintf(b, sizeof(b), "%s%zu more %" PRIu64 "/%" PRIu64, out.empty() ? "" : ", ", rest, rp >> 20u, rr >> 20u);
        out += b;
    }
    return out;
}

// /proc/pressure/memory: "some avg10=1.23 ..." and "full avg10=0.45 ...". False when either is missing.
static bool psi_parse(const char* text, double* some10, double* full10) {
    if (text == nullptr) return false;
    const char* s = std::strstr(text, "some avg10=");
    const char* f = std::strstr(text, "full avg10=");
    if (s == nullptr || f == nullptr) return false;
    char*        e1 = nullptr;
    char*        e2 = nullptr;
    const double a = std::strtod(s + 11, &e1), b = std::strtod(f + 11, &e2);
    if (e1 == s + 11 || e2 == f + 11) return false;
    *some10 = a, *full10 = b;
    return true;
}

// "Key:   123 kB" at a line start -> MiB; -1 when the key is missing or has no number (never 0 for "unknown").
static long kv_mib(const char* text, const char* key) {
    if (text == nullptr) return -1;
    const size_t n = std::strlen(key);
    for (const char* p = text; p != nullptr && *p != 0;) {
        if (std::strncmp(p, key, n) == 0 && p[n] == ':') {
            char*           end = nullptr;
            const long long v = std::strtoll(p + n + 1, &end, 10);
            if (end == p + n + 1 || v < 0) return -1;
            return static_cast<long>(v >> 10);
        }
        p = std::strchr(p, '\n');
        if (p != nullptr) p++;
    }
    return -1;
}

// /proc/self/stat: the faults so far (fields 10 and 12, counted after the last ')').
static bool stat_faults(const char* text, unsigned long long* minflt, unsigned long long* majflt) {
    if (text == nullptr) return false;
    const char* p = std::strrchr(text, ')');
    if (p == nullptr) return false;
    p++;
    unsigned long long v[10] = {};
    int                k = 0;
    while (k < 10) { // v[0] is field 3 (the state), v[7] field 10, v[9] field 12
        while (*p == ' ') p++;
        if (*p == 0) return false;
        char* end = nullptr;
        v[k]      = k == 0 ? 0 : std::strtoull(p, &end, 10);
        if (k == 0) {
            while (*p != 0 && *p != ' ') p++;
        } else {
            if (end == p) return false;
            p = end;
        }
        k++;
    }
    *minflt = v[7], *majflt = v[9];
    return true;
}

// BC5_GUARD_FORGET: the forced chunks under no view of `cov` for idle_ns leave `forced`; `since` remembers when each was
// first seen so. Returns how many left.
static size_t forget_step(std::set<uint64_t>& forced, const Ranges& cov, std::map<uint64_t, uint64_t>& since, uint64_t now, uint64_t idle_ns, uint64_t chunk) {
    size_t n = 0;
    for (auto it = forced.begin(); it != forced.end();) {
        const uint64_t c = *it;
        if (cov.overlap(c, c + chunk) != 0) {
            since.erase(c);
            ++it;
            continue;
        }
        const auto s = since.try_emplace(c, now).first;
        if (now - s->second >= idle_ns) {
            since.erase(s);
            it = forced.erase(it);
            n++;
        } else {
            ++it;
        }
    }
    for (auto it = since.begin(); it != since.end();) { // chunks that left the forced set some other way
        if (forced.count(it->first) == 0) it = since.erase(it);
        else ++it;
    }
    return n;
}

// BC5_GUARD_APPLY_MIN_MS: true when this learned_apply call is put off.
struct Defer {
    uint64_t last_gen = 0, last_ns = 0, last_reopens = 0, deferred = 0;
    bool     seen = false;
};
static bool defer(Defer& d, uint64_t min_ns, uint64_t gen, uint64_t now, uint64_t reopens) {
    if (min_ns == 0) return false;
    if (d.seen && gen == d.last_gen && reopens == d.last_reopens) return false; // learned_apply returns at once by itself
    if (!d.seen || reopens != d.last_reopens || now - d.last_ns >= min_ns) {
        d.seen = true, d.last_gen = gen, d.last_ns = now, d.last_reopens = reopens;
        return false;
    }
    d.deferred++;
    return true;
}

} // namespace g412
// G412_PURE_END

#if !defined(GUARD0412_TEST)
namespace g412 {

static const Cfg& cfg() {
    // exp 0419: only the ledger still has a word; BC5_GUARD_MLOCK, _FILE, _PSI, _PIN_CAP, _APPLY_MIN_MS, _CAP_ACT and
    // _CAP_NAMES are gone (candidates E/F and G), their code is dead until it is cut.
    static const Cfg c = parse(BC5_DIAG_ENV("BC5_GUARD_LEDGER"), nullptr, nullptr, nullptr, nullptr, nullptr, nullptr, nullptr, nullptr);
    return c;
}

struct Req {
    int      kind, fd;
    uint64_t lo, hi;
};
struct State {
    std::mutex            m; // pinned and q
    Ranges                pinned[2];
    std::deque<Req>       q;
    std::atomic<bool>     started {false};
    std::atomic<uint64_t> deferred {0};
    std::mutex            dm; // d
    Defer                 d;
    // What the last full sync left imported (guard0412_synced): the direct file's BOs, and each file's bytes. The lazy
    // release (exp 0401 e7) cuts chunks out again, so `pinned` above, which only grows, is not the pinned set.
    std::vector<std::pair<uint64_t, uint64_t>> bos0; // under m: off and size
    bool                  bos0_seen = false;         // under m
    std::atomic<uint64_t> bytes[2] {};
    std::atomic<uint64_t> cap_off {0}, cap_off_max {0}, cap_changes {0}, cap_hard {0}; // bytes put off now and at most; changes of the set; hard chunks imported over the cap
};
static State& st() {
    static State s;
    return s;
}

static uint64_t mono_ns() {
    return static_cast<uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now().time_since_epoch()).count());
}

static bool slurp(const char* path, char* buf, size_t cap) {
    FILE* f = std::fopen(path, "r");
    if (f == nullptr) return false;
    const size_t n = std::fread(buf, 1, cap - 1, f);
    std::fclose(f);
    buf[n] = 0;
    return n != 0;
}

struct Worker {
    const Cfg& c = cfg();
    bool       lock_ok = false; // RLIMIT_MEMLOCK is unlimited
    bool       lock_dead = false;
    uint64_t   locked = 0, lock_calls = 0, guest_calls = 0, guest_fail = 0;
    const void* guest_seen = nullptr; // the views snapshot the guest pass last worked on
    std::map<int, uint64_t> fd_ino;   // fds under the root that have their advice
    uint64_t   advised = 0, dropped = 0, drops = 0, last_drop_ns = 0, last_psi_line_ns = 0, cap_step = 0;
    unsigned long long minflt0 = 0, majflt0 = 0;
    bool       flt_seen = false;
    uint64_t   t0 = mono_ns();

    void lock_ranges() {
        std::deque<Req> q;
        {
            std::lock_guard l(st().m);
            q.swap(st().q);
        }
        if (c.mlock == 0 || !lock_ok || lock_dead) return;
        for (const Req& r: q) {
            static constexpr uint64_t step = 64ull << 20u; // one mlock call at a time, so no long hold of the address space
            for (uint64_t lo = r.lo; lo < r.hi && !lock_dead; lo += step) {
                const uint64_t n = std::min(step, r.hi - lo);
                void*          p = ::mmap(nullptr, n, PROT_READ, MAP_SHARED, r.fd, static_cast<off_t>(lo));
                if (p == MAP_FAILED) {
                    lock_dead = true;
                    journal("guard: mmap of %s 0x%" PRIx64 "+0x%" PRIx64 " failed (errno %d); BC5_GUARD_MLOCK stops\n", r.kind == 0 ? "direct" : "private", lo, n, errno);
                    break;
                }
                if (::mlock(p, n) != 0) {
                    const int e = errno;
                    ::munmap(p, n);
                    lock_dead = true;
                    journal("guard: mlock of %s 0x%" PRIx64 "+0x%" PRIx64 " failed (errno %d); BC5_GUARD_MLOCK stops, %.1f MiB stay locked\n", r.kind == 0 ? "direct" : "private",
                            lo, n, e, static_cast<double>(locked) / 1048576.0);
                    break;
                }
                locked += n;
                lock_calls++;
            }
        }
    }

    // BC5_GUARD_MLOCK=guest: the direct-memory views that are not eager are locked as their pages come (MLOCK_ONFAULT).
    void lock_guest() {
        if (c.mlock != 2 || !lock_ok || lock_dead) return;
        const auto views = direct_views(g_d[0]);
        if (views.get() == guest_seen) return;
        guest_seen = views.get();
        uint32_t calls = 0;
        for (const auto& v: views->v) {
            if (v.eager || v.size == 0) continue;
            if (calls++ >= 4096) break;
            guest_calls++;
            if (::mlock2(reinterpret_cast<void*>(v.va), v.size, MLOCK_ONFAULT) != 0) guest_fail++; // ENOMEM: the title unmapped it meanwhile
        }
    }

    // The open files under the root: advice once per file, and the list for a drop.
    void files(bool drop, double some10) {
        if (!c.f_random && !c.f_dontneed) return;
        std::vector<int> under;
        for (int fd = 3; fd < 4096; fd++) {
            char link[40], path[512];
            std::snprintf(link, sizeof(link), "/proc/self/fd/%d", fd);
            const ssize_t n = ::readlink(link, path, sizeof(path) - 1);
            if (n <= 0) continue;
            path[n] = 0;
            if (std::strncmp(path, c.root.c_str(), c.root.size()) != 0) continue;
            struct stat sb {};
            if (::fstat(fd, &sb) != 0 || !S_ISREG(sb.st_mode)) continue;
            under.push_back(fd);
            if (!c.f_random) continue;
            auto it = fd_ino.find(fd);
            if (it != fd_ino.end() && it->second == static_cast<uint64_t>(sb.st_ino)) continue;
            if (::posix_fadvise(fd, 0, 0, POSIX_FADV_RANDOM) == 0) advised++;
            fd_ino[fd] = static_cast<uint64_t>(sb.st_ino);
        }
        if (!drop || !c.f_dontneed) return;
        uint32_t n = 0;
        for (const int fd: under) {
            if (::posix_fadvise(fd, 0, 0, POSIX_FADV_DONTNEED) == 0) n++;
        }
        dropped += n;
        drops++;
        journal("guard: psi some %.1f >= %.1f: the page cache of %u open game files dropped (drop %" PRIu64 ")\n", some10, c.psi, n, drops);
    }

    void line(bool psi_ok, double some10, double full10) {
        Ranges pin0;
        uint64_t pin1 = 0;
        {
            std::lock_guard l(st().m);
            if (st().bos0_seen) {
                for (const auto& b: st().bos0) pin0.add(b.first, b.first + b.second);
                pin1 = st().bytes[1].load();
            } else {
                pin0 = st().pinned[0];
                pin1 = st().pinned[1].bytes;
            }
        }
        const auto       views = direct_views(g_d[0]);
        std::vector<VIn> in;
        in.reserve(views->v.size());
        for (const auto& v: views->v) in.push_back({v.off, v.size, &v.name, v.eager, v.lazy});
        const Ledger L = ledger(in, pin0);
        char status[4096], pstat[1024], mem[8192], cg[64];
        const bool   cg_ok = slurp("/sys/fs/cgroup/memory.current", cg, sizeof(cg));
        const bool   s_ok = slurp("/proc/self/status", status, sizeof(status));
        const bool   m_ok = slurp("/proc/meminfo", mem, sizeof(mem));
        unsigned long long mn = 0, mj = 0;
        const bool   f_ok = slurp("/proc/self/stat", pstat, sizeof(pstat)) && stat_faults(pstat, &mn, &mj);
        if (f_ok && !flt_seen) minflt0 = mn, majflt0 = mj, flt_seen = true;
        const double mib = 1048576.0;
        const long   swt = m_ok ? kv_mib(mem, "SwapTotal") : -1, swf = m_ok ? kv_mib(mem, "SwapFree") : -1;
        journal("guard: t %.0f s: pinned direct %.1f MiB, private %.1f; under a view %.1f, orphans %.1f; views %zu over %.1f MiB; gtt %.1f; rss %ld shmem %ld swap %ld MiB; "
                "faults minor %lld major %lld; avail %ld unevictable %ld mlocked %ld swap used %ld MiB; psi some %.1f full %.1f%s; guard locked %.1f MiB, guest views %" PRIu64
                " (%" PRIu64 " refused); files advised %" PRIu64 ", drops %" PRIu64 "; apply put off %" PRIu64 "; rss anon %ld; cgroup %ld MiB; cap put off %.1f MiB (max %.1f, %" PRIu64
                " changes, %" PRIu64 " hard chunks over)\n",
                static_cast<double>(mono_ns() - t0) / 1e9, static_cast<double>(L.pinned) / mib, static_cast<double>(pin1) / mib, static_cast<double>(L.pinned_under) / mib,
                static_cast<double>(L.orphans) / mib, L.views, static_cast<double>(L.reserved_union) / mib, static_cast<double>(direct_gtt("mem_info_gtt_used")) / mib,
                s_ok ? kv_mib(status, "VmRSS") : -1, s_ok ? kv_mib(status, "RssShmem") : -1, s_ok ? kv_mib(status, "VmSwap") : -1,
                f_ok ? static_cast<long long>(mn - minflt0) : -1ll, f_ok ? static_cast<long long>(mj - majflt0) : -1ll, m_ok ? kv_mib(mem, "MemAvailable") : -1,
                m_ok ? kv_mib(mem, "Unevictable") : -1, m_ok ? kv_mib(mem, "Mlocked") : -1, swt >= 0 && swf >= 0 ? swt - swf : -1, psi_ok ? some10 : -1.0, psi_ok ? full10 : -1.0,
                psi_ok ? "" : " (unread)", static_cast<double>(locked) / mib, guest_calls, guest_fail, advised, drops, st().deferred.load(), s_ok ? kv_mib(status, "RssAnon") : -1,
                cg_ok ? static_cast<long>(std::strtoll(cg, nullptr, 10) >> 20) : -1, static_cast<double>(st().cap_off.load()) / mib, static_cast<double>(st().cap_off_max.load()) / mib,
                st().cap_changes.load(), st().cap_hard.load());
        journal("guard heaps (pinned/reserved MiB; E eager, L lazy, D by data): %s\n", heaps_text(L, 12, 760).c_str());
    }

    void run() {
        pthread_setname_np(pthread_self(), "bc5-guard");
        (void)::setpriority(PRIO_PROCESS, static_cast<id_t>(::gettid()), 10);
        struct rlimit rl {};
        const bool    rl_ok = ::getrlimit(RLIMIT_MEMLOCK, &rl) == 0;
        lock_ok = rl_ok && rl.rlim_cur == RLIM_INFINITY;
        journal("guard: switches: LEDGER %s, MLOCK %s, FILE %s%s%s%s, PSI %.1f, PIN_CAP %" PRIu64 " MiB (%s), APPLY_MIN_MS %" PRIu64 "%s%s; memlock limit %s (exp 0412, tag g412b)\n",
                c.ledger ? "on" : "off", c.mlock == 2 ? "guest" : c.mlock == 1 ? "pinned" : "off", c.f_random ? "random" : "", c.f_random && c.f_dontneed ? "," : "",
                c.f_dontneed ? "dontneed" : "", c.f_random || c.f_dontneed ? "" : "off", c.psi, c.cap >> 20u, c.cap_act ? "acts" : "log only", static_cast<uint64_t>(c.apply_ns / 1'000'000ull), c.bad.empty() ? "" : "; not understood, off:",
                c.bad.c_str(), !rl_ok ? "unread" : lock_ok ? "unlimited" : "limited");
        if (c.mlock != 0 && !lock_ok) journal("guard: BC5_GUARD_MLOCK needs \"ulimit -l unlimited\" in the launcher; nothing is locked in this run\n");
        for (uint64_t tick = 1;; tick++) {
            std::this_thread::sleep_for(std::chrono::seconds(1));
            lock_ranges();
            char         ps[512];
            double       some10 = 0.0, full10 = 0.0;
            const bool   want_psi = c.psi > 0.0 || (c.ledger && tick % 10 == 0);
            const bool   psi_ok = want_psi && slurp("/proc/pressure/memory", ps, sizeof(ps)) && psi_parse(ps, &some10, &full10);
            const uint64_t now = mono_ns();
            const bool   over = c.psi > 0.0 && psi_ok && some10 >= c.psi;
            const bool   drop = over && c.f_dontneed && now - last_drop_ns >= 5'000'000'000ull;
            if (drop) last_drop_ns = now;
            if (drop || tick % 5 == 0) files(drop, some10);
            if (over && !c.f_dontneed && now - last_psi_line_ns >= 10'000'000'000ull) {
                last_psi_line_ns = now;
                journal("guard: psi some %.1f >= %.1f (full %.1f)\n", some10, c.psi, full10);
            }
            if (tick % 10 != 0) continue;
            lock_guest();
            if (c.ledger) line(psi_ok, some10, full10);
            if (c.cap != 0) {
                uint64_t pinned = st().bytes[0].load() + st().bytes[1].load();
                if (pinned == 0) {
                    std::lock_guard l(st().m);
                    pinned = st().pinned[0].bytes + st().pinned[1].bytes;
                }
                const uint64_t step = pinned > c.cap ? (pinned - c.cap) / (64ull << 20u) + 1 : 0;
                if (step > cap_step) journal("guard: pinned %.1f MiB is over BC5_GUARD_PIN_CAP %" PRIu64 " MiB (%s)\n", static_cast<double>(pinned) / 1048576.0, c.cap >> 20u,
                                             c.cap_act ? "soft chunks are put off; the rest is hard" : "log only");
                cap_step = step;
            }
        }
    }
};

} // namespace g412

// The import loop's hook: [off, off + size) of the file behind `kind` (0 direct, 1 private) is imported, so pinned.
static void guard0412_imported(int kind, int fd, uint64_t off, uint64_t size) {
    const g412::Cfg& c = g412::cfg();
    if (!c.worker() || kind < 0 || kind > 1 || fd < 0 || size == 0) return;
    g412::State& s = g412::st();
    {
        std::lock_guard l(s.m);
        for (const auto& f: s.pinned[kind].add(off, off + size)) {
            if (c.mlock != 0) s.q.push_back({kind, fd, f.first, f.second});
        }
    }
    if (!s.started.exchange(true)) {
        std::thread([] {
            static g412::Worker w;
            w.run();
        }).detach();
    }
}

// The submission path's hook: true when learned_apply is put off (BC5_GUARD_APPLY_MIN_MS).
static bool guard0412_defer_apply() {
    const g412::Cfg& c = g412::cfg();
    if (c.apply_ns == 0) return false;
    g412::State&    s = g412::st();
    static std::atomic<bool> said {false};
    if (!said.exchange(true)) journal("guard: BC5_GUARD_APPLY_MIN_MS %" PRIu64 ": learned_apply at most once per that while the layout changes (exp 0412, tag g412)\n", static_cast<uint64_t>(c.apply_ns / 1'000'000ull));
    std::lock_guard l(s.dm);
    const bool      put_off = g412::defer(s.d, c.apply_ns, static_cast<uint64_t>(g_layout_gen), g412::mono_ns(), g_m11_reopens.load());
    if (put_off) s.deferred++;
    return put_off;
}

// BC5_GUARD_SPLIT (g412c).
static bool guard0412_split() {
    static const bool on = bc5::env_on(std::getenv("BC5_GUARD_SPLIT"));
    return on;
}
// The end of a sync whose lazy release made cuts: the aliases of the retired BOs are gone (Device::free_shared drops
// them), so they are mapped again now and not at the next submission's rate-limited aliases_apply.
static void guard0412_after_cuts(size_t cuts) {
    if (cuts == 0 || !guard0412_split()) return;
    aliases_apply(true);
    static std::atomic<uint64_t> n {0};
    if (const uint64_t k = n++; k < 8 || (k & 255u) == 0) journal("guard split: %zu BOs cut in this sync; aliases mapped again at once (%" PRIu64 " such syncs)\n", cuts, k + 1);
}

// BC5_GUARD_CAP_ACT. The chunks of the direct file the cap has put off, sorted; the sync thread's own.
static std::vector<uint64_t> g_g412_off;
static bool                  g_g412_off_changed = false;

// After the import loop's list is made: takes the soft chunks out of `need` that do not fit under the cap.
static void guard0412_cap(DState& S, const std::vector<DView>& views, std::vector<uint64_t>& need) {
    const g412::Cfg& c = g412::cfg();
    if (!c.cap_act || S.kind != 0) return;
    std::vector<char> soft(need.size(), 1);
    if (!need.empty()) {
        for (size_t i = 0; i < need.size(); i++) {
            if (S.forced.count(need[i]) != 0) soft[i] = 0;
        }
        for (const auto& v: views) {
            if (!v.eager || v.size == 0 || g412::cap_name(c, v.name)) continue; // a hard heap: its chunks are never put off
            auto it = std::lower_bound(need.begin(), need.end(), v.off & ~(kDChunk - 1));
            for (; it != need.end() && *it < v.off + v.size; ++it) soft[static_cast<size_t>(it - need.begin())] = 0;
        }
    }
    const uint64_t pinned = g_d[0].bytes + g_d[1].bytes;
    g412::CapPlan  p = g412::cap_plan(need, soft, pinned, c.cap, kDChunk);
    g412::State&   s = g412::st();
    if (p.hard != 0 && pinned + p.hard * kDChunk > c.cap) s.cap_hard += p.hard;
    if (p.off != g_g412_off) {
        g_g412_off_changed = true;
        const uint64_t bytes = p.off.size() * kDChunk, n = s.cap_changes++;
        s.cap_off = bytes;
        if (bytes > s.cap_off_max.load()) s.cap_off_max = bytes;
        if (n < 16 || (n & 63u) == 0) {
            journal("guard cap: %.1f MiB pinned, cap %" PRIu64 " MiB: %zu chunks (%.1f MiB) put off, the zero buffer under their views; %" PRIu64 " hard chunks imported "
                    "now (change %" PRIu64 ")\n",
                    static_cast<double>(pinned) / 1048576.0, c.cap >> 20u, p.off.size(), static_cast<double>(bytes) / 1048576.0, p.hard, n + 1);
        }
        g_g412_off.swap(p.off);
    }
    need.swap(p.keep);
}

// True when the put-off set changed since the mappings were last built: the GPU is drained and the mappings rebuilt.
static bool guard0412_cap_changed(const DState& S) {
    return S.kind == 0 && g_g412_off_changed;
}

// The mapping rebuild's hook: every (view, put-off chunk) intersection is one mapping of the zero buffer.
static void guard0412_want(const DState& S, const std::vector<DView>& views, std::vector<DMap>& want) {
    if (S.kind != 0) return;
    g_g412_off_changed = false;
    if (g_g412_off.empty()) return;
    const uint32_t id = scratch_bo();
    if (id == 0) {
        static bool said = false;
        if (!said) journal("guard cap: no zero buffer: the put-off chunks have no mapping (an access faults)\n");
        said = true;
        return;
    }
    for (const auto& v: views) {
        const uint64_t vend = v.off + v.size;
        auto           it = std::lower_bound(g_g412_off.begin(), g_g412_off.end(), v.off & ~(kDChunk - 1));
        for (; it != g_g412_off.end() && *it < vend; ++it) {
            const uint64_t lo = *it > v.off ? *it : v.off;
            const uint64_t hi = *it + kDChunk < vend ? *it + kDChunk : vend;
            if (lo < hi) want.push_back({v.va + (lo - v.off), hi - lo, lo - *it, id});
        }
    }
}

// The end of a full sync: what is imported now, for the ledger and the cap's log line.
static void guard0412_synced(const DState& S) {
    const g412::Cfg& c = g412::cfg();
    if (!c.worker() || S.kind < 0 || S.kind > 1) return;
    g412::State& s = g412::st();
    s.bytes[S.kind] = S.bytes;
    if (S.kind != 0 || !c.ledger) return;
    std::lock_guard l(s.m);
    s.bos0.clear();
    s.bos0.reserve(S.bos.size());
    for (const auto& b: S.bos) s.bos0.emplace_back(b.off, b.size);
    s.bos0_seen = true;
}
#endif // !GUARD0412_TEST

static void learned_apply() {
	bc5::load_stat::Scope ls_scope(bc5::load_stat::kLearned); // experiment 0415 (ls415)
	if (!g_dev) return; // exp 0412 (tag nl412): no learned file
	// The 2 MiB zero guards behind the eager heaps (exp 0037) are always made: BC5_DIRECT_HEAP_GUARDS is gone (exp 0419, candidate G).
	static uint64_t applied_gen = 0;
	if (applied_gen == g_layout_gen) return; // same views, VMAs and learned list as last time
	applied_gen = g_layout_gen;
	bc5::load_stat::Scope ls_apply(bc5::load_stat::kLearnedApply); // experiment 0415 (ls415d): a full application
	const uint64_t la_t0 = SoftCp::now_ns(), la_b0 = g_views_builds.load(); // experiment 0156
	// Holes the guest has put a range in since: give them back first.
	for (size_t i = 0; i < g_scratch.size();) {
		std::vector<std::pair<uint64_t, uint64_t>> guest;
		Libs::LibKernel::Memory::Bc5GuestRangesIn(g_scratch[i].first, g_scratch[i].first + g_scratch[i].second, &guest);
		if (!guest.empty()) {
			scratch_release(g_scratch[i].first, g_scratch[i].first + g_scratch[i].second);
		} else {
			i++;
		}
	}
	const uint64_t la_t1 = SoftCp::now_ns();
	std::vector<bc5::direct::Mapping> have = g_dev->mappings();
	std::sort(have.begin(), have.end(), [](const bc5::direct::Mapping& a, const bc5::direct::Mapping& b) { return a.va < b.va; });
	const uint64_t la_t2 = SoftCp::now_ns();
	// exp 0412 (tag nl412): no window is forced or mapped for a past fault
	const uint64_t la_t3 = SoftCp::now_ns();
	// exp 0412 (tag nl412): no zero buffer over a past fault's window; only the guards behind the eager heaps below
	const uint64_t la_t4 = SoftCp::now_ns();
	// exp 0412 (tag nl412): what follows is a RULE, not a learned window: it comes from the title's behaviour and is
	// applied to every eager heap from the layout, with no memory of a fault. Its proper form is the K3 rule (the
	// console's behaviour over true holes, DESIGN-learned-windows.md section 7); this guard goes when that rule is in.
	// Experiment 0037: the GPU reads up to 64 KiB past the end of the title's GPU heaps (four
	// faults so far, each just past one heap's end), so the hole after every view of an eagerly
	// imported heap of 32 MiB or more gets the zero buffer from the start (2048 KiB;
	// only where the guest has no range).
	static constexpr uint64_t guard = 2048ull << 10u;
	{
		const auto views_p = direct_views(g_d[0]);
		for (const auto& v: views_p->v) {
			if (!v.eager || v.size < (32ull << 20u)) continue; // the heaps, not the many small AMM pages
			const uint64_t end = (v.va + v.size + 0xfffull) & ~0xfffull;
			std::vector<std::pair<uint64_t, uint64_t>> guest;
			Libs::LibKernel::Memory::Bc5GuestRangesIn(end, end + 1, &guest);
			if (!guest.empty()) continue; // the next range of the guest starts right there
			scratch_fill(end, end + guard, have);
		}
	}
	const uint64_t la_t5 = SoftCp::now_ns();
	if (la_t5 - la_t0 > 5'000'000ull) {
		journal("learned apply: %.1f ms (release %.1f, mappings %.1f of %zu, windows %.1f, fill %.1f, guards %.1f); views rebuilt %" PRIu64 " times\n",
		        static_cast<double>(la_t5 - la_t0) / 1e6, static_cast<double>(la_t1 - la_t0) / 1e6, static_cast<double>(la_t2 - la_t1) / 1e6, have.size(),
		        static_cast<double>(la_t3 - la_t2) / 1e6, static_cast<double>(la_t4 - la_t3) / 1e6, static_cast<double>(la_t5 - la_t4) / 1e6, g_views_builds.load() - la_b0);
	}
}

static std::vector<uint64_t> g_hinted; // hint windows already mapped (cleared on a device reopen)
static std::vector<std::pair<const char*, uint64_t>> g_recent_targets; // the CB/DB bases seen lately (sampled at flip)

// Experiment 0065: the context registers hint_targets() follows, by offset from 0xa000 — a flat
// table (the std::map it replaces was looked up ~100 times after every change of a target).
struct HintCtx {
	std::vector<uint32_t> value = std::vector<uint32_t>(0x10000, 0);
	std::vector<uint8_t>  known = std::vector<uint8_t>(0x10000, 0);
	bool     has(uint32_t r) const { return known[r & 0xffffu] != 0; }
	uint32_t get(uint32_t r) const { return value[r & 0xffffu]; }
	void     set(uint32_t r, uint32_t v) {
		value[r & 0xffffu] = v;
		known[r & 0xffffu] = 1;
	}
};

// Experiment 0047: the size of the game's main 3D view, for the F2 menu: the last colour target
// and depth buffer of the same size, at least 640 wide, bound together (CB_COLOR0_ATTRIB2 and
// DB_DEPTH_SIZE_XY).
static std::atomic<uint32_t> g_main_w {0}, g_main_h {0};
static void main_pass_track(const HintCtx& ctx) {
	if (!ctx.has(0x3b0) || !ctx.has(0x07)) return;
	const uint32_t c = ctx.get(0x3b0), d = ctx.get(0x07);
	const uint32_t cw = ((c >> 14u) & 0x3fffu) + 1, ch = (c & 0x3fffu) + 1;
	const uint32_t dw = (d & 0x3fffu) + 1, dh = ((d >> 16u) & 0x3fffu) + 1;
	if (cw == dw && ch == dh && cw >= 640) {
		g_main_w.store(cw, std::memory_order_relaxed);
		g_main_h.store(ch, std::memory_order_relaxed);
	}
}

// Experiment 0412 (tag nl412): the K1 catcher, BC5_GUARD_K1_STAT=1 (default off; no behaviour changes). The rule that
// replaces the learned windows for GPU-written memory is "import exactly what the title binds, when it binds it". This
// counts how far today's hint is from that: for every new target base, was its own chunk imported at bind time, and
// how much did the +-32 MiB window around it pin.
static bool k1412_on() {
	static const bool on = [] {
		const char* e = BC5_DIAG_ENV("BC5_GUARD_K1_STAT");
		return e != nullptr && e[0] != 0 && !(e[0] == '0' && e[1] == 0);
	}();
	return on;
}
// 1: the 2 MiB chunk of the direct or private file under this guest address is imported; 0: it is under a view and
// not imported; -1: no view holds the address.
static int k1412_imported(uint64_t va) {
	for (auto& S: g_d) {
		if (dstate_fd(S) < 0) continue;
		const auto views_p = direct_views(S);
		for (const auto& v: views_p->v) {
			if (va < v.va || va >= v.va + v.size) continue;
			return direct_covered_end(S, (v.off + (va - v.va)) & ~(kDChunk - 1)) != 0 ? 1 : 0;
		}
	}
	return -1;
}
static void k1412_note(const char* name, uint64_t addr, int before, uint64_t window_bytes) {
	static uint64_t binds = 0, base_missing = 0, no_view = 0, window_total = 0, lines = 0;
	binds++;
	if (before == 0) base_missing++;
	if (before < 0) no_view++;
	window_total += window_bytes;
	if ((before == 0 || window_bytes != 0) && lines++ < 200) {
		journal("k1 stat (exp 0412, tag nl412): t %.3f s: %s base 0x%" PRIx64 " bound: its own chunk was %s; the +-32 MiB window pinned %.1f MiB more\n", timing_now(), name, addr,
		        before > 0 ? "imported" : (before == 0 ? "NOT imported (a K1 case: the bind is what brought it in)" : "under no view"), static_cast<double>(window_bytes) / 1048576.0);
	}
	if ((binds & 63u) == 0) {
		journal("k1 stat (exp 0412, tag nl412): t %.0f s: %" PRIu64 " new target bases; own chunk not imported at the bind %" PRIu64 ", under no view %" PRIu64 "; the windows pinned %.1f MiB in all\n",
		        timing_now(), binds, base_missing, no_view, static_cast<double>(window_total) / 1048576.0);
	}
}
static void hint_targets(const uint32_t* ib, uint32_t num_dwords) {
	std::vector<uint64_t>& hinted = g_hinted;
	static constexpr uint64_t window = 32ull << 20u;
	// Below the base as well: GPU-generated textures cluster next to the render targets (run 31:
	// a TCP fault 1.2 MiB below CB0's base, nothing resident within 32 MiB).
	static constexpr uint64_t below = 32ull << 20u;
	if (!g_dev) return;
	// Experiment 0065: the sorted list and a binary search for the table checks (the copy of the
	// whole mapping list and a linear walk per LOAD_CONTEXT_REG_INDEX were most of the pass); the
	// full list only when a window is about to be mapped.
	auto have_p = g_dev->sorted_mappings();
	// Context state accumulates across submissions (a DCB's targets may have been loaded by the
	// preamble or an earlier DCB), and the bases are evaluated after EVERY packet that changes
	// them: a frame DCB sets its targets several times (one per pass) and the last table of the
	// IB may well zero them (run 30: CB0_BASE set four times in #12, the final value 0).
	static HintCtx ctx; // context register offset (relative to 0xa000) -> value
	struct Base { uint32_t lo, hi; const char* name; };
	static const std::vector<Base> bases = [] {
		std::vector<Base> b = {{0x005, 0x01e, "DB_HTILE"}, {0x012, 0x01a, "DB_Z_READ"}, {0x013, 0x01b, "DB_STENCIL_READ"},
		                       {0x014, 0x01c, "DB_Z_WRITE"}, {0x015, 0x01d, "DB_STENCIL_WRITE"}};
		static const char* cb[8] = {"CB0", "CB1", "CB2", "CB3", "CB4", "CB5", "CB6", "CB7"};
		for (uint32_t c = 0; c < 8; c++) {
			b.push_back({0x318 + c * 0xf, 0x390 + c, cb[c]});
			b.push_back({0x31f + c * 0xf, 0x398 + c, cb[c]});
			b.push_back({0x321 + c * 0xf, 0x3a0 + c, cb[c]});
			b.push_back({0x325 + c * 0xf, 0x3a8 + c, cb[c]});
		}
		return b;
	}();
	static const std::vector<bool> is_size = [] {
		std::vector<bool> v(0x10000, false);
		v[0x07] = v[0x95] = v[0x3b0] = true;
		return v;
	}();
	static const std::vector<bool> is_base = [] {
		std::vector<bool> v(0x10000, false);
		for (const auto& b: bases) {
			v[b.lo] = true;
			v[b.hi] = true;
		}
		return v;
	}();
	// The address each base had at its last evaluation: an unchanged one needs no second look
	// (cleared with the hinted windows on a device reopen).
	static std::vector<uint64_t> last_addr(bases.size(), 0);
	if (hinted.empty()) std::fill(last_addr.begin(), last_addr.end(), 0);
	auto evaluate = [&]() {
		for (size_t bi = 0; bi < bases.size(); bi++) {
			const auto& b = bases[bi];
			if (!ctx.has(b.lo) || ctx.get(b.lo) == 0) continue;
			const uint32_t ext  = ctx.has(b.hi) ? (ctx.get(b.hi) & 0xffu) : 0u;
			const uint64_t addr = (static_cast<uint64_t>(ctx.get(b.lo)) << 8u) | (static_cast<uint64_t>(ext) << 40u);
			if (addr == last_addr[bi]) continue;
			last_addr[bi]       = addr;
			const uint64_t lo   = addr & ~0xffffull;
			{
				bool known = false;
				for (const auto& t: g_recent_targets) known = known || t.second == addr;
				if (!known) {
					if (g_recent_targets.size() >= 16) g_recent_targets.erase(g_recent_targets.begin());
					g_recent_targets.emplace_back(b.name, addr);
				}
			}
			if (std::find(hinted.begin(), hinted.end(), lo) != hinted.end()) continue;
			hinted.push_back(lo);
			const Vma* vma = nullptr;
			for (const auto& v: g_vmas) {
				if (lo >= v.start && lo < v.end && !v.readonly) { vma = &v; break; }
			}
			if (vma == nullptr) { // a target in direct memory (ADR 0006)
				const uint64_t dlo = lo > below ? lo - below : 0;
				const int      k1_before = k1412_on() ? k1412_imported(lo) : -1; // exp 0412 (tag nl412)
				const uint64_t k1_bytes  = g_d[0].bytes + g_d[1].bytes;
				const uint64_t asked = direct_force(dlo, lo + window);
				if (k1412_on()) k1412_note(b.name, addr, k1_before, g_d[0].bytes + g_d[1].bytes - k1_bytes); // exp 0412 (tag nl412)
				journal("hint %s 0x%" PRIx64 ": window 0x%" PRIx64 "+0x%" PRIx64 ", direct memory +%.1f MiB\n", b.name, addr, dlo, lo + window - dlo, static_cast<double>(asked) / 1048576.0);
				have_p = g_dev->sorted_mappings();
				continue;
			}
			const uint64_t hi  = (lo + window < vma->end) ? lo + window : vma->end;
			const uint64_t lo2 = (lo > vma->start + below) ? lo - below : vma->start;
			std::vector<std::pair<uint64_t, uint64_t>> pieces = {{lo2, hi}};
			const std::vector<bc5::direct::Mapping> have = g_dev->mappings();
			for (const auto& m: have) {
				std::vector<std::pair<uint64_t, uint64_t>> next;
				for (const auto& [pa, pb]: pieces) {
					if (m.va + m.size <= pa || m.va >= pb) { next.emplace_back(pa, pb); continue; }
					if (m.va > pa) next.emplace_back(pa, m.va);
					if (m.va + m.size < pb) next.emplace_back(m.va + m.size, pb);
				}
				pieces.swap(next);
			}
			uint64_t added = 0;
			for (const auto& [pa, pb]: pieces) {
				if (pb <= pa) continue;
				if (g_dev->map_userptr(pa, pb - pa)) {
					added += pb - pa;
					g_bytes_mapped += pb - pa;
				}
			}
			have_p = g_dev->sorted_mappings();
			journal("hint %s 0x%" PRIx64 ": window 0x%" PRIx64 "+0x%" PRIx64 ", mapped +%.1f MiB\n", b.name, addr, lo2, hi - lo2, static_cast<double>(added) / 1048576.0);
		}
	};
	uint32_t i = 0;
	while (i < num_dwords) {
		const uint32_t h = ib[i];
		const uint32_t type = h >> 30u;
		uint32_t len = 1;
		if (type == 3 || type == 0) {
			const uint32_t count = (h >> 16u) & 0x3fffu;
			len = count == 0x3fffu ? 1 : count + 2;
		}
		if (i + len > num_dwords) break;
		const uint32_t  op = (h >> 8u) & 0xffu;
		const uint32_t* p  = ib + i;
		bool changed = false, base_changed = false;
		if (type == 3 && op == 0x69 && len >= 3) { // SET_CONTEXT_REG
			for (uint32_t k = 2; k < len; k++) {
				const uint32_t off = ((p[1] & 0xffffu) + k - 2) & 0xffffu;
				if (is_base[off] || is_size[off]) {
					ctx.set(off, p[k]);
					changed = true;
					base_changed = base_changed || is_base[off];
				}
			}
		} else if (type == 3 && op == 0x9f && len >= 5 && (p[3] >> 31u) != 0) { // LOAD_CONTEXT_REG_INDEX, pairs
			const uint64_t a = (p[1] & ~3u) | (static_cast<uint64_t>(p[2] & 0xffffu) << 32u);
			const uint32_t n = p[4] & 0x3fffu;
			if (covered_sorted(*have_p, a, static_cast<uint64_t>(n) * 8)) {
				const auto* t = reinterpret_cast<const volatile uint32_t*>(a);
				for (uint32_t k = 0; k + 1 < 2 * n; k += 2) {
					const uint32_t off = t[k] & 0xffffu;
					if (is_base[off] || is_size[off]) {
						ctx.set(off, t[k + 1]);
						changed = true;
						base_changed = base_changed || is_base[off];
					}
				}
			} else {
				journal("hint: context table 0x%" PRIx64 " (%u pairs) not mapped, skipped\n", a, n);
			}
		} else if (type == 3 && op == 0x61 && len >= 5) {
			// LOAD_CONTEXT_REG: base of a flat register image, then (reg_offset, count) pairs; the
			// value of register X is at base + X*4 (the console preamble loads (0x0,215) (0xd8,272)
			// ... (0x2f5,203) from 0xfe0008000; TODO(verify) against PAL's PM4_PFP_LOAD_CONTEXT_REG).
			const uint64_t base = (p[1] & ~3u) | (static_cast<uint64_t>(p[2] & 0xffffu) << 32u);
			for (uint32_t k = 3; k + 1 < len; k += 2) {
				const uint32_t off = p[k] & 0xffffu, n = p[k + 1] & 0x3fffu;
				if (n == 0 || !covered_sorted(*have_p, base + static_cast<uint64_t>(off) * 4, static_cast<uint64_t>(n) * 4)) continue;
				const auto* t = reinterpret_cast<const volatile uint32_t*>(base + static_cast<uint64_t>(off) * 4);
				for (uint32_t q = 0; q < n; q++) {
					if (is_base[(off + q) & 0xffffu] || is_size[(off + q) & 0xffffu]) {
						ctx.set(off + q, t[q]);
						changed = true;
						base_changed = base_changed || is_base[(off + q) & 0xffffu];
					}
				}
			}
		}
		if (changed) {
			if (base_changed) evaluate(); // a size alone moves no target
			main_pass_track(ctx);
		}
		i += len;
	}
}

// BC5_DIRECT_SHADER_DUMP=1: the shader programs the SH tables of an IB point at
// (SPI_SHADER_PGM_LO/HI_{PS,VS,GS,ES,HS,LS}: SH offsets 0x08, 0x48, 0x88, 0xc8, 0x108, 0x148, Mesa
// gfx10), 32 KiB from each distinct address, once per run, as shader-<va>.bin — for the
// standalone replay of a pass in draw-min (experiment 0016, run 67).
static void dump_shaders(const uint32_t* ib, uint32_t num_dwords, const std::vector<bc5::direct::Mapping>& maps) {
	static const bool on = BC5_DIAG_ENV("BC5_DIRECT_SHADER_DUMP") != nullptr;
	if (!on || g_dump_dir.empty()) return;
	static std::vector<uint64_t> seen;
	static const uint32_t lo_offsets[] = {0x08, 0x48, 0x88, 0xc8, 0x108, 0x148};
	// User-data registers (SPI_SHADER_USER_DATA_{PS,VS,GS,ES}_n: SH 0x0c.., 0x4c.., 0x8c.., 0xcc..)
	// that hold a guest pointer (low dword, then a dword whose low 16 bits are the high part):
	// 64 KiB from the page of each target, once, as mem-<va>.bin — the buffers and tables a
	// captured pass reads, for its standalone replay.
	static std::vector<uint64_t> mem_seen;
	auto consider_data = [&](uint32_t off, uint32_t lo, uint32_t hi) {
		const bool user = (off >= 0x0c && off < 0x2c) || (off >= 0x4c && off < 0x6c) || (off >= 0x8c && off < 0xac) || (off >= 0xcc && off < 0xec);
		if (!user || lo == 0 || mem_seen.size() >= 512) return;
		const uint64_t va = (static_cast<uint64_t>(hi & 0xffffu) << 32u) | lo;
		const uint64_t page = va & ~0xfffull;
		if (va < 0x100000000ull || !covered(maps, page, 4096)) return;
		if (std::find(mem_seen.begin(), mem_seen.end(), page) != mem_seen.end()) return;
		mem_seen.push_back(page);
		uint64_t bytes = 65536;
		while (bytes > 4096 && !covered(maps, page, bytes)) bytes -= 4096;
		char name[512];
		std::snprintf(name, sizeof(name), "%s/mem-%012" PRIx64 ".bin", g_dump_dir.c_str(), page);
		if (FILE* f = std::fopen(name, "wb")) {
			std::fwrite(reinterpret_cast<const void*>(page), 1, bytes, f);
			std::fclose(f);
		}
	};
	auto consider = [&](uint32_t off, uint32_t lo, uint32_t hi) {
		consider_data(off, lo, hi);
		bool is_lo = false;
		for (const uint32_t o: lo_offsets) is_lo = is_lo || o == off;
		if (!is_lo || lo == 0) return;
		const uint64_t va = (static_cast<uint64_t>(lo) << 8u) | (static_cast<uint64_t>(hi & 0xffu) << 40u);
		if (std::find(seen.begin(), seen.end(), va) != seen.end()) return;
		seen.push_back(va);
		if (!covered(maps, va, 32768)) { journal("shader 0x%" PRIx64 " (SH 0x%x): not mapped\n", va, 0x2c00 + off); return; }
		char name[512];
		std::snprintf(name, sizeof(name), "%s/shader-%012" PRIx64 ".bin", g_dump_dir.c_str(), va);
		if (FILE* f = std::fopen(name, "wb")) {
			std::fwrite(reinterpret_cast<const void*>(va), 1, 32768, f);
			std::fclose(f);
		}
		journal("shader 0x%" PRIx64 " (SH 0x%x): dumped\n", va, 0x2c00 + off);
	};
	for (uint32_t i = 0; i < num_dwords;) {
		const uint32_t h = ib[i];
		const uint32_t type = h >> 30u;
		uint32_t len = 1;
		if (type == 3 || type == 0) { const uint32_t c = (h >> 16u) & 0x3fffu; len = c == 0x3fffu ? 1 : c + 2; }
		if (i + len > num_dwords) break;
		const uint32_t  op = (h >> 8u) & 0xffu;
		const uint32_t* p  = ib + i;
		if (type == 3 && op == 0x63 && len >= 5 && (p[3] >> 31u) != 0) { // LOAD_SH_REG_INDEX pairs
			const uint64_t a = (p[1] & ~3u) | (static_cast<uint64_t>(p[2] & 0xffffu) << 32u);
			const uint32_t n = p[4] & 0x3fffu;
			if (covered(maps, a, static_cast<uint64_t>(n) * 8)) {
				const auto* t = reinterpret_cast<const volatile uint32_t*>(a);
				std::map<uint32_t, uint32_t> vals;
				for (uint32_t k = 0; k + 1 < 2 * n; k += 2) vals[t[k] & 0xffffu] = t[k + 1];
				for (const auto& [off, lo]: vals) consider(off, lo, vals.count(off + 1) ? vals[off + 1] : 0);
			}
		} else if (type == 3 && op == 0x5f && len >= 5) { // LOAD_SH_REG: flat image at base
			const uint64_t base = (p[1] & ~3u) | (static_cast<uint64_t>(p[2] & 0xffffu) << 32u);
			for (uint32_t k = 3; k + 1 < len; k += 2) {
				const uint32_t off = p[k] & 0xffffu, n = p[k + 1] & 0x3fffu;
				if (n == 0 || !covered(maps, base + static_cast<uint64_t>(off) * 4, static_cast<uint64_t>(n) * 4)) continue;
				const auto* t = reinterpret_cast<const volatile uint32_t*>(base + static_cast<uint64_t>(off) * 4);
				for (uint32_t q = 0; q + 1 < n; q++) consider(off + q, t[q], t[q + 1]);
			}
		} else if (type == 3 && op == 0x76 && len >= 4) { // SET_SH_REG
			consider(p[1] & 0xffffu, p[2], p[3]);
		}
		i += len;
	}
}

// Journals the register tables the LOAD_*_REG[_INDEX] packets of an IB would load: the filter
// cannot see them (they live in guest memory, not in the IB), so they bypass the register policy
// — the prime suspect of the step-(c1) hang (experiment 0016, submit #14). Layout (PAL
// pm4_pfp_load_context_reg_index): dword1 addr lo (bits 31:2) | index (bit 0), dword2 addr hi,
// dword3 reg_offset (15:0) | data_format (bit 31: 1 = offset/data pairs), dword4 num_dwords.
// LOAD_*_REG: dword1/2 base, then (reg_offset, num_dwords) pairs in the packet itself.
// [a, a+bytes) lies inside the mapped ranges; adjacent mappings count as one (the GPU VM has
// them all, a range straddling a 64 KiB piece boundary is still fully mapped).
static bool covered(const std::vector<bc5::direct::Mapping>& maps, uint64_t a, uint64_t bytes) {
	const uint64_t end = a + bytes;
	uint64_t       pos = a;
	for (int guard = 0; pos < end && guard < 64; guard++) {
		bool hit = false;
		for (const auto& m: maps) {
			if (cv412::hole(m.shared, m.readonly)) continue; // exp 0412 (tag cv412): as in covered_sorted
			if (pos >= m.va && pos < m.va + m.size) { pos = m.va + m.size; hit = true; break; }
		}
		if (!hit) return false;
	}
	return pos >= end;
}

static bool covered_sorted(const std::vector<bc5::direct::Mapping>& maps, uint64_t a, uint64_t bytes) {
	const uint64_t end = a + bytes;
	uint64_t       pos = a;
	for (int guard = 0; pos < end && guard < 64; guard++) {
		auto it = std::upper_bound(maps.begin(), maps.end(), pos, [](uint64_t v, const bc5::direct::Mapping& m) { return v < m.va; });
		if (it == maps.begin()) return false;
		--it;
		if (cv412::hole(it->shared, it->readonly)) return false; // exp 0412 (tag cv412): a K1r cover is for the GPU's reads; for the host it is a hole, as before K1r
		if (pos >= it->va + it->size) return false;
		pos = it->va + it->size;
	}
	return pos >= end;
}
// Experiment 0412 (tag ww412): every memory operand of the main buffer's packets names the chunk(s) of direct memory it lies in.
static void ww412_packets(const uint32_t* ib, uint32_t num_dwords) {
	if (!ww412::on() || !g_dev) return;
	const auto  views_p = direct_views(g_d[0]);
	const auto& views   = views_p->v;
	for (uint32_t q = 0; q < num_dwords;) {
		const uint32_t h   = ib[q];
		uint32_t       len = 1;
		if ((h >> 30u) == 3 || (h >> 30u) == 0) {
			const uint32_t c = (h >> 16u) & 0x3fffu;
			len              = c == 0x3fffu ? 1 : c + 2;
		}
		if (q + len > num_dwords) break;
		if ((h >> 30u) == 3) {
			for (const auto& [a, bytes]: bc5::policy::memory_operands(ib + q, len)) {
				if (a == 0) continue;
				const uint64_t e     = a + (bytes == 0 ? 4 : bytes);
				size_t         first = 0;
				if (views_p->sorted) first = static_cast<size_t>(std::partition_point(views.begin(), views.end(), [a](const DView& v) { return v.va + v.size <= a; }) - views.begin());
				for (size_t vi = first; vi < views.size(); vi++) {
					const auto& v = views[vi];
					if (views_p->sorted && v.va >= e) break;
					const uint64_t lo = a > v.va ? a : v.va;
					const uint64_t hi = e < v.va + v.size ? e : v.va + v.size;
					if (lo >= hi) continue;
					for (uint64_t c = (v.off + (lo - v.va)) & ~(kDChunk - 1); c < v.off + (hi - v.va); c += kDChunk) ww412_name(c);
				}
			}
		}
		q += len;
	}
}
// Experiment 0412 (tag k1f412): BC5_GUARD_K1_FILTER, a packet's unmapped operand under a view is imported, not dropped.
namespace k1f412 {
// 1 import (unset or anything else: the default), 0 off ("0"), 2 log only ("log"): name what the filter would drop, import nothing
inline int mode() {
	static const int v = [] {
		const char* e = BC5_DIAG_ENV("BC5_GUARD_K1_FILTER");
		if (e == nullptr) return 1;
		if (e[0] == '0' && e[1] == 0) return 0;
		return std::strcmp(e, "log") == 0 ? 2 : 1;
	}();
	return v;
}
inline bool on() { return mode() != 0; }
} // namespace k1f412
// Log only: every operand the filter would drop is named once per page (the first 400), with its packet, its view and
// whether its chunk is imported; every 10 s a count by packet opcode. Nothing is imported, nothing else changes.
static void k1f412_log(const uint32_t* ib, uint32_t num_dwords, const char* kind) {
	static std::set<uint64_t>           seen;
	static std::map<uint32_t, uint64_t> by_op, by_op_view;
	static uint64_t                     total = 0, under_view = 0, last_ns = 0, lines = 0;
	const auto                          have_p  = g_dev->sorted_mappings();
	const auto                          views_p = direct_views(g_d[0]);
	for (uint32_t q = 0; q < num_dwords;) {
		const uint32_t h   = ib[q];
		uint32_t       len = 1;
		if ((h >> 30u) == 3 || (h >> 30u) == 0) {
			const uint32_t c = (h >> 16u) & 0x3fffu;
			len              = c == 0x3fffu ? 1 : c + 2;
		}
		if (q + len > num_dwords) break;
		if ((h >> 30u) == 3) {
			const uint32_t op = (h >> 8u) & 0xffu;
			for (const auto& [a, bytes]: bc5::policy::memory_operands(ib + q, len)) {
				const uint64_t n = bytes == 0 ? 4 : bytes;
				if (a == 0 || covered_sorted(*have_p, a, n)) continue;
				const DView* v = nullptr;
				for (const auto& x: views_p->v) {
					if (a >= x.va && a < x.va + x.size) {
						v = &x;
						break;
					}
				}
				total++;
				by_op[op]++;
				if (v != nullptr) {
					under_view++;
					by_op_view[op]++;
				}
				if (seen.size() < 400 && seen.insert(a & ~0xfffull).second) {
					const bool imported = v != nullptr && direct_covered_end(g_d[0], (v->off + (a - v->va)) & ~(kDChunk - 1)) != 0;
					journal("k1 at the filter LOG (exp 0412, tag k1f412): t %.3f s: %s %u dwords, packet op 0x%02x at dword %u: operand 0x%" PRIx64 "+%" PRIu64 " is not mapped (the filter drops the packet): %s%s%s%s\n",
					        timing_now(), kind, num_dwords, op, q, a, n, v == nullptr ? "under NO view of the direct file" : "under \"", v == nullptr ? "" : v->name.c_str(),
					        v == nullptr ? "" : (v->eager ? "\" (eager)" : (v->lazy ? "\" (lazy)" : "\" (by data)")), v == nullptr ? "" : (imported ? ", its chunk imported (mapped elsewhere?)" : ", its chunk not imported: an import would let the packet through"));
					lines++;
				}
			}
		}
		q += len;
	}
	const uint64_t now = SoftCp::now_ns();
	if (total != 0 && now - last_ns >= 10'000'000'000ull) {
		last_ns = now;
		std::string ops;
		for (const auto& [op, c]: by_op) {
			char t[64];
			std::snprintf(t, sizeof(t), " 0x%02x:%" PRIu64 "/%" PRIu64, op, c, by_op_view.count(op) != 0 ? by_op_view[op] : 0);
			ops += t;
		}
		journal("k1 at the filter LOG (exp 0412, tag k1f412): t %.0f s: %" PRIu64 " unmapped operands so far, %" PRIu64 " under a view (an import would cure), %zu distinct pages named; by packet opcode (all/under a view):%s\n",
		        timing_now(), total, under_view, seen.size(), ops.c_str());
	}
}
// Experiment 0434 (tag ud434), built in with no switch: a buffer descriptor (V#) written into a shader stage's user-data
// registers by SET_SH_REG names memory the shader reads or WRITES; under a view of direct memory that is not imported it
// is imported before the submit, as k1f412 does for a packet's own operands. ASTRO BOT, Bathhouse Battle's load
// (fault records 20261119-140627/-140758/-141432): COMPUTE_USER_DATA_4..7 held a V# of 16 bytes at 0x314cb62dc in a
// never-written chunk of the lazy heap orbis_user_malloc; the dispatch's store hit K1r's read-only cover (TCP, RW 1).
// The maintainer, 2026-11-19, after his test on Bathhouse Battle: "Wszystko ok, możesz wdrożyć"; no switch.
namespace ud434 {
constexpr uint64_t kMaxSpan = 256ull << 20u; // a descriptor that claims more is cut to this
// The first user-data register of the stage that register r belongs to, or ~0u: PS, VS, GS, ES, HS, LS (32 each,
// SH offsets as in dt412::user_reg) and compute (COMPUTE_USER_DATA_0..15 at 0x240).
inline uint32_t stage_base(uint32_t r) {
	for (uint32_t b: {0x0cu, 0x4cu, 0x8cu, 0xccu, 0x10cu, 0x14cu}) {
		if (r >= b && r < b + 32u) return b;
	}
	return (r >= 0x240u && r < 0x250u) ? 0x240u : ~0u;
}
// One SET_SH_REG (0x76) or SET_SH_REG_INDEX (0x9b) packet of len dwords: every V# in it that starts at a user-data
// register 4-aligned to its stage's first one (a descriptor sits in an aligned SGPR quad; every stage's user data is a
// multiple of 4 registers, so such a quad never crosses its end): found(address, bytes). A V#: dword 3 TYPE (bits 31:30) 0, base dword 0 + dword 1 bits 15:0, a
// non-zero base below 2^40; bytes = stride * num_records, or num_records when the stride is 0; empty ones skipped.
template <typename F> inline void scan(const uint32_t* p, uint32_t len, F&& found) {
	if (len < 3 || (p[0] >> 30u) != 3) return;
	const uint32_t op = (p[0] >> 8u) & 0xffu;
	if (op != 0x76u && op != 0x9bu) return;
	const uint32_t reg0 = p[1] & 0xffffu, count = len - 2;
	for (uint32_t k = 0; k + 4 <= count; k++) {
		const uint32_t r = reg0 + k, b = stage_base(r);
		if (b == ~0u || ((r - b) & 3u) != 0) continue;
		const uint32_t w0 = p[2 + k], w1 = p[3 + k], w2 = p[4 + k], w3 = p[5 + k];
		if ((w3 >> 30u) != 0) continue;
		const uint64_t a = static_cast<uint64_t>(w0) | (static_cast<uint64_t>(w1 & 0xffffu) << 32u);
		if (a == 0 || (a >> 40u) != 0) continue;
		const uint64_t stride = (w1 >> 16u) & 0x3fffu;
		uint64_t       bytes  = stride != 0 ? stride * w2 : static_cast<uint64_t>(w2);
		if (bytes == 0) continue;
		if (bytes > kMaxSpan) bytes = kMaxSpan;
		found(a, bytes);
	}
}
} // namespace ud434
static void k1f412_pass(const uint32_t* ib, uint32_t num_dwords, const char* kind) {
	if (!k1f412::on() || !g_dev) return;
	if (k1f412::mode() == 2) {
		k1f412_log(ib, num_dwords, kind);
		return;
	}
	static uint64_t fired = 0, asked_bytes = 0, lines = 0, no_view = 0;
	auto            have_p = g_dev->sorted_mappings();
	static uint64_t ud_fired = 0, ud_bytes = 0, ud_lines = 0; // exp 0434 (tag ud434)
	for (uint32_t q = 0; q < num_dwords;) {
		const uint32_t h   = ib[q];
		uint32_t       len = 1;
		if ((h >> 30u) == 3 || (h >> 30u) == 0) {
			const uint32_t c = (h >> 16u) & 0x3fffu;
			len              = c == 0x3fffu ? 1 : c + 2;
		}
		if (q + len > num_dwords) break;
		if ((h >> 30u) == 3) {
			for (const auto& [a, bytes]: bc5::policy::memory_operands(ib + q, len)) {
				const uint64_t n = bytes == 0 ? 4 : bytes;
				if (a == 0 || covered_sorted(*have_p, a, n)) continue;
				const uint64_t asked = direct_force(a & ~0xfffull, a + n);
				if (asked == 0) { // under no view (K3), or its chunk was asked for before and could not be imported
					no_view++;
					continue;
				}
				fired++;
				asked_bytes += asked;
				have_p = g_dev->sorted_mappings();
				if (lines++ < 200 || (lines & 255u) == 0) {
					journal("k1 at the filter (exp 0412, tag k1f412): t %.3f s: %s %u dwords, packet op 0x%02x at dword %u: operand 0x%" PRIx64 "+%" PRIu64 " was not mapped: its chunk(s) imported (+%.1f MiB), now %s; "
					        "%" PRIu64 " imports so far, %.1f MiB; %" PRIu64 " operands left unmapped (no view or no import)\n",
					        timing_now(), kind, num_dwords, (h >> 8u) & 0xffu, q, a, n, static_cast<double>(asked) / 1048576.0, covered_sorted(*have_p, a, n) ? "mapped" : "STILL NOT MAPPED", fired,
					        static_cast<double>(asked_bytes) / 1048576.0, no_view);
				}
			}
			{ // exp 0434 (tag ud434): the buffers a stage's user data names, before the submit
				ud434::scan(ib + q, len, [&](uint64_t a, uint64_t n) {
					if (covered_sorted(*have_p, a, n)) return;
					const uint64_t asked = direct_force(a & ~0xfffull, a + n);
					if (asked == 0) return; // under no view, or imported already, or its import failed before
					ud_fired++;
					ud_bytes += asked;
					have_p = g_dev->sorted_mappings();
					if (ud_lines++ < 200 || (ud_lines & 255u) == 0) {
						journal("user-data target (exp 0434, tag ud434): t %.3f s: %s %u dwords, SET_SH_REG at dword %u, reg 0x%x: V# 0x%" PRIx64 "+%" PRIu64 " was not mapped: its chunk(s) imported (+%.1f MiB), now %s; %" PRIu64 " imports so far, %.1f MiB\n",
						        timing_now(), kind, num_dwords, q, ib[q + 1] & 0xffffu, a, n, static_cast<double>(asked) / 1048576.0, covered_sorted(*have_p, a, n) ? "mapped" : "STILL NOT MAPPED", ud_fired,
						        static_cast<double>(ud_bytes) / 1048576.0);
					}
				});
			}
		}
		q += len;
	}
}

// Experiment 0412 (tag dt412): dt0412.inc, the buffers a command buffer's user data names.
namespace dt412 {
inline int mode() {
	static const int v = [] {
		const char* e = BC5_DIAG_ENV("BC5_GUARD_DESC_TARGETS");
		if (e == nullptr || e[0] == 0 || (e[0] == '0' && e[1] == 0)) return 0;
		return (e[0] == '2' && e[1] == 0) ? 2 : 1;
	}();
	return v;
}
constexpr uint64_t kMaxSpan  = 256ull << 20u; // a descriptor that claims more is cut to this
constexpr uint32_t kTableDws = 64;            // dwords read at a plain pointer (16 descriptors)
inline bool user_reg(uint32_t r) {
	for (uint32_t b: {0x0cu, 0x4cu, 0x8cu, 0xccu, 0x10cu, 0x14cu}) {
		if (r >= b && r < b + 32u) return true;
	}
	return r >= 0x240u && r < 0x250u;
}
// The address a pair of dwords may hold and the bytes it spans: found(address, bytes, plain). bytes is 0 for a
// plain pointer (the length is not known). w2_known: a third dword follows (the record count).
template <typename F> inline void pair(uint32_t w0, uint32_t w1, bool w2_known, uint32_t w2, F&& found) {
	if ((w1 & 0xffu) == 0) return;
	const uint64_t a = static_cast<uint64_t>(w0) | (static_cast<uint64_t>(w1 & 0xffu) << 32u);
	if ((w1 >> 8u) == 0) {
		found(a, static_cast<uint64_t>(0), true);
		return;
	}
	const uint64_t stride = (w1 >> 16u) & 0x3fffu;
	uint64_t       bytes  = w2_known ? (stride != 0 ? stride * w2 : static_cast<uint64_t>(w2)) : 0;
	if (bytes > kMaxSpan) bytes = kMaxSpan;
	found(a, bytes, false);
}
// Every pair of a block of dwords (a table a pointer leads to): found(position, address, bytes, plain).
template <typename F> inline void block(const uint32_t* w, uint32_t n, F&& found) {
	for (uint32_t k = 0; k + 1 < n; k++) {
		pair(w[k], w[k + 1], k + 2 < n, k + 2 < n ? w[k + 2] : 0u, [&](uint64_t a, uint64_t bytes, bool plain) { found(k, a, bytes, plain); });
	}
}
// The user data a command buffer sets, by SET_SH_REG, SET_SH_REG_INDEX or a loaded table: found(register, address,
// bytes, plain) for every pair of neighbouring user-data registers. read_table as in dw0412.inc. Returns false
// when a packet runs past the end (the walk stops there).
template <typename R, typename F> inline bool walk(const uint32_t* ib, uint32_t n, R&& read_table, F&& found) {
	std::vector<std::pair<uint32_t, uint32_t>> set; // (register, value) of one packet, in order
	std::vector<uint32_t>                      table;
	auto                                       flush = [&]() {
        for (size_t k = 0; k + 1 < set.size(); k++) {
            if (!user_reg(set[k].first) || set[k + 1].first != set[k].first + 1 || !user_reg(set[k + 1].first)) continue;
            const bool w2 = k + 2 < set.size() && set[k + 2].first == set[k].first + 2 && user_reg(set[k + 2].first);
            pair(set[k].second, set[k + 1].second, w2, w2 ? set[k + 2].second : 0u, [&](uint64_t a, uint64_t bytes, bool plain) { found(set[k].first, a, bytes, plain); });
        }
        set.clear();
	};
	for (uint32_t i = 0; i < n;) {
		const uint32_t h   = ib[i];
		const uint32_t typ = h >> 30u, cnt = (h >> 16u) & 0x3fffu;
		const uint32_t len = typ == 3 ? (cnt == 0x3fffu ? 1u : cnt + 2u) : (typ == 0 ? cnt + 2u : 1u);
		if (len > n - i) return false;
		if (typ == 3 && len >= 3) {
			const uint32_t op = (h >> 8u) & 0xffu;
			if (op == 0x76u || op == 0x9bu) {
				const uint32_t reg = ib[i + 1] & 0xffffu;
				for (uint32_t k = 2; k < len; k++) set.emplace_back(reg + (k - 2), ib[i + k]);
				flush();
			} else if (op == 0x63u && len >= 5 && (ib[i + 3] >> 31u) != 0) {
				const uint64_t ta = (ib[i + 1] & ~3u) | (static_cast<uint64_t>(ib[i + 2] & 0xffffu) << 32u);
				const uint32_t tn = ib[i + 4] & 0x3fffu;
				table.clear();
				if (ta != 0 && tn != 0 && tn <= 4096 && read_table(ta, tn, table) && table.size() >= 2ull * tn) {
					for (uint32_t k = 0; k < tn; k++) set.emplace_back(table[2 * k] & 0xffffu, table[2 * k + 1]);
					flush();
				}
			}
		}
		i += len;
	}
	return true;
}
// What was done lately, so that the same buffer bound in every dispatch of a frame costs one lookup. key(address,
// bytes) -> the time it was last handled; fresh() is true (and nothing is to do) within `keep` seconds of that.
struct Recent {
	std::unordered_map<uint64_t, double> m;
	bool                                 fresh(uint64_t a, uint64_t bytes, double now, double keep = 1.0) {
        if (m.size() > 65536) m.clear();
        const uint64_t k  = a ^ (bytes * 0x9e3779b97f4a7c15ull);
        auto           it = m.find(k);
        if (it != m.end() && now - it->second < keep && now >= it->second) return true;
        m[k] = now;
        return false;
	}
};
} // namespace dt412
// Experiment 0412 (tag dt412): the host's part of dt0412.inc.
// The chunks of [lo, hi) that lie under a view and are not imported: what direct_force would ask for (mode 2).
static uint64_t dt412_missing(uint64_t lo, uint64_t hi) {
	uint64_t bytes = 0;
	for (auto& S: g_d) {
		if (dstate_fd(S) < 0) continue;
		const auto views_p = direct_views(S);
		const auto& views = views_p->v;
		size_t      first = 0;
		if (views_p->sorted) first = static_cast<size_t>(std::partition_point(views.begin(), views.end(), [lo](const DView& v) { return v.va + v.size <= lo; }) - views.begin());
		for (size_t vi = first; vi < views.size(); vi++) {
			const auto& v = views[vi];
			if (views_p->sorted && v.va >= hi) break;
			const uint64_t a = lo > v.va ? lo : v.va;
			const uint64_t b = hi < v.va + v.size ? hi : v.va + v.size;
			if (a >= b) continue;
			for (uint64_t c = (v.off + (a - v.va)) & ~(kDChunk - 1); c < v.off + (b - v.va); c += kDChunk) {
				if (direct_covered_end(S, c) == 0) bytes += kDChunk;
			}
		}
	}
	return bytes;
}
static void dt412_pass(const uint32_t* ib, uint32_t n, const char* kind) {
	const int mode = dt412::mode();
	if (mode == 0 || ib == nullptr || n == 0 || !g_dev) return;
	static dt412::Recent recent, tables;
	static uint64_t      seen = 0, acted = 0, acted_bytes = 0, lines = 0, tables_read = 0;
	static double        last_line = 0;
	const double         now = timing_now();
	auto                 have_p = g_dev->sorted_mappings();
	auto take = [&](uint64_t a, uint64_t bytes, int level, uint32_t where) {
		const uint64_t lo = a & ~0xfffull, hi = a + (bytes != 0 ? bytes : 1);
		if (recent.fresh(lo, hi - lo, now)) return;
		seen++;
		const uint64_t asked = mode == 1 ? direct_force(lo, hi) : dt412_missing(lo, hi);
		if (asked == 0) return; // under no view, or imported already
		acted++;
		acted_bytes += asked;
		if (mode == 1) have_p = g_dev->sorted_mappings();
		if (lines++ < 200 || (lines & 255u) == 0) {
			journal("desc targets (exp 0412, tag dt412): t %.3f s: %s %u dwords: %s 0x%" PRIx64 "+0x%" PRIx64 " (level %d, %s %u): %s %.1f MiB; %" PRIu64 " so far, %.1f MiB\n", now, kind, n,
			        bytes != 0 ? "descriptor" : "pointer", a, bytes, level, level == 1 ? "register" : "table dword", where, mode == 1 ? "imported" : "WOULD import", static_cast<double>(asked) / 1048576.0, acted,
			        static_cast<double>(acted_bytes) / 1048576.0);
		}
	};
	auto read = [&](uint64_t a, uint32_t dws, std::vector<uint32_t>& out) {
		if (!covered_sorted(*have_p, a, static_cast<uint64_t>(dws) * 4)) return false;
		const auto* t = reinterpret_cast<const volatile uint32_t*>(a);
		out.resize(dws);
		for (uint32_t k = 0; k < dws; k++) out[k] = t[k];
		return true;
	};
	std::vector<uint32_t> tab;
	dt412::walk(
	    ib, n, [&](uint64_t a, uint32_t pairs, std::vector<uint32_t>& o) { return read(a, 2 * pairs, o); },
	    [&](uint32_t reg, uint64_t a, uint64_t bytes, bool plain) {
		    take(a, bytes, 1, reg);
		    if (!plain || (a & 3u) != 0 || !read(a, dt412::kTableDws, tab)) return;
		    uint64_t sum = 0xcbf29ce484222325ull; // the table as it is now: looked through again only when it changed
		    for (uint32_t w: tab) sum = (sum ^ w) * 0x100000001b3ull;
		    if (tables.fresh(a, sum, now)) return;
		    tables_read++;
		    dt412::block(tab.data(), dt412::kTableDws, [&](uint32_t k, uint64_t a2, uint64_t bytes2, bool) { take(a2, bytes2, 2, k); });
	    });
	if (now - last_line >= 60.0) {
		last_line = now;
		journal("desc targets (exp 0412, tag dt412): t %.0f s: mode %d (%s): %" PRIu64 " buffers looked at, %" PRIu64 " %s, %.1f MiB; %" PRIu64 " tables read\n", now, mode, mode == 1 ? "import" : "log only", seen, acted,
		        mode == 1 ? "imported" : "would be imported", static_cast<double>(acted_bytes) / 1048576.0, tables_read);
	}
}

static void journal_load_tables(const uint32_t* ib, uint32_t num_dwords,
                                const std::vector<bc5::direct::Mapping>& maps) {
	auto mapped = [&maps](uint64_t a, uint64_t bytes) { return covered(maps, a, bytes); };
	uint32_t i = 0;
	while (i < num_dwords) {
		const uint32_t h = ib[i];
		const uint32_t type = h >> 30u;
		uint32_t len = 1;
		if (type == 3 || type == 0) {
			const uint32_t count = (h >> 16u) & 0x3fffu;
			len = count == 0x3fffu ? 1 : count + 2;
		}
		if (i + len > num_dwords) break;
		const uint32_t op = (h >> 8u) & 0xffu;
		const uint32_t* p = ib + i;
		if (type == 3 && (op == 0x63 || op == 0x64 || op == 0x9f) && len >= 5) {
			const uint64_t a = (p[1] & ~3u) | (static_cast<uint64_t>(p[2] & 0xffffu) << 32u);
			const uint32_t n = p[4] & 0x3fffu;
			const uint32_t want = (p[3] >> 31u) ? 2 * n : n;
			const uint32_t show = want < 16 ? want : 16;
			journal("  load op %02x at %u: addr 0x%" PRIx64 " idx %u fmt %u regoff 0x%x n %u:", op, i, a,
			        p[1] & 1u, p[3] >> 31u, p[3] & 0xffffu, n);
			if (mapped(a, static_cast<uint64_t>(want) * 4)) {
				const auto* t = reinterpret_cast<const volatile uint32_t*>(a);
				for (uint32_t k = 0; k < show; k++) journal(" %08x", t[k]);
				if (show < want) journal(" ...");
			} else {
				journal(" (unmapped)");
			}
			journal("\n");
		} else if (type == 3 && (op == 0x5e || op == 0x5f || op == 0x61) && len >= 3) {
			const uint64_t a = (p[1] & ~3u) | (static_cast<uint64_t>(p[2] & 0xffffu) << 32u);
			journal("  load op %02x at %u: base 0x%" PRIx64 " pairs", op, i, a);
			for (uint32_t k = 3; k + 1 < len; k += 2) journal(" (0x%x,%u)", p[k] & 0xffffu, p[k + 1] & 0x3fffu);
			journal("\n");
		}
		i += len;
	}
}

// Submits one IB.
// BC5 experiment 0412 (tag zp412, README section 40 and its correction, section 45): the decision of the zero skip's
// poll before a submission. `seen` is the direct file's block count the last scan was started for; `sample` is the
// count read now, BEFORE any scan. A scan runs when they differ, and `seen` becomes that sample: never a count read
// after the scan or after the sync that follows it, because a write that lands between the scan and such a second
// read would be credited to `seen` without having been scanned, and the next submission would then skip its scan
// (the review of 2026-11-12, lesson R12: a sequence of reads is not a snapshot).
// The block count is a hint that something was written somewhere in the file; it is the scan that looks at the
// skipped chunks. A growth caused by the host's own pin after a scan costs one more scan at the next submission.
// This text is included by the main unit (through mkzpoll0412.py) and by the CPU test zpoll0412.cpp.
namespace zp412 {
inline bool look(uint64_t& seen, uint64_t sample) {
	if (sample == seen) return false;
	seen = sample;
	return true;
}
} // namespace zp412
// Experiment 0412 (tag zp412): BC5_GUARD_ZSKIP_POLL_SUBMIT. The zero skip's poll before every submission: see mkzpoll0412.py.
static void zpoll412_submit() {
	static const bool on = [] {
		const char* e = nullptr; /* exp 0419: option removed */
		return e != nullptr && e[0] == '1';
	}();
	if (!on || g_zskip.empty()) return;
	DState&   S  = g_d[0];
	const int fd = dstate_fd(S);
	if (fd < 0) return;
	static uint64_t seen = ~0ull, looks = 0, grew = 0, took = 0, took_subs = 0, spent_ns = 0, last_ns = 0, lines = 0;
	const uint64_t  t0 = SoftCp::now_ns();
	struct stat     st {};
	looks++;
	if (fstat(fd, &st) == 0 && zp412::look(seen, static_cast<uint64_t>(st.st_blocks))) { // seen = the sample taken BEFORE the scan (zpoll0412.inc, R12)
		grew++;
		const uint64_t before = g_zstat_cpu + g_zstat_hits;
		zskip_take_back(S, fd);
		const uint64_t n = g_zstat_cpu + g_zstat_hits - before;
		if (n != 0) {
			took += n;
			took_subs++;
			S.blocks = ~0ull; // a full sync: pin what came back and map it in the canary's place, before this buffer goes out
			direct_sync_one(S, true); // the pin allocates pages: the next submission sees a changed count and scans once more
			if (lines++ < 60 || (lines & 63u) == 0) {
				journal("zero skip poll (exp 0412, tag zp412): t %.3f s: %" PRIu64 " chunks taken back before submission %" PRIu64 " (%.2f ms)\n", timing_now(), n, g_submits.load(),
				        static_cast<double>(SoftCp::now_ns() - t0) / 1e6);
			}
		}
	}
	const uint64_t t1 = SoftCp::now_ns();
	spent_ns += t1 - t0;
	if (t1 - last_ns >= 10'000'000'000ull) {
		last_ns = t1;
		journal("zero skip poll (exp 0412, tag zp412): t %.0f s: %" PRIu64 " looks, the file had grown at %" PRIu64 ", %" PRIu64 " chunks taken back at %" PRIu64 " submissions; %.1f MiB still skipped; %.1f ms spent in all\n",
		        timing_now(), looks, grew, took, took_subs, static_cast<double>(g_zskip.bytes()) / 1048576.0, static_cast<double>(spent_ns) / 1e6);
	}
}
static void submit_one(const uint32_t* ib, uint32_t num_dwords, const char* kind);
static void chain_flush(int why); // ADR 0010, defined below

// Cross-queue waits on one ring (ADR 0005 xvi, F31). A WAIT_REG_MEM[64] whose label no earlier
// packet of the same IB writes cannot be honoured by the CP without a deadlock (the writer is
// another queue's IB, serialised behind this one). So the IB is submitted in pieces: the packets
// before the wait, then the host waits for the label on the CPU (it is guest memory the GPU
// writes; 2 s, then it goes on like the soft CP does), then the packets after it. A doorbell
// ring slice is only INDIRECT_BUFFER packets: its targets are submitted this way directly.
static bool wait_satisfied(const uint32_t* p, bool is64) {
	const uint32_t function = p[1] & 7u;
	const uint64_t a        = (p[2] & ~3u) | (static_cast<uint64_t>(p[3] & 0xffffu) << 32u);
	if (a == 0) return true;
	if (is64) {
		const uint64_t v = *reinterpret_cast<const volatile uint64_t*>(a);
		const uint64_t ref = p[4] | (static_cast<uint64_t>(p[5]) << 32u), mask = p[6] | (static_cast<uint64_t>(p[7]) << 32u);
		const uint64_t vm = v & mask, rm = ref & mask;
		switch (function) {
			case 0: return true;
			case 1: return vm < rm;
			case 2: return vm <= rm;
			case 3: return vm == rm;
			case 4: return vm != rm;
			case 5: return vm >= rm;
			case 6: return vm > rm;
			default: return true;
		}
	}
	return SoftCp::compare(function, *reinterpret_cast<const volatile uint32_t*>(a), p[5], p[4]);
}

// A compute IB split at a trailing cross-queue wait (run 73). The frame's compute IB does its
// dispatches, writes a label the frame DCB waits on at its start, then waits on a label that DCB
// writes midway, then only signals (RELEASE_MEM, markers). Taken whole it cannot go before the
// DCB and the DCB cannot go before it: both sat out their timeouts, 4 s per frame, and the DCB
// ran without that frame's compute results. When everything after the unsatisfied wait is
// "light" (no dispatch, no SH state, no nested IB), the packets before it are submitted at once
// and the rest when the wait is satisfied. Run 44's objection to splitting (foreign SH state
// between the pieces) does not apply to a piece that neither sets nor uses SH state.
struct AcbHead {
	const uint32_t*              ib;
	uint32_t                     num_dwords;
	uint32_t                     done;  // dwords already submitted
	std::vector<SoftCp::GpuDone> marks; // what the GPU executed of them, for the soft CP

	uint64_t                     reopens; // exp 0401 e11 (tag m11): g_m11_reopens when made (BC5_DIRECT_RESET_REPLAY_ACB)
};
static std::vector<AcbHead> g_acb_heads; // the queue consumer thread only

// Run 120: a compute buffer's tail (what follows its cross-queue wait) goes to the GPU as a job
// of its own once the wait is satisfied. Until run 120 only a tail of label writes and events
// qualified; the water in the second level has a 250-dword tail and a buffer that never split
// deadlocked with the main buffer (the main buffer waits at its start for a label the compute
// head writes; the compute tail waits for a label the main buffer sets later). Anything that does
// not depend on register state set before the wait may follow it: only draws, dispatches and
// nested buffers are refused, and such a tail is journaled once so that the next step (replaying
// the head's state before the tail) can be judged.
static bool tail_is_light(const uint32_t* p, uint32_t n) {
	std::string ops;
	bool        light = true;
	for (uint32_t i = 0; i < n;) {
		const uint32_t h = p[i];
		const uint32_t type = h >> 30u;
		const uint32_t c = (h >> 16u) & 0x3fffu;
		uint32_t len = 1;
		if (type == 3 || type == 0) len = c == 0x3fffu ? 1 : c + 2;
		if (i + len > n || type == 0) {
			light = false;
			break;
		}
		if (type == 3 && c != 0x3fffu) {
			const uint32_t op = (h >> 8u) & 0xffu;
			char buf[16];
			std::snprintf(buf, sizeof(buf), " %02x", op);
			ops += buf;
			switch (op) {
				case 0x15: // DISPATCH_DIRECT
				case 0x16: // DISPATCH_INDIRECT
				case 0x2a: // DRAW_INDEX_INDIRECT
				case 0x2b: // DRAW_INDIRECT
				case 0x2c: // DRAW_INDEX_INDIRECT_MULTI
				case 0x2d: // DRAW_INDEX_2
				case 0x2f: // DRAW_INDEX_AUTO
				case 0x35: // DRAW_INDEX_OFFSET_2
				case 0x36: // DRAW_INDEX_MULTI_AUTO? (treated as a draw)
				case 0x3f: // INDIRECT_BUFFER
				case 0x33: // INDIRECT_BUFFER_CNST
					light = false;
					break;
				default: break;
			}
		}
		i += len;
	}
	if (!light) {
		static std::atomic<uint32_t> reported {0};
		if (reported++ < 20) journal("acb tail not split: %u dwords, ops%s\n", n, ops.c_str());
	}
	return light;
}

// Run 121: a segment of a compute buffer that follows a cross-queue wait goes to the GPU as a job
// of its own, after other jobs have run in between, so the register state its dispatches rely on
// — set before the wait — is replayed first: every register-setting packet of the buffer up to the
// segment, in order, nothing else (no dispatch, no write, no event), as a small job of its own.
// The buffers live in a ring so that the soft CP's pass can still read them after the job.
static const uint32_t* state_prefix(const uint32_t* ib, uint32_t upto, uint32_t* out_dwords) {
	static std::deque<std::vector<uint32_t>> kept;
	std::vector<uint32_t> pre;
	for (uint32_t i = 0; i < upto;) {
		const uint32_t h    = ib[i];
		const uint32_t type = h >> 30u;
		const uint32_t c    = (h >> 16u) & 0x3fffu;
		uint32_t       len  = 1;
		if (type == 3 || type == 0) len = c == 0x3fffu ? 1 : c + 2;
		if (i + len > upto) break;
		if (type == 3 && c != 0x3fffu) {
			switch ((h >> 8u) & 0xffu) {
				case 0x11: // SET_BASE
				case 0x13: // INDEX_BUFFER_SIZE
				case 0x26: // INDEX_BASE
				case 0x28: // CONTEXT_CONTROL
				case 0x2a: // INDEX_TYPE
				case 0x2f: // NUM_INSTANCES
				case 0x5e: // LOAD_UCONFIG_REG
				case 0x60: // LOAD_CONFIG_REG
				case 0x5f: // LOAD_SH_REG
				case 0x61: // LOAD_CONTEXT_REG
				case 0x63: // LOAD_SH_REG_INDEX
				case 0x68: // SET_CONFIG_REG
				case 0x69: // SET_CONTEXT_REG
				case 0x76: // SET_SH_REG
				case 0x79: // SET_UCONFIG_REG
				case 0x9b: // SET_SH_REG_INDEX
				case 0x9f: // LOAD_CONTEXT_REG_INDEX
					pre.insert(pre.end(), ib + i, ib + i + len);
					break;
				default: break;
			}
		}
		i += len;
	}
	*out_dwords = static_cast<uint32_t>(pre.size());
	if (pre.empty()) return nullptr;
	if (kept.size() >= 256) kept.pop_front();
	kept.push_back(std::move(pre));
	return kept.back().data();
}

// Cleanup batch 6: the journal lines written for every job, every CPU-served wait and every
// indirect packet (some 720 a second in ASTRO BOT) are sampled; failures, timeouts and given-up
// waits are always written.
static bool journal_sample(std::atomic<uint64_t>& n, uint64_t mask) {
	return (n.fetch_add(1, std::memory_order_relaxed) & mask) == 0;
}

static thread_local std::vector<const uint32_t*> t_keep_waits;
// ADR 0009 (BC5_DIRECT_COMPUTE_RING=<n>; experiments only, with the maintainer present): the ring
// thread's compute buffers go to kernel compute ring n instead of the GFX ring, except those for
// which bc5::policy::compute_ring_refusal names a reason (they stay on the GFX ring). The second
// title's buffers hold none (experiment 0128).
// Experiment 0428 (tag w428): BC5_DIRECT_ACB_RINGS=<n>, way 2. 0 (unset, empty, "0") is today's one GFX ring; 1..4 put
// the ring thread's acbs on compute rings, each guest queue on its own libdrm ring index (modulo n). Read with
// std::getenv: the lean build reads it too. Exp 0427: a ring index is not a fixed hardware queue (the kernel's scheduler
// re-picks one when the index is idle), so the queue's compute state comes from aq424's prefix, not from the ring.
static int w428_rings() {
	static const int v = [] {
		const char* e = std::getenv("BC5_DIRECT_ACB_RINGS");
		int         n = e != nullptr && e[0] != 0 ? std::atoi(e) : 0;
		if (n < 0) n = 0;
		if (n > bc5::direct::kComputeRings) n = bc5::direct::kComputeRings;
#ifndef BC5_LEAN
		std::fprintf(stderr, "[bc5] exp 0428 (tag w428): acb rings %d%s\n", n, n == 0 ? " (off: every acb on the GFX ring)" : " (compute rings, one per guest queue, cross-ring waits kept for the GPU)");
#endif
		return n;
	}();
	return v;
}
// Iteration 2 (the smoke w428Q1: the title touches 56 guest queue slots at start, so an index map put its busy queues
// together on ring 0, 169,922 jobs against 14 on each other ring): every queue starts on ring 0; a queue whose acb count
// reaches 256 is busy and moves ONCE to the next ring of the rotation 1, 2, 3, 0, ... Before the move this thread's
// chain is flushed and every ring is waited idle (2 s at most), so the queue's earlier jobs on ring 0 are done before
// its first job on the new ring (its order holds). One move per busy queue, so the wait is paid a few times per run.
struct W428Queue {
	uint64_t n    = 0;
	int      ring = 0;
	bool     busy = false;
};
static std::mutex               g_w428_mu;
static std::map<int, W428Queue> g_w428_qring; // guest queue (t_queue_idx) -> its count and libdrm compute ring index
static int                      g_w428_busy = 0;
static std::atomic<uint64_t>    g_w428_moves {0}, g_w428_move_late {0};
static void                     chain_flush(int why); // ADR 0010, defined below
static int                      w428_queue_ring() {
	int prev = 0, now = 0;
	{
		std::lock_guard lk(g_w428_mu);
		W428Queue&      e = g_w428_qring[t_queue_idx];
		e.n++;
		if (e.busy || e.n < 256) return e.ring;
		e.busy = true;
		prev   = e.ring;
		e.ring = (++g_w428_busy) % w428_rings();
		now    = e.ring;
	}
	if (now != prev) {
		chain_flush(2); // ring/class
		const bool idle = !g_dev || g_dev->wait_idle(2'000'000'000ull);
		g_w428_moves++;
		if (!idle) g_w428_move_late++;
	}
	return now;
}
#ifndef BC5_LEAN
static std::map<std::string, uint64_t> g_w428_refused; // exp 0428 (tag w428c): acbs kept on the GFX ring, by reason
#endif
// Exp 0428 step 2: BC5_DIRECT_ACB_MEC_INDIRECT (read with std::getenv: lean too). The backend refuses every compute-form
// DISPATCH_INDIRECT on the MEC (exp 0290, kMecIndirectCheckVerified = false) because the CP's argument check was not
// verified there. Exp 0428's userdata-rings --cp-check ran the check (indirect_check::apply, compute_ring = true, the
// default limits) around 18 REAL compute-form DISPATCH_INDIRECTs on compute rings 0..2 on kernel 7.3.3: 6 sane triples
// ran, 12 over-limit triples were skipped, 0 kernel lines (raw/cp-run.txt). With the switch on, a buffer refused ONLY for
// that reason goes to its compute ring; the refusal is asked again with every DISPATCH_INDIRECT NOP-ed, so any other
// reason (graphics-only packet, a PARTIAL_TG_EN dispatch, checked here for the NOP-ed ones) still keeps it on the GFX ring.
static bool w428_mec_ok() {
	static const bool v = [] {
		const char* e = std::getenv("BC5_DIRECT_ACB_MEC_INDIRECT");
		return e != nullptr && e[0] != 0 && std::strcmp(e, "0") != 0;
	}();
	return v;
}
#ifndef BC5_LEAN
static std::atomic<uint64_t> g_w428_mec_moved {0}; // exp 0428 (tag w428c): acbs sent to a compute ring by the switch
#endif
static const char* w428_mec_refusal(const uint32_t* ib, uint32_t n, const char* why) {
	if (why == nullptr || !w428_mec_ok() || std::strcmp(why, "indirect dispatch (MEC check unverified)") != 0) return why;
	std::vector<uint32_t> c(ib, ib + n);
	for (uint32_t i = 0; i < n;) {
		const uint32_t h = c[i], type = h >> 30u;
		uint32_t       len = 1;
		if (type == 3 || type == 0) {
			const uint32_t k = (h >> 16u) & 0x3fffu;
			len              = k == 0x3fffu ? 1 : k + 2;
		}
		if (i + len > n) break;
		if (type == 3 && ((h >> 8u) & 0xffu) == 0x16u) {
			if (len >= 4 && (c[i + 3] & 0x2u) != 0 && (c[i + 3] & 0x20u) == 0) return "PARTIAL_TG_EN dispatch";
			c[i] = 0xC0000000u | (h & 0x3fff0000u) | (0x10u << 8u); // a NOP of the same length
		}
		i += len;
	}
	const char* rest = bc5::policy::compute_ring_refusal(std::span<const uint32_t>(c.data(), c.size()));
#ifndef BC5_LEAN
	if (rest == nullptr) g_w428_mec_moved++;
#endif
	return rest;
}
static int compute_ring_env() {
	static const int v = [] {
		if (w428_rings() > 0) return 0; // exp 0428 (tag w428)
		const char* e = BC5_DIAG_ENV("BC5_DIRECT_COMPUTE_RING");
		return e != nullptr ? std::atoi(e) : bc5::direct::kGfxRing;
	}();
	return v;
}
static std::atomic<uint64_t> g_comp_jobs {0}, g_comp_refused {0};
static thread_local int      t_ring = bc5::direct::kGfxRing; // the ring of the compute buffer being submitted
static int                   acb_ring(const uint32_t* ib, uint32_t num_dwords) {
	int ring = compute_ring_env();
	if (ring < 0) return bc5::direct::kGfxRing;
	if (w428_rings() > 1) ring = w428_queue_ring(); // exp 0428 (tag w428): this guest queue's ring index
	const char* why = bc5::policy::compute_ring_refusal(std::span<const uint32_t>(ib, num_dwords));
	why             = w428_mec_refusal(ib, num_dwords, why); // exp 0428 step 2 (BC5_DIRECT_ACB_MEC_INDIRECT)
	if (why == nullptr) return ring;
#ifndef BC5_LEAN
	if (w428_rings() > 0) {
		std::lock_guard lk(g_w428_mu);
		g_w428_refused[why]++;
	}
#endif
	if ((g_comp_refused++ & 0x3ffu) == 0)
		journal("compute ring: a compute buffer of %u dwords stays on the GFX ring (%s; %" PRIu64 " so far)\n", num_dwords, why, g_comp_refused.load());
	return bc5::direct::kGfxRing;
}
static int job_ring(const char* kind) {
	return std::strncmp(kind, "acb", 3) == 0 ? t_ring : bc5::direct::kGfxRing;
}

// Experiment 0401 (BC5_DIRECT_ACB_CS_PREFIX), defined with the CS prefix below.
static std::vector<uint32_t> acb_cs_prefix(const uint32_t* part, uint32_t n);
static void                  acb_cs_track(const uint32_t* part, uint32_t n);
static int                   acb_inherit_mode(); // experiment 0403 (BC5_DIRECT_ACB_INHERIT), defined with the CS prefix below
static std::vector<uint32_t> acb_inherit_prefix(const uint32_t* part, uint32_t n, uint32_t from);
static void                  acb_inherit_track(const uint32_t* part, uint32_t n);
static void                  acb_inherit_census(const uint32_t* p, uint32_t len);
static void                  acb_inherit_census_slice();
static bool                  acb_inherit_take(const uint32_t* p);
static thread_local uint32_t t_acb_from = 0; // experiment 0403: where in its title buffer the acb part submit_split gets starts
static void                  chain_append(const uint32_t* pre, uint32_t pre_n, const uint32_t* ib, uint32_t n, const char* kind, bool host_built);
static void submit_segment(const uint32_t* ib, uint32_t num_dwords, uint32_t from, uint32_t to) {
	if (from > 0) {
		uint32_t        n   = 0;
		const uint32_t* pre = state_prefix(ib, from, &n);
		static std::atomic<uint64_t> n_seg {0};
		if (journal_sample(n_seg, 0x3ffu)) journal("acb segment %u..%u of %u dwords: state prefix of %u dwords replayed first\n", from, to, num_dwords, n);
		if (pre != nullptr) submit_one(pre, n, "acb-state");
	}
	// Experiment 0134: the segment's waits that a pending write will satisfy stay for the GPU, as in
	// submit_split. Dropped (the filter keeps only waits on labels the segment writes itself), the
	// compute ring ran the segment before the graphics job that writes the label: ASTRO BOT's
	// models in black blocks (experiment 0132).
	t_keep_waits.clear();
	std::vector<uint64_t> written;
	for (uint32_t i = from; i < to;) {
		const uint32_t h    = ib[i];
		const uint32_t type = h >> 30u;
		uint32_t       len  = 1;
		if (type == 3 || type == 0) { const uint32_t c = (h >> 16u) & 0x3fffu; len = c == 0x3fffu ? 1 : c + 2; }
		if (i + len > to) break;
		const uint32_t  op = (h >> 8u) & 0xffu;
		const uint32_t* p  = ib + i;
		if (type == 3) {
			const uint32_t dst_sel = len >= 2 ? (p[1] >> 8u) & 0xfu : 0;
			if (op == 0x37 && len >= 4 && (dst_sel == 1 || dst_sel == 2 || dst_sel == 5)) written.push_back((p[2] & ~3u) | (static_cast<uint64_t>(p[3] & 0xffffu) << 32u));
			else if (op == 0x49 && len >= 6) written.push_back((p[3] & ~3u) | (static_cast<uint64_t>(p[4] & 0xffffu) << 32u));
			else if ((op == 0x47 || op == 0x1e) && len >= 4) written.push_back((p[2] & ~3u) | (static_cast<uint64_t>(p[3] & 0xffffu) << 32u));
			else if ((op == 0x3c || op == 0x93) && len >= 4 && ((p[1] >> 4u) & 1u) != 0) {
				const uint64_t label = (p[2] & ~3u) | (static_cast<uint64_t>(p[3] & 0xffffu) << 32u);
				if (std::find(written.begin(), written.end(), label) == written.end() && !wait_satisfied(p, op == 0x93) &&
				    ring_will_satisfy(p, op == 0x93, job_ring("acb"))) {
					t_keep_waits.push_back(p);
					SoftCp::set_gpu_executed(p, len, {0});
				}
			}
		}
		i += len;
	}
	// Experiment 0401: the guest queue's compute registers in front of a part that dispatches before it sets a program, in
	// the part's own chain segment (ADR 0010); without the chain (BC5_DIRECT_CHAIN=0) as a job of its own just before it.
	const std::vector<uint32_t> acb_cs = acb_inherit_mode() != 0 ? acb_inherit_prefix(ib + from, to - from, from) : acb_cs_prefix(ib + from, to - from); // + exp 0403
	if (acb_cs.empty()) {
		submit_one(ib + from, to - from, "acb");
	} else if (chain_on()) {
		chain_append(acb_cs.data(), static_cast<uint32_t>(acb_cs.size()), ib + from, to - from, "acb", false);
	} else {
		static thread_local std::deque<std::vector<uint32_t>> kept; // kept as state_prefix keeps its own
		if (kept.size() >= 256) kept.pop_front();
		kept.push_back(acb_cs);
		submit_one(kept.back().data(), static_cast<uint32_t>(kept.back().size()), "acb-state");
		submit_one(ib + from, to - from, "acb");
	}
	acb_cs_track(ib + from, to - from);
	acb_inherit_track(ib + from, to - from); // experiment 0403
	t_keep_waits.clear();
}

static bool acb_ready(const uint32_t* ib, uint32_t num_dwords) {
	const int         ring       = acb_ring(ib, num_dwords); // ADR 0009
	uint32_t done = 0;
	for (const auto& e: g_acb_heads) {
		if (e.ib == ib && e.num_dwords == num_dwords) done = e.done;
	}
	std::vector<uint64_t> written;
	for (uint32_t i = 0; i < num_dwords;) {
		const uint32_t h = ib[i];
		const uint32_t type = h >> 30u;
		uint32_t len = 1;
		if (type == 3 || type == 0) { const uint32_t c = (h >> 16u) & 0x3fffu; len = c == 0x3fffu ? 1 : c + 2; }
		if (i + len > num_dwords) break;
		const uint32_t  op = (h >> 8u) & 0xffu;
		const uint32_t* p  = ib + i;
		if (type == 3) {
			const uint32_t dst_sel = len >= 2 ? (p[1] >> 8u) & 0xfu : 0;
			if (op == 0x37 && len >= 4 && (dst_sel == 1 || dst_sel == 2 || dst_sel == 5)) written.push_back((p[2] & ~3u) | (static_cast<uint64_t>(p[3] & 0xffffu) << 32u));
			else if (op == 0x49 && len >= 6) written.push_back((p[3] & ~3u) | (static_cast<uint64_t>(p[4] & 0xffffu) << 32u));
			else if (op == 0x47 && len >= 4) written.push_back((p[2] & ~3u) | (static_cast<uint64_t>(p[3] & 0xffffu) << 32u));
			else if (op == 0x1e && len >= 4) written.push_back((p[2] & ~3u) | (static_cast<uint64_t>(p[3] & 0xffffu) << 32u));
			else if ((op == 0x3c || op == 0x93) && len >= 4 && ((p[1] >> 4u) & 1u) != 0) {
				const uint64_t label = (p[2] & ~3u) | (static_cast<uint64_t>(p[3] & 0xffffu) << 32u);
				// Experiment 0055: a wait the ring's pending writes will satisfy does not hold the buffer back.
				if (i >= done && std::find(written.begin(), written.end(), label) == written.end() && !wait_satisfied(p, op == 0x93) &&
				    !ring_will_satisfy(p, op == 0x93, ring)) {
					if (wait_trace()) {
						static std::atomic<uint32_t> n_held {0};
						static const uint32_t*       last_ib  = nullptr;
						static uint32_t              last_pos = ~0u;
						if ((ib != last_ib || i != last_pos) && n_held++ < 20000) { // once per buffer and wait
							last_ib  = ib;
							last_pos = i;
							char           pend[160];
							describe_pending(label, pend, sizeof(pend));
							const uint64_t now_v = op == 0x93 ? *reinterpret_cast<const volatile uint64_t*>(label & ~7ull) : *reinterpret_cast<const volatile uint32_t*>(label & ~3ull);
							const uint64_t ref   = op == 0x93 && len >= 8 ? (p[4] | (static_cast<uint64_t>(p[5]) << 32u)) : p[4];
							journal("wait trace: t %.3f s acb %u dwords at %p (queue %d) held back by its wait at %u (ring %d) on 0x%" PRIx64 ": function %u reference 0x%" PRIx64 " value 0x%" PRIx64 "; %s\n", timing_now(), num_dwords,
							        static_cast<const void*>(ib), t_queue_idx, i, ring, label, p[1] & 7u, ref, now_v, pend);
						}
					}
					t_unready.ib         = ib;
					t_unready.num_dwords = num_dwords;
					t_unready.pos        = i;
					t_unready.function   = p[1] & 7u;
					t_unready.label      = label;
					t_unready.value      = op == 0x93 ? *reinterpret_cast<const volatile uint64_t*>(label) : *reinterpret_cast<const volatile uint32_t*>(label);
					t_unready.reference  = op == 0x93 ? (p[4] | (static_cast<uint64_t>(p[5]) << 32u)) : p[4];
					{
						std::vector<uint64_t> after;
						for (uint32_t k = i + len; k < num_dwords;) {
							const uint32_t hk = ib[k];
							const uint32_t tk = hk >> 30u;
							uint32_t lk = 1;
							if (tk == 3 || tk == 0) { const uint32_t ck = (hk >> 16u) & 0x3fffu; lk = ck == 0x3fffu ? 1 : ck + 2; }
							if (k + lk > num_dwords) break;
							if (tk == 3) {
								const uint32_t ok = (hk >> 8u) & 0xffu;
								const uint32_t* q = ib + k;
								if (ok == 0x37 && lk >= 4) after.push_back((q[2] & ~3u) | (static_cast<uint64_t>(q[3] & 0xffffu) << 32u));
								else if (ok == 0x49 && lk >= 6) after.push_back((q[3] & ~3u) | (static_cast<uint64_t>(q[4] & 0xffffu) << 32u));
								else if ((ok == 0x47 || ok == 0x1e) && lk >= 4) after.push_back((q[2] & ~3u) | (static_cast<uint64_t>(q[3] & 0xffffu) << 32u));
							}
							k += lk;
						}
						std::lock_guard lk2(g_unready_mutex);
						g_unready_writes = std::move(after);
					}
					g_unready_label      = label;
					if (i > done) {
						(void)tail_is_light;
						SoftCp::clear_gpu_executed();
						static std::atomic<uint64_t> n_head {0};
						if (journal_sample(n_head, 0x3ffu)) journal("acb head: %u of %u dwords go ahead of the wait at %u on 0x%" PRIx64 "\n", i - done, num_dwords, i, label);
						t_ring = ring;
						submit_segment(ib, num_dwords, done, i);
						chain_flush(6); // ADR 0010: the head's marks are taken below
						t_ring = bc5::direct::kGfxRing;
						AcbHead* e = nullptr;
						for (auto& x: g_acb_heads) {
							if (x.ib == ib && x.num_dwords == num_dwords) e = &x;
						}
						if (e == nullptr) {
							if (g_acb_heads.size() >= 64) g_acb_heads.erase(g_acb_heads.begin());
							g_acb_heads.push_back({ib, num_dwords, 0, {}, g_m11_reopens.load()}); // exp 0401 e11: + the reopen count
							e = &g_acb_heads.back();
						}
						m11_head_check(e->marks, e->reopens, "head"); // exp 0401 e11 (tag m11): BC5_DIRECT_RESET_REPLAY_ACB
						e->done = i;
						for (auto& g: SoftCp::t_gpu_done) e->marks.push_back(std::move(g));
						SoftCp::clear_gpu_executed();
					}
					return false;
				}
			}
		}
		i += len;
	}
	g_unready_label = 0;
	return true;
}

// Experiment 0050: a wait of this buffer was given up or broken as a cycle, so what it waited for
// (often the arguments of its indirect dispatches) may not have been written yet: trusted
// arguments are checked again in it.
static thread_local bool t_wait_given_up = false;

// ADR 0010 (experiment 0163, BC5_DIRECT_CHAIN=1): the buffers one call into the direct path hands over
// (the game thread's submit ioctl: cc + hib x3, or its dcb list; the ring thread's poll slice of a
// queue) are laid end to end in one scratch IB and go to the kernel as one submission, the console's
// one stream — one filter pass, one BO list, one CS, one fence, one completion item instead of one
// per buffer (F210: 130 submissions a frame took three quarters of the title's render thread). A chain
// closes when the call ends, before a wait is served on the CPU (the head must be on the ring first),
// when the ring, the GDS setting or the class (graphics / compute) changes, around a buffer with
// COND_EXEC (its skip counts are offsets the host's insertions are grown around per IB), at 1 Mi dwords,
// and for the instrumented diagnostic copies (which keep the old path). The soft CP gets its marks
// per title buffer, split back from the chain's executed offsets (as alias_gpu_executed did for a
// prefixed piece). The policy (what may share a chain, and why) is docs/decisions/0010-submission-chains.md.
struct ChainSeg {
	const uint32_t* src;      // the title's buffer (nullptr: host-built, no soft-CP marks)
	uint32_t        n;        // its dwords
	uint32_t        prefix;   // host prefix dwords laid in front of it
	uint32_t        off;      // where the prefix starts in the chain
	bool            given_up; // t_wait_given_up when it was appended (experiment 0054's indirect-draw drop)
	std::vector<uint32_t> keep; // ADR 0010 section B: the waits kept for the GPU, as chain offsets (t_keep_waits is per buffer)
};
struct Chain {
	std::vector<uint32_t> buf;
	std::vector<ChainSeg> segs;
	int                   ring    = bc5::direct::kGfxRing;
	bool                  compute = false; // acb class
};
// ADR 0010 section B (BC5_DIRECT_CHAIN=2): a game thread's chain is held open across its ioctls and may be
// submitted by another thread (the watchdog at the hold bound, a thread at an observe point), so the slot
// carries what the owner's thread-local state used to: the soft-CP replays waiting for the chain's marks,
// the marks themselves, and the owner's state (inside Direct::submit or not).
struct ChainSoft {
	const uint32_t* dwords;
	uint32_t        n;
	const char*     kind;
	std::shared_ptr<const std::vector<uint32_t>> owned {}; // host-generated replay only; captured by value with e
	uint64_t pub = 0; // exp 0417 (BC5_R3_EOP_STAT): the running number of this chained EOP publication, 0 when not counted
};
// ADR 0013 (experiment 0226): a wait a held chain carries for the GPU, released when
// its label is satisfied or its writer is on a ring.
struct HoldCond {
	uint32_t        pkt[8] {};
	const uint32_t* p     = nullptr; // the wait in the title's buffer: its kept offset is found by it
	bool            is64  = false;
	uint64_t        label = 0, t0 = 0;
};
struct ChainSlot {
	Chain                        c;
	std::mutex                   mu;         // c, soft, marks, open_ns, in_submit
	std::recursive_mutex         flush_mu;   // held through a submission: the owner's next flush waits for the watchdog's (ring order); recursive: submit_now's mapping sync calls wait_jobs -> chain_flush on the same thread
	uint64_t                     open_ns    = 0;     // when the first segment was appended
	bool                         cross      = false; // held across ioctls (set at chain_begin on a game thread in mode 2)
	bool                         in_submit  = false; // the owner is inside Direct::submit (a buffer may be split at a wait)
	bool                         registered = false;
	std::vector<ChainSoft>       soft;  // replays posted once the chain that holds their buffers is submitted
	std::vector<SoftCp::GpuDone> marks; // the marks of the chains that carried the pending replays' buffers
	std::vector<HoldCond>        hold;        // ADR 0013: the conditions the chain waits for before it may go
	std::vector<uint64_t>        hold_writes; // ADR 0013: the labels the held chain's segments write
	std::vector<uint64_t>        f10_writes; // exp 0430 F10: the memory addresses the open chain's packets write (RELEASE_MEM/EOP data, WRITE_DATA)
	std::vector<uint64_t>        f10_flight; // exp 0430 F10: the write set of the chain being submitted now (its writes not registered yet)
	bool                         f10_wanted = false; // exp 0430 F10: an acb waits on one of them; the owner flushes at its call's end
	std::atomic<uint64_t>        f16_done {0}; // exp 0430 F16: bumped when a submit_now of this slot's chain has returned (after its f10_flight is cleared)
	std::atomic<int>             f16_phase {0}; // exp 0430 F16: 0 idle, 1 in chain_submit before the device lock (back-pressure), 2 asking for g_dev_mutex, 3 holding it, 4 draining the GPU (wait_jobs)
	~ChainSlot();
};
static thread_local ChainSlot g_chain_tl;
// Experiment 0415 (fs415c): what chain_submit knows about the chain it hands to submit_now (the same thread, the next
// call): when its first segment was appended, why it was flushed, how many of the title's buffers it holds.
static thread_local uint64_t t_fs415_open_ns = 0;
static thread_local int      t_fs415_why     = -1;
static thread_local uint32_t t_fs415_segs    = 0;
static std::mutex             g_chains_mu;
static std::vector<ChainSlot*> g_chains; // the registered (cross) slots, for the watchdog and the observe points
static std::mutex              g_f10_reg_mu; // exp 0430 F10: its own registry of the slots; only chain_register and ~ChainSlot take it, nothing submits under it
static std::vector<ChainSlot*> g_f10_reg;
static thread_local ChainSlot*  t_f16_slot = nullptr; // exp 0430 F16: the slot whose chain this thread's submit_now carries
static const int g_chain_mode = [] {
	const char* e = std::getenv("BC5_DIRECT_CHAIN");
	if (e == nullptr) return 0;
	const long v = std::strtol(e, nullptr, 10);
	return v == 0 && std::strcmp(e, "0") != 0 ? 1 : static_cast<int>(v < 0 ? 0 : (v > 2 ? 2 : v));
}();
static uint64_t chain_hold_ns() {
	static const uint64_t v = 2000ull * 1000ull; /* exp 0419: a constant (was BC5_DIRECT_CHAIN_HOLD_US, never varied) */
	return v;
}
// ADR 0013 (experiment 0226; F312): at a game-thread wait on the two-ring path
// whose label is unsatisfied and whose writer is not on a ring, the title's thread does not poll: the wait is kept
// for the GPU and the thread's chain is held until the label is satisfied or its writer is on a ring. The title's
// thread goes on and submits the writer itself, as on the console (F284, exp 0224). A holder thread submits the
// chain; owner flushes and the observe points wait for it; after 100 ms of the
// wait the kept wait is dropped (today's give-up). The host never writes a label.
static uint64_t hold_ns() {
	return 100ull * 1'000'000ull;
}
static std::atomic<uint64_t>   g_hold_writer {0}, g_hold_sat {0}, g_hold_lost {0}, g_hold_ns_sum {0}, g_hold_ns_max {0};
static void                    chain_submit(ChainSlot& s, int why, bool foreign);
// The labels a buffer writes (WRITE_DATA, RELEASE_MEM, EVENT_WRITE_EOP and 0x1e, as acb_ready's scan reads them).
// Caller holds s.mu.
static void hold_note_writes(ChainSlot& s, const uint32_t* ib, uint32_t n) {
	for (uint32_t k = 0; k < n;) {
		const uint32_t hk = ib[k], tk = hk >> 30u;
		uint32_t       lk = 1;
		if (tk == 3 || tk == 0) {
			const uint32_t ck = (hk >> 16u) & 0x3fffu;
			lk                = ck == 0x3fffu ? 1 : ck + 2;
		}
		if (k + lk > n) break;
		if (tk == 3) {
			const uint32_t  op = (hk >> 8u) & 0xffu;
			const uint32_t* q  = ib + k;
			uint64_t        a  = 0;
			if (op == 0x37 && lk >= 4) a = (q[2] & ~3u) | (static_cast<uint64_t>(q[3] & 0xffffu) << 32u);
			else if (op == 0x49 && lk >= 6) a = (q[3] & ~3u) | (static_cast<uint64_t>(q[4] & 0xffffu) << 32u);
			else if ((op == 0x47 || op == 0x1e) && lk >= 4) a = (q[2] & ~3u) | (static_cast<uint64_t>(q[3] & 0xffffu) << 32u);
			if (a != 0) s.hold_writes.push_back(a);
		}
		k += lk;
	}
}
// Releases the slot's conditions that are met: the label satisfied, or its writer on a ring. Past the bound the kept
// wait is dropped from its segment, or from the owner's t_keep_waits before it is appended (today's give-up). Returns
// whether nothing is held any more; block: poll until then (the bound ends it in any case).
static bool hold_release(ChainSlot& s, bool block) {
	for (;;) {
		{
			std::lock_guard lk(s.mu);
			const uint64_t now = SoftCp::now_ns();
			for (size_t k = 0; k < s.hold.size();) {
				HoldCond&  c    = s.hold[k];
				const bool sat  = wait_satisfied(c.pkt, c.is64);
				const bool wr   = !sat && ring_will_satisfy(c.pkt, c.is64, bc5::direct::kGfxRing);
				const bool lost = !sat && !wr && now - c.t0 >= hold_ns();
				if (!sat && !wr && !lost) {
					k++;
					continue;
				}
				const uint64_t held = now - c.t0;
				if (lost) {
					bool dropped = false;
					for (auto& seg: s.c.segs) {
						if (seg.src != nullptr && c.p >= seg.src && c.p < seg.src + seg.n) {
							std::erase(seg.keep, seg.off + seg.prefix + static_cast<uint32_t>(c.p - seg.src));
							seg.given_up = true;
							dropped      = true;
						}
					}
					if (!dropped && &s == &g_chain_tl) {
						std::erase(t_keep_waits, c.p);
						t_wait_given_up = true;
						dropped         = true;
					}
					if (!dropped) { // its segment is not appended yet and this is not the owner: it stays held until it is (never a kept wait without its writer)
						k++;
						continue;
					}
					journal("hold tail: the wait on 0x%" PRIx64 " GIVEN UP after %.1f ms: its kept wait dropped, the chain goes\n", c.label, static_cast<double>(held) / 1e6);
				}
				g_hold_ns_sum += held;
				for (uint64_t m = g_hold_ns_max.load(); held > m && !g_hold_ns_max.compare_exchange_weak(m, held);) {
				}
				(sat ? g_hold_sat : (wr ? g_hold_writer : g_hold_lost))++;
				if (!lost) {
					const uint64_t r = g_hold_writer.load() + g_hold_sat.load();
					if (r <= 50 || (r & 0x3fu) == 0) journal("hold tail: released after %.3f ms on 0x%" PRIx64 ": %s (%" PRIu64 " released so far)\n", static_cast<double>(held) / 1e6, c.label,
															 sat ? "label satisfied" : "writer on a ring", r);
				}
				s.hold.erase(s.hold.begin() + static_cast<std::ptrdiff_t>(k));
			}
			if (s.hold.empty()) return true;
		}
		if (!block) return false;
		std::this_thread::sleep_for(std::chrono::microseconds(20));
	}
}
static std::atomic<uint64_t> g_chain_flushes {0}, g_chain_segments {0}, g_chain_single {0}, g_chain_dwords {0}, g_chain_cond_segs {0};
static std::atomic<uint64_t> g_chain_why[12]; // 0 end, 1 wait, 2 ring/class, 3 cond-past-end, 4 size, 5 drain, 6 acb head, 7 other, 8 observe, 9 hold (watchdog), 10 hold (owner)
static void submit_now(const uint32_t* ib, uint32_t num_dwords, const char* kind, int ring, const Chain* chain);
static bool chain_on() {
	return g_chain_mode >= 1 && g_stage == Stage::All;
}
static bool chain_cross() {
	return chain_on() && g_chain_tl.cross;
}
static bool chain_cross_mode() {
	return g_chain_mode >= 2;
}
// ADR 0010 section A: a COND_EXEC's skip count only covers dwords of its own buffer, and the passes that
// grow an IB grow the counts per packet now, so a COND_EXEC no longer closes a chain. One whose range runs
// past the end of its buffer is malformed for that reasoning (the console would skip into whatever
// follows the buffer in memory); such a buffer still goes alone, and is counted.
static bool ib_cond_past_end(const uint32_t* ib, uint32_t n, bool* any) {
	bool past = false;
	for (uint32_t q = 0; q < n;) {
		const uint32_t h = ib[q], type = h >> 30u;
		uint32_t       len = 1;
		if (type == 3 || type == 0) { const uint32_t c = (h >> 16u) & 0x3fffu; len = c == 0x3fffu ? 1 : c + 2; }
		if (type == 3 && ((h >> 8u) & 0xffu) == 0x22) {
			*any = true;
			if (len == 5 && q + 5 + (ib[q + 4] & 0x3fffu) > n) past = true;
		}
		q += len;
	}
	return past;
}
// Posts the slot's pending soft-CP replays behind the chain's fence item, each with the marks gathered so
// far (section B.4). Caller holds slot.mu. The marks stay while the owner is inside Direct::submit: the
// buffer being split there gets its replay later, with the marks of every chain that carried a piece of it.
// Experiment 0417: BC5_R3_EOP_STAT=1, measurement only. How many chained EOP publications fall between one
// publication's push and its deferred callback; the ring that exp 0416 removed was wrong from 4,096 on.
static std::atomic<uint64_t> g_eop_stat_pub {0}, g_eop_stat_max {0}, g_eop_stat_seen {0};
static bool eop_stat_on() {
	static const bool on = [] {
		const char* e = BC5_DIAG_ENV("BC5_R3_EOP_STAT");
		return e != nullptr && e[0] != '\0' && !(e[0] == '0' && e[1] == '\0');
	}();
	return on;
}
static void eop_stat_callback(uint64_t pub) {
	const uint64_t d = g_eop_stat_pub.load(std::memory_order_relaxed) - pub;
	const uint64_t n = g_eop_stat_seen.fetch_add(1, std::memory_order_relaxed) + 1;
	uint64_t       m = g_eop_stat_max.load(std::memory_order_relaxed);
	while (d > m && !g_eop_stat_max.compare_exchange_weak(m, d, std::memory_order_relaxed)) {
	}
	if (d > m || n == 1) {
		journal("eop stat (exp 0417): %" PRIu64 " chained EOP publications between a push and its callback (%s; %" PRIu64 " callbacks so far; the old ring wrapped at 4096)\n", d,
		        d > m ? "a new maximum" : "the first callback", n);
	}
}
static void chain_post_soft_locked(ChainSlot& s) {
	if (s.soft.empty()) return;
	auto marks = std::make_shared<std::vector<SoftCp::GpuDone>>(s.marks);
	for (const ChainSoft& e: s.soft) {
		post([e, marks](bool failed) {
			if (failed) journal("soft-cp: %s %u dwords at %p replayed in full after a failed submission\n", e.kind, e.n, static_cast<const void*>(e.dwords));
			SoftCp::t_gpu_done = failed ? std::vector<SoftCp::GpuDone>() : *marks;
			if (e.pub != 0) eop_stat_callback(e.pub); // exp 0417
			SoftCp::submit(e.dwords, e.n, e.kind);
			SoftCp::t_gpu_done.clear();
		});
	}
	s.soft.clear();
	if (!s.in_submit) s.marks.clear();
}
// Submits the slot's chain, from whatever thread. foreign: not the owner (the watchdog, an observe point):
// a chain whose owner is inside Direct::submit is left to the owner (it flushes at its own waits, and a
// buffer split at a wait must not have its head submitted from elsewhere between the pieces).
static void chain_submit(ChainSlot& s, int why, bool foreign) {
	{ // nothing to do: before the flush lock (a re-entrant call from inside submit_now sees its chain already taken)
		std::lock_guard lk(s.mu);
		if (s.c.segs.empty() || (foreign && s.in_submit)) return;
	}
	if (!hold_release(s, !(foreign && (why == 9 || why == 11)))) return; // ADR 0013 (experiment 0226)
	std::lock_guard order(s.flush_mu);
	Chain    mine;
	uint64_t fs_open = 0; // experiment 0415 (fs415c)
	{
		std::lock_guard lk(s.mu);
		Chain& c = s.c;
		if (c.segs.empty() || (foreign && s.in_submit)) return;
		mine.buf.swap(c.buf);
		mine.segs.swap(c.segs);
		mine.ring    = c.ring;
		mine.compute = c.compute;
		fs_open      = s.open_ns;
		s.open_ns    = 0;
		s.hold_writes.clear(); // ADR 0013
		s.f10_flight.swap(s.f10_writes); // exp 0430 F10: in flight until submit_now has registered its writes
		s.f10_writes.clear();
		s.f10_wanted = false;
	}
	g_chain_flushes++;
	g_chain_segments += mine.segs.size();
	g_chain_dwords += mine.buf.size();
	if (mine.segs.size() == 1) g_chain_single++;
	g_chain_why[why < 12 ? why : 7]++;
	{
		static double last = 0;
		const double  now  = timing_now();
		if (now - last >= 10.0) {
			last = now;
			journal("chains: %" PRIu64 " submitted, %" PRIu64 " segments (%" PRIu64 " single, %" PRIu64 " with cond_exec), %" PRIu64 " dwords; closed by: end %" PRIu64 " wait %" PRIu64 " ring/class %" PRIu64 " cond_exec %" PRIu64 " size %" PRIu64 " drain %" PRIu64 " acb-head %" PRIu64 " other %" PRIu64 " observe %" PRIu64 " hold-wd %" PRIu64 " hold-end %" PRIu64 "\n",
			        g_chain_flushes.load(), g_chain_segments.load(), g_chain_single.load(), g_chain_cond_segs.load(), g_chain_dwords.load(), g_chain_why[0].load(), g_chain_why[1].load(),
			        g_chain_why[2].load(), g_chain_why[3].load(), g_chain_why[4].load(), g_chain_why[5].load(), g_chain_why[6].load(), g_chain_why[7].load(), g_chain_why[8].load(),
			        g_chain_why[9].load(), g_chain_why[10].load());
		}
	}
	t_fs415_open_ns = fs_open; // experiment 0415 (fs415c)
	t_fs415_why     = why;
	t_fs415_segs    = static_cast<uint32_t>(mine.segs.size());
	ChainSlot* const f16_prev = t_f16_slot; // exp 0430 F16
	t_f16_slot = &s;
	s.f16_phase.store(1);
	submit_now(mine.buf.data(), static_cast<uint32_t>(mine.buf.size()), mine.compute ? "acb" : "dcb", mine.ring, &mine);
	{ // exp 0430 F10: its writes are registered now
		std::lock_guard lk(s.mu);
		s.f10_flight.clear();
	}
	s.f16_phase.store(0); // exp 0430 F16: after the clear, so a waiter that saw the flight set sees the bump
	s.f16_done.fetch_add(1);
	t_f16_slot = f16_prev;
	if (s.cross) { // section B.4: the marks this submission produced belong to the slot; replays wait for the chain to be empty
		std::lock_guard lk(s.mu);
		s.marks.insert(s.marks.end(), SoftCp::t_gpu_done.begin(), SoftCp::t_gpu_done.end());
		SoftCp::t_gpu_done.clear();
		if (s.c.segs.empty() && !s.in_submit) chain_post_soft_locked(s);
	}
}
static void chain_flush(int why) {
	chain_submit(g_chain_tl, why, false);
}
// Section B.2: the hold bound. A watchdog submits a game thread's chain that has been open for
// 2000 us (exp 0419: a constant) and whose owner is not inside Direct::submit; the owner wakes it
// when a chain opens and when it leaves Direct::submit with the chain open.
static std::mutex              g_chainwd_mu;
static std::condition_variable g_chainwd_cv;
static uint64_t                g_chainwd_gen = 0;
static void chainwd_wake() {
	{
		std::lock_guard lk(g_chainwd_mu);
		g_chainwd_gen++;
	}
	g_chainwd_cv.notify_one();
}
static void chainwd_thread() {
	pthread_setname_np(pthread_self(), "bc5-chainwd");
	static std::atomic<uint64_t> n_wd {0};
	for (;;) {
		uint64_t gen = 0;
		{
			std::lock_guard lk(g_chainwd_mu);
			gen = g_chainwd_gen;
		}
		uint64_t deadline = ~0ull;
		{
			std::lock_guard lk(g_chains_mu);
			for (ChainSlot* s: g_chains) {
				std::lock_guard sl(s->mu);
				if (!s->c.segs.empty() && !s->in_submit && s->hold.empty() && s->open_ns + chain_hold_ns() < deadline) deadline = s->open_ns + chain_hold_ns();
			}
		}
		{
			std::unique_lock lk(g_chainwd_mu);
			const uint64_t now = SoftCp::now_ns();
			if (deadline == ~0ull) g_chainwd_cv.wait(lk, [&] { return g_chainwd_gen != gen; });
			else if (now < deadline) g_chainwd_cv.wait_for(lk, std::chrono::nanoseconds(deadline - now), [&] { return g_chainwd_gen != gen; });
		}
		std::lock_guard lk(g_chains_mu);
		for (ChainSlot* s: g_chains) {
			bool due = false;
			{
				std::lock_guard sl(s->mu);
				due = !s->c.segs.empty() && !s->in_submit && s->hold.empty() && SoftCp::now_ns() >= s->open_ns + chain_hold_ns();
			}
			if (due) {
				chain_submit(*s, 9, true);
				if ((n_wd++ & 0x3ffu) == 0) journal("chain hold: the watchdog submitted a chain of a game thread (%" PRIu64 " so far)\n", n_wd.load());
			}
		}
	}
}
static void chain_register(ChainSlot& s) {
	std::lock_guard lk(g_chains_mu);
	if (s.registered) return;
	g_chains.push_back(&s);
	s.registered = true;
	{ // exp 0430 F10
		std::lock_guard rk(g_f10_reg_mu);
		g_f10_reg.push_back(&s);
	}
	static std::once_flag started;
	std::call_once(started, [] {
		journal("chains: mode 2, a game thread's chain is held across its ioctls for up to %" PRIu64 " us\n", chain_hold_ns() / 1000);
		std::thread(chainwd_thread).detach();
	});
}
ChainSlot::~ChainSlot() {
	if (!registered) return;
	std::lock_guard lk(g_chains_mu);
	std::erase(g_chains, this);
	std::lock_guard rk(g_f10_reg_mu); // exp 0430 F10 holds it while it touches this slot
	std::erase(g_f10_reg, this);
}
// Every registered chain is submitted now (the flip's drain, the observe points of section B.2).
static void chain_flush_all(int why) {
	std::lock_guard lk(g_chains_mu);
	for (ChainSlot* s: g_chains) chain_submit(*s, why, s != &g_chain_tl);
}
static void chain_observe() {
	if (g_chain_mode >= 2) chain_flush_all(8);
}
static void chain_soft_push(const uint32_t* dwords, uint32_t n, const char* kind) {
	ChainSlot&      s = g_chain_tl;
	std::lock_guard lk(s.mu);
	s.soft.push_back({dwords, n, kind});
	if (s.c.segs.empty() && !s.in_submit) chain_post_soft_locked(s); // nothing of the buffer is held back (flushed at a wait, or never appended)
}
// Experiment 0416 (Codex's review of exp 0413): host-generated packets must survive both the held chain and the
// completion queue. Guest command-buffer replays keep their borrowed-buffer semantics.
static void chain_soft_push_copy(const uint32_t* dwords, uint32_t n, const char* kind) {
	auto owned = std::make_shared<const std::vector<uint32_t>>(dwords, dwords + n);
	ChainSlot& s = g_chain_tl;
	std::lock_guard lk(s.mu);
	s.soft.push_back({owned->data(), n, kind, owned, eop_stat_on() ? g_eop_stat_pub.fetch_add(1, std::memory_order_relaxed) + 1 : 0}); // exp 0417: its running number
	if (s.c.segs.empty() && !s.in_submit) chain_post_soft_locked(s);
}
// Appends `pre` (host-built, may be empty) then `ib` to the thread's chain, closing it first if the buffer
// cannot share it. host_built: no soft-CP marks for `ib` (a state prefix submitted on its own).
// exp 0430 F10: the memory addresses ib's packets write (RELEASE_MEM / EVENT_WRITE_EOP with data, WRITE_DATA to memory)
static void f10_note(std::vector<uint64_t>& out, const uint32_t* ib, uint32_t n) {
	for (uint32_t q = 0; q < n;) {
		const uint32_t h = ib[q], type = h >> 30u;
		uint32_t       len = 1;
		if (type == 3 || type == 0) {
			const uint32_t c = (h >> 16u) & 0x3fffu;
			len = c == 0x3fffu ? 1 : c + 2;
		}
		if (q + len > n) break;
		if (type == 3) {
			const uint32_t* w  = ib + q;
			const uint32_t  op = (h >> 8u) & 0xffu;
			auto addr = [w](int lo, int hi) { return (static_cast<uint64_t>(w[lo]) & ~3ull) | (static_cast<uint64_t>(w[hi] & 0xffffu) << 32u); };
			uint64_t a = 0;
			if (op == 0x49 && len >= 8 && (w[2] >> 29u) != 0) a = addr(3, 4);
			else if (op == 0x47 && len >= 6 && (w[3] >> 29u) != 0) a = addr(2, 3);
			else if (op == 0x37 && len >= 5) {
				const uint32_t d = (w[1] >> 8u) & 0xfu;
				if (d == 1 || d == 2 || d == 5) a = addr(2, 3);
			}
			if (a != 0 && std::find(out.begin(), out.end(), a) == out.end()) out.push_back(a);
		}
		q += len;
	}
}
static void chain_append(const uint32_t* pre, uint32_t pre_n, const uint32_t* ib, uint32_t n, const char* kind, bool host_built) {
	ChainSlot& s       = g_chain_tl;
	const bool compute = std::strncmp(kind, "acb", 3) == 0;
	const int  ring    = job_ring(kind);
	bool       any_cond = false;
	const bool cond_past = ib_cond_past_end(ib, n, &any_cond);
	if (any_cond) g_chain_cond_segs++;
	bool opened = false;
	for (;;) {
		int why = -1;
		{
			std::lock_guard lk(s.mu);
			Chain& c = s.c;
			if (!c.segs.empty() && (c.compute != compute || c.ring != ring)) why = 2;
			else if (!c.segs.empty() && cond_past) why = 3;
			else if (!c.segs.empty() && c.buf.size() + pre_n + n > (1u << 20u)) why = 4;
			if (why < 0) {
				if (c.segs.empty()) {
					c.compute = compute;
					c.ring    = ring;
					c.buf.clear();
					s.open_ns = SoftCp::now_ns();
					opened    = true;
				}
				ChainSeg seg {host_built ? nullptr : ib, n, pre_n, static_cast<uint32_t>(c.buf.size()), t_wait_given_up, {}};
				for (const uint32_t* w: t_keep_waits) { // section B.3: the kept waits travel with the segment
					if (w >= ib && w < ib + n) seg.keep.push_back(seg.off + pre_n + static_cast<uint32_t>(w - ib));
				}
				std::erase_if(t_keep_waits, [ib, n](const uint32_t* w) { return w >= ib && w < ib + n; });
				if (pre_n != 0) c.buf.insert(c.buf.end(), pre, pre + pre_n);
				c.buf.insert(c.buf.end(), ib, ib + n);
				c.segs.push_back(std::move(seg));
				if (!s.hold.empty()) hold_note_writes(s, ib, n); // ADR 0013
				f10_note(s.f10_writes, ib, n); // exp 0430 F10 (graphics and compute chains)
				break;
			}
		}
		chain_flush(why);
	}
	if (cond_past) chain_flush(3);
	else if (opened && s.cross) chainwd_wake();
}
static void chain_begin() {
	if (!chain_on()) return;
	ChainSlot& s = g_chain_tl;
	if (g_chain_mode >= 2 && on_game_thread()) { // section B.1: the chain stays open across the thread's ioctls
		if (!s.registered) chain_register(s);
		s.cross = true;
		return;
	}
	chain_flush(7); // nothing should be open here
	SoftCp::clear_gpu_executed(); // the marks of this call's buffers start here (Direct::submit skips its per-buffer clear)
}
static void chain_end() {
	if (!chain_on()) return;
	ChainSlot& s = g_chain_tl;
	if (s.cross) {
		bool over = false;
		{
			std::lock_guard lk(s.mu);
			over = !s.c.segs.empty() && s.hold.empty() && SoftCp::now_ns() >= s.open_ns + chain_hold_ns();
			if (!over && !s.c.segs.empty() && s.f10_wanted && s.hold.empty()) over = true; // exp 0430 F10: an acb waits on one of its writes
			if (s.c.segs.empty() && !s.in_submit) chain_post_soft_locked(s);
		}
		if (over) chain_flush(10);
		return;
	}
	chain_flush(0);
}
// Section B.3: the owner's state for the watchdog, around Direct::submit; the thread's own marks (a
// wait served on the CPU marks itself executed) go to the slot when the buffer is done with.
struct ChainInSubmit {
	ChainSlot* s = nullptr;
	explicit ChainInSubmit(bool cross) {
		if (!cross) return;
		s = &g_chain_tl;
		std::lock_guard lk(s->mu);
		s->in_submit = true;
	}
	~ChainInSubmit() {
		if (s == nullptr) return;
		bool open = false;
		{
			std::lock_guard lk(s->mu);
			s->in_submit = false;
			s->marks.insert(s->marks.end(), SoftCp::t_gpu_done.begin(), SoftCp::t_gpu_done.end());
			SoftCp::t_gpu_done.clear();
			open = !s->c.segs.empty();
			if (!open) chain_post_soft_locked(*s);
		}
		if (open) chainwd_wake();
	}
};
// The soft-CP marks of a chain, per title buffer: the executed offsets inside a segment, less its start.
static void chain_mark_executed(const Chain* chain, const uint32_t* ib, uint32_t num_dwords, const std::vector<uint32_t>& offsets) {
	if (chain == nullptr) {
		SoftCp::set_gpu_executed(ib, num_dwords, offsets);
		return;
	}
	std::vector<uint32_t> local;
	for (const ChainSeg& s: chain->segs) {
		if (s.src == nullptr) continue;
		const uint32_t lo = s.off + s.prefix, hi = lo + s.n;
		local.clear();
		for (const uint32_t o: offsets) {
			if (o >= lo && o < hi) local.push_back(o - lo);
		}
		SoftCp::set_gpu_executed(s.src, s.n, local);
	}
}
static bool chain_given_up_at(const Chain* chain, uint32_t q) {
	if (chain == nullptr) return t_wait_given_up;
	for (const ChainSeg& s: chain->segs) {
		if (q >= s.off && q < s.off + s.prefix + s.n) return s.given_up;
	}
	return false;
}

// Experiment 0055: the label writes with immediate data
// (RELEASE_MEM, EVENT_WRITE_EOP, WRITE_DATA to memory) of the jobs on the ring that have not
// completed yet. A cross-queue wait whose label the last such write sets to a value that satisfies
// it needs no CPU-side wait: the job that writes it runs ahead of this one on the one ring, so the
// WAIT_REG_MEM stays in the buffer for the GPU (FilterOptions::keep_wait_offsets). The second
// title's scene change: a label set to 0 by a compute job 14-15 ms after the graphics buffer's
// 8 ms wait for it was given up, the compute job already submitted (run 244). As AnyPS5's
// noteHeldAtSubmit treats a wait whose write is recorded but not finished.
// ADR 0009: only a write on the ring the waiting job goes to counts (two rings run side by side);
// the last write is the last registered (sequence numbers are per ring).
struct PendingLabelWrite {
	uint64_t label;
	uint64_t value;
	uint64_t seq;
	bool     is64;
	int      ring  = bc5::direct::kGfxRing;
	uint64_t order = 0;
};
static std::mutex                          g_plw_mutex;
static std::vector<PendingLabelWrite>      g_plw;
// ADR 0008 step 2, experiment 0074: at every wait of a graphics buffer that is not satisfied when
// reached, the full-state prefix of the later piece is built (bc5::full_state, from the graphics
// queue's state before the buffer that piece_check keeps), and splits, prefix sizes and the time
// are counted. What then happens to the wait (kept for the GPU by ring order, served on the CPU,
// given up or a cycle) is counted too. Reported with piece_check's journal line.
// ADR 0008 step 3: a game-thread graphics buffer is split at a wait that was neither satisfied, nor
// kept for the GPU by ring order, nor served within the limit (given up, or a cycle): the head goes
// to the GPU so that its own label writes run, the wait is tried again for as long, and the rest
// follows later behind the full-state prefix (bc5::full_state; experiments 0073-0075) instead of
// state_prefix().
static std::atomic<uint64_t> g_full_pieces {0}, g_full_ok {0}, g_full_failed {0};
#ifndef BC5_LEAN
static std::atomic<uint64_t> g_w428_two[5] = {}; // exp 0428 (tag w428c): dcb waits on two rings: kept for the GPU, satisfied, not served; heads split; kept with no split (iteration 3)
#endif
#ifndef BC5_LEAN
static std::atomic<uint64_t> g_w428_poll[5] = {}; // exp 0428 iteration 6: polled first: -, kept, satisfied, split for a cycle, split after 8 ms
static std::atomic<uint64_t> g_w428_late[4] = {}; // exp 0428 iteration 4: still split; kept: writer on a ring, written earlier in the IB, on a ring after the chain went
#endif
// Exp 0428 iterations 4-5: does this IB write the wait's label before dword `at` with a value that satisfies the wait? The
// last such write counts. The packets and fields are exactly register_label_writes' (exp 0055), which decides "kept for the
// GPU" once a job is submitted: top-level RELEASE_MEM 0x49 (DATA_SEL dword 2 bits 31:29, address 3/4, data 5/6),
// EVENT_WRITE_EOP 0x47 (DATA_SEL dword 3, address 2/3, data 4/5) and WRITE_DATA 0x37 to memory (DST_SEL dword 1 bits 11:8 =
// 1, 2 or 5; address 2/3, data from 4); IB2s are not followed, as register does not follow them (iteration 4 gave up at
// the first IB2, and w428L4 kept none). A RELEASE_MEM / EOP with another DATA_SEL is not a write here, as there.
static bool w428_ib_writes_satisfy(const uint32_t* ib, uint32_t at, const uint32_t* p, bool is64) {
	const uint64_t a     = (p[2] & ~3u) | (static_cast<uint64_t>(p[3] & 0xffffu) << 32u);
	bool           found = false, known = true;
	uint64_t       v     = 0;
	for (uint32_t k = 0; k < at;) {
		const uint32_t h = ib[k], t = h >> 30u;
		uint32_t       lk = 1;
		if (t == 3 || t == 0) {
			const uint32_t c = (h >> 16u) & 0x3fffu;
			lk               = c == 0x3fffu ? 1 : c + 2;
		}
		if (k + lk > at) break;
		if (t == 3) {
			const uint32_t  op = (h >> 8u) & 0xffu;
			const uint32_t* w  = ib + k;
			auto addr = [w](int lo, int hi) { return (static_cast<uint64_t>(w[lo]) & ~3ull) | (static_cast<uint64_t>(w[hi] & 0xffffu) << 32u); };
			if (op == 0x49 && lk >= 8 && addr(3, 4) == a) {
				const uint32_t ds = w[2] >> 29u;
				if (ds == 1) { found = true; v = w[5]; }
				if (ds == 2) { found = true; v = w[5] | (static_cast<uint64_t>(w[6]) << 32u); }
			} else if (op == 0x47 && lk >= 6 && addr(2, 3) == a) {
				const uint32_t ds = w[3] >> 29u;
				if (ds == 1) { found = true; v = w[4]; }
				if (ds == 2) { found = true; v = w[4] | (static_cast<uint64_t>(w[5]) << 32u); }
			} else if (op == 0x37 && lk >= 5 && addr(2, 3) == a) {
				const uint32_t dst = (w[1] >> 8u) & 0xfu;
				if (dst == 1 || dst == 2 || dst == 5) {
					found = true;
					v     = lk >= 6 ? (w[4] | (static_cast<uint64_t>(w[5]) << 32u)) : w[4];
				}
			}
		}
		k += lk;
	}
	if (!found || !known) return false;
	const uint32_t function = p[1] & 7u;
	if (is64) {
		const uint64_t ref = p[4] | (static_cast<uint64_t>(p[5]) << 32u), mask = p[6] | (static_cast<uint64_t>(p[7]) << 32u);
		const uint64_t vm = v & mask, rm = ref & mask;
		switch (function) {
			case 1: return vm < rm;
			case 2: return vm <= rm;
			case 3: return vm == rm;
			case 4: return vm != rm;
			case 5: return vm >= rm;
			case 6: return vm > rm;
			default: return false;
		}
	}
	return SoftCp::compare(function, static_cast<uint32_t>(v), p[5], p[4]);
}
static thread_local bool                     t_fs_valid = false;
static thread_local bc5::full_state::Tracker t_fs_before;
// Experiment 0157 (F204): other processes' work on the GFX ring (the desktop compositor's RADV jobs
// between the title's submissions) leaves context registers the title set once and never again per
// buffer -- the second title's menu redraws then ran with RADV's RB+ blend optimisation
// (SX_MRT*_BLEND_OPT) and left their element rectangles transparent. BC5_DIRECT_PREFIX_ALL:
// draws (the default) = the pieces' full-state prefix (CLEAR_STATE, then every tracked context, SH and
// uconfig register) in front of every graphics buffer that draws (run 690: 0 of 88 flagged, 43.9 fps
// against 45.0 without); sx = in front of those, one SET_CONTEXT_REG of SX_PS_DOWNCONVERT..
// SX_MRT7_BLEND_OPT (ctx 0x1d5-0x1df) with the tracked values (run 689: 0 of 88, 45.0 fps); 1|all =
// the full prefix in front of every graphics buffer (run 684: half the frame rate); 0 = off.
static int prefix_mode() {
	static const int v = [] {
		const char* e = BC5_DIAG_ENV("BC5_DIRECT_PREFIX_ALL");
		if (e == nullptr || *e == 0 || std::strcmp(e, "draws") == 0) return 2;
		if (std::strcmp(e, "0") == 0) return 0;
		if (std::strcmp(e, "sx") == 0) return 3;
		return 1;
	}();
	return v;
}
static bool prefix_all() {
	return prefix_mode() != 0;
}
// Experiment 0195: the second title sometimes ends a graphics buffer between a compute program's binding
// (a LOAD_SH_REG_INDEX table of ten (offset, value) pairs: COMPUTE_PGM_LO/HI, RSRC1/2, ...) and its dispatches,
// and starts the next buffer with them (three 2x1x1 DISPATCH_DIRECTs of 0x11d039cd00 after nothing but user
// data): it relies on the queue keeping the program registers, as the console's graphics queue does. On the
// BC-250's one GFX ring other processes' jobs run in between, and Mesa writes COMPUTE_PGM_HI once per IB
// (address32_hi >> 8 = 0x80: src/amd/common/ac_cmdbuf.c:64 @ 0866ae7) and COMPUTE_PGM_LO per dispatch
// (radeonsi si_compute.c:401, RADV radv_cmd_buffer.c:3264); such a buffer draws nothing, gets no prefix
// (BC5_DIRECT_PREFIX_ALL = draws) and ran from a desktop process's shader address, 0x800000005000 (session 0808:
// SQC instruction-fetch fault, ring reset). BC5_DIRECT_CS_PREFIX=1: in front of a graphics buffer that gets no
// other prefix and dispatches before it sets COMPUTE_PGM_LO, the graphics queue's tracked compute registers (SH
// 0x204-0x3ff from bc5::full_state, Mesa gfx10 register JSON: COMPUTE_START_X 0x204 .. COMPUTE_DISPATCH_TUNNEL
// 0x27d and past it; the values the draw prefix already replays), one SET_SH_REG per run, in the same chain
// segment; =journal only journals such buffers with the program the queue's state names (a probe). Off by
// default (D16).
static int cs_prefix_mode() {
	static const int v = [] {
		const char* e = std::getenv("BC5_DIRECT_CS_PREFIX");
		if (e == nullptr || *e == 0 || std::strcmp(e, "0") == 0) return 0;
		return std::strcmp(e, "journal") == 0 ? 2 : 1;
	}();
	return v;
}
// The offset of the first DISPATCH_DIRECT / DISPATCH_INDIRECT (Mesa sid.h 0x15 / 0x16) of ib that comes before
// anything that may set COMPUTE_PGM_LO (SH 0x20c): SET_SH_REG(_INDEX) 0x76 / 0x9b over it, LOAD_SH_REG 0x5f with a
// range over it, LOAD_SH_REG_INDEX 0x63 whose table names it (pairs, DATA_FORMAT bit 31) or covers it, or one whose
// table cannot be read, and INDIRECT_BUFFER 0x3f (not followed); -1 when there is none.
static int cs_inherit_at(const uint32_t* ib, uint32_t num_dwords, const std::vector<bc5::direct::Mapping>& maps) {
	constexpr uint32_t kPgmLo = 0x20cu;
	for (uint32_t i = 0; i < num_dwords;) {
		const uint32_t h = ib[i], type = h >> 30u;
		uint32_t       len = 1;
		if (type == 3 || type == 0) { const uint32_t c = (h >> 16u) & 0x3fffu; len = c == 0x3fffu ? 1 : c + 2; }
		if (i + len > num_dwords) break;
		if (type == 3) {
			const uint32_t  op = (h >> 8u) & 0xffu;
			const uint32_t* p  = ib + i;
			if (op == 0x15 || op == 0x16) return static_cast<int>(i);
			if (op == 0x3f) return -1;
			if ((op == 0x76 || op == 0x9b) && len >= 3 && kPgmLo - (p[1] & 0xffffu) < len - 2) return -1;
			if (op == 0x5f && len >= 5) {
				for (uint32_t k = 3; k + 1 < len; k += 2) {
					if (kPgmLo - (p[k] & 0xffffu) < (p[k + 1] & 0x3fffu)) return -1;
				}
			}
			if (op == 0x63 && len >= 5 && (p[4] & 0x3fffu) != 0) {
				const uint64_t ta    = (p[1] & ~3u) | (static_cast<uint64_t>(p[2] & 0xffffu) << 32u);
				const uint32_t tn    = p[4] & 0x3fffu;
				const bool     pairs = (p[3] >> 31u) != 0;
				if (!pairs) {
					if (kPgmLo - (p[3] & 0xffffu) < tn) return -1;
				} else {
					if (ta == 0 || !covered_sorted(maps, ta, static_cast<uint64_t>(tn) * 8)) return -1;
					const auto* t = reinterpret_cast<const volatile uint32_t*>(ta);
					for (uint32_t k = 0; k < tn; k++) {
						if ((t[2 * k] & 0xffffu) == kPgmLo) return -1;
					}
				}
			}
		}
		i += len;
	}
	return -1;
}
// The tracked compute registers (SH 0x204-0x3ff) as SET_SH_REG runs; *pgm = COMPUTE_PGM_LO/HI as an address.
static std::vector<uint32_t> cs_prefix(const bc5::full_state::Tracker& t, uint64_t* pgm) {
	std::vector<uint32_t> p, vals;
	uint32_t              first = 0;
	const auto flush = [&] {
		if (vals.empty()) return;
		p.push_back(0xC0007600u | (static_cast<uint32_t>(vals.size()) << 16u)); // SET_SH_REG, COUNT = body dwords - 1
		p.push_back(first);
		p.insert(p.end(), vals.begin(), vals.end());
		vals.clear();
	};
	for (uint32_t o = 0x204u; o < 0x400u; o++) {
		uint32_t v = 0;
		if (!t.get(bc5::full_state::Sh, o, v)) {
			flush();
			continue;
		}
		if (vals.empty()) first = o;
		vals.push_back(v);
	}
	flush();
	uint32_t lo = 0, hi = 0;
	t.get(bc5::full_state::Sh, 0x20cu, lo);
	t.get(bc5::full_state::Sh, 0x20du, hi);
	*pgm = (static_cast<uint64_t>(lo) | (static_cast<uint64_t>(hi & 0xffu) << 32u)) << 8u;
	return p;
}
// Experiment 0403 (exp 0401 series e3; BC5_DIRECT_ACB_INHERIT=journal|queue|skip, default off), after 0403's addendum
// (a423f761). An acb part that dispatches before it sets a program (cs_inherit_at) needs its guest queue's own register
// state at the end of the queue's previous buffer, whatever the wave mode: a console compute queue keeps one state from IB
// to IB, and the driver's 2-dword NOP IB in between does not change it. Series e2's per-wave slots are withdrawn; they also
// recorded inherited programs (Codex's review).
// - Tracking, in every mode: per guest queue (t_queue_idx), the live compute state (bc5::full_state::Tracker over all of
//   its parts). Per program address (COMPUTE_PGM_LO/HI), the wave modes the title used with it in a part that set it itself
//   (inherit_scan's bound dispatches), and the queue and part that last did. Per physical ring, the guest queue of its last
//   tracked part (exp 0403's difference 3).
// - journal: no submission changes. Each inheriting part gets a line (the first 64, then every 1024th): queue, head or rest,
//   the part's address, its first inheriting dispatch and initiator, and the queue's live program with USER_DATA_0..3. Also
//   that program's provenance and own-wave counts, and UNSEEN when no dispatch of the title's own with it in this wave
//   mode has been seen (not observed: no evidence of an illegal shader or of a wrong order, Codex's second review). Also
//   whether the physical ring last ran a part of the same queue, the queue's previous three parts with their first two
//   dwords, and the counts below. The census of non-IB packets on the guest rings stays.
// - queue: a head (offset 0 in its title buffer) gets the queue's live state in front (cs_prefix, SH 0x204-0x3ff), as exp
//   0401's prefix does, but on heads only, and only when that state is known: a tracked program, set by a certain write
//   that no IB2 or unreadable table voided since (inherit_scan's end state), and seen with the dispatch's wave mode.
//   Otherwise nothing is put in front and the part keeps today's behaviour, the ring's state: "unknown, fallback ring"
//   (the top session's decision, 2026-11-03). Prefixes and fallbacks are counted apart, so a clean play in this mode
//   cannot come from silent drops.
// - skip: a head's inheriting dispatches are dropped by submit_now's filter (drop_offsets), the way BC5_DIRECT_SKIP_PGM
//   drops them. This is the only mode that drops.
// Rests and segments, whose head state_prefix replays, are left as they are in every mode. With BC5_DIRECT_ACB_CS_PREFIX
// also set, this switch wins: the acb CS prefix stays off, with one journal line.
// Series e3 (exp 0403's addendum, a423f761, and Codex's review of e2): which dispatches of an acb part run a program the
// part set itself. A dispatch (0x15 / 0x16) is "bound" when a packet that certainly sets COMPUTE_PGM_LO (SH 0x20c) comes
// before it in the same part: SET_SH_REG(_INDEX) 0x76 / 0x9b over it, LOAD_SH_REG 0x5f with a range over it,
// LOAD_SH_REG_INDEX 0x63 in the offset format with a range over it or with a pair table (DATA_FORMAT bit 31) that can be
// read and names it (cs_inherit_at's packets). An unreadable pair table and an INDIRECT_BUFFER (0x3f) may set it too, so
// after one the part's own program is no longer known: dispatches are unbound again until the next certain write (Codex's
// second review). w32 is the initiator's bit 15, CS_W32_EN, the packet's last dword (exp 0403 section 2; TODO(verify) in
// the register database). Only bound dispatches say which wave mode the title uses with a program. The return value is
// what the part leaves behind: 1 when its last packet that touches the program is a certain write, 0 when it is one that
// may set it unseen (the queue's program is then not known), -1 when it has none (the queue's state carries over).
struct InheritDispatch {
	uint32_t at = 0, end = 0; // the packet's offset in the part, and the offset after it
	bool     w32 = false, bound = false;
};
template <class Read>
static int inherit_scan(const uint32_t* part, uint32_t n, const Read& read, std::vector<InheritDispatch>& out) {
	constexpr uint32_t kPgmLo = 0x20cu;
	bool               bound  = false;
	int                state  = -1;
	const auto         sure   = [&bound, &state] {
		bound = true;
		state = 1;
	};
	const auto lost = [&bound, &state] {
		bound = false;
		state = 0;
	};
	for (uint32_t i = 0; i < n;) {
		const uint32_t h = part[i], type = h >> 30u;
		uint32_t       len = 1;
		if (type == 3 || type == 0) {
			const uint32_t c = (h >> 16u) & 0x3fffu;
			len              = c == 0x3fffu ? 1 : c + 2;
		}
		if (i + len > n) break;
		if (type == 3) {
			const uint32_t  op = (h >> 8u) & 0xffu;
			const uint32_t* q  = part + i;
			if ((op == 0x76 || op == 0x9b) && len >= 3 && kPgmLo - (q[1] & 0xffffu) < len - 2) sure();
			if (op == 0x5f && len >= 5) {
				for (uint32_t k = 3; k + 1 < len; k += 2) {
					if (kPgmLo - (q[k] & 0xffffu) < (q[k + 1] & 0x3fffu)) sure();
				}
			}
			if (op == 0x63 && len >= 5 && (q[4] & 0x3fffu) != 0) {
				const uint32_t tn = q[4] & 0x3fffu;
				if ((q[3] >> 31u) == 0) {
					if (kPgmLo - (q[3] & 0xffffu) < tn) sure();
				} else {
					const uint64_t  ta = (q[1] & ~3u) | (static_cast<uint64_t>(q[2] & 0xffffu) << 32u);
					const uint32_t* t  = ta != 0 ? read(ta, static_cast<uint64_t>(tn) * 8u) : nullptr;
					if (t == nullptr) lost(); // may set it: the part's own program is not known any more
					for (uint32_t k = 0; t != nullptr && k < tn; k++) {
						if ((t[2 * k] & 0xffffu) == kPgmLo) sure();
					}
				}
			}
			if (op == 0x3f) lost(); // an IB2 may set it too
			if ((op == 0x15 || op == 0x16) && len >= 3) out.push_back(InheritDispatch {i, i + len, (part[i + len - 1] & 0x8000u) != 0, bound});
		}
		i += len;
	}
	return state;
}
static int acb_inherit_mode() { // 0 off, 1 journal, 2 queue, 3 skip
	static const int m = [] {
		const char* e = nullptr; /* exp 0419: option removed */
		if (e == nullptr || *e == 0 || std::strcmp(e, "0") == 0) return 0;
		if (std::strcmp(e, "journal") == 0) return 1;
		if (std::strcmp(e, "queue") == 0) return 2;
		if (std::strcmp(e, "skip") == 0) return 3;
		return -1;
	}();
	static std::atomic<bool> told {false};
	if (!told.exchange(true)) {
		static const char* const names[] = {"an unknown value: off", "off", "journal (no submission changes)",
		                                    "queue (a head gets its queue's live state when it is known, else the ring's; no drops)", "skip (a head's inheriting dispatches are dropped)"};
		journal("exp 0403: acb inherit %s\n", names[m + 1]);
		if (m > 0 && false /* exp 0419: option removed */) journal("exp 0403: BC5_DIRECT_ACB_CS_PREFIX is set too: BC5_DIRECT_ACB_INHERIT wins, the acb CS prefix stays off\n");
	}
	return m < 0 ? 0 : m;
}
struct InheritQueue {
	bc5::full_state::Tracker t;           // the queue's live compute state
	const uint32_t*          prev[3] = {}; // its last three parts, newest first
	uint32_t                 prev_n[3] = {};
	uint64_t                 unbound = 0; // its dispatches that ran a program their part did not set
	bool                     known   = false; // the live program came from a certain write that nothing voided since
};
struct InheritProg {
	uint64_t        own32 = 0, own64 = 0; // the title's own dispatches with this program, by wave mode
	int             queue = -1;           // the queue and part that last made one
	const uint32_t* part  = nullptr;
};
struct InheritCensus {
	std::map<uint32_t, uint64_t> ops, sh; // by opcode; SET_SH_REG by (first register << 8 | count)
	uint64_t                     slices = 0;
};
static std::mutex                     g_inh_mutex;
static std::map<int, InheritQueue>    g_inh;        // by guest queue (t_queue_idx)
static std::map<uint64_t, InheritProg> g_inh_prog;  // by program address
static std::map<int, int>             g_inh_ring;   // physical ring -> the guest queue of its last tracked part
static std::map<int, InheritCensus>   g_inh_census; // by guest queue
static std::set<const uint32_t*>      g_inh_drop;   // skip: the title's dispatch packets submit_now drops
static std::atomic<size_t>            g_inh_drops {0};
static std::atomic<uint64_t>          g_inh_prefixed {0}, g_inh_fb_noprog {0}, g_inh_fb_void {0}, g_inh_fb_unseen {0}; // queue mode
static std::atomic<uint64_t>          g_inh_skip_heads {0}, g_inh_dropped {0};                                     // skip mode
// ---- exp 0401 series e7 (tag cap): caps on the two exp 0403 maps that only grow --------------------------------------
// cap0401-notes.md surveys every e-series catcher's buffers and the journal. With BC5_DIRECT_ACB_INHERIT on,
// acb_inherit_track adds an entry to g_inh_prog for each program address a bound acb dispatch runs, and
// acb_inherit_census one to its queue's census for each SET_SH_REG (first register, count) on a guest ring; nothing ever
// removes one. Both are bounded only by what the title sends. Two switches, each off by default and read once (unset, empty
// and "0" are off, bc5::env_on), cap them:
//   BC5_DIRECT_INHERIT_PROG_CAP    g_inh_prog at most N programs (default 65536: about 5 MiB of map nodes)
//   BC5_DIRECT_INHERIT_CENSUS_CAP  each queue's census at most N SET_SH_REG kinds (default 4096)
// An on value that is a decimal number from 2 to 2^32 is N; any other on value ("1") takes the default. A full map records
// no new key (counted, journaled the first time and every 65536th); the keys already in keep counting. A program that was
// not recorded reads as one never bound in a part of its own: queue mode then leaves its head on the ring's state
// ("unknown, fallback ring"), today's answer for an unknown program; journal mode prints it so. Off (cap 0), cap_slot is
// the map's operator[]: today's entry and counts. The first use journals and prints one line,
// "exp 0401 e7: acb inherit caps: programs <N|off>, census <N|off> per queue".
constexpr uint64_t kInhProgCapDefault   = 65536;
constexpr uint64_t kInhCensusCapDefault = 4096;
static uint64_t cap_parse(const char* e, uint64_t dflt) { // 0: off; otherwise the cap
	if (!bc5::env_on(e)) return 0;
	uint64_t    v = 0;
	const char* c = e;
	for (; *c >= '0' && *c <= '9' && v <= (1ull << 32u); c++) v = v * 10u + static_cast<uint64_t>(*c - '0');
	return *c == 0 && v >= 2 && v <= (1ull << 32u) ? v : dflt;
}
// The entry for key in m, inserted when m holds fewer than cap entries; nullptr when key is new and m is full. cap 0: m[key].
template <class Map>
static typename Map::mapped_type* cap_slot(Map& m, const typename Map::key_type& key, uint64_t cap) {
	if (cap == 0) return &m[key];
	const auto it = m.find(key);
	if (it != m.end()) return &it->second;
	if (m.size() >= cap) return nullptr;
	return &m.emplace(key, typename Map::mapped_type {}).first->second;
}
struct InhCaps {
	uint64_t prog = 0, census = 0; // 0: off
};
static const InhCaps& inh_caps() {
	static const InhCaps c = [] {
		InhCaps v;
		v.prog   = cap_parse(nullptr, kInhProgCapDefault) /* exp 0419: option removed */;
		v.census = cap_parse(nullptr, kInhCensusCapDefault) /* exp 0419: option removed */;
		char p[24] = "off", s[24] = "off";
		if (v.prog != 0) std::snprintf(p, sizeof(p), "%" PRIu64, v.prog);
		if (v.census != 0) std::snprintf(s, sizeof(s), "%" PRIu64, v.census);
		journal("exp 0401 e7: acb inherit caps: programs %s, census %s per queue\n", p, s);
		std::fprintf(stderr, "[bc5] exp 0401 e7: acb inherit caps: programs %s, census %s per queue\n", p, s);
		return v;
	}();
	return c;
}
static std::atomic<uint64_t> g_inh_cap_refused[2]; // the new keys a full map did not record: 0 programs, 1 census kinds
static void inh_cap_refused(int which, size_t size, uint64_t cap) {
	const uint64_t k = g_inh_cap_refused[which & 1]++;
	if (k == 0 || (k & 0xffffu) == 0)
		journal("exp 0401 e7: acb inherit %s full at %zu entries (cap %" PRIu64 "): a new %s is not recorded (%" PRIu64 " so far)\n", which == 0 ? "program map" : "census", size, cap,
				which == 0 ? "program" : "SET_SH_REG kind", k + 1);
}
// g_inh_prog's entry for pgm as acb_inherit_track keeps it: the title's own dispatches by wave mode, and the queue and part
// that last made one. The caller holds g_inh_mutex. False when the cap did not record a new program.
static bool inh_prog_note(uint64_t pgm, bool w32, const uint32_t* part) {
	const uint64_t cap = inh_caps().prog;
	InheritProg*   p   = cap_slot(g_inh_prog, pgm, cap);
	if (p == nullptr) {
		inh_cap_refused(0, g_inh_prog.size(), cap);
		return false;
	}
	(w32 ? p->own32 : p->own64)++;
	p->queue = t_queue_idx;
	p->part  = part;
	return true;
}
// One SET_SH_REG kind counted in a queue's census, as acb_inherit_census counts it. The caller holds g_inh_mutex.
static bool inh_census_sh(InheritCensus& c, uint32_t key) {
	const uint64_t cap = inh_caps().census;
	uint64_t*      v   = cap_slot(c.sh, key, cap);
	if (v == nullptr) {
		inh_cap_refused(1, c.sh.size(), cap);
		return false;
	}
	(*v)++;
	return true;
}
// ---- end of exp 0401 series e7's (tag cap) block -----------------------------------------------------------------------
static uint32_t inherit_len(uint32_t h) {
	const uint32_t type = h >> 30u;
	if (type != 3 && type != 0) return 1;
	const uint32_t c = (h >> 16u) & 0x3fffu;
	return c == 0x3fffu ? 1 : c + 2;
}
static uint64_t inherit_pgm(const bc5::full_state::Tracker& t) { // COMPUTE_PGM_LO/HI as an address, as cs_prefix gives it
	uint32_t lo = 0, hi = 0;
	if (!t.get(bc5::full_state::Sh, 0x20cu, lo)) return 0;
	if (!t.get(bc5::full_state::Sh, 0x20du, hi)) hi = 0;
	return (static_cast<uint64_t>(lo) << 8u) | (static_cast<uint64_t>(hi & 0xffu) << 40u);
}
static void acb_inherit_track(const uint32_t* part, uint32_t n) {
	if (acb_inherit_mode() == 0 || !g_dev || part == nullptr || n == 0) return;
	std::shared_ptr<const std::vector<bc5::direct::Mapping>> maps_p = g_dev->sorted_mappings();
	const bc5::full_state::Tracker::Reader read = [&maps_p](uint64_t a, uint64_t bytes) -> const uint32_t* {
		return covered_sorted(*maps_p, a, bytes) ? reinterpret_cast<const uint32_t*>(a) : nullptr;
	};
	std::vector<InheritDispatch> ds;
	const int end_state = inherit_scan(part, n, read, ds);
	bc5::full_state::Stats st;
	std::lock_guard        lk(g_inh_mutex);
	InheritQueue&          q    = g_inh[t_queue_idx];
	uint32_t               done = 0;
	for (const InheritDispatch& d: ds) { // the program at each bound dispatch: the tracker applied up to it
		if (!d.bound) {
			q.unbound++;
			continue;
		}
		q.t.apply(std::span<const uint32_t>(part + done, d.end - done), read, st);
		done               = d.end;
		const uint64_t pgm = inherit_pgm(q.t);
		if (pgm == 0) continue;
		inh_prog_note(pgm, d.w32, part); // exp 0401 series e7 (tag cap): today's four lines; BC5_DIRECT_INHERIT_PROG_CAP off is g_inh_prog[pgm]
	}
	if (done < n) q.t.apply(std::span<const uint32_t>(part + done, n - done), read, st);
	if (end_state >= 0) q.known = end_state == 1; // what this part leaves: a certain program, or one an IB2 or table voided
	for (int k = 2; k > 0; k--) {
		q.prev[k]   = q.prev[k - 1];
		q.prev_n[k] = q.prev_n[k - 1];
	}
	q.prev[0]          = part;
	q.prev_n[0]        = n;
	g_inh_ring[t_ring] = t_queue_idx;
}
static std::vector<uint32_t> acb_inherit_prefix(const uint32_t* part, uint32_t n, uint32_t from) {
	const int mode = acb_inherit_mode();
	if (mode == 0 || !g_dev || part == nullptr || n == 0) return {};
	std::shared_ptr<const std::vector<bc5::direct::Mapping>> maps_p = g_dev->sorted_mappings();
	const int                                                at     = cs_inherit_at(part, n, *maps_p);
	if (at < 0) return {};
	std::vector<uint32_t> inh; // each dispatch before the part's first packet that may set the program
	for (uint32_t base = 0; base < n;) {
		const int k = cs_inherit_at(part + base, n - base, *maps_p);
		if (k < 0) break;
		const uint32_t o = base + static_cast<uint32_t>(k);
		inh.push_back(o);
		base = o + inherit_len(part[o]);
	}
	const uint32_t        init = part[static_cast<uint32_t>(at) + inherit_len(part[at]) - 1];
	const bool            w32 = (init & 0x8000u) != 0, head = from == 0;
	std::vector<uint32_t> pre;
	uint64_t              pgm = 0;
	uint32_t              ud[4] = {}, prev_n[3] = {};
	const uint32_t*       prev[3] = {};
	InheritProg           prog;
	bool                  known = false, qknown = false;
	int                   ring_q = -1;
	{
		std::lock_guard lk(g_inh_mutex);
		const auto      it = g_inh.find(t_queue_idx);
		if (it != g_inh.end()) {
			const InheritQueue& q = it->second;
			pgm                   = inherit_pgm(q.t);
			for (uint32_t k = 0; k < 4; k++) {
				uint32_t v = 0;
				ud[k]      = q.t.get(bc5::full_state::Sh, 0x240u + k, v) ? v : 0u;
			}
			for (int k = 0; k < 3; k++) {
				prev[k]   = q.prev[k];
				prev_n[k] = q.prev_n[k];
			}
			const auto pit = g_inh_prog.find(pgm);
			if (pgm != 0 && pit != g_inh_prog.end()) {
				prog  = pit->second;
				known = true;
			}
			qknown = q.known;
			if (mode == 2 && head && pgm != 0 && qknown && (w32 ? prog.own32 : prog.own64) != 0) {
				uint64_t live = 0;
				pre           = cs_prefix(q.t, &live);
			}
		}
		const auto rit = g_inh_ring.find(t_ring);
		if (rit != g_inh_ring.end()) ring_q = rit->second;
	}
	const bool  unseen = pgm != 0 && (w32 ? prog.own32 : prog.own64) == 0;
	const bool  skip   = head && mode == 3; // the only mode that drops
	const char* why    = pgm == 0  ? "the queue has no tracked program"
	                     : !qknown ? "an IB2 or an unreadable table voided the state's provenance"
	                     : unseen  ? "the program is unseen in this wave mode"
	                               : "";
	if (head && mode == 2) {
		if (!pre.empty()) g_inh_prefixed++;
		else if (pgm == 0) g_inh_fb_noprog++;
		else if (!qknown) g_inh_fb_void++;
		else g_inh_fb_unseen++;
	}
	if (skip) g_inh_skip_heads++;
	if (skip) {
		std::lock_guard lk(g_inh_mutex);
		if (g_inh_drop.size() > 4096) g_inh_drop.clear(); // parts that never reached submit_now leave entries behind
		for (const uint32_t o: inh) g_inh_drop.insert(part + o);
		g_inh_drops = g_inh_drop.size();
	}
	uint32_t pw[3][2] = {}; // the previous parts' first two dwords, where they are still mapped
	for (int k = 0; k < 3; k++) {
		if (prev[k] != nullptr && prev_n[k] >= 2 && covered_sorted(*maps_p, reinterpret_cast<uint64_t>(prev[k]), 8)) {
			pw[k][0] = prev[k][0];
			pw[k][1] = prev[k][1];
		}
	}
	const char* action = mode == 1      ? "journal only"
	                     : !head        ? "a rest: left as it is"
	                     : mode == 3    ? "dropped (skip mode)"
	                     : !pre.empty() ? "prefixed with the queue's state"
	                                    : "unknown, fallback ring";
	static std::atomic<uint64_t> n_inh {0};
	const uint64_t               k = n_inh++;
	if (k < 64 || (k & 0x3ffu) == 0)
		journal("acb inherit (exp 0403): t %.3f s queue %d %s part %p %u dwords from offset %u: %zu inheriting dispatches, the first at %u, initiator 0x%x (%s); the queue's live program 0x%010" PRIx64 " ud0-3 %08x %08x %08x %08x, %s by queue %d part %p, own W32 %" PRIu64 " W64 %" PRIu64 "%s; ring %d's last tracked part from queue %d (%s); previous parts %p+%u [%08x %08x] %p+%u [%08x %08x] %p+%u [%08x %08x]; %s%s%s%s, %zu dwords in front; so far prefixed %" PRIu64 ", fallback ring %" PRIu64 " (no program %" PRIu64 ", voided %" PRIu64 ", unseen %" PRIu64 "), skip-mode heads %" PRIu64 ", dispatches dropped %" PRIu64 " (%" PRIu64 " such parts)\n",
		        timing_now(), t_queue_idx, head ? "head" : "rest", static_cast<const void*>(part), n, from, inh.size(), from + static_cast<uint32_t>(at), init, w32 ? "W32" : "W64", pgm, ud[0], ud[1],
		        ud[2], ud[3], known ? "bound last" : "never bound in a part of its own", prog.queue, static_cast<const void*>(prog.part), prog.own32, prog.own64, unseen ? ", UNSEEN (not observed in this wave mode)" : "", t_ring, ring_q,
		        ring_q == t_queue_idx ? "the same queue" : ring_q < 0 ? "none yet" : "another queue", static_cast<const void*>(prev[0]), prev_n[0], pw[0][0], pw[0][1], static_cast<const void*>(prev[1]),
		        prev_n[1], pw[1][0], pw[1][1], static_cast<const void*>(prev[2]), prev_n[2], pw[2][0], pw[2][1], action, why[0] != 0 ? " (" : "", why,
		        why[0] != 0 ? ")" : "", pre.size(), g_inh_prefixed.load(), g_inh_fb_noprog.load() + g_inh_fb_void.load() + g_inh_fb_unseen.load(), g_inh_fb_noprog.load(),
		        g_inh_fb_void.load(), g_inh_fb_unseen.load(), g_inh_skip_heads.load(), g_inh_dropped.load(), k + 1);
	return pre;
}
static bool acb_inherit_take(const uint32_t* p) {
	{
		std::lock_guard lk(g_inh_mutex);
		const auto      it = g_inh_drop.find(p);
		if (it == g_inh_drop.end()) return false;
		g_inh_drop.erase(it);
		g_inh_drops = g_inh_drop.size();
	}
	const uint64_t k = g_inh_dropped++;
	if (k < 64 || (k & 0x3ffu) == 0) journal("acb inherit (exp 0403): the inheriting dispatch at %p dropped (%" PRIu64 " so far)\n", static_cast<const void*>(p), k + 1);
	return true;
}
static void acb_inherit_census(const uint32_t* p, uint32_t len) {
	if (acb_inherit_mode() == 0 || p == nullptr || len == 0) return;
	const uint32_t  op = (p[0] >> 8u) & 0xffu;
	std::lock_guard lk(g_inh_mutex);
	InheritCensus&  c = g_inh_census[t_queue_idx];
	c.ops[op]++;
	if (op == 0x76 && len >= 3) inh_census_sh(c, ((p[1] & 0xffffu) << 8u) | std::min<uint32_t>(len - 2, 255u)); // exp 0401 series e7 (tag cap): BC5_DIRECT_INHERIT_CENSUS_CAP off is c.sh[key]++
}
static void acb_inherit_census_slice() {
	if (acb_inherit_mode() == 0) return;
	std::string line;
	uint64_t    k = 0;
	{
		std::lock_guard lk(g_inh_mutex);
		InheritCensus&  c = g_inh_census[t_queue_idx];
		k                 = c.slices++;
		if (k != 0 && (k & 0x3ffu) != 0) return;
		char b[64];
		for (const auto& [op, cnt]: c.ops) {
			std::snprintf(b, sizeof(b), " op %02x x%" PRIu64, op, cnt);
			if (line.size() < 1400) line += b;
		}
		for (const auto& [key, cnt]: c.sh) {
			std::snprintf(b, sizeof(b), " sh 0x%x+%u x%" PRIu64, key >> 8u, key & 0xffu, cnt);
			if (line.size() < 1400) line += b;
		}
	}
	journal("acb inherit census (exp 0403): queue %d after %" PRIu64 " ring slices, non-IB type-3 packets:%s\n", t_queue_idx, k + 1, line.empty() ? " none" : line.c_str());
}
// ---- exp 0401 series e7 (tag cap): the CPU test's seams (cap0401.cpp); always compiled in, never called by the emulator ---
extern "C" uint64_t bc5_cap0401_parse(const char* e, uint64_t dflt) {
	return cap_parse(e, dflt);
}
// cap_slot over a map of the test's own: each key counted once more, as the census counts; out gets (key, count) in key
// order (at most out_cap of them); returns the map's size.
extern "C" uint64_t bc5_cap0401_slot(const uint32_t* keys, uint64_t n, uint64_t cap, uint32_t* out_keys, uint64_t* out_counts, uint64_t out_cap, uint64_t* refused) {
	std::map<uint32_t, uint64_t> m;
	*refused = 0;
	for (uint64_t k = 0; k < n; k++) {
		if (uint64_t* v = cap_slot(m, keys[k], cap); v != nullptr) (*v)++;
		else (*refused)++;
	}
	uint64_t i = 0;
	for (const auto& [key, cnt]: m) {
		if (i < out_cap) {
			out_keys[i]   = key;
			out_counts[i] = cnt;
		}
		i++;
	}
	return i;
}
extern "C" void bc5_cap0401_caps(uint64_t* prog, uint64_t* census) {
	std::lock_guard lk(g_inh_mutex);
	const InhCaps&  c = inh_caps();
	*prog             = c.prog;
	*census           = c.census;
}
extern "C" int bc5_cap0401_prog_note(uint64_t pgm, int w32) { // acb_inherit_track's update of g_inh_prog, for one bound dispatch
	std::lock_guard lk(g_inh_mutex);
	return inh_prog_note(pgm, w32 != 0, nullptr) ? 1 : 0;
}
extern "C" uint64_t bc5_cap0401_prog_size() {
	std::lock_guard lk(g_inh_mutex);
	return g_inh_prog.size();
}
extern "C" int bc5_cap0401_prog_get(uint64_t pgm, uint64_t* own32, uint64_t* own64) {
	std::lock_guard lk(g_inh_mutex);
	const auto      it = g_inh_prog.find(pgm);
	if (it == g_inh_prog.end()) return 0;
	*own32 = it->second.own32;
	*own64 = it->second.own64;
	return 1;
}
extern "C" void bc5_cap0401_census(const uint32_t* p, uint32_t len) { // the real acb_inherit_census (BC5_DIRECT_ACB_INHERIT on)
	acb_inherit_census(p, len);
}
extern "C" uint64_t bc5_cap0401_census_size(uint64_t* ops_76) { // this thread's queue (t_queue_idx): its SET_SH_REG kinds
	std::lock_guard lk(g_inh_mutex);
	*ops_76       = 0;
	const auto it = g_inh_census.find(t_queue_idx);
	if (it == g_inh_census.end()) return 0;
	const auto o = it->second.ops.find(0x76u);
	if (o != it->second.ops.end()) *ops_76 = o->second;
	return it->second.sh.size();
}
extern "C" uint64_t bc5_cap0401_census_get(uint32_t key) {
	std::lock_guard lk(g_inh_mutex);
	const auto      it = g_inh_census.find(t_queue_idx);
	if (it == g_inh_census.end()) return 0;
	const auto s = it->second.sh.find(key);
	return s == it->second.sh.end() ? 0 : s->second;
}
extern "C" uint64_t bc5_cap0401_refused(int which) {
	return g_inh_cap_refused[which & 1].load();
}
// ---- end of exp 0401 series e7's (tag cap) seams ------------------------------------------------------------------------

// Experiment 0401 (BC5_DIRECT_ACB_CS_PREFIX=1, default off): the acb side of experiment 0195's CS prefix. On the console
// an acb runs on its own compute queue, which keeps the compute registers that queue's previous acb left. The second
// title relies on it: on 2026-11-03 08:49 acb #432910 launched 19612 x 1 x 1 four times before it set a program (its
// last dispatch sets 0x9098eb200 over the same arguments), and with the acbs on the GFX ring the stall sampler saw a
// dcb's program, 0x11d0287900, running those groups when the ring hung. With the switch on, every acb part the ring
// thread submits is applied to its guest queue's own tracker (bc5::full_state, keyed by t_queue_idx), and a part that
// dispatches before it sets COMPUTE_PGM_LO (cs_inherit_at) gets that queue's tracked compute registers in front
// (cs_prefix: SH 0x204-0x3ff). A queue with nothing tracked yet gets nothing. With the switch off nothing is tracked.
// Experiment 0424 (tag aq424): BC5_DIRECT_ACB_QUEUE_STATE, the acb's own queue state in front of every acb part that
// dispatches (see acb_cs_prefix). Read with std::getenv: the lean build reads it too. Off by default in the test build.
static bool aq424_on() {
	static const bool on = [] {
		const char* e = std::getenv("BC5_DIRECT_ACB_QUEUE_STATE");
		const bool  v = e != nullptr && e[0] != 0 && std::strcmp(e, "0") != 0;
#ifndef BC5_LEAN
		std::fprintf(stderr, "[bc5] exp 0424 (tag aq424): acb queue state %s\n", v ? "ON (every acb part that dispatches gets its queue's compute registers in front)" : "off");
#endif
		return v;
	}();
	return on;
}
static std::atomic<uint64_t> g_aq424_parts {0}, g_aq424_none {0}; // exp 0424: parts given their queue's state; parts whose queue had none
static bool                  acb_restore_wants(const uint32_t* ib, uint32_t num_dwords);
static std::vector<uint32_t> acb_restore_runs(const bc5::full_state::Tracker& t, size_t* regs);
static bool acb_cs_prefix_on() {
	static const bool        on = aq424_on(); // exp 0424 (tag aq424); exp 0419 had removed the option (false)
	static std::atomic<bool> told {false};
	if (!told.exchange(true))
		journal("exp 0401: acb CS prefix %s\n", on ? "on (an acb part that dispatches before it sets a program gets its queue's tracked compute registers in front)" : "off");
	return on;
}
static std::mutex                              g_acb_cs_mutex;
static std::map<int, bc5::full_state::Tracker> g_acb_cs; // by guest queue (t_queue_idx)
static std::vector<uint32_t> acb_cs_prefix(const uint32_t* part, uint32_t n) {
	if (!acb_cs_prefix_on() || !g_dev || part == nullptr || n == 0) return {};
	// exp 0424 (tag aq424): every part that dispatches, not only one that dispatches before it sets a program (cs_inherit_at):
	// a console compute queue keeps all of its registers from buffer to buffer, and the BVH refit 0x909939900 sets its program
	// and USER_DATA_0..4 but keeps the queue's USER_DATA_5 (on the shared GFX ring it got another queue's, high half 0x11 for
	// 0x12: exp 0424). The set is SH 0x204-0x3ff without COMPUTE_VMID (acb_restore_runs).
	if (!acb_restore_wants(part, n)) return {};
	// exp 0428 (cost candidate, BC5_DIRECT_ACB_STATE_NO_WALK, std::getenv: lean too): `at` only names the inheriting
	// dispatch in the journal line below, so the walk can go; -1 is printed then.
	static const bool     no_walk = [] {
		const char* e = std::getenv("BC5_DIRECT_ACB_STATE_NO_WALK");
		return e != nullptr && e[0] != 0 && std::strcmp(e, "0") != 0;
	}();
	const int             at  = no_walk ? -1 : cs_inherit_at(part, n, *g_dev->sorted_mappings());
	uint64_t              pgm = 0;
	std::vector<uint32_t> cs;
	{
		std::lock_guard lk(g_acb_cs_mutex);
		const auto      it = g_acb_cs.find(t_queue_idx);
		if (it != g_acb_cs.end()) {
			size_t   regs = 0;
			uint32_t lo = 0, hi = 0;
			cs = acb_restore_runs(it->second, &regs);
			it->second.get(bc5::full_state::Sh, 0x20cu, lo);
			it->second.get(bc5::full_state::Sh, 0x20du, hi);
			pgm = (static_cast<uint64_t>(lo) | (static_cast<uint64_t>(hi & 0xffu) << 32u)) << 8u;
		}
	}
	(cs.empty() ? g_aq424_none : g_aq424_parts)++;
	static std::atomic<uint64_t> n_cs {0};
	const uint64_t               k = n_cs++;
	if (k < 64 || (k & 0x3ffu) == 0)
		journal("acb cs prefix (exp 0401): t %.3f s queue %d acb part %u dwords dispatches at %d before it sets a program; the queue's program 0x%010" PRIx64 ", %zu dwords in front (%" PRIu64 " such parts)\n",
		        timing_now(), t_queue_idx, n, at, pgm, cs.size(), k + 1);
	return cs;
}
static void acb_cs_track(const uint32_t* part, uint32_t n) {
	if (!acb_cs_prefix_on() || !g_dev || part == nullptr || n == 0) return;
	std::shared_ptr<const std::vector<bc5::direct::Mapping>> maps_p = g_dev->sorted_mappings();
	const bc5::full_state::Tracker::Reader read = [&maps_p](uint64_t a, uint64_t bytes) -> const uint32_t* {
		return covered_sorted(*maps_p, a, bytes) ? reinterpret_cast<const uint32_t*>(a) : nullptr;
	};
	bc5::full_state::Stats st;
	std::lock_guard        lk(g_acb_cs_mutex);
	g_acb_cs[t_queue_idx].apply(std::span<const uint32_t>(part, n), read, st);
}
// Experiment 0381 (F679, F685), ported to this unit by experiment 0401 series b: BC5_DIRECT_ACB_STATE_RESTORE=1 puts the
// graphics queue's tracked compute registers (the CS prefix's range without COMPUTE_VMID) in front of every graphics
// buffer that dispatches (or calls an IB2) and gets no other prefix, in the buffer's own chain segment. With the acbs on
// the GFX ring a graphics buffer that inherits them (its table sets the program, so cs_inherit_at finds nothing) ran with
// an acb's USER_DATA_0 and faulted at 0x860xxxxxxxx (F679); with the restore 3 of 3 starts ran clean against 3 of 3 faults
// without it (F685). bc5::acb_restore's wants() and runs() (backend/include/bc5/acb_restore.hpp @ main 029e0d6b) are
// copied here, since the header is not on this build's include path; exp 0381's acb register census (Touched) is left out.
// Off by default.
static bool acb_restore_on() {
	static const bool        on = bc5::env_on(BC5_FIXED_ENV("BC5_DIRECT_ACB_STATE_RESTORE", "1"));
	static std::atomic<bool> told {false};
	if (!told.exchange(true)) {
		journal("exp 0401: acb state restore (exp 0381) %s\n", on ? "on (a graphics buffer that dispatches gets the graphics queue's tracked compute registers in front)" : "off");
		std::fprintf(stderr, "[bc5] exp 0401: acb state restore (exp 0381) %s\n", on ? "on" : "off"); // exp 0417: also in the play log (lean has no journal)
	}
	return on;
}
static bool acb_restore_wants(const uint32_t* ib, uint32_t num_dwords) {
	for (uint32_t i = 0; i < num_dwords;) {
		const uint32_t h = ib[i], type = h >> 30u;
		uint32_t       len = 1;
		if (type == 3 || type == 0) { const uint32_t c = (h >> 16u) & 0x3fffu; len = c == 0x3fffu ? 1 : c + 2; }
		if (type == 3) {
			const uint32_t op = (h >> 8u) & 0xffu;
			if (op == 0x15 || op == 0x16 || op == 0x3f) return true; // DISPATCH_DIRECT, DISPATCH_INDIRECT, INDIRECT_BUFFER
		}
		i += len;
	}
	return false;
}
static std::vector<uint32_t> acb_restore_runs(const bc5::full_state::Tracker& t, size_t* regs) {
	std::vector<uint32_t> p, vals;
	uint32_t              first = 0;
	size_t                n     = 0;
	const auto flush = [&] {
		if (vals.empty()) return;
		p.push_back(0xC0007600u | (static_cast<uint32_t>(vals.size()) << 16u)); // SET_SH_REG, COUNT = body dwords - 1
		p.push_back(first);
		p.insert(p.end(), vals.begin(), vals.end());
		n += vals.size();
		vals.clear();
	};
	for (uint32_t o = 0x204u; o < 0x400u; o++) {
		uint32_t v = 0;
		if (o == 0x214u || !t.get(bc5::full_state::Sh, o, v)) { // COMPUTE_VMID is the kernel's: never replayed
			flush();
			continue;
		}
		if (vals.empty()) first = o;
		vals.push_back(v);
	}
	flush();
	*regs = n;
	return p;
}
static bool ib_has_draw(const uint32_t* ib, uint32_t num_dwords) {
	for (uint32_t i = 0; i < num_dwords;) {
		const uint32_t h = ib[i], type = h >> 30u;
		uint32_t       len = 1;
		if (type == 3 || type == 0) { const uint32_t c = (h >> 16u) & 0x3fffu; len = c == 0x3fffu ? 1 : c + 2; }
		if (i + len > num_dwords) break;
		if (type == 3) {
			const uint32_t op = (h >> 8u) & 0xffu;
			if (op == 0x24 || op == 0x25 || op == 0x27 || op == 0x2c || op == 0x2d || op == 0x35 || op == 0x38) return true;
		}
		i += len;
	}
	return false;
}
static std::vector<uint32_t> sx_prefix(const bc5::full_state::Tracker& t) {
	std::vector<uint32_t> p;
	p.push_back(0xC0000000u | (11u << 16u) | (0x69u << 8u)); // SET_CONTEXT_REG, 12 body dwords
	p.push_back(0x1d5u);
	for (uint32_t o = 0x1d5u; o <= 0x1dfu; o++) {
		uint32_t v = 0;
		if (!t.get(bc5::full_state::Context, o, v)) return {};
		p.push_back(v);
	}
	return p;
}
// Experiment 0160: the geometry engine reads tessellation factors from VGT_TF_MEMORY_BASE(_HI) /
// VGT_TF_RING_SIZE (uconfig 0xc250 / 0xc261 / 0xc24e; Mesa src/amd/registers gfx10 and sid.h
// R_030940/R_030984/R_030938), which the console's system programs from the ring the title hands to
// GraphicsDriverSetTFRing; nothing programmed them here, so the GE fetched the ring at address 0 (the
// second title's night scene, runs 741-766). The prefix of every graphics buffer that draws sets them
// from the title's call, with VGT_HS_OFFCHIP_PARAM (0xc24f) from GraphicsDriverSetHsOffchipParam's
// first value.
extern "C" void Bc5TfRingState(uint64_t* base, uint32_t* size, uint64_t* offchip0, uint64_t* offchip1, uint64_t* offchip2);
// Experiment 0189, a behaviour switch, off by default (docs/ports/related-projects-review.md section 7):
// - BC5_DIRECT_OFFCHIP_SECOND=1: VGT_HS_OFFCHIP_PARAM from GraphicsDriverSetHsOffchipParam's second value instead
//   of its first (ps5-vulkan native/tess_offchip_lease.h:27-44 @ e6d3c3f, GPL-3.0, read for the idea only: the
//   first is 0, the second the buffering in 32-KiB blocks minus one).
static void tf_ring_prefix(std::vector<uint32_t>& p) {
	uint64_t base = 0, o0 = 0, o1 = 0, o2 = 0;
	uint32_t size = 0;
	Bc5TfRingState(&base, &size, &o0, &o1, &o2);
	static const bool second = bc5::env_on(BC5_DIAG_ENV("BC5_DIRECT_OFFCHIP_SECOND")); // exp 0419: "=0" is off
	// A ring with no base or no size is no ring.
	if (base == 0 || size == 0) {
		base = 0;
		size = 0;
		o0   = 0;
	}
	uint32_t   off_v        = static_cast<uint32_t>(second ? o1 : o0);
	bool       write_off    = true;
	bool       gc_ring      = false;
	if ((base == 0 || size == 0) && gc_tf_ring_on()) { // experiment 0189: the ring the title's driver sent /dev/gc
		const uint64_t       b = g_gc_tf_base.load();
		const uint32_t       s = g_gc_tf_size.load();
		static std::atomic<bool> told {false};
		const auto           pm = b != 0 && s != 0 && g_dev ? g_dev->sorted_mappings() : nullptr;
		if (pm != nullptr && covered_sorted(*pm, b, s)) {
			base      = b;
			size      = s;
			gc_ring   = true;
			write_off = false;
		} else if (!told.exchange(true)) {
			journal("tf ring (exp 0189): /dev/gc ring 0x%" PRIx64 " size 0x%x not mapped (yet), not programmed\n", b, s);
		}
	}
	if (gc_hs_offchip_on() && (g_gc_hs_offchip.load() >> 32u) != 0 && (gc_ring || base == 0 || size == 0)) {
		off_v     = static_cast<uint32_t>(g_gc_hs_offchip.load());
		write_off = true;
	}
	if (base == 0 || size == 0) {
		// Experiment 0189: the VGT_HS_OFFCHIP_PARAM row without a ring to program: the parameter alone.
		if (write_off && gc_hs_offchip_on() && (g_gc_hs_offchip.load() >> 32u) != 0) p.insert(p.end(), {0xC0017900u, 0x24fu, off_v});
		return;
	}
	static std::atomic<uint64_t> n {0};
	if ((n++ & 0xffffu) == 0) journal("tf ring: base 0x%" PRIx64 " size 0x%x offchip 0x%" PRIx64 " 0x%" PRIx64 " 0x%" PRIx64 " -> VGT_HS_OFFCHIP_PARAM %s0x%x%s (%" PRIu64 " prefixes)\n", base, size, o0, o1, o2, write_off ? "" : "untouched, not ", off_v, gc_ring ? ", the title's /dev/gc ring" : "", n.load());
	const uint32_t size_dw = static_cast<uint32_t>(std::min<uint64_t>(size / 4, 0xffffu));
	if (gc_ring) {
		static std::atomic<bool> flushed {false};
		if (!flushed.exchange(true)) p.insert(p.end(), {0xC0004600u, 0x40fu, 0xC0004600u, 0x24u}); // EVENT_WRITE VS_PARTIAL_FLUSH (index 4), VGT_FLUSH (index 0)
	}
	if (write_off) p.insert(p.end(), {0xC0027900u, 0x24eu, size_dw, off_v}); // VGT_TF_RING_SIZE, VGT_HS_OFFCHIP_PARAM
	else p.insert(p.end(), {0xC0017900u, 0x24eu, size_dw});                  // VGT_TF_RING_SIZE
	// Experiment 0189: one register = COUNT 1 (PKT3 COUNT is the body's dwords minus one). Exp 0160 wrote 0xC0007900
	// here: an offset without a value, the CP wrote nothing, and the value dword read as a type-0 header that the
	// filter dropped with the next dwords (run 770 programmed no base and cut the title's first packet).
	p.insert(p.end(), {0xC0017900u, 0x250u, static_cast<uint32_t>(base >> 8u)});           // VGT_TF_MEMORY_BASE
	p.insert(p.end(), {0xC0017900u, 0x261u, static_cast<uint32_t>(base >> 40u) & 0xffu});  // VGT_TF_MEMORY_BASE_HI
}
// Experiment 0418: the GS ring sizes the title's driver sent /dev/gc ("set gs ring sizes", 0xc00c8110), written with the
// rings by the table's VGT_GS_RINGS row (always on; BC5_DIRECT_START_STATE_SKIP drops it), as RADV writes
// them (radv_queue.c:372-374 @ 0866ae7: one SET_UCONFIG_REG at VGT_ESGS_RING_SIZE_UMD 0x240, the kernel's CAM row maps
// it to the real register, gfx_v10_0.c:7296-7475 @ v7.2), with RADV's VS_PARTIAL_FLUSH + VGT_FLUSH before the first write
// and before any change of sizes. No title of ours sends the request (exp 0189's trace): the ports rule.
static void gs_rings_prefix(std::vector<uint32_t>& p) {
	if (!gc_gs_rings_on()) return;
	const uint64_t v = g_gc_gs_rings.load();
	if ((v >> 63u) == 0) return;
	const bc5::start_state::GsRings r {static_cast<uint32_t>(v), static_cast<uint32_t>(v >> 32u) & 0x7fffffffu};
	static std::atomic<uint64_t> written {0};
	const bool                   changed = written.exchange(v) != v;
	if (changed) journal("gs rings (exp 0418): VGT_ESGS_RING_SIZE 0x%x, VGT_GSVS_RING_SIZE 0x%x (the _UMD addresses), after a flush\n", r.esgs, r.gsvs);
	bc5::start_state::gs_rings_packets(p, r, changed);
}
// Experiment 0418 section 4: the start-state table's constant rows (bc5/start_state.hpp; start_state_sel() says which),
// first in every prefix, after its CONTEXT_CONTROL and CLEAR_STATE, so the state the title wrote, which the tracker writes
// back after them, still wins. They are uconfig and SH registers a user IB may write: Mesa's gfx10 preamble writes the
// same values with the same packets (src/amd/common/ac_cmdbuf.c @ 0866ae7), and none is in Mesa's privileged list
// (src/amd/common/ac_pm4.c:34 is_privileged_reg).
// This replaces exp 0401's mesa_preamble_prefix and its two switches: CP_COHER_START_DELAY = 0x20 by SET_UCONFIG_REG
// 0x7b (ac_cmdbuf.c:60) and SPI_SHADER_REQ_CTRL_PS = 0x7 by SET_SH_REG 0x30 (ac_cmdbuf.c:444-446) are rows here, with
// GE_MIN_VTX_INDX 0, GE_MAX_VTX_INDX ~0 and VGT_INSTANCE_BASE_ID 0; neither register is in the tracker (the static audit
// of 2026-11-02: the title never writes them). All five are the values the umr read of 2026-11-13 found in play (exp
// 0418 impl/README.md result 1), written there today by the Mesa clients on the shared ring; the rows make the host
// independent of them.
static void start_state_prefix(std::vector<uint32_t>& p) {
	static const std::vector<uint32_t> packets = bc5::start_state::constant_packets(start_state_sel());
	static std::atomic<bool>           told {false};
	if (!told.exchange(true)) {
		const auto& s = start_state_sel();
		journal("start state (exp 0418): %zu dwords of constant rows in every prefix (rows 0x%x, skipped 0x%x)\n", packets.size(), s.on, s.skipped);
	}
	if (packets.empty()) return;
	p.insert(p.begin() + static_cast<std::ptrdiff_t>(bc5::start_state::insert_at(p)), packets.begin(), packets.end());
}
static std::vector<uint32_t> prefix_of(const bc5::full_state::Tracker& t) {
	std::vector<uint32_t> p = t.emit_prefix();
	start_state_prefix(p); // experiment 0418 (exp 0401's two registers among its rows)
	tf_ring_prefix(p);     // experiment 0160
	gs_rings_prefix(p);    // experiment 0418
	return p;
}
static std::atomic<uint64_t> g_dry_bufs {0}, g_dry_splits {0}, g_dry_prefix {0}, g_dry_ns {0}, g_dry_max_ns {0}, g_dry_kept {0}, g_dry_ok {0},
    g_dry_failed {0};

static void register_label_writes(const uint32_t* ib, uint32_t num_dwords, const std::vector<uint32_t>& executed, uint64_t seq, int ring) {
	std::vector<PendingLabelWrite> found;
	for (const uint32_t q: executed) {
		if (q >= num_dwords) continue;
		const uint32_t* w   = ib + q;
		const uint32_t  h   = w[0];
		const uint32_t  c   = (h >> 16u) & 0x3fffu;
		const uint32_t  len = c == 0x3fffu ? 1 : c + 2;
		const uint32_t  op  = (h >> 8u) & 0xffu;
		if ((h >> 30u) != 3 || q + len > num_dwords) continue;
		auto addr = [w](int lo, int hi) { return (static_cast<uint64_t>(w[lo]) & ~3ull) | (static_cast<uint64_t>(w[hi] & 0xffffu) << 32u); };
		if (op == 0x49 && len >= 8) { // RELEASE_MEM: DATA_SEL dword 2 bits 31:29, address 3/4, data 5/6
			const uint32_t ds = w[2] >> 29u;
			if (ds == 1) found.push_back({addr(3, 4), w[5], seq, false});
			if (ds == 2) found.push_back({addr(3, 4), w[5] | (static_cast<uint64_t>(w[6]) << 32u), seq, true});
		} else if (op == 0x47 && len >= 6) { // EVENT_WRITE_EOP: DATA_SEL dword 3 bits 31:29, address 2/3, data 4/5
			const uint32_t ds = w[3] >> 29u;
			if (ds == 1) found.push_back({addr(2, 3), w[4], seq, false});
			if (ds == 2) found.push_back({addr(2, 3), w[4] | (static_cast<uint64_t>(w[5]) << 32u), seq, true});
		} else if (op == 0x37 && len >= 5) { // WRITE_DATA to memory: address 2/3, data from 4
			const uint32_t dst = (w[1] >> 8u) & 0xfu;
			if (dst == 1 || dst == 2 || dst == 5) {
				if (len >= 6) found.push_back({addr(2, 3), w[4] | (static_cast<uint64_t>(w[5]) << 32u), seq, true});
				else found.push_back({addr(2, 3), w[4], seq, false});
			}
		}
	}
	if (found.empty()) return;
	std::lock_guard lk(g_plw_mutex);
	static uint64_t order = 0;
	for (auto& w: found) {
		w.ring  = ring;
		w.order = ++order;
	}
	if (g_plw.size() > 8192) g_plw.erase(g_plw.begin(), g_plw.begin() + 4096);
	g_plw.insert(g_plw.end(), found.begin(), found.end());
}

// BC5 experiment 0430 (tag ho430): the fix of the second title's cross-queue GPU hangs (F848, F852, F858), built in on
// 2026-11-18 (the maintainer: "Wprowadzamy wszystkie 4 poprawki. Usuń przełączniki i wybuduj w kod."). No switch.
// The hang: a compute buffer (acb) waits for a label == V that a graphics or compute buffer on another ring releases. The
// host decides such a wait at submit. When the label still held last frame's V, the wait passed, the acb ran ahead of its
// writer and overwrote memory the writer's passes still read (junk indirect grids, then a ring timeout). On the console
// the queue decides the wait when it reaches the packet. Four parts, measured on the R-on tree (h430M1-M3 clean, the
// maintainer's 57-minute play clean of the class; the arms without F16 faulted, h430J1):
// - F10 (the targeted flush): at an acb's wait on L, every other thread's open chain (ADR 0010 section B) whose own packets
//   write L goes to the device first: made due for the watchdog, or flushed by its owner at its call's end when the owner
//   is inside its submit call; a chain being submitted is waited for until its writes are registered. bc5-ring polls, at
//   most 2 ms, through F10's own registry of the slots (g_f10_reg_mu, which nothing submits under), with try_locks only
//   (LESSONS R62); a busy list is looked at again, a busy slot is waited for as a possible writer.
// - F2 + F4: a wait found satisfied while a job not yet completed on ANOTHER ring has a registered pending write to L is
//   ordered behind that job by the kernel (a CS dependency of this buffer's submission), unless that job holds a kept GPU
//   wait on a label this buffer writes (a cycle: left as it is).
// - F16: at F10's bound, a writer in flight (inside its submit_now) is waited for until its submit returns, at most 50 ms;
//   a writer in back-pressure (phase 1) or draining the GPU (phase 4) may wait on work only bc5-ring submits, so it is
//   not waited for past 2 ms more.
// - F18: a bound F16 did not settle: each pending slot is looked at again for up to 200 us; an open writer of L is made
//   due and waited for, a slot still busy is waited for as a possible writer, a slot that writes nothing of L is dropped;
//   50 ms bound and the same phase gate.
// A bound that still stands decides the wait as before. The normal build counts all of it (a 60-s line, the first 64
// waits of F16/F18 and every one that did not settle); the lean build has none of the counting.
namespace ho430 {
struct Store {
	std::mutex                                                m;
	std::map<std::pair<int, uint64_t>, std::vector<uint64_t>> job_waits; // (ring, seq) -> the labels of its kept GPU waits (the cycle check)
#ifndef BC5_LEAN
	uint64_t f2_cycle = 0, f4_fence = 0;
	uint64_t f10_calls = 0, f10_hit = 0, f10_gone = 0, f10_bound = 0, f10_busy = 0, f10_ns = 0;
	uint64_t f16_wait = 0, f16_ok = 0, f16_bound = 0, f16_stop[5] {}, f16_ns = 0, f16_max = 0;
	uint64_t f18_wait = 0, f18_ok = 0, f18_none = 0, f18_bound = 0, f18_stop[5] {}, f18_cls[3] {}, f18_ns = 0, f18_max = 0;
	uint64_t stands = 0; // bounds that still stood after F16 and F18
#endif
};
inline Store& st() {
	static Store s;
	return s;
}
inline uint32_t pkt_len(uint32_t h) {
	const uint32_t type = h >> 30u;
	if (type != 3 && type != 0) return 1;
	const uint32_t c = (h >> 16u) & 0x3fffu;
	return c == 0x3fffu ? 1 : c + 2;
}
// One pass over a submitted job: its kept GPU waits on memory, for the cycle check of the waits after it.
// executed: the offsets the filter kept, in order.
inline void job_submitted(const uint32_t* ib, uint32_t num_dwords, const std::vector<uint32_t>& executed, uint64_t seq, int ring, const char* kind) {
	(void)kind;
	std::vector<uint64_t> waits;
	size_t                e = 0;
	for (uint32_t q = 0; q < num_dwords;) {
		const uint32_t h = ib[q], len = pkt_len(h);
		if (q + len > num_dwords) break;
		while (e < executed.size() && executed[e] < q) e++;
		const bool ran = e < executed.size() && executed[e] == q;
		if ((h >> 30u) == 3) {
			const uint32_t  op = (h >> 8u) & 0xffu;
			const uint32_t* w  = ib + q;
			if ((op == 0x3c || op == 0x93) && len >= 4 && ((w[1] >> 4u) & 1u) != 0 && ran)
				waits.push_back((static_cast<uint64_t>(w[2]) & ~3ull) | (static_cast<uint64_t>(w[3] & 0xffffu) << 32u));
		}
		q += len;
	}
	Store&          s = st();
	std::lock_guard lk(s.m);
	if (!waits.empty()) {
		s.job_waits[{ring, seq}] = std::move(waits);
		if (s.job_waits.size() > 4096) s.job_waits.erase(s.job_waits.begin());
	}
#ifndef BC5_LEAN
	static uint64_t last_line = 0;
	const uint64_t  now       = SoftCp::now_ns();
	if (now - last_line > 60'000'000'000ull) {
		last_line = now;
		journal("ho430 (exp 0430): t %.1f s: F4 fences %" PRIu64 ", F2 cycles left as they are %" PRIu64 "; F10 acb waits %" PRIu64 ", with a chain writing the label %" PRIu64 ", gone %" PRIu64 ", bound %" PRIu64 ", list busy %" PRIu64 " (%.1f ms in all); "
		        "F16 in-flight waits %" PRIu64 ": returned %" PRIu64 ", 50 ms bound %" PRIu64 ", not waited (back-pressure/draining) %" PRIu64 "/%" PRIu64 ", %.1f ms in all, longest %.3f ms; "
		        "F18 bounds looked at %" PRIu64 ": writers went %" PRIu64 ", no writer %" PRIu64 ", 50 ms bound %" PRIu64 ", not waited (back-pressure/draining) %" PRIu64 "/%" PRIu64 ", slots open writer/not a writer/still busy %" PRIu64 "/%" PRIu64 "/%" PRIu64 ", %.1f ms in all, longest %.3f ms; "
		        "bounds that stood %" PRIu64 "\n",
		        timing_now(), s.f4_fence, s.f2_cycle, s.f10_calls, s.f10_hit, s.f10_gone, s.f10_bound, s.f10_busy, static_cast<double>(s.f10_ns) / 1e6,
		        s.f16_wait, s.f16_ok, s.f16_bound, s.f16_stop[1], s.f16_stop[4], static_cast<double>(s.f16_ns) / 1e6, static_cast<double>(s.f16_max) / 1e6,
		        s.f18_wait, s.f18_ok, s.f18_none, s.f18_bound, s.f18_stop[1], s.f18_stop[4], s.f18_cls[0], s.f18_cls[1], s.f18_cls[2], static_cast<double>(s.f18_ns) / 1e6, static_cast<double>(s.f18_max) / 1e6,
		        s.stands);
	}
#endif
}
inline void job_done(uint64_t seq, int ring, bool all) {
	Store&          s = st();
	std::lock_guard lk(s.m);
	if (all) s.job_waits.clear();
	else s.job_waits.erase({ring, seq});
}
// F10: true while one of `mine` still has L open (unsubmitted) or in flight (its writes not registered yet), or is busy.
inline bool f10_pending(uint64_t label, const std::vector<ChainSlot*>& mine) {
	if (!g_f10_reg_mu.try_lock()) return true;
	bool pending = false;
	for (ChainSlot* cs: mine) {
		if (std::find(g_f10_reg.begin(), g_f10_reg.end(), cs) == g_f10_reg.end()) continue; // its thread is gone
		if (!cs->mu.try_lock()) { pending = true; break; }
		if ((!cs->c.segs.empty() && std::find(cs->f10_writes.begin(), cs->f10_writes.end(), label) != cs->f10_writes.end()) ||
		    std::find(cs->f10_flight.begin(), cs->f10_flight.end(), label) != cs->f10_flight.end()) pending = true;
		cs->mu.unlock();
		if (pending) break;
	}
	g_f10_reg_mu.unlock();
	return pending;
}
// The phase gate of F16 and F18: true when one of the slots has been in back-pressure (1) or draining the GPU (4) for 2 ms.
inline bool phase_gate(const std::vector<ChainSlot*>& sl, uint64_t& t_ph, int& ph_out) {
	if (!g_f10_reg_mu.try_lock()) return false;
	int ph = 0;
	for (ChainSlot* cs: sl)
		if (std::find(g_f10_reg.begin(), g_f10_reg.end(), cs) != g_f10_reg.end()) {
			const int p = cs->f16_phase.load();
			if (p == 1 || p == 4) ph = p;
		}
	g_f10_reg_mu.unlock();
	const uint64_t now = SoftCp::now_ns();
	if (ph == 0) t_ph = 0;
	else if (t_ph == 0) t_ph = now;
	else if (now - t_ph >= 2'000'000ull) {
		ph_out = ph;
		return true;
	}
	return false;
}
inline void f10_observe(uint64_t label) {
	if (g_chain_mode < 2) return;
	const uint64_t          t0 = SoftCp::now_ns();
	std::vector<ChainSlot*> mine, seen;
	bool                    list_busy = false;
	for (;;) { // a busy list is looked at again until F10's 2 ms bound; slots already seen are not looked at twice
		list_busy = false;
		if (!g_f10_reg_mu.try_lock()) list_busy = true;
		else {
			for (ChainSlot* cs: g_f10_reg) {
				if (cs == &g_chain_tl || std::find(seen.begin(), seen.end(), cs) != seen.end()) continue;
				seen.push_back(cs);
				if (!cs->mu.try_lock()) { // mid-append or at its swap: its write may be pending, so it is waited for below
					mine.push_back(cs);
					continue;
				}
				const bool writes = !cs->c.segs.empty() && std::find(cs->f10_writes.begin(), cs->f10_writes.end(), label) != cs->f10_writes.end();
				if (writes && cs->hold.empty()) {
					mine.push_back(cs);
					if (cs->in_submit) cs->f10_wanted = true; // its owner flushes at its call's end
					else cs->open_ns = 1;                     // due now for the watchdog
				} else if (std::find(cs->f10_flight.begin(), cs->f10_flight.end(), label) != cs->f10_flight.end()) {
					mine.push_back(cs); // being submitted now: wait for its writes' registration
				} // a writer under the ADR 0013 hold is left to it
				cs->mu.unlock();
			}
			g_f10_reg_mu.unlock();
		}
		if (!list_busy || SoftCp::now_ns() - t0 >= 2'000'000ull) break;
		std::this_thread::yield();
	}
	bool bound = false;
	if (!mine.empty()) {
		chainwd_wake();
		for (;;) {
			if (!f10_pending(label, mine)) break;
			if (SoftCp::now_ns() - t0 >= 2'000'000ull) {
				bound = true;
				break;
			}
			std::this_thread::sleep_for(std::chrono::microseconds(20));
		}
	}
	// F16: the writers still in flight at the bound: wait for their submit_now to return.
	int      f16_res = 0, f16_ph = 0; // 1 returned, 2 50 ms bound, 3 given up by phase
	uint64_t f16_t   = 0;
	if (bound && g_f10_reg_mu.try_lock()) {
		struct W {
			ChainSlot* cs;
			uint64_t   done;
		};
		std::vector<W>          fl;
		std::vector<ChainSlot*> fls;
		for (ChainSlot* cs: mine) {
			if (std::find(g_f10_reg.begin(), g_f10_reg.end(), cs) == g_f10_reg.end() || !cs->mu.try_lock()) continue;
			if (std::find(cs->f10_flight.begin(), cs->f10_flight.end(), label) != cs->f10_flight.end()) fl.push_back({cs, cs->f16_done.load()});
			cs->mu.unlock();
		}
		g_f10_reg_mu.unlock();
		if (!fl.empty()) {
			const uint64_t t1   = SoftCp::now_ns();
			uint64_t       t_ph = 0;
			for (;;) {
				if (g_f10_reg_mu.try_lock()) {
					std::erase_if(fl, [](const W& w) { return std::find(g_f10_reg.begin(), g_f10_reg.end(), w.cs) == g_f10_reg.end() || w.cs->f16_done.load() != w.done; });
					g_f10_reg_mu.unlock();
					if (fl.empty()) {
						f16_res = 1;
						break;
					}
					fls.clear();
					for (const W& w: fl) fls.push_back(w.cs);
					if (phase_gate(fls, t_ph, f16_ph)) {
						f16_res = 3;
						break;
					}
				}
				if (SoftCp::now_ns() - t1 >= 50'000'000ull) {
					f16_res = 2;
					break;
				}
				std::this_thread::sleep_for(std::chrono::microseconds(20));
			}
			f16_t = SoftCp::now_ns() - t1;
			if (f16_res == 1) bound = false;
		}
	}
	// F18: a bound still standing.
	int      f18_res = 0, f18_ph = 0; // 1 the writers went, 2 50 ms bound, 3 given up by phase, 4 no writer of L left
	uint64_t f18_t   = 0;
	uint32_t c18[3] {};
	if (bound) {
		std::vector<ChainSlot*> left = mine, w18;
		bool                    fl18 = false, due = false;
		const uint64_t          t1   = SoftCp::now_ns();
		for (;;) {
			if (g_f10_reg_mu.try_lock()) {
				std::erase_if(left, [&](ChainSlot* cs) {
					if (std::find(g_f10_reg.begin(), g_f10_reg.end(), cs) == g_f10_reg.end()) return true; // its thread is gone
					if (!cs->mu.try_lock()) return false;
					const bool open = !cs->c.segs.empty() && std::find(cs->f10_writes.begin(), cs->f10_writes.end(), label) != cs->f10_writes.end();
					const bool fl   = std::find(cs->f10_flight.begin(), cs->f10_flight.end(), label) != cs->f10_flight.end();
					if (open && !cs->in_submit && cs->hold.empty()) {
						cs->open_ns = 1; // due now for the watchdog
						due         = true;
					}
					cs->mu.unlock();
					if (open) {
						w18.push_back(cs);
						c18[0]++;
					} else if (fl) fl18 = true; // F16's
					else c18[1]++;
					return true;
				});
				g_f10_reg_mu.unlock();
			}
			if (left.empty() || SoftCp::now_ns() - t1 >= 200'000ull) break;
			std::this_thread::yield();
		}
		for (ChainSlot* cs: left) {
			c18[2]++;
			w18.push_back(cs);
		}
		if (due) chainwd_wake();
		if (w18.empty()) f18_res = 4;
		uint64_t t_ph = 0;
		while (f18_res == 0) {
			if (!f10_pending(label, w18)) {
				f18_res = 1;
				break;
			}
			if (phase_gate(w18, t_ph, f18_ph)) {
				f18_res = 3;
				break;
			}
			if (SoftCp::now_ns() - t1 >= 50'000'000ull) {
				f18_res = 2;
				break;
			}
			std::this_thread::sleep_for(std::chrono::microseconds(20));
		}
		f18_t = SoftCp::now_ns() - t1;
		if ((f18_res == 1 || f18_res == 4) && !fl18) bound = false; // nothing of L pending any more
	}
#ifndef BC5_LEAN
	Store&          s = st();
	std::lock_guard lk(s.m);
	s.f10_calls++;
	if (!mine.empty()) s.f10_hit++;
	if (!mine.empty() && !bound && f16_res == 0 && f18_res == 0) s.f10_gone++;
	if (f16_res != 0 || f18_res != 0) s.f10_bound++;
	if (list_busy) s.f10_busy++;
	if (f16_res != 0) {
		s.f16_wait++;
		if (f16_res == 1) s.f16_ok++;
		else if (f16_res == 2) s.f16_bound++;
		else s.f16_stop[f16_ph]++;
		s.f16_ns += f16_t;
		if (f16_t > s.f16_max) s.f16_max = f16_t;
		if (s.f16_wait <= 64 || f16_res != 1)
			journal("ho430 F16: in-flight writer of 0x%" PRIx64 " %s after %.3f ms more (2 ms before)%s\n", label,
			        f16_res == 1 ? "returned" : f16_res == 2 ? "STILL IN SUBMIT at the 50 ms bound" : "not waited on", static_cast<double>(f16_t) / 1e6,
			        f16_res == 3 ? (f16_ph == 1 ? ": it is in back-pressure" : ": it drains the GPU") : "");
	}
	if (f18_res != 0) {
		s.f18_wait++;
		if (f18_res == 1) s.f18_ok++;
		else if (f18_res == 4) s.f18_none++;
		else if (f18_res == 2) s.f18_bound++;
		else s.f18_stop[f18_ph]++;
		for (int k = 0; k < 3; k++) s.f18_cls[k] += c18[k];
		s.f18_ns += f18_t;
		if (f18_t > s.f18_max) s.f18_max = f18_t;
		if (s.f18_wait <= 64 || bound)
			journal("ho430 F18: bound on 0x%" PRIx64 ": pending slots open writer/not a writer/still busy %u/%u/%u; %s after %.3f ms more%s\n", label, c18[0], c18[1], c18[2],
			        f18_res == 1 ? "the writers went" : f18_res == 4 ? "no writer of the label among them" : f18_res == 2 ? "A WRITER STILL PENDING at the 50 ms bound" : "a writer not waited on", static_cast<double>(f18_t) / 1e6,
			        f18_res == 3 ? (f18_ph == 1 ? ": it is in back-pressure" : ": it drains the GPU") : "");
	}
	if (bound) {
		s.stands++;
		journal("ho430: THE BOUND STANDS on 0x%" PRIx64 " after %.3f ms: the wait is decided as before (%" PRIu64 " so far)\n", label, static_cast<double>(SoftCp::now_ns() - t0) / 1e6, s.stands);
	}
	s.f10_ns += SoftCp::now_ns() - t0;
#else
	(void)f16_t;
	(void)f18_t;
	(void)f16_ph;
	(void)f18_ph;
#endif
}
// At a wait of a buffer about to be submitted (submit_split), before the host decides it.
inline void at_wait(const uint32_t* p, bool is64, uint64_t label, const char* kind, int ring, const uint32_t* ib, uint32_t num_dwords, uint32_t off) {
	(void)off;
	if (kind != nullptr && std::strncmp(kind, "acb", 3) == 0) f10_observe(label); // F10: the chains that write this label go first
	if (!wait_satisfied(p, is64)) return;
	std::vector<std::pair<int, uint64_t>> others; // (ring, seq) of pending writes to this label on another ring
	{
		std::lock_guard lk(g_plw_mutex);
		for (const auto& w: g_plw)
			if (w.label == label && w.ring != ring && std::find(others.begin(), others.end(), std::make_pair(w.ring, w.seq)) == others.end()) others.emplace_back(w.ring, w.seq);
	}
	if (others.empty()) return;
	// The cycle check: a writer job holding a kept GPU wait on a label this buffer writes cannot complete before this buffer runs.
	std::vector<uint64_t> writes;
	for (uint32_t q = 0; q < num_dwords;) {
		const uint32_t h = ib[q], len = pkt_len(h);
		if (q + len > num_dwords) break;
		const uint32_t op = (h >> 8u) & 0xffu;
		if ((h >> 30u) == 3 && ((op == 0x49 && len >= 6) || (op == 0x37 && len >= 4) || (op == 0x47 && len >= 4))) {
			const int lo = op == 0x49 ? 3 : 2;
			writes.push_back((static_cast<uint64_t>(ib[q + lo]) & ~3ull) | (static_cast<uint64_t>(ib[q + lo + 1] & 0xffffu) << 32u));
		}
		q += len;
	}
	Store&           s = st();
	std::unique_lock lk(s.m);
	for (const auto& o: others) {
		const auto it = s.job_waits.find(o);
		if (it == s.job_waits.end()) continue;
		for (const uint64_t l: it->second)
			if (std::find(writes.begin(), writes.end(), l) != writes.end()) {
#ifndef BC5_LEAN
				const uint64_t k = s.f2_cycle++;
				if (k < 64 || (k & 0xfffu) == 0)
					journal("ho430 F2: %s wait at %u on 0x%" PRIx64 " (satisfied) has a pending write from job %" PRIu64 " on ring %d, which waits on a label this buffer writes: a cycle, not ordered (%" PRIu64 " so far)\n", kind, off, label, o.second, o.first, k + 1);
#endif
				return;
			}
	}
#ifndef BC5_LEAN
	const uint64_t k = s.f4_fence++;
#endif
	lk.unlock();
	for (const auto& o: others) bc5::direct::Device::add_next_submit_dependency(o.first, o.second); // F4: the kernel orders it
#ifndef BC5_LEAN
	if (k < 64 || (k & 0x3fffu) == 0)
		journal("ho430 F4: %s wait at %u on 0x%" PRIx64 " was satisfied with a pending write from job %" PRIu64 " on ring %d (%zu such jobs): the submission depends on it (%" PRIu64 " so far)\n", kind, off, label,
		        others.front().second, others.front().first, others.size(), k + 1);
#endif
}
} // namespace ho430
static void forget_label_writes(uint64_t seq, int ring, bool all) {
	std::lock_guard lk(g_plw_mutex);
	ho430::job_done(seq, ring, all); // exp 0430 (tag ho430)
	if (all) {
		g_plw.clear();
		return;
	}
	g_plw.erase(std::remove_if(g_plw.begin(), g_plw.end(), [seq, ring](const PendingLabelWrite& w) { return w.seq == seq && w.ring == ring; }), g_plw.end());
}

// Experiment 0401 series e11 (tag m11): the label writes the jobs in flight had pending at a timeout (exp 0055's list, kept by
// m11_keep_lost just before forget_label_writes clears it) and what the reopen does with them (BC5_DIRECT_RESET_LABELS,
// BC5_DIRECT_RESET_LABEL_JOURNAL; the switches are in m11's block above learned_add).
static std::vector<PendingLabelWrite> g_m11_lost;         // under g_plw_mutex
static uint64_t                       g_m11_lost_for = 0; // the reopen they belong to (g_m11_reopens + 1 when kept)
// BC5 experiment 0412 (tag rl412, README section 62): the lost jobs' label writes when TWO jobs time out in one hang.
// m11_keep_lost() (exp 0401 e11) copies the pending label writes at a timeout so that the reopen can write them
// (BC5_DIRECT_RESET_LABELS). It is called once per timed-out job, and each call is followed by a forget of ALL
// pending writes. With two jobs timed out together (a draw buffer and a compute buffer: his play of 2026-11-13, and
// the pairs of F260, sections 38 and 53) the second call copied the list the first call's forget had just emptied,
// over the kept one: "0 label writes of the lost jobs", nothing written, and the title waited for ever on labels of
// the lost compute buffer. BC5_DIRECT_RESET_LABELS_ADD=1 (default off): a second keep for the SAME reopen adds to
// what is kept instead of replacing it. This text is included by the main unit and by the CPU test rlabels0412.cpp.
namespace rl412 {
inline bool on() {
	static const bool v = [] {
		const char* e = nullptr; /* exp 0419: option removed */
		return e != nullptr && e[0] != 0 && !(e[0] == '0' && e[1] == 0);
	}();
	return v;
}
// kept, kept_for: what is held for a reopen and which reopen; pending: the list at this timeout; for_reopen: the
// reopen this timeout leads to. add = the switch.
template <typename V> inline void keep(V& kept, uint64_t& kept_for, const V& pending, uint64_t for_reopen, bool add) {
	if (add && kept_for == for_reopen) {
		kept.insert(kept.end(), pending.begin(), pending.end());
	} else {
		kept = pending;
	}
	kept_for = for_reopen;
}
} // namespace rl412
static void m11_keep_lost() {
	if (!m11_on(1) && !m11_on(3)) return;
	std::lock_guard lk(g_plw_mutex);
	const size_t rl_before = g_m11_lost.size(); // exp 0412 (tag rl412)
	const bool   rl_same   = g_m11_lost_for == g_m11_reopens.load() + 1;
	rl412::keep(g_m11_lost, g_m11_lost_for, g_plw, g_m11_reopens.load() + 1, rl412::on());
	if (rl_same) journal("e11: a second timed-out job before reopen %" PRIu64 ": %zu label writes were kept, %zu are pending now; kept after this call %zu (BC5_DIRECT_RESET_LABELS_ADD %s; exp 0412, tag rl412)\n",
	                    g_m11_lost_for, rl_before, g_plw.size(), g_m11_lost.size(), rl412::on() ? "on" : "off: the earlier ones are dropped");
}
static uint64_t m11_read(uint64_t a, bool is64) {
	return is64 ? *reinterpret_cast<const volatile uint64_t*>(a) : *reinterpret_cast<const volatile uint32_t*>(a);
}
static void m11_after_reopen(bool ok) {
	const uint64_t reopen = g_m11_reopens.fetch_add(1) + 1;
	const bool     labels = m11_on(1), lj = m11_on(3);
	if (!labels && !lj) return;
	m11_switch_line();
	std::vector<PendingLabelWrite> lost;
	uint64_t                       kept_for = 0;
	{
		std::lock_guard lk(g_plw_mutex);
		lost.swap(g_m11_lost);
		kept_for = g_m11_lost_for;
	}
	if (kept_for != reopen) {
		journal("e11: reopen %" PRIu64 ": no lost label writes kept for it (%zu kept for reopen %" PRIu64 ", dropped)\n", reopen, lost.size(), kept_for);
		return;
	}
	std::vector<char> last(lost.size(), 0); // the last write of its label in the list
	{
		std::set<uint64_t> seen;
		for (size_t i = lost.size(); i-- > 0;) last[i] = seen.insert(lost[i].label).second ? 1 : 0;
	}
	size_t held = 0, outside = 0, superseded = 0, written = 0;
	for (size_t i = 0; i < lost.size(); i++) {
		const PendingLabelWrite& w   = lost[i];
		const bool               in  = g_m11_guest_in(w.label, w.label + (w.is64 ? 8u : 4u));
		const uint64_t           was = in ? m11_read(w.label, w.is64) : 0;
		if (lj && i < 64) {
			journal("e11: lost write %zu: label 0x%" PRIx64 " value 0x%" PRIx64 " (%s), seq %" PRIu64 " ring %d%s; %s 0x%" PRIx64 "\n", i, w.label, w.value, w.is64 ? "64-bit" : "32-bit",
					w.seq, w.ring, last[i] != 0 ? "" : ", superseded", in ? "memory holds" : "not in guest memory, read", was);
		}
		if (!in) {
			outside++;
		} else if (was == w.value) {
			held++;
		} else if (last[i] == 0) {
			superseded++;
		} else if (labels && ok) {
			if (w.is64) {
				*reinterpret_cast<volatile uint64_t*>(w.label) = w.value;
			} else {
				*reinterpret_cast<volatile uint32_t*>(w.label) = static_cast<uint32_t>(w.value);
			}
			written++;
		}
	}
	journal("e11: reopen %" PRIu64 " (%s): %zu label writes of the lost jobs: %zu held already, %zu not in guest memory, %zu superseded, %zu written (BC5_DIRECT_RESET_LABELS %s)\n",
			reopen, ok ? "ok" : "FAILED", lost.size(), held, outside, superseded, written, labels ? "on" : "off");
	if (!lj || lost.empty()) return;
	if (lost.size() > 64) lost.resize(64);
	std::thread([lost = std::move(lost), reopen] {
		for (const int s: {5, 30}) {
			std::this_thread::sleep_for(std::chrono::seconds(s == 5 ? 5 : 25));
			size_t holds = 0;
			for (const PendingLabelWrite& w: lost) {
				const bool     in  = g_m11_guest_in(w.label, w.label + (w.is64 ? 8u : 4u));
				const uint64_t now = in ? m11_read(w.label, w.is64) : 0;
				if (in && now == w.value) holds++;
				journal("e11: %d s after reopen %" PRIu64 ": label 0x%" PRIx64 " %s 0x%" PRIx64 " (the lost value 0x%" PRIx64 ")\n", s, reopen, w.label, in ? "holds" : "not in guest memory, read",
						now, w.value);
			}
			journal("e11: %d s after reopen %" PRIu64 ": %zu of %zu lost label writes held\n", s, reopen, holds, lost.size());
		}
	}).detach();
}
// The CPU test's seams (m110401.cpp); nothing in the emulator calls them.
extern "C" int bc5_m11_0401_switch(int k) {
	return k >= 0 && k < 4 ? (m11_on(k) ? 1 : 0) : -1;
}
static uint64_t g_m11_test_lo = 0, g_m11_test_hi = 0;
static bool m11_guest_in_test(uint64_t lo, uint64_t hi) {
	return lo < hi && lo < g_m11_test_hi && hi > g_m11_test_lo;
}
extern "C" void bc5_m11_0401_guest(uint64_t lo, uint64_t hi) { // [lo, hi) is the only guest memory from now on; hi 0: the real test again
	g_m11_test_lo  = lo;
	g_m11_test_hi  = hi;
	g_m11_guest_in = hi != 0 ? m11_guest_in_test : m11_guest_in_real;
}
extern "C" int bc5_m11_0401_learn_refused(uint64_t fault_addr) {
	const uint64_t lo = (fault_addr & ~0x3ffffffull) > 0x2000000ull ? (fault_addr & ~0x3ffffffull) - 0x2000000ull : 0; // learned_add's window
	return m11_learn_refused(fault_addr, lo, 0x6000000ull) ? 1 : 0;
}
extern "C" void bc5_m11_0401_plw_add(uint64_t label, uint64_t value, int is64, uint64_t seq) {
	std::lock_guard   lk(g_plw_mutex);
	PendingLabelWrite w {label, value, seq, is64 != 0, bc5::direct::kGfxRing, 0};
	w.order = g_plw.size() + 1;
	g_plw.push_back(w);
}
extern "C" uint64_t bc5_m11_0401_timeout(uint64_t seq) { // the completion thread's two calls for a timed-out job; the writes left
	m11_keep_lost();
	forget_label_writes(seq, bc5::direct::kGfxRing, true);
	std::lock_guard lk(g_plw_mutex);
	return g_plw.size();
}
extern "C" void bc5_m11_0401_reopen(int ok) {
	m11_after_reopen(ok != 0);
}
extern "C" uint64_t bc5_m11_0401_reopens() {
	return g_m11_reopens.load();
}
extern "C" uint64_t bc5_m11_0401_head(uint64_t head_reopens) { // the marks left of two after m11_head_check
	std::vector<SoftCp::GpuDone> marks(2);
	m11_head_check(marks, head_reopens, "m110401");
	return marks.size();
}

// Experiment 0133 (BC5_DIRECT_WAIT_TRACE=1): the last pending write of a label, for the journal.
static bool wait_trace() {
	static const bool v_env = BC5_DIAG_ENV("BC5_DIRECT_WAIT_TRACE") != nullptr;
	const bool v = v_env && ::Log::Bc5LoggingOn();
	return v;
}
static void describe_pending(uint64_t a, char* out, size_t cap) {
	std::lock_guard          lk(g_plw_mutex);
	const PendingLabelWrite* last  = nullptr;
	uint64_t                 maxo  = 0;
	int                      count = 0;
	for (const auto& w: g_plw) {
		maxo = std::max(maxo, w.order);
		if (w.label != a) continue;
		count++;
		if (last == nullptr || w.order >= last->order) last = &w;
	}
	if (last == nullptr) {
		std::snprintf(out, cap, "no pending write");
		return;
	}
	std::snprintf(out, cap, "%d pending writes, last on ring %d value 0x%" PRIx64 " (%" PRIu64 " writes registered since)", count, last->ring, last->value, maxo - last->order);
}

// Will the last pending write of this wait's label satisfy it?
static bool ring_will_satisfy(const uint32_t* p, bool is64, int ring) {
	const uint32_t function = p[1] & 7u;
	const uint64_t a        = (p[2] & ~3u) | (static_cast<uint64_t>(p[3] & 0xffffu) << 32u);
	std::lock_guard lk(g_plw_mutex);
	const PendingLabelWrite* last = nullptr;
	for (const auto& w: g_plw) {
		if (w.label == a && (last == nullptr || w.order >= last->order)) last = &w;
	}
	if (last == nullptr) return false;
	// exp 0428 (tag w428): with the acb rings on, a wait whose label's last pending write is on another ring stays for the GPU
	// (ADR 0009 waits step 3, "all", as F178); only jobs already submitted are pending, so the waits form no cycle.
	if (last->ring != ring && w428_rings() == 0) return false; // one ring since exp 0342 (exp 0419, candidate G)
	if (is64) {
		if (!last->is64) return false;
		const uint64_t ref = p[4] | (static_cast<uint64_t>(p[5]) << 32u), mask = p[6] | (static_cast<uint64_t>(p[7]) << 32u);
		const uint64_t vm = last->value & mask, rm = ref & mask;
		switch (function) {
			case 1: return vm < rm;
			case 2: return vm <= rm;
			case 3: return vm == rm;
			case 4: return vm != rm;
			case 5: return vm >= rm;
			case 6: return vm > rm;
			default: return false;
		}
	}
	return SoftCp::compare(function, static_cast<uint32_t>(last->value), p[5], p[4]);
}

// Experiment 0160 (diagnostic): BC5_DIRECT_GE_PROBE=<min>:<max> — in every prefixed graphics buffer whose
// title part has min..max dwords, eight COPY_DATA register reads go in front of each draw and dispatch
// (WD_INDEX_BUF_BASE/HI 0xc256/7, WD_POS_BUF_BASE 0xc252, WD_CNTL_SB_BUF_BASE 0xc254, GE_DMA_FIRST_INDEX
// 0xc251, VGT_INDEX_TYPE 0xc243, GE_CNTL 0xc25b, CP_INDEX_BASE_ADDR 0xc0f8; Mesa gfx10 register JSON via
// tools/bc5-agc/regdb) into a slot of the backend's GDS shadow buffer (otherwise unused: every job has
// the GDS partition), which the timeout probe prints for the buffer that timed out.
struct GeProbeSlot {
	uint32_t slot, offset, op;
};
static thread_local std::vector<GeProbeSlot> t_ge_probe;
static std::atomic<uint32_t>                g_ge_probe_next {0};
static constexpr uint32_t                   kGeProbeRegs[8] = {0xc256u, 0xc257u, 0xc252u, 0xc254u, 0xc251u, 0xc243u, 0xc25bu, 0xc0f8u};
static constexpr uint64_t                   kGeProbeOff      = 0xc000; // byte offset in the 64 KiB shadow
static constexpr uint32_t                   kGeProbeSlots    = 512;    // 32 bytes each
static std::pair<uint32_t, uint32_t> ge_probe_range() {
	static const std::pair<uint32_t, uint32_t> r = [] {
		std::pair<uint32_t, uint32_t> v {0, 0};
		if (const char* e = BC5_DIAG_ENV("BC5_DIRECT_GE_PROBE"); e != nullptr) {
			unsigned a = 0, b = 0;
			if (std::sscanf(e, "%u:%u", &a, &b) == 2) v = {a, b};
		}
		return v;
	}();
	return r;
}
static void submit_split(const uint32_t* ib, uint32_t num_dwords, const char* kind) {
	t_wait_given_up = false;
	t_keep_waits.clear();
	std::vector<uint64_t> written;
	uint32_t start = 0, i = 0;
	// Run 122 (BC5_DIRECT_NO_PIECES=1 brings the old way back): a wait that is not satisfied at once
	// splits the buffer — what precedes the wait goes to the GPU first, so that its own label writes
	// execute (the water in the second level: the main buffer's wait at 11097 is on a compute tail
	// that waits for the label this very buffer sets at 1588), then the wait is served on the CPU,
	// and the rest follows with the buffer's register state replayed in front of it (run 44's
	// objection to pieces: foreign SH state between them).
	// Run 123: these pieces faulted from the first frames (0x800000005000, a shader fetch with
	// foreign state); the pieces behind a full-state prefix (experiments 0077-0079, 0119) replaced them.
	std::optional<bc5::full_state::Tracker> dry;     // experiment 0074
	uint32_t                                dry_at = 0;
	std::vector<uint32_t>                   full_prefix; // the prefix of the piece at start
	bool                                    full_used = false;
	if (prefix_all() && std::strcmp(kind, "dcb") == 0 && (prefix_mode() == 1 || ib_has_draw(ib, num_dwords))) { // experiment 0157
		full_prefix = prefix_mode() == 3 ? sx_prefix(t_fs_before) : prefix_of(t_fs_before);
		full_used   = !full_prefix.empty();
	}
	bool cs_used = false; // experiment 0195: the compute prefix stands in front where prefix_all() would let the full one
	if (!full_used && cs_prefix_mode() != 0 && std::strcmp(kind, "dcb") == 0 && g_dev) {
		const int at = cs_inherit_at(ib, num_dwords, *g_dev->sorted_mappings());
		if (at >= 0) {
			uint64_t                     pgm = 0;
			std::vector<uint32_t>        cs  = cs_prefix(t_fs_before, &pgm);
			static std::atomic<uint64_t> n_cs {0};
			const uint64_t               k = n_cs++;
			if (k < 64 || (k & 0x3ffu) == 0) {
				uint32_t r1 = 0, r2 = 0;
				t_fs_before.get(bc5::full_state::Sh, 0x212u, r1);
				t_fs_before.get(bc5::full_state::Sh, 0x213u, r2);
				journal("cs prefix (exp 0195): t %.3f s dcb %u dwords dispatches at %d before it sets a program; the queue's program 0x%010" PRIx64 " rsrc1 %08x rsrc2 %08x, %zu dwords of compute state%s (%" PRIu64 " such buffers)\n",
				        timing_now(), num_dwords, at, pgm, r1, r2, cs.size(), cs_prefix_mode() == 1 ? " in front" : ", journal only", k + 1);
			}
			if (cs_prefix_mode() == 1 && !cs.empty()) {
				full_prefix.swap(cs);
				full_used = cs_used = true;
			}
		}
	}
	// Experiment 0381 (F679): the graphics queue's compute registers back after a merged acb, by the CS prefix's path
	// (full_prefix + cs_used: same segment, same pieces).
	if (!full_used && std::strcmp(kind, "dcb") == 0 && g_dev && acb_restore_on() && acb_restore_wants(ib, num_dwords)) {
		size_t                       regs = 0;
		std::vector<uint32_t>        re   = acb_restore_runs(t_fs_before, &regs);
		static std::atomic<uint64_t> n_re {0};
		const uint64_t               k = n_re++;
		if (k < 16 || (k & 0x3ffu) == 0)
			journal("acb state restore (exp 0381): t %.3f s dcb %u dwords, %zu registers in %zu dwords (%" PRIu64 " such buffers)\n", timing_now(), num_dwords, regs, re.size(), k + 1);
		if (!re.empty()) {
			full_prefix.swap(re);
			full_used = cs_used = true;
		}
	}
	if (!full_used && std::strcmp(kind, "acb") == 0) { // experiment 0401: the acb's own queue state, as the CS prefix above for a dcb
		std::vector<uint32_t> cs = acb_inherit_mode() != 0 ? acb_inherit_prefix(ib, num_dwords, t_acb_from) : acb_cs_prefix(ib, num_dwords); // + exp 0403
		if (!cs.empty()) {
			full_prefix.swap(cs);
			full_used = cs_used = true;
		}
	}
	// Experiment 0118: a piece goes to the GPU as one job with its full-state prefix in front. As two
	// jobs (prefix, then the piece) the ring thread could submit between them, and ASTRO BOT's colour,
	// depth and program addresses then came out tagged 0x80 in bits 47:40 (CB/DB and SQC faults, two
	// machine-downs).
	const auto submit_prefixed = [&](const std::vector<uint32_t>& pre, const uint32_t* part, uint32_t n) {
		if (pre.empty()) {
			submit_one(part, n, kind);
			return;
		}
		{ // ADR 0010: prefix and part as one segment of the chain; the instrumented copies keep the old path
			static const bool instrumented = ge_probe_range().second != 0;
			if (chain_on() && !instrumented) {
				chain_append(pre.data(), static_cast<uint32_t>(pre.size()), part, n, kind, false);
				return;
			}
		}
		std::vector<uint32_t> one;
		one.reserve(pre.size() + n);
		one.insert(one.end(), pre.begin(), pre.end());
		std::vector<uint32_t> ge_new_off; // experiment 0160: part offset -> offset in one, when instrumented
		{
			const auto [gmin, gmax] = ge_probe_range();
			t_ge_probe.clear();
			const bool ge_capture = gmax != 0 && n >= gmin && n <= gmax && g_dev && g_dev->gds_shadow_va() != 0;
			if (ge_capture && std::strcmp(kind, "dcb") == 0) {
				ge_new_off.assign(n + 1, 0);
				for (uint32_t q = 0; q < n;) {
					const uint32_t h = part[q], type = h >> 30u;
					uint32_t       len = 1;
					if (type == 3 || type == 0) { const uint32_t c = (h >> 16u) & 0x3fffu; len = c == 0x3fffu ? 1 : c + 2; }
					if (q + len > n) len = n - q;
					const uint32_t op = type == 3 ? (h >> 8u) & 0xffu : 0;
					if (ge_capture && type == 3 && (op == 0x2d || op == 0x38 || op == 0x27 || op == 0x24 || op == 0x25 || op == 0x2c || op == 0x35 || op == 0x15 || op == 0x16)) {
						const uint32_t slot = g_ge_probe_next++ % kGeProbeSlots;
						const uint64_t dst  = g_dev->gds_shadow_va() + kGeProbeOff + static_cast<uint64_t>(slot) * 32;
						for (uint32_t k = 0; k < 8; k++) {
							const uint64_t a = dst + k * 4;
							one.insert(one.end(), {0xC0044000u, 0x00100500u, kGeProbeRegs[k], 0u, static_cast<uint32_t>(a), static_cast<uint32_t>(a >> 32u) & 0xffffu});
						}
						t_ge_probe.push_back({slot, q, op});
					}
					ge_new_off[q] = static_cast<uint32_t>(one.size());
					one.insert(one.end(), part + q, part + q + len);
					q += len;
				}
				ge_new_off[n] = static_cast<uint32_t>(one.size());
				static std::atomic<uint64_t> n_inst {0};
				if ((n_inst++ & 0x3fu) == 0) journal("ge probe: %s part %u dwords, %zu captures (slots from %u), %zu dwords in all\n", kind, n, t_ge_probe.size(), t_ge_probe.empty() ? 0u : t_ge_probe.front().slot, one.size());
			} else {
				one.insert(one.end(), part, part + n);
			}
		}
		// Experiment 0132: waits kept for the GPU inside the part, moved into the copy.
		for (auto& w: t_keep_waits) {
			if (w >= part && w < part + n) w = ge_new_off.empty() ? one.data() + pre.size() + (w - part) : one.data() + ge_new_off[static_cast<size_t>(w - part)];
		}
		submit_one(one.data(), static_cast<uint32_t>(one.size()), kind);
		if (ge_new_off.empty()) SoftCp::alias_gpu_executed(one.data(), pre.size(), part, n); // experiment 0157 (not for an instrumented copy, experiment 0160)
		std::erase_if(t_keep_waits, [&one](const uint32_t* w) { return w >= one.data() && w < one.data() + one.size(); });
	};
	while (i < num_dwords) {
		const uint32_t h = ib[i];
		const uint32_t type = h >> 30u;
		uint32_t len = 1;
		if (type == 3 || type == 0) { const uint32_t c = (h >> 16u) & 0x3fffu; len = c == 0x3fffu ? 1 : c + 2; }
		if (i + len > num_dwords) break;
		const uint32_t  op = (h >> 8u) & 0xffu;
		const uint32_t* p  = ib + i;
		if (type == 3) {
			const uint32_t dst_sel = len >= 2 ? (p[1] >> 8u) & 0xfu : 0;
			if (op == 0x37 && len >= 4 && (dst_sel == 1 || dst_sel == 2 || dst_sel == 5)) written.push_back((p[2] & ~3u) | (static_cast<uint64_t>(p[3] & 0xffffu) << 32u));
			else if (op == 0x49 && len >= 6) written.push_back((p[3] & ~3u) | (static_cast<uint64_t>(p[4] & 0xffffu) << 32u));
			else if (op == 0x47 && len >= 4) written.push_back((p[2] & ~3u) | (static_cast<uint64_t>(p[3] & 0xffffu) << 32u));
			else if (op == 0x1e && len >= 4) written.push_back((p[2] & ~3u) | (static_cast<uint64_t>(p[3] & 0xffffu) << 32u));
			else if ((op == 0x3c || op == 0x93) && len >= 4 && ((p[1] >> 4u) & 1u) != 0) {
				const uint64_t label = (p[2] & ~3u) | (static_cast<uint64_t>(p[3] & 0xffffu) << 32u);
				if (std::find(written.begin(), written.end(), label) == written.end()) {
					ho430::at_wait(p, op == 0x93, label, kind, job_ring(kind), ib, num_dwords, i); // exp 0430 (tag ho430): F10, F2 + F4
					if (!wait_satisfied(p, op == 0x93)) chain_flush(1); // ADR 0010: what the chain holds may write this label
					// No split (run 44: pieces of one IB interleave with other processes' submissions,
					// which leave their own SH state behind — a dispatch after a split ran with a
					// foreign COMPUTE_PGM_LO, SQC fault at 0x800000400000). The wait is satisfied
					// on the CPU before the whole IB goes, and NOP-ed by the filter inside it.
					// A compute IB (doorbell consumer thread) may wait long: on the console the
					// compute queue blocks on the gfx queue's frame label while the game's thread
					// keeps submitting DCBs (run 45: the stalled compute IBs were those whose wait
					// on the current frame's gfx label had timed out and ran on unfinished data).
					// The gfx path (the game's thread) waits briefly, like the soft CP.
					// A flip label (sceVideoOutGetBufferLabelAddress: host memory, set by the frame's
					// last RELEASE_MEM, awaited == 0 by the next frame that renders into the same
					// buffer) is cleared by the console's VideoOut when the flip has happened. The
					// flip is immediate here, so a label still set at the wait is cleared (run 73:
					// nobody did, 2 s per frame).
					{
						const auto l0 = reinterpret_cast<uint64_t>(&g_labels[0]);
						if (label >= l0 && label < l0 + sizeof(g_labels) && !wait_satisfied(p, op == 0x93)) {
							// Experiment 0069: with the flip deferred, a label still set at the wait
							// usually belongs to a flip still queued behind the GPU's jobs; clearing it
							// let the frame render into the buffer on screen (tearing whenever the
							// game's thread ran ahead, 4,700 clears in a 2.5 min session with the ring
							// order). The wait is served on the CPU until that flip has happened (it
							// clears the label), at most 100 ms; only then is the label cleared.
							const size_t idx = static_cast<size_t>((label - l0) / sizeof(uint64_t));
							// (Experiment 0071 left this wait to the GPU instead: two machine resets.)
							if (g_flip_pending[idx].load() > 0) {
								const uint64_t tw = SoftCp::now_ns();
								while (g_flip_pending[idx].load() > 0 && !wait_satisfied(p, op == 0x93) && SoftCp::now_ns() - tw < 100'000'000ull) {
									std::this_thread::sleep_for(std::chrono::microseconds(50));
								}
								static std::atomic<uint64_t> n_waited {0};
								if ((n_waited++ & 0x3ffu) == 0) {
									journal("flip label 0x%" PRIx64 " set by a queued flip: waited %.2f ms for it (%" PRIu64 " so far)\n", label,
									        static_cast<double>(SoftCp::now_ns() - tw) / 1e6, n_waited.load());
								}
								frame_profile_wait(on_game_thread(), false, static_cast<double>(SoftCp::now_ns() - tw) / 1e6);
							}
						}
						if (label >= l0 && label < l0 + sizeof(g_labels) && !wait_satisfied(p, op == 0x93)) {
							*reinterpret_cast<volatile uint64_t*>(label & ~7ull) = 0;
							journal("flip label 0x%" PRIx64 " still set at the wait: cleared\n", label);
						}
					}
					static constexpr uint64_t acb_ns = 2000ull * 1'000'000ull;
					// Run 124 (8 ms; exp 0419: a constant, was BC5_DIRECT_DCB_WAIT_MS): a wait of the game's thread that is not served
					// within a frame is a cycle the single ring cannot resolve (the water in the second level,
					// where each frame cost two 2 s limits); the buffer goes on without it.
					static constexpr uint64_t dcb_ns = 8ull * 1'000'000ull;
					const uint64_t limit = std::strcmp(kind, "acb") == 0 ? acb_ns : (on_game_thread() ? dcb_ns : 2'000'000'000ull);
					const uint64_t t0 = SoftCp::now_ns();
					bool ok = false;
					bool dry_here = false;
					if (t_fs_valid && i > start && std::strcmp(kind, "dcb") == 0 && !wait_satisfied(p, op == 0x93)) {
						const uint64_t d0 = SoftCp::now_ns();
						std::shared_ptr<const std::vector<bc5::direct::Mapping>> maps_p = g_dev->sorted_mappings();
						const bc5::full_state::Tracker::Reader read = [&maps_p](uint64_t a, uint64_t bytes) -> const uint32_t* {
							return covered_sorted(*maps_p, a, bytes) ? reinterpret_cast<const uint32_t*>(a) : nullptr;
						};
						if (!dry) {
							dry.emplace(t_fs_before);
							g_dry_bufs++;
						}
						bc5::full_state::Stats dst;
						dry->apply(std::span<const uint32_t>(ib + dry_at, i - dry_at), read, dst);
						dry_at = i;
						const auto     pre = dry->emit_prefix();
						const uint64_t dn  = SoftCp::now_ns() - d0;
						g_dry_splits++;
						g_dry_prefix += pre.size();
						g_dry_ns += dn;
						for (uint64_t m = g_dry_max_ns.load(); dn > m && !g_dry_max_ns.compare_exchange_weak(m, dn);) {
						}
						dry_here = true;
					}
					if (!wait_satisfied(p, op == 0x93) && ring_will_satisfy(p, op == 0x93, job_ring(kind))) {
						static std::atomic<uint64_t> n_kept {0};
						if ((n_kept++ & 0x3ffu) == 0) journal("ring order: %s %u dwords keeps its wait at %u on 0x%" PRIx64 " for the GPU (%" PRIu64 " so far)\n", kind, num_dwords, i, label, n_kept.load());
						t_keep_waits.push_back(p);
						SoftCp::set_gpu_executed(p, len, {0});
						if (dry_here) g_dry_kept++;
						i += len;
						continue;
					}
					if (wait_trace() && !wait_satisfied(p, op == 0x93)) {
						static std::atomic<uint32_t> n_traced {0};
						if (n_traced++ < 20000) {
							char           pend[160];
							describe_pending(label, pend, sizeof(pend));
							const uint64_t now_v = op == 0x93 ? *reinterpret_cast<const volatile uint64_t*>(label & ~7ull) : *reinterpret_cast<const volatile uint32_t*>(label & ~3ull);
							const uint64_t ref   = op == 0x93 && len >= 8 ? (p[4] | (static_cast<uint64_t>(p[5]) << 32u)) : p[4];
							journal("wait trace: t %.3f s %s %u dwords at %u (ring %d) on 0x%" PRIx64 ": function %u reference 0x%" PRIx64 " value 0x%" PRIx64 "; %s\n", timing_now(), kind, num_dwords, i,
							        job_ring(kind), label, p[1] & 7u, ref, now_v, pend);
						}
					}
					// Experiment 0428 (tag w428), exp 0132's form without ADR 0013's held tail (gone since build W): with the acb rings on,
					// the compute rings run beside this buffer, and a wait on a label that compute work writes is a real race. The head
					// goes at once (its label writes may be what the compute queue waits for), then the wait is kept for the GPU as soon
					// as its writer is on a ring, or satisfied on the CPU, within 8 ms; otherwise the path below and its limit.
					if (w428_rings() > 0 && on_game_thread() && std::strcmp(kind, "dcb") == 0 && (!g_dev || !g_dev->wedged()) && !wait_satisfied(p, op == 0x93)) {
						// exp 0428 iterations 3-4 (BC5_DIRECT_ACB_SPLIT_LATE, std::getenv: lean too). The 15:09 hang of the maintainer's play
						// (a GE stall at a partial flush, all compute rings idle) was in a split piece behind a full state prefix, and
						// iteration 2 split ~18 k times per run although ~97 % of those waits were kept for the GPU right after. Iteration
						// 3 (=1) kept a wait whose writer was already on a ring: 0 such waits in w428L1 (17,591 splits), so the writer is the
						// thread's own earlier GFX work, held in its chain or earlier in this IB, which reaches a ring only with the split.
						// Iteration 4 (=2): (a) this IB writes the label before the wait (WRITE_DATA, or RELEASE_MEM with 32/64-bit data)
						// with a value that satisfies it: the GFX ring runs that write first, so the wait is kept with no split and no
						// flush; (b) else the thread's held chain (its earlier buffers) is submitted, with no split of this buffer, and the
						// wait is kept if its writer is now on a ring. Only otherwise the split below. Both are in GPU order on one ring.
						static const int split_late = [] {
							const char* e = std::getenv("BC5_DIRECT_ACB_SPLIT_LATE");
							return e != nullptr && e[0] != 0 ? std::atoi(e) : 0;
						}();
						if (split_late >= 1) {
							int how = 0; // 1 writer on a ring, 2 written earlier in this IB, 3 writer on a ring after the chain went
							if (ring_will_satisfy(p, op == 0x93, bc5::direct::kGfxRing)) how = 1;
							else if (split_late >= 2 && w428_ib_writes_satisfy(ib, i, p, op == 0x93)) how = 2;
							else if (split_late >= 2) {
								chain_flush(1); // ADR 0010: the thread's earlier buffers go; this one is not split
								if (ring_will_satisfy(p, op == 0x93, bc5::direct::kGfxRing)) how = 3;
							}
							if (how != 0) {
#ifndef BC5_LEAN
								g_w428_two[4]++;
								g_w428_late[how]++;
#endif
								t_keep_waits.push_back(p);
								SoftCp::set_gpu_executed(p, len, {0});
								i += len;
								continue;
							}
#ifndef BC5_LEAN
							g_w428_late[0]++;
#endif
						}
						// exp 0428 iteration 6 (SPLIT_LATE=3): w428L10 still split 18,625 times with nothing found in the head or the chain,
						// and the poll after the split then kept 17,881: the writer is later work of ANOTHER thread (the ring thread's
						// acb), which arrives within the poll. So poll first, without splitting: the wait is kept once its writer is on a
						// ring, or goes on once satisfied. Split only when the ring thread is blocked on a label this buffer has written
						// before the wait (exp 0132's cycle: that acb cannot come before our head) or after 8 ms (as before).
						if (split_late >= 3) {
							const uint64_t t2  = SoftCp::now_ns();
							int            res = 0; // 1 kept, 2 satisfied, 3 cycle, 4 timeout
							for (;;) {
								if (wait_satisfied(p, op == 0x93)) { res = 2; break; }
								if (ring_will_satisfy(p, op == 0x93, bc5::direct::kGfxRing)) { res = 1; break; }
								const uint64_t blocked = g_unready_label.load();
								if (blocked != 0 && std::find(written.begin(), written.end(), blocked) != written.end()) { res = 3; break; }
								if (SoftCp::now_ns() - t2 >= 8'000'000ull) { res = 4; break; }
								std::this_thread::sleep_for(std::chrono::microseconds(20));
							}
#ifndef BC5_LEAN
							g_w428_poll[res]++;
#endif
							if (res == 1) {
								t_keep_waits.push_back(p);
								SoftCp::set_gpu_executed(p, len, {0});
								i += len;
								continue;
							}
							if (res == 2) {
								ok = true;
								SoftCp::set_gpu_executed(p, len, {0});
								i += len;
								continue;
							}
						}
						if (split_late >= 1) {
#ifndef BC5_LEAN
							static std::atomic<uint32_t> n_left {0};
							if (n_left++ < 40) {
								char pend[160];
								describe_pending(label, pend, sizeof(pend));
								journal("two rings (exp 0428 split-late): %s %u dwords, wait at %u on 0x%" PRIx64 " still splits: %s\n", kind, num_dwords, i, label, pend);
							}
#endif
						}
						bool split = false;
						if (dry_here && i > start) {
							if ((start > 0 || prefix_all() || cs_used) && !full_prefix.empty()) submit_prefixed(full_prefix, ib + start, i - start);
							else submit_one(ib + start, i - start, kind);
							chain_flush(1); // ADR 0010: the head goes before the wait is polled
							full_prefix = prefix_of(*dry);
							start       = i;
							full_used   = true;
							split       = true;
							g_full_pieces++;
						}
						const uint64_t t1   = SoftCp::now_ns();
						bool           kept = false;
						while (!(ok = wait_satisfied(p, op == 0x93))) {
							if (ring_will_satisfy(p, op == 0x93, bc5::direct::kGfxRing)) {
								kept = true;
								break;
							}
							if (SoftCp::now_ns() - t1 >= 8'000'000ull) break;
							std::this_thread::sleep_for(std::chrono::microseconds(20));
						}
#ifndef BC5_LEAN
						static std::atomic<uint64_t> n_two {0};
						g_w428_two[kept ? 0 : (ok ? 1 : 2)]++;
						if (split) g_w428_two[3]++;
						if ((n_two++ & 0x3ffu) == 0)
							journal("two rings (exp 0428): %s %u dwords waits at %u on 0x%" PRIx64 ": %s after %.2f ms%s\n", kind, num_dwords, i, label,
							        kept ? "kept for the GPU" : (ok ? "satisfied" : "NOT served"), static_cast<double>(SoftCp::now_ns() - t1) / 1e6, split ? ", head split off" : "");
#endif
						(void)split; // only the normal build's counters read it
						if (kept) {
							t_keep_waits.push_back(p);
							SoftCp::set_gpu_executed(p, len, {0});
							i += len;
							continue;
						}
						if (ok) {
							SoftCp::set_gpu_executed(p, len, {0});
							i += len;
							continue;
						}
						// not served within 8 ms: the path below (its limit)
					}
					// Run 123: the compute queue's blocked buffer waits for a
					// label this buffer writes — on the console the two run side by side and this one would
					// block at its wait while the other goes on; here this buffer cannot reach the GPU before
					// its wait is served, so it goes without waiting (the water in the second level: the
					// fluid tail's results are a frame late).
					bool broken = false;
					if (on_game_thread() && !wait_satisfied(p, op == 0x93)) {
						for (int k = 0; k < 40 && !wait_satisfied(p, op == 0x93); k++) { // 2 ms for the ordinary case
							const uint64_t blocked = g_unready_label.load();
							if (blocked != 0 && std::find(written.begin(), written.end(), blocked) != written.end()) {
								std::lock_guard lk2(g_unready_mutex);
								if (std::find(g_unready_writes.begin(), g_unready_writes.end(), label) != g_unready_writes.end()) {
									broken = true;
									break;
								}
							}
							std::this_thread::sleep_for(std::chrono::microseconds(50));
						}
						if (broken) {
							static std::atomic<uint32_t> n_broken {0};
							if (n_broken++ < 50) journal("cycle broken: %s %u dwords waits at %u on 0x%" PRIx64 " for a queue that waits on 0x%" PRIx64 ", which this buffer writes; not waited for\n", kind, num_dwords, i, label, g_unready_label.load());
						}
					}
					if (!broken && (!g_dev || !g_dev->wedged())) {
						while (!(ok = wait_satisfied(p, op == 0x93))) {
							if (SoftCp::now_ns() - t0 >= limit) break;
							std::this_thread::sleep_for(std::chrono::microseconds(50));
						}
					}
					if (!ok && dry_here && on_game_thread() && i > start && (!g_dev || !g_dev->wedged())) {
						if ((start > 0 || prefix_all() || cs_used) && !full_prefix.empty()) submit_prefixed(full_prefix, ib + start, i - start);
						else submit_one(ib + start, i - start, kind);
						chain_flush(1); // ADR 0010
						full_prefix = prefix_of(*dry);
						const uint32_t head_from = start;
						start                    = i;
						full_used                = true;
						const uint64_t t1        = SoftCp::now_ns();
						while (!(ok = wait_satisfied(p, op == 0x93))) {
							if (SoftCp::now_ns() - t1 >= limit) break;
							std::this_thread::sleep_for(std::chrono::microseconds(50));
						}
						g_full_pieces++;
						(ok ? g_full_ok : g_full_failed)++;
						static std::atomic<uint32_t> n_logged {0};
						if (n_logged++ < 100) {
							journal("piece: %s %u..%u of %u dwords went ahead of the wait at %u on 0x%" PRIx64 "; the wait then %s after %.1f ms; rest behind a prefix of %zu dwords\n",
							        kind, head_from, i, num_dwords, i, label, ok ? "satisfied" : "not satisfied", static_cast<double>(SoftCp::now_ns() - t1) / 1e6,
							        full_prefix.size());
						}
					}
					if (!ok && op == 0x93 && len >= 8) {
						journal("  wait detail: function %u, value 0x%" PRIx64 ", reference 0x%" PRIx64 ", mask 0x%" PRIx64 "\n", p[1] & 7u,
						        *reinterpret_cast<const volatile uint64_t*>(label & ~7ull), p[4] | (static_cast<uint64_t>(p[5]) << 32u), p[6] | (static_cast<uint64_t>(p[7]) << 32u));
					}
					if (!ok) journal("cpu-wait %s at %u on 0x%" PRIx64 ": %s after %.1f ms\n", op == 0x93 ? "WAIT_REG_MEM64" : "WAIT_REG_MEM", i, label, broken ? "CYCLE" : (limit < 1'000'000'000ull ? "GIVEN UP" : "TIMEOUT"), static_cast<double>(SoftCp::now_ns() - t0) / 1e6);
					if (!ok) t_wait_given_up = true;
					if (dry_here) (ok ? g_dry_ok : g_dry_failed)++;
					frame_profile_wait(on_game_thread(), false, static_cast<double>(SoftCp::now_ns() - t0) / 1e6);
					static const bool timing_waits_env = BC5_DIAG_ENV("BC5_DIRECT_TIMING") != nullptr;
					const bool timing_waits = timing_waits_env && ::Log::Bc5LoggingOn();
					if (timing_waits) journal("timing: t %.3f s after that wait (%s %u dwords)\n", timing_now(), kind, num_dwords);
					SoftCp::set_gpu_executed(p, len, {0}); // the soft CP must not wait again
				}
			}
		}
		i += len;
	}
	if ((start > 0 || prefix_all() || cs_used) && full_used && !full_prefix.empty()) {
		submit_prefixed(full_prefix, ib + start, num_dwords - start);
		return;
	}
	if (start > 0) {
		uint32_t        n   = 0;
		const uint32_t* pre = state_prefix(ib, start, &n);
		static std::atomic<uint64_t> n_rest {0};
		if (journal_sample(n_rest, 0x3ffu)) journal("%s rest %u..%u of %u dwords: state prefix of %u dwords replayed first\n", kind, start, num_dwords, num_dwords, n);
		if (pre != nullptr) submit_one(pre, n, "dcb-state");
		submit_one(ib + start, num_dwords - start, kind);
		return;
	}
	submit_one(ib, num_dwords, kind);
}

// ADR 0008: the full register state of the graphics queue (bc5::full_state: every cc/hib/dcb
// buffer, LOAD_* tables and nested buffers read from memory), for the pieces' prefixes and the
// draw journal; a summary every 10 s. (Experiment 0073's offline check of every split,
// BC5_DIRECT_PIECE_CHECK, was removed in cleanup batch 5 once pieces ran on the GPU.)

// Experiment 0090: BC5_DIRECT_RT_DUMP=<t0>;<va hex>:<width>:<height>:<fmt>[;...] writes, once, at the
// first graphics buffer submitted from t0 s on, each listed colour target detiled on the CPU
// (KytyPlus's tile helpers: TileBlockFamily::RenderTarget64KB, 4 bytes per element, the address
// formula of tests/ShaderRecompilerComputeTests.cpp: block index * block size + (offset in block
// ^ block xor), pitch TileGetRenderTargetPitch) as a PPM image next to the journal. fmt: r11g11b10
// (packed float, R in bits 10:0 -- TODO(verify) the bit order), r32f, rgba8. Floats are shown
// tone-mapped (x / (1 + x)). CPU only; private output.
static float bc5_small_float(uint32_t bits, uint32_t mant_bits) {
	const uint32_t e = bits >> mant_bits, m = bits & ((1u << mant_bits) - 1u);
	if (e == 0) return std::ldexp(static_cast<float>(m), -14 - static_cast<int>(mant_bits));
	if (e == 31) return 65504.0f;
	return std::ldexp(1.0f + static_cast<float>(m) / static_cast<float>(1u << mant_bits), static_cast<int>(e) - 15);
}
// Experiment 0104: the base of the final pass's UI layer 0, as the draw journal last saw it.
static std::atomic<uint64_t> g_layer0_base {0};
// Experiment 0104: surfaces of the UI layer's size (0x1fe0000 bytes, 3840x2176 RGBA8) that the AMM maps
// automatically (libAmpr.cpp); BC5_DIRECT_DRAW_JOURNAL_WATCH=1 journals only the draws and dispatches
// that touch them.
static std::mutex            g_watch_mutex;
static std::vector<uint64_t> g_watch_surfaces;
extern "C" void              bc5_watch_surface(uint64_t va) {
	std::lock_guard lock(g_watch_mutex);
	if (g_watch_surfaces.size() < 64) g_watch_surfaces.push_back(va);
}

static void bc5_rt_dump_once(const std::shared_ptr<const std::vector<bc5::direct::Mapping>>& maps_p) {
	static const std::string spec = [] {
		const char* e = BC5_DIAG_ENV("BC5_DIRECT_RT_DUMP");
		return std::string(e != nullptr ? e : "");
	}();
	// Experiment 0156: BC5_DIRECT_RT_DUMP_EVERY=<s> repeats the dump every s seconds from t0 on, the
	// file names carrying the journal time (-t<seconds>), to catch a target at a broken and at a clean
	// moment in one run.
	static const double every = [] {
		const char* e = BC5_DIAG_ENV("BC5_DIRECT_RT_DUMP_EVERY");
		return e != nullptr ? std::strtod(e, nullptr) : 0.0;
	}();
	static std::atomic<bool> done {false};
	static std::mutex        every_mutex;
	static double            next_t = -1;
	if (spec.empty() || done.load()) return;
	const double t0    = std::strtod(spec.c_str(), nullptr);
	const double now_t = timing_now();
	if (now_t < t0) return;
	if (every > 0) {
		std::lock_guard lock(every_mutex);
		if (next_t < 0) next_t = t0;
		if (now_t < next_t) return;
		next_t = now_t + every;
	} else if (done.exchange(true)) {
		return;
	}
	const double dump_t = now_t;
	size_t pos = spec.find(';');
	while (pos != std::string::npos) {
		const size_t next = spec.find(';', pos + 1);
		const std::string item = spec.substr(pos + 1, next == std::string::npos ? std::string::npos : next - pos - 1);
		pos = next;
		uint64_t va = 0;
		unsigned w = 0, h = 0;
		char     fmt[48] = {};
		// Experiment 0104: "layer:<w>:<h>:<fmt>" dumps the UI layer 0 the draw journal last saw.
		if (item.rfind("layer:", 0) == 0) {
			va = g_layer0_base.load();
			if (va == 0 || std::sscanf(item.c_str() + 6, "%u:%u:%47s", &w, &h, fmt) != 3 || w == 0 || h == 0) continue;
		} else if (std::sscanf(item.c_str(), "%" SCNx64 ":%u:%u:%47s", &va, &w, &h, fmt) != 4 || w == 0 || h == 0) continue;
		// Experiment 0157: "<fmt>@<x>,<y>,<w>,<h>" detiles and writes only that window of the surface.
		uint32_t cx = 0, cy = 0, cw = w, ch = h;
		if (char* at = std::strchr(fmt, '@'); at != nullptr) {
			*at = 0;
			if (std::sscanf(at + 1, "%u,%u,%u,%u", &cx, &cy, &cw, &ch) != 4 || cw == 0 || ch == 0 || cx + cw > w || cy + ch > h) {
				cx = cy = 0;
				cw = w;
				ch = h;
			}
		}
		using namespace Libs::Graphics;
		// Experiment 0095: a "-lin" suffix reads the surface linearly (pitch = width), as a display
		// buffer registered with tiling_mode 0.
		bool linear = false;
		if (char* l = std::strstr(fmt, "-lin"); l != nullptr) {
			*l     = 0;
			linear = true;
		}
		// Experiment 0098: "-fam<n>" picks the KytyPlus TileBlockFamily (0 Standard256B, 1 Standard4KB,
		// 3 Standard64KB, 7 RenderTarget64KB, ...); default RenderTarget64KB.
		uint32_t family = 7;
		if (char* fm = std::strstr(fmt, "-fam"); fm != nullptr) {
			family = static_cast<uint32_t>(std::strtoul(fm + 4, nullptr, 10));
			*fm    = 0;
		}
		// Experiment 0156: r8 (one byte, UNORM) and r16f (two bytes, half float) for the title's glyph atlases.
		const uint32_t  bpe = std::strcmp(fmt, "rgba16f") == 0 ? 8u : std::strcmp(fmt, "r8") == 0 ? 1u : std::strcmp(fmt, "r16f") == 0 ? 2u : 4u; // experiment 0091
		TileBlockLayout block {};
		if (!TileGetBlockLayout(static_cast<TileBlockFamily>(family), bpe, block)) continue;
		const uint32_t pitch   = TileGetRenderTargetPitch(w, bpe);
		const uint64_t columns = (pitch + block.block_width - 1u) / block.block_width;
		const uint64_t rows    = (h + block.block_height - 1u) / block.block_height;
		const uint64_t bytes   = linear ? static_cast<uint64_t>(w) * h * bpe : columns * rows * block.block_size;
		// Experiment 0100: a range the direct path does not list (AMM mappings, F88) is still read if
		// every page of it is mapped in this process (mincore), as the title's CPU sees it.
		bool host_mapped = true;
		{
			const uint64_t page = 4096, first = va & ~(page - 1), last = (va + bytes + page - 1) & ~(page - 1);
			std::vector<unsigned char> vec((last - first) / page);
			host_mapped = ::mincore(reinterpret_cast<void*>(first), last - first, vec.data()) == 0;
		}
		// Experiment 0100: inside the AMM window (0x8000000000, 64 GiB) reserved pages count as
		// mapped for mincore but abort the title when touched; report which parts the guest has
		// mapped there instead of reading.
		if (va >= 0x8000000000ull && va < 0x9000000000ull) {
			struct Cover {
				uint64_t lo, hi, covered = 0;
				std::string names;
			} cv {va, va + bytes};
			Libs::LibKernel::Memory::Bc5ForEachMappedRange(nullptr, &cv, [](uint64_t start, uint64_t size, uint64_t, int type, int, const char* name, void* p) {
				auto*          c = static_cast<Cover*>(p);
				const uint64_t a = std::max(start, c->lo), b = std::min(start + size, c->hi);
				if (a >= b) return;
				c->covered += b - a;
				char buf[96];
				std::snprintf(buf, sizeof(buf), " [%010" PRIx64 "+%" PRIx64 " t%d %s]", a, b - a, type, name != nullptr ? name : "");
				if (c->names.size() < 600) c->names += buf;
			});
			journal("rt dump %010" PRIx64 " %ux%u: AMM window, guest-mapped %" PRIu64 " of %" PRIu64 " bytes, for the GPU %s:%s\n", va, w, h, cv.covered, bytes,
			        covered_sorted(*maps_p, va, bytes) ? "all" : "not all", cv.names.c_str());
			if (cv.covered < bytes) continue; // experiment 0104: read only a fully mapped surface
		}
		if (!covered_sorted(*maps_p, va, bytes) && !host_mapped) {
			journal("rt dump %010" PRIx64 " %ux%u: not mapped for the GPU nor in this process (%" PRIu64 " bytes)\n", va, w, h, bytes);
			continue;
		}
		const auto*          src = reinterpret_cast<const uint8_t*>(va);
		std::vector<uint8_t> rgb(static_cast<size_t>(w) * h * 3u);
		uint64_t             nonzero = 0;
		double               sum_v = 0, max_v = 0; // raw values before tone mapping (mean of channels)
		uint64_t             alpha_hist[4] = {};  // experiment 0099: 2-bit alpha of rgb10a2
		std::vector<uint8_t> alpha8;              // experiment 0104: rgba8 alpha (0 / 1-127 / 128-254 / 255 in alpha_hist)
		if (std::strcmp(fmt, "rgba8") == 0) alpha8.assign(static_cast<size_t>(w) * h, 0);
		for (uint32_t y = cy; y < cy + ch; y++) {
			for (uint32_t x = cx; x < cx + cw; x++) {
				uint32_t local = 0, bxor = 0;
				uint64_t off   = (static_cast<uint64_t>(y) * w + x) * bpe;
				if (!linear) {
					if (!TileGetBlockOffset(block, x % block.block_width, y % block.block_height, 0, local) ||
					    !TileGetBlockXor(block, x / block.block_width, y / block.block_height, bxor))
						continue;
					off = ((y / block.block_height) * columns + x / block.block_width) * block.block_size + (local ^ bxor);
				}
				uint32_t       v   = 0;
				std::memcpy(&v, src + off, bpe < 4 ? bpe : 4);
				uint32_t v2 = 0;
				if (bpe == 8) std::memcpy(&v2, src + off + 4, 4);
				if (v != 0 || v2 != 0) nonzero++;
				float r = 0, g = 0, b = 0;
				if (bpe == 8) {
					auto half = [](uint32_t hb) {
						const uint32_t sgn = hb >> 15u, e = (hb >> 10u) & 0x1fu, m = hb & 0x3ffu;
						float f = e == 0 ? std::ldexp(static_cast<float>(m), -24) : e == 31 ? 65504.0f : std::ldexp(1.0f + static_cast<float>(m) / 1024.0f, static_cast<int>(e) - 15);
						return sgn ? -f : f;
					};
					r = half(v & 0xffffu), g = half(v >> 16u), b = half(v2 & 0xffffu);
					const double mm = (std::fabs(static_cast<double>(r)) + std::fabs(g) + std::fabs(b)) / 3.0;
					sum_v += mm;
					max_v = std::max(max_v, mm);
					r = std::fabs(r), g = std::fabs(g), b = std::fabs(b);
					r /= 1.0f + r, g /= 1.0f + g, b /= 1.0f + b;
				} else if (std::strcmp(fmt, "rgb10a2") == 0) { // KytyPlus gpu_defs.h k10_10_10_2UNorm = 50
					alpha_hist[v >> 30u]++;
					r = static_cast<float>(v & 0x3ffu) / 1023.0f, g = static_cast<float>((v >> 10u) & 0x3ffu) / 1023.0f, b = static_cast<float>((v >> 20u) & 0x3ffu) / 1023.0f;
					const double mm = (static_cast<double>(r) + g + b) / 3.0;
					sum_v += mm;
					max_v = std::max(max_v, mm);
				} else if (std::strcmp(fmt, "rgba8") == 0) {
					r = static_cast<float>(v & 0xffu) / 255.0f, g = static_cast<float>((v >> 8u) & 0xffu) / 255.0f, b = static_cast<float>((v >> 16u) & 0xffu) / 255.0f;
					const uint32_t a8 = v >> 24u;
					alpha_hist[a8 == 0 ? 0 : a8 == 255 ? 3 : a8 < 128 ? 1 : 2]++;
					alpha8[static_cast<size_t>(y) * w + x] = static_cast<uint8_t>(a8);
				} else if (bpe == 1) {
					r = g = b = static_cast<float>(v & 0xffu) / 255.0f;
					sum_v += r;
					max_v = std::max(max_v, static_cast<double>(r));
				} else if (bpe == 2) {
					const uint32_t e = (v >> 10u) & 0x1fu, m = v & 0x3ffu;
					float          f = e == 0 ? std::ldexp(static_cast<float>(m), -24) : e == 31 ? 65504.0f : std::ldexp(1.0f + static_cast<float>(m) / 1024.0f, static_cast<int>(e) - 15);
					if ((v >> 15u) & 1u) f = -f;
					sum_v += f;
					max_v = std::max(max_v, static_cast<double>(f));
					r = g = b = std::fabs(f) / (1.0f + std::fabs(f));
				} else if (std::strcmp(fmt, "r32f") == 0) {
					float f = 0;
					std::memcpy(&f, &v, 4);
					if (std::isfinite(f)) {
						sum_v += f;
						max_v = std::max(max_v, static_cast<double>(f));
					}
					r = g = b = std::isfinite(f) ? std::fabs(f) / (1.0f + std::fabs(f)) : 1.0f;
				} else {
					r = bc5_small_float(v & 0x7ffu, 6), g = bc5_small_float((v >> 11u) & 0x7ffu, 6), b = bc5_small_float((v >> 22u) & 0x3ffu, 5);
					const double m = (static_cast<double>(r) + g + b) / 3.0;
					sum_v += m;
					max_v = std::max(max_v, m);
					r /= 1.0f + r, g /= 1.0f + g, b /= 1.0f + b;
				}
				uint8_t* o = &rgb[(static_cast<size_t>(y) * w + x) * 3u];
				o[0]       = static_cast<uint8_t>(std::clamp(r, 0.0f, 1.0f) * 255.0f);
				o[1]       = static_cast<uint8_t>(std::clamp(g, 0.0f, 1.0f) * 255.0f);
				o[2]       = static_cast<uint8_t>(std::clamp(b, 0.0f, 1.0f) * 255.0f);
			}
		}
		char name[512];
		if (every > 0)
			std::snprintf(name, sizeof(name), "%s/rt-%010" PRIx64 "-%ux%u-%s-f%u-t%07.2f.ppm", g_dump_dir.c_str(), va, w, h, fmt, family, dump_t);
		else
			std::snprintf(name, sizeof(name), "%s/rt-%010" PRIx64 "-%ux%u-%s-f%u.ppm", g_dump_dir.c_str(), va, w, h, fmt, family);
		if (FILE* f = std::fopen(name, "wb"); f != nullptr) {
			std::fprintf(f, "P6" "\n" "%u %u" "\n" "255" "\n", cw, ch);
			for (uint32_t y = cy; y < cy + ch; y++) std::fwrite(&rgb[(static_cast<size_t>(y) * w + cx) * 3u], 1, static_cast<size_t>(cw) * 3u, f);
			std::fclose(f);
		}
		if (!alpha8.empty()) { // experiment 0104: the alpha channel as a grey image
			char an[540];
			std::snprintf(an, sizeof(an), "%s-alpha.pgm", name);
			if (FILE* f = std::fopen(an, "wb"); f != nullptr) {
				std::fprintf(f, "P5" "\n" "%u %u" "\n" "255" "\n", cw, ch);
				for (uint32_t y = cy; y < cy + ch; y++) std::fwrite(&alpha8[static_cast<size_t>(y) * w + cx], 1, cw, f);
				std::fclose(f);
			}
		}
		journal("rt dump %010" PRIx64 " %ux%u %s: %" PRIu64 " of %u pixels non-zero, raw mean %.6g max %.6g, 2-bit alpha 0/1/2/3: %" PRIu64 "/%" PRIu64 "/%" PRIu64 "/%" PRIu64 " -> %s\n", va, w, h, fmt, nonzero, w * h, sum_v / (static_cast<double>(w) * h), max_v,
		        alpha_hist[0], alpha_hist[1], alpha_hist[2], alpha_hist[3], name);
	}
}

// Experiment 0157: memory a journaled draw reads, remembered at submission (bc5_range_remember) and
// compared at the buffer's fence completion (bc5_ranges_complete, completion_thread): a range the
// title rewrote while the buffer was in flight is journaled with the draw it belonged to.
struct Bc5ReadRange {
	const void*          ib;
	uint32_t             buf, off;
	const char*          kind;
	uint64_t             addr;
	double               t;
	std::vector<uint8_t> copy;
};
static std::vector<Bc5ReadRange> g_read_ranges;
static std::mutex                g_read_ranges_mutex;
// Experiment 0157: the buffer piece_check is working on matched the draw journal's filters (a UI redraw):
// submit_one dumps it when BC5_DIRECT_IB_DUMP has 0:0 as its size range.
static thread_local bool     t_ui_buffer = false;
static thread_local uint32_t t_ui_buf_no = 0;
static void bc5_range_remember(const void* ib, uint32_t buf, uint32_t off, const char* kind, uint64_t addr, size_t len) {
	std::lock_guard lock(g_read_ranges_mutex);
	if (g_read_ranges.size() >= 65536) return;
	for (const Bc5ReadRange& r: g_read_ranges)
		if (r.ib == ib && r.addr == addr && r.copy.size() == len) return;
	Bc5ReadRange r {ib, buf, off, kind, addr, timing_now(), {}};
	r.copy.assign(reinterpret_cast<const uint8_t*>(addr), reinterpret_cast<const uint8_t*>(addr) + len);
	g_read_ranges.push_back(std::move(r));
}
static void bc5_ranges_complete(const void* ib, uint64_t n, const std::shared_ptr<const std::vector<bc5::direct::Mapping>>& maps_p) {
	std::vector<Bc5ReadRange> mine;
	{
		std::lock_guard lock(g_read_ranges_mutex);
		for (auto it = g_read_ranges.begin(); it != g_read_ranges.end();) {
			if (it->ib == ib) {
				mine.push_back(std::move(*it));
				it = g_read_ranges.erase(it);
			} else {
				++it;
			}
		}
	}
	if (mine.empty()) return;
	const double now     = timing_now();
	size_t       intact  = 0, rewritten = 0, unreadable = 0;
	for (const Bc5ReadRange& r: mine) {
		if (!covered_sorted(*maps_p, r.addr, r.copy.size())) {
			unreadable++;
			continue;
		}
		const auto* m = reinterpret_cast<const uint8_t*>(r.addr);
		if (std::memcmp(m, r.copy.data(), r.copy.size()) == 0) {
			intact++;
			continue;
		}
		rewritten++;
		size_t first = 0, count = 0;
		while (first < r.copy.size() && m[first] == r.copy[first]) first++;
		for (size_t q = 0; q < r.copy.size(); q++) count += m[q] != r.copy[q];
		journal("range rewritten in flight: submit #%" PRIu64 " buf %u at %u %s %010" PRIx64 "+%zx: %zu bytes differ from %zx; submitted t %.3f, completed t %.3f (%.1f ms)\n", n, r.buf, r.off, r.kind, r.addr,
		        r.copy.size(), count, first, r.t, now, (now - r.t) * 1000.0);
	}
	journal("ranges at completion: submit #%" PRIu64 " buf %u: %zu intact, %zu rewritten, %zu unreadable; %.1f ms from the first draw's journal to completion\n", n, mine.front().buf, intact, rewritten,
	        unreadable, (now - mine.front().t) * 1000.0);
}

static void piece_check(const uint32_t* ib, uint32_t num_dwords, const char* kind) {
	t_ui_buffer = false;
	// Experiment 0089: BC5_DIRECT_DRAW_JOURNAL=<t0>:<buffers> journals every draw and dispatch of the
	// graphics buffers submitted from t0 s on (that many buffers): colour target 0 (base, size,
	// INFO), CB_TARGET_MASK, viewport, PS and VS/ES/GS programs, the packet's dwords. Registers:
	// Mesa gfx10 register JSON (tools/bc5-agc/regdb): CB_COLOR0_BASE ctx 0x318, _BASE_EXT 0x390,
	// _INFO 0x31c, _ATTRIB2 0x3b0 (MIP0_HEIGHT 13:0, MIP0_WIDTH 27:14, TODO(verify)), CB_TARGET_MASK
	// 0x8e, PA_CL_VPORT_XSCALE..YOFFSET 0x10f-0x112, SPI_SHADER_PGM_LO/HI_PS sh 0x8/0x9, _LO_ES 0xc8,
	// _LO_GS 0x88, COMPUTE_PGM_LO sh 0x20c.
	// Experiment 0156: two optional filters, <t0>:<buffers>[:<min dwords>[:<max rt px>]]: buffers below
	// <min dwords> are skipped (run 668 caught only small compute-only buffers), and with <max rt px>
	// only draws whose colour target 0 is at most that wide and high are journaled (the text bakes
	// into small atlas targets, F202), each with its scissors, colour attributes, the PS and GS user
	// data and the first 32 dwords of every table they point at; a buffer with no such draw does not
	// count. Lines then carry the journal time and the wall clock, for matching screenshots.
	static const std::pair<double, uint32_t> draw_journal = [] {
		std::pair<double, uint32_t> v {0, 0};
		if (const char* e = BC5_DIAG_ENV("BC5_DIRECT_DRAW_JOURNAL"); e != nullptr) {
			char* end = nullptr;
			v.first   = std::strtod(e, &end);
			if (end != nullptr && *end == ':') v.second = static_cast<uint32_t>(std::strtoul(end + 1, nullptr, 10));
		}
		return v;
	}();
	static const std::pair<uint32_t, uint32_t> draw_journal_filter = [] {
		std::pair<uint32_t, uint32_t> v {0, 0};
		if (const char* e = BC5_DIAG_ENV("BC5_DIRECT_DRAW_JOURNAL"); e != nullptr) {
			const char* c = std::strchr(e, ':');
			if (c != nullptr) c = std::strchr(c + 1, ':');
			if (c != nullptr) {
				char* end = nullptr;
				v.first   = static_cast<uint32_t>(std::strtoul(c + 1, &end, 10));
				if (end != nullptr && *end == ':') v.second = static_cast<uint32_t>(std::strtoul(end + 1, nullptr, 10));
			}
		}
		return v;
	}();
	static const bool rt_dump = BC5_DIAG_ENV("BC5_DIRECT_RT_DUMP") != nullptr;
	if (rt_dump && std::strcmp(kind, "dcb") == 0 && g_dev) bc5_rt_dump_once(g_dev->sorted_mappings());
	// Experiment 0157: BC5_DIRECT_DRAW_JOURNAL_ACB=1 takes the compute-queue buffers through the journal too
	// (as "dcb" below; their packets set SH registers only, so the shared tracker is not disturbed).
	static const bool journal_acb_env = BC5_DIAG_ENV("BC5_DIRECT_DRAW_JOURNAL_ACB") != nullptr;
	const bool journal_acb = journal_acb_env && ::Log::Bc5LoggingOn();
	const bool        acb_as_dcb  = journal_acb && draw_journal.second != 0 && std::strcmp(kind, "acb") == 0;
	if (acb_as_dcb) kind = "dcb";
	if (std::strcmp(kind, "cc") != 0 && std::strcmp(kind, "hib") != 0 && std::strcmp(kind, "dcb") != 0) return;
	static std::mutex                 mtx;
	static bc5::full_state::Tracker   tracker;
	static bc5::full_state::Stats     st;
	static uint64_t                   bufs = 0, with_waits = 0;
	static double                     ms = 0, last_report = 0;
	std::lock_guard<std::mutex>       lock(mtx);
	const double                      t0     = timing_now();
	std::shared_ptr<const std::vector<bc5::direct::Mapping>> maps_p = g_dev->sorted_mappings();
	const bc5::full_state::Tracker::Reader read = [&maps_p](uint64_t a, uint64_t bytes) -> const uint32_t* {
		return covered_sorted(*maps_p, a, bytes) ? reinterpret_cast<const uint32_t*>(a) : nullptr;
	};
	const std::span<const uint32_t> span(ib, num_dwords);
	bufs++;
	if (std::strcmp(kind, "dcb") == 0) {
		std::vector<size_t> waits;
		for (uint32_t i = 0; i < num_dwords;) {
			const uint32_t h = ib[i], type = h >> 30u;
			uint32_t len = 1;
			if (type == 3 || type == 0) { const uint32_t c = (h >> 16u) & 0x3fffu; len = c == 0x3fffu ? 1 : c + 2; }
			if (i + len > num_dwords) break;
			const uint32_t op = (h >> 8u) & 0xffu;
			if (type == 3 && (op == 0x3c || op == 0x93) && len >= 4 && ((ib[i + 1] >> 4u) & 1u) != 0) waits.push_back(i);
			i += len;
		}
		t_fs_valid = !waits.empty();
		static uint32_t journaled = 0;
		if (draw_journal.second != 0 && journaled < draw_journal.second && timing_now() >= draw_journal.first && num_dwords >= draw_journal_filter.first) {
			const uint32_t buf_no  = journaled;
			bool           counted = draw_journal_filter.second == 0;
			if (counted) journaled++;
			// Experiment 0157: INDEX_BASE (0x26: lo, hi) and INDEX_TYPE (0x2a) by offset, for the vertex lines.
			struct IdxState {
				size_t   off;
				uint64_t base;
				uint32_t type;
			};
			std::vector<IdxState> idx_states;
			{
				uint64_t ib_base = 0;
				uint32_t ib_type = 0;
				for (uint32_t i = 0; i < num_dwords;) {
					const uint32_t h = ib[i], type = h >> 30u;
					uint32_t       len = 1;
					if (type == 3 || type == 0) { const uint32_t c = (h >> 16u) & 0x3fffu; len = c == 0x3fffu ? 1 : c + 2; }
					if (i + len > num_dwords) break;
					if (type == 3) {
						const uint32_t op = (h >> 8u) & 0xffu;
						if (op == 0x26 && len >= 3) { ib_base = ib[i + 1] | (static_cast<uint64_t>(ib[i + 2] & 0xffffu) << 32u); idx_states.push_back({i, ib_base, ib_type}); }
						if (op == 0x2a && len >= 2) { ib_type = ib[i + 1] & 3u; idx_states.push_back({i, ib_base, ib_type}); }
					}
					i += len;
				}
			}
			// (the per-frame re-check of the vertex ranges became bc5_ranges_complete, at fence completion)
			bc5::full_state::for_each_draw(tracker, span, read, [&](size_t off, std::span<const uint32_t> pkt, const bc5::full_state::Tracker& t) {
				auto reg = [&t](bc5::full_state::Space sp, uint32_t o) {
					uint32_t v = 0;
					return t.get(sp, o, v) ? v : 0u;
				};
				// Experiment 0156: the small-target filter (draws only; CB_COLOR0_ATTRIB2 as below).
				// A draw or dispatch the filters reject is still shown to BC5_DIRECT_DRAW_JOURNAL_FIND below.
				const bool filters_on = draw_journal_filter.second != 0;
				const bool matched    = [&]() -> bool {
					if (!filters_on) return true;
					const uint32_t op2 = (pkt[0] >> 8u) & 0xffu;
					if (op2 == 0x15 || op2 == 0x16) return false;
					if (draw_journal_filter.second != 0) {
						const uint32_t a2 = reg(bc5::full_state::Context, 0x3b0);
						if (((a2 >> 14u) & 0x3fffu) + 1u > draw_journal_filter.second || (a2 & 0x3fffu) + 1u > draw_journal_filter.second) return false;
					}
					return true;
				}();
				static const bool find_set_env = BC5_DIAG_ENV("BC5_DIRECT_DRAW_JOURNAL_FIND") != nullptr; // "layer" counts too
				const bool find_set = find_set_env && ::Log::Bc5LoggingOn();
				if (!matched && !find_set) return;
				if (matched && !counted) {
					counted     = true;
					journaled++;
					t_ui_buffer = true;
					t_ui_buf_no = buf_no;
					// Experiment 0157: the register tables this buffer loads (LOAD_CONTEXT/SH/UCONFIG_REG 0x61/0x5f/
					// 0x5e: base lo/hi, then (offset, count) pairs; the _INDEX forms 0x9f/0x63/0x64: base, dword 3
					// bit 31 = pairs of (offset, value), dword 4 = count; as bc5::full_state::Tracker::apply reads
					// them) join the completion-time check.
					for (uint32_t i = 0; i < num_dwords;) {
						const uint32_t h = ib[i], type = h >> 30u;
						uint32_t       len = 1;
						if (type == 3 || type == 0) { const uint32_t c = (h >> 16u) & 0x3fffu; len = c == 0x3fffu ? 1 : c + 2; }
						if (i + len > num_dwords) break;
						if (type == 3 && len >= 5) {
							const uint32_t lop  = (h >> 8u) & 0xffu;
							const uint64_t base = (static_cast<uint64_t>(ib[i + 1]) & ~3ull) | (static_cast<uint64_t>(ib[i + 2] & 0xffffu) << 32u);
							if (lop == 0x61 || lop == 0x5f || lop == 0x5e) {
								for (uint32_t k = 3; k + 1 < len; k += 2) {
									const uint32_t n = ib[i + k + 1] & 0x3fffu;
									const uint64_t a = base + static_cast<uint64_t>(ib[i + k] & 0xffffu) * 4u;
									if (n != 0 && n <= 1024 && read(a, n * 4ull) != nullptr) bc5_range_remember(ib, buf_no, i, "reg table", a, n * 4ull);
								}
							} else if (lop == 0x9f || lop == 0x63 || lop == 0x64) {
								const bool     pairs = (ib[i + 3] >> 31u) != 0;
								const uint32_t n     = ib[i + 4] & 0x3fffu;
								const uint64_t bytes = static_cast<uint64_t>(n) * (pairs ? 8u : 4u);
								if (n != 0 && n <= 1024 && read(base, bytes) != nullptr) {
									bc5_range_remember(ib, buf_no, i, "reg table", base, bytes);
									// Experiment 0157: the table's pairs (offset:value), up to 64; dword 1 and 3 of the packet too.
									const auto* tv = reinterpret_cast<const uint32_t*>(base);
									char        pb[1400] = {};
									int         pw       = 0;
									if (pairs)
										for (uint32_t q = 0; q < n && q < 64 && pw < 1300; q++) pw += std::snprintf(pb + pw, sizeof(pb) - static_cast<size_t>(pw), " %x:%08x", tv[2 * q] & 0xffffu, tv[2 * q + 1]);
									journal("load table buf %u at %u: op %02x dw1 %08x dw3 %08x %s x%u at %010" PRIx64 ":%s%s\n", buf_no, i, lop, ib[i + 1], ib[i + 3], pairs ? "pairs" : "span", n, base, pb,
									        n > 64 ? " ..." : "");
								}
							}
						}
						i += len;
					}
				}
				auto flt = [&](uint32_t o) {
					const uint32_t b = reg(bc5::full_state::Context, o);
					float f = 0;
					std::memcpy(&f, &b, 4);
					return static_cast<double>(f);
				};
				using S                = bc5::full_state::Space;
				const uint64_t rt      = (static_cast<uint64_t>(reg(S::Context, 0x318)) | (static_cast<uint64_t>(reg(S::Context, 0x390) & 0xffu) << 32u)) << 8u;
				const uint32_t attrib2 = reg(S::Context, 0x3b0);
				const uint64_t ps      = (static_cast<uint64_t>(reg(S::Sh, 0x8)) | (static_cast<uint64_t>(reg(S::Sh, 0x9) & 0xffu) << 32u)) << 8u;
				const uint64_t es      = static_cast<uint64_t>(reg(S::Sh, 0xc8)) << 8u;
				const uint64_t gs      = static_cast<uint64_t>(reg(S::Sh, 0x88)) << 8u;
				const uint64_t cs      = static_cast<uint64_t>(reg(S::Sh, 0x20c)) << 8u;
				const double   xs = flt(0x10f), xo = flt(0x110), ys = flt(0x111), yo = flt(0x112);
				char           words[96] = {};
				int            w         = 0;
				for (size_t k = 0; k < pkt.size() && k < 6 && w < 80; k++) w += std::snprintf(words + w, sizeof(words) - static_cast<size_t>(w), " %08x", pkt[k]);
				static const bool watch_quiet_env = BC5_DIAG_ENV("BC5_DIRECT_DRAW_JOURNAL_WATCH") != nullptr;
				const bool watch_quiet = watch_quiet_env && ::Log::Bc5LoggingOn();
				if (!watch_quiet && matched) journal("draw journal buf %u (%u dwords) at %zu:%s | rt0 %010" PRIx64 " %ux%u info %08x mask %08x | vp %.0fx%.0f at %.0f,%.0f | ps %010" PRIx64
				                " es %010" PRIx64 " gs %010" PRIx64 " cs %010" PRIx64 "\n",
				                buf_no, num_dwords, off, words, rt, ((attrib2 >> 14u) & 0x3fffu) + 1u, (attrib2 & 0x3fffu) + 1u, reg(S::Context, 0x31c), reg(S::Context, 0x8e),
				                2 * xs, 2 * ys, xo - xs, yo - ys, ps, es, gs, cs);
				// Experiment 0156: for a small-target draw, the time, the window and generic scissors
				// (PA_SC_WINDOW_SCISSOR_TL/BR ctx 0x81/0x82, PA_SC_GENERIC_SCISSOR_TL/BR 0x90/0x91: X 15:0,
				// Y 31:16), CB_COLOR0_VIEW 0x31b, _ATTRIB 0x31d, _ATTRIB3 0x3b8, CB_BLEND0_CONTROL 0x1e0,
				// CB_COLOR_CONTROL 0x202, SPI_SHADER_COL_FORMAT 0x1c5, the PS user data (sh 0x0c..0x2b) and
				// the GS user data (SPI_SHADER_USER_DATA_GS_0 sh 0x8c..0xab), and the first 32 dwords of each
				// readable table a user-data pair points at (tools/bc5-agc/regdb/gfx10.json).
				if (filters_on && matched) {
					const auto     wall = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::system_clock::now().time_since_epoch()).count();
					const uint32_t wtl = reg(S::Context, 0x81), wbr = reg(S::Context, 0x82), gtl = reg(S::Context, 0x90), gbr = reg(S::Context, 0x91);
					journal("bake draw buf %u at %zu: t %.3f wall %lld.%03lld | win %u,%u-%u,%u gen %u,%u-%u,%u | view %08x attrib %08x attrib3 %08x blend0 %08x cc %08x colfmt %08x\n", buf_no, off,
					        timing_now(), static_cast<long long>(wall / 1000), static_cast<long long>(wall % 1000), wtl & 0x7fffu, (wtl >> 16u) & 0x7fffu, wbr & 0x7fffu, (wbr >> 16u) & 0x7fffu,
					        gtl & 0x7fffu, (gtl >> 16u) & 0x7fffu, gbr & 0x7fffu, (gbr >> 16u) & 0x7fffu, reg(S::Context, 0x31b), reg(S::Context, 0x31d), reg(S::Context, 0x3b8),
					        reg(S::Context, 0x1e0), reg(S::Context, 0x202), reg(S::Context, 0x1c5));
					for (int stage = 0; stage < 2; stage++) {
						const uint32_t ubase = stage == 0 ? 0x0cu : 0x8cu;
						uint32_t       ud[32];
						char           u[320] = {};
						int            uw     = 0;
						for (uint32_t k = 0; k < 32; k++) {
							ud[k] = reg(S::Sh, ubase + k);
							uw += std::snprintf(u + uw, sizeof(u) - static_cast<size_t>(uw), " %08x", ud[k]);
						}
						journal("bake ud %s buf %u at %zu:%s\n", stage == 0 ? "ps" : "gs", buf_no, off, u);
						std::vector<uint64_t> seen;
						for (uint32_t k = 0; k + 1 < 32; k++) {
							const uint64_t addr = ud[k] | (static_cast<uint64_t>(ud[k + 1] & 0xffffu) << 32u);
							const bool guest_range = (addr >= 0x1000000000ull && addr < 0x1400000000ull) || (addr >= 0x8000000000ull && addr < 0x9000000000ull);
							if (!guest_range || (addr & 3u) != 0 || read(addr, 256) == nullptr) continue;
							if (std::find(seen.begin(), seen.end(), addr) != seen.end()) continue;
							seen.push_back(addr);
							const auto* m = reinterpret_cast<const uint32_t*>(addr);
							char        tb[640] = {};
							int         tw      = 0;
							for (uint32_t q = 0; q < 64; q++) tw += std::snprintf(tb + tw, sizeof(tb) - static_cast<size_t>(tw), " %08x", m[q]);
							journal("bake table %s ud%u %010" PRIx64 ":%s\n", stage == 0 ? "ps" : "gs", k, addr, tb);
							bc5_range_remember(ib, buf_no, static_cast<uint32_t>(off), stage == 0 ? "ps table" : "gs table", addr, 256);
							// the paint V# at PS table 28 + 0x20 (experiment 0104): its first 128 bytes
							if (stage == 0 && k == 28) {
								const uint64_t pv = m[8] | (static_cast<uint64_t>(m[9] & 0xffffu) << 32u);
								if (pv != 0 && read(pv, 128) != nullptr) bc5_range_remember(ib, buf_no, static_cast<uint32_t>(off), "paint", pv, 128);
							}
						}
					}
					// Experiment 0157: the vertices of a DRAW_INDEX_OFFSET_2 (0x35: max_size, index_offset, count;
					// Mesa sid.h) through the first V# (base dword 0 | dword 1 bits 15:0 << 32, stride dword 1 bits
					// 29:16) of the table GS user data 4-5 point at, and the index buffer set before the draw.
					if (((pkt[0] >> 8u) & 0xffu) == 0x35 && pkt.size() >= 4) {
						uint64_t ib_base = 0;
						uint32_t ib_type = 0;
						for (const IdxState& st: idx_states) {
							if (st.off >= off) break;
							ib_base = st.base;
							ib_type = st.type;
						}
						const uint64_t gtab = reg(S::Sh, 0x8c + 4) | (static_cast<uint64_t>(reg(S::Sh, 0x8c + 5) & 0xffffu) << 32u);
						const uint32_t* tv  = gtab != 0 ? read(gtab, 16) : nullptr;
						const uint64_t  vb  = tv != nullptr ? (tv[0] | (static_cast<uint64_t>(tv[1] & 0xffffu) << 32u)) : 0;
						const uint32_t  vst = tv != nullptr ? (tv[1] >> 16u) & 0x3fffu : 0;
						const uint32_t  isz = ib_type == 0 ? 2u : 4u, cnt = pkt[3];
						const uint64_t  ia  = ib_base + static_cast<uint64_t>(pkt[2]) * isz;
						if (ib_base != 0 && vb != 0 && vst != 0 && cnt != 0 && cnt <= 65536 && read(ia, static_cast<uint64_t>(cnt) * isz) != nullptr) {
							uint32_t imin = 0xffffffffu, imax = 0;
							for (uint32_t q = 0; q < cnt; q++) {
								const uint32_t idx = isz == 2 ? reinterpret_cast<const uint16_t*>(ia)[q] : reinterpret_cast<const uint32_t*>(ia)[q];
								imin = std::min(imin, idx), imax = std::max(imax, idx);
							}
							const uint64_t va0 = vb + static_cast<uint64_t>(imin) * vst, vlen = static_cast<uint64_t>(imax - imin + 1) * vst;
							if (vlen <= 0x100000 && read(va0, vlen) != nullptr) {
								float    xmin = 1e30f, xmax = -1e30f, ymin = 1e30f, ymax = -1e30f;
								uint32_t v0[8] = {};
								std::memcpy(v0, reinterpret_cast<const void*>(va0), std::min<size_t>(32, vst));
								for (uint32_t q = 0; q < cnt; q++) {
									const uint32_t idx = isz == 2 ? reinterpret_cast<const uint16_t*>(ia)[q] : reinterpret_cast<const uint32_t*>(ia)[q];
									float          xy[2];
									std::memcpy(xy, reinterpret_cast<const void*>(vb + static_cast<uint64_t>(idx) * vst), 8);
									xmin = std::min(xmin, xy[0]), xmax = std::max(xmax, xy[0]), ymin = std::min(ymin, xy[1]), ymax = std::max(ymax, xy[1]);
								}
								journal("bake vertices buf %u at %zu: idx %010" PRIx64 " +%u x%u (%u-bit) -> %u..%u | vb %010" PRIx64 " stride %u | box %.1f,%.1f-%.1f,%.1f | v0 %08x %08x %08x %08x %08x %08x %08x %08x\n", buf_no, off, ib_base,
								        pkt[2], cnt, isz * 8, imin, imax, vb, vst, static_cast<double>(xmin), static_cast<double>(ymin), static_cast<double>(xmax), static_cast<double>(ymax), v0[0], v0[1], v0[2], v0[3], v0[4], v0[5], v0[6], v0[7]);
								bc5_range_remember(ib, buf_no, static_cast<uint32_t>(off), "vertices", va0, vlen);
								bc5_range_remember(ib, buf_no, static_cast<uint32_t>(off), "indices", ia, static_cast<size_t>(cnt) * isz);
							}
						} else {
							journal("bake vertices buf %u at %zu: idx %010" PRIx64 " +%u x%u | vb %010" PRIx64 " stride %u: unreadable\n", buf_no, off, ib_base, pkt[2], cnt, vb, vst);
						}
					}
				}
				// Experiment 0093: for a draw, the bases of every colour target CB_TARGET_MASK enables
				// (CB_COLORn_BASE ctx 0x318 + n * 0xf, CB_COLORn_BASE_EXT 0x390 + n; Mesa gfx10 register JSON).
				if (((pkt[0] >> 8u) & 0xffu) != 0x15 && ((pkt[0] >> 8u) & 0xffu) != 0x16) {
					const uint32_t mask = reg(S::Context, 0x8e);
					char           mrt[256] = {};
					int            mw       = 0;
					for (uint32_t n = 0; n < 8 && mw < 220; n++) {
						if (((mask >> (4u * n)) & 0xfu) == 0) continue;
						const uint64_t bn = (static_cast<uint64_t>(reg(S::Context, 0x318 + n * 0xf)) | (static_cast<uint64_t>(reg(S::Context, 0x390 + n) & 0xffu) << 32u)) << 8u;
						mw += std::snprintf(mrt + mw, sizeof(mrt) - static_cast<size_t>(mw), " %u:%010" PRIx64, n, bn);
					}
					if (mw > 0 && !watch_quiet && matched) journal("draw journal mrt buf %u at %zu:%s | ps %010" PRIx64 "\n", buf_no, off, mrt, ps);
				}
				// Experiment 0105: the title's frame-pacing kernel 0x11d0288100 (one workgroup; its
				// disassembly, private): it spins on s_memrealtime until a deadline computed from the four
				// dwords of the buffer at user data 4-7 and the times it stored at dwords 64-70 of the
				// buffer at user data 0-3 (V#: base = dword0 | dword1[15:0] << 32). Both journaled, as the
				// title left them before this dispatch, with the host's monotonic time.
				if (((pkt[0] >> 8u) & 0xffu) == 0x15 && cs == 0x11d0288100ull) {
					uint32_t u[8];
					for (uint32_t k = 0; k < 8; k++) u[k] = reg(S::Sh, 0x240 + k);
					const uint64_t pb = u[4] | (static_cast<uint64_t>(u[5] & 0xffffu) << 32u);
					const uint64_t sb = u[0] | (static_cast<uint64_t>(u[1] & 0xffffu) << 32u);
					uint32_t       pv[4] = {}, sv[8] = {};
					const bool     pok = pb != 0 && read(pb, 16) != nullptr, sok = sb != 0 && read(sb + 64 * 4, 32) != nullptr;
					if (pok) std::memcpy(pv, reinterpret_cast<const void*>(pb), 16);
					if (sok) std::memcpy(sv, reinterpret_cast<const void*>(sb + 64 * 4), 32);
					journal("pace kernel t %.4f: params %010" PRIx64 "%s: %08x %08x %08x %08x | stored %010" PRIx64 "%s: %08x %08x %08x %08x %08x %08x %08x %08x\n", timing_now(), pb,
					        pok ? "" : " (unreadable)", pv[0], pv[1], pv[2], pv[3], sb + 64 * 4, sok ? "" : " (unreadable)", sv[0], sv[1], sv[2], sv[3], sv[4], sv[5], sv[6], sv[7]);
				}
				// Experiment 0104: a draw or dispatch touching a watched surface: a colour target based in
				// it, or user data (direct, or among the 64 dwords of a table a user-data pair points at)
				// holding its base >> 8. Journaled with the colour state (Mesa gfx10 register JSON: CB_COLORn_INFO
				// ctx 0x31c + n * 0xf, CB_BLEND0_CONTROL 0x1e0, CB_COLOR_CONTROL 0x202; CB_COLOR0_CLEAR_WORD0/1
				// 0x323/0x324, TODO(verify)) or the compute user data.
				if (watch_quiet) {
					std::vector<uint64_t> wv;
					{
						std::lock_guard lock(g_watch_mutex);
						wv = g_watch_surfaces;
					}
					const bool compute = ((pkt[0] >> 8u) & 0xffu) == 0x15 || ((pkt[0] >> 8u) & 0xffu) == 0x16;
					auto       watched = [&wv](uint64_t a) -> uint64_t {
						for (const uint64_t w: wv)
							if (a >= w && a < w + 0x1fe0000ull) return w;
						return 0;
					};
					std::string how;
					uint64_t    hit = 0;
					if (!compute) {
						const uint32_t mask = reg(S::Context, 0x8e);
						for (uint32_t n = 0; n < 8 && hit == 0; n++) {
							if (((mask >> (4u * n)) & 0xfu) == 0) continue;
							const uint64_t bn = (static_cast<uint64_t>(reg(S::Context, 0x318 + n * 0xf)) | (static_cast<uint64_t>(reg(S::Context, 0x390 + n) & 0xffu) << 32u)) << 8u;
							if ((hit = watched(bn)) != 0) {
								char b[260];
								std::snprintf(b, sizeof(b), "CB%u info %08x blend0 %08x color_control %08x clear %08x %08x mask %08x col_format %08x shader_mask %08x", n, reg(S::Context, 0x31c + n * 0xf), reg(S::Context, 0x1e0),
								              reg(S::Context, 0x202), reg(S::Context, 0x323), reg(S::Context, 0x324), mask, reg(S::Context, 0x1c5), reg(S::Context, 0x8f));
								how = b;
							}
						}
					}
					const uint32_t ubase = compute ? 0x240u : 0x0cu, nud = compute ? 16u : 32u;
					std::vector<uint32_t> ud(nud);
					for (uint32_t k = 0; k < nud; k++) ud[k] = reg(S::Sh, ubase + k);
					for (uint32_t k = 0; k < nud && hit == 0; k++) {
						for (const uint64_t w: wv) {
							if (ud[k] == static_cast<uint32_t>(w >> 8u)) {
								hit = w;
								how = "user data " + std::to_string(k) + " direct";
								break;
							}
						}
						if (hit == 0 && k + 1 < nud) {
							const uint64_t addr = ud[k] | (static_cast<uint64_t>(ud[k + 1] & 0xffffu) << 32u);
							if (addr >= 0x1000000000ull && addr < 0x1400000000ull && (addr & 3u) == 0 && read(addr, 256) != nullptr) {
								const auto* m = reinterpret_cast<const uint32_t*>(addr);
								for (uint32_t q = 0; q < 64 && hit == 0; q++) {
									for (const uint64_t w: wv) {
										if (m[q] == static_cast<uint32_t>(w >> 8u)) {
											hit = w;
											char b[120];
											std::snprintf(b, sizeof(b), "user data %u table %010" PRIx64 " dword %u", k, addr, q);
											how = b;
											break;
										}
									}
								}
							}
						}
					}
					if (hit != 0) {
						char u[200] = {};
						int  uw     = 0;
						for (uint32_t k = 0; k < 16 && uw < 180; k++) uw += std::snprintf(u + uw, sizeof(u) - static_cast<size_t>(uw), " %08x", ud[k]);
						journal("watch hit t %.3f: buf %u (%u dwords) at %zu: %s surface %010" PRIx64 " via %s | rt0 %010" PRIx64 " %ux%u | ps %010" PRIx64 " cs %010" PRIx64 " | pkt%s | ud%s\n",
						        timing_now(), buf_no, num_dwords, off, compute ? "dispatch" : "draw", hit, how.c_str(), rt, ((attrib2 >> 14u) & 0x3fffu) + 1u, (attrib2 & 0x3fffu) + 1u, ps, cs, words, u);
						// The UI pixel shaders (0x09099c4300 and relatives) read their paint through the V# at
						// table(user data 28-29) + 0x20 (their disassembly, private): its first 32 dwords as floats.
						if (!compute && nud > 29) {
							const uint64_t tab = ud[28] | (static_cast<uint64_t>(ud[29] & 0xffffu) << 32u);
							if (tab != 0 && read(tab + 0x20, 16) != nullptr) {
								const auto*    vs   = reinterpret_cast<const uint32_t*>(tab + 0x20);
								const uint64_t vb   = vs[0] | (static_cast<uint64_t>(vs[1] & 0xffffu) << 32u);
								const uint32_t strd = (vs[1] >> 16u) & 0x3fffu;
								if (vb != 0 && read(vb, 128) != nullptr) {
									const auto* f = reinterpret_cast<const float*>(vb);
									char        fl[600] = {};
									int         fw      = 0;
									for (int q = 0; q < 32 && fw < 560; q++) fw += std::snprintf(fl + fw, sizeof(fl) - static_cast<size_t>(fw), " %.3g", static_cast<double>(f[q]));
									journal("watch paint: V# base %010" PRIx64 " stride %u records %u:%s\n", vb, strd, vs[2], fl);
								}
							}
						}
					}
				}
				// Experiment 0092: BC5_DIRECT_DRAW_JOURNAL_FIND=<hex>[,<hex>...] journals each draw or dispatch
				// whose user data (COMPUTE_USER_DATA_0..15 sh 0x240-0x24f, SPI_SHADER_USER_DATA_PS_0..31 sh
				// 0x0c-0x2b, Mesa gfx10 register JSON) holds one of the values, directly or among the 64 dwords
				// behind a user-data pair that forms a mapped address (descriptor tables).
				{
					static const std::vector<uint32_t> find = [] {
						std::vector<uint32_t> v;
						if (const char* e = BC5_DIAG_ENV("BC5_DIRECT_DRAW_JOURNAL_FIND"); e != nullptr) {
							for (const char* q = e; *q != 0;) {
								if (*q == 'l') { // experiment 0157: the "layer" token
									while (*q != 0 && *q != ',') q++;
									if (*q == ',') q++;
									continue;
								}
								char* end = nullptr;
								v.push_back(static_cast<uint32_t>(std::strtoul(q, &end, 16)));
								if (end == q) break;
								q = *end == ',' ? end + 1 : end;
							}
						}
						return v;
					}();
					static const bool find_layer = [] {
						const char* e = BC5_DIAG_ENV("BC5_DIRECT_DRAW_JOURNAL_FIND");
						return e != nullptr && std::strstr(e, "layer") != nullptr;
					}();
					const uint32_t layer_hi = find_layer ? static_cast<uint32_t>(g_layer0_base.load() >> 8u) : 0u;
					auto           is_hit   = [&](uint32_t v) { return (layer_hi != 0 && v == layer_hi) || std::find(find.begin(), find.end(), v) != find.end(); };
					if (!find.empty() || layer_hi != 0) {
						const bool compute = ((pkt[0] >> 8u) & 0xffu) == 0x15 || ((pkt[0] >> 8u) & 0xffu) == 0x16;
						const uint32_t base = compute ? 0x240u : 0x0cu, nud = compute ? 16u : 32u;
						std::vector<uint32_t> ud(nud);
						for (uint32_t k = 0; k < nud; k++) ud[k] = reg(S::Sh, base + k);
						for (uint32_t k = 0; k < nud; k++) {
							bool hit = is_hit(ud[k]);
							const char* where = "direct";
							uint64_t    at    = 0, tab = 0;
							if (!hit && k + 1 < nud) {
								const uint64_t addr = ud[k] | (static_cast<uint64_t>(ud[k + 1] & 0xffffu) << 32u);
								if (addr >= 0x1000000000ull && addr < 0x1400000000ull && (addr & 3u) == 0 && read(addr, 256) != nullptr) {
									const auto* m = reinterpret_cast<const uint32_t*>(addr);
									for (uint32_t q = 0; q < 64 && !hit; q++) {
										if (is_hit(m[q])) {
											hit   = true;
											where = "table";
											at    = addr + q * 4u;
											tab   = addr;
										}
									}
								}
							}
							if (hit) {
								journal("draw journal find: %s %s ud%u (%08x) %s %010" PRIx64 " | rt0 %010" PRIx64 " | ps %010" PRIx64 " cs %010" PRIx64 " | pkt%s\n", compute ? "dispatch" : "draw",
								        compute ? "cs" : "ps", k, ud[k], where, at, rt, ps, cs, words);
								// Experiment 0156: the packet's user data and, for a table hit, the table's 64 dwords.
								if (compute) {
									char u[200] = {};
									int  uw     = 0;
									for (uint32_t q = 0; q < nud && uw < 180; q++) uw += std::snprintf(u + uw, sizeof(u) - static_cast<size_t>(uw), " %08x", ud[q]);
									journal("find ud cs %010" PRIx64 " t %.3f:%s\n", cs, timing_now(), u);
								}
								if (tab != 0 && read(tab, 256) != nullptr) {
									const auto* m       = reinterpret_cast<const uint32_t*>(tab);
									char        tb[640] = {};
									int         tw      = 0;
									for (uint32_t q = 0; q < 64; q++) tw += std::snprintf(tb + tw, sizeof(tb) - static_cast<size_t>(tw), " %08x", m[q]);
									journal("find table %010" PRIx64 ":%s\n", tab, tb);
								}
								break;
							}
						}
					}
				}
				// Experiment 0091: for a full-screen 2560x1440 compute pass (DISPATCH_DIRECT 320 x 180), the
				// COMPUTE_USER_DATA_0..15 (sh 0x240-0x24f, Mesa gfx10 register JSON) and, for each pair of
				// them that forms a mapped guest address, the 16 dwords there.
				// Experiment 0094: also the 288-group pass of the copy kernel 0x11d0288a00 run just before the
				// final composition.
				if (pkt.size() >= 4 && ((pkt[0] >> 8u) & 0xffu) == 0x15 && ((pkt[1] == 320 && pkt[2] == 180) || (pkt[1] == 0x120 && pkt[2] == 1))) {
					uint32_t ud[16];
					for (uint32_t k = 0; k < 16; k++) ud[k] = reg(S::Sh, 0x240 + k);
					journal("draw journal cs %010" PRIx64 " user data %08x %08x %08x %08x %08x %08x %08x %08x %08x %08x %08x %08x %08x %08x %08x %08x\n", cs, ud[0], ud[1], ud[2], ud[3],
					        ud[4], ud[5], ud[6], ud[7], ud[8], ud[9], ud[10], ud[11], ud[12], ud[13], ud[14], ud[15]);
					// Experiment 0099: the layer constants of the final pass: the buffer descriptor at
					// table(user data 12-13) + 0x10 (V# base: dword 0 + bits 15:0 of dword 1), 12 dwords
					// there (layer count, scales, layer indices; the pass's disassembly, private).
					if (cs == 0x11d0404200ull) {
						const uint64_t tab = ud[12] | (static_cast<uint64_t>(ud[13] & 0xffffu) << 32u);
						if (read(tab, 32) != nullptr) {
							const auto*    vd = reinterpret_cast<const uint32_t*>(tab + 0x10);
							const uint64_t vb = vd[0] | (static_cast<uint64_t>(vd[1] & 0xffffu) << 32u);
							if (read(vb, 64) != nullptr) {
								const auto* c = reinterpret_cast<const uint32_t*>(vb);
								journal("draw journal layers %010" PRIx64 ": %08x %08x %08x %08x | %08x %08x %08x %08x | %08x %08x %08x %08x\n", vb, c[0], c[1], c[2], c[3], c[4], c[5], c[6], c[7], c[8], c[9],
								        c[10], c[11]);
								// The image descriptor of each layer: table base (user data 8-9, a V# base) + index * 32.
								const uint64_t tb = ud[8] | (static_cast<uint64_t>(ud[9] & 0xffffu) << 32u);
								for (uint32_t l = 0; l < c[0] && l < 4; l++) {
									const uint64_t da = tb + static_cast<uint64_t>(c[4 + l]) * 32u;
									if (read(da, 32) == nullptr) continue;
									const auto* d = reinterpret_cast<const uint32_t*>(da);
									journal("draw journal layer %u index %x -> %010" PRIx64 ": %08x %08x %08x %08x %08x %08x %08x %08x\n", l, c[4 + l], da, d[0], d[1], d[2], d[3], d[4], d[5], d[6], d[7]);
									// Experiment 0104: what backs the layer at this moment, for the guest (its mapped ranges)
									// and for the GPU (the direct path's mappings). T# fields (GFX10, as in the RT dump notes):
									// base = (dword0 | dword1[7:0] << 32) << 8, width - 1 = dword2[13:0] << 2 | dword1[31:30],
									// height - 1 = dword2[29:14]; 4 bytes a pixel, height padded to 64 rows (TODO(verify)).
									{
										const uint64_t lb     = (static_cast<uint64_t>(d[0]) | (static_cast<uint64_t>(d[1] & 0xffu) << 32u)) << 8u;
										const uint32_t lw     = (((d[2] & 0x3fffu) << 2u) | (d[1] >> 30u)) + 1u;
										const uint32_t lh     = ((d[2] >> 14u) & 0xffffu) + 1u;
										const uint64_t lbytes = static_cast<uint64_t>(lw) * ((lh + 63u) & ~63u) * 4u;
										struct Cover {
											uint64_t    lo, hi, covered = 0;
											std::string names;
										} cv {lb, lb + lbytes};
										Libs::LibKernel::Memory::Bc5ForEachMappedRange(nullptr, &cv, [](uint64_t start, uint64_t size, uint64_t, int type, int, const char* name, void* p) {
											auto*          cc = static_cast<Cover*>(p);
											const uint64_t x = std::max(start, cc->lo), y = std::min(start + size, cc->hi);
											if (x >= y) return;
											cc->covered += y - x;
											char buf[96];
											std::snprintf(buf, sizeof(buf), " [%010" PRIx64 "+%" PRIx64 " t%d %s]", x, y - x, type, name != nullptr ? name : "");
											if (cc->names.size() < 400) cc->names += buf;
										});
										uint64_t    gpu = 0, gpu_shared = 0;
										std::string gnames;
										for (const auto& m: *maps_p) {
											const uint64_t x = std::max(m.va, lb), y = std::min(m.va + m.size, lb + lbytes);
											if (x >= y) continue;
											gpu += y - x;
											if (m.shared) gpu_shared += y - x;
											char buf[64];
											std::snprintf(buf, sizeof(buf), " [%010" PRIx64 "+%" PRIx64 " %s]", x, y - x, m.shared ? "s" : "u");
											if (gnames.size() < 400) gnames += buf;
										}
										if (l == 0) g_layer0_base.store(lb);
										journal("draw journal layer %u cover %010" PRIx64 " %ux%u (%" PRIu64 " bytes): guest %" PRIu64 ":%s | GPU %" PRIu64 " (shared %" PRIu64 "):%s\n", l, lb, lw, lh, lbytes,
										        cv.covered, cv.names.c_str(), gpu, gpu_shared, gnames.c_str());
									}
								}
							}
						}
					}
					for (uint32_t k = 0; k + 1 < 16; k++) {
						const uint64_t a = ud[k] | (static_cast<uint64_t>(ud[k + 1] & 0xffffu) << 32u);
						if (a < 0x1000000000ull || a >= 0x1400000000ull || (a & 3u) != 0 || read(a, 64) == nullptr) continue;
						const auto* m = reinterpret_cast<const uint32_t*>(a);
						journal("draw journal cs %010" PRIx64 " ud%u:%u -> %010" PRIx64 ": %08x %08x %08x %08x %08x %08x %08x %08x %08x %08x %08x %08x %08x %08x %08x %08x\n", cs, k, k + 1, a,
						        m[0], m[1], m[2], m[3], m[4], m[5], m[6], m[7], m[8], m[9], m[10], m[11], m[12], m[13], m[14], m[15]);
					}
				}
			});
		}
		if (t_fs_valid || prefix_all() || cs_prefix_mode() != 0 || acb_restore_on()) t_fs_before = tracker; // + exp 0381
		if (!waits.empty()) with_waits++;
	}
	tracker.apply(span, read, st);
	ms += (timing_now() - t0) * 1000.0;
	if (t0 - last_report >= 10.0) {
		last_report = t0;
		{ // experiment 0157: every context register the tracker holds (the title's state so far)
			std::string line = "tracked context:";
			for (uint32_t o = 0; o < 0x400u; o++) {
				uint32_t v = 0;
				if (tracker.get(bc5::full_state::Context, o, v)) {
					char b[24];
					std::snprintf(b, sizeof(b), " %x:%08x", o, v);
					line += b;
				}
			}
			journal("%s\n", line.c_str());
		}
		journal("piece check: %" PRIu64 " graphics buffers, %" PRIu64 " with waits; tracked config %zu context %zu sh %zu uconfig %zu; tables %" PRIu64
		        " unreadable %" PRIu64 ", nested %" PRIu64 " unreadable %" PRIu64 ", clears %" PRIu64 " pushes %" PRIu64 " pops %" PRIu64
		        "; %.0f ms\n",
		        bufs, with_waits, tracker.count(bc5::full_state::Config), tracker.count(bc5::full_state::Context),
		        tracker.count(bc5::full_state::Sh), tracker.count(bc5::full_state::Uconfig), st.tables, st.unreadable_tables, st.nested,
		        st.unreadable_nested, st.clears, st.pushes, st.pops, ms);
		journal("pieces full: %" PRIu64 " splits made, the wait then satisfied %" PRIu64 ", not satisfied %" PRIu64 "\n", g_full_pieces.exchange(0), g_full_ok.exchange(0),
		        g_full_failed.exchange(0));
		{
			const uint64_t n = g_dry_splits.exchange(0);
			journal("pieces dry: %" PRIu64 " splits in %" PRIu64 " buffers, prefix mean %" PRIu64 " dwords, build %.1f ms in all, max %.2f ms; the waits then: %" PRIu64
			        " kept for the GPU, %" PRIu64 " served on the CPU, %" PRIu64 " given up or broken\n",
			        n, g_dry_bufs.exchange(0), n != 0 ? g_dry_prefix.exchange(0) / n : 0, static_cast<double>(g_dry_ns.exchange(0)) / 1e6,
			        static_cast<double>(g_dry_max_ns.exchange(0)) / 1e6, g_dry_kept.exchange(0), g_dry_ok.exchange(0), g_dry_failed.exchange(0));
		}
		bufs = with_waits = 0;
		ms   = 0;
	}
}

// Experiment 0401 series e3 (the top session, 2026-11-03: the next guest crash should show whether memory was at its
// floor): a journal line every 10 s with MemAvailable and swap used (/proc/meminfo), PSI memory (/proc/pressure/memory: some
// and full avg10, full total) and GTT used (amdgpu's sysfs mem_info_gtt_used / mem_info_gtt_total), each file read once, no
// smaps walk; the journal is flushed after it. A value that cannot be read is "unknown" (mem_line_parse). On by default;
// BC5_DIRECT_MEM_LINE=0 turns it off.
// Series e3 (Codex's second review of e3): the memory line's parsing, pure. A field whose file could not be read, or whose
// key or number is missing, is "unknown" in the line, never 0, so a missing file cannot look like memory at its floor or
// like no swap in use.
struct MemLine {
	bool     avail_ok = false, swap_ok = false, some_ok = false, full_ok = false, gtt_ok = false;
	uint64_t avail_kib = 0, swap_used_kib = 0, full_total_us = 0, gtt_used = 0, gtt_total = 0;
	double   some10 = 0.0, full10 = 0.0;
};
static bool mem_line_key(const char* text, const char* key, uint64_t* v) { // "Key:   1234 kB" -> 1234
	const size_t kl = std::strlen(key);
	for (const char* l = text; l != nullptr && *l != 0;) {
		if (std::strncmp(l, key, kl) == 0 && l[kl] == ':') {
			char* end = nullptr;
			*v        = std::strtoull(l + kl + 1, &end, 10);
			return end != l + kl + 1;
		}
		l = std::strchr(l, '\n');
		if (l != nullptr) l++;
	}
	return false;
}
static bool mem_line_number(const char* text, uint64_t* v) {
	if (text == nullptr) return false;
	char* end = nullptr;
	*v        = std::strtoull(text, &end, 10);
	return end != text;
}
// Each argument is a file's text, or nullptr when the file could not be read.
static MemLine mem_line_parse(const char* meminfo, const char* psi, const char* gtt_used, const char* gtt_total) {
	MemLine m;
	if (meminfo != nullptr) {
		uint64_t swap_total = 0, swap_free = 0;
		m.avail_ok = mem_line_key(meminfo, "MemAvailable", &m.avail_kib);
		if (mem_line_key(meminfo, "SwapTotal", &swap_total) && mem_line_key(meminfo, "SwapFree", &swap_free)) {
			m.swap_ok       = true;
			m.swap_used_kib = swap_total - std::min(swap_free, swap_total);
		}
	}
	if (psi != nullptr) {
		m.some_ok                 = std::sscanf(psi, "some avg10=%lf", &m.some10) == 1;
		const char*        full    = std::strstr(psi, "full ");
		unsigned long long total  = 0;
		m.full_ok                 = full != nullptr && std::sscanf(full, "full avg10=%lf avg60=%*f avg300=%*f total=%llu", &m.full10, &total) == 2;
		m.full_total_us           = total;
	}
	m.gtt_ok = mem_line_number(gtt_used, &m.gtt_used) && mem_line_number(gtt_total, &m.gtt_total);
	return m;
}
static void mem_line_format(const MemLine& m, double t, char* out, size_t cap) {
	char a[32] = "unknown", sw[32] = "unknown", so[32] = "unknown", fu[32] = "unknown", ft[32] = "unknown", gu[32] = "unknown", gt[32] = "unknown";
	if (m.avail_ok) std::snprintf(a, sizeof(a), "%llu", static_cast<unsigned long long>(m.avail_kib >> 10u));
	if (m.swap_ok) std::snprintf(sw, sizeof(sw), "%llu", static_cast<unsigned long long>(m.swap_used_kib >> 10u));
	if (m.some_ok) std::snprintf(so, sizeof(so), "%.2f", m.some10);
	if (m.full_ok) {
		std::snprintf(fu, sizeof(fu), "%.2f", m.full10);
		std::snprintf(ft, sizeof(ft), "%llu", static_cast<unsigned long long>(m.full_total_us / 1000u));
	}
	if (m.gtt_ok) {
		std::snprintf(gu, sizeof(gu), "%llu", static_cast<unsigned long long>(m.gtt_used >> 20u));
		std::snprintf(gt, sizeof(gt), "%llu", static_cast<unsigned long long>(m.gtt_total >> 20u));
	}
	std::snprintf(out, cap, "memory (exp 0401): t %.1f s: available %s MiB, swap used %s MiB, psi some %s full %s (avg10, %%), full total %s ms, gtt %s of %s MiB\n", t, a, sw, so, fu, ft, gu, gt);
}
static bool mem_line_read(const char* path, char* buf, size_t cap) {
	FILE* f = std::fopen(path, "r");
	if (f == nullptr) return false;
	const size_t n = std::fread(buf, 1, cap - 1, f);
	std::fclose(f);
	buf[n] = 0;
	return n != 0;
}
static void mem_line_loop() {
	std::string gtt_dir;
	for (int c = 0; c < 8 && gtt_dir.empty(); c++) {
		const std::string d = "/sys/class/drm/card" + std::to_string(c) + "/device/";
		if (access((d + "mem_info_gtt_used").c_str(), R_OK) == 0) gtt_dir = d;
	}
	for (;;) {
		std::this_thread::sleep_for(std::chrono::seconds(10));
		char       mi[8192], ps[512], gu[64], gt[64], line[512];
		const bool mi_ok = mem_line_read("/proc/meminfo", mi, sizeof(mi));
		const bool ps_ok = mem_line_read("/proc/pressure/memory", ps, sizeof(ps));
		const bool gu_ok = !gtt_dir.empty() && mem_line_read((gtt_dir + "mem_info_gtt_used").c_str(), gu, sizeof(gu));
		const bool gt_ok = !gtt_dir.empty() && mem_line_read((gtt_dir + "mem_info_gtt_total").c_str(), gt, sizeof(gt));
		mem_line_format(mem_line_parse(mi_ok ? mi : nullptr, ps_ok ? ps : nullptr, gu_ok ? gu : nullptr, gt_ok ? gt : nullptr), timing_now(), line, sizeof(line));
		journal("%s", line);
		if (g_journal_min) (void)journal_min_file(true);
	}
}
static void mem_line_start() {
	static std::once_flag once;
	std::call_once(once, [] {
		const char* e  = BC5_DIAG_ENV("BC5_DIRECT_MEM_LINE");
		const bool  on = e == nullptr || *e == 0 || std::strcmp(e, "0") != 0;
		journal("exp 0401: memory line %s\n", on ? "every 10 s (MemAvailable, swap, PSI memory, GTT)" : "off");
		if (on) std::thread(mem_line_loop).detach();
	});
}

static void submit(const uint32_t* ib, uint32_t num_dwords, const char* kind) {
	mem_line_start(); // experiment 0401 series e3
	if (!chain_on()) SoftCp::clear_gpu_executed(); // the soft CP runs this buffer next, on this thread (ADR 0010: per call, chain_begin)
	if (g_stage == Stage::Off || !g_dev || ib == nullptr || num_dwords == 0) return;
	const ChainInSubmit in_submit(chain_cross()); // ADR 0010 section B
	piece_check(ib, num_dwords, kind);
	if (std::strcmp(kind, "ring") == 0) {
		for (uint32_t q = 0; q < num_dwords;) {
			const uint32_t h = ib[q];
			const uint32_t type = h >> 30u;
			uint32_t len = 1;
			if (type == 3 || type == 0) { const uint32_t c = (h >> 16u) & 0x3fffu; len = c == 0x3fffu ? 1 : c + 2; }
			if (q + len > num_dwords) break;
			if (type == 3 && (((h >> 8u) & 0xffu) == 0x3f || ((h >> 8u) & 0xffu) == 0x33) && len >= 4) {
				const uint64_t ta = (ib[q + 1] & ~3u) | (static_cast<uint64_t>(ib[q + 2] & 0xffu) << 32u);
				const uint32_t tn = ib[q + 3] & 0xfffffu;
				if (ta != 0 && tn != 0) {
					const auto* t = reinterpret_cast<const uint32_t*>(ta);
					uint32_t skip = 0;
					for (size_t k = 0; k < g_acb_heads.size(); k++) {
						if (g_acb_heads[k].ib == t && g_acb_heads[k].num_dwords == tn) {
							skip = g_acb_heads[k].done;
							m11_head_check(g_acb_heads[k].marks, g_acb_heads[k].reopens, "rest"); // exp 0401 e11 (tag m11): BC5_DIRECT_RESET_REPLAY_ACB
							for (auto& g: g_acb_heads[k].marks) SoftCp::t_gpu_done.push_back(std::move(g));
							g_acb_heads.erase(g_acb_heads.begin() + static_cast<long>(k));
							break;
						}
					}
					if (skip < tn) {
						t_ring = acb_ring(t, tn); // ADR 0009
						if (skip > 0) {
							uint32_t        n   = 0;
							const uint32_t* pre = state_prefix(t, skip, &n);
							journal("acb rest %u..%u of %u dwords: state prefix of %u dwords replayed first\n", skip, tn, tn, n);
							if (pre != nullptr) submit_one(pre, n, "acb-state");
						}
						t_acb_from = skip; // experiment 0403: a rest starts there
						submit_split(t + skip, tn - skip, "acb");
						t_acb_from = 0;
						acb_cs_track(t + skip, tn - skip); // experiment 0401
						acb_inherit_track(t + skip, tn - skip); // experiment 0403
						t_ring = bc5::direct::kGfxRing;
					}
				}
			} else if (type == 3) {
				acb_inherit_census(ib + q, len); // experiment 0403: a non-IB packet on the guest ring
			}
			q += len;
		}
		acb_inherit_census_slice(); // experiment 0403
		return;
	}
	submit_split(ib, num_dwords, kind);
}

// After a fence timeout: learn the fault, wait out the kernel's reset and
// open a fresh device. The caller holds g_dev_mutex.
// Experiment 0058: BC5_DIRECT_UMR_ON_TIMEOUT=1 — at the host's fence timeout (2 s), before anything
// else and long before the kernel's own timeout and ring reset, the waves still on the GPU are
// dumped with umr on the host (the emulator runs in a container): halted SQ, the gfx ring searched
// for the shaders they run, disassembly. Output in the capture directory, synced to disk at once
// (a reset after a hang without a page fault has taken the machine down). The first two only.
static void umr_on_timeout() {
	static const bool on = BC5_DIAG_ENV("BC5_DIRECT_UMR_ON_TIMEOUT") != nullptr;
	static std::atomic<int> n {0};
	if (!on || n.load() >= 2) return;
	const int k = n++;
	if (k >= 2) return;
	const std::string dir = g_dump_dir.empty() ? std::string(std::getenv("HOME") ? std::getenv("HOME") : ".") + "/bc5-work" : g_dump_dir;
	char cmd[1024];
	std::snprintf(cmd, sizeof(cmd),
	              "(distrobox-host-exec sudo -n /usr/local/bin/bc5-gpu-hang-dump || distrobox-host-exec sudo -n /usr/bin/umr -O halt_waves -wa gfx_0.0.0) > %s/umr-waves-%d.txt 2>&1; "
	              "sync",
	              dir.c_str(), k);
	const int rc = std::system(cmd);
	if (FILE* f = journal_min_file(true); f != nullptr) {
		std::fprintf(f, "umr: waves dumped to %s/umr-waves-%d.txt (rc %d)\n", dir.c_str(), k, rc);
		std::fflush(f);
		fsync(fileno(f));
	}
}

// Experiment 0058: the kernel resets the gfx ring ~2 s after a job hangs on it — at the moment the
// host's own 2 s fence wait gives up — so a dump at the host's timeout shows the ring after the
// reset (run 267). A watchdog dumps instead once a completion wait has lasted 0.9 s.
static std::atomic<uint64_t> g_fence_wait_since {0}; // SoftCp::now_ns() at the start of a completion wait, 0 = none
static void umr_watchdog_start() {
	static const bool on = BC5_DIAG_ENV("BC5_DIRECT_UMR_ON_TIMEOUT") != nullptr;
	if (!on) return;
	static std::once_flag once;
	std::call_once(once, [] {
		std::thread([] {
			for (;;) {
				std::this_thread::sleep_for(std::chrono::milliseconds(20));
				const uint64_t t0 = g_fence_wait_since.load();
				if (t0 != 0 && SoftCp::now_ns() - t0 > 900'000'000ull) {
					umr_on_timeout();
					while (g_fence_wait_since.load() == t0) std::this_thread::sleep_for(std::chrono::milliseconds(20));
				}
			}
		}).detach();
	});
}

// Experiment 0412 (tag fr412): BC5_FAULT_RECORD. A GPU fault is a bug to remove at its source: write what is needed to
// find it, then end the game. No reopen, no recovery.
namespace fr412 {
inline bool on() {
	static const bool v = [] {
		const char* e = BC5_DIAG_ENV("BC5_FAULT_RECORD");
		return e == nullptr || !(e[0] == '0' && e[1] == 0); // exp 0412 (mkdef0412.py): on by default, "0" turns it off
	}();
	return v;
}
} // namespace fr412
static void fr412_copy(const std::string& from, const std::string& to, long tail_bytes) {
	FILE* in = std::fopen(from.c_str(), "rb");
	if (in == nullptr) return;
	FILE* out = std::fopen(to.c_str(), "wb");
	if (out != nullptr) {
		if (tail_bytes > 0 && std::fseek(in, 0, SEEK_END) == 0) {
			const long size = std::ftell(in);
			std::fseek(in, size > tail_bytes ? size - tail_bytes : 0, SEEK_SET);
		}
		char   buf[65536];
		size_t n = 0;
		while ((n = std::fread(buf, 1, sizeof(buf), in)) != 0) std::fwrite(buf, 1, n, out);
		std::fclose(out);
	}
	std::fclose(in);
}
// Experiment 0412 (tag ph412): ph0412.inc, who holds a pointer to the faulted chunk.
namespace ph412 {
inline bool on() {
	static const bool v = [] {
		const char* e = BC5_DIAG_ENV("BC5_FAULT_POINTERS");
		return e != nullptr && e[0] != 0 && !(e[0] == '0' && e[1] == 0);
	}();
	return v;
}
constexpr uint64_t kMask40 = (1ull << 40u) - 1;
// Every position p (a multiple of 4) of the block with p + 8 <= n whose 64-bit little-endian word has its low 40
// bits in [lo, hi): hit(p, word). A buffer descriptor keeps other fields above bit 40, a plain pointer keeps zero
// there; the caller is given the whole word and can tell. Words that straddle the block's end are not seen.
template <typename F> inline void scan(const uint8_t* p, size_t n, uint64_t lo, uint64_t hi, F&& hit) {
	if (n < 8) return;
	for (size_t i = 0; i + 8 <= n; i += 4) {
		uint64_t w;
		std::memcpy(&w, p + i, 8);
		const uint64_t a = w & kMask40;
		if (a >= lo && a < hi) hit(i, w);
	}
}
inline bool plain(uint64_t w) { return (w >> 40u) == 0; }
} // namespace ph412
// Experiment 0412 (tag ph412): BC5_FAULT_POINTERS, the host's part. Called once by the fault record, after the save guard.
static void ph412_record(const std::string& dir, uint64_t page) {
	if (!ph412::on() || page == 0) return;
	const uint64_t lo = page & ~(kDChunk - 1), hi = lo + kDChunk;
	FILE*          out = std::fopen((dir + "/pointers.txt").c_str(), "w");
	if (out == nullptr) return;
	std::fprintf(out, "# exp 0412 (tag ph412): words of the title's memory whose low 40 bits lie in the faulted chunk 0x%" PRIx64 "+0x%" PRIx64 " (the fault page 0x%" PRIx64 ")\n", lo,
	             static_cast<uint64_t>(kDChunk), page);
	std::fprintf(out, "# file (0 direct, 1 private) file_offset holder_va word kind (pointer: nothing above bit 40; fields: a descriptor-like word) heap of the holder\n");
	const double                    t0 = timing_now();
	std::vector<uint8_t>            buf(4u << 20u);
	uint64_t                        hits = 0, plain = 0, bytes = 0;
	bool                            cut = false;
	std::map<std::string, uint64_t> by_heap;
	for (auto& S: g_d) {
		const int fd = dstate_fd(S);
		if (fd < 0) continue;
		std::vector<DView> views;
		if (S.kind == 0) views = direct_views(S)->v;
		off_t pos = 0;
		while (!cut) {
			const off_t d = lseek(fd, pos, SEEK_DATA);
			if (d < 0) break;
			const off_t h = lseek(fd, d, SEEK_HOLE);
			if (h <= d) break;
			for (off_t o = d; o < h && !cut;) {
				const size_t  want = static_cast<size_t>(std::min<off_t>(h - o, static_cast<off_t>(buf.size())));
				const ssize_t n    = pread(fd, buf.data(), want, o);
				if (n <= 0) break;
				bytes += static_cast<uint64_t>(n);
				ph412::scan(buf.data(), static_cast<size_t>(n), lo, hi, [&](size_t i, uint64_t w) {
					const uint64_t foff = static_cast<uint64_t>(o) + i;
					uint64_t       va   = foff;
					const char*    name = "private memory";
					if (S.kind == 0) {
						va   = 0;
						name = "under no view";
						for (const auto& v: views) {
							if (foff >= v.off && foff < v.off + v.size) {
								va   = v.va + (foff - v.off);
								name = v.name.c_str();
								break;
							}
						}
					}
					hits++;
					if (ph412::plain(w)) plain++;
					by_heap[name]++;
					if (hits <= 4000) std::fprintf(out, "%d 0x%" PRIx64 " 0x%" PRIx64 " 0x%016" PRIx64 " %s %s\n", S.kind, foff, va, w, ph412::plain(w) ? "pointer" : "fields", name);
				});
				o += n;
				if (timing_now() - t0 > 30.0) cut = true;
			}
			pos = h;
		}
	}
	std::fprintf(out, "# %" PRIu64 " words found (%" PRIu64 " plain pointers) in %.1f MiB read in %.1f s%s; the first 4000 are listed; by heap of the holder:\n", hits, plain,
	             static_cast<double>(bytes) / 1048576.0, timing_now() - t0, cut ? "; CUT at 30 s, not all memory was read" : "");
	for (const auto& [name, n]: by_heap) std::fprintf(out, "# %" PRIu64 " %s\n", n, name.c_str());
	std::fclose(out);
	journal("fault pointers (exp 0412, tag ph412): %" PRIu64 " words of the title's memory point into the faulted chunk 0x%" PRIx64 " (%" PRIu64 " plain pointers), %.1f MiB read in %.1f s%s: pointers.txt in the fault record\n",
	        hits, lo, plain, static_cast<double>(bytes) / 1048576.0, timing_now() - t0, cut ? ", CUT at 30 s" : "");
}
[[noreturn]] static void fr412_record_and_exit(uint64_t fault, uint32_t status, bool timed_out, int rc) {
	const double t = timing_now();
	{ // one record: a second thread that arrives here while the first writes is held
		static std::atomic<bool> once {false};
		if (once.exchange(true)) {
			for (;;) std::this_thread::sleep_for(std::chrono::hours(1));
		}
	}
	// The save guard (tag sg412): the exit must not cut a save. A save being written through the host's calls is let
	// finish (5 s at most), nothing new starts, then what was written is flushed and synced. The outcome goes into
	// the record.
	const sg412::Closed sg      = sg412::close(5000);
	int                 sg_sync = -2; // -2 no save directory was mounted in this run, -1 it could not be opened, else syncfs's result
	if (sg.complete) std::fflush(nullptr);
	if (sg412::g_root_set.load()) {
		const int fd = ::open(sg412::g_root, O_RDONLY | O_DIRECTORY | O_CLOEXEC);
		sg_sync      = fd < 0 ? -1 : ::syncfs(fd);
		if (fd >= 0) ::close(fd);
	}
	char         stamp[32] = "unknown";
	{
		const time_t now = std::time(nullptr);
		struct tm    tm {};
		if (localtime_r(&now, &tm) != nullptr) std::strftime(stamp, sizeof(stamp), "%Y%m%d-%H%M%S", &tm);
	}
	const std::string home = std::getenv("HOME") != nullptr ? std::getenv("HOME") : ".";
	const std::string base = home + "/bc5-data/captures/faults";
	const std::string dir  = base + "/" + stamp;
	mkdir(base.c_str(), 0700);
	mkdir(dir.c_str(), 0700);
	// what lay at the address (the catcher's questions)
	const bool     junk = (fault >> 40u) != 0;
	const uint64_t page = (junk ? fault & ((1ull << 40u) - 1) : fault) & ~0xfffull;
	std::vector<std::pair<uint64_t, uint64_t>> guest;
	if (fault != 0) Libs::LibKernel::Memory::Bc5GuestRangesIn(page, page + 0x1000ull, &guest);
	bool        under = false, lazy = false, eager = false, imported = false;
	int         kind = -1;
	std::string name;
	uint64_t    view_va = 0, view_size = 0;
	if (FILE* fv = std::fopen((dir + "/layout-views.txt").c_str(), "w")) {
		std::fprintf(fv, "# file (0 direct, 1 private) va size file_offset flags(E eager, L lazy, D by data) name\n");
		for (auto& S: g_d) {
			if (dstate_fd(S) < 0) continue;
			const auto views_p = direct_views(S);
			for (const auto& v: views_p->v) {
				std::fprintf(fv, "%d 0x%" PRIx64 " 0x%" PRIx64 " 0x%" PRIx64 " %s %s\n", S.kind, v.va, v.size, v.off, v.eager ? "E" : (v.lazy ? "L" : "D"), v.name.c_str());
				if (fault != 0 && !under && page >= v.va && page < v.va + v.size) {
					under     = true;
					lazy      = v.lazy;
					eager     = v.eager;
					kind      = S.kind;
					name      = v.name;
					view_va   = v.va;
					view_size = v.size;
					imported  = direct_covered_end(S, (v.off + (page - v.va)) & ~(kDChunk - 1)) != 0;
				}
			}
		}
		std::fclose(fv);
	}
	if (FILE* fb = std::fopen((dir + "/layout-buffers.txt").c_str(), "w")) {
		std::fprintf(fb, "# file (0 direct, 1 private) file_offset size\n");
		for (auto& S: g_d) {
			for (const auto& b: S.bos) std::fprintf(fb, "%d 0x%" PRIx64 " 0x%" PRIx64 "\n", S.kind, b.off, b.size);
		}
		std::fclose(fb);
	}
	bool   mapped = false;
	size_t n_maps = 0;
	if (g_dev) {
		const auto maps = g_dev->mappings();
		n_maps          = maps.size();
		if (FILE* fm = std::fopen((dir + "/layout-mappings.txt").c_str(), "w")) {
			std::fprintf(fm, "# gpu_va size\n");
			for (const auto& m: maps) {
				std::fprintf(fm, "0x%" PRIx64 " 0x%" PRIx64 "\n", static_cast<uint64_t>(m.va), static_cast<uint64_t>(m.size));
				if (fault != 0 && page >= m.va && page < m.va + m.size) mapped = true;
			}
			std::fclose(fm);
		}
	}
	fr412_copy("/proc/meminfo", dir + "/meminfo.txt", 0);
	fr412_copy("/proc/pressure/memory", dir + "/pressure.txt", 0);
	ph412_record(dir, fault != 0 ? page : 0); // exp 0412 (tag ph412)
	if (FILE* fe = std::fopen((dir + "/environment.txt").c_str(), "w")) {
		for (char** e = environ; e != nullptr && *e != nullptr; e++) {
			if (std::strncmp(*e, "BC5", 3) == 0 || std::strncmp(*e, "KYTY", 4) == 0) std::fprintf(fe, "%s\n", *e);
		}
		std::fclose(fe);
	}
	if (FILE* fp = std::fopen((dir + "/process.txt").c_str(), "w")) {
		char    exe[1024] = "";
		ssize_t k = readlink("/proc/self/exe", exe, sizeof(exe) - 1);
		if (k > 0) exe[k] = 0;
		std::fprintf(fp, "binary %s\npid %d\ncommand line:", exe, static_cast<int>(getpid()));
		if (FILE* fc = std::fopen("/proc/self/cmdline", "rb")) {
			int c = 0;
			while ((c = std::fgetc(fc)) != EOF) std::fputc(c == 0 ? ' ' : c, fp);
			std::fclose(fc);
		}
		std::fprintf(fp, "\n");
		std::fclose(fp);
	}
	if (!g_dump_dir.empty()) fr412_copy(g_dump_dir + "/direct.log", dir + "/journal-tail.txt", 4l << 20);
	if (FILE* f = std::fopen((dir + "/record.txt").c_str(), "w")) {
		std::fprintf(f, "BC5 GPU fault record (exp 0412, tag fr412). A GPU fault is a bug to remove at its source; the game was ended here.\n\n");
		std::fprintf(f, "when: %s, %.3f s after the emulator's start\n", stamp, t);
		std::fprintf(f, "what the host saw: a submission %s (rc %d); the kernel's last fault address 0x%" PRIx64 ", status 0x%08x (%s)\n", timed_out ? "timed out after 2 s" : "failed", rc, fault, status,
		             fault == 0 ? "no fault address: a hang without a page fault" : ((status & (1u << 18u)) != 0 ? "a WRITE, by the status' bit 18" : "a READ, by the status' bit 18"));
		if (fault != 0) {
			std::fprintf(f, "kind: %s\n", mr412::classify(junk, !guest.empty(), under, lazy, eager, imported, mapped));
			std::fprintf(f, "the address: %s; guest range there: %s; under a view: %s", junk ? "a bit above 40 is set (the facts below are for its low 40 bits)" : "a plain guest address", guest.empty() ? "no" : "yes",
			             under ? "yes" : "NO");
			if (under) {
				std::fprintf(f, ": \"%s\" (%s file, %s), view 0x%" PRIx64 "+0x%" PRIx64 ", the address is 0x%" PRIx64 " into it; its 2 MiB chunk %s", name.c_str(), kind == 0 ? "direct" : "private",
				             eager ? "eager" : (lazy ? "lazy" : "by data"), view_va, view_size, page - view_va, imported ? "is imported" : "is NOT imported (the CPU never wrote it, or its heap is lazy)");
			}
			std::fprintf(f, "; a GPU mapping at the address: %s\n", mapped ? "yes" : "no");
		}
		std::fprintf(f, "memory: pinned direct %.1f MiB in %zu buffers, private %.1f MiB in %zu; %zu GPU mappings (meminfo.txt, pressure.txt)\n", static_cast<double>(g_d[0].bytes) / 1048576.0, g_d[0].bos.size(),
		             static_cast<double>(g_d[1].bytes) / 1048576.0, g_d[1].bos.size(), n_maps);
		std::fprintf(f, "saves (tag sg412): %s. At the request: %d save call(s) of the host in flight, %d save mount(s) written and not yet unmounted, the last save call began %" PRId64 " ms before (-1: none in this run). "
		                "Waited %" PRId64 " ms (5000 at most); left then: %d call(s), %d mount(s); %d caller(s) held from starting something new. Sync of the save directory: %s.\n",
		             sg412::verdict(sg), sg.ops_at_request, sg.dirty_at_request, sg.last_op_age_ms, sg.waited_ms, sg.ops_left, sg.dirty_left, sg.held,
		             sg_sync == 0 ? "done" : (sg_sync == -2 ? "not needed (no save directory was mounted)" : "FAILED"));
		std::fprintf(f, "the capture directory of this run (the whole journal, the dumped buffers of the timed-out jobs): %s\n", g_dump_dir.empty() ? "(none: logging was off)" : g_dump_dir.c_str());
		std::fprintf(f, "\nin this directory: journal-tail.txt (the probe's summary of the timed-out jobs, the last submissions, the ledger, the frame lines), layout-views.txt, layout-buffers.txt,\n"
		                "layout-mappings.txt, meminfo.txt, pressure.txt, environment.txt (every BC5_* and KYTY_* variable), process.txt.\n");
		std::fprintf(f, "\nNOT known to the emulator, added by the launcher when it can (dmesg.txt, build.txt): the kernel's own fault lines (client, RW, the ring), the devcoredump's path, the binary's md5.\n"
		                "Nothing here is read by a later run.\n");
		std::fclose(f);
	}
	journal("fault record (exp 0412, tag fr412): written to %s; the game ends here (BC5_FAULT_RECORD)\n", dir.c_str());
	std::fprintf(stderr, "[bc5] GPU FAULT at 0x%" PRIx64 " (status 0x%08x), %.1f s after the start: the record is in %s; the game ends here (exit 86). A GPU fault is a bug to fix, not something to get up from. Saves: %s.\n", fault,
	             status, t, dir.c_str(), sg412::verdict(sg));
	if (sg.complete) std::fflush(nullptr); // not when a save call is still in flight: it may hold a stream
	else std::fflush(stderr);
	_exit(86);
}
static void recover_after_timeout(const bc5::direct::SubmitResult& r) {
		LOGF_COLOR(Log::Color::Red, "[bc5-direct] fence timeout: fault 0x%" PRIx64 " status 0x%08x\n", r.fault_addr, r.fault_status);
		journal("timeout: fault 0x%" PRIx64 " status 0x%08x\n", r.fault_addr, r.fault_status);
		// Experiment 0140: BC5_DIRECT_SNAP_ON_TIMEOUT=<va hex>:<bytes> copies guest memory [va, va + bytes)
		// once, at the first timeout, to <capture dir>/timeout-snap.bin (fsync'd): the hung job is still
		// on the GPU, so the copy holds what it reads (the second title's per-frame BVH trees). Private.
		{
			static bool done = false;
			unsigned long long a = 0, n = 0;
			if (const char* e = BC5_DIAG_ENV("BC5_DIRECT_SNAP_ON_TIMEOUT"); !done && e != nullptr && std::sscanf(e, "%llx:%llu", &a, &n) == 2 && n != 0 && !g_dump_dir.empty()) {
				done = true;
				char name[512];
				std::snprintf(name, sizeof(name), "%s/timeout-snap.bin", g_dump_dir.c_str());
				if (g_dev && covered_sorted(*g_dev->sorted_mappings(), a, n)) {
					if (FILE* f = std::fopen(name, "wb"); f != nullptr) {
						std::fwrite(reinterpret_cast<const void*>(a), 1, n, f);
						std::fflush(f);
						fsync(fileno(f));
						std::fclose(f);
						journal("timeout snapshot: 0x%llx + %llu bytes -> timeout-snap.bin\n", a, n);
					}
				} else {
					journal("timeout snapshot: 0x%llx + %llu bytes not mapped\n", a, n);
				}
			}
		}
		mr412_would_learn(r.fault_addr, static_cast<uint32_t>(r.fault_status)); // exp 0412 (tag mr412)
		if (fr412::on()) fr412_record_and_exit(r.fault_addr, static_cast<uint32_t>(r.fault_status), r.timed_out, r.rc); // exp 0412 (tag fr412)
		// exp 0419: alias_learn (experiment 0056) is no longer called: no window is learned from a GPU fault
		// exp 0412 (tag nl412): no learned_add; the line above (mr412_would_learn) is all that happens for a fault
		// After the kernel's ring reset (F28) the process opens a fresh device and goes on; the
		// mappings are rebuilt by the next sync, the learned region is in. After any timeout: the
		// kernel's ring reset recovers shader stalls too (run 41).
		std::this_thread::sleep_for(std::chrono::seconds(12)); // the kernel's timeout + reset
		std::unique_lock finish_lock(g_finish_mutex);
		g_dev.reset();
		bc5::direct::OpenOptions ro;
		ro.gds_kib    = 64;
		ro.oa_count   = 16;
		ro.gws_count  = 64;
		ro.gds_shadow = true;
		g_dev = bc5::direct::Device::open(kRenderNode, ro);
		if (g_dev) g_dev->set_state_stack(true);
		mr412_prt_open(); // exp 0412 (tag mr412): after a reopen, as at the first open (experiment 0102)
		if (g_dev) g_dev->set_short_lists(true);
		if (g_dev) g_dev->set_dma_idle(true);
		if (g_dev) g_dev->set_async(g_async);
		g_hinted.clear();
		g_scratch.clear();
		g_scratch_id = 0;
		g_k1r_id     = 0; // exp 0412 (tag k1r412)
		zskip_disable("device reopen"); // experiment 0379
		g_bytes_mapped = 0;
		g_last_sync_ns = 0;
		g_as415_walk_valid = false; // experiment 0415 (as415): the mappings are gone, the next walk must run
		for (auto& S: g_d) {
			S.bos.clear();
			S.maps.clear();
			S.views_sig  = 0;
			S.bos_mapped = 0;
			S.bytes      = 0;
			S.blocks     = ~0ull;
			S.merge_failed.clear();
			// Experiment 0038: S.reported is kept, so the re-import after the reopen is not taken
			// for growth: the breakdown it triggered walked 11,500 views with SEEK_DATA while
			// holding the device lock, and the title's render thread waited on it for a minute.
			S.sync_ns  = 0;
		}
		g_layout_gen++;
		LOGF_COLOR(Log::Color::Yellow, "[bc5-direct] device reopened after the fault: %s\n", g_dev ? "ok" : "FAILED");
		journal("reopen: %s\n", g_dev ? "ok" : "FAILED");
		m11_after_reopen(static_cast<bool>(g_dev)); // exp 0401 e11 (tag m11): BC5_DIRECT_RESET_LABELS, BC5_DIRECT_RESET_LABEL_JOURNAL
	}

// Experiment 0401 series e (BC5_DIRECT_TABLE_CATCHER=1, default off; F403 sub-class B, exp 0402 item 4): the submit-time
// table catcher. The idea is sharpemu 11506fc's (src/SharpEmu.Libs/Agc/AgcExports.Submissions.cs, CaptureSubmittedTables,
// GPL-2.0-or-later: titles rewrite their tables soon after submit); no code is taken from it. At submit, submit_now's walk
// hashes the memory each running indirect packet names: the arguments of DRAW_INDIRECT (0x24, 16 bytes), DRAW_INDEX_INDIRECT
// (0x25, 20), DISPATCH_INDIRECT (0x16, 12; both forms, as the walk reads them) and up to 16 records of the multi-draw packets
// (0x2c, 0x38; count and stride where exp 0054 reads them), at the SET_BASE index-1 base the walk tracks; and the (offset,
// value) tables of LOAD_SH/UCONFIG/CONTEXT_REG_INDEX (0x63, 0x64, 0x9f), in the layout timeout_probe's load_pairs reads
// (exp 0160). The argument sizes are the Vulkan indirect command structs radv passes to these packets unchanged
// (TODO(verify) on the console). At the job's completion, and at a fence timeout before timeout_probe, the same memory is
// hashed again (FNV-1a) and each change is journaled with the first five dwords at submit and now. Not walked: buffers
// reached through INDIRECT_BUFFER (IB2s); the other LOAD_*_REG_INDEX format (offset and size) is counted, not hashed.
// A change says the slot was written between submit and completion; it does not say whether the GPU read the old values
// or the new ones.
struct CatchSlot {
	uint64_t addr  = 0;
	uint32_t bytes = 0, at = 0, op = 0;
	uint64_t hash  = 0;
	uint32_t v[5]  = {};
};
static bool table_catcher_on() {
	static const bool        on = bc5::env_on(BC5_DIAG_ENV("BC5_DIRECT_TABLE_CATCHER"));
	static std::atomic<bool> told {false};
	if (!told.exchange(true))
		journal("exp 0401: table catcher %s\n", on ? "on (indirect arguments and LOAD_*_REG_INDEX tables hashed at submit, compared at completion and at a timeout)" : "off");
	return on;
}
static std::atomic<uint64_t> g_catch_bufs {0}, g_catch_slots {0}, g_catch_changed {0}, g_catch_gone {0}, g_catch_skipped {0};
static uint64_t catch_hash(uint64_t a, uint32_t bytes) {
	const auto* t = reinterpret_cast<const volatile uint32_t*>(a);
	uint64_t    h = 0xcbf29ce484222325ull; // FNV-1a, 64 bits, a dword at a time
	for (uint32_t k = 0; k < bytes / 4; k++) {
		h ^= t[k];
		h *= 0x100000001b3ull;
	}
	return h;
}
static void catch_add(std::vector<CatchSlot>& out, const std::vector<bc5::direct::Mapping>& maps, uint32_t op, uint32_t at, uint64_t a, uint32_t bytes) {
	bytes &= ~3u;
	if (out.size() >= 256 || a == 0 || bytes < 4 || bytes > 65536 || !covered_sorted(maps, a, bytes)) {
		g_catch_skipped++;
		return;
	}
	CatchSlot s;
	s.addr       = a;
	s.bytes      = bytes;
	s.at         = at;
	s.op         = op;
	s.hash       = catch_hash(a, bytes);
	const auto* t = reinterpret_cast<const volatile uint32_t*>(a);
	for (uint32_t k = 0; k < 5 && k < bytes / 4; k++) s.v[k] = t[k];
	out.push_back(s);
	g_catch_slots++;
}
static void catch_check(const std::vector<CatchSlot>& slots, bool at_timeout, uint64_t n, const char* kind) {
	if (slots.empty() || !g_dev) return;
	std::shared_ptr<const std::vector<bc5::direct::Mapping>> maps_p = g_dev->sorted_mappings();
	uint32_t changed = 0;
	for (const CatchSlot& s: slots) {
		if (!covered_sorted(*maps_p, s.addr, s.bytes)) {
			g_catch_gone++;
			continue;
		}
		if (catch_hash(s.addr, s.bytes) == s.hash) continue;
		changed++;
		const uint64_t k = g_catch_changed++;
		if (at_timeout ? changed <= 64 : (k < 64 || (k & 0x3ffu) == 0)) {
			const auto* t    = reinterpret_cast<const volatile uint32_t*>(s.addr);
			uint32_t    v[5] = {};
			for (uint32_t i = 0; i < 5 && i < s.bytes / 4; i++) v[i] = t[i];
			journal("table catcher (exp 0401): at %s, submit #%" PRIu64 " %s op %02x at %u: 0x%" PRIx64 " %u bytes changed since submit: was %08x %08x %08x %08x %08x, now %08x %08x %08x %08x %08x (%" PRIu64 " changes so far)\n",
			        at_timeout ? "the timeout" : "completion", n, kind, s.op, s.at, s.addr, s.bytes, s.v[0], s.v[1], s.v[2], s.v[3], s.v[4], v[0], v[1], v[2], v[3], v[4], k + 1);
		}
	}
	if (at_timeout) journal("table catcher (exp 0401): at the timeout, submit #%" PRIu64 " %s: %zu slots hashed at submit, %u changed\n", n, kind, slots.size(), changed);
	static std::atomic<uint64_t> n_checks {0};
	if ((n_checks++ & 0xffffu) == 0)
		journal("table catcher (exp 0401): %" PRIu64 " buffers, %" PRIu64 " slots hashed, %" PRIu64 " changed, %" PRIu64 " unmapped at the check, %" PRIu64 " not hashed\n", g_catch_bufs.load(),
		        g_catch_slots.load(), g_catch_changed.load(), g_catch_gone.load(), g_catch_skipped.load());
}

// ---- experiment 0404 (in exp 0401's unit): fast-launch draw crumbs and skip, the pure part ------------------------------
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

// ---- exp 0401 series e7 (tag flx): F1/F2 flushes and the A1/A4/A5 catchers, the pure part ----------------------------
// mkflx0401.py adds this and the edits marked "flx" to exp 0404's pure part (flx0401-notes.md; CPU test flx0401.cpp through
// the seams bc5_flx0401_*). Five switches, each off by default and read once (bc5::env_on: unset, empty and "0" are off;
// with all five unset this is exp 0404's path exactly):
//   BC5_DIRECT_FL_PROBE_STATE=1                    A1 catcher, CPU at a fence timeout: fl_probe also prints kFlx*'s registers
//                                                  as fl_scan tracked them at the first draw issued and not done and at the
//                                                  last done one, and the ring entry of the next draw with crumbs
//   (BC5_DIRECT_FL_VGT_FLUSH, option removed by exp 0419) F1 fix candidate: EVENT_WRITE VS_PARTIAL_FLUSH, then EVENT_WRITE VGT_FLUSH:
//                                                  at the head of every host prefix of a dcb (prefix), before a fast-launch
//                                                  draw whose last work before it may be other work (transition: a draw that
//                                                  is not fast-launch, a dispatch, or not known), or before every fast-launch
//                                                  draw (all)
//   (BC5_DIRECT_FL_SERIAL, option removed by exp 0419) F2 fix candidate: EVENT_WRITE VS_PARTIAL_FLUSH after every fast-launch draw:
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
static bool flx_mesh_point(int pat, const uint32_t* ud, uint32_t v6, uint32_t point, const Read& read, FlxMeshPoint& m, bool raw = false) { // + exp 0401 e8 (smp): raw, range model 1
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
			if (!raw) return; // exp 0401 e8 (smp) model 1: read past NUM_RECORDS all the same
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
			if (!raw) return; // exp 0401 e8 (smp) model 1: read past NUM_RECORDS all the same
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
static FlxMeshCounts flx_mesh_counts(int pat, const uint32_t* ud, uint32_t v6, uint32_t points, uint32_t cap, const Read& read, bool raw = false) { // + exp 0401 e8 (smp)
	FlxMeshCounts c;
	c.points = std::min(points, cap);
	for (uint32_t i = 0; i < c.points; i++) {
		FlxMeshPoint m;
		if (!flx_mesh_point(pat, ud, v6, i, read, m, raw)) {
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

struct FlState { // the GFX context's tracked registers, carried from buffer to buffer
	FlVal              stages, es_lo, es_hi, base1;
	FlVal              ud[6];
	std::vector<FlVal> stack; // VGT_SHADER_STAGES_EN as CLEAR_STATE cmd 1 pushed it (full_state's stack, 8 deep)
	FlVal                           last;   // exp 0401 e7 (flx): the GFX ring's last draw or dispatch: 1 fast-launch, 0 other work
	std::vector<FlVal>              x;      // exp 0401 e7 (flx): kFlx*'s registers, kFlxN once A1, A4 or A5 is on (else empty)
	std::vector<std::vector<FlVal>> xstack; // exp 0401 e7 (flx): x's context registers as CLEAR_STATE cmd 1 pushed them
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
	bool               flush  = false; // exp 0401 e7 (flx) F1: VS_PARTIAL_FLUSH + VGT_FLUSH before it (before its crumbs)
	bool               serial = false; // exp 0401 e7 (flx) F2: VS_PARTIAL_FLUSH after it (after its done crumb)
	uint32_t           vcount = 0;     // exp 0401 e7 (flx) A4: a DRAW_INDEX_AUTO's count, from its packet
	int32_t            ml     = 0;     // exp 0401 e7 (flx) A5: the pattern whose object record and headers base[] holds (0: V# bases)
	FlxMeshPoint       mp0;            // exp 0401 e7 (flx) A5: point 0's control path as the CPU followed it at submit
	std::vector<FlVal> x;              // exp 0401 e7 (flx) A1, A4: kFlx*'s registers at the draw (empty unless tracked)
};
struct FlPlan {
	std::vector<FlDraw> draws;        // the draws with crumbs or dropped, in buffer order
	bool     crumbs = false;          // BC5_DIRECT_FL_CRUMBS planned this buffer
	FlLayout lay;
	uint64_t submit = 0;
	uint32_t total = 0, host_dropped = 0, not_fl = 0, fl = 0, maybe = 0, unknown = 0; // the draws of a dcb, by class
	uint32_t skipped = 0, planned = 0, with_crumbs = 0, cond_full = 0, ib2 = 0, unread = 0;
	std::vector<uint32_t> heads;                                                     // exp 0401 e7 (flx) F1 prefix: the host prefixes' heads (sorted)
	bool                  inserts = false;                                           // exp 0401 e7 (flx): F1 or F2 has something to lay
	uint32_t              flushes = 0, serials = 0, heads_laid = 0, ml = 0, ml_failed = 0; // exp 0401 e7 (flx): laid; A5 planned, not followed
};
struct FlOptions {
	bool                         draws   = false;   // a dcb: plan its draws (otherwise only the state is followed)
	bool                         crumbs  = false;   // plan crumbs for them
	const std::vector<uint32_t>* skip_es = nullptr; // sorted SPI_SHADER_PGM_LO_ES values (BC5_DIRECT_FL_SKIP_ES)
	const std::vector<uint32_t>* drops   = nullptr; // sorted offsets the caller drops already: not planned
	int                          flush   = 0;       // exp 0401 e7 (flx) F1: 0 off, 1 prefix (the caller's heads), 2 transition, 3 all
	bool                         serial  = false;   // exp 0401 e7 (flx) F2
	bool                         state   = false;   // exp 0401 e7 (flx) A1, A4, A5: track kFlx*'s registers
	bool                         ml      = false;   // exp 0401 e7 (flx) A5: a crumbed pattern draw copies its object record and headers
};
// exp 0401 e7 (flx) A5: the crumbs' three 32-byte copies of a pattern draw take point 0's object record (+0x00, +0x20) and
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
	if (o.state && st.x.size() != kFlxN) { // exp 0401 e7 (flx): kFlx*'s registers are tracked from here on, unknown at first
		st.x.assign(kFlxN, FlVal {});
		st.xstack.clear();
	}
	const auto addr = [](uint32_t lo, uint32_t hi) {
		return (static_cast<uint64_t>(lo) & ~3ull) | (static_cast<uint64_t>(hi & 0xffffu) << 32u);
	};
	const auto forget_sh = [&st] {
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
				ran = false; // flx
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
	uint32_t              made   = 0, laid = 0; // + exp 0401 e7 (flx): laid counts F1's and F2's packet groups
	bool                  fitted = false;
	for (int attempt = 0; attempt < 64 && !fitted; attempt++) {
		out.clear();
		unit_at.assign(n + 1u, ~0u);
		old_to_new.assign(n + 1u, ~0u);
		made          = 0;
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
				d->entry = made++ % plan.lay.entries;
				d->id    = (static_cast<uint64_t>(q) << 32u) | static_cast<uint32_t>(submit);
				fl_pre(*d, plan.lay, out);
			}
			old_to_new[q] = static_cast<uint32_t>(out.size());
			if (d != nullptr) d->new_at = old_to_new[q];
			out.insert(out.end(), ib + q, ib + q + len);
			if (with) fl_post(*d, plan.lay, out);
			if (d != nullptr && d->serial) { // flx F2: after the draw's done crumb
				fl_vs_flush(out);
				plan.serials++;
				laid++;
			}
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
			if (inside && (d.crumbs || d.flush || d.serial)) { // + flx: its F1 and F2 packets with its crumbs
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
	new_to_old.assign(out.size(), ~0u);
	for (uint32_t q = 0; q < n; q++) {
		if (old_to_new[q] != ~0u) new_to_old[old_to_new[q]] = q;
	}
	plan.with_crumbs = made;
	return made + laid; // flx: laid is 0 without F1 and F2
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
// ---- exp 0401 series e7 (tag flx): the late pure block (after fl_find and fl_entry_check) ------------------------------
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
// ---- exp 0401 series e8 (tag smp): BC5_DIRECT_FL_MESHLET_SAMPLE, the pure part --------------------------------------------
// hang1954-0401.md "r7all 06:40 (e7 catchers)": A4's readings of the hung draws (point 0 past an 8-entry object list, the
// empty record, headers above the programmed limit of 32) were also seen at submit in completed draws, but no completed
// draw was ever walked per point. smp walks completed draws, and the draws of a timeout again, in two range models: model
// 0 takes a load past NUM_RECORDS as 0 (A4's reading), model 1 reads the memory there all the same. TODO(verify) which
// one the hardware does (hang1954-0401.md: the gfx10 V# OOB_SELECT question).
constexpr uint32_t kSmpCap   = 1024; // points walked per draw and model
constexpr uint32_t kSmpDraws = 64;   // pattern draws walked per sample
static int smp_parse(const char* e, bool* bad) { // whole seconds 1-3600; unset, empty, "0" or "off": 0 (off); anything else: 0, bad
	*bad = false;
	if (e == nullptr || *e == '\0' || std::strcmp(e, "0") == 0 || std::strcmp(e, "off") == 0) return 0;
	char*      end = nullptr;
	const long v   = std::strtol(e, &end, 10);
	if (end == e || *end != '\0' || v < 1 || v > 3600) {
		*bad = true;
		return 0;
	}
	return static_cast<int>(v);
}
static bool smp_due(int64_t now_ms, int64_t& next_ms, int period_s) { // due once now reaches next; then next is a period on
	if (period_s <= 0 || now_ms < next_ms) return false;
	next_ms = now_ms + static_cast<int64_t>(period_s) * 1000;
	return true;
}
static std::string smp_counts(const FlxMeshCounts& c) {
	char t[512];
	std::snprintf(t, sizeof(t),
				  "%u followed of %u (%u not readable), %u by the index path, record flag bit 6 clear %u, meshlet index >= count %u (first %d), headers up to %u vertices "
				  "and %u primitives, above 32 vertices %u, above 64 primitives %u, loads past NUM_RECORDS %u",
				  c.followed, c.points, c.unread, c.index_path, c.flag6, c.index, c.first_index, c.max_v, c.max_p, c.over_v, c.over_p, c.oob);
	return t;
}
static std::string smp_point(const FlxMeshPoint& m) {
	char t[384];
	std::snprintf(t, sizeof(t), "object %u, record index %u at 0x%" PRIx64 " (flags %08x, meshlet count %u, header base %08x), meshlet %u, header %08x (%u vertices, %u primitives), %u loads past NUM_RECORDS%s",
				  m.object, m.rindex, m.rec, m.flags, m.count, m.hbase, m.meshlet, m.header, ((m.header >> 17u) & 0x7fu) + 1u, (m.header >> 24u) + 1u, m.oob, m.ok ? "" : " (a read was refused)");
	return t;
}
// One draw: 0 not a pattern draw (its ES), 1 the user data it reads not known for certain, 2 no readable arguments, 3
// walked. line: the journal line (not for 0). read(address, bytes): the memory, or nullptr.
template <class Read>
static int smp_text(const FlDraw& d, const Read& read, const char* tag, uint64_t n, const char* kind, std::string& line) {
	if (d.es_lo.n != 1 || flx_pattern(d.es_lo.v[0]) == 0) return 0;
	const int pat = flx_pattern(d.es_lo.v[0]);
	char      where[200];
	std::snprintf(where, sizeof(where), "fl meshlet sample (exp 0401 e8 smp): %s: submit #%" PRIu64 " %s op %02x at %u: ES %08x (pattern %d)", tag, n, kind, d.op, d.at,
				  static_cast<uint32_t>(d.es_lo.v[0]), pat);
	uint32_t ud[32] = {}, v6 = 0;
	if (!flx_user_data(d.x, pat, ud)) {
		line = std::string(where) + ": the user data it reads were not known for certain at the draw: not walked";
		return 1;
	}
	const int   v6_from = flx_v6(d.x, v6);
	uint32_t    points = 0, inst = 0;
	const char* from   = nullptr;
	if (d.op == 0x2d) {
		points = d.vcount;
		inst   = 1;
		from   = "the packet";
	} else if (d.args != 0) {
		if (const uint32_t* t = read(d.args, 8); t != nullptr) {
			points = t[0];
			inst   = t[1];
			from   = "memory now";
		}
	}
	if (from == nullptr) {
		line = std::string(where) + ": no readable arguments to count its points: not walked";
		return 2;
	}
	const FlxMeshCounts c0 = flx_mesh_counts(pat, ud, v6, points, kSmpCap, read, false);
	const FlxMeshCounts c1 = flx_mesh_counts(pat, ud, v6, points, kSmpCap, read, true);
	FlxMeshPoint        m0, m1;
	flx_mesh_point(pat, ud, v6, 0, read, m0, false);
	flx_mesh_point(pat, ud, v6, 0, read, m1, true);
	static const char* const v6s[3] = {"GE_USER_VGPR1", "GE_USER_VGPR_EN bit 0 clear", "assumed: GE_USER_VGPR_EN or GE_USER_VGPR1 not known"};
	char                     head[200];
	std::snprintf(head, sizeof(head), ": %u x %u points (from %s)%s, v6 %08x (%s)", points, inst, from, points > kSmpCap ? ", walked up to the cap" : "", v6,
				  v6s[v6_from < 0 || v6_from > 2 ? 2 : v6_from]);
	line = std::string(where) + head + "; model 0 (past NUM_RECORDS read as 0): " + smp_counts(c0) + "; model 1 (past NUM_RECORDS read as the memory there): " + smp_counts(c1) +
		   "; point 0, model 0: " + smp_point(m0) + "; point 0, model 1: " + smp_point(m1);
	return 3;
}
// ---- end of exp 0401 series e8's (tag smp) pure block ------------------------------------------------------------------
// ---- end of experiment 0404's pure part -----------------------------------------------------------------------------
// ---- experiment 0404: the switches and the host's side ------------------------------------------------------------------
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
		const bool v = bc5::env_on(BC5_DIAG_ENV("BC5_DIRECT_FL_CRUMBS"));
		journal("exp 0404: fl crumbs %s\n", v ? "on (the fast-launch draws of each dcb: issued/done crumbs and their inputs copied by the CP into the GDS shadow +0x8000; read at a fence timeout)" : "off");
		return v;
	}();
	return on;
}
static const std::vector<uint32_t>& fl_skip_es() {
	static const std::vector<uint32_t> list = [] {
		std::vector<uint32_t> v;
		const char*           e = nullptr; /* exp 0419: option removed */
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
// ---- exp 0401 series e8 (tag smp): the switch ------------------------------------------------------------------------------
static int smp_period() { // BC5_DIRECT_FL_MESHLET_SAMPLE: the seconds between two samples, 0 off; read once
	static const int p = [] {
		bool       bad    = false;
		const int  v      = smp_parse(nullptr, &bad) /* exp 0419: option removed */;
		const bool crumbs = fl_crumbs_on();
		char       line[400];
		if (v > 0)
			std::snprintf(line, sizeof(line), "exp 0401 e8 (smp): fl meshlet sample every %d s, at most %u pattern draws of a completed job, %u points per draw and range model%s", v,
						  kSmpDraws, kSmpCap, crumbs ? "" : " (needs BC5_DIRECT_FL_CRUMBS=1: nothing without it)");
		else
			std::snprintf(line, sizeof(line), "exp 0401 e8 (smp): fl meshlet sample off%s", bad ? " (BC5_DIRECT_FL_MESHLET_SAMPLE does not parse: whole seconds 1-3600, 0 or off)" : "");
		journal("%s\n", line);
		std::fprintf(stderr, "[bc5] %s\n", line);
		return v;
	}();
	return p;
}
// ---- exp 0401 series e7 (tag flx): the switches and the host's side of F1, F2, A1, A4 and A5 -----------------------------
struct FlxSwitches {
	bool probe_state = false, serial = false, meshlet_probe = false, crumbs_meshlet = false;
	int  flush       = 0; // F1: 0 off, 1 prefix, 2 transition, 3 all
};
static const FlxSwitches& flx_switches() {
	static const FlxSwitches s = [] {
		FlxSwitches v;
		v.probe_state    = bc5::env_on(BC5_DIAG_ENV("BC5_DIRECT_FL_PROBE_STATE"));
		v.serial         = false; /* exp 0419: option removed */
		v.meshlet_probe  = bc5::env_on(BC5_DIAG_ENV("BC5_DIRECT_FL_MESHLET_PROBE"));
		v.crumbs_meshlet = bc5::env_on(BC5_DIAG_ENV("BC5_DIRECT_FL_CRUMBS_MESHLET"));
		v.flush          = 0; /* exp 0419: option removed */
		const bool               crumbs = fl_crumbs_on();
		static const char* const arm[4] = {"off", "prefix", "transition", "all"};
		const char* const        need   = " (needs BC5_DIRECT_FL_CRUMBS=1: nothing without it)";
		char                     line[700];
		std::snprintf(line, sizeof(line), "exp 0401 e7 (flx): fl probe state %s%s, fl vgt flush %s%s, fl serial %s, fl meshlet probe %s%s, fl crumbs meshlet %s%s",
					  v.probe_state ? "on" : "off", v.probe_state && !crumbs ? need : "", arm[v.flush], "",
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
	if ((!flx_switches().probe_state && smp_period() == 0) || !plan.crumbs) return; // + exp 0401 e8 (smp): kept for its timeout walk too
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
// ---- exp 0401 series e8 (tag smp): the host's side ----------------------------------------------------------------------
static std::atomic<int64_t>  g_smp_next {0};
static std::atomic<uint64_t> g_smp_samples {0};
static bool smp_take(int period) { // the sample timer: true for one caller once a period
	const int64_t now  = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now().time_since_epoch()).count();
	int64_t       next = g_smp_next.load();
	for (;;) {
		int64_t want = next;
		if (!smp_due(now, want, period)) return false;
		if (g_smp_next.compare_exchange_weak(next, want)) return true;
	}
}
// One draw through the host's mapping of guest memory (covered_sorted), read now; its line in the journal.
static void smp_walk(const FlDraw& d, const std::vector<bc5::direct::Mapping>& maps, const char* tag, uint64_t n, const char* kind) {
	const auto reader = [&maps](uint64_t a, uint64_t bytes) -> const uint32_t* {
		return covered_sorted(maps, a, bytes) ? reinterpret_cast<const uint32_t*>(a) : nullptr;
	};
	std::string line;
	if (smp_text(d, reader, tag, n, kind, line) != 0) journal("%s\n", line.c_str());
}
// A job with crumbs completed (submit_now's sync path, the completion thread): at most once every N s, its pattern draws
// (at most kSmpDraws), walked per point at once, a few ms after its fence, in both range models.
static void smp_sample(const FlPlan& plan, uint64_t n, const char* kind, bool same_device) {
	const int period = smp_period();
	if (period == 0 || !plan.crumbs || !same_device || !g_dev) return;
	uint32_t pattern = 0;
	for (const FlDraw& d: plan.draws) pattern += d.es_lo.n == 1 && flx_pattern(d.es_lo.v[0]) != 0 ? 1u : 0u;
	if (pattern == 0 || !smp_take(period)) return;
	const auto     maps_p = g_dev->sorted_mappings();
	const uint64_t s      = g_smp_samples++;
	char           tag[64];
	std::snprintf(tag, sizeof(tag), "sample %" PRIu64 ", completed", s + 1);
	uint32_t walked = 0;
	for (const FlDraw& d: plan.draws) {
		if (walked >= kSmpDraws) break;
		if (d.es_lo.n != 1 || flx_pattern(d.es_lo.v[0]) == 0) continue;
		smp_walk(d, *maps_p, tag, n, kind);
		walked++;
	}
	journal("fl meshlet sample (exp 0401 e8 smp): sample %" PRIu64 ": submit #%" PRIu64 " %s completed: %u pattern draws of %zu planned, %u walked\n", s + 1, n, kind, pattern,
			plan.draws.size(), walked);
}
// At a fence timeout (fl_probe, the draws issued and not done): the last done draw (this buffer's, or the one fl_keep_done
// kept) and every draw issued and not done, in both range models, read now.
static void smp_at_timeout(const FlPlan& plan, const FlFind& f, uint64_t done, uint64_t n, const char* kind, const std::vector<bc5::direct::Mapping>& maps) {
	if (f.done >= 0) {
		smp_walk(plan.draws[static_cast<std::size_t>(f.done)], maps, "at the timeout, the last done of this buffer", n, kind);
	} else {
		FlDraw   kd;
		uint64_t kn = 0;
		if (flx_kept(done, kd, kn)) smp_walk(kd, maps, "at the timeout, the last done (of the job that completed last)", kn, "-");
		else journal("fl meshlet sample (exp 0401 e8 smp): at the timeout of submit #%" PRIu64 " %s: the last done draw was not kept: not walked\n", n, kind);
	}
	uint32_t lines = 0;
	for (int k = f.first; k >= 0 && k <= f.last && lines < 64; k++) {
		const FlDraw& d = plan.draws[static_cast<std::size_t>(k)];
		if (!d.crumbs) continue;
		smp_walk(d, maps, "at the timeout, issued and not done", n, kind);
		lines++;
	}
}
// ---- end of exp 0401 series e8's (tag smp) host block ------------------------------------------------------------------
// submit_now, after its walk and before the filter: follows the state through the buffer (every GFX-class buffer of the
// GFX ring), plans the draws of a dcb, and adds the ES skip's drops (offsets in ib).
static void fl_plan_buffer(const uint32_t* ib, uint32_t n, const char* kind, int ring, const Chain* chain, const std::vector<bc5::direct::Mapping>& maps,
						   std::vector<uint32_t>& drop_offsets, FlPlan& plan) {
	const bool                   crumbs = fl_crumbs_on();
	const std::vector<uint32_t>& skip   = fl_skip_es();
	const FlxSwitches&           sw     = flx_switches(); // exp 0401 e7 (flx)
	if (!crumbs && skip.empty() && sw.flush == 0 && !sw.serial) return;
	if (std::strncmp(kind, "acb", 3) == 0 && ring != bc5::direct::kGfxRing) return; // a compute ring's own context
	FlOptions      o;
	const uint64_t area = fl_crumbs_area();
	o.draws             = std::strncmp(kind, "dcb", 3) == 0;
	o.crumbs            = crumbs && o.draws && area != 0;
	o.skip_es           = &skip;
	o.flush             = o.draws ? sw.flush : 0;                                              // flx F1 (prefix: the heads below)
	o.serial            = o.draws && sw.serial;                                                // flx F2
	o.state             = crumbs && (sw.probe_state || sw.meshlet_probe || sw.crumbs_meshlet || smp_period() > 0); // flx A1, A4, A5; exp 0401 e8 (smp)
	o.ml                = o.crumbs && sw.crumbs_meshlet;                                       // flx A5
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
	if (o.flush == 1) { // flx F1 prefix: the heads of the host prefixes (flx_heads)
		std::vector<std::pair<uint32_t, uint32_t>> segs;
		if (chain != nullptr) {
			for (const ChainSeg& s: chain->segs) segs.emplace_back(s.off, s.prefix);
		}
		plan.heads = flx_heads(segs, chain != nullptr, std::strcmp(kind, "dcb") == 0, n);
	}
	for (const FlDraw& d: plan.draws) plan.inserts = plan.inserts || d.flush || d.serial; // flx
	plan.inserts = plan.inserts || !plan.heads.empty();
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
	if ((!plan.crumbs || plan.planned == 0) && !plan.inserts) return; // + exp 0401 e7 (flx): F1 and F2 lay theirs without crumbs
	if (mec_rebuilt) { // a compute buffer's rebuild: never a dcb's; counted, no crumbs
		for (FlDraw& d: plan.draws) d.crumbs = d.flush = d.serial = false; // + flx
		plan.heads.clear();                                               // flx
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
	flx_note(plan, submit, kind);      // exp 0401 e7 (flx): F1's and F2's packets counted
	if (plan.with_crumbs == 0) return; // flx: F1 or F2 without crumbs
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
			journal("fl crumbs (exp 0404): submit #%" PRIu64 " %s op %02x at %u (+%u in the copy), entry %u: stages %s es %s, arguments 0x%" PRIx64 ", V# bases 0x%" PRIx64 " 0x%" PRIx64 " 0x%" PRIx64 "%s (%" PRIu64 " draws so far)\n",
					submit, kind, d.op, d.at, d.new_at, d.entry, sg, es, d.args, d.base[0], d.base[1], d.base[2], d.ml != 0 ? " (flx A5: the object record +0x00, +0x20 and the meshlet headers instead)" : "", k + 1);
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
	const FlxSwitches& sw     = flx_switches(); // exp 0401 e7 (flx)
	const auto         maps_p = g_dev->sorted_mappings();
	const auto         entry  = [&](const FlDraw& d, uint32_t* e) { // flx: the draw's ring entry as the CP left it, and its state
		const volatile uint32_t* ev = sh + (plan.lay.ring - plan.lay.shadow) / 4u + static_cast<std::size_t>(d.entry) * (kFlEntryBytes / 4u);
		for (uint32_t k = 0; k < 32; k++) e[k] = ev[k];
		return fl_entry_check(e, d.id);
	};
	const auto show = [&](const FlDraw& d, const char* tag, bool with_data, bool regs) { // + flx: regs, A1's registers
		uint32_t                 e[32];
		const int                st       = entry(d, e);
		static const char* const state[4] = {"complete", "begun, not finished (the CP stopped inside its copies)", "overwritten by another draw (the ring wrapped)", "never written"};
		char                     sg[40], el[40], eh[40];
		fl_fmt(d.stages, sg, sizeof(sg));
		fl_fmt(d.es_lo, el, sizeof(el));
		fl_fmt(d.es_hi, eh, sizeof(eh));
		journal("fl crumbs (exp 0404):   %s: op %02x at %u (chain segment %d +%u; +%u in the copy), entry %u %s (head #%u +%u): stages %s, es hi %s lo %s, %u COND_EXEC ranges open\n", tag, d.op, d.at, d.seg, d.seg_at,
				d.new_at, d.entry, state[st], e[0], e[1], sg, eh, el, d.cond);
		if (regs && sw.probe_state) flx_probe_state(d);        // flx A1
		if (d.ml != 0 && (with_data || regs)) flx_probe_ml(d); // flx A5
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
		if (smp_period() > 0) smp_at_timeout(plan, f, done, n, kind, *maps_p); // exp 0401 e8 (smp): both range models
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
	if (g_journal_min) {
		if (FILE* jf = journal_min_file(true); jf != nullptr) fsync(fileno(jf));
	}
}

// ---- exp 0401 series e7 (tag flx): the CPU test's seams (flx0401.cpp); always compiled in, never called by the emulator ----
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
// ---- exp 0401 series e8 (tag smp): the CPU test's seams (smp0401.cpp); always compiled in, never called by the emulator ----
extern "C" int bc5_smp0401_parse(const char* e, int* bad) {
	bool      b = false;
	const int v = smp_parse(e, &b);
	*bad        = b ? 1 : 0;
	return v;
}
extern "C" int bc5_smp0401_period() { // the unit's reading of the switch
	return smp_period();
}
extern "C" int bc5_smp0401_due(int64_t now_ms, int64_t* next_ms, int period) {
	return smp_due(now_ms, *next_ms, period) ? 1 : 0;
}
extern "C" int bc5_smp0401_take(int period) { // the real timer (the unit's own, global)
	return smp_take(period) ? 1 : 0;
}
extern "C" void bc5_smp0401_consts(uint32_t* out) { // kSmpCap, kSmpDraws, kFlxMeshCap
	out[0] = kSmpCap;
	out[1] = kSmpDraws;
	out[2] = kFlxMeshCap;
}
extern "C" int bc5_smp0401_mesh(uint32_t es, const uint32_t* ud, uint32_t v6, uint32_t points, uint32_t cap, int raw, FlxReadFn read, void* ctx, int32_t* out) { // as bc5_flx0401_mesh, a model
	const auto          reader = [read, ctx](uint64_t a, uint64_t bytes) { return read(a, bytes, ctx); };
	const int           pat    = flx_pattern(es);
	const FlxMeshCounts c      = flx_mesh_counts(pat, ud, v6, points, cap, reader, raw != 0);
	const int32_t       v[14]  = {static_cast<int32_t>(c.points), static_cast<int32_t>(c.followed), static_cast<int32_t>(c.unread), static_cast<int32_t>(c.index_path),
								  static_cast<int32_t>(c.flag6), static_cast<int32_t>(c.index), static_cast<int32_t>(c.over_v), static_cast<int32_t>(c.over_p),
								  static_cast<int32_t>(c.max_v), static_cast<int32_t>(c.max_p), static_cast<int32_t>(c.oob), c.first_flag6, c.first_index, c.first_over};
	for (uint32_t k = 0; k < 14; k++) out[k] = v[k];
	return pat;
}
extern "C" int bc5_smp0401_point(uint32_t es, const uint32_t* ud, uint32_t v6, uint32_t point, int raw, FlxReadFn read, void* ctx, uint64_t* out) { // as bc5_flx0401_mesh_point, a model
	const auto     reader = [read, ctx](uint64_t a, uint64_t bytes) { return read(a, bytes, ctx); };
	FlxMeshPoint   m;
	const bool     ok   = flx_mesh_point(flx_pattern(es), ud, v6, point, reader, m, raw != 0);
	const uint64_t v[13] = {m.ok ? 1u : 0u, m.rec_ok ? 1u : 0u, m.path, m.object, m.rindex, m.meshlet, m.flags, m.count, m.hbase, m.header, m.rec, m.hdr, m.oob};
	for (uint32_t i = 0; i < 13; i++) out[i] = v[i];
	return ok ? 1 : 0;
}
// smp_text on a draw of the test's own: x as flx's seams give it (n, v0, v1 per index), es lo, op, at, args, vcount
extern "C" int bc5_smp0401_text(const uint32_t* ns, const uint32_t* v0, const uint32_t* v1, uint32_t count, uint32_t es, uint32_t op, uint32_t at, uint64_t args, uint32_t vcount,
								FlxReadFn read, void* ctx, char* out, uint32_t cap) {
	FlDraw d;
	d.x          = flx_seam_vals(ns, v0, v1, count);
	d.es_lo.n    = 1;
	d.es_lo.v[0] = es;
	d.op         = op;
	d.at         = at;
	d.args       = args;
	d.vcount     = vcount;
	const auto  reader = [read, ctx](uint64_t a, uint64_t bytes) { return read(a, bytes, ctx); };
	std::string line;
	const int   r = smp_text(d, reader, "test", 7, "dcb", line);
	std::snprintf(out, cap, "%s", line.c_str());
	return r;
}
// the real fl_plan_buffer on a buffer of the test's own (GFX ring, no chain, no mapping): info [3]: draws planned, the size
// of draw 0's tracked state (x), the plan's crumbs
extern "C" uint32_t bc5_smp0401_plan_x(const uint32_t* ib, uint32_t n, const char* kind, uint32_t* info) {
	FlPlan                                  plan;
	std::vector<uint32_t>                   drops;
	const std::vector<bc5::direct::Mapping> none;
	fl_plan_buffer(ib, n, kind, bc5::direct::kGfxRing, nullptr, none, drops, plan);
	info[0] = static_cast<uint32_t>(plan.draws.size());
	info[1] = plan.draws.empty() ? 0u : static_cast<uint32_t>(plan.draws[0].x.size());
	info[2] = plan.crumbs ? 1u : 0u;
	return info[0];
}
// the real smp_sample on a plan of the test's own (no device: it never walks); returns the samples taken so far
extern "C" uint64_t bc5_smp0401_sample(int crumbs, uint32_t es) {
	FlPlan p;
	p.crumbs = crumbs != 0;
	FlDraw d;
	d.es_lo.n    = 1;
	d.es_lo.v[0] = es;
	p.draws.push_back(d);
	smp_sample(p, 9, "dcb", true);
	return g_smp_samples.load();
}
// ---- end of exp 0401 series e8's (tag smp) seams ----------------------------------------------------------------------

// ---- experiment 0024: jobs in flight ---------------------------------------------------------
struct PendingJob {
	uint64_t                 n          = 0;
	const char*              kind       = "";
	uint32_t                 num_dwords = 0;
	const void*              ib         = nullptr;
	bc5::policy::FilterStats filter;
	size_t                   maps       = 0;
	double                   prepare_ms = 0, list_ms = 0, cs_ms = 0;
	uint32_t                 bo_count   = 0;
	bool                     short_list = false, retried = false;
	uint64_t                 seq = 0, t2_ns = 0, queued_ns = 0, dev_gen = 0;
	uint64_t                 fs_sub_ns = 0, fs_ask_ns = 0, fs_got_ns = 0; // experiment 0415 (fs415b): submit_now entered, the device mutex asked, got
	uint64_t                 fs_open_ns = 0, fs_part_ns[6] = {};          // experiment 0415 (fs415c): the chain's first segment; the ends of probe, anon sync, direct sync, learned, hints, pre-device
	int                      fs_why = -1;
	uint32_t                 fs_segs = 0;
	uint64_t                 fs_ds[8] = {}; // experiment 0415 (fs415d): t_fs415_ds at the end of the direct sync
	uint32_t                 slot = 0;
	std::vector<uint64_t>    ts_addrs; // experiment 0046: GPU timestamps to rescale once the job is done
	std::vector<uint32_t>    ib_copy;  // experiment 0160: the executed buffer, kept for the timeout probe
	std::vector<uint32_t>    ran_copy; // experiment 0160: its executed offsets (what the filter let through)
	std::vector<GeProbeSlot> ge_probe; // experiment 0160: the register captures inserted in front of its draws
	std::vector<CatchSlot>   catch_slots; // experiment 0401 series e: the table catcher's slots
	FlPlan                   fl_plan;     // experiment 0404: the fast-launch draws' crumbs, for fl_probe
};
// Experiment 0160: BC5_DIRECT_TIMEOUT_PROBE=1 — after a fence timeout, the buffer the GPU ran (prefix
// and rewrites included) goes to <dump dir>/ib-timeout-<submission>.bin, and its draw packets are
// journaled with the SET_BASE 1 / INDEX_BASE in force and the memory they name as the GPU left it:
// the indirect arguments (first draws) and the first index dwords.
// Experiment 0260: the dump is synced; each WAIT_REG_MEM(64) of the buffer (offset, label or register, function,
// reference, mask, engine, the label's value now and whether it meets the wait, ran or DROPPED), each label write
// (RELEASE_MEM, EVENT_WRITE_EOP, WRITE_DATA to memory: address, data select, value, the address's value now) and each
// dispatch's program are journaled, 200 lines of each at most, with a count; then the journal is synced. A stuck
// compute buffer then shows what it waits on even when the machine goes down (exp 0259: S6N's was not recorded).
// Experiment 0272 (exp 0265, F332: a compute chain hung inside its dispatches): each dispatch's group counts, from the packet
// or, for DISPATCH_INDIRECT, from memory as the GPU left it; every indirect one is journaled, with the largest grid.
// Experiment 0412 (tags tl412, dc412): dw0412.inc, the dispatches of a command buffer.
namespace dw412 {
inline bool env_on(const char* name) {
	const char* e = std::getenv(name);
	return e != nullptr && e[0] != 0 && !(e[0] == '0' && e[1] == 0);
}
inline bool tl_on() {
	static const bool v = BC5_LEAN_OR(false, env_on("BC5_TIMEOUT_LAYOUT"));
	return v;
}
inline bool dc_on() {
	static const bool v = BC5_LEAN_OR(false, env_on("BC5_DISPATCH_COUNT"));
	return v;
}
struct Dispatch {
	uint32_t at = 0;            // dword offset of the packet
	uint32_t op = 0;            // 0x15 direct, 0x16 indirect
	uint64_t program = 0;       // (COMPUTE_PGM_LO | (HI & 0xff) << 32) << 8
	bool     program_known = false; // both registers were set in this buffer (by SET_SH_REG or a loaded table)
	uint32_t initiator = 0;
	uint32_t gx = 0, gy = 0, gz = 0;
	bool     groups_known = false; // direct only: the indirect form's counts are in memory
	uint64_t args = 0;          // indirect: the address of the counts (0 when the base is not known)
	uint32_t ud[16] = {};
	uint32_t ud_known = 0;      // bit k: COMPUTE_USER_DATA_k was set in this buffer
};
// Total dwords of the packet at ib[i] (never 0), by its header.
inline uint32_t packet_len(uint32_t h) {
	const uint32_t type = h >> 30u, cnt = (h >> 16u) & 0x3fffu;
	if (type == 3) return cnt == 0x3fffu ? 1u : cnt + 2u;
	if (type == 0) return cnt + 2u;
	return 1u;
}
// read_table(address, pairs, out): fills out with 2 * pairs dwords (register, value) and returns true, or returns
// false when the memory cannot be read. on_dispatch(const Dispatch&) for every dispatch, in order.
// A packet that would run past the end stops the walk (returns false); true when the whole buffer was walked.
template <typename R, typename F> inline bool walk(const uint32_t* ib, uint32_t n, R&& read_table, F&& on_dispatch) {
	uint32_t pl = 0, ph = 0;
	bool     pl_known = false, ph_known = false;
	uint32_t ud[16] = {};
	uint32_t ud_known = 0;
	uint64_t base1 = 0;
	std::vector<uint32_t> table;
	auto set = [&](uint32_t reg, uint32_t v) {
		if (reg == 0x20cu) pl = v, pl_known = true;
		else if (reg == 0x20du) ph = v, ph_known = true;
		else if (reg >= 0x240u && reg < 0x250u) ud[reg - 0x240u] = v, ud_known |= 1u << (reg - 0x240u);
	};
	for (uint32_t i = 0; i < n;) {
		const uint32_t h = ib[i], len = packet_len(h);
		if (len > n - i) return false;
		if ((h >> 30u) == 3 && len >= 2) {
			const uint32_t op = (h >> 8u) & 0xffu;
			if (op == 0x76u && len >= 3) {
				const uint32_t reg = ib[i + 1] & 0xffffu;
				for (uint32_t k = 2; k < len; k++) set(reg + (k - 2), ib[i + k]);
			} else if (op == 0x63u && len >= 5 && (ib[i + 3] >> 31u) != 0) {
				const uint64_t ta = (ib[i + 1] & ~3u) | (static_cast<uint64_t>(ib[i + 2] & 0xffffu) << 32u);
				const uint32_t tn = ib[i + 4] & 0x3fffu;
				if (ta != 0 && tn != 0 && tn <= 4096) {
					table.clear();
					if (read_table(ta, tn, table) && table.size() >= 2ull * tn) {
						for (uint32_t k = 0; k < tn; k++) set(table[2 * k] & 0xffffu, table[2 * k + 1]);
					}
				}
			} else if (op == 0x11u && len >= 4 && (ib[i + 1] & 0xfu) == 1) {
				base1 = (ib[i + 2] & ~3u) | (static_cast<uint64_t>(ib[i + 3] & 0xffffu) << 32u);
			} else if ((op == 0x15u && len >= 5) || (op == 0x16u && len >= 3)) {
				Dispatch d;
				d.at            = i;
				d.op            = op;
				d.program_known = pl_known && ph_known;
				d.program       = (static_cast<uint64_t>(pl) | (static_cast<uint64_t>(ph & 0xffu) << 32u)) << 8u;
				std::memcpy(d.ud, ud, sizeof(ud));
				d.ud_known = ud_known;
				if (op == 0x15u) {
					d.gx = ib[i + 1], d.gy = ib[i + 2], d.gz = ib[i + 3], d.groups_known = true;
					d.initiator = ib[i + 4];
				} else if (len >= 4) {
					d.args      = (ib[i + 1] & ~3u) | (static_cast<uint64_t>(ib[i + 2] & 0xffffu) << 32u);
					d.initiator = ib[i + 3];
				} else {
					d.args      = base1 != 0 ? base1 + ib[i + 1] : 0;
					d.initiator = ib[i + 2];
				}
				on_dispatch(static_cast<const Dispatch&>(d));
			}
		}
		i += len;
	}
	return true;
}
// The addresses a dispatch's user data may hold. A buffer descriptor has the base's low 32 bits in one dword and
// bits 32-39 in the low byte of the next (form 'b'); a texture descriptor has the base >> 8 in its first dword
// (form 't'). Both readings of every known dword are given; the caller keeps those that lie under a view.
// hit(k, form, address).
template <typename F> inline void candidates(const Dispatch& d, F&& hit) {
	for (uint32_t k = 0; k < 16; k++) {
		if ((d.ud_known & (1u << k)) == 0) continue;
		if (k + 1 < 16 && (d.ud_known & (1u << (k + 1))) != 0) {
			const uint64_t a = static_cast<uint64_t>(d.ud[k]) | (static_cast<uint64_t>(d.ud[k + 1] & 0xffu) << 32u);
			if ((d.ud[k + 1] & 0xffu) != 0) hit(k, 'b', a);
		}
		const uint64_t t = static_cast<uint64_t>(d.ud[k]) << 8u;
		if ((t >> 32u) != 0) hit(k, 't', t);
	}
}
struct Key {
	uint64_t program;
	uint32_t initiator;
	uint32_t op;
	bool     operator<(const Key& o) const { return std::tie(program, initiator, op) < std::tie(o.program, o.initiator, o.op); }
};
struct Val {
	uint64_t n = 0, groups = 0;
	double   first_t = 0, last_t = 0;
};
struct Counter {
	std::map<Key, Val> m;
	uint64_t           dispatches = 0, unknown_program = 0;
	void               add(const Dispatch& d, double t) {
		dispatches++;
		if (!d.program_known) unknown_program++;
		Val& v = m[Key {d.program_known ? d.program : 0, d.initiator, d.op}];
		if (v.n++ == 0) v.first_t = t;
		v.last_t = t;
		if (d.groups_known) v.groups += static_cast<uint64_t>(d.gx) * d.gy * d.gz;
	}
	uint64_t seen(const Dispatch& d) const {
		const auto it = m.find(Key {d.program_known ? d.program : 0, d.initiator, d.op});
		return it == m.end() ? 0 : it->second.n;
	}
	// The rarest first (those are the question), at most `most` lines. line(key, val).
	template <typename F> void report(size_t most, F&& line) const {
		std::vector<std::pair<Key, Val>> v(m.begin(), m.end());
		std::stable_sort(v.begin(), v.end(), [](const auto& a, const auto& b) { return a.second.n < b.second.n; });
		for (size_t i = 0; i < v.size() && i < most; i++) line(v[i].first, v[i].second);
	}
};
} // namespace dw412
// Experiment 0412 (tags tl412, dc412): the host's part of dw0412.inc.
static std::mutex     g_dc412_mutex;
static dw412::Counter g_dc412;
static bool dw412_read_table(const std::vector<bc5::direct::Mapping>& maps, uint64_t a, uint32_t pairs, std::vector<uint32_t>& out) {
	if (!covered_sorted(maps, a, static_cast<uint64_t>(pairs) * 8)) return false;
	const auto* t = reinterpret_cast<const volatile uint32_t*>(a);
	out.resize(2ull * pairs);
	for (uint32_t k = 0; k < 2 * pairs; k++) out[k] = t[k];
	return true;
}
static void dc412_count(const uint32_t* ib, uint32_t n) {
	if (!dw412::dc_on() || ib == nullptr || n == 0 || !g_dev) return;
	const auto      pm = g_dev->sorted_mappings();
	const double    t  = timing_now();
	std::lock_guard lock(g_dc412_mutex);
	dw412::walk(
	    ib, n, [&](uint64_t a, uint32_t p, std::vector<uint32_t>& o) { return dw412_read_table(*pm, a, p, o); }, [&](const dw412::Dispatch& d) { g_dc412.add(d, t); });
	static double last = 0;
	if (t - last < 60.0) return;
	last = t;
	journal("dispatch count (exp 0412, tag dc412): t %.1f s: %" PRIu64 " dispatches so far, %zu kinds (program, initiator, direct or indirect), %" PRIu64 " with no program set in their buffer; the 300 rarest follow\n", t,
	        g_dc412.dispatches, g_dc412.m.size(), g_dc412.unknown_program);
	g_dc412.report(300, [&](const dw412::Key& k, const dw412::Val& v) {
		journal("dispatch count (exp 0412, tag dc412): program 0x%" PRIx64 " initiator 0x%x %s: %" PRIu64 " times, %" PRIu64 " groups, first t %.1f s, last t %.1f s\n", k.program, k.initiator,
		        k.op == 0x16u ? "indirect" : "direct", v.n, v.groups, v.first_t, v.last_t);
	});
}
static void tl412_record(const uint32_t* ib, uint32_t n, const char* kind, uint64_t job) {
	if (!dw412::tl_on() || ib == nullptr || n == 0 || g_dump_dir.empty() || !g_dev) return;
	const double t0 = timing_now();
	char         name[512];
	std::snprintf(name, sizeof(name), "%s/timeout-layout-%08" PRIu64 "-%.8s.txt", g_dump_dir.c_str(), job, kind);
	FILE* f = std::fopen(name, "w");
	if (f == nullptr) return;
	const auto pm = g_dev->sorted_mappings();
	struct VRef {
		uint64_t     va, end;
		int          kind;
		const DView* v;
	};
	std::vector<std::shared_ptr<const DViews>> keep;
	std::vector<VRef>                          vr;
	for (auto& S: g_d) {
		if (dstate_fd(S) < 0) continue;
		keep.push_back(direct_views(S));
		for (const auto& v: keep.back()->v) vr.push_back(VRef {v.va, v.va + v.size, S.kind, &v});
	}
	std::sort(vr.begin(), vr.end(), [](const VRef& a, const VRef& b) { return a.va < b.va; });
	auto find = [&](uint64_t a) -> const VRef* {
		auto it = std::upper_bound(vr.begin(), vr.end(), a, [](uint64_t x, const VRef& r) { return x < r.va; });
		for (int back = 0; back < 8 && it != vr.begin(); back++) { // views are not nested deeper than this (aliases)
			--it;
			if (a < it->end) return &*it;
		}
		return nullptr;
	};
	std::fprintf(f, "# exp 0412 (tag tl412): the dispatches of the timed-out %s #%" PRIu64 " (%u dwords), t %.3f s; written before the probe\n", kind, job, n, t0);
	std::fprintf(f, "# per dispatch: offset, kind, program, initiator (bit 15 CS_W32_EN), groups, times dc412 counted it before (-1: dc412 off)\n");
	std::fprintf(f, "# per address its user data may hold (b: buffer reading, t: texture reading): the view, E eager / L lazy / D by data, the address into the view, its 2 MiB chunk imported or not, a GPU mapping there or not\n");
	uint32_t   n_disp = 0;
	const bool whole  = dw412::walk(
	    ib, n, [&](uint64_t a, uint32_t p, std::vector<uint32_t>& o) { return dw412_read_table(*pm, a, p, o); },
	    [&](const dw412::Dispatch& d) {
		    n_disp++;
		    long long seen = -1;
		    if (dw412::dc_on()) {
			    std::lock_guard lock(g_dc412_mutex);
			    seen = static_cast<long long>(g_dc412.seen(d));
		    }
		    char grid[64] = "?";
		    if (d.groups_known) std::snprintf(grid, sizeof(grid), "%u x %u x %u", d.gx, d.gy, d.gz);
		    else std::snprintf(grid, sizeof(grid), "arguments at 0x%" PRIx64, d.args);
		    std::fprintf(f, "dispatch at %u %s program %s0x%" PRIx64 " initiator 0x%x groups %s seen %lld\n", d.at, d.op == 0x16u ? "indirect" : "direct", d.program_known ? "" : "(not set in this buffer) ", d.program,
		                 d.initiator, grid, seen);
		    dw412::candidates(d, [&](uint32_t k, char form, uint64_t a) {
			    const VRef* r = find(a);
			    if (r == nullptr) return;
			    const DView&   v        = *r->v;
			    const bool     imported = direct_covered_end(g_d[r->kind], (v.off + (a - v.va)) & ~(kDChunk - 1)) != 0;
			    const bool     mapped   = covered_sorted(*pm, a & ~0xfffull, 4);
			    std::fprintf(f, "  ud%u %c 0x%" PRIx64 ": \"%s\" (%s file) %s, 0x%" PRIx64 " into the view 0x%" PRIx64 "+0x%" PRIx64 ", chunk %s, GPU mapping %s\n", k, form, a, v.name.c_str(),
			                 r->kind == 0 ? "direct" : "private", v.eager ? "E" : (v.lazy ? "L" : "D"), a - v.va, v.va, v.size, imported ? "imported" : "NOT imported", mapped ? "yes" : "NO");
			    if (form != 'b' || !mapped || !covered_sorted(*pm, a, 64)) return;
			    // the second level (README section 90): the first 16 dwords there, and the views of what they may hold
			    dw412::Dispatch in;
			    const auto*     w = reinterpret_cast<const volatile uint32_t*>(a);
			    for (int j = 0; j < 16; j++) in.ud[j] = w[j];
			    in.ud_known = 0xffffu;
			    std::fprintf(f, "    its first 16 dwords:");
			    for (int j = 0; j < 16; j++) std::fprintf(f, " %08x", in.ud[j]);
			    std::fprintf(f, "\n");
			    dw412::candidates(in, [&](uint32_t k2, char form2, uint64_t a2) {
				    const VRef* r2 = find(a2);
				    if (r2 == nullptr) return;
				    const DView& v2   = *r2->v;
				    const bool   imp2 = direct_covered_end(g_d[r2->kind], (v2.off + (a2 - v2.va)) & ~(kDChunk - 1)) != 0;
				    std::fprintf(f, "    -> dword %u %c 0x%" PRIx64 ": \"%s\" (%s file) %s, chunk %s, GPU mapping %s\n", k2, form2, a2, v2.name.c_str(), r2->kind == 0 ? "direct" : "private",
				                 v2.eager ? "E" : (v2.lazy ? "L" : "D"), imp2 ? "imported" : "NOT imported", covered_sorted(*pm, a2 & ~0xfffull, 4) ? "yes" : "NO");
			    });
		    });
	    });
	std::fprintf(f, "# %u dispatches%s; this part took %.1f ms\n", n_disp, whole ? "" : "; the walk STOPPED at a packet running past the end", (timing_now() - t0) * 1000.0);
	std::fflush(f);
	fsync(fileno(f)); // the part that matters is on the disk now
	std::fprintf(f, "# every view: file (0 direct, 1 private) va size file_offset flags(E eager, L lazy, D by data) name\n");
	for (const auto& r: vr) std::fprintf(f, "%d 0x%" PRIx64 " 0x%" PRIx64 " 0x%" PRIx64 " %s %s\n", r.kind, r.v->va, r.v->size, r.v->off, r.v->eager ? "E" : (r.v->lazy ? "L" : "D"), r.v->name.c_str());
	std::fflush(f);
	fsync(fileno(f));
	std::fclose(f);
	if (const int dfd = ::open(g_dump_dir.c_str(), O_RDONLY | O_DIRECTORY | O_CLOEXEC); dfd >= 0) {
		fsync(dfd);
		::close(dfd);
	}
	journal("timeout layout (exp 0412, tag tl412): %u dispatches of %s #%" PRIu64 " and %zu views written and synced in %.1f ms: %s\n", n_disp, kind, job, vr.size(), (timing_now() - t0) * 1000.0, name);
}
[[maybe_unused]] static void timeout_probe(const uint32_t* sub_ib, uint32_t sub_n, const char* kind, uint64_t n, const std::vector<uint32_t>* ran, const std::vector<GeProbeSlot>* gep = nullptr) {
	tl412_record(sub_ib, sub_n, kind, n); // exp 0412 (tag tl412): first, before the probe's own files
	if (sub_ib == nullptr || sub_n == 0 || BC5_DIAG_ENV("BC5_DIRECT_TIMEOUT_PROBE") == nullptr || g_dump_dir.empty() || !g_dev) return;
	{
		char name[512];
		std::snprintf(name, sizeof(name), "%s/ib-timeout-%08" PRIu64 "-%.8s-%u.bin", g_dump_dir.c_str(), n, kind, sub_n);
		if (FILE* f = std::fopen(name, "wb"); f != nullptr) {
			std::fwrite(sub_ib, sizeof(uint32_t), sub_n, f);
			std::fflush(f); // experiment 0260: a machine-down follows a timeout often enough
			fsync(fileno(f));
			std::fclose(f);
		}
		auto     pm    = g_dev->sorted_mappings();
		uint64_t b1    = 0, ibase = 0;
		uint32_t itype = 0;
		uint32_t ud_probe[16] = {}; // experiment 0160
		// experiment 0160: draw-time state — context 0x2d5 (VGT_SHADER_STAGES_EN), 0x2d3 (GE_NGG_SUBGRP_CNTL),
		// 0x291 (VGT_GS_ONCHIP_CNTL), 0x2a6 (VGT_DRAW_PAYLOAD_CNTL); uconfig 0x242 (VGT_PRIMITIVE_TYPE), 0x243
		// (VGT_INDEX_TYPE), 0x24d (VGT_NUM_INSTANCES), 0x25b (GE_CNTL), 0x25f (GE_STEREO_CNTL), 0x260 (GE_PC_ALLOC; until exp 0189 0x25f was printed as pc_alloc); SH 0x88/0x89
		// (SPI_SHADER_PGM_LO/HI_GS), 0xc8/0xc9 (ES), 0x8/0x9 (PS), 0x20c/0x20d (COMPUTE_PGM) — from SET_*_REG,
		// SET_UCONFIG_REG_INDEX and the LOAD_*_REG_INDEX tables as they read now (Mesa gfx10 register JSON).
		std::map<uint32_t, uint32_t> st_ctx, st_uc, st_sh;
		auto load_pairs = [&](const uint32_t* pk, uint32_t ln, std::map<uint32_t, uint32_t>& into) {
			if (ln < 5 || (pk[3] >> 31u) == 0) return;
			const uint64_t ta = (pk[1] & ~3u) | (static_cast<uint64_t>(pk[2] & 0xffffu) << 32u);
			const uint32_t tn = pk[4] & 0x3fffu;
			if (ta == 0 || tn == 0 || tn > 4096 || !covered_sorted(*pm, ta, static_cast<uint64_t>(tn) * 8)) return;
			const auto* t = reinterpret_cast<const volatile uint32_t*>(ta);
			for (uint32_t k = 0; k < tn; k++) into[t[2 * k] & 0xffffu] = t[2 * k + 1];
		};
		auto set_regs = [](const uint32_t* pk, uint32_t ln, std::map<uint32_t, uint32_t>& into) {
			if (ln < 3) return;
			const uint32_t first = pk[1] & 0xffffu;
			for (uint32_t k = 0; k + 2 < ln; k++) into[first + k] = pk[2 + k];
		};
		auto g = [](const std::map<uint32_t, uint32_t>& m, uint32_t r) { auto it = m.find(r); return it == m.end() ? 0xffffffffu : it->second; };
		auto state_line = [&](char* out, size_t cap) {
			std::snprintf(out, cap, "stages %08x subgrp %08x onchip %08x payload %08x | prim %08x itype %08x ninst %08x ge_cntl %08x stereo %08x pc_alloc %08x | gs %08x%08x es %08x%08x ps %08x%08x cs %08x%08x ls %08x%08x hs %08x%08x",
			              g(st_ctx, 0x2d5), g(st_ctx, 0x2d3), g(st_ctx, 0x291), g(st_ctx, 0x2a6), g(st_uc, 0x242), g(st_uc, 0x243), g(st_uc, 0x24d), g(st_uc, 0x25b), g(st_uc, 0x25f), g(st_uc, 0x260),
			              g(st_sh, 0x89), g(st_sh, 0x88), g(st_sh, 0xc9), g(st_sh, 0xc8), g(st_sh, 0x9), g(st_sh, 0x8), g(st_sh, 0x20d), g(st_sh, 0x20c), g(st_sh, 0x149), g(st_sh, 0x148), g(st_sh, 0x109), g(st_sh, 0x108)); // exp 0189: + SPI_SHADER_PGM_LO/HI_LS, _HS
		};
		auto     rd    = [&](uint64_t a, uint32_t n, char* out, size_t cap) {
			if (!covered_sorted(*pm, a, static_cast<uint64_t>(n) * 4)) { std::snprintf(out, cap, "<0x%" PRIx64 " unmapped>", a); return; }
			const auto* t = reinterpret_cast<const volatile uint32_t*>(a);
			size_t      o = static_cast<size_t>(std::snprintf(out, cap, "[0x%" PRIx64 "]", a));
			for (uint32_t k = 0; k < n && o + 10 < cap; k++) o += static_cast<size_t>(std::snprintf(out + o, cap - o, " %08x", t[k]));
		};
		journal("timeout probe: %s %u dwords dumped to %s\n", kind, sub_n, name);
		// Experiment 0189: with the title's /dev/gc TF ring programmed, the ring as the GPU left it (<name>.tfring.bin,
		// with a count of its non-zero dwords), and for the first 4 SPI_SHADER_USER_DATA_ADDR_LO/HI_HS pairs the buffer
		// sets (SET_SH_REG sh 0x102/0x103, gfx10 register JSON; the merged LS-HS stage's s0/s1) 1 KiB there
		// (<name>.hsud-<k>.bin) and its first 48 dwords in the journal.
		if (gc_tf_ring_on() && g_gc_tf_base.load() != 0) {
			const uint64_t tb = g_gc_tf_base.load();
			const uint32_t ts = g_gc_tf_size.load() & ~3u;
			if (ts != 0 && covered_sorted(*pm, tb, ts)) {
				const auto* t  = reinterpret_cast<const volatile uint32_t*>(tb);
				uint32_t    nz = 0, first = ~0u, last = 0;
				std::vector<uint32_t> copy(ts / 4);
				for (uint32_t k = 0; k < ts / 4; k++) {
					copy[k] = t[k];
					if (copy[k] != 0) { nz++; if (first == ~0u) first = k; last = k; }
				}
				const std::string nm = std::string(name) + ".tfring.bin";
				if (FILE* f = std::fopen(nm.c_str(), "wb"); f != nullptr) { std::fwrite(copy.data(), 4, copy.size(), f); std::fclose(f); }
				char buf[700];
				rd(tb + (first == ~0u ? 0 : static_cast<uint64_t>(first) * 4), 48, buf, sizeof(buf));
				journal("timeout probe: TF ring 0x%" PRIx64 " +0x%x: %u non-zero dwords (dword %u..%u), from the first: %s\n", tb, ts, nz, first, last, buf);
			}
		}
		{
			uint32_t lo = 0, nud = 0;
			bool     have_lo = false;
			for (uint32_t q = 0; q < sub_n && nud < 4;) {
				const uint32_t h = sub_ib[q], type = h >> 30u;
				uint32_t       len = 1;
				if (type == 3 || type == 0) { const uint32_t c = (h >> 16u) & 0x3fffu; len = c == 0x3fffu ? 1 : c + 2; }
				if (q + len > sub_n) break;
				const uint32_t op = (h >> 8u) & 0xffu;
				if (type == 3 && (op == 0x76 || op == 0x9b) && len >= 3) {
					const uint32_t first = sub_ib[q + 1] & 0xffffu;
					for (uint32_t k = 0; k + 2 < len && nud < 4; k++) {
						const uint32_t r = first + k, v = sub_ib[q + 2 + k];
						if (r == 0x102) { lo = v; have_lo = true; }
						if (r == 0x103 && have_lo) {
							const uint64_t a = (static_cast<uint64_t>(lo) | (static_cast<uint64_t>(v) << 32u)) & ~3ull;
							have_lo = false;
							if (a == 0 || !covered_sorted(*pm, a, 1024)) {
								journal("timeout probe: HS user data address 0x%" PRIx64 " at %u not mapped\n", a, q);
								continue;
							}
							char nm[600];
							std::snprintf(nm, sizeof(nm), "%s.hsud-%u.bin", name, nud);
							if (FILE* f = std::fopen(nm, "wb"); f != nullptr) {
								std::vector<uint32_t> c(256);
								for (uint32_t i = 0; i < 256; i++) c[i] = reinterpret_cast<const volatile uint32_t*>(a)[i];
								std::fwrite(c.data(), 4, c.size(), f);
								std::fclose(f);
							}
							char buf[700];
							rd(a, 48, buf, sizeof(buf));
							journal("timeout probe: HS user data address set at %u: %s\n", q, buf);
							nud++;
						}
					}
				}
				q += len;
			}
		}
		if (gep != nullptr && !gep->empty() && g_dev->gds_shadow_cpu() != nullptr) {
			const volatile uint32_t* sh = g_dev->gds_shadow_cpu() + kGeProbeOff / 4;
			for (const GeProbeSlot& g: *gep) {
				const volatile uint32_t* v = sh + static_cast<size_t>(g.slot) * 8;
				journal("timeout probe: ge regs before op %02x at %u (slot %u): WD_INDEX_BUF_BASE %08x %08x WD_POS_BUF_BASE %08x WD_CNTL_SB_BUF_BASE %08x GE_DMA_FIRST_INDEX %08x VGT_INDEX_TYPE %08x GE_CNTL %08x CP_INDEX_BASE_ADDR %08x\n",
				        g.op, g.offset, g.slot, v[0], v[1], v[2], v[3], v[4], v[5], v[6], v[7]);
			}
		}
		uint32_t n_waits = 0, n_kept = 0, n_writes = 0, n_disp = 0; // experiment 0260
		uint32_t n_ind = 0, max_at = 0;                              // experiment 0272: indirect dispatches, the largest grid's offset
		uint64_t max_groups = 0;
		for (uint32_t q = 0; q < sub_n;) {
			const uint32_t h = sub_ib[q], type = h >> 30u;
			uint32_t       len = 1;
			if (type == 3 || type == 0) { const uint32_t c = (h >> 16u) & 0x3fffu; len = c == 0x3fffu ? 1 : c + 2; }
			if (q + len > sub_n) break;
			if (type == 3) {
				const uint32_t op = (h >> 8u) & 0xffu;
				char           a1[400] = {}, a2[400] = {};
				if (op == 0x69) set_regs(sub_ib + q, len, st_ctx);
				else if (op == 0x79 || op == 0x7a) set_regs(sub_ib + q, len, st_uc);
				else if (op == 0x76) set_regs(sub_ib + q, len, st_sh);
				else if (op == 0x9f) load_pairs(sub_ib + q, len, st_ctx);
				else if (op == 0x64) load_pairs(sub_ib + q, len, st_uc);
				else if (op == 0x63) load_pairs(sub_ib + q, len, st_sh);
				else if (op == 0x2f && len >= 2) st_uc[0x24d] = sub_ib[q + 1];
				if (op == 0x24 || op == 0x25 || op == 0x27 || op == 0x2c || op == 0x2d || op == 0x35 || op == 0x38 || op == 0x15 || op == 0x16) {
					char sl[600];
					state_line(sl, sizeof(sl));
					journal("timeout probe:   state before op %02x at %u: %s\n", op, q, sl);
					if (op != 0x15 && op != 0x16) { // experiment 0160: GS user data (SH 0x2c8c..0x2cab) and the ES's descriptors
						char ul[700];
						int  w = std::snprintf(ul, sizeof(ul), "timeout probe:   gs user data:");
						for (uint32_t k = 0; k < 32 && w < 650; k++) w += std::snprintf(ul + w, sizeof(ul) - static_cast<size_t>(w), " %08x", g(st_sh, 0x8cu + k));
						journal("%s\n", ul);
						auto vsharp = [&](uint32_t k0, const char* name) {
							const uint64_t base = g(st_sh, 0x8cu + k0) | (static_cast<uint64_t>(g(st_sh, 0x8cu + k0 + 1) & 0xffffu) << 32u);
							char           m1[400] = {}, m2[400] = {}, m3[400] = {};
							if (base != 0 && base != 0xffffffffull) rd(base, 16, m1, sizeof(m1));
							if (base != 0 && base != 0xffffffffull && covered_sorted(*pm, base + 0x540, 16)) {
								rd(base + 0x540, 4, m2, sizeof(m2));
								const auto*    t  = reinterpret_cast<const volatile uint32_t*>(base + 0x540);
								const uint64_t b2 = t[0] | (static_cast<uint64_t>(t[1] & 0xffffu) << 32u);
								if (b2 != 0) rd(b2, 16, m3, sizeof(m3));
							}
							journal("timeout probe:   %s: base 0x%" PRIx64 " %s | +0x540 %s | table %s\n", name, base, m1, m2, m3);
						};
						vsharp(8, "s[8:11]");
						vsharp(20, "s[20:23]");
						vsharp(24, "s[24:27]");
					}
				}
				const char*    ex = ran == nullptr ? "" : (std::binary_search(ran->begin(), ran->end(), q) ? " ran" : " DROPPED");
				if ((op == 0x3c && len >= 7) || (op == 0x93 && len >= 9)) { // experiment 0260: the waits
					const bool     is64 = op == 0x93;
					const uint32_t fn   = sub_ib[q + 1] & 7u;
					const bool     mem  = ((sub_ib[q + 1] >> 4u) & 3u) != 0;
					const uint64_t a    = (sub_ib[q + 2] & ~3u) | (static_cast<uint64_t>(sub_ib[q + 3] & 0xffffu) << 32u);
					const uint64_t ref  = is64 ? sub_ib[q + 4] | (static_cast<uint64_t>(sub_ib[q + 5]) << 32u) : sub_ib[q + 4];
					const uint64_t msk  = is64 ? sub_ib[q + 6] | (static_cast<uint64_t>(sub_ib[q + 7]) << 32u) : sub_ib[q + 5];
					char           now[64] = "not read";
					if (mem && a != 0 && covered_sorted(*pm, a, is64 ? 8 : 4)) {
						const uint64_t v  = is64 ? *reinterpret_cast<const volatile uint64_t*>(a) : *reinterpret_cast<const volatile uint32_t*>(a);
						const uint64_t vm = v & msk, rm = ref & msk;
						const bool met = fn == 0 || (fn == 1 && vm < rm) || (fn == 2 && vm <= rm) || (fn == 3 && vm == rm) || (fn == 4 && vm != rm) || (fn == 5 && vm >= rm) || (fn == 6 && vm > rm);
						std::snprintf(now, sizeof(now), "0x%" PRIx64 " (%s)", v, met ? "met" : "NOT met");
					}
					if (ran != nullptr && std::binary_search(ran->begin(), ran->end(), q)) n_kept++;
					if (n_waits++ < 200)
						journal("timeout probe: wait op %02x at %u: %s 0x%" PRIx64 " function %u reference 0x%" PRIx64 " mask 0x%" PRIx64 " %s; now %s%s\n", op, q, mem ? "label" : "register",
						        mem ? a : static_cast<uint64_t>(sub_ib[q + 2]), fn, ref, msk, ((sub_ib[q + 1] >> 8u) & 1u) != 0 ? "pfp" : "me", now, ex);
				} else if ((op == 0x49 && len >= 8) || (op == 0x47 && len >= 6) || (op == 0x37 && len >= 5)) { // experiment 0260: the label writes
					const uint32_t* w   = sub_ib + q;
					const int       lo  = op == 0x49 ? 3 : 2;
					const uint32_t  sel = op == 0x49 ? w[2] >> 29u : (op == 0x47 ? w[3] >> 29u : (w[1] >> 8u) & 0xfu); // WRITE_DATA: its DST_SEL
					const uint32_t  dk  = op == 0x49 ? 5u : 4u;
					const uint64_t  a   = (w[lo] & ~3u) | (static_cast<uint64_t>(w[lo + 1] & 0xffffu) << 32u);
					if (op != 0x37 || sel == 1 || sel == 2 || sel == 5) {
						const bool     two = op == 0x37 ? len >= 6 : sel != 1; // 64-bit data: WRITE_DATA with two dwords, RELEASE_MEM / EOP unless DATA_SEL 1
						const uint64_t v   = w[dk] | (two ? static_cast<uint64_t>(w[dk + 1]) << 32u : 0ull);
						char           now[40] = "not read";
						if (a != 0 && covered_sorted(*pm, a, 8)) std::snprintf(now, sizeof(now), "0x%" PRIx64, *reinterpret_cast<const volatile uint64_t*>(a));
						if (n_writes++ < 200)
							journal("timeout probe: write op %02x at %u: 0x%" PRIx64 " select %u value 0x%" PRIx64 " (packet %u dwords); now %s%s\n", op, q, a, sel, v, len, now, ex);
					}
				} else if (op == 0x15 || op == 0x16) { // experiment 0260: the dispatches' programs; experiment 0272: and their group counts
					const uint32_t pl = g(st_sh, 0x20cu), ph = g(st_sh, 0x20du);
					uint32_t       gx = 0, gy = 0, gz = 0;
					bool           have = false;
					char           where[64] = "";
					if (op == 0x15 && len >= 4) {
						gx = sub_ib[q + 1], gy = sub_ib[q + 2], gz = sub_ib[q + 3], have = true;
					} else if (op == 0x16 && len >= 3) { // the compute-queue form (4 dwords: the address) or the SET_BASE form (3: an offset), as mec_expand_ib has them
						const uint64_t a = len >= 4 ? (sub_ib[q + 1] & ~3u) | (static_cast<uint64_t>(sub_ib[q + 2] & 0xffffu) << 32u) : b1 + sub_ib[q + 1];
						if ((len >= 4 || b1 != 0) && covered_sorted(*pm, a, 12)) {
							const auto* t = reinterpret_cast<const volatile uint32_t*>(a);
							gx = t[0], gy = t[1], gz = t[2], have = true;
						}
						std::snprintf(where, sizeof(where), " (arguments at 0x%" PRIx64 "%s)", a, have ? "" : ", not mapped");
					}
					const uint64_t groups = static_cast<uint64_t>(gx) * gy * gz;
					if (have && groups > max_groups) max_groups = groups, max_at = q;
					if (op == 0x16 ? n_ind++ < 2000 : n_disp - n_ind < 200) {
						char grid[64] = "?";
						if (have) std::snprintf(grid, sizeof(grid), "%u x %u x %u", gx, gy, gz);
						journal("timeout probe: dispatch op %02x at %u: program %s0x%" PRIx64 ", groups %s%s%s\n", op, q, pl == 0xffffffffu ? "not set in this buffer, " : "",
						        (static_cast<uint64_t>(pl) | (static_cast<uint64_t>(ph & 0xffu) << 32u)) << 8u, grid, where, ex);
					}
					n_disp++;
				}
				if (op == 0x11 || op == 0x26 || op == 0x13 || op == 0x2a || (op == 0x2e && len >= 3 && (sub_ib[q + 1] & 0xffffu) == 0x243u))
					journal("timeout probe: op %02x at %u: %08x %08x %08x%s (mapped %d)\n", op, q, len > 1 ? sub_ib[q + 1] : 0u, len > 2 ? sub_ib[q + 2] : 0u, len > 3 ? sub_ib[q + 3] : 0u, ex, op == 0x26 && len >= 3 ? static_cast<int>(covered_sorted(*pm, sub_ib[q + 1] | (static_cast<uint64_t>(sub_ib[q + 2] & 0xffffu) << 32u), 4)) : -1);
				if (op == 0x11 && len >= 4 && (sub_ib[q + 1] & 0xfu) == 1) {
					b1 = (sub_ib[q + 2] & ~3u) | (static_cast<uint64_t>(sub_ib[q + 3] & 0xffffu) << 32u);
				} else if (op == 0x26 && len >= 3) {
					ibase = sub_ib[q + 1] | (static_cast<uint64_t>(sub_ib[q + 2] & 0xffffu) << 32u);
				} else if (op == 0x2a && len >= 2) {
					itype = sub_ib[q + 1];
				} else if (op == 0x2e && len >= 3 && (sub_ib[q + 1] & 0xffffu) == 0x243u) {
					itype = sub_ib[q + 2];
				} else if ((op == 0x2c || op == 0x38) && len >= 10) {
					const uint64_t a = b1 + sub_ib[q + 1];
					rd(a, std::min(sub_ib[q + 5] * (sub_ib[q + 8] / 4u), 40u), a1, sizeof(a1));
					if (op == 0x38 && covered_sorted(*pm, a, 12)) {
						const auto* t = reinterpret_cast<const volatile uint32_t*>(a);
						rd(ibase + static_cast<uint64_t>(t[2]) * ((itype & 3u) == 1 ? 4u : 2u), 8, a2, sizeof(a2));
					}
					journal("timeout probe: op %02x at %u: off 0x%x count %u stride %u base1 0x%" PRIx64 " index_base 0x%" PRIx64 " type 0x%x args %s indices %s%s\n", op, q, sub_ib[q + 1], sub_ib[q + 5], sub_ib[q + 8], b1, ibase, itype, a1, a2, ex);
				} else if ((op == 0x24 || op == 0x25) && len >= 2) {
					rd(b1 + sub_ib[q + 1], 5, a1, sizeof(a1));
					journal("timeout probe: op %02x at %u: off 0x%x base1 0x%" PRIx64 " index_base 0x%" PRIx64 " args %s%s\n", op, q, sub_ib[q + 1], b1, ibase, a1, ex);
				} else if (op == 0x76 && len >= 3) { // SET_SH_REG: COMPUTE_USER_DATA for the V# dump below
					const uint32_t first = sub_ib[q + 1] & 0xffffu;
					for (uint32_t k = 0; k + 2 < len; k++) {
						if (first + k >= 0x240u && first + k < 0x250u) ud_probe[first + k - 0x240u] = sub_ib[q + 2 + k];
					}
				}
				if ((op == 0x15 || op == 0x16) && len >= 2) { // experiment 0160: V# memory at the dispatch
					for (uint32_t k = 0; k + 3 < 16; k += 4) {
						const uint64_t base = ud_probe[k] | (static_cast<uint64_t>(ud_probe[k + 1] & 0xffffu) << 32u);
						const uint32_t nrec = ud_probe[k + 2];
						if (base == 0 || nrec == 0 || (ud_probe[k + 3] & 0xf0000000u) == 0) continue;
						char buf[400] = {};
						rd(base, 16, buf, sizeof(buf));
						journal("timeout probe:   ud%u-%u V# base 0x%" PRIx64 " stride %u records %u: %s\n", k, k + 3, base, (ud_probe[k + 1] >> 16u) & 0x3fffu, nrec, buf);
					}
				}
				if (false) {
				} if (op == 0x27 || op == 0x2d || op == 0x35 || op == 0x15 || op == 0x16 || op == 0x22 || op == 0x3f) {
					journal("timeout probe: op %02x at %u: %08x %08x %08x %08x base1 0x%" PRIx64 " index_base 0x%" PRIx64 "%s\n", op, q, len > 1 ? sub_ib[q + 1] : 0u, len > 2 ? sub_ib[q + 2] : 0u, len > 3 ? sub_ib[q + 3] : 0u, len > 4 ? sub_ib[q + 4] : 0u, b1, ibase, ex);
				}
			}
			q += len;
		}
		journal("timeout probe: %s #%" PRIu64 " %u dwords: %u waits (%u kept for the GPU), %u label writes, %u dispatches (%u indirect; the largest grid %" PRIu64 " groups, at %u)\n", kind, n, sub_n,
		        n_waits, n_kept, n_writes, n_disp, n_ind, max_groups, max_at);
		if (g_journal_min) { // experiment 0260: the probe's lines on the disk (and in a stream of the journal) before a machine-down
			if (FILE* jf = journal_min_file(true); jf != nullptr) fsync(fileno(jf));
		}
	}
}
// Experiment 0046: a timestamp scale k multiplies the 64-bit GPU timestamps (RELEASE_MEM and
// EVENT_WRITE_EOP with DATA_SEL 3) the game's buffers write, once each job is done, so that the
// game measures k times the GPU time it really took. Diagnostic: does the title's dynamic
// resolution follow its timestamps?
// Experiment 0047: settable while the game runs (the F2 menu's Video tab). Experiment 0115: only
// from the running title's own entry, RenderScale.<TITLE_ID> in the input configuration; a title
// without one runs with its timestamps untouched (1). The BC5_DIRECT_TS_SCALE start value, which
// applied to every title, was removed in cleanup batch 5.
static std::atomic<double> g_ts_scale {1.0};
static double ts_scale() {
	return g_ts_scale.load(std::memory_order_relaxed);
}
static void ts_collect(const uint32_t* ib, uint32_t num_dwords, std::vector<uint64_t>* out) {
	for (uint32_t q = 0; q < num_dwords;) {
		const uint32_t h    = ib[q];
		const uint32_t type = h >> 30u;
		uint32_t       len  = 1;
		if (type == 3 || type == 0) { const uint32_t c = (h >> 16u) & 0x3fffu; len = c == 0x3fffu ? 1 : c + 2; }
		if (q + len > num_dwords) break;
		if (type == 3) {
			const uint32_t op = (h >> 8u) & 0xffu;
			if (op == 0x49 && len >= 7 && (ib[q + 2] >> 29u) == 3) out->push_back((ib[q + 3] & ~7ull) | (static_cast<uint64_t>(ib[q + 4] & 0xffffu) << 32u));
			if (op == 0x47 && len >= 6 && (ib[q + 3] >> 29u) == 3) out->push_back((ib[q + 2] & ~7ull) | (static_cast<uint64_t>(ib[q + 3] & 0xffffu) << 32u));
		}
		q += len;
	}
}
// Experiment 0415 (tags fs415, fs415b), KYTY_BC5_FRAME_STAT=<file> (default off; unset, empty and "0" are off), part
// 2's counter. No change of behaviour: lines are written by the completion threads, by a submitter for a job it
// completed itself, and at the flip, outside the device mutex.
//   f <frame> <flip called ns> <flip returned ns>                                   every flip (CLOCK_MONOTONIC)
//   K <frame> <n> <kind> <ring> <title dwords> <filter dwords> <packets> <dropped> <BOs> <prepare ms> <list ms> <cs ms>
//     <submit_now entered ns> <device mutex asked ns> <got ns> <queued ns> <fence seen ns> <gpu start> <gpu end> <how>
//     <chain opened ns> <flush reason> <segments> <six part ends, ns>      (fs415c; build L5a wrote "J" without these)
//       every job (fs415b: ALL of them, on every ring, whether the completion thread or the submitter completed it)
//       while the frame number is inside a window: KYTY_BC5_FRAME_STAT_WIN=<frames>/<period>, 64/512 when unset
//       (64 frames in a row out of every 512). ring -1 is the GFX ring (bc5::direct::kGfxRing), 0-3 the compute
//       rings. <how>: a = by the completion thread, s = by the submitter (not queued: its stamps are the call's).
//       GPU stamps are 0 unless BC5_DIRECT_JOB_TS=1 (the GPU's own clock, 10 ns units).
// The frame number on a J line is the one current when the line is written; frame0415.py assigns jobs to frames by
// their stamps and drops a window's first and last frames, whose jobs may lie outside it.
static FILE* fs415_file() {
	static FILE* const f = [] {
		const char* e = BC5_DIAG_ENV("KYTY_BC5_FRAME_STAT");
		return bc5::load_stat::env_set(e) ? std::fopen(e, "a") : nullptr;
	}();
	return f;
}
static std::mutex            g_fs415_mutex;
static std::atomic<uint64_t> g_fs415_frame {0};
static bool fs415_in_window(uint64_t frame) { // fs415b
	static const std::pair<uint64_t, uint64_t> w = [] {
		std::pair<uint64_t, uint64_t> v {64, 512};
		if (const char* e = BC5_DIAG_ENV("KYTY_BC5_FRAME_STAT_WIN"); bc5::load_stat::env_set(e)) {
			char*                    end = nullptr;
			const unsigned long long a   = std::strtoull(e, &end, 10);
			const unsigned long long b   = end != nullptr && *end == '/' ? std::strtoull(end + 1, nullptr, 10) : 0;
			if (a >= 1 && b >= a && b <= 1'000'000ull) v = {a, b};
		}
		return v;
	}();
	return frame % w.second < w.first;
}
// fs415d: the line is "L": K's fields, then what the submitting thread spent between the probe and the end of the direct
// sync in direct_sync_one's parts (ns: views, scan with its imports, merges, the drain, the mappings; the imports
// alone), in sync_mappings' read of /proc/self/maps (ns), and sync_mappings' flags (1 walked, 2 urgent, 4 left out).
// fs415c: the line was "K": J's fields, then the chain's first segment (ns, 0 without a chain), why it was flushed
// (chain_submit's reason, -1 without a chain), its segments, and the ends of submit_now's parts under the mutex (ns):
// probe, anonymous sync, direct sync, learned windows, hints, the work before the device call. The device call is
// from the last of these to "queued".
static void fs415_job(uint64_t n, const char* kind, int ring, uint32_t num_dwords, const bc5::policy::FilterStats& fs, uint32_t bo_count, double prepare_ms, double list_ms,
                      double cs_ms, uint64_t sub_ns, uint64_t ask_ns, uint64_t got_ns, uint64_t queued_ns, uint64_t gpu_start, uint64_t gpu_end, char how, uint64_t open_ns,
                      int why, uint32_t segs, const uint64_t* part_ns, const uint64_t* ds) {
	FILE* f = fs415_file();
	if (f == nullptr) return;
	const uint64_t frame = g_fs415_frame.load(std::memory_order_relaxed);
	if (!fs415_in_window(frame)) return;
	std::lock_guard fl(g_fs415_mutex);
	std::fprintf(f, "L %" PRIu64 " %" PRIu64 " %s %d %u %" PRIu64 " %" PRIu64 " %" PRIu64 " %u %.3f %.3f %.3f %" PRIu64 " %" PRIu64 " %" PRIu64 " %" PRIu64 " %" PRIu64 " %" PRIu64 " %" PRIu64 " %c %" PRIu64
	                " %d %u %" PRIu64 " %" PRIu64 " %" PRIu64 " %" PRIu64 " %" PRIu64 " %" PRIu64 " %" PRIu64 " %" PRIu64 " %" PRIu64 " %" PRIu64 " %" PRIu64 " %" PRIu64 " %" PRIu64
	                " %" PRIu64 "\n",
	             frame, n, kind, ring, num_dwords, fs.dwords, fs.packets, fs.dropped, bo_count, prepare_ms, list_ms, cs_ms, sub_ns, ask_ns, got_ns, queued_ns,
	             static_cast<uint64_t>(SoftCp::now_ns()), gpu_start, gpu_end, how, open_ns, why, segs, part_ns[0], part_ns[1], part_ns[2], part_ns[3], part_ns[4], part_ns[5], ds[0], ds[1], ds[2], ds[3], ds[4],
	             ds[5], ds[6], ds[7]);
}

struct CqItem {
	bool                      fence = false;
	PendingJob                job;
	std::function<void(bool)> post;
};
struct Cq {
	std::mutex              mutex;
	std::condition_variable cv;
	std::deque<CqItem>      items;
	std::once_flag          started;
};
static Cq                    g_cqs[2];
static thread_local int      t_cq = 0;
static std::atomic<uint32_t> g_cq_fences {0}, g_cq_items {0};
static std::atomic<bool>     g_recovering {false};
static std::atomic<uint64_t> g_dev_gen {0}; // counts device reopens: a job queued on an earlier device is dead

static void set_source(int index) {
	t_cq = index == 1 ? 1 : 0;
}

// Experiment 0343: the bound of a WAIT_REG_MEM poll inside a replay run by the game thread's completion
// queue (BC5_DIRECT_SOFT_WAIT_MS, default 8, like the game thread's DCB waits; 0 keeps the soft CP's
// 2-s deadline) and not the ring thread's: a compute
// buffer may legitimately end in a wait for the next frame's label there, run 110. A replay runs after
// the job's fence: a label still unwritten then can only be written by work the title has not submitted,
// and while drain() holds the game thread at the flip that work cannot come (exp 0341's 22-s hold, F415:
// eleven polls at 2 s). The packets after the wait run as before, only sooner.
static uint64_t soft_wait_ns() {
	static const uint64_t v = (BC5_DIAG_ENV("BC5_DIRECT_SOFT_WAIT_MS") != nullptr ? std::strtoull(BC5_DIAG_ENV("BC5_DIRECT_SOFT_WAIT_MS"), nullptr, 10) : 8ull) * 1'000'000ull;
	return v;
}
static void completion_thread(int index) {
	{
		char name[16];
		std::snprintf(name, sizeof(name), "bc5-cq%d", index);
		pthread_setname_np(pthread_self(), name);
	}
	{
		char name[16];
		std::snprintf(name, sizeof(name), "bc5-cq%d", index);
		pthread_setname_np(pthread_self(), name);
	}
	static const bool timing_env = BC5_DIAG_ENV("BC5_DIRECT_TIMING") != nullptr;
	const bool timing = timing_env && ::Log::Bc5LoggingOn();
	Cq&  cq     = g_cqs[index];
	bool failed = false; // a job since the last post did not complete
	for (;;) {
		CqItem it;
		{
			std::unique_lock lk(cq.mutex);
			cq.cv.wait(lk, [&cq] { return !cq.items.empty(); });
			it = std::move(cq.items.front());
			cq.items.pop_front();
		}
		if (it.fence) {
			const PendingJob&          j = it.job;
			bc5::direct::SubmitResult r;
			while (g_recovering.load()) std::this_thread::sleep_for(std::chrono::milliseconds(1));
			if (g_dev && j.dev_gen == g_dev_gen.load()) {
				std::shared_lock finish_lock(g_finish_mutex);
				umr_watchdog_start(); // experiment 0058
				g_fence_wait_since = j.queued_ns != 0 ? j.queued_ns : SoftCp::now_ns(); // from the job's submission: the kernel resets ~2 s after it hangs
				static constexpr uint64_t fence_ns = 2'000'000'000ull;
				if (g_dev) r = g_dev->finish(j.seq, j.slot, fence_ns);
				if (g_dev) bc5_ranges_complete(j.ib, j.n, g_dev->sorted_mappings()); // experiment 0157
				// Experiment 0124: the GPU's time line from the jobs' own timestamps (100 MHz clock):
				// busy (start to end of each job) and the idle gaps between one job's end and the
				// next one's start, journaled for every second of GPU time.
				// BC5_DIRECT_JOB_TS=<t0>:<t1> also journals every job's interval in that window (offline union).
				static const std::pair<double, double> jt_win = [] {
					std::pair<double, double> w {-1.0, -1.0};
					if (const char* e = BC5_DIAG_ENV("BC5_DIRECT_JOB_TS"); e != nullptr && std::strchr(e, ':') != nullptr) {
						char* end = nullptr;
						w.first   = std::strtod(e, &end);
						w.second  = std::strtod(end + 1, nullptr);
					}
					return w;
				}();
				if (r.ok && r.gpu_start != 0 && jt_win.first >= 0 && timing_now() >= jt_win.first && timing_now() < jt_win.second) {
					journal("jt %" PRIu64 " %" PRIu64 " %s %u %d\n", r.gpu_start, r.gpu_end, j.kind, j.num_dwords, r.ring);
				}
				if (r.ok && r.gpu_start != 0 && r.gpu_end > r.gpu_start) {
					static uint64_t prev_end = 0, win0 = 0, busy = 0, idle = 0, jobs = 0, gaps = 0, overlaps = 0, big = 0, big_t = 0;
					if (win0 == 0) win0 = r.gpu_start;
					busy += r.gpu_end - r.gpu_start;
					jobs++;
					if (prev_end != 0 && r.gpu_start >= prev_end) {
						const uint64_t g = r.gpu_start - prev_end;
						if (g < 5'000'000ull) {
							idle += g;
							gaps++;
							if (g >= 100'000ull) { // 1 ms or more: the GPU waited for the host
								big++;
								big_t += g;
							}
						}
					} else if (prev_end != 0) {
						overlaps++;
					}
					if (r.gpu_end > prev_end) prev_end = r.gpu_end;
					if (r.gpu_end - win0 >= 100'000'000ull) {
						journal("job ts: %" PRIu64 " jobs in %.1f ms of GPU time line: busy %.1f ms, idle between jobs %.1f ms in %" PRIu64 " gaps (mean %.1f us; %" PRIu64 " of 1 ms or more, %.1f ms), %" PRIu64 " out of order\n",
						        jobs, static_cast<double>(r.gpu_end - win0) / 1e5, static_cast<double>(busy) / 1e5, static_cast<double>(idle) / 1e5, gaps,
						        gaps != 0 ? static_cast<double>(idle) / 1e2 / static_cast<double>(gaps) : 0.0, big, static_cast<double>(big_t) / 1e5, overlaps);
						win0 = busy = idle = jobs = gaps = overlaps = big = big_t = 0;
					}
				}
				g_fence_wait_since = 0;
			} else {
				r.rc = -125; // -ECANCELED: the device it was queued on is gone
			}
			if (r.timed_out) m11_keep_lost(); // exp 0401 e11 (tag m11): the lost jobs' label writes, before they are forgotten
			forget_label_writes(j.seq, r.ring, r.timed_out || r.rc == -125); // experiment 0055
			// experiment 0415 (fs415b): every job, also one that failed or timed out (its stamps are 0 then)
			fs415_job(j.n, j.kind, r.ring, j.num_dwords, j.filter, j.bo_count, j.prepare_ms, j.list_ms, j.cs_ms, j.fs_sub_ns, j.fs_ask_ns, j.fs_got_ns, j.queued_ns,
			          r.ok ? r.gpu_start : 0, r.ok ? r.gpu_end : 0, 'a', j.fs_open_ns, j.fs_why, j.fs_segs, j.fs_part_ns, j.fs_ds);
			const double total_ms = static_cast<double>(SoftCp::now_ns() - j.queued_ns) / 1e6 + j.cs_ms;
			frame_profile_done(index == 0, j.queued_ns, SoftCp::now_ns(), 0.0);
			if (!r.ok || (j.n & 0x3fu) == 0) journal("submit #%" PRIu64 " %s %u dwords at %p: pass %" PRIu64 " rewrite %" PRIu64 " drop %" PRIu64 " unmapped %" PRIu64 " cc %" PRIu64 " mappings %zu ... %s rc %d%s%s %.2f ms\n",
			        j.n, j.kind, j.num_dwords, j.ib, j.filter.passed, j.filter.rewritten, j.filter.dropped, j.filter.unmapped_drops, j.filter.context_control_rewrites,
			        j.maps, r.ok ? "OK" : "FAILED", r.rc, r.timed_out ? " TIMEOUT" : "", j.retried ? " (retried)" : "", total_ms);
			if (timing) {
				journal("timing: #%" PRIu64 " done at t %.3f s, %.1f ms after the sync and hints; device: prepare %.2f list %.2f cs %.2f fence %.2f ms, %u BOs%s\n", j.n,
				        timing_now(), static_cast<double>(SoftCp::now_ns() - j.t2_ns) / 1e6, j.prepare_ms, j.list_ms, j.cs_ms, total_ms - j.cs_ms, j.bo_count,
				        j.short_list ? " (short list)" : "");
			}
			if (r.ok && !j.ts_addrs.empty()) {
				const double k = ts_scale();
				for (const uint64_t a: j.ts_addrs) {
					auto* v = reinterpret_cast<volatile uint64_t*>(a);
					*v      = static_cast<uint64_t>(static_cast<double>(*v) * k);
				}
			}
			if (!r.ok) {
				failed = true;
				if (FILE* f = journal_min_file(true); f != nullptr) fsync(fileno(f));
			}
			if (!j.catch_slots.empty() && r.rc != -125) catch_check(j.catch_slots, r.timed_out, j.n, j.kind); // experiment 0401 series e
			if (r.timed_out && j.fl_plan.crumbs) fl_probe(j.fl_plan, j.n, j.kind, g_dev && j.dev_gen == g_dev_gen.load()); // experiment 0404: first, before the long probe
			if (!r.timed_out && r.ok && j.fl_plan.crumbs) fl_keep_done(j.fl_plan, j.n); // exp 0401 e7 (flx) A1: the last done draw, for a later timeout
			if (!r.timed_out && r.ok && j.fl_plan.crumbs) smp_sample(j.fl_plan, j.n, j.kind, g_dev && j.dev_gen == g_dev_gen.load()); // exp 0401 e8 (smp): the draws of a completed job, at most every N s
#ifndef BC5_LEAN // exp 0430: the probe is a diagnostic; the lean build has none of it
			if (r.timed_out && !j.ib_copy.empty()) timeout_probe(j.ib_copy.data(), static_cast<uint32_t>(j.ib_copy.size()), j.kind, j.n, &j.ran_copy, &j.ge_probe); // experiment 0160
#endif
			if (r.timed_out) {
				std::lock_guard lock(g_dev_mutex);
				if (j.dev_gen == g_dev_gen.load()) { // the other queue's thread may have been first
					g_recovering = true;
					g_dev_gen++; // what is still queued was queued on the old device
					recover_after_timeout(r);
					g_recovering = false;
				}
			}
			g_cq_fences--;
		} else {
			const uint64_t t_post = SoftCp::now_ns();
			SoftCp::t_wait_bound_ns = index == 0 ? soft_wait_ns() : 0ull; // experiment 0343
			it.post(failed);
			SoftCp::t_wait_bound_ns = 0;
			const double post_ms = static_cast<double>(SoftCp::now_ns() - t_post) / 1e6;
			if (index == 0) frame_profile_post(post_ms);
			if (post_ms >= 100.0) { // experiment 0343: exp 0341's hold was posts of 2 s on cq0, with no line
				static std::atomic<uint32_t> n_slow {0};
				if (n_slow++ < 1000) journal("slow post: t %.3f s cq%d %.1f ms; last replayed %s %u dwords at %p; soft-cp polls so far %" PRIu64 " (%.1f ms), timed out %" PRIu64 "\n",
				                             timing_now(), index, post_ms, SoftCp::t_cur_kind, SoftCp::t_cur_n, static_cast<const void*>(SoftCp::t_cur_buf),
				                             SoftCp::g_soft_polls.load(), static_cast<double>(SoftCp::g_soft_poll_ns.load()) / 1e6, SoftCp::g_soft_timeouts.load());
			}
			failed = false;
		}
		g_cq_items--;
	}
}

static void cq_push(CqItem&& it) {
	const int index = t_cq;
	Cq&       cq    = g_cqs[index];
	std::call_once(cq.started, [index] { std::thread(completion_thread, index).detach(); });
	{
		std::lock_guard lk(cq.mutex);
		g_cq_items++;
		if (it.fence) g_cq_fences++;
		cq.items.push_back(std::move(it));
	}
	cq.cv.notify_one();
}

static void post(std::function<void(bool failed)> fn) {
	if (!g_async) { // the job has been waited for at submission
		fn(false);
		return;
	}
	CqItem it;
	it.post = std::move(fn);
	cq_push(std::move(it));
}

static void drain() {
	chain_flush(5); // ADR 0010
	if (g_chain_mode >= 2) chain_flush_all(5); // section B: the flip may come from another thread than the submitting one
	if (!g_async) return;
	bc5::load_stat::Scope ls_scope(bc5::load_stat::kDrain); // experiment 0415 (ls415)
	while (g_cq_items.load() != 0) std::this_thread::sleep_for(std::chrono::microseconds(50));
}

// Experiment 0415 (fs415): the flip's line and the frame number the job lines carry.
static void fs415_flip(uint64_t called_ns) {
	FILE* fs = fs415_file();
	if (fs == nullptr) return;
	const uint64_t frame = g_fs415_frame.fetch_add(1, std::memory_order_relaxed) + 1;
	std::lock_guard fl(g_fs415_mutex);
	std::fprintf(fs, "f %" PRIu64 " %" PRIu64 " %" PRIu64 "\n", frame, called_ns, static_cast<uint64_t>(SoftCp::now_ns()));
	if ((frame & 63u) == 0) std::fflush(fs);
}

static void wait_jobs() {
	if (t_f16_slot != nullptr) t_f16_slot->f16_phase.store(4); // exp 0430 F16: a submit drains the GPU: no waiter may wait on it
	chain_flush(5); // ADR 0010
	if (!g_async || !g_dev) return;
	bc5::load_stat::Scope ls_scope(bc5::load_stat::kWaitJobs); // experiment 0415 (ls415)
	g_dev->wait_idle(2'000'000'000ull);
}

static bool async_on() {
	return g_async;
}

static bool on_game_thread() {
	return t_cq == 0;
}

static std::mutex g_fp_mutex;
static struct {
	double   sync_ms = 0, hints_ms = 0, prepare_ms = 0, list_ms = 0, cs_ms = 0, fence_ms = 0, cap_ms = 0, cpuwait_ms = 0, eqwait_ms = 0, post_ms = 0;
	double   pf_ms = 0, pt_ms = 0, pc_ms = 0, pn_ms = 0, pcopy_ms = 0; // the parts of prepare (experiment 0027)
	uint64_t jobs = 0, ring_jobs = 0, gpu_busy_ns = 0, last_done_ns = 0, posts = 0;
	std::thread::id render_thread;
	double   t_last_flip = 0;
} g_fp;
static const bool g_frame_profile_env = BC5_DIAG_ENV("BC5_DIRECT_FRAME_PROFILE") != nullptr;
// Off (or logging off for the session): one load, no counters.
static inline bool g_frame_profile_on() { return g_frame_profile_env && ::Log::Bc5LoggingOn(); }

static void frame_profile_wait(bool game_thread, bool cap, double ms) {
	if (bc5::load_stat::on()) bc5::load_stat::add(cap ? bc5::load_stat::kInflightCap : bc5::load_stat::kLabelWait, ms > 0 ? static_cast<uint64_t>(ms * 1e6) : 0); // experiment 0415 (ls415)
	if (!g_frame_profile_on() || !game_thread) return;
	std::lock_guard lock(g_fp_mutex);
	(cap ? g_fp.cap_ms : g_fp.cpuwait_ms) += ms;
}

static void frame_profile_prep(bool game_thread, double filter_ms, double tracker_ms, double cu_ms, double nested_ms, double copy_ms) {
	if (!g_frame_profile_on() || !game_thread) return;
	std::lock_guard lock(g_fp_mutex);
	g_fp.pf_ms += filter_ms;
	g_fp.pt_ms += tracker_ms;
	g_fp.pc_ms += cu_ms;
	g_fp.pn_ms += nested_ms;
	g_fp.pcopy_ms += copy_ms;
}

static void frame_profile_eqwait(double ms) {
	if (!g_frame_profile_on()) return;
	std::lock_guard lock(g_fp_mutex);
	if (std::this_thread::get_id() == g_fp.render_thread) g_fp.eqwait_ms += ms;
}

static void frame_profile_post(double ms) {
	if (!g_frame_profile_on()) return;
	std::lock_guard lock(g_fp_mutex);
	g_fp.post_ms += ms;
	g_fp.posts++;
}

static void frame_profile_submit(bool game_thread, double sync_ms, double hints_ms) {
	if (!g_frame_profile_on() || !game_thread) return;
	std::lock_guard lock(g_fp_mutex);
	g_fp.render_thread = std::this_thread::get_id();
	g_fp.sync_ms += sync_ms;
	g_fp.hints_ms += hints_ms;
}

static void frame_profile_job(bool game_thread, double prepare_ms, double list_ms, double cs_ms) {
	if (!g_frame_profile_on()) return;
	std::lock_guard lock(g_fp_mutex);
	if (game_thread) {
		g_fp.prepare_ms += prepare_ms;
		g_fp.list_ms += list_ms;
		g_fp.cs_ms += cs_ms;
		g_fp.jobs++;
	} else {
		g_fp.ring_jobs++;
	}
}

// GPU busy: the union of the jobs' [queued, done) intervals — a job queued while the previous one
// still ran only adds what is past that one's completion. Synchronously (done_ns == 0) the wait
// for the fence is the GPU's time, and it is the game thread's too.
static void frame_profile_done(bool game_thread, uint64_t queued_ns, uint64_t done_ns, double fence_ms) {
	if (!g_frame_profile_on()) return;
	std::lock_guard lock(g_fp_mutex);
	if (done_ns == 0) {
		g_fp.gpu_busy_ns += static_cast<uint64_t>(fence_ms * 1e6);
		if (game_thread) g_fp.fence_ms += fence_ms;
		return;
	}
	const uint64_t start = std::max(queued_ns, g_fp.last_done_ns);
	if (done_ns > start) g_fp.gpu_busy_ns += done_ns - start;
	if (done_ns > g_fp.last_done_ns) g_fp.last_done_ns = done_ns;
}

static void frame_profile_flip(double drain_ms) {
	if (!g_frame_profile_on()) return;
	std::lock_guard lock(g_fp_mutex);
	const double now = timing_now();
	// Experiment 0343: the soft CP's polls since the last flip (its counters are global: both completion threads and
	// the ring thread's own pass; the lines say which).
	static uint64_t sp0 = 0, st0 = 0, sn0 = 0;
	const uint64_t  sp = SoftCp::g_soft_polls.load(), st = SoftCp::g_soft_timeouts.load(), sn = SoftCp::g_soft_poll_ns.load();
	if (g_fp.t_last_flip != 0) {
		const double interval = (now - g_fp.t_last_flip) * 1e3;
		const double inside   = g_fp.sync_ms + g_fp.hints_ms + g_fp.prepare_ms + g_fp.list_ms + g_fp.cs_ms + g_fp.fence_ms + g_fp.cap_ms + g_fp.cpuwait_ms + g_fp.eqwait_ms;
		journal("frame profile: t %.3f s, %.1f ms since the last flip; game thread inside the host %.1f ms (sync %.1f, hints %.1f, prepare %.1f, list %.1f, cs %.1f, fence %.1f, cap %.1f, label waits %.1f, event waits %.1f), at the flip %.1f, outside %.1f; GPU busy %.1f ms in %" PRIu64 " jobs (+%" PRIu64 " from the ring thread); soft-CP passes %.1f ms in %" PRIu64 ", waits polled %" PRIu64 " (%.1f ms, %" PRIu64 " timed out); prepare = filter %.1f + tracker %.1f + cu %.1f + nested %.1f + copy %.1f\n",
		        now, interval, inside, g_fp.sync_ms, g_fp.hints_ms, g_fp.prepare_ms, g_fp.list_ms, g_fp.cs_ms, g_fp.fence_ms, g_fp.cap_ms, g_fp.cpuwait_ms, g_fp.eqwait_ms, drain_ms, interval - inside - drain_ms,
		        static_cast<double>(g_fp.gpu_busy_ns) / 1e6, g_fp.jobs, g_fp.ring_jobs, g_fp.post_ms, g_fp.posts, sp - sp0, static_cast<double>(sn - sn0) / 1e6, st - st0, g_fp.pf_ms, g_fp.pt_ms, g_fp.pc_ms, g_fp.pn_ms, g_fp.pcopy_ms);
	}
	g_fp.sync_ms = g_fp.hints_ms = g_fp.prepare_ms = g_fp.list_ms = g_fp.cs_ms = g_fp.fence_ms = g_fp.cap_ms = g_fp.cpuwait_ms = g_fp.eqwait_ms = g_fp.post_ms = 0;
	g_fp.jobs = g_fp.ring_jobs = g_fp.gpu_busy_ns = g_fp.posts = 0;
	sp0 = sp; // experiment 0343
	st0 = st;
	sn0 = sn;
	g_fp.pf_ms = g_fp.pt_ms = g_fp.pc_ms = g_fp.pn_ms = g_fp.pcopy_ms = 0;
	g_fp.t_last_flip = now;
}

// Experiment 0049: BC5_DIRECT_SHADER_DUMP=<dir> writes the code of every shader program a buffer
// points at, once, to <dir>/<address>.bin (64 KiB from the program's start, where mapped): the
// program registers SPI_SHADER_PGM_LO/HI_PS, _VS, _GS, _ES, _HS, _LS (SH offsets 0x08, 0x48, 0x88,
// 0xc8, 0x108, 0x148 from 0x2c00; Mesa sid.h) and COMPUTE_PGM_LO/HI (0x20c), as SET_SH_REG sets
// them or LOAD_SH_REG_INDEX loads them as (offset, value) pairs. For finding out which
// instructions a title uses (ray tracing); the files stay in the private capture directory.
static void shader_dump(const uint32_t* ib, uint32_t num_dwords, const std::vector<bc5::direct::Mapping>& maps) {
	static const char* dir = BC5_DIAG_ENV("BC5_DIRECT_SHADER_DUMP");
	if (dir == nullptr) return;
	static std::mutex                  m;
	static std::set<uint64_t>          seen;
	static std::map<uint32_t, uint32_t> lo; // SH offset of a LO register -> last value
	std::lock_guard<std::mutex>        lock(m);
	auto is_lo = [](uint32_t r) { return r == 0x08 || r == 0x48 || r == 0x88 || r == 0xc8 || r == 0x108 || r == 0x148 || r == 0x20c; };
	auto take  = [&](uint32_t r, uint32_t v) {
		if (is_lo(r)) {
			lo[r] = v;
			return;
		}
		if (!is_lo(r - 1) || lo.count(r - 1) == 0) return;
		const uint64_t a = (static_cast<uint64_t>(lo[r - 1]) << 8u) | (static_cast<uint64_t>(v & 0xffu) << 40u);
		if (a == 0 || !seen.insert(a).second) return;
		uint64_t n = 64ull << 10u;
		while (n > 4096 && !covered_sorted(maps, a, n)) n /= 2;
		if (!covered_sorted(maps, a, n)) return;
		char path[512];
		std::snprintf(path, sizeof(path), "%s/%010" PRIx64 ".bin", dir, a);
		if (FILE* f = std::fopen(path, "wb"); f != nullptr) {
			std::fwrite(reinterpret_cast<const void*>(a), 1, n, f);
			std::fclose(f);
		}
	};
	for (uint32_t q = 0; q < num_dwords;) {
		const uint32_t h    = ib[q];
		const uint32_t type = h >> 30u;
		uint32_t       len  = 1;
		if (type == 3 || type == 0) { const uint32_t c = (h >> 16u) & 0x3fffu; len = c == 0x3fffu ? 1 : c + 2; }
		if (q + len > num_dwords) break;
		const uint32_t op = (h >> 8u) & 0xffu;
		if (type == 3 && op == 0x76 && len >= 3) { // SET_SH_REG
			const uint32_t first = ib[q + 1] & 0xffffu;
			for (uint32_t k = 0; k + 2 < len; k++) take(first + k, ib[q + 2 + k]);
		} else if (type == 3 && op == 0x63 && len >= 5 && (ib[q + 3] >> 31u) != 0) { // LOAD_SH_REG_INDEX, pairs
			const uint64_t a = (ib[q + 1] & ~3u) | (static_cast<uint64_t>(ib[q + 2] & 0xffffu) << 32u);
			const uint32_t n = ib[q + 4] & 0x3fffu;
			if (a != 0 && n != 0 && covered_sorted(maps, a, static_cast<uint64_t>(n) * 8)) {
				const auto* t = reinterpret_cast<const volatile uint32_t*>(a);
				for (uint32_t k = 0; k < n; k++) take(t[2 * k] & 0xffffu, t[2 * k + 1]);
			}
		}
		q += len;
	}
}

// Experiment 0137 (BC5_DIRECT_LOOP_BOUND=<program hex>:<limit>:<dword offset>[,<offset>...]): a copy of
// the program in the device's code area (bc5::direct::Device::code_area, below 2^40), in which each
// listed back-edge (s_cbranch_execnz to an earlier instruction) jumps to a trampoline instead:
//   s_add_u32 s104, s104, 1 ; s_cmp_lt_u32 s104, <limit> ; s_cbranch_scc0 <after the back-edge> ;
//   s_cbranch_execnz <the loop head> ; s_branch <after the back-edge>
// and a prologue (s_mov_b32 s104, 0 ; s_branch <the program's start>) is the copy's entry. s104 is a
// register the program does not use (the second title's reflection traversal 0x11d049aa00 uses up to
// s101). Encodings: llvm-mc -triple=amdgcn -mcpu=gfx1013 -show-encoding. The program's own PC-relative
// data (s_getpc) lies inside the 64 KiB copied, so it moves with it. Returns the copy's address, 0
// when not configured or impossible.
static uint64_t loop_bound_copy(uint64_t pgm) {
	// Experiment 0141 (BC5_DIRECT_BVH_MISS=<program hex>:<dword offset>[,...]): the listed
	// image_bvh_intersect_ray instructions (MIMG NSA, 5 dwords on gfx1013: [0xF1989F07, vdata in bits
	// 15:8 of the second dword, ...]) become four v_mov_b32 v<vdata+k>, -1 and an s_nop: every query
	// returns no child and no hit (0xffffffff, Mesa RADV_BVH_INVALID_NODE), so a ray-traced pass runs
	// to its end and writes "nothing hit" instead of walking trees. Encodings from llvm-mc -show-encoding.
	{
		struct Miss {
			uint64_t              pgm = 0;
			std::vector<uint32_t> at;
		};
		static const Miss miss = [] {
			Miss        m;
			const char* e = BC5_DIAG_ENV("BC5_DIRECT_BVH_MISS");
			if (e == nullptr) return m;
			char* end = nullptr;
			m.pgm     = std::strtoull(e, &end, 16);
			while (end != nullptr && (*end == ':' || *end == ',')) {
				const char* q = end + 1;
				const auto  v = static_cast<uint32_t>(std::strtoul(q, &end, 0));
				if (end == q) break;
				m.at.push_back(v);
			}
			return m;
		}();
		if (miss.pgm != 0 && pgm == miss.pgm && g_dev) {
			static std::mutex           mm;
			static bc5::direct::Device* built_for = nullptr;
			static uint64_t             built_va  = 0;
			std::lock_guard             lk(mm);
			if (built_for == g_dev.get()) return built_va;
			built_for              = g_dev.get();
			constexpr uint32_t kCp = 0x10000 / 4;
			auto*              code = static_cast<volatile uint32_t*>(g_dev->code_area());
			if (code == nullptr) return built_va = 0;
			std::vector<uint32_t> w(kCp);
			const auto*           src = reinterpret_cast<const volatile uint32_t*>(pgm);
			for (uint32_t k = 0; k < kCp; k++) w[k] = src[k];
			for (const uint32_t at: miss.at) {
				if (at + 5 > kCp || w[at] != 0xF1989F07u) {
					journal("bvh miss: dword %u of program 0x%" PRIx64 " is 0x%08x, not image_bvh_intersect_ray; not patched\n", at, pgm, at < kCp ? w[at] : 0u);
					return built_va = 0;
				}
				const uint32_t vd = (w[at + 1] >> 8u) & 0xffu;
				for (uint32_t k = 0; k < 4; k++) w[at + k] = 0x7E0002C1u | ((vd + k) << 17u); // v_mov_b32 v<vd+k>, -1
				w[at + 4] = 0xBF800000u;                                                      // s_nop 0
			}
			for (uint32_t k = 0; k < kCp; k++) code[k] = w[k];
			std::atomic_thread_fence(std::memory_order_seq_cst);
			built_va = bc5::direct::Device::kCodeVa;
			journal("bvh miss: program 0x%" PRIx64 " copied to 0x%" PRIx64 ", %zu ray queries return nothing\n", pgm, built_va, miss.at.size());
			return built_va;
		}
	}
	struct Cfg {
		uint64_t              pgm   = 0;
		uint32_t              limit = 0;
		std::vector<uint32_t> at;
	};
	static const Cfg cfg = [] {
		Cfg c;
		const char* e = BC5_DIAG_ENV("BC5_DIRECT_LOOP_BOUND");
		if (e == nullptr) return c;
		char* end = nullptr;
		c.pgm     = std::strtoull(e, &end, 16);
		if (end == nullptr || *end != ':') return Cfg {};
		c.limit = static_cast<uint32_t>(std::strtoul(end + 1, &end, 0));
		while (end != nullptr && (*end == ':' || *end == ',')) {
			const char* q = end + 1;
			const auto  v = static_cast<uint32_t>(std::strtoul(q, &end, 0));
			if (end == q) break;
			c.at.push_back(v);
		}
		return c;
	}();
	if (cfg.pgm == 0 || pgm != cfg.pgm || !g_dev) return 0;
	static std::mutex                   m;
	static bc5::direct::Device*         built_for = nullptr;
	static uint64_t                     built_va  = 0;
	std::lock_guard                     lk(m);
	if (built_for == g_dev.get()) return built_va;
	constexpr uint32_t kCopy = 0x10000 / 4; // dwords copied (64 KiB, as dumped from the title's memory)
	auto*              code  = static_cast<volatile uint32_t*>(g_dev->code_area());
	if (code == nullptr) {
		journal("loop bound: no code area\n");
		built_for = g_dev.get();
		return built_va = 0;
	}
	std::vector<uint32_t> w(kCopy);
	const auto*           src = reinterpret_cast<const volatile uint32_t*>(pgm);
	for (uint32_t k = 0; k < kCopy; k++) w[k] = src[k];
	auto sopp = [](uint32_t op, uint32_t from, uint32_t to) { // branch at dword `from` to dword `to`
		return 0xBF800000u | (op << 16u) | (static_cast<uint32_t>(static_cast<int32_t>(to) - static_cast<int32_t>(from + 1)) & 0xffffu);
	};
	// Per-wave counters: dword (HW_ID1 & 0xfffff) of the table at kCodeVa + 4 MiB, read and written with
	// scalar memory instructions (GFX10 still has s_store_dword). s102-s105 are free in the program.
	// Encodings from llvm-mc -triple=amdgcn -mcpu=gfx1013 -show-encoding.
	const uint64_t table = bc5::direct::Device::kCodeVa + (4ull << 20);
	auto addr = [&](std::vector<uint32_t>& v, uint32_t at) {
		const uint32_t seq[] = {0xB968F817u,                                // s_getreg_b32 s104, hwreg(HW_REG_HW_ID1)
		                        0x8768FF68u, 0x000FFFFFu,                    // s_and_b32 s104, s104, 0xfffff
		                        0x8F688268u,                                 // s_lshl_b32 s104, s104, 2
		                        0xBEE603FFu, static_cast<uint32_t>(table),   // s_mov_b32 s102, <table lo>
		                        0xBEE703FFu, static_cast<uint32_t>(table >> 32u)}; // s_mov_b32 s103, <table hi>
		for (uint32_t k = 0; k < 8; k++) v[at + k] = seq[k];
		return at + 8;
	};
	w.resize(kCopy + 12 + 19 * cfg.at.size());
	const uint32_t pro = kCopy;
	uint32_t       x   = addr(w, pro);
	w[x++]             = 0xBEE90380u;                // s_mov_b32 s105, 0
	w[x++]             = 0xF4411A73u;                // s_store_dword s105, s[102:103], s104 glc
	w[x++]             = 0xD0000000u;
	w[x]               = sopp(2, x, 0);              // s_branch <the program's start>
	x++;
	uint32_t t = x;
	// The wave ends over the limit: the program's s_endpgm (the traversal has no barrier, so a wave that
	// leaves early holds no other back).
	uint32_t endpgm = 0;
	while (endpgm < kCopy && w[endpgm] != 0xBF810000u) endpgm++;
	for (const uint32_t at: cfg.at) {
		const uint32_t ins = w[at];
		const uint32_t op  = (ins >> 16u) & 0x7fu;
		// backward SOPP branches: s_branch (2), s_cbranch_scc0/scc1/vccz/vccnz/execz/execnz (4-9)
		if (at >= endpgm || (ins & 0xFF800000u) != 0xBF800000u || (op != 2 && (op < 4 || op > 9)) || (ins & 0x8000u) == 0) {
			journal("loop bound: dword %u of program 0x%" PRIx64 " is 0x%08x, not a backward branch; not patched\n", at, pgm, ins);
			built_for = g_dev.get();
			return built_va = 0;
		}
		const uint32_t head = at + 1 + static_cast<uint32_t>(static_cast<int32_t>(static_cast<int16_t>(ins & 0xffffu)));
		w[at]      = sopp(2, at, t); // the back-edge now goes to the trampoline
		uint32_t y = addr(w, t);
		w[y++]     = 0xF4001A73u; w[y++] = 0xD0000000u; // s_load_dword s105, s[102:103], s104
		w[y++]     = 0xBF8CC07Fu;                          // s_waitcnt lgkmcnt(0)
		w[y++]     = 0x80698169u;                          // s_add_u32 s105, s105, 1
		w[y++]     = 0xF4411A73u; w[y++] = 0xD0000000u; // s_store_dword s105, s[102:103], s104 glc
		w[y++]     = 0xBF0AFF69u; w[y++] = cfg.limit;      // s_cmp_lt_u32 s105, <limit>
		w[y]       = sopp(4, y, endpgm); y++;              // s_cbranch_scc0: over the limit, the wave ends
		w[y]       = sopp(op, y, head); y++;               // the original branch (an SCC one is refused below)
		w[y]       = sopp(2, y, at + 1); y++;              // else fall through as before
		if (op == 4 || op == 5) {
			journal("loop bound: dword %u is an SCC branch, which the counter's compare would clobber; not patched\n", at);
			built_for = g_dev.get();
			return built_va = 0;
		}
		t = y;
	}
	for (size_t k = 0; k < w.size(); k++) code[k] = w[k];
	std::atomic_thread_fence(std::memory_order_seq_cst);
	built_for = g_dev.get();
	built_va  = bc5::direct::Device::kCodeVa + static_cast<uint64_t>(pro) * 4u;
	journal("loop bound: program 0x%" PRIx64 " copied to 0x%" PRIx64 " (entry 0x%" PRIx64 "), %zu back-edges bounded at %u iterations\n", pgm, bc5::direct::Device::kCodeVa, built_va,
	        cfg.at.size(), cfg.limit);
	return built_va;
}

// Experiment 0190 (BC5_DIRECT_FLAT_APERTURE=1, or a comma list of program addresses in hex): the second
// title's ray-traced-reflection traversals push their per-lane BVH stack with FLAT stores whose address
// high dword comes from two constants, the console's apertures: s_brev_b32 sN, 1 (0x80000000, LDS) and the
// literal of v_med3_u32 vD, sN, 0x70000000, <packed stack pointer> (0x70000000, private; the median picks
// the LDS one while the pointer's high half is negative). They pop it with ds_read_b32 / scratch_load_dword.
// Under amdgpu the graphics VMIDs' apertures are 0x2000'0000'0000'0000 (LDS) and 0x1000'0000'0000'0000
// (private) (Linux gmc_v10_0.c gmc_v10_0_early_init; gfx_v10_0.c, the SH_MEM_BASES loop; the waves' own
// src_shared_base / src_private_base read 0x2000 / 0x1000, exp 0190), so a push leaves both apertures, the
// wave takes a memory violation (SQ_WAVE_TRAPSTS EXCP bit 8) and is halted (SQ_WAVE_STATUS FATAL_HALT):
// its dispatch never ends, the "endless traversal" of F113-F248. This rewrites in place, in the title's
// code before the program's first dispatch, each such literal to 0x10000000 and the s_brev_b32 operand 1
// to 4 (0x20000000): the same median with the host's apertures. Off by default (D16).
// Encodings: llvm-mc -triple=amdgcn -mcpu=gfx1013 -show-encoding.
static void flat_aperture_fix(uint64_t pgm, const std::vector<bc5::direct::Mapping>& maps) {
	struct Cfg {
		bool               on = false, all = false;
		std::set<uint64_t> list;
	};
	static const Cfg cfg = [] {
		Cfg         c;
		const char* e = std::getenv("BC5_DIRECT_FLAT_APERTURE");
		if (e == nullptr || *e == 0 || std::strcmp(e, "0") == 0) return c;
		c.on = true;
		if (std::strcmp(e, "1") == 0 || std::strcmp(e, "all") == 0) {
			c.all = true;
			return c;
		}
		for (const char* q = e; *q != 0;) {
			char*          end = nullptr;
			const uint64_t x   = std::strtoull(q, &end, 16);
			if (end == q) break;
			c.list.insert(x);
			q = (*end == ',') ? end + 1 : end;
		}
		return c;
	}();
	if (!cfg.on || pgm == 0 || (!cfg.all && cfg.list.count(pgm) == 0)) return;
	thread_local uint64_t last = 0;
	if (pgm == last) return;
	last = pgm;
	static std::mutex         m;
	static std::set<uint64_t> seen;
	std::lock_guard           lk(m);
	if (!seen.insert(pgm).second) return;
	uint32_t n = 0x10000 / 4; // the 64 KiB window shader_dump copies, as far as it is mapped
	while (n >= 0x400 && !covered_sorted(maps, pgm, static_cast<uint64_t>(n) * 4)) n -= 0x400;
	if (n < 0x400) return;
	auto*    w   = reinterpret_cast<volatile uint32_t*>(pgm);
	uint32_t end = 0;
	while (end < n && w[end] != 0xBF810000u) end++; // up to the program's s_endpgm
	uint32_t sites = 0, brevs = 0;
	for (uint32_t k = 0; k + 2 < end; k++) {
		const uint32_t d0 = w[k], d1 = w[k + 1], s = d1 & 0x1ffu;
		// v_med3_u32 (VOP3, no modifiers) with src1 the literal 0x70000000 and src0 an SGPR
		if ((d0 & 0xffffff00u) != 0xD5590000u || ((d1 >> 9u) & 0x1ffu) != 0xffu || w[k + 2] != 0x70000000u || s > 105u) continue;
		// the s_brev_b32 s<src0>, 1 that makes its LDS half, up to 1,024 dwords before
		uint32_t at = 0;
		for (uint32_t j = k; j-- > 0 && k - j <= 1024u;) {
			if (w[j] == (0xBE800B81u | (s << 16u)) || w[j] == (0xBE800B84u | (s << 16u))) {
				at = j + 1;
				break;
			}
		}
		if (at == 0) continue;
		if (w[at - 1] != (0xBE800B84u | (s << 16u))) {
			w[at - 1] = 0xBE800B84u | (s << 16u); // s_brev_b32 s<src0>, 4 = 0x20000000
			brevs++;
		}
		w[k + 2] = 0x10000000u;
		sites++;
		k += 2;
	}
	std::atomic_thread_fence(std::memory_order_seq_cst);
	if (sites != 0)
		journal("flat aperture: program 0x%" PRIx64 ": %u stack pushes (%u s_brev_b32) now address the host's LDS/private apertures\n", pgm, sites, brevs);
}

static void submit_one(const uint32_t* ib, uint32_t num_dwords, const char* kind) {
	if (g_stage == Stage::Off || !g_dev || ib == nullptr || num_dwords == 0) {
		return;
	}
	if (chain_on()) { // ADR 0010: appended; submitted with the call's other buffers
		const bool host_built = std::strstr(kind, "-state") != nullptr;
		chain_append(nullptr, 0, ib, num_dwords, kind, host_built);
		return;
	}
	submit_now(ib, num_dwords, kind, job_ring(kind), nullptr);
}

// Experiment 0436 (tag su436): the kernel submit (DRM_IOCTL_AMDGPU_CS) outside the device mutex (exp 0432 note 8;
// built in with no switch, 2026-11-20). A job is prepared under g_dev_mutex as before (probe, syncs, ud434's imports, hints, the
// backend's prepare); for the CS ioctl alone the backend lets its own lock go and calls back here to let g_dev_mutex go,
// then the device mutex is taken again for everything after the call (EFAULT retry, label writes, ho430's job record,
// the completion queue), so all of that keeps its order relative to the call. The jobs of one ring keep their order
// through a lock per ring (GFX, compute 0-3), taken before g_dev_mutex and held to the end of submit_now: the same ring's
// next job cannot be prepared before this one is in the kernel and recorded. A chain's F10 flight set is cleared after
// submit_now returns, as before, so F10/F16/F18 see the writer in flight for the whole time. Mapping removals wait in
// the backend until no prepared job is in its kernel call (flight lock), so the mappings a job was prepared against are
// still there when the kernel takes it. Async mode only (g_async); in sync mode the call stays under both locks.
static std::mutex            g_su436_ring_mu[bc5::direct::kComputeRings + 1]; // [kComputeRings] is the GFX ring
#ifndef BC5_LEAN
static std::atomic<uint64_t> g_su436_calls {0}; // kernel calls made outside the device mutex (normal build only)
#endif

static void submit_now(const uint32_t* ib, uint32_t num_dwords, const char* kind, int ring, const Chain* chain) {
	if (g_stage == Stage::Off || !g_dev || ib == nullptr || num_dwords == 0) {
		return;
	}
	const int qring = ring; // ADR 0009: the compute ring takes the MEC form as it is
	const uint64_t fs_sub = fs415_file() != nullptr ? SoftCp::now_ns() : 0; // experiment 0415 (fs415b): submit_now entered
	const uint64_t fs_open = t_fs415_open_ns;                               // experiment 0415 (fs415c): the chain's first segment (0: no chain)
	const int      fs_why  = t_fs415_why;
	const uint32_t fs_segs = t_fs415_segs;
	t_fs415_open_ns = 0;
	t_fs415_why     = -1;
	t_fs415_segs    = 0;
	if (g_async) {
		// Experiment 0045: 24 jobs in flight before the game's
		// thread waits; with the flip deferred (BC5_DIRECT_FLIP_DEFER=1) the thread can then run
		// ahead of a GPU-bound frame instead of letting the queue drain (experiment 0028).
		static constexpr uint32_t max_in_flight = 24;
		const uint64_t t_cap = SoftCp::now_ns();
		while (g_cq_fences.load() >= max_in_flight || g_recovering.load()) std::this_thread::sleep_for(std::chrono::microseconds(50));
		frame_profile_wait(t_cq == 0, true, static_cast<double>(SoftCp::now_ns() - t_cap) / 1e6);
	}
	bc5::load_stat::delay(bc5::load_stat::kDevLockWait); // experiment 0415 (ls415): a delay outside the lock, measurement only
	const uint64_t  ls_w0 = bc5::load_stat::begin();
	if (t_f16_slot != nullptr) t_f16_slot->f16_phase.store(2); // exp 0430 F16: past the back-pressure, asking for the device
	const uint64_t  fs_ask = fs415_file() != nullptr ? SoftCp::now_ns() : 0; // experiment 0415 (fs415b)
	// exp 0436 (tag su436): this ring's order, before the device mutex (lock order: ring, g_dev_mutex, backend)
	const bool su = g_async && (qring == bc5::direct::kGfxRing || (qring >= 0 && qring < bc5::direct::kComputeRings));
	std::unique_lock<std::mutex> su_ring;
	if (su) su_ring = std::unique_lock<std::mutex>(g_su436_ring_mu[qring == bc5::direct::kGfxRing ? bc5::direct::kComputeRings : qring]);
	std::unique_lock<std::mutex> lock(g_dev_mutex);
	if (t_f16_slot != nullptr) t_f16_slot->f16_phase.store(3); // exp 0430 F16
	const uint64_t  fs_got = fs_ask != 0 ? SoftCp::now_ns() : 0;
	bc5::load_stat::end(bc5::load_stat::kDevLockWait, ls_w0);
	bc5::load_stat::Scope ls_hold(bc5::load_stat::kDevLockHold);
	if (g_dev->wedged()) {
		return;
	}
	// Unthrottled: the game writes a DCB's register tables right before submitting it, and a
	// table the sync has not seen yet is a NOP-ed LOAD on the GPU and an invisible render
	// target for the hint mapper (run 29: 52 unmapped operands in the first frame DCB).
	// BC5_DIRECT_TIMING=1: where a submission's wall-clock time goes (run 77: ~1 s between the
	// game's submissions) — seconds since the first submission, then the host's own steps.
	static const bool timing_env = BC5_DIAG_ENV("BC5_DIRECT_TIMING") != nullptr;
	const bool timing = timing_env && ::Log::Bc5LoggingOn();
	const double   t_start = timing_now();
	const uint64_t t0 = SoftCp::now_ns();
	// The forced sync (a walk over the guest's 13 GB of VMAs, ~11 ms) is for what the filter
	// cannot see: memory the shaders of this IB will read. An IB without draws, dispatches and
	// nested IBs touches only its packets' operands; when the mappings already cover them all,
	// the throttled sync is enough (run 82).
	bool force_sync = true;
	bool urgent_sync = false;
	// Experiment 0103: BC5_DIRECT_REMEMBER_UNMAPPED=1 — a light IB whose only unmapped operands lie in
	// pages a forced sync left unmapped less than 2 s ago does not force the next one: the packet is
	// dropped either way. The second title's (and ASTRO BOT's) 84-dword DCB after every flip has one
	// such operand and cost a 9 ms walk a frame (run 372).
	static const bool remember_unmapped = bc5::env_on(std::getenv("BC5_DIRECT_REMEMBER_UNMAPPED")); // exp 0419: "=0" is off
	static std::map<uint64_t, double> lazy_unmapped;
	std::vector<uint64_t> lazy_pages;
	{
		bool heavy = false;
		for (uint32_t i = 0; i < num_dwords && !heavy;) {
			const uint32_t h = ib[i];
			const uint32_t type = h >> 30u;
			const uint32_t c = (h >> 16u) & 0x3fffu;
			uint32_t len = 1;
			if (type == 3 || type == 0) len = c == 0x3fffu ? 1 : c + 2;
			if (type == 3 && c != 0x3fffu) {
				const auto op = static_cast<uint8_t>((h >> 8u) & 0xffu);
				heavy = bc5::policy::is_draw_or_dispatch(op) || op == 0x3f || op == 0x33;
			}
			i += len;
		}
		if (!heavy) {
			const auto                 have_p = g_dev->sorted_mappings(); // experiment 0037
			bc5::policy::FilterOptions probe;
			probe.mapped = [&have_p](uint64_t a, uint64_t bytes) { return covered_sorted(*have_p, a, bytes); };
			std::vector<uint32_t> scratch(num_dwords);
			bc5::policy::FilterStats st;
			bc5::policy::filter(bc5::policy::Policy::builtin(), std::span<const uint32_t>(ib, num_dwords), scratch, probe, st);
			force_sync = st.unmapped_drops != 0;
			if (force_sync && remember_unmapped) {
				for (uint32_t q = 0; q < num_dwords;) {
					const uint32_t h   = ib[q];
					uint32_t       len = 1;
					if ((h >> 30u) == 3 || (h >> 30u) == 0) { const uint32_t c = (h >> 16u) & 0x3fffu; len = c == 0x3fffu ? 1 : c + 2; }
					if (q + len > num_dwords) break;
					if ((h >> 30u) == 3) {
						for (const auto& [a, bytes]: bc5::policy::memory_operands(ib + q, len)) {
							if (!covered_sorted(*have_p, a, bytes == 0 ? 4 : bytes)) lazy_pages.push_back(a & ~0xfffull);
						}
					}
					q += len;
				}
				const double now   = timing_now();
				bool         known = !lazy_pages.empty();
				for (const uint64_t pg: lazy_pages) {
					const auto it = lazy_unmapped.find(pg);
					if (it == lazy_unmapped.end() || now - it->second > 2.0) known = false;
				}
				if (known) {
					force_sync = false;
					lazy_pages.clear();
				}
			}
			urgent_sync = force_sync;
		}
	}
	for (uint64_t& v: t_fs415_ds) v = 0; // experiment 0415 (fs415d)
	ww412_packets(ib, num_dwords); // exp 0412 (tag ww412)
	k1f412_pass(ib, num_dwords, kind); // exp 0412 (tag k1f412)
	dt412_pass(ib, num_dwords, kind); // exp 0412 (tag dt412): before the mappings are synced
	const uint64_t ta = SoftCp::now_ns();
	sync_mappings(force_sync, urgent_sync);
	const uint64_t tb = SoftCp::now_ns();
	direct_sync(force_sync);
	if (!lazy_pages.empty()) { // experiment 0103: the pages this forced sync left unmapped
		const auto   after = g_dev->sorted_mappings();
		const double now   = timing_now();
		for (const uint64_t pg: lazy_pages) {
			if (covered_sorted(*after, pg, 4)) continue;
			const bool fresh = lazy_unmapped.count(pg) == 0;
			lazy_unmapped[pg] = now;
			if (fresh) journal("remember unmapped: %s %u dwords, operand page 0x%" PRIx64 " stays unmapped after a forced sync\n", kind, num_dwords, pg);
		}
	}
	const uint64_t t1 = SoftCp::now_ns();
	uint64_t       fs_ds[8]; // experiment 0415 (fs415d): the parts of the two syncs of this submission
	for (int k = 0; k < 8; k++) fs_ds[k] = t_fs415_ds[k];
	{ // exp 0412 (tag nl412): say once what is left of the learned pass
		static bool nl412_said = false;
		if (!nl412_said) {
			nl412_said = true;
			journal("learned windows: removed from this build (exp 0412, tag nl412, guards kept): no file is read, no window is applied; the 2 MiB zero guard behind each eager heap stays unless BC5_DIRECT_HEAP_GUARDS=0 (exp 0417; stderr says which); a GPU fault is journaled as \"would learn\" and adds nothing\n");
		}
	}
	if (!guard0412_defer_apply()) learned_apply(); // exp 0412 (tag g412): BC5_GUARD_APPLY_MIN_MS
	const uint64_t tc = SoftCp::now_ns();
	if (tc - t1 > 20'000'000ull) { // experiment 0156: a long learned_apply call, with its thread
		char tn[32] = {};
		pthread_getname_np(pthread_self(), tn, sizeof(tn));
		journal("learned_apply took %.1f ms on %s (layout gen %" PRIu64 ")\n", static_cast<double>(tc - t1) / 1e6, tn, static_cast<uint64_t>(g_layout_gen));
	}
	hint_targets(ib, num_dwords);
	const uint64_t t2 = SoftCp::now_ns();
#ifndef BC5_LEAN
	{ // exp 0432: the sync + hints part of every submission ("prepare" here), and the counters at most every 10 s
		d432::g_sync_ns += t2 - t0;
		d432::maxed(d432::g_prep_max_ns, t2 - t0);
		if (t2 - t0 > 20'000'000ull) d432::g_prep_over20++;
		uint64_t was = d432::g_last_ns.load(std::memory_order_relaxed);
		if (t2 - was >= 10'000'000'000ull && d432::g_last_ns.compare_exchange_strong(was, t2)) {
			char line[1600];
			std::snprintf(line, sizeof(line),
			              "exp 0432 (tag d432): t %.1f s: unmap-nowait %s, anon-events %s, anon-thread %s, views-kept %s; sync+hints of all submissions %.1f s, longest %.1f ms, over 20 ms %" PRIu64
			              "; rebuilds that change mappings %" PRIu64 ", with a ring busy %" PRIu64 "; mappings dropped %" PRIu64 ", while busy %" PRIu64 ", BOs retired while busy %" PRIu64
			              "; blocking drains %" PRIu64 ", %.1f ms in all, longest %.1f ms; anon walks %" PRIu64 " (asked by the counter %" PRIu64 "), left out %" PRIu64 ", event misses %" PRIu64
			              ", anonymous guest VMAs %" PRIu64 "; view builds %" PRIu64 ", list copies %" PRIu64 ", record mismatches %" PRIu64 "; maps-fast %s: merged %" PRIu64 ", sorted %" PRIu64 "; maps-diff %s: by diff %" PRIu64 ", the old way %" PRIu64 ", views changed %" PRIu64 ", mismatches %" PRIu64
			              " (the old way because: retired %" PRIu64 ", new BOs %" PRIu64 ", cap %" PRIu64 ", k1r %" PRIu64 ", zero list %" PRIu64 ", zero new %" PRIu64
			              ", not plain %" PRIu64 ", no list %" PRIu64 ", sig %" PRIu64 ", old unsorted %" PRIu64 ", new unsorted %" PRIu64 ")",
			              timing_now(), d432::on() ? "ON" : "off", d432::anon_events() ? "ON" : "off", d432::anon_thread() ? "ON" : "off", d432::views_kept() ? "ON" : "off",
			              static_cast<double>(d432::g_sync_ns.load()) / 1e9, static_cast<double>(d432::g_prep_max_ns.load()) / 1e6, d432::g_prep_over20.load(), d432::g_rebuilds.load(),
			              d432::g_busy.load(), d432::g_unmaps.load(), d432::g_unmaps_busy.load(), d432::g_bos_busy.load(), d432::g_drains.load(),
			              static_cast<double>(d432::g_drain_ns.load()) / 1e6, static_cast<double>(d432::g_drain_max_ns.load()) / 1e6, d432::g_anon_walks.load(), d432::g_anon_ev.load(),
			              d432::g_anon_skips.load(), d432::g_anon_ev_miss.load(), d432::g_anon_vmas.load(), static_cast<uint64_t>(g_views_builds), d432::g_views_clone.load(),
			              d432::g_rec_mismatch.load(), d432::maps_fast() ? "ON" : "off", d432::g_maps_fast.load(), d432::g_maps_sorted.load(),
			              d432::maps_diff() == 2 ? "VERIFY" : d432::maps_diff() == 1 ? "ON" : "off", d432::g_x_diff.load(), d432::g_x_full.load(), d432::g_x_views.load(),
			              d432::g_x_mismatch.load(), d432::g_x_why[0].load(), d432::g_x_why[1].load(), d432::g_x_why[2].load(), d432::g_x_why[3].load(), d432::g_x_why[4].load(),
			              d432::g_x_why[5].load(), d432::g_x_why[6].load(), d432::g_x_why[7].load(), d432::g_x_why[8].load(), d432::g_x_why[9].load(), d432::g_x_why[10].load());
			std::fprintf(stderr, "[bc5] %s\n", line);
			journal("%s\n", line);
			journal("exp 0437 (tag vg437): t %.1f s: views-gen %s; range table generation %" PRIu64 ", direct generation %" PRIu64 ", view builds %" PRIu64 "\n", timing_now(),
			        vg437_on() ? "ON" : "off", Libs::LibKernel::Memory::Bc5MappedRangesGeneration(), Libs::LibKernel::Memory::Bc5DirectRangesGeneration(),
			        static_cast<uint64_t>(g_views_builds));
		}
	}
#endif
	if (bc5::load_stat::on()) { // experiment 0415 (ls415c): the hold by part
		bc5::load_stat::add(bc5::load_stat::kHoldProbe, ta - t0);
		bc5::load_stat::add(bc5::load_stat::kHoldHints, t2 - tc);
	}
	if (timing) { // the split of "sync" and "hints", every 128 submissions (experiment 0022, step 3)
		static uint64_t acc[5] = {}, count = 0;
		acc[0] += ta - t0;
		acc[1] += tb - ta;
		acc[2] += t1 - tb;
		acc[3] += tc - t1;
		acc[4] += t2 - tc;
		if ((++count & 127u) == 0) {
			journal("timing split over 128 submissions: probe %.1f ms, anon sync %.1f, direct sync %.1f (views %.1f; %" PRIu64 " full, %" PRIu64 " fast; scan %.1f, merge %.1f, drain %.1f in %" PRIu64 ", maps %.1f = want %.1f + drop %.1f + zero %.1f + add %.1f), learned %.1f, hints %.1f\n",
			        static_cast<double>(acc[0]) / 1e6, static_cast<double>(acc[1]) / 1e6, static_cast<double>(acc[2]) / 1e6, static_cast<double>(g_dprof_views_ns) / 1e6, g_dprof_full,
			        g_dprof_fast, static_cast<double>(g_dprof_scan_ns) / 1e6, static_cast<double>(g_dprof_merge_ns) / 1e6, static_cast<double>(g_dprof_drain_ns) / 1e6, g_dprof_drains,
			        static_cast<double>(g_dprof_maps_ns) / 1e6, static_cast<double>(g_dprof_want_ns) / 1e6, static_cast<double>(g_dprof_drop_ns) / 1e6,
			        static_cast<double>(g_dprof_scratch_ns) / 1e6, static_cast<double>(g_dprof_add_ns) / 1e6, static_cast<double>(acc[3]) / 1e6, static_cast<double>(acc[4]) / 1e6);
			g_dprof_want_ns = g_dprof_drop_ns = g_dprof_scratch_ns = g_dprof_add_ns = 0;
			g_dprof_views_ns = 0;
			g_dprof_scan_ns = g_dprof_merge_ns = g_dprof_drain_ns = g_dprof_maps_ns = g_dprof_drains = 0; // experiment 0169
			g_dprof_full     = 0;
			g_dprof_fast     = 0;
			for (auto& a: acc) a = 0;
		}
	}
	frame_profile_submit(t_cq == 0, static_cast<double>(t1 - t0) / 1e6, static_cast<double>(t2 - t1) / 1e6);
	if (timing) {
		journal("timing: t %.3f s %s %u dwords: sync%s %.1f ms, hints %.1f ms q%d\n", t_start, kind, num_dwords, force_sync ? "" : " (lazy)",
		        static_cast<double>(t1 - t0) / 1e6, static_cast<double>(t2 - t1) / 1e6, t_queue_idx);
	}
	// Experiment 0109: the mapping list is copied only when BC5_DIRECT_SHADER_DUMP is set; the copy
	// (thousands of entries) ran under g_dev_mutex on every submission (stack samples, run 397).
	static const bool dump_shaders_on = BC5_DIAG_ENV("BC5_DIRECT_SHADER_DUMP") != nullptr;
	if (dump_shaders_on) dump_shaders(ib, num_dwords, g_dev->mappings());
	// Every memory operand must lie inside a userptr mapping, or the packet is NOP-ed: a GPU
	// page fault on the BC-250 ends in a reset that takes the machine down (F6, experiment 0016).
	// Experiment 0037: the device keeps this list sorted and rebuilds it only when a mapping
	// changes (a copy and a sort of 12,000 mappings per submission before).
	zpoll412_submit(); // exp 0412 (tag zp412)
	aliases_apply(false); // experiment 0056
	// Experiment 0057: BC5_DIRECT_IB_DUMP=<min>:<max>:<t0>:<count>[:<dir>] writes the first <count>
	// buffers of <min>..<max> dwords submitted from <t0> s on, as the game wrote them, to
	// <dir>/ib-<submission>-<kind>-<dwords>.bin (default: the capture directory). For offline
	// decoding (bc5-agc) of the buffer that hangs; the files stay private.
	{
		static const auto ibd = [] {
			struct Cfg {
				uint32_t    lo = 0, hi = 0, count = 0;
				double      t0 = 0;
				std::string dir;
			} c;
			if (const char* e = BC5_DIAG_ENV("BC5_DIRECT_IB_DUMP"); e != nullptr) {
				char dir[400] = {};
				const int n = std::sscanf(e, "%u:%u:%lf:%u:%399s", &c.lo, &c.hi, &c.t0, &c.count, dir);
				if (n >= 4) c.dir = n == 5 ? std::string(dir) : g_dump_dir;
			}
			return c;
		}();
		static std::atomic<uint32_t> ibd_n {0};
		const bool ui_pick = ibd.lo == 0 && ibd.hi == 0 && t_ui_buffer; // experiment 0157
		if (ibd.count != 0 && !ibd.dir.empty() && ((num_dwords >= ibd.lo && num_dwords <= ibd.hi) || ui_pick) && timing_now() >= ibd.t0 && ibd_n.load() < ibd.count) {
			const uint32_t k = ibd_n++;
			if (k < ibd.count) {
				char name[512];
				if (ui_pick)
					std::snprintf(name, sizeof(name), "%s/ib-%08" PRIu64 "-%.8s-%u-buf%u.bin", ibd.dir.c_str(), g_submits.load(), kind, num_dwords, t_ui_buf_no);
				else
					std::snprintf(name, sizeof(name), "%s/ib-%08" PRIu64 "-%.8s-%u.bin", ibd.dir.c_str(), g_submits.load(), kind, num_dwords);
				if (FILE* f = std::fopen(name, "wb"); f != nullptr) {
					std::fwrite(ib, sizeof(uint32_t), num_dwords, f);
					std::fclose(f);
				}
			}
		}
	}
	std::shared_ptr<const std::vector<bc5::direct::Mapping>> maps_p = g_dev->sorted_mappings();
	shader_dump(ib, num_dwords, *maps_p); // experiment 0049
	bc5::policy::FilterOptions opt;
	opt.cu_mask       = g_cu_mask;
	opt.clear_int_sel = true;
	// Experiment 0050: BC5_DIRECT_DMA_SYNC=1, a CP DMA wait before the first dispatch after an
	// unsynced DMA_DATA (backend FilterOptions::dma_sync_before_dispatch).
	static const bool dma_sync = bc5::env_on(std::getenv("BC5_DIRECT_DMA_SYNC")); // exp 0419: "=0" is off
	opt.dma_sync_before_dispatch = dma_sync;
	// GDS (run 57): the partition on every submission — the gfx queue resets the
	// counters (GDS fills) and its shaders read them; runs 49–51 hung not on the partition but on
	// the giant indirect draws the un-reset counters produced (clamped since run 55).
	opt.drop_gds             = false;
	// Experiment 0404: with BC5_DIRECT_FL_CRUMBS the crumbs' area of the GDS shadow passes the operand check (fl_crumbs_area()
	// is 0 when the switch is off: one compare per operand).
	const uint64_t fl_area = fl_crumbs_area();
	opt.mapped = [&maps_p, fl_area](uint64_t a, uint64_t bytes) {
		if (fl_area != 0 && a >= fl_area && a + bytes <= fl_area + kFlAreaBytes) return true; // experiment 0404
		if (ge_probe_range().second != 0 && g_dev && g_dev->gds_shadow_va() != 0 && a >= g_dev->gds_shadow_va() && a + bytes <= g_dev->gds_shadow_va() + 65536) return true; // experiment 0160
		return covered_sorted(*maps_p, a, bytes);
	};
	// Experiment 0122: BC5_DIRECT_DMA_SNAPSHOT=<min bytes> has the backend copy the source of every
	// DMA_DATA that reads at least that many bytes of memory into a buffer of the job's own slot at
	// submission, and the filtered IB reads the copy (FilterOptions::dma_snapshot_min): the second
	// title rewrites its rotating CPU staging before our jobs run (F146: its menu text and UI images
	// then show other uploads' data). Experiment 0087's ring in guest flexible memory could not be
	// mapped for the GPU and was replaced by this.
	{
		static const uint32_t snap_min = [] {
			const char* e = std::getenv("BC5_DIRECT_DMA_SNAPSHOT");
			return e != nullptr ? static_cast<uint32_t>(std::strtoul(e, nullptr, 10)) : 0u;
		}();
		// Graphics buffers only: the compute buffers also copy what the GPU itself wrote earlier
		// (experiment 0050: tree headers before the refit), which a copy at submission would freeze
		// before it is written.
		opt.dma_snapshot_min = std::strcmp(kind, "dcb") == 0 ? snap_min : 0u;
	}
	// Experiment 0124: BC5_DIRECT_JOB_TS=1, a GPU timestamp at each job's start and end
	// (FilterOptions::job_timestamps); the completion thread journals busy and idle GPU time.
	static const bool job_ts = BC5_DIAG_ENV("BC5_DIRECT_JOB_TS") != nullptr;
	opt.job_timestamps = job_ts;
	static const std::vector<uint8_t> extra = [] {
		std::vector<uint8_t> v;
		// Experiment 0054: DRAW_INDIRECT (0x24), DRAW_INDIRECT_MULTI (0x2c) and
		// DRAW_INDEX_INDIRECT_MULTI (0x38) pass the backend's policy now; they stay dropped here
		// unless BC5_DIRECT_INDIRECT_DRAWS=1 (the second title draws its scene with them).
		// Experiment 0057: "=1" lets DRAW_INDIRECT through only; the multi-draw packets, whose per-draw
		// arguments nobody checks, need "=multi".
		const char* idraws = std::getenv("BC5_DIRECT_INDIRECT_DRAWS");
		if (idraws == nullptr) v.insert(v.end(), {0x24, 0x2c, 0x38});
		else if (std::strcmp(idraws, "multi") != 0) v.insert(v.end(), {0x2c, 0x38});
		return v;
	}();
	opt.extra_drop = extra;
	// Experiment 0057: an indirect draw's counts as the CP checks them: at most 2^20 vertices (the
	// second title's largest is 94,322) and 64 instances (it draws one); 2^22 x 1024 let a draw on
	// stale arguments run for seconds.
	opt.gpu_check_draw_max[0] = 1u << 20;
	opt.gpu_check_draw_max[1] = 64;
	opt.keep_wait_offsets.clear(); // experiment 0055
	if (chain != nullptr) { // ADR 0010: the kept waits were converted to chain offsets when the segment was appended
		for (const ChainSeg& s: chain->segs) opt.keep_wait_offsets.insert(opt.keep_wait_offsets.end(), s.keep.begin(), s.keep.end());
	} else {
		for (const uint32_t* w: t_keep_waits) {
			if (w >= ib && w < ib + num_dwords) opt.keep_wait_offsets.push_back(static_cast<uint32_t>(w - ib));
		}
	}
	// Indirect draws and dispatches (runs 53–54): their arguments live in memory the filter does
	// not read — the counters the compute queues produce. With real GDS they are non-zero and one
	// of them kept the CP busy past the kernel's timeout. Survey them (journal) and NOP the ones
	// whose counts exceed 4M indices/vertices or 65536 groups.
	// Layouts (PAL): DRAW_INDIRECT/DRAW_INDEX_INDIRECT dword1 = offset from the SET_BASE index-1
	// base; args {count, instance_count, first, base_vertex, first_instance}; DISPATCH_INDIRECT
	// dword1 = offset, args {x, y, z}. TODO(verify) SET_BASE index 1 vs the console's usage.
	const bool             catch_on = table_catcher_on(); // experiment 0401 series e: the table catcher's slots of this buffer
	std::vector<CatchSlot> catch_slots;
	if (catch_on) g_catch_bufs++;
	bool                  mec_expand_ib = false; // experiment 0038: rebuild the IB with GFX-form dispatches
	std::vector<uint32_t> mec_positions;         // offsets of its compute-form DISPATCH_INDIRECT
	{
		static constexpr uint64_t max_count = 4u << 20u;
		static std::atomic<uint64_t> n_insane {0}, n_unmapped_args {0};
		uint64_t base1 = 0;
		// Experiment 0038: a compute IB's DISPATCH_INDIRECT carries its argument address (lo, hi,
		// initiator); the GFX ring reads an offset from the SET_BASE index-1 base. The 4 GiB the
		// IB's dispatches use become that base (set in the prologue) and the filter rewrites them
		// (FilterOptions::mec_indirect_base). Before, the address was taken as an offset from 0,
		// "not mapped", and the dispatch dropped: 10 million drops in a 600 s run of one title.
		// Off by default (BC5_DIRECT_MEC_INDIRECT=1 turns it on): with it, the first converted
		// dispatch hung the GPU 4 s into the run and the reset took the machine down (run 64).
		// Off, these dispatches are dropped, as they always were: they have never run here.
		static const bool            mec_on     = bc5::env_on(std::getenv("BC5_DIRECT_MEC_INDIRECT")); // exp 0419: "=0" is off
		const bool                   compute_ib = std::strncmp(kind, "acb", 3) == 0;
		std::map<uint32_t, uint32_t> mec_hi; // high address dword -> dispatches
		// Experiment 0038: the compute program each compute-form dispatch runs (COMPUTE_PGM_LO/HI,
		// SH registers 0x20c/0x20d after 0x2c00, address >> 8), journaled once per program.
		uint64_t pgm = 0;
		uint64_t ud01 = 0; // experiment 0050: COMPUTE_USER_DATA_0/1
		uint32_t ud[16] = {}; // experiment 0059: COMPUTE_USER_DATA_0..15 as this buffer sets them
		CarriedCpState&   carried  = g_carried[compute_ib ? 1 : 0];
		{
			std::lock_guard<std::mutex> lk(g_carried_mutex);
			base1 = carried.base1;
			pgm   = carried.pgm;
			ud01  = carried.ud01;
			std::memcpy(ud, carried.ud, sizeof(ud));
		}
		static const auto pgm_list = [](const char* name) {
			std::set<uint64_t> v;
			if (const char* e = std::getenv(name); e != nullptr) {
				for (const char* c = e; *c != 0;) {
					char*          end = nullptr;
					const uint64_t x   = std::strtoull(c, &end, 16);
					if (end == c) break;
					v.insert(x);
					c = (*end == ',') ? end + 1 : end;
				}
			}
			return v;
		};
		// Experiment 0052: BC5_DIRECT_GPU_CHECK=1, the CP checks a dispatch's group counts when it runs
		// it (backend FilterOptions::gpu_check_indirect) and skips it if they are absurd; the host's
		// check below, on values read at submit time (stale for arguments the GPU writes earlier in
		// the frame), then no longer drops a dispatch the CP will check: one with a known base (a
		// SET_BASE earlier in this IB, or a rebuilt compute dispatch). The backend grows the IB's own
		// COND_EXEC counts around what it inserts.
		static const bool gpu_check = bc5::env_on(std::getenv("BC5_DIRECT_GPU_CHECK")); // exp 0419: "=0" is off
		if (gpu_check) opt.gpu_check_indirect = true;
		for (uint32_t q = 0; q < num_dwords;) {
			const uint32_t h = ib[q];
			const uint32_t type = h >> 30u;
			uint32_t len = 1;
			if (type == 3 || type == 0) { const uint32_t c = (h >> 16u) & 0x3fffu; len = c == 0x3fffu ? 1 : c + 2; }
			if (q + len > num_dwords) break;
			const uint32_t op = (h >> 8u) & 0xffu;
			if (type == 3 && op == 0x63 && len >= 5 && (ib[q + 3] >> 31u) != 0) { // experiment 0050: LOAD_SH_REG_INDEX pairs
				const uint64_t ta = (ib[q + 1] & ~3u) | (static_cast<uint64_t>(ib[q + 2] & 0xffffu) << 32u);
				const uint32_t tn = ib[q + 4] & 0x3fffu;
				if (ta != 0 && tn != 0 && covered_sorted(*maps_p, ta, static_cast<uint64_t>(tn) * 8)) {
					const auto* t = reinterpret_cast<const volatile uint32_t*>(ta);
					for (uint32_t k = 0; k < tn; k++) {
						const uint32_t r = t[2 * k] & 0xffffu, v = t[2 * k + 1];
						if (r == 0x20cu) { // experiment 0137: the program in the table moved to its bounded copy
							const uint64_t moved = loop_bound_copy(static_cast<uint64_t>(v) << 8u);
							if (moved != 0) {
								const_cast<volatile uint32_t*>(t)[2 * k + 1] = static_cast<uint32_t>(moved >> 8u);
								static std::atomic<uint64_t> n_moved {0};
								if ((n_moved++ & 0xfffu) == 0) journal("loop bound: table 0x%" PRIx64 " entry %u now names the copy (%" PRIu64 " so far)\n", ta, k, n_moved.load());
							}
						}
						if (r == 0x20cu) pgm = (pgm & ~0xffffffff00ull) | (static_cast<uint64_t>(v) << 8u);
						if (r == 0x20du) pgm = (pgm & 0xffffffff00ull) | (static_cast<uint64_t>(v & 0xffu) << 40u);
						if (r >= 0x240u && r < 0x250u) ud[r - 0x240u] = v; // experiment 0059
					}
				}
			}
			// BC5 (experiment 0159): the SH registers a dispatch runs with come from SET_SH_REG or from
			// LOAD_SH_REG_INDEX tables in guest memory (the second title restores its compute state that
			// way after a mid-buffer CLEAR_STATE), so both feed the program and user-data tracking;
			// before, BC5_DIRECT_SKIP_PGM and the dispatch journal missed the loaded ones.
			auto sh_reg = [&](uint32_t r, uint32_t v) {
				if (r == 0x20cu) pgm = (pgm & ~0xffffffff00ull) | (static_cast<uint64_t>(v) << 8u);
				if (r == 0x20du) pgm = (pgm & 0xffffffff00ull) | (static_cast<uint64_t>(v & 0xffu) << 40u);
				if (r == 0x244u) ud01 = (ud01 & ~0xffffffffull) | v; // USER_DATA_4/5 = s[4:5], the header pointer
				if (r == 0x245u) ud01 = (ud01 & 0xffffffffull) | (static_cast<uint64_t>(v) << 32u);
				if (r >= 0x240u && r < 0x250u) ud[r - 0x240u] = v; // experiment 0059
			};
			if (type == 3 && op == 0x76 && len >= 3) { // SET_SH_REG: watch COMPUTE_PGM_LO/HI
				const uint32_t first = ib[q + 1] & 0xffffu;
				for (uint32_t k = 0; k + 2 < len; k++) sh_reg(first + k, ib[q + 2 + k]);
			} else if (type == 3 && op == 0x63 && len >= 5 && (ib[q + 3] >> 31u) != 0) { // LOAD_SH_REG_INDEX, (offset, value) pairs
				const uint64_t ta = (ib[q + 1] & ~3u) | (static_cast<uint64_t>(ib[q + 2] & 0xffffu) << 32u);
				const uint32_t tn = ib[q + 4] & 0x3fffu;
				if (ta != 0 && tn != 0 && tn <= 4096 && covered_sorted(*maps_p, ta, static_cast<uint64_t>(tn) * 8)) {
					const auto* t = reinterpret_cast<const volatile uint32_t*>(ta);
					for (uint32_t k = 0; k < tn; k++) sh_reg(t[2 * k] & 0xffffu, t[2 * k + 1]);
				}
			}
			// BC5 (experiment 0159): BC5_DIRECT_DISPATCH_JOURNAL=1 journals every dispatch of a graphics
			// buffer with its program and first user data (which program faults the GPU).
			{
				static const bool dj = BC5_DIAG_ENV("BC5_DIRECT_DISPATCH_JOURNAL") != nullptr;
				if (dj && type == 3 && (op == 0x15 || op == 0x16))
					journal("  %s dispatch op %02x at %u: pgm 0x%" PRIx64 " ud0-3 %08x %08x %08x %08x ud4-7 %08x %08x %08x %08x ud8-11 %08x %08x %08x %08x ud12-15 %08x %08x %08x %08x%s base1 0x%" PRIx64 " +0x%x len %u\n", kind, op, q, pgm, ud[0], ud[1], ud[2], ud[3], ud[4], ud[5], ud[6], ud[7], ud[8], ud[9], ud[10], ud[11], ud[12], ud[13], ud[14], ud[15], op == 0x16 ? " indirect" : "", base1, op == 0x16 && len >= 2 ? ib[q + 1] : 0u, len); // experiment 0160: all user data and the indirect base
				// experiment 0160: register tables — LOAD_SH_REG_INDEX (0x63), LOAD_CONTEXT_REG_INDEX (0x9f) and
				// LOAD_UCONFIG_REG_INDEX (0x64) pairs of a graphics buffer in the GE probe size range, read now.
				if (dj && type == 3 && (op == 0x63 || op == 0x9f || op == 0x64) && len >= 5 && std::strncmp(kind, "dcb", 3) == 0 && ge_probe_range().second != 0 && num_dwords >= ge_probe_range().first + 1249 && num_dwords <= ge_probe_range().second + 1249) {
					const uint64_t ta = (ib[q + 1] & ~3u) | (static_cast<uint64_t>(ib[q + 2] & 0xffffu) << 32u);
					const uint32_t tn = ib[q + 4] & 0x3fffu;
					char           line[1600];
					int            w = std::snprintf(line, sizeof(line), "  %s table op %02x at %u: 0x%" PRIx64 " x%u%s:", kind, op, q, ta, tn, (ib[q + 3] >> 31u) != 0 ? " pairs" : " flat");
					if (ta != 0 && tn != 0 && covered_sorted(*maps_p, ta, static_cast<uint64_t>(tn) * 8)) {
						const auto* t = reinterpret_cast<const volatile uint32_t*>(ta);
						for (uint32_t k = 0; k < tn && w < 1500; k++) w += std::snprintf(line + w, sizeof(line) - static_cast<size_t>(w), " %x=%x", t[2 * k] & 0xffffu, t[2 * k + 1]);
						if (w >= 1500) w += std::snprintf(line + w, sizeof(line) - static_cast<size_t>(w), " ...");
					} else {
						w += std::snprintf(line + w, sizeof(line) - static_cast<size_t>(w), " <unreadable>");
					}
					journal("%s\n", line);
				}
				if (dj && type == 3 && op == 0x22 && len >= 5 && std::strncmp(kind, "dcb", 3) == 0 && ge_probe_range().second != 0) { // COND_EXEC: the flag's value now
					const uint64_t fa = (ib[q + 1] & ~3u) | (static_cast<uint64_t>(ib[q + 2] & 0xffffu) << 32u);
					journal("  %s cond_exec at %u: flag 0x%" PRIx64 " = %s, skips %u dwords\n", kind, q, fa, covered_sorted(*maps_p, fa, 4) ? std::to_string(*reinterpret_cast<const volatile uint32_t*>(fa)).c_str() : "<unreadable>", ib[q + 4] & 0x3fffu);
				}
				// Experiment 0160: with the dispatch journal, every draw, INDEX_BASE/INDEX_BUFFER_SIZE/INDEX_TYPE and SET_BASE packet of a graphics buffer too (offset, dwords, the SET_BASE 1 base the host knows).
				if (dj && type == 3 && (op == 0x24 || op == 0x25 || op == 0x27 || op == 0x2c || op == 0x2d || op == 0x35 || op == 0x38 || op == 0x26 || op == 0x13 || op == 0x11 || op == 0x2a) && std::strncmp(kind, "dcb", 3) == 0)
					journal("  %s pkt op %02x at %u: %08x %08x %08x %08x %08x %08x %08x %08x %08x base1 0x%" PRIx64 " len %u\n", kind, op, q, len > 1 ? ib[q + 1] : 0u, len > 2 ? ib[q + 2] : 0u, len > 3 ? ib[q + 3] : 0u, len > 4 ? ib[q + 4] : 0u, len > 5 ? ib[q + 5] : 0u, len > 6 ? ib[q + 6] : 0u, len > 7 ? ib[q + 7] : 0u, len > 8 ? ib[q + 8] : 0u, len > 9 ? ib[q + 9] : 0u, base1, len);
			}
			// Experiment 0054: in a buffer one of whose CPU-side waits was given up (a cycle between the
			// queues the single ring cannot serve), the indirect draws read arguments and data the other
			// queue has not produced yet; with them the GPU hung at the second title's 150 s scene
			// change (runs 240-242, the last one taking the machine down). They are dropped there.
			if (type == 3 && (op == 0x24 || op == 0x25 || op == 0x2c || op == 0x38) && chain_given_up_at(chain, q) && std::getenv("BC5_DIRECT_INDIRECT_DRAWS") != nullptr) {
				static std::atomic<uint64_t> n_unwaited {0};
				if ((n_unwaited++ & 0xfffu) == 0) journal("  indirect draw op %02x at %u after a given-up wait: DROPPED (%" PRIu64 " so far)\n", op, q, n_unwaited.load());
				opt.drop_offsets.push_back(q);
				q += len;
				continue;
			}
			// Experiment 0059: BC5_DIRECT_FIND_VA=<lo>:<hi> journals the dispatches (any buffer) whose
			// COMPUTE_USER_DATA pairs point into [lo, hi) — which programs get the tree the second
			// title's reflection traversal loops on; the first 4 per program and offset.
			{
				static const auto find = [] {
					std::pair<uint64_t, uint64_t> r {0, 0};
					if (const char* e = BC5_DIAG_ENV("BC5_DIRECT_FIND_VA"); e != nullptr) {
						unsigned long long a = 0, b = 0;
						if (std::sscanf(e, "%llx:%llx", &a, &b) == 2) r = {a, b};
					}
					return r;
				}();
				if (find.second > find.first && type == 3 && (op == 0x15 || op == 0x16)) {
					for (uint32_t k = 0; k + 1 < 16; k++) {
						const uint64_t a = ud[k] | (static_cast<uint64_t>(ud[k + 1] & 0xffffu) << 32u);
						if (a >= find.first && a < find.second) {
							static std::mutex                         find_mutex;
							static std::map<std::pair<uint64_t, uint32_t>, int> seen;
							std::lock_guard lk(find_mutex);
							if (seen[{pgm, (k << 24u) | (q & 0xffffffu)}]++ < 4)
								journal("find: %s #%" PRIu64 " %u dwords, dispatch op %02x at %u, pgm 0x%" PRIx64 ", user data %u:%u = 0x%" PRIx64 " (+0x%" PRIx64 ")\n", kind,
								        g_submits.load(), num_dwords, op, q, pgm, k, k + 1, a, a - find.first);
							break;
						}
					}
				}
			}
			if (type == 3 && (op == 0x15 || op == 0x16)) flat_aperture_fix(pgm, *maps_p); // experiment 0190
			if (type == 3 && (op == 0x15 || op == 0x16) && g_inh_drops.load(std::memory_order_relaxed) != 0) { // experiment 0403: skip
				const uint32_t* gq = chain == nullptr ? ib + q : nullptr; // the title's address of this packet
				if (chain != nullptr) {
					for (const ChainSeg& s: chain->segs) {
						if (s.src != nullptr && q >= s.off + s.prefix && q < s.off + s.prefix + s.n) {
							gq = s.src + (q - s.off - s.prefix);
							break;
						}
					}
				}
				if (gq != nullptr && acb_inherit_take(gq)) {
					opt.drop_offsets.push_back(q);
					q += len;
					continue;
				}
			}
			// Experiment 0059: BC5_DIRECT_SKIP_PGM=<hex list> drops every dispatch (DISPATCH_DIRECT and both
			// forms of DISPATCH_INDIRECT, in any kind of buffer) of these compute programs — e.g. the
			// second title's ray-traced-reflection traversal 0x11d049aa00, which loops forever on a bad
			// tree once its multi-draw packets run (experiment 0058).
			{
				static const std::set<uint64_t> any_skip = pgm_list("BC5_DIRECT_SKIP_PGM");
				if (!any_skip.empty() && type == 3 && (op == 0x15 || op == 0x16) && any_skip.count(pgm) != 0) {
					static std::atomic<uint64_t> n_skipped {0};
					if ((n_skipped++ & 0xfffu) == 0) journal("  skip pgm 0x%" PRIx64 ": %s dispatch op %02x at %u dropped (%" PRIu64 " so far)\n", pgm, kind, op, q, n_skipped.load());
					opt.drop_offsets.push_back(q);
					q += len;
					continue;
				}
			}
			// Experiment 0273: with the window's ray-tracing switch off, a dispatch of a program on the
			// title's BVH build list (KYTY_BC5_RT_BUILD_PGM) is dropped.
			// The 19:04 test (README, Result): dropping the ray-query consumers blanked the title's menu, whose
			// own picture is lit by three image_bvh64 programs. So "off" drops the build list alone, and
			// the consumers walk the trees the build never filled.
			{
				static const std::set<uint64_t> rt_build = pgm_list("KYTY_BC5_RT_BUILD_PGM");
				if (!g_rt_on.load(std::memory_order_relaxed) && type == 3 && (op == 0x15 || op == 0x16) && pgm != 0 && rt_build.count(pgm) != 0) {
					const uint64_t n_rt = g_rt_dropped.fetch_add(1);
					if ((n_rt & 0xfffu) == 0) journal("  ray tracing off: %s dispatch op %02x at %u of 0x%" PRIx64 " dropped (build list; %" PRIu64 " so far)\n", kind, op, q, pgm, n_rt + 1);
					opt.drop_offsets.push_back(q);
					q += len;
					continue;
				}
			}
			if (type == 3 && (op == 0x2c || op == 0x38) && len >= 10 && ib[q + 5] > 65536u) { // experiment 0054
				static std::atomic<uint64_t> n_multi {0};
				if ((n_multi++ & 0xfffu) == 0) journal("  indirect multi draw op %02x at %u: draw count %u, DROPPED (%" PRIu64 " so far)\n", op, q, ib[q + 5], n_multi.load());
				opt.drop_offsets.push_back(q);
			}
			if (catch_on && type == 3) { // experiment 0401 series e: the table catcher
				if ((op == 0x24 || op == 0x25 || op == 0x16) && len >= 2) {
					const bool     cmec = compute_ib && op == 0x16 && len == 4;
					const uint64_t ca   = cmec ? ((ib[q + 1] & ~3ull) | (static_cast<uint64_t>(ib[q + 2] & 0xffffu) << 32u)) : (base1 != 0 ? base1 + ib[q + 1] : 0);
					catch_add(catch_slots, *maps_p, op, q, ca, op == 0x16 ? 12u : op == 0x24 ? 16u : 20u);
				} else if ((op == 0x2c || op == 0x38) && len >= 10) {
					const uint32_t one = op == 0x2c ? 16u : 20u, count = ib[q + 5], stride = ib[q + 8];
					catch_add(catch_slots, *maps_p, op, q, base1 != 0 ? base1 + ib[q + 1] : 0, stride >= one && stride <= 256u && count >= 1 ? std::min(count, 16u) * stride : one);
				} else if ((op == 0x63 || op == 0x64 || op == 0x9f) && len >= 5) {
					if ((ib[q + 3] >> 31u) != 0) catch_add(catch_slots, *maps_p, op, q, (ib[q + 1] & ~3u) | (static_cast<uint64_t>(ib[q + 2] & 0xffffu) << 32u), (ib[q + 4] & 0x3fffu) * 8u);
					else g_catch_skipped++;
				}
			}
			if (type == 3 && op == 0x11 && len >= 4 && (ib[q + 1] & 0xfu) == 1) {
				base1 = (ib[q + 2] & ~3u) | (static_cast<uint64_t>(ib[q + 3] & 0xffffu) << 32u);
			} else if (type == 3 && (op == 0x24 || op == 0x25 || op == 0x16) && len >= 2) {
				const bool     mec  = compute_ib && op == 0x16 && len == 4;
				const uint64_t a    = mec ? ((ib[q + 1] & ~3ull) | (static_cast<uint64_t>(ib[q + 2] & 0xffffu) << 32u)) : base1 + ib[q + 1];
				if (mec && !mec_on && qring == bc5::direct::kGfxRing) {
					opt.drop_offsets.push_back(q);
					q += len;
					continue;
				}
				if (mec && qring == bc5::direct::kGfxRing) {
					mec_hi[ib[q + 2] & 0xffffu]++;
					mec_positions.push_back(q);
				}
				const uint32_t want = op == 0x16 ? 3 : 5;
				if (covered_sorted(*maps_p, a, want * 4)) {
					const auto* t = reinterpret_cast<const volatile uint32_t*>(a);
					uint32_t v[5] = {t[0], t[1], t[2], want > 3 ? t[3] : 0u, want > 4 ? t[4] : 0u};
					// Experiment 0038: the product without overflow (+inf as a count, 0x7f800000, wrapped
					// it to a small number). Values read here can be stale (arguments earlier GPU work
					// writes); trusting them instead (experiment 0041) failed, and 0052's GPU check
					// replaced that.
					const bool        too_many_groups = v[0] > 65536u * 64u || v[1] > 65536u * 64u || v[2] > 65536u * 64u ||
					                             static_cast<uint64_t>(v[0]) * v[1] > 65536ull * 64ull ||
					                             static_cast<uint64_t>(v[0]) * v[1] * v[2] > 65536ull * 64ull;
					const bool gpu_checked = gpu_check && op == 0x16 && (mec || base1 != 0); // experiment 0052
					if (gpu_checked && too_many_groups) {
						static std::atomic<uint64_t> n_deferred {0};
						if ((n_deferred++ & 0xffffu) == 0) journal("gpu check: %" PRIu64 " dispatches left to the CP that the host would have dropped\n", n_deferred.load());
					}
					// Experiment 0054: indirect draws are checked by the CP too (vertex or index count,
					// instance count), so a draw with a known base is no longer dropped on stale values.
					const bool draw_checked = gpu_check && op != 0x16 && base1 != 0;
					const bool insane = op == 0x16 ? (!gpu_checked && too_many_groups)
					                               : (!draw_checked && (v[0] > max_count || v[1] > 1024u || static_cast<uint64_t>(v[0]) * v[1] > max_count));
					if (insane && (n_insane.fetch_add(1, std::memory_order_relaxed) & 0xfffu) == 0)
						journal("  indirect op %02x at %u: base 0x%" PRIx64 " +0x%x -> %u %u %u %u %u%s pgm 0x%" PRIx64 "\n", op, q, base1, ib[q + 1], v[0], v[1], v[2], v[3], v[4],
					                    insane ? " DROPPED" : "", pgm);
					if (insane) opt.drop_offsets.push_back(q);
				} else {
					if ((n_unmapped_args.fetch_add(1, std::memory_order_relaxed) & 0xfffu) == 0)
						journal("  indirect op %02x at %u: args 0x%" PRIx64 " not mapped, DROPPED\n", op, q, a);
					opt.drop_offsets.push_back(q);
				}
			}
			q += len;
		}
		{ // experiment 0161
			std::lock_guard<std::mutex> lk(g_carried_mutex);
			carried.base1 = base1;
			carried.pgm   = pgm;
			carried.ud01  = ud01;
			std::memcpy(carried.ud, ud, sizeof(ud));
		}
		if (!mec_hi.empty() && mec_on) mec_expand_ib = true;
	}
	// Experiment 0404 (BC5_DIRECT_FL_CRUMBS, BC5_DIRECT_FL_SKIP_ES; both off by default): the graphics state the GPU will
	// see, followed through this buffer (fl_scan, carried from the buffers before), its fast-launch draws planned and the
	// ES skip's drops added; the crumbs are laid in below, once the submission's number is known. Off: two flag tests.
	FlPlan fl_plan;
	fl_plan_buffer(ib, num_dwords, kind, qring, chain, *maps_p, opt.drop_offsets, fl_plan);
	// Experiment 0038, BC5_DIRECT_OPS_DUMP=<n>: the opcode sequence (offset:op[/event or
	// control]) of the first n compute IBs of at least 1,000 dwords that hold a compute-form
	// DISPATCH_INDIRECT, to see what separates the dispatch that writes the arguments from the one
	// that reads them.
	{
		static const long ops_dump = BC5_DIAG_ENV("BC5_DIRECT_OPS_DUMP") ? std::atol(BC5_DIAG_ENV("BC5_DIRECT_OPS_DUMP")) : 0;
		static long       ops_done = 0;
		if (ops_done < ops_dump && std::strncmp(kind, "acb", 3) == 0 && num_dwords >= 1000) {
			bool has_mec = false;
			for (uint32_t q = 0; q < num_dwords;) {
				const uint32_t h = ib[q];
				uint32_t       len = 1;
				if ((h >> 30u) == 3 || (h >> 30u) == 0) { const uint32_t c = (h >> 16u) & 0x3fffu; len = c == 0x3fffu ? 1 : c + 2; }
				if ((h >> 30u) == 3 && ((h >> 8u) & 0xffu) == 0x16 && len == 4) has_mec = true;
				q += len;
			}
			if (has_mec) {
				ops_done++;
				std::string line;
				for (uint32_t q = 0; q < num_dwords;) {
					const uint32_t h    = ib[q];
					const uint32_t type = h >> 30u;
					uint32_t       len  = 1;
					if (type == 3 || type == 0) { const uint32_t c = (h >> 16u) & 0x3fffu; len = c == 0x3fffu ? 1 : c + 2; }
					if (q + len > num_dwords) break;
					if (type == 3) {
						const uint32_t op = (h >> 8u) & 0xffu;
						char           buf[64];
						if (op == 0x46 || op == 0x49 || op == 0x47) { // EVENT_WRITE / RELEASE_MEM / EOP: event type and index
							std::snprintf(buf, sizeof(buf), "%u:%02x/e%02x.%u ", q, op, ib[q + 1] & 0x3fu, (ib[q + 1] >> 8u) & 0xfu);
						} else if (op == 0x58) { // ACQUIRE_MEM: coher_cntl
							std::snprintf(buf, sizeof(buf), "%u:58/%08x ", q, len > 1 ? ib[q + 1] : 0u);
						} else if (op == 0x3c || op == 0x93) { // WAIT_REG_MEM: function, address lo
							std::snprintf(buf, sizeof(buf), "%u:%02x/f%u@%08x ", q, op, len > 1 ? ib[q + 1] & 7u : 0u, len > 2 ? ib[q + 2] : 0u);
						} else if (op == 0x16) {
							std::snprintf(buf, sizeof(buf), "%u:16/%u@%x%08x ", q, len, len == 4 ? ib[q + 2] & 0xffffu : 0u, len > 1 ? ib[q + 1] : 0u);
						} else if (op == 0x76 || op == 0x69 || op == 0x68 || op == 0x79) {
							buf[0] = 0; // SET_*_REG: too many to list
						} else {
							std::snprintf(buf, sizeof(buf), "%u:%02x ", q, op);
						}
						line += buf;
						if (line.size() > 900) { journal("ops %s #%" PRIu64 ": %s\n", kind, g_submits.load(), line.c_str()); line.clear(); }
					}
					q += len;
				}
				if (!line.empty()) journal("ops %s #%" PRIu64 ": %s\n", kind, g_submits.load(), line.c_str());
			}
		}
	}
	dc412_count(ib, num_dwords); // exp 0412 (tag dc412)
	const uint64_t n = g_submits.fetch_add(1);
	// Crash journal: a hang takes the machine down before any buffered log reaches the disk, so
	// the raw and the filtered IB and a one-line "about to submit" note are written unbuffered
	// first (BC5_GC_DUMP_DIR/direct-NNNNNN-<kind>.{raw,ib}.bin, direct.log).
	if (!g_dump_dir.empty() && !g_journal_min) {
		journal_load_tables(ib, num_dwords, *maps_p);
		std::vector<uint32_t>     filtered(num_dwords);
		bc5::policy::FilterStats  pre;
		bc5::policy::filter(bc5::policy::Policy::builtin(), std::span<const uint32_t>(ib, num_dwords), filtered, opt, pre);
		char name[512];
		std::snprintf(name, sizeof(name), "%s/direct-%06" PRIu64 "-%s.raw.bin", g_dump_dir.c_str(), n, kind);
		if (FILE* f = std::fopen(name, "wb")) { std::fwrite(ib, 4, num_dwords, f); std::fflush(f); std::fclose(f); }
		// INDIRECT_BUFFER targets (compute rings): their raw contents, for a post-mortem.
		for (uint32_t q = 0, t = 0; q < num_dwords && t < 16;) {
			const uint32_t h = ib[q];
			const uint32_t type = h >> 30u;
			uint32_t len = 1;
			if (type == 3 || type == 0) { const uint32_t c = (h >> 16u) & 0x3fffu; len = c == 0x3fffu ? 1 : c + 2; }
			if (q + len > num_dwords) break;
			if (type == 3 && (((h >> 8u) & 0xffu) == 0x3f || ((h >> 8u) & 0xffu) == 0x33) && len >= 4) {
				const uint64_t ta = (ib[q + 1] & ~3u) | (static_cast<uint64_t>(ib[q + 2] & 0xffu) << 32u);
				const uint32_t tn = ib[q + 3] & 0xfffffu;
				if (ta != 0 && tn != 0 && covered_sorted(*maps_p, ta, static_cast<uint64_t>(tn) * 4)) {
					std::snprintf(name, sizeof(name), "%s/direct-%06" PRIu64 "-%s-ib%u.raw.bin", g_dump_dir.c_str(), n, kind, t);
					if (FILE* f = std::fopen(name, "wb")) { std::fwrite(reinterpret_cast<const void*>(ta), 4, tn, f); std::fflush(f); std::fclose(f); }
				}
				t++;
			}
			q += len;
		}
		std::snprintf(name, sizeof(name), "%s/direct-%06" PRIu64 "-%s.ib.bin", g_dump_dir.c_str(), n, kind);
		if (FILE* f = std::fopen(name, "wb")) { std::fwrite(filtered.data(), 4, num_dwords, f); std::fflush(f); std::fclose(f); }
		std::snprintf(name, sizeof(name), "%s/direct.log", g_dump_dir.c_str());
		if (FILE* f = std::fopen(name, "a")) {
			std::fprintf(f, "submit #%" PRIu64 " %s %u dwords at %p: pass %" PRIu64 " rewrite %" PRIu64 " drop %" PRIu64 " unmapped %" PRIu64 " cc %" PRIu64 " mappings %zu ... ",
			             n, kind, num_dwords, static_cast<const void*>(ib), pre.passed, pre.rewritten, pre.dropped, pre.unmapped_drops, pre.context_control_rewrites, maps_p->size());
			std::fflush(f);
			fsync(fileno(f));
			std::fclose(f);
		}
	}
	// Experiment 0038 (BC5_DIRECT_MEC_INDIRECT=1): every compute-form DISPATCH_INDIRECT (address
	// lo, hi, initiator) becomes SET_BASE index 1 with the compute shader type (base: the page of
	// its arguments), PFP_SYNC_ME (the GFX ring's prefetch parser reads the arguments ahead of the
	// ME, so without it the CS_PARTIAL_FLUSH between the dispatch that writes them and this one did
	// not hold it back), and the GFX-form DISPATCH_INDIRECT (offset in that page, initiator), as
	// RADV emits an indirect dispatch on the GFX ring (Mesa radv_emit_dispatch_packets,
	// TODO(verify) the lines). The IB grows, so the host submits a copy and maps offsets both
	// ways (the drop list in, the executed offsets out). ADR 0010 section A: the IB's own
	// COND_EXEC counts (dword offsets) are grown by what the rebuild inserts in their ranges; a
	// range whose grown count would not fit its 14 bits keeps its rebuilt dispatches dropped
	// instead (what every dispatch of an IB with a COND_EXEC got before).
	std::vector<uint32_t> mec_ib;
	std::vector<uint32_t> mec_new_to_old;
	const uint32_t*       sub_ib = ib;
	uint32_t              sub_n  = num_dwords;
	if (mec_expand_ib) {
		std::vector<uint32_t> old_to_new(num_dwords + 1, ~0u);
		for (int attempt = 0; attempt < 64; attempt++) {
			mec_ib.clear();
			std::fill(old_to_new.begin(), old_to_new.end(), ~0u);
			mec_ib.reserve(num_dwords + 5 * mec_positions.size());
			for (uint32_t q = 0; q < num_dwords;) {
				const uint32_t h = ib[q];
				uint32_t       len = 1;
				if ((h >> 30u) == 3 || (h >> 30u) == 0) { const uint32_t c = (h >> 16u) & 0x3fffu; len = c == 0x3fffu ? 1 : c + 2; }
				if (q + len > num_dwords) len = num_dwords - q;
				const bool dropped = std::find(opt.drop_offsets.begin(), opt.drop_offsets.end(), q) != opt.drop_offsets.end();
				const bool is_mec  = (h >> 30u) == 3 && ((h >> 8u) & 0xffu) == 0x16 && len == 4 && !dropped;
				if (is_mec) {
					const uint64_t a    = (ib[q + 1] & ~3ull) | (static_cast<uint64_t>(ib[q + 2] & 0xffffu) << 32u);
					const uint64_t base = a & ~0xfffull;
					mec_ib.insert(mec_ib.end(), {0xC0021102u, 1u, static_cast<uint32_t>(base), static_cast<uint32_t>(base >> 32u)});
					mec_ib.insert(mec_ib.end(), {0xC0004200u, 0u});
					old_to_new[q] = static_cast<uint32_t>(mec_ib.size());
					mec_ib.insert(mec_ib.end(), {(h & ~(0x3fffu << 16u)) | (1u << 16u), static_cast<uint32_t>(a - base), ib[q + 3]});
				} else {
					old_to_new[q] = static_cast<uint32_t>(mec_ib.size());
					mec_ib.insert(mec_ib.end(), ib + q, ib + q + len);
				}
				q += len;
			}
			old_to_new[num_dwords] = static_cast<uint32_t>(mec_ib.size());
			// the COND_EXEC counts, grown; the ranges that no longer fit have their dispatches dropped and the rebuild redone
			std::vector<std::pair<uint32_t, uint32_t>> overflow;
			for (uint32_t q = 0; q < num_dwords;) {
				const uint32_t h = ib[q];
				uint32_t       len = 1;
				if ((h >> 30u) == 3 || (h >> 30u) == 0) { const uint32_t c = (h >> 16u) & 0x3fffu; len = c == 0x3fffu ? 1 : c + 2; }
				if (q + len > num_dwords) break;
				if ((h >> 30u) == 3 && ((h >> 8u) & 0xffu) == 0x22 && len == 5) {
					uint32_t e = q + 5 + (ib[q + 4] & 0x3fffu);
					if (e > num_dwords) e = num_dwords;
					while (old_to_new[e] == ~0u) e++; // a range ending inside a packet: to its end
					const uint32_t at    = old_to_new[q];
					const uint32_t count = old_to_new[e] - (at + 5);
					if (count > 0x3fffu) overflow.emplace_back(q + 5, e);
					mec_ib[at + 4] = (mec_ib[at + 4] & ~0x3fffu) | (count & 0x3fffu);
				}
				q += len;
			}
			if (overflow.empty()) break;
			uint32_t excluded = 0;
			for (const uint32_t m: mec_positions) {
				bool inside = false;
				for (const auto& [lo, hi]: overflow) inside = inside || (m >= lo && m < hi);
				if (inside && std::find(opt.drop_offsets.begin(), opt.drop_offsets.end(), m) == opt.drop_offsets.end()) {
					opt.drop_offsets.push_back(m);
					excluded++;
				}
			}
			static std::atomic<uint64_t> n_over {0};
			if ((n_over++ & 0x3fu) == 0) journal("mec rebuild: %s %u dwords: %zu COND_EXEC range(s) would overflow, %u rebuilt dispatches dropped (%" PRIu64 " so far)\n", kind, num_dwords, overflow.size(), excluded, n_over.load());
			if (excluded == 0) break; // cannot happen: a range only grows by a rebuilt dispatch inside it
		}
		{
			mec_new_to_old.assign(mec_ib.size(), ~0u);
			for (uint32_t q = 0; q < num_dwords; q++) {
				if (old_to_new[q] != ~0u && old_to_new[q] < mec_new_to_old.size()) mec_new_to_old[old_to_new[q]] = q;
			}
			for (auto& d: opt.drop_offsets) {
				if (d < num_dwords && old_to_new[d] != ~0u) d = old_to_new[d];
			}
			for (auto& d: opt.keep_wait_offsets) {
				if (d < num_dwords && old_to_new[d] != ~0u) d = old_to_new[d];
			}
			sub_ib = mec_ib.data();
			sub_n  = static_cast<uint32_t>(mec_ib.size());
		}
	}
	// Experiment 0404 (BC5_DIRECT_FL_CRUMBS): the copy with the crumbs around the planned draws (fl_build; the buffer's own
	// COND_EXEC counts grown as the mec rebuild above grows them), the drop and kept-wait offsets mapped into it; fl_back
	// maps the executed offsets back to the buffer's own, as mec_back does. The probes get the buffer without the crumbs.
	std::vector<uint32_t> fl_ib, fl_new_to_old;
	if (!fl_plan.draws.empty() || fl_plan.inserts) fl_after(ib, num_dwords, kind, n, mec_expand_ib, fl_plan, opt, fl_ib, fl_new_to_old); // + exp 0401 e7 (flx): a prefix head alone
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
	auto mec_back = [&mec_new_to_old](std::vector<uint32_t>& offsets) {
		if (mec_new_to_old.empty()) return;
		std::vector<uint32_t> back;
		back.reserve(offsets.size());
		for (const uint32_t o: offsets) {
			if (o < mec_new_to_old.size() && mec_new_to_old[o] != ~0u) back.push_back(mec_new_to_old[o]);
		}
		offsets.swap(back);
	};
	const uint64_t ls_t3 = SoftCp::now_ns(); // experiment 0415 (ls415c)
	bc5::direct::SubmitResult r;
	if (su) { // exp 0436 (tag su436): the backend calls back before the CS ioctl; the device mutex is taken again after it
		bool                        let_go = false;
		const std::function<void()> unlock_dev = [&lock, &let_go] {
			lock.unlock();
			let_go = true;
		};
		r = g_dev->submit(std::span<const uint32_t>(sub_ib, sub_n), opt, 2'000'000'000ull, true, qring, unlock_dev);
		if (!lock.owns_lock()) lock.lock();
#ifndef BC5_LEAN
		if (let_go) {
			const uint64_t k = g_su436_calls.fetch_add(1);
			if (k == 0 || (k & 0x3ffffu) == 0) std::fprintf(stderr, "[bc5] exp 0436 (tag su436): %" PRIu64 " kernel submits made outside the device mutex so far\n", k + 1);
		}
#else
		(void)let_go;
#endif
	} else {
		r = g_dev->submit(std::span<const uint32_t>(sub_ib, sub_n), opt, 2'000'000'000ull, true, qring);
	}
	if (bc5::load_stat::on()) { // experiment 0415 (ls415c): the hold by part
		bc5::load_stat::add(bc5::load_stat::kHoldPre, ls_t3 - t2);
		bc5::load_stat::add(bc5::load_stat::kDevCall, SoftCp::now_ns() - ls_t3);
		bc5::load_stat::add(bc5::load_stat::kDevPrepare, r.prepare_ms > 0 ? static_cast<uint64_t>(r.prepare_ms * 1e6) : 0);
		bc5::load_stat::add(bc5::load_stat::kDevList, r.list_ms > 0 ? static_cast<uint64_t>(r.list_ms * 1e6) : 0);
		bc5::load_stat::add(bc5::load_stat::kDevCs, r.cs_ms > 0 ? static_cast<uint64_t>(r.cs_ms * 1e6) : 0);
	}
	mec_back(r.executed_offsets);
	fl_back(r.executed_offsets); // experiment 0404
#ifndef BC5_LEAN
	if (w428_rings() > 0) { // exp 0428 (tag w428c): jobs per ring and the rest, one stderr line at most every 10 s
		static std::atomic<uint64_t> jobs[bc5::direct::kComputeRings + 1] = {};
		static std::atomic<uint64_t> last_ns {0};
		jobs[qring == bc5::direct::kGfxRing ? bc5::direct::kComputeRings : qring]++;
		const uint64_t now = SoftCp::now_ns();
		uint64_t       was = last_ns.load();
		if (now - was >= 10'000'000'000ull && last_ns.compare_exchange_strong(was, now)) {
			std::string q, why;
			{
				std::lock_guard lk(g_w428_mu);
				for (const auto& [k, v]: g_w428_qring)
					if (v.busy) q += " " + std::to_string(k) + "->" + std::to_string(v.ring) + "(" + std::to_string(v.n) + ")";
				q += " moves " + std::to_string(g_w428_moves.load()) + " not-idle-in-2s " + std::to_string(g_w428_move_late.load());
				for (const auto& [k, v]: g_w428_refused) why += " " + k + ":" + std::to_string(v);
			}
			std::fprintf(stderr,
			             "[bc5] exp 0428 (tag w428c): t %.1f s: jobs gfx %" PRIu64 " comp0 %" PRIu64 " comp1 %" PRIu64 " comp2 %" PRIu64 " comp3 %" PRIu64
			             "; acbs kept on gfx:%s; queue->ring:%s; dcb waits on two rings: kept %" PRIu64 " satisfied %" PRIu64 " NOT served %" PRIu64
			             " heads split %" PRIu64 " kept-without-split %" PRIu64 " (on a ring %" PRIu64 ", in the IB %" PRIu64 ", after the chain %" PRIu64 ", still split %" PRIu64 "; polled first: kept %" PRIu64 " satisfied %" PRIu64 " cycle-split %" PRIu64 " timeout-split %" PRIu64 "); aq424 %s, parts given state %" PRIu64 ", parts with no tracked queue %" PRIu64 "; mec-indirect switch %s, acbs moved %" PRIu64 "\n",
			             timing_now(), jobs[4].load(), jobs[0].load(), jobs[1].load(), jobs[2].load(), jobs[3].load(), why.empty() ? " none" : why.c_str(),
			             q.empty() ? " none" : q.c_str(), g_w428_two[0].load(), g_w428_two[1].load(), g_w428_two[2].load(), g_w428_two[3].load(), g_w428_two[4].load(), g_w428_late[1].load(), g_w428_late[2].load(), g_w428_late[3].load(), g_w428_late[0].load(), g_w428_poll[1].load(), g_w428_poll[2].load(), g_w428_poll[3].load(), g_w428_poll[4].load(),
			             aq424_on() ? "ON" : "off", g_aq424_parts.load(), g_aq424_none.load(), w428_mec_ok() ? "ON" : "off", g_w428_mec_moved.load());
		}
	}
#endif
	if (qring != bc5::direct::kGfxRing && (g_comp_jobs++ & 0xffffu) == 0) {
		journal("compute ring %d: %" PRIu64 " jobs so far (rc %d), %" PRIu64 " compute buffers kept on the GFX ring\n", qring, g_comp_jobs.load(), r.rc, g_comp_refused.load());
	}
	if (r.filter.dma_sources != 0 || r.filter.dma_snapshot_overflow != 0) { // experiment 0122
		static std::atomic<uint64_t> n_jobs {0}, n_src {0}, n_bytes {0}, n_over {0};
		n_src += r.filter.dma_sources;
		n_bytes += r.filter.dma_snapshot_bytes;
		n_over += r.filter.dma_snapshot_overflow;
		const uint64_t j = ++n_jobs;
		if (j == 1 || (j & 0x3ffu) == 0) {
			journal("dma snapshot: %" PRIu64 " jobs, %" PRIu64 " sources copied (%" PRIu64 " MiB), %" PRIu64 " left in place (slot buffer full)\n", j, n_src.load(),
			        n_bytes.load() >> 20u, n_over.load());
		}
	}
	// Experiment 0054: BC5_DIRECT_DROP_TALLY=1 counts the packets the filter took out (type 3, not
	// NOP, not among the executed offsets), per kind of buffer and opcode (WRITE_DATA by DST_SEL,
	// EVENT_WRITE by event type), and every 10 s journals the counts since the last report.
	static const bool drop_tally_env = BC5_DIAG_ENV("BC5_DIRECT_DROP_TALLY") != nullptr;
	const bool drop_tally = drop_tally_env && ::Log::Bc5LoggingOn();
	if (drop_tally) {
		static std::mutex                      tally_mutex;
		static std::map<std::string, uint64_t> tally;
		static double                          tally_last = 0;
		std::map<std::string, uint64_t>        mine;
		size_t                                 e = 0;
		for (uint32_t q = 0; q < num_dwords;) {
			const uint32_t h = ib[q];
			uint32_t       len = 1;
			if ((h >> 30u) == 3 || (h >> 30u) == 0) { const uint32_t c = (h >> 16u) & 0x3fffu; len = c == 0x3fffu ? 1 : c + 2; }
			if ((h >> 30u) == 3 && ((h >> 8u) & 0xffu) != 0x10) {
				while (e < r.executed_offsets.size() && r.executed_offsets[e] < q) e++;
				if (e >= r.executed_offsets.size() || r.executed_offsets[e] != q) {
					const uint32_t op = (h >> 8u) & 0xffu;
					char           key[64];
					if (op == 0x37 && q + 1 < num_dwords) {
						std::snprintf(key, sizeof(key), "%.3s %02x dst_sel %u", kind, op, (ib[q + 1] >> 8u) & 0xfu);
					} else if (op == 0x46 && q + 1 < num_dwords) {
						std::snprintf(key, sizeof(key), "%.3s %02x event %u", kind, op, ib[q + 1] & 0x3fu);
					} else {
						std::snprintf(key, sizeof(key), "%.3s %02x", kind, op);
					}
					mine[key]++;
				}
			}
			q += len;
		}
		std::lock_guard<std::mutex> lk(tally_mutex);
		for (const auto& [k, v]: mine) tally[k] += v;
		const double now = timing_now();
		if (now - tally_last >= 10.0) {
			tally_last = now;
			std::string line = "drop tally:";
			for (const auto& [k, v]: tally) line += " [" + k + "] " + std::to_string(v);
			journal("%s\n", line.c_str());
			tally.clear();
		}
	}
	if (opt.gpu_check_indirect) { // experiment 0052
		static std::atomic<uint64_t> checked {0}, unbased {0}, skipped {0}, ibs {0};
		checked += r.filter.gpu_checks;
		unbased += r.filter.gpu_check_unbased;
		skipped += r.filter.gpu_check_skipped;
		if ((ibs++ & 0x3fffu) == 0) {
			journal("gpu check: %" PRIu64 " dispatches checked by the CP, %" PRIu64 " without a base, %" PRIu64 " NOP-ed (a COND_EXEC range too long)\n", checked.load(), unbased.load(),
			        skipped.load());
		}
	}
	// -EFAULT is not a GPU hang: a userptr BO in the list lost its pages (the guest unmapped
	// or re-protected the range since the last sync). Revalidate the mappings now and retry once.
	bool retried = false;
	if (!r.ok && !r.timed_out && r.rc == -EFAULT) {
		journal("EFAULT, resync ... ");
		sync_mappings(true, true, true);
		maps_p  = g_dev->sorted_mappings();
		retried = true;
		r       = g_dev->submit(std::span<const uint32_t>(sub_ib, sub_n), opt, 2'000'000'000ull, true, qring);
		mec_back(r.executed_offsets);
		fl_back(r.executed_offsets); // experiment 0404
	}
	if (!r.ok && !r.timed_out && !r.pending && r.rc != 0 && d432::refused_ends()) { // exp 0432 (tag r432)
		journal("exp 0432 (tag r432): submit #%" PRIu64 " %s %u dwords on ring %d was REFUSED by the device (rc %d%s): a host bug; the game ends here with a record\n", n, kind, num_dwords,
		        qring, r.rc, retried ? ", after the -EFAULT retry" : "");
		std::fprintf(stderr, "[bc5] exp 0432 (tag r432): submit #%" PRIu64 " %s %u dwords on ring %d was REFUSED by the device (rc %d): the game ends here with a record\n", n, kind,
		             num_dwords, qring, r.rc);
		fr412_record_and_exit(0, 0, false, r.rc);
	}
	if (!catch_slots.empty() && (r.timed_out || !r.pending)) catch_check(catch_slots, r.timed_out, n, kind); // experiment 0401 series e
	if (r.timed_out && fl_plan.crumbs) fl_probe(fl_plan, n, kind, true); // experiment 0404: first, before the long probe
	if (!r.timed_out && r.ok && !r.pending && fl_plan.crumbs) fl_keep_done(fl_plan, n); // exp 0401 e7 (flx) A1: the last done draw, for a later timeout
	if (!r.timed_out && r.ok && !r.pending && fl_plan.crumbs) smp_sample(fl_plan, n, kind, true); // exp 0401 e8 (smp): the draws of a completed job, at most every N s
	if (r.timed_out) timeout_probe(fl_ib.empty() ? sub_ib : ib, fl_ib.empty() ? sub_n : num_dwords, kind, g_submits.load(), &r.executed_offsets); // experiment 0160 (+ exp 0404: the buffer without the crumbs, as the offsets)
	if (r.pending) { // the completion thread waits for it and journals the result
		g_ok++;
		chain_mark_executed(chain, ib, num_dwords, r.executed_offsets);
		for (const auto& nb: r.nested) {
			SoftCp::set_gpu_executed(reinterpret_cast<const uint32_t*>(nb.cpu_addr), nb.num_dwords, nb.executed_offsets);
		}
		CqItem it;
		it.fence          = true;
		it.job.n          = n;
		it.job.kind       = kind;
		it.job.num_dwords = num_dwords;
		it.job.ib         = ib;
		if (BC5_LEAN_OR(false, BC5_DIAG_ENV("BC5_DIRECT_TIMEOUT_PROBE") != nullptr)) { if (fl_ib.empty()) it.job.ib_copy.assign(sub_ib, sub_ib + sub_n); else it.job.ib_copy.assign(ib, ib + num_dwords); it.job.ran_copy = r.executed_offsets; } // experiment 0160 (+ exp 0404: without the crumbs)
		it.job.catch_slots.swap(catch_slots); // experiment 0401 series e
		it.job.fl_plan = std::move(fl_plan); // experiment 0404
		it.job.ge_probe.swap(t_ge_probe); t_ge_probe.clear(); // experiment 0160
		it.job.filter     = r.filter;
		it.job.maps       = maps_p->size();
		it.job.prepare_ms = r.prepare_ms;
		it.job.list_ms    = r.list_ms;
		it.job.cs_ms      = r.cs_ms;
		it.job.bo_count   = r.bo_count;
		it.job.short_list = r.short_list;
		it.job.retried    = retried;
		it.job.seq        = r.seq_no;
		it.job.slot       = r.slot;
		it.job.t2_ns      = t2;
		it.job.queued_ns  = SoftCp::now_ns();
		it.job.fs_sub_ns  = fs_sub; // experiment 0415 (fs415b)
		it.job.fs_ask_ns  = fs_ask;
		it.job.fs_got_ns  = fs_got;
		it.job.fs_open_ns = fs_open; // experiment 0415 (fs415c)
		it.job.fs_why     = fs_why;
		it.job.fs_segs    = fs_segs;
		{
			const uint64_t parts[6] = {ta, tb, t1, tc, t2, ls_t3};
			for (int k = 0; k < 6; k++) it.job.fs_part_ns[k] = parts[k];
			for (int k = 0; k < 8; k++) it.job.fs_ds[k] = fs_ds[k]; // experiment 0415 (fs415d)
		}
		it.job.dev_gen    = g_dev_gen.load();
		if (ts_scale() != 1.0) ts_collect(ib, num_dwords, &it.job.ts_addrs);
		frame_profile_job(t_cq == 0, r.prepare_ms, r.list_ms, r.cs_ms);
		frame_profile_prep(t_cq == 0, r.prep_filter_ms, r.prep_tracker_ms, r.prep_cu_ms, r.prep_nested_ms, r.prep_copy_ms);
		register_label_writes(ib, num_dwords, r.executed_offsets, r.seq_no, r.ring); // experiment 0055
		ho430::job_submitted(ib, num_dwords, r.executed_offsets, r.seq_no, r.ring, kind); // exp 0430 (tag ho430)
		cq_push(std::move(it));
		return;
	}
	if (!g_dump_dir.empty() && g_journal_min) {
		if (!r.ok || (n & 0x3fu) == 0) journal("submit #%" PRIu64 " %s %u dwords at %p: pass %" PRIu64 " rewrite %" PRIu64 " drop %" PRIu64 " unmapped %" PRIu64 " cc %" PRIu64 " mappings %zu ... %s rc %d%s%s %.2f ms\n",
		        n, kind, num_dwords, static_cast<const void*>(ib), r.filter.passed, r.filter.rewritten, r.filter.dropped, r.filter.unmapped_drops,
		        r.filter.context_control_rewrites, maps_p->size(), r.ok ? "OK" : "FAILED", r.rc, r.timed_out ? " TIMEOUT" : "", retried ? " (retried)" : "", r.submit_ms);
		if (!r.ok) {
			if (FILE* f = journal_min_file(true); f != nullptr) fsync(fileno(f));
		}
	} else if (!g_dump_dir.empty()) {
		char name[512];
		std::snprintf(name, sizeof(name), "%s/direct.log", g_dump_dir.c_str());
		if (FILE* f = std::fopen(name, "a")) {
			std::fprintf(f, "%s rc %d%s%s %.2f ms\n", r.ok ? "OK" : "FAILED", r.rc, r.timed_out ? " TIMEOUT" : "", retried ? " (retried)" : "", r.submit_ms);
			std::fflush(f);
			if (!r.ok) fsync(fileno(f));
			std::fclose(f);
		}
	}
	frame_profile_job(t_cq == 0, r.prepare_ms, r.list_ms, r.cs_ms);
	frame_profile_prep(t_cq == 0, r.prep_filter_ms, r.prep_tracker_ms, r.prep_cu_ms, r.prep_nested_ms, r.prep_copy_ms);
	// A job the ring thread finished inline (jobs in flight) overlaps the game thread's jobs: it counts by its interval, not by its wait.
	frame_profile_done(t_cq == 0, g_async ? t2 : 0, g_async ? SoftCp::now_ns() : 0, r.fence_ms);
	// experiment 0415 (fs415b): a job this thread waited for itself; "queued" is taken as now less the fence wait
	{
		const uint64_t parts[6] = {ta, tb, t1, tc, t2, ls_t3};
		fs415_job(n, kind, r.ring, num_dwords, r.filter, r.bo_count, r.prepare_ms, r.list_ms, r.cs_ms, fs_sub, fs_ask, fs_got,
		          SoftCp::now_ns() - (r.fence_ms > 0 ? static_cast<uint64_t>(r.fence_ms * 1e6) : 0), r.ok ? r.gpu_start : 0, r.ok ? r.gpu_end : 0, 's', fs_open, fs_why, fs_segs, parts, fs_ds);
	}
	if (timing) {
		journal("timing: #%" PRIu64 " done at t %.3f s, %.1f ms after the sync and hints; device: prepare %.2f list %.2f cs %.2f fence %.2f ms, %u BOs%s\n", n, timing_now(),
		        static_cast<double>(SoftCp::now_ns() - t2) / 1e6, r.prepare_ms, r.list_ms, r.cs_ms, r.fence_ms, r.bo_count, r.short_list ? " (short list)" : "");
	}
	if (r.cu_tables.overrides != 0 || r.cu_tables.conditional != 0 || r.cu_tables.unreadable != 0 || r.filter.cu_mask_rewrites != 0) {
		static uint64_t cu_lines = 0;
		if (cu_lines++ < 400) {
			journal("cu mask #%" PRIu64 ": %" PRIu64 " SET_SH_REG rewritten; loads %u, overrides %u (+%u dwords), conditional %u, unreadable %u\n", n,
			        r.filter.cu_mask_rewrites, r.cu_tables.loads, r.cu_tables.overrides, r.cu_tables.inserted_dwords, r.cu_tables.conditional, r.cu_tables.unreadable);
		}
	}
	if (r.state_stack.pushes != 0 || r.state_stack.pops != 0 || r.state_stack.unmatched_pops != 0) {
		journal("state stack #%" PRIu64 ": push %u pop %u conditional %u unmatched %u; restored %u regs (+%u dwords); tables %u, unreadable %u\n", n,
		        r.state_stack.pushes, r.state_stack.pops, r.state_stack.conditional, r.state_stack.unmatched_pops, r.state_stack.restored_regs,
		        r.state_stack.inserted_dwords, r.state_stack.tables, r.state_stack.unreadable_tables);
	}
	if (r.ok) {
		g_ok++;
		chain_mark_executed(chain, ib, num_dwords, r.executed_offsets);
		for (const auto& nb: r.nested) {
			SoftCp::set_gpu_executed(reinterpret_cast<const uint32_t*>(nb.cpu_addr), nb.num_dwords, nb.executed_offsets);
		}
	}
	if (!r.ok || n < 40 || (n & 0x3fu) == 0) {
		LOGF_COLOR(r.ok ? Log::Color::Green : Log::Color::Red,
		           "[bc5-direct] submit #%" PRIu64 " %s %u dwords: %s rc %d %s %.2f ms; filter: %" PRIu64 " pass %" PRIu64 " rewrite %" PRIu64 " split %" PRIu64 " drop (%" PRIu64 " dwords) cu %" PRIu64 " int %" PRIu64 " cc %" PRIu64 " unmapped %" PRIu64 " extra %" PRIu64 " trunc %" PRIu64 "; ok so far %" PRIu64 "\n",
		           n, kind, num_dwords, r.ok ? "OK" : "FAILED", r.rc, r.timed_out ? "TIMEOUT" : "", r.submit_ms,
		           r.filter.passed, r.filter.rewritten, r.filter.split, r.filter.dropped, r.filter.dwords_dropped,
		           r.filter.cu_mask_rewrites, r.filter.int_sel_rewrites, r.filter.context_control_rewrites,
		           r.filter.unmapped_drops, r.filter.extra_drops, r.filter.truncated, g_ok.load());
	}
	if (!r.ok && r.rc == -12) { // -ENOMEM: the BO list does not fit the driver's GTT domain (run 96)
		static uint64_t last_ns = 0;
		if (const uint64_t now = SoftCp::now_ns(); last_ns == 0 || now - last_ns > 5000000000ull) {
			last_ns = now;
			direct_breakdown("ENOMEM", r.bo_count);
		}
	}
	if (r.timed_out) {
		if (g_async) { // what the game's threads still have in flight was queued on this device
			g_recovering = true;
			g_dev_gen++;
		}
		recover_after_timeout(r);
		g_recovering = false;
	}
}
#else
static void init_once() {}
static void submit(const uint32_t*, uint32_t, const char*) {}
static void post(std::function<void(bool failed)> fn) { fn(false); }
static void drain() {}
static void chain_begin() {}
static void chain_end() {}
static bool chain_on() { return false; }
static bool chain_cross() { return false; }
static bool chain_cross_mode() { return false; }
static void chain_observe() {}
static void chain_soft_push(const uint32_t*, uint32_t, const char*) {}
static void chain_soft_push_copy(const uint32_t*, uint32_t, const char*) {}
static void set_source(int) {}
static bool async_on() { return false; }
static bool on_game_thread() { return true; }
static void frame_profile_wait(bool, bool, double) {}
static void frame_profile_eqwait(double) {}
static void frame_profile_prep(bool, double, double, double, double, double) {}
static void frame_profile_post(double) {}
static void frame_profile_submit(bool, double, double) {}
static void frame_profile_job(bool, double, double, double) {}
static void frame_profile_done(bool, uint64_t, uint64_t, double) {}
static void frame_profile_flip(double) {}
static void fs415_flip(uint64_t) {} // experiment 0415 (fs415)
#endif

} // namespace Direct

// One entry of a submit list is an IT_INDIRECT_BUFFER packet: header 0xc0023f00, address lo, hi,
// IB_SIZE in dwords (bits 0..19). RPCSX hands these to its PM4 interpreter as-is; KytyPlus wants the
// DCB pointer and size, so the packet is unwrapped here.
// ADR 0010: with a chain open, a buffer's soft-CP replay waits for the end of the ioctl (the chain's
// marks exist only once it is submitted): what to replay, and whether it is posted after the fence
// (submit_raw) or run here as before (an IB packet).
struct SoftPending {
	const uint32_t* dwords;
	uint32_t        n;
	const char*     kind;
	bool            post;
};
static thread_local std::vector<SoftPending> t_soft_pending;
static void soft_posts_end() {
	if (t_soft_pending.empty()) return;
	auto marks = std::make_shared<std::vector<SoftCp::GpuDone>>(std::move(SoftCp::t_gpu_done));
	SoftCp::t_gpu_done.clear();
	for (const SoftPending& s: t_soft_pending) {
		if (s.post) {
			Direct::post([s, marks](bool failed) {
				if (failed) Direct::journal("soft-cp: %s %u dwords at %p replayed in full after a failed submission\n", s.kind, s.n, static_cast<const void*>(s.dwords));
				SoftCp::t_gpu_done = failed ? std::vector<SoftCp::GpuDone>() : *marks;
				SoftCp::submit(s.dwords, s.n, s.kind);
				SoftCp::t_gpu_done.clear();
			});
		} else {
			SoftCp::t_gpu_done = *marks;
			SoftCp::submit(s.dwords, s.n, s.kind);
			SoftCp::t_gpu_done.clear();
		}
	}
	t_soft_pending.clear();
}

static void submit_ib_packet(const uint32_t* pkt, const char* kind) {
	if (pkt[0] == 0) {
		return;
	}
	const uint64_t addr = (static_cast<uint64_t>(pkt[2]) << 32u) | pkt[1];
	const uint32_t size = pkt[3] & 0xfffffu;
	static int ib_logged = 0;
	if (Bc5Gc::gc_log_few(&ib_logged, 16)) {
		LOGF("[bc5-gc] %s: ib header 0x%08" PRIx32 " addr 0x%016" PRIx64 " size %u dwords\n", kind,
		     pkt[0], addr, size);
	}
	auto* dcb = reinterpret_cast<uint32_t*>(addr);
	dump_cb(kind, dcb, size);
	Direct::submit(dcb, size, kind);
	if (use_soft_cp() && Direct::chain_cross()) { // ADR 0010 section B: posted behind the chain's fence, once it is submitted
		Direct::chain_soft_push(dcb, size, kind);
	} else if (use_soft_cp() && Direct::chain_on()) { // ADR 0010
		t_soft_pending.push_back({dcb, size, kind, false});
	} else if (use_soft_cp()) {
		SoftCp::submit(dcb, size, kind);
	} else {
		Graphics::Gen5Driver::GraphicsDriverSubmitCommandBuffer(0, dcb, size);
	}
}

static void submit_raw(const uint32_t* dwords, uint32_t num, const char* kind) {
	if (dwords == nullptr || num == 0 || dwords[0] == 0) {
		return;
	}
	dump_cb(kind, dwords, num);
	Direct::submit(dwords, num, kind);
	if (use_soft_cp() && Direct::chain_cross()) { // ADR 0010 section B
		Direct::chain_soft_push(dwords, num, kind);
	} else if (use_soft_cp() && Direct::chain_on()) { // ADR 0010
		t_soft_pending.push_back({dwords, num, kind, true});
	} else if (use_soft_cp()) {
		auto marks = std::move(SoftCp::t_gpu_done);
		SoftCp::t_gpu_done.clear();
		Direct::post([dwords, num, kind, marks = std::move(marks)](bool failed) mutable {
			if (failed) Direct::journal("soft-cp: %s %u dwords at %p replayed in full after a failed submission\n", kind, num, static_cast<const void*>(dwords));
			SoftCp::t_gpu_done = failed ? std::vector<SoftCp::GpuDone>() : std::move(marks);
			SoftCp::submit(dwords, num, kind);
			SoftCp::t_gpu_done.clear();
		});
	} else {
		Graphics::Gen5Driver::GraphicsDriverSubmitCommandBuffer(0, const_cast<uint32_t*>(dwords),
		                                                        num);
	}
}

#ifndef BC5_LEAN
// Experiment 0418 section 3b (diagnostic, compiled out of the lean build): BC5_GC_IOCTL_TRACE=1 writes the first
// bc5::gc_trace::kCallsPerCode calls of each /dev/gc request code to stderr ("[bc5-gc-trace]"): the bytes passed in, as
// exp 0189's trace did (experiments/0189-ge-system-rings/patch_0189.py), and who sent the request: the guest return
// addresses by the frame-pointer walk from the ioctl's own frame, then the module words a scan of 64 stack quadwords above
// that frame finds (for callers built without frame pointers), each with its module and the nearest exported function at
// or before it, by NID. The NIDs are named afterwards from public tables (experiments/0418-console-start-state/impl/
// nid-names.py). It reads the stack (process_vm_readv on this process, so a bad address is an error, not a fault) and the
// dynamic symbol table the loader parsed; nothing of the title's code. The trace's own lock covers the count only: the
// runtime linker holds its lock while modules start (RuntimeLinker::StartAllModules), so FindProgramByAddr is called
// outside it. Lines of two threads can interleave; each carries its request and call number.
static bool trace_read(uint64_t addr, void* out, size_t n) {
#if defined(__linux__)
	iovec local {out, n};
	iovec remote {reinterpret_cast<void*>(static_cast<uintptr_t>(addr)), n};
	return process_vm_readv(getpid(), &local, 1, &remote, 1, 0) == static_cast<ssize_t>(n);
#else
	(void)addr;
	(void)out;
	(void)n;
	return false;
#endif
}
static bool trace_in_code(const Loader::Program* p, uint64_t addr) {
	if (p == nullptr || p->elf == nullptr) return false;
	const auto* ehdr = p->elf->GetEhdr();
	const auto* phdr = p->elf->GetPhdr();
	if (ehdr == nullptr || phdr == nullptr) return false;
	for (Loader::Elf64_Half i = 0; i < ehdr->e_phnum; i++) {
		if (phdr[i].p_type != Loader::PT_LOAD || (phdr[i].p_flags & Loader::PF_X) == 0) continue;
		const uint64_t a = phdr[i].p_vaddr + p->base_vaddr;
		if (addr >= a && addr < a + phdr[i].p_memsz) return true;
	}
	return false;
}
static void trace_where(uint64_t request, int call, const char* what, int i, uint64_t addr) {
	const Loader::Program* p = Common::Singleton<Loader::RuntimeLinker>::Instance()->FindProgramByAddr(addr);
	if (p == nullptr) {
		std::fprintf(stderr, "[bc5-gc-trace] 0x%08" PRIx64 " #%d %s %d 0x%016" PRIx64 " (no module)\n", request, call, what, i, addr);
		return;
	}
	const auto*       di     = p->dynamic_info.get();
	const std::string module = di != nullptr && di->so_name != nullptr && di->so_name[0] != 0 ? std::string(di->so_name) : p->file_name.filename().string();
	std::vector<bc5::gc_trace::Export> ex;
	if (di != nullptr && di->symbol_table != nullptr && di->str_table != nullptr) {
		const size_t n = di->symbol_table_total_size / sizeof(Loader::Elf64_Sym);
		for (size_t k = 0; k < n; k++) {
			const Loader::Elf64_Sym& s    = di->symbol_table[k];
			const auto               bind = s.GetBind();
			if (s.st_value == 0 || s.GetType() != Loader::STT_FUNC || (bind != Loader::STB_GLOBAL && bind != Loader::STB_WEAK) || s.st_name >= di->str_table_size) continue;
			ex.push_back({s.st_value + p->base_vaddr, std::string_view(di->str_table + s.st_name)});
		}
	}
	const bc5::gc_trace::Export* e = bc5::gc_trace::nearest_export(ex.data(), ex.size(), addr);
	if (e == nullptr) {
		std::fprintf(stderr, "[bc5-gc-trace] 0x%08" PRIx64 " #%d %s %d 0x%016" PRIx64 " %s+0x%" PRIx64 " (no export at or before it)\n", request, call, what, i, addr, module.c_str(), addr - p->base_vaddr);
		return;
	}
	const std::string_view nid = bc5::gc_trace::nid_of(e->name);
	std::fprintf(stderr, "[bc5-gc-trace] 0x%08" PRIx64 " #%d %s %d 0x%016" PRIx64 " %s+0x%" PRIx64 " export %.*s+0x%" PRIx64 "\n", request, call, what, i, addr, module.c_str(), addr - p->base_vaddr, static_cast<int>(nid.size()), nid.data(), addr - e->addr);
}
// `frame` is the frame address of the libkernel ioctl the guest called (Bc5LleKernel::Ioctl): {the caller's frame
// pointer, the return address into the caller}.
static void ioctl_trace(uint64_t request, const void* argp, const void* frame) {
	static const bool on = bc5::gc_trace::switch_on(BC5_DIAG_ENV("BC5_GC_IOCTL_TRACE"));
	if (!on) return;
	int call = 0;
	{
		static std::mutex              m;
		static std::map<uint64_t, int> seen;
		std::lock_guard                lk(m);
		call = ++seen[request];
	}
	if (call > bc5::gc_trace::kCallsPerCode) return;
	// _IOC: size bits 29:16, 0x80000000 = the caller passes data in, 0x40000000 = the kernel writes it back.
	const uint32_t size = (static_cast<uint32_t>(request) >> 16u) & 0x1fffu;
	const bool     in   = (request & 0x80000000u) != 0;
	const bool     out  = (request & 0x40000000u) != 0;
	std::string    line;
	char           w[16];
	if (in && argp != nullptr) {
		const auto* a = static_cast<const uint32_t*>(argp);
		for (uint32_t i = 0; i < size / 4 && i < 64; i++) {
			std::snprintf(w, sizeof(w), " %08x", a[i]);
			line += w;
		}
	}
	std::fprintf(stderr, "[bc5-gc-trace] ioctl 0x%08" PRIx64 " (size %u, %s%s) call %d:%s\n", request, size, in ? "in" : "", out ? "out" : "", call, line.c_str());
	// Exp 0418 point 5: 0x80888123 is a table of address and size pairs (136 bytes: 8 pairs and a trailing quadword,
	// exp 0189's trace, F787). Each address is named by the guest mapping it lies in, under the name the title's driver
	// gave that mapping (KernelVirtualQuery), so the trace says which of the driver's areas the table lists.
	if (request == 0x80888123u && in && argp != nullptr) {
		const auto* q = static_cast<const uint64_t*>(argp);
		for (uint32_t i = 0; i + 1 < size / 8; i += 2) {
			if (q[i] == 0) continue;
			LibKernel::Memory::VirtualQueryInfo vq {};
			const int r = LibKernel::Memory::KernelVirtualQuery(reinterpret_cast<const void*>(static_cast<uintptr_t>(q[i])), 0, &vq, sizeof(vq));
			char nm[sizeof(vq.name) + 1] = {};
			std::memcpy(nm, vq.name, sizeof(vq.name));
			if (r != 0) {
				std::fprintf(stderr, "[bc5-gc-trace] 0x%08" PRIx64 " #%d pair %u 0x%016" PRIx64 " size 0x%" PRIx64 " (no mapping, %d)\n", request, call, i / 2, q[i], q[i + 1], r);
				continue;
			}
			std::fprintf(stderr, "[bc5-gc-trace] 0x%08" PRIx64 " #%d pair %u 0x%016" PRIx64 " size 0x%" PRIx64 " mapping '%s' 0x%016" PRIx64 "-0x%016" PRIx64 " %s prot 0x%x\n",
			             request, call, i / 2, q[i], q[i + 1], nm, static_cast<uint64_t>(vq.start), static_cast<uint64_t>(vq.end),
			             vq.is_flexible != 0 ? "flexible" : vq.is_direct != 0 ? "direct" : "other", static_cast<unsigned>(vq.protection));
		}
	}
	const auto fp = static_cast<uint64_t>(reinterpret_cast<uintptr_t>(frame));
	uint64_t   ret[bc5::gc_trace::kMaxFrames] = {};
	const int  nf = bc5::gc_trace::walk_frames(fp, [](uint64_t a, uint64_t* two) { return trace_read(a, two, 16); }, ret, bc5::gc_trace::kMaxFrames);
	for (int i = 0; i < nf; i++) trace_where(request, call, "frame", i, ret[i]);
	uint64_t words[64] = {};
	if (fp != 0 && trace_read(fp + 16, words, sizeof(words))) {
		auto*     rt = Common::Singleton<Loader::RuntimeLinker>::Instance();
		uint64_t  found[12] = {};
		const int ns = bc5::gc_trace::scan_words(words, 64, [rt](uint64_t v) { return trace_in_code(rt->FindProgramByAddr(v), v); }, found, 12);
		for (int i = 0; i < ns; i++) trace_where(request, call, "scan", i, found[i]);
	}
}
#endif // BC5_LEAN

// Returns 0 on success or a positive errno (the libkernel wrapper turns it into -1/errno).
static int gc_ioctl(uint64_t request, void* argp) {
	switch (request) {
		case 0xc004812e: { // ps5: capability/flag query; RPCSX answers unk=0, flag=0
			auto* a = static_cast<uint16_t*>(argp);
			a[0]    = 0;
			a[1]    = 0;
			return 0;
		}
		case 0xc008811b: { // get submit-done flag pointer (one GPU-visible page)
			std::lock_guard lock(g_mutex);
			if (g_submit_area == nullptr) {
				void* addr = nullptr;
				int   r    = LibKernel::Memory::KernelMapNamedFlexibleMemory(
				       &addr, 0x4000, 0x33 /* cpu rw, gpu rw */, 0, "bc5-gc-submit");
				if (r != 0 || addr == nullptr) {
					LOGF_COLOR(Log::Color::Red, "[bc5-gc] submit area alloc failed: %d\n", r);
					return 12; // ENOMEM
				}
				std::memset(addr, 0, 0x4000);
				g_submit_area = addr;
			}
			*static_cast<void**>(argp) = g_submit_area;
			LOGF("[bc5-gc] submit area = %p\n", g_submit_area);
			return 0;
		}
		case 0xc0488131: { // ps5 submit header: contextControl[3] + 3 x IB packet + status
			struct Args {
				uint32_t unk0;
				uint32_t context_control[3];
				uint32_t cmds[3 * 4];
				uint64_t status;
			};
			static_assert(sizeof(Args) == 72);
			auto* a = static_cast<Args*>(argp);
			static int submit_logged = 0;
			if (Bc5Gc::gc_log_few(&submit_logged)) {
				LOGF("[bc5-gc] submit header: unk0 0x%08" PRIx32 " cc %08" PRIx32 " %08" PRIx32
				     " %08" PRIx32 "\n",
				     a->unk0, a->context_control[0], a->context_control[1], a->context_control[2]);
			}
			Direct::chain_begin(); // ADR 0010: the header's buffers as one submission
			submit_raw(a->context_control, 3, "cc");
			for (int i = 0; i < 3; i++) {
				submit_ib_packet(a->cmds + i * 4, "hib"); // header IBs: state preamble + the 2-dword IB
			}
			Direct::chain_end();
			soft_posts_end();
			a->status = 0;
			return 0;
		}
		case 0xc0188132: { // ps5 submit list: count/2 entries of {unk0, unk1, address, size}
			struct Submit {
				uint64_t unk0;
				uint64_t unk1;
				uint64_t address;
				uint64_t size;
			};
			struct Args {
				uint32_t unk0;
				uint32_t count;
				Submit*  submits;
				uint32_t status;
				uint32_t padding;
			};
			static_assert(sizeof(Args) == 24);
			auto* a = static_cast<Args*>(argp);
			if (!g_journal_min) LOGF("[bc5-gc] submit list: unk0 %u count %u\n", a->unk0, a->count);
			Direct::chain_begin(); // ADR 0010
			for (uint32_t i = 0; i < a->count / 2; i++) {
				const auto& s = a->submits[i];
				if (!g_journal_min) {
					LOGF("[bc5-gc]   [%u] unk0 0x%016" PRIx64 " unk1 0x%016" PRIx64 " addr 0x%016" PRIx64
					     " size %" PRIu64 "\n",
					     i, s.unk0, s.unk1, s.address, s.size);
				}
				submit_raw(reinterpret_cast<const uint32_t*>(s.address),
				           static_cast<uint32_t>(s.size), "dcb");
			}
			Direct::chain_end();
			soft_posts_end();
			a->status = 0;
			return 0;
		}
		case 0xc0108102: { // submit: count x IB packet
			struct Args {
				uint32_t  arg0;
				uint32_t  count;
				uint32_t* cmds;
			};
			auto* a = static_cast<Args*>(argp);
			static int submit_logged = 0;
			if (gc_log_few(&submit_logged)) LOGF("[bc5-gc] submit: arg0 %u count %u\n", a->arg0, a->count);
			Direct::chain_begin(); // ADR 0010
			for (uint32_t i = 0; i < a->count; i++) {
				submit_ib_packet(a->cmds + i * 4, "dcb");
			}
			Direct::chain_end();
			soft_posts_end();
			return 0;
		}
		case 0xc020810c: { // submit and write eop
			struct Args {
				uint32_t  arg0;
				uint32_t  count;
				uint32_t* cmds;
				uint64_t  eop_value;
				uint32_t  wait_flag;
			};
			auto* a = static_cast<Args*>(argp);
			static int submit_eop_logged = 0;
			if (gc_log_few(&submit_eop_logged)) {
				LOGF("[bc5-gc] submit+eop: arg0 %u count %u eop 0x%016" PRIx64 " wait %u\n", a->arg0, a->count, a->eop_value, a->wait_flag);
			}
			Direct::chain_begin(); // ADR 0010
			for (uint32_t i = 0; i < a->count; i++) {
				submit_ib_packet(a->cmds + i * 4, "dcb");
			}
			Direct::chain_end();
			soft_posts_end();
			// TODO(bc5): where the EOP value is written on the console is not known yet (RPCSX
			// has its own submitWriteEop); the submit-done page gets it for now.
			if (g_submit_area != nullptr) {
				static_cast<uint64_t*>(g_submit_area)[0] = a->eop_value;
			}
			// Experiment 0405 G6 (BC5_R3_SUBMIT_EOP_EVENT): the graphics EOP event with eop_value once the buffers above have
			// run (SoftCp::r3gpu_submit_eop; RPCSX rpcsx/iodev/gc.cpp:250-277). Off: today's, the value stored only.
			if (SoftCp::r3gpu().submit_eop) SoftCp::r3gpu_submit_eop(a->eop_value);
			return 0;
		}
		case 0xc0088101: // switch buffer
			return 0;
		case 0xc0048116: // submit done
		case 0xc0048117: { // wait idle
			// Experiment 0084: with asynchronous submission these returned at once, so a title that
			// asks for an idle GPU before rewriting its data did not wait; draining the jobs in
			// flight there changed nothing (F144). Calls are counted in the journal (every 500th).
			static std::atomic<uint64_t> n_done {0}, n_idle {0};
			const bool idle = request == 0xc0048117;
			const uint64_t n = idle ? ++n_idle : ++n_done;
			if (n == 1 || n % 500 == 0) Direct::journal("gc ioctl %s: %" PRIu64 " calls\n", idle ? "wait idle" : "submit done", n);
			Direct::chain_observe(); // ADR 0010 section B: the title asks about the GPU
			// Experiment 0405 G12 (BC5_R3_WAIT_IDLE): "wait idle" blocks until the work handed over has run (RPCSX e8ae148
			// rpcsx/iodev/gc.cpp:287-293 waits for idle in 0xc0048117. Its 0xc0048116, gc.cpp:279-285, has the wait commented
			// out but no break, so it falls into the same wait: TODO(verify) whether that is meant; 0xc0048116 stays as it is
			// here, as R3's spec says). Here it returns once the completion queues are empty: every job queued so far has
			// passed its fence and every soft-CP replay posted behind one has run, the wait Direct::drain() does at the flip,
			// but without drain()'s chain flushes (chain_observe above already submitted the held chains; a flush here could
			// close another thread's chain earlier, a different submission) and bounded at 2 s (a replay's label poll can
			// hold a queue).
			// Without asynchronous submission each job was waited for when it was submitted: nothing to wait for.
			// Off: today's, at once.
			if (idle && SoftCp::r3gpu().wait_idle) {
				const uint64_t t0      = SoftCp::now_ns();
				bool           gave_up = false;
#if defined(KYTY_BC5_DIRECT)
				if (Direct::async_on()) {
					while (Direct::g_cq_items.load() != 0) {
						if (SoftCp::now_ns() - t0 >= 2'000'000'000ull) {
							gave_up = true;
							break;
						}
						std::this_thread::sleep_for(std::chrono::microseconds(50));
					}
				}
#endif
				SoftCp::r3gpu_wait_idle_note(gave_up, static_cast<double>(SoftCp::now_ns() - t0) / 1e6);
			}
			return 0;
		}
		case 0xc010810b: { // cu masks: every CU of SE0/SE1, SH0/SH1
			auto* m = static_cast<uint32_t*>(argp);
			m[0] = m[1] = m[2] = m[3] = ~0u;
			return 0;
		}
		case 0xc0408121: { // ps5: queue registration (56 per run); layout is a working hypothesis
			struct Args {
				uint32_t a, b, c, d;       // {1|2, 2}, {slot 0x2b.., index 0..7}
				uint64_t ring_base;        // 16 KiB ring in SceGnmACQRB
				uint64_t ring_end;
				uint64_t doorbell_page;    // the mmap'd submit page (0xfe0200000)
				uint64_t doorbell_slot;    // 0xc
				uint64_t rptr_addr;        // a page in SceGnmEopFifo
				uint64_t rptr_size;        // 0x1000
			};
			static_assert(sizeof(Args) == 64);
			auto* a = static_cast<Args*>(argp);
			LOGF("[bc5-gc] queue reg: %u %u %u 0x%x ring 0x%" PRIx64 "-0x%" PRIx64 " doorbell 0x%" PRIx64
			     "+0x%" PRIx64 " rptr 0x%" PRIx64 " (0x%" PRIx64 ")\n",
			     a->a, a->b, a->c, a->d, a->ring_base, a->ring_end, a->doorbell_page, a->doorbell_slot,
			     a->rptr_addr, a->rptr_size);
			{
				std::lock_guard lock(g_mutex);
				g_queues.push_back({a->a, a->b, a->c, a->d, a->ring_base, a->ring_end, a->doorbell_page,
				                    a->doorbell_slot, a->rptr_addr});
				if (!g_queue_probe_started) {
					g_queue_probe_started = true;
					std::thread(SoftCp::queue_consumer_thread).detach();
				}
			}
			return 0; // out: zeros (whatever the kernel returns here is not known yet)
		}
		case 0xc0048113: // num clients
			*static_cast<uint32_t*>(argp) = 1;
			return 0;
		case 0xc0048115: // is game closed
			*static_cast<uint32_t*>(argp) = 0;
			return 0;
		case 0x80108128: { // experiment 0189: the title's tessellation-factor ring {u64 base, u32 size, u32 0}
			const auto* a = static_cast<const uint32_t*>(argp);
			g_gc_tf_base  = static_cast<uint64_t>(a[0]) | (static_cast<uint64_t>(a[1]) << 32u);
			g_gc_tf_size  = a[2];
			std::fprintf(stderr, "bc5-direct: /dev/gc TF ring 0x%" PRIx64 " size 0x%x%s\n", g_gc_tf_base.load(), a[2], gc_tf_ring_on() ? " (programmed, row VGT_TF_RING)" : " (not programmed: SKIP names VGT_TF_RING)");
			return 0;
		}
		case 0x8004812a: { // experiment 0189: one dword after the TF ring, by its place the HS offchip parameter
			const uint32_t v  = *static_cast<const uint32_t*>(argp);
			g_gc_hs_offchip   = 0x100000000ull | v;
			std::fprintf(stderr, "bc5-direct: /dev/gc HS offchip 0x%x%s\n", v, gc_hs_offchip_on() ? " (programmed, row VGT_HS_OFFCHIP_PARAM)" : " (not programmed: SKIP names VGT_HS_OFFCHIP_PARAM)");
			return 0;
		}
		case 0xc00c8110: { // set gs ring sizes
			auto* a = static_cast<uint32_t*>(argp);
			LOGF("[bc5-gc] gs ring sizes: %u %u %u\n", a[0], a[1], a[2]);
			// Experiment 0418: kept as register values (bytes >> 8; bc5/start_state.hpp gs_rings_from_request says why
			// bytes); Direct::gs_rings_prefix writes them when the table's VGT_GS_RINGS row is on.
			bc5::start_state::GsRings r;
			const bool                ok = bc5::start_state::gs_rings_from_request(a, r);
			if (ok) g_gc_gs_rings = (1ull << 63u) | (static_cast<uint64_t>(r.gsvs) << 32u) | r.esgs;
			std::fprintf(stderr, "bc5-direct: /dev/gc GS ring sizes 0x%x 0x%x 0x%x%s\n", a[0], a[1], a[2],
			             !ok ? " (0 or not a multiple of 256: not programmed)" : gc_gs_rings_on() ? " (programmed, row VGT_GS_RINGS)" : "");
			return 0;
		}
		case 0xc0848119: { // stats report control
			auto* a = static_cast<uint32_t*>(argp);
			LOGF("[bc5-gc] stats report control: 0x%08" PRIx32 " %u %u %u\n", a[0], a[1], a[2],
			     a[3]);
			return 0;
		}
		case 0xc030810d: { // map compute queue
			struct Args {
				uint32_t me_id;
				uint32_t pipe_id;
				uint32_t queue_id;
				uint32_t vqueue_id;
				uint64_t ring_base;
				uint64_t read_ptr;
				uint64_t doorbell;
				uint32_t ring_size_log2;
			};
			auto* a = static_cast<Args*>(argp);
			LOGF_COLOR(Log::Color::Yellow,
			           "[bc5-gc] map compute queue me %u pipe %u queue %u vqueue %u ring 0x%016" PRIx64
			           " rptr 0x%016" PRIx64 " doorbell 0x%016" PRIx64 " size 2^%u (TODO: not wired)\n",
			           a->me_id, a->pipe_id, a->queue_id, a->vqueue_id, a->ring_base, a->read_ptr,
			           a->doorbell, a->ring_size_log2);
			return 0;
		}
		case 0xc010811c: { // ding dong for workload (compute queue kick)
			auto* a = static_cast<uint32_t*>(argp);
			LOGF_COLOR(Log::Color::Yellow, "[bc5-gc] ding dong me %u pipe %u queue %u offset %u (TODO)\n",
			           a[0], a[1], a[2], a[3]);
			return 0;
		}
		default: {
			// _IOC direction bits: 0x40000000 = read (kernel writes argp), 0x80000000 = write.
			const uint32_t size = (static_cast<uint32_t>(request) >> 16u) & 0x1fffu;
			const bool     out  = (request & 0x40000000u) != 0;
			const bool in = (request & 0x80000000u) != 0;
			static int unhandled_logged = 0;
			const bool log_this = gc_log_few(&unhandled_logged, 16);
			if (log_this) {
				LOGF_COLOR(Log::Color::Yellow,
				           "[bc5-gc] unhandled ioctl 0x%08" PRIx64 " (size %u, %s%s): answered with zeros\n",
				           request, size, in ? "in" : "", out ? "out" : "");
			}
			if (log_this && in && argp != nullptr && size != 0) {
				const auto* q = static_cast<const uint64_t*>(argp);
				for (uint32_t i = 0; i < size / 8; i += 4) {
					LOGF("[bc5-gc]   +%03x: %016" PRIx64 " %016" PRIx64 " %016" PRIx64 " %016" PRIx64 "\n",
					     i * 8, q[i], i + 1 < size / 8 ? q[i + 1] : 0, i + 2 < size / 8 ? q[i + 2] : 0,
					     i + 3 < size / 8 ? q[i + 3] : 0);
				}
			}
			if (out && argp != nullptr && size != 0) {
				std::memset(argp, 0, size);
			}
			return 0;
		}
	}
}

// Experiment 0405 (tag gpu): the CPU test's seam into gc_ioctl (gpu0405.cpp, G6 and G12); never called by the emulator.
extern "C" int bc5_exp0405_gpu_gc_ioctl(uint64_t request, void* argp) {
	return gc_ioctl(request, argp);
}

// /dev/dipsw: dip-switch (debug setting) queries from libSceAgc. All switches off.
static int dipsw_ioctl(uint64_t request, void* argp) {
	const uint32_t size = (static_cast<uint32_t>(request) >> 16u) & 0x1fffu;
	LOGF("[bc5-gc] dipsw ioctl 0x%08" PRIx64 " -> 0\n", request);
	if ((request & 0x40000000u) != 0 && argp != nullptr && size != 0) {
		std::memset(argp, 0, size);
	}
	return 0;
}

} // namespace Bc5Gc

// ADR 0010 section B: a wait on an event queue that carries EVFILT_GRAPHICS events (the title's EOP
// queues) is a point where the title observes the GPU; the chains held across ioctls are submitted
// first (their replays post those events). Called by LibKernel::EventQueue::KernelWaitEqueue.
void Bc5ChainObserveEqueue(LibKernel::EventQueue::KernelEqueue eq) {
	if (!Bc5Gc::Direct::chain_cross_mode()) return;
	bool graphics = false;
	{
		std::lock_guard lock(Bc5Gc::SoftCp::g_eq_mutex);
		for (const auto& r: Bc5Gc::SoftCp::g_eqs) {
			if (r.eq == eq) {
				graphics = true;
				break;
			}
		}
	}
	if (graphics) Bc5Gc::Direct::chain_observe();
}

// ---------------------------------------------------------------------------------------------
// libkernel
// ---------------------------------------------------------------------------------------------
namespace Bc5LleKernel {

LIB_VERSION("libkernel", 1, "libkernel", 1, 1);

namespace FS  = LibKernel::FileSystem;
namespace Mem = LibKernel::Memory;
namespace EQ  = LibKernel::EventQueue;

// ioctl(fd, request, argp): raw BSD semantics, 0 or -1.
static KYTY_SYSV_ABI int Ioctl(int fd, uint64_t request, void* argp) {
	PRINT_NAME();
	std::string dev;
	if (!FS::KernelGetSpecialDeviceName(fd, &dev)) {
		LOGF_COLOR(Log::Color::Red, "[bc5-gc] ioctl on non-device fd %d request 0x%08" PRIx64 "\n",
		           fd, request);
		return -1;
	}
	int err = 0;
	if (dev == "/dev/gc") {
		Bc5Gc::Direct::init_once();
#ifndef BC5_LEAN
		Bc5Gc::ioctl_trace(request, argp, __builtin_frame_address(0)); // experiment 0418 section 3b (BC5_GC_IOCTL_TRACE=1)
#endif
		err = Bc5Gc::gc_ioctl(request, argp);
	} else if (dev == "/dev/dipsw") {
		err = Bc5Gc::dipsw_ioctl(request, argp);
	} else {
		LOGF_COLOR(Log::Color::Red, "[bc5-gc] ioctl on unknown device %s\n", dev.c_str());
		err = 25; // ENOTTY
	}
	return err == 0 ? 0 : -1;
}

// ---- exp 0401 series e5 (eq0405): exp 0405's fixes of the libkernel mmap, kevent and timer shims ------------------
} // namespace Bc5LleKernel (eq0405 closes it here for two declarations and opens it again below)

namespace LibKernel::EventQueue {
// Defined in src/kernel/eventQueue.cpp by the same edit (mkeq0405.py); no header declares them (no header may change), so
// a build that pairs this unit with an unedited eventQueue.cpp.o fails at the link.
uint32_t          Bc5EqueueFixes0405();
int KYTY_SYSV_ABI Bc5KernelAddTimerEvent0405(KernelEqueue eq, int id, KernelUseconds usec, void* udata);
} // namespace LibKernel::EventQueue

namespace Bc5LleKernel {

// The bits of EQ::Bc5EqueueFixes0405() (KYTY_BC5_EQUEUE_FIXES, read and journalled in eventQueue.cpp) used here.
static constexpr uint32_t BC5_EQ_FIX_G1_0405   = 4u; // "g1": kevent honours its timespec (exp 0405 R3 G1)
static constexpr uint32_t BC5_EQ_FIX_KK01_0405 = 8u; // "kk01": sceKernelAddTimerEvent is periodic (exp 0405 R2 KK01)

// KYTY_BC5_MMAP_SHIM_FIXES (exp 0405 R3 M2), the mmap shim below:
// - "hint": an anonymous mapping (fd < 0) whose flags lack MAP_FIXED (0x10) takes its address as a hint, the start of the
//   search for free space, and no longer replaces what is mapped there. shadPS4 60c42b9
//   src/core/libraries/kernel/memory.cpp:753-816 (posix_mmap passes the flags on; its MapMemory replaces only with
//   Fixed), AnyPS5 4f41f4c37 core/libs/prx/libkernel/DirectMemory/PosixMemory.cpp:145-249, sharpemu 514d766
//   KernelMemoryCompatExports.Mmap.cs:10-42 (all GPL; behaviour only, no line copied). A device mapping (fd >= 0) keeps
//   today's path, fixed at its address: Sony's driver maps the gc page at 0xfe0200000 (exp 0011), and its flags were
//   logged as MAP_SHARED without saying whether MAP_FIXED is set (TODO(verify) in a run's "[bc5-gc] mmap" line).
//   MAP_FIXED keeps today's path (it replaces, as POSIX says).
// - "prot": prot 0 stays no-access (today it becomes 0x33), and a mapping without CPU write is not cleared with memset
//   (it would fault; flexible memory is zeroed when mapped, memory.cpp FlexibleMemory::Map's ZeroBacking).
// Unset, empty or "0" is off (today's path exactly); any other value turns both on, unless it names items
// (comma-separated "hint", "prot"): then only those. Read once; one stderr line at the first mmap.
static constexpr uint32_t BC5_MMAP_FIX_HINT = 1u;
static constexpr uint32_t BC5_MMAP_FIX_PROT = 2u;

// Not static: the CPU test eq0405.cpp declares them.
uint32_t Bc5MmapShimFixesParse0405(const char* value);
uint32_t Bc5MmapShimFixes0405();

uint32_t Bc5MmapShimFixesParse0405(const char* value) {
	if (value == nullptr || value[0] == '\0' || std::strcmp(value, "0") == 0) {
		return 0;
	}
	uint32_t    items = 0;
	const char* p     = value;
	for (;;) {
		const char*  comma = std::strchr(p, ',');
		const size_t n     = comma != nullptr ? static_cast<size_t>(comma - p) : std::strlen(p);
		if (n == 4 && std::strncmp(p, "hint", n) == 0) {
			items |= BC5_MMAP_FIX_HINT;
		} else if (n == 4 && std::strncmp(p, "prot", n) == 0) {
			items |= BC5_MMAP_FIX_PROT;
		}
		if (comma == nullptr) {
			break;
		}
		p = comma + 1;
	}
	return items != 0 ? items : (BC5_MMAP_FIX_HINT | BC5_MMAP_FIX_PROT);
}

// The items of KYTY_BC5_MMAP_SHIM_FIXES that are on (0: off), read once.
uint32_t Bc5MmapShimFixes0405() {
	static const uint32_t items = [] {
		const uint32_t v = Bc5MmapShimFixesParse0405(BC5_FIXED_ENV("KYTY_BC5_MMAP_SHIM_FIXES", "1"));
		if (v == 0) {
			std::fprintf(stderr, "[bc5] exp 0405: mmap shim fixes off\n");
		} else {
			std::fprintf(stderr, "[bc5] exp 0405: mmap shim fixes on (items:%s%s)\n", (v & BC5_MMAP_FIX_HINT) != 0 ? " hint" : "",
			             (v & BC5_MMAP_FIX_PROT) != 0 ? " prot" : "");
		}
		std::fflush(stderr);
		return v;
	}();
	return items;
}

// "hint" catcher: an anonymous hint that was not free; the first 8 go to stderr.
static void Bc5MmapHintMoved0405(const void* hint, const void* got, size_t len) {
	static std::atomic<uint32_t> told {0};
	const uint32_t                n = told.fetch_add(1, std::memory_order_relaxed);
	if (n < 8) {
		std::fprintf(stderr, "[bc5] exp 0405: mmap hint %p len 0x%zx is not free: mapped at %p (#%u)\n", hint, len, got,
		             static_cast<unsigned>(n + 1));
		std::fflush(stderr);
	}
}

// "g1" (exp 0405 R3 G1): kevent's wait with a timespec (FreeBSD amd64 struct timespec, LibKernel::KernelTimespec's
// layout). FreeBSD kevent(2): a zero timespec polls; when the time runs out, 0 is returned; a timespec with tv_sec < 0,
// tv_nsec < 0 or tv_nsec >= 1e9 is EINVAL. AnyPS5 4f41f4c37 core/libs/prx/libkernel/Equeue/src/Kqueue.cpp:545-551 and
// 669-678 (GPL-2.0-only; read for the semantics only) does the same and waits without a deadline when tv_sec > INT32_MAX.
// TODO(verify): FreeBSD's sys/kern/kern_event.c (kqueue_scan) was not read tonight (no network). Rounded up to whole
// microseconds; waited in parts of 1000 s because KernelWaitEqueue takes 32-bit microseconds. -1 sets no errno, like this
// shim's other failures. The first 8 calls go to stderr (whether the graphics driver's waits carry a timeout is not known).
static int Bc5KeventTimed0405(EQ::KernelEqueue eq, EQ::KernelEvent* events, int nevents, const void* timeout) {
	static std::atomic<uint32_t> told {0};
	LibKernel::KernelTimespec    ts {};
	std::memcpy(&ts, timeout, sizeof(ts));
	int result = 0;
	if (ts.tv_sec < 0 || ts.tv_nsec < 0 || ts.tv_nsec >= 1000000000) {
		result = -1;
	} else if (ts.tv_sec > INT32_MAX) {
		int       out = 0;
		const int r   = EQ::KernelWaitEqueue(eq, events, nevents, &out, nullptr);
		result        = r == 0 ? out : -1;
	} else {
		constexpr uint64_t kPartUs = 1000000000ull;
		uint64_t           left_us = static_cast<uint64_t>(ts.tv_sec) * 1000000ull +
		                            (static_cast<uint64_t>(ts.tv_nsec) + 999ull) / 1000ull;
		for (;;) {
			const auto part = static_cast<LibKernel::KernelUseconds>(std::min(left_us, kPartUs));
			int        out  = 0;
			const int  r    = EQ::KernelWaitEqueue(eq, events, nevents, &out, &part);
			if (r == 0) {
				result = out;
				break;
			}
			if (r != LibKernel::KERNEL_ERROR_ETIMEDOUT) {
				result = -1;
				break;
			}
			if (left_us <= part) {
				result = 0;
				break;
			}
			left_us -= part;
		}
	}
	const uint32_t n = told.fetch_add(1, std::memory_order_relaxed);
	if (n < 8) {
		std::fprintf(stderr, "[bc5] exp 0405: kevent eq %d timeout {%lld s, %lld ns} nevents %d -> %d (#%u)\n",
		             static_cast<int>(eq), static_cast<long long>(ts.tv_sec), static_cast<long long>(ts.tv_nsec), nevents,
		             result, static_cast<unsigned>(n + 1));
		std::fflush(stderr);
	}
	return result;
}

// "kk01": sceKernelDeleteTimerEvent (YWQFUyXIVdU), registered only with the switch on (AnyPS5 4f41f4c37
// core/libs/prx/libkernel/Equeue/Equeue.cpp:841-843, GPL-2.0-only; adapted).
static KYTY_SYSV_ABI int Bc5DeleteTimerEvent0405(EQ::KernelEqueue eq, int id) {
	PRINT_NAME();
	return EQ::KernelDeleteEvent(eq, static_cast<uintptr_t>(id), EQ::KERNEL_EVFILT_TIMER);
}
// ---- end of exp 0401 series e5 (eq0405)'s block ----------------------------------------------------------------------

// mmap(addr, len, prot, flags, fd, offset). The driver maps the gc device at a fixed guest address
// (0xfe0200000, 16 KiB, prot 0x22 = cpu write | gpu write, MAP_SHARED) and keeps the returned
// pointer; anonymous mappings go to flexible memory. Returns nullptr on failure (the driver tests
// the result against 0, not MAP_FAILED).
static KYTY_SYSV_ABI void* Mmap(void* addr, size_t len, int prot, int flags, int fd,
                                int64_t offset) {
	PRINT_NAME();
	LOGF("[bc5-gc] mmap addr %p len 0x%zx prot 0x%x flags 0x%x fd %d off 0x%" PRIx64 "\n", addr,
	     len, prot, flags, fd, offset);
	// exp 0401 series e5 (eq0405, KYTY_BC5_MMAP_SHIM_FIXES): "prot" keeps prot 0 no-access; "hint" makes an anonymous
	// mapping's address without MAP_FIXED a hint. Off: today's path.
	const uint32_t bc5_mmap_fixes = Bc5MmapShimFixes0405();
	const bool     bc5_hint_only  = (bc5_mmap_fixes & BC5_MMAP_FIX_HINT) != 0 && fd < 0 &&
	                           (static_cast<uint32_t>(flags) & Bc5Gc::GUEST_MAP_FIXED) == 0;
	if (prot == 0 && (bc5_mmap_fixes & BC5_MMAP_FIX_PROT) == 0) {
		prot = 0x33;
	}
	void* out = addr;
	int   r   = Mem::KernelMapNamedFlexibleMemory(&out, len, prot,
	                                              (addr != nullptr && !bc5_hint_only) ? Bc5Gc::GUEST_MAP_FIXED : 0,
	                                              fd >= 0 ? "bc5-gc-mmap" : "bc5-anon-mmap");
	if (r != 0 && addr != nullptr) {
		LOGF_COLOR(Log::Color::Yellow, "[bc5-gc] fixed mmap at %p failed (%d), retrying anywhere\n",
		           addr, r);
		out = nullptr;
		r   = Mem::KernelMapNamedFlexibleMemory(&out, len, prot, 0,
		                                        fd >= 0 ? "bc5-gc-mmap" : "bc5-anon-mmap");
	}
	if (r != 0) {
		LOGF_COLOR(Log::Color::Red, "[bc5-gc] mmap failed: %d\n", r);
		return nullptr;
	}
	if (bc5_hint_only && addr != nullptr && out != addr) {
		Bc5MmapHintMoved0405(addr, out, len); // exp 0401 series e5 (eq0405) "hint": the catcher
	}
	if ((bc5_mmap_fixes & BC5_MMAP_FIX_PROT) == 0 || (prot & 0x02) != 0) { // eq0405 "prot": no memset without CPU write
		std::memset(out, 0, len);
	}
	return out;
}

// kevent(kq, changelist, nchanges, eventlist, nevents, timeout). libSceAgcDriver only uses it to
// add/delete EVFILT_GRAPHICS (-14) events on an event queue created with sceKernelCreateEqueue,
// which in KytyPlus is a small integer handle, so the truncation to int on the way in is harmless.
static KYTY_SYSV_ABI int Kevent(int kq, const Bc5Gc::KEvent* changes, int nchanges,
                                Bc5Gc::KEvent* events, int nevents, const void* timeout) {
	PRINT_NAME();
	const auto eq = static_cast<EQ::KernelEqueue>(kq);
	for (int i = 0; i < nchanges; i++) {
		const auto& c = changes[i];
		LOGF("[bc5-gc] kevent change: ident 0x%" PRIx64 " filter %d flags 0x%x fflags 0x%x data 0x%"
		     PRIx64 " udata %p\n",
		     c.ident, c.filter, c.flags, c.fflags, c.data, c.udata);
		if (c.filter == EQ::KERNEL_EVFILT_GRAPHICS) {
			if ((c.flags & Bc5Gc::EV_DELETE) != 0) {
				Graphics::Gen5Driver::GraphicsDriverDeleteEqEvent(eq, static_cast<int>(c.ident));
				Bc5Gc::SoftCp::register_eq(eq, static_cast<int>(c.ident), false);
			} else if ((c.flags & Bc5Gc::EV_ADD) != 0) {
				int r = Graphics::Gen5Driver::GraphicsDriverAddEqEvent(eq, static_cast<int>(c.ident),
				                                                       c.udata);
				if (r != 0) {
					LOGF_COLOR(Log::Color::Red, "[bc5-gc] AddEqEvent failed: 0x%08x\n", r);
					return -1;
				}
				Bc5Gc::SoftCp::register_eq(eq, static_cast<int>(c.ident), true);
			}
		} else {
			LOGF_COLOR(Log::Color::Yellow, "[bc5-gc] kevent: filter %d not handled\n", c.filter);
		}
	}
	if (nevents > 0 && events != nullptr) {
		int out = 0;
		Bc5Gc::Direct::chain_observe(); // ADR 0010 section B: the EOP events it waits for come after the chain's fence
		const uint64_t t_eq = Bc5Gc::SoftCp::now_ns();
		if (timeout != nullptr && (EQ::Bc5EqueueFixes0405() & BC5_EQ_FIX_G1_0405) != 0) {
			// exp 0401 series e5 (eq0405, KYTY_BC5_EQUEUE_FIXES g1): the timespec is honoured; off, today's wait below
			const int n = Bc5KeventTimed0405(eq, reinterpret_cast<EQ::KernelEvent*>(events), nevents, timeout);
			Bc5Gc::Direct::frame_profile_eqwait(static_cast<double>(Bc5Gc::SoftCp::now_ns() - t_eq) / 1e6);
			return n;
		}
		int r   = EQ::KernelWaitEqueue(eq, reinterpret_cast<EQ::KernelEvent*>(events), nevents,
		                               &out, nullptr);
		Bc5Gc::Direct::frame_profile_eqwait(static_cast<double>(Bc5Gc::SoftCp::now_ns() - t_eq) / 1e6);
		(void)timeout; // TODO(bc5): honour the timespec
		return r == 0 ? out : -1;
	}
	return 0;
}

static KYTY_SYSV_ABI int MapNamedSystemFlexibleMemory(void** addr_in_out, size_t len, int prot,
                                                       int flags, const char* name) {
	PRINT_NAME();
	void* want = addr_in_out != nullptr ? *addr_in_out : nullptr;
	int   r    = Mem::KernelMapNamedFlexibleMemory(addr_in_out, len, prot, flags, name);
	if (r != 0 && (static_cast<uint32_t>(flags) & Bc5Gc::GUEST_MAP_FIXED) != 0) {
		LOGF_COLOR(Log::Color::Yellow,
		           "[bc5-gc] fixed system flexible mapping at %p failed (%d), retrying anywhere\n",
		           want, r);
		*addr_in_out = nullptr;
		r = Mem::KernelMapNamedFlexibleMemory(
		    addr_in_out, len, prot, flags & ~static_cast<int>(Bc5Gc::GUEST_MAP_FIXED), name);
	}
	LOGF("[bc5-gc] system flexible %s: want %p got %p len 0x%zx -> %d\n", name, want,
	     addr_in_out != nullptr ? *addr_in_out : nullptr, len, r);
	return r;
}

static KYTY_SYSV_ABI int ReleaseFlexibleMemory(void* addr, size_t len) {
	PRINT_NAME();
	return Mem::KernelMunmap(reinterpret_cast<uint64_t>(addr), len);
}

// Tool memory: on the console a separate pool for tooling (capture, debug). The call sites in
// libSceAgc use AllocateDirectMemory's argument list with a leading kind, and MapDirectMemory's
// list for the mapping, so the pool is simply direct memory here.
static KYTY_SYSV_ABI int AllocateToolMemory(int kind, int64_t search_start, int64_t search_end,
                                            size_t len, size_t alignment, int memory_type,
                                            int64_t* phys_out) {
	PRINT_NAME();
	LOGF("[bc5-gc] tool alloc kind %d start 0x%" PRIx64 " end 0x%" PRIx64 " len 0x%zx align 0x%zx type %d\n",
	     kind, search_start, search_end, len, alignment, memory_type);
	if (search_end == 0) {
		return Mem::KernelAllocateMainDirectMemory(len, alignment, memory_type, phys_out);
	}
	return Mem::KernelAllocateDirectMemory(search_start, search_end, len, alignment, memory_type,
	                                       phys_out);
}

static KYTY_SYSV_ABI int MapToolMemory(void** addr, size_t len, int prot, int flags, int64_t phys,
                                       size_t alignment) {
	PRINT_NAME();
	void* want = addr != nullptr ? *addr : nullptr;
	int   r    = Mem::KernelMapDirectMemory(addr, len, prot, flags, phys, alignment);
	if (r != 0 && (static_cast<uint32_t>(flags) & Bc5Gc::GUEST_MAP_FIXED) != 0) {
		LOGF_COLOR(Log::Color::Yellow, "[bc5-gc] fixed tool mapping at %p failed (%d), retrying anywhere\n",
		           want, r);
		*addr = nullptr;
		r = Mem::KernelMapDirectMemory(addr, len, prot,
		                               flags & ~static_cast<int>(Bc5Gc::GUEST_MAP_FIXED), phys,
		                               alignment);
	}
	LOGF("[bc5-gc] tool map: want %p got %p len 0x%zx -> %d\n", want,
	     addr != nullptr ? *addr : nullptr, len, r);
	return r;
}

static KYTY_SYSV_ABI int ReleaseToolMemory(int64_t phys, size_t len) {
	PRINT_NAME();
	return Mem::KernelReleaseDirectMemory(phys, len);
}

static KYTY_SYSV_ABI int AvailableToolMemorySize(int kind, int64_t search_start,
                                                 int64_t search_end, size_t alignment,
                                                 int64_t* phys_out, size_t* size_out) {
	PRINT_NAME();
	(void)kind;
	return Mem::KernelAvailableDirectMemorySize(search_start, search_end, alignment, phys_out,
	                                            size_out);
}

static KYTY_SYSV_ABI int GetMainSocId() {
	PRINT_NAME();
	return 0; // TODO(bc5): value unknown; the driver stores it and compares later
}

static KYTY_SYSV_ABI int GetAppInfo(int pid, void* info) {
	PRINT_NAME();
	LOGF("[bc5-gc] GetAppInfo pid %d\n", pid);
	if (info != nullptr) {
		// The libSceAgcDriver caller keeps the struct at rbp-0xc8 and its stack canary at
		// rbp-0x30, so the struct is at most 0x98 bytes; it reads a byte at offset 0x48.
		std::memset(info, 0, 0x98);
	}
	return 0;
}

static KYTY_SYSV_ABI int GetCompiledSdkVersion(int* version) {
	PRINT_NAME();
	if (version == nullptr) {
		return LibKernel::KERNEL_ERROR_EINVAL;
	}
	// Experiment 0336 (exp 0335's audit): the version comes from the program's process parameter, which the host serves
	// (RuntimeLinker::GetProcParam). TODO(verify): the layout. A PS4 process parameter is {u64 size, u32 magic, u32 entry
	// count, u64 sdk version}; a PS5 title's param.json writes sdkVersion as a u64 with the version in its high half
	// ("0x0700000000000000", ps5rs crates/ps5-analysis/src/param_json.rs). So the high half of the u64 at +0x10 is taken,
	// or its low half when the high one is 0, and only a value in [0x01000000, 0x20000000) is used; otherwise the old
	// constant 0x0A000000. The second title gives 0x09000040.
	static const uint32_t v = [] {
		uint32_t       out = 0x0A000000;
		const uint64_t pp  = Loader::Bc5ProcParam();
		uint64_t       size = 0, sdk = 0;
		if (pp != 0) {
			std::memcpy(&size, reinterpret_cast<const void*>(pp), 8);
			if (size >= 0x18) std::memcpy(&sdk, reinterpret_cast<const void*>(pp + 0x10), 8);
		}
		const auto hi   = static_cast<uint32_t>(sdk >> 32u);
		const auto lo   = static_cast<uint32_t>(sdk);
		const auto cand = hi != 0 ? hi : lo;
		if (cand >= 0x01000000u && cand < 0x20000000u) out = cand;
		return out;
	}();
	*version = static_cast<int>(v);
	return 0;
}

static KYTY_SYSV_ABI int IsNeoMode() {
	PRINT_NAME();
	return 0;
}

static KYTY_SYSV_ABI int SetProcessProperty(const char* name, uint64_t a1, uint64_t a2,
                                            uint64_t a3, uint64_t a4) {
	PRINT_NAME();
	LOGF("[bc5-gc] SetProcessProperty %s 0x%" PRIx64 " 0x%" PRIx64 " 0x%" PRIx64 " 0x%" PRIx64 "\n",
	     name != nullptr ? name : "(null)", a1, a2, a3, a4);
	return 0;
}

static KYTY_SYSV_ABI int Getuid() {
	PRINT_NAME();
	return 0;
}

static KYTY_SYSV_ABI int KernelError(int e) {
	PRINT_NAME();
	if (e <= 0) {
		return e;
	}
	return static_cast<int>(0x80020000u + static_cast<uint32_t>(e));
}

static KYTY_SYSV_ABI int TitleWorkaroundIsEnabled(int id) {
	PRINT_NAME();
	LOGF("[bc5-gc] TitleWorkaroundIsEnabled %d -> 0\n", id);
	return 0;
}

static KYTY_SYSV_ABI int GetAppCategoryType() {
	PRINT_NAME();
	return 0;
}

static KYTY_SYSV_ABI const char* GetFsSandboxRandomWord() {
	PRINT_NAME();
	return "bc5bc5bc5b";
}

static KYTY_SYSV_ABI int AddTimerEvent(EQ::KernelEqueue eq, int id, const void* ts, void* udata) {
	PRINT_NAME();
	if ((EQ::Bc5EqueueFixes0405() & BC5_EQ_FIX_KK01_0405) != 0) {
		// exp 0401 series e5 (eq0405, KYTY_BC5_EQUEUE_FIXES kk01; exp 0405 R2 KK01, F246): the third argument is the period
		// in microseconds, a 32-bit SceKernelUseconds passed by value (KytyPS5 dfec14a kernel/eventQueue.cpp:537-539, AnyPS5
		// 4f41f4c37 Equeue.cpp:829; the upper half of the register is not part of it); a periodic EVFILT_TIMER.
		return EQ::Bc5KernelAddTimerEvent0405(
		    eq, id, static_cast<LibKernel::KernelUseconds>(reinterpret_cast<uintptr_t>(ts)), udata);
	}
	return EQ::KernelAddHRTimerEvent(eq, id, static_cast<const LibKernel::KernelTimespec*>(ts),
	                                 udata);
}

struct SystemSwVersion {
	uint64_t size;
	char     version_string[28];
	uint32_t version;
};

static KYTY_SYSV_ABI int GetProsperoSystemSwVersion(SystemSwVersion* v) {
	PRINT_NAME();
	if (v == nullptr) {
		return LibKernel::KERNEL_ERROR_EINVAL;
	}
	std::memset(v->version_string, 0, sizeof(v->version_string));
	std::strncpy(v->version_string, "10.60.000", sizeof(v->version_string) - 1);
	v->version = 0x0A600000;
	return 0;
}

// PS5-only NIDs without a public name. Logged, answered with 0.
static KYTY_SYSV_ABI int Unknown_LzoM(int a) {
	PRINT_NAME();
	LOGF("[bc5-gc] libkernel LzoM-wVLJDE(%d) -> 0 (first call of libSceAgcDriver init)\n", a);
	return 0;
}
static KYTY_SYSV_ABI int Unknown_dkBx(uint64_t a, uint64_t b) {
	PRINT_NAME();
	LOGF("[bc5-gc] libkernel dkBx0YqFQ+Y(0x%" PRIx64 ", 0x%" PRIx64 ") -> 0\n", a, b);
	return 0;
}
static KYTY_SYSV_ABI int Unknown_GGeR(uint64_t a, uint64_t b) {
	PRINT_NAME();
	LOGF("[bc5-gc] libkernel GGeRJk1XdWc(0x%" PRIx64 ", 0x%" PRIx64 ") -> 0\n", a, b);
	return 0;
}

LIB_DEFINE(InitBc5LleKernel_1) {
	LIB_FUNC("PfccT7qURYE", Ioctl);
	LIB_FUNC("wW+k21cmbwQ", Ioctl); // _ioctl
	LIB_FUNC("BPE9s9vQQXo", Mmap);
	LIB_FUNC("RW-GEfpnsqg", Kevent);
	LIB_FUNC("kc+LEEIYakc", MapNamedSystemFlexibleMemory);
	LIB_FUNC("teiItL2boFw", ReleaseFlexibleMemory);
	LIB_FUNC("45Yurf7lZmU", AllocateToolMemory);
	LIB_FUNC("d0vezuPZxtg", MapToolMemory);
	LIB_FUNC("gO98NioN5FM", ReleaseToolMemory);
	LIB_FUNC("YkwlupG-S4E", AvailableToolMemorySize);
	LIB_FUNC("0vTn5IDMU9A", GetMainSocId);
	LIB_FUNC("G-MYv5erXaU", GetAppInfo);
	LIB_FUNC("WB66evu8bsU", GetCompiledSdkVersion);
	LIB_FUNC("WslcK1FQcGI", IsNeoMode);
	LIB_FUNC("-W4xI5aVI8w", SetProcessProperty);
	LIB_FUNC("kg4x8Prhfxw", Getuid);
	LIB_FUNC("D4yla3vx4tY", KernelError);
	LIB_FUNC("1yca4VvfcNA", TitleWorkaroundIsEnabled);
	LIB_FUNC("+xy9ORMbd8U", GetAppCategoryType);
	LIB_FUNC("JGfTMBOdUJo", GetFsSandboxRandomWord);
	LIB_FUNC("57ZK+ODEXWY", AddTimerEvent);
	if ((EQ::Bc5EqueueFixes0405() & BC5_EQ_FIX_KK01_0405) != 0) { // exp 0401 series e5 (eq0405) kk01
		LIB_FUNC("YWQFUyXIVdU", Bc5DeleteTimerEvent0405); // sceKernelDeleteTimerEvent
	}
	LIB_FUNC("aML18Z0J0t0", GetProsperoSystemSwVersion);
	LIB_FUNC("LzoM-wVLJDE", Unknown_LzoM);
	LIB_FUNC("dkBx0YqFQ+Y", Unknown_dkBx);
	LIB_FUNC("GGeRJk1XdWc", Unknown_GGeR);
}

} // namespace Bc5LleKernel

// ---------------------------------------------------------------------------------------------
// VideoOut
// ---------------------------------------------------------------------------------------------
namespace Bc5LleVideoOut {

LIB_VERSION("VideoOut", 1, "VideoOut", 1, 1);

static KYTY_SYSV_ABI int SysGetBus(int handle) {
	PRINT_NAME();
	static int logged = 0;
	if (Bc5Gc::gc_log_few(&logged)) {
		LOGF("[bc5-gc] VideoOutSysGetBus(%d) -> 0\n", handle);
	}
	return 0;
}

// The GPU writes flip labels here (EOP flips); the driver reads them back to know a flip landed.
static KYTY_SYSV_ABI int GetBufferLabelAddress(int handle, uint64_t** out) {
	PRINT_NAME();
	if (out == nullptr) {
		return LibKernel::KERNEL_ERROR_EINVAL;
	}
	*out = Bc5Gc::g_labels;
	static int logged = 0;
	if (Bc5Gc::gc_log_few(&logged)) {
		LOGF("[bc5-gc] VideoOutGetBufferLabelAddress(%d) -> %p\n", handle, static_cast<void*>(*out));
	}
	return 0;
}

// (handle, index, flip_mode, flip_arg, ...): treated as a CPU flip for now.
// TODO(bc5): the EOP part (flip when the GPU reaches the end of the submitted DCB).
static KYTY_SYSV_ABI int SubmitEopFlip(int handle, int index, int flip_mode, int64_t flip_arg,
                                       void* unk) {
	PRINT_NAME();
	static int flip_logged = 0;
	if (Bc5Gc::gc_log_few(&flip_logged)) {
		LOGF("[bc5-gc] VideoOutSubmitEopFlip(%d, %d, %d, 0x%" PRIx64 ", %p)\n", handle, index,
		     flip_mode, flip_arg, unk);
	}
	// Experiment 0025: BC5_DIRECT_FLIP_DEFER=1 — with jobs in flight the flip is not waited for
	// here. It is queued behind the frame's jobs and submitted by the completion thread once the
	// GPU has finished them, the buffer's label reset with it; the game's thread goes on with the
	// next frame instead of idling at the flip, and the GPU does not idle while it does (run 117:
	// the wait at the flip is where the two wait for each other).
	static const bool defer = bc5::env_on(std::getenv("BC5_DIRECT_FLIP_DEFER")) && Bc5Gc::Direct::async_on(); // exp 0419: "=0" is off
	const double   t_drain   = Bc5Gc::Direct::timing_now();
	const uint64_t fs_called = bc5::load_stat::now_ns(); // experiment 0415 (fs415b): the title called the flip
	if (!defer) Bc5Gc::Direct::drain(); // nothing of the frame may still be in flight
	Bc5Gc::Direct::frame_profile_flip((Bc5Gc::Direct::timing_now() - t_drain) * 1e3);
	bc5::load_stat::flip(Bc5Gc::Direct::timing_now()); // experiment 0415 (ls415)
	Bc5Gc::Direct::fs415_flip(fs_called);              // experiment 0415 (fs415, fs415b)
	if (defer) {
		if (index >= 0 && index < 64) {
			Bc5Gc::g_flip_pending[index]++; // experiment 0069
		}
		Bc5Gc::Direct::post([handle, index, flip_mode, flip_arg](bool) {
			VideoOut::VideoOutSubmitFlip(handle, index, flip_mode, flip_arg);
			if (index >= 0 && index < 64) {
				// Experiment 0069: the flip only queues the request; the buffer is read by the
				// presentation thread later, at the display's refresh. Experiment 0070: the label is
				// cleared (and the next frame may render into the buffer) once the flip has been
				// copied into the presenter's own frame (KytyPlus FlipQueue::Prepare records the copy,
				// Complete marks it done), which is what the console's flip guarantees for the
				// buffer; the presentation at the refresh shows the copy. A thread of its own waits,
				// so that the completion thread goes on with the jobs. (Waiting for the flip to be
				// shown instead gave 30 fps in the later level, run 303.)
				static std::mutex                           m;
				static std::condition_variable              cv;
				static std::deque<std::pair<int, int>>      q;
				static std::once_flag                       started;
				std::call_once(started, [] {
					std::thread([] {
						pthread_setname_np(pthread_self(), "bc5-flipdone");
						for (;;) {
							std::pair<int, int> it;
							{
								std::unique_lock lk(m);
								cv.wait(lk, [] { return !q.empty(); });
								it = q.front();
								q.pop_front();
							}
							VideoOut::Bc5VideoOutWaitFlipCopied(it.first, it.second);
							Bc5Gc::g_labels[it.second] = 0;
							Bc5Gc::g_flip_pending[it.second]--;
						}
					}).detach();
				});
				{
					std::lock_guard lk(m);
					q.emplace_back(handle, index);
				}
				cv.notify_one();
			}
		});
		return 0;
	}
	Bc5Gc::Direct::ApplyPendingRayTracing(); // experiment 0273: the switch takes effect at a frame boundary
	const double flip_t0 = Bc5Gc::Direct::timing_now();
	const int rc = VideoOut::VideoOutSubmitFlip(handle, index, flip_mode, flip_arg);
	static const bool timing_flips_env = BC5_DIAG_ENV("BC5_DIRECT_TIMING") != nullptr;
	const bool timing_flips = timing_flips_env && ::Log::Bc5LoggingOn();
	if (timing_flips) {
		Bc5Gc::Direct::journal("timing: t %.3f s flip %d/%d, VideoOutSubmitFlip took %.1f ms\n", flip_t0, handle, index, (Bc5Gc::Direct::timing_now() - flip_t0) * 1e3);
	}
	// Experiment 0162: the buffer's flip label goes back to 0 when the flip has been presented, at
	// the vblank it was due by the flip rate (VideoOutSetFlipRate), as the console's VideoOut does
	// (the game waits for the label before it renders into the buffer again; run 73). Resetting it
	// here, at submission, let the second title run its frames at whatever the GPU allowed (22-31
	// ms instead of the 33.3 ms of its 30 Hz flip rate), and its cutscenes and gameplay sped up and
	// slowed down with the frame time (the maintainer, runs 793-795). A thread of its own waits for
	// the presentation, so the game's thread is not held here.
	if (index >= 0 && index < 64) {
		if (rc != 0) {
			Bc5Gc::g_labels[index] = 0;
		} else {
			static std::mutex                      lm;
			static std::condition_variable         lcv;
			static std::deque<std::pair<int, int>> lq;
			static std::once_flag                  lstarted;
			std::call_once(lstarted, [] {
				std::thread([] {
					pthread_setname_np(pthread_self(), "bc5-fliplabel");
					for (;;) {
						std::pair<int, int> it;
						{
							std::unique_lock lk(lm);
							lcv.wait(lk, [] { return !lq.empty(); });
							it = lq.front();
							lq.pop_front();
						}
						VideoOut::Bc5VideoOutWaitFlipDone(it.first, it.second);
						Bc5Gc::g_labels[it.second] = 0;
					}
				}).detach();
			});
			{
				std::lock_guard lk(lm);
				lq.emplace_back(handle, index);
			}
			lcv.notify_one();
		}
	}
	return rc;
}

static KYTY_SYSV_ABI int SysAddSetModeEvent2(uint64_t a, uint64_t b, uint64_t c) {
	PRINT_NAME();
	LOGF("[bc5-gc] VideoOutSysAddSetModeEvent2(0x%" PRIx64 ", 0x%" PRIx64 ", 0x%" PRIx64 ") -> 0\n", a,
	     b, c);
	return 0;
}

static KYTY_SYSV_ABI int Unknown_Ygv0(uint64_t a, uint64_t b, uint64_t c) {
	PRINT_NAME();
	LOGF("[bc5-gc] VideoOut Ygv0S+Hi+hA(0x%" PRIx64 ", 0x%" PRIx64 ", 0x%" PRIx64 ") -> 0\n", a, b, c);
	return 0;
}

LIB_DEFINE(InitBc5LleVideoOut_1) {
	LIB_FUNC("7VSZJxxcTL8", SysGetBus);
	LIB_FUNC("OcQybQejHEY", GetBufferLabelAddress);
	LIB_FUNC("j8xl+92A0q4", SubmitEopFlip);
	LIB_FUNC("fYWVVDKZOCk", SysAddSetModeEvent2);
	LIB_FUNC("Ygv0S+Hi+hA", Unknown_Ygv0);
}

} // namespace Bc5LleVideoOut

// ---------------------------------------------------------------------------------------------
// Sysmodule, RegMgr
// ---------------------------------------------------------------------------------------------
namespace Bc5LleSysmodule {

LIB_VERSION("Sysmodule", 1, "Sysmodule", 1, 1);

static KYTY_SYSV_ABI int LoadModuleInternal(uint16_t id) {
	PRINT_NAME();
	LOGF("[bc5-gc] SysmoduleLoadModuleInternal(0x%x) -> 0\n", id);
	return 0;
}

static KYTY_SYSV_ABI int LoadModuleByNameInternal(const char* name, uint64_t a, uint64_t b) {
	PRINT_NAME();
	LOGF("[bc5-gc] SysmoduleLoadModuleByNameInternal(%s, 0x%" PRIx64 ", 0x%" PRIx64 ") -> 0\n",
	     name != nullptr ? name : "(null)", a, b);
	return 0;
}

LIB_DEFINE(InitBc5LleSysmodule_1) {
	LIB_FUNC("39iV5E1HoCk", LoadModuleInternal);
	LIB_FUNC("CU8m+Qs+HN4", LoadModuleByNameInternal);
}

} // namespace Bc5LleSysmodule

namespace Bc5LleRegMgr {

LIB_VERSION("RegMgr", 1, "RegMgr", 1, 1);

static KYTY_SYSV_ABI int NonSysGetInt(uint32_t key, int* value) {
	PRINT_NAME();
	LOGF("[bc5-gc] RegMgrNonSysGetInt(0x%08x) -> 0\n", key);
	if (value != nullptr) {
		*value = 0;
	}
	return 0;
}

LIB_DEFINE(InitBc5LleRegMgr_1) {
	LIB_FUNC("dKeshzt29G4", NonSysGetInt);
}

} // namespace Bc5LleRegMgr

namespace Bc5Gc::Direct {
// Experiment 0047: what the F2 menu's Video tab sets and shows.
void SetTimestampScale(double k) {
#if defined(KYTY_BC5_DIRECT)
	g_ts_scale.store(k > 0.0 ? k : 1.0, std::memory_order_relaxed);
#else
	(void)k;
#endif
}
double GetTimestampScale() {
#if defined(KYTY_BC5_DIRECT)
	return ts_scale();
#else
	return 1.0;
#endif
}
bool GetMainPass(uint32_t* w, uint32_t* h) {
#if defined(KYTY_BC5_DIRECT)
	*w = g_main_w.load(std::memory_order_relaxed);
	*h = g_main_h.load(std::memory_order_relaxed);
	return *w != 0;
#else
	*w = *h = 0;
	return false;
#endif
}
} // namespace Bc5Gc::Direct

LIB_DEFINE(InitBc5LleAgc_1) {
	Bc5LleKernel::InitBc5LleKernel_1(s);
	Bc5LleVideoOut::InitBc5LleVideoOut_1(s);
	Bc5LleSysmodule::InitBc5LleSysmodule_1(s);
	Bc5LleRegMgr::InitBc5LleRegMgr_1(s);
}

} // namespace Libs
