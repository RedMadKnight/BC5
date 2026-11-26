#!/usr/bin/env python3
# BC5 exp 0439 (tag vt439, 11-25 night, the top session's step 3: the rainbow trigger). In sr439b_dark (the flip hook
# after dc439's in-place decompress; it runs only with BC5_0439_FRAME_DUMP set, normal build): with
# BC5_0439_RB_TRIGGER=<n> (off by default) the 4096 evenly spaced samples of the display surface (2_10_10_10, red in bits
# 0-9, green 10-19, blue 20-29, as sr439cread.py decodes it) are counted for saturated violet-to-magenta pixels
# (saturation > 0.4, lightness 0.1-0.9, hue 235-330 degrees: k439/violet439.py's rule; the patch seen on 11-25 01:1x
# scored ~5 of 4096). At n or more: a journal line on stderr with the count, the display surface written raw (as the
# GPU left it after the decompress, tiled) to <frame dump dir>/vt439-<t>-<count>.raw with its size, at most one every
# 5 s and 40 in all, from BC5_0439_RB_FROM s after the first flip (0: from the start; the opening film's logo light is
# violet); with BC5_0439_RB_ARM=1 also sr439b's capture armed ("violet"). Every 600th flip a line with the
# largest count seen so far.
# Usage: python3 mkvt439.py <d2/new>   (patches bc5LleAgc.cpp in place; after mksr439b.py's sr439b_dark)
import os
import sys

p = os.path.join(sys.argv[1], 'bc5LleAgc.cpp')
s = open(p, 'rb').read().decode('utf-8', 'surrogateescape')
assert '(tag vt439)' not in s
crlf = '\r\n' in s
s = s.replace('\r\n', '\n')
a = '''	const double t = srb439::now_s(), d = bc5::sr439b::dark_fraction(q, 4096, 4096);
'''
assert s.count(a) == 1, s.count(a)
b = a + r'''	{ // exp 0439 (tag vt439): the rainbow trigger (BC5_0439_RB_TRIGGER=<n>)
		static const int vt_n = [] {
			const char* e = std::getenv("BC5_0439_RB_TRIGGER");
			return e != nullptr ? std::atoi(e) : 0;
		}();
		static const double vt_from = [] {
			const char* e = std::getenv("BC5_0439_RB_FROM");
			return e != nullptr ? std::atof(e) : 0.0;
		}();
		static double vt_t0 = -1.0;
		if (vt_t0 < 0) vt_t0 = t;
		if (vt_n > 0 && t - vt_t0 >= vt_from) {
			int v = 0;
			for (uint32_t i = 0; i < 4096; i++) {
				const uint32_t u  = static_cast<uint32_t>(q[4 * i]) | (static_cast<uint32_t>(q[4 * i + 1]) << 8u) | (static_cast<uint32_t>(q[4 * i + 2]) << 16u) | (static_cast<uint32_t>(q[4 * i + 3]) << 24u);
				const double   r  = (u & 0x3ffu) / 1023.0, g = ((u >> 10u) & 0x3ffu) / 1023.0, bb = ((u >> 20u) & 0x3ffu) / 1023.0;
				const double   mx = std::max(r, std::max(g, bb)), mn = std::min(r, std::min(g, bb)), l = (mx + mn) / 2.0, dd = mx - mn;
				if (dd <= 0.0 || l <= 0.1 || l >= 0.9) continue;
				const double sat = l > 0.5 ? dd / (2.0 - mx - mn) : dd / (mx + mn);
				if (sat <= 0.4) continue;
				double hue = mx == r ? std::fmod((g - bb) / dd, 6.0) : (mx == g ? (bb - r) / dd + 2.0 : (r - g) / dd + 4.0);
				hue *= 60.0;
				if (hue < 0) hue += 360.0;
				if (hue >= 235.0 && hue <= 330.0) v++;
			}
			static int      vt_max = 0, vt_written = 0;
			static uint64_t vt_flips = 0;
			static double   vt_last = -100.0;
			if (v > vt_max) vt_max = v;
			if (++vt_flips % 600 == 0) std::fprintf(stderr, "[bc5] exp 0439 (tag vt439): t %.1f s: %" PRIu64 " flips, the largest violet count %d of 4096\n", t, vt_flips, vt_max);
			if (v >= vt_n && t - vt_last >= 5.0 && vt_written < 40) {
				vt_last = t;
				vt_written++;
				char path[512];
				std::snprintf(path, sizeof(path), "%s/vt439-%.1f-%d-%ux%u.raw", srb439::dir(), t, v, w, h);
				const int fd = open(path, O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC, 0600);
				bool      ok = false;
				if (fd >= 0) {
					const uint64_t n = px * 4, step = 1u << 20;
					ok = true;
					static std::vector<uint8_t> tmp(step);
					for (uint64_t o = 0; o < n && ok; o += step) {
						const uint64_t k = std::min<uint64_t>(step, n - o);
						for (uint64_t j = 0; j < k; j++) tmp[j] = m[o + j];
						ok = write(fd, tmp.data(), k) == static_cast<ssize_t>(k);
					}
					close(fd);
				}
				std::fprintf(stderr, "[bc5] exp 0439 (tag vt439): t %.1f s: violet count %d of 4096 (trigger %d): the display surface %s %s\n", t, v, vt_n, ok ? "written to" : "NOT written to", path);
				const char* arm = std::getenv("BC5_0439_RB_ARM");
				if (arm != nullptr && arm[0] == '1') {
					std::lock_guard lk2(srb439::g_mu);
					if (srb439::g_m.arm("violet")) std::fprintf(stderr, "[bc5] exp 0439 (tag vt439): the frame dump armed by the violet count\n");
				}
			}
		}
	}
'''
s = s.replace(a, b)
if crlf:
    s = s.replace('\n', '\r\n')
open(p, 'wb').write(s.encode('utf-8', 'surrogateescape'))
print('mkvt439: patched', p)
