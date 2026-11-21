# SPDX-License-Identifier: GPL-2.0-only
# BC5 exp 0438 A1P (tag a1p438): PhysicalMemory's mapping table, FlexibleMemory's block table and PooledMemory's mapping
# and free tables in ordered maps keyed by guest (or physical) address, edited in place in the affected window, behind
# KYTY_BC5_0438_A1P ("1" = maps; anything else or unset = today's vector code, unchanged).
#   python -I mka1p.py IN_memory.cpp OUT_memory.cpp
#       applies the change by exact replacements. No input md5 is pinned (IN may be the tree's memory.cpp, A1's output,
#       or a later stacked output); every anchor must match exactly once, and the input/output md5s are printed.
#       VirtualRanges, VirtualRangesVec, VirtualRangesMap and the Bc5* readers are not touched.
#   python -I mka1p.py --extract OUT_memory.cpp HEADER.h [MUTANT]
#       pulls the real code (name/overlap helpers, pm412, the three classes, GetAlignedPos, every method of the three
#       classes and the A1P bodies) out of a generated memory.cpp into a header for test_a1p438.cpp; MUTANT (m1..m6)
#       plants one bug in the A1P bodies only, so the test can show that it catches it.
import hashlib
import re
import sys

TAG = b"// BC5 exp 0438 A1P (tag a1p438)"

# ---- the switch, before class PhysicalMemory -------------------------------------------------------------------------
SWITCH_OLD = b"static bool     g_pm412_ok       = true;\nstatic uint64_t g_pm412_mismatch = 0;\n\nclass PhysicalMemory {\n"
SWITCH_NEW = (b"static bool     g_pm412_ok       = true;\nstatic uint64_t g_pm412_mismatch = 0;\n\n"
              b"// BC5 exp 0438 A1P (tag a1p438, mka1p.py): KYTY_BC5_0438_A1P=\"1\" keeps PhysicalMemory's, FlexibleMemory's and\n"
              b"// PooledMemory's tables in ordered maps (the A1P bodies after PooledMemory::GetMappings); anything else keeps the\n"
              b"// vector code. Read once; one stderr line.\n"
              b"static bool Bc5A1pOn() {\n"
              b"\tstatic const bool on = [] {\n"
              b"\t\tconst char* e = std::getenv(\"KYTY_BC5_0438_A1P\");\n"
              b"\t\tconst bool  v = e != nullptr && std::strcmp(e, \"1\") == 0;\n"
              b"\t\tstd::fprintf(stderr, \"[bc5] exp 0438 A1P memory tables in maps: %s (tag a1p438)\\n\", v ? \"on\" : \"off\");\n"
              b"\t\treturn v;\n"
              b"\t}();\n"
              b"\treturn on;\n"
              b"}\n\n"
              b"class PhysicalMemory {\n")

# ---- PhysicalMemory: constructor, GetMappings, members -----------------------------------------------------------------
PCTOR_OLD = (b"\tPhysicalMemory() {\n\t\tEXIT_NOT_IMPLEMENTED(!Common::Thread::IsMainThread());\n\t\tm_free.emplace(0, Size());\n\t}\n")
PCTOR_NEW = (b"\tPhysicalMemory(): PhysicalMemory(Bc5A1pOn()) {}\n"
             b"\t// BC5 exp 0438 A1P (tag a1p438): the map only on top of exp 0412's sorted table (mode 1, no overlap seen yet),\n"
             b"\t// where the vector's order is the guest address order; otherwise the vector code.\n"
             b"\texplicit PhysicalMemory(bool bc5_a1p): m_a1p(bc5_a1p && Pm412Mode() == 1 && g_pm412_ok) {\n"
             b"\t\tEXIT_NOT_IMPLEMENTED(!Common::Thread::IsMainThread());\n\t\tm_free.emplace(0, Size());\n"
             b"\t\tif (bc5_a1p && !m_a1p) {\n"
             b"\t\t\tstd::fprintf(stderr, \"[bc5] exp 0438 A1P physmap: KYTY_BC5_PHYSMAP_SORTED is not 1, the vector code (tag a1p438)\\n\");\n"
             b"\t\t}\n"
             b"\t}\n")
PGET_OLD = b"\t[[nodiscard]] const std::vector<AllocatedBlock>& GetMappings() const { return m_mappings; }\n"
PGET_NEW = (b"\t// BC5 exp 0438 A1P (tag a1p438): under A1P a copy of the map, valid while the caller holds GetMutex()\n"
            b"\t[[nodiscard]] const std::vector<AllocatedBlock>& GetMappings() const { return m_a1p ? Bc5A1pList() : m_mappings; }\n")
PMEM_OLD = (b"\tstd::map<uint64_t, AllocatedBlock> m_physical;\n\tstd::map<uint64_t, uint64_t>       m_free;\n"
            b"\tstd::vector<AllocatedBlock>        m_mappings;\n\tCommon::Mutex                      m_mutex;\n};\n")
PMEM_NEW = (b"\tstd::map<uint64_t, AllocatedBlock> m_physical;\n\tstd::map<uint64_t, uint64_t>       m_free;\n"
            b"\tstd::vector<AllocatedBlock>        m_mappings;\n\tCommon::Mutex                      m_mutex;\n\n"
            b"\t// BC5 exp 0438 A1P (tag a1p438): m_mappings as a map keyed by map_vaddr, no two blocks overlapping\n"
            b"\tusing Bc5A1pTable = std::map<uint64_t, AllocatedBlock>;\n"
            b"\tbool                                     m_a1p = false;\n"
            b"\tBc5A1pTable                              m_a1p_mappings;\n"
            b"\tstd::set<std::pair<uint64_t, uint64_t>>  m_a1p_by_phys; // (start_addr, map_vaddr), for FindMappings\n"
            b"\tstd::map<uint64_t, uint64_t>             m_a1p_sizes;   // block size -> count, for the largest\n"
            b"\tmutable std::vector<AllocatedBlock>      m_a1p_list;    // GetMappings' copy\n"
            b"\tvoid                  Bc5A1pIndex(const AllocatedBlock& b, bool add);\n"
            b"\tBc5A1pTable::iterator Bc5A1pAdd(Bc5A1pTable::iterator hint, const AllocatedBlock& b);\n"
            b"\tBc5A1pTable::iterator Bc5A1pDrop(Bc5A1pTable::iterator it);\n"
            b"\tvoid                  Bc5A1pSet(Bc5A1pTable::iterator it, const AllocatedBlock& b);\n"
            b"\tconst std::vector<AllocatedBlock>&  Bc5A1pList() const;\n"
            b"\tvoid                                Bc5A1pBackToOld();\n"
            b"\tvoid                                Bc5A1pInsert(const AllocatedBlock& mapping);\n"
            b"\tbool Bc5A1pUnmap(uint64_t vaddr, uint64_t size, GpuAccessMode* gpu_mode, uint64_t* host_vaddr_to_release);\n"
            b"\tbool Bc5A1pHostStillMapped(uint64_t host_vaddr, uint64_t host_size) const;\n"
            b"\tvoid Bc5A1pProtect(uint64_t vaddr, uint64_t size, int prot, VirtualMemory::Mode mode, GpuAccessMode gpu_mode);\n"
            b"\tbool Bc5A1pFind(uint64_t vaddr, uint64_t* base_addr, size_t* len, int* prot, VirtualMemory::Mode* mode,\n"
            b"\t                GpuAccessMode* gpu_mode);\n"
            b"\tstd::vector<AllocatedBlock> Bc5A1pFindMappings(uint64_t phys_addr, size_t len);\n"
            b"\tvoid Bc5A1pSetName(uint64_t vaddr, uint64_t len, const char* name);\n"
            b"\tvoid Bc5A1pSetMemoryType(uint64_t vaddr, uint64_t len, int memory_type);\n"
            b"};\n")

# ---- FlexibleMemory ----------------------------------------------------------------------------------------------------
FCTOR_OLD = (b"\tFlexibleMemory() {\n\t\tEXIT_NOT_IMPLEMENTED(!Common::Thread::IsMainThread());\n"
             b"\t\tm_free.emplace(PhysicalMemory::Size(), Size());\n\t}\n")
FCTOR_NEW = (b"\tFlexibleMemory(): FlexibleMemory(Bc5A1pOn()) {}\n"
             b"\texplicit FlexibleMemory(bool bc5_a1p): m_a1p(bc5_a1p) { // BC5 exp 0438 A1P (tag a1p438)\n"
             b"\t\tEXIT_NOT_IMPLEMENTED(!Common::Thread::IsMainThread());\n"
             b"\t\tm_free.emplace(PhysicalMemory::Size(), Size());\n\t}\n")
FGET_OLD = b"\t[[nodiscard]] const std::vector<AllocatedBlock>& GetBlocks() const { return m_allocated; }\n"
FGET_NEW = (b"\t// BC5 exp 0438 A1P (tag a1p438): under A1P a copy of the map, valid while the caller holds GetMutex()\n"
            b"\t[[nodiscard]] const std::vector<AllocatedBlock>& GetBlocks() const { return m_a1p ? Bc5A1pList() : m_allocated; }\n")
FMEM_OLD = (b"\tstd::vector<AllocatedBlock>  m_allocated;\n\tstd::map<uint64_t, uint64_t> m_free;\n"
            b"\tuint64_t                     m_allocated_total = 0;\n\tCommon::Mutex                m_mutex;\n};\n")
FMEM_NEW = (b"\tstd::vector<AllocatedBlock>  m_allocated;\n\tstd::map<uint64_t, uint64_t> m_free;\n"
            b"\tuint64_t                     m_allocated_total = 0;\n\tCommon::Mutex                m_mutex;\n\n"
            b"\t// BC5 exp 0438 A1P (tag a1p438): m_allocated as a map keyed by map_vaddr, no two blocks overlapping\n"
            b"\tusing Bc5A1pTable = std::map<uint64_t, AllocatedBlock>;\n"
            b"\tbool                                m_a1p = false;\n"
            b"\tBc5A1pTable                         m_a1p_allocated;\n"
            b"\tmutable std::vector<AllocatedBlock> m_a1p_list; // GetBlocks' copy\n"
            b"\tconst std::vector<AllocatedBlock>&  Bc5A1pList() const;\n"
            b"\tvoid                                Bc5A1pBackToOld();\n"
            b"\tbool                                Bc5A1pFits(uint64_t start, uint64_t size) const;\n"
            b"\tBc5A1pTable::iterator               Bc5A1pFirstEndingAfter(uint64_t vaddr);\n"
            b"\tint  Bc5A1pMap(uint64_t vaddr, size_t len, int prot, VirtualMemory::Mode mode, GpuAccessMode gpu_mode, const char* name);\n"
            b"\tbool Bc5A1pUnmap(uint64_t vaddr, uint64_t size, GpuAccessMode* gpu_mode, uint64_t* host_vaddr_to_release);\n"
            b"\tbool Bc5A1pSnapshot(uint64_t vaddr, uint64_t size, std::vector<AllocatedBlock>* blocks);\n"
            b"\tint  Bc5A1pRestore(const std::vector<AllocatedBlock>& blocks);\n"
            b"\tvoid Bc5A1pProtect(uint64_t vaddr, uint64_t size, int prot, VirtualMemory::Mode mode, GpuAccessMode gpu_mode);\n"
            b"\tbool Bc5A1pFind(uint64_t vaddr, uint64_t* base_addr, size_t* len, int* prot, VirtualMemory::Mode* mode,\n"
            b"\t                GpuAccessMode* gpu_mode);\n"
            b"\tvoid Bc5A1pSetName(uint64_t vaddr, uint64_t len, const char* name);\n"
            b"};\n")

# ---- PooledMemory ------------------------------------------------------------------------------------------------------
QCTOR_OLD = b"\t\tGpuAccessMode gpu_mode;\n\t};\n\n\tvoid                   Expand("
QCTOR_NEW = (b"\t\tGpuAccessMode gpu_mode;\n\t};\n\n"
             b"\tPooledMemory(): PooledMemory(Bc5A1pOn()) {}\n"
             b"\texplicit PooledMemory(bool bc5_a1p): m_a1p(bc5_a1p) {} // BC5 exp 0438 A1P (tag a1p438)\n\n"
             b"\tvoid                   Expand(")
QMEM_OLD = (b"\tstd::vector<PhysicalRange> m_free;\n\tstd::vector<PhysicalRange> m_expansions;\n"
            b"\tstd::vector<Mapping>       m_mappings;\n\tCommon::Mutex              m_mutex;\n};\n")
QMEM_NEW = (b"\tstd::vector<PhysicalRange> m_free;\n\tstd::vector<PhysicalRange> m_expansions;\n"
            b"\tstd::vector<Mapping>       m_mappings;\n\tCommon::Mutex              m_mutex;\n\n"
            b"\t// BC5 exp 0438 A1P (tag a1p438): m_mappings as a map keyed by vaddr (no two overlapping; seq is the vector's\n"
            b"\t// order: the Allocate piece a mapping comes from, its split pieces stay together in vaddr order), m_free as a\n"
            b"\t// map start -> size (sorted, merged, as the vector code keeps it)\n"
            b"\tstruct Bc5A1pMapping {\n\t\tMapping  m;\n\t\tuint64_t seq;\n\t};\n"
            b"\tbool                              m_a1p = false;\n"
            b"\tstd::map<uint64_t, Bc5A1pMapping> m_a1p_mappings;\n"
            b"\tstd::map<uint64_t, uint64_t>      m_a1p_free;\n"
            b"\tuint64_t                          m_a1p_seq = 0;\n"
            b"\tbool                              m_a1p_free_touching = false; // see Bc5A1pReleaseExpansion\n"
            b"\tstd::vector<Mapping>              Bc5A1pOrdered() const;\n"
            b"\tvoid                              Bc5A1pBackToOld();\n"
            b"\tvoid                              Bc5A1pAddFree(uint64_t start, uint64_t size);\n"
            b"\tbool                              Bc5A1pReleaseExpansion(uint64_t phys_addr, uint64_t size);\n"
            b"\tint  Bc5A1pAllocate(uint64_t vaddr, uint64_t size, GpuAccessMode gpu_mode, std::vector<Mapping>* mappings);\n"
            b"\tbool Bc5A1pQueryUnlocked(uint64_t vaddr, uint64_t size, std::vector<Mapping>* mappings) const;\n"
            b"\tbool Bc5A1pRelease(uint64_t vaddr, uint64_t size, GpuAccessMode* gpu_mode);\n"
            b"};\n")

# ---- PhysicalMemory::Map: the insert and the 0412 check's walk ---------------------------------------------------------
MAPCHK_OLD = b"\t\t\tfor (const auto& b412: m_mappings) {\n"
MAPCHK_NEW = b"\t\t\tfor (const auto& b412: (m_a1p ? Bc5A1pList() : m_mappings)) { // exp 0438 A1P (tag a1p438)\n"
MAPCNT_OLD = b"\t\t\t\t             inserts412, overlaps412, m_mappings.size());\n"
MAPCNT_NEW = b"\t\t\t\t             inserts412, overlaps412, m_a1p ? m_a1p_mappings.size() : m_mappings.size());\n"
MAPINS_OLD = b"\tif (Pm412Mode() != 0 && g_pm412_ok) { // exp 0412 (tag ps412): the table stays sorted by guest address\n"
MAPINS_NEW = (b"\tif (m_a1p) { // BC5 exp 0438 A1P (tag a1p438): into the map; an overlap sends the table back to the vector code\n"
              b"\t\tBc5A1pInsert(mapping);\n"
              b"\t} else if (Pm412Mode() != 0 && g_pm412_ok) { // exp 0412 (tag ps412): the table stays sorted by guest address\n")

# PhysicalMemory::Unmap: after the KYTY_VIRTUAL_MEMORY_ALLOCATION_TESTS hook, the lock and the host reset
PUNMAP_OLD = (b"\tCommon::LockGuard lock(m_mutex);\n\n\tif (host_vaddr_to_release != nullptr) {\n\t\t*host_vaddr_to_release = 0;\n\t}\n\n"
              b"\tauto set_host_release_if_last")
PUNMAP_NEW = (b"\tCommon::LockGuard lock(m_mutex);\n\n\tif (host_vaddr_to_release != nullptr) {\n\t\t*host_vaddr_to_release = 0;\n\t}\n\n"
              b"\tif (m_a1p) { " + TAG + b"\n"
              b"\t\tif (UINT64_MAX - vaddr >= size) {\n"
              b"\t\t\treturn Bc5A1pUnmap(vaddr, size, gpu_mode, host_vaddr_to_release);\n\t\t}\n"
              b"\t\t// vaddr + size wraps: pm412::unmap can then leave overlapping blocks, which the map cannot hold\n"
              b"\t\tBc5A1pBackToOld();\n\t}\n\n"
              b"\tauto set_host_release_if_last")

# (signature, dispatch statement): the statement goes right after the method's first "Common::LockGuard lock(m_mutex);"
# line, or right after the signature when lock is False (the two private *Unlocked methods).
DISPATCH = [
    (b"void PhysicalMemory::ProtectMapping(uint64_t vaddr, uint64_t size, int prot,\n"
     b"                                    VirtualMemory::Mode mode, GpuAccessMode gpu_mode) {\n",
     b"if (m_a1p) {\n\t\tBc5A1pProtect(vaddr, size, prot, mode, gpu_mode);\n\t\treturn;\n\t}", True),
    (b"std::vector<PhysicalMemory::AllocatedBlock> PhysicalMemory::FindMappings(uint64_t phys_addr,\n"
     b"                                                                         size_t   len) {\n",
     b"if (m_a1p) {\n\t\treturn Bc5A1pFindMappings(phys_addr, len);\n\t}", True),
    (b"bool PhysicalMemory::Find(uint64_t vaddr, uint64_t* base_addr, size_t* len, int* prot,\n"
     b"                          VirtualMemory::Mode* mode, GpuAccessMode* gpu_mode) {\n",
     b"if (m_a1p) {\n\t\treturn Bc5A1pFind(vaddr, base_addr, len, prot, mode, gpu_mode);\n\t}", True),
    (b"void PhysicalMemory::SetVirtualRangeName(uint64_t vaddr, uint64_t len, const char* name) {\n",
     b"if (m_a1p) {\n\t\tBc5A1pSetName(vaddr, len, name);\n\t\treturn;\n\t}", True),
    (b"void PhysicalMemory::SetVirtualRangeMemoryType(uint64_t vaddr, uint64_t len, int memory_type) {\n",
     b"if (m_a1p) {\n\t\tBc5A1pSetMemoryType(vaddr, len, memory_type);\n\t\treturn;\n\t}", True),
    (b"bool FlexibleMemory::Map(uint64_t vaddr, size_t len, int prot, VirtualMemory::Mode mode,\n"
     b"                         GpuAccessMode gpu_mode, const char* name) {\n",
     b"if (m_a1p) { // -1: the block would overlap one; the table is back in the vector and the vector code runs\n"
     b"\t\tconst int r = Bc5A1pMap(vaddr, len, prot, mode, gpu_mode, name);\n\t\tif (r >= 0) {\n\t\t\treturn r != 0;\n\t\t}\n\t}", True),
    (b"bool FlexibleMemory::Unmap(uint64_t vaddr, uint64_t size, GpuAccessMode* gpu_mode,\n"
     b"                           uint64_t* host_vaddr_to_release) {\n",
     b"if (m_a1p) {\n\t\treturn Bc5A1pUnmap(vaddr, size, gpu_mode, host_vaddr_to_release);\n\t}", True),
    (b"bool FlexibleMemory::Snapshot(uint64_t vaddr, uint64_t size, std::vector<AllocatedBlock>* blocks) {\n",
     b"if (m_a1p) {\n\t\treturn Bc5A1pSnapshot(vaddr, size, blocks);\n\t}", True),
    (b"bool FlexibleMemory::Restore(const std::vector<AllocatedBlock>& blocks) {\n",
     b"if (m_a1p) { // -1 as in Map\n\t\tconst int r = Bc5A1pRestore(blocks);\n\t\tif (r >= 0) {\n\t\t\treturn r != 0;\n\t\t}\n\t}", True),
    (b"void FlexibleMemory::Protect(uint64_t vaddr, uint64_t size, int prot, VirtualMemory::Mode mode,\n"
     b"                             GpuAccessMode gpu_mode) {\n",
     b"if (m_a1p) {\n\t\tBc5A1pProtect(vaddr, size, prot, mode, gpu_mode);\n\t\treturn;\n\t}", True),
    (b"bool FlexibleMemory::Find(uint64_t vaddr, uint64_t* base_addr, size_t* len, int* prot,\n"
     b"                          VirtualMemory::Mode* mode, GpuAccessMode* gpu_mode) {\n",
     b"if (m_a1p) {\n\t\treturn Bc5A1pFind(vaddr, base_addr, len, prot, mode, gpu_mode);\n\t}", True),
    (b"void FlexibleMemory::SetVirtualRangeName(uint64_t vaddr, uint64_t len, const char* name) {\n",
     b"if (m_a1p) {\n\t\tBc5A1pSetName(vaddr, len, name);\n\t\treturn;\n\t}", True),
    (b"void PooledMemory::AddFreeUnlocked(uint64_t start, uint64_t size) {\n",
     b"if (m_a1p) {\n\t\tBc5A1pAddFree(start, size);\n\t\treturn;\n\t}", False),
    (b"bool PooledMemory::ReleaseExpansion(uint64_t phys_addr, uint64_t size) {\n",
     b"if (m_a1p) {\n\t\treturn Bc5A1pReleaseExpansion(phys_addr, size);\n\t}", True),
    (b"bool PooledMemory::Allocate(uint64_t vaddr, uint64_t size, GpuAccessMode gpu_mode,\n"
     b"                            std::vector<Mapping>* mappings) {\n",
     b"if (m_a1p) { // -1 as in FlexibleMemory::Map\n\t\tconst int r = Bc5A1pAllocate(vaddr, size, gpu_mode, mappings);\n"
     b"\t\tif (r >= 0) {\n\t\t\treturn r != 0;\n\t\t}\n\t}", True),
    (b"bool PooledMemory::QueryUnlocked(uint64_t vaddr, uint64_t size,\n"
     b"                                 std::vector<Mapping>* mappings) const {\n",
     b"if (m_a1p) {\n\t\treturn Bc5A1pQueryUnlocked(vaddr, size, mappings);\n\t}", False),
    (b"bool PooledMemory::Release(uint64_t vaddr, uint64_t size, GpuAccessMode* gpu_mode) {\n",
     b"if (m_a1p) {\n\t\treturn Bc5A1pRelease(vaddr, size, gpu_mode);\n\t}", True),
    (b"uint64_t PooledMemory::Available() {\n",
     b"if (m_a1p) {\n\t\tuint64_t available = 0;\n\t\tfor (const auto& [start, size]: m_a1p_free) {\n\t\t\tavailable += size;\n"
     b"\t\t}\n\t\treturn available;\n\t}", True),
    (b"std::vector<PooledMemory::Mapping> PooledMemory::GetMappings() {\n",
     b"if (m_a1p) {\n\t\treturn Bc5A1pOrdered();\n\t}", True),
]

BLOCK_AT = b"static bool UnmapPooledBackingTransactional(const std::vector<PooledMemory::Mapping>& mappings,\n"

BLOCK = r'''
// ---- BC5 exp 0438 A1P (tag a1p438, mka1p.py) ------------------------------------------------------------------------
// The A1P bodies of PhysicalMemory, FlexibleMemory and PooledMemory. Each one is the vector method it stands for, step by
// step, on an ordered map: a lookup is upper_bound/lower_bound, an edit rewrites, erases or emplaces (with a hint) only
// the entries in its window, nothing is sorted or copied whole. The maps hold what the vectors held, in the same order,
// as long as no two entries overlap (then the vector order is the address order); an edit that would add an overlap
// first copies the map back into the vector and the vector code runs from then on, as exp 0412 does for the physical
// table. Every method runs with its owner's mutex held. test_a1p438.cpp runs this text against the vector code.

// ---- PhysicalMemory (only on top of exp 0412's sorted table, KYTY_BC5_PHYSMAP_SORTED=1) ----

const std::vector<PhysicalMemory::AllocatedBlock>& PhysicalMemory::Bc5A1pList() const {
	m_a1p_list.clear();
	m_a1p_list.reserve(m_a1p_mappings.size());
	for (const auto& kv: m_a1p_mappings) {
		m_a1p_list.push_back(kv.second);
	}
	return m_a1p_list;
}

void PhysicalMemory::Bc5A1pBackToOld() {
	m_mappings.clear();
	m_mappings.reserve(m_a1p_mappings.size() + 1);
	for (const auto& kv: m_a1p_mappings) {
		m_mappings.push_back(kv.second);
	}
	m_a1p_mappings.clear();
	m_a1p_by_phys.clear();
	m_a1p_sizes.clear();
	std::vector<AllocatedBlock>().swap(m_a1p_list);
	m_a1p = false;
	std::fprintf(stderr, "[bc5] exp 0438 A1P physmap: an overlapping block or a wrapping unmap, the vector code from here on (tag a1p438)\n");
}

// Every change of the map goes through these three, which keep FindMappings' index (start_addr, map_vaddr) and the
// count of each block size (for the largest one) in step.
void PhysicalMemory::Bc5A1pIndex(const AllocatedBlock& b, bool add) {
	if (add) {
		m_a1p_by_phys.emplace(b.start_addr, b.map_vaddr);
		m_a1p_sizes[b.size]++;
		return;
	}
	m_a1p_by_phys.erase({b.start_addr, b.map_vaddr});
	const auto s = m_a1p_sizes.find(b.size);
	EXIT_IF(s == m_a1p_sizes.end());
	if (--s->second == 0) {
		m_a1p_sizes.erase(s);
	}
}

PhysicalMemory::Bc5A1pTable::iterator PhysicalMemory::Bc5A1pAdd(Bc5A1pTable::iterator hint, const AllocatedBlock& b) {
	Bc5A1pIndex(b, true);
	return m_a1p_mappings.emplace_hint(hint, b.map_vaddr, b);
}

PhysicalMemory::Bc5A1pTable::iterator PhysicalMemory::Bc5A1pDrop(Bc5A1pTable::iterator it) {
	Bc5A1pIndex(it->second, false);
	return m_a1p_mappings.erase(it);
}

// The block at `it` becomes b, whose map_vaddr is the key's.
void PhysicalMemory::Bc5A1pSet(Bc5A1pTable::iterator it, const AllocatedBlock& b) {
	EXIT_IF(b.map_vaddr != it->first);
	Bc5A1pIndex(it->second, false);
	it->second = b;
	Bc5A1pIndex(b, true);
}

// pm412::insert on the map; on a refusal what the vector code does (g_pm412_ok false, the line, push_back).
void PhysicalMemory::Bc5A1pInsert(const AllocatedBlock& mapping) {
	auto& m = m_a1p_mappings;
	if (mapping.map_size != 0 && UINT64_MAX - mapping.map_vaddr >= mapping.map_size) {
		const auto it      = m.lower_bound(mapping.map_vaddr);
		const bool next_ok = it == m.end() || it->second.map_vaddr - mapping.map_vaddr >= mapping.map_size;
		const bool prev_ok = it == m.begin() || mapping.map_vaddr - std::prev(it)->second.map_vaddr >= std::prev(it)->second.map_size; // a1p438-m5
		if (next_ok && prev_ok) {
			Bc5A1pAdd(it, mapping);
			return;
		}
	}
	g_pm412_ok = false;
	std::fprintf(stderr, "[bc5] exp 0412 physmap sorted: block 0x%" PRIx64 "+0x%" PRIx64 " overlaps another, is empty or wraps: the old table code from here on (tag ps412)\n",
	             mapping.map_vaddr, mapping.map_size);
	Bc5A1pBackToOld();
	m_mappings.push_back(mapping);
}

// pm412::host_still_mapped on the map.
bool PhysicalMemory::Bc5A1pHostStillMapped(uint64_t host_vaddr, uint64_t host_size) const {
	auto it = m_a1p_mappings.upper_bound(host_vaddr);
	if (it != m_a1p_mappings.begin()) {
		--it;
	}
	for (; it != m_a1p_mappings.end(); ++it) {
		const auto& b = it->second;
		if (b.map_vaddr >= host_vaddr && b.map_vaddr - host_vaddr >= host_size) {
			break;
		}
		if (b.host_vaddr == host_vaddr && b.host_size == host_size) {
			return true;
		}
	}
	return false;
}

// Unmap in exp 0412's mode 1 (vaddr + size does not wrap here): size != 0 is pm412::unmap (the block that holds vaddr,
// when it matches a case); size 0 is the vector walk (the first block in order that matches a case, then the resort),
// which only blocks starting at or before vaddr and ending at or after it can match.
bool PhysicalMemory::Bc5A1pUnmap(uint64_t vaddr, uint64_t size, GpuAccessMode* gpu_mode, uint64_t* host_vaddr_to_release) {
	auto& m = m_a1p_mappings;
	auto  it = m.upper_bound(vaddr);
	if (size != 0) {
		if (it == m.begin()) {
			return false;
		}
		--it;
		const AllocatedBlock b = it->second;
		if (vaddr - b.map_vaddr >= b.map_size) {
			return false;
		}
		const pm412::Hit h = pm412::match(&b, vaddr, size);
		if (h == pm412::None) {
			return false;
		}
		*gpu_mode = b.gpu_mode;
		if (h == pm412::Whole) {
			Bc5A1pDrop(it);
			if (host_vaddr_to_release != nullptr && b.host_vaddr != 0 && b.host_size != 0 && !Bc5A1pHostStillMapped(b.host_vaddr, b.host_size)) {
				*host_vaddr_to_release = b.host_vaddr;
			}
		} else if (h == pm412::Middle) {
			auto right = b;
			right.start_addr += (vaddr + size) - b.map_vaddr;
			right.size      = b.map_vaddr + b.map_size - (vaddr + size);
			right.map_size  = right.size;
			right.map_vaddr = vaddr + size;
			auto left       = b;
			left.size       = vaddr - b.map_vaddr;
			left.map_size   = left.size;
			Bc5A1pSet(it, left);
			Bc5A1pAdd(std::next(it), right);
		} else if (h == pm412::Head) {
			auto rest = b; // the block's start moves: a new key, in the same place
			rest.start_addr += size;
			rest.size -= size;
			rest.map_vaddr += size;
			rest.map_size -= size;
			Bc5A1pAdd(Bc5A1pDrop(it), rest);
		} else {
			auto left     = b;
			left.size     = vaddr - b.map_vaddr;
			left.map_size = left.size;
			Bc5A1pSet(it, left);
		}
		return true;
	}

	while (it != m.begin()) {
		const auto& p = std::prev(it)->second;
		if (p.map_vaddr + p.map_size < vaddr) {
			break;
		}
		--it;
	}
	for (; it != m.end() && it->second.map_vaddr <= vaddr; ++it) {
		const AllocatedBlock b = it->second;
		if (b.map_vaddr == vaddr && b.map_size == size) {
			*gpu_mode = b.gpu_mode;
			Bc5A1pDrop(it);
			if (host_vaddr_to_release != nullptr && b.host_vaddr != 0 && b.host_size != 0 && !Bc5A1pHostStillMapped(b.host_vaddr, b.host_size)) {
				*host_vaddr_to_release = b.host_vaddr;
			}
			return true;
		}
		if (vaddr > b.map_vaddr && vaddr + size < b.map_vaddr + b.map_size) {
			*gpu_mode = b.gpu_mode;

			AllocatedBlock right = b;
			right.start_addr += (vaddr + size) - b.map_vaddr;
			right.size      = b.map_vaddr + b.map_size - (vaddr + size);
			right.map_size  = right.size;
			right.map_vaddr = vaddr + size;

			AllocatedBlock left = b;
			left.size           = vaddr - b.map_vaddr;
			left.map_size       = left.size;
			Bc5A1pSet(it, left);
			Bc5A1pAdd(std::next(it), right); // where the resort puts it
			return true;
		}
		if (vaddr == b.map_vaddr && size < b.map_size) { // size is 0 here: the block stays as it is
			*gpu_mode = b.gpu_mode;
			return true;
		}
		if (vaddr > b.map_vaddr && vaddr + size == b.map_vaddr + b.map_size) {
			*gpu_mode = b.gpu_mode;

			AllocatedBlock left = b;
			left.size           = vaddr - b.map_vaddr;
			left.map_size       = left.size;
			Bc5A1pSet(it, left);
			return true;
		}
	}
	return false;
}

// ProtectMapping: the blocks that overlap the range become left, middle, right in place; the others stay untouched.
void PhysicalMemory::Bc5A1pProtect(uint64_t vaddr, uint64_t size, int prot, VirtualMemory::Mode mode, GpuAccessMode gpu_mode) {
	if (size == 0 || UINT64_MAX - vaddr < size) {
		return;
	}
	const auto end = vaddr + size;
	auto&      m   = m_a1p_mappings;
	auto       it  = m.upper_bound(vaddr);
	if (it != m.begin()) {
		--it;
	}
	while (it != m.end() && it->second.map_vaddr < end) {
		const auto block = it->second;
		const auto next  = std::next(it);
		if (!VirtualRangesOverlap(vaddr, size, block.map_vaddr, block.map_size)) {
			it = next;
			continue;
		}
		const auto block_end     = block.map_vaddr + block.map_size;
		const auto overlap_start = std::max(vaddr, block.map_vaddr);
		const auto overlap_end   = std::min(end, block_end);
		auto       middle        = block;
		middle.start_addr        = block.start_addr + overlap_start - block.map_vaddr;
		middle.size              = overlap_end - overlap_start;
		middle.map_vaddr         = overlap_start;
		middle.map_size          = middle.size;
		middle.prot              = prot;
		middle.mode              = mode;
		middle.gpu_mode          = gpu_mode;
		if (block.map_vaddr < overlap_start) {
			auto left     = block;
			left.size     = overlap_start - block.map_vaddr;
			left.map_size = left.size;
			Bc5A1pSet(it, left);
			Bc5A1pAdd(next, middle);
		} else {
			Bc5A1pSet(it, middle);
		}
		if (overlap_end < block_end) {
			auto right       = block;
			right.start_addr = block.start_addr + overlap_end - block.map_vaddr;
			right.size       = block_end - overlap_end;
			right.map_vaddr  = overlap_end;
			right.map_size   = right.size;
			Bc5A1pAdd(next, right); // a1p438-m1
		}
		it = next;
	}
}

bool PhysicalMemory::Bc5A1pFind(uint64_t vaddr, uint64_t* base_addr, size_t* len, int* prot, VirtualMemory::Mode* mode,
                                GpuAccessMode* gpu_mode) {
	auto it = m_a1p_mappings.upper_bound(vaddr);
	if (it == m_a1p_mappings.begin()) {
		return false;
	}
	const auto& b = std::prev(it)->second;
	if (vaddr - b.map_vaddr >= b.map_size) {
		return false;
	}
	if (base_addr != nullptr) *base_addr = b.map_vaddr;
	if (len != nullptr) *len = b.map_size;
	if (prot != nullptr) *prot = b.prot;
	if (mode != nullptr) *mode = b.mode;
	if (gpu_mode != nullptr) *gpu_mode = b.gpu_mode;
	return true;
}

// FindMappings by the physical index: a block [start_addr, start_addr + size) can only overlap [phys_addr, ...) when
// it starts after phys_addr - (the largest block size), so only those are tested (the vector code's test); then the
// vector code's sort by map_vaddr (distinct: the blocks do not overlap).
std::vector<PhysicalMemory::AllocatedBlock> PhysicalMemory::Bc5A1pFindMappings(uint64_t phys_addr, size_t len) {
	std::vector<AllocatedBlock> mappings;
	if (m_a1p_sizes.empty()) {
		return mappings;
	}
	const uint64_t largest = m_a1p_sizes.rbegin()->first;
	const uint64_t lo      = phys_addr > largest ? phys_addr - largest : 0; // a1p438-m6
	const uint64_t end     = UINT64_MAX - phys_addr < len ? UINT64_MAX : phys_addr + len;
	for (auto it = m_a1p_by_phys.lower_bound({lo, 0}); it != m_a1p_by_phys.end() && it->first < end; ++it) {
		const auto& m = m_a1p_mappings.find(it->second)->second;
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

void PhysicalMemory::Bc5A1pSetName(uint64_t vaddr, uint64_t len, const char* name) {
	auto it = m_a1p_mappings.upper_bound(vaddr);
	if (it != m_a1p_mappings.begin()) {
		--it;
	}
	for (; it != m_a1p_mappings.end(); ++it) {
		auto& b = it->second;
		if (b.map_vaddr > vaddr && b.map_vaddr - vaddr >= len) break;
		if (VirtualRangesOverlap(vaddr, len, b.map_vaddr, b.map_size)) CopyVirtualRangeName(b.name, name);
	}
}

void PhysicalMemory::Bc5A1pSetMemoryType(uint64_t vaddr, uint64_t len, int memory_type) {
	auto it = m_a1p_mappings.upper_bound(vaddr);
	if (it != m_a1p_mappings.begin()) {
		--it;
	}
	for (; it != m_a1p_mappings.end(); ++it) {
		auto& b = it->second;
		if (b.map_vaddr > vaddr && b.map_vaddr - vaddr >= len) break;
		if (VirtualRangesOverlap(vaddr, len, b.map_vaddr, b.map_size)) b.memory_type = memory_type;
	}
}

// ---- FlexibleMemory ----

const std::vector<FlexibleMemory::AllocatedBlock>& FlexibleMemory::Bc5A1pList() const {
	m_a1p_list.clear();
	m_a1p_list.reserve(m_a1p_allocated.size());
	for (const auto& kv: m_a1p_allocated) {
		m_a1p_list.push_back(kv.second);
	}
	return m_a1p_list;
}

void FlexibleMemory::Bc5A1pBackToOld() {
	m_allocated.clear();
	m_allocated.reserve(m_a1p_allocated.size());
	for (const auto& kv: m_a1p_allocated) {
		m_allocated.push_back(kv.second);
	}
	m_a1p_allocated.clear();
	std::vector<AllocatedBlock>().swap(m_a1p_list);
	m_a1p = false;
	std::fprintf(stderr, "[bc5] exp 0438 A1P flexible: an overlapping, empty or wrapping block, the vector code from here on (tag a1p438)\n");
}

// Whether [start, start + size) can go into the map: not empty, no wrap, no overlap with a block in it.
bool FlexibleMemory::Bc5A1pFits(uint64_t start, uint64_t size) const {
	if (size == 0 || UINT64_MAX - start < size) {
		return false;
	}
	const auto it = m_a1p_allocated.lower_bound(start);
	if (it != m_a1p_allocated.end() && it->second.map_vaddr - start < size) {
		return false;
	}
	if (it != m_a1p_allocated.begin()) {
		const auto& p = std::prev(it)->second;
		if (start - p.map_vaddr < p.map_size) {
			return false;
		}
	}
	return true;
}

// The first block that ends after vaddr: every block before it ends at or before vaddr (the walks' "continue" part).
FlexibleMemory::Bc5A1pTable::iterator FlexibleMemory::Bc5A1pFirstEndingAfter(uint64_t vaddr) {
	auto it = m_a1p_allocated.upper_bound(vaddr);
	if (it != m_a1p_allocated.begin() && std::prev(it)->second.map_vaddr + std::prev(it)->second.map_size > vaddr) { // a1p438-m2
		--it;
	}
	return it;
}

int FlexibleMemory::Bc5A1pMap(uint64_t vaddr, size_t len, int prot, VirtualMemory::Mode mode, GpuAccessMode gpu_mode,
                              const char* name) {
	const auto available = (Size() >= m_allocated_total ? Size() - m_allocated_total : 0);
	if (len == 0 || len > available) {
		LOGF_COLOR(Log::Color::Red,
		           "\t flexible memory exhausted: configured = 0x%016" PRIx64
		           ", allocated = 0x%016" PRIx64 ", available = 0x%016" PRIx64
		           ", requested = 0x%016" PRIx64 "\n",
		           Size(), m_allocated_total, available, static_cast<uint64_t>(len));
		return 0;
	}
	if (!Bc5A1pFits(vaddr, len)) {
		Bc5A1pBackToOld();
		return -1;
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
		return 0;
	}

	std::vector<AllocatedBlock> mapped;
	for (const auto& block: blocks) {
		if (!g_guest_address_space->ZeroBacking(block.backing_offset, block.map_size)) {
			for (auto it = mapped.rbegin(); it != mapped.rend(); ++it) {
				EXIT_IF(!g_guest_address_space->UnmapBacking(it->map_vaddr, it->map_size));
			}
			return 0;
		}
		if (!g_guest_address_space->MapBacking(block.map_vaddr, block.map_size,
		                                       block.backing_offset, block.mode)) {
			for (auto it = mapped.rbegin(); it != mapped.rend(); ++it) {
				EXIT_IF(!g_guest_address_space->UnmapBacking(it->map_vaddr, it->map_size));
			}
			return 0;
		}
		mapped.push_back(block);
	}

	auto hint = m_a1p_allocated.lower_bound(vaddr);
	for (const auto& block: blocks) {
		auto next = m_free.upper_bound(block.backing_offset);
		EXIT_IF(next == m_free.begin());
		auto range = std::prev(next);
		EXIT_IF(block.backing_offset < range->first ||
		        block.map_size > range->first + range->second - block.backing_offset);
		ConsumeFreeRange(range, block.backing_offset, block.map_size);
		m_a1p_allocated.emplace_hint(hint, block.map_vaddr, block); // the pieces go in ascending, before `hint`
	}
	m_allocated_total += len;

	return 1;
}

bool FlexibleMemory::Bc5A1pUnmap(uint64_t vaddr, uint64_t size, GpuAccessMode* gpu_mode, uint64_t* host_vaddr_to_release) {
	if (host_vaddr_to_release != nullptr) {
		*host_vaddr_to_release = 0;
	}
	if (size == 0 || UINT64_MAX - vaddr < size) {
		return false;
	}

	const auto end     = vaddr + size;
	auto       current = vaddr;
	bool       found   = false;
	const auto first   = Bc5A1pFirstEndingAfter(vaddr);
	for (auto it = first; it != m_a1p_allocated.end(); ++it) {
		const auto& block = it->second;
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

	uint64_t removed = 0;
	for (auto it = first; it != m_a1p_allocated.end() && it->second.map_vaddr < end;) {
		const auto block = it->second;
		const auto next  = std::next(it);
		if (!VirtualRangesOverlap(vaddr, size, block.map_vaddr, block.map_size)) {
			it = next;
			continue;
		}
		const auto block_end     = block.map_vaddr + block.map_size;
		const auto overlap_start = std::max(vaddr, block.map_vaddr);
		const auto overlap_end   = std::min(end, block_end);
		const auto overlap_size  = overlap_end - overlap_start;
		AddFreeRange(block.backing_offset + overlap_start - block.map_vaddr, overlap_size);
		removed += overlap_size;

		if (block.map_vaddr < overlap_start) {
			it->second.map_size = overlap_start - block.map_vaddr; // the left piece keeps the node
		} else {
			m_a1p_allocated.erase(it);
		}
		if (overlap_end < block_end) {
			auto right           = block;
			right.map_vaddr      = overlap_end;
			right.map_size       = block_end - overlap_end;
			right.backing_offset = block.backing_offset + overlap_end - block.map_vaddr;
			m_a1p_allocated.emplace_hint(next, right.map_vaddr, right);
		}
		it = next;
	}
	EXIT_IF(removed != size || removed > m_allocated_total);
	m_allocated_total -= removed;
	return true;
}

bool FlexibleMemory::Bc5A1pSnapshot(uint64_t vaddr, uint64_t size, std::vector<AllocatedBlock>* blocks) {
	blocks->clear();
	if (size == 0 || UINT64_MAX - vaddr < size) {
		return false;
	}

	const auto end     = vaddr + size;
	auto       current = vaddr;
	for (auto it = Bc5A1pFirstEndingAfter(vaddr); it != m_a1p_allocated.end(); ++it) {
		const auto& block     = it->second;
		const auto  block_end = block.map_vaddr + block.map_size;
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

int FlexibleMemory::Bc5A1pRestore(const std::vector<AllocatedBlock>& blocks) {
	if (blocks.empty()) {
		return 0;
	}
	{ // every block must fit the map, and the blocks must not overlap each other
		std::map<uint64_t, uint64_t> seen;
		for (const auto& block: blocks) {
			bool fits = Bc5A1pFits(block.map_vaddr, block.map_size);
			if (fits) {
				const auto it = seen.lower_bound(block.map_vaddr);
				if ((it != seen.end() && it->first - block.map_vaddr < block.map_size) ||
				    (it != seen.begin() && block.map_vaddr - std::prev(it)->first < std::prev(it)->second)) {
					fits = false;
				} else {
					seen.emplace_hint(it, block.map_vaddr, block.map_size);
				}
			}
			if (!fits) {
				Bc5A1pBackToOld();
				return -1;
			}
		}
	}

	for (const auto& block: blocks) {
		auto next = m_free.upper_bound(block.backing_offset);
		if (next == m_free.begin()) {
			return 0;
		}
		const auto range = std::prev(next);
		if (block.backing_offset < range->first ||
		    block.map_size > range->first + range->second - block.backing_offset) {
			return 0;
		}
	}

	std::vector<AllocatedBlock> mapped;
	for (const auto& block: blocks) {
		if (!g_guest_address_space->MapBacking(block.map_vaddr, block.map_size,
		                                       block.backing_offset, block.mode)) {
			for (auto it = mapped.rbegin(); it != mapped.rend(); ++it) {
				EXIT_IF(!g_guest_address_space->UnmapBacking(it->map_vaddr, it->map_size));
			}
			return 0;
		}
		mapped.push_back(block);
	}

	for (const auto& block: blocks) {
		auto next = m_free.upper_bound(block.backing_offset);
		EXIT_IF(next == m_free.begin());
		auto range = std::prev(next);
		ConsumeFreeRange(range, block.backing_offset, block.map_size);
		m_a1p_allocated.emplace(block.map_vaddr, block);
		m_allocated_total += block.map_size;
	}
	return 1;
}

void FlexibleMemory::Bc5A1pProtect(uint64_t vaddr, uint64_t size, int prot, VirtualMemory::Mode mode, GpuAccessMode gpu_mode) {
	if (size == 0 || UINT64_MAX - vaddr < size) {
		return;
	}
	const auto end = vaddr + size;
	auto&      m   = m_a1p_allocated;
	auto       it  = m.upper_bound(vaddr);
	if (it != m.begin()) {
		--it;
	}
	while (it != m.end() && it->second.map_vaddr < end) {
		const auto block = it->second;
		const auto next  = std::next(it);
		if (!VirtualRangesOverlap(vaddr, size, block.map_vaddr, block.map_size)) {
			it = next;
			continue;
		}
		const auto block_end     = block.map_vaddr + block.map_size;
		const auto overlap_start = std::max(vaddr, block.map_vaddr);
		const auto overlap_end   = std::min(end, block_end);
		auto       middle        = block;
		middle.map_vaddr         = overlap_start;
		middle.map_size          = overlap_end - overlap_start;
		middle.backing_offset    = block.backing_offset + overlap_start - block.map_vaddr;
		middle.prot              = prot;
		middle.mode              = mode;
		middle.gpu_mode          = gpu_mode;
		if (block.map_vaddr < overlap_start) {
			it->second.map_size = overlap_start - block.map_vaddr; // the left piece keeps the node
			m.emplace_hint(next, middle.map_vaddr, middle);
		} else {
			it->second = middle;
		}
		if (overlap_end < block_end) {
			auto right           = block;
			right.map_vaddr      = overlap_end;
			right.map_size       = block_end - overlap_end;
			right.backing_offset = block.backing_offset + overlap_end - block.map_vaddr;
			m.emplace_hint(next, right.map_vaddr, right);
		}
		it = next;
	}
}

bool FlexibleMemory::Bc5A1pFind(uint64_t vaddr, uint64_t* base_addr, size_t* len, int* prot, VirtualMemory::Mode* mode,
                                GpuAccessMode* gpu_mode) {
	auto it = m_a1p_allocated.upper_bound(vaddr);
	if (it == m_a1p_allocated.begin()) {
		return false;
	}
	const auto& b = std::prev(it)->second;
	if (!(vaddr >= b.map_vaddr && vaddr < b.map_vaddr + b.map_size)) {
		return false;
	}
	if (base_addr != nullptr) *base_addr = b.map_vaddr;
	if (len != nullptr) *len = b.map_size;
	if (prot != nullptr) *prot = b.prot;
	if (mode != nullptr) *mode = b.mode;
	if (gpu_mode != nullptr) *gpu_mode = b.gpu_mode;
	return true;
}

void FlexibleMemory::Bc5A1pSetName(uint64_t vaddr, uint64_t len, const char* name) {
	auto it = m_a1p_allocated.upper_bound(vaddr);
	if (it != m_a1p_allocated.begin()) {
		--it;
	}
	for (; it != m_a1p_allocated.end(); ++it) {
		auto& b = it->second;
		if (b.map_vaddr > vaddr && b.map_vaddr - vaddr >= len) break;
		if (VirtualRangesOverlap(vaddr, len, b.map_vaddr, b.map_size)) CopyVirtualRangeName(b.name, name);
	}
}

// ---- PooledMemory ----

// The vector's order: by the Allocate piece a mapping comes from, then (pieces of one split) by vaddr.
std::vector<PooledMemory::Mapping> PooledMemory::Bc5A1pOrdered() const {
	std::vector<const Bc5A1pMapping*> order;
	order.reserve(m_a1p_mappings.size());
	for (const auto& kv: m_a1p_mappings) {
		order.push_back(&kv.second);
	}
	std::sort(order.begin(), order.end(), [](const Bc5A1pMapping* a, const Bc5A1pMapping* b) {
		return a->seq != b->seq ? a->seq < b->seq : a->m.vaddr < b->m.vaddr; // a1p438-m3
	});
	std::vector<Mapping> out;
	out.reserve(order.size());
	for (const auto* p: order) {
		out.push_back(p->m);
	}
	return out;
}

void PooledMemory::Bc5A1pBackToOld() {
	m_mappings = Bc5A1pOrdered();
	m_free.clear();
	for (const auto& [start, size]: m_a1p_free) {
		m_free.push_back({start, size});
	}
	m_a1p_mappings.clear();
	m_a1p_free.clear();
	m_a1p = false;
	std::fprintf(stderr, "[bc5] exp 0438 A1P pooled: an overlapping mapping, the vector code from here on (tag a1p438)\n");
}

// AddFreeUnlocked: the range merged with the ranges it overlaps or touches (the vector code's sort-and-merge result).
void PooledMemory::Bc5A1pAddFree(uint64_t start, uint64_t size) {
	if (size == 0) {
		return;
	}
	auto end  = start + size;
	auto next = m_a1p_free.lower_bound(start);
	if (next != m_a1p_free.begin()) {
		auto previous = std::prev(next);
		if (previous->first + previous->second >= start) {
			start = previous->first;
			end   = std::max(end, previous->first + previous->second);
			next  = m_a1p_free.erase(previous);
		}
	}
	while (next != m_a1p_free.end() && next->first <= end) { // a1p438-m4
		end  = std::max(end, next->first + next->second);
		next = m_a1p_free.erase(next);
	}
	m_a1p_free.emplace_hint(next, start, end - start);
	if (m_a1p_free_touching) { // the vector code merges every pair, not only the ones around the new range
		m_a1p_free_touching = false;
		for (auto it = m_a1p_free.begin(); it != m_a1p_free.end();) {
			const auto following = std::next(it);
			if (following != m_a1p_free.end() && following->first <= it->first + it->second) {
				it->second = std::max(it->first + it->second, following->first + following->second) - it->first;
				m_a1p_free.erase(following);
			} else {
				it = following;
			}
		}
	}
}

bool PooledMemory::Bc5A1pReleaseExpansion(uint64_t phys_addr, uint64_t size) {
	const auto expansion = std::find_if(m_expansions.begin(), m_expansions.end(), [phys_addr, size](const auto& range) {
		return range.start == phys_addr && range.size == size;
	});
	if (expansion == m_expansions.end()) {
		return false;
	}
	for (const auto& [key, mapping]: m_a1p_mappings) {
		if (VirtualRangesOverlap(phys_addr, size, mapping.m.phys_addr, mapping.m.size)) {
			return false;
		}
	}

	// The free ranges are sorted and disjoint; they do not touch, except after an empty expansion was released from
	// the inside of one (the two pieces then touch until the next AddFree merges every pair, as the vector code does).
	// So for a non-empty expansion the only range that can hold it is the last one starting at or before it; for an
	// empty one, the vector code's search: the first range, in order, that holds it.
	const auto end        = phys_addr + size;
	auto       free_range = m_a1p_free.end();
	if (size != 0) {
		free_range = m_a1p_free.upper_bound(phys_addr);
		if (free_range == m_a1p_free.begin()) {
			return false;
		}
		--free_range;
		if (!(phys_addr >= free_range->first && end <= free_range->first + free_range->second)) {
			return false;
		}
	} else {
		free_range = std::find_if(m_a1p_free.begin(), m_a1p_free.end(), [phys_addr, end](const auto& r) {
			return phys_addr >= r.first && end <= r.first + r.second;
		});
		if (free_range == m_a1p_free.end()) {
			return false;
		}
	}

	const auto old_start  = free_range->first;
	const auto old_end    = free_range->first + free_range->second;
	const auto left_size  = phys_addr - old_start;
	const auto right_size = old_end - end;
	const auto hint       = m_a1p_free.erase(free_range);
	if (left_size != 0) {
		m_a1p_free.emplace_hint(hint, old_start, left_size);
	}
	if (right_size != 0) {
		m_a1p_free.emplace_hint(hint, end, right_size);
	}
	if (size == 0 && left_size != 0 && right_size != 0) {
		m_a1p_free_touching = true;
	}
	m_expansions.erase(expansion);
	return true;
}

int PooledMemory::Bc5A1pAllocate(uint64_t vaddr, uint64_t size, GpuAccessMode gpu_mode, std::vector<Mapping>* mappings) {
	{ // the vector code keeps a mapping that overlaps another; the map cannot
		const auto it = m_a1p_mappings.lower_bound(vaddr);
		if ((it != m_a1p_mappings.end() && it->first - vaddr < size) ||
		    (it != m_a1p_mappings.begin() && vaddr - std::prev(it)->first < std::prev(it)->second.m.size)) {
			Bc5A1pBackToOld();
			return -1;
		}
	}
	// The vector code's walk on a copy: each piece is the head of the next free range (none is empty).
	auto current   = vaddr;
	auto remaining = size;
	for (auto it = m_a1p_free.begin(); it != m_a1p_free.end() && remaining != 0; ++it) {
		const auto part_size = std::min(it->second, remaining);
		mappings->push_back({current, part_size, it->first, gpu_mode});
		current += part_size;
		remaining -= part_size;
	}
	if (remaining != 0) {
		mappings->clear();
		return 0;
	}

	auto hint = m_a1p_mappings.lower_bound(vaddr);
	for (const auto& mapping: *mappings) {
		auto range = m_a1p_free.begin();
		if (mapping.size == range->second) {
			m_a1p_free.erase(range);
		} else {
			auto node = m_a1p_free.extract(range); // the range's head is taken: the same node under its new start
			node.key() += mapping.size;
			node.mapped() -= mapping.size;
			m_a1p_free.insert(std::move(node));
		}
		m_a1p_mappings.emplace_hint(hint, mapping.vaddr, Bc5A1pMapping {mapping, m_a1p_seq++});
	}
	return 1;
}

bool PooledMemory::Bc5A1pQueryUnlocked(uint64_t vaddr, uint64_t size, std::vector<Mapping>* mappings) const {
	EXIT_IF(mappings == nullptr);
	mappings->clear();
	if (vaddr == 0 || size == 0 || UINT64_MAX - vaddr < size) {
		return false;
	}

	const auto end     = vaddr + size;
	auto       current = vaddr;
	while (current < end) {
		auto it = m_a1p_mappings.upper_bound(current);
		if (it == m_a1p_mappings.begin()) {
			mappings->clear();
			return false;
		}
		const auto& m = std::prev(it)->second.m;
		if (!(current >= m.vaddr && current < m.vaddr + m.size)) {
			mappings->clear();
			return false;
		}
		const auto part_size = std::min(end, m.vaddr + m.size) - current;
		mappings->push_back({current, part_size, m.phys_addr + (current - m.vaddr), m.gpu_mode});
		current += part_size;
	}
	return true;
}

bool PooledMemory::Bc5A1pRelease(uint64_t vaddr, uint64_t size, GpuAccessMode* gpu_mode) {
	std::vector<Mapping> released;
	if (!Bc5A1pQueryUnlocked(vaddr, size, &released)) {
		return false;
	}

	*gpu_mode      = released.front().gpu_mode;
	const auto end = vaddr + size;
	auto       it  = m_a1p_mappings.upper_bound(vaddr);
	if (it != m_a1p_mappings.begin()) {
		--it;
	}
	while (it != m_a1p_mappings.end() && it->first < end) {
		const auto mapping     = it->second.m;
		const auto seq         = it->second.seq;
		const auto next        = std::next(it);
		const auto mapping_end = mapping.vaddr + mapping.size;
		const auto cut_start   = std::max(vaddr, mapping.vaddr);
		const auto cut_end     = std::min(end, mapping_end);
		if (cut_start >= cut_end) {
			it = next;
			continue;
		}
		if (mapping.vaddr < cut_start) {
			it->second.m.size = cut_start - mapping.vaddr; // the left piece keeps the node
		} else {
			m_a1p_mappings.erase(it);
		}
		if (cut_end < mapping_end) {
			auto right      = mapping;
			right.vaddr     = cut_end;
			right.size      = mapping_end - cut_end;
			right.phys_addr = mapping.phys_addr + (cut_end - mapping.vaddr);
			m_a1p_mappings.emplace_hint(next, right.vaddr, Bc5A1pMapping {right, seq});
		}
		it = next;
	}
	for (const auto& mapping: released) {
		Bc5A1pAddFree(mapping.phys_addr, mapping.size);
	}
	return true;
}
// ---- end BC5 exp 0438 A1P (tag a1p438) ----

'''.lstrip("\n").encode()

# Planted bugs for the test (A1P bodies only).
MUTANTS = {
    # ProtectMapping drops the right piece of a split block
    "m1": (b"\t\t\tBc5A1pAdd(next, right); // a1p438-m1\n", b"\t\t\t(void)right;\n"),
    # the flexible walks never step back to the block that holds vaddr
    "m2": (b"std::prev(it)->second.map_vaddr + std::prev(it)->second.map_size > vaddr) { // a1p438-m2\n",
           b"std::prev(it)->second.map_vaddr > vaddr) { // a1p438-m2\n"),
    # GetMappings in vaddr order, not the vector's order
    "m3": (b"return a->seq != b->seq ? a->seq < b->seq : a->m.vaddr < b->m.vaddr; // a1p438-m3\n",
           b"return a->m.vaddr < b->m.vaddr; // a1p438-m3\n"),
    # a released pooled range is not merged with a free range that starts right at its end
    "m4": (b"next->first <= end) { // a1p438-m4\n", b"next->first < end) { // a1p438-m4\n"),
    # a physical block overlapping its left neighbour goes into the map instead of sending the table back
    "m5": (b"const bool prev_ok = it == m.begin() || mapping.map_vaddr - std::prev(it)->second.map_vaddr >= std::prev(it)->second.map_size; // a1p438-m5\n",
           b"const bool prev_ok = true; // a1p438-m5\n"),
    # FindMappings' window starts at phys_addr: misses a block that starts before it
    "m6": (b"const uint64_t lo      = phys_addr > largest ? phys_addr - largest : 0; // a1p438-m6\n",
           b"const uint64_t lo      = phys_addr + 0 * largest; // a1p438-m6\n"),
}


def md5(b):
    return hashlib.md5(b).hexdigest()


def once(data, old, new, what):
    n = data.count(old)
    assert n == 1, f"{what}: {n} matches, want 1"
    return data.replace(old, new)


LOCK_RE = re.compile(rb"\tCommon::LockGuard +lock\(m_mutex\);\n")


def dispatch(data, sig, stmt, after_lock):
    n = data.count(sig)
    assert n == 1, f"dispatch {sig[:60]!r}: {n} matches, want 1"
    i = data.index(sig) + len(sig)
    if after_lock:
        m = LOCK_RE.match(data, i) or LOCK_RE.search(data, i, i + 300)
        assert m is not None, f"dispatch {sig[:60]!r}: no lock line"
        assert data.rfind(b"\n}\n", i, m.start()) < 0, f"dispatch {sig[:60]!r}: lock line outside the method"
        i = m.end()
    line = b"\t" + stmt + b" " + TAG + b"\n"
    return data[:i] + line + data[i:]


def apply(src, dst):
    data = open(src, "rb").read()
    print(f"in  md5 {md5(data)}")
    assert b"\r\n" not in data, "CRLF input"
    assert b"a1p438" not in data, "input already has A1P"
    data = once(data, SWITCH_OLD, SWITCH_NEW, "switch")
    data = once(data, PCTOR_OLD, PCTOR_NEW, "PhysicalMemory ctor")
    data = once(data, PGET_OLD, PGET_NEW, "PhysicalMemory::GetMappings")
    data = once(data, PMEM_OLD, PMEM_NEW, "PhysicalMemory members")
    data = once(data, FCTOR_OLD, FCTOR_NEW, "FlexibleMemory ctor")
    data = once(data, FGET_OLD, FGET_NEW, "FlexibleMemory::GetBlocks")
    data = once(data, FMEM_OLD, FMEM_NEW, "FlexibleMemory members")
    data = once(data, QCTOR_OLD, QCTOR_NEW, "PooledMemory ctor")
    data = once(data, QMEM_OLD, QMEM_NEW, "PooledMemory members")
    data = once(data, MAPCHK_OLD, MAPCHK_NEW, "PhysicalMemory::Map 0412 check walk")
    data = once(data, MAPCNT_OLD, MAPCNT_NEW, "PhysicalMemory::Map 0412 check count")
    data = once(data, MAPINS_OLD, MAPINS_NEW, "PhysicalMemory::Map insert")
    data = once(data, PUNMAP_OLD, PUNMAP_NEW, "PhysicalMemory::Unmap")
    for sig, stmt, after_lock in DISPATCH:
        data = dispatch(data, sig, stmt, after_lock)
    data = once(data, BLOCK_AT, BLOCK + BLOCK_AT, "A1P bodies")
    assert b"\r\n" not in data
    open(dst, "wb").write(data)
    print(f"out md5 {md5(data)}")


def cut(data, begin, end, what, include_end=False):
    assert data.count(begin) == 1, f"extract {what}: begin x{data.count(begin)}"
    i = data.find(begin)
    j = data.find(end, i)
    assert j >= 0 and data.count(end) == 1, f"extract {what}: end"
    return data[i:j + (len(end) if include_end else 0)]


def extract(src, dst, mutant=None):
    data = open(src, "rb").read()
    helpers = cut(data, b"static void CopyVirtualRangeName",
                  b"#if defined(KYTY_VIRTUAL_MEMORY_ALLOCATION_TESTS)\nstatic uint32_t g_test_backing_store", "helpers")
    classes = cut(data, b"namespace pm412 {\n", b"static std::unique_ptr<PhysicalMemory>    g_physical_memory;", "classes")
    aligned = cut(data, b"struct AlignedPos {\n", b"static_assert(!GetAlignedPos(UINT64_MAX - 1, 4).valid);\n", "aligned", True)
    methods = cut(data, b"bool PhysicalMemory::Alloc(", BLOCK_AT, "methods")
    if mutant:
        old, new = MUTANTS[mutant]
        k = methods.find(b"// ---- BC5 exp 0438 A1P (tag a1p438, mka1p.py)")
        assert k >= 0
        methods = methods[:k] + once(methods[k:], old, new, f"mutant {mutant}")
    out = (b"// generated by mka1p.py --extract from " + md5(data).encode() + (b" mutant " + mutant.encode() if mutant else b"") +
           b"\n#pragma once\n#include \"stub_a1p.h\"\nnamespace Libs::LibKernel::Memory {\n" + helpers + classes + aligned + methods +
           b"} // namespace Libs::LibKernel::Memory\n")
    open(dst, "wb").write(out)
    print(f"extract {dst} from {md5(data)}{' mutant ' + mutant if mutant else ''}: md5 {md5(out)}")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "--extract":
        assert len(a) in (3, 4), "usage: mka1p.py --extract OUT_memory.cpp HEADER.h [m1..m6]"
        extract(a[1], a[2], a[3] if len(a) == 4 else None)
    else:
        assert len(a) == 2, "usage: mka1p.py IN_memory.cpp OUT_memory.cpp"
        apply(a[0], a[1])
