#!/usr/bin/env python3
"""BC5 exp 0388, the integration: the job push wait (arm J) into the host's units, on a tree of patch 0001 at main.
Each edit's anchor must occur exactly once, or nothing is written. Line endings stay as each file has them.
usage: python3 -I mkhost.py <tree with src/> <the new header>"""
import shutil
import sys

ROOT, HEADER = sys.argv[1:3]

WAIT = '''// BC5 (experiment 0388): the job push wait, arm J (bc5/job_push_wait.hpp). loader/gamePatch.cpp turns it on with the image
// base, for the second title only; until then a signal pays one relaxed load.
static std::atomic<uint64_t> g_bc5_job_image {0};

extern "C" void bc5_job_push_wait_enable(uint64_t image_base) {
	g_bc5_job_image.store(image_base, std::memory_order_relaxed);
}

static int64_t Bc5NowNs() {
	timespec now {};
	clock_gettime(CLOCK_MONOTONIC, &now);
	return now.tv_sec * 1000000000LL + now.tv_nsec;
}

struct Bc5TitleMemory {
	[[nodiscard]] uint64_t u64(uint64_t address) const { return *reinterpret_cast<const volatile uint64_t*>(address); }
	[[nodiscard]] uint32_t u32(uint64_t address) const { return *reinterpret_cast<const volatile uint32_t*>(address); }
	[[nodiscard]] int      i32(uint64_t address) const { return *reinterpret_cast<const volatile int*>(address); }
};

static void Bc5JobPushWait(const KernelSemaPrivate* sem) {
	using namespace bc5::job_push_wait;
	const uint64_t base = g_bc5_job_image.load(std::memory_order_relaxed);
	if (base == 0 || !sem->Bc5Job()) {
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
	const Bc5TitleMemory mem;
	const auto           sem_address = reinterpret_cast<uint64_t>(sem);
	const bool           open        = target_job_open(mem, base, sem_address);
	bool                 done        = false;
	if (open) {
		const int64_t start = Bc5NowNs();
		while (!done && Bc5NowNs() - start < kBoundUs * 1000LL) {
			done = !target_job_open(mem, base, sem_address);
			__builtin_ia32_pause();
		}
	}
#ifndef BC5_LEAN
	static const bool trace = BC5_DIAG_ENV("KYTY_BC5_JOB_PUSH_TRACE") != nullptr;
	if (trace) {
		static std::atomic<uint64_t> pushes {0};
		static std::atomic<uint64_t> waits {0};
		static std::atomic<uint64_t> met {0};
		waits.fetch_add(open ? 1 : 0, std::memory_order_relaxed);
		met.fetch_add(done ? 1 : 0, std::memory_order_relaxed);
		if ((pushes.fetch_add(1, std::memory_order_relaxed) + 1) % 2000 == 0) {
			std::fprintf(stderr, "job push wait: pushes %" PRIu64 ", waits %" PRIu64 ", ended by their condition %" PRIu64 "\\n", pushes.load(), waits.load(), met.load());
		}
	}
#endif
}

int KYTY_SYSV_ABI KernelWaitSema(KernelSema sem, int need, KernelUseconds* time) {
'''

APPLY = '''// BC5 (experiment 0388): the job push wait, arm J (bc5/job_push_wait.hpp), on by default for the second title. It looks
// at the owner's help call to know the title's code, so it runs before the job-arena fix writes there.
extern "C" void bc5_job_push_wait_enable(uint64_t image_base); // kernel/semaphore.cpp

bool ApplyJobPushWait(Program* program) {
	std::string title;
	SystemContentParamSfoGetString("TITLE_ID", &title);
	const bool title_ok = Common::EqualNoCase(title, bc5::job_arena_fix::kTitleId);
	const bool loaded   = program != nullptr && program->elf != nullptr && program->base_vaddr != 0;
	const bool code_ok  = title_ok && loaded && bc5::job_arena_fix::site_matches(reinterpret_cast<const uint8_t*>(program->base_vaddr + bc5::job_arena_fix::kSiteOffset));
	const bool on       = bc5::job_push_wait::wait_on(title_ok, code_ok, std::getenv("KYTY_BC5_JOB_PUSH_WAIT"));
	if (title_ok) {
		std::fprintf(stderr, "game fix (exp 0388): job push wait %s, %d us at most%s\\n", on ? "ON" : "OFF", static_cast<int>(bc5::job_push_wait::kBoundUs), code_ok ? "" : ", not the known build of the title");
	}
	if (on) {
		bc5_job_push_wait_enable(program->base_vaddr);
	}
	return on;
}

bool Apply(const std::filesystem::path& plan_path, Program* program) {
'''

EDITS = {
    "src/kernel/semaphore.cpp": [
        ('#include "kernel/semaphore.h"\n', '#include "kernel/semaphore.h"\n#include "bc5/job_push_wait.hpp" // BC5 (experiment 0388)\n'),
        ("#include <atomic>\n", "#include <atomic>\n#include <cinttypes>\n#include <cstdio>\n#include <cstring>\n#include <pthread.h>\n#include <time.h>\n"),
        ("m_max_count(max_count) {};\n", "m_max_count(max_count), m_bc5_job(name == \"JobLoaderSema\") {};\n"),
        ("\t[[nodiscard]] const std::string& GetName() const { return m_name; }\n",
         "\t[[nodiscard]] const std::string& GetName() const { return m_name; }\n\t[[nodiscard]] bool               Bc5Job() const { return m_bc5_job; }\n"),
        ("\tint                         m_max_count;\n};\n", "\tint                         m_max_count;\n\tbool                        m_bc5_job;\n};\n"),
        ("int KYTY_SYSV_ABI KernelWaitSema(KernelSema sem, int need, KernelUseconds* time) {\n", WAIT),
        ("\tauto result = sem->Signal(count);\n\n\tint ret = OK;\n", "\tauto result = sem->Signal(count);\n\n\tBc5JobPushWait(sem);\n\n\tint ret = OK;\n"),
    ],
    "src/loader/gamePatch.cpp": [
        ('#include "bc5/job_arena_fix.hpp" // BC5 (experiment 0359)\n',
         '#include "bc5/job_arena_fix.hpp" // BC5 (experiment 0359)\n#include "bc5/job_push_wait.hpp" // BC5 (experiment 0388)\n'),
        ("#include <cstdint>\n", "#include <cstdint>\n#include <cstdlib>\n"),
        ("bool Apply(const std::filesystem::path& plan_path, Program* program) {\n", APPLY),
    ],
    "src/loader/gamePatch.h": [
        ("bool Apply(const std::filesystem::path& plan_path, Program* program);\n",
         "bool Apply(const std::filesystem::path& plan_path, Program* program);\n\n"
         "// BC5 (experiment 0388): the job push wait for PPSA03671 (bc5/job_push_wait.hpp); KYTY_BC5_JOB_PUSH_WAIT=0 turns it off.\n"
         "// True when on. Call it before ApplyJobArenaFix, which writes at the site this looks at.\n"
         "bool ApplyJobPushWait(Program* program);\n"),
    ],
    "src/loader/runtimeLinker.cpp": [
        ("	// BC5 (experiment 0359): the job-arena fix (a temporary game-code workaround), per the title's switch.\n",
         "	GamePatch::ApplyJobPushWait(m_programs.empty() ? nullptr : m_programs.front()); // BC5 (experiment 0388)\n"
         "	// BC5 (experiment 0359): the job-arena fix (a temporary game-code workaround), per the title's switch.\n"),
    ],
}


def main():
    out = {}
    for rel, edits in EDITS.items():
        with open(f"{ROOT}/{rel}", "rb") as f:
            data = f.read()
        crlf = b"\r\n" in data
        text = data.decode("utf-8").replace("\r\n", "\n")
        for old, new in edits:
            if text.count(old) != 1:
                print(f"{rel}: anchor occurs {text.count(old)} times: {old[:60]!r}")
                return 1
            text = text.replace(old, new)
        out[rel] = (text.replace("\n", "\r\n") if crlf else text).encode("utf-8")
    for rel, data in out.items():
        with open(f"{ROOT}/{rel}", "wb") as f:
            f.write(data)
        print(f"{rel}: {len(EDITS[rel])} edits")
    shutil.copyfile(HEADER, f"{ROOT}/src/bc5/job_push_wait.hpp")
    return 0


if __name__ == "__main__":
    sys.exit(main())
