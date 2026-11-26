#!/usr/bin/env bash
# BC5 exp 0439: up to three Performance runs with BC5_DIRECT_ACB_RINGS=0 (every acb on the GFX ring; the top session's
# order of 11-22 06:40): each ends at the hang or runs its 600 s; stop after the first one that runs to its bound.
cd "$HOME/bc5-work/exp0439" || exit 1
for k in 1 2 3; do
  echo "######## run r0-$k $(date +%T)"
  T3P6_SUFFIX=r0$k T3P6_FLAT=1 T3P6_MORE="BC5_DIRECT_ACB_RINGS=0" bash k439/t3p6.sh 389521e4
  grep -a -q "GPU FAULT" runs/t3s-vunset-pr0$k/play-last.log || { echo "######## r0-$k: no GPU fault, series ends"; break; }
done
