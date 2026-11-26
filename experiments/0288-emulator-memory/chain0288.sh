#!/usr/bin/env bash
# BC5 experiment 0288: the three runs in one lock (the top session's GO of 2026-10-25 01:15): M1 (private binary, breakdown at
# 240 s, the launcher's existing mount), N1 (shared normal build, the package mount made fresh with MALLOC_ARENA_MAX=2 and
# unmounted after), L1 (shared lean build; the launcher mounts fresh with the default arenas: the comparison for N1's mount).
# RT off in every arm (run0288.sh). The chain stops after the first run whose verdict is not "pass". One BOX-LOCK line is
# held between the runs (each run writes its own line meanwhile and removes it; this script writes the chain line back).
set -u
E=$HOME/bc5-work/exp0288; LOCK=$HOME/bc5-work/BOX-LOCK
CHAIN=${CHAIN:-"M2 M 300 240|N1 N 300 0 2|L1 L 300 0"}  # M1 of 01:15 came without the table (its SEEK_DATA walk); M2 has NODATA
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator is running: not started"; exit 1; }
[ -s "$LOCK" ] && { echo "the box is locked: $(cat "$LOCK")"; exit 1; }
chainlock() { echo "exp 0288 | chain ${CHAIN//|/, }: the second title's S6N route, RT off, memory sampled, maintainer reachable | start $(date +%H:%M) | until ~$(date -d '+30 min' +%H:%M)" > "$LOCK"; }
chainlock
trap 'grep -q "^exp 0288 | chain" "$LOCK" 2> /dev/null && rm -f "$LOCK"' EXIT
IFS='|' read -r -a SPECS <<< "$CHAIN"
for spec in "${SPECS[@]}"; do
  set -- $spec
  echo "== $(date +%T) run $1 (arm $2)"
  MOUNT_ARENAS=${5:-} "$E/run0288.sh" "$1" "$2" "$3" "$4" 2>&1 | tail -6
  chainlock
  grep -q "^pass" "$E/raw/$1-verdict.txt" 2> /dev/null || { echo "== $(date +%T) the chain stops after $1"; break; }
done
echo "== $(date +%T) chain done"
rm -f "$LOCK" && echo "BOX-LOCK released"
