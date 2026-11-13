// BC5 experiment 0412 (tag wc412): the writers catcher tells a CPU write from a GPU write. Log only.
// BC5_GUARD_WRITERS=2 (1 is the catcher of tag ww412 alone; default off). Linux's soft-dirty bit (bit 55 of a
// /proc/self/pagemap entry; Documentation/admin-guide/mm/soft-dirty.rst) is set when the process writes a page
// through its page tables, and "4" written to /proc/self/clear_refs clears it for the whole process. A write the GPU
// makes does not go through the process's page tables and leaves the bit alone. So, for a chunk that was all zero at
// the last scan and holds data now:
//   a soft-dirty page at ANY address that maps the chunk  -> the CPU wrote it (a GPU write as well is not excluded)
//   none                                                  -> no CPU write: a GPU writer
// Order in a scan, so that no CPU write is missed: (1) read the bits of every chunk that was zero at the last scan,
// (2) clear, (3) the scan reads the file, (4) read the bits again for the chunks that turned. A CPU write is in (1)
// when it came before the clear and in (4) when it came after.
// Costs, why this is a diagnostic value of its own: the clear write-protects every page of the process (each page
// then takes one minor fault at its next write), and it walks all page tables once per scan. The gaps and flips/s of
// an arm run with =2 are not comparable with other arms.
// Limits: the list of mappings is read once per scan (/proc/self/maps); a mapping made after that is not looked at. A
// write the KERNEL makes into the file without the process's page tables (a write() to the memfd) sets no bit.
// The parsing and the address arithmetic are here, free of the host, and tested by wc0412.cpp.
namespace wc412 {
inline int level() { // 0 off, 1 the catcher, 2 the catcher with the CPU/GPU split
	static const int v = [] {
		const char* e = std::getenv("BC5_GUARD_WRITERS");
		if (e == nullptr || e[0] == 0 || (e[0] == '0' && e[1] == 0)) return 0;
		return e[0] == '2' && e[1] == 0 ? 2 : 1;
	}();
	return v;
}
struct MapLine {
	uint64_t va = 0, len = 0, off = 0; // a mapping of the file: [va, va + len) shows the file from off
};
// The lines of /proc/self/maps that map the file with this device and inode ("start-end perms offset maj:min inode path").
inline std::vector<MapLine> parse_maps(const std::string& text, unsigned maj, unsigned min, uint64_t ino) {
	std::vector<MapLine> out;
	size_t               pos = 0;
	while (pos < text.size()) {
		size_t nl = text.find('\n', pos);
		if (nl == std::string::npos) nl = text.size();
		const std::string  line = text.substr(pos, nl - pos);
		pos                     = nl + 1;
		unsigned long long a = 0, b = 0, off = 0, i = 0;
		unsigned           ma = 0, mi = 0;
		char               perms[8] = {};
		if (std::sscanf(line.c_str(), "%llx-%llx %7s %llx %x:%x %llu", &a, &b, perms, &off, &ma, &mi, &i) != 7) continue;
		if (ma != maj || mi != min || i != ino || b <= a) continue;
		out.push_back({a, b - a, off});
	}
	return out;
}
// Every address range that shows a part of the file range [off, off + len): f(va, bytes).
template <typename F> inline void for_va(const std::vector<MapLine>& maps, uint64_t off, uint64_t len, F&& f) {
	for (const auto& m: maps) {
		const uint64_t lo = off > m.off ? off : m.off;
		const uint64_t hi = off + len < m.off + m.len ? off + len : m.off + m.len;
		if (lo < hi) f(m.va + (lo - m.off), hi - lo);
	}
}
inline bool any_soft_dirty(const uint64_t* entries, size_t n) {
	for (size_t i = 0; i < n; i++) {
		if (((entries[i] >> 55u) & 1u) != 0) return true;
	}
	return false;
}
} // namespace wc412
