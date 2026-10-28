#!/usr/bin/perl
# BC5 experiment 0360, the CPU meter: applied to a PRIVATE copy of src/libs/bc5LleAgc.cpp (the shared tree's e7cc2f60;
# the shared tree is only read). Measurement only: nothing the title or the GPU sees changes.
#   (1) bc5-meter, a host thread at nice +5 started at the first flip, journals one "cpu meter:" line a second:
#       - every thread of the process with its CPU and its run-queue wait over the second, from
#         /proc/self/task/<tid>/schedstat (ns on a CPU, ns runnable but not running, slices) and its kernel time from
#         /proc/self/task/<tid>/stat (utime and stime are fields 14 and 15; exp 0358's trap read field 15 as user);
#       - the sums by class: the title's threads (Hi, Lo, Bk workers, game-main, the Render Thread, the rest) and the
#         host's threads, each as CPU ms and wait ms;
#       - the box: busy share of each CPU from /proc/stat, the package mount's CPU (the bc5-mount process), and the
#         rest of the box (kernel threads, the desktop) as the difference;
#       - the direct path's submit costs per second by the submitting thread's class (the title's threads, bc5-ring,
#         bc5-chainwd, other host threads): sync, hints, prepare, list, cs. The frame profile counts the chain
#         watchdog's submissions as the game thread's (t_cq is 0 there).
#   (2) frame_profile_submit and frame_profile_job feed (1)'s class counters under the profile's own mutex.
# BC5_0360_METER=0 turns (1) off. Cost: ~100 small /proc reads a second on its own thread.
# usage: meter0360.pl <private src root>
use strict;
use warnings;
my ($root) = @ARGV;
die "usage: meter0360.pl <src root>\n" unless defined $root;
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
#include <sys/mman.h>
#include <sys/stat.h>
EOF
my $inc_new = <<'EOF';
#include <sys/mman.h>
#include <sys/stat.h>
#include <dirent.h>       // BC5 (experiment 0360, the CPU meter)
#include <sys/resource.h> // BC5 (experiment 0360)
#include <sys/syscall.h>  // BC5 (experiment 0360)
EOF

my $sub_old = <<'EOF';
static void frame_profile_submit(bool game_thread, double sync_ms, double hints_ms) {
	if (!g_frame_profile_on() || !game_thread) return;
	std::lock_guard lock(g_fp_mutex);
	g_fp.render_thread = std::this_thread::get_id();
EOF
my $sub_new = <<'EOF';
// BC5 (experiment 0360): the direct path's submit costs by the submitting thread's class, read once a second by the
// CPU meter (under g_fp_mutex): 0 the title's threads, 1 bc5-ring, 2 bc5-chainwd, 3 other host threads.
struct MeterCls {
	double   sync_ms = 0, hints_ms = 0, prepare_ms = 0, list_ms = 0, cs_ms = 0;
	uint64_t submits = 0, jobs = 0;
};
static MeterCls g_meter_cls[4];
static int meter_cls() {
	static thread_local int cls = -1;
	if (cls < 0) {
		char n[16] = {};
		pthread_getname_np(pthread_self(), n, sizeof(n));
		if (t_cq == 1 || std::strcmp(n, "bc5-ring") == 0) cls = 1;
		else if (std::strcmp(n, "bc5-chainwd") == 0) cls = 2;
		else if (std::strncmp(n, "bc5-", 4) == 0 || std::strncmp(n, "kyty", 4) == 0) cls = 3;
		else cls = 0;
	}
	return cls;
}

static void frame_profile_submit(bool game_thread, double sync_ms, double hints_ms) {
	if (!g_frame_profile_on()) return;
	std::lock_guard lock(g_fp_mutex);
	{ // experiment 0360
		MeterCls& m = g_meter_cls[meter_cls()];
		m.sync_ms += sync_ms;
		m.hints_ms += hints_ms;
		m.submits++;
	}
	if (!game_thread) return;
	g_fp.render_thread = std::this_thread::get_id();
EOF

my $job_old = <<'EOF';
static void frame_profile_job(bool game_thread, double prepare_ms, double list_ms, double cs_ms) {
	if (!g_frame_profile_on()) return;
	std::lock_guard lock(g_fp_mutex);
EOF
my $job_new = <<'EOF';
static void frame_profile_job(bool game_thread, double prepare_ms, double list_ms, double cs_ms) {
	if (!g_frame_profile_on()) return;
	std::lock_guard lock(g_fp_mutex);
	{ // experiment 0360
		MeterCls& m = g_meter_cls[meter_cls()];
		m.prepare_ms += prepare_ms;
		m.list_ms += list_ms;
		m.cs_ms += cs_ms;
		m.jobs++;
	}
EOF

my $flip_old = <<'EOF';
static void frame_profile_flip(double drain_ms) {
	if (!g_frame_profile_on()) return;
	std::lock_guard lock(g_fp_mutex);
EOF
my $flip_new = <<'EOF';
// BC5 (experiment 0360): the CPU meter thread (see meter0360.pl's header).
namespace Meter0360 {
struct T {
	uint64_t tid = 0, exec_ns = 0, wait_ns = 0, slices = 0, utime = 0, stime = 0;
	double   d_cpu = 0, d_wait = 0, d_sys = 0;
	char     comm[16] = {};
	char     state    = '?';
	int      cpu      = -1;
};
static ssize_t read_small(const char* path, char* buf, size_t n) {
	const int fd = open(path, O_RDONLY | O_CLOEXEC);
	if (fd < 0) return -1;
	const ssize_t got = read(fd, buf, n - 1);
	close(fd);
	if (got > 0) buf[got] = 0;
	return got;
}
// /proc/<...>/stat: comm, state, utime (field 14), stime (15), processor (39). Fields after the state start at ppid (4).
static bool read_stat(const char* path, T* t) {
	char          buf[1024];
	const ssize_t n = read_small(path, buf, sizeof(buf));
	if (n <= 0) return false;
	const char* l = std::strchr(buf, '(');
	const char* r = std::strrchr(buf, ')');
	if (l == nullptr || r == nullptr || r < l || r[1] != ' ') return false;
	size_t cn = static_cast<size_t>(r - l - 1);
	if (cn > 15) cn = 15;
	std::memcpy(t->comm, l + 1, cn);
	t->comm[cn] = 0;
	for (char* c = t->comm; *c != 0; c++) {
		if (*c == ' ') *c = '_';
	}
	t->state = r[2];
	long long   f[36] {};
	const char* q = r + 3;
	for (int k = 0; k < 36; k++) {
		while (*q == ' ') q++;
		char* e = nullptr;
		f[k]    = std::strtoll(q, &e, 10);
		if (e == q) break;
		q = e;
	}
	t->utime = static_cast<uint64_t>(f[10]);
	t->stime = static_cast<uint64_t>(f[11]);
	t->cpu   = static_cast<int>(f[35]);
	return true;
}
static bool host_name(const char* c) {
	static const char* const host[] = {"bc5-", "kyty", "mangohud", "SDLAudio", "module-rt", "HIDAPI", "pipewire", "pw-", "gmain", "gdbus", "dconf"};
	for (const char* h: host) {
		if (std::strncmp(c, h, std::strlen(h)) == 0) return true;
	}
	return false;
}
static int find_pid(const char* comm) {
	DIR* d = opendir("/proc");
	if (d == nullptr) return -1;
	int pid = -1;
	while (dirent* de = readdir(d)) {
		if (de->d_name[0] < '0' || de->d_name[0] > '9') continue;
		char path[64], buf[64];
		std::snprintf(path, sizeof(path), "/proc/%s/comm", de->d_name);
		if (read_small(path, buf, sizeof(buf)) <= 0) continue;
		if (char* nl = std::strchr(buf, '\n')) *nl = 0;
		if (std::strcmp(buf, comm) == 0) {
			pid = std::atoi(de->d_name);
			break;
		}
	}
	closedir(d);
	return pid;
}
static void thread_main() {
	pthread_setname_np(pthread_self(), "bc5-meter");
	setpriority(PRIO_PROCESS, static_cast<id_t>(syscall(SYS_gettid)), 5);
	const double hz = static_cast<double>(sysconf(_SC_CLK_TCK));
	static T     prev[512], cur[512];
	int          nprev = 0;
	uint64_t     cpu_busy0[33] {}, cpu_total0[33] {};
	int          mount_pid = -1;
	uint64_t     mount_ticks0 = 0;
	double       mount_find_t = -100;
	MeterCls     cls0[4];
	auto         t_prev = std::chrono::steady_clock::now();
	for (;;) {
		std::this_thread::sleep_for(std::chrono::seconds(1));
		const auto   c0 = std::chrono::steady_clock::now();
		const double dt_ms = std::chrono::duration<double, std::milli>(c0 - t_prev).count();
		t_prev             = c0;
		// the box's CPUs
		int    ncpu = 0, over90 = 0;
		double box_busy_ms = 0, box_pct = -1;
		char   digits[40] {};
		{
			char          buf[8192];
			const ssize_t n = read_small("/proc/stat", buf, sizeof(buf));
			const char*   p = n > 0 ? buf : nullptr;
			while (p != nullptr && std::strncmp(p, "cpu", 3) == 0) {
				int         idx = 0;
				const char* q   = p + 3;
				if (*q >= '0' && *q <= '9') {
					char* e = nullptr;
					idx     = static_cast<int>(std::strtol(q, &e, 10)) + 1;
					q       = e;
				}
				unsigned long long v[8] {};
				for (auto& x: v) {
					while (*q == ' ') q++;
					char* e = nullptr;
					x       = std::strtoull(q, &e, 10);
					if (e == q) break;
					q = e;
				}
				const uint64_t total = v[0] + v[1] + v[2] + v[3] + v[4] + v[5] + v[6] + v[7], busy = total - v[3] - v[4];
				if (idx >= 0 && idx < 33) {
					const uint64_t dt = total - cpu_total0[idx], db = busy - cpu_busy0[idx];
					if (cpu_total0[idx] != 0 && dt != 0) {
						const double pct = 100.0 * static_cast<double>(db) / static_cast<double>(dt);
						if (idx == 0) {
							box_pct = pct;
						} else if (ncpu < 32) {
							digits[ncpu++] = pct < 5 ? '.' : (pct >= 95 ? 'X' : static_cast<char>('0' + static_cast<int>(pct / 10)));
							if (pct >= 90) over90++;
						}
					}
					if (idx == 0 && cpu_total0[0] != 0) box_busy_ms = static_cast<double>(db) * 1000.0 / hz;
					cpu_total0[idx] = total;
					cpu_busy0[idx]  = busy;
				}
				p = std::strchr(p, '\n');
				if (p != nullptr) p++;
			}
		}
		// the package mount (its own process)
		const double now_s    = timing_now();
		double       mount_ms = -1;
		if (mount_pid < 0 && now_s - mount_find_t > 10) {
			mount_find_t = now_s;
			mount_pid    = find_pid("bc5-mount");
			mount_ticks0 = 0;
		}
		if (mount_pid > 0) {
			char path[64];
			std::snprintf(path, sizeof(path), "/proc/%d/stat", mount_pid);
			T m;
			if (read_stat(path, &m)) {
				const uint64_t ticks = m.utime + m.stime;
				if (mount_ticks0 != 0) mount_ms = static_cast<double>(ticks - mount_ticks0) * 1000.0 / hz;
				mount_ticks0 = ticks;
			} else {
				mount_pid = -1;
			}
		}
		// the process's threads
		int ncur = 0;
		if (DIR* d = opendir("/proc/self/task"); d != nullptr) {
			while (dirent* de = readdir(d)) {
				if (de->d_name[0] < '0' || de->d_name[0] > '9' || ncur >= 512) continue;
				T& t  = cur[ncur];
				t     = T {};
				t.tid = std::strtoull(de->d_name, nullptr, 10);
				char path[96], buf[128];
				std::snprintf(path, sizeof(path), "/proc/self/task/%s/stat", de->d_name);
				if (!read_stat(path, &t)) continue;
				std::snprintf(path, sizeof(path), "/proc/self/task/%s/schedstat", de->d_name);
				if (read_small(path, buf, sizeof(buf)) > 0) {
					unsigned long long a = 0, b = 0, c = 0;
					if (std::sscanf(buf, "%llu %llu %llu", &a, &b, &c) == 3) {
						t.exec_ns = a;
						t.wait_ns = b;
						t.slices  = c;
					}
				}
				bool found = false;
				for (int k = 0; k < nprev; k++) {
					if (prev[k].tid == t.tid) {
						t.d_cpu  = static_cast<double>(t.exec_ns - prev[k].exec_ns) / 1e6;
						t.d_wait = static_cast<double>(t.wait_ns - prev[k].wait_ns) / 1e6;
						t.d_sys  = static_cast<double>(t.stime - prev[k].stime) * 1000.0 / hz;
						found    = true;
						break;
					}
				}
				if (!found) { // a thread born in this second: all of it
					t.d_cpu  = static_cast<double>(t.exec_ns) / 1e6;
					t.d_wait = static_cast<double>(t.wait_ns) / 1e6;
					t.d_sys  = static_cast<double>(t.stime) * 1000.0 / hz;
				}
				ncur++;
			}
			closedir(d);
		}
		double title_cpu = 0, title_wait = 0, host_cpu = 0, host_wait = 0;
		double g_cpu[5] {}, g_wait[5] {}, hi_wait_max = 0; // Hi, Lo, Bk, game-main, Render
		int    n_r_title = 0, n_r_host = 0;
		for (int i = 0; i < ncur; i++) {
			const T&   t    = cur[i];
			const bool host = host_name(t.comm);
			(host ? host_cpu : title_cpu) += t.d_cpu;
			(host ? host_wait : title_wait) += t.d_wait;
			if (t.state == 'R') (host ? n_r_host : n_r_title)++;
			int g = -1;
			if (std::strncmp(t.comm, "Job_Hi", 6) == 0) g = 0;
			else if (std::strncmp(t.comm, "Job_Lo", 6) == 0) g = 1;
			else if (std::strncmp(t.comm, "Job_Bk", 6) == 0) g = 2;
			else if (std::strcmp(t.comm, "game-main") == 0) g = 3;
			else if (std::strncmp(t.comm, "Render_Thread", 13) == 0) g = 4;
			if (g >= 0) {
				g_cpu[g] += t.d_cpu;
				g_wait[g] += t.d_wait;
			}
			if (g == 0 && t.d_wait > hi_wait_max) hi_wait_max = t.d_wait;
		}
		std::memcpy(prev, cur, sizeof(T) * static_cast<size_t>(ncur));
		nprev = ncur;
		std::sort(cur, cur + ncur, [](const T& a, const T& b) { return a.d_cpu > b.d_cpu; });
		char   top[1400] {};
		size_t tl = 0;
		for (int i = 0; i < ncur && i < 18 && tl < sizeof(top) - 64; i++) {
			tl += static_cast<size_t>(std::snprintf(top + tl, sizeof(top) - tl, " %s(%c)%.0f/%.0f/%.0f", cur[i].comm, cur[i].state, cur[i].d_cpu, cur[i].d_wait, cur[i].d_sys));
		}
		MeterCls d[4];
		{
			std::lock_guard lock(g_fp_mutex);
			for (int k = 0; k < 4; k++) {
				d[k].sync_ms    = g_meter_cls[k].sync_ms - cls0[k].sync_ms;
				d[k].hints_ms   = g_meter_cls[k].hints_ms - cls0[k].hints_ms;
				d[k].prepare_ms = g_meter_cls[k].prepare_ms - cls0[k].prepare_ms;
				d[k].list_ms    = g_meter_cls[k].list_ms - cls0[k].list_ms;
				d[k].cs_ms      = g_meter_cls[k].cs_ms - cls0[k].cs_ms;
				d[k].submits    = g_meter_cls[k].submits - cls0[k].submits;
				d[k].jobs       = g_meter_cls[k].jobs - cls0[k].jobs;
				cls0[k]         = g_meter_cls[k];
			}
		}
		const double emu_cpu = title_cpu + host_cpu;
		const double rest    = box_busy_ms > 0 ? box_busy_ms - emu_cpu - (mount_ms > 0 ? mount_ms : 0) : -1;
		const auto   cost_us = std::chrono::duration_cast<std::chrono::microseconds>(std::chrono::steady_clock::now() - c0).count();
		journal("cpu meter: t %.3f s, %.0f ms; box busy %.0f %% of %d CPUs, %d over 90 %% [%s]; CPU ms (on a CPU/runnable waiting): title %.0f/%.0f, host %.0f/%.0f, bc5-mount %.0f, rest of the box %.0f; "
		        "Hi %.0f/%.0f (max wait %.0f), Lo %.0f/%.0f, Bk %.0f/%.0f, game-main %.0f/%.0f, Render %.0f/%.0f; runnable now: title %d, host %d; "
		        "submits (n, jobs, sync/hints/prepare/list/cs ms): title %" PRIu64 " %" PRIu64 " %.1f/%.1f/%.1f/%.1f/%.1f, ring %" PRIu64 " %" PRIu64 " %.1f/%.1f/%.1f/%.1f/%.1f, "
		        "chainwd %" PRIu64 " %" PRIu64 " %.1f/%.1f/%.1f/%.1f/%.1f, host %" PRIu64 " %" PRIu64 " %.1f/%.1f/%.1f/%.1f/%.1f; %d threads, top by CPU (cpu/wait/sys ms):%s; cost %lld us\n",
		        now_s, dt_ms, box_pct, ncpu, over90, digits, title_cpu, title_wait, host_cpu, host_wait, mount_ms, rest, g_cpu[0], g_wait[0], hi_wait_max, g_cpu[1], g_wait[1], g_cpu[2], g_wait[2],
		        g_cpu[3], g_wait[3], g_cpu[4], g_wait[4], n_r_title, n_r_host, d[0].submits, d[0].jobs, d[0].sync_ms, d[0].hints_ms, d[0].prepare_ms, d[0].list_ms, d[0].cs_ms, d[1].submits,
		        d[1].jobs, d[1].sync_ms, d[1].hints_ms, d[1].prepare_ms, d[1].list_ms, d[1].cs_ms, d[2].submits, d[2].jobs, d[2].sync_ms, d[2].hints_ms, d[2].prepare_ms, d[2].list_ms,
		        d[2].cs_ms, d[3].submits, d[3].jobs, d[3].sync_ms, d[3].hints_ms, d[3].prepare_ms, d[3].list_ms, d[3].cs_ms, ncur, top, static_cast<long long>(cost_us));
	}
}
static void start_once() {
	static std::once_flag once;
	std::call_once(once, [] {
		const char* e = std::getenv("BC5_0360_METER");
		if (e != nullptr && std::strcmp(e, "0") == 0) return;
		journal("cpu meter: experiment 0360, one line a second from bc5-meter (BC5_0360_METER=0 turns it off)\n");
		std::thread(thread_main).detach();
	});
}
} // namespace Meter0360

static void frame_profile_flip(double drain_ms) {
	Meter0360::start_once(); // experiment 0360
	if (!g_frame_profile_on()) return;
	std::lock_guard lock(g_fp_mutex);
EOF

patch($agc, $inc_old, $inc_new, $sub_old, $sub_new, $job_old, $job_new, $flip_old, $flip_new);
print "meter0360.pl: $marks edits\n";
