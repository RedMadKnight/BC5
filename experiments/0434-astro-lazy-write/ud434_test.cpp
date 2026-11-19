#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <vector>
#include <utility>
#include "ud434.inc"
static int fails = 0, cases = 0;
static void check(const char* name, std::vector<uint32_t> p, std::vector<std::pair<uint64_t, uint64_t>> want) {
	std::vector<std::pair<uint64_t, uint64_t>> got;
	ud434::scan(p.data(), static_cast<uint32_t>(p.size()), [&](uint64_t a, uint64_t n) { got.emplace_back(a, n); });
	cases++;
	if (got != want) {
		fails++;
		std::printf("FAIL %s: got", name);
		for (auto& g: got) std::printf(" 0x%llx+%llu", (unsigned long long)g.first, (unsigned long long)g.second);
		std::printf("\n");
	}
}
static uint32_t hdr(uint32_t op, uint32_t n) { return 0xc0000000u | ((n - 2) << 16u) | (op << 8u); }
int main() {
	// The faulting dispatch's user data, IB dword 64209 of devcoredump 20261119-140758-devcd4 (verbatim).
	check("real 64209", {0xc0087600, 0x240, 0xcf7d5c0, 0x10005, 0x800, 0x30005004, 0x14cb62dc, 0x10003, 0x10, 0x30005004},
	      {{0x50cf7d5c0ull, 2048}, {0x314cb62dcull, 16}});
	// IB dword 64235: one V# (stride 16, 0x4000 records) then four zeros (empty, skipped).
	check("real 64235", {0xc0087600, 0x240, 0x6d8f0000, 0x100005, 0x4000, 0x4bfac, 0, 0, 0, 0}, {{0x56d8f0000ull, 0x40000}});
	check("header form", {hdr(0x76, 10), 0x240, 0xcf7d5c0, 0x10005, 0x800, 0x30005004, 0x14cb62dc, 0x10003, 0x10, 0x30005004},
	      {{0x50cf7d5c0ull, 2048}, {0x314cb62dcull, 16}});
	check("SET_SH_REG_INDEX", {hdr(0x9b, 6), 0x240, 0x14cb62dc, 0x10003, 0x10, 0x30005004}, {{0x314cb62dcull, 16}});
	// Starts at USER_DATA_1: the quad at reg 1 is not aligned; the one at reg 4 is.
	check("misaligned start", {hdr(0x76, 9), 0x241, 1, 2, 3, 0x14cb62dc, 0x10003, 0x10, 0x30005004}, {{0x314cb62dcull, 16}});
	// PS user data at 0x0c..0x2b: aligned to 0x0c.
	check("PS stage", {hdr(0x76, 6), 0x0c, 0x14cb62dc, 0x10003, 0x10, 0x30005004}, {{0x314cb62dcull, 16}});
	check("PS misaligned", {hdr(0x76, 6), 0x0d, 0x14cb62dc, 0x10003, 0x10, 0x30005004}, {});
	// A quad that would cross COMPUTE_USER_DATA_15 into the next register.
	check("crosses compute end", {hdr(0x76, 6), 0x24e, 0x14cb62dc, 0x10003, 0x10, 0x30005004}, {});
	check("compute last quad", {hdr(0x76, 6), 0x24c, 0x14cb62dc, 0x10003, 0x10, 0x30005004}, {{0x314cb62dcull, 16}});
	// An image descriptor (T#: TYPE 8 in bits 31:28) is not a V#.
	check("T# skipped", {hdr(0x76, 6), 0x240, 0x14cb62dc, 0x10003, 0x10, 0x80005004}, {});
	check("stride 0 bytes", {hdr(0x76, 6), 0x240, 0x14cb6000, 0x3, 0x1000, 0x30005004}, {{0x314cb6000ull, 0x1000}});
	check("zero base", {hdr(0x76, 6), 0x240, 0, 0, 0x10, 0x30005004}, {});
	check("cut to 256 MiB", {hdr(0x76, 6), 0x240, 0x14cb6000, 0x3fff0003, 0xffffffff, 0x30005004}, {{0x314cb6000ull, 256ull << 20}});
	check("not a user reg", {hdr(0x76, 6), 0x204, 0x14cb62dc, 0x10003, 0x10, 0x30005004}, {});
	check("SET_CONTEXT_REG", {hdr(0x69, 6), 0x240, 0x14cb62dc, 0x10003, 0x10, 0x30005004}, {});
	check("short", {hdr(0x76, 5), 0x240, 0x14cb62dc, 0x10003, 0x10}, {});
	check("type 2 nop", {0x80000000u, 0x240, 0x14cb62dc, 0x10003, 0x10, 0x30005004}, {});
	std::printf("ud434 scan: %d of %d cases pass\n", cases - fails, cases);
	return fails == 0 ? 0 : 1;
}
