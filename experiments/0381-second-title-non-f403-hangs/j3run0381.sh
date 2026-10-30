#!/usr/bin/env bash
# BC5 exp 0381: one attended J3 start, driven from the laptop: the kernel stream (it ends itself after 240 s), the start
# (start0381j3.sh), TERM at 120 s of emulator time or on the first gfx timeout, then j3check0381.py on the box.
# usage: j3run0381.sh <tag> <switch 0|1> <hold_us|default> <out-dir>
TAG=$1; SW=$2; HOLD=$3; OUT=$4; K=$OUT/kern-$TAG.txt; HERE=$(cd "$(dirname "$0")" && pwd)
ssh bc250 'timeout 240 journalctl -k -f -n 0 -o short-precise' > "$K" 2>&1 &
KP=$!
ssh bc250 'bash -s' -- "$TAG" "$SW" "$HOLD" < "$HERE/start0381j3.sh" > "$OUT/start-$TAG.txt" 2>&1 &
SP=$!
why=""
for _ in $(seq 1 90); do
    sleep 3
    kill -0 $SP 2> /dev/null || { why="launcher ended"; break; }
    grep -q 'ring gfx_0.0.0 timeout' "$K" && { why="gfx timeout"; break; }
    e=$(timeout 20 ssh -o ConnectTimeout=10 bc250 'P=$(pgrep -x kyty_emulator | head -1); [ -n "$P" ] && ps -o etimes= -p $P')
    [ -n "$e" ] && [ "$e" -ge 120 ] && { why="120 s"; break; }
done
echo "$TAG stop reason: ${why:-loop ended}"
for _ in 1 2 3 4 5 6 7 8 9 10; do timeout 20 ssh -o ConnectTimeout=10 bc250 'P=$(pgrep -x kyty_emulator | head -1); [ -z "$P" ] && { echo "no emulator"; exit 0; }; readlink /proc/$P/exe | grep -q exp0381/kyty_emulator || { echo "not our emulator"; exit 5; }; echo "etimes $(ps -o etimes= -p $P)"; kill -TERM $P' && break; sleep 3; done
wait $SP
cat "$OUT/start-$TAG.txt"
kill $KP 2> /dev/null
ssh bc250 'pgrep -f "^timeout 240 journalctl -k" | xargs -r kill'
echo "faults $(grep -c 'in page starting' "$K"); timeouts $(grep -c 'ring gfx_0.0.0 timeout' "$K"); resets ok $(grep -c 'reset succeeded' "$K")"
grep -o 'address 0x[0-9a-f]*' "$K" | sort -u | head -12
ssh bc250 'G=$(ls -dt $HOME/bc5-data/captures/play-* | head -1); echo "$G"; python3 - "$G/gc/direct.log"' < "$HERE/j3check0381.py"
