#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""BC5 experiment 0438 (the lean round): derive run0438l.sh from exp 0432's scene runner run0432f.sh (md5 2d11fd6b, the
runner of every 0438 chain) by applying exp 0430's mkrun0430l.py hunks to it, unchanged, except the two that run0432f.sh
already has (the route by time, N_TIMED) and with the launcher's path in the LGONE line set to exp 0432's.
    mkrun0438l.py <run0432f.sh> <mkrun0430l.py> <run0438l.sh>
The hunks taken (see mkrun0430l.py): N_MH (MangoHud's own per-frame log, invisible overlay, autostart_log,
log_interval=0, into $R/$TAG-mh/; the per-second fps lines made from it), P_HOST (default off: the ubuntu distrobox, as
every 0438 chain), the maps at 30 s, N_LEANSESS (the Plasma shell stopped for the run as the lean shortcuts do, restored
at the end), the host checks at G+60. The MangoHud CSV stays in $R/$TAG-mh/ for the frame-time statistics (mh0438.py).
"""
import hashlib
import sys

src, mk, dst = sys.argv[1], sys.argv[2], sys.argv[3]
b = open(src, 'rb').read()
assert hashlib.md5(b).hexdigest()[:8] == '2d11fd6b', 'run0432f.sh is not 2d11fd6b'
mkb = open(mk, 'rb').read()
code = mkb.decode('utf-8')
s = b.decode('utf-8')
assert '\r' not in s
# exp 0432's launcher path in the LGONE line, as run0432f.sh has it
s = s.replace('pgrep -f "exp0432/n/play-pkg-0425f.sh"', 'pgrep -f "exp0430/n/play-pkg-0425f.sh"')  # matched to the hunk, put back below
applied, skipped = [], []


def sub(old, new, n=1):
    global s
    got = s.count(old)
    if got == 0:
        skipped.append(old.split('\n')[0][:70])
        return
    assert got == n, '%d matches, wanted %d: %r' % (got, n, old[:80])
    s = s.replace(old, new)
    applied.append(old.split('\n')[0][:70])


# run mkrun0430l.py's hunks only: from its first sub( call to the line before its header rewrite
body = code[code.index('# the route by time (exp 0432)'):code.index('s = ("#!/usr/bin/env bash')]
exec(body, {'sub': sub, 's': None})  # the hunks call sub(), which works on this module's s
s = s.replace('pgrep -f "exp0430/n/play-pkg-0425f.sh"', 'pgrep -f "exp0432/n/play-pkg-0425f.sh"')
want_skipped = {'  if [ -z "$J" ] && [ "$NOW" -ge 60 ]; then', '  if [ -n "$J" ] && [ "$RS" -lt 4 ] && [ "$NOW" -ge 85 ]; then'}
assert set(skipped) == want_skipped, ('skipped', skipped)
s = '#!/usr/bin/env bash\n# BC5 exp 0438: derived by mkrun0438l.py from run0432f.sh 2d11fd6b with mkrun0430l.py\'s hunks (N_MH, P_HOST, N_LEANSESS).\n' + s.split('\n', 1)[1]
open(dst, 'w', encoding='utf-8', newline='\n').write(s)
print('applied %d, skipped %d (the timed route, already in run0432f.sh)' % (len(applied), len(skipped)))
print('wrote', dst, hashlib.md5(s.encode()).hexdigest())
