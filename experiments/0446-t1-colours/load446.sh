#!/usr/bin/env bash
# exp 0446: background disk load for a run. usage: load446.sh reader|writer|both <delay s> <duration s> <log>
#   reader: cat of the third title's installed files (not the first title's image) to /dev/null
#   writer: a random 1 GiB chunk appended with fsync to ~/bc5-data/x446-load/w.bin, at most 20 GiB; removed at the end
set -u
kind=$1; delay=$2; dur=$3; log=$4
D=$HOME/bc5-data/x446-load; mkdir -p "$D"
sleep "$delay"
echo "$(date +%T) load $kind start" >> "$log"
pids=()
if [ "$kind" = reader ] || [ "$kind" = both ]; then
    ( find "$HOME/bc5-data/games/TITLE3" -type f -size +1M -print0 | xargs -0 cat > /dev/null 2>&1 ) & pids+=($!)
fi
if [ "$kind" = writer ] || [ "$kind" = both ]; then
    [ -s "$D/chunk" ] || head -c 1G /dev/urandom > "$D/chunk"
    ( for i in $(seq 20); do dd if="$D/chunk" of="$D/w.bin" bs=4M oflag=append conv=notrunc,fsync status=none || break; done ) & pids+=($!)
fi
sleep "$dur"
for p in "${pids[@]}"; do pkill -P "$p" 2> /dev/null; kill "$p" 2> /dev/null; done
wait 2> /dev/null
rm -f "$D/w.bin"
echo "$(date +%T) load $kind end; w.bin removed" >> "$log"
