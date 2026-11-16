
// ---- experiment 0429: KYTY_BC5_0429_GUEST_CPUS=1, the title's own CPU requests mapped onto this host, for any title ---
// The console pins a title's threads to the CPUs their masks name (TODO(verify): no console measurement), and a title
// derives its worker counts from its default mask (the second title: F790). This host gave every thread the default
// mask 0x7f and only stored the masks. Nothing here is per title or per CPU count; all of it is derived at run time:
// - the host CPU list: every online logical CPU, ordered by SMT sibling group (/sys/devices/system/cpu/cpu<c>/topology/
//   thread_siblings_list), so the list is 0,1,2,3,... where siblings are numbered next to each other and 0,8,1,9,...
//   where they are numbered apart;
// - the default mask of a new thread: one guest CPU per host CPU in that list (16 on this box);
// - a guest mask, at thread start and at Setaffinity: guest CPU i -> the i-th CPU of the list (i modulo its length), so
//   guest CPUs 2k and 2k+1 are the two threads of one host core, and the title's split of its threads over CPUs (its
//   owner on a CPU of its own, its workers on others) is kept as it asked.
// Logged in the normal build only: the list and the default mask once, every growth of the union of the CPUs the title
// has asked for, and with KYTY_BC5_0429_TRACE=1 each thread's mask, priority and nice (the first 400 lines).
static bool Bc5GuestCpus() {
	static const bool v = [] {
		const bool on = bc5::env_rule::on(std::getenv("KYTY_BC5_0429_GUEST_CPUS"));
#ifndef BC5_LEAN
		std::fprintf(stderr, "[bc5] exp 0429: guest CPU mapping %s\n", on ? "ON" : "off");
#endif
		return on;
	}();
	return v;
}

static bool Bc5AffinityTrace() {
#ifndef BC5_LEAN
	static const bool v = bc5::env_rule::on(std::getenv("KYTY_BC5_0429_TRACE"));
	return v;
#else
	return false;
#endif
}

struct Bc5HostList {
	int cpu[64];
	int n;
};

static int Bc5ReadSiblings(int c, int* out, int max) {
	char path[96];
	std::snprintf(path, sizeof(path), "/sys/devices/system/cpu/cpu%d/topology/thread_siblings_list", c);
	FILE* f = std::fopen(path, "r");
	if (f == nullptr) {
		return 0;
	}
	int  n         = 0;
	char line[256] = {};
	if (std::fgets(line, sizeof(line), f) != nullptr) {
		const char* p = line;
		while (*p >= '0' && *p <= '9' && n < max) { // "a,b", "a-b" or a mix
			char*      end = nullptr;
			const long a   = std::strtol(p, &end, 10);
			long       b   = a;
			p              = end;
			if (*p == '-') {
				b = std::strtol(p + 1, &end, 10);
				p = end;
			}
			for (long x = a; x <= b && n < max; x++) {
				out[n++] = static_cast<int>(x);
			}
			if (*p == ',') {
				p++;
			}
		}
	}
	std::fclose(f);
	return n;
}

static const Bc5HostList& Bc5Hosts() {
	static const Bc5HostList v = [] {
		Bc5HostList h {};
		// Every CPU whose topology /sys shows (an offline CPU has none), in sibling-group order. Not this thread's own
		// affinity: the first caller may already be pinned.
		for (int c = 0; c < 64 && h.n < 64; c++) {
			int       sib[8];
			const int n = Bc5ReadSiblings(c, sib, 8);
			if (n == 0 || sib[0] != c) {
				continue; // offline or unreadable, or listed with its group's first CPU
			}
			for (int i = 0; i < n && h.n < 64; i++) {
				h.cpu[h.n++] = sib[i];
			}
		}
		if (h.n == 0) {
			h.cpu[h.n++] = 0;
		}
#ifndef BC5_LEAN
		if (Bc5GuestCpus()) {
			std::fprintf(stderr, "[bc5] exp 0429 guest CPUs: %d host CPUs, default mask 0x%llx, guest:host", h.n,
			             static_cast<unsigned long long>(h.n >= 64 ? ~0ull : ((1ull << h.n) - 1)));
			for (int i = 0; i < h.n; i++) {
				std::fprintf(stderr, " %d:%d", i, h.cpu[i]);
			}
			std::fprintf(stderr, "\n");
		}
#endif
		return h;
	}();
	return v;
}

static uint64_t Bc5GuestDefaultMask() {
	if (!Bc5GuestCpus()) {
		return 0x7f;
	}
	const int n = Bc5Hosts().n;
	return n >= 64 ? ~0ull : ((1ull << n) - 1);
}

static void Bc5ApplyAffinity(Pthread thread, const char* why) {
	if (thread == nullptr || thread->attr == nullptr || thread->host_thread_id == 0) {
		return;
	}
	const uint64_t mask = thread->attr->affinity;
	int            rc   = -1; // not applied
	if (Bc5GuestCpus() && mask != 0) {
		const Bc5HostList& h = Bc5Hosts();
		cpu_set_t          set;
		CPU_ZERO(&set);
		for (int i = 0; i < 64; i++) {
			if (((mask >> i) & 1u) != 0) {
				CPU_SET(h.cpu[i % h.n], &set);
			}
		}
		rc = sched_setaffinity(static_cast<pid_t>(thread->host_thread_id), sizeof(set), &set) == 0 ? 0 : errno;
#ifndef BC5_LEAN
		static std::atomic<uint64_t> asked {0};
		const uint64_t               before = asked.fetch_or(mask, std::memory_order_relaxed);
		if ((before | mask) != before) {
			const uint64_t now = before | mask;
			std::fprintf(stderr, "[bc5] exp 0429 guest CPUs asked so far: 0x%llx (%d CPUs, highest %d), by '%s' (%s)\n",
			             static_cast<unsigned long long>(now), __builtin_popcountll(now), 63 - __builtin_clzll(now),
			             thread->name.c_str(), why);
		}
#endif
	}
#ifndef BC5_LEAN
	if (Bc5AffinityTrace()) {
		static std::atomic<int> logged {0};
		if (logged.fetch_add(1, std::memory_order_relaxed) < 400) {
			std::fprintf(stderr, "[bc5] exp 0429 thread: %s tid %d '%s' prio %d nice %d mask 0x%llx applied %s\n", why,
			             static_cast<int>(thread->host_thread_id), thread->name.c_str(), thread->attr->guest_priority,
			             Bc5GuestNice(thread->attr->guest_priority), static_cast<unsigned long long>(mask),
			             rc == -1 ? "no" : rc == 0 ? "yes" : "FAILED");
		}
	}
#else
	(void)why;
	(void)rc;
#endif
}
// ---- end of experiment 0429 guest CPUs -----------------------------------------------------------------------------
