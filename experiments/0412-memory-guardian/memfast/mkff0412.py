#!/usr/bin/env python3
"""BC5 experiment 0412, tag ff412 (README sections 57, 59): two catchers for runs with a smaller memory offer, on the
SHARED tree (patch 4651d1d3: memory.cpp eff24b4c, libAmpr.cpp a2d09d32, hostException.cpp as in that tree).
  KYTY_BC5_MEM_FIRSTFAIL=1  every wrapped memory call of the host that returns an error is counted and the first ones
                            written in full with the state of the direct memory (firstfail0412.inc); the AMM auto
                            pool's refused borrow and a failed AMM command are noted the same way; the exit on an
                            access to a reserved AMM page prints the failures that came before it.
  KYTY_BC5_TRAP_LOG=1       a SIGTRAP is journaled (rip, rsp, thread) and then takes its default action as before.
Both default off; neither changes a result. No fix is in this kit: the fix candidate for the refused borrow is the
shared tree's own KYTY_BC5_AMM_SCATTER=rescue|first (exp 0409).
  BC5_DIRECT_MAX_BO_MIB=<n> the largest import (bc5LleAgc.cpp), for the compaction test of README section 58.
usage: mkff0412.py <shared src dir in> <dir out>     (writes out/src/kernel/memory.cpp, out/src/libs/libAmpr.cpp,
                                                      out/src/common/hostException.cpp; prints their md5)"""
import hashlib
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
T = b" // exp 0412 (tag ff412)\n"

WRAPPED = [b"KernelMapFlexibleMemory", b"KernelMunmap", b"KernelAvailableDirectMemorySize", b"KernelAllocateDirectMemory",
           b"KernelAllocateMainDirectMemory", b"KernelReleaseDirectMemory", b"KernelCheckedReleaseDirectMemory",
           b"KernelMapDirectMemory", b"KernelMapDirectMemory2", b"KernelMapNamedDirectMemory", b"KernelReserveVirtualRange",
           b"KernelMprotect", b"KernelMtypeprotect", b"KernelBatchMap2", b"KernelMemoryPoolExpand", b"KernelMemoryPoolReserve",
           b"KernelMemoryPoolCommit", b"KernelMemoryPoolDecommit"]

STATS = b'''	// exp 0412 (tag ff412): the free list in numbers, for the catcher's state line (the caller holds the memory lock).
	void Bc5FreeStats(uint64_t* total, uint64_t* largest, uint64_t* runs) const {
		*total = 0;
		*largest = 0;
		*runs = m_free.size();
		for (const auto& r: m_free) {
			*total += r.second;
			if (r.second > *largest) *largest = r.second;
		}
	}
'''

GLUE = b'''// Experiment 0412 (tag ff412): KYTY_BC5_MEM_FIRSTFAIL, the host's part. One mutex around the counters and the ring;
// the state line takes the memory lock (recursive: a failing call may still hold it).
static ff412::Ring g_ff412_ring;
static std::mutex  g_ff412_mutex;
static void ff412_thread(char* out, size_t cap) {
	std::snprintf(out, cap, "tid %d", static_cast<int>(gettid()));
	char path[64];
	std::snprintf(path, sizeof(path), "/proc/self/task/%d/comm", static_cast<int>(gettid()));
	if (FILE* f = std::fopen(path, "r")) {
		char name[32] = "";
		if (std::fgets(name, sizeof(name), f) != nullptr) {
			name[std::strcspn(name, "\\n")] = 0;
			std::snprintf(out, cap, "tid %d (%s)", static_cast<int>(gettid()), name);
		}
		std::fclose(f);
	}
}
static void ff412_state_line() {
	std::scoped_lock memory_lock(g_memory_operation_mutex);
	uint64_t total = 0, largest = 0, runs = 0;
	if (g_physical_memory) g_physical_memory->Bc5FreeStats(&total, &largest, &runs);
	std::fprintf(stderr, "[bc5] mem firstfail (exp 0412, tag ff412):   direct memory: offered %" PRIu64 " MiB, free %" PRIu64 " MiB in %" PRIu64 " runs, the largest %" PRIu64 " MiB; flexible: configured %" PRIu64 " MiB, available %" PRIu64 " MiB\\n",
	             static_cast<uint64_t>(PhysicalMemory::Size() >> 20u), total >> 20u, runs, largest >> 20u, static_cast<uint64_t>(FlexibleMemory::Size() >> 20u),
	             g_flexible_memory ? static_cast<uint64_t>(g_flexible_memory->Available() >> 20u) : 0);
}
static void ff412_report(const char* call, int result, const void* caller, std::initializer_list<uint64_t> args) {
	if (!ff412::on()) return;
	ff412::Fail f;
	f.call   = call;
	f.result = result;
	for (const uint64_t a: args) {
		if (f.args < 6) f.a[f.args++] = a;
	}
	bool print = false;
	{
		std::scoped_lock lk(g_ff412_mutex);
		f.n = g_ff412_ring.count + 1;
		g_ff412_ring.push(f);
		print = ff412::full(f.n);
	}
	if (!print) return;
	char who[64];
	ff412_thread(who, sizeof(who));
	std::fprintf(stderr, "[bc5] mem firstfail (exp 0412, tag ff412): failure %" PRIu64 ": %s -> 0x%08x; args", f.n, call, static_cast<unsigned>(result));
	for (unsigned i = 0; i < f.args; i++) std::fprintf(stderr, " 0x%" PRIx64, f.a[i]);
	std::fprintf(stderr, "; caller %p; %s\\n", caller, who);
	ff412_state_line();
	std::fflush(stderr);
}
extern "C" void bc5_mem_firstfail_note(const char* call, int result, uint64_t a0, uint64_t a1, uint64_t a2, uint64_t a3) {
	ff412_report(call, result, __builtin_return_address(0), {a0, a1, a2, a3});
}
// The host is about to exit on an access to a reserved AMM page: what failed before it.
static void ff412_death(uint64_t vaddr) {
	if (!ff412::on()) return;
	const ff412::Fail* kept[ff412::kRing];
	unsigned           n = 0;
	uint64_t           all = 0;
	{
		std::scoped_lock lk(g_ff412_mutex);
		n   = g_ff412_ring.list(kept);
		all = g_ff412_ring.count;
		char who[64];
		ff412_thread(who, sizeof(who));
		std::fprintf(stderr, "[bc5] mem firstfail (exp 0412, tag ff412): access to the reserved AMM page 0x%016" PRIx64 " on %s; %" PRIu64 " memory calls failed before it, the last %u:\\n", vaddr, who, all, n);
		for (unsigned i = 0; i < n; i++) {
			std::fprintf(stderr, "[bc5] mem firstfail (exp 0412, tag ff412):   failure %" PRIu64 ": %s -> 0x%08x; args", kept[i]->n, kept[i]->call, static_cast<unsigned>(kept[i]->result));
			for (unsigned k = 0; k < kept[i]->args; k++) std::fprintf(stderr, " 0x%" PRIx64, kept[i]->a[k]);
			std::fprintf(stderr, "\\n");
		}
	}
	ff412_state_line();
	std::fflush(stderr);
}
'''

AMM_DECL = b'extern "C" void bc5_mem_firstfail_note(const char* call, int result, uint64_t a0, uint64_t a1, uint64_t a2, uint64_t a3); // memory.cpp, exp 0412 (tag ff412)\n'

AMM_BORROW = b'''		{ // exp 0412 (tag ff412): KYTY_BC5_MEM_FIRSTFAIL
			uint64_t ff_free = 0, ff_largest = 0;
			for (const auto& r: g_amm_auto_free) {
				ff_free += r.second;
				if (r.second > ff_largest) ff_largest = r.second;
			}
			bc5_mem_firstfail_note("AMM auto pool: borrow of direct memory refused (args: size, maps holding the pool, pool free bytes, its largest free run)",
			                       LibKernel::KERNEL_ERROR_EAGAIN, size, static_cast<uint64_t>(g_amm_auto_maps.size()), ff_free, ff_largest);
		}
'''

TRAP = b'''#if KYTY_PLATFORM != KYTY_PLATFORM_WINDOWS && !defined(__APPLE__)
// Experiment 0412 (tag ff412): KYTY_BC5_TRAP_LOG=1. A SIGTRAP (an int3 of the title, or a trap of the host) is
// journaled with its address and thread; then the default action happens as it did before (the process ends with
// status 133). stdio in a handler is not async-signal-safe: accepted for a process that is about to die.
static void Bc5TrapLog(int sig, siginfo_t* si, void* uctx) {
	const auto* uc  = static_cast<const ucontext_t*>(uctx);
	const auto  rip = static_cast<unsigned long long>(uc->uc_mcontext.gregs[REG_RIP]);
	const auto  rsp = static_cast<unsigned long long>(uc->uc_mcontext.gregs[REG_RSP]);
	char        name[32] = "?";
	char        path[64];
	std::snprintf(path, sizeof(path), "/proc/self/task/%d/comm", static_cast<int>(gettid()));
	if (FILE* f = std::fopen(path, "r")) {
		if (std::fgets(name, sizeof(name), f) != nullptr) {
			for (char* c = name; *c != 0; c++) {
				if (*c == '\\n') *c = 0;
			}
		}
		std::fclose(f);
	}
	std::fprintf(stderr, "[bc5] trap log (exp 0412, tag ff412): signal %d code %d at rip 0x%llx (the byte before it is the int3 if this is one), rsp 0x%llx, fault address %p, tid %d (%s); the default action follows\\n",
	             sig, si != nullptr ? si->si_code : 0, rip, rsp, si != nullptr ? si->si_addr : nullptr, static_cast<int>(gettid()), name);
	std::fflush(stderr);
	struct sigaction dfl {};
	dfl.sa_handler = SIG_DFL;
	sigemptyset(&dfl.sa_mask);
	::sigaction(sig, &dfl, nullptr);
	::raise(sig);
}
static void Bc5TrapLogInstall() {
	const char* e = std::getenv("KYTY_BC5_TRAP_LOG");
	if (e == nullptr || e[0] == 0 || (e[0] == '0' && e[1] == 0)) return;
	struct sigaction sa {};
	sa.sa_sigaction = Bc5TrapLog;
	sigemptyset(&sa.sa_mask);
	sa.sa_flags = SA_SIGINFO;
	const int rc = ::sigaction(SIGTRAP, &sa, nullptr);
	std::fprintf(stderr, "[bc5] trap log (exp 0412, tag ff412): KYTY_BC5_TRAP_LOG on, sigaction(SIGTRAP) rc %d\\n", rc);
}
#endif

'''


def md5(b):
    return hashlib.md5(b).hexdigest()


def once(s, old, new):
    assert s.count(old) == 1, ("an anchor does not occur exactly once", old[:70], s.count(old))
    return s.replace(old, new)


def wrap(s, name):
    """int KYTY_SYSV_ABI Name(params) { ... }  ->  a forward declaration of the body under another name, a wrapper with
    the old name that reports a non-OK result, and the body renamed."""
    m = list(re.finditer(rb"\nint KYTY_SYSV_ABI " + name + rb"\(([^{};]*?)\) \{\n", s))
    assert len(m) == 1, ("definition not found exactly once", name, len(m))
    params = m[0].group(1)
    names = []
    for p in params.split(b","):
        mm = re.search(rb"(\w+)\s*$", p.strip())
        assert mm, (name, p)
        names.append(mm.group(1))
    assert b"(" not in params and b"=" not in params, ("a parameter list this script does not understand", name)
    body = b"Bc5Ff_" + name
    args = b", ".join(names)
    us = b", ".join(b"ff412::u(" + n + b")" for n in names[:6])
    new = (b"\nstatic int " + body + b"(" + params + b");" + T +
           b"int KYTY_SYSV_ABI " + name + b"(" + params + b") {" + T +
           b"\tconst int bc5_ff_result = " + body + b"(" + args + b");\n"
           b"\tif (bc5_ff_result != OK) [[unlikely]] ff412_report(\"" + name + b"\", bc5_ff_result, __builtin_return_address(0), {" + us + b"});\n"
           b"\treturn bc5_ff_result;\n"
           b"}\n"
           b"static int " + body + b"(" + params + b") {\n")
    return s[:m[0].start()] + new + s[m[0].end():]


def main():
    assert len(sys.argv) == 3 and sys.argv[1] != sys.argv[2], __doc__
    src, out = sys.argv[1], sys.argv[2]
    inc = open(os.path.join(HERE, "firstfail0412.inc"), "rb").read()
    for b in (inc, GLUE, STATS, AMM_BORROW, TRAP):
        assert b"\r" not in b
        b.decode("ascii")
    # --- memory.cpp
    p = "src/kernel/memory.cpp"
    s = open(os.path.join(src, p), "rb").read()
    assert b"\r" not in s and b"tag ff412" not in s, "refused: CRLF or already edited"
    s = once(s, b"\tvirtual ~PhysicalMemory() = default;\n", b"\tvirtual ~PhysicalMemory() = default;\n" + STATS)
    a = b"static std::recursive_mutex g_memory_operation_mutex;\n"
    s = once(s, a, a + inc + GLUE)
    for name in WRAPPED:
        s = wrap(s, name)
    a = b'\tEXIT("AMM virtual-memory unmap is unsupported: addr=0x%016" PRIx64 "\\n", vaddr);\n'
    s = once(s, a, b"\tff412_death(vaddr);" + T + a)
    g = s.index(b"static void ff412_report(")
    for need in (b"static std::unique_ptr<PhysicalMemory>    g_physical_memory;", b"static std::unique_ptr<FlexibleMemory>    g_flexible_memory;",
                 b"class FlexibleMemory {", b"static std::recursive_mutex g_memory_operation_mutex;"):
        assert s.index(need) < g, ("must be defined before the glue", need[:40])
    first = min(s.index(b"static int Bc5Ff_" + n + b"(") for n in WRAPPED)
    assert g < first, "the glue must come before the first wrapper"
    assert s.count(b"static int Bc5Ff_") == 2 * len(WRAPPED) and s.count(b"ff412_report(\"Kernel") == len(WRAPPED)
    os.makedirs(os.path.join(out, "src/kernel"), exist_ok=True)
    open(os.path.join(out, p), "wb").write(s)
    print(f"{p} {md5(s)}")
    # --- libAmpr.cpp
    p = "src/libs/libAmpr.cpp"
    s = open(os.path.join(src, p), "rb").read()
    assert b"\r" not in s and b"tag ff412" not in s
    a = b"static bool AllocateAmmAutoDirectMemory(uint64_t size, int memory_type, uint64_t* dmem_offset) {\n"
    s = once(s, a, AMM_DECL + a)
    a = b"\t\tif (AmmTrace()) {\n\t\t\tuint64_t free_bytes = 0;\n"
    s = once(s, a, AMM_BORROW + a)
    a = b'\t\t\t\t\tLOGF("\\tAMM submit command failed: kind=%u va=0x%016" PRIx64\n'
    s = once(s, a, b'\t\t\t\t\tbc5_mem_firstfail_note("AMM command failed and its buffer stops (args: kind, va, size, 0)", result, static_cast<uint64_t>(command.kind), command.va, command.size, 0);' + T + a)
    assert s.index(AMM_DECL) < s.index(b"bc5_mem_firstfail_note(\"AMM auto pool") < s.index(b"bc5_mem_firstfail_note(\"AMM command failed")
    os.makedirs(os.path.join(out, "src/libs"), exist_ok=True)
    open(os.path.join(out, p), "wb").write(s)
    print(f"{p} {md5(s)}")
    # --- hostException.cpp
    p = "src/common/hostException.cpp"
    s = open(os.path.join(src, p), "rb").read()
    assert b"\r" not in s and b"tag ff412" not in s
    a = b"bool InstallHandler(Handler handler) {\n"
    s = once(s, a, TRAP + a)
    a = b"\tfor (const int signal_number: {SIGSEGV, SIGBUS, SIGILL}) {\n"
    s = once(s, a, b"\tBc5TrapLogInstall();" + T + a)
    os.makedirs(os.path.join(out, "src/common"), exist_ok=True)
    open(os.path.join(out, p), "wb").write(s)
    print(f"{p} {md5(s)}")
    # --- bc5LleAgc.cpp: BC5_DIRECT_MAX_BO_MIB=<2..1024> (README section 58, source iii): the largest import, below the
    # udmabuf module's own limit. Unset: as today. With 16 the kernel's per-buffer arrays are 32 KiB (order 3) instead
    # of 128 KiB (order 5): the test of how much of the compaction our own high-order requests cause.
    p = "src/libs/bc5LleAgc.cpp"
    s = open(os.path.join(src, p), "rb").read()
    assert b"\r" not in s and b"tag ff412" not in s
    a = b"\tif (mb < 2) mb = 2;\n\tif (mb > 1024) mb = 1024;\n\treturn (static_cast<uint64_t>(mb) << 20u) & ~((2ull << 20u) - 1);\n"
    new = (b"\tif (const char* e = std::getenv(\"BC5_DIRECT_MAX_BO_MIB\"); e != nullptr && e[0] != 0) { // exp 0412 (tag ff412): never above the module's limit\n"
           b"\t\tconst unsigned long want = std::strtoul(e, nullptr, 10);\n"
           b"\t\tif (want >= 2 && want < mb) mb = want;\n"
           b"\t\tstd::fprintf(stderr, \"[bc5] exp 0412 (tag ff412): BC5_DIRECT_MAX_BO_MIB=%s: the largest import is %lu MiB\\n\", e, mb);\n"
           b"\t}\n")
    s = once(s, a, new + a)
    open(os.path.join(out, p), "wb").write(s)
    print(f"{p} {md5(s)}")


if __name__ == "__main__":
    main()
