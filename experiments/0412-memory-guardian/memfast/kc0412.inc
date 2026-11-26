// BC5 experiment 0412 (tag kc412, README section 85): the cover -> data log. BC5_GUARD_COVER_LOG=1 (unset, empty or
// 0: off). A catcher: it changes no mapping.
// A K1r cover serves the GPU zeros where the title has never written. When the title writes such a chunk, the next
// mapping rebuild drops the cover and maps the real pages (k1r0412.inc). Between the write and that rebuild a GPU
// read still sees zeros. The k1r line of the journal is written at most every 10 s, so it cannot place such a
// moment beside a fault; this log writes one line for every rebuild in which a cover gave way to data.
// What became of a dropped cover piece is decided here, free of the host, and tested by kc0412.cpp.
namespace kc412 {
inline bool on() {
	static const bool v = [] {
		const char* e = std::getenv("BC5_GUARD_COVER_LOG");
		return e != nullptr && e[0] != 0 && !(e[0] == '0' && e[1] == 0);
	}();
	return v;
}
enum Kind : unsigned { kGone = 0, kData = 1, kCover = 2 };
// A cover piece [va, va + size) is being unmapped. want is the new list of mappings, sorted by va, its entries
// disjoint. kData: a mapping that is not a cover lies over some part of it (the title's data takes its place);
// kCover: only covers do (the piece was cut or joined); kGone: nothing does (its view went away).
template <typename Maps, typename IsCover> inline Kind after(uint64_t va, uint64_t size, const Maps& want, IsCover&& is_cover) {
	auto it = std::upper_bound(want.begin(), want.end(), va, [](uint64_t a, const auto& m) { return a < m.va; });
	if (it != want.begin()) --it;
	Kind k = kGone;
	for (; it != want.end() && it->va < va + size; ++it) {
		if (it->va + it->size <= va) continue;
		if (!is_cover(it->id)) return kData;
		k = kCover;
	}
	return k;
}
struct Tally {
	uint64_t n[3] = {0, 0, 0}, bytes[3] = {0, 0, 0};
	uint64_t first_data_va = 0;
	void     add(Kind k, uint64_t va, uint64_t size) {
		if (k == kData && n[kData] == 0) first_data_va = va;
		n[k]++;
		bytes[k] += size;
	}
};
} // namespace kc412
