#!/usr/bin/env bash
# BC5 exp 0381: one attended J2 start, driven from the laptop: the kernel stream (it ends itself after 240 s), the start
# (start0381j2.sh), and TERM at 120 s of emulator time or on the first gfx timeout. usage: j2run0381.sh <n> <out-dir>
N=$1; OUT=$2; K=$OUT/kern-J2-$N.txt; HERE=$(cd "$(dirname "$0")" && pwd)
ssh bc250 'timeout 240 journalctl -k -f -n 0 -o short-precise' > "$K" 2>&1 &
KP=$!
ssh bc250 'bash -s' -- "$N" < "$HERE/start0381j2.sh" > "$OUT/start-J2-$N.txt" 2>&1 &
SP=$!
why=""
for _ in $(seq 1 90); do
    sleep 3
    kill -0 $SP 2> /dev/null || { why="launcher ended"; break; }
    grep -q 'ring gfx_0.0.0 timeout' "$K" && { why="gfx timeout"; break; }
    e=$(ssh bc250 'P=$(pgrep -x kyty_emulator | head -1); [ -n "$P" ] && ps -o etimes= -p $P')
    [ -n "$e" ] && [ "$e" -ge 120 ] && { why="120 s"; break; }
done
echo "stop reason: ${why:-loop ended}"
ssh bc250 'P=$(pgrep -x kyty_emulator | head -1); [ -z "$P" ] && { echo "no emulator"; exit 0; }; readlink /proc/$P/exe | grep -q exp0381/kyty_emulator || { echo "not our emulator"; exit 5; }; echo "etimes $(ps -o etimes= -p $P)"; kill -TERM $P'
wait $SP
echo "launcher done: $(cat "$OUT/start-J2-$N.txt" | tail -3)"
kill $KP 2> /dev/null
ssh bc250 'pgrep -f "^timeout 240 journalctl -k" | xargs -r kill'
echo "faults $(grep -c 'in page starting' "$K"); timeouts $(grep -c 'ring gfx_0.0.0 timeout' "$K"); resets ok $(grep -c 'reset succeeded' "$K")"
grep -o 'address 0x[0-9a-f]*' "$K" | sort -u | head -12
