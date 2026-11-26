#!/usr/bin/env bash
# BC5 (experiment 0203): the top session's grant of 17:36 as one detached chain.
#   1. Wait until the box is free and stays free for GRACE s (default 60): no BOX-LOCK, no kyty_emulator.
#   2. Check the boot id (BOOT) and that no new amdgpu fault/timeout/reset/error line appeared since the start.
#   3. Rebuild with the v2 read-ahead (rebuild0203.sh, SRC=libAmpr.readahead-v2.cpp).
#   4. Smoke run S0: O2's route (S1's end saves, scripted Continue), KYTY_BC5_APR_READAHEAD=4, 240 s.
#      Halfway, count the emulator's bc5-apr-r* threads.
#   5. S0 passes when all hold:
#      - it ran the full 240 s (no crash or exit);
#      - bc5-apr-r threads existed;
#      - the journal has "readahead ... into host memory" lines and in-order "run ... read" copies;
#      - the sequence writes to 0x90adf7fe0 never decrease;
#      - no new amdgpu kernel line.
#      Only then the full O3 (600 s, the same route and switch) starts right away.
# usage: setsid nohup chain0203.sh > raw/chain.out 2>&1 &
set -u
E=$HOME/bc5-work/exp0203; R=$E/raw; LOCK=$HOME/bc5-work/BOX-LOCK
BOOT=${BOOT:-ac5dab11}; GRACE=${GRACE:-60}
export SAVES=$HOME/bc5-work/exp0196/saves-before-152617 CMD=$E/o2-continue.cmd EXTRA_ENV="KYTY_BC5_APR_READAHEAD=4"
N0=$(sudo -n dmesg 2> /dev/null | wc -l)
free_for() {  # the box free now and still free after $1 s
  [ ! -s "$LOCK" ] && ! pgrep -x kyty_emulator > /dev/null || return 1
  sleep "$1"
  [ ! -s "$LOCK" ] && ! pgrep -x kyty_emulator > /dev/null
}
checks() {
  [ "$(cut -c1-8 /proc/sys/kernel/random/boot_id)" = "$BOOT" ] || { echo "boot id changed: stop"; return 1; }
  local k
  k=$(sudo -n dmesg 2> /dev/null | tail -n +"$((N0 + 1))" | grep -ci "amdgpu.*\(fault\|timeout\|reset\|error\)")
  [ "$k" = 0 ] || { echo "$k new amdgpu lines: stop"; return 1; }
}
for _ in $(seq 1 240); do free_for "$GRACE" && break; sleep 10; done
free_for 1 || { echo "box not free at $(date +%T): stop"; exit 1; }
checks || exit 1
echo "== $(date +%T) rebuild v2"
SRC=libAmpr.readahead-v2.cpp "$E/rebuild0203.sh" > "$R/rebuild-v2.out" 2>&1
cat "$R/rebuild-v2.out"
grep -q "^build rc 0 " "$R/rebuild-v2.out" || { echo "rebuild failed: stop"; exit 1; }
grep -q "into host memory" <(strings "$E/kyty_emulator") || { echo "the binary is not v2: stop"; exit 1; }
checks || exit 1
echo "== $(date +%T) smoke run S0"
"$E/run0203-opening.sh" S0 240 > "$R/S0-run.out" 2>&1 &
RUNPID=$!
sleep 150
P=$(pgrep -x kyty_emulator | head -1)
NR=0; [ -n "$P" ] && NR=$(for t in /proc/"$P"/task/*; do cat "$t/comm" 2> /dev/null; done | grep -c "^bc5-apr-r")
echo "bc5-apr-r threads at +150 s: $NR"
wait "$RUNPID"
cat "$R/S0-run.out"
J=$R/S0-apr-journal.txt
RA=$(grep -c "readahead cb .* into host memory" "$J" 2> /dev/null)
RUNS=$(grep -c " run cb .* read file " "$J" 2> /dev/null)
DEC=$(grep " run cb .* write addr 0x000000090adf7fe0 " "$J" 2> /dev/null | awk '{v=strtonum($14); if (n && v < p) d++; p=v; n++} END {print d+0}')
FULL=0; grep -q "S0 stopped at 240 s" "$R/S0-end.txt" 2> /dev/null && FULL=1
echo "S0: full 240 s $FULL, readers $NR, readahead lines ${RA:-0}, in-order copies ${RUNS:-0}, sequence decreases ${DEC:-?}"
if [ "$FULL" = 1 ] && [ "$NR" -gt 0 ] && [ "${RA:-0}" -gt 0 ] && [ "${RUNS:-0}" -gt 0 ] && [ "${DEC:-1}" = 0 ] && checks; then
  echo "S0 PASSED at $(date +%T): starting O3"
  "$E/run0203-opening.sh" O3 600 > "$R/O3-run.out" 2>&1
  cat "$R/O3-run.out"
  checks
else
  echo "S0 FAILED at $(date +%T): O3 not started"
fi
