p = "/home/kjaniszewski/src/KytyPlus/src/libs/bc5LleAgc.cpp"
s = open(p, encoding="utf-8", newline="").read()
nl = "\r\n" if "\r\n" in s else "\n"


def rep(a, b):
    global s
    a = a.replace("\n", nl)
    b = b.replace("\n", nl)
    assert s.count(a) == 1, (a[:80], s.count(a))
    s = s.replace(a, b)


# copies: every 32nd job through the whole run (=2)
rep("""			static std::atomic<int> copies {0};
			if (keep_copy && copies.load() < 400 && num_dwords <= 200000) {
				copies++;
				it.job.copy.assign(ib, ib + num_dwords);
			}""", """			static std::atomic<uint64_t> copies {0};
			if (keep_copy && (copies++ & 31u) == 0 && num_dwords <= 200000) it.job.copy.assign(ib, ib + num_dwords);""")
# count NOP-payload vs packet diffs; journal only packet diffs and a summary
rep("""					if (!j.copy.empty() && c < 200) { // which dwords, in which packets""", """					if (!j.copy.empty()) { // which dwords, in which packets""")
rep("""							if (now[i] != j.copy[i]) {
								if (diffs++ < 12 && o < 820) {
									o += std::snprintf(line + o, sizeof(line) - static_cast<size_t>(o), " [%u: pkt %u op %02x +%u]", i, pk, (j.copy[pk] >> 8u) & 0xffu, i - pk);
								}
							}
						}
						journal("%s (%u dwords differ)\\n", line, diffs);""", """							if (now[i] != j.copy[i]) {
								const bool nop_payload = (j.copy[pk] >> 30u) == 3 && ((j.copy[pk] >> 8u) & 0xffu) == 0x10 && i > pk;
								if (nop_payload) continue;
								if (diffs++ < 12 && o < 820) {
									o += std::snprintf(line + o, sizeof(line) - static_cast<size_t>(o), " [%u: pkt %u op %02x +%u]", i, pk, (j.copy[pk] >> 8u) & 0xffu, i - pk);
								}
							}
						}
						static std::atomic<uint64_t> copied {0}, packet_changed {0};
						copied++;
						if (diffs != 0) {
							if (packet_changed++ < 60) journal("%s (%u packet dwords differ, NOP payloads not counted)\\n", line, diffs);
						}
						if ((copied.load() & 255u) == 0) {
							journal("ib stable diff: %" PRIu64 " changed jobs compared, %" PRIu64 " with a change outside NOP payloads\\n", copied.load(), packet_changed.load());
						}""")
open(p, "w", encoding="utf-8", newline="").write(s)
print("ok")
