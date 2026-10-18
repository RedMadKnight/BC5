#!/usr/bin/env python3
# Experiment 0156, second step: BC5_DIRECT_DRAW_JOURNAL_PS=<hex prefix>[,...] journals only the draws whose
# pixel shader address (10 hex digits) starts with one of the prefixes (run 670: the UI family 09099c...),
# with the same extras as the small-target filter; tables of 64 dwords; the AMM window counted as a table range.
p = "/home/kjaniszewski/src/KytyPlus/src/libs/bc5LleAgc.cpp"
s = open(p, encoding="utf-8", newline="").read()


def rep(a, b):
    global s
    assert s.count(a) == 1, (s.count(a), a[:80])
    s = s.replace(a, b)


rep("""				if (end != nullptr && *end == ':') v.second = static_cast<uint32_t>(std::strtoul(end + 1, nullptr, 10));
			}
		}
		return v;
	}();""",
    """				if (end != nullptr && *end == ':') v.second = static_cast<uint32_t>(std::strtoul(end + 1, nullptr, 10));
			}
		}
		return v;
	}();
	// Experiment 0156: BC5_DIRECT_DRAW_JOURNAL_PS=<hex prefix>[,...] journals only the draws whose pixel
	// shader address (ten hex digits) starts with one of the prefixes (the second title's UI shaders all
	// lie at 0x09099c....), with the same extras; a buffer with no such draw does not count.
	static const std::vector<std::string> draw_journal_ps = [] {
		std::vector<std::string> v;
		if (const char* e = std::getenv("BC5_DIRECT_DRAW_JOURNAL_PS"); e != nullptr) {
			std::string cur;
			for (const char* q = e;; q++) {
				if (*q == ',' || *q == 0) {
					if (!cur.empty()) v.push_back(cur);
					cur.clear();
					if (*q == 0) break;
				} else {
					cur += static_cast<char>(std::tolower(static_cast<unsigned char>(*q)));
				}
			}
		}
		return v;
	}();""")

rep("""			bool           counted = draw_journal_filter.second == 0;
			if (counted) journaled++;""",
    """			bool           counted = draw_journal_filter.second == 0 && draw_journal_ps.empty();
			if (counted) journaled++;""")

rep("""				// Experiment 0156: the small-target filter (draws only; CB_COLOR0_ATTRIB2 as below).
				if (draw_journal_filter.second != 0) {
					const uint32_t op2 = (pkt[0] >> 8u) & 0xffu;
					if (op2 == 0x15 || op2 == 0x16) return;
					const uint32_t a2 = reg(bc5::full_state::Context, 0x3b0);
					if (((a2 >> 14u) & 0x3fffu) + 1u > draw_journal_filter.second || (a2 & 0x3fffu) + 1u > draw_journal_filter.second) return;
					if (!counted) {""",
    """				// Experiment 0156: the small-target and pixel-shader filters (draws only; CB_COLOR0_ATTRIB2 and
				// SPI_SHADER_PGM_LO/HI_PS as below).
				if (draw_journal_filter.second != 0 || !draw_journal_ps.empty()) {
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
					if (!counted) {""")

rep("""				if (draw_journal_filter.second != 0) {
					const auto     wall = std::chrono""",
    """				if (draw_journal_filter.second != 0 || !draw_journal_ps.empty()) {
					const auto     wall = std::chrono""")

rep("""							if (addr < 0x1000000000ull || addr >= 0x1400000000ull || (addr & 3u) != 0 || read(addr, 128) == nullptr) continue;
							if (std::find(seen.begin(), seen.end(), addr) != seen.end()) continue;
							seen.push_back(addr);
							const auto* m = reinterpret_cast<const uint32_t*>(addr);
							char        tb[320] = {};
							int         tw      = 0;
							for (uint32_t q = 0; q < 32; q++) tw += std::snprintf(tb + tw, sizeof(tb) - static_cast<size_t>(tw), " %08x", m[q]);""",
    """							const bool guest_range = (addr >= 0x1000000000ull && addr < 0x1400000000ull) || (addr >= 0x8000000000ull && addr < 0x9000000000ull);
							if (!guest_range || (addr & 3u) != 0 || read(addr, 256) == nullptr) continue;
							if (std::find(seen.begin(), seen.end(), addr) != seen.end()) continue;
							seen.push_back(addr);
							const auto* m = reinterpret_cast<const uint32_t*>(addr);
							char        tb[640] = {};
							int         tw      = 0;
							for (uint32_t q = 0; q < 64; q++) tw += std::snprintf(tb + tw, sizeof(tb) - static_cast<size_t>(tw), " %08x", m[q]);""")

open(p, "w", encoding="utf-8", newline="").write(s)
print("ok")
