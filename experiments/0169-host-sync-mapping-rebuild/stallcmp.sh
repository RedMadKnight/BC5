#!/usr/bin/env bash
# stallcmp.sh <run> ... : for each run's capture (by its host-log start time), the gameplay window's
# frame count, frames > 250 ms and > 500 ms, the sum of time in those frames, the audio rate
# deviations, the flips per second (VideoOut trace) and the game thread's host time per frame.
for r in "$@"; do
  log=~/bc5-work/run$r-stderr.log; [ -r "$log" ] || { echo "run $r: no log"; continue; }
  stamp=$(head -1 "$log" | awk '{split($3, t, ":"); d = $2; gsub("-", "", d); print d "-" t[1] t[2]}')
  cap=~/bc5-data/captures/play-$stamp
  [ -r "$cap/gc/direct.log" ] || { echo "run $r: capture $cap not found"; continue; }
  grep -a "frame profile" "$cap/gc/direct.log" | awk -v r="$r" '{match($0,/t ([0-9.]+) s, ([0-9.]+) ms since/,m); t=m[1]; g=m[2]; if (t>=130 && t<230) {n++; tot+=g; if (g>70) c++; if (g>250) {a++; sa+=g}; if (g>500) {b++; sb+=g}; match($0,/inside the host ([0-9.]+) ms \(sync ([0-9.]+), hints ([0-9.]+), prepare ([0-9.]+), list ([0-9.]+), cs ([0-9.]+)/,h); ih+=h[1]; sy+=h[2]; pr+=h[4]; cs+=h[6]; match($0,/GPU busy ([0-9.]+) ms in ([0-9]+) jobs \(\+([0-9]+)/,q); gb+=q[1]; gj+=q[2]; rj+=q[3]}} END{if (n==0) {print "run " r ": no frames"; exit}; printf "run %s: gameplay 130-230 s: %d frames (mean %.1f ms), >70 ms: %d, >250 ms: %d (%.1f s), >500 ms: %d (%.1f s); host per frame %.1f ms (sync %.1f, prepare %.1f, cs %.1f); GPU busy %.1f ms, jobs %.0f + %.0f ring\n", r, n, tot/n, c, a, sa/1000, b, sb/1000, ih/n, sy/n, pr/n, cs/n, gb/n, gj/n, rj/n}'
  grep -a "audio trace" "$log" | grep -v "(pad)" | awk -v r="$r" '{for(i=1;i<=NF;i++) if($i=="(rate") {x=$(i+1); sub(/\),/,"",x)}; for(i=1;i<=NF;i++) if($i=="t") t=$(i+1); if (t>=130 && t<230) {n++; if (x<0.95||x>1.05) d++; if (x<lo||lo=="") lo=x; if (x>hi) hi=x}} END{printf "run %s: audio seconds %d, off by >5%%: %d (rate %s..%s)\n", r, n, d, lo, hi}'
  grep -a "videoout trace.*flips mode" "$log" | awk -v r="$r" '{for(i=1;i<=NF;i++) if($i=="t") t=$(i+1); for(i=1;i<=NF;i++) if($i=="mode1") m=$(i+1); if (t>=130 && t<230) {s+=m; n++; if (m<20) low++}} END{if (n) printf "run %s: %.1f flips/s over %d s, seconds under 20 fps: %d\n", r, s/n, n, low}'
done
