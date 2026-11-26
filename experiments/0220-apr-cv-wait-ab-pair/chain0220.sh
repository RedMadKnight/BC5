#!/usr/bin/env bash
# BC5 experiment 0220: the back-to-back pair as one detached chain under one BOX-LOCK line.
#   1. A last check that the box is free (no BOX-LOCK, no kyty_emulator) for GRACE s (default 10); the boot id
#      (BOOT) and no new amdgpu fault/timeout/reset/error line since the start. Start it only on the top session's Go.
#   2. A1: the shared normal build (run0220.sh A1 300 shared), then a 20-s pause, then B1: exp 0216's binary
#      (run0220.sh B1 300 test). The same route, saves restored and checked after each.
#      An arm passes when it ran the full time, had bc5-apr-r threads, journaled read-ahead lines and in-order copies,
#      kept the completion sequence increasing, and had no crash line, no new kernel line and the saves back.
#      Saves that differ, or a new amdgpu line, stop the chain.
#   3. ana0220.sh: both GPU journals with O_DIRECT at 15 MB/s, the samplers. Still under the lock, then released.
# usage: setsid nohup chain0220.sh > raw/chain.out 2>&1 < /dev/null &   (on the box, on the top session's Go)
set -u
E=$HOME/bc5-work/exp0220; R=$E/raw; LOCK=$HOME/bc5-work/BOX-LOCK
BOOT=${BOOT:-$(cut -c1-8 /proc/sys/kernel/random/boot_id)}; GRACE=${GRACE:-10}; SECS=${SECS:-300}
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
release() { grep -q "^exp 0220 | chain: " "$LOCK" 2> /dev/null && rm -f "$LOCK" && echo "== $(date +%T) BOX-LOCK released"; }
arm() {  # <tag> <shared|test>
  echo "== $(date +%T) run $1 ($2)"
  "$E/run0220.sh" "$1" "$SECS" "$2" > "$R/$1-run.out" 2>&1
  cat "$R/$1-run.out"
  grep -q "live saves back and identical" "$R/$1-restore-back.txt" 2> /dev/null || { echo "== $1: THE LIVE SAVES NEED CHECKING: stop"; release; exit 1; }
  checks || { release; exit 1; }
  if grep -q "$1 stopped at $SECS s" "$R/$1-end.txt" 2> /dev/null \
     && awk '/summary:/ {ok = ($5 + 0 > 0 && $8 + 0 > 0 && $11 + 0 > 0 && $14 == "0," && $17 == "0," && $20 == "0")} END {exit !ok}' "$R/$1-summary.txt"; then
    echo "== $(date +%T) $1 PASSED"
  else
    echo "== $(date +%T) $1 FAILED the criteria ($(cat "$R/$1-end.txt" 2> /dev/null); $(head -1 "$R/$1-summary.txt" 2> /dev/null))"
  fi
}
free_for "$GRACE" || { echo "box not free at $(date +%T): $(cat "$LOCK" 2> /dev/null): stop"; exit 1; }
checks || exit 1
# The test binary was linked at 20:33:44 from the shared build's objects of exp 0214 (binary md5 9d43e945...). If the
# shared build changed since, the pair would compare more than patch_0216: stop.
SH=$(md5sum "$HOME/bc5-work/kytyplus-build/src/kyty_emulator" | cut -c1-32)
[ "$SH" = 9d43e945bb79a543224937099d6c45a1 ] || { echo "the shared build changed (md5 $SH): the test binary needs a relink: stop"; exit 1; }
echo "exp 0220 | chain: A/B pair, shared build then exp0216 binary, $SECS s each, O2's route, + journal reads (Go from the top session) | start $(date +%H:%M) | until ~$(date -d "+$((2 * SECS / 60 + 5)) min" +%H:%M)" > "$LOCK"
arm A1 shared
sleep 20
arm B1 test
echo "== $(date +%T) analysis"
"$E/ana0220.sh" > "$R/ana.out" 2>&1
cat "$R/ana.out"
release
