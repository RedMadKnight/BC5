#!/usr/bin/env bash
# BC5 experiment 0274 (exp 0271's capl0271.sh, extended): during one bench run's frozen view, every STEP seconds and at
# most N times, read-only through /proc/<pid>/mem (exp 0212's mem0212.py): the night lake's whole depth memory
# (0x1129ec0000 + 0x2940000, F309), the G-buffer target (0x113f230000 + 0x1860000, exp 0240) and the region of the
# 32_FLOAT image pyramid the depth writers' vertex stage reads (0x11d0880000 + 0x20000: mips 128x64 .. 8x4 at
# 0x11d0886000 .. 0x11d0892000, exp 0253's raw/W251a.wr.txt, GS user data 16/24 tables) and the three other images of
# that table (256x256 fmt 20 at 0x1162e60000, 1024x1024 fmt 179 at 0x848789c000, 256x256 fmt 179 at 0x119975c000; read
# generously: 256 KiB, 1 MiB, 256 KiB), as possible victims of stray writes (the RT session, F339). Starts at the run's first
# frozen-view shot; stops when the emulator or the run's BOX-LOCK line is gone. Reads go to ~/bc5-data/priv/exp0274/<tag>
# (mode 700; the title's data).
# usage: capl0274.sh <tag> <N> <STEP s>   (on the box, started by hand while the run is attended)
set -u
TAG=$1; N=$2; STEP=$3
R=$HOME/bc5-work/exp0194/r-$TAG
P=$HOME/bc5-data/priv/exp0274/$TAG
mkdir -p "$P" && chmod 700 "$HOME/bc5-data/priv/exp0274" "$P"
for _ in $(seq 1 120); do ls "$R/shots/" 2>/dev/null | grep -q ts00 && break; sleep 2; done
for k in $(seq -w 1 "$N"); do
  grep -q "exp 0274 | bench $TAG " ~/bc5-work/BOX-LOCK 2>/dev/null || { echo "lock gone: stop"; break; }
  EP=$(pgrep -x kyty_emulator) || { echo "no emulator: stop"; break; }
  t=$(date +%T.%N | cut -c1-12)
  python3 -I "$HOME/bc5-work/exp0212/mem0212.py" dump "$EP" "$P/cap$k" 1129ec0000:2940000 113f230000:1860000 11d0880000:20000 1162e60000:40000 848789c000:100000 119975c000:40000 >> "$P/errors.txt" 2>&1
  echo "cap$k at $t after $(ls "$R/shots/" | grep ts | tail -1)" | tee -a "$P/caps.txt"
  sleep "$STEP"
done
du -sh "$P" | cut -f1
