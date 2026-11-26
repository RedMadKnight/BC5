#!/usr/bin/env bash
# BC5 experiment 0291: one arm from the laptop, attended. It runs run0291.sh <tag> <report> <secs> on the box and,
# meanwhile, watches the laptop's kernel stream (raw/kernel-stream.txt, kstream0291.sh): at the first new amdgpu line
# it stops the run's emulator (the box holds this experiment's lock, so the emulator is the run's own), as the top
# session asked. After the run, gpu0291.py scores the run's journal (O_DIRECT, 15 MB/s).
# usage: arm0291.sh <tag> <report|-> [secs]   (on the laptop, from the experiment directory)
set -u
TAG=${1:?tag}; REPORT=${2:?report}; SECS=${3:-300}
D="$(cd "$(dirname "$0")" && pwd)"; K=$D/raw/kernel-stream.txt
base=$(grep -ci amdgpu "$K" 2> /dev/null); base=${base:-0}
( while sleep 5; do
    n=$(grep -ci amdgpu "$K" 2> /dev/null); n=${n:-0}
    if [ "$n" -gt "$base" ]; then
      echo "$(date +%T) new amdgpu line in the kernel stream: stopping the run's emulator" | tee -a "$D/raw/$TAG-stopped.txt"
      ssh bc250 'grep -q "^exp 0291 | run '"$TAG"' " ~/bc5-work/BOX-LOCK && pkill -x kyty_emulator'
      break
    fi
  done ) &
WP=$!
ssh -o ServerAliveInterval=30 bc250 "~/bc5-work/exp0291/run0291.sh $TAG $REPORT $SECS"
kill "$WP" 2> /dev/null
J=$(ssh bc250 "cut -d' ' -f1 ~/bc5-work/exp0291/raw/$TAG-journal-path.txt")
ssh bc250 "pgrep '^kyty_emulator' > /dev/null && { echo 'an emulator runs: scoring later'; exit 0; }; cd ~/bc5-work/exp0291 && nice -n 19 python3 -I gpu0291.py 15 100 $TAG=$J | tee raw/$TAG-gpu.txt"
