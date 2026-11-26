#!/usr/bin/env bash
# BC5 experiment 0344: which checked dispatch of acb #76004 sat at the CP's fetch point when exp 0342's R2 hung
# (2026-10-27 12:39:19, F416: PFP 0xea1 / ME 0x77b, IB 6,584 dwords, CP_IB1_BUFSZ 2,840). READ-ONLY on the box: it
# reads the timeout dump, the journal, exp 0342's probe and play extracts, and writes text into ~/bc5-work/exp0344/raw
# only — offsets, counts, opcodes, program and argument addresses, the probe's numbers. No dword of a buffer is
# copied anywhere; the dump stays where it is. Every step runs under ionice -c3 nice -n 19, with the guard: no
# emulator running and an empty BOX-LOCK, our own line in the lock while it runs.
# usage: probe0344.sh   (on the box, with ibmap0344.pl and known0344.txt beside it; ~1 min, most of it one grep
#        over the 428 MB journal)   BC5_0344_CAPTURE=<dir> BC5_0344_CS_SIZE=<dw> BC5_0344_BUFSZ=<dw> to override
set -u
CAP=${BC5_0344_CAPTURE:-$HOME/bc5-data/captures/play-20261027-1237}
DUMP=$CAP/gc/ib-timeout-00076004-acb-2605.bin
JOURNAL=$CAP/gc/direct.log
PROBE=$HOME/bc5-work/exp0342/raw/R2-probe.txt
PLAY=$HOME/bc5-work/exp0342/raw/R2-play.log
CS_SIZE=${BC5_0344_CS_SIZE:-6584}; BUFSZ=${BC5_0344_BUFSZ:-2840}
E=$HOME/bc5-work/exp0344; R=$E/raw; LOCK=$HOME/bc5-work/BOX-LOCK
HERE=$(cd "$(dirname "$0")" && pwd)
N="ionice -c3 nice -n 19"
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator runs: stop"; exit 1; }
[ -e "$LOCK" ] || touch "$LOCK"
[ -s "$LOCK" ] && { echo "box locked: $(cat "$LOCK")"; exit 1; }
for f in "$DUMP" "$JOURNAL" "$HERE/ibmap0344.pl" "$HERE/known0344.txt"; do [ -r "$f" ] || { echo "not readable: $f"; exit 1; }; done
echo "bvh exp 0344 | read-only: the timeout dump of acb #76004 mapped to the fetch point (perl + grep, ionice idle, nice 19; no emulator) | start $(date +%H:%M) | until ~$(date -d +5min +%H:%M)" > "$LOCK"
trap 'grep -q "^bvh exp 0344 | read-only" "$LOCK" 2> /dev/null && : > "$LOCK"' EXIT
mkdir -p "$R"
{
  echo "== $(date '+%F %T') exp 0344 probe; kernel $(uname -r); host $(hostname)"
  echo "dump: $DUMP $(stat -c '%s bytes, %y' "$DUMP") md5 $(md5sum < "$DUMP" | cut -c1-8)"
  echo "journal: $JOURNAL $(stat -c '%s bytes, %y' "$JOURNAL")"
  for f in "$PROBE" "$PLAY"; do [ -r "$f" ] && echo "extract: $f $(stat -c '%s bytes' "$f"), $(wc -l < "$f") lines" || echo "extract missing: $f"; done
  echo "ibmap0344.pl $(md5sum < "$HERE/ibmap0344.pl" | cut -c1-8); CS size $CS_SIZE, CP_IB1_BUFSZ $BUFSZ"
} > "$R/inputs.txt"
cat "$R/inputs.txt"
echo "== $(date +%T) 1. the dump's packets mapped to the job IB (ibmap0344.pl)"
$N perl "$HERE/ibmap0344.pl" "$DUMP" "$CS_SIZE" "$BUFSZ" "$HERE/known0344.txt" > "$R/ibmap.txt" 2>&1
rc=$?; echo "rc $rc"; sed -n '1,14p' "$R/ibmap.txt"
echo "== $(date +%T) 2. the journal: acb #76004's timeout-probe section, and the 40 lines before its submit line"
L=$($N grep -a -n "timeout probe: acb 2605 dwords dumped\|timeout probe: acb #76004 \|submit #76004 acb\|submit #76005 dcb\|timeout probe: dcb #76005 " "$JOURNAL" | head -20)
echo "$L" | cut -c1-160 > "$R/journal-marks.txt"; cat "$R/journal-marks.txt"
A=$(echo "$L" | grep "timeout probe: acb 2605 dwords dumped" | head -1 | cut -d: -f1)
B=$(echo "$L" | grep "timeout probe: acb #76004 " | head -1 | cut -d: -f1)
S=$(echo "$L" | grep "submit #76004 acb" | head -1 | cut -d: -f1)
if [ -n "$A" ] && [ -n "$B" ] && [ "$B" -gt "$A" ]; then
  $N sed -n "${A},${B}p" "$JOURNAL" > "$R/journal-acb-probe.txt"
  echo "acb probe section: lines $A-$B ($(wc -l < "$R/journal-acb-probe.txt") lines): $(grep -c 'dispatch op' "$R/journal-acb-probe.txt") dispatch lines, $(grep -c 'wait op' "$R/journal-acb-probe.txt") wait lines, $(grep -c 'write op' "$R/journal-acb-probe.txt") write lines"
  tail -1 "$R/journal-acb-probe.txt" | cut -c1-300
else
  echo "the acb's probe section was not found in the journal (A='$A' B='$B')"
fi
[ -n "$S" ] && $N sed -n "$((S > 40 ? S - 40 : 1)),$((S + 6))p" "$JOURNAL" | cut -c1-300 > "$R/journal-before-submit.txt" && echo "context before the submit line: $(wc -l < "$R/journal-before-submit.txt") lines in raw/journal-before-submit.txt"
echo "== $(date +%T) 3. the candidate dispatches: the dump offsets ibmap names, looked up in the probe's lines (program, groups read at the timeout, arguments)"
: > "$R/candidates.txt"
grep -o '^  #[0-9]*: [0-9]* ->' "$R/ibmap.txt" | awk '{print $2}' | tr -d ':' | sort -un | while read -r q; do
  [ -r "$R/journal-acb-probe.txt" ] && grep -a "dispatch op 1[56] at ${q}:" "$R/journal-acb-probe.txt" >> "$R/candidates.txt"
done
echo "$(wc -l < "$R/candidates.txt") candidate lines:"; cut -c1-260 "$R/candidates.txt"
echo "== $(date +%T) 4. exp 0342's extracts"
[ -r "$PROBE" ] && { grep -a -c "dispatch op" "$PROBE" | sed 's/^/R2-probe.txt dispatch lines: /'; grep -a "largest grid\|#76004\|#76005" "$PROBE" | cut -c1-300 > "$R/probe-summary.txt"; cat "$R/probe-summary.txt"; }
[ -r "$PLAY" ] && { grep -a -n "TIMEOUT\|timed out\|experiment 0341 periodic\|experiment 0341 switches\|fps counter: t 10[0-9]\.\|fps counter: t 11[0-9]\.\|ray tracing\|wedged\|reset" "$PLAY" | tail -40 | cut -c1-260 > "$R/play-around-the-hang.txt"; echo "play log lines around the hang: $(wc -l < "$R/play-around-the-hang.txt") in raw/play-around-the-hang.txt"; }
echo "== $(date +%T) 5. the programs of the buffer and the fetch-point readings (from raw/ibmap.txt)"
sed -n '/^fetch point/,$p' "$R/ibmap.txt" | cut -c1-260
echo "== $(date +%T) done; raw text in $R (no buffer contents); lock released on exit"
