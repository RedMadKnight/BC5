// BC5 experiment 0412: CPU test of wc0412.inc (tag wc412): the parts of the CPU/GPU split that are free of the host.
//   - parse_maps takes exactly the lines of /proc/self/maps with the file's device and inode (same inode on another
//     device, another inode, anonymous lines and broken lines are left out) and reads start, length and offset;
//   - for_va gives, for a file range, every address range that shows a part of it, and nothing else: against a model
//     that asks byte by byte (page by page) which addresses show which file page;
//   - any_soft_dirty reads bit 55 only;
//   - the level is 0 when the variable is unset.
// build: g++ -std=c++20 -O1 -Wall -Wextra -Werror wc0412.cpp -o wc0412
#include <cinttypes>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <map>
#include <random>
#include <set>
#include <string>
#include <vector>

#include "wc0412.inc"

static uint64_t g_checks = 0, g_ok = 0;
static void     check(bool c, const char* what) {
	g_checks++;
	if (c) g_ok++;
	else if (g_checks - g_ok < 20) std::printf("FAIL: %s\n", what);
}

int main() {
	{
		const std::string text =
		    "7f0000000000-7f0000400000 rw-s 00200000 00:01 4242                       /memfd:bc5-direct (deleted)\n"
		    "1120000000-1120200000 rw-s 40000000 00:01 4242                           /memfd:bc5-direct (deleted)\n"
		    "7f1000000000-7f1000001000 rw-s 00000000 00:01 4243                       /memfd:other (deleted)\n"
		    "7f2000000000-7f2000001000 rw-s 00000000 00:2f 4242                       /some/file\n"
		    "7f3000000000-7f3000021000 rw-p 00000000 00:00 0                          [heap]\n"
		    "not a line at all\n"
		    "7f4000000000-7f4000001000 r--s 00003000 00:01 4242                       /memfd:bc5-direct (deleted)";
		const auto v = wc412::parse_maps(text, 0, 1, 4242);
		check(v.size() == 3, "three lines of the file");
		check(v.size() == 3 && v[0].va == 0x7f0000000000ull && v[0].len == 0x400000 && v[0].off == 0x200000, "first line: start, length, offset");
		check(v.size() == 3 && v[1].va == 0x1120000000ull && v[1].len == 0x200000 && v[1].off == 0x40000000, "second line");
		check(v.size() == 3 && v[2].va == 0x7f4000000000ull && v[2].len == 0x1000 && v[2].off == 0x3000, "a last line without a newline");
		check(wc412::parse_maps(text, 0, 0x2f, 4242).size() == 1, "the same inode on another device is another file");
		check(wc412::parse_maps("", 0, 1, 4242).empty(), "no text: no line");
	}
	constexpr uint64_t P = 0x1000;
	std::mt19937_64    rng(0x7763343132);
	for (int it = 0; it < 3000; it++) {
		// a file of 64 pages; up to 6 mappings at disjoint address blocks, any of them may show the same file pages
		std::vector<wc412::MapLine>         maps;
		std::map<uint64_t, uint64_t>        shows; // address page -> file page
		const int                           n = static_cast<int>(rng() % 7);
		for (int i = 0; i < n; i++) {
			const uint64_t off = (rng() % 60) * P, len = (1 + rng() % 4) * P, va = 0x100000000ull * static_cast<uint64_t>(i + 1) + (rng() % 16) * P;
			maps.push_back({va, len, off});
			for (uint64_t b = 0; b < len; b += P) shows[va + b] = off + b;
		}
		const uint64_t o = (rng() % 62) * P, l = (1 + rng() % 8) * P;
		std::set<uint64_t> got;
		bool               clean = true;
		wc412::for_va(maps, o, l, [&](uint64_t va, uint64_t bytes) {
			clean = clean && bytes != 0 && va % P == 0 && bytes % P == 0;
			for (uint64_t b = 0; b < bytes; b += P) clean = clean && got.insert(va + b).second;
		});
		std::set<uint64_t> want;
		for (const auto& [va, fp]: shows) {
			if (fp >= o && fp < o + l) want.insert(va);
		}
		check(clean, "ranges are whole pages, not empty, and no address comes twice");
		check(got == want, "exactly the addresses that show a page of the range");
	}
	{
		uint64_t e[4] = {0, 1ull << 63u, 1ull << 54u, 1ull << 56u};
		check(!wc412::any_soft_dirty(e, 4), "present and neighbouring bits are not soft-dirty");
		e[2] |= 1ull << 55u;
		check(wc412::any_soft_dirty(e, 4), "bit 55 is");
		check(!wc412::any_soft_dirty(e, 2) && !wc412::any_soft_dirty(e, 0), "only the entries asked about");
	}
	check(wc412::level() == 0, "off when the variable is unset");
	std::printf("wc0412: %" PRIu64 " of %" PRIu64 "; end\n", g_ok, g_checks);
	return g_ok == g_checks ? 0 : 1;
}
