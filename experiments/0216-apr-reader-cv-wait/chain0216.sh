#!/usr/bin/env bash
# BC5 experiment 0216: the test build and its smoke run as one detached chain under one BOX-LOCK line.
#   1. Wait until the box is free and stays free for GRACE s (default 30): no BOX-LOCK, no kyty_emulator. Check the
#      boot id (BOOT) and that no new amdgpu fault/timeout/reset/error line appeared since the start.
#   2. Build: src/libAmpr.cv-wait.cpp (the shared tree's libAmpr.cpp, checked equal to src/libAmpr.before-0216.cpp,
#      plus patch_0216.diff) compiled with the shared build's flags and linked with its other objects (build0216.py)
#      into ~/bc5-work/exp0216/kyty_emulator. The shared tree, binaries and objects are not written.
#   3. Smoke run S1 (run0216.sh, 300 s on O2's route). It passes when it ran the full time, had bc5-apr-r threads with
#      no KYTY_BC5_APR_READAHEAD set, journaled read-ahead lines and in-order copies, kept the completion sequence
#      increasing, and had no crash line, no new kernel line and the live saves back identical.
# Then the lock is released. Start it only on the top session's "Go" (queue order, ~/bc5-work/BOX-QUEUE): the free-box
# wait in step 1 is a last check, not the queue; started early it could jump into a gap between other sessions' slots.
# usage: setsid nohup chain0216.sh > raw/chain.out 2>&1 &   (on the box, on the top session's Go)
set -u
E=$HOME/bc5-work/exp0216; R=$E/raw; LOCK=$HOME/bc5-work/BOX-LOCK; K=$HOME/src/KytyPlus
BOOT=${BOOT:-$(cut -c1-8 /proc/sys/kernel/random/boot_id)}; GRACE=${GRACE:-30}; TAG=${TAG:-S1}; SECS=${SECS:-300}
N0=$(sudo -n dmesg 2> /dev/null | wc -l)
mkdir -p "$R"
free_for() {  # the box free for $1 s, checked every 2 s
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
release() { grep -q "^exp 0216 | chain: " "$LOCK" 2> /dev/null && rm -f "$LOCK" && echo "== $(date +%T) BOX-LOCK released"; }
for _ in $(seq 1 120); do free_for "$GRACE" && break; sleep 10; done
free_for 1 || { echo "box not free at $(date +%T): stop"; exit 1; }
checks || exit 1
echo "exp 0216 | chain: one-file rebuild into ~/bc5-work/exp0216 + smoke run $TAG $SECS s of that binary (GRANTED by the top session) | start $(date +%H:%M) | until ~$(date -d "+$((SECS / 60 + 8)) min" +%H:%M)" > "$LOCK"
echo "== $(date +%T) build"
cd "$E" || { release; exit 1; }
cmp -s "$K/src/libs/libAmpr.cpp" src/libAmpr.before-0216.cpp || { echo "the tree's libAmpr.cpp is not src/libAmpr.before-0216.cpp: stop"; release; exit 1; }
cp -p src/libAmpr.cv-wait.cpp src/libAmpr.cpp
S=$(date +%s)
distrobox enter ubuntu -- python3 -I "$E/build0216.py" "$HOME/bc5-work/exp0203/compdb.json" > "$R/build.log" 2>&1
RC=$?
echo "== $(date +%T) build rc $RC after $(($(date +%s) - S)) s"
sed 's/\x1b\[[0-9;]*m//g' "$R/build.log" | grep -E "warning:|error:" | cut -c1-200
[ $RC = 0 ] && [ kyty_emulator -nt src/libAmpr.cv-wait.cpp ] || { echo "build failed: stop"; release; exit 1; }
grep -q "bc5-apr-r%zu-%zu" <(strings kyty_emulator) || { echo "the test binary has no read-ahead: stop"; release; exit 1; }
md5sum kyty_emulator src/libAmpr.cpp "$HOME/bc5-work/kytyplus-build/src/kyty_emulator"
checks || { release; exit 1; }
echo "== $(date +%T) smoke run $TAG"
"$E/run0216.sh" "$TAG" "$SECS" > "$R/$TAG-run.out" 2>&1
cat "$R/$TAG-run.out"
release
S=$R/$TAG-summary.txt
grep -q "$TAG stopped at $SECS s" "$R/$TAG-end.txt" 2> /dev/null || { echo "== $TAG FAILED: did not run the full $SECS s"; exit 1; }
grep -q "live saves back and identical" "$R/$TAG-restore-back.txt" || { echo "== $TAG: THE LIVE SAVES NEED CHECKING"; exit 1; }
# "<tag> summary: reader threads A, readahead lines B, in-order copies C, sequence decreases D, crash lines E, kernel lines F"
awk '/summary:/ {ok = ($5 + 0 > 0 && $8 + 0 > 0 && $11 + 0 > 0 && $14 == "0," && $17 == "0," && $20 == "0")} END {exit !ok}' "$S" \
  || { echo "== $TAG FAILED: criteria not met ($(head -1 "$S"))"; exit 1; }
checks || exit 1
echo "== $(date +%T) $TAG PASSED"
