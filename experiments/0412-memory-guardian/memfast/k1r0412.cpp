// BC5 experiment 0412: CPU test of k1r0412.inc (tag k1r412): the read-only zero cover's pieces against a page-level
// model of a file with imported ranges and views.
//   - every page under the view that no imported range holds is covered exactly once; no page an imported range holds
//     and no page outside the view is covered;
//   - a piece never exceeds a chunk and never crosses a chunk boundary of the file; pieces ascend and do not overlap;
//   - importing a chunk (the CPU wrote it) removes exactly that chunk's pieces and changes no other piece: the
//     rebuild's "drop what is no longer wanted, keep what is unchanged" then touches only that chunk;
//   - a view wholly imported has no piece; a view with nothing imported is covered whole.
// build: g++ -std=c++20 -O1 -Wall -Wextra -Werror k1r0412.cpp -o k1r0412
#include <algorithm>
#include <cinttypes>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <random>
#include <vector>

#include "k1r0412.inc"

static uint64_t g_checks = 0, g_ok = 0;
static void check(bool c, const char* what) {
	g_checks++;
	if (c) g_ok++;
	else if (g_checks - g_ok < 20) std::printf("FAIL: %s\n", what);
}

int main() {
	constexpr uint64_t kChunk = 2ull << 20, kPage = 4096, kPagesPerChunk = kChunk / kPage;
	std::mt19937_64 rng(0x4b3152);
	for (int it = 0; it < 3000; it++) {
		const uint64_t chunks = 4 + rng() % 28;
		std::vector<char> imported(chunks, 0);
		for (auto& c: imported) c = (rng() % 3 == 0) ? 1 : 0;
		if (it % 50 == 0) std::fill(imported.begin(), imported.end(), 1);
		if (it % 50 == 1) std::fill(imported.begin(), imported.end(), 0);
		auto bos_of = [&](const std::vector<char>& imp) {
			std::vector<k1r412::Bo> bos; // runs of imported chunks, as the import merges them
			for (uint64_t c = 0; c < chunks;) {
				if (!imp[c]) { c++; continue; }
				uint64_t e = c;
				while (e < chunks && imp[e] && (e - c) < 1 + rng() % 8) e++;
				bos.push_back({c * kChunk, (e - c) * kChunk});
				c = e;
			}
			return bos;
		};
		// a view: page aligned, anywhere in the file, mapped at an unrelated address
		const uint64_t file_pages = chunks * kPagesPerChunk;
		const uint64_t voff_p = rng() % file_pages;
		const uint64_t vsize_p = 1 + rng() % (file_pages - voff_p);
		const uint64_t voff = voff_p * kPage, vsize = vsize_p * kPage, vva = 0x1100000000ull + (rng() % 4096) * kPage;
		const auto bos = bos_of(imported);
		std::vector<k1r412::Piece> p;
		k1r412::cover(vva, voff, vsize, bos, kChunk, p);
		// the model: pages
		std::vector<int> cov(file_pages, 0);
		bool inside = true, small = true, one_chunk = true, asc = true;
		uint64_t prev_end = 0;
		for (const auto& x: p) {
			if (x.va < vva || x.va + x.size > vva + vsize || (x.va & (kPage - 1)) != 0 || (x.size & (kPage - 1)) != 0 || x.size == 0) { inside = false; continue; }
			if (x.size > kChunk) small = false;
			const uint64_t f0 = voff + (x.va - vva), f1 = f0 + x.size;
			if (f0 / kChunk != (f1 - 1) / kChunk) one_chunk = false;
			if (x.va < prev_end) asc = false;
			prev_end = x.va + x.size;
			for (uint64_t f = f0; f < f1; f += kPage) cov[f / kPage]++;
		}
		check(inside, "every piece lies inside the view, page aligned, not empty");
		check(small, "no piece exceeds the zero buffer (one chunk)");
		check(one_chunk, "no piece crosses a chunk boundary of the file");
		check(asc, "pieces ascend and do not overlap");
		bool exact = true;
		for (uint64_t pg = 0; pg < file_pages; pg++) {
			const bool under = pg >= voff_p && pg < voff_p + vsize_p;
			const int  want  = under && !imported[pg / kPagesPerChunk] ? 1 : 0;
			if (cov[pg] != want) exact = false;
		}
		check(exact, "covered exactly once: the pages under the view that no imported range holds, and no other page");
		if (std::all_of(imported.begin(), imported.end(), [](char c) { return c != 0; })) check(p.empty(), "a view wholly imported has no piece");
		// the CPU writes one unimported chunk under the view: it is imported; only its pieces go
		std::vector<uint64_t> cand;
		for (uint64_t c = voff / kChunk; c <= (voff + vsize - 1) / kChunk; c++) {
			if (!imported[c]) cand.push_back(c);
		}
		if (!cand.empty()) {
			const uint64_t c = cand[rng() % cand.size()];
			auto imp2 = imported;
			imp2[c] = 1;
			std::vector<k1r412::Piece> q;
			k1r412::cover(vva, voff, vsize, bos_of(imp2), kChunk, q);
			bool only = true;
			for (const auto& x: p) {
				const uint64_t f0 = voff + (x.va - vva);
				const bool in_c = f0 / kChunk == c;
				const bool still = std::find(q.begin(), q.end(), x) != q.end();
				if (in_c == still) only = false; // a piece of the written chunk must go, every other piece must stay as it was
			}
			check(only && q.size() < p.size(), "after the CPU's first write: exactly that chunk's pieces go, every other piece is unchanged");
		}
	}
	{ // nothing imported: the view is covered whole, in chunk-bounded pieces
		std::vector<k1r412::Bo> none;
		std::vector<k1r412::Piece> p;
		k1r412::cover(0x1100000000ull, 0x4000, 3 * kChunk, none, kChunk, p);
		uint64_t sum = 0;
		for (const auto& x: p) sum += x.size;
		check(sum == 3 * kChunk && p.size() == 4 && p.front().va == 0x1100000000ull && p.front().size == kChunk - 0x4000, "nothing imported: covered whole, the first piece ends at the chunk boundary");
	}
	{ // The cost of the pass (README section 78): 21,000 views over a file with 600 imported buffers, as in the second
		// title's menu. The form before 2026-11-13 evening walked the list from its start for every view; it is kept here
		// as the reference, with its step counter. The pieces must be the same; the steps must not.
		auto old_cover = [](uint64_t vva, uint64_t voff, uint64_t vsize, const std::vector<k1r412::Bo>& bos, uint64_t chunk, std::vector<k1r412::Piece>& out, uint64_t& steps) {
			const uint64_t vend = voff + vsize;
			uint64_t       cur  = voff;
			auto           emit = [&](uint64_t lo, uint64_t hi) {
				while (lo < hi) {
					const uint64_t stop = ((lo / chunk) + 1) * chunk, e = stop < hi ? stop : hi;
					out.push_back({vva + (lo - voff), e - lo});
					lo = e;
				}
			};
			for (const auto& b: bos) {
				steps++;
				if (b.off + b.size <= cur) continue;
				if (b.off >= vend) break;
				if (b.off > cur) emit(cur, b.off < vend ? b.off : vend);
				if (b.off + b.size > cur) cur = b.off + b.size;
				if (cur >= vend) break;
			}
			if (cur < vend) emit(cur, vend);
		};
		std::mt19937_64         r2(0x636f7374);
		std::vector<k1r412::Bo> bos;
		uint64_t                off = 0;
		for (int i = 0; i < 600; i++) { // 600 buffers of 2-64 MiB with gaps of 0-16 MiB: about 12 GiB of file
			off += (r2() % 9) * kChunk;
			const uint64_t n = (1 + r2() % 32) * kChunk;
			bos.push_back({off, n});
			off += n;
		}
		uint64_t steps_old = 0, steps_new = 0, pieces = 0;
		bool     same = true;
		for (int v = 0; v < 21000; v++) {
			const uint64_t voff = (r2() % (off / kPage)) * kPage, vsize = (1 + r2() % 2048) * kPage, vva = 0x1000000000ull + voff;
			std::vector<k1r412::Piece> a, b;
			old_cover(vva, voff, vsize, bos, kChunk, a, steps_old);
			k1r412::cover(vva, voff, vsize, bos, kChunk, b, &steps_new);
			same = same && a == b;
			pieces += b.size();
		}
		std::printf("cost: 21000 views, 600 buffers: the old pass looked at %" PRIu64 " list entries, the new one at %" PRIu64 " (%" PRIu64 " pieces)\n", steps_old, steps_new, pieces);
		check(same, "the pass with the binary search gives the same pieces as the walk from the list's start");
		check(steps_old > 3'000'000, "the old pass costs millions of steps for 21,000 views (the 20 ms a rebuild of section 78)");
		check(steps_new < 21000 * 6, "the new pass looks at a handful of entries per view");
	}
	// the write bit of the fault status, the two kernel samples
	check(k1r412::status_write(0x00741041u), "status 0x00741041 (E1 case 4, RW 1) is a write");
	check(!k1r412::status_write(0x00601431u), "status 0x00601431 (the play of 2026-11-13, RW 0) is a read");
	check(k1r412::on(), "the rule is on when the variable is unset");
	std::printf("k1r0412: %" PRIu64 " of %" PRIu64 "; end\n", g_ok, g_checks);
	return g_ok == g_checks ? 0 : 1;
}
