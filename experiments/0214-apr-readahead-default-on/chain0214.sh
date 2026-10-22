#!/usr/bin/env bash
# BC5 experiment 0214: the integration as one detached chain, under one BOX-LOCK line (no gap between the steps).
#   1. Wait until the box is free and stays free for GRACE s (default 120): no BOX-LOCK, no kyty_emulator. Check the
#      boot id (BOOT) and that no new amdgpu fault/timeout/reset/error line appeared since the start.
#   2. rebuild0214.sh: patch_0214.diff into ~/src/KytyPlus, both shared builds rebuilt and synced.
#   3. Smoke run S1N on the normal shared build (run0214.sh, 300 s). It passes when it ran the full time, had
#      bc5-apr-r threads with no KYTY_BC5_APR_READAHEAD set, journaled read-ahead lines and in-order copies, kept the
#      completion sequence increasing, and had no crash line, no new kernel line and the live saves back identical.
#   4. Smoke run S1L on the lean build (150 s): the full time, reader threads, no crash or kernel line, saves back.
#   5. If a smoke run fails: both binaries and libAmpr.cpp are put back from the *.before-0214 copies (ROLLED BACK).
# Then the lock is released, and S1N's GPU journal is scored by ra0214.py (O_DIRECT, 15 MB/s).
# usage: setsid nohup chain0214.sh > raw/chain.out 2>&1 &   (on the box, after the top session's GRANTED)
set -u
E=$HOME/bc5-work/exp0214; R=$E/raw; LOCK=$HOME/bc5-work/BOX-LOCK; K=$HOME/src/KytyPlus
N=$HOME/bc5-work/kytyplus-build/src/kyty_emulator
L=$HOME/bc5-work/kytyplus-build-lean/src/kyty_emulator
BOOT=${BOOT:-$(cut -c1-8 /proc/sys/kernel/random/boot_id)}; GRACE=${GRACE:-120}
N0=$(sudo -n dmesg 2> /dev/null | wc -l)
free_for() {  # the box free for $1 s, checked every 2 s: any lock or emulator in the window (even a 2-s read pass) restarts it
  local i
  for i in $(seq 0 2 "$1"); do
    [ ! -s "$LOCK" ] && ! pgrep -x kyty_emulator > /dev/null || return 1
    [ "$i" -lt "$1" ] && sleep 2
  done
  return 0
}
checks() {
  [ "$(cut -c1-8 /proc/sys/kernel/random/boot_id)" = "$BOOT" ] || { echo "boot id changed: stop"; return 1; }
  local k
  k=$(sudo -n dmesg 2> /dev/null | tail -n +"$((N0 + 1))" | grep -ci "amdgpu.*\(fault\|timeout\|reset\|error\)")
  [ "$k" = 0 ] || { echo "$k new amdgpu lines: stop"; return 1; }
}
# The run of 20:02 matched "chain " here against its "chain:" line, so its lock stayed 65 s until removed by hand.
release() { grep -q "^exp 0214 | chain: " "$LOCK" 2> /dev/null && rm -f "$LOCK" && echo "== $(date +%T) BOX-LOCK released"; }
rollback() {
  echo "== $(date +%T) $*: ROLLING BACK"
  cp -p "$E/src/libAmpr.before-0214.cpp" "$K/src/libs/libAmpr.cpp" && cp -p "$E/kyty_emulator.before-0214" "$N" \
    && cp -p "$E/kyty_emulator-lean.before-0214" "$L" && sync && echo "ROLLED BACK: $(md5sum "$N" "$L" "$K/src/libs/libAmpr.cpp" | cut -c1-12 | tr '\n' ' ')"
  release
  exit 1
}
for _ in $(seq 1 240); do free_for "$GRACE" && break; sleep 10; done
free_for 1 || { echo "box not free at $(date +%T): stop"; exit 1; }
checks || exit 1
echo "exp 0214 | chain: rebuild of both shared builds (APR read-ahead on by default), smoke runs S1N 300 s + S1L 150 s (GRANTED by the top session) | start $(date +%H:%M) | until ~$(date -d +22min +%H:%M)" > "$LOCK"
echo "== $(date +%T) rebuild"
"$E/rebuild0214.sh" > "$R/rebuild.out" 2>&1
cat "$R/rebuild.out"
grep -q "^FAILED" "$R/rebuild.out" && { release; exit 1; }
grep -q "after (synced)" "$R/rebuild.out" || { echo "rebuild did not finish: stop"; release; exit 1; }
checks || rollback "checks after the rebuild"
echo "== $(date +%T) smoke run S1N (normal shared build)"
"$E/run0214.sh" S1N 300 0 > "$R/S1N-run.out" 2>&1
cat "$R/S1N-run.out"
S=$R/S1N-summary.txt
grep -q "S1N stopped at 300 s" "$R/S1N-end.txt" 2> /dev/null || rollback "S1N did not run the full 300 s"
grep -q "live saves back and identical" "$R/S1N-restore-back.txt" || { echo "S1N: THE LIVE SAVES NEED CHECKING"; rollback "S1N saves"; }
# "<tag> summary: reader threads A, readahead lines B, in-order copies C, sequence decreases D, crash lines E, kernel lines F"
awk '/summary:/ {ok = ($5 + 0 > 0 && $8 + 0 > 0 && $11 + 0 > 0 && $14 == "0," && $17 == "0," && $20 == "0")} END {exit !ok}' "$S" \
  || rollback "S1N criteria not met ($(head -1 "$S"))"
checks || rollback "checks after S1N"
echo "== $(date +%T) S1N PASSED; smoke run S1L (lean build)"
"$E/run0214.sh" S1L 150 1 > "$R/S1L-run.out" 2>&1
cat "$R/S1L-run.out"
S=$R/S1L-summary.txt
grep -q "S1L stopped at 150 s" "$R/S1L-end.txt" 2> /dev/null || rollback "S1L did not run the full 150 s"
grep -q "live saves back and identical" "$R/S1L-restore-back.txt" || { echo "S1L: THE LIVE SAVES NEED CHECKING"; rollback "S1L saves"; }
awk '/summary:/ {ok = ($5 + 0 > 0 && $17 == "0," && $20 == "0")} END {exit !ok}' "$S" || rollback "S1L criteria not met ($(head -1 "$S"))"
checks || rollback "checks after S1L"
echo "== $(date +%T) S1L PASSED: both shared builds keep the read-ahead on by default"
release
J=$(cut -d' ' -f1 "$R/S1N-journal-path.txt")
nice -n 19 python3 -I "$E/ra0214.py" 15 100 S1N="$J" > "$R/S1N-frames.txt" 2>&1
cat "$R/S1N-frames.txt"
