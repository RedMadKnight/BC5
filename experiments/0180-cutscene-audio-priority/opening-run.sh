#!/usr/bin/env bash
# BC5 (experiment 0180): the second title's opening cutscene by script (start screen, slot list,
# down twice to the empty slot 3, challenge level, as the run of 09:53), 330 s, normal build.
# The saves are put back to ~/bc5-work/save-backup-0180-0953 before and after (the run writes slot 3).
# Prints, for t 150-300 s (the cutscene: daytime forest, then the night jungle from ~195 s): the
# audio seconds of the main port that pushed under 98 % or cleared the queue, the frame rate, and
# the frame gaps over 150 ms. usage: opening-run.sh <tag> "<env>"
TAG=$1; ENVS=$2
cd ~/bc5-work
BK=save-backup-0180-0953; SD=_SaveData/PPSA03671
restore() {
  cp -a "$BK/." "$SD/"
  for d in "$SD"/*/; do d=${d%/}; [ -e "$BK/$(basename "$d")" ] || rm -r -- "$d"; done
  diff -rq "$BK" "$SD" > /dev/null || echo "SAVES DIFFER from $BK"
}
pgrep -x kyty_emulator >/dev/null && { echo busy; exit 1; }
restore
printf 'wait 85000\npress cross\nwait 20000\npress down\nwait 800\npress down\nwait 800\npress cross\nwait 30000\npress cross\nwait 8000\npress cross\n' > op-$TAG.cmd
setsid nohup distrobox enter ubuntu -- env KYTY_BC5_INPUT_CMD=$HOME/bc5-work/op-$TAG.cmd $ENVS ~/bc5-work/play-pkg.sh < /dev/null > op-$TAG.out 2>&1 &
for _ in $(seq 1 60); do pgrep -x kyty_emulator >/dev/null && break; sleep 1; done
P=$(pgrep -x kyty_emulator | head -1)
[ -n "${SAMPLE:-}" ] && ( python3 -I ~/bc5-work/audio-thread-sampler.py "$P" 195 265 ats-$TAG.txt &)
( XDG_RUNTIME_DIR=/run/user/$(id -u) timeout 340 pw-top -b > pwtop-$TAG.txt 2>&1 & )
sleep 228; SHOTS=0180-op ~/bc5-work/shot.sh "$TAG-230" 0 > /dev/null 2>&1
NICE=$(for t in /proc/$P/task/*; do c=$(cat $t/comm); case "$c" in AK::AudioOutThr|AK::JobWrkr-Acm|PulseMainloop|SDLAudioP2|Render\ Thread|Job\ Bk\ 0) s=$(cat $t/stat); s=${s#*) }; set -- $s; printf "%s=%s " "$c" "${17}";; esac; done)
sleep 100
cp play-pkg-last.log op-$TAG.log
pkill -x kyty_emulator; sleep 4; pkill -9 -x kyty_emulator; sleep 3
restore
echo "$TAG  nice: $NICE"
grep -a "^audio trace" op-$TAG.log | grep " port 0 " | awk -v tag="$TAG" '{t=$4+0; if (t<150||t>=300) next; n++; for(i=1;i<=NF;i++){ if ($i=="(rate") r=$(i+1)+0; if ($i=="clears,") c=$(i-1)+0 } if (r<0.98||c>0) {bad++; list=list sprintf(" %d(%.2f/%d)", t, r, c)} cl+=c} END{printf "   audio t150-300: %d of %d s off (rate<0.98 or cleared), %d clears:%s\n", bad, n, cl, list}'
grep -a "^fps counter" op-$TAG.log | awk '{t=$4+0; if (t<150||t>=300) next; n++; f=$6/$9; s+=f; if (mn==""||f<mn) mn=f; match($0,/longest gap ([0-9.]+)/,g); if (g[1]+0>150) {gg++}; if (g[1]+0>mx) mx=g[1]+0} END{printf "   frames t150-300: %.1f flips/s, lowest second %.0f, %d s with a gap over 150 ms, longest %.0f ms\n", s/n, mn, gg, mx}'
grep -a "AudioOut: PulseMainloop" op-$TAG.log | head -1
# PipeWire's own counters (pw-top, cumulative per node): the output device's and the emulator's
# 8-channel stream's errors (xruns) over the run, and the graph's quantum.
awk '/kyty_emulator$/ && / F32LE 8 / {e=$9+0; if (e0=="") e0=e; e1=e; q[$3]++} /alsa_output.usb-Plantronics/ {s=$9+0; if (s0=="") s0=s; s1=s; sq[$3]++} END{printf "   pipewire: stream errors %d, headset errors %d, quantum", e1-e0, s1-s0; for (k in sq) if (k>0) printf " %s(%d)", k, sq[k]; printf "\n"}' pwtop-$TAG.txt
