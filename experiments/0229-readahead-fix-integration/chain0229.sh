#!/usr/bin/env bash
# BC5 experiment 0229: the integration of the read-ahead fix as one detached chain under one BOX-LOCK line (exp 0214's
# chain0214.sh with this patch).
#   1. A last check that the box is free (no BOX-LOCK, no kyty_emulator) for GRACE s (default 10); the boot id and no new
#      amdgpu fault/timeout/reset/error line since the start. Start it only on the user's approval and the top
#      session's Go.
#   2. rebuild0229.sh: patch_0227-readahead-fix.diff into ~/src/KytyPlus, both shared builds rebuilt and synced.
#   3. Smoke run S4N on the normal shared build (run0229.sh, 300 s, O2's route). It passes when it ran the full time,
#      had bc5-apr-r threads with no KYTY_BC5_APR_READAHEAD set, journaled read-ahead lines and in-order copies, kept
#      the completion sequence increasing, and had no crash line, no new kernel line and the live saves back identical.
#   4. Smoke run S4L on the lean build (150 s): the full time, reader threads, no crash or kernel line, saves back.
#   4b. Smoke run S4A: ASTRO BOT on the normal build, read-ahead on (run0229a.sh, exp 0228's runner, 100 s): the full
#      time, no crash or kernel line, the live saves back. (The launchers will turn the read-ahead on for both titles.)
#   5. On any failure: libAmpr.cpp (new mtime) and both binaries put back from the *.before-fix copies (ROLLED BACK).
# Then S4N's GPU journal is read with exp 0214's ra0214.py and gu0214.py (O_DIRECT, 15 MB/s), and the lock released.
# usage: setsid nohup chain0229.sh > raw/chain.out 2>&1 < /dev/null &   (on the box)
set -u
E=$HOME/bc5-work/exp0229; R=$E/raw; LOCK=$HOME/bc5-work/BOX-LOCK; K=$HOME/src/KytyPlus
N=$HOME/bc5-work/kytyplus-build/src/kyty_emulator
L=$HOME/bc5-work/kytyplus-build-lean/src/kyty_emulator
BOOT=${BOOT:-$(cut -c1-8 /proc/sys/kernel/random/boot_id)}; GRACE=${GRACE:-10}
N0=$(sudo -n dmesg 2> /dev/null | wc -l)
mkdir -p "$R"
free_for() {
  local i
  for i in $(seq 0 2 "$1"); do
    [ ! -s "$LOCK" ] && ! pgrep '^kyty_emulator' > /dev/null || return 1
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
release() { grep -q "^exp 0229 | chain: " "$LOCK" 2> /dev/null && rm -f "$LOCK" && echo "== $(date +%T) BOX-LOCK released"; }
rollback() {
  echo "== $(date +%T) $*: ROLLING BACK"
  cp "$E/src/libAmpr.before-fix.cpp" "$K/src/libs/libAmpr.cpp" && cp -p "$E/kyty_emulator.before-fix" "$N" \
    && cp -p "$E/kyty_emulator-lean.before-fix" "$L" && sync && echo "ROLLED BACK: $(md5sum "$N" "$L" "$K/src/libs/libAmpr.cpp" | cut -c1-12 | tr '\n' ' ')"
  release
  exit 1
}
free_for "$GRACE" || { echo "box not free at $(date +%T): $(cat "$LOCK" 2> /dev/null): stop"; exit 1; }
checks || exit 1
echo "exp 0229 | chain: the read-ahead fix into the tree, rebuild of both shared builds, smoke runs S4N 300 s + S4L 150 s + S4A 100 s (approved; Go from the top session) | start $(date +%H:%M) | until ~$(date -d +21min +%H:%M)" > "$LOCK"
echo "== $(date +%T) rebuild"
"$E/rebuild0229.sh" > "$R/rebuild.out" 2>&1
cat "$R/rebuild.out"
grep -q "^FAILED" "$R/rebuild.out" && { release; exit 1; }
grep -q "after (synced)" "$R/rebuild.out" || { echo "rebuild did not finish (nothing was changed if it stopped before the backups)"; release; exit 1; }
checks || rollback "checks after the rebuild"
echo "== $(date +%T) smoke run S4N (normal shared build)"
"$E/run0229.sh" S4N 300 0 > "$R/S4N-run.out" 2>&1
cat "$R/S4N-run.out"
grep -q "live saves back and identical" "$R/S4N-restore-back.txt" || { echo "S4N: THE LIVE SAVES NEED CHECKING"; rollback "S4N saves"; }
grep -q "S4N stopped at 300 s" "$R/S4N-end.txt" 2> /dev/null || rollback "S4N did not run the full 300 s"
# "<tag> summary: reader threads A, readahead lines B, in-order copies C, sequence decreases D, crash lines E, kernel lines F"
awk '/summary:/ {ok = ($5 + 0 > 0 && $8 + 0 > 0 && $11 + 0 > 0 && $14 == "0," && $17 == "0," && $20 == "0")} END {exit !ok}' "$R/S4N-summary.txt" \
  || rollback "S4N criteria not met ($(head -1 "$R/S4N-summary.txt"))"
checks || rollback "checks after S4N"
echo "== $(date +%T) S4N PASSED; smoke run S4L (lean build)"
"$E/run0229.sh" S4L 150 1 > "$R/S4L-run.out" 2>&1
cat "$R/S4L-run.out"
grep -q "live saves back and identical" "$R/S4L-restore-back.txt" || { echo "S4L: THE LIVE SAVES NEED CHECKING"; rollback "S4L saves"; }
grep -q "S4L stopped at 150 s" "$R/S4L-end.txt" 2> /dev/null || rollback "S4L did not run the full 150 s"
awk '/summary:/ {ok = ($5 + 0 > 0 && $17 == "0," && $20 == "0")} END {exit !ok}' "$R/S4L-summary.txt" || rollback "S4L criteria not met ($(head -1 "$R/S4L-summary.txt"))"
checks || rollback "checks after S4L"
echo "== $(date +%T) S4L PASSED; smoke run S4A (ASTRO BOT, normal build, read-ahead on)"
"$E/run0229a.sh" astro S4A RA4 100 > "$R/S4A-run.out" 2>&1
cat "$R/S4A-run.out"
grep -q "live saves back and identical" "$R/S4A-restore-back.txt" || { echo "S4A: THE LIVE SAVES NEED CHECKING"; rollback "S4A saves"; }
grep -q "S4A stopped at 100 s" "$R/S4A-end.txt" 2> /dev/null || rollback "S4A did not run the full 100 s"
grep -q "crash lines 0, kernel lines 0" "$R/S4A-summary.txt" || rollback "S4A crash or kernel lines ($(head -1 "$R/S4A-summary.txt"))"
checks || rollback "checks after S4A"
echo "== $(date +%T) S4A PASSED: both shared builds have the read-ahead fix"
J=$(cut -d' ' -f1 "$R/S4N-journal-path.txt")
nice -n 19 python3 -I "$HOME/bc5-work/exp0214/ra0214.py" 15 100 S4N="$J" > "$R/S4N-frames.txt" 2>&1
nice -n 19 python3 -I "$HOME/bc5-work/exp0214/gu0214.py" 15 S4N="$J" > "$R/S4N-giveups.txt" 2>&1
cat "$R/S4N-frames.txt" "$R/S4N-giveups.txt"
release
