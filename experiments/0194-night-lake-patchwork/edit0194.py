#!/usr/bin/env python3
# Experiment 0194: the draw journal (BC5_DIRECT_DRAW_JOURNAL, exp 0089) also journals, for every indirect draw
# (DRAW_INDIRECT 0x24, DRAW_INDEX_INDIRECT 0x25, DRAW_INDIRECT_MULTI 0x2c, DRAW_INDEX_INDIRECT_MULTI 0x38), the
# arguments as they read at submission through the SET_BASE index-1 base the buffer set before it, and whether the
# CP check of exp 0052/0057 (BC5_DIRECT_GPU_CHECK=1: vertex/index count above 2^20 or instance count above 64)
# would skip it; and BC5_DIRECT_DRAW_JOURNAL_EVERY (below). Diagnostic, only with the draw journal on. Applied to a COPY of bc5LleAgc.cpp:
#   python3 edit0194.py <in bc5LleAgc.cpp> <out bc5LleAgc.cpp>
import sys

src = open(sys.argv[1]).read()

A1 = "\t\t\t// (the per-frame re-check of the vertex ranges became bc5_ranges_complete, at fence completion)\n"
B1 = A1 + r'''			// Experiment 0194: SET_BASE (0x11) index 1 (dword 1 bits 3:0) by offset, base = dword 2 & ~3 | dword 3
			// bits 15:0 << 32, as bc5::indirect_check::apply reads it: the indirect draws' argument base.
			std::vector<std::pair<size_t, uint64_t>> base1_states;
			for (uint32_t i = 0; i < num_dwords;) {
				const uint32_t h = ib[i], type = h >> 30u;
				uint32_t       len = 1;
				if (type == 3 || type == 0) { const uint32_t c = (h >> 16u) & 0x3fffu; len = c == 0x3fffu ? 1 : c + 2; }
				if (i + len > num_dwords) break;
				if (type == 3 && ((h >> 8u) & 0xffu) == 0x11 && len >= 4 && (ib[i + 1] & 0xfu) == 1)
					base1_states.emplace_back(i, (static_cast<uint64_t>(ib[i + 2]) & ~3ull) | (static_cast<uint64_t>(ib[i + 3] & 0xffffu) << 32u));
				i += len;
			}
'''
assert src.count(A1) == 1
src = src.replace(A1, B1)

A2 = "\t\t\t\t                2 * xs, 2 * ys, xo - xs, yo - ys, ps, es, gs, cs);\n"
B2 = A2 + r'''				// Experiment 0194: an indirect draw's arguments as they read now (for arguments the GPU writes: the
				// previous frame's, the scene standing still), through the SET_BASE index-1 base set before it in this
				// buffer. DRAW_INDIRECT {vertex count, instance count, start vertex, start instance}, DRAW_INDEX_INDIRECT
				// {index count, instance count, start index, base vertex, start instance} (Vulkan's indirect commands, as
				// Mesa radv_cs_emit_indirect_draw_packet emits them, 0866ae7); the multi forms: dword 1 offset, dword 4
				// flags (count from memory: TODO(verify) bit 30), dword 5 count, dwords 6-7 count address, dword 8 stride
				// (same function). "cp-skip": the CP check of BC5_DIRECT_GPU_CHECK (exp 0057 limits 2^20, 64) skips
				// a DRAW_INDIRECT/DRAW_INDEX_INDIRECT with these values; the multi forms are not checked.
				{
					const uint32_t op4 = (pkt[0] >> 8u) & 0xffu;
					if (matched && (op4 == 0x24 || op4 == 0x25 || op4 == 0x2c || op4 == 0x38) && pkt.size() >= 2) {
						uint64_t b1 = 0;
						for (const auto& bs: base1_states) {
							if (bs.first >= off) break;
							b1 = bs.second;
						}
						const bool     multi  = op4 == 0x2c || op4 == 0x38;
						const uint32_t nargs  = (op4 == 0x25 || op4 == 0x38) ? 5u : 4u;
						const uint32_t stride = multi && pkt.size() >= 9 && pkt[8] != 0 ? pkt[8] : nargs * 4u;
						uint32_t       count  = multi && pkt.size() >= 6 ? pkt[5] : 1u;
						uint64_t       ca     = 0;
						uint32_t       cmem   = 0xffffffffu;
						if (multi && pkt.size() >= 8) {
							ca = (static_cast<uint64_t>(pkt[6]) & ~3ull) | (static_cast<uint64_t>(pkt[7] & 0xffffu) << 32u);
							if (ca != 0 && read(ca, 4) != nullptr) cmem = *reinterpret_cast<const volatile uint32_t*>(ca);
						}
						const uint32_t n = std::min<uint32_t>(cmem != 0xffffffffu ? std::min(count, cmem) : count, 4096u);
						char           al[700] = {};
						int            aw      = 0;
						uint32_t       maxv = 0, maxi = 0, n_skip = 0, n_zero = 0, shown = 0;
						const uint64_t a0 = b1 + pkt[1];
						if (b1 != 0 && n != 0 && read(a0, static_cast<uint64_t>(n - 1) * stride + nargs * 4u) != nullptr) {
							for (uint32_t k = 0; k < n; k++) {
								const auto* g = reinterpret_cast<const volatile uint32_t*>(a0 + static_cast<uint64_t>(k) * stride);
								const uint32_t v = g[0], in = g[1];
								maxv = std::max(maxv, v), maxi = std::max(maxi, in);
								if (v > (1u << 20u) || in > 64u) n_skip++;
								if (v == 0 || in == 0) n_zero++;
								if (shown < 8 && aw < 600) {
									shown++;
									aw += std::snprintf(al + aw, sizeof(al) - static_cast<size_t>(aw), " [");
									for (uint32_t q = 0; q < nargs; q++) aw += std::snprintf(al + aw, sizeof(al) - static_cast<size_t>(aw), q ? " %x" : "%x", g[q]);
									aw += std::snprintf(al + aw, sizeof(al) - static_cast<size_t>(aw), "]");
								}
							}
							if (!multi) bc5_range_remember(ib, buf_no, static_cast<uint32_t>(off), nargs == 5 ? "args5" : "args4", a0, nargs * 4u); // read again at completion (exp 0194)
							journal("draw journal args buf %u at %zu: op %02x base1 %010" PRIx64 " +0x%x%s count %u (dw4 %08x, count addr %010" PRIx64 " = %d) stride %u | max count %u max inst %u, %u zero, %u over the CP limits%s |%s\n",
							        buf_no, off, op4, b1, pkt[1], multi ? "" : " single", count, multi && pkt.size() >= 5 ? pkt[4] : 0u, ca, static_cast<int>(cmem), stride, maxv, maxi, n_zero, n_skip,
							        (!multi && n_skip != 0) ? " cp-skip" : "", al);
						} else {
							journal("draw journal args buf %u at %zu: op %02x base1 %010" PRIx64 " +0x%x count %u: %s\n", buf_no, off, op4, b1, pkt[1], count, b1 == 0 ? "no SET_BASE 1 in this buffer" : "unreadable");
						}
					}
				}
'''
assert src.count(A2) == 1
src = src.replace(A2, B2)

# Experiment 0194: BC5_DIRECT_DRAW_JOURNAL_EVERY=<s> repeats the draw journal's window: once <buffers> buffers are
# journaled, the next window opens <s> seconds later (buffer numbers keep counting), each window starting with a line
# carrying the journal time and the wall clock, for matching screenshots taken while the maintainer plays.
A3 = "\t\tstatic uint32_t journaled = 0;\n\t\tif (draw_journal.second != 0 && journaled < draw_journal.second && timing_now() >= draw_journal.first && num_dwords >= draw_journal_filter.first) {\n\t\t\tconst uint32_t buf_no  = journaled;\n"
B3 = r"""		static uint32_t journaled = 0;
		// Experiment 0194: BC5_DIRECT_DRAW_JOURNAL_EVERY=<s>: the window repeats <s> seconds after it filled.
		static const double dj_every = [] {
			const char* e = BC5_DIAG_ENV("BC5_DIRECT_DRAW_JOURNAL_EVERY");
			return e != nullptr ? std::strtod(e, nullptr) : 0.0;
		}();
		static uint32_t dj_window_base = 0;
		static double   dj_window_t0   = draw_journal.first;
		if (dj_every > 0 && draw_journal.second != 0 && journaled - dj_window_base >= draw_journal.second) {
			dj_window_base = journaled;
			dj_window_t0   = timing_now() + dj_every;
		}
		if (draw_journal.second != 0 && journaled - dj_window_base < draw_journal.second && timing_now() >= dj_window_t0 && num_dwords >= draw_journal_filter.first) {
			const uint32_t buf_no  = journaled;
			if (journaled == dj_window_base) {
				const auto wall = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::system_clock::now().time_since_epoch()).count();
				journal("draw journal window from buf %u: t %.3f wall %lld.%03lld\n", buf_no, timing_now(), static_cast<long long>(wall / 1000), static_cast<long long>(wall % 1000));
			}
"""
assert src.count(A3) == 1
src = src.replace(A3, B3)

# Experiment 0194: at the buffer's completion, the arguments of each journaled single indirect draw as the GPU left them
# (the values the CP check saw, unless the next frame rewrote them already), with the CP limits flagged.
A4 = "\tif (mine.empty()) return;\n\tconst double now     = timing_now();\n"
B4 = A4 + r"""	for (const Bc5ReadRange& r: mine) { // experiment 0194
		if (std::strncmp(r.kind, "args", 4) != 0 || !covered_sorted(*maps_p, r.addr, r.copy.size()) || r.copy.size() < 16) continue;
		const auto* g = reinterpret_cast<const volatile uint32_t*>(r.addr);
		uint32_t    s4[4] = {};
		std::memcpy(s4, r.copy.data(), sizeof(s4));
		journal("args at completion: submit #%" PRIu64 " buf %u at %u %010" PRIx64 ": [%x %x %x %x] submitted [%x %x %x %x]%s\n", n, r.buf, r.off, r.addr, g[0], g[1], g[2], g[3], s4[0], s4[1], s4[2],
		        s4[3], (g[0] > (1u << 20u) || g[1] > 64u) ? " over the CP limits" : "");
	}
"""
assert src.count(A4) == 1
src = src.replace(A4, B4)
open(sys.argv[2], "w").write(src)
print("ok")
