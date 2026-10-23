#!/usr/bin/env bash
# BC5 experiment 0242: stream the box's kernel log into raw/kernel-stream.txt (run on the laptop) for the run only.
# It ends by itself once the run is over (exp 0242's BOX-LOCK gone and no emulator) or after 30 minutes (exp 0218).
out="$(cd "$(dirname "$0")" && pwd)/raw/kernel-stream.txt"
ssh -o ServerAliveInterval=30 bc250 '
  journalctl -k -f -o short-iso-precise --since -2min & jp=$!
  end=$(( $(date +%s) + 1800 ))
  sleep 60
  while [ $(date +%s) -lt $end ]; do
    grep -q "^exp 0242 | cutscene re-check" ~/bc5-work/BOX-LOCK 2>/dev/null || pgrep "^kyty_emulator" >/dev/null || break
    sleep 20
  done
  sleep 30
  kill $jp' >> "$out" 2>&1
echo "kernel stream ended $(date +%T)" >&2
