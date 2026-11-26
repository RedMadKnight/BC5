#!/usr/bin/env bash
# BC5 experiment 0385: the kernel log for the laptop while exp 0385 holds the box (exp 0291's kstream0291.sh, on the box
# side). Ends by itself once our BOX-LOCK lines are gone and no emulator runs, or after 32 minutes.
# usage: from the laptop, ssh ... 'bash ~/bc5-work/exp0385/kstream0385.sh' > raw/kernel-stream.txt
journalctl -k -f -n 0 -o short-precise & jp=$!
end=$(( $(date +%s) + 1920 ))
sleep 30
while [ "$(date +%s)" -lt "$end" ]; do
  grep -q "^water session exp 0385" ~/bc5-work/BOX-LOCK 2>/dev/null || pgrep "^kyty_emulator" > /dev/null || break
  sleep 10
done
sleep 5
kill "$jp"
