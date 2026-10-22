#!/usr/bin/env bash
# BC5 experiment 0218: stream the box's kernel log into raw/kernel-stream.txt (run on the laptop) for the play only.
# It ends by itself once the play is over (BOX-LOCK no longer ours and no emulator) or after 70 minutes:
# exp 0211's stream outlived its run and kept appending to a committed file.
out="$(cd "$(dirname "$0")" && pwd)/raw/kernel-stream.txt"
ssh -o ServerAliveInterval=30 bc250 '
  journalctl -k -f -o short-iso-precise --since -2min & jp=$!
  end=$(( $(date +%s) + 4200 ))
  sleep 60
  while [ $(date +%s) -lt $end ]; do
    grep -q "play exp 0218" ~/bc5-work/BOX-LOCK 2>/dev/null || pgrep -x kyty_emulator >/dev/null || break
    sleep 20
  done
  sleep 30
  kill $jp' >> "$out" 2>&1
echo "kernel stream ended $(date +%T)" >&2
