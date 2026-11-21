// SPDX-License-Identifier: GPL-2.0-only
// BC5 exp 0438 A1P (tag a1p438): differential test of the REAL PhysicalMemory, FlexibleMemory and PooledMemory code,
// extracted from a memory.cpp made by mka1p.py (a1p_real.h). One object of each class runs the vector code
// (constructed with false), one the A1P maps (true); both get the same random operations, and after each one every
// result and the full table contents (vectors against maps, free lists, totals, the backing calls) must be equal.
//   test_a1p438 [ops_per_seed] [seeds]     the differential test, exit 1 on any difference
//   test_a1p438 --bench                    old against new edit costs at 29,000 entries
#include "stub_a1p.h"
#define private public // the test reads the tables themselves
#include "a1p_real.h"
#undef private

#include <chrono>

using namespace Libs::LibKernel::Memory;

static constexpr uint64_t P = 0x4000;          // the guest page
static constexpr uint64_t B = 0x100000000ull;  // where the test's guest mappings start

static uint64_t g_rng = 1;
static uint64_t Next() {
	uint64_t z = (g_rng += 0x9e3779b97f4a7c15ull);
	z          = (z ^ (z >> 30u)) * 0xbf58476d1ce4e5b9ull;
	z          = (z ^ (z >> 27u)) * 0x94d049bb133111ebull;
	return z ^ (z >> 31u);
}
static uint64_t Rnd(uint64_t n) { return n == 0 ? 0 : Next() % n; }
static bool     Chance(uint64_t per_mille) { return Rnd(1000) < per_mille; }

static uint64_t    g_pass = 0, g_fail = 0, g_seed = 0, g_op = 0;
static const char* g_cls  = "";
static void        Check(bool ok, const char* what) {
    if (ok) {
        g_pass++;
        return;
    }
    if (g_fail++ < 12) {
        std::fprintf(stderr, "FAIL %s seed %" PRIu64 " op %" PRIu64 ": %s\n", g_cls, g_seed, g_op, what);
    }
}

static const char* const NAMES[] = {"a", "bc", "main", "", nullptr, "a-name-longer-than-thirty-two-characters-xx"};
static const char*       RndName() { return NAMES[Rnd(6)]; }
static auto              RndMode() { return static_cast<VirtualMemory::Mode>(Rnd(8)); }
static auto              RndGpu() { return static_cast<GpuAccessMode>(Rnd(4)); }
static uint64_t          RndLen() { // mostly pages, sometimes odd, empty or wrapping
	const uint64_t r = Rnd(100);
	if (r < 3) return 0;
	if (r < 5) return UINT64_MAX - Rnd(3);
	if (r < 12) return Rnd(40) * P + Rnd(P);
	return Rnd(40) * P;
}

// ---- PhysicalMemory --------------------------------------------------------------------------------------------------
using PB = PhysicalMemory::AllocatedBlock;
static bool Eq(const PB& a, const PB& b) {
	return a.start_addr == b.start_addr && a.size == b.size && a.map_vaddr == b.map_vaddr && a.map_size == b.map_size &&
	       a.host_vaddr == b.host_vaddr && a.host_size == b.host_size && a.prot == b.prot && a.mode == b.mode &&
	       a.gpu_mode == b.gpu_mode && a.memory_type == b.memory_type && a.pool_expansion == b.pool_expansion &&
	       std::memcmp(a.name, b.name, sizeof(a.name)) == 0;
}
template <class T, class F> static bool EqV(const std::vector<T>& a, const std::vector<T>& b, F eq) {
	if (a.size() != b.size()) return false;
	for (size_t i = 0; i < a.size(); i++)
		if (!eq(a[i], b[i])) return false;
	return true;
}
static std::vector<PB> Mappings(PhysicalMemory& p) { // as RegisterCallbacks reads it: under the owner's mutex
	p.GetMutex().Lock();
	std::vector<PB> v = p.GetMappings();
	p.GetMutex().Unlock();
	return v;
}
static bool Overlaps(const std::vector<PB>& v, uint64_t a, uint64_t s) {
	for (const auto& b: v)
		if (VirtualRangesOverlap(a, s, b.map_vaddr, b.map_size)) return true;
	return false;
}
static bool SameMap(const std::map<uint64_t, PB>& a, const std::map<uint64_t, PB>& b) {
	if (a.size() != b.size()) return false;
	for (auto i = a.begin(), j = b.begin(); i != a.end(); ++i, ++j)
		if (i->first != j->first || !Eq(i->second, j->second)) return false;
	return true;
}

static uint64_t g_phys_back = 0, g_a1p_ops[3] = {0, 0, 0}, g_all_ops[3] = {0, 0, 0}; // seeds that went back to the vector code; ops run with A1P on

static void PhysSeed(uint64_t seed, uint64_t ops) {
	g_cls        = "physical";
	g_pm412_ok   = true;
	const bool   allow_overlap = seed % 3 == 2;
	PhysicalMemory o(false), n(true);
	Check(!o.m_a1p && n.m_a1p == (Pm412Mode() == 1), "A1P on exactly in exp 0412 mode 1");
	bool fell_back = false;
	for (g_op = 0; g_op < ops; g_op++) {
		const auto     list = Mappings(o);
		const uint64_t r    = Rnd(100);
		const PB*      pick = list.empty() ? nullptr : &list[Rnd(list.size())];
		const uint64_t near = pick != nullptr ? pick->map_vaddr + (Rnd(pick->map_size / P + 3) - 1) * P : B + Rnd(4000) * P;
		if (r < 8 || o.m_physical.empty()) { // Alloc
			const uint64_t len   = (1 + Rnd(32)) * P;
			const uint64_t align = Chance(500) ? P << Rnd(3) : 0;
			const uint64_t start = Chance(800) ? 0 : Rnd(1u << 16u) * P;
			const bool     pool  = Chance(50);
			const int      type  = static_cast<int>(Rnd(4));
			uint64_t       a = 1, b = 2;
			Check(o.Alloc(start, UINT64_MAX, len, align, &a, type, pool) == n.Alloc(start, UINT64_MAX, len, align, &b, type, pool) && a == b, "Alloc");
		} else if (r < 35) { // Map
			auto it = o.m_physical.begin();
			std::advance(it, static_cast<long>(Rnd(o.m_physical.size())));
			const auto& blk  = it->second;
			uint64_t    phys = blk.start_addr + Rnd(blk.size / P) * P;
			uint64_t    len  = (1 + Rnd((blk.start_addr + blk.size - phys) / P)) * P;
			if (Chance(100)) len += Rnd(4) * P;
			if (Chance(20)) len = 0;
			if (Chance(10)) phys = UINT64_MAX - P;
			uint64_t vaddr = 0;
			for (int t = 0; t < 30; t++) {
				vaddr = B + Rnd(4000) * P;
				if (!Overlaps(list, vaddr, len)) break;
				if (allow_overlap && Chance(30)) break;
				vaddr = 0;
			}
			if (vaddr == 0) continue;
			const int  prot = static_cast<int>(Rnd(0x40));
			const auto mode = RndMode();
			const auto gpu  = RndGpu();
			Check(o.Map(vaddr, phys, len, prot, mode, gpu) == n.Map(vaddr, phys, len, prot, mode, gpu), "Map");
		} else if (r < 55) { // Unmap
			uint64_t v = near, s = Rnd(4) * P;
			if (pick != nullptr) {
				const uint64_t pages = pick->map_size / P, k = 1 + Rnd(pages > 1 ? pages - 1 : 1);
				switch (Rnd(9)) {
				case 0: v = pick->map_vaddr; s = pick->map_size; break;
				case 1: v = pick->map_vaddr; s = k * P; break;
				case 2: v = pick->map_vaddr + pick->map_size - k * P; s = k * P; break;
				case 3: v = pick->map_vaddr + P; s = (pages > 2 ? Rnd(pages - 2) : 0) * P + Rnd(2) * 0x1000; break;
				case 4: v = pick->map_vaddr; s = 0; break;
				case 5: v = pick->map_vaddr + pick->map_size; s = 0; break;
				case 6: v = pick->map_vaddr + Rnd(pick->map_size); s = 0; break;
				case 7: // a wrapping size (only in the overlap seeds: it sends A1P back to the vector code)
					v = pick->map_vaddr + Rnd(pick->map_size);
					do s = RndLen(); while (!allow_overlap && UINT64_MAX - v < s);
					break;
				default: break;
				}
			}
			const bool    host = Chance(500);
			GpuAccessMode ga = static_cast<GpuAccessMode>(9), gb = static_cast<GpuAccessMode>(9);
			uint64_t      ha = 0xdead, hb = 0xdead;
			const bool    ra = o.Unmap(v, s, &ga, host ? &ha : nullptr);
			const bool    rb = n.Unmap(v, s, &gb, host ? &hb : nullptr);
			Check(ra == rb && ga == gb && ha == hb, "Unmap");
		} else if (r < 67) { // ProtectMapping
			const uint64_t v    = Chance(100) ? B + Rnd(4000) * P : near;
			const uint64_t s    = RndLen();
			const int      prot = static_cast<int>(Rnd(0x40));
			const auto     mode = RndMode();
			const auto     gpu  = RndGpu();
			o.ProtectMapping(v, s, prot, mode, gpu);
			n.ProtectMapping(v, s, prot, mode, gpu);
		} else if (r < 77) { // Find(vaddr)
			const uint64_t      v = near + Rnd(P);
			uint64_t            ba = 1, bb = 1;
			size_t              la = 1, lb = 1;
			int                 pa = -1, pb = -1;
			VirtualMemory::Mode ma = VirtualMemory::Mode::NoAccess, mb = VirtualMemory::Mode::NoAccess;
			GpuAccessMode       ga = GpuAccessMode::NoAccess, gb = GpuAccessMode::NoAccess;
			const uint64_t      mask = Rnd(32);
			const bool          ra   = o.Find(v, (mask & 1u) ? &ba : nullptr, (mask & 2u) ? &la : nullptr, (mask & 4u) ? &pa : nullptr,
			                                  (mask & 8u) ? &ma : nullptr, (mask & 16u) ? &ga : nullptr);
			const bool          rb   = n.Find(v, (mask & 1u) ? &bb : nullptr, (mask & 2u) ? &lb : nullptr, (mask & 4u) ? &pb : nullptr,
			                                  (mask & 8u) ? &mb : nullptr, (mask & 16u) ? &gb : nullptr);
			Check(ra == rb && ba == bb && la == lb && pa == pb && ma == mb && ga == gb, "Find(vaddr)");
		} else if (r < 83) { // FindMappings
			const uint64_t phys = pick != nullptr ? pick->start_addr + (Rnd(pick->size / P + 3) - 1) * P : Rnd(1000) * P;
			const uint64_t len  = Chance(50) ? 0 : Rnd(40) * P + Rnd(2) * 0x100;
			Check(EqV(o.FindMappings(phys, len), n.FindMappings(phys, len), Eq), "FindMappings");
		} else if (r < 89) { // SetVirtualRangeName
			const uint64_t v = near, s = RndLen();
			const char*    nm = RndName();
			o.SetVirtualRangeName(v, s, nm);
			n.SetVirtualRangeName(v, s, nm);
		} else if (r < 94) { // SetVirtualRangeMemoryType
			const uint64_t v = near, s = RndLen();
			const int      t = static_cast<int>(Rnd(8));
			o.SetVirtualRangeMemoryType(v, s, t);
			n.SetVirtualRangeMemoryType(v, s, t);
		} else if (r < 98) { // Release (the physical table only; the mappings must not change)
			auto it = o.m_physical.begin();
			std::advance(it, static_cast<long>(Rnd(o.m_physical.size())));
			const uint64_t pages = it->second.size / P;
			const uint64_t st    = it->second.start_addr + Rnd(pages) * P;
			const uint64_t len   = (1 + Rnd(pages)) * P;
			uint64_t       va = 1, vb = 1, sa = 1, sb = 1;
			GpuAccessMode  ga = GpuAccessMode::NoAccess, gb = GpuAccessMode::NoAccess;
			Check(o.Release(st, len, &va, &sa, &ga) == n.Release(st, len, &vb, &sb, &gb) && va == vb && sa == sb && ga == gb, "Release");
		} else { // Find(phys, next)
			const uint64_t phys = Rnd(1u << 12u) * P;
			const bool     nx   = Chance(500);
			PB             a {}, b {};
			Check(o.Find(phys, nx, &a) == n.Find(phys, nx, &b) && Eq(a, b), "Find(phys)");
		}
		Check(EqV(Mappings(o), Mappings(n), Eq), "the mapping tables");
		Check(SameMap(o.m_physical, n.m_physical) && o.m_free == n.m_free, "the physical blocks and free list");
		Check(n.m_a1p ? n.m_mappings.empty() : n.m_a1p_mappings.empty(), "one table in use");
		if (n.m_a1p) { // FindMappings' index matches the map
			bool     ok    = n.m_a1p_by_phys.size() == n.m_a1p_mappings.size();
			uint64_t count = 0;
			for (const auto& [sz, c]: n.m_a1p_sizes) count += c;
			ok = ok && count == n.m_a1p_mappings.size();
			for (const auto& [key, b]: n.m_a1p_mappings) {
				ok = ok && key == b.map_vaddr && n.m_a1p_by_phys.count({b.start_addr, b.map_vaddr}) == 1 && n.m_a1p_sizes.count(b.size) == 1;
			}
			Check(ok, "the physical index");
		}
		Check(g_pm412_ok || !n.m_a1p, "A1P off once exp 0412 is");
		if (!n.m_a1p && Pm412Mode() == 1) fell_back = true;
		g_a1p_ops[0] += n.m_a1p ? 1 : 0;
		g_all_ops[0]++;
	}
	if (fell_back) g_phys_back++;
}

// ---- FlexibleMemory --------------------------------------------------------------------------------------------------
using FB = FlexibleMemory::AllocatedBlock;
static bool Eq(const FB& a, const FB& b) {
	return a.map_vaddr == b.map_vaddr && a.map_size == b.map_size && a.backing_offset == b.backing_offset &&
	       a.host_vaddr == b.host_vaddr && a.host_size == b.host_size && a.prot == b.prot && a.mode == b.mode &&
	       a.gpu_mode == b.gpu_mode && std::memcmp(a.name, b.name, sizeof(a.name)) == 0;
}
static std::vector<FB> Blocks(FlexibleMemory& f) {
	f.GetMutex().Lock();
	std::vector<FB> v = f.GetBlocks();
	f.GetMutex().Unlock();
	return v;
}
static uint64_t g_flex_back = 0;

// The backing calls of one operation on each object, with the same failure planted.
template <class F> static std::string Backing(int fail_in, F f) {
	g_guest_address_space->log.clear();
	g_guest_address_space->fail_in = fail_in;
	f();
	g_guest_address_space->fail_in = 0;
	return g_guest_address_space->log;
}

static void FlexSeed(uint64_t seed, uint64_t ops) {
	g_cls                       = "flexible";
	g_flexible_memory_size      = 64ull * 1024ull * 1024ull;
	const bool     allow_overlap = seed % 3 == 2;
	FlexibleMemory o(false), n(true);
	bool           fell_back = false;
	bool           overlapped = false; // the vector code aborts (EXIT_IF) when it unmaps overlapping blocks: no Unmap then
	for (g_op = 0; g_op < ops; g_op++) {
		const auto     list = Blocks(o);
		const uint64_t r    = Rnd(100);
		const size_t   idx  = list.empty() ? 0 : Rnd(list.size());
		const FB*      pick = list.empty() ? nullptr : &list[idx];
		const uint64_t near = pick != nullptr ? pick->map_vaddr + (Rnd(pick->map_size / P + 3) - 1) * P : B + Rnd(6000) * P;
		const int      fail = Chance(60) ? static_cast<int>(1 + Rnd(4)) : 0;
		// a range for Unmap/Snapshot: a block, a run of touching blocks, a part of one, or anything
		uint64_t rv = near, rs = RndLen();
		if (pick != nullptr) {
			const uint64_t pages = pick->map_size / P;
			switch (Rnd(6)) {
			case 0: rv = pick->map_vaddr; rs = pick->map_size; break;
			case 1: {
				size_t j = idx;
				while (j + 1 < list.size() && list[j + 1].map_vaddr == list[j].map_vaddr + list[j].map_size && Chance(700)) j++;
				rv = pick->map_vaddr;
				rs = list[j].map_vaddr + list[j].map_size - rv;
				if (Chance(300) && rs > P) rs -= P;
				break;
			}
			case 2: rv = pick->map_vaddr + Rnd(pages) * P; rs = (1 + Rnd(pages)) * P; break;
			case 3: rv = pick->map_vaddr + P; rs = pages > 2 ? Rnd(pages - 2) * P + P : P; break;
			default: break;
			}
		}
		if (r < 25) { // Map
			uint64_t len = Chance(30) ? RndLen() : (1 + Rnd(16)) * P;
			uint64_t vaddr = 0;
			for (int t = 0; t < 30; t++) {
				vaddr     = B + Rnd(6000) * P;
				bool over = false;
				for (const auto& b: list) over = over || VirtualRangesOverlap(vaddr, len, b.map_vaddr, b.map_size);
				if (!over || (allow_overlap && Chance(30))) {
					overlapped = overlapped || over;
					break;
				}
				vaddr = 0;
			}
			if (vaddr == 0) continue;
			if (allow_overlap && Chance(5)) { // a wrapping block
				vaddr      = UINT64_MAX - P;
				overlapped = true;
			}
			const int   prot = static_cast<int>(Rnd(0x40));
			const auto  mode = RndMode();
			const auto  gpu  = RndGpu();
			const char* nm   = RndName();
			bool        ra = false, rb = false;
			const auto  la = Backing(fail, [&] { ra = o.Map(vaddr, len, prot, mode, gpu, nm); });
			const auto  lb = Backing(fail, [&] { rb = n.Map(vaddr, len, prot, mode, gpu, nm); });
			Check(ra == rb && la == lb, "Map");
		} else if (r < 45) { // Unmap
			if (overlapped) continue;
			const bool    host = Chance(500);
			GpuAccessMode ga = static_cast<GpuAccessMode>(9), gb = static_cast<GpuAccessMode>(9);
			uint64_t      ha = 0xdead, hb = 0xdead;
			bool          ra = false, rb = false;
			const auto    la = Backing(fail, [&] { ra = o.Unmap(rv, rs, &ga, host ? &ha : nullptr); });
			const auto    lb = Backing(fail, [&] { rb = n.Unmap(rv, rs, &gb, host ? &hb : nullptr); });
			Check(ra == rb && ga == gb && ha == hb && la == lb, "Unmap");
		} else if (r < 57) { // Snapshot, then maybe Unmap and Restore (the rollback ReplaceFixedRangeWithReserved does)
			std::vector<FB> sa {FB {}}, sb;
			const bool      ra = o.Snapshot(rv, rs, &sa);
			const bool      rb = n.Snapshot(rv, rs, &sb);
			Check(ra == rb && EqV(sa, sb, [](const FB& x, const FB& y) { return Eq(x, y); }), "Snapshot");
			if (allow_overlap && Chance(500)) { // Restore without Unmap: the backing is not free (or, A1P, the blocks overlap)
				bool       xa = false, xb = false;
				const auto la = Backing(fail, [&] { xa = o.Restore(sa); });
				const auto lb = Backing(fail, [&] { xb = n.Restore(sa); });
				Check(xa == xb && la == lb, "Restore over mapped blocks");
			} else if (ra && !overlapped) {
				GpuAccessMode ga = GpuAccessMode::NoAccess, gb = GpuAccessMode::NoAccess;
				Check(o.Unmap(rv, rs, &ga) == n.Unmap(rv, rs, &gb) && ga == gb, "Unmap before Restore");
				// a partial restore (a shifted backing_offset would make the vector code's EXIT_IF fire when two blocks
				// then share a free range: not a valid input)
				if (Chance(200) && sa.size() > 1) sa.pop_back();
				bool       xa = false, xb = false;
				const auto la = Backing(fail, [&] { xa = o.Restore(sa); });
				const auto lb = Backing(fail, [&] { xb = n.Restore(sa); });
				Check(xa == xb && la == lb, "Restore");
			}
		} else if (r < 70) { // Protect
			const uint64_t v = near, s = RndLen();
			const int      prot = static_cast<int>(Rnd(0x40));
			const auto     mode = RndMode();
			const auto     gpu  = RndGpu();
			o.Protect(v, s, prot, mode, gpu);
			n.Protect(v, s, prot, mode, gpu);
		} else if (r < 82) { // Find
			const uint64_t      v  = near + Rnd(P);
			uint64_t            ba = 1, bb = 1;
			size_t              la = 1, lb = 1;
			int                 pa = -1, pb = -1;
			VirtualMemory::Mode ma = VirtualMemory::Mode::NoAccess, mb = VirtualMemory::Mode::NoAccess;
			GpuAccessMode       ga = GpuAccessMode::NoAccess, gb = GpuAccessMode::NoAccess;
			const uint64_t      mask = Rnd(32);
			const bool          ra   = o.Find(v, (mask & 1u) ? &ba : nullptr, (mask & 2u) ? &la : nullptr, (mask & 4u) ? &pa : nullptr,
			                                  (mask & 8u) ? &ma : nullptr, (mask & 16u) ? &ga : nullptr);
			const bool          rb   = n.Find(v, (mask & 1u) ? &bb : nullptr, (mask & 2u) ? &lb : nullptr, (mask & 4u) ? &pb : nullptr,
			                                  (mask & 8u) ? &mb : nullptr, (mask & 16u) ? &gb : nullptr);
			Check(ra == rb && ba == bb && la == lb && pa == pb && ma == mb && ga == gb, "Find");
		} else if (r < 92) { // SetVirtualRangeName
			const uint64_t v = near, s = RndLen();
			const char*    nm = RndName();
			o.SetVirtualRangeName(v, s, nm);
			n.SetVirtualRangeName(v, s, nm);
		} else {
			Check(o.Available() == n.Available(), "Available");
		}
		Check(EqV(Blocks(o), Blocks(n), [](const FB& x, const FB& y) { return Eq(x, y); }), "the block tables");
		Check(o.m_free == n.m_free && o.m_allocated_total == n.m_allocated_total, "the free list and total");
		Check(n.m_a1p ? n.m_allocated.empty() : n.m_a1p_allocated.empty(), "one table in use");
		if (!n.m_a1p) fell_back = overlapped = true;
		g_a1p_ops[1] += n.m_a1p ? 1 : 0;
		g_all_ops[1]++;
	}
	if (fell_back) g_flex_back++;
}

// ---- PooledMemory ----------------------------------------------------------------------------------------------------
using PM = PooledMemory::Mapping;
static bool Eq(const PM& a, const PM& b) {
	return a.vaddr == b.vaddr && a.size == b.size && a.phys_addr == b.phys_addr && a.gpu_mode == b.gpu_mode;
}
static std::vector<std::pair<uint64_t, uint64_t>> Free(const PooledMemory& p) {
	std::vector<std::pair<uint64_t, uint64_t>> v;
	if (p.m_a1p) {
		for (const auto& kv: p.m_a1p_free) v.emplace_back(kv.first, kv.second);
	} else {
		for (const auto& r: p.m_free) v.emplace_back(r.start, r.size);
	}
	return v;
}
static uint64_t g_pool_back = 0;

static void PoolSeed(uint64_t seed, uint64_t ops) {
	g_cls                     = "pooled";
	const bool   allow_overlap = seed % 3 == 2;
	PooledMemory o(false), n(true);
	bool         fell_back = false;
	const auto   eqv       = [](const std::vector<PM>& a, const std::vector<PM>& b) {
        return EqV(a, b, [](const PM& x, const PM& y) { return Eq(x, y); });
	};
	for (g_op = 0; g_op < ops; g_op++) {
		const auto     list = o.GetMappings();
		const uint64_t r    = Rnd(100);
		const size_t   idx  = list.empty() ? 0 : Rnd(list.size());
		const PM*      pick = list.empty() ? nullptr : &list[idx];
		uint64_t       rv = pick != nullptr ? pick->vaddr + (Rnd(pick->size / P + 3) - 1) * P : B + Rnd(6000) * P, rs = RndLen();
		if (pick != nullptr) {
			const uint64_t pages = pick->size / P;
			switch (Rnd(5)) {
			case 0: rv = pick->vaddr; rs = pick->size; break;
			case 1: rv = pick->vaddr + Rnd(pages) * P; rs = (1 + Rnd(3 * pages)) * P; break;
			case 2: rv = pick->vaddr + P; rs = pages > 2 ? Rnd(pages - 2) * P + P : P; break;
			default: break;
			}
		}
		if (r < 10 || (o.m_expansions.empty() && r < 50)) { // Expand
			const uint64_t phys = Chance(100) && !o.m_expansions.empty() ? o.m_expansions[Rnd(o.m_expansions.size())].start + Rnd(8) * P
			                                                             : Rnd(3000) * P;
			const uint64_t size = Chance(20) ? 0 : (1 + Rnd(64)) * P;
			o.Expand(phys, size);
			n.Expand(phys, size);
		} else if (r < 16) { // ReleaseExpansion
			uint64_t phys = Rnd(3000) * P, size = (1 + Rnd(64)) * P;
			if (!o.m_expansions.empty() && Chance(800)) {
				const auto& e = o.m_expansions[Rnd(o.m_expansions.size())];
				phys = e.start;
				size = e.size;
			}
			Check(o.ReleaseExpansion(phys, size) == n.ReleaseExpansion(phys, size), "ReleaseExpansion");
		} else if (r < 42) { // Allocate
			const uint64_t size  = Chance(30) ? RndLen() : (1 + Rnd(24)) * P;
			uint64_t       vaddr = 0;
			for (int t = 0; t < 30; t++) {
				vaddr     = B + Rnd(6000) * P;
				bool over = false;
				for (const auto& m: list) over = over || VirtualRangesOverlap(vaddr, size, m.vaddr, m.size);
				if (!over || (allow_overlap && Chance(30))) break;
				vaddr = 0;
			}
			if (Chance(10)) vaddr = 0;
			const auto      gpu = RndGpu();
			std::vector<PM> ma {PM {}}, mb {PM {}};
			const bool      ra = o.Allocate(vaddr, size, gpu, &ma);
			const bool      rb = n.Allocate(vaddr, size, gpu, &mb);
			Check(ra == rb && eqv(ma, mb), "Allocate");
		} else if (r < 55) { // Query
			std::vector<PM> ma {PM {}}, mb;
			const bool      ra = o.Query(rv, rs, &ma);
			const bool      rb = n.Query(rv, rs, &mb);
			Check(ra == rb && eqv(ma, mb), "Query");
		} else if (r < 80) { // Release
			GpuAccessMode ga = static_cast<GpuAccessMode>(9), gb = static_cast<GpuAccessMode>(9);
			Check(o.Release(rv, rs, &ga) == n.Release(rv, rs, &gb) && ga == gb, "Release");
		} else {
			Check(o.Available() == n.Available(), "Available");
		}
		Check(eqv(o.GetMappings(), n.GetMappings()), "the mappings, in the vector's order");
		Check(Free(o) == Free(n), "the free lists");
		Check(o.m_expansions.size() == n.m_expansions.size() &&
		          std::equal(o.m_expansions.begin(), o.m_expansions.end(), n.m_expansions.begin(),
		                     [](const auto& x, const auto& y) { return x.start == y.start && x.size == y.size; }),
		      "the expansions");
		Check(n.m_a1p ? n.m_mappings.empty() && n.m_free.empty() : n.m_a1p_mappings.empty() && n.m_a1p_free.empty(), "one table in use");
		if (!n.m_a1p) fell_back = true;
		g_a1p_ops[2] += n.m_a1p ? 1 : 0;
		g_all_ops[2]++;
	}
	if (fell_back) g_pool_back++;
}

// ---- bench -----------------------------------------------------------------------------------------------------------
template <class F> static double Ms(F f) {
	const auto t0 = std::chrono::steady_clock::now();
	f();
	return std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
}
static void Row(const char* what, uint64_t k, double a, double b) {
	std::printf("  %-44s %6" PRIu64 " ops: old %10.1f ms (%8.2f us/op), A1P %8.1f ms (%6.2f us/op), old/A1P %.1f\n", what, k, a,
	            a * 1000.0 / static_cast<double>(k), b, b * 1000.0 / static_cast<double>(k), b > 0 ? a / b : 0.0);
}

static int Bench() {
	constexpr uint64_t N = 29000, K = 2000;
	g_guest_address_space->quiet = true;
	std::printf("bench: %" PRIu64 " entries per table (guest pages at every other page), %s\n", N,
	            Pm412Mode() == 1 ? "exp 0412 sorted physical table on" : "exp 0412 sorted physical table OFF");
	int bad = 0;
	{
		g_pm412_ok = true;
		PhysicalMemory o(false), n(true);
		uint64_t       pa = 0, pb = 0;
		EXIT_IF(!o.Alloc(0, UINT64_MAX, N * P, 0, &pa, 0) || !n.Alloc(0, UINT64_MAX, N * P, 0, &pb, 0));
		const double fa = Ms([&] { for (uint64_t i = 0; i < N; i++) o.Map(B + 2 * i * P, pa + i * P, P, 3, VirtualMemory::Mode::ReadWrite, GpuAccessMode::ReadWrite); });
		const double fb = Ms([&] { for (uint64_t i = 0; i < N; i++) n.Map(B + 2 * i * P, pb + i * P, P, 3, VirtualMemory::Mode::ReadWrite, GpuAccessMode::ReadWrite); });
		std::printf("PhysicalMemory\n");
		Row("Map, ascending (fill)", N, fa, fb);
		std::vector<uint64_t> idx(K);
		for (auto& i: idx) i = Rnd(N);
		Row("ProtectMapping of one block", K, Ms([&] { for (auto i: idx) o.ProtectMapping(B + 2 * i * P, P, 1, VirtualMemory::Mode::Read, GpuAccessMode::Read); }),
		    Ms([&] { for (auto i: idx) n.ProtectMapping(B + 2 * i * P, P, 1, VirtualMemory::Mode::Read, GpuAccessMode::Read); }));
		GpuAccessMode g {};
		Row("Unmap whole + Map back", K, Ms([&] { for (auto i: idx) { o.Unmap(B + 2 * i * P, P, &g); o.Map(B + 2 * i * P, pa + i * P, P, 3, VirtualMemory::Mode::ReadWrite, GpuAccessMode::ReadWrite); } }),
		    Ms([&] { for (auto i: idx) { n.Unmap(B + 2 * i * P, P, &g); n.Map(B + 2 * i * P, pb + i * P, P, 3, VirtualMemory::Mode::ReadWrite, GpuAccessMode::ReadWrite); } }));
		Row("Find(vaddr)", 10 * K, Ms([&] { for (uint64_t j = 0; j < 10 * K; j++) o.Find(B + 2 * Rnd(N) * P, nullptr, nullptr, nullptr, nullptr, nullptr); }),
		    Ms([&] { for (uint64_t j = 0; j < 10 * K; j++) n.Find(B + 2 * Rnd(N) * P, nullptr, nullptr, nullptr, nullptr, nullptr); }));
		Row("FindMappings (one page)", K, Ms([&] { for (auto i: idx) (void)o.FindMappings(pa + i * P, P); }),
		    Ms([&] { for (auto i: idx) (void)n.FindMappings(pb + i * P, P); }));
		if (Mappings(o).size() != N || Mappings(n).size() != N) bad++;
	}
	{
		g_flexible_memory_size = 1024ull * 1024ull * 1024ull;
		FlexibleMemory o(false), n(true);
		const double   fa = Ms([&] { for (uint64_t i = 0; i < N; i++) o.Map(B + 2 * i * P, P, 3, VirtualMemory::Mode::ReadWrite, GpuAccessMode::ReadWrite, "f"); });
		const double   fb = Ms([&] { for (uint64_t i = 0; i < N; i++) n.Map(B + 2 * i * P, P, 3, VirtualMemory::Mode::ReadWrite, GpuAccessMode::ReadWrite, "f"); });
		std::printf("FlexibleMemory\n");
		Row("Map, ascending (fill)", N, fa, fb);
		std::vector<uint64_t> idx(K);
		for (auto& i: idx) i = Rnd(N);
		Row("Protect of one block", K, Ms([&] { for (auto i: idx) o.Protect(B + 2 * i * P, P, 1, VirtualMemory::Mode::Read, GpuAccessMode::Read); }),
		    Ms([&] { for (auto i: idx) n.Protect(B + 2 * i * P, P, 1, VirtualMemory::Mode::Read, GpuAccessMode::Read); }));
		GpuAccessMode g {};
		Row("Unmap whole + Map back", K, Ms([&] { for (auto i: idx) { o.Unmap(B + 2 * i * P, P, &g); o.Map(B + 2 * i * P, P, 3, VirtualMemory::Mode::ReadWrite, GpuAccessMode::ReadWrite, "f"); } }),
		    Ms([&] { for (auto i: idx) { n.Unmap(B + 2 * i * P, P, &g); n.Map(B + 2 * i * P, P, 3, VirtualMemory::Mode::ReadWrite, GpuAccessMode::ReadWrite, "f"); } }));
		Row("Find", 10 * K, Ms([&] { for (uint64_t j = 0; j < 10 * K; j++) o.Find(B + 2 * Rnd(N) * P, nullptr, nullptr, nullptr, nullptr, nullptr); }),
		    Ms([&] { for (uint64_t j = 0; j < 10 * K; j++) n.Find(B + 2 * Rnd(N) * P, nullptr, nullptr, nullptr, nullptr, nullptr); }));
		if (Blocks(o).size() != N || Blocks(n).size() != N || !EqV(Blocks(o), Blocks(n), [](const FB& x, const FB& y) { return Eq(x, y); })) bad++;
	}
	{
		PooledMemory o(false), n(true);
		o.Expand(0, 2 * N * P);
		n.Expand(0, 2 * N * P);
		std::vector<PM> m;
		const double    fa = Ms([&] { for (uint64_t i = 0; i < N; i++) o.Allocate(B + 2 * i * P, P, GpuAccessMode::ReadWrite, &m); });
		const double    fb = Ms([&] { for (uint64_t i = 0; i < N; i++) n.Allocate(B + 2 * i * P, P, GpuAccessMode::ReadWrite, &m); });
		std::printf("PooledMemory\n");
		Row("Allocate, ascending (fill)", N, fa, fb);
		std::vector<uint64_t> idx(K);
		for (auto& i: idx) i = Rnd(N);
		GpuAccessMode g {};
		Row("Release + Allocate back", K, Ms([&] { for (auto i: idx) { o.Release(B + 2 * i * P, P, &g); o.Allocate(B + 2 * i * P, P, GpuAccessMode::ReadWrite, &m); } }),
		    Ms([&] { for (auto i: idx) { n.Release(B + 2 * i * P, P, &g); n.Allocate(B + 2 * i * P, P, GpuAccessMode::ReadWrite, &m); } }));
		Row("Query (one page)", 10 * K, Ms([&] { for (uint64_t j = 0; j < 10 * K; j++) o.Query(B + 2 * Rnd(N) * P, P, &m); }),
		    Ms([&] { for (uint64_t j = 0; j < 10 * K; j++) n.Query(B + 2 * Rnd(N) * P, P, &m); }));
		const auto ga = o.GetMappings(), gb = n.GetMappings();
		if (ga.size() != N || !EqV(ga, gb, [](const PM& x, const PM& y) { return Eq(x, y); }) || Free(o) != Free(n)) bad++;
	}
	std::printf("bench end tables %s\n", bad == 0 ? "equal" : "DIFFER");
	return bad == 0 ? 0 : 1;
}

int main(int argc, char** argv) {
	if (argc > 1 && std::strcmp(argv[1], "--bench") == 0) return Bench();
	const uint64_t ops   = argc > 1 ? std::strtoull(argv[1], nullptr, 10) : 20000;
	const uint64_t seeds = argc > 2 ? std::strtoull(argv[2], nullptr, 10) : 12;
	{ // the default constructors read the switch
		g_pm412_ok = true;
		PhysicalMemory p;
		FlexibleMemory f;
		PooledMemory   q;
		const char*    e  = std::getenv("KYTY_BC5_0438_A1P");
		const bool     on = e != nullptr && std::strcmp(e, "1") == 0;
		g_cls             = "switch";
		Check(f.m_a1p == on && q.m_a1p == on && p.m_a1p == (on && Pm412Mode() == 1), "default constructors follow KYTY_BC5_0438_A1P");
	}
	for (uint64_t s = 1; s <= seeds; s++) {
		g_seed = s;
		g_rng  = s * 0x1234567ull;
		PhysSeed(s, ops);
		FlexSeed(s, ops);
		PoolSeed(s, ops);
		if (g_fail >= 100) break; // a mutant: enough
	}
	std::printf("test_a1p438: %" PRIu64 " ops x 3 classes x %" PRIu64 " seeds, PASS %" PRIu64 " FAIL %" PRIu64
	            "; seeds where A1P went back to the vector code: physical %" PRIu64 ", flexible %" PRIu64 ", pooled %" PRIu64 "\n",
	            ops, seeds, g_pass, g_fail, g_phys_back, g_flex_back, g_pool_back);
	std::printf("ops run with A1P still on: physical %" PRIu64 "/%" PRIu64 ", flexible %" PRIu64 "/%" PRIu64 ", pooled %" PRIu64 "/%" PRIu64 "\n",
	            g_a1p_ops[0], g_all_ops[0], g_a1p_ops[1], g_all_ops[1], g_a1p_ops[2], g_all_ops[2]);
	return g_fail == 0 ? 0 : 1;
}
