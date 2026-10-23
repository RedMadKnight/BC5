#!/usr/bin/env bash
# Read-only extracts from exp 0211's lake-bench runs R11A/R11B/R11D for the compaction analysis (granted slot, no GPU).
# Writes only under ~/bc5-work/exp-cx/ (scratch) and holds one BOX-LOCK line meanwhile.
cd ~/bc5-work || exit 1
pgrep '^kyty_emulator' >/dev/null && { echo "emulator running: stop"; exit 1; }
[ -s BOX-LOCK ] && { echo "locked: $(cat BOX-LOCK)"; exit 1; }
echo "second-title-why-the-bvh | read-only journal greps R11A/R11B/R11D (granted) | start $(date +%H:%M) | until ~+8min" > BOX-LOCK
trap 'grep -q "read-only journal greps R11A" BOX-LOCK 2>/dev/null && rm -f BOX-LOCK' EXIT
O=~/bc5-work/exp-cx; mkdir -p $O
N="nice -n 10 ionice -c3"
for T in R11A R11B R11D; do
  echo "=== $T"
  ls exp0194/r-$T/ 2>/dev/null | tr '\n' ' '; echo
  # the capture directory: named in the run's output, else the newest play-* dir started within the run
  C=$(grep -a -o "/home/kjaniszewski/bc5-data/captures/play-[0-9-]*" exp0211/$T.out exp0194/r-$T/*.txt exp0194/r-$T/*.log 2>/dev/null | head -1 | sed 's/^[^:]*://')
  echo "capture: ${C:-?}"
  [ -n "$C" ] && [ -f "$C/gc/direct.log" ] || continue
  J=$C/gc/direct.log
  ls -la $J; ls $C/gc | grep -v direct.log | head -20
  LC_ALL=C $N grep -a -n -E "skip pgm|flat aperture|TIMEOUT|timeout|learned|reopen|fault|ib-timeout|probe:|unmapped VA|^frame profile: t [0-9]*\.[0-9]* s" $J \
    | awk -F: '/frame profile: t /{ split($0, a, " t "); split(a[2], b, " "); s=int(b[1]); if (s != last) { print $1 ":t " b[1]; last = s }; next } { print }' \
    | gzip > $O/$T-x.gz
  echo "lines: $(zcat $O/$T-x.gz | wc -l)"
done
ls -la $O
