# BC5 exp 0439: three more private units for the CJobManager stall (the top session's GO, 11-21 ~21:35): semaphore.cpp,
# pthread.cpp and libKernel.cpp from the shared tree (patch 589ef163). Every replacement must match exactly once.
#   python mkk439.py <dir with the originals> <out dir>
# Switches, all off by default:
#   BC5_0439_SEMA_TRACE=1 (tag st439): for the title's "CJobManager" semaphores only, every signal, wait (entry and return),
#     poll and cancel goes into a ring of the last 64 per semaphore (time, thread name, operation, count asked, the
#     semaphore's count before and after, waiters, result), with totals per semaphore, thread and operation. Printed every
#     5 s by a thread of its own. The count reads are racy by design (diagnosis only).
#   BC5_0439_THREAD_LOG=1 (tag th439): every PthreadSetaffinity and PthreadSetprio call, for every thread, with the target
#     thread's name, the value, the result and the calling thread (PRINT_NAME logs only on the loading thread).
#   BC5_0439_REAL_CPU=1 (tag rc439): sceKernelGetCurrentCpu (NID g0VTBxfJyu0) answers the host CPU (sched_getcpu, modulo 13:
#     the title's masks use bits 0-12) instead of the host's constant 0. Its calls are counted with the switch off too.
import sys

src, dst = sys.argv[1], sys.argv[2]


def rd(path):  # the tree's files may be CRLF (semaphore.cpp, pthread.cpp): work on LF, write back as found
    t = open(path, encoding='utf-8', newline='').read()
    crlf = t.count('\r\n') > t.count('\n') // 2
    return t.replace('\r\n', '\n'), crlf


def wr(path, t, crlf):
    open(path, 'w', encoding='utf-8', newline='').write(t.replace('\n', '\r\n') if crlf else t)


def rep(s, a, b, n=1):
    c = s.count(a)
    assert c == n, (a[:90], c)
    return s.replace(a, b)


# ---- semaphore.cpp ----
s, s_crlf = rd(src + '/semaphore.cpp')
s = rep(s, '#include "bc5/load_stat.hpp" // experiment 0415 (ls415)\n', r'''#include "bc5/load_stat.hpp" // experiment 0415 (ls415)
#include <chrono>  // exp 0439 (tag st439)
#include <map>     // exp 0439 (tag st439)
#include <mutex>   // exp 0439 (tag st439)
#include <string>  // exp 0439 (tag st439)
#include <thread>  // exp 0439 (tag st439)
#include <pthread.h>
namespace st439 { // exp 0439 (tag st439): BC5_0439_SEMA_TRACE, the CJobManager semaphores' last 64 operations
inline bool on() {
	static const bool v = [] {
		const char* e  = std::getenv("BC5_0439_SEMA_TRACE");
		const bool  r = e != nullptr && e[0] == '1' && e[1] == 0;
		std::fprintf(stderr, "[bc5] exp 0439 (tag st439): BC5_0439_SEMA_TRACE=%d\n", r ? 1 : 0);
		return r;
	}();
	return v;
}
struct Op {
	double t = 0;
	char   thread[16] = {};
	char   op = 0; // S signal, w wait enter, W wait return, P poll, C cancel
	int    n = 0, before = 0, after = 0, waiters = 0, result = 0;
};
struct Ring {
	Op       ops[64];
	uint64_t n = 0;
	std::string name;
};
inline std::mutex& mu() { static std::mutex m; return m; }
inline std::map<const void*, Ring>& rings() { static std::map<const void*, Ring> r; return r; }
inline std::map<std::string, std::pair<uint64_t, uint64_t>>& totals() { static std::map<std::string, std::pair<uint64_t, uint64_t>> t; return t; }
inline double now_s() {
	static const auto t0 = std::chrono::steady_clock::now();
	return std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
}
inline void dump(const char* why) {
	std::lock_guard lk(mu());
	for (const auto& [sem, r]: rings()) {
		std::fprintf(stderr, "[bc5] exp 0439 (tag st439): t %.3f s %s: semaphore %s %p, %llu operations so far; the last %d:\n", now_s(), why, r.name.c_str(), sem,
		             static_cast<unsigned long long>(r.n), static_cast<int>(r.n < 64 ? r.n : 64));
		const uint64_t first = r.n < 64 ? 0 : r.n - 64;
		for (uint64_t k = first; k < r.n; k++) {
			const Op& o = r.ops[k % 64];
			std::fprintf(stderr, "[bc5] exp 0439 (tag st439):   #%llu t %.4f %-15s %c n %d count %d -> %d waiters %d result %d\n", static_cast<unsigned long long>(k), o.t, o.thread, o.op, o.n, o.before, o.after,
			             o.waiters, o.result);
		}
	}
	for (const auto& [key, v]: totals())
		std::fprintf(stderr, "[bc5] exp 0439 (tag st439):   total %s: %llu calls, count %llu\n", key.c_str(), static_cast<unsigned long long>(v.first), static_cast<unsigned long long>(v.second));
}
inline void start_dumper() {
	static std::once_flag once;
	std::call_once(once, [] {
		std::thread([] {
			for (;;) {
				std::this_thread::sleep_for(std::chrono::seconds(5));
				dump("every 5 s");
			}
		}).detach();
	});
}
inline void rec(const void* sem, const std::string& name, char op, int n, int before, int after, int waiters, int result) {
	if (!on() || name != "CJobManager") return;
	Op o;
	o.t = now_s();
	pthread_getname_np(pthread_self(), o.thread, sizeof(o.thread));
	o.op = op; o.n = n; o.before = before; o.after = after; o.waiters = waiters; o.result = result;
	std::lock_guard lk(mu());
	Ring& r = rings()[sem];
	if (r.name.empty()) r.name = name;
	r.ops[r.n % 64] = o;
	r.n++;
	char key[96];
	std::snprintf(key, sizeof(key), "%p %s %c", sem, o.thread, op);
	auto& t = totals()[key];
	t.first++;
	t.second += static_cast<uint64_t>(n > 0 ? n : 0);
}
} // namespace st439
''')
s = rep(s, '''	Result Poll(int need_count) {''', '''	int st439_count() { // exp 0439 (tag st439): racy reads for the trace
		Common::LockGuard lock(m_mutex);
		return m_count;
	}
	int st439_waiters() {
		Common::LockGuard lock(m_mutex);
		return static_cast<int>(m_waiting_threads.size());
	}
	Result Poll(int need_count) {''')
s = rep(s, '''	LOGF("\\t Semaphore create: %s, ptr=0x%016" PRIx64 ", init=%d, max=%d\\n", name,''', '''	if (st439::on() && std::string(name) == "CJobManager") { // exp 0439 (tag st439)
		st439::rec(*sem, name, 'c', init, 0, init, 0, max);
		st439::start_dumper();
	}
	LOGF("\\t Semaphore create: %s, ptr=0x%016" PRIx64 ", init=%d, max=%d\\n", name,''')
s = rep(s, '''	auto result = sem->Wait(need, time);''', '''	const int st_b = st439::on() ? sem->st439_count() : 0; // exp 0439 (tag st439)
	if (st439::on()) st439::rec(sem, sem->GetName(), 'w', need, st_b, st_b, sem->st439_waiters(), 0);
	auto result = sem->Wait(need, time);
	if (st439::on()) st439::rec(sem, sem->GetName(), 'W', need, st_b, sem->st439_count(), sem->st439_waiters(), static_cast<int>(result));''')
s = rep(s, '''	auto result = sem->Poll(need);''', '''	const int st_b = st439::on() ? sem->st439_count() : 0; // exp 0439 (tag st439)
	auto result = sem->Poll(need);
	if (st439::on()) st439::rec(sem, sem->GetName(), 'P', need, st_b, sem->st439_count(), sem->st439_waiters(), static_cast<int>(result));''')
s = rep(s, '''	auto result = sem->Signal(count);''', '''	const int st_b = st439::on() ? sem->st439_count() : 0; // exp 0439 (tag st439)
	const int st_w = st439::on() ? sem->st439_waiters() : 0;
	auto result = sem->Signal(count);
	if (st439::on()) st439::rec(sem, sem->GetName(), 'S', count, st_b, sem->st439_count(), st_w, static_cast<int>(result));''')
s = rep(s, '''	auto result = sem->Cancel(count, threads);''', '''	const int st_b = st439::on() ? sem->st439_count() : 0; // exp 0439 (tag st439)
	auto result = sem->Cancel(count, threads);
	if (st439::on()) st439::rec(sem, sem->GetName(), 'C', count, st_b, sem->st439_count(), sem->st439_waiters(), static_cast<int>(result));''')
wr(dst + '/semaphore.cpp', s, s_crlf)

# ---- pthread.cpp ----
p, p_crlf = rd(src + '/pthread.cpp')
TH = r'''static bool th439_on() { // exp 0439 (tag th439): BC5_0439_THREAD_LOG
	static const bool v = [] {
		const char* e = std::getenv("BC5_0439_THREAD_LOG");
		return e != nullptr && e[0] == '1' && e[1] == 0;
	}();
	return v;
}
static void th439_caller(char* out, size_t cap) {
	out[0] = 0;
	pthread_getname_np(pthread_self(), out, cap);
}
'''
p = rep(p, '''int KYTY_SYSV_ABI PthreadSetaffinity(Pthread thread, KernelCpumask mask) {
	PRINT_NAME();

	if (thread == nullptr) {
		return KERNEL_ERROR_ESRCH;
	}

	auto result = PthreadAttrSetaffinity(&thread->attr, mask);
''', TH + '''int KYTY_SYSV_ABI PthreadSetaffinity(Pthread thread, KernelCpumask mask) {
	PRINT_NAME();

	if (thread == nullptr) {
		return KERNEL_ERROR_ESRCH;
	}

	auto result = PthreadAttrSetaffinity(&thread->attr, mask);
	if (th439_on()) { // exp 0439 (tag th439)
		char c[16];
		th439_caller(c, sizeof(c));
		std::fprintf(stderr, "[bc5] exp 0439 (tag th439): PthreadSetaffinity(%s, 0x%llx) -> %d (from %s)\\n", thread->name.c_str(), static_cast<unsigned long long>(mask), result, c);
	}
''')
p = rep(p, '''int KYTY_SYSV_ABI PthreadSetprio(Pthread thread, int prio) {
	PRINT_NAME();
''', '''int KYTY_SYSV_ABI PthreadSetprio(Pthread thread, int prio) {
	PRINT_NAME();
	if (th439_on() && thread != nullptr) { // exp 0439 (tag th439): the call; its result is the function's return
		char c[16];
		th439_caller(c, sizeof(c));
		std::fprintf(stderr, "[bc5] exp 0439 (tag th439): PthreadSetprio(%s, %d) (from %s)\\n", thread->name.c_str(), prio, c);
	}
''')
wr(dst + '/pthread.cpp', p, p_crlf)

# ---- libKernel.cpp ----
k, k_crlf = rd(src + '/libKernel.cpp')
k = rep(k, '''static KYTY_SYSV_ABI int KernelGetCurrentCpu() {
	PRINT_NAME();

	return 0;
}''', '''static KYTY_SYSV_ABI int KernelGetCurrentCpu() {
	PRINT_NAME();
	// exp 0439 (tag rc439): counted; BC5_0439_REAL_CPU=1 answers the host CPU modulo 13 (the title's masks use bits 0-12)
	static const bool real = [] {
		const char* e = std::getenv("BC5_0439_REAL_CPU");
		const bool  r = e != nullptr && e[0] == '1' && e[1] == 0;
		std::fprintf(stderr, "[bc5] exp 0439 (tag rc439): sceKernelGetCurrentCpu answers %s (BC5_0439_REAL_CPU=%d)\\n", r ? "the host CPU modulo 13" : "0, the host's constant", r ? 1 : 0);
		return r;
	}();
	static std::atomic<uint64_t> calls {0};
	const uint64_t k = ++calls;
	int            cpu = 0;
	if (real) {
		const int c = sched_getcpu();
		cpu         = c < 0 ? 0 : c % 13;
	}
	if (k <= 8 || k == 100 || k == 1000 || k == 10000 || k % 100000 == 0) {
		char tn[16] = {};
		pthread_getname_np(pthread_self(), tn, sizeof(tn));
		std::fprintf(stderr, "[bc5] exp 0439 (tag rc439): sceKernelGetCurrentCpu call %llu from %s -> %d\\n", static_cast<unsigned long long>(k), tn, cpu);
	}
	return cpu;
}''')
wr(dst + '/libKernel.cpp', k, k_crlf)
print("ok")
