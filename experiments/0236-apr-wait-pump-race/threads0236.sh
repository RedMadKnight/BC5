#!/usr/bin/env bash
# BC5 experiment 0236: per sampler file of exps 0214-0229 (cpu0216.sh/cpu0214.sh format, "t <uptime> <comm> ..."),
# the number of APR thread samples, the samples of the wait thread (bc5-apr-wait), the workers seen and the span.
# Laptop-side, read-only. usage: threads0236.sh <experiments dir>
cd "$1" || exit 1
for f in $(grep -l "^# cpu02" */raw/*.txt 2> /dev/null); do
  n=$(grep -c "^t " "$f")
  w=$(grep -c " bc5-apr-wait " "$f")
  q=$(grep -o " bc5-apr-q[0-9]" "$f" | sort -u | tr -d ' ' | tr '\n' ' ')
  first=$(grep -m1 "^t " "$f" | awk '{print $2}')
  last=$(grep "^t " "$f" | tail -1 | awk '{print $2}')
  echo "$f samples=$n bc5-apr-wait=$w workers=[ $q] span=$(awk -v a="$first" -v b="$last" 'BEGIN{printf "%.0f", b-a}')s"
done
