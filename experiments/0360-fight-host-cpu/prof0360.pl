#!/usr/bin/perl
# BC5 experiment 0360, the CPU sampler: applied AFTER meter0360.pl to the same PRIVATE copy of src/libs/bc5LleAgc.cpp.
# Measurement only. The meter thread gives each of the title's threads (game-main, the Render Thread, the Job Hi, Lo and
# Bk workers, the Archive IO threads) a POSIX CPU-time timer of its own (the thread's CPU clock, MAKE_THREAD_CPUCLOCK of
# the kernel's include/linux/posix-timers.h, as glibc's pthread_getcpuclockid builds it), with SIGEV_THREAD_ID and
# SIGRTMIN+9: a thread is interrupted only after each 4 ms it spends on a CPU, never while it sleeps. The handler takes
# the interrupted rip from the ucontext and counts it, lock-free, as:
#   title code (any executable address outside a file mapping), the emulator's own code (/proc/self/exe; also into a
#   histogram by offset/16 per thread group), a shared library (by file name), or a syscall return (the two bytes before
#   rip are 0f 05: the timer expired in the kernel), and title code also into a histogram by address/256.
# The meter journals one "cpu prof:" line a second (per group: samples and the four shares) and every 10 s the
# cumulative top of both histograms ("cpu prof top host:" / "cpu prof top title:") and the library names. The emulator's
# offsets are resolved offline with nm on the private binary; title addresses are kept as numbers only.
# BC5_0360_PROF=0 turns it off; BC5_0360_PROF_MS=<ms of CPU> sets the period (default 4).
# usage: prof0360.pl <private src root>
use strict;
use warnings;
my ($root) = @ARGV;
die "usage: prof0360.pl <src root>\n" unless defined $root;
my $marks = 0;
sub patch {
	my ($file, @pairs) = @_;
	open(my $h, "<", $file) or die "$file: $!\n";
	my $s = do { local $/; <$h> };
	close $h;
	my $crlf = ($s =~ /\r\n/) ? 1 : 0;
	while (@pairs) {
		my $old = shift @pairs;
		my $new = shift @pairs;
		if ($crlf) {
			$old =~ s/\n/\r\n/g;
			$new =~ s/\n/\r\n/g;
		}
		my $n = () = $s =~ /\Q$old\E/g;
		die "$file: anchor found $n times, expected once:\n$old\n" unless $n == 1;
		$s =~ s/\Q$old\E/$new/;
		$marks++;
	}
	open(my $o, ">", $file) or die "$file: $!\n";
	print $o $s;
	close $o;
}
my $agc = "$root/src/libs/bc5LleAgc.cpp";

my $inc_old = <<'EOF';
#include <sys/syscall.h>  // BC5 (experiment 0360)
EOF
my $inc_new = <<'EOF';
#include <sys/syscall.h>  // BC5 (experiment 0360)
#include <csignal>        // BC5 (experiment 0360, the CPU sampler)
#include <ctime>
#include <ucontext.h>
EOF

my $ns_old = <<'EOF';
// BC5 (experiment 0360): the CPU meter thread (see meter0360.pl's header).
namespace Meter0360 {
EOF
my $ns_new = <<'EOF';
// BC5 (experiment 0360): the CPU sampler (see prof0360.pl's header), driven by the meter thread.
namespace Prof0360 {
#ifndef sigev_notify_thread_id
#define sigev_notify_thread_id _sigev_un._tid
#endif
constexpr int kSlots = 64, kLibs = 64, kHash = 1 << 15, kGroups = 6;
constexpr int kGuest = 0, kHost = 1, kSys = 2, kLib0 = 3, kCls = kLib0 + kLibs;
static const char* const kGroupName[kGroups] = {"game-main", "Render", "Hi", "Lo", "Bk", "IO"};
struct Range {
	uint64_t lo = 0, hi = 0;
	int      lib = 0; // -1 the emulator, >= 0 a library
};
struct Maps {
	Range    r[512];
	int      n = 0;
	char     names[kLibs][40] {};
	int      nlibs    = 0;
	uint64_t exe_base = 0;
};
struct Slot {
	std::atomic<uint64_t> n[kCls];
	uint64_t              tid  = 0;
	int                   grp  = 0;
	bool                  used = false, seen = false;
	timer_t               timer {};
};
struct HEnt {
	std::atomic<uint64_t> key, count;
};
static std::atomic<const Maps*> g_maps {nullptr};
static Slot                     g_slot[kSlots];
static HEnt                     g_host[kHash], g_guest[kHash];
static std::atomic<uint64_t>    g_hist_full {0}, g_attached {0}, g_attach_failed {0};
static bool                     g_on = false;

static void hist_add(HEnt* t, uint64_t key) {
	key += 1; // 0 marks an empty entry
	const uint64_t h = (key * 0x9E3779B97F4A7C15ull) >> 49u;
	for (uint64_t i = 0; i < 32; i++) {
		HEnt&    e = t[(h + i) & (kHash - 1)];
		uint64_t k = e.key.load(std::memory_order_relaxed);
		if (k == 0 && (e.key.compare_exchange_strong(k, key, std::memory_order_relaxed) || k == key)) {
			e.count.fetch_add(1, std::memory_order_relaxed);
			return;
		}
		if (k == key) {
			e.count.fetch_add(1, std::memory_order_relaxed);
			return;
		}
	}
	g_hist_full.fetch_add(1, std::memory_order_relaxed);
}
static void handler(int, siginfo_t* si, void* ctx) {
	const int s = si->si_value.sival_int;
	if (s < 0 || s >= kSlots) return;
	const auto*    uc  = static_cast<const ucontext_t*>(ctx);
	const uint64_t rip = static_cast<uint64_t>(uc->uc_mcontext.gregs[REG_RIP]);
	const Maps*    m   = g_maps.load(std::memory_order_acquire);
	int            lib = -2;
	uint64_t       rlo = 0;
	if (m != nullptr) {
		int lo = 0, hi = m->n - 1;
		while (lo <= hi) {
			const int mid = (lo + hi) / 2;
			if (rip < m->r[mid].lo) hi = mid - 1;
			else if (rip >= m->r[mid].hi) lo = mid + 1;
			else {
				lib = m->r[mid].lib;
				rlo = m->r[mid].lo;
				break;
			}
		}
	}
	Slot& sl  = g_slot[s];
	int   cls = kGuest;
	if (lib == -1) cls = kHost;
	else if (lib >= 0) cls = kLib0 + lib;
	if (lib >= -1 && rip >= rlo + 2) {
		const auto* p = reinterpret_cast<const uint8_t*>(rip);
		if (p[-2] == 0x0f && p[-1] == 0x05) cls = kSys;
	}
	sl.n[cls].fetch_add(1, std::memory_order_relaxed);
	if (cls == kHost && m != nullptr) hist_add(g_host, ((rip - m->exe_base) >> 4u) | (static_cast<uint64_t>(sl.grp) << 56u));
	else if (cls == kGuest) hist_add(g_guest, (rip >> 8u) | (static_cast<uint64_t>(sl.grp) << 56u));
}
static void read_maps() {
	auto* m       = new Maps();
	char  exe[512] {};
	if (const ssize_t el = readlink("/proc/self/exe", exe, sizeof(exe) - 1); el > 0) exe[el] = 0;
	FILE* f = std::fopen("/proc/self/maps", "r");
	if (f == nullptr) {
		delete m;
		return;
	}
	char     line[1024];
	uint64_t exe_base = ~0ull;
	while (std::fgets(line, sizeof(line), f) != nullptr) {
		unsigned long long lo = 0, hi = 0, off = 0;
		char               perms[8] {};
		int                pos = 0;
		if (std::sscanf(line, "%llx-%llx %7s %llx %*s %*s %n", &lo, &hi, perms, &off, &pos) < 4) continue;
		char* path = pos > 0 ? line + pos : line + std::strlen(line);
		if (char* nl = std::strchr(path, '\n')) *nl = 0;
		const bool is_exe = exe[0] != 0 && std::strcmp(path, exe) == 0;
		if (is_exe && lo < exe_base) exe_base = lo;
		// anonymous executable memory and the guest's memfds (memfd:KytyPrivateMemory, M1): the title's code
		if (perms[2] != 'x' || path[0] == 0 || std::strncmp(path, "memfd:", 6) == 0 || std::strncmp(path, "/memfd:", 7) == 0 || m->n >= 512) continue;
		int lib = -1;
		if (!is_exe) {
			const char* b = std::strrchr(path, '/');
			b             = b != nullptr ? b + 1 : path;
			lib           = -2;
			for (int k = 0; k < m->nlibs; k++) {
				if (std::strncmp(m->names[k], b, sizeof(m->names[k]) - 1) == 0) {
					lib = k;
					break;
				}
			}
			if (lib == -2) {
				lib = m->nlibs < kLibs ? m->nlibs++ : kLibs - 1;
				std::snprintf(m->names[lib], sizeof(m->names[lib]), "%s", b);
			}
		}
		m->r[m->n++] = {lo, hi, lib};
	}
	std::fclose(f);
	m->exe_base = exe_base == ~0ull ? 0 : exe_base;
	const Maps* old = g_maps.exchange(m, std::memory_order_acq_rel);
	if (old == nullptr || old->nlibs != m->nlibs || old->n != m->n) {
		char   names[2600] {};
		size_t nl = 0;
		for (int k = 0; k < m->nlibs && nl < sizeof(names) - 48; k++) nl += static_cast<size_t>(std::snprintf(names + nl, sizeof(names) - nl, " %d:%s", k, m->names[k]));
		journal("cpu prof libs: exe %s base 0x%" PRIx64 ", %d executable ranges, libraries:%s\n", exe, m->exe_base, m->n, names);
	}
	// the previous table is not freed: a handler may still be reading it
}
static int group_of(const char* comm) {
	if (std::strcmp(comm, "game-main") == 0) return 0;
	if (std::strncmp(comm, "Render_Thread", 13) == 0) return 1;
	if (std::strncmp(comm, "Job_Hi", 6) == 0) return 2;
	if (std::strncmp(comm, "Job_Lo", 6) == 0) return 3;
	if (std::strncmp(comm, "Job_Bk", 6) == 0) return 4;
	if (std::strncmp(comm, "Archive_", 8) == 0) return 5;
	return -1;
}
static void init() {
	const char* e = std::getenv("BC5_0360_PROF");
	if (e != nullptr && std::strcmp(e, "0") == 0) return;
	struct sigaction sa {};
	sa.sa_sigaction = handler;
	sa.sa_flags     = SA_SIGINFO | SA_RESTART;
	sigemptyset(&sa.sa_mask);
	if (sigaction(SIGRTMIN + 9, &sa, nullptr) != 0) {
		journal("cpu prof: sigaction failed, the sampler is off\n");
		return;
	}
	read_maps();
	g_on = true;
	journal("cpu prof: experiment 0360, the title's threads sampled every %ld ms of their CPU (SIGRTMIN+9)\n", std::getenv("BC5_0360_PROF_MS") != nullptr ? std::strtol(std::getenv("BC5_0360_PROF_MS"), nullptr, 10) : 4L);
}
static void sync_begin() {
	for (auto& s: g_slot) s.seen = false;
}
static void see(uint64_t tid, const char* comm) {
	if (!g_on) return;
	const int grp = group_of(comm);
	if (grp < 0) return;
	for (auto& s: g_slot) {
		if (s.used && s.tid == tid) {
			s.seen = true;
			return;
		}
	}
	int k = -1;
	for (int i = 0; i < kSlots; i++) {
		if (!g_slot[i].used) {
			k = i;
			break;
		}
	}
	if (k < 0) return;
	static const long period_ms = std::getenv("BC5_0360_PROF_MS") != nullptr ? std::max(1L, std::strtol(std::getenv("BC5_0360_PROF_MS"), nullptr, 10)) : 4L;
	sigevent sev {};
	sev.sigev_notify           = SIGEV_THREAD_ID;
	sev.sigev_signo            = SIGRTMIN + 9;
	sev.sigev_value.sival_int  = k;
	sev.sigev_notify_thread_id = static_cast<pid_t>(tid);
	const auto clk             = static_cast<clockid_t>((~static_cast<uint32_t>(tid) << 3u) | 6u); // MAKE_THREAD_CPUCLOCK(tid, CPUCLOCK_SCHED)
	Slot&      s               = g_slot[k];
	for (auto& x: s.n) x.store(0, std::memory_order_relaxed);
	s.grp = grp;
	timer_t t {};
	if (timer_create(clk, &sev, &t) != 0) {
		g_attach_failed++;
		return;
	}
	itimerspec its {};
	its.it_value.tv_sec     = period_ms / 1000;
	its.it_value.tv_nsec    = (period_ms % 1000) * 1'000'000L;
	its.it_interval         = its.it_value;
	if (timer_settime(t, 0, &its, nullptr) != 0) {
		timer_delete(t);
		g_attach_failed++;
		return;
	}
	s.timer = t;
	s.tid   = tid;
	s.used  = true;
	s.seen  = true;
	g_attached++;
}
static void sync_end() {
	if (!g_on) return;
	for (auto& s: g_slot) {
		if (s.used && !s.seen) { // the thread is gone
			timer_delete(s.timer);
			s.used = false;
		}
	}
}
static void top(HEnt* t, const char* what, int count, uint64_t mul) {
	struct E {
		uint64_t key, n;
	};
	static E v[kHash];
	int      nv = 0;
	uint64_t total = 0;
	for (int i = 0; i < kHash; i++) {
		const uint64_t k = t[i].key.load(std::memory_order_relaxed);
		if (k == 0) continue;
		v[nv++] = {k - 1, t[i].count.load(std::memory_order_relaxed)};
		total += v[nv - 1].n;
	}
	std::sort(v, v + nv, [](const E& a, const E& b) { return a.n > b.n; });
	char   line[4096] {};
	size_t ll = 0;
	for (int i = 0; i < nv && i < count && ll < sizeof(line) - 48; i++) {
		const int      g = static_cast<int>(v[i].key >> 56u);
		const uint64_t a = (v[i].key & ((1ull << 56u) - 1)) * mul;
		ll += static_cast<size_t>(std::snprintf(line + ll, sizeof(line) - ll, " %s:%" PRIx64 "=%" PRIu64, g < kGroups ? kGroupName[g] : "?", a, v[i].n));
	}
	journal("cpu prof top %s (cumulative, %d buckets, %" PRIu64 " samples; group:address=samples):%s\n", what, nv, total, line);
}
static void report(double now_s) {
	if (!g_on) return;
	static uint64_t prev[kGroups][kCls] {};
	uint64_t        cur[kGroups][kCls] {};
	for (auto& s: g_slot) {
		if (!s.used) continue;
		for (int c = 0; c < kCls; c++) cur[s.grp][c] += s.n[c].load(std::memory_order_relaxed);
	}
	// totals of the threads that left are lost from cur; the deltas clamp at 0
	char   line[1600] {};
	size_t ll = 0;
	for (int g = 0; g < kGroups && ll < sizeof(line) - 120; g++) {
		uint64_t d[kCls] {}, n = 0, lib = 0;
		int      best = -1;
		for (int c = 0; c < kCls; c++) {
			d[c] = cur[g][c] > prev[g][c] ? cur[g][c] - prev[g][c] : 0;
			n += d[c];
			if (c >= kLib0) {
				lib += d[c];
				if (best < 0 || d[c] > d[best]) best = c;
			}
		}
		const double q = n != 0 ? 100.0 / static_cast<double>(n) : 0;
		ll += static_cast<size_t>(std::snprintf(line + ll, sizeof(line) - ll, " %s %" PRIu64 ": title %.0f host %.0f sys %.0f lib %.0f (most %d);", kGroupName[g], n, static_cast<double>(d[kGuest]) * q,
		                                        static_cast<double>(d[kHost]) * q, static_cast<double>(d[kSys]) * q, static_cast<double>(lib) * q, best >= 0 && d[best] != 0 ? best - kLib0 : -1));
	}
	std::memcpy(prev, cur, sizeof(prev));
	journal("cpu prof: t %.3f s; per group samples and %% title code / emulator / in the kernel / libraries:%s %" PRIu64 " threads attached, %" PRIu64 " failed, histogram overflow %" PRIu64 "\n", now_s, line,
	        g_attached.load(), g_attach_failed.load(), g_hist_full.load());
	static double last_top = 0;
	if (now_s - last_top >= 10.0) {
		last_top = now_s;
		read_maps();
		top(g_host, "host", 60, 16);
		top(g_guest, "title", 40, 256);
	}
}
} // namespace Prof0360

// BC5 (experiment 0360): the CPU meter thread (see meter0360.pl's header).
namespace Meter0360 {
EOF

my $init_old = <<'EOF';
	setpriority(PRIO_PROCESS, static_cast<id_t>(syscall(SYS_gettid)), 5);
	const double hz = static_cast<double>(sysconf(_SC_CLK_TCK));
EOF
my $init_new = <<'EOF';
	setpriority(PRIO_PROCESS, static_cast<id_t>(syscall(SYS_gettid)), 5);
	Prof0360::init(); // experiment 0360, the CPU sampler
	const double hz = static_cast<double>(sysconf(_SC_CLK_TCK));
EOF

my $scan_old = <<'EOF';
		int ncur = 0;
		if (DIR* d = opendir("/proc/self/task"); d != nullptr) {
EOF
my $scan_new = <<'EOF';
		int ncur = 0;
		Prof0360::sync_begin(); // experiment 0360, the CPU sampler
		if (DIR* d = opendir("/proc/self/task"); d != nullptr) {
EOF

my $seen_old = <<'EOF';
				bool found = false;
				for (int k = 0; k < nprev; k++) {
EOF
my $seen_new = <<'EOF';
				Prof0360::see(t.tid, t.comm); // experiment 0360, the CPU sampler
				bool found = false;
				for (int k = 0; k < nprev; k++) {
EOF

my $end_old = <<'EOF';
		double title_cpu = 0, title_wait = 0, host_cpu = 0, host_wait = 0;
EOF
my $end_new = <<'EOF';
		Prof0360::sync_end(); // experiment 0360, the CPU sampler
		double title_cpu = 0, title_wait = 0, host_cpu = 0, host_wait = 0;
EOF

my $rep_old = <<'EOF';
		        d[2].cs_ms, d[3].submits, d[3].jobs, d[3].sync_ms, d[3].hints_ms, d[3].prepare_ms, d[3].list_ms, d[3].cs_ms, ncur, top, static_cast<long long>(cost_us));
EOF
my $rep_new = <<'EOF';
		        d[2].cs_ms, d[3].submits, d[3].jobs, d[3].sync_ms, d[3].hints_ms, d[3].prepare_ms, d[3].list_ms, d[3].cs_ms, ncur, top, static_cast<long long>(cost_us));
		Prof0360::report(now_s); // experiment 0360, the CPU sampler
EOF

patch($agc, $inc_old, $inc_new, $ns_old, $ns_new, $init_old, $init_new, $scan_old, $scan_new, $seen_old, $seen_new, $end_old, $end_new, $rep_old, $rep_new);
print "prof0360.pl: $marks edits\n";
