#!/usr/bin/env python3
"""BC5 exp 0429: the private build's edits on a copy of the shared tree at patch a8717e53.
    mk0429.py <tree root>
The maintainer, 2026-11-16, through the top session: JobArenaFix must leave the menu, the switches and every other
place, and the crash must be solved by the host.

1. Removal of exp 0359's job-arena workaround, in both builds, with no switch:
   - src/loader/gamePatch.cpp and .h: the hook, ApplyJobArenaFix and their includes (both files go back to f266548's
     text; checked by the caller's diff);
   - src/loader/runtimeLinker.cpp: the call at Execute, the switch's extern and bc5_tls_main_tcb (used only by the hook);
   - src/graphics/presentation/hostMenu.cpp: the "Game fixes" submenu (it held only this item);
   - src/graphics/presentation/window/hostInput.cpp and .h: the input.cfg key, its member and accessors, and
     KYTY_BC5_JOB_ARENA_FIX. An old "JobArenaFix.<TITLE_ID>=..." line is accepted silently and not written back;
   - src/bc5/job_arena_fix.hpp: deleted;
   - the one comment in pthread.cpp that named it.
2. Candidates, each behind its own switch, default off:
   - KYTY_BC5_0429_PRIO_ORDER=1 (pthread.cpp, Bc5GuestNice): guest priorities 550-732 keep their order as nice +1..+4
     below the job workers (550-599 +1, 600-649 +2, 650-699 +3, 700-732 +4); up to 299 -15, 300-549 0, from 733 +5 as
     before;
   - KYTY_BC5_0429_CPU13=1 (pthread.cpp): the title's 13-CPU model: the default mask 0x1fff, and each guest CPU 0-12 as
     one host logical CPU (guest 2k, 2k+1 = the SMT threads of host core k), applied at start and at Setaffinity
     (exp 0429's second build; the first build's AFFINITY=1|2 read the bits as cores and is gone);
   - exp 0425's semaphore edits unchanged (patch0425.SEMA): C2 KYTY_BC5_0425_HANDOFF_US, C3 KYTY_BC5_0425_DIRECT_WAKE,
     and its counters (KYTY_BC5_0425_CATCH, normal only, now read by nothing).
3. Catcher, normal build only: KYTY_BC5_0429_TRACE=1 logs each guest thread's mask, priority and nice at start and at
   Setaffinity/Setprio (the first 400), so the title's requests are on record.
Every anchor must occur once; line endings are kept."""
import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import patch0425  # noqa: E402  (exp 0425's semaphore edits)

PINS = {  # sha256 of the units at patch a8717e53 (laptop tree f266548 + a8717e53, 2026-11-16)
    'src/kernel/semaphore.cpp': '0deadcb85b3419a9bd75535a8dc39878a3b7fd81120217db3043c65dcf5f0bdd',
    'src/kernel/pthread.cpp': '4e30e573b5d5838be591c31bc318264dca90b8c7a04405a9127801707a103da9',
}


def load(path):
    raw = open(path, 'rb').read()
    crlf = b'\r\n' in raw
    return raw, crlf, raw.decode('utf-8').replace('\r\n', '\n')


def save(path, text, crlf):
    out = (text.replace('\n', '\r\n') if crlf else text).encode('utf-8')
    open(path, 'wb').write(out)
    print('mk0429: %s %s, sha256 %s' % (path, 'CRLF' if crlf else 'LF', hashlib.sha256(out).hexdigest()[:16]))


def stop(msg):
    sys.exit('mk0429 STOP: ' + msg)


def one(text, old, new, what):
    if text.count(old) != 1:
        stop('%s: anchor occurs %d times' % (what, text.count(old)))
    return text.replace(old, new)


def idx(lines, needle, what):
    hits = [i for i, l in enumerate(lines) if needle in l]
    if len(hits) != 1:
        stop('%s: "%s" on %d lines' % (what, needle, len(hits)))
    return hits[0]


def close_of(lines, i, what):
    """The index of the line that closes the brace block opened on line i: the next line that is the same indent + '}'."""
    ind = lines[i][:len(lines[i]) - len(lines[i].lstrip())]
    for k in range(i + 1, len(lines)):
        if lines[k] == ind + '}':
            return k
    stop('%s: no closing brace' % what)


def edit_lines(path, fn):
    raw, crlf, text = load(path)
    lines = text.split('\n')
    lines = fn(lines)
    save(path, '\n'.join(lines), crlf)


# ---------------------------------------------------------------------------------------------------- 1. the removal
def gp_cpp(lines):
    i = idx(lines, '#include "bc5/job_arena_fix.hpp"', 'gamePatch.cpp include')
    want = ['#include "common/abi.h"', '', '#include <array>', '#include <atomic>', '#include <cinttypes>', '#include <cstdint>']
    if lines[i + 1:i + 7] != want:
        stop('gamePatch.cpp: the includes after job_arena_fix.hpp are not exp 0359\'s')
    del lines[i:i + 7]
    s = idx(lines, '// BC5 (experiment 0359): the job-arena fix, a TEMPORARY', 'gamePatch.cpp block')
    e = idx(lines, 'bool Apply(const std::filesystem::path& plan_path, Program* program) {', 'gamePatch.cpp Apply')
    if not s < e:
        stop('gamePatch.cpp: block order')
    del lines[s:e]
    return lines


def gp_h(lines):
    i = idx(lines, '// BC5 (experiment 0359): the job-arena fix for PPSA03671', 'gamePatch.h')
    if lines[i - 1] != '' or not lines[i + 2].startswith('bool ApplyJobArenaFix('):
        stop('gamePatch.h: unexpected shape')
    del lines[i - 1:i + 3]
    return lines


def rl_cpp(lines):
    del lines[idx(lines, 'extern "C" int bc5_title_switch_job_arena_fix();', 'runtimeLinker extern')]
    i = idx(lines, '// BC5 (experiment 0359): the current thread\'s thread control block', 'runtimeLinker tcb')
    if lines[i + 1] != 'extern "C" uint8_t* bc5_tls_main_tcb() {' or lines[i + 3] != '}' or lines[i + 4] != '':
        stop('runtimeLinker.cpp: bc5_tls_main_tcb is not the expected 3 lines')
    del lines[i:i + 5]
    i = idx(lines, '// BC5 (experiment 0359): the job-arena fix (a temporary game-code workaround)', 'runtimeLinker call')
    if 'GamePatch::ApplyJobArenaFix(' not in lines[i + 1]:
        stop('runtimeLinker.cpp: the call is not after its comment')
    del lines[i:i + 2]
    return lines


def menu_cpp(lines):
    s = idx(lines, '// Experiment 0359: game fixes - TEMPORARY game-code workarounds', 'hostMenu comment')
    b = idx(lines, 'if (ImGui::BeginMenu("Game fixes")) {', 'hostMenu submenu')
    if b != s + 2:
        stop('hostMenu.cpp: unexpected shape')
    e = close_of(lines, b, 'hostMenu submenu')
    del lines[s:e + 1]
    return lines


def input_cpp(lines):
    del lines[idx(lines, 'if (m_job_arena_fix >= 0) out.emplace_back("JobArenaFix."', 'hostInput save')]
    del lines[idx(lines, 'JobArenaFix() const { return m_job_arena_fix; }', 'hostInput getter')]
    del lines[idx(lines, 'SetJobArenaFix(int v) { m_job_arena_fix = v; }', 'hostInput setter')]
    i = idx(lines, 'EqualNoCase(left.substr(0, 12), "JobArenaFix.")', 'hostInput parse')
    e = close_of(lines, i, 'hostInput parse')
    ind = lines[i][:len(lines[i]) - len(lines[i].lstrip())]
    lines[i:e + 1] = [
        ind + 'if (left.size() > 12 && EqualNoCase(left.substr(0, 12), "JobArenaFix.")) {',
        ind + '\t// Experiment 0429: the job-arena workaround of exp 0359 is gone; an old line of its key is accepted silently',
        ind + '\t// and not written back.',
        ind + '\treturn true;',
        ind + '}',
    ]
    del lines[idx(lines, 'int                  m_job_arena_fix    = -1;', 'hostInput member')]
    s = idx(lines, '// BC5 (experiment 0359): the job-arena fix switch, JobArenaFix.<TITLE_ID>=on|off;', 'hostInput functions')
    f = idx(lines, 'extern "C" int bc5_title_switch_job_arena_fix() {', 'hostInput extern C')
    if lines[f + 1].strip() != 'return HostInputJobArenaFix();' or lines[f + 2] != '}' or f - s != 8:
        stop('hostInput.cpp: the functions are not the expected 11 lines')
    del lines[s:f + 3]
    if lines[s] == '' and lines[s - 1] == '':
        del lines[s]
    return lines


def input_h(lines):
    i = idx(lines, '// BC5 (experiment 0359): the job-arena fix switch (JobArenaFix.<TITLE_ID>=on|off)', 'hostInput.h')
    if lines[i + 2] != 'int  HostInputJobArenaFix();' or lines[i + 3] != 'void HostInputSetJobArenaFix(int v);':
        stop('hostInput.h: unexpected shape')
    del lines[i:i + 4]
    return lines


# ---------------------------------------------------------------------------------------------- 2. pthread.cpp edits
PRIO_FN = '''// ---- experiment 0429: KYTY_BC5_0429_PRIO_ORDER=1, the console's priority order below the job workers ------------
// The console runs a title's threads by fixed priority (TODO(verify): no console measurement; FreeBSD-derived kernel):
// a lower number always wins. Here 300-732 were all nice 0, so the title's Hi job workers (500) shared the CPU equally
// with its Lo workers (600), physics (550, 700), video and IO threads (exp 0360 F471: the Hi workers 156-205 ms a
// second in the run queue at the fight). On: 550-599 +1, 600-649 +2, 650-699 +3, 700-732 +4; the rest as before.
static bool Bc5PrioOrder() {
	static const bool v = [] {
		const bool on = bc5::env_rule::on(std::getenv("KYTY_BC5_0429_PRIO_ORDER"));
#ifndef BC5_LEAN
		std::fprintf(stderr, "[bc5] exp 0429: prio order %s\\n", on ? "ON" : "off");
#endif
		return on;
	}();
	return v;
}

static int Bc5GuestNice(int guest_priority) {
	if (guest_priority <= 299) {
		return -15;
	}
	if (guest_priority >= 733) {
		return 5;
	}
	if (guest_priority >= 550 && Bc5PrioOrder()) {
		return std::min(4, (guest_priority - 500) / 50);
	}
	return 0;
}'''

AFF_BLOCK = '''
// ---- experiment 0429: KYTY_BC5_0429_CPU13=1, the title's 13-CPU model with its masks applied --------------------
// The title's masks use guest CPUs 0-12 (exp 0429's smoke trace: Job Hi 0xff, Job Lo/Bk 0x1ff, MainThread 0x100 or
// 0x800, Render Thread 0x400, IO and audio 0x800-0x1a00), but the host's default mask was 0x7f, so the title counted 7
// CPUs (F790) and every mask was only stored. On: the default mask is 0x1fff (13 CPUs; the title then makes 8 workers per
// entry), and at thread start and at Setaffinity each guest CPU i (0-12) becomes one host logical CPU: guest CPUs 2k and
// 2k+1 are the two SMT threads of host core k (TODO(verify): the console's CPU numbering; host siblings from
// /sys/devices/system/cpu/cpu<k>/topology/thread_siblings_list). Guest CPUs 0-12 use host cores 0-6 and the first
// thread of core 6; the rest of the host's CPUs carry no title thread unless the title asks. A mask with no bit in 0-12
// is left alone. KYTY_BC5_0429_TRACE=1 (normal build) logs each guest thread's mask, priority and nice at start,
// Setaffinity and Setprio (the first 400 lines) and the CPU map once.
static int Bc5Cpu13() {
	static const int v = [] {
		const bool on = bc5::env_rule::on(std::getenv("KYTY_BC5_0429_CPU13"));
#ifndef BC5_LEAN
		std::fprintf(stderr, "[bc5] exp 0429: 13-CPU model %s\\n", on ? "ON" : "off");
#endif
		return on ? 1 : 0;
	}();
	return v;
}

static bool Bc5AffinityTrace() {
#ifndef BC5_LEAN
	static const bool v = bc5::env_rule::on(std::getenv("KYTY_BC5_0429_TRACE"));
	return v;
#else
	return false;
#endif
}

struct Bc5CpuMap {
	int host[13];
};

static const Bc5CpuMap& Bc5Map() {
	static const Bc5CpuMap v = [] {
		Bc5CpuMap m {};
		for (int k = 0; k < 7; k++) {
			int  sib[2] = {k, k};
			int  n      = 0;
			char path[96];
			std::snprintf(path, sizeof(path), "/sys/devices/system/cpu/cpu%d/topology/thread_siblings_list", k);
			FILE* f = std::fopen(path, "r");
			if (f != nullptr) {
				char line[128] = {};
				if (std::fgets(line, sizeof(line), f) != nullptr) {
					const char* p = line;
					while (*p >= '0' && *p <= '9' && n < 2) { // "a,b" or "a-b"
						char*      end = nullptr;
						const long a   = std::strtol(p, &end, 10);
						long       b   = a;
						p              = end;
						if (*p == '-') {
							b = std::strtol(p + 1, &end, 10);
							p = end;
						}
						for (long c = a; c <= b && n < 2; c++) {
							sib[n++] = static_cast<int>(c);
						}
						if (*p == ',') {
							p++;
						}
					}
				}
				std::fclose(f);
			}
			if (n < 2) {
				sib[1] = sib[0]; // no sibling known: both guest CPUs on the one host CPU
			}
			m.host[2 * k] = sib[0];
			if (2 * k + 1 < 13) {
				m.host[2 * k + 1] = sib[1];
			}
		}
#ifndef BC5_LEAN
		if (Bc5AffinityTrace()) {
			std::fprintf(stderr, "[bc5] exp 0429 cpu map (guest:host):");
			for (int i = 0; i < 13; i++) {
				std::fprintf(stderr, " %d:%d", i, m.host[i]);
			}
			std::fprintf(stderr, "\\n");
		}
#endif
		return m;
	}();
	return v;
}

static void Bc5ApplyAffinity(Pthread thread, const char* why) {
	if (thread == nullptr || thread->attr == nullptr || thread->host_thread_id == 0) {
		return;
	}
	const uint64_t mask = thread->attr->affinity;
	int            rc   = -1; // not applied
	if (Bc5Cpu13() != 0 && (mask & 0x1fffu) != 0) {
		cpu_set_t set;
		CPU_ZERO(&set);
		for (int i = 0; i < 13; i++) {
			if (((mask >> i) & 1u) != 0) {
				CPU_SET(Bc5Map().host[i], &set);
			}
		}
		rc = sched_setaffinity(static_cast<pid_t>(thread->host_thread_id), sizeof(set), &set) == 0 ? 0 : errno;
	}
#ifndef BC5_LEAN
	if (Bc5AffinityTrace()) {
		static std::atomic<int> logged {0};
		if (logged.fetch_add(1, std::memory_order_relaxed) < 400) {
			std::fprintf(stderr, "[bc5] exp 0429 thread: %s tid %d '%s' prio %d nice %d mask 0x%llx applied %s\\n", why,
			             static_cast<int>(thread->host_thread_id), thread->name.c_str(), thread->attr->guest_priority,
			             Bc5GuestNice(thread->attr->guest_priority), static_cast<unsigned long long>(mask),
			             rc == -1 ? "no" : rc == 0 ? "yes" : "FAILED");
		}
	}
#else
	(void)why;
	(void)rc;
#endif
}
// ---- end of experiment 0429 affinity -------------------------------------------------------------------------------
'''


def pthread(path):
    raw, crlf, text = load(path)
    if hashlib.sha256(raw).hexdigest() != PINS['src/kernel/pthread.cpp']:
        stop('%s is not its pin' % path)
    lines = text.split('\n')
    s = idx(lines, 'static int Bc5GuestNice(int guest_priority) {', 'Bc5GuestNice')
    e = close_of(lines, s, 'Bc5GuestNice')
    lines[s:e + 1] = PRIO_FN.split('\n')
    text = '\n'.join(lines)
    text = one(text, 'KYTY_BC5_0425_WAKE_SLICE_US=0 turns it off. Exp 0425: with JobArenaFix off, the\n',
               'KYTY_BC5_0425_WAKE_SLICE_US=0 turns it off. Exp 0425: the\n', 'pthread comment')
    end_c1 = '// ---- end of experiment 0425 C1 ------------------------------------------------------------------------------------\n'
    text = one(text, end_c1, end_c1 + AFF_BLOCK, 'pthread after C1')
    text = one(text, '\t(*attr)->affinity       = 0x7f;\n',
               '\t(*attr)->affinity       = Bc5Cpu13() != 0 ? 0x1fff : 0x7f; // experiment 0429: the title\'s 13-CPU model\n',
               'pthread attr init')
    text = one(text, 'int KYTY_SYSV_ABI PthreadAttrInit(PthreadAttr* attr) {\n',
               'static int Bc5Cpu13(); // experiment 0429, defined with its affinity block\n\nint KYTY_SYSV_ABI PthreadAttrInit(PthreadAttr* attr) {\n',
               'pthread forward')
    text = one(text, '\tBc5ApplyGuestPriority(thread, "start");\n#endif\n',
               '\tBc5ApplyGuestPriority(thread, "start");\n\tBc5ApplyAffinity(thread, "start"); // experiment 0429\n#endif\n',
               'pthread start')
    text = one(text, '''	auto result = PthreadAttrSetaffinity(&thread->attr, mask);

	return result;
}''', '''	auto result = PthreadAttrSetaffinity(&thread->attr, mask);
#if KYTY_PLATFORM == KYTY_PLATFORM_LINUX
	if (result == OK) {
		Bc5ApplyAffinity(thread, "setaffinity"); // experiment 0429
	}
#endif

	return result;
}''', 'pthread setaffinity')
    text = one(text, '\tBc5ApplyGuestPriority(thread, "setprio");\n#endif\n',
               '\tBc5ApplyGuestPriority(thread, "setprio");\n\tif (Bc5AffinityTrace()) {\n\t\tBc5ApplyAffinity(thread, "setprio"); // experiment 0429: the trace line; the mask is unchanged\n\t}\n#endif\n',
               'pthread setprio')
    if 'JobArenaFix' in text or 'job_arena' in text.lower():
        stop('pthread.cpp still names the workaround')
    save(path, text, crlf)


def semaphore(path):
    raw, crlf, text = load(path)
    if hashlib.sha256(raw).hexdigest() != PINS['src/kernel/semaphore.cpp']:
        stop('%s is not its pin' % path)
    for old, new in patch0425.SEMA:
        text = one(text, old, new, 'semaphore (exp 0425)')
    save(path, text, crlf)


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    t = sys.argv[1].rstrip('/') + '/'
    edit_lines(t + 'src/loader/gamePatch.cpp', gp_cpp)
    edit_lines(t + 'src/loader/gamePatch.h', gp_h)
    edit_lines(t + 'src/loader/runtimeLinker.cpp', rl_cpp)
    edit_lines(t + 'src/graphics/presentation/hostMenu.cpp', menu_cpp)
    edit_lines(t + 'src/graphics/presentation/window/hostInput.cpp', input_cpp)
    edit_lines(t + 'src/graphics/presentation/window/hostInput.h', input_h)
    os.remove(t + 'src/bc5/job_arena_fix.hpp')
    print('mk0429: removed src/bc5/job_arena_fix.hpp')
    pthread(t + 'src/kernel/pthread.cpp')
    semaphore(t + 'src/kernel/semaphore.cpp')
    print('mk0429: done')


if __name__ == '__main__':
    main()
