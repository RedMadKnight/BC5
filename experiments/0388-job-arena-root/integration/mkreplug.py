#!/usr/bin/env python3
"""BC5 exp 0388, the integration: exp 0372's software replug check on the shared build. s6n0372.sh and replug0372.sh with the
shared binary, the new launcher and the atomic lock of box0388.sh in place of their own.
usage: mkreplug.py <exp 0372 raw dir> <out dir> <first 8 of the shared normal> <tag>"""
import sys

SRC, OUT, MD5, TAG = sys.argv[1:5]


def R(s, a, b, n=1):
    assert s.count(a) == n, (a, s.count(a))
    return s.replace(a, b)


s = open(f"{SRC}/s6n0372.sh", encoding="utf-8", newline="").read()
s = R(s, 'BIN=$W/exp0372/kyty_emulator; WANT=$(cat "$W/exp0372/binary.md5" 2> /dev/null)', f'BIN=$W/kytyplus-build/src/kyty_emulator; WANT={MD5}')
s = R(s, '[ -s "$LOCK" ] && ! grep -q "^top exp 0372 |" "$LOCK" && { echo "the box is locked: $(cat "$LOCK")"; exit 1; }', f'grep -q "^top exp 0388 | .*, {TAG}, " "$LOCK" || {{ echo "the box is not locked for this run: $(cat "$LOCK")"; exit 1; }}')
lines = s.split("\n")
keep = []
for x in lines:
    if x.startswith('echo "top exp 0372 | s6n run:'):
        continue  # the lock is taken before this script, atomically, and released after it
    if x.startswith("trap '[ -z \"${SOAK:-}\" ] && grep -q \"^top exp 0372 | s6n run\""):
        continue
    if x.startswith('grep -q "^top exp 0372 | s6n run" "$LOCK"'):
        continue
    keep.append(x)
s = "\n".join(keep)
assert "top exp 0372" not in s
s = R(s, "chk 'export BC5_DIRECT_COMPUTE_RING=-1 BC5_DIRECT_CROSS_RING_WAITS=all  #", "chk 'export BC5_DIRECT_CROSS_RING_WAITS=all  #")
s = R(s, "'exp0372/direct-learned-pkg.txt' 'COMPUTE_RING=-1'; do", "'exp0372/direct-learned-pkg.txt' 'CROSS_RING_WAITS=all'; do")
s = R(s, 'WANTENV=("BC5_DIRECT_COMPUTE_RING=-1" ', 'WANTENV=(')
open(f"{OUT}/s6n0372j.sh", "w", encoding="utf-8", newline="").write(s)

s = open(f"{SRC}/replug0372.sh", encoding="utf-8", newline="").read()
s = R(s, 'ours() { grep -q "^top exp 0372 | s6n run: .*, $TAG, " "$LOCK" 2> /dev/null; }', 'ours() { grep -q "^top exp 0388 | .*, $TAG, " "$LOCK" 2> /dev/null; }')
open(f"{OUT}/replug0372j.sh", "w", encoding="utf-8", newline="").write(s)
print("ok")
