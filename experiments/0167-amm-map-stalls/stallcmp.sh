#!/usr/bin/env bash
# stallcmp.sh <run> ... : for each run's capture (by its host-log start time), the gameplay window's
# frame count, frames > 250 ms and > 500 ms, the sum of time in those frames, and the audio rate
# deviations.
for r in "$@"; do
  log=~/bc5-work/run$r-stderr.log; [ -r "$log" ] || { echo "run $r: no log"; continue; }
  stamp=$(head -1 "$log" | awk '{split($3, t, ":"); d = $2; gsub("-", "", d); print d "-" t[1] t[2]}')
  cap=~/bc5-data/captures/play-$stamp
  [ -r "$cap/gc/direct.log" ] || { echo "run $r: capture $cap not found"; continue; }
  grep -a "frame profile" "$cap/gc/direct.log" | awk -v r="$r" '{match($0,/t ([0-9.]+) s, ([0-9.]+) ms since/,m); t=m[1]; g=m[2]; if (t>=130 && t<230) {n++; if (g>250) {a++; sa+=g}; if (g>500) {b++; sb+=g}}} END{printf "run %s: gameplay 130-230 s: %d frames, >250 ms: %d (%.1f s), >500 ms: %d (%.1f s)\n", r, n, a, sa/1000, b, sb/1000}'
  grep -a "audio trace" "$log" | grep -v "(pad)" | awk -v r="$r" '{for(i=1;i<=NF;i++) if($i=="(rate") {x=$(i+1); sub(/\),/,"",x)}; for(i=1;i<=NF;i++) if($i=="t") t=$(i+1); if (t>=130 && t<230) {n++; if (x<0.95||x>1.05) d++}} END{printf "run %s: audio seconds %d, off by >5%%: %d\n", r, n, d}'
done
