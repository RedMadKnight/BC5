#!/usr/bin/env bash
# BC5 experiment 0248: during one bench run's frozen view, read the night lake's depth buffer (0x1129ec0000, Z_32_FLOAT,
# ADDR_SW_64KB_Z_X; exp 0245) and the G-buffer target (0x113f230000, 32_FLOAT, ADDR_SW_64KB_R_X; exp 0240) at the same
# moment, read-only through /proc/<pid>/mem (exp 0212's mem0212.py), every STEP seconds and at most N times, from the
# run's first frozen-view shot on; stops when the emulator or the run's BOX-LOCK line is gone. Both extents are
# 3328x1872 at 4 bytes in 64-KiB blocks of 128x128 elements: 26 x 15 blocks = 0x1860000 bytes (exp 0205's layout()).
# Reads go to ~/bc5-data/priv/exp0248/<tag> (mode 700; the title's data).
# usage: capl0248.sh <tag> <N> <STEP s>   (on the box, started by hand while the run is attended)
set -u
TAG=$1; N=$2; STEP=$3
R=$HOME/bc5-work/exp0194/r-$TAG
P=$HOME/bc5-data/priv/exp0248/$TAG
mkdir -p "$P" && chmod 700 "$HOME/bc5-data/priv/exp0248" "$P"
for _ in $(seq 1 120); do ls "$R/shots/" 2>/dev/null | grep -q ts00 && break; sleep 2; done
for k in $(seq -w 1 "$N"); do
  grep -q "exp 0248 | bench $TAG " ~/bc5-work/BOX-LOCK 2>/dev/null || { echo "lock gone: stop"; break; }
  EP=$(pgrep -x kyty_emulator) || { echo "no emulator: stop"; break; }
  t=$(date +%T.%N | cut -c1-12)
  python3 -I "$HOME/bc5-work/exp0212/mem0212.py" dump "$EP" "$P/cap$k" 1129ec0000:1860000 113f230000:1860000 >> "$P/errors.txt" 2>&1
  echo "cap$k at $t after $(ls "$R/shots/" | grep ts | tail -1)" | tee -a "$P/caps.txt"
  sleep "$STEP"
done
du -sh "$P" | cut -f1
