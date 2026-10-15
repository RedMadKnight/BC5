#!/usr/bin/env bash
# ADR 0009 step 3 (experiment 0129): the second title's start screen as run 525, with job timestamps
# journaled from 165 to 180 s, with or without the compute ring. Maintainer present, hang watcher on.
# Usage: exp0129.sh <run> <label> [ENV=VALUE ...]
cd ~/bc5-work || exit 1
R=$1; LABEL=$2; shift 2
EXTRA=""
for kv in "$@"; do EXTRA="$EXTRA $kv"; done
sed -e "s/run 525 (start screen at GPU clock 1850-2150 MHz; maintainer present, hang watcher on)/run $R (start screen, $LABEL; maintainer present, hang watcher on)/" \
    -e "s/test525/test$R/" \
    -e "s|^exec |export BC5_DIRECT_JOB_TS=165:180$EXTRA\nexec |" run525.sh > run$R.sh
chmod +x run$R.sh
sync
(nohup sudo -n /usr/local/bin/bc5-gpu-hang-watch > /dev/null 2>&1 &)
sleep $((61 - $(date +%S | sed "s/^0//")))
pkill -9 -x steam 2>/dev/null
t0=$(date "+%Y-%m-%d %H:%M:%S")
(SHOTS=0129 ./shot.sh run$R-190 190 > /dev/null 2>&1 &)
distrobox enter ubuntu -- /home/kjaniszewski/bc5-work/run$R.sh > run$R.out 2>&1
sync
c=$(ls -td ~/bc5-data/captures/pkg-* | head -1); d=$c/gc/direct.log
printf "run %s (%s) capture %s timeouts=%s faults=%s resets=%s\n" "$R" "$LABEL" "$(basename $c)" "$(grep -c TIMEOUT $d)" \
  "$(journalctl _TRANSPORT=kernel --since "$t0" --no-pager | grep -c "in page starting")" \
  "$(journalctl _TRANSPORT=kernel --since "$t0" --no-pager | grep -ci "ring .* timeout\|reset")"
for w in "85 100" "130 165" "165 200"; do set -- $w; printf "  t%s-%s %s\n" $1 $2 "$(python3 frameprof.py $d $1 $2 | head -1)"; done
grep -E "compute ring|stays on the GFX ring" $d | head -5
grep -c "^jt \|\] jt " $d | sed "s/^/  jt lines: /"
python3 jtunion.py $d 2>/dev/null | tail -4
journalctl _TRANSPORT=kernel --since "$t0" --no-pager | grep -iE "amdgpu.*(timeout|reset|fault)" | head -5
