// SPDX-License-Identifier: GPL-2.0-only
// BC5 exp 0438 A1 (tag a1438): differential test of VirtualRangesMap (and the VirtualRanges dispatcher, in whichever
// mode KYTY_BC5_0438_A1 selects for this process) against the old VirtualRangesVec. The class text comes from the
// generated memory.cpp through `mka1.py --extract` (a1_real.h), not from a copy. Every op runs on all three with the
// same arguments; after every op the op's results, Generation, the full Snapshot, both CountPageTableEntries,
// DirtyWithTouching and a set of probes (Query with flags 0/1/2, QueryOverlap, HasOverlap, QuerySpan, ClampRangeSize,
// Overlapping) are compared. A run stops at its first differing op (later ops would only repeat it).
//   test_a1438 [ops_per_seed] [seeds]      differential run, prints PASS/FAIL counts, exit 1 on any FAIL
//   test_a1438 --bench                     29,000 ranges, timed edits and snapshots for both classes
#include "a1_real.h"

#include <chrono>
#include <random>
#include <string>

using namespace Libs::LibKernel::Memory;
using Range = VirtualRangesVec::Range;

static bool Same(const Range& a, const Range& b) {
	return a.start == b.start && a.size == b.size && a.offset == b.offset && a.protection == b.protection &&
	       a.memory_type == b.memory_type && a.type == b.type && a.disallow_merge == b.disallow_merge &&
	       std::memcmp(a.name, b.name, KERNEL_MAXIMUM_NAME_LENGTH) == 0;
}
static bool Same(const std::vector<Range>& a, const std::vector<Range>& b) {
	if (a.size() != b.size()) return false;
	for (size_t i = 0; i < a.size(); i++)
		if (!Same(a[i], b[i])) return false;
	return true;
}

struct Counts {
	uint64_t pass = 0, fail = 0, ops = 0;
	std::string first;
};

struct Run {
	VirtualRangesVec vec;
	VirtualRangesMap map;
	VirtualRanges    disp;
	Counts&          c;
	bool             bad = false;
	std::string      opname;
	explicit Run(Counts& counts): c(counts) {}

	template <class T> void eq(const T& a, const T& b, const T& d, const char* what) {
		if (a == b && a == d) {
			c.pass++;
			return;
		}
		Fail(what);
	}
	void eqr(bool ok, const char* what) {
		if (ok) {
			c.pass++;
			return;
		}
		Fail(what);
	}
	void Fail(const char* what) {
		c.fail++;
		if (!bad && c.first.empty()) c.first = "op " + std::to_string(c.ops) + " (" + opname + "): " + what;
		bad = true;
	}
};

static const char* kNames[] = {"", "a", "b", "heap", "a-name-longer-than-thirty-two-characters-xyz", nullptr};
static const VirtualRangeType kTypes[] = {VirtualRangeType::Reserved, VirtualRangeType::PoolReserved, VirtualRangeType::Direct,
                                          VirtualRangeType::Flexible, VirtualRangeType::Pooled,       VirtualRangeType::Stack,
                                          VirtualRangeType::Code,     VirtualRangeType::Runtime,      VirtualRangeType::Reserved,
                                          VirtualRangeType::Flexible, VirtualRangeType::Direct};
static const int kProt[] = {0, 1, 3, 0x13, 0x33, 3};

static bool RunSeed(uint64_t seed, uint64_t nops, Counts& c) {
	std::mt19937_64 g(seed);
	auto            rnd = [&](uint64_t n) { return n == 0 ? 0 : g() % n; };
	const uint64_t  unit   = (seed % 3 == 0) ? 0x1000 : (seed % 3 == 1) ? 0x10000 : 0x80000; // 4K, 64K, 512K pages
	const uint64_t  extent = 512 + rnd(3000);                                                 // address space in units
	const uint64_t  base   = 0x10000000ull + rnd(64) * unit;
	const uint64_t  target = 150 + rnd(600); // ranges the run hovers around
	auto            run    = std::make_unique<Run>(c);
	Run&            R      = *run;

	// the dirty log is off until the first reader: turn it on in all three
	{
		std::vector<Range>                         s1, s2, s3;
		uint64_t                                   g1, g2, g3;
		std::vector<std::pair<uint64_t, uint64_t>> d1, d2, d3;
		bool                                       k1, k2, k3;
		R.vec.SnapshotWithDirty(&s1, &g1, &d1, &k1);
		R.map.SnapshotWithDirty(&s2, &g2, &d2, &k2);
		R.disp.SnapshotWithDirty(&s3, &g3, &d3, &k3);
	}
	std::vector<Range> snap;

	auto addr_in = [&]() -> uint64_t {
		const uint64_t r = rnd(1000);
		if (r < 4) return 0;
		if (r < 12) return UINT64_MAX - rnd(20) * unit; // the top of the address space: saturated ends
		uint64_t a = base + rnd(extent + 4) * unit - 2 * unit;
		if (rnd(10) == 0) a += rnd(unit);
		if (!snap.empty() && rnd(3) == 0) { // a boundary of an existing range
			const Range& x = snap[rnd(snap.size())];
			const uint64_t e = x.size > UINT64_MAX - x.start ? UINT64_MAX : x.start + x.size;
			switch (rnd(4)) {
				case 0: a = x.start; break;
				case 1: a = e; break;
				case 2: a = e - 1; break;
				default: a = x.start + rnd(x.size); break;
			}
		}
		return a;
	};
	auto size_in = [&](uint64_t maxu) -> uint64_t {
		const uint64_t r = rnd(1000);
		if (r < 4) return 0;
		if (r < 10) return UINT64_MAX - rnd(3);
		uint64_t s = (1 + rnd(maxu)) * unit;
		if (rnd(12) == 0) s += rnd(unit) - unit / 2;
		return s;
	};
	// a span covering one existing range, a part of it, or several neighbours
	auto span_of_range = [&](uint64_t* s, uint64_t* z) {
		if (snap.empty()) {
			*s = addr_in();
			*z = size_in(32);
			return;
		}
		const size_t i = rnd(snap.size());
		const Range& x = snap[i];
		switch (rnd(4)) {
			case 0: *s = x.start; *z = x.size; break;
			case 1: {
				const uint64_t u = x.size / unit;
				const uint64_t a = u > 1 ? rnd(u) : 0;
				*s = x.start + a * unit;
				*z = std::max<uint64_t>(unit, (u > a ? rnd(u - a) + 1 : 1) * unit);
				break;
			}
			case 2: {
				const size_t j = std::min(snap.size() - 1, i + rnd(4));
				*s = x.start;
				*z = (snap[j].start - x.start) + snap[j].size;
				break;
			}
			default: *s = x.start + unit * rnd(2); *z = x.size + unit * rnd(3); break;
		}
	};

	for (uint64_t op = 0; op < nops; op++) {
		c.ops++;
		R.vec.Snapshot(&snap);
		const uint64_t pick   = rnd(100);
		const bool     crowd  = snap.size() > target;
		uint64_t       s = 0, z = 0;
		if (pick < (crowd ? 18 : 36)) {
			R.opname = "Add";
			s        = addr_in();
			z        = size_in(rnd(4) == 0 ? 64 : 8);
			if (!snap.empty() && rnd(3) == 0) { // adjacent to an existing range, on either side
				const Range& x = snap[rnd(snap.size())];
				if (rnd(2)) s = x.start + x.size;
				else s = x.start - z;
			}
			const uint64_t         off  = rnd(4) == 0 ? 0 : rnd(1u << 20) * 0x1000;
			const int              prot = kProt[rnd(6)];
			const int              mt   = static_cast<int>(rnd(3));
			const VirtualRangeType t    = kTypes[rnd(std::size(kTypes))];
			const char*            nm   = kNames[rnd(6)];
			const bool             dm   = rnd(10) == 0;
			bool                   r1, r2, r3;
			if (rnd(2)) {
				r1 = R.vec.Add(s, z, off, prot, mt, t, nm, dm);
				r2 = R.map.Add(s, z, off, prot, mt, t, nm, dm);
				r3 = R.disp.Add(s, z, off, prot, mt, t, nm, dm);
			} else { // the default argument
				r1 = R.vec.Add(s, z, off, prot, mt, t, nm);
				r2 = R.map.Add(s, z, off, prot, mt, t, nm);
				r3 = R.disp.Add(s, z, off, prot, mt, t, nm);
			}
			R.eq(r1, r2, r3, "Add result");
		} else if (pick < (crowd ? 48 : 50)) {
			R.opname = "Remove";
			if (rnd(5) < 2) span_of_range(&s, &z);
			else {
				s = addr_in();
				z = size_in(16);
			}
			const bool r1 = R.vec.Remove(s, z), r2 = R.map.Remove(s, z), r3 = R.disp.Remove(s, z);
			R.eq(r1, r2, r3, "Remove result");
		} else if (pick < 58) {
			R.opname = "Rename";
			if (rnd(2)) span_of_range(&s, &z);
			else {
				s = addr_in();
				z = size_in(16);
			}
			const char* nm = kNames[rnd(6)];
			R.vec.Rename(s, z, nm);
			R.map.Rename(s, z, nm);
			R.disp.Rename(s, z, nm);
		} else if (pick < 72) {
			R.opname = "Protect";
			if (rnd(3)) span_of_range(&s, &z);
			else {
				s = addr_in();
				z = size_in(24);
			}
			const int p = kProt[rnd(6)];
			R.vec.Protect(s, z, p);
			R.map.Protect(s, z, p);
			R.disp.Protect(s, z, p);
		} else if (pick < 80) {
			R.opname = "SetMemoryType";
			if (rnd(3)) span_of_range(&s, &z);
			else {
				s = addr_in();
				z = size_in(24);
			}
			const int m = static_cast<int>(rnd(3));
			R.vec.SetMemoryType(s, z, m);
			R.map.SetMemoryType(s, z, m);
			R.disp.SetMemoryType(s, z, m);
		} else if (pick < 85) {
			R.opname = "ReleaseReserved";
			span_of_range(&s, &z);
			if (rnd(4) == 0) s += unit;
			const bool r1 = R.vec.ReleaseReserved(s, z), r2 = R.map.ReleaseReserved(s, z), r3 = R.disp.ReleaseReserved(s, z);
			R.eq(r1, r2, r3, "ReleaseReserved result");
		} else if (pick < 92) {
			R.opname = "ConsumeReserved";
			span_of_range(&s, &z);
			const uint64_t k  = rnd(4);
			bool           r1, r2, r3;
			if (k == 0) {
				r1 = R.vec.ConsumeReserved(s, z);
				r2 = R.map.ConsumeReserved(s, z);
				r3 = R.disp.ConsumeReserved(s, z);
			} else {
				const VirtualRangeType t = k == 1 ? VirtualRangeType::PoolReserved : kTypes[rnd(std::size(kTypes))];
				r1 = R.vec.ConsumeReserved(s, z, t);
				r2 = R.map.ConsumeReserved(s, z, t);
				r3 = R.disp.ConsumeReserved(s, z, t);
			}
			R.eq(r1, r2, r3, "ConsumeReserved result");
		} else {
			R.opname = "ConsumeReservedSpan";
			span_of_range(&s, &z);
			const uint64_t k = rnd(3);
			Range          f1 {}, f2 {}, f3 {};
			bool           r1, r2, r3;
			if (k == 0) {
				r1 = R.vec.ConsumeReservedSpan(s, z);
				r2 = R.map.ConsumeReservedSpan(s, z);
				r3 = R.disp.ConsumeReservedSpan(s, z);
			} else if (k == 1) {
				r1 = R.vec.ConsumeReservedSpan(s, z, &f1);
				r2 = R.map.ConsumeReservedSpan(s, z, &f2);
				r3 = R.disp.ConsumeReservedSpan(s, z, &f3);
			} else {
				const VirtualRangeType t = rnd(2) ? VirtualRangeType::PoolReserved : kTypes[rnd(std::size(kTypes))];
				r1 = R.vec.ConsumeReservedSpan(s, z, &f1, t);
				r2 = R.map.ConsumeReservedSpan(s, z, &f2, t);
				r3 = R.disp.ConsumeReservedSpan(s, z, &f3, t);
			}
			R.eq(r1, r2, r3, "ConsumeReservedSpan result");
			R.eqr(Same(f1, f2) && Same(f1, f3), "ConsumeReservedSpan first_range");
		}

		// ---- the state after the op
		R.eq(R.vec.Generation(), R.map.Generation(), R.disp.Generation(), "Generation");
		std::vector<Range> s1, s2, s3;
		R.vec.Snapshot(&s1);
		R.map.Snapshot(&s2);
		R.disp.Snapshot(&s3);
		R.eqr(Same(s1, s2) && Same(s1, s3), "Snapshot");
		if (!(Same(s1, s2) && Same(s1, s3)) && std::getenv("A1_DEBUG")) {
			std::printf("snapshot sizes %zu %zu %zu; op args s=%llx z=%llx\n", s1.size(), s2.size(), s3.size(), (unsigned long long)s, (unsigned long long)z);
			for (size_t i = 0; i < std::max(s1.size(), s2.size()); i++) {
				auto pr = [](const char* t, const std::vector<Range>& v, size_t i) {
					if (i < v.size()) std::printf(" %s %llx+%llx t%d p%x m%d dm%d o%llx '%s'", t, (unsigned long long)v[i].start, (unsigned long long)v[i].size, (int)v[i].type, v[i].protection, v[i].memory_type, (int)v[i].disallow_merge, (unsigned long long)v[i].offset, v[i].name);
				};
				if (i < s1.size() && i < s2.size() && Same(s1[i], s2[i])) continue;
				pr("vec", s1, i); pr("map", s2, i); std::printf("\n");
			}
		}
		R.map.Snapshot(&s2); // again with no edit: the cached copy
		R.eqr(Same(s1, s2), "Snapshot (cached)");
		R.eq(R.vec.CountPageTableEntries(true), R.map.CountPageTableEntries(true), R.disp.CountPageTableEntries(true), "CountPageTableEntries(gpu)");
		R.eq(R.vec.CountPageTableEntries(false), R.map.CountPageTableEntries(false), R.disp.CountPageTableEntries(false), "CountPageTableEntries(cpu)");
		if (op % 64 == 63) {
			uint64_t                                   g1, g2, g3;
			std::vector<std::pair<uint64_t, uint64_t>> d1, d2, d3;
			bool                                       k1, k2, k3;
			R.vec.SnapshotWithDirty(&s1, &g1, &d1, &k1);
			R.map.SnapshotWithDirty(&s2, &g2, &d2, &k2);
			R.disp.SnapshotWithDirty(&s3, &g3, &d3, &k3);
			R.eqr(Same(s1, s2) && Same(s1, s3) && g1 == g2 && g1 == g3 && d1 == d2 && d1 == d3 && k1 == k2 && k1 == k3, "SnapshotWithDirty");
		} else {
			uint64_t                                   g1, g2, g3;
			std::vector<std::pair<uint64_t, uint64_t>> d1, d2, d3;
			std::vector<std::vector<Range>>            t1, t2, t3;
			bool                                       k1, k2, k3;
			R.vec.DirtyWithTouching(&g1, &d1, &t1, &k1);
			R.map.DirtyWithTouching(&g2, &d2, &t2, &k2);
			R.disp.DirtyWithTouching(&g3, &d3, &t3, &k3);
			bool ok = g1 == g2 && g1 == g3 && d1 == d2 && d1 == d3 && k1 == k2 && k1 == k3 && t1.size() == t2.size() && t1.size() == t3.size();
			for (size_t i = 0; ok && i < t1.size(); i++) ok = Same(t1[i], t2[i]) && Same(t1[i], t3[i]);
			R.eqr(ok, "DirtyWithTouching");
		}
		snap = s1;
		for (int p = 0; p < 6; p++) {
			const uint64_t a = addr_in();
			for (int fl = 0; fl < 3; fl++) {
				Range      q1 {}, q2 {}, q3 {};
				const bool r1 = R.vec.Query(a, fl, &q1), r2 = R.map.Query(a, fl, &q2), r3 = R.disp.Query(a, fl, &q3);
				R.eqr(r1 == r2 && r1 == r3 && Same(q1, q2) && Same(q1, q3), "Query");
			}
			uint64_t qs, qz;
			if (rnd(2)) span_of_range(&qs, &qz);
			else {
				qs = a;
				qz = size_in(40);
			}
			{
				Range      q1 {}, q2 {}, q3 {};
				const bool r1 = R.vec.QueryOverlap(qs, qz, &q1), r2 = R.map.QueryOverlap(qs, qz, &q2), r3 = R.disp.QueryOverlap(qs, qz, &q3);
				R.eqr(r1 == r2 && r1 == r3 && Same(q1, q2) && Same(q1, q3), "QueryOverlap");
			}
			R.eq(R.vec.HasOverlap(qs, qz), R.map.HasOverlap(qs, qz), R.disp.HasOverlap(qs, qz), "HasOverlap");
			{
				std::vector<Range> v1, v2, v3;
				const bool         r1 = R.vec.QuerySpan(qs, qz, &v1), r2 = R.map.QuerySpan(qs, qz, &v2), r3 = R.disp.QuerySpan(qs, qz, &v3);
				R.eqr(r1 == r2 && r1 == r3 && Same(v1, v2) && Same(v1, v3), "QuerySpan");
			}
			R.eq(R.vec.ClampRangeSize(qs, qz), R.map.ClampRangeSize(qs, qz), R.disp.ClampRangeSize(qs, qz), "ClampRangeSize");
			{
				std::vector<std::pair<uint64_t, uint64_t>> o1, o2, o3;
				const uint64_t                             hi = qz > UINT64_MAX - qs ? UINT64_MAX : qs + qz;
				R.vec.Overlapping(qs, hi, &o1);
				R.map.Overlapping(qs, hi, &o2);
				R.disp.Overlapping(qs, hi, &o3);
				R.eqr(o1 == o2 && o1 == o3, "Overlapping");
			}
		}
		if (R.bad) return false;
	}
	return true;
}

static void Bench() {
	constexpr uint64_t kBase = 0x100000000ull, kUnit = 0x4000, kN = 29000;
	auto               time = [](auto&& f) {
		const auto t0 = std::chrono::steady_clock::now();
		f();
		return std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
	};
	auto bench = [&](auto& v, const char* label) {
		std::mt19937_64 g(7);
		const double    t_add = time([&] {
            for (uint64_t i = 0; i < kN; i++) v.Add(kBase + i * 17 * kUnit, 16 * kUnit, 0, 3, 0, VirtualRangeType::Flexible, "f");
        });
		const double    t_edit = time([&] {
            for (int i = 0; i < 20000; i++) {
                const uint64_t r = kBase + (g() % kN) * 17 * kUnit;
                v.Protect(r + 4 * kUnit, 4 * kUnit, 1); // split into three
                v.Protect(r + 4 * kUnit, 4 * kUnit, 3); // and merge back
                v.Add(r + 16 * kUnit, kUnit, 0, 1, 0, VirtualRangeType::Direct, "d");
                v.Remove(r + 16 * kUnit, kUnit);
            }
        });
		std::vector<Range> out;
		const double       t_snap = time([&] {
            for (int i = 0; i < 200; i++) v.Snapshot(&out);
        });
		std::printf("bench %-4s: %zu ranges; add %.1f ms, 80000 edits %.1f ms, 200 snapshots %.1f ms\n", label, out.size(), t_add,
		            t_edit, t_snap);
	};
	auto vec = std::make_unique<VirtualRangesVec>();
	auto map = std::make_unique<VirtualRangesMap>();
	bench(*vec, "vec");
	bench(*map, "map");
}

int main(int argc, char** argv) {
	if (argc > 1 && std::string(argv[1]) == "--bench") {
		Bench();
		return 0;
	}
	const uint64_t nops  = argc > 1 ? std::strtoull(argv[1], nullptr, 10) : 25000;
	const uint64_t seeds = argc > 2 ? std::strtoull(argv[2], nullptr, 10) : 12;
	std::printf("dispatcher mode: %s\n", VirtualRanges::A1On() ? "map" : "vec");
	Counts   c;
	uint64_t seeds_failed = 0;
	for (uint64_t s = 1; s <= seeds; s++) {
		if (!RunSeed(s, nops, c)) seeds_failed++;
	}
	std::printf("ops %llu, checks PASS %llu FAIL %llu, seeds %llu/%llu clean\n", (unsigned long long)c.ops,
	            (unsigned long long)c.pass, (unsigned long long)c.fail, (unsigned long long)(seeds - seeds_failed),
	            (unsigned long long)seeds);
	if (!c.first.empty()) std::printf("first FAIL: %s\n", c.first.c_str());
	std::printf("%s\n", c.fail == 0 ? "PASS" : "FAIL");
	return c.fail == 0 ? 0 : 1;
}
