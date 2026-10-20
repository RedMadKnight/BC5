#!/usr/bin/env bash
# BC5 (experiment 0181): what the headset hears, recorded without losses: parecord from the default
# output's monitor (PipeWire's PulseAudio layer, real-time data thread, 500 ms server buffer), the
# lean build, from the second title's start through the opening into combat and walking.
# pw-top counts the recorder's and the headset's errors. Saves put back before and after.
TAG=$1; SECS=${2:-400}
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
SINK=$(pactl get-default-sink)
cat > fin-$TAG.cmd <<'CMD'
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
wait 6000
press triangle
wait 1500
press square
wait 400
press square
wait 400
press square
wait 1500
stick l 0 128 2500
stick l 128 0 4000
press triangle
wait 1200
press square
wait 400
press square
wait 400
press square
wait 1000
stick l 255 128 3000
stick l 128 0 5000
stick r 255 128 1200
stick l 128 0 5000
wait 2000
press l1
wait 1200
press square
wait 400
press square
wait 400
press square
wait 1500
stick l 128 0 4000
reset
CMD
parecord --device="$SINK.monitor" --latency-msec=500 --rate=48000 --channels=2 --format=s16le --file-format=wav rec-$TAG.wav &
REC=$!
( timeout $((SECS + 20)) pw-top -b > pwtop-fin-$TAG.txt 2>&1 & )
sleep 1
setsid nohup distrobox enter ubuntu -- env BC5_LEAN=1 KYTY_BC5_INPUT_CMD=$HOME/bc5-work/fin-$TAG.cmd ~/bc5-work/play-pkg.sh < /dev/null > fin-$TAG.out 2>&1 &
for _ in $(seq 1 60); do pgrep -x kyty_emulator >/dev/null && break; sleep 1; done
T0=$(date +%s)
for s in 330 360 390; do
  while [ $(( $(date +%s) - T0 )) -lt $s ]; do sleep 1; done
  SHOTS=0181-fin-$TAG ~/bc5-work/shot.sh "t$s" 0 > /dev/null 2>&1
done
while [ $(( $(date +%s) - T0 )) -lt "$SECS" ]; do sleep 1; done
pkill -x kyty_emulator; sleep 3; kill $REC; sleep 1; pkill -9 -x kyty_emulator; pkill -x pw-top; sleep 2
cp play-pkg-lean-last.log fin-$TAG.log
restore
grep -a "SDL audio driver\|AudioOut:" fin-$TAG.log | head -4
awk '$1=="R" && $9 ~ /^[0-9]+$/ {name=$NF; if ($0 ~ /Audio Stream|kyty_emulator/) name="emulator-" $2; if ($0 ~ /parecord/) name="recorder"; if ($0 ~ /Plantronics/) name="headset"; if (!(name in first)) first[name]=$9; last[name]=$9} END {for (n in last) if (last[n]-first[n] > 0 || n=="recorder" || n=="headset") printf "pipewire errors %s: %d\n", n, last[n]-first[n]}' pwtop-fin-$TAG.txt
ls -la rec-$TAG.wav; cat fin-$TAG.cmd.done
