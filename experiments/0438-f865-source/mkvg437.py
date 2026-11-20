#!/usr/bin/env python3
# BC5 experiment 0437 (tag vg437): the direct view list and the direct sync keyed on a generation that moves only when
# a direct range changes, applied to a KytyPlus tree with patch 0001 bb04219b (exp 0436 in it). Run once on a clean tree:
#   python -I mkvg437.py <KytyPlus tree>
# Switch BC5_DIRECT_VIEWS_GEN, read in normal and lean: "0" = off (the shared behaviour: every edit of any guest range
# rebuilds the direct view list and lets the next submission past the 50 ms gate); unset or anything else = on, in this
# TEST build only, so that the candidate's arm is its binary (LESSONS R66). Every replacement must match exactly once,
# or nothing is written.
import os
import sys

root = sys.argv[1]
files = {}


def load(rel):
    if rel not in files:
        files[rel] = open(os.path.join(root, rel), encoding="utf-8", newline="").read()
    return files[rel]


def rep(rel, old, new, count=1):
    s = load(rel)
    n = s.count(old)
    assert n == count, (rel, old[:70], n)
    files[rel] = s.replace(old, new)


MEM = "src/kernel/memory.cpp"
MEMH = "src/kernel/memory.h"
AGC = "src/libs/bc5LleAgc.cpp"

# --- memory.cpp: the direct generation in VirtualRanges ------------------------------------------------------------
rep(MEM, """	[[nodiscard]] uint64_t Generation() const { return m_gen.load(std::memory_order_acquire); }
""", """	[[nodiscard]] uint64_t Generation() const { return m_gen.load(std::memory_order_acquire); }
	// BC5 (experiment 0437, tag vg437): changes only with an edit that changes a direct range's start, size, offset or
	// name, the four things the direct view list is made of (bc5LleAgc.cpp, direct_views_build: type 0 only; the
	// protection and the memory type are not in it). An edit of a flexible, pooled, stack, code or reserved range, or a
	// protection change that leaves a direct range whole, leaves it as it is.
	[[nodiscard]] uint64_t DirectGeneration() const { return m_gen_direct.load(std::memory_order_acquire); }
""")

# The guard: constructed right after the lock in every editing call, it copies the direct ranges of the edit's window
# (the span and every range that overlaps it: an edit changes nothing outside that window, and direct ranges never
# merge, SameMergeKey) and on leaving the call, still under the lock, compares them with the window's direct ranges
# after the edit. Exact, no hash. Bumped after the edit and under the same lock as the edit: a reader that sees the new
# value takes its snapshot after the edit; one that read the old value rebuilds at its next call.
GUARD = """	// BC5 (experiment 0437, tag vg437): see DirectGeneration. Declared after the lock, so it is destroyed under it.
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

	bool Add(uint64_t start, uint64_t size, uint64_t offset, int protection, int memory_type,"""
rep(MEM, """	bool Add(uint64_t start, uint64_t size, uint64_t offset, int protection, int memory_type,""", GUARD)

# every editing call: the guard right after its generation bump (8 calls, each with the same two lines)
BUMP = """		m_gen.fetch_add(1, std::memory_order_acq_rel); // BC5 (experiment 0037)
		NoteDirtyUnlocked(start, size);                // BC5 (experiment 0415, mr415)
"""
rep(MEM, BUMP, BUMP + """		DirectEditGuard vg437(this, start, size);      // BC5 (experiment 0437, tag vg437)
""", count=8)

rep(MEM, """	std::atomic<uint64_t> m_gen {1};
""", """	std::atomic<uint64_t> m_gen {1};
	std::atomic<uint64_t> m_gen_direct {1}; // BC5 (experiment 0437, tag vg437)
""")

rep(MEM, """uint64_t Bc5MappedRangesGeneration() {
	return g_virtual_ranges != nullptr ? g_virtual_ranges->Generation() : 0;
}
""", """uint64_t Bc5MappedRangesGeneration() {
	return g_virtual_ranges != nullptr ? g_virtual_ranges->Generation() : 0;
}
// BC5 (experiment 0437, tag vg437): see VirtualRanges::DirectGeneration.
uint64_t Bc5DirectRangesGeneration() {
	return g_virtual_ranges != nullptr ? g_virtual_ranges->DirectGeneration() : 0;
}
""")

rep(MEMH, """uint64_t Bc5MappedRangesGeneration(); // BC5 (experiment 0037): changes with every edit of the guest's ranges
""", """uint64_t Bc5MappedRangesGeneration(); // BC5 (experiment 0037): changes with every edit of the guest's ranges
uint64_t Bc5DirectRangesGeneration(); // BC5 (experiment 0437, tag vg437): changes only when a direct range's start, size, offset or name changes
""")

# --- bc5LleAgc.cpp: the two readers of the direct path --------------------------------------------------------------
rep(AGC, """static std::atomic<uint64_t> g_views_builds {0}; // experiment 0156: rebuilds of the views
""", """static std::atomic<uint64_t> g_views_builds {0}; // experiment 0156: rebuilds of the views
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
		std::fprintf(stderr, "[bc5] exp 0437 (tag vg437): BC5_DIRECT_VIEWS_GEN %s: the direct view list follows %s\\n", on ? "ON" : "off",
		             on ? "the direct ranges' generation" : "every edit of the guest's ranges");
		return on;
	}();
	return v;
}
static uint64_t vg437_gen() {
	return vg437_on() ? Libs::LibKernel::Memory::Bc5DirectRangesGeneration() : Libs::LibKernel::Memory::Bc5MappedRangesGeneration();
}
""")

rep(AGC, """	const uint64_t  g           = Libs::LibKernel::Memory::Bc5MappedRangesGeneration();
	const uint64_t  now         = SoftCp::now_ns();
	std::lock_guard l(m);""", """	const uint64_t  g           = k == 0 ? vg437_gen() : Libs::LibKernel::Memory::Bc5MappedRangesGeneration(); // exp 0437 (tag vg437)
	const uint64_t  now         = SoftCp::now_ns();
	std::lock_guard l(m);""")

# mr415's stage S2 hands back the snapshot's generation of the whole table; with vg437 on, kind 0 keeps the direct
# generation read before the build (a direct edit after that read makes the next call rebuild).
rep(AGC, """	gen[k]   = g_used; // experiment 0415 (mr415c): the generation of the snapshot the list was made from""",
    """	gen[k]   = k == 0 && vg437_on() ? g : g_used; // experiment 0415 (mr415c): the generation of the snapshot the list was made from; exp 0437 (vg437): kind 0's direct generation""")

rep(AGC, """	const uint64_t    ranges_gen  = S.kind == 0 ? Libs::LibKernel::Memory::Bc5MappedRangesGeneration() : S.ranges_gen;""",
    """	const uint64_t    ranges_gen  = S.kind == 0 ? vg437_gen() : S.ranges_gen; // exp 0437 (tag vg437)""")

# the count beside exp 0432's 10 s line (normal build only): edits of the table, of them direct, and the view builds
rep(AGC, """			std::fprintf(stderr, "[bc5] %s\\n", line);
			journal("%s\\n", line);
		}
	}
#endif
	if (bc5::load_stat::on()) { // experiment 0415 (ls415c): the hold by part""", """			std::fprintf(stderr, "[bc5] %s\\n", line);
			journal("%s\\n", line);
			journal("exp 0437 (tag vg437): t %.1f s: views-gen %s; range table generation %" PRIu64 ", direct generation %" PRIu64 ", view builds %" PRIu64 "\\n", timing_now(),
			        vg437_on() ? "ON" : "off", Libs::LibKernel::Memory::Bc5MappedRangesGeneration(), Libs::LibKernel::Memory::Bc5DirectRangesGeneration(),
			        static_cast<uint64_t>(g_views_builds));
		}
	}
#endif
	if (bc5::load_stat::on()) { // experiment 0415 (ls415c): the hold by part""")

for rel, s in files.items():
    open(os.path.join(root, rel), "w", encoding="utf-8", newline="").write(s)
    print("written", rel)
