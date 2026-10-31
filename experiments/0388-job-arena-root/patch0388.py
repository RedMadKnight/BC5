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
        ("int KYTY_SYSV_ABI KernelWaitSema(KernelSema sem, int need, KernelUseconds* time) {\n",
         '''// BC5 (experiment 0388), JobLoaderSema only. Catcher (KYTY_BC5_0388_TRACE=1): the time from the last signal to a wait's
// return, as counts in five bands. Candidates, each after a game-main signal: PUSH_SPIN_US spins that long,
// PUSH_UNTIL_TAKEN_US spins until a waiter has returned, at most that long.
static std::atomic<uint64_t> g_bc5_taken {0};
static std::atomic<int64_t>  g_bc5_signal_ns {0};

static int64_t Bc5NowNs() {
	timespec now {};
	clock_gettime(CLOCK_MONOTONIC, &now);
	return now.tv_sec * 1000000000LL + now.tv_nsec;
}

static bool Bc5JobSema(const std::string& name) {
	return name == "JobLoaderSema";
}

static bool Bc5Trace0388() {
	static const bool on = bc5::cpu_model::parse_flag(std::getenv("KYTY_BC5_0388_TRACE"));
	return on;
}

static void Bc5NoteTaken(const std::string& name) {
	if (!Bc5JobSema(name)) {
		return;
	}
	g_bc5_taken.fetch_add(1, std::memory_order_release);
	const int64_t signal_ns = g_bc5_signal_ns.load(std::memory_order_relaxed);
	if (!Bc5Trace0388() || signal_ns == 0) {
		return;
	}
	static std::atomic<uint64_t> bands[5] {};
	static std::atomic<uint64_t> total {0};
	const int64_t                us   = (Bc5NowNs() - signal_ns) / 1000;
	const int                    band = (us < 50 ? 0 : us < 200 ? 1 : us < 500 ? 2 : us < 2000 ? 3 : 4);
	bands[band].fetch_add(1, std::memory_order_relaxed);
	const uint64_t n = total.fetch_add(1, std::memory_order_relaxed) + 1;
	if (n % 5000 == 0) {
		std::fprintf(stderr, "bc5 exp 0388: wake us <50 %" PRIu64 " <200 %" PRIu64 " <500 %" PRIu64 " <2000 %" PRIu64 " more %" PRIu64 "\\n", bands[0].load(), bands[1].load(), bands[2].load(),
		             bands[3].load(), bands[4].load());
	}
}

static void Bc5OwnerPushSpin(const std::string& name, uint64_t taken_before) {
	static const unsigned spin_us  = bc5::cpu_model::parse_spin_us(std::getenv("KYTY_BC5_0388_PUSH_SPIN_US"));
	static const unsigned until_us = bc5::cpu_model::parse_spin_us(std::getenv("KYTY_BC5_0388_PUSH_UNTIL_TAKEN_US"));
	if ((spin_us == 0 && until_us == 0) || !Bc5JobSema(name)) {
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
	const int64_t start = Bc5NowNs();
	const int64_t limit = static_cast<int64_t>(spin_us != 0 ? spin_us : until_us) * 1000;
	bool          taken = false;
	while (Bc5NowNs() - start < limit) {
		if (spin_us == 0 && g_bc5_taken.load(std::memory_order_acquire) != taken_before) {
			taken = true;
			break;
		}
		__builtin_ia32_pause();
	}
	static std::atomic<uint64_t> spins {0};
	static std::atomic<uint64_t> takes {0};
	const uint64_t               got = takes.fetch_add(taken ? 1 : 0, std::memory_order_relaxed) + (taken ? 1 : 0);
	const uint64_t               n   = spins.fetch_add(1, std::memory_order_relaxed) + 1;
	if (n == 1 || n % 2000 == 0) {
		std::fprintf(stderr, "bc5 exp 0388: push spin %" PRIu64 ", taken in time %" PRIu64 "\\n", n, got);
	}
}

int KYTY_SYSV_ABI KernelWaitSema(KernelSema sem, int need, KernelUseconds* time) {
'''),
        ("\tauto result = sem->Wait(need, time);\n",
         "\tauto result = sem->Wait(need, time);\n\n\tif (result == KernelSemaPrivate::Result::Ok) {\n\t\tBc5NoteTaken(sem->GetName());\n\t}\n"),
        ("\tauto result = sem->Signal(count);\n\n\tint ret = OK;\n",
         "\tconst uint64_t bc5_taken = g_bc5_taken.load(std::memory_order_acquire);\n"
         "\tif (Bc5Trace0388() && Bc5JobSema(sem->GetName())) {\n\t\tg_bc5_signal_ns.store(Bc5NowNs(), std::memory_order_relaxed);\n\t}\n"
         "\tauto result = sem->Signal(count);\n\n\tBc5OwnerPushSpin(sem->GetName(), bc5_taken);\n\n\tint ret = OK;\n"),
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
