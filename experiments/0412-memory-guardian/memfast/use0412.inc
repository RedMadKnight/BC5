// BC5 experiment 0412 (tag us412, README section 32): how much of the pinned guest memory do submitted command
// buffers name? BC5_GUARD_USE_STAT=1 (default off: touch() and report() return after one test of a constant).
// touch(addr, bytes) is called for every memory operand the backend's filter asks about at submission (the same
// callback that decides whether a packet is kept); it stamps the 2 MiB chunks of guest address space the operand lies
// in. report(label, views) runs in the direct sync every 30 s and prints, per heap name of the views, the MiB under
// views, and of them the MiB in chunks that an operand named ever / in the last 60 s / 10 s / 1 s.
// LIMIT, to be read with every number: an operand is an address written in a command buffer or in a register table
// it loads. Memory that only shaders reach, through descriptors and pointers they read from other memory (textures,
// most buffers), is NOT seen here, so "named" is a lower bound of what the GPU touches.
// Build g412r: when the views carry the title's protection bits (DView::prot, mkprot0412.py), each heap's line also
// gives the MiB whose bits include GPU read (0x10) or GPU write (0x20) and the MiB with neither, and the bit
// patterns seen.
// Both functions are called with the device mutex held. No behaviour changes.
namespace us412 {
static constexpr uint64_t kChunk = 2ull << 20;
inline bool on() {
	static const bool v = [] {
		const char* e = std::getenv("BC5_GUARD_USE_STAT");
		return e != nullptr && e[0] != 0 && !(e[0] == '0' && e[1] == 0);
	}();
	return v;
}
inline uint64_t now_ns() {
	timespec ts {};
	clock_gettime(CLOCK_MONOTONIC, &ts);
	return static_cast<uint64_t>(ts.tv_sec) * 1000000000ull + static_cast<uint64_t>(ts.tv_nsec);
}
inline std::unordered_map<uint64_t, uint64_t>& last() { // chunk index -> the last time an operand named it
	static std::unordered_map<uint64_t, uint64_t> m;
	return m;
}
inline uint64_t g_now = 0, g_operands = 0; // the submission's time, set once per submission by begin()
inline void begin() {
	if (on()) g_now = now_ns();
}
inline void touch(uint64_t addr, uint64_t bytes) {
	if (!on()) return;
	g_operands++;
	if (bytes == 0) bytes = 4;
	if (bytes > (64ull << 20)) bytes = 64ull << 20; // an absurd length does not paint the address space
	auto& m = last();
	for (uint64_t c = addr / kChunk; c <= (addr + bytes - 1) / kChunk; c++) m[c] = g_now;
}
template <typename Views> inline void report(const char* label, const Views& views) {
	if (!on()) return;
	static uint64_t next = 0;
	const uint64_t  now  = now_ns();
	if (now < next) return;
	next = now + 30000000000ull;
	struct Row {
		uint64_t all = 0, ever = 0, s60 = 0, s10 = 0, s1 = 0, gpu = 0, nogpu = 0;
		std::map<int, uint64_t> prots;
	};
	std::map<std::string, Row> rows;
	Row                        tot;
	const auto&                m = last();
	for (const auto& v: views) {
		Row& r = rows[std::string(v.name).empty() ? std::string("(no name)") : std::string(v.name)];
		const int pr = v.prot;
		r.prots[pr] += v.size;
		if ((pr & 0x30) != 0) { r.gpu += v.size; tot.gpu += v.size; } else { r.nogpu += v.size; tot.nogpu += v.size; }
		for (uint64_t a = v.va; a < v.va + v.size;) {
			const uint64_t c    = a / kChunk;
			const uint64_t end  = (c + 1) * kChunk < v.va + v.size ? (c + 1) * kChunk : v.va + v.size;
			const uint64_t part = end - a;
			r.all += part;
			tot.all += part;
			const auto it = m.find(c);
			if (it != m.end()) {
				const uint64_t age = now - it->second;
				r.ever += part;
				tot.ever += part;
				if (age <= 60000000000ull) { r.s60 += part; tot.s60 += part; }
				if (age <= 10000000000ull) { r.s10 += part; tot.s10 += part; }
				if (age <= 1000000000ull) { r.s1 += part; tot.s1 += part; }
			}
			a = end;
		}
	}
	std::vector<std::pair<uint64_t, std::string>> order;
	for (const auto& kv: rows) order.push_back({kv.second.all, kv.first});
	std::sort(order.begin(), order.end(), [](const auto& x, const auto& y) { return x.first > y.first; });
	const double mib = 1048576.0;
	US412_PRINT("use stat (exp 0412, tag us412): %s: t %.0f s: by the title's protection bits: %.0f MiB with a GPU bit (0x10 read, 0x20 write), %.0f MiB with none\n", label, US412_NOW(),
	            static_cast<double>(tot.gpu) / mib, static_cast<double>(tot.nogpu) / mib);
	US412_PRINT("use stat (exp 0412, tag us412): %s: t %.0f s: under views %.0f MiB; in chunks an operand named: ever %.0f, last 60 s %.0f, last 10 s %.0f, last 1 s %.0f MiB; %zu chunks named, %" PRIu64 " operands so far\n",
	            label, US412_NOW(), static_cast<double>(tot.all) / mib, static_cast<double>(tot.ever) / mib, static_cast<double>(tot.s60) / mib, static_cast<double>(tot.s10) / mib,
	            static_cast<double>(tot.s1) / mib, m.size(), g_operands);
	size_t k = 0;
	for (const auto& o: order) {
		if (k++ >= 14 || o.first < (16ull << 20)) break;
		const Row& r = rows[o.second];
		char pt[160] = {};
		int  pw      = 0;
		for (const auto& kv: r.prots) {
			if (pw < 130) pw += std::snprintf(pt + pw, sizeof(pt) - static_cast<size_t>(pw), " 0x%x:%.0f", static_cast<unsigned>(kv.first), static_cast<double>(kv.second) / mib);
		}
		US412_PRINT("use stat (exp 0412, tag us412): %s:   %-28s under views %7.0f MiB; named ever %7.0f, 60 s %7.0f, 10 s %7.0f, 1 s %7.0f; GPU bit %7.0f, none %7.0f; prot:MiB%s\n", label, o.second.c_str(),
		            static_cast<double>(r.all) / mib, static_cast<double>(r.ever) / mib, static_cast<double>(r.s60) / mib, static_cast<double>(r.s10) / mib, static_cast<double>(r.s1) / mib,
		            static_cast<double>(r.gpu) / mib, static_cast<double>(r.nogpu) / mib, pt);
	}
}
} // namespace us412
