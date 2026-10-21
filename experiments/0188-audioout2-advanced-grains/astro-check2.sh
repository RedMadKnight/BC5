#!/usr/bin/env bash
# BC5 (experiment 0188): ASTRO BOT for 100 s from its start (no input), as exp 0180's astro-check.sh,
# with extra switches (ENVX) and the AudioOut2 and VideoOut event traces: audio seconds off real time,
# clears, frame rate, AudioOut2 advances/pushes, and whether the title reads its flip events.
# usage: ENVX="<switches>" astro-check2.sh <tag>
TAG=$1
cd ~/bc5-work
pgrep -x kyty_emulator >/dev/null && { echo busy; exit 1; }
setsid nohup distrobox enter ubuntu -- env KYTY_BC5_FPS_COUNTER=1 KYTY_BC5_AUDIO_TRACE=1 KYTY_BC5_MEASURE=1 KYTY_BC5_INPUT_CMD=/dev/null KYTY_BC5_AUDIO2_TRACE=1 KYTY_BC5_VIDEOOUT_EVENT_TRACE=1 ${ENVX:-} ~/bc5-work/play-astro.sh < /dev/null > astro-$TAG.out 2>&1 &
for _ in $(seq 1 60); do pgrep -x kyty_emulator >/dev/null && break; sleep 1; done
sleep 100; cp play-last.log astro-$TAG.log
pkill -x kyty_emulator; sleep 4; pkill -9 -x kyty_emulator; sleep 3
echo "== $TAG: ${ENVX:-defaults}"
grep -a "^audio trace" astro-$TAG.log | grep -v "(pad)" | awk '{t=$4+0; if (t<20) next; n++; for(i=1;i<=NF;i++){ if ($i=="(rate") r=$(i+1)+0; if ($i=="clears,") c=$(i-1)+0 } if (r<0.98||c>0) {bad++; l=l sprintf(" %d(%.2f/%d)", t, r, c)} cl+=c} END{printf "ASTRO BOT audio t20-100: %d of %d port-seconds off, %d clears:%s\n", bad, n, cl, l}'
grep -a "^fps counter" astro-$TAG.log | awk '{t=$4+0; if (t<40) next; n++; s+=$6/$9} END{printf "ASTRO BOT frames t40-100: %.1f flips/s\n", s/n}'
grep -a "^audio2 trace" astro-$TAG.log | awk '{for(i=1;i<=NF;i++){ if ($i=="advance") a+=$(i+1); if ($i=="push") p+=$(i+1)}} END {printf "AudioOut2: %d advances, %d pushes (ratio %.3f)\n", a, p, p ? a/p : 0}'
grep -a "^vo events" astro-$TAG.log | awk '{for(i=1;i<=NF;i++){ if ($i=="flip" && $(i+1)=="triggers,") tr+=$(i-1); if ($i=="while" && $(i+1)=="unread") un+=$(i-1); if ($i=="GetEventCount") gc+=$(i+1)} if ($0 !~ /delivered counts none/) dl++} END {printf "flip events: %d triggers, %d while unread, %d seconds with deliveries, GetEventCount calls %d\n", tr, un, dl, gc}'
