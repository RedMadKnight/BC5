// SPDX-License-Identifier: GPL-2.0-only
// BC5 exp 0438 A1b (tag a1b438): differential test of A1b's readers against today's. The code under test is the real
// text of the generated memory.cpp (mka1b.py --extract): the range classes (a1b_real.h) and the reader functions
// (a1b_readers.inc, namespace a1b, on the VirtualRanges dispatcher in whichever mode KYTY_BC5_0438_A1 selects).
// Today's readers are the text of A1's output (today_readers.inc, namespace today, on VirtualRangesVec). Every op
// goes to today's table, A1b's dispatcher and two reference tables for the cursor readers; after every op:
//   the results, Generation, the chunks against today's Snapshot (with their invariants), Bc5ForEachMappedRange
//   (cb / cb2 / both), Bc5ForEachPrivateRegion on random regions, Bc5RangesWithDirty or Bc5RangesDirtyTouching,
//   Bc5GuestRangesIn; and on two schedules Bc5RangesTouchingSince(since) against today's Bc5RangesDirtyTouching on a
//   reference table whose log was emptied at `since` (cursor A every 1-40 ops; cursor B every RING/2 - 5 RING/2 ops,
//   so it falls out of the ring: then *complete must be false and the full path must equal today's).
// With a journal directory every seed's dispatcher writes KYTY_BC5_0438_A1J's file; after the seed the file must hold
// exactly the issued calls with their results, and replaying it must give the same results and the same table.
//   test_a1b438 [ops_per_seed] [seeds] [journal_dir]
//   test_a1b438 --replay FILE      drives today's and A1b's code with a journal file, checking as above
//   test_a1b438 --bench            29,000 ranges: an edit plus a full reader, today / A1's snapshot / A1b's chunks
#include "a1b_real.h"

#include <chrono>
#include <cstddef>
#include <random>
#include <unordered_set>

namespace Libs::LibKernel::Memory {
namespace today {
using VirtualRanges = VirtualRangesVec;
struct GuestBackingStore {
	static int Bc5Fd() { return -1; }
};
struct GuestAddressSpace {
	std::vector<std::pair<uint64_t, uint64_t>> regions;
	static int Bc5PrivateFd() { return -1; }
	void Bc5SnapshotPrivate(std::vector<std::pair<uint64_t, uint64_t>>* out) const { *out = regions; }
};
static std::unique_ptr<VirtualRanges> g_virtual_ranges;
#include "today_readers.inc"
static std::unique_ptr<GuestAddressSpace> g_space;
static std::unique_ptr<GuestAddressSpace>& Bc5GuestAddressSpace() { return g_space; }
} // namespace today
namespace a1b {
struct GuestBackingStore {
	static int Bc5Fd() { return -1; }
};
struct GuestAddressSpace {
	std::vector<std::pair<uint64_t, uint64_t>> regions;
	static int Bc5PrivateFd() { return -1; }
	void Bc5SnapshotPrivate(std::vector<std::pair<uint64_t, uint64_t>>* out) const { *out = regions; }
};
static std::unique_ptr<VirtualRanges> g_virtual_ranges; // the dispatcher
#include "a1b_readers.inc"
static std::unique_ptr<GuestAddressSpace> g_space;
static std::unique_ptr<GuestAddressSpace>& Bc5GuestAddressSpace() { return g_space; }
} // namespace a1b
} // namespace Libs::LibKernel::Memory

using namespace Libs::LibKernel::Memory;
using Range = VirtualRangesVec::Range;
using Spans = std::vector<std::pair<uint64_t, uint64_t>>;

constexpr uint64_t kRing  = KYTY_BC5_0438_A1B_RING;
constexpr size_t   kChunk = KYTY_BC5_0438_A1B_CHUNK;

// The journal record, declared here as well so that the lean build (no VirtualRangesJournal) still compiles.
struct TRec {
	uint8_t  op, type, flags, result;
	int32_t  protection, memory_type;
	uint32_t reserved;
	uint64_t start, size, offset;
	char     name[32];
};
static_assert(sizeof(TRec) == 72, "record");
enum : uint8_t { kAdd = 1, kRemove, kReleaseReserved, kConsumeReserved, kConsumeReservedSpan, kRename, kProtect, kSetMemoryType };
#if !defined(BC5_LEAN)
using JRec = VirtualRangesJournal::Rec;
static_assert(sizeof(JRec) == sizeof(TRec) && offsetof(JRec, protection) == offsetof(TRec, protection) &&
                  offsetof(JRec, start) == offsetof(TRec, start) && offsetof(JRec, name) == offsetof(TRec, name),
              "the test's record is the journal's");
static_assert(int {VirtualRangesJournal::kAdd} == int {kAdd} && int {VirtualRangesJournal::kSetMemoryType} == int {kSetMemoryType} &&
                  int {VirtualRangesJournal::kConsumeReservedSpan} == int {kConsumeReservedSpan},
              "op codes");
#endif
static const char* const kOpName[] = {"?", "Add", "Remove", "ReleaseReserved", "ConsumeReserved", "ConsumeReservedSpan", "Rename", "Protect", "SetMemoryType"};

static bool Same(const Range& a, const Range& b) {
	return a.start == b.start && a.size == b.size && a.offset == b.offset && a.protection == b.protection &&
	       a.memory_type == b.memory_type && a.type == b.type && a.disallow_merge == b.disallow_merge &&
	       std::memcmp(a.name, b.name, KERNEL_MAXIMUM_NAME_LENGTH) == 0;
}

// one callback of a reader
struct Ev {
	int         kind;
	size_t      index;
	uint64_t    start, size, offset;
	int         type, prot;
	std::string name;
	bool        operator==(const Ev&) const = default;
};
using Evs = std::vector<Ev>;
static void CbA(uint64_t s, uint64_t z, int t, int p, const char* n, void* c) { static_cast<Evs*>(c)->push_back({1, 0, s, z, 0, t, p, n}); }
static void CbB(uint64_t s, uint64_t z, uint64_t o, int t, int p, const char* n, void* c) { static_cast<Evs*>(c)->push_back({2, 0, s, z, o, t, p, n}); }
static void CbT(size_t i, uint64_t s, uint64_t z, uint64_t o, int t, int p, const char* n, void* c) {
	static_cast<Evs*>(c)->push_back({3, i, s, z, o, t, p, n});
}
static void CbP(uint64_t s, uint64_t z, int t, const char* n, void* c) { static_cast<Evs*>(c)->push_back({4, 0, s, z, 0, t, 0, n}); }

// a record applied to a table: the result as the journal stores it (0/1, 2 for void)
template <class T>
static int Apply(T& v, const TRec& r, Range* first) {
	const char* nm = (r.flags & 2) != 0 ? nullptr : r.name;
	const auto  t  = static_cast<VirtualRangeType>(r.type);
	switch (r.op) {
		case kAdd: return v.Add(r.start, r.size, r.offset, r.protection, r.memory_type, t, nm, (r.flags & 1) != 0) ? 1 : 0;
		case kRemove: return v.Remove(r.start, r.size) ? 1 : 0;
		case kReleaseReserved: return v.ReleaseReserved(r.start, r.size) ? 1 : 0;
		case kConsumeReserved: return v.ConsumeReserved(r.start, r.size, t) ? 1 : 0;
		case kConsumeReservedSpan: return v.ConsumeReservedSpan(r.start, r.size, (r.flags & 4) != 0 ? first : nullptr, t) ? 1 : 0;
		case kRename: v.Rename(r.start, r.size, nm); return 2;
		case kProtect: v.Protect(r.start, r.size, r.protection); return 2;
		case kSetMemoryType: v.SetMemoryType(r.start, r.size, r.memory_type); return 2;
		default: std::fprintf(stderr, "bad op %d\n", r.op); std::abort();
	}
}

struct Counts {
	uint64_t    pass = 0, fail = 0, ops = 0;
	uint64_t    cur_complete = 0, cur_fallback = 0, journal_recs = 0, replay_ops = 0, chunks_seen = 0, chunks_rebuilt = 0, max_chunks = 0;
	std::string first;
};

template <class F>
static auto WithToday(std::unique_ptr<VirtualRangesVec>& v, F f) {
	std::swap(today::g_virtual_ranges, v);
	auto r = f();
	std::swap(today::g_virtual_ranges, v);
	return r;
}

struct Harness {
	Counts&                           c;
	std::mt19937_64                   g;
	std::unique_ptr<VirtualRangesVec> refA, refB;
	uint64_t                          sinceA = 0, sinceB = 0, nextA = 0, nextB = 0, op = 0;
	bool                              bad    = false;
	std::string                       opname;
	std::vector<Range>                snap; // today's table after the last op
	std::unordered_set<const void*>   prev_chunks;
	const bool                        a1;

	uint64_t rnd(uint64_t n) { return n == 0 ? 0 : g() % n; }

	Harness(Counts& counts, uint64_t seed, const char* journal): c(counts), g(seed * 7919 + 13), a1(VirtualRanges::A1On()) {
		today::g_virtual_ranges = std::make_unique<VirtualRangesVec>();
		a1b::g_virtual_ranges   = std::make_unique<VirtualRanges>(journal);
		today::g_space          = std::make_unique<today::GuestAddressSpace>();
		a1b::g_space            = std::make_unique<a1b::GuestAddressSpace>();
		refA                    = std::make_unique<VirtualRangesVec>();
		refB                    = std::make_unique<VirtualRangesVec>();
		opname                  = "start";
		DirtyReaders(true); // the first call of each turns its log on
		DirtyReaders(false);
		for (auto* ref: {&refA, &refB}) {
			Evs   e;
			uint64_t gg;
			Spans s;
			bool  k;
			WithToday(*ref, [&] { return today::Bc5RangesDirtyTouching(CbT, &e, &gg, &s, &k); });
		}
		sinceA = sinceB = a1b::Bc5MappedRangesGeneration();
		nextA           = 1 + rnd(40);
		nextB           = kRing / 2 + rnd(2 * kRing);
	}

	void Check(bool ok, const char* what) {
		if (ok) {
			c.pass++;
			return;
		}
		c.fail++;
		if (!bad && c.first.empty()) c.first = "op " + std::to_string(c.ops) + " (" + opname + "): " + what;
		bad = true;
	}

	void DirtyReaders(bool with_dirty) {
		Evs      e1, e2;
		uint64_t g1 = 0, g2 = 0;
		Spans    s1, s2;
		bool     k1 = false, k2 = false;
		bool     r1, r2;
		if (with_dirty) {
			r1 = today::Bc5RangesWithDirty(CbB, &e1, &g1, &s1, &k1);
			r2 = a1b::Bc5RangesWithDirty(CbB, &e2, &g2, &s2, &k2);
		} else {
			r1 = today::Bc5RangesDirtyTouching(CbT, &e1, &g1, &s1, &k1);
			r2 = a1b::Bc5RangesDirtyTouching(CbT, &e2, &g2, &s2, &k2);
		}
		Check(r1 == r2 && g1 == g2 && s1 == s2 && k1 == k2 && e1 == e2, with_dirty ? "Bc5RangesWithDirty" : "Bc5RangesDirtyTouching");
	}

	void Cursor(std::unique_ptr<VirtualRangesVec>& ref, uint64_t* since) {
		Evs        en, er;
		uint64_t   gn = 0, gr = 0;
		Spans      sn, sr;
		bool       cn = false, cr = false;
		const bool okn = a1b::Bc5RangesTouchingSince(*since, CbT, &en, &gn, &sn, &cn);
		const bool okr = WithToday(ref, [&] { return today::Bc5RangesDirtyTouching(CbT, &er, &gr, &sr, &cr); });
		Check(okn && okr && gn == gr, "TouchingSince generation");
		Check(cn == (a1 && gn - *since <= kRing), "TouchingSince complete exactly while the ring holds `since`");
		Check(cr, "today's log complete (reference)");
		if (cn) {
			c.cur_complete++;
			Check(sn == sr && en == er, "TouchingSince spans and touching ranges");
		} else {
			c.cur_fallback++;
			Check(sn.empty() && en.empty(), "TouchingSince fallback gives nothing");
			Evs f1, f2; // the full path the reader takes then
			today::Bc5ForEachMappedRange(nullptr, &f1, CbB);
			a1b::Bc5ForEachMappedRange(nullptr, &f2, CbB);
			Check(f1 == f2, "TouchingSince fallback: full path");
		}
		*since = gn;
	}

	void CheckState() {
		const uint64_t gt = today::Bc5MappedRangesGeneration();
		Check(gt == a1b::Bc5MappedRangesGeneration() && gt == refA->Generation() && gt == refB->Generation(), "Generation");
		today::g_virtual_ranges->Snapshot(&snap);
		if (a1) {
			const auto t  = a1b::g_virtual_ranges->Chunks();
			bool       ok = t->total == snap.size();
			size_t     i  = 0;
			std::unordered_set<const void*> now;
			for (size_t k = 0; k < t->chunks.size(); k++) {
				const auto& ch = *t->chunks[k];
				now.insert(t->chunks[k].get());
				if (prev_chunks.count(t->chunks[k].get()) == 0) c.chunks_rebuilt++;
				ok = ok && !ch.empty();
				if (ok && k > 0) ok = t->chunks[k - 1]->back().start < ch.front().start; // a boundary between two starts
				if (ok && ch.size() > kChunk) ok = ch[kChunk - 1].start == ch.back().start; // only a run of equal starts
				for (const auto& r: ch) {
					ok = ok && i < snap.size() && Same(r, snap[i]);
					i++;
				}
			}
			ok = ok && i == snap.size();
			c.chunks_seen += t->chunks.size();
			c.max_chunks = std::max<uint64_t>(c.max_chunks, t->chunks.size());
			prev_chunks.swap(now);
			Check(ok, "chunks equal today's Snapshot, invariants hold");
		}
		{
			Evs        e1, e2;
			const auto v = op % 3;
			today::Bc5ForEachMappedRange(v == 2 ? nullptr : CbA, &e1, v == 1 ? nullptr : CbB);
			a1b::Bc5ForEachMappedRange(v == 2 ? nullptr : CbA, &e2, v == 1 ? nullptr : CbB);
			Check(e1 == e2, "Bc5ForEachMappedRange");
		}
		{
			Spans regions;
			const uint64_t k = rnd(9);
			for (uint64_t j = 0; j < k; j++) {
				uint64_t s = 0x10000000ull + rnd(1ull << 34);
				if (!snap.empty() && rnd(4) != 0) {
					const Range& x = snap[rnd(snap.size())];
					switch (rnd(4)) {
						case 0: s = x.start; break;
						case 1: s = x.start + x.size; break;
						case 2: s = x.start + x.size - 1; break;
						default: s = x.start + rnd(x.size); break;
					}
				}
				regions.emplace_back(s, 0x1000 * (1 + rnd(64)));
			}
			std::sort(regions.begin(), regions.end());
			today::g_space->regions = regions;
			a1b::g_space->regions   = regions;
			Evs e1, e2;
			today::Bc5ForEachPrivateRegion(&e1, CbP);
			a1b::Bc5ForEachPrivateRegion(&e2, CbP);
			Check(e1 == e2, "Bc5ForEachPrivateRegion");
		}
		DirtyReaders(op % 2 == 0);
		{
			const uint64_t lo = snap.empty() ? 0 : snap[rnd(snap.size())].start - rnd(2) * 0x1000;
			const uint64_t hi = lo + 0x1000 * (1 + rnd(256));
			Spans          o1, o2;
			today::Bc5GuestRangesIn(lo, hi, &o1);
			a1b::Bc5GuestRangesIn(lo, hi, &o2);
			Check(o1 == o2, "Bc5GuestRangesIn");
		}
		if (op >= nextA) {
			Cursor(refA, &sinceA);
			nextA = op + 1 + rnd(40);
		}
		if (op >= nextB) {
			Cursor(refB, &sinceB);
			nextB = op + kRing / 2 + rnd(2 * kRing);
		}
	}

	int Step(const TRec& r) {
		c.ops++;
		op++;
		opname = kOpName[r.op <= kSetMemoryType ? r.op : 0];
		Range     f1 {}, f2 {}, f3 {}, f4 {};
		const int r1 = Apply(*today::g_virtual_ranges, r, &f1);
		const int r2 = Apply(*a1b::g_virtual_ranges, r, &f2);
		const int r3 = Apply(*refA, r, &f3);
		const int r4 = Apply(*refB, r, &f4);
		Check(r1 == r2 && r1 == r3 && r1 == r4, "result");
		Check(Same(f1, f2) && Same(f1, f3) && Same(f1, f4), "first_range");
		CheckState();
		return r1;
	}
};

static const char* kNames[] = {"", "a", "b", "heap", "a-name-longer-than-thirty-two-characters-xyz", nullptr};
static const VirtualRangeType kTypes[] = {VirtualRangeType::Reserved, VirtualRangeType::PoolReserved, VirtualRangeType::Direct,
                                          VirtualRangeType::Flexible, VirtualRangeType::Pooled,       VirtualRangeType::Stack,
                                          VirtualRangeType::Code,     VirtualRangeType::Runtime,      VirtualRangeType::Reserved,
                                          VirtualRangeType::Flexible, VirtualRangeType::Direct};
static const int kProt[] = {0, 1, 3, 0x13, 0x33, 3};

static void SetName(TRec* r, const char* nm) {
	if (nm == nullptr) r->flags |= 2;
	else std::strncpy(r->name, nm, sizeof(r->name) - 1);
}

static std::vector<TRec> ReadJournal(const std::string& path, bool* ok) {
	std::vector<TRec> out;
	*ok     = false;
	FILE* f = std::fopen(path.c_str(), "rb");
	if (f == nullptr) return out;
	char     magic[8];
	uint32_t h[2];
	if (std::fread(magic, 1, 8, f) == 8 && std::memcmp(magic, "BC5A1J01", 8) == 0 && std::fread(h, sizeof(h), 1, f) == 1 && h[0] == sizeof(TRec) && h[1] == 0) {
		TRec r;
		while (std::fread(&r, sizeof(r), 1, f) == 1) out.push_back(r);
		*ok = std::feof(f) != 0;
	}
	std::fclose(f);
	return out;
}

// drive a fresh pair with a journal's records; the results must be the recorded ones
static bool Replay(const std::vector<TRec>& recs, Counts& c, uint64_t seed, std::vector<Range>* final_table) {
	auto h = std::make_unique<Harness>(c, seed, nullptr);
	for (const TRec& r: recs) {
		const int res = h->Step(r);
		c.replay_ops++;
		h->Check(res == r.result, "replayed result equals the recorded one");
		if (h->bad) return false;
	}
	if (final_table != nullptr) today::g_virtual_ranges->Snapshot(final_table);
	return !h->bad;
}

static bool RunSeed(uint64_t seed, uint64_t nops, Counts& c, const char* journal_dir) {
	std::mt19937_64 g(seed);
	auto            rnd    = [&](uint64_t n) { return n == 0 ? 0 : g() % n; };
	const uint64_t  unit   = (seed % 3 == 0) ? 0x1000 : (seed % 3 == 1) ? 0x10000 : 0x80000;
	const uint64_t  extent = 512 + rnd(3000);
	const uint64_t  base   = 0x10000000ull + rnd(64) * unit;
	const uint64_t  target = 150 + rnd(600);
	std::string     jpath;
	if (journal_dir != nullptr) {
		jpath = std::string(journal_dir) + "/seed" + std::to_string(seed) + ".a1j";
		std::remove(jpath.c_str());
	}
	auto     hp = std::make_unique<Harness>(c, seed, journal_dir != nullptr ? jpath.c_str() : nullptr);
	Harness& H  = *hp;
	std::vector<TRec> issued;
	const auto&       snap = H.snap;

	auto addr_in = [&]() -> uint64_t {
		const uint64_t r = rnd(1000);
		if (r < 4) return 0;
		if (r < 12) return UINT64_MAX - rnd(20) * unit;
		uint64_t a = base + rnd(extent + 4) * unit - 2 * unit;
		if (rnd(10) == 0) a += rnd(unit);
		if (!snap.empty() && rnd(3) == 0) {
			const Range&   x = snap[rnd(snap.size())];
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
				*s               = x.start + a * unit;
				*z               = std::max<uint64_t>(unit, (u > a ? rnd(u - a) + 1 : 1) * unit);
				break;
			}
			case 2: {
				const size_t j = std::min(snap.size() - 1, i + rnd(4));
				*s             = x.start;
				*z             = (snap[j].start - x.start) + snap[j].size;
				break;
			}
			default: *s = x.start + unit * rnd(2); *z = x.size + unit * rnd(3); break;
		}
	};
	auto any_span = [&](uint64_t* s, uint64_t* z, int one_in, uint64_t maxu) {
		if (rnd(one_in) != 0) span_of_range(s, z);
		else {
			*s = addr_in();
			*z = size_in(maxu);
		}
	};

	today::g_virtual_ranges->Snapshot(&H.snap);
	for (uint64_t op = 0; op < nops; op++) {
		const uint64_t pick  = rnd(100);
		const bool     crowd = snap.size() > target;
		TRec           r {};
		if (pick < (crowd ? 18 : 36)) {
			r.op   = kAdd;
			r.start = addr_in();
			r.size  = size_in(rnd(4) == 0 ? 64 : 8);
			if (!snap.empty() && rnd(3) == 0) {
				const Range& x = snap[rnd(snap.size())];
				r.start        = rnd(2) ? x.start + x.size : x.start - r.size;
			}
			r.offset      = rnd(4) == 0 ? 0 : rnd(1u << 20) * 0x1000;
			r.protection  = kProt[rnd(6)];
			r.memory_type = static_cast<int>(rnd(3));
			r.type        = static_cast<uint8_t>(kTypes[rnd(std::size(kTypes))]);
			SetName(&r, kNames[rnd(6)]);
			if (rnd(10) == 0) r.flags |= 1;
		} else if (pick < (crowd ? 48 : 50)) {
			r.op = kRemove;
			if (rnd(5) < 2) span_of_range(&r.start, &r.size);
			else {
				r.start = addr_in();
				r.size  = size_in(16);
			}
		} else if (pick < 58) {
			r.op = kRename;
			any_span(&r.start, &r.size, 2, 16);
			SetName(&r, kNames[rnd(6)]);
		} else if (pick < 72) {
			r.op = kProtect;
			any_span(&r.start, &r.size, 3, 24);
			r.protection = kProt[rnd(6)];
		} else if (pick < 80) {
			r.op = kSetMemoryType;
			any_span(&r.start, &r.size, 3, 24);
			r.memory_type = static_cast<int>(rnd(3));
		} else if (pick < 85) {
			r.op = kReleaseReserved;
			span_of_range(&r.start, &r.size);
			if (rnd(4) == 0) r.start += unit;
		} else if (pick < 92) {
			r.op = kConsumeReserved;
			span_of_range(&r.start, &r.size);
			const uint64_t k = rnd(4);
			r.type           = static_cast<uint8_t>(k == 0 ? VirtualRangeType::Reserved : k == 1 ? VirtualRangeType::PoolReserved : kTypes[rnd(std::size(kTypes))]);
		} else {
			r.op = kConsumeReservedSpan;
			span_of_range(&r.start, &r.size);
			const uint64_t k = rnd(3);
			if (k != 0) r.flags |= 4;
			r.type = static_cast<uint8_t>(k == 2 ? (rnd(2) ? VirtualRangeType::PoolReserved : kTypes[rnd(std::size(kTypes))]) : VirtualRangeType::Reserved);
		}
		r.result = static_cast<uint8_t>(H.Step(r));
		issued.push_back(r);
		if (H.bad) return false;
	}
	if (journal_dir == nullptr) return true;

	// ---- the journal of this seed: closed with the dispatcher, then read back and replayed
	std::vector<Range> final_table = H.snap;
	a1b::g_virtual_ranges.reset();
#if defined(BC5_LEAN)
	const bool want = false; // compiled out
#else
	const bool want = H.a1; // only with the map
#endif
	bool       ok   = false;
	const auto recs = ReadJournal(jpath, &ok);
	if (!want) {
		H.Check(!ok && recs.empty(), "no journal file without KYTY_BC5_0438_A1=1 or in the lean build");
		return !H.bad;
	}
	H.Check(ok, "journal file readable");
	H.Check(recs.size() == issued.size(), "journal holds one record per call");
	bool same = ok && recs.size() == issued.size();
	for (size_t i = 0; same && i < recs.size(); i++) same = std::memcmp(&recs[i], &issued[i], sizeof(TRec)) == 0;
	H.Check(same, "journal records equal the issued calls and results, byte for byte");
	c.journal_recs += recs.size();
	if (H.bad) return false;
	hp.reset();
	std::vector<Range> replayed;
	if (!Replay(recs, c, seed + 1000, &replayed)) return false;
	bool eq = replayed.size() == final_table.size();
	for (size_t i = 0; eq && i < replayed.size(); i++) eq = Same(replayed[i], final_table[i]);
	if (eq) c.pass++;
	else {
		c.fail++;
		if (c.first.empty()) c.first = "seed " + std::to_string(seed) + ": replayed table differs from the run's";
	}
	return eq;
}

static void Bench() {
	constexpr uint64_t kBase = 0x100000000ull, kUnit = 0x4000, kN = 29000;
	constexpr int      kRounds = 2000;
	auto               time    = [](auto&& f) {
		const auto t0 = std::chrono::steady_clock::now();
		f();
		return std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
	};
	if (!VirtualRanges::A1On()) {
		std::printf("bench needs KYTY_BC5_0438_A1=1\n");
		return;
	}
	today::g_virtual_ranges = std::make_unique<VirtualRangesVec>();
	a1b::g_virtual_ranges   = std::make_unique<VirtualRanges>(nullptr);
	auto map                = std::make_unique<VirtualRangesMap>();
	for (uint64_t i = 0; i < kN; i++) {
		today::g_virtual_ranges->Add(kBase + i * 17 * kUnit, 16 * kUnit, 0, 3, 0, VirtualRangeType::Direct, "f");
		a1b::g_virtual_ranges->Add(kBase + i * 17 * kUnit, 16 * kUnit, 0, 3, 0, VirtualRangeType::Direct, "f");
		map->Add(kBase + i * 17 * kUnit, 16 * kUnit, 0, 3, 0, VirtualRangeType::Direct, "f");
	}
	uint64_t sink = 0;
	auto     cb   = [](uint64_t s, uint64_t, uint64_t, int, int, const char*, void* c) { *static_cast<uint64_t*>(c) += s; };
	auto     edit = [&](auto& v, int i) {
		const uint64_t r = kBase + ((static_cast<uint64_t>(i) * 7919) % kN) * 17 * kUnit;
		v.Protect(r + 4 * kUnit, 4 * kUnit, (i & 1) ? 3 : 1);
	};
	const double e_vec = time([&] { for (int i = 0; i < kRounds; i++) edit(*today::g_virtual_ranges, i); });
	const double e_map = time([&] { for (int i = 0; i < kRounds; i++) edit(*map, i); });
	const double e_a1b = time([&] { for (int i = 0; i < kRounds; i++) edit(*a1b::g_virtual_ranges, i); });
	const double f_vec = time([&] {
		for (int i = 0; i < kRounds; i++) {
			edit(*today::g_virtual_ranges, i);
			today::Bc5ForEachMappedRange(nullptr, &sink, cb);
		}
	});
	const double f_map = time([&] { // A1's reader: Snapshot (the sorted copy rebuilt for the generation, then copied) and the walk
		std::vector<Range> v;
		for (int i = 0; i < kRounds; i++) {
			edit(*map, i);
			map->Snapshot(&v);
			for (const auto& r: v) cb(r.start, r.size, r.offset, 0, r.protection, r.name, &sink);
		}
	});
	const double f_a1b = time([&] {
		for (int i = 0; i < kRounds; i++) {
			edit(*a1b::g_virtual_ranges, i);
			a1b::Bc5ForEachMappedRange(nullptr, &sink, cb);
		}
	});
	const double c_a1b = time([&] { // the chunk upkeep alone: an edit and taking the chunk pointer
		for (int i = 0; i < kRounds; i++) {
			edit(*a1b::g_virtual_ranges, i);
			sink += a1b::g_virtual_ranges->Chunks()->total;
		}
	});
	std::printf("bench: %llu ranges, %d rounds of one Protect edit (+ reader)\n", (unsigned long long)kN, kRounds);
	std::printf("  edits only          : vec %.1f ms, map %.1f ms, a1b %.1f ms\n", e_vec, e_map, e_a1b);
	std::printf("  edit + ForEachMapped: today(vec) %.1f ms, A1 map Snapshot %.1f ms, A1b chunks %.1f ms\n", f_vec, f_map, f_a1b);
	std::printf("  edit + Chunks() only: A1b %.1f ms (sink %llu)\n", c_a1b, (unsigned long long)(sink & 1));
}

int main(int argc, char** argv) {
	if (argc > 1 && std::string(argv[1]) == "--bench") {
		Bench();
		return 0;
	}
	Counts c;
	if (argc > 2 && std::string(argv[1]) == "--replay") {
		bool       ok   = false;
		const auto recs = ReadJournal(argv[2], &ok);
		std::printf("replay %s: %zu records%s\n", argv[2], recs.size(), ok ? "" : " (file not readable)");
		const bool good = ok && Replay(recs, c, 99, nullptr);
		std::printf("replay ops %llu, checks PASS %llu FAIL %llu\n", (unsigned long long)c.replay_ops, (unsigned long long)c.pass,
		            (unsigned long long)c.fail);
		if (!c.first.empty()) std::printf("first FAIL: %s\n", c.first.c_str());
		std::printf("%s\n", good && c.fail == 0 ? "PASS" : "FAIL");
		return good && c.fail == 0 ? 0 : 1;
	}
	const uint64_t nops  = argc > 1 ? std::strtoull(argv[1], nullptr, 10) : 25000;
	const uint64_t seeds = argc > 2 ? std::strtoull(argv[2], nullptr, 10) : 12;
	const char*    jdir  = argc > 3 ? argv[3] : nullptr;
#if defined(BC5_LEAN)
	const char* lean = "lean";
#else
	const char* lean = "normal";
#endif
	std::printf("dispatcher mode: %s, %s build, chunk %zu, ring %llu, journal %s\n", VirtualRanges::A1On() ? "map" : "vec", lean, kChunk,
	            (unsigned long long)kRing, jdir != nullptr ? jdir : "off");
	uint64_t seeds_failed = 0;
	for (uint64_t s = 1; s <= seeds; s++) {
		if (!RunSeed(s, nops, c, jdir)) seeds_failed++;
	}
	std::printf("ops %llu (replayed %llu), checks PASS %llu FAIL %llu, seeds %llu/%llu clean\n", (unsigned long long)c.ops,
	            (unsigned long long)c.replay_ops, (unsigned long long)c.pass, (unsigned long long)c.fail,
	            (unsigned long long)(seeds - seeds_failed), (unsigned long long)seeds);
	std::printf("cursor reads: complete %llu, fallback %llu; journal records %llu; chunks seen %llu, new %llu, max %llu\n",
	            (unsigned long long)c.cur_complete, (unsigned long long)c.cur_fallback, (unsigned long long)c.journal_recs,
	            (unsigned long long)c.chunks_seen, (unsigned long long)c.chunks_rebuilt, (unsigned long long)c.max_chunks);
	if (!c.first.empty()) std::printf("first FAIL: %s\n", c.first.c_str());
	std::printf("%s\n", c.fail == 0 ? "PASS" : "FAIL");
	return c.fail == 0 ? 0 : 1;
}
