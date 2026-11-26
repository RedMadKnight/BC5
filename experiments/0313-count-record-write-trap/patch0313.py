#!/usr/bin/env python3
# BC5 experiment 0313: who writes the count record from the CPU — a host-side write trap on the page of the build chain's
# argument block (exp 0310: record 1 of {struct + 0x100, stride 0x20, 2 records} holds per-tree float triples at the GPU's
# read, changing frame to frame, still while the GPU is wedged; no GPU program of the chain stores there). In
# src/libs/bc5LleAgc.cpp of the shared tree as integrated on the box (md5 5bccbb80). Diagnostic, BC5_DIRECT_WRITE_TRAP=1.
#   - At filter time, each count-pass dispatch (0x909939400, BC5_DIRECT_COUNT_PGM overrides) names its struct (ud0:1); the
#     page of struct + 0x100 is ARMED: mprotect(PROT_READ) from the host — only when the device maps that page as a shared
#     memfd mapping (bc5::direct::Mapping::shared; a userptr page made read-only would break the GPU's own write path),
#     else "not armed (userptr)". At most 64 distinct pages; each arming has a budget of 32 caught stores.
#   - A SIGSEGV on an armed page: the handler records {thread, RIP, target address, time, page} into a lock-free ring
#     (nothing async-unsafe in the handler), makes the page writable, sets the x86 trap flag and returns; the SIGTRAP
#     handler re-protects the page and clears the flag — a software watchpoint, every store caught, the game thread
#     delayed by two signals per store. A fault outside the armed pages goes to the host's previous SIGSEGV action.
#   - The filter drains the ring at every dispatch it looks at and journals each store ("write trap (exp 0313)": thread,
#     RIP with the module and offset from /proc/self/maps, the target, whether it is THE RECORD (struct + 0x120 .. +0x12c) or
#     other data on the page, the arming's struct) — bounded; and a summary per 4096 stores.
# usage: patch0313.py <src root of the shared tree> <out dir>
import difflib, hashlib, os, sys

EDITS = {
    'src/libs/bc5LleAgc.cpp': [
        ('''#include <sys/mman.h>
''', 1, '''#include <sys/mman.h>
#include <csignal>       // experiment 0313
#include <sys/syscall.h> // experiment 0313: SYS_gettid in the handler
#include <ucontext.h>    // experiment 0313
'''),
        ('''static void timeout_probe(const uint32_t* sub_ib, uint32_t sub_n, const char* kind, uint64_t n, const std::vector<uint32_t>* ran, const std::vector<GeProbeSlot>* gep = nullptr) {
''', 1, '''// Experiment 0313: a software watchpoint on the pages of the build chain's argument blocks. The SIGSEGV handler only
// touches the ring, mprotect and the signal context (async-signal-safe); the filter thread journals the ring.
namespace x0313 {
struct Ev {
	uint64_t tid = 0, rip = 0, addr = 0, page = 0, st = 0;
	uint64_t ret[4] = {}; // 0313b: the four words at the faulting thread's RSP — candidate return addresses (the caller of a libc store loop)
	double   t = 0;
};
struct Page {
	uint64_t page = 0, st = 0;
	uint32_t budget = 0;
	bool     armed = false;
};
static std::atomic<bool>      g_on {false};
static std::atomic<uint32_t>  g_wr {0}, g_rd {0}; // the ring's write and read indices
static Ev                     g_ring[1024];        // 0313b: 1024 deep (run 1 dropped 998 of 2912 with 256)
static Page                   g_pages[64];
static std::atomic<uint32_t>  g_npages {0};
static std::atomic<uint32_t>  g_next_page {0};     // 0313b: the page table is an LRU ring — the oldest arming is replaced, never a refusal
static std::atomic<uint64_t>  g_caught {0}, g_dropped {0}, g_foreign {0};
static std::atomic<bool>      g_trap_taken {false}; // a SIGTRAP handler was already installed: never arm (the trap flag would collide)
static constexpr uint64_t     kCap = 4096;          // the hard cap on caught stores a process: beyond it nothing is armed again
static struct sigaction       g_old_segv, g_old_trap;
static thread_local uint64_t  t_rearm = 0; // the page the SIGTRAP handler re-protects
static double now_s() {
	timespec ts {};
	clock_gettime(CLOCK_MONOTONIC, &ts);
	return static_cast<double>(ts.tv_sec) + static_cast<double>(ts.tv_nsec) * 1e-9;
}
static int page_index(uint64_t page) {
	const uint32_t n = g_npages.load(std::memory_order_acquire);
	for (uint32_t i = 0; i < n && i < 64; i++) {
		if (g_pages[i].page == page) return static_cast<int>(i);
	}
	return -1;
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
	const uint32_t w = g_wr.fetch_add(1, std::memory_order_acq_rel);
	if (w - g_rd.load(std::memory_order_acquire) < 1024) {
		Ev& e  = g_ring[w & 1023u];
		e.tid  = static_cast<uint64_t>(syscall(SYS_gettid));
		e.rip  = static_cast<uint64_t>(uc->uc_mcontext.gregs[REG_RIP]);
		e.addr = a;
		e.page = page;
		e.st   = g_pages[pi].st;
		e.t    = now_s();
		const auto* sp = reinterpret_cast<const uint64_t*>(uc->uc_mcontext.gregs[REG_RSP]); // the thread's own stack: mapped
		for (int k = 0; k < 4; k++) e.ret[k] = sp[k];
	} else {
		g_dropped.fetch_add(1, std::memory_order_relaxed);
	}
	const uint64_t caught = g_caught.fetch_add(1, std::memory_order_relaxed) + 1;
	mprotect(reinterpret_cast<void*>(page), 4096, PROT_READ | PROT_WRITE);
	if (g_pages[pi].budget > 0 && caught < kCap) {
		g_pages[pi].budget--;
		t_rearm = page;
		uc->uc_mcontext.gregs[REG_EFL] |= 0x100; // trap flag: one instruction, then SIGTRAP re-protects
	} else {
		g_pages[pi].armed = false; // the budget is spent: the page stays writable until the next arming
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
static void install_once() {
	static std::once_flag once;
	std::call_once(once, [] {
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
static const char* arm(uint64_t st, const std::vector<bc5::direct::Mapping>& maps) {
	const uint64_t page = (st + 0x100u) & ~0xfffull;
	auto it = std::upper_bound(maps.begin(), maps.end(), page, [](uint64_t v, const bc5::direct::Mapping& m) { return v < m.va; });
	if (it == maps.begin()) return "not armed: page not mapped";
	--it;
	if (!(page >= it->va && page + 4096 <= it->va + it->size)) return "not armed: page not mapped";
	if (!it->shared) return "not armed: a userptr page (a read-only VMA would break the GPU's write path)";
	install_once();
	if (g_trap_taken.load(std::memory_order_acquire)) return "not armed: a SIGTRAP handler is already installed (the trap flag would collide)";
	if (g_caught.load(std::memory_order_relaxed) >= kCap) return "not armed: the hard cap of caught stores is spent";
	int pi = page_index(page);
	if (pi < 0) {
		const uint32_t n = g_npages.load(std::memory_order_acquire);
		if (n < 64) {
			g_pages[n].page = page;
			g_pages[n].st   = st;
			g_npages.store(n + 1, std::memory_order_release);
			pi = static_cast<int>(n);
		} else { // 0313b: replace the oldest arming (an LRU ring); its page is left writable
			const uint32_t slot = g_next_page.fetch_add(1, std::memory_order_acq_rel) & 63u;
			if (g_pages[slot].armed) mprotect(reinterpret_cast<void*>(g_pages[slot].page), 4096, PROT_READ | PROT_WRITE);
			g_pages[slot].armed = false;
			g_pages[slot].page  = page;
			g_pages[slot].st    = st;
			pi = static_cast<int>(slot);
		}
	}
	g_pages[pi].st     = st;
	g_pages[pi].budget = 32;
	g_pages[pi].armed  = true;
	return mprotect(reinterpret_cast<void*>(page), 4096, PROT_READ) == 0 ? "ARMED" : "not armed: mprotect failed";
}
// The module and offset of an address, from /proc/self/maps (read once per distinct page of RIP; the filter thread only).
static std::string where(uint64_t rip) {
	static std::mutex                              m;
	static std::map<uint64_t, std::pair<std::string, uint64_t>> cache; // page of rip -> (path, offset of that page in the file)
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
					found = {path[0] ? path : "[anon]", off + (pg - lo)};
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
	const double                 tnow = now_s();
	if (tnow - last_sum >= 1.0) { // the per-second summary (the supervisor's note: the game thread pays a fault and a step per store)
		const uint64_t c = g_caught.load();
		if (c != last_caught || last_sum == 0) {
			uint32_t armed = 0;
			const uint32_t np = g_npages.load(std::memory_order_acquire);
			for (uint32_t i = 0; i < np && i < 64; i++) armed += g_pages[i].armed ? 1u : 0u;
			journal("write trap (exp 0313): summary: %" PRIu64 " stores caught (+%" PRIu64 " in the last %.1f s), %" PRIu64 " dropped, %" PRIu64 " foreign faults, %u of %u pages armed, cap %" PRIu64 "\\n", c, c - last_caught, last_sum == 0 ? 0.0 : tnow - last_sum,
			        g_dropped.load(), g_foreign.load(), armed, np, kCap);
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
		if (nl < 512 || rec || (nl & 0xfffu) == 0) {
			std::string callers; // 0313b: the words at RSP that look like code addresses, mapped
			for (int k = 0; k < 4; k++) {
				if (e.ret[k] < 0x10000ull) continue;
				const std::string w = where(e.ret[k]);
				if (w.rfind("?+", 0) == 0 || w.rfind("[anon]", 0) == 0) continue;
				callers += (callers.empty() ? " <- " : " | ") + w;
			}
			journal("write trap (exp 0313): thread %" PRIu64 " stored to 0x%" PRIx64 " (%s) from %s (rip 0x%" PRIx64 ")%s, struct 0x%" PRIx64 ", t %.3f (%" PRIu64 " caught, %" PRIu64 " dropped, %" PRIu64 " foreign faults)\\n", e.tid, e.addr,
			        rec ? (e.addr >= e.st + 0x120u && e.addr < e.st + 0x130u ? "THE RECORD 1 of the argument block" : "the argument block") : "other data on the page", where(e.rip).c_str(), e.rip, callers.c_str(), e.st, e.t,
			        g_caught.load(), g_dropped.load(), g_foreign.load());
		}
	}
}
} // namespace x0313
static void timeout_probe(const uint32_t* sub_ib, uint32_t sub_n, const char* kind, uint64_t n, const std::vector<uint32_t>* ran, const std::vector<GeProbeSlot>* gep = nullptr) {
'''),
        ('''			if (type == 3 && (op == 0x2c || op == 0x38) && len >= 10 && ib[q + 5] > 65536u) { // experiment 0054
''', 1, '''			// Experiment 0313: the write trap on the chain's argument-block pages, armed at each count-pass dispatch; the ring
			// of caught stores journaled here (the filter thread), at every dispatch the filter looks at.
			{
				static const bool     trap_on   = BC5_DIAG_ENV("BC5_DIRECT_WRITE_TRAP") != nullptr;
				static const uint64_t count_pgm = [] { const char* e = std::getenv("BC5_DIRECT_COUNT_PGM"); return e != nullptr && *e != 0 ? std::strtoull(e, nullptr, 16) : 0x909939400ull; }();
				if (trap_on && type == 3 && (op == 0x15 || op == 0x16)) {
					if (pgm == count_pgm) {
						const uint64_t st = ud[0] | (static_cast<uint64_t>(ud[1] & 0xffffu) << 32u);
						const char*    r  = st != 0 ? x0313::arm(st, *maps_p) : "not armed: no struct";
						static std::atomic<uint64_t> n_arm {0};
						const uint64_t na = n_arm++;
						static std::atomic<uint64_t> n_ref {0}; // 0313b: a refusal is journaled once per 4096 (run 1 wrote 1.17 M refusal lines)
						if (na < 64 || (na & 0xfffu) == 0 || (r[0] != 'A' && (n_ref++ & 0xfffu) == 0)) journal("write trap (exp 0313): count pass at %u before #%" PRIu64 ": struct 0x%" PRIx64 ", page 0x%" PRIx64 " %s (%" PRIu64 " armings, %" PRIu64 " refusals)\\n", q, g_submits.load(), st, (st + 0x100u) & ~0xfffull, r, na + 1, n_ref.load());
					}
					x0313::drain();
				}
			}
			if (type == 3 && (op == 0x2c || op == 0x38) && len >= 10 && ib[q + 5] > 65536u) { // experiment 0054
'''),
    ],
}


def main():
    if len(sys.argv) != 3:
        print('usage: patch0313.py <src root> <out dir>')
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
    open(os.path.join(out, 'patch_0313.diff'), 'w', encoding='utf-8', newline='\n').write(''.join(diff))
    print(f'patch_0313.diff: {sum(1 for l in diff if l.startswith("+") and not l.startswith("+++"))} added lines')


if __name__ == '__main__':
    main()
