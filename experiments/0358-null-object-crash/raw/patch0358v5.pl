#!/usr/bin/perl
# BC5 experiment 0358, trap v5 + the second fix candidate: applied AFTER patch0358.pl, patch0358v3.pl and patch0358v4.pl
# to the same PRIVATE copies (the shared tree is only read). Same four units.
#   BC5_0358_FIX is now a bit mask: bit 1 (value 1) the targeted semaphore wake of v4; bit 2 (value 2) the host's own
#   threads at nice +5 (F453: at the fight the box's cores are saturated - five Bk workers runnable with little CPU, a
#   woken Hi worker 1.1-1.7 ms from the signal to its return - so the threads the console does not have, the host's
#   GPU feed, pollers and helpers, yield to the title's threads; the title's own threads keep their mapped nice).
#   kernel/semaphore.cpp: bc5_fix_on() reads bit 1.
#   libs/bc5LleAgc.cpp: the sampler, every fifth second, lists every thread of the process with its CPU over the
#     interval and its state (the top 12 journaled) and the system's busy share from /proc/stat; under bit 2 it puts
#     each host thread (not a guest pthread, not the game thread, not the process's main thread) at nice +5 once, and
#     journals which.
#   loader/runtimeLinker.cpp: the crash print adds every host thread's state and CPU (the guest ones are printed by v4).
#   The /proc reader of v4 gains the thread's comm and a with_status switch (the sampler skips /status).
# usage: patch0358v5.pl <private src root>
use strict;
use warnings;
my ($root) = @ARGV;
die "usage: patch0358v5.pl <src root>\n" unless defined $root;
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
	open(my $w, ">", $file) or die "$file: $!\n";
	print $w $s;
	close $w;
}

# the v4 reader, in both units: comm, and the with_status switch
my @reader_edits = (
	"\tchar     state = '?';\n\tdouble   cpu_s = 0, user_s = 0;\n\tuint64_t vol = 0, invol = 0;\n};\n" .
	"static bool bc5_proc_state(uint64_t os_tid, Bc5ProcState* out) {\n",
	"\tchar     state = '?';\n\tdouble   cpu_s = 0, user_s = 0;\n\tuint64_t vol = 0, invol = 0;\n\tchar     comm[20] {}; // trap v5\n};\n" .
	"static bool bc5_proc_state(uint64_t os_tid, Bc5ProcState* out, bool with_status = true) {\n",

	"\tout->state = p[2];\n",
	"\tout->state = p[2];\n" .
	"\tif (const char* a = std::strchr(buf, '('); a != nullptr && p > a) { // trap v5: the comm between the parentheses\n" .
	"\t\tsize_t n = static_cast<size_t>(p - a - 1);\n" .
	"\t\tif (n > sizeof(out->comm) - 1) n = sizeof(out->comm) - 1;\n" .
	"\t\tstd::memcpy(out->comm, a + 1, n);\n" .
	"\t\tout->comm[n] = 0;\n" .
	"\t}\n",

	"\tstd::snprintf(path, sizeof(path), \"/proc/self/task/%\" PRIu64 \"/status\", os_tid);\n\tfd = open(path, O_RDONLY | O_CLOEXEC);\n",
	"\tif (!with_status) return true; // trap v5\n" .
	"\tstd::snprintf(path, sizeof(path), \"/proc/self/task/%\" PRIu64 \"/status\", os_tid);\n\tfd = open(path, O_RDONLY | O_CLOEXEC);\n",
);

# ---- kernel/semaphore.cpp: bit 1
my $sem = "$root/src/kernel/semaphore.cpp";
patch($sem,
	"\t\tconst char* e = std::getenv(\"BC5_0358_FIX\");\n\t\treturn e != nullptr && std::strcmp(e, \"0\") != 0;\n",
	"\t\tconst char* e = std::getenv(\"BC5_0358_FIX\");\n\t\treturn e != nullptr && (std::strtol(e, nullptr, 10) & 1) != 0; // v5: a bit mask, bit 1 the targeted wake\n",
);

# ---- loader/runtimeLinker.cpp: every host thread at the fault
my $rtl = "$root/src/loader/runtimeLinker.cpp";
patch($rtl,
	"#include <fcntl.h> // BC5 (experiment 0358, trap v4)\n",
	"#include <fcntl.h> // BC5 (experiment 0358, trap v4)\n#include <dirent.h> // BC5 (experiment 0358, trap v5)\n#include <sys/resource.h>\n",
	@reader_edits,

	"\t\t\t\t\tbc5_sema_ring_dump([](const char* line, void*) { Bc5CrashLog(\"thread trap: %s\\n\", line); }, nullptr);\n",
	"\t\t\t\t\t// trap v5: the host's own threads (every task of the process that is not a guest pthread)\n" .
	"\t\t\t\t\tif (DIR* d = opendir(\"/proc/self/task\"); d != nullptr) {\n" .
	"\t\t\t\t\t\twhile (dirent* de = readdir(d)) {\n" .
	"\t\t\t\t\t\t\tif (de->d_name[0] < '0' || de->d_name[0] > '9') continue;\n" .
	"\t\t\t\t\t\t\tconst uint64_t tid   = std::strtoull(de->d_name, nullptr, 10);\n" .
	"\t\t\t\t\t\t\tbool           guest = false;\n" .
	"\t\t\t\t\t\t\tfor (int k = 0; k < nnames; k++) {\n" .
	"\t\t\t\t\t\t\t\tif (names[k].os_tid == tid) { guest = true; break; }\n" .
	"\t\t\t\t\t\t\t}\n" .
	"\t\t\t\t\t\t\tif (guest) continue;\n" .
	"\t\t\t\t\t\t\tBc5ProcState ps;\n" .
	"\t\t\t\t\t\t\tif (!bc5_proc_state(tid, &ps, false)) continue;\n" .
	"\t\t\t\t\t\t\tint prio = getpriority(PRIO_PROCESS, static_cast<id_t>(tid));\n" .
	"\t\t\t\t\t\t\tBc5CrashLog(\"thread trap: host thread \\\"%s\\\" os %\" PRIu64 \": state %c cpu %.3f s (user %.3f) nice %d\\n\", ps.comm, tid, ps.state, ps.cpu_s, ps.user_s, prio);\n" .
	"\t\t\t\t\t\t}\n" .
	"\t\t\t\t\t\tclosedir(d);\n" .
	"\t\t\t\t\t}\n" .
	"\t\t\t\t\tbc5_sema_ring_dump([](const char* line, void*) { Bc5CrashLog(\"thread trap: %s\\n\", line); }, nullptr);\n",
);

# ---- libs/bc5LleAgc.cpp: the thread table every fifth sample, the system's busy share, the nice +5 under bit 2
my $agc = "$root/src/libs/bc5LleAgc.cpp";
patch($agc,
	"#include <sys/mman.h>\n#include <sys/uio.h> // BC5 (experiment 0358, trap v3)\n",
	"#include <sys/mman.h>\n#include <sys/uio.h> // BC5 (experiment 0358, trap v3)\n#include <dirent.h> // BC5 (experiment 0358, trap v5)\n#include <sys/resource.h>\n#include <sys/syscall.h>\n",
	@reader_edits,

	"\t        s.e[1].bad + s.e[1].nulls, s.e[2].bad + s.e[2].nulls, s.owner_id, s.over, hi_cpu[0], hi_cpu[1], hi_cpu[2], hi_cpu[3], hi_cpu[4], hi_state, ns2, cost_max);\n",
	"\t        s.e[1].bad + s.e[1].nulls, s.e[2].bad + s.e[2].nulls, s.owner_id, s.over, hi_cpu[0], hi_cpu[1], hi_cpu[2], hi_cpu[3], hi_cpu[4], hi_state, ns2, cost_max);\n" .
	"\t// trap v5: every fifth sample, the process's threads (CPU over the interval, state) and the system's busy\n" .
	"\t// share; under BC5_0358_FIX bit 2 the host's own threads go to nice +5 once (F453).\n" .
	"\tstatic int tick = 0;\n" .
	"\tif (++tick % 5 != 0) return;\n" .
	"\tstatic const int fix = [] {\n" .
	"\t\tconst char* e = std::getenv(\"BC5_0358_FIX\");\n" .
	"\t\treturn e != nullptr ? static_cast<int>(std::strtol(e, nullptr, 10)) : 0;\n" .
	"\t}();\n" .
	"\tstruct T {\n" .
	"\t\tuint64_t tid;\n" .
	"\t\tdouble   cpu;\n" .
	"\t\tdouble   delta;\n" .
	"\t\tchar     state;\n" .
	"\t\tbool     guest;\n" .
	"\t\tchar     comm[20];\n" .
	"\t};\n" .
	"\tstatic T        prev[512];\n" .
	"\tstatic int      nprev = 0;\n" .
	"\tstatic uint64_t niced[512];\n" .
	"\tstatic int      nniced = 0;\n" .
	"\tstatic uint64_t gtid[512];\n" .
	"\tstatic int      ngt = 0;\n" .
	"\tstatic uint64_t busy0 = 0, total0 = 0;\n" .
	"\tconst auto      c5 = std::chrono::steady_clock::now();\n" .
	"\tngt = 0;\n" .
	"\tbc5_pthread_each([](int, int, const char*, uint64_t os_tid, void*) { if (ngt < 512) gtid[ngt++] = os_tid; }, nullptr);\n" .
	"\tconst uint64_t self_tid = static_cast<uint64_t>(syscall(SYS_gettid));\n" .
	"\tconst uint64_t main_tid = static_cast<uint64_t>(getpid());\n" .
	"\tT   cur[512];\n" .
	"\tint ncur = 0;\n" .
	"\tif (DIR* d = opendir(\"/proc/self/task\"); d != nullptr) {\n" .
	"\t\twhile (dirent* de = readdir(d)) {\n" .
	"\t\t\tif (de->d_name[0] < '0' || de->d_name[0] > '9' || ncur >= 512) continue;\n" .
	"\t\t\tT& t  = cur[ncur];\n" .
	"\t\t\tt.tid = std::strtoull(de->d_name, nullptr, 10);\n" .
	"\t\t\tBc5ProcState ps;\n" .
	"\t\t\tif (!bc5_proc_state(t.tid, &ps, false)) continue;\n" .
	"\t\t\tt.cpu   = ps.cpu_s;\n" .
	"\t\t\tt.state = ps.state;\n" .
	"\t\t\tstd::memcpy(t.comm, ps.comm, sizeof(t.comm));\n" .
	"\t\t\tt.guest = false;\n" .
	"\t\t\tfor (int k = 0; k < ngt; k++) {\n" .
	"\t\t\t\tif (gtid[k] == t.tid) { t.guest = true; break; }\n" .
	"\t\t\t}\n" .
	"\t\t\tt.delta = t.cpu;\n" .
	"\t\t\tfor (int k = 0; k < nprev; k++) {\n" .
	"\t\t\t\tif (prev[k].tid == t.tid) { t.delta = t.cpu - prev[k].cpu; break; }\n" .
	"\t\t\t}\n" .
	"\t\t\tncur++;\n" .
	"\t\t}\n" .
	"\t\tclosedir(d);\n" .
	"\t}\n" .
	"\t// the system's busy share over the interval (/proc/stat's cpu line: user nice system idle iowait irq softirq)\n" .
	"\tdouble busy_pct = -1;\n" .
	"\tif (int fd = open(\"/proc/stat\", O_RDONLY | O_CLOEXEC); fd >= 0) {\n" .
	"\t\tchar          buf[256] {};\n" .
	"\t\tconst ssize_t n = read(fd, buf, sizeof(buf) - 1);\n" .
	"\t\tclose(fd);\n" .
	"\t\tif (n > 4) {\n" .
	"\t\t\tunsigned long long f[7] {};\n" .
	"\t\t\tif (std::sscanf(buf, \"cpu %llu %llu %llu %llu %llu %llu %llu\", &f[0], &f[1], &f[2], &f[3], &f[4], &f[5], &f[6]) == 7) {\n" .
	"\t\t\t\tconst uint64_t total = f[0] + f[1] + f[2] + f[3] + f[4] + f[5] + f[6], busy = total - f[3] - f[4];\n" .
	"\t\t\t\tif (total0 != 0 && total > total0) busy_pct = 100.0 * static_cast<double>(busy - busy0) / static_cast<double>(total - total0);\n" .
	"\t\t\t\tbusy0  = busy;\n" .
	"\t\t\t\ttotal0 = total;\n" .
	"\t\t\t}\n" .
	"\t\t}\n" .
	"\t}\n" .
	"\t// nice +5 for the host's own threads, once each (bit 2)\n" .
	"\tchar niced_line[512] {};\n" .
	"\tsize_t nl = 0;\n" .
	"\tif ((fix & 2) != 0) {\n" .
	"\t\tfor (int i = 0; i < ncur; i++) {\n" .
	"\t\t\tconst T& t = cur[i];\n" .
	"\t\t\tif (t.guest || t.tid == self_tid || t.tid == main_tid || std::strcmp(t.comm, \"game-main\") == 0) continue; // game-main: the title's main thread (not in the pool's list)\n" .
	"\t\t\tbool done = false;\n" .
	"\t\t\tfor (int k = 0; k < nniced; k++) {\n" .
	"\t\t\t\tif (niced[k] == t.tid) { done = true; break; }\n" .
	"\t\t\t}\n" .
	"\t\t\tif (done || nniced >= 512) continue;\n" .
	"\t\t\tconst int rc = setpriority(PRIO_PROCESS, static_cast<id_t>(t.tid), 5);\n" .
	"\t\t\tniced[nniced++] = t.tid;\n" .
	"\t\t\tif (nl < sizeof(niced_line) - 40) nl += static_cast<size_t>(std::snprintf(niced_line + nl, sizeof(niced_line) - nl, \" %s(%\" PRIu64 \")%s\", t.comm, t.tid, rc == 0 ? \"\" : \"!\"));\n" .
	"\t\t}\n" .
	"\t}\n" .
	"\t// the top 12 by CPU over the interval\n" .
	"\tstd::sort(cur, cur + ncur, [](const T& a, const T& b) { return a.delta > b.delta; });\n" .
	"\tchar line[1024] {};\n" .
	"\tsize_t ll = 0;\n" .
	"\tfor (int i = 0; i < ncur && i < 12 && ll < sizeof(line) - 64; i++) {\n" .
	"\t\tll += static_cast<size_t>(std::snprintf(line + ll, sizeof(line) - ll, \" %s%s(%c)%.0f\", cur[i].guest ? \"\" : \"host:\", cur[i].comm, cur[i].state, cur[i].delta * 1e3));\n" .
	"\t}\n" .
	"\tint nR = 0;\n" .
	"\tfor (int i = 0; i < ncur; i++) if (cur[i].state == 'R') nR++;\n" .
	"\tconst auto ns5 = static_cast<uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now() - c5).count());\n" .
	"\tjournal(\"thread sample: t %.3f s, %d threads, %d runnable, system busy %.0f %%, fix %d; top by CPU ms over the interval:%s; cost %\" PRIu64 \" ns%s%s\\n\", now, ncur, nR, busy_pct, fix, line, ns5,\n" .
	"\t        nl != 0 ? \"; niced to +5:\" : \"\", niced_line);\n" .
	"\tstd::memcpy(prev, cur, sizeof(T) * static_cast<size_t>(ncur));\n" .
	"\tnprev = ncur;\n",
);
print "patch0358v5.pl: $marks edits\n";
