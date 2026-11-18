#!/usr/bin/env python3
# BC5 exp 0430 (2026-11-18 evening, the maintainer through the top session: "F18 - ja przetestuję na dłuższej grze"):
# makes the private play launcher "BC5 test 0430 (F10+F4+F16+F18)" from a copy of the shared ~/bc5-work/play-pkg.sh
# (pinned by md5), which stays untouched. Made like mkplay0430b.py. Changes: the private normal build in exp0430/p22
# (its md5 given as argv[3], checked at every start), its own logs under exp0430/play-f18/, no lean, no BC5_EMU
# override, the unpacked game as in the runs, and after the title's words: exactly the M runs' words (chain0430.sh
# CATCH=0 plus ab0430b.sh FWORDS of h430M*) and BC5_DIRECT_XQ_BUSY_WAIT=1 (F18); BC5_GUARD_MAP_RULE and BC5_GUARD_PRT_BG
# unset. Way 2 and R as shared (title defaults, R compiled on by default). His saves (_SaveData-pkg-play), his
# input.cfg (RT on), no learned windows (direct-learned-none.txt), ulimit -c 0: all as play-pkg.sh has them.
# No JobArenaFix word.
# usage (on the box): python3 -I mkplay0430c.py ~/bc5-work/play-pkg.sh ~/bc5-work/exp0430/play-0430f18.sh <md5-8>
import hashlib
import sys

src, dst, BIN = sys.argv[1], sys.argv[2], sys.argv[3]
assert len(BIN) == 8
b = open(src, 'rb').read()
assert hashlib.md5(b).hexdigest().startswith('47426d8e'), 'play-pkg.sh is not 47426d8e'
s = b.decode('utf-8')
E = '/home/kjaniszewski/bc5-work/exp0430'
P = E + '/play-f18'


def rep(old, new):
    global s
    assert s.count(old) == 1, old
    s = s.replace(old, new)


rep('#!/usr/bin/env bash\n', '#!/usr/bin/env bash\n'
    '# BC5 exp 0430 F18 TEST (2026-11-18, the maintainer\'s long play): a private copy of play-pkg.sh 47426d8e, made by\n'
    '# experiments/0430-hang-catcher/mkplay0430c.py. The private normal build ' + BIN + ' (F10 + F4 + F16 + F18 on the M\n'
    '# runs\' words); logs in ' + P + '/, the counters in the play\'s gc/direct.log. Not a shared launcher.\n')
rep('M=~/bc5-data/mnt/pkg-play\n', 'M=~/bc5-data/mnt/pkg-play\n'
    'export BC5_GAME_DIR=${BC5_GAME_DIR:-/home/kjaniszewski/bc5-data/games/PPSA03671}  # exp 0430: the unpacked game, as in the runs\n')
rep('EMU=~/bc5-work/kytyplus-build/src/kyty_emulator\n',
    'EMU=' + E + '/p22/kyty_emulator  # exp 0430: the private normal build with F18, checked below\n')
rep('LOG=~/bc5-work/play-pkg-last.log\n',
    'mkdir -p ' + P + '\n'
    'LOG=' + P + '/play-last.log  # exp 0430: own log, each play kept\n'
    '[ -f "$LOG" ] && mv "$LOG" "${LOG%.log}-$(date -r "$LOG" +%Y%m%d-%H%M%S).log"\n')
rep('  EMU=~/bc5-work/kytyplus-build-lean/src/kyty_emulator LOG=~/bc5-work/play-pkg-lean-last.log\n',
    '  echo "exp 0430: there is no private lean build"; exit 1\n')
rep('MLOG=~/bc5-work/play-pkg-mount.log\n', 'MLOG=' + P + '/mount.log\n')
rep('[ -n "${BC5_EMU:-}" ] && EMU=$BC5_EMU  # exp 0177: another binary (A/B against an older build)\n',
    '[ "$(md5sum < "$EMU" | cut -c1-8)" = ' + BIN + ' ] || { echo "exp 0430: $EMU is not the build ' + BIN + '"; exit 1; }\n')
anchor = '  n=${w%%=*}; [ -n "${!n+x}" ] || export "$w"\ndone\n'
rep(anchor, anchor +
    '# exp 0430 F18 test: the M runs\' words (chain0430.sh CATCH=0, ab0430b.sh FWORDS of h430M*) and F18 on\n'
    'export BC5_DIRECT_ACB_RINGS=4 BC5_DIRECT_ACB_QUEUE_STATE=1 BC5_DIRECT_ACB_MEC_INDIRECT=1 BC5_DIRECT_ACB_STATE_NO_WALK=1 BC5_DIRECT_ACB_SPLIT_LATE=3\n'
    'export BC5_0430_F3=1 BC5_0430_F2=1 BC5_0430_G=0 BC5_DIRECT_TIMEOUT_PROBE=1\n'
    'export BC5_DIRECT_XQ_PENDING=1 BC5_DIRECT_XQ_ACQUIRE=0 BC5_DIRECT_XQ_FENCE=1 BC5_DIRECT_XQ_PRECISE=0 BC5_DIRECT_XQ_KEEP=0 BC5_DIRECT_XQ_KEEP_ALL=0\n'
    'export BC5_DIRECT_XQ_ORDER=0 BC5_DIRECT_XQ_FLUSH=0 BC5_DIRECT_XQ_COUNT=2 BC5_DIRECT_XQ_FLIGHT_WAIT=1 BC5_DIRECT_XQ_BUSY_WAIT=1\n'
    'unset BC5_GUARD_MAP_RULE BC5_GUARD_PRT_BG  # CLAUDE.md: never set in a launcher\n')
assert 'learned-none' in s and 'direct-learned-pkg' not in s
assert 'ulimit -c 0' in s
assert 'JobArena' not in s and 'JOB_ARENA' not in s
open(dst, 'w', encoding='utf-8', newline='\n').write(s)
print('written', dst, hashlib.md5(s.encode()).hexdigest()[:8])
