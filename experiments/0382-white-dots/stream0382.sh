#!/usr/bin/env bash
# BC5 experiment 0382 (exp 0379's stream0379t.sh): the box's kernel log streamed to the laptop for one s6n0382.sh arm.
# Ends itself once the arm's "white-dots exp 0382 | arm <tag>" BOX-LOCK line is gone (after it was seen), or after 25
# minutes.
# usage: stream0382.sh <tag>   (on the laptop, in the background, started before the arm)
TAG=${1:?tag}
out=/c/Users/kjani/Downloads/bc5/bc5-0382/experiments/0382-white-dots/raw
mkdir -p "$out"
# shellcheck disable=SC2016
ssh -o ServerAliveInterval=10 -o ServerAliveCountMax=6 bc250 "journalctl -k -f -o short-precise -n 0 & jp=\$!
  end=\$(( \$(date +%s) + 1500 )); seen=0
  while [ \$(date +%s) -lt \$end ]; do
    if grep -q '^white-dots exp 0382 | arm $TAG ' ~/bc5-work/BOX-LOCK 2>/dev/null; then seen=1; elif [ \$seen = 1 ]; then break; fi
    sleep 5
  done
  sleep 15; kill \$jp" >> "$out/$TAG-kernel-stream.txt" 2>&1
echo "stream ended $(date +%T)" >&2
