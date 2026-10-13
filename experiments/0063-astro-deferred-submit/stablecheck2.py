p = "/home/kjaniszewski/src/KytyPlus/src/libs/bc5LleAgc.cpp"
s = open(p, encoding="utf-8", newline="").read()
nl = "\r\n" if "\r\n" in s else "\n"


def rep(a, b):
    global s
    a = a.replace("\n", nl)
    b = b.replace("\n", nl)
    assert s.count(a) == 1, (a[:80], s.count(a))
    s = s.replace(a, b)


rep("""	uint64_t                                    ib_hash = 0;
	std::vector<std::pair<const uint32_t*, uint32_t>> hashed;
};""", """	uint64_t                                    ib_hash = 0;
	std::vector<std::pair<const uint32_t*, uint32_t>> hashed;
	std::vector<uint32_t>                       copy; // BC5_DIRECT_IB_STABLE_CHECK=2: the main buffer at submission
};""")
rep("""			it.job.ib_hash = ib_hash(it.job.hashed);
		}""", """			it.job.ib_hash = ib_hash(it.job.hashed);
			static const bool keep_copy = std::getenv("BC5_DIRECT_IB_STABLE_CHECK")[0] == '2';
			static std::atomic<int> copies {0};
			if (keep_copy && copies.load() < 400 && num_dwords <= 200000) {
				copies++;
				it.job.copy.assign(ib, ib + num_dwords);
			}
		}""")
rep("""				if (ib_hash(j.hashed) != j.ib_hash) {
					const uint64_t c = changed++;
					changed_dwords += n_dw;""", """				if (ib_hash(j.hashed) != j.ib_hash) {
					const uint64_t c = changed++;
					changed_dwords += n_dw;
					if (!j.copy.empty() && c < 200) { // which dwords, in which packets
						const auto* now = reinterpret_cast<const volatile uint32_t*>(j.ib);
						char        line[900];
						int         o = std::snprintf(line, sizeof(line), "ib stable diff: #%" PRIu64 " %s %u dwords:", j.n, j.kind, j.num_dwords);
						uint32_t    diffs = 0, pk = 0, pk_len = 1;
						for (uint32_t i = 0; i < j.num_dwords; i++) {
							while (pk + pk_len <= i) { // the packet holding dword i (walked on the copy)
								pk += pk_len;
								const uint32_t h = j.copy[pk];
								const uint32_t c2 = (h >> 16u) & 0x3fffu;
								pk_len = ((h >> 30u) == 3 || (h >> 30u) == 0) ? (c2 == 0x3fffu ? 1 : c2 + 2) : 1;
							}
							if (i == 0) {
								const uint32_t h = j.copy[0];
								const uint32_t c2 = (h >> 16u) & 0x3fffu;
								pk_len = ((h >> 30u) == 3 || (h >> 30u) == 0) ? (c2 == 0x3fffu ? 1 : c2 + 2) : 1;
							}
							if (now[i] != j.copy[i]) {
								if (diffs++ < 12 && o < 820) {
									o += std::snprintf(line + o, sizeof(line) - static_cast<size_t>(o), " [%u: pkt %u op %02x +%u]", i, pk, (j.copy[pk] >> 8u) & 0xffu, i - pk);
								}
							}
						}
						journal("%s (%u dwords differ)\\n", line, diffs);
					}""")
open(p, "w", encoding="utf-8", newline="").write(s)
print("ok")
