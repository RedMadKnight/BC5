#!/usr/bin/env bash
# BC5 experiment 0216: after S1, read-only analysis on the box, at nice 19. The GPU journal is read with O_DIRECT at
# 15 MB/s (exp 0214's ra0214.py: flips, frames over 100/250/1000 ms, TIMEOUT/fault/reopen/given-up lines; long0216.py:
# the frames over 1 s). Exp 0200's ana0200.py gives the cinematic clock and the memory/io pressure per 5 s, for S1
# and, for comparison, exp 0214's S1N. usage: ana0216.sh   (on the box, after S1)
set -u
E=$HOME/bc5-work/exp0216; R=$E/raw; B=$HOME/bc5-work/exp0214/raw
J=$(cut -d' ' -f1 "$R/S1-journal-path.txt")
nice -n 19 python3 -I "$HOME/bc5-work/exp0214/ra0214.py" 15 100 S1="$J" > "$R/S1-frames.txt" 2>&1
nice -n 19 python3 -I "$E/long0216.py" 15 1000 "$J" > "$R/S1-long-frames.txt" 2>&1
nice -n 19 python3 -I "$HOME/bc5-work/exp0200/ana0200.py" "$R/S1-sample.txt" "$R/S1-play-pkg.log" - 5 > "$R/S1-ana5.txt" 2>&1
if [ -r "$B/S1N-sample.txt" ]; then
  nice -n 19 python3 -I "$HOME/bc5-work/exp0200/ana0200.py" "$B/S1N-sample.txt" "$B/S1N-play-pkg.log" - 5 > "$R/S1N-ana5.txt" 2>&1
else
  echo "no $B/S1N-sample.txt" > "$R/S1N-ana5.txt"
fi
cat "$R/S1-frames.txt"; wc -l "$R/S1-long-frames.txt" "$R/S1-ana5.txt" "$R/S1N-ana5.txt"
