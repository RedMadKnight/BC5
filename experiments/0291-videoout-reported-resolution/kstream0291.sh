#!/usr/bin/env bash
# BC5 experiment 0291: stream the box's kernel log into raw/kernel-stream.txt (run on the laptop) while the experiment
# holds the box: as long as ~/bc5-work/exp0291/ACTIVE exists, an exp 0291 BOX-LOCK line is held or an emulator runs,
# at most 40 minutes (exp 0218's kstream.sh, which ends by itself).
out="$(cd "$(dirname "$0")" && pwd)/raw/kernel-stream.txt"
mkdir -p "$(dirname "$out")"
ssh -o ServerAliveInterval=30 bc250 '
  journalctl -k -f -o short-iso-precise --since -1min & jp=$!
  end=$(( $(date +%s) + 2400 ))
  sleep 30
  while [ $(date +%s) -lt $end ]; do
    [ -e ~/bc5-work/exp0291/ACTIVE ] || grep -q "^exp 0291 |" ~/bc5-work/BOX-LOCK 2>/dev/null || pgrep "^kyty_emulator" >/dev/null || break
    sleep 15
  done
  sleep 20
  kill $jp' >> "$out" 2>&1
echo "kernel stream ended $(date +%T)" >&2
