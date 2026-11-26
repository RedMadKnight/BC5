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

# E3 (tag r438o, 2026-11-21): the trim of g_plw keeps early entries with r438 on. Today both trims (register_label_writes
# and r438_begin) erase the oldest 4096 entries by position once the table passes 8192, early ones included; a dropped
# early write makes a game-thread wait read "no pending write" (the give-up path) and its slice's end flags nothing.
# Bound: an early entry lives only from its slice's r438_begin to its r438_end (which erases all of them), so the table
# holds at most 8192 real entries plus one call's batch plus the early writes of the slices in flight.
# E4: counters for the normal build only (renumbered early entries, early entries kept by a trim, trims), in r438's
# 60-s journal line.
rep('static std::atomic<uint64_t> g_r438_early {0}, g_r438_lost {0}, g_r438_waits {0}, g_r438_wait_ns {0}, g_r438_wait_max {0}, g_r438_long {0};\n#endif\n',
    'static std::atomic<uint64_t> g_r438_early {0}, g_r438_lost {0}, g_r438_waits {0}, g_r438_wait_ns {0}, g_r438_wait_max {0}, g_r438_long {0};\n'
    'static std::atomic<uint64_t> g_r438o_renum {0}, g_r438o_kept {0}, g_r438o_trims {0}; // exp 0438 (r438o)\n#endif\n')
rep('static std::condition_variable             g_plw_cv; // exp 0438 (b438, PLWCV): real writes registered or early ones gone\n',
    '// exp 0438 (r438o): the trim of g_plw (over 8192 entries the oldest 4096 go). With r438 on, early entries are kept: they are\n'
    '// not in the kernel yet, and a dropped one reads as "no pending write". Bound: an early entry lives only from the r438_begin\n'
    '// to the r438_end of its slice, so the table holds at most 8192 real entries, one batch and the slices in flight.\n'
    'static void r438o_trim_locked() {\n'
    '\tif (g_plw.size() <= 8192) return;\n'
    '\tif (!r438_on()) {\n'
    '\t\tg_plw.erase(g_plw.begin(), g_plw.begin() + 4096);\n'
    '\t\treturn;\n'
    '\t}\n'
    '\tsize_t dropped = 0, kept = 0;\n'
    '\tauto   out     = g_plw.begin();\n'
    '\tfor (auto it = g_plw.begin(); it != g_plw.end(); ++it) {\n'
    '\t\tconst bool early = (it->seq & kR438Early) != 0;\n'
    '\t\tif (!early && dropped < 4096) {\n'
    '\t\t\tdropped++;\n'
    '\t\t\tcontinue;\n'
    '\t\t}\n'
    '\t\tif (early && dropped < 4096) kept++;\n'
    '\t\t*out++ = *it;\n'
    '\t}\n'
    '\tg_plw.erase(out, g_plw.end());\n'
    '#ifndef BC5_LEAN\n'
    '\tg_r438o_trims++;\n'
    '\tg_r438o_kept += kept;\n'
    '#endif\n'
    '}\n'
    'static std::condition_variable             g_plw_cv; // exp 0438 (b438, PLWCV): real writes registered or early ones gone\n')
rep('\t\tw.order = ++order;\n\t}\n\tif (g_plw.size() > 8192) g_plw.erase(g_plw.begin(), g_plw.begin() + 4096);\n',
    '\t\tw.order = ++order;\n\t}\n\tr438o_trim_locked(); // exp 0438 (r438o): early entries kept with r438 on\n')
rep('\t\tw.order = ++g_plw_order;\n\t}\n\tif (g_plw.size() > 8192) g_plw.erase(g_plw.begin(), g_plw.begin() + 4096);\n',
    '\t\tw.order = ++g_plw_order;\n\t}\n\tr438o_trim_locked(); // exp 0438 (r438o): early entries kept with r438 on\n')
rep('\t\tfor (PendingLabelWrite* w: early) w->order = ++order;\n',
    '\t\tfor (PendingLabelWrite* w: early) w->order = ++order;\n#ifndef BC5_LEAN\n\t\tg_r438o_renum += early.size();\n#endif\n')
rep('bug lines (over 100 ms) %" PRIu64 "\\n",',
    'bug lines (over 100 ms) %" PRIu64 "; r438o: early entries renumbered %" PRIu64 ", kept by the trim %" PRIu64 " in %" PRIu64 " trims\\n",')
rep('g_r438_long.load());', 'g_r438_long.load(), g_r438o_renum.load(), g_r438o_kept.load(), g_r438o_trims.load());')
# E5 (2026-11-21, after the lean A/B q438oA: r438o lean 58.9-59.2 flips/s against the control's 59.3-59.7, p99 33 ms in
# all three runs; the first title took no r438 slice): the renumbering scanned the whole g_plw on every register_label_writes
# under g_plw_mutex, with no early entry to renumber. g_r438o_live counts the early entries in g_plw (under
# g_plw_mutex): r438_begin adds its batch, r438_end subtracts what it erases, forget_label_writes(all) clears the table and
# the count; r438o's trim keeps early entries. The scan runs only while the count is not 0.
rep('static uint64_t                           g_plw_order = 0;          // under g_plw_mutex, shared with register_label_writes\n',
    'static uint64_t                           g_plw_order = 0;          // under g_plw_mutex, shared with register_label_writes\n'
    'static uint64_t                           g_r438o_live = 0;         // exp 0438 (r438o): early entries in g_plw, under g_plw_mutex\n')
rep("\tif (r438_on()) { // exp 0438 (r438o): a taken slice's early writes are not in the kernel yet: they stay after this real write of their label\n",
    "\tif (r438_on() && g_r438o_live != 0) { // exp 0438 (r438o): a taken slice's early writes are not in the kernel yet: they stay after this real write of their label\n")
rep('\t\tw.order = ++g_plw_order;\n\t}\n\tr438o_trim_locked(); // exp 0438 (r438o): early entries kept with r438 on\n\tg_plw.insert(g_plw.end(), found.begin(), found.end());\n',
    '\t\tw.order = ++g_plw_order;\n\t}\n\tr438o_trim_locked(); // exp 0438 (r438o): early entries kept with r438 on\n\tg_plw.insert(g_plw.end(), found.begin(), found.end());\n\tg_r438o_live += found.size(); // exp 0438 (r438o)\n')
rep('\t\t\t\tit = g_plw.erase(it);\n\t\t\t} else {\n\t\t\t\t++it;\n\t\t\t}\n\t\t}\n\t}\n',
    '\t\t\t\tit = g_plw.erase(it);\n\t\t\t\tif (g_r438o_live != 0) g_r438o_live--; // exp 0438 (r438o)\n\t\t\t} else {\n\t\t\t\t++it;\n\t\t\t}\n\t\t}\n\t}\n')
rep('\tif (all) {\n\t\tg_plw.clear();\n\t\treturn;\n\t}\n',
    '\tif (all) {\n\t\tg_plw.clear();\n\t\tg_r438o_live = 0; // exp 0438 (r438o)\n\t\treturn;\n\t}\n')

out = s.encode('utf-8')
open(OUT, 'wb').write(out)
print('IN ', hashlib.md5(src).hexdigest(), IN)
print('OUT', hashlib.md5(out).hexdigest(), OUT, f'({s.count(chr(10))} lines)')
