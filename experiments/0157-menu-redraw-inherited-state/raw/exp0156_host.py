#!/usr/bin/env python3
# Experiment 0156: host diagnostics for the second title's text bakes (bc5LleAgc.cpp), applied as exact
# text replacements, like drawjournal_host.py of experiment 0089.
p = "/home/kjaniszewski/src/KytyPlus/src/libs/bc5LleAgc.cpp"
s = open(p, encoding="utf-8", newline="").read()


def rep(a, b):
    global s
    assert s.count(a) == 1, (s.count(a), a[:80])
    s = s.replace(a, b)


# 1. BC5_DIRECT_DRAW_JOURNAL=<t0>:<buffers>[:<min dwords>[:<max rt px>]]
rep("""	static const std::pair<double, uint32_t> draw_journal = [] {
		std::pair<double, uint32_t> v {0, 0};
		if (const char* e = std::getenv("BC5_DIRECT_DRAW_JOURNAL"); e != nullptr) {
			char* end = nullptr;
			v.first   = std::strtod(e, &end);
			if (end != nullptr && *end == ':') v.second = static_cast<uint32_t>(std::strtoul(end + 1, nullptr, 10));
		}
		return v;
	}();""",
    """	// Experiment 0156: two optional filters, <t0>:<buffers>[:<min dwords>[:<max rt px>]]: buffers below
	// <min dwords> are skipped (run 668 caught only small compute-only buffers), and with <max rt px>
	// only draws whose colour target 0 is at most that wide and high are journaled (the text bakes
	// into small atlas targets, F202), each with its scissors, colour attributes, the PS and GS user
	// data and the first 32 dwords of every table they point at; a buffer with no such draw does not
	// count. Lines then carry the journal time and the wall clock, for matching screenshots.
	static const std::pair<double, uint32_t> draw_journal = [] {
		std::pair<double, uint32_t> v {0, 0};
		if (const char* e = std::getenv("BC5_DIRECT_DRAW_JOURNAL"); e != nullptr) {
			char* end = nullptr;
			v.first   = std::strtod(e, &end);
			if (end != nullptr && *end == ':') v.second = static_cast<uint32_t>(std::strtoul(end + 1, nullptr, 10));
		}
		return v;
	}();
	static const std::pair<uint32_t, uint32_t> draw_journal_filter = [] {
		std::pair<uint32_t, uint32_t> v {0, 0};
		if (const char* e = std::getenv("BC5_DIRECT_DRAW_JOURNAL"); e != nullptr) {
			const char* c = std::strchr(e, ':');
			if (c != nullptr) c = std::strchr(c + 1, ':');
			if (c != nullptr) {
				char* end = nullptr;
				v.first   = static_cast<uint32_t>(std::strtoul(c + 1, &end, 10));
				if (end != nullptr && *end == ':') v.second = static_cast<uint32_t>(std::strtoul(end + 1, nullptr, 10));
			}
		}
		return v;
	}();""")

rep("""		static uint32_t journaled = 0;
		if (draw_journal.second != 0 && journaled < draw_journal.second && timing_now() >= draw_journal.first) {
			const uint32_t buf_no = journaled++;
			bc5::full_state::for_each_draw(tracker, span, read, [&](size_t off, std::span<const uint32_t> pkt, const bc5::full_state::Tracker& t) {
				auto reg = [&t](bc5::full_state::Space sp, uint32_t o) {
					uint32_t v = 0;
					return t.get(sp, o, v) ? v : 0u;
				};""",
    """		static uint32_t journaled = 0;
		if (draw_journal.second != 0 && journaled < draw_journal.second && timing_now() >= draw_journal.first && num_dwords >= draw_journal_filter.first) {
			const uint32_t buf_no  = journaled;
			bool           counted = draw_journal_filter.second == 0;
			if (counted) journaled++;
			bc5::full_state::for_each_draw(tracker, span, read, [&](size_t off, std::span<const uint32_t> pkt, const bc5::full_state::Tracker& t) {
				auto reg = [&t](bc5::full_state::Space sp, uint32_t o) {
					uint32_t v = 0;
					return t.get(sp, o, v) ? v : 0u;
				};
				// Experiment 0156: the small-target filter (draws only; CB_COLOR0_ATTRIB2 as below).
				if (draw_journal_filter.second != 0) {
					const uint32_t op2 = (pkt[0] >> 8u) & 0xffu;
					if (op2 == 0x15 || op2 == 0x16) return;
					const uint32_t a2 = reg(bc5::full_state::Context, 0x3b0);
					if (((a2 >> 14u) & 0x3fffu) + 1u > draw_journal_filter.second || (a2 & 0x3fffu) + 1u > draw_journal_filter.second) return;
					if (!counted) {
						counted = true;
						journaled++;
					}
				}""")

# After the main line: the small-target extras.
rep("""				// Experiment 0093: for a draw, the bases of every colour target CB_TARGET_MASK enables""",
    """				// Experiment 0156: for a small-target draw, the time, the window and generic scissors
				// (PA_SC_WINDOW_SCISSOR_TL/BR ctx 0x81/0x82, PA_SC_GENERIC_SCISSOR_TL/BR 0x90/0x91: X 15:0,
				// Y 31:16), CB_COLOR0_VIEW 0x31b, _ATTRIB 0x31d, _ATTRIB3 0x3b8, CB_BLEND0_CONTROL 0x1e0,
				// CB_COLOR_CONTROL 0x202, SPI_SHADER_COL_FORMAT 0x1c5, the PS user data (sh 0x0c..0x2b) and
				// the GS user data (SPI_SHADER_USER_DATA_GS_0 sh 0x8c..0xab), and the first 32 dwords of each
				// readable table a user-data pair points at (tools/bc5-agc/regdb/gfx10.json).
				if (draw_journal_filter.second != 0) {
					const auto     wall = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::system_clock::now().time_since_epoch()).count();
					const uint32_t wtl = reg(S::Context, 0x81), wbr = reg(S::Context, 0x82), gtl = reg(S::Context, 0x90), gbr = reg(S::Context, 0x91);
					journal("bake draw buf %u at %zu: t %.3f wall %lld.%03lld | win %u,%u-%u,%u gen %u,%u-%u,%u | view %08x attrib %08x attrib3 %08x blend0 %08x cc %08x colfmt %08x\\n", buf_no, off,
					        timing_now(), static_cast<long long>(wall / 1000), static_cast<long long>(wall % 1000), wtl & 0x7fffu, (wtl >> 16u) & 0x7fffu, wbr & 0x7fffu, (wbr >> 16u) & 0x7fffu,
					        gtl & 0x7fffu, (gtl >> 16u) & 0x7fffu, gbr & 0x7fffu, (gbr >> 16u) & 0x7fffu, reg(S::Context, 0x31b), reg(S::Context, 0x31d), reg(S::Context, 0x3b8),
					        reg(S::Context, 0x1e0), reg(S::Context, 0x202), reg(S::Context, 0x1c5));
					for (int stage = 0; stage < 2; stage++) {
						const uint32_t ubase = stage == 0 ? 0x0cu : 0x8cu;
						uint32_t       ud[32];
						char           u[320] = {};
						int            uw     = 0;
						for (uint32_t k = 0; k < 32; k++) {
							ud[k] = reg(S::Sh, ubase + k);
							uw += std::snprintf(u + uw, sizeof(u) - static_cast<size_t>(uw), " %08x", ud[k]);
						}
						journal("bake ud %s buf %u at %zu:%s\\n", stage == 0 ? "ps" : "gs", buf_no, off, u);
						std::vector<uint64_t> seen;
						for (uint32_t k = 0; k + 1 < 32; k++) {
							const uint64_t addr = ud[k] | (static_cast<uint64_t>(ud[k + 1] & 0xffffu) << 32u);
							if (addr < 0x1000000000ull || addr >= 0x1400000000ull || (addr & 3u) != 0 || read(addr, 128) == nullptr) continue;
							if (std::find(seen.begin(), seen.end(), addr) != seen.end()) continue;
							seen.push_back(addr);
							const auto* m = reinterpret_cast<const uint32_t*>(addr);
							char        tb[320] = {};
							int         tw      = 0;
							for (uint32_t q = 0; q < 32; q++) tw += std::snprintf(tb + tw, sizeof(tb) - static_cast<size_t>(tw), " %08x", m[q]);
							journal("bake table %s ud%u %010" PRIx64 ":%s\\n", stage == 0 ? "ps" : "gs", k, addr, tb);
						}
					}
				}
				// Experiment 0093: for a draw, the bases of every colour target CB_TARGET_MASK enables""")

# 2. BC5_DIRECT_RT_DUMP_EVERY=<s>: the dump repeats every s seconds, the file name carrying the time.
rep("""	static std::atomic<bool> done {false};
	if (spec.empty() || done.load()) return;
	const double t0 = std::strtod(spec.c_str(), nullptr);
	if (timing_now() < t0 || done.exchange(true)) return;""",
    """	// Experiment 0156: BC5_DIRECT_RT_DUMP_EVERY=<s> repeats the dump every s seconds from t0 on, the
	// file names carrying the journal time (-t<seconds>), to catch a target at a broken and at a clean
	// moment in one run.
	static const double every = [] {
		const char* e = std::getenv("BC5_DIRECT_RT_DUMP_EVERY");
		return e != nullptr ? std::strtod(e, nullptr) : 0.0;
	}();
	static std::atomic<bool> done {false};
	static std::mutex        every_mutex;
	static double            next_t = -1;
	if (spec.empty() || done.load()) return;
	const double t0    = std::strtod(spec.c_str(), nullptr);
	const double now_t = timing_now();
	if (now_t < t0) return;
	if (every > 0) {
		std::lock_guard lock(every_mutex);
		if (next_t < 0) next_t = t0;
		if (now_t < next_t) return;
		next_t = now_t + every;
	} else if (done.exchange(true)) {
		return;
	}
	const double dump_t = now_t;""")

OLD_NAME = """		std::snprintf(name, sizeof(name), "%s/rt-%010" PRIx64 "-%ux%u-%s-f%u.ppm", g_dump_dir.c_str(), va, w, h, fmt, family);
		if (FILE* f = std::fopen(name, "wb"); f != nullptr) {"""
NEW_NAME = """		if (every > 0)
			std::snprintf(name, sizeof(name), "%s/rt-%010" PRIx64 "-%ux%u-%s-f%u-t%07.2f.ppm", g_dump_dir.c_str(), va, w, h, fmt, family, dump_t);
		else
			std::snprintf(name, sizeof(name), "%s/rt-%010" PRIx64 "-%ux%u-%s-f%u.ppm", g_dump_dir.c_str(), va, w, h, fmt, family);
		if (FILE* f = std::fopen(name, "wb"); f != nullptr) {"""
rep(OLD_NAME, NEW_NAME)

open(p, "w", encoding="utf-8", newline="").write(s)
print("ok")
