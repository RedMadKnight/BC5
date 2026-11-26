#!/usr/bin/env bash
# BC5 experiment 0282 (exp 0274's capl0274.sh, changed to bursts): during one bench run's frozen view, every STEP seconds
# and at most N times, one burst of burst0282.py, read-only through /proc/<pid>/mem: K reads of the night lake's depth
# image (0x1129ec0000 + 0x1860000 = 390 blocks of 64 KiB, the largest render size's 26 x 15; F309) started PER ms apart
# (0 = back to back), then one read of the G-buffer target (0x113f230000 + 0x1860000, exp 0240). Starts at the run's
# first frozen-view shot; stops when the emulator or the run's BOX-LOCK line is gone. Reads go to
# ~/bc5-data/priv/exp0282/<tag> (mode 700; the title's data), the per-read times to b<NN>.times.txt next to them.
# usage: capb0282.sh <tag> <N> <STEP s> <K> <PER ms>   (on the box, started by hand while the run is attended)
set -u
TAG=$1; N=$2; STEP=$3; K=$4; PER=$5
R=$HOME/bc5-work/exp0194/r-$TAG
P=$HOME/bc5-data/priv/exp0282/$TAG
mkdir -p "$P" && chmod 700 "$HOME/bc5-data/priv/exp0282" "$P"
for _ in $(seq 1 120); do ls "$R/shots/" 2>/dev/null | grep -q ts00 && break; sleep 2; done
for b in $(seq -w 1 "$N"); do
  grep -q "exp 0282 | bench $TAG " ~/bc5-work/BOX-LOCK 2>/dev/null || { echo "lock gone: stop"; break; }
  EP=$(pgrep -x kyty_emulator) || { echo "no emulator: stop"; break; }
  t=$(date +%T.%N | cut -c1-12)
  python3 -I "$HOME/bc5-work/exp0282/burst0282.py" "$EP" "$P/b$b" "$K" "$PER" 1129ec0000:1860000 113f230000:1860000 > "$P/b$b.times.txt" 2>> "$P/errors.txt"
  echo "b$b at $t after $(ls "$R/shots/" | grep ts | tail -1): $(awk '{printf "%s %s+%s ", $1, $3, $5}' "$P/b$b.times.txt")" | tee -a "$P/caps.txt"
  sleep "$STEP"
done
du -sh "$P" | cut -f1
