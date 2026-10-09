#!/usr/bin/env bash
# BC5 (experiment 0038): N unattended runs of the second title in a row, each summarised in one line:
# exit, GPU faults, failed submissions, the last submission's time and the fps from 250 s on.
# usage: pkg-series.sh FIRST_RUN_NUMBER COUNT SECONDS [extra env assignments...]
set -u
FIRST=$1; COUNT=$2; SECS=$3; shift 3
P=""; for t in $(seq 120 30 $((SECS - 30))); do P="$P$t:cross,"; done; P=${P%,}
OUT=~/bc5-work/series-$FIRST.txt
: > "$OUT"
for i in $(seq 0 $((COUNT - 1))); do
  n=$((FIRST + i))
  env PRINTF_DIR=Silent AUTOPRESS=$P \
    "EAGER_NAMES=RenderGpuWcLarge,RenderGpuWcSmall,RenderGpuRwLarge,RenderGpuRwSmall,CommitIABufferAllocator,AMM,RenderAlloc,Physics,Decal Job Scheduler,VisualEffectInstanceHeap,DynamicHeap,DynamicHeap Small,ComponentHeap,ComponentHeap Small,MaterialHeap,DDLHeap,Physics query allocator" \
    PACK_DIR=$HOME/bc5-data/sysmodules-pack-hle-ampr "$@" \
    distrobox enter ubuntu -- ~/bc5-work/run-pkg.sh $HOME/bc5-data/pkg/game.pkg "$SECS" < /dev/null > ~/bc5-work/run-pkg$n.out 2>&1
  L=$(cat ~/bc5-work/last-pkg)
  ex=$(grep -o "kyty exit [0-9]* after [0-9]* s" ~/bc5-work/run-pkg$n.out)
  faults=$(grep -o "timeout: fault 0x[0-9a-f]*" "$L/gc/direct.log" | awk '{print $3}' | tr "\n" " ")
  failed=$(grep -c FAILED "$L/gc/direct.log")
  last=$(grep -o "timing: #[0-9]* done at t [0-9.]*" "$L/gc/direct.log" | tail -1 | awk '{print $NF}')
  av=$(grep -c "Access violation" "$L/kyty.log")
  fps=$(python3 ~/bc5-work/frameprof.py "$L/gc/direct.log" 250 "$SECS" | head -1)
  echo "run $n: $ex; faults: ${faults:-none}; failed $failed; last submit at $last s; access violations $av; 250 s on: $fps ($L)" >> "$OUT"
done
echo "series done" >> "$OUT"
