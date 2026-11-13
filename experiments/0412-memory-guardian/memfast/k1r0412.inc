// BC5 experiment 0412 (tag k1r412, README sections 62 and 63; design section 8): the read-only zero cover.
// ON by default since 2026-11-13 (the top's order after the maintainer's play); BC5_GUARD_K1R=0 turns it off. Every part of a view of direct
// memory that no imported buffer covers (a chunk the CPU has never written, in a heap that is imported by data or
// lazily) is GPU-mapped READABLE ONLY onto one shared 2 MiB zero buffer of its own. Nothing is pinned for it.
//   - a GPU READ there returns zeros, which is what the file holds there (E1 case 2; his play of 2026-11-13 faulted on
//     exactly such a read);
//   - a GPU WRITE there is a named page fault (E1 case 4): the job is lost and the catcher names the address as its own
//     kind; nothing can be written into the shared zero buffer, so nothing is aliased through it (the zero skip's
//     defect, section 48, is excluded by the mapping's missing write bit, not by a watcher);
//   - an address under NO view gets nothing: it stays unmapped and loud;
//   - when the CPU writes the chunk, the import's SEEK_DATA pass sees data, the chunk is imported and the same mapping
//     rebuild drops the cover and maps the real pages, before the submission that follows the sync reaches the kernel.
//     Ordering relied on: the title writes its data before it submits what reads it, and the sync runs before every
//     submission. A chunk written since the last sync is still zero for the GPU until that sync: for an unimported
//     chunk that was a fault before, never the real data.
// The cover's pieces are computed here, free of the host, and tested by k1r0412.cpp.
namespace k1r412 {
struct Bo {
	uint64_t off, size; // an imported range of the file, chunk aligned; the list is sorted by off and disjoint
};
struct Piece {
	uint64_t va, size; // a GPU mapping of the zero buffer: [va, va + size), size <= chunk, page aligned
	bool     operator==(const Piece& o) const { return va == o.va && size == o.size; }
};
inline bool on() {
	static const bool v = [] {
		const char* e = std::getenv("BC5_GUARD_K1R");
		return e == nullptr || !(e[0] == '0' && e[1] == 0); // on unless "0"
	}();
	return v;
}
// The parts of the view [voff, voff + vsize) of the file, mapped at vva, that no imported range covers, cut at the
// file's chunk boundaries (so that a piece never exceeds the zero buffer and a chunk's later import replaces whole
// pieces). Appended to out in ascending address order.
template <typename Bos> inline void cover(uint64_t vva, uint64_t voff, uint64_t vsize, const Bos& bos, uint64_t chunk, std::vector<Piece>& out) {
	const uint64_t vend = voff + vsize;
	uint64_t       cur  = voff;
	auto           emit = [&](uint64_t lo, uint64_t hi) { // a gap [lo, hi) of the file under the view
		while (lo < hi) {
			const uint64_t stop = ((lo / chunk) + 1) * chunk;
			const uint64_t e    = stop < hi ? stop : hi;
			out.push_back({vva + (lo - voff), e - lo});
			lo = e;
		}
	};
	for (const auto& b: bos) {
		if (b.off + b.size <= cur) continue;
		if (b.off >= vend) break;
		if (b.off > cur) emit(cur, b.off < vend ? b.off : vend);
		if (b.off + b.size > cur) cur = b.off + b.size;
		if (cur >= vend) break;
	}
	if (cur < vend) emit(cur, vend);
}
// The fault status' write bit, read off two kernel lines (E1 case 4: status 0x00741041, "RW: 0x1"; the play of
// 2026-11-13: 0x00601431, "RW: 0x0"): bit 18. TODO(verify) against the gfx10 register header; the raw status is
// always journaled beside it.
inline bool status_write(uint32_t status) { return (status & (1u << 18u)) != 0; }
} // namespace k1r412
