// BC5 experiment 0412 (tag ph412, README section 86): who holds a pointer to the faulted chunk. BC5_FAULT_POINTERS=1
// (unset, empty or 0: off). A catcher for the fault record; it runs once, when the game is being ended anyway.
// Arm b1 of 2026-11-14 (CommitIABufferAllocator imported by data) ended in a GPU WRITE under the read-only cover. The
// writer was a shader's own store (client TCP): its target came from a buffer descriptor the shader was given, not
// from a packet operand, so nothing in the journal names the job. What can still be read at that moment is the
// title's memory: every place that holds an address inside the faulted 2 MiB chunk is a candidate descriptor (or
// a plain pointer), and the heap it lies in says who owns the table.
// The search of a block of bytes is here, free of the host, and tested by ph0412.cpp.
namespace ph412 {
inline bool on() {
	static const bool v = [] {
		const char* e = std::getenv("BC5_FAULT_POINTERS");
		return e != nullptr && e[0] != 0 && !(e[0] == '0' && e[1] == 0);
	}();
	return v;
}
constexpr uint64_t kMask40 = (1ull << 40u) - 1;
// Every position p (a multiple of 4) of the block with p + 8 <= n whose 64-bit little-endian word has its low 40
// bits in [lo, hi): hit(p, word). A buffer descriptor keeps other fields above bit 40, a plain pointer keeps zero
// there; the caller is given the whole word and can tell. Words that straddle the block's end are not seen.
template <typename F> inline void scan(const uint8_t* p, size_t n, uint64_t lo, uint64_t hi, F&& hit) {
	if (n < 8) return;
	for (size_t i = 0; i + 8 <= n; i += 4) {
		uint64_t w;
		std::memcpy(&w, p + i, 8);
		const uint64_t a = w & kMask40;
		if (a >= lo && a < hi) hit(i, w);
	}
}
inline bool plain(uint64_t w) { return (w >> 40u) == 0; }
} // namespace ph412
