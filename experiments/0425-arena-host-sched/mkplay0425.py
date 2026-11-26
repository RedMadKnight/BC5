#!/usr/bin/env python3
# BC5 exp 0425 (2026-11-16, the maintainer's yes to making him a shortcut through the top session): makes the private play
# launcher for C1 from a copy of the shared ~/bc5-work/play-pkg.sh (pinned by md5), which stays untouched.
# Changes: the private normal build 81e8d0f7 (checked at every start), its own logs under exp0425/play-c1/, no lean,
# no BC5_EMU override, and after the title's words: JobArenaFix off, the catcher on, C1 at 200 us, the unpacked
# game as in the S runs, BC5_GUARD_MAP_RULE and BC5_GUARD_PRT_BG unset. His saves (_SaveData-pkg-play) are kept.
# usage (on the box): python3 mkplay0425.py ~/bc5-work/play-pkg.sh ~/bc5-work/exp0425/play-0425-c1.sh
import hashlib, sys

src, dst = sys.argv[1], sys.argv[2]
b = open(src, 'rb').read()
assert hashlib.md5(b).hexdigest().startswith('47426d8e'), 'play-pkg.sh is not 47426d8e'
s = b.decode('utf-8')
E = '$HOME/bc5-work/exp0425'


def rep(old, new):
    global s
    assert s.count(old) == 1, old
    s = s.replace(old, new)


rep('#!/usr/bin/env bash\n', '#!/usr/bin/env bash\n'
    '# BC5 exp 0425 C1 TEST (2026-11-16, the maintainer\'s yes): a private copy of play-pkg.sh 47426d8e, made by\n'
    '# experiments/0425-arena-host-sched/mkplay0425.py. The private normal build 81e8d0f7 with C1 (a 200 us wake slice)\n'
    '# and JobArenaFix OFF, the catcher on; logs in ' + E + '/play-c1/. Not a shared launcher.\n')
rep('M=~/bc5-data/mnt/pkg-play\n', 'M=~/bc5-data/mnt/pkg-play\n'
    'export BC5_GAME_DIR=${BC5_GAME_DIR:-$HOME/bc5-data/games/TITLE2}  # exp 0425: the unpacked game, as in the S runs\n')
rep('EMU=~/bc5-work/kytyplus-build/src/kyty_emulator\n',
    'EMU=' + E + '/kyty_emulator  # exp 0425: the private normal build, checked below\n')
rep('LOG=~/bc5-work/play-pkg-last.log\n',
    'mkdir -p ' + E + '/play-c1\n'
    'LOG=' + E + '/play-c1/play-last.log  # exp 0425: own log, each play kept\n'
    '[ -f "$LOG" ] && mv "$LOG" "${LOG%.log}-$(date -r "$LOG" +%Y%m%d-%H%M%S).log"\n')
rep('  EMU=~/bc5-work/kytyplus-build-lean/src/kyty_emulator LOG=~/bc5-work/play-pkg-lean-last.log\n',
    '  echo "exp 0425: there is no private lean build"; exit 1\n')
rep('MLOG=~/bc5-work/play-pkg-mount.log\n', 'MLOG=' + E + '/play-c1/mount.log\n')
rep('[ -n "${BC5_EMU:-}" ] && EMU=$BC5_EMU  # exp 0177: another binary (A/B against an older build)\n',
    '[ "$(md5sum < "$EMU" | cut -c1-8)" = 81e8d0f7 ] || { echo "exp 0425: $EMU is not the build 81e8d0f7"; exit 1; }\n')
anchor = '  n=${w%%=*}; [ -n "${!n+x}" ] || export "$w"\ndone\n'
rep(anchor, anchor +
    '# exp 0425 C1 test: the S runs\' arm words: JobArenaFix off, the catcher on, C1 at 200 us\n'
    'export KYTY_BC5_JOB_ARENA_FIX=0 KYTY_BC5_0425_CATCH=1 KYTY_BC5_0425_WAKE_SLICE_US=200\n'
    'unset BC5_GUARD_MAP_RULE BC5_GUARD_PRT_BG  # CLAUDE.md: never set in a launcher\n')
assert 'learned-none' in s and 'direct-learned-pkg' not in s
open(dst, 'w', encoding='utf-8', newline='\n').write(s)
