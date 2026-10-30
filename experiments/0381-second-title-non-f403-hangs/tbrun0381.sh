#!/usr/bin/env bash
# BC5 exp 0381: the attended test-build smoke, from the laptop: the kernel stream (it ends itself after 240 s), the start,
# TERM at 120 s of emulator time or on the first gfx timeout, then the summary on the box. Every ssh is bounded.
# usage: tbrun0381.sh <tag> <out-dir>
TAG=$1; OUT=$2; K=$OUT/kern-$TAG.txt; HERE=$(cd "$(dirname "$0")" && pwd)
BSSH="timeout 20 ssh -o ConnectTimeout=10 bc250"
ssh bc250 'timeout 240 journalctl -k -f -n 0 -o short-precise' > "$K" 2>&1 &
KP=$!
ssh bc250 'bash -s' -- "$TAG" < "$HERE/start0381tb.sh" > "$OUT/start-$TAG.txt" 2>&1 &
SP=$!
why=""
for _ in $(seq 1 60); do
    sleep 3
    kill -0 $SP 2> /dev/null || { why="launcher ended"; break; }
    grep -q 'ring gfx_0.0.0 timeout' "$K" && { why="gfx timeout"; break; }
    e=$($BSSH 'P=$(pgrep -x kyty_emulator | head -1); [ -n "$P" ] && ps -o etimes= -p $P')
    [ -n "$e" ] && [ "$e" -ge 120 ] && { why="120 s"; break; }
done
echo "$TAG stop reason: ${why:-loop ended}"
for _ in 1 2 3 4 5; do
    $BSSH 'P=$(pgrep -x kyty_emulator | head -1); [ -z "$P" ] && { echo "no emulator"; exit 0; }; readlink /proc/$P/exe | grep -q exp0381/tb/bin/kyty_emulator || { echo "not our emulator"; exit 5; }; echo "etimes $(ps -o etimes= -p $P)"; kill -TERM $P' && break
    sleep 3
done
wait $SP
cat "$OUT/start-$TAG.txt"
kill $KP 2> /dev/null
$BSSH 'pgrep -f "^timeout 240 journalctl -k" | xargs -r kill'
echo "faults $(grep -c 'in page starting' "$K"); timeouts $(grep -c 'ring gfx_0.0.0 timeout' "$K"); resets ok $(grep -c 'reset succeeded' "$K")"
$BSSH 'TB=$HOME/bc5-work/exp0381/tb; G=$(ls -dt $HOME/bc5-data/captures/play-* | head -1); echo "$G"; cat $TB/raw/'"$TAG"'-start.txt | cut -c1-120; L=$(ls -t $TB/play/play-*.log | head -1); echo "$L"; grep -a -m1 "^== exp 0381" "$L" | cut -c1-170; grep -a -c "zero skip" "$L"; grep -a -m1 "fps counter" "$L" | cut -c1-90; grep -a "fps counter" "$L" | tail -1 | cut -c1-90; grep -a -c "acb state restore" "$G/gc/direct.log"; grep -a -m1 "acb state restore" "$G/gc/direct.log" | cut -c1-150; grep -a "acb state restore" "$G/gc/direct.log" | tail -1 | cut -c1-150; ls $G/gc | grep -c ib-timeout'
