#!/usr/bin/env python3
# Experiment 0157, twelfth step: BC5_DIRECT_PREFIX_ALL takes a mode: 1|all = the full-state prefix on every
# graphics buffer; draws = only on graphics buffers that draw; sx = on buffers that draw, a single
# SET_CONTEXT_REG of SX_PS_DOWNCONVERT..SX_MRT7_BLEND_OPT (ctx 0x1d5-0x1df, the RB+ blend optimisation
# registers; Mesa gfx10 register JSON) with the title's tracked values.
p = "/home/kjaniszewski/src/KytyPlus/src/libs/bc5LleAgc.cpp"
s = open(p, encoding="utf-8", newline="").read()


def rep(a, b, count=1):
    global s
    assert s.count(a) == count, (s.count(a), a[:80])
    s = s.replace(a, b)


rep("""// Experiment 0157: BC5_DIRECT_PREFIX_ALL=1, the full-state prefix in front of every graphics buffer.
static bool prefix_all() {
	static const bool v = std::getenv("BC5_DIRECT_PREFIX_ALL") != nullptr;
	return v;
}""",
    """// Experiment 0157: BC5_DIRECT_PREFIX_ALL: 1|all = the full-state prefix (as the pieces') in front of
// every graphics buffer; draws = in front of the graphics buffers that draw; sx = in front of those, a
// SET_CONTEXT_REG of SX_PS_DOWNCONVERT..SX_MRT7_BLEND_OPT (ctx 0x1d5-0x1df) alone, with the tracked values.
static int prefix_mode() {
	static const int v = [] {
		const char* e = std::getenv("BC5_DIRECT_PREFIX_ALL");
		if (e == nullptr || *e == 0 || std::strcmp(e, "0") == 0) return 0;
		if (std::strcmp(e, "draws") == 0) return 2;
		if (std::strcmp(e, "sx") == 0) return 3;
		return 1;
	}();
	return v;
}
static bool prefix_all() {
	return prefix_mode() != 0;
}
static bool ib_has_draw(const uint32_t* ib, uint32_t num_dwords) {
	for (uint32_t i = 0; i < num_dwords;) {
		const uint32_t h = ib[i], type = h >> 30u;
		uint32_t       len = 1;
		if (type == 3 || type == 0) { const uint32_t c = (h >> 16u) & 0x3fffu; len = c == 0x3fffu ? 1 : c + 2; }
		if (i + len > num_dwords) break;
		if (type == 3) {
			const uint32_t op = (h >> 8u) & 0xffu;
			if (op == 0x24 || op == 0x25 || op == 0x27 || op == 0x2c || op == 0x2d || op == 0x35 || op == 0x38) return true;
		}
		i += len;
	}
	return false;
}
static std::vector<uint32_t> sx_prefix(const bc5::full_state::Tracker& t) {
	std::vector<uint32_t> p;
	p.push_back(0xC0000000u | (11u << 16u) | (0x69u << 8u)); // SET_CONTEXT_REG, 12 body dwords
	p.push_back(0x1d5u);
	for (uint32_t o = 0x1d5u; o <= 0x1dfu; o++) {
		uint32_t v = 0;
		if (!t.get(bc5::full_state::Context, o, v)) return {};
		p.push_back(v);
	}
	return p;
}""")

rep("""	if (prefix_all() && std::strcmp(kind, "dcb") == 0 && g_stage != Stage::MapOnly) { // experiment 0157
		full_prefix = prefix_of(t_fs_before);
		full_used   = !full_prefix.empty();
	}""",
    """	if (prefix_all() && std::strcmp(kind, "dcb") == 0 && g_stage != Stage::MapOnly && (prefix_mode() == 1 || ib_has_draw(ib, num_dwords))) { // experiment 0157
		full_prefix = prefix_mode() == 3 ? sx_prefix(t_fs_before) : prefix_of(t_fs_before);
		full_used   = !full_prefix.empty();
	}""")

open(p, "w", encoding="utf-8", newline="").write(s)
print("ok")
