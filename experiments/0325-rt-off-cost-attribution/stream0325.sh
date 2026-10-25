#!/usr/bin/env bash
# BC5 experiment 0325: run on the laptop before the s6n runs (s6n0325.sh) start (exp 0290's stream0290.sh, exp 0260's stream0260.sh). Two passive streams from the box, as
# the box supervisor arranged for this run (both only read; nothing on the box is started, stopped or written):
#   raw/kernel-stream.txt   the kernel log (journalctl -k -f), as exp 0254's kstream0254b.sh;
#   raw/journal-stream.txt  each GPU journal created after this script starts (play-pkg.sh's
#                           ~/bc5-data/captures/play-<time>/gc/direct.log; the newest is followed, the next run's replaces
#                           it), only the lines that matter after a machine-down: the probe's, TIMEOUT, give-ups,
#                           unserved two-ring waits, the hold summaries, the prefix's lines, faults. The full journal stays
#                           on the box (synced up to the probe's end).
# Each ends by itself once the chain is over (its "exp 0325 | ver run" BOX-LOCK line gone, after it was seen) or after
# 75 minutes; journals are followed only while that line is there, so other sessions' runs are never read.
# usage: stream0325.sh   (in the background; it returns when both streams end)
out="$(cd "$(dirname "$0")" && pwd)/raw"
mkdir -p "$out"
SSH="ssh -o ServerAliveInterval=10 -o ServerAliveCountMax=6 -o IdentityFile=~/.ssh/id_ed25519_bc250 -o IdentitiesOnly=yes kjaniszewski@192.168.10.66"  # the LAN address: the bc250 alias (Tailscale) does not answer from this laptop tonight
# shellcheck disable=SC2016
LIVE='grep -q "^exp 0325 | ver run" ~/bc5-work/BOX-LOCK 2>/dev/null'  # only this chain's lock: other sessions' runs are not read
$SSH "journalctl -k -f -o short-precise --since -1min & jp=\$!
  end=\$(( \$(date +%s) + 4500 )); seen=0
  while [ \$(date +%s) -lt \$end ]; do
    if $LIVE; then seen=1; elif [ \$seen = 1 ]; then break; fi
    sleep 5
  done
  sleep 20; kill \$jp" >> "$out/kernel-stream.txt" 2>&1 &
$SSH "t0=\$(date +%s); end=\$(( t0 + 4500 )); seen=0; cur=; tp=
  while [ \$(date +%s) -lt \$end ]; do
    d=; $LIVE && d=\$(find ~/bc5-data/captures -maxdepth 2 -name gc -newermt @\$t0 2>/dev/null | sort | tail -1)
    if [ -n \"\$d\" ] && [ \"\$d\" != \"\$cur\" ] && [ -e \"\$d/direct.log\" ]; then
      [ -n \"\$tp\" ] && { pkill -P \$tp; kill \$tp 2>/dev/null; }
      cur=\$d; echo \"journal \$cur/direct.log from \$(date +%T)\"
      ( tail -n +1 -F \"\$cur/direct.log\" | grep --line-buffered -a -E 'timeout probe|TIMEOUT|descriptor \(exp 0302\)|table \(exp 0302\)|ray tracing|mec rebuild|^ring order: STALE|GIVEN UP|NOT served|^hold tail: [0-9]+ holds|^cs prefix|fault|^aliases' ) & tp=\$!
    fi
    if $LIVE; then seen=1; elif [ \$seen = 1 ]; then break; fi
    sleep 3
  done
  sleep 20; [ -n \"\$tp\" ] && { pkill -P \$tp; kill \$tp 2>/dev/null; }; exit 0" >> "$out/journal-stream.txt" 2>&1 &
wait
echo "streams ended $(date +%T)" >&2
