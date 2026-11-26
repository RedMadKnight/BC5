#!/usr/bin/env bash
# BC5 experiment 0244: during one bench run's frozen view, run cap0244.py every STEP seconds (at most N times) on the
# run's emulator, from the run's first frozen-view shot (r-<tag>/shots/*-ts00.png) on; stops when the emulator or the
# run's BOX-LOCK line is gone. Captures go to ~/bc5-data/priv/exp0244/<tag> (mode 700; the title's data).
# usage: capl0244.sh <tag> <N> <STEP s> <udK+0xOFF:image|buffer> [...]   (on the box, started by hand while the run is attended)
set -u
TAG=$1; N=$2; STEP=$3; shift 3
R=$HOME/bc5-work/exp0194/r-$TAG
P=$HOME/bc5-data/priv/exp0244/$TAG
mkdir -p "$P" && chmod 700 "$HOME/bc5-data/priv/exp0244" "$P"
for _ in $(seq 1 120); do ls "$R/shots/" 2>/dev/null | grep -q ts00 && break; sleep 2; done
JD=$(ls -td ~/bc5-data/captures/play-*/gc | head -1)
for k in $(seq -w 1 "$N"); do
  grep -q "exp 0244 | bench $TAG " ~/bc5-work/BOX-LOCK 2>/dev/null || { echo "lock gone: stop"; break; }
  EP=$(pgrep -x kyty_emulator) || { echo "no emulator: stop"; break; }
  python3 -I "$HOME/bc5-work/exp0244/cap0244.py" "$EP" "$JD/direct.log" "$P/cap$k" "$@" > /dev/null 2>> "$P/errors.txt"
  echo "cap$k at $(date +%T) after $(ls "$R/shots/" | grep ts | tail -1)"
  sleep "$STEP"
done
du -sh "$P" | cut -f1
