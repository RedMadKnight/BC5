#!/usr/bin/env python3
"""BC5 exp 0425, the shared swap (2026-11-16): C1 only, on by default for every title.
    mkc1.py <tree root>
on the shared tree at patch 4945ef1b. The maintainer, to the top session: "na razie wdroz to rozwiazanie do wszystkich
wersji - najwyzej pozniej wycofasz" (C1, the 200 us wake slice).

Two edits:
- src/kernel/pthread.cpp (pinned): patch0425.py's C1 block, unchanged in code: Bc5ApplyWakeSlice after the nice in
  Bc5ApplyGuestPriority. Its two stderr lines are under #ifndef BC5_LEAN; the switch itself is read in both builds.
- src/bc5/switch_defaults.hpp: the row {"KYTY_BC5_0425_WAKE_SLICE_US", "200"} in kSoft, in both builds. kSoft is set
  without overwrite, so KYTY_BC5_0425_WAKE_SLICE_US=0 in the environment turns C1 off (the rollback without a build).
  NOT kFixes: since exp 0419 its rows are forced with overwrite, so =0 could not turn them off.
Not in it: the catcher, C2, C3, P1-P3 (semaphore.cpp, gamePatch.cpp and libPlayGo.cpp are untouched). JobArenaFix
stays as the shared tree has it."""
import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import patch0425  # noqa: E402  (the private build's edits: the same C1 text)

PTH_REL = 'src/kernel/pthread.cpp'
SD_REL = 'src/bc5/switch_defaults.hpp'

OLD_HEAD = '// ---- experiment 0425 C1: KYTY_BC5_0425_WAKE_SLICE_US=<100..3000> -----------------------------------------------------\n'
NEW_HEAD = ('// ---- experiment 0425 C1: KYTY_BC5_0425_WAKE_SLICE_US=<100..3000> -----------------------------------------------------\n'
            '// Shared since 2026-11-16 (the maintainer\'s word): on by default at 200 us for every title, through kSoft in\n'
            '// bc5/switch_defaults.hpp; KYTY_BC5_0425_WAKE_SLICE_US=0 turns it off. Exp 0425: with JobArenaFix off, the\n'
            '// second title\'s fight crashed 0 of 10 with it against 6 of 15 controls (a rule-passing 4/4 vs 3/3, R13).\n')

SD_OLD = '    {"BC5_GC_MODE", "direct"},\n'
SD_NEW = ('    {"BC5_GC_MODE", "direct"},\n'
          '    // exp 0425 C1 (2026-11-16, the maintainer\'s word): a 200 us EEVDF wake slice for guest threads below priority\n'
          '    // 733 (pthread.cpp). Soft, so KYTY_BC5_0425_WAKE_SLICE_US=0 turns it off.\n'
          '    {"KYTY_BC5_0425_WAKE_SLICE_US", "200"},\n')


def edit(path, pairs, pin=None):
    raw = open(path, 'rb').read()
    if pin is not None and hashlib.sha256(raw).hexdigest() != pin:
        sys.exit('mkc1 STOP: %s is not its pin' % path)
    crlf = b'\r\n' in raw
    text = raw.decode('utf-8').replace('\r\n', '\n')
    for old, new in pairs:
        if text.count(old) != 1:
            sys.exit('mkc1 STOP: %s: an anchor occurs %d times' % (path, text.count(old)))
        text = text.replace(old, new)
    out = (text.replace('\n', '\r\n') if crlf else text).encode('utf-8')
    open(path, 'wb').write(out)
    print('mkc1: %s %s, sha256 %s' % (path, 'CRLF' if crlf else 'LF', hashlib.sha256(out).hexdigest()[:16]))


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    tree = sys.argv[1]
    old, new = patch0425.PTH[0]
    assert len(patch0425.PTH) == 1 and new.count(OLD_HEAD) == 1
    new = new.replace(OLD_HEAD, NEW_HEAD)
    edit(tree + '/' + PTH_REL, [(old, new)], patch0425.PINS[PTH_REL])
    edit(tree + '/' + SD_REL, [(SD_OLD, SD_NEW)])
    print('mkc1: done')


if __name__ == '__main__':
    main()
