#!/usr/bin/env bash
# BC5 exp 0371 (the maintainer's play after the 23:30 reboot, normal shortcut; slowdowns and the pad's haptics after a
# replug): run on the laptop. Passive streams from the box (only reads):
#   raw/kernel-stream.txt   the kernel log (journalctl -k -f);
#   raw/playlog-stream.txt  ~/bc5-work/play-pkg-last.log: audio, pad, crash and fault lines.
# Both end once the "MAINTAINER PLAYING | play 2330" BOX-LOCK line is gone (after it was seen) or after 4 hours.
# usage: stream0371.sh   (in the background)
out=/c/Users/kjani/Downloads/bc5/bc5/experiments/0371-maintainer-play-slowdowns/raw
mkdir -p "$out"
SSH="ssh -o ServerAliveInterval=10 -o ServerAliveCountMax=6 bc250"
# shellcheck disable=SC2016
LIVE='grep -q "^MAINTAINER PLAYING | play 2330" ~/bc5-work/BOX-LOCK 2>/dev/null'
$SSH "journalctl -k -f -o short-precise --since -3min & jp=\$!
  end=\$(( \$(date +%s) + 14400 )); seen=0
  while [ \$(date +%s) -lt \$end ]; do
    if $LIVE; then seen=1; elif [ \$seen = 1 ]; then break; fi
    sleep 5
  done
  sleep 20; kill \$jp" >> "$out/kernel-stream.txt" 2>&1 &
$SSH "( tail -n +1 -F ~/bc5-work/play-pkg-last.log | grep --line-buffered -a -i -E 'AudioOut|controller|DualSense|haptic|vibration|rumble|gamepad|joystick|Access violation|Segmentation|Aborted|terminate called|TIMEOUT|fault|job-arena|ray tracing' ) & tp=\$!
  end=\$(( \$(date +%s) + 14400 )); seen=0
  while [ \$(date +%s) -lt \$end ]; do
    if $LIVE; then seen=1; elif [ \$seen = 1 ]; then break; fi
    sleep 5
  done
  sleep 20; pkill -P \$tp; kill \$tp 2>/dev/null; exit 0" >> "$out/playlog-stream.txt" 2>&1 &
wait
echo "streams ended $(date +%T)" >&2
