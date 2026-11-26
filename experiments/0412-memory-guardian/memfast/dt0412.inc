// BC5 experiment 0412 (tag dt412, README section 94): the buffers a shader is given through user data.
//   BC5_GUARD_DESC_TARGETS=1  before a command buffer is submitted, every buffer its shaders are given by a
//                             descriptor or a pointer in user data is imported (the host's direct_force), so a
//                             shader's store through such a descriptor never meets the read-only zero cover.
//   BC5_GUARD_DESC_TARGETS=2  log only: the same walk, nothing imported; the journal says how many of those
//                             buffers lay under a cover or were not mapped, and how many MiB the import would add.
//   unset, empty or 0: off.
// Why: arm b1 of 2026-11-14 (CommitIABufferAllocator imported by data; README section 85) ended in a GPU WRITE
// under the cover at 0x121a807000. The writer was a shader's own store: its target came from a descriptor in user
// data, not from a packet operand, and the host names only packet operands and render targets. A descriptor does
// not say whether the shader reads or writes, so all of them are taken; mode 2 gives the price.
// Layouts: PKT3 header as in dw0412.inc; SET_SH_REG 0x76, SET_SH_REG_INDEX 0x9B, LOAD_SH_REG_INDEX 0x63 (Mesa
// src/amd/common/sid.h, 94ad3c5e). User-data registers as SH offsets (Mesa src/amd/registers/gfx10.json, 94ad3c5e:
// SPI_SHADER_USER_DATA_PS_0 0xb030, VS_0 0xb130, GS_0 0xb230, ES_0 0xb330, HS_0 0xb430, LS_0 0xb530, 32 each;
// COMPUTE_USER_DATA_0 0xb900, 16): 0x0c, 0x4c, 0x8c, 0xcc, 0x10c, 0x14c, 0x240.
// A buffer descriptor (README section 89, read from arm n8F8's own buffer: a5ae8000 03000011 00000800 = base
// 0x11a5ae8000, stride 0x300, 0x800 records): dword 0 the base's low 32 bits; dword 1 bits 0-7 the base's bits
// 32-39, bits 16-29 the stride; dword 2 the number of records. A plain pointer has only bits 0-7 set in dword 1.
// The walk is here, free of the host, and tested by dt0412.cpp.
namespace dt412 {
inline int mode() {
	static const int v = [] {
		const char* e = std::getenv("BC5_GUARD_DESC_TARGETS");
		if (e == nullptr || e[0] == 0 || (e[0] == '0' && e[1] == 0)) return 0;
		return (e[0] == '2' && e[1] == 0) ? 2 : 1;
	}();
	return v;
}
constexpr uint64_t kMaxSpan  = 256ull << 20u; // a descriptor that claims more is cut to this
constexpr uint32_t kTableDws = 64;            // dwords read at a plain pointer (16 descriptors)
inline bool user_reg(uint32_t r) {
	for (uint32_t b: {0x0cu, 0x4cu, 0x8cu, 0xccu, 0x10cu, 0x14cu}) {
		if (r >= b && r < b + 32u) return true;
	}
	return r >= 0x240u && r < 0x250u;
}
// The address a pair of dwords may hold and the bytes it spans: found(address, bytes, plain). bytes is 0 for a
// plain pointer (the length is not known). w2_known: a third dword follows (the record count).
template <typename F> inline void pair(uint32_t w0, uint32_t w1, bool w2_known, uint32_t w2, F&& found) {
	if ((w1 & 0xffu) == 0) return;
	const uint64_t a = static_cast<uint64_t>(w0) | (static_cast<uint64_t>(w1 & 0xffu) << 32u);
	if ((w1 >> 8u) == 0) {
		found(a, static_cast<uint64_t>(0), true);
		return;
	}
	const uint64_t stride = (w1 >> 16u) & 0x3fffu;
	uint64_t       bytes  = w2_known ? (stride != 0 ? stride * w2 : static_cast<uint64_t>(w2)) : 0;
	if (bytes > kMaxSpan) bytes = kMaxSpan;
	found(a, bytes, false);
}
// Every pair of a block of dwords (a table a pointer leads to): found(position, address, bytes, plain).
template <typename F> inline void block(const uint32_t* w, uint32_t n, F&& found) {
	for (uint32_t k = 0; k + 1 < n; k++) {
		pair(w[k], w[k + 1], k + 2 < n, k + 2 < n ? w[k + 2] : 0u, [&](uint64_t a, uint64_t bytes, bool plain) { found(k, a, bytes, plain); });
	}
}
// The user data a command buffer sets, by SET_SH_REG, SET_SH_REG_INDEX or a loaded table: found(register, address,
// bytes, plain) for every pair of neighbouring user-data registers. read_table as in dw0412.inc. Returns false
// when a packet runs past the end (the walk stops there).
template <typename R, typename F> inline bool walk(const uint32_t* ib, uint32_t n, R&& read_table, F&& found) {
	std::vector<std::pair<uint32_t, uint32_t>> set; // (register, value) of one packet, in order
	std::vector<uint32_t>                      table;
	auto                                       flush = [&]() {
        for (size_t k = 0; k + 1 < set.size(); k++) {
            if (!user_reg(set[k].first) || set[k + 1].first != set[k].first + 1 || !user_reg(set[k + 1].first)) continue;
            const bool w2 = k + 2 < set.size() && set[k + 2].first == set[k].first + 2 && user_reg(set[k + 2].first);
            pair(set[k].second, set[k + 1].second, w2, w2 ? set[k + 2].second : 0u, [&](uint64_t a, uint64_t bytes, bool plain) { found(set[k].first, a, bytes, plain); });
        }
        set.clear();
	};
	for (uint32_t i = 0; i < n;) {
		const uint32_t h   = ib[i];
		const uint32_t typ = h >> 30u, cnt = (h >> 16u) & 0x3fffu;
		const uint32_t len = typ == 3 ? (cnt == 0x3fffu ? 1u : cnt + 2u) : (typ == 0 ? cnt + 2u : 1u);
		if (len > n - i) return false;
		if (typ == 3 && len >= 3) {
			const uint32_t op = (h >> 8u) & 0xffu;
			if (op == 0x76u || op == 0x9bu) {
				const uint32_t reg = ib[i + 1] & 0xffffu;
				for (uint32_t k = 2; k < len; k++) set.emplace_back(reg + (k - 2), ib[i + k]);
				flush();
			} else if (op == 0x63u && len >= 5 && (ib[i + 3] >> 31u) != 0) {
				const uint64_t ta = (ib[i + 1] & ~3u) | (static_cast<uint64_t>(ib[i + 2] & 0xffffu) << 32u);
				const uint32_t tn = ib[i + 4] & 0x3fffu;
				table.clear();
				if (ta != 0 && tn != 0 && tn <= 4096 && read_table(ta, tn, table) && table.size() >= 2ull * tn) {
					for (uint32_t k = 0; k < tn; k++) set.emplace_back(table[2 * k] & 0xffffu, table[2 * k + 1]);
					flush();
				}
			}
		}
		i += len;
	}
	return true;
}
// What was done lately, so that the same buffer bound in every dispatch of a frame costs one lookup. key(address,
// bytes) -> the time it was last handled; fresh() is true (and nothing is to do) within `keep` seconds of that.
struct Recent {
	std::unordered_map<uint64_t, double> m;
	bool                                 fresh(uint64_t a, uint64_t bytes, double now, double keep = 1.0) {
        if (m.size() > 65536) m.clear();
        const uint64_t k  = a ^ (bytes * 0x9e3779b97f4a7c15ull);
        auto           it = m.find(k);
        if (it != m.end() && now - it->second < keep && now >= it->second) return true;
        m[k] = now;
        return false;
	}
};
} // namespace dt412
