#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""BC5 experiment 0438 (tag h438): h438.hpp's spans in the host unit, normal build only, off unless BC5_0438_HOSTWAIT=1.
Usage: mkh438.py IN.cpp OUT.cpp   (IN: the bake unit, bake/mkbake438.py's output, md5 ff9e8fe2...)
  - #include "kernel/h438.hpp" after the unit's first quoted include (h438.hpp includes o438.hpp beside it);
  - BC5_H438_GC(request) at the top of gc_ioctl;
  - BC5_H438_FLIPSPAN() at the top of VideoOutSubmitEopFlip, and its Direct::drain() between BC5_H438_DRAIN_BEGIN/END;
  - every lock site of the form "<indent>std::lock_guard|unique_lock|scoped_lock[<...>] name(mutex);" alone on its
    line: BC5_H438_LOCK_ID(id, "mutex@line", <the statement>); one id per site (line: IN's line number); and exp 0436's
    ring lock of the unlocked kernel submit (if (su) su_ring = std::unique_lock...), timed as one statement. Other
    forms (several arguments, try_to_lock, defer_lock) are left as they are and counted.
Writes OUT and prints the site count and OUT's md5.
"""
import hashlib
import re
import sys

IN, OUT = sys.argv[1], sys.argv[2]
src = open(IN, 'rb').read()
assert hashlib.md5(src).hexdigest() == 'ff9e8fe2e4139264ebaf74f9e84bd892', 'not the bake unit (ff9e8fe2)'
s = src.decode('utf-8')
assert '\r' not in s

LOCK = re.compile(r'^(\s+)(std::(?:lock_guard|unique_lock|scoped_lock)(?:<[^>]*>)? +[A-Za-z_][A-Za-z_0-9]* *\(([A-Za-z_][A-Za-z_0-9.:>()-]*)\));(\s*//.*)?$')
# exp 0436's ring lock of the unlocked kernel submit, an assignment: the whole statement is timed
RING = re.compile(r'^(\s+)(if \(su\) su_ring = std::unique_lock<std::mutex>\(g_su436_ring_mu\[.*\]\));(\s*//.*)?$')
ANY = re.compile(r'std::(?:lock_guard|unique_lock|scoped_lock)\b')
lines = s.split('\n')
sites, left, ring = 0, 0, False
for i, ln in enumerate(lines):
    m = LOCK.match(ln)
    g = RING.match(ln)
    if g:
        lines[i] = f'{g.group(1)}BC5_H438_LOCK_ID({sites}, "g_su436_ring_mu@{i + 1}", {g.group(2)});{g.group(3) or ""}'
        sites += 1
        ring = True
    elif m:
        lines[i] = f'{m.group(1)}BC5_H438_LOCK_ID({sites}, "{m.group(3)}@{i + 1}", {m.group(2)});{m.group(4) or ""}'
        sites += 1
    elif ANY.search(ln) and not ln.lstrip().startswith('//'):
        left += 1
assert 0 < sites <= 512 and ring, (sites, ring)
s = '\n'.join(lines)


def rep(old, new):
    global s
    n = s.count(old)
    assert n == 1, (n, old[:100])
    s = s.replace(old, new)


i = s.index('#include "')
j = s.index('\n', i) + 1
s = s[:j] + '#include "kernel/h438.hpp" // exp 0438 (tag h438): records, normal build only, off unless BC5_0438_HOSTWAIT=1\n' + s[j:]
rep('''static int gc_ioctl(uint64_t request, void* argp) {
''', '''static int gc_ioctl(uint64_t request, void* argp) {
	BC5_H438_GC(request); // exp 0438 (tag h438)
''')
a = s.index('static KYTY_SYSV_ABI int SubmitEopFlip(')
b = s.index(') {\n', a) + 4
assert s.count('static KYTY_SYSV_ABI int SubmitEopFlip(') == 1 and ';' not in s[a:b]
s = s[:b] + '\tBC5_H438_FLIPSPAN(); // exp 0438 (tag h438)\n' + s[b:]
rep('''	if (!defer) Bc5Gc::Direct::drain(); // nothing of the frame may still be in flight''',
    '''	if (!defer) { // exp 0438 (tag h438): the drain's own span
		BC5_H438_DRAIN_BEGIN()
		Bc5Gc::Direct::drain(); // nothing of the frame may still be in flight
		BC5_H438_DRAIN_END()
	}''')
out = s.encode('utf-8')
open(OUT, 'wb').write(out)
print(f'mkh438: lock sites {sites} (left as they are: {left}); {hashlib.md5(out).hexdigest()}')
