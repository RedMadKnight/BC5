#!/usr/bin/env bash
# BC5 experiment 0260: run on the laptop before the catch run starts. Two passive streams from the box, as the box
# supervisor arranged for this run (both only read; nothing on the box is started, stopped or written):
#   raw/kernel-stream.txt   the kernel log (journalctl -k -f), as exp 0254's kstream0254b.sh;
#   raw/journal-stream.txt  from the first GPU journal created after this script starts (play-pkg.sh's
#                           ~/bc5-data/captures/play-<time>/gc/direct.log), only the lines that matter after a machine-
#                           down: the probe's, TIMEOUT, give-ups, unserved two-ring waits, the hold summaries, the
#                           prefix's lines, faults. The full journal stays on the box (synced up to the probe's end).
# Each ends by itself once the run is over (no "exp 0260" BOX-LOCK line and no emulator, after it has started) or after
# 35 minutes. usage: stream0260.sh   (in the background; it returns when both streams end)
out="$(cd "$(dirname "$0")" && pwd)/raw"
mkdir -p "$out"
SSH="ssh -o ServerAliveInterval=10 -o ServerAliveCountMax=6 bc250"
# the box-side loop: wait until the run has started (lock line or emulator), then until it is over
WATCH='end=$(( $(date +%s) + 2100 )); seen=0
  while [ $(date +%s) -lt $end ]; do
    if grep -q "exp 0260" ~/bc5-work/BOX-LOCK 2>/dev/null || pgrep -x kyty_emulator >/dev/null; then seen=1; elif [ $seen = 1 ]; then break; fi
    sleep 5
  done
  sleep 20'
$SSH "journalctl -k -f -o short-precise --since -1min & jp=\$!
  $WATCH
  kill \$jp" >> "$out/kernel-stream.txt" 2>&1 &
$SSH "t0=\$(date +%s); d=
  while [ -z \"\$d\" ] && [ \$(( \$(date +%s) - t0 )) -lt 2100 ]; do
    d=\$(find ~/bc5-data/captures -maxdepth 2 -name gc -newermt @\$t0 2>/dev/null | head -1); [ -z \"\$d\" ] && sleep 2
  done
  [ -n \"\$d\" ] || { echo 'no new capture directory'; exit 0; }
  echo \"journal \$d/direct.log\"
  while [ ! -e \"\$d/direct.log\" ]; do sleep 1; done
  ( tail -n +1 -F \"\$d/direct.log\" | grep --line-buffered -a -E 'timeout probe|TIMEOUT|GIVEN UP|NOT served|^hold tail: [0-9]+ holds|^cs prefix|fault|^aliases' ) & tp=\$!
  $WATCH
  pkill -P \$tp; kill \$tp 2>/dev/null; exit 0" >> "$out/journal-stream.txt" 2>&1 &
wait
echo "streams ended $(date +%T)" >&2
