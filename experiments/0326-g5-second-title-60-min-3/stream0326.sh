#!/usr/bin/env bash
# BC5 experiment 0326 (exp 0294's stream0294.sh): run on the laptop while the maintainer plays the G5 attempt. Two
# passive streams from the box (both only read; nothing on the box is started, stopped or written):
#   raw/kernel-stream.txt   the kernel log (journalctl -k -f);
#   raw/journal-stream.txt  the GPU journal of each play started after this script (play-pkg.sh's
#                           ~/bc5-data/captures/play-<time>/gc/direct.log; the newest is followed), only the lines that
#                           matter after a hang or a machine-down: the probe's, TIMEOUT, give-ups, unserved two-ring
#                           waits, faults.
# Both end once the "MAINTAINER PLAYING | G5 attempt 3, exp 0326" BOX-LOCK line is gone (after it was seen) or after
# 4 hours. sample0326.sh is the third, separate stream (memory once a minute).
# usage: stream0326.sh   (in the background; it returns when both streams end)
out="$(cd "$(dirname "$0")" && pwd)/raw"
mkdir -p "$out"
SSH="ssh -o ServerAliveInterval=10 -o ServerAliveCountMax=6 bc250"
# shellcheck disable=SC2016
LIVE='grep -q "^MAINTAINER PLAYING | G5 attempt 3, exp 0326" ~/bc5-work/BOX-LOCK 2>/dev/null'
$SSH "journalctl -k -f -o short-precise --since -1min & jp=\$!
  end=\$(( \$(date +%s) + 14400 )); seen=0
  while [ \$(date +%s) -lt \$end ]; do
    if $LIVE; then seen=1; elif [ \$seen = 1 ]; then break; fi
    sleep 5
  done
  sleep 20; kill \$jp" >> "$out/kernel-stream.txt" 2>&1 &
$SSH "t0=\$(date +%s); end=\$(( t0 + 14400 )); seen=0; cur=; tp=
  while [ \$(date +%s) -lt \$end ]; do
    d=; $LIVE && d=\$(find ~/bc5-data/captures -maxdepth 2 -name gc -newermt @\$t0 2>/dev/null | sort | tail -1)
    if [ -n \"\$d\" ] && [ \"\$d\" != \"\$cur\" ] && [ -e \"\$d/direct.log\" ]; then
      [ -n \"\$tp\" ] && { pkill -P \$tp; kill \$tp 2>/dev/null; }
      cur=\$d; echo \"journal \$cur/direct.log from \$(date +%T)\"
      ( tail -n +1 -F \"\$cur/direct.log\" | grep --line-buffered -a -E 'timeout probe|TIMEOUT|^ring order: STALE|GIVEN UP|NOT served|fault' ) & tp=\$!
    fi
    if $LIVE; then seen=1; elif [ \$seen = 1 ]; then break; fi
    sleep 3
  done
  sleep 20; [ -n \"\$tp\" ] && { pkill -P \$tp; kill \$tp 2>/dev/null; }; exit 0" >> "$out/journal-stream.txt" 2>&1 &
wait
echo "streams ended $(date +%T)" >&2
