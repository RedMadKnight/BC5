#!/usr/bin/env bash
# BC5 (experiment 0181): one opening (New Game, slot 3) on the normal build with the title's own
# sound dumped for t 150-300 s (KYTY_BC5_AUDIO_DUMP_FROM/SECONDS, before the host's output path)
# and the headset's mix recorded (pw-record from the default output's monitor), to compare by ear.
# PipeWire's downmix of the 7.1 stream is normalized (PIPEWIRE_PROPS) unless NORMALIZE=0.
TAG=$1; SECS=${2:-310}
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
D=~/bc5-work/dump-$TAG; rm -rf "$D"; mkdir -p "$D"
cp ~/bc5-work/long-cmd.txt cap-$TAG.cmd
NORM='{ channelmix.normalize = true }'; [ "${NORMALIZE:-1}" = 0 ] && NORM='{ }'
if [ "${RECORDER:-parecord}" = parecord ]; then parecord --device="$SINK.monitor" --latency-msec=500 --rate=48000 --channels=2 --format=s16le --file-format=wav rec-$TAG.wav & else pw-record -P "{ stream.capture.sink=true }" --target "$SINK" --rate 48000 --channels 2 --format s16 rec-$TAG.wav & fi
REC=$!
( timeout 330 pw-top -b > pwtop-cap-$TAG.txt 2>&1 & )
sleep 1
setsid nohup distrobox enter ubuntu -- env KYTY_BC5_INPUT_CMD=$HOME/bc5-work/cap-$TAG.cmd "PIPEWIRE_PROPS=$NORM" ${ENVX:-} ~/bc5-work/play-pkg.sh < /dev/null > cap-$TAG.out 2>&1 &
for _ in $(seq 1 60); do pgrep -x kyty_emulator >/dev/null && break; sleep 1; done
T0=$(date +%s)
while [ $(( $(date +%s) - T0 )) -lt 200 ]; do sleep 1; done
pw-dump > pwdump-$TAG.json 2>/dev/null
python3 -I - pwdump-$TAG.json <<'PY'
import json, sys
for o in json.load(open(sys.argv[1])):
    if o.get("type") != "PipeWire:Interface:Node": continue
    p = (o.get("info") or {}).get("props") or {}
    if p.get("application.name") == "kyty_emulator" or "Audio Stream" in str(p.get("media.name", "")):
        print("node", o["id"], {k: p[k] for k in p if k.startswith(("channelmix", "node.latency", "audio.channels", "media.name"))})
PY
while [ $(( $(date +%s) - T0 )) -lt "$SECS" ]; do sleep 1; done
pkill -x kyty_emulator; sleep 3; kill $REC; sleep 1; pkill -9 -x kyty_emulator; sleep 2
cp play-pkg-last.log cap-$TAG.log
restore
grep -a "audio dump:\|SDL audio driver" cap-$TAG.log | head -8
ls -la "$D" rec-$TAG.wav
# PipeWire's error counters over the run (cumulative per node): the emulator's stream(s), the
# recorder, the headset.
awk '$1=="R" && $9 ~ /^[0-9]+$/ {name=$NF; if ($0 ~ /Audio Stream|kyty_emulator/) name="emulator-" $2; if ($0 ~ /pw-record|parecord/) name="recorder"; if ($0 ~ /Plantronics/) name="headset"; if (!(name in first)) first[name]=$9; last[name]=$9} END {for (n in last) if (last[n]-first[n] > 0 || n=="recorder" || n=="headset") printf "   pipewire errors %s: %d\n", n, last[n]-first[n]}' pwtop-cap-$TAG.txt
