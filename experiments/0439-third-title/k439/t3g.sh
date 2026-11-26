#!/usr/bin/env bash
# BC5 exp 0439: the SIGFPE run (the top session's GO of 11-21 ~22:50): the path of item 41 (crosses at 45, 125, 145 and 205 s),
# the emulator under gdb in the distrobox (play439.sh P439_GDB=k439/fpe439.gdb), bound 260 s. gdb's report goes to the log.
#   t3g.sh <md5-8 of the private normal build>
set -u
PIN=${1:?md5}
cd "$HOME/bc5-work/exp0439" || exit 1
T3S_TAG=-g T3S_BOUND=260 T3S_PRESSES="45 125 145 205" T3S_EXTRA="P439_GDB=$HOME/bc5-work/exp0439/k439/fpe439.gdb BC5_0439_AUDIO_CATCH=1" bash k439/t3s.sh "$PIN" unset "" script 2>&1 | tail -30
O=runs/t3s-vunset-g
echo "== presses"; cat $O.keys
echo "== memory"; cat $O.mem
echo "== gdb"; sed -n '/=== fpe439: the stop ===/,/=== fpe439: threads ===/p' $O/play-last.log | cut -c1-200 | head -400; echo '== ZERO lines'; grep -a 'tag fz439): ZERO' $O/play-last.log | head -40
