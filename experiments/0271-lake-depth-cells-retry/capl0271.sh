#!/usr/bin/env bash
# BC5 experiment 0271 (exp 0266's capl0266.sh, renamed): during one bench run's frozen view, read the night lake's whole
# depth memory, 0x1129ec0000 .. 0x112c800000 (0x2940000 bytes): the depth data of every render size with their HTILE
# and stencil (F309), read-only through /proc/<pid>/mem (exp 0212's mem0212.py), every STEP seconds and at most N times,
# from the run's first frozen-view shot on; stops when the emulator or the run's BOX-LOCK line is gone. With it, the
# G-buffer target 0x113f230000 (32_FLOAT, ADDR_SW_64KB_R_X; exp 0240) up to the 3328x1872 extent (26 x 15 blocks of 64
# KiB = 0x1860000), read right after the depth memory. Reads go to ~/bc5-data/priv/exp0271/<tag> (mode 700; the title's
# data).
# usage: capl0271.sh <tag> <N> <STEP s>   (on the box, started by hand while the run is attended)
set -u
TAG=$1; N=$2; STEP=$3
R=$HOME/bc5-work/exp0194/r-$TAG
P=$HOME/bc5-data/priv/exp0271/$TAG
mkdir -p "$P" && chmod 700 "$HOME/bc5-data/priv/exp0271" "$P"
for _ in $(seq 1 120); do ls "$R/shots/" 2>/dev/null | grep -q ts00 && break; sleep 2; done
for k in $(seq -w 1 "$N"); do
  grep -q "exp 0271 | bench $TAG " ~/bc5-work/BOX-LOCK 2>/dev/null || { echo "lock gone: stop"; break; }
  EP=$(pgrep -x kyty_emulator) || { echo "no emulator: stop"; break; }
  t=$(date +%T.%N | cut -c1-12)
  python3 -I "$HOME/bc5-work/exp0212/mem0212.py" dump "$EP" "$P/cap$k" 1129ec0000:2940000 113f230000:1860000 >> "$P/errors.txt" 2>&1
  echo "cap$k at $t after $(ls "$R/shots/" | grep ts | tail -1)" | tee -a "$P/caps.txt"
  sleep "$STEP"
done
du -sh "$P" | cut -f1
