#!/usr/bin/env python3
# BC5 exp 0430 (2026-11-17 ~09:00: build 8 for the maintainer's play to catch a crash; the first version 2026-11-16 ~21:10, the maintainer wants to play to trigger the hang himself, through the top session):
# makes the private play launcher "BC5 test 0430 (hang catcher)" from a copy of the shared ~/bc5-work/play-pkg.sh
# (pinned by md5), which stays untouched. Made like exp 0425's mkplay0425.py. Changes: the private normal build bfde29b6
# (build 3b, checked at every start), its own logs under exp0430/play/, no lean, no BC5_EMU override, the unpacked game
# as in the runs, and after the title's words: the exp 0430 catchers (dispatch journal, args at submit, waves at a 900-ms
# stall through the helper, the stalled submission's memory, the BVH tables at submit); BC5_GUARD_MAP_RULE and
# BC5_GUARD_PRT_BG unset. Way 2 stays as the build's title defaults (as shared). His saves (_SaveData-pkg-play), his
# input.cfg (RT on), no learned windows (direct-learned-none.txt), ulimit -c 0: all as play-pkg.sh has them.
# usage (on the box): python3 -I mkplay0430.py ~/bc5-work/play-pkg.sh ~/bc5-work/exp0430/play-0430.sh
import hashlib
import sys

src, dst = sys.argv[1], sys.argv[2]
b = open(src, 'rb').read()
assert hashlib.md5(b).hexdigest().startswith('47426d8e'), 'play-pkg.sh is not 47426d8e'
s = b.decode('utf-8')
E = '$HOME/bc5-work/exp0430'
BIN = '75f87980'


def rep(old, new):
    global s
    assert s.count(old) == 1, old
    s = s.replace(old, new)


rep('#!/usr/bin/env bash\n', '#!/usr/bin/env bash\n'
    '# BC5 exp 0430 HANG-CATCHER TEST (2026-11-16, the maintainer\'s play): a private copy of play-pkg.sh 47426d8e, made by\n'
    '# experiments/0430-hang-catcher/mkplay0430.py. The private normal build ' + BIN + ' (build 8: F3 + F4 + F2 fallback, every catcher) with the exp 0430\n'
    '# catchers on; logs in ' + E + '/play/, the catchers\' files in the play\'s gc directory. Not a shared launcher.\n')
rep('M=~/bc5-data/mnt/pkg-play\n', 'M=~/bc5-data/mnt/pkg-play\n'
    'export BC5_GAME_DIR=${BC5_GAME_DIR:-$HOME/bc5-data/games/TITLE2}  # exp 0430: the unpacked game, as in the runs\n')
rep('EMU=~/bc5-work/kytyplus-build/src/kyty_emulator\n',
    'EMU=' + E + '/kyty_emulator.' + BIN + '  # exp 0430: the private normal build 8, checked below\n')
rep('LOG=~/bc5-work/play-pkg-last.log\n',
    'mkdir -p ' + E + '/play\n'
    'LOG=' + E + '/play/play-last.log  # exp 0430: own log, each play kept\n'
    '[ -f "$LOG" ] && mv "$LOG" "${LOG%.log}-$(date -r "$LOG" +%Y%m%d-%H%M%S).log"\n')
rep('  EMU=~/bc5-work/kytyplus-build-lean/src/kyty_emulator LOG=~/bc5-work/play-pkg-lean-last.log\n',
    '  echo "exp 0430: there is no private lean build"; exit 1\n')
rep('MLOG=~/bc5-work/play-pkg-mount.log\n', 'MLOG=' + E + '/play/mount.log\n')
rep('[ -n "${BC5_EMU:-}" ] && EMU=$BC5_EMU  # exp 0177: another binary (A/B against an older build)\n',
    '[ "$(md5sum < "$EMU" | cut -c1-8)" = ' + BIN + ' ] || { echo "exp 0430: $EMU is not the build ' + BIN + '"; exit 1; }\n')
anchor = '  n=${w%%=*}; [ -n "${!n+x}" ] || export "$w"\ndone\n'
rep(anchor, anchor +
    '# exp 0430 hang-catcher test, build 8: the D runs\' words (the fix F3 + F4 + F2 fallback, every catcher, G dump at 300 s)\n'
    'export BC5_0430_F3=1 BC5_0430_F2=1 BC5_0430_F4=1 BC5_0430_G=1 BC5_0430_G_AT=300 BC5_DIRECT_TIMEOUT_PROBE=1\n'
    'export BC5_0430_DJ=1 BC5_0430_ARGS=1 BC5_0430_WAVES_MS=900 BC5_0430_SNAP=1 BC5_0430_TABLES=1\n'
    'export BC5_0430_TABLE_PGMS=909973900,909973b00,909973d00,909973f00,909974400,909977100,90997a500\n'
    'unset BC5_GUARD_MAP_RULE BC5_GUARD_PRT_BG  # CLAUDE.md: never set in a launcher\n')
assert 'learned-none' in s and 'direct-learned-pkg' not in s
assert 'ulimit -c 0' in s
open(dst, 'w', encoding='utf-8', newline='\n').write(s)
print('written', dst, hashlib.md5(s.encode()).hexdigest()[:8])
