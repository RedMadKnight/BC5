#!/usr/bin/env python3
# Experiment 0157, fifth step: BC5_DIRECT_RT_DUMP items take a crop, "<fmt>@<x>,<y>,<w>,<h>": only that window
# of the surface is detiled and written (the UI layer's list area instead of 33 MB every 2 s).
p = "/home/kjaniszewski/src/KytyPlus/src/libs/bc5LleAgc.cpp"
s = open(p, encoding="utf-8", newline="").read()


def rep(a, b, count=1):
    global s
    assert s.count(a) == count, (s.count(a), a[:80])
    s = s.replace(a, b)


rep("""		uint64_t va = 0;
		unsigned w = 0, h = 0;
		char     fmt[16] = {};
		// Experiment 0104: "layer:<w>:<h>:<fmt>" dumps the UI layer 0 the draw journal last saw.
		if (item.rfind("layer:", 0) == 0) {
			va = g_layer0_base.load();
			if (va == 0 || std::sscanf(item.c_str() + 6, "%u:%u:%15s", &w, &h, fmt) != 3 || w == 0 || h == 0) continue;
		} else if (std::sscanf(item.c_str(), "%" SCNx64 ":%u:%u:%15s", &va, &w, &h, fmt) != 4 || w == 0 || h == 0) continue;""",
    """		uint64_t va = 0;
		unsigned w = 0, h = 0;
		char     fmt[48] = {};
		// Experiment 0104: "layer:<w>:<h>:<fmt>" dumps the UI layer 0 the draw journal last saw.
		if (item.rfind("layer:", 0) == 0) {
			va = g_layer0_base.load();
			if (va == 0 || std::sscanf(item.c_str() + 6, "%u:%u:%47s", &w, &h, fmt) != 3 || w == 0 || h == 0) continue;
		} else if (std::sscanf(item.c_str(), "%" SCNx64 ":%u:%u:%47s", &va, &w, &h, fmt) != 4 || w == 0 || h == 0) continue;
		// Experiment 0157: "<fmt>@<x>,<y>,<w>,<h>" detiles and writes only that window of the surface.
		uint32_t cx = 0, cy = 0, cw = w, ch = h;
		if (char* at = std::strchr(fmt, '@'); at != nullptr) {
			*at = 0;
			if (std::sscanf(at + 1, "%u,%u,%u,%u", &cx, &cy, &cw, &ch) != 4 || cw == 0 || ch == 0 || cx + cw > w || cy + ch > h) {
				cx = cy = 0;
				cw = w;
				ch = h;
			}
		}""")

rep("""		for (uint32_t y = 0; y < h; y++) {
			for (uint32_t x = 0; x < w; x++) {
				uint32_t local = 0, bxor = 0;""",
    """		for (uint32_t y = cy; y < cy + ch; y++) {
			for (uint32_t x = cx; x < cx + cw; x++) {
				uint32_t local = 0, bxor = 0;""")

rep("""			std::fprintf(f, "P6" "\\n" "%u %u" "\\n" "255" "\\n", w, h);
			std::fwrite(rgb.data(), 1, rgb.size(), f);
			std::fclose(f);""",
    """			std::fprintf(f, "P6" "\\n" "%u %u" "\\n" "255" "\\n", cw, ch);
			for (uint32_t y = cy; y < cy + ch; y++) std::fwrite(&rgb[(static_cast<size_t>(y) * w + cx) * 3u], 1, static_cast<size_t>(cw) * 3u, f);
			std::fclose(f);""")

rep("""				std::fprintf(f, "P5" "\\n" "%u %u" "\\n" "255" "\\n", w, h);
				std::fwrite(alpha8.data(), 1, alpha8.size(), f);
				std::fclose(f);""",
    """				std::fprintf(f, "P5" "\\n" "%u %u" "\\n" "255" "\\n", cw, ch);
				for (uint32_t y = cy; y < cy + ch; y++) std::fwrite(&alpha8[static_cast<size_t>(y) * w + cx], 1, cw, f);
				std::fclose(f);""")

open(p, "w", encoding="utf-8", newline="").write(s)
print("ok")
