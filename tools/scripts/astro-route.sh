#!/usr/bin/env bash
# BC5 (2026-10-21): ASTRO BOT from its start into gameplay by script (title screen, X, the save loads,
# then a minute of walking and jumping), SECS seconds, with extra environment; the title's saves are
# backed up once to ~/bc5-work/save-backup-astro and put back before and after the run.
# Prints the frame rate (KYTY_BC5_FPS_COUNTER) per 20-s window, the main audio port's seconds off real
# time and its queue clears (KYTY_BC5_AUDIO_TRACE), fence timeouts in the log, and amdgpu resets or
# ring timeouts the kernel logged during the run. usage: astro-route.sh <tag> [secs] ["VAR=value ..."]
TAG=$1; SECS=${2:-200}; ENVS=${3:-}
cd ~/bc5-work
SD=_SaveData/PPSA21564; BK=save-backup-astro
pgrep -x kyty_emulator >/dev/null && { echo busy; exit 1; }
[ -d "$BK" ] || cp -a "$SD" "$BK"
restore() {
  cp -a "$BK/." "$SD/"
  for d in "$SD"/*/; do d=${d%/}; [ -e "$BK/$(basename "$d")" ] || rm -r -- "$d"; done
  diff -rq "$BK" "$SD" > /dev/null && echo "saves as in $BK" || echo "SAVES DIFFER from $BK"
}
restore
{
  echo "wait 40000"; echo "press cross"; echo "wait 25000"; echo "press cross"; echo "wait 15000"
  for i in $(seq 1 20); do
    echo "stick l 128 0"; echo "wait 1500"; echo "press cross"; echo "wait 600"
    echo "stick l 255 128"; echo "wait 1000"; echo "press cross"; echo "wait 400"
  done
  echo "stick l 128 128"
} > astro-$TAG.cmd
K0=$(sudo -n dmesg 2>/dev/null | grep -c -i -E "amdgpu.*(ring .* timeout|GPU reset|reset succeeded|reset begin)")
setsid nohup distrobox enter ubuntu -- env KYTY_BC5_INPUT_CMD=$HOME/bc5-work/astro-$TAG.cmd KYTY_BC5_FPS_COUNTER=1 KYTY_BC5_AUDIO_TRACE=1 KYTY_BC5_MEASURE=1 $ENVS ~/bc5-work/play-astro.sh < /dev/null > astro-$TAG.out 2>&1 &
for _ in $(seq 1 60); do pgrep -x kyty_emulator >/dev/null && break; sleep 1; done
T0=$(date +%s); ENDED=""
while [ $(( $(date +%s) - T0 )) -lt "$SECS" ]; do
  pgrep -x kyty_emulator >/dev/null || { ENDED="ended by itself at $(( $(date +%s) - T0 )) s"; break; }
  [ -n "${SHOT_AT:-}" ] && [ $(( $(date +%s) - T0 )) -eq "$SHOT_AT" ] && { XDG_RUNTIME_DIR=/run/user/1000 WAYLAND_DISPLAY=wayland-0 spectacle -b -n -a -o ~/bc5-work/shots-mh/astro-$TAG.png >/dev/null 2>&1; }
  sleep 1
done
cp play-last.log astro-$TAG.log
pkill -x kyty_emulator; sleep 4; pkill -9 -x kyty_emulator; sleep 3
restore
K1=$(sudo -n dmesg 2>/dev/null | grep -c -i -E "amdgpu.*(ring .* timeout|GPU reset|reset succeeded|reset begin)")
echo "== $TAG: ${ENVS:-defaults}; ${ENDED:-stopped at $SECS s}"
grep -a "^fps counter" astro-$TAG.log | awk '{t=$4+0; w=int(t/20); n[w]++; f[w]+=$6/$9; if ($0 ~ /over 70 ms [1-9]/) s[w]++} END {for (k in n) printf "%d:%.1f(%d) ", k*20, f[k]/n[k], s[k]}' | tr ' ' '\n' | sort -n | tr '\n' ' '; echo " <- fps per 20 s (seconds with a gap over 70 ms)"
grep -a "^audio trace" astro-$TAG.log | grep -v "(pad)" | awk '{t=$4+0; if (t<20) next; n++; for(i=1;i<=NF;i++){ if ($i=="(rate") r=$(i+1)+0; if ($i=="clears,") c=$(i-1)+0 } if (r<0.98||c>0) bad++; cl+=c} END{printf "audio t20+: %d of %d port-seconds off, %d clears\n", bad, n, cl}'
echo "fence timeouts in the log: $(grep -a -c -i "fence timeout" astro-$TAG.log); amdgpu reset/timeout lines in the kernel log during the run: $((K1 - K0))"
