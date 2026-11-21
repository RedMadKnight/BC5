#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""BC5 experiment 0438 (tag stack438): Q438 stacked on A2's host change on the SHARED unit since 2026-11-21 14:54 (r438o,
2e6168de). Usage: python -I mkstack438.py MKQ438.py IN.cpp OUT.cpp
  MKQ438.py: q438/mkq438.py (md5 618fadba...), run here with two of its steps taken out:
    E2b (queued chains' early writes renumbered after a later real write) and E9 (the g_plw trim keeps early entries):
    r438o already does both for r438's entries (F874, F875), so they are merged into r438o's code instead of added
    beside it:
      - the renumbering runs when (r438 on and early entries in the table) or Q438 on, and excludes the registering
        thread's own early entries of either kind (t_r438_own, t_q438_early);
      - the trim keeps early entries when r438 or Q438 is on.
  IN.cpp: a2/mka2host.py --any on r438o/r438o.cpp (2e6168de), md5 pinned below.
Every replacement must match exactly once, or nothing is written.
"""
import hashlib
import sys

MKQ, IN, OUT = sys.argv[1:4]
code = open(MKQ, 'rb').read()
assert hashlib.md5(code).hexdigest() == '618fadbacaa1ee4582a73c4c8cc73a85', 'mkq438.py is not the tested one (618fadba)'
code = code.decode('utf-8')
A2R = open(IN, 'rb').read()
A2R_MD5 = hashlib.md5(A2R).hexdigest()


def cut(c, a, b, what):
    i, j = c.index(a), c.index(b)
    assert c.count(a) == 1 and c.count(b) == 1 and i < j, what
    return c[:i] + c[j:]


code = cut(code, '# E2b: ring order.', '# E9: g_plw', 'E2b')
code = cut(code, '# E9: g_plw', '# E3\n', 'E9')
k = code.index("INPUTS = {")
e = code.index('\n', k)
code = code[:k] + 'INPUTS = {' + repr(A2R_MD5) + ': "A2\'s host change on the shared r438o unit (2e6168de)"}' + code[e:]
tail = "out = s.encode('utf-8')"
assert code.count(tail) == 1
code = code.replace(tail, 'COMBINED()\n' + tail)


def COMBINED():
    s = ns['s']

    def rep(old, new):
        nonlocal s
        n = s.count(old)
        assert n == 1, (n, old[:120])
        s = s.replace(old, new)

    rep("\tif (r438_on() && g_r438o_live != 0) { // exp 0438 (r438o): a taken slice's early writes are not in the kernel yet: they stay after this real write of their label\n",
        "\tif ((r438_on() && g_r438o_live != 0) || q438_on()) { // exp 0438 (r438o; q438 stack438): early writes (a taken slice's, a queued chain's) are not in the kernel yet: they stay after this real write of their label\n")
    rep('\t\t\tif ((w.seq & kR438Early) != 0 && w.seq != t_r438_own && std::any_of(',
        '\t\t\tif ((w.seq & kR438Early) != 0 && w.seq != t_r438_own && w.seq != t_q438_early && std::any_of(')
    rep('\tif (!r438_on()) {\n\t\tg_plw.erase(g_plw.begin(), g_plw.begin() + 4096);\n',
        '\tif (!r438_on() && !q438_on()) { // exp 0438 (stack438): early entries kept when r438 or Q438 is on\n\t\tg_plw.erase(g_plw.begin(), g_plw.begin() + 4096);\n')
    rep('\tq438_plw_trim_locked();\n\tif (g_plw.size() > 8192) g_plw.erase(g_plw.begin(), g_plw.begin() + 4096);\n\tg_plw.insert(g_plw.end(), found.begin(), found.end());\n\treturn id;\n',
        '\tr438o_trim_locked(); // exp 0438 (stack438): the queued chain\'s early registration, r438o\'s trim\n\tg_plw.insert(g_plw.end(), found.begin(), found.end());\n\treturn id;\n')
    for w in ('q438_plw_trim_locked', 'g_q438_trims'):
        assert w not in s, w
    ns['s'] = s


ns = {'__name__': 'mkq438_stack438', 'COMBINED': lambda: COMBINED()}
saved = sys.argv
sys.argv = [MKQ, IN, OUT]
try:
    exec(compile(code, MKQ, 'exec'), ns)
finally:
    sys.argv = saved
