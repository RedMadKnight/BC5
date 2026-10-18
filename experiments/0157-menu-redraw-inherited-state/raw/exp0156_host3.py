#!/usr/bin/env python3
# Experiment 0156, third step: (a) BC5_DIRECT_RT_DUMP formats r8 and r16f (1 and 2 bytes per element);
# (b) with the small-target or pixel-shader filter on, BC5_DIRECT_DRAW_JOURNAL_FIND still sees every draw
# and dispatch of the journaled buffers (to find what writes the atlases).
p = "/home/kjaniszewski/src/KytyPlus/src/libs/bc5LleAgc.cpp"
s = open(p, encoding="utf-8", newline="").read()


def rep(a, b):
    global s
    assert s.count(a) == 1, (s.count(a), a[:80])
    s = s.replace(a, b)


# (a) formats
rep("""		const uint32_t  bpe = std::strcmp(fmt, "rgba16f") == 0 ? 8u : 4u; // experiment 0091""",
    """		// Experiment 0156: r8 (one byte, UNORM) and r16f (two bytes, half float) for the title's glyph atlases.
		const uint32_t  bpe = std::strcmp(fmt, "rgba16f") == 0 ? 8u : std::strcmp(fmt, "r8") == 0 ? 1u : std::strcmp(fmt, "r16f") == 0 ? 2u : 4u; // experiment 0091""")

rep("""				uint32_t       v   = 0;
				std::memcpy(&v, src + off, 4);
				uint32_t v2 = 0;""",
    """				uint32_t       v   = 0;
				std::memcpy(&v, src + off, bpe < 4 ? bpe : 4);
				uint32_t v2 = 0;""")

rep("""				} else if (std::strcmp(fmt, "r32f") == 0) {
					float f = 0;
					std::memcpy(&f, &v, 4);""",
    """				} else if (bpe == 1) {
					r = g = b = static_cast<float>(v & 0xffu) / 255.0f;
					sum_v += r;
					max_v = std::max(max_v, static_cast<double>(r));
				} else if (bpe == 2) {
					const uint32_t e = (v >> 10u) & 0x1fu, m = v & 0x3ffu;
					float          f = e == 0 ? std::ldexp(static_cast<float>(m), -24) : e == 31 ? 65504.0f : std::ldexp(1.0f + static_cast<float>(m) / 1024.0f, static_cast<int>(e) - 15);
					if ((v >> 15u) & 1u) f = -f;
					sum_v += f;
					max_v = std::max(max_v, static_cast<double>(f));
					r = g = b = std::fabs(f) / (1.0f + std::fabs(f));
				} else if (std::strcmp(fmt, "r32f") == 0) {
					float f = 0;
					std::memcpy(&f, &v, 4);""")

# (b) FIND alongside the filters
rep("""				if (draw_journal_filter.second != 0 || !draw_journal_ps.empty()) {
					const uint32_t op2 = (pkt[0] >> 8u) & 0xffu;
					if (op2 == 0x15 || op2 == 0x16) return;
					if (draw_journal_filter.second != 0) {
						const uint32_t a2 = reg(bc5::full_state::Context, 0x3b0);
						if (((a2 >> 14u) & 0x3fffu) + 1u > draw_journal_filter.second || (a2 & 0x3fffu) + 1u > draw_journal_filter.second) return;
					}
					if (!draw_journal_ps.empty()) {
						const uint64_t ps_now = (static_cast<uint64_t>(reg(bc5::full_state::Sh, 0x8)) | (static_cast<uint64_t>(reg(bc5::full_state::Sh, 0x9) & 0xffu) << 32u)) << 8u;
						char           pb[24];
						std::snprintf(pb, sizeof(pb), "%010" PRIx64, ps_now);
						bool ok = false;
						for (const std::string& pre: draw_journal_ps)
							if (std::strncmp(pb, pre.c_str(), pre.size()) == 0) ok = true;
						if (!ok) return;
					}
					if (!counted) {
						counted = true;
						journaled++;
					}
				}""",
    """				// A draw or dispatch the filters reject is still shown to BC5_DIRECT_DRAW_JOURNAL_FIND below.
				const bool filters_on = draw_journal_filter.second != 0 || !draw_journal_ps.empty();
				const bool matched    = [&]() -> bool {
					if (!filters_on) return true;
					const uint32_t op2 = (pkt[0] >> 8u) & 0xffu;
					if (op2 == 0x15 || op2 == 0x16) return false;
					if (draw_journal_filter.second != 0) {
						const uint32_t a2 = reg(bc5::full_state::Context, 0x3b0);
						if (((a2 >> 14u) & 0x3fffu) + 1u > draw_journal_filter.second || (a2 & 0x3fffu) + 1u > draw_journal_filter.second) return false;
					}
					if (!draw_journal_ps.empty()) {
						const uint64_t ps_now = (static_cast<uint64_t>(reg(bc5::full_state::Sh, 0x8)) | (static_cast<uint64_t>(reg(bc5::full_state::Sh, 0x9) & 0xffu) << 32u)) << 8u;
						char           pb[24];
						std::snprintf(pb, sizeof(pb), "%010" PRIx64, ps_now);
						bool ok = false;
						for (const std::string& pre: draw_journal_ps)
							if (std::strncmp(pb, pre.c_str(), pre.size()) == 0) ok = true;
						if (!ok) return false;
					}
					return true;
				}();
				static const bool find_set = std::getenv("BC5_DIRECT_DRAW_JOURNAL_FIND") != nullptr;
				if (!matched && !find_set) return;
				if (matched && !counted) {
					counted = true;
					journaled++;
				}""")

rep("""				if (!watch_quiet) journal("draw journal buf %u (%u dwords) at %zu:%s | rt0""",
    """				if (!watch_quiet && matched) journal("draw journal buf %u (%u dwords) at %zu:%s | rt0""")

rep("""					if (mw > 0 && !watch_quiet) journal("draw journal mrt buf %u at %zu:%s | ps %010" PRIx64 "\\n", buf_no, off, mrt, ps);""",
    """					if (mw > 0 && !watch_quiet && matched) journal("draw journal mrt buf %u at %zu:%s | ps %010" PRIx64 "\\n", buf_no, off, mrt, ps);""")

rep("""				if (draw_journal_filter.second != 0 || !draw_journal_ps.empty()) {
					const auto     wall = std::chrono""",
    """				if (filters_on && matched) {
					const auto     wall = std::chrono""")

open(p, "w", encoding="utf-8", newline="").write(s)
print("ok")
