#!/usr/bin/env bash
# fpscmp.sh <run> ... : from the host log's "fps counter" lines (KYTY_BC5_FPS_COUNTER=1, exp 0172;
# printed whatever the logging switch), the gameplay window t 130-230 s: mean flips a second, the
# slowest second, the frame-interval tally and the longest interval.
for r in "$@"; do
  log=~/bc5-work/run$r-stderr.log; [ -r "$log" ] || { echo "run $r: no log"; continue; }
  grep -a "^fps counter" "$log" | awk -v r="$r" '{
    t=$4+0; if (t<130 || t>=230) next
    n++; f=$6+0; secs=$9+0; fps=f/secs; s+=fps; if (n==1 || fps<lo) lo=fps; if (fps>hi) hi=fps
    match($0,/longest gap ([0-9.]+) ms/,g); if (g[1]+0>mx) mx=g[1]+0
    match($0,/over 40 ms ([0-9]+), over 70 ms ([0-9]+)/,o); o40+=o[1]; o70+=o[2]; fr+=f
  } END { if (n==0) {print "run " r ": no fps counter lines in the window"; exit}
    printf "run %s: %.1f flips/s over %d s (slowest second %.1f, fastest %.1f); %d frames, intervals over 40 ms: %d, over 70 ms: %d; longest %.1f ms\n", r, s/n, n, lo, hi, fr, o40, o70, mx }'
done
