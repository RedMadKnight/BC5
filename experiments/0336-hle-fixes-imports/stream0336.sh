#!/usr/bin/env bash
# BC5 experiment 0336: run in the supervising session before s6n0336.sh starts (exp 0333's stream0333.sh). Two passive
# the box (both only read; nothing on the box is started, stopped or written):
#   raw/kernel-stream.txt   the kernel log (journalctl -k -f), as exp 0254's kstream0254b.sh;
#   raw/journal-stream.txt  each GPU journal created after this script starts (play-pkg.sh's
#                           ~/bc5-data/captures/play-<time>/gc/direct.log; the newest is followed, the next run's replaces
#                           it), only the lines that matter after a machine-down: the probe's, TIMEOUT, give-ups,
#                           unserved two-ring waits, the hold summaries, the prefix's lines, faults. The full journal stays
#                           on the box (synced up to the probe's end).
# Each ends by itself once the chain is over (its "cloud exp 0336 | s6n run" BOX-LOCK line gone, after it was seen) or after
# 45 minutes; journals are followed only while that line is there, so other sessions' runs are never read.
# usage: stream0336.sh   (in the background; it returns when both streams end)
out="$(cd "$(dirname "$0")" && pwd)/raw"
mkdir -p "$out"
SSH="ssh -o ServerAliveInterval=10 -o ServerAliveCountMax=6 bc250"
# shellcheck disable=SC2016
LIVE='grep -q "^cloud exp 0336 | s6n run" ~/bc5-work/BOX-LOCK 2>/dev/null'  # only this chain's lock: other sessions' runs are not read
$SSH "journalctl -k -f -o short-precise --since -1min & jp=\$!
  end=\$(( \$(date +%s) + 2700 )); seen=0
  while [ \$(date +%s) -lt \$end ]; do
    if $LIVE; then seen=1; elif [ \$seen = 1 ]; then break; fi
    sleep 5
  done
  sleep 20; kill \$jp" >> "$out/kernel-stream.txt" 2>&1 &
$SSH "t0=\$(date +%s); end=\$(( t0 + 2700 )); seen=0; cur=; tp=
  while [ \$(date +%s) -lt \$end ]; do
    d=; $LIVE && d=\$(find ~/bc5-data/captures -maxdepth 2 -name gc -newermt @\$t0 2>/dev/null | sort | tail -1)
    if [ -n \"\$d\" ] && [ \"\$d\" != \"\$cur\" ] && [ -e \"\$d/direct.log\" ]; then
      [ -n \"\$tp\" ] && { pkill -P \$tp; kill \$tp 2>/dev/null; }
      cur=\$d; echo \"journal \$cur/direct.log from \$(date +%T)\"
      ( tail -n +1 -F \"\$cur/direct.log\" | grep --line-buffered -a -E 'timeout probe|TIMEOUT|zero scan|by name \(|MiB in all-zero|zero map \(exp 0336\)|views: .* MiB reserved|learned: fault|descriptor \(exp 0302\)|table \(exp 0302\)|mec rebuild|^ring order: STALE|GIVEN UP|NOT served|^hold tail: [0-9]+ holds|^cs prefix|fault|^aliases' ) & tp=\$!
    fi
    if $LIVE; then seen=1; elif [ \$seen = 1 ]; then break; fi
    sleep 3
  done
  sleep 20; [ -n \"\$tp\" ] && { pkill -P \$tp; kill \$tp 2>/dev/null; }; exit 0" >> "$out/journal-stream.txt" 2>&1 &
wait
echo "streams ended $(date +%T)" >&2
