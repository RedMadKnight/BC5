#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""BC5 experiment 0438 (tag bake438b): q438/test_q438.cpp for a gate-only unit (no Q438, no labelmap), as a copy.
Usage: python -I gatecpp438b.py IN_test_q438.cpp OUT.cpp
With -DQ438_GATE (and -DQ438_X) the copy includes the gate unit's q_ng.inc (tag q438ng: acb_wait_unready, ng438) where
test_q438.cpp includes mkq438x.py's labelmap + q438ng pieces, and its q_w.inc (tag ng438w: inflight_ng_writer,
open_ng_writer, wd438) before ho430; the labelmap parts of the stub filter and the labelmap det cases (they need Q438) are
left out. Everything else, the inflight and rings modes among it, is test_q438.cpp's own text. Each edit matches once.
"""
import sys

IN, OUT = sys.argv[1], sys.argv[2]
s = open(IN, 'rb').read().decode('utf-8')
assert '\r' not in s


def rep(old, new):
    global s
    n = s.count(old)
    assert n == 1, f'{n} matches for {old[:80]!r}'
    s = s.replace(old, new)


rep('#ifdef Q438_X\n#include "q_cov.inc"\n#include "q_lwm.inc"\n#include "q_ng.inc"\n#endif\n',
    '#if defined(Q438_GATE) // bake438b: the gate-only unit\n#include "q_ng.inc"\n#elif defined(Q438_X)\n#include "q_cov.inc"\n#include "q_lwm.inc"\n#include "q_ng.inc"\n#endif\n')
rep('#include "q_ho.inc" // ho430, cut from every unit\n',
    '#ifdef Q438_GATE // bake438b: the gate\'s writer tests and wd438 (tag ng438w)\n#include "q_w.inc"\n#endif\n#include "q_ho.inc" // ho430, cut from every unit\n')
rep('#ifdef Q438_X\n\tif (g_dev) { // the filter',
    '#if defined(Q438_X) && !defined(Q438_GATE)\n\tif (g_dev) { // the filter')
rep('#ifdef Q438_X\n// ---- labelmap and q438ng (mkq438x.py)',
    '#if defined(Q438_X) && !defined(Q438_GATE)\n// ---- labelmap and q438ng (mkq438x.py)')
open(OUT, 'wb').write(s.encode('utf-8'))
