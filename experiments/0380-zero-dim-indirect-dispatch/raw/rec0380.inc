// Experiment 0380 (F592, F595: the flight recorder's part A; BC5_0380_REC=1, default off). After a fence timeout, and
// after timeout_probe: where in the title's memory are the group counts the CP launched? It takes them from the newest
// event of sampler 0377 (its COMPUTE_DIM line, <BC5_0380_REC_SAMPLER_DIR or ~/bc5-data/captures/gpu-stall>/event-*/
// summary.txt, waiting up to 8 s for it), dumps 64 bytes at every SET_BASE 1 base, INDEX_BASE and indirect-argument
// address of the buffer and at the program, and scans every resident page of the GPU mappings (mincore: no page is
// faulted in; reads through process_vm_readv, so an unreadable page is counted, not fatal) for the three dwords
// together, each neighbouring pair and each one alone. A triple across a 64 KiB read block is missed. The scan stops
// after BC5_0380_REC_SCAN_S seconds (default 20). Results: <dump dir>/rec0380-<submission>-<kind>.txt (1 MiB at most,
// fsynced) and "rec0380:" journal lines, synced. CPU only: no packet is added to any buffer.
// Event matching (Codex review REVIEW-01 R1, F608): an event counts only if its directory names the ring
// (event-YYYYMMDD-HHMMSS-<ring>, BC5_0380_REC_RING, default gfx_0.0.0) and its summary.txt was written after the timed-out
// job was queued (the caller's age_s, less 1 s of slack; mtime in ns). Several matching events must agree on the dims.
// Otherwise, or with none within BC5_0380_REC_WAIT_S (default 8 s), the dims are "unknown" and nothing is scanned.
// BC5_0380_REC_SELFTEST_S=<s>: once, on the first completed dcb with an indirect dispatch after <s> s of journal time,
// the same with that dispatch's arguments as the dims (the dump path's check; it holds the completion thread for the
// scan).
static std::atomic<bool> g_rec0380_selftest_done {false};
static bool rec0380_selftest_due(const char* kind) {
	static const double at = [] {
		const char* e = BC5_DIAG_ENV("BC5_0380_REC_SELFTEST_S");
		return e != nullptr && *e != 0 ? std::atof(e) : -1.0;
	}();
	return at >= 0 && !g_rec0380_selftest_done.load() && std::strncmp(kind, "dcb", 3) == 0 && timing_now() >= at;
}
struct Rec0380Pick {
	bool               have = false;
	uint32_t           d[3] = {};
	unsigned long long prog = 0;
	std::string        src;
};
// One look at the sampler's directory: the events of `ring` written at or after not_before (CLOCK_REALTIME).
static Rec0380Pick rec0380_pick(const std::string& dir, const std::string& ring, const timespec& not_before) {
	Rec0380Pick              r;
	std::vector<std::string> names;
	if (DIR* dd = opendir(dir.c_str()); dd != nullptr) {
		while (const dirent* e = readdir(dd)) {
			const std::string nm = e->d_name;
			constexpr size_t  kStamp = 22; // "event-YYYYMMDD-HHMMSS-"
			if (nm.size() < kStamp + ring.size() || nm.compare(0, 6, "event-") != 0 || nm.compare(kStamp, ring.size(), ring) != 0) continue;
			if (nm.size() > kStamp + ring.size() && nm[kStamp + ring.size()] != '-') continue; // another ring with this one as prefix
			const std::string p = dir + "/" + nm + "/summary.txt";
			struct stat       st {};
			if (stat(p.c_str(), &st) != 0) continue;
			if (st.st_mtim.tv_sec < not_before.tv_sec || (st.st_mtim.tv_sec == not_before.tv_sec && st.st_mtim.tv_nsec < not_before.tv_nsec)) continue;
			names.push_back(p);
		}
		closedir(dd);
	}
	std::sort(names.begin(), names.end());
	int parsed = 0, disagree = 0;
	for (const auto& p: names) {
		FILE* f = std::fopen(p.c_str(), "r");
		if (f == nullptr) continue;
		char               line[600];
		unsigned long long pr = 0;
		unsigned           x = 0, y = 0, z = 0;
		bool               ok = false;
		while (!ok && std::fgets(line, sizeof(line), f) != nullptr) {
			const char* c = std::strstr(line, "compute: program=0x");
			ok            = c != nullptr && std::sscanf(c, "compute: program=0x%llx dim=[%u %u %u]", &pr, &x, &y, &z) == 4;
		}
		std::fclose(f);
		if (!ok) continue;
		if (parsed++ == 0) {
			r.d[0] = x, r.d[1] = y, r.d[2] = z, r.prog = pr, r.src = "sampler " + p;
		} else if (x != r.d[0] || y != r.d[1] || z != r.d[2] || pr != r.prog) {
			disagree++;
		}
	}
	if (parsed > 0 && disagree == 0) {
		r.have = true;
		if (parsed > 1) r.src += " (+" + std::to_string(parsed - 1) + " agreeing)";
	} else if (parsed > 0) {
		r.src = "unknown: " + std::to_string(parsed) + " events of " + ring + " in the window disagree";
		r.d[0] = r.d[1] = r.d[2] = 0, r.prog = 0;
	}
	return r;
}
// age_s: seconds since the timed-out job was queued (the event must be newer); < 0 in the self-test.
static bool rec0380(const uint32_t* sub_ib, uint32_t sub_n, const char* kind, uint64_t n, bool selftest, double age_s = -1.0) {
	if (sub_ib == nullptr || sub_n == 0 || g_dump_dir.empty() || !g_dev) return false;
	using clk     = std::chrono::steady_clock;
	const auto t0 = clk::now();
	auto       secs = [&] { return std::chrono::duration<double>(clk::now() - t0).count(); };
	const pid_t self = getpid();
	auto       safe_read = [&](uint64_t a, void* buf, size_t len) {
		iovec l {buf, len}, r {reinterpret_cast<void*>(a), len};
		return process_vm_readv(self, &l, 1, &r, 1, 0) == static_cast<ssize_t>(len);
	};
	auto pm = g_dev->sorted_mappings();
	// the buffer's bases and argument addresses, in order, without repeats
	std::vector<std::pair<const char*, uint64_t>> cand;
	auto add = [&](const char* what, uint64_t a) {
		if (a == 0 || cand.size() >= 64) return;
		for (const auto& c: cand)
			if (c.second == a) return;
		cand.emplace_back(what, a);
	};
	uint64_t b1 = 0, first_args = 0;
	uint32_t n_ind = 0;
	for (uint32_t q = 0; q < sub_n;) {
		const uint32_t h = sub_ib[q], type = h >> 30u;
		uint32_t       len = 1;
		if (type == 3 || type == 0) { const uint32_t c = (h >> 16u) & 0x3fffu; len = c == 0x3fffu ? 1 : c + 2; }
		if (q + len > sub_n) break;
		const uint32_t op = (h >> 8u) & 0xffu;
		if (type == 3 && op == 0x11 && len >= 4 && (sub_ib[q + 1] & 0xfu) == 1) {
			b1 = (sub_ib[q + 2] & ~3u) | (static_cast<uint64_t>(sub_ib[q + 3] & 0xffffu) << 32u);
			add("SET_BASE 1", b1);
		} else if (type == 3 && op == 0x26 && len >= 3) {
			add("INDEX_BASE", sub_ib[q + 1] | (static_cast<uint64_t>(sub_ib[q + 2] & 0xffffu) << 32u));
		} else if (type == 3 && op == 0x16 && len >= 3) {
			const uint64_t a = len >= 4 ? (sub_ib[q + 1] & ~3u) | (static_cast<uint64_t>(sub_ib[q + 2] & 0xffffu) << 32u) : b1 + sub_ib[q + 1];
			if (len >= 4 || b1 != 0) {
				add("arguments", a);
				if (first_args == 0) first_args = a;
			}
			n_ind++;
		}
		q += len;
	}
	if (selftest && first_args == 0) return false;
	journal("rec0380: #%" PRIu64 " %s: start (%s), %u dwords, %u indirect dispatches, %zu addresses\n", n, kind, selftest ? "self-test" : "timeout", sub_n, n_ind, cand.size());
	if (FILE* jf = journal_min_file(true); jf != nullptr) fsync(fileno(jf));
	// the launched group counts
	uint32_t           d[3] = {};
	unsigned long long prog = 0;
	bool               have = false;
	std::string        src;
	if (selftest) {
		have = safe_read(first_args, d, sizeof(d));
		char s[128];
		std::snprintf(s, sizeof(s), "self-test: the first indirect dispatch's arguments at 0x%" PRIx64, first_args);
		src = s;
	} else {
		std::string dir;
		if (const char* e = BC5_DIAG_ENV("BC5_0380_REC_SAMPLER_DIR"); e != nullptr && *e != 0) dir = e;
		else if (const char* home = std::getenv("HOME"); home != nullptr) dir = std::string(home) + "/bc5-data/captures/gpu-stall";
		std::string ring = "gfx_0.0.0";
		if (const char* e = BC5_DIAG_ENV("BC5_0380_REC_RING"); e != nullptr && *e != 0) ring = e;
		double wait_s = 8.0;
		if (const char* e = BC5_DIAG_ENV("BC5_0380_REC_WAIT_S"); e != nullptr && *e != 0) wait_s = std::atof(e);
		timespec nb {};
		clock_gettime(CLOCK_REALTIME, &nb);
		const double back = age_s + 1.0; // the job's age and 1 s of slack
		nb.tv_sec -= static_cast<time_t>(back);
		nb.tv_nsec -= static_cast<long>((back - static_cast<double>(static_cast<time_t>(back))) * 1e9);
		if (nb.tv_nsec < 0) nb.tv_nsec += 1000000000L, nb.tv_sec--;
		bool undecided = false;
		while (age_s >= 0 && !have && secs() < wait_s) {
			const Rec0380Pick pk = rec0380_pick(dir, ring, nb);
			if (pk.have) {
				d[0] = pk.d[0], d[1] = pk.d[1], d[2] = pk.d[2], prog = pk.prog, src = pk.src, have = true;
			} else if (!pk.src.empty()) {
				src = pk.src, undecided = true; // matching events that disagree: no dims
				break;
			} else {
				std::this_thread::sleep_for(std::chrono::milliseconds(100));
			}
		}
		char wb[96];
		std::snprintf(wb, sizeof(wb), "%.1f s", wait_s);
		if (age_s < 0) src = "unknown: the job's age is unknown";
		else if (!have && !undecided) src = "unknown: no event of " + ring + " newer than the job in " + dir + " within " + wb;
	}
	char name[512];
	std::snprintf(name, sizeof(name), "%s/rec0380-%08" PRIu64 "-%.8s.txt", g_dump_dir.c_str(), n, kind);
	FILE*  out   = std::fopen(name, "w");
	size_t bytes = 0;
	auto   emit  = [&](const char* s) {
		if (out == nullptr || bytes >= (1u << 20u)) return;
		std::fputs(s, out);
		bytes += std::strlen(s);
	};
	char ln[512];
	std::snprintf(ln, sizeof(ln), "rec0380 #%" PRIu64 " %s (%s), %u dwords, %u indirect dispatches\ndims %08x %08x %08x program 0x%llx (%s)\n", n, kind, selftest ? "self-test" : "timeout", sub_n, n_ind, d[0], d[1], d[2], prog, src.c_str());
	emit(ln);
	if (prog != 0) add("program", prog);
	for (const auto& [what, a]: cand) {
		uint32_t w[16];
		int      o = std::snprintf(ln, sizeof(ln), "dump %-10s 0x%" PRIx64 ":", what, a);
		if (safe_read(a, w, sizeof(w))) {
			for (const uint32_t v: w) o += std::snprintf(ln + o, sizeof(ln) - static_cast<size_t>(o), " %08x", v);
		} else {
			o += std::snprintf(ln + o, sizeof(ln) - static_cast<size_t>(o), " unreadable");
		}
		std::snprintf(ln + o, sizeof(ln) - static_cast<size_t>(o), "\n");
		emit(ln);
	}
	// the scan
	double cap = 20.0;
	if (const char* e = BC5_DIAG_ENV("BC5_0380_REC_SCAN_S"); e != nullptr && *e != 0) cap = std::atof(e);
	const uint64_t             pg = static_cast<uint64_t>(sysconf(_SC_PAGESIZE));
	constexpr uint64_t         kBlock = 64u << 10u;
	uint64_t                   scanned = 0, absent = 0, unreadable = 0, h3 = 0, h2[2] = {}, h1[3] = {};
	bool                       cut = false;
	std::vector<unsigned char> vec;
	std::vector<uint32_t>      buf(kBlock / 4);
	const double               t_scan = secs();
	auto hit = [&](const char* what, uint64_t a, const bc5::direct::Mapping& m) {
		std::snprintf(ln, sizeof(ln), "%s at 0x%" PRIx64 " (mapping 0x%" PRIx64 " +0x%" PRIx64 " of 0x%" PRIx64 "%s%s)\n", what, a, m.va, a - m.va, m.size, m.readonly ? ", read-only" : "", m.shared ? ", shared" : "");
		emit(ln);
	};
	for (size_t mi = 0; have && mi < pm->size() && !cut; mi++) {
		const auto&    m   = (*pm)[mi];
		const uint64_t end = m.va + m.size;
		for (uint64_t c = m.va & ~(pg - 1); c < end && !cut; c += kBlock) {
			const uint64_t ce = std::min(end, c + kBlock), np = (ce - c + pg - 1) / pg;
			vec.assign(np, 0);
			if (mincore(reinterpret_cast<void*>(c), ce - c, vec.data()) != 0) { absent += ce - c; continue; }
			for (uint64_t i = 0; i < np;) {
				if ((vec[i] & 1u) == 0) { absent += pg; i++; continue; }
				uint64_t j = i;
				while (j < np && (vec[j] & 1u) != 0) j++;
				const uint64_t ra = std::max(c + i * pg, m.va), re = std::min(c + j * pg, end);
				i = j;
				if (re <= ra || !safe_read(ra, buf.data(), re - ra)) { unreadable += re > ra ? re - ra : 0; continue; }
				const size_t nw = (re - ra) / 4;
				for (size_t k = 0; k < nw; k++) {
					const uint32_t v = buf[k];
					if (v != d[0] && v != d[1] && v != d[2]) continue;
					const uint64_t a = ra + k * 4;
					for (int x = 0; x < 3; x++)
						if (v == d[x] && h1[x]++ < 16) {
							char what[32];
							std::snprintf(what, sizeof(what), "dword %d (%08x)", x, d[x]);
							hit(what, a, m);
						}
					if (k + 1 < nw && v == d[0] && buf[k + 1] == d[1]) {
						if (h2[0]++ < 32) hit("pair 0-1", a, m);
						if (k + 2 < nw && buf[k + 2] == d[2] && h3++ < 64) hit("TRIPLE", a, m);
					}
					if (k + 1 < nw && v == d[1] && buf[k + 1] == d[2] && h2[1]++ < 32) hit("pair 1-2", a, m);
				}
				scanned += re - ra;
			}
			if (secs() > cap) cut = true;
		}
	}
	std::snprintf(ln, sizeof(ln), "scan: %.1f MiB resident read, %.1f MiB not resident, %.1f MiB unreadable, %zu mappings, %.2f s%s; triple %" PRIu64 ", pairs %" PRIu64 " / %" PRIu64 ", dwords %" PRIu64 " / %" PRIu64 " / %" PRIu64 " (lines: the first 16 per dword, 32 per pair, 64 triples)\n",
	              static_cast<double>(scanned) / 1048576.0, static_cast<double>(absent) / 1048576.0, static_cast<double>(unreadable) / 1048576.0, pm->size(), secs() - t_scan, cut ? ", CUT at the time cap" : (have ? "" : ", not run: no dims"), h3, h2[0], h2[1], h1[0], h1[1], h1[2]);
	emit(ln);
	if (out != nullptr) {
		std::fflush(out);
		fsync(fileno(out));
		std::fclose(out);
	}
	journal("rec0380: #%" PRIu64 " %s: dims %08x %08x %08x (%s); %s", n, kind, d[0], d[1], d[2], src.c_str(), ln);
	journal("rec0380: #%" PRIu64 " %s: written %s (%zu bytes) in %.2f s\n", n, kind, out != nullptr ? name : "(open failed)", bytes, secs());
	if (FILE* jf = journal_min_file(true); jf != nullptr) fsync(fileno(jf));
	return true;
}

