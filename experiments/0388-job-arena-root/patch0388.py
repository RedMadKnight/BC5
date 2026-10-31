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
        ("#include <atomic>\n", "#include <atomic>\n#include <cstring>\n#include <pthread.h>\n#include <time.h>\n"),
        ("int KYTY_SYSV_ABI KernelSignalSema(KernelSema sem, int count) {\n",
         '''// BC5 (experiment 0388): after the title's main thread pushes to its job system, spin a bounded time so a worker can
// take the job first.
static void Bc5OwnerPushSpin(const std::string& name) {
	static const unsigned us = bc5::cpu_model::parse_spin_us(std::getenv("KYTY_BC5_0388_PUSH_SPIN_US"));
	if (us == 0 || name != "JobLoaderSema") {
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
	timespec start {};
	timespec now {};
	clock_gettime(CLOCK_MONOTONIC, &start);
	do {
		__builtin_ia32_pause();
		clock_gettime(CLOCK_MONOTONIC, &now);
	} while ((now.tv_sec - start.tv_sec) * 1000000000LL + (now.tv_nsec - start.tv_nsec) < us * 1000LL);
}

int KYTY_SYSV_ABI KernelSignalSema(KernelSema sem, int count) {
'''),
        ("\tauto result = sem->Signal(count);\n\n\tint ret = OK;\n",
         "\tauto result = sem->Signal(count);\n\n\tBc5OwnerPushSpin(sem->GetName());\n\n\tint ret = OK;\n"),
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
