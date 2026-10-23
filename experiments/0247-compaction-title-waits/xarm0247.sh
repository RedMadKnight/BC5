#!/usr/bin/env bash
# BC5 experiment 0247 (exp 0246's xarm.sh with the wait-trace and emulator-log lines). Box side, right after one bench arm (its slot still ours): the run's journal lines the analysis needs, in one pass,
# gzipped into ~/bc5-work/exp<N>/<tag>-x.gz, plus the run's environment and dmesg summary.
# usage: xarm.sh <N> <tag>
N=$1; TAG=$2
cd ~/bc5-work || exit 1
pgrep '^kyty_emulator' >/dev/null && { echo "emulator running: stop"; exit 1; }
[ -s BOX-LOCK ] && { echo "locked: $(cat BOX-LOCK)"; exit 1; }
echo "second-title-why-the-bvh exp $N | extract $TAG (granted slot) | start $(date +%H:%M) | until ~+3min" > BOX-LOCK
trap 'grep -q "exp $N | extract $TAG " BOX-LOCK 2>/dev/null && rm -f BOX-LOCK' EXIT
R=exp0194/r-$TAG
C=$(cat $R/journal-dir.txt 2>/dev/null | head -1)
[ -n "$C" ] || C=$(grep -a -o "/home/kjaniszewski/bc5-data/captures/play-[0-9-]*" exp$N/$TAG.out $R/*.txt 2>/dev/null | head -1 | sed 's/^[^:]*://')
C=${C%/gc}; C=${C%/gc/direct.log}
J=$C/gc/direct.log
echo "journal: $J ($(stat -c %s $J 2>/dev/null) bytes)"
LC_ALL=C nice -n 10 ionice -c3 grep -a -E "^frame profile: t |^wait trace: t |^timing: t [0-9.]+ s after that wait|^cpu-wait |^two rings: |skip pgm|flat aperture|TIMEOUT|timeout: |timeout probe: (dcb|acb)|^submit #.*FAILED|learned 0x|reopen" $J | gzip > exp$N/$TAG-x.gz
echo "lines: $(zcat exp$N/$TAG-x.gz | wc -l)"
ls $C/gc | grep ib-timeout
cp $R/env.txt exp$N/$TAG-env.txt 2>/dev/null; LC_ALL=C grep -a -E 'bc5 clock|amm trace:' $R/emu.log | gzip > exp$N/$TAG-emu-x.gz; echo "emu lines: $(zcat exp$N/$TAG-emu-x.gz | wc -l)"; cp $R/dmesg.txt exp$N/$TAG-dmesg.txt 2>/dev/null
tail -3 exp$N/$TAG.out
