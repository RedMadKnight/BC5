#!/usr/bin/env bash
# BC5 experiment 0255: the read-only part of the slot (no emulator, no GPU). The TCP write faults into memory the host has
# no guest memory for: the 2026-10-23 22:59 play (0x2675dfa000), exp 0199's L7 (0x1765833000) and exp 0211's R11B
# (0x1208a7c000). For each case's timed-out buffers (the host's timeout-probe dumps, private, on the box):
#   - markers.py (exp 0199): the debug markers and every dispatch's place inside them;
#   - ibwalk.py (exp 0199): each dispatch with its program and user data.
# For the 22:59 journal: the submissions around the timeout, the learned-window, AMM and PRT lines. And the learned-window
# file's windows. Output under ~/bc5-work/exp0255/raw; nothing outside it is written. Run with nice/ionice.
# usage: run0255.sh
set -u
E=$HOME/bc5-work/exp0255; R=$E/raw; LOCK=$HOME/bc5-work/BOX-LOCK; S=$HOME/bc5-work/exp0199
pgrep -x kyty_emulator > /dev/null && { echo "an emulator runs: stop"; exit 1; }
[ -s "$LOCK" ] && { echo "box locked: $(cat "$LOCK")"; exit 1; }
mkdir -p "$R"
echo "tcp exp 0255 | read-only: IB dumps and journal lines of three TCP faults, no GPU | start $(date +%H:%M) | until ~$(date -d +6min +%H:%M)" > "$LOCK"
trap 'grep -q "^tcp exp 0255 | read-only" "$LOCK" 2> /dev/null && rm -f "$LOCK"' EXIT
N="nice -n 19 ionice -c3"
C=$HOME/bc5-data/captures
# the three cases: the 22:59 play, L7 (play-20261022-1244, exp 0199) and R11B (play-20261022-1926, exp 0211); the
# dumps only (not the probe's .tfring.bin / .hsud-*.bin side files)
: > "$R/cases.txt"
for c in play-20261023-2259 play-20261022-1244 play-20261022-1926; do
  dumps=$(ls "$C/$c"/gc/ib-timeout-*.bin 2> /dev/null | grep -v '\.bin\.')
  for f in $dumps; do
    tag=$c-$(basename "$f" .bin)
    n=$(( $(stat -c %s "$f") / 4 ))
    echo "$tag: $n dwords" >> "$R/cases.txt"
    $N python3 -I "$S/markers.py" "$f" > "$R/$tag-markers.txt" 2>&1
    $N python3 -I "$S/ibwalk.py" "$f" 0 0 "$n" > "$R/$tag-walk.txt" 2>&1
  done
  # exp 0260's decode: waits, label writes, dispatches, and with two dumps of one timeout the cross references
  # shellcheck disable=SC2086
  [ -n "$dumps" ] && $N python3 -I "$E/dec0255.py" $dumps > "$R/$c-dec.txt" 2>&1
done
j=$C/play-20261023-2259/gc/direct.log
$N grep -an "submit #7676[5-9][0-9] \|timing: #7676[5-9][0-9] \|^learned\|AMM window\|amm window\|PRT\|prt window\|TIMEOUT\|^timeout" "$j" | grep -v "^[0-9]*:timeout probe:   " > "$R/2259-journal-lines.txt"
cp "$HOME/bc5-work/direct-learned-pkg.txt" "$R/direct-learned-pkg.txt"
ls -la "$R"
echo "== $(date +%T) done"
