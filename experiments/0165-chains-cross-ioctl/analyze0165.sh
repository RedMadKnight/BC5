#!/usr/bin/env bash
# exp 0165: per run N (801..803): the capture dir from box-claims start time, chains0165.py over t0..t1, excerpts into ~/bc5-work/exp0165/
cd ~/bc5-work; mkdir -p exp0165; T0=${T0:-155}; T1=${T1:-200}
for N in ${RUNS:-804 805 803}; do
  st=$(grep "exp0165 run $N started" box-claims.txt | tail -1 | sed "s/.*started \([0-9:]*\).*/\1/")
  [ -n "$st" ] || continue
  D=$(ls -d ~/bc5-data/captures/play-$(date +%Y%m%d)-${st:0:2}${st:3:2} 2>/dev/null | head -1)
  [ -d "$D" ] || D=$(ls -td ~/bc5-data/captures/play-* | head -3 | tail -1)
  echo "=== run $N (started $st, capture $D)"
  python3 chains0165.py run$N-stderr.log cpu-$N.txt $D/gc/direct.log $T0 $T1
  grep -E "chains:|chain hold|mec rebuild|cond-past|GIVEN UP|CYCLE|FAILED|TIMEOUT" $D/gc/direct.log | tail -6
  grep -E "videoout trace" run$N-stderr.log | awk "NR % 5 == 1" > exp0165/videoout-$N-sampled.txt
  grep -E "^chains:|chain hold|mec rebuild|^cpu-wait|FAILED|TIMEOUT|^gc ioctl" $D/gc/direct.log | awk "/^cpu-wait/ {c++; if (c % 50 != 1) next} {print}" > exp0165/journal-$N-excerpt.txt
  cp cpu-$N.txt exp0165/; cp dmesg-$N-after.txt exp0165/kernel-$N-after.txt; cp drive$N.log exp0165/
  grep -c "GCVM_L2_PROTECTION_FAULT\|amdgpu.*fault\|timeout\|reset" dmesg-$N-after.txt
done
