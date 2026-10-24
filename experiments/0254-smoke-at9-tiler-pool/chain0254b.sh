#!/usr/bin/env bash
# BC5 experiment 0254, part 2, under one BOX-LOCK line, detached:
#   1. The top session's integration of the compute-state prefix (~/bc5-work/exp0195/integration/int.out) must have
#      ended with "done", and the box must be free (no BOX-LOCK, no kyty_emulator) for GRACE s (default 10).
#   2. The journal counts of part 1's ASTRO BOT runs, S5A and S5C (jcount0254.awk). Part 1's own pass failed: the awk
#      program in run0254.sh had a newline inside its printf string. The journals' paths come from their
#      <tag>-journal.txt.
#   3. With run0254b.sh:
#      - S6N: the second title, the normal shared build, play-pkg.sh with its defaults (the prefix on), S4N's route, SN s
#        (default 300);
#      - S6A: ASTRO BOT, the normal shared build, play-astro.sh, S4A's route, SA s (default 150): patch_0195's
#        alias_learn guard is on for every title, and ASTRO BOT had not run with it;
#      - S5L: part 1's lean run, which did not run there (its chain stopped at S5C's saves), SL s (default 150).
# It stops at a run whose verdict is not "pass", on a new amdgpu fault/timeout/reset/error line or a changed boot id. Only on the top session's request.
# usage: WANT_N=<md5 8> WANT_L=<md5 8> setsid nohup chain0254b.sh > raw/chain-b.out 2>&1 < /dev/null &   (on the box)
set -u
E=$HOME/bc5-work/exp0254; R=$E/raw; LOCK=$HOME/bc5-work/BOX-LOCK
INT=$HOME/bc5-work/exp0195/integration/int.out
: "${WANT_N:?expected md5 of the normal build}" "${WANT_L:?expected md5 of the lean build}"
export WANT_N WANT_L
BOOT=$(cut -c1-8 /proc/sys/kernel/random/boot_id); GRACE=${GRACE:-10}; SN=${SN:-300}; SA=${SA:-150}; SL=${SL:-150}
N0=$(sudo -n dmesg 2> /dev/null | wc -l)
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
release() { grep -q "^exp 0254 | chain b: " "$LOCK" 2> /dev/null && rm -f "$LOCK" && echo "== $(date +%T) BOX-LOCK released"; }
tail -1 "$INT" 2> /dev/null | grep -q "done" || { echo "the integration has not ended with \"done\": $(tail -1 "$INT" 2> /dev/null): stop"; exit 1; }
free_for "$GRACE" || { echo "box not free at $(date +%T): $(cat "$LOCK" 2> /dev/null): stop"; exit 1; }
echo "exp 0254 | chain b: journal counts of S5A/S5C, then smoke runs S6N (second title, normal, $SN s) + S6A (ASTRO BOT, normal, $SA s) + S5L (second title, lean, $SL s) (top session's request) | start $(date +%H:%M) | until ~$(date -d "+$(((SN + SA + SL) / 60 + 8))min" +%H:%M)" > "$LOCK"
echo "== $(date +%T) expected md5 normal $WANT_N, lean $WANT_L; integration's last line: $(tail -1 "$INT")"
for t in S5A S5C; do
  J=$(awk 'NR == 1 && $1 == "journal" {print $2}' "$R/$t-journal.txt" 2> /dev/null)
  if [ -n "$J" ] && [ -f "$J" ]; then
    { echo "journal $J $(stat -c '%y %s' "$J") (counted by chain0254b.sh)"; nice -n 19 awk -f "$E/jcount0254.awk" "$J"; } > "$R/$t-journal-b.txt"
  else echo "no journal path for $t" > "$R/$t-journal-b.txt"; fi
  sed "s/^/$t /" "$R/$t-journal-b.txt"
done
checks || { release; exit 1; }
for run in "pkgn S6N $SN" "astro S6A $SA" "pkg S5L $SL"; do
  set -- $run
  echo "== $(date +%T) smoke run $2 ($1, $3 s)"
  "$E/run0254b.sh" "$1" "$2" "$3" > "$R/$2-run.out" 2>&1
  cat "$R/$2-run.out"
  grep -qx pass "$R/$2-verdict.txt" 2> /dev/null || { echo "== $(date +%T) $2 did not pass: stop"; release; exit 1; }
  checks || { release; exit 1; }
  echo "== $(date +%T) $2 PASSED"
done
release
echo "== $(date +%T) chain b done"
