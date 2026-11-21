#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""BC5 experiment 0438 (tag r438o): r438's early writes keep their ring order in g_plw.
Usage: python -I mkr438o.py IN.cpp OUT.cpp   (IN: the bake unit, md5 ff9e8fe2e4139264ebaf74f9e84bd892)
The hole (test_r438o.sh order on the bake unit): bc5-ring's r438_begin registers a taken slice's label writes early
(g_plw order N). Before the slice's own job registers them for real, another thread's job (the Render Thread's or the
chain watchdog's submit_now) can register a real write of the same label, with order N+1. ring_will_satisfy takes the
highest order as the last write, so a game-thread wait on the slice's value is answered from the other write while the
slice's writer is still to come.
The change, inside the existing r438 path (BC5_0438_EARLYREG on unless "0"; no other new behaviour):
  E1 t_r438_own: the slice's own early seq, set in r438_begin, cleared in r438_end;
  E2 register_label_writes renumbers the other early entries of the labels it registers after them, in their own order.
With BC5_0438_EARLYREG=0 r438_begin registers nothing and the renumbering is skipped: today's code path.
Writes OUT (LF) and prints both md5s.
"""
import hashlib
import sys

IN, OUT = sys.argv[1], sys.argv[2]
src = open(IN, 'rb').read()
assert hashlib.md5(src).hexdigest() == 'ff9e8fe2e4139264ebaf74f9e84bd892', 'not the bake unit (ff9e8fe2)'
s = src.decode('utf-8')
assert '\r' not in s


def rep(old, new):
    global s
    n = s.count(old)
    assert n == 1, f'{n} matches for: {old[:90]!r}'
    s = s.replace(old, new)


rep('static thread_local std::vector<uint64_t> t_r438_real;              // the labels the slice\'s jobs registered for real\n',
    'static thread_local std::vector<uint64_t> t_r438_real;              // the labels the slice\'s jobs registered for real\n'
    'static thread_local uint64_t              t_r438_own = 0;           // exp 0438 (r438o): the taken slice\'s own early seq (0: none)\n')
rep('\tt_r438_slice    = g_r438_slices.fetch_add(1) + 1;\n',
    '\tt_r438_slice    = g_r438_slices.fetch_add(1) + 1;\n'
    '\tt_r438_own      = kR438Early | t_r438_slice; // exp 0438 (r438o)\n')
rep('\tt_r438_on_slice = false;\n\tstd::vector<PendingLabelWrite> lost;\n',
    '\tt_r438_on_slice = false;\n\tt_r438_own      = 0; // exp 0438 (r438o)\n\tstd::vector<PendingLabelWrite> lost;\n')
rep('\tg_plw.insert(g_plw.end(), found.begin(), found.end());\n\tif (r438_cv()) g_plw_cv.notify_all(); // exp 0438 (b438, PLWCV)\n',
    '\tg_plw.insert(g_plw.end(), found.begin(), found.end());\n'
    '\tif (r438_on()) { // exp 0438 (r438o): a taken slice\'s early writes are not in the kernel yet: they stay after this real write of their label\n'
    '\t\tstd::vector<PendingLabelWrite*> early;\n'
    '\t\tfor (auto& w: g_plw)\n'
    '\t\t\tif ((w.seq & kR438Early) != 0 && w.seq != t_r438_own && std::any_of(found.begin(), found.end(), [&w](const PendingLabelWrite& f) { return f.label == w.label; })) early.push_back(&w);\n'
    '\t\tstd::sort(early.begin(), early.end(), [](const PendingLabelWrite* a, const PendingLabelWrite* b) { return a->order < b->order; });\n'
    '\t\tfor (PendingLabelWrite* w: early) w->order = ++order;\n'
    '\t}\n'
    '\tif (r438_cv()) g_plw_cv.notify_all(); // exp 0438 (b438, PLWCV)\n')

out = s.encode('utf-8')
open(OUT, 'wb').write(out)
print('IN ', hashlib.md5(src).hexdigest(), IN)
print('OUT', hashlib.md5(out).hexdigest(), OUT, f'({s.count(chr(10))} lines)')
