#!/usr/bin/env bash
# BC5 experiment 0341 (the maintainer's RT-on test) (exp 0328's streamplay0328.sh): run on the laptop while the
# maintainer plays on the "BC5 emulator (test 0341)" shortcut. Three passive streams from the box (all only read;
# nothing on the box is started, stopped or written):
#   raw/maintainer-test/kernel-stream.txt   the kernel log (journalctl -k -f);
#   raw/maintainer-test/journal-stream.txt  the GPU journal of each play started after this script (play-pkg.sh's
#                                           ~/bc5-data/captures/play-<time>/gc/direct.log; the newest is followed),
#                                           only the lines that matter after a hang or a machine-down;
#   raw/maintainer-test/playlog-stream.txt  the emulator's output of each start (the test launcher's
#                                           ~/bc5-work/exp0341/play/play-<time>.log; the newest is followed): the
#                                           backend's exp 0341 lines (switches, the periodic shadow summary, the
#                                           histogram) and crash lines.
# All end once the "MAINTAINER PLAYING | test 0341, the maintainer" BOX-LOCK line is gone (after it was seen) or after
# 4 hours. sampleplay0341.sh is the fourth, separate stream (memory once a minute).
# usage: streamplay0341.sh   (in the background; it returns when the streams end)
out="$(cd "$(dirname "$0")" && pwd)/raw/maintainer-test"
mkdir -p "$out"
SSH="ssh -o ServerAliveInterval=10 -o ServerAliveCountMax=6 bc250"
# shellcheck disable=SC2016
LIVE='grep -q "^MAINTAINER PLAYING | test 0341, the maintainer" ~/bc5-work/BOX-LOCK 2>/dev/null'
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
      ( tail -n +1 -F \"\$cur/direct.log\" | grep --line-buffered -a -E 'timeout probe|TIMEOUT|^ring order: STALE|GIVEN UP|NOT served|fault|refus' ) & tp=\$!
    fi
    if $LIVE; then seen=1; elif [ \$seen = 1 ]; then break; fi
    sleep 3
  done
  sleep 20; [ -n \"\$tp\" ] && { pkill -P \$tp; kill \$tp 2>/dev/null; }; exit 0" >> "$out/journal-stream.txt" 2>&1 &
$SSH "t0=\$(date +%s); end=\$(( t0 + 14400 )); seen=0; cur=; tp=
  while [ \$(date +%s) -lt \$end ]; do
    f=; $LIVE && f=\$(find ~/bc5-work/exp0341/play -maxdepth 1 -name 'play-*.log' -newermt @\$t0 2>/dev/null | sort | tail -1)
    if [ -n \"\$f\" ] && [ \"\$f\" != \"\$cur\" ]; then
      [ -n \"\$tp\" ] && { pkill -P \$tp; kill \$tp 2>/dev/null; }
      cur=\$f; echo \"play log \$cur from \$(date +%T)\"
      ( tail -n +1 -F \"\$cur\" | grep --line-buffered -a -E 'experiment 0341|ray tracing|Access violation|Segmentation|Aborted|terminate called|TIMEOUT|fault' ) & tp=\$!
    fi
    if $LIVE; then seen=1; elif [ \$seen = 1 ]; then break; fi
    sleep 3
  done
  sleep 20; [ -n \"\$tp\" ] && { pkill -P \$tp; kill \$tp 2>/dev/null; }; exit 0" >> "$out/playlog-stream.txt" 2>&1 &
wait
echo "streams ended $(date +%T)" >&2
