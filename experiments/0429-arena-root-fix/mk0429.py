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
   - KYTY_BC5_0429_GUEST_CPUS=1 (pthread.cpp, affinity0429.cpp): the title's own CPU requests on this host, for any
     title, all derived at run time: the host CPU list in SMT sibling order from /sys, the default mask one guest CPU
     per host CPU, and every guest mask applied with guest CPU i -> the i-th host CPU of the list (exp 0429's third
     build; the first build's AFFINITY and the second's CPU13, a fixed 13-CPU model, are gone);
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

AFF_BLOCK = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'affinity0429.cpp'), encoding='utf-8').read()


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
               '\t(*attr)->affinity       = Bc5GuestDefaultMask(); // experiment 0429: one guest CPU per host CPU when mapping\n',
               'pthread attr init')
    text = one(text, 'int KYTY_SYSV_ABI PthreadAttrInit(PthreadAttr* attr) {\n',
               'static uint64_t Bc5GuestDefaultMask(); // experiment 0429, defined with its guest CPU block\n\nint KYTY_SYSV_ABI PthreadAttrInit(PthreadAttr* attr) {\n',
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
