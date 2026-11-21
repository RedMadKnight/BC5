#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""BC5 experiment 0438 (tag a1c438): counters for A1 / A1P / the A1J journal, a 60-s stderr line, normal build only
(everything inside "#if !defined(BC5_LEAN)"). The top session's order of 2026-11-21: a quiet run proves nothing without
the numbers. Applied after mka1 -> mka1b -> mka1p.
Usage: mka1c.py IN.cpp OUT.cpp
- range edits by kind, counted in the VirtualRanges dispatcher before each mutating call (both modes, A1 on or off);
- A1P operations by table (physical, flexible, pooled), counted at each "if (m_a1p) {" map path;
- journal records written, in VirtualRangesJournal::Write;
- a printer thread started once by the VirtualRanges constructor prints, every 60 s:
  "[bc5] exp 0438 (tag a1c438): t <s> s: range edits add N remove N release N consume N span N rename N protect N
   memtype N; A1P map ops physical N flexible N pooled N; journal records N" (cumulative), so a run with no edits shows
  zeros instead of no line.
Every anchor must match the expected number of times.
"""
import hashlib
import re
import sys

IN, OUT = sys.argv[1], sys.argv[2]
src = open(IN, 'rb').read()
s = src.decode('utf-8')
assert '\r' not in s
KINDS = ['kAdd', 'kRemove', 'kReleaseReserved', 'kConsumeReserved', 'kConsumeReservedSpan', 'kRename', 'kProtect', 'kSetMemoryType']

# 1. the counters and the printer, before the journal class (inside its lean guard region: own guard)
anchor = '// exp 0438 A1b (tag a1b438): KYTY_BC5_0438_A1J=<file>'
assert s.count(anchor) == 1
COUNTERS = r'''// exp 0438 (tag a1c438): counters for A1 / A1P / the A1J journal, a 60-s stderr line (normal build only)
#if !defined(BC5_LEAN)
namespace a1c {
inline std::atomic<uint64_t> g_edit[8] {};
inline std::atomic<uint64_t> g_a1p[3] {}; // physical, flexible, pooled
inline std::atomic<uint64_t> g_journal {0};
inline void count_edit(int k) { g_edit[k].fetch_add(1, std::memory_order_relaxed); }
inline void count_a1p(int t) { g_a1p[t].fetch_add(1, std::memory_order_relaxed); }
#if !defined(KYTY_BC5_0438_A1C_PERIOD_S)
#define KYTY_BC5_0438_A1C_PERIOD_S 60
#endif
inline void print_line(double t) {
	std::fprintf(stderr,
	             "[bc5] exp 0438 (tag a1c438): t %.0f s: range edits add %llu remove %llu release %llu consume %llu span %llu rename %llu protect %llu memtype %llu; "
	             "A1P map ops physical %llu flexible %llu pooled %llu; journal records %llu\n",
	             t, (unsigned long long)g_edit[0].load(), (unsigned long long)g_edit[1].load(), (unsigned long long)g_edit[2].load(), (unsigned long long)g_edit[3].load(),
	             (unsigned long long)g_edit[4].load(), (unsigned long long)g_edit[5].load(), (unsigned long long)g_edit[6].load(), (unsigned long long)g_edit[7].load(),
	             (unsigned long long)g_a1p[0].load(), (unsigned long long)g_a1p[1].load(), (unsigned long long)g_a1p[2].load(), (unsigned long long)g_journal.load());
}
inline void start_printer() {
	static std::once_flag once;
	std::call_once(once, [] {
		std::thread([] {
			const auto t0 = std::chrono::steady_clock::now();
			for (;;) {
				std::this_thread::sleep_for(std::chrono::seconds(KYTY_BC5_0438_A1C_PERIOD_S));
				print_line(std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count());
			}
		}).detach();
	});
}
#if defined(BC5_0438_A1C_TEST) // the offline test only: one line at exit, t = -1
struct ExitLine { ~ExitLine() { print_line(-1); } };
inline ExitLine g_exit_line;
#endif
} // namespace a1c
#endif
'''
s = s.replace(anchor, COUNTERS + anchor)

# 2. journal records
a = '        m_buf.push_back(r);\n        if (m_buf.size() >= kBuffered) Flush();'
if s.count(a) != 1:
    a = '\t\tm_buf.push_back(r);\n\t\tif (m_buf.size() >= kBuffered) Flush();'
assert s.count(a) == 1, 'journal Write anchor'
s = s.replace(a, a.replace('m_buf.push_back(r);', 'm_buf.push_back(r);\n#if !defined(BC5_LEAN)\n        a1c::g_journal.fetch_add(1, std::memory_order_relaxed);\n#endif', 1))

# 3. range edits by kind: before each "if (m_journal != nullptr) {" of the dispatcher, the kind from its Write
pat = '#if !defined(BC5_LEAN)\n\t\tif (m_journal != nullptr) {'
n = s.count(pat)
assert n == 8, ('dispatcher journal blocks', n)
out, pos = [], 0
for _ in range(n):
    i = s.index(pat, pos)
    k = re.search(r'VirtualRangesJournal::(k[A-Za-z]+)', s[i:i + 600]).group(1)
    out.append(s[pos:i] + '#if !defined(BC5_LEAN)\n\t\ta1c::count_edit(' + str(KINDS.index(k)) + '); // exp 0438 (tag a1c438)\n\t\tif (m_journal != nullptr) {')
    pos = i + len(pat)
s = ''.join(out) + s[pos:]

# 4. the printer, from the VirtualRanges constructor
a = 'explicit VirtualRanges(const char* journal_path): m_a1(A1On()) {'
assert s.count(a) == 1, 'constructor'
s = s.replace(a, a + '\n#if !defined(BC5_LEAN)\n\t\ta1c::start_printer(); // exp 0438 (tag a1c438)\n#endif')

# 5. A1P map ops by table: each "if (m_a1p) {" line, the table from the nearest preceding method definition
lines = s.split('\n')
table, hits = None, [0, 0, 0]
for i, ln in enumerate(lines):
    m = re.match(r'^[A-Za-z_].*\b(PhysicalMemory|FlexibleMemory|PooledMemory)::[A-Za-z_]+\(', ln)
    if m:
        table = ['PhysicalMemory', 'FlexibleMemory', 'PooledMemory'].index(m.group(1))
    if re.match(r'^\tif \(m_a1p\) \{', ln) and table is not None:
        lines[i] = ln + '\n#if !defined(BC5_LEAN)\n\t\ta1c::count_a1p(' + str(table) + '); // exp 0438 (tag a1c438)\n#endif'
        hits[table] += 1
assert sum(hits) >= 20 and all(h > 0 for h in hits), ('A1P points', hits)
s = '\n'.join(lines)
for inc in ('<atomic>', '<thread>', '<chrono>', '<mutex>'):
    if '#include ' + inc not in s:
        s = '#include ' + inc + ' // exp 0438 (tag a1c438)\n' + s
o = s.encode('utf-8')
open(OUT, 'wb').write(o)
print(f'mka1c: A1P points physical {hits[0]} flexible {hits[1]} pooled {hits[2]}; in {hashlib.md5(src).hexdigest()} out {hashlib.md5(o).hexdigest()}')
