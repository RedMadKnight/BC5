#!/usr/bin/env python3
# Experiment 0157, seventh step: the memory a filtered draw reads (its vertex and index ranges, the tables
# behind the PS and GS user data, the paint V# at PS table 28 + 0x20) is remembered at submission and
# compared again when the buffer's fence completes (completion_thread): ranges the title rewrote while the
# buffer was in flight are journaled per buffer. Replaces the per-frame re-check of step six.
p = "/home/kjaniszewski/src/KytyPlus/src/libs/bc5LleAgc.cpp"
s = open(p, encoding="utf-8", newline="").read()


def rep(a, b):
    global s
    assert s.count(a) == 1, (s.count(a), a[:80])
    s = s.replace(a, b)


# globals before piece_check
rep("""static void piece_check(const uint32_t* ib, uint32_t num_dwords, const char* kind) {""",
    """// Experiment 0157: memory a journaled draw reads, remembered at submission (bc5_range_remember) and
// compared at the buffer's fence completion (bc5_ranges_complete, completion_thread): a range the
// title rewrote while the buffer was in flight is journaled with the draw it belonged to.
struct Bc5ReadRange {
	const void*          ib;
	uint32_t             buf, off;
	const char*          kind;
	uint64_t             addr;
	double               t;
	std::vector<uint8_t> copy;
};
static std::vector<Bc5ReadRange> g_read_ranges;
static std::mutex                g_read_ranges_mutex;
static void bc5_range_remember(const void* ib, uint32_t buf, uint32_t off, const char* kind, uint64_t addr, size_t len) {
	std::lock_guard lock(g_read_ranges_mutex);
	if (g_read_ranges.size() >= 65536) return;
	for (const Bc5ReadRange& r: g_read_ranges)
		if (r.ib == ib && r.addr == addr && r.copy.size() == len) return;
	Bc5ReadRange r {ib, buf, off, kind, addr, timing_now(), {}};
	r.copy.assign(reinterpret_cast<const uint8_t*>(addr), reinterpret_cast<const uint8_t*>(addr) + len);
	g_read_ranges.push_back(std::move(r));
}
static void bc5_ranges_complete(const void* ib, uint64_t n, const std::shared_ptr<const std::vector<bc5::direct::Mapping>>& maps_p) {
	std::vector<Bc5ReadRange> mine;
	{
		std::lock_guard lock(g_read_ranges_mutex);
		for (auto it = g_read_ranges.begin(); it != g_read_ranges.end();) {
			if (it->ib == ib) {
				mine.push_back(std::move(*it));
				it = g_read_ranges.erase(it);
			} else {
				++it;
			}
		}
	}
	if (mine.empty()) return;
	const double now     = timing_now();
	size_t       intact  = 0, rewritten = 0, unreadable = 0;
	for (const Bc5ReadRange& r: mine) {
		if (!covered_sorted(*maps_p, r.addr, r.copy.size())) {
			unreadable++;
			continue;
		}
		const auto* m = reinterpret_cast<const uint8_t*>(r.addr);
		if (std::memcmp(m, r.copy.data(), r.copy.size()) == 0) {
			intact++;
			continue;
		}
		rewritten++;
		size_t first = 0, count = 0;
		while (first < r.copy.size() && m[first] == r.copy[first]) first++;
		for (size_t q = 0; q < r.copy.size(); q++) count += m[q] != r.copy[q];
		journal("range rewritten in flight: submit #%" PRIu64 " buf %u at %u %s %010" PRIx64 "+%zx: %zu bytes differ from %zx; submitted t %.3f, completed t %.3f (%.1f ms)\\n", n, r.buf, r.off, r.kind, r.addr,
		        r.copy.size(), count, first, r.t, now, (now - r.t) * 1000.0);
	}
	journal("ranges at completion: submit #%" PRIu64 " buf %u: %zu intact, %zu rewritten, %zu unreadable; %.1f ms from the first draw's journal to completion\\n", n, mine.front().buf, intact, rewritten,
	        unreadable, (now - mine.front().t) * 1000.0);
}

static void piece_check(const uint32_t* ib, uint32_t num_dwords, const char* kind) {""")

# the per-frame re-check of step six goes
rep("""			struct VtxRange {
				uint64_t             addr;
				double               t;
				uint32_t             buf, off;
				std::vector<uint8_t> copy;
			};
			static std::vector<VtxRange> vtx_ranges;
			static std::mutex            vtx_mutex;
			{
				// the re-check of the remembered ranges (600 ms), on this buffer's submission
				std::lock_guard lock(vtx_mutex);
				const double    now = timing_now();
				for (auto it = vtx_ranges.begin(); it != vtx_ranges.end();) {
					if (now - it->t > 0.6) { it = vtx_ranges.erase(it); continue; }
					const uint32_t* m = read(it->addr, it->copy.size());
					if (m != nullptr && std::memcmp(m, it->copy.data(), it->copy.size()) != 0) {
						size_t first = 0;
						while (first < it->copy.size() && reinterpret_cast<const uint8_t*>(m)[first] == it->copy[first]) first++;
						journal("vertex rewrite: buf %u at %u range %010" PRIx64 "+%zx changed %.0f ms after submission (first byte %zx)\\n", it->buf, it->off, it->addr, it->copy.size(), (now - it->t) * 1000.0, first);
						it = vtx_ranges.erase(it);
						continue;
					}
					++it;
				}
			}""",
    """			// (the per-frame re-check of the vertex ranges became bc5_ranges_complete, at fence completion)""")

rep("""								std::lock_guard lock(vtx_mutex);
								if (vtx_ranges.size() < 4096) {
									VtxRange r {va0, timing_now(), buf_no, static_cast<uint32_t>(off), {}};
									r.copy.assign(reinterpret_cast<const uint8_t*>(va0), reinterpret_cast<const uint8_t*>(va0) + vlen);
									vtx_ranges.push_back(std::move(r));
								}""",
    """								bc5_range_remember(ib, buf_no, static_cast<uint32_t>(off), "vertices", va0, vlen);
								bc5_range_remember(ib, buf_no, static_cast<uint32_t>(off), "indices", ia, static_cast<size_t>(cnt) * isz);""")

# tables and the paint V#
rep("""							const auto* m = reinterpret_cast<const uint32_t*>(addr);
							char        tb[640] = {};
							int         tw      = 0;
							for (uint32_t q = 0; q < 64; q++) tw += std::snprintf(tb + tw, sizeof(tb) - static_cast<size_t>(tw), " %08x", m[q]);
							journal("bake table %s ud%u %010" PRIx64 ":%s\\n", stage == 0 ? "ps" : "gs", k, addr, tb);""",
    """							const auto* m = reinterpret_cast<const uint32_t*>(addr);
							char        tb[640] = {};
							int         tw      = 0;
							for (uint32_t q = 0; q < 64; q++) tw += std::snprintf(tb + tw, sizeof(tb) - static_cast<size_t>(tw), " %08x", m[q]);
							journal("bake table %s ud%u %010" PRIx64 ":%s\\n", stage == 0 ? "ps" : "gs", k, addr, tb);
							bc5_range_remember(ib, buf_no, static_cast<uint32_t>(off), stage == 0 ? "ps table" : "gs table", addr, 256);
							// the paint V# at PS table 28 + 0x20 (experiment 0104): its first 128 bytes
							if (stage == 0 && k == 28) {
								const uint64_t pv = m[8] | (static_cast<uint64_t>(m[9] & 0xffffu) << 32u);
								if (pv != 0 && read(pv, 128) != nullptr) bc5_range_remember(ib, buf_no, static_cast<uint32_t>(off), "paint", pv, 128);
							}""")

# the completion hook
rep("""				if (g_dev) r = g_dev->finish(j.seq, j.slot, 2'000'000'000ull);""",
    """				if (g_dev) r = g_dev->finish(j.seq, j.slot, 2'000'000'000ull);
				if (g_dev) bc5_ranges_complete(j.ib, j.n, g_dev->sorted_mappings()); // experiment 0157""")

open(p, "w", encoding="utf-8", newline="").write(s)
print("ok")
