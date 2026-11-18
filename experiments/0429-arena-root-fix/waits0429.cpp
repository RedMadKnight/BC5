
// ---- experiment 0429 catcher: KYTY_BC5_0429_WAITS=1 (normal build only), where the job workers are at the crash -----
// Every guest semaphore wait that sleeps is stamped in a per-thread slot: the wait's start, the moment a signal readied
// it (Bc5Ready) and the moment it ran again (after the semaphore's lock was retaken). The ready-to-run latency is
// counted in bands, apart for the title's job semaphores ("JobLoaderSema", F451) and for all others, and printed every
// 50,000 resumes. At an access violation (loader/runtimeLinker.cpp) bc5_0429_dump_waits() prints one line per thread
// of the process: its name, state and CPU (/proc stat), its current syscall (/proc syscall: 202 is futex), its run and
// run-queue nanoseconds (/proc schedstat), and its guest semaphore slot (waiting since / readied and not yet running
// since). Allocation-free: open/read/getdents64 and snprintf into stack buffers, as the handler's other lines.
#ifndef BC5_LEAN
#include <dirent.h>
#include <fcntl.h>
namespace bc5_0429w {
static bool On() {
	static const bool v = [] {
		const bool on = bc5::env_rule::on(std::getenv("KYTY_BC5_0429_WAITS"));
		std::fprintf(stderr, "[bc5] exp 0429: wait catcher %s\n", on ? "ON" : "off");
		return on;
	}();
	return v;
}
struct Slot {
	std::atomic<int>      tid {0};
	char                  name[32] {};
	std::atomic<int>      state {0}; // 0 not waiting, 1 asleep in a wait, 2 readied and not yet running
	std::atomic<uint64_t> t_wait {0}, t_ready {0}, last_lat {0}, max_lat {0};
	std::atomic<uint64_t> waits {0};
};
static Slot             g_slots[256];
static std::atomic<int> g_nslots {0};
static thread_local int t_slot = -1;
static std::atomic<uint64_t> g_band[2][6]; // [job sema?][<20us, <100us, <500us, <2ms, <8ms, >=8ms]
static std::atomic<uint64_t> g_resumes {0};
static uint64_t NowNs() {
	timespec ts {};
	clock_gettime(CLOCK_MONOTONIC, &ts);
	return static_cast<uint64_t>(ts.tv_sec) * 1000000000ull + static_cast<uint64_t>(ts.tv_nsec);
}
static int OnWait(const std::string& name) {
	if (t_slot < 0) {
		const int s = g_nslots.fetch_add(1, std::memory_order_relaxed);
		if (s >= 256) {
			return -1;
		}
		t_slot = s;
		g_slots[s].tid.store(static_cast<int>(syscall(SYS_gettid)), std::memory_order_release);
	}
	Slot& sl = g_slots[t_slot];
	std::snprintf(sl.name, sizeof(sl.name), "%s", name.c_str());
	sl.t_wait.store(NowNs(), std::memory_order_relaxed);
	sl.waits.fetch_add(1, std::memory_order_relaxed);
	sl.state.store(1, std::memory_order_release);
	return t_slot;
}
static void OnReady(int s) {
	if (s >= 0) {
		g_slots[s].t_ready.store(NowNs(), std::memory_order_relaxed);
		g_slots[s].state.store(2, std::memory_order_release);
	}
}
static void OnEnd(int s, bool resumed) {
	if (s < 0) {
		return;
	}
	Slot& sl = g_slots[s];
	if (resumed && sl.state.load(std::memory_order_acquire) == 2) {
		const uint64_t lat = NowNs() - sl.t_ready.load(std::memory_order_relaxed);
		sl.last_lat.store(lat, std::memory_order_relaxed);
		if (lat > sl.max_lat.load(std::memory_order_relaxed)) {
			sl.max_lat.store(lat, std::memory_order_relaxed);
		}
		const int job  = std::strncmp(sl.name, "JobLoaderSema", 13) == 0 ? 1 : 0;
		const int band = lat < 20000 ? 0 : lat < 100000 ? 1 : lat < 500000 ? 2 : lat < 2000000 ? 3 : lat < 8000000 ? 4 : 5;
		g_band[job][band].fetch_add(1, std::memory_order_relaxed);
		const uint64_t n = g_resumes.fetch_add(1, std::memory_order_relaxed) + 1;
		if (n % 50000 == 0) {
			std::fprintf(stderr,
			             "[bc5] exp 0429 waits: %llu resumes; ready-to-run JobLoaderSema <20us %llu <100us %llu <500us %llu <2ms %llu "
			             "<8ms %llu >=8ms %llu; other <20us %llu <100us %llu <500us %llu <2ms %llu <8ms %llu >=8ms %llu\n",
			             static_cast<unsigned long long>(n), (unsigned long long)g_band[1][0].load(), (unsigned long long)g_band[1][1].load(),
			             (unsigned long long)g_band[1][2].load(), (unsigned long long)g_band[1][3].load(), (unsigned long long)g_band[1][4].load(),
			             (unsigned long long)g_band[1][5].load(), (unsigned long long)g_band[0][0].load(), (unsigned long long)g_band[0][1].load(),
			             (unsigned long long)g_band[0][2].load(), (unsigned long long)g_band[0][3].load(), (unsigned long long)g_band[0][4].load(),
			             (unsigned long long)g_band[0][5].load());
		}
	}
	sl.state.store(0, std::memory_order_release);
}
static int ReadSmall(const char* path, char* buf, int cap) {
	const int fd = open(path, O_RDONLY | O_CLOEXEC);
	if (fd < 0) {
		buf[0] = 0;
		return 0;
	}
	const ssize_t r = read(fd, buf, static_cast<size_t>(cap - 1));
	close(fd);
	const int n = r > 0 ? static_cast<int>(r) : 0;
	buf[n]      = 0;
	return n;
}
} // namespace bc5_0429w

extern "C" void bc5_0429_dump_waits() {
	using namespace bc5_0429w;
	if (!On()) {
		return;
	}
	const uint64_t now = NowNs();
	char           line[512];
	int            k = std::snprintf(line, sizeof(line), "[bc5] exp 0429 waits at the fault: crashing tid %d, %d slots\n",
	                                 static_cast<int>(syscall(SYS_gettid)), g_nslots.load());
	(void)!write(2, line, static_cast<size_t>(k));
	const int dfd = open("/proc/self/task", O_RDONLY | O_DIRECTORY | O_CLOEXEC);
	if (dfd < 0) {
		return;
	}
	alignas(8) char dents[8192];
	for (;;) {
		const long nread = syscall(SYS_getdents64, dfd, dents, sizeof(dents));
		if (nread <= 0) {
			break;
		}
		for (long off = 0; off < nread;) {
			auto* d = reinterpret_cast<struct dirent64*>(dents + off);
			off += d->d_reclen;
			if (d->d_name[0] < '0' || d->d_name[0] > '9') {
				continue;
			}
			const int tid = static_cast<int>(std::strtol(d->d_name, nullptr, 10));
			char      path[64], stat[512], sc[128], ss[128];
			std::snprintf(path, sizeof(path), "/proc/self/task/%d/stat", tid);
			ReadSmall(path, stat, sizeof(stat));
			std::snprintf(path, sizeof(path), "/proc/self/task/%d/syscall", tid);
			ReadSmall(path, sc, sizeof(sc));
			std::snprintf(path, sizeof(path), "/proc/self/task/%d/schedstat", tid);
			ReadSmall(path, ss, sizeof(ss));
			// stat: "tid (comm) S ..." ; the CPU is field 39
			const char* lp   = std::strchr(stat, '(');
			const char* rp   = std::strrchr(stat, ')');
			char        comm[24] = "?";
			char        st       = '?';
			int         cpu      = -1;
			if (lp != nullptr && rp != nullptr && rp > lp) {
				const int len = static_cast<int>(std::min<long>(rp - lp - 1, 23));
				std::memcpy(comm, lp + 1, static_cast<size_t>(len));
				comm[len] = 0;
				st        = rp[2];
				const char* p = rp + 2;
				for (int field = 3; field < 39 && p != nullptr; field++) {
					p = std::strchr(p, ' ');
					if (p != nullptr) {
						p++;
					}
				}
				if (p != nullptr) {
					cpu = static_cast<int>(std::strtol(p, nullptr, 10));
				}
			}
			char* nl = std::strchr(sc, ' ');
			if (nl != nullptr) {
				*nl = 0; // the syscall number only
			}
			nl = std::strchr(ss, '\n');
			if (nl != nullptr) {
				*nl = 0;
			}
			char slot[200] = "";
			for (int i = 0; i < g_nslots.load() && i < 256; i++) {
				if (g_slots[i].tid.load(std::memory_order_acquire) == tid) {
					const Slot& sl = g_slots[i];
					const int   s  = sl.state.load();
					const uint64_t since = s == 2 ? now - sl.t_ready.load() : s == 1 ? now - sl.t_wait.load() : 0;
					std::snprintf(slot, sizeof(slot), " | sema '%s' %s %.3f ms, last ready-to-run %.3f ms, max %.3f ms, waits %llu", sl.name,
					              s == 2 ? "READIED, not running for" : s == 1 ? "asleep for" : "not waiting;",
					              static_cast<double>(since) / 1e6, static_cast<double>(sl.last_lat.load()) / 1e6,
					              static_cast<double>(sl.max_lat.load()) / 1e6, static_cast<unsigned long long>(sl.waits.load()));
					break;
				}
			}
			k = std::snprintf(line, sizeof(line), "[bc5] exp 0429 thread at fault: tid %d '%s' state %c cpu %d syscall %s schedstat [%s]%s\n",
			                  tid, comm, st, cpu, sc[0] != 0 ? sc : "-", ss, slot);
			(void)!write(2, line, static_cast<size_t>(k));
		}
	}
	close(dfd);
}
#endif
// ---- end of experiment 0429's wait catcher ---------------------------------------------------------------------------
