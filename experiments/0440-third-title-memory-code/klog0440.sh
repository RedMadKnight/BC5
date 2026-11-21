#!/usr/bin/env bash
# Experiment 0440: the kernel log, streamed to the laptop for one run. It ends itself when the exp0440 lock line
# is gone (PROMPT.md section 2) and is bounded: 3 min for the line to appear, 20 min in all (LESSONS R64, R67).
# From the laptop:  ssh bc250 'bash ~/bc5-work/exp0440/klog0440.sh' > klog-<tag>.txt
# After the run, check on the box: pgrep -u "$USER" -a journalctl  (expect no line from this script).
set -u
L=$HOME/bc5-work/BOX-LOCK
journalctl -k -f -n 0 -o short-precise &
J=$!
trap 'kill "$J" 2>/dev/null; wait "$J" 2>/dev/null' EXIT HUP INT TERM PIPE
seen=0
for i in $(seq 1 600); do
  if grep -q '^exp0440 ' "$L" 2>/dev/null; then seen=1; elif [ $seen = 1 ]; then break; fi
  if [ $seen = 0 ] && [ "$i" -gt 90 ]; then break; fi
  sleep 2
done
sleep 2
