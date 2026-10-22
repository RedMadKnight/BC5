#!/usr/bin/env python3
# Experiment 0197: on top of exp 0194's edit, BC5_DIRECT_DROP_PS=<hex list> drops every draw of a graphics
# buffer whose pixel shader is in the list (diagnostic, off by default): which draw is the night lake's water.
# The pixel shader is tracked in submit_now's packet walk from SPI_SHADER_PGM_LO_PS / _HI_PS (SH 0x8 / 0x9, as
# the draw journal of exp 0089 reads them: Mesa gfx10 register JSON), set by SET_SH_REG or the title's
# LOAD_SH_REG_INDEX tables, in stream order and carried across buffers.
#   python3 edit0197.py <exp 0194's edited bc5LleAgc.cpp> <out>
import sys

src = open(sys.argv[1]).read()

A1 = "static void submit_now(const uint32_t* ib, uint32_t num_dwords, const char* kind, bool from_header, int ring, const Chain* chain) {\n"
B1 = ("// Experiment 0197: the pixel shader the graphics stream has set last (SPI_SHADER_PGM_LO/HI_PS), for BC5_DIRECT_DROP_PS.\n"
      "static std::atomic<uint64_t> g_bc5_ps_cur {0};\n" + A1)
assert src.count(A1) == 1
src = src.replace(A1, B1)

A2 = "\t\t\t\tif (r == 0x20du) pgm = (pgm & 0xffffffff00ull) | (static_cast<uint64_t>(v & 0xffu) << 40u);\n\t\t\t\tif (r == 0x244u) ud01"
B2 = ("\t\t\t\tif (r == 0x20du) pgm = (pgm & 0xffffffff00ull) | (static_cast<uint64_t>(v & 0xffu) << 40u);\n"
      "\t\t\t\tif (r == 0x8u) g_bc5_ps_cur = (g_bc5_ps_cur.load() & 0xff0000000000ull) | (static_cast<uint64_t>(v) << 8u); // experiment 0197: SPI_SHADER_PGM_LO_PS\n"
      "\t\t\t\tif (r == 0x9u) g_bc5_ps_cur = (g_bc5_ps_cur.load() & 0xffffffff00ull) | (static_cast<uint64_t>(v & 0xffu) << 40u); // _HI_PS\n"
      "\t\t\t\tif (r == 0x244u) ud01")
assert src.count(A2) == 1
src = src.replace(A2, B2)

A3 = "\t\t\t// Experiment 0160 (diagnostic): BC5_DIRECT_DROP_AT=<dwords>:<offset>[,<offset>...] drops the packets at\n"
B3 = r'''			// Experiment 0197 (diagnostic): BC5_DIRECT_DROP_PS=<hex list> drops every draw of a graphics buffer whose pixel
			// shader is in the list (g_bc5_ps_cur above): which draw is the night lake's water (exp 0194/0197).
			// The PS registers also from SET_SH_REG_INDEX (0x9b), LOAD_SH_REG (0x5f: base, then (offset, count) spans) and
			// the flat form of LOAD_SH_REG_INDEX (0x63, dword 3 bit 31 clear: start offset in dword 3 bits 15:0), as
			// bc5::full_state::Tracker::apply_level reads them; only SH 0x8/0x9 are taken from these.
			{
				auto ps_reg = [](uint32_t r, uint32_t v) {
					if (r == 0x8u) g_bc5_ps_cur = (g_bc5_ps_cur.load() & 0xff0000000000ull) | (static_cast<uint64_t>(v) << 8u);
					if (r == 0x9u) g_bc5_ps_cur = (g_bc5_ps_cur.load() & 0xffffffff00ull) | (static_cast<uint64_t>(v & 0xffu) << 40u);
				};
				if (type == 3 && op == 0x9b && len >= 3) {
					const uint32_t f = ib[q + 1] & 0xffffu;
					for (uint32_t k = 0; k + 2 < len; k++) ps_reg(f + k, ib[q + 2 + k]);
				}
				if (type == 3 && op == 0x5f && len >= 5) {
					const uint64_t base = (ib[q + 1] & ~3u) | (static_cast<uint64_t>(ib[q + 2] & 0xffffu) << 32u);
					for (uint32_t k = 3; k + 1 < len; k += 2) {
						const uint32_t off = ib[q + k] & 0xffffu, n = std::min<uint32_t>(ib[q + k + 1] & 0x3fffu, 4096u);
						if (n != 0 && off <= 0x9u && off + n > 0x8u && covered_sorted(*maps_p, base + off * 4ull, n * 4ull)) {
							const auto* t = reinterpret_cast<const volatile uint32_t*>(base + off * 4ull);
							for (uint32_t r = 0; r < n; r++) ps_reg(off + r, t[r]);
						}
					}
				}
				if (type == 3 && op == 0x63 && len >= 5 && (ib[q + 3] >> 31u) == 0) {
					const uint64_t ta = (ib[q + 1] & ~3u) | (static_cast<uint64_t>(ib[q + 2] & 0xffffu) << 32u);
					const uint32_t f = ib[q + 3] & 0xffffu, n = std::min<uint32_t>(ib[q + 4] & 0x3fffu, 4096u);
					if (n != 0 && f <= 0x9u && f + n > 0x8u && covered_sorted(*maps_p, ta, n * 4ull)) {
						const auto* t = reinterpret_cast<const volatile uint32_t*>(ta);
						for (uint32_t r = 0; r < n; r++) ps_reg(f + r, t[r]);
					}
				}
			}
			{
				static const std::set<uint64_t> drop_ps_env = pgm_list("BC5_DIRECT_DROP_PS");
				// BC5_DIRECT_DROP_PS_FILE=<path>: the list is (re)read from this file (hex addresses, comma, space or newline
				// separated) whenever its mtime changes, checked at most every 0.5 s, so draws can be dropped and restored in
				// one frozen view (shader addresses differ between runs: experiment 0197).
				static const char*        drop_ps_file = std::getenv("BC5_DIRECT_DROP_PS_FILE");
				static std::mutex         drop_ps_mutex;
				static std::set<uint64_t> drop_ps_live;
				static double             drop_ps_checked = -1;
				static int64_t            drop_ps_mtime   = -1;
				std::set<uint64_t>        drop_ps_now;
				if (drop_ps_file != nullptr) {
					std::lock_guard lk(drop_ps_mutex);
					const double now = timing_now();
					if (now - drop_ps_checked > 0.5) {
						drop_ps_checked = now;
						struct stat st {};
						if (stat(drop_ps_file, &st) == 0 && static_cast<int64_t>(st.st_mtime) != drop_ps_mtime) {
							drop_ps_mtime = static_cast<int64_t>(st.st_mtime);
							drop_ps_live.clear();
							if (FILE* f = std::fopen(drop_ps_file, "r"); f != nullptr) {
								char tok[64];
								while (std::fscanf(f, " %63[0-9a-fA-Fx]%*[, \n\r\t]", tok) == 1) drop_ps_live.insert(std::strtoull(tok, nullptr, 16));
								std::fclose(f);
							}
							journal("drop ps file: %zu shaders now\n", drop_ps_live.size());
						}
					}
					drop_ps_now = drop_ps_live;
				}
				const std::set<uint64_t>& drop_ps = drop_ps_file != nullptr ? drop_ps_now : drop_ps_env;
				// BC5_DIRECT_DROP_PS_TRACE=1: each new pixel shader the tracker holds at a draw of a graphics buffer (up to 512).
				static const bool ps_trace = std::getenv("BC5_DIRECT_DROP_PS_TRACE") != nullptr;
				if (ps_trace && type == 3 && std::strncmp(kind, "dcb", 3) == 0 && bc5::policy::is_draw_or_dispatch(static_cast<uint8_t>(op)) && op != 0x15 && op != 0x16) {
					static std::mutex         seen_mutex;
					static std::set<uint64_t> seen;
					std::lock_guard           lk(seen_mutex);
					if (seen.size() < 512 && seen.insert(g_bc5_ps_cur.load()).second) journal("ps trace: draw op %02x at %u of a %u-dword %s: ps 0x%010" PRIx64 "\n", op, q, num_dwords, kind, g_bc5_ps_cur.load());
				}
				if (!drop_ps.empty() && type == 3 && std::strncmp(kind, "dcb", 3) == 0 && bc5::policy::is_draw_or_dispatch(static_cast<uint8_t>(op)) && op != 0x15 && op != 0x16 &&
				    drop_ps.count(g_bc5_ps_cur.load()) != 0) {
					static std::atomic<uint64_t> n_dps {0};
					if ((n_dps++ & 0xfffu) == 0) journal("  drop ps 0x%" PRIx64 ": %s draw op %02x at %u dropped (%" PRIu64 " so far)\n", g_bc5_ps_cur.load(), kind, op, q, n_dps.load());
					opt.drop_offsets.push_back(q);
					q += len;
					continue;
				}
			}
''' + A3
assert src.count(A3) == 1
src = src.replace(A3, B3)
open(sys.argv[2], "w", newline="\n").write(src)
print("ok")
