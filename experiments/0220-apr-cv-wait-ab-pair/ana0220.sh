#!/usr/bin/env bash
# BC5 experiment 0220: read-only analysis of the pair on the box, at nice 19: both GPU journals with O_DIRECT at
# 15 MB/s (exp 0214's ra0214.py: flips, long frames, TIMEOUT/fault/reopen/given-up lines; exp 0216's long0216.py: the
# frames over 1 s), and exp 0200's ana0200.py on both samplers (5-s windows: the cinematic clock, faults, PSI).
# usage: ana0220.sh   (on the box, after both arms; chain0220.sh runs it under its lock)
set -u
E=$HOME/bc5-work/exp0220; R=$E/raw
A=""
for T in A1 B1; do
  [ -s "$R/$T-journal-path.txt" ] || continue
  J=$(cut -d' ' -f1 "$R/$T-journal-path.txt")
  A="$A $T=$J"
  nice -n 19 python3 -I "$HOME/bc5-work/exp0216/long0216.py" 15 1000 "$J" > "$R/$T-long-frames.txt" 2>&1
  nice -n 19 python3 -I "$HOME/bc5-work/exp0200/ana0200.py" "$R/$T-sample.txt" "$R/$T-play-pkg.log" - 5 > "$R/$T-ana5.txt" 2>&1
done
# shellcheck disable=SC2086
nice -n 19 python3 -I "$HOME/bc5-work/exp0214/ra0214.py" 15 100 $A > "$R/frames.txt" 2>&1
cat "$R/frames.txt"
wc -l "$R"/*-long-frames.txt "$R"/*-ana5.txt
