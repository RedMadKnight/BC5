#!/usr/bin/env python3
# Experiment 0157, eighth step: (a) BC5_DIRECT_IB_DUMP=0:0:<t0>:<count>[:<dir>] dumps the raw buffers the draw
# journal's filters matched (the UI redraws), named ib-<submission>-<kind>-<dwords>-buf<journal buffer>.bin;
# (b) the register tables of LOAD_*_REG(_INDEX) packets of a matched buffer join the completion-time check.
p = "/home/kjaniszewski/src/KytyPlus/src/libs/bc5LleAgc.cpp"
s = open(p, encoding="utf-8", newline="").read()


def rep(a, b):
    global s
    assert s.count(a) == 1, (s.count(a), a[:80])
    s = s.replace(a, b)


rep("""static std::vector<Bc5ReadRange> g_read_ranges;
static std::mutex                g_read_ranges_mutex;""",
    """static std::vector<Bc5ReadRange> g_read_ranges;
static std::mutex                g_read_ranges_mutex;
// Experiment 0157: the buffer piece_check is working on matched the draw journal's filters (a UI redraw):
// submit_one dumps it when BC5_DIRECT_IB_DUMP has 0:0 as its size range.
static thread_local bool     t_ui_buffer = false;
static thread_local uint32_t t_ui_buf_no = 0;""")

rep("""static void piece_check(const uint32_t* ib, uint32_t num_dwords, const char* kind) {""",
    """static void piece_check(const uint32_t* ib, uint32_t num_dwords, const char* kind) {
	t_ui_buffer = false;""")

rep("""				if (matched && !counted) {
					counted = true;
					journaled++;
				}""",
    """				if (matched && !counted) {
					counted     = true;
					journaled++;
					t_ui_buffer = true;
					t_ui_buf_no = buf_no;
					// Experiment 0157: the register tables this buffer loads (LOAD_CONTEXT/SH/UCONFIG_REG 0x61/0x5f/
					// 0x5e: base lo/hi, then (offset, count) pairs; the _INDEX forms 0x9f/0x63/0x64: base, dword 3
					// bit 31 = pairs of (offset, value), dword 4 = count; as bc5::full_state::Tracker::apply reads
					// them) join the completion-time check.
					for (uint32_t i = 0; i < num_dwords;) {
						const uint32_t h = ib[i], type = h >> 30u;
						uint32_t       len = 1;
						if (type == 3 || type == 0) { const uint32_t c = (h >> 16u) & 0x3fffu; len = c == 0x3fffu ? 1 : c + 2; }
						if (i + len > num_dwords) break;
						if (type == 3 && len >= 5) {
							const uint32_t lop  = (h >> 8u) & 0xffu;
							const uint64_t base = (static_cast<uint64_t>(ib[i + 1]) & ~3ull) | (static_cast<uint64_t>(ib[i + 2] & 0xffffu) << 32u);
							if (lop == 0x61 || lop == 0x5f || lop == 0x5e) {
								for (uint32_t k = 3; k + 1 < len; k += 2) {
									const uint32_t n = ib[i + k + 1] & 0x3fffu;
									const uint64_t a = base + static_cast<uint64_t>(ib[i + k] & 0xffffu) * 4u;
									if (n != 0 && n <= 1024 && read(a, n * 4ull) != nullptr) bc5_range_remember(ib, buf_no, i, "reg table", a, n * 4ull);
								}
							} else if (lop == 0x9f || lop == 0x63 || lop == 0x64) {
								const bool     pairs = (ib[i + 3] >> 31u) != 0;
								const uint32_t n     = ib[i + 4] & 0x3fffu;
								const uint64_t bytes = static_cast<uint64_t>(n) * (pairs ? 8u : 4u);
								if (n != 0 && n <= 1024 && read(base, bytes) != nullptr) bc5_range_remember(ib, buf_no, i, "reg table", base, bytes);
							}
						}
						i += len;
					}
				}""")

rep("""		if (ibd.count != 0 && !ibd.dir.empty() && num_dwords >= ibd.lo && num_dwords <= ibd.hi && timing_now() >= ibd.t0 && ibd_n.load() < ibd.count) {
			const uint32_t k = ibd_n++;
			if (k < ibd.count) {
				char name[512];
				std::snprintf(name, sizeof(name), "%s/ib-%08" PRIu64 "-%.8s-%u.bin", ibd.dir.c_str(), g_submits.load(), kind, num_dwords);""",
    """		const bool ui_pick = ibd.lo == 0 && ibd.hi == 0 && t_ui_buffer; // experiment 0157
		if (ibd.count != 0 && !ibd.dir.empty() && ((num_dwords >= ibd.lo && num_dwords <= ibd.hi) || ui_pick) && timing_now() >= ibd.t0 && ibd_n.load() < ibd.count) {
			const uint32_t k = ibd_n++;
			if (k < ibd.count) {
				char name[512];
				if (ui_pick)
					std::snprintf(name, sizeof(name), "%s/ib-%08" PRIu64 "-%.8s-%u-buf%u.bin", ibd.dir.c_str(), g_submits.load(), kind, num_dwords, t_ui_buf_no);
				else
					std::snprintf(name, sizeof(name), "%s/ib-%08" PRIu64 "-%.8s-%u.bin", ibd.dir.c_str(), g_submits.load(), kind, num_dwords);""")

open(p, "w", encoding="utf-8", newline="").write(s)
print("ok")
