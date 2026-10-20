#!/usr/bin/env bash
# BC5 (experiment 0180): ASTRO BOT for 100 s from its start (no input) with the frame counter and
# the audio trace; prints the audio seconds off real time, the clears and the frame rate.
cd ~/bc5-work
pgrep -x kyty_emulator >/dev/null && { echo busy; exit 1; }
setsid nohup distrobox enter ubuntu -- env KYTY_BC5_FPS_COUNTER=1 KYTY_BC5_AUDIO_TRACE=1 KYTY_BC5_MEASURE=1 KYTY_BC5_INPUT_CMD=/dev/null ~/bc5-work/play-astro.sh < /dev/null > astro-check.out 2>&1 &
for _ in $(seq 1 60); do pgrep -x kyty_emulator >/dev/null && break; sleep 1; done
sleep 100; cp play-last.log astro-check.log
pkill -x kyty_emulator; sleep 4; pkill -9 -x kyty_emulator; sleep 3
grep -a "^audio trace" astro-check.log | grep -v "(pad)" | awk '{t=$4+0; if (t<20) next; n++; for(i=1;i<=NF;i++){ if ($i=="(rate") r=$(i+1)+0; if ($i=="clears,") c=$(i-1)+0 } if (r<0.98||c>0) {bad++; l=l sprintf(" %d(%.2f/%d)", t, r, c)} cl+=c} END{printf "ASTRO BOT audio t20-100: %d of %d port-seconds off, %d clears:%s\n", bad, n, cl, l}'
grep -a "^fps counter" astro-check.log | awk '{t=$4+0; if (t<40) next; n++; s+=$6/$9} END{printf "ASTRO BOT frames t40-100: %.1f flips/s\n", s/n}'
