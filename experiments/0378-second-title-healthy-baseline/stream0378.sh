#!/usr/bin/env bash
# BC5 exp 0378: the box's kernel log streamed to the laptop for the s6n0378.sh run. Ends
# itself once the "top exp 0378 | second-title baseline" BOX-LOCK line is gone (after it was seen), or after 30 minutes.
# usage: stream0378.sh <tag>   (on the laptop, in the background)
TAG=${1:?tag}
out=/c/Users/kjani/Downloads/bc5/bc5-0378/experiments/0378-second-title-healthy-baseline/raw
# shellcheck disable=SC2016
ssh -o ServerAliveInterval=10 -o ServerAliveCountMax=6 bc250 "journalctl -k -f -o short-precise -n 0 & jp=\$!
  end=\$(( \$(date +%s) + 1800 )); seen=0
  while [ \$(date +%s) -lt \$end ]; do
    if grep -q '^top exp 0378 | second-title baseline' ~/bc5-work/BOX-LOCK 2>/dev/null; then seen=1; elif [ \$seen = 1 ]; then break; fi
    sleep 5
  done
  sleep 15; kill \$jp" >> "$out/$TAG-kernel-stream.txt" 2>&1
echo "stream ended $(date +%T)" >&2
