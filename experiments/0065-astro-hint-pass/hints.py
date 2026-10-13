p = "/home/kjaniszewski/src/KytyPlus/src/libs/bc5LleAgc.cpp"
s = open(p, encoding="utf-8", newline="").read()
nl = "\r\n" if "\r\n" in s else "\n"


def rep(a, b, count=1):
    global s
    a = a.replace("\n", nl)
    b = b.replace("\n", nl)
    assert s.count(a) == count, (a[:80], s.count(a))
    s = s.replace(a, b)


# 1. the context registers the hint pass follows: a flat table instead of a std::map
rep("""static std::mutex                      g_size_mutex;
static std::map<std::string, uint64_t> g_size_counts;
static void size_tally(const std::map<uint32_t, uint32_t>& ctx) {
	static const bool on = std::getenv("BC5_DIRECT_PKT_STATS") != nullptr;
	if (!on) return;
	char k[160];
	auto get = [&](uint32_t r) { auto it = ctx.find(r); return it == ctx.end() ? 0xffffffffu : it->second; };""",
    """static std::mutex                      g_size_mutex;
static std::map<std::string, uint64_t> g_size_counts;
// Experiment 0065: the context registers hint_targets() follows, by offset from 0xa000 — a flat
// table (the std::map it replaces was looked up ~100 times after every change of a target).
struct HintCtx {
	std::vector<uint32_t> value = std::vector<uint32_t>(0x10000, 0);
	std::vector<uint8_t>  known = std::vector<uint8_t>(0x10000, 0);
	bool     has(uint32_t r) const { return known[r & 0xffffu] != 0; }
	uint32_t get(uint32_t r) const { return value[r & 0xffffu]; }
	void     set(uint32_t r, uint32_t v) {
		value[r & 0xffffu] = v;
		known[r & 0xffffu] = 1;
	}
};
static void size_tally(const HintCtx& ctx) {
	static const bool on = std::getenv("BC5_DIRECT_PKT_STATS") != nullptr;
	if (!on) return;
	char k[160];
	auto get = [&](uint32_t r) { return ctx.has(r) ? ctx.get(r) : 0xffffffffu; };""")

rep("""static void main_pass_track(const std::map<uint32_t, uint32_t>& ctx) {
	auto it_c = ctx.find(0x3b0);
	auto it_d = ctx.find(0x07);
	if (it_c == ctx.end() || it_d == ctx.end()) return;
	const uint32_t cw = ((it_c->second >> 14u) & 0x3fffu) + 1, ch = (it_c->second & 0x3fffu) + 1;
	const uint32_t dw = (it_d->second & 0x3fffu) + 1, dh = ((it_d->second >> 16u) & 0x3fffu) + 1;""",
    """static void main_pass_track(const HintCtx& ctx) {
	if (!ctx.has(0x3b0) || !ctx.has(0x07)) return;
	const uint32_t c = ctx.get(0x3b0), d = ctx.get(0x07);
	const uint32_t cw = ((c >> 14u) & 0x3fffu) + 1, ch = (c & 0x3fffu) + 1;
	const uint32_t dw = (d & 0x3fffu) + 1, dh = ((d >> 16u) & 0x3fffu) + 1;""")

# 2. hint_targets: sorted mappings, flat context, evaluate on a base change only
rep("""	if (off || !g_dev) return;
	std::vector<bc5::direct::Mapping> have = g_dev->mappings();
	// Context state accumulates""", """	if (off || !g_dev) return;
	// Experiment 0065: the sorted list and a binary search for the table checks (the copy of the
	// whole mapping list and a linear walk per LOAD_CONTEXT_REG_INDEX were most of the pass); the
	// full list only when a window is about to be mapped.
	auto have_p = g_dev->sorted_mappings();
	// Context state accumulates""")
rep("""	static std::map<uint32_t, uint32_t> ctx; // context register offset (relative to 0xa000) -> value""",
    """	static HintCtx ctx; // context register offset (relative to 0xa000) -> value""")
rep("""			auto it = ctx.find(b.lo);
			if (it == ctx.end() || it->second == 0) continue;
			const uint32_t ext  = ctx.count(b.hi) ? (ctx[b.hi] & 0xffu) : 0u;
			const uint64_t addr = (static_cast<uint64_t>(it->second) << 8u) | (static_cast<uint64_t>(ext) << 40u);""",
    """			if (!ctx.has(b.lo) || ctx.get(b.lo) == 0) continue;
			const uint32_t ext  = ctx.has(b.hi) ? (ctx.get(b.hi) & 0xffu) : 0u;
			const uint64_t addr = (static_cast<uint64_t>(ctx.get(b.lo)) << 8u) | (static_cast<uint64_t>(ext) << 40u);""")
rep("""				journal("hint %s 0x%" PRIx64 ": window 0x%" PRIx64 "+0x%" PRIx64 ", direct memory +%.1f MiB\\n", b.name, addr, dlo, lo + window - dlo, static_cast<double>(asked) / 1048576.0);
				have = g_dev->mappings();
				continue;""", """				journal("hint %s 0x%" PRIx64 ": window 0x%" PRIx64 "+0x%" PRIx64 ", direct memory +%.1f MiB\\n", b.name, addr, dlo, lo + window - dlo, static_cast<double>(asked) / 1048576.0);
				have_p = g_dev->sorted_mappings();
				continue;""")
rep("""			std::vector<std::pair<uint64_t, uint64_t>> pieces = {{lo2, hi}};
			for (const auto& m: have) {""", """			std::vector<std::pair<uint64_t, uint64_t>> pieces = {{lo2, hi}};
			const std::vector<bc5::direct::Mapping> have = g_dev->mappings();
			for (const auto& m: have) {""")
rep("""				if (g_dev->map_userptr(pa, pb - pa)) {
					added += pb - pa;
					g_bytes_mapped += pb - pa;
					have.push_back({pa, pb - pa});
				}
			}""", """				if (g_dev->map_userptr(pa, pb - pa)) {
					added += pb - pa;
					g_bytes_mapped += pb - pa;
				}
			}
			have_p = g_dev->sorted_mappings();""")
rep("""		const uint32_t* p  = ib + i;
		bool changed = false;
		if (type == 3 && op == 0x69 && len >= 3) { // SET_CONTEXT_REG
			for (uint32_t k = 2; k < len; k++) {
				const uint32_t off = ((p[1] & 0xffffu) + k - 2) & 0xffffu;
				if (is_base[off] || is_size[off]) {
					ctx[off] = p[k];
					changed = true;
				}
			}""", """		const uint32_t* p  = ib + i;
		bool changed = false, base_changed = false;
		if (type == 3 && op == 0x69 && len >= 3) { // SET_CONTEXT_REG
			for (uint32_t k = 2; k < len; k++) {
				const uint32_t off = ((p[1] & 0xffffu) + k - 2) & 0xffffu;
				if (is_base[off] || is_size[off]) {
					ctx.set(off, p[k]);
					changed = true;
					base_changed = base_changed || is_base[off];
				}
			}""")
rep("""			if (covered(have, a, static_cast<uint64_t>(n) * 8)) {
				const auto* t = reinterpret_cast<const volatile uint32_t*>(a);
				for (uint32_t k = 0; k + 1 < 2 * n; k += 2) {
					const uint32_t off = t[k] & 0xffffu;
					if (is_base[off] || is_size[off]) {
						ctx[off] = t[k + 1];
						changed = true;
					}
				}""", """			if (covered_sorted(*have_p, a, static_cast<uint64_t>(n) * 8)) {
				const auto* t = reinterpret_cast<const volatile uint32_t*>(a);
				for (uint32_t k = 0; k + 1 < 2 * n; k += 2) {
					const uint32_t off = t[k] & 0xffffu;
					if (is_base[off] || is_size[off]) {
						ctx.set(off, t[k + 1]);
						changed = true;
						base_changed = base_changed || is_base[off];
					}
				}""")
rep("""				if (n == 0 || !covered(have, base + static_cast<uint64_t>(off) * 4, static_cast<uint64_t>(n) * 4)) continue;
				const auto* t = reinterpret_cast<const volatile uint32_t*>(base + static_cast<uint64_t>(off) * 4);
				for (uint32_t q = 0; q < n; q++) {
					if (is_base[(off + q) & 0xffffu] || is_size[(off + q) & 0xffffu]) {
						ctx[off + q] = t[q];
						changed = true;
					}
				}""", """				if (n == 0 || !covered_sorted(*have_p, base + static_cast<uint64_t>(off) * 4, static_cast<uint64_t>(n) * 4)) continue;
				const auto* t = reinterpret_cast<const volatile uint32_t*>(base + static_cast<uint64_t>(off) * 4);
				for (uint32_t q = 0; q < n; q++) {
					if (is_base[(off + q) & 0xffffu] || is_size[(off + q) & 0xffffu]) {
						ctx.set(off + q, t[q]);
						changed = true;
						base_changed = base_changed || is_base[(off + q) & 0xffffu];
					}
				}""")
rep("""		if (changed) {
			evaluate();
			size_tally(ctx);
			main_pass_track(ctx);
		}""", """		if (changed) {
			if (base_changed) evaluate(); // a size alone moves no target
			size_tally(ctx);
			main_pass_track(ctx);
		}""")
open(p, "w", encoding="utf-8", newline="").write(s)
print("ok")
