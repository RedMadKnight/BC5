// ---- experiment 0379: the zero list (BC5_DIRECT_ZEROSCAN_AT/_OUT) and the skip (BC5_DIRECT_ZERO_SKIP) ---------------
// RenderGpuWcLarge and CommitIABufferAllocator are eager, so every chunk of them is pinned, and exp 0333 found ~2.8 GB
// of them all-zero for 20 minutes (F402); with RT on the box then runs out of page cache (F505). A diagnostic run scans
// the named heaps (BC5_DIRECT_ZERO_NAMES) on a background thread at the given times and writes the chunks that were
// all-zero in every scan (bc5/zero_skip.hpp). A later run leaves those chunks out of the eager import. Each skipped
// run is mapped onto its own 2 MiB slice of one canary BO at every VA that maps it, so a GPU access never faults: a
// read gets zeros, a write shows in the slice, which a background thread checks (one slice per 50 ms), and the run
// is then taken back. A CPU write (SEEK_DATA), a hint window and a device reopen take chunks back too; a learned
// window does not (the learned windows in these heaps predate their eager import, F96). Off unless
// BC5_DIRECT_ZERO_SKIP names a list.
static const std::vector<std::string>& zero_names() {
	static const std::vector<std::string> names = [] {
		std::vector<std::string> v;
		const char*              e = std::getenv("BC5_DIRECT_ZERO_NAMES");
		std::string              s = e != nullptr ? e : "RenderGpuWcLarge,CommitIABufferAllocator", cur;
		for (const char c: s + ",") {
			if (c == ',') {
				if (!cur.empty()) v.push_back(cur);
				cur.clear();
			} else {
				cur.push_back(c);
			}
		}
		return v;
	}();
	return names;
}
// The file range a named heap's eager views span (the lowest offset and the span), 0 when none is there yet.
static std::pair<uint64_t, uint64_t> zero_heap_span(const std::vector<DView>& views, const std::string& name) {
	uint64_t lo = ~0ull, hi = 0;
	for (const auto& v: views) {
		if (!v.eager || v.name != name) continue;
		lo = std::min(lo, v.off);
		hi = std::max(hi, v.off + v.size);
	}
	return hi > lo ? std::pair<uint64_t, uint64_t> {lo, hi - lo} : std::pair<uint64_t, uint64_t> {0, 0};
}

// The diagnostic scan (arm S).
struct ZScanHeap {
	std::string                                  name;
	uint64_t                                     base = 0, span = 0;
	std::vector<std::pair<uint64_t, uint64_t>> ranges; // the views' file ranges
};
static std::mutex                                      g_zscan_mutex;
static std::map<std::string, bc5::zero_skip::ZeroMask> g_zscan_masks;
static std::map<std::string, uint64_t>                 g_zscan_spans;
static std::atomic<bool>                               g_zscan_busy {false};
static void zscan_run(int fd, std::vector<ZScanHeap> heaps, double t_start, uint32_t k) {
	setpriority(PRIO_PROCESS, static_cast<id_t>(syscall(SYS_gettid)), 19);
	const char*         out     = std::getenv("BC5_DIRECT_ZEROSCAN_OUT");
	const uint64_t      min_mib = std::getenv("BC5_DIRECT_ZERO_MIN_MIB") != nullptr ? std::strtoull(std::getenv("BC5_DIRECT_ZERO_MIN_MIB"), nullptr, 10) : 8ull;
	std::vector<char>   buf(kDChunk);
	std::vector<bc5::zero_skip::Heap> list;
	for (const auto& h: heaps) {
		const size_t         n = static_cast<size_t>((h.span + kDChunk - 1) / kDChunk);
		std::vector<uint8_t> now(n, 0);
		uint64_t             zero_now = 0;
		for (size_t i = 0; i < n; i++) {
			const uint64_t c = h.base + static_cast<uint64_t>(i) * kDChunk;
			bool           in = false;
			for (const auto& [a, b]: h.ranges) in = in || (c >= a && c + kDChunk <= b);
			if (!in) continue; // not wholly inside a view: never listed
			const ssize_t r = pread(fd, buf.data(), kDChunk, static_cast<off_t>(c));
			if (r == static_cast<ssize_t>(kDChunk) && bc5::zero_skip::all_zero(buf.data(), kDChunk)) {
				now[i] = 1;
				zero_now += kDChunk;
			}
		}
		std::lock_guard lk(g_zscan_mutex);
		if (auto s = g_zscan_spans.find(h.name); s != g_zscan_spans.end() && s->second != h.span) {
			journal("zero scan %u: %s spans 0x%" PRIx64 ", not 0x%" PRIx64 " as before: its mask starts again\n", k, h.name.c_str(), h.span, s->second);
			g_zscan_masks.erase(h.name);
		}
		g_zscan_spans[h.name] = h.span;
		auto& m = g_zscan_masks.try_emplace(h.name, h.span).first->second;
		m.intersect(now);
		bc5::zero_skip::Heap lh {h.name, h.span, m.scans(), m.runs(h.span, min_mib << 20u)};
		uint64_t             listed = 0;
		for (const auto& [o, l]: lh.runs) listed += l;
		journal("zero scan %u at t %.1f s: %s %.1f MiB, zero now %.1f MiB, zero in all %u scans %.1f MiB, listed %.1f MiB in %zu runs of >= %" PRIu64 " MiB (%.0f ms)\n", k,
		        t_start, h.name.c_str(), static_cast<double>(h.span) / 1048576.0, static_cast<double>(zero_now) / 1048576.0, m.scans(),
		        static_cast<double>(m.zero_bytes()) / 1048576.0, static_cast<double>(listed) / 1048576.0, lh.runs.size(), min_mib, (timing_now() - t_start) * 1000.0);
		list.push_back(std::move(lh));
	}
	if (out != nullptr) {
		const std::string tmp = std::string(out) + ".tmp";
		if (FILE* f = std::fopen(tmp.c_str(), "w")) {
			const std::string text = bc5::zero_skip::format_list(list);
			const bool        ok   = std::fwrite(text.data(), 1, text.size(), f) == text.size();
			if (std::fclose(f) == 0 && ok && std::rename(tmp.c_str(), out) == 0) journal("zero scan %u: list written to %s\n", k, out);
		}
	}
	g_zscan_busy = false;
}
static void zscan_tick(const DState& S, const std::vector<DView>& views) {
	static const std::vector<double> at = [] {
		std::vector<double> v;
		if (const char* e = BC5_DIAG_ENV("BC5_DIRECT_ZEROSCAN_AT"); e != nullptr) {
			for (const char* p = e; *p != 0;) {
				char* end = nullptr;
				const double t = std::strtod(p, &end);
				if (end == p) break;
				v.push_back(t);
				p = *end == ',' ? end + 1 : end;
			}
			std::sort(v.begin(), v.end());
		}
		return v;
	}();
	static size_t   next = 0;
	static uint32_t k    = 0;
	if (S.kind != 0 || next >= at.size() || timing_now() < at[next] || g_zscan_busy) return;
	const double t = timing_now();
	while (next < at.size() && at[next] <= t) next++; // times that passed while a scan ran go to this one
	std::vector<ZScanHeap> heaps;
	for (const auto& name: zero_names()) {
		const auto [base, span] = zero_heap_span(views, name);
		if (span == 0) continue;
		ZScanHeap h {name, base, span, {}};
		for (const auto& v: views) {
			if (v.eager && v.name == name) h.ranges.emplace_back(v.off, v.off + v.size);
		}
		heaps.push_back(std::move(h));
	}
	const int fd = dstate_fd(S);
	if (heaps.empty() || fd < 0) return;
	g_zscan_busy = true;
	std::thread(zscan_run, fd, std::move(heaps), t, ++k).detach();
}

// The skip (arm B). One thread does the sync, the forcing and the mapping (as the rest of this path); the canary
// thread only reads the slices and raises a run's flag.
static bc5::zero_skip::SkipSet                  g_zskip;
struct ZPiece { uint64_t size; uint32_t run; };
static std::map<uint64_t, ZPiece>               g_zpieces; // canary mappings by VA
static std::set<std::string>                    g_zskip_placed; // list heaps placed or refused
static std::vector<bc5::zero_skip::Heap>        g_zskip_list;
static bool                                     g_zskip_off = false;
static int                                      g_zcanary_fd = -1;
static uint32_t                                 g_zcanary_id = 0;
static const unsigned char*                     g_zcanary_cpu = nullptr;
static std::unique_ptr<std::atomic<uint8_t>[]>  g_zflag; // per run: 0 watched, 1 hit (not yet taken back), 2 done
static size_t                                   g_zruns = 0; // the list's runs: one slice each, whatever order the heaps are placed in
static std::vector<uint64_t>                    g_zleft; // per run: bytes still skipped (0: nothing to look at)
static std::atomic<bool>                        g_zcanary_stop {false};
static uint64_t g_zstat_cpu = 0, g_zstat_hint = 0, g_zstat_hits = 0, g_zstat_placed = 0;
static thread_local bool t_force_learned = false; // direct_force called for a learned window (map_window)
static const char* zskip_path() {
	static const char* p = std::getenv("BC5_DIRECT_ZERO_SKIP");
	return p;
}
static void zcanary_watch(size_t runs) {
	setpriority(PRIO_PROCESS, static_cast<id_t>(syscall(SYS_gettid)), 10);
	for (size_t r = 0; !g_zcanary_stop; r = (r + 1) % runs) {
		std::this_thread::sleep_for(std::chrono::milliseconds(50));
		if (g_zflag[r].load() != 0) continue;
		const unsigned char* p = g_zcanary_cpu + r * kDChunk;
		// TODO(verify): whether the CPU sees the GPU's writes to an imported udmabuf page without a flush; the
		// lines are flushed first, so a stale cached zero line cannot hide a write.
		for (uint64_t o = 0; o < kDChunk; o += 64) __builtin_ia32_clflush(p + o);
		__builtin_ia32_mfence();
		if (!bc5::zero_skip::all_zero(p, kDChunk)) g_zflag[r] = 1;
	}
}
// Unmaps the canary mappings that overlap [lo, hi) (a real mapping is about to go there).
static void zskip_release(uint64_t lo, uint64_t hi) {
	auto it = g_zpieces.lower_bound(lo >= kDChunk ? lo - kDChunk : 0);
	while (it != g_zpieces.end() && it->first < hi) {
		if (it->first + it->second.size > lo) {
			if (g_dev) g_dev->unmap_shared(it->first);
			it = g_zpieces.erase(it);
		} else {
			++it;
		}
	}
}
// Maps the canary under every skipped chunk at every VA a view gives it, where no canary is yet.
static void zskip_map(const std::vector<DView>& views) {
	if (g_zskip.empty() || g_zcanary_id == 0 || !g_dev) return;
	uint32_t added = 0, failed = 0;
	for (const auto& v: views) {
		for (const uint64_t c: g_zskip.chunks_in(v.off, v.off + v.size)) {
			const uint64_t lo = std::max(c, v.off), hi = std::min(c + kDChunk, v.off + v.size);
			if (lo >= hi) continue;
			const uint64_t va = v.va + (lo - v.off);
			if (g_zpieces.count(va) != 0) continue;
			const long run = g_zskip.run_of(c);
			if (run < 0) continue;
			if (g_dev->map_shared(g_zcanary_id, static_cast<uint64_t>(run) * kDChunk + (lo - c), hi - lo, va)) {
				g_zpieces.emplace(va, ZPiece {hi - lo, static_cast<uint32_t>(run)});
				added++;
			} else {
				failed++;
			}
		}
	}
	if (added != 0 || failed != 0) journal("zero skip: canary +%u mappings (%zu)%s\n", added, g_zpieces.size(), failed != 0 ? "; SOME CANARY MAPS FAILED" : "");
}
// Places the list's heaps once their views are there (same span as in the list), before their first import.
static bool zskip_resolve(const std::vector<DView>& views) {
	if (zskip_path() == nullptr || g_zskip_off || g_zskip_placed.size() == g_zskip_list.size() + 1) return false;
	if (g_zskip_placed.empty()) { // first call: load the list
		g_zskip_placed.insert(""); // the marker that the list was read
		std::string text;
		if (FILE* f = std::fopen(zskip_path(), "r")) {
			char   b[4096];
			size_t n = 0;
			while ((n = std::fread(b, 1, sizeof b, f)) > 0) text.append(b, n);
			std::fclose(f);
		}
		uint32_t bad = 0;
		g_zskip_list = bc5::zero_skip::parse_list(text, &bad);
		uint64_t total = 0;
		for (const auto& h: g_zskip_list) {
			for (const auto& [o, l]: h.runs) total += l;
		}
		journal("zero skip: list %s, %zu heaps, %.1f MiB listed, %u bad lines\n", zskip_path(), g_zskip_list.size(), static_cast<double>(total) / 1048576.0, bad);
	}
	bool placed = false;
	for (const auto& h: g_zskip_list) {
		if (g_zskip_placed.count(h.name) != 0) continue;
		const auto [base, span] = zero_heap_span(views, h.name);
		if (span == 0) continue; // not there yet
		g_zskip_placed.insert(h.name);
		if (span != h.size) {
			journal("zero skip: %s spans 0x%" PRIx64 ", the list says 0x%" PRIx64 ": not skipped\n", h.name.c_str(), span, h.size);
			continue;
		}
		if (g_zskip.run_count() + h.runs.size() > (g_zruns != 0 ? g_zruns : ~size_t {0})) { journal("zero skip: %s: no canary slice left: not skipped\n", h.name.c_str()); continue; }
		const uint64_t n = bc5::zero_skip::place(h, base, &g_zskip);
		g_zstat_placed += n;
		placed = true;
		journal("zero skip: %s at file 0x%" PRIx64 ": %.1f MiB in %zu runs skipped\n", h.name.c_str(), base, static_cast<double>(n) / 1048576.0, h.runs.size());
	}
	if (!placed) return false;
	// The canary: one memfd BO with one 2 MiB slice for each run of the list, made at the first placement (add_run
	// numbers the runs in placement order, so every placed run has a slice).
	if (g_zcanary_id == 0 && g_zcanary_fd < 0) {
		g_zruns = 0;
		for (const auto& h: g_zskip_list) g_zruns += h.runs.size();
		const uint64_t size = static_cast<uint64_t>(g_zruns) * kDChunk;
		g_zcanary_fd = memfd_create("bc5-zero-canary", MFD_CLOEXEC | MFD_ALLOW_SEALING);
		void* cpu = MAP_FAILED;
		if (g_zcanary_fd >= 0 && ftruncate(g_zcanary_fd, static_cast<off_t>(size)) == 0 && fcntl(g_zcanary_fd, F_ADD_SEALS, F_SEAL_SHRINK) == 0) {
			cpu = mmap(nullptr, size, PROT_READ, MAP_SHARED, g_zcanary_fd, 0);
		}
		g_zcanary_id = cpu != MAP_FAILED && g_dev ? g_dev->import_memfd(g_zcanary_fd, 0, size) : 0;
		if (g_zcanary_id == 0) {
			journal("zero skip: the canary BO (%zu runs) could not be made: nothing skipped\n", g_zruns);
			g_zskip.clear();
			g_zskip_off = true;
			return false;
		}
		g_zcanary_cpu = static_cast<const unsigned char*>(cpu);
		g_zflag.reset(new std::atomic<uint8_t>[g_zruns]);
		g_zleft.assign(g_zruns, 0);
		for (size_t r = 0; r < g_zruns; r++) g_zflag[r] = 0;
		std::thread(zcanary_watch, g_zruns).detach();
		journal("zero skip: canary BO %u, %zu slices of 2 MiB\n", g_zcanary_id, g_zruns);
	}
	for (size_t r = 0; r < g_zskip.run_count() && r < g_zleft.size(); r++) {
		if (g_zleft[r] == 0 && g_zflag[r].load() == 0) g_zleft[r] = g_zskip.run_left(static_cast<uint32_t>(r));
	}
	return true;
}
// Takes back the chunks of skipped runs the CPU has written (SEEK_DATA) and the runs whose canary was hit.
static void zskip_take_back(DState& S, int fd) {
	if (S.kind != 0 || g_zskip.empty()) return;
	for (size_t r = 0; r < g_zskip.run_count() && r < g_zruns; r++) {
		if (g_zflag[r].load() != 1 || g_zleft[r] == 0) continue;
		g_zflag[r] = 2;
		const auto     [o, l] = g_zskip.run(static_cast<uint32_t>(r));
		const uint64_t n      = g_zskip.erase_run(static_cast<uint32_t>(r));
		g_zleft[r]            = 0;
		g_zstat_hits++;
		S.blocks = ~0ull;
		journal("zero skip: canary hit in run %zu (file 0x%" PRIx64 " +%.1f MiB): %.1f MiB taken back\n", r, o, static_cast<double>(l) / 1048576.0, static_cast<double>(n) / 1048576.0);
	}
	for (size_t r = 0; r < g_zskip.run_count() && r < g_zleft.size(); r++) {
		if (g_zleft[r] == 0) continue;
		const auto [o, l] = g_zskip.run(static_cast<uint32_t>(r));
		for (uint64_t pos = o; pos < o + l;) {
			const off_t d = lseek(fd, static_cast<off_t>(pos), SEEK_DATA);
			if (d < 0 || static_cast<uint64_t>(d) >= o + l) break;
			const uint64_t c = static_cast<uint64_t>(d) & ~(kDChunk - 1);
			if (g_zskip.run_of(c) == static_cast<long>(r) && g_zskip.erase_chunk(c)) {
				g_zstat_cpu++;
				g_zleft[r] -= kDChunk;
			}
			pos = c + kDChunk;
		}
	}
}
static void zskip_report() {
	static double last = 0.0;
	if (zskip_path() == nullptr || g_zskip_placed.empty() || timing_now() - last < 60.0) return;
	last = timing_now();
	journal("zero skip: %.1f MiB still skipped of %.1f placed; taken back: %" PRIu64 " chunks by CPU writes, %" PRIu64 " by hints, %" PRIu64 " runs by canary hits; %zu canary mappings%s\n",
	        static_cast<double>(g_zskip.bytes()) / 1048576.0, static_cast<double>(g_zstat_placed) / 1048576.0, g_zstat_cpu, g_zstat_hint, g_zstat_hits, g_zpieces.size(),
	        g_zskip_off ? "; OFF" : "");
}
// After a device reopen the canary BO and its mappings are gone: the skip ends and everything is imported.
static void zskip_disable(const char* why) {
	if (zskip_path() == nullptr) return;
	g_zcanary_stop = true;
	g_zskip.clear();
	g_zpieces.clear();
	g_zcanary_id = 0;
	g_zskip_off  = true;
	journal("zero skip: off (%s)\n", why);
}

