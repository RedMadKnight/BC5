#!/usr/bin/env bash
# BC5 exp 0380 (exp 0378's stream0378.sh): the box's kernel log streamed to the laptop for one s6n0380w.sh run. Ends
# itself once the "top exp 0380 | wb run" BOX-LOCK line is gone (after it was seen), or after 30 minutes.
# usage: stream0380.sh <tag>   (on the laptop, in the background)
TAG=${1:?tag}
out=/c/Users/kjani/Downloads/bc5/bc5-0380/experiments/0380-zero-dim-indirect-dispatch/raw/runs
mkdir -p "$out"
# shellcheck disable=SC2016
ssh -o ServerAliveInterval=10 -o ServerAliveCountMax=6 bc250 "journalctl -k -f -o short-precise -n 0 & jp=\$!
  end=\$(( \$(date +%s) + 1800 )); seen=0
  while [ \$(date +%s) -lt \$end ]; do
    if grep -q '^top exp 0380 | wb run' ~/bc5-work/BOX-LOCK 2>/dev/null; then seen=1; elif [ \$seen = 1 ]; then break; fi
    sleep 5
  done
  sleep 15; kill \$jp" >> "$out/$TAG-kernel-stream.txt" 2>&1
echo "stream ended $(date +%T)" >&2
