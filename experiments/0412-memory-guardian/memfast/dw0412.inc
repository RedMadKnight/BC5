// BC5 experiment 0412 (tags tl412, dc412; README section 89): the dispatches of a command buffer, for two catchers.
//   BC5_TIMEOUT_LAYOUT=1 (tl412): at a timeout, BEFORE the long probe, one file with every dispatch of the timed-out
//     buffer (program, initiator, groups, user data) and, for every address its user data may hold, the view it
//     lies in; written and fsync'd first, because on 2026-11-14 the kernel was crashed 0.2 s after the timeout
//     (arm n8F8) and no fault record was made.
//   BC5_DISPATCH_COUNT=1 (dc412): how often each compute program is dispatched (by program, initiator and kind),
//     so that "is this a rare kind of work" has a number in a clean run.
// Both unset, empty or 0: off. Catchers only: nothing here changes a buffer, a mapping or a result.
// Packet layout as the host's timeout probe reads it (experiments 0160, 0260, 0272) and Mesa's
// src/amd/common/sid.h (94ad3c5e): PKT3 header = type 3 in bits 30-31, count in 16-29, opcode in 8-15;
// SET_SH_REG 0x76, LOAD_SH_REG_INDEX 0x63, SET_BASE 0x11, DISPATCH_DIRECT 0x15, DISPATCH_INDIRECT 0x16;
// registers by Mesa's src/amd/registers/gfx10.json: SH 0x20c/0x20d COMPUTE_PGM_LO/HI, 0x240.. COMPUTE_USER_DATA_0..15;
// COMPUTE_DISPATCH_INITIATOR bit 15 CS_W32_EN.
// The walk and the counter are here, free of the host, and tested by dw0412.cpp.
namespace dw412 {
inline bool env_on(const char* name) {
	const char* e = std::getenv(name);
	return e != nullptr && e[0] != 0 && !(e[0] == '0' && e[1] == 0);
}
inline bool tl_on() {
	static const bool v = env_on("BC5_TIMEOUT_LAYOUT");
	return v;
}
inline bool dc_on() {
	static const bool v = env_on("BC5_DISPATCH_COUNT");
	return v;
}
struct Dispatch {
	uint32_t at = 0;            // dword offset of the packet
	uint32_t op = 0;            // 0x15 direct, 0x16 indirect
	uint64_t program = 0;       // (COMPUTE_PGM_LO | (HI & 0xff) << 32) << 8
	bool     program_known = false; // both registers were set in this buffer (by SET_SH_REG or a loaded table)
	uint32_t initiator = 0;
	uint32_t gx = 0, gy = 0, gz = 0;
	bool     groups_known = false; // direct only: the indirect form's counts are in memory
	uint64_t args = 0;          // indirect: the address of the counts (0 when the base is not known)
	uint32_t ud[16] = {};
	uint32_t ud_known = 0;      // bit k: COMPUTE_USER_DATA_k was set in this buffer
};
// Total dwords of the packet at ib[i] (never 0), by its header.
inline uint32_t packet_len(uint32_t h) {
	const uint32_t type = h >> 30u, cnt = (h >> 16u) & 0x3fffu;
	if (type == 3) return cnt == 0x3fffu ? 1u : cnt + 2u;
	if (type == 0) return cnt + 2u;
	return 1u;
}
// read_table(address, pairs, out): fills out with 2 * pairs dwords (register, value) and returns true, or returns
// false when the memory cannot be read. on_dispatch(const Dispatch&) for every dispatch, in order.
// A packet that would run past the end stops the walk (returns false); true when the whole buffer was walked.
template <typename R, typename F> inline bool walk(const uint32_t* ib, uint32_t n, R&& read_table, F&& on_dispatch) {
	uint32_t pl = 0, ph = 0;
	bool     pl_known = false, ph_known = false;
	uint32_t ud[16] = {};
	uint32_t ud_known = 0;
	uint64_t base1 = 0;
	std::vector<uint32_t> table;
	auto set = [&](uint32_t reg, uint32_t v) {
		if (reg == 0x20cu) pl = v, pl_known = true;
		else if (reg == 0x20du) ph = v, ph_known = true;
		else if (reg >= 0x240u && reg < 0x250u) ud[reg - 0x240u] = v, ud_known |= 1u << (reg - 0x240u);
	};
	for (uint32_t i = 0; i < n;) {
		const uint32_t h = ib[i], len = packet_len(h);
		if (len > n - i) return false;
		if ((h >> 30u) == 3 && len >= 2) {
			const uint32_t op = (h >> 8u) & 0xffu;
			if (op == 0x76u && len >= 3) {
				const uint32_t reg = ib[i + 1] & 0xffffu;
				for (uint32_t k = 2; k < len; k++) set(reg + (k - 2), ib[i + k]);
			} else if (op == 0x63u && len >= 5 && (ib[i + 3] >> 31u) != 0) {
				const uint64_t ta = (ib[i + 1] & ~3u) | (static_cast<uint64_t>(ib[i + 2] & 0xffffu) << 32u);
				const uint32_t tn = ib[i + 4] & 0x3fffu;
				if (ta != 0 && tn != 0 && tn <= 4096) {
					table.clear();
					if (read_table(ta, tn, table) && table.size() >= 2ull * tn) {
						for (uint32_t k = 0; k < tn; k++) set(table[2 * k] & 0xffffu, table[2 * k + 1]);
					}
				}
			} else if (op == 0x11u && len >= 4 && (ib[i + 1] & 0xfu) == 1) {
				base1 = (ib[i + 2] & ~3u) | (static_cast<uint64_t>(ib[i + 3] & 0xffffu) << 32u);
			} else if ((op == 0x15u && len >= 5) || (op == 0x16u && len >= 3)) {
				Dispatch d;
				d.at            = i;
				d.op            = op;
				d.program_known = pl_known && ph_known;
				d.program       = (static_cast<uint64_t>(pl) | (static_cast<uint64_t>(ph & 0xffu) << 32u)) << 8u;
				std::memcpy(d.ud, ud, sizeof(ud));
				d.ud_known = ud_known;
				if (op == 0x15u) {
					d.gx = ib[i + 1], d.gy = ib[i + 2], d.gz = ib[i + 3], d.groups_known = true;
					d.initiator = ib[i + 4];
				} else if (len >= 4) {
					d.args      = (ib[i + 1] & ~3u) | (static_cast<uint64_t>(ib[i + 2] & 0xffffu) << 32u);
					d.initiator = ib[i + 3];
				} else {
					d.args      = base1 != 0 ? base1 + ib[i + 1] : 0;
					d.initiator = ib[i + 2];
				}
				on_dispatch(static_cast<const Dispatch&>(d));
			}
		}
		i += len;
	}
	return true;
}
// The addresses a dispatch's user data may hold. A buffer descriptor has the base's low 32 bits in one dword and
// bits 32-39 in the low byte of the next (form 'b'); a texture descriptor has the base >> 8 in its first dword
// (form 't'). Both readings of every known dword are given; the caller keeps those that lie under a view.
// hit(k, form, address).
template <typename F> inline void candidates(const Dispatch& d, F&& hit) {
	for (uint32_t k = 0; k < 16; k++) {
		if ((d.ud_known & (1u << k)) == 0) continue;
		if (k + 1 < 16 && (d.ud_known & (1u << (k + 1))) != 0) {
			const uint64_t a = static_cast<uint64_t>(d.ud[k]) | (static_cast<uint64_t>(d.ud[k + 1] & 0xffu) << 32u);
			if ((d.ud[k + 1] & 0xffu) != 0) hit(k, 'b', a);
		}
		const uint64_t t = static_cast<uint64_t>(d.ud[k]) << 8u;
		if ((t >> 32u) != 0) hit(k, 't', t);
	}
}
struct Key {
	uint64_t program;
	uint32_t initiator;
	uint32_t op;
	bool     operator<(const Key& o) const { return std::tie(program, initiator, op) < std::tie(o.program, o.initiator, o.op); }
};
struct Val {
	uint64_t n = 0, groups = 0;
	double   first_t = 0, last_t = 0;
};
struct Counter {
	std::map<Key, Val> m;
	uint64_t           dispatches = 0, unknown_program = 0;
	void               add(const Dispatch& d, double t) {
		dispatches++;
		if (!d.program_known) unknown_program++;
		Val& v = m[Key {d.program_known ? d.program : 0, d.initiator, d.op}];
		if (v.n++ == 0) v.first_t = t;
		v.last_t = t;
		if (d.groups_known) v.groups += static_cast<uint64_t>(d.gx) * d.gy * d.gz;
	}
	uint64_t seen(const Dispatch& d) const {
		const auto it = m.find(Key {d.program_known ? d.program : 0, d.initiator, d.op});
		return it == m.end() ? 0 : it->second.n;
	}
	// The rarest first (those are the question), at most `most` lines. line(key, val).
	template <typename F> void report(size_t most, F&& line) const {
		std::vector<std::pair<Key, Val>> v(m.begin(), m.end());
		std::stable_sort(v.begin(), v.end(), [](const auto& a, const auto& b) { return a.second.n < b.second.n; });
		for (size_t i = 0; i < v.size() && i < most; i++) line(v[i].first, v[i].second);
	}
};
} // namespace dw412
