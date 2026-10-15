#!/usr/bin/env bash
# Experiment 0129, menu: the second title's Initial Setup and Settings > Visuals scrolled as in run 513
# (experiment 0122), with the flip brightness detector (jumps of more than 3 points) and screenshots;
# with or without the compute ring. Maintainer present, hang watcher on.
# Usage: exp0129m.sh <run> <label> [ENV=VALUE ...]
cd ~/bc5-work || exit 1
R=$1; LABEL=$2; shift 2
EXTRA=""
for kv in "$@"; do EXTRA="$EXTRA $kv"; done
sed -e "s/test513/test$R/" -e "s|^exec |export BC5_DIRECT_JOB_TS=120:135$EXTRA\nexec |" run513.sh > run$R.sh
sed -i "2i # BC5 run $R (menu, $LABEL; experiment 0129)" run$R.sh
chmod +x run$R.sh
sync
(nohup sudo -n /usr/local/bin/bc5-gpu-hang-watch > /dev/null 2>&1 &)
sleep $((61 - $(date +%S | sed "s/^0//")))
pkill -9 -x steam 2>/dev/null
t0=$(date "+%Y-%m-%d %H:%M:%S")
for t in 95 110 125 140 155 170 185 200; do (SHOTS=0129 ./shot.sh menu$R-$t $t > /dev/null 2>&1 &); done
distrobox enter ubuntu -- /home/kjaniszewski/bc5-work/run$R.sh > run$R.out 2>&1
sync
c=$(ls -td ~/bc5-data/captures/pkg-* | head -1); d=$c/gc/direct.log
printf "run %s (%s) capture %s timeouts=%s faults=%s\n" "$R" "$LABEL" "$(basename $c)" "$(grep -c TIMEOUT $d)" \
  "$(journalctl _TRANSPORT=kernel --since "$t0" --no-pager | grep -c "in page starting")"
printf "  flip bright jumps (>3 points) from 85 s: %s; last: %s\n" "$(grep -c "flip bright: t .* lit (was" $d)" "$(grep "flip bright: t .* jumps" $d | tail -1 | cut -c1-120)"
python3 frameprof.py $d 120 135 | head -1
python3 jtrings.py $d 2>/dev/null | head -4
journalctl _TRANSPORT=kernel --since "$t0" --no-pager | grep -iE "amdgpu.*(timeout|reset|fault)" | head -5
