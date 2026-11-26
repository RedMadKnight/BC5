#!/usr/bin/env bash
# BC5 experiment 0254: stream the box's kernel log into raw/kernel-stream.txt (run on the laptop) for the chain only
# (exp 0218's kstream.sh). It ends by itself once the chain is over (no "exp 0254" BOX-LOCK line and no emulator) or
# after 25 minutes.
out="$(cd "$(dirname "$0")" && pwd)/raw/kernel-stream.txt"
mkdir -p "$(dirname "$out")"
ssh -o ServerAliveInterval=10 -o ServerAliveCountMax=6 bc250 '
  journalctl -k -f -o short-precise --since -1min & jp=$!
  end=$(( $(date +%s) + 1500 ))
  sleep 60
  while [ $(date +%s) -lt $end ]; do
    grep -q "^exp 0254 |" ~/bc5-work/BOX-LOCK 2>/dev/null || pgrep "^kyty_emulator" >/dev/null || break
    sleep 15
  done
  sleep 20
  kill $jp' >> "$out" 2>&1
echo "kernel stream ended $(date +%T)" >&2
