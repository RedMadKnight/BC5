#!/usr/bin/env python3
"""BC5 exp 0429, the shared swap's edits: the removal of exp 0359's job-arena workaround (JobArenaFix), nothing else.
    mkswap0429.py <tree root>
The maintainer, 2026-11-16, through the top session: "JobArenaFix ma zniknac z menu, z przelacznikow i wszystkich
miejsc". On the shared tree at patch 9e7c4514 (exp 0431). In both builds, with no switch:
   - src/loader/gamePatch.cpp and .h: the hook, ApplyJobArenaFix and their includes (both back to f266548's text);
   - src/loader/runtimeLinker.cpp: the call at Execute, the switch's extern and bc5_tls_main_tcb (used only by the hook);
   - src/graphics/presentation/hostMenu.cpp: the "Game fixes" submenu (it held only this item);
   - src/graphics/presentation/window/hostInput.cpp and .h: the input.cfg key, its member and accessors, and
     KYTY_BC5_JOB_ARENA_FIX. An old "JobArenaFix.<TITLE_ID>=..." line is accepted silently and not written back;
   - src/bc5/job_arena_fix.hpp: deleted;
   - the one comment in pthread.cpp that named it.
None of exp 0429's candidates or catchers goes in. Every anchor must occur once; line endings are kept. Each unit is
checked against its pin first, and nothing is written unless all edits succeed."""
import hashlib
import os
import sys

# md5 (first 8) of the units at patch 9e7c4514, read 2026-11-17 from a tree of f266548 + 9e7c4514
PINS = {}  # filled by the --pins run; checked when not empty
PINS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pins-swap0429.txt')
UNITS = ['src/loader/gamePatch.cpp', 'src/loader/gamePatch.h', 'src/loader/runtimeLinker.cpp',
         'src/graphics/presentation/hostMenu.cpp', 'src/graphics/presentation/window/hostInput.cpp',
         'src/graphics/presentation/window/hostInput.h', 'src/kernel/pthread.cpp', 'src/bc5/job_arena_fix.hpp']


def stop(msg):
    sys.exit('mkswap0429 STOP: ' + msg)


def idx(lines, needle, what):
    hits = [i for i, l in enumerate(lines) if needle in l]
    if len(hits) != 1:
        stop('%s: "%s" on %d lines' % (what, needle, len(hits)))
    return hits[0]


def close_of(lines, i, what):
    ind = lines[i][:len(lines[i]) - len(lines[i].lstrip())]
    for k in range(i + 1, len(lines)):
        if lines[k] == ind + '}':
            return k
    stop('%s: no closing brace' % what)


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


def pthread_cpp(lines):
    old = 'KYTY_BC5_0425_WAKE_SLICE_US=0 turns it off. Exp 0425: with JobArenaFix off, the'
    i = idx(lines, old, 'pthread comment')
    lines[i] = lines[i].replace(old, 'KYTY_BC5_0425_WAKE_SLICE_US=0 turns it off. Exp 0425: the')
    return lines


EDITS = [
    ('src/loader/gamePatch.cpp', gp_cpp),
    ('src/loader/gamePatch.h', gp_h),
    ('src/loader/runtimeLinker.cpp', rl_cpp),
    ('src/graphics/presentation/hostMenu.cpp', menu_cpp),
    ('src/graphics/presentation/window/hostInput.cpp', input_cpp),
    ('src/graphics/presentation/window/hostInput.h', input_h),
    ('src/kernel/pthread.cpp', pthread_cpp),
]


def m8(b):
    return hashlib.md5(b).hexdigest()[:8]


def main():
    args = sys.argv[1:]
    if len(args) == 2 and args[0] == '--pins':
        t = args[1].rstrip('/') + '/'
        with open(PINS_FILE, 'w', newline='\n') as f:
            for u in UNITS:
                f.write('%s %s\n' % (m8(open(t + u, 'rb').read()), u))
        print('mkswap0429: pins written to', PINS_FILE)
        return
    if len(args) != 1:
        sys.exit(__doc__)
    t = args[0].rstrip('/') + '/'
    pins = {}
    for line in open(PINS_FILE, encoding='utf-8'):
        h, u = line.split()
        pins[u] = h
    for u in UNITS:
        if not os.path.exists(t + u):
            stop('%s is missing' % u)
        got = m8(open(t + u, 'rb').read())
        if got != pins.get(u):
            stop('%s is %s, not its pin %s' % (u, got, pins.get(u)))
    out = {}
    for u, fn in EDITS:
        raw = open(t + u, 'rb').read()
        crlf = b'\r\n' in raw
        lines = fn(raw.decode('utf-8').replace('\r\n', '\n').split('\n'))
        text = '\n'.join(lines)
        if 'JobArenaFix' in text.replace('"JobArenaFix."', '') or 'job_arena' in text.lower() or 'Game fixes' in text:
            stop('%s still names the workaround' % u)
        out[u] = (text.replace('\n', '\r\n') if crlf else text).encode('utf-8')
    for u, b in out.items():  # all edits succeeded: write
        open(t + u, 'wb').write(b)
        print('mkswap0429: %s %s -> %s' % (u, pins[u], m8(b)))
    os.remove(t + 'src/bc5/job_arena_fix.hpp')
    print('mkswap0429: removed src/bc5/job_arena_fix.hpp; done')


if __name__ == '__main__':
    main()
