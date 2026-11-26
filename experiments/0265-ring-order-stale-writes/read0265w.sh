#!/usr/bin/env bash
# BC5 experiment 0265, data point: the water session's W266a (exp 0266, 2026-10-24 17:03-17:05, exp 0251's private binary
# of 2026-10-23, without exp 0260's synced probe): six TCP write faults at 0x145e628000-0x145e62d000, then comp_1.1.0 and
# gfx_0.0.0 timeouts whose resets succeeded. Read-only, in the box supervisor's window, under a short lock line:
#   - the capture directory's timeout-probe dumps through exp 0255's dec0255.py (waits, label writes, dispatches, and the
#     cross references of the stuck pair);
#   - the journal: the TIMEOUT and probe lines (not the state lines), the fault-query and learned-window lines, the hold,
#     give-up and two-ring lines in the 40,000 lines before the timeout, and the last 60 lines before it;
#   - the water session's emulator log of the run, if kept (only its error, fault and timeout lines).
# Output under ~/bc5-work/exp0265/raw/W266a-*; only offsets, labels, register values, counts and the host's own lines.
# usage: read0265w.sh   (on the box)
set -u
E=$HOME/bc5-work/exp0265; R=$E/raw; LOCK=$HOME/bc5-work/BOX-LOCK
C=$HOME/bc5-data/captures/play-20261024-1703/gc; J=$C/direct.log; DEC=$HOME/bc5-work/exp0255/dec0255.py
N="nice -n 19 ionice -c3"
pgrep -x kyty_emulator > /dev/null && { echo "an emulator runs: stop"; exit 1; }
[ -s "$LOCK" ] && { echo "box locked: $(cat "$LOCK")"; exit 1; }
mkdir -p "$R"
echo "tcp exp 0265 | read-only: W266a's dumps and journal (water's run), no GPU | start $(date +%H:%M) | until ~$(date -d +5min +%H:%M)" > "$LOCK"
trap 'grep -q "^tcp exp 0265 | read-only: W266a" "$LOCK" 2> /dev/null && rm -f "$LOCK"' EXIT
ls -la "$C" > "$R/W266a-capture-dir.txt"
dumps=$(ls "$C"/ib-timeout-*.bin 2> /dev/null | grep -v '\.bin\.')
# shellcheck disable=SC2086
if [ -n "$dumps" ]; then $N python3 -I "$DEC" $dumps > "$R/W266a-dec.txt" 2>&1; else echo "no timeout-probe dumps" > "$R/W266a-dec.txt"; fi
n=$(grep -an "TIMEOUT" "$J" | head -1 | cut -d: -f1)
{ echo "journal $J $(stat -c '%y %s' "$J"), first TIMEOUT at line ${n:-none}"
  $N grep -an "TIMEOUT\|^timeout probe: [ad]cb\|^timeout: \|^learned\|AMM\|PRT" "$J" | grep -v "^[0-9]*:learned 0x[0-9a-f]*: window" | cut -c1-260
} > "$R/W266a-journal-lines.txt"
if [ -n "$n" ]; then
  $N sed -n "$((n > 40000 ? n - 40000 : 1)),$((n + 2000))p" "$J" | grep -an "12004b[0-9a-f]*\(c8\|38\)\|^two rings\|cpu-wait\|^ring order\|GIVEN UP\|NOT served\|cycle broken\|^hold tail\|^acb head\|TIMEOUT" | cut -c1-260 > "$R/W266a-labels-near-timeout.txt"
  $N sed -n "$((n > 60 ? n - 60 : 1)),$((n + 8))p" "$J" | cut -c1-300 > "$R/W266a-journal-tail.txt"
fi
ls -la "$HOME/bc5-work/exp0266/r-W266a" > "$R/W266a-run-dir.txt" 2>&1
for f in "$HOME"/bc5-work/exp0266/r-W266a/*.log "$HOME"/bc5-work/exp0266/r-W266a/*.out "$HOME"/bc5-work/exp0266/*W266a*.log; do
  [ -f "$f" ] && { echo "== $f"; $N grep -a -i "error\|fault\|timeout\|terminate\|abort\|segmentation" "$f" | cut -c1-220 | head -60; }
done > "$R/W266a-emulog-lines.txt" 2>&1
wc -l "$R"/W266a-*.txt
echo "== $(date +%T) done"
