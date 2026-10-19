#!/usr/bin/env bash
# BC5: from START s after the emulator appears, every GAP s, COUNT times: eu-stack of the threads named in NAMES (comma list) -> OUT
set -u
START=$1; COUNT=$2; GAP=$3; OUT=$4; NAMES=$5
: > "$OUT"
for _ in $(seq 1 300); do PID=$(pgrep -x kyty_emulator | head -1); [ -n "$PID" ] && break; sleep 1; done
[ -z "${PID:-}" ] && { echo "no emulator" >> "$OUT"; exit 1; }
sleep "$START"
IFS=, read -ra WANT <<< "$NAMES"
for i in $(seq 1 "$COUNT"); do
  kill -0 "$PID" 2>/dev/null || break
  echo "== sample $i $(date +%T.%N | cut -c1-12)" >> "$OUT"
  TIDS=""
  for t in /proc/$PID/task/*; do
    c=$(cat $t/comm 2>/dev/null); for w in "${WANT[@]}"; do [ "$c" = "$w" ] && { TIDS="$TIDS $(basename $t):$c:$(cut -d" " -f3 $t/stat)"; }; done
  done
  echo "threads:$TIDS" >> "$OUT"
  eu-stack -m -p "$PID" 2>/dev/null | awk -v tids="$TIDS" "BEGIN{n=split(tids,a,\" \"); for(k=1;k<=n;k++){split(a[k],b,\":\"); w[\"TID \" b[1] \":\"]=1}} /^TID/{keep=(\$0 in w)} keep" >> "$OUT"
  sleep "$GAP"
done
echo DONE >> "$OUT"
