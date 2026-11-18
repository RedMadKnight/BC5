#!/usr/bin/env bash
# BC5 exp 0429: the read-only look at the thread dumps at the fault (the wait catcher, KYTY_BC5_0429_WAITS=1) of the
# crashes of this experiment: per run, how many Job Bk workers were running and on which CPUs, the Hi workers' state
# and last wake, and every job thread or the owner that was NOT asleep in futex (a host call would show here).
# usage (on the box): bash ~/bc5-work/exp0429/faultread0429.sh h429M6 h429M7 ...
set -u
R=$HOME/bc5-work/exp0429/n/raw
for t in "$@"; do
  L=$R/$t-play.log
  [ -s "$L" ] || { echo "== $t: no play log"; continue; }
  n=$(grep -ac 'exp 0429 thread at fault' "$L")
  [ "$n" -gt 0 ] || { echo "== $t: no dump (catcher off or another class)"; continue; }
  f=$(grep -a 'waits at the fault' "$L" | head -1)
  echo "== $t: $n threads; $f"
  bk=$(grep -a 'thread at fault' "$L" | grep -a "'Job Bk" | grep -ac ' state R ')
  bkcpu=$(grep -a 'thread at fault' "$L" | grep -a "'Job Bk" | grep -a ' state R ' | sed -E 's/.* cpu ([0-9]+) .*/\1/' | tr '\n' ' ')
  echo "   Job Bk running: $bk (CPUs $bkcpu)"
  echo "   Hi workers: $(grep -a 'thread at fault' "$L" | grep -a "'Job Hi" | sed -E "s/.*'Job Hi ([0-9])' state (.) cpu ([0-9]+) syscall ([^ ]+).*last ready-to-run ([0-9.]+) ms.*/\1:\2\/cpu\3\/sc\4\/wake \5ms/" | tr '\n' ' ')"
  echo "   job threads or the owner not in futex:"
  grep -a 'thread at fault' "$L" | grep -a "'Job \|'game-main'\|'MainThread'" | grep -av ' syscall 202 ' | sed 's/schedstat \[[^]]*\]//' | cut -c30-190
  echo "   other running threads: $(grep -a 'thread at fault' "$L" | grep -a ' state R ' | grep -av "'Job " | sed -E "s/.*'([^']*)' state R cpu ([0-9]+).*/\1@\2/" | tr '\n' ' ')"
  echo "   D state: $(grep -a 'thread at fault' "$L" | grep -a ' state D ' | sed -E "s/.*'([^']*)' state D cpu ([0-9]+) syscall ([^ ]+).*/\1@\2\/sc\3/" | tr '\n' ' ')"
done
