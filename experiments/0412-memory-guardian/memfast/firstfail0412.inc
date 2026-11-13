// BC5 experiment 0412 (tag ff412, README sections 57 and 59): which host memory call fails first when the title is
// offered less memory. KYTY_BC5_MEM_FIRSTFAIL=1 (unset, empty or 0: off; one test of a constant on a path that has
// already failed). A catcher: it changes no result.
//   - every wrapped memory call that returns an error is counted per call; the first kFull failures and then every
//     failure whose number is a power of two are written in full (the call, its result, up to six arguments, the
//     caller's address, the thread) with the state of the direct memory at that moment;
//   - the last kRing failures are kept and printed again when the host is about to die on an access to a reserved
//     AMM page (the exit "AMM virtual-memory unmap is unsupported"), so the death is tied to what failed before it.
// The decisions (when to print, the ring) are here, free of the host, and tested by firstfail0412.cpp; the host's part
// (wrappers, the state line) is pasted by mkff0412.py.
namespace ff412 {
static constexpr uint64_t kFull = 12;
static constexpr unsigned kRing = 8;
struct Fail {
	const char* call = "";
	int         result = 0;
	uint64_t    n = 0; // its number among all failures, from 1
	uint64_t    a[6] = {0, 0, 0, 0, 0, 0};
	unsigned    args = 0;
};
// Is the n-th failure (from 1) written in full?
inline bool full(uint64_t n) { return n != 0 && (n <= kFull || (n & (n - 1)) == 0); }
struct Ring {
	Fail     e[kRing];
	uint64_t count = 0;
	void     push(const Fail& f) { e[count++ % kRing] = f; }
	// The kept failures, oldest first.
	unsigned list(const Fail** out) const {
		const unsigned n = count < kRing ? static_cast<unsigned>(count) : kRing;
		for (unsigned i = 0; i < n; i++) out[i] = &e[(count - n + i) % kRing];
		return n;
	}
};
inline bool on() {
	static const bool v = [] {
		const char* e = std::getenv("KYTY_BC5_MEM_FIRSTFAIL");
		return e != nullptr && e[0] != 0 && !(e[0] == '0' && e[1] == 0);
	}();
	return v;
}
template <class T> inline uint64_t u(T v) {
	if constexpr (std::is_pointer_v<T>) return reinterpret_cast<uint64_t>(v);
	else return static_cast<uint64_t>(v);
}
} // namespace ff412
