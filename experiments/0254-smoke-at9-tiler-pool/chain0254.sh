#!/usr/bin/env bash
# BC5 experiment 0254: the smoke runs under one BOX-LOCK line, detached (exp 0229's chain0229.sh without the rebuild or a
# rollback: nothing is changed here).
#   1. The top session's integration of the held tail (~/bc5-work/exp0226/integration/int.out) must have ended with
#      "done", and the box must be free (no BOX-LOCK, no kyty_emulator) for GRACE s (default 10).
#   2. S5A: ASTRO BOT, the normal shared build, play-astro.sh, S4A's route, SA s (default 200).
#   3. S5C: ASTRO BOT through play-astro-compute.sh (the compute ring: the held tail acts), the same route, SC s (150).
#   4. S5L: the second title, the lean shared build, S4L's route, SL s (default 150).
# It stops at the first run whose verdict is not "pass" (run0254.sh), or on a new amdgpu fault/timeout/reset/error line
# or a changed boot id. Only on the top session's Go.
# usage: WANT_N=<md5 8> WANT_L=<md5 8> setsid nohup chain0254.sh > raw/chain.out 2>&1 < /dev/null &   (on the box)
set -u
E=$HOME/bc5-work/exp0254; R=$E/raw; LOCK=$HOME/bc5-work/BOX-LOCK
INT=$HOME/bc5-work/exp0226/integration/int.out
: "${WANT_N:?expected md5 of the normal build}" "${WANT_L:?expected md5 of the lean build}"
export WANT_N WANT_L
BOOT=$(cut -c1-8 /proc/sys/kernel/random/boot_id); GRACE=${GRACE:-10}; SA=${SA:-200}; SC=${SC:-150}; SL=${SL:-150}
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
release() { grep -q "^exp 0254 | chain: " "$LOCK" 2> /dev/null && rm -f "$LOCK" && echo "== $(date +%T) BOX-LOCK released"; }
tail -1 "$INT" 2> /dev/null | grep -q "done" || { echo "the integration has not ended with \"done\": $(tail -1 "$INT" 2> /dev/null): stop"; exit 1; }
free_for "$GRACE" || { echo "box not free at $(date +%T): $(cat "$LOCK" 2> /dev/null): stop"; exit 1; }
echo "exp 0254 | chain: smoke runs S5A (ASTRO BOT, $SA s) + S5C (ASTRO BOT compute ring, $SC s) + S5L (second title lean, $SL s) (Go from the top session) | start $(date +%H:%M) | until ~$(date -d "+$(((SA + SC + SL) / 60 + 6))min" +%H:%M)" > "$LOCK"
echo "== $(date +%T) expected md5 normal $WANT_N, lean $WANT_L; integration's last line: $(tail -1 "$INT")"
for run in "astro S5A $SA" "astroc S5C $SC" "pkg S5L $SL"; do
  set -- $run
  echo "== $(date +%T) smoke run $2 ($1, $3 s)"
  "$E/run0254.sh" "$1" "$2" "$3" > "$R/$2-run.out" 2>&1
  cat "$R/$2-run.out"
  grep -qx pass "$R/$2-verdict.txt" 2> /dev/null || { echo "== $(date +%T) $2 did not pass: stop"; release; exit 1; }
  checks || { release; exit 1; }
  echo "== $(date +%T) $2 PASSED"
done
release
echo "== $(date +%T) chain done"
