#!/usr/bin/env bash
# Experiment 0439: the kernel log, streamed to whoever holds this script's stdin (LESSONS R67).
# From the laptop:  sleep 86400 | ssh bc250 'bash ~/bc5-work/exp0439/klog0439.sh' > klog-<tag>.txt &
# journalctl dies with the stream: when the ssh channel (our stdin) closes, `cat` returns and the trap kills it.
# After a stop, check on the box: pgrep -u "$USER" -a journalctl  (expect no line from this script).
set -u
journalctl -k -f -n 0 -o short-precise &
J=$!
trap 'kill "$J" 2>/dev/null; wait "$J" 2>/dev/null' EXIT HUP INT TERM PIPE
cat > /dev/null
