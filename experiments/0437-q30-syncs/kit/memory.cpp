#include "bc5/env_rule.hpp" // exp 0419 (build W): BC5_DIAG_ENV, BC5_FIXED_ENV, BC5_LEAN_OR
#include "bc5/ports_pack1.hpp" // ports pack 1: C
#include <set>
#include <cinttypes>
#include <cstdio>
#include "kernel/memory.h"

#include "common/assert.h"
#include "common/logging/log.h"
#include "common/magicEnum.h"
#include "common/stringUtils.h"
#include "common/threads.h"
#include "common/virtualMemory.h"
#include "graphics/guest_gpu/graphicsRun.h"
#include "graphics/host_gpu/renderer/cache/gpuResourceManager.h"
#include "libs/errno.h"
#include "libs/libs.h"
#include "loader/systemContent.h" // experiment 0401 series e

#include <algorithm>
#include <array>
#include <atomic>
#include <cstddef>
#include <cstdlib>
#include <cstring>
#include <map>
#include <memory>
#include <mutex>
#include <vector>
#include <thread>
#include <cerrno> // experiment 0329: mlock
#if KYTY_PLATFORM == KYTY_PLATFORM_LINUX
#include <sys/mman.h> // experiment 0329: mlock
#endif

#if KYTY_PLATFORM == KYTY_PLATFORM_WINDOWS
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h> // IWYU pragma: keep
#ifndef MEM_RESERVE_PLACEHOLDER
#define MEM_RESERVE_PLACEHOLDER 0x00040000
#endif
#ifndef MEM_REPLACE_PLACEHOLDER
#define MEM_REPLACE_PLACEHOLDER 0x00004000
#endif
#ifndef MEM_PRESERVE_PLACEHOLDER
#define MEM_PRESERVE_PLACEHOLDER 0x00000002
#endif
#ifndef MEM_COALESCE_PLACEHOLDERS
#define MEM_COALESCE_PLACEHOLDERS 0x00000001
#endif
#elif KYTY_PLATFORM == KYTY_PLATFORM_LINUX
#include <cerrno>
#include <fcntl.h>
#include <sys/mman.h>
#include <sys/syscall.h>
#include <unistd.h>
#include "bc5/load_stat.hpp" // experiment 0415 (ls415)
#include "bc5/map_records.hpp" // experiment 0415 (mr415c, stage S2)
#endif

namespace Libs::LibKernel::Memory {

namespace VirtualMemory = Common::VirtualMemory;

LIB_NAME("libkernel", "libkernel");

constexpr int PROT_CPU_READ  = 0x01;
constexpr int PROT_CPU_WRITE = 0x02;
constexpr int PROT_CPU_EXEC  = 0x04;
constexpr int PROT_GPU_READ  = 0x10;
constexpr int PROT_GPU_WRITE = 0x20;

enum class GpuAccessMode { NoAccess, Read, Write, ReadWrite };

constexpr uint64_t PAGE_TABLE_POOL_SIZE   = 4ull * 1024ull * 1024ull * 1024ull;
constexpr uint64_t PAGE_TABLE_GRANULARITY = 2ull * 1024ull * 1024ull;
constexpr int      PAGE_TABLE_POOL_ENTRIES =
    static_cast<int>(PAGE_TABLE_POOL_SIZE / PAGE_TABLE_GRANULARITY);
constexpr uint64_t DEFAULT_FLEXIBLE_MEMORY_SIZE = 1ull * 1024ull * 1024ull * 1024ull;

static uint64_t                      g_flexible_memory_size        = DEFAULT_FLEXIBLE_MEMORY_SIZE;
static bool                          g_flexible_memory_size_frozen = false;
static Graphics::GpuResourceManager* g_gpu_resources               = nullptr;

// ---- Experiment 0405 series e5 (mkmem0405.py): exp 0405's R3 memory ports ------------------------------------------
// One switch per item, R3's names (exp 0405 raw/r3-gpu-memory.md, "e4-now port specs"), read once from the
// environment: on when set, not empty and not "0" (F767's reading); unset or "0" keeps today's code path. One stderr
// line at memory init lists the items that are on. Each change cites its sources where it is made.
//   BC5_R3_MPROTECT_GAPS (M1)  sceKernelMprotect/sceKernelMtypeprotect change the mapped parts of a range, skip its gaps
//                              and return 0, also for a range that starts in a gap or is wholly unmapped (today: EXIT);
//                              an overflowing range returns EINVAL (today: EXIT); the batch-map protect operations
//                              return EINVAL for an unmapped start.
//   BC5_R3_NULL_ARGS (M21)     sceKernelQueryMemoryProtection(NULL) returns EACCES and sceKernelMapNamedFlexibleMemory
//                              with a NULL addr_in_out returns EINVAL (today: EXIT for both).
//   BC5_R3_RELEASE_HOLES (M3)  an unchecked sceKernelReleaseDirectMemory over free gaps releases the allocated runs and
//                              skips the gaps (today: it frees nothing; it returns OK either way).
//   BC5_R3_MUNMAP_HOLES (M7)   sceKernelMunmap over holes unmaps the mapped runs and returns 0; a range with nothing
//                              mapped returns 0 (today: EACCES for both).
//   BC5_R3_FLEX_HINT (M6)      a flexible map without MAP_FIXED whose hint range lies wholly in reserved ranges is placed
//                              at the hint, as direct maps already are (today: placed after the reservation).
//   BC5_R3_DMQ_END (M20)       sceKernelDirectMemoryQuery find-next past the last block returns EACCES (today: OK with a
//                              terminal record at the end of direct memory).
//   BC5_R3_EXEC_EINVAL (M26)   sceKernelMapDirectMemory with CPU execute returns EINVAL (today: EACCES).
//   BC5_R3_QUERY_SIZE (M30)    sceKernelVirtualQuery and sceKernelDirectMemoryQuery accept an info size larger than
//                              their struct and write the struct only (today: EINVAL unless the size is equal).
// Not here: M16, M17, M22-M25, M32 (registrations in libKernel.cpp), M18 (the system flexible map is in
// bc5LleAgc.cpp), M28 (param.json sizing).
enum Bc5R3Item : unsigned {
	BC5_R3_ITEM_MPROTECT_GAPS,
	BC5_R3_ITEM_NULL_ARGS,
	BC5_R3_ITEM_RELEASE_HOLES,
	BC5_R3_ITEM_MUNMAP_HOLES,
	BC5_R3_ITEM_FLEX_HINT,
	BC5_R3_ITEM_DMQ_END,
	BC5_R3_ITEM_EXEC_EINVAL,
	BC5_R3_ITEM_QUERY_SIZE,
	BC5_R3_ITEM_COUNT,
};
static constexpr const char* BC5_R3_SWITCH_NAMES[BC5_R3_ITEM_COUNT] = {
    "BC5_R3_MPROTECT_GAPS", "BC5_R3_NULL_ARGS", "BC5_R3_RELEASE_HOLES", "BC5_R3_MUNMAP_HOLES",
    "BC5_R3_FLEX_HINT",     "BC5_R3_DMQ_END",   "BC5_R3_EXEC_EINVAL",   "BC5_R3_QUERY_SIZE",
};

static bool Bc5R3On(Bc5R3Item item) {
	static const std::array<bool, BC5_R3_ITEM_COUNT> on = [] {
		std::array<bool, BC5_R3_ITEM_COUNT> v {};
		for (unsigned i = 0; i < BC5_R3_ITEM_COUNT; i++) {
			const char* e = std::getenv(BC5_R3_SWITCH_NAMES[i]);
			v[i]          = e != nullptr && e[0] != 0 && std::strcmp(e, "0") != 0;
		}
		return v;
	}();
	return on[item];
}

// The one journal line, at memory init: "[bc5] exp 0405: mem off" or "[bc5] exp 0405: mem on (items: A,B)".
static void Bc5R3Journal() {
	char   items[512] = {};
	size_t used       = 0;
	for (unsigned i = 0; i < BC5_R3_ITEM_COUNT; i++) {
		if (Bc5R3On(static_cast<Bc5R3Item>(i)) && used < sizeof(items)) {
			const int n = std::snprintf(items + used, sizeof(items) - used, "%s%s", used == 0 ? "" : ",", BC5_R3_SWITCH_NAMES[i]);
			used += (n > 0 ? static_cast<size_t>(n) : 0);
		}
	}
	if (used == 0) {
		std::fprintf(stderr, "[bc5] exp 0405: mem off\n");
	} else {
		std::fprintf(stderr, "[bc5] exp 0405: mem on (items: %s)\n", items);
	}
}

static Graphics::GpuResourceManager& GetGpuResources() {
	EXIT_IF(g_gpu_resources == nullptr);
	return *g_gpu_resources;
}

static bool IsGpuAddressRange(uint64_t vaddr, uint64_t size) {
	constexpr uint64_t GPU_ADDRESS_LIMIT = 1ull << 40u;
	return vaddr != 0 && size != 0 && vaddr < GPU_ADDRESS_LIMIT && size < GPU_ADDRESS_LIMIT - vaddr;
}

static void MapGpuRange(uint64_t vaddr, uint64_t size) {
	if (g_gpu_resources == nullptr || !IsGpuAddressRange(vaddr, size)) {
		return;
	}
	GetGpuResources().MapMemory(vaddr, size);
}

static void UnmapGpuRange(uint64_t vaddr, uint64_t size) {
	if (g_gpu_resources == nullptr || !IsGpuAddressRange(vaddr, size)) {
		return;
	}
	GetGpuResources().UnmapMemory(vaddr, size);
}

static bool DecodeMemoryProtection(int prot, VirtualMemory::Mode* mode, GpuAccessMode* gpu_mode) {
	EXIT_IF(mode == nullptr);
	EXIT_IF(gpu_mode == nullptr);

	bool cpu_read  = (prot & PROT_CPU_READ) != 0;
	bool cpu_write = (prot & PROT_CPU_WRITE) != 0;
	bool cpu_exec  = (prot & PROT_CPU_EXEC) != 0;
	bool gpu_read  = (prot & PROT_GPU_READ) != 0;
	bool gpu_write = (prot & PROT_GPU_WRITE) != 0;

	if ((prot &
	     (PROT_CPU_READ | PROT_CPU_WRITE | PROT_CPU_EXEC | PROT_GPU_READ | PROT_GPU_WRITE)) == 0 &&
	    prot != 0) {
		return false;
	}

	if (gpu_read && gpu_write) {
		*gpu_mode = GpuAccessMode::ReadWrite;
	} else if (gpu_read) {
		*gpu_mode = GpuAccessMode::Read;
	} else if (gpu_write) {
		*gpu_mode = GpuAccessMode::Write;
	} else {
		*gpu_mode = GpuAccessMode::NoAccess;
	}

	bool host_read  = cpu_read || gpu_read;
	bool host_write = cpu_write || gpu_write;

	if (host_write) {
		host_read = true;
	}

	*mode = VirtualMemory::Mode::NoAccess;
	if (cpu_exec) {
		*mode = (host_write ? VirtualMemory::Mode::ExecuteReadWrite
		                    : (host_read ? VirtualMemory::Mode::ExecuteRead
		                                 : VirtualMemory::Mode::Execute));
	} else if (host_write) {
		*mode = VirtualMemory::Mode::ReadWrite;
	} else if (host_read) {
		*mode = VirtualMemory::Mode::Read;
	}

	return true;
}

static void CopyVirtualRangeName(char* dst, const char* name) {
	EXIT_IF(dst == nullptr);

	std::memset(dst, 0, KERNEL_MAXIMUM_NAME_LENGTH);

	if (name != nullptr) {
		std::strncpy(dst, name, KERNEL_MAXIMUM_NAME_LENGTH - 1);
	}
}

static bool VirtualRangesOverlap(uint64_t left_start, uint64_t left_size, uint64_t right_start,
                                 uint64_t right_size) {
	if (left_size == 0 || right_size == 0) {
		return false;
	}

	auto left_end = (UINT64_MAX - left_start < left_size ? UINT64_MAX : left_start + left_size);
	auto right_end =
	    (UINT64_MAX - right_start < right_size ? UINT64_MAX : right_start + right_size);

	return left_start < right_end && right_start < left_end;
}

#if defined(KYTY_VIRTUAL_MEMORY_ALLOCATION_TESTS)
static uint32_t g_test_backing_store_unmaps_before_failure = UINT32_MAX;
#endif

#include "memoryAddressSpace.inc"

enum class VirtualRangeType {
	Reserved,
	PoolReserved,
	Direct,
	Flexible,
	Pooled,
	Stack,
	Code,
	Runtime,
};

static bool IsReservedRangeType(VirtualRangeType type) {
	return type == VirtualRangeType::Reserved || type == VirtualRangeType::PoolReserved;
}

static bool IsPooledRangeType(VirtualRangeType type) {
	return type == VirtualRangeType::Pooled || type == VirtualRangeType::PoolReserved;
}

static bool IsCommittedRangeType(VirtualRangeType type) {
	return !IsReservedRangeType(type);
}

static bool IsPrivateCommittedRangeType(VirtualRangeType type) {
	return type == VirtualRangeType::Stack || type == VirtualRangeType::Code ||
	       type == VirtualRangeType::Runtime;
}

class VirtualRanges {
public:
	// BC5 (experiment 0037): changes with every edit of the ranges, so readers can cache a snapshot.
	[[nodiscard]] uint64_t Generation() const { return m_gen.load(std::memory_order_acquire); }
	// BC5 (experiment 0437, tag vg437): changes only with an edit that changes a direct range's start, size, offset or
	// name, the four things the direct view list is made of (bc5LleAgc.cpp, direct_views_build: type 0 only; the
	// protection and the memory type are not in it). An edit of a flexible, pooled, stack, code or reserved range, or a
	// protection change that leaves a direct range whole, leaves it as it is.
	[[nodiscard]] uint64_t DirectGeneration() const { return m_gen_direct.load(std::memory_order_acquire); }
	// BC5 (experiment 0037): [start, end) of every range, reserved or mapped, that overlaps [lo, hi).
	void Overlapping(uint64_t lo, uint64_t hi, std::vector<std::pair<uint64_t, uint64_t>>* out) {
		Common::LockGuard lock(m_mutex);
		out->clear();
		auto it = std::upper_bound(m_ranges.begin(), m_ranges.end(), lo, [](uint64_t v, const Range& r) { return v < r.start; });
		if (it != m_ranges.begin()) --it;
		for (; it != m_ranges.end() && it->start < hi; ++it) {
			if (it->start + it->size > lo) out->emplace_back(it->start, it->start + it->size);
		}
	}

	struct Range {
		uint64_t         start          = 0;
		uint64_t         size           = 0;
		uint64_t         offset         = 0;
		int              protection     = 0;
		int              memory_type    = 0;
		VirtualRangeType type           = VirtualRangeType::Reserved;
		bool             disallow_merge = false;
		char             name[KERNEL_MAXIMUM_NAME_LENGTH];
	};

	// BC5 (experiment 0437, tag vg437): see DirectGeneration. Declared after the lock, so it is destroyed under it.
	struct DirectEditGuard {
		struct D {
			uint64_t start, size, offset;
			char     name[KERNEL_MAXIMUM_NAME_LENGTH];
			bool operator==(const D& o) const {
				return start == o.start && size == o.size && offset == o.offset && std::strncmp(name, o.name, KERNEL_MAXIMUM_NAME_LENGTH) == 0;
			}
		};
		VirtualRanges*  self;
		uint64_t        lo, hi;
		std::vector<D>  before;
		DirectEditGuard(VirtualRanges* s, uint64_t start, uint64_t size): self(s), lo(start), hi(End(start, size)) {
			if (hi < lo) hi = UINT64_MAX; // the span wraps: the whole table is the window
			auto [first, last] = self->OverlapWindowUnlocked(lo, hi - lo);
			if (first != last) {
				lo = std::min(lo, first->start);
				hi = std::max(hi, End(std::prev(last)->start, std::prev(last)->size));
			}
			self->DirectInUnlocked(lo, hi, &before);
		}
		~DirectEditGuard() {
			std::vector<D> after;
			self->DirectInUnlocked(lo, hi, &after);
			if (after != before) self->m_gen_direct.fetch_add(1, std::memory_order_acq_rel);
		}
		DirectEditGuard(const DirectEditGuard&)            = delete;
		DirectEditGuard& operator=(const DirectEditGuard&) = delete;
	};
	void DirectInUnlocked(uint64_t lo, uint64_t hi, std::vector<DirectEditGuard::D>* out) {
		out->clear();
		if (hi <= lo) return;
		auto [first, last] = OverlapWindowUnlocked(lo, hi - lo);
		for (auto it = first; it != last; ++it) {
			if (it->type != VirtualRangeType::Direct) continue;
			DirectEditGuard::D d {it->start, it->size, it->offset, {}};
			std::memcpy(d.name, it->name, KERNEL_MAXIMUM_NAME_LENGTH);
			out->push_back(d);
		}
	}

	bool Add(uint64_t start, uint64_t size, uint64_t offset, int protection, int memory_type,
	         VirtualRangeType type, const char* name, bool disallow_merge = false) {
		Common::LockGuard lock(m_mutex);
		m_gen.fetch_add(1, std::memory_order_acq_rel); // BC5 (experiment 0037)
		NoteDirtyUnlocked(start, size);                // BC5 (experiment 0415, mr415)
		DirectEditGuard vg437(this, start, size);      // BC5 (experiment 0437, tag vg437)

		if (start == 0 || size == 0) {
			return false;
		}
		auto position = LowerBound(start);
		if ((position != m_ranges.end() &&
		     VirtualRangesOverlap(start, size, position->start, position->size)) ||
		    (position != m_ranges.begin() &&
		     VirtualRangesOverlap(start, size, std::prev(position)->start,
		                          std::prev(position)->size))) {
			return false;
		}

		Range r {};
		r.start          = start;
		r.size           = size;
		r.offset         = offset;
		r.protection     = protection;
		r.memory_type    = memory_type;
		r.type           = type;
		r.disallow_merge = disallow_merge;
		CopyVirtualRangeName(r.name, name);
		const auto index = static_cast<size_t>(position - m_ranges.begin());
		m_ranges.insert(position, r);
		MergeAroundUnlocked(index);
		return true;
	}

	bool Remove(uint64_t start, uint64_t size) {
		Common::LockGuard lock(m_mutex);
		m_gen.fetch_add(1, std::memory_order_acq_rel); // BC5 (experiment 0037)
		NoteDirtyUnlocked(start, size);                // BC5 (experiment 0415, mr415)
		DirectEditGuard vg437(this, start, size);      // BC5 (experiment 0437, tag vg437)

		auto position = LowerBound(start);
		if (position != m_ranges.end() && position->start == start && position->size == size) {
			m_ranges.erase(position);
			return true;
		}
		return RemoveUnlocked(start, size); // BC5 (experiment 0167): a window-local edit, no sort
	}

	bool HasOverlap(uint64_t start, uint64_t size) {
		Common::LockGuard lock(m_mutex);

		return FindOverlap(start, size) != nullptr;
	}

	bool QueryOverlap(uint64_t start, uint64_t size, Range* out) {
		EXIT_IF(out == nullptr);
		Common::LockGuard lock(m_mutex);

		const auto* overlap = FindOverlap(start, size);
		if (overlap == nullptr) {
			return false;
		}
		*out = *overlap;
		return true;
	}

	bool ReleaseReserved(uint64_t start, uint64_t size) {
		Common::LockGuard lock(m_mutex);
		m_gen.fetch_add(1, std::memory_order_acq_rel); // BC5 (experiment 0037)
		NoteDirtyUnlocked(start, size);                // BC5 (experiment 0415, mr415)
		DirectEditGuard vg437(this, start, size);      // BC5 (experiment 0437, tag vg437)

		for (size_t index = 0; index < m_ranges.size(); index++) {
			auto& r = m_ranges[index];
			if (r.start == start && r.size == size && IsReservedRangeType(r.type)) {
				m_ranges.erase(m_ranges.begin() + static_cast<std::ptrdiff_t>(index));
				return true;
			}
		}
		return true;
	}

	bool ConsumeReserved(uint64_t start, uint64_t size,
	                     VirtualRangeType type = VirtualRangeType::Reserved) {
		Common::LockGuard lock(m_mutex);
		m_gen.fetch_add(1, std::memory_order_acq_rel); // BC5 (experiment 0037)
		NoteDirtyUnlocked(start, size);                // BC5 (experiment 0415, mr415)
		DirectEditGuard vg437(this, start, size);      // BC5 (experiment 0437, tag vg437)

		auto end = End(start, size);
		if (const Range* r = ContainingUnlocked(start); r != nullptr && r->type == type && end <= End(r->start, r->size)) {
			RemoveUnlocked(start, size); // BC5 (experiment 0167): a window-local edit, no sort
			return true;
		}

		return false;
	}

	bool ConsumeReservedSpan(uint64_t start, uint64_t size, Range* first_range = nullptr,
	                         VirtualRangeType type = VirtualRangeType::Reserved) {
		Common::LockGuard lock(m_mutex);
		m_gen.fetch_add(1, std::memory_order_acq_rel); // BC5 (experiment 0037)
		NoteDirtyUnlocked(start, size);                // BC5 (experiment 0415, mr415)
		DirectEditGuard vg437(this, start, size);      // BC5 (experiment 0437, tag vg437)

		if (size == 0) {
			return false;
		}

		auto current = start;
		auto end     = End(start, size);
		while (current < end) {
			const Range* candidate = ContainingUnlocked(current); // BC5 (experiment 0167): binary search
			if (candidate == nullptr || candidate->type != type) {
				return false;
			}
			if (current == start && first_range != nullptr) {
				*first_range = *candidate;
			}
			current = std::min(end, End(candidate->start, candidate->size));
		}

		RemoveUnlocked(start, size); // BC5 (experiment 0167): a window-local edit, no sort
		return true;
	}

	void Rename(uint64_t start, uint64_t size, const char* name) {
		Common::LockGuard lock(m_mutex);
		m_gen.fetch_add(1, std::memory_order_acq_rel); // BC5 (experiment 0037)
		NoteDirtyUnlocked(start, size);                // BC5 (experiment 0415, mr415)
		DirectEditGuard vg437(this, start, size);      // BC5 (experiment 0437, tag vg437)

		auto position = LowerBound(start);
		if (position != m_ranges.end() && position->start == start && position->size == size) {
			CopyVirtualRangeName(position->name, name);
			MergeAroundUnlocked(static_cast<size_t>(position - m_ranges.begin()));
			return;
		}
		EditUnlocked(start, size, [name](Range* r) { CopyVirtualRangeName(r->name, name); });
	}

	void Protect(uint64_t start, uint64_t size, int protection) {
		Common::LockGuard lock(m_mutex);
		m_gen.fetch_add(1, std::memory_order_acq_rel); // BC5 (experiment 0037)
		NoteDirtyUnlocked(start, size);                // BC5 (experiment 0415, mr415)
		DirectEditGuard vg437(this, start, size);      // BC5 (experiment 0437, tag vg437)

		EditUnlocked(start, size, [protection](Range* r) { r->protection = protection; });
	}

	void SetMemoryType(uint64_t start, uint64_t size, int memory_type) {
		Common::LockGuard lock(m_mutex);
		m_gen.fetch_add(1, std::memory_order_acq_rel); // BC5 (experiment 0037)
		NoteDirtyUnlocked(start, size);                // BC5 (experiment 0415, mr415)
		DirectEditGuard vg437(this, start, size);      // BC5 (experiment 0437, tag vg437)

		EditUnlocked(start, size, [memory_type](Range* r) { r->memory_type = memory_type; });
	}

	bool Query(uint64_t addr, int flags, Range* out) {
		EXIT_IF(out == nullptr);

		Common::LockGuard lock(m_mutex);

		auto next = std::upper_bound(
		    m_ranges.begin(), m_ranges.end(), addr,
		    [](uint64_t value, const Range& range) { return value < range.start; });
		if (next != m_ranges.begin()) {
			auto current = std::prev(next);
			if (addr < End(current->start, current->size)) {
				*out = *current;
				return true;
			}
		}
		if (flags != 1 || next == m_ranges.end()) {
			return false;
		}

		*out = *next;
		return true;
	}

	// BC5: copy of every range (the direct-mode host maps the game's ranges 1:1 into the GPU).
	void Snapshot(std::vector<Range>* out) {
		EXIT_IF(out == nullptr);
		Common::LockGuard lock(m_mutex);
		*out = m_ranges;
	}

	// BC5 (experiment 0415, tag mr415; stage S1 of experiments/0415-load-times-fps/DESIGN-lock-side.md): under ONE hold
	// of the mutex, the ranges as they are, their generation, and the spans the mutators were called with since the
	// last call (the log is emptied). The first call turns the log on, so its spans are not complete: *complete is
	// false then, and when the log was full. Every mutator above bumps the generation and notes its span in the same
	// critical section, so a reader never sees a change without its record.
	void SnapshotWithDirty(std::vector<Range>* out, uint64_t* gen, std::vector<std::pair<uint64_t, uint64_t>>* spans, bool* complete) {
		EXIT_IF(out == nullptr || gen == nullptr || spans == nullptr || complete == nullptr);
		Common::LockGuard lock(m_mutex);
		*out      = m_ranges;
		*gen      = m_gen.load(std::memory_order_acquire);
		*complete = m_dirty_on && !m_dirty_overflow;
		spans->clear();
		spans->swap(m_dirty);
		m_dirty_on       = true;
		m_dirty_overflow = false;
	}

	bool QuerySpan(uint64_t start, uint64_t size, std::vector<Range>* out) {
		EXIT_IF(out == nullptr);

		Common::LockGuard lock(m_mutex);
		out->clear();
		if (start == 0 || size == 0 || size > UINT64_MAX - start) {
			return false;
		}

		const auto end     = start + size;
		auto       current = start;
		// Experiment 0412 (tag mf412, mkmem0412.py): KYTY_BC5_RANGES_FAST=1 starts the walk at the range that holds `start`
		// instead of at the table's first element (28,000 ranges while the second title streams). The ranges are sorted
		// by start and do not overlap, so every range before that one ends at or before `start` and the loop below skipped it.
		static const bool fast412 = [] {
			const char* e  = BC5_FIXED_ENV("KYTY_BC5_RANGES_FAST", "1");
			const bool  on = e != nullptr && e[0] != 0 && !(e[0] == '0' && e[1] == 0);
			std::fprintf(stderr, "[bc5] exp 0412 ranges fast: %s (tag mf412)\n", on ? "on" : "off"); // exp 0417: said once, either way
			return on;
		}();
		auto first412 = m_ranges.begin();
		if (fast412) {
			first412 = std::upper_bound(m_ranges.begin(), m_ranges.end(), start, [](uint64_t v, const Range& r) { return v < r.start; });
			if (first412 != m_ranges.begin()) --first412;
		}
		for (auto it412 = first412; it412 != m_ranges.end(); ++it412) {
			const auto& range     = *it412;
			const auto  range_end = End(range.start, range.size);
			if (range_end <= current) {
				continue;
			}
			if (range.start > current) {
				break;
			}

			Range part = range;
			part.start = current;
			part.size  = std::min(end, range_end) - current;
			if (part.type == VirtualRangeType::Direct) {
				part.offset += current - range.start;
			}
			out->push_back(part);
			current += part.size;
			if (current == end) {
				return true;
			}
		}

		out->clear();
		return false;
	}

	uint64_t ClampRangeSize(uint64_t virtual_addr, uint64_t size) {
		Common::LockGuard lock(m_mutex);

		if (virtual_addr == 0 || size == 0 || size > UINT64_MAX - virtual_addr) {
			return 0;
		}

		auto vma = std::upper_bound(
		    m_ranges.begin(), m_ranges.end(), virtual_addr,
		    [](uint64_t value, const Range& range) { return value < range.start; });
		if (vma == m_ranges.begin()) {
			return 0;
		}
		--vma;

		const auto vma_end = End(vma->start, vma->size);
		if (virtual_addr < vma->start || virtual_addr >= vma_end ||
		    !IsCommittedRangeType(vma->type)) {
			return 0;
		}

		uint64_t clamped_size = std::min(size, vma_end - virtual_addr);
		uint64_t expected     = virtual_addr + clamped_size;
		++vma;

		while (vma != m_ranges.end() && vma->start == expected && IsCommittedRangeType(vma->type) &&
		       clamped_size < size) {
			const auto chunk = std::min(size - clamped_size, vma->size);
			clamped_size += chunk;
			expected += chunk;
			++vma;
		}

		return clamped_size;
	}

	uint64_t CountPageTableEntries(bool gpu) {
		Common::LockGuard lock(m_mutex);

		uint64_t used = 0;
		for (const auto& r: m_ranges) {
			if (!IsCommittedRangeType(r.type) || r.size == 0) {
				continue;
			}

			const bool has_cpu_access =
			    (r.protection & (PROT_CPU_READ | PROT_CPU_WRITE | PROT_CPU_EXEC)) != 0;
			const bool has_gpu_access = (r.protection & (PROT_GPU_READ | PROT_GPU_WRITE)) != 0;
			if (gpu ? !has_gpu_access : !has_cpu_access) {
				continue;
			}

			const auto end         = End(r.start, r.size);
			const auto first_entry = r.start / PAGE_TABLE_GRANULARITY;
			const auto last_entry  = (end - 1) / PAGE_TABLE_GRANULARITY;
			used += last_entry - first_entry + 1;
		}

		return used;
	}

private:
	static uint64_t End(uint64_t start, uint64_t size) {
		return (UINT64_MAX - start < size ? UINT64_MAX : start + size);
	}

	static bool SameMergeKey(const Range& left, const Range& right) {
		if (left.disallow_merge || right.disallow_merge || left.type == VirtualRangeType::Direct ||
		    right.type == VirtualRangeType::Direct) {
			return false;
		}

		return left.type == right.type && left.protection == right.protection &&
		       left.memory_type == right.memory_type &&
		       std::strncmp(left.name, right.name, KERNEL_MAXIMUM_NAME_LENGTH) == 0;
	}

	// BC5 (experiment 0415, mr415): the span of a mutator's call, under m_mutex. Off until the first reader asks.
	void NoteDirtyUnlocked(uint64_t start, uint64_t size) {
		if (!m_dirty_on) return;
		if (m_dirty.size() >= 65536) {
			m_dirty_overflow = true;
			return;
		}
		m_dirty.emplace_back(start, size);
	}
	std::vector<std::pair<uint64_t, uint64_t>> m_dirty;
	bool                                       m_dirty_on       = false;
	bool                                       m_dirty_overflow = false;

public:
	// BC5 (experiment 0415, tag mr415c; stage S2 of DESIGN-lock-side.md): as SnapshotWithDirty, but instead of every
	// range only, per span, the ranges that overlap or touch it as they are NOW (one hold of the mutex for all).
	// *complete false: the log was not on or was full; the spans are then not to be used and `touching` is empty.
	void DirtyWithTouching(uint64_t* gen, std::vector<std::pair<uint64_t, uint64_t>>* spans, std::vector<std::vector<Range>>* touching, bool* complete) {
		EXIT_IF(gen == nullptr || spans == nullptr || touching == nullptr || complete == nullptr);
		Common::LockGuard lock(m_mutex);
		*gen      = m_gen.load(std::memory_order_acquire);
		*complete = m_dirty_on && !m_dirty_overflow;
		spans->clear();
		spans->swap(m_dirty);
		m_dirty_on       = true;
		m_dirty_overflow = false;
		touching->clear();
		if (!*complete) return;
		touching->reserve(spans->size());
		for (const auto& [start, size]: *spans) {
			const auto [a, b] = bc5::map_records::touching(m_ranges, start, bc5::map_records::end_of(start, size));
			touching->emplace_back(m_ranges.begin() + static_cast<std::ptrdiff_t>(a), m_ranges.begin() + static_cast<std::ptrdiff_t>(b));
		}
	}

private:
	static void AddPiece(std::vector<Range>* ranges, const Range& source, uint64_t start,
	                     uint64_t end) {
		EXIT_IF(ranges == nullptr);

		if (end <= start) {
			return;
		}

		Range piece = source;
		piece.start = start;
		piece.size  = end - start;
		if (piece.type == VirtualRangeType::Direct) {
			piece.offset += start - source.start;
		}
		ranges->push_back(piece);
	}

	std::vector<Range>::iterator LowerBound(uint64_t start) {
		return std::lower_bound(
		    m_ranges.begin(), m_ranges.end(), start,
		    [](const Range& range, uint64_t value) { return range.start < value; });
	}

	void MergeAroundUnlocked(size_t index) {
		if (index >= m_ranges.size()) {
			return;
		}
		if (index != 0) {
			auto& previous = m_ranges[index - 1];
			auto& current  = m_ranges[index];
			if (End(previous.start, previous.size) == current.start &&
			    SameMergeKey(previous, current)) {
				previous.size += current.size;
				m_ranges.erase(m_ranges.begin() + static_cast<std::ptrdiff_t>(index));
				index--;
			}
		}
		while (index + 1 < m_ranges.size()) {
			auto& current = m_ranges[index];
			auto& next    = m_ranges[index + 1];
			if (End(current.start, current.size) != next.start || !SameMergeKey(current, next)) {
				break;
			}
			current.size += next.size;
			m_ranges.erase(m_ranges.begin() + static_cast<std::ptrdiff_t>(index + 1));
		}
	}

	// BC5 (experiment 0167): the three editing operations touch only the ranges that overlap
	// [start, start + size); the table stays sorted, nothing else is copied or sorted. Before,
	// each of them rebuilt the whole vector and MergeUnlocked re-sorted it: with 14,000 ranges
	// and three edits per AMM map, a burst of the second title's streaming maps held the game
	// thread for a second or more (run 810: the stall dumps in introsort and MergeUnlocked).
	// Returns [first, last) of the overlapping ranges.
	std::pair<std::vector<Range>::iterator, std::vector<Range>::iterator> OverlapWindowUnlocked(uint64_t start, uint64_t size) {
		const auto end   = End(start, size);
		auto       first = LowerBound(start);
		if (first != m_ranges.begin()) {
			auto prev = std::prev(first);
			if (VirtualRangesOverlap(start, size, prev->start, prev->size)) {
				first = prev;
			}
		}
		auto last = first;
		while (last != m_ranges.end() && last->start < end) {
			++last;
		}
		return {first, last};
	}

	const Range* ContainingUnlocked(uint64_t address) {
		auto it = LowerBound(address);
		if (it != m_ranges.end() && it->start == address) {
			return &*it;
		}
		if (it == m_ranges.begin()) {
			return nullptr;
		}
		--it;
		return address >= it->start && address < End(it->start, it->size) ? &*it : nullptr;
	}

	template <typename EditFunc>
	void EditUnlocked(uint64_t start, uint64_t size, EditFunc edit) {
		if (size == 0) {
			return;
		}

		std::vector<Range> out;
		auto               edit_end = End(start, size);
		auto [first, last]          = OverlapWindowUnlocked(start, size);

		for (auto it = first; it != last; ++it) {
			const auto& r     = *it;
			auto        r_end = End(r.start, r.size);

			auto mid_start = std::max(start, r.start);
			auto mid_end   = std::min(edit_end, r_end);

			AddPiece(&out, r, r.start, mid_start);

			Range mid = r;
			mid.start = mid_start;
			mid.size  = mid_end - mid_start;
			if (mid.type == VirtualRangeType::Direct) {
				mid.offset += mid_start - r.start;
			}
			edit(&mid);
			out.push_back(mid);

			AddPiece(&out, r, mid_end, r_end);
		}

		const auto index = static_cast<size_t>(first - m_ranges.begin());
		m_ranges.erase(first, last);
		m_ranges.insert(m_ranges.begin() + static_cast<std::ptrdiff_t>(index), out.begin(), out.end());
		MergeWindowUnlocked(index, out.size());
	}

	bool RemoveUnlocked(uint64_t start, uint64_t size) {
		if (size == 0) {
			return false;
		}

		std::vector<Range> out;
		auto               rem_end       = End(start, size);
		auto [first, last]               = OverlapWindowUnlocked(start, size); // BC5 (experiment 0167)
		if (first == last) {
			return false;
		}
		for (auto it = first; it != last; ++it) {
			const auto& r     = *it;
			auto        r_end = End(r.start, r.size);
			AddPiece(&out, r, r.start, std::max(start, r.start));
			AddPiece(&out, r, std::min(rem_end, r_end), r_end);
		}

		const auto index = static_cast<size_t>(first - m_ranges.begin());
		m_ranges.erase(first, last);
		m_ranges.insert(m_ranges.begin() + static_cast<std::ptrdiff_t>(index), out.begin(), out.end());
		return true;
	}

	// BC5 (experiment 0167): merges the `count` ranges inserted at `index` with each other and
	// with their two neighbours, in place.
	void MergeWindowUnlocked(size_t index, size_t count) {
		size_t lo = index > 0 ? index - 1 : 0;
		size_t hi = std::min(m_ranges.size(), index + count + 1); // exclusive
		for (size_t i = lo; i + 1 < hi && i + 1 < m_ranges.size();) {
			auto&       current = m_ranges[i];
			const auto& next    = m_ranges[i + 1];
			if (End(current.start, current.size) == next.start && SameMergeKey(current, next)) {
				current.size += next.size;
				m_ranges.erase(m_ranges.begin() + static_cast<std::ptrdiff_t>(i + 1));
				hi--;
			} else {
				i++;
			}
		}
	}

	void MergeUnlocked() {
		if (m_ranges.size() < 2) {
			return;
		}

		// BC5 (experiment 0167): every edit keeps the table sorted; the sort is a safety net.
		const auto by_start = [](const Range& left, const Range& right) { return left.start < right.start; };
		if (!std::is_sorted(m_ranges.begin(), m_ranges.end(), by_start)) {
			std::sort(m_ranges.begin(), m_ranges.end(), by_start);
		}

		size_t w = 0;
		for (size_t i = 1; i < m_ranges.size(); i++) {
			auto&       last = m_ranges[w];
			const auto& r    = m_ranges[i];
			if (End(last.start, last.size) == r.start && SameMergeKey(last, r)) {
				last.size += r.size;
				continue;
			}
			w++;
			if (w != i) {
				m_ranges[w] = r;
			}
		}
		m_ranges.resize(w + 1);
	}

	Range* FindOverlap(uint64_t start, uint64_t size) {
		auto position = LowerBound(start);
		if (position != m_ranges.end() &&
		    VirtualRangesOverlap(start, size, position->start, position->size)) {
			return &*position;
		}
		if (position != m_ranges.begin()) {
			auto previous = std::prev(position);
			if (VirtualRangesOverlap(start, size, previous->start, previous->size)) {
				return &*previous;
			}
		}
		return nullptr;
	}

	std::vector<Range> m_ranges;
	std::atomic<uint64_t> m_gen {1};
	std::atomic<uint64_t> m_gen_direct {1}; // BC5 (experiment 0437, tag vg437)
	Common::Mutex      m_mutex;
};

#if defined(KYTY_VIRTUAL_MEMORY_ALLOCATION_TESTS)
static uint32_t g_test_physical_memory_unmaps_before_failure = UINT32_MAX;
static bool     g_test_fail_next_fixed_reserve_range_add     = false;
#endif

// SPDX-License-Identifier: GPL-2.0-only
// Experiment 0412 (tag ps412, mksort0412.py; README section 18): PhysicalMemory's mapping table kept sorted by guest
// address, so a block is found by binary search. Used only with KYTY_BC5_PHYSMAP_SORTED set and only while no two blocks
// overlap (insert() refuses an overlapping block; the caller then goes back to the old code for the rest of the run).
// Under that condition the old code's "first block, in insertion order, that matches" is "the block that contains the
// address", which is what containing() returns. V is a std::vector of blocks with map_vaddr, map_size, start_addr, size,
// host_vaddr, host_size and gpu_mode. No system call, no global: physmap0412.cpp runs this text against the old code.
namespace pm412 {

// The block whose [map_vaddr, map_vaddr + map_size) holds addr; end() when none does.
template <class V> auto containing(V& v, uint64_t addr) {
	auto it = std::upper_bound(v.begin(), v.end(), addr, [](uint64_t a, const auto& b) { return a < b.map_vaddr; });
	if (it == v.begin()) return v.end();
	--it;
	return addr - it->map_vaddr < it->map_size ? it : v.end();
}

// A place to start a walk over every block that can overlap [addr, ...): one block before the first that starts after addr.
template <class V> auto walk_from(V& v, uint64_t addr) {
	auto it = std::upper_bound(v.begin(), v.end(), addr, [](uint64_t a, const auto& b) { return a < b.map_vaddr; });
	if (it != v.begin()) --it;
	return it;
}

// Puts b in its place. False, and nothing changed, when b is empty, wraps, or overlaps a neighbour.
template <class V, class B> bool insert(V& v, const B& b) {
	if (b.map_size == 0 || UINT64_MAX - b.map_vaddr < b.map_size) return false;
	auto it = std::lower_bound(v.begin(), v.end(), b.map_vaddr, [](const auto& x, uint64_t a) { return x.map_vaddr < a; });
	if (it != v.end() && it->map_vaddr - b.map_vaddr < b.map_size) return false;
	if (it != v.begin()) {
		const auto& p = *std::prev(it);
		if (b.map_vaddr - p.map_vaddr < p.map_size) return false;
	}
	v.insert(it, b);
	return true;
}

enum Hit { None = 0, Whole = 1, Middle = 2, Head = 3, Tail = 4 };

// Which of Unmap's four cases the block at `it` matches for [vaddr, vaddr + size), in the old code's order.
template <class It> Hit match(It it, uint64_t vaddr, uint64_t size) {
	const auto& b = *it;
	if (b.map_vaddr == vaddr && b.map_size == size) return Whole;
	if (vaddr > b.map_vaddr && vaddr + size < b.map_vaddr + b.map_size) return Middle;
	if (vaddr == b.map_vaddr && size < b.map_size) return Head;
	if (vaddr > b.map_vaddr && vaddr + size == b.map_vaddr + b.map_size) return Tail;
	return None;
}

// The block Unmap acts on, or end(): the one that contains vaddr, when it matches a case.
template <class V> auto candidate(V& v, uint64_t vaddr, uint64_t size) {
	auto it = containing(v, vaddr);
	return it != v.end() && match(it, vaddr, size) != None ? it : v.end();
}

// The old search, for the verify mode and the CPU test: the first block in vector order that matches a case.
template <class V> auto linear_first(V& v, uint64_t vaddr, uint64_t size) {
	for (auto it = v.begin(); it != v.end(); ++it) {
		if (match(it, vaddr, size) != None) return it;
	}
	return v.end();
}

// Unmap's edit on the sorted table, the old code's statements. For Whole, *host_vaddr and *host_size are the removed
// block's host mapping (the caller asks host_still_mapped). The table stays sorted and without overlaps.
template <class V, class G> Hit unmap(V& v, uint64_t vaddr, uint64_t size, G* gpu_mode, uint64_t* host_vaddr, uint64_t* host_size) {
	auto it = candidate(v, vaddr, size);
	if (it == v.end()) return None;
	const Hit h = match(it, vaddr, size);
	auto&     b = *it;
	*gpu_mode   = b.gpu_mode;
	if (h == Whole) {
		*host_vaddr = b.host_vaddr;
		*host_size  = b.host_size;
		v.erase(it);
	} else if (h == Middle) {
		auto right = b;
		right.start_addr += (vaddr + size) - b.map_vaddr;
		right.size      = b.map_vaddr + b.map_size - (vaddr + size);
		right.map_size  = right.size;
		right.map_vaddr = vaddr + size;
		b.size          = vaddr - b.map_vaddr;
		b.map_size      = b.size;
		v.insert(std::next(it), right); // right after its left half: still sorted
	} else if (h == Head) {
		b.start_addr += size;
		b.size -= size;
		b.map_vaddr += size;
		b.map_size -= size;
	} else {
		b.size     = vaddr - b.map_vaddr;
		b.map_size = b.size;
	}
	return h;
}

// Whether a block with this host mapping is left. Every block is a piece of the Map() call that made its host mapping
// (Map sets host_vaddr = vaddr, host_size = len; the splits copy them), so it lies inside the host range.
template <class V> bool host_still_mapped(V& v, uint64_t host_vaddr, uint64_t host_size) {
	for (auto it = walk_from(v, host_vaddr); it != v.end(); ++it) {
		if (it->map_vaddr >= host_vaddr && it->map_vaddr - host_vaddr >= host_size) break; // past the host range
		if (it->host_vaddr == host_vaddr && it->host_size == host_size) return true;
	}
	return false;
}

// Whether every block lies inside its host range (what host_still_mapped relies on) and the table is sorted without overlaps.
template <class V> bool sound(const V& v) {
	for (size_t i = 0; i < v.size(); i++) {
		const auto& b = v[i];
		if (b.map_size == 0 || b.map_vaddr < b.host_vaddr || b.map_vaddr - b.host_vaddr > b.host_size || b.map_size > b.host_size - (b.map_vaddr - b.host_vaddr)) return false;
		if (i != 0 && b.map_vaddr - v[i - 1].map_vaddr < v[i - 1].map_size) return false;
		if (i != 0 && b.map_vaddr < v[i - 1].map_vaddr) return false;
	}
	return true;
}

} // namespace pm412

// Experiment 0412 (tag ps412): KYTY_BC5_PHYSMAP_SORTED. 0 off, 1 on, 2 verify. g_pm412_ok: no overlapping block was ever added.
static int Pm412Mode() {
	static const int mode = [] {
		const char* e = BC5_FIXED_ENV("KYTY_BC5_PHYSMAP_SORTED", "1");
		if (e == nullptr || e[0] == 0 || (e[0] == '0' && e[1] == 0)) {
			std::fprintf(stderr, "[bc5] exp 0412 physmap sorted: off (tag ps412)\n"); // exp 0417: said once, also when off
			return 0;
		}
		const int m = std::strcmp(e, "verify") == 0 ? 2 : std::strcmp(e, "1") == 0 ? 1 : 0;
		std::fprintf(stderr, "[bc5] exp 0412 physmap sorted: %s (tag ps412)\n", m == 2 ? "verify" : m == 1 ? "on" : "value not understood, off");
		return m;
	}();
	return mode;
}
static bool     g_pm412_ok       = true;
static uint64_t g_pm412_mismatch = 0;

class PhysicalMemory {
public:
	struct AllocatedBlock {
		uint64_t            start_addr;
		uint64_t            size;
		uint64_t            map_vaddr;
		uint64_t            map_size;
		uint64_t            host_vaddr;
		uint64_t            host_size;
		int                 prot;
		VirtualMemory::Mode mode;
		GpuAccessMode       gpu_mode;
		int                 memory_type;
		bool                pool_expansion;
		char                name[KERNEL_MAXIMUM_NAME_LENGTH];
	};

	PhysicalMemory() {
		EXIT_NOT_IMPLEMENTED(!Common::Thread::IsMainThread());
		m_free.emplace(0, Size());
	}
	virtual ~PhysicalMemory() = default;
	// exp 0412 (tag ff412): the free list in numbers, for the catcher's state line (the caller holds the memory lock).
	void Bc5FreeStats(uint64_t* total, uint64_t* largest, uint64_t* runs) const {
		*total = 0;
		*largest = 0;
		*runs = m_free.size();
		for (const auto& r: m_free) {
			*total += r.second;
			if (r.second > *largest) *largest = r.second;
		}
	}

	KYTY_CLASS_NO_COPY(PhysicalMemory);

	static uint64_t TotalSize()
	{
		// KytyPlus: PS5 titles expect ~12.5 GB of game-visible memory (direct + flexible).
		// 8 GB made large UE4 titles fail streaming allocations at level load (Sonic
		// Superstars #12: stutters then null-write crash); the failure surfaced as a guest
		// write-to-null. Cap by host RAM (leave ~3.5 GB for the host) with an 8 GB floor.
		static const uint64_t cached = [] {
			constexpr uint64_t megabyte       = 1024ull * 1024ull;
			constexpr uint64_t ps5_game_total = 12800ull * megabyte; // ~12.5 GiB
			constexpr uint64_t minimum        = 8192ull * megabyte;
			uint64_t host_total               = 0;
			uint64_t host_avail               = 0;
		#if KYTY_PLATFORM == KYTY_PLATFORM_WINDOWS
			MEMORYSTATUSEX st {};
			st.dwLength     = sizeof(st);
			if (GlobalMemoryStatusEx(&st)) {
				host_total = st.ullTotalPhys;
				host_avail = st.ullAvailPhys;
			}
		#elif KYTY_PLATFORM == KYTY_PLATFORM_LINUX
			long pages = sysconf(_SC_PHYS_PAGES);
			long page  = sysconf(_SC_PAGE_SIZE);
			if (pages > 0 && page > 0) {
				host_total = static_cast<uint64_t>(pages) * static_cast<uint64_t>(page);
			}
			host_avail = host_total;
		#endif
			uint64_t target = ps5_game_total;
			if (host_total > 0 && host_total < ps5_game_total + 3500ull * megabyte) {
				// Small host: leave ~3.5 GB for the OS/emulator, floor at minimum.
				const uint64_t capped = host_avail > 3500ull * megabyte
				                            ? host_avail - 3500ull * megabyte
				                            : minimum;
				target = std::max(minimum, std::min(ps5_game_total, capped));
			}
			// BC5 local patch: explicit override for hosts where the RAM cap is too low for a
			// PS5 title (direct memory is memfd-backed and committed lazily, so overcommit works
			// as long as the title does not touch it all).
			if (const char* env = std::getenv("KYTY_GUEST_MEMORY_MB"); env != nullptr && *env != 0) {
				target = std::strtoull(env, nullptr, 10) * megabyte;
			}
			target = target & ~(0x4000ull - 1ull);
			LOGF("guest memory total = %llu MiB\n", static_cast<unsigned long long>(target / megabyte));
			return target;
		}();
		return cached;
	}
	static uint64_t           Size() {
		EXIT_IF(g_flexible_memory_size >= TotalSize());
		return TotalSize() - g_flexible_memory_size;
	}

	bool Alloc(uint64_t search_start, uint64_t search_end, size_t len, size_t alignment,
	           uint64_t* phys_addr_out, int memory_type, bool pool_expansion = false);
	bool Available(uint64_t search_start, uint64_t search_end, size_t alignment,
	               uint64_t* phys_addr_out, uint64_t* size_out);
	bool Release(uint64_t start, size_t len, uint64_t* vaddr, uint64_t* size,
	             GpuAccessMode* gpu_mode);
	bool Map(uint64_t vaddr, uint64_t phys_addr, size_t len, int prot, VirtualMemory::Mode mode,
	         GpuAccessMode gpu_mode);
	bool Unmap(uint64_t vaddr, uint64_t size, GpuAccessMode* gpu_mode,
	           uint64_t* host_vaddr_to_release = nullptr);
	bool Find(uint64_t vaddr, uint64_t* base_addr, size_t* len, int* prot,
	          VirtualMemory::Mode* mode, GpuAccessMode* gpu_mode);
	bool Find(uint64_t phys_addr, bool next, PhysicalMemory::AllocatedBlock* out);
	bool CanMapDirect(uint64_t phys_addr, size_t len);
	bool ReleasePoolExpansion(uint64_t phys_addr, size_t len);
	bool GetAllocatedSpan(uint64_t phys_addr, size_t len, std::vector<AllocatedBlock>* blocks);
	std::vector<AllocatedBlock> FindMappings(uint64_t phys_addr, size_t len);
	void ProtectMapping(uint64_t vaddr, uint64_t size, int prot, VirtualMemory::Mode mode,
	                    GpuAccessMode gpu_mode);
	void SetVirtualRangeName(uint64_t vaddr, uint64_t len, const char* name);
	void SetVirtualRangeMemoryType(uint64_t vaddr, uint64_t len, int memory_type);

	[[nodiscard]] Common::Mutex&                            GetMutex() { return m_mutex; }
	[[nodiscard]] const std::map<uint64_t, AllocatedBlock>& GetPhysicalBlocks() const {
		return m_physical;
	}
	[[nodiscard]] const std::vector<AllocatedBlock>& GetMappings() const { return m_mappings; }

private:
	void ConsumeFreeRange(std::map<uint64_t, uint64_t>::iterator range, uint64_t start,
	                      uint64_t size);
	void AddFreeRange(uint64_t start, uint64_t size);

	std::map<uint64_t, AllocatedBlock> m_physical;
	std::map<uint64_t, uint64_t>       m_free;
	std::vector<AllocatedBlock>        m_mappings;
	Common::Mutex                      m_mutex;
};

class FlexibleMemory {
public:
	struct AllocatedBlock {
		uint64_t            map_vaddr;
		uint64_t            map_size;
		uint64_t            backing_offset;
		uint64_t            host_vaddr;
		uint64_t            host_size;
		int                 prot;
		VirtualMemory::Mode mode;
		GpuAccessMode       gpu_mode;
		char                name[KERNEL_MAXIMUM_NAME_LENGTH];
	};

	FlexibleMemory() {
		EXIT_NOT_IMPLEMENTED(!Common::Thread::IsMainThread());
		m_free.emplace(PhysicalMemory::Size(), Size());
	}
	virtual ~FlexibleMemory() = default;

	KYTY_CLASS_NO_COPY(FlexibleMemory);

	static uint64_t Size() { return g_flexible_memory_size; }
	uint64_t        Available();

	bool Map(uint64_t vaddr, size_t len, int prot, VirtualMemory::Mode mode, GpuAccessMode gpu_mode,
	         const char* name);
	bool Unmap(uint64_t vaddr, uint64_t size, GpuAccessMode* gpu_mode,
	           uint64_t* host_vaddr_to_release = nullptr);
	bool Find(uint64_t vaddr, uint64_t* base_addr, size_t* len, int* prot,
	          VirtualMemory::Mode* mode, GpuAccessMode* gpu_mode);
	bool Snapshot(uint64_t vaddr, uint64_t size, std::vector<AllocatedBlock>* blocks);
	bool Restore(const std::vector<AllocatedBlock>& blocks);
	void Protect(uint64_t vaddr, uint64_t size, int prot, VirtualMemory::Mode mode,
	             GpuAccessMode gpu_mode);
	void SetVirtualRangeName(uint64_t vaddr, uint64_t len, const char* name);

	[[nodiscard]] Common::Mutex&                     GetMutex() { return m_mutex; }
	[[nodiscard]] const std::vector<AllocatedBlock>& GetBlocks() const { return m_allocated; }

private:
	void ConsumeFreeRange(std::map<uint64_t, uint64_t>::iterator range, uint64_t start,
	                      uint64_t size);
	void AddFreeRange(uint64_t start, uint64_t size);

	std::vector<AllocatedBlock>  m_allocated;
	std::map<uint64_t, uint64_t> m_free;
	uint64_t                     m_allocated_total = 0;
	Common::Mutex                m_mutex;
};

class PooledMemory {
public:
	struct Mapping {
		uint64_t      vaddr;
		uint64_t      size;
		uint64_t      phys_addr;
		GpuAccessMode gpu_mode;
	};

	void                   Expand(uint64_t phys_addr, uint64_t size);
	bool                   ReleaseExpansion(uint64_t phys_addr, uint64_t size);
	bool                   Allocate(uint64_t vaddr, uint64_t size, GpuAccessMode gpu_mode,
	                                std::vector<Mapping>* mappings);
	bool                   Query(uint64_t vaddr, uint64_t size, std::vector<Mapping>* mappings);
	bool                   Release(uint64_t vaddr, uint64_t size, GpuAccessMode* gpu_mode);
	[[nodiscard]] uint64_t Available();
	[[nodiscard]] std::vector<Mapping> GetMappings();

private:
	struct PhysicalRange {
		uint64_t start;
		uint64_t size;
	};

	void AddFreeUnlocked(uint64_t start, uint64_t size);
	bool QueryUnlocked(uint64_t vaddr, uint64_t size, std::vector<Mapping>* mappings) const;

	std::vector<PhysicalRange> m_free;
	std::vector<PhysicalRange> m_expansions;
	std::vector<Mapping>       m_mappings;
	Common::Mutex              m_mutex;
};

static std::unique_ptr<PhysicalMemory>    g_physical_memory;
static std::unique_ptr<FlexibleMemory>    g_flexible_memory;
static std::unique_ptr<PooledMemory>      g_pooled_memory;
static std::unique_ptr<VirtualRanges>     g_virtual_ranges;

// BC5: enumerates the guest's mapped (non-reserved) ranges: start, size, type (0 direct,
// 1 flexible, 2 pooled, 3 stack, 4 code, 5 runtime), protection, name.
void Bc5ForEachMappedRange(void (*cb)(uint64_t, uint64_t, int, int, const char*, void*), void* ctx,
                           void (*cb2)(uint64_t, uint64_t, uint64_t, int, int, const char*, void*)) {
	if (g_virtual_ranges == nullptr || (cb == nullptr && cb2 == nullptr)) {
		return;
	}
	std::vector<VirtualRanges::Range> ranges;
	g_virtual_ranges->Snapshot(&ranges);
	for (const auto& r: ranges) {
		int type = -1;
		switch (r.type) {
			case VirtualRangeType::Direct: type = 0; break;
			case VirtualRangeType::Flexible: type = 1; break;
			case VirtualRangeType::Pooled: type = 2; break;
			case VirtualRangeType::Stack: type = 3; break;
			case VirtualRangeType::Code: type = 4; break;
			case VirtualRangeType::Runtime: type = 5; break;
			default: break;
		}
		if (type >= 0) {
			if (cb != nullptr) cb(r.start, r.size, type, r.protection, r.name, ctx);
			if (cb2 != nullptr) cb2(r.start, r.size, r.offset, type, r.protection, r.name, ctx); // with the physical offset
		}
	}
}
// BC5 (experiment 0037): the generation of the guest's ranges (see VirtualRanges::Generation).
void Bc5GuestRangesIn(uint64_t lo, uint64_t hi, std::vector<std::pair<uint64_t, uint64_t>>* out) {
	if (g_virtual_ranges == nullptr || out == nullptr) {
		if (out != nullptr) out->clear();
		return;
	}
	g_virtual_ranges->Overlapping(lo, hi, out);
}
uint64_t Bc5MappedRangesGeneration() {
	return g_virtual_ranges != nullptr ? g_virtual_ranges->Generation() : 0;
}
// BC5 (experiment 0437, tag vg437): see VirtualRanges::DirectGeneration.
uint64_t Bc5DirectRangesGeneration() {
	return g_virtual_ranges != nullptr ? g_virtual_ranges->DirectGeneration() : 0;
}
// BC5 (experiment 0415, tag mr415c): the spans changed since the last call and, through cb, for span number `index`
// the mapped ranges that overlap or touch it now (the types of Bc5ForEachMappedRange). False when there are no ranges.
bool Bc5RangesDirtyTouching(void (*cb)(size_t, uint64_t, uint64_t, uint64_t, int, int, const char*, void*), void* ctx, uint64_t* gen,
                            std::vector<std::pair<uint64_t, uint64_t>>* spans, bool* complete) {
	if (g_virtual_ranges == nullptr || cb == nullptr || gen == nullptr || spans == nullptr || complete == nullptr) {
		return false;
	}
	std::vector<std::vector<VirtualRanges::Range>> touching;
	g_virtual_ranges->DirtyWithTouching(gen, spans, &touching, complete);
	for (size_t i = 0; i < touching.size(); i++) {
		for (const auto& r: touching[i]) {
			int type = -1;
			switch (r.type) {
				case VirtualRangeType::Direct: type = 0; break;
				case VirtualRangeType::Flexible: type = 1; break;
				case VirtualRangeType::Pooled: type = 2; break;
				case VirtualRangeType::Stack: type = 3; break;
				case VirtualRangeType::Code: type = 4; break;
				case VirtualRangeType::Runtime: type = 5; break;
				default: break;
			}
			if (type >= 0) cb(i, r.start, r.size, r.offset, type, r.protection, r.name, ctx);
		}
	}
	return true;
}
// BC5 (experiment 0415, tag mr415): Bc5ForEachMappedRange's callback over one snapshot, with that snapshot's
// generation and the spans changed since the last call (see VirtualRanges::SnapshotWithDirty). False when there are
// no ranges yet.
bool Bc5RangesWithDirty(void (*cb)(uint64_t, uint64_t, uint64_t, int, int, const char*, void*), void* ctx, uint64_t* gen,
                        std::vector<std::pair<uint64_t, uint64_t>>* spans, bool* complete) {
	if (g_virtual_ranges == nullptr || cb == nullptr || gen == nullptr || spans == nullptr || complete == nullptr) {
		return false;
	}
	std::vector<VirtualRanges::Range> ranges;
	g_virtual_ranges->SnapshotWithDirty(&ranges, gen, spans, complete);
	for (const auto& r: ranges) {
		int type = -1;
		switch (r.type) {
			case VirtualRangeType::Direct: type = 0; break;
			case VirtualRangeType::Flexible: type = 1; break;
			case VirtualRangeType::Pooled: type = 2; break;
			case VirtualRangeType::Stack: type = 3; break;
			case VirtualRangeType::Code: type = 4; break;
			case VirtualRangeType::Runtime: type = 5; break;
			default: break;
		}
		if (type >= 0) cb(r.start, r.size, r.offset, type, r.protection, r.name, ctx);
	}
	return true;
}
// BC5 (ADR 0006): the direct-memory memfd (sealed), -1 when there is none.
int Bc5DirectMemoryFd() {
	return GuestBackingStore::Bc5Fd();
}
static std::unique_ptr<GuestAddressSpace>& Bc5GuestAddressSpace();
// BC5 (experiment 0023): the memfd behind private guest memory (file offset = guest address), -1
// when private memory is anonymous; and the private regions with the type and name of the range
// each one starts in (type as in Bc5ForEachMappedRange, -1 when unknown).
int Bc5PrivateMemoryFd() {
	return GuestAddressSpace::Bc5PrivateFd();
}
void Bc5ForEachPrivateRegion(void* ctx, void (*cb)(uint64_t start, uint64_t size, int type, const char* name, void* ctx)) {
	auto& space = Bc5GuestAddressSpace();
	if (space == nullptr || cb == nullptr) {
		return;
	}
	std::vector<std::pair<uint64_t, uint64_t>> regions;
	space->Bc5SnapshotPrivate(&regions);
	std::vector<VirtualRanges::Range> ranges;
	if (g_virtual_ranges != nullptr) {
		g_virtual_ranges->Snapshot(&ranges);
	}
	for (const auto& [start, size]: regions) {
		int         type = -1;
		const char* name = "";
		// BC5 (experiment 0037): the ranges are sorted by start; one binary search per region
		// instead of a walk over all of them (11,600 ranges, 140 regions, every sync).
		auto it = std::upper_bound(ranges.begin(), ranges.end(), start,
		                           [](uint64_t v, const VirtualRanges::Range& r) { return v < r.start; });
		if (it != ranges.begin()) {
			--it;
		}
		for (; it != ranges.end() && it->start <= start; ++it) {
			const auto& r = *it;
			if (start >= r.start && start < r.start + r.size) {
				switch (r.type) {
					case VirtualRangeType::Direct: type = 0; break;
					case VirtualRangeType::Flexible: type = 1; break;
					case VirtualRangeType::Pooled: type = 2; break;
					case VirtualRangeType::Stack: type = 3; break;
					case VirtualRangeType::Code: type = 4; break;
					case VirtualRangeType::Runtime: type = 5; break;
					default: break;
				}
				name = r.name;
				break;
			}
		}
		cb(start, size, type, name != nullptr ? name : "", ctx);
	}
}
static std::unique_ptr<GuestAddressSpace> g_guest_address_space;
static std::unique_ptr<GuestAddressSpace>& Bc5GuestAddressSpace() {
	return g_guest_address_space;
}
static callback_func_t                    g_alloc_callback        = nullptr;
static callback_func_t                    g_free_callback         = nullptr;
static std::atomic<uint64_t>              g_memory_pool_committed = 0;
static void                               MemoryPoolSubtractCommitted(uint64_t len);
// Keep host mappings, physical blocks, placeholders, and virtual ranges in step.
static std::recursive_mutex g_memory_operation_mutex;
// BC5 experiment 0412 (tag ff412, README sections 57 and 59): which host memory call fails first when the title is
// offered less memory. KYTY_BC5_MEM_FIRSTFAIL=1 (unset, empty or 0: off; one test of a constant on a path that has
// already failed). A catcher: it changes no result.
//   - every wrapped memory call that returns an error is counted per call; the first kFull failures and then every
//     failure whose number is a power of two are written in full (the call, its result, up to six arguments, the
//     caller's address, the thread) with the state of the direct memory at that moment;
//   - the last kRing failures are kept and printed again when the host is about to die on an access to a reserved
//     AMM page (the exit "AMM virtual-memory unmap is unsupported"), so the death is tied to what failed before it.
// The decisions (when to print, the ring) are here, free of the host, and tested by firstfail0412.cpp; the host's part
// (wrappers, the state line) is pasted by mkff0412.py.
namespace ff412 {
static constexpr uint64_t kFull = 12;
static constexpr unsigned kRing = 8;
struct Fail {
	const char* call = "";
	int         result = 0;
	uint64_t    n = 0; // its number among all failures, from 1
	uint64_t    a[6] = {0, 0, 0, 0, 0, 0};
	unsigned    args = 0;
};
// Is the n-th failure (from 1) written in full?
inline bool full(uint64_t n) { return n != 0 && (n <= kFull || (n & (n - 1)) == 0); }
struct Ring {
	Fail     e[kRing];
	uint64_t count = 0;
	void     push(const Fail& f) { e[count++ % kRing] = f; }
	// The kept failures, oldest first.
	unsigned list(const Fail** out) const {
		const unsigned n = count < kRing ? static_cast<unsigned>(count) : kRing;
		for (unsigned i = 0; i < n; i++) out[i] = &e[(count - n + i) % kRing];
		return n;
	}
};
inline bool on() {
	static const bool v = [] {
		const char* e = BC5_DIAG_ENV("KYTY_BC5_MEM_FIRSTFAIL");
		return e != nullptr && e[0] != 0 && !(e[0] == '0' && e[1] == 0);
	}();
	return v;
}
template <class T> inline uint64_t u(T v) {
	if constexpr (std::is_pointer_v<T>) return reinterpret_cast<uint64_t>(v);
	else return static_cast<uint64_t>(v);
}
} // namespace ff412
// Experiment 0412 (tag ff412): KYTY_BC5_MEM_FIRSTFAIL, the host's part. One mutex around the counters and the ring;
// the state line takes the memory lock (recursive: a failing call may still hold it).
static ff412::Ring g_ff412_ring;
static std::mutex  g_ff412_mutex;
// exp 0412 (tag ff412, 2026-11-14): the arming line. Without it "the catcher printed nothing" cannot be told from
// "the catcher was not on" (exp 0419's nine walks of 2026-11-13).
[[maybe_unused]] static const bool g_ff412_armed = [] {
	if (ff412::on()) {
		std::fprintf(stderr, "[bc5] mem firstfail (exp 0412, tag ff412): KYTY_BC5_MEM_FIRSTFAIL on, armed: the wrapped memory calls, the AMM auto pool's refused borrow and the exit on a reserved AMM page report here\n");
		std::fflush(stderr);
	}
	return true;
}();
static void ff412_thread(char* out, size_t cap) {
	std::snprintf(out, cap, "tid %d", static_cast<int>(gettid()));
	char path[64];
	std::snprintf(path, sizeof(path), "/proc/self/task/%d/comm", static_cast<int>(gettid()));
	if (FILE* f = std::fopen(path, "r")) {
		char name[32] = "";
		if (std::fgets(name, sizeof(name), f) != nullptr) {
			name[std::strcspn(name, "\n")] = 0;
			std::snprintf(out, cap, "tid %d (%s)", static_cast<int>(gettid()), name);
		}
		std::fclose(f);
	}
}
static void ff412_state_line() {
	std::scoped_lock memory_lock(g_memory_operation_mutex);
	uint64_t total = 0, largest = 0, runs = 0;
	if (g_physical_memory) g_physical_memory->Bc5FreeStats(&total, &largest, &runs);
	std::fprintf(stderr, "[bc5] mem firstfail (exp 0412, tag ff412):   direct memory: offered %" PRIu64 " MiB, free %" PRIu64 " MiB in %" PRIu64 " runs, the largest %" PRIu64 " MiB; flexible: configured %" PRIu64 " MiB, available %" PRIu64 " MiB\n",
	             static_cast<uint64_t>(PhysicalMemory::Size() >> 20u), total >> 20u, runs, largest >> 20u, static_cast<uint64_t>(FlexibleMemory::Size() >> 20u),
	             g_flexible_memory ? static_cast<uint64_t>(g_flexible_memory->Available() >> 20u) : 0);
}
static void ff412_report(const char* call, int result, const void* caller, std::initializer_list<uint64_t> args) {
	if (!ff412::on()) return;
	ff412::Fail f;
	f.call   = call;
	f.result = result;
	for (const uint64_t a: args) {
		if (f.args < 6) f.a[f.args++] = a;
	}
	bool print = false;
	{
		std::scoped_lock lk(g_ff412_mutex);
		f.n = g_ff412_ring.count + 1;
		g_ff412_ring.push(f);
		print = ff412::full(f.n);
	}
	if (!print) return;
	char who[64];
	ff412_thread(who, sizeof(who));
	std::fprintf(stderr, "[bc5] mem firstfail (exp 0412, tag ff412): failure %" PRIu64 ": %s -> 0x%08x; args", f.n, call, static_cast<unsigned>(result));
	for (unsigned i = 0; i < f.args; i++) std::fprintf(stderr, " 0x%" PRIx64, f.a[i]);
	std::fprintf(stderr, "; caller %p; %s\n", caller, who);
	ff412_state_line();
	std::fflush(stderr);
}
extern "C" void bc5_mem_firstfail_note(const char* call, int result, uint64_t a0, uint64_t a1, uint64_t a2, uint64_t a3) {
	ff412_report(call, result, __builtin_return_address(0), {a0, a1, a2, a3});
}
// The host is about to exit on an access to a reserved AMM page: what failed before it.
static void ff412_death(uint64_t vaddr) {
	if (!ff412::on()) return;
	const ff412::Fail* kept[ff412::kRing];
	unsigned           n = 0;
	uint64_t           all = 0;
	{
		std::scoped_lock lk(g_ff412_mutex);
		n   = g_ff412_ring.list(kept);
		all = g_ff412_ring.count;
		char who[64];
		ff412_thread(who, sizeof(who));
		std::fprintf(stderr, "[bc5] mem firstfail (exp 0412, tag ff412): access to the reserved AMM page 0x%016" PRIx64 " on %s; %" PRIu64 " memory calls failed before it, the last %u:\n", vaddr, who, all, n);
		for (unsigned i = 0; i < n; i++) {
			std::fprintf(stderr, "[bc5] mem firstfail (exp 0412, tag ff412):   failure %" PRIu64 ": %s -> 0x%08x; args", kept[i]->n, kept[i]->call, static_cast<unsigned>(kept[i]->result));
			for (unsigned k = 0; k < kept[i]->args; k++) std::fprintf(stderr, " 0x%" PRIx64, kept[i]->a[k]);
			std::fprintf(stderr, "\n");
		}
	}
	ff412_state_line();
	std::fflush(stderr);
}

// The base address the PS5 kernel hands out for hint-less user mappings. Guest code can
// assume mappings it did not place explicitly are at or above this (Sony's libc rejects a
// heap below it), so hint-less searches must not fall back to the low system-managed range.
static constexpr uint64_t GUEST_DEFAULT_MAP_BASE = 0x200000000ull;

static uint64_t FindGuestFreeRange(uint64_t search_addr, uint64_t size, uint64_t alignment) {
	EXIT_IF(g_guest_address_space == nullptr || g_virtual_ranges == nullptr);

	auto find_in = [&](uint64_t begin, uint64_t end) {
		auto current = begin;
		while (current < end && size <= end - current) {
			const auto candidate =
			    g_guest_address_space->FindFreeAligned(current, end, size, alignment);
			if (candidate == 0) {
				return uint64_t {0};
			}
			VirtualRanges::Range overlap {};
			if (!g_virtual_ranges->QueryOverlap(candidate, size, &overlap)) {
				return candidate;
			}
			const auto overlap_end = overlap.start + overlap.size;
			if (overlap_end <= current) {
				return uint64_t {0};
			}
			current = overlap_end;
		}
		return uint64_t {0};
	};

	if (search_addr != 0) {
		return find_in(search_addr, HOST_USER_MAX + 1u);
	}
	auto addr = find_in(GUEST_DEFAULT_MAP_BASE, HOST_SYSTEM_MANAGED_MAX + 1u);
	if (addr == 0) {
		addr = find_in(HOST_USER_MIN, HOST_USER_MAX + 1u);
	}
	return addr;
}

bool TryWriteBacking(uint64_t vaddr, const void* data, uint64_t size) {
	return g_guest_address_space != nullptr &&
	       g_guest_address_space->TryWriteBacking(vaddr, data, size);
}

bool TryReadBacking(uint64_t vaddr, void* data, uint64_t size) {
	return g_guest_address_space != nullptr &&
	       g_guest_address_space->TryReadBacking(vaddr, data, size);
}

uint64_t ClampRangeSize(uint64_t vaddr, uint64_t size) {
	EXIT_IF(g_virtual_ranges == nullptr);

	const auto clamped_size = g_virtual_ranges->ClampRangeSize(vaddr, size);
	if (clamped_size == 0) {
		EXIT("Memory: attempted to access invalid address 0x%016" PRIx64 " with size 0x%016" PRIx64
		     "\n",
		     vaddr, size);
	}
	if (clamped_size != size) {
		LOGF("Memory: clamped buffer range addr=0x%016" PRIx64 " size=0x%016" PRIx64
		     " to 0x%016" PRIx64 "\n",
		     vaddr, size, clamped_size);
	}
	return clamped_size;
}

void WriteBacking(uint64_t vaddr, const void* data, uint64_t size) noexcept {
	if (!TryWriteBacking(vaddr, data, size)) {
		EXIT("Memory: required direct-backing write failed, addr=0x%016" PRIx64
		     " size=0x%016" PRIx64 "\n",
		     vaddr, size);
	}
}

void InvalidateMemory(uint64_t vaddr, uint64_t size) {
	if (size == 0) {
		return;
	}
	(void)GetGpuResources().InvalidateMemory(vaddr, size);
}

void InstallGpuResources(Graphics::GpuResourceManager* resources) noexcept {
	EXIT_IF(resources != nullptr && g_gpu_resources != nullptr);
	g_gpu_resources = resources;
}

bool HandleGpuFault(Graphics::PageFaultAccess access, uint64_t fault_vaddr) noexcept {
	return g_gpu_resources != nullptr && g_gpu_resources->HandleFault(access, fault_vaddr);
}

struct PrtAperture {
	uint64_t address = 0;
	uint64_t size    = 0;
};

constexpr int      PRT_APERTURE_MAX_INDEX = 2;
constexpr uint64_t PRT_PAGE_SIZE          = 0x4000;
constexpr uint64_t PRT_APERTURE_START     = 0x0f00000000ull;
constexpr uint64_t PRT_APERTURE_END       = 0xfc00000000ull;

static std::array<PrtAperture, PRT_APERTURE_MAX_INDEX + 1> g_prt_apertures {};
static Common::Mutex                                       g_prt_aperture_mutex;

static bool IsInPrtAperture(uint64_t address) {
	Common::LockGuard lock(g_prt_aperture_mutex);

	for (const auto& aperture: g_prt_apertures) {
		if (address >= aperture.address && address < aperture.address + aperture.size) {
			return true;
		}
	}

	return false;
}

static bool SelfTestSub64SharedPlaceholderAlias() {
#if KYTY_PLATFORM == KYTY_PLATFORM_WINDOWS
	constexpr uint64_t PageSize    = 0x4000;
	const auto         granularity = g_guest_address_space->GetGranularity();
	if (granularity < PageSize * 2u) {
		LOGF_COLOR(
		    Log::Color::Yellow,
		    "\t direct-memory sub-64K placeholder self-test skipped: granularity too small\n");
		return true;
	}

	const auto base = FindGuestFreeRange(0, granularity, granularity);
	if (base == 0) {
		LOGF_COLOR(Log::Color::Red,
		           "\t direct-memory sub-64K placeholder self-test: reserve unavailable\n");
		return false;
	}

	const auto alias          = base + PageSize;
	bool       ok             = false;
	auto       failure_reason = GuestBackingStore::FailureReason::None;
	if (g_guest_address_space->MapBacking(alias, PageSize, PageSize, VirtualMemory::Mode::ReadWrite,
	                                      &failure_reason)) {
		auto* ptr = reinterpret_cast<uint64_t*>(alias);
		*ptr      = 0x4b59545953553634ull; // "KYTYSU64"
		ok        = (*ptr == 0x4b59545953553634ull);
		std::memset(ptr, 0, PageSize);

		ok = g_guest_address_space->UnmapBacking(alias, PageSize) && ok;
	}

	LOGF_COLOR(
	    ok ? Log::Color::Green : Log::Color::Red,
	    "\t direct-memory sub-64K placeholder self-test: %s%s%s\n", ok ? "ok" : "failed",
	    ok ? "" : ", reason = ", ok ? "" : GuestBackingStore::GetFailureReasonName(failure_reason));
	return ok;
#else
	return true;
#endif
}

static bool ReplaceFixedRangeWithReserved(uint64_t start, uint64_t size);

KYTY_SUBSYSTEM_INIT(Memory) {
	g_flexible_memory_size_frozen = true;
	{ // experiment 0401 series e: the sizes, with the switch on or off (flexible + table overhead must fit, as in 09753bf)
		constexpr uint64_t mib    = 1024ull * 1024ull;
		const auto         tables = ::Loader::SystemContentGetMemoryTables();
		const uint64_t     total  = PhysicalMemory::TotalSize();
		EXIT_IF(g_flexible_memory_size >= total);
		std::fprintf(stderr,
		             "[bc5] exp 0401: memory from param.json %s: total %" PRIu64 " MiB, flexible %" PRIu64 " MiB, direct %" PRIu64
		             " MiB (param.json: flexible %" PRIu64 ", cpu table %" PRIu64 ", gpu table %" PRIu64 ", amm table %" PRIu64 " MiB)",
		             "off", total / mib, g_flexible_memory_size / mib, (total - g_flexible_memory_size) / mib,
		             ::Loader::SystemContentGetFlexibleMemorySize() / mib, tables.cpu_table_memory / mib,
		             tables.gpu_table_memory / mib, tables.amm_table_memory / mib);
		std::fprintf(stderr, "\n");
	}
	Bc5R3Journal(); // experiment 0405 series e5: one line, the R3 memory switches
	VirtualMemory::Init();
	g_guest_address_space = std::make_unique<GuestAddressSpace>(PhysicalMemory::TotalSize());
	g_physical_memory     = std::make_unique<PhysicalMemory>();
	g_flexible_memory     = std::make_unique<FlexibleMemory>();
	g_pooled_memory       = std::make_unique<PooledMemory>();
	g_virtual_ranges      = std::make_unique<VirtualRanges>();
	EXIT_IF(!g_guest_address_space->SelfTest());
	EXIT_IF(!SelfTestSub64SharedPlaceholderAlias());
}

KYTY_SUBSYSTEM_UNEXPECTED_SHUTDOWN(Memory) {}

KYTY_SUBSYSTEM_DESTROY(Memory) {
	g_pooled_memory.reset();
	g_flexible_memory.reset();
	g_physical_memory.reset();
	g_virtual_ranges.reset();
	g_guest_address_space.reset();
}

struct AlignedPos {
	uint64_t value = 0;
	bool     valid = false;
};

static constexpr AlignedPos GetAlignedPos(uint64_t pos, size_t alignment) {
	if (alignment == 0) {
		return {pos, true};
	}

	const auto remainder = pos % alignment;
	const auto increment = (remainder != 0 ? alignment - remainder : 0);
	if (increment > UINT64_MAX - pos) {
		return {};
	}

	return {pos + increment, true};
}

static_assert(!GetAlignedPos(UINT64_MAX - 1, 4).valid);

void RegisterCallbacks(callback_func_t alloc_func, callback_func_t free_func) {
	EXIT_IF(g_alloc_callback != nullptr || g_free_callback != nullptr);
	EXIT_IF(alloc_func == nullptr || free_func == nullptr);

	bc5::load_stat::CountedLock<std::recursive_mutex> memory_operation_lock(g_memory_operation_mutex, bc5::load_stat::kMemLockWait); // exp 0415 (ls415): a lock_guard with the wait counted

	g_alloc_callback = alloc_func;
	g_free_callback  = free_func;

	g_physical_memory->GetMutex().Lock();
	for (const auto& b: g_physical_memory->GetMappings()) {
		if (b.map_vaddr != 0 && b.map_size != 0) {
			g_alloc_callback(b.map_vaddr, b.map_size);
		}
	}
	g_physical_memory->GetMutex().Unlock();

	g_flexible_memory->GetMutex().Lock();
	for (const auto& b: g_flexible_memory->GetBlocks()) {
		g_alloc_callback(b.map_vaddr, b.map_size);
	}
	g_flexible_memory->GetMutex().Unlock();

	for (const auto& mapping: g_pooled_memory->GetMappings()) {
		g_alloc_callback(mapping.vaddr, mapping.size);
	}
}

void SetFlexibleMemorySize(uint64_t size) {
	constexpr uint64_t GuestPageSize = 0x4000;
	EXIT_IF(g_flexible_memory_size_frozen || g_guest_address_space != nullptr);
	EXIT_IF(size == 0 || (size & (GuestPageSize - 1u)) != 0 || size >= PhysicalMemory::TotalSize());
	g_flexible_memory_size = size;
	LOGF("\t flexible memory size = 0x%016" PRIx64 " (%" PRIu64 " MiB)\n", size,
	     size / (1024ull * 1024ull));
}

bool PhysicalMemory::Alloc(uint64_t search_start, uint64_t search_end, size_t len, size_t alignment,
                           uint64_t* phys_addr_out, int memory_type, bool pool_expansion) {
	if (phys_addr_out == nullptr) {
		return false;
	}

	Common::LockGuard lock(m_mutex);

	search_end = std::min<uint64_t>(search_end, Size());
	if (search_start >= search_end) {
		return false;
	}

	auto range = m_free.upper_bound(search_start);
	if (range != m_free.begin()) {
		range--;
	}
	for (; range != m_free.end() && range->first < search_end; ++range) {
		const auto range_end   = std::min<uint64_t>(range->first + range->second, search_end);
		const auto lower_bound = std::max(range->first, search_start);
		const auto aligned     = GetAlignedPos(lower_bound, alignment);
		const auto free_pos    = aligned.value;
		if (!aligned.valid || free_pos < lower_bound || free_pos > range_end ||
		    len > range_end - free_pos) {
			continue;
		}

		AllocatedBlock b {};
		b.size           = len;
		b.start_addr     = free_pos;
		b.gpu_mode       = GpuAccessMode::NoAccess;
		b.map_size       = 0;
		b.map_vaddr      = 0;
		b.prot           = 0;
		b.mode           = VirtualMemory::Mode::NoAccess;
		b.memory_type    = memory_type;
		b.pool_expansion = pool_expansion;

		ConsumeFreeRange(range, free_pos, len);
		EXIT_IF(!m_physical.emplace(b.start_addr, b).second);

		*phys_addr_out = free_pos;
		return true;
	}

	return false;
}

bool PhysicalMemory::Available(uint64_t search_start, uint64_t search_end, size_t alignment,
                               uint64_t* phys_addr_out, uint64_t* size_out) {
	if (phys_addr_out == nullptr || size_out == nullptr) {
		return false;
	}

	Common::LockGuard lock(m_mutex);

	search_end = std::min<uint64_t>(search_end, Size());
	if (search_start >= search_end) {
		return false;
	}

	uint64_t best_addr = 0;
	uint64_t best_size = 0;

	for (const auto& [range_start, range_size]: m_free) {
		if (range_start >= search_end) {
			break;
		}
		const auto range_end   = std::min<uint64_t>(range_start + range_size, search_end);
		const auto lower_bound = std::max(range_start, search_start);
		const auto aligned     = GetAlignedPos(lower_bound, alignment);
		const auto free_pos    = aligned.value;
		if (aligned.valid && free_pos >= lower_bound && free_pos < range_end &&
		    range_end - free_pos > best_size) {
			best_addr = free_pos;
			best_size = range_end - free_pos;
		}
	}

	if (best_size == 0) {
		return false;
	}

	*phys_addr_out = best_addr;
	*size_out      = best_size;
	return true;
}

void PhysicalMemory::ConsumeFreeRange(std::map<uint64_t, uint64_t>::iterator range, uint64_t start,
                                      uint64_t size) {
	const auto range_start = range->first;
	const auto range_end   = range->first + range->second;
	m_free.erase(range);
	if (range_start < start) {
		m_free.emplace(range_start, start - range_start);
	}
	if (start + size < range_end) {
		m_free.emplace(start + size, range_end - start - size);
	}
}

void PhysicalMemory::AddFreeRange(uint64_t start, uint64_t size) {
	auto end  = start + size;
	auto next = m_free.lower_bound(start);
	if (next != m_free.begin()) {
		auto previous = std::prev(next);
		if (previous->first + previous->second >= start) {
			start = previous->first;
			end   = std::max(end, previous->first + previous->second);
			next  = m_free.erase(previous);
		}
	}
	while (next != m_free.end() && next->first <= end) {
		end  = std::max(end, next->first + next->second);
		next = m_free.erase(next);
	}
	m_free.emplace(start, end - start);
}

bool PhysicalMemory::Release(uint64_t start, size_t len, uint64_t* vaddr, uint64_t* size,
                             GpuAccessMode* gpu_mode) {
	EXIT_IF(vaddr == nullptr);
	EXIT_IF(size == nullptr);
	EXIT_IF(gpu_mode == nullptr);

	Common::LockGuard lock(m_mutex);

	auto next = m_physical.upper_bound(start);
	if (next == m_physical.begin()) {
		return false;
	}
	auto  it = std::prev(next);
	auto& b  = it->second;
	if (b.pool_expansion || start < b.start_addr || start >= b.start_addr + b.size ||
	    len > b.start_addr + b.size - start) {
		return false;
	}

	if (start == b.start_addr && len == b.size) {
		*vaddr    = b.map_vaddr;
		*size     = b.map_size;
		*gpu_mode = b.gpu_mode;

		m_physical.erase(it);
		AddFreeRange(start, len);
		return true;
	}
	if (start > b.start_addr && start + len < b.start_addr + b.size) {
		auto old_start = b.start_addr;
		auto old_end   = b.start_addr + b.size;

		*vaddr    = (b.map_vaddr != 0 ? b.map_vaddr + (start - old_start) : 0);
		*size     = (b.map_vaddr != 0 ? len : 0);
		*gpu_mode = b.gpu_mode;

		AllocatedBlock right = b;
		right.start_addr     = start + len;
		right.size           = old_end - right.start_addr;
		if (right.map_vaddr != 0) {
			right.map_vaddr += right.start_addr - old_start;
			right.map_size = right.size;
		}

		b.size = start - old_start;
		if (b.map_vaddr != 0) {
			b.map_size = b.size;
		}

		m_physical.emplace(right.start_addr, right);
		AddFreeRange(start, len);
		return true;
	}
	if (start == b.start_addr && len < b.size) {
		*vaddr    = b.map_vaddr;
		*size     = (b.map_vaddr != 0 ? len : 0);
		*gpu_mode = b.gpu_mode;

		AllocatedBlock remaining = b;
		m_physical.erase(it);
		remaining.start_addr += len;
		remaining.size -= len;
		if (remaining.map_vaddr != 0) {
			remaining.map_vaddr += len;
			remaining.map_size -= len;
		}
		m_physical.emplace(remaining.start_addr, remaining);
		AddFreeRange(start, len);
		return true;
	}
	if (start > b.start_addr && start + len == b.start_addr + b.size) {
		*vaddr    = (b.map_vaddr != 0 ? b.map_vaddr + (start - b.start_addr) : 0);
		*size     = (b.map_vaddr != 0 ? len : 0);
		*gpu_mode = b.gpu_mode;

		b.size = start - b.start_addr;
		if (b.map_vaddr != 0) {
			b.map_size = b.size;
		}
		AddFreeRange(start, len);
		return true;
	}

	return false;
}

bool PhysicalMemory::Map(uint64_t vaddr, uint64_t phys_addr, size_t len, int prot,
                         VirtualMemory::Mode mode, GpuAccessMode gpu_mode) {
	Common::LockGuard lock(m_mutex);

	if (len == 0 || UINT64_MAX - phys_addr < len) {
		return false;
	}

	auto current = phys_addr;
	auto next    = m_physical.upper_bound(current);
	if (next == m_physical.begin()) {
		return false;
	}
	auto first = std::prev(next);
	while (current < phys_addr + len) {
		auto block = m_physical.upper_bound(current);
		if (block == m_physical.begin()) {
			return false;
		}
		--block;
		const auto block_end = block->second.start_addr + block->second.size;
		if (block->second.pool_expansion || current < block->second.start_addr ||
		    current >= block_end) {
			return false;
		}
		current = std::min<uint64_t>(phys_addr + len, block_end);
		if (current < phys_addr + len) {
			const auto following = std::next(block);
			if (following == m_physical.end() || following->second.start_addr != current) {
				return false;
			}
		}
	}

	AllocatedBlock mapping = first->second;
	mapping.start_addr     = phys_addr;
	mapping.size           = len;
	mapping.map_vaddr      = vaddr;
	mapping.map_size       = len;
	mapping.host_vaddr     = vaddr;
	mapping.host_size      = len;
	mapping.prot           = prot;
	mapping.mode           = mode;
	mapping.gpu_mode       = gpu_mode;
	{ // Experiment 0412 (tag pm412, mkphys0412.py): KYTY_BC5_PHYSMAP_CHECK=1 counts the blocks that overlap one already in the table
		static const bool check412 = [] {
			const char* e = BC5_DIAG_ENV("KYTY_BC5_PHYSMAP_CHECK");
			return e != nullptr && e[0] != 0 && !(e[0] == '0' && e[1] == 0);
		}();
		if (check412) {
			static uint64_t inserts412 = 0, overlaps412 = 0;
			inserts412++;
			for (const auto& b412: m_mappings) {
				if (VirtualRangesOverlap(mapping.map_vaddr, mapping.map_size, b412.map_vaddr, b412.map_size)) {
					if (overlaps412++ < 8) {
						std::fprintf(stderr, "[bc5] exp 0412 physmap check: new block 0x%" PRIx64 "+0x%" PRIx64 " overlaps 0x%" PRIx64 "+0x%" PRIx64 "\n",
						             mapping.map_vaddr, mapping.map_size, b412.map_vaddr, b412.map_size);
					}
					break;
				}
			}
			if ((inserts412 & (inserts412 - 1)) == 0 || inserts412 % 100000 == 0) {
				std::fprintf(stderr, "[bc5] exp 0412 physmap check: %" PRIu64 " blocks added, %" PRIu64 " overlapped an existing one, table %zu (tag pm412)\n",
				             inserts412, overlaps412, m_mappings.size());
			}
		}
	}
	if (Pm412Mode() != 0 && g_pm412_ok) { // exp 0412 (tag ps412): the table stays sorted by guest address
		if (!pm412::insert(m_mappings, mapping)) {
			g_pm412_ok = false;
			std::fprintf(stderr, "[bc5] exp 0412 physmap sorted: block 0x%" PRIx64 "+0x%" PRIx64 " overlaps another, is empty or wraps: the old table code from here on (tag ps412)\n",
			             mapping.map_vaddr, mapping.map_size);
			m_mappings.push_back(mapping);
		}
	} else {
		m_mappings.push_back(mapping);
	}

	return true;
}

bool PhysicalMemory::CanMapDirect(uint64_t phys_addr, size_t len) {
	Common::LockGuard lock(m_mutex);

	if (len == 0 || UINT64_MAX - phys_addr < len) {
		return false;
	}

	const auto end     = phys_addr + len;
	auto       current = phys_addr;
	while (current < end) {
		auto block = m_physical.upper_bound(current);
		if (block == m_physical.begin()) {
			return false;
		}
		--block;
		const auto block_end = block->second.start_addr + block->second.size;
		if (block->second.pool_expansion || current < block->second.start_addr ||
		    current >= block_end) {
			return false;
		}
		current = std::min(end, block_end);
		if (current < end) {
			const auto following = std::next(block);
			if (following == m_physical.end() || following->second.start_addr != current) {
				return false;
			}
		}
	}
	return true;
}

bool PhysicalMemory::ReleasePoolExpansion(uint64_t phys_addr, size_t len) {
	Common::LockGuard lock(m_mutex);
	const auto        it = m_physical.find(phys_addr);
	if (it == m_physical.end() || !it->second.pool_expansion || it->second.size != len) {
		return false;
	}
	m_physical.erase(it);
	AddFreeRange(phys_addr, len);
	return true;
}

bool PhysicalMemory::GetAllocatedSpan(uint64_t phys_addr, size_t len,
                                      std::vector<AllocatedBlock>* blocks) {
	EXIT_IF(blocks == nullptr);
	blocks->clear();
	if (len == 0 || UINT64_MAX - phys_addr < len) {
		return false;
	}

	Common::LockGuard lock(m_mutex);
	const auto        end     = phys_addr + len;
	auto              current = phys_addr;
	while (current < end) {
		auto block = m_physical.upper_bound(current);
		if (block == m_physical.begin()) {
			blocks->clear();
			return false;
		}
		--block;
		const auto block_end = block->second.start_addr + block->second.size;
		if (block->second.pool_expansion || current < block->second.start_addr ||
		    current >= block_end) {
			blocks->clear();
			return false;
		}

		auto part       = block->second;
		part.start_addr = current;
		part.size       = std::min(end, block_end) - current;
		blocks->push_back(part);
		current += part.size;
		if (current < end) {
			const auto following = std::next(block);
			if (following == m_physical.end() || following->second.start_addr != current) {
				blocks->clear();
				return false;
			}
		}
	}
	return true;
}

bool PhysicalMemory::Unmap(uint64_t vaddr, uint64_t size, GpuAccessMode* gpu_mode,
                           uint64_t* host_vaddr_to_release) {
#if defined(KYTY_VIRTUAL_MEMORY_ALLOCATION_TESTS)
	if (g_test_physical_memory_unmaps_before_failure == 0) {
		g_test_physical_memory_unmaps_before_failure = UINT32_MAX;
		return false;
	}
	if (g_test_physical_memory_unmaps_before_failure != UINT32_MAX) {
		g_test_physical_memory_unmaps_before_failure--;
	}
#endif

	EXIT_IF(gpu_mode == nullptr);

	Common::LockGuard lock(m_mutex);

	if (host_vaddr_to_release != nullptr) {
		*host_vaddr_to_release = 0;
	}

	auto set_host_release_if_last = [this, host_vaddr_to_release](uint64_t host_vaddr,
	                                                              uint64_t host_size) {
		if (host_vaddr_to_release == nullptr || host_vaddr == 0 || host_size == 0) {
			return;
		}
		const bool still_mapped = std::any_of(
		    m_mappings.begin(), m_mappings.end(), [host_vaddr, host_size](const auto& block) {
			    return block.host_vaddr == host_vaddr && block.host_size == host_size;
		    });
		if (!still_mapped) {
			*host_vaddr_to_release = host_vaddr;
		}
	};

	// Experiment 0412 (tag ps412): the old walk below can append the right half of a split block; when it runs in the
	// sorted mode (an empty range, or a verify difference) the table is sorted again on the way out.
	struct Pm412Resort {
		std::vector<AllocatedBlock>* v = nullptr;
		~Pm412Resort() {
			if (v != nullptr) {
				std::stable_sort(v->begin(), v->end(), [](const AllocatedBlock& x, const AllocatedBlock& y) { return x.map_vaddr < y.map_vaddr; });
			}
		}
	} resort412;
	if (Pm412Mode() != 0 && g_pm412_ok) {
		bool fast412 = size != 0;
		if (fast412 && Pm412Mode() == 2 && pm412::linear_first(m_mappings, vaddr, size) != pm412::candidate(m_mappings, vaddr, size)) {
			fast412 = false;
			if (g_pm412_mismatch++ < 8) {
				std::fprintf(stderr, "[bc5] exp 0412 physmap sorted: verify: Unmap 0x%" PRIx64 "+0x%" PRIx64 ": the old search finds another block (tag ps412)\n", vaddr, size);
			}
		}
		if (fast412) {
			uint64_t         hv412 = 0, hs412 = 0;
			const pm412::Hit hit412 = pm412::unmap(m_mappings, vaddr, size, gpu_mode, &hv412, &hs412);
			if (hit412 == pm412::Whole && host_vaddr_to_release != nullptr && hv412 != 0 && hs412 != 0 && !pm412::host_still_mapped(m_mappings, hv412, hs412)) {
				*host_vaddr_to_release = hv412;
			}
			return hit412 != pm412::None;
		}
		resort412.v = &m_mappings;
	}
	size_t index = 0;
	for (auto& b: m_mappings) {
		if (b.map_vaddr == vaddr && b.map_size == size) {
			*gpu_mode             = b.gpu_mode;
			const auto host_vaddr = b.host_vaddr;
			const auto host_size  = b.host_size;

			m_mappings.erase(m_mappings.begin() + static_cast<std::ptrdiff_t>(index));
			set_host_release_if_last(host_vaddr, host_size);

			return true;
		}
		if (vaddr > b.map_vaddr && vaddr + size < b.map_vaddr + b.map_size) {
			*gpu_mode = b.gpu_mode;

			AllocatedBlock right = b;
			right.start_addr += (vaddr + size) - b.map_vaddr;
			right.size      = b.map_vaddr + b.map_size - (vaddr + size);
			right.map_size  = right.size;
			right.map_vaddr = vaddr + size;

			b.size     = vaddr - b.map_vaddr;
			b.map_size = b.size;
			m_mappings.push_back(right);
			return true;
		}
		if (vaddr == b.map_vaddr && size < b.map_size) {
			*gpu_mode = b.gpu_mode;

			b.start_addr += size;
			b.size -= size;
			b.map_vaddr += size;
			b.map_size -= size;
			return true;
		}
		if (vaddr > b.map_vaddr && vaddr + size == b.map_vaddr + b.map_size) {
			*gpu_mode = b.gpu_mode;

			b.size     = vaddr - b.map_vaddr;
			b.map_size = b.size;
			return true;
		}
		index++;
	}

	return false;
}

void PhysicalMemory::ProtectMapping(uint64_t vaddr, uint64_t size, int prot,
                                    VirtualMemory::Mode mode, GpuAccessMode gpu_mode) {
	Common::LockGuard lock(m_mutex);
	if (size == 0 || UINT64_MAX - vaddr < size) {
		return;
	}

	const auto                  end = vaddr + size;
	std::vector<AllocatedBlock> updated;
	updated.reserve(m_mappings.size() + 2);
	for (const auto& block: m_mappings) {
		const auto block_end = block.map_vaddr + block.map_size;
		if (!VirtualRangesOverlap(vaddr, size, block.map_vaddr, block.map_size)) {
			updated.push_back(block);
			continue;
		}
		const auto overlap_start = std::max(vaddr, block.map_vaddr);
		const auto overlap_end   = std::min(end, block_end);
		if (block.map_vaddr < overlap_start) {
			auto left     = block;
			left.size     = overlap_start - block.map_vaddr;
			left.map_size = left.size;
			updated.push_back(left);
		}
		auto middle       = block;
		middle.start_addr = block.start_addr + overlap_start - block.map_vaddr;
		middle.size       = overlap_end - overlap_start;
		middle.map_vaddr  = overlap_start;
		middle.map_size   = middle.size;
		middle.prot       = prot;
		middle.mode       = mode;
		middle.gpu_mode   = gpu_mode;
		updated.push_back(middle);
		if (overlap_end < block_end) {
			auto right       = block;
			right.start_addr = block.start_addr + overlap_end - block.map_vaddr;
			right.size       = block_end - overlap_end;
			right.map_vaddr  = overlap_end;
			right.map_size   = right.size;
			updated.push_back(right);
		}
	}
	m_mappings = std::move(updated);
}

bool PhysicalMemory::Find(uint64_t phys_addr, bool next, AllocatedBlock* out) {
	EXIT_IF(out == nullptr);

	Common::LockGuard lock(m_mutex);

	auto following = m_physical.upper_bound(phys_addr);
	if (following != m_physical.begin()) {
		const auto& block = std::prev(following)->second;
		if (phys_addr < block.start_addr + block.size) {
			*out = block;
			return true;
		}
	}

	if (next && following != m_physical.end()) {
		*out = following->second;
		return true;
	}

	return false;
}

std::vector<PhysicalMemory::AllocatedBlock> PhysicalMemory::FindMappings(uint64_t phys_addr,
                                                                         size_t   len) {
	Common::LockGuard lock(m_mutex);

	std::vector<AllocatedBlock> mappings;
	for (const auto& m: m_mappings) {
		if (!VirtualRangesOverlap(phys_addr, len, m.start_addr, m.size)) {
			continue;
		}

		const uint64_t overlap_start = std::max<uint64_t>(phys_addr, m.start_addr);
		const uint64_t overlap_end   = std::min<uint64_t>(phys_addr + len, m.start_addr + m.size);
		AllocatedBlock part          = m;
		part.start_addr              = overlap_start;
		part.size                    = overlap_end - overlap_start;
		part.map_vaddr += overlap_start - m.start_addr;
		part.map_size = part.size;
		mappings.push_back(part);
	}

	std::sort(mappings.begin(), mappings.end(),
	          [](const auto& a, const auto& b) { return a.map_vaddr < b.map_vaddr; });
	return mappings;
}

bool PhysicalMemory::Find(uint64_t vaddr, uint64_t* base_addr, size_t* len, int* prot,
                          VirtualMemory::Mode* mode, GpuAccessMode* gpu_mode) {
	Common::LockGuard lock(m_mutex);

	if (Pm412Mode() != 0 && g_pm412_ok) { // exp 0412 (tag ps412): the block that holds vaddr, by binary search
		const auto it412 = pm412::containing(m_mappings, vaddr);
		if (it412 == m_mappings.end()) {
			return false;
		}
		if (base_addr != nullptr) *base_addr = it412->map_vaddr;
		if (len != nullptr) *len = it412->map_size;
		if (prot != nullptr) *prot = it412->prot;
		if (mode != nullptr) *mode = it412->mode;
		if (gpu_mode != nullptr) *gpu_mode = it412->gpu_mode;
		return true;
	}
	return std::any_of(m_mappings.begin(), m_mappings.end(),
	                   [vaddr, base_addr, len, prot, mode, gpu_mode](auto& b) {
		                   if (vaddr >= b.map_vaddr && vaddr < b.map_vaddr + b.map_size) {
			                   if (base_addr != nullptr) {
				                   *base_addr = b.map_vaddr;
			                   }
			                   if (len != nullptr) {
				                   *len = b.map_size;
			                   }
			                   if (prot != nullptr) {
				                   *prot = b.prot;
			                   }
			                   if (mode != nullptr) {
				                   *mode = b.mode;
			                   }
			                   if (gpu_mode != nullptr) {
				                   *gpu_mode = b.gpu_mode;
			                   }

			                   return true;
		                   }
		                   return false;
	                   });
}

void PhysicalMemory::SetVirtualRangeName(uint64_t vaddr, uint64_t len, const char* name) {
	Common::LockGuard lock(m_mutex);

	if (Pm412Mode() != 0 && g_pm412_ok) { // exp 0412 (tag ps412): only the blocks around the range, the same overlap test
		for (auto it412 = pm412::walk_from(m_mappings, vaddr); it412 != m_mappings.end(); ++it412) {
			if (it412->map_vaddr > vaddr && it412->map_vaddr - vaddr >= len) break;
			if (VirtualRangesOverlap(vaddr, len, it412->map_vaddr, it412->map_size)) CopyVirtualRangeName(it412->name, name);
		}
		return;
	}
	for (auto& b: m_mappings) {
		if (VirtualRangesOverlap(vaddr, len, b.map_vaddr, b.map_size)) {
			CopyVirtualRangeName(b.name, name);
		}
	}
}

bool FlexibleMemory::Map(uint64_t vaddr, size_t len, int prot, VirtualMemory::Mode mode,
                         GpuAccessMode gpu_mode, const char* name) {
	Common::LockGuard lock(m_mutex);

	const auto available = (Size() >= m_allocated_total ? Size() - m_allocated_total : 0);
	if (len == 0 || len > available) {
		LOGF_COLOR(Log::Color::Red,
		           "\t flexible memory exhausted: configured = 0x%016" PRIx64
		           ", allocated = 0x%016" PRIx64 ", available = 0x%016" PRIx64
		           ", requested = 0x%016" PRIx64 "\n",
		           Size(), m_allocated_total, available, static_cast<uint64_t>(len));
		return false;
	}

	std::vector<AllocatedBlock> blocks;
	auto                        current   = vaddr;
	auto                        remaining = static_cast<uint64_t>(len);
	for (const auto& [backing_offset, free_size]: m_free) {
		if (remaining == 0) {
			break;
		}
		const auto     chunk = std::min(remaining, free_size);
		AllocatedBlock block {};
		block.map_vaddr      = current;
		block.map_size       = chunk;
		block.backing_offset = backing_offset;
		block.host_vaddr     = vaddr;
		block.host_size      = len;
		block.prot           = prot;
		block.mode           = mode;
		block.gpu_mode       = gpu_mode;
		CopyVirtualRangeName(block.name, name);
		blocks.push_back(block);
		current += chunk;
		remaining -= chunk;
	}
	if (remaining != 0) {
		return false;
	}

	std::vector<AllocatedBlock> mapped;
	for (const auto& block: blocks) {
		if (!g_guest_address_space->ZeroBacking(block.backing_offset, block.map_size)) {
			for (auto it = mapped.rbegin(); it != mapped.rend(); ++it) {
				EXIT_IF(!g_guest_address_space->UnmapBacking(it->map_vaddr, it->map_size));
			}
			return false;
		}
		if (!g_guest_address_space->MapBacking(block.map_vaddr, block.map_size,
		                                       block.backing_offset, block.mode)) {
			for (auto it = mapped.rbegin(); it != mapped.rend(); ++it) {
				EXIT_IF(!g_guest_address_space->UnmapBacking(it->map_vaddr, it->map_size));
			}
			return false;
		}
		mapped.push_back(block);
	}

	for (const auto& block: blocks) {
		auto next = m_free.upper_bound(block.backing_offset);
		EXIT_IF(next == m_free.begin());
		auto range = std::prev(next);
		EXIT_IF(block.backing_offset < range->first ||
		        block.map_size > range->first + range->second - block.backing_offset);
		ConsumeFreeRange(range, block.backing_offset, block.map_size);
		m_allocated.push_back(block);
	}
	std::sort(m_allocated.begin(), m_allocated.end(),
	          [](const auto& left, const auto& right) { return left.map_vaddr < right.map_vaddr; });
	m_allocated_total += len;

	return true;
}

bool FlexibleMemory::Unmap(uint64_t vaddr, uint64_t size, GpuAccessMode* gpu_mode,
                           uint64_t* host_vaddr_to_release) {
	EXIT_IF(gpu_mode == nullptr);

	Common::LockGuard lock(m_mutex);

	if (host_vaddr_to_release != nullptr) {
		*host_vaddr_to_release = 0;
	}
	if (size == 0 || UINT64_MAX - vaddr < size) {
		return false;
	}

	const auto end     = vaddr + size;
	auto       current = vaddr;
	bool       found   = false;
	for (const auto& block: m_allocated) {
		if (block.map_vaddr + block.map_size <= current) {
			continue;
		}
		if (block.map_vaddr > current || block.map_vaddr >= end) {
			break;
		}
		if (!found) {
			*gpu_mode = block.gpu_mode;
			found     = true;
		}
		current = std::min(end, block.map_vaddr + block.map_size);
		if (current == end) {
			break;
		}
	}
	if (!found || current != end || !g_guest_address_space->UnmapBacking(vaddr, size)) {
		return false;
	}

	std::vector<AllocatedBlock> remaining;
	remaining.reserve(m_allocated.size() + 1);
	uint64_t removed = 0;
	for (const auto& block: m_allocated) {
		const auto block_end = block.map_vaddr + block.map_size;
		if (!VirtualRangesOverlap(vaddr, size, block.map_vaddr, block.map_size)) {
			remaining.push_back(block);
			continue;
		}
		const auto overlap_start = std::max(vaddr, block.map_vaddr);
		const auto overlap_end   = std::min(end, block_end);
		const auto overlap_size  = overlap_end - overlap_start;
		AddFreeRange(block.backing_offset + overlap_start - block.map_vaddr, overlap_size);
		removed += overlap_size;

		if (block.map_vaddr < overlap_start) {
			auto left     = block;
			left.map_size = overlap_start - block.map_vaddr;
			remaining.push_back(left);
		}
		if (overlap_end < block_end) {
			auto right           = block;
			right.map_vaddr      = overlap_end;
			right.map_size       = block_end - overlap_end;
			right.backing_offset = block.backing_offset + overlap_end - block.map_vaddr;
			remaining.push_back(right);
		}
	}
	EXIT_IF(removed != size || removed > m_allocated_total);
	m_allocated = std::move(remaining);
	m_allocated_total -= removed;
	return true;
}

void FlexibleMemory::ConsumeFreeRange(std::map<uint64_t, uint64_t>::iterator range, uint64_t start,
                                      uint64_t size) {
	const auto range_start = range->first;
	const auto range_end   = range->first + range->second;
	m_free.erase(range);
	if (range_start < start) {
		m_free.emplace(range_start, start - range_start);
	}
	if (start + size < range_end) {
		m_free.emplace(start + size, range_end - start - size);
	}
}

void FlexibleMemory::AddFreeRange(uint64_t start, uint64_t size) {
	auto end  = start + size;
	auto next = m_free.lower_bound(start);
	if (next != m_free.begin()) {
		auto previous = std::prev(next);
		if (previous->first + previous->second >= start) {
			start = previous->first;
			end   = std::max(end, previous->first + previous->second);
			next  = m_free.erase(previous);
		}
	}
	while (next != m_free.end() && next->first <= end) {
		end  = std::max(end, next->first + next->second);
		next = m_free.erase(next);
	}
	m_free.emplace(start, end - start);
}

bool FlexibleMemory::Snapshot(uint64_t vaddr, uint64_t size, std::vector<AllocatedBlock>* blocks) {
	EXIT_IF(blocks == nullptr);
	Common::LockGuard lock(m_mutex);
	blocks->clear();
	if (size == 0 || UINT64_MAX - vaddr < size) {
		return false;
	}

	const auto end     = vaddr + size;
	auto       current = vaddr;
	for (const auto& block: m_allocated) {
		const auto block_end = block.map_vaddr + block.map_size;
		if (block_end <= current) {
			continue;
		}
		if (block.map_vaddr > current || block.map_vaddr >= end) {
			break;
		}
		const auto part_end = std::min(end, block_end);
		auto       part     = block;
		part.map_vaddr      = current;
		part.map_size       = part_end - current;
		part.backing_offset += current - block.map_vaddr;
		blocks->push_back(part);
		current = part_end;
		if (current == end) {
			return true;
		}
	}
	blocks->clear();
	return false;
}

bool FlexibleMemory::Restore(const std::vector<AllocatedBlock>& blocks) {
	Common::LockGuard lock(m_mutex);
	if (blocks.empty()) {
		return false;
	}

	for (const auto& block: blocks) {
		auto next = m_free.upper_bound(block.backing_offset);
		if (next == m_free.begin()) {
			return false;
		}
		const auto range = std::prev(next);
		if (block.backing_offset < range->first ||
		    block.map_size > range->first + range->second - block.backing_offset) {
			return false;
		}
	}

	std::vector<AllocatedBlock> mapped;
	for (const auto& block: blocks) {
		if (!g_guest_address_space->MapBacking(block.map_vaddr, block.map_size,
		                                       block.backing_offset, block.mode)) {
			for (auto it = mapped.rbegin(); it != mapped.rend(); ++it) {
				EXIT_IF(!g_guest_address_space->UnmapBacking(it->map_vaddr, it->map_size));
			}
			return false;
		}
		mapped.push_back(block);
	}

	for (const auto& block: blocks) {
		auto next = m_free.upper_bound(block.backing_offset);
		EXIT_IF(next == m_free.begin());
		auto range = std::prev(next);
		ConsumeFreeRange(range, block.backing_offset, block.map_size);
		m_allocated.push_back(block);
		m_allocated_total += block.map_size;
	}
	std::sort(m_allocated.begin(), m_allocated.end(),
	          [](const auto& left, const auto& right) { return left.map_vaddr < right.map_vaddr; });
	return true;
}

void FlexibleMemory::Protect(uint64_t vaddr, uint64_t size, int prot, VirtualMemory::Mode mode,
                             GpuAccessMode gpu_mode) {
	Common::LockGuard lock(m_mutex);
	if (size == 0 || UINT64_MAX - vaddr < size) {
		return;
	}

	const auto                  end = vaddr + size;
	std::vector<AllocatedBlock> updated;
	updated.reserve(m_allocated.size() + 2);
	for (const auto& block: m_allocated) {
		const auto block_end = block.map_vaddr + block.map_size;
		if (!VirtualRangesOverlap(vaddr, size, block.map_vaddr, block.map_size)) {
			updated.push_back(block);
			continue;
		}
		const auto overlap_start = std::max(vaddr, block.map_vaddr);
		const auto overlap_end   = std::min(end, block_end);
		if (block.map_vaddr < overlap_start) {
			auto left     = block;
			left.map_size = overlap_start - block.map_vaddr;
			updated.push_back(left);
		}
		auto middle           = block;
		middle.map_vaddr      = overlap_start;
		middle.map_size       = overlap_end - overlap_start;
		middle.backing_offset = block.backing_offset + overlap_start - block.map_vaddr;
		middle.prot           = prot;
		middle.mode           = mode;
		middle.gpu_mode       = gpu_mode;
		updated.push_back(middle);
		if (overlap_end < block_end) {
			auto right           = block;
			right.map_vaddr      = overlap_end;
			right.map_size       = block_end - overlap_end;
			right.backing_offset = block.backing_offset + overlap_end - block.map_vaddr;
			updated.push_back(right);
		}
	}
	m_allocated = std::move(updated);
}

bool FlexibleMemory::Find(uint64_t vaddr, uint64_t* base_addr, size_t* len, int* prot,
                          VirtualMemory::Mode* mode, GpuAccessMode* gpu_mode) {
	Common::LockGuard lock(m_mutex);

	return std::any_of(m_allocated.begin(), m_allocated.end(),
	                   [vaddr, base_addr, len, prot, mode, gpu_mode](auto& b) {
		                   if (vaddr >= b.map_vaddr && vaddr < b.map_vaddr + b.map_size) {
			                   if (base_addr != nullptr) {
				                   *base_addr = b.map_vaddr;
			                   }
			                   if (len != nullptr) {
				                   *len = b.map_size;
			                   }
			                   if (prot != nullptr) {
				                   *prot = b.prot;
			                   }
			                   if (mode != nullptr) {
				                   *mode = b.mode;
			                   }
			                   if (gpu_mode != nullptr) {
				                   *gpu_mode = b.gpu_mode;
			                   }

			                   return true;
		                   }
		                   return false;
	                   });
}

void FlexibleMemory::SetVirtualRangeName(uint64_t vaddr, uint64_t len, const char* name) {
	Common::LockGuard lock(m_mutex);

	for (auto& b: m_allocated) {
		if (VirtualRangesOverlap(vaddr, len, b.map_vaddr, b.map_size)) {
			CopyVirtualRangeName(b.name, name);
		}
	}
}

void PhysicalMemory::SetVirtualRangeMemoryType(uint64_t vaddr, uint64_t len, int memory_type) {
	Common::LockGuard lock(m_mutex);

	if (Pm412Mode() != 0 && g_pm412_ok) { // exp 0412 (tag ps412): only the blocks around the range, the same overlap test
		for (auto it412 = pm412::walk_from(m_mappings, vaddr); it412 != m_mappings.end(); ++it412) {
			if (it412->map_vaddr > vaddr && it412->map_vaddr - vaddr >= len) break;
			if (VirtualRangesOverlap(vaddr, len, it412->map_vaddr, it412->map_size)) it412->memory_type = memory_type;
		}
		return;
	}
	for (auto& b: m_mappings) {
		if (VirtualRangesOverlap(vaddr, len, b.map_vaddr, b.map_size)) {
			b.memory_type = memory_type;
		}
	}
}

uint64_t FlexibleMemory::Available() {
	Common::LockGuard lock(m_mutex);

	return (Size() >= m_allocated_total ? Size() - m_allocated_total : 0);
}

void PooledMemory::AddFreeUnlocked(uint64_t start, uint64_t size) {
	if (size == 0) {
		return;
	}

	m_free.push_back({start, size});
	std::sort(m_free.begin(), m_free.end(),
	          [](const auto& left, const auto& right) { return left.start < right.start; });

	std::vector<PhysicalRange> merged;
	for (const auto& range: m_free) {
		if (!merged.empty() && range.start <= merged.back().start + merged.back().size) {
			const auto end =
			    std::max(merged.back().start + merged.back().size, range.start + range.size);
			merged.back().size = end - merged.back().start;
		} else {
			merged.push_back(range);
		}
	}
	m_free = std::move(merged);
}

void PooledMemory::Expand(uint64_t phys_addr, uint64_t size) {
	Common::LockGuard lock(m_mutex);
	m_expansions.push_back({phys_addr, size});
	AddFreeUnlocked(phys_addr, size);
}

bool PooledMemory::ReleaseExpansion(uint64_t phys_addr, uint64_t size) {
	Common::LockGuard lock(m_mutex);
	const auto        expansion = std::find_if(m_expansions.begin(), m_expansions.end(),
	                                           [phys_addr, size](const auto& range) {
		                                    return range.start == phys_addr && range.size == size;
	                                           });
	if (expansion == m_expansions.end()) {
		return false;
	}
	if (std::any_of(m_mappings.begin(), m_mappings.end(), [phys_addr, size](const auto& mapping) {
		    return VirtualRangesOverlap(phys_addr, size, mapping.phys_addr, mapping.size);
	    })) {
		return false;
	}

	const auto end = phys_addr + size;
	const auto free_range =
	    std::find_if(m_free.begin(), m_free.end(), [phys_addr, end](const auto& r) {
		    return phys_addr >= r.start && end <= r.start + r.size;
	    });
	if (free_range == m_free.end()) {
		return false;
	}

	const auto old        = *free_range;
	const auto old_end    = old.start + old.size;
	const auto left_size  = phys_addr - old.start;
	const auto right_size = old_end - end;
	m_free.erase(free_range);
	if (left_size != 0) {
		m_free.push_back({old.start, left_size});
	}
	if (right_size != 0) {
		m_free.push_back({end, right_size});
	}
	std::sort(m_free.begin(), m_free.end(),
	          [](const auto& left, const auto& right) { return left.start < right.start; });
	m_expansions.erase(expansion);
	return true;
}

bool PooledMemory::Allocate(uint64_t vaddr, uint64_t size, GpuAccessMode gpu_mode,
                            std::vector<Mapping>* mappings) {
	EXIT_IF(mappings == nullptr);
	mappings->clear();
	if (vaddr == 0 || size == 0 || UINT64_MAX - vaddr < size) {
		return false;
	}

	Common::LockGuard lock(m_mutex);
	auto              free      = m_free;
	auto              current   = vaddr;
	auto              remaining = size;
	for (auto& range: free) {
		if (remaining == 0 || range.size == 0) {
			continue;
		}
		const auto part_size = std::min(range.size, remaining);
		mappings->push_back({current, part_size, range.start, gpu_mode});
		range.start += part_size;
		range.size -= part_size;
		current += part_size;
		remaining -= part_size;
	}
	if (remaining != 0) {
		mappings->clear();
		return false;
	}

	free.erase(
	    std::remove_if(free.begin(), free.end(), [](const auto& range) { return range.size == 0; }),
	    free.end());
	m_free = std::move(free);
	m_mappings.insert(m_mappings.end(), mappings->begin(), mappings->end());
	return true;
}

bool PooledMemory::QueryUnlocked(uint64_t vaddr, uint64_t size,
                                 std::vector<Mapping>* mappings) const {
	EXIT_IF(mappings == nullptr);
	mappings->clear();
	if (vaddr == 0 || size == 0 || UINT64_MAX - vaddr < size) {
		return false;
	}

	const auto end     = vaddr + size;
	auto       current = vaddr;
	while (current < end) {
		const auto it =
		    std::find_if(m_mappings.begin(), m_mappings.end(), [current](const auto& m) {
			    return current >= m.vaddr && current < m.vaddr + m.size;
		    });
		if (it == m_mappings.end()) {
			mappings->clear();
			return false;
		}
		const auto part_size = std::min(end, it->vaddr + it->size) - current;
		mappings->push_back(
		    {current, part_size, it->phys_addr + (current - it->vaddr), it->gpu_mode});
		current += part_size;
	}
	return true;
}

bool PooledMemory::Query(uint64_t vaddr, uint64_t size, std::vector<Mapping>* mappings) {
	Common::LockGuard lock(m_mutex);
	return QueryUnlocked(vaddr, size, mappings);
}

bool PooledMemory::Release(uint64_t vaddr, uint64_t size, GpuAccessMode* gpu_mode) {
	EXIT_IF(gpu_mode == nullptr);

	Common::LockGuard    lock(m_mutex);
	std::vector<Mapping> released;
	if (!QueryUnlocked(vaddr, size, &released)) {
		return false;
	}

	*gpu_mode                = released.front().gpu_mode;
	const auto           end = vaddr + size;
	std::vector<Mapping> kept;
	for (const auto& mapping: m_mappings) {
		const auto mapping_end = mapping.vaddr + mapping.size;
		const auto cut_start   = std::max(vaddr, mapping.vaddr);
		const auto cut_end     = std::min(end, mapping_end);
		if (cut_start >= cut_end) {
			kept.push_back(mapping);
			continue;
		}
		if (mapping.vaddr < cut_start) {
			auto left = mapping;
			left.size = cut_start - mapping.vaddr;
			kept.push_back(left);
		}
		if (cut_end < mapping_end) {
			auto right      = mapping;
			right.vaddr     = cut_end;
			right.size      = mapping_end - cut_end;
			right.phys_addr = mapping.phys_addr + (cut_end - mapping.vaddr);
			kept.push_back(right);
		}
	}
	m_mappings = std::move(kept);
	for (const auto& mapping: released) {
		AddFreeUnlocked(mapping.phys_addr, mapping.size);
	}
	return true;
}

uint64_t PooledMemory::Available() {
	Common::LockGuard lock(m_mutex);
	uint64_t          available = 0;
	for (const auto& range: m_free) {
		available += range.size;
	}
	return available;
}

std::vector<PooledMemory::Mapping> PooledMemory::GetMappings() {
	Common::LockGuard lock(m_mutex);
	return m_mappings;
}

static bool UnmapPooledBackingTransactional(const std::vector<PooledMemory::Mapping>& mappings,
                                            VirtualMemory::Mode                       mode) {
	std::vector<PooledMemory::Mapping> removed;
	for (const auto& mapping: mappings) {
		if (!g_guest_address_space->UnmapBacking(mapping.vaddr, mapping.size)) {
			for (auto it = removed.rbegin(); it != removed.rend(); ++it) {
				auto       failure_reason = GuestBackingStore::FailureReason::None;
				const bool restored       = g_guest_address_space->MapBacking(
				    it->vaddr, it->size, it->phys_addr, mode, &failure_reason);
				if (!restored) {
					EXIT("pooled-memory unmap rollback failed: %s\n",
					     GuestBackingStore::GetFailureReasonName(failure_reason));
				}
			}
			return false;
		}
		removed.push_back(mapping);
	}
	return true;
}

int32_t KYTY_SYSV_ABI KernelMapNamedFlexibleMemory(void** addr_in_out, size_t len, int prot,
                                                   int flags, const char* name) {
	PRINT_NAME();

	bc5::load_stat::CountedLock<std::recursive_mutex> memory_operation_lock(g_memory_operation_mutex, bc5::load_stat::kMemLockWait); // exp 0415 (ls415): a lock_guard with the wait counted

	// Experiment 0405 series e5, BC5_R3_NULL_ARGS (M21): a NULL addr_in_out is the guest's error, not the host's exit.
	// EINVAL, as sharpemu 514d766 src/SharpEmu.Libs/Kernel/KernelMemoryCompatExports.cs:3352-3360 (MapFlexibleMemoryCore:
	// a pointer of 0 gives MemoryInvalidArgument; GPL-2.0-or-later) and AnyPS5 4f41f4c37
	// core/libs/prx/libkernel/DirectMemory/DirectMemory.cpp:1103-1108 (ValidateOutput: its comment names EINVAL, the code
	// throws; GPL-2.0-only). shadPS4 60c42b9 reads *addr_in_out unchecked.
	if (addr_in_out == nullptr && Bc5R3On(BC5_R3_ITEM_NULL_ARGS)) {
		return KERNEL_ERROR_EINVAL;
	}
	EXIT_NOT_IMPLEMENTED(addr_in_out == nullptr);

	constexpr size_t   PAGE_SIZE                = 0x4000;
	constexpr size_t   MAXIMUM_NAME_SIZE        = 32;
	constexpr uint64_t DEFAULT_PS5_BASE         = 0x200000000;
	constexpr uint32_t GUEST_MAP_FIXED          = 0x10;
	constexpr uint32_t GUEST_MAP_NO_OVERWRITE   = 0x80;
	constexpr uint32_t GUEST_MAP_DMEM_COMPAT    = 0x400;
	constexpr uint32_t GUEST_MAP_UNKNOWN_8000   = 0x8000;
	constexpr uint32_t GUEST_MAP_NO_COALESCE    = 0x400000;
	constexpr uint32_t GUEST_MAP_ALIGNMENT_MASK = 0xff000000;
	constexpr uint32_t SUPPORTED_MAP_BITS       = GUEST_MAP_FIXED | GUEST_MAP_NO_OVERWRITE |
	                                              GUEST_MAP_DMEM_COMPAT | GUEST_MAP_UNKNOWN_8000 |
	                                              GUEST_MAP_NO_COALESCE | GUEST_MAP_ALIGNMENT_MASK;

	if (len == 0 || (len & (PAGE_SIZE - 1)) != 0) {
		return KERNEL_ERROR_EINVAL;
	}
	if (len > g_flexible_memory->Available()) {
		return KERNEL_ERROR_ENOMEM;
	}

	if (name == nullptr) {
		return KERNEL_ERROR_EFAULT;
	}

	if (std::strlen(name) >= MAXIMUM_NAME_SIZE) {
		return KERNEL_ERROR_ENAMETOOLONG;
	}

	const auto map_flags       = static_cast<uint32_t>(flags);
	const auto alignment_shift = (map_flags & GUEST_MAP_ALIGNMENT_MASK) >> 24u;
	if ((map_flags & ~SUPPORTED_MAP_BITS) != 0 ||
	    (alignment_shift != 0 && (alignment_shift < 14 || alignment_shift > 31))) {
		LOGF_COLOR(Log::Color::Red, "\t unsupported flags = 0x%08" PRIx32 "\n", map_flags);
		return KERNEL_ERROR_EINVAL;
	}
	const uint64_t map_alignment =
	    alignment_shift != 0 ? uint64_t {1} << alignment_shift : PAGE_SIZE;

	VirtualMemory::Mode mode     = VirtualMemory::Mode::NoAccess;
	GpuAccessMode       gpu_mode = GpuAccessMode::NoAccess;

	if (!DecodeMemoryProtection(prot, &mode, &gpu_mode)) {
		// ports pack 1, C (AnyPS5 c55fb36d57 core/libs/prx/libkernel/DirectMemory/Export.cpp:63-64, 394-395; dca5752e1b,
		// measured EINVAL on fw 13.60): a protection this map cannot take is EINVAL, not a host exit.
		if (BC5_P1("KYTY_BC5_P1_FATAL_TO_ERROR")) {
			LOGF_COLOR(Log::Color::Red, "\t unknown prot = %d: EINVAL (ports pack 1)\n", prot);
			return KERNEL_ERROR_EINVAL;
		}
		EXIT("unknown prot: %d\n", prot);
	}

	auto                 in_addr              = reinterpret_cast<uint64_t>(*addr_in_out);
	uint64_t             out_addr             = 0;
	bool                 consumed_reservation = false;
	VirtualRanges::Range consumed_range {};

	if ((flags & GUEST_MAP_FIXED) != 0) {
		if (in_addr == 0 || (in_addr & (PAGE_SIZE - 1)) != 0 ||
		    (in_addr & (map_alignment - 1u)) != 0) {
			return KERNEL_ERROR_EINVAL;
		}
		if ((flags & GUEST_MAP_NO_OVERWRITE) != 0 && g_virtual_ranges->HasOverlap(in_addr, len)) {
			return KERNEL_ERROR_ENOMEM;
		}
		std::vector<VirtualRanges::Range> reserved_ranges;
		if (g_virtual_ranges->QuerySpan(in_addr, len, &reserved_ranges) &&
		    std::all_of(reserved_ranges.begin(), reserved_ranges.end(), [](const auto& range) {
			    return range.type == VirtualRangeType::Reserved;
		    })) {
			UnmapGpuRange(in_addr, len);
			consumed_range = reserved_ranges.front();
			if (g_virtual_ranges->ConsumeReservedSpan(in_addr, len)) {
				consumed_reservation = true;
				out_addr             = in_addr;
			}
		}
		if (!consumed_reservation && ReplaceFixedRangeWithReserved(in_addr, len) &&
		    g_virtual_ranges->ConsumeReservedSpan(in_addr, len, &consumed_range)) {
			consumed_reservation = true;
			out_addr             = in_addr;
		}
	} else {
		// Experiment 0405 series e5, BC5_R3_FLEX_HINT (M6): a hint whose whole range lies in reserved ranges is used as the
		// address, as if MAP_FIXED were set (AnyPS5 4f41f4c37 core/libs/prx/libkernel/DirectMemory/DirectMemory.cpp:1157-1160,
		// PlaceHintInReservation, used by MapAnonymous at 1205; title-observed in TITLEX, docs/dev/debt/libkernel.md:109;
		// GPL-2.0-only; sharpemu 514d766 BackedMappings.cs:339-344, GPL-2.0-or-later). This file's direct maps already do
		// it (KernelMapDirectMemory's non-fixed branch); this is the same code. An unaligned hint stays a hint.
		if (Bc5R3On(BC5_R3_ITEM_FLEX_HINT) && in_addr != 0 && (in_addr & (PAGE_SIZE - 1)) == 0 &&
		    (in_addr & (map_alignment - 1u)) == 0) {
			std::vector<VirtualRanges::Range> reserved_ranges;
			if (g_virtual_ranges->QuerySpan(in_addr, len, &reserved_ranges) &&
			    std::all_of(reserved_ranges.begin(), reserved_ranges.end(),
			                [](const auto& range) { return range.type == VirtualRangeType::Reserved; })) {
				UnmapGpuRange(in_addr, len);
				consumed_range = reserved_ranges.front();
				if (g_virtual_ranges->ConsumeReservedSpan(in_addr, len)) {
					consumed_reservation = true;
					out_addr             = in_addr;
				}
			}
		}
		if (!consumed_reservation) {
		const auto search_addr = (in_addr != 0 ? in_addr : DEFAULT_PS5_BASE);
		out_addr               = FindGuestFreeRange(search_addr, len, map_alignment);
		if (out_addr != 0) {
			UnmapGpuRange(out_addr, len);
		}
		} // experiment 0405 series e5 (M6)
	}

	*addr_in_out = reinterpret_cast<void*>(out_addr);

	if (out_addr == 0) {
		if (consumed_reservation) {
			g_virtual_ranges->Add(in_addr, len, 0, 0, 0, VirtualRangeType::Reserved,
			                      consumed_range.name);
		}
		return KERNEL_ERROR_ENOMEM;
	}

	if (!g_flexible_memory->Map(out_addr, len, prot, mode, gpu_mode, name)) {
		LOGF_COLOR(Log::Color::Red, "\t [Fail]\n");
		if (consumed_reservation) {
			EXIT_IF(!g_virtual_ranges->Add(out_addr, len, 0, 0, 0, VirtualRangeType::Reserved,
			                               consumed_range.name));
		}
		return KERNEL_ERROR_ENOMEM;
	}

	if (!g_virtual_ranges->Add(out_addr, len, 0, prot, 0, VirtualRangeType::Flexible, name,
	                           (map_flags & GUEST_MAP_NO_COALESCE) != 0)) {
		GpuAccessMode rollback_gpu_mode = GpuAccessMode::NoAccess;
		EXIT_IF(!g_flexible_memory->Unmap(out_addr, len, &rollback_gpu_mode));
		if (consumed_reservation) {
			EXIT_IF(!g_virtual_ranges->Add(out_addr, len, 0, 0, 0, VirtualRangeType::Reserved,
			                               consumed_range.name));
		}
		return KERNEL_ERROR_EBUSY;
	}

	LOGF("\t in_addr  = 0x%016" PRIx64 "\n"
	     "\t out_addr = 0x%016" PRIx64 "\n"
	     "\t size     = %" PRIu64 "\n"
	     "\t mode     = %s\n"
	     "\t flags    = 0x%08" PRIx32 "\n"
	     "\t name     = %s\n"
	     "\t gpu_mode = %s\n",
	     in_addr, out_addr, len, Common::EnumName(mode).c_str(), static_cast<uint32_t>(flags), name,
	     Common::EnumName(gpu_mode).c_str());

	MapGpuRange(out_addr, len);

	if (g_alloc_callback != nullptr) {
		g_alloc_callback(out_addr, len);
	}

	return OK;
}

static int Bc5Ff_KernelMapFlexibleMemory(void** addr_in_out, size_t len, int prot, int flags); // exp 0412 (tag ff412)
int KYTY_SYSV_ABI KernelMapFlexibleMemory(void** addr_in_out, size_t len, int prot, int flags) { // exp 0412 (tag ff412)
	const int bc5_ff_result = Bc5Ff_KernelMapFlexibleMemory(addr_in_out, len, prot, flags);
	if (bc5_ff_result != OK) [[unlikely]] ff412_report("KernelMapFlexibleMemory", bc5_ff_result, __builtin_return_address(0), {ff412::u(addr_in_out), ff412::u(len), ff412::u(prot), ff412::u(flags)});
	return bc5_ff_result;
}
static int Bc5Ff_KernelMapFlexibleMemory(void** addr_in_out, size_t len, int prot, int flags) {
	return KernelMapNamedFlexibleMemory(addr_in_out, len, prot, flags, "");
}

int KYTY_SYSV_ABI KernelSetPrtAperture(int index, void* addr, size_t len) {
	PRINT_NAME();

	bc5::load_stat::CountedLock<std::recursive_mutex> memory_operation_lock(g_memory_operation_mutex, bc5::load_stat::kMemLockWait); // exp 0415 (ls415): a lock_guard with the wait counted

	const auto address = reinterpret_cast<uint64_t>(addr);

	LOGF("\t index = %d\n"
	     "\t addr  = 0x%016" PRIx64 "\n"
	     "\t len   = 0x%016" PRIx64 "\n",
	     index, address, static_cast<uint64_t>(len));

	if (index < 0 || index > PRT_APERTURE_MAX_INDEX) {
		return KERNEL_ERROR_EINVAL;
	}

	if (len != 0 && (address == 0 || (address & (PRT_PAGE_SIZE - 1u)) != 0 ||
	                 (len & (PRT_PAGE_SIZE - 1u)) != 0 || address < PRT_APERTURE_START ||
	                 len > PRT_APERTURE_END - address)) {
		return KERNEL_ERROR_EINVAL;
	}

	PrtAperture old {};
	{
		Common::LockGuard lock(g_prt_aperture_mutex);
		old = g_prt_apertures[static_cast<size_t>(index)];
	}
	if (old.size != 0) {
		UnmapGpuRange(old.address, old.size);
	}
	{
		Common::LockGuard lock(g_prt_aperture_mutex);
		g_prt_apertures[static_cast<size_t>(index)] =
		    len == 0 ? PrtAperture {} : PrtAperture {address, static_cast<uint64_t>(len)};
	}
	if (len != 0) {
		MapGpuRange(address, len);
	}

	LOGF_COLOR(Log::Color::Green, "\t[Ok]\n");

	return OK;
}

int KYTY_SYSV_ABI KernelGetPrtAperture(int index, void** addr, size_t* len) {
	PRINT_NAME();

	LOGF("\t index = %d\n"
	     "\t addr  = %p\n"
	     "\t len   = %p\n",
	     index, static_cast<void*>(addr), static_cast<void*>(len));

	if (index < 0 || index > PRT_APERTURE_MAX_INDEX) {
		return KERNEL_ERROR_EINVAL;
	}

	if (addr == nullptr || len == nullptr) {
		return KERNEL_ERROR_EFAULT;
	}

	PrtAperture aperture {};
	{
		Common::LockGuard lock(g_prt_aperture_mutex);
		aperture = g_prt_apertures[static_cast<size_t>(index)];
	}

	*addr = reinterpret_cast<void*>(aperture.address);
	*len  = static_cast<size_t>(aperture.size);

	LOGF_COLOR(Log::Color::Green,
	           "\t *addr = 0x%016" PRIx64 "\n"
	           "\t *len  = 0x%016" PRIx64 "\n"
	           "\t[Ok]\n",
	           aperture.address, aperture.size);

	return OK;
}

int KYTY_SYSV_ABI KernelSetVirtualRangeName(const void* addr, uint64_t len, const char* name) {
	PRINT_NAME();

	bc5::load_stat::CountedLock<std::recursive_mutex> memory_operation_lock(g_memory_operation_mutex, bc5::load_stat::kMemLockWait); // exp 0415 (ls415): a lock_guard with the wait counted

	auto vaddr = reinterpret_cast<uint64_t>(addr);

	LOGF("\t addr = 0x%016" PRIx64 "\n"
	     "\t len  = 0x%016" PRIx64 "\n"
	     "\t name = %s\n",
	     vaddr, len, name != nullptr ? name : "(null)");

	if (name == nullptr) {
		return KERNEL_ERROR_EFAULT;
	}

	if (std::strlen(name) >= KERNEL_MAXIMUM_NAME_LENGTH) {
		return KERNEL_ERROR_ENAMETOOLONG;
	}

	g_physical_memory->SetVirtualRangeName(vaddr, len, name);
	g_flexible_memory->SetVirtualRangeName(vaddr, len, name);
	g_virtual_ranges->Rename(vaddr, len, name);

	return OK;
}

static bool FreeGuestMemoryOwner(uint64_t vaddr, uint64_t size) {
	return g_guest_address_space->ReleaseCommitted(vaddr, size) &&
	       g_virtual_ranges->Remove(vaddr, size);
}

static int UnmapMemoryRange(uint64_t vaddr, size_t len) {
	if (len == 0 || UINT64_MAX - vaddr < len) {
		return KERNEL_ERROR_EINVAL;
	}

	VirtualRanges::Range range {};
	if (!g_virtual_ranges->Query(vaddr, 0, &range)) {
		return KERNEL_ERROR_EACCES;
	}
	const auto chunk_len = std::min<uint64_t>(len, range.size - (vaddr - range.start));
	if (chunk_len < len) {
		const int ret = UnmapMemoryRange(vaddr, chunk_len);
		return ret == OK ? UnmapMemoryRange(vaddr + chunk_len, len - chunk_len) : ret;
	}
	if (IsReservedRangeType(range.type)) {
		if (!g_guest_address_space->ReleaseFree(vaddr, len)) {
			return KERNEL_ERROR_EACCES;
		}
		g_virtual_ranges->Remove(vaddr, len);
		return OK;
	}
	if (range.type == VirtualRangeType::Code || range.type == VirtualRangeType::Runtime) {
		return FreeGuestMemoryOwner(vaddr, len) ? OK : KERNEL_ERROR_EACCES;
	}

	GpuAccessMode gpu_mode       = GpuAccessMode::NoAccess;
	bool          owner_unmapped = false;
	if (range.type == VirtualRangeType::Pooled) {
		std::vector<PooledMemory::Mapping> mappings;
		if (g_pooled_memory->Query(vaddr, len, &mappings)) {
			VirtualMemory::Mode mode        = VirtualMemory::Mode::NoAccess;
			GpuAccessMode       decoded_gpu = GpuAccessMode::NoAccess;
			owner_unmapped = DecodeMemoryProtection(range.protection, &mode, &decoded_gpu) &&
			                 UnmapPooledBackingTransactional(mappings, mode);
			if (owner_unmapped && !g_pooled_memory->Release(vaddr, len, &gpu_mode)) {
				EXIT("failed to release unmapped pooled-memory range\n");
			}
		}
		if (!owner_unmapped) {
			return KERNEL_ERROR_EACCES;
		}
	} else if (range.type == VirtualRangeType::Direct) {
		VirtualMemory::Mode direct_mode   = VirtualMemory::Mode::NoAccess;
		GpuAccessMode       direct_gpu    = GpuAccessMode::NoAccess;
		const auto          direct_offset = range.offset + vaddr - range.start;
		if (DecodeMemoryProtection(range.protection, &direct_mode, &direct_gpu) &&
		    g_guest_address_space->BackingContains(vaddr, len) &&
		    g_guest_address_space->UnmapBacking(vaddr, len)) {
			uint64_t ignored_host = 0;
			if (g_physical_memory->Unmap(vaddr, len, &gpu_mode, &ignored_host)) {
				owner_unmapped = true;
			} else {
				EXIT_IF(!g_guest_address_space->MapBacking(vaddr, len, direct_offset, direct_mode));
			}
		}
	} else if (range.type == VirtualRangeType::Stack) {
		owner_unmapped = g_guest_address_space->ReleaseCommitted(vaddr, len);
	} else {
		uint64_t ignored_host = 0;
		owner_unmapped        = g_flexible_memory->Unmap(vaddr, len, &gpu_mode, &ignored_host);
	}
	if (!owner_unmapped) {
		return KERNEL_ERROR_EACCES;
	}

	g_virtual_ranges->Remove(vaddr, len);

	if (g_free_callback != nullptr && IsCommittedRangeType(range.type)) {
		g_free_callback(vaddr, len);
	}
	if (range.type == VirtualRangeType::Pooled) {
		MemoryPoolSubtractCommitted(len);
	}

	return OK;
}

// Experiment 0405 series e5, BC5_R3_MUNMAP_HOLES (M7): sceKernelMunmap over holes unmaps what is mapped, skips the
// holes and returns 0; a range with nothing mapped returns 0. AnyPS5 4f41f4c37 core/libs/prx/libkernel/DirectMemory/
// Export.cpp:332-339 and DirectMemory.cpp:1615-1622 (DoMunmap: nothing overlapping gives 0, after prosper's console
// oracle, docs/dev/debt/libkernel.md:313; GPL-2.0-only); shadPS4 60c42b9 src/core/memory.cpp:913-1008 (free areas are
// skipped, 942-944; GPL-2.0-or-later). sharpemu 514d766 returns an error here, as this file does today. Length checks
// are unchanged (AnyPS5 and shadPS4 disagree on a length that is not a page multiple); a NULL address keeps today's
// EACCES (AnyPS5 gives EINVAL there). Adapted, no code copied: each run of ranges without a hole goes through today's
// path (UnmapGpuRange, UnmapMemoryRange); the first error ends the walk and is returned. The caller holds the memory
// operation lock and has checked len != 0 and no overflow.
static int Bc5MunmapHoles(uint64_t vaddr, size_t len) {
	const uint64_t                             end     = vaddr + len;
	uint64_t                                   current = vaddr;
	std::vector<std::pair<uint64_t, uint64_t>> runs;
	while (current < end) {
		VirtualRanges::Range range {};
		if (!g_virtual_ranges->Query(current, 1, &range) || range.start >= end) {
			break;
		}
		const uint64_t range_end = (UINT64_MAX - range.start < range.size ? UINT64_MAX : range.start + range.size);
		const uint64_t lo        = std::max(current, range.start);
		const uint64_t hi        = std::min(end, range_end);
		if (hi <= lo) {
			break;
		}
		if (!runs.empty() && runs.back().first + runs.back().second == lo) {
			runs.back().second += hi - lo;
		} else {
			runs.emplace_back(lo, hi - lo);
		}
		current = hi;
	}
	LOGF("\t exp 0405 M7: 0x%016" PRIx64 "+0x%016" PRIx64 " has holes: %" PRIu64 " mapped run(s)\n", vaddr,
	     static_cast<uint64_t>(len), static_cast<uint64_t>(runs.size()));
	for (const auto& [run_start, run_size]: runs) {
		UnmapGpuRange(run_start, run_size);
		const int result = UnmapMemoryRange(run_start, run_size);
		if (result != OK) {
			return result;
		}
	}
	return OK;
}

static int Bc5Ff_KernelMunmap(uint64_t vaddr, size_t len); // exp 0412 (tag ff412)
int KYTY_SYSV_ABI KernelMunmap(uint64_t vaddr, size_t len) { // exp 0412 (tag ff412)
	const int bc5_ff_result = Bc5Ff_KernelMunmap(vaddr, len);
	if (bc5_ff_result != OK) [[unlikely]] ff412_report("KernelMunmap", bc5_ff_result, __builtin_return_address(0), {ff412::u(vaddr), ff412::u(len)});
	return bc5_ff_result;
}
static int Bc5Ff_KernelMunmap(uint64_t vaddr, size_t len) {
	PRINT_NAME();

	bc5::load_stat::CountedLock<std::recursive_mutex> memory_operation_lock(g_memory_operation_mutex, bc5::load_stat::kMemLockWait); // exp 0415 (ls415): a lock_guard with the wait counted

	LOGF("\t start = 0x%016" PRIx64 "\n"
	     "\t len   = 0x%016" PRIx64 "\n",
	     vaddr, len);

	if (len == 0 || UINT64_MAX - vaddr < len) {
		return KERNEL_ERROR_EINVAL;
	}
	std::vector<VirtualRanges::Range> ranges;
	if (!g_virtual_ranges->QuerySpan(vaddr, len, &ranges)) {
		if (vaddr != 0 && Bc5R3On(BC5_R3_ITEM_MUNMAP_HOLES)) { // experiment 0405 series e5 (M7)
			return Bc5MunmapHoles(vaddr, len);
		}
		return KERNEL_ERROR_EACCES;
	}
	UnmapGpuRange(vaddr, len);
	return UnmapMemoryRange(vaddr, len);
}

size_t KYTY_SYSV_ABI KernelGetDirectMemorySize() {
	PRINT_NAME();

	return PhysicalMemory::Size();
}

static int Bc5Ff_KernelAvailableDirectMemorySize(int64_t search_start, int64_t search_end,
                                                  size_t alignment, int64_t* phys_addr_out,
                                                  size_t* size_out); // exp 0412 (tag ff412)
int KYTY_SYSV_ABI KernelAvailableDirectMemorySize(int64_t search_start, int64_t search_end,
                                                  size_t alignment, int64_t* phys_addr_out,
                                                  size_t* size_out) { // exp 0412 (tag ff412)
	const int bc5_ff_result = Bc5Ff_KernelAvailableDirectMemorySize(search_start, search_end, alignment, phys_addr_out, size_out);
	if (bc5_ff_result != OK) [[unlikely]] ff412_report("KernelAvailableDirectMemorySize", bc5_ff_result, __builtin_return_address(0), {ff412::u(search_start), ff412::u(search_end), ff412::u(alignment), ff412::u(phys_addr_out), ff412::u(size_out)});
	return bc5_ff_result;
}
static int Bc5Ff_KernelAvailableDirectMemorySize(int64_t search_start, int64_t search_end,
                                                  size_t alignment, int64_t* phys_addr_out,
                                                  size_t* size_out) {
	PRINT_NAME();

	bc5::load_stat::CountedLock<std::recursive_mutex> memory_operation_lock(g_memory_operation_mutex, bc5::load_stat::kMemLockWait); // exp 0415 (ls415): a lock_guard with the wait counted

	LOGF("\t search_start = 0x%016" PRIx64 "\n"
	     "\t search_end   = 0x%016" PRIx64 "\n"
	     "\t alignment    = 0x%016" PRIx64 "\n",
	     search_start, search_end, static_cast<uint64_t>(alignment));

	if (phys_addr_out == nullptr || size_out == nullptr) {
		return KERNEL_ERROR_EINVAL;
	}

	*phys_addr_out = 0;
	*size_out      = 0;

	if (search_start < 0 || search_end < 0) {
		return KERNEL_ERROR_EINVAL;
	}

	if (search_end <= search_start) {
		LOGF_COLOR(Log::Color::Red, "\t[Fail]\n");
		return KERNEL_ERROR_ENOMEM;
	}

	uint64_t phys_addr = 0;
	uint64_t size      = 0;
	if (!g_physical_memory->Available(static_cast<uint64_t>(search_start),
	                                  static_cast<uint64_t>(search_end), alignment, &phys_addr,
	                                  &size)) {
		LOGF_COLOR(Log::Color::Red, "\t[Fail]\n");
		return KERNEL_ERROR_ENOMEM;
	}

	*phys_addr_out = static_cast<int64_t>(phys_addr);
	*size_out      = static_cast<size_t>(size);

	LOGF_COLOR(Log::Color::Green,
	           "\t phys_addr = 0x%016" PRIx64 "\n"
	           "\t size      = 0x%016" PRIx64 "\n"
	           "\t[Ok]\n",
	           phys_addr, size);

	return OK;
}

int KYTY_SYSV_ABI KernelGetPageTableStats(int* cpu_total, int* cpu_available, int* gpu_total,
                                          int* gpu_available) {
	PRINT_NAME();

	bc5::load_stat::CountedLock<std::recursive_mutex> memory_operation_lock(g_memory_operation_mutex, bc5::load_stat::kMemLockWait); // exp 0415 (ls415): a lock_guard with the wait counted

	if (cpu_total == nullptr || cpu_available == nullptr || gpu_total == nullptr ||
	    gpu_available == nullptr) {
		return KERNEL_ERROR_EFAULT;
	}

	const auto cpu_used =
	    (g_virtual_ranges != nullptr ? g_virtual_ranges->CountPageTableEntries(false) : 0);
	const auto gpu_used =
	    (g_virtual_ranges != nullptr ? g_virtual_ranges->CountPageTableEntries(true) : 0);

	*cpu_total     = PAGE_TABLE_POOL_ENTRIES;
	*gpu_total     = PAGE_TABLE_POOL_ENTRIES;
	*cpu_available = PAGE_TABLE_POOL_ENTRIES -
	                 static_cast<int>(std::min<uint64_t>(cpu_used, PAGE_TABLE_POOL_ENTRIES));
	*gpu_available = PAGE_TABLE_POOL_ENTRIES -
	                 static_cast<int>(std::min<uint64_t>(gpu_used, PAGE_TABLE_POOL_ENTRIES));

	LOGF_COLOR(Log::Color::Green,
	           "\t cpu_total     = %d\n"
	           "\t cpu_available = %d\n"
	           "\t gpu_total     = %d\n"
	           "\t gpu_available = %d\n"
	           "\t[Ok]\n",
	           *cpu_total, *cpu_available, *gpu_total, *gpu_available);

	return OK;
}

int KYTY_SYSV_ABI KernelDirectMemoryQuery(int64_t offset, int flags, void* info, size_t info_size) {
	PRINT_NAME();

	bc5::load_stat::CountedLock<std::recursive_mutex> memory_operation_lock(g_memory_operation_mutex, bc5::load_stat::kMemLockWait); // exp 0415 (ls415): a lock_guard with the wait counted

	LOGF("\t offset    = 0x%016" PRIx64 "\n"
	     "\t flags     = 0x%08" PRIx32 "\n"
	     "\t info_size = 0x%016" PRIx64 "\n",
	     offset, flags, info_size);

	struct QueryInfo {
		int64_t start;
		int64_t end;
		int     memory_type;
	};

	// Experiment 0405 series e5, BC5_R3_QUERY_SIZE (M30): an info size larger than the struct is accepted and only the
	// struct is written (AnyPS5 4f41f4c37 core/libs/prx/libkernel/DirectMemory/Export.cpp:253-262, size below the struct
	// is EINVAL; GPL-2.0-only).
	if (offset < 0 || (flags != 0 && flags != 1) ||
	    (Bc5R3On(BC5_R3_ITEM_QUERY_SIZE) ? info_size < sizeof(QueryInfo) : info_size != sizeof(QueryInfo)) ||
	    info == nullptr) {
		return KERNEL_ERROR_EINVAL;
	}

	auto* query_info = static_cast<QueryInfo*>(info);

	PhysicalMemory::AllocatedBlock block {};
	{
		Common::LockGuard lock(g_physical_memory->GetMutex());
		const auto&       blocks  = g_physical_memory->GetPhysicalBlocks();
		auto              current = blocks.upper_bound(static_cast<uint64_t>(offset));
		if (current != blocks.begin()) {
			auto previous = std::prev(current);
			if (static_cast<uint64_t>(offset) <
			    previous->second.start_addr + previous->second.size) {
				current = previous;
			}
		}
		if (current == blocks.end() ||
		    (flags == 0 && (static_cast<uint64_t>(offset) < current->second.start_addr ||
		                    static_cast<uint64_t>(offset) >=
		                        current->second.start_addr + current->second.size))) {
			// Experiment 0405 series e5, BC5_R3_DMQ_END (M20): find-next past the last block is EACCES, no terminal record
			// (AnyPS5 4f41f4c37 core/libs/prx/libkernel/DirectMemory/Export.cpp:253-262 and MemoryPool.cpp:125-136, GPL-2.0-only;
			// shadPS4 60c42b9 src/core/memory.cpp:1242-1245, GPL-2.0-or-later; sharpemu 514d766 KernelMemoryCompatExports.cs:
			// 3713-3739). KytyPS5 dfec14a src/kernel/memory.cpp:2164-2170 returns the terminal record, as this file does today.
			if (flags == 1 && static_cast<uint64_t>(offset) < PhysicalMemory::Size() && !Bc5R3On(BC5_R3_ITEM_DMQ_END)) {
				query_info->start       = static_cast<int64_t>(PhysicalMemory::Size());
				query_info->end         = static_cast<int64_t>(PhysicalMemory::Size());
				query_info->memory_type = 0;
				LOGF_COLOR(Log::Color::Green, "\t terminal    = true\n\t[Ok]\n");
				return OK;
			}

			LOGF_COLOR(Log::Color::Red, "\t[Fail]\n");
			return KERNEL_ERROR_EACCES;
		}

		block        = current->second;
		uint64_t end = block.start_addr + block.size;
		for (auto following = std::next(current);
		     following != blocks.end() && following->second.start_addr == end &&
		     following->second.memory_type == block.memory_type;
		     ++following) {
			end += following->second.size;
		}
		block.size = end - block.start_addr;
	}

	query_info->start       = static_cast<int64_t>(block.start_addr);
	query_info->end         = static_cast<int64_t>(block.start_addr + block.size);
	query_info->memory_type = block.memory_type;

	LOGF_COLOR(Log::Color::Green,
	           "\t start       = %016" PRIx64 "\n"
	           "\t end         = %016" PRIx64 "\n"
	           "\t memory_type = %d\n"
	           "\t[Ok]\n",
	           query_info->start, query_info->end, query_info->memory_type);

	return OK;
}

static int Bc5Ff_KernelAllocateDirectMemory(int64_t search_start, int64_t search_end, size_t len,
                                             size_t alignment, int memory_type,
                                             int64_t* phys_addr_out); // exp 0412 (tag ff412)
int KYTY_SYSV_ABI KernelAllocateDirectMemory(int64_t search_start, int64_t search_end, size_t len,
                                             size_t alignment, int memory_type,
                                             int64_t* phys_addr_out) { // exp 0412 (tag ff412)
	const int bc5_ff_result = Bc5Ff_KernelAllocateDirectMemory(search_start, search_end, len, alignment, memory_type, phys_addr_out);
	if (bc5_ff_result != OK) [[unlikely]] ff412_report("KernelAllocateDirectMemory", bc5_ff_result, __builtin_return_address(0), {ff412::u(search_start), ff412::u(search_end), ff412::u(len), ff412::u(alignment), ff412::u(memory_type), ff412::u(phys_addr_out)});
	return bc5_ff_result;
}
static int Bc5Ff_KernelAllocateDirectMemory(int64_t search_start, int64_t search_end, size_t len,
                                             size_t alignment, int memory_type,
                                             int64_t* phys_addr_out) {
	PRINT_NAME();

	bc5::load_stat::CountedLock<std::recursive_mutex> memory_operation_lock(g_memory_operation_mutex, bc5::load_stat::kMemLockWait); // exp 0415 (ls415): a lock_guard with the wait counted

	LOGF("\t search_start = 0x%016" PRIx64 "\n"
	     "\t search_end   = 0x%016" PRIx64 "\n"
	     "\t len          = 0x%016" PRIx64 "\n"
	     "\t alignment    = 0x%016" PRIx64 "\n"
	     "\t memory_type  = %d\n",
	     search_start, search_end, len, alignment, memory_type);

	constexpr uint64_t PAGE_SIZE = 0x4000;
	if (search_start < 0 || search_end <= search_start || len == 0 ||
	    (len & (PAGE_SIZE - 1u)) != 0 || (alignment != 0 && (alignment & (PAGE_SIZE - 1u)) != 0) ||
	    phys_addr_out == nullptr) {
		return KERNEL_ERROR_EINVAL;
	}

	uint64_t addr = 0;
	if (!g_physical_memory->Alloc(search_start, search_end, len, alignment, &addr, memory_type)) {
		LOGF_COLOR(Log::Color::Red, "\t[Fail]\n");
		return KERNEL_ERROR_EAGAIN;
	}

	*phys_addr_out = static_cast<int64_t>(addr);

	LOGF_COLOR(Log::Color::Green, "\tphys_addr    = %016" PRIx64 "\n\t[Ok]\n", addr);

	return OK;
}

static int Bc5Ff_KernelAllocateMainDirectMemory(size_t len, size_t alignment, int memory_type,
                                                 int64_t* phys_addr_out); // exp 0412 (tag ff412)
int KYTY_SYSV_ABI KernelAllocateMainDirectMemory(size_t len, size_t alignment, int memory_type,
                                                 int64_t* phys_addr_out) { // exp 0412 (tag ff412)
	const int bc5_ff_result = Bc5Ff_KernelAllocateMainDirectMemory(len, alignment, memory_type, phys_addr_out);
	if (bc5_ff_result != OK) [[unlikely]] ff412_report("KernelAllocateMainDirectMemory", bc5_ff_result, __builtin_return_address(0), {ff412::u(len), ff412::u(alignment), ff412::u(memory_type), ff412::u(phys_addr_out)});
	return bc5_ff_result;
}
static int Bc5Ff_KernelAllocateMainDirectMemory(size_t len, size_t alignment, int memory_type,
                                                 int64_t* phys_addr_out) {
	PRINT_NAME();

	bc5::load_stat::CountedLock<std::recursive_mutex> memory_operation_lock(g_memory_operation_mutex, bc5::load_stat::kMemLockWait); // exp 0415 (ls415): a lock_guard with the wait counted

	LOGF("\t len          = 0x%016" PRIx64 "\n"
	     "\t alignment    = 0x%016" PRIx64 "\n"
	     "\t memory_type  = %d\n",
	     len, alignment, memory_type);

	return KernelAllocateDirectMemory(0, static_cast<int64_t>(PhysicalMemory::Size()), len,
	                                  alignment, memory_type, phys_addr_out);
}

static int ReleaseDirectMemoryInternal(int64_t start, size_t len) {
	bc5::load_stat::CountedLock<std::recursive_mutex> memory_operation_lock(g_memory_operation_mutex, bc5::load_stat::kMemLockWait); // exp 0415 (ls415): a lock_guard with the wait counted

	if (g_pooled_memory->ReleaseExpansion(static_cast<uint64_t>(start), len)) {
		if (!g_physical_memory->ReleasePoolExpansion(static_cast<uint64_t>(start), len)) {
			EXIT("failed to release physical pool expansion\n");
		}
		return OK;
	}

	std::vector<PhysicalMemory::AllocatedBlock> allocated_span;
	if (!g_physical_memory->GetAllocatedSpan(static_cast<uint64_t>(start), len, &allocated_span)) {
		return KERNEL_ERROR_EACCES;
	}

	const auto mapped_aliases = g_physical_memory->FindMappings(start, len);
	for (const auto& alias: mapped_aliases) {
		VirtualRanges::Range range {};
		if (!g_guest_address_space->BackingContains(alias.map_vaddr, alias.map_size) ||
		    !g_virtual_ranges->Query(alias.map_vaddr, 0, &range) ||
		    range.type != VirtualRangeType::Direct ||
		    alias.map_size > range.start + range.size - alias.map_vaddr) {
			EXIT("direct-memory alias escaped guest address-space ownership\n");
		}
	}

	for (const auto& alias: mapped_aliases) {
		UnmapGpuRange(alias.map_vaddr, alias.map_size);
	}

	auto restore_gpu_aliases = [&mapped_aliases]() {
		for (const auto& alias: mapped_aliases) {
			MapGpuRange(alias.map_vaddr, alias.map_size);
		}
	};
	auto restore_owner_aliases = [](const std::vector<PhysicalMemory::AllocatedBlock>& aliases) {
		for (auto it = aliases.rbegin(); it != aliases.rend(); ++it) {
			EXIT_IF(!g_guest_address_space->MapBacking(it->map_vaddr, it->map_size, it->start_addr,
			                                           it->mode));
		}
	};

	std::vector<PhysicalMemory::AllocatedBlock> owner_unmapped;
	for (const auto& alias: mapped_aliases) {
		if (!g_guest_address_space->UnmapBacking(alias.map_vaddr, alias.map_size)) {
			restore_owner_aliases(owner_unmapped);
			restore_gpu_aliases();
			return KERNEL_ERROR_EACCES;
		}
		owner_unmapped.push_back(alias);
	}

	std::vector<PhysicalMemory::AllocatedBlock> metadata_unmapped;
	for (const auto& alias: mapped_aliases) {
		GpuAccessMode alias_gpu_mode = GpuAccessMode::NoAccess;
		if (!g_physical_memory->Unmap(alias.map_vaddr, alias.map_size, &alias_gpu_mode)) {
			for (const auto& removed: metadata_unmapped) {
				EXIT_IF(!g_physical_memory->Map(removed.map_vaddr, removed.start_addr,
				                                removed.map_size, removed.prot, removed.mode,
				                                removed.gpu_mode));
			}
			restore_owner_aliases(owner_unmapped);
			restore_gpu_aliases();
			return KERNEL_ERROR_EACCES;
		}
		metadata_unmapped.push_back(alias);
	}

	for (const auto& alias: mapped_aliases) {
		EXIT_IF(!g_virtual_ranges->Remove(alias.map_vaddr, alias.map_size));
	}

	for (const auto& block: allocated_span) {
		uint64_t      unused_vaddr = 0;
		uint64_t      unused_size  = 0;
		GpuAccessMode unused_gpu   = GpuAccessMode::NoAccess;
		EXIT_IF(!g_physical_memory->Release(block.start_addr, block.size, &unused_vaddr,
		                                    &unused_size, &unused_gpu));
	}

	if (g_free_callback != nullptr) {
		for (const auto& alias: mapped_aliases) {
			g_free_callback(alias.map_vaddr, alias.map_size);
		}
	}

	return OK;
}

static int ValidateDirectReleaseRange(int64_t start, size_t len) {
	constexpr uint64_t PAGE_SIZE = 0x4000;
	return start < 0 || (static_cast<uint64_t>(start) & (PAGE_SIZE - 1u)) != 0 ||
	               (len & (PAGE_SIZE - 1u)) != 0
	           ? KERNEL_ERROR_EINVAL
	           : OK;
}

// Experiment 0405 series e5, BC5_R3_RELEASE_HOLES (M3): an unchecked sceKernelReleaseDirectMemory over free gaps
// releases the allocated parts and skips the gaps. KytyPS5 dfec14a src/kernel/memory.cpp:1281-1315 (GetAllocatedSpan
// with skip_gaps) and 2354-2370 (the unchecked release; GPL-2.0); shadPS4 60c42b9 src/core/memory.cpp:283-376 (an
// unchecked free ignores free areas, 305-313; GPL-2.0-or-later); AnyPS5 4f41f4c37 core/libs/prx/libkernel/DirectMemory/
// MemoryPool.cpp:259-286 (only the used runs are forgotten; GPL-2.0-only). sharpemu 514d766 frees nothing here, as this
// file does today. The checked form keeps ENOENT. Adapted, no code copied: called only after today's call failed. The
// allocated blocks in the range are collected into runs of adjacent blocks, and each run goes through today's path
// (ReleaseDirectMemoryInternal, which takes the run's mappings down too). As in KytyPS5, a pool-expansion block in the
// range releases nothing (only an exact release frees an expansion, as today); a range with no hole is left to
// today's result.
static void Bc5ReleaseDirectMemoryHoles(int64_t start, size_t len) {
	bc5::load_stat::CountedLock<std::recursive_mutex> memory_operation_lock(g_memory_operation_mutex, bc5::load_stat::kMemLockWait); // exp 0415 (ls415): a lock_guard with the wait counted

	const auto first = static_cast<uint64_t>(start);
	if (len == 0 || UINT64_MAX - first < len) {
		return;
	}
	const uint64_t                             end = first + len;
	std::vector<std::pair<uint64_t, uint64_t>> runs;
	{
		Common::LockGuard lock(g_physical_memory->GetMutex());
		const auto&       blocks = g_physical_memory->GetPhysicalBlocks();
		auto              it     = blocks.upper_bound(first);
		if (it != blocks.begin()) {
			const auto previous = std::prev(it);
			if (previous->second.start_addr + previous->second.size > first) {
				it = previous;
			}
		}
		for (; it != blocks.end() && it->second.start_addr < end; ++it) {
			const auto& block = it->second;
			if (block.pool_expansion) {
				return;
			}
			const uint64_t lo = std::max(first, block.start_addr);
			const uint64_t hi = std::min(end, block.start_addr + block.size);
			if (hi <= lo) {
				continue;
			}
			if (!runs.empty() && runs.back().first + runs.back().second == lo) {
				runs.back().second += hi - lo;
			} else {
				runs.emplace_back(lo, hi - lo);
			}
		}
	}
	if (runs.empty() || (runs.size() == 1 && runs.front().first == first && runs.front().second == len)) {
		return;
	}
	LOGF("\t exp 0405 M3: 0x%016" PRIx64 "+0x%016" PRIx64 " has free gaps: releasing %" PRIu64 " allocated run(s)\n",
	     first, static_cast<uint64_t>(len), static_cast<uint64_t>(runs.size()));
	for (const auto& [run_start, run_size]: runs) {
		(void)ReleaseDirectMemoryInternal(static_cast<int64_t>(run_start), static_cast<size_t>(run_size));
	}
}

static int Bc5Ff_KernelReleaseDirectMemory(int64_t start, size_t len); // exp 0412 (tag ff412)
int KYTY_SYSV_ABI KernelReleaseDirectMemory(int64_t start, size_t len) { // exp 0412 (tag ff412)
	const int bc5_ff_result = Bc5Ff_KernelReleaseDirectMemory(start, len);
	if (bc5_ff_result != OK) [[unlikely]] ff412_report("KernelReleaseDirectMemory", bc5_ff_result, __builtin_return_address(0), {ff412::u(start), ff412::u(len)});
	return bc5_ff_result;
}
static int Bc5Ff_KernelReleaseDirectMemory(int64_t start, size_t len) {
	PRINT_NAME();

	LOGF("\t start = 0x%016" PRIx64 "\n"
	     "\t len   = 0x%016" PRIx64 "\n",
	     start, len);

	const int validation = ValidateDirectReleaseRange(start, len);
	if (validation != OK) {
		return validation;
	}
	if (len != 0) {
		const int released = ReleaseDirectMemoryInternal(start, len); // today's call; its result is still not returned
		if (released != OK && Bc5R3On(BC5_R3_ITEM_RELEASE_HOLES)) {    // experiment 0405 series e5 (M3)
			Bc5ReleaseDirectMemoryHoles(start, len);
		}
	}
	return OK;
}

static int Bc5Ff_KernelCheckedReleaseDirectMemory(int64_t start, size_t len); // exp 0412 (tag ff412)
int KYTY_SYSV_ABI KernelCheckedReleaseDirectMemory(int64_t start, size_t len) { // exp 0412 (tag ff412)
	const int bc5_ff_result = Bc5Ff_KernelCheckedReleaseDirectMemory(start, len);
	if (bc5_ff_result != OK) [[unlikely]] ff412_report("KernelCheckedReleaseDirectMemory", bc5_ff_result, __builtin_return_address(0), {ff412::u(start), ff412::u(len)});
	return bc5_ff_result;
}
static int Bc5Ff_KernelCheckedReleaseDirectMemory(int64_t start, size_t len) {
	PRINT_NAME();

	LOGF("\t start = 0x%016" PRIx64 "\n"
	     "\t len   = 0x%016" PRIx64 "\n",
	     start, len);

	const int validation = ValidateDirectReleaseRange(start, len);
	if (validation != OK || len == 0) {
		return validation;
	}

	const int result = ReleaseDirectMemoryInternal(start, len);
	return result == KERNEL_ERROR_EACCES ? KERNEL_ERROR_ENOENT : result;
}

static int Bc5Ff_KernelMapDirectMemory(void** addr, size_t len, int prot, int flags,
                                        int64_t direct_memory_start, size_t alignment); // exp 0412 (tag ff412)
int KYTY_SYSV_ABI KernelMapDirectMemory(void** addr, size_t len, int prot, int flags,
                                        int64_t direct_memory_start, size_t alignment) { // exp 0412 (tag ff412)
	const int bc5_ff_result = Bc5Ff_KernelMapDirectMemory(addr, len, prot, flags, direct_memory_start, alignment);
	if (bc5_ff_result != OK) [[unlikely]] ff412_report("KernelMapDirectMemory", bc5_ff_result, __builtin_return_address(0), {ff412::u(addr), ff412::u(len), ff412::u(prot), ff412::u(flags), ff412::u(direct_memory_start), ff412::u(alignment)});
	return bc5_ff_result;
}
static int Bc5Ff_KernelMapDirectMemory(void** addr, size_t len, int prot, int flags,
                                        int64_t direct_memory_start, size_t alignment) {
	PRINT_NAME();

	bc5::load_stat::CountedLock<std::recursive_mutex> memory_operation_lock(g_memory_operation_mutex, bc5::load_stat::kMemLockWait); // exp 0415 (ls415): a lock_guard with the wait counted

	if (addr == nullptr) {
		return KERNEL_ERROR_EFAULT;
	}
	constexpr uint64_t PAGE_SIZE              = 0x4000;
	constexpr int      GUEST_MAP_FIXED        = 0x10;
	constexpr int      GUEST_MAP_NO_OVERWRITE = 0x80;

	if (len == 0 || (len & (PAGE_SIZE - 1u)) != 0 || direct_memory_start < 0 ||
	    (static_cast<uint64_t>(direct_memory_start) & (PAGE_SIZE - 1u)) != 0 ||
	    (alignment != 0 && (alignment & (alignment - 1u)) != 0 &&
	     (alignment & (PAGE_SIZE - 1u)) != 0)) {
		return KERNEL_ERROR_EINVAL;
	}
	if ((prot & PROT_CPU_EXEC) != 0) {
		// Experiment 0405 series e5, BC5_R3_EXEC_EINVAL (M26): EINVAL with nothing mapped, as measured in a title on
		// firmware 12.09 (PS5_PayloadSDK PROBE.md, cited by AnyPS5 4f41f4c37 docs/dev/debt/libkernel.md:190; AnyPS5
		// core/libs/prx/libkernel/DirectMemory/DirectMemory.cpp:1168, GPL-2.0-only). shadPS4 and sharpemu use EACCES, as
		// this file does today.
		return Bc5R3On(BC5_R3_ITEM_EXEC_EINVAL) ? KERNEL_ERROR_EINVAL : KERNEL_ERROR_EACCES;
	}

	bool fixed        = ((flags & GUEST_MAP_FIXED) != 0);
	bool no_overwrite = ((flags & GUEST_MAP_NO_OVERWRITE) != 0);

	VirtualMemory::Mode mode     = VirtualMemory::Mode::NoAccess;
	GpuAccessMode       gpu_mode = GpuAccessMode::NoAccess;

	if (!DecodeMemoryProtection(prot, &mode, &gpu_mode)) {
		return KERNEL_ERROR_EINVAL;
	}
	if (!g_physical_memory->CanMapDirect(static_cast<uint64_t>(direct_memory_start), len)) {
		return KERNEL_ERROR_ENOMEM;
	}

	auto                 in_addr              = reinterpret_cast<uint64_t>(*addr);
	uint64_t             out_addr             = 0;
	bool                 shared_backing       = false;
	bool                 consumed_reservation = false;
	VirtualRanges::Range consumed_range {};
	auto                 shared_failure = GuestBackingStore::FailureReason::None;
	// Direct mappings must remain views of the single backing object. Anonymous fallbacks break
	// aliasing and lose direct-memory contents when a range is unmapped and mapped again.
	auto map_shared_fixed = [&](uint64_t target_addr) -> bool {
		return g_guest_address_space->MapBacking(target_addr, len, direct_memory_start, mode,
		                                         &shared_failure);
	};
	auto map_consumed_reserved_fixed = [&]() {
		if (map_shared_fixed(in_addr)) {
			out_addr       = in_addr;
			shared_backing = true;
		}
	};

	if (fixed) {
		if (in_addr == 0 || (in_addr & (PAGE_SIZE - 1u)) != 0 ||
		    (alignment != 0 && in_addr % alignment != 0)) {
			return KERNEL_ERROR_EINVAL;
		}
		if (no_overwrite && g_virtual_ranges->HasOverlap(in_addr, len)) {
			return KERNEL_ERROR_ENOMEM;
		}

		std::vector<VirtualRanges::Range> reserved_ranges;
		if (g_virtual_ranges->QuerySpan(in_addr, len, &reserved_ranges) &&
		    std::all_of(reserved_ranges.begin(), reserved_ranges.end(), [](const auto& range) {
			    return range.type == VirtualRangeType::Reserved;
		    })) {
			UnmapGpuRange(in_addr, len);
			consumed_range = reserved_ranges.front();
			if (g_virtual_ranges->ConsumeReservedSpan(in_addr, len)) {
				consumed_reservation = true;
				map_consumed_reserved_fixed();
			}
		}
		if (!consumed_reservation && ReplaceFixedRangeWithReserved(in_addr, len) &&
		    g_virtual_ranges->ConsumeReservedSpan(in_addr, len, &consumed_range)) {
			consumed_reservation = true;
			map_consumed_reserved_fixed();
		}
		if (!consumed_reservation) {
			return KERNEL_ERROR_ENOMEM;
		}
	} else {
		constexpr size_t DEFAULT_ALIGNMENT = 0x4000;
		alignment                          = (alignment != 0 ? alignment : DEFAULT_ALIGNMENT);
		std::vector<VirtualRanges::Range> reserved_ranges;
		if (in_addr != 0 && g_virtual_ranges->QuerySpan(in_addr, len, &reserved_ranges) &&
		    std::all_of(reserved_ranges.begin(), reserved_ranges.end(), [](const auto& range) {
			    return range.type == VirtualRangeType::Reserved;
		    })) {
			UnmapGpuRange(in_addr, len);
			consumed_range = reserved_ranges.front();
			if (g_virtual_ranges->ConsumeReservedSpan(in_addr, len)) {
				consumed_reservation = true;
				if (map_shared_fixed(in_addr)) {
					out_addr       = in_addr;
					shared_backing = true;
				}
			}
		}
		if (!consumed_reservation) {
			out_addr = FindGuestFreeRange(in_addr, len, alignment);
			if (out_addr != 0) {
				UnmapGpuRange(out_addr, len);
				shared_backing = map_shared_fixed(out_addr);
				if (!shared_backing) {
					out_addr = 0;
				}
			}
		}
	}

	*addr = reinterpret_cast<void*>(out_addr);

	const char* shared_reason = "n/a";
	if (!shared_backing) {
		shared_reason = GuestBackingStore::GetFailureReasonName(shared_failure);
	}

	LOGF("\t in_addr  = 0x%016" PRIx64 "\n"
	     "\t out_addr = 0x%016" PRIx64 "\n"
	     "\t dmem     = 0x%016" PRIx64 "\n"
	     "\t size     = 0x%016" PRIx64 "\n"
	     "\t mode     = %s\n"
	     "\t flags    = 0x%08" PRIx32 "\n"
	     "\t align    = 0x%016" PRIx64 "\n"
	     "\t gpu_mode = %s\n"
	     "\t shared   = %s\n"
	     "\t reason   = %s\n",
	     in_addr, out_addr, static_cast<uint64_t>(direct_memory_start), len,
	     Common::EnumName(mode).c_str(), static_cast<uint32_t>(flags), alignment,
	     Common::EnumName(gpu_mode).c_str(), shared_backing ? "yes" : "no", shared_reason);

	if (out_addr == 0) {
		if (consumed_reservation) {
			g_virtual_ranges->Add(in_addr, len, 0, 0, 0, VirtualRangeType::Reserved,
			                      consumed_range.name);
		}
		return KERNEL_ERROR_ENOMEM;
	}

	if (!g_physical_memory->Map(out_addr, direct_memory_start, len, prot, mode, gpu_mode)) {
		LOGF_COLOR(Log::Color::Red, "\t [Fail]\n");
		EXIT_IF(!g_guest_address_space->UnmapBacking(out_addr, len));
		if (consumed_reservation) {
			EXIT_IF(!g_virtual_ranges->Add(in_addr, len, 0, 0, 0, VirtualRangeType::Reserved,
			                               consumed_range.name));
		}
		return KERNEL_ERROR_EBUSY;
	}

	PhysicalMemory::AllocatedBlock mapped_block {};
	g_physical_memory->Find(direct_memory_start, false, &mapped_block);
	if (!g_virtual_ranges->Add(out_addr, len, direct_memory_start, prot, mapped_block.memory_type,
	                           VirtualRangeType::Direct, "")) {
		GpuAccessMode rollback_gpu_mode = GpuAccessMode::NoAccess;
		EXIT_IF(!g_physical_memory->Unmap(out_addr, len, &rollback_gpu_mode));
		EXIT_IF(!g_guest_address_space->UnmapBacking(out_addr, len));
		if (consumed_reservation) {
			EXIT_IF(!g_virtual_ranges->Add(in_addr, len, 0, 0, 0, VirtualRangeType::Reserved,
			                               consumed_range.name));
		}
		return KERNEL_ERROR_EBUSY;
	}

	MapGpuRange(out_addr, len);

	if (g_alloc_callback != nullptr) {
		g_alloc_callback(out_addr, len);
	}

	LOGF_COLOR(Log::Color::Green, "\t [Ok]\n");

	return OK;
}

static int Bc5Ff_KernelMapDirectMemory2(void** addr, size_t len, int type, int prot, int flags,
                                         int64_t direct_memory_start, size_t alignment); // exp 0412 (tag ff412)
int KYTY_SYSV_ABI KernelMapDirectMemory2(void** addr, size_t len, int type, int prot, int flags,
                                         int64_t direct_memory_start, size_t alignment) { // exp 0412 (tag ff412)
	const int bc5_ff_result = Bc5Ff_KernelMapDirectMemory2(addr, len, type, prot, flags, direct_memory_start, alignment);
	if (bc5_ff_result != OK) [[unlikely]] ff412_report("KernelMapDirectMemory2", bc5_ff_result, __builtin_return_address(0), {ff412::u(addr), ff412::u(len), ff412::u(type), ff412::u(prot), ff412::u(flags), ff412::u(direct_memory_start)});
	return bc5_ff_result;
}
static int Bc5Ff_KernelMapDirectMemory2(void** addr, size_t len, int type, int prot, int flags,
                                         int64_t direct_memory_start, size_t alignment) {
	PRINT_NAME();

	bc5::load_stat::CountedLock<std::recursive_mutex> memory_operation_lock(g_memory_operation_mutex, bc5::load_stat::kMemLockWait); // exp 0415 (ls415): a lock_guard with the wait counted

	LOGF("\t type = %d\n", type);

	auto ret = KernelMapDirectMemory(addr, len, prot, flags, direct_memory_start, alignment);
	if (ret == OK && addr != nullptr && *addr != nullptr) {
		const auto out_addr = reinterpret_cast<uint64_t>(*addr);
		g_physical_memory->SetVirtualRangeMemoryType(out_addr, len, type);
		g_virtual_ranges->SetMemoryType(out_addr, len, type);
	}

	return ret;
}

static int Bc5Ff_KernelMapNamedDirectMemory(void** addr, size_t len, int prot, int flags,
                                             int64_t direct_memory_start, size_t alignment,
                                             const char* name); // exp 0412 (tag ff412)
int KYTY_SYSV_ABI KernelMapNamedDirectMemory(void** addr, size_t len, int prot, int flags,
                                             int64_t direct_memory_start, size_t alignment,
                                             const char* name) { // exp 0412 (tag ff412)
	const int bc5_ff_result = Bc5Ff_KernelMapNamedDirectMemory(addr, len, prot, flags, direct_memory_start, alignment, name);
	if (bc5_ff_result != OK) [[unlikely]] ff412_report("KernelMapNamedDirectMemory", bc5_ff_result, __builtin_return_address(0), {ff412::u(addr), ff412::u(len), ff412::u(prot), ff412::u(flags), ff412::u(direct_memory_start), ff412::u(alignment)});
	return bc5_ff_result;
}
static int Bc5Ff_KernelMapNamedDirectMemory(void** addr, size_t len, int prot, int flags,
                                             int64_t direct_memory_start, size_t alignment,
                                             const char* name) {
	PRINT_NAME();

	bc5::load_stat::CountedLock<std::recursive_mutex> memory_operation_lock(g_memory_operation_mutex, bc5::load_stat::kMemLockWait); // exp 0415 (ls415): a lock_guard with the wait counted

	LOGF("\t name = %s\n", name != nullptr ? name : "(null)");

	if (name == nullptr) {
		return KERNEL_ERROR_EFAULT;
	}

	if (std::strlen(name) >= KERNEL_MAXIMUM_NAME_LENGTH) {
		return KERNEL_ERROR_ENAMETOOLONG;
	}

	auto ret = KernelMapDirectMemory(addr, len, prot, flags, direct_memory_start, alignment);
	if (ret == OK && addr != nullptr) {
		g_physical_memory->SetVirtualRangeName(reinterpret_cast<uint64_t>(*addr), len, name);
		g_virtual_ranges->Rename(reinterpret_cast<uint64_t>(*addr), len, name);
	}

	return ret;
}

int KYTY_SYSV_ABI KernelIsAddressSanitizerEnabled() {
	PRINT_NAME();

	return 0;
}

int KYTY_SYSV_ABI KernelQueryMemoryProtection(void* addr, void** start, void** end, int* prot) {
	PRINT_NAME();

	bc5::load_stat::CountedLock<std::recursive_mutex> memory_operation_lock(g_memory_operation_mutex, bc5::load_stat::kMemLockWait); // exp 0415 (ls415): a lock_guard with the wait counted

	// Experiment 0405 series e5, BC5_R3_NULL_ARGS (M21): NULL is an unmapped address: EACCES, as for any unmapped address
	// below (shadPS4 60c42b9 src/core/memory.cpp:1024-1030, an address below the mappable base gives EACCES;
	// GPL-2.0-or-later; AnyPS5 4f41f4c37 core/libs/prx/libkernel/DirectMemory/Export.cpp:484-494 answers through
	// sceKernelVirtualQuery, GPL-2.0-only).
	if (addr == nullptr && Bc5R3On(BC5_R3_ITEM_NULL_ARGS)) {
		return KERNEL_ERROR_EACCES;
	}
	EXIT_NOT_IMPLEMENTED(addr == nullptr);

	VirtualRanges::Range range {};
	if (!g_virtual_ranges->Query(reinterpret_cast<uint64_t>(addr), 0, &range)) {
		return KERNEL_ERROR_EACCES;
	}

	if (start != nullptr) {
		*start = reinterpret_cast<void*>(range.start);
	}
	if (end != nullptr) {
		*end = reinterpret_cast<void*>(range.start + range.size);
	}
	if (prot != nullptr) {
		*prot = range.protection;
	}

	return OK;
}

static bool ReplaceFixedRangeWithReserved(uint64_t start, uint64_t size) {

	struct ReplacedChunk {
		VirtualRanges::Range                        range {};
		VirtualMemory::Mode                         mode     = VirtualMemory::Mode::NoAccess;
		GpuAccessMode                               gpu_mode = GpuAccessMode::NoAccess;
		std::vector<FlexibleMemory::AllocatedBlock> flexible_blocks;
		bool                                        host_unmapped    = false;
		bool                                        backend_unmapped = false;
	};

	std::vector<ReplacedChunk> chunks;
	const auto                 end     = start + size;
	auto                       current = start;

	while (current < end) {
		VirtualRanges::Range range {};
		if (!g_virtual_ranges->Query(current, 1, &range)) {
			break;
		}
		if (range.start >= end) {
			break;
		}
		if (current < range.start) {
			current = std::min<uint64_t>(end, range.start);
			continue;
		}

		const auto range_end = range.start + range.size;
		const auto chunk     = std::min<uint64_t>(end, range_end) - current;

		ReplacedChunk replaced {};
		replaced.range       = range;
		replaced.range.start = current;
		replaced.range.size  = chunk;
		if (range.type == VirtualRangeType::Direct) {
			replaced.range.offset += current - range.start;
		}
		DecodeMemoryProtection(replaced.range.protection, &replaced.mode, &replaced.gpu_mode);
		// BC5 (experiment 0036): a fixed mapping over live memory replaces it silently; trace it.
		if (range.type != VirtualRangeType::Reserved && range.type != VirtualRangeType::PoolReserved) {
			static const bool trace_env = (BC5_DIAG_ENV("KYTY_BC5_AMM_TRACE") != nullptr);
			const bool trace = trace_env && ::Log::Bc5LoggingOn();
			if (trace) {
				std::fprintf(stderr,
				             "amm trace: fixed map over live range: new 0x%016" PRIx64 "+0x%" PRIx64
				             " replaces type %d '%s' 0x%016" PRIx64 "+0x%" PRIx64 "\n",
				             start, size, static_cast<int>(range.type), range.name, range.start, range.size);
			}
		}
		if (range.type == VirtualRangeType::Direct &&
		    !g_guest_address_space->BackingContains(current, chunk)) {
			return false;
		}
		if (range.type == VirtualRangeType::Flexible &&
		    !g_flexible_memory->Snapshot(current, chunk, &replaced.flexible_blocks)) {
			return false;
		}
		if (range.type == VirtualRangeType::Pooled) {
			EXIT("reserve-fixed replacement of pooled memory is unsupported: addr=0x%016" PRIx64
			     " size=0x%016" PRIx64 "\n",
			     replaced.range.start, replaced.range.size);
		}
		chunks.push_back(replaced);

		current += chunk;
	}

	auto restore_chunks = [&chunks]() -> bool {
		bool ok = true;
		for (auto it = chunks.rbegin(); it != chunks.rend(); ++it) {
			const auto& chunk            = *it;
			bool        host_restored    = true;
			bool        backend_restored = true;

			if (chunk.range.type == VirtualRangeType::Direct) {
				if (chunk.host_unmapped) {
					host_restored = g_guest_address_space->MapBacking(
					    chunk.range.start, chunk.range.size, chunk.range.offset, chunk.mode);
				}
				if (chunk.backend_unmapped) {
					backend_restored = g_physical_memory->Map(
					    chunk.range.start, chunk.range.offset, chunk.range.size,
					    chunk.range.protection, chunk.mode, chunk.gpu_mode);
				}
			} else if (chunk.range.type == VirtualRangeType::Flexible && chunk.backend_unmapped) {
				host_restored = backend_restored =
				    g_flexible_memory->Restore(chunk.flexible_blocks);
			} else if (IsPrivateCommittedRangeType(chunk.range.type) && chunk.host_unmapped) {
				host_restored =
				    g_guest_address_space->Commit(chunk.range.start, chunk.range.size, chunk.mode);
			}
			ok = host_restored && backend_restored && ok;
		}

		for (const auto& chunk: chunks) {
			const bool range_restored = g_virtual_ranges->Add(
			    chunk.range.start, chunk.range.size, chunk.range.offset, chunk.range.protection,
			    chunk.range.memory_type, chunk.range.type, chunk.range.name,
			    chunk.range.disallow_merge);
			ok = range_restored && ok;
		}
		if (ok) {
			for (const auto& chunk: chunks) {
				if (IsCommittedRangeType(chunk.range.type)) {
					MapGpuRange(chunk.range.start, chunk.range.size);
				}
			}
		}
		return ok;
	};

	UnmapGpuRange(start, size);
	g_virtual_ranges->Remove(start, size);

	for (auto& chunk: chunks) {
		GpuAccessMode gpu_mode = GpuAccessMode::NoAccess;
		bool          unmapped = true;

		if (chunk.range.type == VirtualRangeType::Direct) {
			if (!g_guest_address_space->UnmapBacking(chunk.range.start, chunk.range.size)) {
				unmapped = false;
			} else {
				chunk.host_unmapped = true;
			}
			if (unmapped) {
				unmapped = g_physical_memory->Unmap(chunk.range.start, chunk.range.size, &gpu_mode);
				chunk.gpu_mode         = gpu_mode;
				chunk.backend_unmapped = unmapped;
			}
		} else if (chunk.range.type == VirtualRangeType::Flexible) {
			unmapped = g_flexible_memory->Unmap(chunk.range.start, chunk.range.size, &gpu_mode);
			chunk.host_unmapped    = unmapped;
			chunk.backend_unmapped = unmapped;
			chunk.gpu_mode         = gpu_mode;
		} else if (IsPrivateCommittedRangeType(chunk.range.type)) {
			unmapped = g_guest_address_space->ReleaseCommitted(chunk.range.start, chunk.range.size);
			chunk.host_unmapped    = unmapped;
			chunk.backend_unmapped = unmapped;
		} else if (IsReservedRangeType(chunk.range.type)) {
			unmapped = g_guest_address_space->ReleaseFree(chunk.range.start, chunk.range.size);
		} else {
			unmapped = false;
		}
		if (chunk.range.type == VirtualRangeType::Direct) {
			chunk.gpu_mode         = gpu_mode;
			chunk.backend_unmapped = chunk.backend_unmapped && unmapped;
		}

		if (!unmapped) {
			LOGF_COLOR(Log::Color::Red,
			           "\t reserve-fixed replace: backend unmap failed at 0x%016" PRIx64
			           ", size=0x%016" PRIx64 ", type=%s\n",
			           chunk.range.start, chunk.range.size,
			           Common::EnumName(chunk.range.type).c_str());
			if (!restore_chunks()) {
				EXIT("reserve-fixed backend-unmap rollback failed\n");
			}
			return false;
		}
	}

	if (!g_guest_address_space->ReserveFixed(start, size)) {
		if (!restore_chunks()) {
			EXIT("reserve-fixed host-reservation rollback failed\n");
		}
		return false;
	}

	bool range_added = false;
#if defined(KYTY_VIRTUAL_MEMORY_ALLOCATION_TESTS)
	if (g_test_fail_next_fixed_reserve_range_add) {
		g_test_fail_next_fixed_reserve_range_add = false;
	} else
#endif
	{
		range_added =
		    g_virtual_ranges->Add(start, size, 0, 0, 0, VirtualRangeType::Reserved, "anon");
	}
	if (!range_added) {
		LOGF_COLOR(Log::Color::Red,
		           "\t reserve-fixed replace: range add failed at 0x%016" PRIx64
		           ", size=0x%016" PRIx64 "\n",
		           start, size);
		if (!restore_chunks()) {
			EXIT("reserve-fixed range-registration rollback failed\n");
		}
		auto free_start = start;
		for (const auto& chunk: chunks) {
			if (free_start < chunk.range.start &&
			    !g_guest_address_space->ReleaseFree(free_start, chunk.range.start - free_start)) {
				EXIT("reserve-fixed range-registration gap cleanup failed\n");
			}
			free_start = chunk.range.start + chunk.range.size;
		}
		if (free_start < start + size &&
		    !g_guest_address_space->ReleaseFree(free_start, start + size - free_start)) {
			EXIT("reserve-fixed range-registration tail cleanup failed\n");
		}
		return false;
	}

	for (const auto& chunk: chunks) {
		if (g_free_callback != nullptr && IsCommittedRangeType(chunk.range.type)) {
			g_free_callback(chunk.range.start, chunk.range.size);
		}
	}

	return true;
}

static int Bc5Ff_KernelReserveVirtualRange(void** addr, size_t len, int flags, size_t alignment); // exp 0412 (tag ff412)
int KYTY_SYSV_ABI KernelReserveVirtualRange(void** addr, size_t len, int flags, size_t alignment) { // exp 0412 (tag ff412)
	const int bc5_ff_result = Bc5Ff_KernelReserveVirtualRange(addr, len, flags, alignment);
	if (bc5_ff_result != OK) [[unlikely]] ff412_report("KernelReserveVirtualRange", bc5_ff_result, __builtin_return_address(0), {ff412::u(addr), ff412::u(len), ff412::u(flags), ff412::u(alignment)});
	return bc5_ff_result;
}
static int Bc5Ff_KernelReserveVirtualRange(void** addr, size_t len, int flags, size_t alignment) {
	PRINT_NAME();

	bc5::load_stat::CountedLock<std::recursive_mutex> memory_operation_lock(g_memory_operation_mutex, bc5::load_stat::kMemLockWait); // exp 0415 (ls415): a lock_guard with the wait counted

	const auto in_addr = (addr != nullptr ? reinterpret_cast<uint64_t>(*addr) : 0);

	LOGF("\t in_addr   = 0x%016" PRIx64 "\n"
	     "\t len       = 0x%016" PRIx64 "\n"
	     "\t flags     = 0x%08" PRIx32 "\n"
	     "\t alignment = 0x%016" PRIx64 "\n",
	     in_addr, len, flags, alignment);

	constexpr size_t PAGE_SIZE              = 0x4000;
	constexpr int    GUEST_MAP_FIXED        = 0x10;
	constexpr int    GUEST_MAP_NO_OVERWRITE = 0x80;

	if (addr == nullptr || len == 0 || (len & (PAGE_SIZE - 1)) != 0) {
		return KERNEL_ERROR_EINVAL;
	}
	if (alignment != 0 && (alignment & (alignment - 1)) != 0 &&
	    (alignment & (PAGE_SIZE - 1)) != 0) {
		return KERNEL_ERROR_EINVAL;
	}

	uint64_t out_addr            = 0;
	bool     range_already_added = false;
	if ((flags & GUEST_MAP_FIXED) != 0) {
		if (in_addr == 0 || (in_addr & (PAGE_SIZE - 1)) != 0) {
			return KERNEL_ERROR_EINVAL;
		}
		if ((flags & GUEST_MAP_NO_OVERWRITE) != 0 && g_virtual_ranges->HasOverlap(in_addr, len)) {
			return KERNEL_ERROR_ENOMEM;
		}
		if (ReplaceFixedRangeWithReserved(in_addr, len)) {
			out_addr            = in_addr;
			range_already_added = true;
		}
	} else {
		alignment = (alignment != 0 ? alignment : PAGE_SIZE);
		out_addr  = FindGuestFreeRange(in_addr, len, alignment);
		if (out_addr != 0) {
			UnmapGpuRange(out_addr, len);
		}
	}

	if (out_addr == 0) {
		return KERNEL_ERROR_ENOMEM;
	}

	if (!range_already_added &&
	    !g_virtual_ranges->Add(out_addr, len, 0, 0, 0, VirtualRangeType::Reserved, "anon")) {
		return KERNEL_ERROR_EBUSY;
	}

	*addr = reinterpret_cast<void*>(out_addr);

	LOGF("\t out_addr  = 0x%016" PRIx64 "\n", out_addr);

	return OK;
}

#if defined(KYTY_VIRTUAL_MEMORY_ALLOCATION_TESTS)
void TestFailNextPhysicalMemoryUnmap() {
	TestFailPhysicalMemoryUnmapAfter(0);
}

void TestFailPhysicalMemoryUnmapAfter(uint32_t successful_unmaps) {
	g_test_physical_memory_unmaps_before_failure = successful_unmaps;
}

void TestFailGuestBackingStoreUnmapAfter(uint32_t successful_unmaps) {
	g_test_backing_store_unmaps_before_failure = successful_unmaps;
}

void TestFailNextFixedReserveRangeRegistration() {
	g_test_fail_next_fixed_reserve_range_add = true;
}

bool TestPlaceholderRangeIsFree(uint64_t vaddr, uint64_t size) {
	return g_guest_address_space->TestContainsFree(vaddr, size);
}

bool TestGuestAddressRangeIsOwned(uint64_t vaddr, uint64_t size) {
	return g_guest_address_space->Owns(vaddr, size);
}

bool TestGuestBackingOutsideAddressSpace() {
	return !g_guest_address_space->OverlapsOwned(g_guest_address_space->GetBackingBase(),
	                                             g_guest_address_space->GetBackingSize());
}

uint64_t TestGuestBackingSize() {
	return g_guest_address_space->GetBackingSize();
}

bool TestGuestFreeRangeBounds() {
	return GuestFreeRangeContains(0x10000, 0x20000, 0x18000, 0x4000) &&
	       !GuestFreeRangeContains(0x10000, 0x20000, 0x40000, 0x4000) &&
	       !GuestFreeRangeContains(UINT64_MAX - 0x1000, 0x2000, UINT64_MAX - 0x800, 0x400);
}
#endif

bool KernelHandleReservedRangeAccessViolation(uint64_t vaddr) {
	bc5::load_stat::CountedLock<std::recursive_mutex> memory_operation_lock(g_memory_operation_mutex, bc5::load_stat::kMemLockWait); // exp 0415 (ls415): a lock_guard with the wait counted

	VirtualRanges::Range range {};
	if (!g_virtual_ranges->Query(vaddr, 0, &range) ||
	    std::strncmp(range.name, "AMM", KERNEL_MAXIMUM_NAME_LENGTH) != 0) {
		return false;
	}
	// Experiment 0035 tried committing such pages lazily (removed in cleanup batch 3): the AMM
	// failures seen were the fixed window reservation wiping the game's mappings, not pages it
	// expected to appear.
	ff412_death(vaddr); // exp 0412 (tag ff412)
	EXIT("AMM virtual-memory unmap is unsupported: addr=0x%016" PRIx64 "\n", vaddr);
	return false;
}

int KYTY_SYSV_ABI KernelVirtualQuery(const void* addr, int flags, VirtualQueryInfo* info,
                                     uint64_t info_size) {
	PRINT_NAME();

	bc5::load_stat::CountedLock<std::recursive_mutex> memory_operation_lock(g_memory_operation_mutex, bc5::load_stat::kMemLockWait); // exp 0415 (ls415): a lock_guard with the wait counted

	auto vaddr = reinterpret_cast<uint64_t>(addr);

	LOGF("\t addr      = 0x%016" PRIx64 "\n"
	     "\t flags     = 0x%08" PRIx32 "\n"
	     "\t info_size = 0x%016" PRIx64 "\n",
	     vaddr, flags, info_size);

	// Experiment 0405 series e5, BC5_R3_QUERY_SIZE (M30): an info size larger than the struct is accepted; only the
	// struct is written (AnyPS5 4f41f4c37 core/libs/prx/libkernel/DirectMemory/Export.cpp:373, GPL-2.0-only; sharpemu
	// 514d766 KernelMemoryCompatExports.cs:3579, GPL-2.0-or-later; titles pass other sizes than 0x48, AnyPS5
	// docs/dev/debt/libkernel.md:361).
	if (info == nullptr ||
	    (Bc5R3On(BC5_R3_ITEM_QUERY_SIZE) ? info_size < sizeof(VirtualQueryInfo) : info_size != sizeof(VirtualQueryInfo)) ||
	    (flags != 0 && flags != 1)) {
		return KERNEL_ERROR_EINVAL;
	}

	VirtualRanges::Range candidate {};
	if (!g_virtual_ranges->Query(vaddr, flags, &candidate)) {
		return KERNEL_ERROR_EACCES;
	}

	std::memset(info, 0, sizeof(VirtualQueryInfo));
	info->start        = candidate.start;
	info->end          = candidate.start + candidate.size;
	info->offset       = candidate.offset;
	info->protection   = candidate.protection;
	info->memory_type  = candidate.memory_type;
	info->is_flexible  = (candidate.type == VirtualRangeType::Flexible ? 1 : 0);
	info->is_direct    = (candidate.type == VirtualRangeType::Direct ? 1 : 0);
	info->is_stack     = (candidate.type == VirtualRangeType::Stack ? 1 : 0);
	info->is_pooled    = (IsPooledRangeType(candidate.type) ? 1 : 0);
	info->is_committed = (IsCommittedRangeType(candidate.type) ? 1 : 0);
	info->is_gpu_prt   = IsInPrtAperture(vaddr);
	CopyVirtualRangeName(info->name, candidate.name);

	static std::atomic<uint32_t> log_count {0};
	if (log_count.fetch_add(1) < 64) {
		LOGF("\t start       = 0x%016" PRIx64 "\n"
		     "\t end         = 0x%016" PRIx64 "\n"
		     "\t offset      = 0x%016" PRIx64 "\n"
		     "\t protection  = 0x%08" PRIx32 "\n"
		     "\t memory_type = %d\n"
		     "\t flexible    = %d\n"
		     "\t direct      = %d\n"
		     "\t name        = %s\n",
		     static_cast<uint64_t>(info->start), static_cast<uint64_t>(info->end), info->offset,
		     info->protection, info->memory_type, static_cast<int>(info->is_flexible),
		     static_cast<int>(info->is_direct), info->name);
	}

	return OK;
}

// Experiment 0329: sceKernelMlock (3k6kx-zOOSQ), libc.prx's import — the pages of a mapped range are pinned in RAM.
// Every page of the range must lie in a mapped virtual range of the process (ENOMEM otherwise, as FreeBSD's mlock
// answers an unmapped page); EINVAL for a null pointer or a length of zero. The host pins the same pages with
// mlock(2) (AnyPS5's DirectMemory/Export.cpp:717 does the same), rounded to the host's pages; the host's own
// refusal — ENOMEM at RLIMIT_MEMLOCK, EPERM — is returned as the console's error of the same name, logged once.
int KYTY_SYSV_ABI KernelMlock(void* addr, size_t len) {
	PRINT_NAME();

	bc5::load_stat::CountedLock<std::recursive_mutex> memory_operation_lock(g_memory_operation_mutex, bc5::load_stat::kMemLockWait); // exp 0415 (ls415): a lock_guard with the wait counted

	const auto vaddr = reinterpret_cast<uint64_t>(addr);

	LOGF("\t addr = 0x%016" PRIx64 ", len = 0x%" PRIx64 "\n", vaddr, static_cast<uint64_t>(len));

	if (addr == nullptr || len == 0 || vaddr > UINT64_MAX - len) {
		return KERNEL_ERROR_EINVAL;
	}

	const uint64_t end = vaddr + len;
	for (uint64_t pos = vaddr; pos < end;) {
		VirtualRanges::Range range {};
		if (!g_virtual_ranges->Query(pos, 0, &range) || range.type == VirtualRangeType::Reserved ||
		    pos < range.start || range.start + range.size <= pos) {
			LOGF("\t 0x%016" PRIx64 " is not mapped: ENOMEM\n", pos);
			return KERNEL_ERROR_ENOMEM;
		}
		pos = range.start + range.size;
	}

#if KYTY_PLATFORM == KYTY_PLATFORM_LINUX
	constexpr uint64_t host_page = 4096;
	const uint64_t     first     = vaddr & ~(host_page - 1);
	if (::mlock(reinterpret_cast<void*>(first), static_cast<size_t>(end - first)) != 0) {
		const int saved = errno;
		static std::atomic<uint32_t> logged {0};
		if (logged.fetch_add(1) < 4) {
			LOGF("\t host mlock failed: errno %d (RLIMIT_MEMLOCK? see ulimit -l)\n", saved);
			std::fprintf(stderr, "[bc5] sceKernelMlock: the host refused to pin 0x%" PRIx64 " bytes at 0x%016" PRIx64
			                     " (errno %d)\n",
			             static_cast<uint64_t>(end - first), first, saved);
		}
		return saved == EPERM ? KERNEL_ERROR_EPERM : saved == ENOMEM ? KERNEL_ERROR_ENOMEM : KERNEL_ERROR_EINVAL;
	}
#endif

	return OK;
}

int KYTY_SYSV_ABI KernelIsStack(void* addr, void** start, void** end) {
	PRINT_NAME();

	bc5::load_stat::CountedLock<std::recursive_mutex> memory_operation_lock(g_memory_operation_mutex, bc5::load_stat::kMemLockWait); // exp 0415 (ls415): a lock_guard with the wait counted

	auto vaddr = reinterpret_cast<uint64_t>(addr);

	LOGF("\t addr = 0x%016" PRIx64 "\n", vaddr);

	VirtualRanges::Range candidate {};
	if (!g_virtual_ranges->Query(vaddr, 0, &candidate)) {
		return KERNEL_ERROR_EACCES;
	}

	uint64_t stack_start = 0;
	uint64_t stack_end   = 0;
	if (candidate.type == VirtualRangeType::Stack) {
		stack_start = candidate.start;
		stack_end   = candidate.start + candidate.size;
	}

	if (start != nullptr) {
		*start = reinterpret_cast<void*>(stack_start);
	}

	if (end != nullptr) {
		*end = reinterpret_cast<void*>(stack_end);
	}

	LOGF("\t start = 0x%016" PRIx64 "\n"
	     "\t end   = 0x%016" PRIx64 "\n",
	     stack_start, stack_end);

	return OK;
}

int KYTY_SYSV_ABI KernelAvailableFlexibleMemorySize(size_t* size) {
	PRINT_NAME();

	bc5::load_stat::CountedLock<std::recursive_mutex> memory_operation_lock(g_memory_operation_mutex, bc5::load_stat::kMemLockWait); // exp 0415 (ls415): a lock_guard with the wait counted

	if (size == nullptr) {
		return KERNEL_ERROR_EINVAL;
	}

	*size = g_flexible_memory->Available();

	LOGF("\t *size = 0x%016" PRIx64 "\n", *size);

	return OK;
}

int KYTY_SYSV_ABI KernelConfiguredFlexibleMemorySize(size_t* size) {
	PRINT_NAME();

	if (size == nullptr) {
		return KERNEL_ERROR_EINVAL;
	}

	*size = FlexibleMemory::Size();

	LOGF("\t *size = 0x%016" PRIx64 "\n", *size);

	return OK;
}

static int ProgramProtection(VirtualMemory::Mode mode) {
	const auto protection = static_cast<int>(mode);
	if ((protection & ~(PROT_CPU_READ | PROT_CPU_WRITE | PROT_CPU_EXEC)) != 0) {
		EXIT("unsupported program-memory protection: 0x%08x\n", protection);
	}
	return protection;
}

static std::vector<VirtualRanges::Range> RequireGuestRuntimeMemory(uint64_t vaddr, uint64_t size) {
	std::vector<VirtualRanges::Range> ranges;
	if (g_virtual_ranges == nullptr || !g_virtual_ranges->QuerySpan(vaddr, size, &ranges) ||
	    std::any_of(ranges.begin(), ranges.end(), [](const auto& range) {
		    return range.type != VirtualRangeType::Code && range.type != VirtualRangeType::Runtime;
	    })) {
		EXIT("guest runtime range is not fully mapped: addr=0x%016" PRIx64 " size=0x%016" PRIx64
		     "\n",
		     vaddr, size);
	}
	return ranges;
}

static uint64_t AllocateGuestRuntimeMemory(uint64_t search_addr, uint64_t size,
                                           VirtualMemory::Mode mode, const char* name,
                                           VirtualRangeType type, bool fixed) {
	bc5::load_stat::CountedLock<std::recursive_mutex> memory_operation_lock(g_memory_operation_mutex, bc5::load_stat::kMemLockWait); // exp 0415 (ls415): a lock_guard with the wait counted

	constexpr uint64_t GuestPageSize = 0x4000;
	if (size == 0 || size > UINT64_MAX - (GuestPageSize - 1u) || name == nullptr ||
	    (fixed && (search_addr == 0 || (search_addr & (GuestPageSize - 1u)) != 0))) {
		return 0;
	}
	const auto mapped_size = (size + GuestPageSize - 1u) & ~(GuestPageSize - 1u);
	const auto vaddr =
	    fixed ? search_addr : FindGuestFreeRange(search_addr, mapped_size, GuestPageSize);
	if (vaddr == 0 || g_virtual_ranges->HasOverlap(vaddr, mapped_size)) {
		return 0;
	}
	UnmapGpuRange(vaddr, mapped_size);
	if (!g_guest_address_space->Commit(vaddr, mapped_size, mode)) {
		return 0;
	}
	if (!g_virtual_ranges->Add(vaddr, mapped_size, 0, ProgramProtection(mode), 0, type, name)) {
		EXIT_IF(!g_guest_address_space->ReleaseCommitted(vaddr, mapped_size));
		return 0;
	}
	MapGpuRange(vaddr, mapped_size);
	return vaddr;
}

uint64_t AllocateProgramMemory(uint64_t search_addr, uint64_t size, VirtualMemory::Mode mode,
                               const char* name) {
	return AllocateGuestRuntimeMemory(search_addr, size, mode, name, VirtualRangeType::Code, false);
}

void SetProgramMemoryProtection(uint64_t vaddr, uint64_t size, VirtualMemory::Mode mode) {
	bc5::load_stat::CountedLock<std::recursive_mutex> memory_operation_lock(g_memory_operation_mutex, bc5::load_stat::kMemLockWait); // exp 0415 (ls415): a lock_guard with the wait counted

	const auto ranges = RequireGuestRuntimeMemory(vaddr, size);
	if (std::any_of(ranges.begin(), ranges.end(),
	                [](const auto& range) { return range.type != VirtualRangeType::Code; })) {
		EXIT("program-memory range is not fully mapped: addr=0x%016" PRIx64 " size=0x%016" PRIx64
		     "\n",
		     vaddr, size);
	}

	const auto host_mode = VirtualMemory::IsExecute(mode) ? VirtualMemory::Mode::ExecuteReadWrite
	                                                      : VirtualMemory::Mode::ReadWrite;
	EXIT_IF(!g_guest_address_space->Protect(vaddr, size, host_mode));
	g_virtual_ranges->Protect(vaddr, size, ProgramProtection(mode));
}

uint64_t AllocateRuntimeMemory(uint64_t search_addr, uint64_t size, VirtualMemory::Mode mode,
                               const char* name, bool fixed) {
	return AllocateGuestRuntimeMemory(search_addr, size, mode, name, VirtualRangeType::Runtime,
	                                  fixed);
}

uint64_t AllocateGuestStackMemory(uint64_t search_addr, uint64_t size, VirtualMemory::Mode mode,
                                  const char* name) {
	const auto vaddr =
	    AllocateGuestRuntimeMemory(search_addr, size, mode, name, VirtualRangeType::Stack, false);
	if (vaddr != 0 && g_alloc_callback != nullptr) {
		g_alloc_callback(vaddr, size);
	}
	return vaddr;
}

bool ProtectGuestMemory(uint64_t vaddr, uint64_t size, VirtualMemory::Mode mode,
                        VirtualMemory::Mode* old_mode) {
	bc5::load_stat::CountedLock<std::recursive_mutex> memory_operation_lock(g_memory_operation_mutex, bc5::load_stat::kMemLockWait); // exp 0415 (ls415): a lock_guard with the wait counted
	constexpr uint64_t                    GuestPageSize = 0x4000;
	if (vaddr == 0 || size == 0 || size > UINT64_MAX - (vaddr & (GuestPageSize - 1u))) {
		return false;
	}
	const auto aligned_addr = vaddr & ~(GuestPageSize - 1u);
	const auto aligned_size =
	    (size + (vaddr - aligned_addr) + GuestPageSize - 1u) & ~(GuestPageSize - 1u);
	const auto ranges = RequireGuestRuntimeMemory(aligned_addr, aligned_size);
	if (old_mode != nullptr) {
		*old_mode = static_cast<VirtualMemory::Mode>(
		    ranges.front().protection & (PROT_CPU_READ | PROT_CPU_WRITE | PROT_CPU_EXEC));
	}
	if (!g_guest_address_space->Protect(aligned_addr, aligned_size, mode)) {
		return false;
	}
	g_virtual_ranges->Protect(aligned_addr, aligned_size, ProgramProtection(mode));
	return true;
}

bool ProtectGuestHostMemory(uint64_t vaddr, uint64_t size, VirtualMemory::Mode mode) {
	return g_guest_address_space != nullptr &&
	       g_guest_address_space->ProtectTransient(vaddr, size, mode);
}

bool FreeGuestMemory(uint64_t vaddr, uint64_t size) {
	bc5::load_stat::CountedLock<std::recursive_mutex> memory_operation_lock(g_memory_operation_mutex, bc5::load_stat::kMemLockWait); // exp 0415 (ls415): a lock_guard with the wait counted

	constexpr uint64_t GuestPageSize = 0x4000;
	if (vaddr == 0 || size == 0 || size > UINT64_MAX - (GuestPageSize - 1u)) {
		return false;
	}
	const auto mapped_size = (size + GuestPageSize - 1u) & ~(GuestPageSize - 1u);
	(void)RequireGuestRuntimeMemory(vaddr, mapped_size);
	UnmapGpuRange(vaddr, mapped_size);
	return FreeGuestMemoryOwner(vaddr, mapped_size);
}

// ---- BC5 experiment 0405 (series e6 of experiment 0401), KYTY_BC5_JIT_SHM: JIT shared memory (exp 0405 R3 M31) ----
// What a JIT engine (an emulator, a script runtime) asks for to write code through one view and run it through another.
// libKernel.cpp registers the three calls under the NIDs of their public names only when KYTY_BC5_JIT_SHM is on; with it
// off nothing here is reachable and today's path is unchanged. Behaviour of AnyPS5 4f41f4c375f5 (GPL-2.0-only):
// core/libs/prx/libkernel/DirectMemory/Jit.cpp:197-237, its note docs/dev/debt/libkernel.md:175 and the close path
// core/libs/prx/libkernel/File/src/Open.cpp:312-320. Adapted, no code copied; the names and the structure are ours.
//   create (label, bytes, ceiling, handle out): a new area of `bytes` whose views never get more than `ceiling` (CPU
//       read 1, write 2, execute 4). The label is not used. No handle out, `bytes` 0 or not a multiple of the 16 KiB
//       guest page, or other bits in `ceiling`: EINVAL. The host out of descriptors or memory: EMFILE, ENFILE or ENOMEM.
//   alias (handle, ceiling, handle out): one more handle on the same area, with a ceiling no wider than the handle's.
//       No handle out or other bits: EINVAL; not an area's handle: EBADF; a wider ceiling: EACCES.
//   map (handle, prot, address in/out): the whole area at a free guest address; the address passed in is a hint only,
//       and the address chosen is written back. No address or other bits: EINVAL; not an area's handle: EBADF; prot
//       above the handle's ceiling: EACCES.
//   Write and execute count as read when two protections are compared. A closed handle is gone (libKernel.cpp's close
//   wrappers call Bc5JitHandleClose); views stay mapped until munmap, and an area lives as long as one of its views.
// Host side, Linux: an area is a memfd of `bytes`. A view is a guest runtime range made by AllocateGuestRuntimeMemory (the
// range table and the guest address space, so VirtualQuery, QueryMemoryProtection, mprotect and munmap treat it as any
// other committed range), whose host pages are then replaced by a MAP_SHARED mapping of the memfd: every view of an area
// shows the same bytes. munmap puts the placeholder back over it. As everywhere in this file the host view is read-write,
// plus execute when prot has it; the range table keeps the guest's prot. Areas count against no memory budget. Other
// hosts: create answers ENOMEM. Handles are our own numbers, 0x40000 up and never reused, clear of the file system's
// descriptors (3 up), the sockets (128-1023) and the epoll ids (1024 up).
// TODO(verify): the error answers and the budget are not measured on a console (AnyPS5's note says the same).
static constexpr int      BC5_JIT_CPU_BITS     = PROT_CPU_READ | PROT_CPU_WRITE | PROT_CPU_EXEC;
static constexpr uint64_t BC5_JIT_PAGE         = 0x4000; // the guest page, as GuestPageSize in this file
static constexpr int      BC5_JIT_FIRST_HANDLE = 0x40000;
static constexpr int      BC5_JIT_LAST_HANDLE  = 0x7fffffff;
static constexpr char     BC5_JIT_VIEW_NAME[]  = "bc5-jit";

// The bits a protection grants, write and execute taken to include read.
static int Bc5JitGrants(int prot) {
	return (prot & (PROT_CPU_WRITE | PROT_CPU_EXEC)) != 0 ? (prot | PROT_CPU_READ) : prot;
}

static bool Bc5JitFits(int prot, int ceiling) {
	return (Bc5JitGrants(prot) & ~Bc5JitGrants(ceiling)) == 0;
}

// The host memory of one area. Its descriptor is closed with the area's last handle; mapped views keep their pages.
struct Bc5JitArea {
	int      host_fd = -1;
	uint64_t bytes   = 0;

	Bc5JitArea(int fd, uint64_t size): host_fd(fd), bytes(size) {}
	~Bc5JitArea() {
#if KYTY_PLATFORM == KYTY_PLATFORM_LINUX
		::close(host_fd);
#endif
	}
	KYTY_CLASS_NO_COPY(Bc5JitArea);
};

struct Bc5JitHandle {
	std::shared_ptr<Bc5JitArea> area;
	int                         ceiling = 0;
};

static std::mutex                  g_bc5_jit_mutex;
static std::map<int, Bc5JitHandle> g_bc5_jit_handles;
static int                         g_bc5_jit_next_handle = BC5_JIT_FIRST_HANDLE;

// A host errno as the guest's answer.
static int Bc5JitHostAnswer(int error) {
	switch (error) {
		case EMFILE: return KERNEL_ERROR_EMFILE;
		case ENFILE: return KERNEL_ERROR_ENFILE;
		default: return KERNEL_ERROR_ENOMEM;
	}
}

static std::shared_ptr<Bc5JitArea> Bc5JitNewArea(uint64_t bytes, int* error) {
#if KYTY_PLATFORM == KYTY_PLATFORM_LINUX
	if (bytes > static_cast<uint64_t>(INT64_MAX)) {
		*error = ENOMEM;
		return nullptr;
	}
	// 0x0001 is MFD_CLOEXEC (Linux include/uapi/linux/memfd.h); this file calls memfd_create through syscall, as here.
	const int fd = static_cast<int>(syscall(SYS_memfd_create, "bc5-jit", 0x0001u));
	if (fd < 0) {
		*error = errno;
		return nullptr;
	}
	if (ftruncate(fd, static_cast<off_t>(bytes)) != 0) {
		*error = errno;
		::close(fd);
		return nullptr;
	}
	return std::make_shared<Bc5JitArea>(fd, bytes);
#else
	(void)bytes;
	*error = ENOMEM;
	return nullptr;
#endif
}

// Puts a shared view of the area over the host pages of the committed guest range at vaddr, area.bytes long.
static bool Bc5JitShowArea(const Bc5JitArea& area, uint64_t vaddr, int prot) {
#if KYTY_PLATFORM == KYTY_PLATFORM_LINUX
	const int host_prot = PROT_READ | PROT_WRITE | ((prot & PROT_CPU_EXEC) != 0 ? PROT_EXEC : 0);
	void*     view =
	    mmap(reinterpret_cast<void*>(vaddr), area.bytes, host_prot, MAP_SHARED | MAP_FIXED, area.host_fd, 0);
	return view != MAP_FAILED && reinterpret_cast<uint64_t>(view) == vaddr;
#else
	(void)area;
	(void)vaddr;
	(void)prot;
	return false;
#endif
}

static int Bc5JitAddHandle(std::shared_ptr<Bc5JitArea> area, int ceiling, int* handle_out) {
	std::lock_guard<std::mutex> lock(g_bc5_jit_mutex);
	if (g_bc5_jit_next_handle == BC5_JIT_LAST_HANDLE) {
		return KERNEL_ERROR_EMFILE;
	}
	const int handle            = g_bc5_jit_next_handle++;
	g_bc5_jit_handles[handle]   = Bc5JitHandle {std::move(area), ceiling};
	*handle_out                 = handle;
	return OK;
}

// The area behind a handle, if the handle is one and `prot` fits under its ceiling; else the answer.
static int Bc5JitLookUp(int handle, int prot, std::shared_ptr<Bc5JitArea>* area) {
	std::lock_guard<std::mutex> lock(g_bc5_jit_mutex);
	const auto                  it = g_bc5_jit_handles.find(handle);
	if (it == g_bc5_jit_handles.end()) {
		return KERNEL_ERROR_EBADF;
	}
	if (!Bc5JitFits(prot, it->second.ceiling)) {
		return KERNEL_ERROR_EACCES;
	}
	*area = it->second.area;
	return OK;
}

int KYTY_SYSV_ABI Bc5JitAreaCreate(const char* label, size_t bytes, int ceiling, int* handle_out) {
	PRINT_NAME();

	(void)label;
	if (handle_out == nullptr || bytes == 0 || (bytes & (BC5_JIT_PAGE - 1u)) != 0 || (ceiling & ~BC5_JIT_CPU_BITS) != 0) {
		return KERNEL_ERROR_EINVAL;
	}
	int  error = 0;
	auto area  = Bc5JitNewArea(bytes, &error);
	if (area == nullptr) {
		LOGF("\t jit area of 0x%016" PRIx64 " bytes: the host refused it (errno %d)\n", static_cast<uint64_t>(bytes), error);
		return Bc5JitHostAnswer(error);
	}
	const int result = Bc5JitAddHandle(std::move(area), ceiling, handle_out);
	LOGF("\t jit area: 0x%016" PRIx64 " bytes, ceiling 0x%x, handle %d\n", static_cast<uint64_t>(bytes), ceiling,
	     result == OK ? *handle_out : -1);
	return result;
}

int KYTY_SYSV_ABI Bc5JitAreaAlias(int handle, int ceiling, int* handle_out) {
	PRINT_NAME();

	if (handle_out == nullptr || (ceiling & ~BC5_JIT_CPU_BITS) != 0) {
		return KERNEL_ERROR_EINVAL;
	}
	std::shared_ptr<Bc5JitArea> area;
	if (const int result = Bc5JitLookUp(handle, ceiling, &area); result != OK) {
		return result;
	}
	const int result = Bc5JitAddHandle(std::move(area), ceiling, handle_out);
	LOGF("\t jit alias of handle %d: ceiling 0x%x, handle %d\n", handle, ceiling, result == OK ? *handle_out : -1);
	return result;
}

int KYTY_SYSV_ABI Bc5JitAreaMap(int handle, int prot, void** where) {
	PRINT_NAME();

	if (where == nullptr || (prot & ~BC5_JIT_CPU_BITS) != 0) {
		return KERNEL_ERROR_EINVAL;
	}
	std::shared_ptr<Bc5JitArea> area;
	if (const int result = Bc5JitLookUp(handle, prot, &area); result != OK) {
		return result;
	}

	bc5::load_stat::CountedLock<std::recursive_mutex> memory_operation_lock(g_memory_operation_mutex, bc5::load_stat::kMemLockWait); // exp 0415 (ls415): a lock_guard with the wait counted

	const auto mode  = static_cast<VirtualMemory::Mode>(prot);
	const auto hint  = reinterpret_cast<uint64_t>(*where) & ~(BC5_JIT_PAGE - 1u);
	uint64_t   vaddr = 0;
	if (hint != 0) {
		vaddr = AllocateGuestRuntimeMemory(hint, area->bytes, mode, BC5_JIT_VIEW_NAME, VirtualRangeType::Runtime, false);
	}
	if (vaddr == 0) {
		vaddr = AllocateGuestRuntimeMemory(0, area->bytes, mode, BC5_JIT_VIEW_NAME, VirtualRangeType::Runtime, false);
	}
	if (vaddr == 0) {
		return KERNEL_ERROR_ENOMEM;
	}
	if (!Bc5JitShowArea(*area, vaddr, prot)) {
		UnmapGpuRange(vaddr, area->bytes);
		EXIT_IF(!FreeGuestMemoryOwner(vaddr, area->bytes));
		return KERNEL_ERROR_ENOMEM;
	}
	*where = reinterpret_cast<void*>(vaddr);
	LOGF("\t jit view of handle %d: 0x%016" PRIx64 "..0x%016" PRIx64 ", prot 0x%x\n", handle, vaddr, vaddr + area->bytes,
	     prot);
	return OK;
}

// Lets a JIT handle go; false when `handle` is not one (the caller then does today's close).
bool Bc5JitHandleClose(int handle) {
	if (handle < BC5_JIT_FIRST_HANDLE) {
		return false;
	}
	std::shared_ptr<Bc5JitArea> last; // destroyed after the lock is released
	std::lock_guard<std::mutex>  lock(g_bc5_jit_mutex);
	const auto                   it = g_bc5_jit_handles.find(handle);
	if (it == g_bc5_jit_handles.end()) {
		return false;
	}
	last = std::move(it->second.area);
	g_bc5_jit_handles.erase(it);
	LOGF("\t jit handle %d closed\n", handle);
	return true;
}
// ---- end of BC5 experiment 0405 series e6, KYTY_BC5_JIT_SHM ----------------------------------------------------------

// Experiment 0405 series e5, BC5_R3_MPROTECT_GAPS (M1): protection over gaps, as a PS5 does. AnyPS5 measured on
// firmware 13.60 that sceKernelMprotect, mprotect and sceKernelMtypeprotect change the mapped parts of a range, skip its
// gaps and return 0, also when the range starts in a gap or is wholly unmapped (AnyPS5 4f41f4c37
// docs/dev/debt/libkernel.md:172, commit 748b35835; DoMprotect in core/libs/prx/libkernel/DirectMemory/
// DirectMemory.cpp:1484-1585, called with requireMappedStart false from Export.cpp:326-330 and 478-481; GPL-2.0-only).
// Its batch-map protect operations keep EINVAL for an unmapped start (Export.cpp:620-624, unmeasured):
// require_mapped_start. shadPS4 60c42b9 src/core/memory.cpp:1052-1178 (GPL-2.0-or-later) also skips gaps, and records
// the protection on a reserved range without applying it (1104-1108) and leaves a pool-reserved one alone (1059-1062);
// so does this. Adapted, no code copied: the pieces come from the range table; each mapped (committed) piece gets
// today's treatment (host view, direct or flexible block, range table); a Reserved piece gets the range table only.
// A host protect failure still EXITs, as today; an overflowing range returns EINVAL instead of EXIT.
static int Bc5MprotectGaps(uint64_t vaddr, size_t len, int prot, bool require_mapped_start) {
	bc5::load_stat::CountedLock<std::recursive_mutex> memory_operation_lock(g_memory_operation_mutex, bc5::load_stat::kMemLockWait); // exp 0415 (ls415): a lock_guard with the wait counted

	constexpr uint64_t PAGE_SIZE    = 0x4000;
	const uint64_t     aligned_addr = vaddr & ~(PAGE_SIZE - 1);
	const uint64_t     page_offset  = vaddr - aligned_addr;
	if (len > UINT64_MAX - page_offset || len + page_offset > UINT64_MAX - (PAGE_SIZE - 1)) {
		return KERNEL_ERROR_EINVAL;
	}
	const uint64_t aligned_len = (len + page_offset + PAGE_SIZE - 1) & ~(PAGE_SIZE - 1);
	if (aligned_len == 0) {
		return OK;
	}
	if (aligned_len > UINT64_MAX - aligned_addr) {
		return KERNEL_ERROR_EINVAL;
	}

	VirtualMemory::Mode mode     = VirtualMemory::Mode::NoAccess;
	GpuAccessMode       gpu_mode = GpuAccessMode::NoAccess;
	if (!DecodeMemoryProtection(prot, &mode, &gpu_mode)) {
		return KERNEL_ERROR_EINVAL;
	}

	// The parts of the range that lie in a range of the table, in address order; what lies between them is a gap.
	const uint64_t                    end     = aligned_addr + aligned_len;
	uint64_t                          current = aligned_addr;
	std::vector<VirtualRanges::Range> pieces;
	while (current < end) {
		VirtualRanges::Range range {};
		if (!g_virtual_ranges->Query(current, 1, &range) || range.start >= end) {
			break;
		}
		const uint64_t range_end = (UINT64_MAX - range.start < range.size ? UINT64_MAX : range.start + range.size);
		VirtualRanges::Range piece = range;
		piece.start                = std::max(current, range.start);
		if (range_end <= piece.start) {
			break;
		}
		piece.size = std::min(end, range_end) - piece.start;
		if (piece.type == VirtualRangeType::Direct) {
			piece.offset += piece.start - range.start;
		}
		pieces.push_back(piece);
		current = piece.start + piece.size;
	}
	if (require_mapped_start && (pieces.empty() || pieces.front().start != aligned_addr)) {
		return KERNEL_ERROR_EINVAL;
	}

	for (const auto& piece: pieces) {
		if (IsCommittedRangeType(piece.type) && !g_guest_address_space->Protect(piece.start, piece.size, mode)) {
			EXIT("host memory-protection update failed: addr=0x%016" PRIx64 " size=0x%016" PRIx64 " prot=0x%08x\n",
			     piece.start, piece.size, prot);
		}
	}
	uint64_t changed = 0;
	for (const auto& piece: pieces) {
		if (piece.type == VirtualRangeType::Direct) {
			g_physical_memory->ProtectMapping(piece.start, piece.size, prot, mode, gpu_mode);
		} else if (piece.type == VirtualRangeType::Flexible) {
			g_flexible_memory->Protect(piece.start, piece.size, prot, mode, gpu_mode);
		}
		if (IsCommittedRangeType(piece.type) || piece.type == VirtualRangeType::Reserved) {
			g_virtual_ranges->Protect(piece.start, piece.size, prot);
		}
		if (IsCommittedRangeType(piece.type)) {
			changed += piece.size;
		}
	}

	LOGF("\t exp 0405 M1: 0x%016" PRIx64 "+0x%016" PRIx64 ": 0x%016" PRIx64 " mapped bytes in %" PRIu64
	     " piece(s) -> %s\n",
	     aligned_addr, aligned_len, changed, static_cast<uint64_t>(pieces.size()), Common::EnumName(mode).c_str());

	return OK;
}

static int Bc5Ff_KernelMprotect(const void* addr, size_t len, int prot); // exp 0412 (tag ff412)
int KYTY_SYSV_ABI KernelMprotect(const void* addr, size_t len, int prot) { // exp 0412 (tag ff412)
	const int bc5_ff_result = Bc5Ff_KernelMprotect(addr, len, prot);
	if (bc5_ff_result != OK) [[unlikely]] ff412_report("KernelMprotect", bc5_ff_result, __builtin_return_address(0), {ff412::u(addr), ff412::u(len), ff412::u(prot)});
	return bc5_ff_result;
}
static int Bc5Ff_KernelMprotect(const void* addr, size_t len, int prot) {
	PRINT_NAME();

	bc5::load_stat::CountedLock<std::recursive_mutex> memory_operation_lock(g_memory_operation_mutex, bc5::load_stat::kMemLockWait); // exp 0415 (ls415): a lock_guard with the wait counted

	auto vaddr = reinterpret_cast<uint64_t>(addr);

	LOGF("\t addr = 0x%016" PRIx64 "\n"
	     "\t len  = 0x%016" PRIx64 "\n",
	     vaddr, static_cast<uint64_t>(len));

	if (Bc5R3On(BC5_R3_ITEM_MPROTECT_GAPS)) { // experiment 0405 series e5 (M1); sceKernelMtypeprotect comes here too
		return Bc5MprotectGaps(vaddr, len, prot, false);
	}

	constexpr uint64_t PAGE_SIZE    = 0x4000;
	auto               aligned_addr = vaddr & ~(PAGE_SIZE - 1);
	const auto         page_offset  = vaddr - aligned_addr;
	if (len > UINT64_MAX - page_offset || len + page_offset > UINT64_MAX - (PAGE_SIZE - 1)) {
		EXIT("memory-protection range overflows: addr=0x%016" PRIx64 " size=0x%016" PRIx64 "\n",
		     vaddr, static_cast<uint64_t>(len));
	}
	auto aligned_len = (len + page_offset + PAGE_SIZE - 1) & ~(PAGE_SIZE - 1);

	if (aligned_len == 0) {
		return OK;
	}

	VirtualMemory::Mode mode     = VirtualMemory::Mode::NoAccess;
	GpuAccessMode       gpu_mode = GpuAccessMode::NoAccess;

	if (!DecodeMemoryProtection(prot, &mode, &gpu_mode)) {
		return KERNEL_ERROR_EINVAL;
	}
	std::vector<VirtualRanges::Range> old_ranges;
	if (!g_virtual_ranges->QuerySpan(aligned_addr, aligned_len, &old_ranges) ||
	    std::any_of(old_ranges.begin(), old_ranges.end(),
	                [](const auto& range) { return !IsCommittedRangeType(range.type); })) {
		EXIT("memory-protection range is not fully mapped: addr=0x%016" PRIx64 " size=0x%016" PRIx64
		     "\n",
		     aligned_addr, aligned_len);
	}
	const auto old_mode = static_cast<VirtualMemory::Mode>(
	    old_ranges.front().protection & (PROT_CPU_READ | PROT_CPU_WRITE | PROT_CPU_EXEC));
	bool ok = g_guest_address_space->Protect(aligned_addr, aligned_len, mode);

	if (!ok) {
		EXIT("host memory-protection update failed: addr=0x%016" PRIx64 " size=0x%016" PRIx64
		     " prot=0x%08x\n",
		     aligned_addr, aligned_len, prot);
	}
	for (const auto& old_range: old_ranges) {
		if (old_range.type == VirtualRangeType::Direct) {
			g_physical_memory->ProtectMapping(old_range.start, old_range.size, prot, mode,
			                                  gpu_mode);
		} else if (old_range.type == VirtualRangeType::Flexible) {
			g_flexible_memory->Protect(old_range.start, old_range.size, prot, mode, gpu_mode);
		}
	}
	g_virtual_ranges->Protect(aligned_addr, aligned_len, prot);

	LOGF("\t prot: %s -> %s\n", Common::EnumName(old_mode).c_str(), Common::EnumName(mode).c_str());

	return OK;
}

static int Bc5Ff_KernelMtypeprotect(const void* addr, size_t len, int type, int prot); // exp 0412 (tag ff412)
int KYTY_SYSV_ABI KernelMtypeprotect(const void* addr, size_t len, int type, int prot) { // exp 0412 (tag ff412)
	const int bc5_ff_result = Bc5Ff_KernelMtypeprotect(addr, len, type, prot);
	if (bc5_ff_result != OK) [[unlikely]] ff412_report("KernelMtypeprotect", bc5_ff_result, __builtin_return_address(0), {ff412::u(addr), ff412::u(len), ff412::u(type), ff412::u(prot)});
	return bc5_ff_result;
}
static int Bc5Ff_KernelMtypeprotect(const void* addr, size_t len, int type, int prot) {
	PRINT_NAME();

	bc5::load_stat::CountedLock<std::recursive_mutex> memory_operation_lock(g_memory_operation_mutex, bc5::load_stat::kMemLockWait); // exp 0415 (ls415): a lock_guard with the wait counted

	LOGF("\t addr = 0x%016" PRIx64 "\n"
	     "\t len  = 0x%016" PRIx64 "\n"
	     "\t type = 0x%08" PRIx32 "\n"
	     "\t prot = 0x%08" PRIx32 "\n",
	     reinterpret_cast<uint64_t>(addr), static_cast<uint64_t>(len), static_cast<uint32_t>(type),
	     static_cast<uint32_t>(prot));

	return KernelMprotect(addr, len, prot);
}

static int Bc5Ff_KernelBatchMap2(KernelBatchMapEntry* entries, int num_entries,
                                  int* num_entries_out, int flags); // exp 0412 (tag ff412)
int KYTY_SYSV_ABI KernelBatchMap2(KernelBatchMapEntry* entries, int num_entries,
                                  int* num_entries_out, int flags) { // exp 0412 (tag ff412)
	const int bc5_ff_result = Bc5Ff_KernelBatchMap2(entries, num_entries, num_entries_out, flags);
	if (bc5_ff_result != OK) [[unlikely]] ff412_report("KernelBatchMap2", bc5_ff_result, __builtin_return_address(0), {ff412::u(entries), ff412::u(num_entries), ff412::u(num_entries_out), ff412::u(flags)});
	return bc5_ff_result;
}
static int Bc5Ff_KernelBatchMap2(KernelBatchMapEntry* entries, int num_entries,
                                  int* num_entries_out, int flags) {
	PRINT_NAME();

	bc5::load_stat::CountedLock<std::recursive_mutex> memory_operation_lock(g_memory_operation_mutex, bc5::load_stat::kMemLockWait); // exp 0415 (ls415): a lock_guard with the wait counted

	LOGF("\t entries         = %p\n"
	     "\t num_entries     = %d\n"
	     "\t num_entries_out = %p\n"
	     "\t flags           = 0x%08" PRIx32 "\n",
	     static_cast<void*>(entries), num_entries, static_cast<void*>(num_entries_out),
	     static_cast<uint32_t>(flags));

	enum MemoryOpTypes {
		MAP_OP_MAP_DIRECT   = 0,
		MAP_OP_UNMAP        = 1,
		MAP_OP_PROTECT      = 2,
		MAP_OP_MAP_FLEXIBLE = 3,
		MAP_OP_TYPE_PROTECT = 4,
	};

	if (entries == nullptr || num_entries < 0) {
		return KERNEL_ERROR_EINVAL;
	}

	int processed = 0;

	for (int i = 0; i < num_entries; i++, processed++) {
		auto* entry = &entries[i];

		LOGF("\t [%d] start = %p, offset = 0x%016" PRIx64 ", length = 0x%016" PRIx64
		     ", prot = 0x%02" PRIx32 ", type = 0x%02" PRIx32 ", op = %d\n",
		     i, entry->start, entry->offset, entry->length,
		     static_cast<uint32_t>(static_cast<unsigned char>(entry->protection)),
		     static_cast<uint32_t>(static_cast<unsigned char>(entry->type)), entry->operation);

		if (entry->length == 0 || entry->operation < MAP_OP_MAP_DIRECT ||
		    entry->operation > MAP_OP_TYPE_PROTECT) {
			break;
		}

		int result = OK;
		switch (entry->operation) {
			case MAP_OP_MAP_DIRECT:
				result = KernelMapNamedDirectMemory(&entry->start, entry->length, entry->protection,
				                                    flags, static_cast<int64_t>(entry->offset), 0,
				                                    "anon");
				break;
			case MAP_OP_UNMAP:
				result = KernelMunmap(reinterpret_cast<uint64_t>(entry->start), entry->length);
				break;
			case MAP_OP_PROTECT:
				// experiment 0405 series e5 (M1): with BC5_R3_MPROTECT_GAPS a batch protect returns EINVAL for an unmapped
				// start and skips later gaps (AnyPS5 4f41f4c37 Export.cpp:620-624, requireMappedStart; GPL-2.0-only)
				result = Bc5R3On(BC5_R3_ITEM_MPROTECT_GAPS)
				             ? Bc5MprotectGaps(reinterpret_cast<uint64_t>(entry->start), entry->length, entry->protection, true)
				             : KernelMprotect(entry->start, entry->length, entry->protection);
				break;
			case MAP_OP_MAP_FLEXIBLE:
				result = KernelMapNamedFlexibleMemory(&entry->start, entry->length,
				                                      entry->protection, flags, "anon");
				break;
			case MAP_OP_TYPE_PROTECT:
				// experiment 0405 series e5 (M1): as MAP_OP_PROTECT; the type is not applied, as today
				result = Bc5R3On(BC5_R3_ITEM_MPROTECT_GAPS)
				             ? Bc5MprotectGaps(reinterpret_cast<uint64_t>(entry->start), entry->length, entry->protection, true)
				             : KernelMtypeprotect(entry->start, entry->length, entry->type, entry->protection);
				break;
			default: result = KERNEL_ERROR_EINVAL; break;
		}

		if (result != OK) {
			if (num_entries_out != nullptr) {
				*num_entries_out = processed;
			}
			return result;
		}
	}

	if (num_entries_out != nullptr) {
		*num_entries_out = processed;
	}

	return (processed == num_entries ? OK : KERNEL_ERROR_EINVAL);
}

int KYTY_SYSV_ABI KernelBatchMap(KernelBatchMapEntry* entries, int num_entries,
                                 int* num_entries_out) {
	constexpr int GUEST_MAP_FIXED = 0x10;
	return KernelBatchMap2(entries, num_entries, num_entries_out, GUEST_MAP_FIXED);
}

static bool IsAligned(uint64_t value, uint64_t alignment) {
	return alignment == 0 || (value & (alignment - 1u)) == 0;
}

static bool IsPowerOfTwo(uint64_t value) {
	return value != 0 && (value & (value - 1u)) == 0;
}

static void MemoryPoolSubtractCommitted(uint64_t len) {
	auto current = g_memory_pool_committed.load(std::memory_order_relaxed);
	while (current != 0) {
		const auto next = (current > len ? current - len : 0);
		if (g_memory_pool_committed.compare_exchange_weak(current, next,
		                                                  std::memory_order_relaxed)) {
			return;
		}
	}
}

static int Bc5Ff_KernelMemoryPoolExpand(int64_t search_start, int64_t search_end, size_t len,
                                         size_t alignment, int64_t* phys_addr_out); // exp 0412 (tag ff412)
int KYTY_SYSV_ABI KernelMemoryPoolExpand(int64_t search_start, int64_t search_end, size_t len,
                                         size_t alignment, int64_t* phys_addr_out) { // exp 0412 (tag ff412)
	const int bc5_ff_result = Bc5Ff_KernelMemoryPoolExpand(search_start, search_end, len, alignment, phys_addr_out);
	if (bc5_ff_result != OK) [[unlikely]] ff412_report("KernelMemoryPoolExpand", bc5_ff_result, __builtin_return_address(0), {ff412::u(search_start), ff412::u(search_end), ff412::u(len), ff412::u(alignment), ff412::u(phys_addr_out)});
	return bc5_ff_result;
}
static int Bc5Ff_KernelMemoryPoolExpand(int64_t search_start, int64_t search_end, size_t len,
                                         size_t alignment, int64_t* phys_addr_out) {
	PRINT_NAME();

	bc5::load_stat::CountedLock<std::recursive_mutex> memory_operation_lock(g_memory_operation_mutex, bc5::load_stat::kMemLockWait); // exp 0415 (ls415): a lock_guard with the wait counted

	constexpr uint64_t POOL_PAGE_SIZE = 0x10000;
	if (search_start < 0 || search_end <= search_start || len == 0 ||
	    (len & (POOL_PAGE_SIZE - 1u)) != 0 || phys_addr_out == nullptr ||
	    (alignment != 0 &&
	     (!IsPowerOfTwo(alignment) || (alignment & (POOL_PAGE_SIZE - 1u)) != 0))) {
		return KERNEL_ERROR_EINVAL;
	}
	if (static_cast<uint64_t>(search_end - search_start) < len) {
		return KERNEL_ERROR_ENOMEM;
	}

	const auto effective_alignment = (alignment != 0 ? alignment : POOL_PAGE_SIZE);
	uint64_t   phys_addr           = 0;
	if (!g_physical_memory->Alloc(static_cast<uint64_t>(search_start),
	                              static_cast<uint64_t>(search_end), len, effective_alignment,
	                              &phys_addr, 0, true)) {
		return KERNEL_ERROR_ENOMEM;
	}

	g_pooled_memory->Expand(phys_addr, len);
	*phys_addr_out = static_cast<int64_t>(phys_addr);

	LOGF("\t search_start = 0x%016" PRIx64 "\n"
	     "\t search_end   = 0x%016" PRIx64 "\n"
	     "\t len          = 0x%016" PRIx64 "\n"
	     "\t alignment    = 0x%016" PRIx64 "\n"
	     "\t phys_addr    = 0x%016" PRIx64 "\n",
	     search_start, search_end, static_cast<uint64_t>(len), static_cast<uint64_t>(alignment),
	     phys_addr);
	return OK;
}

static int Bc5Ff_KernelMemoryPoolReserve(void* addr_in, size_t len, size_t alignment, int flags,
                                          void** addr_out); // exp 0412 (tag ff412)
int KYTY_SYSV_ABI KernelMemoryPoolReserve(void* addr_in, size_t len, size_t alignment, int flags,
                                          void** addr_out) { // exp 0412 (tag ff412)
	const int bc5_ff_result = Bc5Ff_KernelMemoryPoolReserve(addr_in, len, alignment, flags, addr_out);
	if (bc5_ff_result != OK) [[unlikely]] ff412_report("KernelMemoryPoolReserve", bc5_ff_result, __builtin_return_address(0), {ff412::u(addr_in), ff412::u(len), ff412::u(alignment), ff412::u(flags), ff412::u(addr_out)});
	return bc5_ff_result;
}
static int Bc5Ff_KernelMemoryPoolReserve(void* addr_in, size_t len, size_t alignment, int flags,
                                          void** addr_out) {
	PRINT_NAME();

	bc5::load_stat::CountedLock<std::recursive_mutex> memory_operation_lock(g_memory_operation_mutex, bc5::load_stat::kMemLockWait); // exp 0415 (ls415): a lock_guard with the wait counted

	LOGF("\t addr_in   = 0x%016" PRIx64 "\n"
	     "\t len       = 0x%016" PRIx64 "\n"
	     "\t alignment = 0x%016" PRIx64 "\n"
	     "\t flags     = 0x%08" PRIx32 "\n"
	     "\t addr_out  = %p\n",
	     reinterpret_cast<uint64_t>(addr_in), static_cast<uint64_t>(len),
	     static_cast<uint64_t>(alignment), static_cast<uint32_t>(flags),
	     static_cast<void*>(addr_out));

	constexpr uint64_t POOL_RESERVE_ALIGNMENT = 0x200000;

	if (addr_out == nullptr || len == 0 || !IsAligned(len, POOL_RESERVE_ALIGNMENT)) {
		return KERNEL_ERROR_EINVAL;
	}
	if (alignment != 0 &&
	    (!IsPowerOfTwo(alignment) || !IsAligned(alignment, POOL_RESERVE_ALIGNMENT))) {
		return KERNEL_ERROR_EINVAL;
	}

	void*      out_addr          = addr_in;
	const auto reserve_alignment = (alignment != 0 ? alignment : POOL_RESERVE_ALIGNMENT);
	const int  ret = KernelReserveVirtualRange(&out_addr, len, flags, reserve_alignment);
	if (ret == OK) {
		const auto           out_vaddr = reinterpret_cast<uint64_t>(out_addr);
		VirtualRanges::Range reserved_range {};
		if (!g_virtual_ranges->Query(out_vaddr, 0, &reserved_range) ||
		    reserved_range.start != out_vaddr || reserved_range.size != len ||
		    !IsReservedRangeType(reserved_range.type)) {
			return KERNEL_ERROR_EBUSY;
		}
		g_virtual_ranges->Remove(out_vaddr, len);
		if (!g_virtual_ranges->Add(out_vaddr, len, 0, 0, 0, VirtualRangeType::PoolReserved,
		                           reserved_range.name)) {
			g_virtual_ranges->Add(out_vaddr, len, reserved_range.offset, reserved_range.protection,
			                      reserved_range.memory_type, reserved_range.type,
			                      reserved_range.name);
			return KERNEL_ERROR_EBUSY;
		}
		*addr_out = out_addr;
		LOGF("\t out_addr  = 0x%016" PRIx64 "\n", reinterpret_cast<uint64_t>(out_addr));
	}

	return ret;
}

static int Bc5Ff_KernelMemoryPoolCommit(void* addr, size_t len, int type, int prot, int flags); // exp 0412 (tag ff412)
int KYTY_SYSV_ABI KernelMemoryPoolCommit(void* addr, size_t len, int type, int prot, int flags) { // exp 0412 (tag ff412)
	const int bc5_ff_result = Bc5Ff_KernelMemoryPoolCommit(addr, len, type, prot, flags);
	if (bc5_ff_result != OK) [[unlikely]] ff412_report("KernelMemoryPoolCommit", bc5_ff_result, __builtin_return_address(0), {ff412::u(addr), ff412::u(len), ff412::u(type), ff412::u(prot), ff412::u(flags)});
	return bc5_ff_result;
}
static int Bc5Ff_KernelMemoryPoolCommit(void* addr, size_t len, int type, int prot, int flags) {
	PRINT_NAME();

	bc5::load_stat::CountedLock<std::recursive_mutex> memory_operation_lock(g_memory_operation_mutex, bc5::load_stat::kMemLockWait); // exp 0415 (ls415): a lock_guard with the wait counted

	LOGF("\t addr  = 0x%016" PRIx64 "\n"
	     "\t len   = 0x%016" PRIx64 "\n"
	     "\t type  = 0x%08" PRIx32 "\n"
	     "\t prot  = 0x%08" PRIx32 "\n"
	     "\t flags = 0x%08" PRIx32 "\n",
	     reinterpret_cast<uint64_t>(addr), static_cast<uint64_t>(len), static_cast<uint32_t>(type),
	     static_cast<uint32_t>(prot), static_cast<uint32_t>(flags));

	constexpr uint64_t POOL_COMMIT_ALIGNMENT = 0x10000;
	constexpr int      PROT_CPU_EXEC         = 0x04;

	if (addr == nullptr || len == 0 || !IsAligned(len, POOL_COMMIT_ALIGNMENT) ||
	    (prot & PROT_CPU_EXEC) != 0) {
		return KERNEL_ERROR_EINVAL;
	}

	VirtualMemory::Mode mode     = VirtualMemory::Mode::NoAccess;
	GpuAccessMode       gpu_mode = GpuAccessMode::NoAccess;
	if (!DecodeMemoryProtection(prot, &mode, &gpu_mode)) {
		return KERNEL_ERROR_EINVAL;
	}

	const auto vaddr = reinterpret_cast<uint64_t>(addr);

	VirtualRanges::Range old_range {};
	if (!g_virtual_ranges->Query(vaddr, 0, &old_range) ||
	    old_range.type != VirtualRangeType::PoolReserved) {
		return KERNEL_ERROR_EACCES;
	}

	if (!g_virtual_ranges->ConsumeReserved(vaddr, len, VirtualRangeType::PoolReserved)) {
		return KERNEL_ERROR_EACCES;
	}

	std::vector<PooledMemory::Mapping> mappings;
	if (!g_pooled_memory->Allocate(vaddr, len, gpu_mode, &mappings)) {
		g_virtual_ranges->Add(vaddr, len, 0, 0, 0, VirtualRangeType::PoolReserved, old_range.name);
		return KERNEL_ERROR_ENOMEM;
	}

	std::vector<PooledMemory::Mapping> mapped;
	auto                               rollback = [&]() {
		if (!UnmapPooledBackingTransactional(mapped, mode)) {
			EXIT("failed to roll back pooled-memory backing maps\n");
		}
		GpuAccessMode rollback_gpu_mode = GpuAccessMode::NoAccess;
		if (!g_pooled_memory->Release(vaddr, len, &rollback_gpu_mode)) {
			EXIT("failed to release pooled-memory rollback allocation\n");
		}
		g_virtual_ranges->Add(vaddr, len, 0, 0, 0, VirtualRangeType::PoolReserved, old_range.name);
	};

	for (const auto& mapping: mappings) {
		auto       failure_reason = GuestBackingStore::FailureReason::None;
		const bool ok = g_guest_address_space->MapBacking(mapping.vaddr, mapping.size,
		                                                  mapping.phys_addr, mode, &failure_reason);
		if (!ok) {
			LOGF_COLOR(Log::Color::Red, "\t pool backing map failed: %s\n",
			           GuestBackingStore::GetFailureReasonName(failure_reason));
			rollback();
			return KERNEL_ERROR_ENOMEM;
		}
		mapped.push_back(mapping);
	}

	if (!g_virtual_ranges->Add(vaddr, len, 0, prot, type, VirtualRangeType::Pooled,
	                           old_range.name)) {
		rollback();
		return KERNEL_ERROR_EBUSY;
	}

	MapGpuRange(vaddr, len);

	if (g_alloc_callback != nullptr) {
		g_alloc_callback(vaddr, len);
	}

	g_memory_pool_committed.fetch_add(len, std::memory_order_relaxed);

	return OK;
}

static int DecommitMemoryPoolRange(uint64_t vaddr, size_t len) {
	VirtualRanges::Range old_range {};
	if (!g_virtual_ranges->Query(vaddr, 0, &old_range)) {
		return KERNEL_ERROR_EACCES;
	}
	const auto chunk_len = std::min<uint64_t>(len, old_range.size - (vaddr - old_range.start));
	if (old_range.type == VirtualRangeType::PoolReserved) {
		return chunk_len < len ? DecommitMemoryPoolRange(vaddr + chunk_len, len - chunk_len) : OK;
	}
	if (old_range.type != VirtualRangeType::Pooled) {
		return KERNEL_ERROR_EACCES;
	}
	if (chunk_len < len) {
		const int ret = DecommitMemoryPoolRange(vaddr, chunk_len);
		return ret == OK ? DecommitMemoryPoolRange(vaddr + chunk_len, len - chunk_len) : ret;
	}

	std::vector<PooledMemory::Mapping> mappings;
	if (!g_pooled_memory->Query(vaddr, len, &mappings)) {
		return KERNEL_ERROR_EACCES;
	}

	VirtualMemory::Mode mode        = VirtualMemory::Mode::NoAccess;
	GpuAccessMode       decoded_gpu = GpuAccessMode::NoAccess;
	if (!DecodeMemoryProtection(old_range.protection, &mode, &decoded_gpu)) {
		return KERNEL_ERROR_EACCES;
	}
	if (!UnmapPooledBackingTransactional(mappings, mode)) {
		EXIT("pooled-memory backing transaction failed after GPU unmap: addr=0x%016" PRIx64
		     " size=0x%016" PRIx64 "\n",
		     vaddr, len);
	}

	GpuAccessMode gpu_mode = GpuAccessMode::NoAccess;
	if (!g_pooled_memory->Release(vaddr, len, &gpu_mode)) {
		EXIT("failed to release decommitted pooled-memory range\n");
	}

	g_virtual_ranges->Remove(vaddr, len);
	g_virtual_ranges->Add(vaddr, len, 0, 0, 0, VirtualRangeType::PoolReserved, old_range.name);

	if (g_free_callback != nullptr) {
		g_free_callback(vaddr, len);
	}

	MemoryPoolSubtractCommitted(len);
	return OK;
}

static int Bc5Ff_KernelMemoryPoolDecommit(void* addr, size_t len, int flags); // exp 0412 (tag ff412)
int KYTY_SYSV_ABI KernelMemoryPoolDecommit(void* addr, size_t len, int flags) { // exp 0412 (tag ff412)
	const int bc5_ff_result = Bc5Ff_KernelMemoryPoolDecommit(addr, len, flags);
	if (bc5_ff_result != OK) [[unlikely]] ff412_report("KernelMemoryPoolDecommit", bc5_ff_result, __builtin_return_address(0), {ff412::u(addr), ff412::u(len), ff412::u(flags)});
	return bc5_ff_result;
}
static int Bc5Ff_KernelMemoryPoolDecommit(void* addr, size_t len, int flags) {
	PRINT_NAME();

	bc5::load_stat::CountedLock<std::recursive_mutex> memory_operation_lock(g_memory_operation_mutex, bc5::load_stat::kMemLockWait); // exp 0415 (ls415): a lock_guard with the wait counted

	LOGF("\t addr  = 0x%016" PRIx64 "\n"
	     "\t len   = 0x%016" PRIx64 "\n"
	     "\t flags = 0x%08" PRIx32 "\n",
	     reinterpret_cast<uint64_t>(addr), static_cast<uint64_t>(len),
	     static_cast<uint32_t>(flags));

	constexpr uint64_t POOL_COMMIT_ALIGNMENT = 0x10000;

	if (addr == nullptr || len == 0 || !IsAligned(len, POOL_COMMIT_ALIGNMENT)) {
		return KERNEL_ERROR_EINVAL;
	}

	const auto vaddr = reinterpret_cast<uint64_t>(addr);
	if (UINT64_MAX - vaddr < len) {
		return KERNEL_ERROR_EINVAL;
	}
	const auto end  = vaddr + len;
	auto       scan = vaddr;
	while (scan < end) {
		VirtualRanges::Range scan_range {};
		if (!g_virtual_ranges->Query(scan, 0, &scan_range) ||
		    (scan_range.type != VirtualRangeType::Pooled &&
		     scan_range.type != VirtualRangeType::PoolReserved)) {
			return KERNEL_ERROR_EACCES;
		}
		const auto next = std::min(end, scan_range.start + scan_range.size);
		if (next <= scan) {
			return KERNEL_ERROR_EACCES;
		}
		scan = next;
	}

	UnmapGpuRange(vaddr, len);
	return DecommitMemoryPoolRange(vaddr, len);
}

int KYTY_SYSV_ABI KernelMemoryPoolBatch(const KernelMemoryPoolBatchEntry* entries, int num_entries,
                                        int* num_entries_out, int flags) {
	PRINT_NAME();

	bc5::load_stat::CountedLock<std::recursive_mutex> memory_operation_lock(g_memory_operation_mutex, bc5::load_stat::kMemLockWait); // exp 0415 (ls415): a lock_guard with the wait counted

	if (entries == nullptr || num_entries < 0) {
		return KERNEL_ERROR_EINVAL;
	}

	enum MemoryPoolOp {
		POOL_OP_COMMIT       = 1,
		POOL_OP_DECOMMIT     = 2,
		POOL_OP_PROTECT      = 3,
		POOL_OP_TYPE_PROTECT = 4,
		POOL_OP_MOVE         = 5,
	};

	int processed = 0;
	int result    = OK;

	for (int i = 0; i < num_entries; i++, processed++) {
		const auto& entry = entries[i];
		switch (entry.op) {
			case POOL_OP_COMMIT:
				result = KernelMemoryPoolCommit(entry.commit.addr, entry.commit.len,
				                                entry.commit.type, entry.commit.prot, entry.flags);
				break;
			case POOL_OP_DECOMMIT:
				result =
				    KernelMemoryPoolDecommit(entry.decommit.addr, entry.decommit.len, entry.flags);
				break;
			case POOL_OP_PROTECT:
				result = KernelMprotect(entry.protect.addr, entry.protect.len, entry.protect.prot);
				break;
			case POOL_OP_TYPE_PROTECT:
				result = KernelMtypeprotect(entry.type_protect.addr, entry.type_protect.len,
				                            entry.type_protect.type, entry.type_protect.prot);
				break;
			case POOL_OP_MOVE:
			default: result = KERNEL_ERROR_EINVAL; break;
		}

		if (result != OK) {
			break;
		}
	}

	if (num_entries_out != nullptr) {
		*num_entries_out = processed;
	}

	(void)flags;
	return result;
}

int KYTY_SYSV_ABI KernelMemoryPoolGetBlockStats(KernelMemoryPoolBlockStats* output,
                                                size_t                      output_size) {
	PRINT_NAME();

	bc5::load_stat::CountedLock<std::recursive_mutex> memory_operation_lock(g_memory_operation_mutex, bc5::load_stat::kMemLockWait); // exp 0415 (ls415): a lock_guard with the wait counted

	if (output == nullptr && output_size != 0) {
		return KERNEL_ERROR_EFAULT;
	}

	KernelMemoryPoolBlockStats stats {};
	constexpr uint64_t         BLOCK_SIZE = 0x10000;
	const uint64_t             committed  = g_memory_pool_committed.load(std::memory_order_relaxed);
	const uint64_t available = (g_pooled_memory != nullptr ? g_pooled_memory->Available() : 0);

	stats.available_flushed_blocks = static_cast<int32_t>(available / BLOCK_SIZE);
	stats.available_cached_blocks  = 0;
	stats.allocated_flushed_blocks = static_cast<int32_t>(committed / BLOCK_SIZE);
	stats.allocated_cached_blocks  = 0;

	const auto copy_size = std::min(output_size, sizeof(stats));
	if (copy_size != 0) {
		std::memcpy(output, &stats, copy_size);
	}

	return OK;
}

} // namespace Libs::LibKernel::Memory
