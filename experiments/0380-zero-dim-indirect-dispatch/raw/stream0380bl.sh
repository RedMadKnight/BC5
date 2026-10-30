#!/usr/bin/env bash
# BC5 exp 0380 (stream0380r1.sh): the box's kernel log streamed to the laptop for the B loop (loop0380b.sh). The lock
# line flips between the loop's and each try's, so this ends once loop-done appears, after no "top exp 0380 |" line
# for 3 checks in a row (once seen), after 2.5 hours, or when the box goes down (the ssh drops at a reboot).
# usage: stream0380bl.sh <prefix>   (on the laptop, in the background)
PFX=${1:?prefix}
out=/c/Users/kjani/Downloads/bc5/bc5-0380/experiments/0380-zero-dim-indirect-dispatch/raw/runs
mkdir -p "$out"
# shellcheck disable=SC2016
ssh -o ServerAliveInterval=10 -o ServerAliveCountMax=6 bc250 "journalctl -k -f -o short-precise -n 0 & jp=\$!
  end=\$(( \$(date +%s) + 9000 )); seen=0; gone=0
  while [ \$(date +%s) -lt \$end ]; do
    [ -e ~/bc5-work/exp0380r1/run/loop-done ] && [ \$seen = 1 ] && break
    if grep -q '^top exp 0380 |' ~/bc5-work/BOX-LOCK 2>/dev/null; then seen=1; gone=0; elif [ \$seen = 1 ]; then gone=\$((gone + 1)); [ \$gone -ge 3 ] && break; fi
    sleep 5
  done
  sleep 15; kill \$jp" >> "$out/$PFX-kernel-stream.txt" 2>&1
echo "stream ended $(date +%T) (ssh rc $?)" >> "$out/$PFX-kernel-stream.txt"
