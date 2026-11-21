#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""BC5 experiment 0438 (tag r438h): r438 registers nothing early in sync mode.
Usage: python -I mkr438h.py IN.cpp OUT.cpp   (IN: the shared unit r438o/r438o.cpp, md5 2e6168de7774de436fe7e916c895180a)
The defect (exp 0439's third title, full journal: 1,281 "early-registered write ... never reached the ring" lines in 58 s;
0 with BC5_DIRECT_JOURNAL=min): submission is asynchronous only with the journal at "min" (g_async = g_journal_min). In
sync mode submit_now waits for each job and registers no pending write: register_label_writes runs only for a pending job
(the `if (r.pending)` branch). So every early entry r438_begin made for a slice with label writes ended as a BUG line at
r438_end, and until then a game-thread wait on its label waited for a writer that would never be registered.
The change, inside the existing BC5_0438_EARLYREG path: r438_begin returns at once when !g_async (r438_end then finds no
slice). Async mode is unchanged.
Exact-once replacement; writes OUT (LF) and prints both md5s.
"""
import hashlib
import sys

IN, OUT = sys.argv[1], sys.argv[2]
src = open(IN, 'rb').read()
assert hashlib.md5(src).hexdigest() == '2e6168de7774de436fe7e916c895180a', 'not the shared unit r438o.cpp (2e6168de)'
s = src.decode('utf-8')
assert '\r' not in s
old = 'static void r438_begin(const uint32_t* s1, uint32_t n1, const uint32_t* s2, uint32_t n2) {\n\tif (!r438_on()) return;\n'
new = ('static void r438_begin(const uint32_t* s1, uint32_t n1, const uint32_t* s2, uint32_t n2) {\n'
       '\tif (!r438_on() || !g_async) return; // exp 0438 (r438h): sync mode registers no pending write, so nothing early\n')
assert s.count(old) == 1, s.count(old)
s = s.replace(old, new)
out = s.encode('utf-8')
open(OUT, 'wb').write(out)
print('IN ', hashlib.md5(src).hexdigest(), IN)
print('OUT', hashlib.md5(out).hexdigest(), OUT, f'({s.count(chr(10))} lines)')
