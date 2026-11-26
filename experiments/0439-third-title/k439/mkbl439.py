#!/usr/bin/env python3
# BC5 exp 0439 (tag bl439): two catchers for the run after the maintainer's session of 11-22 17:49 (README item 51), in
# the private unit after mkpa439/mkqc444/mkfp439. Normal build only (both compile out in lean). No fix.
#  1. The black picture: at every flip of a registered DCC display surface, the keys the title's draw left are counted
#     (already scanned there); a key that is not a clear code (0x00, 0xFF, 0x40, 0x80, 0xC0, 0x20, 0x10: Mesa 0866ae7
#     src/amd/common/ac_descriptors.h) is compressed picture data. After 300 or more flips with picture data, the first
#     run of 30 flips with none is the picture going black: one journal line, then pa439's record of the newest dcb
#     (unmet waits, dispatch_state/sc439/sx439, its piece files once), the same record the stall watchdog writes.
#     BC5_0439_BLACK_CATCH=1 turns it on.
#  2. The soft-CP waits that time out (exp 0343's bound, 8 ms on cq0; the host then continues as if satisfied): the line
#     cap becomes BC5_0439_SOFT_LINES (default 2000 as before), and a timed-out wait adds one line with the packets that
#     run early after it: up to 8, within the wait's own 64-KiB block, opcode, length and first two dwords.
# Usage: python mkbl439.py IN.cpp OUT.cpp (every anchor exactly once)
import sys

src, dst = sys.argv[1], sys.argv[2]
s = open(src, 'rb').read().decode('utf-8', 'surrogateescape')
assert '\r' not in s and 'bl439' not in s


def rep(a, b):
    global s
    assert s.count(a) == 1, (a[:70], s.count(a))
    s = s.replace(a, b)


# ---- 2: the soft-CP line cap and the packets after a timed-out wait ----
rep('''	if (g_soft_lines++ >= 2000) return; // the counters go on, the lines stop''',
    '''	static const uint64_t bl439_cap = [] { // exp 0439 (tag bl439): BC5_0439_SOFT_LINES, default 2000 as before
		const char* e = std::getenv("BC5_0439_SOFT_LINES");
		return e != nullptr && *e != 0 ? std::strtoull(e, nullptr, 10) : 2000ull;
	}();
	if (g_soft_lines++ >= bl439_cap) return; // the counters go on, the lines stop''')
rep('''	                static_cast<const void*>(t_cur_buf), static_cast<const void*>(p), where, t_gpu_done.empty() ? "empty" : "set");
}''', '''	                static_cast<const void*>(t_cur_buf), static_cast<const void*>(p), where, t_gpu_done.empty() ? "empty" : "set");
#ifndef BC5_LEAN
	if (timed_out) { // exp 0439 (tag bl439): what this replay runs early, up to 8 packets after the wait, in its 64-KiB block
		const uint64_t pa  = reinterpret_cast<uint64_t>(p);
		const uint64_t end = (pa | 0xffffull) + 1;
		char           line[512];
		size_t         o = 0;
		uint64_t       q = pa;
		for (int k = 0; k < 9 && q + 4 <= end; k++) {
			const uint32_t h = *reinterpret_cast<const volatile uint32_t*>(q), ty = h >> 30u;
			uint32_t       len = 1;
			if (ty == 3 || ty == 0) {
				const uint32_t c = (h >> 16u) & 0x3fffu;
				len = c == 0x3fffu ? 1 : c + 2;
			}
			if (k > 0 && o + 48 < sizeof(line)) {
				const uint32_t d1 = q + 8 <= end ? *reinterpret_cast<const volatile uint32_t*>(q + 4) : 0u;
				const uint32_t d2 = q + 12 <= end ? *reinterpret_cast<const volatile uint32_t*>(q + 8) : 0u;
				o += static_cast<size_t>(std::snprintf(line + o, sizeof(line) - o, " %s0x%02x/%u(%08x %08x)", ty == 3 ? "" : "t", (h >> 8u) & 0xffu, len, d1, d2));
			}
			q += 4ull * len;
		}
		line[o] = 0;
		Direct::journal("soft-cp after timeout: t %.3f s the packets after the wait on 0x%" PRIx64 ":%s\\n", Direct::timing_now(), a, line);
	}
#endif
}''')
# ---- 1: the black-picture trigger at the flip ----
rep('''		for (uint64_t k = 0; k < keys; k++) {
			const uint8_t v = meta[k];
			n00 += v == 0x00;
			nff += v == 0xFF;
		}
''', '''		uint64_t ncomp = 0; // exp 0439 (tag bl439): keys that are picture data, not a clear code
		for (uint64_t k = 0; k < keys; k++) {
			const uint8_t v = meta[k];
			n00 += v == 0x00;
			nff += v == 0xFF;
			ncomp += !(v == 0x00 || v == 0xFF || v == 0x40 || v == 0x80 || v == 0xC0 || v == 0x20 || v == 0x10);
		}
#ifndef BC5_LEAN
		{ // exp 0439 (tag bl439): the picture going black (BC5_0439_BLACK_CATCH=1)
			static const bool bl = [] {
				const char* e = std::getenv("BC5_0439_BLACK_CATCH");
				return e != nullptr && e[0] == '1' && e[1] == 0;
			}();
			static uint64_t with = 0, without = 0;
			static bool     fired = false;
			if (bl && !fired) {
				if (ncomp != 0) with++, without = 0;
				else without++;
				if (with >= 300 && without == 30) {
					fired = true;
					journal("bl439: t %.3f s the display surface's keys hold no picture data for 30 flips after %" PRIu64 " flips with it: the picture went black; pa439's record of the newest dcb follows\\n", timing_now(), with);
					std::fprintf(stderr, "[bc5] exp 0439 (tag bl439): t %.3f s the picture went black (keys all clear codes for 30 flips)\\n", timing_now());
					pw439_unmet_journal("black picture");
				}
			}
		}
#endif
''')
# ---- 3: indirect draws per frame, and whether the filter lets them through (experiment 0054/0057's extra_drop:
#      0x24 DRAW_INDIRECT, 0x2c DRAW_INDIRECT_MULTI, 0x38 DRAW_INDEX_INDIRECT_MULTI dropped unless
#      BC5_DIRECT_INDIRECT_DRAWS; "=1" passes 0x24 only, "multi" all three). Counted in the same walk as fp439, the
#      buffer's top level and its pieces; journaled with fp439's line every 4096 submits. Normal build only.
rep('''			bc5::fp439::Stats     ss;
''', '''			bc5::fp439::Stats     ss;
#ifndef BC5_LEAN
			{ // exp 0439 (tag bl439): the indirect draws of this buffer and whether they reach the GPU
				static const bool words_once = [] { // exp 0439 (tag bl439): the effective values the series' runs change, after the defaults tables
					static const char* const names[] = {"BC5_DIRECT_SOFT_WAIT_MS", "BC5_0439_SOFT_WAIT_MS", "BC5_0439_CHAIN_WRITERS", "BC5_DIRECT_CHAIN_WRITERS", "BC5_DIRECT_CROSS_RING_WAITS", "BC5_DIRECT_RING_DEPS",
					                                    "BC5_DIRECT_INDIRECT_DRAWS", "BC5_DIRECT_GPU_CHECK", "BC5_DIRECT_GPU_CHECK_PRODUCT", "BC5_DIRECT_MEC_INDIRECT", "BC5_DIRECT_SHADOW_LABELS",
					                                    "BC5_DIRECT_DMA_SYNC", "BC5_DIRECT_GC_TF_RING", "BC5_DIRECT_GC_HS_OFFCHIP", "BC5_DIRECT_FLAT_APERTURE", "BC5_DIRECT_FLAT_APERTURE_PIECES", "BC5_DIRECT_HOST_INDIRECT",
					                                    "KYTY_BC5_SAVEDATA_DIR", "KYTY_BC5_APR_RESULT_ORDER", "BC5_DIRECT_IB_CHAIN", "BC5_DIRECT_IB_CHAIN_FLAT", "BC5_DIRECT_AGC_EOP_IDENT", "BC5_DIRECT_DMA_SYNC_MEC", "BC5_DIRECT_DMA_SYNC_LABEL", "BC5_DIRECT_PREFIX_CHAINS", "KYTY_BC5_AT9_DMC", "KYTY_BC5_VD2_SIZES", "BC5_DIRECT_WAIT_MS", "KYTY_BC5_0439_PAD_TOUCH", "KYTY_BC5_0439_PAD_TIME", "BC5_0439_FRAME_DUMP"};
					std::string l;
					for (const char* n : names) {
						const char* v = std::getenv(n);
						l += std::string(" ") + n + "=" + (v != nullptr ? v : "(unset)");
					}
					std::fprintf(stderr, "[bc5] exp 0439 (tag bl439): effective words:%s\\n", l.c_str());
					journal("bl439: effective words:%s\\n", l.c_str());
					return true;
				}();
				(void)words_once;
				static const int idr = [] {
					const char* e = std::getenv("BC5_DIRECT_INDIRECT_DRAWS");
					return e == nullptr ? 0 : (std::strcmp(e, "multi") == 0 ? 2 : 1);
				}();
				static std::atomic<uint64_t> n_ind {0}, n_pass {0};
				for (const auto& pc : cr.pieces)
					for (uint32_t q = 0; q < pc.n;) {
						const uint32_t h = pc.src[q], ty = h >> 30u;
						uint32_t       len = 1;
						if (ty == 3 || ty == 0) {
							const uint32_t c = (h >> 16u) & 0x3fffu;
							len = c == 0x3fffu ? 1 : c + 2;
						}
						if (q + len > pc.n) break;
						const uint32_t op = (h >> 8u) & 0xffu;
						if (ty == 3 && (op == 0x24 || op == 0x2c || op == 0x38)) {
							n_ind++;
							if (idr == 2 || (idr == 1 && op == 0x24)) n_pass++;
						}
						q += len;
					}
				static std::atomic<uint64_t> n_sub2 {0};
				if ((n_sub2++ & 0xfffu) == 0)
					journal("bl439: indirect draws so far %" PRIu64 " (op 0x24/0x2c/0x38 in buffers and their pieces), %" PRIu64 " let through by the filter (BC5_DIRECT_INDIRECT_DRAWS %s); frames by the flip count in the frame profile\\n",
					        n_ind.load(), n_pass.load(), idr == 0 ? "unset: all dropped" : (idr == 1 ? "=1: 0x24 only" : "=multi: all"));
			}
#endif
''')
# ---- 4: a measurement word for the soft-CP bound. BC5_DIRECT_SOFT_WAIT_MS is in switch_defaults.hpp's kIgnored (exp
#      0419, F432: taken out of the environment at start, the 8 ms is the tested behaviour), so run r2 of 11-22 ran with
#      8 ms. BC5_0439_SOFT_WAIT_MS=<ms> (1..60000) overrides it for a measurement; never a default.
rep('''static uint64_t soft_wait_ns() {
	static const uint64_t v = (BC5_DIAG_ENV("BC5_DIRECT_SOFT_WAIT_MS") != nullptr ? std::strtoull(BC5_DIAG_ENV("BC5_DIRECT_SOFT_WAIT_MS"), nullptr, 10) : 8ull) * 1'000'000ull;
	return v;
}''', '''static uint64_t soft_wait_ns() {
	static const uint64_t v = [] { // exp 0439 (tag bl439): BC5_0439_SOFT_WAIT_MS for a measurement, else as before
		if (const char* e = std::getenv("BC5_0439_SOFT_WAIT_MS"); e != nullptr && *e != 0) {
			const uint64_t ms = std::strtoull(e, nullptr, 10);
			if (ms >= 1 && ms <= 60000) {
				std::fprintf(stderr, "[bc5] exp 0439 (tag bl439): soft-CP wait bound %" PRIu64 " ms (BC5_0439_SOFT_WAIT_MS, a measurement)\\n", ms);
				return ms * 1'000'000ull;
			}
		}
		return (BC5_DIAG_ENV("BC5_DIRECT_SOFT_WAIT_MS") != nullptr ? std::strtoull(BC5_DIAG_ENV("BC5_DIRECT_SOFT_WAIT_MS"), nullptr, 10) : 8ull) * 1'000'000ull;
	}();
	return v;
}''')
# on a unit without pa439's record (the bake-2 based build of 11-22 night), the black trigger journals its line only
if 'pw439_unmet_journal(const char' not in s:
    t = '\t\t\t\t\tpw439_unmet_journal("black picture");\n'
    assert s.count(t) == 1, s.count(t)
    s = s.replace(t, '\t\t\t\t\t// (no pa439 record in this unit: the line above is the record)\n')
open(dst, 'wb').write(s.encode('utf-8', 'surrogateescape'))
print('mkbl439: wrote', dst)
