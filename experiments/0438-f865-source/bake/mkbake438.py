#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""BC5 exp 0438, the bake unit: r438 with PLWCV, the shape the lean round tested (result 13), without p438.
Usage: python -I mkbake438.py MKB438.py IN.cpp OUT.cpp
  MKB438.py: exp 0438's mkb438.py (md5 3b00ab29...), run here for its steps 1-6 only (r438's registration, the slice's
             end, PLWCV, F2/F4, ring_will_satisfy, the slice hooks); its step 7 (p438, the prologue merge) is not run:
             the top session did not propose it (no performance case, result 13).
  IN.cpp:    patch bb04219b's src/libs/bc5LleAgc.cpp (a62e8bf6...).
Kept, as tested: BC5_0438_EARLYREG and BC5_0438_PLWCV, both on unless "0" (the top session, 2026-11-20: the switches
stay for a per-run opt-out), read in normal and lean; normal's r438 count line every 60 s and its BUG lines.
Removed: the lean build's lost-write counter and its two stderr lines (a catcher; the lean build carries no
diagnostics, the maintainer's rule of 2026-11-15). Lean keeps the behaviour: the registration, the wait and the removal
of a lost write's early entry.
Every replacement must match exactly once, or nothing is written.
"""
import hashlib
import sys

MKB, IN, OUT = sys.argv[1:4]
code = open(MKB, 'rb').read()
assert hashlib.md5(code).hexdigest() == '3b00ab29cec22374354e0d2a4fb01c08', 'mkb438.py is not the tested one'
code = code.decode('utf-8')
a, b = code.index('# 7. p438'), code.index('out = s.encode')
assert code.count('# 7. p438') == 1 and code.count('out = s.encode') == 1 and a < b
ns = {'__name__': 'mkb438_steps_1_6'}
saved = sys.argv
sys.argv = [MKB, IN, OUT]
try:
    exec(compile(code[:a], MKB, 'exec'), ns)  # steps 1-6; nothing is written
finally:
    sys.argv = saved
s = ns['s']
NL = chr(92) + 'n'


def rep(old, new):
    global s
    n = s.count(old)
    assert n == 1, (n, old[:120])
    s = s.replace(old, new)


rep('''#ifdef BC5_LEAN
static std::atomic<uint64_t> g_r438_lost_lean {0}; // exp 0438 (b438): lean's one counter, printed at a normal exit
struct R438LeanExit {
	~R438LeanExit() {
		if (r438_on()) std::fprintf(stderr, "r438 (exp 0438, b438, lean): early writes that never reached the ring %" PRIu64 "NL", g_r438_lost_lean.load());
	}
};
static R438LeanExit g_r438_lean_exit;
#endif
'''.replace('NL', NL), '')
rep('''#else
	if (!lost.empty() && g_r438_lost_lean.fetch_add(lost.size()) == 0)
		std::fprintf(stderr, "r438 (exp 0438, b438, lean): an early-registered write never reached the ring (the first; the total is printed at a normal exit)NL");
#endif
	if (r438_cv())'''.replace('NL', NL), '''#endif
	if (r438_cv())''')
for w in ('p438', 'PROLMERGE', 'g_r438_lost_lean', 'b438, lean'):
    assert w not in s, w
for w in ('BC5_0438_EARLYREG', 'BC5_0438_PLWCV', 'r438 (exp 0438, b438): t '):
    assert w in s, w
out = s.encode('utf-8')
open(OUT, 'wb').write(out)
print('mkbake438:', hashlib.md5(out).hexdigest())
