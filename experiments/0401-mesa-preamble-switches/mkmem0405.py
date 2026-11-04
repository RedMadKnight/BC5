#!/usr/bin/env python3
"""BC5 experiment 0401 series e5, tag mem: exp 0405's R3 memory ports (raw/r3-gpu-memory.md, ranked table and "e4-now
port specs") in src/kernel/memory.cpp, one switch per item, R3's names:
  BC5_R3_MPROTECT_GAPS (M1)  mprotect/mtypeprotect over gaps change the mapped parts and return 0 (today: EXIT)
  BC5_R3_NULL_ARGS     (M21) QueryMemoryProtection(NULL) -> EACCES, MapNamedFlexibleMemory(NULL) -> EINVAL (today: EXIT)
  BC5_R3_RELEASE_HOLES (M3)  unchecked ReleaseDirectMemory over free gaps releases the allocated runs (today: nothing)
  BC5_R3_MUNMAP_HOLES  (M7)  munmap over holes unmaps the mapped runs, nothing mapped is 0 (today: EACCES)
  BC5_R3_FLEX_HINT     (M6)  a non-fixed flexible hint wholly inside reserved ranges is used (today: placed after)
  BC5_R3_DMQ_END       (M20) DirectMemoryQuery find-next past the last block -> EACCES (today: OK, terminal record)
  BC5_R3_EXEC_EINVAL   (M26) MapDirectMemory with CPU execute -> EINVAL (today: EACCES)
  BC5_R3_QUERY_SIZE    (M30) VirtualQuery/DirectMemoryQuery accept an info size larger than the struct (today: EINVAL)
Each switch is on when set, non-empty and not "0" (F767's reading), read once. Off (unset or "0") is today's code
path; the only addition then is one stderr line at memory init: "[bc5] exp 0405: mem off" (or "... on (items: ...)").
Sources (all GPL-2.0-compatible; behaviour adapted, no code copied) are cited in each inserted block; mem0405-notes.md
has the per-item verdicts. No header is edited.
Input: the e5 input tree's src/kernel/memory.cpp (e4's private unit, mkmem0401.py's output, md5 43713ef6...), LF line
endings. Every anchor must occur exactly once; an input that has the edit already is refused; so is any other md5.
After editing, the script checks that undoing every replacement (new -> old, last first) gives the input back.
Prints "<relpath> <md5>" for the output.
usage: mkmem0405.py <tree root in> <out dir>"""
import hashlib
import os
import sys

REL = "src/kernel/memory.cpp"
IN_MD5 = "43713ef677ec887a8ca273f7ab5cee90"  # e4's private memory.cpp (mkmem0401.py's output)
MARK = b"Bc5R3On"

# ---- the switches, the journal line --------------------------------------------------------------------------------
SWITCH_ANCHOR = b"static Graphics::GpuResourceManager& GetGpuResources() {\n"
SWITCH_BLOCK = b"""// ---- Experiment 0405 series e5 (mkmem0405.py): exp 0405's R3 memory ports ------------------------------------------
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
\tBC5_R3_ITEM_MPROTECT_GAPS,
\tBC5_R3_ITEM_NULL_ARGS,
\tBC5_R3_ITEM_RELEASE_HOLES,
\tBC5_R3_ITEM_MUNMAP_HOLES,
\tBC5_R3_ITEM_FLEX_HINT,
\tBC5_R3_ITEM_DMQ_END,
\tBC5_R3_ITEM_EXEC_EINVAL,
\tBC5_R3_ITEM_QUERY_SIZE,
\tBC5_R3_ITEM_COUNT,
};
static constexpr const char* BC5_R3_SWITCH_NAMES[BC5_R3_ITEM_COUNT] = {
    "BC5_R3_MPROTECT_GAPS", "BC5_R3_NULL_ARGS", "BC5_R3_RELEASE_HOLES", "BC5_R3_MUNMAP_HOLES",
    "BC5_R3_FLEX_HINT",     "BC5_R3_DMQ_END",   "BC5_R3_EXEC_EINVAL",   "BC5_R3_QUERY_SIZE",
};

static bool Bc5R3On(Bc5R3Item item) {
\tstatic const std::array<bool, BC5_R3_ITEM_COUNT> on = [] {
\t\tstd::array<bool, BC5_R3_ITEM_COUNT> v {};
\t\tfor (unsigned i = 0; i < BC5_R3_ITEM_COUNT; i++) {
\t\t\tconst char* e = std::getenv(BC5_R3_SWITCH_NAMES[i]);
\t\t\tv[i]          = e != nullptr && e[0] != 0 && std::strcmp(e, "0") != 0;
\t\t}
\t\treturn v;
\t}();
\treturn on[item];
}

// The one journal line, at memory init: "[bc5] exp 0405: mem off" or "[bc5] exp 0405: mem on (items: A,B)".
static void Bc5R3Journal() {
\tchar   items[512] = {};
\tsize_t used       = 0;
\tfor (unsigned i = 0; i < BC5_R3_ITEM_COUNT; i++) {
\t\tif (Bc5R3On(static_cast<Bc5R3Item>(i)) && used < sizeof(items)) {
\t\t\tconst int n = std::snprintf(items + used, sizeof(items) - used, "%s%s", used == 0 ? "" : ",", BC5_R3_SWITCH_NAMES[i]);
\t\t\tused += (n > 0 ? static_cast<size_t>(n) : 0);
\t\t}
\t}
\tif (used == 0) {
\t\tstd::fprintf(stderr, "[bc5] exp 0405: mem off\\n");
\t} else {
\t\tstd::fprintf(stderr, "[bc5] exp 0405: mem on (items: %s)\\n", items);
\t}
}

"""

JOURNAL_OLD = b"\tVirtualMemory::Init();\n"
JOURNAL_NEW = b"\tBc5R3Journal(); // experiment 0405 series e5: one line, the R3 memory switches\n\tVirtualMemory::Init();\n"

# ---- M21: NULL arguments -------------------------------------------------------------------------------------------
FLEX_NULL_OLD = b"\tEXIT_NOT_IMPLEMENTED(addr_in_out == nullptr);\n"
FLEX_NULL_NEW = b"""\t// Experiment 0405 series e5, BC5_R3_NULL_ARGS (M21): a NULL addr_in_out is the guest's error, not the host's exit.
\t// EINVAL, as sharpemu 514d766 src/SharpEmu.Libs/Kernel/KernelMemoryCompatExports.cs:3352-3360 (MapFlexibleMemoryCore:
\t// a pointer of 0 gives MemoryInvalidArgument; GPL-2.0-or-later) and AnyPS5 4f41f4c37
\t// core/libs/prx/libkernel/DirectMemory/DirectMemory.cpp:1103-1108 (ValidateOutput: its comment names EINVAL, the code
\t// throws; GPL-2.0-only). shadPS4 60c42b9 reads *addr_in_out unchecked.
\tif (addr_in_out == nullptr && Bc5R3On(BC5_R3_ITEM_NULL_ARGS)) {
\t\treturn KERNEL_ERROR_EINVAL;
\t}
\tEXIT_NOT_IMPLEMENTED(addr_in_out == nullptr);
"""

QUERY_NULL_OLD = b"\tEXIT_NOT_IMPLEMENTED(addr == nullptr);\n"
QUERY_NULL_NEW = b"""\t// Experiment 0405 series e5, BC5_R3_NULL_ARGS (M21): NULL is an unmapped address: EACCES, as for any unmapped address
\t// below (shadPS4 60c42b9 src/core/memory.cpp:1024-1030, an address below the mappable base gives EACCES;
\t// GPL-2.0-or-later; AnyPS5 4f41f4c37 core/libs/prx/libkernel/DirectMemory/Export.cpp:484-494 answers through
\t// sceKernelVirtualQuery, GPL-2.0-only).
\tif (addr == nullptr && Bc5R3On(BC5_R3_ITEM_NULL_ARGS)) {
\t\treturn KERNEL_ERROR_EACCES;
\t}
\tEXIT_NOT_IMPLEMENTED(addr == nullptr);
"""

# ---- M6: a flexible hint inside a reservation ----------------------------------------------------------------------
FLEX_HINT_OLD = b"""\t\tconst auto search_addr = (in_addr != 0 ? in_addr : DEFAULT_PS5_BASE);
\t\tout_addr               = FindGuestFreeRange(search_addr, len, map_alignment);
\t\tif (out_addr != 0) {
\t\t\tUnmapGpuRange(out_addr, len);
\t\t}
\t}
"""
FLEX_HINT_NEW = b"""\t\t// Experiment 0405 series e5, BC5_R3_FLEX_HINT (M6): a hint whose whole range lies in reserved ranges is used as the
\t\t// address, as if MAP_FIXED were set (AnyPS5 4f41f4c37 core/libs/prx/libkernel/DirectMemory/DirectMemory.cpp:1157-1160,
\t\t// PlaceHintInReservation, used by MapAnonymous at 1205; title-observed in PPSA01474, docs/dev/debt/libkernel.md:109;
\t\t// GPL-2.0-only; sharpemu 514d766 BackedMappings.cs:339-344, GPL-2.0-or-later). This file's direct maps already do
\t\t// it (KernelMapDirectMemory's non-fixed branch); this is the same code. An unaligned hint stays a hint.
\t\tif (Bc5R3On(BC5_R3_ITEM_FLEX_HINT) && in_addr != 0 && (in_addr & (PAGE_SIZE - 1)) == 0 &&
\t\t    (in_addr & (map_alignment - 1u)) == 0) {
\t\t\tstd::vector<VirtualRanges::Range> reserved_ranges;
\t\t\tif (g_virtual_ranges->QuerySpan(in_addr, len, &reserved_ranges) &&
\t\t\t    std::all_of(reserved_ranges.begin(), reserved_ranges.end(),
\t\t\t                [](const auto& range) { return range.type == VirtualRangeType::Reserved; })) {
\t\t\t\tUnmapGpuRange(in_addr, len);
\t\t\t\tconsumed_range = reserved_ranges.front();
\t\t\t\tif (g_virtual_ranges->ConsumeReservedSpan(in_addr, len)) {
\t\t\t\t\tconsumed_reservation = true;
\t\t\t\t\tout_addr             = in_addr;
\t\t\t\t}
\t\t\t}
\t\t}
\t\tif (!consumed_reservation) {
\t\tconst auto search_addr = (in_addr != 0 ? in_addr : DEFAULT_PS5_BASE);
\t\tout_addr               = FindGuestFreeRange(search_addr, len, map_alignment);
\t\tif (out_addr != 0) {
\t\t\tUnmapGpuRange(out_addr, len);
\t\t}
\t\t} // experiment 0405 series e5 (M6)
\t}
"""

# ---- M7: munmap over holes -----------------------------------------------------------------------------------------
MUNMAP_FN_ANCHOR = b"int KYTY_SYSV_ABI KernelMunmap(uint64_t vaddr, size_t len) {\n"
MUNMAP_FN = b"""// Experiment 0405 series e5, BC5_R3_MUNMAP_HOLES (M7): sceKernelMunmap over holes unmaps what is mapped, skips the
// holes and returns 0; a range with nothing mapped returns 0. AnyPS5 4f41f4c37 core/libs/prx/libkernel/DirectMemory/
// Export.cpp:332-339 and DirectMemory.cpp:1615-1622 (DoMunmap: nothing overlapping gives 0, after prosper's console
// oracle, docs/dev/debt/libkernel.md:313; GPL-2.0-only); shadPS4 60c42b9 src/core/memory.cpp:913-1008 (free areas are
// skipped, 942-944; GPL-2.0-or-later). sharpemu 514d766 returns an error here, as this file does today. Length checks
// are unchanged (AnyPS5 and shadPS4 disagree on a length that is not a page multiple); a NULL address keeps today's
// EACCES (AnyPS5 gives EINVAL there). Adapted, no code copied: each run of ranges without a hole goes through today's
// path (UnmapGpuRange, UnmapMemoryRange); the first error ends the walk and is returned. The caller holds the memory
// operation lock and has checked len != 0 and no overflow.
static int Bc5MunmapHoles(uint64_t vaddr, size_t len) {
\tconst uint64_t                             end     = vaddr + len;
\tuint64_t                                   current = vaddr;
\tstd::vector<std::pair<uint64_t, uint64_t>> runs;
\twhile (current < end) {
\t\tVirtualRanges::Range range {};
\t\tif (!g_virtual_ranges->Query(current, 1, &range) || range.start >= end) {
\t\t\tbreak;
\t\t}
\t\tconst uint64_t range_end = (UINT64_MAX - range.start < range.size ? UINT64_MAX : range.start + range.size);
\t\tconst uint64_t lo        = std::max(current, range.start);
\t\tconst uint64_t hi        = std::min(end, range_end);
\t\tif (hi <= lo) {
\t\t\tbreak;
\t\t}
\t\tif (!runs.empty() && runs.back().first + runs.back().second == lo) {
\t\t\truns.back().second += hi - lo;
\t\t} else {
\t\t\truns.emplace_back(lo, hi - lo);
\t\t}
\t\tcurrent = hi;
\t}
\tLOGF("\\t exp 0405 M7: 0x%016" PRIx64 "+0x%016" PRIx64 " has holes: %" PRIu64 " mapped run(s)\\n", vaddr,
\t     static_cast<uint64_t>(len), static_cast<uint64_t>(runs.size()));
\tfor (const auto& [run_start, run_size]: runs) {
\t\tUnmapGpuRange(run_start, run_size);
\t\tconst int result = UnmapMemoryRange(run_start, run_size);
\t\tif (result != OK) {
\t\t\treturn result;
\t\t}
\t}
\treturn OK;
}

"""
MUNMAP_OLD = b"""\tif (!g_virtual_ranges->QuerySpan(vaddr, len, &ranges)) {
\t\treturn KERNEL_ERROR_EACCES;
\t}
"""
MUNMAP_NEW = b"""\tif (!g_virtual_ranges->QuerySpan(vaddr, len, &ranges)) {
\t\tif (vaddr != 0 && Bc5R3On(BC5_R3_ITEM_MUNMAP_HOLES)) { // experiment 0405 series e5 (M7)
\t\t\treturn Bc5MunmapHoles(vaddr, len);
\t\t}
\t\treturn KERNEL_ERROR_EACCES;
\t}
"""

# ---- M30 and M20: DirectMemoryQuery --------------------------------------------------------------------------------
DMQ_SIZE_OLD = b"""\tif (offset < 0 || (flags != 0 && flags != 1) || info_size != sizeof(QueryInfo) ||
\t    info == nullptr) {
"""
DMQ_SIZE_NEW = b"""\t// Experiment 0405 series e5, BC5_R3_QUERY_SIZE (M30): an info size larger than the struct is accepted and only the
\t// struct is written (AnyPS5 4f41f4c37 core/libs/prx/libkernel/DirectMemory/Export.cpp:253-262, size below the struct
\t// is EINVAL; GPL-2.0-only).
\tif (offset < 0 || (flags != 0 && flags != 1) ||
\t    (Bc5R3On(BC5_R3_ITEM_QUERY_SIZE) ? info_size < sizeof(QueryInfo) : info_size != sizeof(QueryInfo)) ||
\t    info == nullptr) {
"""

DMQ_END_OLD = b"\t\t\tif (flags == 1 && static_cast<uint64_t>(offset) < PhysicalMemory::Size()) {\n"
DMQ_END_NEW = b"""\t\t\t// Experiment 0405 series e5, BC5_R3_DMQ_END (M20): find-next past the last block is EACCES, no terminal record
\t\t\t// (AnyPS5 4f41f4c37 core/libs/prx/libkernel/DirectMemory/Export.cpp:253-262 and MemoryPool.cpp:125-136, GPL-2.0-only;
\t\t\t// shadPS4 60c42b9 src/core/memory.cpp:1242-1245, GPL-2.0-or-later; sharpemu 514d766 KernelMemoryCompatExports.cs:
\t\t\t// 3713-3739). KytyPS5 dfec14a src/kernel/memory.cpp:2164-2170 returns the terminal record, as this file does today.
\t\t\tif (flags == 1 && static_cast<uint64_t>(offset) < PhysicalMemory::Size() && !Bc5R3On(BC5_R3_ITEM_DMQ_END)) {
"""

# ---- M3: unchecked release over holes ------------------------------------------------------------------------------
RELEASE_FN_ANCHOR = b"int KYTY_SYSV_ABI KernelReleaseDirectMemory(int64_t start, size_t len) {\n"
RELEASE_FN = b"""// Experiment 0405 series e5, BC5_R3_RELEASE_HOLES (M3): an unchecked sceKernelReleaseDirectMemory over free gaps
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
\tstd::lock_guard<std::recursive_mutex> memory_operation_lock(g_memory_operation_mutex);

\tconst auto first = static_cast<uint64_t>(start);
\tif (len == 0 || UINT64_MAX - first < len) {
\t\treturn;
\t}
\tconst uint64_t                             end = first + len;
\tstd::vector<std::pair<uint64_t, uint64_t>> runs;
\t{
\t\tCommon::LockGuard lock(g_physical_memory->GetMutex());
\t\tconst auto&       blocks = g_physical_memory->GetPhysicalBlocks();
\t\tauto              it     = blocks.upper_bound(first);
\t\tif (it != blocks.begin()) {
\t\t\tconst auto previous = std::prev(it);
\t\t\tif (previous->second.start_addr + previous->second.size > first) {
\t\t\t\tit = previous;
\t\t\t}
\t\t}
\t\tfor (; it != blocks.end() && it->second.start_addr < end; ++it) {
\t\t\tconst auto& block = it->second;
\t\t\tif (block.pool_expansion) {
\t\t\t\treturn;
\t\t\t}
\t\t\tconst uint64_t lo = std::max(first, block.start_addr);
\t\t\tconst uint64_t hi = std::min(end, block.start_addr + block.size);
\t\t\tif (hi <= lo) {
\t\t\t\tcontinue;
\t\t\t}
\t\t\tif (!runs.empty() && runs.back().first + runs.back().second == lo) {
\t\t\t\truns.back().second += hi - lo;
\t\t\t} else {
\t\t\t\truns.emplace_back(lo, hi - lo);
\t\t\t}
\t\t}
\t}
\tif (runs.empty() || (runs.size() == 1 && runs.front().first == first && runs.front().second == len)) {
\t\treturn;
\t}
\tLOGF("\\t exp 0405 M3: 0x%016" PRIx64 "+0x%016" PRIx64 " has free gaps: releasing %" PRIu64 " allocated run(s)\\n",
\t     first, static_cast<uint64_t>(len), static_cast<uint64_t>(runs.size()));
\tfor (const auto& [run_start, run_size]: runs) {
\t\t(void)ReleaseDirectMemoryInternal(static_cast<int64_t>(run_start), static_cast<size_t>(run_size));
\t}
}

"""
RELEASE_OLD = b"""\tif (len != 0) {
\t\t(void)ReleaseDirectMemoryInternal(start, len);
\t}
\treturn OK;
"""
RELEASE_NEW = b"""\tif (len != 0) {
\t\tconst int released = ReleaseDirectMemoryInternal(start, len); // today's call; its result is still not returned
\t\tif (released != OK && Bc5R3On(BC5_R3_ITEM_RELEASE_HOLES)) {    // experiment 0405 series e5 (M3)
\t\t\tBc5ReleaseDirectMemoryHoles(start, len);
\t\t}
\t}
\treturn OK;
"""

# ---- M26: MapDirectMemory with execute -----------------------------------------------------------------------------
EXEC_OLD = b"""\tif ((prot & PROT_CPU_EXEC) != 0) {
\t\treturn KERNEL_ERROR_EACCES;
\t}
"""
EXEC_NEW = b"""\tif ((prot & PROT_CPU_EXEC) != 0) {
\t\t// Experiment 0405 series e5, BC5_R3_EXEC_EINVAL (M26): EINVAL with nothing mapped, as measured in a title on
\t\t// firmware 12.09 (PS5_PayloadSDK PROBE.md, cited by AnyPS5 4f41f4c37 docs/dev/debt/libkernel.md:190; AnyPS5
\t\t// core/libs/prx/libkernel/DirectMemory/DirectMemory.cpp:1168, GPL-2.0-only). shadPS4 and sharpemu use EACCES, as
\t\t// this file does today.
\t\treturn Bc5R3On(BC5_R3_ITEM_EXEC_EINVAL) ? KERNEL_ERROR_EINVAL : KERNEL_ERROR_EACCES;
\t}
"""

# ---- M30: VirtualQuery ---------------------------------------------------------------------------------------------
VQ_SIZE_OLD = b"\tif (info == nullptr || info_size != sizeof(VirtualQueryInfo) || (flags != 0 && flags != 1)) {\n"
VQ_SIZE_NEW = b"""\t// Experiment 0405 series e5, BC5_R3_QUERY_SIZE (M30): an info size larger than the struct is accepted; only the
\t// struct is written (AnyPS5 4f41f4c37 core/libs/prx/libkernel/DirectMemory/Export.cpp:373, GPL-2.0-only; sharpemu
\t// 514d766 KernelMemoryCompatExports.cs:3579, GPL-2.0-or-later; titles pass other sizes than 0x48, AnyPS5
\t// docs/dev/debt/libkernel.md:361).
\tif (info == nullptr ||
\t    (Bc5R3On(BC5_R3_ITEM_QUERY_SIZE) ? info_size < sizeof(VirtualQueryInfo) : info_size != sizeof(VirtualQueryInfo)) ||
\t    (flags != 0 && flags != 1)) {
"""

# ---- M1: mprotect over gaps ----------------------------------------------------------------------------------------
MPROTECT_FN_ANCHOR = b"int KYTY_SYSV_ABI KernelMprotect(const void* addr, size_t len, int prot) {\n"
MPROTECT_FN = b"""// Experiment 0405 series e5, BC5_R3_MPROTECT_GAPS (M1): protection over gaps, as a PS5 does. AnyPS5 measured on
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
\tstd::lock_guard<std::recursive_mutex> memory_operation_lock(g_memory_operation_mutex);

\tconstexpr uint64_t PAGE_SIZE    = 0x4000;
\tconst uint64_t     aligned_addr = vaddr & ~(PAGE_SIZE - 1);
\tconst uint64_t     page_offset  = vaddr - aligned_addr;
\tif (len > UINT64_MAX - page_offset || len + page_offset > UINT64_MAX - (PAGE_SIZE - 1)) {
\t\treturn KERNEL_ERROR_EINVAL;
\t}
\tconst uint64_t aligned_len = (len + page_offset + PAGE_SIZE - 1) & ~(PAGE_SIZE - 1);
\tif (aligned_len == 0) {
\t\treturn OK;
\t}
\tif (aligned_len > UINT64_MAX - aligned_addr) {
\t\treturn KERNEL_ERROR_EINVAL;
\t}

\tVirtualMemory::Mode mode     = VirtualMemory::Mode::NoAccess;
\tGpuAccessMode       gpu_mode = GpuAccessMode::NoAccess;
\tif (!DecodeMemoryProtection(prot, &mode, &gpu_mode)) {
\t\treturn KERNEL_ERROR_EINVAL;
\t}

\t// The parts of the range that lie in a range of the table, in address order; what lies between them is a gap.
\tconst uint64_t                    end     = aligned_addr + aligned_len;
\tuint64_t                          current = aligned_addr;
\tstd::vector<VirtualRanges::Range> pieces;
\twhile (current < end) {
\t\tVirtualRanges::Range range {};
\t\tif (!g_virtual_ranges->Query(current, 1, &range) || range.start >= end) {
\t\t\tbreak;
\t\t}
\t\tconst uint64_t range_end = (UINT64_MAX - range.start < range.size ? UINT64_MAX : range.start + range.size);
\t\tVirtualRanges::Range piece = range;
\t\tpiece.start                = std::max(current, range.start);
\t\tif (range_end <= piece.start) {
\t\t\tbreak;
\t\t}
\t\tpiece.size = std::min(end, range_end) - piece.start;
\t\tif (piece.type == VirtualRangeType::Direct) {
\t\t\tpiece.offset += piece.start - range.start;
\t\t}
\t\tpieces.push_back(piece);
\t\tcurrent = piece.start + piece.size;
\t}
\tif (require_mapped_start && (pieces.empty() || pieces.front().start != aligned_addr)) {
\t\treturn KERNEL_ERROR_EINVAL;
\t}

\tfor (const auto& piece: pieces) {
\t\tif (IsCommittedRangeType(piece.type) && !g_guest_address_space->Protect(piece.start, piece.size, mode)) {
\t\t\tEXIT("host memory-protection update failed: addr=0x%016" PRIx64 " size=0x%016" PRIx64 " prot=0x%08x\\n",
\t\t\t     piece.start, piece.size, prot);
\t\t}
\t}
\tuint64_t changed = 0;
\tfor (const auto& piece: pieces) {
\t\tif (piece.type == VirtualRangeType::Direct) {
\t\t\tg_physical_memory->ProtectMapping(piece.start, piece.size, prot, mode, gpu_mode);
\t\t} else if (piece.type == VirtualRangeType::Flexible) {
\t\t\tg_flexible_memory->Protect(piece.start, piece.size, prot, mode, gpu_mode);
\t\t}
\t\tif (IsCommittedRangeType(piece.type) || piece.type == VirtualRangeType::Reserved) {
\t\t\tg_virtual_ranges->Protect(piece.start, piece.size, prot);
\t\t}
\t\tif (IsCommittedRangeType(piece.type)) {
\t\t\tchanged += piece.size;
\t\t}
\t}

\tLOGF("\\t exp 0405 M1: 0x%016" PRIx64 "+0x%016" PRIx64 ": 0x%016" PRIx64 " mapped bytes in %" PRIu64
\t     " piece(s) -> %s\\n",
\t     aligned_addr, aligned_len, changed, static_cast<uint64_t>(pieces.size()), Common::EnumName(mode).c_str());

\treturn OK;
}

"""
MPROTECT_OLD = b"""\t     vaddr, static_cast<uint64_t>(len));

\tconstexpr uint64_t PAGE_SIZE    = 0x4000;
\tauto               aligned_addr = vaddr & ~(PAGE_SIZE - 1);
"""
MPROTECT_NEW = b"""\t     vaddr, static_cast<uint64_t>(len));

\tif (Bc5R3On(BC5_R3_ITEM_MPROTECT_GAPS)) { // experiment 0405 series e5 (M1); sceKernelMtypeprotect comes here too
\t\treturn Bc5MprotectGaps(vaddr, len, prot, false);
\t}

\tconstexpr uint64_t PAGE_SIZE    = 0x4000;
\tauto               aligned_addr = vaddr & ~(PAGE_SIZE - 1);
"""

BATCH_PROTECT_OLD = b"\t\t\t\tresult = KernelMprotect(entry->start, entry->length, entry->protection);\n"
BATCH_PROTECT_NEW = b"""\t\t\t\t// experiment 0405 series e5 (M1): with BC5_R3_MPROTECT_GAPS a batch protect returns EINVAL for an unmapped
\t\t\t\t// start and skips later gaps (AnyPS5 4f41f4c37 Export.cpp:620-624, requireMappedStart; GPL-2.0-only)
\t\t\t\tresult = Bc5R3On(BC5_R3_ITEM_MPROTECT_GAPS)
\t\t\t\t             ? Bc5MprotectGaps(reinterpret_cast<uint64_t>(entry->start), entry->length, entry->protection, true)
\t\t\t\t             : KernelMprotect(entry->start, entry->length, entry->protection);
"""
BATCH_TYPE_OLD = b"""\t\t\t\tresult =
\t\t\t\t    KernelMtypeprotect(entry->start, entry->length, entry->type, entry->protection);
"""
BATCH_TYPE_NEW = b"""\t\t\t\t// experiment 0405 series e5 (M1): as MAP_OP_PROTECT; the type is not applied, as today
\t\t\t\tresult = Bc5R3On(BC5_R3_ITEM_MPROTECT_GAPS)
\t\t\t\t             ? Bc5MprotectGaps(reinterpret_cast<uint64_t>(entry->start), entry->length, entry->protection, true)
\t\t\t\t             : KernelMtypeprotect(entry->start, entry->length, entry->type, entry->protection);
"""

# (old, new) in file order; an insertion is old -> new + old (or old + new).
EDITS = (
    ("switches", SWITCH_ANCHOR, SWITCH_BLOCK + SWITCH_ANCHOR),
    ("journal", JOURNAL_OLD, JOURNAL_NEW),
    ("M21 flexible NULL", FLEX_NULL_OLD, FLEX_NULL_NEW),
    ("M6 flexible hint", FLEX_HINT_OLD, FLEX_HINT_NEW),
    ("M7 function", MUNMAP_FN_ANCHOR, MUNMAP_FN + MUNMAP_FN_ANCHOR),
    ("M7 munmap", MUNMAP_OLD, MUNMAP_NEW),
    ("M30 DirectMemoryQuery size", DMQ_SIZE_OLD, DMQ_SIZE_NEW),
    ("M20 DirectMemoryQuery end", DMQ_END_OLD, DMQ_END_NEW),
    ("M3 function", RELEASE_FN_ANCHOR, RELEASE_FN + RELEASE_FN_ANCHOR),
    ("M3 release", RELEASE_OLD, RELEASE_NEW),
    ("M26 execute", EXEC_OLD, EXEC_NEW),
    ("M21 query NULL", QUERY_NULL_OLD, QUERY_NULL_NEW),
    ("M30 VirtualQuery size", VQ_SIZE_OLD, VQ_SIZE_NEW),
    ("M1 function", MPROTECT_FN_ANCHOR, MPROTECT_FN + MPROTECT_FN_ANCHOR),
    ("M1 mprotect", MPROTECT_OLD, MPROTECT_NEW),
    ("M1 batch protect", BATCH_PROTECT_OLD, BATCH_PROTECT_NEW),
    ("M1 batch type protect", BATCH_TYPE_OLD, BATCH_TYPE_NEW),
)


def edit(s):
    if MARK in s or b"exp 0405" in s or b"experiment 0405" in s:
        sys.exit(f"mkmem0405: {REL} has the edit already")
    got = hashlib.md5(s).hexdigest()
    if got != IN_MD5:
        sys.exit(f"mkmem0405: {REL} md5 {got} is not the e5 input's {IN_MD5}")
    if b"\r\n" in s:
        sys.exit(f"mkmem0405: {REL} has CRLF line endings; this script expects LF")
    o = s
    for what, old, new in EDITS:
        n = o.count(old)
        if n != 1:
            sys.exit(f"mkmem0405: anchor '{what}' occurs {n} times, not once")
        o = o.replace(old, new)
    # Undo every replacement, last first: the input must come back.
    back = o
    for what, old, new in reversed(EDITS):
        if back.count(new) != 1:
            sys.exit(f"mkmem0405: self-check: the new text of '{what}' occurs {back.count(new)} times")
        back = back.replace(new, old)
    if back != s:
        sys.exit("mkmem0405: self-check: undoing the edits does not give the input back")
    return o


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    root, out = sys.argv[1], sys.argv[2]
    with open(os.path.join(root, REL), "rb") as f:
        s = f.read()
    o = edit(s)
    p = os.path.join(out, REL)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as f:
        f.write(o)
    print(f"{REL} {hashlib.md5(o).hexdigest()}")


if __name__ == "__main__":
    main()
