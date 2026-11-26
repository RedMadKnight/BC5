#include <cinttypes>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <set>
#include <string>
#include <utility>
#include <vector>
#include "late_import.hpp"
typedef long long off_t2;
#define off_t off_t2
#define SEEK_DATA 3
static off_t lseek(int, off_t o, int) { return o; }
static void journal(const char* fmt, ...) __attribute__((format(printf, 1, 2)));
static void journal(const char*, ...) {}
constexpr uint64_t kDChunk = 2ull << 20u;
struct DView { uint64_t va, size, off; std::string name; bool lazy; bool eager; };
struct DState { int kind; const char* label; std::set<uint64_t> failed; uint64_t file_size = 0; };
static uint64_t direct_covered_end(const DState&, uint64_t) { return 0; }
// Exp 0421 (tag fs421), BC5_DIRECT_FS_LATE (default off): the GPU read fault of arm n13P4 (fault record
// 20261114-184017) read two written chunks of the lazy heap "FileSystem" 580 s after they were written. Build V/W
// imports the heap by data instead, at the moment of each write, and W's loads gained in-host stalls (exp 0412
// section 102; the link is inferred). With the switch on the heap stays lazy and each written chunk is imported once
// it has been written for the delay, one chunk a pass: no import of it during the load that wrote it.
static uint64_t fs421_late_ns() {
	static const uint64_t ns = [] {
		const uint64_t v = bc5::late_import::delay_of(std::getenv("BC5_DIRECT_FS_LATE"));
#ifndef KYTY_BC5_LEAN
		if (v != 0)
			std::fprintf(stderr, "[bc5] exp 0421 (tag fs421): BC5_DIRECT_FS_LATE on: \"FileSystem\" stays lazy; a written chunk of it is imported %.0f s after it is first seen, "
			                     "one chunk a pass, passes 250 ms apart\n", static_cast<double>(v) / 1e9);
#endif
		return v;
	}();
	return ns;
}
static bc5::late_import::State g_fs421[2]; // per DState kind
// The data chunks of a late view that no import covers (the by-data walk of direct_sync_one, for one view).
static void fs421_scan(const DState& S, const DView& v, int fd, std::vector<uint64_t>& out) {
	const uint64_t end = v.off + v.size;
	uint64_t       pos = v.off & ~(kDChunk - 1);
	while (pos < end) {
		if (const uint64_t ce = direct_covered_end(S, pos); ce != 0) { pos = ce; continue; }
		const off_t d = lseek(fd, static_cast<off_t>(pos), SEEK_DATA);
		if (d < 0 || static_cast<uint64_t>(d) >= end) break;
		const uint64_t c = static_cast<uint64_t>(d) & ~(kDChunk - 1);
		if (direct_covered_end(S, c) == 0) out.push_back(c);
		pos = c + kDChunk;
	}
}
static void fs421_pick(const DState& S, const std::vector<uint64_t>& written, uint64_t now, std::vector<uint64_t>& need) {
	std::vector<uint64_t> w;
	w.reserve(written.size());
	for (const uint64_t c: written) {
		if (S.failed.count(c) == 0 && c + kDChunk <= S.file_size) w.push_back(c);
	}
	bc5::late_import::Limits L;
	L.delay_ns = fs421_late_ns();
	auto& st = g_fs421[S.kind == 0 ? 0 : 1];
#ifndef KYTY_BC5_LEAN
	std::vector<std::pair<uint64_t, uint64_t>> first; // the chunks about to be picked, with when they were first seen
	for (const auto& [c, t]: st.seen) first.emplace_back(c, t);
#endif
	const std::vector<uint64_t> got = bc5::late_import::pick(st, std::move(w), now, L);
	for (const uint64_t c: got) need.push_back(c);
#ifndef KYTY_BC5_LEAN
	static uint64_t lines = 0;
	for (const uint64_t c: got) {
		uint64_t t0 = now;
		for (const auto& [fc, ft]: first) if (fc == c) t0 = ft;
		if (lines++ < 64)
			journal("fs421 late import (exp 0421): %s chunk 0x%" PRIx64 " of \"FileSystem\", seen written %.1f s ago; %" PRIu64 " late chunks so far, %zu waiting\n", S.label, c,
			        static_cast<double>(now - t0) / 1e9, st.imported, st.seen.size() - got.size());
	}
#endif
}

int main() { DState S{0,"direct",{},64ull<<20}; DView v{0,8ull<<20,0,"FileSystem",true,false}; std::vector<uint64_t> w, need; fs421_scan(S, v, 3, w); fs421_pick(S, w, 1, need); return (int)need.size(); }
