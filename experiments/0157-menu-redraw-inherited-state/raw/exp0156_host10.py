#!/usr/bin/env python3
# Experiment 0157, tenth step: (a) BC5_DIRECT_RT_DUMP_AT_COMPLETION=1 dumps the RT_DUMP items again at the fence
# completion of every buffer the draw journal matched (file tag -buf<N>-done); (b) BC5_DIRECT_DRAW_JOURNAL_ACB=1
# runs the draw journal (and FIND) over the compute-queue buffers too; (c) the FIND list accepts "layer": the
# UI layer 0 base the draw journal last saw.
p = "/home/kjaniszewski/src/KytyPlus/src/libs/bc5LleAgc.cpp"
s = open(p, encoding="utf-8", newline="").read()


def rep(a, b):
    global s
    assert s.count(a) == 1, (s.count(a), a[:80])
    s = s.replace(a, b)


# (a) force + tag
rep("""static void bc5_rt_dump_once(const std::shared_ptr<const std::vector<bc5::direct::Mapping>>& maps_p) {""",
    """static void bc5_rt_dump_once(const std::shared_ptr<const std::vector<bc5::direct::Mapping>>& maps_p, bool force = false, const char* tag = nullptr) {""")

rep("""	if (spec.empty() || done.load()) return;
	const double t0    = std::strtod(spec.c_str(), nullptr);
	const double now_t = timing_now();
	if (now_t < t0) return;
	if (every > 0) {
		std::lock_guard lock(every_mutex);
		if (next_t < 0) next_t = t0;
		if (now_t < next_t) return;
		next_t = now_t + every;
	} else if (done.exchange(true)) {
		return;
	}
	const double dump_t = now_t;""",
    """	if (spec.empty() || (!force && done.load())) return;
	const double t0    = std::strtod(spec.c_str(), nullptr);
	const double now_t = timing_now();
	if (!force) {
		if (now_t < t0) return;
		if (every > 0) {
			std::lock_guard lock(every_mutex);
			if (next_t < 0) next_t = t0;
			if (now_t < next_t) return;
			next_t = now_t + every;
		} else if (done.exchange(true)) {
			return;
		}
	}
	const double dump_t = now_t;
	char         tagbuf[72] = {};
	if (tag != nullptr) std::snprintf(tagbuf, sizeof(tagbuf), "-%s", tag);""")

rep("""		if (every > 0)
			std::snprintf(name, sizeof(name), "%s/rt-%010" PRIx64 "-%ux%u-%s-f%u-t%07.2f.ppm", g_dump_dir.c_str(), va, w, h, fmt, family, dump_t);
		else
			std::snprintf(name, sizeof(name), "%s/rt-%010" PRIx64 "-%ux%u-%s-f%u.ppm", g_dump_dir.c_str(), va, w, h, fmt, family);""",
    """		if (every > 0 || force)
			std::snprintf(name, sizeof(name), "%s/rt-%010" PRIx64 "-%ux%u-%s-f%u-t%07.2f%s.ppm", g_dump_dir.c_str(), va, w, h, fmt, family, dump_t, tagbuf);
		else
			std::snprintf(name, sizeof(name), "%s/rt-%010" PRIx64 "-%ux%u-%s-f%u.ppm", g_dump_dir.c_str(), va, w, h, fmt, family);""")

rep("""	journal("ranges at completion: submit #%" PRIu64 " buf %u: %zu intact, %zu rewritten, %zu unreadable; %.1f ms from the first draw's journal to completion\\n", n, mine.front().buf, intact, rewritten,
	        unreadable, (now - mine.front().t) * 1000.0);
}""",
    """	journal("ranges at completion: submit #%" PRIu64 " buf %u: %zu intact, %zu rewritten, %zu unreadable; %.1f ms from the first draw's journal to completion\\n", n, mine.front().buf, intact, rewritten,
	        unreadable, (now - mine.front().t) * 1000.0);
	// Experiment 0157: BC5_DIRECT_RT_DUMP_AT_COMPLETION=1 dumps the RT_DUMP items now, as the GPU left them.
	static const bool dump_done = std::getenv("BC5_DIRECT_RT_DUMP_AT_COMPLETION") != nullptr;
	if (dump_done) {
		char tag[40];
		std::snprintf(tag, sizeof(tag), "buf%u-done", mine.front().buf);
		bc5_rt_dump_once(maps_p, true, tag);
	}
}""")

# (b) acb buffers through the journal path
rep("""	if (!pieces_dry() && !pieces_full() && draw_journal.second == 0) return;
	if (std::strcmp(kind, "cc") != 0 && std::strcmp(kind, "hib") != 0 && std::strcmp(kind, "dcb") != 0) return;""",
    """	if (!pieces_dry() && !pieces_full() && draw_journal.second == 0) return;
	// Experiment 0157: BC5_DIRECT_DRAW_JOURNAL_ACB=1 takes the compute-queue buffers through the journal too
	// (as "dcb" below; their packets set SH registers only, so the shared tracker is not disturbed).
	static const bool journal_acb = std::getenv("BC5_DIRECT_DRAW_JOURNAL_ACB") != nullptr;
	const bool        acb_as_dcb  = journal_acb && draw_journal.second != 0 && std::strcmp(kind, "acb") == 0;
	if (acb_as_dcb) kind = "dcb";
	if (std::strcmp(kind, "cc") != 0 && std::strcmp(kind, "hib") != 0 && std::strcmp(kind, "dcb") != 0) return;""")

# (c) FIND "layer"
rep("""					static const std::vector<uint32_t> find = [] {
						std::vector<uint32_t> v;
						if (const char* e = std::getenv("BC5_DIRECT_DRAW_JOURNAL_FIND"); e != nullptr) {
							for (const char* q = e; *q != 0;) {
								char* end = nullptr;
								v.push_back(static_cast<uint32_t>(std::strtoul(q, &end, 16)));
								if (end == q) break;
								q = *end == ',' ? end + 1 : end;
							}
						}
						return v;
					}();
					if (!find.empty()) {""",
    """					static const std::vector<uint32_t> find = [] {
						std::vector<uint32_t> v;
						if (const char* e = std::getenv("BC5_DIRECT_DRAW_JOURNAL_FIND"); e != nullptr) {
							for (const char* q = e; *q != 0;) {
								if (*q == 'l') { // experiment 0157: the "layer" token
									while (*q != 0 && *q != ',') q++;
									if (*q == ',') q++;
									continue;
								}
								char* end = nullptr;
								v.push_back(static_cast<uint32_t>(std::strtoul(q, &end, 16)));
								if (end == q) break;
								q = *end == ',' ? end + 1 : end;
							}
						}
						return v;
					}();
					static const bool find_layer = [] {
						const char* e = std::getenv("BC5_DIRECT_DRAW_JOURNAL_FIND");
						return e != nullptr && std::strstr(e, "layer") != nullptr;
					}();
					const uint32_t layer_hi = find_layer ? static_cast<uint32_t>(g_layer0_base.load() >> 8u) : 0u;
					auto           is_hit   = [&](uint32_t v) { return (layer_hi != 0 && v == layer_hi) || std::find(find.begin(), find.end(), v) != find.end(); };
					if (!find.empty() || layer_hi != 0) {""")

rep("""							bool hit = std::find(find.begin(), find.end(), ud[k]) != find.end();
							const char* where = "direct";""",
    """							bool hit = is_hit(ud[k]);
							const char* where = "direct";""")

rep("""									for (uint32_t q = 0; q < 64 && !hit; q++) {
										if (std::find(find.begin(), find.end(), m[q]) != find.end()) {
											hit   = true;
											where = "table";""",
    """									for (uint32_t q = 0; q < 64 && !hit; q++) {
										if (is_hit(m[q])) {
											hit   = true;
											where = "table";""")

# the FIND block must also run when only the layer token is set: find_set
rep("""				static const bool find_set = std::getenv("BC5_DIRECT_DRAW_JOURNAL_FIND") != nullptr;""",
    """				static const bool find_set = std::getenv("BC5_DIRECT_DRAW_JOURNAL_FIND") != nullptr; // "layer" counts too""")

open(p, "w", encoding="utf-8", newline="").write(s)
print("ok")
