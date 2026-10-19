#!/usr/bin/env bash
# BC5 (exp 0175): one 90-s start of the second title (intro and start screen, no input), with the
# given launcher and environment; prints the frame counter for t 55-82 s. usage: startscreen.sh <tag> <launcher> "<env>"
TAG=$1; L=$2; ENVS=$3
cd ~/bc5-work
pgrep -x kyty_emulator >/dev/null && { echo busy; exit 1; }
while [ "$(date +%M)" = "$(stat -c %y play-pkg-last.log | cut -c15-16)" ]; do sleep 5; done
setsid nohup distrobox enter ubuntu -- env KYTY_BC5_FPS_COUNTER=1 KYTY_BC5_INPUT_CMD=/dev/null $ENVS ~/bc5-work/$L < /dev/null > ~/bc5-work/ss-$TAG.out 2>&1 &
for i in $(seq 1 60); do pgrep -x kyty_emulator >/dev/null && break; sleep 1; done
sleep 88; cp play-pkg-last.log ss-$TAG.log; pkill -x kyty_emulator; sleep 4; pkill -9 -x kyty_emulator; sleep 3
grep -a "^fps counter" ss-$TAG.log | awk -v tag="$TAG" "{t=\$4+0; if (t<55||t>=82) next; n++; s+=\$6/\$9; match(\$0,/longest gap ([0-9.]+)/,g); if (g[1]+0>mx) mx=g[1]+0} END{printf \"%-28s %.1f flips/s over %d s, longest gap %.0f ms\n\", tag, (n?s/n:0), n, mx}"
