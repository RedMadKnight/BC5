#!/usr/bin/env bash
# BC5 experiment 0222: the integration of patch_0216 as one detached chain under one BOX-LOCK line (exp 0214's
# chain0214.sh with this patch).
#   1. A last check that the box is free (no BOX-LOCK, no kyty_emulator) for GRACE s (default 10); the boot id and no new
#      amdgpu fault/timeout/reset/error line since the start. Start it only on the user's approval and the top
#      session's Go.
#   2. rebuild0222.sh: patch_0216.diff into ~/src/KytyPlus, both shared builds rebuilt and synced.
#   3. Smoke run S2N on the normal shared build (run0222.sh, 300 s, O2's route). It passes when it ran the full time,
#      had bc5-apr-r threads with no KYTY_BC5_APR_READAHEAD set, journaled read-ahead lines and in-order copies, kept
#      the completion sequence increasing, and had no crash line, no new kernel line and the live saves back identical.
#   4. Smoke run S2L on the lean build (150 s): the full time, reader threads, no crash or kernel line, saves back.
#   5. On any failure: libAmpr.cpp (new mtime) and both binaries put back from the *.before-0216 copies (ROLLED BACK).
# Then S2N's GPU journal is read with exp 0214's ra0214.py and gu0214.py (O_DIRECT, 15 MB/s), and the lock released.
# usage: setsid nohup chain0222.sh > raw/chain.out 2>&1 < /dev/null &   (on the box)
set -u
E=$HOME/bc5-work/exp0222; R=$E/raw; LOCK=$HOME/bc5-work/BOX-LOCK; K=$HOME/src/KytyPlus
N=$HOME/bc5-work/kytyplus-build/src/kyty_emulator
L=$HOME/bc5-work/kytyplus-build-lean/src/kyty_emulator
BOOT=${BOOT:-$(cut -c1-8 /proc/sys/kernel/random/boot_id)}; GRACE=${GRACE:-10}
N0=$(sudo -n dmesg 2> /dev/null | wc -l)
mkdir -p "$R"
free_for() {
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
release() { grep -q "^exp 0222 | chain: " "$LOCK" 2> /dev/null && rm -f "$LOCK" && echo "== $(date +%T) BOX-LOCK released"; }
rollback() {
  echo "== $(date +%T) $*: ROLLING BACK"
  cp "$E/src/libAmpr.before-0216.cpp" "$K/src/libs/libAmpr.cpp" && cp -p "$E/kyty_emulator.before-0216" "$N" \
    && cp -p "$E/kyty_emulator-lean.before-0216" "$L" && sync && echo "ROLLED BACK: $(md5sum "$N" "$L" "$K/src/libs/libAmpr.cpp" | cut -c1-12 | tr '\n' ' ')"
  release
  exit 1
}
free_for "$GRACE" || { echo "box not free at $(date +%T): $(cat "$LOCK" 2> /dev/null): stop"; exit 1; }
checks || exit 1
echo "exp 0222 | chain: patch_0216 into the tree, rebuild of both shared builds, smoke runs S2N 300 s + S2L 150 s (approved; Go from the top session) | start $(date +%H:%M) | until ~$(date -d +17min +%H:%M)" > "$LOCK"
echo "== $(date +%T) rebuild"
"$E/rebuild0222.sh" > "$R/rebuild.out" 2>&1
cat "$R/rebuild.out"
grep -q "^FAILED" "$R/rebuild.out" && { release; exit 1; }
grep -q "after (synced)" "$R/rebuild.out" || { echo "rebuild did not finish (nothing was changed if it stopped before the backups)"; release; exit 1; }
checks || rollback "checks after the rebuild"
echo "== $(date +%T) smoke run S2N (normal shared build)"
"$E/run0222.sh" S2N 300 0 > "$R/S2N-run.out" 2>&1
cat "$R/S2N-run.out"
grep -q "live saves back and identical" "$R/S2N-restore-back.txt" || { echo "S2N: THE LIVE SAVES NEED CHECKING"; rollback "S2N saves"; }
grep -q "S2N stopped at 300 s" "$R/S2N-end.txt" 2> /dev/null || rollback "S2N did not run the full 300 s"
# "<tag> summary: reader threads A, readahead lines B, in-order copies C, sequence decreases D, crash lines E, kernel lines F"
awk '/summary:/ {ok = ($5 + 0 > 0 && $8 + 0 > 0 && $11 + 0 > 0 && $14 == "0," && $17 == "0," && $20 == "0")} END {exit !ok}' "$R/S2N-summary.txt" \
  || rollback "S2N criteria not met ($(head -1 "$R/S2N-summary.txt"))"
checks || rollback "checks after S2N"
echo "== $(date +%T) S2N PASSED; smoke run S2L (lean build)"
"$E/run0222.sh" S2L 150 1 > "$R/S2L-run.out" 2>&1
cat "$R/S2L-run.out"
grep -q "live saves back and identical" "$R/S2L-restore-back.txt" || { echo "S2L: THE LIVE SAVES NEED CHECKING"; rollback "S2L saves"; }
grep -q "S2L stopped at 150 s" "$R/S2L-end.txt" 2> /dev/null || rollback "S2L did not run the full 150 s"
awk '/summary:/ {ok = ($5 + 0 > 0 && $17 == "0," && $20 == "0")} END {exit !ok}' "$R/S2L-summary.txt" || rollback "S2L criteria not met ($(head -1 "$R/S2L-summary.txt"))"
checks || rollback "checks after S2L"
echo "== $(date +%T) S2L PASSED: both shared builds have patch_0216"
J=$(cut -d' ' -f1 "$R/S2N-journal-path.txt")
nice -n 19 python3 -I "$HOME/bc5-work/exp0214/ra0214.py" 15 100 S2N="$J" > "$R/S2N-frames.txt" 2>&1
nice -n 19 python3 -I "$HOME/bc5-work/exp0214/gu0214.py" 15 S2N="$J" > "$R/S2N-giveups.txt" 2>&1
cat "$R/S2N-frames.txt" "$R/S2N-giveups.txt"
release
