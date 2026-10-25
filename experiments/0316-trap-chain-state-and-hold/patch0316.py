#!/usr/bin/env python3
# BC5 experiment 0316: exp 0313's write trap on the pages of the build chain's argument blocks, extended with the state of
# the GPU job that armed the page — and a holding mode that is the fix test. In src/libs/bc5LleAgc.cpp of the shared tree
# as integrated on the box (md5 5bccbb80). BC5_DIRECT_WRITE_TRAP=1 (log) or =2 (hold).
#   - Arming (as 0313b: at each count-pass dispatch, the page of struct + 0x100 made read-only, shared memfd pages only,
#     an LRU ring of 64 pages) now records the submission being filtered (#n = g_submits at filter time, the count pass's
#     acb) and its completion queue (t_cq: 0 the game thread's, 1 the ring thread's).
#   - The completion thread notes the highest submission number it has seen complete, per queue (jobs complete in order
#     within a queue): x0316::note_done(index, n) right after the job's fence wait.
#   - A caught store (SIGSEGV on an armed page) records, besides 0313b's {thread, RIP, address, the four words at RSP},
#     the arming's #n and queue and the queue's highest completed number at the fault: "the chain of this struct is done /
#     NOT done (frontier #…)". The four RSP words are journaled raw too, and an address in an anonymous mapping is named
#     anon@<mapping start>+offset (the title's code: eboot.bin / prx loaded by KytyPlus; the play log gives the bases).
#   - Mode 2 (BC5_DIRECT_WRITE_TRAP=2): if the arming's job is NOT done at the fault and the faulting thread is not a host
#     thread (its comm does not start with "bc5-"), the handler holds the thread — nanosleep 50 µs steps — until the
#     queue's completed number reaches #n, at most 2.5 s (the fence timeout is 2 s: a wedged GPU frees the thread), then
#     makes the page writable and lets the store through; the page is not re-armed (the slot is the title's again). That
#     is the console's semantics: the CPU cannot reuse the slot before the GPU consumed it. The hold's length, count and
#     give-ups are journaled per store and per second. In mode 1 the page is single-stepped and re-armed as in 0313b.
# usage: patch0316.py <src root of the shared tree> <out dir>
import difflib, hashlib, os, sys

EDITS = {
    'src/libs/bc5LleAgc.cpp': [
        ('''#include <sys/mman.h>
''', 1, '''#include <sys/mman.h>
#include <csignal>       // experiment 0316
#include <fcntl.h>       // experiment 0316: the faulting thread's comm
#include <sys/syscall.h> // experiment 0316: SYS_gettid in the handler
#include <ucontext.h>    // experiment 0316
'''),
        ('''static void timeout_probe(const uint32_t* sub_ib, uint32_t sub_n, const char* kind, uint64_t n, const std::vector<uint32_t>* ran, const std::vector<GeProbeSlot>* gep = nullptr) {
''', 1, '''// Experiment 0316: a software watchpoint on the pages of the build chain's argument blocks (exp 0313), with the state of
// the job that armed the page, and a holding mode. The SIGSEGV handler only touches the ring, mprotect, nanosleep, the
// comm file and the signal context (async-signal-safe); the filter thread journals the ring.
namespace x0316 {
struct Ev {
	uint64_t tid = 0, rip = 0, addr = 0, page = 0, st = 0;
	uint64_t ret[4] = {};         // the four words at the faulting thread's RSP — candidate return addresses
	uint64_t n = 0, done_n = 0;   // the arming's submission, and its queue's highest completed submission at the fault
	uint64_t hold_ns = 0;         // mode 2: how long the thread was held
	int      cq = 0;
	bool     host = false, gaveup = false;
	double   t = 0;
};
struct Page {
	uint64_t page = 0, st = 0, n = 0;
	uint32_t budget = 0;
	int      cq = 0;
	bool     armed = false;
};
static std::atomic<bool>      g_on {false};
static std::atomic<uint32_t>  g_mode {0};        // 1 log, 2 hold
static std::atomic<uint32_t>  g_wr {0}, g_rd {0}; // the ring's write and read indices
static Ev                     g_ring[1024];
static Page                   g_pages[64];
static std::atomic<uint32_t>  g_npages {0};
static std::atomic<uint32_t>  g_next_page {0};   // the page table is an LRU ring — the oldest arming is replaced, never a refusal
static std::atomic<uint64_t>  g_caught {0}, g_dropped {0}, g_foreign {0}, g_notdone {0}, g_held {0}, g_held_ns {0}, g_gaveup {0}, g_hostskip {0};
static std::atomic<uint64_t>  g_done_n[2] {{0}, {0}}; // per completion queue: the highest submission number seen complete
static std::atomic<bool>      g_trap_taken {false}; // a SIGTRAP handler was already installed: never arm (the trap flag would collide)
static constexpr uint64_t     kCap = 4096;          // the hard cap on caught stores a process: beyond it nothing is armed again
static struct sigaction       g_old_segv, g_old_trap;
static thread_local uint64_t  t_rearm = 0; // the page the SIGTRAP handler re-protects
static uint64_t now_ns() {
	timespec ts {};
	clock_gettime(CLOCK_MONOTONIC, &ts);
	return static_cast<uint64_t>(ts.tv_sec) * 1000000000ull + static_cast<uint64_t>(ts.tv_nsec);
}
static double now_s() { return static_cast<double>(now_ns()) * 1e-9; }
// The completion thread of queue index has seen submission n complete (jobs complete in order within a queue).
static void note_done(int index, uint64_t n) {
	std::atomic<uint64_t>& d = g_done_n[index == 1 ? 1 : 0];
	uint64_t cur = d.load(std::memory_order_relaxed);
	while (n > cur && !d.compare_exchange_weak(cur, n, std::memory_order_release, std::memory_order_relaxed)) {}
}
static int page_index(uint64_t page) {
	const uint32_t n = g_npages.load(std::memory_order_acquire);
	for (uint32_t i = 0; i < n && i < 64; i++) {
		if (g_pages[i].page == page) return static_cast<int>(i);
	}
	return -1;
}
// True when the calling thread is one of the host's own ("bc5-…" comm): the completion threads, the ring thread, the
// APR workers, the filter — never held in mode 2 (a completion thread held for its own job would deadlock).
static bool host_thread(uint64_t tid) {
	char path[64];
	int  k = 0;
	const char* p = "/proc/self/task/";
	while (*p) path[k++] = *p++;
	char digits[24];
	int  nd = 0;
	uint64_t v = tid;
	do { digits[nd++] = static_cast<char>('0' + v % 10); v /= 10; } while (v != 0);
	while (nd > 0) path[k++] = digits[--nd];
	p = "/comm";
	while (*p) path[k++] = *p++;
	path[k] = 0;
	const int fd = open(path, O_RDONLY | O_CLOEXEC);
	if (fd < 0) return false;
	char buf[8] = {};
	const ssize_t r = read(fd, buf, 4);
	close(fd);
	return r == 4 && buf[0] == 'b' && buf[1] == 'c' && buf[2] == '5' && buf[3] == '-';
}
static void on_segv(int sig, siginfo_t* si, void* uc_) {
	const uint64_t a    = reinterpret_cast<uint64_t>(si->si_addr);
	const uint64_t page = a & ~0xfffull;
	const int      pi   = page_index(page);
	auto*          uc   = static_cast<ucontext_t*>(uc_);
	if (pi < 0 || !g_pages[pi].armed) { // not ours: the host's previous action
		g_foreign.fetch_add(1, std::memory_order_relaxed);
		if (g_old_segv.sa_flags & SA_SIGINFO) {
			if (g_old_segv.sa_sigaction != nullptr) { g_old_segv.sa_sigaction(sig, si, uc_); return; }
		} else if (g_old_segv.sa_handler != SIG_DFL && g_old_segv.sa_handler != SIG_IGN) {
			g_old_segv.sa_handler(sig);
			return;
		}
		signal(SIGSEGV, SIG_DFL); // default: the fault repeats and kills the process as before
		return;
	}
	const uint64_t tid    = static_cast<uint64_t>(syscall(SYS_gettid));
	const int      cq     = g_pages[pi].cq;
	const uint64_t n      = g_pages[pi].n;
	const uint64_t done_n = g_done_n[cq].load(std::memory_order_acquire);
	const bool     host   = host_thread(tid);
	uint64_t       hold   = 0;
	bool           gaveup = false;
	if (done_n < n) g_notdone.fetch_add(1, std::memory_order_relaxed);
	if (g_mode.load(std::memory_order_relaxed) == 2 && done_n < n) {
		if (host) {
			g_hostskip.fetch_add(1, std::memory_order_relaxed);
		} else { // the fix test: the title's thread waits for the GPU job that reads this slot, as on the console
			const uint64_t t0 = now_ns();
			while (g_done_n[cq].load(std::memory_order_acquire) < n) {
				if (now_ns() - t0 > 2500000000ull) { gaveup = true; break; } // the fence timeout is 2 s: a wedged GPU frees the thread
				timespec ts {0, 50000};
				nanosleep(&ts, nullptr);
			}
			hold = now_ns() - t0;
			g_held.fetch_add(1, std::memory_order_relaxed);
			g_held_ns.fetch_add(hold, std::memory_order_relaxed);
			if (gaveup) g_gaveup.fetch_add(1, std::memory_order_relaxed);
		}
	}
	const uint32_t w = g_wr.fetch_add(1, std::memory_order_acq_rel);
	if (w - g_rd.load(std::memory_order_acquire) < 1024) {
		Ev& e     = g_ring[w & 1023u];
		e.tid     = tid;
		e.rip     = static_cast<uint64_t>(uc->uc_mcontext.gregs[REG_RIP]);
		e.addr    = a;
		e.page    = page;
		e.st      = g_pages[pi].st;
		e.n       = n;
		e.cq      = cq;
		e.done_n  = done_n;
		e.hold_ns = hold;
		e.host    = host;
		e.gaveup  = gaveup;
		e.t       = now_s();
		const auto* sp = reinterpret_cast<const uint64_t*>(uc->uc_mcontext.gregs[REG_RSP]); // the thread's own stack: mapped
		for (int k = 0; k < 4; k++) e.ret[k] = sp[k];
	} else {
		g_dropped.fetch_add(1, std::memory_order_relaxed);
	}
	const uint64_t caught = g_caught.fetch_add(1, std::memory_order_relaxed) + 1;
	mprotect(reinterpret_cast<void*>(page), 4096, PROT_READ | PROT_WRITE);
	if (g_mode.load(std::memory_order_relaxed) != 2 && g_pages[pi].budget > 0 && caught < kCap) {
		g_pages[pi].budget--;
		t_rearm = page;
		uc->uc_mcontext.gregs[REG_EFL] |= 0x100; // trap flag: one instruction, then SIGTRAP re-protects
	} else {
		g_pages[pi].armed = false; // mode 2, or the budget spent: the page stays writable until the next arming
	}
}
static void on_trap(int sig, siginfo_t* si, void* uc_) {
	auto* uc = static_cast<ucontext_t*>(uc_);
	if (t_rearm != 0) {
		mprotect(reinterpret_cast<void*>(t_rearm), 4096, PROT_READ);
		t_rearm = 0;
		uc->uc_mcontext.gregs[REG_EFL] &= ~0x100ull;
		return;
	}
	if (g_old_trap.sa_flags & SA_SIGINFO) {
		if (g_old_trap.sa_sigaction != nullptr) { g_old_trap.sa_sigaction(sig, si, uc_); return; }
	} else if (g_old_trap.sa_handler != SIG_DFL && g_old_trap.sa_handler != SIG_IGN) {
		g_old_trap.sa_handler(sig);
		return;
	}
	signal(SIGTRAP, SIG_DFL);
}
static void install_once(uint32_t mode) {
	static std::once_flag once;
	std::call_once(once, [mode] {
		g_mode.store(mode, std::memory_order_release);
		struct sigaction sa {};
		sa.sa_flags     = SA_SIGINFO | SA_NODEFER;
		sa.sa_sigaction = on_segv;
		sigemptyset(&sa.sa_mask);
		sigaction(SIGSEGV, &sa, &g_old_segv);
		struct sigaction st {};
		st.sa_flags     = SA_SIGINFO | SA_NODEFER;
		st.sa_sigaction = on_trap;
		sigemptyset(&st.sa_mask);
		sigaction(SIGTRAP, &st, &g_old_trap);
		const bool taken = (g_old_trap.sa_flags & SA_SIGINFO) ? g_old_trap.sa_sigaction != nullptr : (g_old_trap.sa_handler != SIG_DFL && g_old_trap.sa_handler != SIG_IGN);
		if (taken) { // somebody else uses SIGTRAP (a debugger hook, the host): give it back and never arm
			sigaction(SIGTRAP, &g_old_trap, nullptr);
			g_trap_taken.store(true, std::memory_order_release);
		}
		g_on.store(true, std::memory_order_release);
	});
}
// Arms the page of struct + 0x100 (the chain's argument block) if the device maps it as a shared memfd page; returns a text.
static const char* arm(uint64_t st, const std::vector<bc5::direct::Mapping>& maps, uint64_t n, int cq, uint32_t mode) {
	const uint64_t page = (st + 0x100u) & ~0xfffull;
	auto it = std::upper_bound(maps.begin(), maps.end(), page, [](uint64_t v, const bc5::direct::Mapping& m) { return v < m.va; });
	if (it == maps.begin()) return "not armed: page not mapped";
	--it;
	if (!(page >= it->va && page + 4096 <= it->va + it->size)) return "not armed: page not mapped";
	if (!it->shared) return "not armed: a userptr page (a read-only VMA would break the GPU's write path)";
	install_once(mode);
	if (g_trap_taken.load(std::memory_order_acquire)) return "not armed: a SIGTRAP handler is already installed (the trap flag would collide)";
	if (mode != 2 && g_caught.load(std::memory_order_relaxed) >= kCap) return "not armed: the hard cap of caught stores is spent"; // mode 2: one fault per arming, no cap
	int pi = page_index(page);
	if (pi < 0) {
		const uint32_t np = g_npages.load(std::memory_order_acquire);
		if (np < 64) {
			g_pages[np].page = page;
			g_pages[np].st   = st;
			g_npages.store(np + 1, std::memory_order_release);
			pi = static_cast<int>(np);
		} else { // replace the oldest arming (an LRU ring); its page is left writable
			const uint32_t slot = g_next_page.fetch_add(1, std::memory_order_acq_rel) & 63u;
			if (g_pages[slot].armed) mprotect(reinterpret_cast<void*>(g_pages[slot].page), 4096, PROT_READ | PROT_WRITE);
			g_pages[slot].armed = false;
			g_pages[slot].page  = page;
			g_pages[slot].st    = st;
			pi = static_cast<int>(slot);
		}
	}
	g_pages[pi].st     = st;
	g_pages[pi].n      = n;
	g_pages[pi].cq     = cq == 1 ? 1 : 0;
	g_pages[pi].budget = 32;
	g_pages[pi].armed  = true;
	return mprotect(reinterpret_cast<void*>(page), 4096, PROT_READ) == 0 ? "ARMED" : "not armed: mprotect failed";
}
// The module and offset of an address, from /proc/self/maps (read once per distinct page; the filter thread only). An
// anonymous mapping is named anon@<its start>+offset — the title's own code, loaded by KytyPlus (the play log has the bases).
static std::string where(uint64_t rip) {
	static std::mutex                              m;
	static std::map<uint64_t, std::pair<std::string, uint64_t>> cache; // page of rip -> (name, offset of that page in the file / mapping)
	std::lock_guard<std::mutex> lk(m);
	const uint64_t pg = rip & ~0xfffull;
	auto it = cache.find(pg);
	if (it == cache.end()) {
		std::pair<std::string, uint64_t> found {"?", 0};
		if (FILE* f = std::fopen("/proc/self/maps", "r"); f != nullptr) {
			char line[1024];
			while (std::fgets(line, sizeof(line), f) != nullptr) {
				uint64_t lo = 0, hi = 0, off = 0;
				char     perms[8] = {}, path[768] = {};
				if (std::sscanf(line, "%" SCNx64 "-%" SCNx64 " %7s %" SCNx64 " %*s %*s %767s", &lo, &hi, perms, &off, path) >= 4 && rip >= lo && rip < hi) {
					if (path[0]) {
						found = {path, off + (pg - lo)};
					} else {
						char an[40];
						std::snprintf(an, sizeof(an), "anon@0x%" PRIx64, lo);
						found = {an, pg - lo};
					}
					break;
				}
			}
			std::fclose(f);
		}
		it = cache.emplace(pg, found).first;
	}
	char buf[900];
	std::snprintf(buf, sizeof(buf), "%s+0x%" PRIx64, it->second.first.c_str(), it->second.second + (rip - pg));
	return buf;
}
// Journals the ring's new events (the filter thread).
static void drain() {
	static std::atomic<uint64_t> n_lines {0};
	static double                last_sum = 0;
	static uint64_t              last_caught = 0;
	static bool                  maps_once = false;
	const double                 tnow = now_s();
	if (!maps_once) { // once: the executable anonymous mappings (the title's code), for the anon@ names
		maps_once = true;
		if (FILE* f = std::fopen("/proc/self/maps", "r"); f != nullptr) {
			char line[1024];
			int  k = 0;
			while (std::fgets(line, sizeof(line), f) != nullptr && k < 24) {
				uint64_t lo = 0, hi = 0, off = 0;
				char     perms[8] = {}, path[768] = {};
				const int got = std::sscanf(line, "%" SCNx64 "-%" SCNx64 " %7s %" SCNx64 " %*s %*s %767s", &lo, &hi, perms, &off, path);
				if (got >= 4 && perms[2] == 'x' && path[0] == 0) {
					journal("write trap (exp 0316): executable anonymous mapping %d: 0x%" PRIx64 "-0x%" PRIx64 " (%" PRIu64 " KiB)\\n", k++, lo, hi, (hi - lo) >> 10u);
				}
			}
			std::fclose(f);
		}
	}
	if (tnow - last_sum >= 1.0) { // the per-second summary
		const uint64_t c = g_caught.load();
		if (c != last_caught || last_sum == 0) {
			uint32_t armed = 0;
			const uint32_t np = g_npages.load(std::memory_order_acquire);
			for (uint32_t i = 0; i < np && i < 64; i++) armed += g_pages[i].armed ? 1u : 0u;
			journal("write trap (exp 0316): summary: mode %u, %" PRIu64 " stores caught (+%" PRIu64 " in the last %.1f s), %" PRIu64 " into slots whose chain was NOT done, %" PRIu64 " held %.1f ms in all (%" PRIu64 " give-ups, %" PRIu64 " host-thread skips), %" PRIu64 " dropped, %" PRIu64 " foreign faults, %u of %u pages armed, done #%" PRIu64 "/#%" PRIu64 ", cap %" PRIu64 "\\n",
			        g_mode.load(), c, c - last_caught, last_sum == 0 ? 0.0 : tnow - last_sum, g_notdone.load(), g_held.load(), static_cast<double>(g_held_ns.load()) / 1e6, g_gaveup.load(), g_hostskip.load(),
			        g_dropped.load(), g_foreign.load(), armed, np, g_done_n[0].load(), g_done_n[1].load(), kCap);
		}
		last_sum = tnow;
		last_caught = c;
	}
	while (true) {
		const uint32_t r = g_rd.load(std::memory_order_acquire);
		if (r == g_wr.load(std::memory_order_acquire)) break;
		const Ev e = g_ring[r & 1023u];
		g_rd.store(r + 1, std::memory_order_release);
		const uint64_t nl  = n_lines++;
		const bool     rec = e.addr >= e.st + 0x100u && e.addr < e.st + 0x140u;
		static uint64_t n_nd = 0;
		const bool      nd   = e.done_n < e.n && (n_nd++ < 2048 || (n_nd & 63u) == 0); // the stall journal bounded
		if (nl < 512 || (rec && nl < 65536) || nd || (nl & 0xfffu) == 0) {
			std::string callers; // the words at RSP that look like code addresses, mapped (anon@ = the title's code)
			for (int k = 0; k < 4; k++) {
				if (e.ret[k] < 0x10000ull) continue;
				const std::string w = where(e.ret[k]);
				if (w.rfind("?+", 0) == 0) continue;
				callers += (callers.empty() ? " <- " : " | ") + w;
			}
			char job[160];
			if (e.done_n < e.n) {
				std::snprintf(job, sizeof(job), "chain #%" PRIu64 " (cq %d) NOT done at the store (frontier #%" PRIu64 ")%s%s", e.n, e.cq, e.done_n, e.host ? ", a host thread" : "", e.gaveup ? ", GAVE UP" : "");
			} else {
				std::snprintf(job, sizeof(job), "chain #%" PRIu64 " (cq %d) done (frontier #%" PRIu64 ")", e.n, e.cq, e.done_n);
			}
			journal("write trap (exp 0316): thread %" PRIu64 " stored to 0x%" PRIx64 " (%s) from %s (rip 0x%" PRIx64 ")%s [rsp %" PRIx64 " %" PRIx64 " %" PRIx64 " %" PRIx64 "], struct 0x%" PRIx64 ", %s, held %.2f ms, t %.3f (%" PRIu64 " caught, %" PRIu64 " not done, %" PRIu64 " dropped, %" PRIu64 " foreign faults)\\n", e.tid, e.addr,
			        rec ? (e.addr >= e.st + 0x120u && e.addr < e.st + 0x130u ? "THE RECORD 1 of the argument block" : "the argument block") : "other data on the page", where(e.rip).c_str(), e.rip, callers.c_str(), e.ret[0], e.ret[1], e.ret[2], e.ret[3], e.st, job, static_cast<double>(e.hold_ns) / 1e6, e.t,
			        g_caught.load(), g_notdone.load(), g_dropped.load(), g_foreign.load());
		}
	}
}
} // namespace x0316
static void timeout_probe(const uint32_t* sub_ib, uint32_t sub_n, const char* kind, uint64_t n, const std::vector<uint32_t>* ran, const std::vector<GeProbeSlot>* gep = nullptr) {
'''),
        ('''				if (g_dev) bc5_ranges_complete(j.ib, j.n, g_dev->sorted_mappings()); // experiment 0157
''', 1, '''				if (g_dev) bc5_ranges_complete(j.ib, j.n, g_dev->sorted_mappings()); // experiment 0157
				x0316::note_done(index, j.n); // experiment 0316: this queue's highest completed submission
'''),
        ('''			if (type == 3 && (op == 0x2c || op == 0x38) && len >= 10 && ib[q + 5] > 65536u) { // experiment 0054
''', 1, '''			// Experiment 0316: the write trap on the chain's argument-block pages (exp 0313), armed at each count-pass
			// dispatch with the submission being filtered and its queue; the ring of caught stores journaled here.
			{
				static const uint32_t trap_mode = [] { const char* e = BC5_DIAG_ENV("BC5_DIRECT_WRITE_TRAP"); return e != nullptr && *e != 0 ? static_cast<uint32_t>(std::strtoul(e, nullptr, 10)) : 0u; }();
				static const uint64_t count_pgm = [] { const char* e = std::getenv("BC5_DIRECT_COUNT_PGM"); return e != nullptr && *e != 0 ? std::strtoull(e, nullptr, 16) : 0x909939400ull; }();
				if (trap_mode != 0 && type == 3 && (op == 0x15 || op == 0x16)) {
					if (pgm == count_pgm) {
						const uint64_t st = ud[0] | (static_cast<uint64_t>(ud[1] & 0xffffu) << 32u);
						const char*    r  = st != 0 ? x0316::arm(st, *maps_p, g_submits.load(), t_cq, trap_mode) : "not armed: no struct";
						static std::atomic<uint64_t> n_arm {0};
						const uint64_t na = n_arm++;
						static std::atomic<uint64_t> n_ref {0}; // a refusal is journaled once per 4096
						if (na < 64 || (na & 0xfffu) == 0 || (r[0] != 'A' && (n_ref++ & 0xfffu) == 0)) journal("write trap (exp 0316): count pass at %u before #%" PRIu64 " (cq %d): struct 0x%" PRIx64 ", page 0x%" PRIx64 " %s (%" PRIu64 " armings, %" PRIu64 " refusals)\\n", q, g_submits.load(), t_cq, st, (st + 0x100u) & ~0xfffull, r, na + 1, n_ref.load());
					}
					x0316::drain();
				}
			}
			if (type == 3 && (op == 0x2c || op == 0x38) && len >= 10 && ib[q + 5] > 65536u) { // experiment 0054
'''),
    ],
}


def main():
    if len(sys.argv) != 3:
        print('usage: patch0316.py <src root> <out dir>')
        sys.exit(2)
    root, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    diff = []
    for rel, edits in EDITS.items():
        path = os.path.join(root, rel)
        src = open(path, encoding='utf-8').read()
        print(f'{rel}: md5 {hashlib.md5(src.encode("utf-8")).hexdigest()[:8]} in')
        dst = src
        for k, (old, n, new) in enumerate(edits, 1):
            c = dst.count(old)
            if c != n:
                print(f'{rel}: edit {k}: anchor found {c} times, expected {n}:\n{old}')
                sys.exit(1)
            dst = dst.replace(old, new)
        target = os.path.join(out, os.path.basename(rel))
        open(target, 'w', encoding='utf-8', newline='\n').write(dst)
        diff += difflib.unified_diff(src.splitlines(True), dst.splitlines(True), 'a/' + rel, 'b/' + rel)
        print(f'{rel}: {len(edits)} edits -> {target}, md5 {hashlib.md5(dst.encode("utf-8")).hexdigest()[:8]} out')
    open(os.path.join(out, 'patch_0316.diff'), 'w', encoding='utf-8', newline='\n').write(''.join(diff))
    print(f'patch_0316.diff: {sum(1 for l in diff if l.startswith("+") and not l.startswith("+++"))} added lines')


if __name__ == '__main__':
    main()
