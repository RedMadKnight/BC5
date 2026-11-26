#!/usr/bin/env python3
# BC5 exp 0438's two items "for the next bake", as exact edits for exp 0439's bake 2 (on top of exp 0442's bake 1).
# Both worlds (they are not part of exp 0444's switch). Every anchor must appear exactly once, or nothing is written.
#   r438h   r438_begin registers nothing early in sync mode (any BC5_DIRECT_JOURNAL other than "min": g_async false).
#           submit_now then waits for each job and registers no pending write, so every early entry ended as r438's
#           "never reached the ring" BUG line (F884), and a game-thread wait on its label waited for a writer that was
#           never registered. Det case `sync` (exp 0438 r438o/mkr438h.py, written on unit 2e6168de). No change with the
#           journal at "min", which every play launcher sets.
#   kept438 r438o_trim_locked's `kept` is set but not used in lean (its counter is compiled out): (void)kept there.
# Usage: python mkb2_0438.py IN.cpp OUT.cpp   (checked on the shared unit 589ef163, ed489aca; bake 1's 3b28b024 by
# exp 0439's kit: the anchors are r438 code that bake 1 does not touch)
import hashlib, sys

src, dst = sys.argv[1], sys.argv[2]
s = open(src, 'rb').read().decode('utf-8', 'surrogateescape')
assert '\r' not in s
T = '\t'


def rep(tag, old, new):
    global s
    n = s.count(old)
    assert n == 1, '%s: anchor found %d times' % (tag, n)
    s = s.replace(old, new)


assert 'exp 0438 (r438h)' not in s, 'already has r438h'
rep('r438h',
    'static void r438_begin(const uint32_t* s1, uint32_t n1, const uint32_t* s2, uint32_t n2) {\n' + T + 'if (!r438_on()) return;\n',
    'static void r438_begin(const uint32_t* s1, uint32_t n1, const uint32_t* s2, uint32_t n2) {\n' + T +
    'if (!r438_on() || !g_async) return; // exp 0438 (r438h): sync mode registers no pending write, so nothing early\n')
rep('kept438',
    '#ifndef BC5_LEAN\n' + T + 'g_r438o_trims++;\n' + T + 'g_r438o_kept += kept;\n#endif\n',
    '#ifndef BC5_LEAN\n' + T + 'g_r438o_trims++;\n' + T + 'g_r438o_kept += kept;\n#else\n' + T +
    '(void)kept; // exp 0438 (kept438): its counter is compiled out in lean\n#endif\n')
b = s.encode('utf-8', 'surrogateescape')
open(dst, 'wb').write(b)
print('mkb2_0438: wrote', dst, hashlib.md5(b).hexdigest()[:8], 'from', hashlib.md5(open(src, 'rb').read()).hexdigest()[:8])
