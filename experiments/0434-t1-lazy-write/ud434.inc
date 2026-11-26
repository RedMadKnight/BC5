// Experiment 0434 (tag ud434), built in with no switch: a buffer descriptor (V#) written into a shader stage's user-data
// registers by SET_SH_REG names memory the shader reads or WRITES; under a view of direct memory that is not imported it
// is imported before the submit, as k1f412 does for a packet's own operands. The first title, that level's load
// (fault records 20261119-140627/-140758/-141432): COMPUTE_USER_DATA_4..7 held a V# of 16 bytes at 0x314cb62dc in a
// never-written chunk of the lazy heap orbis_user_malloc; the dispatch's store hit K1r's read-only cover (TCP, RW 1).
// The maintainer, 2026-11-19, after his test on a later level: approval to deploy; no switch.
namespace ud434 {
constexpr uint64_t kMaxSpan = 256ull << 20u; // a descriptor that claims more is cut to this
// The first user-data register of the stage that register r belongs to, or ~0u: PS, VS, GS, ES, HS, LS (32 each,
// SH offsets as in dt412::user_reg) and compute (COMPUTE_USER_DATA_0..15 at 0x240).
inline uint32_t stage_base(uint32_t r) {
	for (uint32_t b: {0x0cu, 0x4cu, 0x8cu, 0xccu, 0x10cu, 0x14cu}) {
		if (r >= b && r < b + 32u) return b;
	}
	return (r >= 0x240u && r < 0x250u) ? 0x240u : ~0u;
}
// One SET_SH_REG (0x76) or SET_SH_REG_INDEX (0x9b) packet of len dwords: every V# in it that starts at a user-data
// register 4-aligned to its stage's first one (a descriptor sits in an aligned SGPR quad; every stage's user data is a
// multiple of 4 registers, so such a quad never crosses its end): found(address, bytes). A V#: dword 3 TYPE (bits 31:30) 0, base dword 0 + dword 1 bits 15:0, a
// non-zero base below 2^40; bytes = stride * num_records, or num_records when the stride is 0; empty ones skipped.
template <typename F> inline void scan(const uint32_t* p, uint32_t len, F&& found) {
	if (len < 3 || (p[0] >> 30u) != 3) return;
	const uint32_t op = (p[0] >> 8u) & 0xffu;
	if (op != 0x76u && op != 0x9bu) return;
	const uint32_t reg0 = p[1] & 0xffffu, count = len - 2;
	for (uint32_t k = 0; k + 4 <= count; k++) {
		const uint32_t r = reg0 + k, b = stage_base(r);
		if (b == ~0u || ((r - b) & 3u) != 0) continue;
		const uint32_t w0 = p[2 + k], w1 = p[3 + k], w2 = p[4 + k], w3 = p[5 + k];
		if ((w3 >> 30u) != 0) continue;
		const uint64_t a = static_cast<uint64_t>(w0) | (static_cast<uint64_t>(w1 & 0xffffu) << 32u);
		if (a == 0 || (a >> 40u) != 0) continue;
		const uint64_t stride = (w1 >> 16u) & 0x3fffu;
		uint64_t       bytes  = stride != 0 ? stride * w2 : static_cast<uint64_t>(w2);
		if (bytes == 0) continue;
		if (bytes > kMaxSpan) bytes = kMaxSpan;
		found(a, bytes);
	}
}
} // namespace ud434
