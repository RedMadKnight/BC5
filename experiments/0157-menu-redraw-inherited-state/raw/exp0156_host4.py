#!/usr/bin/env python3
# Experiment 0156, fourth step: a BC5_DIRECT_DRAW_JOURNAL_FIND hit also journals the packet's user data and
# the 64 dwords of the table the hit was found in (the compute writers of the glyph atlases).
p = "/home/kjaniszewski/src/KytyPlus/src/libs/bc5LleAgc.cpp"
s = open(p, encoding="utf-8", newline="").read()


def rep(a, b):
    global s
    assert s.count(a) == 1, (s.count(a), a[:80])
    s = s.replace(a, b)


rep("""						for (uint32_t k = 0; k < nud; k++) {
							bool hit = std::find(find.begin(), find.end(), ud[k]) != find.end();
							const char* where = "direct";
							uint64_t    at    = 0;
							if (!hit && k + 1 < nud) {
								const uint64_t addr = ud[k] | (static_cast<uint64_t>(ud[k + 1] & 0xffffu) << 32u);
								if (addr >= 0x1000000000ull && addr < 0x1400000000ull && (addr & 3u) == 0 && read(addr, 256) != nullptr) {
									const auto* m = reinterpret_cast<const uint32_t*>(addr);
									for (uint32_t q = 0; q < 64 && !hit; q++) {
										if (std::find(find.begin(), find.end(), m[q]) != find.end()) {
											hit   = true;
											where = "table";
											at    = addr + q * 4u;
										}
									}
								}
							}
							if (hit) {
								journal("draw journal find: %s %s ud%u (%08x) %s %010" PRIx64 " | rt0 %010" PRIx64 " | ps %010" PRIx64 " cs %010" PRIx64 " | pkt%s\\n", compute ? "dispatch" : "draw",
								        compute ? "cs" : "ps", k, ud[k], where, at, rt, ps, cs, words);
								break;
							}
						}""",
    """						for (uint32_t k = 0; k < nud; k++) {
							bool hit = std::find(find.begin(), find.end(), ud[k]) != find.end();
							const char* where = "direct";
							uint64_t    at    = 0, tab = 0;
							if (!hit && k + 1 < nud) {
								const uint64_t addr = ud[k] | (static_cast<uint64_t>(ud[k + 1] & 0xffffu) << 32u);
								if (addr >= 0x1000000000ull && addr < 0x1400000000ull && (addr & 3u) == 0 && read(addr, 256) != nullptr) {
									const auto* m = reinterpret_cast<const uint32_t*>(addr);
									for (uint32_t q = 0; q < 64 && !hit; q++) {
										if (std::find(find.begin(), find.end(), m[q]) != find.end()) {
											hit   = true;
											where = "table";
											at    = addr + q * 4u;
											tab   = addr;
										}
									}
								}
							}
							if (hit) {
								journal("draw journal find: %s %s ud%u (%08x) %s %010" PRIx64 " | rt0 %010" PRIx64 " | ps %010" PRIx64 " cs %010" PRIx64 " | pkt%s\\n", compute ? "dispatch" : "draw",
								        compute ? "cs" : "ps", k, ud[k], where, at, rt, ps, cs, words);
								// Experiment 0156: the packet's user data and, for a table hit, the table's 64 dwords.
								if (compute) {
									char u[200] = {};
									int  uw     = 0;
									for (uint32_t q = 0; q < nud && uw < 180; q++) uw += std::snprintf(u + uw, sizeof(u) - static_cast<size_t>(uw), " %08x", ud[q]);
									journal("find ud cs %010" PRIx64 " t %.3f:%s\\n", cs, timing_now(), u);
								}
								if (tab != 0 && read(tab, 256) != nullptr) {
									const auto* m       = reinterpret_cast<const uint32_t*>(tab);
									char        tb[640] = {};
									int         tw      = 0;
									for (uint32_t q = 0; q < 64; q++) tw += std::snprintf(tb + tw, sizeof(tb) - static_cast<size_t>(tw), " %08x", m[q]);
									journal("find table %010" PRIx64 ":%s\\n", tab, tb);
								}
								break;
							}
						}""")

open(p, "w", encoding="utf-8", newline="").write(s)
print("ok")
