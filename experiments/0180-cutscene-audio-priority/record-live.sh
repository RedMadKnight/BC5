#!/usr/bin/env bash
# BC5 (experiment 0180): what the headset hears, from the second title's start to walking after the
# opening, on the lean build: pw-record from the default output's monitor (the final mix the
# device gets), New Game in slot 3 by script, the "Leap Attack" prompt answered, then walking.
# Saves put back before and after. Output: rec-<tag>.wav (48 kHz stereo s16) and screenshots.
TAG=$1; SECS=${2:-560}
cd ~/bc5-work
BK=save-backup-0180-0953; SD=_SaveData/PPSA03671
restore() {
  cp -a "$BK/." "$SD/"
  for d in "$SD"/*/; do d=${d%/}; [ -e "$BK/$(basename "$d")" ] || rm -r -- "$d"; done
  diff -rq "$BK" "$SD" > /dev/null && echo "saves as in $BK" || echo "SAVES DIFFER from $BK"
}
pgrep -x kyty_emulator >/dev/null && { echo busy; exit 1; }
restore
export XDG_RUNTIME_DIR=/run/user/$(id -u)
SINK=$(wpctl inspect @DEFAULT_AUDIO_SINK@ | sed -n 's/.*node.name = "\(.*\)"/\1/p' | head -1)
echo "recording $SINK"
cat > rec-$TAG.cmd <<'CMD'
wait 85000
press cross
wait 20000
press down
wait 800
press down
wait 800
press cross
wait 30000
press cross
wait 8000
press cross
wait 175000
stick l 128 0
press triangle
wait 1500
press triangle
wait 2500
hold l1
press triangle
release l1
wait 2500
press square
wait 2000
press square
wait 2000
press square
wait 2000
CMD
pw-record -P '{ stream.capture.sink=true }' --target "$SINK" --rate 48000 --channels 2 --format s16 rec-$TAG.wav &
REC=$!
sleep 1
setsid nohup distrobox enter ubuntu -- env BC5_LEAN=1 KYTY_BC5_INPUT_CMD=$HOME/bc5-work/rec-$TAG.cmd ~/bc5-work/play-pkg.sh < /dev/null > rec-$TAG.out 2>&1 &
for _ in $(seq 1 60); do pgrep -x kyty_emulator >/dev/null && break; sleep 1; done
T0=$(date +%s)
for s in 300 345; do
  while [ $(( $(date +%s) - T0 )) -lt $s ]; do sleep 1; done
  SHOTS=0180-rec-$TAG ~/bc5-work/shot.sh "t$s" 0 > /dev/null 2>&1
done
while [ $(( $(date +%s) - T0 )) -lt "$SECS" ]; do sleep 1; done
pkill -x kyty_emulator; sleep 3; kill $REC; sleep 1; pkill -9 -x kyty_emulator; sleep 2
cp play-pkg-lean-last.log rec-$TAG.log
restore
ls -la rec-$TAG.wav; cat rec-$TAG.cmd.done
