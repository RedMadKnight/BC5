#!/usr/bin/env bash
# BC5 (experiment 0180): the second title from its start screen into slot 1 (cross x4, as the route
# runs), then no input, for <seconds>; a screenshot every 15 s from t 100 s (private, not committed).
# The normal build logs its frame counter and the audio push rate each second.
# usage: [LC_ENV="VAR=value ..."] cutscene-run.sh <tag> <0|1> <seconds>
TAG=$1; LEAN=$2; SECS=${3:-240}
cd ~/bc5-work
pgrep -x kyty_emulator >/dev/null && { echo busy; exit 1; }
printf 'wait 85000\npress cross\nwait 20000\npress cross\nwait 8000\npress cross\nwait 8000\npress cross\n' > cs-$TAG.cmd
LOGF=play-pkg-last.log; [ "$LEAN" = 1 ] && LOGF=play-pkg-lean-last.log
setsid nohup distrobox enter ubuntu -- env BC5_LEAN="$LEAN" KYTY_BC5_INPUT_CMD=$HOME/bc5-work/cs-$TAG.cmd ${LC_ENV:-} ~/bc5-work/play-pkg.sh < /dev/null > ~/bc5-work/cs-$TAG.out 2>&1 &
for _ in $(seq 1 60); do pgrep -x kyty_emulator >/dev/null && break; sleep 1; done
T0=$(date +%s)
while [ $(( $(date +%s) - T0 )) -lt "$SECS" ]; do
  e=$(( $(date +%s) - T0 ))
  if [ "$e" -ge 100 ] && [ $(( e % 15 )) -eq 0 ]; then SHOTS=0180-$TAG ~/bc5-work/shot.sh "t$e" 0 > /dev/null 2>&1; fi
  pgrep -x kyty_emulator >/dev/null || break
  sleep 1
done
cp "$LOGF" cs-$TAG.log
pkill -x kyty_emulator; sleep 4; pkill -9 -x kyty_emulator; sleep 3
ls ~/bc5-work/shots0180-$TAG/*.jpg 2>/dev/null | wc -l
