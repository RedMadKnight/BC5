#!/usr/bin/env bash
# exp 0218: one pass over the play journal, the lines the summary and the stats need, into exp0218/
cd ~/bc5-work/exp0218 || exit 1
d=~/bc5-data/captures/play-20261022-2058
j=$d/gc/direct.log
ls -la $j
LC_ALL=C grep -a -E "^frame profile: t |^direct: [0-9]* views|^submit #|flat aperture|skip pgm|TIMEOUT|timeout: fault|^timing: #|learned region" $j | gzip > jx.gz
zcat jx.gz | wc -l
{
  echo "journal $(stat -c %s $j) bytes"
  echo "flat aperture lines: $(zcat jx.gz | grep -ac "flat aperture"); skip pgm lines: $(zcat jx.gz | grep -ac "skip pgm"); TIMEOUT: $(zcat jx.gz | grep -ac TIMEOUT); timeout: fault: $(zcat jx.gz | grep -ac "timeout: fault")"
  zcat jx.gz | grep -a "flat aperture" | cut -c1-160
  zcat jx.gz | grep -a "skip pgm" | sort | uniq -c | head -5 | cut -c1-160
  echo "fence waits > 300 ms:"
  zcat jx.gz | grep -a "^timing: #" | awk "{ for (i=1;i<=NF;i++) if (\$i==\"fence\" && \$(i+1)+0 > 300) { print; break } }" | cut -c1-200
  echo "learned regions:"
  zcat jx.gz | grep -a "learned region" | head -5 | cut -c1-200
  echo "emulator log tail:"
  tail -2 emu.log | cut -c1-200
} > summary.txt
cat summary.txt
