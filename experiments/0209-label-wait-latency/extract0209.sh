#!/usr/bin/env bash
# Experiment 0209 (TCP session): one filtering pass per tcpW journal, read-only. Keeps only the lines
# the wait-latency analysis needs: wait-trace lines (an unsatisfied game-thread wait, with its time,
# buffer size, dword, label), "timing: t … after that wait" (the host stopped waiting: served or given
# up), "cpu-wait … GIVEN UP", "two rings" lines, and the frame-profile lines. Output in ~/bc5-work/exp0209.
set -u
O=~/bc5-work/exp0209
mkdir -p "$O"
: > "$O/calibration.txt"
for s in 1652:tcpW1 1712:tcpW2 1732:tcpW2b 1742:tcpW1b 1811:B1b 1825:B2; do
  d=${s%%:*}; t=${s##*:}
  f=~/bc5-data/captures/play-20261022-$d/gc/direct.log
  nice -n 19 ionice -c3 grep -E '^wait trace: t |^timing: t [0-9.]+ s after that wait|^cpu-wait |^two rings: |^frame profile: t ' "$f" > "$O/$t-extract.txt"
  # wall-clock calibration: the file's last write against the last journal time in its tail
  mt=$(stat -c %Y "$f"); lt=$(tail -c 400000 "$f" | grep -o '^[a-z ]*t [0-9][0-9.]* s' | tail -1 | grep -o '[0-9][0-9.]*')
  echo "$t mtime $mt ($(date -d @$mt +%T)) last_t $lt" >> "$O/calibration.txt"
  echo "$t: $(wc -l < "$O/$t-extract.txt") lines, $(du -h "$O/$t-extract.txt" | cut -f1); mtime $(date -d @$mt +%T), last t $lt s"
done
