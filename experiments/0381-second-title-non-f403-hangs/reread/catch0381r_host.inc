// BC5 exp 0381: F687's page check and F688's reopen trace, both off by default and read-only. They write their own files in the
// capture directory, opened and closed for each line, so logging off and the journal's 1 MiB buffer do not hide them.
// BC5_0381_PAGE_CHECK=<va>[,<va>...] (hex): where each page stands: the host's GPU mapping and its recorded rights, zero page, guest
// range, CPU rights and residence. Written at each change, at most once a second, and for any fault address at a timeout. The rights
// are the host's record of what it mapped, not a read of the PTE.
// BC5_0381_REOPEN_TRACE=1: for 240 s after a device reopen, one line a second: flips, pinned bytes, GTT, RSS, the killed jobs' labels,
// and the threads asleep in the kernel on something unusual.
static std::atomic<uint64_t>      g_c0381r_flips {0};
static std::mutex                 g_c0381r_mutex;
static std::vector<c0381r::Label> g_c0381r_labels;
static std::atomic<uint64_t>      g_c0381r_trace_gen {0};
static void c0381r_write(const char* file, const std::string& line) {
	if (g_dump_dir.empty()) return;
	char name[512];
	std::snprintf(name, sizeof(name), "%s/%s", g_dump_dir.c_str(), file);
	if (FILE* f = std::fopen(name, "a"); f != nullptr) {
		std::fprintf(f, "%.3f %s\n", timing_now(), line.c_str());
		std::fclose(f);
	}
}
static bool c0381r_trace_on() {
	static const bool on = [] { const char* e = BC5_DIAG_ENV("BC5_0381_REOPEN_TRACE"); return e != nullptr && e[0] == '1'; }();
	return on;
}
static std::string c0381r_page(uint64_t va) {
	char out[512];
	const uint64_t page = va & ~0xfffull;
	std::string    gpu = "gpu none";
	if (g_dev) {
		const auto have = g_dev->mappings();
		if (const auto* m = c0381r::find_mapping(have, page); m != nullptr) {
			std::snprintf(out, sizeof(out), "gpu %s 0x%" PRIx64 "+0x%" PRIx64 " %s", m->shared ? "shared" : "userptr", m->va, m->size, m->readonly ? "read" : "read-write");
			gpu = out;
		}
	}
	bool zero = false;
	for (const auto& [a, n]: g_scratch) zero = zero || (page >= a && page - a < n);
	std::vector<std::pair<uint64_t, uint64_t>> guest;
	Libs::LibKernel::Memory::Bc5GuestRangesIn(page, page + 0x1000, &guest);
	bool learned = false;
	for (const auto& [a, n]: g_learned) learned = learned || (page >= a && page - a < n);
	const char* vma = "none";
	for (const auto& v: g_vmas) {
		if (page >= v.start && page < v.end) vma = v.readonly ? "read" : "read-write";
	}
	std::string perms = "none", mapped;
	if (FILE* f = std::fopen("/proc/self/maps", "r"); f != nullptr) {
		char line[768];
		while (std::fgets(line, sizeof(line), f) != nullptr) {
			if (c0381r::maps_line(line, page, &perms, &mapped)) break;
		}
		std::fclose(f);
	}
	uint64_t pm = 0;
	if (const int fd = ::open("/proc/self/pagemap", O_RDONLY | O_CLOEXEC); fd >= 0) {
		if (::pread(fd, &pm, sizeof(pm), static_cast<off_t>((page >> 12u) * 8u)) != static_cast<ssize_t>(sizeof(pm))) pm = 0;
		::close(fd);
	}
	std::snprintf(out, sizeof(out), "%s; zero page %d; learned window %d; guest ranges %zu; guest vma %s; cpu %s %s; resident %d swapped %d", gpu.c_str(), zero ? 1 : 0,
	              learned ? 1 : 0, guest.size(), vma, perms.c_str(), mapped.c_str(), (pm >> 63u) != 0 ? 1 : 0, ((pm >> 62u) & 1u) != 0 ? 1 : 0);
	return out;
}
static void c0381r_page_run(const char* why) {
	static const std::vector<uint64_t> vas = c0381r::parse_vas(BC5_DIAG_ENV("BC5_0381_PAGE_CHECK"));
	if (vas.empty()) return;
	static std::vector<std::string> last;
	static uint64_t                 last_ns = 0;
	const uint64_t                  now = SoftCp::now_ns();
	if (now - last_ns < 1'000'000'000ull) return;
	last_ns = now;
	last.resize(vas.size());
	for (size_t i = 0; i < vas.size(); i++) {
		std::string s = c0381r_page(vas[i]);
		if (s == last[i]) continue;
		last[i] = s;
		char head[64];
		std::snprintf(head, sizeof(head), "%s 0x%" PRIx64 ": ", why, vas[i]);
		c0381r_write("page-check.txt", head + s);
	}
}
static void c0381r_fault(uint64_t va) {
	if (va == 0 || BC5_DIAG_ENV("BC5_0381_PAGE_CHECK") == nullptr) return;
	char head[64];
	std::snprintf(head, sizeof(head), "fault 0x%" PRIx64 ": ", va);
	c0381r_write("page-check.txt", head + c0381r_page(va));
}
static void c0381r_label(uint64_t addr, uint64_t want) {
	if (!c0381r_trace_on() || addr == 0) return;
	std::lock_guard lk(g_c0381r_mutex);
	if (g_c0381r_labels.size() < 400) g_c0381r_labels.push_back({addr, want});
}
static uint64_t c0381r_number(const char* path) {
	unsigned long long v = 0;
	if (FILE* f = std::fopen(path, "r"); f != nullptr) {
		if (std::fscanf(f, "%llu", &v) != 1) v = 0;
		std::fclose(f);
	}
	return v;
}
static std::string c0381r_threads() {
	std::string out;
	DIR*        d = ::opendir("/proc/self/task");
	if (d == nullptr) return out;
	int shown = 0;
	while (dirent* e = ::readdir(d)) {
		if (e->d_name[0] == '.' || shown >= 16) continue;
		char path[128], comm[32] = "?", wchan[64] = "", state = '?';
		std::snprintf(path, sizeof(path), "/proc/self/task/%s/comm", e->d_name);
		if (FILE* f = std::fopen(path, "r"); f != nullptr) {
			if (std::fscanf(f, "%31[^\n]", comm) != 1) comm[0] = '\0';
			std::fclose(f);
		}
		std::snprintf(path, sizeof(path), "/proc/self/task/%s/wchan", e->d_name);
		if (FILE* f = std::fopen(path, "r"); f != nullptr) {
			if (std::fscanf(f, "%63s", wchan) != 1) wchan[0] = '\0';
			std::fclose(f);
		}
		std::snprintf(path, sizeof(path), "/proc/self/task/%s/stat", e->d_name);
		if (FILE* f = std::fopen(path, "r"); f != nullptr) {
			char line[256] = "";
			if (std::fgets(line, sizeof(line), f) != nullptr) {
				if (const char* p = std::strrchr(line, ')'); p != nullptr && p[1] == ' ') state = p[2];
			}
			std::fclose(f);
		}
		if (!c0381r::thread_of_note(state, wchan)) continue;
		char one[128];
		std::snprintf(one, sizeof(one), " %s:%c:%s", comm, state, wchan);
		out += one;
		shown++;
	}
	::closedir(d);
	return out;
}
// process_vm_readv: a label's page may be gone by now, and a read here must not fault.
static bool c0381r_read(uint64_t addr, uint64_t* v) {
	iovec local {v, sizeof(*v)}, remote {reinterpret_cast<void*>(addr), sizeof(*v)};
	return ::process_vm_readv(::getpid(), &local, 1, &remote, 1, 0) == static_cast<ssize_t>(sizeof(*v));
}
static void c0381r_trace_start(const char* result) {
	if (!c0381r_trace_on()) return;
	c0381r_write("reopen-trace.txt", std::string("reopen ") + result);
	const uint64_t me = ++g_c0381r_trace_gen;
	std::thread([me] {
		uint64_t last_flips = g_c0381r_flips.load();
		for (int i = 0; i < 240 && g_c0381r_trace_gen.load() == me; i++) {
			std::this_thread::sleep_for(std::chrono::seconds(1));
			uint64_t gtt = c0381r_number("/sys/class/drm/card1/device/mem_info_gtt_used");
			if (gtt == 0) gtt = c0381r_number("/sys/class/drm/card0/device/mem_info_gtt_used");
			std::vector<c0381r::Label> labels;
			{
				std::lock_guard lk(g_c0381r_mutex);
				labels = g_c0381r_labels;
			}
			const uint64_t flips = g_c0381r_flips.load(), waited = g_fence_wait_since.load();
			char           head[192];
			std::snprintf(head, sizeof(head), "flips +%" PRIu64 " mapped %" PRIu64 " MiB gtt %" PRIu64 " MiB fence wait %.1f s; ", flips - last_flips, g_bytes_mapped >> 20u, gtt >> 20u,
			              waited != 0 ? static_cast<double>(SoftCp::now_ns() - waited) / 1e9 : 0.0);
			last_flips = flips;
			c0381r_write("reopen-trace.txt", head + c0381r::label_summary(labels, c0381r_read) + ";" + c0381r_threads());
		}
	}).detach();
}
