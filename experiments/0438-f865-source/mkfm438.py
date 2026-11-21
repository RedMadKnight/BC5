#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""BC5 experiment 0438 (tags f438, m438): the last records before the second title is uninstalled. Test builds only.
Usage: mkfm438.py IN.cpp OUT.cpp
  IN = h438.cpp (mkh438.py's output, 3aa9d745...): f438 + m438, for the NORMAL build (F runs):
       - ChainSlot gets "bc5::f438::Slot f438;" beside its flush_mu;
       - chain_submit's flush-order lock (h438's site "s.flush_mu@7985") becomes BC5_F438_FLUSH_LOCK(s, why, foreign):
         the holder (thread, reason) read before the wait, the wait recorded by holder and reason, each hold timed;
         off unless BC5_0438_HOSTWAIT=1 (h438.hpp);
       - m438 (below).
  IN = bake438.cpp (the bake unit, ff9e8fe2...): m438 only, for the LEAN build (P runs, perf beside them).
m438: frame marks. At the top of VideoOutSubmitEopFlip, with BC5_0438_FRAMEMARK=1, the steady clock (CLOCK_MONOTONIC,
the clock perf -k CLOCK_MONOTONIC stamps its samples with) in ns is appended to $BC5_0438_FRAMEMARK_FILE (else
~/bc5-work/exp0438/m438-<pid>.txt), one line per flip, written every 64 flips. Off: one static bool read per flip. It is
compiled into lean too: these are private test builds, never the shared ones (the lean rule of 2026-11-15 is for those).
"""
import hashlib
import sys

IN, OUT = sys.argv[1], sys.argv[2]
src = open(IN, 'rb').read()
md5 = hashlib.md5(src).hexdigest()
H438, BAKE = '3aa9d745fb27f421a595ba1ae736f86f', 'ff9e8fe2e4139264ebaf74f9e84bd892'
assert md5 in (H438, BAKE), f'{IN} is neither h438.cpp nor the bake unit: {md5}'
s = src.decode('utf-8')
assert '\r' not in s
NL = chr(92) + 'n'


def rep(old, new):
    global s
    n = s.count(old)
    assert n == 1, (n, old[:100])
    s = s.replace(old, new)


if md5 == H438:
    rep('''	std::recursive_mutex         flush_mu;   // held through a submission''', '''	bc5::f438::Slot              f438;       // exp 0438 (tag f438): who holds flush_mu, and why (records only)
	std::recursive_mutex         flush_mu;   // held through a submission''')
    lines = s.split('\n')
    hits = [i for i, l in enumerate(lines) if '"s.flush_mu@7985", std::lock_guard order(s.flush_mu));' in l]
    assert len(hits) == 1, hits
    ind = lines[hits[0]][:len(lines[hits[0]]) - len(lines[hits[0]].lstrip())]
    lines[hits[0]] = ind + 'BC5_F438_FLUSH_LOCK(s, why, foreign); // exp 0438 (tag f438): was h438\'s site s.flush_mu@7985'
    s = '\n'.join(lines)

M438 = '''// BC5 experiment 0438 (tag m438): frame marks for a profile (test builds only), off unless BC5_0438_FRAMEMARK=1
static void m438_mark() {
	static const bool on = [] {
		const char* e = std::getenv("BC5_0438_FRAMEMARK");
		return e != nullptr && e[0] == '1' && e[1] == 0;
	}();
	if (!on) return;
	static std::mutex            m;
	static std::vector<uint64_t> buf;
	static FILE*                 f = nullptr;
	const uint64_t               ns = static_cast<uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now().time_since_epoch()).count());
	std::lock_guard              lk(m);
	buf.push_back(ns);
	if (buf.size() < 64) return;
	if (f == nullptr) {
		const char* e    = std::getenv("BC5_0438_FRAMEMARK_FILE");
		const char* h    = std::getenv("HOME");
		std::string path = e != nullptr && e[0] != 0 ? std::string(e) : std::string(h != nullptr ? h : ".") + "/bc5-work/exp0438/m438-" + std::to_string(static_cast<long>(getpid())) + ".txt";
		f                = std::fopen(path.c_str(), "w");
		std::fprintf(stderr, "m438 (exp 0438): frame marks (steady clock ns per flip) in %s%sNL", path.c_str(), f == nullptr ? " (CANNOT OPEN)" : "");
	}
	if (f != nullptr) {
		for (const uint64_t x: buf) std::fprintf(f, "%llu" "NL", static_cast<unsigned long long>(x));
		std::fflush(f);
	}
	buf.clear();
}
'''.replace('NL', NL)
a = s.index('static KYTY_SYSV_ABI int SubmitEopFlip(')
assert s.count('static KYTY_SYSV_ABI int SubmitEopFlip(') == 1
s = s[:a] + M438 + s[a:]
a = s.index('static KYTY_SYSV_ABI int SubmitEopFlip(')
b = s.index(') {\n', a) + 4
assert ';' not in s[a:b]
s = s[:b] + '\tm438_mark(); // exp 0438 (tag m438)\n' + s[b:]
for w in ('<chrono>', '<mutex>', '<vector>', '<string>'):
    pass  # the unit includes them already (checked below by the compile); getpid: <unistd.h> via the tree's headers
out = s.encode('utf-8')
open(OUT, 'wb').write(out)
print(f'mkfm438: {"f438 + m438" if md5 == H438 else "m438"}; {hashlib.md5(out).hexdigest()}')
