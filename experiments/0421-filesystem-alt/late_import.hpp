// BC5 experiment 0421 (tag fs421): the late import of a lazy heap's written chunks (BC5_DIRECT_FS_LATE).
// Copied by mk0421.py into the KytyPlus tree as src/bc5/late_import.hpp; tested on the laptop by test0421late.cpp.
//
// A chunk of a "late" view (the title's heap "FileSystem") that holds data and is not imported is first seen at some
// time; it is imported once it has been seen for `delay_ns`, at most `per_pass` chunks in one pass and passes with an
// import at least `gap_ns` apart. Until then the heap is lazy, as on build U (no import during the loads that
// follow a write); after it the chunk is GPU-readable, as on build W. No CPU write is caught: a chunk is "written"
// when SEEK_DATA finds data in it, the same test the by-data import uses.
#pragma once

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <unordered_map>
#include <vector>

namespace bc5::late_import {

struct Limits {
	uint64_t delay_ns = 30'000'000'000ull; // seen this long before the import
	uint64_t gap_ns   = 250'000'000ull;    // passes that import a late chunk are at least this far apart
	size_t   per_pass = 1;                 // chunks imported in one pass
};

struct State {
	std::unordered_map<uint64_t, uint64_t> seen; // chunk offset -> when it was first seen written and not imported
	uint64_t last_ns     = 0;                    // the last pass that imported a late chunk (0: none yet)
	uint64_t next_due_ns = 0;                    // 0: nothing waits; else the earliest time a waiting chunk may go
	uint64_t imported    = 0;                    // chunks picked so far
};

// `written`: the chunks of late views that hold data and are not imported now (any order, repeats allowed).
// Returns the chunks to import in this pass, ascending. A chunk that is no longer in `written` (imported by another
// path, or its view gone) is forgotten; if it comes back, its time starts again.
inline std::vector<uint64_t> pick(State& s, std::vector<uint64_t> written, uint64_t now, const Limits& L) {
	std::sort(written.begin(), written.end());
	written.erase(std::unique(written.begin(), written.end()), written.end());
	std::unordered_map<uint64_t, uint64_t> keep;
	keep.reserve(written.size());
	for (const uint64_t c: written) {
		const auto it = s.seen.find(c);
		keep.emplace(c, it != s.seen.end() ? it->second : now);
	}
	s.seen.swap(keep);
	std::vector<uint64_t> out;
	const bool gap_ok = s.last_ns == 0 || now - s.last_ns >= L.gap_ns;
	if (gap_ok) {
		for (const uint64_t c: written) {
			if (out.size() >= L.per_pass) break;
			if (s.seen[c] + L.delay_ns <= now) out.push_back(c);
		}
	}
	if (!out.empty()) {
		s.last_ns = now;
		s.imported += out.size();
	}
	// When the rest may go: its own time, and not before the gap after the last pass that imported.
	uint64_t next = 0;
	for (const uint64_t c: written) {
		if (std::binary_search(out.begin(), out.end(), c)) continue;
		uint64_t t = s.seen[c] + L.delay_ns;
		if (s.last_ns != 0) t = std::max(t, s.last_ns + L.gap_ns);
		next = next == 0 ? t : std::min(next, t);
	}
	s.next_due_ns = next;
	return out;
}

// True when a chunk waits and its time has come: the caller must not skip its pass for "nothing changed".
inline bool due(const State& s, uint64_t now) {
	return s.next_due_ns != 0 && now >= s.next_due_ns;
}

// The switch's value (on by default since the maintainer's order of 2026-11-15: it replaces build W's "FileSystem is
// never lazy"): "0" is off (W's way: imported by data at once); unset, empty, "1" or "on" is 30 s; a number of
// seconds from 5 to 3600 is that; anything else is 30 s.
inline uint64_t delay_of(const char* e) {
	if (e != nullptr && e[0] == '0' && e[1] == 0) return 0;
	if (e == nullptr || e[0] == 0) return 30'000'000'000ull;
	uint64_t v = 0;
	const char* p = e;
	for (; *p >= '0' && *p <= '9'; p++) {
		v = v * 10 + static_cast<uint64_t>(*p - '0');
		if (v > 100000) break;
	}
	if (*p == 0 && v >= 5 && v <= 3600) return v * 1'000'000'000ull;
	return 30'000'000'000ull;
}

} // namespace bc5::late_import
