#!/usr/bin/env bash
# BC5 exp 0439: the CB_SHADER_MASK run (the top session's GO of 11-21 ~22:30): t3s.sh in script mode, 150 s, crosses at
# 45 s and 125 s, BC5_0439_DC_SHADER_MASK=15, the same switch set as 21:51; first in place (tag -sm), then, only if the
# pass changed key bytes, the copy mode (tag -smcp, BC5_0439_DCC_COPY=1). Each run takes and drops the lock (t3s.sh).
#   t3v.sh <md5-8 of the private normal build>
set -u
PIN=${1:?md5}
cd "$HOME/bc5-work/exp0439" || exit 1
one() { # $1 tag, $2 extra switches
  echo "== $(date +%T) run $1"
  T3S_TAG=-$1 T3S_BOUND=150 T3S_PRESSES="45 125" T3S_EXTRA="$2" bash k439/t3s.sh "$PIN" unset "" script 2>&1 | tail -40
  echo "== keys: $(cat runs/t3s-vunset-$1.keys 2> /dev/null | tr '\n' ' ')"
  grep -a 'tag sm439\|tag ph439): .*AFTER' runs/t3s-vunset-$1/play-last.log | head -3 | cut -c1-200
  grep -a 'tag ph439): .*AFTER' runs/t3s-vunset-$1/play-last.log | grep -ao 'pass [0-9]* index [0-9]\|clear codes.*' | paste - - | tail -12
}
one sm "BC5_0439_DC_SHADER_MASK=15"
ch=$(grep -a 'tag ph439): .*AFTER' runs/t3s-vunset-sm/play-last.log | grep -aoE '[0-9]+ of [0-9]+ key bytes changed' | awk '{s += $1} END {print s + 0}')
echo "== key bytes changed by the pass over the sample flips: $ch"
if [ "$ch" -gt 0 ]; then one smcp "BC5_0439_DC_SHADER_MASK=15 BC5_0439_DCC_COPY=1"; else echo "== no change: no copy-mode run"; fi
