#!/usr/bin/env bash
# BC5 exp 0439: the speckle run (the top session's step 5 of 11-21 ~22:45): the build with ph439 (the draw's keys before and
# after the pass at the sample flips, key dumps beside the surface dumps), cm439 (CB_COLOR_CONTROL modes in the title's GFX
# jobs) and cp439 (BC5_0439_DCC_COPY=1: the surface and keys saved before the pass, restored after the present's read).
# Two runs of t3s.sh in script mode, 60 s each, the same switch set as 21:51 (cross at 45 s; the 65-s check is past the
# bound): first in place (tag -ip), then the copy mode (tag -cp). Each run takes and drops the box lock itself (t3s.sh).
#   t3u.sh <md5-8 of the private normal build>
set -u
PIN=${1:?md5}
cd "$HOME/bc5-work/exp0439" || exit 1
for v in ip cp; do
  x=""; [ $v = cp ] && x="BC5_0439_DCC_COPY=1"
  echo "== $(date +%T) run $v"
  T3S_TAG=-$v T3S_BOUND=60 T3S_EXTRA="$x" bash k439/t3s.sh "$PIN" unset "" script 2>&1 | tail -40
  echo "== keys: $(cat runs/t3s-vunset-$v.keys 2> /dev/null | tr '\n' ' ')"
  P=runs/t3s-vunset-$v/play-last.log
  grep -a 'tag ph439\|tag cm439\|tag cp439' $P | head -40 | cut -c1-900
done
