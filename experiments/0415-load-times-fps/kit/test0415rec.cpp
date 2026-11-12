// SPDX-License-Identifier: GPL-2.0-only
// Experiment 0415: CPU test of src/bc5/map_records.hpp (tag mr415, stage S1). A model of the guest's range table
// (sorted ranges that merge with equal neighbours and split under partial edits, as VirtualRanges does) takes random
// add / remove / rename / protect / retype calls; every call leaves its span as a record. A view list (the ranges of
// type 0) is kept up to date from the records with map_records::apply and compared with the list rebuilt from every
// range: after each call, and in batches (several calls, then all their spans applied against the final state, in
// shuffled order, with spans of calls that changed nothing among them).
// Ends with "test0415rec: <passed> of <run>; end". Portable.
#include "bc5/map_records.hpp"

#include <cstdio>
#include <random>
#include <string>

namespace mr = bc5::map_records;

struct Range {
	uint64_t start, size, offset;
	int      type, prot, name;
};
struct View {
	uint64_t    va, size, off;
	std::string name;
	bool        operator==(const View& o) const { return va == o.va && size == o.size && off == o.off && name == o.name; }
};

static int g_run = 0, g_ok = 0;
static void check(bool v, const char* what) {
	g_run++;
	if (v) {
		g_ok++;
	} else {
		std::printf("FAIL: %s\n", what);
	}
}

struct Model {
	std::vector<Range> r; // sorted by start, not overlapping

	static bool mergeable(const Range& a, const Range& b) {
		return a.start + a.size == b.start && a.type == b.type && a.prot == b.prot && a.name == b.name && a.offset + a.size == b.offset;
	}
	void merge_all_around(uint64_t lo, uint64_t hi) { // merges neighbours that became equal at the span's edges and inside it
		for (size_t i = 0; i + 1 < r.size();) {
			if (r[i].start + r[i].size >= lo && r[i + 1].start <= hi && mergeable(r[i], r[i + 1])) {
				r[i].size += r[i + 1].size;
				r.erase(r.begin() + static_cast<std::ptrdiff_t>(i) + 1);
			} else {
				i++;
			}
		}
	}
	// cuts every range at lo and hi, calls f on the pieces inside [lo, hi); f returns false to delete the piece
	template <class F>
	void edit(uint64_t lo, uint64_t hi, F&& f) {
		std::vector<Range> out;
		for (const Range& x: r) {
			const uint64_t xs = x.start, xe = x.start + x.size;
			if (xe <= lo || xs >= hi) {
				out.push_back(x);
				continue;
			}
			if (xs < lo) out.push_back({xs, lo - xs, x.offset, x.type, x.prot, x.name});
			Range mid {std::max(xs, lo), std::min(xe, hi) - std::max(xs, lo), x.offset + (std::max(xs, lo) - xs), x.type, x.prot, x.name};
			if (f(&mid)) out.push_back(mid);
			if (xe > hi) out.push_back({hi, xe - hi, x.offset + (hi - xs), x.type, x.prot, x.name});
		}
		r.swap(out);
		merge_all_around(lo, hi);
	}
	bool add(uint64_t start, uint64_t size, uint64_t offset, int type, int prot, int name) {
		for (const Range& x: r) {
			if (x.start < start + size && x.start + x.size > start) return false;
		}
		const auto pos = std::lower_bound(r.begin(), r.end(), start, [](const Range& x, uint64_t s) { return x.start < s; });
		r.insert(pos, {start, size, offset, type, prot, name});
		merge_all_around(start, start + size);
		return true;
	}
};

static bool make_view(const Range& x, View* v) {
	if (x.type != 0 || x.size == 0) return false;
	*v = {x.start, x.size, x.offset, "heap" + std::to_string(x.name)};
	return true;
}

static std::vector<View> rebuild(const Model& m) {
	std::vector<View> v;
	for (const Range& x: m.r) {
		View w;
		if (make_view(x, &w)) v.push_back(w);
	}
	return v;
}

int main() {
	std::mt19937_64 rng(0x0415'0001ull);
	auto            rnd = [&rng](uint64_t n) { return n == 0 ? 0 : rng() % n; };
	const uint64_t  kPage = 0x4000, kSpace = 400; // pages

	uint64_t steps = 0, differ = 0, batches = 0, batch_differ = 0, nonempty = 0, splits = 0;
	for (int round = 0; round < 300; round++) {
		Model             m;
		std::vector<View> views;             // kept from records, call by call
		std::vector<View> bviews;            // kept from records, batch by batch
		std::vector<std::pair<uint64_t, uint64_t>> pending;
		for (int step = 0; step < 400; step++) {
			const uint64_t lo = (1 + rnd(kSpace)) * kPage, hi = lo + (1 + rnd(24)) * kPage;
			const int      op = static_cast<int>(rnd(10));
			const size_t   before = m.r.size();
			if (op < 4) {
				m.add(lo, hi - lo, rnd(3) == 0 ? lo : rnd(1000) * kPage, rnd(4) == 0 ? 1 : 0, static_cast<int>(rnd(2)), static_cast<int>(rnd(3)));
			} else if (op < 6) {
				m.edit(lo, hi, [](Range*) { return false; }); // remove (unmap), splitting what it cuts
			} else if (op < 8) {
				const int name = static_cast<int>(rnd(3));
				m.edit(lo, hi, [name](Range* x) { x->name = name; return true; });
			} else if (op < 9) {
				const int prot = static_cast<int>(rnd(2));
				m.edit(lo, hi, [prot](Range* x) { x->prot = prot; return true; });
			} else {
				const int type = rnd(2) == 0 ? 0 : 1;
				m.edit(lo, hi, [type](Range* x) { x->type = type; return true; });
			}
			if (m.r.size() > before + 1) splits++;
			mr::apply(views, m.r, lo, hi, make_view);
			const auto full = rebuild(m);
			steps++;
			if (!(views == full)) {
				differ++;
				views = full;
			}
			if (!full.empty()) nonempty++;
			pending.emplace_back(lo, hi);
			if (rnd(8) == 0) pending.emplace_back((1 + rnd(kSpace)) * kPage, (1 + rnd(kSpace)) * kPage + kPage); // a record of a call that changed nothing
			if (rnd(6) == 0) { // a batch: all pending spans against the state as it is now, in any order
				std::shuffle(pending.begin(), pending.end(), rng);
				for (const auto& [a, b]: pending) mr::apply(bviews, m.r, a, b, make_view);
				pending.clear();
				batches++;
				if (!(bviews == full)) {
					batch_differ++;
					bviews = full;
				}
			}
		}
	}
	check(differ == 0, "apply: the list kept from records equals the rebuilt list after every call");
	check(batch_differ == 0, "apply: the same for batches of spans applied late and in any order");
	check(nonempty > steps / 2 && splits > steps / 100, "apply: the calls include splits and leave views most of the time");
	std::printf("apply: %llu calls, %llu differences; %llu batches, %llu differences; %llu calls that split a range\n", static_cast<unsigned long long>(steps),
	            static_cast<unsigned long long>(differ), static_cast<unsigned long long>(batches), static_cast<unsigned long long>(batch_differ), static_cast<unsigned long long>(splits));

	// touching(): by hand
	{
		std::vector<Range> r = {{0x1000, 0x1000, 0, 0, 0, 0}, {0x2000, 0x2000, 0, 0, 0, 0}, {0x8000, 0x1000, 0, 0, 0, 0}};
		auto               t = mr::touching(r, 0x4000, 0x8000);
		check(t.first == 1 && t.second == 3, "touching: a span between two ranges takes both neighbours it touches");
		t = mr::touching(r, 0x5000, 0x6000);
		check(t.first == 2 && t.second == 2, "touching: a span in a gap touches nothing");
		t = mr::touching(r, 0x0, 0x800);
		check(t.first == 0 && t.second == 0, "touching: before everything");
		t = mr::touching(r, 0x2800, 0x3000);
		check(t.first == 1 && t.second == 2, "touching: inside one range");
		t = mr::touching(r, 0x9000, 0xa000);
		check(t.first == 2 && t.second == 3, "touching: a span that starts where the last range ends");
		t = mr::touching(std::vector<Range> {}, 1, 2);
		check(t.first == 0 && t.second == 0, "touching: no ranges");
		check(mr::end_of(UINT64_MAX - 5, 100) == UINT64_MAX && mr::end_of(10, 5) == 15, "end_of: saturates");
	}
	std::printf("test0415rec: %d of %d; end\n", g_ok, g_run);
	return g_ok == g_run ? 0 : 1;
}
