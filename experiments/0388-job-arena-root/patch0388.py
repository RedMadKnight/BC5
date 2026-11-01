#!/usr/bin/env python3
"""BC5 experiment 0388: the switches of the private test build, on a private copy of the host's units.
Each edit's anchor must occur exactly once, or nothing is written. Line endings stay as the file has them.
usage: python3 -I patch0388.py <tree with src/>"""
import sys

ROOT = sys.argv[1]
INCLUDE = '#include "bc5/cpu_model.hpp" // BC5 (experiment 0388)\n'

HELPERS_PTHREAD = '''
// BC5 (experiment 0388): each KYTY_BC5_0388_* switch is default off; off leaves the host as it was.
uint64_t Bc5ModelMask() {
	static const uint64_t mask = [] {
		bool       invalid = false;
		const auto value   = bc5::cpu_model::parse_mask(std::getenv("KYTY_BC5_0388_CPU_MASK"), &invalid);
		std::fprintf(stderr, "bc5 exp 0388: guest CPU mask %" PRIx64 "%s\\n", value, invalid ? " (the switch is invalid)" : "");
		return value;
	}();
	return mask;
}

static bool Bc5Trace0388() {
	static const bool on = bc5::cpu_model::parse_flag(std::getenv("KYTY_BC5_0388_TRACE"));
	return on;
}

static void Bc5TraceAffinity(const char* what, const char* name, uint64_t mask) {
	static std::atomic<int> left {400};
	if (Bc5Trace0388() && left.fetch_sub(1) > 0) {
		std::fprintf(stderr, "bc5 exp 0388: %s thread %s mask %" PRIx64 "\\n", what, name, mask);
	}
}

#if KYTY_PLATFORM == KYTY_PLATFORM_LINUX
static void Bc5ApplyAffinity(Pthread thread, const char* why) {
	static const bool on = bc5::cpu_model::parse_flag(std::getenv("KYTY_BC5_0388_APPLY_AFFINITY"));
	if (!on || thread == nullptr || thread->attr == nullptr || thread->host_thread_id == 0) {
		return;
	}
	const uint64_t mask = bc5::cpu_model::host_mask(thread->attr->affinity, Bc5ModelMask());
	cpu_set_t      set;
	CPU_ZERO(&set);
	for (int cpu = 0; cpu < 16; cpu++) {
		if (mask == 0 || ((mask >> cpu) & 1u) != 0) {
			CPU_SET(cpu, &set);
		}
	}
	const int rc = sched_setaffinity(static_cast<pid_t>(thread->host_thread_id), sizeof(set), &set);
	if (Bc5Trace0388()) {
		std::fprintf(stderr, "bc5 exp 0388: %s %s host mask %" PRIx64 " rc %d\\n", why, thread->name.c_str(), mask, rc);
	}
}
#endif

'''

EDITS = {
    "src/kernel/pthread.cpp": [
        ('#include "common/assert.h"\n', INCLUDE + '#include "common/assert.h"\n'),
        ("#include <atomic>\n", "#include <atomic>\n#include <cinttypes>\n#include <cstdio>\n#include <cstdlib>\n#include <sched.h>\n"),
        ("static void* RunThread(void* arg) {\n", HELPERS_PTHREAD + "static void* RunThread(void* arg) {\n"),
        ("\tif (guest_priority >= 733) {\n\t\treturn 5;\n\t}\n\treturn 0;\n}\n",
         "\tif (guest_priority >= 733) {\n\t\treturn 5;\n\t}\n"
         "\t// BC5 (experiment 0388): KYTY_BC5_0388_WORKER_NICE, the job workers at guest priority 500 (the Hi entry) only.\n"
         '\tstatic const int worker_nice = bc5::cpu_model::parse_worker_nice(std::getenv("KYTY_BC5_0388_WORKER_NICE"));\n'
         "\treturn guest_priority == 500 ? worker_nice : 0;\n}\n"),
        ('\tBc5ApplyGuestPriority(thread, "start");\n#endif\n',
         '\tBc5ApplyGuestPriority(thread, "start");\n\tBc5ApplyAffinity(thread, "start");\n#endif\n'),
        ("\t(*attr)->affinity       = 0x7f;\n", "\t(*attr)->affinity       = Bc5ModelMask();\n"),
        ("\tauto result = PthreadAttrSetaffinity(&thread->attr, mask);\n\n\treturn result;\n",
         '\tauto result = PthreadAttrSetaffinity(&thread->attr, mask);\n\n\tBc5TraceAffinity("set", thread->name.c_str(), mask);\n'
         '#if KYTY_PLATFORM == KYTY_PLATFORM_LINUX\n\tBc5ApplyAffinity(thread, "set");\n#endif\n\n\treturn result;\n'),
        ("int KYTY_SYSV_ABI PthreadAttrGetaffinity(const PthreadAttr* attr, KernelCpumask* mask) {\n",
         "static void Bc5TraceAffinity(const char* what, const char* name, uint64_t mask);\n\n"
         "int KYTY_SYSV_ABI PthreadAttrGetaffinity(const PthreadAttr* attr, KernelCpumask* mask) {\n"),
        ("\t*mask = (*attr)->affinity;\n",
         '\t*mask = (*attr)->affinity;\n\tBc5TraceAffinity("attr get", "(attr)", *mask); // libc.prx counts its CPUs from this read\n'),
        ("\treturn PthreadAttrGetaffinity(&thread->attr, mask);\n",
         '\tconst int result = PthreadAttrGetaffinity(&thread->attr, mask);\n\tBc5TraceAffinity("get", thread->name.c_str(), *mask);\n\treturn result;\n'),
    ],
    "src/kernel/pthread.h": [
        ("Pthread KYTY_SYSV_ABI PthreadSelf();\n", "Pthread KYTY_SYSV_ABI PthreadSelf();\nuint64_t              Bc5ModelMask(); // BC5 (experiment 0388)\n"),
    ],
    "src/libs/libKernel.cpp": [
        ('#include "common/abi.h"\n', INCLUDE + '#include "common/abi.h"\n'),
        ("#include <atomic>\n", "#include <atomic>\n#include <sched.h>\n"),
        ("static KYTY_SYSV_ABI int KernelGetCurrentCpu() {\n\tPRINT_NAME();\n\n\treturn 0;\n}\n",
         "static KYTY_SYSV_ABI int KernelGetCurrentCpu() {\n\tPRINT_NAME();\n\n"
         "\t// BC5 (experiment 0388): the real CPU, inside the thread's guest mask.\n"
         '\tstatic const bool on = bc5::cpu_model::parse_flag(std::getenv("KYTY_BC5_0388_CURRENT_CPU"));\n'
         "\tif (!on) {\n\t\treturn 0;\n\t}\n"
         "\tKernelCpumask mask = 0;\n\tPthreadGetaffinity(PthreadSelf(), &mask);\n"
         "\tconst int cpu = sched_getcpu();\n"
         "\treturn cpu < 0 ? 0 : bc5::cpu_model::guest_cpu(static_cast<unsigned>(cpu), mask, Bc5ModelMask());\n}\n"),
    ],
    "src/kernel/semaphore.cpp": [
        ('#include "kernel/semaphore.h"\n', '#include "kernel/semaphore.h"\n' + INCLUDE),
        ("#include <atomic>\n", "#include <atomic>\n#include <cinttypes>\n#include <cstdio>\n#include <cstdlib>\n#include <cstring>\n#include <pthread.h>\n#include <time.h>\n"),
        ("class KernelSemaPrivate {\npublic:\n",
         '''// BC5 (experiment 0388). Every part is off unless its switch is set, and acts on the title's JobLoaderSema only.
static int64_t Bc5NowNs() {
	timespec now {};
	clock_gettime(CLOCK_MONOTONIC, &now);
	return now.tv_sec * 1000000000LL + now.tv_nsec;
}

static bool Bc5Trace0388() {
	static const bool on = bc5::cpu_model::parse_flag(std::getenv("KYTY_BC5_0388_TRACE"));
	return on;
}

static bool Bc5TargetedWake() {
	static const bool on = bc5::cpu_model::parse_flag(std::getenv("KYTY_BC5_0388_TARGETED_WAKE"));
	return on;
}

// Catcher: counts in five time bands, printed every 20000.
class Bc5Bands {
public:
	void Add(const char* what, const void* sem, int64_t us) {
		m_bands[bc5::cpu_model::time_band(us)].fetch_add(1, std::memory_order_relaxed);
		if ((m_total.fetch_add(1, std::memory_order_relaxed) + 1) % 20000 == 0) {
			std::fprintf(stderr, "bc5 exp 0388: %s sema %p us <50 %" PRIu64 " <200 %" PRIu64 " <500 %" PRIu64 " <2000 %" PRIu64 " more %" PRIu64 "\\n", what, sem,
			             m_bands[0].load(), m_bands[1].load(), m_bands[2].load(), m_bands[3].load(), m_bands[4].load());
		}
	}

private:
	std::atomic<uint64_t> m_bands[5] {};
	std::atomic<uint64_t> m_total {0};
};

class KernelSemaPrivate {
public:
'''),
        ("m_max_count(max_count) {};\n", "m_max_count(max_count), m_bc5_job(name == \"JobLoaderSema\") {};\n"),
        ("\t[[nodiscard]] const std::string& GetName() const { return m_name; }\n",
         "\t[[nodiscard]] const std::string& GetName() const { return m_name; }\n"
         "\t[[nodiscard]] bool               Bc5Job() const { return m_bc5_job; }\n"
         "\t[[nodiscard]] uint64_t           Bc5Marked() const { return m_bc5_marked.load(std::memory_order_acquire); }\n"
         "\t[[nodiscard]] uint64_t           Bc5Returned() const { return m_bc5_returned.load(std::memory_order_acquire); }\n"),
        ("\t\tbool   ready      = false;\n",
         "\t\tbool   ready      = false;\n\t\tint64_t         bc5_signal_ns = 0;       // BC5 (experiment 0388): the signal that marked this waiter\n"
         "\t\tCommon::CondVar* bc5_cv       = nullptr;\n"),
        ("\tint                         m_max_count;\n};\n",
         "\tint                         m_max_count;\n"
         "\tbool                        m_bc5_job;\n"
         "\tstd::atomic<uint64_t>       m_bc5_marked {0};\n"
         "\tstd::atomic<uint64_t>       m_bc5_returned {0};\n"
         "\tint64_t                     m_bc5_signal_ns = 0;\n"
         "\tBc5Bands                    m_bc5_blocked;\n"
         "\tBc5Bands                    m_bc5_credit;\n};\n"),
        ("\tWakeWaiters();\n\n\tm_cond_var.SignalAll();\n",
         "\tif (m_bc5_job && Bc5Trace0388()) {\n\t\tm_bc5_signal_ns = Bc5NowNs();\n\t}\n\n"
         "\tWakeWaiters();\n\n\tif (!(m_bc5_job && Bc5TargetedWake())) {\n\t\tm_cond_var.SignalAll();\n\t}\n"),
        ("\t\t\twaiter->result = Result::Ok;\n\t\t\twaiter->ready  = true;\n",
         "\t\t\twaiter->result = Result::Ok;\n\t\t\twaiter->ready  = true;\n"
         "\t\t\tif (m_bc5_job) {\n\t\t\t\twaiter->bc5_signal_ns = m_bc5_signal_ns;\n\t\t\t\tm_bc5_marked.fetch_add(1, std::memory_order_release);\n"
         "\t\t\t\tif (waiter->bc5_cv != nullptr) {\n\t\t\t\t\twaiter->bc5_cv->Signal();\n\t\t\t\t}\n\t\t\t}\n"),
        ("KernelSemaPrivate::Result KernelSemaPrivate::Wait(int need_count, uint32_t* ptr_micros) {\n\tCommon::LockGuard lock(m_mutex);\n",
         '''KernelSemaPrivate::Result KernelSemaPrivate::Wait(int need_count, uint32_t* ptr_micros) {
	// BC5 (experiment 0388): KYTY_BC5_0388_WAIT_SPIN_US, a waiter looks at the count for a bounded time before it sleeps.
	static const unsigned wait_spin_us = bc5::cpu_model::parse_spin_us(std::getenv("KYTY_BC5_0388_WAIT_SPIN_US"));
	if (wait_spin_us != 0 && m_bc5_job) {
		const int64_t start = Bc5NowNs();
		while (__atomic_load_n(&m_count, __ATOMIC_RELAXED) < need_count && Bc5NowNs() - start < wait_spin_us * 1000LL) {
			__builtin_ia32_pause();
		}
	}

	Common::LockGuard lock(m_mutex);
'''),
        ("\tif (m_count >= need_count) {\n\t\tm_count -= need_count;\n\t\tif (ptr_micros != nullptr) {\n",
         "\tif (m_count >= need_count) {\n\t\tm_count -= need_count;\n"
         "\t\tif (m_bc5_job && Bc5Trace0388()) {\n\t\t\tm_bc5_credit.Add(\"credit taken after signal\", this, (Bc5NowNs() - m_bc5_signal_ns) / 1000);\n\t\t}\n"
         "\t\tif (ptr_micros != nullptr) {\n"),
        ("\twaiter.need_count = need_count;\n\tAddWaiter(&waiter);\n",
         "\twaiter.need_count = need_count;\n"
         "\tCommon::CondVar* wait_cv = &m_cond_var;\n"
         "\tif (m_bc5_job && Bc5TargetedWake()) { // Cancel and delete still broadcast: such a waiter sees them at its next timeout\n"
         "\t\tstatic thread_local Common::CondVar bc5_own_cv;\n\t\twait_cv       = &bc5_own_cv;\n\t\twaiter.bc5_cv = wait_cv;\n\t}\n"
         "\tAddWaiter(&waiter);\n"),
        ("\t\t\tm_cond_var.WaitFor(&m_mutex, SIGNAL_APC_POLL_MICROS);\n\t\t} else {\n\t\t\tm_cond_var.WaitFor(&m_mutex, micros - elapsed);\n",
         "\t\t\twait_cv->WaitFor(&m_mutex, SIGNAL_APC_POLL_MICROS);\n\t\t} else {\n\t\t\twait_cv->WaitFor(&m_mutex, micros - elapsed);\n"),
        ("\tRemoveWaiter(&waiter);\n\n\tif (ptr_micros != nullptr) {\n\t\t*ptr_micros = (elapsed >= micros ? 0 : micros - elapsed);\n",
         "\tRemoveWaiter(&waiter);\n\n"
         "\tif (m_bc5_job && waiter.result == Result::Ok) {\n"
         "\t\tm_bc5_returned.fetch_add(1, std::memory_order_release);\n"
         "\t\tif (Bc5Trace0388()) {\n\t\t\tm_bc5_blocked.Add(\"marked waiter returned after its signal\", this, (Bc5NowNs() - waiter.bc5_signal_ns) / 1000);\n\t\t}\n\t}\n\n"
         "\tif (ptr_micros != nullptr) {\n\t\t*ptr_micros = (elapsed >= micros ? 0 : micros - elapsed);\n"),
        ("int KYTY_SYSV_ABI KernelWaitSema(KernelSema sem, int need, KernelUseconds* time) {\n",
         '''// BC5 (experiment 0388). After a game-main signal, one of (the first set wins): PUSH_SPIN_US spins that long.
// PUSH_UNTIL_RETURN_US spins until any wait on any JobLoaderSema returned; not paired with a signal or a job (R11).
// PUSH_UNTIL_PAIRED_US spins until every waiter this semaphore has marked has returned, and not at all if none is marked.
// PUSH_UNTIL_TARGET_US spins while the entry of this semaphore has an open job of the crash's function, and not at all
// otherwise: the pairing with the job. It reads the title's job table (exp 0358 F449).
static std::atomic<uint64_t> g_bc5_wait_returns {0};
static std::atomic<int64_t>  g_bc5_signal_ns {0};

static void Bc5NoteWaitReturn(const KernelSemaPrivate* sem) {
	if (!sem->Bc5Job()) {
		return;
	}
	g_bc5_wait_returns.fetch_add(1, std::memory_order_release);
	const int64_t signal_ns = g_bc5_signal_ns.load(std::memory_order_relaxed);
	if (Bc5Trace0388() && signal_ns != 0) {
		static Bc5Bands bands;
		bands.Add("last signal of any JobLoaderSema to wait return (unpaired)", nullptr, (Bc5NowNs() - signal_ns) / 1000);
	}
}

template <class T>
static T Bc5TitleRead(uint64_t address) {
	return *reinterpret_cast<const volatile T*>(address);
}

static bool Bc5TargetJobOpen(const KernelSemaPrivate* sem) {
	using namespace bc5::cpu_model;
	const uint64_t table = kImageBase + kJobTable;
	for (uint64_t k = 0; k < 3; k++) {
		const uint64_t entry = table + k * kJobEntryStride;
		if (Bc5TitleRead<uint64_t>(entry + kJobSema) != reinterpret_cast<uint64_t>(sem)) {
			continue;
		}
		const int      pending = Bc5TitleRead<int>(entry + kJobPendingN);
		const uint64_t list    = Bc5TitleRead<uint64_t>(entry + kJobPending);
		for (int i = 0; list != 0 && i < pending && i < 64; i++) {
			const uint64_t handle = Bc5TitleRead<uint64_t>(list + static_cast<uint64_t>(i) * 8);
			const auto     job_id = decode_job(handle);
			const uint64_t owner  = table + job_id.entry * kJobEntryStride;
			if (handle == 0 || Bc5TitleRead<uint32_t>(owner + kJobGeneration) != job_id.generation ||
			    static_cast<int>(job_id.index) >= Bc5TitleRead<int>(owner + kJobLive)) {
				continue;
			}
			const uint64_t job  = Bc5TitleRead<uint64_t>(owner + kJobObjects) + job_id.index * kJobSize;
			bool           kind = false;
			for (uint64_t off = 0; off < kJobSize; off += 8) { // where the object keeps the function is not read yet
				kind = kind || Bc5TitleRead<uint64_t>(job + off) == kImageBase + kCrashJobFn;
			}
			if (kind && Bc5TitleRead<int>(job + kJobStarted) < Bc5TitleRead<int>(job + kJobTotal)) {
				return true;
			}
		}
		return false;
	}
	return false;
}

static void Bc5OwnerPushSpin(const KernelSemaPrivate* sem, uint64_t returns_before) {
	static const unsigned spin_us   = bc5::cpu_model::parse_spin_us(std::getenv("KYTY_BC5_0388_PUSH_SPIN_US"));
	static const unsigned until_us  = bc5::cpu_model::parse_spin_us(std::getenv("KYTY_BC5_0388_PUSH_UNTIL_RETURN_US"));
	static const unsigned paired_us = bc5::cpu_model::parse_bound_us(std::getenv("KYTY_BC5_0388_PUSH_UNTIL_PAIRED_US"));
	static const unsigned target_us = bc5::cpu_model::parse_bound_us(std::getenv("KYTY_BC5_0388_PUSH_UNTIL_TARGET_US"));
	const unsigned        bound     = spin_us != 0 ? spin_us : until_us != 0 ? until_us : paired_us != 0 ? paired_us : target_us;
	if (!sem->Bc5Job() || (bound == 0 && !Bc5Trace0388())) {
		return;
	}
	static thread_local const bool is_main = [] {
		char thread_name[16] = {};
		pthread_getname_np(pthread_self(), thread_name, sizeof(thread_name));
		return std::strcmp(thread_name, "game-main") == 0;
	}();
	if (!is_main) {
		return;
	}
	static std::atomic<uint64_t> pushes {0};
	static std::atomic<uint64_t> targets {0};
	static std::atomic<uint64_t> spins {0};
	static std::atomic<uint64_t> met {0};
	const bool                   by_paired = spin_us == 0 && until_us == 0 && paired_us != 0;
	const bool                   by_target = spin_us == 0 && until_us == 0 && paired_us == 0 && target_us != 0;
	const bool                   open      = Bc5TargetJobOpen(sem);
	const uint64_t               marked    = sem->Bc5Marked();
	if (open) {
		targets.fetch_add(1, std::memory_order_relaxed);
	}
	bool wanted = bound != 0;
	if (by_paired) {
		wanted = sem->Bc5Returned() < marked;
	} else if (by_target) {
		wanted = open;
	}
	if (wanted) {
		const int64_t start = Bc5NowNs();
		bool          done  = false;
		while (!done && Bc5NowNs() - start < bound * 1000LL) {
			if (by_paired) {
				done = sem->Bc5Returned() >= marked;
			} else if (by_target) {
				done = !Bc5TargetJobOpen(sem);
			} else if (spin_us == 0) {
				done = g_bc5_wait_returns.load(std::memory_order_acquire) != returns_before;
			}
			__builtin_ia32_pause();
		}
		spins.fetch_add(1, std::memory_order_relaxed);
		met.fetch_add(done ? 1 : 0, std::memory_order_relaxed);
	}
	if ((pushes.fetch_add(1, std::memory_order_relaxed) + 1) % 2000 == 0) {
		std::fprintf(stderr, "bc5 exp 0388: push spin pushes %" PRIu64 ", open target jobs %" PRIu64 ", spins %" PRIu64 ", ended by their condition %" PRIu64 "\\n", pushes.load(),
		             targets.load(), spins.load(), met.load());
	}
}

int KYTY_SYSV_ABI KernelWaitSema(KernelSema sem, int need, KernelUseconds* time) {
'''),
        ("\tauto result = sem->Wait(need, time);\n",
         "\tauto result = sem->Wait(need, time);\n\n\tif (result == KernelSemaPrivate::Result::Ok) {\n\t\tBc5NoteWaitReturn(sem);\n\t}\n"),
        ("\tauto result = sem->Signal(count);\n\n\tint ret = OK;\n",
         "\tconst uint64_t bc5_returns = g_bc5_wait_returns.load(std::memory_order_acquire);\n"
         "\tif (Bc5Trace0388() && sem->Bc5Job()) {\n\t\tg_bc5_signal_ns.store(Bc5NowNs(), std::memory_order_relaxed);\n\t}\n"
         "\tauto result = sem->Signal(count);\n\n\tBc5OwnerPushSpin(sem, bc5_returns);\n\n\tint ret = OK;\n"),
    ],
}


def main():
    out = {}
    for rel, edits in EDITS.items():
        with open(f"{ROOT}/{rel}", "rb") as f:
            data = f.read()
        crlf = b"\r\n" in data
        text = data.decode("utf-8").replace("\r\n", "\n")
        if "\r" in text:
            print(f"{rel}: stray CR")
            return 1
        for old, new in edits:
            if text.count(old) != 1:
                print(f"{rel}: anchor occurs {text.count(old)} times: {old[:60]!r}")
                return 1
            text = text.replace(old, new)
        if crlf:
            text = text.replace("\n", "\r\n")
        out[rel] = text.encode("utf-8")
    for rel, data in out.items():
        with open(f"{ROOT}/{rel}", "wb") as f:
            f.write(data)
        print(f"{rel}: {len(EDITS[rel])} edits")
    return 0


if __name__ == "__main__":
    sys.exit(main())
