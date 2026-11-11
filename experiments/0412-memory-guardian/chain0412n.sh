#!/usr/bin/env bash
# BC5 exp 0412: the rest of the night of 2026-11-10/11 as one chain on the box (setsid nohup, no ssh needed): waits for
# series c, then the forget arm again (c1zof ended in a GPU ring reset at 99 s, before the load), the two ASTRO BOT runs
# of 600 s, and the forget arm without the zero skip. Each step guards and locks by itself. A file $N/STOP ends the chain
# between steps; so does the clock past 0135.
set -u
X=$HOME/bc5-work/exp0412; N=$X/night
stop() { [ -e "$N/STOP" ] || { h=$(date +%H%M); [ "$h" -lt 1200 ] && [ "$h" -ge 135 ]; }; }
calm() { for _ in $(seq 1 36); do pgrep '^kyty_emulator' > /dev/null || pgrep -x bc5-mount > /dev/null || [ -s "$HOME/bc5-work/BOX-LOCK" ] || return 0; sleep 5; done; return 1; }
for _ in $(seq 1 240); do grep -q "series c: end" "$N/series-c.log" && break; sleep 5; done
stop && { echo "$(date '+%F %T') chain: stopped before series d"; exit 0; }
bash "$X/series0412n.sh" d 600 zof > "$N/series-d.log" 2>&1
calm || { echo "$(date '+%F %T') chain: the box is not calm before astro"; exit 1; }
stop && { echo "$(date '+%F %T') chain: stopped before astro"; exit 0; }
bash "$X/astro0412n.sh" ao1off off 600 > "$N/astro-ao1off.log" 2>&1
calm || { echo "$(date '+%F %T') chain: the box is not calm before the second astro"; exit 1; }
sleep 20
stop && { echo "$(date '+%F %T') chain: stopped before the second astro"; exit 0; }
bash "$X/astro0412n.sh" ao2on on 600 > "$N/astro-ao2on.log" 2>&1
calm || { echo "$(date '+%F %T') chain: the box is not calm before series e"; exit 1; }
sleep 20
stop && { echo "$(date '+%F %T') chain: stopped before series e"; exit 0; }
bash "$X/series0412n.sh" e 300 of > "$N/series-e.log" 2>&1
echo "$(date '+%F %T') chain: end"
